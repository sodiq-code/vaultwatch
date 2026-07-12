"""
VaultWatch — Main Orchestration Pipeline
Wires all 6 agents + sidecar SSE into concurrent asyncio queues.
Run with: python pipeline.py
"""

from __future__ import annotations

import os
import asyncio
import logging
import signal
from typing import Any, Dict

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# Agents
from agents.scanner_agent import ScannerAgent
from agents.anomaly_agent import AnomalyAgent, AnomalyResult
from agents.self_correction_agent import SelfCorrectionAgent
from agents.rwa_agent import RWAAgent
from agents.safety_guard import SafetyGuard
from agents.audit_agent import AuditAgent
from agents.intel_agent import IntelAgent

# Sidecar
from streaming.sidecar_client import SidecarClient

# Casper
from casper_client import CasperContractClient

# ---------------------------------------------------------------------------
# Logging & tracing
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("vaultwatch.pipeline")

_provider = TracerProvider()
_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
trace.set_tracer_provider(_provider)
tracer = trace.get_tracer("vaultwatch.pipeline")

# ---------------------------------------------------------------------------
# Queue capacity
# ---------------------------------------------------------------------------
QUEUE_SIZE = 256

# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class VaultWatchPipeline:
    """
    Orchestrates VaultWatch agents over async queues.

    Data flow:
      sidecar_events -> scanner_queue -> scanner_agent
                     -> anomaly_queue -> anomaly_agent -> self_correction
                     -> rwa_queue    -> rwa_agent
                     -> intel_queue  -> intel_agent
                     -> audit_queue  -> audit_agent
    """

    def __init__(self) -> None:
        groq_key = os.getenv("GROQ_API_KEY", "")
        mock_casper = os.getenv("CASPER_MOCK", "true").lower() == "true"

        self.casper = CasperContractClient(mock=mock_casper)
        self.sidecar = SidecarClient(
            url=os.getenv("CASPER_SIDECAR_URL", "http://localhost:9999/events/main"),
        )

        self.scanner = ScannerAgent(groq_api_key=groq_key)
        self.anomaly = AnomalyAgent(groq_api_key=groq_key)
        self.correction = SelfCorrectionAgent(groq_api_key=groq_key)
        self.rwa = RWAAgent(groq_api_key=groq_key)
        self.safety = SafetyGuard(groq_api_key=groq_key)
        self.audit = AuditAgent(casper_client=self.casper)
        self.intel = IntelAgent(groq_api_key=groq_key)

        # Inter-agent queues
        self.scanner_q: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(QUEUE_SIZE)
        self.anomaly_q: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(QUEUE_SIZE)
        self.rwa_q: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(QUEUE_SIZE)
        self.intel_q: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(QUEUE_SIZE)
        self.audit_q: asyncio.Queue[Dict[str, Any]] = asyncio.Queue(QUEUE_SIZE)
        self.correction_q: asyncio.Queue[AnomalyResult] = asyncio.Queue(QUEUE_SIZE)

        self._running = False

    # ------------------------------------------------------------------
    # Sidecar event fan-out
    # ------------------------------------------------------------------

    async def _sidecar_fan_out(self) -> None:
        """
        Consume Casper Sidecar SSE events and distribute to relevant queues.
        Reconnects on error.
        """
        logger.info("Sidecar fan-out started")
        while self._running:
            try:
                async for event in self.sidecar.stream():
                    if not self._running:
                        break
                    with tracer.start_as_current_span("pipeline.fan_out") as span:
                        span.set_attribute("event_type", event.get("type", "unknown"))

                        event_type = event.get("type", "")

                        # Route Deploy events to scanner + anomaly
                        if event_type in ("Deploy", "DeployProcessed"):
                            await _put_nowait(self.scanner_q, event, "scanner_q")
                            await _put_nowait(self.anomaly_q, event, "anomaly_q")
                            await _put_nowait(
                                self.audit_q,
                                {"action": "deploy_event", "data": event},
                                "audit_q",
                            )

                        # Block events go to intel
                        elif event_type in ("Block", "BlockAdded"):
                            await _put_nowait(self.intel_q, event, "intel_q")

                        # Transfer/step events -> rwa
                        elif event_type in ("Step", "Transfer"):
                            await _put_nowait(self.rwa_q, event, "rwa_q")

                        # Unclassified -> intel as catch-all
                        else:
                            await _put_nowait(self.intel_q, event, "intel_q")

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Sidecar stream error (%s) — reconnecting in 5s", exc)
                await asyncio.sleep(5)

    # ------------------------------------------------------------------
    # Agent workers
    # ------------------------------------------------------------------

    async def _scanner_worker(self) -> None:
        logger.info("Scanner worker started")
        while self._running:
            try:
                event = await asyncio.wait_for(self.scanner_q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            try:
                with tracer.start_as_current_span("pipeline.scanner"):
                    protocol = _extract_protocol(event)
                    result = await self.scanner.scan(protocol=protocol, chain="casper")
                    logger.debug("Scanner result for %s: %s", protocol, result.get("risk_level"))
                    # High-risk scans get forwarded to intel
                    if result.get("risk_level") in ("HIGH", "CRITICAL"):
                        await _put_nowait(
                            self.intel_q,
                            {"type": "scanner_alert", "scan": result},
                            "intel_q",
                        )
            except Exception as exc:
                logger.error("Scanner worker error: %s", exc)
            finally:
                self.scanner_q.task_done()

    async def _anomaly_worker(self) -> None:
        logger.info("Anomaly worker started")
        while self._running:
            try:
                event = await asyncio.wait_for(self.anomaly_q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            try:
                with tracer.start_as_current_span("pipeline.anomaly") as span:
                    metrics = _event_to_metrics(event)
                    result: AnomalyResult = await self.anomaly.detect(metrics)
                    span.set_attribute("risk_score", result.risk_score)

                    if result.risk_score >= 70:
                        # High risk — trigger self-correction
                        await _put_nowait(self.correction_q, result, "correction_q")
                        await _put_nowait(
                            self.audit_q,
                            {"action": "high_risk_anomaly", "data": result.__dict__},
                            "audit_q",
                        )
            except Exception as exc:
                logger.error("Anomaly worker error: %s", exc)
            finally:
                self.anomaly_q.task_done()

    async def _correction_worker(self) -> None:
        logger.info("Self-correction worker started")
        while self._running:
            try:
                anomaly_result = await asyncio.wait_for(self.correction_q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            try:
                with tracer.start_as_current_span("pipeline.self_correction"):
                    corrected = await self.correction.correct(anomaly_result)
                    logger.info(
                        "Self-correction applied for %s — confidence: %.2f",
                        anomaly_result.protocol,
                        corrected.get("confidence", 0),
                    )
            except Exception as exc:
                logger.error("Correction worker error: %s", exc)
            finally:
                self.correction_q.task_done()

    async def _rwa_worker(self) -> None:
        logger.info("RWA worker started")
        while self._running:
            try:
                event = await asyncio.wait_for(self.rwa_q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            try:
                with tracer.start_as_current_span("pipeline.rwa"):
                    asset_data = _event_to_asset(event)
                    result = await self.rwa.assess(asset_data)
                    logger.debug("RWA assessment: %s", result.get("verdict"))
            except Exception as exc:
                logger.error("RWA worker error: %s", exc)
            finally:
                self.rwa_q.task_done()

    async def _intel_worker(self) -> None:
        logger.info("Intel worker started")
        while self._running:
            try:
                event = await asyncio.wait_for(self.intel_q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            try:
                with tracer.start_as_current_span("pipeline.intel"):
                    query = _event_to_query(event)
                    result = await self.intel.analyze(query)
                    logger.debug(
                        "Intel analysis complete — findings: %d",
                        result.get("findings_count", 0),
                    )
            except Exception as exc:
                logger.error("Intel worker error: %s", exc)
            finally:
                self.intel_q.task_done()

    async def _audit_worker(self) -> None:
        logger.info("Audit worker started")
        while self._running:
            try:
                item = await asyncio.wait_for(self.audit_q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            try:
                with tracer.start_as_current_span("pipeline.audit"):
                    await self.audit.record(
                        action=item.get("action", "unknown"),
                        actor="pipeline",
                        details=str(item.get("data", "")),
                    )
            except Exception as exc:
                logger.error("Audit worker error: %s", exc)
            finally:
                self.audit_q.task_done()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Start all workers and the sidecar stream concurrently."""
        self._running = True
        logger.info("VaultWatch pipeline starting...")

        tasks = [
            asyncio.create_task(self._sidecar_fan_out(), name="sidecar_fan_out"),
            asyncio.create_task(self._scanner_worker(), name="scanner_worker"),
            asyncio.create_task(self._anomaly_worker(), name="anomaly_worker"),
            asyncio.create_task(self._correction_worker(), name="correction_worker"),
            asyncio.create_task(self._rwa_worker(), name="rwa_worker"),
            asyncio.create_task(self._intel_worker(), name="intel_worker"),
            asyncio.create_task(self._audit_worker(), name="audit_worker"),
        ]

        def _shutdown(sig: Any, frame: Any) -> None:
            logger.info("Shutdown signal received")
            self._running = False
            for t in tasks:
                t.cancel()

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        logger.info("VaultWatch pipeline running — %d workers active", len(tasks))
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("VaultWatch pipeline shut down cleanly")


# ---------------------------------------------------------------------------
# Event extraction helpers
# ---------------------------------------------------------------------------


def _extract_protocol(event: Dict[str, Any]) -> str:
    return event.get("contract_package_hash") or event.get("deploy_hash", "")[:16] or "unknown"


def _event_to_metrics(event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "protocol": _extract_protocol(event),
        "tvl": float(event.get("amount", 0)),
        "volume_24h": float(event.get("volume", 0)),
        "price_change_1h": float(event.get("price_delta", 0)),
        "num_transactions": int(event.get("tx_count", 1)),
        "liquidity_ratio": float(event.get("liquidity_ratio", 1.0)),
    }


def _event_to_asset(event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "asset_id": event.get("deploy_hash", "unknown"),
        "asset_type": event.get("asset_type", "token"),
        "issuer": event.get("from", "unknown"),
        "collateral_ratio": float(event.get("collateral_ratio", 1.5)),
        "maturity_days": int(event.get("maturity_days", 365)),
        "credit_rating": event.get("credit_rating", "BBB"),
    }


def _event_to_query(event: Dict[str, Any]) -> str:
    event_type = event.get("type", "unknown")
    protocol = _extract_protocol(event)
    return f"Analyze {event_type} event for protocol {protocol}: {str(event)[:200]}"


async def _put_nowait(q: asyncio.Queue, item: Any, name: str) -> None:
    try:
        q.put_nowait(item)
    except asyncio.QueueFull:
        logger.warning("Queue %s is full — dropping item", name)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    asyncio.run(VaultWatchPipeline().run())
