"""Integration test — AgentBehaviorIndex contract (mock Casper client)

Tests on-chain AI agent accountability: confidence scoring, correction rates,
safety rejection tracking, and trust score calculation.
Maps to AgentBehaviorIndex.rs on testnet.
"""

import pytest
from unittest.mock import MagicMock

from casper_client import CasperContractClient


@pytest.fixture
def mock_client():
    client = MagicMock(spec=CasperContractClient)
    client.mock = True

    _metrics: dict = {}
    _agent_count = {"n": 0}

    def mock_call_contract(
        contract_hash, entry_point, args, payment_amount=5_000_000_000
    ):
        if entry_point == "record_decision":
            name = args["agent_name"]
            confidence = args["confidence"]
            correction = args.get("correction_applied", False)
            rejected = args.get("safety_rejected", False)
            block = args.get("block_height", 0)

            if name not in _metrics:
                _agent_count["n"] += 1
                _metrics[name] = {
                    "agent_name": name,
                    "total_decisions": 0,
                    "corrections_applied": 0,
                    "safety_rejections": 0,
                    "avg_confidence": 0,
                    "high_confidence_count": 0,
                    "low_confidence_count": 0,
                    "last_updated_block": 0,
                    "trust_score": 100,
                }

            m = _metrics[name]
            m["total_decisions"] += 1
            total_conf = m["avg_confidence"] * (m["total_decisions"] - 1) + confidence
            m["avg_confidence"] = total_conf // m["total_decisions"]
            if correction:
                m["corrections_applied"] += 1
            if rejected:
                m["safety_rejections"] += 1
            if confidence >= 80:
                m["high_confidence_count"] += 1
            if confidence < 75:
                m["low_confidence_count"] += 1
            penalty = (m["corrections_applied"] + m["safety_rejections"]) * 5
            base = m["high_confidence_count"] * 100 // m["total_decisions"]
            m["trust_score"] = max(0, min(100, base - penalty))
            m["last_updated_block"] = block
            return f"hash-behavior-{name[:8]}-{m['total_decisions']:03d}"
        return "hash-unknown"

    def mock_query_state(contract_hash, path):
        if path[0] == "metrics" and len(path) > 1:
            return _metrics.get(path[1])
        if path[0] == "agent_count":
            return _agent_count["n"]
        if path[0] == "trust_score" and len(path) > 1:
            m = _metrics.get(path[1])
            return m["trust_score"] if m else 0
        return None

    client.call_contract.side_effect = mock_call_contract
    client.query_contract_state.side_effect = mock_query_state
    return client


def test_record_decision_returns_hash(mock_client):
    """record_decision entry point returns a valid deploy hash."""
    h = mock_client.call_contract(
        contract_hash="hash-agentbehavior",
        entry_point="record_decision",
        args={
            "agent_name": "AnomalyAgent",
            "confidence": 91,
            "correction_applied": False,
            "safety_rejected": False,
            "block_height": 1_500_000,
        },
    )
    assert isinstance(h, str)
    assert "hash-behavior" in h


def test_new_agent_registered_on_first_decision(mock_client):
    """First decision for an agent increments the agent count."""
    count_before = mock_client.query_contract_state(
        "hash-agentbehavior", ["agent_count"]
    )
    mock_client.call_contract(
        contract_hash="hash-agentbehavior",
        entry_point="record_decision",
        args={
            "agent_name": "ScannerAgent",
            "confidence": 95,
            "correction_applied": False,
            "safety_rejected": False,
            "block_height": 1_000_000,
        },
    )
    count_after = mock_client.query_contract_state(
        "hash-agentbehavior", ["agent_count"]
    )
    assert count_after == (count_before or 0) + 1


def test_confidence_averaging(mock_client):
    """avg_confidence rolls up correctly across multiple decisions."""
    for conf in [90, 80, 70]:
        mock_client.call_contract(
            contract_hash="hash-agentbehavior",
            entry_point="record_decision",
            args={
                "agent_name": "RWAAgent",
                "confidence": conf,
                "correction_applied": False,
                "safety_rejected": False,
                "block_height": 2_000_000,
            },
        )
    m = mock_client.query_contract_state("hash-agentbehavior", ["metrics", "RWAAgent"])
    assert m is not None
    assert m["total_decisions"] == 3
    assert m["avg_confidence"] == 80  # (90+80+70)//3


def test_correction_rate_tracked(mock_client):
    """corrections_applied increments only when correction_applied=True."""
    mock_client.call_contract(
        contract_hash="hash-agentbehavior",
        entry_point="record_decision",
        args={
            "agent_name": "SelfCorrectionAgent",
            "confidence": 88,
            "correction_applied": False,
            "safety_rejected": False,
            "block_height": 1_200_000,
        },
    )
    mock_client.call_contract(
        contract_hash="hash-agentbehavior",
        entry_point="record_decision",
        args={
            "agent_name": "SelfCorrectionAgent",
            "confidence": 70,
            "correction_applied": True,
            "safety_rejected": False,
            "block_height": 1_200_001,
        },
    )
    m = mock_client.query_contract_state(
        "hash-agentbehavior", ["metrics", "SelfCorrectionAgent"]
    )
    assert m["corrections_applied"] == 1
    assert m["total_decisions"] == 2


def test_trust_score_decreases_with_corrections(mock_client):
    """Trust score is penalised when corrections are applied."""
    # First: clean high-confidence decisions
    for _ in range(5):
        mock_client.call_contract(
            contract_hash="hash-agentbehavior",
            entry_point="record_decision",
            args={
                "agent_name": "AuditAgent",
                "confidence": 92,
                "correction_applied": False,
                "safety_rejected": False,
                "block_height": 1_300_000,
            },
        )
    m_clean = mock_client.query_contract_state(
        "hash-agentbehavior", ["metrics", "AuditAgent"]
    )
    clean_score = m_clean["trust_score"]

    # Now add corrections
    for _ in range(3):
        mock_client.call_contract(
            contract_hash="hash-agentbehavior",
            entry_point="record_decision",
            args={
                "agent_name": "AuditAgent",
                "confidence": 65,
                "correction_applied": True,
                "safety_rejected": False,
                "block_height": 1_300_010,
            },
        )
    m_penalised = mock_client.query_contract_state(
        "hash-agentbehavior", ["metrics", "AuditAgent"]
    )
    assert m_penalised["trust_score"] <= clean_score


def test_multiple_agents_tracked_independently(mock_client):
    """Metrics for different agents are stored independently."""
    agents = ["ScannerAgent", "AnomalyAgent", "IntelAgent"]
    confidences = [95, 70, 85]
    for agent, conf in zip(agents, confidences):
        mock_client.call_contract(
            contract_hash="hash-agentbehavior",
            entry_point="record_decision",
            args={
                "agent_name": agent,
                "confidence": conf,
                "correction_applied": False,
                "safety_rejected": False,
                "block_height": 1_400_000,
            },
        )
    for agent, conf in zip(agents, confidences):
        m = mock_client.query_contract_state("hash-agentbehavior", ["metrics", agent])
        assert m is not None
        assert m["avg_confidence"] == conf
        assert m["agent_name"] == agent
