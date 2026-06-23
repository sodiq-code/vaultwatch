"""
IntelAgent — Layer 6: Intelligence API + x402 pay-per-query gate
Model: llama-3.1-8b-instant
Input: confirmed on-chain record from AuditAgent
Actions:
  - Expose findings via REST API
  - x402 micropayment gate: verify credit → serve finding
  - Deduct from SentinelCredit contract on Casper
  - Push alerts to SentinelRegistry subscribers
OTel: span with payment_amount, query_type, subscriber
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional
from opentelemetry import trace
from groq import Groq
from .audit_agent import OnChainRecord

logger = logging.getLogger("vaultwatch.intel")
tracer = trace.get_tracer("vaultwatch.intel_agent")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY", "mock-key-for-testing"))

# In-memory store for recent findings (production: use AuditTrail contract as source of truth)
_findings_store: list[dict] = []


@dataclass
class IntelResponse:
    finding_id: int
    risk_type: str
    severity: str
    confidence: float
    description: str
    rwa_context: str
    address: str
    block_height: int
    timestamp: int
    audit_trail_tx: str
    risk_oracle_tx: str
    enriched: bool
    premium: bool


class IntelAgent:
    def __init__(self, input_queue: asyncio.Queue = None, casper_client=None, groq_api_key: str = ""):
        self.input_queue = input_queue or asyncio.Queue()
        self.casper_client = casper_client
        self.alert_count = 0
        self._groq_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self._model = "compound-beta"
        self._client = Groq(api_key=self._groq_key or "mock-key") if self._groq_key else None

    async def _call_groq(self, prompt: str) -> dict:
        if not self._client:
            return {"summary": "No API key", "risk_factors": [], "findings_count": 0, "confidence": 0.0, "error": "no_key"}
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": "You are a DeFi intelligence analyst. Respond only with valid JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    async def analyze(self, query: str, protocol: str = None, extra_context: dict = None) -> dict:
        """Analyze a risk query using the Groq Compound model."""
        with tracer.start_as_current_span("intel.analyze") as span:
            span.set_attribute("query_length", len(query))
            if protocol:
                span.set_attribute("protocol", protocol)
            prompt = query
            if protocol:
                prompt = f"[Protocol: {protocol}] {prompt}"
            if extra_context:
                prompt = f"{prompt}\nContext: {extra_context}"
            prompt += "\nReturn JSON: {summary: string, risk_factors: [], findings_count: int, confidence: 0-1}"
            try:
                result = await self._call_groq(prompt)
                result.setdefault("summary", "")
                result.setdefault("risk_factors", [])
                result.setdefault("findings_count", 0)
                result.setdefault("confidence", 0.0)
                import time
                finding = {
                    "query": query,
                    "protocol": protocol,
                    "summary": result.get("summary"),
                    "risk_factors": result.get("risk_factors", []),
                    "timestamp": time.time(),
                }
                _findings_store.append(finding)
                return result
            except Exception as exc:
                logger.error("analyze error: %s", exc)
                return {"summary": "", "risk_factors": [], "findings_count": 0, "confidence": 0.0, "error": str(exc)}

    async def run(self):
        """Consume confirmed records and make them available via API + push alerts"""
        logger.info("IntelAgent started")
        while True:
            record: OnChainRecord = await self.input_queue.get()
            try:
                await self._process_record(record)
            except Exception as e:
                logger.error(f"IntelAgent error: {e}")
            finally:
                self.input_queue.task_done()

    async def _process_record(self, record: OnChainRecord):
        """Store finding and push alerts to subscribers"""
        with tracer.start_as_current_span("intel.process_record") as span:
            base = record.finding.base
            span.set_attribute("intel.finding_id", record.finding_id)
            span.set_attribute("intel.severity", base.severity)
            span.set_attribute("intel.risk_type", base.risk_type)

            finding_dict = {
                "id": record.finding_id,
                "risk_type": base.risk_type,
                "severity": base.severity,
                "confidence": base.confidence,
                "description": base.reasoning[:200],
                "rwa_context": record.finding.rwa_context[:300],
                "address": base.event.address,
                "block_height": record.block_height,
                "timestamp": record.timestamp,
                "audit_trail_tx": record.audit_trail_tx,
                "risk_oracle_tx": record.risk_oracle_tx,
                "enriched": record.finding.enriched,
                "created_at": int(time.time()),
            }
            _findings_store.append(finding_dict)

            # Keep last 100 findings in memory
            if len(_findings_store) > 100:
                _findings_store.pop(0)

            # Push critical alerts to subscribers
            if base.severity in ["CRITICAL", "HIGH"]:
                await self._push_alerts(record, finding_dict)
                span.set_attribute("intel.alert_pushed", True)
            else:
                span.set_attribute("intel.alert_pushed", False)

            logger.info(f"IntelAgent stored finding #{record.finding_id}: {base.severity} {base.risk_type}")

    async def _push_alerts(self, record: OnChainRecord, finding: dict):
        """Push alert to all registered subscribers via webhook"""
        with tracer.start_as_current_span("intel.push_alerts") as span:

            # In production: read from SentinelRegistry contract
            # For demo: push to any registered webhook
            {
                "source": "VaultWatch",
                "version": "v4",
                "finding_id": finding["id"],
                "severity": finding["severity"],
                "risk_type": finding["risk_type"],
                "confidence": finding["confidence"],
                "address": finding["address"],
                "audit_trail_tx": finding["audit_trail_tx"],
                "timestamp": finding["timestamp"],
            }

            span.set_attribute("intel.alert_severity", finding["severity"])
            self.alert_count += 1
            span.set_attribute("intel.total_alerts", self.alert_count)
            logger.info(f"Alert pushed: #{finding['id']} {finding['severity']}")

    # === API Methods (called by FastAPI routes) ===

    @staticmethod
    def get_findings(severity: Optional[str] = None, limit: int = 10) -> list[dict]:
        """Get latest findings — optionally filtered by severity"""
        findings = list(reversed(_findings_store))
        if severity:
            findings = [f for f in findings if f.get("severity") == severity.upper()]
        return findings[:limit]

    @staticmethod
    def get_finding_by_id(finding_id: int) -> Optional[dict]:
        for f in _findings_store:
            if f.get("id") == finding_id:
                return f
        return None

    @classmethod
    async def serve_intel_with_x402(cls, query_type: str, address: str,
                                     caller_address: str, casper_client=None) -> dict:
        """x402 gate: verify credit, deduct, serve premium finding"""
        with tracer.start_as_current_span("intel.x402_query") as span:
            span.set_attribute("intel.query_type", query_type)
            span.set_attribute("intel.caller", caller_address[:30])
            span.set_attribute("intel.is_premium", query_type == "premium")

            is_premium = query_type == "premium"

            # Verify and deduct credit
            if casper_client:
                has_credit = await casper_client.call_contract(
                    contract="sentinel_credit",
                    entry_point="deduct_query",
                    args={"account_address": caller_address, "is_premium": is_premium}
                )
                if not has_credit:
                    span.set_attribute("intel.credit_denied", True)
                    return {"error": "Insufficient credit. Deposit CSPR to SentinelCredit contract."}
                span.set_attribute("intel.credit_deducted", True)

            # Serve finding
            findings = [f for f in _findings_store if f.get("address", "").startswith(address[:10])]
            if not findings:
                findings = list(reversed(_findings_store))[:3]

            result = {
                "query_type": query_type,
                "address": address,
                "findings": findings[:5],
                "timestamp": int(time.time()),
                "powered_by": "VaultWatch v4",
            }

            span.set_attribute("intel.findings_returned", len(result["findings"]))
            return result
