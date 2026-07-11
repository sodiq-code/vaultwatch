# VaultWatch — Final Round Deployment Guide

> **Read this first.** This is the step-by-step path from the current
> state (8 failed deploys) to a verified, Final-Round-eligible submission.
> Follow it top-to-bottom. Each step has a verification command — do not
> proceed until the verification passes.

## Timeline (estimated)

| Day | Task | Status |
|-----|------|--------|
| 0 | Rotate compromised keys, install toolchain | Pre-work |
| 1 | Build + deploy contracts (WASM fix) | Mandatory |
| 2 | Verify deploys + update PROOF.md | Mandatory |
| 3–4 | Publish MCP + x402 packages | High priority |
| 5–6 | Write tests for new MCP tools + reputation | High priority |
| 7 | Update README + record fresh demo | Medium |
| 8–14 | Buffer / polish | — |

## Prerequisites

### 0.1 Rotate compromised credentials

**CRITICAL** — your wallet secret keys, NPM recovery codes, and PyPI
recovery codes were exposed in a previous chat session. Treat ALL as
compromised.

1. **Casper wallet**: generate a new key pair with `casper-client keygen`
   or the Casper Signer extension. Fund the new testnet account from the
   faucet (https://testnet.cspr.live/tools/faucet). Do NOT transfer from
   the old account — the old account is burned.
2. **NPM**: log in to npmjs.com → Account Settings → Authentication &
   Security → regenerate recovery codes. Enable 2FA if not already.
3. **PyPI**: log in to pypi.org → Account settings → Recovery codes →
   reset. Enable 2FA.

### 0.2 Install the Rust toolchain

```bash
# Install rustup if you don't have it
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install the pinned nightly (matches contracts/rust-toolchain)
rustup toolchain install nightly-2026-01-01
rustup target add wasm32-unknown-unknown --toolchain nightly-2026-01-01
rustup component add rust-src --toolchain nightly-2026-01-01

# Install cargo-odra (provides the `cargo odra` subcommand — NOT a standalone `odra` binary)
cargo install --locked cargo-odra --version 0.1.7

# Install wasm-opt (binaryen)
sudo apt-get install -y binaryen wabt   # Debian/Ubuntu
# or: brew install binaryen wabt        # macOS
# or: choco install binaryen            # Windows
```

Verify:
```bash
cargo --version          # cargo 1.x
cargo odra --version     # cargo-odra 0.1.7
wasm-opt --version       # 116+
```

### 0.3 Install Python + Node deps

```bash
pip install -r requirements.txt
pip install -e sdk/
pip install pycspr       # for live deploys

cd x402 && npm install && cd ..
cd vaultwatch_mcp && npm install && cd ..
```

---

## Step 1 — Build the Casper-compatible WASM (MANDATORY)

This is the fix for the "Bulk memory operations are not supported" error
that caused all 8 prior deploys to fail.

```bash
cd vaultwatch
bash scripts/build_contracts.sh
```

**What this does:**
1. Compiles all 8 contracts with `RUSTFLAGS=-C target-feature=-bulk-memory`
   (set via `contracts/.cargo/config.toml`)
2. Post-processes each `.wasm` with `wasm-opt --enable-bulk-memory=no`
3. Runs `scripts/check_wasm_bulk_memory.py` as a hard gate

**Verify:**
```bash
python3 scripts/check_wasm_bulk_memory.py contracts/wasm/
# Expected output:
# ✅ PASS — all 8 WASM files are Casper-compatible (no bulk-memory opcodes).
```

If this fails, the CI workflow `.github/workflows/build-contracts.yml`
will also fail — check the Actions tab for build logs.

---

## Step 2 — Deploy to Casper Testnet (MANDATORY)

```bash
# Set the rotated key path (NEVER commit this)
export CASPER_KEY_PATH=/path/to/rotated_secret_key.pem
export CASPER_NODE_URL=https://rpc.testnet.casper.network

# Dry-run first — validates WASM without deploying
python3 scripts/deploy_contracts_live.py --dry-run

# Live deploy
python3 scripts/deploy_contracts_live.py
```

The script:
- Pre-validates WASM (refuses to deploy if bulk-memory check fails)
- Deploys all 8 contracts via pycspr
- Waits for each deploy to be included + executed
- Writes `deploy_hashes_live.json` with the new hashes
- Prints a ready-to-paste table for `proof/PROOF.md`

**Verify:**
```bash
python3 scripts/verify_deploys.py \
  --deploy-hashes deploy_hashes_live.json \
  --account <YOUR_NEW_DEPLOYER_PUBKEY>
```

Expected: all 8 deploys show `✅ success` and `named_keys_count > 0`.
If any show `❌ failed` or `named_keys_count: 0`, the WASM fix didn't
work — go back to Step 1.

---

## Step 3 — Update proof/PROOF.md (MANDATORY)

Open `proof/PROOF.md` and replace §1's deploy hash table with the output
from Step 2. Also:

1. Replace the deployer account public key with your NEW (rotated) key.
2. Update the deployment date.
3. Add the new deploy hashes to the "29 on-chain TX hashes" section
   (you'll re-broadcast interactions in Step 4).
4. Remove or annotate the OLD hashes as "FAILED — June 24, 2026 —
   bulk-memory error, replaced on <new date>".

**Verify:** every link in PROOF.md opens to a testnet.cspr.live page
showing `Status: Success` (not `Wasm preprocessing error`).

---

## Step 4 — Broadcast sample interactions

Re-run the interaction broadcasts with the new contracts:

```bash
# Set the new contract hashes
export AUDIT_TRAIL_HASH=<from deploy_hashes_live.json>
export RISK_ORACLE_HASH=<...>
# ... etc for all 8

python3 scripts/broadcast_interactions.py --live
```

This re-creates the 21 sample interactions (add_entry, update_score,
log_alert, etc.) against the new contracts. Record the new interaction
hashes in `proof/PROOF.md §9`.

---

## Step 5 — Publish MCP package to npm

```bash
cd vaultwatch_mcp

# Bump version (we added 5 new tools)
# Edit package.json: "version": "4.1.0"
npm version 4.1.0

# Login with your ROTATED npm account
npm login

# Publish
npm publish
```

**Verify:** https://www.npmjs.com/package/casper-sentinel-mcp shows
v4.1.0 with the new tools listed in the README.

Update the badge in the root README:
`[![npm](https://img.shields.io/npm/v/casper-sentinel-mcp.svg)](https://www.npmjs.com/package/casper-sentinel-mcp)`

---

## Step 6 — Publish x402 package to npm (new)

```bash
cd x402
npm login
npm publish --access public
```

This publishes `@vaultwatch/x402` — the official x402 SDK integration.

---

## Step 7 — Publish Python SDK to PyPI

```bash
cd sdk
# Bump version in setup.py to 4.1.0
python setup.py sdist bdist_wheel

# Upload with your ROTATED PyPI credentials
python -m twine upload dist/*
```

**Verify:** https://pypi.org/project/casper-sentinel/ shows v4.1.0.

---

## Step 8 — Configure GitHub repository

### 8.1 Topics (required by hackathon)

Go to https://github.com/sodiq-code/vaultwatch and click the gear icon
next to "About". Add these topics:
- `casper-blockchain`
- `casper-network`
- `buildathon`
- `odra`
- `defi`
- `risk-intelligence`
- `ai-agents`
- `mcp`
- `x402`
- `rwa`
- `groq`
- `opentelemetry`

### 8.2 Repository description + website

- **Description**: `AI-Powered DeFi Risk Intelligence Agent on Casper — 8 Odra contracts, 20-tool MCP server, hybrid reputation formula`
- **Website**: `https://dashboard-rho-amber-89.vercel.app`

### 8.3 Community standards

Go to https://github.com/sodiq-code/vaultwatch/community and verify each
section has a green checkmark:
- README ✅
- Code of Conduct ✅ (added in this branch)
- Contributing ✅ (added in this branch)
- License ✅ (MIT — already present)
- Security policy ✅ (added in this branch)
- Issue templates (optional but recommended)
- Pull request template (optional but recommended)

### 8.4 Enable security features

- Settings → Code security & analysis → enable:
  - **CodeQL** ✅ (workflow added in this branch)
  - **Dependabot alerts** ✅ (config added in this branch)
  - **Dependabot security updates** ✅
  - **Secret scanning** ✅
  - **Push protection** ✅

Fix ALL CodeQL alerts with severity High or greater before the final
round deadline.

---

## Step 9 — Merge the fix branch

```bash
# From your local machine (NOT this sandbox)
git fetch origin
git checkout main
git merge --no-ff fix/final-round-wasm-mcp-x402-reputation

# Push
git push origin main
```

**Verify:** CI passes on main (lint + tests + build-contracts + CodeQL).

---

## Step 10 — Record a fresh demo video

The existing demo (https://youtu.be/Jmg_MFSxwdE) references the old
(broken) deploys. Record a new demo showing:

1. The 8 NEW deploy hashes on testnet.cspr.live (all Success)
2. The MCP server running with 20 tools (show `agent_attestation` +
   `reputation_query` + `x402_subscribe`)
3. The hybrid reputation score for AnomalyAgent
4. A live x402 payment flow (subscribe → query → deduct)
5. The red-team checklist (docs/RED_TEAM_CHECKLIST.md)

Upload to YouTube, update the README link.

---

## Step 11 — Update DoraHacks BUIDL page

Go to https://dorahacks.io/hackathon/casper-agentic-buildathon/detail
and update your BUIDL submission with:

1. The new deploy hashes (from `deploy_hashes_live.json`)
2. The new demo video URL
3. Concise step-by-step testing instructions (no marketing) — e.g.:
   ```
   1. Clone repo, pip install -r requirements.txt
   2. Set GROQ_API_KEY env var
   3. Run: python3 vaultwatch_mcp/server.py
   4. In another terminal: python3 scripts/demo_risk.py
   5. View results: open dashboard at https://dashboard-rho-amber-89.vercel.app
   6. Verify on-chain: https://testnet.cspr.live/deploy/<new-AuditTrail-hash>
   ```
4. The new contract package hashes (from `verify_deploys.py` output)

---

## Emergency: if a judge visits mid-fix

The hackathon team warned: "if a judge comes in the middle of changes
and the repo/project is in a broken state, it might fail."

**Mitigation:** the fix branch is separate from `main`. Only merge to
`main` when ALL of these are true:
- [ ] `python3 scripts/check_wasm_bulk_memory.py contracts/wasm/` passes
- [ ] `pytest tests/ -v` passes (130 tests)
- [ ] `ruff check .` passes
- [ ] The live deploy script succeeded for all 8 contracts
- [ ] `verify_deploys.py` shows named_keys > 0 for all 8

Until then, `main` stays on the old (broken) state — which is still a
functional MVP (the off-chain agent + dashboard work, the contracts just
failed to deploy). This is strictly better than a half-merged broken
state.

---

## Final Checklist (print this)

- [ ] All 3 credential sets rotated (Casper wallet, NPM, PyPI)
- [ ] Rust nightly + Odra CLI + wasm-opt installed
- [ ] `bash scripts/build_contracts.sh` succeeds
- [ ] `check_wasm_bulk_memory.py` reports 8/8 clean
- [ ] `deploy_contracts_live.py` deploys all 8 contracts
- [ ] `verify_deploys.py` shows 8/8 success + named_keys > 0
- [ ] `proof/PROOF.md` updated with new hashes
- [ ] `broadcast_interactions.py` re-broadcasts 21 interactions
- [ ] MCP package v4.1.0 published to npm
- [ ] x402 package published to npm
- [ ] Python SDK v4.1.0 published to PyPI
- [ ] GitHub topics set (casper-blockchain, casper-network, buildathon, ...)
- [ ] GitHub community standards all green
- [ ] CodeQL + Dependabot enabled
- [ ] All High+ CodeQL alerts fixed
- [ ] Fix branch merged to main
- [ ] Fresh demo video recorded + README updated
- [ ] DoraHacks BUIDL page updated with new hashes + testing instructions
- [ ] Hybrid reputation formula + red-team checklist linked from README

When all boxes are checked, you are Final-Round eligible and competitive
with the top 2.
