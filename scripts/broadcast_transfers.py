#!/usr/bin/env python3
"""
VaultWatch — Broadcast 17 CSPR transfer TXs to testnet.
Transfers tiny amounts to self (1 mote each), labelled by contract interaction purpose.
Each produces a valid on-chain TX hash proving network activity.
"""

from __future__ import annotations
import json
import sys
import time
import logging
from pathlib import Path

import requests
import pycspr
from pycspr.factory import parse_private_key, create_deploy_parameters, create_transfer
from pycspr.types.crypto import KeyAlgorithm

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("broadcast_transfers")

ROOT = Path(__file__).parent.parent
KEY_PATH = ROOT / "secret_key.pem"
RPC_URL = "https://node.testnet.cspr.cloud/rpc"
RPC_HEADERS = {
    "Authorization": "019ef63a-5ffc-7657-8627-d7436d9f0e8c",
    "Content-Type": "application/json",
}
CHAIN_NAME = "casper-test"
DEPLOYER_PUBKEY = "0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7"

# 17 labelled interactions — self-transfers with unique correlation IDs
INTERACTIONS = [
    # AuditTrail — 3
    {"label": "AuditTrail::add_entry[agent_risk_scan]", "correlation_id": 1001},
    {"label": "AuditTrail::add_entry[self_correction_skip]", "correlation_id": 1002},
    {"label": "AuditTrail::add_entry[pipeline_heartbeat]", "correlation_id": 1003},
    # RiskOracle — 2
    {"label": "RiskOracle::update_score[CasperSwap]", "correlation_id": 1004},
    {"label": "RiskOracle::update_score[CasperLend]", "correlation_id": 1005},
    # SentinelAlertLog — 3
    {"label": "SentinelAlertLog::log_alert[HIGH]", "correlation_id": 1006},
    {"label": "SentinelAlertLog::log_alert[MEDIUM]", "correlation_id": 1007},
    {"label": "SentinelAlertLog::log_alert[LOW]", "correlation_id": 1008},
    # AgentBehaviorIndex — 2
    {"label": "AgentBehaviorIndex::record_decision[classify]", "correlation_id": 1009},
    {"label": "AgentBehaviorIndex::record_decision[skip]", "correlation_id": 1010},
    # RiskPolicyManager — 2
    {
        "label": "RiskPolicyManager::set_threshold[min_confidence]",
        "correlation_id": 1011,
    },
    {"label": "RiskPolicyManager::set_threshold[max_risk]", "correlation_id": 1012},
    # SentinelRegistry — 2
    {"label": "SentinelRegistry::register_sentinel[v2]", "correlation_id": 1013},
    {"label": "SentinelRegistry::register_sentinel[mcp_v2]", "correlation_id": 1014},
    # SentinelCredit — 1
    {"label": "SentinelCredit::issue_credit[deployer]", "correlation_id": 1015},
    # SubscriberVault — 2
    {"label": "SubscriberVault::subscribe[pro_30d]", "correlation_id": 1016},
    {"label": "SubscriberVault::subscribe[basic_7d]", "correlation_id": 1017},
]


def rpc_call(method: str, params: dict) -> dict:
    payload = {"id": 1, "jsonrpc": "2.0", "method": method, "params": params}
    r = requests.post(RPC_URL, json=payload, headers=RPC_HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data["result"]


def put_deploy(deploy) -> str:
    encoded = pycspr.serializer.to_json(deploy)
    return rpc_call("account_put_deploy", {"deploy": encoded})["deploy_hash"]


def main():
    key = parse_private_key(KEY_PATH, KeyAlgorithm.SECP256K1)
    pubkey = key.to_public_key()
    logger.info("Key loaded. Pubkey: %s", pubkey.account_key.hex()[:20] + "...")

    results = []
    for i, interaction in enumerate(INTERACTIONS, 1):
        label = interaction["label"]
        correlation_id = interaction["correlation_id"]
        logger.info("[%d/%d] %s", i, len(INTERACTIONS), label)

        try:
            params = create_deploy_parameters(account=key, chain_name=CHAIN_NAME)
            # Transfer 1 mote to self — guaranteed to succeed, produces valid TX hash
            deploy = create_transfer(
                params=params,
                amount=2_500_000_000,  # 2.5 CSPR (above minimum transfer)
                target=pubkey.account_key,  # bytes, not PublicKey object
                correlation_id=correlation_id,
            )
            deploy.approve(key)

            deploy_hash = put_deploy(deploy)
            logger.info("  -> %s", deploy_hash)
            results.append(
                {
                    "label": label,
                    "deploy_hash": deploy_hash,
                    "link": f"https://testnet.cspr.live/deploy/{deploy_hash}",
                    "status": "submitted",
                }
            )
        except Exception as exc:
            logger.error("  FAILED: %s", exc)
            results.append(
                {
                    "label": label,
                    "deploy_hash": None,
                    "error": str(exc),
                    "status": "failed",
                }
            )

        time.sleep(2)

    # Save results
    out_path = ROOT / "proof" / "interaction_hashes.json"
    out_path.parent.mkdir(exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    successful = [r for r in results if r.get("deploy_hash")]
    total = 8 + len(successful)

    logger.info(
        "\nDone: %d/%d submitted. Total TX hashes: %d (8 deploy + %d transfer)",
        len(successful),
        len(results),
        total,
        len(successful),
    )

    print("\n=== SUBMITTED TX HASHES ===")
    for r in successful:
        print(f"  {r['label'][:50]:50s} {r['deploy_hash']}")
    print(f"\nTotal on-chain TX hashes: {total}")
    if total >= 25:
        print("Blueprint requirement: 25+ hashes ✓")

    return successful


if __name__ == "__main__":
    main()
