#!/usr/bin/env python3
"""
VaultWatch — Live Testnet Contract Deployer
Submits all 8 WASM contracts to Casper testnet via cspr.cloud JSON-RPC proxy.
"""

from __future__ import annotations

import json
import sys
import time
import requests
from pathlib import Path

import pycspr
from pycspr.factory import parse_private_key, create_deploy_parameters, create_deploy
from pycspr.types.crypto import KeyAlgorithm
from pycspr.types.cl import CLV_U512
from pycspr.types.node.rpc.complex import DeployArgument, DeployOfModuleBytes

ROOT = Path(__file__).parent.parent
KEY_PATH = ROOT / "secret_key.pem"
WASM_DIR = ROOT / "contracts" / "wasm"
OUT_FILE = ROOT / "deploy_hashes_live.json"

RPC_URL = "https://node.testnet.cspr.cloud/rpc"
RPC_HEADERS = {
    "Authorization": "019ef63a-5ffc-7657-8627-d7436d9f0e8c",
    "Content-Type": "application/json",
}
CHAIN_NAME = "casper-test"

CONTRACTS = [
    {
        "name": "AuditTrail",
        "wasm": "AuditTrail.wasm",
        "payment": 120_000_000_000,
        "args": [],
    },
    {
        "name": "RiskOracle",
        "wasm": "RiskOracle.wasm",
        "payment": 120_000_000_000,
        "args": [],
    },
    {
        "name": "SentinelCredit",
        "wasm": "SentinelCredit.wasm",
        "payment": 150_000_000_000,
        "args": [],
    },
    {
        "name": "SentinelRegistry",
        "wasm": "SentinelRegistry.wasm",
        "payment": 130_000_000_000,
        "args": [],
    },
    {
        "name": "SentinelAlertLog",
        "wasm": "SentinelAlertLog.wasm",
        "payment": 120_000_000_000,
        "args": [],
    },
    {
        "name": "AgentBehaviorIndex",
        "wasm": "AgentBehaviorIndex.wasm",
        "payment": 130_000_000_000,
        "args": [],
    },
    {
        "name": "RiskPolicyManager",
        "wasm": "RiskPolicyManager.wasm",
        "payment": 130_000_000_000,
        "args": [],
    },
    {
        "name": "SubscriberVault",
        "wasm": "SubscriberVault.wasm",
        "payment": 140_000_000_000,
        "args": [],
    },
]


def rpc_call(method: str, params: dict) -> dict:
    payload = {"id": 1, "jsonrpc": "2.0", "method": method, "params": params}
    r = requests.post(RPC_URL, json=payload, headers=RPC_HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data["result"]


def get_account_balance(pub_key_hex: str) -> int:
    try:
        status = rpc_call("info_get_status", {})
        state_root = status.get("last_added_block_info", {}).get("state_root_hash", "")
        result = rpc_call(
            "query_global_state",
            {
                "state_identifier": {"StateRootHash": state_root},
                "key": f"account-hash-{pub_key_hex}",
                "path": [],
            },
        )
        purse = result["stored_value"]["Account"]["main_purse"]
        bal = rpc_call("query_balance", {"purse_identifier": {"URef": purse}})
        return int(bal.get("balance", 0))
    except Exception as e:
        print(f"  Balance check failed: {e}")
        return 0


def build_and_send(key, contract: dict) -> str:
    wasm_path = WASM_DIR / contract["wasm"]
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


def main():
    print("=" * 60)
    print("VaultWatch — Live Casper Testnet Deployer")
    print("=" * 60)

    # Load key
    key = parse_private_key(KEY_PATH, KeyAlgorithm.SECP256K1)
    pub_hex = key.to_public_key().account_key.hex()
    print(f"Account: {pub_hex[:20]}...")

    # Check node connectivity
    try:
        status = rpc_call("info_get_status", {})
        print(f"Node: {status.get('chainspec_name', '?')} era {status.get('last_added_block_info', {}).get('era_id', '?')}")
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
            # Wait between deploys to avoid nonce/replay issues
            if i < len(CONTRACTS):
                time.sleep(3)
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            failed.append(name)
            results[name] = f"FAILED: {e}"

    # Save results
    OUT_FILE.write_text(json.dumps(results, indent=2))
    print(f"\n{'=' * 60}")
    print(f"Results saved to {OUT_FILE}")
    print(f"Deployed: {len(results) - len(failed)}/{len(CONTRACTS)}")
    if failed:
        print(f"Failed: {failed}")

    # Print liveApi.js snippet
    print("\n--- liveApi.js CONTRACT_HASHES snippet ---")
    good = {k: v for k, v in results.items() if not v.startswith("FAILED")}
    if good:
        print("export const CONTRACT_HASHES = {")
        for name, h in good.items():
            print(f"  {name}: '{h}',")
        print("};")


if __name__ == "__main__":
    main()
