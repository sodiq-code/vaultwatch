# VaultWatch — What's Real vs Mock

**Project**: VaultWatch — DeFi Risk Intelligence Agent on Casper  
**Repository**: https://github.com/sodiq-code/vaultwatch  
**Testnet**: Casper Testnet (casper-test)

---

## Real (Verified On-Chain)

| Component | Status | Evidence |
|-----------|--------|----------|
| 8 Odra contracts compiled to WASM | ✅ Real | `contracts/wasm/*.wasm` — 8 files, ~14KB each |
| All 8 contracts deployed to testnet | ✅ Real | `deploy_hashes.json` — 8 unique deploy hashes |
| Contract WASM artifacts | ✅ Real | `proof/03_wasm_contracts.txt` — `ls -la` output |
| Test suite 107/107 passing | ✅ Real | `proof/05_test_results.txt` — actual pytest output |
| FastMCP server with 15 tools | ✅ Real | `vaultwatch_mcp/server.py` — 500+ lines |
| 6 Groq agents with model assignments | ✅ Real | `agents/*.py` — each agent file |
| FastAPI REST API | ✅ Real | `api/main.py` — OTel-instrumented endpoints |
| Python SDK | ✅ Real | `sdk/vaultwatch/` — installable, tested |
| Casper Sidecar SSE client | ✅ Real | `streaming/sidecar_client.py` |
| OpenTelemetry instrumentation | ✅ Real | Every agent file + `sdk/vaultwatch/otel_instrumentation.py` |
| React/Vite dashboard | ✅ Real | `dashboard/src/` — 800+ lines |

## Mock (In Tests, Requires Live Node for Production)

| Component | Mock Reason | Production Path |
|-----------|-------------|-----------------|
| Casper node calls in tests | No testnet node in CI | Set `CASPER_MOCK=false` + fund wallet |
| Groq API calls in tests | Uses mock responses | Set real `GROQ_API_KEY` |
| x402 payments in tests | Mock CSPR balance | SubscriberVault contract holds real CSPR |
| Sidecar SSE in tests | Replayed events | Point `CASPER_SIDECAR_URL` to live node |

---

## Verification (5 minutes)

```bash
# 1. Check WASM artifacts
ls -la contracts/wasm/
# Expected: 8 .wasm files

# 2. Run all tests
pytest tests/ -v
# Expected: 107 passed

# 3. Verify deploy hashes
cat deploy_hashes.json

# 4. Check each hash on Casper testnet explorer
# https://testnet.cspr.live/deploy/{hash}

# 5. Start API + MCP
uvicorn api.main:app --port 8000 &
python vaultwatch_mcp/server.py
```
