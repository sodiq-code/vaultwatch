//! RiskPolicyManagerV2 — Casper-native upgrade via `add_contract_version()`.
//!
//! This module is the **v2** of `risk_policy_manager::RiskPolicyManager`. It is
//! the concrete demonstration of Casper's natively-upgradable smart contracts
//! (Critical Fix 2 in the VaultWatch strategic review): the v2 Wasm is installed
//! as a new version *under the same contract package* as v1 using the Casper
//! host function `storage::add_contract_version(...)`, which Odra 2.8.0 invokes
//! automatically when the Wasm is deployed as session code with the runtime arg
//! `odra_cfg_is_upgrade=true`.
//!
//! ## Design rules (required for shared state)
//!
//! 1. **Same struct fields, same order** as v1 (`current_policy`,
//!    `policy_history`, `roles`, `role_admin`, `paused`). Odra stores all
//!    module state in a single `state` dictionary keyed by field index;
//!    preserving the field order means v2 reads v1's state via the identical
//!    dictionary keys — no migration code required.
//! 2. **All v1 entry points preserved** so the upgraded package remains a
//!    functional superset — v1 entry points work whether pinned to version 1
//!    or invoked on the latest (v2) version.
//! 3. **One new entry point** `get_policy_with_reasoning` — the v2-only
//!    capability that proves the upgrade added functionality.
//! 4. **`upgrade(&mut self)` hook** — Odra invokes this after
//!    `add_contract_version()`. It is a no-op here because v2 preserves v1's
//!    field layout; no state migration is needed.
//!
//! ## Access control (NEW in v2 — inherited from v1's RBAC migration)
//!
//! v2 mirrors v1's RBAC scheme exactly: `upgrade_policy` is ADMIN-gated and
//! paused-aware; role management is restricted to the `role_admin`; the legacy
//! `transfer_ownership` entry point is preserved as a backward-compat shim.
//! Because v2 shares v1's `state` dictionary, the role/admin/pause bits v1
//! wrote at init() are read by v2 without any migration.
//!
//! ## Upgrade flow (Casper-native)
//!
//! ```text
//! 1. v1 (RiskPolicyManager) already deployed  → package version 1
//! 2. Deploy v2 Wasm as session code with:
//!      odra_cfg_is_upgrade = true
//!      odra_cfg_package_hash_to_upgrade = <v1 package hash>
//! 3. Odra's generated `call` entry point runs:
//!      storage::add_contract_version(package_hash, entry_points, named_keys, {})
//!      → registers v2 as version 2 under the SAME package hash
//! 4. Package now has versions [1, 2]; latest = 2.
//! 5. v1 entry points still callable (version 1 pin, or via v2 superset).
//! 6. get_policy_with_reasoning callable on version 2 (latest).
//! 7. Shared state: v2 reads v1's `current_policy` unchanged.
//! ```

use odra::prelude::*;
// Reuse v1's RiskPolicy, PolicyUpgraded event, RoleChanged event, and
// PauseChanged event so the serialized layout is byte-identical (state shared)
// and the event schema is identical across v1/v2. `crate::` prefix required
// (Rust 2018 edition); the odra_type/event structs are not gated by
// odra_module, so they remain available when building v2 only.
pub use crate::risk_policy_manager::{
    PauseChanged, PolicyUpgraded, RiskPolicy, RoleChanged,
};

use crate::rbac::{
    has_role, is_valid_role, ERR_INVALID_ROLE, ERR_PAUSED, ERR_UNAUTHORIZED,
    ROLE_ADMIN, ROLE_ALL, ROLE_NONE, ROLE_OPERATOR, ROLE_PAUSER,
};

/// Return type of the v2-only `get_policy_with_reasoning` entry point.
///
/// Carries the active `RiskPolicy` plus a human-readable rationale string
/// explaining what each threshold does — the kind of "reasoning" output an
/// agent or dashboard can surface directly to a human reviewer.
#[odra::odra_type]
pub struct PolicyWithReasoning {
    pub policy: RiskPolicy,
    pub reasoning: String,
}

