# VaultWatch Contract Build Task

## Goal
Compile 8 Odra Casper contracts to WASM and deploy to testnet.

## Status
- [x] Keypair generated + .env updated (secp256k1 from wallet)
- [x] Workspace structure created (src/{contract}/src/lib.rs)
- [x] Code compiles with odra 1.5.1 (but produces empty WASMs - wrong approach)
- [ ] Fix: Use odra 2.8.0 with proper build structure

## Key Findings
- cargo-odra 0.1.7 works with odra 2.8.0 (not 1.5.1)
- Template structure: single flat crate with all contracts as modules
- Required files per crate:
  - bin/build_contract.rs (use <crate_name>; no_std; no_main)
  - build.rs (calls odra_build::build())
  - Cargo.toml with [[bin]] entry and odra-build dep
  - Odra.toml with [[contracts]] fqn = "module::StructName"

## Plan
1. Restructure as single flat crate (not workspace) - matches odra template
2. Update contracts to odra 2.x API (Var, Mapping from prelude, same approach)
3. Add bin/build_contract.rs and build.rs
4. Run cargo odra build
5. Deploy with deploy_contracts.py --mock=false
6. Update README with TX hashes
7. Push to GitHub

## Odra 2.x API Notes
- Same as 1.x: `use odra::prelude::*` gives Var, Mapping, etc.
- ExecutionError::User(code) still valid
- get_or_revert_with() still the method name
- #![cfg_attr(not(test), no_std)] pattern
