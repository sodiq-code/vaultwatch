"""Unit tests for the AgentWallet abstraction (CSPR.click AI Agent Skill).

These tests verify the Python wrapper logic WITHOUT submitting real
deploys (no network, no gas). The Node helper is invoked only for the
``info``/``public`` commands against a temporary unfunded key —
``call_contract`` and ``transfer_cspr`` are exercised with a stubbed
subprocess to keep the tests hermetic.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from agents.agent_wallet import (  # noqa: E402
    AgentWallet,
    AgentWalletError,
    AgentWalletUnfunded,
    DEFAULT_AGENT_KEY_PATH,
    DEFAULT_CHAIN_NAME,
    DEFAULT_KEY_ALGORITHM,
    DEFAULT_RPC_URL,
    FAUCET_URL,
)


# ---------------------------------------------------------------------------
# Test fixture: create a fresh unfunded agent wallet in a temp dir
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def temp_agent_wallet_path(tmp_path_factory):
    """Create a real (unfunded) agent wallet PEM in a temp directory."""
    tmp_dir = tmp_path_factory.mktemp("agent_wallet")
    key_path = tmp_dir / "agent_key.pem"

    # Use the Node helper to create a real keypair (exercises the full
    # create → PEM serialization → save path).
    AgentWallet._create_keypair(
        key_path,
        key_algorithm=DEFAULT_KEY_ALGORITHM,
        rpc_url=DEFAULT_RPC_URL,
        chain_name=DEFAULT_CHAIN_NAME,
    )
    assert key_path.exists(), "agent_wallet.cjs create did not produce a PEM file"
    assert key_path.stat().st_size > 100, "PEM file is suspiciously small"
    return key_path


# ---------------------------------------------------------------------------
# Constants + module structure
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify the module-level constants match the Node helper defaults."""

    def test_default_rpc_url(self):
        assert DEFAULT_RPC_URL == "https://node.testnet.casper.network/rpc"

    def test_default_chain_name(self):
        assert DEFAULT_CHAIN_NAME == "casper-test"

    def test_default_key_algorithm(self):
        assert DEFAULT_KEY_ALGORITHM == "secp256k1"

    def test_faucet_url(self):
        assert FAUCET_URL == "https://testnet.cspr.live/tools/faucet"

    def test_default_agent_key_path_is_in_home(self):
        assert ".vaultwatch" in str(DEFAULT_AGENT_KEY_PATH)
        assert DEFAULT_AGENT_KEY_PATH.name == "agent_key.pem"


# ---------------------------------------------------------------------------
# Wallet creation + loading
# ---------------------------------------------------------------------------


class TestWalletCreation:
    """Verify the create → load cycle works end-to-end with a real keypair."""

    def test_create_produces_valid_pem(self, temp_agent_wallet_path):
        """The created PEM must be loadable by casper-js-sdk (via the Node helper)."""
        # If the PEM were invalid, AgentWallet.load() would raise.
        wallet = AgentWallet.load(key_path=temp_agent_wallet_path)
        assert wallet.public_key.startswith("02")  # SECP256K1 prefix
        # Casper public key format: 1-byte algo prefix (02) + 33-byte SECP256K1 pubkey
        # = 34 bytes = 68 hex chars.
        assert len(wallet.public_key) == 68
        assert wallet.account_hash.startswith("account-hash-")
        assert len(wallet.account_hash) == len("account-hash-") + 64

    def test_load_returns_unfunded_wallet_for_fresh_keypair(self, temp_agent_wallet_path):
        """A freshly-created wallet has no on-chain account → balance is None."""
        wallet = AgentWallet.load(key_path=temp_agent_wallet_path)
        # The wallet is unfunded (no on-chain account), so balance is None.
        assert wallet.balance_motes is None
        assert wallet.balance_cspr is None
        assert wallet.funded is False

    def test_load_raises_on_missing_key(self, tmp_path):
        """Loading a non-existent key path raises AgentWalletError."""
        with pytest.raises(AgentWalletError, match="No agent wallet"):
            AgentWallet.load(key_path=tmp_path / "nonexistent.pem")

    def test_ensure_exists_creates_wallet_when_missing(self, tmp_path):
        """ensure_exists(create_if_missing=True) creates a wallet if none exists."""
        key_path = tmp_path / "auto_created.pem"
        assert not key_path.exists()
        wallet = AgentWallet.ensure_exists(key_path=key_path)
        assert key_path.exists()
        assert wallet.public_key.startswith("02")

    def test_ensure_exists_raises_when_missing_and_not_create(self, tmp_path):
        """ensure_exists(create_if_missing=False) raises if no wallet exists."""
        with pytest.raises(AgentWalletError, match="No agent wallet"):
            AgentWallet.ensure_exists(
                key_path=tmp_path / "nonexistent.pem",
                create_if_missing=False,
            )

    def test_ensure_exists_loads_existing_wallet(self, temp_agent_wallet_path):
        """ensure_exists loads an existing wallet without overwriting it."""
        original = AgentWallet.load(key_path=temp_agent_wallet_path)
        loaded = AgentWallet.ensure_exists(key_path=temp_agent_wallet_path)
        assert loaded.public_key == original.public_key
        assert loaded.account_hash == original.account_hash


