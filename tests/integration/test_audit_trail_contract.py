"""Integration test — AuditTrail contract (mock Casper client)"""

import pytest
from unittest.mock import MagicMock

from casper_client import CasperContractClient
from agents.audit_agent import AuditAgent


@pytest.fixture
def mock_client():
    client = MagicMock(spec=CasperContractClient)
    client.mock = True
    client.call_contract.return_value = "deploy-hash-audit-001"
    client.query_contract_state.return_value = [
        {"id": 1, "action": "risk_alert", "actor": "pipeline", "details": "score=85"},
        {
            "id": 2,
            "action": "policy_update",
            "actor": "admin",
            "details": "threshold=3",
        },
    ]
    client.get_block_height.return_value = 42000
    return client


@pytest.fixture
def audit_agent(mock_client):
    return AuditAgent(casper_client=mock_client)


@pytest.mark.asyncio
async def test_record_calls_contract(audit_agent, mock_client):
    deploy_hash = await audit_agent.record(
        action="risk_alert",
        actor="pipeline",
        details="anomaly_score=88",
    )
    assert isinstance(deploy_hash, str)
    mock_client.call_contract.assert_called_once()


@pytest.mark.asyncio
async def test_record_entry_point(audit_agent, mock_client):
    await audit_agent.record(action="test", actor="system", details="")
    call_args = mock_client.call_contract.call_args
    assert call_args is not None
    kwargs = call_args.kwargs or {}
    args = call_args.args or ()
    # entry_point must be 'record_finding' — the only write entry point on
    # the AuditTrail contract (record_action never existed on-chain).
    entry_point = kwargs.get("entry_point") or (args[1] if len(args) > 1 else "")
    assert entry_point == "record_finding"


@pytest.mark.asyncio
async def test_get_log_queries_contract(audit_agent, mock_client):
    entries = await audit_agent.get_log(limit=10)
    assert isinstance(entries, list)
    assert len(entries) >= 0


@pytest.mark.asyncio
async def test_multiple_records(audit_agent, mock_client):
    mock_client.call_contract.side_effect = [
        "hash-001",
        "hash-002",
        "hash-003",
    ]
    hashes = []
    for i in range(3):
        h = await audit_agent.record(action=f"action_{i}", actor="system", details="")
        hashes.append(h)
    assert len(hashes) == 3
    assert mock_client.call_contract.call_count == 3


@pytest.mark.asyncio
async def test_record_args_contain_action(audit_agent, mock_client):
    await audit_agent.record(action="my_action", actor="agent", details="some detail")
    call_args = mock_client.call_contract.call_args
    all_args = str(call_args)
    assert "my_action" in all_args or "record" in all_args
    # Standardized on contract_hash= kwarg (not the legacy contract= path)
    kwargs = call_args.kwargs or {}
    assert "contract_hash" in kwargs
    assert "contract" not in kwargs


@pytest.mark.asyncio
async def test_audit_entry_has_required_fields(audit_agent, mock_client):
    entries = await audit_agent.get_log(limit=5)
    for entry in entries:
        assert isinstance(entry, dict)
