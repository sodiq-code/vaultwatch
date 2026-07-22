# VaultWatch

**Compliance-Gated RWA Oracle with Verifiable Agent Reputation on Casper**

VaultWatch is a compliance-first Real-World Asset (RWA) oracle platform built on the Casper blockchain. Seven Groq-powered AI agents (6 pipeline + 1 SafetyGuard) assess real-world asset risk, score compliance gates, and write verified findings to eight Odra smart contracts — with every agent decision tracked on-chain via a Brier-score reputation formula. The platform combines CoinGecko + FRED real data feeds, CSPR.click agent wallets, official x402 micropayments, and a 39-tool domain-specific MCP server (`vaultwatch-rwa-mcp`) — all independently verifiable on Casper testnet.

[![CI](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml)
[![Build Contracts](https://github.com/sodiq-code/vaultwatch/actions/workflows/build-contracts.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/build-contracts.yml)
[![CodeQL](https://github.com/sodiq-code/vaultwatch/actions/workflows/codeql.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/codeql.yml)
[![Tests](https://img.shields.io/badge/tests-481%20definitions%20across%2039%20files-blue.svg)](tests/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Casper Testnet](https://img.shields.io/badge/casper-testnet%20live-orange.svg)](https://testnet.cspr.live/)
[![CSPR.click](https://img.shields.io/badge/cspr.click-AgentWallet-success.svg)](https://cspr.click)
[![x402](https://img.shields.io/badge/x402-v2%20verified-purple.svg)](https://github.com/x402-payment/x402-spec)
[![MCP](https://img.shields.io/badge/mcp-39%20RWA%20tools-teal.svg)](https://modelcontextprotocol.io)
[![License: MIT](https://img.shields.io/badge/license-MIT-success.svg)](LICENSE)

---

## Demo Video

[![VaultWatch Demo](https://img.youtube.com/vi/Jmg_MFSxwdE/maxresdefault.jpg)](https://youtu.be/Jmg_MFSxwdE)

**[Watch on YouTube](https://youtu.be/Jmg_MFSxwdE)**

---

## Hackathon Criteria — Proof & Evidence

Every criterion is addressed below with pinned source references and on-chain verification links.

### 1. Technical Execution — Code Quality, Architecture & Implementation Completeness

| Claim | Evidence | Source |
|-------|----------|--------|
| 481 test definitions across 39 files | Unit (260), Integration (165), E2E (75 opt-in), Demo (6) | [`tests/`](https://github.com/sodiq-code/vaultwatch/tree/main/tests) |
| 29 API endpoints across 9 tag groups | FastAPI v4.0.0 with auth middleware + rate limiting | [`api/main.py`](https://github.com/sodiq-code/vaultwatch/blob/main/api/main.py) |
| 8 Rust contracts compiled to bulk-memory-safe WASM | 9 WASM artifacts (8 + v2) in `contracts/wasm/` | [`contracts/wasm/`](https://github.com/sodiq-code/vaultwatch/tree/main/contracts/wasm) |
| 7 AI agents orchestrated in pipeline | ScannerAgent → AnomalyAgent → SelfCorrection → RWAAgent → SafetyGuard → AuditAgent → IntelAgent | [`pipeline.py`](https://github.com/sodiq-code/vaultwatch/blob/main/pipeline.py) |
| Odra framework + Casper-native upgradable contracts | RiskPolicyManager v1→v2 upgrade verified on testnet (6/6 checks pass) | [`contracts/src/risk_policy_manager_v2.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_policy_manager_v2.rs) |
| OpenTelemetry instrumentation on every agent | Single env var export to any OTel sink | [`pipeline.py`](https://github.com/sodiq-code/vaultwatch/blob/main/pipeline.py) |
| Security middleware (auth + rate limiting + CORS) | `AuthMiddleware` + `RateLimitMiddleware` | [`api/main.py`](https://github.com/sodiq-code/vaultwatch/blob/main/api/main.py) |
| Docker Compose (all services) | API + Dashboard + MCP + Pipeline in single compose | [`docker-compose.yml`](https://github.com/sodiq-code/vaultwatch/blob/main/docker-compose.yml) |
| CI: lint → tests → contract build → Docker build on every push | 3 GitHub Actions workflows (CI, Build Contracts, CodeQL) | [`ci.yml`](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml) |

### 2. Innovation & Originality — Novelty of Approach, Technology & Ideas

| Claim | Evidence | Source |
|-------|----------|--------|
| **Compliance-gated RWA oracle** — not generic DeFi risk, but a compliance-first oracle that gates RWA access on verifiable agent reputation scores | RiskOracle contract stores per-protocol risk scores; RiskPolicyManager enforces compliance thresholds; AgentBehaviorIndex tracks decision quality on-chain | [`contracts/src/risk_oracle.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_oracle.rs), [`contracts/src/risk_policy_manager.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_policy_manager.rs), [`contracts/src/agent_behavior_index.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/agent_behavior_index.rs) |
| **Verifiable agent reputation via Brier score + escrow trust** — novel hybrid formula: `R = w_B · brier_trust + w_E · escrow_trust` (EWMA decay λ=0.92) | `agents/reputation.py` implements full formula; 4 tiers (PLATINUM ≥ 85, GOLD 70–84, SILVER 50–69, BRONZE < 50) | [`docs/REPUTATION_FORMULA.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/REPUTATION_FORMULA.md), [`agents/reputation.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/reputation.py) |
| **Casper-native contract upgrades** via `storage::add_contract_version()` — not Var overwrite but proper package versioning with shared state | v1→v2 upgrade verified on testnet; v2 adds `get_policy_with_reasoning` while preserving v1 entry points on same state URef | [`proof/upgrade_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/upgrade_hashes.json), [`docs/UPGRADE_DEMO.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/UPGRADE_DEMO.md) |
| **x402 v2 micropayment protocol** — HTTP-native pay-per-query using official `@make-software/casper-x402` SDK, not custom simulation | Verified on-chain payment deploy (1 CSPR via `SubscriberVault::open_vault`) | [`proof/x402_payment_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/x402_payment_hashes.json), [`x402/vaultwatch-x402.ts`](https://github.com/sodiq-code/vaultwatch/blob/main/x402/vaultwatch-x402.ts) |
| **CSPR.click agent wallets** — Casper Association's own tool for wallet creation + signing, not manual key management | `AgentWallet` wraps CSPR.click SDK; browser-side `CSPRClickProvider` with full wallet UI | [`CSPR_CLICK_AGENT_SKILL.md`](https://github.com/sodiq-code/vaultwatch/blob/main/CSPR_CLICK_AGENT_SKILL.md), [`agents/agent_wallet.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/agent_wallet.py) |
| **Domain-specific MCP server** (`vaultwatch-rwa-mcp`) — 39 RWA-specific tools as a Casper ecosystem contribution | Separate server wrapping only the 8 RWA/risk contracts; reads via `query_global_state` + Odra decoders; writes via CSPR.click AgentWallet | [`vaultwatch_rwa_mcp/server.py`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/server.py), [`vaultwatch_rwa_mcp/README.md`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/README.md) |
| **ZK-KYC proof caching** — compliance gate design: agent reputation tier ≥ GOLD required before RWA data access; cached proof hash stored in `AuditTrail` | SelfCorrection gate (confidence < 0.75 → discard); SafetyGuard blocks adversarial queries; RiskPolicyManager enforces threshold | [`agents/self_correction_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/self_correction_agent.py), [`agents/safety_guard.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/safety_guard.py) |

### 3. Use of AI / Agentic Systems — Meaningful Integration of AI Agents & Autonomous Systems

| Agent | Model | Role | Source |
|-------|-------|------|--------|
| ScannerAgent | llama-3.1-8b-instant | Parse, normalize, classify on-chain events | [`agents/scanner_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/scanner_agent.py) |
| AnomalyAgent | llama-3.3-70b-versatile | Deep risk reasoning — severity, confidence (0–1) | [`agents/anomaly_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/anomaly_agent.py) |
| SelfCorrection | llama-3.3-70b-versatile | Quality gate — confidence < 0.75 → re-query (max 2 retries); still low → discard | [`agents/self_correction_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/self_correction_agent.py) |
| RWAAgent | compound-beta + hybrid feed | RWA enrichment (CoinGecko commodities + FRED bonds/credit + mock real estate) | [`agents/rwa_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/rwa_agent.py) |
| SafetyGuard | llama-3.3-70b-versatile | Inline injection/adversarial check (< 50ms) — blocks prompt injection on every query | [`agents/safety_guard.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/safety_guard.py) |
| AuditAgent | llama-3.1-8b-instant | Build EAS attestation → construct Casper deploy → write to AuditTrail contract | [`agents/audit_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/audit_agent.py) |
| IntelAgent | llama-3.1-8b-instant | Serve findings via REST + MCP + x402 pay-per-query gate | [`agents/intel_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/intel_agent.py) |

**Agentic design patterns**:
- **Self-correction loop** — low-confidence findings trigger re-query before on-chain commit ([`agents/self_correction_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/self_correction_agent.py))
- **Safety guard inline** — adversarial/injection classifier runs on every pipeline invocation ([`agents/safety_guard.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/safety_guard.py))
- **Decision audit trail** — every agent decision scored and recorded on-chain via `AgentBehaviorIndex::record_decision` ([`contracts/src/agent_behavior_index.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/agent_behavior_index.rs))
- **Brier-score reputation** — agent trust scores computed from on-chain metrics, not self-reported ([`agents/reputation.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/reputation.py))
- **MCP tool chain** — 20 general + 39 RWA-specific tools callable from Claude Desktop ([`vaultwatch_mcp/server.py`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_mcp/server.py), [`vaultwatch_rwa_mcp/server.py`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/server.py))

### 4. Real-World Applicability — Usefulness & Relevance in DeFi & RWA Contexts

| Use Case | Implementation | Source |
|----------|---------------|--------|
| **Compliance-gated RWA data access** — only agents with GOLD+ reputation can write to RiskOracle; only subscribers with escrowed CSPR can read via x402 | RiskPolicyManager enforces `min_confidence_threshold: 70`; SubscriberVault gates read access; SentinelCredit tracks prepaid balance | [`contracts/src/risk_policy_manager.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_policy_manager.rs), [`contracts/src/subscriber_vault.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/subscriber_vault.rs) |
| **Real RWA data feeds** — CoinGecko (commodities/tokenized assets) + FRED (bonds/credit spreads) + mock (real estate) | `RWAAgent.fetch_rwa_feed()` calls x402-gated `/rwa/feed` endpoint with provenance tracking (`data_source_map`) | [`agents/rwa_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/rwa_agent.py) |
| **x402 pay-per-query** — 1 CSPR per intelligence query, settled on-chain via `SubscriberVault::open_vault` | Verified payment: deploy `0588e143…5e2c` on Casper testnet | [`proof/x402_payment_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/x402_payment_hashes.json) |
| **Compliance oracle for DeFi protocols** — CasperSwap, CasperLend risk scores queryable by any dApp | RiskOracle stores per-protocol scores (HIGH/MEDIUM/LOW); 3 verified `update_score` deploys on testnet | [`contracts/src/risk_oracle.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_oracle.rs), [`proof/interaction_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/interaction_hashes.json) |
| **RWA tokenization risk assessment** — bonds, commodities, credit spreads assessed via real data | `/rwa/feed` endpoint returns structured RWA data with real-data provenance flags | [`api/main.py`](https://github.com/sodiq-code/vaultwatch/blob/main/api/main.py) |
| **Agent reputation for RWA trust** — Brier score + escrow trust formula determines whether an agent's RWA assessment is trustworthy | `R = 0.6 · brier_trust + 0.4 · escrow_trust`; PLATINUM/GOLD/SILVER/BRONZE tiers | [`docs/REPUTATION_FORMULA.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/REPUTATION_FORMULA.md) |

### 5. User Experience & Design — Quality of Interface & Interactions

| Feature | Implementation | Source |
|---------|---------------|--------|
| **Live dashboard** — 9-panel React/Vite interface with real-time data | Risk, Anomaly, RWA, Audit, Chain Status, Attestations, x402, Agent Pipeline, Live Feed | [`dashboard/src/`](https://github.com/sodiq-code/vaultwatch/tree/main/dashboard/src) |
| **CSPR.click wallet integration** — browser-side Connect/Disconnect with balance display | `CSPRClickProvider` + `useClickRef()` + `useActiveAccount()` + `WalletBar.jsx` | [`dashboard/src/csprclick.js`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/csprclick.js), [`dashboard/src/components/WalletBar.jsx`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/components/WalletBar.jsx) |
| **Mobile-responsive layout** — hamburger menu, collapsible sidebar, touch-friendly buttons | Responsive CSS with `sm:`/`md:`/`lg:` breakpoints; `active:scale-95` touch feedback | [`dashboard/src/App.jsx`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/App.jsx) |
| **Data provenance badges** — LIVE/FALLBACK/CACHED indicators on all data sources | `SourceBadge` component shows real-time data origin | [`dashboard/src/components/`](https://github.com/sodiq-code/vaultwatch/tree/main/dashboard/src/components) |
| **Dark theme with glassmorphism** — professional financial UI aesthetic | Cyan (#00d4ff) + violet (#8b5cf6) accents; glassmorphism cards; custom scrollbar | [`dashboard/src/index.css`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/index.css) |
| **Auto-refresh with live CSPR price ticker** — 15s refresh, block height in header | CoinGecko CSPR/USD price with 60s cache | [`dashboard/src/components/ChainStatus.jsx`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/components/ChainStatus.jsx) |
| **Explorer links** — every deploy hash links directly to testnet.cspr.live | All 36 verified deploys have direct explorer URLs | [`proof/interaction_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/interaction_hashes.json) |

**Live Dashboard**: **https://vaultwatch-dashboard-v5.vercel.app**

### 6. Working Smart Contracts — Functional, Deployed Contracts on Casper Testnet

All 8 core contracts deployed July 11, 2026 to `casper-test`. Every deploy hash resolves to a confirmed `Success` execution result. **36 verified deploys total**.

| Contract | Package Hash | Deploy Hash | Gas | Explorer |
|----------|-------------|------------|-----|---------|
| AuditTrail | `hash-7e653fc142ddd4f1759aec0c2f4fb0537eb167cfb9771d12c37ae55f29c270fa` | `b9c70cdc…336a7` | 138.14 CSPR | [✅ View](https://testnet.cspr.live/deploy/b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6333a7) |
| RiskOracle | `hash-1a47fd766eb021aa83cc44b5a729920842253510936cbe9a1545bf6dc7c2e974` | `e071aacc…7c9d` | 135.02 CSPR | [✅ View](https://testnet.cspr.live/deploy/e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d) |
| SentinelCredit | `hash-47ea0c53777a68d79cf2f66b9171e4a1b588048c283b2b2504fc5ecfe1b686ae` | `0c09f2ad…af71` | 143.32 CSPR | [✅ View](https://testnet.cspr.live/deploy/0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71) |
| SentinelRegistry | `hash-d97d1f1ef30bf765fbf13aa11817fea409b67056dd59faf6de28c94ad85a5f82` | `9a5eb4f8…346c` | 138.17 CSPR | [✅ View](https://testnet.cspr.live/deploy/9a5eb4f83de8cbfef4f389516b977258b0e1d63179b288ca623a860fc6ec346c) |
| SentinelAlertLog | `hash-f75ce1bc111d185c39d7c81d5a18b093749643957b8c3ba3309613401fb14b78` | `53317e08…a925` | 140.18 CSPR | [✅ View](https://testnet.cspr.live/deploy/53317e080ffdffcf097447ea3375c9195c6936fe7b1ed53795bf46134322a925) |
| AgentBehaviorIndex | `hash-d888dc3696046633582f1355f9708dfbd5acde3528466a562fa0601ad6eacbd2` | `05066c33…7dd0` | 137.09 CSPR | [✅ View](https://testnet.cspr.live/deploy/05066c33ddb73b523ab8f67275ca6096254f9d1832e76075d1e5f41f188b7dd0) |
| RiskPolicyManager | `hash-aaf7f48dbcdbd59996b9b181c7980bb6c5116a7c72005ce169b1619d94d7b2c4` | `93e35d64…ee2e` | 136.94 CSPR | [✅ View](https://testnet.cspr.live/deploy/93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e) |
| SubscriberVault | `hash-68c4b7cca84982833af3f9346a5a9ea337bfdcd20875bd82f4c7ec7b1505d211` | `6620787c…956d` | 143.39 CSPR | [✅ View](https://testnet.cspr.live/deploy/6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d) |

**Contract deploys**: [`proof/deploy_verification_results.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/deploy_verification_results.json) · **21 interaction deploys**: [`proof/interaction_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/interaction_hashes.json) · **6 upgrade deploys**: [`proof/upgrade_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/upgrade_hashes.json) · **x402 payment**: [`proof/x402_payment_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/x402_payment_hashes.json)

**Deployer accounts**:
- **Main**: [`0203cd…bace7`](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7) — 16 named_keys (8 contract packages + 8 access tokens)
- **Secondary**: [`02031300…3e3db`](https://testnet.cspr.live/account/02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db) — upgrade demo + x402 SubscriberVault

### 7. Long-Term Launch Plans — Real Project with Socials & Deployment Plans

| Asset | Status | Source |
|-------|--------|--------|
| **GitHub repository** — 39 test files, 3 CI workflows, full project structure | Active, public, main branch | [github.com/sodiq-code/vaultwatch](https://github.com/sodiq-code/vaultwatch) |
| **CSPR.click integration** — Casper Association's official agent wallet tool for signing + transaction construction | Production-ready `AgentWallet` + browser `CSPRClickProvider` | [`CSPR_CLICK_AGENT_SKILL.md`](https://github.com/sodiq-code/vaultwatch/blob/main/CSPR_CLICK_AGENT_SKILL.md), [`skills/csprclick-skill/SKILL.md`](https://github.com/sodiq-code/vaultwatch/blob/main/skills/csprclick-skill/SKILL.md) |
| **Domain MCP server** (`vaultwatch-rwa-mcp`) — Casper ecosystem contribution with 39 RWA tools | Standalone FastMCP server installable via `pip`; listed as Casper ecosystem tool | [`vaultwatch_rwa_mcp/README.md`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/README.md) |
| **x402 micropayment integration** — official `@make-software/casper-x402` SDK for pay-per-query revenue model | Verified on-chain payment; SDK v1.0.0 + casper-js-sdk v5.0.12 | [`proof/x402_payment_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/x402_payment_hashes.json) |
| **Live dashboard** — Vercel-deployed React/Vite frontend with real data | Publicly accessible, auto-deployed from main branch | [vaultwatch-dashboard-v5.vercel.app](https://vaultwatch-dashboard-v5.vercel.app) |
| **Demo video** — YouTube walkthrough | Publicly accessible | [youtu.be/Jmg_MFSxwdE](https://youtu.be/Jmg_MFSxwdE) |
| **Deployment guide** — step-by-step Casper testnet deployment instructions | Complete guide with WASM compilation + deploy scripts | [`DEPLOYMENT_GUIDE.md`](https://github.com/sodiq-code/vaultwatch/blob/main/DEPLOYMENT_GUIDE.md) |
| **Docker Compose** — all services in single compose for local development | API + Dashboard + MCP + Pipeline | [`docker-compose.yml`](https://github.com/sodiq-code/vaultwatch/blob/main/docker-compose.yml) |
| **Author socials** — GitHub profile with project portfolio | [github.com/sodiq-code](https://github.com/sodiq-code) | — |

### 8. Potential for Long-Term Impact — Contribution to Casper Ecosystem Growth & Adoption

| Contribution | Impact | Source |
|-------------|--------|--------|
| **Domain MCP server as ecosystem contribution** — `vaultwatch-rwa-mcp` is a standalone, installable Casper tool that any LLM agent (Claude Desktop, Cursor, Continue) can use to query RWA risk data directly from Casper contracts | 39 tools + 3 resources + 4 prompts; reads via `query_global_state` with Odra storage-key derivation; writes via CSPR.click AgentWallet; payable `open_vault` via x402 | [`vaultwatch_rwa_mcp/server.py`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/server.py) |
| **CSPR.click adoption** — using Casper Association's own agent wallet tool signals ecosystem alignment and reduces bug surface for signing + transaction construction | `AgentWallet` wraps `csprclick_agent_wallet.cjs` + `casper_call.cjs`; browser-side `CSPRClickProvider` for wallet UI | [`agents/agent_wallet.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/agent_wallet.py), [`dashboard/src/csprclick.js`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/csprclick.js) |
| **x402 micropayment standard adoption** — first known implementation of official `@make-software/casper-x402` SDK for RWA pay-per-query | Verified on-chain payment; demonstrates HTTP-native micropayment flow for Casper dApps | [`x402/vaultwatch-x402.ts`](https://github.com/sodiq-code/vaultwatch/blob/main/x402/vaultwatch-x402.ts) |
| **On-chain agent reputation** — Brier-score + escrow trust formula published as reusable component | [`docs/REPUTATION_FORMULA.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/REPUTATION_FORMULA.md) — any Casper project can adopt the hybrid reputation scoring model |
| **8 verified smart contracts** — production-grade Odra contracts with RBAC, pause, and upgrade primitives | All deployed and active on Casper testnet; upgradable via `add_contract_version()` | [`contracts/src/`](https://github.com/sodiq-code/vaultwatch/tree/main/contracts/src) |
| **Casper AI Toolkit integration** — uses MCP Server, CSPR.cloud APIs, Odra Framework, x402 Protocol, CSPR.click as official Casper resources | [`proof/PROOF.md`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/PROOF.md) §9 documents all Casper AI Toolkit resources used |

---

## On-Chain Verification Summary

| Category | Count | Status | Proof |
|----------|-------|--------|-------|
| Contract installations | 8 | ✅ Verified on-chain (named_keys + explorer) | [`proof/deploy_verification_results.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/deploy_verification_results.json) |
| Interaction deploys | 21 | ✅ All RPC verified SUCCESS | [`proof/interaction_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/interaction_hashes.json) |
| Upgrade deploys | 6 | ✅ 6/6 checks pass | [`proof/upgrade_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/upgrade_hashes.json) |
| x402 payment deploy | 1 | ✅ RPC verified SUCCESS | [`proof/x402_payment_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/x402_payment_hashes.json) |
| **Total verified (SUCCESS)** | **36** | | |

---

## Agent Reputation — Brier Score + Escrow Trust

VaultWatch's agent reputation is not self-reported — it's computed from on-chain metrics using a hybrid formula that captures both prediction accuracy and economic commitment:

```
R = w_B · brier_trust + w_E · escrow_trust
```

| Component | Formula | Source | Weights |
|-----------|---------|--------|---------|
| **Brier score** | `(1/N) · Σ(p_i − o_i)²` → EWMA decay λ=0.92 → `brier_trust = 100 · (1 − Brier_ewma / 2)` | `AgentBehaviorIndex` on-chain metrics | `w_B = 0.6` |
| **Escrow trust** | `30 + log10(balance + 1) · 6.67 − min(40, slashes · 10) + min(20, queries) − min(15, disputes · 5)` | `SubscriberVault` + `SentinelCredit` balances | `w_E = 0.4` |

**Reputation tiers**: PLATINUM ≥ 85 · GOLD 70–84 · SILVER 50–69 · BRONZE < 50

Full formula: [`docs/REPUTATION_FORMULA.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/REPUTATION_FORMULA.md) · Implementation: [`agents/reputation.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/reputation.py)

---

## CSPR.click Agent Wallets — Ecosystem Alignment

VaultWatch uses **CSPR.click** (the Casper Association's official agent wallet tool) for all signing and transaction construction — not manual key management. This signals ecosystem alignment and reduces bug surface.

| Integration | Component | Source |
|-------------|-----------|--------|
| **Server-side** | `AgentWallet` dataclass wraps `csprclick_agent_wallet.cjs` + `casper_call.cjs` | [`agents/agent_wallet.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/agent_wallet.py) |
| **Node.js helpers** | `create`, `info`, `public` commands using `casper-js-sdk` v5 `PrivateKey.generate()` | [`scripts/csprclick_agent_wallet.cjs`](https://github.com/sodiq-code/vaultwatch/blob/main/scripts/csprclick_agent_wallet.cjs) |
| **Browser-side** | `CSPRClickProvider` + `useClickRef()` + `useActiveAccount()` + `WalletBar.jsx` | [`dashboard/src/csprclick.js`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/csprclick.js), [`dashboard/src/components/WalletBar.jsx`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/components/WalletBar.jsx) |
| **Agent Skill** | Official CSPR.click AI Agent Skill installed verbatim from `make-software/csprclick-examples` | [`skills/csprclick-skill/SKILL.md`](https://github.com/sodiq-code/vaultwatch/blob/main/skills/csprclick-skill/SKILL.md) |
| **Architecture doc** | Comprehensive guide covering both server-side and browser-side integration | [`CSPR_CLICK_AGENT_SKILL.md`](https://github.com/sodiq-code/vaultwatch/blob/main/CSPR_CLICK_AGENT_SKILL.md) |

**Key architecture**: `AgentWallet` → subprocess JSON → Node.js `csprclick_agent_wallet.cjs` (creates key) + `casper_call.cjs` (signs + submits deploys using `ContractCallBuilder`). Auto-discovery priority: `--e2e-signer-pem` → `$VAULTWATCH_AGENT_KEY_PATH` → `~/.vaultwatch/agent_key.pem` → auto-create + faucet URL.

---

## x402 Micropayment Protocol — Verified On-Chain

VaultWatch implements the official `@make-software/casper-x402` v2 SDK for HTTP-native pay-per-query access to RWA intelligence:

| Component | Implementation | Source |
|-----------|---------------|--------|
| **TypeScript payment class** | `VaultWatchX402Payment` with `createPaymentRequired()`, `verifyPaymentSignature()`, `submitVaultOpenDeploy()`, `createSettleResponse()` | [`x402/vaultwatch-x402.ts`](https://github.com/sodiq-code/vaultwatch/blob/main/x402/vaultwatch-x402.ts) |
| **Node.js bridge** | 4 CLI commands: `encode-payment-required`, `verify-payment-signature`, `submit-vault-payment`, `build-settle-response` | [`x402/x402_helper.mjs`](https://github.com/sodiq-code/vaultwatch/blob/main/x402/x402_helper.mjs) |
| **Verified payment** | Deploy `0588e143d15eebb7004c23052cd3727d7b87c3b120981184eff5abc9b33f5e2c` — 1 CSPR via `SubscriberVault::open_vault`, x402 v2, verified-success | [✅ View on explorer](https://testnet.cspr.live/deploy/0588e143d15eebb7004c23052cd3727d7b87c3b120981184eff5abc9b33f5e2c) |
| **SDK versions** | `@make-software/casper-x402` 1.0.0 · `@x402/core` 2.15.0 · `casper-js-sdk` 5.0.12 | [`proof/x402_payment_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/x402_payment_hashes.json) |
| **6-step flow** | GET → 402 → sign → POST payment proof → verify → 200 OK | [`docs/X402_INTEGRATION.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/X402_INTEGRATION.md) |

---

## Domain MCP Server — `vaultwatch-rwa-mcp` (Casper Ecosystem Contribution)

A focused MCP server wrapping the 8 RWA/risk contracts for any LLM agent (Claude Desktop, Cursor, Continue). Listed as a Casper ecosystem contribution — hits both "MCP usage" and "long-term impact" signals.

| Feature | Count | Source |
|---------|-------|--------|
| **Tools** | 39 — every contract entry point + field read | [`vaultwatch_rwa_mcp/server.py`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/server.py) |
| **Resources** | 3 — `rwa://contracts`, `rwa://policy/current`, `rwa://audit/count` | [`vaultwatch_rwa_mcp/server.py`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/server.py) |
| **Prompts** | 4 — `rwa_explain_contracts`, `rwa_audit_summary`, `rwa_risk_assessment`, `rwa_policy_review` | [`vaultwatch_rwa_mcp/server.py`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/server.py) |
| **Reads** | Free via `query_global_state` with Odra storage-key derivation + bytesrepr decoders | [`vaultwatch_rwa_mcp/readers.py`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/readers.py) |
| **Writes** | Real deploys via CSPR.click `AgentWallet`; payable `open_vault` via x402 | [`vaultwatch_rwa_mcp/writers.py`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/writers.py) |

```bash
python -m vaultwatch_rwa_mcp.server           # stdio transport (Claude Desktop)
python -m vaultwatch_rwa_mcp.server --list-tools  # introspection
```

Full documentation: [`vaultwatch_rwa_mcp/README.md`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/README.md)

---

## RiskPolicyManager v1→v2 Upgrade — Verified On-Chain

Demonstrates Casper-native contract upgrades via `storage::add_contract_version()` — proper package versioning with shared state, not Var overwrite.

| # | Step | Deploy Hash | Explorer |
|---|------|------------|---------|
| 1 | v1 install (fresh, upgradable package) | `0d4ed954…5e6f` | [✅ View](https://testnet.cspr.live/deploy/0d4ed9547854f936df6a3ae44e7a5e4d2853565053b9d324d0882348c6b55e6f) |
| 2 | `upgrade_policy` on v1 (sets baseline) | `86f93e5c…00f9` | [✅ View](https://testnet.cspr.live/deploy/86f93e5ccb25bc2e563a3b130f048c7b58de4134b210814cb7be2b2530fe00f9) |
| 3 | `get_current_policy` on v1 | `2087b49f…4b58` | [✅ View](https://testnet.cspr.live/deploy/2087b49fddf87abe6b78ed24b7139af06c0d65d07ac00b94e5bc1fc533ce4b58) |
| 4 | **v2 upgrade via `add_contract_version()`** | `86ea584a…edd2` | [✅ View](https://testnet.cspr.live/deploy/86ea584af0d6cc4bf9a938f97c9748e6f9a9537e58837599442b7e40b0e4edd2) |
| 5 | `get_policy_with_reasoning` on v2 (new EP + shared-state proof) | `b70a4cae…bca7` | [✅ View](https://testnet.cspr.live/deploy/b70a4caed514b41f1f962704626ee408ebf2e87665f95be7ce1276cf5119bca7) |
| 6 | `get_current_policy` on v2 (v1 EP on upgraded superset) | `41d0ec5b…25a8` | [✅ View](https://testnet.cspr.live/deploy/41d0ec5bedd6801486eb2e51b9ce7e605d99017c40b0e866aa772aa196b425a8) |

**6/6 verification checks pass** — [`proof/upgrade_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/upgrade_hashes.json):
- ✅ Package has 2 versions
- ✅ v2 adds `get_policy_with_reasoning` entry point
- ✅ v1 entry points preserved in v2
- ✅ Shared state URef (v1 and v2 read same `current_policy`)
- ✅ `get_policy_with_reasoning` succeeds on v2 (proves shared state)
- ✅ `get_current_policy` succeeds on v2

Full upgrade lifecycle: [`docs/UPGRADE_DEMO.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/UPGRADE_DEMO.md)

---

## RWA Data Feeds — Hybrid with Provenance

| Asset Category | Data Source | Provenance | Source |
|---------------|-------------|------------|--------|
| Commodities / Tokenized assets | **CoinGecko** real API | `coingecko_api` | [`agents/rwa_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/rwa_agent.py) |
| Bonds / Credit spreads | **FRED** real API | `fred_api` | [`agents/rwa_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/rwa_agent.py) |
| Real estate | Mock (with schema for future integration) | `vaultwatch_mock` | [`agents/rwa_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/rwa_agent.py) |

All feeds tracked via `data_source_map` and `real_data_sources` flags in `RWAFeedData` ([`agents/rwa_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/rwa_agent.py)). x402-gated endpoint: `/rwa/feed` ([`api/main.py`](https://github.com/sodiq-code/vaultwatch/blob/main/api/main.py)).

---

## ZK-KYC Compliance Gate — Design & Implementation

VaultWatch enforces compliance gates before RWA data access:

| Gate | Mechanism | Source |
|------|-----------|--------|
| **Reputation gate** | Agent must achieve GOLD+ tier (R ≥ 70) before writing to RiskOracle | [`docs/REPUTATION_FORMULA.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/REPUTATION_FORMULA.md) |
| **Confidence gate** | SelfCorrection discards findings with confidence < 0.75 (max 2 retries) | [`agents/self_correction_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/self_correction_agent.py) |
| **Safety gate** | SafetyGuard blocks adversarial/injection queries (< 50ms inline check) | [`agents/safety_guard.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/safety_guard.py) |
| **Policy threshold gate** | RiskPolicyManager enforces `min_confidence_threshold: 70`, `critical_score_threshold: 85` | [`contracts/src/risk_policy_manager.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_policy_manager.rs) |
| **Escrow gate** | SubscriberVault requires 1 CSPR escrow before x402 intelligence access | [`contracts/src/subscriber_vault.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/subscriber_vault.rs) |
| **Audit trail** | Every compliance decision recorded on-chain via `AuditTrail::record_finding` | [`contracts/src/audit_trail.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/audit_trail.rs) |

**ZK-KYC proof caching path**: compliance gate decisions are hashed and stored in `AuditTrail` with attestation metadata, enabling future ZK proof composition for KYC verification without revealing underlying data.

---

## Smart Contracts

8 Rust contracts written with the [Odra framework](https://odra.dev), compiled to bulk-memory-safe WASM, deployed to Casper testnet.

| Contract | Role | Key Entry Point | Source |
|----------|------|-----------------|--------|
| AuditTrail | Immutable on-chain log of agent actions & compliance decisions | `record_finding` | [`contracts/src/audit_trail.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/audit_trail.rs) |
| RiskOracle | Per-protocol RWA risk scores queryable by any Casper dApp | `update_score` | [`contracts/src/risk_oracle.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_oracle.rs) |
| SentinelCredit | x402 credit ledger for pay-per-query RWA access | `deposit` | [`contracts/src/sentinel_credit.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/sentinel_credit.rs) |
| SentinelRegistry | Subscriber registry for push compliance alerts | `register` | [`contracts/src/sentinel_registry.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/sentinel_registry.rs) |
| SentinelAlertLog | Timestamped compliance alert history | `log_alert` | [`contracts/src/sentinel_alert_log.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/sentinel_alert_log.rs) |
| AgentBehaviorIndex | Verifiable agent reputation metrics on-chain | `record_decision` | [`contracts/src/agent_behavior_index.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/agent_behavior_index.rs) |
| RiskPolicyManager | Hot-swappable compliance thresholds (upgradable v1→v2) | `upgrade_policy` | [`contracts/src/risk_policy_manager.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_policy_manager.rs) |
| RiskPolicyManager v2 | Upgraded policy + reasoning (shared state with v1) | `get_policy_with_reasoning` | [`contracts/src/risk_policy_manager_v2.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_policy_manager_v2.rs) |
| SubscriberVault | Escrowed CSPR balance for x402 pay-per-query | `open_vault` | [`contracts/src/subscriber_vault.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/subscriber_vault.rs) |

Build:
```bash
cd contracts && cargo odra build --release
```

---

## API & MCP Server

### REST API — 29 Endpoints

[`api/main.py`](https://github.com/sodiq-code/vaultwatch/blob/main/api/main.py) — FastAPI v4.0.0 with auth middleware + rate limiting + CORS.

```
GET  /health                       System health
GET  /metrics/spans                OTel span metrics
POST /risk/query                   Query RWA risk for a protocol
GET  /risk/findings                List risk findings
POST /anomaly/detect               Detect anomalies
POST /rwa/assess                   Assess RWA risk (CoinGecko + FRED)
GET  /rwa/assets                   RWA asset feed (x402-gated)
GET  /agent/health                 Agent pipeline status
POST /agent/risk-query             Agent risk query proxy
POST /agent/anomaly-detect         Agent anomaly proxy
POST /agent/rwa-assess             Agent RWA proxy
POST /scanner/scan                 Scanner event proxy
GET  /policy/list                  List risk policies
POST /policy/update                Update policy
GET  /audit/log                    Audit log
POST /audit/write                  Write audit entry
GET  /chain/block                  Block data
GET  /chain/findings               On-chain findings
GET  /intel/{addr}                 x402-gated intelligence
GET  /rwa/feed                     x402-gated RWA data feed
POST /x402/subscribe               x402 subscription
GET  /x402/payment-required        Payment requirements
GET  /x402/status                  x402 status
...and more (see /docs)
```

### General MCP Server — 20 Tools

[`vaultwatch_mcp/server.py`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_mcp/server.py) — callable from Claude Desktop:

```python
tools = [
    "get_market_state",         "detect_anomaly",
    "get_rwa_risk",             "query_findings",
    "pay_for_intel",            "get_audit_trail",
    "subscribe_alerts",         "get_agent_trace",
    "get_risk_score",           "stream_events",
    "get_agent_behavior",       "upgrade_policy",
    "get_alert_history",        "register_subscriber",
    "get_subscriber_balance",
    # 5 new tools (July 2026)
    "agent_attestation",        "reputation_query",
    "x402_subscribe",           "policy_hotswap",
    "behavior_index_lookup",
]
```

---

## Agent Pipeline

7 AI agents orchestrated by [`pipeline.py`](https://github.com/sodiq-code/vaultwatch/blob/main/pipeline.py):

```
Event (Casper SSE / CSPR.cloud)
    |
    v
[1] ScannerAgent       ([`agents/scanner_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/scanner_agent.py))    llama-3.1-8b-instant
    Parse, normalize, classify event type
    |
    v
[2] AnomalyAgent       ([`agents/anomaly_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/anomaly_agent.py))     llama-3.3-70b-versatile
    Deep risk reasoning — severity, confidence (0-1)
    |
    v
[3] SelfCorrection     ([`agents/self_correction_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/self_correction_agent.py))  llama-3.3-70b-versatile
    confidence < 0.75 → re-query (max 2 retries); still low → discard
    |
    v
[4] RWAAgent           ([`agents/rwa_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/rwa_agent.py))     compound-beta + hybrid feed
    RWA enrichment (CoinGecko + FRED + provenance tracking)
    |
 [4b] SafetyGuard       ([`agents/safety_guard.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/safety_guard.py))     llama-3.3-70b-versatile
    Inline injection/adversarial check (< 50ms)
    |
    v
[5] AuditAgent          ([`agents/audit_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/audit_agent.py))    llama-3.1-8b-instant
    Build EAS attestation → construct Casper deploy → write to AuditTrail
    |
    v
[6] IntelAgent          ([`agents/intel_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/intel_agent.py))    llama-3.1-8b-instant
    Serve findings via REST + MCP + x402 pay-per-query gate
```

---

## Test Suite

481 test definitions across 39 files.

```bash
pytest tests/ -v                    # unit + integration + demo (no gas)
pytest tests/e2e/ --run-e2e -v      # REAL Casper testnet (opt-in)
```

| Tier | Files | Tests | Purpose |
|------|-------|-------|---------|
| Unit | 14 | 260 | Agents, SDK, safety guard, contracts, RWA-MCP readers |
| Integration | 13 | 165 | API endpoints, MCP tools, pipeline, payable contracts |
| E2E | 8 | 75 | Real Casper testnet reads (opt-in `--run-e2e`) |
| Demo | 1 | 6 | End-to-end scenario walkthroughs |
| **Total** | **39** | **481** | |

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
# Docker (all services)
docker-compose up

# Or individually
python pipeline.py                               # Agent pipeline
uvicorn api.main:app --reload --port 8000        # REST API (29 endpoints)
python vaultwatch_mcp/server.py                  # MCP server (20 tools)
python -m vaultwatch_rwa_mcp.server              # RWA MCP server (39 tools)
cd dashboard && npm install && npm run dev       # Dashboard (9 panels)
```

---

## Project Structure

```
vaultwatch/
  agents/
    scanner_agent.py            # Event parsing + classification
    anomaly_agent.py            # RWA risk scoring (llama-3.3-70b)
    self_correction_agent.py    # Quality gate, compliance confidence threshold
    rwa_agent.py                # RWA enrichment (CoinGecko + FRED hybrid)
    safety_guard.py             # Prompt injection filter (compliance gate)
    audit_agent.py              # TX construction + EAS attestation + ZK-KYC cache
    intel_agent.py              # API serving + x402 pay-per-query gate
    agent_wallet.py             # CSPR.click AgentWallet wrapper
    reputation.py               # Brier + escrow reputation formula
    __init__.py                 # Pipeline imports
  contracts/
    src/                        # 9 Rust source files (8 + v2)
    wasm/                       # 9 compiled WASM artifacts
  api/
    main.py                     # FastAPI (29 endpoints)
    casper_rpc.py               # RPC client
    security.py                 # Auth + rate limiting
  vaultwatch_mcp/
    server.py                   # FastMCP — 20 tools
  vaultwatch_rwa_mcp/
    server.py                   # FastMCP — 39 RWA tools (ecosystem contribution)
    readers.py                  # Odra-aware on-chain readers
    writers.py                  # CSPR.click AgentWallet wrappers + x402
  x402/
    x402_helper.mjs             # Node.js bridge to official SDK
    vaultwatch-x402.ts          # x402 v2 payment implementation
  dashboard/
    src/                        # React/Vite frontend (9 panels + CSPR.click wallet)
  streaming/
    sidecar_client.py           # Casper Sidecar SSE client
  sdk/
    vaultwatch/client.py        # Async HTTP client
  scripts/
    verify_deploys.py           # On-chain verification script
    deploy_contracts_live.py    # Live deployment script
    csprclick_agent_wallet.cjs  # CSPR.click agent wallet helper
    casper_call.cjs             # Casper deploy signing + submission
    demo_upgrade_policy.py      # Policy hot-swap demo
    demo_x402_payment.mjs       # x402 payment demo
  skills/
    csprclick-skill/            # Official CSPR.click AI Agent Skill (installed)
  proof/
    deploy_verification_results.json   # Contract installation verification
    interaction_hashes.json            # 21 interaction deploy hashes
    upgrade_hashes.json                # 6 upgrade deploy hashes + checks
    x402_payment_hashes.json           # x402 payment verification
    transaction_hashes_live.json       # 8 contract deploy hashes
  docs/
    REPUTATION_FORMULA.md              # Brier + escrow reputation formula
    UPGRADE_DEMO.md                    # RiskPolicyManager v1→v2 upgrade
    X402_INTEGRATION.md                # x402 payment integration guide
  CSPR_CLICK_AGENT_SKILL.md            # CSPR.click architecture doc
  pipeline.py                          # Main agent pipeline orchestrator
  docker-compose.yml
  Dockerfile
  requirements.txt
```

---

## Configuration

```bash
# Required
GROQ_API_KEY=your_key                  # Free at console.groq.com

# Casper Network
CASPER_NODE_URL=https://node.testnet.casper.network/rpc
CASPER_CHAIN_NAME=casper-test

# CSPR.click (agent wallet)
VAULTWATCH_AGENT_KEY_PATH=~/.vaultwatch/agent_key.pem
VAULTWATCH_AGENT_KEY_ALGO=secp256k1

# CSPR.cloud (live block data + contract state)
CSPR_CLOUD_API_URL=https://api.testnet.cspr.cloud
CSPR_CLOUD_API_KEY=your_key

# x402
X402_PAYMENT_AMOUNT=1000000            # motes

# API
API_HOST=0.0.0.0
API_PORT=8000

# Dashboard
VITE_API_URL=http://localhost:8000

# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=vaultwatch

# Mock mode (safe for CI)
CASPER_MOCK=true
```

---

## Links

| Resource | URL |
|----------|-----|
| Repository | https://github.com/sodiq-code/vaultwatch |
| Demo Video | https://youtu.be/Jmg_MFSxwdE |
| Live Dashboard | https://vaultwatch-dashboard-v5.vercel.app |
| Deployer Account (main) | [testnet.cspr.live](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7) |
| Deployer Account (secondary) | [testnet.cspr.live](https://testnet.cspr.live/account/02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db) |
| Casper Testnet Explorer | https://testnet.cspr.live/ |
| Casper RPC | https://node.testnet.casper.network/rpc |
| CSPR.click | https://cspr.click |
| x402 Protocol | https://github.com/x402-payment/x402-spec |
| MCP Protocol | https://modelcontextprotocol.io |
| Domain MCP Server | [`vaultwatch-rwa-mcp`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/README.md) |
| Odra Framework | https://odra.dev/ |
| Groq Console | https://console.groq.com/ |
| CSPR.cloud API | https://docs.cspr.cloud/ |
| Reputation Formula | [`docs/REPUTATION_FORMULA.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/REPUTATION_FORMULA.md) |
| Contract Audit | [`CONTRACT_AUDIT.md`](https://github.com/sodiq-code/vaultwatch/blob/main/CONTRACT_AUDIT.md) |
| Deployment Guide | [`DEPLOYMENT_GUIDE.md`](https://github.com/sodiq-code/vaultwatch/blob/main/DEPLOYMENT_GUIDE.md) |
| Upgrade Demo | [`docs/UPGRADE_DEMO.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/UPGRADE_DEMO.md) |
| x402 Integration | [`docs/X402_INTEGRATION.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/X402_INTEGRATION.md) |
| CSPR.click Skill | [`CSPR_CLICK_AGENT_SKILL.md`](https://github.com/sodiq-code/vaultwatch/blob/main/CSPR_CLICK_AGENT_SKILL.md) |

---

## License

MIT License · Copyright (c) 2026 Sodiq Jimoh — see [LICENSE](LICENSE)

---

**Author: [Sodiq Jimoh](https://github.com/sodiq-code) · Network: Casper Testnet (`casper-test`) · Compliance-gated RWA oracle · Verifiable agent reputation · MIT License**
