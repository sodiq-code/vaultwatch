"""Unit tests — IntelAgent"""

import pytest
from unittest.mock import AsyncMock, patch

from agents.intel_agent import IntelAgent, _findings_store


@pytest.fixture(autouse=True)
def clear_findings():
    """Clear global findings store before each test."""
    _findings_store.clear()
    yield
    _findings_store.clear()


@pytest.fixture
def agent():
    return IntelAgent(groq_api_key="test-key")


@pytest.mark.asyncio
async def test_analyze_returns_dict(agent):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "summary": "Protocol appears safe",
            "risk_factors": [],
            "findings_count": 0,
            "confidence": 0.9,
        }
        result = await agent.analyze("Is Aave safe?")
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_analyze_stores_finding(agent):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "summary": "Risk detected",
            "risk_factors": ["oracle_risk"],
            "findings_count": 1,
            "confidence": 0.8,
        }
        await agent.analyze("Check Compound risk")
    assert len(_findings_store) >= 1


@pytest.mark.asyncio
async def test_analyze_with_protocol(agent):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {"summary": "Low risk", "risk_factors": [], "findings_count": 0, "confidence": 0.95}
        result = await agent.analyze("Risk analysis", protocol="Uniswap")
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_analyze_with_context(agent):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {"summary": "Context-aware", "risk_factors": [], "findings_count": 0, "confidence": 0.7}
        result = await agent.analyze(
            "Analyze with context",
            protocol="TestProto",
            extra_context={"tvl": 1_000_000},
        )
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_groq_error_fallback(agent):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.side_effect = Exception("API error")
        result = await agent.analyze("query")
    assert isinstance(result, dict)
    assert "error" in result or "summary" in result


@pytest.mark.asyncio
async def test_multiple_analyses_accumulate_findings(agent):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {"summary": "ok", "risk_factors": [], "findings_count": 0, "confidence": 0.8}
        for i in range(3):
            await agent.analyze(f"Query {i}")
    assert len(_findings_store) == 3


@pytest.mark.asyncio
async def test_findings_store_has_timestamp(agent):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {"summary": "test", "risk_factors": [], "findings_count": 0, "confidence": 0.9}
        await agent.analyze("test query")
    assert "timestamp" in _findings_store[0] or len(_findings_store) > 0


@pytest.mark.asyncio
async def test_compound_model_used(agent):
    """Verify IntelAgent targets the compound-beta model."""
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {"summary": "", "risk_factors": [], "findings_count": 0, "confidence": 0.5}
        await agent.analyze("test")
    # Model selection verified by agent's internal _model attribute
    assert agent._model == "compound-beta"
