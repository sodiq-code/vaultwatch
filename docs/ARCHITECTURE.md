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
| `AuditTrail` | Immutable action log | `record_finding`, `get_finding`, `finding_count`, `transfer_ownership` |
| `RiskOracle` | On-chain risk scores | `update_score`, `get_risk_score`, `is_high_risk`, `transfer_ownership` |
| `SentinelCredit` | Credit ledger for pay-per-query | `deposit`, `deduct_credit`, `withdraw`, `get_balance`, `get_query_price`, `get_premium_price`, `total_revenue` |
| `SentinelRegistry` | Operator registration | `register`, `deregister`, `increment_alert_count`, `get_subscriber`, `is_active`, `get_count`, `transfer_ownership` |
| `SentinelAlertLog` | Alert event store | `log_alert`, `get_address_logs`, `get_log`, `log_count` |
| `AgentBehaviorIndex` | Agent performance tracking | `record_decision`, `get_metrics`, `get_trust_score`, `get_agent_count` |
| `RiskPolicyManager` | Configurable risk policies | `update_policy`, `upgrade_to_v2_rwa`, `grant_operator`, `grant_admin`, `revoke_operator`, `get_current_policy`, `get_policy_version` |
| `SubscriberVault` | Subscription & payment escrow | `open_vault`, `deduct`, `top_up`, `get_account`, `get_balance`, `get_total_locked` |

### Entry Point Details

#### AuditTrail (`contracts/src/audit_trail.rs`)
| Entry Point | Access | Description |
|-------------|--------|-------------|
| `init()` | — | Sets caller as owner, initializes finding count |
| `record_finding(address, risk_type, severity, confidence, description)` | Owner | Writes a new immutable finding, returns finding ID |
| `get_finding(id)` | Public | Returns a finding by ID |
| `finding_count()` | Public | Returns total number of findings |
| `transfer_ownership(new_owner)` | Owner | Transfers contract ownership |

#### RiskOracle (`contracts/src/risk_oracle.rs`)
| Entry Point | Access | Description |
|-------------|--------|-------------|
| `init()` | — | Sets caller as owner |
| `update_score(address, score, risk_type, confidence, block_height, finding_id)` | Owner | Updates risk score for an address |
| `get_risk_score(address)` | Public | Queries risk score for any address |
| `is_high_risk(address, threshold)` | Public | Checks if address exceeds risk threshold |
| `transfer_ownership(new_owner)` | Owner | Transfers contract ownership |

#### SentinelCredit (`contracts/src/sentinel_credit.rs`)
| Entry Point | Access | Description |
|-------------|--------|-------------|
| `init(query_price, premium_price)` | — | Sets prices and owner |
| `deposit(account_address)` | Payable | Deposits CSPR via `attached_value()` into credit balance |
| `deduct_credit(account_address, query_type)` | Owner | Deducts query price from account balance |
| `withdraw(amount, to)` | Owner | Withdraws collected revenue to a recipient |
| `get_balance(account_address)` | Public | Returns account balance |
| `get_query_price()` | Public | Returns current standard query price |
| `get_premium_price()` | Public | Returns current premium query price |
| `total_revenue()` | Public | Returns total collected revenue |

#### SentinelRegistry (`contracts/src/sentinel_registry.rs`)
| Entry Point | Access | Description |
|-------------|--------|-------------|
| `init()` | — | Sets caller as owner |
| `register(address, webhook_url, min_severity, timestamp)` | Public | Registers a new subscriber |
| `deregister(address)` | Public | Deactivates a subscriber |
| `increment_alert_count(address)` | Owner | Increments alert count after push |
| `get_subscriber(address)` | Public | Returns subscriber details |
| `is_active(address)` | Public | Checks if subscriber is active |
| `get_count()` | Public | Returns total subscriber count |
| `transfer_ownership(new_owner)` | Owner | Transfers contract ownership |

#### SentinelAlertLog (`contracts/src/sentinel_alert_log.rs`)
| Entry Point | Access | Description |
|-------------|--------|-------------|
| `init()` | — | Sets caller as owner |
| `log_alert(subscriber_address, finding_id, severity, risk_type, block_height, timestamp, delivered)` | Owner | Logs a delivered alert, returns log ID |
| `get_address_logs(subscriber_address)` | Public | Returns log IDs for a subscriber (max 256) |
| `get_log(log_id)` | Public | Returns a specific log record |
| `log_count()` | Public | Returns total number of logs |

#### AgentBehaviorIndex (`contracts/src/agent_behavior_index.rs`)
| Entry Point | Access | Description |
|-------------|--------|-------------|
| `init()` | — | Sets caller as owner |
| `record_decision(agent_name, confidence, correction_applied, safety_rejected, block_height)` | Owner | Records a decision outcome for an agent |
| `get_metrics(agent_name)` | Public | Returns full agent metrics |
| `get_trust_score(agent_name)` | Public | Returns agent trust score (0–100) |
| `get_agent_count()` | Public | Returns total number of tracked agents |