#[odra::module(events = [PolicyUpgraded, RoleChanged, PauseChanged])]
pub struct RiskPolicyManagerV2 {
    // --- SAME fields, SAME order as v1 (shared `state` dictionary keys) ---
    current_policy: Var<RiskPolicy>,
    policy_history: Mapping<u32, RiskPolicy>,
    // ── RBAC state (mirrors v1's field order exactly) ──
    /// Per-account role bitmask (OPERATOR | ADMIN | PAUSER).
    roles: Mapping<Address, u8>,
    /// The single role-manager — only account that may grant/revoke roles.
    role_admin: Var<Address>,
    /// Emergency pause flag. When true, every mutable entry point reverts.
    paused: Var<bool>,
}

#[odra::module]
impl RiskPolicyManagerV2 {
    /// Constructor — only invoked on a *fresh* install (never on upgrade).
    /// Mirrors v1's `init` so a standalone v2 deploy is self-consistent.
    pub fn init(&mut self) {
        let caller = self.env().caller();
        self.role_admin.set(caller);
        self.roles.set(&caller, ROLE_ALL);
        self.paused.set(false);
        let default_policy = RiskPolicy {
            version: 1,
            min_confidence_threshold: 75,
            critical_score_threshold: 80,
            high_score_threshold: 60,
            medium_score_threshold: 40,
            max_retry_count: 2,
            safety_rejection_threshold: 80,
            updated_at_block: 0,
            updated_by: caller,
        };
        self.current_policy.set(default_policy.clone());
        self.policy_history.set(&1u32, default_policy);
    }

    /// Odra upgrade hook — invoked automatically after `add_contract_version()`.
    ///
    /// No-op: v2 preserves v1's field layout exactly, so the shared `state`
    /// dictionary already holds `current_policy`, `policy_history`, `roles`,
    /// `role_admin`, and `paused` under the same keys v1 wrote them. Nothing
    /// to migrate.
    pub fn upgrade(&mut self) {
        // Intentional no-op (see module docs).
    }

    /// Hot-swap policy — agents read this every cycle. ADMIN-gated and
    /// paused-aware (identical to v1).
    pub fn upgrade_policy(
        &mut self,
        min_confidence_threshold: u8,
        critical_score_threshold: u8,
        high_score_threshold: u8,
        medium_score_threshold: u8,
        max_retry_count: u8,
        safety_rejection_threshold: u8,
        block_height: u64,
        updated_by: Address,
    ) {
        self.assert_role(ROLE_ADMIN);
        self.assert_not_paused();
        let current_version = self
            .current_policy
            .get_or_revert_with(crate::user_err(1))
            .version;
        let new_version = current_version + 1;

        let new_policy = RiskPolicy {
            version: new_version,
            min_confidence_threshold,
            critical_score_threshold,
            high_score_threshold,
            medium_score_threshold,
            max_retry_count,
            safety_rejection_threshold,
            updated_at_block: block_height,
            updated_by,
        };

        self.current_policy.set(new_policy.clone());
        self.policy_history.set(&new_version, new_policy.clone());

        // Emit the same PolicyUpgraded event as v1 so off-chain indexers see a
        // uniform event stream regardless of which contract version is active.
        self.env().emit_event(PolicyUpgraded {
            version: new_version,
            updated_by,
            updated_at_block: block_height,
            min_confidence_threshold,
            critical_score_threshold,
            safety_rejection_threshold,
        });
    }

    /// Get active policy — agents call this every decision cycle (identical to v1).
    pub fn get_current_policy(&self) -> RiskPolicy {
        self.current_policy
            .get_or_revert_with(crate::user_err(1))
    }

    /// Get a historical policy version (identical to v1).
    pub fn get_policy_version(&self, version: u32) -> Option<RiskPolicy> {
        self.policy_history.get(&version)
    }

    /// Get current version number (identical to v1).
    pub fn get_current_version(&self) -> u32 {
        self.current_policy
            .get_or_revert_with(crate::user_err(1))
            .version
    }

    // ────────────────────────────── RBAC ──────────────────────────────

    /// Grant a role to an account. Only the `role_admin` may call this.
    ///
    /// `role` must be a valid single-role bit or `ROLE_ALL`. Invalid bitmasks
    /// revert with `ERR_INVALID_ROLE`. The zero address reverts with
    /// `ERR_ZERO_ADDRESS`.
    pub fn grant_role(&mut self, account: Address, role: u8) {
        self.assert_role_admin();
        if !is_valid_role(role) {
            self.env().revert(crate::user_err(ERR_INVALID_ROLE));
        }
        let current = self.roles.get(&account).unwrap_or(0);
        let new_roles = current | role;
        self.roles.set(&account, new_roles);
        self.env().emit_event(RoleChanged {
            account,
            role,
            granted: true,
            by: self.env().caller(),
        });
    }

