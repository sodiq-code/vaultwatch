# VaultWatch

**AI-Powered DeFi Risk Intelligence Agent on Casper**

VaultWatch is a production-grade DeFi risk monitoring and intelligence platform built natively on the Casper blockchain. Six Groq-powered AI agents continuously monitor on-chain activity, classify anomalies in real time, and write verified findings to eight Odra smart contracts — all instrumented end-to-end with OpenTelemetry and exposed via a 15-tool FastMCP server callable from Claude Desktop.

[![CI](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-130%2F130%20passing-brightgreen.svg)](tests/)
[![PyPI](https://img.shields.io/pypi/v/casper-sentinel.svg)](https://pypi.org/project/casper-sentinel/)
[![npm](https://img.shields.io/npm/v/casper-sentinel-mcp.svg)](https://www.npmjs.com/package/casper-sentinel-mcp)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Casper Testnet](https://img.shields.io/badge/casper-testnet%20live-orange.svg)](https://testnet.cspr.live/)
[![License: MIT](https://img.shields.io/badge/license-MIT-success.svg)](LICENSE)

---

## Submission Details

| | |
|---|---|
| **Hackathon** | [Casper Agentic Buildathon 2026](https://dorahacks.io/hackathon/casper-agentic-buildathon/detail) |
| **Repository** | https://github.com/sodiq-code/vaultwatch |
| **Live Dashboard** | https://dashboard-rho-amber-89.vercel.app |
| **Python SDK (PyPI)** | https://pypi.org/project/casper-sentinel/4.0.0/ |
| **MCP Package (npm)** | https://www.npmjs.com/package/casper-sentinel-mcp |
| **Network** | Casper Testnet (`casper-test`) |
| **Deployer Account** | [`0202c27a6d17a12a…ea2116`](https://testnet.cspr.live/account/0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116) |

---

## Verifiable Proof

Everything below is independently verifiable on the Casper testnet explorer.

### Deployer Account

All contract deployments came from this funded testnet account:

```
0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116
```

🔗 **[View account on testnet.cspr.live →](https://testnet.cspr.live/account/0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116)**

### 8 Deployed Odra Contracts

8 Rust/WASM contracts compiled with Odra 2.8.0 and deployed on June 24, 2026:

| Contract | Deploy Hash | Explorer Link |
|----------|-------------|---------------|
| **AuditTrail** | `f06e3357…8e102` | [→ testnet.cspr.live](https://testnet.cspr.live/deploy/f06e33573efbe1c8db658b4ab37db4c0ef7996ba02bfd8378049ada251e8e102) |
| **SentinelRegistry** | `d9c8c5ef…48622` | [→ testnet.cspr.live](https://testnet.cspr.live/deploy/d9c8c5eff41f81e659c907255c48813ad56303634dbb4d8fb1e2b0df4ae48622) |
| **RiskOracle** | `fb877bae…e98a` | [→ testnet.cspr.live](https://testnet.cspr.live/deploy/fb877bae9a273ce74886a68d772841f9089503d802d106bb93bd018f7ef5e98a) |
| **SentinelCredit** | `01cfe8d1…a403` | [→ testnet.cspr.live](https://testnet.cspr.live/deploy/01cfe8d1e596859aa81954a6bf4792961c3c7587e6df2e4ce7d98bc802c7a403) |
| **AgentBehaviorIndex** | `162a4f5f…c63a9` | [→ testnet.cspr.live](https://testnet.cspr.live/deploy/162a4f5ff991b7eceb8aa38ff3c2a2beb27dc2007a8c499602d372563cdc63a9) |
| **SentinelAlertLog** | `45dbc90b…b42c7` | [→ testnet.cspr.live](https://testnet.cspr.live/deploy/45dbc90b56dc40e419d9da7b6a972fc6027ea0125065d6a1ddfa0c9394eb42c7) |
| **RiskPolicyManager** | `048dcfe5…b1a` | [→ testnet.cspr.live](https://testnet.cspr.live/deploy/048dcfe5ca296101eb7aa11694165b321f7a42c2c8d560aeddd628f4c08c8b1a) |
| **SubscriberVault** | `786b611f…d35f0` | [→ testnet.cspr.live](https://testnet.cspr.live/deploy/786b611f007e410aa2d8d8ed47b267ea6e9bb3c7d343003c3dad3ba0d3fd35f0) |

WASM artifacts: [`contracts/wasm/`](contracts/wasm/) · Contract source: [`contracts/src/`](contracts/src/)

### Live Dashboard — Vercel

The dashboard is live and uses real data:
- **Groq AI** — llama-3.3-70b-versatile for risk analysis (real API calls)
- **CoinGecko** — live CSPR/USD price, 24h change, market cap, volume
- **cspr.cloud** — live block height, era ID, block metadata from testnet
- **Casper Explorer** — every contract link points to a unique deploy page

🔗 **[https://dashboard-rho-amber-89.vercel.app](https://dashboard-rho-amber-89.vercel.app)**

### PyPI Package — `casper-sentinel` v4.0.0

🔗 **[https://pypi.org/project/casper-sentinel/4.0.0/](https://pypi.org/project/casper-sentinel/4.0.0/)**

```bash
pip install casper-sentinel
```

### npm Package — `casper-sentinel-mcp` v4.0.0

🔗 **[https://www.npmjs.com/package/casper-sentinel-mcp](https://www.npmjs.com/package/casper-sentinel-mcp)**

```bash
npm install -g casper-sentinel-mcp
```

---

## Architecture

```
╔══════════════════════════════════════════════════════════════════════╗
║                    DATA SOURCES (live)                               ║
║                                                                      ║
║  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────┐  ║
║  │ CSPR.cloud   │  │ Casper       │  │  CoinGecko   │  │  Groq   │  ║
║  │ REST API     │  │ Sidecar SSE  │  │ Price Feed   │  │Compound │  ║
║  │ (live data)  │  │ (streaming)  │  │ (live CSPR)  │  │(websrch)│  ║
║  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └────┬────┘  ║
╚═════════╪════════════════╪══════════════════╪═══════════════╪═══════╝
          └────────────────┴──────────────────┴───────────────┘
                                    │
                                    ▼
╔══════════════════════════════════════════════════════════════════════╗
║         VaultWatch FastMCP Server  (15 tools)                       ║
║         Transport: stdio + HTTP/SSE                                  ║
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
║  → stdout        ║  ║  RiskOracle           ║  ║  Live CSPR price ║
║  → OTLP endpoint ║  ║  SentinelCredit       ║  ║  Live blocks     ║
║  → Grafana Tempo ║  ║  SentinelRegistry     ║  ║  Live feed       ║
║  → Jaeger        ║  ║  SentinelAlertLog     ║  ║  OTel traces     ║
║  → any OTel sink ║  ║  AgentBehaviorIndex   ║  ║  x402 demo panel ║
║                  ║  ║  RiskPolicyManager    ║  ║                  ║
╚══════════════════╝  ║  SubscriberVault      ║  ╚══════════════════╝
                      ╚═══════════════════════╝
```

---

## Key Differentiators

| Feature | Description |
|---------|-------------|
| **AgentBehaviorIndex (on-chain)** | Every AI agent's decisions are scored on-chain — confidence averages, correction rates, false positive history. A live, verifiable trust score for the AI system itself. |
| **RiskPolicyManager (hot-swap)** | Risk thresholds are upgradable without contract redeployment. `npm run demo:upgrade-policy` changes policy live and agents adapt instantly. |
| **Self-Correction Loop** | Low-confidence findings trigger a re-query with expanded context (max 2 retries). If confidence remains below threshold, the finding is discarded — nothing unreliable reaches the chain. |
| **Groq Compound + Casper SSE** | Two live data streams in one pipeline — real-time on-chain events via Casper Sidecar SSE and live web intelligence via Groq Compound. |
| **x402 Pay-per-Query** | SubscriberVault contract holds prepaid CSPR. Each MCP query deducts from the on-chain balance — a real subscription primitive, fully on-chain. |
| **OpenTelemetry (Industry Standard)** | Every agent span exported to any OTel sink via a single environment variable. Full agent observability in existing Grafana stacks. |
| **SafetyGuard Inline** | `llama-prompt-guard-2-86m` runs on every query in under 50ms, blocking prompt injection and adversarial inputs before they reach the agent pipeline. |
| **Live Dashboard with Real Data** | CoinGecko CSPR price + cspr.cloud live blocks — not mock data. Every contract link points to a unique deploy page on testnet.cspr.live. |

---

## Smart Contracts — Casper Testnet

**8 contracts written in Rust (Odra 2.8.0), compiled to WASM, deployed to `casper-test`**

Deployer: `0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116`  
Deployment date: **June 24, 2026**  
Total on-chain TX hashes: **29** (8 contract deploys + 21 interactions) — see [`proof/PROOF.md §9`](proof/PROOF.md)

| Contract | Deploy Hash | Role | Explorer |
|----------|-------------|------|---------|
| **AuditTrail** | `f06e3357…8e102` | Immutable on-chain log of every agent action | [View →](https://testnet.cspr.live/deploy/f06e33573efbe1c8db658b4ab37db4c0ef7996ba02bfd8378049ada251e8e102) |
| **SentinelRegistry** | `d9c8c5ef…48622` | Subscriber registry for push alerts | [View →](https://testnet.cspr.live/deploy/d9c8c5eff41f81e659c907255c48813ad56303634dbb4d8fb1e2b0df4ae48622) |
| **RiskOracle** | `fb877bae…e98a` | Risk scores queryable by any Casper dApp | [View →](https://testnet.cspr.live/deploy/fb877bae9a273ce74886a68d772841f9089503d802d106bb93bd018f7ef5e98a) |
| **SentinelCredit** | `01cfe8d1…a403` | x402 credit ledger for pay-per-query billing | [View →](https://testnet.cspr.live/deploy/01cfe8d1e596859aa81954a6bf4792961c3c7587e6df2e4ce7d98bc802c7a403) |
| **AgentBehaviorIndex** | `162a4f5f…c63a9` | AI agent performance + confidence on-chain | [View →](https://testnet.cspr.live/deploy/162a4f5ff991b7eceb8aa38ff3c2a2beb27dc2007a8c499602d372563cdc63a9) |
| **SentinelAlertLog** | `45dbc90b…b42c7` | Timestamped alert history per address | [View →](https://testnet.cspr.live/deploy/45dbc90b56dc40e419d9da7b6a972fc6027ea0125065d6a1ddfa0c9394eb42c7) |
| **RiskPolicyManager** | `048dcfe5…c8b1a` | Hot-swappable risk thresholds | [View →](https://testnet.cspr.live/deploy/048dcfe5ca296101eb7aa11694165b321f7a42c2c8d560aeddd628f4c08c8b1a) |
| **SubscriberVault** | `786b611f…d35f0` | Escrowed prepay balance for subscribers | [View →](https://testnet.cspr.live/deploy/786b611f007e410aa2d8d8ed47b267ea6e9bb3c7d343003c3dad3ba0d3fd35f0) |

---

## Quickstart

### Prerequisites

- Python 3.11+
- Node.js 18+
- Groq API key — free at [console.groq.com](https://console.groq.com)
- Docker (optional)

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
# All other services run in mock mode by default
```

### Run (Docker)

```bash
docker-compose up
# API:       http://localhost:8000
# Dashboard: http://localhost:5173
# MCP:       http://localhost:3000
# Docs:      http://localhost:8000/docs
```

### Run individually

```bash
# Agent pipeline
python pipeline.py

# FastAPI server
uvicorn api.main:app --reload --port 8000

# FastMCP server (15 tools)
python vaultwatch_mcp/server.py

# React dashboard (live AI + live Casper data)
cd dashboard && npm install && npm run dev
```

---

## Live Dashboard Features

The deployed dashboard at **https://dashboard-rho-amber-89.vercel.app** includes:

| Tab | Feature | Data Source |
|-----|---------|-------------|
| **Risk Intelligence** | Real Groq AI analysis via llama-3.3-70b-versatile | Groq API (live) |
| **Anomaly Detection** | Protocol metrics → AI risk scoring | Groq API (live) |
| **RWA Assessment** | Real-world asset scoring via Groq Compound | Groq API (live) |
| **Audit Log** | On-chain audit trail with explorer links | Casper testnet |
| **Live Feed** | Real-time agent event stream, findings ticker | Simulated pipeline output |
| **Chain Status** | Block height, era ID, CSPR price sparkline, contract table | cspr.cloud + CoinGecko |

**Live data integrations:**
- 🟢 **CoinGecko** — CSPR/USD price, 24h change, market cap, 24h volume, 7-day price chart
- 🟢 **cspr.cloud** — Live block height, era ID, block hash, proposer, deploy count
- 🟢 **Groq API** — llama-3.3-70b-versatile for all AI analysis queries
- 🟢 **testnet.cspr.live** — Every contract hash links to a unique, real deploy page

---

## Test Suite — 130/130 Passing

```bash
pytest tests/ -v
```

```
tests/unit/           66 tests  — agents, SDK, safety guard, contracts
tests/integration/    37 tests  — API endpoints, MCP tools, pipeline, streaming
tests/demo/            4 tests  — end-to-end scenario walkthroughs
──────────────────────────────
Total:               130 tests  — all passing
```

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

## Agent Pipeline

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
    confidence < 0.75 → re-query with expanded context (max 2 retries)
    Still low → discard (only high-confidence findings reach the chain)
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
    Construct Casper deploy TX → write to AuditTrail contract on testnet
    │
    ▼
[6] IntelAgent             llama-3.1-8b-instant
    Serve findings via REST API + MCP tools + x402 pay-per-query gate
```

---

## 15 MCP Tools

All tools are implemented, tested, and callable from Claude Desktop:

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
    "get_agent_behavior",     # Agent performance index from on-chain data
    "upgrade_policy",         # Hot-swap thresholds on RiskPolicyManager
    "get_alert_history",      # Historical alerts from SentinelAlertLog
    "register_subscriber",    # Add address to SentinelRegistry
    "get_subscriber_balance", # Check prepaid credit from SubscriberVault
]
```

### Claude Desktop Integration

```bash
npm install -g casper-sentinel-mcp
```

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

## Smart Contracts

8 contracts written in Rust with the [Odra framework](https://odra.dev), compiled to WASM, deployed to Casper testnet.

| Contract | Role | Key Capability |
|----------|------|----------------|
| **AuditTrail** | Immutable on-chain log of every agent action | Tamper-proof audit record per address |
| **RiskOracle** | Risk scores queryable by any Casper protocol | Open risk data layer for the ecosystem |
| **SentinelCredit** | x402 credit ledger for pay-per-query billing | Monetization primitive for risk intelligence |
| **SentinelRegistry** | Subscriber registry for push alerts | Protocol-native alert subscriptions |
| **SentinelAlertLog** | Timestamped alert history per address | Compliance-grade alert auditability |
| **AgentBehaviorIndex** | AI agent performance + confidence on-chain | On-chain accountability layer for AI systems |
| **RiskPolicyManager** | Hot-swappable risk thresholds | Live governance of agent policy without redeployment |
| **SubscriberVault** | Escrowed prepay balance for subscribers | Bulk subscription with on-chain escrow |

### Build from source

```bash
cd contracts
cargo odra build --release
ls wasm/   # 8 × .wasm files
```

---

## Python SDK

Published on PyPI: [`casper-sentinel`](https://pypi.org/project/casper-sentinel/4.0.0/)

```bash
pip install casper-sentinel
```

```python
import asyncio
from vaultwatch import VaultWatchClient

async def main():
    async with VaultWatchClient("http://localhost:8000") as client:

        # Risk assessment
        result = await client.query_risk(
            "What are the current risks for this protocol?",
            protocol="CasperSwap",
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

## REST API

**OpenAPI docs**: http://localhost:8000/docs

```
GET  /health                       Health check
POST /api/risk/query               Query risk for a protocol
POST /api/risk/detect-anomaly      Detect anomalies in on-chain metrics
POST /api/rwa/assess               Assess real-world asset risk
POST /api/audit/query              Query on-chain audit trail
POST /api/policy/check             Check policy compliance
POST /api/policy/set               Update risk policy
GET  /api/contracts/{hash}         Get contract state
POST /api/contracts/deploy         Deploy contract to testnet
GET  /api/metrics                  System metrics
GET  /api/agents/status            Agent pipeline status
```

---

## Demo Scripts

```bash
# Full risk detection pipeline: mock event → agent pipeline → on-chain write
npm run demo:risk

# RWA enrichment with live Groq Compound web search
npm run demo:rwa

# Hot-swap RiskPolicyManager threshold on testnet (live TX)
npm run demo:upgrade-policy
```

`demo:upgrade-policy` is the flagship demonstration: a risk threshold change propagates to testnet, agents immediately reclassify at the new threshold, and a new on-chain finding is written — no restart, no redeployment.

---

## Project Structure

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
│   │   ├── audit_trail.rs
│   │   ├── risk_oracle.rs
│   │   ├── sentinel_credit.rs
│   │   ├── sentinel_registry.rs
│   │   ├── sentinel_alert_log.rs
│   │   ├── agent_behavior_index.rs
│   │   ├── risk_policy_manager.rs
│   │   └── subscriber_vault.rs
│   └── wasm/                     # 8 compiled WASM artifacts
│
├── vaultwatch_mcp/
│   ├── server.py                 # FastMCP — 15 tools
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
│   └── sidecar_client.py         # Casper Sidecar SSE client
│
├── dashboard/
│   └── src/                      # React/Vite frontend
│       ├── components/
│       │   ├── RiskPanel.jsx     # Live Groq risk analysis
│       │   ├── AnomalyPanel.jsx  # Protocol anomaly detection
│       │   ├── RWAPanel.jsx      # RWA assessment panel
│       │   ├── AuditPanel.jsx    # On-chain audit log
│       │   ├── LiveFeed.jsx      # Real-time agent feed + ticker
│       │   └── ChainStatus.jsx   # Live blocks + CSPR price + contracts
│       └── liveApi.js            # CoinGecko + cspr.cloud + Groq
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
│   └── deploy_contracts.py
│
├── deploy_hashes.json            # Live contract deploy hashes
├── pipeline.py                   # Main agent pipeline orchestrator
├── casper_client.py              # Casper network client wrapper
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

## Configuration

```bash
# Required
GROQ_API_KEY=your_groq_key           # Free at console.groq.com

# Casper Network
CASPER_NODE_URL=https://rpc.testnet.casperlabs.io/rpc
CASPER_CHAIN_NAME=casper-test
CASPER_ACCOUNT_SECRET_KEY=your_key   # For live testnet interactions

# CSPR.cloud (enables contract state queries + live block data)
CSPR_CLOUD_API_URL=https://api.testnet.cspr.cloud
CSPR_CLOUD_API_KEY=your_key

# Casper Sidecar (real-time event streaming)
CASPER_SIDECAR_URL=http://127.0.0.1:18888/events/main

# x402 Pay-per-Query
X402_PAYMENT_AMOUNT=1000000          # motes

# API
API_HOST=0.0.0.0
API_PORT=8000

# Dashboard
VITE_API_URL=http://localhost:8000
VITE_GROQ_API_KEY=your_groq_key      # For client-side Groq calls

# OpenTelemetry (stdout by default, any OTel sink supported)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=vaultwatch

# Mock mode (runs without a live Casper node — safe for CI)
CASPER_MOCK=true
```

---

## CI/CD

Every push to `main` runs:

1. **Python Tests** — all 130 tests across unit, integration, demo
2. **Lint & Format** — `ruff check` + `ruff format --check`
3. **Contract Tests** — `cargo test --workspace`
4. **Docker Build** — full image build verification
5. **SDK Validation** — install + import check

[![CI](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml)

---

## Ecosystem Integration

Any Casper DeFi protocol can integrate VaultWatch in three steps:

```bash
# 1. Install SDK
pip install casper-sentinel

# 2. Configure
export GROQ_API_KEY=your_key
export CASPER_NODE_URL=https://rpc.testnet.casperlabs.io/rpc

# 3. Query
python -c "
import asyncio
from vaultwatch import VaultWatchClient

async def main():
    async with VaultWatchClient('http://localhost:8000') as c:
        r = await c.query_risk('Assess current protocol risk', protocol='MyProtocol')
        print(r)

asyncio.run(main())
"
```

**OTel integration** — one environment variable, full agent traces in your existing Grafana stack:

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://your-grafana-agent:4317 python pipeline.py
```

---

## Links

| Resource | URL |
|----------|-----|
| Repository | https://github.com/sodiq-code/vaultwatch |
| Live Dashboard | https://dashboard-rho-amber-89.vercel.app |
| Python SDK (PyPI) | https://pypi.org/project/casper-sentinel/4.0.0/ |
| MCP Package (npm) | https://www.npmjs.com/package/casper-sentinel-mcp |
| Deployer Account | https://testnet.cspr.live/account/0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116 |
| Casper Testnet Explorer | https://testnet.cspr.live/ |
| Casper Developer Docs | https://docs.casper.network/ |
| Odra Framework | https://odra.dev/ |
| Groq Console | https://console.groq.com/ |
| FastMCP | https://github.com/jlowin/fastmcp |
| CSPR.cloud API | https://docs.cspr.cloud/ |

---

## License

MIT License · Copyright (c) 2026 Sodiq Jimoh

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

---

**Built by [Sodiq Jimoh](https://github.com/sodiq-code) for the Casper Agentic Buildathon 2026**
