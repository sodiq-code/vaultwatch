"""On-chain writers for vaultwatch-rwa-mcp.

Submits REAL deploys to the 8 RWA / risk contracts on Casper testnet via the
**CSPR.click AI Agent Skill** integration (``agents.agent_wallet.AgentWallet``),
which programmatically creates + signs deploys using ``casper-js-sdk`` v5 (the
only SDK that produces Casper-2.x-compatible signatures — see worklog Task 1).

Why AgentWallet (CSPR.click pattern) instead of raw pycspr?
-----------------------------------------------------------
The CSPR.click AI Agent Skill (``skills/csprclick-skill/SKILL.md``) documents
the browser-side wallet flow. For headless agent workflows (MCP server,
pytest e2e, scheduled pipelines), the sanctioned pattern — per the Autarca
reference impl — is ``casper-js-sdk`` v5 + a server-side PEM keypair that is
**created programmatically** via ``PrivateKey.generate()`` (no manual keygen,
no committed secrets). ``AgentWallet`` implements exactly this.

Every write here:
  1. Resolves the agent wallet (auto-created on first call via CSPR.click
     pattern — ``AgentWallet.ensure_exists()``).
  2. Builds the typed-args dict ``{name: {"type": "...", "value": "..."}}``.
  3. Delegates to ``AgentWallet.call_contract`` (non-payable) or
     ``x402_helper.mjs submit-vault-payment`` (the payable ``open_vault``
     path proven in proof/PROOF.md §11).
  4. Returns the verified deploy hash + testnet.cspr.live link.

Payable entry points (``deposit``, ``top_up``) are not exposed as executable
writes here because ``casper_call.cjs`` does not attach value — only
``open_vault`` (via the x402 helper) is. The contract registry still lists
them so LLM agents know they exist.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("vaultwatch_rwa_mcp.writers")

# Make the sibling ``agents`` package importable when this module is loaded
# from inside the vaultwatch_rwa_mcp package.
_PKG_ROOT = Path(__file__).resolve().parent.parent
if str(_PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(_PKG_ROOT))

from agents.agent_wallet import (  # noqa: E402  (after sys.path insert)
    AgentWallet,
    AgentWalletError,
    AgentWalletUnfunded,
    get_agent_wallet,
)
from . import contracts as C  # noqa: E402

__all__ = [
    "get_wallet",
    "wallet_status",
    "record_finding",
    "update_risk_score",
    "upgrade_policy",
    "register_subscriber",
    "deregister_subscriber",
    "log_alert",
    "record_agent_decision",
    "withdraw_credit",
    "withdraw_vault",
    "open_vault",
]


_X402_HELPER = _PKG_ROOT / "x402" / "x402_helper.mjs"


def get_wallet() -> AgentWallet:
    """Return the process-wide agent wallet (CSPR.click AI Agent Skill)."""
    return get_agent_wallet()


def wallet_status() -> Dict[str, Any]:
    """Return a JSON snapshot of the agent wallet (no deploy submitted)."""
    try:
        w = get_wallet()
        return {
            "ok": True,
            "public_key": w.public_key,
            "account_hash": w.account_hash,
            "balance_motes": w.balance_motes,
            "balance_cspr": w.balance_cspr,
            "funded": w.funded,
            "key_algorithm": w.key_algorithm,
            "chain_name": w.chain_name,
            "rpc_url": w.rpc_url,
            "key_path": str(w.key_path),
            "explorer_url": w.explorer_url,
            "faucet_url": w.faucet_url,
            "integration": "CSPR.click AI Agent Skill (headless casper-js-sdk v5)",
        }
    except AgentWalletError as e:
        return {"ok": False, "error": str(e)}


def _typed(args: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """Coerce a {name: value} dict into the {name: {type, value}} schema.

    Infers the CL type from the Python value:
      str  → string
      bool → bool
      int  → u64 (use _u8/_u512 helpers for narrower/wider)
    """
    out: Dict[str, Dict[str, str]] = {}
    for k, v in args.items():
        if isinstance(v, bool):
            out[k] = {"type": "bool", "value": "true" if v else "false"}
        elif isinstance(v, int):
            out[k] = {"type": "u64", "value": str(v)}
        else:
            out[k] = {"type": "string", "value": str(v)}
    return out


def _u8(v: int) -> Dict[str, str]:
    return {"type": "u8", "value": str(int(v))}


def _u32(v: int) -> Dict[str, str]:
    return {"type": "u32", "value": str(int(v))}


def _u64(v: int) -> Dict[str, str]:
    return {"type": "u64", "value": str(int(v))}


def _u512(v: int) -> Dict[str, str]:
    return {"type": "u512", "value": str(int(v))}


def _bool(v: bool) -> Dict[str, str]:
    return {"type": "bool", "value": "true" if v else "false"}


def _str(v: str) -> Dict[str, str]:
    return {"type": "string", "value": str(v)}


def _enrich(result: Dict[str, Any], *, contract: str, entry_point: str,
            args_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Attach consistent metadata to a deploy result."""
    success = bool(result.get("success"))
    return {
        "contract": contract,
        "entry_point": entry_point,
        "contract_hash": C.get_contract_hash(contract),
        "package_hash": C.get_package_hash(contract),
        "args": args_summary,
        "status": "deployed_on_chain" if success else "deploy_failed",
        "on_chain_verified": success,
        "deploy_hash": result.get("deploy_hash", result.get("deployHash", "")),
        "block_hash": result.get("block_hash", result.get("blockHash", "")),
        "gas_cost_motes": result.get("cost_motes", result.get("gasCostMotes", "0")),
        "explorer_url": result.get("link", ""),
        "deployer_account_hash": result.get("deployer_account_hash",
                                            result.get("deployerAccountHash", "")),
        "error": result.get("error"),
        "timestamp": int(time.time()),
        "network": C.DEFAULT_CHAIN_NAME,
    }


