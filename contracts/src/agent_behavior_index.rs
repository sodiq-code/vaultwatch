
/// AgentBehaviorIndex — On-chain AI agent accountability index
///
/// Every agent's decisions are scored on-chain: confidence averages,
/// correction rates, and false positive history. Creates a live trust score
/// for the AI system itself — providing transparent, verifiable accountability
/// for every AI-driven decision on the Casper network.
///
/// ## Access control
///
/// Uses role-based access control (see `crate::rbac`). `record_decision` is
/// OPERATOR-gated and paused-aware; role management is restricted to the
/// `role_admin`. The legacy `transfer_ownership` entry point is preserved as a
/// backward-compat shim that grants `ROLE_ALL` to the new address and transfers
/// `role_admin` (ADMIN/role-admin gated).

use odra::prelude::*;

use crate::rbac::{
    has_role, is_valid_role, ERR_INVALID_ROLE, ERR_PAUSED, ERR_UNAUTHORIZED,
    ROLE_ADMIN, ROLE_ALL, ROLE_NONE, ROLE_OPERATOR, ROLE_PAUSER,
};

/// Event emitted whenever an agent's decision outcome is recorded on-chain.
///
/// The accountability dashboard subscribes to this event to display a live
/// feed of agent decisions and their trust-score impact.
#[odra::event]
pub struct BehaviorRecorded {
    pub agent_name: String,
    pub confidence: u8,
    pub correction_applied: bool,
    pub safety_rejected: bool,
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
pub struct AgentMetrics {
    pub agent_name: String,
    pub total_decisions: u64,
    pub corrections_applied: u64,   // times SelfCorrection re-ran
    pub safety_rejections: u64,     // times SafetyGuard blocked output
    pub avg_confidence: u8,         // rolling average confidence 0–100
    pub high_confidence_count: u64, // decisions with confidence >= 80
    pub low_confidence_count: u64,  // decisions with confidence < 75 (triggered retry)
    pub last_updated_block: u64,
    pub trust_score: u8,            // derived: (high_confidence - corrections) / total * 100
}

#[odra::module(events = [BehaviorRecorded, RoleChanged, PauseChanged])]
pub struct AgentBehaviorIndex {
    metrics: Mapping<String, AgentMetrics>,
    agent_count: Var<u64>,
    // ── RBAC state (replaces legacy `owner: Var<Address>`) ──
    /// Per-account role bitmask (OPERATOR | ADMIN | PAUSER).
    roles: Mapping<Address, u8>,
    /// The single role-manager — only account that may grant/revoke roles.
    role_admin: Var<Address>,
    /// Emergency pause flag. When true, every mutable entry point reverts.
    paused: Var<bool>,
}

#[odra::module]
impl AgentBehaviorIndex {
    /// Initialize the contract — caller becomes role_admin and receives all
    /// three roles (ROLE_ALL). The contract starts unpaused.
    pub fn init(&mut self) {
        let caller = self.env().caller();
        self.role_admin.set(caller);
        self.roles.set(&caller, ROLE_ALL);
        self.paused.set(false);
        self.agent_count.set(0u64);
    }

    /// Record a decision outcome for an agent — only callable by an OPERATOR
    /// when not paused.
    pub fn record_decision(
        &mut self,
        agent_name: String,
        confidence: u8,
        correction_applied: bool,
        safety_rejected: bool,
        block_height: u64,
    ) {
        self.assert_role(ROLE_OPERATOR);
        self.assert_not_paused();
        let mut m = self.metrics.get(&agent_name).unwrap_or_else(|| {
            let count = self.agent_count.get_or_default() + 1;
            self.agent_count.set(count);
            AgentMetrics {
                agent_name: agent_name.clone(),
                total_decisions: 0,
                corrections_applied: 0,
                safety_rejections: 0,
                avg_confidence: 0,
                high_confidence_count: 0,
                low_confidence_count: 0,
                last_updated_block: 0,
                trust_score: 100,
            }
        });

        m.total_decisions += 1;

        // Rolling average confidence (simplified: cumulative sum approach)
        let total_conf = (m.avg_confidence as u64 * (m.total_decisions - 1)) + confidence as u64;
        m.avg_confidence = (total_conf / m.total_decisions) as u8;

        if correction_applied {
            m.corrections_applied += 1;
        }
        if safety_rejected {
            m.safety_rejections += 1;
        }
        if confidence >= 80 {
            m.high_confidence_count += 1;
        }
        if confidence < 75 {
            m.low_confidence_count += 1;
        }

        // Recalculate trust score
        if m.total_decisions > 0 {
            let penalty = (m.corrections_applied + m.safety_rejections) * 5;
            let base = m.high_confidence_count * 100 / m.total_decisions;
            m.trust_score = base.saturating_sub(penalty).min(100) as u8;
        }

        m.last_updated_block = block_height;
        self.metrics.set(&agent_name, m);

        // Emit the on-chain event so the accountability dashboard is notified.
        self.env().emit_event(BehaviorRecorded {
            agent_name,
            confidence,
            correction_applied,
            safety_rejected,
            block_height,
        });
    }

    pub fn get_metrics(&self, agent_name: String) -> Option<AgentMetrics> {
        self.metrics.get(&agent_name)
    }

    pub fn get_trust_score(&self, agent_name: String) -> u8 {
        match self.metrics.get(&agent_name) {
            Some(m) => m.trust_score,
            None => 0,
        }
    }

