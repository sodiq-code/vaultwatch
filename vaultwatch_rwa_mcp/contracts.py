"""Contract registry for vaultwatch-rwa-mcp.

Single source of truth for the 8 RWA / risk contracts deployed on the Casper
testnet: their hashes, package hashes, Odra field indices, and entry-point
metadata (argument schemas + role gating).

This module is intentionally dependency-free (stdlib only) so it can be
imported by the MCP server, the test suite, and external tooling without
pulling in httpx / fastmcp.

All hashes are verified live on ``casper-test`` (see ``deploy_hashes_live.json``
and ``tests/e2e/conftest.py``). Override any of them via environment variables
(useful for pointing at a fresh deploy).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List

__all__ = [
    "ContractMeta",
    "EntryPoint",
    "CONTRACTS",
    "CONTRACT_HASHES",
    "CONTRACT_PACKAGE_HASHES",
    "FIELD_INDICES",
    "ENTRY_POINTS",
    "DEFAULT_RPC_URL",
    "DEFAULT_CHAIN_NAME",
    "get_contract_hash",
    "get_package_hash",
    "get_field_index",
    "list_contracts",
]


DEFAULT_RPC_URL = os.getenv("CASPER_RPC_URL", "https://node.testnet.casper.network/rpc")
DEFAULT_CHAIN_NAME = os.getenv("CASPER_CHAIN_NAME", "casper-test")


# ---------------------------------------------------------------------------
# Verified live contract hashes (deploy_hashes_live.json — the canonical source)
# ---------------------------------------------------------------------------
CONTRACT_HASHES: Dict[str, str] = {
    "AuditTrail": "cd1579001dcd923888baa9ea44b1df3b816de52ced44682a3042779d1d4d9932",
    "RiskOracle": "234a34a71fb04625971373b06b73ac6dbc5f7d701f7e96621c752d73ccde80ff",
    "SentinelCredit": "993d8947a6c8220539efaea87c7631c9fc45780c674406d48487bcf66fb1cbfb",
    "SentinelRegistry": "9cce03a0e5d1aa3dab07da50afb4cb9eaba29973eb2b1e766cc6724a1e34e31e",
    "SentinelAlertLog": "43f9b7df3f9f808db8b035c13ae0bac0b47335709abeafdc36e6a9bffe9b9322",
    "AgentBehaviorIndex": "1a976fe839366c4399541055245695cf94626b3d99c0f3a6675ae761395d822b",
    "RiskPolicyManager": "1027cb2a989b75d8b29b82cab60a8b12a892138a5704cdd4753a0862f65b1d85",
    "SubscriberVault": "9a93db9c1f315f1ed34ee55e46f65ed28585f9529fb8427aedf937a6ea0d7bd0",
}

CONTRACT_PACKAGE_HASHES: Dict[str, str] = {
    "AuditTrail": "hash-7e653fc142ddd4f1759aec0c2f4fb0537eb167cfb9771d12c37ae55f29c270fa",
    "RiskOracle": "hash-1a47fd766eb021aa83cc44b5a729920842253510936cbe9a1545bf6dc7c2e974",
    "SentinelCredit": "hash-47ea0c53777a68d79cf2f66b9171e4a1b588048c283b2b2504fc5ecfe1b686ae",
    "SentinelRegistry": "hash-d97d1f1ef30bf765fbf13aa11817fea409b67056dd59faf6de28c94ad85a5f82",
    "SentinelAlertLog": "hash-f75ce1bc111d185c39d7c81d5a18b093749643957b8c3ba3309613401fb14b78",
    "AgentBehaviorIndex": "hash-d888dc3696046633582f1355f9708dfbd5acde3528466a562fa0601ad6eacbd2",
    "RiskPolicyManager": "hash-aaf7f48dbcdbd59996b9b181c7980bb6c5116a7c72005ce169b1619d94d7b2c4",
    "SubscriberVault": "hash-68c4b7cca84982833af3f9346a5a9ea337bfdcd20875bd82f4c7ec7b1505d211",
}


# ---------------------------------------------------------------------------
# Odra field indices (0 = hidden reentrancy-guard bookkeeping; user fields at 1+)
# ---------------------------------------------------------------------------
FIELD_INDICES: Dict[str, Dict[str, int]] = {
    "AuditTrail": {
        "findings": 1,        # Mapping<u64, Finding>
        "finding_count": 2,   # Var<u64>
        "roles": 3,           # Mapping<Address, u8>
        "role_admin": 4,      # Var<Address>
        "paused": 5,          # Var<bool>
    },
    "RiskOracle": {
        "scores": 1,          # Mapping<String, RiskScore>
        "roles": 2,
        "role_admin": 3,
        "paused": 4,
    },
    "RiskPolicyManager": {
        "current_policy": 1,   # Var<RiskPolicy>
        "policy_history": 2,   # Mapping<u32, RiskPolicy>
        "roles": 3,
        "role_admin": 4,
        "paused": 5,
    },
    "SentinelAlertLog": {
        "logs": 1,             # Mapping<u64, AlertRecord>
        "log_count": 2,        # Var<u64>
        "address_logs": 3,     # Mapping<Address, Vec<u64>>
        "roles": 4,
        "role_admin": 5,
        "paused": 6,
    },
    "SentinelCredit": {
        "accounts": 1,         # Mapping<String, CreditAccount>
        "query_price": 2,      # Var<U512>
        "premium_price": 3,    # Var<U512>
        "total_revenue": 4,    # Var<U512>
        "roles": 5,
        "role_admin": 6,
        "paused": 7,
    },
    "SentinelRegistry": {
        "subscribers": 1,      # Mapping<String, Subscriber>
        "subscriber_count": 2, # Var<u64>
        "roles": 3,
        "role_admin": 4,
        "paused": 5,
    },
    "SubscriberVault": {
        "accounts": 1,         # Mapping<String, VaultAccount>
        "total_locked": 2,     # Var<U512>
        "roles": 3,
        "role_admin": 4,
        "paused": 5,
    },
    "AgentBehaviorIndex": {
        "metrics": 1,          # Mapping<String, AgentMetrics>
        "agent_count": 2,      # Var<u64>
        "roles": 3,
        "role_admin": 4,
        "paused": 5,
    },
}


# ---------------------------------------------------------------------------
# Entry-point metadata — name, role, payable flag, arg schema
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EntryPoint:
    name: str
    role: str  # "public" | "OPERATOR" | "ADMIN" | "PAUSER" | "init"
    payable: bool = False
    args: Dict[str, str] = field(default_factory=dict)
    returns: str = "unit"
    notes: str = ""


@dataclass(frozen=True)
class ContractMeta:
    name: str
    contract_hash: str
    package_hash: str
    summary: str
    entry_points: List[EntryPoint]


# Standard RBAC suite shared by all 8 contracts
def _rbac_suite() -> List[EntryPoint]:
    return [
        EntryPoint("init", "init", args={}, returns="unit", notes="one-time initializer"),
        EntryPoint("grant_role", "ADMIN", args={"account": "address", "role": "u8"}, returns="unit"),
        EntryPoint("revoke_role", "ADMIN", args={"account": "address", "role": "u8"}, returns="unit"),
        EntryPoint("renounce_role", "public", args={"role": "u8"}, returns="unit"),
        EntryPoint("has_role", "public", args={"account": "address", "role": "u8"}, returns="bool"),
        EntryPoint("get_roles", "public", args={"account": "address"}, returns="u8"),
        EntryPoint("get_role_admin", "public", args={}, returns="address"),
        EntryPoint("transfer_role_admin", "ADMIN", args={"new_admin": "address"}, returns="unit"),
        EntryPoint("transfer_ownership", "ADMIN", args={"new_owner": "address"}, returns="unit"),
        EntryPoint("pause", "PAUSER", args={}, returns="unit"),
        EntryPoint("unpause", "PAUSER", args={}, returns="unit"),
        EntryPoint("is_paused", "public", args={}, returns="bool"),
    ]


ENTRY_POINTS: Dict[str, List[EntryPoint]] = {
    "AuditTrail": [
        EntryPoint("record_finding", "OPERATOR",
                   args={"address": "string", "risk_type": "string", "severity": "string",
                         "confidence": "u8", "description": "string", "rwa_enriched": "bool",
                         "agent_model": "string", "block_height": "u64", "timestamp": "u64"},
                   returns="u64", notes="appends a Finding; returns new finding id"),
        EntryPoint("get_finding", "public", args={"id": "u64"}, returns="Finding"),
        EntryPoint("get_count", "public", args={}, returns="u64"),
        *_rbac_suite(),
    ],
    "RiskOracle": [
        EntryPoint("update_score", "OPERATOR",
                   args={"address": "string", "score": "u8", "risk_type": "string",
                         "confidence": "u8", "block_height": "u64", "finding_id": "u64"},
                   returns="unit"),
        EntryPoint("get_risk_score", "public", args={"address": "string"}, returns="Option<RiskScore>"),
        EntryPoint("is_high_risk", "public", args={"address": "string", "threshold": "u8"}, returns="bool"),
        *_rbac_suite(),
    ],
    "RiskPolicyManager": [
        EntryPoint("upgrade_policy", "ADMIN",
                   args={"min_confidence_threshold": "u8", "critical_score_threshold": "u8",
                         "high_score_threshold": "u8", "medium_score_threshold": "u8",
                         "max_retry_count": "u8", "safety_rejection_threshold": "u8",
                         "block_height": "u64", "updated_by": "string"},
                   returns="unit", notes="hot-swap thresholds without redeployment"),
        EntryPoint("get_current_policy", "public", args={}, returns="RiskPolicy"),
        EntryPoint("get_policy_version", "public", args={"version": "u32"}, returns="Option<RiskPolicy>"),
        EntryPoint("get_current_version", "public", args={}, returns="u32"),
        *_rbac_suite(),
    ],
    "SentinelAlertLog": [
        EntryPoint("log_alert", "OPERATOR",
                   args={"subscriber_address": "address", "finding_id": "u64", "severity": "string",
                         "risk_type": "string", "block_height": "u64", "timestamp": "u64",
                         "delivered": "bool"},
                   returns="u64"),
        EntryPoint("get_log", "public", args={"log_id": "u64"}, returns="AlertRecord"),
        EntryPoint("get_address_log_ids", "public", args={"address": "address"}, returns="Vec<u64>"),
        EntryPoint("get_total_count", "public", args={}, returns="u64"),
        *_rbac_suite(),
    ],
    "SentinelCredit": [
        EntryPoint("deposit", "OPERATOR", payable=True,
                   args={"account_address": "string", "amount": "u512"}, returns="unit",
                   notes="payable — attached CSPR must equal amount"),
        EntryPoint("withdraw", "OPERATOR",
                   args={"account_address": "string", "amount": "u512"}, returns="unit"),
        EntryPoint("get_contract_balance", "public", args={}, returns="u512"),
        EntryPoint("deduct_query", "OPERATOR",
                   args={"account_address": "string", "is_premium": "bool"}, returns="bool"),
        EntryPoint("get_balance", "public", args={"account_address": "string"}, returns="u512"),
        EntryPoint("get_account", "public", args={"account_address": "string"}, returns="Option<CreditAccount>"),
        EntryPoint("get_query_price", "public", args={}, returns="u512"),
        EntryPoint("get_premium_price", "public", args={}, returns="u512"),
        EntryPoint("get_total_revenue", "public", args={}, returns="u512"),
        EntryPoint("set_prices", "ADMIN", args={"query_price": "u512", "premium_price": "u512"}, returns="unit"),
        *_rbac_suite(),
    ],
    "SentinelRegistry": [
        EntryPoint("register", "public",
                   args={"address": "string", "webhook_url": "string", "min_severity": "string",
                         "timestamp": "u64"}, returns="unit"),
        EntryPoint("deregister", "public", args={"address": "string"}, returns="unit"),
        EntryPoint("increment_alert_count", "OPERATOR", args={"address": "string"}, returns="unit"),
        EntryPoint("get_subscriber", "public", args={"address": "string"}, returns="Option<Subscriber>"),
        EntryPoint("is_active", "public", args={"address": "string"}, returns="bool"),
        EntryPoint("get_count", "public", args={}, returns="u64"),
        *_rbac_suite(),
    ],
    "SubscriberVault": [
        EntryPoint("open_vault", "OPERATOR", payable=True,
                   args={"subscriber_address": "string", "initial_deposit": "u512",
                         "lock_blocks": "u64", "auto_renew": "bool",
                         "monthly_spend_limit": "u512", "current_block": "u64"},
                   returns="unit",
                   notes="payable — attached CSPR must equal initial_deposit"),
        EntryPoint("withdraw", "OPERATOR",
                   args={"subscriber_address": "string", "amount": "u512", "current_block": "u64"},
                   returns="unit"),
        EntryPoint("get_contract_balance", "public", args={}, returns="u512"),
        EntryPoint("deduct", "OPERATOR",
                   args={"subscriber_address": "string", "amount": "u512"}, returns="bool"),
        EntryPoint("top_up", "OPERATOR", payable=True,
                   args={"subscriber_address": "string", "amount": "u512"}, returns="unit",
                   notes="payable — attached CSPR must equal amount"),
        EntryPoint("get_account", "public", args={"subscriber_address": "string"}, returns="Option<VaultAccount>"),
        EntryPoint("get_balance", "public", args={"subscriber_address": "string"}, returns="u512"),
        EntryPoint("get_total_locked", "public", args={}, returns="u512"),
        *_rbac_suite(),
    ],
    "AgentBehaviorIndex": [
        EntryPoint("record_decision", "OPERATOR",
                   args={"agent_name": "string", "confidence": "u8",
                         "correction_applied": "bool", "safety_rejected": "bool",
                         "block_height": "u64"},
                   returns="unit", notes="recomputes trust_score on-chain"),
        EntryPoint("get_metrics", "public", args={"agent_name": "string"}, returns="Option<AgentMetrics>"),
        EntryPoint("get_trust_score", "public", args={"agent_name": "string"}, returns="u8"),
        EntryPoint("get_agent_count", "public", args={}, returns="u64"),
        *_rbac_suite(),
    ],
}

_CONTRACT_SUMMARIES = {
    "AuditTrail": "Immutable on-chain log of every agent-recorded risk finding.",
    "RiskOracle": "Open risk-score oracle — any Casper protocol can read risk for an address.",
    "SentinelCredit": "x402 prepaid credit ledger for pay-per-query intelligence billing.",
    "SentinelRegistry": "Subscriber registry for push-alert delivery + min-severity filters.",
    "SentinelAlertLog": "Compliance-grade timestamped alert history per subscriber address.",
    "AgentBehaviorIndex": "On-chain AI agent accountability — decisions, corrections, trust score.",
    "RiskPolicyManager": "Hot-swappable risk thresholds — live governance without redeployment.",
    "SubscriberVault": "Escrowed prepay vault for bulk x402 subscriptions with lock periods.",
}

CONTRACTS: Dict[str, ContractMeta] = {
    name: ContractMeta(
        name=name,
        contract_hash=CONTRACT_HASHES[name],
        package_hash=CONTRACT_PACKAGE_HASHES[name],
        summary=_CONTRACT_SUMMARIES[name],
        entry_points=ENTRY_POINTS[name],
    )
    for name in CONTRACT_HASHES
}


# ---------------------------------------------------------------------------
# Lookup helpers (with env-var override for testnet redeploy flexibility)
# ---------------------------------------------------------------------------
def get_contract_hash(name: str) -> str:
    """Return the live contract-version hash (64 hex, no prefix)."""
    env_key = f"{name.upper()}_HASH"
    return os.getenv(env_key, CONTRACT_HASHES[name])


def get_package_hash(name: str) -> str:
    """Return the contract package hash (with ``hash-`` prefix)."""
    env_key = f"{name.upper()}_PACKAGE_HASH"
    return os.getenv(env_key, CONTRACT_PACKAGE_HASHES[name])


def get_field_index(contract: str, field: str) -> int:
    """Return the Odra field index for ``field`` on ``contract``."""
    return FIELD_INDICES[contract][field]


def list_contracts() -> List[Dict[str, object]]:
    """Return a JSON-serialisable summary of every contract."""
    return [
        {
            "name": c.name,
            "contract_hash": c.contract_hash,
            "package_hash": c.package_hash,
            "summary": c.summary,
            "entry_points": [
                {
                    "name": ep.name,
                    "role": ep.role,
                    "payable": ep.payable,
                    "args": ep.args,
                    "returns": ep.returns,
                    "notes": ep.notes,
                }
                for ep in c.entry_points
            ],
        }
        for c in CONTRACTS.values()
    ]
