"""
VaultWatch — FastAPI REST API
Exposes all agent outputs, risk scores, RWA data, and audit logs via HTTP.
OTel middleware captures every request as a trace span.
"""

from __future__ import annotations

import os
import time
import logging
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Query
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
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
)
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
                "duration_ms": (s.end_time - s.start_time) / 1_000_000
                if s.end_time
                else None,
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

        result = await intel.analyze(
            req.query, protocol=req.protocol, extra_context=req.context
        )
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


# ---------------------------------------------------------------------------
# Entrypoint (for `python api/main.py`)
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