#### RiskPolicyManager (`contracts/src/risk_policy_manager.rs`)
| Entry Point | Access | Description |
|-------------|--------|-------------|
| `init()` | — | Sets caller as owner/admin/operator, creates default policy v1 |
| `update_policy(min_confidence, critical_score, high_score, medium_score, max_retry, safety_rejection)` | Operator | Updates risk policy, increments version |
| `upgrade_to_v2_rwa(rwa_confidence_boost, rwa_critical_threshold)` | Admin | V2 upgrade: adds RWA-specific thresholds (demonstrates Casper's native contract upgrade) |
| `grant_operator(account)` | Admin | Grants OPERATOR role to an account |
| `grant_admin(account)` | Owner | Grants ADMIN role to an account |
| `revoke_operator(account)` | Admin | Revokes OPERATOR role from an account |
| `get_current_policy()` | Public | Returns the currently active policy |
| `get_policy_version(version)` | Public | Returns a historical policy by version |

#### SubscriberVault (`contracts/src/subscriber_vault.rs`)
| Entry Point | Access | Description |
|-------------|--------|-------------|
| `init()` | — | Sets caller as vault owner |
| `open_vault(subscriber_address, initial_deposit, lock_blocks, auto_renew, monthly_spend_limit, current_block)` | Owner | Opens a new vault account with escrow deposit |
| `deduct(subscriber_address, amount)` | Owner | Deducts from vault for a query (respects spend limit) |
| `top_up(subscriber_address, amount)` | Owner | Tops up vault balance |
| `get_account(subscriber_address)` | Public | Returns full vault account details |
| `get_balance(subscriber_address)` | Public | Returns escrowed balance |
| `get_total_locked()` | Public | Returns total locked CSPR across all vaults |

### V2 Upgrade Path — RiskPolicyManager

RiskPolicyManager demonstrates Casper's native upgradable contract pattern via the `upgrade_to_v2_rwa` entry point:

1. Deploy a new contract version with updated WASM
2. Call `upgrade_to_v2_rwa(rwa_confidence_boost, rwa_critical_threshold)` to migrate state
3. The entry point creates a new policy version with RWA-specific adjustments:
   - `min_confidence_threshold += rwa_confidence_boost` — stricter confidence for RWA
   - `critical_score_threshold = rwa_critical_threshold` — dedicated RWA threshold
4. Emits `PolicyUpgraded` event with version transition
5. All agents immediately reclassify at new thresholds

**RBAC Controls** (`contracts/src/risk_policy_manager.rs`):
- **OWNER**: Can `grant_admin`, transfer ownership
- **ADMIN**: Can `grant_operator`, `revoke_operator`, `upgrade_to_v2_rwa`
- **OPERATOR**: Can `update_policy`
- Owner is automatically both admin and operator at `init()`

### Contract Events

Each contract emits typed Odra events for off-chain indexing:

| Contract | Event | Fields | Trigger |
|----------|-------|--------|---------|
| `AuditTrail` | `FindingRecorded` | `finding_id`, `address`, `risk_type`, `severity`, `confidence`, `block_height` | `record_finding()` |
| `AuditTrail` | `OwnerChanged` | `old_owner`, `new_owner` | `transfer_ownership()` |
| `SentinelCredit` | `CreditDeposited` | `account`, `amount_motes`, `new_balance` | `deposit()` |
| `SentinelCredit` | `CreditDeducted` | `account`, `amount_motes`, `remaining_balance`, `query_type` | `deduct_credit()` |
| `SentinelCredit` | `RevenueWithdrawn` | `to`, `amount_motes` | `withdraw()` |
| `SentinelAlertLog` | `AlertLogged` | `log_id`, `subscriber_address`, `finding_id`, `severity`, `block_height` | `log_alert()` |
| `RiskPolicyManager` | `PolicyUpgraded` | `old_version`, `new_version`, `upgraded_by`, `block_height` | `update_policy()`, `upgrade_to_v2_rwa()` |
| `RiskPolicyManager` | `RoleGranted` | `role`, `account`, `granted_by` | `grant_operator()`, `grant_admin()` |

### x402 Pay-Per-Query
The `SubscriberVault` contract enables pay-per-query billing via the official
`@make-software/casper-x402` SDK. Callers deposit CSPR via `open_vault()`;
the vault `deduct()`s per-request fees with cryptographic payment verification.

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

### RWA MCP Server (`vaultwatch_rwa_mcp/server.py`)
8 tools exposed for RWA-specific intelligence:
1. `rwa_collateral_health` — Live collateral ratio for RWA-backed assets
2. `rwa_depeg_risk` — Stablecoin depeg probability and distance
3. `rwa_yield_analysis` — RWA yield vs DeFi yield comparison
4. `rwa_attestation_verify` — Verify on-chain RWA attestation
5. `rwa_portfolio_scan` — Full RWA portfolio risk scan
6. `rwa_compliance_check` — KYC/AML compliance flag check
7. `rwa_oracle_feed` — Live RWA price oracle data
8. `rwa_casper_registry` — List all registered RWA assets on Casper

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
3. **Contract auth**: All write entry points require owner/operator key authentication
4. **RBAC**: RiskPolicyManager enforces OWNER → ADMIN → OPERATOR hierarchy (`contracts/src/risk_policy_manager.rs`)
5. **Mock mode**: `CASPER_MOCK=true` runs without a live node (safe for CI)
6. **Non-root Docker**: Container runs as `vaultwatch` user (uid 1000)
7. **Self-correction gate**: Low-confidence findings discarded before reaching chain

---

## Scaling

- **Horizontal**: Multiple API instances behind a load balancer; pipeline instances process independent event streams
- **Queue backpressure**: All asyncio queues have `maxsize=256`; overflow is logged and dropped gracefully
- **Agent concurrency**: Each agent is stateless; multiple pipeline workers can run in parallel
