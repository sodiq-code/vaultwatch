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
