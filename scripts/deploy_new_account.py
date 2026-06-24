#!/usr/bin/env python3
"""
VaultWatch — Contract Deployer Script
Deploys all 8 Odra/WASM contracts to Casper Testnet (casper-test).

Deployer Account: 0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116

Usage:
    # Option A: Provide secret key as hex (32 bytes = 64 hex chars)
    CASPER_SECRET_KEY_HEX=<your_private_key_hex> python scripts/deploy_new_account.py

    # Option B: Provide path to secret_key.pem file
    python scripts/deploy_new_account.py --key-path /path/to/secret_key.pem

    # Option C: Place secret_key.pem in the repo root and run:
    python scripts/deploy_new_account.py

Output is saved to deploy_hashes_live.json in the repo root.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests

# Try importing pycspr
try:
    from pycspr.factory import parse_private_key, create_deploy_parameters, create_deploy
    from pycspr.types.crypto import KeyAlgorithm
    from pycspr.types.cl import CLV_U512
    from pycspr.types.node.rpc.complex import DeployArgument, DeployOfModuleBytes
    import pycspr
    SDK_OK = True
except ImportError:
    SDK_OK = False
    print("ERROR: pycspr not installed. Run: pip install pycspr")
    sys.exit(1)

ROOT = Path(__file__).parent.parent
WASM_DIR = ROOT / "contracts" / "wasm"
OUT_FILE = ROOT / "deploy_hashes_live.json"

RPC_URL = "https://node.testnet.cspr.cloud/rpc"
RPC_HEADERS = {
    "Authorization": "019ef63a-5ffc-7657-8627-d7436d9f0e8c",
    "Content-Type": "application/json",
}
CHAIN_NAME = "casper-test"

NEW_ACCOUNT_PUBKEY = "0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116"

CONTRACTS = [
    {"name": "AuditTrail",          "wasm": "AuditTrail.wasm",          "payment": 120_000_000_000, "args": []},
    {"name": "RiskOracle",          "wasm": "RiskOracle.wasm",          "payment": 120_000_000_000, "args": []},
    {"name": "SentinelCredit",      "wasm": "SentinelCredit.wasm",      "payment": 150_000_000_000, "args": []},
    {"name": "SentinelRegistry",    "wasm": "SentinelRegistry.wasm",    "payment": 130_000_000_000, "args": []},
    {"name": "SentinelAlertLog",    "wasm": "SentinelAlertLog.wasm",    "payment": 120_000_000_000, "args": []},
    {"name": "AgentBehaviorIndex",  "wasm": "AgentBehaviorIndex.wasm",  "payment": 130_000_000_000, "args": []},
    {"name": "RiskPolicyManager",   "wasm": "RiskPolicyManager.wasm",   "payment": 130_000_000_000, "args": []},
    {"name": "SubscriberVault",     "wasm": "SubscriberVault.wasm",     "payment": 140_000_000_000, "args": []},
]

# Total payment needed: ~1060 CSPR (well within 5000 CSPR balance)


def rpc_call(method: str, params: dict) -> dict:
    payload = {"id": 1, "jsonrpc": "2.0", "method": method, "params": params}
    r = requests.post(RPC_URL, json=payload, headers=RPC_HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data["result"]


def check_balance() -> int:
    r = requests.get(
        f"https://api.testnet.cspr.cloud/accounts/{NEW_ACCOUNT_PUBKEY}",
        headers={"Authorization": "019ef63a-5ffc-7657-8627-d7436d9f0e8c"},
        timeout=10,
    )
    bal = int(r.json().get("data", {}).get("balance", 0))
    print(f"Account balance: {bal/1e9:.1f} CSPR")
    return bal


def build_and_send(key, contract: dict) -> str:
    wasm_path = WASM_DIR / contract["wasm"]
    if not wasm_path.exists():
        raise FileNotFoundError(f"WASM not found: {wasm_path}")

    wasm_bytes = wasm_path.read_bytes()
    params = create_deploy_parameters(account=key, chain_name=CHAIN_NAME)
    payment = DeployOfModuleBytes(
        module_bytes=b"",
        args=[DeployArgument(name="amount", value=CLV_U512(contract["payment"]))],
    )
    session = DeployOfModuleBytes(module_bytes=wasm_bytes, args=contract["args"])
    deploy = create_deploy(params, payment, session)
    deploy.approve(key)

    deploy_hash = deploy.hash.hex()
    encoded = pycspr.serializer.to_json(deploy)
    result = rpc_call("account_put_deploy", {"deploy": encoded})
    returned_hash = result.get("deploy_hash", deploy_hash)
    return returned_hash


def wait_for_deploy(deploy_hash: str, timeout: int = 180) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            result = rpc_call("info_get_deploy", {"deploy_hash": deploy_hash})
            if result.get("execution_results"):
                return True
        except Exception:
            pass
        time.sleep(6)
    return False


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--key-path", default=str(ROOT / "secret_key.pem"))
    args = parser.parse_args()

    # Try env var first
    secret_hex = os.getenv("CASPER_SECRET_KEY_HEX", "")
    key_path = Path(args.key_path)

    print("=" * 60)
    print("VaultWatch — New Account Deployer")
    print(f"Account: {NEW_ACCOUNT_PUBKEY[:30]}...")
    print("=" * 60)

    # Check balance
    try:
        bal = check_balance()
        if bal < 500_000_000_000:  # < 500 CSPR
            print("ERROR: Insufficient balance for deployment")
            sys.exit(1)
    except Exception as e:
        print(f"Balance check failed: {e}")

    # Load key
    if secret_hex:
        # Convert hex to PEM and save temporarily
        print("Loading key from CASPER_SECRET_KEY_HEX env var...")
        tmp_pem = ROOT / "_tmp_secret_key.pem"
        # Write raw hex key as PEM
        key_bytes = bytes.fromhex(secret_hex)
        import base64
        b64 = base64.b64encode(key_bytes).decode()
        pem_content = f"-----BEGIN EC PRIVATE KEY-----\n{b64}\n-----END EC PRIVATE KEY-----\n"
        tmp_pem.write_text(pem_content)
        key = parse_private_key(tmp_pem, KeyAlgorithm.SECP256K1)
        tmp_pem.unlink(missing_ok=True)
    elif key_path.exists():
        print(f"Loading key from {key_path}...")
        key = parse_private_key(key_path, KeyAlgorithm.SECP256K1)
    else:
        print("\nERROR: No private key found.")
        print("  Option A: export CASPER_SECRET_KEY_HEX=<64-hex-char private key>")
        print(f"  Option B: place secret_key.pem at {key_path}")
        print("\nYour account has 5000 CSPR ready to deploy!")
        sys.exit(1)

    pub_hex = key.to_public_key().account_key.hex()
    print(f"Loaded key — public: {pub_hex[:30]}...")

    # Verify it matches expected account
    if pub_hex.lower() != NEW_ACCOUNT_PUBKEY[2:].lower():  # strip leading '02' algo prefix
        print("WARNING: Key doesn't match expected account. Proceeding anyway.")

    # Check node
    try:
        status = rpc_call("info_get_status", {})
        print(f"Node: {status.get('chainspec_name')} era {status.get('last_added_block_info', {}).get('era_id')}")
    except Exception as e:
        print(f"ERROR: Cannot reach node — {e}")
        sys.exit(1)

    results = {}
    failed = []

    for i, contract in enumerate(CONTRACTS, 1):
        name = contract["name"]
        print(f"\n[{i}/{len(CONTRACTS)}] Deploying {name}...")
        try:
            h = build_and_send(key, contract)
            results[name] = h
            print(f"  ✅ Hash: {h}")
            print("  Waiting for inclusion...")
            ok = wait_for_deploy(h, timeout=180)
            if ok:
                print(f"  ✅ {name} confirmed on-chain!")
            else:
                print(f"  ⚠️  {name} not confirmed after 3min — hash saved, check explorer")
            if i < len(CONTRACTS):
                time.sleep(2)
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            failed.append(name)
            results[name] = f"FAILED: {e}"

    # Save results
    good = {k: v for k, v in results.items() if not str(v).startswith("FAILED")}
    if good:
        OUT_FILE.write_text(json.dumps(good, indent=2))
        print(f"\nResults saved to {OUT_FILE}")

        # Print liveApi.js snippet
        print("\n--- Paste this into dashboard/src/liveApi.js CONTRACT_HASHES ---")
        print("export const CONTRACT_HASHES = {")
        for n, h in good.items():
            print(f"  {n}: '{h}',")
        print("};")
        print(f"\nDEPLOYER_ACCOUNT: '{NEW_ACCOUNT_PUBKEY}'")

    print(f"\n{'=' * 60}")
    print(f"Deployed: {len(results) - len(failed)}/{len(CONTRACTS)}")
    if failed:
        print(f"Failed: {failed}")


if __name__ == "__main__":
    main()
