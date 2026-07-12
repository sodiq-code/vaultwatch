"""
VaultWatch Reputation Engine — Hybrid Brier + Escrow-Derived Formula

This module implements the published reputation formula described in
docs/REPUTATION_FORMULA.md. It is the single most important differentiator
for VaultWatch — a defensible reputation primitive that scores BOTH the AI
agents (Brier) AND the human/protocol subscribers (escrow-derived) in one
formula.

Two sub-scores:
  1. Agent Brier Score (B)  — measures AI prediction accuracy over time.
     Lower Brier = better. We invert and normalize to [0,100].
     Source: AgentBehaviorIndex on-chain metrics (confidence, corrections,
     safety_rejections, decision outcomes).
  2. Escrow Trust Score (E) — measures economic stake and slash history.
     Higher = better. Already [0,100].
     Source: SentinelCredit + SubscriberVault (deposits, slash events,
     successful query count).

Final reputation:
  R = w_B * (100 - normalized_Brier) + w_E * escrow_trust
  Default weights: w_B = 0.6, w_E = 0.4 (AI accuracy weighted higher
  because VaultWatch's core value is agent intelligence; escrow is the
  economic backstop).

The formula is deterministic, on-chain-verifiable, and accompanied by a
12-check red-team checklist (docs/RED_TEAM_CHECKLIST.md).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from opentelemetry import trace

tracer = trace.get_tracer("vaultwatch.reputation")

# ─── Default weights ─────────────────────────────────────────────────────────
DEFAULT_W_BRIER = 0.6  # weight on agent prediction accuracy
DEFAULT_W_ESCROW = 0.4  # weight on economic stake / slash history

# EWMA decay for Brier (matches Pantheon's approach). lambda = 0.92 means
# a prediction 10 cycles ago carries 0.92^10 ≈ 43% weight vs. the latest.
EWMA_LAMBDA = 0.92


@dataclass
class AgentPrediction:
    """A single agent prediction with realized outcome. Used for Brier scoring."""

    agent_name: str
    predicted_probability: float  # the agent's confidence, 0.0–1.0
    outcome: float  # realized: 1.0 = event happened, 0.0 = didn't
    timestamp: float = field(default_factory=time.time)
    # weight for EWMA (older = lower)


@dataclass
class EscrowStake:
    """A subscriber's economic position. Used for escrow-derived score."""

    address: str
    escrowed_balance_motes: int  # from SubscriberVault
    total_deposited_motes: int  # from SentinelCredit + SubscriberVault
    total_spent_motes: int  # queries consumed
    slash_count: int  # number of times slashed (penalty events)
    successful_queries: int  # queries served without dispute
    disputed_queries: int  # queries that were disputed/resolved against


def brier_score(predictions: list[AgentPrediction]) -> float:
    """Compute the raw Brier score (lower = better, range [0, 2] for binary).

    Brier = (1/N) * Σ (p_i - o_i)^2

    With EWMA decay:
    Brier_ewma = Σ w_i * (p_i - o_i)^2  /  Σ w_i
    where w_i = λ^(N - i)  (most recent = i=N, weight=λ^0=1)
    """
    if not predictions:
        return 0.5  # neutral — no data
    # Sort by timestamp ascending so i=0 is oldest
    preds = sorted(predictions, key=lambda p: p.timestamp)
    n = len(preds)
    weighted_sum = 0.0
    weight_total = 0.0
    for i, p in enumerate(preds):
        w = EWMA_LAMBDA ** (n - 1 - i)  # most recent (i=n-1) → w=1
        weighted_sum += w * (p.predicted_probability - p.outcome) ** 2
        weight_total += w
    return weighted_sum / weight_total if weight_total > 0 else 0.5


def normalize_brier_to_trust(b: float) -> float:
    """Convert raw Brier [0, 2] → trust [0, 100].

    Brier=0  → perfect predictions → trust=100
    Brier=0.5→ random guessing     → trust=50
    Brier=2  → perfectly wrong     → trust=0
    Formula: trust = 100 * (1 - brier/2)
    """
    return max(0.0, min(100.0, 100.0 * (1.0 - b / 2.0)))


def escrow_trust(stake: EscrowStake) -> float:
    """Escrow-derived trust score [0, 100].

    Combines:
      - Log-scaled escrow stake (1 CSPR ≈ 30 pts, 1000 CSPR ≈ 60, 1M CSPR ≈ 90)
      - Slash penalty: -10 pts per slash, floor 0
      - Successful-query bonus: +1 pt per query (capped +20)
      - Dispute penalty: -5 pts per dispute

    This mirrors CTL's escrow-derived approach but is open and on-chain
    verifiable via SentinelCredit + SubscriberVault.
    """
    # Log-scaled stake: log10(motes + 1) gives smooth growth
    # 1 CSPR = 1e9 motes → log10(1e9) ≈ 9 → 9 * 6.67 ≈ 60 pts
    # 1000 CSPR = 1e12 motes → log10(1e12) = 12 → 80 pts
    motes = stake.escrowed_balance_motes
    stake_pts = min(60.0, math.log10(motes + 1) * 6.67)  # cap at 60

    slash_penalty = min(40.0, stake.slash_count * 10.0)
    query_bonus = min(20.0, float(stake.successful_queries))
    dispute_penalty = min(15.0, stake.disputed_queries * 5.0)

    score = 30.0 + stake_pts - slash_penalty + query_bonus - dispute_penalty
    return max(0.0, min(100.0, score))


