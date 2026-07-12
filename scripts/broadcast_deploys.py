#!/usr/bin/env python3
"""
VaultWatch — Deploy Broadcaster
Broadcasts pre-signed deploy JSON files to Casper testnet via cspr.cloud.

Usage:
    python scripts/broadcast_deploys.py
"""

from __future__ import annotations

import json
import sys
import time
import logging
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from pycspr import serializer as rpc_serializer  # noqa: E402
from pycspr.types.node.rpc.complex import Deploy  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("broadcast_deploys")

DEPLOYS_DIR = Path(__file__).parent.parent / "deploys"
NODE_URL = "https://node.testnet.cspr.cloud/rpc"
API_KEY = "019ef63a-5ffc-7657-8627-d7436d9f0e8c"
HEADERS = {"Content-Type": "application/json", "Authorization": API_KEY}

CONTRACT_ORDER = [
    "AuditTrail",
    "RiskOracle",
    "SentinelCredit",
    "SentinelRegistry",
    "SentinelAlertLog",
    "AgentBehaviorIndex",
    "RiskPolicyManager",
    "SubscriberVault",
]


def rpc_call(method: str, params: dict) -> dict:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp = requests.post(NODE_URL, json=payload, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data.get("result", {})


def wait_for_deploy(deploy_hash: str, timeout: int = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            result = rpc_call("info_get_deploy", {"deploy_hash": deploy_hash})
            if result.get("execution_results"):
                return True
        except Exception:
            pass
        time.sleep(5)
    return False


def broadcast_all() -> dict:
    results = {}

    for name in CONTRACT_ORDER:
        deploy_path = DEPLOYS_DIR / f"{name}_deploy.json"
        if not deploy_path.exists():
            logger.warning("Deploy file not found: %s", deploy_path)
            continue

        logger.info("Broadcasting %s...", name)
        deploy_json = json.loads(deploy_path.read_text())

        # deploy JSON is flat — no nested 'deploy' key
        raw = deploy_json.get("deploy", deploy_json)

        try:
            # Reconstruct pycspr Deploy object then re-serialize for RPC
            deploy_obj = rpc_serializer.from_json(Deploy, raw)
            deploy_dict = rpc_serializer.to_json(deploy_obj)

            result = rpc_call("account_put_deploy", {"deploy": deploy_dict})
            deploy_hash = result.get("deploy_hash", "")
            if hasattr(deploy_hash, "hex"):
                deploy_hash = deploy_hash.hex()
            deploy_hash = str(deploy_hash)

            logger.info("%s broadcast — hash: %s", name, deploy_hash)
            results[name] = deploy_hash

            logger.info("Waiting for %s to be included (up to 120s)...", name)
            ok = wait_for_deploy(deploy_hash, timeout=120)
            if ok:
                logger.info("%s CONFIRMED on-chain!", name)
            else:
                logger.warning("%s not confirmed after 120s — hash saved, check explorer", name)

        except Exception as exc:
            logger.error("Failed to broadcast %s: %s", name, exc)
            results[name] = f"FAILED: {exc}"

    # Save results
    out = Path(__file__).parent.parent / "deploy_hashes_live.json"
    # Only overwrite with successful hashes
    good = {k: v for k, v in results.items() if not str(v).startswith("FAILED")}
    if good:
        out.write_text(json.dumps(good, indent=2))
        logger.info("Results saved to %s", out)

    print("\n" + "=" * 60)
    print("BROADCAST SUMMARY")
    print("=" * 60)
    for name, h in results.items():
        status = "OK  " if not str(h).startswith("FAILED") else "FAIL"
        print(f"  [{status}] {name:<25} {str(h)[:56]}")
    print("=" * 60)
    return results


if __name__ == "__main__":
    broadcast_all()
