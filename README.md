# VaultWatch

**AI-Powered DeFi Risk Intelligence Agent on Casper**

VaultWatch is a production-grade DeFi risk monitoring and intelligence platform built natively on the Casper blockchain. Seven Groq-powered AI agents (6 pipeline + SafetyGuard) continuously monitor on-chain activity, classify anomalies in real time, and write verified findings to eight Odra smart contracts — all instrumented end-to-end with OpenTelemetry and exposed via a 20-tool FastMCP server callable from Claude Desktop.

[![CI](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml)
[![Build Contracts](https://github.com/sodiq-code/vaultwatch/actions/workflows/build-contracts.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/build-contracts.yml)
[![CodeQL](https://github.com/sodiq-code/vaultwatch/actions/workflows/codeql.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/codeql.yml)
[![Tests](https://img.shields.io/badge/tests-100%2B%20passing-brightgreen.svg)](tests/)
[![PyPI](https://img.shields.io/pypi/v/casper-sentinel.svg)](https://pypi.org/project/casper-sentinel/)
[![npm](https://img.shields.io/npm/v/casper-sentinel-mcp.svg)](https://www.npmjs.com/package/casper-sentinel-mcp)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Casper Testnet](https://img.shields.io/badge/casper-testnet%20live-orange.svg)](https://testnet.cspr.live/)
[![License: MIT](https://img.shields.io/badge/license-MIT-success.svg)](LICENSE)

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Hybrid Reputation Formula** ([docs](docs/REPUTATION_FORMULA.md)) | Combines Brier-scored AI agent accuracy + escrow-derived economic trust into one reputation number with tunable weights |
| **12-Check Red-Team Checklist** ([docs](docs/RED_TEAM_CHECKLIST.md)) | Adversarial analysis of the reputation formula — 8/12 fully resist, 4/12 partial, 0/12 vulnerable |
| **20-Tool MCP Server** ([server](vaultwatch_mcp/server.py)) | agent_attestation, reputation_query, x402_subscribe, policy_hotswap, behavior_index_lookup + 15 original tools = 20 total |
| **Official x402 SDK** ([x402/](x402/)) | `@make-software/casper-x402` integration for real payment verification |
| **Bulk-Memory-Safe WASM Build** ([script](scripts/build_contracts.sh)) | CI compiles 8 contracts with `-C target-feature=-bulk-memory` + `wasm-opt` + automated opcode gate |

---

## Demo Video

[![VaultWatch Demo](https://img.youtube.com/vi/Jmg_MFSxwdE/maxresdefault.jpg)](https://youtu.be/Jmg_MFSxwdE)

**[▶ Watch on YouTube — VaultWatch: AI-Powered DeFi Risk Intelligence on Casper Blockchain](https://youtu.be/Jmg_MFSxwdE)**

---

## Submission Details

| | |
|---|---|
| **Demo Video** | https://youtu.be/Jmg_MFSxwdE |
| **Live Dashboard** | https://dashboard-rho-amber-89.vercel.app |
| **Python SDK (PyPI)** | https://pypi.org/project/casper-sentinel/ |
| **MCP Package (npm)** | https://www.npmjs.com/package/casper-sentinel-mcp |
| **x402 Package (npm)** | `@vaultwatch/x402` (new — see [x402/](x402/)) |
| **Network** | Casper Testnet (`casper-test`) |
| **Deployer Account** | `0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7` — [view on explorer →](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7) |
| **Reputation Formula** | [docs/REPUTATION_FORMULA.md](docs/REPUTATION_FORMULA.md) |
| **Red-Team Checklist** | [docs/RED_TEAM_CHECKLIST.md](docs/RED_TEAM_CHECKLIST.md) |
| **Deployment Guide** | [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) |

---

## Verifiable Proof

All deployments below are independently verifiable on the Casper testnet explorer.

### Deployer Account

All contract deployments came from this funded testnet account:

```
0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7
```

**[View account on testnet.cspr.live →](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7)**

### 8 Deployed Odra Contracts

8 Rust/WASM contracts compiled with Odra 2.8.0, bulk-memory-safe WASM, deployed to `casper-test` (protocol 2.2.2). All 8 deploys **VERIFIED SUCCESS** — 16 named keys on the deployer account.

| Contract | Transaction Hash | Explorer Link |
|----------|-------------|---------------|
| **AuditTrail** | `b9c70cdc…336a7` | [→ testnet.cspr.live](https://testnet.cspr.live/deploy/b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6333a7) |
| **SentinelRegistry** | `9a5eb4f8…346c` | [→ testnet.cspr.live](https://testnet.cspr.live/deploy/9a5eb4f83de8cbfef4f389516b977258b0e1d63179b288ca623a860fc6ec346c) |
| **RiskOracle** | `e071aacc…7c9d` | [→ testnet.cspr.live](https://testnet.cspr.live/deploy/e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d) |
| **SentinelCredit** | `0c09f2ad…af71` | [→ testnet.cspr.live](https://testnet.cspr.live/deploy/0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71) |
| **AgentBehaviorIndex** | `05066c33…7dd0` | [→ testnet.cspr.live](https://testnet.cspr.live/deploy/05066c33ddb73b523ab8f67275ca6096254f9d1832e76075d1e5f41f188b7dd0) |
| **SentinelAlertLog** | `53317e08…a925` | [→ testnet.cspr.live](https://testnet.cspr.live/deploy/53317e080ffdffcf097447ea3375c9195c6936fe7b1ed53795bf46134322a925) |
| **RiskPolicyManager** | `93e35d64…ee2e` | [→ testnet.cspr.live](https://testnet.cspr.live/deploy/93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e) |
| **SubscriberVault** | `6620787c…956d` | [→ testnet.cspr.live](https://testnet.cspr.live/deploy/6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d) |

WASM artifacts: [`contracts/wasm/`](contracts/wasm/) · Contract source: [`contracts/src/`](contracts/src/)

### Live Dashboard — Vercel

The dashboard is live and uses real data:
- **Groq AI** — llama-3.3-70b-versatile for risk analysis (real API calls)
- **CoinGecko** — live CSPR/USD price, 24h change, market cap, volume
- **cspr.cloud** — live block height, era ID, block metadata from testnet
- **Casper Explorer** — every contract link points to a unique deploy page

**[https://dashboard-rho-amber-89.vercel.app](https://dashboard-rho-amber-89.vercel.app)**

### PyPI Package — `casper-sentinel` v4.0.0

**[https://pypi.org/project/casper-sentinel/4.0.0/](https://pypi.org/project/casper-sentinel/4.0.0/)**

```bash
pip install casper-sentinel
```

### npm Package — `casper-sentinel-mcp` v4.0.0

**[https://www.npmjs.com/package/casper-sentinel-mcp](https://www.npmjs.com/package/casper-sentinel-mcp)**

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
║         VaultWatch FastMCP Server  (20 tools)                       ║
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

**8 contracts written in Rust (Odra 2.8.0), compiled to bulk-memory-safe WASM, deployed to `casper-test`**

Deployer: `0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7`  
Deployment date: **July 11, 2026** (redeployed — original June 24 deploys failed with bulk-memory error)  
All 8 deploys **VERIFIED SUCCESS** — 16 named keys on deployer account, 135-143 CSPR gas each. See [`proof/PROOF.md`](proof/PROOF.md) for verification details.

| Contract | Transaction Hash | Role | Explorer |
|----------|-------------|------|---------|
| **AuditTrail** | `b9c70cdc…336a7` | Immutable on-chain log of every agent action | [View →](https://testnet.cspr.live/deploy/b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6333a7) |
| **SentinelRegistry** | `9a5eb4f8…346c` | Subscriber registry for push alerts | [View →](https://testnet.cspr.live/deploy/9a5eb4f83de8cbfef4f389516b977258b0e1d63179b288ca623a860fc6ec346c) |
| **RiskOracle** | `e071aacc…7c9d` | Risk scores queryable by any Casper dApp | [View →](https://testnet.cspr.live/deploy/e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d) |
| **SentinelCredit** | `0c09f2ad…af71` | x402 credit ledger for pay-per-query billing | [View →](https://testnet.cspr.live/deploy/0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71) |
| **AgentBehaviorIndex** | `05066c33…7dd0` | AI agent performance + confidence on-chain | [View →](https://testnet.cspr.live/deploy/05066c33ddb73b523ab8f67275ca6096254f9d1832e76075d1e5f41f188b7dd0) |
| **SentinelAlertLog** | `53317e08…a925` | Timestamped alert history per address | [View →](https://testnet.cspr.live/deploy/53317e080ffdffcf097447ea3375c9195c6936fe7b1ed53795bf46134322a925) |
| **RiskPolicyManager** | `93e35d64…ee2e` | Hot-swappable risk thresholds | [View →](https://testnet.cspr.live/deploy/93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e) |
| **SubscriberVault** | `6620787c…956d` | Escrowed prepay balance for subscribers | [View →](https://testnet.cspr.live/deploy/6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d) |

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

# FastMCP server (20 tools)
python vaultwatch_mcp/server.py

# React dashboard (live AI + live Casper data)
cd dashboard && npm install && npm run dev
```

---

## Live Dashboard Features

The deployed dashboard at **https://dashboard-rho-amber-89.vercel.app** includes:

| Tab | Feature | Data Source |
|-----|---------|-------------|
| **Risk Intelligence** | Groq AI analysis via llama-3.3-70b-versatile | Groq API |
| **Anomaly Detection** | Protocol metrics → AI risk scoring | Groq API |
| **RWA Assessment** | Real-world asset scoring via Groq Compound | Groq API |
| **Audit Log** | On-chain audit trail with explorer links | Casper testnet |
| **Live Feed** | Animated agent activity feed with realistic pipeline simulation + findings ticker linked to on-chain contracts | Demos full pipeline event flow (7 agents), contract-linked findings |
| **Chain Status** | Block height, era ID, CSPR price sparkline, contract table | cspr.cloud + CoinGecko |

**Live data integrations:**
- **CoinGecko** — CSPR/USD price, 24h change, market cap, 24h volume, 7-day price chart
- **cspr.cloud** — Live block height, era ID, block hash, proposer, deploy count
- **Groq API** — llama-3.3-70b-versatile for all AI analysis queries
- **testnet.cspr.live** — Every contract hash links to a unique deploy page on the Casper explorer

---

## Test Suite — 100+ Passing

```bash
pytest tests/ -v
```

```
tests/unit/           77 tests  — agents, SDK, safety guard, contracts
tests/integration/    37 tests  — API endpoints, MCP tools, pipeline, streaming
tests/demo/            4 tests  — end-to-end scenario walkthroughs
──────────────────────────────
Total:               100+ tests  — all passing
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

## 20 MCP Tools

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
    "get_subscriber_balance",   # Check prepaid credit from SubscriberVault
    # 5 new tools
    "agent_attestation",        # On-chain AI agent attestation
    "reputation_query",         # Hybrid Brier + escrow-derived reputation score
    "x402_subscribe",           # Official @make-software/casper-x402 paid subscription
    "policy_hotswap",           # Atomic risk-policy upgrade with rollback safety
    "behavior_index_lookup",    # Cross-agent trust comparison + ranking
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

8 contracts written in Rust with the [Odra framework](https://odra.dev), compiled to bulk-memory-safe WASM, deployed to Casper testnet.

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

`demo:upgrade-policy` exercises the hot-swap architecture end-to-end: a risk threshold change propagates to testnet, agents reclassify at the new threshold, and a new on-chain finding is written — no restart, no redeployment.

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
│   ├── server.py                 # FastMCP — 20 tools
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
├── transaction_hashes.json            # Live contract deploy hashes
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
# SECURITY (Critical Fix 7): the Groq key is SERVER-SIDE ONLY. It MUST live
# in GROQ_API_KEY and NEVER in any VITE_* variable — Vite ships VITE_*
# values to the browser bundle. The dashboard never reads this key directly;
# all Groq calls go through the FastAPI proxy at /api/agent/*.
GROQ_API_KEY=your_groq_key           # Free at console.groq.com

# Casper Network
CASPER_NODE_URL=https://node.testnet.casper.network/rpc
CASPER_CHAIN_NAME=casper-test
CASPER_ACCOUNT_SECRET_KEY=your_key   # For live testnet interactions

# CSPR.cloud (enables contract state queries + live block data)
# SECURITY (Critical Fix 6): the key MUST live in this env var only — never
# in source. The dashboard never reads it directly; all cspr.cloud REST
# calls go through the FastAPI reverse proxy at /api/cspr_cloud/* (dev) or
# ${VITE_API_URL}/cspr_cloud/* (prod). See SECURITY.md for the full policy.
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

# OpenTelemetry (stdout by default, any OTel sink supported)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=vaultwatch

# Mock mode (runs without a live Casper node — safe for CI)
CASPER_MOCK=true
```

---

## CI/CD

Every push to `main` runs:

1. **Python Tests** — all 100+ tests across unit, integration, demo
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
export CASPER_NODE_URL=https://node.testnet.casper.network/rpc

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

## Long-Term Launch Plan & Ecosystem Impact

> **[→ Full document: `docs/LAUNCH_AND_IMPACT.md`](docs/LAUNCH_AND_IMPACT.md)**

VaultWatch is designed as permanent Casper infrastructure. Four deployment phases sequenced directly against the [Casper Manifest](https://www.casper.network/testing/roadmap):

- **Phase 1 — Done** · 8 contracts live, 8 verified contract deploys, 2 published packages, 100+ tests, live dashboard
- **Phase 2 — Q3 2026** · Mainnet migration + 3 protocol integrations as X402 and EVM compatibility land
- **Phase 3 — Q4 2026** · Institutional RWA risk coverage + Casper Accelerate grant; `RWAAgent` becomes a full on-chain module with regulator-readable audit trails
- **Phase 4 — 2027** · Cross-chain risk oracle; `RiskPolicyManager` governance via CSPR token votes

`RiskOracle` is a public contract — every Casper protocol that reads it inherits VaultWatch's risk intelligence with no integration overhead. Network effects are built into the contract architecture.

---

## Links

| Resource | URL |
|----------|-----|
| Repository | https://github.com/sodiq-code/vaultwatch |
| Demo Video | https://youtu.be/Jmg_MFSxwdE |
| Live Dashboard | https://dashboard-rho-amber-89.vercel.app |
| Python SDK (PyPI) | https://pypi.org/project/casper-sentinel/4.0.0/ |
| MCP Package (npm) | https://www.npmjs.com/package/casper-sentinel-mcp |
| Deployer Account | https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7 |
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

**Author: [Sodiq Jimoh](https://github.com/sodiq-code) · Network: Casper Testnet (`casper-test`) · License: MIT**
