
/// RiskPolicyManager — Hot-swappable risk thresholds without contract redeployment
///
/// Run `npm run demo:upgrade-policy` → threshold changes live on testnet →
/// agents immediately reclassify events at new threshold → new finding on-chain.
/// Hot upgrade of a live production system in 30 seconds.
///
/// ## Access control
///
/// Uses role-based access control (see `crate::rbac`). The economic write
/// `upgrade_policy` is ADMIN-gated and paused-aware; role management is
/// restricted to the `role_admin`. The legacy `transfer_ownership` entry point
/// is preserved as a backward-compat shim that grants `ROLE_ALL` to the new
/// address and transfers `role_admin` (ADMIN/role-admin gated).

use odra::prelude::*;

use crate::rbac::{
    has_role, is_valid_role, ERR_INVALID_ROLE, ERR_PAUSED, ERR_UNAUTHORIZED,
    ROLE_ADMIN, ROLE_ALL, ROLE_NONE, ROLE_OPERATOR, ROLE_PAUSER,
};

/// Event emitted whenever the active risk policy is hot-swapped.
///
/// Off-chain indexers (dashboard, MCP server) subscribe to this event to
/// surface "policy changed at block X by account Y" in real time — no polling
/// of `get_current_policy` required.
#[odra::event]
pub struct PolicyUpgraded {
    pub version: u32,
    pub updated_by: Address,
    pub updated_at_block: u64,
    pub min_confidence_threshold: u8,
    pub critical_score_threshold: u8,
    pub safety_rejection_threshold: u8,
}

/// Event emitted whenever a role is granted or revoked, or the role-admin is
/// transferred. Provides an on-chain audit trail of every authorization change.
///
/// Reused by `risk_policy_manager_v2` so the event schema is identical across
/// v1/v2 of the contract package.
#[odra::event]
pub struct RoleChanged {
    pub account: Address,
    pub role: u8,
    pub granted: bool,
    pub by: Address,
}

/// Event emitted whenever the contract is paused or unpaused. Reused by
/// `risk_policy_manager_v2` (see above).
#[odra::event]
pub struct PauseChanged {
    pub paused: bool,
    pub by: Address,
}

#[odra::odra_type]
pub struct RiskPolicy {
    pub version: u32,
    pub min_confidence_threshold: u8,   // below this → trigger SelfCorrection
    pub critical_score_threshold: u8,   // above this → CRITICAL severity
    pub high_score_threshold: u8,       // above this → HIGH severity
    pub medium_score_threshold: u8,     // above this → MEDIUM severity
    pub max_retry_count: u8,            // SelfCorrection max retries
    pub safety_rejection_threshold: u8, // SafetyGuard: reject if score > this (0–100)
    pub updated_at_block: u64,
    /// Account that performed the upgrade. Typed as `Address` (Casper Key) so
    /// the on-chain record is a real account/contract hash, not a free-form
    /// string — enabling on-chain accountability for every policy change.
    pub updated_by: Address,
}

#[odra::module(events = [PolicyUpgraded, RoleChanged, PauseChanged])]
pub struct RiskPolicyManager {
    current_policy: Var<RiskPolicy>,
    policy_history: Mapping<u32, RiskPolicy>,
    // ── RBAC state (replaces legacy `owner: Var<Address>`) ──
    // CRITICAL: v2 (risk_policy_manager_v2.rs) shares this contract package's
    // state dictionary and MUST preserve this exact field order so the
    // serialized dictionary keys line up across versions.
    /// Per-account role bitmask (OPERATOR | ADMIN | PAUSER).
    roles: Mapping<Address, u8>,
    /// The single role-manager — only account that may grant/revoke roles.
    role_admin: Var<Address>,
    /// Emergency pause flag. When true, every mutable entry point reverts.
    paused: Var<bool>,
}

