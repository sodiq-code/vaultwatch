
/// SentinelAlertLog — Timestamped on-chain alert history per address
///
/// Every alert pushed to a subscriber is logged here immutably.
/// Compliance-grade: any protocol can prove "we received a CRITICAL alert
/// at block X from VaultWatch"
///
/// ## Access control
///
/// Uses role-based access control (see `crate::rbac`). `log_alert` is
/// OPERATOR-gated and paused-aware; role management is restricted to the
/// `role_admin`. The legacy `transfer_ownership` entry point is preserved as a
/// backward-compat shim that grants `ROLE_ALL` to the new address and transfers
/// `role_admin` (ADMIN/role-admin gated).

use odra::prelude::*;

use crate::rbac::{
    has_role, is_valid_role, ERR_INVALID_ROLE, ERR_PAUSED, ERR_UNAUTHORIZED,
    ROLE_ADMIN, ROLE_ALL, ROLE_NONE, ROLE_OPERATOR, ROLE_PAUSER,
};

/// Event emitted whenever an alert is logged on-chain.
///
/// Off-chain subscribers / dashboards listen to this event for real-time
/// notification of new alerts — no polling of `get_total_count` required.
#[odra::event]
pub struct AlertLogged {
    pub log_id: u64,
    pub subscriber_address: Address,
    pub finding_id: u64,
    pub severity: String,
    pub block_height: u64,
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
pub struct AlertRecord {
    pub log_id: u64,
    /// Subscriber's on-chain identity — typed as `Address` (Casper Key) so it
    /// is a real account/contract hash, not a free-form string. This enables
    /// deterministic per-subscriber indexing and cross-contract lookups.
    pub subscriber_address: Address,
    pub finding_id: u64,
    pub severity: String,
    pub risk_type: String,
    pub block_height: u64,
    pub timestamp: u64,
    pub delivered: bool,
}

#[odra::module(events = [AlertLogged, RoleChanged, PauseChanged])]
pub struct SentinelAlertLog {
    logs: Mapping<u64, AlertRecord>,
    log_count: Var<u64>,
    // address → list of log IDs (typed Vec<u64>, capped at MAX_ADDRESS_LOG_IDS).
    // Previously a comma-separated String, which was unbounded, required parsing
    // off-chain, and could blow up global-state URef values for noisy accounts.
    // A bounded Vec<u64> keeps per-address history deterministic and cheap.
    address_logs: Mapping<Address, Vec<u64>>,
    // ── RBAC state (replaces legacy `owner: Var<Address>`) ──
    /// Per-account role bitmask (OPERATOR | ADMIN | PAUSER).
    roles: Mapping<Address, u8>,
    /// The single role-manager — only account that may grant/revoke roles.
    role_admin: Var<Address>,
    /// Emergency pause flag. When true, every mutable entry point reverts.
    paused: Var<bool>,
}

/// Hard cap on the number of log IDs retained per subscriber address.
///
/// When the cap is exceeded the oldest IDs are evicted first (FIFO), so the
/// index always reflects the most-recent `MAX_ADDRESS_LOG_IDS` alerts. 256
/// keeps a single subscriber's on-chain footprint bounded while preserving
/// enough history for compliance lookbacks.
const MAX_ADDRESS_LOG_IDS: usize = 256;

#[odra::module]
impl SentinelAlertLog {
    /// Initialize the contract — caller becomes role_admin and receives all
    /// three roles (ROLE_ALL). The contract starts unpaused.
    pub fn init(&mut self) {
        let caller = self.env().caller();
        self.role_admin.set(caller);
        self.roles.set(&caller, ROLE_ALL);
        self.paused.set(false);
        self.log_count.set(0u64);
    }

    /// Log a delivered alert — only callable by an OPERATOR when not paused.
    pub fn log_alert(
        &mut self,
        subscriber_address: Address,
        finding_id: u64,
        severity: String,
        risk_type: String,
        block_height: u64,
        timestamp: u64,
        delivered: bool,
    ) -> u64 {
        self.assert_role(ROLE_OPERATOR);
        self.assert_not_paused();
        let log_id = self.log_count.get_or_default() + 1;
        let record = AlertRecord {
            log_id,
            subscriber_address: subscriber_address.clone(),
            finding_id,
            severity: severity.clone(),
            risk_type,
            block_height,
            timestamp,
            delivered,
        };
        self.logs.set(&log_id, record);
        self.log_count.set(log_id);

        // Append to the per-address log-ID index (Vec<u64>, FIFO-capped at 256).
        // unwrap_or_default yields an empty Vec for first-time subscribers.
        let mut ids = self.address_logs.get(&subscriber_address).unwrap_or_default();
        ids.push(log_id);
        if ids.len() > MAX_ADDRESS_LOG_IDS {
            // Drop the oldest entries first so only the most-recent 256 remain.
            let drop_count = ids.len() - MAX_ADDRESS_LOG_IDS;
            ids.drain(0..drop_count);
        }
        self.address_logs.set(&subscriber_address, ids);

        // Emit the on-chain event so off-chain indexers/dashboard are notified.
        self.env().emit_event(AlertLogged {
            log_id,
            subscriber_address,
            finding_id,
            severity,
            block_height,
        });

        log_id
    }

