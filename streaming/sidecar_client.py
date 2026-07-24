"""
Casper Sidecar SSE Client — Real-time event streaming
Connects to Casper Sidecar SSE endpoint.
Reconnects automatically on disconnect.
Pushes events directly into ScannerAgent queue.
OTel: span per event received, reconnect count
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Callable, Optional
import httpx
from opentelemetry import trace

logger = logging.getLogger("vaultwatch.sidecar")
tracer = trace.get_tracer("vaultwatch.sidecar_client")

SIDECAR_SSE_URL = os.getenv("CASPER_SIDECAR_URL", "http://127.0.0.1:18888/events/main")
RECONNECT_DELAY = 5  # seconds between reconnects


@dataclass
class SidecarEvent:
    event_type: str  # BlockAdded | TransactionProcessed | Fault | Step
    block_hash: Optional[str]
    block_height: Optional[int]
    timestamp: int
    raw_data: dict
    source: str = "casper_sidecar_sse"


class SidecarClient:
    def __init__(
        self,
        event_handler: Callable = None,
        queue: Optional[asyncio.Queue] = None,
        url: str = "",
    ):
        """
        event_handler: async callable that receives SidecarEvent
        queue: optional asyncio.Queue — if provided, events are pushed here
        url: SSE endpoint URL (overrides SIDECAR_SSE_URL env var)
        """
        self.event_handler = event_handler
        self.queue = queue
        self.url = url or SIDECAR_SSE_URL
        self.reconnect_count = 0
        self.event_count = 0
        self.running = False

    async def _raw_stream(self):
        """Yield raw SSE byte lines from the endpoint."""
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", self.url) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        yield line[5:].strip().encode()

    async def stream(self):
        """Yield decoded event dicts. Auto-reconnects on error."""
        import json as _json

        async for raw in self._raw_stream():
            try:
                event = _json.loads(raw)
                yield event
            except Exception:
                continue

    async def run(self):
        """Start streaming loop — reconnects automatically on disconnect"""
        self.running = True
        logger.info(f"SidecarClient connecting to {SIDECAR_SSE_URL}")

        while self.running:
            with tracer.start_as_current_span("sidecar.stream_session") as span:
                span.set_attribute("sidecar.url", SIDECAR_SSE_URL)
                span.set_attribute("sidecar.reconnect_count", self.reconnect_count)

                try:
                    async with httpx.AsyncClient(timeout=None) as client:
                        async with client.stream("GET", SIDECAR_SSE_URL) as response:
                            logger.info("SidecarClient connected — streaming events")
                            span.set_attribute("sidecar.connected", True)

                            async for line in response.aiter_lines():
                                if not self.running:
                                    break
                                if line.startswith("data:"):
                                    await self._handle_line(line[5:].strip())
                                elif line.startswith("event:"):
                                    pass  # event type hint — handled in data parsing

                except httpx.ConnectError:
                    logger.warning(f"SidecarClient: connection refused at {SIDECAR_SSE_URL}. Is Sidecar running?")
                    span.set_attribute("sidecar.connect_error", True)
                except httpx.RemoteProtocolError as e:
                    logger.warning(f"SidecarClient: protocol error: {e}")
                    span.record_exception(e)
                except Exception as e:
                    logger.error(f"SidecarClient unexpected error: {e}")
                    span.record_exception(e)

                if self.running:
                    self.reconnect_count += 1
                    logger.info(f"SidecarClient reconnecting in {RECONNECT_DELAY}s (attempt #{self.reconnect_count})")
                    await asyncio.sleep(RECONNECT_DELAY)

    async def _handle_line(self, data_str: str):
        """Parse SSE data line and dispatch event"""
        if not data_str or data_str == ":":
            return

        with tracer.start_as_current_span("sidecar.handle_event") as span:
            try:
                raw = json.loads(data_str)
                event_type = list(raw.keys())[0] if raw else "Unknown"

                event = SidecarEvent(
                    event_type=event_type,
                    block_hash=self._extract_block_hash(raw),
                    block_height=self._extract_block_height(raw),
                    timestamp=int(time.time()),
                    raw_data=raw,
                )

                self.event_count += 1
                span.set_attribute("sidecar.event_type", event_type)
                span.set_attribute("sidecar.total_events", self.event_count)

                if self.queue:
                    # Convert to scanner-compatible event if it's a transaction
                    from agents.scanner_agent import RawEvent

                    if event_type in ["TransactionProcessed", "DeployProcessed"]:
                        raw_evt = RawEvent(
                            event_type="contract_call",
                            address=self._extract_sender(raw),
                            amount_motes=self._extract_amount(raw),
                            block_height=event.block_height or 0,
                            timestamp=event.timestamp,
                            raw_data=raw,
                            source="casper_sidecar_sse",
                        )
                        await self.queue.put(raw_evt)

                await self.event_handler(event)

            except json.JSONDecodeError:
                pass  # Skip non-JSON lines (heartbeats)
            except Exception as e:
                span.record_exception(e)
                logger.warning(f"SidecarClient event parse error: {e}")

    def _extract_block_hash(self, raw: dict) -> Optional[str]:
        try:
            return raw.get("BlockAdded", {}).get("block_hash")
        except Exception:
            return None

    def _extract_block_height(self, raw: dict) -> Optional[int]:
        try:
            block_data = raw.get("BlockAdded", {})
            return block_data.get("block", {}).get("header", {}).get("height")
        except Exception:
            return None

    def _extract_sender(self, raw: dict) -> str:
        try:
            deploy = raw.get("DeployProcessed", {})
            return deploy.get("account", "unknown")
        except Exception:
            return "unknown"

    def _extract_amount(self, raw: dict) -> int:
        try:
            payment = raw.get("DeployProcessed", {}).get("execution_result", {})
            return int(payment.get("Success", {}).get("cost", 0))
        except Exception:
            return 0

    def stop(self):
        self.running = False
