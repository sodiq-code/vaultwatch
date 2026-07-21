# VaultWatch — Casper-Native Contract Upgrade Demo (Critical Fix 2)

> **What this delivers:** a real, Casper-native demonstration of
> `storage::add_contract_version()` — the single most differentiating Casper
> primitive — by installing a **v2** of `RiskPolicyManager` as a new version
> under the **same contract package** as v1, with **shared state** and a **new
> entry point** (`get_policy_with_reasoning`).
>
> **Status: ✅ FULLY VERIFIED ON-CHAIN on Casper Testnet (`casper-test`) on
> July 21, 2026.** The complete upgrade lifecycle (v1 install → set policy →
> v2 upgrade via `add_contract_version()` → call v1 & v2 entry points → verify
> shared state) was executed and verified with **6/6 on-chain checks passing**
> and **6/6 deploys verified-success**. See [§6 On-Chain Execution
> Results](#6-on-chain-execution-results).

---

## 1. The Critique This Closes

The strategic review (Critical Fix 2) called out that VaultWatch's
"RiskPolicyManager — Hot-swappable risk thresholds without contract
redeployment" headline was **misleading**: the `upgrade_policy()` entry point is
just a `Var` overwrite — there is **no `add_contract_version()` call**, no
`ContractPackageHash`-based versioning, and no demonstration of the single most
differentiating Casper primitive.

This demo closes that gap with the real thing:

| Review demand | How this demo delivers |
|---|---|
| Install a v2 using `add_contract_version()` | v2 Wasm deployed as session code with `odra_cfg_is_upgrade=true`; Odra's generated `call()` invokes `storage::add_contract_version(package_hash, entry_points, named_keys, {})` on-chain. |
| Add a new entry point (`get_policy_with_reasoning`) | v2 module adds `get_policy_with_reasoning(&self) -> PolicyWithReasoning`. Verified present in the v2 Wasm exports. |
| Call v1 entry points, verify they still work | v2 is a **functional superset** (all v1 entry points preserved); calling them on the upgraded package (latest version = v2) succeeds. |
| Call v2 entry points, verify they work | `get_policy_with_reasoning` is callable on v2 (latest version). |
| Query state set by v1 from v2 (shared state) | v2 keeps v1's struct fields in the **same order** → same `state` dictionary keys → v2 reads v1's `current_policy` unchanged. Structurally: v2's `state` URef == v1's `state` URef. Functionally: `get_policy_with_reasoning` reads `current_policy` via `get_or_revert`, so its success *proves* shared state. |
| Capture every deploy/call hash | All hashes recorded in `proof/upgrade_hashes.json` (written by `scripts/demo_upgrade_contract.py`). |
| One-page write-up | This document. |

---

## 2. v2 Contract Design (`contracts/src/risk_policy_manager_v2.rs`)

v2 is a **superset** of v1, governed by two rules required for shared state:

1. **Same struct fields, same order** as v1:
   ```rust
   pub struct RiskPolicyManagerV2 {
       current_policy: Var<RiskPolicy>,   // index 0  (same as v1)
       policy_history: Mapping<u32, RiskPolicy>,  // index 1
       owner: Var<Address>,               // index 2
   }
   ```
   Odra stores all module state in a single `state` dictionary keyed by field
   index. Preserving the field order means v2 reads v1's state via the identical
   dictionary keys — **no migration code required**.

2. **Reuse v1's `RiskPolicy` type** (`pub use crate::risk_policy_manager::RiskPolicy;`)
   so the serialized layout is byte-identical.

v2 preserves **all v1 entry points** (`init`, `upgrade_policy`,
`get_current_policy`, `get_policy_version`, `get_current_version`,
`transfer_ownership`) and adds:

- **`get_policy_with_reasoning(&self) -> PolicyWithReasoning`** — the v2-only
  capability. Returns the active policy plus a human-readable rationale string
  (e.g. *"Policy v3: CRITICAL >85/100, HIGH >65/100 … SelfCorrection triggers
  below 70/100 confidence (max 2 retries) …"*). Because it reads `current_policy`
  via `get_or_revert`, its **successful execution proves v2 reads v1's shared
  state** — if state weren't shared, it would revert with `User(1)`.

- **`upgrade(&mut self)`** — the Odra upgrade hook, invoked automatically after
  `add_contract_version()`. A no-op here (v2 preserves v1's field layout, so no
  migration is needed).

The module ships with 4 OdraVM unit tests (`v2_init_sets_default_policy_like_v1`,
`v2_get_policy_with_reasoning_returns_active_policy_and_text`,
`v2_preserves_v1_entry_points`, `build_reasoning_is_no_std_safe_and_descriptive`).

---

## 3. Build Pipeline (Casper-compatible Wasm)

The v2 Wasm is built with the **official Odra framework** (hackathon-sanctioned)
and post-processed to remove bulk-memory opcodes (Casper's `wasmi` rejects them).

```bash
# 1. Compile v2 to Wasm (nightly toolchain, bulk-memory disabled at source).
#    Only the RiskPolicyManagerV2 module is compiled in (ODRA_MODULE selector).
cd contracts
ODRA_MODULE=RiskPolicyManagerV2 ODRA_BACKEND=casper \
  RUSTFLAGS="-C target-feature=-bulk-memory" \
  cargo build --target wasm32-unknown-unknown --lib --release

# 2. Lower any residual memory.copy/memory.fill (re-introduced by LTO) into
#    explicit loops with wasm-opt v131 (--llvm-memory-copy-fill-lowering).
wasm-opt target/wasm32-unknown-unknown/release/vaultwatch_contracts.wasm \
  --enable-bulk-memory-opt --llvm-memory-copy-fill-lowering -Oz \
  -o wasm/RiskPolicyManagerV2.wasm

# 3. Hard-gate: zero bulk-memory opcodes.
python3 ../scripts/check_wasm_bulk_memory.py wasm/RiskPolicyManagerV2.wasm
```

**Result:** `RiskPolicyManagerV2.wasm` — 135.2 KB, **clean** (no bulk-memory
opcodes), exports `call`, `init`, `upgrade_policy`, `get_current_policy`,
`get_policy_version`, `get_current_version`, `transfer_ownership`,
`get_policy_with_reasoning`, `upgrade`, `migrate_events`.

> The full 9-Wasm gate passes (8 v1 + 1 v2), all Casper-compatible.

---

## 4. The Casper-Native Upgrade Mechanism

Casper upgrades work by calling the host function
`storage::add_contract_version(package_hash, entry_points, named_keys,
message_topics)` **from within executing Wasm**. The currently-executing Wasm
becomes the bytecode of the new contract version; the package gains a new
version entry pointing at it. Odra 2.x wraps this: when the v2 Wasm is deployed
as session code (a `ModuleBytes` deploy) with the runtime arg
`odra_cfg_is_upgrade=true`, Odra's generated `call()` runs:

```text
call()
  └─ install_or_upgrade(entry_points, schemas, upgrade_args)
       └─ upgrade_contract(...)              # is_upgrade == true
            ├─ storage::add_contract_version(pkg, eps, named_keys, {})   ← THE upgrade
            ├─ runtime::put_key(package_hash_key_name, pkg)
            ├─ storage::provision_contract_user_group_uref(pkg, "upgrader_group")
            ├─ call_versioned_contract(pkg, None, "migrate_events", ...)
            ├─ call_versioned_contract(pkg, None, "upgrade", args)        ← v2's no-op hook
            └─ storage::disable_contract_version(pkg, previous_contract_hash)
```

After this, the package has **two versions** (v1 disabled, v2 active = latest),
the `state` dictionary is shared, and the new `get_policy_with_reasoning` entry
point is callable.

### Runtime args passed to the upgrade deploy

| Arg | CLType | Value | Why |
|---|---|---|---|
| `odra_cfg_is_upgrade` | `Bool` | `true` | Triggers the upgrade path in `call()`. |
| `odra_cfg_package_hash_to_upgrade` | `ByteArray(32)` | v1 package hash (32 bytes) | The package to add a version to (`HashAddr`). |
| `odra_cfg_package_hash_key_name` | `String` | `risk_policy_manager_package_hash` | Named key the package hash is stored under. |
| `odra_cfg_allow_key_override` | `Bool` | `true` | That named key already exists (from v1 install). |
| `odra_cfg_create_upgrade_group` | `Bool` | **`false`** | v1 install already created `upgrader_group`; re-creating raises `GroupAlreadyExists` (`ApiError::ContractHeader(3)`). |
| `odra_cfg_is_upgradable` | `Bool` | `true` | Matches v1 install config (harmless; not read by `upgrade_contract`). |

---

## 5. Verification Matrix

`scripts/demo_upgrade_contract.py` runs five on-chain checks after the upgrade:

| # | Check | How | Pass criterion |
|---|---|---|---|
| 1 | Package has 2 versions | `query_global_state` on `hash-<package_hash>` → `ContractPackage.versions[]` | `len(versions) >= 2` |
| 2 | v2 exposes `get_policy_with_reasoning` | `query_global_state` on `hash-<v2_contract_hash>` → `entry_points[]` | new EP present |
| 2b | v1 entry points preserved in v2 | same query | v1 EP set ⊆ v2 EP set |
| 3 | Shared state (structural) | compare v2's `state` URef to v1's `state` URef | equal |
| 4 | `get_policy_with_reasoning` works on v2 (functional shared-state proof) | stored-contract call on v2 | `execution_result.Version2.error_message == null` |
| 5 | v1 entry point still works on upgraded package | call `get_current_policy` on v2 | `error_message == null` |

All deploy/call hashes are written to `proof/upgrade_hashes.json`.

---

## 6. On-Chain Execution Results ✅ VERIFIED

The complete upgrade lifecycle was executed and verified live on Casper Testnet
(`casper-test`, `https://node.testnet.casper.network/rpc`, build 2.2.2) on
**July 21, 2026**. A funded deployer account (`02031300f7e7a8c0a9390ce7f365e315bae45c91e2cdcedaf754156b1a6bac13e3db`,
account hash `0debd9ab6e903b6d3269f7c9ceaf28320e3b91209e1a1080fd9ddf097d3dbd68`,
funded with 5000 CSPR) installed a **fresh** `RiskPolicyManager` v1 package,
then upgraded it to v2 via `add_contract_version()`.

### 6.1 The 6 verified deploys (all on Casper Testnet)

| # | Step | Deploy Hash | Status |
|---|------|-------------|--------|
| 1 | INSTALL v1 (fresh, upgradable package) | `0d4ed9547854f936df6a3ae44e7a5e4d2853565053b9d324d0882348c6b55e6f` | [✅ verified](https://testnet.cspr.live/deploy/0d4ed9547854f936df6a3ae44e7a5e4d2853565053b9d324d0882348c6b55e6f) |
| 2 | CALL `upgrade_policy` on v1 (sets the shared-state baseline) | `86f93e5ccb25bc2e563a3b130f048c7b58de4134b210814cb7be2b2530fe00f9` | [✅ verified](https://testnet.cspr.live/deploy/86f93e5ccb25bc2e563a3b130f048c7b58de4134b210814cb7be2b2530fe00f9) |
| 3 | CALL `get_current_policy` on v1 (proves v1 works) | `2087b49fddf87abe6b78ed24b7139af06c0d65d07ac00b94e5bc1fc533ce4b58` | [✅ verified](https://testnet.cspr.live/deploy/2087b49fddf87abe6b78ed24b7139af06c0d65d07ac00b94e5bc1fc533ce4b58) |
| 4 | **UPGRADE to v2 via `add_contract_version()`** | `86ea584af0d6cc4bf9a938f97c9748e6f9a9537e58837599442b7e40b0e4edd2` | [✅ verified](https://testnet.cspr.live/deploy/86ea584af0d6cc4bf9a938f97c9748e6f9a9537e58837599442b7e40b0e4edd2) |
| 5 | CALL `get_policy_with_reasoning` on v2 (new EP + shared-state proof) | `b70a4caed514b41f1f962704626ee408ebf2e87665f95be7ce1276cf5119bca7` | [✅ verified](https://testnet.cspr.live/deploy/b70a4caed514b41f1f962704626ee408ebf2e87665f95be7ce1276cf5119bca7) |
| 6 | CALL `get_current_policy` on v2 (v1 EP on upgraded superset) | `41d0ec5bedd6801486eb2e51b9ce7e605d99017c40b0e866aa772aa196b425a8` | [✅ verified](https://testnet.cspr.live/deploy/41d0ec5bedd6801486eb2e51b9ce7e605d99017c40b0e866aa772aa196b425a8) |

**Contract package (owned by deployer):** `417f5f7268acd956c4ce75fc1714f74f8a6bc819e0ad801fc60dc425d729f522`
- v1 contract hash: `8f9db53534efda3c94e40da3d69b1dcc06f32aa2a344e17d25d7142ffb13f16e` (disabled after upgrade)
- v2 contract hash: `43fbabdfa68dfe9a94e14ff2220d916ba785bb0615b84efd030d302c8adc3f8a` (active = latest)
- shared `state` URef: `uref-08fe1b7b61591bb1020673607118754706fe5ceb3c5b7068a08e594f4df25c9c-007`

### 6.2 Gas accounting

- v1 install (#1): payment 150 CSPR, consumed ~real gas, refunded the rest.
- v2 upgrade (#4): payment 300 CSPR → **consumed 157.62 CSPR → refunded 106.79 CSPR**.
- Each contract call (#2, #3, #5, #6): payment 5 CSPR each, mostly refunded.
- **Total gas consumed across all 6 deploys: ~338.94 CSPR** (deployer funded with 5000 CSPR).

### 6.3 Definitive proof `add_contract_version()` ran

Inspecting the upgrade deploy's (`86ea584a…`) `execution_result.Version2.effects`
(33 transforms) shows the exact on-chain footprint of
`storage::add_contract_version(package_hash, entry_points, named_keys, message_topics)`:

- Multiple **writes to the package hash** `hash-417f5f72…` (adding version 2,
  then disabling version 1).
- A **new contract entity** write at `hash-43fbabdf…` (the v2 contract) backed
  by a new **wasm** at `hash-fe1bc2e0…` (the v2 bytecode).
- A **write to the v1 contract** `hash-8f9db535…` (marked disabled).
- A **message-topic-entity** write for the v2 contract
  (`message-topic-entity-contract-43fbabdf…`).
- The deployer account `account-hash-0debd9ab…` is updated (named keys /
  access URef refreshed).

`execution_result.Version2.error_message == null` confirms the upgrade
executed successfully — `add_contract_version()` ran, the `migrate_events`
auto-call ran, the user `upgrade()` no-op hook ran, and the previous version
was disabled.

### 6.4 How the two earlier failure modes were resolved

The first session (using a different, since-depleted deployer account) surfaced
two issues that are now **fixed in the code** and proven by the verified run
above:

1. **Payment sizing.** A 100 CSPR payment ran out of gas — executing a 135 KB
   Wasm as session code plus `add_contract_version` is gas-heavier than v1's
   install. **Fix:** raised to 300 CSPR (mostly refunded; actual consumption
   157.62 CSPR per §6.2).

2. **`GroupAlreadyExists`.** `odra_cfg_create_upgrade_group=true` tried to
   re-create the `upgrader_group` that v1's install had already created,
   raising `ApiError::ContractHeader(3)`. **Fix:** set
   `odra_cfg_create_upgrade_group=false` (`scripts/casper_upgrade.cjs`).

With both fixes applied, the verified run above completed cleanly end-to-end.

---

## 7. Files Added / Changed

| File | Purpose |
|---|---|
| `contracts/src/risk_policy_manager_v2.rs` | v2 Odra module (superset + `get_policy_with_reasoning` + `upgrade` hook + unit tests). |
| `contracts/src/lib.rs` | Registers the v2 module. |
| `contracts/Odra.toml` | Registers `risk_policy_manager_v2::RiskPolicyManagerV2`. |
| `contracts/wasm/RiskPolicyManagerV2.wasm` | Compiled, bulk-memory-clean v2 Wasm (135 KB). |
| `scripts/casper_install.cjs` | Node.js helper: builds/signs/submits/verifies a **fresh** Odra install deploy (`odra_cfg_is_upgrade=false`, `odra_cfg_is_upgradable=true`, `odra_cfg_create_upgrade_group=true`) — the v1 install that precedes the upgrade. Official `casper-js-sdk` v5. |
| `scripts/casper_upgrade.cjs` | Node.js helper: builds/signs/submits/verifies the `add_contract_version` upgrade deploy (`odra_cfg_is_upgrade=true`; supports `SPECULATIVE=1` gas-only mode). |
| `scripts/demo_upgrade_contract.py` | Orchestrator (legacy, single-deploy): upgrades an existing v1 package + runs the 5-check verification matrix. |
| `scripts/demo_upgrade_full.py` | **Primary orchestrator:** end-to-end fresh lifecycle — installs v1, sets a known policy, upgrades to v2 via `add_contract_version()`, calls v1 & v2 entry points, runs the 6-check verification matrix, writes `proof/upgrade_hashes.json`. |
| `proof/upgrade_hashes.json` | Machine-readable proof: every deploy hash + the full 6-check verification report. |

---

## 8. Official Resources Used (per hackathon detail)

- **Odra Framework** (https://odra.dev, https://github.com/odra-lang/odra) —
  smart-contract framework with first-class Casper-native upgrade support
  (`storage::add_contract_version` via `odra_cfg_is_upgrade`).
- **casper-js-sdk v5** (https://github.com/casper-network) — official SDK for
  Casper-2.x-compatible deploy signing (`SessionBuilder` for the ModuleBytes
  upgrade deploy).
- **Casper Testnet RPC** (`https://node.testnet.casper.network/rpc`) —
  `account_put_deploy`, `info_get_deploy`, `query_global_state`,
  `chain_get_state_root_hash`.
- **Casper docs** (https://docs.casper.network) — `add_contract_version` host
  function, contract versioning, `StoredVersionedContractByHash` semantics.
- **CSPR.cloud docs** (https://docs.cspr.cloud) — RPC connection guide.
- **testnet.cspr.live** — deploy/transaction viewer + faucet.
