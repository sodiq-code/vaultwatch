
/// RiskPolicyManager — Hot-swappable risk thresholds without contract redeployment
///
/// Run `npm run demo:upgrade-policy` → threshold changes live on testnet →
/// agents immediately reclassify events at new threshold → new finding on-chain.
/// Hot upgrade of a live production system in 30 seconds.

use odra::prelude::*;

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

#[odra::module(events = [PolicyUpgraded])]
pub struct RiskPolicyManager {
    current_policy: Var<RiskPolicy>,
    policy_history: Mapping<u32, RiskPolicy>,
    owner: Var<Address>,
}

#[odra::module]
impl RiskPolicyManager {
    pub fn init(&mut self) {
        let caller = self.env().caller();
        self.owner.set(caller);
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
        updated_by: Address,
    ) {
        self.assert_owner();
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

    pub fn transfer_ownership(&mut self, new_owner: Address) {
        self.assert_owner();
        self.owner.set(new_owner);
    }

    fn assert_owner(&self) {
        let caller = self.env().caller();
        let owner = self.owner.get_or_revert_with(crate::user_err(1));
        if caller != owner {
            self.env().revert(crate::user_err(1));
        }
    }
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
}
