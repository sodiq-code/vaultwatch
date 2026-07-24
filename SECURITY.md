# Security Policy

## Supported Versions

VaultWatch is a hackathon project. We apply security fixes to the latest
`main` branch only.

| Version | Supported          |
|---------|--------------------|
| 4.x     | ✅ (current)       |
| < 4.0   | ❌                 |

## Reporting a Vulnerability

If you discover a security vulnerability in VaultWatch:

1. **DO NOT open a public GitHub issue.**
2. Email the maintainer at `dev@vaultwatch.io` with:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)
3. You will receive an acknowledgment within 48 hours.
4. A fix will be developed and disclosed responsibly.

## Critical Security Notes

### Signing Keys

- **NEVER commit signing keys (`.pem`), recovery codes, or mnemonics to git.**
- The `.gitignore` excludes `secret_key.pem`, `.env`, and similar patterns.
- If you accidentally commit a key, treat it as COMPROMISED and rotate
  immediately. GitHub's secret scanning will also flag known patterns.

### Casper Testnet Keys

- Use a dedicated testnet key for contract deployments. Do not reuse
  mainnet keys.
- The deploy script (`scripts/deploy_contracts_live.py`) reads the key
  path from `CASPER_KEY_PATH` env var only — it never accepts inline keys.
- After deployment, the key file should be stored offline or in a secret
  manager (1Password, AWS Secrets Manager, etc.), not in the repo.

### API Keys (Groq, CSPR.cloud, etc.)

- API keys are read from environment variables (`GROQ_API_KEY`,
  `CSPR_CLOUD_API_KEY`, etc.).
- The `.env.example` file documents required variables without containing
  real values.
- In CI, secrets are injected via GitHub Actions secrets — never echoed
  to logs.

### CSPR.cloud API Key — Reverse Proxy (Critical Fix 6)

The CSPR.cloud REST API (`https://api.testnet.cspr.cloud`) requires a
Bearer access token. Previously this key was hardcoded in
`dashboard/src/liveApi.js` (browser-exposed — anyone with devtools open
could lift it) and in several Python scripts. **The leaked key has been
revoked and rotated.**

Mitigations now in place:

1. **The key lives only in the `CSPR_CLOUD_API_KEY` environment variable.**
   It is never committed to source, never logged, and never echoed in API
   responses. The `.env.example` documents the variable with a placeholder.

2. **The dashboard never reads the key directly.** All CSPR.cloud REST
   calls go through the VaultWatch FastAPI reverse proxy:
   - Browser calls `GET /api/cspr_cloud/blocks?page_size=1` (in dev, the
     Vite dev server proxies `/api/*` and `/cspr_cloud/*` to
     `http://localhost:8000`; in production, set `VITE_API_URL` to the
     deployed API origin).
   - The FastAPI app (`api/main.py` → `cspr_cloud_proxy_get`) reads
     `CSPR_CLOUD_API_KEY` from env, injects
     `Authorization: Bearer $CSPR_CLOUD_API_KEY`, and forwards the
     request to `https://api.testnet.cspr.cloud/<path>?<query>`. The
     upstream response body, content-type, and status code are returned
     verbatim.
   - The key never appears in the browser bundle, the network tab, or
     client-side JS.

3. **Server-side scripts read the key from env directly.**
   `scripts/broadcast_interactions.py`, `scripts/broadcast_transfers.py`,
   `scripts/deploy_live.py`, `scripts/deploy_new_account.py`,
   `scripts/broadcast_deploys.py`, and `scripts/verify_contract_entrypoints.py`
   all use `os.getenv("CSPR_CLOUD_API_KEY", "")`. They run in a trusted
   environment (deployer machine, CI), so they do not need the proxy.
   Empty string is safe — the public Casper testnet node
   (`node.testnet.casper.network/rpc`) does not require the header.

4. **The proxy exposes a `/cspr_cloud/status` health endpoint** that
   reports whether `CSPR_CLOUD_API_KEY` is set and what the upstream URL
   is — without ever echoing the key itself. Useful for debugging 401s
   and for the dashboard health-check.

5. **A test (`tests/integration/test_cspr_cloud_proxy.py`) verifies**:
   - The leaked key prefix does not appear in any tracked source file.
   - The proxy injects the Bearer header from env when forwarding.
   - The `/cspr_cloud/status` endpoint does not leak the key.
   - `dashboard/src/liveApi.js` does not contain the key and does not
     call `api.testnet.cspr.cloud` directly.

### Rotation procedure

If the CSPR.cloud key is ever compromised again:

1. Revoke it immediately at https://cspr.cloud/account/settings/tokens.
2. Generate a new token with the same scope.
3. Update `CSPR_CLOUD_API_KEY` in the server environment (`.env` locally,
   Vercel/Render env vars in production, GitHub Actions secret in CI).
4. Restart the FastAPI app (uvicorn picks up the new env on reload — no
   code change or redeploy needed).
5. Run `pytest tests/integration/test_cspr_cloud_proxy.py` to verify.

### Smart Contract Security

The 8 VaultWatch contracts use Odra 2.8.0 and follow these patterns:
- **Owner-only mutations**: every state-changing entry point calls
  `assert_owner()` to verify the caller.
- **No arbitrary calls**: contracts do not have `delegate_call` or
  generic call facilities.
- **Checked arithmetic**: Odra's `U512` type panics on overflow.
- **No reentrancy**: contracts do not call back into untrusted code.

Known limitations (documented in `docs/RED_TEAM_CHECKLIST.md`):
- Owner key is a single signer (multisig is a future upgrade).
- Reputation formula has 4 partial-resistance attack vectors (Checks 2,
  5, 10, 11) — all documented with mitigations.

## CodeQL + Dependabot

- **CodeQL** runs on every push and PR (`.github/workflows/codeql.yml`).
- **Dependabot** opens PRs for outdated dependencies weekly
  (`.github/dependabot.yml`).
- All CodeQL alerts with High or Critical severity MUST be resolved
  before merging to `main`.

## Supply Chain

- Python packages: published to PyPI as `casper-sentinel` (built from
  `sdk/`).
- npm packages: published as `casper-sentinel-mcp` (built from
  `vaultwatch_mcp/`).
- npm provenance is enabled for the MCP package.
- Contract WASM is built reproducibly via CI
  (`.github/workflows/build-contracts.yml`) with pinned Rust nightly
  and verified zero bulk-memory opcodes.
