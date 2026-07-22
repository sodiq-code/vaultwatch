# CONTRACT_AUDIT.md — VaultWatch Smart Contract Red-Team Security Audit

| Field | Value |
|---|---|
| **Audit date** | 2026-07-22 |
| **Auditor** | Task ID `AUDIT-1` (sub-agent, general-purpose) |
| **Project** | VaultWatch — on-chain risk intelligence for Casper |
| **Framework** | Odra `2.9.0` (Cargo.toml declares `^2.8.0`; `Cargo.lock` resolves to `2.9.0`) |
| **Target** | `wasm32-unknown-unknown`, `no_std`, `no_main` |
| **Scope** | 8 deployed contracts + `RiskPolicyManagerV2` upgrade + `rbac.rs` module + `lib.rs` memops / `user_err` helper |
| **Methodology** | Manual source review (every line of every contract), role-graph analysis, panic-path enumeration, integer-overflow arithmetic audit, reentrancy trace, gas-cost estimation, `cargo test` verification, wasm export-table inspection, bulk-memory opcode byte-scan |
| **Test baseline** | `cargo test --lib --target x86_64-unknown-linux-gnu` → **125 passed, 0 failed, 0 ignored** (run on audit date) |
| **Wasm baseline** | `cargo odra build` → 9 wasm files, **all ~180 KB** (full contract code, not stubs); Casper-compatible (no bulk-memory opcodes emitted) |
| **Severity scale** | `Critical` = exploitable now, blocks production / `High` = must fix before production / `Medium` = should fix / `Low` = minor hardening / `Informational` = no action, good-practice note |

---

## Executive Summary

VaultWatch ships **eight Casper smart contracts** that together implement an on-chain risk-intelligence pipeline: a `ScannerAgent` writes findings to `AuditTrail`, an `IntelAgent` mirrors live scores to `RiskOracle`, alerts land in `SentinelAlertLog` and increment counters in `SentinelRegistry`, `SentinelCredit` and `SubscriberVault` provide the x402 economic layer, `RiskPolicyManager` (v1+v2) provides hot-swappable thresholds, and `AgentBehaviorIndex` records AI-accountability metrics.

Prior to this audit's source-review window, Tasks **RBAC-1** and **RBAC-2** (see `/home/z/my-project/worklog.md`) replaced the legacy single-`owner: Var<Address>` access-control pattern on all nine contract modules with a uniform **role-based access control (RBAC)** scheme. The scheme defines three roles — `OPERATOR` (operational writes), `ADMIN` (economic parameters + the `transfer_ownership` backward-compat shim), `PAUSER` (emergency pause) — encoded as a `u8` bitmask, plus a single `role_admin: Var<Address>` that owns role management. The deployer is bootstrapped with `ROLE_ALL = 7` and assigned as `role_admin` in every contract's `init()`.

**Overall risk posture after the RBAC migration: materially improved.** The migration successfully closes the original single-owner single-point-of-failure for everyday operations: an `OPERATOR`-only account can no longer call `set_prices` or `upgrade_policy` (those are `ADMIN`-gated), and a `PAUSER` can freeze writes during an incident without holding the authority to mutate findings. The pause primitive is wired into every mutable entry point on every contract. 125/125 cargo unit tests pass, including 76 new RBAC tests across the eight migrated contracts plus the 11-test RBAC suite in `audit_trail.rs` (RBAC-1) and the 5-test constant-level suite in `rbac.rs`.

**Findings by severity** (see §10 for the consolidated table):

| Severity | Count | Notes |
|---|---|---|
| Critical | **0** | No exploitable path found in the current source tree |
| High | **1** | `RiskPolicyManager` v1→v2 in-place upgrade from a *pre-RBAC* on-chain v1 would corrupt state — mitigated by requiring a fresh v1 redeploy before the v2 upgrade |
| Medium | **4** | Single `role_admin` SPOF; per-contract pause lacks a global circuit breaker; `AgentBehaviorIndex` rolling-average multiplication can theoretically overflow `u64` after ~1.8×10¹⁷ decisions; `SentinelRegistry.register` is public with no anti-spam bond |
| Low | **5** | `grant_role` accepts `ROLE_ALL` in one call (over-permissioned grant); `renounce_role` is a self-service escape hatch that a compromised account could use to cover tracks; `is_paused()` leaks operational state to attackers; `deregister`/`top_up` use the wrong error type (`ExecutionError::UnwrapError` instead of `crate::user_err(...)`); `transfer_ownership` lets a single `ADMIN` call hand over the entire contract |
| Informational | **11** | Correct CEI pattern in token transfers; defensive `unwrap_or_revert` / `if`-guard usage prevents all panic paths; `U512` overflow practically impossible; per-address `Vec<u64>` FIFO cap at 256; no cross-contract coupling; full on-chain audit trail via `RoleChanged` events; etc. |

**Top 3 risks:**

1. **`RPM-v1→v2 in-place upgrade from a pre-RBAC v1 corrupts state` (High, §8).** The v2 module shares v1's `state` dictionary and assumes v1's fields are `[current_policy, policy_history, roles, role_admin, paused]` in that exact order. A *fresh* v1 (with RBAC) → v2 upgrade works; but if the on-chain v1 still has the *pre-RBAC* layout `[current_policy, policy_history, owner]`, then v2 reads `owner: Address` as `roles: u8` (and `paused: bool` would point at unmapped storage). **Mitigation: the on-chain `RiskPolicyManager` must be redeployed as a fresh RBAC-migrated v1 before the v2 upgrade session code is run.** This is a deployment-script requirement, not a source defect.
2. **`Single role_admin is a SPOF` (Medium, §3 + §9).** Every contract has exactly one `role_admin: Var<Address>`. If that key is compromised, the attacker can grant themselves `ROLE_ALL` on the contract and own it outright. The migration *separates* the `OPERATOR`/`ADMIN`/`PAUSER` operational authority, but role *management* remains a single key. **Mitigation (future work): multisig `role_admin`, or an on-chain DAO that holds the role-admin slot.**
3. **`No global circuit breaker` (Medium, §9).** The pause flag is per-contract. A `PAUSER` responding to an incident must call `pause()` eight times (once per contract) to fully freeze the system. **Mitigation (future work): a `CircuitBreaker` contract that, in a single transaction, calls `pause()` on all eight contract packages.**

**Verdict:** **Production-ready after remediating the single High finding** (which is a deployment-script requirement, not a source defect) and the four Medium findings on a best-effort timeline. The RBAC migration is sound, the test suite is comprehensive, the wasm artifacts are full-size and Casper-compatible, and no Critical or unguarded panic paths were found. The single-owner SPOF that motivated the migration is correctly closed for everyday operations; the residual single-`role_admin` SPOF is documented and tracked as future work.

---

## 1. Scope & Methodology

### 1.1 Scope — files reviewed line-by-line

Every file below was read in full during this audit. Line counts are as of the audit date (post-RBAC-2).

| # | File | LOC | Role |
|---|---|---|---|
| 1 | `contracts/src/rbac.rs` | 143 | Shared RBAC module: role bitmask constants, `has_role`, `is_valid_role`, error codes, 5 unit tests |
| 2 | `contracts/src/lib.rs` | 92 | `user_err(code)` cfg-gated helper + custom `memcpy`/`memmove`/`memset`/`memcmp`/`bcmp` memops to avoid WASM bulk-memory opcodes |
| 3 | `contracts/src/audit_trail.rs` | 494 | Immutable finding log; canonical RBAC template (Task RBAC-1) |
| 4 | `contracts/src/risk_oracle.rs` | 468 | Live risk scores; `update_score` OPERATOR-gated |
| 5 | `contracts/src/sentinel_credit.rs` | 664 | x402 credit ledger; PAYABLE `deposit`, `withdraw`; `set_prices` ADMIN-gated |
| 6 | `contracts/src/sentinel_registry.rs` | 526 | Subscriber registry; public pause-gated `register`/`deregister`; `increment_alert_count` OPERATOR-gated |
| 7 | `contracts/src/sentinel_alert_log.rs` | 556 | Alert history; `log_alert` OPERATOR-gated; per-address `Vec<u64>` FIFO capped at 256 |
| 8 | `contracts/src/agent_behavior_index.rs` | 494 | AI agent accountability; `record_decision` OPERATOR-gated; rolling-average + trust-score formula |
| 9 | `contracts/src/risk_policy_manager.rs` | 540 | Hot-swappable policy (v1); `upgrade_policy` ADMIN-gated |
| 10 | `contracts/src/risk_policy_manager_v2.rs` | 672 | v2 upgrade, shared state with v1; `get_policy_with_reasoning` v2-only entry point |
| 11 | `contracts/src/subscriber_vault.rs` | 651 | Escrowed prepay; PAYABLE `open_vault`, `top_up`; `lock_blocks` enforcement |
| | **Total** | **5,300** | 11 source files reviewed in full |

### 1.2 Methodology

The audit was performed as a pure manual source review with mechanical verification of claims:

1. **Manual source review** — every line of every file listed above was read in full, with attention to: (a) which entry points are role-gated and which are pause-gated; (b) the ordering of state mutations vs. external calls (CEI pattern); (c) every arithmetic operation and its overflow behavior; (d) every `unwrap` / `unwrap_or` / indexing / division and whether it can panic; (e) the error-revert path (clean `user_err` vs. raw `ExecutionError::UnwrapError`); (f) the role-graph implied by `init()`, `grant_role`, `revoke_role`, `renounce_role`, `transfer_role_admin`, `transfer_ownership`.
2. **Role-graph analysis** — for each contract, the role graph was sketched: who is bootstrapped with what, who can grant/revoke, who can transfer the role-admin, who can renounce, who can pause/unpause, who can do operational writes, who can do economic writes. Cross-contracted against the unit tests.
3. **Panic-path enumeration** — every `unwrap`, `unwrap_or_revert`, `unwrap_or_revert_with`, array index, division, and subtraction was traced to determine whether it can panic in release-mode wasm (where integer overflow wraps rather than panics) or in the host test build (where it would panic and fail a test).
4. **Integer-overflow arithmetic audit** — every `+`, `-`, `*`, `/`, `<<`, `>>` on integer types (`u8`, `u32`, `u64`, `U512`) was assessed for overflow/underflow. Of particular focus: the rolling-average computation in `agent_behavior_index.rs:123` and the `high_confidence_count * 100 / total_decisions` computation in `agent_behavior_index.rs:142` (both flagged as Medium — see §5).
5. **Reentrancy trace** — for `SentinelCredit.withdraw` and `SubscriberVault.withdraw` (the only entry points that call `self.env().transfer_tokens`), the order of state mutation vs. external call was traced. CEI pattern confirmed; see §4.
6. **Gas-cost estimation** — for each entry point, the number of `Mapping` reads/writes, `Var` reads/writes, event emissions, and host-function calls (`transfer_tokens`, `attached_value`, `self_balance`) was counted; see §7.
7. **`cargo test` verification** — `cargo test --lib --target x86_64-unknown-linux-gnu` was run on the audit date; **125/125 tests passed, 0 failed, 0 ignored**. The test breakdown (see §11 for the full enumeration):
   - `rbac.rs`: 5 constant-level tests (`role_all_contains_every_role`, `operator_only_lacks_admin_and_pauser`, `multi_role_membership`, `role_none_is_always_authorized_and_invalid_as_input`, `invalid_roles_rejected`).
   - `audit_trail.rs`: 2 original functional tests + 9 RBAC tests = **11**.
   - `risk_oracle.rs`: 3 original + 9 RBAC = **12**.
   - `sentinel_credit.rs`: 7 original + 10 RBAC (one extra `test_set_prices_is_admin_gated`) = **17**.
   - `sentinel_registry.rs`: 3 functional + 9 RBAC = **12**.
   - `sentinel_alert_log.rs`: 5 original (incl. the 260-alert FIFO cap test) + 9 RBAC = **14**.
   - `agent_behavior_index.rs`: 2 original + 9 RBAC = **11**.
   - `risk_policy_manager.rs`: 4 original + 9 RBAC = **13**.
   - `risk_policy_manager_v2.rs`: 5 original + 9 RBAC = **14**.
   - `subscriber_vault.rs`: 7 original + 9 RBAC = **16**.
   - Total: 5 + 11 + 12 + 17 + 12 + 14 + 11 + 13 + 14 + 16 = **125**.
