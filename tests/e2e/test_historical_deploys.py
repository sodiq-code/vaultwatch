"""E2E — All 29+ historical deploy hashes still resolve to Success on Casper
testnet (or are gracefully recognised as pruned).

These tests verify the deploy hashes recorded in PROOF.md §1 (8 contract
installs), §8 (21 verified interactions), §10.1 (6 upgrade lifecycle), and
§11.2 (1 x402 payment) are STILL on-chain with ``Version2.error_message == None``
(success). This proves the on-chain footprint claimed in the proof is durable.

Casper testnet PRUNES deploy history after ~7 days to bound state growth.
The 8 contract installs from 2026-07-11 are older than that and may have
been pruned. Those tests use ``verify_deploy_exists_or_pruned`` which
returns ``None`` for pruned deploys — the test then skips with a clear
message rather than failing (the contract STATE installed by the deploy
remains verifiable via ``query_global_state`` — see
test_contracts_on_chain.py).

Each test issues only read-only ``info_get_deploy`` RPC calls — no gas.
"""

from __future__ import annotations

import pytest

from tests.e2e.conftest import (
    HISTORICAL_INTERACTION_HASHES,
    INSTALL_DEPLOY_HASHES,
    UPGRADE_DEPLOY_HASHES,
    rpc_call,
    verify_deploy_exists_or_pruned,
)

pytestmark = pytest.mark.e2e

#: The Critical-Fix-3 x402 payment deploy (PROOF.md §11.2).
X402_PAYMENT_DEPLOY_HASH = "0588e143d15eebb7004c23052cd3727d7b87c3b120981184eff5abc9b33f5e2c"


# ---------------------------------------------------------------------------
# §1  Contract install deploys (8 hashes from transaction_hashes_live.json —
#     PROOF.md §1). These are >7 days old and MAY have been pruned.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "contract_name,deploy_hash",
    list(INSTALL_DEPLOY_HASHES.items()),
)
def test_contract_install_deploy_still_successful_or_pruned(rpc_url, contract_name, deploy_hash):
    """Each of the 8 v1 contract install deploys (2026-07-11) is EITHER:

      * STILL on-chain with a Success execution result (typical for recent
        installs), OR
      * Pruned from testnet history (typical for installs >7 days old). In
        this case the test SKIPS — the contract STATE installed by the
        deploy remains verifiable via query_global_state (see
        test_contracts_on_chain.py), so the proof claim still holds.

    This pruning-tolerance is necessary because Casper testnet prunes deploy
    history to bound state growth, but contract state (the URef-backed
    dictionary entries) is permanent.
    """
    v2 = verify_deploy_exists_or_pruned(rpc_url, deploy_hash)
    if v2 is None:
        pytest.skip(
            f"{contract_name} install deploy {deploy_hash} has been pruned from testnet "
            "history (Casper testnet prunes deploys older than ~7 days). The contract "
            "STATE installed by this deploy is still verifiable via query_global_state — "
            "see test_contracts_on_chain.py."
        )
    assert int(v2.get("cost", 0)) > 0, (
        f"{contract_name} install {deploy_hash} has zero cost — wasn't actually executed?"
    )


# ---------------------------------------------------------------------------
# §2  Interaction deploys (21 hashes from proof/interaction_hashes.json —
#     PROOF.md §8). These are recent (2026-07-21) and should all exist.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("deploy_hash", list(HISTORICAL_INTERACTION_HASHES))
def test_interaction_deploy_still_successful(rpc_url, deploy_hash):
    """Each of the 21 verified interaction deploys (2026-07-21) is STILL
    on-chain with a Success execution result.

    These are recent enough that testnet pruning should NOT have removed
    them yet (as of late July 2026). If any are missing, that's a real
    regression in the proof's claims.
    """
    v2 = verify_deploy_exists_or_pruned(rpc_url, deploy_hash)
    if v2 is None:
        pytest.fail(
            f"interaction deploy {deploy_hash} is missing from testnet — this is a "
            "real regression. The proof (PROOF.md §8) claims it was verified-success "
            "on 2026-07-21. If the testnet pruned it, the proof's table needs updating."
        )
    assert int(v2.get("cost", 0)) > 0, (
        f"interaction deploy {deploy_hash} has zero cost — wasn't actually executed?"
    )


# ---------------------------------------------------------------------------
# §3  Aggregate counts (sanity check that the proof's "29 hashes" claim holds)
# ---------------------------------------------------------------------------


def test_install_deploy_count_is_8():
    """PROOF.md §1 lists exactly 8 contract install deploys."""
    assert len(INSTALL_DEPLOY_HASHES) == 8, (
        f"expected 8 install deploys, got {len(INSTALL_DEPLOY_HASHES)}. "
        "transaction_hashes_live.json may have been modified."
    )


def test_interaction_deploy_count_is_21():
    """PROOF.md §8 lists exactly 21 verified interaction deploys."""
    assert len(HISTORICAL_INTERACTION_HASHES) == 21, (
        f"expected 21 interaction deploys, got {len(HISTORICAL_INTERACTION_HASHES)}. "
        "proof/interaction_hashes.json may have been modified."
    )


def test_total_historical_deploy_count_is_29():
    """PROOF.md §8 headline: 'Total: 29 on-chain TX hashes (8 contract deploys
    + 21 verified interactions)'. This test asserts that arithmetic still
    holds (i.e. no hash was accidentally added or removed from the JSON
    files)."""
    total = len(INSTALL_DEPLOY_HASHES) + len(HISTORICAL_INTERACTION_HASHES)
    assert total == 29, f"expected 29 total historical deploys, got {total}"


