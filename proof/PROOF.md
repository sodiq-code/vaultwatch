# VaultWatch — Verification Guide

**Repository**: https://github.com/sodiq-code/vaultwatch  
**Network**: Casper Testnet (`casper-test`)  
**Deployer**: `0202c27a6d17a12aef3775e27ac8964b075f55b665240f48d8d0880efdce56ea2116`

---

## 1. Smart Contracts on Casper Testnet

All 8 Odra contracts were compiled to WASM and deployed to `casper-test` on June 24, 2026.

| Contract | Deploy Hash | Testnet Link |
|----------|-------------|--------------|
| AuditTrail | `f06e33573efbe1c8db658b4ab37db4c0ef7996ba02bfd8378049ada251e8e102` | [testnet.cspr.live](https://testnet.cspr.live/deploy/f06e33573efbe1c8db658b4ab37db4c0ef7996ba02bfd8378049ada251e8e102) |
| SentinelRegistry | `d9c8c5eff41f81e659c907255c48813ad56303634dbb4d8fb1e2b0df4ae48622` | [testnet.cspr.live](https://testnet.cspr.live/deploy/d9c8c5eff41f81e659c907255c48813ad56303634dbb4d8fb1e2b0df4ae48622) |
| RiskOracle | `fb877bae9a273ce74886a68d772841f9089503d802d106bb93bd018f7ef5e98a` | [testnet.cspr.live](https://testnet.cspr.live/deploy/fb877bae9a273ce74886a68d772841f9089503d802d106bb93bd018f7ef5e98a) |
| SentinelCredit | `01cfe8d1e596859aa81954a6bf4792961c3c7587e6df2e4ce7d98bc802c7a403` | [testnet.cspr.live](https://testnet.cspr.live/deploy/01cfe8d1e596859aa81954a6bf4792961c3c7587e6df2e4ce7d98bc802c7a403) |
| AgentBehaviorIndex | `162a4f5ff991b7eceb8aa38ff3c2a2beb27dc2007a8c499602d372563cdc63a9` | [testnet.cspr.live](https://testnet.cspr.live/deploy/162a4f5ff991b7eceb8aa38ff3c2a2beb27dc2007a8c499602d372563cdc63a9) |
| SentinelAlertLog | `45dbc90b56dc40e419d9da7b6a972fc6027ea0125065d6a1ddfa0c9394eb42c7` | [testnet.cspr.live](https://testnet.cspr.live/deploy/45dbc90b56dc40e419d9da7b6a972fc6027ea0125065d6a1ddfa0c9394eb42c7) |
| RiskPolicyManager | `048dcfe5ca296101eb7aa11694165b321f7a42c2c8d560aeddd628f4c08c8b1a` | [testnet.cspr.live](https://testnet.cspr.live/deploy/048dcfe5ca296101eb7aa11694165b321f7a42c2c8d560aeddd628f4c08c8b1a) |
| SubscriberVault | `786b611f007e410aa2d8d8ed47b267ea6e9bb3c7d343003c3dad3ba0d3fd35f0` | [testnet.cspr.live](https://testnet.cspr.live/deploy/786b611f007e410aa2d8d8ed47b267ea6e9bb3c7d343003c3dad3ba0d3fd35f0) |

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
