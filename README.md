# VaultWatch

**AI-Powered DeFi Risk Intelligence Agent on Casper**

VaultWatch is a DeFi risk monitoring and intelligence platform built on the Casper blockchain. Seven Groq-powered AI agents (6 pipeline + 1 SafetyGuard) monitor on-chain activity, classify anomalies, and write verified findings to eight Odra smart contracts — instrumented with OpenTelemetry and exposed via a 20-tool FastMCP server callable from Claude Desktop.

[![CI](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml)
[![Build Contracts](https://github.com/sodiq-code/vaultwatch/actions/workflows/build-contracts.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/build-contracts.yml)
[![CodeQL](https://github.com/sodiq-code/vaultwatch/actions/workflows/codeql.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/codeql.yml)
[![Tests](https://img.shields.io/badge/tests-481%20definitions%20across%2039%20files-blue.svg)](tests/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Casper Testnet](https://img.shields.io/badge/casper-testnet%20live-orange.svg)](https://testnet.cspr.live/)
[![License: MIT](https://img.shields.io/badge/license-MIT-success.svg)](LICENSE)

---

## Demo Video

[![VaultWatch Demo](https://img.youtube.com/vi/Jmg_MFSxwdE/maxresdefault.jpg)](https://youtu.be/Jmg_MFSxwdE)

**[Watch on YouTube](https://youtu.be/Jmg_MFSxwdE)**

---

## On-Chain Verification Summary

All deployment claims are independently verifiable on Casper testnet. Every deploy hash resolves to a confirmed `Success` execution result. Verification performed via RPC at `node.testnet.casper.network/rpc` ([`scripts/verify_deploys.py`](https://github.com/sodiq-code/vaultwatch/blob/main/scripts/verify_deploys.py)).

| Category | Count | Status | Proof |
|----------|-------|--------|-------|
| Contract installations | 8 | ✅ Verified on-chain (named_keys + explorer) | [`proof/deploy_verification_results.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/deploy_verification_results.json) |
| Interaction deploys | 21 | ✅ All RPC verified SUCCESS | [`proof/interaction_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/interaction_hashes.json) |
| Upgrade deploys | 6 | ✅ All RPC verified SUCCESS (6/6 checks pass) | [`proof/upgrade_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/upgrade_hashes.json) |
| x402 payment deploy | 1 | ✅ RPC verified SUCCESS | [`proof/x402_payment_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/x402_payment_hashes.json) |
| **Total verified (SUCCESS)** | **36** | | |

---

## Deployer Accounts

### Main Deployer

```
0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7
```

- 16 named_keys (8 contract package hashes + 8 access tokens) — [`proof/deploy_verification_results.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/deploy_verification_results.json)
- Deployed all 8 core contracts (AuditTrail, RiskOracle, SentinelCredit, SentinelRegistry, SentinelAlertLog, AgentBehaviorIndex, RiskPolicyManager, SubscriberVault)
- Contract deploy hashes: [`transaction_hashes_live.json`](https://github.com/sodiq-code/vaultwatch/blob/main/transaction_hashes_live.json)
- All 8 contract deploys verified on-chain via named_keys proof — contracts installed and active on Casper testnet ([`proof/deploy_verification_results.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/deploy_verification_results.json))

**[View on explorer](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7)**

### Secondary Deployer

```
02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db
```

- Account hash: `0debd9ab6e903b6d3269f7c9ceaf28320e3b91209e1a1080fd9ddf097d3dbd68` — [`proof/upgrade_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/upgrade_hashes.json)
- 4 named_keys: RiskPolicyManager + SubscriberVault (2 contracts for upgrade demo + x402)
- Deployed RiskPolicyManager v1→v2 upgrade and x402 SubscriberVault payment

**[View on explorer](https://testnet.cspr.live/account/02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db)**

---

## Contract Package Hashes (On-Chain)

Verified from named_keys on deployer accounts ([`proof/deploy_verification_results.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/deploy_verification_results.json)):

| Contract | Package Hash | Deployer | Explorer |
|----------|-------------|----------|---------|
| AuditTrail | `hash-7e653fc142ddd4f1759aec0c2f4fb0537eb167cfb9771d12c37ae55f29c270fa` | Main | [View](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7) |
| RiskOracle | `hash-1a47fd766eb021aa83cc44b5a729920842253510936cbe9a1545bf6dc7c2e974` | Main | [View](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7) |
| SentinelCredit | `hash-47ea0c53777a68d79cf2f66b9171e4a1b588048c283b2b2504fc5ecfe1b686ae` | Main | [View](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7) |
| SentinelRegistry | `hash-d97d1f1ef30bf765fbf13aa11817fea409b67056dd59faf6de28c94ad85a5f82` | Main | [View](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7) |
| SentinelAlertLog | `hash-f75ce1bc111d185c39d7c81d5a18b093749643957b8c3ba3309613401fb14b78` | Main | [View](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7) |
| AgentBehaviorIndex | `hash-d888dc3696046633582f1355f9708dfbd5acde3528466a562fa0601ad6eacbd2` | Main | [View](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7) |
| RiskPolicyManager (main) | `hash-aaf7f48dbcdbd59996b9b181c7980bb6c5116a7c72005ce169b1619d94d7b2c4` | Main | [View](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7) |
| RiskPolicyManager (upgrade demo) | `hash-417f5f7268acd956c4ce75fc1714f74f8a6bc819e0ad801fc60dc425d729f522` | Secondary | [View](https://testnet.cspr.live/account/02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db) |
| SubscriberVault (main) | `hash-68c4b7cca84982833af3f9346a5a9ea337bfdcd20875bd82f4c7ec7b1505d211` | Main | [View](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7) |
| SubscriberVault (x402) | `hash-d1cb42e21855b938d7e189186bb13751fc4d2523da53e1482027595a0f3463bf` | Secondary | [View](https://testnet.cspr.live/account/02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db) |

---

## 8 Contract Deployment Transactions

All 8 core contracts deployed July 11, 2026 to `casper-test`. Verified on-chain via named_keys proof ([`proof/deploy_verification_results.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/deploy_verification_results.json)).

| Contract | Deploy Hash | Gas | Explorer |
|----------|------------|-----|---------|
| AuditTrail | `b9c70cdc…336a7` | 138.14 CSPR | [✅ View](https://testnet.cspr.live/deploy/b9c70cdceff1011008b3933835d4a46146f26f1d1e82ada8520be77e1d6333a7) |
| SentinelRegistry | `9a5eb4f8…346c` | 138.17 CSPR | [✅ View](https://testnet.cspr.live/deploy/9a5eb4f83de8cbfef4f389516b977258b0e1d63179b288ca623a860fc6ec346c) |
| RiskOracle | `e071aacc…7c9d` | 135.02 CSPR | [✅ View](https://testnet.cspr.live/deploy/e071aacc460a62e538092f5006930710f49e632598846c4c843e3daf0c5a7c9d) |
| SentinelCredit | `0c09f2ad…af71` | 143.32 CSPR | [✅ View](https://testnet.cspr.live/deploy/0c09f2ad66701b38b1720390e20bf8ac5b7bf6a20cc174cba44f3861549baf71) |
| AgentBehaviorIndex | `05066c33…7dd0` | 137.09 CSPR | [✅ View](https://testnet.cspr.live/deploy/05066c33ddb73b523ab8f67275ca6096254f9d1832e76075d1e5f41f188b7dd0) |
| SentinelAlertLog | `53317e08…a925` | 140.18 CSPR | [✅ View](https://testnet.cspr.live/deploy/53317e080ffdffcf097447ea3375c9195c6936fe7b1ed53795bf46134322a925) |
| RiskPolicyManager | `93e35d64…ee2e` | 136.94 CSPR | [✅ View](https://testnet.cspr.live/deploy/93e35d6488dcab8524a22c82241c7ddc6d07b0f7c011544e6c4a296c1a0eee2e) |
| SubscriberVault | `6620787c…956d` | 143.39 CSPR | [✅ View](https://testnet.cspr.live/deploy/6620787c14d9d78506b281be8c95c8f9b105781b9705d2bd9736f2aabfd6956d) |

Gas data source: [`proof/deploy_verification_results.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/deploy_verification_results.json)

---

## 21 Interaction Deploys — All Verified SUCCESS

Each deploy verified via RPC `info_get_deploy` showing `execution_results` with Success outcome. Source: [`proof/interaction_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/interaction_hashes.json)

| Deploy | Contract | Entry Point | Hash | Explorer |
|--------|----------|-------------|------|---------|
| anomaly_scan_CasperSwap | AuditTrail | `record_finding` | `86d00025…5dd3` | [✅ View](https://testnet.cspr.live/deploy/86d00025e95dea720e2b693e6188c3aa2271854d887674241912b7c1b70b5dd3) |
| rwa_treasury_scan | AuditTrail | `record_finding` | `66317cc6…2203` | [✅ View](https://testnet.cspr.live/deploy/66317cc6e500c22ea902456c88c0f91f83e460bb521aa532b543db103b7b2203) |
| liquidity_monitor | AuditTrail | `record_finding` | `64fd34dd…1b04` | [✅ View](https://testnet.cspr.live/deploy/64fd34dd9bca6d5d92379d0ba26a4d47383018951fabccf1f7b4946688141b04) |
| CasperSwap_HIGH | RiskOracle | `update_score` | `c22b90c0…267a` | [✅ View](https://testnet.cspr.live/deploy/c22b90c085ed393c49d160e0048a5b525cbe9168029ea63bdbdec0f9dd6a267a) |
| CasperLend_MEDIUM | RiskOracle | `update_score` | `9b639792…ba29` | [✅ View](https://testnet.cspr.live/deploy/9b639792e864321be75a4ff1ee75ae60e5e2acb0e71671520427536bc7deba29) |
| Treasury_LOW | RiskOracle | `update_score` | `ad24b32f…a509` | [✅ View](https://testnet.cspr.live/deploy/ad24b32f936208ff65a69ade8c0aeca8f64352cbfe7e745fd198def109dea509) |
| HIGH_price_crash | SentinelAlertLog | `log_alert` | `c4e8bb8e…9c41` | [✅ View](https://testnet.cspr.live/deploy/c4e8bb8ea80ef2002ad3998bbfa29c62c3f4dbd2a0ecd7eeec3aae720dea9c41) |
| MEDIUM_collateral | SentinelAlertLog | `log_alert` | `c5c22bcc…6500` | [✅ View](https://testnet.cspr.live/deploy/c5c22bcc94fd0d16e4c8614a844bb665e14ffa1347371a54697b0b31a43b6500) |
| LOW_liquidity | SentinelAlertLog | `log_alert` | `7f683c5c…20e3` | [✅ View](https://testnet.cspr.live/deploy/7f683c5cf448e7d583e55583a0a5b2557c702cf3da5e3f2996672356153720e3) |
| HIGH_rwa_compliance | SentinelAlertLog | `log_alert` | `60bf62fd…3fa4` | [✅ View](https://testnet.cspr.live/deploy/60bf62fd56cb6481f798a9e0327a5354772855706b021af181cf50d119403fa4) |
| pipeline_v3 | SentinelRegistry | `register` | `7899efd9…512d` | [✅ View](https://testnet.cspr.live/deploy/7899efd9a50b48b985dc94ed6d4c754874d5d0db36776e10f17494303c63512d) |
| mcp_v3 | SentinelRegistry | `register` | `892f3197…a6a3` | [✅ View](https://testnet.cspr.live/deploy/892f31975cae02fd77706803418946c95a1ee63f96e988b998868aabd055a6a3) |
| pipeline_account | SentinelCredit | `deposit` | `ce5e4e57…8593` | [✅ View](https://testnet.cspr.live/deploy/ce5e4e5752b75baf913fed550f6b3686c668138b2379b2911fc91cbd3be48593) |
| mcp_account | SentinelCredit | `deposit` | `1f25bd1c…71c7` | [✅ View](https://testnet.cspr.live/deploy/1f25bd1c4f1a426dc393fd34e4f2159697c32463a7cfaa47e236e5a6fc2a71c7) |
| anomaly_classify | AgentBehaviorIndex | `record_decision` | `d8c4fa75…42b9` | [✅ View](https://testnet.cspr.live/deploy/d8c4fa752d453034a91b52f921b2564b4917e6aa7c5c0e8f9dd91552e21f42b9) |
| correction_skip | AgentBehaviorIndex | `record_decision` | `5e125cca…0c35` | [✅ View](https://testnet.cspr.live/deploy/5e125cca3aa41df18f1c62684fd52716adada69d06612d8147fb81fc2f0d0c35) |
| safety_reject | AgentBehaviorIndex | `record_decision` | `7d297d81…bbf4` | [✅ View](https://testnet.cspr.live/deploy/7d297d8196135f67094d16cae7f719f84947962feb530f0629b93bd7447ebbf4) |
| v2_conservative | RiskPolicyManager | `upgrade_policy` | `a6b9dad2…3f81` | [✅ View](https://testnet.cspr.live/deploy/a6b9dad28323894ff3e2c0b8440bc9953f83498a49410e3d46347e9ec5143f81) |
| v3_aggressive | RiskPolicyManager | `upgrade_policy` | `effe124f…66c9` | [✅ View](https://testnet.cspr.live/deploy/effe124f23754b16ed9ce4daa342a14b565f2986fb309983949e29b434bf66c9) |
| pro_30d | SubscriberVault | `open_vault` | `47b96fac…5a7f` | [✅ View](https://testnet.cspr.live/deploy/47b96facf685059f81375335b8298544854420f378b6a1c7a5a03d8764dd5a7f) |
| basic_7d | SubscriberVault | `open_vault` | `5e09a0fc…e25e` | [✅ View](https://testnet.cspr.live/deploy/5e09a0fcc9ccc8aab086be601925d4851a63e5c2cf8f887435567a55e43ae25e) |

Breakdown: 3 AuditTrail · 3 RiskOracle · 4 SentinelAlertLog · 2 SentinelRegistry · 2 SentinelCredit · 3 AgentBehaviorIndex · 2 RiskPolicyManager · 2 SubscriberVault

---

## 6 Upgrade Deploys — All Verified SUCCESS

RiskPolicyManager v1→v2 upgrade demo, deployed from secondary account. All 6 verification checks pass. Source: [`proof/upgrade_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/upgrade_hashes.json)

| Step | Deploy Hash | Explorer |
|------|------------|---------|
| v1_install | `0d4ed954…5e6f` | [✅ View](https://testnet.cspr.live/deploy/0d4ed9547854f936df6a3ae44e7a5e4d2853565053b9d324d0882348c6b55e6f) |
| upgrade_policy_on_v1 | `86f93e5c…00f9` | [✅ View](https://testnet.cspr.live/deploy/86f93e5ccb25bc2e563a3b130f048c7b58de4134b210814cb7be2b2530fe00f9) |
| get_current_policy_on_v1 | `2087b49f…4b58` | [✅ View](https://testnet.cspr.live/deploy/2087b49fddf87abe6b78ed24b7139af06c0d65d07ac00b94e5bc1fc533ce4b58) |
| v2_upgrade_add_contract_version | `86ea584a…edd2` | [✅ View](https://testnet.cspr.live/deploy/86ea584af0d6cc4bf9a938f97c9748e6f9a9537e58837599442b7e40b0e4edd2) |
| get_policy_with_reasoning_on_v2 | `b70a4cae…bca7` | [✅ View](https://testnet.cspr.live/deploy/b70a4caed514b41f1f962704626ee408ebf2e87665f95be7ce1276cf5119bca7) |
| get_current_policy_on_v2 | `41d0ec5b…25a8` | [✅ View](https://testnet.cspr.live/deploy/41d0ec5bedd6801486eb2e51b9ce7e605d99017c40b0e866aa772aa196b425a8) |

Upgrade verification checks (all 6 pass — [`proof/upgrade_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/upgrade_hashes.json)):
- ✅ Package has 2 versions
- ✅ v2 adds `get_policy_with_reasoning` entry point
- ✅ v1 entry points preserved in v2
- ✅ Shared state URef (v1 and v2 read same `current_policy`)
- ✅ `get_policy_with_reasoning` call succeeds on v2 (proves shared state)
- ✅ `get_current_policy` call succeeds on v2

---

## x402 Payment Deploy — Verified SUCCESS

1 CSPR SubscriberVault payment via official `@make-software/casper-x402` SDK. Source: [`proof/x402_payment_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/x402_payment_hashes.json)

| Detail | Value |
|--------|-------|
| Deploy hash | `0588e143…5e2c` |
| Amount | 1 CSPR (1,000,000,000 motes) |
| Entry point | `SubscriberVault::open_vault` |
| Explorer | [✅ View](https://testnet.cspr.live/deploy/0588e143d15eebb7004c23052cd3727d7b87c3b120981184eff5abc9b33f5e2c) |
| SDK | `@make-software/casper-x402` v1.0.0 + `casper-js-sdk` v5.0.12 ([`proof/x402_payment_hashes.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/x402_payment_hashes.json)) |

---

## Verification Methodology

All deploys verified via two independent methods ([`scripts/verify_deploys.py`](https://github.com/sodiq-code/vaultwatch/blob/main/scripts/verify_deploys.py)):

1. **RPC verification** — `info_get_deploy` call to `node.testnet.casper.network/rpc` for each deploy hash. Confirms `execution_results` with Success outcome.
2. **Named_keys proof** — For contract installations, verification relies on the deployer account's named_keys containing the contract package hashes. Presence of named_keys is definitive proof of successful contract installation ([`proof/deploy_verification_results.json`](https://github.com/sodiq-code/vaultwatch/blob/main/proof/deploy_verification_results.json)).

---

## Agent Pipeline

7 agents orchestrated by [`pipeline.py`](https://github.com/sodiq-code/vaultwatch/blob/main/pipeline.py) (`run()` method):

```
Event (Casper SSE / CSPR.cloud)
    |
    v
[1] ScannerAgent       ([`agents/scanner_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/scanner_agent.py))    llama-3.1-8b-instant
    Parse, normalize, classify event type
    |
    v
[2] AnomalyAgent       ([`agents/anomaly_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/anomaly_agent.py))     llama-3.3-70b-versatile
    Deep risk reasoning — severity, confidence (0-1)
    |
    v
[3] SelfCorrection     ([`agents/self_correction_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/self_correction_agent.py))  llama-3.3-70b-versatile
    confidence < 0.75 -> re-query (max 2 retries); still low -> discard
    |
    v
[4] RWAAgent           ([`agents/rwa_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/rwa_agent.py))     compound-beta + hybrid feed
    Enrich with real-world asset intelligence (CoinGecko + FRED + mock fallback)
    |
 [4b] SafetyGuard       ([`agents/safety_guard.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/safety_guard.py))     llama-3.3-70b-versatile
    Inline injection/adversarial check (<50ms)
    |
    v
[5] AuditAgent          ([`agents/audit_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/audit_agent.py))    llama-3.1-8b-instant
    Build EAS attestation -> construct Casper deploy TX -> write to AuditTrail
    |
    v
[6] IntelAgent          ([`agents/intel_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/intel_agent.py))    llama-3.1-8b-instant
    Serve findings via REST API + MCP + x402 pay-per-query gate
```

All imports defined in [`agents/__init__.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/__init__.py).

---

## Smart Contracts

8 Rust contracts written with the [Odra framework](https://odra.dev), compiled to bulk-memory-safe WASM, deployed to Casper testnet.

| Contract | Role | Key Entry Point | Source Ref |
|----------|------|-----------------|-----------|
| AuditTrail | Immutable on-chain log of agent actions | `record_finding` | [`contracts/src/audit_trail.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/audit_trail.rs) |
| RiskOracle | Risk scores queryable by any Casper dApp | `update_score` | [`contracts/src/risk_oracle.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_oracle.rs) |
| SentinelCredit | x402 credit ledger for pay-per-query | `deposit` | [`contracts/src/sentinel_credit.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/sentinel_credit.rs) |
| SentinelRegistry | Subscriber registry for push alerts | `register` | [`contracts/src/sentinel_registry.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/sentinel_registry.rs) |
| SentinelAlertLog | Timestamped alert history | `log_alert` | [`contracts/src/sentinel_alert_log.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/sentinel_alert_log.rs) |
| AgentBehaviorIndex | AI agent performance on-chain | `record_decision` | [`contracts/src/agent_behavior_index.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/agent_behavior_index.rs) |
| RiskPolicyManager | Hot-swappable risk thresholds | `upgrade_policy` v1 | [`contracts/src/risk_policy_manager.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_policy_manager.rs) |
| RiskPolicyManager v2 | Upgraded policy + reasoning | `upgrade_policy` v2 | [`contracts/src/risk_policy_manager_v2.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_policy_manager_v2.rs) |
| SubscriberVault | Escrowed prepay balance | `open_vault` | [`contracts/src/subscriber_vault.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/subscriber_vault.rs) |

WASM artifacts: [`contracts/wasm/`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/wasm/) (9 files including v2)

Build:
```bash
cd contracts && cargo odra build --release
```

---

## API & MCP Server

### REST API

[`api/main.py`](https://github.com/sodiq-code/vaultwatch/blob/main/api/main.py) — FastAPI app, 29 endpoint decorators, 20+ active endpoints. OpenAPI docs at `/docs`.

```
GET  /health                       Health check
POST /api/risk/query               Query risk for a protocol
POST /api/risk/detect-anomaly      Detect anomalies
POST /api/rwa/assess               Assess real-world asset risk
POST /api/audit/query              Query on-chain audit trail
POST /api/policy/check             Check policy compliance
POST /api/policy/set               Update risk policy
GET  /api/contracts/{hash}         Get contract state
POST /api/contracts/deploy         Deploy contract to testnet
GET  /api/metrics                  System metrics
GET  /api/agents/status            Agent pipeline status
...and more (see /docs)
```

### MCP Server — 20 Tools

[`vaultwatch_mcp/server.py`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_mcp/server.py) — FastMCP server with 20 tools callable from Claude Desktop:

```python
tools = [
    "get_market_state",         "detect_anomaly",
    "get_rwa_risk",             "query_findings",
    "pay_for_intel",            "get_audit_trail",
    "subscribe_alerts",         "get_agent_trace",
    "get_risk_score",           "stream_events",
    "get_agent_behavior",       "upgrade_policy",
    "get_alert_history",        "register_subscriber",
    "get_subscriber_balance",
    # 5 newer tools
    "agent_attestation",        "reputation_query",
    "x402_subscribe",           "policy_hotswap",
    "behavior_index_lookup",
]
```

### x402 Integration

Official `@make-software/casper-x402` SDK integration via Node.js helper:
- [`agents/intel_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/intel_agent.py) — `serve_intel_with_x402` method
- [`x402/x402_helper.mjs`](https://github.com/sodiq-code/vaultwatch/blob/main/x402/x402_helper.mjs) — Bridge between Python FastAPI and JS SDK
- [`x402/vaultwatch-x402.ts`](https://github.com/sodiq-code/vaultwatch/blob/main/x402/vaultwatch-x402.ts) — Real x402 v2 payment implementation

---

## Live Dashboard

**https://vaultwatch-dashboard-v5.vercel.app**

React/Vite dashboard with real data integrations:

| Panel | Data Source | Component |
|-------|-----------|-----------|
| Risk Intelligence | Groq API | [`dashboard/src/components/RiskPanel.jsx`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/components/RiskPanel.jsx) |
| Anomaly Detection | Groq API | [`dashboard/src/components/AnomalyPanel.jsx`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/components/AnomalyPanel.jsx) |
| RWA Assessment | Groq API | [`dashboard/src/components/RWAPanel.jsx`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/components/RWAPanel.jsx) |
| Audit Log | Casper testnet | [`dashboard/src/components/AuditPanel.jsx`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/components/AuditPanel.jsx) |
| Live Feed | Pipeline simulation | [`dashboard/src/components/LiveFeed.jsx`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/components/LiveFeed.jsx) |
| Chain Status | cspr.cloud + CoinGecko | [`dashboard/src/components/ChainStatus.jsx`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/components/ChainStatus.jsx) |
| Attestations | On-chain | [`dashboard/src/components/AttestationsPanel.jsx`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/components/AttestationsPanel.jsx) |
| x402 Payments | On-chain | [`dashboard/src/components/X402PaymentsPanel.jsx`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/components/X402PaymentsPanel.jsx) |
| Agent Pipeline | OTel | [`dashboard/src/components/AgentPipelinePanel.jsx`](https://github.com/sodiq-code/vaultwatch/blob/main/dashboard/src/components/AgentPipelinePanel.jsx) |

---

## Test Suite

481 test definitions across 39 files. E2E tests require opt-in (`--run-e2e`).

```bash
pytest tests/ -v
```

| Directory | Files | Test Definitions | Notes |
|-----------|-------|-----------------|-------|
| `tests/unit/` | 14 | 195 | Agents, SDK, safety guard, contracts, RWA-MCP readers |
| `tests/integration/` | 16 | 196 | API endpoints, MCP tools, pipeline, payable contracts |
| `tests/e2e/` | 8 | 75 | Real Casper testnet reads (opt-in `--run-e2e`) |
| `tests/demo/` | 1 | 6 | End-to-end scenario walkthroughs |
| **Total** | **39** | **481** | |

---

## Quickstart

### Prerequisites

- Python 3.11+ · Node.js 18+ · Groq API key ([console.groq.com](https://console.groq.com)) · Docker (optional)

### Install

```bash
git clone https://github.com/sodiq-code/vaultwatch
cd vaultwatch
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Set GROQ_API_KEY (required)
# All other services run in mock mode by default
# RPC endpoint: CASPER_NODE_URL=https://node.testnet.casper.network/rpc
```

### Run

```bash
# Docker (all services)
docker-compose up
# API: http://localhost:8000 · Dashboard: http://localhost:5173 · MCP: http://localhost:3000

# Or individually
python pipeline.py                               # Agent pipeline
uvicorn api.main:app --reload --port 8000        # REST API
python vaultwatch_mcp/server.py                  # MCP server (20 tools)
cd dashboard && npm install && npm run dev       # Dashboard
```

---

## Key Differentiators

| Feature | Description | Source Ref |
|---------|-------------|-----------|
| AgentBehaviorIndex | Every AI agent's decisions scored on-chain — confidence, correction rates, false positive history | [`contracts/src/agent_behavior_index.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/agent_behavior_index.rs) |
| RiskPolicyManager hot-swap | Risk thresholds upgradable without contract redeployment; v1→v2 upgrade verified on testnet | [`contracts/src/risk_policy_manager.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_policy_manager.rs), [`contracts/src/risk_policy_manager_v2.rs`](https://github.com/sodiq-code/vaultwatch/blob/main/contracts/src/risk_policy_manager_v2.rs) |
| Self-Correction Loop | Low-confidence findings trigger re-query (max 2 retries); still low -> discarded | [`agents/self_correction_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/self_correction_agent.py) |
| Hybrid RWA Feed | CoinGecko (commodities) + FRED (bonds/credit) + mock fallback (real estate) with provenance tracking | [`agents/rwa_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/rwa_agent.py) |
| x402 Pay-per-Query | SubscriberVault holds prepaid CSPR; each MCP query deducts on-chain balance via official SDK | [`agents/intel_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/intel_agent.py), [`x402/x402_helper.mjs`](https://github.com/sodiq-code/vaultwatch/blob/main/x402/x402_helper.mjs) |
| OpenTelemetry | Every agent span exported via single env var to any OTel sink | [`pipeline.py`](https://github.com/sodiq-code/vaultwatch/blob/main/pipeline.py) |
| SafetyGuard Inline | Safety classifier on every query, blocking prompt injection | [`agents/safety_guard.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/safety_guard.py) |
| EAS Attestations | AuditAgent builds EAS-style attestation proving data retrieval provenance | [`agents/audit_agent.py`](https://github.com/sodiq-code/vaultwatch/blob/main/agents/audit_agent.py) |

---

## Domain-Specific MCP Server — `vaultwatch-rwa-mcp`

A focused MCP server wrapping the 8 RWA/risk contracts for any LLM agent (Claude Desktop, Cursor, Continue). See [`vaultwatch_rwa_mcp/README.md`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/README.md).

- 39 tools — every contract entry point + field read
- 3 resources — `rwa://contracts`, `rwa://policy/current`, `rwa://audit/count`
- 4 prompts — explain contracts, audit summary, risk assessment, policy review
- Reads — free `query_global_state` with Odra storage-key derivation + bytesrepr decoders
- Writes — REAL deploys via CSPR.click AgentWallet; payable `open_vault` via `@make-software/casper-x402`

```bash
python -m vaultwatch_rwa_mcp.server           # stdio transport
python -m vaultwatch_rwa_mcp.server --list-tools  # introspection
```

---

## Project Structure

```
vaultwatch/
  agents/
    scanner_agent.py            # Event parsing + classification
    anomaly_agent.py            # Risk scoring (llama-3.3-70b)
    self_correction_agent.py    # Quality gate, retry loop
    rwa_agent.py                # RWA enrichment (hybrid feed)
    safety_guard.py             # Prompt injection filter
    audit_agent.py              # TX construction + EAS attestation
    intel_agent.py              # API serving + x402 gate
    __init__.py                 # Pipeline imports
  contracts/
    src/                        # 9 Rust source files (8 + v2)
    wasm/                       # 9 compiled WASM artifacts
  api/
    main.py                     # FastAPI (29 endpoints)
    casper_rpc.py               # RPC client
    security.py                 # Auth + rate limiting
  vaultwatch_mcp/
    server.py                   # FastMCP — 20 tools
  vaultwatch_rwa_mcp/
    server.py                   # FastMCP — 39 tools (domain-specific)
    readers.py                  # Odra-aware on-chain readers
    writers.py                  # CSPR.click AgentWallet wrappers
  x402/
    x402_helper.mjs             # Node.js bridge to official SDK
    vaultwatch-x402.ts          # x402 v2 payment implementation
  dashboard/
    src/                        # React/Vite frontend (9 panels)
  streaming/
    sidecar_client.py           # Casper Sidecar SSE client
  sdk/
    vaultwatch/client.py        # Async HTTP client
  tests/
    unit/                       # 195 test definitions
    integration/                # 196 test definitions
    e2e/                        # 75 test definitions (opt-in)
    demo/                       # 6 test definitions
  scripts/
    verify_deploys.py           # On-chain verification script
    deploy_contracts_live.py    # Live deployment script
    demo_upgrade_policy.py      # Policy hot-swap demo
    demo_x402_payment.mjs       # x402 payment demo
  proof/
    deploy_verification_results.json   # Contract installation verification
    interaction_hashes.json            # 21 interaction deploy hashes
    upgrade_hashes.json                # 6 upgrade deploy hashes + checks
    x402_payment_hashes.json           # x402 payment verification
    transaction_hashes_live.json       # 8 contract deploy hashes
  pipeline.py                  # Main agent pipeline orchestrator
  docker-compose.yml
  Dockerfile
  requirements.txt
```

---

## Configuration

```bash
# Required
GROQ_API_KEY=your_key                  # Free at console.groq.com

# Casper Network
CASPER_NODE_URL=https://node.testnet.casper.network/rpc
CASPER_CHAIN_NAME=casper-test

# CSPR.cloud (live block data + contract state queries)
CSPR_CLOUD_API_URL=https://api.testnet.cspr.cloud
CSPR_CLOUD_API_KEY=your_key

# Sidecar SSE (real-time event streaming)
CASPER_SIDECAR_URL=http://127.0.0.1:18888/events/main

# x402
X402_PAYMENT_AMOUNT=1000000            # motes

# API
API_HOST=0.0.0.0
API_PORT=8000

# Dashboard
VITE_API_URL=http://localhost:8000

# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=vaultwatch

# Mock mode (safe for CI)
CASPER_MOCK=true
```

---

## Links

| Resource | URL |
|----------|-----|
| Repository | https://github.com/sodiq-code/vaultwatch |
| Demo Video | https://youtu.be/Jmg_MFSxwdE |
| Live Dashboard | https://vaultwatch-dashboard-v5.vercel.app |
| Deployer Account (main) | [testnet.cspr.live](https://testnet.cspr.live/account/0203cd257525b180a32cab4efc0d9d9a365bf9bc1b8d2e76ebfb9186a4eeb23bace7) |
| Deployer Account (secondary) | [testnet.cspr.live](https://testnet.cspr.live/account/02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db) |
| Casper Testnet Explorer | https://testnet.cspr.live/ |
| Casper RPC | https://node.testnet.casper.network/rpc |
| Domain MCP Server | [`vaultwatch-rwa-mcp`](https://github.com/sodiq-code/vaultwatch/blob/main/vaultwatch_rwa_mcp/README.md) |
| Odra Framework | https://odra.dev/ |
| Groq Console | https://console.groq.com/ |
| CSPR.cloud API | https://docs.cspr.cloud/ |
| Reputation Formula | [`docs/REPUTATION_FORMULA.md`](https://github.com/sodiq-code/vaultwatch/blob/main/docs/REPUTATION_FORMULA.md) |
| Deployment Guide | [`DEPLOYMENT_GUIDE.md`](https://github.com/sodiq-code/vaultwatch/blob/main/DEPLOYMENT_GUIDE.md) |
| Contract Audit | [`CONTRACT_AUDIT.md`](https://github.com/sodiq-code/vaultwatch/blob/main/CONTRACT_AUDIT.md) |

---

## License

MIT License · Copyright (c) 2026 Sodiq Jimoh — see [LICENSE](LICENSE)

---

**Author: [Sodiq Jimoh](https://github.com/sodiq-code) · Network: Casper Testnet (`casper-test`) · License: MIT**
