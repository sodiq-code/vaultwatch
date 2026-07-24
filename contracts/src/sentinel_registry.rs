
/// SentinelRegistry — Subscriber registry for push alerts
///
/// Protocols register their webhook endpoints here. When a CRITICAL finding
/// is confirmed, the IntelAgent reads this registry and pushes alerts to
/// every registered subscriber. On-chain subscriber management — no database.
///
/// ## Access control
///
/// Uses role-based access control (see `crate::rbac`). The public
/// `register` / `deregister` entry points are pause-gated (so an incident
/// response can freeze subscriber churn without freezing reads). The
/// operational write `increment_alert_count` is OPERATOR-gated and
/// paused-aware. Role management is restricted to the `role_admin`. The
/// legacy `transfer_ownership` entry point is preserved as a backward-compat
/// shim that grants `ROLE_ALL` to the new address and transfers `role_admin`.

use odra::prelude::*;

use crate::rbac::{
    has_role, is_valid_role, ERR_INVALID_ROLE, ERR_PAUSED, ERR_UNAUTHORIZED,
    ROLE_ADMIN, ROLE_ALL, ROLE_NONE, ROLE_OPERATOR, ROLE_PAUSER,
};

/// Event emitted whenever a new subscriber registers for push alerts.
///
/// The IntelAgent / dashboard listens to this event to maintain a live view
/// of the subscriber registry without polling `get_count`.
#[odra::event]
pub struct SentinelRegistered {
    pub address: String,
    pub webhook_url: String,
    pub min_severity: String,
    pub registered_at: u64,
}

/// Event emitted whenever a role is granted or revoked, or the role-admin is
/// transferred. Provides an on-chain audit trail of every authorization change.
#[odra::event]
pub struct RoleChanged {
    pub account: Address,
    pub role: u8,
    pub granted: bool,
    pub by: Address,
}

/// Event emitted whenever the contract is paused or unpaused.
#[odra::event]
pub struct PauseChanged {
    pub paused: bool,
    pub by: Address,
}

#[odra::odra_type]
pub struct Subscriber {
    pub address: String,
    pub webhook_url: String,
    pub min_severity: String,  // CRITICAL | HIGH | MEDIUM | LOW
    pub active: bool,
    pub registered_at: u64,
    pub alert_count: u64,
}

#[odra::module(events = [SentinelRegistered, RoleChanged, PauseChanged])]
pub struct SentinelRegistry {
    subscribers: Mapping<String, Subscriber>,
    subscriber_count: Var<u64>,
    // ── RBAC state (replaces legacy `owner: Var<Address>`) ──
    /// Per-account role bitmask (OPERATOR | ADMIN | PAUSER).
    roles: Mapping<Address, u8>,
    /// The single role-manager — only account that may grant/revoke roles.
    role_admin: Var<Address>,
    /// Emergency pause flag. When true, every mutable entry point reverts.
    paused: Var<bool>,
}

#[odra::module]
impl SentinelRegistry {
    /// Initialize the contract — caller becomes role_admin and receives all
    /// three roles (ROLE_ALL). The contract starts unpaused.
    pub fn init(&mut self) {
        let caller = self.env().caller();
        self.role_admin.set(caller);
        self.roles.set(&caller, ROLE_ALL);
        self.paused.set(false);
        self.subscriber_count.set(0u64);
    }

    /// Register a new subscriber — public (no role required) but pause-gated
    /// so an incident response can freeze subscriber churn.
    pub fn register(
        &mut self,
        address: String,
        webhook_url: String,
        min_severity: String,
        timestamp: u64,
    ) {
        self.assert_not_paused();
        let sub = Subscriber {
            address: address.clone(),
            webhook_url: webhook_url.clone(),
            min_severity: min_severity.clone(),
            active: true,
            registered_at: timestamp,
            alert_count: 0,
        };
        self.subscribers.set(&address, sub);
        let count = self.subscriber_count.get_or_default() + 1;
        self.subscriber_count.set(count);

        // Emit the on-chain event so the IntelAgent / dashboard are notified.
        self.env().emit_event(SentinelRegistered {
            address,
            webhook_url,
            min_severity,
            registered_at: timestamp,
        });
    }

