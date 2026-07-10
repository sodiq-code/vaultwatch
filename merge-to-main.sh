#!/usr/bin/env bash
# VaultWatch — Merge the feature branch to main (ONLY after deploy succeeds)
#
# Run this ONLY after:
#   - bash scripts/build_contracts.sh succeeded
#   - python3 scripts/check_wasm_bulk_memory.py contracts/wasm/ passed (8/8 clean)
#   - python3 scripts/deploy_contracts_live.py deployed all 8 contracts
#   - python3 scripts/verify_deploys.py shows 8/8 success + named_keys > 0
#   - proof/PROOF.md updated with new deploy hashes
#
# This script:
#   1. Switches to main
#   2. Merges the feature branch (no-ff to preserve history)
#   3. Pushes to GitHub
#
# Usage:
#   bash merge-to-main.sh /path/to/your/vaultwatch/clone

set -e

CLONE_DIR="${1:-./vaultwatch}"

if [ ! -d "$CLONE_DIR" ]; then
    echo "ERROR: clone directory not found: $CLONE_DIR"
    exit 1
fi

cd "$CLONE_DIR"

echo "=== PRE-MERGE CHECKLIST ==="
echo "Before continuing, verify ALL of these are done:"
echo "  [ ] bash scripts/build_contracts.sh succeeded"
echo "  [ ] python3 scripts/check_wasm_bulk_memory.py contracts/wasm/ → 8/8 clean"
echo "  [ ] python3 scripts/deploy_contracts_live.py → 8/8 deployed"
echo "  [ ] python3 scripts/verify_deploys.py → 8/8 success + named_keys > 0"
echo "  [ ] proof/PROOF.md updated with new hashes"
echo ""
read -p "All checks passed? Type 'yes' to merge to main: " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Aborted. Complete the checklist first."
    exit 0
fi

echo ""
echo "=== Step 1: switch to main and pull latest ==="
git checkout main
git pull origin main

echo ""
echo "=== Step 2: merge feature branch (no-ff preserves history) ==="
git merge --no-ff fix/final-round-wasm-mcp-x402-reputation -m "merge: Final Round fix — bulk-memory WASM fix + 5 MCP tools + hybrid reputation + official x402 + repo hygiene

8 contracts rebuilt bulk-memory-safe and redeployed to Casper Testnet.
All deploys verified via state_get_account_info (named_keys > 0).
See DEPLOYMENT_GUIDE.md for the full fix story."

echo ""
echo "=== Step 3: push to GitHub ==="
git push origin main

echo ""
echo "=== DONE! main is now updated. ==="
echo ""
echo "NEXT STEPS:"
echo "  1. Wait for CI to pass (Actions tab → ci.yml + build-contracts.yml + codeql.yml)"
echo "  2. Fix any High+ CodeQL alerts"
echo "  3. Set GitHub topics: casper-blockchain, casper-network, buildathon, ..."
echo "  4. Enable Dependabot (Settings → Code security & analysis)"
echo "  5. Record a fresh demo video"
echo "  6. Create your Final Round BUIDL submission on DoraHacks (if invited)"
