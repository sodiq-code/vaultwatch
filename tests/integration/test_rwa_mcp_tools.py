"""Integration tests for vaultwatch-rwa-mcp — tool signatures, mocked RPC, mocked writes.

Uses FastMCP's in-memory Client to exercise every tool's full path:
  * read tools → mocked ``query_global_state`` JSON-RPC responses
  * write tools → mocked ``AgentWallet.call_contract`` / ``open_vault``
  * wallet tools → mocked ``AgentWallet`` singleton

No network access, no real deploys, no real CSPR spent. Mirrors the pattern in
``tests/integration/test_mcp_tools.py``.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastmcp import Client

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

import vaultwatch_rwa_mcp.server as srv
from vaultwatch_rwa_mcp import readers as R
from vaultwatch_rwa_mcp import writers as W


# ---------------------------------------------------------------------------
# Helpers — build CLValue responses the way the Casper RPC returns them
# ---------------------------------------------------------------------------
def _clvalue(inner: bytes) -> dict:
    """Wrap inner bytes as the Odra List<U8> CLValue the RPC returns."""
    return {"bytes": (struct.pack("<I", len(inner)) + inner).hex(), "parsed": list(inner)}


def _mock_rpc_response_for_dict(cl_value: dict | None) -> dict:
    if cl_value is None:
        # ValueNotFound error code
        return {"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "ValueNotFound"}}
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"stored_value": {"CLValue": cl_value}, "merkle_proof": ""},
    }


def _patch_rpc(monkeypatch, responses):
    """Patch the low-level ``_rpc`` sync helper to return queued responses.

    ``responses`` is a list of dicts (each one full JSON-RPC envelope). Each
    call pops the next response. The state-root-hash + state-uref lookups are
    pre-seeded so the read path doesn't try to hit the network.
    """
    calls = {"n": 0}

    def fake_rpc(method, params, rpc_url=None):
        i = calls["n"]
        calls["n"] += 1
        if method == "chain_get_state_root_hash":
            return {"result": {"state_root_hash": "ab" * 32}}
        if method == "query_global_state" and params and params[1].startswith("hash-"):
            # contract hash lookup → return a Contract with a 'state' named key
            return {
                "result": {
                    "stored_value": {
                        "Contract": {
                            "named_keys": [{"name": "state", "key": "uref-" + "cd" * 32 + "-007"}],
                            "entry_points": [],
                        }
                    }
                }
            }
        # dictionary read
        if i < len(responses):
            return responses[i]
        return _mock_rpc_response_for_dict(None)

    monkeypatch.setattr(R, "_rpc", fake_rpc)
    monkeypatch.setattr(R, "_get_state_root_hash", lambda *a, **k: "ab" * 32)
    # State uref addr = the 32 bytes from the named key
    uref_addr = bytes.fromhex("cd" * 32)
    monkeypatch.setattr(R, "_get_state_uref_addr", lambda *a, **k: uref_addr)


# ---------------------------------------------------------------------------
# Server + tool registration
# ---------------------------------------------------------------------------
class TestServerShape:
    @pytest.mark.asyncio
    async def test_server_has_39_tools(self):
        async with Client(srv.mcp) as c:
            tools = await c.list_tools()
            assert len(tools) == 39, f"expected 39 tools, got {len(tools)}"

    @pytest.mark.asyncio
    async def test_tools_are_prefixed_rwa(self):
        async with Client(srv.mcp) as c:
            tools = await c.list_tools()
            for t in tools:
                assert t.name.startswith("rwa_"), f"tool {t.name} not rwa_-prefixed"

    @pytest.mark.asyncio
    async def test_server_has_3_resources(self):
        async with Client(srv.mcp) as c:
            res = await c.list_resources()
            uris = [str(r.uri) for r in res]
            assert "rwa://contracts" in uris
            assert "rwa://policy/current" in uris
            assert "rwa://audit/count" in uris

    @pytest.mark.asyncio
    async def test_server_has_4_prompts(self):
        async with Client(srv.mcp) as c:
            prompts = await c.list_prompts()
            names = {p.name for p in prompts}
            assert "rwa_explain_contracts" in names
            assert "rwa_audit_summary" in names
            assert "rwa_risk_assessment" in names
            assert "rwa_policy_review" in names

    @pytest.mark.asyncio
    async def test_every_tool_has_description(self):
        async with Client(srv.mcp) as c:
            tools = await c.list_tools()
            for t in tools:
                assert t.description and len(t.description) > 20, f"{t.name} missing description"


# ---------------------------------------------------------------------------
# Read tools — mocked RPC
# ---------------------------------------------------------------------------
class TestReadTools:
    @pytest.mark.asyncio
    async def test_rwa_list_contracts(self):
        async with Client(srv.mcp) as c:
            r = await c.call_tool("rwa_list_contracts", {})
            d = json.loads(r.content[0].text)
            assert d["count"] == 8
            assert "network" in d
            assert any(c["name"] == "AuditTrail" for c in d["contracts"])

    @pytest.mark.asyncio
    async def test_rwa_audit_get_count(self, monkeypatch):
        # finding_count Var<u64> = 9
        inner = struct.pack("<Q", 9)
        _patch_rpc(monkeypatch, [_mock_rpc_response_for_dict(_clvalue(inner))])
        async with Client(srv.mcp) as c:
            r = await c.call_tool("rwa_audit_get_count", {})
            d = json.loads(r.content[0].text)
            assert d["finding_count"] == 9
            assert d["source"] == "on-chain"
            assert d["contract"] == "AuditTrail"

    @pytest.mark.asyncio
    async def test_rwa_audit_get_finding(self, monkeypatch):
        # Build a Finding
        inner = (
            struct.pack("<Q", 3)
            + R._enc_string("account-hash-f1")
            + R._enc_string("wash_trading")
            + R._enc_string("HIGH")
            + bytes([90])
            + R._enc_string("test finding")
            + bytes([1])
            + R._enc_string("AnomalyAgent")
            + struct.pack("<Q", 100)
            + struct.pack("<Q", 1700000000)
            + R._enc_string("hash123")
        )
        _patch_rpc(monkeypatch, [_mock_rpc_response_for_dict(_clvalue(inner))])
        async with Client(srv.mcp) as c:
            r = await c.call_tool("rwa_audit_get_finding", {"finding_id": 3})
            d = json.loads(r.content[0].text)
            assert d["finding_id"] == 3
            assert d["finding"]["id"] == 3
            assert d["finding"]["severity"] == "HIGH"
            assert d["finding"]["confidence"] == 90
            assert d["source"] == "on-chain"

    @pytest.mark.asyncio
    async def test_rwa_risk_get_score(self, monkeypatch):
        inner = (
            R._enc_string("account-hash-risky") + bytes([85]) + R._enc_string("liquidity") + bytes([92]) + struct.pack("<Q", 1700000001) + struct.pack("<Q", 5)
        )
        _patch_rpc(monkeypatch, [_mock_rpc_response_for_dict(_clvalue(inner))])
        async with Client(srv.mcp) as c:
            r = await c.call_tool("rwa_risk_get_score", {"address": "account-hash-risky"})
            d = json.loads(r.content[0].text)
            assert d["risk_score"]["score"] == 85
            assert d["risk_score"]["risk_type"] == "liquidity"
            assert d["source"] == "on-chain"

    @pytest.mark.asyncio
    async def test_rwa_risk_is_high_risk_above_threshold(self, monkeypatch):
        inner = R._enc_string("addr") + bytes([85]) + R._enc_string("liquidity") + bytes([90]) + struct.pack("<Q", 1) + struct.pack("<Q", 1)
        _patch_rpc(monkeypatch, [_mock_rpc_response_for_dict(_clvalue(inner))])
        async with Client(srv.mcp) as c:
            r = await c.call_tool("rwa_risk_is_high_risk", {"address": "addr", "threshold": 70})
            d = json.loads(r.content[0].text)
            assert d["is_high_risk"] is True
            assert d["score"] == 85

    @pytest.mark.asyncio
    async def test_rwa_risk_is_high_risk_below_threshold(self, monkeypatch):
        inner = R._enc_string("addr") + bytes([50]) + R._enc_string("liquidity") + bytes([90]) + struct.pack("<Q", 1) + struct.pack("<Q", 1)
        _patch_rpc(monkeypatch, [_mock_rpc_response_for_dict(_clvalue(inner))])
        async with Client(srv.mcp) as c:
            r = await c.call_tool("rwa_risk_is_high_risk", {"address": "addr", "threshold": 70})
            d = json.loads(r.content[0].text)
            assert d["is_high_risk"] is False

    @pytest.mark.asyncio
    async def test_rwa_risk_is_high_risk_not_found(self, monkeypatch):
        _patch_rpc(monkeypatch, [_mock_rpc_response_for_dict(None)])
        async with Client(srv.mcp) as c:
            r = await c.call_tool("rwa_risk_is_high_risk", {"address": "unknown"})
            d = json.loads(r.content[0].text)
            assert d["is_high_risk"] is False
            assert d["source"] == "not_found"

    @pytest.mark.asyncio
    async def test_rwa_policy_get_current(self, monkeypatch):
        label = "admin"
        inner = struct.pack("<I", 1) + bytes([75, 80, 60, 40, 2, 80]) + struct.pack("<Q", 4000) + R._enc_string(label)
        _patch_rpc(monkeypatch, [_mock_rpc_response_for_dict(_clvalue(inner))])
        async with Client(srv.mcp) as c:
            r = await c.call_tool("rwa_policy_get_current", {})
            d = json.loads(r.content[0].text)
            assert d["current_policy"]["version"] == 1
            assert d["current_policy"]["min_confidence_threshold"] == 75
            assert d["current_policy"]["updated_by"] == "admin"

    @pytest.mark.asyncio
    async def test_rwa_agent_get_metrics(self, monkeypatch):
        inner = (
            R._enc_string("AnomalyAgent")
            + struct.pack("<Q", 50)
            + struct.pack("<Q", 3)
            + struct.pack("<Q", 1)
            + bytes([88])
            + struct.pack("<Q", 40)
            + struct.pack("<Q", 10)
            + struct.pack("<Q", 4500)
            + bytes([82])
        )
        _patch_rpc(monkeypatch, [_mock_rpc_response_for_dict(_clvalue(inner))])
        async with Client(srv.mcp) as c:
            r = await c.call_tool("rwa_agent_get_metrics", {"agent_name": "AnomalyAgent"})
            d = json.loads(r.content[0].text)
            assert d["metrics"]["agent_name"] == "AnomalyAgent"
            assert d["metrics"]["trust_score"] == 82
            assert d["metrics"]["total_decisions"] == 50

    @pytest.mark.asyncio
    async def test_rwa_credit_get_balance(self, monkeypatch):
        motes = 5_000_000_000
        mag = motes.to_bytes(5, "little")
        inner = (
            R._enc_string("account-hash-cred")
            + struct.pack("<I", len(mag))
            + mag  # balance
            + struct.pack("<I", len(mag))
            + mag  # total_deposited
            + struct.pack("<I", 1)
            + (1).to_bytes(1, "little")  # total_spent
            + struct.pack("<Q", 7)  # query_count
        )
        _patch_rpc(monkeypatch, [_mock_rpc_response_for_dict(_clvalue(inner))])
        async with Client(srv.mcp) as c:
            r = await c.call_tool("rwa_credit_get_balance", {"account_address": "account-hash-cred"})
            d = json.loads(r.content[0].text)
            assert d["balance_motes"] == motes
            assert d["balance_cspr"] == 5.0

    @pytest.mark.asyncio
    async def test_rwa_contract_entrypoints_unknown_contract(self):
        async with Client(srv.mcp) as c:
            r = await c.call_tool("rwa_contract_entrypoints", {"contract": "Bogus"})
            d = json.loads(r.content[0].text)
            assert "error" in d
            assert "Bogus" in d["error"]


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------
class TestResources:
    @pytest.mark.asyncio
    async def test_rwa_contracts_resource(self):
        async with Client(srv.mcp) as c:
            res = await c.read_resource("rwa://contracts")
            d = json.loads(res[0].text)
            assert isinstance(d, list)
            assert len(d) == 8
            assert d[0]["name"] in {
                "AuditTrail",
                "RiskOracle",
                "SentinelCredit",
                "SentinelRegistry",
                "SentinelAlertLog",
                "AgentBehaviorIndex",
                "RiskPolicyManager",
                "SubscriberVault",
            }

    @pytest.mark.asyncio
    async def test_rwa_audit_count_resource(self, monkeypatch):
        inner = struct.pack("<Q", 9)
        _patch_rpc(monkeypatch, [_mock_rpc_response_for_dict(_clvalue(inner))])
        async with Client(srv.mcp) as c:
            res = await c.read_resource("rwa://audit/count")
            d = json.loads(res[0].text)
            assert d["finding_count"] == 9
            assert d["source"] == "on-chain"


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
class TestPrompts:
    @pytest.mark.asyncio
    async def test_prompt_risk_assessment_includes_address(self):
        async with Client(srv.mcp) as c:
            r = await c.get_prompt("rwa_risk_assessment", {"address": "account-hash-abc"})
            # The prompt's message text should reference the address
            text = r.messages[0].content.text if hasattr(r.messages[0].content, "text") else str(r.messages[0].content)
            assert "account-hash-abc" in text

    @pytest.mark.asyncio
    async def test_prompt_explain_contracts_lists_all(self):
        async with Client(srv.mcp) as c:
            r = await c.get_prompt("rwa_explain_contracts", {})
            text = r.messages[0].content.text if hasattr(r.messages[0].content, "text") else str(r.messages[0].content)
            for name in ["AuditTrail", "RiskOracle", "SubscriberVault"]:
                assert name in text


# ---------------------------------------------------------------------------
# Write tools — mocked AgentWallet
# ---------------------------------------------------------------------------
class TestWriteTools:
    @pytest.mark.asyncio
    async def test_rwa_wallet_status(self, monkeypatch):
        fake_wallet = MagicMock()
        fake_wallet.public_key = "02" + "ab" * 32
        fake_wallet.account_hash = "account-hash-" + "cd" * 32
        fake_wallet.balance_motes = 5_000_000_000
        fake_wallet.balance_cspr = 5.0
        fake_wallet.funded = True
        fake_wallet.key_algorithm = "secp256k1"
        fake_wallet.chain_name = "casper-test"
        fake_wallet.rpc_url = "https://node.testnet.casper.network/rpc"
        fake_wallet.key_path = Path("/tmp/fake_key.pem")
        fake_wallet.explorer_url = "https://testnet.cspr.live/account/02ab"
        fake_wallet.faucet_url = "https://testnet.cspr.live/tools/faucet"
        monkeypatch.setattr(W, "get_wallet", lambda: fake_wallet)
        monkeypatch.setattr(srv.W, "get_wallet", lambda: fake_wallet)
        async with Client(srv.mcp) as c:
            r = await c.call_tool("rwa_wallet_status", {})
            d = json.loads(r.content[0].text)
            assert d["ok"] is True
            assert d["funded"] is True
            assert d["balance_cspr"] == 5.0
            assert d["integration"] == "CSPR.click AI Agent Skill (headless casper-js-sdk v5)"

    @pytest.mark.asyncio
    async def test_rwa_audit_record_finding(self, monkeypatch):
        fake_wallet = MagicMock()
        fake_wallet.call_contract.return_value = {
            "success": True,
            "deploy_hash": "deadbeef" * 8,
            "block_hash": "feedface" * 8,
            "cost_motes": "2500000000",
            "link": "https://testnet.cspr.live/deploy/deadbeef",
            "deployer_account_hash": "account-hash-abc",
            "error": None,
        }
        monkeypatch.setattr(W, "get_wallet", lambda: fake_wallet)
        monkeypatch.setattr(srv.W, "get_wallet", lambda: fake_wallet)
        async with Client(srv.mcp) as c:
            r = await c.call_tool(
                "rwa_audit_record_finding",
                {
                    "address": "account-hash-target",
                    "risk_type": "wash_trading",
                    "severity": "HIGH",
                    "confidence": 88,
                    "description": "suspicious volume",
                },
            )
            d = json.loads(r.content[0].text)
            assert d["status"] == "deployed_on_chain"
            assert d["on_chain_verified"] is True
            assert d["deploy_hash"] == "deadbeef" * 8
            assert d["contract"] == "AuditTrail"
            assert d["entry_point"] == "record_finding"
            # Verify the wallet was called with the right contract + entry point
            call_args = fake_wallet.call_contract.call_args
            assert call_args.kwargs["entry_point"] == "record_finding"
            # Confidence must be u8
            args = call_args.kwargs["args"]
            assert args["confidence"] == {"type": "u8", "value": "88"}

    @pytest.mark.asyncio
    async def test_rwa_policy_upgrade(self, monkeypatch):
        fake_wallet = MagicMock()
        fake_wallet.call_contract.return_value = {
            "success": True,
            "deploy_hash": "abc" * 21,
            "block_hash": "def" * 21,
            "cost_motes": "2500000000",
            "link": "https://testnet.cspr.live/deploy/abc",
            "deployer_account_hash": "account-hash-x",
            "error": None,
        }
        monkeypatch.setattr(W, "get_wallet", lambda: fake_wallet)
        monkeypatch.setattr(srv.W, "get_wallet", lambda: fake_wallet)
        async with Client(srv.mcp) as c:
            r = await c.call_tool(
                "rwa_policy_upgrade",
                {
                    "min_confidence_threshold": 80,
                    "critical_score_threshold": 85,
                    "updated_by": "test-agent",
                },
            )
            d = json.loads(r.content[0].text)
            assert d["status"] == "deployed_on_chain"
            assert d["contract"] == "RiskPolicyManager"
            args = fake_wallet.call_contract.call_args.kwargs["args"]
            assert args["updated_by"] == {"type": "string", "value": "test-agent"}
            assert args["min_confidence_threshold"] == {"type": "u8", "value": "80"}

    @pytest.mark.asyncio
    async def test_rwa_agent_record_decision(self, monkeypatch):
        fake_wallet = MagicMock()
        fake_wallet.call_contract.return_value = {
            "success": True,
            "deploy_hash": "dec" * 21,
            "block_hash": "blk" * 21,
            "cost_motes": "2500000000",
            "link": "https://testnet.cspr.live/deploy/dec",
            "deployer_account_hash": "account-hash-y",
            "error": None,
        }
        monkeypatch.setattr(W, "get_wallet", lambda: fake_wallet)
        monkeypatch.setattr(srv.W, "get_wallet", lambda: fake_wallet)
        async with Client(srv.mcp) as c:
            r = await c.call_tool(
                "rwa_agent_record_decision",
                {
                    "agent_name": "RWAAgent",
                    "confidence": 91,
                },
            )
            d = json.loads(r.content[0].text)
            assert d["status"] == "deployed_on_chain"
            assert d["contract"] == "AgentBehaviorIndex"
            args = fake_wallet.call_contract.call_args.kwargs["args"]
            assert args["confidence"] == {"type": "u8", "value": "91"}
            assert args["safety_rejected"] == {"type": "bool", "value": "false"}

    @pytest.mark.asyncio
    async def test_rwa_sentinel_register(self, monkeypatch):
        fake_wallet = MagicMock()
        fake_wallet.call_contract.return_value = {
            "success": True,
            "deploy_hash": "reg" * 21,
            "block_hash": "b" * 63,
            "cost_motes": "2500000000",
            "link": "https://testnet.cspr.live/deploy/reg",
            "deployer_account_hash": "account-hash-z",
            "error": None,
        }
        monkeypatch.setattr(W, "get_wallet", lambda: fake_wallet)
        monkeypatch.setattr(srv.W, "get_wallet", lambda: fake_wallet)
        async with Client(srv.mcp) as c:
            r = await c.call_tool(
                "rwa_sentinel_register",
                {
                    "address": "account-hash-sub",
                    "webhook_url": "https://hook.x/wh",
                    "min_severity": "CRITICAL",
                },
            )
            d = json.loads(r.content[0].text)
            assert d["status"] == "deployed_on_chain"
            assert d["contract"] == "SentinelRegistry"
            assert d["entry_point"] == "register"

    @pytest.mark.asyncio
    async def test_rwa_write_handles_wallet_error(self, monkeypatch):
        from agents.agent_wallet import AgentWalletError

        fake_wallet = MagicMock()
        fake_wallet.call_contract.side_effect = AgentWalletError("unfunded wallet")
        monkeypatch.setattr(W, "get_wallet", lambda: fake_wallet)
        monkeypatch.setattr(srv.W, "get_wallet", lambda: fake_wallet)
        async with Client(srv.mcp) as c:
            r = await c.call_tool(
                "rwa_audit_record_finding",
                {
                    "address": "addr",
                    "risk_type": "t",
                    "severity": "LOW",
                    "confidence": 50,
                    "description": "d",
                },
            )
            d = json.loads(r.content[0].text)
            assert d["status"] == "deploy_failed"
            assert d["on_chain_verified"] is False
            assert "unfunded" in d["error"]

    @pytest.mark.asyncio
    async def test_rwa_vault_open_uses_x402_helper(self, monkeypatch):
        """open_vault must route through the x402 helper (payable path), not casper_call."""
        fake_wallet = MagicMock()
        fake_wallet.key_path = Path("/tmp/fake.pem")
        fake_wallet.key_algorithm = "secp256k1"
        fake_wallet.rpc_url = "https://node.testnet.casper.network/rpc"
        monkeypatch.setattr(W, "get_wallet", lambda: fake_wallet)
        monkeypatch.setattr(srv.W, "get_wallet", lambda: fake_wallet)

        captured = {}

        class FakeProc:
            returncode = 0

            async def communicate(self, stdin):
                captured["payload"] = json.loads(stdin.decode())
                return (
                    json.dumps(
                        {
                            "success": True,
                            "deployHash": "vault" + "0" * 59,
                            "blockHash": "b" * 64,
                            "gasCostMotes": "2500000000",
                            "link": "https://testnet.cspr.live/deploy/vault",
                            "deployerAccountHash": "account-hash-v",
                            "error": None,
                        }
                    ).encode(),
                    b"",
                )

        async def fake_exec(*args, **kwargs):
            return FakeProc()

        monkeypatch.setattr(W.asyncio, "create_subprocess_exec", fake_exec)
        async with Client(srv.mcp) as c:
            r = await c.call_tool(
                "rwa_vault_open",
                {
                    "subscriber_address": "account-hash-sub",
                    "initial_deposit_motes": 5_000_000_000,
                    "lock_blocks": 0,
                },
            )
            d = json.loads(r.content[0].text)
            assert d["status"] == "deployed_on_chain"
            assert d["contract"] == "SubscriberVault"
            assert d["entry_point"] == "open_vault"
            # Verify the x402 helper payload schema
            assert captured["payload"]["subscriberAddress"] == "account-hash-sub"
            assert captured["payload"]["amountMotes"] == 5_000_000_000
            assert captured["payload"]["autoRenew"] is True
            assert captured["payload"]["signerPemPath"] == "/tmp/fake.pem"
