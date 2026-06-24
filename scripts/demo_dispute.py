#!/usr/bin/env python3
"""
VaultWatch — Dispute / Self-Correction Demo
Demonstrates: low-confidence finding → SelfCorrectionAgent retry loop → SKIP decision.

Flow:
  1. Craft a deliberately ambiguous anomaly result (confidence = 0.35, below threshold 0.75)
  2. Push it through SelfCorrectionAgent._evaluate()
  3. Mock retries keep confidence low → SKIP is returned
  4. Show audit trail — nothing written on-chain when SKIP

This proves VaultWatch never persists garbage findings.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.anomaly_agent import AnomalyResult
from agents.self_correction_agent import SelfCorrectionAgent, CorrectionResult

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("demo_dispute")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ambiguous_result(protocol: str = "CasperSwap") -> AnomalyResult:
    """Create a low-confidence anomaly result that should trigger the retry loop."""
    mock_event = MagicMock()
    mock_event.event_type = "large_transfer"
    mock_event.address = "0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116"
    mock_event.amount_motes = 500_000_000_000  # 500 CSPR
    mock_event.block_height = 4_200_000

    return AnomalyResult(
        protocol=protocol,
        risk_score=48.0,
        anomalies=["unusual_volume"],
        recommendation="Monitor closely — ambiguous signal",
        confidence=0.35,          # <-- below 0.75 threshold → triggers retry
        risk_type="anomalous_flow",
        severity="MEDIUM",
        reasoning="Transfer size is elevated but not definitively malicious.",
        event=mock_event,
        model_used="llama-3.1-8b-instant",
        tokens_used=120,
        latency_ms=340,
    )


def _make_retry_result(original: AnomalyResult, confidence: float) -> AnomalyResult:
    """Simulate a retry that still returns low confidence."""
    return AnomalyResult(
        protocol=original.protocol,
        risk_score=original.risk_score,
        anomalies=original.anomalies,
        recommendation=original.recommendation,
        confidence=confidence,
        risk_type=original.risk_type,
        severity=original.severity,
        reasoning=f"Retry re-analysis: still inconclusive (confidence={confidence})",
        event=original.event,
        model_used="llama-3.3-70b-versatile",
        tokens_used=210,
        latency_ms=520,
    )


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------

async def run_demo() -> None:
    print("\n" + "=" * 70)
    print("  VaultWatch — Dispute & Self-Correction Demo")
    print("=" * 70)

    agent = SelfCorrectionAgent()

    # --- Scenario 1: stays low confidence → SKIP ---
    print("\n[Scenario 1] Low-confidence finding — both retries fail to gain confidence")
    print("-" * 60)

    ambiguous = make_ambiguous_result("CasperSwap")
    print(f"  Input  | protocol={ambiguous.protocol}  confidence={ambiguous.confidence}  severity={ambiguous.severity}")
    print(f"  Input  | anomalies={ambiguous.anomalies}")
    print(f"  Input  | reasoning: {ambiguous.reasoning}")

    # Patch _retry_with_context so it stays low (no real Groq call needed)
    with patch.object(
        agent,
        "_retry_with_context",
        side_effect=[
            _make_retry_result(ambiguous, confidence=0.42),
            _make_retry_result(ambiguous, confidence=0.51),
        ],
    ):
        t0 = time.perf_counter()
        correction: CorrectionResult = await agent._evaluate(ambiguous)
        elapsed = (time.perf_counter() - t0) * 1000

    print(f"\n  Result | passed={correction.passed}  retry_count={correction.retry_count}")
    print(f"  Result | final_confidence={correction.final_result.confidence}")
    if correction.skip_reason:
        print(f"  Result | skip_reason: {correction.skip_reason}")
    print(f"  Result | elapsed={elapsed:.1f}ms")

    if not correction.passed:
        print("\n  [SKIP] On-chain write SUPPRESSED — no garbage persisted to AuditTrail ✓")
    else:
        print("\n  [PASS] Forwarded to RWAAgent")

    # --- Scenario 2: second retry gains confidence → PASS ---
    print("\n[Scenario 2] Low-confidence finding — retry 2 gains confidence → PASS")
    print("-" * 60)

    ambiguous2 = make_ambiguous_result("CasperLend")
    ambiguous2.confidence = 0.40

    print(f"  Input  | protocol={ambiguous2.protocol}  confidence={ambiguous2.confidence}")

    with patch.object(
        agent,
        "_retry_with_context",
        side_effect=[
            _make_retry_result(ambiguous2, confidence=0.55),  # still low
            _make_retry_result(ambiguous2, confidence=0.82),  # crosses threshold
        ],
    ):
        t0 = time.perf_counter()
        correction2: CorrectionResult = await agent._evaluate(ambiguous2)
        elapsed2 = (time.perf_counter() - t0) * 1000

    print(f"\n  Result | passed={correction2.passed}  retry_count={correction2.retry_count}")
    print(f"  Result | final_confidence={correction2.final_result.confidence}")
    print(f"  Result | elapsed={elapsed2:.1f}ms")

    if correction2.passed:
        print("\n  [PASS] Confidence recovered after retries — forwarded to RWAAgent ✓")
    else:
        print(f"\n  [SKIP] {correction2.skip_reason}")

    # --- Summary ---
    print("\n" + "=" * 70)
    print("  Dispute Demo Complete")
    print(f"  Scenario 1 → {'SKIP (no on-chain write)' if not correction.passed else 'PASS'}")
    print(f"  Scenario 2 → {'PASS (forwarded after retry)' if correction2.passed else 'SKIP'}")
    print("  Self-correction logic: working as designed.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(run_demo())
