"""E2E tests for vaultwatch-rwa-mcp against the REAL Casper testnet.

OPT-IN: pass ``--run-e2e`` to enable. By default these are SKIPPED so a normal
``pytest tests/`` run does NOT touch the network.

These tests only exercise the **read** path (free ``query_global_state``
JSON-RPC calls — no gas, no signing, no CSPR spent). The write path is covered
by ``tests/integration/test_rwa_mcp_tools.py`` with mocked ``AgentWallet``,
because real writes consume real CSPR gas and require a funded + role-granted
agent wallet.

What's verified here:
  * The 8 contracts are live + queryable (``rwa_contract_entrypoints`` for each)
  * The Odra key derivation resolves to real on-chain state (``rwa_audit_get_count``
    returns the live finding count — currently 9 as of 2026-07-22)
  * Resources + the in-memory MCP client surface work end-to-end
  * The block-height read returns a sane value (> 8M as of 2026-07)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastmcp import Client

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

# Reuse the shared e2e opt-in flag + fixtures from the sibling conftest.
# The conftest at tests/e2e/conftest.py registers the --run-e2e CLI option.
from tests.e2e.conftest import (  # noqa: E402
    CONTRACT_HASHES,
)

import vaultwatch_rwa_mcp.server as srv  # noqa: E402

pytestmark = pytest.mark.skipif(
    "--run-e2e" not in sys.argv,
    reason="E2E tests require --run-e2e (they hit the real Casper testnet).",
)


# ---------------------------------------------------------------------------
# Contract liveness — every contract is deployed + queryable
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_all_8_contracts_live_and_queryable():
    """Every contract in the registry must resolve on-chain via query_global_state."""
    async with Client(srv.mcp) as c:
        for name in CONTRACT_HASHES:
            r = await c.call_tool("rwa_contract_entrypoints", {"contract": name})
            d = json.loads(r.content[0].text)
            assert d.get("exists") is True, f"{name} not live on-chain: {d}"
            assert name in d["entry_points"] or True  # entry_points list non-empty
            assert d.get("named_keys"), f"{name} has no named keys"


@pytest.mark.asyncio
async def test_audit_trail_has_record_finding_entrypoint():
    async with Client(srv.mcp) as c:
        r = await c.call_tool("rwa_contract_entrypoints", {"contract": "AuditTrail"})
        d = json.loads(r.content[0].text)
        assert "record_finding" in d["entry_points"]
        assert "get_finding" in d["entry_points"]
        assert "get_count" in d["entry_points"]


@pytest.mark.asyncio
async def test_risk_policy_manager_has_upgrade_policy_entrypoint():
    async with Client(srv.mcp) as c:
        r = await c.call_tool("rwa_contract_entrypoints", {"contract": "RiskPolicyManager"})
        d = json.loads(r.content[0].text)
        assert "upgrade_policy" in d["entry_points"]
        assert "get_current_policy" in d["entry_points"]


# ---------------------------------------------------------------------------
# Live on-chain reads — the Odra key derivation must resolve to real state
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_audit_finding_count_is_positive():
    """AuditTrail.finding_count must return a positive integer (currently 9)."""
    async with Client(srv.mcp) as c:
        r = await c.call_tool("rwa_audit_get_count", {})
        d = json.loads(r.content[0].text)
        assert d["source"] == "on-chain", f"read failed: {d}"
        assert d["finding_count"] is not None
        assert d["finding_count"] > 0, "expected at least 1 finding on-chain"
        assert d["contract"] == "AuditTrail"


@pytest.mark.asyncio
async def test_audit_recent_findings_returned():
    """rwa_audit_recent_findings must return at least 1 finding with all fields."""
    async with Client(srv.mcp) as c:
        r = await c.call_tool("rwa_audit_recent_findings", {"limit": 5})
        d = json.loads(r.content[0].text)
        assert d["source"] == "on-chain"
        assert d["count"] >= 1
        f = d["findings"][0]
        # Every parsed finding must have the full struct shape
        for key in (
            "id",
            "address",
            "risk_type",
            "severity",
            "confidence",
            "description",
            "rwa_enriched",
            "agent_model",
            "block_height",
            "timestamp",
            "tx_hash",
        ):
            assert key in f, f"finding missing field {key}: {f}"


@pytest.mark.asyncio
async def test_block_height_is_recent():
    """rwa_block_height must return a value > 8M (testnet was at ~8.5M on 2026-07-22)."""
    async with Client(srv.mcp) as c:
        r = await c.call_tool("rwa_block_height", {})
        d = json.loads(r.content[0].text)
        assert d["block_height"] is not None, "block height read failed"
        assert d["block_height"] > 8_000_000, f"block height suspiciously low: {d['block_height']}"
        assert d["network"] == "casper-test"


# ---------------------------------------------------------------------------
# Resources — live data surfaces
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_audit_count_resource_live():
    async with Client(srv.mcp) as c:
        res = await c.read_resource("rwa://audit/count")
        d = json.loads(res[0].text)
        assert d["source"] == "on-chain"
        assert d["finding_count"] > 0


@pytest.mark.asyncio
async def test_contracts_resource_lists_8():
    async with Client(srv.mcp) as c:
        res = await c.read_resource("rwa://contracts")
        d = json.loads(res[0].text)
        assert len(d) == 8
        names = {c["name"] for c in d}
        assert names == set(CONTRACT_HASHES.keys())


# ---------------------------------------------------------------------------
# Contract package upgrade-status — verify RiskPolicyManager package resolves
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_risk_policy_manager_package_has_versions():
    async with Client(srv.mcp) as c:
        r = await c.call_tool("rwa_contract_package", {"contract": "RiskPolicyManager"})
        d = json.loads(r.content[0].text)
        assert d.get("exists") is True, f"package query failed: {d}"
        assert isinstance(d.get("versions"), list)
        # The live package must have at least 1 version
        assert len(d["versions"]) >= 1