def test_all_historical_hashes_are_unique():
    """All 29 historical deploy hashes must be distinct (a duplicate would
    mean the proof's table is double-counting)."""
    all_hashes = list(INSTALL_DEPLOY_HASHES.values()) + list(HISTORICAL_INTERACTION_HASHES)
    assert len(set(all_hashes)) == len(all_hashes), (
        f"duplicate deploy hashes detected: {len(all_hashes) - len(set(all_hashes))} dupes"
    )


def test_all_historical_hashes_are_64_char_hex():
    """All historical deploy hashes must be 64-char lowercase hex (a
    malformed hash would fail info_get_deploy with a confusing error)."""
    all_hashes = list(INSTALL_DEPLOY_HASHES.values()) + list(HISTORICAL_INTERACTION_HASHES)
    for h in all_hashes:
        assert len(h) == 64, f"hash {h!r} is {len(h)} chars (expected 64)"
        assert all(c in "0123456789abcdef" for c in h), (
            f"hash {h!r} contains non-hex characters"
        )


# ---------------------------------------------------------------------------
# §4  Upgrade deploys (Critical Fix 2 — PROOF.md §10.1)
# ---------------------------------------------------------------------------


def test_upgrade_lifecycle_deploy_count_is_6():
    """PROOF.md §10.1 lists exactly 6 upgrade-lifecycle deploys."""
    assert len(UPGRADE_DEPLOY_HASHES) == 6, (
        f"expected 6 upgrade deploys, got {len(UPGRADE_DEPLOY_HASHES)}. "
        "proof/upgrade_hashes.json may have been modified."
    )


@pytest.mark.parametrize("deploy_hash", list(UPGRADE_DEPLOY_HASHES))
def test_upgrade_lifecycle_deploy_still_successful(rpc_url, deploy_hash):
    """Each of the 6 Critical-Fix-2 upgrade deploys is STILL on-chain with
    Success execution result (PROOF.md §10.1).

    These deploys are from 2026-07-21 — recent enough that testnet pruning
    should not have removed them.
    """
    v2 = verify_deploy_exists_or_pruned(rpc_url, deploy_hash)
    if v2 is None:
        pytest.fail(
            f"upgrade deploy {deploy_hash} is missing from testnet — this is a real "
            "regression. PROOF.md §10.1 claims it was verified-success on 2026-07-21."
        )
    assert int(v2.get("cost", 0)) > 0


# ---------------------------------------------------------------------------
# §5  x402 payment deploy (Critical Fix 3 — PROOF.md §11.2)
# ---------------------------------------------------------------------------


def test_x402_payment_deploy_still_successful(rpc_url):
    """The Critical-Fix-3 x402 payment deploy (PROOF.md §11.2) is STILL
    on-chain with Success execution result."""
    v2 = verify_deploy_exists_or_pruned(rpc_url, X402_PAYMENT_DEPLOY_HASH)
    if v2 is None:
        pytest.fail(
            f"x402 payment deploy {X402_PAYMENT_DEPLOY_HASH} is missing from testnet — "
            "PROOF.md §11.2 claims it was verified-success on 2026-07-21."
        )
    assert int(v2.get("cost", 0)) > 0


# ---------------------------------------------------------------------------
# §6  Each historical deploy's effects are non-empty (where still queryable)
# ---------------------------------------------------------------------------


def test_audit_trail_install_deploy_has_execution_effects(rpc_url):
    """The AuditTrail install deploy's execution effects (if still on-chain)
    must contain at least one Write transform of type Contract or
    ContractPackage (proves the contract was actually installed, not just
    that the deploy was accepted).

    If the install deploy has been pruned, the test SKIPS — the contract
    itself remains queryable (test_contracts_on_chain.py).
    """
    # Use the AuditTrail install hash from the live JSON.
    deploy_hash = INSTALL_DEPLOY_HASHES.get("AuditTrail", "")
    assert deploy_hash, "AuditTrail install deploy hash missing from transaction_hashes_live.json"
    v2 = verify_deploy_exists_or_pruned(rpc_url, deploy_hash)
    if v2 is None:
        pytest.skip(
            f"AuditTrail install deploy {deploy_hash} has been pruned from testnet. "
            "The contract itself remains queryable — see test_contracts_on_chain.py."
        )
    # Reach into the raw deploy result for the effects. The
    # verify_deploy_exists_or_pruned helper returns the Version2 result
    # (which is execution_result.Version2). We need the sibling `effects`
    # field too — re-fetch.
    result = rpc_call(rpc_url, "info_get_deploy", {"deploy_hash": deploy_hash})
    effects = (
        result.get("execution_info", {})
        .get("execution_result", {})
        .get("Version2", {})
        .get("effects", {})
    )
    transforms = effects.get("transforms", [])
    assert len(transforms) > 0, (
        f"install deploy {deploy_hash} has 0 execution-effect transforms — "
        "the contract was not actually installed."
    )
    # The install must produce at least one Write of type Contract or ContractPackage.
    write_kinds = {
        t.get("transform", {}).get("Write", {}).get("stored_value", {}).get("type")
        for t in transforms
        if "Write" in t.get("transform", {})
    }
    write_kinds.discard(None)
    assert "ContractPackage" in write_kinds or "Contract" in write_kinds, (
        f"install deploy {deploy_hash} did not write a Contract/ContractPackage entity. "
        f"Write kinds: {write_kinds}"
    )
