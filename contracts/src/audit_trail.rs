
/// AuditTrail — Immutable on-chain log of every VaultWatch finding
///
/// Every risk finding that passes the full agent pipeline (SelfCorrection +
/// SafetyGuard) is written here. Immutable. Timestamped. Publicly queryable.
/// Any Casper DeFi protocol can verify: "was there a CRITICAL alert at block X?"

use odra::prelude::*;

/// A single immutable finding record
#[odra::odra_type]
pub struct Finding {
    pub id: u64,
    pub address: String,
    pub risk_type: String,        // rug_pull | whale_dump | depeg | wash_trade | collateral_drop | flash_loan | anomalous_flow
    pub severity: String,         // CRITICAL | HIGH | MEDIUM | LOW
    pub confidence: u8,           // 0–100 (percentage * 100 from float 0.0–1.0)
    pub description: String,
    pub rwa_enriched: bool,
    pub agent_model: String,
    pub block_height: u64,
    pub timestamp: u64,
    pub tx_hash: String,
}

#[odra::module]
pub struct AuditTrail {
    findings: Mapping<u64, Finding>,
    finding_count: Var<u64>,
    owner: Var<Address>,
}

#[odra::module]
impl AuditTrail {
    /// Initialize the contract — caller becomes owner
    pub fn init(&mut self) {
        self.owner.set(self.env().caller());
        self.finding_count.set(0u64);
    }

    /// Write a new finding — only callable by the authorized VaultWatch agent wallet
    pub fn record_finding(
        &mut self,
        address: String,
        risk_type: String,
        severity: String,
        confidence: u8,
        description: String,
        rwa_enriched: bool,
        agent_model: String,
        block_height: u64,
        timestamp: u64,
    ) -> u64 {
        self.assert_owner();
        let id = self.finding_count.get_or_default() + 1;
        let finding = Finding {
            id,
            address,
            risk_type,
            severity,
            confidence,
            description,
            rwa_enriched,
            agent_model,
            block_height,
            timestamp,
            tx_hash: String::new(), // filled by client after deploy
        };
        self.findings.set(&id, finding);
        self.finding_count.set(id);
        id
    }

    /// Get a finding by ID
    pub fn get_finding(&self, id: u64) -> Finding {
        self.findings.get(&id).unwrap_or_revert(self)
    }

    /// Get total finding count
    pub fn get_count(&self) -> u64 {
        self.finding_count.get_or_default()
    }

    /// Transfer ownership (for agent wallet rotation)
    pub fn transfer_ownership(&mut self, new_owner: Address) {
        self.assert_owner();
        self.owner.set(new_owner);
    }

    fn assert_owner(&self) {
        let caller = self.env().caller();
        let owner = self.owner.get_or_revert_with(ExecutionError::User(1));
        if caller != owner {
            self.env().revert(ExecutionError::User(1));
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use odra::host::{Deployer, HostRef};

    #[test]
    fn test_record_and_retrieve_finding() {
        let env = odra_test::env();
        let mut contract = AuditTrailHostRef::deploy(&env, NoArgs);

        let id = contract.record_finding(
            "casper1abc".to_string(),
            "whale_dump".to_string(),
            "CRITICAL".to_string(),
            91,
            "Large whale dump detected: 2.4M CSPR moved in 3 blocks".to_string(),
            false,
            "llama-3.3-70b-versatile".to_string(),
            1500000u64,
            1750000000u64,
        );
        assert_eq!(id, 1);

        let f = contract.get_finding(1);
        assert_eq!(f.severity, "CRITICAL");
        assert_eq!(f.risk_type, "whale_dump");
        assert_eq!(f.confidence, 91);
    }

    #[test]
    fn test_count_increments() {
        let env = odra_test::env();
        let mut contract = AuditTrailHostRef::deploy(&env, NoArgs);
        assert_eq!(contract.get_count(), 0);
        contract.record_finding("addr".to_string(), "depeg".to_string(), "HIGH".to_string(), 80, "desc".to_string(), true, "llama-3.1-8b".to_string(), 100u64, 200u64);
        assert_eq!(contract.get_count(), 1);
        contract.record_finding("addr2".to_string(), "rug_pull".to_string(), "CRITICAL".to_string(), 95, "desc2".to_string(), false, "llama-3.3-70b".to_string(), 101u64, 201u64);
        assert_eq!(contract.get_count(), 2);
    }
}
