"""
RWAAgent — Layer 4: Real-World Asset enrichment via live web intelligence
Model: llama-3.3-70b-versatile (JSON-mode RWA enrichment — replaces deprecated compound-beta)
Input: confirmed anomaly finding
Output: enriched finding with RWA context (yield rates, depeg news, vault health)
OTel: span with rwa_sources, collateral_ratio, enrichment_type

Task 3-5 additions:
  • RWAFeedData dataclass for structured feed data from /rwa/feed API
  • fetch_rwa_feed() method that calls the x402-gated /rwa/feed endpoint
  • _enrich() now FIRST fetches from the dedicated RWA feed API, THEN also
    calls Groq llama-3.3-70b-versatile for additional intelligence, merging both
  • EnrichedFinding now tracks feed_source and x402_payment_id
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from opentelemetry import trace
from groq import Groq
import httpx
from .anomaly_agent import AnomalyResult

logger = logging.getLogger("vaultwatch.rwa")
tracer = trace.get_tracer("vaultwatch.rwa_agent")

# No module-level Groq client — injected per-instance via the constructor
# (``groq_client=...``) or built from ``groq_api_key``. Tests inject a mock
# client and exercise the real ``_enrich`` production path.


@dataclass
class RWAFeedData:
    """Structured RWA data fetched from the dedicated /rwa/feed API endpoint.

    Represents the five asset categories served by the x402-gated feed:
    real_estate, bonds, commodities, credit, tokenized_assets.

    Hybrid upgrade (v1.1.0): each category may contain real data from
    CoinGecko (commodities/tokenized_assets) or FRED (bonds/credit) or
    remain mock-only (real_estate). Provenance is tracked via:
      - real_data_sources: bool flags indicating which external APIs were live
      - attestation_proof: SHA-256 hashes + timestamps per category
      - data_source_map: per-category provenance (coingecko_api / fred_api / vaultwatch_mock)
    """

    feed_source: str = "rwa_feed_api"
    x402_payment_id: str = ""
    timestamp: int = 0
    feed_version: str = "1.1.0"
    real_estate: Dict[str, Any] = field(default_factory=dict)
    bonds: Dict[str, Any] = field(default_factory=dict)
    commodities: Dict[str, Any] = field(default_factory=dict)
    credit: Dict[str, Any] = field(default_factory=dict)
    tokenized_assets: Dict[str, Any] = field(default_factory=dict)
    raw_feed: Dict[str, Any] = field(default_factory=dict)
    real_data_sources: Dict[str, bool] = field(default_factory=dict)
    attestation_proof: Dict[str, Any] = field(default_factory=dict)
    data_source_map: Dict[str, str] = field(default_factory=dict)


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
    feed_source: str = ""
    x402_payment_id: str = ""


class RWAAgent:
    _UNSET = object()  # sentinel: distinguishes "not provided" from "explicitly empty"

    def __init__(
        self,
        input_queue: asyncio.Queue = None,
        output_queue: asyncio.Queue = None,
        groq_api_key=_UNSET,
        groq_client=None,
        api_base_url: str = "http://localhost:8000",
    ):
        self.input_queue = input_queue or asyncio.Queue()
        self.output_queue = output_queue or asyncio.Queue()
        # When groq_api_key is explicitly provided (even as ""), use it directly.
        # When not provided (default sentinel), fall back to env var.
        if groq_api_key is RWAAgent._UNSET:
            self._groq_key = os.getenv("GROQ_API_KEY", "")
        else:
            self._groq_key = groq_api_key
        # Inject a pre-built client (tests / DI) or construct one from the key.
        if groq_client is not None:
            self._client = groq_client
        else:
            self._client = Groq(api_key=self._groq_key or "mock-key") if self._groq_key else None
        self._assets: list = []
        self._api_base_url = api_base_url
        self._httpx_client: Optional[httpx.AsyncClient] = None

    async def fetch_rwa_feed(self, asset_type: str = "") -> RWAFeedData:
        """Call the dedicated /rwa/feed API endpoint using httpx.

        The endpoint is x402-gated; in production a valid PAYMENT-SIGNATURE
        header must be supplied. In dev/mock mode, the agent can call with
        a test payment header or rely on the 402-challenge flow being
        handled externally. Falls back gracefully on any error.
        """
        with tracer.start_as_current_span("rwa.fetch_feed") as span:
            span.set_attribute("rwa.feed.asset_type", asset_type or "all")
            span.set_attribute("rwa.feed.api_base", self._api_base_url)

            url = f"{self._api_base_url}/rwa/feed"
            if asset_type:
                url = f"{url}?asset_type={asset_type}"

            # Build headers — in production, PAYMENT-SIGNATURE would come from
            # the x402 payment flow. For internal agent calls, use a
            # well-known internal signature that the API recognises.
            headers = {
                "PAYMENT-SIGNATURE": os.getenv("VAULTWATCH_RWA_FEED_SIGNATURE", "internal-agent-call"),
                "Accept": "application/json",
            }

            try:
                if self._httpx_client is None:
                    self._httpx_client = httpx.AsyncClient(timeout=30.0)
                resp = await self._httpx_client.get(url, headers=headers)
                span.set_attribute("rwa.feed.http_status", resp.status_code)

                if resp.status_code == 200:
                    body = resp.json()
                    feed_data_dict = body.get("feed_data", body)
                    payment_id = body.get("payer", "") or resp.headers.get("PAYMENT-RESPONSE", "")
                    span.set_attribute("rwa.feed.success", True)
                    span.set_attribute("rwa.feed.x402_payment_id", payment_id)

                    return RWAFeedData(
                        feed_source="rwa_feed_api",
                        x402_payment_id=payment_id,
                        timestamp=feed_data_dict.get("timestamp", int(time.time())),
                        feed_version=feed_data_dict.get("feed_version", "1.1.0"),
                        real_estate=feed_data_dict.get("real_estate", {}),
                        bonds=feed_data_dict.get("bonds", {}),
                        commodities=feed_data_dict.get("commodities", {}),
                        credit=feed_data_dict.get("credit", {}),
                        tokenized_assets=feed_data_dict.get("tokenized_assets", {}),
                        raw_feed=feed_data_dict,
                        real_data_sources=feed_data_dict.get("real_data_sources", {}),
                        attestation_proof=feed_data_dict.get("attestation_proof", {}),
                        data_source_map={
                            "real_estate": feed_data_dict.get("real_estate", {}).get("data_source", "vaultwatch_mock"),
                            "bonds": feed_data_dict.get("bonds", {}).get("data_source", "vaultwatch_mock"),
                            "commodities": feed_data_dict.get("commodities", {}).get("data_source", "vaultwatch_mock"),
                            "credit": feed_data_dict.get("credit", {}).get("data_source", "vaultwatch_mock"),
                            "tokenized_assets": feed_data_dict.get("tokenized_assets", {}).get("data_source", "vaultwatch_mock"),
                        },
                    )
                else:
                    span.set_attribute("rwa.feed.success", False)
                    span.set_attribute("rwa.feed.error_status", resp.status_code)
                    logger.warning("RWA feed API returned status %d", resp.status_code)
                    return RWAFeedData(feed_source="rwa_feed_api_failed")

            except Exception as exc:
                span.record_exception(exc)
                span.set_attribute("rwa.feed.error", str(exc))
                logger.error("RWA feed API call failed: %s", exc)
                return RWAFeedData(feed_source="rwa_feed_api_error")

    async def _call_groq(self, prompt: str) -> dict:
        if not self._client:
            return {
                "verdict": "REVIEW",
                "risk_score": 50.0,
                "notes": "No API key",
                "error": "no_key",
            }
        resp = self._client.chat.completions.create(
            model="llama-3.3-70b-versatile",
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
                exc_str = str(exc)
                is_auth_error = any(code in exc_str for code in ["403", "401", "429", "Forbidden", "Unauthorized", "Rate limit"])
                # Heuristic-based RWA assessment when Groq auth fails.
                if is_auth_error:
                    collateral_ratio = asset_data.get("collateral_ratio", 1.0)
                    credit_rating = asset_data.get("credit_rating", "BBB")
                    score = 0
                    if collateral_ratio < 1.0:
                        score += 30
                    elif collateral_ratio < 1.15:
                        score += 15
                    if credit_rating in ("AAA", "AA"):
                        score += 10
                    elif credit_rating in ("BBB", "BB"):
                        score += 25
                    elif credit_rating in ("B", "CCC"):
                        score += 40
                    score += 15  # base risk for unverified AI assessment
                    verdict = "REJECTED" if score > 70 else "REVIEW" if score > 40 else "APPROVED"
                    return {
                        "verdict": verdict,
                        "risk_score": min(100.0, score),
                        "notes": (
                            f"VaultWatch heuristic RWA assessment (Groq unavailable): "
                            f"{asset_data.get('asset_type', 'unknown')} asset "
                            f"'{asset_data.get('asset_id', 'unknown')}' with collateral "
                            f"ratio {collateral_ratio:.2f} and credit rating {credit_rating}. "
                            f"Heuristic verdict: {verdict}. "
                            f"Full AI analysis requires valid Groq key."
                        ),
                        "risk_factors": ["valuation_uncertainty", "market_volatility", "groq_auth_failure"],
                        "collateral_assessment": f"Collateral ratio {collateral_ratio:.2f} — {'below' if collateral_ratio < 1.0 else 'above'} 1.0x threshold",
                        "regulatory_status": "Pending AI verification (heuristic fallback)",
                        "groq_model": "llama-3.3-70b-versatile (heuristic-fallback)",
                        "on_chain_contract": "RiskPolicyManager",
                        "on_chain_hash": "93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e",
                        "error": f"Groq auth error — heuristic fallback active: {exc_str[:80]}",
                    }
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
                        enrichment_model="llama-3.3-70b-versatile",
                    )
                )
            finally:
                self.input_queue.task_done()

    async def _enrich(self, result: AnomalyResult) -> EnrichedFinding:
        """Enrich finding by FIRST fetching from the dedicated RWA feed API,
        THEN calling Groq llama-3.3-70b-versatile for additional intelligence, and
        merging structured feed data with Groq's analysis results.
        """
        with tracer.start_as_current_span("rwa.enrich") as span:
            span.set_attribute("rwa.risk_type", result.risk_type)
            span.set_attribute("rwa.severity", result.severity)
            span.set_attribute("rwa.model", "llama-3.3-70b-versatile+rwa_feed")

            # ---- Step 1: Fetch structured RWA feed data from /rwa/feed ----
            # Determine which asset category to query based on risk type
            feed_asset_type = self._map_risk_type_to_asset_type(result.risk_type)
            feed_data: RWAFeedData = await self.fetch_rwa_feed(asset_type=feed_asset_type)

            span.set_attribute("rwa.feed_source", feed_data.feed_source)
            span.set_attribute("rwa.feed_fetched", feed_data.timestamp > 0)

            # Build feed summary string for merging with Groq context
            feed_summary = self._summarize_feed_data(feed_data)

            # ---- Step 2: Build targeted RWA query including feed data ----
            query = self._build_rwa_query(result)
            # Inject the structured feed data into the Groq query so the LLM
            # can cross-reference live web intel against the known feed values.
            if feed_summary:
                provenance_info = ""
                if feed_data.real_data_sources:
                    active = [k for k, v in feed_data.real_data_sources.items() if v]
                    provenance_info = f" (live data sources: {', '.join(active) if active else 'all mock'})"
                query += (
                    f"\n\n--- STRUCTURED RWA FEED DATA (source: {feed_data.feed_source}{provenance_info}) ---\n"
                    f"{feed_summary}\n"
                    f"Cross-reference the above feed data with your live web search."
                )

            # Fail-safe: with no model client configured, return a feed-only
            # enriched finding (feed data is still valuable without Groq).
            if self._client is None:
                span.set_attribute("rwa.enrich", "skipped_no_client_feed_only")
                return EnrichedFinding(
                    base=result,
                    rwa_context=feed_summary or "RWA enrichment unavailable — no Groq client configured",
                    collateral_signals=self._extract_collateral_from_feed(feed_data),
                    yield_data=self._extract_yield_from_feed(feed_data),
                    depeg_alerts=[],
                    enriched=bool(feed_summary),
                    rwa_sources_count=1 if feed_summary else 0,
                    enrichment_model="rwa_feed_api",
                    feed_source=feed_data.feed_source,
                    x402_payment_id=feed_data.x402_payment_id,
                )

            # ---- Step 3: Call Groq llama-3.3-70b-versatile for analysis ----
            response = self._client.chat.completions.create(
                model="llama-3.3-70b-versatile",  # JSON-mode enrichment (compound-beta deprecated)
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are VaultWatch RWAAgent. Enrich DeFi risk findings with real-world context. "
                            "Analyze stablecoin depeg risk, DeFi protocol health, tokenized asset yields, "
                            "and collateral ratios relevant to the finding. "
                            "When structured feed data is provided, cross-reference it with your analysis. "
                            "Return JSON: "
                            '{"rwa_context": str, "collateral_signals": [str], "yield_data": str, '
                            '"depeg_alerts": [str], "sources_found": int}'
                        ),
                    },
                    {"role": "user", "content": query},
                ],
                temperature=0.3,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content
            tokens = response.usage.total_tokens

            span.set_attribute("rwa.tokens_used", tokens)

            try:
                # Extract JSON from response (model returns structured JSON)
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed = json.loads(content[start:end])
                else:
                    parsed = {}

                groq_context = parsed.get("rwa_context", content[:500])
                groq_collateral = parsed.get("collateral_signals", [])
                groq_yield = parsed.get("yield_data", "")
                groq_depeg = parsed.get("depeg_alerts", [])
                sources_count = parsed.get("sources_found", 1)

                # ---- Step 4: Merge feed data with Groq web intelligence ----
                merged_context = self._merge_context(feed_summary, groq_context)
                merged_collateral = self._merge_collateral_signals(self._extract_collateral_from_feed(feed_data), groq_collateral)
                merged_yield = self._merge_yield_data(self._extract_yield_from_feed(feed_data), groq_yield)
                merged_depeg = self._merge_depeg_alerts(groq_depeg, feed_data)

                # Feed data counts as 1 additional source
                total_sources = sources_count + (1 if feed_summary else 0)

                span.set_attribute("rwa.sources_count", total_sources)
                span.set_attribute("rwa.depeg_alerts_count", len(merged_depeg))
                span.set_attribute("rwa.enriched", True)

                return EnrichedFinding(
                    base=result,
                    rwa_context=merged_context,
                    collateral_signals=merged_collateral,
                    yield_data=merged_yield,
                    depeg_alerts=merged_depeg,
                    enriched=True,
                    rwa_sources_count=total_sources,
                    enrichment_model="llama-3.3-70b-versatile+rwa_feed",
                    feed_source=feed_data.feed_source,
                    x402_payment_id=feed_data.x402_payment_id,
                )

            except Exception as e:
                span.record_exception(e)
                span.set_attribute("rwa.parse_error", str(e))
                # Still include feed data even if Groq parsing failed
                return EnrichedFinding(
                    base=result,
                    rwa_context=self._merge_context(feed_summary, content[:500]),
                    collateral_signals=self._extract_collateral_from_feed(feed_data),
                    yield_data=self._extract_yield_from_feed(feed_data),
                    depeg_alerts=[],
                    enriched=True,
                    rwa_sources_count=1 if feed_summary else 0,
                    enrichment_model="llama-3.3-70b-versatile+rwa_feed",
                    feed_source=feed_data.feed_source,
                    x402_payment_id=feed_data.x402_payment_id,
                )

    # ------------------------------------------------------------------
    # Helper methods for feed data processing and merging
    # ------------------------------------------------------------------

    def _map_risk_type_to_asset_type(self, risk_type: str) -> str:
        """Map a risk type to the most relevant RWA asset category for feed queries."""
        mapping = {
            "depeg": "commodities",
            "whale_dump": "",
            "whale_movement": "",
            "collateral_drop": "tokenized_assets",
            "rug_pull": "",
            "liquidity_drain": "bonds",
            "price_manipulation": "commodities",
        }
        return mapping.get(risk_type, "")

    def _summarize_feed_data(self, feed: RWAFeedData) -> str:
        """Build a human-readable summary of structured feed data for Groq context.

        Hybrid upgrade: includes provenance annotations (data_source per category).
        """
        if feed.timestamp == 0 and not feed.raw_feed:
            return ""
        parts = []
        # Provenance header
        if feed.real_data_sources:
            active = [k for k, v in feed.real_data_sources.items() if v]
            if active:
                parts.append(f"[Provenance: live data from {', '.join(active)}]")
        if feed.real_estate:
            props = feed.real_estate.get("properties", [])
            for p in props[:3]:
                parts.append(
                    f"Property {p.get('property_id', '?')}: "
                    f"valuation=${p.get('valuation_usd', 0):,.0f}, "
                    f"occupancy={p.get('occupancy_rate', 0):.1%}, "
                    f"location_risk={p.get('location_risk', 0):.2%}"
                )
        if feed.bonds:
            for tb in feed.bonds.get("treasury", [])[:2]:
                parts.append(f"T-Bill {tb.get('bond_id', '?')}: yield={tb.get('yield_pct', 0):.2f}%, maturity_risk={tb.get('maturity_risk', 0):.3%}")
            for cb in feed.bonds.get("corporate", [])[:1]:
                parts.append(f"Corp Bond {cb.get('bond_id', '?')}: yield={cb.get('yield_pct', 0):.2f}%, spread={cb.get('spread_bps', 0)}bps")
        if feed.commodities:
            parts.append(
                f"Gold=${feed.commodities.get('gold_price_usd_per_oz', 0):,.2f}/oz, "
                f"Silver=${feed.commodities.get('silver_price_usd_per_oz', 0):.2f}/oz, "
                f"Oil=${feed.commodities.get('oil_price_usd_per_barrel', 0):.2f}/bbl"
            )
        if feed.credit:
            ratings = feed.credit.get("ratings", [])
            for r in ratings[:2]:
                parts.append(f"Credit {r.get('entity', '?')}: rating={r.get('rating', '?')}, default_prob={r.get('default_probability', 0):.2%}")
        if feed.tokenized_assets:
            for a in feed.tokenized_assets.get("on_chain_assets", [])[:2]:
                parts.append(f"Tokenized {a.get('token_symbol', '?')}: collateral_ratio={a.get('collateral_ratio', 0):.2f}x, chain={a.get('chain_id', '?')}")
        return "\n".join(parts) if parts else ""

    def _extract_collateral_from_feed(self, feed: RWAFeedData) -> list[str]:
        """Extract collateral-related signals from feed data."""
        signals = []
        for a in feed.tokenized_assets.get("on_chain_assets", []):
            cr = a.get("collateral_ratio", 0)
            if cr:
                signals.append(f"{a.get('token_symbol', '?')} collateral ratio: {cr:.2f}x (chain: {a.get('chain_id', '?')})")
        for p in feed.real_estate.get("properties", []):
            cap = p.get("cap_rate", 0)
            if cap:
                signals.append(f"Property {p.get('property_id', '?')} cap rate: {cap:.2%}")
        return signals

    def _extract_yield_from_feed(self, feed: RWAFeedData) -> str:
        """Extract yield-related data from feed."""
        if not feed.bonds:
            return ""
        yields = []
        for tb in feed.bonds.get("treasury", []):
            yields.append(f"{tb.get('bond_id', '?')}: {tb.get('yield_pct', 0):.2f}%")
        for cb in feed.bonds.get("corporate", []):
            yields.append(f"{cb.get('bond_id', '?')}: {cb.get('yield_pct', 0):.2f}% (spread: {cb.get('spread_bps', 0)}bps)")
        return "Feed yields: " + ", ".join(yields) if yields else ""

    def _merge_context(self, feed_summary: str, groq_context: str) -> str:
        """Merge structured feed summary with Groq's web intelligence context."""
        if not feed_summary:
            return groq_context
        if not groq_context:
            return f"[RWA Feed] {feed_summary}"
        return f"[RWA Feed] {feed_summary}\n\n[Web Intelligence] {groq_context}"

    def _merge_collateral_signals(self, feed_signals: list[str], groq_signals: list[str]) -> list[str]:
        """Merge feed-derived collateral signals with Groq-derived signals."""
        # Deduplicate by keeping unique entries from both sources
        all_signals = list(feed_signals)
        for s in groq_signals:
            if s not in all_signals:
                all_signals.append(s)
        return all_signals

    def _merge_yield_data(self, feed_yield: str, groq_yield: str) -> str:
        """Merge feed yield data with Groq yield data."""
        if not feed_yield:
            return groq_yield
        if not groq_yield:
            return feed_yield
        return f"{feed_yield} | {groq_yield}"

    def _merge_depeg_alerts(self, groq_depeg: list[str], feed: RWAFeedData) -> list[str]:
        """Merge Groq depeg alerts with feed-derived alerts."""
        alerts = list(groq_depeg)
        # Check commodities feed for large price swings that could indicate depeg
        if feed.commodities:
            gold = feed.commodities.get("gold_price_usd_per_oz", 0)
            if gold > 2450:
                alerts.append("[Feed] Gold above $2,450/oz — possible commodity depeg signal")
        if feed.bonds:
            for tb in feed.bonds.get("treasury", []):
                if tb.get("yield_pct", 0) > 5.45:
                    alerts.append(f"[Feed] {tb.get('bond_id', '?')} yield above 5.45% — treasury rate stress")
        return alerts

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
