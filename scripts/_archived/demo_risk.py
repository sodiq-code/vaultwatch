#!/usr/bin/env python3
"""
VaultWatch — Risk Intelligence Demo
Demonstrates the full risk query + anomaly detection + self-correction flow.
"""

from __future__ import annotations

import os
import sys
import asyncio
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.intel_agent import IntelAgent
from agents.anomaly_agent import AnomalyAgent
from agents.self_correction_agent import SelfCorrectionAgent
from agents.safety_guard import SafetyGuard
from agents.audit_agent import AuditAgent
from casper_client import CasperContractClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("demo_risk")

GROQ_KEY = os.getenv("GROQ_API_KEY", "")

DEMO_PROTOCOLS = [
    {
        "name": "CasperSwap",
        "query": "What are the main risk factors for CasperSwap decentralised exchange on Casper network?",
        "metrics": {
            "protocol": "CasperSwap",
            "tvl": 12_000_000.0,
            "volume_24h": 18_500_000.0,
            "price_change_1h": -22.3,
            "num_transactions": 4200,
            "liquidity_ratio": 0.035,
        },
    },
    {
        "name": "CasperLend",
        "query": "Analyze the collateral and liquidation risk for CasperLend lending protocol.",
        "metrics": {
            "protocol": "CasperLend",
            "tvl": 45_000_000.0,
            "volume_24h": 3_200_000.0,
            "price_change_1h": 1.2,
            "num_transactions": 340,
            "liquidity_ratio": 0.72,
        },
    },
]


async def run_demo() -> None:
    print("\n" + "=" * 70)
    print("  VaultWatch — Risk Intelligence Demo")
    print("=" * 70)

    casper = CasperContractClient(mock=True)
    safety = SafetyGuard(groq_api_key=GROQ_KEY)
    intel = IntelAgent(groq_api_key=GROQ_KEY)
    anomaly = AnomalyAgent(groq_api_key=GROQ_KEY)
    correction = SelfCorrectionAgent(groq_api_key=GROQ_KEY)
    audit = AuditAgent(casper_client=casper)

    for i, protocol_data in enumerate(DEMO_PROTOCOLS, 1):
        name = protocol_data["name"]
        query = protocol_data["query"]
        metrics = protocol_data["metrics"]

        print(f"\n[{i}/{len(DEMO_PROTOCOLS)}] Protocol: {name}")
        print("-" * 50)

        # 1. Safety check
        print("  Step 1: Safety check...")
        safe_result = await safety.check(query)
        if not safe_result.get("safe", True):
            print(f"  [BLOCKED] Query failed safety: {safe_result.get('reason')}")
            continue
        print(f"  [OK] Safe — {safe_result.get('reason', 'approved')}")

        # 2. Risk intelligence
        print("  Step 2: Risk intelligence analysis...")
        analysis = await intel.analyze(query, protocol=name)
        print(f"  [INTEL] {analysis.get('summary', 'N/A')[:120]}")
        print(f"  [INTEL] Confidence: {analysis.get('confidence', 'N/A')}")

        # 3. Anomaly detection
        print("  Step 3: Anomaly detection...")
        anomaly_result = await anomaly.detect(metrics)
        print(f"  [ANOMALY] Score: {anomaly_result.risk_score:.1f}/100")
        if anomaly_result.anomalies:
            print(f"  [ANOMALY] Detected: {', '.join(anomaly_result.anomalies)}")
        print(f"  [ANOMALY] {anomaly_result.recommendation}")

        # 4. Self-correction (if high risk)
        if anomaly_result.risk_score >= 70:
            print("  Step 4: Self-correction (high risk triggered)...")
            corrected = await correction.correct(anomaly_result)
            print(f"  [CORRECTED] Score: {corrected.get('corrected_score', 'N/A')}")
            print(f"  [CORRECTED] Action: {corrected.get('action', 'N/A')}")
            print(f"  [CORRECTED] Confidence: {corrected.get('confidence', 'N/A')}")

        # 5. Audit
        print("  Step 5: Writing audit entry...")
        deploy_hash = await audit.record(
            action="risk_analysis_complete",
            actor="demo_script",
            details=f"protocol={name} score={anomaly_result.risk_score:.1f}",
        )
        print(f"  [AUDIT] Deploy hash: {deploy_hash[:32]}...")

    print("\n" + "=" * 70)
    print("  Demo complete. All risk flows executed.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(run_demo())
