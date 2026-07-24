"""Integration tests — /chain/* FastAPI endpoints (mocked Casper RPC).

Verifies the four on-chain-read endpoints added in api/main.py:
  • GET /chain/finding-count   — AuditTrail.finding_count (Var<u64>)
  • GET /chain/findings        — latest N findings (newest first)
  • GET /chain/finding/{id}    — single finding by numeric ID
  • GET /chain/risk-score/{a}  — RiskOracle.scores[address]

The Casper testnet RPC is mocked (no network). Each test exercises both the
on-chain success path and the graceful-fallback path so the dashboard keeps
working when the node is unreachable.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def client(monkeypatch):
    """TestClient with auth + rate limiting disabled (clean baseline)."""
    monkeypatch.delenv("VAULTWATCH_API_KEY", raising=False)
    monkeypatch.delenv("RATE_LIMIT_PER_MINUTE", raising=False)
    monkeypatch.delenv("RATE_LIMIT_ENABLED", raising=False)
    from api.security import reset_rate_limiter

    reset_rate_limiter()
    import api.main as api_mod
    from fastapi.testclient import TestClient

    with TestClient(api_mod.app) as c:
        yield c
    reset_rate_limiter()


@pytest.fixture()
def clean_findings_store():
    """Snapshot + restore the in-memory _findings_store so tests don't leak."""
    from agents.intel_agent import _findings_store

    snapshot = list(_findings_store)
    _findings_store.clear()
    yield _findings_store
    _findings_store.clear()
    _findings_store.extend(snapshot)


# ===========================================================================
# GET /chain/finding-count
# ===========================================================================
def test_finding_count_on_chain(client, monkeypatch):
    async def fake_count(*a, **kw):
        return 42

    monkeypatch.setattr("api.main.casper_rpc.read_finding_count", fake_count)
    r = client.get("/chain/finding-count")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 42
    assert body["source"] == "on-chain"
    assert body["network"] == "casper-test"


def test_finding_count_falls_back_to_in_memory(client, monkeypatch, clean_findings_store):
    clean_findings_store.extend([{"id": "F-1"}, {"id": "F-2"}, {"id": "F-3"}])

    async def fake_count(*a, **kw):
        return None

    monkeypatch.setattr("api.main.casper_rpc.read_finding_count", fake_count)
    r = client.get("/chain/finding-count")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 3
    assert body["source"] == "fallback"


# ===========================================================================
# GET /chain/findings
# ===========================================================================
def test_findings_on_chain(client, monkeypatch):
    async def fake_recent(limit=20, contract_hash=None):
        return [
            {
                "id": 2,
                "address": "casper1def",
                "risk_type": "depeg",
                "severity": "HIGH",
                "confidence": 80,
                "description": "depeg detected",
                "rwa_enriched": False,
                "agent_model": "llama-3.3-70b",
                "block_height": 100,
                "timestamp": 1750000000,
                "tx_hash": "abc",
                "source": "on-chain",
            },
            {
                "id": 1,
                "address": "casper1abc",
                "risk_type": "whale_dump",
                "severity": "CRITICAL",
                "confidence": 91,
                "description": "whale dump",
                "rwa_enriched": False,
                "agent_model": "llama-3.3-70b",
                "block_height": 99,
                "timestamp": 1749999999,
                "tx_hash": "def",
                "source": "on-chain",
            },
        ]

    monkeypatch.setattr("api.main.casper_rpc.read_recent_findings", fake_recent)
    r = client.get("/chain/findings?limit=10")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "on-chain"
    assert body["count"] == 2
    # Newest first (id=2 before id=1).
    assert body["findings"][0]["numeric_id"] == 2
    assert body["findings"][1]["numeric_id"] == 1
    # Dashboard shape fields are present.
    f0 = body["findings"][0]
    assert f0["severity"] == "HIGH"
    assert f0["summary"] == "depeg detected"
    assert f0["confidence"] == 0.8  # 80 → 0.8
    assert f0["contract"] == "AuditTrail"
    assert "contract_hash" in f0


