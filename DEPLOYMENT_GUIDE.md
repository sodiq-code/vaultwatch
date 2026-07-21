# VaultWatch — Deployment Guide

> **Current state:** All 8 contracts deployed to Casper Testnet on July 11, 2026.
> Dashboard live at https://dashboard-rho-amber-89.vercel.app.
> This guide covers how to build, deploy, and verify from a fresh checkout.

---

## Prerequisites

### 0.1 Install Python + Node deps

```bash
git clone https://github.com/sodiq-code/vaultwatch
cd vaultwatch
pip install -r requirements.txt
pip install -e sdk/
```

### 0.2 Install the Rust toolchain (for contract builds)

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup toolchain install nightly-2026-01-01
rustup target add wasm32-unknown-unknown --toolchain nightly-2026-01-01
cargo install --locked cargo-odra --version 0.1.7
# wasm-opt:
sudo apt-get install -y binaryen wabt   # Debian/Ubuntu
# or: brew install binaryen wabt        # macOS
```

Verify:
```bash
cargo odra --version     # cargo-odra 0.1.7
wasm-opt --version       # 116+
```

---

## Step 0 — Create an Agent Wallet with CSPR.click

VaultWatch AI agents need Casper accounts to sign contract interactions. Use CSPR.click for browser-based wallet creation, or the CLI script for automated setup.

### Option A: CSPR.click Browser Wallet (Recommended for Development)

1. **Open CSPR.click** — Navigate to [https://cspr.click](https://cspr.click)
2. **Create a new wallet** — Click "Create Wallet" and follow the on-screen prompts
3. **Secure your seed phrase** — Write down the 12-word recovery phrase and store it securely
4. **Copy your public key** — This is your agent's on-chain identity (starts with `02...`)
5. **Fund the wallet** — Send CSPR from [testnet faucet](https://testnet.cspr.live/faucet) (testnet) or your exchange (mainnet)
6. **Export the signing key** — In CSPR.click Settings → Export Keys → download `secret_key.pem`
7. **Place the key file** — Move `secret_key.pem` to the repo root (already in `.gitignore`)

```bash
# Verify your key is loaded
export CASPER_KEY_PATH=./secret_key.pem
python3 -c "from pycspr.factory import parse_private_key; from pycspr.types.crypto import KeyAlgorithm; \
  key = parse_private_key('./secret_key.pem', KeyAlgorithm.SECP256K1); \
  print(f'Agent public key: {key.to_public_key().account_key.hex()[:30]}...')"
```

### Option B: CLI Script (Automated / CI)

```bash
# Generate a new agent wallet using CSPR.click pattern
node scripts/create_agent_wallet.js

# This creates:
#   .wallets/agent-<timestamp>/public_key_hex.txt  — Agent identity
#   .wallets/agent-<timestamp>/secret_key.pem       — Signing key (NEVER commit)
#   .wallets/agent-<timestamp>/cspr_click_url.txt   — CSPR.click import URL
```

The script also outputs a CSPR.click URL that you can open in a browser to import the wallet for monitoring.

### Agent Wallet Security

- **Never commit** `secret_key.pem` or `.wallets/` to git (already in `.gitignore`)
- **Use environment variables** for CI/CD: `CASPER_SECRET_KEY_HEX` or `CASPER_KEY_PATH`
- **Rotate keys** if any signing key is accidentally exposed
- **Separate keys per agent** in production — each AI agent should have its own Casper identity

---

## Step 1 — Build the WASM Contracts

```bash
bash scripts/build_contracts.sh
```

This compiles all 8 Odra contracts with `RUSTFLAGS=-C target-feature=-bulk-memory`,
post-processes with `wasm-opt --enable-bulk-memory=no`, and runs the bulk-memory
check as a hard gate.

**Verify:**
```bash
python3 scripts/check_wasm_bulk_memory.py contracts/wasm/
# Expected: ✅ PASS — all 8 WASM files are Casper-compatible
```

---

## Step 2 — Deploy to Casper Testnet

```bash
# Set key path (NEVER commit keys)
export CASPER_KEY_PATH=/path/to/secret_key.pem
export CASPER_NODE_URL=https://rpc.testnet.casper.network

# Dry-run first
python3 scripts/deploy_contracts_live.py --dry-run

# Live deploy
python3 scripts/deploy_contracts_live.py
```

The script writes `deploy_hashes_live.json` with the new hashes.

**Verify:**
```bash
python3 scripts/verify_deploys.py \
  --deploy-hashes deploy_hashes_live.json \
  --account <YOUR_DEPLOYER_PUBKEY>
```

Expected: all 8 deploys show `✅ success` and `named_keys_count > 0`.

---

## Step 3 — Update Hashes in the Dashboard

After deploying new contracts, update the contract hashes in:
- `dashboard/src/liveApi.js` — update `CONTRACT_HASHES` and `CONTRACT_PACKAGE_HASHES`
- `deploy_hashes_live.json` — machine-readable hash registry
- `proof/PROOF.md` — verification guide

Redeploy the dashboard:
```bash
cd dashboard
vercel --prod --yes
```

---

## Step 4 — Broadcast Sample Interactions

```bash
# Set the contract hashes from deploy_hashes_live.json
export AUDIT_TRAIL_HASH=<new hash>
# ... etc for all 8

python3 scripts/broadcast_interactions.py --live
```

Record the new interaction hashes in `proof/PROOF.md`.

---

## Step 5 — Publish Packages

### MCP Package (npm)

```bash
cd vaultwatch_mcp
npm version patch
npm login
npm publish
```

### x402 Package (npm)

```bash
cd x402
npm login
npm publish --access public
```

### Python SDK (PyPI)

```bash
cd sdk
python setup.py sdist bdist_wheel
python -m twine upload dist/*
```

---

## Step 6 — Verify CI Pipeline

Push to `main` and verify all CI jobs pass on GitHub Actions:

1. **Lint & Format** — ruff check + ruff format
2. **Python Tests** — all unit, integration, and demo tests
3. **Validate SDK** — pip install + import check
4. **Rust Contracts** — cargo test
5. **Docker Build** — image build verification

[![CI](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml)

---

## Contract Hashes (Current — July 11, 2026)

| Contract | Deploy Hash |
|----------|-------------|
| AuditTrail | `b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6333a7` |
| SentinelRegistry | `9a5eb4f83de8cbfef4f389516b977258b0e1d63179b288ca623a860fc6ec346c` |
| RiskOracle | `e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d` |
| SentinelCredit | `0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71` |
| AgentBehaviorIndex | `05066c33ddb73b523ab8f67275ca6096254f9d1832e76075d1e5f41f188b7dd0` |
| SentinelAlertLog | `53317e080ffdffcf097447ea3375c9195c6936fe7b1ed53795bf46134322a925` |
| RiskPolicyManager | `93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e` |
| SubscriberVault | `6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d` |

Deployer: `0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7`
