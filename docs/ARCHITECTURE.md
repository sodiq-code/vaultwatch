# VaultWatch Architecture — Elite v4

## Overview

VaultWatch is a multi-layer DeFi risk intelligence platform. It processes real-time Casper blockchain events through a cascade of AI agents, records audit trails on-chain, and exposes all capabilities via REST API, FastMCP tools, and a Python SDK.

---

## Layer 1 — Data Ingestion

### Casper Sidecar SSE
The `SidecarClient` connects to the Casper node's SSE endpoint (`/events/main`) and streams:
- `DeployProcessed` — smart contract interactions
- `BlockAdded` — new blocks
- `Step` — era transitions
- `Transfer` — CSPR transfers

Events are decoded from JSON and distributed to agent queues via the pipeline fan-out.

---

## Layer 2 — AI Agent Pipeline

Six specialised agents run concurrently over async queues:

### ScannerAgent
- **Model**: `llama-3.3-70b-versatile`
- **Input**: Protocol name, contract address, chain identifier
- **Output**: Risk level (LOW/MEDIUM/HIGH/CRITICAL), vulnerability list, summary
- **Trigger**: Every `DeployProcessed` event

### AnomalyAgent
- **Model**: `llama-3.3-70b-versatile`
- **Input**: Protocol metrics (TVL, volume, price change, liquidity ratio, tx count)
- **Output**: `AnomalyResult` with risk score 0–100, anomaly labels, recommendation
- **Trigger**: Every `DeployProcessed` event

### SelfCorrectionAgent
- **Model**: `llama-3.1-8b-instant`
- **Input**: `AnomalyResult` with risk score ≥ 70
- **Output**: Corrected score, confidence, reasoning, action (alert/escalate/none)
- **Logic**: Low-confidence responses trigger a retry with additional context

### RWAAgent
- **Model**: `llama-3.1-8b-instant`
- **Input**: Asset data (type, issuer, collateral ratio, maturity, credit rating)
- **Output**: Verdict (APPROVED/REJECTED/REVIEW), risk score, notes
- **Trigger**: `Step` and `Transfer` events

### IntelAgent
- **Model**: `compound-beta` (Groq Compound — tool-augmented reasoning)
- **Input**: Free-form risk queries, block events, scanner alerts
- **Output**: Structured findings with summary, risk factors, confidence
- **Storage**: Appends to module-level `_findings_store` (shared with API + MCP)

### SafetyGuard
- **Model**: `llama-prompt-guard-2-86m`
- **Input**: Any user query before processing
- **Output**: `{"safe": bool, "reason": str}`
- **Blocks**: Prompt injection, malicious intent, exploit requests

---

## Layer 3 — Smart Contracts (Odra / Casper)

All contracts compiled to WASM and deployed to Casper testnet:

| Contract | Purpose | Key Entry Points |
|----------|---------|-----------------|
| `AuditTrail` | Immutable action log | `record_action`, `get_log` |
| `RiskOracle` | On-chain risk scores | `update_risk_score`, `get_score` |
| `SentinelCredit` | ERC-20-like credit token | `mint`, `burn`, `transfer` |
| `SentinelRegistry` | Operator registration | `register_sentinel`, `deactivate_sentinel` |
| `SentinelAlertLog` | Alert event store | `log_alert`, `get_alerts` |
| `AgentBehaviorIndex` | Agent performance tracking | `record_behavior`, `get_index` |
| `RiskPolicyManager` | Configurable risk policies | `update_policy`, `get_policy` |
| `SubscriberVault` | Subscription & payment | `subscribe`, `unsubscribe`, `collect_fees` |

### x402 Pay-Per-Query
The `SubscriberVault` contract enables pay-per-query billing. Callers deposit CSPR; the vault deducts per-request fees and allows operators to collect earnings.

---

## Layer 4 — API & MCP

### FastAPI REST API (`api/main.py`)
- OTel middleware on every request
- All agents exposed as HTTP endpoints
- Routes: `/risk/query`, `/anomaly/detect`, `/rwa/assess`, `/scanner/scan`, `/policy/update`, `/audit/log`, `/chain/block`

### FastMCP Server (`mcp/server.py`)
15 tools exposed for AI agent integration:
1. `query_risk` — IntelAgent queries
2. `detect_anomaly` — AnomalyAgent
3. `scan_protocol` — ScannerAgent
4. `assess_rwa` — RWAAgent
5. `get_audit_log` — AuditAgent read
6. `write_audit_entry` — AuditAgent write
7. `get_block_height` — Chain connectivity
8. `list_policies` — Policy read
9. `update_policy` — Policy write
10. `check_safety` — SafetyGuard
11. `get_findings` — IntelAgent store
12. `get_risk_score` — RiskOracle query
13. `list_rwa_assets` — RWA assets
14. `get_agent_spans` — OTel spans
15. `get_health` — System health

---

## Layer 5 — Observability

Every function is instrumented with OpenTelemetry:
- Tracer names follow `vaultwatch.<module>` convention
- Span attributes: protocol, risk_score, deploy_hash, model, etc.
- In-memory exporter available via `/metrics/spans`
- OTLP exporter configurable for production (Jaeger, Grafana Tempo, etc.)

---

## Data Flow Diagram

```
Casper Node
    │
    ▼ SSE /events/main
SidecarClient
    │
    ├──► scanner_q ──► ScannerAgent ──► [high risk] ──► intel_q
    │
    ├──► anomaly_q ──► AnomalyAgent ──► [score≥70] ──► correction_q ──► SelfCorrectionAgent
    │                                                ──► audit_q
    │
    ├──► rwa_q ──────► RWAAgent
    │
    ├──► intel_q ────► IntelAgent ──► _findings_store
    │
    └──► audit_q ────► AuditAgent ──► Casper (AuditTrail contract)
```

---

## Security Model

1. **Input validation**: SafetyGuard screens every user-facing query
2. **Prompt Guard**: Llama-prompt-guard-2-86m blocks injection attempts
3. **Contract auth**: All write entry points require operator key authentication
4. **Mock mode**: `CASPER_MOCK=true` runs without a live node (safe for CI)
5. **Non-root Docker**: Container runs as `vaultwatch` user (uid 1000)

---

## Scaling

- **Horizontal**: Multiple API instances behind a load balancer; pipeline instances process independent event streams
- **Queue backpressure**: All asyncio queues have `maxsize=256`; overflow is logged and dropped gracefully
- **Agent concurrency**: Each agent is stateless; multiple pipeline workers can run in parallel

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | — | Groq API key (required) |
| `CASPER_NODE_URL` | `http://localhost:7777` | Casper node REST |
| `CASPER_CHAIN_NAME` | `casper-test` | Network identifier |
| `CASPER_MOCK` | `true` | Mock mode (no live node) |
| `CASPER_SIDECAR_URL` | `http://localhost:9999/events/main` | SSE endpoint |
| `CASPER_SIGNING_KEY_PATH` | — | Operator key PEM path |
| `AUDIT_TRAIL_HASH` | — | AuditTrail contract hash |
| `RISK_ORACLE_HASH` | — | RiskOracle contract hash |
| `RISK_POLICY_MANAGER_HASH` | — | RiskPolicyManager contract hash |
