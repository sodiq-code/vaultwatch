# Contributing to VaultWatch

First off — thank you for considering a contribution! VaultWatch is a
hackathon project but we welcome improvements, especially around the
reputation formula, MCP tools, and Casper contract correctness.

## Development Setup

```bash
git clone https://github.com/sodiq-code/vaultwatch
cd vaultwatch

# Python (3.11+)
pip install -r requirements.txt
pip install -e sdk/

# Rust contracts (nightly pinned)
rustup toolchain install nightly-2026-01-01
rustup target add wasm32-unknown-unknown --toolchain nightly-2026-01-01
cargo install --locked odra-cli --version 2.8.0

# wasm-opt (for Casper-compatible builds)
sudo apt install binaryen  # or: brew install binaryen

# Node (18+) for x402 + MCP + dashboard
cd x402 && npm install && cd ..
cd vaultwatch_mcp && npm install && cd ..
cd dashboard && npm install && cd ..
```

## Branching & Workflow

- `main` — always deployable. Never push directly.
- `develop` — integration branch.
- Feature branches: `feat/<short-name>` or `fix/<short-name>`.
- 

**Critical rule** (from the hackathon team): the repo MUST be in a
functional state at every commit. A judge may visit mid-PR. So:
- All risky changes land on a feature branch first.
- `main` only receives merges after CI is green AND (for contract changes)
  the WASM passes `scripts/check_wasm_bulk_memory.py`.

## Building Contracts

```bash
# Build all 8 contracts (bulk-memory-safe for Casper)
bash scripts/build_contracts.sh

# Verify zero bulk-memory opcodes (hard gate)
python3 scripts/check_wasm_bulk_memory.py contracts/wasm/
```

The `.github/workflows/build-contracts.yml` workflow does this on every
push. Compiled WASM must be bulk-memory-safe for Casper Testnet compatibility.

## Testing

```bash
# Python tests (100+ tests)
pytest tests/ -v

# Contract tests (Rust)
cd contracts && cargo test --workspace

# MCP server smoke test
python3 vaultwatch_mcp/server.py  # should start successfully
```

## Code Style

- **Python**: `ruff check .` and `ruff format --check .` must pass.
- **Rust**: `cargo fmt --check` and `cargo clippy` must pass.
- **TypeScript/JavaScript**: `tsc --noEmit` must pass.

## Pull Request Checklist

- [ ] Branch is up to date with `develop`
- [ ] CI is green (lint + tests + build-contracts)
- [ ] No new CodeQL High/Critical alerts
- [ ] If touching contracts: `check_wasm_bulk_memory.py` passes
- [ ] If adding an MCP tool: tool count in `server.py` docstring is updated
- [ ] If adding a dependency: it's in `requirements.txt` or `package.json`
- [ ] README updated if user-facing behavior changed
- [ ] `proof/PROOF.md` updated if deploy hashes changed

## Reporting Issues

Open a GitHub issue with:
- Clear title and description
- Steps to reproduce
- Expected vs actual behavior
- Logs (redact any secrets — API keys, signing keys, mnemonics)

## Security Issues

See [SECURITY.md](SECURITY.md) — do NOT open a public issue for security.

## License

By contributing, you agree your contributions are licensed under the MIT
License (see [LICENSE](LICENSE)).
