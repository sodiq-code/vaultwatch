"""E2E — REAL on-chain writes against Casper testnet.

Each test in this module submits a REAL stored-contract deploy via
``scripts/casper_call.cjs`` (casper-js-sdk v5 ``ContractCallBuilder`` +
``PrivateKey.fromPem``). Each deploy:

  * Is signed by the Account-2 deployer key (``secret_key.pem``).
  * Pays 5 CSPR gas (5_000_000_000 motes); ~90% is refunded on success.
  * Is verified on-chain via ``info_get_deploy`` — asserts
    ``Version2.error_message == None`` (= success).
  * Records the deploy hash in ``DEPLOYS_THIS_RUN`` for downstream read tests.

Owner-gated contracts
---------------------
6 of the 8 v1 contracts (AuditTrail, RiskOracle, SentinelAlertLog,
AgentBehaviorIndex, SentinelCredit, and the transfer_ownership entry point
on every contract) are OWNER-GATED: their write entry points call
``self.assert_owner()`` and revert with ``User(1)`` if the caller is not
the installer. The installer of those 6 v1 contracts is Account 1
(``0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7``)
— which has been DRAINED to 0 CSPR (verified live). The funded key
(Account 2) only owns:
  * RiskPolicyManager v2 (fresh install + v2 upgrade, PROOF.md §10.1)
  * SubscriberVault (fresh install, PROOF.md §11.2)

So this module's REAL writes target:
  * ``SentinelRegistry::register`` — public (no assert_owner); Account 2 can call
  * ``RiskPolicyManager(v2)::upgrade_policy`` — Account 2 owns the v2 package
  * ``SubscriberVault::open_vault`` — Account 2 owns the fresh install
  * ``SubscriberVault::top_up`` — Account 2 owns the fresh install

The owner-gated writes (``AuditTrail::record_finding``, ``RiskOracle::update_score``,
``AgentBehaviorIndex::record_decision``, ``SentinelAlertLog::log_alert``,
``SentinelCredit::deposit``) are documented in
``test_owner_gated_deploys_skipped.py`` as skipped — they require Account 1
to be refilled at https://testnet.cspr.live/tools/faucet before they can run.

Total gas across this module: ~4 deploys × ~0.5 CSPR = ~2 CSPR.
"""

from __future__ import annotations

import time
from typing import Any, Dict

import pytest

from tests.e2e.conftest import (
    E2E_RUN_ID,
    EXPLORER_URL,
    _e2e_address,
    rpc_call,
    submit_real_deploy,
    verify_deploy_success,
)

pytestmark = pytest.mark.e2e

# Module-level record of deploy hashes from this run. Downstream test modules
# (test_real_queries.py) import this dict to verify state written here.
DEPLOYS_THIS_RUN: Dict[str, str] = {}

# STABLE subscriber address for SubscriberVault::open_vault / top_up / get_balance.
# We use a CONSTANT (not time-based) so that test_real_deploys and
# test_real_queries can be run in SEPARATE pytest invocations (e.g. when
# debugging a single test) and still see the same on-chain state.
#
# open_vault's `accounts.set(&addr, ...)` is idempotent — re-running open_vault
# with the same address just overwrites the record (no revert). So this
# constant address is safe to reuse across runs.
SUBSCRIBER_VAULT_ADDRESS = "e2e_vaultwatch_stable_subscriber"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _explorer_link(deploy_hash: str) -> str:
    return f"{EXPLORER_URL}{deploy_hash}"


def _assert_deploy_verified(rpc_url: str, result: Dict[str, Any]) -> str:
    """Common post-deploy assertions + return the verified deploy hash."""
    assert result.get("success") is True, (
        f"deploy did not report success: {result}"
    )
    deploy_hash = result.get("deploy_hash", "")
    assert isinstance(deploy_hash, str) and len(deploy_hash) == 64, (
        f"bad deploy_hash: {deploy_hash!r}"
    )
    # Re-verify independently (defence in depth — the helper's own
    # verification could be bypassed by a bug; this is the e2e source of
    # truth).
    v2 = verify_deploy_success(rpc_url, deploy_hash)
    # Cost must be > 0 — proves the deploy actually executed on-chain.
    cost = int(v2.get("cost", 0))
    assert cost > 0, (
        f"deploy {deploy_hash} has zero cost — did it actually execute?"
    )
    return deploy_hash


# ---------------------------------------------------------------------------
# §1  SentinelRegistry::register  (REAL deploy — public entry point)
# ---------------------------------------------------------------------------


