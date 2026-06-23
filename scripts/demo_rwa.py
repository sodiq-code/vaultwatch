#!/usr/bin/env python3
"""
VaultWatch — RWA Assessment Demo
Demonstrates real-world asset evaluation for on-chain tokenisation.
"""

from __future__ import annotations

import os
import sys
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.rwa_agent import RWAAgent
from agents.audit_agent import AuditAgent
from casper_client import CasperContractClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("demo_rwa")

GROQ_KEY = os.getenv("GROQ_API_KEY", "")

RWA_ASSETS = [
    {
        "asset_id": "ng-tbill-91d-001",
        "asset_type": "treasury_bill",
        "issuer": "Central Bank of Nigeria",
        "collateral_ratio": 1.05,
        "maturity_days": 91,
        "credit_rating": "B+",
        "description": "Nigerian 91-day Treasury Bill",
    },
    {
        "asset_id": "us-t10y-2026-042",
        "asset_type": "treasury_bond",
        "issuer": "US Department of Treasury",
        "collateral_ratio": 1.02,
        "maturity_days": 3650,
        "credit_rating": "AAA",
        "description": "US 10-Year Treasury Bond",
    },
    {
        "asset_id": "corp-bond-risky-001",
        "asset_type": "corporate_bond",
        "issuer": "HighYield Corp Ltd",
        "collateral_ratio": 0.75,
        "maturity_days": 730,
        "credit_rating": "CCC",
        "description": "High-yield corporate bond (junk)",
    },
    {
        "asset_id": "real-estate-dubai-001",
        "asset_type": "real_estate",
        "issuer": "Dubai REIT Fund",
        "collateral_ratio": 1.45,
        "maturity_days": 1825,
        "credit_rating": "BBB",
        "description": "Dubai real estate tokenised fund",
    },
    {
        "asset_id": "gold-xau-vault-001",
        "asset_type": "commodity",
        "issuer": "VaultGold Custody",
        "collateral_ratio": 1.00,
        "maturity_days": 0,  # perpetual
        "credit_rating": "AA",
        "description": "Gold-backed token (1oz = 1 token)",
    },
]


async def run_demo() -> None:
    print("\n" + "=" * 70)
    print("  VaultWatch — Real-World Asset (RWA) Assessment Demo")
    print("=" * 70)

    casper = CasperContractClient(mock=True)
    rwa_agent = RWAAgent(groq_api_key=GROQ_KEY)
    audit = AuditAgent(casper_client=casper)

    results_summary = []

    for i, asset in enumerate(RWA_ASSETS, 1):
        print(f"\n[{i}/{len(RWA_ASSETS)}] {asset['description']}")
        print(f"  ID: {asset['asset_id']}")
        print(f"  Type: {asset['asset_type']} | Issuer: {asset['issuer']}")
        print(
            f"  Collateral: {asset['collateral_ratio']:.2f}x | Rating: {asset['credit_rating']}"
        )
        print(f"  Maturity: {asset['maturity_days']}d")
        print("-" * 50)

        asset_data = {k: v for k, v in asset.items() if k != "description"}
        result = await rwa_agent.assess(asset_data)

        verdict = result.get("verdict", "UNKNOWN")
        risk_score = result.get("risk_score", "N/A")
        notes = result.get("notes", "")

        verdict_icon = "✓" if verdict == "APPROVED" else "✗"
        print(f"  [{verdict_icon}] Verdict: {verdict}")
        print(f"  Risk Score: {risk_score}")
        if notes:
            print(f"  Notes: {notes[:100]}")

        # Write to on-chain audit log
        await audit.record(
            action="rwa_assessment",
            actor="demo_rwa",
            details=f"asset_id={asset['asset_id']} verdict={verdict} score={risk_score}",
        )

        results_summary.append(
            {
                "asset": asset["description"],
                "verdict": verdict,
                "risk_score": risk_score,
            }
        )

    # Summary table
    print("\n" + "=" * 70)
    print("  ASSESSMENT SUMMARY")
    print("=" * 70)
    print(f"  {'Asset':<40} {'Verdict':<12} {'Score'}")
    print(f"  {'-' * 40} {'-' * 12} {'-' * 5}")
    for r in results_summary:
        icon = "✓" if r["verdict"] == "APPROVED" else "✗"
        print(f"  [{icon}] {r['asset']:<38} {r['verdict']:<12} {r['risk_score']}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(run_demo())