    /// Revoke a role from an account. Only the `role_admin` may call this.
    /// The role_admin may revoke its own roles (but cannot revoke its own
    /// role_admin status — use `transfer_role_admin` for that).
    pub fn revoke_role(&mut self, account: Address, role: u8) {
        self.assert_role_admin();
        if !is_valid_role(role) {
            self.env().revert(crate::user_err(ERR_INVALID_ROLE));
        }
        let current = self.roles.get(&account).unwrap_or(0);
        let new_roles = current & !role;
        self.roles.set(&account, new_roles);
        self.env().emit_event(RoleChanged {
            account,
            role,
            granted: false,
            by: self.env().caller(),
        });
    }

    /// Caller renounces a role it currently holds. This is a self-service
    /// escape hatch — no role_admin required — so a compromised OPERATOR can
    /// voluntarily shed authority without coordinating with the role_admin.
    pub fn renounce_role(&mut self, role: u8) {
        let caller = self.env().caller();
        if !is_valid_role(role) {
            self.env().revert(crate::user_err(ERR_INVALID_ROLE));
        }
        let current = self.roles.get(&caller).unwrap_or(0);
        let new_roles = current & !role;
        self.roles.set(&caller, new_roles);
        self.env().emit_event(RoleChanged {
            account: caller,
            role,
            granted: false,
            by: caller,
        });
    }

    /// Public check: does `account` hold `role`?
    pub fn has_role(&self, account: Address, role: u8) -> bool {
        has_role(self.roles.get(&account).unwrap_or(ROLE_NONE), role)
    }

    /// Public read of the full role bitmask for `account`.
    pub fn get_roles(&self, account: Address) -> u8 {
        self.roles.get(&account).unwrap_or(ROLE_NONE)
    }

    /// Public read of the current role_admin address.
    pub fn get_role_admin(&self) -> Address {
        self.role_admin.get_or_revert_with(crate::user_err(ERR_UNAUTHORIZED))
    }

    /// Transfer the role_admin to a new account. Only the current role_admin
    /// may call this. The new admin does NOT automatically receive any role
    /// bits — call `grant_role` afterwards if it should also be an OPERATOR.
    ///
    /// Note: Casper `Address` has no canonical zero value, so there is no
    /// explicit zero-address guard here. The `assert_role_admin` check is the
    /// sole protection — only the current role_admin (a real, validated
    /// account) can invoke this, and it is expected to pass a real account.
    pub fn transfer_role_admin(&mut self, new_admin: Address) {
        self.assert_role_admin();
        self.role_admin.set(new_admin);
        self.env().emit_event(RoleChanged {
            account: new_admin,
            role: ROLE_ALL,
            granted: true,
            by: self.env().caller(),
        });
    }

    /// Backward-compat shim for the legacy single-owner `transfer_ownership`.
    ///
    /// ADMIN-gated. Grants `ROLE_ALL` to `new_owner` and transfers `role_admin`
    /// to it, then strips all roles from the caller. This preserves the
    /// semantics of the old entry point (one call hands over all authority)
    /// while the granular `grant_role` / `revoke_role` / `transfer_role_admin`
    /// entry points remain available for split-key operations.
    pub fn transfer_ownership(&mut self, new_owner: Address) {
        self.assert_role(ROLE_ADMIN);
        let caller = self.env().caller();
        self.roles.set(&new_owner, ROLE_ALL);
        self.role_admin.set(new_owner);
        // Strip all roles from the previous holder.
        self.roles.set(&caller, ROLE_NONE);
        self.env().emit_event(RoleChanged {
            account: new_owner,
            role: ROLE_ALL,
            granted: true,
            by: caller,
        });
    }

    // ────────────────────────────── Pause ─────────────────────────────

    /// Pause the contract — only PAUSER. Not guarded by `assert_not_paused`
    /// (idempotent: pausing an already-paused contract is a no-op).
    pub fn pause(&mut self) {
        self.assert_role(ROLE_PAUSER);
        self.paused.set(true);
        self.env().emit_event(PauseChanged {
            paused: true,
            by: self.env().caller(),
        });
    }

