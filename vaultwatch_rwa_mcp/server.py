"""vaultwatch-rwa-mcp — domain-specific MCP server for the VaultWatch RWA contracts.

A focused Model Context Protocol server that wraps the 8 RWA / risk smart
contracts deployed on the Casper testnet and exposes them to any LLM agent
(Claude Desktop, Cursor, Continue, Cody, …) via the standard MCP stdio
transport.

Scope — what makes this "domain-specific"
-----------------------------------------
Unlike the general ``vaultwatch_mcp`` server (which mixes market data, Groq
anomaly detection, and sidecar streaming), this server is **exclusively** about
the on-chain RWA / risk contract layer:

  * Reads — free ``query_global_state`` JSON-RPC calls that decode the Odra
    2.9.0 storage layout (Var<T> + Mapping<K,V> dictionaries) for every
    contract field. No gas, no signing, no LLM.
  * Writes — REAL deploys signed via the CSPR.click AI Agent Skill
    (``agents.agent_wallet.AgentWallet`` → ``casper-js-sdk`` v5). Each write
    returns the verified deploy hash + testnet.cspr.live link.
  * Resources + Prompts — contract registry, current policy, and audit
    summary surfaces designed for LLM consumption.

Any MCP-compatible client can connect:

    {
      "mcpServers": {
        "vaultwatch-rwa": {
          "command": "python",
          "args": ["-m", "vaultwatch_rwa_mcp.server"]
        }
      }
    }

Or via the npm launcher: ``npx vaultwatch-rwa-mcp``.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Ensure the sibling vaultwatch packages (agents/, api/) are importable.
_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from fastmcp import FastMCP  # noqa: E402

from . import contracts as C  # noqa: E402
from . import readers as R  # noqa: E402
from . import writers as W  # noqa: E402

logger = logging.getLogger("vaultwatch_rwa_mcp")

mcp = FastMCP("VaultWatch-RWA")

__version__ = "1.0.0"


# ===========================================================================
# RESOURCES — read-only URI surfaces designed for LLM context injection
# ===========================================================================
@mcp.resource("rwa://contracts")
def resource_contracts() -> str:
    """The full contract registry — names, hashes, package hashes, entry points.

    Inject this into an LLM context so the agent knows which contracts exist,
    their on-chain addresses, and the exact entry-point signatures it can call.
    """
    return json.dumps(C.list_contracts(), indent=2, default=str)


@mcp.resource("rwa://policy/current")
async def resource_current_policy() -> str:
    """The live on-chain RiskPolicy (hot-swappable thresholds)."""
    policy = await R.read_current_policy()
    return json.dumps(policy or {"error": "policy read failed", "source": "none"}, indent=2, default=str)


@mcp.resource("rwa://audit/count")
async def resource_audit_count() -> str:
    """The live AuditTrail finding count (a single integer)."""
    count = await R.read_finding_count()
    return json.dumps({"finding_count": count, "source": "on-chain" if count is not None else "unavailable"}, indent=2)


# ===========================================================================
# PROMPTS — reusable LLM task templates
# ===========================================================================
@mcp.prompt()
def rwa_explain_contracts() -> str:
    """Explain the 8 VaultWatch RWA contracts and their roles in the Casper ecosystem."""
    return (
        "You are a Casper blockchain assistant. Explain the 8 VaultWatch RWA / risk "
        "contracts deployed on the Casper testnet. For each contract, describe its role, "
        "its key entry points, and how an AI agent or DeFi protocol would use it. Use the "
        "rwa://contracts resource for the exact entry-point signatures. The contracts are: "
        + ", ".join(C.CONTRACTS.keys())
        + ". Be precise about which entry points are read-only (public) vs role-gated "
        "(OPERATOR / ADMIN / PAUSER) and which are payable."
    )


@mcp.prompt()
def rwa_audit_summary() -> str:
    """Summarise the current on-chain AuditTrail state (count + recent findings)."""
    return (
        "Summarise the current state of the VaultWatch AuditTrail contract on Casper testnet. "
        "Call rwa_audit_get_count and rwa_audit_recent_findings to get the live data, then "
        "produce a concise report: total findings, the most recent 5 findings (id, severity, "
        "risk_type, confidence, agent_model), and any severity distribution. Note which "
        "findings are RWA-enriched. End with one sentence on the overall risk posture."
    )


@mcp.prompt()
def rwa_risk_assessment(address: str) -> str:
    """Assess the on-chain risk for a Casper address (RiskOracle score + high-risk check)."""
    return (
        f"Assess the on-chain risk for Casper address '{address}'. "
        "Call rwa_risk_get_score with this address, then call rwa_risk_is_high_risk with "
        "threshold=70. Also call rwa_audit_recent_findings and filter for any finding whose "
        "'address' field matches. Produce a risk report: the RiskOracle score, confidence, "
        "risk_type, whether the address is high-risk, and any matching audit findings. "
        "Conclude with a recommended action (monitor / alert / block)."
    )


@mcp.prompt()
def rwa_policy_review() -> str:
    """Review the current on-chain RiskPolicy and recommend adjustments."""
    return (
        "Review the current on-chain VaultWatch RiskPolicy. Call rwa_policy_get_current to "
        "read the live policy (min_confidence_threshold, critical_score_threshold, "
        "high_score_threshold, medium_score_threshold, max_retry_count, "
        "safety_rejection_threshold, version, updated_by). Compare the values against "
        "conservative defaults (75/80/60/40/2/80) and recommend whether any threshold "
        "should be tightened or loosened, with a one-line rationale per recommendation. "
        "Do NOT submit an upgrade_policy deploy unless explicitly asked."
    )


# ===========================================================================
# TOOLS — discovery + introspection
# ===========================================================================
@mcp.tool()
def rwa_list_contracts() -> dict:
    """List all 8 RWA / risk contracts with their hashes, package hashes, and entry points.

    Returns a JSON-serialisable registry. Use this first to discover what's
    available before calling contract-specific read/write tools.
    """
    return {
        "contracts": C.list_contracts(),
        "count": len(C.CONTRACTS),
        "network": C.DEFAULT_CHAIN_NAME,
        "rpc_url": C.DEFAULT_RPC_URL,
    }


@mcp.tool()
async def rwa_contract_entrypoints(contract: str) -> dict:
    """List the on-chain entry points of a contract (verified via query_global_state).

    Args:
        contract: one of AuditTrail, RiskOracle, SentinelCredit, SentinelRegistry,
            SentinelAlertLog, AgentBehaviorIndex, RiskPolicyManager, SubscriberVault.
    """
    if contract not in C.CONTRACTS:
        return {"error": f"unknown contract: {contract}", "valid": list(C.CONTRACTS)}
    return await R.query_contract(contract)


@mcp.tool()
async def rwa_contract_package(contract: str) -> dict:
    """Read the on-chain ContractPackage (versions, disabled versions, lock status).

    Use this to check whether a contract has been upgraded (e.g. the
    RiskPolicyManager v1→v2 Casper-native upgrade).
    """
    if contract not in C.CONTRACTS:
        return {"error": f"unknown contract: {contract}", "valid": list(C.CONTRACTS)}
    return await R.query_contract_package(contract)


@mcp.tool()
async def rwa_block_height() -> dict:
    """Return the latest Casper testnet block height."""
    h = await R.get_block_height()
    return {"block_height": h, "network": C.DEFAULT_CHAIN_NAME, "timestamp": int(time.time())}


# ===========================================================================
# TOOLS — AuditTrail reads
# ===========================================================================
@mcp.tool()
async def rwa_audit_get_count() -> dict:
    """Read AuditTrail.finding_count (Var<u64>) — the total number of recorded findings."""
    count = await R.read_finding_count()
    return {
        "contract": "AuditTrail",
        "finding_count": count,
        "contract_hash": C.get_contract_hash("AuditTrail"),
        "source": "on-chain" if count is not None else "unavailable",
    }


@mcp.tool()
async def rwa_audit_get_finding(finding_id: int) -> dict:
    """Read a single AuditTrail finding by id (Mapping<u64, Finding>).

    Args:
        finding_id: the 1-based finding id returned by record_finding.
    """
    finding = await R.read_finding(finding_id)
    return {
        "contract": "AuditTrail",
        "finding_id": finding_id,
        "finding": finding,
        "contract_hash": C.get_contract_hash("AuditTrail"),
        "source": "on-chain" if finding is not None else "not_found",
    }


@mcp.tool()
async def rwa_audit_recent_findings(limit: int = 10) -> dict:
    """Read the latest N AuditTrail findings (newest first).

    Args:
        limit: max findings to return (default 10, capped at 50).
    """
    limit = max(1, min(50, int(limit)))
    findings = await R.read_recent_findings(limit)
    return {
        "contract": "AuditTrail",
        "findings": findings,
        "count": len(findings),
        "contract_hash": C.get_contract_hash("AuditTrail"),
        "source": "on-chain",
    }


# ===========================================================================
# TOOLS — RiskOracle reads
# ===========================================================================
@mcp.tool()
async def rwa_risk_get_score(address: str) -> dict:
    """Read RiskOracle.scores[address] (Mapping<String, RiskScore>).

    Args:
        address: the Casper account hash string the contract stores (e.g.
            ``account-hash-<64 hex>`` or a public key label).
    """
    score = await R.read_risk_score(address)
    return {
        "contract": "RiskOracle",
        "address": address,
        "risk_score": score,
        "contract_hash": C.get_contract_hash("RiskOracle"),
        "source": "on-chain" if score is not None else "not_found",
    }


@mcp.tool()
async def rwa_risk_is_high_risk(address: str, threshold: int = 70) -> dict:
    """Check whether an address's RiskOracle score exceeds a threshold (computed locally).

    Args:
        address: the Casper address / account-hash string.
        threshold: score threshold (0-100, default 70).
    """
    score = await R.read_risk_score(address)
    if score is None:
        return {
            "contract": "RiskOracle",
            "address": address,
            "threshold": threshold,
            "is_high_risk": False,
            "score": None,
            "source": "not_found",
            "note": "no RiskOracle score recorded for this address",
        }
    return {
        "contract": "RiskOracle",
        "address": address,
        "threshold": threshold,
        "score": score.get("score"),
        "is_high_risk": score.get("score", 0) >= threshold,
        "risk_type": score.get("risk_type"),
        "confidence": score.get("confidence"),
        "contract_hash": C.get_contract_hash("RiskOracle"),
        "source": "on-chain",
    }


# ===========================================================================
# TOOLS — RiskPolicyManager reads
# ===========================================================================
@mcp.tool()
async def rwa_policy_get_current() -> dict:
    """Read RiskPolicyManager.current_policy (Var<RiskPolicy>) — the live risk policy."""
    policy = await R.read_current_policy()
    return {
        "contract": "RiskPolicyManager",
        "current_policy": policy,
        "contract_hash": C.get_contract_hash("RiskPolicyManager"),
        "source": "on-chain" if policy is not None else "unavailable",
    }


@mcp.tool()
async def rwa_policy_get_version(version: int) -> dict:
    """Read a historical RiskPolicy by version (Mapping<u32, RiskPolicy>).

    Args:
        version: the policy version number (1-based).
    """
    policy = await R.read_policy_version(version)
    return {
        "contract": "RiskPolicyManager",
        "version": version,
        "policy": policy,
        "contract_hash": C.get_contract_hash("RiskPolicyManager"),
        "source": "on-chain" if policy is not None else "not_found",
    }


@mcp.tool()
async def rwa_policy_get_current_version() -> dict:
    """Read the current RiskPolicy version number (u32)."""
    policy = await R.read_current_policy()
    version = policy.get("version") if policy else None
    return {
        "contract": "RiskPolicyManager",
        "current_version": version,
        "contract_hash": C.get_contract_hash("RiskPolicyManager"),
        "source": "on-chain" if version is not None else "unavailable",
    }


# ===========================================================================
# TOOLS — SentinelRegistry reads
# ===========================================================================
@mcp.tool()
async def rwa_sentinel_get_subscriber(address: str) -> dict:
    """Read SentinelRegistry.subscribers[address] (Mapping<String, Subscriber>).

    Args:
        address: the subscriber's Casper address / account-hash string.
    """
    sub = await R.read_subscriber(address)
    return {
        "contract": "SentinelRegistry",
        "address": address,
        "subscriber": sub,
        "contract_hash": C.get_contract_hash("SentinelRegistry"),
        "source": "on-chain" if sub is not None else "not_found",
    }


@mcp.tool()
async def rwa_sentinel_is_active(address: str) -> dict:
    """Check whether an address is an active SentinelRegistry subscriber.

    Args:
        address: the subscriber's Casper address / account-hash string.
    """
    sub = await R.read_subscriber(address)
    if sub is None:
        return {
            "contract": "SentinelRegistry",
            "address": address,
            "is_active": False,
            "source": "not_found",
            "note": "no subscriber record for this address",
        }
    return {
        "contract": "SentinelRegistry",
        "address": address,
        "is_active": sub.get("active", False),
        "min_severity": sub.get("min_severity"),
        "alert_count": sub.get("alert_count"),
        "contract_hash": C.get_contract_hash("SentinelRegistry"),
        "source": "on-chain",
    }


@mcp.tool()
async def rwa_sentinel_get_count() -> dict:
    """Read SentinelRegistry.subscriber_count (Var<u64>) — total registered subscribers."""
    count = await R.read_subscriber_count()
    return {
        "contract": "SentinelRegistry",
        "subscriber_count": count,
        "contract_hash": C.get_contract_hash("SentinelRegistry"),
        "source": "on-chain" if count is not None else "unavailable",
    }


# ===========================================================================
# TOOLS — SentinelAlertLog reads
# ===========================================================================
@mcp.tool()
async def rwa_alert_get_log(log_id: int) -> dict:
    """Read SentinelAlertLog.logs[log_id] (Mapping<u64, AlertRecord>).

    Args:
        log_id: the 1-based alert log id returned by log_alert.
    """
    log = await R.read_alert_log(log_id)
    return {
        "contract": "SentinelAlertLog",
        "log_id": log_id,
        "alert": log,
        "contract_hash": C.get_contract_hash("SentinelAlertLog"),
        "source": "on-chain" if log is not None else "not_found",
    }


@mcp.tool()
async def rwa_alert_get_total_count() -> dict:
    """Read SentinelAlertLog.log_count (Var<u64>) — total alerts ever logged."""
    count = await R.read_alert_log_count()
    return {
        "contract": "SentinelAlertLog",
        "total_alert_count": count,
        "contract_hash": C.get_contract_hash("SentinelAlertLog"),
        "source": "on-chain" if count is not None else "unavailable",
    }


# ===========================================================================
# TOOLS — SentinelCredit reads
# ===========================================================================
@mcp.tool()
async def rwa_credit_get_account(account_address: str) -> dict:
    """Read SentinelCredit.accounts[address] (Mapping<String, CreditAccount>).

    Args:
        account_address: the account's Casper address / account-hash string.
    """
    acct = await R.read_credit_account(account_address)
    return {
        "contract": "SentinelCredit",
        "account_address": account_address,
        "account": acct,
        "contract_hash": C.get_contract_hash("SentinelCredit"),
        "source": "on-chain" if acct is not None else "not_found",
    }


@mcp.tool()
async def rwa_credit_get_balance(account_address: str) -> dict:
    """Read a SentinelCredit account's prepaid balance (U512 motes).

    Args:
        account_address: the account's Casper address / account-hash string.
    """
    bal = await R.read_credit_balance(account_address)
    return {
        "contract": "SentinelCredit",
        "account_address": account_address,
        "balance_motes": bal,
        "balance_cspr": (bal / 1_000_000_000) if bal is not None else None,
        "contract_hash": C.get_contract_hash("SentinelCredit"),
        "source": "on-chain" if bal is not None else "not_found",
    }


@mcp.tool()
async def rwa_credit_get_prices() -> dict:
    """Read SentinelCredit query_price + premium_price (Var<U512> each)."""
    prices = await R.read_credit_prices()
    return {
        "contract": "SentinelCredit",
        "prices_motes": prices,
        "prices_cspr": ({"query_price": prices["query_price"] / 1_000_000_000, "premium_price": prices["premium_price"] / 1_000_000_000} if prices else None),
        "contract_hash": C.get_contract_hash("SentinelCredit"),
        "source": "on-chain" if prices is not None else "unavailable",
    }


@mcp.tool()
async def rwa_credit_get_total_revenue() -> dict:
    """Read SentinelCredit.total_revenue (Var<U512>) — lifetime CSPR collected."""
    rev = await R.read_total_revenue()
    return {
        "contract": "SentinelCredit",
        "total_revenue_motes": rev,
        "total_revenue_cspr": (rev / 1_000_000_000) if rev is not None else None,
        "contract_hash": C.get_contract_hash("SentinelCredit"),
        "source": "on-chain" if rev is not None else "unavailable",
    }


# ===========================================================================
# TOOLS — SubscriberVault reads
# ===========================================================================
@mcp.tool()
async def rwa_vault_get_account(subscriber_address: str) -> dict:
    """Read SubscriberVault.accounts[address] (Mapping<String, VaultAccount>).

    Args:
        subscriber_address: the subscriber's Casper address / account-hash string.
    """
    acct = await R.read_vault_account(subscriber_address)
    return {
        "contract": "SubscriberVault",
        "subscriber_address": subscriber_address,
        "account": acct,
        "contract_hash": C.get_contract_hash("SubscriberVault"),
        "source": "on-chain" if acct is not None else "not_found",
    }


@mcp.tool()
async def rwa_vault_get_balance(subscriber_address: str) -> dict:
    """Read a SubscriberVault account's escrowed balance (U512 motes).

    Args:
        subscriber_address: the subscriber's Casper address / account-hash string.
    """
    bal = await R.read_vault_balance(subscriber_address)
    return {
        "contract": "SubscriberVault",
        "subscriber_address": subscriber_address,
        "escrowed_balance_motes": bal,
        "escrowed_balance_cspr": (bal / 1_000_000_000) if bal is not None else None,
        "contract_hash": C.get_contract_hash("SubscriberVault"),
        "source": "on-chain" if bal is not None else "not_found",
    }


@mcp.tool()
async def rwa_vault_get_total_locked() -> dict:
    """Read SubscriberVault.total_locked (Var<U512>) — total CSPR escrowed across all vaults."""
    locked = await R.read_total_locked()
    return {
        "contract": "SubscriberVault",
        "total_locked_motes": locked,
        "total_locked_cspr": (locked / 1_000_000_000) if locked is not None else None,
        "contract_hash": C.get_contract_hash("SubscriberVault"),
        "source": "on-chain" if locked is not None else "unavailable",
    }


# ===========================================================================
# TOOLS — AgentBehaviorIndex reads
# ===========================================================================
@mcp.tool()
async def rwa_agent_get_metrics(agent_name: str) -> dict:
    """Read AgentBehaviorIndex.metrics[agent_name] (Mapping<String, AgentMetrics>).

    Args:
        agent_name: e.g. "AnomalyAgent", "RWAAgent", "ScannerAgent".
    """
    m = await R.read_agent_metrics(agent_name)
    return {
        "contract": "AgentBehaviorIndex",
        "agent_name": agent_name,
        "metrics": m,
        "contract_hash": C.get_contract_hash("AgentBehaviorIndex"),
        "source": "on-chain" if m is not None else "not_found",
    }


@mcp.tool()
async def rwa_agent_get_trust_score(agent_name: str) -> dict:
    """Read an agent's trust score (u8, 0-100) from AgentBehaviorIndex.

    Args:
        agent_name: e.g. "AnomalyAgent".
    """
    ts = await R.read_agent_trust_score(agent_name)
    return {
        "contract": "AgentBehaviorIndex",
        "agent_name": agent_name,
        "trust_score": ts,
        "contract_hash": C.get_contract_hash("AgentBehaviorIndex"),
        "source": "on-chain" if ts is not None else "not_found",
    }


@mcp.tool()
async def rwa_agent_get_count() -> dict:
    """Read AgentBehaviorIndex.agent_count (Var<u64>) — total agents with recorded decisions."""
    count = await R.read_agent_count()
    return {
        "contract": "AgentBehaviorIndex",
        "agent_count": count,
        "contract_hash": C.get_contract_hash("AgentBehaviorIndex"),
        "source": "on-chain" if count is not None else "unavailable",
    }


# ===========================================================================
# TOOLS — Wallet (CSPR.click AI Agent Skill)
# ===========================================================================
@mcp.tool()
def rwa_wallet_status() -> dict:
    """Return the status of the agent wallet (CSPR.click AI Agent Skill integration).

    Shows the programmatically-created agent wallet's public key, account hash,
    CSPR balance, and funded status. The wallet is auto-created on first call
    via ``PrivateKey.generate()`` (casper-js-sdk v5) — no manual keygen.
    """
    return W.wallet_status()


@mcp.tool()
def rwa_wallet_ensure() -> dict:
    """Ensure an agent wallet exists (create one on first call via CSPR.click pattern).

    Returns the wallet status. If the wallet is unfunded, the response includes
    the testnet faucet URL — fund it once, then re-call to confirm.
    """
    return W.wallet_status()


# ===========================================================================
# TOOLS — Writes (REAL deploys via AgentWallet + casper-js-sdk v5)
# ===========================================================================
@mcp.tool()
def rwa_audit_record_finding(
    address: str,
    risk_type: str,
    severity: str,
    confidence: int,
    description: str,
    rwa_enriched: bool = False,
    agent_model: str = "vaultwatch-rwa-mcp",
    block_height: int = 0,
    timestamp: Optional[int] = None,
) -> dict:
    """Submit a REAL AuditTrail.record_finding deploy (OPERATOR-gated).

    Appends an immutable Finding to the on-chain audit log. Returns the verified
    deploy hash + testnet.cspr.live link. The agent wallet must hold OPERATOR
    role on AuditTrail (granted by the role_admin via grant_role).

    Args:
        address: the Casper address the finding pertains to.
        risk_type: e.g. "wash_trading", "oracle_manipulation", "depeg".
        severity: one of LOW / MEDIUM / HIGH / CRITICAL.
        confidence: 0-100 confidence score.
        description: human-readable finding summary.
        rwa_enriched: whether RWA context was added.
        agent_model: the agent model name (e.g. "AnomalyAgent").
        block_height: the block the finding relates to (0 = unknown).
        timestamp: unix seconds (default: now).
    """
    return W.record_finding(
        address=address,
        risk_type=risk_type,
        severity=severity,
        confidence=confidence,
        description=description,
        rwa_enriched=rwa_enriched,
        agent_model=agent_model,
        block_height=block_height,
        timestamp=timestamp,
    )


@mcp.tool()
def rwa_risk_update_score(
    address: str,
    score: int,
    risk_type: str,
    confidence: int,
    block_height: int = 0,
    finding_id: int = 0,
) -> dict:
    """Submit a REAL RiskOracle.update_score deploy (OPERATOR-gated).

    Updates the on-chain risk score for an address. Any Casper protocol reading
    RiskOracle inherits the new score immediately.

    Args:
        address: the Casper address to score.
        score: 0-100 risk score (higher = riskier).
        risk_type: e.g. "liquidity", "credit", "smart_contract".
        confidence: 0-100 confidence in the score.
        block_height: block the score relates to.
        finding_id: the AuditTrail finding id that triggered this score.
    """
    return W.update_risk_score(
        address=address,
        score=score,
        risk_type=risk_type,
        confidence=confidence,
        block_height=block_height,
        finding_id=finding_id,
    )


@mcp.tool()
def rwa_policy_upgrade(
    min_confidence_threshold: int = 75,
    critical_score_threshold: int = 80,
    high_score_threshold: int = 60,
    medium_score_threshold: int = 40,
    max_retry_count: int = 2,
    safety_rejection_threshold: int = 80,
    block_height: int = 0,
    updated_by: str = "vaultwatch-rwa-mcp",
) -> dict:
    """Submit a REAL RiskPolicyManager.upgrade_policy deploy (ADMIN-gated).

    Hot-swaps the risk thresholds WITHOUT redeploying the contract. Agents read
    the updated policy every decision cycle. The agent wallet must hold ADMIN
    role on RiskPolicyManager.

    Args:
        min_confidence_threshold: min confidence to record a finding (0-100).
        critical_score_threshold: score threshold for CRITICAL severity.
        high_score_threshold: score threshold for HIGH severity.
        medium_score_threshold: score threshold for MEDIUM severity.
        max_retry_count: SelfCorrection retry limit.
        safety_rejection_threshold: SafetyGuard block threshold.
        block_height: block at which the upgrade is recorded.
        updated_by: human-readable label (stored on-chain as updated_by).
    """
    return W.upgrade_policy(
        min_confidence_threshold=min_confidence_threshold,
        critical_score_threshold=critical_score_threshold,
        high_score_threshold=high_score_threshold,
        medium_score_threshold=medium_score_threshold,
        max_retry_count=max_retry_count,
        safety_rejection_threshold=safety_rejection_threshold,
        block_height=block_height,
        updated_by=updated_by,
    )


@mcp.tool()
def rwa_sentinel_register(
    address: str,
    webhook_url: str,
    min_severity: str = "HIGH",
    timestamp: Optional[int] = None,
) -> dict:
    """Submit a REAL SentinelRegistry.register deploy (public — any account).

    Registers an address for push-alert delivery with a min-severity filter.

    Args:
        address: the subscriber's Casper address.
        webhook_url: the HTTPS webhook to deliver alerts to.
        min_severity: minimum severity to receive (LOW/MEDIUM/HIGH/CRITICAL).
        timestamp: unix seconds (default: now).
    """
    return W.register_subscriber(
        address=address,
        webhook_url=webhook_url,
        min_severity=min_severity,
        timestamp=timestamp,
    )


@mcp.tool()
def rwa_sentinel_deregister(address: str) -> dict:
    """Submit a REAL SentinelRegistry.deregister deploy (public — any account).

    Args:
        address: the subscriber's Casper address to deregister.
    """
    return W.deregister_subscriber(address=address)


@mcp.tool()
def rwa_alert_log(
    subscriber_address: str,
    finding_id: int,
    severity: str,
    risk_type: str,
    block_height: int = 0,
    timestamp: Optional[int] = None,
    delivered: bool = True,
) -> dict:
    """Submit a REAL SentinelAlertLog.log_alert deploy (OPERATOR-gated).

    Records a timestamped alert for a subscriber. Compliance-grade: proves
    receipt of a CRITICAL alert at a specific block.

    Args:
        subscriber_address: the subscriber's Casper account-hash string.
        finding_id: the AuditTrail finding id that triggered the alert.
        severity: LOW / MEDIUM / HIGH / CRITICAL.
        risk_type: e.g. "price_crash", "oracle_depeg".
        block_height: block at which the alert was raised.
        timestamp: unix seconds (default: now).
        delivered: whether the webhook delivery succeeded.
    """
    return W.log_alert(
        subscriber_address=subscriber_address,
        finding_id=finding_id,
        severity=severity,
        risk_type=risk_type,
        block_height=block_height,
        timestamp=timestamp,
        delivered=delivered,
    )


@mcp.tool()
def rwa_agent_record_decision(
    agent_name: str,
    confidence: int,
    correction_applied: bool = False,
    safety_rejected: bool = False,
    block_height: int = 0,
) -> dict:
    """Submit a REAL AgentBehaviorIndex.record_decision deploy (OPERATOR-gated).

    Records an AI agent's decision on-chain, contributing to its trust score.
    The contract recomputes trust_score = (high_confidence_count * 100 / total)
    − (corrections + safety_rejections) * 5.

    Args:
        agent_name: e.g. "AnomalyAgent", "RWAAgent".
        confidence: 0-100 confidence in the decision.
        correction_applied: whether SelfCorrection modified the decision.
        safety_rejected: whether SafetyGuard blocked the decision.
        block_height: block at which the decision was made.
    """
    return W.record_agent_decision(
        agent_name=agent_name,
        confidence=confidence,
        correction_applied=correction_applied,
        safety_rejected=safety_rejected,
        block_height=block_height,
    )


@mcp.tool()
def rwa_credit_withdraw(account_address: str, amount_motes: int) -> dict:
    """Submit a REAL SentinelCredit.withdraw deploy (OPERATOR-gated).

    Withdraws prepaid CSPR credit back to the account holder.

    Args:
        account_address: the account's Casper address / account-hash string.
        amount_motes: amount to withdraw in motes (1 CSPR = 1e9 motes).
    """
    return W.withdraw_credit(account_address=account_address, amount_motes=amount_motes)


@mcp.tool()
def rwa_vault_withdraw(subscriber_address: str, amount_motes: int, current_block: int = 0) -> dict:
    """Submit a REAL SubscriberVault.withdraw deploy (OPERATOR-gated).

    Withdraws escrowed CSPR from a subscriber vault (respects lock period).

    Args:
        subscriber_address: the subscriber's Casper address / account-hash string.
        amount_motes: amount to withdraw in motes.
        current_block: the current block height (for lock-period check).
    """
    return W.withdraw_vault(
        subscriber_address=subscriber_address,
        amount_motes=amount_motes,
        current_block=current_block,
    )


@mcp.tool()
async def rwa_vault_open(
    subscriber_address: str,
    initial_deposit_motes: int,
    lock_blocks: int = 0,
    auto_renew: bool = True,
    monthly_spend_limit_motes: int = 0,
    current_block: int = 0,
) -> dict:
    """Submit a REAL SubscriberVault.open_vault deploy (OPERATOR-gated, PAYABLE).

    Opens an escrow vault by attaching CSPR (via the official
    @make-software/casper-x402 payable-deploy path — the only sanctioned way to
    attach value to a stored-contract call; casper_call.cjs cannot attach value).

    Args:
        subscriber_address: the subscriber's Casper address.
        initial_deposit_motes: CSPR to escrow (1 CSPR = 1e9 motes).
        lock_blocks: 0 = no lock, or N blocks to lock the deposit.
        auto_renew: whether to auto-renew the subscription.
        monthly_spend_limit_motes: monthly spend cap (0 = unlimited).
        current_block: the current block height.
    """
    return await W.open_vault(
        subscriber_address=subscriber_address,
        initial_deposit_motes=initial_deposit_motes,
        lock_blocks=lock_blocks,
        auto_renew=auto_renew,
        monthly_spend_limit_motes=monthly_spend_limit_motes,
        current_block=current_block,
    )


# ===========================================================================
# CLI helpers — introspection / smoke tests (do NOT start the MCP stdio loop)
# ===========================================================================
def _cli_list_tools() -> int:
    """Print the registered tools / resources / prompts as JSON and exit.

    Used for smoke-testing the server without speaking the MCP stdio protocol:

        python -m vaultwatch_rwa_mcp.server --list-tools

    The output is a JSON object with three keys: ``tools``, ``resources``,
    ``prompts``. Each is a list of ``{name, description}`` dicts. This is
    intentionally NOT a full MCP handshake — it just confirms the server
    imports cleanly, the FastMCP registry is populated, and every tool has a
    non-empty description.
    """
    import asyncio

    from fastmcp import Client

    async def _run() -> dict:
        async with Client(mcp) as c:
            tools = await c.list_tools()
            resources = await c.list_resources()
            prompts = await c.list_prompts()
            return {
                "server": mcp.name,
                "version": __version__,
                "network": C.DEFAULT_CHAIN_NAME,
                "rpc_url": C.DEFAULT_RPC_URL,
                "contracts": len(C.CONTRACTS),
                "tools": [{"name": t.name, "description": (t.description or "").splitlines()[0][:120]} for t in tools],
                "resources": [{"uri": str(r.uri), "description": (r.description or "")[:120]} for r in resources],
                "prompts": [{"name": p.name, "description": (p.description or "")[:120]} for p in prompts],
            }

    payload = asyncio.run(_run())
    print(json.dumps(payload, indent=2, default=str))
    # Non-zero exit if any tool is missing a description — smoke-test guard.
    bad = [t["name"] for t in payload["tools"] if not t["description"]]
    if bad:
        sys.stderr.write(f"ERROR: tools missing description: {bad}\n")
        return 2
    return 0


def _cli_smoke_read() -> int:
    """Exercise one free read tool against the live Casper testnet and exit.

    Used to confirm the server can actually reach the chain end-to-end:

        python -m vaultwatch_rwa_mcp.server --smoke-read

    Prints the AuditTrail finding count and exits 0 on success, 1 on failure.
    """
    import asyncio

    from fastmcp import Client

    async def _run() -> dict:
        async with Client(mcp) as c:
            r = await c.call_tool("rwa_audit_get_count", {})
            return json.loads(r.content[0].text)

    try:
        payload = asyncio.run(_run())
    except Exception as exc:  # pragma: no cover — network-dependent
        sys.stderr.write(f"ERROR: smoke-read failed: {exc}\n")
        return 1
    print(json.dumps(payload, indent=2, default=str))
    if payload.get("finding_count") is None:
        sys.stderr.write("ERROR: smoke-read returned no count\n")
        return 1
    return 0


# ===========================================================================
# Entrypoint
# ===========================================================================
def main() -> None:
    """Run the MCP server over stdio (the standard MCP transport).

    CLI flags (mutually exclusive; for smoke-testing only):

      --list-tools   Print the registered tools/resources/prompts as JSON and exit.
      --smoke-read   Exercise one free read against the live Casper testnet and exit.
      --help, -h     Show usage.

    With no flag, the server starts the MCP stdio loop (the normal mode for
    Claude Desktop / Cursor / Continue / npx).
    """
    logging.basicConfig(
        level=os.getenv("VAULTWATCH_RWA_MCP_LOG", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    argv = sys.argv[1:]
    if argv:
        flag = argv[0]
        if flag in ("-h", "--help"):
            print(__doc__)
            print(
                "\nUsage:\n"
                "  python -m vaultwatch_rwa_mcp.server            # start MCP stdio server\n"
                "  python -m vaultwatch_rwa_mcp.server --list-tools\n"
                "  python -m vaultwatch_rwa_mcp.server --smoke-read\n"
            )
            return
        if flag == "--list-tools":
            sys.exit(_cli_list_tools())
        if flag == "--smoke-read":
            sys.exit(_cli_smoke_read())
        sys.stderr.write(f"ERROR: unknown flag {flag!r}\n")
        sys.stderr.write("Run with --help for usage.\n")
        sys.exit(2)

    logger.info("vaultwatch-rwa-mcp v%s starting (network=%s, rpc=%s)", __version__, C.DEFAULT_CHAIN_NAME, C.DEFAULT_RPC_URL)
    mcp.run()


if __name__ == "__main__":
    main()
