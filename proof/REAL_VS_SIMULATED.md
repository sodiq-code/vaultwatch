# VaultWatch — What's Real vs Mocked

**Project**: VaultWatch — DeFi Risk Intelligence Agent on Casper  
**Repository**: https://github.com/sodiq-code/vaultwatch  
**Network**: Casper Testnet (casper-test)

---

## What's Real (Verifiable in This Repository)

| Component | Status | Evidence |
|-----------|--------|----------|
| 8 Odra contracts compiled to WASM | ✅ Real | `contracts/wasm/*.wasm` — 8 WASM binaries |
| Contract source code (Rust/Odra) | ✅ Real | `contracts/src/` — 8 contracts, fully implemented |
| Test suite 107/107 passing | ✅ Real | `proof/05_test_results.txt` — actual pytest output |
| FastMCP server with 15 tools | ✅ Real | `vaultwatch_mcp/server.py` — 500+ lines |
| 6 Groq AI agents | ✅ Real | `agents/*.py` — each with assigned Groq model |
| FastAPI REST API | ✅ Real | `api/main.py` — OTel-instrumented endpoints |
| Python SDK | ✅ Real | `sdk/vaultwatch/` — installable, tested |
| Casper Sidecar SSE client | ✅ Real | `streaming/sidecar_client.py` |
| OpenTelemetry instrumentation | ✅ Real | Every agent + `sdk/vaultwatch/otel_instrumentation.py` |
| React/Vite dashboard | ✅ Real | `dashboard/src/` — 800+ lines |

## What's Mocked in Tests

| Component | Mock Reason | Production Path |
|-----------|-------------|-----------------|
| Casper node RPC calls | No live testnet node in CI | Set `CASPER_MOCK=false` with funded wallet |
| Groq API responses | Avoids API key requirement in CI | Set real `GROQ_API_KEY` env var |
| x402 payment deductions | Mock CSPR balance | SubscriberVault contract + funded wallet |
| Sidecar SSE stream | Replayed fixture events | Point `CASPER_SIDECAR_URL` to live node |

---

## Verification

```bash
# 1. Check WASM artifacts
ls -la contracts/wasm/
# Expected: 8 .wasm files (~14KB each)

# 2. Run all tests
CASPER_MOCK=true GROQ_API_KEY=mock pytest tests/ -v
# Expected: 107 passed

# 3. Start API + MCP server
uvicorn api.main:app --port 8000 &
python vaultwatch_mcp/server.py
```
