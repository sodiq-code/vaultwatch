"""Production-path tests — exercise the real internal LLM call sites.

These tests inject a mock Groq client via the constructor (``groq_client=``)
and exercise the internal methods that previously used a module-level global
client (``_classify``, ``_enrich``, ``_llm_filter``, ``_retry_with_context``,
``_format_description``). This verifies the production code path end-to-end:
the agent builds the real prompt, calls ``self._client.chat.completions.create``
with the documented model, and parses the response — without patching any
module global.

The mock client mirrors the ``groq.Groq`` shape (``.chat.completions.create``
returning an object with ``choices[0].message.content`` and ``usage.total_tokens``).
"""

import json
from unittest.mock import MagicMock

import pytest

from agents.anomaly_agent import AnomalyAgent, AnomalyResult
from agents.audit_agent import AuditAgent
from agents.rwa_agent import EnrichedFinding, RWAAgent
from agents.scanner_agent import RawEvent, ScannerAgent
from agents.self_correction_agent import SelfCorrectionAgent


# ---------------------------------------------------------------------------
# Helpers — build a groq-shaped mock client
# ---------------------------------------------------------------------------


def _mock_groq_client(content: str, total_tokens: int = 42):
    """Build a mock that quacks like ``groq.Groq`` for ``chat.completions.create``."""
    client = MagicMock()
    resp = MagicMock()
    resp.choices = [MagicMock(message=MagicMock(content=content))]
    resp.usage = MagicMock(total_tokens=total_tokens)
    client.chat.completions.create.return_value = resp
    return client


def _make_raw_event() -> RawEvent:
    return RawEvent(
        event_type="whale_movement",
        address="casper1abcdef0123456789",
        amount_motes=500_000_000_000_000,  # 500k CSPR
        block_height=1_500_000,
        timestamp=1_750_000_000,
        raw_data={"demo": True},
        source="cspr_cloud",
    )


def _make_anomaly_result() -> AnomalyResult:
    return AnomalyResult(
        event=_make_raw_event(),
        risk_type="whale_dump",
        severity="HIGH",
        confidence=0.55,  # below default 0.75 threshold → triggers retry
        reasoning="Large transfer detected",
        protocol="CasperSwap",
    )


def _make_enriched_finding() -> EnrichedFinding:
    return EnrichedFinding(
        base=_make_anomaly_result(),
        rwa_context="USDC peg stable",
        collateral_signals=[],
        yield_data="",
        depeg_alerts=[],
        enriched=True,
        rwa_sources_count=1,
        enrichment_model="groq/compound",
    )


# ---------------------------------------------------------------------------
# AnomalyAgent._classify — production path (no _call_groq patching)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_production_path_parses_groq_response():
    """_classify calls self._client with the llama-3.3-70b model and parses JSON."""
    payload = {
        "risk_type": "flash_loan",
        "severity": "CRITICAL",
        "confidence": 0.91,
        "reasoning": "Flash-loan pattern detected",
    }
    client = _mock_groq_client(json.dumps(payload))
    agent = AnomalyAgent(groq_client=client)

    result = await agent._classify(_make_raw_event())

    # Verify the real client was called with the documented model
    client.chat.completions.create.assert_called_once()
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "llama-3.3-70b-versatile"
    assert kwargs["response_format"] == {"type": "json_object"}

    # Verify response parsing
    assert result.risk_type == "flash_loan"
    assert result.severity == "CRITICAL"
    assert result.confidence == 0.91
    assert result.reasoning == "Flash-loan pattern detected"
    assert result.model_used == "llama-3.3-70b-versatile"
    assert result.tokens_used == 42
    assert result.latency_ms >= 0


@pytest.mark.asyncio
async def test_classify_production_path_json_parse_error_falls_back():
    """Malformed Groq output falls back to a medium-confidence manual-review result."""
    client = _mock_groq_client("not valid json at all")
    agent = AnomalyAgent(groq_client=client)

    result = await agent._classify(_make_raw_event())

    assert result.risk_type == "anomalous_flow"
    assert result.severity == "MEDIUM"
    assert result.confidence == 0.5
    assert "manual review" in result.reasoning.lower()


