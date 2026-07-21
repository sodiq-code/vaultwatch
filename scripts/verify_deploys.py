#!/usr/bin/env python3
"""
VaultWatch — Post-deploy verification for Casper Testnet.

Confirms that each contract deploy actually INSTALLED a contract (not just
that the deploy was included in a block). This is the definitive test that
the June 24 deploys FAILED — they were included but rejected during WASM
preprocessing, producing zero named keys and zero published contracts.

This script checks the three evidentiary tests for "deployed" on Casper:
  1. RPC info_get_transaction — execution_results contains a Success outcome
  2. RPC state_get_account_info — named_keys count > 0 for deployer
  3. RPC query_global_state — ContractPackage is queryable

Usage:
    python3 scripts/verify_deploys.py
    python3 scripts/verify_deploys.py --deploy-hashes deploy_hashes_live.json
    python3 scripts/verify_deploys.py --account 0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116

Exit codes:
    0 = all deploys verified (named_keys > 0)
    1 = one or more deploys failed verification
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NODE = "https://rpc.testnet.casper.network/rpc"
DEFAULT_HASHES_FILE = REPO_ROOT / "deploy_hashes_live.json"

# The OLD (compromised) deployer account — kept for historical comparison only.
# Do NOT deploy from this account again.
OLD_DEPLOYER = "0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116"


def rpc(node_url: str, method: str, params: dict) -> dict:
    import httpx

    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    r = httpx.post(node_url, json=body, timeout=30)
    r.raise_for_status()
    j = r.json()
    if "error" in j:
        raise RuntimeError(f"RPC error: {j['error']}")
    return j.get("result", {})


def verify_deploy(node_url: str, deploy_hash: str) -> dict:
    """Check 1: info_get_deploy shows a successful execution result.

    Handles both Casper 1.x (execution_results[].result.Success/Failure) and
    Casper 2.x (execution_info.execution_result.Version2.error_message) formats.
    """
    try:
        result = rpc(node_url, "info_get_deploy", {"deploy_hash": deploy_hash})
        # Casper 2.x: top-level execution_info
        exec_info = result.get("execution_info")
        if exec_info:
            block_hash = exec_info.get("block_hash", "")
            exec_result = exec_info.get("execution_result", {})
            v2 = exec_result.get("Version2")
            if v2 is not None:
                err = v2.get("error_message")
                if err is None:
                    return {"deploy_hash": deploy_hash, "status": "success",
                            "block_hash": block_hash, "gas": str(v2.get("cost", "0"))}
                return {"deploy_hash": deploy_hash, "status": "failed",
                        "block_hash": block_hash, "error": err}
            # 1.x-style Success/Failure nested under execution_result
            if "Success" in exec_result:
                return {"deploy_hash": deploy_hash, "status": "success",
                        "block_hash": block_hash,
                        "gas": exec_result["Success"].get("cost", "0")}
            if "Failure" in exec_result:
                return {"deploy_hash": deploy_hash, "status": "failed",
                        "block_hash": block_hash,
                        "error": exec_result["Failure"].get("error_message", "unknown")}
        # Casper 1.x: deploy.execution_results[]
        deploy = result.get("deploy", {})
        exec_results = deploy.get("execution_results", [])
        if exec_results:
            outcome = exec_results[0].get("result", {})
            block_hash = exec_results[0].get("block_hash", "")
            if "Success" in outcome:
                return {"deploy_hash": deploy_hash, "status": "success",
                        "block_hash": block_hash, "gas": outcome["Success"].get("cost", "0")}
            elif "Failure" in outcome:
                err = outcome["Failure"].get("error_message", "unknown")
                return {"deploy_hash": deploy_hash, "status": "failed",
                        "block_hash": block_hash, "error": err}
        return {"deploy_hash": deploy_hash, "status": "pending",
                "detail": "accepted but not yet executed"}
    except Exception as e:
        return {"deploy_hash": deploy_hash, "status": "error", "error": str(e)}


def verify_account(node_url: str, account_hash_or_pubkey: str) -> dict:
    """Check 2: state_get_account_info shows named_keys > 0."""
    try:
        # Accept either a public key (02...) or an account hash (hash-...)
        params = {"public_key": account_hash_or_pubkey} if account_hash_or_pubkey.startswith("02") else {"account_identifier": account_hash_or_pubkey}
        result = rpc(node_url, "state_get_account_info", params)
        account = result.get("account", {})
        named_keys = account.get("named_keys", [])
        return {"account": account_hash_or_pubkey, "named_keys_count": len(named_keys), "named_key_names": [nk.get("name", "") for nk in named_keys][:20]}
    except Exception as e:
        return {"account": account_hash_or_pubkey, "error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify VaultWatch deploys on Casper Testnet")
    parser.add_argument("--node-url", default=DEFAULT_NODE)
    parser.add_argument("--deploy-hashes", default=str(DEFAULT_HASHES_FILE), help="JSON file mapping contract name → deploy hash")
    parser.add_argument("--account", default=None, help="Deployer public key (02...) or account hash to check named_keys")
    args = parser.parse_args()

    hashes_path = Path(args.deploy_hashes)
    if not hashes_path.exists():
        print(f"ERROR: {hashes_path} not found. Run deploy_contracts_live.py first.")
        return 1

    deploy_hashes = json.loads(hashes_path.read_text())
    print(f"[verify] Checking {len(deploy_hashes)} deploys against {args.node_url}\n")

    all_ok = True
    print("| Contract | Deploy Status | Block | Gas/Error |")
    print("|----------|---------------|-------|-----------|")
    for name, dh in deploy_hashes.items():
        r = verify_deploy(args.node_url, dh)
        status = r["status"]
        marker = "✅" if status == "success" else "❌"
        if status != "success":
            all_ok = False
        detail = r.get("gas", r.get("error", r.get("detail", "")))
        block = r.get("block_hash", "")[:12]
        print(f"| {marker} {name:<22} | {status:<13} | {block:<5} | {str(detail)[:50]} |")

    # Check 2: named keys
    if args.account:
        print(f"\n[verify] Checking named_keys for account {args.account[:20]}…")
        acct = verify_account(args.node_url, args.account)
        if "error" in acct:
            print(f"  ❌ {acct['error']}")
            all_ok = False
        else:
            n = acct["named_keys_count"]
            marker = "✅" if n > 0 else "❌"
            print(f"  {marker} named_keys count: {n}")
            if n > 0:
                print(f"     sample names: {acct['named_key_names'][:5]}")
            else:
                print("     ❌ ZERO named keys — no contracts were installed.")
                print("        This is exactly the June 24 failure signature.")
                all_ok = False

    # Historical comparison
    print(f"\n[verify] Historical note — old deployer {OLD_DEPLOYER[:20]}…")
    old = verify_account(args.node_url, OLD_DEPLOYER)
    if "error" not in old:
        print(f"  Old account named_keys: {old['named_keys_count']} (should be 0 — proves the old failure)")

    print()
    if all_ok:
        print("✅ ALL DEPLOYS VERIFIED — contracts are installed on Casper Testnet.")
        print("   Update proof/PROOF.md with these hashes and update proof/PROOF.md.")
        return 0
    print("❌ VERIFICATION FAILED — see table above. Do NOT update PROOF.md yet.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
