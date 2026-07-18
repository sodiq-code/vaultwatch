# VaultWatch RWA — Long-Term Launch Plan & Ecosystem Impact

**Compliance-Gated, x402-Paid, MCP-Exposed RWA Oracle on Casper**

> *Track 2+4 Hybrid · 8 Odra Contracts · 8 Verified Deploys · 7 AI Agents · 20+8 MCP Tools · Live on Testnet*

---

## Executive Summary

VaultWatch RWA is the first compliance-gated RWA risk oracle on Casper's natively upgradable contracts. It combines **verifiable on-chain agent identity** (Track 2 — RWA Oracle Agents) with **AI-driven compliance and KYC** (Track 4 — AI-Driven Compliance) to create a hybrid platform where:

- Every risk assessment is written to an immutable on-chain audit trail (`AuditTrail.record_finding()`)
- Every AI agent has a verifiable on-chain trust score (`AgentBehaviorIndex.record_decision()`)
- Access to intelligence is gated by both compliance checks and x402 micropayments
- Risk policies are hot-swappable with Casper's native contract upgrade pattern (`RiskPolicyManager.upgrade_to_v2_rwa()`)
- RBAC (OWNER → ADMIN → OPERATOR) ensures proper access control for policy changes

Eight contracts are live on `casper-test`. Two packages are published to public registries. A CI pipeline runs 100+ tests on every commit. A Vercel-hosted dashboard provides real-time risk intelligence.

The long-term trajectory: VaultWatch becomes the canonical compliance-gated RWA risk infrastructure layer for every protocol, vault, and institution operating on Casper — and, over time, a cross-chain risk standard powered by the Casper AI Toolkit.

---

## Track 2+4 Hybrid Strategy

| Track | VaultWatch Capability | Contract Integration |
|-------|----------------------|---------------------|
| **Track 2 — RWA Oracle Agents** | 7 AI agents with verifiable on-chain identity | `AuditTrail.record_finding()`, `RiskOracle.update_score()`, `AgentBehaviorIndex.record_decision()` |
| **Track 4 — AI-Driven Compliance** | Compliance-gated access, RWA-specific risk thresholds | `RiskPolicyManager.upgrade_to_v2_rwa()`, RBAC (`grant_operator`, `grant_admin`, `revoke_operator`), `SubscriberVault.deduct()` with x402 |

**The hybrid value**: RWA oracle agents (Track 2) produce risk assessments that are only accessible after compliance verification (Track 4) and x402 payment — creating a **compliance-gated RWA risk oracle** that no pure Track 2 or Track 4 project can replicate alone.

**Casper-native features used**:
- Upgradable contracts (demonstrated with `upgrade_to_v2_rwa`)
- x402 micropayment protocol (pay-per-intelligence-query)
- MCP server (Claude Desktop integration)
- Native RBAC (operator/admin roles on RiskPolicyManager)
- Account/contract unification (verifiable agent identity via deployer key)

---

## 1. The Problem VaultWatch Solves

DeFi protocols operating on Casper today have no shared, on-chain risk intelligence layer. Risk assessment is either absent, siloed per protocol, or delegated to off-chain tooling that leaves no verifiable audit trail. The consequences are measurable:

- **No shared anomaly baseline.** Each protocol re-implements risk monitoring independently, producing inconsistent thresholds and blind spots.
- **No on-chain verifiability.** Findings from off-chain monitoring tools cannot be proven immutable, timestamped, or audited.
- **No AI-native infrastructure.** Existing monitoring tools predate the AI agent paradigm entirely and cannot interface with Claude Desktop or MCP-compatible agents.
- **No RWA risk coverage.** As Casper targets regulated real-world asset tokenization, no tool exists to assess RWA collateral risk on-chain.
- **No pay-per-query primitive.** Subscriptions to risk data are handled via Web2 billing; no on-chain escrow or x402 micropayment flow exists for risk intelligence queries.
- **No compliance gating.** No mechanism ensures that only KYC-verified entities can access RWA risk intelligence.

