# VaultWatch Architecture

## Overview

VaultWatch is a multi-layer DeFi risk intelligence platform. It processes real-time Casper blockchain events through a cascade of AI agents, records audit trails on-chain, and exposes all capabilities via REST API, FastMCP tools, and a Python SDK.

---

## Layer 1 — Data Ingestion

### cspr.cloud REST API + Casper Sidecar SSE
- `cspr.cloud` REST API for live block data, account deploys, and network status
- `SidecarClient` connects to Casper SSE endpoint for streaming events
- CoinGecko API for live CSPR/USD price data
- FRED (Federal Reserve Economic Data) for macroeconomic indicators (bond yields, credit spreads)

---

## Layer 2 — AI Agent Pipeline

Seven specialised agents run over async queues. All AI calls go through the
`MultiProviderClient` (see **Multi-Provider AI Resilience** below), which tries
Groq → OpenRouter → heuristic fallback.

### ScannerAgent
- **Model**: `llama-3.3-70b-versatile` (replaces deprecated `llama-3.1-8b-instant`)
- **Input**: Protocol name, contract address, chain identifier
- **Output**: Risk level (LOW/MEDIUM/HIGH/CRITICAL), vulnerability list, summary
- **Sources**: CSPR.cloud REST API + Casper Sidecar SSE

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
- **Model**: `llama-3.3-70b-versatile` (replaces deprecated `compound-beta`)
- **Input**: Asset data (type, issuer, collateral ratio, maturity, credit rating)
- **Output**: Verdict (APPROVED/REJECTED/REVIEW), risk score, notes
- **Hybrid Feed Approach**: Fetches real data from CoinGecko (commodities/tokenized assets)
  and FRED (bonds/credit) via the `/rwa/feed` API endpoint, then enriches with Groq AI
  intelligence. `EnrichedFinding` tracks `feed_source` and `x402_payment_id`.

### SafetyGuard
- **Model**: `llama-3.3-70b-versatile` (JSON-mode safety classifier — replaces deprecated `llama-prompt-guard-2-86m`)
- **Input**: Any user query or agent finding before on-chain write
- **Output**: `{"safety_score": float, "safe": bool, "reason": str}` — 0.0–1.0 safety score classification via JSON-mode prompt
- **Position**: Between RWAAgent and AuditAgent — **nothing writes to chain without passing here**
- **Fail-closed policy**: When AI providers are unavailable (missing `GROQ_API_KEY`, auth errors,
  model 404s, network failures), SafetyGuard **rejects ALL findings** rather than silently
  approving them. The rejection threshold is configurable via `RiskPolicyManager` (default 0.80).
  This ensures no unsafe content ever reaches the Casper blockchain.

### AuditAgent
- **Model**: `llama-3.3-70b-versatile` (replaces deprecated `llama-3.1-8b-instant`)
- **Input**: Approved enriched finding from SafetyGuard
- **Output**: Casper deploy TX → writes to AuditTrail, RiskOracle, SentinelAlertLog, AgentBehaviorIndex contracts on testnet
- **Attestations**: Posts EAS-style RWA attestations (schemaId, attester, recipient, dataHash, dataEncoded) to AuditTrail

### IntelAgent
- **Model**: `llama-3.3-70b-versatile` (replaces deprecated `llama-3.1-8b-instant`)
- **Input**: Free-form risk queries, block events, scanner alerts, confirmed on-chain records
- **Output**: Structured findings with summary, risk factors, confidence
- **Storage**: Appends to module-level `_findings_store` (shared with API + MCP)
- **x402 Gate**: Micropayment gate for pay-per-query access to findings

---

## Multi-Provider AI Resilience

All AI-dependent agents use `agents/ai_providers.py` → `MultiProviderClient`, a
3-tier resilience architecture that ensures agents always produce meaningful output:

