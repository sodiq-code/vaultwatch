"""Unit tests — AnomalyAgent"""

import pytest
import time
from unittest.mock import AsyncMock, patch

from agents.anomaly_agent import AnomalyAgent, AnomalyResult


@pytest.fixture
def agent():
    return AnomalyAgent(groq_api_key="test-key")


@pytest.fixture
def safe_metrics():
    return {
        "protocol": "SafeProto",
        "tvl": 10_000_000.0,
        "volume_24h": 500_000.0,
        "price_change_1h": 0.5,
        "num_transactions": 200,
        "liquidity_ratio": 0.8,
    }


@pytest.fixture
def risky_metrics():
    return {
        "protocol": "RiskyProto",
        "tvl": 10_000_000.0,
        "volume_24h": 5_000_000.0,
        "price_change_1h": -35.0,
        "num_transactions": 5000,
        "liquidity_ratio": 0.03,
    }


@pytest.mark.asyncio
async def test_detect_returns_anomaly_result(agent, safe_metrics):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_score": 15,
            "anomalies": [],
            "recommendation": "Monitor",
        }
        result = await agent.detect(safe_metrics)
    assert isinstance(result, AnomalyResult)


@pytest.mark.asyncio
async def test_anomaly_result_fields(agent, safe_metrics):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_score": 20,
            "anomalies": [],
            "recommendation": "All clear",
        }
        result = await agent.detect(safe_metrics)
    assert result.protocol == "SafeProto"
    assert 0 <= result.risk_score <= 100
    assert isinstance(result.anomalies, list)
    assert isinstance(result.recommendation, str)
    assert isinstance(result.timestamp, float)


@pytest.mark.asyncio
async def test_high_risk_detection(agent, risky_metrics):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_score": 88,
            "anomalies": ["extreme_price_drop", "low_liquidity", "volume_spike"],
            "recommendation": "Immediate action required",
        }
        result = await agent.detect(risky_metrics)
    assert result.risk_score >= 70
    assert len(result.anomalies) > 0


@pytest.mark.asyncio
async def test_groq_error_fallback(agent, safe_metrics):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.side_effect = Exception("API down")
        result = await agent.detect(safe_metrics)
    assert isinstance(result, AnomalyResult)
    assert result.protocol == "SafeProto"


@pytest.mark.asyncio
async def test_timestamp_is_recent(agent, safe_metrics):
    now = time.time()
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_score": 10,
            "anomalies": [],
            "recommendation": "",
        }
        result = await agent.detect(safe_metrics)
    assert result.timestamp >= now - 5


@pytest.mark.asyncio
async def test_zero_tvl_metrics(agent):
    metrics = {
        "protocol": "EmptyProto",
        "tvl": 0.0,
        "volume_24h": 0.0,
        "price_change_1h": 0.0,
        "num_transactions": 0,
        "liquidity_ratio": 0.0,
    }
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_score": 50,
            "anomalies": ["zero_tvl"],
            "recommendation": "Investigate",
        }
        result = await agent.detect(metrics)
    assert isinstance(result, AnomalyResult)


@pytest.mark.asyncio
async def test_concurrent_detections(agent, safe_metrics, risky_metrics):
    import asyncio

    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_score": 30,
            "anomalies": [],
            "recommendation": "",
        }
        results = await asyncio.gather(
            agent.detect(safe_metrics),
            agent.detect(risky_metrics),
        )
    assert len(results) == 2
    assert all(isinstance(r, AnomalyResult) for r in results)


@pytest.mark.asyncio
async def test_risk_score_clamped_to_100(agent, safe_metrics):
    """Groq returning score > 100 must be clamped."""
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_score": 150,
            "anomalies": ["overflow"],
            "recommendation": "cap it",
        }
        result = await agent.detect(safe_metrics)
    assert result.risk_score <= 100


@pytest.mark.asyncio
async def test_risk_score_not_negative(agent, safe_metrics):
    """Groq returning negative score must be clamped to 0."""
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_score": -10,
            "anomalies": [],
            "recommendation": "none",
        }
        result = await agent.detect(safe_metrics)
    assert result.risk_score >= 0


@pytest.mark.asyncio
async def test_anomalies_is_list_even_on_empty(agent, safe_metrics):
    """anomalies field is always a list, never None."""
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_score": 5,
            "anomalies": None,
            "recommendation": "",
        }
        result = await agent.detect(safe_metrics)
    assert isinstance(result.anomalies, list)


@pytest.mark.asyncio
async def test_multiple_anomaly_types(agent, risky_metrics):
    """Multiple anomaly tags are preserved in result."""
    tags = ["whale_dump", "flash_loan", "oracle_drift", "depeg"]
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_score": 95,
            "anomalies": tags,
            "recommendation": "emergency",
        }
        result = await agent.detect(risky_metrics)
    assert len(result.anomalies) == 4


@pytest.mark.asyncio
async def test_recommendation_non_empty_on_high_risk(agent, risky_metrics):
    """High risk result should always carry a non-empty recommendation."""
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_score": 92,
            "anomalies": ["whale_dump"],
            "recommendation": "Halt withdrawals immediately",
        }
        result = await agent.detect(risky_metrics)
    assert len(result.recommendation) > 0


@pytest.mark.asyncio
async def test_protocol_name_preserved(agent):
    """Protocol name from metrics is stored unchanged in result."""
    metrics = {
        "protocol": "UniqueProtoXYZ",
        "tvl": 1_000_000.0,
        "volume_24h": 100_000.0,
        "price_change_1h": -2.0,
        "num_transactions": 300,
        "liquidity_ratio": 0.5,
    }
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_score": 20,
            "anomalies": [],
            "recommendation": "ok",
        }
        result = await agent.detect(metrics)
    assert result.protocol == "UniqueProtoXYZ"


@pytest.mark.asyncio
async def test_detect_called_with_metrics_context(agent, risky_metrics):
    """_call_groq is invoked exactly once per detect call."""
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_score": 55,
            "anomalies": ["volume_spike"],
            "recommendation": "Watch",
        }
        await agent.detect(risky_metrics)
    mock_groq.assert_called_once()


@pytest.mark.asyncio
async def test_liquidity_crisis_classification(agent):
    """Very low liquidity ratio should trigger liquidity-related anomaly."""
    metrics = {
        "protocol": "LiquidCrisis",
        "tvl": 50_000_000.0,
        "volume_24h": 45_000_000.0,
        "price_change_1h": -5.0,
        "num_transactions": 8000,
        "liquidity_ratio": 0.01,
    }
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_score": 89,
            "anomalies": ["liquidity_crisis"],
            "recommendation": "Suspend operations",
        }
        result = await agent.detect(metrics)
    assert result.risk_score >= 70
    assert any("liquidity" in a for a in result.anomalies)