# ---------------------------------------------------------------------------
# AuditTrail.record_finding (OPERATOR)
# ---------------------------------------------------------------------------
def record_finding(
    *,
    address: str,
    risk_type: str,
    severity: str,
    confidence: int,
    description: str,
    rwa_enriched: bool = False,
    agent_model: str = "vaultwatch-rwa-mcp",
    block_height: int = 0,
    timestamp: Optional[int] = None,
    wallet: Optional[AgentWallet] = None,
    payment_motes: int = 5_000_000_000,
) -> Dict[str, Any]:
    """Submit ``AuditTrail.record_finding`` deploy (returns new finding id)."""
    w = wallet or get_wallet()
    ts = int(timestamp if timestamp is not None else time.time())
    args = {
        "address": _str(address),
        "risk_type": _str(risk_type),
        "severity": _str(severity),
        "confidence": _u8(confidence),
        "description": _str(description),
        "rwa_enriched": _bool(rwa_enriched),
        "agent_model": _str(agent_model),
        "block_height": _u64(block_height),
        "timestamp": _u64(ts),
    }
    summary = {"address": address, "risk_type": risk_type, "severity": severity,
               "confidence": confidence, "agent_model": agent_model}
    try:
        res = w.call_contract(
            contract_hash=C.get_contract_hash("AuditTrail"),
            entry_point="record_finding",
            args=args,
            payment_motes=payment_motes,
        )
    except (AgentWalletError, AgentWalletUnfunded) as e:
        return _enrich({"success": False, "error": str(e)},
                       contract="AuditTrail", entry_point="record_finding", args_summary=summary)
    return _enrich(res, contract="AuditTrail", entry_point="record_finding", args_summary=summary)


# ---------------------------------------------------------------------------
# RiskOracle.update_score (OPERATOR)
# ---------------------------------------------------------------------------
def update_risk_score(
    *,
    address: str,
    score: int,
    risk_type: str,
    confidence: int,
    block_height: int = 0,
    finding_id: int = 0,
    wallet: Optional[AgentWallet] = None,
    payment_motes: int = 5_000_000_000,
) -> Dict[str, Any]:
    w = wallet or get_wallet()
    args = {
        "address": _str(address),
        "score": _u8(score),
        "risk_type": _str(risk_type),
        "confidence": _u8(confidence),
        "block_height": _u64(block_height),
        "finding_id": _u64(finding_id),
    }
    summary = {"address": address, "score": score, "risk_type": risk_type}
    try:
        res = w.call_contract(
            contract_hash=C.get_contract_hash("RiskOracle"),
            entry_point="update_score",
            args=args,
            payment_motes=payment_motes,
        )
    except (AgentWalletError, AgentWalletUnfunded) as e:
        return _enrich({"success": False, "error": str(e)},
                       contract="RiskOracle", entry_point="update_score", args_summary=summary)
    return _enrich(res, contract="RiskOracle", entry_point="update_score", args_summary=summary)