| Tier | Provider | Role | Fallback Behavior |
|------|----------|------|-------------------|
| 1 | **Groq** (primary) | Fast, low-latency inference | Falls to tier 2 on auth errors (401/403), rate limits (429), or network failures |
| 2 | **OpenRouter** (secondary) | Broad model catalog, free tier available | Auto-maps Groq model names to OpenRouter equivalents (e.g. `llama-3.3-70b-versatile` → `meta-llama/llama-3.3-70b-instruct:free`) |
| 3 | **Heuristic fallback** (tertiary) | No external API — rule-based analysis | Each agent owns its own heuristic logic; `MultiProviderClient.chat_completion()` returns `None`, triggering the agent-specific fallback |

Key features:
- Model name mapping: `GROQ_TO_OPENROUTER` dict maps deprecated Groq models to free-tier OpenRouter equivalents
- Environment variables: `GROQ_API_KEY` (primary), `OPENROUTER_API_KEY` (secondary, free at openrouter.ai), `OPENROUTER_MODEL` (override)
- Uniform response format: All providers return `MockChatCompletion` with `.choices[0].message.content` pattern
- JSON convenience: `chat_completion_json()` parses response as JSON dict, returns `None` on failure

---

## Layer 3 — Smart Contracts (Odra / Casper)

All 8 contracts compiled to WASM (bulk-memory-safe) and deployed to Casper testnet:

| Contract | Purpose | Key Entry Points |
|----------|---------|-----------------|
| `AuditTrail` | Immutable finding log + EAS attestations | `record_finding`, `get_finding`, `get_count` |
| `RiskOracle` | On-chain risk scores | `update_score`, `get_risk_score`, `is_high_risk` |
| `SentinelCredit` | Credit ledger for pay-per-query | `deposit` (payable), `withdraw`, `deduct_query`, `get_balance`, `get_contract_balance` |
| `SentinelRegistry` | Operator registration | `register`, `deregister`, `is_active` |
| `SentinelAlertLog` | Alert event store | `log_alert`, `get_log`, `get_total_count` |
| `AgentBehaviorIndex` | Agent performance tracking | `record_decision`, `get_metrics`, `get_trust_score` |
| `RiskPolicyManager` | Configurable risk policies | `upgrade_policy`, `get_current_policy`, `get_policy_version` |
| `SubscriberVault` | Subscription & payment escrow | `open_vault` (payable), `top_up` (payable), `withdraw`, `deduct`, `get_balance`, `get_contract_balance` |

### Payable Contracts

`SentinelCredit.deposit` and `SubscriberVault.open_vault` / `top_up` are marked
`#[odra(payable)]` — the caller attaches real CSPR via `CallDef::with_amount()`.
Odra's `handle_attached_value()` transfers the CSPR from the caller's cargo purse
into the contract's `__contract_main_purse`. The `amount` argument must match the
attached value (the contract verifies this). Both contracts also expose
`withdraw()` (transfers real CSPR back to the caller via `transfer_tokens()`,
respecting the vault's lock period) and `get_contract_balance()` (reads the
main purse balance via `self.env().self_balance()`).

All payable flows are signed via the **CSPR.click AgentWallet** integration
(see below), which replaces the previous manual `secret_key.pem` management.

### x402 Pay-Per-Query (Dual-Path)

VaultWatch implements a **dual-path x402 payment architecture** — the first Casper
project to support both payment verification paths defined by the x402 v2
specification. See `docs/X402_DUAL_PATH_ARCHITECTURE.md` for full details.

| Path | Token | Verification | Settlement |
|------|-------|--------------|------------|
| **Path A — Self-Hosted / Native CSPR** | CSPR via SubscriberVault escrow | Local `ExactCasperScheme.verify()` + EIP-712 signatures | Direct on-chain deploy (`open_vault`) |
| **Path B — CSPR.cloud Facilitator / WCSPR** | WCSPR (CEP-18 wrapped CSPR) | CSPR.cloud `/verify` + `transfer_with_authorization` | CSPR.cloud `/settle` facilitator |

The `SubscriberVault` contract enables pay-per-query billing via the official
`@make-software/casper-x402` SDK. Callers deposit CSPR; the vault deducts
per-request fees with cryptographic payment verification.

---

## Dual-Path x402 Payment Architecture

