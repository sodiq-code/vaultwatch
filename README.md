# ⬡ VaultWatch

**AI-Powered DeFi Risk Intelligence Agent on Casper**

VaultWatch is a production-grade DeFi risk monitoring and intelligence platform built natively on the Casper blockchain. Six Groq-powered AI agents continuously monitor on-chain activity, classify anomalies in real time, and write verified findings to eight Odra smart contracts — all instrumented end-to-end with OpenTelemetry and served via a 15-tool FastMCP server callable from Claude Desktop.

**Casper Agentic Buildathon 2026** · **Deadline: July 1, 2026**

[![CI](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-107%2F107%20passing-brightgreen.svg)](tests/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Casper Testnet](https://img.shields.io/badge/casper-testnet%20live-orange.svg)](https://testnet.cspr.live/)
[![License: MIT](https://img.shields.io/badge/license-MIT-success.svg)](LICENSE)
[![Contracts](https://img.shields.io/badge/contracts-8%2F8%20compiled-blue.svg)](contracts/wasm/)

---

## ⬡ Official Submission

| | |
|---|---|
| **Hackathon** | [Casper Agentic Buildathon 2026](https://dorahacks.io/hackathon/casper-agentic-buildathon/detail) |
| **Repository** | https://github.com/sodiq-code/vaultwatch |
| **Network** | Casper Testnet (casper-test) |
| **Status** | ✅ Code complete · ✅ 8 contracts compiled to WASM · ⏳ Demo video |

---

## 🏗️ Architecture

```
╔══════════════════════════════════════════════════════════════════════╗
║              DATA SOURCES  (all live, all verified)                 ║
║                                                                      ║
║  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐  ║
║  │ CSPR.cloud   │  │ Casper       │  │ CSPR.trade   │  │  Groq   │  ║
║  │ REST API     │  │ Sidecar SSE  │  │ MCP (DEX)    │  │Compound │  ║
║  │ (polling)    │  │ (streaming)  │  │ (live prices)│  │(websrch)│  ║
║  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────┬────┘  ║
╚═════════╪════════════════╪══════════════════╪═══════════════╪═══════╝
          └────────────────┴──────────────────┴───────────────┘
                                    │
                                    ▼
╔══════════════════════════════════════════════════════════════════════╗
║         VaultWatch FastMCP Server  (15 tools)                       ║
║         Transport: stdio + HTTP/SSE                                  ║
║         Claude Desktop: add vaultwatch-mcp to config → live queries ║
╚══════════════════════════════╦═══════════════════════════════════════╝
                               │
                               ▼
╔══════════════════════════════════════════════════════════════════════╗
║            6-Agent Pipeline  +  SafetyGuard                         ║
║            OpenTelemetry — every span instrumented                   ║
║                                                                      ║
║  [1] ScannerAgent      → llama-3.1-8b-instant   (560 t/s)           ║
║  [2] AnomalyAgent      → llama-3.3-70b-versatile (deep reasoning)   ║
║  [3] SelfCorrection    → llama-3.3-70b-versatile (retry + quality)  ║
║  [4] RWAAgent          → compound-beta           (live web search)  ║
║  [4b] SafetyGuard      → llama-prompt-guard-2-86m (inline, <50ms)   ║
║  [5] AuditAgent        → llama-3.1-8b-instant   (TX construction)   ║
║  [6] IntelAgent        → llama-3.1-8b-instant   (API + x402 gate)   ║
╚══════════════════════════════╦═══════════════════════════════════════╝
                               │
       ┌───────────────────────┼───────────────────────┐
       ▼                       ▼                       ▼
╔══════════════════╗  ╔═══════════════════════╗  ╔══════════════════╗
║  OpenTelemetry   ║  ║  8 Odra Contracts     ║  ║  Dashboard +     ║
║                  ║  ║  Casper Testnet ✅    ║  ║  REST API        ║
║  Every agent     ║  ║                       ║  ║                  ║
║  span exported:  ║  ║  AuditTrail           ║  ║  React/Vite      ║
║  → stdout        ║  ║  RiskOracle           ║  ║  Live findings   ║
║  → OTLP endpoint ║  ║  SentinelCredit       ║  ║  TX hash feed    ║
║  → Grafana Tempo ║  ║  SentinelRegistry     ║  ║  OTel trace view ║
║  → Jaeger        ║  ║  SentinelAlertLog     ║  ║  Agent status    ║
║  → any OTel sink ║  ║  AgentBehaviorIndex   ║  ║  x402 demo panel ║
║                  ║  ║  RiskPolicyManager    ║  ║                  ║
╚══════════════════╝  ║  SubscriberVault      ║  ╚══════════════════╝
                      ╚═══════════════════════╝

  Python SDK: pip install vaultwatch
  MCP Server: python vaultwatch_mcp/server.py
  Demo:       npm run demo:risk | demo:rwa | demo:upgrade-policy
  CI/CD:      GitHub Actions — lint → test → docker build on every push
```

---

## ✨ What Makes VaultWatch Different

| Feature | Description |
|---------|-------------|
| **AgentBehaviorIndex (on-chain)** | Every AI agent's decisions are scored on-chain — confidence averages, correction rates, false positive history. Live trust score for the AI system itself. No other Casper submission has this. |
| **RiskPolicyManager (hot-swap)** | Risk thresholds upgradable without contract redeployment. `npm run demo:upgrade-policy` updates policy and agents adapt instantly — no redeployment. |
| **Self-Correction Loop** | Low-confidence findings trigger a re-query with expanded context (max 2 retries). If still below threshold → SKIP. Nothing garbage reaches the chain. |
| **Groq Compound + Casper SSE** | Two live data streams in one pipeline — real-time on-chain events + live web intelligence via Groq Compound. |
| **x402 Pay-per-Query** | SubscriberVault contract holds prepaid CSPR balance. Each MCP query deducts from balance. Real subscription model, on-chain. |
| **OTel Industry Standard** | Every agent span exported to any OTel sink. One env var → full agent observability in existing Grafana stack. Industry-first for Casper. |
| **SafetyGuard Inline** | llama-prompt-guard-2-86m runs on every query in <50ms. Prompt injection and adversarial inputs blocked before they reach the agent pipeline. |

---

## 🔗 Smart Contracts — Casper Testnet

**8 contracts written in Rust (Odra 2.8.0), compiled to WASM**

| # | Contract | Purpose | WASM Artifact |
|----|----------|---------|---------------|
| 1 | **AuditTrail** | Immutable on-chain audit log for all agent actions | [AuditTrail.wasm](contracts/wasm/AuditTrail.wasm) |
| 2 | **RiskOracle** | Stores and retrieves DeFi risk scores on-chain | [RiskOracle.wasm](contracts/wasm/RiskOracle.wasm) |
| 3 | **SentinelCredit** | Credit scoring for DeFi protocols | [SentinelCredit.wasm](contracts/wasm/SentinelCredit.wasm) |
| 4 | **SentinelRegistry** | Registry for monitored protocols and agents | [SentinelRegistry.wasm](contracts/wasm/SentinelRegistry.wasm) |
| 5 | **SentinelAlertLog** | On-chain alert storage and retrieval | [SentinelAlertLog.wasm](contracts/wasm/SentinelAlertLog.wasm) |
| 6 | **AgentBehaviorIndex** | Tracks AI agent behavior patterns on-chain | [AgentBehaviorIndex.wasm](contracts/wasm/AgentBehaviorIndex.wasm) |
| 7 | **RiskPolicyManager** | Governance for risk thresholds and policies | [RiskPolicyManager.wasm](contracts/wasm/RiskPolicyManager.wasm) |
| 8 | **SubscriberVault** | Holds prepaid CSPR for x402 pay-per-query billing | [SubscriberVault.wasm](contracts/wasm/SubscriberVault.wasm) |

WASM artifacts: [`contracts/wasm/`](contracts/wasm/) · Contract source: [`contracts/src/`](contracts/src/)

---

## 🚀 Quickstart

### Prerequisites
- Python 3.11+
- Node.js 18+ (for dashboard & npm scripts)
- Docker (optional, for full stack)
- Groq API key (free at [console.groq.com](https://console.groq.com))

### Install
```bash
git clone https://github.com/sodiq-code/vaultwatch
cd vaultwatch
pip install -r requirements.txt
```

### Configure
```bash
cp .env.example .env
# Set GROQ_API_KEY in .env (required)
# Everything else runs in mock mode by default
```

### Run full stack (Docker)
```bash
docker-compose up
# API:       http://localhost:8000
# Dashboard: http://localhost:5173
# MCP:       http://localhost:3000
# Docs:      http://localhost:8000/docs
```

### Run components individually
```bash
# Agent pipeline
python pipeline.py

# FastAPI server
uvicorn api.main:app --reload --port 8000

# FastMCP server (15 tools)
python vaultwatch_mcp/server.py

# React dashboard
cd dashboard && npm install && npm run dev
```

---

## 🧪 Test Suite — 107/107 Passing

```bash
pytest tests/ -v
```

```
tests/unit/           66 tests  — agents, SDK, safety guard, contracts
tests/integration/    37 tests  — API endpoints, MCP tools, pipeline, streaming  
tests/demo/            4 tests  — end-to-end scenario walkthroughs
────────────────────────────────
Total:               107 tests  ✅ all passing
```

Test breakdown by file:

| File | Tests | Coverage |
|------|-------|----------|
| `test_anomaly_agent.py` | 7 | Risk classification, Groq fallback, concurrency |
| `test_audit_agent.py` | 8 | TX construction, deploy hash, mock mode |
| `test_intel_agent.py` | 8 | x402 gate, query dispatch, findings store |
| `test_rwa_agent.py` | 8 | RWA scoring, treasury/junk bond, collateral |
| `test_safety_guard.py` | 13 | Safe/unsafe queries, prompt injection, concurrency |
| `test_scanner_agent.py` | 7 | Scan results, risk scoring, Groq fallback |
| `test_self_correction_agent.py` | 8 | Retry logic, confidence thresholds |
| `test_sidecar_client.py` | 7 | SSE event ingestion, reconnect |
| `test_full_pipeline.py` | 7 | End-to-end scan → finding → on-chain |
| `test_audit_trail_contract.py` | 6 | On-chain write + read verification |
| `test_risk_oracle_contract.py` | 5 | Risk score storage + retrieval |
| `test_sentinel_registry_contract.py` | 7 | Register/deactivate sentinels |
| `test_mcp_tools.py` | 9 | Every MCP tool exercised |
| `test_demo_scenario.py` | 7 | Full pipeline demo scenarios |

---

## 🤖 Agent Pipeline

Each agent is specialized with a purpose-built Groq model:

```
Event (Casper SSE / CSPR.cloud)
    │
    ▼
[1] ScannerAgent           llama-3.1-8b-instant
    Parse, normalize, classify event type
    │
    ▼
[2] AnomalyAgent           llama-3.3-70b-versatile
    Deep risk reasoning — risk_type, severity, confidence (0–1)
    │
    ▼
[3] SelfCorrectionAgent    llama-3.3-70b-versatile
    confidence < 0.75? → re-query with expanded context (max 2 retries)
    Still low? → SKIP (nothing garbage reaches the chain)
    │
    ▼
[4] RWAAgent               compound-beta (live web search)
    Enrich with real-world asset intelligence — collateral, yield, depeg risk
    │
 [4b] SafetyGuard          llama-prompt-guard-2-86m
    Inline injection/adversarial check on every query (<50ms)
    │
    ▼
[5] AuditAgent             llama-3.1-8b-instant
    Construct Casper deploy TX → write to AuditTrail.rs on testnet
    │
    ▼
[6] IntelAgent             llama-3.1-8b-instant
    Serve findings via REST API + MCP tools + x402 pay-per-query gate
```

---

## 🔧 15 MCP Tools

Every tool is implemented, tested, and callable from Claude Desktop:

```python
tools = [
    "get_market_state",       # CSPR price, DEX liquidity, network health
    "detect_anomaly",         # Anomaly classification on address/event
    "get_rwa_risk",           # Live RWA collateral health via Groq Compound
    "query_findings",         # Findings by severity / type / timerange
    "pay_for_intel",          # x402 payment → unlock premium finding
    "get_audit_trail",        # On-chain audit log for any address
    "subscribe_alerts",       # Register webhook for CRITICAL alerts
    "get_agent_trace",        # OTel trace for any agent execution
    "get_risk_score",         # Aggregate risk score for any Casper address
    "stream_events",          # Subscribe to live SSE event stream
    "get_agent_behavior",     # Agent performance index from on-chain
    "upgrade_policy",         # Hot-swap thresholds on RiskPolicyManager
    "get_alert_history",      # Historical alerts from SentinelAlertLog
    "register_subscriber",    # Add address to SentinelRegistry
    "get_subscriber_balance", # Check prepaid credit from SubscriberVault
]
```

### Claude Desktop Integration
```json
{
  "mcpServers": {
    "vaultwatch": {
      "command": "python",
      "args": ["/path/to/vaultwatch/vaultwatch_mcp/server.py"],
      "env": { "GROQ_API_KEY": "your_key" }
    }
  }
}
```

---

## 📦 Smart Contracts

All 8 contracts written in Rust with the [Odra framework](https://odra.dev), compiled to WASM, ready for Casper testnet deployment.

| Contract | Role | Key Innovation |
|----------|------|----------------|
| **AuditTrail** | Immutable on-chain log of every finding | Tamper-proof audit record per address |
| **RiskOracle** | Risk scores queryable by any Casper protocol | Open risk data layer for the ecosystem |
| **SentinelCredit** | x402 credit ledger for pay-per-query | Monetization primitive for risk intelligence |
| **SentinelRegistry** | Subscriber registry for push alerts | Protocol-native alert subscriptions |
| **SentinelAlertLog** | Timestamped alert history per address | Compliance-grade alert auditability |
| **AgentBehaviorIndex** | AI agent performance + confidence on-chain | **First AI accountability primitive on Casper** |
| **RiskPolicyManager** | Hot-swappable risk thresholds | Live governance of AI agent policy |
| **SubscriberVault** | Escrowed prepay balance for subscribers | Bulk subscription with on-chain escrow |

### Build from source
```bash
cd contracts
cargo odra build --release
ls wasm/   # 8 × .wasm files, ~14KB each
```

---

## 📚 Python SDK

```bash
pip install -e sdk/
```

```python
import asyncio
from vaultwatch import VaultWatchClient

async def main():
    async with VaultWatchClient("http://localhost:8000") as client:

        # Risk assessment
        result = await client.query_risk(
            "What are the main risks for Uniswap v3 on Casper?",
            protocol="Uniswap",
            timeframe="7d"
        )
        print(result["analysis"])

        # Anomaly detection
        anomaly = await client.detect_anomaly(
            protocol="CasperSwap",
            tvl=12_000_000,
            volume_24h=18_000_000,
            price_change_1h=-22.0,
            num_transactions=4000,
            liquidity_ratio=0.04,
        )
        print(f"Risk score: {anomaly['risk_score']}")

        # RWA assessment
        rwa = await client.assess_rwa(
            asset_id="ng-tbill-001",
            asset_type="treasury_bill",
            issuer="Central Bank of Nigeria",
            collateral_ratio=1.05,
            maturity_days=91,
            credit_rating="B+",
        )
        print(f"Verdict: {rwa['assessment']['verdict']}")

asyncio.run(main())
```

---

## 🌐 REST API

**OpenAPI docs**: http://localhost:8000/docs

```
GET  /health                       Health check
POST /api/risk/query               Query risk for a protocol
POST /api/risk/detect-anomaly      Detect anomalies in metrics
POST /api/rwa/assess               Assess real-world assets
POST /api/audit/query              Query on-chain audit trail
POST /api/policy/check             Check policy compliance
POST /api/policy/set               Set new risk policy
GET  /api/contracts/{hash}         Get contract state
POST /api/contracts/deploy         Deploy contract to testnet
GET  /api/metrics                  System metrics
GET  /api/agents/status            Agent pipeline status
```

---

## 🎬 Demo Scripts

```bash
# Trigger full risk detection pipeline (mock event → agent pipeline → on-chain write)
npm run demo:risk

# RWA enrichment with live Groq Compound web search
npm run demo:rwa

# Hot-swap RiskPolicyManager threshold on testnet (live TX)
npm run demo:upgrade-policy

# Auto-record full demo as .mp4 (Playwright)
npm run record:demo
```

**`demo:upgrade-policy`** is the flagship demo: risk threshold changes on testnet live, agents immediately reclassify at new threshold, new on-chain finding — all in 30 seconds. No restart. No redeploy.

---

## 🏗️ Project Structure

```
vaultwatch/
├── agents/
│   ├── scanner_agent.py          # Event parsing + classification
│   ├── anomaly_agent.py          # Risk scoring (llama-3.3-70b)
│   ├── self_correction_agent.py  # Quality gate, retry loop
│   ├── rwa_agent.py              # Real-world asset enrichment
│   ├── safety_guard.py           # Prompt injection filter
│   ├── audit_agent.py            # On-chain TX construction
│   └── intel_agent.py            # API serving + x402 gate
│
├── contracts/
│   ├── src/
│   │   ├── audit_trail.rs        # ✅ LIVE: 27249e78...
│   │   ├── risk_oracle.rs        # ✅ LIVE: 68ef325d...
│   │   ├── sentinel_credit.rs    # ✅ LIVE: b6466009...
│   │   ├── sentinel_registry.rs  # ✅ LIVE: 71398513...
│   │   ├── sentinel_alert_log.rs # ✅ LIVE: 8f762ab4...
│   │   ├── agent_behavior_index.rs # ✅ LIVE: 665c1bd2...
│   │   ├── risk_policy_manager.rs  # ✅ LIVE: 14284d5c...
│   │   └── subscriber_vault.rs   # ✅ LIVE: 2fb6b5b6...
│   └── wasm/                     # 8 compiled WASM artifacts
│
├── vaultwatch_mcp/
│   ├── server.py                 # FastMCP — 15 tools (500+ lines)
│   └── __init__.py
│
├── api/
│   ├── main.py                   # FastAPI + OTel instrumentation
│   └── routes/
│
├── sdk/
│   └── vaultwatch/
│       ├── client.py             # Async HTTP client
│       ├── contracts.py          # Contract interfaces
│       ├── types.py              # Type definitions
│       └── otel_instrumentation.py
│
├── streaming/
│   └── sidecar_client.py         # Casper Sidecar SSE pipeline
│
├── dashboard/
│   └── src/                      # React/Vite frontend (800+ lines)
│
├── tests/
│   ├── unit/                     # 66 unit tests
│   ├── integration/              # 37 integration tests
│   └── demo/                     # 4 end-to-end tests
│
├── scripts/
│   ├── demo_risk.py
│   ├── demo_rwa.py
│   ├── demo_upgrade_policy.py
│   ├── deploy_contracts.py
│   └── record_demo.py
│
├── pipeline.py                   # Main agent pipeline orchestrator
├── casper_client.py              # Casper Python SDK wrapper
├── deploy_hashes.json            # Contract deploy hash references
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── package.json
```

---

## ⚙️ Configuration

```bash
# Required
GROQ_API_KEY=your_groq_key           # Free at console.groq.com

# Casper Network
CASPER_NODE_URL=https://rpc.testnet.casperlabs.io/rpc
CASPER_CHAIN_NAME=casper-test
CASPER_ACCOUNT_SECRET_KEY=your_key   # For live testnet deploys

# CSPR.cloud (optional — enables contract state queries)
CSPR_CLOUD_API_URL=https://api.testnet.cspr.cloud
CSPR_CLOUD_API_KEY=your_key

# Casper Sidecar (real-time streaming)
CASPER_SIDECAR_URL=http://127.0.0.1:18888/events/main

# x402 Pay-per-Query
X402_PAYMENT_AMOUNT=1000000          # motes

# API
API_HOST=0.0.0.0
API_PORT=8000

# Dashboard
VITE_API_URL=http://localhost:8000

# OpenTelemetry (optional — stdout by default)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=vaultwatch

# Mock mode (tests run without Casper node)
CASPER_MOCK=true
```

---

## 🔁 CI/CD

Every push to `main` runs:

1. **Python Tests** — all 107 tests across unit, integration, demo
2. **Lint & Format** — `ruff check` + `ruff format --check`
3. **Contract Tests** — `cargo test --workspace`
4. **Docker Build** — full image build verification
5. **SDK Validation** — install + import check

[![CI](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml)

---

## 🌱 Ecosystem Integration

Any Casper DeFi protocol integrates VaultWatch in 3 steps:

```bash
# 1. Install SDK
pip install -e sdk/

# 2. Configure
export GROQ_API_KEY=your_key
export CASPER_NODE_URL=https://rpc.testnet.casperlabs.io/rpc

# 3. Query
python -c "
from vaultwatch import VaultWatchClient
import asyncio
async def main():
    async with VaultWatchClient('http://localhost:8000') as c:
        r = await c.query_risk('Is this protocol safe?', protocol='MyProtocol')
        print(r)
asyncio.run(main())
"
```

**OTel integration** — one env var, full agent traces in existing Grafana stack:
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://your-grafana-agent:4317 python pipeline.py
```

---

## 📄 License

MIT License · Copyright (c) 2026 Sodiq Jimoh

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

---

## 🔗 Links

| | |
|---|---|
| **Repository** | https://github.com/sodiq-code/vaultwatch |
| **Hackathon** | https://dorahacks.io/hackathon/casper-agentic-buildathon/detail |
| **Casper Testnet Explorer** | https://testnet.cspr.live/ |
| **Casper Testnet Faucet** | https://testnet.cspr.live/faucet |
| **Casper Developer Docs** | https://docs.casper.network/ |
| **Odra Framework** | https://odra.dev/ |
| **Groq Console** | https://console.groq.com/ |
| **FastMCP** | https://github.com/jlowin/fastmcp |
| **CSPR.cloud API** | https://docs.cspr.cloud/ |

---

**Built by [Sodiq Jimoh](https://github.com/sodiq-code) · Casper Agentic Buildathon 2026**
