
/// RiskOracle — Live risk scores queryable by any Casper DeFi protocol
///
/// Any protocol on Casper can call get_risk_score(address) to retrieve the
/// current VaultWatch risk assessment. This is the integration hook — one
/// contract call, live risk intelligence, no account required.
///
/// FIX #11: Added Odra events (ScoreUpdated)

use odra::prelude::*;

// ─── Events ────────────────────────────────────────────────────────────────

#[odra::event]
pub struct ScoreUpdated {
    pub address: String,
    pub old_score: u8,
    pub new_score: u8,
    pub risk_type: String,
}

// ─── Data types ────────────────────────────────────────────────────────────

#[odra::odra_type]
pub struct RiskScore {
    pub address: String,
    pub score: u8,           // 0–100
    pub risk_type: String,
    pub confidence: u8,      // 0–100
    pub last_updated: u64,   // block height
    pub finding_id: u64,     // reference back to AuditTrail
}

// ─── Contract ──────────────────────────────────────────────────────────────

#[odra::module]
pub struct RiskOracle {
    scores: Mapping<String, RiskScore>,
    owner: Var<Address>,
}

#[odra::module]
impl RiskOracle {
    pub fn init(&mut self) {
        self.owner.set(self.env().caller());
    }

    /// Update risk score for an address — only VaultWatch agent wallet
    pub fn update_score(
        &mut self,
        address: String,
        score: u8,
        risk_type: String,
        confidence: u8,
        block_height: u64,
        finding_id: u64,
    ) {
        self.assert_owner();

        // FIX #11: capture old_score for event emission
        let old_score = match self.scores.get(&address) {
            Some(existing) => existing.score,
            None => 0u8,
        };

        let record = RiskScore {
            address: address.clone(),
            score,
            risk_type: risk_type.clone(),
            confidence,
            last_updated: block_height,
            finding_id,
        };
        self.scores.set(&address, record);

        // FIX #11: emit ScoreUpdated event
        self.env().emit_event(ScoreUpdated {
            address,
            old_score,
            new_score: score,
            risk_type,
        });
    }

    /// Query risk score for any address — public, no auth required
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
    fn test_update_and_query_score() {
        let env = odra_test::env();
        let mut contract = RiskOracleHostRef::deploy(&env, NoArgs);

        contract.update_score("casper1xyz".to_string(), 87, "whale_concentration".to_string(), 92, 1500000, 1);

        let score = contract.get_risk_score("casper1xyz".to_string()).unwrap();
        assert_eq!(score.score, 87);
        assert_eq!(score.risk_type, "whale_concentration");
        assert_eq!(score.confidence, 92);
    }

    #[test]
    fn test_is_high_risk() {
        let env = odra_test::env();
        let mut contract = RiskOracleHostRef::deploy(&env, NoArgs);
        contract.update_score("casper1abc".to_string(), 75, "depeg".to_string(), 88, 1500001, 2);
        assert!(contract.is_high_risk("casper1abc".to_string(), 70));
        assert!(!contract.is_high_risk("casper1abc".to_string(), 80));
    }

    #[test]
    fn test_unknown_address_returns_none() {
        let env = odra_test::env();
        let contract = RiskOracleHostRef::deploy(&env, NoArgs);
        assert!(contract.get_risk_score("casper1unknown".to_string()).is_none());
    }
}
