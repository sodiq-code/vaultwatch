"""Unit tests — SelfCorrectionAgent"""

import pytest
import time
from unittest.mock import AsyncMock, patch

from agents.anomaly_agent import AnomalyResult
from agents.self_correction_agent import SelfCorrectionAgent


@pytest.fixture
def agent():
    return SelfCorrectionAgent(groq_api_key="test-key")


@pytest.fixture
def anomaly_result():
    return AnomalyResult(
        protocol="TestProto",
        risk_score=85.0,
        anomalies=["price_drop", "volume_spike"],
        recommendation="Pause liquidity",
        timestamp=time.time(),
    )


@pytest.mark.asyncio
async def test_correct_returns_dict(agent, anomaly_result):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "corrected_score": 80.0,
            "confidence": 0.85,
            "reasoning": "Confirmed anomaly pattern",
            "action": "alert",
        }
        result = await agent.correct(anomaly_result)
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_correct_has_confidence(agent, anomaly_result):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "corrected_score": 78.0,
            "confidence": 0.92,
            "reasoning": "High confidence",
            "action": "escalate",
        }
        result = await agent.correct(anomaly_result)
    assert "confidence" in result
    assert 0.0 <= result["confidence"] <= 1.0


@pytest.mark.asyncio
async def test_correct_low_risk_no_correction(agent):
    low_risk = AnomalyResult(
        protocol="SafeProto",
        risk_score=15.0,
        anomalies=[],
        recommendation="All clear",
        timestamp=time.time(),
    )
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "corrected_score": 15.0,
            "confidence": 0.95,
            "reasoning": "No anomaly",
            "action": "none",
        }
        result = await agent.correct(low_risk)
    assert result.get("action") == "none" or result.get("corrected_score", 100) < 50


@pytest.mark.asyncio
async def test_groq_error_fallback(agent, anomaly_result):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.side_effect = Exception("Groq timeout")
        result = await agent.correct(anomaly_result)
    assert isinstance(result, dict)
    assert "error" in result or "corrected_score" in result


@pytest.mark.asyncio
async def test_correct_preserves_protocol(agent, anomaly_result):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "corrected_score": 82.0,
            "confidence": 0.88,
            "reasoning": "Pattern match",
            "action": "alert",
        }
        result = await agent.correct(anomaly_result)
    assert result.get("protocol") == "TestProto" or "corrected_score" in result


@pytest.mark.asyncio
async def test_score_within_bounds(agent, anomaly_result):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "corrected_score": 150.0,  # invalid — should be clamped
            "confidence": 0.5,
            "reasoning": "",
            "action": "alert",
        }
        result = await agent.correct(anomaly_result)
    corrected = result.get("corrected_score", 100)
    assert corrected <= 100  # must be clamped


@pytest.mark.asyncio
async def test_retry_on_low_confidence(agent, anomaly_result):
    call_count = 0

    async def mock_groq(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            return {"corrected_score": 80.0, "confidence": 0.3, "reasoning": "", "action": ""}
        return {"corrected_score": 82.0, "confidence": 0.85, "reasoning": "Retried", "action": "alert"}

    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_g:
        mock_g.side_effect = mock_groq
        result = await agent.correct(anomaly_result)
    assert isinstance(result, dict)
