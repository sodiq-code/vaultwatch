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
//!    `policy_history`, `owner`). Odra stores all module state in a single
//!    `state` dictionary keyed by field index; preserving the field order
//!    means v2 reads v1's state via the identical dictionary keys — no
//!    migration code required.
//! 2. **All v1 entry points preserved** so the upgraded package remains a
//!    functional superset — v1 entry points work whether pinned to version 1
//!    or invoked on the latest (v2) version.
//! 3. **One new entry point** `get_policy_with_reasoning` — the v2-only
//!    capability that proves the upgrade added functionality.
//! 4. **`upgrade(&mut self)` hook** — Odra invokes this after
//!    `add_contract_version()`. It is a no-op here because v2 preserves v1's
//!    field layout; no state migration is needed.
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
// Reuse v1's RiskPolicy AND PolicyUpgraded event so the serialized layout is
// byte-identical (state shared) and the event schema is identical across v1/v2.
// `crate::` prefix required (Rust 2018 edition); the odra_type/event structs are
// not gated by odra_module, so they remain available when building v2 only.
pub use crate::risk_policy_manager::{PolicyUpgraded, RiskPolicy};

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

#[odra::module(events = [PolicyUpgraded])]
pub struct RiskPolicyManagerV2 {
    // --- SAME fields, SAME order as v1 (shared `state` dictionary keys) ---
    current_policy: Var<RiskPolicy>,
    policy_history: Mapping<u32, RiskPolicy>,
    owner: Var<Address>,
}

#[odra::module]
impl RiskPolicyManagerV2 {
    /// Constructor — only invoked on a *fresh* install (never on upgrade).
    /// Mirrors v1's `init` so a standalone v2 deploy is self-consistent.
    pub fn init(&mut self) {
        let caller = self.env().caller();
        self.owner.set(caller);
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
    /// dictionary already holds `current_policy`, `policy_history`, and `owner`
    /// under the same keys v1 wrote them. Nothing to migrate.
    pub fn upgrade(&mut self) {
        // Intentional no-op (see module docs).
    }

    /// Hot-swap policy — agents read this every cycle (identical to v1).
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

    /// Transfer ownership (identical to v1).
    pub fn transfer_ownership(&mut self, new_owner: Address) {
        self.assert_owner();
        self.owner.set(new_owner);
    }

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

    fn assert_owner(&self) {
        let caller = self.env().caller();
        let owner = self.owner.get_or_revert_with(crate::user_err(1));
        if caller != owner {
            self.env().revert(crate::user_err(1));
        }
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
}
