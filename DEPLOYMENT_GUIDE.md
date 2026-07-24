# VaultWatch — Deployment Guide

> **Current state:** All 8 contracts deployed to Casper Testnet on July 11, 2026.
> **36 verified deploys — all SUCCESS** (8 installs + 21 interactions + 6 upgrades + 1 x402 payment).
> Dashboard live at https://vaultwatch-dashboard-v5.vercel.app.
> Demo video: https://youtu.be/aWwmSC361ac
> This guide covers how to build, deploy, configure, and verify from a fresh checkout.

---

## Prerequisites

### 0.1 Install Python + Node deps

```bash
git clone https://github.com/sodiq-code/vaultwatch
cd vaultwatch
pip install -r requirements.txt
pip install -e sdk/
npm install   # Node helpers for CSPR.click + x402
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

### 0.3 Set up environment variables

Create `.env` from `.env.example` (or set these as shell exports):

```bash
# ── AI Providers ────────────────────────────────────────────────
GROQ_API_KEY=your_groq_key                          # Required — primary AI provider
OPENROUTER_API_KEY=your_openrouter_key              # Optional — secondary AI provider (free tier at openrouter.ai)

# ── Casper Network ──────────────────────────────────────────────
CASPER_NODE_URL=https://node.testnet.casper.network/rpc
CASPER_CHAIN_NAME=casper-test
CASPER_MOCK=true                                    # true = safe for CI / local dev (no on-chain writes)

# ── CSPR.click Agent Wallet ────────────────────────────────────
VAULTWATCH_AGENT_KEY_PATH=~/.vaultwatch/agent_key.pem  # Created programmatically on first run; gitignored

# ── x402 Dual-Path Payment ─────────────────────────────────────
X402_PAYMENT_AMOUNT=1000000                         # Motes (1 CSPR = 1_000_000_000 motes)

# ── WCSPR / CSPR.cloud Facilitator (Path B) ────────────────────
CSPR_CLOUD_API_URL=https://api.testnet.cspr.cloud
CSPR_CLOUD_API_KEY=your_cspr_cloud_key              # Required for Path B WCSPR facilitator
WCSPR_CONTRACT_HASH=93c7f84f...                     # WCSPR CEP-18 contract hash on testnet

# ── API Server ──────────────────────────────────────────────────
API_HOST=0.0.0.0
API_PORT=8000

# ── Observability (optional) ───────────────────────────────────
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

---

## CSPR.click Agent Wallet Setup

