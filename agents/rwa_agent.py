"""
RWAAgent — Layer 4: Real-World Asset enrichment via live web intelligence
Model: groq/compound (built-in live web search — NO extra API keys)
Input: confirmed anomaly finding
Output: enriched finding with live RWA context (yield rates, depeg news, vault health)
OTel: span with rwa_sources, collateral_ratio, enrichment_type
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from opentelemetry import trace
from groq import Groq
from .anomaly_agent import AnomalyResult

logger = logging.getLogger("vaultwatch.rwa")
tracer = trace.get_tracer("vaultwatch.rwa_agent")

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY", "mock-key-for-testing"))


@dataclass
class EnrichedFinding:
    base: AnomalyResult
    rwa_context: str
    collateral_signals: list[str]
    yield_data: str
    depeg_alerts: list[str]
    enriched: bool
    rwa_sources_count: int
    enrichment_model: str


class RWAAgent:
    def __init__(
        self,
        input_queue: asyncio.Queue = None,
        output_queue: asyncio.Queue = None,
        groq_api_key: str = "",
    ):
        self.input_queue = input_queue or asyncio.Queue()
        self.output_queue = output_queue or asyncio.Queue()
        self._groq_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self._client = Groq(api_key=self._groq_key or "mock-key") if self._groq_key else None
        self._assets: list = []

    async def _call_groq(self, prompt: str) -> dict:
        if not self._client:
            return {
                "verdict": "REVIEW",
                "risk_score": 50.0,
                "notes": "No API key",
                "error": "no_key",
            }
        resp = self._client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {
                    "role": "system",
                    "content": "You are a real-world asset risk analyst. Respond only with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        import json

        return json.loads(resp.choices[0].message.content)

    async def assess(self, asset_data: dict) -> dict:
        """Assess a real-world asset for on-chain tokenisation viability."""
        with tracer.start_as_current_span("rwa.assess") as span:
            span.set_attribute("asset_id", asset_data.get("asset_id", "unknown"))
            prompt = (
                f"Evaluate this real-world asset for on-chain tokenisation: {asset_data}. "
                "Return JSON: {verdict: APPROVED|REJECTED|REVIEW, risk_score: 0-100, notes: string}"
            )
            try:
                result = await self._call_groq(prompt)
                result.setdefault("verdict", "REVIEW")
                self._assets.append(
                    {
                        "asset_id": asset_data.get("asset_id"),
                        "asset_type": asset_data.get("asset_type"),
                    }
                )
                return result
            except Exception as exc:
                logger.error("assess error: %s", exc)
                return {
                    "verdict": "REVIEW",
                    "risk_score": 50.0,
                    "notes": "",
                    "error": str(exc),
                }

    async def list_assets(self) -> list:
        """Return all tracked RWA assets."""
        return list(self._assets)

    async def run(self):
        logger.info("RWAAgent started")
        while True:
            result: AnomalyResult = await self.input_queue.get()
            try:
                enriched = await self._enrich(result)
                await self.output_queue.put(enriched)
            except Exception as e:
                logger.error(f"RWAAgent error: {e}")
                # On failure, pass through with minimal enrichment
                await self.output_queue.put(
                    EnrichedFinding(
                        base=result,
                        rwa_context="RWA enrichment unavailable",
                        collateral_signals=[],
                        yield_data="",
                        depeg_alerts=[],
                        enriched=False,
                        rwa_sources_count=0,
                        enrichment_model="groq/compound",
                    )
                )
            finally:
                self.input_queue.task_done()

    async def _enrich(self, result: AnomalyResult) -> EnrichedFinding:
        """Enrich finding with live RWA web intelligence via Groq Compound"""
        with tracer.start_as_current_span("rwa.enrich") as span:
            span.set_attribute("rwa.risk_type", result.risk_type)
            span.set_attribute("rwa.severity", result.severity)
            span.set_attribute("rwa.model", "groq/compound")

            # Build targeted RWA query based on risk type
            query = self._build_rwa_query(result)

            response = groq_client.chat.completions.create(
                model="compound-beta",  # groq/compound with live web search
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are VaultWatch RWAAgent. Enrich DeFi risk findings with real-world context. "
                            "Search for current stablecoin depeg status, DeFi protocol health, tokenized asset yields, "
                            "and collateral ratios relevant to the finding. "
                            "Return JSON: "
                            '{"rwa_context": str, "collateral_signals": [str], "yield_data": str, '
                            '"depeg_alerts": [str], "sources_found": int}'
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                temperature=0.3,
                max_tokens=1024,
            )

            content = response.choices[0].message.content
            tokens = response.usage.total_tokens

            span.set_attribute("rwa.tokens_used", tokens)

            try:
                # Extract JSON from response (Compound may include tool call text)
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(content[start:end])
                else:
                    parsed = {}

                rwa_context = parsed.get("rwa_context", content[:500])
                collateral_signals = parsed.get("collateral_signals", [])
                yield_data = parsed.get("yield_data", "")
                depeg_alerts = parsed.get("depeg_alerts", [])
                sources_count = parsed.get("sources_found", 1)

                span.set_attribute("rwa.sources_count", sources_count)
                span.set_attribute("rwa.depeg_alerts_count", len(depeg_alerts))
                span.set_attribute("rwa.enriched", True)

                return EnrichedFinding(
                    base=result,
                    rwa_context=rwa_context,
                    collateral_signals=collateral_signals,
                    yield_data=yield_data,
                    depeg_alerts=depeg_alerts,
                    enriched=True,
                    rwa_sources_count=sources_count,
                    enrichment_model="groq/compound",
                )

            except Exception as e:
                span.record_exception(e)
                span.set_attribute("rwa.parse_error", str(e))
                return EnrichedFinding(
                    base=result,
                    rwa_context=content[:500],
                    collateral_signals=[],
                    yield_data="",
                    depeg_alerts=[],
                    enriched=True,
                    rwa_sources_count=0,
                    enrichment_model="groq/compound",
                )

    def _build_rwa_query(self, result: AnomalyResult) -> str:
        base = (
            f"DeFi risk finding on Casper blockchain:\n"
            f"Risk Type: {result.risk_type}\n"
            f"Severity: {result.severity}\n"
            f"Confidence: {result.confidence:.0%}\n"
            f"Reasoning: {result.reasoning}\n"
            f"Address: {result.event.address[:30]}\n"
            f"Amount: {result.event.amount_motes / 1_000_000_000:.0f} CSPR\n\n"
        )

        if result.risk_type == "depeg":
            base += "Search for: current CSPR stablecoin depeg events, USDC/USDT peg status on Casper DEXs, recent DeFi protocol depeg news."
        elif result.risk_type in ["whale_dump", "whale_movement"]:
            base += "Search for: current CSPR large holder activity, whale wallet movements, exchange inflow spikes, recent Casper DeFi liquidity events."
        elif result.risk_type == "collateral_drop":
            base += "Search for: current tokenized asset collateral ratios, Casper RWA vault health, recent real-world asset price drops."
        elif result.risk_type == "rug_pull":
            base += "Search for: recent Casper DeFi rug pull warnings, suspicious protocol exits, liquidity removal events in Casper ecosystem."
        else:
            base += "Search for: current Casper DeFi ecosystem health, recent protocol incidents, CSPR market conditions, DeFi risk alerts."

        return base
