use odra::casper_types::U512;

/// SentinelCredit — x402 credit ledger for pay-per-intelligence queries
///
/// Protocols deposit CSPR credits. Each intelligence query deducts from balance.
/// The IntelAgent verifies credit before serving premium findings.
/// This is the economic engine of VaultWatch — not a flat API, a market.

use odra::prelude::*;

#[odra::odra_type]
pub struct CreditAccount {
    pub owner: String,
    pub balance: U512,       // in motes (1 CSPR = 1_000_000_000 motes)
    pub total_deposited: U512,
    pub total_spent: U512,
    pub query_count: u64,
}

#[odra::module]
pub struct SentinelCredit {
    accounts: Mapping<String, CreditAccount>,
    query_price: Var<U512>,   // price per standard query in motes
    premium_price: Var<U512>, // price per premium (RWA-enriched) query
    owner: Var<Address>,
    total_revenue: Var<U512>,
}

#[odra::module]
impl SentinelCredit {
    pub fn init(&mut self, query_price: U512, premium_price: U512) {
        self.owner.set(self.env().caller());
        self.query_price.set(query_price);
        self.premium_price.set(premium_price);
        self.total_revenue.set(U512::zero());
    }

    /// Deposit CSPR credits to an account
    pub fn deposit(&mut self, account_address: String, amount: U512) {
        self.assert_owner();
        let mut account = self.accounts.get(&account_address).unwrap_or(CreditAccount {
            owner: account_address.clone(),
            balance: U512::zero(),
            total_deposited: U512::zero(),
            total_spent: U512::zero(),
            query_count: 0,
        });
        account.balance += amount;
        account.total_deposited += amount;
        self.accounts.set(&account_address, account);
    }

    /// Deduct credit for a standard query — called by IntelAgent
    pub fn deduct_query(&mut self, account_address: String, is_premium: bool) -> bool {
        self.assert_owner();
        let price = if is_premium {
            self.premium_price.get_or_default()
        } else {
            self.query_price.get_or_default()
        };

        match self.accounts.get(&account_address) {
            Some(mut account) => {
                if account.balance < price {
                    return false; // insufficient credit
                }
                account.balance -= price;
                account.total_spent += price;
                account.query_count += 1;
                self.accounts.set(&account_address, account);
                let rev = self.total_revenue.get_or_default() + price;
                self.total_revenue.set(rev);
                true
            }
            None => false,
        }
    }

    /// Check credit balance for an account
    pub fn get_balance(&self, account_address: String) -> U512 {
        match self.accounts.get(&account_address) {
            Some(account) => account.balance,
            None => U512::zero(),
        }
    }

    pub fn get_account(&self, account_address: String) -> Option<CreditAccount> {
        self.accounts.get(&account_address)
    }

    pub fn get_query_price(&self) -> U512 {
        self.query_price.get_or_default()
    }

    pub fn get_premium_price(&self) -> U512 {
        self.premium_price.get_or_default()
    }

    pub fn get_total_revenue(&self) -> U512 {
        self.total_revenue.get_or_default()
    }

    pub fn set_prices(&mut self, query_price: U512, premium_price: U512) {
        self.assert_owner();
        self.query_price.set(query_price);
        self.premium_price.set(premium_price);
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
    fn test_deposit_and_balance() {
        let env = odra_test::env();
        let mut contract = SentinelCreditHostRef::deploy(&env, InitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        contract.deposit("casper1proto".to_string(), U512::from(10_000_000u64));
        assert_eq!(contract.get_balance("casper1proto".to_string()), U512::from(10_000_000u64));
    }

    #[test]
    fn test_deduct_query_success() {
        let env = odra_test::env();
        let mut contract = SentinelCreditHostRef::deploy(&env, InitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        contract.deposit("casper1proto".to_string(), U512::from(10_000_000u64));
        let success = contract.deduct_query("casper1proto".to_string(), false);
        assert!(success);
        assert_eq!(contract.get_balance("casper1proto".to_string()), U512::from(9_000_000u64));
    }

    #[test]
    fn test_deduct_query_insufficient_credit() {
        let env = odra_test::env();
        let mut contract = SentinelCreditHostRef::deploy(&env, InitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        let success = contract.deduct_query("casper1broke".to_string(), false);
        assert!(!success);
    }
}
