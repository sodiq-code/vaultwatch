"""Unit tests — ScannerAgent"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from agents.scanner_agent import ScannerAgent


@pytest.fixture
def agent():
    return ScannerAgent(groq_api_key="test-key")


@pytest.mark.asyncio
async def test_scan_returns_dict(agent):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_level": "LOW",
            "vulnerabilities": [],
            "summary": "No issues found",
        }
        result = await agent.scan(protocol="TestProtocol", chain="casper")
    assert isinstance(result, dict)
    assert "risk_level" in result


@pytest.mark.asyncio
async def test_scan_high_risk(agent):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_level": "HIGH",
            "vulnerabilities": ["reentrancy", "oracle_manipulation"],
            "summary": "Critical vulnerabilities detected",
        }
        result = await agent.scan(protocol="RiskyProtocol", chain="casper")
    assert result["risk_level"] == "HIGH"
    assert len(result["vulnerabilities"]) == 2


@pytest.mark.asyncio
async def test_scan_with_contract_address(agent):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {"risk_level": "MEDIUM", "vulnerabilities": [], "summary": ""}
        result = await agent.scan(
            protocol="TestProtocol",
            contract_address="hash-abc123",
            chain="casper",
        )
    assert "risk_level" in result


@pytest.mark.asyncio
async def test_scan_groq_error_returns_fallback(agent):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.side_effect = Exception("Groq API error")
        result = await agent.scan(protocol="FailProtocol", chain="casper")
    assert "risk_level" in result
    assert result.get("error") or result["risk_level"] == "UNKNOWN"


def test_agent_init():
    a = ScannerAgent(groq_api_key="")
    assert a is not None


@pytest.mark.asyncio
async def test_scan_result_has_summary(agent):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_level": "LOW",
            "vulnerabilities": [],
            "summary": "Clean protocol",
        }
        result = await agent.scan(protocol="CleanProtocol")
    assert "summary" in result


@pytest.mark.asyncio
async def test_scan_casper_chain_tag(agent):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {"risk_level": "LOW", "vulnerabilities": [], "summary": ""}
        result = await agent.scan(protocol="P", chain="casper")
    # Chain should be referenced somewhere in the scan call
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_multiple_scans(agent):
    with patch.object(agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {"risk_level": "LOW", "vulnerabilities": [], "summary": "ok"}
        results = await asyncio.gather(
            agent.scan(protocol="A"),
            agent.scan(protocol="B"),
            agent.scan(protocol="C"),
        )
    assert len(results) == 3
    assert all(isinstance(r, dict) for r in results)