VaultWatch is the **first Casper project** implementing both x402 v2 payment paths,
maximizing eligibility for the $100K x402 ecosystem credits in the DoraHacks
Casper Agentic Buildathon.

### Path A — Self-Hosted / Native CSPR

- **Token**: Native CSPR deposited into `SubscriberVault` escrow
- **Verification**: Local `ExactCasperScheme.verify()` using Casper's native
  `verify_signature()` + EIP-712-style typed-data signatures
- **Settlement**: Direct on-chain deploy via `open_vault` / `top_up` entry points
- **Use case**: Clients who prefer direct deploy, no external dependency, full
  self-hosted control

### Path B — CSPR.cloud Facilitator / WCSPR

- **Token**: WCSPR (CEP-18 wrapped CSPR, faucet-claimable on testnet)
- **Verification**: CSPR.cloud `/verify` endpoint + `transfer_with_authorization`
  CEP-18 standard flow
- **Settlement**: CSPR.cloud `/settle` facilitator endpoint
- **Use case**: Clients who prefer no signer PEM, standard CEP-18 token flow,
  or CSPR.cloud-managed infrastructure

### Resilience

If the CSPR.cloud facilitator is unavailable, Path A operates independently.
If on-chain signing is unavailable, Path B operates via the facilitator. VaultWatch
serves both, ensuring payment never blocks risk intelligence delivery.

> Full specification: `docs/X402_DUAL_PATH_ARCHITECTURE.md`

---

## CSPR.click AgentWallet Integration

VaultWatch replaces the previous manual `secret_key.pem` key management with a
**programmatic agent-wallet abstraction** built on the official CSPR.click AI
Agent Skill guidance and the Autarca reference implementation.

The integration spans both sides of the Casper wallet ecosystem:

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Server-side (headless)** | `casper-js-sdk` v5 + `PrivateKey.generate()` | Autonomous agent wallet creation + signing for pytest e2e tests, MCP server deploys, scheduled pipeline writes |
| **Browser-side (user-facing)** | CSPR.click Web SDK (CDN) | End-user wallet connection + transaction approval via Casper Wallet / WalletConnect / social-login wallets |

### Server-side: `AgentWallet`

- Python class: `agents/agent_wallet.py` → `AgentWallet`
- Node.js helper: `scripts/csprclick_agent_wallet.cjs` (create, info, public commands)
- Deploy helper: `scripts/casper_call.cjs` (sign + submit + verify)
- Key storage: `$VAULTWATCH_AGENT_KEY_PATH` (default `~/.vaultwatch/agent_key.pem`, mode 0600, gitignored)
- Key algorithm: SECP256K1 (configurable via `VAULTWATCH_AGENT_KEY_ALGO`)
- API: `ensure_exists()`, `call_contract()`, `transfer_cspr()`, `refresh_balance()`, `assert_funded()`

### Browser-side: CSPR.click Web SDK

- React context: `dashboard/src/csprclick.js` → `CSPRClickProvider`, `useClickRef()`, `useActiveAccount()`
- Wallet bar: `dashboard/src/components/WalletBar.jsx` → "Connect Wallet" button + account chip + disconnect
- CDN: `https://cdn.cspr.click/ui/v2.1.0/` (dynamically injected, no static `<script>` tag)
- All CSPR.click SDK constraints respected (see `CSPR_CLICK_AGENT_SKILL.md`)

### Backward Compatibility

Legacy `CasperContractClient(signing_key_path=...)` still works — it now accepts
an optional `agent_wallet` parameter. E2e test suite auto-discovers the key in
priority order: CLI option → env var → default agent wallet → legacy `secret_key.pem`
→ auto-create new wallet.

> Full specification: `CSPR_CLICK_AGENT_SKILL.md`

---

## Layer 4 — API & MCP

### FastAPI REST API (`api/main.py`)
- OTel middleware on every request
- All agents exposed as HTTP endpoints
- OpenAPI docs at http://localhost:8000/docs

### FastMCP Server — General (`vaultwatch_mcp/server.py`)
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