    /// Deactivate a subscriber — public (no role required) but pause-gated.
    pub fn deregister(&mut self, address: String) {
        self.assert_not_paused();
        match self.subscribers.get(&address) {
            Some(mut sub) => {
                sub.active = false;
                self.subscribers.set(&address, sub);
            }
            None => self.env().revert(ExecutionError::UnwrapError),
        }
    }

    /// Increment alert count for subscriber (called by IntelAgent after push) —
    /// OPERATOR-gated and paused-aware.
    pub fn increment_alert_count(&mut self, address: String) {
        self.assert_role(ROLE_OPERATOR);
        self.assert_not_paused();
        match self.subscribers.get(&address) {
            Some(mut sub) => {
                sub.alert_count += 1;
                self.subscribers.set(&address, sub);
            }
            None => {}
        }
    }

    pub fn get_subscriber(&self, address: String) -> Option<Subscriber> {
        self.subscribers.get(&address)
    }

    pub fn is_active(&self, address: String) -> bool {
        match self.subscribers.get(&address) {
            Some(sub) => sub.active,
            None => false,
        }
    }

    pub fn get_count(&self) -> u64 {
        self.subscriber_count.get_or_default()
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
}

#[cfg(test)]
mod tests {
    use super::*;
    use odra::host::{Deployer, NoArgs};

    #[test]
    fn test_register_and_get_subscriber() {
        let env = odra_test::env();
        let mut contract = SentinelRegistry::deploy(&env, NoArgs);
        contract.register(
            "casper1sub".to_string(),
            "https://hooks.example.com/vw".to_string(),
            "HIGH".to_string(),
            1500000,
        );
        assert_eq!(contract.get_count(), 1);
        let sub = contract.get_subscriber("casper1sub".to_string()).unwrap();
        assert!(sub.active);
        assert_eq!(sub.min_severity, "HIGH");
        assert_eq!(sub.alert_count, 0);
    }

    #[test]
    fn test_deregister_marks_inactive() {
        let env = odra_test::env();
        let mut contract = SentinelRegistry::deploy(&env, NoArgs);
        contract.register(
            "casper1sub".to_string(),
            "https://hooks.example.com/vw".to_string(),
            "HIGH".to_string(),
            1500000,
        );
        assert!(contract.is_active("casper1sub".to_string()));
        contract.deregister("casper1sub".to_string());
        assert!(!contract.is_active("casper1sub".to_string()));
    }

    #[test]
    fn test_increment_alert_count_as_operator() {
        let env = odra_test::env();
        let mut contract = SentinelRegistry::deploy(&env, NoArgs);
        contract.register(
            "casper1sub".to_string(),
            "https://hooks.example.com/vw".to_string(),
            "HIGH".to_string(),
            1500000,
        );
        // deployer has ROLE_ALL → OPERATOR
        contract.increment_alert_count("casper1sub".to_string());
        let sub = contract.get_subscriber("casper1sub".to_string()).unwrap();
        assert_eq!(sub.alert_count, 1);
    }

    // ── RBAC tests ──

    #[test]
    fn test_init_grants_deployer_all_roles_and_role_admin() {
        let env = odra_test::env();
        let contract = SentinelRegistry::deploy(&env, NoArgs);
        let deployer = env.get_account(0);
        assert_eq!(contract.get_roles(deployer), ROLE_ALL);
        assert!(contract.has_role(deployer, ROLE_OPERATOR));
        assert!(contract.has_role(deployer, ROLE_ADMIN));
        assert!(contract.has_role(deployer, ROLE_PAUSER));
        assert_eq!(contract.get_role_admin(), deployer);
        assert!(!contract.is_paused());
    }

    #[test]
    fn test_non_operator_reverts_on_increment_alert_count() {
        // Account 1 has no roles — increment_alert_count must revert.
        let env = odra_test::env();
        let mut contract = SentinelRegistry::deploy(&env, NoArgs);
        contract.register(
            "casper1sub".to_string(),
            "https://hooks.example.com/vw".to_string(),
            "HIGH".to_string(),
            1500000,
        );
        let outsider = env.get_account(1);
        env.set_caller(outsider);
        let r = contract.try_increment_alert_count("casper1sub".to_string());
        assert!(r.is_err(), "non-operator must be rejected");
        // alert_count unchanged
        let sub = contract.get_subscriber("casper1sub".to_string()).unwrap();
        assert_eq!(sub.alert_count, 0);
    }

