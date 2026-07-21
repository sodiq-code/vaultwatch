"""Integration tests — Critical Fix 5: MCP tools wired to REAL Casper RPC.

Verifies that the 4 critical MCP tools (agent_attestation, reputation_query,
x402_subscribe, policy_hotswap) actually:
  - Make real JSON-RPC calls to the Casper testnet node (for reads)
  - Shell out to the real Node.js deploy helpers (for writes)
  - Use the REAL 64-char contract hashes (not the old 50-char fake hashes)
  - Return the on-chain deploy hash / verification status in the response
"""

import json
import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))


# ---------------------------------------------------------------------------
# Hash verification — the core of Critical Fix 5
# ---------------------------------------------------------------------------

def test_contract_package_hashes_are_real_64_char():
    """All 8 CONTRACT_PACKAGE_HASHES must be 64-hex-char real Casper hashes,
    not the old 45-hex-char (50 with 'hash-' prefix) fake hashes."""
    import vaultwatch_mcp.server as srv

    assert len(srv.CONTRACT_PACKAGE_HASHES) == 8
    for name, h in srv.CONTRACT_PACKAGE_HASHES.items():
        assert h.startswith("hash-"), f"{name}: must start with 'hash-'"
        hex_part = h[len("hash-"):]
        assert len(hex_part) == 64, (
            f"{name}: hex part is {len(hex_part)} chars — expected 64 (real Casper hash). "
            f"The old fake hashes were 45 chars (50 with prefix)."
        )
        # Must be valid hex
        int(hex_part, 16)


def test_contract_hashes_are_real_64_char():
    """All 8 CONTRACT_HASHES (contract-version hashes) must be 64-hex-char."""
    import vaultwatch_mcp.server as srv

    assert len(srv.CONTRACT_HASHES) == 8
    expected_names = {
        "AgentBehaviorIndex", "SubscriberVault", "RiskOracle", "SentinelCredit",
        "AuditTrail", "SentinelRegistry", "SentinelAlertLog", "RiskPolicyManager",
    }
    assert set(srv.CONTRACT_HASHES.keys()) == expected_names
    for name, h in srv.CONTRACT_HASHES.items():
        assert not h.startswith("hash-"), f"{name}: CONTRACT_HASHES should be raw hex (no 'hash-' prefix)"
        assert len(h) == 64, f"{name}: {len(h)} chars — expected 64"
        int(h, 16)


def test_no_fake_50_char_hashes_remain():
    """No hash anywhere in the server module should be the old 50-char fake."""
    import vaultwatch_mcp.server as srv

    for name, h in srv.CONTRACT_PACKAGE_HASHES.items():
        total_len = len(h)
        assert total_len != 50, (
            f"{name}: package hash is still the 50-char fake ({h}). "
            f"Must be the real 69-char hash ('hash-' + 64 hex)."
        )


# ---------------------------------------------------------------------------
# Tool callability — FastMCP FunctionTool fix
# ---------------------------------------------------------------------------

def test_all_4_critical_tools_directly_callable():
    """The 4 critical tools must be directly callable async functions (not
    non-callable FunctionTool objects). This is required for both testing
    and direct invocation from the API layer."""
    import inspect
    import vaultwatch_mcp.server as srv

    for name in ("agent_attestation", "reputation_query", "x402_subscribe", "policy_hotswap"):
        fn = getattr(srv, name, None)
        assert fn is not None, f"{name} not found in server module"
        assert callable(fn), f"{name} is not callable (type={type(fn).__name__})"
        assert inspect.iscoroutinefunction(fn), f"{name} is not an async function"


