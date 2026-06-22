
/// SentinelRegistry — Subscriber registry for push alerts
///
/// Protocols register their webhook endpoints here. When a CRITICAL finding
/// is confirmed, the IntelAgent reads this registry and pushes alerts to
/// every registered subscriber. On-chain subscriber management — no database.

use odra::prelude::*;

#[odra::odra_type]
pub struct Subscriber {
    pub address: String,
    pub webhook_url: String,
    pub min_severity: String,  // CRITICAL | HIGH | MEDIUM | LOW
    pub active: bool,
    pub registered_at: u64,
    pub alert_count: u64,
}

#[odra::module]
pub struct SentinelRegistry {
    subscribers: Mapping<String, Subscriber>,
    subscriber_count: Var<u64>,
    owner: Var<Address>,
}

#[odra::module]
impl SentinelRegistry {
    pub fn init(&mut self) {
        self.owner.set(self.env().caller());
        self.subscriber_count.set(0u64);
    }

    /// Register a new subscriber
    pub fn register(
        &mut self,
        address: String,
        webhook_url: String,
        min_severity: String,
        timestamp: u64,
    ) {
        let sub = Subscriber {
            address: address.clone(),
            webhook_url,
            min_severity,
            active: true,
            registered_at: timestamp,
            alert_count: 0,
        };
        self.subscribers.set(&address, sub);
        let count = self.subscriber_count.get_or_default() + 1;
        self.subscriber_count.set(count);
    }

    /// Deactivate a subscriber
    pub fn deregister(&mut self, address: String) {
        match self.subscribers.get(&address) {
            Some(mut sub) => {
                sub.active = false;
                self.subscribers.set(&address, sub);
            }
            None => self.env().revert(ExecutionError::UnwrapError),
        }
    }

    /// Increment alert count for subscriber (called by IntelAgent after push)
    pub fn increment_alert_count(&mut self, address: String) {
        self.assert_owner();
        match self.subscribers.get(&address) {
            Some(mut sub) => {
                sub.alert_count += 1;
                self.subscribers.set(&address, sub);
            }
            None => {}
        }
    }

    pub fn get_subscriber(&self, address: String) -> Option<Subscriber> {
        self.subscribers.get(&address)
    }

    pub fn is_active(&self, address: String) -> bool {
        match self.subscribers.get(&address) {
            Some(sub) => sub.active,
            None => false,
        }
    }

    pub fn get_count(&self) -> u64 {
        self.subscriber_count.get_or_default()
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
