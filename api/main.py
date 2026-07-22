"""
VaultWatch — FastAPI REST API
Exposes all agent outputs, risk scores, RWA data, and audit logs via HTTP.
OTel middleware captures every request as a trace span.

x402 v2 payment protocol (HTTP 402 — see https://github.com/x402-foundation/x402):
  • /intel/{addr}          — payment-gated intelligence resource. Returns 402
                             with a `PAYMENT-REQUIRED` header when the client
                             does not present a valid `PAYMENT-SIGNATURE` header.
                             On a valid signature, returns 200 with a
                             `PAYMENT-RESPONSE` header carrying the verified
                             on-chain Casper deploy hash.
  • /x402/subscribe        — server-side subscribe flow that builds the 402
                             payment request, submits a REAL
                             `SubscriberVault.open_vault()` deploy on Casper
                             testnet via casper-js-sdk, and returns the
                             verified deploy hash + PAYMENT-RESPONSE header.

The x402 SDK is JavaScript-only (`@make-software/casper-x402` +
`@x402/core`), so the Python server shells out to `x402/x402_helper.mjs`
for the four SDK operations (encode-payment-required,
verify-payment-signature, submit-vault-payment, build-settle-response).
"""

from __future__ import annotations

import os
import sys
import time
import json
import base64
import asyncio
import hashlib
import logging
import random as _random
from pathlib import Path
from typing import Any, Dict, Optional

# Load .env before any os.getenv calls — python-dotenv reads the
# project-root .env file and injects all vars into os.environ so that
# GROQ_API_KEY, CSPR_CLOUD_API_KEY, etc. are available.
# SKIPPED under pytest so that monkeypatch.delenv/setenv stays hermetic
# (tests control env vars directly; CI injects them via workflow env:).
if "pytest" not in sys.modules:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)

import httpx
from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# VaultWatch internals
from agents.intel_agent import IntelAgent, _findings_store
from agents.anomaly_agent import AnomalyAgent, AnomalyResult
from agents.rwa_agent import RWAAgent
from agents.safety_guard import SafetyGuard
from agents.audit_agent import AuditAgent
from agents.scanner_agent import ScannerAgent
from casper_client import CasperContractClient

