#!/usr/bin/env python3
"""VaultWatch — LIVE contract deployment to Casper Testnet (pycspr v0.12.4)."""

from __future__ import annotations
import argparse
import json
import os
import sys
import time
from pathlib import Path
import httpx
import pycspr

REPO_ROOT = Path(__file__).resolve().parent.parent
WASM_DIR = REPO_ROOT / "contracts" / "wasm"
CHECKER = REPO_ROOT / "scripts" / "check_wasm_bulk_memory.py"

CONTRACTS = [
    {"name": "AuditTrail", "wasm": "AuditTrail.wasm", "payment": 150_000_000_000},
    {"name": "SentinelRegistry", "wasm": "SentinelRegistry.wasm", "payment": 130_000_000_000},
    {"name": "RiskOracle", "wasm": "RiskOracle.wasm", "payment": 130_000_000_000},
    {"name": "SentinelCredit", "wasm": "SentinelCredit.wasm", "payment": 180_000_000_000},
    {"name": "AgentBehaviorIndex", "wasm": "AgentBehaviorIndex.wasm", "payment": 140_000_000_000},
    {"name": "SentinelAlertLog", "wasm": "SentinelAlertLog.wasm", "payment": 130_000_000_000},
    {"name": "RiskPolicyManager", "wasm": "RiskPolicyManager.wasm", "payment": 140_000_000_000},
    {"name": "SubscriberVault", "wasm": "SubscriberVault.wasm", "payment": 150_000_000_000},
]


def log(msg):
    print(f"[deploy] {msg}", flush=True)


def pre_validate_wasm():
    import subprocess

    log("Step 1: pre-validating WASM…")
    result = subprocess.run([sys.executable, str(CHECKER), str(WASM_DIR)])
    return 0 if result.returncode == 0 else 1


def rpc_call(node_url, method, params):
    body = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    r = httpx.post(node_url, json=body, timeout=30)
    r.raise_for_status()
    j = r.json()
    if "error" in j:
        raise RuntimeError(f"RPC error: {j['error']}")
    return j.get("result", {})


def submit_and_wait(node_url, deploy_json, timeout=120):
    result = rpc_call(node_url, "account_put_deploy", [deploy_json])
    deploy_hash = result.get("deploy_hash")
    if not deploy_hash:
        raise RuntimeError(f"no deploy_hash: {result}")
    start = time.time()
    while time.time() - start < timeout:
        time.sleep(5)
        try:
            data = rpc_call(node_url, "info_get_deploy", [{"deploy_hash": deploy_hash}])
        except:
            continue
        exec_results = data.get("deploy", {}).get("execution_results", [])
        if exec_results:
            outcome = exec_results[0].get("result", {})
            block_hash = exec_results[0].get("block_hash", "")
            if "Success" in outcome:
                return {"status": "success", "deploy_hash": deploy_hash, "block_hash": block_hash, "gas": outcome["Success"].get("cost", "0")}
            elif "Failure" in outcome:
                return {"status": "failed", "deploy_hash": deploy_hash, "block_hash": block_hash, "error": outcome["Failure"].get("error_message", "unknown")}
    return {"status": "timeout", "deploy_hash": deploy_hash}


def build_sign_and_submit(key_path, algo, wasm_path, payment, chain_name, node_url):
    pk = pycspr.parse_private_key(key_path, algo)
    wasm_bytes = pycspr.read_wasm(wasm_path)
    params = pycspr.factory.create_deploy_parameters(account=pk, chain_name=chain_name, ttl="30m")
    payment_item = pycspr.create_standard_payment(payment)
    session = pycspr.types.deploys.ModuleBytes(module_bytes=wasm_bytes, args=[])
    deploy = pycspr.factory.create_deploy(params=params, payment=payment_item, session=session)
    deploy.approve(pk)
    deploy_json = pycspr.to_json(deploy)
    return submit_and_wait(node_url, deploy_json)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-path", required=True)
    parser.add_argument("--algo", default="secp256k1", choices=["ed25519", "secp256k1"])
    parser.add_argument("--node-url", default=os.getenv("CASPER_NODE_URL", "https://rpc.testnet.casper.network/rpc"))
    parser.add_argument("--chain-name", default="casper-test")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", default=str(REPO_ROOT / "deploy_hashes_live.json"))
    args = parser.parse_args()

    log("=" * 70)
    log("VaultWatch — LIVE Deployment")
    log("=" * 70)
    log(f"  Node: {args.node_url} | Chain: {args.chain_name} | Algo: {args.algo}")

    if pre_validate_wasm() != 0:
        return 1
    if args.dry_run:
        log("✅ Dry run OK — WASM valid. Remove --dry-run to deploy.")
        return 0

    key_path = Path(args.key_path).expanduser().resolve()
    if not key_path.exists():
        log(f"❌ Key not found: {key_path}")
        return 2
    algo = pycspr.KeyAlgorithm.ED25519 if args.algo == "ed25519" else pycspr.KeyAlgorithm.SECP256K1
    pk = pycspr.parse_private_key(key_path, algo)
    log(f"  Account: {pk.account_key.hex()}")

    results, deploy_hashes = {}, {}
    for c in CONTRACTS:
        name = c["name"]
        wasm_path = WASM_DIR / c["wasm"]
        log(f"\n--- {name} ({c['payment']:,} motes) ---")
        if not wasm_path.exists():
            log(f"❌ {wasm_path} not found")
            return 1
        try:
            outcome = build_sign_and_submit(key_path, algo, wasm_path, c["payment"], args.chain_name, args.node_url)
            if outcome["status"] == "success":
                gas = outcome.get("gas", "0")
                log(f"  ✅ {name} — hash: {outcome['deploy_hash']}")
                log(f"     gas: {gas} motes ({int(gas) / 1e9:.4f} CSPR)")
                deploy_hashes[name] = outcome["deploy_hash"]
                results[name] = outcome
            else:
                log(f"  ❌ {name} {outcome['status']}: {outcome.get('error', '')}")
                results[name] = outcome
        except Exception as e:
            log(f"  ❌ {name} EXCEPTION: {e}")
            results[name] = {"status": "exception", "error": str(e)}
        time.sleep(3)

    log("\n" + "=" * 70)
    log("SUMMARY")
    log("=" * 70)
    success = sum(1 for r in results.values() if r.get("status") == "success")
    for name, r in results.items():
        m = "✅" if r.get("status") == "success" else "❌"
        log(f"  {m} {name:<25} {r.get('status', '?'):<10} {r.get('deploy_hash', '')[:40]}")
    log(f"\n  {success}/{len(CONTRACTS)} deployed.")

    Path(args.output).write_text(json.dumps(deploy_hashes, indent=2))
    log(f"Hashes → {args.output}")

    if success == len(CONTRACTS):
        log("\n=== Paste into proof/PROOF.md: ===")
        print("\n| Contract | Deploy Hash | Explorer |")
        print("|----------|-------------|----------|")
        for c in CONTRACTS:
            dh = deploy_hashes.get(c["name"], "")
            print(f"| **{c['name']}** | `{dh}` | [view](https://testnet.cspr.live/deploy/{dh}) |")
        return 0
    return 3


if __name__ == "__main__":
    sys.exit(main())
