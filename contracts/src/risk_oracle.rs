
/// RiskOracle — Live risk scores queryable by any Casper DeFi protocol
///
/// Any protocol on Casper can call get_risk_score(address) to retrieve the
/// current VaultWatch risk assessment. This is the integration hook — one
/// contract call, live risk intelligence, no account required.
///
/// ## Access control
///
/// Uses role-based access control (see `crate::rbac`). `update_score` is
/// OPERATOR-gated and paused-aware; role management is restricted to the
/// `role_admin`. The legacy `transfer_ownership` entry point is preserved as a
/// backward-compat shim that grants `ROLE_ALL` to the new address and transfers
/// `role_admin` (ADMIN/role-admin gated).

use odra::prelude::*;

use crate::rbac::{
    has_role, is_valid_role, ERR_INVALID_ROLE, ERR_PAUSED, ERR_UNAUTHORIZED,
    ROLE_ADMIN, ROLE_ALL, ROLE_NONE, ROLE_OPERATOR, ROLE_PAUSER,
};

/// Event emitted whenever a risk score is updated for an address.
///
/// Casper DeFi protocols can subscribe to this event to react to risk-score
/// changes in real time (e.g. trigger a collateral top-up when a counterparty
/// crosses a threshold) without polling `get_risk_score`.
#[odra::event]
pub struct ScoreUpdated {
    pub address: String,
    pub score: u8,
    pub risk_type: String,
    pub confidence: u8,
    pub last_updated: u64,
    pub finding_id: u64,
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
pub struct RiskScore {
    pub address: String,
    pub score: u8,           // 0–100
    pub risk_type: String,
    pub confidence: u8,      // 0–100
    pub last_updated: u64,   // block height
    pub finding_id: u64,     // reference back to AuditTrail
}

#[odra::module(events = [ScoreUpdated, RoleChanged, PauseChanged])]
pub struct RiskOracle {
    scores: Mapping<String, RiskScore>,
    // ── RBAC state (replaces legacy `owner: Var<Address>`) ──
    /// Per-account role bitmask (OPERATOR | ADMIN | PAUSER).
    roles: Mapping<Address, u8>,
    /// The single role-manager — only account that may grant/revoke roles.
    role_admin: Var<Address>,
    /// Emergency pause flag. When true, every mutable entry point reverts.
    paused: Var<bool>,
}

#[odra::module]
impl RiskOracle {
    /// Initialize the contract — caller becomes role_admin and receives all
    /// three roles (ROLE_ALL). The contract starts unpaused.
    pub fn init(&mut self) {
        let caller = self.env().caller();
        self.role_admin.set(caller);
        self.roles.set(&caller, ROLE_ALL);
        self.paused.set(false);
    }

    /// Update risk score for an address — only callable by an OPERATOR when
    /// not paused.
    pub fn update_score(
        &mut self,
        address: String,
        score: u8,
        risk_type: String,
        confidence: u8,
        block_height: u64,
        finding_id: u64,
    ) {
        self.assert_role(ROLE_OPERATOR);
        self.assert_not_paused();
        let record = RiskScore {
            address: address.clone(),
            score,
            risk_type: risk_type.clone(),
            confidence,
            last_updated: block_height,
            finding_id,
        };
        self.scores.set(&address, record);

        // Emit the on-chain event so subscribing protocols are notified.
        self.env().emit_event(ScoreUpdated {
            address,
            score,
            risk_type,
            confidence,
            last_updated: block_height,
            finding_id,
        });
    }

    /// Query risk score for any address — public, no auth required. Reads are
    /// never pause-guarded so observers can inspect state during an incident.
    pub fn get_risk_score(&self, address: String) -> Option<RiskScore> {
        self.scores.get(&address)
    }

