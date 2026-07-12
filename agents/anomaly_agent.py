"""
AnomalyAgent — Layer 2: Deep risk classification
Model: llama-3.3-70b-versatile (strongest Groq model for nuanced reasoning)
Input: raw event stream from ScannerAgent queue
Output: {severity, risk_type, confidence, reasoning} → SelfCorrectionAgent
OTel: span with severity, confidence, model, tokens_used, risk_type
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from opentelemetry import trace
from groq import Groq
from .scanner_agent import RawEvent

logger = logging.getLogger("vaultwatch.anomaly")
tracer = trace.get_tracer("vaultwatch.anomaly_agent")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY", "mock-key-for-testing"))

RISK_TYPES = [
    "rug_pull",
    "whale_dump",
    "depeg",
    "wash_trade",
    "collateral_drop",
    "flash_loan",
    "anomalous_flow",
    "benign",
]

SEVERITY_LEVELS = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "NONE"]


@dataclass
class AnomalyResult:
    """Unified anomaly result — supports both pipeline (event-based) and direct call patterns."""

    protocol: str = ""
    risk_score: float = 0.0
    anomalies: list = None
    recommendation: str = ""
    timestamp: float = 0.0
    # Legacy pipeline fields (optional)
    event: object = None
    risk_type: str = ""
    severity: str = ""
    confidence: float = 0.0
    reasoning: str = ""
    raw_response: str = ""
    model_used: str = ""
    tokens_used: int = 0
    latency_ms: int = 0

    def __post_init__(self):
        if self.anomalies is None:
            self.anomalies = []


class AnomalyAgent:
    def __init__(
        self,
        input_queue: asyncio.Queue = None,
        output_queue: asyncio.Queue = None,
        groq_api_key: str = "",
    ):
        self.input_queue = input_queue or asyncio.Queue()
        self.output_queue = output_queue or asyncio.Queue()
        self.decision_count = 0
        self._groq_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self._client = Groq(api_key=self._groq_key or "mock-key") if self._groq_key else None

    async def _call_groq(self, prompt: str) -> dict:
        if not self._client:
            return {
                "risk_score": 0,
                "anomalies": [],
                "recommendation": "No API key",
                "error": "no_key",
            }
        resp = self._client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a DeFi anomaly detection system. Respond only with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        import json

        return json.loads(resp.choices[0].message.content)

    async def detect(self, metrics: dict) -> "AnomalyResult":
        """Detect anomalies from protocol metrics dict."""
        with tracer.start_as_current_span("anomaly.detect") as span:
            protocol = metrics.get("protocol", "unknown")
            span.set_attribute("protocol", protocol)
            prompt = f"Analyze these DeFi metrics for anomalies: {metrics}. Return JSON: {{risk_score: 0-100, anomalies: [], recommendation: string}}"
            try:
                result = await self._call_groq(prompt)
                score = min(100.0, max(0.0, float(result.get("risk_score", 0))))
                return AnomalyResult(
                    protocol=protocol,
                    risk_score=score,
                    anomalies=result.get("anomalies", []),
                    recommendation=result.get("recommendation", ""),
                    timestamp=time.time(),
                )
            except Exception as exc:
                logger.error("detect error: %s", exc)
                return AnomalyResult(
                    protocol=protocol,
                    risk_score=0.0,
                    anomalies=[],
                    recommendation="",
                    timestamp=time.time(),
                )

    async def run(self):
        """Consume events from ScannerAgent, classify risk, push to SelfCorrection"""
        logger.info("AnomalyAgent started")
        while True:
            event: RawEvent = await self.input_queue.get()
            try:
                result = await self._classify(event)
                await self.output_queue.put(result)
                self.decision_count += 1
            except Exception as e:
                logger.error(f"AnomalyAgent classification error: {e}")
            finally:
                self.input_queue.task_done()

    async def _classify(self, event: RawEvent) -> AnomalyResult:
        """Classify a single event using llama-3.3-70b-versatile"""
        start_ms = int(time.time() * 1000)

        with tracer.start_as_current_span("anomaly.classify") as span:
            span.set_attribute("event.type", event.event_type)
            span.set_attribute("event.address", event.address[:30])
            span.set_attribute("event.amount_cspr", event.amount_motes / 1_000_000_000)
            span.set_attribute("anomaly.model", "llama-3.3-70b-versatile")

            prompt = self._build_prompt(event)

            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are VaultWatch AnomalyAgent — an expert DeFi risk classifier for the Casper blockchain. "
                            "Analyze the given on-chain event and classify its risk profile. "
                            "You MUST respond with a valid JSON object and nothing else. "
                            "JSON schema:\n"
                            "{\n"
                            '  "risk_type": one of ["rug_pull","whale_dump","depeg","wash_trade","collateral_drop","flash_loan","anomalous_flow","benign"],\n'
                            '  "severity": one of ["CRITICAL","HIGH","MEDIUM","LOW","NONE"],\n'
                            '  "confidence": float between 0.0 and 1.0,\n'
                            '  "reasoning": "concise 1-2 sentence explanation"\n'
                            "}\n"
                            "Be precise. Calibrate confidence honestly. High confidence only when signals are unambiguous."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=512,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            tokens = response.usage.total_tokens
            latency = int(time.time() * 1000) - start_ms

            span.set_attribute("anomaly.tokens_used", tokens)
            span.set_attribute("anomaly.latency_ms", latency)

            try:
                parsed = json.loads(content)
                risk_type = parsed.get("risk_type", "anomalous_flow")
                severity = parsed.get("severity", "MEDIUM")
                confidence = float(parsed.get("confidence", 0.5))
                reasoning = parsed.get("reasoning", "")

                span.set_attribute("anomaly.risk_type", risk_type)
                span.set_attribute("anomaly.severity", severity)
                span.set_attribute("anomaly.confidence", confidence)

                return AnomalyResult(
                    event=event,
                    risk_type=risk_type,
                    severity=severity,
                    confidence=confidence,
                    reasoning=reasoning,
                    raw_response=content,
                    model_used="llama-3.3-70b-versatile",
                    tokens_used=tokens,
                    latency_ms=latency,
                )

            except json.JSONDecodeError:
                span.set_attribute("anomaly.parse_error", True)
                # Fallback: return medium confidence for manual review
                return AnomalyResult(
                    event=event,
                    risk_type="anomalous_flow",
                    severity="MEDIUM",
                    confidence=0.5,
                    reasoning="JSON parse error — manual review required",
                    raw_response=content,
                    model_used="llama-3.3-70b-versatile",
                    tokens_used=tokens,
                    latency_ms=latency,
                )

    def _build_prompt(self, event: RawEvent) -> str:
        amount_cspr = event.amount_motes / 1_000_000_000
        return f"""Casper blockchain event to classify:

Event Type: {event.event_type}
Address: {event.address}
Amount: {amount_cspr:.2f} CSPR ({event.amount_motes} motes)
Block Height: {event.block_height}
Source: {event.source}
Raw Data: {json.dumps(event.raw_data, default=str)[:500]}

Classify this event's DeFi risk profile."""