# ---------------------------------------------------------------------------
# Properties + assertions
# ---------------------------------------------------------------------------


class TestWalletProperties:
    """Verify the read-only properties + funded/balance assertions."""

    def test_explorer_url_format(self, temp_agent_wallet_path):
        wallet = AgentWallet.load(key_path=temp_agent_wallet_path)
        assert wallet.explorer_url == f"https://testnet.cspr.live/account/{wallet.public_key}"

    def test_faucet_url(self, temp_agent_wallet_path):
        wallet = AgentWallet.load(key_path=temp_agent_wallet_path)
        assert wallet.faucet_url == FAUCET_URL

    def test_assert_funded_raises_on_unfunded_wallet(self, temp_agent_wallet_path):
        """assert_funded raises AgentWalletUnfunded when balance is None."""
        wallet = AgentWallet.load(key_path=temp_agent_wallet_path)
        with pytest.raises(AgentWalletUnfunded, match="no on-chain account"):
            wallet.assert_funded(min_cspr=1.0)

    def test_assert_funded_raises_when_below_minimum(self, temp_agent_wallet_path):
        """assert_funded raises when balance is below the minimum."""
        wallet = AgentWallet.load(key_path=temp_agent_wallet_path)
        # Force a fake balance below the minimum
        wallet.balance_motes = 500_000_000  # 0.5 CSPR
        with pytest.raises(AgentWalletUnfunded, match="below the minimum"):
            wallet.assert_funded(min_cspr=1.0)

    def test_assert_funded_passes_when_above_minimum(self, temp_agent_wallet_path):
        """assert_funded passes when balance is above the minimum."""
        wallet = AgentWallet.load(key_path=temp_agent_wallet_path)
        wallet.balance_motes = 100_000_000_000  # 100 CSPR
        wallet.assert_funded(min_cspr=1.0)  # should not raise

    def test_balance_cspr_conversion(self, temp_agent_wallet_path):
        """balance_cspr = balance_motes / 1e9."""
        wallet = AgentWallet.load(key_path=temp_agent_wallet_path)
        wallet.balance_motes = 4_308_321_908_670  # 4308.32 CSPR
        assert wallet.balance_cspr == pytest.approx(4308.32, rel=1e-6)


# ---------------------------------------------------------------------------
# call_contract — subprocess stubbed (no real deploy)
# ---------------------------------------------------------------------------


