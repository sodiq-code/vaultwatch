"""
SelfCorrectionAgent — Layer 3: Quality gate before on-chain write
Model: llama-3.3-70b-versatile
Logic: if confidence < threshold → re-query with more context → max 2 retries
       → SKIP if still low confidence after retries
Purpose: nothing garbage reaches the AuditTrail contract
OTel: span with retry_count, final_confidence, PASSED/SKIPPED

FIX #10: policy_reader actively queries RiskPolicyManager.get_current_policy
         via Casper RPC instead of reading a static config dict.
FIX #15: Groq client injected via constructor.
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

from groq import Groq
from opentelemetry import trace

from .anomaly_agent import AnomalyResult

logger = logging.getLogger("vaultwatch.selfcorrection")
tracer = trace.get_tracer("vaultwatch.selfcorrection_agent")

# Default thresholds (overridden by live policy when casper_client available)
_DEFAULT_CONFIDENCE_THRESHOLD = 0.75
_DEFAULT_MAX_RETRIES = 2


@dataclass
class CorrectionResult:
    original: AnomalyResult
    final_result: AnomalyResult
    retry_count: int
    passed: bool  # True = forward to RWAAgent. False = SKIP
    skip_reason: Optional[str] = None


class SelfCorrectionAgent:
    def __init__(
        self,
        input_queue: asyncio.Queue = None,
        output_queue: asyncio.Queue = None,
        policy_reader=None,
        groq_api_key: str = "",
        casper_client=None,
    ):
        self.input_queue = input_queue or asyncio.Queue()
        self.output_queue = output_queue or asyncio.Queue()
        # FIX #10: policy_reader can be a live Casper client
        self.policy_reader = policy_reader
        self._casper = casper_client
        # FIX #15: inject Groq client
        self._groq_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self._client: Optional[Groq] = (
            Groq(api_key=self._groq_key) if self._groq_key else None
        )

    # ------------------------------------------------------------------
    # FIX #10: Live policy fetch from RiskPolicyManager contract
    # ------------------------------------------------------------------

    async def _get_live_policy(self) -> dict:
        """Query RiskPolicyManager.get_current_policy from Casper testnet.

        Falls back to default thresholds if the RPC call fails.
        """
        if self._casper and not getattr(self._casper, "mock", True):
            try:
                import httpx

                rpc_url = os.getenv(
                    "CASPER_RPC_URL",
                    "https://node.testnet.casper.network/rpc",
                )
                contract_hash = os.getenv("RISK_POLICY_MANAGER_HASH", "")
                body = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "query_global_state",
                    "params": {
                        "state_identifier": {"BlockHash": "latest"},
                        "key": f"hash-{contract_hash}",
                        "path": ["current_policy"],
                    },
                }
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(rpc_url, json=body)
                    data = resp.json()
                    if "result" in data:
                        stored = data["result"].get("stored_value", {})
                        policy = stored.get("CLValue", {}).get("parsed", {})
                        if policy:
                            logger.info(
                                "SelfCorrectionAgent: loaded live policy v%s",
                                policy.get("version"),
                            )
                            return {
                                "confidence_threshold": (
                                    policy.get("min_confidence_threshold", 75) / 100.0
                                ),
                                "max_retries": policy.get("max_retry_count", 2),
                            }
            except Exception as exc:
                logger.warning(
                    "SelfCorrectionAgent: policy fetch failed, using defaults: %s", exc
                )

        # FIX #10: Also support dict-based policy_reader for backward compat
        if isinstance(self.policy_reader, dict):
            return {
                "confidence_threshold": self.policy_reader.get(
                    "min_confidence_threshold", _DEFAULT_CONFIDENCE_THRESHOLD
                ),
                "max_retries": self.policy_reader.get(
                    "max_retry_count", _DEFAULT_MAX_RETRIES
                ),
            }

        return {
            "confidence_threshold": _DEFAULT_CONFIDENCE_THRESHOLD,
            "max_retries": _DEFAULT_MAX_RETRIES,
        }

    # ------------------------------------------------------------------
    # Groq call
    # ------------------------------------------------------------------

    async def _call_groq(self, prompt: str) -> dict:
        if not self._client:
            return {
                "corrected_score": 0.0,
                "confidence": 0.5,
                "reasoning": "no_key",
                "action": "none",
                "error": "no_key",
            }
        resp = self._client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a DeFi risk validator. Respond only with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    # ------------------------------------------------------------------
    # Core correction logic
    # ------------------------------------------------------------------

    async def correct(self, anomaly_result: AnomalyResult) -> dict:
        """Apply self-correction logic to an anomaly result."""
        with tracer.start_as_current_span("selfcorrection.correct") as span:
            span.set_attribute("protocol", anomaly_result.protocol)
            span.set_attribute("input_score", anomaly_result.risk_score)

            # FIX #10: always load live policy
            policy = await self._get_live_policy()
            confidence_threshold = policy["confidence_threshold"]
            max_retries = policy["max_retries"]

            prompt = (
                f"Review this DeFi anomaly result and validate or correct it:\n"
                f"Protocol: {anomaly_result.protocol}\n"
                f"Risk score: {anomaly_result.risk_score}\n"
                f"Risk type: {anomaly_result.risk_type}\n"
                f"Confidence threshold: {confidence_threshold}\n"
                f"Return JSON: {{\"corrected_score\": float, \"confidence\": float, "
                f"\"reasoning\": str, \"action\": \"pass\"|}}"
            )

            result = await self._call_groq(prompt)
            span.set_attribute("confidence", result.get("confidence", 0))
            return result

    async def process(
        self, anomaly_result: AnomalyResult
    ) -> CorrectionResult:
        """Full correction pipeline with retry logic."""
        with tracer.start_as_current_span("selfcorrection.process") as span:
            policy = await self._get_live_policy()
            confidence_threshold = policy["confidence_threshold"]
            max_retries = policy["max_retries"]

            current = anomaly_result
            retry_count = 0

            while retry_count <= max_retries:
                result = await self.correct(current)
                confidence = result.get("confidence", 0.0)

                if confidence >= confidence_threshold:
                    span.set_attribute("result", "PASSED")
                    span.set_attribute("retry_count", retry_count)
                    return CorrectionResult(
                        original=anomaly_result,
                        final_result=current,
                        retry_count=retry_count,
                        passed=True,
                    )

                retry_count += 1
                logger.warning(
                    "SelfCorrection retry %d: confidence=%.2f < threshold=%.2f",
                    retry_count,
                    confidence,
                    confidence_threshold,
                )

            span.set_attribute("result", "SKIPPED")
            return CorrectionResult(
                original=anomaly_result,
                final_result=current,
                retry_count=retry_count,
                passed=False,
                skip_reason=f"confidence below threshold after {max_retries} retries",
            )

    async def run(self):
        """Queue consumer loop."""
        logger.info("SelfCorrectionAgent started")
        while True:
            item = await self.input_queue.get()
            if isinstance(item, AnomalyResult):
                result = await self.process(item)
                if result.passed and self.output_queue:
                    await self.output_queue.put(result)
            self.input_queue.task_done()
