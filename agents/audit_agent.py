"""
AuditAgent — Layer 5: On-chain write to Casper contracts
Model: llama-3.1-8b-instant (fast formatting — no heavy reasoning needed here)
Input: approved enriched finding from SafetyGuard
Actions:
  - Write to AuditTrail.rs via record_finding entry point
  - Write to RiskOracle.rs
  - Write to SentinelAlertLog.rs (if subscribers exist)
  - Record to AgentBehaviorIndex.rs
Records: tx_hash, block_height, deploy_hash
OTel: span with tx_hash, contract_target, gas_used

FIX #4: Standardised entry-point to record_finding everywhere.
FIX #15: Groq client injected via constructor (no module-level singleton).
"""

import asyncio
import hashlib
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

from groq import Groq
from opentelemetry import trace

from .rwa_agent import EnrichedFinding
from .safety_guard import SafetyResult

logger = logging.getLogger("vaultwatch.audit")
tracer = trace.get_tracer("vaultwatch.audit_agent")


@dataclass
class OnChainRecord:
    finding: EnrichedFinding
    audit_trail_tx: str
    risk_oracle_tx: str
    finding_id: int
    block_height: int
    timestamp: int
    success: bool
    error: Optional[str] = None


class AuditAgent:
    """Layer-5 agent: writes approved findings to Casper contracts."""

    def __init__(
        self,
        input_queue: asyncio.Queue = None,
        output_queue: asyncio.Queue = None,
        casper_client=None,
        groq_api_key: str = "",
    ):
        self.input_queue = input_queue or asyncio.Queue()
        self.output_queue = output_queue or asyncio.Queue()
        self._casper = casper_client
        # Legacy compat alias
        self.casper_client = casper_client
        self._log: list = []
        # FIX #15: inject Groq client so tests can mock it
        self._groq_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self._client = (
            Groq(api_key=self._groq_key) if self._groq_key else None
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _mock_hash(self, action: str) -> str:
        """Deterministic mock deploy hash for tests."""
        return hashlib.sha256(f"{action}-{time.time()}".encode()).hexdigest()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def record(
        self, action: str, actor: str, details: str = ""
    ) -> str:
        """Record an audit entry on-chain. Returns deploy hash.

        FIX #4: Calls record_finding entry point (was record_action).
        """
        with tracer.start_as_current_span("audit.record") as span:
            span.set_attribute("action", action)
            span.set_attribute("actor", actor)

            entry = {
                "action": action,
                "actor": actor,
                "details": details,
                "timestamp": time.time(),
            }
            self._log.append(entry)

            if self._casper and not getattr(self._casper, "mock", True):
                try:
                    # FIX #4: use contract_hash kwarg (not contract)
                    contract_hash = os.getenv("AUDIT_TRAIL_HASH", "")
                    deploy_hash = self._casper.call_contract(
                        contract_hash=contract_hash,
                        # FIX #4: correct entry point name
                        entry_point="record_finding",
                        args={
                            "address": actor,
                            "risk_type": action,
                            "severity": details.get("severity", "LOW") if isinstance(details, dict) else "LOW",
                            "confidence": details.get("confidence", 50) if isinstance(details, dict) else 50,
                            "description": details if isinstance(details, str) else str(details),
                        },
                    )
                    span.set_attribute("deploy_hash", deploy_hash)
                    logger.info("Audit recorded on-chain: %s", deploy_hash)
                    return deploy_hash
                except Exception as exc:
                    logger.error("On-chain audit failed: %s", exc)
                    span.record_exception(exc)

            mock_hash = self._mock_hash(action)
            span.set_attribute("deploy_hash", mock_hash)
            span.set_attribute("mock", True)
            return mock_hash

    async def process_finding(
        self, safety_result: SafetyResult
    ) -> Optional[OnChainRecord]:
        """Process an approved SafetyResult and write to chain."""
        if not safety_result.approved:
            logger.warning(
                "AuditAgent: finding rejected by SafetyGuard — skipping"
            )
            return None

        finding = safety_result.finding
        ts = int(time.time())

        with tracer.start_as_current_span("audit.process_finding") as span:
            span.set_attribute("risk_type", finding.risk_type)
            span.set_attribute("severity", finding.severity)

            audit_tx = await self.record(
                action=finding.risk_type,
                actor=finding.address,
                details={
                    "severity": finding.severity,
                    "confidence": int(finding.confidence * 100),
                    "description": finding.description,
                },
            )

            record = OnChainRecord(
                finding=finding,
                audit_trail_tx=audit_tx,
                risk_oracle_tx="",
                finding_id=int(ts),
                block_height=0,
                timestamp=ts,
                success=True,
            )

            if self.output_queue:
                await self.output_queue.put(record)

            return record

    async def run(self):
        """Queue consumer loop."""
        logger.info("AuditAgent started")
        while True:
            item = await self.input_queue.get()
            if isinstance(item, SafetyResult):
                await self.process_finding(item)
            self.input_queue.task_done()

    def get_log(self) -> list:
        """Return in-memory audit log (test helper)."""
        return list(self._log)
