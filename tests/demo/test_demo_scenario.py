"""
Demo scenario test — End-to-end VaultWatch walkthrough.
Simulates the full demonstration flow without a live node.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from agents.scanner_agent import ScannerAgent
from agents.anomaly_agent import AnomalyAgent, AnomalyResult
from agents.self_correction_agent import SelfCorrectionAgent
from agents.rwa_agent import RWAAgent
from agents.safety_guard import SafetyGuard
from agents.audit_agent import AuditAgent
from agents.intel_agent import IntelAgent, _findings_store
from casper_client import CasperContractClient


@pytest.fixture(autouse=True)
def clear_findings():
    _findings_store.clear()
    yield
    _findings_store.clear()


@pytest.fixture
def casper():
    return CasperContractClient(mock=True)


@pytest.fixture
def agents(casper):
    return {
        "scanner": ScannerAgent(groq_api_key="test"),
        "anomaly": AnomalyAgent(groq_api_key="test"),
        "correction": SelfCorrectionAgent(groq_api_key="test"),
        "rwa": RWAAgent(groq_api_key="test"),
        "safety": SafetyGuard(groq_api_key="test"),
        "audit": AuditAgent(casper_client=casper),
        "intel": IntelAgent(groq_api_key="test"),
    }


@pytest.mark.asyncio
async def test_demo_scenario_1_risk_query(agents):
    """Demo 1: User queries risk for a protocol."""
    safety = agents["safety"]
    intel = agents["intel"]

    query = "What is the current risk level for the Casper native CSPR staking protocol?"

    with patch.object(safety, "_call_groq", new_callable=AsyncMock) as mock_safe, \
         patch.object(intel, "_call_groq", new_callable=AsyncMock) as mock_intel:

        mock_safe.return_value = {"safe": True, "reason": "Legitimate risk query"}
        mock_intel.return_value = {
            "summary": "CSPR staking protocol has LOW risk. Native staking is secured by Casper's PoS mechanism.",
            "risk_factors": [],
            "findings_count": 0,
            "confidence": 0.92,
        }

        safe_result = await safety.check(query)
        assert safe_result["safe"] is True

        analysis = await intel.analyze(query, protocol="CSPR-Staking")
        assert "summary" in analysis
        assert analysis.get("confidence", 0) > 0.5

    print(f"\n[DEMO 1] Risk query result: {analysis['summary'][:80]}...")


@pytest.mark.asyncio
async def test_demo_scenario_2_anomaly_detection(agents):
    """Demo 2: Anomaly detected in protocol — triggers self-correction."""
    anomaly = agents["anomaly"]
    correction = agents["correction"]
    audit = agents["audit"]

    metrics = {
        "protocol": "CasperSwap",
        "tvl": 8_500_000.0,
        "volume_24h": 12_000_000.0,  # Suspicious: volume > TVL
        "price_change_1h": -18.5,
        "num_transactions": 3200,
        "liquidity_ratio": 0.04,
    }

    with patch.object(anomaly, "_call_groq", new_callable=AsyncMock) as mock_a, \
         patch.object(correction, "_call_groq", new_callable=AsyncMock) as mock_c:

        mock_a.return_value = {
            "risk_score": 82,
            "anomalies": ["volume_exceeds_tvl", "low_liquidity", "price_decline"],
            "recommendation": "Reduce exposure. Possible liquidity crisis.",
        }
        mock_c.return_value = {
            "corrected_score": 79.0,
            "confidence": 0.87,
            "reasoning": "Pattern matches historical liquidity crisis events",
            "action": "escalate",
        }

        result: AnomalyResult = await anomaly.detect(metrics)
        assert result.risk_score >= 70, "Should be high risk"

        corrected = await correction.correct(result)
        assert corrected.get("confidence", 0) > 0.5

        deploy_hash = await audit.record(
            action="anomaly_escalation",
            actor="pipeline",
            details=f"protocol={result.protocol} score={result.risk_score}",
        )
        assert isinstance(deploy_hash, str)

    print(f"\n[DEMO 2] Anomaly: score={result.risk_score}, action={corrected.get('action')}, audit_hash={deploy_hash[:16]}...")


@pytest.mark.asyncio
async def test_demo_scenario_3_rwa_assessment(agents):
    """Demo 3: Real-world asset assessed for on-chain tokenisation."""
    rwa = agents["rwa"]

    asset = {
        "asset_id": "ng-tbill-2026-001",
        "asset_type": "treasury_bill",
        "issuer": "Central Bank of Nigeria",
        "collateral_ratio": 1.08,
        "maturity_days": 91,
        "credit_rating": "B+",
    }

    with patch.object(rwa, "_call_groq", new_callable=AsyncMock) as mock_rwa:
        mock_rwa.return_value = {
            "verdict": "APPROVED",
            "risk_score": 38.0,
            "notes": "Emerging market sovereign debt. Acceptable for limited tokenisation.",
        }
        result = await rwa.assess(asset)

    assert result["verdict"] == "APPROVED"
    print(f"\n[DEMO 3] RWA assessment: {result['verdict']} (score={result.get('risk_score')})")


@pytest.mark.asyncio
async def test_demo_scenario_4_protocol_scan(agents):
    """Demo 4: Deep security scan of a Casper-deployed protocol."""
    scanner = agents["scanner"]

    with patch.object(scanner, "_call_groq", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = {
            "risk_level": "MEDIUM",
            "vulnerabilities": ["integer_overflow_potential", "unchecked_return_value"],
            "summary": "2 low-severity issues found. No critical vulnerabilities.",
        }
        result = await scanner.scan(
            protocol="CasperVault",
            contract_address="hash-casper-vault-abc123",
            chain="casper",
        )

    assert result["risk_level"] == "MEDIUM"
    assert len(result["vulnerabilities"]) == 2
    print(f"\n[DEMO 4] Scan: {result['risk_level']} — {result['summary']}")


@pytest.mark.asyncio
async def test_demo_scenario_5_full_pipeline_mock(agents, casper):
    """Demo 5: Simulate a complete event processing cycle."""
    # 1. Safety check
    safety = agents["safety"]
    with patch.object(safety, "_call_groq", new_callable=AsyncMock) as m:
        m.return_value = {"safe": True, "reason": "ok"}
        safe = await safety.check("Analyze CasperDex")

    # 2. Scan
    scanner = agents["scanner"]
    with patch.object(scanner, "_call_groq", new_callable=AsyncMock) as m:
        m.return_value = {"risk_level": "LOW", "vulnerabilities": [], "summary": "Clean"}
        scan = await scanner.scan("CasperDex")

    # 3. Anomaly
    anomaly = agents["anomaly"]
    with patch.object(anomaly, "_call_groq", new_callable=AsyncMock) as m:
        m.return_value = {"risk_score": 22, "anomalies": [], "recommendation": "OK"}
        anom = await anomaly.detect({
            "protocol": "CasperDex", "tvl": 2e6, "volume_24h": 100_000,
            "price_change_1h": 0.5, "num_transactions": 80, "liquidity_ratio": 0.6,
        })

    # 4. Intel
    intel = agents["intel"]
    with patch.object(intel, "_call_groq", new_callable=AsyncMock) as m:
        m.return_value = {"summary": "Low risk", "risk_factors": [], "findings_count": 0, "confidence": 0.9}
        intel_result = await intel.analyze("CasperDex risk?", protocol="CasperDex")

    # 5. Audit
    audit = agents["audit"]
    h = await audit.record(action="demo_complete", actor="test_suite", details="all_stages_passed")

    assert safe["safe"] is True
    assert scan["risk_level"] == "LOW"
    assert anom.risk_score == 22
    assert "summary" in intel_result
    assert isinstance(h, str)
    print("\n[DEMO 5] Full pipeline cycle complete — all stages passed.")


@pytest.mark.asyncio
async def test_demo_scenario_6_block_height(casper):
    """Demo 6: Verify live chain connectivity (mock)."""
    height = casper.get_block_height()
    assert isinstance(height, int)
    assert height > 0
    print(f"\n[DEMO 6] Current block height: {height}")
