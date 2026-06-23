#!/usr/bin/env python3
"""
VaultWatch — Deploy Broadcaster
Broadcasts pre-signed deploy JSON files to Casper testnet.
Run this from a machine with network access to rpc.testnet.casperlabs.io.

Usage:
    python scripts/broadcast_deploys.py [--node-url https://rpc.testnet.casperlabs.io]
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import logging
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("broadcast_deploys")

from pycspr import NodeRpcClient, NodeRpcConnectionInfo
from pycspr import serializer as rpc_serializer
from pycspr.types.node.rpc.complex import Deploy

DEPLOYS_DIR = Path(__file__).parent.parent / "deploys"
NODE_URL = "https://rpc.testnet.casperlabs.io/rpc"

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


def make_client(node_url: str) -> NodeRpcClient:
    url = node_url.replace("https://", "").replace("http://", "").split("/")[0]
    host = url.split(":")[0]
    port = int(url.split(":")[-1]) if ":" in url else 443
    conn = NodeRpcConnectionInfo(host=host, port=port)
    return NodeRpcClient(conn)


async def wait_for_deploy(client: NodeRpcClient, deploy_hash: str, timeout: int = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            result = await client.get_deploy(deploy_hash)
            if result.get("execution_results"):
                return True
        except Exception:
            pass
        await asyncio.sleep(5)
    return False


async def broadcast_all(node_url: str) -> dict:
    client = make_client(node_url)
    results = {}

    for name in CONTRACT_ORDER:
        deploy_path = DEPLOYS_DIR / f"{name}_deploy.json"
        if not deploy_path.exists():
            logger.warning("Deploy file not found: %s — run export_signed_deploys.py first", deploy_path)
            continue

        logger.info("Broadcasting %s...", name)
        deploy_json = json.loads(deploy_path.read_text())

        # Reconstruct deploy from JSON and put it
        try:
            deploy_hash = await client.account_put_deploy(
                rpc_serializer.from_json(Deploy, deploy_json["deploy"])
            )
            if hasattr(deploy_hash, "hex"):
                deploy_hash = deploy_hash.hex()
            deploy_hash = str(deploy_hash)
            logger.info("%s broadcast — hash: %s", name, deploy_hash)
            results[name] = deploy_hash

            logger.info("Waiting for %s to be included...", name)
            ok = await wait_for_deploy(client, deploy_hash, timeout=120)
            if ok:
                logger.info("%s CONFIRMED on-chain!", name)
            else:
                logger.warning("%s not yet confirmed after 120s — hash saved, check explorer", name)

        except Exception as exc:
            logger.error("Failed to broadcast %s: %s", name, exc)
            results[name] = f"FAILED: {exc}"

    # Save results
    out = Path(__file__).parent.parent / "deploy_hashes_live.json"
    out.write_text(json.dumps(results, indent=2))
    logger.info("Results saved to %s", out)

    print("\n" + "=" * 60)
    print("BROADCAST SUMMARY")
    print("=" * 60)
    for name, h in results.items():
        status = "OK" if not str(h).startswith("FAILED") else "FAIL"
        print(f"  [{status}] {name:<25} {h[:32]}...")
    print("=" * 60)
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--node-url", default=NODE_URL, help="Casper node RPC URL")
    args = parser.parse_args()
    asyncio.run(broadcast_all(args.node_url))


if __name__ == "__main__":
    main()
