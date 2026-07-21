# VaultWatch — Verification Guide

**Repository**: https://github.com/sodiq-code/vaultwatch  
**Network**: Casper Testnet (`casper-test`)  
**Deployer**: `0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7`

> All 8 Odra contracts were successfully deployed on **July 11, 2026** with
> bulk-memory-safe WASM. The original June 24 deploys failed with
> "Bulk memory operations are not supported." The fix: recompile with
> `RUSTFLAGS=-C target-feature=-bulk-memory` + `wasm-opt --enable-bulk-memory=no`.
> See `DEPLOYMENT_GUIDE.md` and `scripts/check_wasm_bulk_memory.py`.
>
> **21 verified-success interaction deploys** were executed on **July 21, 2026**,
> each calling correct entry points (`record_finding`, `log_alert`, `register`,
> `deposit`, `record_decision`, `upgrade_policy`, `open_vault`, `update_score`)
> that exist on the deployed Odra contracts. Every deploy hash below resolves to
> a `Success` execution result on testnet.cspr.live.

---

## 1. Smart Contracts on Casper Testnet

All 8 Odra contracts deployed to `casper-test` on **July 11, 2026**.
Verified: 16 named keys on deployer account, all deploys executed successfully.

| Contract | Contract Hash | Package Hash | Deploy TX |
|----------|--------------|-------------|-----------|
| AuditTrail | `cd1579001dcd...d9932` | `7e653fc142dd...c270fa` | [view](https://testnet.cspr.live/deploy/b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6333a7) |
| SentinelRegistry | `9cce03a0e5d...4e31e` | `d97d1f1ef30b...a5f82` | [view](https://testnet.cspr.live/deploy/9a5eb4f83de8cbfef4f389516b977258b0e1d63179b288ca623a860fc6ec346c) |
| RiskOracle | `234a34a71fb0...80ff` | `1a47fd766eb0...c2e974` | [view](https://testnet.cspr.live/deploy/e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d) |
| SentinelCredit | `993d8947a6c8...1cbfb` | `47ea0c53777a...b686ae` | [view](https://testnet.cspr.live/deploy/0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71) |
| AgentBehaviorIndex | `1a976fe83936...d822b` | `d888dc369604...acbd2` | [view](https://testnet.cspr.live/deploy/05066c33ddb73b523ab8f67275ca6096254f9d1832e76075d1e5f41f188b7dd0) |
| SentinelAlertLog | `43f9b7df3f9f...9322` | `f75ce1bc111d...14b78` | [view](https://testnet.cspr.live/deploy/53317e080ffdffcf097447ea3375c9195c6936fe7b1ed53795bf46134322a925) |
| RiskPolicyManager | `1027cb2a989b...1d85` | `aaf7f48dbcdb...7b2c4` | [view](https://testnet.cspr.live/deploy/93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e) |
| SubscriberVault | `9a93db9c1f31...7bd0` | `68c4b7cca849...5d211` | [view](https://testnet.cspr.live/deploy/6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d) |

### Verification (Triple-Checked)

```bash
# 1. RPC: info_get_transaction shows execution_results with Success outcome
python3 scripts/verify_deploys.py --deploy-hashes transaction_hashes_live.json

# 2. RPC: state_get_account_info shows named_keys > 0
python3 scripts/verify_deploys.py --account 0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7

# 3. WASM: zero bulk-memory opcodes (hard gate)
python3 scripts/check_wasm_bulk_memory.py contracts/wasm/

# 4. Entry-point verification (confirms on-chain EP names match deploy calls)
python3 scripts/verify_contract_entrypoints.py
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

```bash
pip install casper-sentinel==4.0.0
python -c "from vaultwatch import VaultWatchClient; print('SDK OK')"
npm install casper-sentinel-mcp
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

## 8. Contract Interactions — 21 Verified-Success On-Chain TX Hashes

21 interaction deploys broadcast to Casper testnet on **July 21, 2026**, all
calling **correct entry points** that exist on the deployed Odra contracts.
Every deploy was **verified on-chain** with `Success` execution result before
recording. Total on-chain TX hashes: **29** (8 contract deploys + 21 verified
interactions).

### Entry Point Mapping (Verified On-Chain)

| Contract | Correct Entry Point | Previous (Broken) |
|----------|-------------------|-------------------|
| AuditTrail | `record_finding` | ~~add_entry~~ |
| RiskOracle | `update_score` | ~~protocol_scan~~ |
| SentinelAlertLog | `log_alert` | ~~batch_flush~~ |
| SentinelRegistry | `register` | ~~register_sentinel~~ |
| SentinelCredit | `deposit` | ~~issue_credit~~ |
| AgentBehaviorIndex | `record_decision` | ~~record_action~~ |
| RiskPolicyManager | `upgrade_policy` | ~~set_threshold~~ |
| SubscriberVault | `open_vault` | ~~subscribe~~ |

### Verified Interaction Deploys

> Run `python3 scripts/broadcast_interactions.py` with the deployer secret key
> to regenerate these hashes. The script verifies each deploy on-chain before
> recording it. Output is saved to `proof/interaction_hashes.json`.

<!-- INTERACTION_HASHES_TABLE_START -->
<!-- Auto-populated by scripts/broadcast_interactions.py on 2026-07-21 -->
| # | Interaction | Status | Transaction Hash |
|---|-------------|--------|-------------------|
| 1 | AuditTrail::record_finding[anomaly_scan_CasperSwap] | verified_success | [`86d00025e95dea72…`](https://testnet.cspr.live/deploy/86d00025e95dea720e2b693e6188c3aa2271854d887674241912b7c1b70b5dd3) |
| 2 | AuditTrail::record_finding[rwa_treasury_scan] | verified_success | [`66317cc6e500c22e…`](https://testnet.cspr.live/deploy/66317cc6e500c22ea902456c88c0f91f83e460bb521aa532b543db103b7b2203) |
| 3 | AuditTrail::record_finding[liquidity_monitor] | verified_success | [`64fd34dd9bca6d5d…`](https://testnet.cspr.live/deploy/64fd34dd9bca6d5d92379d0ba26a4d47383018951fabccf1f7b4946688141b04) |
| 4 | RiskOracle::update_score[CasperSwap_HIGH] | verified_success | [`c22b90c085ed393c…`](https://testnet.cspr.live/deploy/c22b90c085ed393c49d160e0048a5b525cbe9168029ea63bdbdec0f9dd6a267a) |
| 5 | RiskOracle::update_score[CasperLend_MEDIUM] | verified_success | [`9b639792e864321b…`](https://testnet.cspr.live/deploy/9b639792e864321be75a4ff1ee75ae60e5e2acb0e71671520427536bc7deba29) |
| 6 | RiskOracle::update_score[Treasury_LOW] | verified_success | [`ad24b32f936208ff…`](https://testnet.cspr.live/deploy/ad24b32f936208ff65a69ade8c0aeca8f64352cbfe7e745fd198def109dea509) |
| 7 | SentinelAlertLog::log_alert[HIGH_price_crash] | verified_success | [`c4e8bb8ea80ef200…`](https://testnet.cspr.live/deploy/c4e8bb8ea80ef2002ad3998bbfa29c62c3f4dbd2a0ecd7eeec3aae720dea9c41) |
| 8 | SentinelAlertLog::log_alert[MEDIUM_collateral] | verified_success | [`c5c22bcc94fd0d16…`](https://testnet.cspr.live/deploy/c5c22bcc94fd0d16e4c8614a844bb665e14ffa1347371a54697b0b31a43b6500) |
| 9 | SentinelAlertLog::log_alert[LOW_liquidity] | verified_success | [`7f683c5cf448e7d5…`](https://testnet.cspr.live/deploy/7f683c5cf448e7d583e55583a0a5b2557c702cf3da5e3f2996672356153720e3) |
| 10 | SentinelAlertLog::log_alert[HIGH_rwa_compliance] | verified_success | [`60bf62fd56cb6481…`](https://testnet.cspr.live/deploy/60bf62fd56cb6481f798a9e0327a5354772855706b021af181cf50d119403fa4) |
| 11 | SentinelRegistry::register[pipeline_v3] | verified_success | [`7899efd9a50b48b9…`](https://testnet.cspr.live/deploy/7899efd9a50b48b985dc94ed6d4c754874d5d0db36776e10f17494303c63512d) |
| 12 | SentinelRegistry::register[mcp_v3] | verified_success | [`892f31975cae02fd…`](https://testnet.cspr.live/deploy/892f31975cae02fd77706803418946c95a1ee63f96e988b998868aabd055a6a3) |
| 13 | SentinelCredit::deposit[pipeline_account] | verified_success | [`ce5e4e5752b75baf…`](https://testnet.cspr.live/deploy/ce5e4e5752b75baf913fed550f6b3686c668138b2379b2911fc91cbd3be48593) |
| 14 | SentinelCredit::deposit[mcp_account] | verified_success | [`1f25bd1c4f1a426d…`](https://testnet.cspr.live/deploy/1f25bd1c4f1a426dc393fd34e4f2159697c32463a7cfaa47e236e5a6fc2a71c7) |
| 15 | AgentBehaviorIndex::record_decision[anomaly_classify] | verified_success | [`d8c4fa752d453034…`](https://testnet.cspr.live/deploy/d8c4fa752d453034a91b52f921b2564b4917e6aa7c5c0e8f9dd91552e21f42b9) |
| 16 | AgentBehaviorIndex::record_decision[correction_skip] | verified_success | [`5e125cca3aa41df1…`](https://testnet.cspr.live/deploy/5e125cca3aa41df18f1c62684fd52716adada69d06612d8147fb81fc2f0d0c35) |
| 17 | AgentBehaviorIndex::record_decision[safety_reject] | verified_success | [`7d297d8196135f67…`](https://testnet.cspr.live/deploy/7d297d8196135f67094d16cae7f719f84947962feb530f0629b93bd7447ebbf4) |
| 18 | RiskPolicyManager::upgrade_policy[v2_conservative] | verified_success | [`a6b9dad28323894f…`](https://testnet.cspr.live/deploy/a6b9dad28323894ff3e2c0b8440bc9953f83498a49410e3d46347e9ec5143f81) |
| 19 | RiskPolicyManager::upgrade_policy[v3_aggressive] | verified_success | [`effe124f23754b16…`](https://testnet.cspr.live/deploy/effe124f23754b16ed9ce4daa342a14b565f2986fb309983949e29b434bf66c9) |
| 20 | SubscriberVault::open_vault[pro_30d] | verified_success | [`47b96facf685059f…`](https://testnet.cspr.live/deploy/47b96facf685059f81375335b8298544854420f378b6a1c7a5a03d8764dd5a7f) |
| 21 | SubscriberVault::open_vault[basic_7d] | verified_success | [`5e09a0fcc9ccc8aa…`](https://testnet.cspr.live/deploy/5e09a0fcc9ccc8aab086be601925d4851a63e5c2cf8f887435567a55e43ae25e) |
<!-- INTERACTION_HASHES_TABLE_END -->

**Total: 29 on-chain TX hashes (8 contract deploys + 21 verified interactions) ✓**

Full machine-readable list: [`proof/interaction_hashes.json`](interaction_hashes.json)

---

## 9. On-Chain Resources (Casper AI Toolkit)

This project uses the following resources from the [Casper AI Toolkit](https://www.casper.network/ai):

| Resource | URL | Usage |
|----------|-----|-------|
| Casper MCP Server | https://github.com/casper-network/casper-mcp-server | Chain state queries for agent context |
| CSPR.cloud APIs | https://cspr.cloud | REST + Streaming middleware for blockchain interaction |
| Odra Framework | https://github.com/odra-lang/odra | Smart contract development with AI-discoverable docs |
| x402 Micropayments Protocol | https://github.com/x402-payment/x402-spec | HTTP-native payment protocol for agent API access |
| CSPR.click AI Agent Skill | https://cspr.click | Agent wallet creation and transaction signing |