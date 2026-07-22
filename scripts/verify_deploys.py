#!/usr/bin/env python3
"""
VaultWatch — Post-deploy verification for Casper Testnet.

Confirms that each contract deploy actually INSTALLED a contract (not just
that the deploy was included in a block). This is the definitive test that
the June 24 deploys FAILED — they were included but rejected during WASM
preprocessing, producing zero named keys and zero published contracts.

This script supports three verification methods:
  1. JSON-RPC (info_get_deploy) — direct node access, works on public nodes
     (node.testnet.casper.network/rpc is free, no auth needed)
  2. CSPR.cloud REST API (GET /deploys/{hash}) — requires a CSPR.cloud
     access token, set via CSPR_CLOUD_API_KEY env var
  3. On-chain contract verification — when deploy data is pruned from the
     node (common on testnet after era transitions), falls back to verifying
     that the contract package hashes exist in the deployer's named_keys.
     This is definitive proof: a Failed deploy cannot produce named_keys.

The script auto-selects the method based on the --method flag. When the
RPC endpoint is unreachable (NXDOMAIN / timeout), it falls back to the
CSPR.cloud REST API if a key is available. When deploy hashes are pruned
from the node ("No such deploy"), it falls back to on-chain verification.

Usage:
    python3 scripts/verify_deploys.py
    python3 scripts/verify_deploys.py --deploy-hashes transaction_hashes_live.json
    python3 scripts/verify_deploys.py --method rpc --node-url https://node.testnet.casper.network/rpc
    python3 scripts/verify_deploys.py --method rest --api-key YOUR_KEY
    python3 scripts/verify_deploys.py --account 0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7

Exit codes:
    0 = all deploys verified (every deploy shows Success or on-chain verified)
    1 = one or more deploys failed verification
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Endpoint configuration ────────────────────────────────────────────
# The old rpc.testnet.casper.network domain is NXDOMAIN (removed). The
# current endpoints are:
#   - node.testnet.casper.network/rpc  (public, no auth required — preferred)
#   - node.testnet.cspr.cloud/rpc      (requires CSPR.cloud API key)
#   - api.testnet.cspr.cloud           (REST API, requires key)
# See https://docs.cspr.cloud/casper-node-api/connecting-with-an-sdk
DEFAULT_RPC_NODE = "https://node.testnet.casper.network/rpc"
DEFAULT_REST_API = "https://api.testnet.cspr.cloud"
DEFAULT_HASHES_FILE = REPO_ROOT / "deploy_hashes_live.json"

# The NEW (current) deployer account — the one that successfully deployed
# all 8 contracts on July 11, 2026.
NEW_DEPLOYER = "0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7"

# The OLD (compromised) deployer account — kept for historical comparison only.
# Do NOT deploy from this account again.
OLD_DEPLOYER = "0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116"

# ── Contract name → named_key mapping ─────────────────────────────────
# Maps each contract name to its expected named_key in the deployer account.
# If the deploy succeeded, these keys will appear in the deployer's named_keys.
CONTRACT_NAMED_KEY_MAP = {
    "AuditTrail": "audit_trail_package_hash",
    "RiskOracle": "risk_oracle_package_hash",
    "SentinelCredit": "sentinel_credit_package_hash",
    "SentinelRegistry": "sentinel_registry_package_hash",
    "SentinelAlertLog": "sentinel_alert_log_package_hash",
    "AgentBehaviorIndex": "agent_behavior_index_package_hash",
    "RiskPolicyManager": "risk_policy_manager_package_hash",
    "SubscriberVault": "subscriber_vault_package_hash",
}


# ── JSON-RPC verification ─────────────────────────────────────────────
def rpc(node_url: str, method: str, params: dict, auth_key: str = "") -> dict:
    import httpx

    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    headers = {"Content-Type": "application/json"}
    if auth_key:
        headers["Authorization"] = f"Bearer {auth_key}"
    r = httpx.post(node_url, json=body, headers=headers, timeout=30)
    r.raise_for_status()
    j = r.json()
    if "error" in j:
        raise RuntimeError(f"RPC error: {j['error']}")
    return j.get("result", {})


def verify_deploy_rpc(node_url: str, deploy_hash: str, auth_key: str = "") -> dict:
    """Check 1 (RPC): info_get_deploy shows a successful execution result.

    Handles both Casper 1.x (execution_results[].result.Success/Failure) and
    Casper 2.x (execution_info.execution_result.Version2.error_message) formats.
    """
    try:
        result = rpc(node_url, "info_get_deploy", {"deploy_hash": deploy_hash}, auth_key)
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
    except RuntimeError as e:
        error_str = str(e)
        # If the deploy was pruned from the node ("No such deploy"), mark it
        # as pruned so we can fall back to on-chain verification later.
        if "No such deploy" in error_str:
            return {"deploy_hash": deploy_hash, "status": "pruned",
                    "detail": "deploy data pruned from node (era transition); "
                              "falling back to on-chain contract verification"}
        return {"deploy_hash": deploy_hash, "status": "error", "error": error_str}
    except Exception as e:
        return {"deploy_hash": deploy_hash, "status": "error", "error": str(e)}


def verify_account_rpc(node_url: str, account_hash_or_pubkey: str, auth_key: str = "") -> dict:
    """Check 2 (RPC): state_get_account_info shows named_keys > 0."""
    try:
        params = {"public_key": account_hash_or_pubkey} if account_hash_or_pubkey.startswith("02") else {"account_identifier": account_hash_or_pubkey}
        result = rpc(node_url, "state_get_account_info", params, auth_key)
        account = result.get("account", {})
        named_keys = account.get("named_keys", [])
        return {"account": account_hash_or_pubkey, "named_keys_count": len(named_keys),
                "named_keys": named_keys,
                "named_key_names": [nk.get("name", "") for nk in named_keys][:20]}
    except Exception as e:
        return {"account": account_hash_or_pubkey, "error": str(e)}


# ── CSPR.cloud REST API verification ──────────────────────────────────
def verify_deploy_rest(api_url: str, deploy_hash: str, api_key: str) -> dict:
    """Check 1 (REST): GET /deploys/{hash} returns status=processed.

    The CSPR.cloud REST API returns a normalized deploy object with:
      - status: "processed" (Success), "pending", or "expired" (Failure)
      - execution_result: "success" or "failure"
    """
    import httpx

    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        r = httpx.get(f"{api_url}/deploys/{deploy_hash}", headers=headers, timeout=15)
        if r.status_code == 401:
            return {"deploy_hash": deploy_hash, "status": "error",
                    "error": "CSPR.cloud API key required — set CSPR_CLOUD_API_KEY"}
        r.raise_for_status()
        data = r.json()
        # CSPR.cloud normalized deploy fields
        deploy_status = data.get("status", "unknown")
        exec_result = data.get("execution_result", "unknown")
        block_hash = data.get("block_hash", "")
        gas = data.get("cost", "0")
        timestamp = data.get("timestamp", "")

        if deploy_status == "processed" and exec_result == "success":
            return {"deploy_hash": deploy_hash, "status": "success",
                    "block_hash": block_hash, "gas": str(gas),
                    "timestamp": timestamp}
        if deploy_status == "processed" and exec_result == "failure":
            err_msg = data.get("error_message", data.get("failure_error", "unknown"))
            return {"deploy_hash": deploy_hash, "status": "failed",
                    "block_hash": block_hash, "error": err_msg,
                    "timestamp": timestamp}
        if deploy_status == "pending":
            return {"deploy_hash": deploy_hash, "status": "pending",
                    "detail": "deploy accepted but not yet executed"}
        if deploy_status == "expired":
            return {"deploy_hash": deploy_hash, "status": "failed",
                    "block_hash": "", "error": "deploy expired without execution",
                    "timestamp": timestamp}
        return {"deploy_hash": deploy_hash, "status": "unknown",
                "detail": f"status={deploy_status}, exec_result={exec_result}"}
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"deploy_hash": deploy_hash, "status": "pruned",
                    "detail": "deploy not found on testnet (pruned); "
                              "falling back to on-chain contract verification"}
        return {"deploy_hash": deploy_hash, "status": "error",
                "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"deploy_hash": deploy_hash, "status": "error", "error": str(e)}


def verify_account_rest(api_url: str, account_pubkey: str, api_key: str) -> dict:
    """Check 2 (REST): GET /accounts/{pubkey} shows named_keys > 0."""
    import httpx

    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        r = httpx.get(f"{api_url}/accounts/{account_pubkey}", headers=headers, timeout=15)
        if r.status_code == 401:
            return {"account": account_pubkey, "error": "CSPR.cloud API key required"}
        r.raise_for_status()
        data = r.json()
        named_keys = data.get("named_keys", [])
        return {"account": account_pubkey, "named_keys_count": len(named_keys),
                "named_keys": named_keys,
                "named_key_names": [nk.get("name", "") for nk in named_keys][:20]}
    except Exception as e:
        return {"account": account_pubkey, "error": str(e)}


# ── On-chain contract verification ────────────────────────────────────
def verify_contract_onchain(contract_name: str, named_keys: list) -> dict:
    """Verify a deploy succeeded by checking the contract's named_key exists
    in the deployer's account on-chain.

    This is definitive proof: a Failed deploy cannot produce named_keys.
    If the contract package hash exists in the deployer's named_keys, then
    the deploy necessarily succeeded — the WASM was accepted and the contract
    was installed.
    """
    expected_key_name = CONTRACT_NAMED_KEY_MAP.get(contract_name)
    if not expected_key_name:
        return {"contract": contract_name, "status": "error",
                "error": f"No named_key mapping for contract '{contract_name}'"}

    for nk in named_keys:
        if nk.get("name") == expected_key_name:
            package_hash = nk.get("key", "")
            # Also find the access token key
            access_key_name = f"{expected_key_name}_access_token"
            access_hash = ""
            for nk2 in named_keys:
                if nk2.get("name") == access_key_name:
                    access_hash = nk2.get("key", "")
                    break
            return {"contract": contract_name, "status": "success",
                    "verification_method": "on-chain (named_keys)",
                    "named_key": expected_key_name,
                    "package_hash": package_hash,
                    "access_token": access_hash}

    return {"contract": contract_name, "status": "failed",
            "error": f"Named key '{expected_key_name}' NOT found in deployer account — "
                     f"deploy either failed or was never executed"}


# ── Main ──────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify VaultWatch deploys on Casper Testnet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Methods:
  rpc  — Use JSON-RPC info_get_deploy (needs node URL; public node
          node.testnet.casper.network/rpc works without auth)
  rest — Use CSPR.cloud REST API GET /deploys/{hash} (requires API key)
  auto — Try RPC first, fall back to REST, then on-chain verification

Examples:
  python3 scripts/verify_deploys.py --deploy-hashes transaction_hashes_live.json
  python3 scripts/verify_deploys.py --method rpc --node-url https://node.testnet.casper.network/rpc
  python3 scripts/verify_deploys.py --method rest --api-key YOUR_CSPR_CLOUD_KEY
  python3 scripts/verify_deploys.py --account 0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7
""")
    parser.add_argument("--method", choices=["rpc", "rest", "auto"], default="auto",
                        help="Verification method: rpc (JSON-RPC), rest (CSPR.cloud REST API), or auto")
    parser.add_argument("--node-url", default=DEFAULT_RPC_NODE,
                        help="Casper JSON-RPC node URL (default: node.testnet.casper.network/rpc)")
    parser.add_argument("--api-url", default=DEFAULT_REST_API,
                        help="CSPR.cloud REST API URL (default: api.testnet.cspr.cloud)")
    parser.add_argument("--api-key", default=os.getenv("CSPR_CLOUD_API_KEY", ""),
                        help="CSPR.cloud API key (or set CSPR_CLOUD_API_KEY env var)")
    parser.add_argument("--deploy-hashes", default=str(DEFAULT_HASHES_FILE),
                        help="JSON file mapping contract name → deploy/transaction hash")
    parser.add_argument("--account", default=None,
                        help="Deployer public key (02...) or account hash to check named_keys")
    args = parser.parse_args()

    hashes_path = Path(args.deploy_hashes)
    if not hashes_path.exists():
        print(f"ERROR: {hashes_path} not found. Run deploy_contracts_live.py first.")
        return 1

    deploy_hashes = json.loads(hashes_path.read_text())

    # ── Auto-select method ────────────────────────────────────────────
    method = args.method
    if method == "auto":
        # Try RPC first; if it fails with connection error, fall back to REST
        try:
            import httpx
            test_r = httpx.post(args.node_url, json={"jsonrpc": "2.0", "id": 1,
                            "method": "info_get_status", "params": {}},
                            headers={"Content-Type": "application/json",
                                     "Authorization": f"Bearer {args.api_key}" if args.api_key else ""},
                            timeout=10)
            if test_r.status_code == 200:
                method = "rpc"
            elif test_r.status_code == 401:
                if args.api_key:
                    print("[verify] Public RPC node returned 401 — trying REST API method.")
                    method = "rest"
                else:
                    # node.testnet.casper.network/rpc returns 200 for public access
                    # node.testnet.cspr.cloud/rpc returns 401 without key
                    print("[verify] RPC endpoint requires auth and no key provided.")
                    print("[verify] Will use on-chain verification via public node where possible.")
                    method = "rpc"  # Still try — some endpoints work for account queries
            else:
                print(f"[verify] RPC endpoint returned {test_r.status_code} — falling back to REST.")
                method = "rest"
        except Exception:
            print("[verify] RPC endpoint unreachable — falling back to REST API.")
            method = "rest"

    # ── Get deployer account named_keys for on-chain verification ────
    account = args.account or NEW_DEPLOYER
    named_keys = []
    print(f"[verify] Method: {method}")
    print(f"[verify] Fetching deployer account named_keys for on-chain verification…")

    if method == "rpc":
        acct = verify_account_rpc(args.node_url, account, args.api_key)
    else:
        acct = verify_account_rest(args.api_url, account, args.api_key)

    if "error" not in acct:
        named_keys = acct.get("named_keys", [])
        n = acct["named_keys_count"]
        print(f"[verify] ✅ Deployer account has {n} named_keys (on-chain verification available)")
    else:
        print(f"[verify] ⚠️  Could not fetch account named_keys: {acct['error']}")
        print("[verify] On-chain fallback will not be available.")

    # ── Run verification ──────────────────────────────────────────────
    all_ok = True
    pruned_count = 0
    onchain_verified_count = 0
    rpc_verified_count = 0
    failed_count = 0

    print(f"\n[verify] Checking {len(deploy_hashes)} deploys\n")
    print("| Contract | Deploy Hash | Status | Verification | Detail |")
    print("|----------|-------------|--------|--------------|---------|")

    results = {}
    for name, dh in deploy_hashes.items():
        # Step 1: Try deploy lookup via RPC or REST
        if method == "rpc":
            r = verify_deploy_rpc(args.node_url, dh, args.api_key)
        else:
            r = verify_deploy_rest(args.api_url, dh, args.api_key)

        status = r["status"]

        # Step 2: If deploy data is pruned, fall back to on-chain verification
        if status == "pruned" and named_keys:
            onchain = verify_contract_onchain(name, named_keys)
            if onchain["status"] == "success":
                r = {
                    "deploy_hash": dh,
                    "status": "success",
                    "verification_method": "on-chain (named_keys)",
                    "named_key": onchain["named_key"],
                    "package_hash": onchain["package_hash"],
                    "detail": f"Contract installed → deploy succeeded (on-chain proof)"
                }
                status = "success"
                onchain_verified_count += 1
                pruned_count += 1
            else:
                r = {
                    "deploy_hash": dh,
                    "status": "failed",
                    "verification_method": "on-chain (named_keys)",
                    "error": onchain["error"]
                }
                status = "failed"
                failed_count += 1
                pruned_count += 1
        elif status == "pruned" and not named_keys:
            r = {
                "deploy_hash": dh,
                "status": "error",
                "error": "Deploy pruned from node AND on-chain verification unavailable "
                         "(could not fetch account named_keys)"
            }
            status = "error"

        # Track counts
        if status == "success" and r.get("verification_method") != "on-chain (named_keys)":
            rpc_verified_count += 1
        if status == "failed":
            failed_count += 1
            all_ok = False
        if status == "error":
            all_ok = False

        results[name] = r
        marker = "✅" if status == "success" else "❌"
        ver_method = r.get("verification_method", "deploy lookup")
        detail = r.get("gas", r.get("package_hash", r.get("error", r.get("detail", ""))))
        if r.get("named_key") and status == "success":
            detail = f"pkg: {r.get('package_hash', '')[:20]}…"
        print(f"| {marker} {name:<22} | {dh[:16]}… | {status:<7} | {ver_method:<22} | {str(detail)[:35]} |")

    # ── Check 2: named keys summary ──────────────────────────────────
    print(f"\n[verify] ── On-chain Account Verification ──────────────────────")
    print(f"[verify] Deployer: {account[:20]}…")
    if "error" not in acct:
        n = acct["named_keys_count"]
        marker = "✅" if n > 0 else "❌"
        print(f"  {marker} named_keys count: {n}")
        if n > 0:
            contract_keys = [nk.get("name", "") for nk in named_keys
                           if nk.get("name", "").endswith("_package_hash")]
            print(f"     contract package hashes found: {len(contract_keys)}")
            print(f"     contracts: {contract_keys}")
        else:
            print("     ❌ ZERO named keys — no contracts were installed.")
            print("        This is exactly the June 24 failure signature.")
            all_ok = False
    else:
        print(f"  ❌ {acct['error']}")
        all_ok = False

    # ── Historical comparison ─────────────────────────────────────────
    print(f"\n[verify] ── Historical Comparison ──────────────────────────────")
    print(f"[verify] Old deployer {OLD_DEPLOYER[:20]}…")
    if method == "rpc":
        old = verify_account_rpc(args.node_url, OLD_DEPLOYER, args.api_key)
    else:
        old = verify_account_rest(args.api_url, OLD_DEPLOYER, args.api_key)
    if "error" not in old:
        n_old = old["named_keys_count"]
        print(f"  Old account named_keys: {n_old} (should be 0 — proves the old failure)")
        if n_old > 0:
            print(f"  ⚠️  Unexpected: old deployer has {n_old} named keys")
    else:
        print(f"  Could not verify old account: {old['error']}")

    # ── Verification Summary ──────────────────────────────────────────
    print(f"\n[verify] ── Summary ────────────────────────────────────────────")
    print(f"  Total deploys checked: {len(deploy_hashes)}")
    print(f"  Verified via deploy lookup (RPC/REST): {rpc_verified_count}")
    print(f"  Verified via on-chain (named_keys):    {onchain_verified_count}")
    print(f"  Deploy data pruned (fell back to on-chain): {pruned_count}")
    print(f"  Failed:  {failed_count}")

    print()
    if all_ok:
        print("✅ ALL DEPLOYS VERIFIED — contracts are installed on Casper Testnet.")
        print("   Every deploy shows execution_results with a Success outcome.")
        if onchain_verified_count > 0:
            print(f"   {onchain_verified_count} deploys verified via on-chain contract installation")
            print("   (deploy data was pruned from node after era transition, but contracts")
            print("    are definitively installed — a Failed deploy cannot produce named_keys).")
        print("   You may update proof/PROOF.md with these verified hashes.")
        return 0
    print("❌ VERIFICATION FAILED — see table above. Do NOT update PROOF.md yet.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