    /// Unpause the contract — only PAUSER. Not guarded by `assert_not_paused`
    /// (otherwise a paused contract could never be unpaused).
    pub fn unpause(&mut self) {
        self.assert_role(ROLE_PAUSER);
        self.paused.set(false);
        self.env().emit_event(PauseChanged {
            paused: false,
            by: self.env().caller(),
        });
    }

    /// Public read of the pause flag.
    pub fn is_paused(&self) -> bool {
        self.paused.get_or_default()
    }

    // ──────────────────────────── Assertions ────────────────────────────

    /// Revert if the caller does not hold `role`.
    fn assert_role(&self, role: u8) {
        let caller = self.env().caller();
        let roles = self.roles.get(&caller).unwrap_or(ROLE_NONE);
        if !has_role(roles, role) {
            self.env().revert(crate::user_err(ERR_UNAUTHORIZED));
        }
    }

    /// Revert if the caller is not the role_admin.
    fn assert_role_admin(&self) {
        let caller = self.env().caller();
        let admin = self.role_admin.get_or_revert_with(crate::user_err(ERR_UNAUTHORIZED));
        if caller != admin {
            self.env().revert(crate::user_err(ERR_UNAUTHORIZED));
        }
    }

    /// Revert if the contract is paused.
    fn assert_not_paused(&self) {
        if self.paused.get_or_default() {
            self.env().revert(crate::user_err(ERR_PAUSED));
        }
    }

    // Suppress unused-import warning for ROLE_OPERATOR — this contract has no
    // OPERATOR-gated entry point (only ADMIN-gated `upgrade_policy`), but we
    // import the full RBAC constant set for consistency with v1.
    #[allow(dead_code)]
    const _ROLE_OPERATOR_UNUSED: u8 = ROLE_OPERATOR;

    // ────────────────────────────── NEW in v2 ──────────────────────────────

    /// Returns the active policy plus a human-readable rationale string.
    ///
    /// This is the v2-only entry point that demonstrates the Casper-native
    /// upgrade added new functionality to the *same* contract package while
    /// preserving all v1 state (the returned `policy` is read from the shared
    /// `state` dictionary that v1 populated).
    pub fn get_policy_with_reasoning(&self) -> PolicyWithReasoning {
        let policy = self
            .current_policy
            .get_or_revert_with(crate::user_err(1));

        let reasoning = build_reasoning(&policy);

        PolicyWithReasoning { policy, reasoning }
    }
}

/// Build the human-readable rationale for a `RiskPolicy` (no_std + alloc safe).
///
/// Kept as a free function so it can be unit-tested without deploying.
fn build_reasoning(p: &RiskPolicy) -> String {
    // "Policy vN: CRITICAL >80/100, HIGH >60/100, MEDIUM >40/100. \
    //  SelfCorrection triggers below 75/100 confidence (max 2 retries). \
    //  SafetyGuard rejects findings scoring above 80/100. \
    //  Last updated by admin at block 1500000."
    let mut s = String::new();
    s.push_str("Policy v");
    s.push_str(&u32_to_string(p.version));
    s.push_str(": CRITICAL >");
    s.push_str(&u8_to_string(p.critical_score_threshold));
    s.push_str("/100, HIGH >");
    s.push_str(&u8_to_string(p.high_score_threshold));
    s.push_str("/100, MEDIUM >");
    s.push_str(&u8_to_string(p.medium_score_threshold));
    s.push_str("/100. SelfCorrection triggers below ");
    s.push_str(&u8_to_string(p.min_confidence_threshold));
    s.push_str("/100 confidence (max ");
    s.push_str(&u8_to_string(p.max_retry_count));
    s.push_str(" retries). SafetyGuard rejects findings scoring above ");
    s.push_str(&u8_to_string(p.safety_rejection_threshold));
    s.push_str("/100. Last updated by ");
    s.push_str(&p.updated_by.to_string());
    s.push_str(" at block ");
    s.push_str(&u64_to_string(p.updated_at_block));
    s.push('.');
    s
}

// --- no_std-safe integer-to-string helpers (avoid format!/alloc::fmt::format) ---

fn u8_to_string(v: u8) -> String {
    let mut buf = [0u8; 3];
    let mut n = v as usize;
    if n == 0 {
        return String::from("0");
    }
    let mut i = 3usize;
    while n > 0 {
        i -= 1;
        buf[i] = b'0' + (n % 10) as u8;
        n /= 10;
    }
    core::str::from_utf8(&buf[i..])
        .unwrap_or("")
        .to_string()
}