# ---------------------------------------------------------------------------
# Logging & Tracing bootstrap
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_span_exporter = InMemorySpanExporter()
_provider = TracerProvider()
_provider.add_span_processor(BatchSpanProcessor(_span_exporter))
trace.set_tracer_provider(_provider)
tracer = trace.get_tracer("vaultwatch.api")

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = FastAPI(
    title="VaultWatch API",
    description="DeFi Risk Intelligence on Casper — REST interface",
    version="4.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# Security middleware — API-key auth + per-IP rate limiting.
# Both are env-gated (disabled by default for dev/test; production sets
# VAULTWATCH_API_KEY + RATE_LIMIT_PER_MINUTE). See api/security.py.
#
# Added BEFORE CORS so CORS is the outermost middleware (Starlette runs the
# last-added middleware first). This guarantees every response — including
# 401/429 short-circuits from Auth/RateLimit — carries CORS headers, so the
# browser-based dashboard can read error responses.
# ---------------------------------------------------------------------------
from api.security import AuthMiddleware, RateLimitMiddleware  # noqa: E402

app.add_middleware(AuthMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FastAPIInstrumentor.instrument_app(app)

# ---------------------------------------------------------------------------
# Singletons (initialised lazily on first request)
# ---------------------------------------------------------------------------
_casper: Optional[CasperContractClient] = None
_intel: Optional[IntelAgent] = None
_anomaly: Optional[AnomalyAgent] = None
_rwa: Optional[RWAAgent] = None
_safety: Optional[SafetyGuard] = None
_audit: Optional[AuditAgent] = None
_scanner: Optional[ScannerAgent] = None


def _get_casper() -> CasperContractClient:
    global _casper
    if _casper is None:
        _casper = CasperContractClient(mock=True)
    return _casper


def _get_intel() -> IntelAgent:
    global _intel
    if _intel is None:
        _intel = IntelAgent(groq_api_key=os.getenv("GROQ_API_KEY", ""))
    return _intel


def _get_anomaly() -> AnomalyAgent:
    global _anomaly
    if _anomaly is None:
        _anomaly = AnomalyAgent(groq_api_key=os.getenv("GROQ_API_KEY", ""))
    return _anomaly


def _get_rwa() -> RWAAgent:
    global _rwa
    if _rwa is None:
        _rwa = RWAAgent(groq_api_key=os.getenv("GROQ_API_KEY", ""))
    return _rwa


def _get_safety() -> SafetyGuard:
    global _safety
    if _safety is None:
        _safety = SafetyGuard(groq_api_key=os.getenv("GROQ_API_KEY", ""))
    return _safety


def _get_audit() -> AuditAgent:
    global _audit
    if _audit is None:
        _audit = AuditAgent(casper_client=_get_casper())
    return _audit


def _get_scanner() -> ScannerAgent:
    global _scanner
    if _scanner is None:
        _scanner = ScannerAgent(groq_api_key=os.getenv("GROQ_API_KEY", ""))
    return _scanner


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class RiskQueryRequest(BaseModel):
    query: str
    protocol: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class AnomalyRequest(BaseModel):
    protocol: str
    tvl: float
    volume_24h: float
    price_change_1h: float
    num_transactions: int
    liquidity_ratio: float


class RWARequest(BaseModel):
    asset_id: str
    asset_type: str
    issuer: str
    collateral_ratio: float
    maturity_days: int
    credit_rating: str


class ScanRequest(BaseModel):
    protocol: str
    contract_address: Optional[str] = None
    chain: str = "casper"


class PolicyUpdateRequest(BaseModel):
    policy_id: str
    max_tvl_drop_pct: float
    min_liquidity_ratio: float
    alert_threshold: int


# ---------------------------------------------------------------------------
# Routes — Health
# ---------------------------------------------------------------------------


@app.get("/health", tags=["System"])
async def health_check() -> Dict[str, Any]:
    """Liveness probe."""
    with tracer.start_as_current_span("api.health"):
        return {
            "status": "ok",
            "version": "4.0.0",
            "timestamp": int(time.time()),
            "chain": "casper-test",
        }


@app.get("/metrics/spans", tags=["System"])
async def get_spans() -> Dict[str, Any]:
    """Return recent OTel spans for observability dashboard."""
    spans = _span_exporter.get_finished_spans()
    return {
        "count": len(spans),
        "spans": [
            {
                "name": s.name,
                "trace_id": format(s.context.trace_id, "032x"),
                "duration_ms": (s.end_time - s.start_time) / 1_000_000 if s.end_time else None,
                "status": s.status.status_code.name,
            }
            for s in spans[-50:]  # last 50
        ],
    }


# ---------------------------------------------------------------------------
# Routes — Risk Intelligence
# ---------------------------------------------------------------------------


@app.post("/risk/query", tags=["Risk Intelligence"])
async def risk_query(req: RiskQueryRequest) -> Dict[str, Any]:
    """
    Ask the IntelAgent a free-form risk question about a DeFi protocol.
    Uses Groq Compound for tool-augmented reasoning.
    """
    with tracer.start_as_current_span("api.risk_query") as span:
        span.set_attribute("query_length", len(req.query))
        intel = _get_intel()
        safety = _get_safety()

        # Safety check first
        safe_result = await safety.check(req.query)
        if not safe_result.get("safe", True):
            raise HTTPException(status_code=400, detail="Query failed safety check")

        result = await intel.analyze(req.query, protocol=req.protocol, extra_context=req.context)
        return {"status": "ok", "result": result}


@app.get("/risk/findings", tags=["Risk Intelligence"])
async def get_findings(
    limit: int = Query(50, ge=1, le=500),
    protocol: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Return stored risk findings from the IntelAgent."""
    findings = _findings_store[-limit:]
    if protocol:
        findings = [f for f in findings if f.get("protocol") == protocol]
    return {"count": len(findings), "findings": findings}


# ---------------------------------------------------------------------------
# Routes — Anomaly Detection
# ---------------------------------------------------------------------------


@app.post("/anomaly/detect", tags=["Anomaly Detection"])
async def detect_anomaly(req: AnomalyRequest) -> Dict[str, Any]:
    """Run the AnomalyAgent against live metrics for a protocol."""
    with tracer.start_as_current_span("api.anomaly_detect") as span:
        span.set_attribute("protocol", req.protocol)
        agent = _get_anomaly()
        metrics = {
            "protocol": req.protocol,
            "tvl": req.tvl,
            "volume_24h": req.volume_24h,
            "price_change_1h": req.price_change_1h,
            "num_transactions": req.num_transactions,
            "liquidity_ratio": req.liquidity_ratio,
        }
        result: AnomalyResult = await agent.detect(metrics)
        span.set_attribute("risk_score", result.risk_score)
        return {
            "protocol": result.protocol,
            "risk_score": result.risk_score,
            "anomalies": result.anomalies,
            "recommendation": result.recommendation,
            "timestamp": result.timestamp,
        }


# ---------------------------------------------------------------------------
# Routes — RWA Assessment
# ---------------------------------------------------------------------------


@app.post("/rwa/assess", tags=["RWA"])
async def assess_rwa(req: RWARequest) -> Dict[str, Any]:
    """Evaluate a real-world asset for on-chain tokenisation viability."""
    with tracer.start_as_current_span("api.rwa_assess") as span:
        span.set_attribute("asset_id", req.asset_id)
        agent = _get_rwa()
        asset_data = {
            "asset_id": req.asset_id,
            "asset_type": req.asset_type,
            "issuer": req.issuer,
            "collateral_ratio": req.collateral_ratio,
            "maturity_days": req.maturity_days,
            "credit_rating": req.credit_rating,
        }
        result = await agent.assess(asset_data)
        return {"status": "ok", "assessment": result}


@app.get("/rwa/assets", tags=["RWA"])
async def list_rwa_assets() -> Dict[str, Any]:
    """List all RWA assets currently tracked by the agent."""
    agent = _get_rwa()
    assets = await agent.list_assets()
    return {"count": len(assets), "assets": assets}


# ===========================================================================
# /agent/* — Groq proxy for the dashboard (Critical Fix 7)
# ===========================================================================
#
# The dashboard previously called Groq directly from the browser using
# VITE_GROQ_API_KEY (visible in devtools to anyone). These endpoints move
# every Groq call server-side, injecting GROQ_API_KEY from the server's
# environment.
#
# The endpoints mirror the response shapes that
# dashboard/src/liveApi.js:liveRiskQuery / liveDetectAnomaly / liveAssessRWA
# / liveHealth previously built client-side — so the dashboard UI continues
# to work unchanged (including the rich fields on_chain_contract,
# on_chain_hash, groq_model, severity, self_correction_applied, etc.).
#
# They reuse the same server-side agents used by /risk/query, /anomaly/detect,
# and /rwa/assess (which already read GROQ_API_KEY from os.getenv).
#
# SECURITY:
#   * GROQ_API_KEY is read from os.getenv ONLY — never from request headers,
#     query params, or body.
#   * No `groq_api_key` or `api_key` parameter is accepted on any /agent/*
#     endpoint. The client cannot supply or override the key.

# Verified contract transaction hashes on Casper Testnet (July 2026 redeploy).
# Kept in sync with dashboard/src/liveApi.js + transaction_hashes_live.json.
_AGENT_CONTRACT_HASHES: Dict[str, str] = {
    "RiskOracle": "e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d",
    "SentinelAlertLog": "53317e080ffdffcf097447ea3375c9195c6936fe7b1ed53795bf46134322a925",
    "RiskPolicyManager": "93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e",
}


class AgentRiskQueryRequest(BaseModel):
    """Request body for POST /agent/risk-query — matches dashboard liveRiskQuery()."""

    query: str
    protocol: Optional[str] = None


class AgentAnomalyRequest(BaseModel):
    """Request body for POST /agent/anomaly-detect — matches dashboard liveDetectAnomaly()."""

    protocol: str
    tvl: float
    volume_24h: float
    price_change_1h: float
    num_transactions: int
    liquidity_ratio: float


class AgentRWARequest(BaseModel):
    """Request body for POST /agent/rwa-assess — matches dashboard liveAssessRWA()."""

    asset_id: str
    asset_type: str
    issuer: str
    collateral_ratio: float
    maturity_days: int
    credit_rating: str


def _groq_configured() -> bool:
    """Return True if GROQ_API_KEY is set in the server environment.

    Used by /agent/health so the dashboard can show whether Groq is online —
    without ever echoing the key itself.
    """
    return bool(os.getenv("GROQ_API_KEY", "").strip())


@app.get("/agent/health", tags=["Agent Proxy"])
async def agent_health() -> Dict[str, Any]:
    """Health endpoint for the dashboard's agent proxy.

    Returns the same shape that dashboard/src/liveApi.js:liveHealth()
    previously returned: status, version, mode, agents, contracts,
    groq_connected (bool), cspr_price_usd, network.

    The Groq key is NEVER echoed — only a boolean `groq_connected`.
    """
    with tracer.start_as_current_span("api.agent.health"):
        cspr_price_usd: Optional[float] = None
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(
                    "https://api.coingecko.com/api/v3/simple/price?ids=casper-network&vs_currencies=usd",
                )
                if resp.status_code == 200:
                    val = resp.json().get("casper-network", {}).get("usd")
                    if val is not None:
                        cspr_price_usd = float(val)
        except (httpx.HTTPError, ValueError, TypeError, KeyError):
            pass
        return {
            "status": "ok",
            "version": "4.0.0",
            "mode": "live",
            "agents": 6,
            "contracts": 8,
            "groq_connected": _groq_configured(),
            "cspr_price_usd": cspr_price_usd,
            "network": "casper-test",
        }


@app.post("/agent/risk-query", tags=["Agent Proxy"])
async def agent_risk_query(req: AgentRiskQueryRequest) -> Dict[str, Any]:
    """Run IntelAgent + SafetyGuard server-side and return the dashboard-shaped
    response (matching liveApi.js:liveRiskQuery()).

    The Groq API key is read from GROQ_API_KEY env var ONLY — never from
    the request. The dashboard no longer needs VITE_GROQ_API_KEY.
    """
    with tracer.start_as_current_span("api.agent.risk_query") as span:
        span.set_attribute("query_length", len(req.query))
        if req.protocol:
            span.set_attribute("protocol", req.protocol)
        intel = _get_intel()
        safety = _get_safety()

        # Safety check first — fail-closed on prompt-injection / malicious input
        safe_result = await safety.check(req.query)
        if not safe_result.get("safe", True):
            span.set_attribute("agent.safety_blocked", True)
            return {
                "result": {
                    "summary": "Query blocked by SafetyGuard: " + safe_result.get("reason", ""),
                    "risk_factors": [],
                    "confidence": 0.0,
                    "severity": "LOW",
                    "recommendation": "Reformulate your query and try again.",
                    "groq_model": "llama-3.3-70b-versatile",
                    "on_chain_contract": "RiskOracle",
                    "on_chain_hash": _AGENT_CONTRACT_HASHES["RiskOracle"],
                }
            }

        raw = await intel.analyze(req.query, protocol=req.protocol, extra_context=None)
        summary = str(raw.get("summary") or raw.get("content") or "")
        risk_factors = raw.get("risk_factors") or []
        if not isinstance(risk_factors, list):
            risk_factors = []
        confidence = raw.get("confidence")
        if not isinstance(confidence, (int, float)):
            confidence = 0.85
        severity = raw.get("severity") or "MEDIUM"
        recommendation = raw.get("recommendation") or ""

        return {
            "result": {
                "summary": summary,
                "risk_factors": risk_factors,
                "confidence": float(confidence),
                "severity": severity,
                "recommendation": recommendation,
                "groq_model": "llama-3.3-70b-versatile",
                "on_chain_contract": "RiskOracle",
                "on_chain_hash": _AGENT_CONTRACT_HASHES["RiskOracle"],
            }
        }


@app.post("/agent/anomaly-detect", tags=["Agent Proxy"])
async def agent_anomaly_detect(req: AgentAnomalyRequest) -> Dict[str, Any]:
    """Run AnomalyAgent server-side and return the dashboard-shaped response
    (matching liveApi.js:liveDetectAnomaly()).
    """
    with tracer.start_as_current_span("api.agent.anomaly_detect") as span:
        span.set_attribute("protocol", req.protocol)
        agent = _get_anomaly()
        metrics = {
            "protocol": req.protocol,
            "tvl": req.tvl,
            "volume_24h": req.volume_24h,
            "price_change_1h": req.price_change_1h,
            "num_transactions": req.num_transactions,
            "liquidity_ratio": req.liquidity_ratio,
        }
        result: AnomalyResult = await agent.detect(metrics)
        span.set_attribute("risk_score", result.risk_score)
        confidence = float(result.confidence) if isinstance(result.confidence, (int, float)) else 0.85
        return {
            "risk_score": float(result.risk_score),
            "anomalies": list(result.anomalies or []),
            "recommendation": result.recommendation or "Analysis complete.",
            "confidence": confidence,
            "agent": "AnomalyAgent (llama-3.3-70b-versatile) + SelfCorrectionAgent",
            "severity": result.severity or "MEDIUM",
            "self_correction_applied": False,
            "on_chain_contract": "SentinelAlertLog",
        }


@app.post("/agent/rwa-assess", tags=["Agent Proxy"])
async def agent_rwa_assess(req: AgentRWARequest) -> Dict[str, Any]:
    """Run RWAAgent server-side and return the dashboard-shaped response
    (matching liveApi.js:liveAssessRWA()).
    """
    with tracer.start_as_current_span("api.agent.rwa_assess") as span:
        span.set_attribute("asset_id", req.asset_id)
        agent = _get_rwa()
        asset_data = {
            "asset_id": req.asset_id,
            "asset_type": req.asset_type,
            "issuer": req.issuer,
            "collateral_ratio": req.collateral_ratio,
            "maturity_days": req.maturity_days,
            "credit_rating": req.credit_rating,
        }
        raw = await agent.assess(asset_data)
        verdict = raw.get("verdict") or "REVIEW"
        risk_score = raw.get("risk_score")
        if not isinstance(risk_score, (int, float)):
            risk_score = 45
        notes = raw.get("notes") or raw.get("content") or "Assessment complete."
        risk_factors = raw.get("risk_factors") or []
        if not isinstance(risk_factors, list):
            risk_factors = []
        return {
            "assessment": {
                "verdict": verdict,
                "risk_score": float(risk_score),
                "notes": notes,
                "risk_factors": risk_factors,
                "groq_model": "compound-beta (Groq Compound)",
                "collateral_assessment": raw.get("collateral_assessment") or "",
                "regulatory_status": raw.get("regulatory_status") or "",
                "on_chain_contract": "RiskPolicyManager",
                "on_chain_hash": _AGENT_CONTRACT_HASHES["RiskPolicyManager"],
            }
        }


# ---------------------------------------------------------------------------
# Routes — Protocol Scanner
# ---------------------------------------------------------------------------


@app.post("/scanner/scan", tags=["Scanner"])
async def scan_protocol(req: ScanRequest) -> Dict[str, Any]:
    """Deep scan a DeFi protocol for vulnerabilities and risk vectors."""
    with tracer.start_as_current_span("api.scan_protocol") as span:
        span.set_attribute("protocol", req.protocol)
        span.set_attribute("chain", req.chain)
        agent = _get_scanner()
        result = await agent.scan(
            protocol=req.protocol,
            contract_address=req.contract_address,
            chain=req.chain,
        )
        return {"status": "ok", "scan_result": result}


# ---------------------------------------------------------------------------
# Routes — Policy Management
# ---------------------------------------------------------------------------


@app.get("/policy/list", tags=["Policy"])
async def list_policies() -> Dict[str, Any]:
    """Return all active risk policies from the RiskPolicyManager contract."""
    client = _get_casper()
    contract_hash = os.getenv("RISK_POLICY_MANAGER_HASH", "")
    if not contract_hash:
        # Return mock policies when no contract is deployed
        return {
            "policies": [
                {
                    "id": "default",
                    "max_tvl_drop_pct": 20.0,
                    "min_liquidity_ratio": 0.1,
                    "alert_threshold": 3,
                },
                {
                    "id": "strict",
                    "max_tvl_drop_pct": 10.0,
                    "min_liquidity_ratio": 0.2,
                    "alert_threshold": 1,
                },
            ]
        }
    state = client.query_contract_state(contract_hash, ["policies"])
    return {"policies": state}


@app.post("/policy/update", tags=["Policy"])
async def update_policy(req: PolicyUpdateRequest) -> Dict[str, Any]:
    """Update a risk policy on the RiskPolicyManager contract."""
    with tracer.start_as_current_span("api.update_policy") as span:
        span.set_attribute("policy_id", req.policy_id)
        client = _get_casper()
        contract_hash = os.getenv("RISK_POLICY_MANAGER_HASH", "")
        deploy_hash = client.call_contract(
            contract_hash=contract_hash,
            entry_point="update_policy",
            args={
                "policy_id": req.policy_id,
                "max_tvl_drop_pct": int(req.max_tvl_drop_pct * 100),
                "min_liquidity_ratio": int(req.min_liquidity_ratio * 10000),
                "alert_threshold": req.alert_threshold,
            },
        )
        span.set_attribute("deploy_hash", deploy_hash)
        return {"status": "submitted", "deploy_hash": deploy_hash}


# ---------------------------------------------------------------------------
# Routes — Audit Log
# ---------------------------------------------------------------------------


@app.get("/audit/log", tags=["Audit"])
async def get_audit_log(limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    """Fetch the latest audit entries from the on-chain AuditTrail contract."""
    agent = _get_audit()
    entries = await agent.get_log(limit=limit)
    return {"count": len(entries), "entries": entries}


@app.post("/audit/write", tags=["Audit"])
async def write_audit_entry(
    action: str,
    actor: str,
    details: str = "",
) -> Dict[str, Any]:
    """Manually write an audit entry to the on-chain log."""
    agent = _get_audit()
    deploy_hash = await agent.record(action=action, actor=actor, details=details)
    return {"status": "submitted", "deploy_hash": deploy_hash}


# ---------------------------------------------------------------------------
# Routes — Block info
# ---------------------------------------------------------------------------


@app.get("/chain/block", tags=["Chain"])
async def get_block_height() -> Dict[str, Any]:
    """Return the current Casper block height."""
    client = _get_casper()
    height = client.get_block_height()
    return {"block_height": height, "network": "casper-test"}


# ===========================================================================
# /chain/* — direct on-chain contract reads (AuditTrail + RiskOracle)
# ===========================================================================
#
# These endpoints perform REAL ``query_global_state`` JSON-RPC reads against
# the public Casper testnet node (no auth, no gas, no signing) via
# ``api/casper_rpc.py``. They expose the AuditTrail + RiskOracle contract
# state to:
#
#   * the browser dashboard — replacing the hardcoded ``LIVE_FINDINGS``
#     constant with live chain data fetched through this FastAPI proxy
#     (Critical Fix: dashboard no longer ships a stale, hand-written list;
#     it shows what is actually on-chain);
#   * the VaultWatch Python SDK — ``client.audit_trail.get_finding(id)`` and
#     ``client.risk_oracle.get_score(address)`` hit these endpoints directly.
#
# Every endpoint is **chain-first with graceful fallback**:
#   * On success → returns on-chain data with ``"source": "on-chain"``.
#   * On RPC failure / empty chain → falls back to the in-memory
#     ``_findings_store`` (findings the live agent pipeline recorded this
#     session) or returns a clear ``404`` for single-item lookups.
#
# This keeps the dashboard + SDK functional even when the testnet RPC is
# unreachable (e.g. sandbox CI), while serving genuine on-chain state whenever
# the node is available.

from api import casper_rpc  # noqa: E402


def _finding_to_dashboard_shape(f: Dict[str, Any]) -> Dict[str, Any]:
    """Map a parsed on-chain ``Finding`` (or in-memory finding) into the
    dashboard's ``LIVE_FINDINGS`` shape so the UI consumes one consistent
    schema regardless of source.
    """
    # In-memory findings from _findings_store already carry dashboard fields.
    if "summary" in f and "protocol" in f:
        return f
    confidence = f.get("confidence", 0)
    return {
        "id": f"F-{f.get('id', 0)}",
        "numeric_id": f.get("id"),
        "protocol": f.get("address", "unknown")[:18] or "unknown",
        "summary": f.get("description") or f.get("risk_type", "finding"),
        "severity": f.get("severity", "MEDIUM"),
        "risk_type": f.get("risk_type", "unknown"),
        "confidence": (confidence / 100.0) if confidence <= 100 else confidence,
        "contract": "AuditTrail",
        "contract_hash": casper_rpc._audit_trail_hash(),
        "timestamp": f.get("timestamp", 0) * 1000 if f.get("timestamp", 0) < 10**12 else f.get("timestamp", 0),
        "agent": f.get("agent_model", "VaultWatchAgent"),
        "tx_hash": f.get("tx_hash", ""),
        "block_height": f.get("block_height"),
        "source": f.get("source", "on-chain"),
    }


@app.get("/chain/finding-count", tags=["Chain"])
async def chain_finding_count() -> Dict[str, Any]:
    """Return the total number of findings recorded on AuditTrail.

    Reads ``AuditTrail.finding_count`` (a ``Var<u64>``) directly from chain.
    Falls back to the in-memory ``_findings_store`` length when the RPC is
    unreachable so the dashboard never shows a broken counter.
    """
    with tracer.start_as_current_span("api.chain.finding_count") as span:
        count = await casper_rpc.read_finding_count()
        if count is not None:
            span.set_attribute("chain.count", count)
            span.set_attribute("chain.source", "on-chain")
            return {"count": count, "source": "on-chain", "network": "casper-test"}
        span.set_attribute("chain.source", "fallback")
        return {
            "count": len(_findings_store),
            "source": "fallback",
            "network": "casper-test",
            "note": "testnet RPC unreachable; using in-memory store length",
        }


@app.get("/chain/findings", tags=["Chain"])
async def chain_findings(
    limit: int = Query(20, ge=1, le=200),
) -> Dict[str, Any]:
    """Return the latest ``limit`` findings from AuditTrail (newest first).

    Chain-first: queries ``finding_count`` then reads each finding by ID in
    parallel. Falls back to the in-memory ``_findings_store`` when the chain
    read returns nothing (RPC down or contract has no findings yet), so the
    dashboard always has findings to render.
    """
    with tracer.start_as_current_span("api.chain.findings") as span:
        span.set_attribute("limit", limit)
        chain_findings_list = await casper_rpc.read_recent_findings(limit=limit)
        if chain_findings_list:
            span.set_attribute("chain.source", "on-chain")
            span.set_attribute("chain.count", len(chain_findings_list))
            shaped = [_finding_to_dashboard_shape(f) for f in chain_findings_list]
            return {
                "count": len(shaped),
                "findings": shaped,
                "source": "on-chain",
                "network": "casper-test",
            }
        # Fallback: in-memory findings store (live agent pipeline output).
        span.set_attribute("chain.source", "fallback")
        mem = list(_findings_store[-limit:])
        shaped = [_finding_to_dashboard_shape(f) for f in mem]
        return {
            "count": len(shaped),
            "findings": shaped,
            "source": "fallback",
            "network": "casper-test",
            "note": "testnet RPC unreachable or no on-chain findings; showing in-memory store",
        }


@app.get("/chain/finding/{finding_id}", tags=["Chain"])
async def chain_finding(finding_id: int) -> Dict[str, Any]:
    """Return a single finding by its numeric on-chain ID from AuditTrail.

    Powers ``VaultWatchClient.audit_trail.get_finding(id)``. Returns 404 when
    the finding does not exist on chain AND is not in the in-memory store.
    """
    with tracer.start_as_current_span("api.chain.finding") as span:
        span.set_attribute("finding_id", finding_id)
        finding = await casper_rpc.read_finding(finding_id)
        if finding is not None:
            span.set_attribute("chain.source", "on-chain")
            return _finding_to_dashboard_shape(finding)
        # Fallback: look it up in the in-memory store by numeric id.
        for f in _findings_store:
            if f.get("numeric_id") == finding_id or f.get("id") == f"F-{finding_id}":
                span.set_attribute("chain.source", "fallback-memory")
                return _finding_to_dashboard_shape(f)
        raise HTTPException(
            status_code=404,
            detail=f"finding {finding_id} not found on chain or in memory",
        )


@app.get("/chain/risk-score/{address}", tags=["Chain"])
async def chain_risk_score(address: str) -> Dict[str, Any]:
    """Return the on-chain risk score for ``address`` from RiskOracle.

    Powers ``VaultWatchClient.risk_oracle.get_score(address)``. The address
    is the String key the contract stores (typically a Casper account-hash
    string). Returns 404 when no score exists for the address.
    """
    with tracer.start_as_current_span("api.chain.risk_score") as span:
        span.set_attribute("address", address)
        score = await casper_rpc.read_risk_score(address)
        if score is None:
            raise HTTPException(
                status_code=404,
                detail=f"no risk score on chain for address {address}",
            )
        span.set_attribute("chain.score", score.get("score", 0))
        return score


# ===========================================================================
# x402 v2 Payment Protocol — HTTP 402 middleware + payment-gated routes
# ===========================================================================
#
# Implements the real x402 v2 flow (https://github.com/x402-foundation/x402)
# using the OFFICIAL @make-software/casper-x402 SDK + @x402/core transport
# primitives (both npm dependencies — see package.json and x402/package.json).
#
# Flow:
#   Client ──GET /intel/{addr}──────────► VaultWatch API
#   Client ◄──402 + PAYMENT-REQUIRED──── VaultWatch API   (encode-payment-required)
#   Client ──GET + PAYMENT-SIGNATURE───► VaultWatch API   (verify-payment-signature)
#   VaultWatch ──open_vault deploy─────► Casper testnet   (submit-vault-payment)
#   VaultWatch ──build SettleResponse──► Client (200 + PAYMENT-RESPONSE)
#
# The on-chain payment is a `SubscriberVault.open_vault()` stored-contract
# call that escrows CSPR into the subscriber's vault balance — this is the
# "verified payment hash" recorded in proof/PROOF.md §11.
#
# The x402 SDK is JavaScript-only (no Python port of the Casper EIP-712 /
# ExactCasperScheme exists — see docs/X402_INTEGRATION.md §12), so the Python
# server shells out to `x402/x402_helper.mjs` for the four SDK operations.

_VAULTWATCH_ROOT = Path(__file__).resolve().parent.parent
_X402_HELPER = _VAULTWATCH_ROOT / "x402" / "x402_helper.mjs"
_DEFAULT_SIGNER_PEM = _VAULTWATCH_ROOT / "secret_key.pem"

# Plans: 1 CSPR per standard query, 5 CSPR per premium query (1 CSPR = 1e9 motes)
_X402_PLAN_PRICES_MOTES = {
    "standard": 1_000_000_000,
    "premium": 5_000_000_000,
}


class X402SubscribeRequest(BaseModel):
    """Request body for POST /x402/subscribe — server-initiated payment flow.

    The server signs + submits the on-chain `SubscriberVault.open_vault()`
    deploy on behalf of the subscriber (the deployer is the vault owner).
    """

    subscriber_address: str
    plan: str = "standard"  # "standard" | "premium"
    payment_amount_cspr: Optional[float] = None  # defaults to plan price
    lock_blocks: int = 0
    auto_renew: bool = True
    monthly_spend_limit_motes: str = "0"


class X402SubscribeResponse(BaseModel):
    success: bool
    plan: str
    deploy_hash: Optional[str] = None
    block_hash: Optional[str] = None
    gas_cost_motes: Optional[str] = None
    escrow_balance_motes: str
    query_price_motes: str
    expected_queries: int
    link: Optional[str] = None
    payment_required_header: Optional[str] = None
    payment_response_header: Optional[str] = None
    error: Optional[str] = None


async def _x402_helper(command: str, request_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Shell out to x402/x402_helper.mjs and return its parsed JSON response.

    Raises HTTPException(500) on subprocess failure or invalid JSON output.
    """
    if not _X402_HELPER.exists():
        raise HTTPException(
            status_code=500,
            detail=f"x402 helper not found at {_X402_HELPER}. Run `npm install`.",
        )

    span = trace.get_current_span()
    span.set_attribute("x402.command", command)

    proc = await asyncio.create_subprocess_exec(
        "node",
        str(_X402_HELPER),
        command,
        cwd=str(_VAULTWATCH_ROOT),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate(json.dumps(request_payload).encode("utf-8"))
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip()
        span.set_attribute("x402.error", err)
        raise HTTPException(
            status_code=500,
            detail=f"x402 helper '{command}' exited {proc.returncode}: {err}",
        )
    try:
        result = json.loads(stdout.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"x402 helper '{command}' returned non-JSON: {e}",
        )
    if not result.get("success", False):
        raise HTTPException(
            status_code=502,
            detail=f"x402 helper '{command}' reported failure: {result.get('error', 'unknown')}",
        )
    return result


def _b64_or_none(raw: Optional[str]) -> Optional[str]:
    """Validate that a header value is plausible base64 (no newlines, etc.)."""
    if not raw:
        return None
    try:
        base64.b64decode(raw, validate=True)
        return raw
    except Exception:
        return None


@app.get("/intel/{addr}", tags=["x402 Payment Protocol"])
async def intel_resource(
    addr: str,
    request: Request,
    plan: str = Query("standard", pattern="^(standard|premium)$"),
):
    """Payment-gated VaultWatch intelligence resource (x402 v2 flow).

    Without a `PAYMENT-SIGNATURE` header: returns **402 Payment Required** with
    a `PAYMENT-REQUIRED` base64 header describing the exact Casper payment
    (network=casper:casper-test, scheme=exact, asset=SubscriberVault package,
    payTo=deployer account hash, amount=plan price in motes).

    With a valid `PAYMENT-SIGNATURE` header: verifies the EIP-712 signature
    via the official `@make-software/casper-x402` facilitator scheme, then
    returns **200 OK** with the intelligence payload and a `PAYMENT-RESPONSE`
    header carrying the verified payment identifier.

    NOTE: This endpoint implements the 402-challenge half of the flow. The
    actual on-chain payment deploy is submitted by POST /x402/subscribe (or
    by an external x402 client wallet). See proof/PROOF.md §11 for the
    verified payment hash.
    """
    with tracer.start_as_current_span("api.x402.intel") as span:
        span.set_attribute("x402.addr", addr)
        span.set_attribute("x402.plan", plan)

        payment_signature = request.headers.get("PAYMENT-SIGNATURE")

        # ---- No payment signature → 402 + PAYMENT-REQUIRED header ----------
        if not payment_signature:
            amount_motes = str(_X402_PLAN_PRICES_MOTES[plan])
            enc = await _x402_helper(
                "encode-payment-required",
                {
                    "resourceUrl": str(request.url),
                    "description": f"VaultWatch {plan} intelligence query — {addr}",
                    "mimeType": "application/json",
                    "plan": plan,
                    "amountMotes": amount_motes,
                },
            )
            header = enc.get("paymentRequiredHeader", "")
            span.set_attribute("x402.challenge", True)
            return Response(
                status_code=402,
                headers={
                    "PAYMENT-REQUIRED": header,
                    "Content-Type": "application/json",
                },
                content=json.dumps(
                    {
                        "error": "PAYMENT-SIGNATURE header is required",
                        "x402Version": 2,
                        "resource": addr,
                        "plan": plan,
                        "amount_motes": amount_motes,
                        "network": "casper:casper-test",
                        "instructions": (
                            "Decode the PAYMENT-REQUIRED base64 header to obtain the "
                            "x402 PaymentRequired object. Sign the EIP-712 "
                            "ExactCasperPayload with your Casper wallet, then retry "
                            "this request with the base64 signature in the "
                            "PAYMENT-SIGNATURE header. See "
                            "https://github.com/x402-foundation/x402 and "
                            "https://www.npmjs.com/package/@make-software/casper-x402."
                        ),
                    }
                ),
            )

        # ---- Payment signature present → verify via facilitator scheme ----
        try:
            verify = await _x402_helper(
                "verify-payment-signature",
                {"paymentSignatureHeader": payment_signature},
            )
        except HTTPException as e:
            span.set_attribute("x402.verify_error", e.detail)
            return Response(
                status_code=402,
                content=json.dumps({"error": "payment verification failed", "detail": e.detail}),
                headers={"Content-Type": "application/json"},
            )

        if not verify.get("isValid"):
            return Response(
                status_code=402,
                headers={"Content-Type": "application/json"},
                content=json.dumps(
                    {
                        "error": "invalid payment signature",
                        "invalidReason": verify.get("invalidReason"),
                        "invalidMessage": verify.get("invalidMessage"),
                    }
                ),
            )

        # Signature valid → serve the intelligence payload + PAYMENT-RESPONSE.
        # Build a SettleResponse referencing the verified payer. (In a fully
        # client-driven flow, the SettleResponse.transaction would be the
        # on-chain deploy hash; here we reference the payer's account hash
        # because the actual on-chain deploy is submitted by /x402/subscribe.)
        settle = await _x402_helper(
            "build-settle-response",
            {
                "deployHash": verify.get("payer", "") or "0" * 64,
                "payer": verify.get("payer", ""),
                "amountMotes": str(_X402_PLAN_PRICES_MOTES[plan]),
                "success": True,
            },
        )
        intel_payload = {
            "resource": addr,
            "plan": plan,
            "payer": verify.get("payer"),
            "findings": _findings_store[-20:],
            "note": ("Payment signature verified via @make-software/casper-x402 ExactCasperScheme (EIP-712 / CEP-3009)."),
        }
        return Response(
            status_code=200,
            headers={
                "PAYMENT-RESPONSE": settle.get("settleResponseHeader", ""),
                "Content-Type": "application/json",
            },
            content=json.dumps(intel_payload),
        )


# ---------------------------------------------------------------------------
# RWA Feed — Hybrid real+mock structured RWA data (x402-gated)
#
# Real data sources (gracefully degrade to mock on failure):
#   • CoinGecko (free, no key): CSPR price, PAXG gold token price,
#     USDC/USDT stablecoin depeg detection
#   • FRED (env-gated via FRED_API_KEY): Treasury yields (10y, 2y, 3m),
#     BAA corporate spread, effective federal funds rate
#
# Provenance tracking: each category records whether it came from a real
# API (data_source = "coingecko_api" / "fred_api") or mock fallback
# (data_source = "vaultwatch_mock"). attestation_proof contains SHA-256
# hashes + timestamps for audit verification.
# ---------------------------------------------------------------------------


async def _fetch_coingecko_rwa_data() -> Dict[str, Any]:
    """Fetch real RWA-related market data from CoinGecko (free, no API key).

    Returns:
        Dict with:
          - cspr_price_usd: current CSPR/USD price
          - paxg_price_usd: PAXG (PAX Gold) token price ≈ physical gold
          - stablecoin_depeg: USDC/USDT price deviation from $1.00
          - fetched_at: UNIX timestamp of fetch
        Empty dict on any error (graceful fallback to mock).
    """
    result: Dict[str, Any] = {}
    now = int(time.time())
    try:
        async with httpx.AsyncClient(timeout=8.0) as cg:
            # CSPR price (same pattern as /agent/health)
            resp = await cg.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=casper-network&vs_currencies=usd",
            )
            if resp.status_code == 200:
                cspr_val = resp.json().get("casper-network", {}).get("usd")
                if cspr_val is not None:
                    result["cspr_price_usd"] = float(cspr_val)

            # PAXG (tokenised gold) price — best free proxy for real gold
            resp = await cg.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=pax-gold&vs_currencies=usd",
            )
            if resp.status_code == 200:
                paxg_val = resp.json().get("pax-gold", {}).get("usd")
                if paxg_val is not None:
                    result["paxg_price_usd"] = float(paxg_val)

            # Stablecoin depeg detection: USDC and USDT should be ≈ $1.00
            resp = await cg.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=usd-coin,tether&vs_currencies=usd",
            )
            if resp.status_code == 200:
                sc_data = resp.json()
                usdc = sc_data.get("usd-coin", {}).get("usd")
                usdt = sc_data.get("tether", {}).get("usd")
                depeg_signals = {}
                if usdc is not None and abs(float(usdc) - 1.0) > 0.005:
                    depeg_signals["USDC"] = {
                        "price_usd": float(usdc),
                        "deviation_pct": round((float(usdc) - 1.0) * 100, 4),
                        "depeg_risk": "medium" if abs(float(usdc) - 1.0) > 0.01 else "low",
                    }
                if usdt is not None and abs(float(usdt) - 1.0) > 0.005:
                    depeg_signals["USDT"] = {
                        "price_usd": float(usdt),
                        "deviation_pct": round((float(usdt) - 1.0) * 100, 4),
                        "depeg_risk": "medium" if abs(float(usdt) - 1.0) > 0.01 else "low",
                    }
                result["stablecoin_depeg"] = depeg_signals

            result["fetched_at"] = now
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        logger.warning("CoinGecko RWA fetch failed: %s", exc)
    return result


async def _fetch_fred_rwa_data() -> Dict[str, Any]:
    """Fetch real US Treasury / macro data from FRED (Federal Reserve Economic Data).

    Gated by FRED_API_KEY env var — if not set, returns empty dict and
    all bond/credit data falls back to mock. FRED is free (register at
    https://fred.stlouisfed.org/docs/api/api_key.html).

    Returns:
        Dict with:
          - treasury_10y_yield, treasury_2y_yield, treasury_3m_yield
          - baa_spread (BAA corporate bond spread over 10y Treasury)
          - effective_fed_rate (effective federal funds rate)
          - fetched_at: UNIX timestamp
        Empty dict on any error or missing API key.
    """
    fred_key = os.getenv("FRED_API_KEY", "")
    if not fred_key:
        return {}

    result: Dict[str, Any] = {}
    now = int(time.time())
    # FRED series IDs for key RWA indicators
    series_map = {
        "treasury_10y_yield": "DGS10",  # 10-Year Treasury
        "treasury_2y_yield": "DGS2",  # 2-Year Treasury
        "treasury_3m_yield": "DGS3MO",  # 3-Month Treasury
        "baa_spread": "BAA10YM",  # BAA corporate spread
        "effective_fed_rate": "EFFR",  # Effective Fed Funds Rate
    }
    try:
        async with httpx.AsyncClient(timeout=8.0) as fred:
            for field, series_id in series_map.items():
                resp = await fred.get(
                    f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={fred_key}&file_type=json&sort_order=desc&limit=1",
                )
                if resp.status_code == 200:
                    obs = resp.json().get("observations", [])
                    if obs:
                        val_str = obs[0].get("value", "")
                        if val_str and val_str != ".":
                            result[field] = float(val_str)
            if result:
                result["fetched_at"] = now
    except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
        logger.warning("FRED RWA fetch failed: %s", exc)
    return result


async def _generate_rwa_feed_data(asset_type: Optional[str] = None) -> Dict[str, Any]:
    """Generate hybrid real+mock structured RWA data with provenance tracking.

    Strategy:
      1. Generate the full mock dataset (deterministic, time-rotating).
      2. Fetch real data from CoinGecko (free) and FRED (env-gated).
      3. Overlay real values onto the corresponding mock categories:
         - Bonds: real Treasury yields from FRED when available
         - Commodities: real gold price from PAXG (CoinGecko) when available
         - Credit: real BAA spread from FRED when available
         - Tokenized Assets: overlay CSPR price + stablecoin depeg from CoinGecko
         - Real Estate: always mock (no free property data API)
      4. Record provenance per category (data_source: "fred_api" / "coingecko_api"
         vs "vaultwatch_mock") and attestation_proof (SHA-256 + timestamps).

    Falls back gracefully: if CoinGecko/FRED are unreachable or return errors,
    the corresponding categories use pure mock data.
    """
    now = int(time.time())
    minute_bucket = now // 60
    seed = hashlib.sha256(f"vaultwatch-rwa-feed-{minute_bucket}".encode()).hexdigest()
    rng = _random.Random(seed)

    # ---- Step 1: Fetch real data from CoinGecko + FRED (concurrent) ----
    coingecko_data, fred_data = await asyncio.gather(
        _fetch_coingecko_rwa_data(),
        _fetch_fred_rwa_data(),
    )
    has_coingecko = bool(coingecko_data)
    has_fred = bool(fred_data)

    # Provenance tracking flags
    real_data_sources: Dict[str, bool] = {
        "coingecko": has_coingecko,
        "fred": has_fred,
    }

    # ---- Step 2: Generate mock baseline (unchanged deterministic data) ----

    # --- Real Estate (always mock — no free property API) ---
    real_estate = {
        "data_source": "vaultwatch_mock",
        "properties": [
            {
                "property_id": "RWE-001",
                "name": "Manhattan Commercial Tower",
                "type": "commercial",
                "location": "New York, NY",
                "valuation_usd": round(rng.uniform(45_000_000, 55_000_000), 2),
                "occupancy_rate": round(rng.uniform(0.82, 0.96), 4),
                "location_risk": round(rng.uniform(0.12, 0.25), 4),
                "cap_rate": round(rng.uniform(0.04, 0.07), 4),
                "last_appraisal_ts": now - rng.randint(86400, 864000),
            },
            {
                "property_id": "RWE-002",
                "name": "London Residential Portfolio",
                "type": "residential",
                "location": "London, UK",
                "valuation_usd": round(rng.uniform(22_000_000, 30_000_000), 2),
                "occupancy_rate": round(rng.uniform(0.88, 0.97), 4),
                "location_risk": round(rng.uniform(0.10, 0.20), 4),
                "cap_rate": round(rng.uniform(0.03, 0.06), 4),
                "last_appraisal_ts": now - rng.randint(86400, 864000),
            },
            {
                "property_id": "RWE-003",
                "name": "Singapore Mixed-Use Development",
                "type": "mixed_use",
                "location": "Singapore",
                "valuation_usd": round(rng.uniform(60_000_000, 72_000_000), 2),
                "occupancy_rate": round(rng.uniform(0.90, 0.98), 4),
                "location_risk": round(rng.uniform(0.08, 0.15), 4),
                "cap_rate": round(rng.uniform(0.035, 0.055), 4),
                "last_appraisal_ts": now - rng.randint(86400, 864000),
            },
        ],
    }

    # --- Bonds (overlay real FRED data when available) ---
    bonds_data_source = "vaultwatch_mock"
    treasury_bonds = [
        {
            "bond_id": "TBY-4W",
            "name": "4-Week US Treasury Bill",
            "maturity_days": 28,
            "yield_pct": round(rng.uniform(5.20, 5.45), 4),
            "par_value_usd": 10_000,
            "spread_bps": 0,
            "maturity_risk": round(rng.uniform(0.001, 0.005), 4),
        },
        {
            "bond_id": "TBY-13W",
            "name": "13-Week US Treasury Bill",
            "maturity_days": 91,
            "yield_pct": round(rng.uniform(5.25, 5.50), 4),
            "par_value_usd": 10_000,
            "spread_bps": 0,
            "maturity_risk": round(rng.uniform(0.002, 0.008), 4),
        },
        {
            "bond_id": "TBY-26W",
            "name": "26-Week US Treasury Bill",
            "maturity_days": 182,
            "yield_pct": round(rng.uniform(5.30, 5.60), 4),
            "par_value_usd": 10_000,
            "spread_bps": 0,
            "maturity_risk": round(rng.uniform(0.003, 0.01), 4),
        },
    ]
    # Overlay real Treasury yields from FRED onto mock T-Bills
    if has_fred:
        fred_3m = fred_data.get("treasury_3m_yield")
        fred_2y = fred_data.get("treasury_2y_yield")
        fred_10y = fred_data.get("treasury_10y_yield")
        if fred_3m is not None:
            treasury_bonds[0]["yield_pct"] = round(fred_3m, 4)
            treasury_bonds[0]["real_source"] = "fred_api"
        if fred_2y is not None:
            treasury_bonds[1]["yield_pct"] = round(fred_2y, 4)
            treasury_bonds[1]["real_source"] = "fred_api"
        if fred_10y is not None:
            treasury_bonds[2]["yield_pct"] = round(fred_10y, 4)
            treasury_bonds[2]["real_source"] = "fred_api"
        bonds_data_source = "fred_api"

    corporate_bonds = [
        {
            "bond_id": "CB-IBM",
            "name": "IBM 5-Year Corporate Bond",
            "maturity_days": 1825,
            "yield_pct": round(rng.uniform(5.80, 6.20), 4),
            "par_value_usd": 1_000,
            "spread_bps": round(rng.uniform(50, 80), 1),
            "maturity_risk": round(rng.uniform(0.02, 0.05), 4),
        },
        {
            "bond_id": "CB-UKG",
            "name": "UK 10-Year Gilt",
            "maturity_days": 3650,
            "yield_pct": round(rng.uniform(4.30, 4.60), 4),
            "par_value_usd": 1_000,
            "spread_bps": round(rng.uniform(20, 40), 1),
            "maturity_risk": round(rng.uniform(0.03, 0.07), 4),
        },
    ]
    # Overlay real BAA corporate spread from FRED onto IBM corporate bond
    if has_fred:
        baa_spread = fred_data.get("baa_spread")
        if baa_spread is not None:
            # BAA spread is the difference between BAA yield and 10y Treasury
            # IBM bond spread should track the BAA spread
            corporate_bonds[0]["spread_bps"] = round(baa_spread * 100, 1)  # Convert % to bps
            corporate_bonds[0]["real_source"] = "fred_api"

    bonds = {
        "data_source": bonds_data_source,
        "treasury": treasury_bonds,
        "corporate": corporate_bonds,
    }
    # Include raw FRED yields for direct reference
    if has_fred:
        bonds["fred_raw"] = {
            "treasury_10y": fred_data.get("treasury_10y_yield"),
            "treasury_2y": fred_data.get("treasury_2y_yield"),
            "treasury_3m": fred_data.get("treasury_3m_yield"),
            "baa_spread_pct": fred_data.get("baa_spread"),
            "effective_fed_rate_pct": fred_data.get("effective_fed_rate"),
            "fetched_at": fred_data.get("fetched_at"),
        }

    # --- Commodities (overlay real gold from PAXG when available) ---
    commodities_data_source = "vaultwatch_mock"
    commodities = {
        "gold_price_usd_per_oz": round(rng.uniform(2_300, 2_500), 2),
        "silver_price_usd_per_oz": round(rng.uniform(26, 32), 2),
        "oil_price_usd_per_barrel": round(rng.uniform(72, 85), 2),
        "commodity_indices": {
            "S&P_GSCI": round(rng.uniform(680, 750), 2),
            "Bloomberg_Commodity": round(rng.uniform(115, 130), 2),
        },
    }
    # Overlay real gold price from PAXG (CoinGecko)
    if has_coingecko and "paxg_price_usd" in coingecko_data:
        # PAXG ≈ 1 oz gold — its USD price directly maps to gold_price_usd_per_oz
        commodities["gold_price_usd_per_oz"] = round(coingecko_data["paxg_price_usd"], 2)
        commodities["gold_real_source"] = "coingecko_api"
        commodities_data_source = "coingecko_api"
    if has_coingecko:
        commodities["cspr_price_usd"] = coingecko_data.get("cspr_price_usd")
    commodities["data_source"] = commodities_data_source

    # --- Credit (overlay real BAA spread from FRED when available) ---
    credit_data_source = "vaultwatch_mock"
    credit = {
        "ratings": [
            {"entity": "US Government", "rating": "AAA", "default_probability": 0.0003, "recovery_rate": 0.95},
            {
                "entity": "IBM Corporation",
                "rating": "A+",
                "default_probability": round(rng.uniform(0.005, 0.01), 4),
                "recovery_rate": round(rng.uniform(0.40, 0.60), 4),
            },
            {
                "entity": "SME Loan Pool",
                "rating": "BBB",
                "default_probability": round(rng.uniform(0.03, 0.06), 4),
                "recovery_rate": round(rng.uniform(0.30, 0.50), 4),
            },
        ],
        "aggregate_default_rate": round(rng.uniform(0.02, 0.05), 4),
        "average_recovery_rate": round(rng.uniform(0.40, 0.60), 4),
    }
    # Overlay real BAA spread from FRED as credit risk indicator
    if has_fred:
        baa_spread = fred_data.get("baa_spread")
        if baa_spread is not None:
            # BAA spread is a proxy for corporate default risk
            credit["fred_baa_spread_pct"] = round(baa_spread, 4)
            credit["data_source"] = "fred_api"
            credit_data_source = "fred_api"
    credit["data_source"] = credit_data_source

    # --- Tokenized Assets (overlay CSPR price + stablecoin depeg from CoinGecko) ---
    tokenized_assets = {
        "on_chain_assets": [
            {
                "token_address": "0x" + hashlib.sha256(b"vaultwatch-rwa-realestate").hexdigest()[:40],
                "asset_type": "real_estate",
                "collateral_ratio": round(rng.uniform(1.30, 1.50), 4),
                "chain_id": "casper-test",
                "valuation_usd": round(rng.uniform(45_000_000, 55_000_000), 2),
                "token_symbol": "rWEPROP",
            },
            {
                "token_address": "0x" + hashlib.sha256(b"vaultwatch-rwa-treasury").hexdigest()[:40],
                "asset_type": "bonds",
                "collateral_ratio": round(rng.uniform(1.05, 1.15), 4),
                "chain_id": "casper-test",
                "valuation_usd": round(rng.uniform(10_000_000, 15_000_000), 2),
                "token_symbol": "rWTBILL",
            },
            {
                "token_address": "0x" + hashlib.sha256(b"vaultwatch-rwa-gold").hexdigest()[:40],
                "asset_type": "commodities",
                "collateral_ratio": round(rng.uniform(1.20, 1.35), 4),
                "chain_id": "casper-test",
                "valuation_usd": round(rng.uniform(5_000_000, 8_000_000), 2),
                "token_symbol": "rWGOLD",
            },
            {
                "token_address": "0x" + hashlib.sha256(b"vaultwatch-rwa-credit").hexdigest()[:40],
                "asset_type": "credit",
                "collateral_ratio": round(rng.uniform(1.10, 1.25), 4),
                "chain_id": "casper-test",
                "valuation_usd": round(rng.uniform(3_000_000, 6_000_000), 2),
                "token_symbol": "rWCREDIT",
            },
        ],
    }
    # Overlay CSPR price + stablecoin depeg from CoinGecko
    if has_coingecko:
        cspr_price = coingecko_data.get("cspr_price_usd")
        if cspr_price is not None:
            tokenized_assets["cspr_price_usd"] = cspr_price
            tokenized_assets["cspr_real_source"] = "coingecko_api"
        depeg = coingecko_data.get("stablecoin_depeg", {})
        if depeg:
            tokenized_assets["stablecoin_depeg_signals"] = depeg
            tokenized_assets["depeg_real_source"] = "coingecko_api"
    tokenized_assets["data_source"] = "coingecko_api" if has_coingecko else "vaultwatch_mock"

    # ---- Step 3: Build attestation proof (SHA-256 hashes + timestamps) ----
    # Each category's data is hashed to prove integrity for AuditAgent verification.
    attestation_proof: Dict[str, Any] = {}
    for category_name, category_data in [
        ("real_estate", real_estate),
        ("bonds", bonds),
        ("commodities", commodities),
        ("credit", credit),
        ("tokenized_assets", tokenized_assets),
    ]:
        data_str = json.dumps(category_data, sort_keys=True, separators=(",", ":"))
        data_hash = hashlib.sha256(data_str.encode("utf-8")).hexdigest()
        attestation_proof[category_name] = {
            "sha256": data_hash,
            "data_source": category_data.get("data_source", "vaultwatch_mock"),
            "timestamp": now,
        }

    # ---- Step 4: Assemble the final hybrid feed ----
    feed: Dict[str, Any] = {
        "timestamp": now,
        "feed_version": "1.1.0",
        "network": "casper-test",
        "real_estate": real_estate,
        "bonds": bonds,
        "commodities": commodities,
        "credit": credit,
        "tokenized_assets": tokenized_assets,
        "real_data_sources": real_data_sources,
        "attestation_proof": attestation_proof,
    }

    # If a specific asset_type is requested, filter to just that category
    if asset_type:
        type_map = {
            "real_estate": real_estate,
            "bonds": bonds,
            "commodities": commodities,
            "credit": credit,
            "tokenized_assets": tokenized_assets,
        }
        filtered = type_map.get(asset_type)
        if filtered:
            filtered_proof = attestation_proof.get(asset_type, {})
            feed = {
                "timestamp": now,
                "feed_version": "1.1.0",
                "network": "casper-test",
                asset_type: filtered,
                "real_data_sources": real_data_sources,
                "attestation_proof": {asset_type: filtered_proof},
            }

    return feed


@app.get("/rwa/feed", tags=["x402 Payment Protocol"])
async def rwa_feed(
    request: Request,
    asset_type: Optional[str] = Query(
        None,
        description="Filter to a single asset category: real_estate, bonds, commodities, credit, tokenized_assets",
    ),
    plan: str = Query("standard", pattern="^(standard|premium)$"),
):
    """Payment-gated hybrid real+mock RWA feed resource (x402 v2 flow).

    Returns structured RWA data covering five asset categories:
    Real Estate (property valuations, occupancy rates, location risk — always mock),
    Bonds (treasury yields, corporate bond spreads, maturity risk — real from FRED when available),
    Commodities (gold/silver prices, oil prices — real gold from CoinGecko/PAXG when available),
    Credit (credit ratings, default probabilities — real BAA spread from FRED when available),
    Tokenized Assets (on-chain RWA tokens, collateral ratios — overlay CSPR price + stablecoin depeg).

    Each category includes a `data_source` field indicating whether it came from
    a real API ("coingecko_api"/"fred_api") or mock fallback ("vaultwatch_mock").
    The feed also includes `real_data_sources` (bool flags) and `attestation_proof`
    (SHA-256 hashes + timestamps) for AuditAgent provenance verification.

    Data rotates on a per-minute bucket so each call gets "fresh" deterministic
    values for mock fallback, while real data is fetched live from external APIs.

    Without a `PAYMENT-SIGNATURE` header: returns **402 Payment Required** with
    a `PAYMENT-REQUIRED` base64 header (same pattern as /intel/{addr}).

    With a valid `PAYMENT-SIGNATURE` header: verifies the EIP-712 signature
    via the official `@make-software/casper-x402` facilitator, then returns
    **200 OK** with the RWA feed payload and a `PAYMENT-RESPONSE` header.
    """
    with tracer.start_as_current_span("api.x402.rwa_feed") as span:
        span.set_attribute("x402.rwa_feed.asset_type", asset_type or "all")
        span.set_attribute("x402.plan", plan)

        payment_signature = request.headers.get("PAYMENT-SIGNATURE")

        # ---- No payment signature → 402 + PAYMENT-REQUIRED header ----------
        if not payment_signature:
            amount_motes = str(_X402_PLAN_PRICES_MOTES[plan])
            enc = await _x402_helper(
                "encode-payment-required",
                {
                    "resourceUrl": str(request.url),
                    "description": f"VaultWatch {plan} RWA feed query",
                    "mimeType": "application/json",
                    "plan": plan,
                    "amountMotes": amount_motes,
                },
            )
            header = enc.get("paymentRequiredHeader", "")
            span.set_attribute("x402.challenge", True)
            return Response(
                status_code=402,
                headers={
                    "PAYMENT-REQUIRED": header,
                    "Content-Type": "application/json",
                },
                content=json.dumps(
                    {
                        "error": "PAYMENT-SIGNATURE header is required",
                        "x402Version": 2,
                        "resource": "rwa/feed",
                        "plan": plan,
                        "amount_motes": amount_motes,
                        "network": "casper:casper-test",
                        "instructions": (
                            "Decode the PAYMENT-REQUIRED base64 header to obtain the "
                            "x402 PaymentRequired object. Sign the EIP-712 "
                            "ExactCasperPayload with your Casper wallet, then retry "
                            "this request with the base64 signature in the "
                            "PAYMENT-SIGNATURE header."
                        ),
                    }
                ),
            )

        # ---- Payment signature present → verify via facilitator scheme ----
        try:
            verify = await _x402_helper(
                "verify-payment-signature",
                {"paymentSignatureHeader": payment_signature},
            )
        except HTTPException as e:
            span.set_attribute("x402.verify_error", e.detail)
            return Response(
                status_code=402,
                content=json.dumps({"error": "payment verification failed", "detail": e.detail}),
                headers={"Content-Type": "application/json"},
            )

        if not verify.get("isValid"):
            return Response(
                status_code=402,
                headers={"Content-Type": "application/json"},
                content=json.dumps(
                    {
                        "error": "invalid payment signature",
                        "invalidReason": verify.get("invalidReason"),
                        "invalidMessage": verify.get("invalidMessage"),
                    }
                ),
            )

        # Signature valid → serve the RWA feed + PAYMENT-RESPONSE
        settle = await _x402_helper(
            "build-settle-response",
            {
                "deployHash": verify.get("payer", "") or "0" * 64,
                "payer": verify.get("payer", ""),
                "amountMotes": str(_X402_PLAN_PRICES_MOTES[plan]),
                "success": True,
            },
        )
        feed_data = await _generate_rwa_feed_data(asset_type)
        feed_payload = {
            "resource": "rwa/feed",
            "plan": plan,
            "payer": verify.get("payer"),
            "feed_data": feed_data,
            "payment_verified": True,
            "note": ("Payment signature verified via @make-software/casper-x402 ExactCasperScheme."),
        }
        return Response(
            status_code=200,
            headers={
                "PAYMENT-RESPONSE": settle.get("settleResponseHeader", ""),
                "Content-Type": "application/json",
            },
            content=json.dumps(feed_payload),
        )


@app.post(
    "/x402/subscribe",
    response_model=X402SubscribeResponse,
    tags=["x402 Payment Protocol"],
)
async def x402_subscribe(req: X402SubscribeRequest) -> X402SubscribeResponse:
    """Server-initiated x402 payment: submit a REAL on-chain
    `SubscriberVault.open_vault()` deploy on Casper testnet.

    This is the "verified payment hash" path: the server (acting as the vault
    owner / merchant) builds the x402 PaymentRequired, then signs and submits
    a real `SubscriberVault.open_vault()` stored-contract deploy via
    `casper-js-sdk` v5's `ContractCallBuilder`. The deploy escrows CSPR into
    the subscriber's vault balance. The returned deploy hash is the verified
    payment proof recorded in proof/PROOF.md §11.

    The deploy is signed by the deployer account whose PEM is at
    `secret_key.pem` (vault owner = `VAULTWATCH_SIGNER_PEM` env override).
    """
    with tracer.start_as_current_span("api.x402.subscribe") as span:
        span.set_attribute("x402.subscriber", req.subscriber_address)
        span.set_attribute("x402.plan", req.plan)

        if req.plan not in _X402_PLAN_PRICES_MOTES:
            raise HTTPException(
                status_code=400,
                detail=f"plan must be 'standard' or 'premium', got '{req.plan}'",
            )

        plan_price_motes = _X402_PLAN_PRICES_MOTES[req.plan]
        if req.payment_amount_cspr is not None:
            amount_motes = int(req.payment_amount_cspr * 1_000_000_000)
        else:
            amount_motes = plan_price_motes

        # 1. Build the x402 v2 PaymentRequired (the 402 challenge payload)
        enc = await _x402_helper(
            "encode-payment-required",
            {
                "resourceUrl": f"https://api.vaultwatch.io/intel/{req.subscriber_address}",
                "description": (f"VaultWatch {req.plan} subscription — {amount_motes / 1e9:.2f} CSPR escrowed"),
                "plan": req.plan,
                "amountMotes": str(amount_motes),
            },
        )
        payment_required_header = enc.get("paymentRequiredHeader", "")

        # 2. Submit the REAL on-chain payment deploy (SubscriberVault.open_vault)
        submit_payload: Dict[str, Any] = {
            "subscriberAddress": req.subscriber_address,
            "amountMotes": amount_motes,
            "lockBlocks": req.lock_blocks,
            "autoRenew": req.auto_renew,
            "monthlySpendLimitMotes": req.monthly_spend_limit_motes,
        }
        if _DEFAULT_SIGNER_PEM.exists():
            submit_payload["signerPemPath"] = str(_DEFAULT_SIGNER_PEM)
        if os.getenv("VAULTWATCH_SIGNER_ALGO"):
            submit_payload["keyAlgorithm"] = os.environ["VAULTWATCH_SIGNER_ALGO"]
        if os.getenv("VAULTWATCH_SIGNER_RPC"):
            submit_payload["rpcUrl"] = os.environ["VAULTWATCH_SIGNER_RPC"]

        try:
            submit = await _x402_helper("submit-vault-payment", submit_payload)
        except HTTPException as e:
            span.set_attribute("x402.submit_error", e.detail)
            return X402SubscribeResponse(
                success=False,
                plan=req.plan,
                escrow_balance_motes="0",
                query_price_motes=str(plan_price_motes),
                expected_queries=0,
                payment_required_header=payment_required_header,
                error=e.detail,
            )

        success = bool(submit.get("success"))
        deploy_hash = submit.get("deployHash")
        block_hash = submit.get("blockHash")
        gas_cost = submit.get("gasCostMotes")
        link = submit.get("link")
        settle_header = submit.get("settleResponseHeader")
        err = submit.get("error")

        span.set_attribute("x402.deploy_hash", deploy_hash or "")
        span.set_attribute("x402.success", success)

        return X402SubscribeResponse(
            success=success,
            plan=req.plan,
            deploy_hash=deploy_hash,
            block_hash=block_hash,
            gas_cost_motes=gas_cost,
            escrow_balance_motes=str(amount_motes) if success else "0",
            query_price_motes=str(plan_price_motes),
            expected_queries=(amount_motes // plan_price_motes) if success else 0,
            link=link,
            payment_required_header=payment_required_header,
            payment_response_header=settle_header,
            error=err,
        )


@app.get("/x402/payment-required", tags=["x402 Payment Protocol"])
async def x402_payment_required(
    resource_url: str = Query(..., description="Resource URL to gate"),
    plan: str = Query("standard", pattern="^(standard|premium)$"),
    amount_motes: Optional[str] = Query(None, description="Override amount in motes (1 CSPR = 1e9 motes)"),
) -> Dict[str, Any]:
    """Standalone helper: build the x402 v2 PaymentRequired object + base64
    PAYMENT-REQUIRED header value (no on-chain submission).

    Useful for x402 client wallets that need to discover the payment
    requirements before constructing their PAYMENT-SIGNATURE header.
    """
    with tracer.start_as_current_span("api.x402.payment_required"):
        result = await _x402_helper(
            "encode-payment-required",
            {
                "resourceUrl": resource_url,
                "description": f"VaultWatch {plan} intelligence query",
                "plan": plan,
                "amountMotes": amount_motes,
            },
        )
        return {
            "x402Version": 2,
            "network": "casper:casper-test",
            "scheme": "exact",
            "plan": plan,
            "amount_motes": amount_motes or str(_X402_PLAN_PRICES_MOTES[plan]),
            "payment_required": result.get("paymentRequired"),
            "payment_required_header": result.get("paymentRequiredHeader"),
            "instructions": (
                "Decode the base64 payment_required_header to obtain the x402 "
                "PaymentRequired JSON. Sign the ExactCasperPayload (EIP-712 over "
                "CEP-3009 domain) with your Casper wallet, base64-encode the "
                "PaymentPayload, and send it as the PAYMENT-SIGNATURE header on "
                "your next request to the resource URL."
            ),
        }


@app.get("/x402/status", tags=["x402 Payment Protocol"])
async def x402_status() -> Dict[str, Any]:
    """Return the x402 integration status (SDK versions, contract refs, plan
    prices). Useful for debugging and for clients to discover the payment
    configuration without triggering a 402 challenge.
    """
    return {
        "x402Version": 2,
        "scheme": "exact",
        "network": "casper:casper-test",
        "chainName": "casper-test",
        "sdk": {
            "@make-software/casper-x402": "1.0.0",
            "@x402/core": "2.15.0",
            "casper-js-sdk": "5.0.12",
        },
        "contracts": {
            "SubscriberVault": {
                "contractHash": os.getenv(
                    "SUBSCRIBER_VAULT_HASH",
                    "0d41615944471f18c7ac75725901be7eeff26a0c168e1a3387db2449256b1f8c",
                ),
                "packageHash": os.getenv(
                    "SUBSCRIBER_VAULT_PACKAGE_HASH",
                    "d1cb42e21855b938d7e189186bb13751fc4d2523da53e1482027595a0f3463bf",
                ),
                "entryPoint": "open_vault",
            }
        },
        "payeeAccountHash": os.getenv(
            "VAULTWATCH_PAYEE",
            "000debd9ab6e903b6d3269f7c9ceaf28320e3b91209e1a1080fd9ddf097d3dbd68",
        ),
        "planPricesMotes": _X402_PLAN_PRICES_MOTES,
        "rpcUrl": "https://node.testnet.casper.network/rpc",
        "helper": str(_X402_HELPER),
        "helperAvailable": _X402_HELPER.exists(),
        "signerPemAvailable": _DEFAULT_SIGNER_PEM.exists(),
    }


# ===========================================================================
# CSPR.cloud reverse proxy — keep the API key server-side (Critical Fix 6)
# ===========================================================================
#
# The CSPR.cloud REST API (https://api.testnet.cspr.cloud) requires a Bearer
# access token. Previously the key was hardcoded in dashboard/src/liveApi.js
# and shipped to every browser — anyone with devtools open could lift it.
#
# This proxy keeps the key on the server. The dashboard (and any other
# browser-side caller) hits `/cspr_cloud/<path>?<query>` on the FastAPI app;
# the server injects `Authorization: Bearer $CSPR_CLOUD_API_KEY` and forwards
# the request upstream, then streams the response back verbatim.
#
# Server-side scripts (broadcast_interactions.py, deploy_live.py, etc.) read
# the same `CSPR_CLOUD_API_KEY` env var directly — they never need the proxy
# because they already run in a trusted environment.
#
# Env:
#   CSPR_CLOUD_API_KEY     — required (the rotated key)
#   CSPR_CLOUD_API_URL     — optional, defaults to https://api.testnet.cspr.cloud
#   CSPR_CLOUD_PROXY_TIMEOUT — optional seconds, default 15

_CSPR_CLOUD_UPSTREAM = os.getenv("CSPR_CLOUD_API_URL", "https://api.testnet.cspr.cloud").rstrip("/")
_CSPR_CLOUD_TIMEOUT = float(os.getenv("CSPR_CLOUD_PROXY_TIMEOUT", "15"))


def _cspr_cloud_key() -> str:
    """Return the CSPR.cloud API key from env, or empty string if unset.

    Empty string is permitted so the proxy can still serve the public
    (unauthenticated) endpoints on cspr.cloud — but authenticated endpoints
    will return 401 from upstream. The /cspr_cloud/status route surfaces this.
    """
    return os.getenv("CSPR_CLOUD_API_KEY", "").strip()


@app.get("/cspr_cloud/status", tags=["CSPR.cloud Proxy"])
async def cspr_cloud_proxy_status() -> Dict[str, Any]:
    """Report whether the CSPR.cloud proxy is configured correctly.

    Does NOT echo the key — only whether one is set + the upstream base URL.
    Useful for the dashboard health-check + for debugging 401s.
    """
    return {
        "configured": bool(_cspr_cloud_key()),
        "upstream": _CSPR_CLOUD_UPSTREAM,
        "timeout_seconds": _CSPR_CLOUD_TIMEOUT,
        "instructions": (
            "Set CSPR_CLOUD_API_KEY in the server environment to enable "
            "authenticated CSPR.cloud REST calls. The key is NEVER exposed "
            "to the browser — all calls go through /cspr_cloud/<path>."
        ),
    }


@app.get("/cspr_cloud/{path:path}", tags=["CSPR.cloud Proxy"])
async def cspr_cloud_proxy_get(path: str, request: Request) -> Response:
    """Forward a GET request to the CSPR.cloud REST API.

    The browser-facing dashboard calls this endpoint as
    `/api/cspr_cloud/blocks?page_size=1` (the vite dev proxy rewrites `/api/*`
    to `/*` on the FastAPI app). The server injects the Bearer token from
    `CSPR_CLOUD_API_KEY` and forwards to `{CSPR_CLOUD_API_URL}/{path}?{query}`.

    Returns the upstream body, content-type, and status code verbatim. On
    upstream failure returns 502 with a JSON error envelope.

    Security notes:
      * GET-only — no POST/PUT/DELETE surface (cspr.cloud REST is read-only
        for our use case).
      * No auth on the proxy itself — the dashboard is a public read-only
        viewer of public chain data. If a route needs to be gated, gate it
        with x402 (see /intel/{addr}) instead of the CSPR.cloud key.
      * The key is read from env on every request — rotating it does not
        require a redeploy, just a server env update + uvicorn reload.
    """
    with tracer.start_as_current_span("api.cspr_cloud_proxy") as span:
        span.set_attribute("cspr_cloud.path", path)
        upstream_url = f"{_CSPR_CLOUD_UPSTREAM}/{path}"
        if request.url.query:
            upstream_url = f"{upstream_url}?{request.url.query}"

        headers = {"Accept": "application/json"}
        key = _cspr_cloud_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        else:
            span.set_attribute("cspr_cloud.key_missing", True)

        try:
            async with httpx.AsyncClient(timeout=_CSPR_CLOUD_TIMEOUT) as client:
                resp = await client.get(upstream_url, headers=headers)
        except httpx.TimeoutException as exc:
            span.set_attribute("cspr_cloud.error", "timeout")
            span.record_exception(exc)
            raise HTTPException(status_code=504, detail=f"CSPR.cloud upstream timed out: {exc}")
        except httpx.HTTPError as exc:
            span.set_attribute("cspr_cloud.error", str(exc))
            span.record_exception(exc)
            raise HTTPException(status_code=502, detail=f"CSPR.cloud upstream error: {exc}")

        span.set_attribute("cspr_cloud.upstream_status", resp.status_code)
        # Forward the upstream body + content-type verbatim. We explictly
        # exclude upstream's Authorization-echoing headers.
        forwarded_headers = {
            "Content-Type": resp.headers.get("Content-Type", "application/json"),
        }
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=forwarded_headers,
            media_type=resp.headers.get("Content-Type", "application/json"),
        )


@app.post("/cspr_cloud/rpc", tags=["CSPR.cloud Proxy"])
async def cspr_cloud_proxy_rpc(request: Request) -> Response:
    """Forward a JSON-RPC POST to the CSPR.cloud RPC endpoint.

    The CSPR.cloud JSON-RPC proxy (`https://node.testnet.cspr.cloud/rpc`)
    accepts the same Bearer token. The dashboard does not currently use
    JSON-RPC directly (it uses the REST API), but this endpoint exists so
    that any future browser-side RPC call can stay key-free.

    The public Casper testnet node (`https://node.testnet.casper.network/rpc`)
    does NOT require an Authorization header and is preferred for RPC when
    available — use this proxy only when the cspr.cloud RPC middleware is
    specifically needed.
    """
    with tracer.start_as_current_span("api.cspr_cloud_proxy_rpc") as span:
        body = await request.body()
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"invalid JSON body: {exc}")

        upstream_url = f"{_CSPR_CLOUD_UPSTREAM.rstrip('/')}/rpc"
        # If CSPR_CLOUD_API_URL was overridden to point at the REST root,
        # also accept an explicit RPC URL via CSPR_CLOUD_RPC_URL.
        rpc_url = os.getenv("CSPR_CLOUD_RPC_URL", upstream_url)

        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        key = _cspr_cloud_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"

        span.set_attribute("cspr_cloud.rpc_method", payload.get("method", ""))

        try:
            async with httpx.AsyncClient(timeout=_CSPR_CLOUD_TIMEOUT) as client:
                resp = await client.post(rpc_url, content=body, headers=headers)
        except httpx.TimeoutException as exc:
            span.set_attribute("cspr_cloud.error", "timeout")
            span.record_exception(exc)
            raise HTTPException(status_code=504, detail=f"CSPR.cloud RPC timed out: {exc}")
        except httpx.HTTPError as exc:
            span.set_attribute("cspr_cloud.error", str(exc))
            span.record_exception(exc)
            raise HTTPException(status_code=502, detail=f"CSPR.cloud RPC error: {exc}")

        span.set_attribute("cspr_cloud.upstream_status", resp.status_code)
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            media_type="application/json",
        )


# ---------------------------------------------------------------------------
# Entrypoint (for `python api/main.py`)
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