### FastMCP Server — RWA Domain (`vaultwatch_rwa_mcp/server.py`)
A domain-specific MCP server exclusively for the on-chain RWA / risk contract
layer. Unlike the general server (which mixes market data, Groq anomaly detection,
and sidecar streaming), this server focuses purely on contract reads and writes:

**39 tools** covering:
- Contract reads (free `query_global_state` JSON-RPC calls, no gas, no LLM)
- Contract writes (real deploys signed via CSPR.click AgentWallet)
- Risk policy operations
- RWA asset management
- Audit trail queries
- x402 subscription management

**3 resources** (read-only URI surfaces for LLM context injection):
1. `rwa://contracts` — Full contract registry (names, hashes, entry points)
2. `rwa://policy/current` — Live on-chain RiskPolicy
3. `rwa://audit/summary` — Recent audit findings digest

**4 prompts** (guided LLM interaction templates):
- RWA assessment workflow
- Risk policy hot-swap procedure
- Audit trail investigation
- x402 payment setup guide

Connect via: `{"mcpServers": {"vaultwatch-rwa": {"command": "python", "args": ["-m", "vaultwatch_rwa_mcp.server"]}}}`
or `npx vaultwatch-rwa-mcp`.

> Reference: `vaultwatch_rwa_mcp/server.py`

---

## Layer 5 — Observability

Every function is instrumented with OpenTelemetry:
- Tracer names follow `vaultwatch.<module>` convention
- Span attributes: protocol, risk_score, deploy_hash, model, safety_score, etc.
- OTLP exporter configurable for production (Jaeger, Grafana Tempo, etc.)

---

## Data Flow

```
Casper Node + cspr.cloud + CoinGecko + FRED
    │
    ▼
SidecarClient / REST clients
    │
    ├──► scanner_q ──► ScannerAgent ──► [high risk] ──► intel_q
    │
    ├──► anomaly_q ──► AnomalyAgent ──► [score≥70] ──► correction_q ──► SelfCorrectionAgent
    │                                                ──► audit_q
    │
    ├──► rwa_q ──────► RWAAgent (CoinGecko + FRED + Groq enrichment)
    │
    ├──► intel_q ────► IntelAgent ──► _findings_store
    │
    └──► audit_q ───► SafetyGuard ──► [approved] ──► AuditAgent ──► Casper (AuditTrail + RiskOracle + SentinelAlertLog)
                       (fail-closed     │
                        0.0-1.0 score)  └► [rejected] ──► dropped + logged

    ──► IntelAgent ──► x402 Pay-Per-Query ──► dual-path output:
                        ├── Path A: Native CSPR / SubscriberVault escrow
                        └── Path B: WCSPR (CEP-18) / CSPR.cloud facilitator
```

---

## Security Model

1. **Input validation**: SafetyGuard screens every user-facing query and agent finding before on-chain write
2. **Safety classifier**: `llama-3.3-70b-versatile` JSON-mode classifier produces 0.0–1.0 safety score; findings with score ≥ threshold (default 0.80) are rejected
3. **Fail-closed SafetyGuard**: When AI providers are unavailable (missing API key, auth errors, model 404s, network failures), SafetyGuard **rejects ALL findings** — no unsafe content ever reaches the Casper blockchain
4. **Contract auth**: All write entry points require operator key authentication via CSPR.click AgentWallet
5. **Mock mode**: `CASPER_MOCK=true` runs without a live node (safe for CI)
6. **Non-root Docker**: Container runs as `vaultwatch` user (uid 1000)
7. **Self-correction gate**: Low-confidence findings discarded before reaching chain
8. **Multi-provider resilience**: Groq → OpenRouter → heuristic fallback ensures no single AI provider failure blocks the pipeline

---

## Scaling

- **Horizontal**: Multiple API instances behind a load balancer; pipeline instances process independent event streams
- **Queue backpressure**: All asyncio queues have `maxsize=256`; overflow is logged and dropped gracefully
- **Agent concurrency**: Each agent is stateless; multiple pipeline workers can run in parallel
- **AI provider resilience**: `MultiProviderClient` tries Groq → OpenRouter → heuristic; no single provider outage blocks the entire pipeline