VaultWatch uses **CSPR.click** (the Casper Association's official tool) for all agent signing and transaction construction — not manual PEM key management. The `AgentWallet` abstraction creates the keypair programmatically on first run.

### Server-side (pipeline, MCP, e2e tests)

```python
from agents.agent_wallet import AgentWallet

# 1. Ensure an agent wallet exists (creates one on first run)
wallet = AgentWallet.ensure_exists()

# 2. Fund the wallet on testnet
print(wallet.public_key)       # e.g. '0203...'
print(wallet.faucet_url)       # https://testnet.cspr.live/tools/faucet
# Paste the public key into the faucet to fund it

# 3. Verify funding
wallet.refresh_balance()
wallet.assert_funded(min_cspr=1.0)

# 4. Sign + submit deploys
result = wallet.call_contract(
    contract_hash='hash-68c4b7cca84982833af3f9346a5a9ea337bfdcd20875bd82f4c7ec7b1505d211',
    entry_point='open_vault',
    args={...},
)
```

The key lives at `$VAULTWATCH_AGENT_KEY_PATH` (default `~/.vaultwatch/agent_key.pem`), which is gitignored. On first run, `AgentWallet.ensure_exists()` creates the key and logs the faucet URL.

Under the hood, `AgentWallet` delegates to:
- [`scripts/csprclick_agent_wallet.cjs`](scripts/csprclick_agent_wallet.cjs) — keypair creation + wallet info
- [`scripts/casper_call.cjs`](scripts/casper_call.cjs) — deploy signing + submission + on-chain verification

### Browser-side (dashboard)

The dashboard uses `CSPRClickProvider` + `WalletBar.jsx` for user-facing Connect/Disconnect flows: [`dashboard/src/csprclick.js`](dashboard/src/csprclick.js)

---

## x402 Dual-Path Payment Architecture

VaultWatch implements the x402 v2 specification with **two payment paths**, covering both the self-hosted and external facilitator models:

| Path | Token | Verification | Settlement |
|------|-------|--------------|------------|
| **Path A — Self-Hosted** | Native CSPR via `SubscriberVault` escrow | Local `ExactCasperScheme.verify()` + EIP-712 | Direct on-chain deploy (`open_vault`) |
| **Path B — CSPR.cloud Facilitator** | WCSPR (CEP-18 wrapped CSPR) | CSPR.cloud `/verify` + `transfer_with_authorization` | CSPR.cloud `/settle` facilitator |

### Path A: Native CSPR (Self-Hosted)

- Payment via `SubscriberVault::open_vault` with 1 CSPR escrow
- Verified payment deploy: [`0588e143…5e2c`](https://testnet.cspr.live/deploy/0588e143d15eebb7004c23052cd3727d7b87c3b120981184eff5abc9b33f5e2c)
- Source: [`x402/vaultwatch-x402.ts`](x402/vaultwatch-x402.ts) · [`docs/X402_INTEGRATION.md`](docs/X402_INTEGRATION.md)

### Path B: WCSPR (CSPR.cloud Facilitator)

- Payment via WCSPR CEP-18 token transfer with CSPR.cloud facilitator
- Requires `CSPR_CLOUD_API_KEY` and `WCSPR_CONTRACT_HASH` env vars
- Source: [`x402/wcspr-x402-path.ts`](x402/wcspr-x402-path.ts) · [`x402/wcspr_helper.mjs`](x402/wcspr_helper.mjs)
- Architecture: [`docs/X402_DUAL_PATH_ARCHITECTURE.md`](docs/X402_DUAL_PATH_ARCHITECTURE.md)
- Proof: [`proof/X402_DUAL_PATH_PROOF.md`](proof/X402_DUAL_PATH_PROOF.md)

### 7 API endpoints for x402 dual-path

`/x402/facilitator/status` · `/x402/facilitator/supported` · `/x402/facilitator/verify` · `/x402/facilitator/settle` · `/x402/wcspr/info` · `/x402/wcspr/balance/{account_hash}` · `/x402/dual-path/status`

---

## Multi-Provider AI Resilience

VaultWatch agents use a `MultiProviderClient` that tries providers in priority order:

1. **Groq** (primary — fast, low-latency)
2. **OpenRouter** (secondary — broad model catalog, free tier)
3. **Heuristic fallback** (no external API — rule-based analysis)

Each agent owns its own heuristic fallback logic. The `MultiProviderClient` gives them more chances to get a real AI response before falling back.

```python
from agents.ai_providers import MultiProviderClient

client = MultiProviderClient(
    groq_api_key="gsk_...",
    openrouter_api_key="sk-or-...",   # optional — free tier at openrouter.ai
)

result = client.chat_completion(
    model="llama-3.3-70b-versatile",
    messages=[...],
)
if result is not None:
    content = result.first_content
else:
    # Use agent-specific heuristic fallback
```

Source: [`agents/ai_providers.py`](agents/ai_providers.py)

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
# Expected: PASS — all 8 WASM files are Casper-compatible (zero bulk-memory opcodes)
```

---

## Step 2 — Deploy to Casper Testnet

```bash
# Set key path (NEVER commit keys)
export VAULTWATCH_AGENT_KEY_PATH=~/.vaultwatch/agent_key.pem
export CASPER_NODE_URL=https://node.testnet.casper.network/rpc

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
  --account 0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7
```

Expected: all 8 deploys show `success` and `named_keys_count > 0`.

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

## Step 5 — Publish Packages (Future Plans)

The following npm and PyPI publications are planned for post-hackathon release. They are not currently published.

### MCP Package (npm) — Planned

```bash
cd vaultwatch_mcp
npm version patch
npm login
npm publish
```

### x402 Package (npm) — Planned

```bash
cd x402
npm login
npm publish --access public
```

### Python SDK (PyPI) — Planned

```bash
cd sdk
python setup.py sdist bdist_wheel
python -m twine upload dist/*
```

---

## Step 6 — Verify CI Pipeline

Push to `main` and verify all CI workflows pass on GitHub Actions. VaultWatch has **3 CI workflows**:

### ci.yml — VaultWatch CI

| Job | Description |
|-----|-------------|
| **Lint & Format** | `ruff check` + `ruff format --check` |
| **Python Tests** | Unit (260) + Integration (165) + Demo (6) — 481 total, `CASPER_MOCK=true` |
| **Validate Python SDK** | `pip install -e sdk/` + import check |
| **Rust Contracts** | `cargo test` in `contracts/` |
| **Docker Build** | Build `vaultwatch:latest` image (main branch only) |

[![CI](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml)

### build-contracts.yml — Build Casper-Compatible WASM

Compiles all 8 contracts with bulk-memory-disabled Rust flags, post-processes with `wasm-opt`, verifies zero bulk-memory opcodes, uploads clean WASM as CI artifact.

| Job | Description |
|-----|-------------|
| **build-wasm** | Compile 8 contracts (bulk-memory safe) + `cargo odra test` + re-verify gate + upload artifacts |

[![Build Contracts](https://github.com/sodiq-code/vaultwatch/actions/workflows/build-contracts.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/build-contracts.yml)

### codeql.yml — CodeQL Security Analysis

| Job | Description |
|-----|-------------|
| **analyze-python** | CodeQL analysis of Python codebase (agents + MCP + SDK) with `security-extended` queries |
| **analyze-javascript** | CodeQL analysis of JS/TS codebase (x402 + MCP + dashboard) with `security-extended` queries |

Runs weekly on Mondays at 04:00 UTC + on push/PR to main.

[![CodeQL](https://github.com/sodiq-code/vaultwatch/actions/workflows/codeql.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/codeql.yml)

---

## Run Instructions

VaultWatch has **two MCP servers** in addition to the API, pipeline, and dashboard:

```bash
# All services via Docker Compose
docker-compose up

# Individual services
python pipeline.py                                          # Agent pipeline (7 agents)
uvicorn api.main:app --reload --port 8000                   # REST API (29 endpoints)
python vaultwatch_mcp/server.py                              # General MCP server (20 tools)
python -m vaultwatch_rwa_mcp.server                          # RWA MCP server (39 tools)
cd dashboard && npm install && npm run dev                   # Dashboard (9 panels)
```

### MCP Servers

| Server | Tools | Transport | Source |
|--------|-------|-----------|--------|
| `vaultwatch_mcp` | 20 general tools | stdio / SSE | [`vaultwatch_mcp/server.py`](vaultwatch_mcp/server.py) |
| `vaultwatch_rwa_mcp` | 39 RWA-specific tools + 3 resources + 4 prompts | stdio | [`vaultwatch_rwa_mcp/server.py`](vaultwatch_rwa_mcp/server.py) |

The RWA MCP server reads via `query_global_state` + Odra decoders, writes via CSPR.click AgentWallet, and supports payable `open_vault` via x402.

```bash
# Introspection
python -m vaultwatch_rwa_mcp.server --list-tools

# stdio mode (for Claude Desktop integration)
python -m vaultwatch_rwa_mcp.server
```

---

## Docker Compose

A `docker-compose.yml` is included in the repo root, providing:

| Service | Port | Description |
|---------|------|-------------|
| `api` | 8000 | VaultWatch REST API (FastAPI + uvicorn) |
| `pipeline` | — | Agent pipeline (depends on healthy `api`) |
| `mcp` | 8080 | General MCP server |
| `dashboard` | 5173 | React dashboard (Vite dev server) |
| `otel-collector` | 4317/4318 | OpenTelemetry collector (optional, `--profile observability`) |

```bash
docker-compose up                                          # Core services
docker-compose --profile observability up                  # With OTel collector
```

All services use `CASPER_MOCK=true` by default in Docker, making on-chain writes opt-in.

---

## Contract Hashes (Current — July 11, 2026)

Deployer: `0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7`

Secondary deployer: `02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db`

| Contract | Package Hash | Deploy Hash | Gas (CSPR) | Named Key | Explorer |
|----------|-------------|------------|------------|-----------|---------|
| AuditTrail | `hash-7e653fc142ddd4f1759aec0c2f4fb0537eb167cfb9771d12c37ae55f29c270fa` | `b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6333a7` | 138.14 | `audit_trail_package_hash` | [View](https://testnet.cspr.live/deploy/b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6333a7) |
| RiskOracle | `hash-1a47fd766eb021aa83cc44b5a729920842253510936cbe9a1545bf6dc7c2e974` | `e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d` | 135.02 | `risk_oracle_package_hash` | [View](https://testnet.cspr.live/deploy/e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d) |
| SentinelCredit | `hash-47ea0c53777a68d79cf2f66b9171e4a1b588048c283b2b2504fc5ecfe1b686ae` | `0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71` | 143.32 | `sentinel_credit_package_hash` | [View](https://testnet.cspr.live/deploy/0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71) |
| SentinelRegistry | `hash-d97d1f1ef30bf765fbf13aa11817fea409b67056dd59faf6de28c94ad85a5f82` | `9a5eb4f83de8cbfef4f389516b977258b0e1d63179b288ca623a860fc6ec346c` | 138.17 | `sentinel_registry_package_hash` | [View](https://testnet.cspr.live/deploy/9a5eb4f83de8cbfef4f389516b977258b0e1d63179b288ca623a860fc6ec346c) |
| SentinelAlertLog | `hash-f75ce1bc111d185c39d7c81d5a18b093749643957b8c3ba3309613401fb14b78` | `53317e080ffdffcf097447ea3375c9195c6936fe7b1ed53795bf46134322a925` | 140.18 | `sentinel_alert_log_package_hash` | [View](https://testnet.cspr.live/deploy/53317e080ffdffcf097447ea3375c9195c6936fe7b1ed53795bf46134322a925) |
| AgentBehaviorIndex | `hash-d888dc3696046633582f1355f9708dfbd5acde3528466a562fa0601ad6eacbd2` | `05066c33ddb73b523ab8f67275ca6096254f9d1832e76075d1e5f41f188b7dd0` | 137.09 | `agent_behavior_index_package_hash` | [View](https://testnet.cspr.live/deploy/05066c33ddb73b523ab8f67275ca6096254f9d1832e76075d1e5f41f188b7dd0) |
| RiskPolicyManager | `hash-aaf7f48dbcdbd59996b9b181c7980bb6c5116a7c72005ce169b1619d94d7b2c4` | `93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e` | 136.94 | `risk_policy_manager_package_hash` | [View](https://testnet.cspr.live/deploy/93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e) |
| SubscriberVault | `hash-68c4b7cca84982833af3f9346a5a9ea337bfdcd20875bd82f4c7ec7b1505d211` | `6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d` | 143.39 | `subscriber_vault_package_hash` | [View](https://testnet.cspr.live/deploy/6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d) |

### Verification commands

Verify any deploy on-chain via the Casper RPC node (no auth required):

```bash
curl -s -X POST https://node.testnet.casper.network/rpc \
  -H 'Content-Type:application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"info_get_deploy","params":["b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6333a7"]}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result']['deploy']['execution_results'][0]['result']['Success'] and 'SUCCESS' or 'FAILED')"
```

Verify all 8 package hashes exist in the deployer's named_keys:

```bash
python3 scripts/verify_deploys.py \
  --deploy-hashes deploy_hashes_live.json \
  --account 0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7
```

### Full verification proof

[`proof/deploy_verification_results.json`](proof/deploy_verification_results.json) — multi-method verification (testnet.cspr.live browser + on-chain named_keys programmatic), all 8 contracts verified `true`.

---

## Verified Deploy Summary

| Category | Count | Status |
|----------|-------|--------|
| Contract installs | 8 | All SUCCESS |
| Contract interactions | 21 | All SUCCESS |
| Contract upgrades | 6 | All SUCCESS (RiskPolicyManager v1→v2) |
| x402 payments | 1 | SUCCESS (1 CSPR via SubscriberVault) |
| **Total** | **36** | **36/36 SUCCESS** |

Proof files:
- Installs: [`proof/deploy_verification_results.json`](proof/deploy_verification_results.json)
- Interactions: [`proof/interaction_hashes.json`](proof/interaction_hashes.json)
- Upgrades: [`proof/upgrade_hashes.json`](proof/upgrade_hashes.json)
- x402 payment: [`proof/x402_payment_hashes.json`](proof/x402_payment_hashes.json)
- Dual-path proof: [`proof/X402_DUAL_PATH_PROOF.md`](proof/X402_DUAL_PATH_PROOF.md)

---

## Project Structure

```
vaultwatch/
├── api/                    # FastAPI REST server (29 endpoints)
├── agents/                 # 7 AI agents + AgentWallet + MultiProviderClient
├── contracts/              # 8 Odra Rust contracts (9 source files + WASM)
├── dashboard/              # React + Vite 9-panel dashboard (Vercel)
├── docs/                   # Architecture, x402, reputation formula, upgrade demo
├── pipeline.py             # Agent orchestration pipeline
├── proof/                  # On-chain verification evidence
├── scripts/                # Deploy, verify, upgrade, x402, CSPR.click helpers
├── sdk/                    # Python SDK (pip install -e sdk/)
├── streaming/              # Casper Sidecar event client
├── tests/                  # 481 test definitions across 39 files
├── vaultwatch_mcp/         # General MCP server (20 tools)
├── vaultwatch_rwa_mcp/     # Domain RWA MCP server (39 tools + 3 resources + 4 prompts)
├── x402/                   # x402 dual-path implementation (Path A + Path B)
├── docker-compose.yml      # All services in one file
├── Dockerfile              # API + pipeline container
└── requirements.txt        # Python dependencies
```
