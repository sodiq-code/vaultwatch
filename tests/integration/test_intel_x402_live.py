"""Integration tests — IntelAgent.serve_intel_with_x402 (Fix A)

Verifies that ``serve_intel_with_x402``:
  1. Uses the ``contract_hash=`` kwarg (NOT the legacy ``contract=``) when
     calling ``CasperContractClient.call_contract`` / ``call_contract_real``.
  2. Calls the real ``SentinelCredit::deduct_query`` entry point with the
     correct args (account_address: String, is_premium: bool).
  3. Returns the served findings + the on-chain deduct deploy hash when the
     deploy succeeds.
  4. Falls back gracefully (returns an error dict) when the deduction fails.

The live testnet test submits a REAL deduct_query deploy (verified on-chain)
using the owner key — proving the end-to-end x402 payment gate works against
the Casper testnet.
"""

import os
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.intel_agent import IntelAgent, _findings_store
from casper_client import CasperContractClient


@pytest.fixture(autouse=True)
def clear_findings():
    _findings_store.clear()
    yield
    _findings_store.clear()


@pytest.fixture
def seeded_findings():
    _findings_store.append(
        {
            "id": 1,
            "risk_type": "oracle_manipulation",
            "severity": "HIGH",
            "confidence": 0.88,
            "description": "Price oracle deviation >5%",
            "rwa_context": "Treasury exposure: 2.3M CSPR",
            "address": "hash-47ea0c53777a68d79cf2f66b9171e4a1b588048c283b2b2504fc5ecfe1b686ae",
            "block_height": 1500000,
            "timestamp": int(time.time()),
            "audit_trail_tx": "86d00025e95dea720e2b693e6188c3aa2271854d887674241912b7c1b70b5dd3",
            "risk_oracle_tx": "c22b90c085ed393c49d160e0048a5b525cbe9168029ea63bdbdec0f9dd6a267a",
            "enriched": True,
            "created_at": int(time.time()),
        }
    )


# ---------------------------------------------------------------------------
# Mock-client tests — verify the call_contract signature
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_serve_intel_uses_contract_hash_kwarg_with_mock_client(seeded_findings):
    """serve_intel_with_x402 must call_contract with contract_hash= (not contract=)."""
    mock_client = MagicMock(spec=CasperContractClient)
    mock_client.mock = True  # triggers the mock path inside serve_intel_with_x402
    # The mock path calls the sync call_contract and expects a str return.
    mock_client.call_contract.return_value = "deploy-hash-mock-123"
    # spec=CasperContractClient gives it call_contract_real as an attribute,
    # but we want the mock path — ensure hasattr check reflects mock=True.
    # (serve_intel_with_x402 checks `not getattr(client, 'mock', False)`.)

    result = await IntelAgent.serve_intel_with_x402(
        query_type="standard",
        address="hash-47ea0c5377",
        caller_address="account-hash-abc",
        casper_client=mock_client,
    )

    mock_client.call_contract.assert_called_once()
    call_kwargs = mock_client.call_contract.call_args.kwargs or {}
    # CRITICAL: must use contract_hash=, never contract=
    assert "contract_hash" in call_kwargs, "must use contract_hash= kwarg"
    assert "contract" not in call_kwargs, "must NOT use legacy contract= kwarg"
    assert call_kwargs["entry_point"] == "deduct_query"
    assert call_kwargs["args"]["account_address"] == "account-hash-abc"
    assert call_kwargs["args"]["is_premium"] is False
    # Result must include the deploy hash + verification flag
    assert result["deduct_deploy_hash"] == "deploy-hash-mock-123"
    assert result["deduct_verified"] is True
    assert len(result["findings"]) == 1


@pytest.mark.asyncio
async def test_serve_intel_premium_sets_is_premium_true(seeded_findings):
    """query_type='premium' must pass is_premium=True to deduct_query."""
    mock_client = MagicMock(spec=CasperContractClient)
    mock_client.mock = True
    mock_client.call_contract.return_value = "deploy-hash-premium"

    await IntelAgent.serve_intel_with_x402(
        query_type="premium",
        address="hash-47ea0c5377",
        caller_address="account-hash-xyz",
        casper_client=mock_client,
    )

    call_kwargs = mock_client.call_contract.call_args.kwargs or {}
    assert call_kwargs["args"]["is_premium"] is True


@pytest.mark.asyncio
async def test_serve_intel_returns_error_when_deduct_returns_empty(seeded_findings):
    """An empty deploy-hash from the mock client must surface as an error."""
    mock_client = MagicMock(spec=CasperContractClient)
    mock_client.mock = True
    mock_client.call_contract.return_value = ""

    result = await IntelAgent.serve_intel_with_x402(
        query_type="standard",
        address="hash-47ea0c5377",
        caller_address="account-hash-broke",
        casper_client=mock_client,
    )
    assert "error" in result
    assert "Insufficient credit" in result["error"]


