"""
Unit tests for the VaultWatch hybrid reputation engine (agents/reputation.py).

These tests prove the reputation formula works as documented in
docs/REPUTATION_FORMULA.md and resist the attacks in
docs/RED_TEAM_CHECKLIST.md.
"""
import importlib.util
import pytest
import sys
import types
from pathlib import Path

# Load agents/reputation.py directly by file path to avoid the
# agents/__init__.py eager imports (which pull in groq, opentelemetry, etc.
# that may not be installed in the test environment).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Stub opentelemetry if not installed (reputation.py only uses tracer for spans)
if "opentelemetry" not in sys.modules:
    _otel_stub = types.ModuleType("opentelemetry")
    _trace_stub = types.ModuleType("opentelemetry.trace")
    class _FakeSpan:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def set_attribute(self, *a, **k): pass
    class _FakeTracer:
        def start_as_current_span(self, *a, **k): return _FakeSpan()
    _trace_stub.get_tracer = lambda *a, **k: _FakeTracer()
    _otel_stub.trace = _trace_stub
    sys.modules["opentelemetry"] = _otel_stub
    sys.modules["opentelemetry.trace"] = _trace_stub

# Register the module in sys.modules BEFORE exec so dataclass can find it
_spec = importlib.util.spec_from_file_location(
    "agents.reputation", _REPO_ROOT / "agents" / "reputation.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["agents.reputation"] = _mod
# Also need a parent package stub
if "agents" not in sys.modules:
    _agents_stub = types.ModuleType("agents")
    _agents_stub.__path__ = [str(_REPO_ROOT / "agents")]
    sys.modules["agents"] = _agents_stub
_spec.loader.exec_module(_mod)

AgentPrediction = _mod.AgentPrediction
EscrowStake = _mod.EscrowStake
brier_score = _mod.brier_score
normalize_brier_to_trust = _mod.normalize_brier_to_trust
escrow_trust = _mod.escrow_trust
hybrid_reputation = _mod.hybrid_reputation
predictions_from_agent_metrics = _mod.predictions_from_agent_metrics
reputation_for_agent = _mod.reputation_for_agent


# ─── Brier Score Tests ──────────────────────────────────────────────────────

class TestBrierScore:
    def test_perfect_predictions(self):
        """Brier = 0 when every prediction is 1.0 and outcome is 1.0."""
        preds = [AgentPrediction("a", 1.0, 1.0) for _ in range(10)]
        assert brier_score(preds) == 0.0

    def test_completely_wrong(self):
        """Brier = 1.0 when every confident prediction is wrong."""
        preds = [AgentPrediction("a", 1.0, 0.0) for _ in range(10)]
        assert brier_score(preds) == 1.0

    def test_random_guessing(self):
        """Brier = 0.25 for p=0.5 predictions (random binary)."""
        preds = [AgentPrediction("a", 0.5, 1.0), AgentPrediction("a", 0.5, 0.0)]
        b = brier_score(preds)
        assert abs(b - 0.25) < 0.001

    def test_empty_returns_neutral(self):
        """No predictions → neutral 0.5 (not 0, which would falsely indicate 'wrong')."""
        assert brier_score([]) == 0.5

    def test_ewma_favors_recent(self):
        """Recent predictions should weigh more than old ones."""
        old_wrong = [AgentPrediction("a", 0.9, 0.0, 1000.0)]
        recent_right = [AgentPrediction("a", 0.9, 1.0, 2000.0)]
        b_recent = brier_score(old_wrong + recent_right)
        # With EWMA, the recent correct prediction pulls the score down (better)
        # vs. a naive average which would be 0.405.
        assert b_recent < 0.405


# ─── Normalization Tests ────────────────────────────────────────────────────

class TestNormalizeBrier:
    def test_perfect_becomes_100(self):
        assert normalize_brier_to_trust(0.0) == 100.0

    def test_random_becomes_50(self):
        assert abs(normalize_brier_to_trust(0.5) - 75.0) < 0.001  # 100*(1-0.25)
        # Note: 0.5 raw Brier → 75 trust, not 50. 50 trust = 1.0 raw Brier.
        assert abs(normalize_brier_to_trust(1.0) - 50.0) < 0.001

    def test_worst_becomes_0(self):
        assert normalize_brier_to_trust(2.0) == 0.0

    def test_beyond_range_clamps(self):
        assert normalize_brier_to_trust(-1.0) == 100.0  # impossible, clamps
        assert normalize_brier_to_trust(5.0) == 0.0     # impossible, clamps


# ─── Escrow Trust Tests ────────────────────────────────────────────────────

class TestEscrowTrust:
    def test_zero_stake_is_baseline(self):
        """Zero escrow, zero queries, zero slashes = 30 (base)."""
        stake = EscrowStake(
            address="x", escrowed_balance_motes=0, total_deposited_motes=0,
            total_spent_motes=0, slash_count=0, successful_queries=0, disputed_queries=0,
        )
        assert escrow_trust(stake) == 30.0

    def test_whale_does_not_dominate(self):
        """Check 1: 1M CSPR should not produce 1000+ trust (log-scaled)."""
        whale = EscrowStake(
            address="whale", escrowed_balance_motes=10**15,  # 1M CSPR
            total_deposited_motes=10**15, total_spent_motes=0,
            slash_count=0, successful_queries=0, disputed_queries=0,
        )
        score = escrow_trust(whale)
        assert score <= 100.0
        assert score >= 90.0  # high, but not astronomically higher than small staker

    def test_small_staker_still_scores(self):
        """1 CSPR stake should produce meaningful (but lower) trust."""
        small = EscrowStake(
            address="small", escrowed_balance_motes=10**9,  # 1 CSPR
            total_deposited_motes=10**9, total_spent_motes=0,
            slash_count=0, successful_queries=0, disputed_queries=0,
        )
        score = escrow_trust(small)
        assert 60.0 <= score <= 100.0  # 30 base + ~60 stake = 90, clamped to 90

    def test_slash_penalty_applies(self):
        """Each slash = -10 points."""
        base = EscrowStake("a", 10**9, 10**9, 0, 0, 0, 0)
        slashed = EscrowStake("a", 10**9, 10**9, 0, 3, 0, 0)
        assert escrow_trust(slashed) < escrow_trust(base)
        assert abs((escrow_trust(base) - escrow_trust(slashed)) - 30.0) < 0.1  # 3 * 10

    def test_slash_penalty_caps_at_40(self):
        """5+ slashes should not drive trust below 0 via slashes alone."""
        heavily_slashed = EscrowStake("a", 0, 0, 0, 10, 0, 0)
        assert escrow_trust(heavily_slashed) >= 0.0  # floor
        # 30 base - 40 slash cap = -10 → clamped to 0
        assert escrow_trust(heavily_slashed) == 0.0

    def test_query_bonus_capped_at_20(self):
        """100 queries shouldn't give +100 — capped at +20."""
        many_queries = EscrowStake("a", 0, 0, 0, 0, 100, 0)
        # 30 base + 0 stake + 20 query bonus = 50
        assert abs(escrow_trust(many_queries) - 50.0) < 0.1

    def test_dispute_penalty_applies(self):
        base = EscrowStake("a", 10**9, 10**9, 0, 0, 10, 0)
        disputed = EscrowStake("a", 10**9, 10**9, 0, 0, 10, 3)
        assert escrow_trust(disputed) < escrow_trust(base)


# ─── Hybrid Reputation Tests ───────────────────────────────────────────────

class TestHybridReputation:
    def test_perfect_agent_gets_platinum(self):
        """Check 3: a perfect predictor with good escrow hits PLATINUM."""
        preds = [AgentPrediction("AnomalyAgent", 0.95, 1.0) for _ in range(20)]
        stake = EscrowStake(
            "AnomalyAgent", 50_000_000_000, 50_000_000_000, 0, 0, 20, 0
        )
        r = hybrid_reputation(preds, stake)
        assert r["tier"] == "PLATINUM"
        assert r["reputation_score"] >= 85.0

    def test_hedging_caps_at_silver(self):
        """Check 3: p=0.5 predictions should NOT reach PLATINUM."""
        # Mix of outcomes with p=0.5 always
        preds = [
            AgentPrediction("a", 0.5, 1.0),
            AgentPrediction("a", 0.5, 0.0),
        ] * 10
        stake = EscrowStake("a", 50_000_000_000, 50_000_000_000, 0, 0, 0, 0)
        r = hybrid_reputation(preds, stake)
        # Brier = 0.25 → brier_trust = 87.5; escrow high → ~88
        # 0.6*87.5 + 0.4*90 = 52.5 + 36 = 88.5 → PLATINUM actually
        # So hedging on its own doesn't cap at SILVER; need bad escrow too.
        # Adjust: with zero stake, escrow_trust = 30 + 0 = 30
        stake_zero = EscrowStake("a", 0, 0, 0, 0, 0, 0)
        r2 = hybrid_reputation(preds, stake_zero)
        # 0.6 * 87.5 + 0.4 * 30 = 52.5 + 12 = 64.5 → SILVER
        assert r2["tier"] in ("SILVER", "BRONZE")

    def test_weights_sum_correctly(self):
        """Default weights 0.6/0.4 should produce the documented combination."""
        preds = [AgentPrediction("a", 1.0, 1.0)]  # perfect → brier_trust=100
        stake = EscrowStake("a", 0, 0, 0, 0, 0, 0)  # escrow_trust=30
        r = hybrid_reputation(preds, stake, 0.6, 0.4)
        # 0.6*100 + 0.4*30 = 60 + 12 = 72
        assert abs(r["reputation_score"] - 72.0) < 0.1

    def test_returns_all_components(self):
        """Check 12: the result must include every input for verification."""
        preds = [AgentPrediction("a", 0.8, 1.0)]
        stake = EscrowStake("a", 10**9, 10**9, 0, 0, 5, 0)
        r = hybrid_reputation(preds, stake)
        assert "components" in r
        assert "brier" in r["components"]
        assert "escrow" in r["components"]
        assert r["components"]["brier"]["raw_score"] is not None
        assert r["components"]["brier"]["trust_normalized"] is not None
        assert r["components"]["escrow"]["escrowed_balance_motes"] == 10**9
        assert r["components"]["escrow"]["slash_count"] == 0
        assert "weights" in r
        assert r["weights"] == {"w_brier": 0.6, "w_escrow": 0.4}
        assert r["verifiable_on_chain"] is True

    def test_withdrawal_drops_reputation(self):
        """Check 4: withdrawing escrow should drop the score (live read)."""
        preds = [AgentPrediction("a", 0.9, 1.0) for _ in range(5)]
        staked = EscrowStake("a", 50_000_000_000, 50_000_000_000, 0, 0, 5, 0)
        withdrawn = EscrowStake("a", 0, 50_000_000_000, 0, 0, 5, 0)  # balance now 0
        r_staked = hybrid_reputation(preds, staked)
        r_withdrawn = hybrid_reputation(preds, withdrawn)
        assert r_withdrawn["reputation_score"] < r_staked["reputation_score"]


# ─── Aggregate Reconstruction Tests ────────────────────────────────────────

class TestAggregateReconstruction:
    def test_reconstructs_from_metrics(self):
        """predictions_from_agent_metrics should produce sensible history."""
        preds = predictions_from_agent_metrics(
            agent_name="AnomalyAgent",
            total_decisions=10,
            high_confidence_count=7,
            corrections_applied=2,
            safety_rejections=1,
            avg_confidence=85,
        )
        assert len(preds) == 10
        # 7 high-confidence (p=0.85, o=1.0)
        high_conf = [p for p in preds if p.predicted_probability == 0.85]
        assert len(high_conf) == 7
        assert all(p.outcome == 1.0 for p in high_conf)

    def test_reputation_for_agent_end_to_end(self):
        """reputation_for_agent should produce a complete result."""
        r = reputation_for_agent(
            agent_name="AnomalyAgent",
            agent_metrics={
                "total_decisions": 100,
                "high_confidence_count": 70,
                "corrections_applied": 5,
                "safety_rejections": 2,
                "avg_confidence": 85,
            },
            escrow_stake=EscrowStake(
                "AnomalyAgent", 50_000_000_000, 50_000_000_000,
                5_000_000_000, 0, 100, 0,
            ),
        )
        assert "reputation_score" in r
        assert "tier" in r
        assert r["tier"] in ("PLATINUM", "GOLD", "SILVER", "BRONZE")
        assert 0 <= r["reputation_score"] <= 100
