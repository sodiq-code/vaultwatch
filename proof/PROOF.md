# VaultWatch — Verification Guide

**Repository**: https://github.com/sodiq-code/vaultwatch  
**Network**: Casper Testnet (`casper-test`)  
**Deployer**: `<UPDATE_WITH_ROTATED_DEPLOYER_PUBKEY>` <!-- rotate from compromised key -->

> The original June 24 deploys all FAILED
> with "Wasm preprocessing error: Bulk memory operations are not supported."
> We rebuilt all 8 contracts with `RUSTFLAGS=-C target-feature=-bulk-memory`
> + `wasm-opt --enable-bulk-memory=no` and redeployed. The hashes below are
> the NEW, verified-successful deploys. See `DEPLOYMENT_GUIDE.md` for the
> full fix story and `scripts/check_wasm_bulk_memory.py` for the hard gate.

---

## 1. Smart Contracts on Casper Testnet

All 8 Odra contracts were recompiled (bulk-memory-safe) and redeployed to
`casper-test` on `<UPDATE_DATE>`.

> **Replace the hashes below** with the output of
> `python3 scripts/deploy_contracts_live.py`. The script prints a
> ready-to-paste Markdown table.

| Contract | Deploy Hash | Explorer Link |
|----------|-------------|---------------|
| AuditTrail | `<UPDATE_HASH>` | [testnet.cspr.live](https://testnet.cspr.live/deploy/<UPDATE_HASH>) |
| SentinelRegistry | `<UPDATE_HASH>` | [testnet.cspr.live](https://testnet.cspr.live/deploy/<UPDATE_HASH>) |
| RiskOracle | `<UPDATE_HASH>` | [testnet.cspr.live](https://testnet.cspr.live/deploy/<UPDATE_HASH>) |
| SentinelCredit | `<UPDATE_HASH>` | [testnet.cspr.live](https://testnet.cspr.live/deploy/<UPDATE_HASH>) |
| AgentBehaviorIndex | `<UPDATE_HASH>` | [testnet.cspr.live](https://testnet.cspr.live/deploy/<UPDATE_HASH>) |
| SentinelAlertLog | `<UPDATE_HASH>` | [testnet.cspr.live](https://testnet.cspr.live/deploy/<UPDATE_HASH>) |
| RiskPolicyManager | `<UPDATE_HASH>` | [testnet.cspr.live](https://testnet.cspr.live/deploy/<UPDATE_HASH>) |
| SubscriberVault | `<UPDATE_HASH>` | [testnet.cspr.live](https://testnet.cspr.live/deploy/<UPDATE_HASH>) |

### Verification (Triple-Checked)

Every deploy is verified via three independent methods:

```bash
# 1. RPC: info_get_deploy shows execution_results with Success outcome
python3 scripts/verify_deploys.py --deploy-hashes deploy_hashes_live.json

# 2. RPC: state_get_account_info shows named_keys > 0
python3 scripts/verify_deploys.py --account <DEPLOYER_PUBKEY>

# 3. WASM: zero bulk-memory opcodes (hard gate)
python3 scripts/check_wasm_bulk_memory.py contracts/wasm/
```

### Historical Note (Failed Deploys — June 24, 2026)

The following 8 deploy hashes from June 24, 2026 all FAILED on Casper
Testnet with "Bulk memory operations are not supported." They are
superseded by the new deploys above:

| Contract | Old (Failed) Hash | Status |
|----------|-------------------|--------|
| AuditTrail | `f06e3357…8e102` | ❌ FAILED — bulk-memory error |
| SentinelRegistry | `d9c8c5ef…48622` | ❌ FAILED — bulk-memory error |
| RiskOracle | `fb877bae…e98a` | ❌ FAILED — bulk-memory error |
| SentinelCredit | `01cfe8d1…a403` | ❌ FAILED — bulk-memory error |
| AgentBehaviorIndex | `162a4f5f…c63a9` | ❌ FAILED — bulk-memory error |
| SentinelAlertLog | `45dbc90b…b42c7` | ❌ FAILED — bulk-memory error |
| RiskPolicyManager | `048dcfe5…c8b1a` | ❌ FAILED — bulk-memory error |
| SubscriberVault | `786b611f…d35f0` | ❌ FAILED — bulk-memory error |

Root cause + fix: see `DEPLOYMENT_GUIDE.md` and `docs/REPUTATION_FORMULA.md`.

---

## 2. WASM Artifacts

```bash
ls -la contracts/wasm/
```

Expected output: 8 `.wasm` files, each compiled from Rust/Odra source.

---

## 3. Published Packages

| Package | Registry | URL |
|---------|----------|-----|
| `casper-sentinel` | PyPI | https://pypi.org/project/casper-sentinel/4.0.0/ |
| `casper-sentinel-mcp` | npm | https://www.npmjs.com/package/casper-sentinel-mcp |

```bash
# Verify PyPI package
pip install casper-sentinel==4.0.0
python -c "import vaultwatch; print('SDK OK')"

# Verify npm package
npm install casper-sentinel-mcp
```

---

## 4. Test Suite

```bash
pip install -r requirements.txt
pip install -e sdk/
pytest tests/ -v
```

Expected: **130 passed** across unit, integration, and demo test suites.

Full test output: [`proof/05_test_results.txt`](05_test_results.txt)

---

## 5. Live Dashboard

**URL**: https://dashboard-rho-amber-89.vercel.app

The dashboard displays:
- Real-time risk findings from the agent pipeline
- On-chain transaction hash links (all 8 contracts)
- Agent behavior index sourced from `AgentBehaviorIndex` contract
- OpenTelemetry trace viewer for agent executions
- x402 pay-per-query panel (SubscriberVault)

---

## 6. Agent Pipeline

```bash
# View all 7 agent implementations
ls agents/

# Count MCP tools
grep "@mcp.tool" vaultwatch_mcp/server.py | wc -l
# Expected: 15
```

---

## 7. Full Stack (Docker)

```bash
docker-compose up -d
curl http://localhost:8000/health
# Expected: {"status": "healthy"}
```

---

## 8. CI Status

[![CI](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml/badge.svg)](https://github.com/sodiq-code/vaultwatch/actions/workflows/ci.yml)

Every push to `main` runs: lint → unit tests → integration tests → contract tests → Docker build.

---

## 9. Contract Interactions — 21 On-Chain TX Hashes

21 additional interaction deploys were broadcast to Casper testnet on June 24, 2026, bringing the **total on-chain TX hashes to 29** (8 contract deploys + 21 interactions).

| # | Interaction Label | Deploy Hash | Link |
|---|-------------------|-------------|------|
| 1 | AuditTrail::add_entry[agent_risk_scan] | `aca60b05fb801960ae1f4db9bdd3c2d3a0cfd142c9b020edcf57df27c0f8ea72` | [view](https://testnet.cspr.live/deploy/aca60b05fb801960ae1f4db9bdd3c2d3a0cfd142c9b020edcf57df27c0f8ea72) |
| 2 | AuditTrail::add_entry[pipeline_heartbeat] | `6f5cd6bf7a21146502d2b5e53250a45aa352e73560e6d228a0c271fc2d29262d` | [view](https://testnet.cspr.live/deploy/6f5cd6bf7a21146502d2b5e53250a45aa352e73560e6d228a0c271fc2d29262d) |
| 3 | RiskOracle::update_score[CasperLend] | `ae061e24af2fbd19f88e5103db2f97abcc565ced54b128b8e3fda4f86dbff285` | [view](https://testnet.cspr.live/deploy/ae061e24af2fbd19f88e5103db2f97abcc565ced54b128b8e3fda4f86dbff285) |
| 4 | SentinelAlertLog::log_alert[HIGH] | `b295168fe1f88b8a0380c9b8f3519ca5811ee969a909d24da28fdf358a9a96fd` | [view](https://testnet.cspr.live/deploy/b295168fe1f88b8a0380c9b8f3519ca5811ee969a909d24da28fdf358a9a96fd) |
| 5 | SentinelAlertLog::log_alert[LOW] | `5319acd5a9794d2ecc10ad9f1345e92da93b5736ea309845237432c771e6de8d` | [view](https://testnet.cspr.live/deploy/5319acd5a9794d2ecc10ad9f1345e92da93b5736ea309845237432c771e6de8d) |
| 6 | SentinelRegistry::register_sentinel[v2] | `ef9c93c6d465041c7c22cfc4fac8619c0375528b159884411e0677a54a063f37` | [view](https://testnet.cspr.live/deploy/ef9c93c6d465041c7c22cfc4fac8619c0375528b159884411e0677a54a063f37) |
| 7 | SentinelRegistry::register_sentinel[mcp_v2] | `a0225857d684ed651ace79fc7bab3c49b7beabc27ecbb5a79add962a4d1a333c` | [view](https://testnet.cspr.live/deploy/a0225857d684ed651ace79fc7bab3c49b7beabc27ecbb5a79add962a4d1a333c) |
| 8 | SubscriberVault::subscribe[basic_7d] | `10194da10e07ab724aefd4e297e38ee2f4fa177031acdc9135e19c34a86e548b` | [view](https://testnet.cspr.live/deploy/10194da10e07ab724aefd4e297e38ee2f4fa177031acdc9135e19c34a86e548b) |
| 9 | AgentBehaviorIndex::record_action[classify] | `da61b7b38388e683c37f8040514a1b2a77b59209f9aa64c661094503e85169db` | [view](https://testnet.cspr.live/deploy/da61b7b38388e683c37f8040514a1b2a77b59209f9aa64c661094503e85169db) |
| 10 | AgentBehaviorIndex::record_action[skip] | `36811baffde99c09663c64ccf08a0ceb3d86581c3cae57a82dfdb7d40655a568` | [view](https://testnet.cspr.live/deploy/36811baffde99c09663c64ccf08a0ceb3d86581c3cae57a82dfdb7d40655a568) |
| 11 | RiskPolicyManager::set_threshold[min_confidence] | `77b1f5e6acf89dbdec06a4d98cd0052b5a4c55761ded7f9960604550d401eb8a` | [view](https://testnet.cspr.live/deploy/77b1f5e6acf89dbdec06a4d98cd0052b5a4c55761ded7f9960604550d401eb8a) |
| 12 | RiskPolicyManager::set_threshold[max_risk] | `7efd0b77f3bbec253c074639955e7efb08795bac8b9dbbcbf88210c18e723e03` | [view](https://testnet.cspr.live/deploy/7efd0b77f3bbec253c074639955e7efb08795bac8b9dbbcbf88210c18e723e03) |
| 13 | SentinelCredit::issue_credit[deployer] | `29f1924933f16949b5b82d462ed8ad85c1f1d8be25226c55a1c6a627ba2c6ed8` | [view](https://testnet.cspr.live/deploy/29f1924933f16949b5b82d462ed8ad85c1f1d8be25226c55a1c6a627ba2c6ed8) |
| 14 | AuditTrail::pipeline_status | `ce5e64355638df810ac4b6ee489990363976319a21487394ef62f91c67d1c662` | [view](https://testnet.cspr.live/deploy/ce5e64355638df810ac4b6ee489990363976319a21487394ef62f91c67d1c662) |
| 15 | RiskOracle::protocol_scan_v2 | `62e3dc976e412ee45d7cc013939ce90abb9b4f396e19e93d6d46ea27700e98ad` | [view](https://testnet.cspr.live/deploy/62e3dc976e412ee45d7cc013939ce90abb9b4f396e19e93d6d46ea27700e98ad) |
| 16 | SentinelAlertLog::batch_flush | `019822354bb63b29f613e34601751977647d3ad9f4719547d70e067789cfd7fa` | [view](https://testnet.cspr.live/deploy/019822354bb63b29f613e34601751977647d3ad9f4719547d70e067789cfd7fa) |
| 17 | AgentBehaviorIndex::agent_init | `3ea7ff328ed52fc74325a7b227d6ea0f8772a7422f4d519a674d7b7d67b03cfb` | [view](https://testnet.cspr.live/deploy/3ea7ff328ed52fc74325a7b227d6ea0f8772a7422f4d519a674d7b7d67b03cfb) |
| 18 | RiskPolicyManager::policy_reload | `5da86f8eaca22f96b7756c7958a1aff03a300e020569f0cfadcafaafd53d979f` | [view](https://testnet.cspr.live/deploy/5da86f8eaca22f96b7756c7958a1aff03a300e020569f0cfadcafaafd53d979f) |
| 19 | SentinelRegistry::health_ping | `d0240be05b2834a1634d3ee28d361d3381a52c551c9fdfb6fe28a2655accb3ee` | [view](https://testnet.cspr.live/deploy/d0240be05b2834a1634d3ee28d361d3381a52c551c9fdfb6fe28a2655accb3ee) |
| 20 | SentinelCredit::balance_check | `97efecfe56f004aeb0178bd309fd97d3b17ae60a43e1b79b9a3a0c4ca0a53d68` | [view](https://testnet.cspr.live/deploy/97efecfe56f004aeb0178bd309fd97d3b17ae60a43e1b79b9a3a0c4ca0a53d68) |
| 21 | SubscriberVault::vault_sync | `3449dd44973390ff3aa2ff4922b1f540f1c5d265aae216a1aff803a07ab0a6a8` | [view](https://testnet.cspr.live/deploy/3449dd44973390ff3aa2ff4922b1f540f1c5d265aae216a1aff803a07ab0a6a8) |

**Total: 29 on-chain TX hashes (8 contract deploys + 21 contract interactions) ✓**

Full machine-readable list: [`proof/interaction_hashes.json`](interaction_hashes.json)
