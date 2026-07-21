# VaultWatch — Verification Guide

**Repository**: https://github.com/sodiq-code/vaultwatch  
**Network**: Casper Testnet (`casper-test`)  
**Deployer**: `0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7`

> All 8 Odra contracts were successfully redeployed on **July 11, 2026** with
> bulk-memory-safe WASM. The original June 24 deploys failed with
> "Bulk memory operations are not supported." The fix: recompile with
> `RUSTFLAGS=-C target-feature=-bulk-memory` + `wasm-opt --enable-bulk-memory=no`.
> See `DEPLOYMENT_GUIDE.md` and `scripts/check_wasm_bulk_memory.py`.

---

## ⚠️ WARNING: Interaction Deploys Need Replacement

> **Fix #21**: The 21 interaction deploys listed in §8 below were broadcast by
> `scripts/broadcast_interactions.py` using **incorrect entry point names** that
> do not match the actual Rust contract entry points. Specifically:
>
> | Script Called | Contract Actually Expects | Status |
> |---------------|---------------------------|--------|
> | `add_entry` | `record_finding` | ❌ Wrong |
> | `pipeline_heartbeat` | `record_finding` | ❌ Wrong |
> | `pipeline_status` | `record_finding` | ❌ Wrong |
> | `update_score` (correct) | `update_score` | ✅ Correct |
> | `register_sentinel` | `register` | ❌ Wrong |
> | `subscribe` | `open_vault` | ❌ Wrong |
> | `record_action` | `record_decision` | ❌ Wrong |
> | `issue_credit` | `deposit` | ❌ Wrong |
> | `collect_fees` | `deduct` | ❌ Wrong |
>
> These 21 deploys likely **failed on-chain** because the Casper runtime rejects
> calls to non-existent entry points. They need to be re-broadcast with the
> corrected entry point names using the fixed `broadcast_interactions.py` script.
>
> The **8 contract deployment hashes in §1 are verified and correct** — those
> are unaffected by this issue.

---

## 1. Smart Contracts on Casper Testnet

All 8 Odra contracts deployed to `casper-test` on **July 11, 2026**.
Verified: 16 named keys on deployer account, all deploys executed successfully.

> **Hash verification**: All 8 deploy hashes below have been verified against
> `transaction_hashes_live.json` and match exactly. ✅

| Contract | Transaction Hash | Verified |
|----------|-------------|----------|
| AuditTrail | `b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6333a7` | ✅ Verified |
| SentinelRegistry | `9a5eb4f83de8cbfef4f389516b977258b0e1d63179b288ca623a860fc6ec346c` | ✅ Verified |
| RiskOracle | `e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d` | ✅ Verified |
| SentinelCredit | `0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71` | ✅ Verified |
| AgentBehaviorIndex | `05066c33ddb73b523ab8f67275ca6096254f9d1832e76075d1e5f41f188b7dd0` | ✅ Verified |
| SentinelAlertLog | `53317e080ffdffcf097447ea3375c9195c6936fe7b1ed53795bf46134322a925` | ✅ Verified |
| RiskPolicyManager | `93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e` | ✅ Verified |
| SubscriberVault | `6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d` | ✅ Verified |

### Verification (Triple-Checked)

```bash
# 1. RPC: info_get_transaction shows execution_results with Success outcome
python3 scripts/verify_deploys.py --deploy-hashes transaction_hashes_live.json

# 2. RPC: state_get_account_info shows named_keys > 0
python3 scripts/verify_deploys.py --account 0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7

# 3. WASM: zero bulk-memory opcodes (hard gate)
python3 scripts/check_wasm_bulk_memory.py contracts/wasm/
```

### Historical Note (Failed Deploys — June 24, 2026)

The original 8 deploy attempts on June 24, 2026 all FAILED with
"Bulk memory operations are not supported." They are superseded by
the July 11, 2026 redeploys above.

