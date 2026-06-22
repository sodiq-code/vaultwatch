"""Integration test — Full VaultWatch Pipeline (mock mode)"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from pipeline import VaultWatchPipeline


@pytest.fixture
def pipeline():
    return VaultWatchPipeline()


@pytest.mark.asyncio
async def test_pipeline_initialises(pipeline):
    assert pipeline.scanner is not None
    assert pipeline.anomaly is not None
    assert pipeline.rwa is not None
    assert pipeline.intel is not None
    assert pipeline.audit is not None
    assert pipeline.correction is not None
    assert pipeline.casper is not None
    assert pipeline.sidecar is not None


@pytest.mark.asyncio
async def test_pipeline_queues_created(pipeline):
    assert pipeline.scanner_q is not None
    assert pipeline.anomaly_q is not None
    assert pipeline.rwa_q is not None
    assert pipeline.intel_q is not None
    assert pipeline.audit_q is not None
    assert pipeline.correction_q is not None


@pytest.mark.asyncio
async def test_scanner_worker_processes_event(pipeline):
    event = {"type": "DeployProcessed", "deploy_hash": "abc123", "contract_package_hash": "test_proto"}

    with patch.object(pipeline.scanner, "scan", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = {"risk_level": "LOW", "vulnerabilities": [], "summary": "ok"}
        pipeline._running = True
        await pipeline.scanner_q.put(event)
        # Run worker as task, cancel after item is processed
        task = asyncio.create_task(pipeline._scanner_worker())
        await asyncio.sleep(0.1)  # let worker process the item
        pipeline._running = False
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    mock_scan.assert_called_once()


@pytest.mark.asyncio
async def test_anomaly_worker_processes_event(pipeline):
    event = {"type": "DeployProcessed", "deploy_hash": "xyz789", "amount": "50000"}

    with patch.object(pipeline.anomaly, "detect", new_callable=AsyncMock) as mock_detect:
        from agents.anomaly_agent import AnomalyResult
        import time
        mock_detect.return_value = AnomalyResult(
            protocol="test_proto",
            risk_score=25.0,
            anomalies=[],
            recommendation="Monitor",
            timestamp=time.time(),
        )
        pipeline._running = True
        await pipeline.anomaly_q.put(event)
        task = asyncio.create_task(pipeline._anomaly_worker())
        await asyncio.sleep(0.1)
        pipeline._running = False
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    mock_detect.assert_called_once()


@pytest.mark.asyncio
async def test_audit_worker_records_entry(pipeline):
    item = {"action": "test_action", "data": {"key": "value"}}

    with patch.object(pipeline.audit, "record", new_callable=AsyncMock) as mock_record:
        mock_record.return_value = "deploy-hash-123"
        pipeline._running = True
        await pipeline.audit_q.put(item)
        task = asyncio.create_task(pipeline._audit_worker())
        await asyncio.sleep(0.1)
        pipeline._running = False
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    mock_record.assert_called_once()


@pytest.mark.asyncio
async def test_high_risk_triggers_correction(pipeline):
    """Anomaly score >= 70 should enqueue into correction_q."""
    from agents.anomaly_agent import AnomalyResult
    import time

    event = {"type": "DeployProcessed", "deploy_hash": "risk001", "price_delta": "-40"}
    high_risk_result = AnomalyResult(
        protocol="RiskyProto",
        risk_score=85.0,
        anomalies=["price_drop"],
        recommendation="Pause",
        timestamp=time.time(),
    )

    with patch.object(pipeline.anomaly, "detect", new_callable=AsyncMock) as mock_detect:
        with patch.object(pipeline.audit, "record", new_callable=AsyncMock) as mock_record:
            mock_detect.return_value = high_risk_result
            mock_record.return_value = "hash"
            pipeline._running = True
            await pipeline.anomaly_q.put(event)
            task = asyncio.create_task(pipeline._anomaly_worker())
            await asyncio.sleep(0.1)
            pipeline._running = False
            await asyncio.sleep(0.05)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    assert not pipeline.correction_q.empty()


@pytest.mark.asyncio
async def test_pipeline_mock_casper(pipeline):
    """Ensure pipeline works with mock Casper client."""
    assert pipeline.casper.mock is True
    height = pipeline.casper.get_block_height()
    assert isinstance(height, int)
    assert height > 0
