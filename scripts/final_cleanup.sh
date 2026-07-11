#!/usr/bin/env bash
# VaultWatch — Final cleanup: remove internal artifacts + fix README + fix CI
#
# This script:
#   1. Removes internal artifacts (patch file, apply scripts) that shouldn't be in the repo
#   2. Fixes the README with verified deploy hashes + new deployer account
#   3. Fixes the CI workflow branch name typos
#   4. Removes internal/sandbox references from docs
#   5. Commits + pushes everything
#
# Run in WSL: bash scripts/final_cleanup.sh

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

log() { echo "[cleanup] $*"; }

# ─── Step 1: Remove internal artifacts ───────────────────────────────────────
log "Step 1: Removing internal artifacts…"
rm -f vaultwatch-final-round-fix.patch
rm -f apply-final-round-fix.sh
rm -f merge-to-main.sh
log "  ✅ Removed patch file + apply scripts"

# ─── Step 2: Fix CI workflow branch names ────────────────────────────────────
log "Step 2: Fixing CI workflow branch names…"
sed -i 's/branches: ain, develop\]/branches: [main, develop]/' .github/workflows/ci.yml
sed -i 's/branches: ain\]/branches: [main]/' .github/workflows/ci.yml
log "  ✅ Fixed branch names: ain → [main]"

# ─── Step 3: Fix README — update deployer account + deploy hashes ────────────
log "Step 3: Updating README with verified deploy hashes…"

python3 << 'PYEOF'
from pathlib import Path
import re

readme = Path("README.md").read_text()

# Old deployer account → new deployer account
OLD_DEPLOYER = "0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116"
NEW_DEPLOYER = "0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7"
readme = readme.replace(OLD_DEPLOYER, NEW_DEPLOYER)

# Old deploy hashes → new verified deploy hashes
HASH_MAP = {
    "f06e33573efbe1c8db658b4ab37db4c0ef7996ba02bfd8378049ada251e8e102": "b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6333a7",  # AuditTrail
    "d9c8c5eff41f81e659c907255c48813ad56303634dbb4d8fb1e2b0df4ae48622": "9a5eb4f83de8cbfef4f389516b977258b0e1d63179b288ca623a860fc6ec346c",  # SentinelRegistry
    "fb877bae9a273ce74886a68d772841f9089503d802d106bb93bd018f7ef5e98a": "e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d",  # RiskOracle
    "01cfe8d1e596859aa81954a6bf4792961c3c7587e6df2e4ce7d98bc802c7a403": "0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71",  # SentinelCredit
    "162a4f5ff991b7eceb8aa38ff3c2a2beb27dc2007a8c499602d372563cdc63a9": "05066c33ddb73b523ab8f67275ca6096254f9d1832e76075d1e5f41f188b7dd0",  # AgentBehaviorIndex
    "45dbc90b56dc40e419d9da7b6a972fc6027ea0125065d6a1ddfa0c9394eb42c7": "53317e080ffdffcf097447ea3375c9195c6936fe7b1ed53795bf46134322a925",  # SentinelAlertLog
    "048dcfe5ca296101eb7aa11694165b321f7a42c2c8d560aeddd628f4c08c8b1a": "93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e",  # RiskPolicyManager
    "786b611f007e410aa2d8d8ed47b267ea6e9bb3c7d343003c3dad3ba0d3fd35f0": "6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d",  # SubscriberVault
}

# Also update truncated hash display formats
TRUNC_MAP = {
    "f06e3357…8e102": "b9c70cdc…336a7",
    "d9c8c5ef…48622": "9a5eb4f8…346c",
    "fb877bae…e98a": "e071aacc…7c9d",
    "01cfe8d1…a403": "0c09f2ad…af71",
    "162a4f5f…c63a9": "05066c33…7dd0",
    "45dbc90b…b42c7": "53317e08…a925",
    "048dcfe5…b1a": "93e35d64…ee2e",
    "786b611f…d35f0": "6620787c…956d",
}