Root cause + fix: see `DEPLOYMENT_GUIDE.md`.

---

## 2. WASM Artifacts

8 `.wasm` files in `contracts/wasm/`, each compiled from Rust/Odra source
with `-C target-feature=-bulk-memory` flag and post-processed with `wasm-opt`.

---

## 3. Published Packages

| Package | Registry | URL |
|---------|----------|-----|
| `casper-sentinel` | PyPI | https://pypi.org/project/casper-sentinel/4.0.0/ |
| `casper-sentinel-mcp` | npm | https://www.npmjs.com/package/casper-sentinel-mcp |
| `vaultwatch-rwa-mcp` | npm | https://www.npmjs.com/package/vaultwatch-rwa-mcp |

```bash
pip install casper-sentinel==4.0.0
python -c "from vaultwatch import VaultWatchClient; print('SDK OK')"
npm install casper-sentinel-mcp
npm install vaultwatch-rwa-mcp
```

---

## 4. Test Suite

```bash
pip install -r requirements.txt
pip install -e sdk/
pytest tests/ -v
```

Expected: all tests passing across unit, integration, and demo suites.

Full test output: [`proof/05_test_results.txt`](05_test_results.txt)

---

## 5. Live Dashboard

**URL**: https://dashboard-rho-amber-89.vercel.app

Powered by live data: Groq llama-3.3-70b-versatile, CoinGecko CSPR price,
cspr.cloud block data. Every contract hash links to testnet.cspr.live.

---

## 6. Agent Pipeline

7 AI agents (6 pipeline + SafetyGuard) powered by Groq, writing findings to
8 Odra contracts on Casper testnet. Full pipeline instrumented with OpenTelemetry.

```bash
ls agents/
# Expected: scanner_agent.py, anomaly_agent.py, self_correction_agent.py,
#           rwa_agent.py, safety_guard.py, audit_agent.py, intel_agent.py
```

---

## 7. CI Status

