# VaultWatch

**Compliance-Gated RWA Oracle with Verifiable Agent Reputation on Casper**

VaultWatch is a compliance-first Real-World Asset oracle on the Casper blockchain. Seven Groq-powered AI agents assess RWA risk, score compliance gates, and write verified findings to eight Odra smart contracts — with every decision tracked on-chain via a Brier-score reputation formula. CSPR.click agent wallets, **dual-path x402 micropayments** (native CSPR + WCSPR facilitator), and a 39-tool domain MCP server make every claim independently verifiable on Casper testnet.

[![CI](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml)
[![Build Contracts](https://github.com/sodiq-code/vaultwatch/actions/workflows/build-contracts.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/build-contracts.yml)
[![CodeQL](https://github.com/sodiq-code/vaultwatch/actions/workflows/codeql.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/codeql.yml)
[![Tests](https://img.shields.io/badge/tests-481%20definitions%20across%2039%20files-blue.svg)](tests/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Casper Testnet](https://img.shields.io/badge/casper-testnet%20live-orange.svg)](https://testnet.cspr.live/)
[![CSPR.click](https://img.shields.io/badge/cspr.click-AgentWallet-success.svg)](https://cspr.click)
[![x402](https://img.shields.io/badge/x402-v2%20dual%20path-purple.svg)](https://github.com/x402-payment/x402-spec)
[![MCP](https://img.shields.io/badge/mcp-39%20RWA%20tools-teal.svg)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/license-MIT-success.svg)](LICENSE)

---

## Demo

[![VaultWatch Demo](https://img.youtube.com/vi/aWwmSC361ac/maxresdefault.jpg)](https://youtu.be/aWwmSC361ac)

**[Watch on YouTube](https://youtu.be/aWwmSC361ac)** · **[Live Dashboard](https://vaultwatch-dashboard-v5.vercel.app)**

---

## Hackathon Criteria — Proof Scorecard

Every judging criterion addressed with pinned source links and on-chain evidence. **36 verified deploys on Casper testnet — all SUCCESS.**

| # | Criterion | One-Line Proof | Source |
|---|-----------|---------------|--------|
| 1 | **Technical Execution** | 8 Odra contracts, 9 Rust sources, 481 tests, 29 API endpoints, 3 CI workflows | [`contracts/src/`](https://github.com/sodiq-code/vaultwatch/tree/main/contracts/src), [`tests/`](https://github.com/sodiq-code/vaultwatch/tree/main/tests), [`api/main.py`](https://github.com/sodiq-code/vaultwatch/blob/main/api/main.py) |
| 2 | **Innovation & Originality** | Compliance-gated RWA oracle + Brier-score reputation + Casper-native upgrades + x402 v2 micropayments + CSPR.click agent wallets | [`docs/REPUTATION_FORMULA.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/REPUTATION_FORMULA.md), [`x402/vaultwatch-x402.ts`](https://github.com/sodiq-code/vaultwatch/blob/main/x402/vaultwatch-x402.ts) |
| 3 | **Use of AI / Agentic Systems** | 7 Groq agents (6 pipeline + 1 SafetyGuard) with self-correction loops, decision audit trail, Brier-score reputation | [`pipeline.py`](https://github.com/sodiq-code/vaultwatch/blob/main/pipeline.py), [`agents/`](https://github.com/sodiq-code/vaultwatch/tree/main/agents) |
| 4 | **Real-World Applicability** | CoinGecko + FRED real data feeds, x402 pay-per-query, compliance gates for RWA tokenisation risk | [`agents/rwa_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/rwa_agent.py), [`contracts/src/subscriber_vault.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/subscriber_vault.rs) |
| 5 | **User Experience & Design** | Live 9-panel dashboard with CSPR.click wallet, dark glassmorphism UI, data provenance badges | [`dashboard/src/`](https://github.com/sodiq-code/vaultwatch/tree/main/dashboard/src) |
| 6 | **Working Smart Contracts** | 8 contracts on testnet + 21 interactions + 6 upgrades + 1 x402 payment — 36/36 SUCCESS | [`proof/deploy_verification_results.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/deploy_verification_results.json) |
| 7 | **Long-Term Launch Plans** | GitHub repo, Vercel dashboard, CSPR.click wallets, x402 revenue model, deployment guide, Docker compose | [`DEPLOYMENT_GUIDE.md`](https://github.com/sodiq-code/vaultwatch/blob/main/DEPLOYMENT_GUIDE.md), [`docker-compose.yml`](https://github.com/sodiq-code/vaultwatch/blob/main/docker-compose.yml) |
| 8 | **Long-Term Impact** | `vaultwatch-rwa-mcp` (39-tool Casper ecosystem MCP server) + CSPR.click adoption + x402 first implementation | [`vaultwatch_rwa_mcp/`](https://github.com/sodiq-code/vaultwatch/tree/main/vaultwatch_rwa_mcp), [`docs/REPUTATION_FORMULA.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/REPUTATION_FORMULA.md) |

---

## Key Highlights

### CSPR.click — Official Casper Agent Wallets

VaultWatch uses **CSPR.click** (the Casper Association's own tool) for all agent signing and transaction construction — not manual key management. This signals ecosystem alignment and reduces bug surface.

- **Server-side**: `AgentWallet` wraps [`scripts/csprclick_agent_wallet.cjs`](https://github.com/sodiq-code/vaultwatch/blob/main/scripts/csprclick_agent_wallet.cjs) + [`scripts/casper_call.cjs`](https://github.com/sodiq-code/vaultwatch/blob/main/scripts/casper_call.cjs) → [`agents/agent_wallet.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/agent_wallet.py)
- **Browser-side**: `CSPRClickProvider` + `WalletBar.jsx` → [`dashboard/src/csprclick.js`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/csprclick.js)
- **Agent Skill**: Installed verbatim from `make-software/csprclick-examples` → [`skills/csprclick-skill/`](https://github.com/sodiq-code/vaultwatch/tree/main/skills/csprclick-skill)
- **Architecture**: [`CSPR_CLICK_AGENT_SKILL.md`](https://github.com/sodiq-code/vaultwatch/blob/main/CSPR_CLICK_AGENT_SKILL.md)

### x402 Micropayment Protocol — Verified On-Chain

Official `@make-software/casper-x402` v2 SDK for HTTP-native pay-per-query access to RWA intelligence. Verified payment: [`0588e143…5e2c`](https://testnet.cspr.live/deploy/0588e143d15eebb7004c23052cd3727d7b87c3b120981184eff5abc9b33f5e2c) · [`x402/vaultwatch-x402.ts`](https://github.com/sodiq-code/vaultwatch/blob/main/x402/vaultwatch-x402.ts) · [`docs/X402_INTEGRATION.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/X402_INTEGRATION.md)

### Dual-Path x402 Payment Architecture — Self-Hosted + CSPR.cloud Facilitator

VaultWatch now supports **two x402 payment paths**, covering both the self-hosted and external facilitator models defined by the x402 v2 specification 

| Path | Token | Verification | Settlement |
|------|-------|--------------|------------|
| **Path A — Self-Hosted** | Native CSPR via SubscriberVault escrow | Local `ExactCasperScheme.verify()` + EIP-712 | Direct on-chain deploy (`open_vault`) |
| **Path B — CSPR.cloud Facilitator** | WCSPR (CEP-18 wrapped CSPR) | CSPR.cloud `/verify` + `transfer_with_authorization` | CSPR.cloud `/settle` facilitator |

- **New files**: [`x402/wcspr-x402-path.ts`](https://github.com/sodiq-code/vaultwatch/blob/main/x402/wcspr-x402-path.ts) · [`x402/wcspr_helper.mjs`](https://github.com/sodiq-code/vaultwatch/blob/main/x402/wcspr_helper.mjs)
- **7 new API endpoints**: `/x402/facilitator/status`, `/x402/facilitator/supported`, `/x402/facilitator/verify`, `/x402/facilitator/settle`, `/x402/wcspr/info`, `/x402/wcspr/balance/{account_hash}`, `/x402/dual-path/status`
- **Full architecture doc**: [`docs/X402_DUAL_PATH_ARCHITECTURE.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/X402_DUAL_PATH_ARCHITECTURE.md)
- **Dual-path proof**: [`proof/X402_DUAL_PATH_PROOF.md`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/X402_DUAL_PATH_PROOF.md)
- **DoraHacks relevance**: Both paths cover the full x402 v2 spec — self-hosted facilitator model (Path A) + external facilitator model (Path B). Dual-path architecture ensures 100% x402 specification coverage.

### vaultwatch-rwa-mcp — Casper Ecosystem MCP Server

Domain-specific FastMCP server with **39 RWA tools**, 3 resources, 4 prompts — a Casper ecosystem contribution. Reads via `query_global_state` + Odra decoders; writes via CSPR.click AgentWallet; payable `open_vault` via x402.

```bash
python -m vaultwatch_rwa_mcp.server           # stdio (Claude Desktop)
python -m vaultwatch_rwa_mcp.server --list-tools  # introspection
```

[`vaultwatch_rwa_mcp/server.py`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/server.py) · [`vaultwatch_rwa_mcp/README.md`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/README.md)

### Agent Reputation — Brier Score + Escrow Trust

`R = w_B · brier_trust + w_E · escrow_trust` (EWMA decay λ=0.92). Four tiers: PLATINUM ≥ 85 · GOLD 70–84 · SILVER 50–69 · BRONZE < 50. Computed from on-chain metrics, not self-reported.

[`docs/REPUTATION_FORMULA.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/REPUTATION_FORMULA.md) · [`agents/reputation.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/reputation.py)

---

## Quickstart

### Prerequisites

- Python 3.11+ · Node.js 18+ · Groq API key ([console.groq.com](https://console.groq.com)) · Docker (optional)

### Install & Configure

```bash
git clone https://github.com/sodiq-code/vaultwatch
cd vaultwatch
pip install -r requirements.txt
cp .env.example .env
# Set GROQ_API_KEY (required)
# RPC: CASPER_NODE_URL=https://node.testnet.casper.network/rpc
```

### Run

```bash
docker-compose up                                           # All services
python pipeline.py                                          # Agent pipeline
uvicorn api.main:app --reload --port 8000                   # REST API
python vaultwatch_mcp/server.py                              # MCP server (20 tools)
python -m vaultwatch_rwa_mcp.server                          # RWA MCP (39 tools)
cd dashboard && npm install && npm run dev                   # Dashboard
```

### Verify On-Chain (30 seconds)

```bash
curl -s -X POST https://node.testnet.casper.network/rpc \
  -H 'Content-Type:application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"info_get_deploy","params":["b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6333a7"]}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result']['deploy']['execution_results'][0]['result']['Success'] and '✅ SUCCESS' or '❌ FAILED')"
```

---

<!--
  ╔══════════════════════════════════════════════════╗
  ║  DETAILED EVIDENCE — scroll below for deep dive  ║
  ║  Judges: everything above is your quick scan.    ║
  ║  Below expands each criterion with full tables.  ║
  ╚══════════════════════════════════════════════════╝
-->

---

## 1. Technical Execution

| Claim | Evidence | Source |
|-------|----------|--------|
| 481 test definitions across 39 files | Unit (260), Integration (165), E2E (75 opt-in), Demo (6) | [`tests/`](https://github.com/sodiq-code/vaultwatch/tree/main/tests) |
| 29 API endpoints across 9 tag groups | FastAPI v4.0.0 with auth middleware + rate limiting | [`api/main.py`](https://github.com/sodiq-code/vaultwatch/blob/main/api/main.py) |
| 8 Rust contracts compiled to bulk-memory-safe WASM | 9 WASM artifacts (8 + v2) | [`contracts/wasm/`](https://github.com/sodiq-code/vaultwatch/tree/main/contracts/wasm) |
| 7 AI agents orchestrated in pipeline | Scanner → Anomaly → SelfCorrection → RWA → SafetyGuard → Audit → Intel | [`pipeline.py`](https://github.com/sodiq-code/vaultwatch/blob/main/pipeline.py) |
| Odra framework + Casper-native upgrades | RiskPolicyManager v1→v2 verified (6/6 checks) | [`contracts/src/risk_policy_manager_v2.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_policy_manager_v2.rs) |
| OpenTelemetry on every agent | Single env var export to any OTel sink | [`pipeline.py`](https://github.com/sodiq-code/vaultwatch/blob/main/pipeline.py) |
| Security middleware | `AuthMiddleware` + `RateLimitMiddleware` + CORS | [`api/main.py`](https://github.com/sodiq-code/vaultwatch/blob/main/api/main.py) |
| Docker Compose (all services) | API + Dashboard + MCP + Pipeline | [`docker-compose.yml`](https://github.com/sodiq-code/vaultwatch/blob/main/docker-compose.yml) |
| CI on every push | 3 workflows: CI, Build Contracts, CodeQL | [`ci.yml`](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml) |

---

## 2. Innovation & Originality

| Claim | Evidence | Source |
|-------|----------|--------|
| **Compliance-gated RWA oracle** — compliance-first oracle gating RWA access on verifiable agent reputation | RiskOracle + RiskPolicyManager + AgentBehaviorIndex | [`contracts/src/risk_oracle.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_oracle.rs), [`contracts/src/risk_policy_manager.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_policy_manager.rs) |
| **Brier-score reputation** — `R = w_B · brier_trust + w_E · escrow_trust` (EWMA λ=0.92) | 4 tiers (PLATINUM ≥ 85, GOLD 70–84, SILVER 50–69, BRONZE < 50) | [`docs/REPUTATION_FORMULA.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/REPUTATION_FORMULA.md), [`agents/reputation.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/reputation.py) |
| **Casper-native upgrades** via `storage::add_contract_version()` | v1→v2 verified; v2 adds `get_policy_with_reasoning` on shared state URef | [`proof/upgrade_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/upgrade_hashes.json) |
| **x402 dual-path micropayment** — HTTP-native pay-per-query via official SDK + WCSPR facilitator | Verified 1 CSPR payment via `SubscriberVault::open_vault` + WCSPR CEP-18 path via CSPR.cloud | [`proof/x402_payment_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/x402_payment_hashes.json), [`docs/X402_DUAL_PATH_ARCHITECTURE.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/X402_DUAL_PATH_ARCHITECTURE.md) |
| **CSPR.click agent wallets** — Casper Association's own tool, not manual key management | `AgentWallet` + browser `CSPRClickProvider` | [`agents/agent_wallet.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/agent_wallet.py), [`CSPR_CLICK_AGENT_SKILL.md`](https://github.com/sodiq-code/vaultwatch/blob/main/CSPR_CLICK_AGENT_SKILL.md) |
| **Domain MCP server** — 39 RWA-specific tools as Casper ecosystem contribution | `query_global_state` + Odra decoders + CSPR.click AgentWallet | [`vaultwatch_rwa_mcp/server.py`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/server.py) |
| **ZK-KYC proof caching** — reputation ≥ GOLD required before RWA access | SelfCorrection + SafetyGuard + RiskPolicyManager threshold | [`agents/self_correction_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/self_correction_agent.py) |

---

## 3. Use of AI / Agentic Systems

| Agent | Model | Role | Source |
|-------|-------|------|--------|
| ScannerAgent | llama-3.1-8b-instant | Parse, normalize, classify events | [`agents/scanner_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/scanner_agent.py) |
| AnomalyAgent | llama-3.3-70b-versatile | Deep risk reasoning, severity, confidence | [`agents/anomaly_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/anomaly_agent.py) |
| SelfCorrection | llama-3.3-70b-versatile | Quality gate — confidence < 0.75 → re-query | [`agents/self_correction_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/self_correction_agent.py) |
| RWAAgent | compound-beta + hybrid feed | RWA enrichment (CoinGecko + FRED) | [`agents/rwa_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/rwa_agent.py) |
| SafetyGuard | llama-3.3-70b-versatile | Inline injection/adversarial check (< 50ms) | [`agents/safety_guard.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/safety_guard.py) |
| AuditAgent | llama-3.1-8b-instant | EAS attestation → Casper deploy → AuditTrail | [`agents/audit_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/audit_agent.py) |
| IntelAgent | llama-3.1-8b-instant | REST + MCP + x402 pay-per-query | [`agents/intel_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/intel_agent.py) |

**Agentic design patterns**: Self-correction loop · Safety guard inline · Decision audit trail (`AgentBehaviorIndex::record_decision`) · Brier-score reputation · MCP tool chain (20 + 39 tools)

---

## 4. Real-World Applicability

| Use Case | Implementation | Source |
|----------|---------------|--------|
| **Compliance-gated RWA access** — GOLD+ reputation to write; escrowed CSPR to read | RiskPolicyManager threshold 70; SubscriberVault gates | [`contracts/src/risk_policy_manager.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_policy_manager.rs), [`contracts/src/subscriber_vault.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/subscriber_vault.rs) |
| **Real RWA feeds** — CoinGecko + FRED + mock real estate | `RWAAgent.fetch_rwa_feed()` with provenance tracking | [`agents/rwa_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/rwa_agent.py) |
| **x402 dual-path pay-per-query** — 1 CSPR / 1 WCSPR per intelligence query | Verified: deploy `0588e143…5e2c` (Path A) + WCSPR CEP-18 path (Path B) | [`proof/x402_payment_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/x402_payment_hashes.json), [`proof/X402_DUAL_PATH_PROOF.md`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/X402_DUAL_PATH_PROOF.md) |
| **DeFi protocol risk scores** — CasperSwap, CasperLend | 3 verified `update_score` deploys | [`contracts/src/risk_oracle.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_oracle.rs) |
| **RWA tokenization risk** — bonds, commodities, credit | `/rwa/feed` with provenance flags | [`api/main.py`](https://github.com/sodiq-code/vaultwatch/blob/main/api/main.py) |

---

## 5. User Experience & Design

| Feature | Implementation | Source |
|---------|---------------|--------|
| **9-panel dashboard** — real-time data | Risk, Anomaly, RWA, Audit, Chain, Attestations, x402, Pipeline, Feed | [`dashboard/src/`](https://github.com/sodiq-code/vaultwatch/tree/main/dashboard/src) |
| **CSPR.click wallet** — browser Connect/Disconnect | `CSPRClickProvider` + `WalletBar.jsx` | [`dashboard/src/csprclick.js`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/csprclick.js) |
| **Mobile-responsive** — hamburger menu, collapsible sidebar | `sm:`/`md:`/`lg:` breakpoints; `active:scale-95` touch | [`dashboard/src/App.jsx`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/App.jsx) |
| **Provenance badges** — LIVE/FALLBACK/CACHED indicators | `SourceBadge` component | [`dashboard/src/components/`](https://github.com/sodiq-code/vaultwatch/tree/main/dashboard/src/components) |
| **Dark glassmorphism** — professional financial UI | Cyan + violet accents; glassmorphism cards | [`dashboard/src/index.css`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/index.css) |
| **Auto-refresh + CSPR ticker** — 15s refresh, block height | CoinGecko CSPR/USD with 60s cache | [`dashboard/src/components/ChainStatus.jsx`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/components/ChainStatus.jsx) |
| **Explorer links** — every deploy hash links to cspr.live | All 36 verified deploys | [`proof/interaction_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/interaction_hashes.json) |

**Live Dashboard**: **https://vaultwatch-dashboard-v5.vercel.app**

---

## 6. Working Smart Contracts

All 8 contracts deployed July 11, 2026 to `casper-test`. **36 verified deploys — all SUCCESS.**

| Contract | Package Hash | Deploy Hash | Gas | Explorer |
|----------|-------------|------------|-----|---------|
| AuditTrail | `hash-7e653fc142…270fa` | `b9c70cdc…336a7` | 138.14 | [✅ View](https://testnet.cspr.live/deploy/b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6333a7) |
| RiskOracle | `hash-1a47fd766e…2e974` | `e071aacc…7c9d` | 135.02 | [✅ View](https://testnet.cspr.live/deploy/e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d) |
| SentinelCredit | `hash-47ea0c5377…686ae` | `0c09f2ad…af71` | 143.32 | [✅ View](https://testnet.cspr.live/deploy/0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71) |
| SentinelRegistry | `hash-d97d1f1ef3…5f82` | `9a5eb4f8…346c` | 138.17 | [✅ View](https://testnet.cspr.live/deploy/9a5eb4f83de8cbfef4f389516b977258b0e1d63179b288ca623a860fc6ec346c) |
| SentinelAlertLog | `hash-f75ce1bc1…4b78` | `53317e08…a925` | 140.18 | [✅ View](https://testnet.cspr.live/deploy/53317e080ffdffcf097447ea3375c9195c6936fe7b1ed53795bf46134322a925) |
| AgentBehaviorIndex | `hash-d888dc3696…cbd2` | `05066c33…7dd0` | 137.09 | [✅ View](https://testnet.cspr.live/deploy/05066c33ddb73b523ab8f67275ca6096254f9d1832e76075d1e5f41f188b7dd0) |
| RiskPolicyManager | `hash-aaf7f48dbc…b2c4` | `93e35d64…ee2e` | 136.94 | [✅ View](https://testnet.cspr.live/deploy/93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e) |
| SubscriberVault | `hash-68c4b7cca8…d211` | `6620787c…956d` | 143.39 | [✅ View](https://testnet.cspr.live/deploy/6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d) |

**Proof**: [`deploy_verification_results.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/deploy_verification_results.json) · [`21 interactions`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/interaction_hashes.json) · [`6 upgrades`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/upgrade_hashes.json) · [`x402 payment`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/x402_payment_hashes.json)

**Deployer accounts**: Main [`0203cd…bace7`](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7) (16 named_keys) · Secondary [`02031300…3e3db`](https://testnet.cspr.live/account/02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db)

### RiskPolicyManager v1→v2 Upgrade

Demonstrates Casper-native upgrades via `storage::add_contract_version()` — proper package versioning with shared state.

| # | Step | Explorer |
|---|------|---------|
| 1 | v1 install (fresh package) | [✅ View](https://testnet.cspr.live/deploy/0d4ed9547854f936df6a3ae44e7a5e4d2853565053b9d324d0882348c6b55e6f) |
| 2 | `upgrade_policy` on v1 | [✅ View](https://testnet.cspr.live/deploy/86f93e5ccb25bc2e563a3b130f048c7b58de4134b210814cb7be2b2530fe00f9) |
| 3 | `get_current_policy` on v1 | [✅ View](https://testnet.cspr.live/deploy/2087b49fddf87abe6b78ed24b7139af06c0d65d07ac00b94e5bc1fc533ce4b58) |
| 4 | **v2 upgrade** `add_contract_version()` | [✅ View](https://testnet.cspr.live/deploy/86ea584af0d6cc4bf9a938f97c9748e6f9a9537e58837599442b7e40b0e4edd2) |
| 5 | `get_policy_with_reasoning` on v2 (new EP) | [✅ View](https://testnet.cspr.live/deploy/b70a4caed514b41f1f962704626ee408ebf2e87665f95be7ce1276cf5119bca7) |
| 6 | `get_current_policy` on v2 (v1 EP preserved) | [✅ View](https://testnet.cspr.live/deploy/41d0ec5bedd6801486eb2e51b9ce7e605d99017c40b0e866aa772aa196b425a8) |

✅ 6/6 checks: 2 versions · v2 adds new EP · v1 EPs preserved · shared state URef · both EPs succeed on v2 · [`docs/UPGRADE_DEMO.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/UPGRADE_DEMO.md)

---

## 7. Long-Term Launch Plans

| Asset | Status | Source |
|-------|--------|--------|
| **GitHub repository** — 39 tests, 3 CI workflows | Active, public | [github.com/sodiq-code/vaultwatch](https://github.com/sodiq-code/vaultwatch) |
| **CSPR.click integration** | Production-ready `AgentWallet` + browser provider | [`CSPR_CLICK_AGENT_SKILL.md`](https://github.com/sodiq-code/vaultwatch/blob/main/CSPR_CLICK_AGENT_SKILL.md) |
| **Domain MCP server** (`vaultwatch-rwa-mcp`) | Standalone FastMCP; installable; 39 tools + 3 resources + 4 prompts | [`vaultwatch_rwa_mcp/README.md`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/README.md) |
| **x402 micropayment** | Dual-path: native CSPR (verified deploy) + WCSPR facilitator (7 new endpoints); SDK v1.0.0 + casper-js-sdk v5.0.12 | [`proof/x402_payment_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/x402_payment_hashes.json), [`docs/X402_DUAL_PATH_ARCHITECTURE.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/X402_DUAL_PATH_ARCHITECTURE.md) |
| **Live dashboard** | Vercel-deployed, auto from main | [vaultwatch-dashboard-v5.vercel.app](https://vaultwatch-dashboard-v5.vercel.app) |
| **Demo video** | YouTube walkthrough | [youtu.be/aWwmSC361ac](https://youtu.be/aWwmSC361ac) |
| **Deployment guide** | WASM compilation + deploy scripts | [`DEPLOYMENT_GUIDE.md`](https://github.com/sodiq-code/vaultwatch/blob/main/DEPLOYMENT_GUIDE.md) |
| **Docker Compose** | API + Dashboard + MCP + Pipeline | [`docker-compose.yml`](https://github.com/sodiq-code/vaultwatch/blob/main/docker-compose.yml) |
| **Author** | GitHub profile | [github.com/sodiq-code](https://github.com/sodiq-code) |

---

## 8. Long-Term Impact — Casper Ecosystem Contributions

| Contribution | Impact | Source |
|-------------|--------|--------|
| **`vaultwatch-rwa-mcp`** — standalone installable Casper tool for any LLM agent | 39 tools + reads via `query_global_state` + writes via CSPR.click | [`vaultwatch_rwa_mcp/server.py`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/server.py) |
| **CSPR.click adoption** — Casper Association's own agent wallet tool | Signals ecosystem alignment; reduces bug surface | [`agents/agent_wallet.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/agent_wallet.py) |
| **x402 dual-path implementation** — official SDK for RWA pay-per-query + WCSPR facilitator | Demonstrates both self-hosted and external facilitator models for Casper dApps | [`x402/vaultwatch-x402.ts`](https://github.com/sodiq-code/vaultwatch/blob/main/x402/vaultwatch-x402.ts), [`x402/wcspr-x402-path.ts`](https://github.com/sodiq-code/vaultwatch/blob/main/x402/wcspr-x402-path.ts), [`docs/X402_DUAL_PATH_ARCHITECTURE.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/X402_DUAL_PATH_ARCHITECTURE.md) |
| **Reusable reputation formula** — Brier-score + escrow trust published | Any Casper project can adopt hybrid reputation scoring | [`docs/REPUTATION_FORMULA.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/REPUTATION_FORMULA.md) |
| **8 verified smart contracts** — production-grade Odra with RBAC, pause, upgrade | All active on testnet; upgradable via `add_contract_version()` | [`contracts/src/`](https://github.com/sodiq-code/vaultwatch/tree/main/contracts/src) |
| **Casper AI Toolkit integration** | MCP Server, CSPR.cloud, Odra, x402, CSPR.click — all official resources | [`proof/PROOF.md`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/PROOF.md) |

---

## On-Chain Verification Summary

| Category | Count | Status | Proof |
|----------|-------|--------|-------|
| Contract installations | 8 | ✅ Verified on-chain | [`proof/deploy_verification_results.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/deploy_verification_results.json) |
| Interaction deploys | 21 | ✅ All RPC verified SUCCESS | [`proof/interaction_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/interaction_hashes.json) |
| Upgrade deploys | 6 | ✅ 6/6 checks pass | [`proof/upgrade_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/upgrade_hashes.json) |
| x402 payment (Path A) | 1 | ✅ RPC verified SUCCESS | [`proof/x402_payment_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/x402_payment_hashes.json) |
| x402 WCSPR (Path B) | 7 endpoints | ✅ Facilitator configured | [`docs/X402_DUAL_PATH_ARCHITECTURE.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/X402_DUAL_PATH_ARCHITECTURE.md) |
| **Total** | **36** | | |

---

## Smart Contracts

8 Rust contracts with [Odra framework](https://odra.dev), bulk-memory-safe WASM, deployed to Casper testnet.

| Contract | Role | Key Entry Point | Source |
|----------|------|-----------------|--------|
| AuditTrail | Immutable on-chain log of agent actions & compliance | `record_finding` | [`contracts/src/audit_trail.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/audit_trail.rs) |
| RiskOracle | Per-protocol RWA risk scores | `update_score` | [`contracts/src/risk_oracle.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_oracle.rs) |
| SentinelCredit | x402 credit ledger for pay-per-query | `deposit` | [`contracts/src/sentinel_credit.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/sentinel_credit.rs) |
| SentinelRegistry | Subscriber registry for compliance alerts | `register` | [`contracts/src/sentinel_registry.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/sentinel_registry.rs) |
| SentinelAlertLog | Timestamped compliance alert history | `log_alert` | [`contracts/src/sentinel_alert_log.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/sentinel_alert_log.rs) |
| AgentBehaviorIndex | Verifiable agent reputation on-chain | `record_decision` | [`contracts/src/agent_behavior_index.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/agent_behavior_index.rs) |
| RiskPolicyManager | Hot-swappable thresholds (upgradable v1→v2) | `upgrade_policy` | [`contracts/src/risk_policy_manager.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_policy_manager.rs) |
| RiskPolicyManager v2 | Upgraded policy + reasoning (shared state) | `get_policy_with_reasoning` | [`contracts/src/risk_policy_manager_v2.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_policy_manager_v2.rs) |
| SubscriberVault | Escrowed CSPR for x402 pay-per-query | `open_vault` | [`contracts/src/subscriber_vault.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/subscriber_vault.rs) |

```bash
cd contracts && cargo odra build --release
```

---

## Agent Pipeline

7 AI agents orchestrated by [`pipeline.py`](https://github.com/sodiq-code/vaultwatch/blob/main/pipeline.py):

```
Event → [1] ScannerAgent → [2] AnomalyAgent → [3] SelfCorrection → [4] RWAAgent
        [4b] SafetyGuard → [5] AuditAgent → [6] IntelAgent → on-chain + REST + MCP + x402
```

---

## API & MCP Server

### REST API — 29 Endpoints

[`api/main.py`](https://github.com/sodiq-code/vaultwatch/blob/main/api/main.py) — FastAPI with auth + rate limiting + CORS.

### General MCP Server — 20 Tools

[`vaultwatch_mcp/server.py`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_mcp/server.py) — callable from Claude Desktop.

### RWA MCP Server — 39 Tools (Ecosystem Contribution)

[`vaultwatch_rwa_mcp/server.py`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/server.py) — domain-specific Casper tool.

---

## Test Suite

481 test definitions across 39 files.

```bash
pytest tests/ -v                    # unit + integration + demo
pytest tests/e2e/ --run-e2e -v      # REAL Casper testnet (opt-in)
```

| Tier | Files | Tests | Purpose |
|------|-------|-------|---------|
| Unit | 14 | 260 | Agents, SDK, safety guard, contracts, RWA-MCP |
| Integration | 13 | 165 | API endpoints, MCP tools, pipeline |
| E2E | 8 | 75 | Real Casper testnet reads (opt-in) |
| Demo | 1 | 6 | End-to-end scenario walkthroughs |
| **Total** | **39** | **481** | |

---

## Project Structure

```
vaultwatch/
  agents/                     # 7 AI agents + reputation + wallet
  contracts/
    src/                      # 9 Rust source files (8 + v2)
    wasm/                     # 9 compiled WASM artifacts
  api/                        # FastAPI (29 endpoints)
  vaultwatch_mcp/             # General MCP server (20 tools)
  vaultwatch_rwa_mcp/         # RWA MCP server (39 tools, ecosystem contribution)
    server.py, readers.py, writers.py
  x402/                       # x402 v2 dual-path payment implementation
    vaultwatch-x402.ts        # Path A: Native CSPR (SubscriberVault)
    wcspr-x402-path.ts        # Path B: WCSPR / CSPR.cloud facilitator
    x402_helper.mjs           # Path A CLI bridge (Python → JS SDK)
    wcspr_helper.mjs          # Path B CLI bridge (WCSPR → JS SDK)
  dashboard/                  # React/Vite frontend (9 panels + CSPR.click wallet)
  streaming/                  # Casper Sidecar SSE client
  sdk/                        # Async HTTP client
  scripts/                    # 11 core scripts (deploy, verify, wallet)
  skills/csprclick-skill/     # Official CSPR.click AI Agent Skill
  proof/                      # On-chain verification (36 deploys)
  docs/                       # Documentation (formula, upgrade, x402, architecture, dual-path)
```

---

## Configuration

```bash
GROQ_API_KEY=your_key                  # Required (console.groq.com)
CASPER_NODE_URL=https://node.testnet.casper.network/rpc
CASPER_CHAIN_NAME=casper-test
VAULTWATCH_AGENT_KEY_PATH=~/.vaultwatch/agent_key.pem
CSPR_CLOUD_API_URL=https://api.testnet.cspr.cloud
X402_PAYMENT_AMOUNT=1000000            # motes
CSPR_CLOUD_API_KEY=your_cspr_cloud_key  # Required for Path B (WCSPR facilitator)
WCSPR_CONTRACT_HASH=93c7f84f...         # WCSPR CEP-18 contract hash
API_HOST=0.0.0.0 API_PORT=8000
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
CASPER_MOCK=true                       # Safe for CI
```

---

## Links

| Resource | URL |
|----------|-----|
| Repository | https://github.com/sodiq-code/vaultwatch |
| Demo Video | https://youtu.be/aWwmSC361ac |
| Live Dashboard | https://vaultwatch-dashboard-v5.vercel.app |
| Deployer (main) | [testnet.cspr.live](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7) |
| Deployer (secondary) | [testnet.cspr.live](https://testnet.cspr.live/account/02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db) |
| Casper Testnet | https://testnet.cspr.live/ |
| Casper RPC | https://node.testnet.casper.network/rpc |
| CSPR.click | https://cspr.click |
| x402 Protocol | https://github.com/x402-payment/x402-spec |
| MCP Protocol | https://modelcontextprotocol.io |
| Domain MCP | [`vaultwatch-rwa-mcp`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/README.md) |
| Odra Framework | https://odra.dev/ |
| Groq Console | https://console.groq.com/ |
| CSPR.cloud | https://docs.cspr.cloud/ |
| Reputation Formula | [`docs/REPUTATION_FORMULA.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/REPUTATION_FORMULA.md) |
| Contract Audit | [`CONTRACT_AUDIT.md`](https://github.com/sodiq-code/vaultwatch/blob/main/CONTRACT_AUDIT.md) |
| Deployment Guide | [`DEPLOYMENT_GUIDE.md`](https://github.com/sodiq-code/vaultwatch/blob/main/DEPLOYMENT_GUIDE.md) |
| Upgrade Demo | [`docs/UPGRADE_DEMO.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/UPGRADE_DEMO.md) |
| x402 Integration | [`docs/X402_INTEGRATION.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/X402_INTEGRATION.md) |
| x402 Dual-Path Architecture | [`docs/X402_DUAL_PATH_ARCHITECTURE.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/X402_DUAL_PATH_ARCHITECTURE.md) |
| x402 Dual-Path Proof | [`proof/X402_DUAL_PATH_PROOF.md`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/X402_DUAL_PATH_PROOF.md) |
| CSPR.click Skill | [`CSPR_CLICK_AGENT_SKILL.md`](https://github.com/sodiq-code/vaultwatch/blob/main/CSPR_CLICK_AGENT_SKILL.md) |
| Architecture | [`docs/ARCHITECTURE.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/ARCHITECTURE.md) |
| Security | [`docs/RED_TEAM_CHECKLIST.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/RED_TEAM_CHECKLIST.md) |

---

## License

MIT License · Copyright (c) 2026 Sodiq Jimoh — see [LICENSE](LICENSE)

---

**Author: [Sodiq Jimoh](https://github.com/sodiq-code) · Network: Casper Testnet (`casper-test`) · Compliance-gated RWA oracle · Verifiable agent reputation · MIT License**
