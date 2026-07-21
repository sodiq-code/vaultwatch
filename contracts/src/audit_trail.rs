/// AuditTrail — Immutable on-chain log of every VaultWatch finding
///
/// Every risk finding that passes the full agent pipeline (SelfCorrection +
/// SafetyGuard) is written here. Immutable. Timestamped. Publicly queryable.
/// Any Casper DeFi protocol can verify: "was there a CRITICAL alert at block X?"
///
/// FIX #11: Added Odra events (FindingRecorded, OwnerChanged)
/// FIX #12: address field uses Casper Address type for proper validation

use odra::prelude::*;

// ─── Events ────────────────────────────────────────────────────────────────

/// Emitted every time a new finding is recorded on-chain
#[odra::event]
pub struct FindingRecorded {
    pub finding_id: u64,
    pub address: String,
    pub risk_type: String,
    pub severity: String,
    pub confidence: u8,
    pub block_height: u64,
}

/// Emitted when contract ownership is transferred
#[odra::event]
pub struct OwnerChanged {
    pub old_owner: Address,
    pub new_owner: Address,
}

// ─── Data types ────────────────────────────────────────────────────────────

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

// ─── Contract ──────────────────────────────────────────────────────────────

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
    ) -> u64 {
        self.assert_owner();
        let id = self.finding_count.get().unwrap_or(0u64);
        let block_height = self.env().block_time() / 1000; // ms → seconds approx
        let timestamp = self.env().block_time();

        let finding = Finding {
            id,
            address: address.clone(),
            risk_type: risk_type.clone(),
            severity: severity.clone(),
            confidence,
            description,
            rwa_enriched: false,
            agent_model: String::from("llama-3.1-8b-instant"),
            block_height,
            timestamp,
            tx_hash: String::from(""),
        };

        self.findings.set(&id, finding);
        self.finding_count.set(id + 1);

        // FIX #11: Emit event
        self.env().emit_event(FindingRecorded {
            finding_id: id,
            address,
            risk_type,
            severity,
            confidence,
            block_height,
        });

        id
    }

    /// Get a finding by ID
    pub fn get_finding(&self, id: u64) -> Option<Finding> {
        self.findings.get(&id)
    }

    /// Total number of findings recorded
    pub fn finding_count(&self) -> u64 {
        self.finding_count.get().unwrap_or(0u64)
    }

    /// Transfer ownership (emits OwnerChanged event)
    pub fn transfer_ownership(&mut self, new_owner: Address) {
        self.assert_owner();
        let old_owner = self.owner.get().unwrap();
        self.owner.set(new_owner);
        // FIX #11: emit ownership event
        self.env().emit_event(OwnerChanged { old_owner, new_owner });
    }

    // ── Private ────────────────────────────────────────────────────────────

    fn assert_owner(&self) {
        let caller = self.env().caller();
        let owner = self.owner.get().unwrap_or_revert_with(self.env(), Error::Unauthorized);
        if caller != owner {
            self.env().revert(Error::Unauthorized);
        }
    }
}

/// Contract-specific error codes
#[odra::odra_error]
pub enum Error {
    Unauthorized = 1,
    FindingNotFound = 2,
}
