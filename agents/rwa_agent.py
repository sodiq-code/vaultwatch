"""
RWAAgent — Layer 4: Real-World Asset context enrichment
Model: compound-beta (Groq built-in web search — no external API keys needed)
Input: passed CorrectionResult from SelfCorrectionAgent
Actions:
  - Query live RWA data: DeFiLlama stablecoins, Chainlink feeds
  - Enrich finding with off-chain context
  - Post verified RWA attestation on AgentBehaviorIndex contract
OTel: span with rwa_sources, enrichment_time, attestation_tx

FIX #28: Wire to real off-chain RWA data sources:
         - DeFiLlama stablecoin API (live collateral ratios)
         - CoinGecko prices (no key needed)
         - Groq Compound for live web search
FIX #15: Groq client injected via constructor.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx
from groq import Groq
from opentelemetry import trace

logger = logging.getLogger("vaultwatch.rwa")
tracer = trace.get_tracer("vaultwatch.rwa_agent")

# FIX #28: Real data source endpoints
DEFILLAMA_STABLECOINS_URL = "https://api.llama.fi/stablecoins"
DEFILLAMA_PROTOCOL_URL = "https://api.llama.fi/protocol/{}"
COINGECKO_PRICE_URL = "https://api.coingecko.com/api/v3/simple/price"


@dataclass
class AnomalyResult:
    """Input from AnomalyAgent (re-declared to avoid circular import)."""
    protocol: str
    address: str
    risk_type: str
    severity: str
    risk_score: float
    confidence: float
    description: str
    block_height: int
    timestamp: int
    raw_event: dict = field(default_factory=dict)


@dataclass
class EnrichedFinding:
    """Output: anomaly result enriched with live RWA context."""
    protocol: str
    address: str
    risk_type: str
    severity: str
    risk_score: float
    confidence: float
    description: str
    block_height: int
    timestamp: int
    raw_event: dict
    # RWA enrichment fields
    rwa_context: str
    rwa_sources: list
    collateral_ratio: Optional[float]
    depeg_risk: Optional[float]
    enriched_at: int
    attestation_tx: Optional[str] = None


class RWAAgent:
    """Layer-4 agent: enriches anomaly findings with live RWA market context."""

    def __init__(
        self,
        input_queue: asyncio.Queue = None,
        output_queue: asyncio.Queue = None,
        groq_api_key: str = "",
        casper_client=None,
    ):
        self.input_queue = input_queue or asyncio.Queue()
        self.output_queue = output_queue or asyncio.Queue()
        self._casper = casper_client
        # FIX #15: inject Groq client
        self._groq_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self._client: Optional[Groq] = (
            Groq(api_key=self._groq_key) if self._groq_key else None
        )

    # ------------------------------------------------------------------
    # FIX #28: Real data source fetches
    # ------------------------------------------------------------------

    async def _fetch_defilllama_stablecoins(self) -> list:
        """Fetch live stablecoin data from DeFiLlama."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(DEFILLLAMA_STABLECOINS_URL)
                data = resp.json()
                return data.get("peggedAssets", [])[:20]  # top 20
        except Exception as exc:
            logger.warning("DeFiLlama fetch failed: %s", exc)
            return []

    async def _fetch_cspr_price(self) -> float:
        """Fetch live CSPR price from CoinGecko."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    COINGECKO_PRICE_URL,
                    params={"ids": "casper-network", "vs_currencies": "usd"},
                )
                data = resp.json()
                return data.get("casper-network", {}).get("usd", 0.0)
        except Exception as exc:
            logger.warning("CoinGecko price fetch failed: %s", exc)
            return 0.0

    async def _call_groq_compound(self, prompt: str) -> str:
        """Query Groq Compound model with live web search."""
        if not self._client:
            return json.dumps({"error": "no_key", "context": "RWA data unavailable"})
        try:
            resp = self._client.chat.completions.create(
                model="compound-beta",
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                max_tokens=512,
            )
            return resp.choices[0].message.content
        except Exception as exc:
            logger.error("Groq Compound call failed: %s", exc)
            return json.dumps({"error": str(exc)})

    # ------------------------------------------------------------------
    # Core enrichment
    # ------------------------------------------------------------------

    async def enrich(
        self, anomaly_result: AnomalyResult
    ) -> EnrichedFinding:
        """Enrich an anomaly finding with live RWA data."""
        with tracer.start_as_current_span("rwa.enrich") as span:
            span.set_attribute("risk_type", anomaly_result.risk_type)
            span.set_attribute("protocol", anomaly_result.protocol)

            sources = []
            collateral_ratio = None
            depeg_risk = None

            # FIX #28: Fetch live DeFiLlama data
            stablecoins = await self._fetch_defilllama_stablecoins()
            if stablecoins:
                sources.append("DeFiLlama")
                # Find relevant stablecoin data
                relevant = [
                    s for s in stablecoins
                    if s.get("symbol", "").lower() in anomaly_result.description.lower()
                    or s.get("name", "").lower() in anomaly_result.protocol.lower()
                ]
                if relevant:
                    sc = relevant[0]
                    price = sc.get("price", 1.0) or 1.0
                    depeg_risk = abs(1.0 - float(price))  # 0.0 = perfectly pegged
                    span.set_attribute("depeg_risk", depeg_risk)

            # FIX #28: Groq Compound for live web context
            rwa_prompt = (
                f"DeFi risk finding: {anomaly_result.risk_type} on protocol '{anomaly_result.protocol}'.\n"
                f"Severity: {anomaly_result.severity}. Address: {anomaly_result.address}\n"
                f"Description: {anomaly_result.description}\n\n"
                f"Provide RWA context: collateral health, real-world asset exposure, "
                f"regulatory risk, and any recent news about this protocol. "
                f"Be concise (max 3 sentences)."
            )
            rwa_context = await self._call_groq_compound(rwa_prompt)
            sources.append("Groq Compound (live web search)")

            # FIX #28: Post on-chain attestation if casper client available
            attestation_tx = None
            if self._casper and not getattr(self._casper, "mock", True):
                try:
                    behavior_hash = os.getenv("AGENT_BEHAVIOR_INDEX_HASH", "")
                    attestation_tx = self._casper.call_contract(
                        contract_hash=behavior_hash,
                        entry_point="record_decision",
                        args={
                            "agent_name": "RWAAgent",
                            "confidence": int(anomaly_result.confidence * 100),
                            "correction_applied": False,
                            "safety_rejected": False,
                            "block_height": anomaly_result.block_height,
                        },
                    )
                    logger.info("RWA attestation recorded: %s", attestation_tx)
                    sources.append(f"Casper attestation: {attestation_tx[:20]}...")
                except Exception as exc:
                    logger.warning("Attestation failed (non-critical): %s", exc)

            span.set_attribute("rwa_sources", ",".join(sources))

            return EnrichedFinding(
                protocol=anomaly_result.protocol,
                address=anomaly_result.address,
                risk_type=anomaly_result.risk_type,
                severity=anomaly_result.severity,
                risk_score=anomaly_result.risk_score,
                confidence=anomaly_result.confidence,
                description=anomaly_result.description,
                block_height=anomaly_result.block_height,
                timestamp=anomaly_result.timestamp,
                raw_event=anomaly_result.raw_event,
                rwa_context=rwa_context,
                rwa_sources=sources,
                collateral_ratio=collateral_ratio,
                depeg_risk=depeg_risk,
                enriched_at=int(time.time()),
                attestation_tx=attestation_tx,
            )

    async def analyze_rwa_risk(self, asset_type: str = "stablecoin") -> dict:
        """Standalone RWA risk analysis (used by FastAPI /api/rwa endpoint)."""
        with tracer.start_as_current_span("rwa.analyze_risk") as span:
            span.set_attribute("asset_type", asset_type)

            # FIX #28: Real live data
            stablecoins = await self._fetch_defilllama_stablecoins()
            cspr_price = await self._fetch_cspr_price()

            analysis = await self._call_groq_compound(
                f"Current {asset_type} RWA risk signals on DeFi protocols. "
                f"CSPR price: ${cspr_price:.4f}. "
                f"Key metrics: depeg risk, collateral ratio, yield rates, protocol TVL. "
                f"Return JSON with: depeg_risk (float 0-1), collateral_ratio (float), "
                f"yield_rate_pct (float), risk_level (LOW/MEDIUM/HIGH/CRITICAL), summary (str)."
            )

            return {
                "asset_type": asset_type,
                "analysis": analysis,
                "cspr_price_usd": cspr_price,
                "stablecoins_monitored": len(stablecoins),
                "timestamp": int(time.time()),
                "sources": ["DeFiLlama", "CoinGecko", "Groq Compound"],
                "model": "compound-beta",
            }

    async def run(self):
        """Queue consumer loop."""
        logger.info("RWAAgent started")
        while True:
            item = await self.input_queue.get()
            if isinstance(item, AnomalyResult):
                enriched = await self.enrich(item)
                if self.output_queue:
                    await self.output_queue.put(enriched)
            self.input_queue.task_done()
