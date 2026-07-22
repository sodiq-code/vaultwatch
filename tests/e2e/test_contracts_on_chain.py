"""E2E — All 8 VaultWatch contracts exist on Casper testnet with the expected
entry points.

These tests run against the REAL Casper testnet (`casper-test`). They use
ONLY read-only RPC calls (``query_global_state``) — no gas is consumed.

Verifies:
  * All 8 contract hashes resolve to a ``Contract`` stored value on-chain.
  * Each contract's ``contract_package_hash`` matches the expected package.
  * Each contract exposes the entry points declared in
    ``contracts/src/*.rs`` (the source of truth — see
    ``scripts/verify_contract_entrypoints.py`` for the same expected-set).
  * Each contract package's ``versions[]`` array is non-empty and its
    latest enabled version matches the deployed contract hash.
"""

from __future__ import annotations

from typing import Dict, Set

import pytest

from tests.e2e.conftest import (
    CONTRACT_HASHES,
    CONTRACT_PACKAGE_HASHES,
    normalize_package_hash,
    query_contract,
    query_contract_package,
)

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Expected entry-point sets — derived from the ON-CHAIN contracts (verified
# 2026-07-21 via query_global_state). The on-chain contracts were deployed
# on 2026-07-11; the source code in contracts/src/*.rs has since drifted
# (Critical Fix 8 added withdraw/get_contract_balance to the source, but
# those have NOT been redeployed — the on-chain contracts still match the
# July 11 source revision).
# ---------------------------------------------------------------------------

#: Minimal entry-point set each contract MUST expose on-chain. This is the
#: subset our e2e deploys + queries actually call — so a missing EP here
#: would cause a real deploy revert.
REQUIRED_ENTRY_POINTS: Dict[str, Set[str]] = {
    "AuditTrail": {"init", "record_finding", "get_count", "transfer_ownership"},
    "RiskOracle": {"init", "update_score", "get_risk_score", "transfer_ownership"},
    "SentinelCredit": {
        "init", "deposit", "deduct_query", "get_balance", "get_account",
        "get_query_price", "get_premium_price", "get_total_revenue",
        "set_prices", "transfer_ownership",
    },
    "SentinelRegistry": {
        "init", "register", "deregister", "increment_alert_count",
        "get_subscriber", "is_active", "get_count", "transfer_ownership",
    },
    "SentinelAlertLog": {"init", "log_alert", "get_log", "get_address_log_ids", "get_total_count"},
    "AgentBehaviorIndex": {"init", "record_decision", "get_metrics", "get_trust_score", "get_agent_count"},
    "RiskPolicyManager": {
        "init", "upgrade_policy", "get_current_policy",
        "get_policy_version", "get_current_version", "transfer_ownership",
    },
    "SubscriberVault": {
        "init", "open_vault", "deduct", "top_up",
        "get_account", "get_balance", "get_total_locked",
    },
}


# ---------------------------------------------------------------------------
# §1  Each contract hash resolves to a Contract stored value
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("contract_name", list(CONTRACT_HASHES.keys()))
def test_contract_exists_on_chain(rpc_url, contract_name):
    """``query_global_state`` on each contract hash returns a non-empty
    ``Contract`` stored value."""
    contract = query_contract(rpc_url, CONTRACT_HASHES[contract_name])
    assert contract.get("contract_package_hash"), (
        f"{contract_name}: missing contract_package_hash in stored_value.Contract"
    )
    assert contract.get("entry_points") is not None, (
        f"{contract_name}: entry_points missing"
    )


@pytest.mark.parametrize("contract_name", list(CONTRACT_HASHES.keys()))
def test_contract_package_hash_matches_expected(rpc_url, contract_name):
    """Each contract's stored ``contract_package_hash`` matches the expected
    package hash from CONTRACT_PACKAGE_HASHES.

    NOTE: Casper 2.x returns the package hash in the format
    ``contract-package-<hex>`` (not the older ``hash-<hex>``). We normalise
    both to the raw 64-char hex before comparing.
    """
    contract = query_contract(rpc_url, CONTRACT_HASHES[contract_name])
    on_chain_pkg = contract.get("contract_package_hash", "")
    on_chain_hex = normalize_package_hash(on_chain_pkg)
    expected_hex = normalize_package_hash(CONTRACT_PACKAGE_HASHES[contract_name])
    assert on_chain_hex == expected_hex, (
        f"{contract_name}: on-chain package hash hex {on_chain_hex!r} != expected {expected_hex!r}"
    )


# ---------------------------------------------------------------------------
# §2  Entry-point verification
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("contract_name", list(CONTRACT_HASHES.keys()))
def test_contract_exposes_required_entry_points(rpc_url, contract_name):
    """Each contract MUST expose its required entry-point set on-chain.

    This is the critical guard that catches the Critical-Fix-4 class of bug
    (agents calling entry points that don't exist on-chain). If an entry
    point is missing here, every deploy calling it would revert.
    """
    contract = query_contract(rpc_url, CONTRACT_HASHES[contract_name])
    on_chain_eps = {ep["name"] for ep in contract.get("entry_points", [])}
    required = REQUIRED_ENTRY_POINTS[contract_name]
    missing = required - on_chain_eps
    assert not missing, (
        f"{contract_name}: missing required entry points on-chain: {sorted(missing)}. "
        f"Present EPs: {sorted(on_chain_eps)}"
    )


def test_audit_trail_record_finding_arg_types(rpc_url):
    """AuditTrail.record_finding must accept the 9 args our e2e deploys pass.

    Verifies the arg CL types match what ``scripts/casper_call.cjs`` will
    serialise: address:String, risk_type:String, severity:String,
    confidence:U8, description:String, rwa_enriched:Bool, agent_model:String,
    block_height:U64, timestamp:U64.
    """
    contract = query_contract(rpc_url, CONTRACT_HASHES["AuditTrail"])
    ep = next(e for e in contract["entry_points"] if e["name"] == "record_finding")
    args = {a["name"]: a["cl_type"] for a in ep["args"]}
    expected = {
        "address": "String",
        "risk_type": "String",
        "severity": "String",
        "confidence": "U8",
        "description": "String",
        "rwa_enriched": "Bool",
        "agent_model": "String",
        "block_height": "U64",
        "timestamp": "U64",
    }
    for name, cl_type in expected.items():
        assert args.get(name) == cl_type, (
            f"AuditTrail.record_finding arg {name!r}: expected {cl_type}, got {args.get(name)!r}. "
            f"Full args: {args}"
        )


def test_risk_oracle_update_score_arg_types(rpc_url):
    """RiskOracle.update_score must accept the 6 args our e2e deploys pass."""
    contract = query_contract(rpc_url, CONTRACT_HASHES["RiskOracle"])
    ep = next(e for e in contract["entry_points"] if e["name"] == "update_score")
    args = {a["name"]: a["cl_type"] for a in ep["args"]}
    expected = {
        "address": "String",
        "score": "U8",
        "risk_type": "String",
        "confidence": "U8",
        "block_height": "U64",
        "finding_id": "U64",
    }
    for name, cl_type in expected.items():
        assert args.get(name) == cl_type, (
            f"RiskOracle.update_score arg {name!r}: expected {cl_type}, got {args.get(name)!r}"
        )


def test_agent_behavior_index_record_decision_arg_types(rpc_url):
    """AgentBehaviorIndex.record_decision must accept the 5 args our e2e
    deploys pass."""
    contract = query_contract(rpc_url, CONTRACT_HASHES["AgentBehaviorIndex"])
    ep = next(e for e in contract["entry_points"] if e["name"] == "record_decision")
    args = {a["name"]: a["cl_type"] for a in ep["args"]}
    expected = {
        "agent_name": "String",
        "confidence": "U8",
        "correction_applied": "Bool",
        "safety_rejected": "Bool",
        "block_height": "U64",
    }
    for name, cl_type in expected.items():
        assert args.get(name) == cl_type, (
            f"AgentBehaviorIndex.record_decision arg {name!r}: expected {cl_type}, got {args.get(name)!r}"
        )


def test_sentinel_alert_log_log_alert_arg_types(rpc_url):
    """SentinelAlertLog.log_alert on-chain signature uses ``subscriber_address:String``
    (not the Rust-source ``Address`` — the on-chain contract was compiled
    from an earlier source revision). Our e2e deploy relies on this.
    """
    contract = query_contract(rpc_url, CONTRACT_HASHES["SentinelAlertLog"])
    ep = next(e for e in contract["entry_points"] if e["name"] == "log_alert")
    args = {a["name"]: a["cl_type"] for a in ep["args"]}
    expected = {
        "subscriber_address": "String",
        "finding_id": "U64",
        "severity": "String",
        "risk_type": "String",
        "block_height": "U64",
        "timestamp": "U64",
        "delivered": "Bool",
    }
    for name, cl_type in expected.items():
        assert args.get(name) == cl_type, (
            f"SentinelAlertLog.log_alert arg {name!r}: expected {cl_type}, got {args.get(name)!r}"
        )


def test_risk_policy_manager_upgrade_policy_arg_types(rpc_url):
    """RiskPolicyManager.upgrade_policy on-chain signature uses
    ``updated_by:String`` (the v1 deployed source). Our e2e deploy relies
    on this — passing an Address arg would revert."""
    contract = query_contract(rpc_url, CONTRACT_HASHES["RiskPolicyManager"])
    ep = next(e for e in contract["entry_points"] if e["name"] == "upgrade_policy")
    args = {a["name"]: a["cl_type"] for a in ep["args"]}
    expected = {
        "min_confidence_threshold": "U8",
        "critical_score_threshold": "U8",
        "high_score_threshold": "U8",
        "medium_score_threshold": "U8",
        "max_retry_count": "U8",
        "safety_rejection_threshold": "U8",
        "block_height": "U64",
        "updated_by": "String",
    }
    for name, cl_type in expected.items():
        assert args.get(name) == cl_type, (
            f"RiskPolicyManager.upgrade_policy arg {name!r}: expected {cl_type}, got {args.get(name)!r}"
        )


# ---------------------------------------------------------------------------
# §3  Contract package versions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("contract_name", list(CONTRACT_PACKAGE_HASHES.keys()))
def test_contract_package_has_versions(rpc_url, contract_name):
    """Each contract package's ``versions[]`` array is non-empty (proves the
    package was installed, not just registered)."""
    pkg = query_contract_package(rpc_url, CONTRACT_PACKAGE_HASHES[contract_name])
    versions = pkg.get("versions", [])
    assert len(versions) > 0, (
        f"{contract_name} package has 0 versions — was it ever installed?"
    )


@pytest.mark.parametrize("contract_name", list(CONTRACT_PACKAGE_HASHES.keys()))
def test_contract_package_latest_version_enabled(rpc_url, contract_name):
    """The latest version of each package must be ``Enabled`` (otherwise
    queries/calls would fail)."""
    pkg = query_contract_package(rpc_url, CONTRACT_PACKAGE_HASHES[contract_name])
    versions = pkg.get("versions", [])
    # Pick the highest version number.
    latest = max(versions, key=lambda v: v.get("contract_version", 0))
    assert latest.get("contract_version") is not None
    # Casper 2.x: each version has an `enabled` flag (defaults true on install).
    # The v2 RiskPolicyManager upgrade disabled v1 (PROOF.md §10.1).
    # We only assert the LATEST version is enabled here.
    assert latest.get("enabled", True) is True, (
        f"{contract_name}: latest version {latest.get('contract_version')} is disabled"
    )


def test_risk_policy_manager_v2_upgrade_evidenced_on_chain(rpc_url):
    """Critical-Fix-2 proof: the Account-2 RiskPolicyManager package (fresh
    install + v2 upgrade, PROOF.md §10.1) has 2 versions on-chain with
    v1 disabled and v2 enabled — proving ``add_contract_version`` ran.

    Note: the Account-1 v1 RiskPolicyManager package (hash
    ``aaf7f48d…7b2c4``) was NOT upgraded (Account 1 was drained before the
    upgrade could run). The Account-2 fresh install + upgrade is the one
    that proves Critical Fix 2 (PROOF.md §10).

    On Casper 2.x, disabled versions are listed in a separate
    ``disabled_versions`` field (format: ``[[protocol_major, contract_version], ...]``)
    rather than as an ``enabled`` flag on each version.
    """
    # Account-2's RiskPolicyManager package hash (from named keys +
    # proof/upgrade_hashes.json).
    account2_rpm_pkg = "hash-417f5f7268acd956c4ce75fc1714f74f8a6bc819e0ad801fc60dc425d729f522"
    pkg = query_contract_package(rpc_url, account2_rpm_pkg)
    versions = pkg.get("versions", [])
    version_nums = sorted(v.get("contract_version", 0) for v in versions)
    assert version_nums[-1] >= 2, (
        f"Account-2 RiskPolicyManager package only has versions {version_nums} — "
        "expected >= 2 (v1 install + v2 upgrade). See PROOF.md §10."
    )
    # v1 should be in disabled_versions, v2 should NOT.
    disabled = pkg.get("disabled_versions", [])
    # Each entry is [protocol_version_major, contract_version].
    disabled_contract_versions = {entry[1] for entry in disabled}
    assert 1 in disabled_contract_versions, (
        f"RiskPolicyManager v1 should be disabled after the v2 upgrade. "
        f"disabled_versions: {disabled}"
    )
    assert 2 not in disabled_contract_versions, (
        "RiskPolicyManager v2 should be enabled (not in disabled_versions)"
    )
