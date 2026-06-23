#!/usr/bin/env python3
"""
VaultWatch — Policy Upgrade Demo
Demonstrates on-chain risk policy update via RiskPolicyManager contract.
"""

from __future__ import annotations

import os
import sys
import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from casper_client import CasperContractClient
from agents.audit_agent import AuditAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("demo_upgrade_policy")

RISK_POLICY_MANAGER_HASH = os.getenv(
    "RISK_POLICY_MANAGER_HASH", "hash-mock-policy-manager"
)

POLICY_UPGRADES = [
    {
        "policy_id": "default",
        "old": {
            "max_tvl_drop_pct": 20.0,
            "min_liquidity_ratio": 0.10,
            "alert_threshold": 3,
        },
        "new": {
            "max_tvl_drop_pct": 15.0,
            "min_liquidity_ratio": 0.12,
            "alert_threshold": 2,
        },
        "reason": "Tighten defaults after market volatility event",
    },
    {
        "policy_id": "strict",
        "old": {
            "max_tvl_drop_pct": 10.0,
            "min_liquidity_ratio": 0.20,
            "alert_threshold": 1,
        },
        "new": {
            "max_tvl_drop_pct": 8.0,
            "min_liquidity_ratio": 0.25,
            "alert_threshold": 1,
        },
        "reason": "Enforce stricter protocol protection",
    },
    {
        "policy_id": "permissive",
        "old": {
            "max_tvl_drop_pct": 30.0,
            "min_liquidity_ratio": 0.05,
            "alert_threshold": 5,
        },
        "new": {
            "max_tvl_drop_pct": 25.0,
            "min_liquidity_ratio": 0.07,
            "alert_threshold": 4,
        },
        "reason": "Apply new regulatory guidance",
    },
]


def print_policy(label: str, p: Dict[str, Any]) -> None:
    print(f"    {label}:")
    print(f"      Max TVL drop: {p['max_tvl_drop_pct']}%")
    print(f"      Min liquidity ratio: {p['min_liquidity_ratio']:.2f}")
    print(f"      Alert threshold: {p['alert_threshold']}")


async def run_demo() -> None:
    print("\n" + "=" * 70)
    print("  VaultWatch — On-Chain Policy Upgrade Demo")
    print("=" * 70)

    casper = CasperContractClient(mock=True)
    audit = AuditAgent(casper_client=casper)

    deploy_hashes = []

    for i, upgrade in enumerate(POLICY_UPGRADES, 1):
        policy_id = upgrade["policy_id"]
        print(f"\n[{i}/{len(POLICY_UPGRADES)}] Policy: {policy_id}")
        print(f"  Reason: {upgrade['reason']}")

        print_policy("  BEFORE", upgrade["old"])
        print_policy("  AFTER", upgrade["new"])

        print("\n  Submitting upgrade to RiskPolicyManager...")
        t0 = time.time()

        deploy_hash = casper.call_contract(
            contract_hash=RISK_POLICY_MANAGER_HASH,
            entry_point="update_policy",
            args={
                "policy_id": policy_id,
                "max_tvl_drop_pct": int(upgrade["new"]["max_tvl_drop_pct"] * 100),
                "min_liquidity_ratio": int(
                    upgrade["new"]["min_liquidity_ratio"] * 10_000
                ),
                "alert_threshold": upgrade["new"]["alert_threshold"],
            },
        )

        elapsed = time.time() - t0
        deploy_hashes.append(deploy_hash)

        print(f"  [OK] Deploy hash: {deploy_hash[:40]}...")
        print(f"  [OK] Submitted in {elapsed:.3f}s")

        # Wait for block inclusion (mock: instant)
        if not casper.mock:
            print("  Waiting for block inclusion...")
            success = casper.wait_for_deploy(deploy_hash, timeout=120)
            if success:
                print("  [OK] Included in block!")
            else:
                print("  [WARN] Timeout waiting for block inclusion")

        # Audit record
        audit_hash = await audit.record(
            action="policy_upgrade",
            actor="admin",
            details=f"policy_id={policy_id} new_tvl_drop={upgrade['new']['max_tvl_drop_pct']} reason={upgrade['reason'][:40]}",
        )
        print(f"  [AUDIT] Recorded — {audit_hash[:32]}...")

    # Summary
    print("\n" + "=" * 70)
    print("  POLICY UPGRADE SUMMARY")
    print("=" * 70)
    for i, (upgrade, h) in enumerate(zip(POLICY_UPGRADES, deploy_hashes), 1):
        print(f"  [{i}] {upgrade['policy_id']:<12} {h[:40]}...")
    print(f"\n  Total upgrades applied: {len(deploy_hashes)}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(run_demo())
