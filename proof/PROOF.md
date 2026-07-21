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

---

## 10. Critical Fix 2 — Casper-Native Upgradable Contracts (`add_contract_version`) ✅ VERIFIED ON-CHAIN

Closes the review's Critical Fix 2: the "upgradable contracts" headline is now
backed by a **real** `storage::add_contract_version()` upgrade, not a Var
overwrite. A **v2** of `RiskPolicyManager` (`contracts/src/risk_policy_manager_v2.rs`)
is installed as a new version under the **same contract package** as v1, with
**shared state** and a **new entry point** `get_policy_with_reasoning`.

**Status: FULLY VERIFIED ON-CHAIN on Casper Testnet (`casper-test`) on July 21, 2026.**
The complete upgrade lifecycle (v1 install → set policy → v2 upgrade via
`add_contract_version()` → call v1 & v2 entry points → verify shared state) was
executed and verified with **6/6 on-chain checks passing** and **6/6 deploys
verified-success**. Deployer account: `02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db`
(account hash `0debd9ab6e903b6d3269f7c9ceaf28320e3b91209e1a1080fd9ddf097d3dbd68`).

**Build artifact:** `contracts/wasm/RiskPolicyManagerV2.wasm` (135.2 KB,
bulk-memory-clean, exports `call` + all v1 entry points + `get_policy_with_reasoning`
+ `upgrade` + `migrate_events`).

**Upgrade mechanism:** v2 Wasm deployed as session code with `odra_cfg_is_upgrade=true`
+ `odra_cfg_package_hash_to_upgrade=<v1 package hash>`; Odra's generated `call()`
invokes `storage::add_contract_version(pkg, entry_points, named_keys, {})`
on-chain. Full design + build + verification matrix:
[`docs/UPGRADE_DEMO.md`](../docs/UPGRADE_DEMO.md).

### 10.1 The Verified Upgrade Lifecycle (6 deploys, all on Casper Testnet)

