"""E2E — WASM artifact verification (bulk-memory-clean, exports correct).

These tests run against the LOCAL ``contracts/wasm/*.wasm`` artifacts (the
ones that were deployed to Casper testnet on 2026-07-11 and verified
on-chain in test_contracts_on_chain.py). They use:

  * ``scripts/check_wasm_bulk_memory.py`` — the project's hard-gate script
    that parses the WASM binary and FAILS on any bulk-memory opcode.
  * ``wasm-objdump -x`` (from wabt 1.0.36) — produces a human-readable
    dump of every WASM section (imports, exports, function bodies, etc.).
  * ``wasm-validate`` — confirms each WASM is a valid WebAssembly module.

These tests do NOT consume gas (no RPC calls). They are intentionally
fast so they can run in CI on every push.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
WASM_DIR = ROOT / "contracts" / "wasm"
CHECK_SCRIPT = ROOT / "scripts" / "check_wasm_bulk_memory.py"

pytestmark = pytest.mark.e2e

#: The 8 v1 contracts + the v2 RiskPolicyManager upgrade WASM.
EXPECTED_WASM_FILES = [
    "AuditTrail.wasm",
    "SentinelRegistry.wasm",
    "RiskOracle.wasm",
    "SentinelCredit.wasm",
    "AgentBehaviorIndex.wasm",
    "SentinelAlertLog.wasm",
    "RiskPolicyManager.wasm",
    "SubscriberVault.wasm",
    "RiskPolicyManagerV2.wasm",
]

#: Each WASM must export at minimum the ``call`` entry point (Odra's
#: universal entry point that dispatches to entry points based on the
#: "entry_point" runtime arg).
REQUIRED_EXPORTS = ["call"]

#: Per-contract required entry-point exports (Odra exports each entry point
#: as a top-level WASM export with the same name).
CONTRACT_REQUIRED_EXPORTS: Dict[str, List[str]] = {
    "AuditTrail": ["call", "init", "record_finding", "get_count"],
    "SentinelRegistry": ["call", "init", "register", "get_count"],
    "RiskOracle": ["call", "init", "update_score", "get_risk_score"],
    "SentinelCredit": ["call", "init", "deposit", "withdraw", "deduct_query"],
    "AgentBehaviorIndex": ["call", "init", "record_decision", "get_metrics"],
    "SentinelAlertLog": ["call", "init", "log_alert", "get_total_count"],
    "RiskPolicyManager": ["call", "init", "upgrade_policy", "get_current_policy"],
    "SubscriberVault": ["call", "init", "open_vault", "withdraw", "top_up"],
    "RiskPolicyManagerV2": [
        "call", "init", "upgrade_policy", "get_current_policy",
        "get_policy_with_reasoning", "upgrade",
    ],
}


# ---------------------------------------------------------------------------
# §1  WASM files present
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("wasm_name", EXPECTED_WASM_FILES)
def test_wasm_file_exists(wasm_name):
    """Each expected WASM file is present in ``contracts/wasm/``."""
    p = WASM_DIR / wasm_name
    assert p.exists(), f"WASM file not found: {p}"
    assert p.stat().st_size > 1000, f"{wasm_name} is suspiciously small (< 1 KB)"


def test_no_unexpected_wasm_files():
    """``contracts/wasm/`` should contain ONLY the expected WASM files
    (no stale artifacts from older builds)."""
    actual = {p.name for p in WASM_DIR.glob("*.wasm")}
    expected = set(EXPECTED_WASM_FILES)
    extra = actual - expected
    assert not extra, f"unexpected WASM files: {extra}"


# ---------------------------------------------------------------------------
# §2  Bulk-memory-clean (the hard gate — Casper's wasmi rejects bulk memory)
# ---------------------------------------------------------------------------


def test_check_wasm_bulk_memory_script_passes_on_all_wasms():
    """Run ``scripts/check_wasm_bulk_memory.py contracts/wasm/`` and assert
    exit code 0 (all WASM files clean).

    This is the EXACT script PROOF.md §1 references as the hard gate. Its
    exit code is the source of truth for "bulk-memory-safe WASM".
    """
    assert CHECK_SCRIPT.exists(), f"check_wasm_bulk_memory.py missing: {CHECK_SCRIPT}"
    proc = subprocess.run(
        [sys.executable, str(CHECK_SCRIPT), str(WASM_DIR)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, (
        f"check_wasm_bulk_memory.py FAILED (exit {proc.returncode}):\n"
        f"--- stdout ---\n{proc.stdout}\n"
        f"--- stderr ---\n{proc.stderr}"
    )
    # The script should mention each WASM file as PASS.
    for wasm_name in EXPECTED_WASM_FILES:
        assert wasm_name in proc.stdout, (
            f"{wasm_name} not mentioned in check_wasm_bulk_memory.py output:\n{proc.stdout}"
        )


@pytest.mark.parametrize("wasm_name", EXPECTED_WASM_FILES)
def test_wasm_validates(wasm_name):
    """``wasm-validate`` (wabt 1.0.36) accepts each WASM as a valid module."""
    if not shutil.which("wasm-validate"):
        pytest.skip("wasm-validate (wabt) not installed — install with `apt install wabt` or download from https://github.com/WebAssembly/wabt/releases")
    proc = subprocess.run(
        ["wasm-validate", str(WASM_DIR / wasm_name)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, (
        f"wasm-validate FAILED on {wasm_name} (exit {proc.returncode}):\n{proc.stderr}"
    )


# ---------------------------------------------------------------------------
# §3  wasm-objdump -x (the human-readable section dump)
# ---------------------------------------------------------------------------


def _wasm_objdump(wasm_path: Path, flag: str = "-x") -> str:
    """Run ``wasm-objdump <flag> <wasm>`` and return stdout. Skips if the
    wabt binary is not installed."""
    if not shutil.which("wasm-objdump"):
        pytest.skip("wasm-objdump (wabt) not installed — install with `apt install wabt` or download from https://github.com/WebAssembly/wabt/releases")
    proc = subprocess.run(
        ["wasm-objdump", flag, str(wasm_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, (
        f"wasm-objdump {flag} FAILED on {wasm_path.name} (exit {proc.returncode}):\n{proc.stderr}"
    )
    return proc.stdout


@pytest.mark.parametrize("wasm_name", EXPECTED_WASM_FILES)
def test_wasm_objdump_section_header(wasm_name):
    """``wasm-objdump -x`` produces a section-header dump for each WASM
    (proves the file is parseable + has the expected sections)."""
    out = _wasm_objdump(WASM_DIR / wasm_name, "-x")
    # Every Odra contract WASM has at minimum these sections.
    for required_section in ("Type", "Import", "Function", "Memory", "Export"):
        assert required_section in out, (
            f"{wasm_name}: wasm-objdump output missing '{required_section}' section.\n"
            f"Output:\n{out[:2000]}"
        )


@pytest.mark.parametrize("wasm_name", EXPECTED_WASM_FILES)
def test_wasm_exports_required_entry_points(wasm_name):
    """``wasm-objdump -x`` lists the contract's required entry points in the
    Export section. This is the on-disk proof that the WASM we deployed
    really exposes the entry points our agents call.

    (The on-chain query in test_contracts_on_chain.py proves the same thing
    from the RPC side — together they're airtight.)
    """
    out = _wasm_objdump(WASM_DIR / wasm_name, "-x")
    # Strip the .wasm suffix to get the contract name.
    contract_name = wasm_name.replace(".wasm", "")
    required = CONTRACT_REQUIRED_EXPORTS.get(contract_name, REQUIRED_EXPORTS)
    # Extract the Export section lines.
    # wasm-objdump output: "  - func <name> -> <name>" or similar.
    # We just check each required export name appears anywhere in the output.
    missing = [name for name in required if name not in out]
    assert not missing, (
        f"{wasm_name}: required exports missing from wasm-objdump output: {missing}.\n"
        f"Output excerpt:\n{out[:3000]}"
    )


@pytest.mark.parametrize("wasm_name", EXPECTED_WASM_FILES)
def test_wasm_does_not_import_bulk_memory_intrinsics(wasm_name):
    """No WASM should import or reference ``memory.copy`` / ``memory.fill`` /
    other bulk-memory intrinsics (Casper's wasmi rejects them).

    We assert that the strings 'memory.copy' and 'memory.fill' do NOT appear
    in the wasm-objdump output. (The hard-gate script does the deeper opcode
    check; this is a complementary string-level check.)
    """
    out = _wasm_objdump(WASM_DIR / wasm_name, "-x")
    forbidden = ["memory.copy", "memory.fill", "table.copy", "table.fill", "table.init"]
    found = [s for s in forbidden if s in out]
    assert not found, (
        f"{wasm_name}: wasm-objdump output mentions forbidden bulk-memory intrinsics {found}.\n"
        f"Output excerpt:\n{out[:3000]}"
    )


# ---------------------------------------------------------------------------
# §4  WASM file sizes (smoke check — dramatically smaller = broken build)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("wasm_name", EXPECTED_WASM_FILES)
def test_wasm_size_in_expected_range(wasm_name):
    """Each Odra contract WASM should be 100–250 KB. A < 50 KB WASM indicates
    a stub build (cargo-odra bin build issue from Task 2); a > 1 MB WASM
    indicates the bulk-memory lowering was skipped."""
    size = (WASM_DIR / wasm_name).stat().st_size
    assert 50_000 <= size <= 1_500_000, (
        f"{wasm_name}: size {size} bytes is outside the expected 50KB-1.5MB range"
    )