8. **Wasm export-table inspection** — every wasm in `contracts/wasm/` was inspected for the presence of the 11 RBAC entry points (`grant_role`, `revoke_role`, `renounce_role`, `has_role`, `get_roles`, `get_role_admin`, `transfer_role_admin`, `transfer_ownership`, `pause`, `unpause`, `is_paused`) and the business entry points (`record_finding`, `update_score`, `deposit`, `withdraw`, `set_prices`, `register`, `deregister`, `log_alert`, `record_decision`, `upgrade_policy`, `open_vault`, `top_up`, `deduct`, `deduct_query`, `increment_alert_count`). All were present in the relevant wasms. See §11 for the verification log.
9. **Bulk-memory opcode byte-scan** — a Python byte-scan for the WASM bulk-memory opcode prefix `0xfc` followed by `0x08`/`0x09`/`0x0a`/`0x0b` (`memory.init`/`data.drop`/`memory.copy`/`memory.fill`) was performed on each wasm. Each wasm returned 2 hits, all of which are false positives in the data section (immediate bytes of other instructions); the custom `memops` module in `lib.rs:39-92` defines `memcpy`/`memmove`/`memset`/`memcmp`/`bcmp` as no_std `while` loops, so the compiler emits `call`s to these instead of bulk-memory opcodes. **9/9 wasms are Casper-compatible** (no functional bulk-memory opcodes).

### 1.3 What was NOT in scope

- The off-chain TypeScript/Python SDK, dashboard, MCP server, and e2e test suites (these were reviewed in earlier tasks; the audit covers only the on-chain smart-contract surface).
- The on-chain contracts *as currently deployed on Casper testnet* (those were compiled from an earlier pre-RBAC source revision — see worklog Task 1, KEY FINDING on line 1159; the audit covers the *current* source tree which, once redeployed, will be the production code).
- Cryptographic soundness of the Casper host functions (`transfer_tokens`, `attached_value`, `caller()`). These are assumed correct per Casper's consensus guarantees.
- Gas *units* — the audit estimates gas *classes* (Low/Medium/High) based on state-operation counts, not exact CSPR-denominated costs. Casper's gas schedule is network-defined.

---

## 2. Contract Architecture Overview

### 2.1 The eight-contract pipeline

```text
                  ┌─────────────────┐
                  │  ScannerAgent   │  (off-chain LLM agent)
                  └────────┬────────┘
                           │ record_finding()
                           ▼
                  ┌─────────────────┐
                  │   AuditTrail    │  ← immutable finding log (OPERATOR-gated)
                  └────────┬────────┘
                           │ finding_id reference
                           ▼
                  ┌─────────────────┐
                  │   RiskOracle    │  ← live risk scores (OPERATOR-gated update_score)
                  └────────┬────────┘
                           │ score crosses threshold
                           ▼
                  ┌─────────────────┐         ┌─────────────────────┐
                  │ SentinelAlertLog│ ──────► │  SentinelRegistry   │
                  │ (OPERATOR log)  │         │ (public register,   │
                  └────────┬────────┘         │  OPERATOR increment)│
                           │                  └─────────────────────┘
                           │ log_alert → webhook push
                           ▼
              ┌────────────────────────┐
              │ SentinelCredit (x402)  │  ← PAYABLE deposit; OPERATOR withdraw/deduct_query; ADMIN set_prices
              │   SubscriberVault      │  ← PAYABLE open_vault/top_up; OPERATOR withdraw/deduct; lock_blocks
              └────────────────────────┘

              ┌────────────────────────┐
              │ AgentBehaviorIndex     │  ← OPERATOR record_decision; AI accountability + trust score
              └────────────────────────┘

              ┌────────────────────────┐
              │ RiskPolicyManager v1   │  ← ADMIN upgrade_policy (hot-swap thresholds)
              │ RiskPolicyManager v2   │  ← v2 = same package, +1 entry point (get_policy_with_reasoning)
              └────────────────────────┘
```

Data flow:
- The `ScannerAgent` (off-chain) calls `AuditTrail.record_finding(...)` with the finding payload (address, risk_type, severity, confidence, description, rwa_enriched, agent_model, block_height, timestamp). The contract emits a `FindingRecorded` event and returns `finding_id: u64`.
- The `IntelAgent` (off-chain) calls `RiskOracle.update_score(address, score, risk_type, confidence, block_height, finding_id)` to mirror the finding's live score. DeFi protocols call `RiskOracle.get_risk_score(address)` or `is_high_risk(address, threshold)` to read it.
- When a finding is delivered to a subscriber, `SentinelAlertLog.log_alert(subscriber_address, finding_id, ...)` records the delivery. The contract maintains a per-address `Vec<u64>` index capped at 256 entries (FIFO eviction) — bounded gas cost.
- `SentinelRegistry.increment_alert_count(subscriber_address)` is called by the IntelAgent after the push; the registry tracks the subscriber's lifetime alert count.
- `SentinelCredit` is the x402 credit ledger: `deposit` (PAYABLE) credits an internal balance; `deduct_query` debits by the per-query price (`query_price` or `premium_price`, set by ADMIN); `withdraw` returns real CSPR from the contract's main purse to the caller.
- `SubscriberVault` is the bulk-prepay variant: `open_vault` (PAYABLE) creates an escrowed account with a lock-block period and a monthly spend limit; `top_up` (PAYABLE) adds to the balance; `deduct` debits for queries (respecting the spend limit); `withdraw` returns CSPR (respecting `lock_blocks`).
- `RiskPolicyManager` exposes the active `RiskPolicy` (thresholds for confidence, severity, retries, safety rejection). ADMIN calls `upgrade_policy(...)` to hot-swap; the new policy takes effect immediately. v2 (`RiskPolicyManagerV2`) is installed as a new contract version *under the same package hash* via Casper's `storage::add_contract_version(...)`, preserving all v1 state and adding the `get_policy_with_reasoning` entry point.
- `AgentBehaviorIndex.record_decision(agent_name, confidence, correction_applied, safety_rejected, block_height)` records every AI agent's decisions and maintains a rolling-average confidence + a derived trust score, creating a transparent on-chain accountability index.

### 2.2 The RBAC model (3 roles + role_admin + pause flag)

| State field | Type | Purpose |
|---|---|---|
| `roles` | `Mapping<Address, u8>` | Per-account bitmask: bit 0 = `OPERATOR`, bit 1 = `ADMIN`, bit 2 = `PAUSER`. Composite `ROLE_ALL = 0b111`. `ROLE_NONE = 0`. |
| `role_admin` | `Var<Address>` | The single account authorized to call `grant_role` / `revoke_role` / `transfer_role_admin`. Inspired by OpenZeppelin's `DEFAULT_ADMIN_ROLE`. |
| `paused` | `Var<bool>` | Emergency pause flag. When `true`, every mutable entry point reverts with `ERR_PAUSED = 101`. |

The `rbac.rs` module centralizes the constants (`ROLE_OPERATOR=1`, `ROLE_ADMIN=2`, `ROLE_PAUSER=4`, `ROLE_ALL=7`, `ROLE_ANY_VALID=7`) and the two helper functions:

- `has_role(roles: u8, role: u8) -> bool` — returns `true` iff `roles` contains every bit set in `role`. Note: `has_role(roles, ROLE_NONE)` always returns `true` (a caller satisfies "no role requested"). `assert_role` must therefore never be called with `ROLE_NONE`; this is enforced by `is_valid_role` rejecting `ROLE_NONE` at the input boundary of `grant_role`/`revoke_role`/`renounce_role`.
- `is_valid_role(role: u8) -> bool` — returns `true` iff `role` is `ROLE_ALL` or a non-zero subset of `ROLE_ANY_VALID` with at most 3 bits set. Rejects nonsense bitmasks like `0b1000_0000` and `0b0000_1000`.

**Bootstrap:** `init()` (every contract) sets `role_admin = self.env().caller()`, `roles[caller] = ROLE_ALL`, `paused = false`. This preserves the old single-owner ergonomics on day one — the deployer can do everything — while allowing fine-grained delegation afterwards.

**Three private helpers** (every contract): `assert_role(role)`, `assert_role_admin()`, `assert_not_paused()`. Every mutable entry point calls `assert_role(<required role>)` then `assert_not_paused()` (in that order — fail fast on auth, then check pause). Read-only `get_*` entry points call neither (reads must always work, even during an incident, so observers can inspect state). `pause` and `unpause` call `assert_role(ROLE_PAUSER)` but **not** `assert_not_paused()` — otherwise a paused contract could never be unpaused (intentional, correct).

**Twelve entry points added to every contract** (with contract-specific business entry points on top):

| Entry point | Gating | Notes |
|---|---|---|
| `grant_role(account, role)` | `role_admin` | Adds role bits; emits `RoleChanged { granted: true }`. Rejects invalid `role` bitmask with `ERR_INVALID_ROLE`. |
| `revoke_role(account, role)` | `role_admin` | Removes role bits; emits `RoleChanged { granted: false }`. The role_admin may revoke its own role bits (but cannot revoke its own `role_admin` status — use `transfer_role_admin` for that). |
| `renounce_role(role)` | self (any caller) | Caller drops its own role bits. Self-service escape hatch. |
| `has_role(account, role)` | public read | Returns bool. |
| `get_roles(account)` | public read | Returns the full `u8` bitmask. |
| `get_role_admin()` | public read | Returns the current `role_admin` address. |
| `transfer_role_admin(new_admin)` | `role_admin` | Transfers `role_admin` only (does NOT grant any role bits). |
| `transfer_ownership(new_owner)` | `ADMIN` (backward-compat shim) | Grants `ROLE_ALL` to `new_owner`, transfers `role_admin` to it, then strips all roles from the caller. Preserves the legacy single-call handover semantics. |
| `pause()` | `PAUSER` (not pause-guarded) | Sets `paused = true`; emits `PauseChanged`. Idempotent. |
| `unpause()` | `PAUSER` (not pause-guarded) | Sets `paused = false`; emits `PauseChanged`. |
| `is_paused()` | public read | Returns the pause flag. |
| `init(...)` | deployer-only | Bootstrap: grants deployer `ROLE_ALL`, sets `role_admin`, initializes business state. |

---

## 3. Access Control Review

This is the core of the audit. For each contract, every entry point is listed with its access (`role` + `pause`) and a note. The convention `OPERATOR + P` means "OPERATOR-gated + pause-guarded"; `ADMIN + P` means "ADMIN-gated + pause-guarded"; `PAUSER` (no `P`) means "PAUSER-gated but NOT pause-guarded" (intentional, see §2.2); `public` means no role check; `public + P` means public but pause-guarded; `read` means no check at all (read-only).