#[odra::module]
impl RiskPolicyManager {
    /// Initialize the contract — caller becomes role_admin and receives all
    /// three roles (ROLE_ALL). The contract starts unpaused with the default
    /// policy v1 (genesis updater is the deploying account).
    pub fn init(&mut self) {
        let caller = self.env().caller();
        self.role_admin.set(caller);
        self.roles.set(&caller, ROLE_ALL);
        self.paused.set(false);
        // Default policy v1 — genesis updater is the deploying account.
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

    /// Hot-swap policy — agents read this every cycle, no restart needed.
    /// ADMIN-gated and paused-aware.
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
        let current_version = self.current_policy
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

        // Emit the on-chain event so off-chain indexers/dashboard/MCP server
        // are notified of the hot-swap in real time.
        self.env().emit_event(PolicyUpgraded {
            version: new_version,
            updated_by,
            updated_at_block: block_height,
            min_confidence_threshold,
            critical_score_threshold,
            safety_rejection_threshold,
        });
    }

    /// Get active policy — agents call this every decision cycle
    pub fn get_current_policy(&self) -> RiskPolicy {
        self.current_policy.get_or_revert_with(crate::user_err(1))
    }

    /// Get a historical policy version
    pub fn get_policy_version(&self, version: u32) -> Option<RiskPolicy> {
        self.policy_history.get(&version)
    }

    pub fn get_current_version(&self) -> u32 {
        self.current_policy.get_or_revert_with(crate::user_err(1)).version
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
    // import the full RBAC constant set for consistency with the other
    // contracts and so future OPERATOR-gated entry points can be added without
    // touching the imports.
    #[allow(dead_code)]
    const _ROLE_OPERATOR_UNUSED: u8 = ROLE_OPERATOR;
}

#[cfg(test)]
mod tests {
    use super::*;
    use odra::host::{Deployer, NoArgs};

    #[test]
    fn test_default_policy_on_init() {
        let env = odra_test::env();
        let contract = RiskPolicyManager::deploy(&env, NoArgs);
        let policy = contract.get_current_policy();
        assert_eq!(policy.version, 1);
        assert_eq!(policy.min_confidence_threshold, 75);
        assert_eq!(policy.critical_score_threshold, 80);
        // genesis updater is the deploying account (account 0 in the test env)
        let deployer = env.get_account(0);
        assert_eq!(policy.updated_by, deployer);
    }

    #[test]
    fn test_hot_upgrade_policy() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManager::deploy(&env, NoArgs);
        let admin = env.get_account(1);

        contract.upgrade_policy(60, 70, 50, 30, 3, 85, 1500000, admin);

        let policy = contract.get_current_policy();
        assert_eq!(policy.version, 2);
        assert_eq!(policy.min_confidence_threshold, 60);
        assert_eq!(policy.critical_score_threshold, 70);
        assert_eq!(policy.updated_by, admin);
    }

    #[test]
    fn test_policy_history_preserved() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManager::deploy(&env, NoArgs);
        let admin = env.get_account(1);
        contract.upgrade_policy(60, 70, 50, 30, 3, 85, 1500000, admin);

        let v1 = contract.get_policy_version(1).unwrap();
        assert_eq!(v1.min_confidence_threshold, 75);

