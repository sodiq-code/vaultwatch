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

### API Keys (Groq, etc.)

- API keys are read from environment variables (`GROQ_API_KEY`, etc.).
- The `.env.example` file documents required variables without containing
  real values.
- In CI, secrets are injected via GitHub Actions secrets — never echoed
  to logs.

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