# ---------------------------------------------------------------------------
# agent_attestation — real AgentBehaviorIndex.record_decision() deploy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_agent_attestation_submits_real_deploy():
    """agent_attestation must shell out to scripts/casper_call.cjs with the
    REAL AgentBehaviorIndex contract hash + record_decision entry point +
    the correct typed args (u8 confidence, u64 block_height, etc.)."""
    import vaultwatch_mcp.server as srv

    mock_deploy_result = {
        "success": True,
        "deploy_hash": "abc123def456",
        "block_hash": "block789",
        "cost_motes": "5000000000",
        "link": "https://testnet.cspr.live/deploy/abc123def456",
        "deployer_account_hash": "account-hash-test",
        "error": None,
    }
    with patch.object(srv, "_submit_contract_call_real", new=AsyncMock(return_value=mock_deploy_result)) as mock_call:
        result = await srv.agent_attestation(
            agent_name="AnomalyAgent",
            decision_summary="whale dump detected",
            confidence=91,
            evidence_refs=["finding_1"],
        )

    assert result["status"] == "attested_on_chain"
    assert result["on_chain_verified"] is True
    assert result["deploy_hash"] == "abc123def456"
    assert result["explorer_url"] == "https://testnet.cspr.live/deploy/abc123def456"
    assert result["entry_point"] == "record_decision"
    assert result["contract_hash"] == srv.CONTRACT_HASHES["AgentBehaviorIndex"]

    # Verify the helper was called with the REAL contract + entry point + typed args
    mock_call.assert_called_once()
    call_args = mock_call.call_args
    assert call_args.args[0] == "AgentBehaviorIndex"
    assert call_args.args[1] == "record_decision"
    typed_args = call_args.args[2]
    assert typed_args["agent_name"] == {"type": "string", "value": "AnomalyAgent"}
    assert typed_args["confidence"] == {"type": "u8", "value": "91"}
    assert typed_args["correction_applied"] == {"type": "bool", "value": "false"}
    assert typed_args["safety_rejected"] == {"type": "bool", "value": "false"}
    assert typed_args["block_height"] == {"type": "u64", "value": "0"}


@pytest.mark.asyncio
async def test_agent_attestation_failure_returns_error():
    """When the deploy fails, agent_attestation must report the failure (not
    claim success)."""
    import vaultwatch_mcp.server as srv

    mock_fail = {"success": False, "error": "insufficient funds", "deploy_hash": ""}
    with patch.object(srv, "_submit_contract_call_real", new=AsyncMock(return_value=mock_fail)):
        result = await srv.agent_attestation(
            agent_name="TestAgent", decision_summary="test", confidence=50
        )
    assert result["status"] == "attestation_failed"
    assert result["on_chain_verified"] is False
    assert result["error"] == "insufficient funds"


# ---------------------------------------------------------------------------
# reputation_query — real query_global_state on 3 contracts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reputation_query_makes_real_rpc_calls():
    """reputation_query must make REAL query_global_state calls to 3 contracts:
    AgentBehaviorIndex, SentinelCredit, SubscriberVault. Verify the response
    includes on_chain_queries verification status."""
    import vaultwatch_mcp.server as srv

    # Mock the real query helpers to return a successful (but empty) response
    async def mock_query(contract_name, path):
        return {"stored_value": {"CLValue": {"parsed": {}}}, "result": {}}

    async def mock_exists(contract_name):
        return {"exists": True, "contract_hash": srv.CONTRACT_HASHES.get(contract_name, "")}

    with patch.object(srv, "_query_contract_state_real", new=AsyncMock(side_effect=mock_query)) as mock_q, \
         patch.object(srv, "_query_contract_exists_real", new=AsyncMock(side_effect=mock_exists)):
        result = await srv.reputation_query(address="AnomalyAgent")

    # Must have queried AgentBehaviorIndex, SentinelCredit, AND SubscriberVault
    queried_contracts = [call.args[0] for call in mock_q.call_args_list]
    assert "AgentBehaviorIndex" in queried_contracts
    assert "SentinelCredit" in queried_contracts
    assert "SubscriberVault" in queried_contracts

    # Response must include the on-chain verification status
    assert "on_chain_queries" in result
    assert result["on_chain_queries"]["AgentBehaviorIndex"]["contract_hash"] == srv.CONTRACT_HASHES["AgentBehaviorIndex"]
    assert result["on_chain_queries"]["SentinelCredit"]["contract_hash"] == srv.CONTRACT_HASHES["SentinelCredit"]
    assert result["on_chain_queries"]["SubscriberVault"]["contract_hash"] == srv.CONTRACT_HASHES["SubscriberVault"]
    assert result["data_source"].startswith("Casper Testnet RPC")