    pub fn get_log(&self, log_id: u64) -> AlertRecord {
        self.logs.get(&log_id).unwrap_or_revert(self)
    }

    /// Returns the list of log IDs recorded for `address`, most-recent last.
    ///
    /// The returned `Vec<u64>` is capped at `MAX_ADDRESS_LOG_IDS` (256); once an
    /// address exceeds the cap the oldest IDs are evicted. An address with no
    /// alerts returns an empty Vec.
    pub fn get_address_log_ids(&self, address: Address) -> Vec<u64> {
        self.address_logs.get(&address).unwrap_or_default()
    }

    pub fn get_total_count(&self) -> u64 {
        self.log_count.get_or_default()
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
    fn test_log_and_retrieve_alert() {
        let env = odra_test::env();
        let mut contract = SentinelAlertLog::deploy(&env, NoArgs);
        let sub = env.get_account(1);

        let id = contract.log_alert(
            sub, 1, "CRITICAL".to_string(),
            "whale_dump".to_string(), 1500000, 1750000000, true
        );
        assert_eq!(id, 1);
        let log = contract.get_log(1);
        assert_eq!(log.severity, "CRITICAL");
        assert!(log.delivered);
        assert_eq!(log.subscriber_address, sub);
    }

    #[test]
    fn test_address_log_index() {
        let env = odra_test::env();
        let mut contract = SentinelAlertLog::deploy(&env, NoArgs);
        let sub = env.get_account(1);

        contract.log_alert(sub, 1, "CRITICAL".to_string(), "whale_dump".to_string(), 100, 200, true);
        contract.log_alert(sub, 2, "HIGH".to_string(), "depeg".to_string(), 101, 201, true);

        let ids = contract.get_address_log_ids(sub);
        assert_eq!(ids, vec![1u64, 2u64]);
    }

    #[test]
    fn test_address_log_ids_empty_for_unknown_address() {
        let env = odra_test::env();
        let contract = SentinelAlertLog::deploy(&env, NoArgs);
        let sub = env.get_account(2);

        let ids = contract.get_address_log_ids(sub);
        assert!(ids.is_empty(), "unknown address must return an empty Vec");
    }

    #[test]
    fn test_address_log_ids_capped_at_256() {
        let env = odra_test::env();
        let mut contract = SentinelAlertLog::deploy(&env, NoArgs);
        let sub = env.get_account(1);

        // Log 260 alerts for the same subscriber — the index must cap at 256
        // most-recent IDs (FIFO eviction of the oldest 4).
        for i in 1..=260u64 {
            contract.log_alert(
                sub,
                i,
                "HIGH".to_string(),
                "depeg".to_string(),
                100 + i,
                200 + i,
                true,
            );
        }

        let ids = contract.get_address_log_ids(sub);
        assert_eq!(ids.len(), 256, "address log index must be capped at 256");
        // FIFO: oldest 4 (ids 1..=4) dropped; first retained is 5, last is 260.
        assert_eq!(ids[0], 5, "oldest entries are evicted first (FIFO)");
        assert_eq!(*ids.last().unwrap(), 260, "most-recent entry is retained");
        // Monotonic ascending order preserved after eviction.
        assert!(ids.windows(2).all(|w| w[0] < w[1]));
    }

    #[test]
    fn test_log_alert_emits_alert_logged_event() {
        let env = odra_test::env();
        let mut contract = SentinelAlertLog::deploy(&env, NoArgs);
        let sub = env.get_account(2);

        contract.log_alert(
            sub, 7, "HIGH".to_string(), "depeg".to_string(), 1234, 1700000000, true
        );

        let events = env.events(&contract);
        assert_eq!(events.len(), 1, "log_alert must emit exactly one AlertLogged event");
    }

    // ── RBAC tests ──

    #[test]
    fn test_init_grants_deployer_all_roles_and_role_admin() {
        let env = odra_test::env();
        let contract = SentinelAlertLog::deploy(&env, NoArgs);
        let deployer = env.get_account(0);
        assert_eq!(contract.get_roles(deployer), ROLE_ALL);
        assert!(contract.has_role(deployer, ROLE_OPERATOR));
        assert!(contract.has_role(deployer, ROLE_ADMIN));
        assert!(contract.has_role(deployer, ROLE_PAUSER));
        assert_eq!(contract.get_role_admin(), deployer);
        assert!(!contract.is_paused());
    }

    #[test]
    fn test_non_operator_reverts_on_log_alert() {
        // Account 1 has no roles — log_alert must revert.
        let env = odra_test::env();
        let mut contract = SentinelAlertLog::deploy(&env, NoArgs);
        let outsider = env.get_account(1);
        env.set_caller(outsider);
        let r = contract.try_log_alert(
            outsider, 1, "HIGH".to_string(), "depeg".to_string(), 100u64, 200u64, true,
        );
        assert!(r.is_err(), "non-operator must be rejected");
    }

    #[test]
    fn test_grant_role_enables_operator() {
        let env = odra_test::env();
        let mut contract = SentinelAlertLog::deploy(&env, NoArgs);
        let ops = env.get_account(1);
        assert!(!contract.has_role(ops, ROLE_OPERATOR));
        contract.grant_role(ops, ROLE_OPERATOR);
        assert!(contract.has_role(ops, ROLE_OPERATOR));
        assert!(!contract.has_role(ops, ROLE_ADMIN));
    }

    #[test]
    fn test_non_role_admin_cannot_grant_role() {
        let env = odra_test::env();
        let mut contract = SentinelAlertLog::deploy(&env, NoArgs);
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
        let mut contract = SentinelAlertLog::deploy(&env, NoArgs);
        let sub = env.get_account(1);
        // deployer is PAUSER
        contract.pause();
        assert!(contract.is_paused());
        // log_alert must now revert (paused)
        let r = contract.try_log_alert(
            sub, 1, "HIGH".to_string(), "depeg".to_string(), 100u64, 200u64, true,
        );
        assert!(r.is_err(), "paused contract must reject writes");
        // unpause
        contract.unpause();
        assert!(!contract.is_paused());
        // now writes succeed again
        let id = contract.log_alert(
            sub, 1, "HIGH".to_string(), "depeg".to_string(), 100u64, 200u64, true,
        );
        assert_eq!(id, 1);
    }

    #[test]
    fn test_renounce_role_strips_authority() {
        let env = odra_test::env();
        let mut contract = SentinelAlertLog::deploy(&env, NoArgs);
        let sub = env.get_account(1);
        // deployer renounces OPERATOR — log_alert must then revert
        contract.renounce_role(ROLE_OPERATOR);
        let r = contract.try_log_alert(
            sub, 1, "HIGH".to_string(), "depeg".to_string(), 100u64, 200u64, true,
        );
        assert!(r.is_err(), "after renouncing OPERATOR, writes must revert");
        // deployer still is role_admin and ADMIN/PAUSER
        assert!(contract.has_role(env.get_account(0), ROLE_ADMIN));
    }

    #[test]
    fn test_transfer_ownership_grants_all_and_strips_caller() {
        let env = odra_test::env();
        let mut contract = SentinelAlertLog::deploy(&env, NoArgs);
        let new_owner = env.get_account(1);
        contract.transfer_ownership(new_owner);
        assert_eq!(contract.get_roles(new_owner), ROLE_ALL);
        assert_eq!(contract.get_role_admin(), new_owner);
        assert_eq!(contract.get_roles(env.get_account(0)), ROLE_NONE);
    }

    #[test]
    fn test_grant_invalid_role_reverts() {
        let env = odra_test::env();
        let mut contract = SentinelAlertLog::deploy(&env, NoArgs);
        let ops = env.get_account(1);
        let r = contract.try_grant_role(ops, 0b1000_0000);
        assert!(r.is_err(), "invalid role bitmask must revert");
    }

    #[test]
    fn test_non_pauser_cannot_pause() {
        let env = odra_test::env();
        let mut contract = SentinelAlertLog::deploy(&env, NoArgs);
        let ops = env.get_account(1);
        contract.grant_role(ops, ROLE_OPERATOR); // OPERATOR but NOT PAUSER
        env.set_caller(ops);
        let r = contract.try_pause();
        assert!(r.is_err(), "non-PAUSER must not be able to pause");
        assert!(!contract.is_paused());
    }
}