[![CI](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml)

Every push to `main` runs: lint → unit tests → integration tests → contract tests → Docker build.

---

## 8. Contract Interactions — 21 On-Chain TX Hashes

> **⚠️ WARNING**: These 21 interaction deploys were broadcast using incorrect
> entry point names (see warning at top of file). They likely failed on-chain.
> New verified interaction deploys will be listed in §9 after the
> `broadcast_interactions.py` script is fixed and re-run.

21 interaction deploys broadcast to Casper testnet, bringing total on-chain
TX hashes to **29** (8 contract deploys + 21 interactions).

| # | Interaction | Transaction Hash | Status |
|---|-------------|-------------|--------|
| 1 | AuditTrail::add_entry | `aca60b05fb801960ae1f4db9bdd3c2d3a0cfd142c9b020edcf57df27c0f8ea72` | ⚠️ Needs replacement |
| 2 | AuditTrail::pipeline_heartbeat | `6f5cd6bf7a21146502d2b5e53250a45aa352e73560e6d228a0c271fc2d29262d` | ⚠️ Needs replacement |
| 3 | RiskOracle::update_score | `ae061e24af2fbd19f88e5103db2f97abcc565ced54b128b8e3fda4f86dbff285` | ⚠️ Needs replacement |
| 4 | SentinelAlertLog::log_alert[HIGH] | `b295168fe1f88b8a0380c9b8f3519ca5811ee969a909d24da28fdf358a9a96fd` | ⚠️ Needs replacement |
| 5 | SentinelAlertLog::log_alert[LOW] | `5319acd5a9794d2ecc10ad9f1345e92da93b5736ea309845237432c771e6de8d` | ⚠️ Needs replacement |
| 6 | SentinelRegistry::register_sentinel | `ef9c93c6d465041c7c22cfc4fac8619c0375528b159884411e0677a54a063f37` | ⚠️ Needs replacement |
| 7 | SentinelRegistry::register_sentinel[mcp] | `a0225857d684ed651ace79fc7bab3c49b7beabc27ecbb5a79add962a4d1a333c` | ⚠️ Needs replacement |
| 8 | SubscriberVault::subscribe | `10194da10e07ab724aefd4e297e38ee2f4fa177031acdc9135e19c34a86e548b` | ⚠️ Needs replacement |
| 9 | AgentBehaviorIndex::record_action | `da61b7b38388e683c37f8040514a1b2a77b59209f9aa64c661094503e85169db` | ⚠️ Needs replacement |
| 10 | AgentBehaviorIndex::record_action[skip] | `36811baffde99c09663c64ccf08a0ceb3d86581c3cae57a82dfdb7d40655a568` | ⚠️ Needs replacement |
| 11 | RiskPolicyManager::set_threshold | `77b1f5e6acf89dbdec06a4d98cd0052b5a4c55761ded7f9960604550d401eb8a` | ⚠️ Needs replacement |
| 12 | RiskPolicyManager::set_threshold[max] | `7efd0b77f3bbec253c074639955e7efb08795bac8b9dbbcbf88210c18e723e03` | ⚠️ Needs replacement |
| 13 | SentinelCredit::issue_credit | `29f1924933f16949b5b82d462ed8ad85c1f1d8be25226c55a1c6a627ba2c6ed8` | ⚠️ Needs replacement |
| 14 | AuditTrail::pipeline_status | `ce5e64355638df810ac4b6ee489990363976319a21487394ef62f91c67d1c662` | ⚠️ Needs replacement |
| 15 | RiskOracle::protocol_scan | `62e3dc976e412ee45d7cc013939ce90abb9b4f396e19e93d6d46ea27700e98ad` | ⚠️ Needs replacement |
| 16 | SentinelAlertLog::batch_flush | `019822354bb63b29f613e34601751977647d3ad9f4719547d70e067789cfd7fa` | ⚠️ Needs replacement |
| 17 | AgentBehaviorIndex::agent_init | `3ea7ff328ed52fc74325a7b227d6ea0f8772a7422f4d519a674d7b7d67b03cfb` | ⚠️ Needs replacement |
| 18 | RiskPolicyManager::policy_reload | `5da86f8eaca22f96b7756c7958a1aff03a300e020569f0cfadcafaafd53d979f` | ⚠️ Needs replacement |
| 19 | SentinelRegistry::health_ping | `d0240be05b2834a1634d3ee28d361d3381a52c551c9fdfb6fe28a2655accb3ee` | ⚠️ Needs replacement |
| 20 | SentinelCredit::balance_check | `97efecfe56f004aeb0178bd309fd97d3b17ae60a43e1b79b9a3a0c4ca0a53d68` | ⚠️ Needs replacement |
| 21 | SubscriberVault::vault_sync | `3449dd44973390ff3aa2ff4922b1f540f1c5d265aae216a1aff803a07ab0a6a8` | ⚠️ Needs replacement |

**Total: 29 on-chain TX hashes (8 contract deploys ✅ + 21 interactions ⚠️)**

Full machine-readable list: [`proof/interaction_hashes.json`](interaction_hashes.json)

---

## 9. New Verified Interactions (Post-Fix)

> This section will be populated after `scripts/broadcast_interactions.py` is
> updated with the correct entry point names and re-run against Casper testnet.
>
> Expected corrected entry point mappings:
>
> | # | Corrected Interaction | Entry Point | Expected Status |
> |---|----------------------|-------------|-----------------|
> | 1 | AuditTrail::record_finding[agent_risk_scan] | `record_finding` | Pending |
> | 2 | AuditTrail::record_finding[pipeline_heartbeat] | `record_finding` | Pending |
> | 3 | RiskOracle::update_score[CasperLend] | `update_score` | Pending |
> | 4 | SentinelAlertLog::log_alert[HIGH] | `log_alert` | Pending |
> | 5 | SentinelAlertLog::log_alert[LOW] | `log_alert` | Pending |
> | 6 | SentinelRegistry::register[v2] | `register` | Pending |
> | 7 | SentinelRegistry::register[mcp_v2] | `register` | Pending |
> | 8 | SubscriberVault::open_vault[basic_7d] | `open_vault` | Pending |
> | 9 | AgentBehaviorIndex::record_decision[classify] | `record_decision` | Pending |
> | 10 | AgentBehaviorIndex::record_decision[skip] | `record_decision` | Pending |
> | 11 | RiskPolicyManager::update_policy[min_confidence] | `update_policy` | Pending |
> | 12 | RiskPolicyManager::update_policy[max_risk] | `update_policy` | Pending |
> | 13 | SentinelCredit::deposit[deployer] | `deposit` | Pending |
> | 14 | AuditTrail::record_finding[pipeline_status] | `record_finding` | Pending |
> | 15 | RiskOracle::update_score[protocol_scan] | `update_score` | Pending |
> | 16 | SentinelAlertLog::log_alert[batch] | `log_alert` | Pending |
> | 17 | AgentBehaviorIndex::record_decision[agent_init] | `record_decision` | Pending |
> | 18 | RiskPolicyManager::update_policy[policy_reload] | `update_policy` | Pending |
> | 19 | SentinelRegistry::increment_alert_count[health_ping] | `increment_alert_count` | Pending |
> | 20 | SentinelCredit::get_balance[balance_check] | `get_balance` (read-only) | Pending |
> | 21 | SubscriberVault::deduct[vault_sync] | `deduct` | Pending |

---

## 10. Verification Instructions

To independently verify all deploy hashes and contract interactions:

### Step 1: Verify Contract Deployment Hashes

```bash
# Check all 8 contract deploys have "Success" execution results
python3 scripts/verify_deploys.py --deploy-hashes transaction_hashes_live.json
```

This script queries `info_get_deploy` for each hash in `transaction_hashes_live.json`
and confirms:
- The deploy exists on Casper testnet
- `execution_results[0].result` contains `"Success"`
- The deploy was not rejected or failed

### Step 2: Verify Deployer Account Has Named Keys

```bash
# Check that the deployer account has named keys from contract deploys
python3 scripts/verify_deploys.py --account 0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7
```

This confirms 16+ named keys exist on the deployer account, proving
the contracts were properly initialized.

### Step 3: Verify WASM Binaries Are Bulk-Memory-Safe

```bash
# Ensure no bulk-memory opcodes in any WASM binary
python3 scripts/check_wasm_bulk_memory.py contracts/wasm/
```

This is the hard gate — any WASM with bulk-memory opcodes will be
rejected by the Casper runtime.

### Step 4: Verify Interaction Deploys (After Fix)

```bash
# After broadcast_interactions.py is fixed and re-run:
python3 scripts/verify_deploys.py --deploy-hashes proof/interaction_hashes.json
```

### Step 5: Manual Verification on Explorer

Visit each deploy hash on [testnet.cspr.live](https://testnet.cspr.live):
- Confirm "Status: Success"
- Confirm the entry point name matches the contract source
- Confirm the deploy timestamp is after July 11, 2026

---

## 11. Hash Cross-Reference

All 8 contract deployment hashes are cross-referenced across three sources:

| Source | File | Status |
|--------|------|--------|
| PROOF.md | This file | ✅ Consistent |
| transaction_hashes_live.json | `/transaction_hashes_live.json` | ✅ Consistent |
| MCP Server | `/vaultwatch_mcp/server.py` | ✅ Consistent |
| RWA MCP Server | `/vaultwatch_rwa_mcp/server.py` | ✅ Consistent |

Any discrepancy between these files should be resolved in favor of
`transaction_hashes_live.json` (the authoritative source from the
Casper RPC at deploy time).