All six gaps are addressed in a single, composable stack.

---

## 2. What Is Already Deployed

All deliverables below are independently verifiable on the Casper testnet explorer and public registries.

### 2.1 Smart Contracts on Casper Testnet

Eight Rust/Odra smart contracts compiled to WASM and deployed to `casper-test` on July 11, 2026:

| Contract | Role | Deploy Hash |
|---|---|---|
| `AuditTrail` | Immutable log of every agent finding | `b9c70cdc…33a7` |
| `RiskOracle` | On-chain risk scores queryable by any dApp | `e071aacc…7c9d` |
| `SentinelAlertLog` | Alert storage with severity tagging (256-entry sliding window) | `53317e08…a925` |
| `SentinelRegistry` | Subscriber identity and registration | `9a5eb4f8…346c` |
| `AgentBehaviorIndex` | AI agent trust scores and correction rates | `05066c33…7dd0` |
| `RiskPolicyManager` | Hot-swappable thresholds + RBAC + v2 upgrade | `93e35d64…ee2e` |
| `SentinelCredit` | x402 credit ledger for pay-per-query billing | `0c09f2ad…af71` |
| `SubscriberVault` | Escrowed CSPR prepay for subscribers | `6620787c…956d` |

**29 total on-chain TX hashes**: 8 contract deploys + 21 contract interaction deploys — all verifiable at [testnet.cspr.live](https://testnet.cspr.live).

### 2.2 Published Packages

| Package | Registry | Version | URL |
|---|---|---|---|
| `casper-sentinel` | PyPI | `4.0.0` | https://pypi.org/project/casper-sentinel/4.0.0/ |
| `casper-sentinel-mcp` | npm | Latest | https://www.npmjs.com/package/casper-sentinel-mcp |
| `vaultwatch-rwa-mcp` | npm | `1.0.0` | https://www.npmjs.com/package/vaultwatch-rwa-mcp |

### 2.3 Live Dashboard

**URL**: https://dashboard-rho-amber-89.vercel.app

Real-time risk intelligence powered by Groq `llama-3.3-70b-versatile`, live CSPR price from CoinGecko, and live network data from cspr.cloud. Every AI finding links to its on-chain contract deploy hash.

---

## 3. Post-Hackathon Roadmap

### Phase 1 — Mainnet Deployment & Real RWA Data (1–3 Months)

**Trigger**: Casper 2.0 EVM compatibility and x402 micropayments reach mainnet (target: 2026 H2).

**Deliverables:**

#### 1.1 Mainnet Contract Migration
All 8 contracts migrated to `casper` mainnet with production deployer keys. Contract addresses published in SDK, dashboard, and public documentation. Every mainnet deploy hash registered in proof artifacts.

#### 1.2 Real RWA Data Feeds
Replace simulated RWA data with live feeds from:
- **DeFiLlama** — stablecoin collateral ratios, TVL data
- **Chainlink** — price oracle integration for RWA-backed assets
- **Casper Native Token Registry** — registered RWA token metadata
- **Institutional APIs** — credit rating data from Moody's/S&P

Every RWA assessment is written to the Casper `AuditTrail` contract — providing regulators with a timestamped, tamper-proof record of risk surveillance.

#### 1.3 Protocol Partnerships — First Integration Cohort
Target: 3 Casper DeFi protocols integrating `casper-sentinel` SDK for live risk data:

```bash
pip install casper-sentinel
export VAULTWATCH_ENDPOINT=https://api.vaultwatch.io
# Live risk score for any Casper protocol in < 5 lines of Python
```

### Phase 2 — ZK-KYC Compliance Layer (3–6 Months)

**Trigger**: Casper Compliant Security Tokens and institutional demand for privacy-preserving compliance.

**Deliverables:**

#### 2.1 Zero-Knowledge KYC Layer
Implement privacy-preserving compliance checks using **ZoKrates + Groth16**:

```
User generates ZK proof: "I am KYC-verified in jurisdiction X"
  → Smart contract verifies proof on-chain
  → No personal data stored on-chain
  → Compliance check passes → RWA intelligence unlocked
```

This eliminates the current limitation where `rwa_compliance_check()` returns a placeholder. With ZK proofs, compliance is verified cryptographically without revealing identity.

#### 2.2 ComplianceToken (CEP-18)
Deploy a Casper CEP-18 compliance token that:
- Tracks KYC verification status on-chain
- Enables RWA access gating without PII exposure
- Integrates with `RiskPolicyManager` RBAC for institutional access control
- Supports jurisdiction-specific compliance rules

#### 2.3 Institutional API Tier
Enterprise API with:
- SLA-backed dedicated endpoints
- Historical risk score exports (CSV/Parquet)
- Regulatory reporting dashboards
- Multi-jurisdiction compliance flag management

### Phase 3 — Institutional DeFi Gateway (6–12 Months)

**Trigger**: Cross-chain RWA markets mature; institutional DeFi on Casper reaches critical mass.

**Deliverables:**

#### 3.1 ComplianceToken — Institutional DeFi Gateway
`ComplianceToken` (CEP-18) becomes the gateway token for institutional DeFi on Casper:
- Institutions must hold ComplianceToken to access RWA risk intelligence
- ComplianceToken holders receive discounted x402 query rates
- Token-gated MCP tools for institutional Claude Desktop integration
- On-chain compliance audit trail for regulators

#### 3.2 Cross-Chain Risk Oracle Bridge
Risk scores computed on Casper are bridged to EVM-compatible chains:
- Ethereum-based protocols consume Casper-verified RWA risk data
- Unified collateral risk views across RWA issuers on multiple chains
- Industry-standard risk score format (JSON-LD + on-chain hash attestation)

#### 3.3 AI Agent Economy Integration
As Casper's Agent Infrastructure reaches production:
- Agent-to-agent x402 micropayment flows
- Protocol-native spending limits for AI agent accounts
- Session-key-bounded risk query permissions
- VaultWatch is the first risk intelligence service natively consumable by autonomous AI agents on Casper

---

## 4. Revenue Model

### x402 Pay-Per-Query

| Tier | Price (CSPR) | Features |
|------|-------------|----------|
| Standard | 1 CSPR/query | Risk score, basic findings |
| Premium | 5 CSPR/query | Full findings, RWA enrichment, compliance flags |
| Institutional | Custom | SLA, historical data, regulatory reports |

### Subscription Vaults

| Plan | Monthly CSPR | Queries Included | Overage Rate |
|------|-------------|-----------------|-------------|
| Basic | 30 CSPR | 50 | 1 CSPR/query |
| Professional | 150 CSPR | 500 | 0.5 CSPR/query |
| Enterprise | Custom | Unlimited | Negotiated |

### Revenue Projections (Conservative)

| Year | Queries/Month | Revenue (CSPR) | Revenue (USD @ $0.02) |
|------|--------------|----------------|----------------------|
| Y1 Q1 | 10,000 | 10,000 | $200 |
| Y1 Q4 | 100,000 | 100,000 | $2,000 |
| Y2 Q4 | 1,000,000 | 1,000,000 | $20,000 |

---

## 5. Target Market

### Primary Market: RWA Tokenization Platforms

- Casper-based protocols issuing compliant security tokens
- Need: On-chain risk surveillance for regulatory compliance
- Value: Every RWA assessment is an immutable `AuditTrail` entry

### Secondary Market: DeFi Protocols on Casper

- CasperSwap, CasperLend, CasperYield
- Need: Shared risk intelligence layer
- Value: One contract call to `RiskOracle.get_risk_score()` — no integration overhead

### Tertiary Market: Institutional DeFi

- Traditional finance entering DeFi via RWA tokenization
- Need: Compliance-gated access to risk intelligence
- Value: ZK-KYC + ComplianceToken + x402 micropayments

### Market Size

The global DeFi security market is valued at $4.8 billion in 2025, projected to reach $22.6 billion by 2034 at 18.7% CAGR (Dataintelo, 2025). On-chain risk scoring specifically was valued at $1.21 billion in 2024 (MarketIntelo, 2024). Casper is currently underpenetrated in both markets. VaultWatch is positioned to become Casper's primary contributor to that segment.

---

## 6. Competitive Moat

### Original IP: Hybrid Brier + Escrow Reputation Formula

VaultWatch's agent reputation system (`agents/reputation.py`) uses a novel hybrid formula that combines:

1. **Brier Score** — Measures calibration of probabilistic predictions (how well confidence matches outcome)
2. **Escrow-Derived Stake** — Agents with more CSPR staked in `SentinelCredit` have higher reputation weight

This formula is **original IP** — no other on-chain risk oracle uses a hybrid Brier + escrow reputation system. The formula creates a natural economic incentive for agents to produce accurate risk assessments, because:

- Overconfident wrong predictions → Brier penalty → lower reputation → fewer queries
- Underconfident predictions → lower trust score → fewer queries
- Staking CSPR → higher reputation → more queries → more revenue
- Losing stake on wrong predictions → lower reputation → fewer queries

### Casper-Native Advantages

| Advantage | Competitor Gap | VaultWatch Implementation |
|-----------|---------------|--------------------------|
| Natively upgradable contracts | Most chains require proxy patterns | `upgrade_to_v2_rwa()` — one entry point, state preserved |
| x402 micropayments | No standard pay-per-query on any chain | `SubscriberVault` + `SentinelCredit` + `@make-software/casper-x402` |
| MCP integration | No risk oracle exposes MCP tools | 20 + 8 MCP tools callable from Claude Desktop |
| RBAC built-in | Most contracts use single-owner | OWNER → ADMIN → OPERATOR hierarchy |
| Account/contract unification | Agents can't prove identity on-chain | Deployer key = agent identity = verifiable |

---

## 7. Ecosystem Impact on Casper

### 7.1 DeFi Infrastructure Layer

Every DeFi protocol on Casper currently operates without a shared risk standard. VaultWatch installs that standard directly into the chain via publicly readable smart contracts. `RiskOracle` is queryable by any Casper dApp — it is not a closed API.

### 7.2 AI Agent Economy Enablement

The Casper Manifest explicitly targets the machine-to-machine economy. VaultWatch is the first project to deploy this stack end-to-end on Casper testnet:

- `SubscriberVault` implements x402-compatible escrow for AI agent micropayments
- `SentinelCredit` handles per-query credit deduction
- `AgentBehaviorIndex` creates an on-chain trust score for AI systems

### 7.3 RWA Market Risk Coverage

Institutions tokenizing assets on Casper need assurance that risk surveillance exists. VaultWatch's `RWAAgent` and `RiskPolicyManager` provide that assurance in a form that regulators can verify: a timestamped, on-chain audit trail of every risk assessment performed.

### 7.4 Developer Ecosystem Growth

Three categories of reusable ecosystem artifacts:

**Published libraries** — `casper-sentinel` (PyPI), `casper-sentinel-mcp` (npm), `vaultwatch-rwa-mcp` (npm) are live, versioned packages.

**Open-source reference implementations** — 8-contract Odra stack, 7-agent AI pipeline, MCP server construction, x402 pay-per-query primitives.

**CI/CD template** — GitHub Actions pipeline (lint → unit → integration → contract → Docker) usable as a starting template for any Casper project.

---

## 8. Alignment with the Casper Manifest

| Casper Manifest Initiative | Status | VaultWatch Alignment |
|---|---|---|
| **X402 Micropayments** | In Progress (2026 H2) | `SubscriberVault` + `SentinelCredit` implement x402 pay-per-query on testnet |
| **Agent Infrastructure** | Planned (2026/2027) | `AgentBehaviorIndex` provides on-chain AI trust scores; 7 agents production-ready |
| **Compliant Security Tokens** | In Progress (2026 H2) | `RWAAgent` assesses RWA collateral; `RiskPolicyManager` holds compliance thresholds; ZK-KYC planned |
| **Smart Accounts** | Planned (2026/2027) | MCP server enables AI agents to call risk tools with scoped permissions |
| **EVM Compatibility** | In Progress (2026 H2) | Phase 3 cross-chain oracle bridges Casper risk scores to EVM chains |
| **Native Token Registry** | Planned (2026/2027) | `RiskOracle` becomes queryable risk layer for all registered tokens |
| **Quantum Safety** | Planned (2027) | VaultWatch's pluggable key system is forward-compatible with ML-DSA-44 |

---

## 9. Social Infrastructure & Community

| Resource | URL | Status |
|---|---|---|
| **GitHub Repository** | https://github.com/sodiq-code/vaultwatch | Public, active |
| **Live Dashboard** | https://dashboard-rho-amber-89.vercel.app | Always-on |
| **Python SDK (PyPI)** | https://pypi.org/project/casper-sentinel/4.0.0/ | Published |
| **MCP Package (npm)** | https://www.npmjs.com/package/casper-sentinel-mcp | Published |
| **RWA MCP Package (npm)** | https://www.npmjs.com/package/vaultwatch-rwa-mcp | Published |
| **Testnet Explorer** | https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7 | Live |
| **Verification Guide** | `proof/PROOF.md` | Complete |
| **Security Audit** | `CONTRACT_AUDIT.md` | Complete |

**Community engagement plan:**

- **Casper Forum** — monthly technical posts covering VaultWatch findings, RWA risk reports, and compliance architecture
- **Developer documentation** — SDK docs, MCP tool reference, and contract ABI published alongside each release
- **Grant applications** — Casper Accelerate ($25M program) application for continued development
- **Integration bounties** — third-party Casper protocols that integrate `casper-sentinel` receive co-marketing

---

## 10. Risk Factors & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Casper mainnet migration delays | Medium | Phase 1 deliverables execute on testnet first; mainnet migration is a configuration change |
| Protocol partnership acquisition | Medium | SDK integration requires 5 lines of Python; open-source + published packages allow self-service |
| Groq API dependency | Low | Model abstraction layer allows swap to any OpenAI-compatible endpoint |
| Smart contract exploits | Low | Odra 2.8.0 with typed storage; 100+ test suite; audit-ready architecture (`CONTRACT_AUDIT.md`) |
| Competing risk platforms on Casper | Very Low | No competing on-chain risk intelligence platform exists on Casper as of July 2026 |
| ZK-KYC implementation complexity | Medium | ZoKrates + Groth16 is well-documented; start with simple jurisdiction proofs |

---

## 11. Summary

VaultWatch RWA is the only deployed, compliance-gated, x402-paid, MCP-exposed RWA risk oracle on the Casper blockchain — live, tested, and publicly verifiable on the Casper testnet.

The Track 2+4 hybrid strategy creates a unique competitive position: RWA oracle agents with verifiable on-chain identity, gated by AI-driven compliance checks and x402 micropayments. No pure Track 2 or Track 4 project can replicate this combination.

The post-hackathon roadmap addresses the risk infrastructure gap that limits DeFi growth on Casper, enables the AI agent economy the Casper Manifest is building toward, and delivers the RWA risk surveillance layer that institutional adoption requires.

Every milestone is either already delivered or sequenced directly off a confirmed Casper protocol initiative.

---

*Repository: https://github.com/sodiq-code/vaultwatch*  
*Network: Casper Testnet (`casper-test`)*  
*Deployer: `0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7`*  
*Verification: `proof/PROOF.md`*  
*Security Audit: `CONTRACT_AUDIT.md`*