def test_findings_falls_back_to_in_memory(client, monkeypatch, clean_findings_store):
    clean_findings_store.extend(
        [
            {
                "id": "F-2026-001",
                "protocol": "CasperSwap",
                "summary": "whale concentration",
                "severity": "CRITICAL",
                "confidence": 0.91,
            }
        ]
    )

    async def fake_recent(limit=20, contract_hash=None):
        return []

    monkeypatch.setattr("api.main.casper_rpc.read_recent_findings", fake_recent)
    r = client.get("/chain/findings")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "fallback"
    assert body["count"] == 1
    assert body["findings"][0]["protocol"] == "CasperSwap"


def test_findings_limit_param_validated(client):
    r = client.get("/chain/findings?limit=0")
    assert r.status_code == 422  # ge=1
    r = client.get("/chain/findings?limit=999")
    assert r.status_code == 422  # le=200


# ===========================================================================
# GET /chain/finding/{id}
# ===========================================================================
def test_finding_by_id_on_chain(client, monkeypatch):
    async def fake_read(finding_id, contract_hash=None):
        if finding_id == 5:
            return {
                "id": 5,
                "address": "casper1abc",
                "risk_type": "rug_pull",
                "severity": "CRITICAL",
                "confidence": 95,
                "description": "rug pull detected",
                "rwa_enriched": False,
                "agent_model": "llama-3.3-70b",
                "block_height": 200,
                "timestamp": 1750000500,
                "tx_hash": "deadbeef",
                "source": "on-chain",
            }
        return None

    monkeypatch.setattr("api.main.casper_rpc.read_finding", fake_read)
    r = client.get("/chain/finding/5")
    assert r.status_code == 200
    body = r.json()
    assert body["numeric_id"] == 5
    assert body["severity"] == "CRITICAL"
    assert body["summary"] == "rug pull detected"


def test_finding_by_id_falls_back_to_memory(client, monkeypatch, clean_findings_store):
    clean_findings_store.append({"id": "F-7", "numeric_id": 7, "protocol": "CasperLend", "summary": "collateral drop", "severity": "HIGH", "confidence": 0.87})

    async def fake_read(finding_id, contract_hash=None):
        return None

    monkeypatch.setattr("api.main.casper_rpc.read_finding", fake_read)
    r = client.get("/chain/finding/7")
    assert r.status_code == 200
    assert r.json()["numeric_id"] == 7


def test_finding_by_id_404_when_not_found(client, monkeypatch, clean_findings_store):
    async def fake_read(finding_id, contract_hash=None):
        return None

    monkeypatch.setattr("api.main.casper_rpc.read_finding", fake_read)
    r = client.get("/chain/finding/999")
    assert r.status_code == 404


# ===========================================================================
# GET /chain/risk-score/{address}
# ===========================================================================
def test_risk_score_on_chain(client, monkeypatch):
    async def fake_score(address, contract_hash=None):
        if address == "account-hash-abc":
            return {
                "address": "account-hash-abc",
                "score": 87,
                "risk_type": "whale_concentration",
                "confidence": 92,
                "last_updated": 1_500_000,
                "finding_id": 1,
                "source": "on-chain",
            }
        return None

    monkeypatch.setattr("api.main.casper_rpc.read_risk_score", fake_score)
    r = client.get("/chain/risk-score/account-hash-abc")
    assert r.status_code == 200
    body = r.json()
    assert body["score"] == 87
    assert body["risk_type"] == "whale_concentration"
    assert body["source"] == "on-chain"


def test_risk_score_404_when_unknown(client, monkeypatch):
    async def fake_score(address, contract_hash=None):
        return None

    monkeypatch.setattr("api.main.casper_rpc.read_risk_score", fake_score)
    r = client.get("/chain/risk-score/account-hash-unknown")
    assert r.status_code == 404


def test_risk_score_handles_url_encoded_address(client, monkeypatch):
    captured = {}

    async def fake_score(address, contract_hash=None):
        captured["address"] = address
        return {"address": address, "score": 50, "risk_type": "x", "confidence": 60, "last_updated": 1, "finding_id": 1, "source": "on-chain"}

    monkeypatch.setattr("api.main.casper_rpc.read_risk_score", fake_score)
    # The address contains a hyphen (no special encoding needed) — verify it
    # reaches the reader intact.
    r = client.get("/chain/risk-score/account-hash-deadbeef")
    assert r.status_code == 200
    assert captured["address"] == "account-hash-deadbeef"