def test_sentinel_registry_register_real_deploy(rpc_url, signer_pem):
    """Submit a REAL ``SentinelRegistry::register`` deploy to Casper testnet.

    ``register`` is a PUBLIC entry point (no ``assert_owner``), so Account 2
    can call it. Each run uses a unique ``address`` arg so the
    subscriber_count monotonically increases — observable in
    test_real_queries.
    """
    args = {
        "address": {"type": "string", "value": _e2e_address("registry_subscriber")},
        "webhook_url": {"type": "string", "value": "https://hooks.vaultwatch.io/e2e"},
        "min_severity": {"type": "string", "value": "HIGH"},
        "timestamp": {"type": "u64", "value": str(int(time.time()))},
    }
    result = submit_real_deploy(
        contract_name="SentinelRegistry",
        entry_point="register",
        args=args,
        rpc_url=rpc_url,
        signer_pem=signer_pem,
    )
    deploy_hash = _assert_deploy_verified(rpc_url, result)
    DEPLOYS_THIS_RUN["sentinel_registry_register"] = deploy_hash
    print(f"\n  SentinelRegistry::register deploy: {_explorer_link(deploy_hash)}")


# ---------------------------------------------------------------------------
# §2  RiskPolicyManager(v2)::upgrade_policy  (REAL deploy — Account 2 owns v2)
# ---------------------------------------------------------------------------


def test_risk_policy_manager_v2_upgrade_policy_real_deploy(rpc_url, signer_pem):
    """Submit a REAL ``RiskPolicyManager::upgrade_policy`` deploy on the v2
    contract (Account-2-owned, PROOF.md §10.1).

    The original v1 RiskPolicyManager (contract hash ``1027cb2a…1d85``) was
    installed by Account 1 (now drained). Only Account 1 can call
    ``upgrade_policy`` on it (owner-gated). So this test calls
    ``upgrade_policy`` on the v2 RiskPolicyManager contract
    (``43fbabdf…3f8a``) which is the active version of the Account-2-owned
    package — and Account 2 is the funded deployer.
    """
    v2_rpm_hash = "43fbabdfa68dfe9a94e14ff2220d916ba785bb0615b84efd030d302c8adc3f8a"
    args = {
        "min_confidence_threshold": {"type": "u8", "value": "78"},
        "critical_score_threshold": {"type": "u8", "value": "88"},
        "high_score_threshold": {"type": "u8", "value": "72"},
        "medium_score_threshold": {"type": "u8", "value": "45"},
        "max_retry_count": {"type": "u8", "value": "3"},
        "safety_rejection_threshold": {"type": "u8", "value": "92"},
        "block_height": {"type": "u64", "value": "0"},
        "updated_by": {"type": "string", "value": f"e2e_upgrade_{E2E_RUN_ID}"},
    }
    result = submit_real_deploy(
        contract_hash=v2_rpm_hash,
        entry_point="upgrade_policy",
        args=args,
        rpc_url=rpc_url,
        signer_pem=signer_pem,
    )
    deploy_hash = _assert_deploy_verified(rpc_url, result)
    DEPLOYS_THIS_RUN["risk_policy_manager_upgrade_policy"] = deploy_hash
    print(f"\n  RiskPolicyManager(v2)::upgrade_policy deploy: {_explorer_link(deploy_hash)}")


# ---------------------------------------------------------------------------
# §3  SubscriberVault::open_vault  (REAL deploy — Account 2 owns fresh install)
# ---------------------------------------------------------------------------


def test_subscriber_vault_open_vault_real_deploy(rpc_url, signer_pem):
    """Submit a REAL ``SubscriberVault::open_vault`` deploy on the
    Account-2-owned fresh SubscriberVault (PROOF.md §11.2).

    ``open_vault`` is ``#[odra(payable)]`` — the deploy attaches real CSPR
    (the ``initial_deposit`` arg, 1 CSPR = 1_000_000_000 motes). The
    contract's ``assert_vault_owner()`` check passes because Account 2
    installed the fresh SubscriberVault and is therefore the vault owner.

    The deploy also creates the subscriber record (using a unique
    ``subscriber_address`` per run) — observable in
    test_real_queries.test_subscriber_vault_balance_after_open.
    """
    # Account-2-owned fresh SubscriberVault contract hash (PROOF.md §11.2).
    fresh_sv_hash = "0d41615944471f18c7ac75725901be7eeff26a0c168e1a3387db2449256b1f8c"
    args = {
        "subscriber_address": {"type": "string", "value": SUBSCRIBER_VAULT_ADDRESS},
        "initial_deposit": {"type": "u512", "value": "1000000000"},  # 1 CSPR
        "lock_blocks": {"type": "u64", "value": "43200"},  # 30 days @ ~16s blocks
        "auto_renew": {"type": "bool", "value": "false"},
        "monthly_spend_limit": {"type": "u512", "value": "10000000000"},  # 10 CSPR
        "current_block": {"type": "u64", "value": "0"},
    }
    result = submit_real_deploy(
        contract_hash=fresh_sv_hash,
        entry_point="open_vault",
        args=args,
        rpc_url=rpc_url,
        signer_pem=signer_pem,
        payment_motes=10_000_000_000,  # 10 CSPR — payable deploys need extra gas
    )
    deploy_hash = _assert_deploy_verified(rpc_url, result)
    DEPLOYS_THIS_RUN["subscriber_vault_open_vault"] = deploy_hash
    print(f"\n  SubscriberVault::open_vault deploy: {_explorer_link(deploy_hash)}")


