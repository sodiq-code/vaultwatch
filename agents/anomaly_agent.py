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

# No module-level Groq client — injected per-instance via the constructor
# (``groq_client=...``) or built from ``groq_api_key``. Tests inject a mock
# client and exercise the real ``_classify`` production path.

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
    _UNSET = object()  # sentinel: distinguishes "not provided" from "explicitly empty"

    def __init__(
        self,
        input_queue: asyncio.Queue = None,
        output_queue: asyncio.Queue = None,
        groq_api_key=_UNSET,
        groq_client=None,
    ):
        self.input_queue = input_queue or asyncio.Queue()
        self.output_queue = output_queue or asyncio.Queue()
        self.decision_count = 0
        # When groq_api_key is explicitly provided (even as ""), use it directly.
        # When not provided (default sentinel), fall back to env var.
        # This ensures groq_api_key="" → no client (tests verify fail-safe paths).
        if groq_api_key is AnomalyAgent._UNSET:
            self._groq_key = os.getenv("GROQ_API_KEY", "")
        else:
            self._groq_key = groq_api_key
        # Inject a pre-built client (tests / DI) or construct one from the key.
        if groq_client is not None:
            self._client = groq_client
        else:
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
                exc_str = str(exc)
                is_auth_error = any(code in exc_str for code in ['403', '401', '429', 'Forbidden', 'Unauthorized', 'Rate limit'])
                if is_auth_error:
                    # Heuristic-based anomaly detection when Groq auth fails.
                    # Uses the input metrics to compute a rule-based risk score
                    # instead of returning empty/zero values.
                    score = min(100.0, max(0.0, 
                        abs(metrics.get('price_change_1h', 0)) * 15 +
                        (1 - metrics.get('liquidity_ratio', 0.5)) * 40 +
                        (metrics.get('volume_24h', 0) / 5000) * 10
                    ))
                    anomalies_list = []
                    if abs(metrics.get('price_change_1h', 0)) > 3:
                        anomalies_list.append({"metric": "Price Impact", "value": abs(metrics.get('price_change_1h', 0)), "threshold": 3, "severity": "HIGH"})
                    if metrics.get('liquidity_ratio', 0.5) < 0.5:
                        anomalies_list.append({"metric": "Liquidity Depth", "value": metrics.get('liquidity_ratio', 0.5), "threshold": 0.5, "severity": "CRITICAL"})
                    if metrics.get('volume_24h', 0) > 3000:
                        anomalies_list.append({"metric": "Volume Spike", "value": metrics.get('volume_24h', 0), "threshold": 3000, "severity": "MEDIUM"})
                    severity = "CRITICAL" if score > 70 else "HIGH" if score > 50 else "MEDIUM" if score > 30 else "LOW"
                    return AnomalyResult(
                        protocol=metrics.get('protocol', protocol),
                        risk_score=round(score, 1),
                        anomalies=anomalies_list,
                        recommendation=f"VaultWatch heuristic analysis (Groq unavailable): Risk score {score:.1f}/100. Severity: {severity}. Full AI analysis requires valid Groq key.",
                        timestamp=time.time(),
                        confidence=0.4,
                        severity=severity,
                        model_used="AnomalyAgent (heuristic-fallback)",
                    )
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

            # Fail-safe: with no model client configured, return a medium-
            # confidence result for manual review instead of raising.
            if self._client is None:
                span.set_attribute("anomaly.classify", "skipped_no_client")
                return AnomalyResult(
                    event=event,
                    risk_type="anomalous_flow",
                    severity="MEDIUM",
                    confidence=0.5,
                    reasoning="No Groq client configured — manual review required",
                    raw_response="",
                    model_used="llama-3.3-70b-versatile (unavailable)",
                    tokens_used=0,
                    latency_ms=int(time.time() * 1000) - start_ms,
                )

            response = self._client.chat.completions.create(
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