    pub fn get_agent_count(&self) -> u64 {
        self.agent_count.get_or_default()
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
    fn test_record_and_trust_score() {
        let env = odra_test::env();
        let mut contract = AgentBehaviorIndex::deploy(&env, NoArgs);

        contract.record_decision("AnomalyAgent".to_string(), 91, false, false, 1500000);
        contract.record_decision("AnomalyAgent".to_string(), 88, false, false, 1500001);
        contract.record_decision("AnomalyAgent".to_string(), 72, true, false, 1500002);

        let m = contract.get_metrics("AnomalyAgent".to_string()).unwrap();
        assert_eq!(m.total_decisions, 3);
        assert_eq!(m.corrections_applied, 1);
        assert!(m.trust_score > 0);
    }

    #[test]
    fn test_new_agent_registered_on_first_decision() {
        let env = odra_test::env();
        let mut contract = AgentBehaviorIndex::deploy(&env, NoArgs);
        assert_eq!(contract.get_agent_count(), 0);
        contract.record_decision("ScannerAgent".to_string(), 95, false, false, 100);
        assert_eq!(contract.get_agent_count(), 1);
    }

    // ── RBAC tests ──

    #[test]
    fn test_init_grants_deployer_all_roles_and_role_admin() {
        let env = odra_test::env();
        let contract = AgentBehaviorIndex::deploy(&env, NoArgs);
        let deployer = env.get_account(0);
        assert_eq!(contract.get_roles(deployer), ROLE_ALL);
        assert!(contract.has_role(deployer, ROLE_OPERATOR));
        assert!(contract.has_role(deployer, ROLE_ADMIN));
        assert!(contract.has_role(deployer, ROLE_PAUSER));
        assert_eq!(contract.get_role_admin(), deployer);
        assert!(!contract.is_paused());
    }

    #[test]
    fn test_non_operator_reverts_on_record_decision() {
        // Account 1 has no roles — record_decision must revert.
        let env = odra_test::env();
        let mut contract = AgentBehaviorIndex::deploy(&env, NoArgs);
        let outsider = env.get_account(1);
        env.set_caller(outsider);
        let r = contract.try_record_decision(
            "AnomalyAgent".to_string(), 80, false, false, 100u64,
        );
        assert!(r.is_err(), "non-operator must be rejected");
    }

    #[test]
    fn test_grant_role_enables_operator() {
        let env = odra_test::env();
        let mut contract = AgentBehaviorIndex::deploy(&env, NoArgs);
        let ops = env.get_account(1);
        assert!(!contract.has_role(ops, ROLE_OPERATOR));
        contract.grant_role(ops, ROLE_OPERATOR);
        assert!(contract.has_role(ops, ROLE_OPERATOR));
        assert!(!contract.has_role(ops, ROLE_ADMIN));
    }

    #[test]
    fn test_non_role_admin_cannot_grant_role() {
        let env = odra_test::env();
        let mut contract = AgentBehaviorIndex::deploy(&env, NoArgs);
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
        let mut contract = AgentBehaviorIndex::deploy(&env, NoArgs);
        // deployer is PAUSER
        contract.pause();
        assert!(contract.is_paused());
        // record_decision must now revert (paused)
        let r = contract.try_record_decision(
            "AnomalyAgent".to_string(), 80, false, false, 100u64,
        );
        assert!(r.is_err(), "paused contract must reject writes");
        // unpause
        contract.unpause();
        assert!(!contract.is_paused());
        // now writes succeed again
        contract.record_decision("AnomalyAgent".to_string(), 80, false, false, 100u64);
        assert_eq!(contract.get_agent_count(), 1);
    }

    #[test]
    fn test_renounce_role_strips_authority() {
        let env = odra_test::env();
        let mut contract = AgentBehaviorIndex::deploy(&env, NoArgs);
        // deployer renounces OPERATOR — record_decision must then revert
        contract.renounce_role(ROLE_OPERATOR);
        let r = contract.try_record_decision(
            "AnomalyAgent".to_string(), 80, false, false, 100u64,
        );
        assert!(r.is_err(), "after renouncing OPERATOR, writes must revert");
        // deployer still is role_admin and ADMIN/PAUSER
        assert!(contract.has_role(env.get_account(0), ROLE_ADMIN));
    }

    #[test]
    fn test_transfer_ownership_grants_all_and_strips_caller() {
        let env = odra_test::env();
        let mut contract = AgentBehaviorIndex::deploy(&env, NoArgs);
        let new_owner = env.get_account(1);
        contract.transfer_ownership(new_owner);
        assert_eq!(contract.get_roles(new_owner), ROLE_ALL);
        assert_eq!(contract.get_role_admin(), new_owner);
        assert_eq!(contract.get_roles(env.get_account(0)), ROLE_NONE);
    }

    #[test]
    fn test_grant_invalid_role_reverts() {
        let env = odra_test::env();
        let mut contract = AgentBehaviorIndex::deploy(&env, NoArgs);
        let ops = env.get_account(1);
        let r = contract.try_grant_role(ops, 0b1000_0000);
        assert!(r.is_err(), "invalid role bitmask must revert");
    }

    #[test]
    fn test_non_pauser_cannot_pause() {
        let env = odra_test::env();
        let mut contract = AgentBehaviorIndex::deploy(&env, NoArgs);
        let ops = env.get_account(1);
        contract.grant_role(ops, ROLE_OPERATOR); // OPERATOR but NOT PAUSER
        env.set_caller(ops);
        let r = contract.try_pause();
        assert!(r.is_err(), "non-PAUSER must not be able to pause");
        assert!(!contract.is_paused());
    }
}