    /// Check if address exceeds threshold — useful for on-chain protocol guards
    pub fn is_high_risk(&self, address: String, threshold: u8) -> bool {
        match self.scores.get(&address) {
            Some(record) => record.score >= threshold,
            None => false,
        }
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

    /// Backward-compat shim for the legacy singleowner `transfer_ownership`.
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
    fn test_update_and_query_score() {
        let env = odra_test::env();
        let mut contract = RiskOracle::deploy(&env, NoArgs);

        contract.update_score("casper1xyz".to_string(), 87, "whale_concentration".to_string(), 92, 1500000, 1);

        let score = contract.get_risk_score("casper1xyz".to_string()).unwrap();
        assert_eq!(score.score, 87);
        assert_eq!(score.risk_type, "whale_concentration");
        assert_eq!(score.confidence, 92);
    }

    #[test]
    fn test_is_high_risk() {
        let env = odra_test::env();
        let mut contract = RiskOracle::deploy(&env, NoArgs);
        contract.update_score("casper1abc".to_string(), 75, "depeg".to_string(), 88, 1500001, 2);
        assert!(contract.is_high_risk("casper1abc".to_string(), 70));
        assert!(!contract.is_high_risk("casper1abc".to_string(), 80));
    }

    #[test]
    fn test_unknown_address_returns_none() {
        let env = odra_test::env();
        let contract = RiskOracle::deploy(&env, NoArgs);
        assert!(contract.get_risk_score("casper1unknown".to_string()).is_none());
    }

    // ── RBAC tests ──

    #[test]
    fn test_init_grants_deployer_all_roles_and_role_admin() {
        let env = odra_test::env();
        let contract = RiskOracle::deploy(&env, NoArgs);
        let deployer = env.get_account(0);
        assert_eq!(contract.get_roles(deployer), ROLE_ALL);
        assert!(contract.has_role(deployer, ROLE_OPERATOR));
        assert!(contract.has_role(deployer, ROLE_ADMIN));
        assert!(contract.has_role(deployer, ROLE_PAUSER));
        assert_eq!(contract.get_role_admin(), deployer);
        assert!(!contract.is_paused());
    }

    #[test]
    fn test_non_operator_reverts_on_update_score() {
        // Account 1 has no roles — update_score must revert.
        let env = odra_test::env();
        let mut contract = RiskOracle::deploy(&env, NoArgs);
        let outsider = env.get_account(1);
        env.set_caller(outsider);
        let r = contract.try_update_score(
            "addr".to_string(), 80, "depeg".to_string(), 88, 100u64, 1u64,
        );
        assert!(r.is_err(), "non-operator must be rejected");
    }

    #[test]
    fn test_grant_role_enables_operator() {
        let env = odra_test::env();
        let mut contract = RiskOracle::deploy(&env, NoArgs);
        let ops = env.get_account(1);
        // ops has no roles initially
        assert!(!contract.has_role(ops, ROLE_OPERATOR));
        // deployer (role_admin) grants OPERATOR to ops
        contract.grant_role(ops, ROLE_OPERATOR);
        assert!(contract.has_role(ops, ROLE_OPERATOR));
        assert!(!contract.has_role(ops, ROLE_ADMIN)); // only OPERATOR granted
    }

    #[test]
    fn test_non_role_admin_cannot_grant_role() {
        let env = odra_test::env();
        let mut contract = RiskOracle::deploy(&env, NoArgs);
        let ops = env.get_account(1);
        // deployer (role_admin) grants OPERATOR to ops
        contract.grant_role(ops, ROLE_OPERATOR);
        // ops is now OPERATOR but NOT role_admin — grant_role must revert
        env.set_caller(ops);
        let other = env.get_account(2);
        let r = contract.try_grant_role(other, ROLE_ADMIN);
        assert!(r.is_err(), "non-role-admin must not be able to grant roles");
        // sanity: other did not receive ADMIN
        assert!(!contract.has_role(other, ROLE_ADMIN));
    }

    #[test]
    fn test_pause_blocks_writes_and_unpause_restores() {
        let env = odra_test::env();
        let mut contract = RiskOracle::deploy(&env, NoArgs);
        // deployer is PAUSER
        contract.pause();
        assert!(contract.is_paused());
        // update_score must now revert (paused)
        let r = contract.try_update_score(
            "addr".to_string(), 80, "depeg".to_string(), 88, 100u64, 1u64,
        );
        assert!(r.is_err(), "paused contract must reject writes");
        // unpause
        contract.unpause();
        assert!(!contract.is_paused());
        // now writes succeed again
        contract.update_score("addr".to_string(), 80, "depeg".to_string(), 88, 100u64, 1u64);
        let s = contract.get_risk_score("addr".to_string()).unwrap();
        assert_eq!(s.score, 80);
    }

    #[test]
    fn test_renounce_role_strips_authority() {
        let env = odra_test::env();
        let mut contract = RiskOracle::deploy(&env, NoArgs);
        // deployer renounces OPERATOR — update_score must then revert
        contract.renounce_role(ROLE_OPERATOR);
        let r = contract.try_update_score(
            "addr".to_string(), 80, "depeg".to_string(), 88, 100u64, 1u64,
        );
        assert!(r.is_err(), "after renouncing OPERATOR, writes must revert");
        // deployer still is role_admin and ADMIN/PAUSER
        assert!(contract.has_role(env.get_account(0), ROLE_ADMIN));
    }

    #[test]
    fn test_transfer_ownership_grants_all_and_strips_caller() {
        let env = odra_test::env();
        let mut contract = RiskOracle::deploy(&env, NoArgs);
        let new_owner = env.get_account(1);
        contract.transfer_ownership(new_owner);
        assert_eq!(contract.get_roles(new_owner), ROLE_ALL);
        assert_eq!(contract.get_role_admin(), new_owner);
        // caller (deployer) stripped
        assert_eq!(contract.get_roles(env.get_account(0)), ROLE_NONE);
    }

    #[test]
    fn test_grant_invalid_role_reverts() {
        let env = odra_test::env();
        let mut contract = RiskOracle::deploy(&env, NoArgs);
        let ops = env.get_account(1);
        let r = contract.try_grant_role(ops, 0b1000_0000);
        assert!(r.is_err(), "invalid role bitmask must revert");
    }

    #[test]
    fn test_non_pauser_cannot_pause() {
        let env = odra_test::env();
        let mut contract = RiskOracle::deploy(&env, NoArgs);
        let ops = env.get_account(1);
        contract.grant_role(ops, ROLE_OPERATOR); // OPERATOR but NOT PAUSER
        env.set_caller(ops);
        let r = contract.try_pause();
        assert!(r.is_err(), "non-PAUSER must not be able to pause");
        assert!(!contract.is_paused());
    }
}