# ---------------------------------------------------------------------------
# §4  SubscriberVault::top_up  (REAL deploy — Account 2 owns fresh install)
# ---------------------------------------------------------------------------


def test_subscriber_vault_top_up_real_deploy(rpc_url, signer_pem):
    """Submit a REAL ``SubscriberVault::top_up`` deploy on the Account-2-owned
    SubscriberVault. ``top_up`` is also ``#[odra(payable)]`` — attaches real
    CSPR (0.5 CSPR top-up)."""
    # Wait briefly so the open_vault deploy is committed before top_up tries
    # to read the subscriber record.
    time.sleep(2)
    fresh_sv_hash = "0d41615944471f18c7ac75725901be7eeff26a0c168e1a3387db2449256b1f8c"
    args = {
        "subscriber_address": {"type": "string", "value": SUBSCRIBER_VAULT_ADDRESS},
        "amount": {"type": "u512", "value": "500000000"},  # 0.5 CSPR
    }
    result = submit_real_deploy(
        contract_hash=fresh_sv_hash,
        entry_point="top_up",
        args=args,
        rpc_url=rpc_url,
        signer_pem=signer_pem,
        payment_motes=7_000_000_000,  # 7 CSPR — payable + state-write
    )
    deploy_hash = _assert_deploy_verified(rpc_url, result)
    DEPLOYS_THIS_RUN["subscriber_vault_top_up"] = deploy_hash
    print(f"\n  SubscriberVault::top_up deploy: {_explorer_link(deploy_hash)}")


# ---------------------------------------------------------------------------
# §5  Cross-check: each deploy's execution effects contain a Write transform
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "deploy_key",
    [
        "sentinel_registry_register",
        "risk_policy_manager_upgrade_policy",
        "subscriber_vault_open_vault",
        "subscriber_vault_top_up",
    ],
)
def test_deploy_produced_on_chain_writes(rpc_url, deploy_key):
    """Each deploy from §1-§4 must have produced at least one ``Write``
    transform in its execution effects — proving state was actually mutated
    on-chain (not just gas consumed).

    On Casper 2.x, ``execution_result.Version2.effects`` is a LIST of
    operation records (each ``{"key": ..., "kind": "Identity" | {"Write": {...}}``).
    We iterate the list and look for any ``Write`` operation.
    """
    if deploy_key not in DEPLOYS_THIS_RUN:
        pytest.skip(f"{deploy_key} did not run (upstream failure)")
    deploy_hash = DEPLOYS_THIS_RUN[deploy_key]
    result = rpc_call(rpc_url, "info_get_deploy", {"deploy_hash": deploy_hash})
    effects = (
        result.get("execution_info", {})
        .get("execution_result", {})
        .get("Version2", {})
        .get("effects", [])
    )
    assert isinstance(effects, list), (
        f"effects is not a list (got {type(effects).__name__}): {effects!r}"
    )
    # Collect the written-value type from each Write operation.
    write_value_types = set()
    for eff in effects:
        kind = eff.get("kind", {})
        if isinstance(kind, dict) and "Write" in kind:
            write_payload = kind["Write"]
            # The payload is a dict like {"CLValue": {...}} or
            # {"Account": {...}} or {"Contract": {...}} etc.
            if isinstance(write_payload, dict):
                write_value_types.update(write_payload.keys())
    assert write_value_types, (
        f"deploy {deploy_hash} produced 0 Write transforms — state was not "
        f"mutated. Effects: {effects}"
    )
    print(
        f"\n  {deploy_key}: {len(write_value_types)} Write value-type(s): "
        f"{sorted(write_value_types)}"
    )
