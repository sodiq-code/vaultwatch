#!/usr/bin/env python3
"""
VaultWatch — Offline Deploy Exporter
Generates signed deploy JSON files for all 8 contracts.
These can be broadcast to the Casper testnet from any machine with network access.

Usage:
    python scripts/export_signed_deploys.py

Then broadcast each deploy:
    casper-client put-deploy --input deploys/AuditTrail_deploy.json --node-address https://rpc.testnet.casperlabs.io

Or use the companion broadcast script:
    python scripts/broadcast_deploys.py
"""

from __future__ import annotations

import json
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pycspr.factory import create_deploy, create_deploy_parameters, parse_private_key  # noqa: E402
from pycspr.types.crypto import KeyAlgorithm  # noqa: E402
from pycspr.types.cl import CLV_U512, CLV_String, CLV_Bool  # noqa: E402
from pycspr.types.node.rpc.complex import DeployArgument, DeployOfModuleBytes  # noqa: E402
from pycspr import serializer  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("export_deploys")

KEY_PATH = Path(__file__).parent.parent / "secret_key.pem"
WASM_DIR = Path(__file__).parent.parent / "contracts" / "wasm"
OUT_DIR = Path(__file__).parent.parent / "deploys"

CONTRACTS = [
    {"name": "AuditTrail",          "wasm": "AuditTrail.wasm",          "payment": 120_000_000_000, "args": {}},
    {"name": "RiskOracle",          "wasm": "RiskOracle.wasm",          "payment": 120_000_000_000, "args": {}},
    {"name": "SentinelCredit",      "wasm": "SentinelCredit.wasm",      "payment": 150_000_000_000, "args": {"name": "SentinelCredit", "symbol": "SRC", "decimals": 9}},
    {"name": "SentinelRegistry",    "wasm": "SentinelRegistry.wasm",    "payment": 130_000_000_000, "args": {}},
    {"name": "SentinelAlertLog",    "wasm": "SentinelAlertLog.wasm",    "payment": 120_000_000_000, "args": {}},
    {"name": "AgentBehaviorIndex",  "wasm": "AgentBehaviorIndex.wasm",  "payment": 130_000_000_000, "args": {}},
    {"name": "RiskPolicyManager",   "wasm": "RiskPolicyManager.wasm",   "payment": 130_000_000_000, "args": {}},
    {"name": "SubscriberVault",     "wasm": "SubscriberVault.wasm",     "payment": 140_000_000_000, "args": {}},
]


def make_cl_value(value):
    if isinstance(value, bool):
        return CLV_Bool(value)
    elif isinstance(value, int):
        return CLV_U512(value)
    elif isinstance(value, str):
        return CLV_String(value)
    return value


def main():
    OUT_DIR.mkdir(exist_ok=True)
    key = parse_private_key(KEY_PATH, KeyAlgorithm.SECP256K1)
    logger.info("Loaded signing key from %s", KEY_PATH)

    hashes = {}

    for contract in CONTRACTS:
        name = contract["name"]
        wasm_path = WASM_DIR / contract["wasm"]

        if not wasm_path.exists():
            logger.error("WASM not found: %s", wasm_path)
            continue

        logger.info("Building deploy for %s...", name)

        wasm_bytes = wasm_path.read_bytes()
        params = create_deploy_parameters(account=key, chain_name="casper-test")
        payment = DeployOfModuleBytes(
            module_bytes=b"",
            args=[DeployArgument("amount", CLV_U512(contract["payment"]))],
        )
        session_args = [
            DeployArgument(k, make_cl_value(v))
            for k, v in contract["args"].items()
        ]
        session = DeployOfModuleBytes(module_bytes=wasm_bytes, args=session_args)

        deploy = create_deploy(params, payment, session)
        deploy.approve(key)

        deploy_json = serializer.to_json(deploy)
        out_path = OUT_DIR / f"{name}_deploy.json"
        out_path.write_text(json.dumps(deploy_json, indent=2))

        deploy_hash = deploy.hash.hex() if hasattr(deploy.hash, "hex") else str(deploy.hash)
        hashes[name] = deploy_hash
        logger.info("%s -> hash: %s  saved: %s", name, deploy_hash, out_path)

    # Save hash map
    hashes_path = Path(__file__).parent.parent / "deploy_hashes_live.json"
    hashes_path.write_text(json.dumps(hashes, indent=2))
    logger.info("Deploy hashes saved to %s", hashes_path)

    print("\n" + "=" * 60)
    print("SIGNED DEPLOYS EXPORTED")
    print("=" * 60)
    for name, h in hashes.items():
        print(f"  {name:<25} {h}")
    print("=" * 60)
    print(f"\nDeploy JSON files in: {OUT_DIR}/")
    print("\nTo broadcast from your machine:")
    print("  python scripts/broadcast_deploys.py")
    print("\nOr manually per contract:")
    print("  casper-client put-deploy --input deploys/<Name>_deploy.json \\")
    print("    --node-address https://rpc.testnet.casperlabs.io")

    return hashes


if __name__ == "__main__":
    main()
