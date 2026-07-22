"""E2E — Casper testnet network liveness + deployer account state.

These tests run against the REAL Casper testnet (`casper-test`). They use
ONLY read-only RPC calls (``info_get_status``, ``state_get_account_info``,
``state_get_balance``) — no gas is consumed.

Verifies:
  * RPC endpoint is reachable and serves Casper 2.x (api_version >= 2.0.0).
  * ``chainspec_name == 'casper-test'``.
  * Deployer account (Account 2) is funded above the e2e gas floor.
  * Deployer account has the 4 named keys installed by the v1 contract
    deploys + the v2 RiskPolicyManager upgrade (PROOF.md §1, §10).
"""

from __future__ import annotations

import pytest

from tests.e2e.conftest import (
    CHAIN_NAME,
    DEPLOYER_ACCOUNT_HASH,
    DEPLOYER_PUBLIC_KEY,
    rpc_call,
)

pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# §1  Network liveness
# ---------------------------------------------------------------------------


def test_rpc_endpoint_reachable(casper_node_status):
    """``info_get_status`` returns a non-empty result."""
    assert casper_node_status, "info_get_status returned an empty result"


def test_chainspec_is_casper_test(casper_node_status):
    """The RPC endpoint must be the public Casper testnet, not mainnet."""
    assert casper_node_status["chainspec_name"] == CHAIN_NAME


def test_api_version_is_casper_2x(casper_node_status):
    """Casper 2.x is required — the on-chain contracts use the
    ``add_contract_version`` 4-arg form introduced in Casper 2.x (the v2
    upgrade PROOF.md §10 depends on it)."""
    api_version = casper_node_status.get("api_version", "")
    assert api_version.startswith("2."), (
        f"expected Casper 2.x api_version, got {api_version!r} — "
        "the public testnet node may have rolled back to 1.x."
    )


def test_build_version_present(casper_node_status):
    """``build_version`` is non-empty (smoke check that the node is healthy)."""
    assert casper_node_status.get("build_version"), "build_version missing"


def test_node_has_peers(casper_node_status):
    """A healthy testnet node reports > 0 peers (otherwise it cannot
    propagate our deploys)."""
    peers = casper_node_status.get("peers", [])
    assert len(peers) > 0, "node has 0 peers — deploys will not propagate"


# ---------------------------------------------------------------------------
# §2  Deployer account state
# ---------------------------------------------------------------------------


def test_deployer_account_exists_on_chain(deployer_account):
    """The deployer account (Account 2) must exist on Casper testnet."""
    assert deployer_account.get("account_hash") == DEPLOYER_ACCOUNT_HASH, (
        f"unexpected account hash: {deployer_account.get('account_hash')!r}"
    )


def test_deployer_account_has_associated_key(deployer_account):
    """The deployer public key must be in ``associated_keys`` with weight 1
    (so it can sign deploys under the default action_thresholds)."""
    keys = deployer_account.get("associated_keys", [])
    assert any(
        k.get("account_hash") == DEPLOYER_ACCOUNT_HASH and k.get("weight", 0) >= 1
        for k in keys
    ), f"deployer public key {DEPLOYER_PUBLIC_KEY} not in associated_keys: {keys}"


def test_deployer_balance_above_gas_floor(deployer_balance_cspr, request):
    """The deployer balance must be above the e2e gas floor.

    Each write deploy costs ~0.5 CSPR (5 CSPR payment, ~90% refunded on
    success). The suite submits ~8 deploys, so ~5 CSPR total gas. The floor
    (default 100 CSPR) gives plenty of headroom for repeated runs.
    """
    floor = request.config.getoption("--e2e-min-balance-cspr")
    assert deployer_balance_cspr >= floor, (
        f"deployer balance {deployer_balance_cspr} CSPR is below the e2e floor "
        f"of {floor} CSPR. Refill at https://testnet.cspr.live/tools/faucet, "
        "or lower the floor via --e2e-min-balance-cspr."
    )


def test_deployer_has_named_keys_for_contracts(deployer_account):
    """The deployer account must own the 8 contract package hashes as named
    keys (proves the v1 contract installs really happened from this account).

    Account 2 owns the v1 RiskPolicyManager + SubscriberVault packages
    (plus their access tokens). Account 1 (drained) owned the original 8
    packages. This test only asserts the Account-2-owned named keys.
    """
    named_keys = {nk["name"] for nk in deployer_account.get("named_keys", [])}
    # Account 2 owns the v2 RiskPolicyManager + the fresh SubscriberVault.
    expected_ownerships = {
        "risk_policy_manager_package_hash",
        "subscriber_vault_package_hash",
    }
    missing = expected_ownerships - named_keys
    assert not missing, (
        f"deployer missing expected named keys: {missing}. "
        f"Present named keys: {sorted(named_keys)}"
    )


def test_deployer_action_thresholds_default(deployer_account):
    """Default action thresholds (deployment=1, key_management=1) — so the
    single deployer key alone is sufficient to install contracts and manage
    keys. Required for the e2e deploys to succeed."""
    thresholds = deployer_account.get("action_thresholds", {})
    assert thresholds.get("deployment", 0) <= 1, (
        f"deployment threshold too high for single-key signer: {thresholds}"
    )
    assert thresholds.get("key_management", 0) <= 1, (
        f"key_management threshold too high for single-key signer: {thresholds}"
    )


# ---------------------------------------------------------------------------
# §3  State root hash + a fresh block
# ---------------------------------------------------------------------------


def test_state_root_hash_is_fresh(rpc_url, state_root_hash):
    """The state root hash fixture is non-empty and refers to a recent block.

    Re-fetches the deployer account via ``query_global_state`` with the
    fixture's SRH as the explicit state identifier, to prove the SRH is
    real and points at a state where the deployer exists.
    """
    result = rpc_call(
        rpc_url,
        "query_global_state",
        {
            "state_identifier": {"StateRootHash": state_root_hash},
            "key": DEPLOYER_ACCOUNT_HASH,
        },
    )
    # query_global_state returns stored_value.Account for account-hash- keys.
    account = result.get("stored_value", {}).get("Account", {})
    assert account.get("account_hash") == DEPLOYER_ACCOUNT_HASH, (
        f"state root hash {state_root_hash} did not resolve the deployer account: {result}"
    )


def test_block_height_advancing(rpc_url):
    """Two consecutive ``info_get_status`` calls return different
    ``last_added_block_info.height`` values (chain is producing blocks)."""
    s1 = rpc_call(rpc_url, "info_get_status", {})
    h1 = s1.get("last_added_block_info", {}).get("height", 0)
    # Wait briefly for at least one new block (testnet block time ~ 16s).
    import time
    time.sleep(2)
    s2 = rpc_call(rpc_url, "info_get_status", {})
    h2 = s2.get("last_added_block_info", {}).get("height", 0)
    assert h2 >= h1, (
        f"block height went backwards: {h1} -> {h2} (chain stalled or forked)"
    )
