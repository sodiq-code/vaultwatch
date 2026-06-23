# VaultWatch — Verification Guide

**Repository**: https://github.com/sodiq-code/vaultwatch  
**Hackathon**: [Casper Agentic Buildathon 2026](https://dorahacks.io/hackathon/casper-agentic-buildathon/detail)  
**Testnet**: Casper Testnet

---

## Component Verification

### 1. Smart Contracts (5 min)

All 8 Odra contracts deployed to Casper testnet on June 22, 2026.

```bash
# View compiled WASM artifacts
ls -la contracts/wasm/
# Expected: 8 .wasm files (~14KB each)

# Rebuild from source (optional)
cd contracts && cargo odra build --release
```

**Live explorer links:**

| Contract | Link |
|----------|------|
| AuditTrail | https://testnet.cspr.live/deploy/27249e7838f2b14443ebd3b0aa461608675e36e6ef3a954af431b5f2df8041fb |
| RiskOracle | https://testnet.cspr.live/deploy/68ef325d2b3a0f544467d8624e5042e428cd40258009777ffcdc568c1f426c55 |
| SentinelCredit | https://testnet.cspr.live/deploy/b6466009e65ac07a7ab7a26b3c5f0f600a6dc4c1efeaf96ea105000d24c8e6d9 |
| SentinelRegistry | https://testnet.cspr.live/deploy/71398513bc183652549d46f4ea3d5319a7614cc55ce6c5378302150e46b07562 |
| SentinelAlertLog | https://testnet.cspr.live/deploy/8f762ab42f0da419ace4d99259893165a8483ad376d524b15ba76355cb597693 |
| AgentBehaviorIndex | https://testnet.cspr.live/deploy/665c1bd2937f88403806a1e3cd4fc9de7b931baa6cbc9b87bd05b6b23d823171 |
| RiskPolicyManager | https://testnet.cspr.live/deploy/14284d5c3f3acf47dab65df94bbe982cdc787ff38245154521810f7cf819d874 |
| SubscriberVault | https://testnet.cspr.live/deploy/2fb6b5b699216d4662701b9d54101bb3740b3a10c62d8f7aaf5f0703a7a1b009 |

### 2. AI/Agentic Layer (5 min)

```bash
# View 6 agent implementations
ls agents/
# anomaly_agent.py, audit_agent.py, intel_agent.py, rwa_agent.py,
# safety_guard.py, scanner_agent.py, self_correction_agent.py

# View 15 MCP tools
grep "@mcp.tool" vaultwatch_mcp/server.py | wc -l
# Expected: 15
```

### 3. Tests (10 min)

```bash
pip install -r requirements.txt
pip install -e sdk/
pytest tests/ -v
# Expected: 107 passed
```

### 4. SDK

```bash
pip install -e sdk/
python -c "from vaultwatch import VaultWatchClient; print('SDK OK')"
```

### 5. Full Stack

```bash
docker-compose up -d
curl http://localhost:8000/health
# Expected: {"status": "healthy"}
```

---

## Proof Files

| File | Contents |
|------|----------|
| `proof/01_build_output.txt` | Cargo build output — 8 contracts compiled |
| `proof/03_wasm_contracts.txt` | `ls -la contracts/wasm/` output |
| `proof/05_test_results.txt` | Full pytest output — 107 passed |
| `proof/06_mcp_server.txt` | MCP server startup + tool list |
| `deploy_hashes.json` | All 8 live deploy hashes |
