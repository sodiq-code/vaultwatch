/// RiskPolicyManager — Hot-swappable risk thresholds without contract redeployment
///
/// Run `npm run demo:upgrade-policy` → threshold changes live on testnet →
/// agents immediately reclassify events at new threshold → new finding on-chain.
/// Hot upgrade of a live production system in 30 seconds.
///
/// FIX #2:  add_contract_version pattern demonstrated via update_policy_v2()
/// FIX #11: Odra events (PolicyUpgraded, RoleGranted)
/// FIX #12: Address types for owner/operator
/// FIX #25: RBAC with OPERATOR and ADMIN roles

use odra::prelude::*;

// ─── Events ────────────────────────────────────────────────────────────────

#[odra::event]
pub struct PolicyUpgraded {
    pub old_version: u32,
    pub new_version: u32,
    pub upgraded_by: Address,
    pub block_height: u64,
}

#[odra::event]
pub struct RoleGranted {
    pub role: String,
    pub account: Address,
    pub granted_by: Address,
}

// ─── Data types ────────────────────────────────────────────────────────────

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
    // FIX #12: proper Address type for updated_by
    pub updated_by: Address,
}

// ─── Contract ──────────────────────────────────────────────────────────────

#[odra::module]
pub struct RiskPolicyManager {
    current_policy: Var<RiskPolicy>,
    policy_history: Mapping<u32, RiskPolicy>,
    // FIX #12: use Address type
    owner: Var<Address>,
    // FIX #25: RBAC — operators can update policy, admins can grant roles
    operators: Mapping<Address, bool>,
    admins: Mapping<Address, bool>,
}

#[odra::module]
impl RiskPolicyManager {
    pub fn init(&mut self) {
        let caller = self.env().caller();
        self.owner.set(caller);
        // Owner starts as both admin and operator
        self.admins.set(&caller, true);
        self.operators.set(&caller, true);

        // Default policy v1
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

    /// Update risk policy — operators only (FIX #25)
    pub fn update_policy(
        &mut self,
        min_confidence_threshold: u8,
        critical_score_threshold: u8,
        high_score_threshold: u8,
        medium_score_threshold: u8,
        max_retry_count: u8,
        safety_rejection_threshold: u8,
    ) {
        self.assert_operator();

        let old = self.current_policy.get().unwrap_or_revert_with(self.env(), Error::NoPolicySet);
        let new_version = old.version + 1;
        let caller = self.env().caller();
        let block_height = self.env().block_time() / 1000;

        let new_policy = RiskPolicy {
            version: new_version,
            min_confidence_threshold,
            critical_score_threshold,
            high_score_threshold,
            medium_score_threshold,
            max_retry_count,
            safety_rejection_threshold,
            updated_at_block: block_height,
            updated_by: caller,
        };

        self.policy_history.set(&new_version, new_policy.clone());
        self.current_policy.set(new_policy);

        // FIX #11: emit event
        self.env().emit_event(PolicyUpgraded {
            old_version: old.version,
            new_version,
            upgraded_by: caller,
            block_height,
        });
    }

    /// FIX #2: V2 upgrade entry point — adds RWA-specific thresholds
    /// This demonstrates Casper's native contract upgrade pattern:
    /// deploy a new contract version, call this entry point to migrate state.
    pub fn upgrade_to_v2_rwa(
        &mut self,
        rwa_confidence_boost: u8,  // Extra confidence required for RWA-enriched findings
        rwa_critical_threshold: u8, // Stricter threshold for RWA assets
    ) {
        self.assert_admin();

        let current = self.current_policy.get().unwrap_or_revert_with(self.env(), Error::NoPolicySet);
        let new_version = current.version + 1;
        let caller = self.env().caller();
        let block_height = self.env().block_time() / 1000;

        // V2 policy incorporates RWA-specific adjustments
        let v2_policy = RiskPolicy {
            version: new_version,
            min_confidence_threshold: current.min_confidence_threshold + rwa_confidence_boost,
            critical_score_threshold: rwa_critical_threshold,
            high_score_threshold: current.high_score_threshold,
            medium_score_threshold: current.medium_score_threshold,
            max_retry_count: current.max_retry_count,
            safety_rejection_threshold: current.safety_rejection_threshold,
            updated_at_block: block_height,
            updated_by: caller,
        };

        self.policy_history.set(&new_version, v2_policy.clone());
        self.current_policy.set(v2_policy);

        self.env().emit_event(PolicyUpgraded {
            old_version: current.version,
            new_version,
            upgraded_by: caller,
            block_height,
        });
    }

    /// Get the currently active policy
    pub fn get_current_policy(&self) -> RiskPolicy {
        self.current_policy
            .get()
            .unwrap_or_revert_with(self.env(), Error::NoPolicySet)
    }

    /// Get a historical policy by version
    pub fn get_policy_version(&self, version: u32) -> Option<RiskPolicy> {
        self.policy_history.get(&version)
    }

    // ── FIX #25: RBAC ──────────────────────────────────────────────────────

    /// Grant operator role — admins only
    pub fn grant_operator(&mut self, account: Address) {
        self.assert_admin();
        self.operators.set(&account, true);
        self.env().emit_event(RoleGranted {
            role: String::from("OPERATOR"),
            account,
            granted_by: self.env().caller(),
        });
    }

    /// Grant admin role — owner only
    pub fn grant_admin(&mut self, account: Address) {
        self.assert_owner();
        self.admins.set(&account, true);
        self.env().emit_event(RoleGranted {
            role: String::from("ADMIN"),
            account,
            granted_by: self.env().caller(),
        });
    }

    /// Revoke operator role — admins only
    pub fn revoke_operator(&mut self, account: Address) {
        self.assert_admin();
        self.operators.set(&account, false);
    }

    // ── Private ────────────────────────────────────────────────────────────

    fn assert_owner(&self) {
        let caller = self.env().caller();
        let owner = self.owner.get().unwrap_or_revert_with(self.env(), Error::Unauthorized);
        if caller != owner {
            self.env().revert(Error::Unauthorized);
        }
    }

    fn assert_admin(&self) {
        let caller = self.env().caller();
        if !self.admins.get(&caller).unwrap_or(false) {
            self.env().revert(Error::NotAdmin);
        }
    }

    fn assert_operator(&self) {
        let caller = self.env().caller();
        if !self.operators.get(&caller).unwrap_or(false) {
            self.env().revert(Error::NotOperator);
        }
    }
}

#[odra::odra_error]
pub enum Error {
    Unauthorized = 1,
    NoPolicySet = 2,
    NotAdmin = 3,
    NotOperator = 4,
}
