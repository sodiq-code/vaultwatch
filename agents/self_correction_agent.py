"""
SelfCorrectionAgent — Layer 3: Quality gate before on-chain write
Model: llama-3.3-70b-versatile
Logic: if confidence < threshold → re-query with more context → max 2 retries
       → SKIP if still low confidence after retries
Purpose: nothing garbage reaches the AuditTrail contract
OTel: span with retry_count, final_confidence, PASSED/SKIPPED
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional
from opentelemetry import trace
from groq import Groq
from .ai_providers import MultiProviderClient
from .anomaly_agent import AnomalyResult

logger = logging.getLogger("vaultwatch.selfcorrection")
tracer = trace.get_tracer("vaultwatch.selfcorrection_agent")

# No module-level Groq client — injected per-instance via the constructor
# (``groq_client=...``) or built from ``groq_api_key``. Tests inject a mock
# client and exercise the real ``_retry_with_context`` production path.


@dataclass
class CorrectionResult:
    original: AnomalyResult
    final_result: AnomalyResult
    retry_count: int
    passed: bool  # True = forward to RWAAgent. False = SKIP
    skip_reason: Optional[str] = None


class SelfCorrectionAgent:
    _UNSET = object()  # sentinel: distinguishes "not provided" from "explicitly empty"

    def __init__(
        self,
        input_queue: asyncio.Queue = None,
        output_queue: asyncio.Queue = None,
        policy_reader=None,
        groq_api_key=_UNSET,
        groq_client=None,
    ):
        self.input_queue = input_queue or asyncio.Queue()
        self.output_queue = output_queue or asyncio.Queue()
        self.policy_reader = policy_reader
        # When groq_api_key is explicitly provided (even as ""), use it directly.
        # When not provided (default sentinel), fall back to env var.
        if groq_api_key is SelfCorrectionAgent._UNSET:
            self._groq_key = os.getenv("GROQ_API_KEY", "")
        else:
            self._groq_key = groq_api_key
        # Build multi-provider client (Groq → OpenRouter → heuristic fallback)
        if groq_client is not None:
            self._mp_client = MultiProviderClient(
                groq_api_key=self._groq_key or "mock-key",
                openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
                groq_client=groq_client,
            )
        elif self._groq_key:
            self._mp_client = MultiProviderClient(
                groq_api_key=self._groq_key,
                openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            )
        else:
            self._mp_client = None
        self._client = groq_client if groq_client is not None else (Groq(api_key=self._groq_key or "mock-key") if self._groq_key else None)

    async def _call_groq(self, prompt: str) -> dict:
        if not self._mp_client:
            return {
                "corrected_score": 0.0,
                "confidence": 0.5,
                "reasoning": "no_key",
                "action": "none",
                "error": "no_key",
            }
        result = self._mp_client.chat_completion_json(
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
        if result is not None:
            return result
        return {
            "corrected_score": 0.0,
            "confidence": 0.5,
            "reasoning": "providers_failed",
            "action": "none",
            "error": "providers_failed",
        }

    async def correct(self, anomaly_result: "AnomalyResult") -> dict:
        """Apply self-correction logic to an anomaly result."""
        with tracer.start_as_current_span("selfcorrection.correct") as span:
            span.set_attribute("protocol", anomaly_result.protocol)
            span.set_attribute("input_score", anomaly_result.risk_score)
            prompt = (
                f"Review this DeFi anomaly result and validate or correct it: "
                f"protocol={anomaly_result.protocol}, risk_score={anomaly_result.risk_score}, "
                f"anomalies={anomaly_result.anomalies}, recommendation={anomaly_result.recommendation}. "
                "Return JSON: {corrected_score: 0-100, confidence: 0-1, reasoning: string, action: alert|escalate|none, protocol: string}"
            )
            try:
                result = await self._call_groq(prompt)
                # Clamp score
                if "corrected_score" in result:
                    result["corrected_score"] = min(100.0, max(0.0, float(result["corrected_score"])))
                result.setdefault("protocol", anomaly_result.protocol)
                return result
            except Exception as exc:
                logger.error("correct error: %s", exc)
                return {
                    "corrected_score": anomaly_result.risk_score,
                    "confidence": 0.0,
                    "error": str(exc),
                    "action": "none",
                }

    async def run(self):
        logger.info("SelfCorrectionAgent started")
        while True:
            result: AnomalyResult = await self.input_queue.get()
            try:
                corrected = await self._evaluate(result)
                if corrected.passed:
                    await self.output_queue.put(corrected.final_result)
            except Exception as e:
                logger.error(f"SelfCorrectionAgent error: {e}")
            finally:
                self.input_queue.task_done()

    async def _evaluate(self, result: AnomalyResult) -> CorrectionResult:
        # Get threshold from RiskPolicyManager (live) or use default
        threshold = 0.75
        max_retries = 2
        if self.policy_reader:
            try:
                policy = await self.policy_reader()
                threshold = policy.get("min_confidence_threshold", 75) / 100
                max_retries = policy.get("max_retry_count", 2)
            except Exception:
                pass

        with tracer.start_as_current_span("selfcorrection.evaluate") as span:
            span.set_attribute("correction.initial_confidence", result.confidence)
            span.set_attribute("correction.threshold", threshold)
            span.set_attribute("correction.risk_type", result.risk_type)
            span.set_attribute("correction.severity", result.severity)

            # Fast path: confidence is above threshold
            if result.confidence >= threshold:
                span.set_attribute("correction.result", "PASSED_IMMEDIATELY")
                span.set_attribute("correction.retry_count", 0)
                return CorrectionResult(
                    original=result,
                    final_result=result,
                    retry_count=0,
                    passed=True,
                )

            # Low confidence — enter retry loop
            current = result
            for attempt in range(max_retries):
                logger.info(f"SelfCorrection retry {attempt + 1}/{max_retries} — confidence {current.confidence:.2f} < {threshold}")
                current = await self._retry_with_context(current, attempt + 1)
                if current.confidence >= threshold:
                    span.set_attribute("correction.retry_count", attempt + 1)
                    span.set_attribute("correction.final_confidence", current.confidence)
                    span.set_attribute("correction.result", "PASSED_AFTER_RETRY")
                    return CorrectionResult(
                        original=result,
                        final_result=current,
                        retry_count=attempt + 1,
                        passed=True,
                    )

            # Still low confidence after all retries — SKIP
            span.set_attribute("correction.retry_count", max_retries)
            span.set_attribute("correction.final_confidence", current.confidence)
            span.set_attribute("correction.result", "SKIPPED")
            logger.info(f"SelfCorrection SKIP: confidence {current.confidence:.2f} after {max_retries} retries")

            return CorrectionResult(
                original=result,
                final_result=current,
                retry_count=max_retries,
                passed=False,
                skip_reason=f"Confidence {current.confidence:.2f} below threshold {threshold} after {max_retries} retries",
            )

    async def _retry_with_context(self, result: AnomalyResult, attempt: int) -> AnomalyResult:
        """Re-query with additional context to improve confidence"""
        with tracer.start_as_current_span("selfcorrection.retry") as span:
            span.set_attribute("correction.attempt", attempt)

            # Fail-safe: with no model client configured, return the result
            # unchanged so the retry loop terminates gracefully (the evaluate
            # loop will SKIP the finding on persistently-low confidence).
            if self._client is None:
                span.set_attribute("correction.retry", "skipped_no_client")
                return result

            response = self._client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are VaultWatch SelfCorrectionAgent. A previous classification had low confidence. "
                            "Re-analyze with additional context. Be more decisive — eliminate ambiguity. "
                            "If evidence is genuinely insufficient, set confidence to 0.3 and risk_type to 'benign'. "
                            "Respond with valid JSON only:\n"
                            '{"risk_type": str, "severity": str, "confidence": float, "reasoning": str}'
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Previous classification (attempt {attempt}):\n"
                            f"Risk Type: {result.risk_type}\n"
                            f"Severity: {result.severity}\n"
                            f"Confidence: {result.confidence}\n"
                            f"Reasoning: {result.reasoning}\n\n"
                            f"Original event:\n"
                            f"Type: {result.event.event_type}\n"
                            f"Address: {result.event.address}\n"
                            f"Amount: {result.event.amount_motes / 1_000_000_000:.2f} CSPR\n"
                            f"Block: {result.event.block_height}\n\n"
                            "Re-classify with improved confidence. Be decisive."
                        ),
                    },
                ],
                temperature=0.1,
                max_tokens=512,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            span.set_attribute("correction.tokens_used", response.usage.total_tokens)

            try:
                parsed = json.loads(content)
                from .anomaly_agent import AnomalyResult

                return AnomalyResult(
                    event=result.event,
                    risk_type=parsed.get("risk_type", result.risk_type),
                    severity=parsed.get("severity", result.severity),
                    confidence=float(parsed.get("confidence", result.confidence)),
                    reasoning=parsed.get("reasoning", result.reasoning),
                    raw_response=content,
                    model_used="llama-3.3-70b-versatile",
                    tokens_used=response.usage.total_tokens,
                    latency_ms=0,
                )
            except Exception:
                return result  # Return unchanged if parse fails