| # | Step | Deploy Hash | Status |
|---|------|-------------|--------|
| 1 | INSTALL v1 `RiskPolicyManager` (fresh, upgradable package) | `0d4ed9547854f936df6a3ae44e7a5e4d2853565053b9d324d0882348c6b55e6f` | [✅ verified](https://testnet.cspr.live/deploy/0d4ed9547854f936df6a3ae44e7a5e4d2853565053b9d324d0882348c6b55e6f) |
| 2 | CALL `upgrade_policy` on v1 (sets the shared-state baseline) | `86f93e5ccb25bc2e563a3b130f048c7b58de4134b210814cb7be2b2530fe00f9` | [✅ verified](https://testnet.cspr.live/deploy/86f93e5ccb25bc2e563a3b130f048c7b58de4134b210814cb7be2b2530fe00f9) |
| 3 | CALL `get_current_policy` on v1 (proves v1 works) | `2087b49fddf87abe6b78ed24b7139af06c0d65d07ac00b94e5bc1fc533ce4b58` | [✅ verified](https://testnet.cspr.live/deploy/2087b49fddf87abe6b78ed24b7139af06c0d65d07ac00b94e5bc1fc533ce4b58) |
| 4 | **UPGRADE to v2 via `add_contract_version()`** | `86ea584af0d6cc4bf9a938f97c9748e6f9a9537e58837599442b7e40b0e4edd2` | [✅ verified](https://testnet.cspr.live/deploy/86ea584af0d6cc4bf9a938f97c9748e6f9a9537e58837599442b7e40b0e4edd2) |
| 5 | CALL `get_policy_with_reasoning` on v2 (new EP + shared-state proof) | `b70a4caed514b41f1f962704626ee408ebf2e87665f95be7ce1276cf5119bca7` | [✅ verified](https://testnet.cspr.live/deploy/b70a4caed514b41f1f962704626ee408ebf2e87665f95be7ce1276cf5119bca7) |
| 6 | CALL `get_current_policy` on v2 (v1 EP on upgraded superset) | `41d0ec5bedd6801486eb2e51b9ce7e605d99017c40b0e866aa772aa196b425a8` | [✅ verified](https://testnet.cspr.live/deploy/41d0ec5bedd6801486eb2e51b9ce7e605d99017c40b0e866aa772aa196b425a8) |

**Contract package (owned by deployer):** `417f5f7268acd956c4ce75fc1714f74f8a6bc819e0ad801fc60dc425d729f522`
- v1 contract hash: `8f9db53534efda3c94e40da3d69b1dcc06f32aa2a344e17d25d7142ffb13f16e` (disabled after upgrade)
- v2 contract hash: `43fbabdfa68dfe9a94e14ff2220d916ba785bb0615b84efd030d302c8adc3f8a` (active = latest)
- shared `state` URef: `uref-08fe1b7b61591bb1020673607118754706fe5ceb3c5b7068a08e594f4df25c9c-007`

**Gas accounting (upgrade deploy #4):** payment 300 CSPR → consumed **157.62 CSPR** → refunded 106.79 CSPR.
Total gas consumed across all 6 deploys: **~338.94 CSPR** (deployer funded with 5000 CSPR).

### 10.2 Verification Matrix — 6/6 PASS

Run by `scripts/demo_upgrade_full.py` (full report: [`proof/upgrade_hashes.json`](upgrade_hashes.json)):

| # | Check | How | Result |
|---|-------|-----|--------|
| 1 | Package has 2 versions | `query_global_state` on `hash-<package>` → `ContractPackage.versions[]` | ✅ versions=[1, 2], v1 disabled |
| 2a | v2 exposes `get_policy_with_reasoning` | `query_global_state` on `hash-<v2_contract>` → `entry_points[]` | ✅ present (9 EPs total) |
| 2b | v1 entry points preserved in v2 | same query | ✅ all 6 v1 EPs ⊆ v2 EPs |
| 3 | Shared state (structural) | compare v2's `state` URef to v1's `state` URef | ✅ equal (`uref-08fe1b7b…c9c-007`) |
| 4 | `get_policy_with_reasoning` works on v2 (functional shared-state proof) | stored-contract call on v2 | ✅ success (`error_message == null`) |
| 5 | v1 entry point still works on upgraded package | call `get_current_policy` on v2 | ✅ success |

**Why check 4 is a functional shared-state proof:** `get_policy_with_reasoning`
reads `current_policy` via `get_or_revert_with(ExecutionError::User(1))`. If v2
could NOT read v1's state (i.e. the `state` dictionary were not shared), this
call would revert with `User(1)`. Its success proves v2 reads v1's written state.

**Why check 3 is a structural shared-state proof:** Odra stores all module state
in a single `state` dictionary (a named key on the contract holding the seed
URef). v2 keeps v1's struct fields in the **same order** (`current_policy`,
`policy_history`, `owner`), so v2 reads v1's state via the identical dictionary
keys. The `state` URef being byte-identical between v1 and v2 is the on-chain
structural confirmation.

### 10.3 Definitive Proof `add_contract_version()` Ran (execution effects of deploy #4)

Inspecting the upgrade deploy's execution_result.effects (33 transforms) shows:
- Multiple **writes to the package hash** `417f5f72…` (adding version 2,
  disabling version 1).
- A **new contract entity** write at `hash-43fbabdf…` (the v2 contract) backed
  by a new **wasm** at `hash-fe1bc2e0…` (the v2 bytecode).
- A **write to the v1 contract** `hash-8f9db535…` (marked disabled).
- A **message-topic-entity** write for the v2 contract (`message-topic-entity-contract-43fbabdf…`).

This is exactly the on-chain footprint of `storage::add_contract_version(package_hash,
entry_points, named_keys, message_topics)`.

### 10.4 Reproduce the on-chain upgrade + verification

```bash
# The deployer secret key (Account 2) is at vaultwatch/secret_key.pem.
# (Account 2 is the package owner; the upgrade requires the access URef that
#  Odra stores under <package_hash_key_name>_access_token in the deployer's
#  named keys — so the same account must install v1 AND upgrade to v2.)

python3 scripts/demo_upgrade_full.py
# → installs v1 (fresh upgradable package), sets a known policy, upgrades to
#   v2 via add_contract_version(), calls v1 + v2 entry points, verifies all
#   6 on-chain checks, writes proof/upgrade_hashes.json with every deploy hash.
```

Full design, build pipeline, mechanism, and on-chain results:
[`docs/UPGRADE_DEMO.md`](../docs/UPGRADE_DEMO.md).
---

## 11. Critical Fix 3 — Real x402 v2 Payment Flow ✅ VERIFIED ON-CHAIN

Closes the review's Critical Fix 3: the x402 payment protocol is now a **REAL**
end-to-end flow on Casper testnet, not a stub. All four required components are
implemented, tested, and verified:

1. **`@make-software/casper-x402` is installed as a real npm dependency**
   (not a `peerDependency`). See `package.json` (`dependencies.@make-software/casper-x402`)
   and `x402/package.json` (`dependencies`). `@x402/core` (the HTTP transport
   primitives) and `casper-js-sdk` v5 are also real dependencies. Verified:
   `npm ls @make-software/casper-x402 @x402/core casper-js-sdk` resolves to
   `1.0.0`, `2.15.0`, `5.0.12` respectively.

2. **`submitVaultOpenDeploy()` is implemented with `casper-js-sdk`** —
   `x402/x402_helper.mjs` exposes the `submit-vault-payment` command that builds,
   signs, submits, and on-chain verifies a REAL `SubscriberVault.open_vault()`
   stored-contract deploy via the SDK's `ContractCallBuilder` +
   `PrivateKey.fromPem()` + `account_put_deploy` + `info_get_deploy`.

3. **HTTP 402 middleware is added in FastAPI** — `api/main.py` exposes:
   - `GET /intel/{addr}` — payment-gated resource. Without a `PAYMENT-SIGNATURE`
     header, returns **402** with a real `PAYMENT-REQUIRED` base64 header built
     by `@x402/core/http`'s `encodePaymentRequiredHeader()`. With a valid
     signature, verifies via `@make-software/casper-x402`'s facilitator
     `ExactCasperScheme.verify()` and returns 200 + `PAYMENT-RESPONSE` header.
   - `POST /x402/subscribe` — server-initiated subscribe flow that builds the
     PaymentRequired AND submits the REAL on-chain payment deploy, returning
     the verified deploy hash + the `PAYMENT-RESPONSE` header.
   - `GET /x402/payment-required` — standalone PaymentRequired builder for
     x402 client wallets to discover the payment requirements.
   - `GET /x402/status` — integration status (SDK versions, contract refs,
     plan prices).

4. **A verified payment hash is recorded** — see §11.2 below. The on-chain
   `SubscriberVault.open_vault()` deploy is verified-success
   (`Version2.error_message == null`) on Casper testnet, and the deploy hash
   is carried in the x402 `SettleResponse.transaction` field of the
   `PAYMENT-RESPONSE` header.

**Status: FULLY VERIFIED ON-CHAIN on Casper Testnet (`casper-test`) on July 21, 2026.**
The complete x402 flow (build PaymentRequired → sign + submit
`open_vault()` deploy → verify on-chain → build SettleResponse carrying the
verified deploy hash) was executed and verified. Deployer account:
`02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db`
(account hash `0debd9ab6e903b6d3269f7c9ceaf28320e3b91209e1a1080fd9ddf097d3dbd68`).

### 11.1 Architecture — the x402 v2 flow on Casper

```
Client ──GET /intel/{addr}──────────► VaultWatch API (FastAPI)
Client ◄──402 + PAYMENT-REQUIRED──── VaultWatch API   (@x402/core/http encodePaymentRequiredHeader)
Client ──GET + PAYMENT-SIGNATURE───► VaultWatch API   (@make-software/casper-x402 ExactCasperScheme.verify)
VaultWatch ──open_vault deploy─────► Casper testnet   (casper-js-sdk ContractCallBuilder + PrivateKey.sign)
VaultWatch ──build SettleResponse──► Client (200 + PAYMENT-RESPONSE)
```

The on-chain payment is a `SubscriberVault.open_vault()` stored-contract call
that records `initial_deposit` CSPR as `escrowed_balance` in the subscriber's
vault account (see `contracts/src/subscriber_vault.rs:39`). The deploy is
signed by the vault owner (the deployer account, whose PEM is at
`secret_key.pem`) — `open_vault()` is gated by `assert_vault_owner()`, so the
deployer must own the SubscriberVault contract.

### 11.2 The Verified Payment Hash

| Field | Value |
|-------|-------|
| **Deploy hash** | `0588e143d15eebb7004c23052cd3727d7b87c3b120981184eff5abc9b33f5e2c` |
| **Block hash** | `753289ded7815545d801281b65aa2e6cc26047d6f5e8f13d1c54c939213ccf22` |
| **Timestamp** | `2026-07-21T18:48:08.326Z` |
| **Gas cost** | 5 CSPR (5_000_000_000 motes) |
| **Execution result** | `Version2.error_message == null` → **SUCCESS** |
| **Effects** | 12 transforms (writes to SubscriberVault contract + package + balance hold) |
| **testnet.cspr.live link** | [view deploy](https://testnet.cspr.live/deploy/0588e143d15eebb7004c23052cd3727d7b87c3b120981184eff5abc9b33f5e2c) |

**SubscriberVault contract (fresh, owned by Account 2):**
- contract hash: `0d41615944471f18c7ac75725901be7eeff26a0c168e1a3387db2449256b1f8c`
- package hash: `d1cb42e21855b938d7e189186bb13751fc4d2523da53e1482027595a0f3463bf`
- install deploy: `8b4ba50c91c075792fb10aa0a116234fcdd7d2fddcc99772b8e693e67e339c29`
  ([view](https://testnet.cspr.live/deploy/8b4ba50c91c075792fb10aa0a116234fcdd7d2fddcc99772b8e693e67e339c29))

> **Why a fresh SubscriberVault?** The original SubscriberVault (hash
> `9a93db9c…`, package `68c4b7cc…`) was installed by Account 1 (now drained).
> `open_vault()` is gated by `assert_vault_owner()` — only the installer can
> call it. To make Account 2 the vault owner (so it can submit real x402
> payments), a fresh SubscriberVault was installed with Account 2's key via
> `scripts/casper_install.cjs` (same fresh-install path used in §10 for
> RiskPolicyManager). The fresh contract is owned by Account 2 and is the
> target of all x402 payment deploys.

### 11.3 The x402 v2 PaymentRequired object (built by the official SDK)

```json
{
  "x402Version": 2,
  "error": "PAYMENT-SIGNATURE header is required",
  "resource": {
    "url": "https://api.vaultwatch.io/intel/subscriber-vaultwatch-demo-001",
    "description": "VaultWatch standard subscription — 1 CSPR escrowed",
    "mimeType": "application/json",
    "serviceName": "VaultWatch",
    "tags": ["defi", "risk-intelligence", "casper"]
  },
  "accepts": [{
    "scheme": "exact",
    "network": "casper:casper-test",
    "asset": "d1cb42e21855b938d7e189186bb13751fc4d2523da53e1482027595a0f3463bf",
    "amount": "1000000000",
    "payTo": "000debd9ab6e903b6d3269f7c9ceaf28320e3b91209e1a1080fd9ddf097d3dbd68",
    "maxTimeoutSeconds": 300,
    "extra": {
      "name": "VaultWatch SubscriberVault",
      "version": "1",
      "description": "Escrowed CSPR credit for VaultWatch intelligence queries"
    }
  }]
}
```

The `PAYMENT-REQUIRED` HTTP response header is the base64 encoding of this
JSON, produced by `@x402/core/http`'s `encodePaymentRequiredHeader()` — NOT a
hand-rolled base64. Constants come from `@make-software/casper-x402`:
`NETWORK_CASPER_TESTNET` (`"casper:casper-test"`), `SCHEME_EXACT` (`"exact"`),
`NetworkConfigs[CASPER_TESTNET].rpcUrl`.

### 11.4 The x402 v2 SettleResponse (carrying the verified deploy hash)

```json
{
  "success": true,
  "payer": "000debd9ab6e903b6d3269f7c9ceaf28320e3b91209e1a1080fd9ddf097d3dbd68",
  "transaction": "0588e143d15eebb7004c23052cd3727d7b87c3b120981184eff5abc9b33f5e2c",
  "network": "casper:casper-test",
  "amount": "1000000000",
  "extensions": {
    "casperDeployLink": "https://testnet.cspr.live/deploy/0588e143d15eebb7004c23052cd3727d7b87c3b120981184eff5abc9b33f5e2c",
    "contract": "SubscriberVault",
    "entryPoint": "open_vault"
  }
}
```

The `PAYMENT-RESPONSE` HTTP response header is the base64 encoding of this
JSON, produced by `@x402/core/http`'s `encodePaymentResponseHeader()`. The
`transaction` field is the verified on-chain Casper deploy hash — this is the
"verified payment hash" required by Critical Fix 3.

### 11.5 SDK versions (all real npm dependencies)

| Package | Version | Role |
|---------|---------|------|
| `@make-software/casper-x402` | `1.0.0` | Official Casper x402 scheme — `ExactCasperScheme` (EIP-712 / CEP-3009), `NETWORK_CASPER_TESTNET`, `SCHEME_EXACT`, `NetworkConfigs`, `toFacilitatorCasperSigner` |
| `@x402/core` | `2.15.0` | x402 v2 transport primitives — `encodePaymentRequiredHeader`, `encodePaymentResponseHeader`, `decodePaymentSignatureHeader` |
| `casper-js-sdk` | `5.0.12` | Casper-2.x-compatible deploy signing — `ContractCallBuilder`, `PrivateKey`, `Args`, `CLValue`, `RpcClient`, `HttpHandler` |

### 11.6 Reproduce the on-chain x402 payment

```bash
# The deployer secret key (Account 2) is at vaultwatch/secret_key.pem.
# Account 2 owns the fresh SubscriberVault (contract hash 0d416159…, package
# hash d1cb42e2…). The x402 payment deploy calls open_vault() on this contract.

# 1. Verify the SDKs are installed as real dependencies:
npm ls @make-software/casper-x402 @x402/core casper-js-sdk

# 2. Run the end-to-end live verification script (builds PaymentRequired,
#    submits + verifies the open_vault() deploy, builds SettleResponse,
#    writes proof/x402_payment_hashes.json):
node scripts/demo_x402_payment.mjs

# 3. Inspect the proof artifact:
cat proof/x402_payment_hashes.json

# 4. Verify the deploy on-chain (independent of the SDK):
curl -s -X POST https://node.testnet.casper.network/rpc \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"info_get_deploy",
       "params":{"deploy_hash":"0588e143d15eebb7004c23052cd3727d7b87c3b120981184eff5abc9b33f5e2c"}}' \
  | python3 -c "import json,sys; r=json.load(sys.stdin)['result']; print('error_message:', r['execution_info']['execution_result']['Version2']['error_message']); print('cost (motes):', r['execution_info']['execution_result']['Version2']['cost'])"
# → error_message: None
# → cost (motes): 5000000000

# 5. Start the FastAPI server and exercise the 402 flow:
uvicorn api.main:app --host 0.0.0.0 --port 8000 &
curl -i http://localhost:8000/intel/casper_swap_protocol
# → HTTP/1.1 402 Payment Required
# → PAYMENT-REQUIRED: eyJ4NDAyVmVyc2lvbiI6Miwi...
curl -i http://localhost:8000/x402/status
# → HTTP/1.1 200 OK  (integration status + SDK versions)
```

### 11.7 Files touched by Critical Fix 3

| File | Role |
|------|------|
| `x402/package.json` | Promoted `@make-software/casper-x402`, `@x402/core`, `casper-js-sdk` from `peerDependencies` to real `dependencies` |
| `x402/x402_helper.mjs` | The bridge between Python FastAPI and the JS x402 SDKs. Four commands: `encode-payment-required`, `verify-payment-signature`, `submit-vault-payment`, `build-settle-response`. Uses ESM with `import * as casperSdk from 'casper-js-sdk'` + `.default` destructure (the only interop path that works for both the CJS-only casper-js-sdk and the ESM-only @make-software/casper-x402). |
| `x402/vaultwatch-x402.ts` | TypeScript wrapper class with the same `submitVaultOpenDeploy()` method, updated for the v5 SDK API (`RpcClient` + `HttpHandler`, `newCLUint64`). |
| `api/main.py` | FastAPI 402 middleware + `/intel/{addr}`, `/x402/subscribe`, `/x402/payment-required`, `/x402/status` endpoints. Shells out to `x402/x402_helper.mjs` via `asyncio.create_subprocess_exec`. |
| `scripts/demo_x402_payment.mjs` | End-to-end live verification script. Builds PaymentRequired, submits + verifies the `open_vault()` deploy, builds SettleResponse, writes `proof/x402_payment_hashes.json`. |
| `proof/x402_payment_hashes.json` | The proof artifact: full PaymentRequired + on-chain deploy hash + SettleResponse + PAYMENT-REQUIRED / PAYMENT-RESPONSE headers. |
| `proof/PROOF.md` (this section) | The human-readable proof referencing the verified payment hash. |

### 11.8 Official resources used (per hackathon detail)

Per https://dorahacks.io/hackathon/casper-agentic-buildathon-finals/detail, the
officially sanctioned resources for x402 are:
- **x402** (HTTP-native payment protocol) — https://github.com/x402-foundation/x402
- **`@make-software/casper-x402`** (Casper x402 scheme) — https://www.npmjs.com/package/@make-software/casper-x402
- **`casper-js-sdk` v5** (Casper-2.x-compatible deploy signing) — https://github.com/casper-network/casper-js-sdk
- **Casper Testnet RPC** — https://node.testnet.casper.network/rpc
- **testnet.cspr.live** (deploy viewer) — https://testnet.cspr.live/deploy/0588e143d15eebb7004c23052cd3727d7b87c3b120981184eff5abc9b33f5e2c
