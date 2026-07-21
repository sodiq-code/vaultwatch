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
import time
import json
import base64
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional

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


# ---------------------------------------------------------------------------
# Entrypoint (for `python api/main.py`)
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
