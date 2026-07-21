/// SentinelAlertLog — Timestamped on-chain alert history per address
///
/// Every alert pushed to a subscriber is logged here immutably.
/// Compliance-grade: any protocol can prove "we received a CRITICAL alert
/// at block X from VaultWatch"
///
/// FIX #13: address_logs changed from comma-separated String to Vec<u64>
///          capped at 256 entries per address.
/// FIX #11: Added Odra events (AlertLogged)

use odra::prelude::*;

// ─── Events ────────────────────────────────────────────────────────────────

#[odra::event]
pub struct AlertLogged {
    pub log_id: u64,
    pub subscriber_address: String,
    pub finding_id: u64,
    pub severity: String,
    pub block_height: u64,
}

// ─── Data types ────────────────────────────────────────────────────────────

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

/// Max log IDs stored per address (prevents unbounded storage)
const MAX_LOGS_PER_ADDRESS: usize = 256;

// ─── Contract ──────────────────────────────────────────────────────────────

#[odra::module]
pub struct SentinelAlertLog {
    logs: Mapping<u64, AlertRecord>,
    log_count: Var<u64>,
    // FIX #13: was Mapping<String, String> (comma-separated) — now Vec<u64>
    address_logs: Mapping<String, Vec<u64>>,
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

        let log_id = self.log_count.get().unwrap_or(0u64);

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
        self.log_count.set(log_id + 1);

        // FIX #13: append to Vec<u64>, capped at MAX_LOGS_PER_ADDRESS
        let mut ids = self
            .address_logs
            .get(&subscriber_address)
            .unwrap_or_default();
        if ids.len() < MAX_LOGS_PER_ADDRESS {
            ids.push(log_id);
        } else {
            // Evict oldest (shift left) — sliding window
            ids.remove(0);
            ids.push(log_id);
        }
        self.address_logs.set(&subscriber_address, ids);

        // FIX #11: emit event
        self.env().emit_event(AlertLogged {
            log_id,
            subscriber_address,
            finding_id,
            severity,
            block_height,
        });

        log_id
    }

    /// Get all log IDs for a subscriber address
    pub fn get_address_logs(&self, subscriber_address: String) -> Vec<u64> {
        self.address_logs
            .get(&subscriber_address)
            .unwrap_or_default()
    }

    /// Get a specific log record by ID
    pub fn get_log(&self, log_id: u64) -> Option<AlertRecord> {
        self.logs.get(&log_id)
    }

    /// Total number of logs
    pub fn log_count(&self) -> u64 {
        self.log_count.get().unwrap_or(0u64)
    }

    fn assert_owner(&self) {
        let caller = self.env().caller();
        let owner = self.owner.get().unwrap_or_revert_with(self.env(), Error::Unauthorized);
        if caller != owner {
            self.env().revert(Error::Unauthorized);
        }
    }
}

#[odra::odra_error]
pub enum Error {
    Unauthorized = 1,
    LogNotFound = 2,
}