# ---------------------------------------------------------------------------
# RiskPolicyManager.upgrade_policy (ADMIN)
# ---------------------------------------------------------------------------
def upgrade_policy(
    *,
    min_confidence_threshold: int = 75,
    critical_score_threshold: int = 80,
    high_score_threshold: int = 60,
    medium_score_threshold: int = 40,
    max_retry_count: int = 2,
    safety_rejection_threshold: int = 80,
    block_height: int = 0,
    updated_by: str = "vaultwatch-rwa-mcp",
    wallet: Optional[AgentWallet] = None,
    payment_motes: int = 5_000_000_000,
) -> Dict[str, Any]:
    """Hot-swap risk thresholds (ADMIN-gated, non-payable)."""
    w = wallet or get_wallet()
    args = {
        "min_confidence_threshold": _u8(min_confidence_threshold),
        "critical_score_threshold": _u8(critical_score_threshold),
        "high_score_threshold": _u8(high_score_threshold),
        "medium_score_threshold": _u8(medium_score_threshold),
        "max_retry_count": _u8(max_retry_count),
        "safety_rejection_threshold": _u8(safety_rejection_threshold),
        "block_height": _u64(block_height),
        # The deployed v1 contract accepts updated_by as a String label.
        "updated_by": _str(updated_by[:80]),
    }
    summary = {
        "min_confidence_threshold": min_confidence_threshold,
        "critical_score_threshold": critical_score_threshold,
        "high_score_threshold": high_score_threshold,
        "updated_by": updated_by,
    }
    try:
        res = w.call_contract(
            contract_hash=C.get_contract_hash("RiskPolicyManager"),
            entry_point="upgrade_policy",
            args=args,
            payment_motes=payment_motes,
        )
    except (AgentWalletError, AgentWalletUnfunded) as e:
        return _enrich({"success": False, "error": str(e)},
                       contract="RiskPolicyManager", entry_point="upgrade_policy", args_summary=summary)
    return _enrich(res, contract="RiskPolicyManager", entry_point="upgrade_policy", args_summary=summary)


# ---------------------------------------------------------------------------
# SentinelRegistry.register / deregister (public)
# ---------------------------------------------------------------------------
def register_subscriber(
    *,
    address: str,
    webhook_url: str,
    min_severity: str = "HIGH",
    timestamp: Optional[int] = None,
    wallet: Optional[AgentWallet] = None,
    payment_motes: int = 5_000_000_000,
) -> Dict[str, Any]:
    w = wallet or get_wallet()
    ts = int(timestamp if timestamp is not None else time.time())
    args = {
        "address": _str(address),
        "webhook_url": _str(webhook_url),
        "min_severity": _str(min_severity),
        "timestamp": _u64(ts),
    }
    summary = {"address": address, "webhook_url": webhook_url, "min_severity": min_severity}
    try:
        res = w.call_contract(
            contract_hash=C.get_contract_hash("SentinelRegistry"),
            entry_point="register",
            args=args,
            payment_motes=payment_motes,
        )
    except (AgentWalletError, AgentWalletUnfunded) as e:
        return _enrich({"success": False, "error": str(e)},
                       contract="SentinelRegistry", entry_point="register", args_summary=summary)
    return _enrich(res, contract="SentinelRegistry", entry_point="register", args_summary=summary)


def deregister_subscriber(
    *,
    address: str,
    wallet: Optional[AgentWallet] = None,
    payment_motes: int = 5_000_000_000,
) -> Dict[str, Any]:
    w = wallet or get_wallet()
    args = {"address": _str(address)}
    try:
        res = w.call_contract(
            contract_hash=C.get_contract_hash("SentinelRegistry"),
            entry_point="deregister",
            args=args,
            payment_motes=payment_motes,
        )
    except (AgentWalletError, AgentWalletUnfunded) as e:
        return _enrich({"success": False, "error": str(e)},
                       contract="SentinelRegistry", entry_point="deregister", args_summary={"address": address})
    return _enrich(res, contract="SentinelRegistry", entry_point="deregister", args_summary={"address": address})


