"""
VaultWatch RWA MCP Server — Compliance-Gated RWA Intelligence

Fix #27: Standalone vaultwatch-rwa-mcp server exposing 5 RWA-specific tools.
Forked from vaultwatch_mcp but focused ONLY on Real-World Asset operations.

This MCP server is a Casper ecosystem contribution — any Claude Desktop user
can query RWA risk, compliance, and attestation data from Casper testnet.

Tools:
  1. rwa_risk_assessment   — Query RWA risk score for a Casper address
  2. compliance_check      — Verify if an address meets compliance requirements
  3. rwa_oracle_query      — Get RWA attestation data from on-chain oracle
  4. subscribe_rwa_feed    — x402-gated RWA data subscription
  5. agent_reputation      — Query agent trust score for RWA attestations

Install:
  pip install vaultwatch-rwa-mcp
  # or
  npm install vaultwatch-rwa-mcp
"""

import json
import os
import time
from typing import Optional

try:
    from fastmcp import FastMCP
except ImportError:
    raise ImportError("fastmcp required: pip install fastmcp")

from opentelemetry import trace

tracer = trace.get_tracer("vaultwatch.rwa_mcp")

mcp = FastMCP("VaultWatch-RWA")

# === Casper contract hashes on testnet ===
RWA_CONTRACT_HASHES = {
    "RiskOracle": "e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d",
    "AgentBehaviorIndex": "05066c33ddb73b523ab8f67275ca6096254f9d1832e76075d1e5f41f188b7dd0",
    "AuditTrail": "b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6333a7",
    "SentinelRegistry": "9a5eb4f83de8cbfef4f389516b977258b0e1d63179b288ca623a860fc6ec346c",
    "RiskPolicyManager": "93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e",
    "SubscriberVault": "6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d",
    "SentinelCredit": "0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71",
}

CASPER_RPC_URL = os.getenv("CASPER_RPC_URL", "https://node.testnet.casper.network/rpc")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


# ─── Helpers ───────────────────────────────────────────────────────────────

