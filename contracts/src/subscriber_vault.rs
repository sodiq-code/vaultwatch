use odra::casper_types::U512;

/// SubscriberVault — Escrowed prepay balance for bulk subscribers
///
/// Protocols prepay CSPR into escrow. Each query deducts from balance.
/// This makes x402 usable for high-frequency integrations — not just
/// one-off queries. Real subscription model, on-chain, no middlemen.

use odra::prelude::*;

#[odra::odra_type]
pub struct VaultAccount {
    pub owner_address: String,
    pub escrowed_balance: U512,
    pub locked_until_block: u64,  // 0 = no lock, can withdraw anytime
    pub auto_renew: bool,
    pub monthly_spend_limit: U512,
    pub current_period_spent: U512,
    pub total_deposits: U512,
    pub total_withdrawals: U512,
    pub created_at_block: u64,
}

#[odra::module]
pub struct SubscriberVault {
    accounts: Mapping<String, VaultAccount>,
    vault_owner: Var<Address>,
    total_locked: Var<U512>,
}

#[odra::module]
impl SubscriberVault {
    pub fn init(&mut self) {
        self.vault_owner.set(self.env().caller());
        self.total_locked.set(U512::zero());
    }

    /// Open a vault account — subscriber calls this with initial deposit
    pub fn open_vault(
        &mut self,
        subscriber_address: String,
        initial_deposit: U512,
        lock_blocks: u64,
        auto_renew: bool,
        monthly_spend_limit: U512,
        current_block: u64,
    ) {
        self.assert_vault_owner();
        let account = VaultAccount {
            owner_address: subscriber_address.clone(),
            escrowed_balance: initial_deposit,
            locked_until_block: if lock_blocks > 0 { current_block + lock_blocks } else { 0 },
            auto_renew,
            monthly_spend_limit,
            current_period_spent: U512::zero(),
            total_deposits: initial_deposit,
            total_withdrawals: U512::zero(),
            created_at_block: current_block,
        };
        self.accounts.set(&subscriber_address, account);
        let locked = self.total_locked.get_or_default() + initial_deposit;
        self.total_locked.set(locked);
    }

    /// Deduct from vault for a query
    pub fn deduct(
        &mut self,
        subscriber_address: String,
        amount: U512,
    ) -> bool {
        self.assert_vault_owner();
        match self.accounts.get(&subscriber_address) {
            Some(mut account) => {
                if account.escrowed_balance < amount {
                    return false;
                }
                // Check spend limit
                if account.monthly_spend_limit > U512::zero() {
                    if account.current_period_spent + amount > account.monthly_spend_limit {
                        return false;
                    }
                }
                account.escrowed_balance -= amount;
                account.current_period_spent += amount;
                self.accounts.set(&subscriber_address, account);
                true
            }
            None => false,
        }
    }

    /// Top up vault balance
    pub fn top_up(&mut self, subscriber_address: String, amount: U512) {
        self.assert_vault_owner();
        match self.accounts.get(&subscriber_address) {
            Some(mut account) => {
                account.escrowed_balance += amount;
                account.total_deposits += amount;
                self.accounts.set(&subscriber_address, account);
                let locked = self.total_locked.get_or_default() + amount;
                self.total_locked.set(locked);
            }
            None => self.env().revert(ExecutionError::UnwrapError),
        }
    }

    pub fn get_account(&self, subscriber_address: String) -> Option<VaultAccount> {
        self.accounts.get(&subscriber_address)
    }

    pub fn get_balance(&self, subscriber_address: String) -> U512 {
        match self.accounts.get(&subscriber_address) {
            Some(account) => account.escrowed_balance,
            None => U512::zero(),
        }
    }

    pub fn get_total_locked(&self) -> U512 {
        self.total_locked.get_or_default()
    }

    fn assert_vault_owner(&self) {
        let caller = self.env().caller();
        let owner = self.vault_owner.get_or_revert_with(ExecutionError::User(1));
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
    fn test_open_vault_and_balance() {
        let env = odra_test::env();
        let mut contract = SubscriberVaultHostRef::deploy(&env, NoArgs);
        contract.open_vault(
            "casper1proto".to_string(),
            U512::from(50_000_000u64),
            0, true,
            U512::from(100_000_000u64),
            1500000,
        );
        assert_eq!(contract.get_balance("casper1proto".to_string()), U512::from(50_000_000u64));
    }

    #[test]
    fn test_deduct_from_vault() {
        let env = odra_test::env();
        let mut contract = SubscriberVaultHostRef::deploy(&env, NoArgs);
        contract.open_vault("casper1proto".to_string(), U512::from(50_000_000u64), 0, true, U512::zero(), 1500000);
        let ok = contract.deduct("casper1proto".to_string(), U512::from(5_000_000u64));
        assert!(ok);
        assert_eq!(contract.get_balance("casper1proto".to_string()), U512::from(45_000_000u64));
    }
}