    #[test]
    fn test_grant_role_enables_operator() {
        let env = odra_test::env();
        let mut contract = SentinelRegistry::deploy(&env, NoArgs);
        let ops = env.get_account(1);
        assert!(!contract.has_role(ops, ROLE_OPERATOR));
        contract.grant_role(ops, ROLE_OPERATOR);
        assert!(contract.has_role(ops, ROLE_OPERATOR));
        assert!(!contract.has_role(ops, ROLE_ADMIN));
    }

    #[test]
    fn test_non_role_admin_cannot_grant_role() {
        let env = odra_test::env();
        let mut contract = SentinelRegistry::deploy(&env, NoArgs);
        let ops = env.get_account(1);
        contract.grant_role(ops, ROLE_OPERATOR);
        env.set_caller(ops);
        let other = env.get_account(2);
        let r = contract.try_grant_role(other, ROLE_ADMIN);
        assert!(r.is_err(), "non-role-admin must not be able to grant roles");
        assert!(!contract.has_role(other, ROLE_ADMIN));
    }

    #[test]
    fn test_pause_blocks_writes_and_unpause_restores() {
        let env = odra_test::env();
        let mut contract = SentinelRegistry::deploy(&env, NoArgs);
        // deployer is PAUSER
        contract.pause();
        assert!(contract.is_paused());
        // register must now revert (paused)
        let r = contract.try_register(
            "casper1sub".to_string(),
            "https://hooks.example.com/vw".to_string(),
            "HIGH".to_string(),
            1500000u64,
        );
        assert!(r.is_err(), "paused contract must reject writes");
        // register count unchanged
        assert_eq!(contract.get_count(), 0);
        // unpause
        contract.unpause();
        assert!(!contract.is_paused());
        // now writes succeed again
        contract.register(
            "casper1sub".to_string(),
            "https://hooks.example.com/vw".to_string(),
            "HIGH".to_string(),
            1500000u64,
        );
        assert_eq!(contract.get_count(), 1);
    }

    #[test]
    fn test_renounce_role_strips_authority() {
        let env = odra_test::env();
        let mut contract = SentinelRegistry::deploy(&env, NoArgs);
        contract.register(
            "casper1sub".to_string(),
            "https://hooks.example.com/vw".to_string(),
            "HIGH".to_string(),
            1500000,
        );
        // deployer renounces OPERATOR — increment_alert_count must then revert
        contract.renounce_role(ROLE_OPERATOR);
        let r = contract.try_increment_alert_count("casper1sub".to_string());
        assert!(r.is_err(), "after renouncing OPERATOR, writes must revert");
        // deployer still is role_admin and ADMIN/PAUSER
        assert!(contract.has_role(env.get_account(0), ROLE_ADMIN));
    }

    #[test]
    fn test_transfer_ownership_grants_all_and_strips_caller() {
        let env = odra_test::env();
        let mut contract = SentinelRegistry::deploy(&env, NoArgs);
        let new_owner = env.get_account(1);
        contract.transfer_ownership(new_owner);
        assert_eq!(contract.get_roles(new_owner), ROLE_ALL);
        assert_eq!(contract.get_role_admin(), new_owner);
        assert_eq!(contract.get_roles(env.get_account(0)), ROLE_NONE);
    }

    #[test]
    fn test_grant_invalid_role_reverts() {
        let env = odra_test::env();
        let mut contract = SentinelRegistry::deploy(&env, NoArgs);
        let ops = env.get_account(1);
        let r = contract.try_grant_role(ops, 0b1000_0000);
        assert!(r.is_err(), "invalid role bitmask must revert");
    }

    #[test]
    fn test_non_pauser_cannot_pause() {
        let env = odra_test::env();
        let mut contract = SentinelRegistry::deploy(&env, NoArgs);
        let ops = env.get_account(1);
        contract.grant_role(ops, ROLE_OPERATOR); // OPERATOR but NOT PAUSER
        env.set_caller(ops);
        let r = contract.try_pause();
        assert!(r.is_err(), "non-PAUSER must not be able to pause");
        assert!(!contract.is_paused());
    }
}