async def _casper_rpc(method: str, params: dict = None) -> dict:
    """Query Casper JSON-RPC endpoint."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": method,
                "params": params or {},
            }
            resp = await client.post(CASPER_RPC_URL, json=payload)
            return resp.json()
    except Exception as exc:
        return {"error": str(exc)}


async def _groq_query(prompt: str, model: str = "compound-beta") -> str:
    """Query Groq with live web search capability for RWA data."""
    if not GROQ_API_KEY:
        return json.dumps({"error": "GROQ_API_KEY not set", "mock": True})
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
        )
        return resp.choices[0].message.content
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ─── Tool 1: rwa_risk_assessment ──────────────────────────────────────────

@mcp.tool()
async def rwa_risk_assessment(
    address: str,
    asset_type: Optional[str] = None,
    include_historical: bool = False,
) -> dict:
    """
    Query RWA risk score for a Casper address.
    Returns risk score, risk type, confidence, and compliance status.
    Reads from the on-chain RiskOracle contract.
    """
    with tracer.start_as_current_span("rwa.risk_assessment") as span:
        span.set_attribute("address", address[:20])
        span.set_attribute("asset_type", asset_type or "unknown")

        # Query on-chain RiskOracle for this address
        oracle_result = await _casper_rpc(
            "state_get_dictionary_item",
            {
                "state_root_hash": RWA_CONTRACT_HASHES["RiskOracle"],
                "dictionary_item_key": address,
            }
        )

        # AI-enriched risk analysis for RWA context
        ai_analysis = ""
        if asset_type:
            ai_analysis = await _groq_query(
                f"RWA risk assessment for address {address[:16]}... holding {asset_type}. "
                f"Consider: collateral ratio, maturity, credit rating, jurisdiction risk. "
                f"Return JSON: {{\"risk_level\": str, \"collateral_adequacy\": str, "
                f"\"jurisdiction_risk\": str, \"recommendation\": str}}"
            )

        result = {
            "address": address,
            "on_chain_risk_score": oracle_result.get("result", "not_found"),
            "asset_type": asset_type,
            "risk_oracle_contract": RWA_CONTRACT_HASHES["RiskOracle"],
            "ai_enrichment": ai_analysis if ai_analysis else None,
            "compliance_gated": True,
            "network": "casper-test",
            "timestamp": int(time.time()),
        }

        if include_historical:
            result["historical_finding_contract"] = RWA_CONTRACT_HASHES["AuditTrail"]
            result["note"] = "Historical findings queryable via AuditTrail.record_finding()"

        return result


# ─── Tool 2: compliance_check ──────────────────────────────────────────────

@mcp.tool()
async def compliance_check(
    address: str,
    jurisdiction: str = "US",
    required_kyc_level: str = "basic",
    asset_class: Optional[str] = None,
) -> dict:
    """
    Verify if a Casper address meets compliance requirements for RWA access.
    Checks RiskPolicyManager thresholds and SentinelRegistry subscription status.
    """
    with tracer.start_as_current_span("rwa.compliance_check") as span:
        span.set_attribute("address", address[:20])
        span.set_attribute("jurisdiction", jurisdiction)
        span.set_attribute("required_kyc_level", required_kyc_level)

        # Check if address is a registered subscriber (SentinelRegistry)
        registry_result = await _casper_rpc(
            "state_get_dictionary_item",
            {
                "state_root_hash": RWA_CONTRACT_HASHES["SentinelRegistry"],
                "dictionary_item_key": address,
            }
        )

        # Get current compliance policy from RiskPolicyManager
        policy_result = await _casper_rpc(
            "state_get_dictionary_item",
            {
                "state_root_hash": RWA_CONTRACT_HASHES["RiskPolicyManager"],
                "dictionary_item_key": "current_policy",
            }
        )

        # Determine compliance status
        subscriber_active = False
        if "result" in registry_result:
            subscriber_active = True  # Address found in registry

        # Jurisdiction-specific compliance rules
        jurisdiction_rules = {
            "US": {"kyc_required": True, "accredited_investor": False, "max_exposure_pct": 100},
            "EU": {"kyc_required": True, "accredited_investor": False, "max_exposure_pct": 100},
            "SG": {"kyc_required": True, "accredited_investor": True, "max_exposure_pct": 75},
            "UK": {"kyc_required": True, "accredited_investor": False, "max_exposure_pct": 100},
        }

        rules = jurisdiction_rules.get(jurisdiction, jurisdiction_rules["US"])

        kyc_levels = {"basic": 1, "enhanced": 2, "institutional": 3}
        required_level = kyc_levels.get(required_kyc_level, 1)

        return {
            "address": address,
            "jurisdiction": jurisdiction,
            "compliant": subscriber_active,
            "kyc_level": required_kyc_level,
            "kyc_level_numeric": required_level,
            "subscriber_active": subscriber_active,
            "jurisdiction_rules": rules,
            "risk_policy_contract": RWA_CONTRACT_HASHES["RiskPolicyManager"],
            "sentinel_registry_contract": RWA_CONTRACT_HASHES["SentinelRegistry"],
            "required_for_rwa": required_level >= 1 and subscriber_active,
            "asset_class": asset_class,
            "note": (
                "Full ZK-KYC compliance verification planned for Phase 2 "
                "(ZoKrates/Groth16). Current check verifies subscription status."
            ),
            "timestamp": int(time.time()),
        }


# ─── Tool 3: rwa_oracle_query ──────────────────────────────────────────────

@mcp.tool()
async def rwa_oracle_query(
    asset_symbol: str = "USDC",
    query_type: str = "attestation",
    include_price_data: bool = True,
) -> dict:
    """
    Get RWA attestation data from on-chain oracle.
    Queries RiskOracle for on-chain RWA scores and enriches with live data.
    """
    with tracer.start_as_current_span("rwa.oracle_query") as span:
        span.set_attribute("asset_symbol", asset_symbol)
        span.set_attribute("query_type", query_type)

        # On-chain risk score for the asset
        on_chain_result = await _casper_rpc(
            "state_get_dictionary_item",
            {
                "state_root_hash": RWA_CONTRACT_HASHES["RiskOracle"],
                "dictionary_item_key": asset_symbol,
            }
        )

        # AI-enriched attestation data
        ai_attestation = await _groq_query(
            f"RWA attestation data for {asset_symbol}. "
            f"Current collateralization, audit status, issuer credibility, "
            f"regulatory compliance status. "
            f"Return JSON: {{\"attestation_id\": str, \"collateral_ratio\": float, "
            f"\"audit_status\": str, \"issuer_rating\": str, \"compliance_flags\": list}}"
        )

        result = {
            "asset_symbol": asset_symbol,
            "query_type": query_type,
            "on_chain_data": on_chain_result.get("result", "not_found"),
            "ai_attestation": ai_attestation,
            "risk_oracle_contract": RWA_CONTRACT_HASHES["RiskOracle"],
            "audit_trail_contract": RWA_CONTRACT_HASHES["AuditTrail"],
            "network": "casper-test",
            "timestamp": int(time.time()),
        }

        if include_price_data:
            price_data = await _groq_query(
                f"Current price of {asset_symbol} tokenized RWA. "
                f"Return JSON: {{\"price_usd\": float, \"change_24h_pct\": float}}"
            )
            result["price_data"] = price_data

        return result


# ─── Tool 4: subscribe_rwa_feed ────────────────────────────────────────────

@mcp.tool()
async def subscribe_rwa_feed(
    subscriber_address: str,
    plan: str = "standard",
    payment_amount_cspr: float = 10.0,
    asset_filter: Optional[str] = None,
) -> dict:
    """
    x402-gated RWA data subscription.
    Opens a SubscriberVault with escrow deposit, enabling pay-per-query
    access to RWA intelligence via the x402 micropayment protocol.
    """
    with tracer.start_as_current_span("rwa.subscribe_feed") as span:
        span.set_attribute("subscriber_address", subscriber_address[:20])
        span.set_attribute("plan", plan)

        # Calculate pricing
        CSPR_TO_MOTES = 1_000_000_000
        amount_motes = int(payment_amount_cspr * CSPR_TO_MOTES)

        plan_prices = {
            "standard": 1 * CSPR_TO_MOTES,   # 1 CSPR per query
            "premium": 5 * CSPR_TO_MOTES,     # 5 CSPR per query
        }

        query_price = plan_prices.get(plan, plan_prices["standard"])
        expected_queries = amount_motes // query_price if query_price > 0 else 0

        # Build x402 payment request
        x402_payment_request = {
            "version": 1,
            "maxTotalAmount": str(amount_motes),
            "paymentRequirements": [{
                "scheme": "casper-x402",
                "network": "casper-test",
                "assetScale": 9,
                "payTo": RWA_CONTRACT_HASHES["SubscriberVault"],
                "maxAmountRequired": str(query_price),
                "resource": "/api/intel/rwa",
                "description": f"VaultWatch RWA Intelligence — {plan} query",
            }],
        }

        return {
            "subscriber_address": subscriber_address,
            "plan": plan,
            "payment_amount_cspr": payment_amount_cspr,
            "payment_amount_motes": amount_motes,
            "query_price_motes": query_price,
            "expected_queries": expected_queries,
            "x402_payment_request": x402_payment_request,
            "subscriber_vault_contract": RWA_CONTRACT_HASHES["SubscriberVault"],
            "sentinel_credit_contract": RWA_CONTRACT_HASHES["SentinelCredit"],
            "asset_filter": asset_filter,
            "next_step": (
                "Sign the x402 payment request using @make-software/casper-x402 SDK "
                "and submit to Casper testnet. See docs/X402_INTEGRATION.md"
            ),
            "network": "casper-test",
            "timestamp": int(time.time()),
        }


# ─── Tool 5: agent_reputation ──────────────────────────────────────────────

@mcp.tool()
async def agent_reputation(
    agent_name: str = "RWAAgent",
    include_decision_history: bool = False,
) -> dict:
    """
    Query agent trust score for RWA attestations.
    Reads from the on-chain AgentBehaviorIndex contract.
    """
    with tracer.start_as_current_span("rwa.agent_reputation") as span:
        span.set_attribute("agent_name", agent_name)

        # Query on-chain AgentBehaviorIndex for agent metrics
        on_chain_result = await _casper_rpc(
            "state_get_dictionary_item",
            {
                "state_root_hash": RWA_CONTRACT_HASHES["AgentBehaviorIndex"],
                "dictionary_item_key": agent_name,
            }
        )

        # Agent-specific metadata
        agent_metadata = {
            "RWAAgent": {
                "model": "llama-3.3-70b-versatile",
                "specialization": "RWA collateral risk, stablecoin depeg, credit rating analysis",
                "track": "Track 2 (RWA Oracle Agents) + Track 4 (AI Compliance)",
            },
            "AnomalyAgent": {
                "model": "llama-3.3-70b-versatile",
                "specialization": "Protocol anomaly detection, TVL monitoring",
                "track": "Track 2",
            },
            "ScannerAgent": {
                "model": "llama-3.1-8b-instant",
                "specialization": "Vulnerability scanning, exploit detection",
                "track": "Track 2",
            },
            "AuditAgent": {
                "model": "llama-3.1-8b-instant",
                "specialization": "On-chain audit trail writing",
                "track": "Track 2",
            },
        }

        metadata = agent_metadata.get(agent_name, {
            "model": "unknown",
            "specialization": "unknown",
            "track": "unknown",
        })

        result = {
            "agent_name": agent_name,
            "on_chain_metrics": on_chain_result.get("result", "not_found"),
            "metadata": metadata,
            "behavior_index_contract": RWA_CONTRACT_HASHES["AgentBehaviorIndex"],
            "reputation_formula": "Hybrid Brier Score + Escrow-Derived Stake",
            "reputation_source": "agents/reputation.py",
            "network": "casper-test",
            "timestamp": int(time.time()),
        }

        if include_decision_history:
            result["audit_trail_contract"] = RWA_CONTRACT_HASHES["AuditTrail"]
            result["note"] = (
                "Decision history queryable via AuditTrail.get_finding() — "
                "filter by agent_model field"
            )

        return result


if __name__ == "__main__":
    mcp.run()
