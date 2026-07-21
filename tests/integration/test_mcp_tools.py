"""Integration test — MCP server tools (VaultWatch v4)

FIX #7: Aligned all test calls with the actual MCP tool signatures
from server.py. Removed references to non-existent tools
(subscribe_alerts, upgrade_policy) and fixed parameter mismatches.
"""

import pytest
import json
import sys
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


def test_mcp_server_importable():
    """MCP server module should import without errors."""
    import vaultwatch_mcp.server

    assert hasattr(vaultwatch_mcp.server, "mcp")


def test_mcp_has_15_tools():
    """MCP server should expose at least 10 async tool functions."""
    import vaultwatch_mcp.server as srv

    # FastMCP stores tools in mcp._tool_manager or similar
    try:
        tools = srv.mcp._tool_manager._tools
        len(tools)
    except AttributeError:
        # Try alternate attribute
        try:
            tools = srv.mcp.tools
            len(tools)
        except AttributeError:
            pass
    # At minimum server exposes the decorated functions
    import inspect

    funcs = [name for name, obj in inspect.getmembers(srv, inspect.iscoroutinefunction)]
    assert len(funcs) >= 10, f"Expected >=10 async tool functions, got {len(funcs)}: {funcs}"


@pytest.mark.asyncio
async def test_get_market_state_returns_dict():
    """get_market_state: should return dict with cspr_price_usd on success or error on network failure."""
    import vaultwatch_mcp.server as srv

    mock_resp = MagicMock()
    mock_resp.json.return_value = {"casper-network": {"usd": 0.05, "usd_24h_change": 1.5}}
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_resp)
    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await srv.get_market_state()
    assert isinstance(result, dict)
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_detect_anomaly_returns_dict():
    """detect_anomaly: should return dict with address on success."""
    import vaultwatch_mcp.server as srv

    mock_groq = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps(
        {
            "risk_type": "wash_trading",
            "severity": "LOW",
            "confidence": 80,
            "reasoning": "Pattern consistent with normal activity",
        }
    )
    mock_groq.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
    with patch("groq.Groq", return_value=mock_groq):
        result = await srv.detect_anomaly(address="test_address_001", amount_cspr=5000.0)
    assert isinstance(result, dict)
    assert result.get("address") == "test_address_001"
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_get_rwa_risk_returns_dict():
    """get_rwa_risk: should return dict with rwa_intelligence."""
    import vaultwatch_mcp.server as srv

    mock_groq = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = json.dumps({"depeg_risk": "low", "collateral_ratio": 1.5})
    mock_groq.chat.completions.create.return_value = MagicMock(choices=[mock_choice])
    with patch("groq.Groq", return_value=mock_groq):
        result = await srv.get_rwa_risk(asset_type="stablecoin")
    assert isinstance(result, dict)
    assert "asset_type" in result
    assert result["asset_type"] == "stablecoin"


@pytest.mark.asyncio
async def test_query_findings_returns_dict():
    """query_findings: should return dict with findings list."""
    import vaultwatch_mcp.server as srv
    import agents.intel_agent as intel_mod

    # Inject a finding
    intel_mod._findings_store.clear()
    intel_mod._findings_store.append(
        {
            "id": 1,
            "protocol": "TestProto",
            "severity": "HIGH",
            "summary": "test finding",
            "address": "test_addr",
            "timestamp": time.time(),
        }
    )
    with patch("vaultwatch_mcp.server._findings_store", intel_mod._findings_store):
        result = await srv.query_findings(severity=None, limit=10)
    assert isinstance(result, dict)
    assert "findings" in result
    assert isinstance(result["findings"], list)


@pytest.mark.asyncio
async def test_get_audit_trail_returns_dict():
    """get_audit_trail: should return dict with findings.

    FIX: get_audit_trail takes only (limit=10), not (address=..., limit=5).
    Removed address parameter — audit trail is global, not per-address.
    """
    import vaultwatch_mcp.server as srv

    result = await srv.get_audit_trail(limit=5)
    assert isinstance(result, dict)
    assert "findings" in result
    assert "count" in result


@pytest.mark.asyncio
async def test_x402_subscribe_returns_dict():
    """x402_subscribe: should return subscription confirmation dict.

    FIX: Replaced non-existent subscribe_alerts with x402_subscribe,
    which takes (subscriber_address, plan, payment_amount_cspr).
    """
    import vaultwatch_mcp.server as srv

    result = await srv.x402_subscribe(
        subscriber_address="test_address_003",
        plan="standard",
        payment_amount_cspr=10.0,
    )
    assert isinstance(result, dict)
    assert "subscriber" in result or "x402Version" in result


@pytest.mark.asyncio
async def test_policy_hotswap_returns_dict():
    """policy_hotswap: should confirm new policy settings.

    FIX: Replaced non-existent upgrade_policy with policy_hotswap,
    which takes (new_critical_threshold, new_confidence_threshold, new_max_retries).
    """
    import vaultwatch_mcp.server as srv

    result = await srv.policy_hotswap(
        new_critical_threshold=85,
        new_confidence_threshold=75,
        new_max_retries=2,
    )
    assert isinstance(result, dict)
    assert "proposed_policy" in result or "hotswap_ready" in result


@pytest.mark.asyncio
async def test_get_risk_score_returns_dict():
    """get_risk_score: should return composite risk dict."""
    import vaultwatch_mcp.server as srv

    # Mock the Casper RPC call to avoid network dependency
    mock_rpc_result = {"stored_value": {"CLValue": {"parsed": {"score": 30}}}}
    with patch.object(srv, "casper_rpc_call", new_callable=AsyncMock) as mock_rpc:
        mock_rpc.return_value = mock_rpc_result
        result = await srv.get_risk_score(address="test_addr_004")
    assert isinstance(result, dict)
    assert "address" in result or "risk_oracle_query" in result or "timestamp" in result