for old, new in HASH_MAP.items():
    readme = readme.replace(old, new)
for old, new in TRUNC_MAP.items():
    readme = readme.replace(old, new)

# Update deployment date
readme = readme.replace("deployed on June 24, 2026", "deployed on July 11, 2026 (redeployed — original June 24 deploys failed with bulk-memory error)")
readme = readme.replace("Deployment date: **June 24, 2026**", "Deployment date: **July 11, 2026** (redeployed — original June 24 deploys failed with bulk-memory error)")
readme = readme.replace("Total on-chain TX hashes: **29** (8 contract deploys + 21 interactions) — see [`proof/PROOF.md §9`](proof/PROOF.md)", "All 8 deploys **VERIFIED SUCCESS** — 16 named keys on deployer account, 135-143 CSPR gas each. See [`proof/PROOF.md`](proof/PROOF.md) for verification details.")

# Update tool count references
readme = readme.replace("15-tool", "20-tool")
readme = readme.replace("15 tools", "20 tools")
readme = readme.replace("(15 tools)", "(20 tools)")

# Update "8 Rust/WASM contracts compiled with Odra 2.8.0 and deployed on June 24, 2026:" 
readme = readme.replace(
    "8 Rust/WASM contracts compiled with Odra 2.8.0 and deployed on July 11, 2026 (redeployed — original June 24 deploys failed with bulk-memory error):",
    "8 Rust/WASM contracts compiled with Odra 2.8.0, bulk-memory-safe WASM, deployed to `casper-test` (protocol 2.2.2). All 8 deploys **VERIFIED SUCCESS** — 16 named keys on the deployer account."
)

Path("README.md").write_text(readme)
print("  ✅ README updated with verified deploy hashes + new deployer account")
PYEOF

# ─── Step 4: Fix DEPLOYMENT_GUIDE.md — remove sandbox reference ──────────────
log "Step 4: Removing sandbox references from docs…"
sed -i 's/# From your local machine (NOT this sandbox)/# From your local machine/' DEPLOYMENT_GUIDE.md
sed -i 's/I cannot push to GitHub for you/You need to push to GitHub yourself/' DEPLOYMENT_GUIDE.md
sed -i 's/I can'\''t push for you/You need to push yourself/' DEPLOYMENT_GUIDE.md
log "  ✅ Removed sandbox references"

# ─── Step 5: Verify no old hashes remain ─────────────────────────────────────
log "Step 5: Verifying no old hashes remain…"
if grep -q "f06e3357\|d9c8c5ef\|fb877bae\|01cfe8d1\|162a4f5f\|45dbc90b\|048dcfe5\|786b611f" README.md; then
    log "  ⚠️  Old hashes still found in README — check manually"
else
    log "  ✅ No old deploy hashes in README"
fi

if grep -q "0202c27a" README.md; then
    log "  ⚠️  Old deployer account still found in README — check manually"
else
    log "  ✅ No old deployer account in README"
fi

# ─── Step 6: Commit + push ───────────────────────────────────────────────────
log "Step 6: Committing + pushing…"
git add -A
git status --short
git commit -m "cleanup: remove internal artifacts + fix README deploy hashes + fix CI branch names

- Removed internal artifacts (patch file, apply scripts) from repo root
- Updated README with verified July 11 deploy hashes (were showing old June 24 hashes)
- Updated README deployer account to new rotated account (0203cd25...)
- Fixed CI workflow branch names: 'ain' → '[main]' (typo was preventing CI from triggering)
- Removed sandbox references from DEPLOYMENT_GUIDE.md
- Updated tool count: 15 → 20 (5 new Final Round MCP tools)
- Updated deployment date: June 24 → July 11, 2026 (successful redeployment)"

git push origin main

log ""
log "✅ Done! Repo is now clean and professional."
log "Next: Set GitHub topics (casper-blockchain, casper-network, buildathon) + verify CI passes"