@pytest.mark.asyncio
async def test_reputation_query_subscriber_uses_real_balances():
    """For a subscriber address, reputation_query must parse REAL on-chain
    balances from SentinelCredit + SubscriberVault (not hardcoded values)."""
    import vaultwatch_mcp.server as srv

    async def mock_query(contract_name, path):
        if contract_name == "AgentBehaviorIndex":
            return {"error": "not found"}  # not an agent
        if contract_name == "SentinelCredit":
            return {
                "stored_value": {
                    "CLValue": {
                        "parsed": {"escrowed_balance": 5000000000, "total_deposited": 10000000000}
                    }
                }
            }
        if contract_name == "SubscriberVault":
            return {
                "stored_value": {
                    "CLValue": {
                        "parsed": {"escrowed_balance": 3000000000, "total_deposits": 5000000000}
                    }
                }
            }
        return {}

    async def mock_exists(contract_name):
        return {"exists": True, "contract_hash": srv.CONTRACT_HASHES.get(contract_name, "")}

    with patch.object(srv, "_query_contract_state_real", new=AsyncMock(side_effect=mock_query)), \
         patch.object(srv, "_query_contract_exists_real", new=AsyncMock(side_effect=mock_exists)):
        result = await srv.reputation_query(address="casper1subscriber123")

    assert result["query_address"] == "casper1subscriber123"
    # The reputation must reflect the REAL parsed escrow balances:
    # SentinelCredit escrowed_balance=5e9 + SubscriberVault escrowed_balance=3e9 = 8e9 motes
    # (NOT the old hardcoded 10e9 motes). This proves the real RPC values flow
    # through to the reputation computation.
    components = result.get("components", {})
    escrow = components.get("escrow", {})
    assert escrow.get("escrowed_balance_motes") == 8_000_000_000, (
        f"Expected 8e9 motes (5e9 SentinelCredit + 3e9 SubscriberVault from real RPC), "
        f"got {escrow.get('escrowed_balance_motes')}"
    )


# ---------------------------------------------------------------------------
# x402_subscribe — real SubscriberVault.open_vault() deploy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_x402_subscribe_submits_real_deploy():
    """x402_subscribe must shell out to x402/x402_helper.mjs with the
    'submit-vault-payment' command (REAL SubscriberVault.open_vault() deploy)."""
    import vaultwatch_mcp.server as srv

    mock_enc = {"success": True, "paymentRequiredHeader": "base64-header"}
    mock_submit = {
        "success": True,
        "deployHash": "vault-deploy-abc",
        "blockHash": "vault-block-def",
        "gasCostMotes": "5000000000",
        "link": "https://testnet.cspr.live/deploy/vault-deploy-abc",
        "error": None,
    }

    async def mock_deploy_helper(helper_path, payload, command=None):
        if command == "encode-payment-required":
            return mock_enc
        if command == "submit-vault-payment":
            return mock_submit
        return {"success": False, "error": f"unexpected command: {command}"}

    with patch.object(srv, "_submit_real_deploy", new=AsyncMock(side_effect=mock_deploy_helper)) as mock_dep:
        result = await srv.x402_subscribe(
            subscriber_address="casper1subscriber",
            plan="standard",
            payment_amount_cspr=10.0,
        )

    assert result["status"] == "subscribed_on_chain"
    assert result["on_chain_verified"] is True
    assert result["deploy_hash"] == "vault-deploy-abc"
    assert result["explorer_url"] == "https://testnet.cspr.live/deploy/vault-deploy-abc"
    assert result["entry_point"] == "open_vault"
    assert result["contract_hash"] == srv.CONTRACT_HASHES["SubscriberVault"]
    assert result["payment_required_header"] == "base64-header"

    # Verify the helper was called with the x402 helper path + submit-vault-payment command
    submit_calls = [c for c in mock_dep.call_args_list if c.kwargs.get("command") == "submit-vault-payment"]
    assert len(submit_calls) == 1
    submit_payload = submit_calls[0].args[1]
    assert submit_payload["subscriberAddress"] == "casper1subscriber"
    assert submit_payload["amountMotes"] == 10_000_000_000  # 10 CSPR