class TestCallContract:
    """Verify call_contract builds the correct payload for casper_call.cjs."""

    def test_call_contract_invokes_casper_call_helper(self, temp_agent_wallet_path):
        """call_contract shells out to scripts/casper_call.cjs with the right payload."""
        wallet = AgentWallet.load(key_path=temp_agent_wallet_path)

        # Stub the subprocess call to capture the payload without hitting the network
        captured_payload = {}

        def fake_run(cmd, input, capture_output, timeout, cwd):
            captured_payload["cmd"] = cmd
            captured_payload["input"] = json.loads(input.decode("utf-8"))
            captured_payload["cwd"] = cwd

            class _Proc:
                returncode = 0
                stdout = json.dumps(
                    {
                        "success": True,
                        "deploy_hash": "abc123",
                        "block_hash": "def456",
                        "cost_motes": "5000000000",
                        "link": "https://testnet.cspr.live/deploy/abc123",
                        "error": None,
                    }
                ).encode("utf-8")
                stderr = b""

            return _Proc()

        with patch("subprocess.run", side_effect=fake_run):
            result = wallet.call_contract(
                contract_hash="cd1579001dcd923888baa9ea44b1df3b816de52ced44682a3042779d1d4d9932",
                entry_point="record_finding",
                args={"agent_name": {"type": "string", "value": "TestAgent"}},
                payment_motes=5_000_000_000,
            )

        assert result["success"] is True
        assert result["deploy_hash"] == "abc123"
        # Verify the payload passed to casper_call.cjs
        payload = captured_payload["input"]
        assert payload["contract_hash"] == "cd1579001dcd923888baa9ea44b1df3b816de52ced44682a3042779d1d4d9932"
        assert payload["entry_point"] == "record_finding"
        assert payload["signer_pem_path"] == str(wallet.key_path)
        assert payload["key_algorithm"] == wallet.key_algorithm
        assert payload["rpc_url"] == wallet.rpc_url
        assert payload["payment_motes"] == 5_000_000_000

    def test_call_contract_strips_hash_prefix(self, temp_agent_wallet_path):
        """call_contract strips the 'hash-' prefix from contract_hash."""
        wallet = AgentWallet.load(key_path=temp_agent_wallet_path)

        captured = {}

        def fake_run(cmd, input, capture_output, timeout, cwd):
            captured["input"] = json.loads(input.decode("utf-8"))

            class _Proc:
                returncode = 0
                stdout = json.dumps({"success": True, "deploy_hash": "x"}).encode()
                stderr = b""

            return _Proc()

        with patch("subprocess.run", side_effect=fake_run):
            wallet.call_contract(
                contract_hash="hash-cd1579001dcd923888baa9ea44b1df3b816de52ced44682a3042779d1d4d9932",
                entry_point="get_count",
                args={},
            )
        assert captured["input"]["contract_hash"] == "cd1579001dcd923888baa9ea44b1df3b816de52ced44682a3042779d1d4d9932"

    def test_call_contract_raises_on_helper_failure(self, temp_agent_wallet_path):
        """call_contract raises AgentWalletError when casper_call.cjs exits non-zero."""
        wallet = AgentWallet.load(key_path=temp_agent_wallet_path)

        def fake_run(cmd, input, capture_output, timeout, cwd):
            class _Proc:
                returncode = 1
                stdout = b""
                stderr = b"simulated helper failure"

            return _Proc()

        with patch("subprocess.run", side_effect=fake_run):
            with pytest.raises(AgentWalletError, match="exited 1"):
                wallet.call_contract(
                    contract_hash="cd1579001dcd923888baa9ea44b1df3b816de52ced44682a3042779d1d4d9932",
                    entry_point="get_count",
                    args={},
                )


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


class TestErrorPaths:
    """Verify error handling for missing helpers + bad JSON responses."""

    def test_run_helper_raises_when_helper_missing(self, tmp_path):
        """_run_helper raises AgentWalletError when the .cjs helper doesn't exist."""
        # Patch the helper path to a non-existent file
        with patch("agents.agent_wallet._AGENT_WALLET_HELPER", tmp_path / "missing.cjs"):
            with pytest.raises(AgentWalletError, match="helper not found"):
                AgentWallet._run_helper(["info"])

    def test_run_call_helper_raises_when_missing(self, tmp_path):
        """_run_call_helper raises AgentWalletError when casper_call.cjs is missing."""
        wallet = AgentWallet(
            key_path=tmp_path / "fake.pem",
            public_key="02" + "0" * 64,
            account_hash="account-hash-" + "0" * 64,
        )
        with patch("agents.agent_wallet._CALL_HELPER", tmp_path / "missing.cjs"):
            with pytest.raises(AgentWalletError, match="helper not found"):
                wallet._run_call_helper({"contract_hash": "x", "entry_point": "y", "args": {}})


# ---------------------------------------------------------------------------
# get_agent_wallet singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    """Verify the process-wide singleton behaves correctly."""

    def test_get_agent_wallet_returns_same_instance(self, temp_agent_wallet_path, monkeypatch):
        """get_agent_wallet() returns the same AgentWallet on repeated calls."""
        # Reset the singleton
        import agents.agent_wallet as aw_module

        monkeypatch.setattr(aw_module, "_WALLET_SINGLETON", None)
        monkeypatch.setenv("VAULTWATCH_AGENT_KEY_PATH", str(temp_agent_wallet_path))

        w1 = aw_module.get_agent_wallet()
        w2 = aw_module.get_agent_wallet()
        assert w1 is w2  # same instance
        assert w1.public_key.startswith("02")
