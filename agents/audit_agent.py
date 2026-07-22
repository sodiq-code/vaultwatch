"""
AuditAgent — Layer 5: On-chain write to Casper contracts
Model: llama-3.1-8b-instant (fast formatting — no heavy reasoning needed here)
Input: approved enriched finding from SafetyGuard
Actions:
  - Write to AuditTrail.rs
  - Write to RiskOracle.rs
  - Write to SentinelAlertLog.rs (if subscribers exist)
  - Record to AgentBehaviorIndex.rs
  - Post EAS-style RWA attestation to AuditTrail (Task 3-5)
Records: tx_hash, block_height, deploy_hash
OTel: span with tx_hash, contract_target, gas_used

Task 3-5 additions:
  • EAS-style attestation fields (schemaId, attester, recipient, dataHash, dataEncoded)
  • _build_attestation() creates an attestation object proving data retrieval provenance
  • _post_attestation_on_chain() writes the attestation to AuditTrail via record_finding
  • OnChainRecord now includes attestation fields
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional
from opentelemetry import trace
from groq import Groq
from .rwa_agent import EnrichedFinding, RWAFeedData
from .safety_guard import SafetyResult

logger = logging.getLogger("vaultwatch.audit")
tracer = trace.get_tracer("vaultwatch.audit_agent")

# No module-level Groq client — injected per-instance via the constructor
# (``groq_client=...``) or built from ``GROQ_API_KEY``. Tests inject a mock
# client and exercise the real ``_format_description`` production path.


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
    # EAS-style attestation fields (Task 3-5)
    schema_id: str = ""
    attester: str = ""
    recipient: str = ""
    data_hash: str = ""
    data_encoded: str = ""
    attestation_tx: Optional[str] = None


class AuditAgent:
    def __init__(
        self,
        input_queue: asyncio.Queue = None,
        output_queue: asyncio.Queue = None,
        casper_client=None,
        groq_api_key: str = "",
        groq_client=None,
    ):
        self.input_queue = input_queue or asyncio.Queue()
        self.output_queue = output_queue or asyncio.Queue()
        self._casper = casper_client
        self._log: list = []
        # Legacy compat
        self.casper_client = casper_client
        # Groq client for _format_description (LLM-formatted on-chain text).
        # Injected via constructor (tests / DI) or built from groq_api_key /
        # GROQ_API_KEY. When neither is supplied, _format_description falls
        # back to a static template string — on-chain writes still succeed.
        if groq_client is not None:
            self._client = groq_client
        else:
            _key = groq_api_key or os.getenv("GROQ_API_KEY", "")
            self._client = Groq(api_key=_key or "mock-key") if _key else None

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

                # If the finding was enriched with RWA feed data (feed_source
                # is present), build and post an EAS-style attestation proving
                # the data retrieval provenance.
                if safety_result.finding.feed_source:
                    try:
                        attestation = self._build_attestation(safety_result.finding, None)
                        attestation_tx = await self._post_attestation_on_chain(attestation)
                        record.schema_id = attestation.get("schemaId", "")
                        record.attester = attestation.get("attester", "")
                        record.recipient = attestation.get("recipient", "")
                        record.data_hash = attestation.get("dataHash", "")
                        record.data_encoded = attestation.get("dataEncoded", "")
                        record.attestation_tx = attestation_tx
                        logger.info(f"RWA attestation posted: {attestation_tx}")
                    except Exception as att_exc:
                        logger.error(f"RWA attestation post failed: {att_exc}")

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
                        count_state = self.casper_client.query_contract_state(audit_trail_hash, ["finding_count"])
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
            # Fail-safe: with no model client configured, use the static
            # template — the on-chain write must never block on LLM availability.
            if self._client is None:
                return f"{base.risk_type} | {base.severity} | {base.confidence:.0%} confidence | {base.event.address[:20]}"
            response = self._client.chat.completions.create(
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

    # ------------------------------------------------------------------
    # EAS-style RWA attestation methods (Task 3-5)
    # ------------------------------------------------------------------

    # Well-known schema ID for VaultWatch RWA data provenance attestations.
    # Follows EAS (Ethereum Attestation Service) naming conventions.
    _RWA_ATTESTATION_SCHEMA_ID = "0xvaultwatch-rwa-data-provenance-v1"

    def _build_attestation(
        self,
        finding: EnrichedFinding,
        rwa_feed_data: Optional[RWAFeedData] = None,
    ) -> Dict[str, Any]:
        """Build an EAS-style attestation object proving data retrieval provenance.

        The attestation proves: "I retrieved asset X's data from source Y at
        timestamp Z, and here's the signed proof."

        Args:
            finding: The enriched finding containing RWA context and feed metadata.
            rwa_feed_data: Optional structured RWA feed data (if available from
                a direct feed fetch). When None, the attestation is built from
                the finding's existing enrichment data.

        Returns:
            Dict containing EAS-style attestation fields:
            schemaId, attester, recipient, dataHash, dataEncoded,
            plus VaultWatch-specific feed_source, x402_payment_id, timestamp.
        """
        with tracer.start_as_current_span("audit.build_attestation") as span:
            base = finding.base
            timestamp = int(time.time())

            # The attester is the agent wallet's public key. In production,
            # this would be the Casper account hash of the AuditAgent's signer.
            # In dev/mock mode, use a well-known test key or env override.
            attester = os.getenv("VAULTWATCH_AGENT_PUBLIC_KEY", "0xaudit-agent-public-key-placeholder")

            # The recipient is the finding address (the entity being attested about).
            recipient = base.event.address

            # Build the attestation data payload — the core content being attested.
            attestation_data = {
                "risk_type": base.risk_type,
                "severity": base.severity,
                "confidence": base.confidence,
                "address": base.event.address,
                "amount_motes": base.event.amount_motes,
                "block_height": base.event.block_height,
                "rwa_context": finding.rwa_context[:500],
                "collateral_signals": finding.collateral_signals[:10],
                "yield_data": finding.yield_data[:200],
                "depeg_alerts": finding.depeg_alerts[:10],
                "enrichment_model": finding.enrichment_model,
                "feed_source": finding.feed_source,
                "x402_payment_id": finding.x402_payment_id,
            }

            # If structured RWA feed data was provided, include it in the attestation.
            if rwa_feed_data is not None:
                attestation_data["feed_timestamp"] = rwa_feed_data.timestamp
                attestation_data["feed_version"] = rwa_feed_data.feed_version
                if rwa_feed_data.real_estate:
                    attestation_data["feed_real_estate_summary"] = str(rwa_feed_data.real_estate)[:200]
                if rwa_feed_data.bonds:
                    attestation_data["feed_bonds_summary"] = str(rwa_feed_data.bonds)[:200]
                if rwa_feed_data.commodities:
                    attestation_data["feed_commodities_summary"] = str(rwa_feed_data.commodities)[:200]
                if rwa_feed_data.credit:
                    attestation_data["feed_credit_summary"] = str(rwa_feed_data.credit)[:200]
                if rwa_feed_data.tokenized_assets:
                    attestation_data["feed_tokenized_assets_summary"] = str(rwa_feed_data.tokenized_assets)[:200]

            # Compute SHA-256 hash of the attestation data (proves data integrity).
            data_json = json.dumps(attestation_data, sort_keys=True, separators=(",", ":"))
            data_hash = hashlib.sha256(data_json.encode("utf-8")).hexdigest()

            # Base64-encode the full attestation data (for on-chain storage).
            data_encoded = base64.b64encode(data_json.encode("utf-8")).decode("utf-8")

            attestation = {
                "schemaId": self._RWA_ATTESTATION_SCHEMA_ID,
                "attester": attester,
                "recipient": recipient,
                "dataHash": data_hash,
                "dataEncoded": data_encoded,
                "feed_source": finding.feed_source,
                "x402_payment_id": finding.x402_payment_id,
                "timestamp": timestamp,
            }

            span.set_attribute("attestation.schema_id", attestation["schemaId"])
            span.set_attribute("attestation.attester", attestation["attester"])
            span.set_attribute("attestation.recipient", attestation["recipient"])
            span.set_attribute("attestation.data_hash", attestation["dataHash"])
            span.set_attribute("attestation.feed_source", attestation["feed_source"])

            logger.info(
                "Built attestation: schema=%s, recipient=%s, dataHash=%s, feed=%s",
                attestation["schemaId"],
                recipient[:20],
                data_hash[:16],
                attestation["feed_source"],
            )

            return attestation

    async def _post_attestation_on_chain(self, attestation: Dict[str, Any]) -> str:
        """Write the attestation to AuditTrail via record_finding.

        Uses the same pattern as _write_on_chain — calls the AuditTrail
        contract's record_finding entry point with:
          - risk_type = "rwa_attestation"
          - description = JSON string containing {schemaId, attester, recipient,
            dataHash, dataEncoded, feed_source, x402_payment_id, timestamp}
          - rwa_enriched = True (since this specifically about RWA data verification)

        Returns the deploy hash (or mock hash in test mode).
        """
        with tracer.start_as_current_span("audit.post_attestation") as span:
            span.set_attribute("attestation.schema_id", attestation.get("schemaId", ""))
            span.set_attribute("attestation.attester", attestation.get("attester", ""))
            span.set_attribute("attestation.recipient", attestation.get("recipient", ""))
            span.set_attribute("attestation.data_hash", attestation.get("dataHash", ""))

            # Build the description as a JSON string containing all attestation fields.
            attestation_description = json.dumps(
                {
                    "schemaId": attestation.get("schemaId", ""),
                    "attester": attestation.get("attester", ""),
                    "recipient": attestation.get("recipient", ""),
                    "dataHash": attestation.get("dataHash", ""),
                    "dataEncoded": attestation.get("dataEncoded", ""),
                    "feed_source": attestation.get("feed_source", ""),
                    "x402_payment_id": attestation.get("x402_payment_id", ""),
                    "timestamp": attestation.get("timestamp", 0),
                },
                sort_keys=True,
            )

            timestamp = int(time.time())
            recipient = attestation.get("recipient", "unknown")

            if self.casper_client:
                try:
                    audit_trail_hash = os.getenv("AUDIT_TRAIL_HASH", "")
                    deploy_hash = self.casper_client.call_contract(
                        contract_hash=audit_trail_hash,
                        entry_point="record_finding",
                        args={
                            "address": recipient,
                            "risk_type": "rwa_attestation",
                            "severity": "INFO",
                            "confidence": 100,
                            "description": attestation_description,
                            "rwa_enriched": True,
                            "agent_model": "vaultwatch-audit-agent-eas",
                            "block_height": 0,
                            "timestamp": timestamp,
                        },
                    )
                    span.set_attribute("attestation.deploy_hash", deploy_hash)
                    logger.info(f"Attestation on-chain write SUCCESS: {deploy_hash}")
                    return deploy_hash
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_attribute("attestation.error", str(exc))
                    logger.error(f"Attestation on-chain write failed: {exc}")
                    # Fall back to mock hash
                    mock_hash = hashlib.sha256(f"attestation-{attestation.get('dataHash', '')}-{timestamp}".encode()).hexdigest()
                    return f"0x{mock_hash}_mock_attestation"
            else:
                # Mock mode (no Casper client)
                mock_hash = hashlib.sha256(f"attestation-{attestation.get('dataHash', '')}-{timestamp}".encode()).hexdigest()
                mock_tx = f"0x{mock_hash}_mock_attestation_{int(time.time())}"
                span.set_attribute("attestation.mock_mode", True)
                span.set_attribute("attestation.mock_tx", mock_tx)
                logger.info(f"AuditAgent MOCK attestation: {mock_tx}")
                return mock_tx