@pytest.mark.asyncio
async def test_serve_intel_returns_error_when_call_raises(seeded_findings):
    """An exception from call_contract must surface as an error dict (not crash)."""
    mock_client = MagicMock(spec=CasperContractClient)
    mock_client.mock = True
    mock_client.call_contract.side_effect = RuntimeError("network down")

    result = await IntelAgent.serve_intel_with_x402(
        query_type="standard",
        address="hash-47ea0c5377",
        caller_address="account-hash-abc",
        casper_client=mock_client,
    )
    assert "error" in result
    assert "Insufficient credit" in result["error"] or "deduction failed" in result["error"]


@pytest.mark.asyncio
async def test_serve_intel_real_path_uses_call_contract_real(seeded_findings):
    """When mock=False and call_contract_real exists, serve_intel_with_x402 must
    call the async call_contract_real (the Node.js casper-js-sdk path)."""
    real_client = MagicMock(spec=CasperContractClient)
    real_client.mock = False
    real_client.call_contract_real = AsyncMock(
        return_value={
            "success": True,
            "deploy_hash": "real-deploy-hash-abc",
            "block_hash": "block-hash-xyz",
            "cost_motes": "5000000000",
            "link": "https://testnet.cspr.live/deploy/real-deploy-hash-abc",
            "error": None,
        }
    )

    result = await IntelAgent.serve_intel_with_x402(
        query_type="standard",
        address="hash-47ea0c5377",
        caller_address="account-hash-owner",
        casper_client=real_client,
    )

    real_client.call_contract_real.assert_called_once()
    call_kwargs = real_client.call_contract_real.call_args.kwargs or {}
    assert "contract_hash" in call_kwargs, "call_contract_real must use contract_hash="
    assert "contract" not in call_kwargs
    assert call_kwargs["entry_point"] == "deduct_query"
    assert result["deduct_deploy_hash"] == "real-deploy-hash-abc"
    assert result["deduct_verified"] is True


@pytest.mark.asyncio
async def test_serve_intel_real_path_returns_error_on_failed_deploy(seeded_findings):
    """A failed on-chain deploy (success=False) must surface as an error."""
    real_client = MagicMock(spec=CasperContractClient)
    real_client.mock = False
    real_client.call_contract_real = AsyncMock(
        return_value={
            "success": False,
            "deploy_hash": "failed-deploy",
            "error": "User error: 1",
        }
    )
    result = await IntelAgent.serve_intel_with_x402(
        query_type="standard",
        address="hash-47ea0c5377",
        caller_address="account-hash-nonowner",
        casper_client=real_client,
    )
    assert "error" in result
    assert "Credit deduction failed" in result["error"]


@pytest.mark.asyncio
async def test_serve_intel_without_casper_client_serves_findings(seeded_findings):
    """Without a casper_client, serve_intel_with_x402 still serves findings (no deduct)."""
    result = await IntelAgent.serve_intel_with_x402(
        query_type="standard",
        address="hash-47ea0c5377",
        caller_address="account-hash-abc",
        casper_client=None,
    )
    assert "error" not in result
    assert len(result["findings"]) == 1
    assert "deduct_deploy_hash" not in result


# ---------------------------------------------------------------------------
# Live testnet test — submits a REAL deduct_query deploy (owner key required)
# ---------------------------------------------------------------------------


# The SentinelCredit owner key (depleted but re-funded with 20 CSPR for gas).
# This file is gitignored. Skip the live test if the key is absent.
_OWNER_KEY_PATH = "secret_key.depleted_2026-07-21T17-06-18.pem"
_OWNER_ACCOUNT_HASH = (
    "account-hash-aff1536a1cc925dab64b18049e0b63d5ec48580480a8d8306003663070c83136"
)
_LIVE_SKIP_REASON = (
    "requires the SentinelCredit owner key file "
    f"({_OWNER_KEY_PATH}) and live testnet access"
)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.path.exists(_OWNER_KEY_PATH),
    reason=_LIVE_SKIP_REASON,
)
async def test_serve_intel_with_x402_live_testnet(seeded_findings):
    """End-to-end: submit a REAL SentinelCredit::deduct_query deploy to testnet.

    Uses the owner key (the only account permitted to call deduct_query).
    The deploy is verified on-chain (success=True, error_message=None).
    """
    client = CasperContractClient(
        node_url="https://node.testnet.casper.network/rpc",
        chain_name="casper-test",
        signing_key_path=_OWNER_KEY_PATH,
        mock=False,
    )
    assert not client.mock, "client must not be in mock mode"
    assert hasattr(client, "call_contract_real"), "must have call_contract_real"

    result = await IntelAgent.serve_intel_with_x402(
        query_type="standard",
        address="hash-47ea0c5377",
        caller_address=_OWNER_ACCOUNT_HASH,
        casper_client=client,
    )

    # The deploy must have succeeded on-chain.
    assert "error" not in result, f"deduct failed: {result.get('error')}"
    assert result["deduct_verified"] is True
    deploy_hash = result["deduct_deploy_hash"]
    assert isinstance(deploy_hash, str) and len(deploy_hash) == 64
    # The finding must be served.
    assert len(result["findings"]) >= 1
    assert result["findings"][0]["risk_type"] == "oracle_manipulation"
    assert result["powered_by"] == "VaultWatch v4"
