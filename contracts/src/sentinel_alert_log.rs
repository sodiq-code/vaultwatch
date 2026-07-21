
/// SentinelAlertLog — Timestamped on-chain alert history per address
///
/// Every alert pushed to a subscriber is logged here immutably.
/// Compliance-grade: any protocol can prove "we received a CRITICAL alert
/// at block X from VaultWatch"

use odra::prelude::*;

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

#[odra::module(events = [AlertLogged])]
pub struct SentinelAlertLog {
    logs: Mapping<u64, AlertRecord>,
    log_count: Var<u64>,
    // address → list of log IDs (typed Vec<u64>, capped at MAX_ADDRESS_LOG_IDS).
    // Previously a comma-separated String, which was unbounded, required parsing
    // off-chain, and could blow up global-state URef values for noisy accounts.
    // A bounded Vec<u64> keeps per-address history deterministic and cheap.
    address_logs: Mapping<Address, Vec<u64>>,
    owner: Var<Address>,
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
    pub fn init(&mut self) {
        self.owner.set(self.env().caller());
        self.log_count.set(0u64);
    }

    /// Log a delivered alert — only VaultWatch agent wallet
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
        self.assert_owner();
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
}
