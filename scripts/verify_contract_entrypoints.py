#!/usr/bin/env python3
"""
VaultWatch — Verify that contract hashes on-chain expose the expected entry points.

Uses Casper 2.x RPC to query each contract's entry points and confirms
they match what the interaction deploys expect.

Usage:
    python3 scripts/verify_contract_entrypoints.py
    python3 scripts/verify_contract_entrypoints.py --rpc https://node.testnet.cspr.cloud/rpc
"""

from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).parent.parent
DEFAULT_RPC = "https://node.testnet.cspr.cloud/rpc"
# Critical Fix 6: CSPR.cloud token is read from env, NOT hardcoded. The
# previous key was leaked in source control and has been rotated.
DEFAULT_AUTH = os.getenv("CSPR_CLOUD_API_KEY", "")

# Expected entry points per contract (from Odra source analysis).
#
# NOTE (RBAC migration): The on-chain contracts were deployed 2026-07-11 from
# the pre-RBAC single-owner source, so the sets below match the ON-CHAIN
# entry points (the legacy `transfer_ownership` is retained as a backward-compat
# shim). The current source (contracts/src/*.rs) has migrated from single-owner
# to role-based access control (OPERATOR / ADMIN / PAUSER + emergency pause).
# Each contract now ALSO exposes these 10 RBAC entry points, which will appear
# on-chain after the RBAC wasms are redeployed:
#
#   grant_role, revoke_role, renounce_role, has_role, get_roles,
#   get_role_admin, transfer_role_admin, pause, unpause, is_paused
#
# (transfer_ownership is preserved as an ADMIN-gated compat shim that grants
# ROLE_ALL + transfers role_admin.) See CONTRACT_AUDIT.md §3 and contracts/src/rbac.rs.
EXPECTED_ENTRY_POINTS = {
    "AuditTrail": ["init", "record_finding", "get_finding", "get_count", "transfer_ownership"],
    "RiskOracle": ["init", "update_score", "get_risk_score", "is_high_risk", "transfer_ownership"],
    "SentinelCredit": ["init", "deposit", "withdraw", "get_contract_balance",
                       "deduct_query", "get_balance", "get_account",
                       "get_query_price", "get_premium_price", "get_total_revenue",
                       "set_prices", "transfer_ownership"],
    "SentinelRegistry": ["init", "register", "deregister", "increment_alert_count", "get_subscriber", "is_active", "get_count", "transfer_ownership"],
    "SentinelAlertLog": ["init", "log_alert", "get_log", "get_address_log_ids", "get_total_count"],
    "AgentBehaviorIndex": ["init", "record_decision", "get_metrics", "get_trust_score", "get_agent_count"],
    "RiskPolicyManager": ["init", "upgrade_policy", "get_current_policy", "get_policy_version", "get_current_version", "transfer_ownership"],
    "SubscriberVault": ["init", "open_vault", "withdraw", "get_contract_balance",
                        "deduct", "top_up", "get_account", "get_balance", "get_total_locked"],
}

# Contract hashes (verified on-chain July 2026)
CONTRACT_HASHES_FILE = ROOT / "deploy_hashes_live.json"

DEFAULT_CONTRACT_HASHES = {
    "AuditTrail": "cd1579001dcd923888baa9ea44b1df3b816de52ced44682a3042779d1d4d9932",
    "RiskOracle": "234a34a71fb04625971373b06b73ac6dbc5f7d701f7e96621c752d73ccde80ff",
    "SentinelCredit": "993d8947a6c8220539efaea87c7631c9fc45780c674406d48487bcf66fb1cbfb",
    "SentinelRegistry": "9cce03a0e5d1aa3dab07da50afb4cb9eaba29973eb2b1e766cc6724a1e34e31e",
    "SentinelAlertLog": "43f9b7df3f9f808db8b035c13ae0bac0b47335709abeafdc36e6a9bffe9b9322",
    "AgentBehaviorIndex": "1a976fe839366c4399541055245695cf94626b3d99c0f3a6675ae761395d822b",
    "RiskPolicyManager": "1027cb2a989b75d8b29b82cab60a8b12a892138a5704cdd4753a0862f65b1d85",
    "SubscriberVault": "9a93db9c1f315f1ed34ee55e46f65ed28585f9529fb8427aedf937a6ea0d7bd0",
}


def rpc_call(rpc_url, auth, method, params):
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["Authorization"] = auth
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    r = requests.post(rpc_url, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        return {"error": data["error"]}
    return data.get("result", {})


def load_contract_hashes():
    if CONTRACT_HASHES_FILE.exists():
        with open(CONTRACT_HASHES_FILE) as f:
            return json.load(f)
    return dict(DEFAULT_CONTRACT_HASHES)


def main():
    parser = argparse.ArgumentParser(description="Verify VaultWatch contract entry points on Casper testnet")
    parser.add_argument("--rpc", default=DEFAULT_RPC)
    parser.add_argument("--auth", default=DEFAULT_AUTH)
    args = parser.parse_args()

    srh = rpc_call(args.rpc, args.auth, "chain_get_state_root_hash", {}).get("state_root_hash", "")
    if not srh:
        print("ERROR: Could not get state root hash")
        sys.exit(1)

    contract_hashes = load_contract_hashes()
    all_pass = True

    print(f"State root hash: {srh[:20]}...\n")
    print("=" * 80)
    print("CONTRACT ENTRY POINT VERIFICATION")
    print("=" * 80)

    for name, ch in contract_hashes.items():
        expected = set(EXPECTED_ENTRY_POINTS.get(name, []))
        print(f"\n{name} ({ch[:20]}...)")

        # Query contract from global state
        result = rpc_call(args.rpc, args.auth, "query_global_state", {
            "state_identifier": {"StateRootHash": srh},
            "key": f"hash-{ch}",
            "path": [],
        })

        if "error" in result:
            print(f"  ERROR: {result['error']}")
            all_pass = False
            continue

        contract_data = result.get("stored_value", {}).get("Contract", {})
        on_chain_eps = set(ep["name"] for ep in contract_data.get("entry_points", []))

        missing = expected - on_chain_eps
        extra = on_chain_eps - expected

        if not missing and not extra:
            print(f"  PASS - All {len(expected)} expected entry points found")
        else:
            if missing:
                print(f"  MISSING on-chain: {sorted(missing)}")
                all_pass = False
            if extra:
                print(f"  EXTRA on-chain:  {sorted(extra)}")

        print(f"  On-chain entry points ({len(on_chain_eps)}): {sorted(on_chain_eps)}")

    print("\n" + "=" * 80)
    if all_pass:
        print("ALL CONTRACTS VERIFIED - Entry points match expected signatures")
    else:
        print("SOME MISMATCHES FOUND - Review the output above")
        sys.exit(1)


if __name__ == "__main__":
    main()
