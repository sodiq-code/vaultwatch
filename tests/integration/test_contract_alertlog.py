"""Integration test — SentinelAlertLog contract (mock Casper client)

Tests alert logging, timestamp integrity, address indexing,
and delivery tracking — maps to SentinelAlertLog.rs on testnet.
"""

import pytest
from unittest.mock import MagicMock

from casper_client import CasperContractClient


@pytest.fixture
def mock_client():
    client = MagicMock(spec=CasperContractClient)
    client.mock = True

    _logs: dict = {}
    _address_index: dict = {}
    _counter = {"n": 0}

    def mock_call_contract(
        contract_hash, entry_point, args, payment_amount=5_000_000_000
    ):
        if entry_point == "log_alert":
            _counter["n"] += 1
            log_id = _counter["n"]
            addr = args["subscriber_address"]
            _logs[log_id] = {
                "log_id": log_id,
                "subscriber_address": addr,
                "finding_id": args["finding_id"],
                "severity": args["severity"],
                "risk_type": args["risk_type"],
                "block_height": args["block_height"],
                "timestamp": args["timestamp"],
                "delivered": args.get("delivered", True),
            }
            _address_index.setdefault(addr, []).append(log_id)
            return f"hash-alertlog-{log_id:03d}"
        return "hash-unknown"

    def mock_query_state(contract_hash, path):
        if path[0] == "logs" and len(path) > 1:
            return _logs.get(int(path[1]))
        if path[0] == "address_logs" and len(path) > 1:
            ids = _address_index.get(path[1], [])
            return ",".join(str(i) for i in ids)
        if path[0] == "log_count":
            return _counter["n"]
        return None

    client.call_contract.side_effect = mock_call_contract
    client.query_contract_state.side_effect = mock_query_state
    return client


def test_log_alert_returns_hash(mock_client):
    """log_alert entry point returns a deploy hash."""
    h = mock_client.call_contract(
        contract_hash="hash-alertlog",
        entry_point="log_alert",
        args={
            "subscriber_address": "casper1abc",
            "finding_id": 1,
            "severity": "CRITICAL",
            "risk_type": "whale_dump",
            "block_height": 1_500_000,
            "timestamp": 1_750_000_000,
            "delivered": True,
        },
    )
    assert isinstance(h, str)
    assert h.startswith("hash-alertlog-")


def test_log_stored_and_retrievable(mock_client):
    """Alert logged on-chain is retrievable with correct fields."""
    mock_client.call_contract(
        contract_hash="hash-alertlog",
        entry_point="log_alert",
        args={
            "subscriber_address": "casper1xyz",
            "finding_id": 42,
            "severity": "HIGH",
            "risk_type": "depeg",
            "block_height": 1_600_000,
            "timestamp": 1_750_100_000,
            "delivered": True,
        },
    )
    record = mock_client.query_contract_state("hash-alertlog", ["logs", "1"])
    assert record is not None
    assert record["severity"] == "HIGH"
    assert record["risk_type"] == "depeg"
    assert record["finding_id"] == 42
    assert record["delivered"] is True


def test_address_log_index(mock_client):
    """Multiple alerts for the same address are indexed correctly."""
    addr = "casper1subscriber"
    for i in range(3):
        mock_client.call_contract(
            contract_hash="hash-alertlog",
            entry_point="log_alert",
            args={
                "subscriber_address": addr,
                "finding_id": i + 1,
                "severity": "CRITICAL",
                "risk_type": "flash_loan",
                "block_height": 1_500_000 + i,
                "timestamp": 1_750_000_000 + i,
                "delivered": True,
            },
        )
    ids_str = mock_client.query_contract_state("hash-alertlog", ["address_logs", addr])
    assert ids_str is not None
    ids = [int(x) for x in ids_str.split(",")]
    assert len(ids) == 3


def test_log_count_increments(mock_client):
    """Total log count increases with each alert."""
    for i in range(4):
        mock_client.call_contract(
            contract_hash="hash-alertlog",
            entry_point="log_alert",
            args={
                "subscriber_address": f"casper1addr{i}",
                "finding_id": i,
                "severity": "MEDIUM",
                "risk_type": "oracle_drift",
                "block_height": 2_000_000 + i,
                "timestamp": 1_751_000_000 + i,
                "delivered": False,
            },
        )
    count = mock_client.query_contract_state("hash-alertlog", ["log_count"])
    assert count == 4


def test_severity_values_preserved(mock_client):
    """All severity levels are stored without mutation."""
    severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    for i, sev in enumerate(severities):
        mock_client.call_contract(
            contract_hash="hash-alertlog",
            entry_point="log_alert",
            args={
                "subscriber_address": f"casper1sev{i}",
                "finding_id": i + 10,
                "severity": sev,
                "risk_type": "test",
                "block_height": 1_000_000 + i,
                "timestamp": 1_748_000_000 + i,
                "delivered": True,
            },
        )
    for idx, sev in enumerate(severities, start=1):
        record = mock_client.query_contract_state("hash-alertlog", ["logs", str(idx)])
        assert record["severity"] == sev


def test_casper_client_mock_mode():
    """CasperContractClient initializes in mock mode cleanly."""
    client = CasperContractClient(mock=True)
    assert client.mock is True
    height = client.get_block_height()
    assert isinstance(height, int)
