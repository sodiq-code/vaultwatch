"""Unit tests — RWAAgent"""

import pytest
from unittest.mock import AsyncMock, patch

from agents.rwa_agent import RWAAgent


@pytest.fixture
def agent():
    return RWAAgent(groq_api_key="test-key")


@pytest.fixture
def treasury_asset():
    return {
        "asset_id": "us-treasury-10y-001",
        "asset_type": "treasury_bond",
        "issuer": "US Government",
        "collateral_ratio": 1.05,
        "maturity_days": 3650,
        "credit_rating": "AAA",
    }


@pytest.fixture
def junk_asset():
    return {
        "asset_id": "junk-bond-001",
        "asset_type": "corporate_bond",
        "issuer": "Risky Corp",
        "collateral_ratio": 0.8,
        "maturity_days": 180,
        "credit_rating": "CCC",
    }


@pytest.mark.asyncio
async def test_assess_returns_dict(agent, treasury_asset):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "verdict": "APPROVED",
            "risk_score": 12.0,
            "notes": "High-grade sovereign debt",
        }
        result = await agent.assess(treasury_asset)
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_treasury_approved(agent, treasury_asset):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "verdict": "APPROVED",
            "risk_score": 10.0,
            "notes": "",
        }
        result = await agent.assess(treasury_asset)
    assert result.get("verdict") == "APPROVED"


@pytest.mark.asyncio
async def test_junk_bond_rejected(agent, junk_asset):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "verdict": "REJECTED",
            "risk_score": 91.0,
            "notes": "Sub-investment grade",
        }
        result = await agent.assess(junk_asset)
    assert result.get("verdict") == "REJECTED"


@pytest.mark.asyncio
async def test_list_assets_returns_list(agent):
    result = await agent.list_assets()
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_assess_groq_error_fallback(agent, treasury_asset):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.side_effect = Exception("Groq error")
        result = await agent.assess(treasury_asset)
    assert isinstance(result, dict)
    assert "error" in result or "verdict" in result


@pytest.mark.asyncio
async def test_real_estate_asset(agent):
    asset = {
        "asset_id": "re-nyc-001",
        "asset_type": "real_estate",
        "issuer": "Manhattan REIT",
        "collateral_ratio": 1.4,
        "maturity_days": 1825,
        "credit_rating": "BBB",
    }
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "verdict": "APPROVED",
            "risk_score": 35.0,
            "notes": "Moderate RE exposure",
        }
        result = await agent.assess(asset)
    assert "verdict" in result


@pytest.mark.asyncio
async def test_undercollateralised_rejected(agent):
    asset = {
        "asset_id": "undercoll-001",
        "asset_type": "loan",
        "issuer": "MicroFin",
        "collateral_ratio": 0.5,  # undercollateralised
        "maturity_days": 90,
        "credit_rating": "B",
    }
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "verdict": "REJECTED",
            "risk_score": 85.0,
            "notes": "Undercollateralised",
        }
        result = await agent.assess(asset)
    assert result.get("verdict") == "REJECTED"


@pytest.mark.asyncio
async def test_concurrent_assessments(agent, treasury_asset, junk_asset):
    import asyncio

    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "verdict": "APPROVED",
            "risk_score": 20.0,
            "notes": "",
        }
        results = await asyncio.gather(
            agent.assess(treasury_asset),
            agent.assess(junk_asset),
        )
    assert len(results) == 2