# ---------------------------------------------------------------------------
# SentinelAlertLog.log_alert (OPERATOR)
# ---------------------------------------------------------------------------
def log_alert(
    *,
    subscriber_address: str,
    finding_id: int,
    severity: str,
    risk_type: str,
    block_height: int = 0,
    timestamp: Optional[int] = None,
    delivered: bool = True,
    wallet: Optional[AgentWallet] = None,
    payment_motes: int = 5_000_000_000,
) -> Dict[str, Any]:
    w = wallet or get_wallet()
    ts = int(timestamp if timestamp is not None else time.time())
    args = {
        # The contract expects subscriber_address: Address (Casper Key). The
        # non-payable stored-contract call via casper_call.cjs passes it as a
        # String (the account-hash label), matching the verified interaction
        # deploy SentinelAlertLog::log_alert[HIGH_price_crash].
        "subscriber_address": _str(subscriber_address),
        "finding_id": _u64(finding_id),
        "severity": _str(severity),
        "risk_type": _str(risk_type),
        "block_height": _u64(block_height),
        "timestamp": _u64(ts),
        "delivered": _bool(delivered),
    }
    summary = {"subscriber_address": subscriber_address, "finding_id": finding_id, "severity": severity}
    try:
        res = w.call_contract(
            contract_hash=C.get_contract_hash("SentinelAlertLog"),
            entry_point="log_alert",
            args=args,
            payment_motes=payment_motes,
        )
    except (AgentWalletError, AgentWalletUnfunded) as e:
        return _enrich({"success": False, "error": str(e)},
                       contract="SentinelAlertLog", entry_point="log_alert", args_summary=summary)
    return _enrich(res, contract="SentinelAlertLog", entry_point="log_alert", args_summary=summary)


# ---------------------------------------------------------------------------
# AgentBehaviorIndex.record_decision (OPERATOR)
# ---------------------------------------------------------------------------
def record_agent_decision(
    *,
    agent_name: str,
    confidence: int,
    correction_applied: bool = False,
    safety_rejected: bool = False,
    block_height: int = 0,
    wallet: Optional[AgentWallet] = None,
    payment_motes: int = 5_000_000_000,
) -> Dict[str, Any]:
    w = wallet or get_wallet()
    args = {
        "agent_name": _str(agent_name),
        "confidence": _u8(confidence),
        "correction_applied": _bool(correction_applied),
        "safety_rejected": _bool(safety_rejected),
        "block_height": _u64(block_height),
    }
    summary = {"agent_name": agent_name, "confidence": confidence}
    try:
        res = w.call_contract(
            contract_hash=C.get_contract_hash("AgentBehaviorIndex"),
            entry_point="record_decision",
            args=args,
            payment_motes=payment_motes,
        )
    except (AgentWalletError, AgentWalletUnfunded) as e:
        return _enrich({"success": False, "error": str(e)},
                       contract="AgentBehaviorIndex", entry_point="record_decision", args_summary=summary)
    return _enrich(res, contract="AgentBehaviorIndex", entry_point="record_decision", args_summary=summary)


# ---------------------------------------------------------------------------
# SentinelCredit.withdraw (OPERATOR, non-payable — transfers CSPR out)
# ---------------------------------------------------------------------------
def withdraw_credit(
    *,
    account_address: str,
    amount_motes: int,
    wallet: Optional[AgentWallet] = None,
    payment_motes: int = 5_000_000_000,
) -> Dict[str, Any]:
    w = wallet or get_wallet()
    args = {
        "account_address": _str(account_address),
        "amount": _u512(amount_motes),
    }
    summary = {"account_address": account_address, "amount_motes": amount_motes}
    try:
        res = w.call_contract(
            contract_hash=C.get_contract_hash("SentinelCredit"),
            entry_point="withdraw",
            args=args,
            payment_motes=payment_motes,
        )
    except (AgentWalletError, AgentWalletUnfunded) as e:
        return _enrich({"success": False, "error": str(e)},
                       contract="SentinelCredit", entry_point="withdraw", args_summary=summary)
    return _enrich(res, contract="SentinelCredit", entry_point="withdraw", args_summary=summary)


