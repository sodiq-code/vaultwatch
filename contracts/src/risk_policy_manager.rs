/// RiskPolicyManager — Hot-swappable risk thresholds without contract redeployment
///
/// THE KILLSHOT DEMO FEATURE.
/// Run `npm run demo:upgrade-policy` → threshold changes live on testnet →
/// agents immediately reclassify events at new threshold → new finding on-chain.
/// Hot upgrade of a live production system in 30 seconds.
/// No other submission can demonstrate this.

use odra::prelude::*;
use odra::{Address, Mapping, UnwrapOrRevert, Var};

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
    pub updated_by: String,
}

#[odra::module]
pub struct RiskPolicyManager {
    current_policy: Var<RiskPolicy>,
    policy_history: Mapping<u32, RiskPolicy>,
    owner: Var<Address>,
}

#[odra::module]
impl RiskPolicyManager {
    pub fn init(&mut self) {
        self.owner.set(self.env().caller());
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
            updated_by: "genesis".to_string(),
        };
        self.current_policy.set(default_policy.clone());
        self.policy_history.set(&1u32, default_policy);
    }

    /// Hot-swap policy — agents read this every cycle, no restart needed
    pub fn upgrade_policy(
        &mut self,
        min_confidence_threshold: u8,
        critical_score_threshold: u8,
        high_score_threshold: u8,
        medium_score_threshold: u8,
        max_retry_count: u8,
        safety_rejection_threshold: u8,
        block_height: u64,
        updated_by: String,
    ) {
        self.assert_owner();
        let current_version = self.current_policy
            .get_or_revert(self.env())
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
        self.policy_history.set(&new_version, new_policy);
    }

    /// Get active policy — agents call this every decision cycle
    pub fn get_current_policy(&self) -> RiskPolicy {
        self.current_policy.get_or_revert(self.env())
    }

    /// Get a historical policy version
    pub fn get_policy_version(&self, version: u32) -> Option<RiskPolicy> {
        self.policy_history.get(&version)
    }

    pub fn get_current_version(&self) -> u32 {
        self.current_policy.get_or_revert(self.env()).version
    }

    pub fn transfer_ownership(&mut self, new_owner: Address) {
        self.assert_owner();
        self.owner.set(new_owner);
    }

    fn assert_owner(&self) {
        let caller = self.env().caller();
        let owner = self.owner.get_or_revert(self.env());
        if caller != owner {
            self.env().revert(odra::ExecutionError::UnauthorizedInvoker);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use odra::host::{Deployer, HostRef};

    #[test]
    fn test_default_policy_on_init() {
        let env = odra_test::env();
        let contract = RiskPolicyManagerHostRef::deploy(&env, NoArgs);
        let policy = contract.get_current_policy();
        assert_eq!(policy.version, 1);
        assert_eq!(policy.min_confidence_threshold, 75);
        assert_eq!(policy.critical_score_threshold, 80);
    }

    #[test]
    fn test_hot_upgrade_policy() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManagerHostRef::deploy(&env, NoArgs);

        contract.upgrade_policy(60, 70, 50, 30, 3, 85, 1500000, "admin".to_string());

        let policy = contract.get_current_policy();
        assert_eq!(policy.version, 2);
        assert_eq!(policy.min_confidence_threshold, 60);
        assert_eq!(policy.critical_score_threshold, 70);
        assert_eq!(policy.updated_by, "admin");
    }

    #[test]
    fn test_policy_history_preserved() {
        let env = odra_test::env();
        let mut contract = RiskPolicyManagerHostRef::deploy(&env, NoArgs);
        contract.upgrade_policy(60, 70, 50, 30, 3, 85, 1500000, "admin".to_string());

        let v1 = contract.get_policy_version(1).unwrap();
        assert_eq!(v1.min_confidence_threshold, 75);

        let v2 = contract.get_policy_version(2).unwrap();
        assert_eq!(v2.min_confidence_threshold, 60);
    }
}
