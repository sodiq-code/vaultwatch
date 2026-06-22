# ⬡ VaultWatch

**DeFi Risk Intelligence on Casper — Elite Architecture v4**

VaultWatch is an AI-powered DeFi risk monitoring platform built on the Casper blockchain. It combines 6 Groq AI agents, 8 Odra smart contracts, a FastMCP tool server, real-time Casper Sidecar SSE streaming, and a React dashboard into a unified risk intelligence system.

[![CI](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![Casper Testnet](https://img.shields.io/badge/network-casper--test-orange.svg)](https://testnet.cspr.live/)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         VaultWatch v4                               │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    6 Groq AI Agents                         │   │
│  │                                                             │   │
│  │  ScannerAgent    ──►  AnomalyAgent  ──►  SelfCorrection    │   │
│  │  (llama-3.3-70b)      (llama-3.3-70b)    (llama-3.1-8b)   │   │
│  │                                                             │   │
│  │  RWAAgent        ──►  IntelAgent    ──►  SafetyGuard       │   │
│  │  (llama-3.1-8b)       (compound-β)       (prompt-guard)    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│           │                    │                    │               │
│           ▼                    ▼                    ▼               │
│  ┌─────────────┐    ┌──────────────────┐   ┌───────────────┐      │
│  │  AuditAgent │    │  FastAPI REST API │   │  FastMCP      │      │
│  │  (on-chain) │    │  /risk /anomaly   │   │  15 tools     │      │
│  └─────────────┘    │  /rwa /audit      │   └───────────────┘      │
│           │         │  /policy /chain   │                           │
│           ▼         └──────────────────┘                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  8 Odra Smart Contracts                     │   │
│  │                                                             │   │
│  │  AuditTrail  RiskOracle  SentinelCredit  SentinelRegistry  │   │
│  │  AlertLog    BehaviorIdx RiskPolicyMgr   SubscriberVault   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│           │                                                         │
│           ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              Casper Sidecar SSE Streaming                   │   │
│  │         Real-time Deploy / Block / Transfer events          │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Features

| Feature | Detail |
|---------|--------|
| **6 AI Agents** | Scanner, Anomaly, SelfCorrection, RWA, Intel, SafetyGuard |
| **Groq Models** | `compound-beta`, `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`, `llama-prompt-guard-2-86m` |
| **8 Contracts** | AuditTrail, RiskOracle, SentinelCredit, SentinelRegistry, SentinelAlertLog, AgentBehaviorIndex, RiskPolicyManager, SubscriberVault |
| **15 MCP Tools** | Full FastMCP server for AI agent integration |
| **REST API** | FastAPI with OTel middleware, all agents exposed as endpoints |
| **SDK** | `pip install vaultwatch` — async Python client |
| **Dashboard** | React/Vite real-time UI |
| **Streaming** | Casper Sidecar SSE event fan-out pipeline |
| **Observability** | OTel spans on every agent call and API route |
| **Docker** | Single `docker-compose up` to run everything |

---

## Quickstart

### 1. Clone & install

```bash
git clone https://github.com/sodiq-code/vaultwatch
cd vaultwatch
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env — set GROQ_API_KEY at minimum
```

### 3. Run the API

```bash
python -m uvicorn api.main:app --reload --port 8000
# Docs at http://localhost:8000/docs
```

### 4. Run the pipeline

```bash
python pipeline.py
```

### 5. Run the MCP server

```bash
python vaultwatch_mcp/server.py
```

### 6. Run the dashboard

```bash
cd dashboard && npm install && npm run dev
# Open http://localhost:5173
```

### 7. Docker (all-in-one)

```bash
docker-compose up
```

---

## Demo Scripts

```bash
# Risk intelligence demo
python scripts/demo_risk.py

# RWA assessment demo
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

## Tests

```bash
# All tests
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# Demo scenarios
pytest tests/demo/ -v -s

# With coverage
pytest tests/ --cov=. --cov-report=html
```

---

## Contract Deployment

```bash
# Mock mode (no live node required)
python scripts/deploy_contracts.py --mock

# Live testnet
python scripts/deploy_contracts.py --output deploy_hashes.json
```

---

## Testnet Transactions

| Contract | Deploy Hash |
|----------|-------------|
| AuditTrail | `pending testnet deployment` |
| RiskOracle | `pending testnet deployment` |
| SentinelCredit | `pending testnet deployment` |
| SentinelRegistry | `pending testnet deployment` |
| SentinelAlertLog | `pending testnet deployment` |
| AgentBehaviorIndex | `pending testnet deployment` |
| RiskPolicyManager | `pending testnet deployment` |
| SubscriberVault | `pending testnet deployment` |

---

## SDK Usage

```bash
pip install vaultwatch
```

```python
import asyncio
from vaultwatch import VaultWatchClient

async def main():
    async with VaultWatchClient("http://localhost:8000") as client:
        # Query risk
        result = await client.query_risk(
            "What are the main risks for Uniswap v3?",
            protocol="Uniswap"
        )
        print(result)

        # Detect anomaly
        anomaly = await client.detect_anomaly(
            protocol="CasperSwap",
            tvl=12_000_000,
            volume_24h=18_000_000,
            price_change_1h=-22.0,
            num_transactions=4000,
            liquidity_ratio=0.04,
        )
        print(f"Risk score: {anomaly['risk_score']}")

        # Assess RWA
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

## Project Structure

```
vaultwatch/
├── agents/                  # 6 AI agents
│   ├── scanner_agent.py
│   ├── anomaly_agent.py
│   ├── self_correction_agent.py
│   ├── rwa_agent.py
│   ├── intel_agent.py
│   ├── safety_guard.py
│   └── audit_agent.py
├── contracts/               # 8 Odra smart contracts
│   ├── Cargo.toml
│   └── src/
│       ├── audit_trail.rs
│       ├── risk_oracle.rs
│       ├── sentinel_credit.rs
│       ├── sentinel_registry.rs
│       ├── sentinel_alert_log.rs
│       ├── agent_behavior_index.rs
│       ├── risk_policy_manager.rs
│       └── subscriber_vault.rs
├── streaming/
│   └── sidecar_client.py    # Casper Sidecar SSE client
├── mcp/
│   └── server.py            # FastMCP — 15 tools
├── api/
│   └── main.py              # FastAPI REST API
├── sdk/
│   └── vaultwatch/          # Python SDK (pip install vaultwatch)
│       ├── __init__.py
│       └── client.py
├── tests/
│   ├── unit/                # 8 unit test files
│   ├── integration/         # 5 integration test files
│   └── demo/                # demo scenario tests
├── scripts/
│   ├── deploy_contracts.py
│   ├── demo_risk.py
│   ├── demo_rwa.py
│   ├── demo_upgrade_policy.py
│   └── record_demo.py
├── dashboard/               # React/Vite UI
├── casper_client.py         # Casper SDK wrapper
├── pipeline.py              # Async orchestration pipeline
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

---

## License

MIT © VaultWatch
