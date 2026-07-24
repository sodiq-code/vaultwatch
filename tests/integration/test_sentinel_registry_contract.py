"""Integration test — SentinelRegistry contract (mock Casper client)"""

import pytest
from unittest.mock import MagicMock

from casper_client import CasperContractClient


@pytest.fixture
def mock_client():
    client = MagicMock(spec=CasperContractClient)
    client.mock = True

    # Registry state mock
    _registry: dict = {}

    def mock_call_contract(contract_hash, entry_point, args, payment_amount=5_000_000_000):
        if entry_point == "register_sentinel":
            _registry[args["sentinel_id"]] = {
                "operator": args["operator"],
                "stake": args.get("stake", 0),
                "active": True,
            }
            return f"hash-register-{args['sentinel_id']}"
        elif entry_point == "deactivate_sentinel":
            if args["sentinel_id"] in _registry:
                _registry[args["sentinel_id"]]["active"] = False
            return f"hash-deactivate-{args['sentinel_id']}"
        return "hash-unknown"

    def mock_query_state(contract_hash, path):
        if path[0] == "sentinels":
            sentinel_id = path[1] if len(path) > 1 else None
            if sentinel_id:
                return _registry.get(sentinel_id)
            return _registry
        return None

    client.call_contract.side_effect = mock_call_contract
    client.query_contract_state.side_effect = mock_query_state
    return client


def test_register_sentinel(mock_client):
    deploy_hash = mock_client.call_contract(
        contract_hash="hash-registry",
        entry_point="register_sentinel",
        args={"sentinel_id": "sentinel-001", "operator": "account-abc", "stake": 1000},
    )
    assert "register-sentinel-001" in deploy_hash


def test_query_registered_sentinel(mock_client):
    mock_client.call_contract(
        contract_hash="hash-registry",
        entry_point="register_sentinel",
        args={"sentinel_id": "sentinel-002", "operator": "account-xyz", "stake": 2000},
    )
    state = mock_client.query_contract_state("hash-registry", ["sentinels", "sentinel-002"])
    assert state is not None
    assert state["operator"] == "account-xyz"
    assert state["active"] is True


def test_deactivate_sentinel(mock_client):
    mock_client.call_contract(
        contract_hash="hash-registry",
        entry_point="register_sentinel",
        args={"sentinel_id": "sentinel-003", "operator": "account-abc", "stake": 500},
    )
    mock_client.call_contract(
        contract_hash="hash-registry",
        entry_point="deactivate_sentinel",
        args={"sentinel_id": "sentinel-003"},
    )
    state = mock_client.query_contract_state("hash-registry", ["sentinels", "sentinel-003"])
    assert state["active"] is False


def test_register_multiple_sentinels(mock_client):
    for i in range(5):
        h = mock_client.call_contract(
            contract_hash="hash-registry",
            entry_point="register_sentinel",
            args={
                "sentinel_id": f"bulk-{i:03d}",
                "operator": "account-bulk",
                "stake": 100 * i,
            },
        )
        assert isinstance(h, str)
    assert mock_client.call_contract.call_count == 5


def test_unknown_entry_point(mock_client):
    result = mock_client.call_contract(
        contract_hash="hash-registry",
        entry_point="nonexistent_fn",
        args={},
    )
    assert result == "hash-unknown"


def test_query_nonexistent_sentinel(mock_client):
    state = mock_client.query_contract_state("hash-registry", ["sentinels", "no-such-sentinel"])
    assert state is None


def test_casper_client_mock_mode():
    client = CasperContractClient(mock=True)
    assert client.mock is True
    height = client.get_block_height()
    assert isinstance(height, int)
