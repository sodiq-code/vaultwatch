#!/usr/bin/env bash
# Restore original 200KB WASMs from git + strip bulk-memory + rename main→call

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WASM_DIR="$REPO_ROOT/contracts/wasm"
CONTRACTS=(AuditTrail SentinelRegistry RiskOracle SentinelCredit AgentBehaviorIndex SentinelAlertLog RiskPolicyManager SubscriberVault)

log() { echo "[fix_wasm] $*"; }
fail() { echo "[fix_wasm] ERROR: $*" >&2; exit 1; }

log "Step 1: Restoring original 200KB WASMs from git…"
cd "$REPO_ROOT"
for c in "${CONTRACTS[@]}"; do
    git show "main:contracts/wasm/$c.wasm" > "$WASM_DIR/$c.wasm"
    size=$(stat -c%s "$WASM_DIR/$c.wasm")
    log "  $c.wasm restored ($size bytes)"
done

log ""
log "Step 2: Stripping bulk-memory opcodes with wasm-opt v130…"
command -v wasm-opt >/dev/null 2>&1 || fail "wasm-opt not found"
log "  wasm-opt version: $(wasm-opt --version 2>&1 | head -1)"

for c in "${CONTRACTS[@]}"; do
    wasm_path="$WASM_DIR/$c.wasm"
    tmp_path="$WASM_DIR/${c}.tmp.wasm"
    wasm-opt "$wasm_path" --enable-bulk-memory-opt --llvm-memory-copy-fill-lowering -Oz -o "$tmp_path" \
        || fail "wasm-opt failed on $c"
    mv "$tmp_path" "$wasm_path"
    size=$(stat -c%s "$wasm_path")
    log "  $c.wasm optimized ($size bytes)"
done

log ""
log "Step 3: Renaming 'main' export to 'call' (Casper 2.x requirement)…"
python3 "$REPO_ROOT/scripts/rename_main_to_call.py" "$WASM_DIR"

log ""
log "Step 4: Verifying — bulk-memory check…"
python3 "$REPO_ROOT/scripts/check_wasm_bulk_memory.py" "$WASM_DIR"

log ""
log "Step 5: Verifying call + init exports in each WASM…"
python3 << 'EOF'
from pathlib import Path
wasm_dir = Path("contracts/wasm")
all_ok = True
for name in ["AuditTrail", "SentinelRegistry", "RiskOracle", "SentinelCredit",
             "AgentBehaviorIndex", "SentinelAlertLog", "RiskPolicyManager", "SubscriberVault"]:
    data = (wasm_dir / f"{name}.wasm").read_bytes()
    size_kb = len(data) / 1024
    i = 8
    exports = []
    while i < len(data):
        section_id = data[i]; i += 1
        size = 0; shift = 0
        while True:
            b = data[i]; i += 1
            size |= (b & 0x7f) << shift
            if not (b & 0x80): break
            shift += 7
        if section_id == 7:
            j = i
            num_exports = 0; shift = 0
            while True:
                b = data[j]; j += 1
                num_exports |= (b & 0x7f) << shift
                if not (b & 0x80): break
                shift += 7
            for _ in range(num_exports):
                name_len = data[j]; j += 1
                ename = data[j:j+name_len].decode('utf-8', errors='replace')
                j += name_len + 1
                while True:
                    b = data[j]; j += 1
                    if not (b & 0x80): break
                exports.append(ename)
            break
        i += size
    has_call = "call" in exports
    has_init = "init" in exports
    ok = has_call and has_init
    all_ok = all_ok and ok
    print(f"  {'✅' if ok else '❌'} {name:25s} {size_kb:6.1f} KB  exports={len(exports)}  call={'yes' if has_call else 'NO'}  init={'yes' if has_init else 'NO'}")
print()
if all_ok:
    print("✅ ALL WASMs have 'call' + 'init' exports — ready for Casper 2.x deploy!")
else:
    print("❌ Some WASMs missing exports — DO NOT deploy")
EOF

log ""
log "✅ Done! WASMs are ready for deployment."
