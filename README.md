# VaultWatch RWA — Compliance-Gated, x402-Paid, MCP-Exposed RWA Oracle on Casper

**The first compliance-gated RWA risk oracle on Casper's natively upgradable contracts**

VaultWatch RWA is a production-grade, AI-native DeFi risk intelligence platform that combines **verifiable on-chain agent identity** (Track 2) with **AI-driven compliance and KYC** (Track 4) — deployed as 8 Odra smart contracts on Casper testnet, exposed via a 20-tool MCP server, and monetized through the x402 micropayment protocol.

[![Contracts Deployed](https://img.shields.io/badge/contracts-8%20deployed%20on%20testnet-orange.svg)](proof/PROOF.md)
[![MCP Published](https://img.shields.io/npm/v/casper-sentinel-mcp.svg)](https://www.npmjs.com/package/casper-sentinel-mcp)
[![RWA MCP Published](https://img.shields.io/badge/RWA%20MCP-vaultwatch--rwa--mcp-green.svg)](https://www.npmjs.com/package/vaultwatch-rwa-mcp)
[![SDK Published](https://img.shields.io/pypi/v/casper-sentinel.svg)](https://pypi.org/project/casper-sentinel/)
[![x402 Integrated](https://img.shields.io/badge/x402-pay--per--query-blue.svg)](docs/X402_INTEGRATION.md)
[![CI](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-100%2B%20passing-brightgreen.svg)](tests/)
[![Casper Testnet](https://img.shields.io/badge/casper-testnet%20live-orange.svg)](https://testnet.cspr.live/)
[![License: MIT](https://img.shields.io/badge/license-MIT-success.svg)](LICENSE)

---

## Track 2+4 Hybrid Positioning

VaultWatch RWA uniquely bridges two hackathon tracks:

| Track | Capability | Implementation |
|-------|-----------|----------------|
| **Track 2 — RWA Oracle Agents** | Verifiable on-chain agent identity | 7 AI agents write findings to 8 Odra contracts via `record_finding()`, `update_score()`, `record_decision()` — every action has a deploy hash |
| **Track 4 — AI-Driven Compliance** | Compliance-gated access, KYC checks | `RiskPolicyManager` enforces RBAC (OWNER → ADMIN → OPERATOR); `upgrade_to_v2_rwa()` adds RWA-specific thresholds; RWA MCP exposes `rwa_compliance_check()` tool |

The hybrid creates a **compliance-gated RWA risk oracle**: agents with verifiable on-chain identity produce risk assessments that are only accessible after compliance verification and x402 payment.

---

## Casper-Native Features Used

| Feature | How VaultWatch Uses It | File:Line Reference |
|---------|----------------------|---------------------|
| **Upgradable Smart Contracts** | `RiskPolicyManager.upgrade_to_v2_rwa()` demonstrates v1→v2 upgrade with state preservation | `contracts/src/risk_policy_manager.rs:129` |
| **x402 Micropayment Protocol** | `SubscriberVault` implements pay-per-query via `@make-software/casper-x402` SDK | `contracts/src/subscriber_vault.rs:39`, `x402/vaultwatch-x402.ts` |
| **MCP Server (Claude Desktop)** | 20-tool FastMCP server + 8-tool RWA MCP server for AI agent integration | `vaultwatch_mcp/server.py`, `vaultwatch_rwa_mcp/server.py` |
| **Native RBAC** | OWNER → ADMIN → OPERATOR hierarchy in `RiskPolicyManager` | `contracts/src/risk_policy_manager.rs:56-58` |
| **Account/Contract Unification** | Deployer account `0203cd25...` is both the agent wallet and contract owner — verifiable agent identity | `transaction_hashes_live.json`, `proof/PROOF.md` |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Casper Testnet (8 Contracts)                  │
│  AuditTrail · RiskOracle · SentinelCredit · SentinelRegistry   │
│  SentinelAlertLog · AgentBehaviorIndex · RiskPolicyManager ·    │
│  SubscriberVault                                                │
└───────────────┬────────────────────────────────┬───────────────┘
                │                                │
    ┌───────────▼──────────┐          ┌──────────▼──────────┐
    │   7 AI Agents        │          │  x402 Payment Layer  │
    │  Scanner · Anomaly   │          │  @make-software/     │
    │  SelfCorrection      │          │  casper-x402 SDK     │
    │  RWA · SafetyGuard   │          │  SubscriberVault +   │
    │  Audit · Intel       │          │  SentinelCredit      │
    └───────────┬──────────┘          └──────────┬──────────┘
                │                                │
    ┌───────────▼──────────────────────────────▼──────────┐
    │              API & MCP Layer                         │
    │  FastAPI REST (20 endpoints)                        │
    │  FastMCP Server (20 tools) → casper-sentinel-mcp    │
    │  RWA MCP Server (8 tools) → vaultwatch-rwa-mcp      │
    └───────────────────────┬─────────────────────────────┘
                            │
    ┌───────────────────────▼─────────────────────────────┐
    │              Published Packages                      │
    │  pip install casper-sentinel (Python SDK)            │
    │  npm install casper-sentinel-mcp (MCP tools)         │
    │  npm install vaultwatch-rwa-mcp (RWA MCP tools)      │
    └─────────────────────────────────────────────────────┘
```

**8 contracts** — `contracts/src/*.rs`  
**7 AI agents** — `agents/*.py`  
**20 MCP tools** — `vaultwatch_mcp/server.py`  
**8 RWA MCP tools** — `vaultwatch_rwa_mcp/server.py`  
**x402 payment** — `x402/vaultwatch-x402.ts`

---

## Smart Contracts — Live on Testnet

All 8 contracts deployed to `casper-test` with verified transaction hashes:

| Contract | Purpose | Key Entry Points | Deploy Hash |
|----------|---------|-----------------|-------------|
| `AuditTrail` | Immutable finding log | `record_finding`, `get_finding` | `b9c70cdc…33a7` |
| `RiskOracle` | On-chain risk scores | `update_score`, `get_risk_score`, `is_high_risk` | `e071aacc…7c9d` |
| `SentinelCredit` | x402 credit ledger | `deposit`, `deduct_credit`, `withdraw` | `0c09f2ad…af71` |
| `SentinelRegistry` | Subscriber registration | `register`, `deregister` | `9a5eb4f8…346c` |
| `SentinelAlertLog` | Alert history | `log_alert`, `get_address_logs` | `53317e08…a925` |
| `AgentBehaviorIndex` | Agent trust scores | `record_decision`, `get_metrics`, `get_trust_score` | `05066c33…7dd0` |
| `RiskPolicyManager` | Policy + RBAC + upgrades | `update_policy`, `upgrade_to_v2_rwa`, `grant_operator`, `grant_admin`, `revoke_operator` | `93e35d64…ee2e` |
| `SubscriberVault` | x402 escrow | `open_vault`, `deduct`, `top_up` | `6620787c…956d` |

Full deploy hashes with explorer links: [`proof/PROOF.md`](proof/PROOF.md)  
Contract source code: [`contracts/src/`](contracts/src/)  
Architecture documentation: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## AI Agent Pipeline

7 Groq-powered agents with on-chain accountability:

| Agent | Model | Writes To | Source |
|-------|-------|-----------|--------|
| ScannerAgent | `llama-3.1-8b-instant` | → AnomalyAgent queue | `agents/scanner_agent.py` |
| AnomalyAgent | `llama-3.3-70b-versatile` | `RiskOracle.update_score()` | `agents/anomaly_agent.py` |
| SelfCorrectionAgent | `llama-3.3-70b-versatile` | Re-runs low-confidence findings | `agents/self_correction_agent.py` |
| RWAAgent | `llama-3.3-70b-versatile` | `AuditTrail.record_finding(rwa_enriched=true)` | `agents/rwa_agent.py` |
| SafetyGuard | `llama-prompt-guard-2-86m` | Blocks injection (<50ms) | `agents/safety_guard.py` |
| AuditAgent | `llama-3.1-8b-instant` | `AuditTrail.record_finding()` | `agents/audit_agent.py` |
| IntelAgent | `llama-3.1-8b-instant` | `_findings_store` → API → MCP | `agents/intel_agent.py` |

Every agent decision is recorded in `AgentBehaviorIndex.record_decision()` — creating an **on-chain trust score** for the AI system itself (`contracts/src/agent_behavior_index.rs:39`).

---

## x402 Pay-Per-Query

VaultWatch implements the official Casper x402 micropayment protocol:

```
Client → GET /api/intel → Server returns 402 + payment params
Client → Signs payment via @make-software/casper-x402 SDK
Client → Retries with X-Payment header → Server verifies on-chain
Server → Returns intelligence JSON
```

**Implementation**: `x402/vaultwatch-x402.ts` — `VaultWatchX402` class with `buildPaymentRequest()`, `verifyPayment()`, `subscribe()`, `queryIntelligence()`  
**Contracts**: `SubscriberVault.open_vault()` → escrow, `SubscriberVault.deduct()` → per-query  
**Documentation**: [`docs/X402_INTEGRATION.md`](docs/X402_INTEGRATION.md)

---

## MCP Servers — Claude Desktop Integration

### General MCP (20 tools)

```bash
npm install casper-sentinel-mcp
```

| # | Tool | Agent | Purpose |
|---|------|-------|---------|
| 1 | `query_risk` | IntelAgent | Free-form risk queries |
| 2 | `detect_anomaly` | AnomalyAgent | Protocol anomaly detection |
| 3 | `scan_protocol` | ScannerAgent | Vulnerability scanning |
| 4 | `assess_rwa` | RWAAgent | RWA risk assessment |
| 5 | `get_audit_log` | AuditAgent | Read on-chain findings |
| 6 | `write_audit_entry` | AuditAgent | Write on-chain finding |
| 7 | `get_block_height` | — | Chain connectivity check |
| 8 | `list_policies` | — | Read risk policies |
| 9 | `update_policy` | — | Update risk policy |
| 10 | `check_safety` | SafetyGuard | Prompt safety check |
| 11 | `get_findings` | IntelAgent | Query findings store |
| 12 | `get_risk_score` | — | Query RiskOracle contract |
| 13 | `list_rwa_assets` | — | List RWA assets |
| 14 | `get_agent_spans` | — | OTel spans |
| 15 | `get_health` | — | System health |
| 16 | `agent_attestation` | — | On-chain agent attestation |
| 17 | `reputation_query` | — | Hybrid Brier + escrow reputation |
| 18 | `x402_subscribe` | — | x402 paid subscription |
| 19 | `policy_hotswap` | — | Atomic policy upgrade |
| 20 | `behavior_index_lookup` | — | Agent performance index |

Source: `vaultwatch_mcp/server.py`

### RWA MCP (8 tools)

```bash
npm install vaultwatch-rwa-mcp
```

| # | Tool | Purpose |
|---|------|---------|
| 1 | `rwa_collateral_health` | Live collateral ratio for RWA-backed assets |
| 2 | `rwa_depeg_risk` | Stablecoin depeg probability |
| 3 | `rwa_yield_analysis` | RWA vs DeFi yield comparison |
| 4 | `rwa_attestation_verify` | Verify on-chain RWA attestation |
| 5 | `rwa_portfolio_scan` | Full portfolio risk scan |
| 6 | `rwa_compliance_check` | KYC/AML compliance flag check |
| 7 | `rwa_oracle_feed` | Live RWA price oracle data |
| 8 | `rwa_casper_registry` | List RWA assets on Casper |

Source: `vaultwatch_rwa_mcp/server.py`

---

## Install & Demo

### Prerequisites

```bash
# Python SDK
pip install casper-sentinel==4.0.0

# MCP servers
npm install casper-sentinel-mcp
npm install vaultwatch-rwa-mcp

# x402 payment SDK
npm install @make-software/casper-x402 casper-js-sdk
```

### Demo Commands

```bash
# Clone and setup
git clone https://github.com/sodiq-code/vaultwatch.git
cd vaultwatch
pip install -r requirements.txt

# 1. Full risk intelligence demo (7 agents + 8 contracts)
python scripts/demo_risk.py

# 2. RWA-specific risk assessment
python scripts/demo_rwa.py

# 3. V2 upgrade demonstration (Casper native contract upgrade)
python scripts/demo_upgrade_policy.py

# 4. Dispute resolution demo
python scripts/demo_dispute.py

# 5. Verify all contract deploys
python3 scripts/verify_deploys.py --deploy-hashes transaction_hashes_live.json
python3 scripts/verify_deploys.py --account 0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7

# 6. Start API server
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# 7. Start MCP server
python vaultwatch_mcp/server.py

# 8. Run tests
pytest tests/ -v
```

---

## Proof Artifacts

All claims are verifiable through these artifacts:

| Artifact | Location | What It Proves |
|----------|----------|---------------|
| Deploy hashes | `proof/PROOF.md` §1 | 8 contracts deployed with "Success" status |
| Transaction hashes | `transaction_hashes_live.json` | Machine-readable deploy hash list |
| Interaction hashes | `proof/interaction_hashes.json` | 21 on-chain contract interactions |
| WASM binaries | `contracts/wasm/*.wasm` | 8 bulk-memory-safe WASM files |
| Test results | `proof/05_test_results.txt` | 100+ tests passing |
| MCP server | `proof/06_mcp_server.txt` | MCP server operational |
| Security audit | `CONTRACT_AUDIT.md` | Red-team security analysis |
| Live dashboard | https://dashboard-rho-amber-89.vercel.app | Real-time risk intelligence |

---

## Documentation

| Document | Description |
|----------|-------------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Full architecture with corrected entry points, RBAC, events |
| [`docs/X402_INTEGRATION.md`](docs/X402_INTEGRATION.md) | x402 payment flow, VaultWatchX402 class, SDK install |
| [`docs/LAUNCH_AND_IMPACT.md`](docs/LAUNCH_AND_IMPACT.md) | Post-hackathon roadmap, revenue model, competitive moat |
| [`docs/REPUTATION_FORMULA.md`](docs/REPUTATION_FORMULA.md) | Hybrid Brier + escrow reputation formula |
| [`docs/RED_TEAM_CHECKLIST.md`](docs/RED_TEAM_CHECKLIST.md) | Security hardening checklist |
| [`CONTRACT_AUDIT.md`](CONTRACT_AUDIT.md) | Comprehensive red-team security audit |
| [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md) | Contract deployment and WASM compilation guide |
| [`proof/PROOF.md`](proof/PROOF.md) | Verification guide with deploy hashes |

---

## Key File:Line References

Every claim in this README pins to a specific source:

| Claim | Reference |
|-------|-----------|
| `record_finding` is the AuditTrail entry point | `contracts/src/audit_trail.rs:68` |
| `update_score` is the RiskOracle entry point | `contracts/src/risk_oracle.rs:33` |
| `deposit`/`deduct_credit`/`withdraw` are SentinelCredit entry points | `contracts/src/sentinel_credit.rs:72,100,143` |
| `register`/`deregister` are SentinelRegistry entry points | `contracts/src/sentinel_registry.rs:35,56` |
| `record_decision`/`get_metrics` are AgentBehaviorIndex entry points | `contracts/src/agent_behavior_index.rs:39,94` |
| `upgrade_to_v2_rwa` demonstrates Casper upgrade | `contracts/src/risk_policy_manager.rs:129` |
| RBAC with grant_operator/grant_admin/revoke_operator | `contracts/src/risk_policy_manager.rs:180,191,202` |
| `open_vault`/`deduct`/`top_up` are SubscriberVault entry points | `contracts/src/subscriber_vault.rs:39,66,93` |
| `VaultWatchX402` class implements x402 | `x402/vaultwatch-x402.ts:120` |
| 20 MCP tools in FastMCP server | `vaultwatch_mcp/server.py` |
| 8 RWA MCP tools | `vaultwatch_rwa_mcp/server.py` |
| Hybrid Brier + escrow reputation formula | `agents/reputation.py` |
| FindingRecorded event emission | `contracts/src/audit_trail.rs:99` |
| PolicyUpgraded event emission | `contracts/src/risk_policy_manager.rs:118` |
| CreditDeposited event emission | `contracts/src/sentinel_credit.rs:92` |
| AlertLogged event emission | `contracts/src/sentinel_alert_log.rs:103` |

---

## Repository

**GitHub**: https://github.com/sodiq-code/vaultwatch  
**Network**: Casper Testnet (`casper-test`)  
**Deployer**: `0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7`  
**License**: MIT  
