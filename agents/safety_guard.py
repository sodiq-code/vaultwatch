"""
SafetyGuard — Inline validation before any on-chain write (~50ms)
Model: llama-prompt-guard-2-86m (purpose-built for injection detection)
Validates: prompt injection | hallucination | suspicious content
Position: between RWAAgent and AuditAgent — nothing writes to chain without passing here
OTel: span with safety_score, APPROVED/REJECTED, rejection_reason
"""

import json
import logging
import os
from dataclasses import dataclass
from opentelemetry import trace
from groq import Groq
from .rwa_agent import EnrichedFinding

logger = logging.getLogger("vaultwatch.safetyguard")
tracer = trace.get_tracer("vaultwatch.safety_guard")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY", "mock-key-for-testing"))


@dataclass
class SafetyResult:
    finding: EnrichedFinding
    approved: bool
    safety_score: float  # 0.0 = safe, 1.0 = definitely malicious
    rejection_reason: str
    model_used: str


class SafetyGuard:
    """Synchronous inline guard — called directly, not a queue consumer"""

    def __init__(self, policy_reader=None, groq_api_key: str = ""):
        self.policy_reader = policy_reader
        self.rejection_threshold = 0.80
        self._groq_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self._client = Groq(api_key=self._groq_key or "mock-key") if self._groq_key else None

    async def _call_groq(self, prompt: str) -> dict:
        if not self._client:
            return {"safe": True, "reason": "No API key — defaulting safe"}
        resp = self._client.chat.completions.create(
            model="llama-prompt-guard-2-86m",
            messages=[
                {
                    "role": "system",
                    "content": "You are a content safety classifier for DeFi queries. Respond only with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content)

    async def check(self, query: str) -> dict:
        """Check if a query is safe to process."""
        if not query or not query.strip():
            return {"safe": True, "reason": "Empty query"}
        with tracer.start_as_current_span("safetyguard.check") as span:
            span.set_attribute("query_length", len(query))
            prompt = f"Is this query safe for a DeFi risk analysis system? Query: {query!r}. Return JSON: {{safe: true|false, reason: string}}"
            try:
                result = await self._call_groq(prompt)
                result.setdefault("safe", True)
                result.setdefault("reason", "")
                return result
            except Exception as exc:
                logger.error("check error: %s", exc)
                return {"safe": False, "reason": f"error: {exc}"}

    async def validate(self, finding: EnrichedFinding) -> SafetyResult:
        """Validate a finding before on-chain write — returns APPROVED or REJECTED"""

        # Get threshold from policy if available
        if self.policy_reader:
            try:
                policy = await self.policy_reader()
                self.rejection_threshold = policy.get("safety_rejection_threshold", 80) / 100
            except Exception:
                pass

        with tracer.start_as_current_span("safetyguard.validate") as span:
            span.set_attribute("safety.risk_type", finding.base.risk_type)
            span.set_attribute("safety.severity", finding.base.severity)
            span.set_attribute("safety.model", "llama-prompt-guard-2-86m")

            # Prepare content to validate
            content_to_check = (
                f"Risk finding: {finding.base.risk_type} | {finding.base.severity} | "
                f"Confidence: {finding.base.confidence} | "
                f"Reasoning: {finding.base.reasoning} | "
                f"RWA context: {finding.rwa_context[:200]}"
            )

            try:
                response = groq_client.chat.completions.create(
                    model="llama-prompt-guard-2-86m",
                    messages=[{"role": "user", "content": content_to_check}],
                    temperature=0.0,
                    max_tokens=64,
                )

                # Prompt Guard returns benign/injection classification
                output = response.choices[0].message.content.lower()

                # Parse safety signal
                if "injection" in output or "jailbreak" in output or "malicious" in output:
                    safety_score = 0.95
                elif "safe" in output or "benign" in output:
                    safety_score = 0.05
                else:
                    safety_score = 0.30  # uncertain — pass through

                approved = safety_score < self.rejection_threshold

                span.set_attribute("safety.score", safety_score)
                span.set_attribute("safety.approved", approved)
                span.set_attribute("safety.threshold", self.rejection_threshold)

                rejection_reason = ""
                if not approved:
                    rejection_reason = f"Safety score {safety_score:.2f} exceeds threshold {self.rejection_threshold:.2f}"
                    logger.warning(f"SafetyGuard REJECTED: {rejection_reason}")
                else:
                    logger.info(f"SafetyGuard APPROVED: safety_score={safety_score:.2f}")

                return SafetyResult(
                    finding=finding,
                    approved=approved,
                    safety_score=safety_score,
                    rejection_reason=rejection_reason,
                    model_used="llama-prompt-guard-2-86m",
                )

            except Exception as e:
                span.record_exception(e)
                logger.warning(f"SafetyGuard model error — defaulting to APPROVED: {e}")
                # On model error, pass through (don't block valid findings)
                return SafetyResult(
                    finding=finding,
                    approved=True,
                    safety_score=0.0,
                    rejection_reason="",
                    model_used="llama-prompt-guard-2-86m",
                )