@pytest.mark.asyncio
async def test_classify_no_client_returns_manual_review():
    """No injected client → deterministic medium-confidence fallback (no raise)."""
    agent = AnomalyAgent(groq_api_key="")  # no client
    assert agent._client is None

    result = await agent._classify(_make_raw_event())

    assert result.severity == "MEDIUM"
    assert result.confidence == 0.5
    assert "unavailable" in result.model_used.lower()


# ---------------------------------------------------------------------------
# RWAAgent._enrich — production path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enrich_production_path_parses_compound_response():
    """_enrich calls self._client with compound-beta and parses the RWA JSON."""
    payload = {
        "rwa_context": "USDC depeg risk elevated; collateral ratio dropping.",
        "collateral_signals": ["usdc_depeg", "collateral_drop"],
        "yield_data": "T-bill 10y: 4.2%",
        "depeg_alerts": ["USDC below peg by 0.3%"],
        "sources_found": 3,
    }
    # Compound may wrap JSON in tool-call text; _enrich extracts the {...} block.
    client = _mock_groq_client(f"Here is the analysis:\n{json.dumps(payload)}\nDone.")
    agent = RWAAgent(groq_client=client)

    result = await agent._enrich(_make_anomaly_result())

    client.chat.completions.create.assert_called_once()
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "compound-beta"

    assert result.enriched is True
    # Context now includes feed data prefix alongside Groq web intelligence
    assert "USDC depeg" in result.rwa_context
    # collateral_signals are merged: feed signals + Groq signals (deduplicated)
    assert "usdc_depeg" in result.collateral_signals
    assert "usdc_depeg" in result.collateral_signals or "collateral_drop" in result.collateral_signals
    # depeg_alerts may be merged with feed-derived alerts
    assert "USDC below peg by 0.3%" in result.depeg_alerts
    # Feed data counts as 1 additional source (3 from Groq + 1 from feed)
    assert result.rwa_sources_count >= 3
    # Model now includes feed source alongside Groq
    assert result.enrichment_model == "groq/compound+rwa_feed"
    # New fields: feed_source and x402_payment_id
    assert result.feed_source is not None
    assert isinstance(result.x402_payment_id, str)


@pytest.mark.asyncio
async def test_enrich_no_client_returns_unenriched():
    """No client → un-enriched finding (enriched=False) so pipeline continues."""
    agent = RWAAgent(groq_api_key="")
    assert agent._client is None

    result = await agent._enrich(_make_anomaly_result())

    assert result.enriched is False
    assert result.rwa_sources_count == 0
    assert "unavailable" in result.rwa_context.lower()


# ---------------------------------------------------------------------------
# ScannerAgent._llm_filter — production path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_filter_production_path_filters_events():
    """_llm_filter calls self._client with llama-3.1-8b-instant and filters by index."""
    client = _mock_groq_client("[0, 2]")  # keep events at index 0 and 2
    agent = ScannerAgent(groq_client=client)

    events = [_make_raw_event() for _ in range(3)]
    events[0].event_type = "whale_movement"
    events[1].event_type = "token_transfer"
    events[2].event_type = "contract_call"

    filtered = await agent._llm_filter(events)

    client.chat.completions.create.assert_called_once()
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "llama-3.1-8b-instant"
    assert len(filtered) == 2
    assert filtered[0].event_type == "whale_movement"
    assert filtered[1].event_type == "contract_call"


@pytest.mark.asyncio
async def test_llm_filter_no_client_passes_all_events():
    """No client → all events pass through unfiltered (fail-safe)."""
    agent = ScannerAgent(groq_api_key="")
    assert agent._client is None

    events = [_make_raw_event() for _ in range(5)]
    filtered = await agent._llm_filter(events)
    assert len(filtered) == 5


@pytest.mark.asyncio
async def test_llm_filter_malformed_response_passes_all():
    """Malformed LLM output (no JSON array) → all events pass through."""
    client = _mock_groq_client("I cannot help with that.")
    agent = ScannerAgent(groq_client=client)

    events = [_make_raw_event() for _ in range(3)]
    filtered = await agent._llm_filter(events)
    assert len(filtered) == 3


