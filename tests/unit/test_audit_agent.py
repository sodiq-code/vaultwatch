"""Unit tests — AuditAgent"""

import pytest
from unittest.mock import MagicMock

from agents.audit_agent import AuditAgent
from casper_client import CasperContractClient


@pytest.fixture
def mock_casper():
    client = MagicMock(spec=CasperContractClient)
    client.mock = True
    client.call_contract.return_value = "deploy-hash-abc123"
    client.query_contract_state.return_value = [
        {"id": 1, "action": "test", "actor": "tester", "details": "unit test"},
    ]
    return client


@pytest.fixture
def agent(mock_casper):
    return AuditAgent(casper_client=mock_casper)


@pytest.fixture
def agent_no_casper():
    return AuditAgent(casper_client=None)


@pytest.mark.asyncio
async def test_record_returns_deploy_hash(agent):
    result = await agent.record(action="test_action", actor="tester", details="unit test")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_record_no_casper_mock_mode(agent_no_casper):
    result = await agent_no_casper.record(action="test", actor="system", details="mock")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_get_log_returns_list(agent):
    result = await agent.get_log(limit=10)
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_log_no_casper(agent_no_casper):
    result = await agent_no_casper.get_log(limit=5)
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_record_finding_stored(agent):
    """record() must standardize on the record_finding entry point (the only
    write entry point on the AuditTrail contract) and use the contract_hash=
    kwarg (not the legacy contract= path)."""
    deploy_hash = await agent.record(action="policy_update", actor="admin", details="threshold=5")
    assert isinstance(deploy_hash, str)
    # Verify casper call was made with the standardized entry point + kwarg
    if hasattr(agent, "_casper") and agent._casper:
        agent._casper.call_contract.assert_called()
        call_kwargs = agent._casper.call_contract.call_args.kwargs or {}
        assert call_kwargs.get("entry_point") == "record_finding"
        assert "contract_hash" in call_kwargs
        assert "contract" not in call_kwargs
        args = call_kwargs.get("args", {})
        # record_finding requires these 9 runtime args
        for required in (
            "address",
            "risk_type",
            "severity",
            "confidence",
            "description",
            "rwa_enriched",
            "agent_model",
            "block_height",
            "timestamp",
        ):
            assert required in args, f"missing record_finding arg: {required}"
        assert args["risk_type"] == "policy_update"
        assert args["address"] == "admin"


@pytest.mark.asyncio
async def test_audit_multiple_records(agent):
    hashes = []
    for i in range(5):
        h = await agent.record(action=f"action_{i}", actor="system", details=f"detail_{i}")
        hashes.append(h)
    assert len(hashes) == 5
    assert all(isinstance(h, str) for h in hashes)


@pytest.mark.asyncio
async def test_record_empty_details(agent):
    result = await agent.record(action="empty_details", actor="pipeline", details="")
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_get_log_limit_respected(agent):
    result = await agent.get_log(limit=5)
    assert isinstance(result, list)
    assert len(result) <= 5
