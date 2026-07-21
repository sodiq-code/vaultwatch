#!/usr/bin/env python3
"""
VaultWatch — Casper-native Contract Upgrade Demo (Critical Fix 2).

Demonstrates Casper's natively-upgradable smart contracts by installing a **v2**
of `RiskPolicyManager` as a new version under the SAME contract package as v1,
using the Casper host function `storage::add_contract_version(...)` (invoked
automatically by Odra 2.x when the v2 Wasm is deployed as session code with
`odra_cfg_is_upgrade=true`).

v2 is a functional SUPERSET of v1:
  - Same struct fields, same order (shared `state` dictionary -> v2 reads v1 state).
  - All v1 entry points preserved (upgrade_policy, get_current_policy, ...).
  - One new entry point: `get_policy_with_reasoning` (policy + human rationale).

Verification matrix (all on Casper Testnet, via official RPC):
  1. Package now has 2 versions (v1 disabled, v2 active = latest).
  2. v2 contract exposes `get_policy_with_reasoning` (new capability).
  3. v2's `state` URef == v1's `state` URef (shared state, structural proof).
  4. Calling `get_policy_with_reasoning` on v2 SUCCEEDS (new entry point works;
     and because it reads `current_policy` via get_or_revert, success also proves
     v2 can read v1's shared state — a functional proof).
  5. Calling `get_current_policy` on v2 SUCCEEDS (v1 entry point still works on
     the upgraded superset).

Usage:
    python3 scripts/demo_upgrade_contract.py
    python3 scripts/demo_upgrade_contract.py --dry-run   # verification queries only
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RPC = "https://node.testnet.casper.network/rpc"
CHAIN_NAME = "casper-test"

# RiskPolicyManager v1 (verified on-chain, from deploy_hashes_live.json + PROOF.md)
RPM_V1_CONTRACT_HASH = "1027cb2a989b75d8b29b82cab60a8b12a892138a5704cdd4753a0862f65b1d85"
RPM_PACKAGE_HASH = "aaf7f48dbcdbd59996b9b181c7980bb6c5116a7c72005ce169b1619d94d7b2c4"
RPM_PACKAGE_KEY_NAME = "risk_policy_manager_package_hash"
RPM_V1_STATE_UREF = "uref-dca768b2e203f0019a96626d800a7c5c9b0658df56c861346298a61b2b0117bf-007"

V2_WASM = REPO_ROOT / "contracts" / "wasm" / "RiskPolicyManagerV2.wasm"
SECRET_KEY = REPO_ROOT / "secret_key.pem"
UPGRADE_HELPER = REPO_ROOT / "scripts" / "casper_upgrade.cjs"
CALL_HELPER = REPO_ROOT / "scripts" / "casper_deploy.cjs"
PROOF_FILE = REPO_ROOT / "proof" / "upgrade_hashes.json"

UPGRADE_PAYMENT_MOTES = 300_000_000_000   # 300 CSPR (upgrade is heavier than v1's 140 CSPR install; mostly refunded)
CALL_PAYMENT_MOTES = 5_000_000_000        # 5 CSPR (mostly refunded)


def log(msg: str) -> None:
    print(f"[upgrade] {msg}", flush=True)


def rpc_call(rpc_url: str, method: str, params) -> dict:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    r = requests.post(rpc_url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        return {"error": data["error"]}
    return data.get("result", {})


def get_state_root_hash(rpc_url: str) -> str:
    return rpc_call(rpc_url, "chain_get_state_root_hash", {}).get("state_root_hash", "")


def query_package(rpc_url: str, srh: str, package_hash: str) -> dict:
    """Query a contract package -> versions[] + access_key + lock_status."""
    res = rpc_call(rpc_url, "query_global_state", {
        "state_identifier": {"StateRootHash": srh},
        "key": f"hash-{package_hash}",
        "path": [],
    })
    return (res.get("stored_value") or {}).get("ContractPackage", {})


def query_contract(rpc_url: str, srh: str, contract_hash: str) -> dict:
    """Query a contract -> entry_points + named_keys."""
    res = rpc_call(rpc_url, "query_global_state", {
        "state_identifier": {"StateRootHash": srh},
        "key": f"hash-{contract_hash}",
        "path": [],
    })
    return (res.get("stored_value") or {}).get("Contract", {})


def run_node_helper(helper: Path, request: dict) -> dict:
    """Run a Node.js deploy helper with a request.json; return parsed JSON result."""
    req_file = REPO_ROOT / ".upgrade_req.tmp.json"
    req_file.write_text(json.dumps(request))
    try:
        proc = subprocess.run(
            ["node", str(helper), str(req_file)],
            capture_output=True, text=True, timeout=300,
        )
        out = proc.stdout.strip()
        if not out:
            raise RuntimeError(
                f"helper produced no stdout; stderr={proc.stderr[:500]}; exit={proc.returncode}"
            )
        return json.loads(out)
    finally:
        try:
            req_file.unlink()
        except OSError:
            pass


def execute_upgrade(rpc_url: str) -> dict:
    """Deploy the v2 Wasm as session code with odra_cfg_is_upgrade=true."""
    request = {
        "key_path": str(SECRET_KEY),
        "wasm_path": str(V2_WASM),
        "payment_motes": UPGRADE_PAYMENT_MOTES,
        "package_hash": RPM_PACKAGE_HASH,
        "package_hash_key_name": RPM_PACKAGE_KEY_NAME,
        "rpc_url": rpc_url,
    }
    log(f"Deploying v2 Wasm as session code (add_contract_version)...")
    log(f"  v1 package hash: {RPM_PACKAGE_HASH}")
    log(f"  v2 wasm: {V2_WASM.name} ({V2_WASM.stat().st_size} bytes)")
    result = run_node_helper(UPGRADE_HELPER, request)
    if result.get("success"):
        log(f"  ✅ UPGRADE VERIFIED SUCCESS on-chain")
        log(f"     deploy:  {result['deploy_hash']}")
        log(f"     block:   {result['block_hash']}")
        log(f"     cost:    {int(result['cost_motes'])/1e9:.4f} CSPR")
        log(f"     link:    {result['link']}")
    else:
        log(f"  ❌ UPGRADE FAILED: {result.get('error')}")
    return result


def call_entrypoint(rpc_url: str, contract_hash: str, entry_point: str, args: list) -> dict:
    """Call an entry point on a contract (stored-contract call) via casper_deploy.cjs."""
    request = {
        "key_path": str(SECRET_KEY),
        "contract_hash": contract_hash,
        "entry_point": entry_point,
        "payment_motes": CALL_PAYMENT_MOTES,
        "args": args,
        "rpc_url": rpc_url,
    }
    return run_node_helper(CALL_HELPER, request)


def verify(rpc_url: str, upgrade_result: dict | None) -> dict:
    """Run the full on-chain verification matrix. Returns a structured report."""
    srh = get_state_root_hash(rpc_url)
    log(f"State root hash: {srh[:20]}...")

    report = {
        "network": CHAIN_NAME,
        "rpc_url": rpc_url,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "v1_contract_hash": RPM_V1_CONTRACT_HASH,
        "package_hash": RPM_PACKAGE_HASH,
        "upgrade_deploy": None,
        "checks": {},
    }
    if upgrade_result and upgrade_result.get("success"):
        report["upgrade_deploy"] = {
            "deploy_hash": upgrade_result["deploy_hash"],
            "block_hash": upgrade_result["block_hash"],
            "cost_motes": upgrade_result["cost_motes"],
            "link": upgrade_result["link"],
        }

    # --- Check 1: package versions ---
    pkg = query_package(rpc_url, srh, RPM_PACKAGE_HASH)
    versions = pkg.get("versions", [])
    disabled = pkg.get("disabled_versions", [])
    log(f"Check 1 — package versions: {len(versions)} ({[v.get('contract_version') for v in versions]})")
    report["checks"]["package_versions"] = {
        "count": len(versions),
        "versions": versions,
        "disabled_versions": disabled,
        "lock_status": pkg.get("lock_status"),
        "access_key": pkg.get("access_key"),
        "pass": len(versions) >= 2,
    }

    # Identify v2 = the version with the highest contract_version number.
    v2_contract_hash = None
    if versions:
        v2 = max(versions, key=lambda v: v.get("contract_version", 0))
        # strip "contract-" prefix if present
        ch = v2.get("contract_hash", "")
        v2_contract_hash = ch.replace("contract-", "") if ch.startswith("contract-") else ch
        report["v2_contract_hash"] = v2_contract_hash
        log(f"  v2 contract hash (latest version): {v2_contract_hash}")

    # --- Check 2: v2 exposes get_policy_with_reasoning ---
    v2_contract = query_contract(rpc_url, srh, v2_contract_hash) if v2_contract_hash else {}
    v2_eps = {ep["name"] for ep in v2_contract.get("entry_points", [])}
    has_new_ep = "get_policy_with_reasoning" in v2_eps
    log(f"Check 2 — v2 entry points: {len(v2_eps)} | has get_policy_with_reasoning: {has_new_ep}")
    report["checks"]["v2_new_entry_point"] = {
        "v2_entry_points": sorted(v2_eps),
        "has_get_policy_with_reasoning": has_new_ep,
        "pass": has_new_ep,
    }

    # v2 must also preserve all v1 entry points (superset)
    v1_eps_expected = {
        "init", "upgrade_policy", "get_current_policy", "get_policy_version",
        "get_current_version", "transfer_ownership",
    }
    v1_preserved = v1_eps_expected.issubset(v2_eps)
    report["checks"]["v1_entry_points_preserved_in_v2"] = {
        "expected": sorted(v1_eps_expected),
        "preserved": v1_preserved,
        "pass": v1_preserved,
    }
    log(f"  v1 entry points preserved in v2: {v1_preserved}")

    # --- Check 3: shared state — v2's `state` URef == v1's `state` URef ---
    def state_uref_of(contract: dict) -> str | None:
        for nk in contract.get("named_keys", []):
            if nk.get("name") == "state":
                return nk.get("key")
        return None

    v2_state_uref = state_uref_of(v2_contract)
    shared_state = bool(v2_state_uref) and v2_state_uref == RPM_V1_STATE_UREF
    log(f"Check 3 — shared state URef: v1={RPM_V1_STATE_UREF} v2={v2_state_uref} -> {shared_state}")
    report["checks"]["shared_state_uref"] = {
        "v1_state_uref": RPM_V1_STATE_UREF,
        "v2_state_uref": v2_state_uref,
        "shared": shared_state,
        "pass": shared_state,
    }

    # --- Checks 4 & 5: call entry points on v2 (only if upgrade was executed) ---
    if upgrade_result is not None and v2_contract_hash:
        # Check 4: get_policy_with_reasoning (v2-only) — success proves new EP works
        # AND that v2 reads v1's shared state (get_or_revert would fail otherwise).
        log(f"Check 4 — calling get_policy_with_reasoning on v2...")
        r4 = call_entrypoint(rpc_url, v2_contract_hash, "get_policy_with_reasoning", [])
        log(f"  -> success={r4.get('success')} cost={r4.get('cost_motes')}")
        report["checks"]["call_get_policy_with_reasoning_on_v2"] = {
            "deploy_hash": r4.get("deploy_hash"),
            "link": r4.get("link"),
            "success": r4.get("success"),
            "error": r4.get("error"),
            "pass": bool(r4.get("success")),
        }

        # Check 5: get_current_policy on v2 — v1 entry point still works on the superset.
        log(f"Check 5 — calling get_current_policy on v2 (v1 entry point on upgraded package)...")
        r5 = call_entrypoint(rpc_url, v2_contract_hash, "get_current_policy", [])
        log(f"  -> success={r5.get('success')} cost={r5.get('cost_motes')}")
        report["checks"]["call_get_current_policy_on_v2"] = {
            "deploy_hash": r5.get("deploy_hash"),
            "link": r5.get("link"),
            "success": r5.get("success"),
            "error": r5.get("error"),
            "pass": bool(r5.get("success")),
        }
    else:
        report["checks"]["call_get_policy_with_reasoning_on_v2"] = {"skipped": True}
        report["checks"]["call_get_current_policy_on_v2"] = {"skipped": True}

    # --- Overall verdict ---
    checks = report["checks"]
    actionable = [k for k, v in checks.items() if isinstance(v, dict) and "pass" in v]
    report["all_pass"] = all(checks[k]["pass"] for k in actionable)
    report["checks_run"] = len(actionable)
    report["checks_passed"] = sum(1 for k in actionable if checks[k]["pass"])

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="VaultWatch Casper-native contract upgrade demo (Critical Fix 2).")
    parser.add_argument("--rpc", default=DEFAULT_RPC)
    parser.add_argument("--dry-run", action="store_true", help="verification queries only (no upgrade deploy)")
    parser.add_argument("--no-write", action="store_true", help="do not write proof/upgrade_hashes.json")
    args = parser.parse_args()

    if not V2_WASM.exists():
        log(f"ERROR: v2 wasm not found at {V2_WASM}")
        return 1
    if not SECRET_KEY.exists():
        log(f"ERROR: deployer secret key not found at {SECRET_KEY}")
        return 1

    log("=" * 78)
    log("VaultWatch — Casper-native Contract Upgrade (Critical Fix 2)")
    log("  Demonstrating storage::add_contract_version() on RiskPolicyManager")
    log("=" * 78)

    upgrade_result = None
    if not args.dry_run:
        upgrade_result = execute_upgrade(args.rpc)
        if not upgrade_result.get("success"):
            log("Upgrade did not verify successful; aborting verification calls.")
            # Still write the partial report.
            report = verify(args.rpc, upgrade_result)
            if not args.no_write:
                PROOF_FILE.parent.mkdir(parents=True, exist_ok=True)
                PROOF_FILE.write_text(json.dumps(report, indent=2))
            return 1

    report = verify(args.rpc, upgrade_result)

    log("")
    log("=" * 78)
    log("VERIFICATION SUMMARY")
    log("=" * 78)
    for name, check in report["checks"].items():
        if isinstance(check, dict) and "pass" in check:
            status = "✅ PASS" if check["pass"] else "❌ FAIL"
            log(f"  {status}  {name}")
        elif isinstance(check, dict) and check.get("skipped"):
            log(f"  ⏭ SKIP  {name}")
    log("")
    log(f"Result: {report['checks_passed']}/{report['checks_run']} checks passed | all_pass={report['all_pass']}")

    if not args.no_write:
        PROOF_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROOF_FILE.write_text(json.dumps(report, indent=2))
        log(f"\nReport written to {PROOF_FILE}")

    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