def hybrid_reputation(
    predictions: list[AgentPrediction],
    stake: EscrowStake,
    w_brier: float = DEFAULT_W_BRIER,
    w_escrow: float = DEFAULT_W_ESCROW,
) -> dict:
    """Compute the full hybrid reputation score.

    Returns a dict suitable for on-chain attestation via the
    agent_attestation MCP tool. Every field is verifiable against
    AgentBehaviorIndex + SentinelCredit + SubscriberVault contract state.
    """
    with tracer.start_as_current_span("reputation.compute") as span:
        b = brier_score(predictions)
        brier_trust = normalize_brier_to_trust(b)
        escrow = escrow_trust(stake)

        # Final weighted reputation
        reputation = (w_brier * brier_trust) + (w_escrow * escrow)

        # Tier for UI/attestation
        if reputation >= 85:
            tier = "PLATINUM"
        elif reputation >= 70:
            tier = "GOLD"
        elif reputation >= 50:
            tier = "SILVER"
        else:
            tier = "BRONZE"

        span.set_attribute("reputation.brier_raw", b)
        span.set_attribute("reputation.brier_trust", brier_trust)
        span.set_attribute("reputation.escrow_trust", escrow)
        span.set_attribute("reputation.final", reputation)
        span.set_attribute("reputation.tier", tier)

        return {
            "agent_address": stake.address,
            "reputation_score": round(reputation, 2),
            "tier": tier,
            "components": {
                "brier": {
                    "raw_score": round(b, 4),
                    "trust_normalized": round(brier_trust, 2),
                    "weight": w_brier,
                    "prediction_count": len(predictions),
                    "ewma_lambda": EWMA_LAMBDA,
                },
                "escrow": {
                    "trust_score": round(escrow, 2),
                    "weight": w_escrow,
                    "escrowed_balance_motes": stake.escrowed_balance_motes,
                    "slash_count": stake.slash_count,
                    "successful_queries": stake.successful_queries,
                    "disputed_queries": stake.disputed_queries,
                },
            },
            "formula": "R = w_B * (100 - Brier/2 * 100) + w_E * escrow_trust",
            "weights": {"w_brier": w_brier, "w_escrow": w_escrow},
            "computed_at": int(time.time()),
            "verifiable_on_chain": True,
            "on_chain_sources": [
                "AgentBehaviorIndex.get_metrics(agent_name)",
                "SentinelCredit.get_account(address)",
                "SubscriberVault.get_account(address)",
            ],
        }


# ─── Convenience: build a prediction history from on-chain metrics ──────────
def predictions_from_agent_metrics(
    agent_name: str,
    total_decisions: int,
    high_confidence_count: int,
    corrections_applied: int,
    safety_rejections: int,
    avg_confidence: int,
) -> list[AgentPrediction]:
    """Reconstruct a synthetic prediction history from on-chain aggregates.

    The AgentBehaviorIndex contract stores cumulative counters, not a full
    prediction log. We reconstruct a representative history:
      - high_confidence_count decisions were predicted at p=0.85, outcome=1
        (correct high-confidence calls)
      - corrections_applied were predicted at p=0.7, outcome=0 (corrected =
        the original prediction was wrong)
      - safety_rejections were predicted at p=0.6, outcome=0 (blocked =
        the prediction was deemed unsafe → treat as wrong)
      - remaining decisions at p=0.5, outcome=0.5 (neutral)

    This is documented in REPUTATION_FORMULA.md §4 as the "aggregate
    reconstruction" method. For full precision, a future contract upgrade
    could store a rolling prediction log on-chain.
    """
    preds: list[AgentPrediction] = []
    base_t = time.time() - total_decisions * 60  # 1 decision per minute

    for i in range(high_confidence_count):
        preds.append(AgentPrediction(agent_name, 0.85, 1.0, base_t + i * 60))
    for i in range(corrections_applied):
        preds.append(AgentPrediction(agent_name, 0.70, 0.0, base_t + (high_confidence_count + i) * 60))
    for i in range(safety_rejections):
        preds.append(AgentPrediction(agent_name, 0.60, 0.0, base_t + (high_confidence_count + corrections_applied + i) * 60))
    # Remaining neutral decisions
    remaining = total_decisions - high_confidence_count - corrections_applied - safety_rejections
    for i in range(max(0, remaining)):
        p = (avg_confidence / 100.0) if avg_confidence else 0.5
        preds.append(AgentPrediction(agent_name, p, 0.5, base_t + (high_confidence_count + corrections_applied + safety_rejections + i) * 60))
    return preds


def reputation_for_agent(
    agent_name: str,
    agent_metrics: dict,  # from AgentBehaviorIndex.get_metrics()
    escrow_stake: EscrowStake,
) -> dict:
    """End-to-end: on-chain metrics → hybrid reputation. Used by MCP tool."""
    preds = predictions_from_agent_metrics(
        agent_name=agent_name,
        total_decisions=agent_metrics.get("total_decisions", 0),
        high_confidence_count=agent_metrics.get("high_confidence_count", 0),
        corrections_applied=agent_metrics.get("corrections_applied", 0),
        safety_rejections=agent_metrics.get("safety_rejections", 0),
        avg_confidence=agent_metrics.get("avg_confidence", 0),
    )
    return hybrid_reputation(preds, escrow_stake)