# ---------------------------------------------------------------------------
# SelfCorrectionAgent._retry_with_context — production path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_retry_with_context_production_path_improves_confidence():
    """_retry_with_context calls self._client with llama-3.3-70b and returns improved result."""
    payload = {
        "risk_type": "whale_dump",
        "severity": "HIGH",
        "confidence": 0.88,
        "reasoning": "Confirmed whale dump pattern after re-analysis",
    }
    client = _mock_groq_client(json.dumps(payload))
    agent = SelfCorrectionAgent(groq_client=client)

    original = _make_anomaly_result()
    result = await agent._retry_with_context(original, attempt=1)

    client.chat.completions.create.assert_called_once()
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "llama-3.3-70b-versatile"

    assert result.confidence == 0.88
    assert result.reasoning == "Confirmed whale dump pattern after re-analysis"
    assert result.tokens_used == 42


@pytest.mark.asyncio
async def test_retry_with_context_no_client_returns_unchanged():
    """No client → result returned unchanged (retry loop terminates, SKIP path)."""
    agent = SelfCorrectionAgent(groq_api_key="")
    assert agent._client is None

    original = _make_anomaly_result()
    result = await agent._retry_with_context(original, attempt=1)
    assert result is original  # unchanged


@pytest.mark.asyncio
async def test_retry_with_context_malformed_json_returns_original():
    """Malformed JSON → original returned unchanged (parse-failure safety)."""
    client = _mock_groq_client("{ broken json")
    agent = SelfCorrectionAgent(groq_client=client)

    original = _make_anomaly_result()
    result = await agent._retry_with_context(original, attempt=1)
    assert result is original


# ---------------------------------------------------------------------------
# AuditAgent._format_description — production path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_format_description_production_path_uses_llm():
    """_format_description calls self._client with llama-3.1-8b-instant."""
    client = _mock_groq_client("Whale dump of 500k CSPR detected on CasperSwap.")
    agent = AuditAgent(casper_client=None, groq_client=client)

    desc = await agent._format_description(_make_enriched_finding())

    client.chat.completions.create.assert_called_once()
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "llama-3.1-8b-instant"
    assert "Whale dump" in desc
    assert len(desc) <= 200


@pytest.mark.asyncio
async def test_format_description_no_client_returns_static_template():
    """No client → static template string (on-chain write still succeeds)."""
    agent = AuditAgent(casper_client=None, groq_api_key="")
    assert agent._client is None

    desc = await agent._format_description(_make_enriched_finding())
    assert "whale_dump" in desc
    assert "HIGH" in desc
    assert "casper1" in desc


@pytest.mark.asyncio
async def test_format_description_llm_error_returns_static_template():
    """LLM call raising → static template string (never blocks on-chain write)."""
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("Groq 503")
    agent = AuditAgent(casper_client=None, groq_client=client)

    desc = await agent._format_description(_make_enriched_finding())
    assert "whale_dump" in desc
    assert "HIGH" in desc


# ---------------------------------------------------------------------------
# Constructor-injection contract — verifies the DI wiring across all agents
# ---------------------------------------------------------------------------


def test_all_agents_accept_groq_client_injection():
    """Every agent accepts a pre-built client via the groq_client= kwarg."""
    mock = _mock_groq_client("{}")
    assert AnomalyAgent(groq_client=mock)._client is mock
    assert RWAAgent(groq_client=mock)._client is mock
    assert ScannerAgent(groq_client=mock)._client is mock
    assert SelfCorrectionAgent(groq_client=mock)._client is mock
    assert AuditAgent(casper_client=None, groq_client=mock)._client is mock
    # IntelAgent + SafetyGuard also support injection (verified in their test files)
    from agents.intel_agent import IntelAgent
    from agents.safety_guard import SafetyGuard

    assert IntelAgent(groq_client=mock)._client is mock
    assert SafetyGuard(groq_client=mock)._client is mock
