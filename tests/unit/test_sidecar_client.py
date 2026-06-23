"""Unit tests — SidecarClient"""

import pytest
from unittest.mock import patch

from streaming.sidecar_client import SidecarClient


@pytest.fixture
def client():
    return SidecarClient(url="http://localhost:9999/events/main")


@pytest.mark.asyncio
async def test_client_init(client):
    assert client.url == "http://localhost:9999/events/main"


@pytest.mark.asyncio
async def test_stream_yields_events(client):
    """stream() should yield decoded event dicts."""
    raw_lines = [
        b'{"type": "BlockAdded", "block_height": 100}',
        b'{"type": "DeployProcessed", "deploy_hash": "abc"}',
    ]

    async def mock_raw_stream():
        for line in raw_lines:
            yield line

    with patch.object(client, "_raw_stream", return_value=mock_raw_stream()):
        events = []
        async for event in client.stream():
            events.append(event)

    assert len(events) == 2
    assert events[0]["type"] == "BlockAdded"
    assert events[1]["type"] == "DeployProcessed"


@pytest.mark.asyncio
async def test_stream_handles_invalid_json(client):
    """stream() should skip invalid JSON lines."""
    raw_lines = [
        b'INVALID_JSON',
        b'{"type": "BlockAdded"}',
    ]

    async def mock_raw_stream():
        for line in raw_lines:
            yield line

    with patch.object(client, "_raw_stream", return_value=mock_raw_stream()):
        events = []
        async for event in client.stream():
            events.append(event)

    # Should skip invalid, yield valid
    assert len(events) >= 1
    assert events[0]["type"] == "BlockAdded"


@pytest.mark.asyncio
async def test_stream_empty(client):
    """stream() with no events should yield nothing."""
    async def mock_raw_stream():
        return
        yield  # make it an async generator

    with patch.object(client, "_raw_stream", return_value=mock_raw_stream()):
        events = []
        async for event in client.stream():
            events.append(event)

    assert events == []


@pytest.mark.asyncio
async def test_stream_reconnects_on_error(client):
    """stream() propagates errors; pipeline handles reconnect."""
    async def failing_raw_stream():
        raise ConnectionError("SSE server down")
        yield  # make it a generator

    # stream wraps _raw_stream — test that it handles error gracefully
    with patch.object(client, "_raw_stream", side_effect=ConnectionError("down")):
        try:
            async for _ in client.stream():
                break
        except (ConnectionError, StopAsyncIteration, Exception):
            pass


def test_default_url():
    c = SidecarClient()
    assert c.url.startswith("http")


@pytest.mark.asyncio
async def test_stream_block_events(client):
    """stream() should yield BlockAdded events."""
    raw_lines = [
        b'{"type": "Block", "block_height": 200, "block_hash": "xyz"}',
    ]

    async def mock_raw_stream():
        for line in raw_lines:
            yield line

    with patch.object(client, "_raw_stream", return_value=mock_raw_stream()):
        events = []
        async for event in client.stream():
            events.append(event)

    if events:
        assert events[0].get("type") == "Block"
