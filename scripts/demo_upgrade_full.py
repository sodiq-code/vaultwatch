#!/usr/bin/env python3
"""
VaultWatch — Full Casper-native Contract Upgrade Lifecycle (Critical Fix 2).

End-to-end demonstration of Casper's natively-upgradable smart contracts:

  1. INSTALL v1 `RiskPolicyManager` as a fresh, UPGRADABLE contract package
     (owned by the funded deployer account), via Odra's `install_new_contract`
     path (which calls `storage::new_contract()` + creates the `upgrader_group`).
  2. CALL `upgrade_policy` on v1 with a known, distinctive policy — this is the
     state we will later prove v2 can read (shared-state baseline).
  3. CALL `get_current_policy` on v1 — proves v1 works and establishes the
     baseline value.
  4. UPGRADE the package to v2 `RiskPolicyManagerV2` using the Casper host
     function `storage::add_contract_version(...)`, invoked automatically by
     Odra 2.x when the v2 Wasm is deployed as session code with
     `odra_cfg_is_upgrade=true`. v2 is a functional SUPERSET: all v1 entry
     points preserved + new `get_policy_with_reasoning`.
  5. VERIFY a 5-check matrix on-chain:
       5a. Package now has 2 versions (v1 disabled, v2 active = latest).
       5b. v2 contract exposes `get_policy_with_reasoning` (new capability)
           AND preserves all v1 entry points (superset).
       5c. v2's `state` URef == v1's `state` URef (structural shared-state proof).
       5d. Calling `get_policy_with_reasoning` on v2 SUCCEEDS — because it reads
           `current_policy` via `get_or_revert`, success proves v2 reads v1's
           shared state (functional shared-state proof).
       5e. Calling `get_current_policy` on v2 SUCCEEDS — v1 entry point still
           works on the upgraded superset.
  6. WRITE proof/upgrade_hashes.json with every deploy/call hash + the
     verification report.

Uses only hackathon-sanctioned resources (per the DoraHacks Casper Agentic
Buildathon Finals detail page):
  - Odra Framework (odra.dev) — smart-contract framework with first-class
    Casper-native upgrade support.
  - casper-js-sdk v5 (github.com/casper-network) — official SDK for
    Casper-2.x-compatible deploy signing.
  - Casper Testnet RPC (node.testnet.casper.network) — account_put_deploy,
    info_get_deploy, query_global_state, chain_get_state_root_hash.
  - Casper docs (docs.casper.network) — add_contract_version, contract versioning.

Usage:
    python3 scripts/demo_upgrade_full.py
    python3 scripts/demo_upgrade_full.py --dry-run   # verification queries only
    python3 scripts/demo_upgrade_full.py --from-existing <package_hash>
        # skip the v1 install; upgrade an existing v1 package instead
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

V1_WASM = REPO_ROOT / "contracts" / "wasm" / "RiskPolicyManager.wasm"
V2_WASM = REPO_ROOT / "contracts" / "wasm" / "RiskPolicyManagerV2.wasm"
SECRET_KEY = REPO_ROOT / "secret_key.pem"
INSTALL_HELPER = REPO_ROOT / "scripts" / "casper_install.cjs"
UPGRADE_HELPER = REPO_ROOT / "scripts" / "casper_upgrade.cjs"
CALL_HELPER = REPO_ROOT / "scripts" / "casper_deploy.cjs"
PROOF_FILE = REPO_ROOT / "proof" / "upgrade_hashes.json"

# Named key under which the package hash is stored on the deployer account.
PACKAGE_HASH_KEY_NAME = "risk_policy_manager_package_hash"

# Payment sizing (mostly refunded; out-of-gas charges the full payment).
INSTALL_PAYMENT_MOTES = 150_000_000_000       # 150 CSPR for v1 install
UPGRADE_PAYMENT_MOTES = 300_000_000_000       # 300 CSPR for v2 upgrade (heavier)
CALL_PAYMENT_MOTES = 5_000_000_000            # 5 CSPR per contract call

# The distinctive policy we set on v1 (baseline for the shared-state proof).
# v2's get_policy_with_reasoning reads this exact value via the shared `state`
# dictionary — success + matching reasoning proves shared state functionally.
BASELINE_POLICY = {
    "min_confidence_threshold": 70,
    "critical_score_threshold": 85,
    "high_score_threshold": 65,
    "medium_score_threshold": 45,
    "max_retry_count": 2,
    "safety_rejection_threshold": 90,
    "block_height": 1_500_000,
    "updated_by": "v1-pre-upgrade-state",
}


def log(msg: str) -> None:
    print(f"[upgrade-full] {msg}", flush=True)


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------

def rpc_call(rpc_url: str, method: str, params) -> dict:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    r = requests.post(rpc_url, json=payload, headers={"Content-Type": "application/json"}, timeout=45)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        return {"error": data["error"]}
    return data.get("result", {})


def get_state_root_hash(rpc_url: str) -> str:
    return rpc_call(rpc_url, "chain_get_state_root_hash", {}).get("state_root_hash", "")


def get_account(rpc_url: str, srh: str, account_hash: str) -> dict:
    """Query an account by its account-hash (hex, no prefix)."""
    res = rpc_call(rpc_url, "query_global_state", {
        "state_identifier": {"StateRootHash": srh},
        "key": f"account-hash-{account_hash}",
        "path": [],
    })
    return (res.get("stored_value") or {}).get("Account", {})


def get_deployer_account_hash(rpc_url: str) -> str | None:
    """The casper_install.cjs helper returns the deployer account hash; if we
    need it independently, we derive it from the install result. Otherwise None."""
    return None


def query_package(rpc_url: str, srh: str, package_hash: str) -> dict:
    res = rpc_call(rpc_url, "query_global_state", {
        "state_identifier": {"StateRootHash": srh},
        "key": f"hash-{package_hash}",
        "path": [],
    })
    return (res.get("stored_value") or {}).get("ContractPackage", {})


def query_contract(rpc_url: str, srh: str, contract_hash: str) -> dict:
    res = rpc_call(rpc_url, "query_global_state", {
        "state_identifier": {"StateRootHash": srh},
        "key": f"hash-{contract_hash}",
        "path": [],
    })
    return (res.get("stored_value") or {}).get("Contract", {})


def resolve_package_hash(rpc_url: str, srh: str, account_hash: str) -> str | None:
    """Read the package hash from the deployer account's named keys
    (stored under PACKAGE_HASH_KEY_NAME by Odra's install_new_contract)."""
    acct = get_account(rpc_url, srh, account_hash)
    for nk in acct.get("named_keys", []):
        if nk.get("name") == PACKAGE_HASH_KEY_NAME:
            key = nk.get("key", "")
            # key is "hash-<64 hex>"
            return key.replace("hash-", "") if key.startswith("hash-") else key
    return None


def resolve_v1_contract_hash(rpc_url: str, srh: str, package_hash: str) -> str | None:
    """From the package, get the latest (only) version's contract hash."""
    pkg = query_package(rpc_url, srh, package_hash)
    versions = pkg.get("versions", [])
    if not versions:
        return None
    # latest version = highest contract_version
    latest = max(versions, key=lambda v: v.get("contract_version", 0))
    ch = latest.get("contract_hash", "")
    return ch.replace("contract-", "") if ch.startswith("contract-") else ch


def state_uref_of(contract: dict) -> str | None:
    for nk in contract.get("named_keys", []):
        if nk.get("name") == "state":
            return nk.get("key")
    return None


# ---------------------------------------------------------------------------
# Node helper runner
# ---------------------------------------------------------------------------

def run_node_helper(helper: Path, request: dict, timeout: int = 300) -> dict:
    req_file = REPO_ROOT / ".upgrade_req.tmp.json"
    req_file.write_text(json.dumps(request))
    try:
        proc = subprocess.run(
            ["node", str(helper), str(req_file)],
            capture_output=True, text=True, timeout=timeout,
        )
        out = proc.stdout.strip()
        if not out:
            raise RuntimeError(
                f"helper {helper.name} produced no stdout; "
                f"stderr={proc.stderr[:800]}; exit={proc.returncode}"
            )
        return json.loads(out)
    finally:
        try:
            req_file.unlink()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Lifecycle steps
# ---------------------------------------------------------------------------

def step_install_v1(rpc_url: str) -> dict:
    """Install a fresh, upgradable RiskPolicyManager v1 package."""
    request = {
        "key_path": str(SECRET_KEY),
        "wasm_path": str(V1_WASM),
        "payment_motes": INSTALL_PAYMENT_MOTES,
        "package_hash_key_name": PACKAGE_HASH_KEY_NAME,
        "rpc_url": rpc_url,
    }
    log(f"Step 1 — INSTALL v1 RiskPolicyManager (fresh, upgradable package)...")
    log(f"  v1 wasm: {V1_WASM.name} ({V1_WASM.stat().st_size} bytes)")
    log(f"  payment: {INSTALL_PAYMENT_MOTES/1e9:.0f} CSPR")
    result = run_node_helper(INSTALL_HELPER, request, timeout=300)
    if result.get("success"):
        log(f"  ✅ v1 INSTALL VERIFIED SUCCESS on-chain")
        log(f"     deploy:  {result['deploy_hash']}")
        log(f"     block:   {result['block_hash']}")
        log(f"     cost:    {int(result['cost_motes'])/1e9:.4f} CSPR")
        log(f"     link:    {result['link']}")
    else:
        log(f"  ❌ v1 INSTALL FAILED: {result.get('error')}")
    return result


def step_call(rpc_url: str, contract_hash: str, entry_point: str, args: list, label: str) -> dict:
    """Call an entry point on a contract (stored-contract call)."""
    request = {
        "key_path": str(SECRET_KEY),
        "contract_hash": contract_hash,
        "entry_point": entry_point,
        "payment_motes": CALL_PAYMENT_MOTES,
        "args": args,
        "rpc_url": rpc_url,
    }
    log(f"{label} — calling {entry_point}()...")
    result = run_node_helper(CALL_HELPER, request, timeout=200)
    if result.get("success"):
        log(f"  ✅ {entry_point} SUCCEEDED")
        log(f"     deploy: {result['deploy_hash']}")
        log(f"     cost:   {int(result['cost_motes'])/1e9:.4f} CSPR")
    else:
        log(f"  ❌ {entry_point} FAILED: {result.get('error')}")
    return result


def step_upgrade_v2(rpc_url: str, package_hash: str) -> dict:
    """Upgrade the package to v2 via add_contract_version (odra_cfg_is_upgrade=true)."""
    request = {
        "key_path": str(SECRET_KEY),
        "wasm_path": str(V2_WASM),
        "payment_motes": UPGRADE_PAYMENT_MOTES,
        "package_hash": package_hash,
        "package_hash_key_name": PACKAGE_HASH_KEY_NAME,
        "rpc_url": rpc_url,
    }
    log(f"Step 4 — UPGRADE to v2 via add_contract_version()...")
    log(f"  v1 package hash: {package_hash}")
    log(f"  v2 wasm: {V2_WASM.name} ({V2_WASM.stat().st_size} bytes)")
    log(f"  payment: {UPGRADE_PAYMENT_MOTES/1e9:.0f} CSPR")
    result = run_node_helper(UPGRADE_HELPER, request, timeout=300)
    if result.get("success"):
        log(f"  ✅ v2 UPGRADE VERIFIED SUCCESS on-chain")
        log(f"     deploy:  {result['deploy_hash']}")
        log(f"     block:   {result['block_hash']}")
        log(f"     cost:    {int(result['cost_motes'])/1e9:.4f} CSPR")
        log(f"     link:    {result['link']}")
    else:
        log(f"  ❌ v2 UPGRADE FAILED: {result.get('error')}")
    return result


# ---------------------------------------------------------------------------
# Verification matrix
# ---------------------------------------------------------------------------

def verify(rpc_url: str, deployer_account_hash: str, package_hash: str,
           v1_contract_hash: str, v1_state_uref: str,
           install_result: dict | None, upgrade_result: dict | None,
           set_policy_result: dict | None, get_policy_v1_result: dict | None,
           get_reasoning_v2_result: dict | None, get_policy_v2_result: dict | None) -> dict:
    srh = get_state_root_hash(rpc_url)
    log(f"State root hash: {srh[:20]}...")

    report = {
        "network": CHAIN_NAME,
        "rpc_url": rpc_url,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "deployer_account_hash": f"account-hash-{deployer_account_hash}",
        "package_hash": package_hash,
        "v1_contract_hash": v1_contract_hash,
        "v1_state_uref": v1_state_uref,
        "baseline_policy_set_on_v1": BASELINE_POLICY,
        "deploys": {},
        "checks": {},
    }
    for name, r in [
        ("v1_install", install_result),
        ("upgrade_policy_on_v1", set_policy_result),
        ("get_current_policy_on_v1", get_policy_v1_result),
        ("v2_upgrade_add_contract_version", upgrade_result),
        ("get_policy_with_reasoning_on_v2", get_reasoning_v2_result),
        ("get_current_policy_on_v2", get_policy_v2_result),
    ]:
        if r and r.get("deploy_hash"):
            report["deploys"][name] = {
                "deploy_hash": r["deploy_hash"],
                "block_hash": r.get("block_hash", ""),
                "cost_motes": r.get("cost_motes", "0"),
                "link": r.get("link", ""),
                "success": bool(r.get("success")),
            }

    # --- Check 1: package has 2 versions ---
    pkg = query_package(rpc_url, srh, package_hash)
    versions = pkg.get("versions", [])
    disabled = pkg.get("disabled_versions", [])
    v2_contract_hash = None
    if versions:
        v2 = max(versions, key=lambda v: v.get("contract_version", 0))
        ch = v2.get("contract_hash", "")
        v2_contract_hash = ch.replace("contract-", "") if ch.startswith("contract-") else ch
    log(f"Check 1 — package versions: {len(versions)} "
        f"({[v.get('contract_version') for v in versions]}) disabled={len(disabled)}")
    report["v2_contract_hash"] = v2_contract_hash
    report["checks"]["package_has_2_versions"] = {
        "count": len(versions),
        "versions": versions,
        "disabled_versions": disabled,
        "lock_status": pkg.get("lock_status"),
        "access_key": pkg.get("access_key"),
        "pass": len(versions) >= 2,
    }

    # --- Check 2a: v2 exposes get_policy_with_reasoning ---
    # --- Check 2b: v1 entry points preserved in v2 (superset) ---
    v2_contract = query_contract(rpc_url, srh, v2_contract_hash) if v2_contract_hash else {}
    v2_eps = {ep["name"] for ep in v2_contract.get("entry_points", [])}
    has_new_ep = "get_policy_with_reasoning" in v2_eps
    v1_eps_expected = {
        "init", "upgrade_policy", "get_current_policy", "get_policy_version",
        "get_current_version", "transfer_ownership",
    }
    v1_preserved = v1_eps_expected.issubset(v2_eps)
    log(f"Check 2 — v2 entry points: {len(v2_eps)} | has get_policy_with_reasoning: {has_new_ep} | v1 EPs preserved: {v1_preserved}")
    report["checks"]["v2_new_entry_point"] = {
        "v2_entry_points": sorted(v2_eps),
        "has_get_policy_with_reasoning": has_new_ep,
        "pass": has_new_ep,
    }
    report["checks"]["v1_entry_points_preserved_in_v2"] = {
        "expected": sorted(v1_eps_expected),
        "preserved": v1_preserved,
        "pass": v1_preserved,
    }

    # --- Check 3: shared state — v2's `state` URef == v1's `state` URef ---
    v2_state_uref = state_uref_of(v2_contract)
    shared_state = bool(v2_state_uref) and v2_state_uref == v1_state_uref
    log(f"Check 3 — shared state URef: v1={v1_state_uref} v2={v2_state_uref} -> {shared_state}")
    report["checks"]["shared_state_uref"] = {
        "v1_state_uref": v1_state_uref,
        "v2_state_uref": v2_state_uref,
        "shared": shared_state,
        "pass": shared_state,
    }

    # --- Check 4: get_policy_with_reasoning works on v2 (functional shared-state proof) ---
    if get_reasoning_v2_result:
        ok4 = bool(get_reasoning_v2_result.get("success"))
        log(f"Check 4 — get_policy_with_reasoning on v2: success={ok4}")
        report["checks"]["call_get_policy_with_reasoning_on_v2"] = {
            "deploy_hash": get_reasoning_v2_result.get("deploy_hash"),
            "link": get_reasoning_v2_result.get("link"),
            "success": ok4,
            "error": get_reasoning_v2_result.get("error"),
            "pass": ok4,
            "rationale": "success proves v2 reads v1's shared state "
                         "(get_policy_with_reasoning reads current_policy via get_or_revert; "
                         "without shared state it would revert with User(1))",
        }
    else:
        report["checks"]["call_get_policy_with_reasoning_on_v2"] = {"skipped": True}

    # --- Check 5: get_current_policy on v2 (v1 EP on upgraded superset) ---
    if get_policy_v2_result:
        ok5 = bool(get_policy_v2_result.get("success"))
        log(f"Check 5 — get_current_policy on v2 (v1 EP on upgraded package): success={ok5}")
        report["checks"]["call_get_current_policy_on_v2"] = {
            "deploy_hash": get_policy_v2_result.get("deploy_hash"),
            "link": get_policy_v2_result.get("link"),
            "success": ok5,
            "error": get_policy_v2_result.get("error"),
            "pass": ok5,
        }
    else:
        report["checks"]["call_get_current_policy_on_v2"] = {"skipped": True}

    # --- Overall verdict ---
    checks = report["checks"]
    actionable = [k for k, v in checks.items() if isinstance(v, dict) and "pass" in v]
    report["all_pass"] = all(checks[k]["pass"] for k in actionable)
    report["checks_run"] = len(actionable)
    report["checks_passed"] = sum(1 for k in actionable if checks[k]["pass"])
    return report


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="VaultWatch full Casper-native contract upgrade lifecycle (Critical Fix 2).")
    parser.add_argument("--rpc", default=DEFAULT_RPC)
    parser.add_argument("--dry-run", action="store_true",
                        help="verification queries only (no deploys)")
    parser.add_argument("--from-existing", metavar="PACKAGE_HASH", default=None,
                        help="skip the v1 install; upgrade an existing v1 package instead")
    parser.add_argument("--no-write", action="store_true",
                        help="do not write proof/upgrade_hashes.json")
    args = parser.parse_args()

    for f in (V1_WASM, V2_WASM, SECRET_KEY, INSTALL_HELPER, UPGRADE_HELPER, CALL_HELPER):
        if not f.exists():
            log(f"ERROR: required file not found: {f}")
            return 1

    log("=" * 80)
    log("VaultWatch — FULL Casper-native Contract Upgrade Lifecycle (Critical Fix 2)")
    log("  Demonstrating storage::add_contract_version() on RiskPolicyManager")
    log("  v1 install -> set policy -> v2 upgrade -> verify shared state")
    log("=" * 80)

    # ---- Resolve deployer account hash from the install helper on the fly,
    #      OR derive it from the existing package's access URef context. We
    #      get it directly from the install result; for --from-existing we
    #      query the package and read the deployer from the access URef. The
    #      simplest universal source: the casper_install.cjs helper returns it.
    deployer_account_hash = None
    package_hash = None
    v1_contract_hash = None
    v1_state_uref = None
    install_result = None

    if args.dry_run:
        if not args.from_existing:
            log("--dry-run requires --from-existing <package_hash>")
            return 1
        package_hash = args.from_existing.replace("hash-", "")
        deployer_account_hash = None
    elif args.from_existing:
        package_hash = args.from_existing.replace("hash-", "")
        log(f"Using EXISTING v1 package: {package_hash}")
    else:
        # Step 1: fresh v1 install
        install_result = step_install_v1(args.rpc)
        if not install_result.get("success"):
            log("v1 install did not verify successful; aborting.")
            return 1
        deployer_account_hash = install_result.get("deployer_account_hash", "").replace("account-hash-", "")
        if not deployer_account_hash:
            log("ERROR: install helper did not return deployer_account_hash")
            return 1
        log(f"  deployer account hash: {deployer_account_hash}")

        # Resolve the freshly-created package hash from the deployer's named keys.
        srh = get_state_root_hash(args.rpc)
        package_hash = resolve_package_hash(args.rpc, srh, deployer_account_hash)
        if not package_hash:
            log("ERROR: could not resolve package hash from deployer named keys")
            return 1
        log(f"  resolved v1 package hash: {package_hash}")

    # Resolve v1 contract hash + state URef from the package.
    srh = get_state_root_hash(args.rpc)
    v1_contract_hash = resolve_v1_contract_hash(args.rpc, srh, package_hash)
    if not v1_contract_hash:
        log("ERROR: could not resolve v1 contract hash from package")
        return 1
    log(f"  v1 contract hash: {v1_contract_hash}")
    v1_contract = query_contract(args.rpc, srh, v1_contract_hash)
    v1_state_uref = state_uref_of(v1_contract)
    log(f"  v1 state URef:    {v1_state_uref}")

    set_policy_result = None
    get_policy_v1_result = None
    upgrade_result = None
    get_reasoning_v2_result = None
    get_policy_v2_result = None

    if not args.dry_run:
        # Step 2: set a known, distinctive policy on v1 (shared-state baseline).
        bp = BASELINE_POLICY
        set_policy_result = step_call(
            args.rpc, v1_contract_hash, "upgrade_policy",
            [
                ["min_confidence_threshold", "U8", bp["min_confidence_threshold"]],
                ["critical_score_threshold", "U8", bp["critical_score_threshold"]],
                ["high_score_threshold", "U8", bp["high_score_threshold"]],
                ["medium_score_threshold", "U8", bp["medium_score_threshold"]],
                ["max_retry_count", "U8", bp["max_retry_count"]],
                ["safety_rejection_threshold", "U8", bp["safety_rejection_threshold"]],
                ["block_height", "U64", str(bp["block_height"])],
                ["updated_by", "String", bp["updated_by"]],
            ],
            "Step 2",
        )
        if not set_policy_result.get("success"):
            log("upgrade_policy on v1 failed; aborting.")
            return 1

        # Step 3: call get_current_policy on v1 (proves v1 works + baseline).
        get_policy_v1_result = step_call(
            args.rpc, v1_contract_hash, "get_current_policy", [], "Step 3",
        )

        # Step 4: upgrade to v2 via add_contract_version.
        upgrade_result = step_upgrade_v2(args.rpc, package_hash)
        if not upgrade_result.get("success"):
            log("v2 upgrade did not verify successful; running partial verification.")
            report = verify(args.rpc, deployer_account_hash or "", package_hash,
                            v1_contract_hash, v1_state_uref, install_result,
                            upgrade_result, set_policy_result, get_policy_v1_result,
                            None, None)
            if not args.no_write:
                PROOF_FILE.parent.mkdir(parents=True, exist_ok=True)
                PROOF_FILE.write_text(json.dumps(report, indent=2))
            return 1

        # Resolve v2 contract hash for the calls.
        srh2 = get_state_root_hash(args.rpc)
        pkg2 = query_package(args.rpc, srh2, package_hash)
        versions2 = pkg2.get("versions", [])
        v2_contract_hash = None
        if versions2:
            v2 = max(versions2, key=lambda v: v.get("contract_version", 0))
            ch = v2.get("contract_hash", "")
            v2_contract_hash = ch.replace("contract-", "") if ch.startswith("contract-") else ch
        if not v2_contract_hash:
            log("ERROR: could not resolve v2 contract hash after upgrade")
            return 1
        log(f"  v2 contract hash: {v2_contract_hash}")

        # Step 5: call get_policy_with_reasoning on v2 (functional shared-state proof).
        get_reasoning_v2_result = step_call(
            args.rpc, v2_contract_hash, "get_policy_with_reasoning", [], "Step 5a",
        )

        # Step 6: call get_current_policy on v2 (v1 EP on upgraded superset).
        get_policy_v2_result = step_call(
            args.rpc, v2_contract_hash, "get_current_policy", [], "Step 5b",
        )

    # Verification matrix.
    report = verify(args.rpc, deployer_account_hash or "", package_hash,
                    v1_contract_hash, v1_state_uref, install_result, upgrade_result,
                    set_policy_result, get_policy_v1_result,
                    get_reasoning_v2_result, get_policy_v2_result)

    log("")
    log("=" * 80)
    log("VERIFICATION SUMMARY")
    log("=" * 80)
    for name, check in report["checks"].items():
        if isinstance(check, dict) and "pass" in check:
            status = "✅ PASS" if check["pass"] else "❌ FAIL"
            log(f"  {status}  {name}")
        elif isinstance(check, dict) and check.get("skipped"):
            log(f"  ⏭ SKIP  {name}")
    log("")
    log(f"Result: {report['checks_passed']}/{report['checks_run']} checks passed | all_pass={report['all_pass']}")

    # Print the deploy-hash table for the proof doc.
    if report.get("deploys"):
        log("")
        log("On-chain deploy hashes:")
        log(f"  {'Step':<42} {'Deploy hash':<66} {'Status'}")
        for name, d in report["deploys"].items():
            log(f"  {name:<42} {d['deploy_hash']:<66} {'✅' if d['success'] else '❌'}")

    if not args.no_write:
        PROOF_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROOF_FILE.write_text(json.dumps(report, indent=2))
        log(f"\nReport written to {PROOF_FILE}")

    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
