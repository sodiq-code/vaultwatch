"""Unit tests — AuditAgent

FIX #6: Fixed method signatures:
  - get_log() takes no limit parameter (was get_log(limit=10))
  - record() is the correct method name (was record_action/record_finding)
"""

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
    # FIX: get_log() takes no limit parameter
    result = await agent.get_log()
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_get_log_no_casper(agent_no_casper):
    # FIX: get_log() takes no limit parameter
    result = await agent_no_casper.get_log()
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_record_stored_in_log(agent):
    deploy_hash = await agent.record(action="policy_update", actor="admin", details="threshold=5")
    assert isinstance(deploy_hash, str)
    # Verify the entry was stored in the internal log
    log = agent.get_log()
    assert len(log) >= 1
    last_entry = log[-1]
    assert last_entry["action"] == "policy_update"
    assert last_entry["actor"] == "admin"


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
async def test_get_log_returns_all_entries(agent):
    # Record several entries
    for i in range(5):
        await agent.record(action=f"action_{i}", actor="system", details=f"detail_{i}")
    # FIX: get_log() takes no limit parameter — returns all entries
    log = agent.get_log()
    assert isinstance(log, list)
    assert len(log) >= 5
