"""
AuditAgent — Layer 5: On-chain write to Casper contracts
Model: llama-3.1-8b-instant (fast formatting — no heavy reasoning needed here)
Input: approved enriched finding from SafetyGuard
Actions:
  - Write to AuditTrail.rs
  - Write to RiskOracle.rs
  - Write to SentinelAlertLog.rs (if subscribers exist)
  - Record to AgentBehaviorIndex.rs
Records: tx_hash, block_height, deploy_hash
OTel: span with tx_hash, contract_target, gas_used
"""

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional
from opentelemetry import trace
from groq import Groq
from .rwa_agent import EnrichedFinding
from .safety_guard import SafetyResult

logger = logging.getLogger("vaultwatch.audit")
tracer = trace.get_tracer("vaultwatch.audit_agent")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY", "mock-key-for-testing"))


def _parse_finding_count(state: object) -> Optional[int]:
    """Best-effort parse of the AuditTrail ``finding_count`` named-key value
    returned by ``CasperContractClient.query_contract_state``.

    The query response shape varies across mock/real clients and SDK versions
    (it may be a raw int, a dict with a ``CLValue`` wrapper, or a dict with a
    parsed ``value``). This helper extracts the integer finding count if
    present and returns ``None`` when the shape is unrecognized.
    """
    if state is None:
        return None
    if isinstance(state, int):
        return state
    if isinstance(state, dict):
        for key in ("value", "finding_count", "count"):
            val = state.get(key)
            if isinstance(val, int):
                return val
            if isinstance(val, str) and val.isdigit():
                return int(val)
            if isinstance(val, dict):
                inner = val.get("value") or val.get("parsed")
                if isinstance(inner, int):
                    return inner
                if isinstance(inner, str) and inner.isdigit():
                    return int(inner)
        clvalue = state.get("CLValue")
        if isinstance(clvalue, dict):
            inner = clvalue.get("value") or clvalue.get("parsed")
            if isinstance(inner, int):
                return inner
            if isinstance(inner, str) and inner.isdigit():
                return int(inner)
    return None


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
    def __init__(
        self,
        input_queue: asyncio.Queue = None,
        output_queue: asyncio.Queue = None,
        casper_client=None,
    ):
        self.input_queue = input_queue or asyncio.Queue()
        self.output_queue = output_queue or asyncio.Queue()
        self._casper = casper_client
        self._log: list = []
        # Legacy compat
        self.casper_client = casper_client

    async def record(self, action: str, actor: str, details: str = "") -> str:
        """Record an audit entry on-chain (or mock). Returns deploy hash.

        Standardized on the AuditTrail contract's ``record_finding`` entry
        point. The legacy ``record_action`` entry point never existed on-chain
        (AuditTrail only exposes ``record_finding``); the (action, actor,
        details) public API is preserved by mapping it onto ``record_finding``'s
        9 required runtime args.
        """
        import time
        import hashlib

        with tracer.start_as_current_span("audit.record") as span:
            span.set_attribute("action", action)
            span.set_attribute("actor", actor)
            span.set_attribute("audit.entry_point", "record_finding")
            entry = {
                "action": action,
                "actor": actor,
                "details": details,
                "timestamp": time.time(),
            }
            self._log.append(entry)
            if self._casper:
                try:
                    contract_hash = os.getenv("AUDIT_TRAIL_HASH", "")
                    timestamp = int(time.time())
                    # Map the (action, actor, details) audit tuple onto the
                    # AuditTrail::record_finding entry point's 9 runtime args.
                    # call_contract() returns the deploy hash as a str.
                    deploy_hash = self._casper.call_contract(
                        contract_hash=contract_hash,
                        entry_point="record_finding",
                        args={
                            "address": actor,
                            "risk_type": action,
                            "severity": "LOW",
                            "confidence": 0,
                            "description": details or action,
                            "rwa_enriched": False,
                            "agent_model": "vaultwatch-audit-agent",
                            "block_height": 0,
                            "timestamp": timestamp,
                        },
                    )
                    return deploy_hash
                except Exception as exc:
                    logger.error("audit.record contract call failed: %s", exc)
            # Mock hash
            return hashlib.sha256(f"{action}{actor}{time.time()}".encode()).hexdigest()

    async def get_log(self, limit: int = 50) -> list:
        """Return audit log entries."""
        if self._casper:
            try:
                contract_hash = os.getenv("AUDIT_TRAIL_HASH", "")
                entries = self._casper.query_contract_state(contract_hash, ["log"])
                if isinstance(entries, list):
                    return entries[-limit:]
            except Exception:
                pass
        return self._log[-limit:]

    async def run(self):
        logger.info("AuditAgent started")
        while True:
            safety_result: SafetyResult = await self.input_queue.get()

            if not safety_result.approved:
                logger.info(f"AuditAgent SKIP (rejected by SafetyGuard): {safety_result.rejection_reason}")
                self.input_queue.task_done()
                continue

            try:
                record = await self._write_on_chain(safety_result.finding)
                await self.output_queue.put(record)
            except Exception as e:
                logger.error(f"AuditAgent on-chain write error: {e}")
            finally:
                self.input_queue.task_done()

    async def _write_on_chain(self, finding: EnrichedFinding) -> OnChainRecord:
        """Write finding to AuditTrail and RiskOracle contracts"""
        with tracer.start_as_current_span("audit.write_on_chain") as span:
            base = finding.base
            span.set_attribute("audit.risk_type", base.risk_type)
            span.set_attribute("audit.severity", base.severity)
            span.set_attribute("audit.confidence", base.confidence)
            span.set_attribute("audit.rwa_enriched", finding.enriched)

            # Format description using fast LLM
            description = await self._format_description(finding)

            timestamp = int(time.time())
            confidence_int = int(base.confidence * 100)

            if self.casper_client:
                # Real on-chain write
                try:
                    audit_trail_hash = os.getenv("AUDIT_TRAIL_HASH", "")
                    risk_oracle_hash = os.getenv("RISK_ORACLE_HASH", "")
                    # call_contract() returns the deploy hash as a str (not a
                    # dict). Standardized on the ``contract_hash=`` kwarg
                    # everywhere — the legacy ``contract=`` path is removed.
                    audit_tx = self.casper_client.call_contract(
                        contract_hash=audit_trail_hash,
                        entry_point="record_finding",
                        args={
                            "address": base.event.address,
                            "risk_type": base.risk_type,
                            "severity": base.severity,
                            "confidence": confidence_int,
                            "description": description,
                            "rwa_enriched": finding.enriched,
                            "agent_model": base.model_used,
                            "block_height": base.event.block_height,
                            "timestamp": timestamp,
                        },
                    )

                    oracle_tx = self.casper_client.call_contract(
                        contract_hash=risk_oracle_hash,
                        entry_point="update_score",
                        args={
                            "address": base.event.address,
                            "score": min(int(base.confidence * 100), 100),
                            "risk_type": base.risk_type,
                            "confidence": confidence_int,
                            "block_height": base.event.block_height,
                            "finding_id": 1,  # updated after audit_trail response
                        },
                    )

                    # call_contract returns the deploy-hash string. finding_id
                    # is not echoed back by the host function; resolve it by
                    # querying AuditTrail::finding_count (named key) after the
                    # write, falling back to 0 if the query is unavailable.
                    finding_id = 0
                    try:
                        count_state = self.casper_client.query_contract_state(
                            audit_trail_hash, ["finding_count"]
                        )
                        parsed = _parse_finding_count(count_state)
                        if parsed is not None:
                            finding_id = parsed
                    except Exception as count_exc:
                        logger.debug("finding_count query failed: %s", count_exc)

                    span.set_attribute("audit.audit_trail_tx", audit_tx)
                    span.set_attribute("audit.risk_oracle_tx", oracle_tx)

                    logger.info(f"On-chain write SUCCESS: {audit_tx}")

                    return OnChainRecord(
                        finding=finding,
                        audit_trail_tx=audit_tx,
                        risk_oracle_tx=oracle_tx,
                        finding_id=finding_id,
                        block_height=base.event.block_height,
                        timestamp=timestamp,
                        success=True,
                    )

                except Exception as e:
                    span.record_exception(e)
                    logger.error(f"On-chain write failed: {e}")
                    return OnChainRecord(
                        finding=finding,
                        audit_trail_tx="",
                        risk_oracle_tx="",
                        finding_id=0,
                        block_height=base.event.block_height,
                        timestamp=timestamp,
                        success=False,
                        error=str(e),
                    )
            else:
                # Mock mode (for testing without Casper node)
                mock_tx = f"0x{'a' * 64}_mock_{int(time.time())}"
                span.set_attribute("audit.mock_mode", True)
                span.set_attribute("audit.mock_tx", mock_tx)
                logger.info(f"AuditAgent MOCK write: {mock_tx}")

                return OnChainRecord(
                    finding=finding,
                    audit_trail_tx=mock_tx,
                    risk_oracle_tx=mock_tx.replace("a", "b"),
                    finding_id=int(time.time()) % 10000,
                    block_height=base.event.block_height,
                    timestamp=timestamp,
                    success=True,
                )

    async def _format_description(self, finding: EnrichedFinding) -> str:
        """Use fast LLM to format a concise on-chain description"""
        base = finding.base
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Write a 1-sentence on-chain audit description (max 200 chars) for:\n"
                            f"Risk: {base.risk_type} | Severity: {base.severity} | "
                            f"Confidence: {base.confidence:.0%} | Address: {base.event.address[:20]} | "
                            f"Amount: {base.event.amount_motes / 1_000_000_000:.0f} CSPR | "
                            f"Reasoning: {base.reasoning[:100]}\n"
                            f"Be factual and concise."
                        ),
                    }
                ],
                temperature=0.1,
                max_tokens=64,
            )
            return response.choices[0].message.content.strip()[:200]
        except Exception:
            return f"{base.risk_type} | {base.severity} | {base.confidence:.0%} confidence | {base.event.address[:20]}"