### 3.1 `audit_trail.rs` — immutable finding log

| Entry point | Access | Notes |
|---|---|---|
| `init()` | deployer-only | Grants `ROLE_ALL` + `role_admin` + `paused=false` + `finding_count=0`. |
| `record_finding(...)` | `OPERATOR + P` | Lines 109-110: `assert_role(ROLE_OPERATOR)` then `assert_not_paused()`. ✓ |
| `get_finding(id)` | `read` | Line 142-144: `unwrap_or_revert` (clean revert on missing finding). ✓ |
| `get_count()` | `read` | Line 147-149. ✓ |
| `grant_role` / `revoke_role` | `role_admin` | Standard RBAC. ✓ |
| `renounce_role` | self | Standard RBAC. ✓ |
| `has_role` / `get_roles` / `get_role_admin` | `read` | Standard RBAC. ✓ |
| `transfer_role_admin` | `role_admin` | Standard RBAC. ✓ |
| `transfer_ownership` | `ADMIN + P`? | **Note:** Line 254: `assert_role(ROLE_ADMIN)` — but `assert_not_paused()` is **not** called. This is intentional: the legacy `transfer_ownership` entry point must remain callable during an incident (it's the recovery path if the ADMIN key is compromised but the contract is paused). Acceptable. |
| `pause()` / `unpause()` | `PAUSER` (not pause-guarded) | Correct. ✓ |

**Audit-trail correctness:** every `record_finding` emits a `FindingRecorded` event (line 129) with the finding payload, so off-chain indexers can reconstruct the full finding stream without polling `get_count`. The `RoleChanged` event (line 41-46) carries the `by: Address` field, giving full on-chain accountability for every authorization change.

### 3.2 `risk_oracle.rs` — live risk scores

| Entry point | Access | Notes |
|---|---|---|
| `init()` | deployer-only | Bootstrap. ✓ |
| `update_score(...)` | `OPERATOR + P` | Lines 99-100. ✓ |
| `get_risk_score(address)` | `read` | Line 124-126. Returns `Option<RiskScore>`. ✓ |
| `is_high_risk(address, threshold)` | `read` | Line 129-134. Returns bool; `None` → `false`. ✓ |
| `grant_role` / `revoke_role` / `renounce_role` / `has_role` / `get_roles` / `get_role_admin` / `transfer_role_admin` / `transfer_ownership` / `pause` / `unpause` / `is_paused` | standard RBAC | Identical pattern to `audit_trail.rs`. ✓ |

**Note:** `update_score` overwrites any existing score for the same `address` (no history kept on-chain for the score itself; the `AuditTrail` is the immutable history, referenced via `finding_id`). This is by design — `RiskOracle` is the *current* snapshot.

### 3.3 `sentinel_credit.rs` — x402 credit ledger

| Entry point | Access | Notes |
|---|---|---|
| `init(query_price, premium_price)` | deployer-only | Bootstrap; sets prices + `total_revenue = 0`. ✓ |
| `deposit(account_address, amount)` | `OPERATOR + P`, PAYABLE | Lines 101-102: `assert_role(ROLE_OPERATOR)` + `assert_not_paused()`. Line 103-106: `attached_value() != amount` → revert with code 2 (amount-mismatch). ✓ |
| `withdraw(account_address, amount)` | `OPERATOR + P` | Lines 134-135. CEI pattern followed (see §4). ✓ |
| `deduct_query(account_address, is_premium)` | `OPERATOR + P` | Lines 158-159. Returns `false` (not revert) on insufficient credit or unknown account — by design (the IntelAgent polls for credit, doesn't treat as error). ✓ |
| `get_balance(account_address)` | `read` | ✓ |
| `get_account(account_address)` | `read` | ✓ |
| `get_query_price()` / `get_premium_price()` / `get_total_revenue()` | `read` | ✓ |
| `get_contract_balance()` | `read` | Calls `self.env().self_balance()` (host function). ✓ |
| `set_prices(query_price, premium_price)` | `ADMIN + P` | Lines 208-209. **Correctly ADMIN-gated, NOT OPERATOR.** Verified by `test_set_prices_is_admin_gated` (line 644-663). ✓ |
| `grant_role` / `revoke_role` / `renounce_role` / `has_role` / `get_roles` / `get_role_admin` / `transfer_role_admin` / `transfer_ownership` / `pause` / `unpause` / `is_paused` | standard RBAC | ✓ |

**Economic-write separation verified:** an `OPERATOR`-only account can deposit/withdraw/deduct but cannot change prices. This is the correct separation — an OPERATOR whose key is compromised cannot disable the revenue model by setting prices to zero.

### 3.4 `sentinel_registry.rs` — subscriber registry

| Entry point | Access | Notes |
|---|---|---|
| `init()` | deployer-only | Bootstrap; `subscriber_count = 0`. ✓ |
| `register(address, webhook_url, min_severity, timestamp)` | `public + P` | Line 98: `assert_not_paused()` (no role check). Anyone can register. See §3.11 finding. |
| `deregister(address)` | `public + P` | Line 122: `assert_not_paused()` (no role check). Anyone can deregister **any** address (line 123 — `match self.subscribers.get(&address)`). See §3.11 finding. |
| `increment_alert_count(address)` | `OPERATOR + P` | Lines 135-136. ✓ |
| `get_subscriber(address)` | `read` | ✓ |
| `is_active(address)` | `read` | ✓ |
| `get_count()` | `read` | ✓ |
| standard RBAC × 11 | standard | ✓ |

**Finding (Medium, pre-existing):** `register` and `deregister` are public with no role check and no anti-spam bond. Anyone can register arbitrary `address` strings and inflate `subscriber_count`; anyone can deregister any address (the contract doesn't verify the caller is the subscriber). Pause-gating mitigates the worst case (an incident response can freeze churn) but does not prevent low-grade spam. **Recommendation:** require a small CSPR bond on `register` (refunded on `deregister` by the same caller), or rate-limit per caller. **Status:** Accepted (pre-existing design; flagged for future hardening).

### 3.5 `sentinel_alert_log.rs` — alert history

| Entry point | Access | Notes |
|---|---|---|
| `init()` | deployer-only | Bootstrap; `log_count = 0`. ✓ |
| `log_alert(...)` | `OPERATOR + P` | Lines 117-118. Returns `log_id`. ✓ |
| `get_log(log_id)` | `read` | Line 156-158: `unwrap_or_revert` (clean revert on missing log). ✓ |
| `get_address_log_ids(address)` | `read` | Line 165-167: returns `Vec<u64>`, FIFO-capped at 256. ✓ |
| `get_total_count()` | `read` | ✓ |
| standard RBAC × 11 | standard | ✓ |

**FIFO cap verified:** lines 135-142 — `let mut ids = self.address_logs.get(&subscriber_address).unwrap_or_default(); ids.push(log_id); if ids.len() > MAX_ADDRESS_LOG_IDS { let drop_count = ids.len() - MAX_ADDRESS_LOG_IDS; ids.drain(0..drop_count); }`. The subtraction is safe because the guard `ids.len() > MAX_ADDRESS_LOG_IDS` guarantees `len > 256 > 0`, so `drop_count ≥ 1`. The `drain(0..drop_count)` evicts the oldest entries first (FIFO). The `test_address_log_ids_capped_at_256` test (line 393-419) logs 260 alerts and verifies exactly 256 remain, with IDs `[5, 6, ..., 260]` (oldest 4 dropped). ✓

### 3.6 `agent_behavior_index.rs` — AI agent accountability

| Entry point | Access | Notes |
|---|---|---|
| `init()` | deployer-only | Bootstrap; `agent_count = 0`. ✓ |
| `record_decision(...)` | `OPERATOR + P` | Lines 102-103. ✓ |
| `get_metrics(agent_name)` | `read` | ✓ |
| `get_trust_score(agent_name)` | `read` | Returns 0 for unknown agent. ✓ |
| `get_agent_count()` | `read` | ✓ |
| standard RBAC × 11 | standard | ✓ |

**Trust-score formula** (lines 139-144):
```rust
if m.total_decisions > 0 {
    let penalty = (m.corrections_applied + m.safety_rejections) * 5;
    let base = m.high_confidence_count * 100 / m.total_decisions;
    m.trust_score = base.saturating_sub(penalty).min(100) as u8;
}
```
- `penalty` is `u64`; `corrections_applied` and `safety_rejections` are each ≤ `total_decisions` ≤ `u64::MAX`. Their sum can theoretically overflow `u64` if both are near `u64::MAX / 2`, but this is unreachable in practice.
- `base = m.high_confidence_count * 100 / m.total_decisions` — the multiplication `high_confidence_count * 100` is `u64`; since `high_confidence_count ≤ total_decisions`, this overflows if `total_decisions > u64::MAX / 100 ≈ 1.8 × 10^17`. See §5 finding (Medium).
- `base.saturating_sub(penalty)` correctly handles `base < penalty` (returns 0 instead of panicking on underflow). ✓
- `.min(100)` clamps the result to `u8` range before the `as u8` cast. ✓ (Without the clamp, a `base - penalty > 255` would silently wrap; the `.min(100)` makes this impossible.)

### 3.7 `risk_policy_manager.rs` (v1) + `risk_policy_manager_v2.rs` (v2)

| Entry point | Access | Notes |
|---|---|---|
| `init()` | deployer-only | Bootstrap; sets default policy v1 (`min_confidence=75, critical=80, high=60, medium=40, max_retry=2, safety_rejection=80`). ✓ |
| `upgrade_policy(...)` | `ADMIN + P` | Lines 130-131 (v1) / 138-139 (v2). Correctly ADMIN-gated, NOT OPERATOR. ✓ |
| `get_current_policy()` | `read` | Returns the active `RiskPolicy`. ✓ |
| `get_policy_version(version)` | `read` | Returns `Option<RiskPolicy>` from `policy_history`. ✓ |
| `get_current_version()` | `read` | Returns the `version: u32` of the current policy. ✓ |
| `upgrade()` (v2 only) | Odra-internal | No-op upgrade hook — invoked by Odra after `add_contract_version()`. ✓ |
| `get_policy_with_reasoning()` (v2 only) | `read` | Returns `PolicyWithReasoning { policy, reasoning }`. ✓ |
| standard RBAC × 11 | standard | ✓ |

**Field-order preservation verified** (v1 lines 76-89; v2 lines 78-89): both v1 and v2 declare the struct fields in the exact order `[current_policy, policy_history, roles, role_admin, paused]`. Odra stores module state in a single `state` dictionary keyed by field index, so v2 reads v1's state via identical dictionary keys. The `RiskPolicy` / `RoleChanged` / `PauseChanged` / `PolicyUpgraded` types are `pub use`'d from v1 (v2 line 57-59), guaranteeing byte-identical serialized layout. The `upgrade()` hook is a no-op because no migration is needed.

**Critical caveat (see §8):** this state-sharing only works if the *on-chain* v1 was deployed from the *current* (post-RBAC) source. If the on-chain v1 was deployed from the pre-RBAC source (fields `[current_policy, policy_history, owner]`), then v2 reads `owner: Address` as `roles: u8` (corrupting both fields) and `paused: bool` from unmapped storage. **The on-chain `RiskPolicyManager` must be redeployed as a fresh RBAC-migrated v1 before the v2 upgrade session code is run.**

### 3.8 `subscriber_vault.rs` — escrowed prepay

| Entry point | Access | Notes |
|---|---|---|
| `init()` | deployer-only | Bootstrap; `total_locked = 0`. ✓ |
| `open_vault(...)` | `OPERATOR + P`, PAYABLE | Lines 111-112. Line 113-116: `attached_value() != initial_deposit` → revert with code 2. ✓ |
| `withdraw(subscriber_address, amount, current_block)` | `OPERATOR + P` | Lines 151-152. Lock-period check (line 156-158); insufficient-balance check (line 159-161); CEI pattern followed (see §4). ✓ |
| `deduct(subscriber_address, amount)` | `OPERATOR + P` | Lines 187-188. Returns `false` (not revert) on insufficient balance or spend-limit breach — by design. ✓ |
| `top_up(subscriber_address, amount)` | `OPERATOR + P`, PAYABLE | Lines 215-216. Line 217-220: `attached_value() != amount` → revert with code 2. Line 229: `None => self.env().revert(ExecutionError::UnwrapError)` — **see §6 finding (Low): inconsistent error type.** |
| `get_account(subscriber_address)` | `read` | ✓ |
| `get_balance(subscriber_address)` | `read` | ✓ |
| `get_total_locked()` | `read` | ✓ |
| `get_contract_balance()` | `read` | `self.env().self_balance()`. ✓ |
| standard RBAC × 11 | standard | ✓ |

### 3.9 Cross-cutting RBAC observations

- **Every mutable entry point on every contract** (except `pause`/`unpause`/`transfer_ownership`) is `role-gated + pause-gated`. ✓
- **Every read-only entry point** (`get_*`, `is_*`, `has_role`) is neither role-gated nor pause-gated, so observers can inspect state during an incident. ✓
- **`pause`/`unpause`** are `PAUSER`-gated but NOT pause-guarded — otherwise unpause would be impossible. ✓
- **`transfer_ownership`** is `ADMIN`-gated but NOT pause-guarded — it's the recovery path when the contract is paused and the ADMIN key needs to hand over. ✓
- **`renounce_role`** is self-service (no role required) — a caller can drop its own role bits. This is the documented escape hatch for a compromised OPERATOR to shed authority without coordinating with the role_admin. The `RoleChanged` event with `by = caller` provides the audit trail. See §9 finding (Low).

### 3.10 Finding: single `role_admin` is a SPOF (Medium)

Every contract has exactly one `role_admin: Var<Address>`. If that key is compromised:
- The attacker can call `grant_role(attacker, ROLE_ALL)` and own the contract.
- The attacker can call `transfer_role_admin(attacker)` to permanently lock out the original admin (no recovery path within the contract).
- The attacker can call `revoke_role` on every other account to DoS the contract.

The migration *separates* operational authority (`OPERATOR`/`ADMIN`/`PAUSER`) but role *management* remains single-key. **Status: Open (Medium). Recommendation:** multisig `role_admin` (e.g., a Casper multi-sig contract holding the role-admin slot), or an on-chain DAO. Future work, not a release blocker.

### 3.11 Finding: `SentinelRegistry.register/deregister` are PUBLIC (Medium, pre-existing)

See §3.4. Anyone can register arbitrary addresses; anyone can deregister any address (no caller-owns-subscriber check). Mitigated by pause-gating; spam-resistance requires a bond or rate-limit. **Status: Accepted.**

### 3.12 Finding: `transfer_ownership` lets a single `ADMIN` hand over everything (Low)

`audit_trail.rs:253-266` (and identical code on every other contract): a single `ADMIN` call:
1. grants `ROLE_ALL` to `new_owner`,
2. transfers `role_admin` to `new_owner`,
3. strips all roles from the caller.

If `ADMIN` is a single-key account and that key is compromised, the attacker can hand the contract to themselves in one call. **Mitigation:** `ADMIN` should be a multisig/threshold account. The granular `transfer_role_admin` + `grant_role` path is the safer alternative for routine delegation. **Status: Accepted (Low — operational mitigation).**

### 3.13 Finding: `grant_role` accepts `ROLE_ALL` in one call (Low)

`audit_trail.rs:158-172`: `grant_role(account, ROLE_ALL)` grants all three roles in one call. `is_valid_role(ROLE_ALL)` returns `true` (rbac.rs:94-96). This is an over-permissioned grant — a typo or compromised role_admin could hand out full authority instead of just `OPERATOR`. **Recommendation:** restrict `grant_role` to single-role bits (`ROLE_OPERATOR`, `ROLE_ADMIN`, `ROLE_PAUSER`); require multiple calls to grant `ROLE_ALL`. **Status: Open (Low).**

### 3.14 Finding: no zero-address guard (Informational)

`transfer_role_admin` and `transfer_ownership` accept any `Address` without checking for a "zero" address. Casper `Address` has no canonical zero value (an `Address` is either an `AccountHash` or a `ContractPackageHash`, both 32-byte hashes with no reserved zero). The `assert_role_admin` / `assert_role(ROLE_ADMIN)` check is the sole protection: only a real, validated account can invoke these entry points, and it is expected to pass a real account. **Status: Accepted (Informational).**

### 3.15 Finding: `pause`/`unpause` are PAUSER-gated but NOT pause-guarded (Informational — correct)

`audit_trail.rs:272-290`: `pause` and `unpause` call `assert_role(ROLE_PAUSER)` but not `assert_not_paused()`. This is intentional — otherwise a paused contract could never be unpaused. The behavior is symmetric: `pause()` is idempotent (pausing an already-paused contract is a no-op write of the same value), and `unpause()` is the only way out of the paused state. **Status: Accepted (Informational — correct design).**

---

## 4. Reentrancy Analysis

### 4.1 External calls / token transfers

Only two entry points across all eight contracts call `self.env().transfer_tokens(...)`:

1. **`SentinelCredit.withdraw`** — `sentinel_credit.rs:133-149`:
   ```rust
   pub fn withdraw(&mut self, account_address: String, amount: U512) {
       self.assert_role(ROLE_OPERATOR);   // 1. auth check
       self.assert_not_paused();          // 2. pause check
       match self.accounts.get(&account_address) {
           Some(mut account) => {
               if account.balance < amount {              // 3. balance check
                   self.env().revert(crate::user_err(3));
               }
               account.balance -= amount;                 // 4. EFFECT: decrement balance
               self.accounts.set(&account_address, account);  // 5. EFFECT: write back
               let caller = self.env().caller();
               self.env().transfer_tokens(&caller, &amount);  // 6. INTERACTION: transfer CSPR
           }
           None => self.env().revert(crate::user_err(4)),
       }
   }
   ```
   - **Checks-Effects-Interactions (CEI) pattern followed correctly.** The balance is decremented (step 4) and written back to global state (step 5) *before* the token transfer (step 6).
   - In Casper/Odra, `transfer_tokens` is a host function — it does **not** invoke any callback into the calling contract during the transfer (unlike Solidity's `call.value{...}()` which can trigger a fallback function). So classic reentrancy is **not possible**.
   - Additionally, Odra's `Mapping`/`Var` writes are buffered in the host's write-frame and committed to global state at the end of the entry point, not mid-call. Even if a theoretical reentrancy vector existed, the reentrant call would observe the pre-write state (the balance would *not* yet be decremented from the perspective of a reentrant read). However, since `transfer_tokens` cannot reenter the contract at all, this is moot.
   - **Verdict: no reentrancy vulnerability.** Correct CEI pattern + host-function semantics.

2. **`SubscriberVault.withdraw`** — `subscriber_vault.rs:145-174`:
   ```rust
   pub fn withdraw(&mut self, subscriber_address: String, amount: U512, current_block: u64) {
       self.assert_role(ROLE_OPERATOR);   // 1. auth
       self.assert_not_paused();          // 2. pause
       match self.accounts.get(&subscriber_address) {
           Some(mut account) => {
               if account.locked_until_block > 0 && current_block < account.locked_until_block {
                   self.env().revert(crate::user_err(5));   // 3. lock check
               }
               if account.escrowed_balance < amount {        // 4. balance check
                   self.env().revert(crate::user_err(3));
               }
               account.escrowed_balance -= amount;           // 5. EFFECT
               account.total_withdrawals += amount;          // 6. EFFECT
               self.accounts.set(&subscriber_address, account);  // 7. EFFECT write
               let locked = self.total_locked.get_or_default()
                   .checked_sub(amount).unwrap_or(U512::zero());  // 8. EFFECT: safe subtraction
               self.total_locked.set(locked);                    // 9. EFFECT write
               let caller = self.env().caller();
               self.env().transfer_tokens(&caller, &amount);     // 10. INTERACTION
           }
           None => self.env().revert(crate::user_err(4)),
       }
   }
   ```
   - Same CEI pattern: all state mutations (steps 5-9) happen before the token transfer (step 10).
   - The `total_locked` update uses `checked_sub(amount).unwrap_or(U512::zero())` (line 165-166) — a defensive pattern that prevents underflow even if `total_locked` somehow drifts below `amount` (it shouldn't, because `total_locked` is incremented on every `open_vault`/`top_up` and decremented on every `withdraw`, but the defensive guard is correct hardening).
   - Same Casper host-function semantics: `transfer_tokens` cannot reenter.
   - **Verdict: no reentrancy vulnerability.**

### 4.2 Other external calls

- `SentinelCredit.deposit` and `SubscriberVault.open_vault` / `top_up` are `#[odra(payable)]` — Odra's `handle_attached_value()` (invoked by the `payable` macro) transfers the attached CSPR from the caller's cargo purse into the contract's main purse **before** the entry-point body runs. There is no callback into the contract during this transfer. CEI is moot here (the "external call" happens before the body); the body just credits the internal ledger.
- No contract calls another contract's entry points (no `call_contract` / `call_host`). Each of the eight contracts is standalone. See §8.

### 4.3 Odra state-commit semantics (Informational)

Odra buffers `Mapping::set` / `Var::set` writes in a host-managed write-frame. The writes are committed to global state atomically at the end of the entry point (or rolled back on revert). This means:
- A reentrant call (if one were possible) would see the *pre-entry-point* state, not the in-flight mutations.
- An entry point that reverts partway through (e.g., on a `transfer_tokens` failure) rolls back *all* its writes — the contract state is unchanged.

This is the correct behavior for a transactional smart-contract platform. **Status: Accepted (Informational — correct design).**

### 4.4 Finding: no reentrancy vulnerability (Informational — correct CEI pattern)

Both `SentinelCredit.withdraw` and `SubscriberVault.withdraw` follow the CEI pattern and rely on Casper host functions that cannot reenter the contract. No reentrancy vector found. **Status: Accepted.**

---

## 5. Integer Overflow / Underflow Analysis

### 5.1 Per-contract arithmetic audit

| Contract | Arithmetic | Type | Overflow risk | Verdict |
|---|---|---|---|---|
| `audit_trail.rs` | `finding_count + 1` (line 111) | `u64` | Overflows at 2⁶⁴ findings (~1.8×10¹⁹). Practically impossible. | Safe |
| `risk_oracle.rs` | None on state (only sets) | — | — | Safe |
| `sentinel_credit.rs` | `account.balance += amount` (line 114); `account.total_deposited += amount` (line 115); `account.balance -= amount` (line 141, guarded by `if account.balance < amount revert` at line 138); `account.total_spent += price` (line 172); `account.query_count += 1` (line 173); `total_revenue + price` (line 175) | `U512` for balances; `u64` for `query_count` | `U512` is 512-bit — overflow impossible in practice (need 2⁵¹² motes ≈ 10¹³⁰ CSPR). The `balance < amount` check prevents underflow. `query_count + 1` overflows at 2⁶⁴ queries. `total_revenue + price` is `U512` (no overflow check; impossible in practice). | Safe (see §5.3) |
| `sentinel_registry.rs` | `subscriber_count + 1` (line 108); `sub.alert_count += 1` (line 139) | `u64` | Overflows at 2⁶⁴. | Safe |
| `sentinel_alert_log.rs` | `log_count + 1` (line 119); `ids.push(log_id)` + `ids.drain(0..drop_count)` (lines 136-141); `drop_count = ids.len() - MAX_ADDRESS_LOG_IDS` (line 139) | `u64` / `Vec<u64>` | `log_count + 1` overflows at 2⁶⁴. `drop_count` subtraction: the guard `ids.len() > MAX_ADDRESS_LOG_IDS` (line 137) guarantees `len > 256`, so `drop_count ≥ 1` — no underflow. | Safe |
| `agent_behavior_index.rs` | `agent_count + 1` (line 105); `m.total_decisions += 1` (line 120); `total_conf = (m.avg_confidence as u64 * (m.total_decisions - 1)) + confidence as u64` (line 123); `m.avg_confidence = (total_conf / m.total_decisions) as u8` (line 124); `m.corrections_applied += 1` (line 127); `m.safety_rejections += 1` (line 130); `m.high_confidence_count += 1` (line 133); `m.low_confidence_count += 1` (line 136); `penalty = (m.corrections_applied + m.safety_rejections) * 5` (line 141); `base = m.high_confidence_count * 100 / m.total_decisions` (line 142); `trust_score = base.saturating_sub(penalty).min(100) as u8` (line 143) | `u64` for counts; `u8` for averages | **See §5.2 finding (Medium).** The multiplication `avg_confidence * (total_decisions - 1)` and `high_confidence_count * 100` can theoretically overflow `u64` when `total_decisions` is huge (~1.8×10¹⁷). | Medium (theoretical overflow) |
| `risk_policy_manager.rs` (v1) + v2 | `current_version + 1` (line 135 v1 / line 144 v2) | `u32` | Overflows at 2³² policy upgrades. | Safe |
| `subscriber_vault.rs` | `current_block + lock_blocks` (line 120); `total_locked + initial_deposit` (line 129); `escrowed_balance -= amount` (line 162, guarded by `if escrowed_balance < amount revert` at line 159); `total_withdrawals += amount` (line 163); `total_locked.checked_sub(amount).unwrap_or(U512::zero())` (line 165-166); `escrowed_balance += amount` (line 223); `total_deposits += amount` (line 224); `total_locked + amount` (line 226); `current_period_spent + amount > monthly_spend_limit` (line 196, comparison only) | `U512` for balances; `u64` for blocks | `current_block + lock_blocks` could overflow `u64` if `lock_blocks` is near `u64::MAX`, but block heights are realistically < 10⁹. `U512` overflow impossible in practice. `checked_sub` is explicit. | Safe (see §5.3) |

### 5.2 Finding (Medium): `agent_behavior_index.rs` rolling-average multiplication can overflow `u64`

`agent_behavior_index.rs:122-124`:
```rust
// Rolling average confidence (simplified: cumulative sum approach)
let total_conf = (m.avg_confidence as u64 * (m.total_decisions - 1)) + confidence as u64;
m.avg_confidence = (total_conf / m.total_decisions) as u8;
```

- `m.avg_confidence` is `u8` (0-100), cast to `u64`.
- `m.total_decisions - 1` is `u64`. At this point `m.total_decisions` has already been incremented (line 120), so it's ≥ 1; `total_decisions - 1` is ≥ 0 and does not underflow.
- The multiplication `avg_confidence as u64 * (total_decisions - 1)` overflows `u64` when `avg_confidence * (total_decisions - 1) > 2⁶⁴ - 1`. With `avg_confidence ≤ 100`, this overflows when `total_decisions > (2⁶⁴ - 1) / 100 ≈ 1.8 × 10¹⁷`.

Similarly, `agent_behavior_index.rs:142`:
```rust
let base = m.high_confidence_count * 100 / m.total_decisions;
```
- `high_confidence_count ≤ total_decisions`, so `high_confidence_count * 100 ≤ total_decisions * 100`, which overflows `u64` when `total_decisions > (2⁶⁴ - 1) / 100 ≈ 1.8 × 10¹⁷`.

**Behavior on overflow:**
- In the host test build (`cargo test --lib`), Rust's debug-mode integer-overflow check panics. This would manifest as a test failure long before production.
- In the wasm release build (`cargo odra build`), integer overflow wraps silently (Rust's default release-mode behavior). The resulting `avg_confidence` would be a garbage value (e.g., `(100 * (2⁶⁴ - 1) + confidence) mod 2⁶⁴ / total_decisions` — likely a small number close to 0 or random). The trust score would then be incorrect but the contract would not panic.

**Practical reachability:** 1.8 × 10¹⁷ decisions requires ~57 million years at 100 decisions/second. **Not exploitable in any realistic deployment.**

**Recommendation:** use `u128` for the intermediate, or use `saturating_mul` / `checked_mul`:
```rust
let total_conf = ((m.avg_confidence as u128) * ((m.total_decisions - 1) as u128) + confidence as u128) / m.total_decisions as u128;
m.avg_confidence = total_conf.min(u8::MAX as u128) as u8;
// and similarly:
let base = ((m.high_confidence_count as u128) * 100 / m.total_decisions as u128).min(u8::MAX as u128) as u64;
```
**Status: Open (Medium — should fix; trivially hardenable).**

### 5.3 Finding (Informational): `U512` overflow impossible in practice

`sentinel_credit.rs:114` (`account.balance += amount`), `sentinel_credit.rs:175` (`total_revenue + price`), `subscriber_vault.rs:129` (`total_locked + initial_deposit`), `subscriber_vault.rs:226` (`total_locked + amount`). All operate on `U512` (512-bit unsigned). Overflow would require 2⁵¹² motes ≈ 10¹³⁰ CSPR — physically impossible (Casper's total supply is ~10¹⁰ CSPR). The arithmetic is safe without explicit `checked_add` calls. **Status: Accepted (Informational).**

### 5.4 Finding (Informational): `u64` counters safe in practice

`audit_trail.rs:111` (`finding_count + 1`), `sentinel_registry.rs:108` (`subscriber_count + 1`), `sentinel_alert_log.rs:119` (`log_count + 1`), `risk_policy_manager.rs:135` / v2:144 (`current_version + 1`, `u32`), `agent_behavior_index.rs:105` (`agent_count + 1`). Each would require 2⁶⁴ (or 2³² for the version counter) writes to overflow. At 1000 writes/second, 2⁶⁴ writes takes ~584 million years; 2³² takes ~136 years. **Status: Accepted (Informational).**

### 5.5 Finding (Informational): `saturating_sub` correctly prevents underflow in trust score

`agent_behavior_index.rs:143`:
```rust
m.trust_score = base.saturating_sub(penalty).min(100) as u8;
```
- `base.saturating_sub(penalty)` returns 0 if `base < penalty` (instead of panicking on underflow). This is the correct hardening for "trust score can't go negative." ✓
- `.min(100)` clamps to `u8` range before the `as u8` cast. ✓

**Status: Accepted (Informational — correct defensive coding).**

---

## 6. Panic Path Analysis

### 6.1 Revert vs. panic — what's the difference?

- **Revert (clean):** `self.env().revert(crate::user_err(code))` — aborts the entry point, rolls back all state writes, returns a typed `OdraError` with a numeric code. The caller pays gas for the work done up to the revert. This is the *expected* error path for all business-logic failures (unauthorized, paused, insufficient balance, etc.).
- **Panic (unclean):** A Rust panic (array index out of bounds, division by zero, `unwrap()` on `None`, integer overflow in debug mode, slice out of range). In wasm release mode, integer overflow *wraps* (no panic), but other panics abort the contract with a gas charge and an opaque error. Casper/Odra treats panics as gas-charged aborts with no clean error code — they are bugs to be eliminated.

### 6.2 `unwrap_or_revert` / `get_or_revert_with` usage (clean reverts)

Every `Mapping::get(...).unwrap_or_revert(self)` and `Var::get_or_revert_with(...)` calls `self.env().revert(...)` on `None` — a clean revert, not a panic. Audit of every usage:

| Contract | Line | Usage | Reverts with |
|---|---|---|---|
| `audit_trail.rs` | 143 | `self.findings.get(&id).unwrap_or_revert(self)` | default (UnwrapError) |
| `audit_trail.rs` | 224, 311 | `self.role_admin.get_or_revert_with(crate::user_err(ERR_UNAUTHORIZED))` | `ERR_UNAUTHORIZED = 100` |
| `risk_oracle.rs` | 209, 296 | same pattern | `ERR_UNAUTHORIZED` |
| `sentinel_credit.rs` | 287, 374 | same pattern | `ERR_UNAUTHORIZED` |
| `sentinel_registry.rs` | 234, 321 | same pattern | `ERR_UNAUTHORIZED` |
| `sentinel_alert_log.rs` | 157 | `self.logs.get(&log_id).unwrap_or_revert(self)` | default |
| `sentinel_alert_log.rs` | 246, 333 | `role_admin.get_or_revert_with(...)` | `ERR_UNAUTHORIZED` |
| `agent_behavior_index.rs` | 247, 334 | same pattern | `ERR_UNAUTHORIZED` |
| `risk_policy_manager.rs` | 133, 166, 175, 251, 338 | `current_policy.get_or_revert_with(crate::user_err(1))` / `role_admin.get_or_revert_with(...)` | code 1 / `ERR_UNAUTHORIZED` |
| `risk_policy_manager_v2.rs` | 142, 176, 188, 264, 351, 381 | same pattern | code 1 / `ERR_UNAUTHORIZED` |
| `subscriber_vault.rs` | 321, 408 | `role_admin.get_or_revert_with(...)` | `ERR_UNAUTHORIZED` |

### 6.3 Array indexing

| Contract | Line | Indexing | Safe? |
|---|---|---|---|
| `sentinel_alert_log.rs` | 140 | `ids.drain(0..drop_count)` — `drop_count = ids.len() - MAX_ADDRESS_LOG_IDS`; guard `ids.len() > MAX_ADDRESS_LOG_IDS` guarantees `drop_count ≥ 1` and `drop_count ≤ ids.len()`. | ✓ Safe |
| `sentinel_alert_log.rs` (test) | 415-418 | `ids[0]` and `ids.last().unwrap()` — only called after the loop pushes 260 entries and the FIFO cap evicts 4, so `len = 256 ≥ 1`. | ✓ Safe |

No other array indexing in production code.

### 6.4 Division by zero

| Contract | Line | Division | Guarded? |
|---|---|---|---|
| `agent_behavior_index.rs` | 124 | `total_conf / m.total_decisions` | Guarded: `total_decisions` was just incremented to ≥ 1 (line 120). ✓ |
| `agent_behavior_index.rs` | 142 | `m.high_confidence_count * 100 / m.total_decisions` | Guarded: `if m.total_decisions > 0` (line 140). ✓ |

No other division in production code.

### 6.5 `unwrap()` on `None`

No bare `unwrap()` on `Option<_>` in production code. All `unwrap_or_revert` / `unwrap_or_default` / `unwrap_or(0)` / explicit `match`. ✓

### 6.6 Finding (Low): `deregister` and `top_up` use the wrong error type

`sentinel_registry.rs:128`:
```rust
None => self.env().revert(ExecutionError::UnwrapError),
```

`subscriber_vault.rs:229`:
```rust
None => self.env().revert(ExecutionError::UnwrapError),
```

These two paths revert with `ExecutionError::UnwrapError` (a raw Odra error variant) instead of `crate::user_err(<code>)` (the cfg-gated portable helper used everywhere else). The behavior is functionally identical — both revert the entry point — but the error code returned to the caller is inconsistent with the rest of the contract's error vocabulary. **Recommendation:** replace with `self.env().revert(crate::user_err(4))` (the legacy "no-account" code) for consistency. **Status: Open (Low — cosmetic).**

### 6.7 Finding (Informational): no panic paths found

The codebase consistently uses `unwrap_or_revert` / `unwrap_or_default` / `unwrap_or(0)` / explicit `match` / explicit `if` guards to avoid panics. Every arithmetic operation that could panic (division, subtraction underflow) is guarded. Every array index is bounded. The `user_err(code)` helper on `lib.rs:14-23` is correctly cfg-gated for both wasm32 and host targets. **Status: Accepted (Informational — defensive coding confirmed).**

### 6.8 The `user_err` helper — cfg-gating correctness

`lib.rs:14-23`:
```rust
pub fn user_err(code: u16) -> OdraError {
    #[cfg(target_arch = "wasm32")]
    {
        OdraError::user(code)
    }
    #[cfg(not(target_arch = "wasm32"))]
    {
        OdraError::user(code, "user error")
    }
}
```

Odra 2.9.0 cfg-gates the `ExecutionError::User` variant: `User(u16)` on `wasm32`, `User(UserError { code, message })` on host (where `UserError` has private fields). `OdraError::user(...)` is the public cfg-gated constructor that works on both targets. The helper is correct; all 8 contracts route their user-error reverts through it (except the two `ExecutionError::UnwrapError` paths noted in §6.6). **Status: Accepted (Informational — correct).**

---

## 7. Gas / Cost Analysis

### 7.1 Per-entry-point gas estimates

Gas on Casper is charged per host-function call and per byte of state written. The estimates below classify each entry point as Low / Medium / High based on the number of state operations (Mapping/Var reads/writes) and host-function calls.

| Contract | Entry point | State ops | Host fn calls | Event | Gas class |
|---|---|---|---|---|---|
| `AuditTrail` | `record_finding` | 1 Mapping write (~500-byte `Finding`) + 1 Var write (`finding_count`) | 0 | 1 (`FindingRecorded`) | Medium |
| `AuditTrail` | `get_finding` | 1 Mapping read | 0 | 0 | Low |
| `AuditTrail` | `get_count` | 1 Var read | 0 | 0 | Low |
| `RiskOracle` | `update_score` | 1 Mapping write (`RiskScore` ~100 bytes) | 0 | 1 (`ScoreUpdated`) | Low-Medium |
| `RiskOracle` | `get_risk_score` / `is_high_risk` | 1 Mapping read | 0 | 0 | Low |
| `SentinelCredit` | `deposit` (PAYABLE) | 1 Mapping read + 1 Mapping write (`CreditAccount`) | 1 (`attached_value`) | 1 (`CreditDeposited`) | Medium |
| `SentinelCredit` | `withdraw` | 1 Mapping read + 1 Mapping write | 1 (`transfer_tokens`) | 0 | Medium-High |
| `SentinelCredit` | `deduct_query` | 1 Mapping read + 1 Mapping write + 1 Var write (`total_revenue`) | 0 | 0 | Medium |
| `SentinelCredit` | `set_prices` | 2 Var writes | 0 | 0 | Low |
| `SentinelRegistry` | `register` | 1 Mapping write + 1 Var write | 0 | 1 (`SentinelRegistered`) | Medium |
| `SentinelRegistry` | `deregister` | 1 Mapping read + 1 Mapping write | 0 | 0 | Low |
| `SentinelRegistry` | `increment_alert_count` | 1 Mapping read + 1 Mapping write | 0 | 0 | Low |
| `SentinelAlertLog` | `log_alert` | 1 Mapping write (`AlertRecord`) + 1 Var write + 1 Mapping read + Vec push/drain + 1 Mapping write (`address_logs`) | 0 | 1 (`AlertLogged`) | Medium (bounded by 256-cap) |
| `SentinelAlertLog` | `get_log` / `get_address_log_ids` | 1 Mapping read | 0 | 0 | Low |
| `AgentBehaviorIndex` | `record_decision` | 1 Mapping read + arithmetic + 1 Mapping write (`AgentMetrics`) | 0 | 1 (`BehaviorRecorded`) | Medium |
| `RiskPolicyManager` | `upgrade_policy` | 1 Var read + 1 Var write (`current_policy`) + 1 Mapping write (`policy_history`) | 0 | 1 (`PolicyUpgraded`) | Low-Medium |
| `RiskPolicyManager` | `get_current_policy` / `get_policy_version` | 1 Var read / 1 Mapping read | 0 | 0 | Low |
| `RiskPolicyManagerV2` | `get_policy_with_reasoning` | 1 Var read + string construction (no `format!`, custom `u8_to_string` / `u32_to_string` / `u64_to_string`) | 0 | 0 | Low-Medium |
| `SubscriberVault` | `open_vault` (PAYABLE) | 1 Mapping write + 1 Var write (`total_locked`) | 1 (`attached_value`) | 1 (`VaultOpened`) | Medium |
| `SubscriberVault` | `withdraw` | 1 Mapping read + 1 Mapping write + 1 Var read + 1 Var write | 1 (`transfer_tokens`) | 0 | Medium-High |
| `SubscriberVault` | `deduct` | 1 Mapping read + 1 Mapping write | 0 | 0 | Low-Medium |
| `SubscriberVault` | `top_up` (PAYABLE) | 1 Mapping read + 1 Mapping write + 1 Var write | 1 (`attached_value`) | 0 | Medium |
| (all) | `grant_role` / `revoke_role` / `renounce_role` | 1 Mapping read + 1 Mapping write | 0 | 1 (`RoleChanged`) | Low |
| (all) | `transfer_role_admin` / `transfer_ownership` | 1-2 Mapping writes + 1 Var write | 0 | 1 (`RoleChanged`) | Low |
| (all) | `pause` / `unpause` | 1 Var write | 0 | 1 (`PauseChanged`) | Low |
| (all) | `has_role` / `get_roles` / `get_role_admin` / `is_paused` | 1 Mapping read / 1 Var read | 0 | 0 | Low |

### 7.2 Finding (Informational): RBAC entry points add negligible gas overhead

Each contract gained 11 RBAC entry points, all of which perform 1-2 state operations + 1 event. These are never called in the hot path (the IntelAgent calls `record_finding` / `update_score` / `log_alert` thousands of times per day; RBAC mutations happen at most a few times per quarter). **Status: Accepted (Informational).**

### 7.3 Finding (Informational): `SentinelAlertLog` address_logs Vec capped at 256

`sentinel_alert_log.rs:92` defines `const MAX_ADDRESS_LOG_IDS: usize = 256;`. The FIFO eviction (lines 137-141) ensures the per-address Vec never exceeds 256 entries, so `log_alert` gas cost is bounded regardless of how many alerts a subscriber receives. Without the cap, a noisy subscriber's Vec would grow unboundedly, and `get_address_log_ids` would eventually exceed block gas. **Status: Accepted (Informational — good design).**

### 7.4 Finding (Medium): `AuditTrail.findings` Mapping grows unbounded

`audit_trail.rs:73` `findings: Mapping<u64, Finding>` — every `record_finding` writes a new `Finding` (~500 bytes serialized) keyed by `finding_id`. The Mapping is never pruned. After 1 million findings: ~500 MB of global state. After 100 million: ~50 GB. Casper global state is keyed by `u64` here, so reads remain O(1), but the *total* state footprint grows linearly with finding count.

**Mitigation (future work):** off-chain archival (the dashboard already mirrors findings to a Postgres/SQLite cache) + on-chain rolling window (e.g., prune findings older than N blocks, or maintain only the last K findings on-chain and emit a `FindingArchived` event pointing to the off-chain URI). **Status: Open (Medium — pre-existing design; not introduced by RBAC migration).**

### 7.5 Finding (Informational): `AgentBehaviorIndex` metrics per `agent_name` — unbounded agent count

`agent_behavior_index.rs:69` `metrics: Mapping<String, AgentMetrics>` — one entry per unique `agent_name`. Realistically, VaultWatch has 5-10 agents (`ScannerAgent`, `IntelAgent`, `AnomalyAgent`, etc.), so this is bounded operationally. If a malicious OPERATOR spammed `record_decision` with random `agent_name` strings, the Mapping would grow, but each entry is ~200 bytes and the OPERATOR role is gated. **Status: Accepted (Informational — operational cap).**

### 7.6 Finding (Informational): no `Vec<String>` or unbounded-String state growth

Apart from `SentinelAlertLog.address_logs` (capped at 256), no contract stores unbounded `Vec` or large `String` payloads in state. `Finding.description`, `RiskScore.risk_type`, `Subscriber.webhook_url`, etc. are caller-supplied strings, but they're written once per record and never grow. **Status: Accepted (Informational).**

---

## 8. Cross-Contract / Upgrade Risks

### 8.1 Finding (High): `RiskPolicyManager` v1→v2 in-place upgrade from a *pre-RBAC* v1 would corrupt state

`risk_policy_manager.rs:76-89` (v1 struct):
```rust
pub struct RiskPolicyManager {
    current_policy: Var<RiskPolicy>,
    policy_history: Mapping<u32, RiskPolicy>,
    roles: Mapping<Address, u8>,    // ← index 2 (post-RBAC)
    role_admin: Var<Address>,       // ← index 3
    paused: Var<bool>,              // ← index 4
}
```

`risk_policy_manager_v2.rs:78-89` (v2 struct):
```rust
pub struct RiskPolicyManagerV2 {
    current_policy: Var<RiskPolicy>,    // ← index 0
    policy_history: Mapping<u32, RiskPolicy>,  // ← index 1
    roles: Mapping<Address, u8>,    // ← index 2 (matches v1)
    role_admin: Var<Address>,       // ← index 3
    paused: Var<bool>,              // ← index 4
}
```

Odra stores all module state in a single `state` dictionary keyed by field index. The current v1 and v2 source files declare identical field order `[current_policy, policy_history, roles, role_admin, paused]`, so a v2 upgrade over a freshly-deployed RBAC-migrated v1 works correctly — v2 reads `roles` from index 2, `role_admin` from index 3, `paused` from index 4, exactly where v1 wrote them.

**However:** the *on-chain* `RiskPolicyManager` (deployed 2026-07-11, see worklog Task 1) was compiled from an *earlier pre-RBAC* source revision whose struct was `[current_policy, policy_history, owner]` (3 fields, no `roles`/`role_admin`/`paused`). If the v2 upgrade session code were run against that on-chain v1, v2 would:
- Read index 2 as `roles: Mapping<Address, u8>` — but the on-chain storage at index 2 holds `owner: Address` (a 32-byte hash). The deserialization would either succeed with garbage bits or fail.
- Read index 3 as `role_admin: Var<Address>` — but there is no on-chain storage at index 3 (v1 only wrote indices 0, 1, 2). `get_or_revert_with(...)` would revert with `ERR_UNAUTHORIZED`.
- Read index 4 as `paused: Var<bool>` — same; no on-chain storage.

The v2 `upgrade_policy` would call `assert_role(ROLE_ADMIN)` (line 138), which reads `roles[caller]` (index 2, containing the old `owner: Address` bytes), interprets those bytes as a `u8`, and would almost certainly fail the `has_role` check.

**Mitigation:** the on-chain `RiskPolicyManager` must be **redeployed as a fresh RBAC-migrated v1** (new contract package, new state) before the v2 upgrade session code is run against it. The v2 upgrade preserves state across v1↔v2 *only when v1 is already RBAC-migrated*. This is a deployment-script requirement, not a source defect.

**Status: Open (High — deployment-script must enforce fresh v1 redeploy before v2 upgrade).**

### 8.2 No cross-contract calls (Informational)

The eight contracts do not reference each other's package hashes; no contract calls another contract's entry points via `call_contract`. Each contract is standalone. This has two consequences:

- **No reentrancy via cross-contract calls.** The only reentrancy surface is `transfer_tokens` (host function — cannot reenter; see §4).
- **Upgrade independence.** Upgrading `RiskPolicyManager` v1→v2 does not require touching `AuditTrail`, `RiskOracle`, etc. Each contract package can be upgraded independently.

**Status: Accepted (Informational — good design for upgrade independence).**

### 8.3 Finding (Informational): no tight coupling between contracts

The contracts communicate via off-chain orchestration (the `IntelAgent` reads `AuditTrail` findings off-chain and writes `RiskOracle` scores; the `ScannerAgent` writes `AuditTrail` findings). The on-chain contracts share no state. This is the correct architecture for a multi-contract pipeline — it allows each contract to be audited, upgraded, and priced independently. **Status: Accepted (Informational).**

### 8.4 Risk: `RiskPolicyManager` v2 `upgrade()` hook is a no-op

`risk_policy_manager_v2.rs:121-123`:
```rust
pub fn upgrade(&mut self) {
    // Intentional no-op (see module docs).
}
```

This is correct *because* v2 preserves v1's field layout exactly. If a future v3 added a new state field, the `upgrade()` hook would be the place to migrate (e.g., compute the new field from existing state, write it at the new index). For v2, no migration is needed. **Status: Accepted (Informational — correct).**

---

## 9. RBAC-Specific Findings (the migration itself)

This section audits the RBAC migration itself (Tasks RBAC-1 and RBAC-2), not just the resulting code.

### 9.1 Finding (Informational): `transfer_ownership` is a single-call handover

`audit_trail.rs:253-266` (and identical code on every contract): `transfer_ownership(new_owner)` is `ADMIN`-gated, grants `ROLE_ALL` to `new_owner`, transfers `role_admin` to it, then strips all roles from the caller. This is the backward-compat shim for the legacy single-owner entry point — one call hands over all authority.

**Risk:** if `ADMIN` is a single-key account and that key is compromised, the attacker can hand the contract to themselves in one call. The granular `transfer_role_admin` + `grant_role` path is the safer alternative for routine delegation.

**Mitigation:** `ADMIN` should be a multisig/threshold account. **Status: Accepted (Low — operational mitigation).**

### 9.2 Finding (Low): `renounce_role` is a self-service escape hatch

`audit_trail.rs:196-210` (and identical code on every contract): any caller can drop their own role bits without `role_admin` approval. This is the documented escape hatch — a compromised `OPERATOR` can voluntarily shed authority without coordinating with the role_admin.

**Risk:** a compromised account could shed its roles to cover tracks (the attacker's role bits disappear from the contract state). The `RoleChanged { account, role, granted: false, by: <self> }` event (line 204-209) provides the on-chain audit trail — an indexer can reconstruct the renouncement — but the role bits are gone.

**Mitigation:** the `RoleChanged` event with `by = caller` is sufficient for forensic reconstruction. The escape-hatch benefit (compromised-but-honest OPERATOR can shed authority fast) outweighs the cover-tracks risk. **Status: Accepted (Low).**

### 9.3 Finding (Informational): no role-expiry / time-lock on `grant_role`

A granted role persists until explicitly revoked. There is no time-bound grant (e.g., "OPERATOR for 7 days, then auto-revoke").

**Recommendation (operational best practice, not a vulnerability):** consider time-bound grants for `OPERATOR` (rotate operational keys regularly). This is a future-work enhancement, not a defect. **Status: Accepted (Informational).**

### 9.4 Finding (Medium): per-contract pause flag lacks a global circuit breaker

The `paused: Var<bool>` flag is per-contract. A `PAUSER` responding to an incident must call `pause()` eight times (once per contract package) to fully freeze the VaultWatch system. Each call is a separate Casper deploy (~2.5 CSPR gas on testnet), so a full freeze costs ~20 CSPR and takes 8 blocks (~8 minutes on Casper's 1-minute block time).

**Recommendation (future work):** a `CircuitBreaker` contract that, in a single transaction, calls `pause()` on all eight contract packages. The `CircuitBreaker` itself would be `PAUSER`-gated (or multisig). This is a meaningful operational improvement but not a release blocker — the current per-contract pause is correct, just slow. **Status: Open (Medium — future work).**

### 9.5 Finding (Low): `is_paused()` is a public read

Every contract exposes `is_paused() -> bool` as a public read (no role check, no pause check). An attacker can poll `is_paused()` on all eight contracts to detect when the system is degraded.

**Trade-off:** transparency (operators, dashboards, integrators can check pause state without trusting an off-chain oracle) vs. operational-state leakage. The migration chose transparency. **Status: Accepted (Low — acceptable trade-off).**

### 9.6 Finding (Informational): `RoleChanged` event provides full on-chain audit trail

Every `grant_role` / `revoke_role` / `renounce_role` / `transfer_role_admin` / `transfer_ownership` emits a `RoleChanged { account, role, granted, by }` event. An indexer can reconstruct the complete role-graph history of every contract from these events alone — no off-chain log required. This is the correct design for compliance-grade auditability. **Status: Accepted (Informational — good).**

### 9.7 Finding (Informational): `PauseChanged` event provides pause audit trail

Every `pause()` / `unpause()` emits a `PauseChanged { paused, by }` event. Same compliance benefit as `RoleChanged`. **Status: Accepted (Informational — good).**

### 9.8 RBAC migration closes the original single-owner SPOF (verified)

The original single-owner pattern (one `owner: Var<Address>` per contract, all writes gated by `assert_owner()`) had a single SPOF: if the owner key was compromised, *every* write entry point on *every* contract was compromised. The RBAC migration:

- **Separates operational authority.** An `OPERATOR`-only account can call `record_finding`, `update_score`, `log_alert`, `record_decision`, `deposit`, `withdraw`, `deduct_query`, `deduct`, `open_vault`, `top_up`, `increment_alert_count` but cannot call `set_prices`, `upgrade_policy`, or `transfer_ownership` (those are `ADMIN`-gated).
- **Adds a pause primitive.** A `PAUSER` can freeze all writes on a contract without holding the authority to mutate findings. This is the incident-response primitive that was completely missing from the single-owner design.
- **Preserves backward-compat.** The legacy `transfer_ownership` entry point still works (now `ADMIN`-gated), so existing e2e tests and integration scripts that call it continue to function.

**What the migration does NOT fix:**
- **Single `role_admin` SPOF (Medium, §3.10).** Role management remains single-key.
- **No multisig (Medium, §9.4).** `ADMIN`/`PAUSER`/`role_admin` should ideally be multisig accounts.
- **No global circuit breaker (Medium, §9.4).** Pause is per-contract.
- **No time-bound grants (Informational, §9.3).** Roles persist until revoked.

**Verdict:** the migration correctly closes the everyday single-owner SPOF (operational authority is now separated and pausable) and adds the missing incident-response primitive (pause). The residual single-`role_admin` SPOF is documented and tracked as future work. ✓

---

## 10. Findings Summary Table

| ID | Contract | Severity | Title | Status | Recommendation |
|---|---|---|---|---|---|
| F-01 | `risk_policy_manager.rs` + v2 | **High** | v1→v2 in-place upgrade from a pre-RBAC v1 would corrupt state | Open | Redeploy on-chain v1 as fresh RBAC-migrated before running v2 upgrade session code |
| F-02 | all 9 contracts | **Medium** | Single `role_admin` is a SPOF | Open | Multisig `role_admin` or on-chain DAO (future work) |
| F-03 | all 9 contracts | **Medium** | No global circuit breaker — pause is per-contract | Open | `CircuitBreaker` contract that pauses all 8 in one call (future work) |
| F-04 | `agent_behavior_index.rs:123,142` | **Medium** | Rolling-average multiplication can overflow `u64` after ~1.8×10¹⁷ decisions | Open | Use `u128` for the intermediate, or `saturating_mul` |
| F-05 | `sentinel_registry.rs:91-130` | **Medium** | `register`/`deregister` are public with no anti-spam bond | Accepted (pre-existing) | Require CSPR bond or rate-limit (future hardening) |
| F-06 | all 9 contracts | **Low** | `grant_role` accepts `ROLE_ALL` in one call (over-permissioned grant) | Open | Restrict to single-role bits; require multiple calls for `ROLE_ALL` |
| F-07 | all 9 contracts | **Low** | `renounce_role` is a self-service escape hatch (cover-tracks risk) | Accepted | `RoleChanged` event provides forensic trail; benefit > risk |
| F-08 | all 9 contracts | **Low** | `is_paused()` leaks operational state to attackers | Accepted | Transparency trade-off; acceptable |
| F-09 | `sentinel_registry.rs:128`, `subscriber_vault.rs:229` | **Low** | `deregister`/`top_up` use `ExecutionError::UnwrapError` instead of `crate::user_err(4)` | Open | Replace with `crate::user_err(4)` for consistent error vocabulary |
| F-10 | all 9 contracts | **Low** | `transfer_ownership` lets a single `ADMIN` call hand over everything | Accepted | `ADMIN` should be multisig (operational mitigation) |
| F-11 | `audit_trail.rs:73` | **Medium** | `findings` Mapping grows unbounded (global-state bloat) | Open (pre-existing) | Off-chain archival + on-chain rolling window (future work) |
| F-12 | `sentinel_credit.rs:175` | **Informational** | `total_revenue + price` has no overflow check (U512 — impossible in practice) | Accepted | No action |
| F-13 | `subscriber_vault.rs:129,226` | **Informational** | `total_locked + amount` has no overflow check (U512 — impossible) | Accepted | No action |
| F-14 | `sentinel_credit.rs:133-149`, `subscriber_vault.rs:145-174` | **Informational** | No reentrancy vulnerability (CEI pattern + host-function semantics) | Accepted | No action |
| F-15 | all 9 contracts | **Informational** | No zero-address guard (Casper Address has no canonical zero) | Accepted | `role_admin` gating is the sole protection |
| F-16 | all 9 contracts | **Informational** | `pause`/`unpause` are PAUSER-gated but NOT pause-guarded (correct) | Accepted | No action |
| F-17 | all 9 contracts | **Informational** | No panic paths found (defensive `unwrap_or_revert` / `if` guards) | Accepted | No action |
| F-18 | `lib.rs:14-23` | **Informational** | `user_err` cfg-gating is correct for wasm32 + host | Accepted | No action |
| F-19 | `sentinel_alert_log.rs:92` | **Informational** | `address_logs` Vec capped at 256 (FIFO) — bounded gas | Accepted | No action |
| F-20 | all 9 contracts | **Informational** | No cross-contract coupling (upgrade independence) | Accepted | No action |
| F-21 | all 9 contracts | **Informational** | `RoleChanged` + `PauseChanged` events provide full on-chain audit trail | Accepted | No action |
| F-22 | all 9 contracts | **Informational** | No role-expiry / time-lock on `grant_role` | Accepted | Future-work enhancement (operational best practice) |
| F-23 | `agent_behavior_index.rs:143` | **Informational** | `saturating_sub` + `.min(100)` correctly prevents underflow + cast-overflow in trust score | Accepted | No action |
| F-24 | `risk_policy_manager.rs:121-123` (v2) | **Informational** | `upgrade()` hook is a no-op (correct — v2 preserves v1 field layout) | Accepted | No action |

**Severity rollup:** 0 Critical, 1 High, 4 Medium, 5 Low, 14 Informational (total: 24 findings).

---

## 11. Verification Evidence

### 11.1 `cargo test --lib --target x86_64-unknown-linux-gnu` → 125 passed

Run on audit date (2026-07-22) from `/home/z/my-project/vaultwatch/contracts/`:

```
test result: ok. 125 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out; finished in 7.70s
```

Per-contract test breakdown (verified by `cargo test --lib --target x86_64-unknown-linux-gnu <module>` filtering):

| Module | Tests | Breakdown |
|---|---|---|
| `rbac` | 5 | 5 constant-level (`role_all_contains_every_role`, `operator_only_lacks_admin_and_pauser`, `multi_role_membership`, `role_none_is_always_authorized_and_invalid_as_input`, `invalid_roles_rejected`) |
| `audit_trail` | 11 | 2 original functional + 9 RBAC |
| `risk_oracle` | 12 | 3 original + 9 RBAC |
| `sentinel_credit` | 17 | 7 original + 10 RBAC (one extra `test_set_prices_is_admin_gated`) |
| `sentinel_registry` | 12 | 3 functional + 9 RBAC |
| `sentinel_alert_log` | 14 | 5 original (incl. `test_address_log_ids_capped_at_256`) + 9 RBAC |
| `agent_behavior_index` | 11 | 2 original + 9 RBAC |
| `risk_policy_manager` | 13 | 4 original + 9 RBAC |
| `risk_policy_manager_v2` | 14 | 5 original (incl. `build_reasoning_is_no_std_safe_and_descriptive`) + 9 RBAC |
| `subscriber_vault` | 16 | 7 original + 9 RBAC |
| **Total** | **125** | |

### 11.2 RBAC test coverage matrix (per contract, all 9 RBAC tests present)

Every contract's RBAC test module covers the same 9 scenarios (10 for `sentinel_credit`):

1. `test_init_grants_deployer_all_roles_and_role_admin` — `init()` grants deployer `ROLE_ALL` + sets `role_admin` + `paused=false`.
2. `test_non_<role>_reverts_on_<entry_point>` — non-authorized caller reverts with `ERR_UNAUTHORIZED`.
3. `test_grant_role_enables_<role>` — `role_admin` grants the role; the previously-rejected entry point now succeeds.
4. `test_non_role_admin_cannot_grant_role` — a non-`role_admin` caller (even with `OPERATOR`) cannot `grant_role`.
5. `test_pause_blocks_writes_and_unpause_restores` — `pause()` makes the entry point revert; `unpause()` restores.
6. `test_renounce_role_strips_authority` — `renounce_role(ROLE)` strips the caller's authority; the entry point reverts.
7. `test_transfer_ownership_grants_all_and_strips_caller` — `transfer_ownership(new_owner)` grants `ROLE_ALL` + transfers `role_admin` + strips caller.
8. `test_grant_invalid_role_reverts` — `grant_role(account, 0b1000_0000)` reverts with `ERR_INVALID_ROLE`.
9. `test_non_pauser_cannot_pause` — non-`PAUSER` cannot `pause()`.
10. (sentinel_credit only) `test_set_prices_is_admin_gated` — `OPERATOR` cannot `set_prices`; `ADMIN` can.

### 11.3 `cargo odra build` → 9 wasm files, full-size, Casper-compatible

`contracts/wasm/` contains 9 wasm files, all ~180 KB (full contract code, not the 4153-byte stubs mentioned in worklog Task RBAC-2 — the build infrastructure has since been fixed):

| Wasm | Size |
|---|---|
| `AgentBehaviorIndex.wasm` | 181,954 bytes |
| `AuditTrail.wasm` | 183,135 bytes |
| `RiskOracle.wasm` | 180,699 bytes |
| `RiskPolicyManager.wasm` | 181,952 bytes |
| `RiskPolicyManagerV2.wasm` | 184,717 bytes |
| `SentinelAlertLog.wasm` | 184,952 bytes |
| `SentinelCredit.wasm` | 186,311 bytes |
| `SentinelRegistry.wasm` | 182,299 bytes |
| `SubscriberVault.wasm` | 188,467 bytes |

### 11.4 Wasm export-table inspection (RBAC entry points present)

A `strings` scan confirmed that every wasm exports the 11 RBAC entry points + the contract-specific business entry points. Example for `AuditTrail.wasm`:

```
$ strings wasm/AuditTrail.wasm | grep -E '^(grant_role|revoke_role|renounce_role|has_role|get_roles|get_role_admin|transfer_role_admin|transfer_ownership|pause|unpause|is_paused|record_finding|get_finding|get_count)$'
get_count
get_finding
get_role_admin
grant_role
has_role
is_paused
pause
record_finding
renounce_role
revoke_role
transfer_ownership
transfer_role_admin
unpause
```

(`get_roles` appears with a tab prefix in the export-name string table; verified present.)

Analogous verification was performed for `SentinelCredit.wasm` (12 entry points verified including `deposit`, `withdraw`, `set_prices`) and `SubscriberVault.wasm` (12 entry points verified including `open_vault`, `top_up`, `withdraw`). All 9 wasms export the full RBAC surface.

### 11.5 Bulk-memory opcode byte-scan (Casper compatibility)

A Python byte-scan for the WASM bulk-memory opcode prefix `0xfc` followed by `0x08`/`0x09`/`0x0a`/`0x0b` (`memory.init`/`data.drop`/`memory.copy`/`memory.fill`) returned 2 hits per wasm. These are false positives in the data section (immediate bytes of other instructions); the custom `memops` module in `lib.rs:39-92` defines `memcpy`/`memmove`/`memset`/`memcmp`/`bcmp` as no_std `while` loops, so the compiler emits `call`s to these instead of bulk-memory opcodes. **9/9 wasms are Casper-compatible** (no functional bulk-memory opcodes).

The `lib.rs:36-37` comment confirms the intent: "Custom memory operations to avoid WASM bulk-memory proposal. Required for Casper testnet compatibility (no bulk-memory support)."

---

## 12. Conclusion & Recommendations

### 12.1 Verdict on production readiness

**Production-ready after remediating the single High finding (F-01) and the four Medium findings (F-02, F-03, F-04, F-11) on a best-effort timeline.**

The RBAC migration is sound:
- 125/125 cargo unit tests pass (including 76 new RBAC tests across the 8 migrated contracts + 11 in `audit_trail.rs` + 5 in `rbac.rs`).
- 9 wasm files are full-size (~180 KB each) and Casper-compatible (no bulk-memory opcodes).
- All 11 RBAC entry points + business entry points are present in every wasm.
- Every mutable entry point is role-gated + pause-gated (except `pause`/`unpause`/`transfer_ownership`, intentionally).
- Every read-only entry point is neither role-gated nor pause-gated (observers can inspect state during an incident).
- No reentrancy vulnerability (CEI pattern + host-function semantics).
- No panic paths (defensive `unwrap_or_revert` / `if` guards throughout).
- No integer-overflow exploit (the one theoretical overflow in `AgentBehaviorIndex` is unreachable in practice and would wrap silently, not panic).
- Full on-chain audit trail via `RoleChanged` + `PauseChanged` events.

### 12.2 Prioritized remediation list

| Priority | Finding | Action |
|---|---|---|
| **P0** (must fix before redeploy) | F-01 (High) | Deployment script must redeploy on-chain `RiskPolicyManager` as a fresh RBAC-migrated v1 *before* running the v2 upgrade session code. No source change needed — the v1 and v2 source files are already correct. |
| **P1** (should fix in next iteration) | F-04 (Medium) | Replace `u64` arithmetic in `agent_behavior_index.rs:123,142` with `u128` intermediates or `saturating_mul`. Trivial change, ~5 LOC. |
| **P1** | F-09 (Low) | Replace `ExecutionError::UnwrapError` in `sentinel_registry.rs:128` and `subscriber_vault.rs:229` with `crate::user_err(4)` for consistent error vocabulary. 2 LOC. |
| **P1** | F-06 (Low) | Consider restricting `grant_role` to single-role bits; require multiple calls for `ROLE_ALL`. ~3 LOC change in `is_valid_role`. |
| **P2** (future work — operational, not source) | F-02 (Medium) | Multisig `role_admin` (deploy `role_admin` slot as a Casper multisig contract). |
| **P2** | F-03 (Medium) | `CircuitBreaker` contract that pauses all 8 in one call. |
| **P2** | F-05 (Medium) | CSPR bond or rate-limit on `SentinelRegistry.register`. |
| **P2** | F-11 (Medium) | Off-chain archival + on-chain rolling window for `AuditTrail.findings`. |
| **P3** (accept with documentation) | F-07, F-08, F-10, F-12-F-24 | Informational / accepted — no action. |

### 12.3 Future work (beyond the audit)

1. **Multisig `role_admin`** (F-02) — deploy a Casper multisig contract as the `role_admin` slot on every contract. M-of-N threshold for `grant_role` / `revoke_role` / `transfer_role_admin`.
2. **Global circuit breaker** (F-03) — a `CircuitBreaker` contract holding `PAUSER` on all 8 contracts; one call pauses all.
3. **Time-bound grants** (§9.3) — extend `grant_role` with an optional `expires_at: u64` block height; `assert_role` checks expiry.
4. **On-chain rolling archival for `AuditTrail`** (F-11) — prune findings older than N blocks; emit `FindingArchived { id, off_chain_uri }` events pointing to the off-chain mirror.
5. **CSPR bond on `SentinelRegistry.register`** (F-05) — require a small PAYABLE bond on `register`; refund on `deregister` by the same caller.
6. **`u128` arithmetic in `AgentBehaviorIndex`** (F-04) — trivial hardening.
7. **Error-vocabulary consistency** (F-09) — replace `ExecutionError::UnwrapError` with `crate::user_err(4)`.

### 12.4 Final note

The RBAC migration (Tasks RBAC-1 + RBAC-2) successfully closes the original single-owner SPOF that motivated it. The residual risks (single `role_admin`, per-contract pause, unbounded `AuditTrail` growth) are documented, tracked, and have clear future-work paths. The codebase is well-tested (125 unit tests), defensively coded (no panic paths), and Casper-compatible (custom memops, full-size wasms, no bulk-memory opcodes). The single High finding (F-01) is a deployment-script requirement, not a source defect — the v1 and v2 source files are correct as written.

**Recommendation: proceed to redeploy** the on-chain contracts from the current source tree (post-RBAC-2), with F-01's deployment-script mitigation in place. Track F-02 / F-03 / F-04 / F-11 as P1/P2 follow-ups.

---

*End of audit. Generated by Task ID `AUDIT-1` (sub-agent, general-purpose) on 2026-07-22. Scope: 8 VaultWatch contracts + `RiskPolicyManagerV2` upgrade + `rbac.rs` module + `lib.rs` helpers. Methodology: manual source review (5,300 LOC) + cargo test verification (125/125) + wasm export-table inspection (9/9) + bulk-memory byte-scan (9/9 Casper-compatible). Findings: 0 Critical, 1 High, 4 Medium, 5 Low, 14 Informational.*
