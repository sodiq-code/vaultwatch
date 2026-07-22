# vaultwatch-rwa-mcp

A **domain-specific** [Model Context Protocol](https://modelcontextprotocol.io) server that wraps the 8 VaultWatch RWA / risk smart contracts on the Casper testnet and exposes them to any LLM agent — Claude Desktop, Cursor, Continue, Cody, or any MCP-compatible client.

> Casper ecosystem contribution. Part of [VaultWatch](https://github.com/sodiq-code/vaultwatch).

## Why a second MCP server?

The sibling [`casper-sentinel-mcp`](https://www.npmjs.com/package/casper-sentinel-mcp) package is a **general** server — it mixes market data (CoinGecko), Groq anomaly detection, sidecar SSE streaming, and x402 payments. That breadth is great for end-user dashboards but noisy for an agent that just wants to query or transact with the on-chain RWA / risk contract layer.

`vaultwatch-rwa-mcp` is **domain-specific**: it is exclusively about the 8 Odra contracts. Every tool maps 1-to-1 to a contract entry point or field. No LLM calls, no market data, no streaming — just deterministic on-chain reads and signed deploys.

## Contracts wrapped

| Contract | Role | Read tools | Write tools |
|----------|------|------------|-------------|
| **AuditTrail** | Immutable risk-finding log | `rwa_audit_get_count`, `rwa_audit_get_finding`, `rwa_audit_recent_findings` | `rwa_audit_record_finding` |
| **RiskOracle** | Open risk-score oracle | `rwa_risk_get_score`, `rwa_risk_is_high_risk` | `rwa_risk_update_score` |
| **RiskPolicyManager** | Hot-swappable thresholds | `rwa_policy_get_current`, `rwa_policy_get_version`, `rwa_policy_get_current_version` | `rwa_policy_upgrade` |
| **SentinelRegistry** | Subscriber registry | `rwa_sentinel_get_subscriber`, `rwa_sentinel_is_active`, `rwa_sentinel_get_count` | `rwa_sentinel_register`, `rwa_sentinel_deregister` |
| **SentinelAlertLog** | Alert history | `rwa_alert_get_log`, `rwa_alert_get_total_count` | `rwa_alert_log` |
| **SentinelCredit** | x402 prepaid credit | `rwa_credit_get_account`, `rwa_credit_get_balance`, `rwa_credit_get_prices`, `rwa_credit_get_total_revenue` | `rwa_credit_withdraw` |
| **SubscriberVault** | Escrowed prepay vaults | `rwa_vault_get_account`, `rwa_vault_get_balance`, `rwa_vault_get_total_locked` | `rwa_vault_open` (payable), `rwa_vault_withdraw` |
| **AgentBehaviorIndex** | AI agent accountability | `rwa_agent_get_metrics`, `rwa_agent_get_trust_score`, `rwa_agent_get_count` | `rwa_agent_record_decision` |

Plus 3 cross-cutting tools: `rwa_list_contracts`, `rwa_contract_entrypoints`, `rwa_contract_package`, `rwa_block_height`, and 2 wallet tools (`rwa_wallet_status`, `rwa_wallet_ensure`).

## Install

```bash
# From source (inside the vaultwatch repo)
pip install -r requirements.txt          # fastmcp, httpx, …

# Or via the npm launcher (once published)
npx vaultwatch-rwa-mcp
```

## Smoke-test flags

The server ships with two introspection flags that don't speak the MCP stdio
protocol — useful for CI smoke tests and quick local verification:

```bash
# Dump all 39 tools / 3 resources / 4 prompts as JSON (no network)
python -m vaultwatch_rwa_mcp.server --list-tools

# Exercise one free read against the live Casper testnet (confirms end-to-end)
python -m vaultwatch_rwa_mcp.server --smoke-read
# → {"contract":"AuditTrail","finding_count":9,"source":"on-chain"}

# Show usage
python -m vaultwatch_rwa_mcp.server --help
```

`--list-tools` exits non-zero if any tool is missing a description, so it's
safe to use as a CI gate.

## Configure

Reads work out-of-the-box against the public Casper testnet node.

Writes need an **agent wallet** — created programmatically on first call via the [CSPR.click AI Agent Skill](../skills/csprclick-skill/SKILL.md) pattern (`casper-js-sdk` v5 `PrivateKey.generate()`). No manual keygen, no committed secrets:

```bash
# Optional: override the agent key path (default ~/.vaultwatch/agent_key.pem)
export VAULTWATCH_AGENT_KEY_PATH=~/.vaultwatch/agent_key.pem

# Optional: override the RPC endpoint
export CASPER_RPC_URL=https://node.testnet.casper.network/rpc
```

On first write, the server auto-creates a wallet and logs the public key + testnet faucet URL. Fund it once at <https://testnet.cspr.live/tools/faucet>, then re-run. The deployer of the 8 contracts (Account 2) already holds `ROLE_ALL` on every contract — grant `OPERATOR`/`ADMIN` to the agent wallet via `grant_role` if you deploy with a fresh wallet.

## Connect from Claude Desktop

```json
{
  "mcpServers": {
    "vaultwatch-rwa": {
      "command": "python",
      "args": ["-m", "vaultwatch_rwa_mcp.server"],
      "cwd": "/path/to/vaultwatch"
    }
  }
}
```

Or via the npm launcher:

```json
{
  "mcpServers": {
    "vaultwatch-rwa": {
      "command": "npx",
      "args": ["vaultwatch-rwa-mcp"]
    }
  }
}
```

## Resources + Prompts

The server also exposes 3 MCP **resources** (LLM context injection):

- `rwa://contracts` — full contract registry (hashes, entry points, arg schemas)
- `rwa://policy/current` — live on-chain RiskPolicy JSON
- `rwa://audit/count` — live AuditTrail finding count

And 4 MCP **prompts** (reusable task templates):

- `rwa_explain_contracts` — explain the 8 contracts and their roles
- `rwa_audit_summary` — summarise the current on-chain audit state
- `rwa_risk_assessment` — assess on-chain risk for a Casper address
- `rwa_policy_review` — review the current RiskPolicy and recommend adjustments

## How reads work

Reads are free `query_global_state` JSON-RPC calls. The server implements the exact Odra 2.9.0 storage-key derivation (`blake2b(state_uref ++ blake2b(be32(field_index) ++ key_bytes))`) and bytesrepr decoders for every contract value type (`Finding`, `RiskScore`, `AlertRecord`, `Subscriber`, `AgentMetrics`, `CreditAccount`, `VaultAccount`, `RiskPolicy`). No gas, no signing, no third-party SDK — just stdlib `urllib` + `hashlib`.

## How writes work

Writes are REAL deploys signed via the CSPR.click AI Agent Skill integration (`agents.agent_wallet.AgentWallet` → `casper-js-sdk` v5, the only SDK that produces Casper-2.x-compatible signatures). Each write returns the verified deploy hash + a `testnet.cspr.live` link. The payable `open_vault` routes through the official `@make-software/casper-x402` helper (the only sanctioned way to attach CSPR to a stored-contract call).

## Test

```bash
# Unit (bytesrepr parsers + key derivation, no network)
pytest tests/unit/test_rwa_mcp_readers.py -v

# Integration (tool signatures + mocked RPC, no network)
pytest tests/integration/test_rwa_mcp_tools.py -v

# E2E (real testnet reads — free, no gas)
pytest tests/e2e/test_rwa_mcp_real_rpc.py -v --run-e2e
```

## License

MIT — same as the parent VaultWatch project.
