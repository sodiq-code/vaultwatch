#!/usr/bin/env bash
# VaultWatch — Apply the Final Round fix patch to your local clone
#
# This script applies the patch I generated to your local vaultwatch clone.
# It creates the feature branch, applies the patch, and verifies it applied
# cleanly. It does NOT merge to main — that's a separate step you do after
# building + deploying.
#
# Usage:
#   1. Download vaultwatch-final-round-fix.patch to your machine
#   2. Download this script (apply-final-round-fix.sh) to the same folder
#   3. Run: bash apply-final-round-fix.sh /path/to/your/vaultwatch/clone
#
# If you don't have a local clone yet:
#   git clone https://github.com/sodiq-code/vaultwatch
#   bash apply-final-round-fix.sh ./vaultwatch

set -e

CLONE_DIR="${1:-./vaultwatch}"
PATCH_FILE="$(dirname "$0")/vaultwatch-final-round-fix.patch"

if [ ! -d "$CLONE_DIR" ]; then
    echo "ERROR: clone directory not found: $CLONE_DIR"
    echo "Clone it first: git clone https://github.com/sodiq-code/vaultwatch"
    exit 1
fi

if [ ! -f "$PATCH_FILE" ]; then
    echo "ERROR: patch file not found: $PATCH_FILE"
    echo "Download it from the chat and place it next to this script."
    exit 1
fi

cd "$CLONE_DIR"

echo "=== Step 1: verify you're on main and up to date ==="
git checkout main
git pull origin main

echo ""
echo "=== Step 2: create the feature branch ==="
git checkout -b fix/final-round-wasm-mcp-x402-reputation

echo ""
echo "=== Step 3: apply the patch ==="
git apply --check "$PATCH_FILE" && echo "Patch applies cleanly ✅" || {
    echo "ERROR: patch does not apply cleanly. Your main may have diverged."
    echo "Contact me to regenerate the patch."
    exit 1
}
git apply "$PATCH_FILE"

echo ""
echo "=== Step 4: verify files were added ==="
git status --short | head -25

echo ""
echo "=== Step 5: commit ==="
git add -A
git commit -m "fix(final-round): bulk-memory WASM fix + 5 MCP tools + hybrid reputation + x402 + hygiene"

echo ""
echo "=== Done! ==="
echo "Feature branch 'fix/final-round-wasm-mcp-x402-reputation' is ready."
echo ""
echo "NEXT STEPS (do NOT merge to main yet):"
echo "  1. Install Rust nightly + Odra CLI + wasm-opt (see DEPLOYMENT_GUIDE.md §0.2)"
echo "  2. Build WASM:  bash scripts/build_contracts.sh"
echo "  3. Verify:      python3 scripts/check_wasm_bulk_memory.py contracts/wasm/"
echo "  4. Deploy:      python3 scripts/deploy_contracts_live.py"
echo "  5. Verify:      python3 scripts/verify_deploys.py --account <NEW_PUBKEY>"
echo "  6. Update proof/PROOF.md with new hashes"
echo "  7. ONLY THEN merge to main (see merge-to-main.sh)"
