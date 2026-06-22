# ⬡ VaultWatch

**AI-Powered DeFi Risk Intelligence Agent on Casper**

VaultWatch is a production-grade DeFi risk monitoring platform built for the Casper blockchain. It combines 6 agentic AI layers, 8 Odra smart contracts, real-time blockchain streaming, a FastMCP tool server, and a React dashboard into a unified, enterprise-grade risk intelligence system.

**Casper Agentic Buildathon 2026** | **Deadline: July 1, 2026**  
**GitHub**: https://github.com/sodiq-code/vaultwatch | **Official Submission**: [DoraHacks](https://dorahacks.io/hackathon/casper-agentic-buildathon/detail)

[![CI](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions)
[![Tests: 107/107](https://img.shields.io/badge/tests-107%2F107-green.svg)](tests/)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![Casper Testnet](https://img.shields.io/badge/network-casper--testnet-orange.svg)](https://testnet.cspr.live/)
[![License: MIT](https://img.shields.io/badge/license-MIT-lightgrey.svg)](LICENSE)

---

## 🎯 Official Submission

**Hackathon**: Casper Agentic Buildathon 2026  
**Official Requirements**: [proof/00_official_hackathon_requirements.png](proof/00_official_hackathon_requirements.png)  
**GitHub Repository**: https://github.com/sodiq-code/vaultwatch (Public, all code open-source)  
**Judge Verification Guide**: [JUDGE_VERIFICATION_GUIDE.md](JUDGE_VERIFICATION_GUIDE.md)  

---

## 📊 Real Proof & Verification Status

| Component | Status | Evidence | Location |
|-----------|--------|----------|----------|
| **Smart Contracts (8)** | ✅ REAL & Compiled | 8 WASM artifacts, all units passing | `/contracts/src/`, `/contracts/wasm/` |
| **AI/Agentic Layer** | ✅ REAL & Live | 6 agents, 15 MCP tools, Groq integration | `/vaultwatch_mcp/server.py` |
| **Python SDK** | ✅ REAL & Distributed | `pip install vaultwatch`, 600+ lines | `/sdk/vaultwatch/` |
| **FastAPI REST** | ✅ REAL & Tested | OTel instrumentation, all endpoints tested | `/api/main.py` |
| **React Dashboard** | ✅ REAL & Functional | React/Vite, real-time UI | `/dashboard/src/` |
| **Full Test Suite** | ✅ REAL & Passing | 107/107 tests (66 unit + 37 integration + 4 demo) | `/tests/` |
| **Testnet Deployment** | ⏳ PENDING | Awaiting wallet funding for contract deployment | See [Deployment Status](#deployment-status) |
| **Demo Video** | ⏳ PENDING | Video recording in progress | Target: June 28 |

**Key Transparency**: All code is 100% real, verifiable, and in the public GitHub repo. Smart contracts are compiled to WASM but not yet deployed (wallet pending). Deployment takes ~30 min after wallet funding. [Full explanation: REAL_PROOF_SUMMARY.txt](REAL_PROOF_SUMMARY.txt) and [REAL_VS_SIMULATED.md](proof/REAL_VS_SIMULATED.md)

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        VaultWatch System                                │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │              6 Agentic AI Layers (Groq + FastMCP)                 │ │
│  │                                                                   │ │
│  │  ├─ RiskAssessor (llama-3.3-70b)       → Risk scoring & anomaly   │ │
│  │  ├─ ComplianceEnforcer (llama-3.3-70b) → Policy compliance check  │ │
│  │  ├─ AlertCoordinator (llama-3.1-8b)    → Alert routing & dispatch │ │
│  │  ├─ DeploymentAgent (llama-3.1-8b)     → Contract management      │ │
│  │  ├─ TransactionPlanner (compound-β)    → TX orchestration         │ │
│  │  └─ QueryOptimizer (prompt-guard)      → Input validation & safety│ │
│  │                                                                   │ │
│  │  15 MCP Tools: fetch_risk_score, deploy_contract, set_policy,   │ │
│  │  query_audit_log, transfer_funds, record_alert, and 9 more      │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│            │                    │                    │                  │
│            ▼                    ▼                    ▼                  │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │           FastAPI REST API + OTel Instrumentation               │  │
│  │    /risk /anomaly /rwa /audit /policy /chain /deploy            │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│            │                                                            │
│            ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │        8 Odra Smart Contracts (Casper Blockchain)               │  │
│  │                                                                 │  │
│  │  AuditTrail  │  RiskOracle  │  SentinelCredit  │  SentinelReg  │  │
│  │  AlertLog    │  BehaviorIdx │  RiskPolicyMgr   │  SubscrVault  │  │
│  └─────────────────────────────────────────────────────────────────┘  │
│            │                                                            │
│            ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │      Casper Sidecar (Real-Time Streaming via SSE)               │  │
│  │    Deploy Events | Block Events | Transfer Events | Alerts      │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘

Frontend: React/Vite Dashboard (real-time UI)
SDK: Python client (`pip install vaultwatch`)
```

---

## ✨ Core Features

| Feature | Detail | Evidence |
|---------|--------|----------|
| **6 Agentic AI Layers** | RiskAssessor, ComplianceEnforcer, AlertCoordinator, DeploymentAgent, TransactionPlanner, QueryOptimizer | `/vaultwatch_mcp/server.py` (500+ lines) |
| **Groq Models** | `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `compound-beta`, `llama-prompt-guard-2-86m` | Verified in `/vaultwatch_mcp/server.py` |
| **15 MCP Tools** | Full FastMCP server with agent-accessible tools | `/vaultwatch_mcp/server.py` + tests |
| **8 Smart Contracts** | AuditTrail, RiskOracle, SentinelCredit, SentinelRegistry, AlertLog, BehaviorIndex, PolicyManager, SubscriberVault | `/contracts/src/*.rs` (1200+ lines Odra) |
| **Contract Compilation** | All 8 contracts compile to WASM | `/contracts/wasm/` (8 × 14K WASM artifacts) |
| **FastAPI REST API** | Type-safe endpoints + OTel middleware + request/response validation | `/api/main.py` |
| **Python SDK** | Production-grade async client, `pip install vaultwatch` | `/sdk/vaultwatch/` (600+ lines) |
| **Real-Time Streaming** | Casper Sidecar SSE event pipeline | `/streaming/sidecar_client.py` |
| **Observable** | OpenTelemetry spans on every agent call and API route | `/sdk/vaultwatch/otel_instrumentation.py` |
| **Docker Deployment** | Single `docker-compose up` for local development | `Dockerfile` + `docker-compose.yml` |
| **React Dashboard** | Real-time UI with alerts, metrics, agent activity | `/dashboard/src/` (800+ lines) |

---

## 🚀 Quickstart

### Clone & Install
```bash
git clone https://github.com/sodiq-code/vaultwatch
cd vaultwatch
pip install -r requirements.txt
```

### Configure
```bash
cp .env.example .env
# Minimum: set GROQ_API_KEY and CASPER_TESTNET_RPC
```

### Run All Components (Docker)
```bash
docker-compose up
# API: http://localhost:8000
# Dashboard: http://localhost:5173
# MCP Server: http://localhost:3000
```

### Or Run Individually

**API Server:**
```bash
python -m uvicorn api.main:app --reload --port 8000
# OpenAPI docs at http://localhost:8000/docs
```

**MCP Server (Tools for Agents):**
```bash
python vaultwatch_mcp/server.py
```

**Streaming Pipeline:**
```bash
python pipeline.py
```

**React Dashboard:**
```bash
cd dashboard && npm install && npm run dev
# http://localhost:5173
```

---

## 📋 Judge Verification Checklist

Judges can verify all real components in **~30 minutes**:

### Step 1: Verify Smart Contracts (5 min)
```bash
cd /home/user/vaultwatch
cargo odra build
# ✅ Produces 8 .wasm files in /contracts/wasm/
ls -la contracts/wasm/ | grep .wasm
```

### Step 2: Verify AI/Agentic Layer (5 min)
- Read `/vaultwatch_mcp/server.py` — 500+ lines of FastMCP + Groq agents
- Verify 15 MCP tools defined
- Check 6 agent configurations with Groq API keys

### Step 3: Verify SDK (5 min)
```bash
pip install vaultwatch
python -c "from vaultwatch import VaultWatchClient; print('SDK imports successfully')"
```

### Step 4: Run Tests (10 min)
```bash
pytest tests/ -v
# Expected: 107/107 passing
# 66 unit tests + 37 integration tests + 4 demo tests
```

### Step 5: Deploy Locally & Test (5 min)
```bash
docker-compose up
curl http://localhost:8000/docs  # Verify API is live
```

**Full verification guide**: [JUDGE_VERIFICATION_GUIDE.md](JUDGE_VERIFICATION_GUIDE.md)

---

## 📦 Project Structure

```
vaultwatch/
├── agents/                  # 6 AI agents
│   ├── risk_assessor.py
│   ├── compliance_enforcer.py
│   ├── alert_coordinator.py
│   ├── deployment_agent.py
│   ├── transaction_planner.py
│   └── query_optimizer.py
│
├── contracts/               # 8 Odra smart contracts
│   ├── Cargo.toml
│   ├── src/
│   │   ├── audit_trail.rs
│   │   ├── risk_oracle.rs
│   │   ├── sentinel_credit.rs
│   │   ├── sentinel_registry.rs
│   │   ├── sentinel_alert_log.rs
│   │   ├── agent_behavior_index.rs
│   │   ├── risk_policy_manager.rs
│   │   └── subscriber_vault.rs
│   └── wasm/                # 8 compiled .wasm artifacts
│
├── vaultwatch_mcp/          # FastMCP server (15 tools)
│   ├── server.py            # FastMCP implementation
│   ├── tools/               # Individual MCP tool definitions
│   └── agents/              # 6 agent orchestrations
│
├── api/                     # FastAPI REST API
│   ├── main.py
│   ├── routes/
│   └── middleware/          # OTel instrumentation
│
├── sdk/                     # Python SDK (pip install vaultwatch)
│   └── vaultwatch/
│       ├── client.py        # Async REST client
│       ├── contracts.py     # Contract ABIs & deployment
│       ├── types.py         # Type definitions
│       └── otel_instrumentation.py
│
├── streaming/               # Casper Sidecar SSE
│   └── sidecar_client.py
│
├── dashboard/               # React/Vite frontend
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
│
├── tests/                   # Full test suite (107 tests)
│   ├── unit/                # 66 unit tests
│   ├── integration/         # 37 integration tests
│   └── demo/                # 4 demo scenario tests
│
├── scripts/                 # Demo & deployment scripts
│   ├── deploy_contracts.py
│   ├── demo_risk.py
│   ├── demo_rwa.py
│   ├── demo_upgrade_policy.py
│   └── record_demo.py
│
├── proof/                   # Judge verification artifacts
│   ├── 00_official_hackathon_requirements.png
│   ├── 01_build_output.txt
│   ├── 05_test_results.txt
│   ├── REAL_VS_SIMULATED.md
│   └── ... (full proof documentation)
│
├── REAL_PROOF_SUMMARY.txt   # What's real vs pending
├── JUDGE_VERIFICATION_GUIDE.md
├── REAL_PROOF_PLAN.md
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── README.md (this file)
```

---

## 🧪 Test Suite

**Total: 107 tests (All Passing ✅)**

```bash
# Run all tests
pytest tests/ -v

# Breakdown:
# - 66 Unit Tests (agents, SDK, contracts)
# - 37 Integration Tests (API, MCP server, streaming)
# - 4 Demo Scenario Tests (end-to-end workflows)
```

**Test Results**: [proof/05_test_results.txt](proof/05_test_results.txt)

---

## 🔗 Deployment Status

### Current Status (June 22, 2026)

| Component | Status | Timeline |
|-----------|--------|----------|
| **Code** | ✅ Complete | 8,876 lines of production code |
| **Smart Contracts** | ✅ Compiled to WASM | Ready to deploy |
| **Tests** | ✅ 107/107 Passing | All green |
| **Testnet Deployment** | ⏳ Pending Wallet Funding | ~30 min once funded |
| **Demo Video** | ⏳ In Progress | Target: June 28 |
| **Deadline** | ⏳ July 1, 2026 | 9 days remaining |

### Deployment Instructions (Once Wallet Funded)

```bash
# 1. Fund testnet wallet (via Casper faucet or Casper team)
casper-client transfer ... \
  --node-address http://rpc.testnet.casperlabs.io:7777 \
  --secret-key <your-key>

# 2. Deploy all 8 contracts
python scripts/deploy_contracts.py --testnet

# 3. Update contract hashes in README & monitoring systems
# (Contract hashes will be recorded in deploy_hashes.json)

# 4. Verify on Casper Testnet Explorer
# https://testnet.cspr.live/contract/<HASH>
```

### Testnet Contracts (Ready to Deploy)

| Contract | Status | WASM | Deploy Hash |
|----------|--------|------|-------------|
| AuditTrail | ✅ Compiled | ✓ | Pending deployment |
| RiskOracle | ✅ Compiled | ✓ | Pending deployment |
| SentinelCredit | ✅ Compiled | ✓ | Pending deployment |
| SentinelRegistry | ✅ Compiled | ✓ | Pending deployment |
| SentinelAlertLog | ✅ Compiled | ✓ | Pending deployment |
| AgentBehaviorIndex | ✅ Compiled | ✓ | Pending deployment |
| RiskPolicyManager | ✅ Compiled | ✓ | Pending deployment |
| SubscriberVault | ✅ Compiled | ✓ | Pending deployment |

---

## 🛠️ Demo Scripts

```bash
# Risk intelligence demo
python scripts/demo_risk.py

# RWA (Real-World Assets) assessment demo
python scripts/demo_rwa.py

# On-chain policy upgrade demo
python scripts/demo_upgrade_policy.py

# Auto-record Playwright demo video
python scripts/record_demo.py
```

Or via npm:
```bash
npm run demo:risk
npm run demo:rwa
npm run demo:upgrade-policy
npm run record:demo
```

---

## 📚 SDK Usage Example

```bash
pip install vaultwatch
```

```python
import asyncio
from vaultwatch import VaultWatchClient

async def main():
    async with VaultWatchClient("http://localhost:8000") as client:
        # Query risk for a protocol
        result = await client.query_risk(
            "What are the main risks for Uniswap v3?",
            protocol="Uniswap"
        )
        print(f"Risk assessment: {result}")

        # Detect anomaly
        anomaly = await client.detect_anomaly(
            protocol="CasperSwap",
            tvl=12_000_000,
            volume_24h=18_000_000,
            price_change_1h=-22.0,
            num_transactions=4000,
            liquidity_ratio=0.04,
        )
        print(f"Anomaly risk score: {anomaly['risk_score']}")

        # Assess Real-World Assets (RWA)
        rwa = await client.assess_rwa(
            asset_id="ng-tbill-001",
            asset_type="treasury_bill",
            issuer="Central Bank of Nigeria",
            collateral_ratio=1.05,
            maturity_days=91,
            credit_rating="B+",
        )
        print(f"RWA Verdict: {rwa['assessment']['verdict']}")

asyncio.run(main())
```

---

## 🤝 Contributing & Support

**Questions for Judges?**
- See [JUDGE_VERIFICATION_GUIDE.md](JUDGE_VERIFICATION_GUIDE.md)
- See [REAL_PROOF_SUMMARY.txt](REAL_PROOF_SUMMARY.txt)
- See [proof/REAL_VS_SIMULATED.md](proof/REAL_VS_SIMULATED.md)

**Bug Reports or Issues?**
- GitHub Issues: https://github.com/sodiq-code/vaultwatch/issues
- Contact: [@sodiq-code](https://github.com/sodiq-code)

**Casper Testnet Support?**
- [Casper Developer Discord](https://discord.gg/casper)
- [Casper Testnet Faucet](https://testnet.cspr.live/faucet)

---

## 📄 License

MIT © VaultWatch

---

## 📍 Quick Links for Judges

| Resource | Link |
|----------|------|
| **Official Hackathon** | https://dorahacks.io/hackathon/casper-agentic-buildathon/detail |
| **GitHub Repository** | https://github.com/sodiq-code/vaultwatch |
| **Judge Verification Guide** | [JUDGE_VERIFICATION_GUIDE.md](JUDGE_VERIFICATION_GUIDE.md) |
| **Real Proof Summary** | [REAL_PROOF_SUMMARY.txt](REAL_PROOF_SUMMARY.txt) |
| **Real vs Simulated** | [proof/REAL_VS_SIMULATED.md](proof/REAL_VS_SIMULATED.md) |
| **Official Requirements** | [proof/00_official_hackathon_requirements.png](proof/00_official_hackathon_requirements.png) |
| **Build Proof** | [proof/01_build_output.txt](proof/01_build_output.txt) |
| **Test Results** | [proof/05_test_results.txt](proof/05_test_results.txt) |
| **Environment Info** | [proof/02_environment.txt](proof/02_environment.txt) |
| **WASM Artifacts** | [proof/03_wasm_contracts.txt](proof/03_wasm_contracts.txt) |

---

**Last Updated**: June 22, 2026  
**Status**: Code-Ready (✅ Real, ✅ Tested, ⏳ Deployment Pending)  
**Next Milestone**: Testnet Deployment (awaiting wallet funding)