# ---------------------------------------------------------------------------
# SubscriberVault.withdraw (OPERATOR, non-payable)
# ---------------------------------------------------------------------------
def withdraw_vault(
    *,
    subscriber_address: str,
    amount_motes: int,
    current_block: int = 0,
    wallet: Optional[AgentWallet] = None,
    payment_motes: int = 5_000_000_000,
) -> Dict[str, Any]:
    w = wallet or get_wallet()
    args = {
        "subscriber_address": _str(subscriber_address),
        "amount": _u512(amount_motes),
        "current_block": _u64(current_block),
    }
    summary = {"subscriber_address": subscriber_address, "amount_motes": amount_motes}
    try:
        res = w.call_contract(
            contract_hash=C.get_contract_hash("SubscriberVault"),
            entry_point="withdraw",
            args=args,
            payment_motes=payment_motes,
        )
    except (AgentWalletError, AgentWalletUnfunded) as e:
        return _enrich({"success": False, "error": str(e)},
                       contract="SubscriberVault", entry_point="withdraw", args_summary=summary)
    return _enrich(res, contract="SubscriberVault", entry_point="withdraw", args_summary=summary)


# ---------------------------------------------------------------------------
# SubscriberVault.open_vault (OPERATOR, payable) — via x402_helper.mjs
# ---------------------------------------------------------------------------
async def open_vault(
    *,
    subscriber_address: str,
    initial_deposit_motes: int,
    lock_blocks: int = 0,
    auto_renew: bool = True,
    monthly_spend_limit_motes: int = 0,
    current_block: int = 0,
    wallet: Optional[AgentWallet] = None,
    verify_timeout_ms: int = 240_000,
) -> Dict[str, Any]:
    """Open a SubscriberVault escrow vault (payable — attaches CSPR).

    Routes through ``x402/x402_helper.mjs submit-vault-payment`` (the official
    ``@make-software/casper-x402`` payable-deploy path proven in
    proof/PROOF.md §11). ``casper_call.cjs`` cannot attach value, so this is
    the only sanctioned payable write path.
    """
    w = wallet or get_wallet()
    payload = {
        "subscriberAddress": subscriber_address,
        "amountMotes": int(initial_deposit_motes),
        "lockBlocks": int(lock_blocks),
        "autoRenew": bool(auto_renew),
        "monthlySpendLimitMotes": str(int(monthly_spend_limit_motes)),
        "signerPemPath": str(w.key_path),
        "keyAlgorithm": w.key_algorithm,
        "rpcUrl": w.rpc_url,
        "verifyTimeoutMs": int(verify_timeout_ms),
    }
    summary = {
        "subscriber_address": subscriber_address,
        "initial_deposit_motes": initial_deposit_motes,
        "lock_blocks": lock_blocks,
        "auto_renew": auto_renew,
    }
    if not _X402_HELPER.exists():
        return _enrich({"success": False, "error": f"x402 helper not found: {_X402_HELPER}"},
                       contract="SubscriberVault", entry_point="open_vault", args_summary=summary)
    try:
        proc = await asyncio.create_subprocess_exec(
            "node", str(_X402_HELPER), "submit-vault-payment",
            cwd=str(_PKG_ROOT),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate(json.dumps(payload).encode("utf-8"))
        if proc.returncode != 0:
            err = stderr.decode("utf-8", errors="replace").strip()[:500]
            return _enrich({"success": False, "error": f"x402 helper exited {proc.returncode}: {err}"},
                           contract="SubscriberVault", entry_point="open_vault", args_summary=summary)
        result = json.loads(stdout.decode("utf-8"))
    except Exception as e:
        return _enrich({"success": False, "error": f"x402 subprocess error: {e}"},
                       contract="SubscriberVault", entry_point="open_vault", args_summary=summary)
    # Normalise the x402 helper's camelCase keys into the common envelope.
    normalised = {
        "success": bool(result.get("success")),
        "deploy_hash": result.get("deployHash", result.get("deploy_hash", "")),
        "block_hash": result.get("blockHash", result.get("block_hash", "")),
        "cost_motes": result.get("gasCostMotes", result.get("cost_motes", "0")),
        "link": result.get("link", ""),
        "deployer_account_hash": result.get("deployerAccountHash",
                                            result.get("deployer_account_hash", "")),
        "error": result.get("error"),
    }
    return _enrich(normalised, contract="SubscriberVault", entry_point="open_vault", args_summary=summary)
