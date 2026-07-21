"""Unit tests — VaultWatch SDK audit_trail + risk_oracle namespaces.

Verifies the direct contract-query methods added to the SDK:
  • client.audit_trail.get_finding(id)
  • client.audit_trail.get_findings(limit)
  • client.audit_trail.get_count()
  • client.risk_oracle.get_score(address)

Uses a mocked httpx.AsyncClient so no real network calls are made — the tests
assert the SDK hits the correct /chain/* paths, parses the JSON response, and
propagates 404 errors.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "sdk"))

from vaultwatch import VaultWatchClient  # noqa: E402
from vaultwatch.client import AuditTrailNamespace, RiskOracleNamespace  # noqa: E402


def _mock_response(status: int, payload: dict) -> httpx.Response:
    request = httpx.Request("GET", "http://localhost:8000/")
    return httpx.Response(
        status_code=status,
        content=json.dumps(payload).encode(),
        request=request,
        headers={"content-type": "application/json"},
    )


@pytest.fixture()
def client():
    return VaultWatchClient(base_url="http://localhost:8000", api_key="test-key-123")


# ===========================================================================
# Namespace wiring
# ===========================================================================
def test_namespaces_attached_to_client(client):
    assert isinstance(client.audit_trail, AuditTrailNamespace)
    assert isinstance(client.risk_oracle, RiskOracleNamespace)
    assert client.audit_trail._client is client
    assert client.risk_oracle._client is client


def test_auth_headers_sent(client):
    headers = client._auth_headers()
    assert headers["X-API-Key"] == "test-key-123"
    assert headers["Authorization"] == "Bearer test-key-123"


def test_no_auth_headers_when_no_key():
    c = VaultWatchClient(api_key="")
    assert c._auth_headers() == {}


# ===========================================================================
# audit_trail.get_finding
# ===========================================================================
@pytest.mark.asyncio
async def test_audit_trail_get_finding_hits_correct_path(client):
    payload = {
        "id": "F-5",
        "numeric_id": 5,
        "protocol": "CasperSwap",
        "summary": "whale dump",
        "severity": "CRITICAL",
        "confidence": 0.91,
        "source": "on-chain",
    }
    mock_http = MagicMock()
    mock_http.get = AsyncMock(return_value=_mock_response(200, payload))
    with patch.object(client, "_http", return_value=mock_http):
        result = await client.audit_trail.get_finding(5)
    assert result["numeric_id"] == 5
    mock_http.get.assert_awaited_once()
    call_args = mock_http.get.await_args
    assert call_args.args[0] == "/chain/finding/5"


@pytest.mark.asyncio
async def test_audit_trail_get_finding_404_propagates(client):
    mock_http = MagicMock()
    mock_http.get = AsyncMock(
        return_value=_mock_response(404, {"detail": "finding 99 not found"})
    )
    with patch.object(client, "_http", return_value=mock_http):
        with pytest.raises(httpx.HTTPStatusError):
            await client.audit_trail.get_finding(99)


# ===========================================================================
# audit_trail.get_findings
# ===========================================================================
@pytest.mark.asyncio
async def test_audit_trail_get_findings_passes_limit(client):
    payload = {
        "count": 2,
        "findings": [{"id": "F-2"}, {"id": "F-1"}],
        "source": "on-chain",
    }
    mock_http = MagicMock()
    mock_http.get = AsyncMock(return_value=_mock_response(200, payload))
    with patch.object(client, "_http", return_value=mock_http):
        result = await client.audit_trail.get_findings(limit=15)
    assert result["count"] == 2
    assert result["source"] == "on-chain"
    call_args = mock_http.get.await_args
    assert call_args.args[0] == "/chain/findings"
    assert call_args.kwargs.get("params", {}).get("limit") == 15


# ===========================================================================
# audit_trail.get_count
# ===========================================================================
@pytest.mark.asyncio
async def test_audit_trail_get_count(client):
    mock_http = MagicMock()
    mock_http.get = AsyncMock(
        return_value=_mock_response(200, {"count": 7, "source": "on-chain", "network": "casper-test"})
    )
    with patch.object(client, "_http", return_value=mock_http):
        result = await client.audit_trail.get_count()
    assert result["count"] == 7
    assert result["source"] == "on-chain"


# ===========================================================================
# risk_oracle.get_score
# ===========================================================================
@pytest.mark.asyncio
async def test_risk_oracle_get_score_hits_correct_path(client):
    payload = {
        "address": "account-hash-abc",
        "score": 87,
        "risk_type": "whale_concentration",
        "confidence": 92,
        "last_updated": 1500000,
        "finding_id": 1,
        "source": "on-chain",
    }
    mock_http = MagicMock()
    mock_http.get = AsyncMock(return_value=_mock_response(200, payload))
    with patch.object(client, "_http", return_value=mock_http):
        result = await client.risk_oracle.get_score("account-hash-abc")
    assert result["score"] == 87
    call_args = mock_http.get.await_args
    assert call_args.args[0] == "/chain/risk-score/account-hash-abc"


@pytest.mark.asyncio
async def test_risk_oracle_get_score_url_encodes_address(client):
    payload = {"address": "a b", "score": 1, "risk_type": "x", "confidence": 1,
               "last_updated": 1, "finding_id": 1, "source": "on-chain"}
    mock_http = MagicMock()
    mock_http.get = AsyncMock(return_value=_mock_response(200, payload))
    with patch.object(client, "_http", return_value=mock_http):
        await client.risk_oracle.get_score("account-hash-abc def")
    call_args = mock_http.get.await_args
    # Space must be percent-encoded.
    assert "account-hash-abc%20def" in call_args.args[0]


@pytest.mark.asyncio
async def test_risk_oracle_get_score_404_propagates(client):
    mock_http = MagicMock()
    mock_http.get = AsyncMock(
        return_value=_mock_response(404, {"detail": "no risk score on chain"})
    )
    with patch.object(client, "_http", return_value=mock_http):
        with pytest.raises(httpx.HTTPStatusError):
            await client.risk_oracle.get_score("account-hash-unknown")


# ===========================================================================
# Sync wrappers (smoke — verify asyncio.run path works)
# ===========================================================================
def test_audit_trail_get_finding_sync(client):
    payload = {"id": "F-1", "numeric_id": 1, "source": "on-chain"}
    mock_http = MagicMock()
    mock_http.get = AsyncMock(return_value=_mock_response(200, payload))
    with patch.object(client, "_http", return_value=mock_http):
        result = client.audit_trail.get_finding_sync(1)
    assert result["numeric_id"] == 1


def test_risk_oracle_get_score_sync(client):
    payload = {"address": "a", "score": 50, "risk_type": "x", "confidence": 50,
               "last_updated": 1, "finding_id": 1, "source": "on-chain"}
    mock_http = MagicMock()
    mock_http.get = AsyncMock(return_value=_mock_response(200, payload))
    with patch.object(client, "_http", return_value=mock_http):
        result = client.risk_oracle.get_score_sync("account-hash-x")
    assert result["score"] == 50
