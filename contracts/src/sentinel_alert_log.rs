
/// SentinelAlertLog — Timestamped on-chain alert history per address
///
/// Every alert pushed to a subscriber is logged here immutably.
/// Compliance-grade: any protocol can prove "we received a CRITICAL alert
/// at block X from VaultWatch" 

use odra::prelude::*;

#[odra::odra_type]
pub struct AlertRecord {
    pub log_id: u64,
    pub subscriber_address: String,
    pub finding_id: u64,
    pub severity: String,
    pub risk_type: String,
    pub block_height: u64,
    pub timestamp: u64,
    pub delivered: bool,
}

#[odra::module]
pub struct SentinelAlertLog {
    logs: Mapping<u64, AlertRecord>,
    log_count: Var<u64>,
    // address → list of log IDs (stored as comma-separated string for simplicity)
    address_logs: Mapping<String, String>,
    owner: Var<Address>,
}

#[odra::module]
impl SentinelAlertLog {
    pub fn init(&mut self) {
        self.owner.set(self.env().caller());
        self.log_count.set(0u64);
    }

    /// Log a delivered alert — only VaultWatch agent wallet
    pub fn log_alert(
        &mut self,
        subscriber_address: String,
        finding_id: u64,
        severity: String,
        risk_type: String,
        block_height: u64,
        timestamp: u64,
        delivered: bool,
    ) -> u64 {
        self.assert_owner();
        let log_id = self.log_count.get_or_default() + 1;
        let record = AlertRecord {
            log_id,
            subscriber_address: subscriber_address.clone(),
            finding_id,
            severity,
            risk_type,
            block_height,
            timestamp,
            delivered,
        };
        self.logs.set(&log_id, record);
        self.log_count.set(log_id);

        // Append to address log index
        let existing = self.address_logs.get(&subscriber_address).unwrap_or_default();
        let updated = if existing.is_empty() {
            format!("{}", log_id)
        } else {
            format!("{},{}", existing, log_id)
        };
        self.address_logs.set(&subscriber_address, updated);

        log_id
    }

    pub fn get_log(&self, log_id: u64) -> AlertRecord {
        self.logs.get(&log_id).unwrap_or_revert(self)
    }

    pub fn get_address_log_ids(&self, address: String) -> String {
        self.address_logs.get(&address).unwrap_or_default()
    }

    pub fn get_total_count(&self) -> u64 {
        self.log_count.get_or_default()
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
    fn test_log_and_retrieve_alert() {
        let env = odra_test::env();
        let mut contract = SentinelAlertLogHostRef::deploy(&env, NoArgs);

        let id = contract.log_alert(
            "casper1sub".to_string(), 1, "CRITICAL".to_string(),
            "whale_dump".to_string(), 1500000, 1750000000, true
        );
        assert_eq!(id, 1);
        let log = contract.get_log(1);
        assert_eq!(log.severity, "CRITICAL");
        assert!(log.delivered);
    }

    #[test]
    fn test_address_log_index() {
        let env = odra_test::env();
        let mut contract = SentinelAlertLogHostRef::deploy(&env, NoArgs);

        contract.log_alert("casper1sub".to_string(), 1, "CRITICAL".to_string(), "whale_dump".to_string(), 100, 200, true);
        contract.log_alert("casper1sub".to_string(), 2, "HIGH".to_string(), "depeg".to_string(), 101, 201, true);

        let ids = contract.get_address_log_ids("casper1sub".to_string());
        assert_eq!(ids, "1,2");
    }
}
