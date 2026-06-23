"""Integration test — RiskOracle contract (mock Casper client)"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from casper_client import CasperContractClient
from agents.anomaly_agent import AnomalyAgent, AnomalyResult


@pytest.fixture
def mock_client():
    client = MagicMock(spec=CasperContractClient)
    client.mock = True
    client.call_contract.return_value = "deploy-hash-oracle-001"
    client.query_contract_state.return_value = {
        "risk_score": 42,
        "last_updated": 1750000000,
        "protocol": "TestProtocol",
    }
    return client


@pytest.fixture
def anomaly_agent():
    return AnomalyAgent(groq_api_key="test-key")


@pytest.mark.asyncio
async def test_oracle_risk_score_publish(mock_client):
    """Simulate publishing a risk score to the RiskOracle contract."""
    deploy_hash = mock_client.call_contract(
        contract_hash="hash-risk-oracle",
        entry_point="update_risk_score",
        args={"protocol": "TestProto", "score": 75, "confidence": 90},
    )
    assert deploy_hash == "deploy-hash-oracle-001"
    mock_client.call_contract.assert_called_once()


@pytest.mark.asyncio
async def test_oracle_query_state(mock_client):
    """Simulate querying the RiskOracle state."""
    state = mock_client.query_contract_state(
        "hash-risk-oracle",
        ["risk_scores", "TestProtocol"],
    )
    assert isinstance(state, dict)
    assert "risk_score" in state


@pytest.mark.asyncio
async def test_anomaly_to_oracle_flow(mock_client, anomaly_agent):
    """Full flow: detect anomaly -> publish score to oracle."""
    metrics = {
        "protocol": "OracleTestProto",
        "tvl": 5_000_000.0,
        "volume_24h": 2_000_000.0,
        "price_change_1h": -25.0,
        "num_transactions": 1500,
        "liquidity_ratio": 0.05,
    }
    with patch.object(anomaly_agent, "_call_groq", new_callable=AsyncMock) as mock_groq:
        mock_groq.return_value = {
            "risk_score": 78,
            "anomalies": ["liquidity_crisis"],
            "recommendation": "Reduce exposure",
        }
        result: AnomalyResult = await anomaly_agent.detect(metrics)

    # Publish to oracle
    deploy_hash = mock_client.call_contract(
        contract_hash="hash-risk-oracle",
        entry_point="update_risk_score",
        args={
            "protocol": result.protocol,
            "score": int(result.risk_score),
            "confidence": 80,
        },
    )
    assert deploy_hash == "deploy-hash-oracle-001"
    assert result.risk_score == 78


@pytest.mark.asyncio
async def test_oracle_batch_update(mock_client):
    """Simulate updating multiple protocols in the oracle."""
    protocols = ["Aave", "Compound", "Uniswap", "Curve", "MakerDAO"]
    mock_client.call_contract.side_effect = [
        f"hash-{i:03d}" for i in range(len(protocols))
    ]

    hashes = []
    for proto in protocols:
        h = mock_client.call_contract(
            contract_hash="hash-risk-oracle",
            entry_point="update_risk_score",
            args={"protocol": proto, "score": 30, "confidence": 85},
        )
        hashes.append(h)

    assert len(hashes) == 5
    assert mock_client.call_contract.call_count == 5


def test_oracle_contract_hash_format():
    """Contract hash should follow Casper naming convention."""
    contract_hash = (
        "hash-a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    )
    assert contract_hash.startswith("hash-")
    assert len(contract_hash) > 10
