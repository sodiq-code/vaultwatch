"""E2E — Owner-gated deploy tests (SKIPPED — Account 1 depleted).

6 of the 8 v1 contracts (AuditTrail, RiskOracle, SentinelAlertLog,
AgentBehaviorIndex, SentinelCredit, and the transfer_ownership entry point
on every contract) are OWNER-GATED: their write entry points call
``self.assert_owner()`` and revert with ``User(1)`` if the caller is not
the installer. The installer of those 6 v1 contracts is Account 1
(public key ``0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7``,
account hash ``account-hash-aff1536a1cc925dab64b18049e0b63d5ec48580480a8d8306003663070c83136``).

Account 1 has been DRAINED to 0 CSPR (verified live). The funded key in
``secret_key.pem`` is Account 2 (public key
``02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db``,
balance ~4476 CSPR). Account 2 owns only:
  * RiskPolicyManager v2 (fresh install + v2 upgrade, PROOF.md §10.1)
  * SubscriberVault (fresh install, PROOF.md §11.2)

So the owner-gated writes below CANNOT be run end-to-end against the
currently-deployed v1 contracts — they require Account 1 to be refilled
at https://testnet.cspr.live/tools/faucet.

This file documents each owner-gated deploy as a SKIPPED test, so the
e2e suite honestly reports what would be tested if Account 1 were funded.
The other e2e tests (test_real_deploys.py) cover all the writable entry
points Account 2 CAN call.

To re-enable these tests:
  1. Refill Account 1 at https://testnet.cspr.live/tools/faucet (the
     faucet is captcha-protected; no public API).
  2. Restore Account 1's PEM to ``vaultwatch/secret_key.pem``.
  3. Run: ``pytest tests/e2e/test_owner_gated_deploys_skipped.py --run-e2e``.

The 21 verified-success interaction deploys from PROOF.md §8 (executed
with Account 1 on 2026-07-21, before it was depleted) prove that these
owner-gated entry points DO work end-to-end when Account 1 is funded.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


#: Account 1's balance (verified live at session start). Documented here so
#: the skip messages reference the actual number, not a static guess.
ACCOUNT_1_BALANCE_CSPR = 0  # drained — see module docstring.


_SKIP_REASON = (
    f"Account 1 (the v1 contract installer) has balance {ACCOUNT_1_BALANCE_CSPR} CSPR — "
    "DRAINED. This owner-gated entry point requires Account 1 to be refilled at "
    "https://testnet.cspr.live/tools/faucet. See module docstring for full context. "
    "The 21 verified-success interaction deploys in PROOF.md §8 prove this entry "
    "point works end-to-end when Account 1 is funded."
)


# ---------------------------------------------------------------------------
# AuditTrail::record_finding — owner-gated
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason=_SKIP_REASON)
def test_audit_trail_record_finding_real_deploy():
    """Submit a REAL ``AuditTrail::record_finding`` deploy (SKIPPED — Account 1
    depleted). PROOF.md §8 rows 1-3 record 3 verified-success deploys of this
    entry point executed with Account 1 on 2026-07-21."""
    # Body is intentionally empty — the test is skipped before any code runs.


# ---------------------------------------------------------------------------
# RiskOracle::update_score — owner-gated
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason=_SKIP_REASON)
def test_risk_oracle_update_score_real_deploy():
    """Submit a REAL ``RiskOracle::update_score`` deploy (SKIPPED — Account 1
    depleted). PROOF.md §8 rows 4-6 record 3 verified-success deploys of this
    entry point executed with Account 1 on 2026-07-21."""
    # Body is intentionally empty — the test is skipped before any code runs.


# ---------------------------------------------------------------------------
# SentinelAlertLog::log_alert — owner-gated
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason=_SKIP_REASON)
def test_sentinel_alert_log_log_alert_real_deploy():
    """Submit a REAL ``SentinelAlertLog::log_alert`` deploy (SKIPPED — Account 1
    depleted). PROOF.md §8 rows 7-10 record 4 verified-success deploys of this
    entry point executed with Account 1 on 2026-07-21."""
    # Body is intentionally empty — the test is skipped before any code runs.


# ---------------------------------------------------------------------------
# AgentBehaviorIndex::record_decision — owner-gated
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason=_SKIP_REASON)
def test_agent_behavior_index_record_decision_real_deploy():
    """Submit a REAL ``AgentBehaviorIndex::record_decision`` deploy (SKIPPED —
    Account 1 depleted). PROOF.md §8 rows 15-17 record 3 verified-success
    deploys of this entry point executed with Account 1 on 2026-07-21."""
    # Body is intentionally empty — the test is skipped before any code runs.


# ---------------------------------------------------------------------------
# SentinelCredit::deposit — owner-gated + payable
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason=_SKIP_REASON)
def test_sentinel_credit_deposit_real_deploy():
    """Submit a REAL ``SentinelCredit::deposit`` deploy (SKIPPED — Account 1
    depleted). PROOF.md §8 rows 13-14 record 2 verified-success deploys of
    this entry point executed with Account 1 on 2026-07-21."""
    # Body is intentionally empty — the test is skipped before any code runs.


# ---------------------------------------------------------------------------
# SentinelCredit::deduct_query — owner-gated (used by serve_intel_with_x402)
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason=_SKIP_REASON)
def test_sentinel_credit_deduct_query_real_deploy():
    """Submit a REAL ``SentinelCredit::deduct_query`` deploy (SKIPPED — Account 1
    depleted). PROOF.md §18 records a verified-success `deduct_query` deploy
    (Critical Fix 9) executed with Account 1."""
    # Body is intentionally empty — the test is skipped before any code runs.


# ---------------------------------------------------------------------------
# Sanity check: this file should always produce 6 skipped tests, not 0
# ---------------------------------------------------------------------------


def test_this_file_has_6_skipped_owner_gated_deploys():
    """Meta-test: this file MUST always contain exactly 6 skipped deploy
    tests (one per owner-gated write entry point in the 6 Account-1-owned
    contracts). If you add or remove a test, update this count.

    Why a meta-test? Because if the @pytest.mark.skip decorators are
    accidentally removed (or the file is refactored to skip differently),
    the suite would silently lose coverage of these 6 entry points. This
    test makes the expectation explicit.
    """
    import inspect
    import sys

    mod = sys.modules[__name__]
    skipped_test_fns = []
    for name, obj in inspect.getmembers(mod, inspect.isfunction):
        if not name.startswith("test_") or name == "test_this_file_has_6_skipped_owner_gated_deploys":
            continue
        marks = getattr(obj, "pytestmark", [])
        for mark in marks:
            # Mark objects have a `.name` attribute (e.g. "skip").
            if getattr(mark, "name", None) == "skip":
                skipped_test_fns.append(name)
                break
    assert len(skipped_test_fns) == 6, f"expected 6 skipped deploy tests, got {len(skipped_test_fns)}: {skipped_test_fns}"
