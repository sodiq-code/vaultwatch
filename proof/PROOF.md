# VaultWatch — Verification Guide

**Repository**: https://github.com/sodiq-code/vaultwatch  
**Network**: Casper Testnet (`casper-test`)  
**Deployer**: `0202c223a43185563f404720fbb7028305cd79d6046ffdf7b746cfa42294c43db1d0`

---

## 1. Smart Contracts on Casper Testnet

All 8 Odra contracts were compiled to WASM and deployed to `casper-test` on June 23, 2026.

| Contract | Deploy Hash | Testnet Link |
|----------|-------------|--------------|
| AuditTrail | `9be661d1ed21ac8d762233108ec57b0a8a9e50580ad7b82066cd5690f69a86c4` | [testnet.cspr.live](https://testnet.cspr.live/deploy/9be661d1ed21ac8d762233108ec57b0a8a9e50580ad7b82066cd5690f69a86c4) |
| RiskOracle | `c8341d32cb40667a3c61f8b49389104e211ad1ae57833c79a084d5bbf805f541` | [testnet.cspr.live](https://testnet.cspr.live/deploy/c8341d32cb40667a3c61f8b49389104e211ad1ae57833c79a084d5bbf805f541) |
| SentinelCredit | `2101c5c55305fd5fb23fdf3c24029dc493fa07c5722e006313525eec80a0b8c6` | [testnet.cspr.live](https://testnet.cspr.live/deploy/2101c5c55305fd5fb23fdf3c24029dc493fa07c5722e006313525eec80a0b8c6) |
| SentinelRegistry | `bb722bbd2ac8698419e59fd87f86e52d0ac59cae0e7542f2efa7a3cefdeb6acc` | [testnet.cspr.live](https://testnet.cspr.live/deploy/bb722bbd2ac8698419e59fd87f86e52d0ac59cae0e7542f2efa7a3cefdeb6acc) |
| SentinelAlertLog | `e98ca94c5f88474019b7459a3203d0ca3cb0cf2ae594e2c0ee2042f948f0fa50` | [testnet.cspr.live](https://testnet.cspr.live/deploy/e98ca94c5f88474019b7459a3203d0ca3cb0cf2ae594e2c0ee2042f948f0fa50) |
| AgentBehaviorIndex | `6061dfdeb871f932375da817032f2c890eaf85b77f07a77a6d81811871c79928` | [testnet.cspr.live](https://testnet.cspr.live/deploy/6061dfdeb871f932375da817032f2c890eaf85b77f07a77a6d81811871c79928) |
| RiskPolicyManager | `5b4a65a946f96edd1673d379557356b0e8c1e2ac75efbdd591eaeb436ba61e6e` | [testnet.cspr.live](https://testnet.cspr.live/deploy/5b4a65a946f96edd1673d379557356b0e8c1e2ac75efbdd591eaeb436ba61e6e) |
| SubscriberVault | `340557ddf3509f15aca0e94216aa419f083bdf2b3241ad2773a5feda079fb1f7` | [testnet.cspr.live](https://testnet.cspr.live/deploy/340557ddf3509f15aca0e94216aa419f083bdf2b3241ad2773a5feda079fb1f7) |

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

Expected: **107 passed** across unit, integration, and demo test suites.

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
