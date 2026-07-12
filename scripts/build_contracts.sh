#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONTRACTS_DIR="$REPO_ROOT/contracts"
WASM_OUT_DIR="$CONTRACTS_DIR/wasm"
CHECK_SCRIPT="$SCRIPT_DIR/check_wasm_bulk_memory.py"
RENAME_SCRIPT="$SCRIPT_DIR/rename_main_to_call.py"

CONTRACTS=(AuditTrail SentinelRegistry RiskOracle SentinelCredit AgentBehaviorIndex SentinelAlertLog RiskPolicyManager SubscriberVault)

log()  { echo "[build_contracts] $*"; }
fail() { echo "[build_contracts] ERROR: $*" >&2; exit "${2:-1}"; }

if [[ "${1:-}" == "--check" ]]; then
    log "Check-only mode: verifying existing WASM in $WASM_OUT_DIR"
    for c in "${CONTRACTS[@]}"; do
        [[ -f "$WASM_OUT_DIR/$c.wasm" ]] || fail "missing $WASM_OUT_DIR/$c.wasm" 4
    done
    python3 "$CHECK_SCRIPT" "$WASM_OUT_DIR" || fail "bulk-memory check failed" 4
    log "All 8 WASM files verified clean (no bulk-memory opcodes)."
    exit 0
fi

log "Step 1/4: checking toolchain…"
command -v cargo >/dev/null 2>&1 || fail "cargo not found. Install Rust: https://rustup.rs" 1
command -v wasm-opt >/dev/null 2>&1 || fail "wasm-opt not found. Install: apt-get install binaryen" 1

( cd "$CONTRACTS_DIR" && rustup toolchain install "$(cat rust-toolchain)" --profile minimal --component rust-src --target wasm32-unknown-unknown 2>/dev/null || true )

log "  cargo:     $(cargo --version)"
log "  wasm-opt:  $(wasm-opt --version 2>&1 | head -1)"
log "  toolchain: $(cat "$CONTRACTS_DIR/rust-toolchain")"

log "Step 2/4: compiling 8 contracts with cargo odra build…"
cd "$CONTRACTS_DIR"
cargo odra build

# Verify WASM files exist
mkdir -p "$WASM_OUT_DIR"
for c in "${CONTRACTS[@]}"; do
    wasm="$WASM_OUT_DIR/$c.wasm"
    if [[ ! -f "$wasm" ]]; then
        # Fallback: check target/release/
        raw_wasm="$CONTRACTS_DIR/target/wasm32-unknown-unknown/release/${c,,}.wasm"
        if [[ -f "$raw_wasm" ]]; then
            cp "$raw_wasm" "$wasm"
        else
            fail "could not find $c.wasm after cargo odra build" 2
        fi
    fi
    log "  $c.wasm  ($(stat -c%s "$WASM_OUT_DIR/$c.wasm") bytes)"
done

log "Step 3/4: post-processing with wasm-opt --llvm-memory-copy-fill-lowering…"
for c in "${CONTRACTS[@]}"; do
    wasm_path="$WASM_OUT_DIR/$c.wasm"
    tmp_path="$WASM_OUT_DIR/${c}.tmp.wasm"
    wasm-opt "$wasm_path" --enable-bulk-memory-opt --llvm-memory-copy-fill-lowering -Oz -o "$tmp_path" || fail "wasm-opt failed on $c" 3
    mv "$tmp_path" "$wasm_path"
    log "  $c.wasm optimized ($(stat -c%s "$wasm_path") bytes)"
done

log "Step 4/4: verifying zero bulk-memory opcodes + renaming main→call…"
python3 "$CHECK_SCRIPT" "$WASM_OUT_DIR" || fail "bulk-memory check failed" 4
python3 "$RENAME_SCRIPT" "$WASM_OUT_DIR" || log "  (rename skipped)"

log "✅ Done. 8 clean WASM artifacts in $WASM_OUT_DIR"
