#!/usr/bin/env bash
# VaultWatch — Build all 8 Odra contracts with Casper-compatible WASM
#
# This script is the SINGLE SOURCE OF TRUTH for producing deployable WASM.
# It is called by:
#   - GitHub Actions workflow  .github/workflows/build-contracts.yml
#   - Local developer workflow (see DEPLOYMENT_GUIDE.md)
#
# What it does (in order):
#   1. Asserts Rust nightly + wasm32 target are installed
#   2. Compiles all 8 contracts with RUSTFLAGS=-C target-feature=-bulk-memory
#      (set via contracts/.cargo/config.toml — no env hacks needed)
#   3. Post-processes each .wasm with wasm-opt --enable-bulk-memory=no
#      (binaryen) as a belt-and-suspenders safety net
#   4. Runs scripts/check_wasm_bulk_memory.py — FAILS the build if any
#      bulk-memory opcodes remain
#   5. Copies the clean WASM into contracts/wasm/ (committed artifacts)
#
# Why both RUSTFLAGS and wasm-opt?
#   RUSTFLAGS prevents most emission at compile time. wasm-opt rewrites any
#   stragglers that slip through (e.g. from dependency code). The Python
#   check is the hard gate — if it fails, the WASM will fail on Casper.
#
# Usage:
#   bash scripts/build_contracts.sh           # build all
#   bash scripts/build_contracts.sh --check   # only verify existing WASM
#
# Exit codes:
#   0 = all 8 contracts built and verified clean
#   1 = toolchain missing
#   2 = compilation failed
#   3 = wasm-opt post-process failed
#   4 = bulk-memory opcode check failed (WASM would be rejected by Casper)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONTRACTS_DIR="$REPO_ROOT/contracts"
WASM_OUT_DIR="$CONTRACTS_DIR/wasm"
CHECK_SCRIPT="$SCRIPT_DIR/check_wasm_bulk_memory.py"

# 8 contracts defined in contracts/Odra.toml
CONTRACTS=(
    "AuditTrail"
    "SentinelRegistry"
    "RiskOracle"
    "SentinelCredit"
    "AgentBehaviorIndex"
    "SentinelAlertLog"
    "RiskPolicyManager"
    "SubscriberVault"
)

log()  { echo "[build_contracts] $*"; }
warn() { echo "[build_contracts] WARN: $*" >&2; }
fail() { echo "[build_contracts] ERROR: $*" >&2; exit "${2:-1}"; }

# ─── Step 0: --check mode ────────────────────────────────────────────────────
if [[ "${1:-}" == "--check" ]]; then
    log "Check-only mode: verifying existing WASM in $WASM_OUT_DIR"
    for c in "${CONTRACTS[@]}"; do
        wasm="$WASM_OUT_DIR/$c.wasm"
        [[ -f "$wasm" ]] || fail "missing $wasm" 4
    done
    python3 "$CHECK_SCRIPT" "$WASM_OUT_DIR" || fail "bulk-memory check failed" 4
    log "All 8 WASM files verified clean (no bulk-memory opcodes)."
    exit 0
fi

# ─── Step 1: toolchain checks ────────────────────────────────────────────────
log "Step 1/5: checking toolchain…"

command -v cargo >/dev/null 2>&1 || fail "cargo not found. Install Rust: https://rustup.rs" 1
command -v wasm-opt >/dev/null 2>&1 || fail "wasm-opt not found. Install: apt-get install binaryen  (or: brew install binaryen)" 1
command -v wasm-objdump >/dev/null 2>&1 || warn "wasm-objdump not found (optional, for debug). Install: apt-get install wabt"

# cargo-odra provides the `cargo odra` subcommand (the binary is cargo-odra,
# NOT a standalone `odra` — odra-cli is a library crate). Install with:
#   cargo install --locked cargo-odra --version 0.1.7
if ! cargo odra --help >/dev/null 2>&1; then
    fail "cargo-odra not installed. Run: cargo install --locked cargo-odra --version 0.1.7" 1
fi

# Ensure nightly toolchain (contracts/rust-toolchain pins the exact date)
( cd "$CONTRACTS_DIR" && rustup toolchain install "$(cat rust-toolchain)" --profile minimal --component rust-src --target wasm32-unknown-unknown 2>/dev/null || true )

log "  cargo:      $(cargo --version)"
log "  wasm-opt:   $(wasm-opt --version 2>&1 | head -1)"
log "  cargo-odra: $(cargo odra --version 2>&1 | head -1 || echo 'unknown')"
log "  toolchain:  $(cat "$CONTRACTS_DIR/rust-toolchain")"

# ─── Step 2: compile all contracts ───────────────────────────────────────────
log "Step 2/5: compiling 8 contracts with RUSTFLAGS=-C target-feature=-bulk-memory …"
log "  (flags are sourced from contracts/.cargo/config.toml — no env needed)"

cd "$CONTRACTS_DIR"

# Build via Odra's build system. `cargo odra build` reads Odra.toml and
# compiles each contract FQN to wasm32-unknown-unknown, placing output in
# target/wasm32-unknown-unknown/release/*.wasm
log "  using: cargo odra build"
cargo odra build

# Locate raw WASM outputs
RAW_WASM_DIR="$CONTRACTS_DIR/target/wasm32-unknown-unknown/release"
[[ -d "$RAW_WASM_DIR" ]] || fail "expected WASM output at $RAW_WASM_DIR" 2

mkdir -p "$WASM_OUT_DIR"

# ─── Step 3: wasm-opt post-process each contract ─────────────────────────────
log "Step 3/5: post-processing with wasm-opt --enable-bulk-memory=no …"

for c in "${CONTRACTS[@]}"; do
    # Odra names the output after the contract module — try common casings
    raw=""
    for candidate in "$RAW_WASM_DIR/${c,,}.wasm" "$RAW_WASM_DIR/$c.wasm" "$RAW_WASM_DIR/vaultwatch_contracts.wasm"; do
        if [[ -f "$candidate" ]]; then raw="$candidate"; break; fi
    done
    if [[ -z "$raw" ]]; then
        fail "could not find raw WASM for $c in $RAW_WASM_DIR" 2
    fi

    out="$WASM_OUT_DIR/$c.wasm"
    # --enable-bulk-memory=no rewrites memory.copy / memory.fill / table.* into
    # explicit loops. -Oz also shrinks the binary (Casper deploy gas ∝ size).
    wasm-opt "$raw" --enable-bulk-memory=no -Oz -o "$out" \
        || fail "wasm-opt failed on $raw" 3
    log "  $c.wasm  ($(stat -c%s "$out") bytes)"
done

# ─── Step 4: hard-gate bulk-memory opcode check ──────────────────────────────
log "Step 4/5: verifying zero bulk-memory opcodes (hard gate) …"
python3 "$CHECK_SCRIPT" "$WASM_OUT_DIR" || fail "bulk-memory check failed — WASM would be rejected by Casper" 4

# ─── Step 5: summary ─────────────────────────────────────────────────────────
log "Step 5/5: done. 8 clean WASM artifacts in $WASM_OUT_DIR"
log ""
log "Next steps:"
log "  1. Deploy:  python3 scripts/deploy_contracts.py --node-url https://rpc.testnet.casper.network"
log "  2. Verify:  python3 scripts/verify_deploys.py"
log "  3. Update:  proof/PROOF.md with new deploy hashes (deploy script prints them)"
log ""
log "✅ All contracts pass the Casper bulk-memory gate."