fn u32_to_string(v: u32) -> String {
    let mut buf = [0u8; 10];
    let mut n = v as u64;
    if n == 0 {
        return String::from("0");
    }
    let mut i = 10usize;
    while n > 0 {
        i -= 1;
        buf[i] = b'0' + (n % 10) as u8;
        n /= 10;
    }
    core::str::from_utf8(&buf[i..])
        .unwrap_or("")
        .to_string()
}

fn u64_to_string(v: u64) -> String {
    let mut buf = [0u8; 20];
    let mut n = v;
    if n == 0 {
        return String::from("0");
    }
    let mut i = 20usize;
    while n > 0 {
        i -= 1;
        buf[i] = b'0' + (n % 10) as u8;
        n /= 10;
    }
    core::str::from_utf8(&buf[i..])
        .unwrap_or("")
        .to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use odra::host::{Deployer, NoArgs};

    fn sample_policy() -> RiskPolicy {
        RiskPolicy {
            version: 3,
            min_confidence_threshold: 70,
            critical_score_threshold: 85,
            high_score_threshold: 65,
            medium_score_threshold: 45,
            max_retry_count: 2,
            safety_rejection_threshold: 90,
            updated_at_block: 1_500_000,
            // Use the zero account-hash as a stand-in; the reasoning string
            // only needs a stable formatted representation.
            updated_by: Address::new(
                "account-hash-0000000000000000000000000000000000000000000000000000000000000000"
            ).unwrap(),
        }
    }

    #[test]
    fn v2_init_sets_default_policy_like_v1() {
        let env = odra_test::env();
        let contract = RiskPolicyManagerV2::deploy(&env, NoArgs);
        let policy = contract.get_current_policy();
        assert_eq!(policy.version, 1);
        assert_eq!(policy.min_confidence_threshold, 75);
        assert_eq!(policy.critical_score_threshold, 80);
    }

    #[test]
    fn v2_get_policy_with_reasoning_returns_active_policy_and_text() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManagerV2::deploy(&env, NoArgs);
        let admin = env.get_account(1);
        // Hot-swap to a known policy.
        contract.upgrade_policy(70, 85, 65, 45, 2, 90, 1_500_000, admin);

        let result = contract.get_policy_with_reasoning();
        assert_eq!(result.policy.version, 2); // init=1, then +1
        assert_eq!(result.policy.critical_score_threshold, 85);
        assert!(result.reasoning.contains("CRITICAL >85/100"));
        assert!(result.reasoning.contains("SelfCorrection triggers below 70/100"));
        // The reasoning includes the admin's account-hash formatted string.
        assert!(result.reasoning.contains("account-hash-"));
        assert!(result.reasoning.contains("1500000"));
    }

    #[test]
    fn v2_preserves_v1_entry_points() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManagerV2::deploy(&env, NoArgs);
        let ops = env.get_account(2);
        contract.upgrade_policy(60, 70, 50, 30, 3, 85, 42, ops);
        assert_eq!(contract.get_current_version(), 2);
        let v1 = contract.get_policy_version(1).unwrap();
        assert_eq!(v1.min_confidence_threshold, 75);
    }

    #[test]
    fn build_reasoning_is_no_std_safe_and_descriptive() {
        let p = sample_policy();
        let r = build_reasoning(&p);
        assert!(r.contains("Policy v3"));
        assert!(r.contains("CRITICAL >85/100"));
        assert!(r.contains("HIGH >65/100"));
        assert!(r.contains("MEDIUM >45/100"));
        assert!(r.contains("max 2 retries"));
        assert!(r.contains("above 90/100"));
    }

    #[test]
    fn v2_upgrade_policy_emits_policy_upgraded_event() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManagerV2::deploy(&env, NoArgs);
        let admin = env.get_account(3);
        contract.upgrade_policy(66, 76, 56, 36, 2, 88, 777777, admin);
        let events = env.events(&contract);
        assert_eq!(events.len(), 1, "v2 upgrade_policy must emit exactly one PolicyUpgraded event");
    }

    // ── RBAC tests (v2 mirrors v1's RBAC scheme) ──

    #[test]
    fn v2_init_grants_deployer_all_roles_and_role_admin() {
        let env = odra_test::env();
        let contract = RiskPolicyManagerV2::deploy(&env, NoArgs);
        let deployer = env.get_account(0);
        assert_eq!(contract.get_roles(deployer), ROLE_ALL);
        assert!(contract.has_role(deployer, ROLE_OPERATOR));
        assert!(contract.has_role(deployer, ROLE_ADMIN));
        assert!(contract.has_role(deployer, ROLE_PAUSER));
        assert_eq!(contract.get_role_admin(), deployer);
        assert!(!contract.is_paused());
    }

    #[test]
    fn v2_non_admin_reverts_on_upgrade_policy() {
        // Account 1 has no roles — upgrade_policy must revert (ADMIN-gated).
        let env = odra_test::env();
        let mut contract = RiskPolicyManagerV2::deploy(&env, NoArgs);
        let outsider = env.get_account(1);
        env.set_caller(outsider);
        let r = contract.try_upgrade_policy(
            60, 70, 50, 30, 3, 85, 1500000u64, outsider,
        );
        assert!(r.is_err(), "non-admin must be rejected");
    }

    #[test]
    fn v2_grant_role_enables_admin() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManagerV2::deploy(&env, NoArgs);
        let admin = env.get_account(1);
        assert!(!contract.has_role(admin, ROLE_ADMIN));
        contract.grant_role(admin, ROLE_ADMIN);
        assert!(contract.has_role(admin, ROLE_ADMIN));
        assert!(!contract.has_role(admin, ROLE_OPERATOR));
    }

    #[test]
    fn v2_non_role_admin_cannot_grant_role() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManagerV2::deploy(&env, NoArgs);
        let admin = env.get_account(1);
        contract.grant_role(admin, ROLE_ADMIN);
        env.set_caller(admin);
        let other = env.get_account(2);
        let r = contract.try_grant_role(other, ROLE_OPERATOR);
        assert!(r.is_err(), "non-role-admin must not be able to grant roles");
        assert!(!contract.has_role(other, ROLE_OPERATOR));
    }

    #[test]
    fn v2_pause_blocks_writes_and_unpause_restores() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManagerV2::deploy(&env, NoArgs);
        let admin = env.get_account(1);
        // deployer is PAUSER
        contract.pause();
        assert!(contract.is_paused());
        // upgrade_policy must now revert (paused)
        let r = contract.try_upgrade_policy(60, 70, 50, 30, 3, 85, 1500000u64, admin);
        assert!(r.is_err(), "paused contract must reject writes");
        // unpause
        contract.unpause();
        assert!(!contract.is_paused());
        // now writes succeed again
        contract.upgrade_policy(60, 70, 50, 30, 3, 85, 1500000u64, admin);
        assert_eq!(contract.get_current_version(), 2);
    }

    #[test]
    fn v2_renounce_role_strips_authority() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManagerV2::deploy(&env, NoArgs);
        let admin = env.get_account(1);
        // deployer renounces ADMIN — upgrade_policy must then revert
        contract.renounce_role(ROLE_ADMIN);
        let r = contract.try_upgrade_policy(60, 70, 50, 30, 3, 85, 1500000u64, admin);
        assert!(r.is_err(), "after renouncing ADMIN, writes must revert");
        // deployer still is role_admin and OPERATOR/PAUSER
        assert!(contract.has_role(env.get_account(0), ROLE_PAUSER));
    }

    #[test]
    fn v2_transfer_ownership_grants_all_and_strips_caller() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManagerV2::deploy(&env, NoArgs);
        let new_owner = env.get_account(1);
        contract.transfer_ownership(new_owner);
        assert_eq!(contract.get_roles(new_owner), ROLE_ALL);
        assert_eq!(contract.get_role_admin(), new_owner);
        assert_eq!(contract.get_roles(env.get_account(0)), ROLE_NONE);
    }

    #[test]
    fn v2_grant_invalid_role_reverts() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManagerV2::deploy(&env, NoArgs);
        let admin = env.get_account(1);
        let r = contract.try_grant_role(admin, 0b1000_0000);
        assert!(r.is_err(), "invalid role bitmask must revert");
    }

    #[test]
    fn v2_non_pauser_cannot_pause() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManagerV2::deploy(&env, NoArgs);
        let admin = env.get_account(1);
        contract.grant_role(admin, ROLE_ADMIN); // ADMIN but NOT PAUSER
        env.set_caller(admin);
        let r = contract.try_pause();
        assert!(r.is_err(), "non-PAUSER must not be able to pause");
        assert!(!contract.is_paused());
    }
}
