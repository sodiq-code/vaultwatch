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

    /// Open a vault account — subscriber calls this with initial deposit.
    /// PAYABLE: the caller attaches real CSPR via `CallDef::with_amount()`.
    ///
    /// Odra's `#[odra(payable)]` attribute auto-invokes
    /// `handle_attached_value()` which transfers the attached CSPR from the
    /// caller's cargo purse into this contract's main purse
    /// (`__contract_main_purse`). The `initial_deposit` argument MUST match
    /// the attached value — the contract verifies this.
    #[odra(payable)]
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
        let attached = self.env().attached_value();
        if attached != initial_deposit {
            self.env().revert(ExecutionError::User(2));
        }
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

    /// Withdraw CSPR from a vault — transfers real CSPR from the contract's
    /// main purse back to the caller. Respects the lock_blocks period: if
    /// the vault is still locked, the withdraw reverts.
    pub fn withdraw(
        &mut self,
        subscriber_address: String,
        amount: U512,
        current_block: u64,
    ) {
        self.assert_vault_owner();
        match self.accounts.get(&subscriber_address) {
            Some(mut account) => {
                // Check lock period
                if account.locked_until_block > 0 && current_block < account.locked_until_block {
                    self.env().revert(ExecutionError::User(5));
                }
                if account.escrowed_balance < amount {
                    self.env().revert(ExecutionError::User(3));
                }
                account.escrowed_balance -= amount;
                account.total_withdrawals += amount;
                self.accounts.set(&subscriber_address, account);
                let locked = self.total_locked.get_or_default().checked_sub(amount)
                    .unwrap_or(U512::zero());
                self.total_locked.set(locked);
                // Transfer real CSPR from the contract's main purse to the caller.
                let caller = self.env().caller();
                self.env().transfer_tokens(&caller, &amount);
            }
            None => self.env().revert(ExecutionError::User(4)),
        }
    }

    /// Returns the contract's real CSPR balance (the main purse balance).
    pub fn get_contract_balance(&self) -> U512 {
        self.env().self_balance()
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

    /// Top up vault balance — PAYABLE.
    ///
    /// The caller attaches real CSPR via `CallDef::with_amount(amount)`. The
    /// `amount` argument MUST match the attached value.
    #[odra(payable)]
    pub fn top_up(&mut self, subscriber_address: String, amount: U512) {
        self.assert_vault_owner();
        let attached = self.env().attached_value();
        if attached != amount {
            self.env().revert(ExecutionError::User(2));
        }
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
        // open_vault is now payable — attach 50 CSPR via with_tokens
        contract
            .with_tokens(U512::from(50_000_000u64))
            .open_vault(
                "casper1proto".to_string(),
                U512::from(50_000_000u64),
                0, true,
                U512::from(100_000_000u64),
                1500000,
            );
        assert_eq!(contract.get_balance("casper1proto".to_string()), U512::from(50_000_000u64));
    }

    #[test]
    fn test_open_vault_increases_contract_balance() {
        let env = odra_test::env();
        let mut contract = SubscriberVaultHostRef::deploy(&env, NoArgs);
        assert_eq!(contract.get_contract_balance(), U512::zero());
        // Payable open_vault transfers real CSPR to the contract's main purse
        contract
            .with_tokens(U512::from(50_000_000u64))
            .open_vault(
                "casper1proto".to_string(),
                U512::from(50_000_000u64),
                0, true,
                U512::from(100_000_000u64),
                1500000,
            );
        assert_eq!(contract.get_contract_balance(), U512::from(50_000_000u64));
    }

    #[test]
    fn test_deduct_from_vault() {
        let env = odra_test::env();
        let mut contract = SubscriberVaultHostRef::deploy(&env, NoArgs);
        contract
            .with_tokens(U512::from(50_000_000u64))
            .open_vault("casper1proto".to_string(), U512::from(50_000_000u64), 0, true, U512::zero(), 1500000);
        let ok = contract.deduct("casper1proto".to_string(), U512::from(5_000_000u64));
        assert!(ok);
        assert_eq!(contract.get_balance("casper1proto".to_string()), U512::from(45_000_000u64));
    }

    #[test]
    fn test_withdraw_transfers_real_cspr() {
        let env = odra_test::env();
        let mut contract = SubscriberVaultHostRef::deploy(&env, NoArgs);
        // Open vault with 50 CSPR (payable)
        contract
            .with_tokens(U512::from(50_000_000u64))
            .open_vault("casper1proto".to_string(), U512::from(50_000_000u64), 0, true, U512::zero(), 1500000);
        assert_eq!(contract.get_contract_balance(), U512::from(50_000_000u64));
        // Withdraw 20 CSPR — should transfer real CSPR back to caller
        contract.withdraw("casper1proto".to_string(), U512::from(20_000_000u64), 1500000);
        // Vault balance decremented
        assert_eq!(contract.get_balance("casper1proto".to_string()), U512::from(30_000_000u64));
        // Contract main purse decremented (20 CSPR transferred out)
        assert_eq!(contract.get_contract_balance(), U512::from(30_000_000u64));
    }

    #[test]
    fn test_withdraw_insufficient_balance_reverts() {
        let env = odra_test::env();
        let mut contract = SubscriberVaultHostRef::deploy(&env, NoArgs);
        contract
            .with_tokens(U512::from(10_000_000u64))
            .open_vault("casper1proto".to_string(), U512::from(10_000_000u64), 0, true, U512::zero(), 1500000);
        // Try to withdraw 50 CSPR (more than balance) — should revert
        let result = contract.try_withdraw("casper1proto".to_string(), U512::from(50_000_000u64), 1500000);
        assert!(result.is_err());
        // Balance unchanged
        assert_eq!(contract.get_balance("casper1proto".to_string()), U512::from(10_000_000u64));
    }

    #[test]
    fn test_withdraw_locked_vault_reverts() {
        let env = odra_test::env();
        let mut contract = SubscriberVaultHostRef::deploy(&env, NoArgs);
        // Open vault locked for 1000 blocks starting at block 1500000
        contract
            .with_tokens(U512::from(10_000_000u64))
            .open_vault("casper1proto".to_string(), U512::from(10_000_000u64), 1000, true, U512::zero(), 1500000);
        // Try to withdraw at block 1500500 (still locked) — should revert
        let result = contract.try_withdraw("casper1proto".to_string(), U512::from(5_000_000u64), 1500500);
        assert!(result.is_err());
        // Balance unchanged
        assert_eq!(contract.get_balance("casper1proto".to_string()), U512::from(10_000_000u64));
    }

    #[test]
    fn test_withdraw_after_lock_expires_succeeds() {
        let env = odra_test::env();
        let mut contract = SubscriberVaultHostRef::deploy(&env, NoArgs);
        // Open vault locked for 1000 blocks starting at block 1500000
        contract
            .with_tokens(U512::from(10_000_000u64))
            .open_vault("casper1proto".to_string(), U512::from(10_000_000u64), 1000, true, U512::zero(), 1500000);
        // Withdraw at block 1501001 (lock expired) — should succeed
        contract.withdraw("casper1proto".to_string(), U512::from(5_000_000u64), 1501001);
        assert_eq!(contract.get_balance("casper1proto".to_string()), U512::from(5_000_000u64));
    }
}
