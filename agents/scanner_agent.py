"""
ScannerAgent — Layer 1 of VaultWatch pipeline
Model: llama-3.1-8b-instant (560 t/s — fastest Groq model)
Data sources: CSPR.cloud REST API + Casper Sidecar SSE
Output: structured event stream → AnomalyAgent queue
OTel: span per scan cycle with event_count, latency, source
"""

import asyncio
import json
import os
import time
import logging
from dataclasses import dataclass
import httpx
from opentelemetry import trace
from groq import Groq

logger = logging.getLogger("vaultwatch.scanner")
tracer = trace.get_tracer("vaultwatch.scanner_agent")

CSPR_CLOUD_URL = os.getenv("CSPR_CLOUD_API_URL", "https://api.testnet.cspr.cloud")
CSPR_CLOUD_KEY = os.getenv("CSPR_CLOUD_API_KEY", "")
SCAN_INTERVAL = int(os.getenv("SCAN_INTERVAL_SECONDS", "60"))



@dataclass
class RawEvent:
    event_type: str  # token_transfer | staking | whale_movement | deploy | contract_call
    address: str
    amount_motes: int
    block_height: int
    timestamp: int
    raw_data: dict
    source: str  # cspr_cloud | sidecar_sse


class ScannerAgent:
    def __init__(self, event_queue: asyncio.Queue = None, groq_api_key: str = ""):
        self.queue = event_queue or asyncio.Queue()
        self.last_block = 0
        self.scan_count = 0
        self._groq_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self._client = Groq(api_key=self._groq_key or "mock-key") if self._groq_key else None

    async def _call_groq(self, prompt: str) -> dict:
        """Call Groq for protocol scan analysis."""
        if not self._client:
            return {
                "risk_level": "UNKNOWN",
                "vulnerabilities": [],
                "summary": "No API key",
                "error": "no_key",
            }
        resp = self._client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a DeFi security analyst. Respond only with valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        import json

        return json.loads(resp.choices[0].message.content)

    async def scan(self, protocol: str, contract_address: str = None, chain: str = "casper") -> dict:
        """Scan a protocol for vulnerabilities and return risk assessment."""
        with tracer.start_as_current_span("scanner.scan") as span:
            span.set_attribute("protocol", protocol)
            span.set_attribute("chain", chain)
            prompt = (
                f"Analyze DeFi protocol '{protocol}' on {chain} network"
                + (f" at contract {contract_address}" if contract_address else "")
                + ". Return JSON: {risk_level: LOW|MEDIUM|HIGH|CRITICAL, vulnerabilities: [], summary: string}"
            )
            try:
                result = await self._call_groq(prompt)
                result.setdefault("risk_level", "UNKNOWN")
                result.setdefault("vulnerabilities", [])
                result.setdefault("summary", "")
                return result
            except Exception as exc:
                logger.error("scan error: %s", exc)
                return {
                    "risk_level": "UNKNOWN",
                    "vulnerabilities": [],
                    "summary": "",
                    "error": str(exc),
                }

    async def run(self):
        """Main scan loop — runs forever, pushes events to queue"""
        logger.info("ScannerAgent started")
        while True:
            with tracer.start_as_current_span("scanner.scan_cycle") as span:
                try:
                    events = await self._fetch_events()
                    span.set_attribute("scan.event_count", len(events))
                    span.set_attribute("scan.block_height", self.last_block)
                    span.set_attribute("scan.source", "cspr_cloud")
                    span.set_attribute("scan.cycle_number", self.scan_count)

                    for event in events:
                        await self.queue.put(event)

                    self.scan_count += 1
                    logger.info(f"Scan #{self.scan_count}: {len(events)} events from block {self.last_block}")

                except Exception as e:
                    span.record_exception(e)
                    span.set_attribute("scan.error", str(e))
                    logger.error(f"ScannerAgent error: {e}")

            await asyncio.sleep(SCAN_INTERVAL)

    async def _fetch_events(self) -> list[RawEvent]:
        """Fetch latest transfers and staking events from CSPR.cloud"""
        events = []

        headers = {}
        if CSPR_CLOUD_KEY:
            headers["Authorization"] = f"Bearer {CSPR_CLOUD_KEY}"

        async with httpx.AsyncClient(timeout=30) as client:
            # Fetch recent transfers
            try:
                resp = await client.get(
                    f"{CSPR_CLOUD_URL}/transfers",
                    params={
                        "fields": "deploy_hash,from_purse,to_purse,amount,timestamp,block_height",
                        "page": 1,
                        "page_size": 100,
                    },
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for transfer in data.get("data", []):
                        amount = int(transfer.get("amount", 0))
                        # Flag whale movements: > 100,000 CSPR (100B motes)
                        event_type = "whale_movement" if amount > 100_000_000_000_000 else "token_transfer"
                        events.append(
                            RawEvent(
                                event_type=event_type,
                                address=transfer.get("from_purse", ""),
                                amount_motes=amount,
                                block_height=int(transfer.get("block_height", 0)),
                                timestamp=int(time.time()),
                                raw_data=transfer,
                                source="cspr_cloud",
                            )
                        )
            except Exception as e:
                logger.warning(f"CSPR.cloud transfer fetch failed: {e}")

            # Fetch recent deploys (contract interactions)
            try:
                resp = await client.get(
                    f"{CSPR_CLOUD_URL}/deploys",
                    params={
                        "fields": "deploy_hash,caller_public_key,block_height,timestamp",
                        "page": 1,
                        "page_size": 50,
                    },
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for deploy in data.get("data", []):
                        events.append(
                            RawEvent(
                                event_type="contract_call",
                                address=deploy.get("caller_public_key", ""),
                                amount_motes=0,
                                block_height=int(deploy.get("block_height", 0)),
                                timestamp=int(time.time()),
                                raw_data=deploy,
                                source="cspr_cloud",
                            )
                        )
            except Exception as e:
                logger.warning(f"CSPR.cloud deploy fetch failed: {e}")

        # Use LLM to pre-classify and filter noise (fast model)
        if events:
            events = await self._llm_filter(events)

        return events

    async def _llm_filter(self, events: list[RawEvent]) -> list[RawEvent]:
        """Use llama-3.1-8b-instant to filter noise — keep only suspicious events"""
        with tracer.start_as_current_span("scanner.llm_filter") as span:
            span.set_attribute("scanner.raw_event_count", len(events))
            span.set_attribute("scanner.model", "llama-3.1-8b-instant")

            # Summarize events for LLM
            summary = [
                {
                    "type": e.event_type,
                    "address": e.address[:20] + "..." if len(e.address) > 20 else e.address,
                    "amount_cspr": e.amount_motes / 1_000_000_000,
                    "block": e.block_height,
                }
                for e in events[:20]  # cap at 20 for token efficiency
            ]

            if self._client is None:
                logger.warning("No Groq client available, skipping LLM filter and returning all events")
                return events

            try:
                response = self._client.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a Casper blockchain event filter for VaultWatch DeFi risk system. "
                                "Given a list of events, return a JSON array of indices (0-based) that are "
                                "potentially suspicious or worth risk analysis. Focus on: large transfers (>10k CSPR), "
                                "whale movements, rapid sequential deploys from same address, unusual staking changes. "
                                "Return only a JSON array of integers, e.g. [0, 2, 5]. Return [] if nothing suspicious."
                            ),
                        },
                        {"role": "user", "content": json.dumps(summary)},
                    ],
                    temperature=0.1,
                    max_tokens=256,
                )

                content = response.choices[0].message.content.strip()
                span.set_attribute("scanner.tokens_used", response.usage.total_tokens)

                # Parse indices
                start = content.find("[")
                end = content.rfind("]") + 1
                if start >= 0 and end > start:
                    indices = json.loads(content[start:end])
                    filtered = [events[i] for i in indices if i < len(events)]
                    span.set_attribute("scanner.filtered_event_count", len(filtered))
                    return filtered if filtered else events[:5]  # fallback: first 5

            except Exception as e:
                span.record_exception(e)
                logger.warning(f"LLM filter failed, passing all events: {e}")

            return events

    async def inject_mock_event(self, event_type: str = "whale_movement") -> RawEvent:
        """Inject a mock event for demo purposes — used by demo scripts"""
        mock = RawEvent(
            event_type=event_type,
            address="casper1demo_whale_address_abc123",
            amount_motes=2_400_000_000_000_000,  # 2.4M CSPR
            block_height=1_500_000,
            timestamp=int(time.time()),
            raw_data={"demo": True, "injected": True},
            source="demo_injection",
        )
        await self.queue.put(mock)
        logger.info(f"Injected mock event: {event_type}")
        return mock