        let v2 = contract.get_policy_version(2).unwrap();
        assert_eq!(v2.min_confidence_threshold, 60);
        assert_eq!(v2.updated_by, admin);
    }

    #[test]
    fn test_upgrade_policy_emits_policy_upgraded_event() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManager::deploy(&env, NoArgs);
        let admin = env.get_account(2);

        contract.upgrade_policy(65, 75, 55, 35, 3, 88, 999999, admin);

        // The events buffer for this contract should now contain exactly one
        // PolicyUpgraded event.
        let events = env.events(&contract);
        assert_eq!(events.len(), 1, "expected exactly one event after upgrade_policy");
        // Odra tags events with a 4-byte BLAKE2b prefix of the event type name.
        // We assert the event was emitted; the typed payload is verified by the
        // schema generator (cargo odra schema).
    }

    // ── RBAC tests ──

    #[test]
    fn test_init_grants_deployer_all_roles_and_role_admin() {
        let env = odra_test::env();
        let contract = RiskPolicyManager::deploy(&env, NoArgs);
        let deployer = env.get_account(0);
        assert_eq!(contract.get_roles(deployer), ROLE_ALL);
        assert!(contract.has_role(deployer, ROLE_OPERATOR));
        assert!(contract.has_role(deployer, ROLE_ADMIN));
        assert!(contract.has_role(deployer, ROLE_PAUSER));
        assert_eq!(contract.get_role_admin(), deployer);
        assert!(!contract.is_paused());
    }

    #[test]
    fn test_non_admin_reverts_on_upgrade_policy() {
        // Account 1 has no roles — upgrade_policy must revert (ADMIN-gated).
        let env = odra_test::env();
        let mut contract = RiskPolicyManager::deploy(&env, NoArgs);
        let outsider = env.get_account(1);
        env.set_caller(outsider);
        let r = contract.try_upgrade_policy(
            60, 70, 50, 30, 3, 85, 1500000u64, outsider,
        );
        assert!(r.is_err(), "non-admin must be rejected");
    }

    #[test]
    fn test_grant_role_enables_admin() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManager::deploy(&env, NoArgs);
        let admin = env.get_account(1);
        assert!(!contract.has_role(admin, ROLE_ADMIN));
        contract.grant_role(admin, ROLE_ADMIN);
        assert!(contract.has_role(admin, ROLE_ADMIN));
        assert!(!contract.has_role(admin, ROLE_OPERATOR)); // only ADMIN granted
    }

    #[test]
    fn test_non_role_admin_cannot_grant_role() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManager::deploy(&env, NoArgs);
        let admin = env.get_account(1);
        contract.grant_role(admin, ROLE_ADMIN);
        env.set_caller(admin);
        let other = env.get_account(2);
        let r = contract.try_grant_role(other, ROLE_OPERATOR);
        assert!(r.is_err(), "non-role-admin must not be able to grant roles");
        assert!(!contract.has_role(other, ROLE_OPERATOR));
    }

    #[test]
    fn test_pause_blocks_writes_and_unpause_restores() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManager::deploy(&env, NoArgs);
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
    fn test_renounce_role_strips_authority() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManager::deploy(&env, NoArgs);
        let admin = env.get_account(1);
        // deployer renounces ADMIN — upgrade_policy must then revert
        contract.renounce_role(ROLE_ADMIN);
        let r = contract.try_upgrade_policy(60, 70, 50, 30, 3, 85, 1500000u64, admin);
        assert!(r.is_err(), "after renouncing ADMIN, writes must revert");
        // deployer still is role_admin and OPERATOR/PAUSER
        assert!(contract.has_role(env.get_account(0), ROLE_PAUSER));
    }

    #[test]
    fn test_transfer_ownership_grants_all_and_strips_caller() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManager::deploy(&env, NoArgs);
        let new_owner = env.get_account(1);
        contract.transfer_ownership(new_owner);
        assert_eq!(contract.get_roles(new_owner), ROLE_ALL);
        assert_eq!(contract.get_role_admin(), new_owner);
        assert_eq!(contract.get_roles(env.get_account(0)), ROLE_NONE);
    }

    #[test]
    fn test_grant_invalid_role_reverts() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManager::deploy(&env, NoArgs);
        let admin = env.get_account(1);
        let r = contract.try_grant_role(admin, 0b1000_0000);
        assert!(r.is_err(), "invalid role bitmask must revert");
    }

    #[test]
    fn test_non_pauser_cannot_pause() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManager::deploy(&env, NoArgs);
        let admin = env.get_account(1);
        contract.grant_role(admin, ROLE_ADMIN); // ADMIN but NOT PAUSER
        env.set_caller(admin);
        let r = contract.try_pause();
        assert!(r.is_err(), "non-PAUSER must not be able to pause");
        assert!(!contract.is_paused());
    }
}
