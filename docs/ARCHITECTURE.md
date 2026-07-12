# VaultWatch Architecture

## Overview

VaultWatch is a multi-layer DeFi risk intelligence platform. It processes real-time Casper blockchain events through a cascade of AI agents, records audit trails on-chain, and exposes all capabilities via REST API, FastMCP tools, and a Python SDK.

---

## Layer 1 — Data Ingestion

### cspr.cloud REST API + Casper Sidecar SSE
- `cspr.cloud` REST API for live block data, account deploys, and network status
- `SidecarClient` connects to Casper SSE endpoint for streaming events
- CoinGecko API for live CSPR/USD price data

---

## Layer 2 — AI Agent Pipeline

Seven specialised agents run over async queues:

### ScannerAgent
- **Model**: `llama-3.1-8b-instant` (~560 t/s)
- **Input**: Protocol name, contract address, chain identifier
- **Output**: Risk level (LOW/MEDIUM/HIGH/CRITICAL), vulnerability list, summary

### AnomalyAgent
- **Model**: `llama-3.3-70b-versatile`
- **Input**: Protocol metrics (TVL, volume, price change, liquidity ratio, tx count)
- **Output**: `AnomalyResult` with risk score 0–100, anomaly labels, recommendation

### SelfCorrectionAgent
- **Model**: `llama-3.3-70b-versatile`
- **Input**: `AnomalyResult` with low confidence
- **Output**: Corrected score, confidence, reasoning, action (alert/escalate/none)
- **Logic**: Low-confidence responses trigger retry with expanded context (max 2 retries)

### RWAAgent
- **Model**: `llama-3.3-70b-versatile`
- **Input**: Asset data (type, issuer, collateral ratio, maturity, credit rating)
- **Output**: Verdict (APPROVED/REJECTED/REVIEW), risk score, notes

### SafetyGuard
- **Model**: `llama-prompt-guard-2-86m`
- **Input**: Any user query before processing
- **Output**: `{"safe": bool, "reason": str}`
- **Blocks**: Prompt injection, malicious intent, exploit requests (<50ms inline)

### AuditAgent
- **Model**: `llama-3.1-8b-instant`
- **Input**: Risk finding data
- **Output**: Casper deploy TX → writes to AuditTrail contract on testnet

### IntelAgent
- **Model**: `llama-3.1-8b-instant`
- **Input**: Free-form risk queries, block events, scanner alerts
- **Output**: Structured findings with summary, risk factors, confidence
- **Storage**: Appends to module-level `_findings_store` (shared with API + MCP)

---

## Layer 3 — Smart Contracts (Odra / Casper)

All 8 contracts compiled to WASM (bulk-memory-safe) and deployed to Casper testnet:

| Contract | Purpose | Key Entry Points |
|----------|---------|-----------------|
| `AuditTrail` | Immutable action log | `record_action`, `get_log` |
| `RiskOracle` | On-chain risk scores | `update_risk_score`, `get_score` |
| `SentinelCredit` | Credit ledger for pay-per-query | `mint`, `burn`, `transfer` |
| `SentinelRegistry` | Operator registration | `register_sentinel`, `deactivate_sentinel` |
| `SentinelAlertLog` | Alert event store | `log_alert`, `get_alerts` |
| `AgentBehaviorIndex` | Agent performance tracking | `record_behavior`, `get_index` |
| `RiskPolicyManager` | Configurable risk policies | `update_policy`, `get_policy` |
| `SubscriberVault` | Subscription & payment escrow | `subscribe`, `unsubscribe`, `collect_fees` |

### x402 Pay-Per-Query
The `SubscriberVault` contract enables pay-per-query billing via the official
`@make-software/casper-x402` SDK. Callers deposit CSPR; the vault deducts
per-request fees with cryptographic payment verification.

---

## Layer 4 — API & MCP

### FastAPI REST API (`api/main.py`)
- OTel middleware on every request
- All agents exposed as HTTP endpoints
- OpenAPI docs at http://localhost:8000/docs

### FastMCP Server (`vaultwatch_mcp/server.py`)
20 tools exposed for AI agent integration:
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
16. `agent_attestation` — Attest agent decisions on-chain
17. `reputation_query` — Hybrid reputation score (Brier + escrow)
18. `x402_subscribe` — x402 pay-per-query subscription
19. `policy_hotswap` — Hot-swap risk policy thresholds
20. `behavior_index_lookup` — Query agent performance index

---

## Layer 5 — Observability

Every function is instrumented with OpenTelemetry:
- Tracer names follow `vaultwatch.<module>` convention
- Span attributes: protocol, risk_score, deploy_hash, model, etc.
- OTLP exporter configurable for production (Jaeger, Grafana Tempo, etc.)

---

## Data Flow

```
Casper Node + cspr.cloud + CoinGecko
    │
    ▼
SidecarClient / REST clients
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
2. **Prompt Guard**: llama-prompt-guard-2-86m blocks injection attempts
3. **Contract auth**: All write entry points require operator key authentication
4. **Mock mode**: `CASPER_MOCK=true` runs without a live node (safe for CI)
5. **Non-root Docker**: Container runs as `vaultwatch` user (uid 1000)
6. **Self-correction gate**: Low-confidence findings discarded before reaching chain

---

## Scaling

- **Horizontal**: Multiple API instances behind a load balancer; pipeline instances process independent event streams
- **Queue backpressure**: All asyncio queues have `maxsize=256`; overflow is logged and dropped gracefully
- **Agent concurrency**: Each agent is stateless; multiple pipeline workers can run in parallel