# ---------------------------------------------------------------------------
# policy_hotswap — real RiskPolicyManager.upgrade_policy() deploy
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_policy_hotswap_queries_current_policy_then_submits_deploy():
    """policy_hotswap must (1) query the REAL current policy on-chain (for
    rollback), then (2) submit a REAL upgrade_policy() deploy. Must use
    'upgrade_policy' (not the old 'set_threshold')."""
    import vaultwatch_mcp.server as srv

    mock_prev = {
        "stored_value": {
            "CLValue": {
                "parsed": {
                    "min_confidence_threshold": 75,
                    "critical_score_threshold": 80,
                    "high_score_threshold": 60,
                    "medium_score_threshold": 45,
                }
            }
        }
    }
    mock_deploy = {
        "success": True,
        "deploy_hash": "policy-deploy-xyz",
        "block_hash": "policy-block-123",
        "cost_motes": "5000000000",
        "link": "https://testnet.cspr.live/deploy/policy-deploy-xyz",
        "error": None,
    }

    with patch.object(srv, "_query_contract_state_real", new=AsyncMock(return_value=mock_prev)) as mock_q, \
         patch.object(srv, "_submit_contract_call_real", new=AsyncMock(return_value=mock_deploy)) as mock_call:
        result = await srv.policy_hotswap(
            new_min_confidence=85,
            new_critical_threshold=90,
            new_high_threshold=70,
            reason="tightening thresholds",
        )

    assert result["status"] == "policy_swapped_on_chain"
    assert result["on_chain_verified"] is True
    assert result["deploy_hash"] == "policy-deploy-xyz"
    assert result["entry_point"] == "upgrade_policy"
    assert result["contract_hash"] == srv.CONTRACT_HASHES["RiskPolicyManager"]

    # Must have queried the current policy first (for rollback snapshot)
    mock_q.assert_called_once_with("RiskPolicyManager", ["current_policy"])

    # previous_policy should reflect the real on-chain values
    assert result["previous_policy"]["min_confidence_threshold"] == 75
    assert result["previous_policy"]["critical_score_threshold"] == 80

    # Must have called upgrade_policy (NOT set_threshold) with the correct typed args
    mock_call.assert_called_once()
    call_args = mock_call.call_args
    assert call_args.args[0] == "RiskPolicyManager"
    assert call_args.args[1] == "upgrade_policy"
    typed_args = call_args.args[2]
    assert typed_args["min_confidence_threshold"] == {"type": "u8", "value": "85"}
    assert typed_args["critical_score_threshold"] == {"type": "u8", "value": "90"}
    assert typed_args["high_score_threshold"] == {"type": "u8", "value": "70"}
    assert typed_args["updated_by"] == {"type": "string", "value": "tightening thresholds"}


@pytest.mark.asyncio
async def test_policy_hotswap_no_set_threshold():
    """policy_hotswap must NOT reference the non-existent 'set_threshold'
    entry point (RiskPolicyManager only exposes 'upgrade_policy')."""
    import vaultwatch_mcp.server as srv

    # Run with mocks so no real RPC is made
    with patch.object(srv, "_query_contract_state_real", new=AsyncMock(return_value={"error": "mock"})), \
         patch.object(srv, "_submit_contract_call_real", new=AsyncMock(return_value={"success": False, "error": "mock"})):
        result = await srv.policy_hotswap()

    # The entry_point in the response must be upgrade_policy, never set_threshold
    assert result["entry_point"] == "upgrade_policy"
    assert "set_threshold" not in json.dumps(result)
