use odra::casper_types::U512;

/// SentinelCredit — x402 credit ledger for pay-per-intelligence queries
///
/// Protocols deposit CSPR credits. Each intelligence query deducts from balance.
/// The IntelAgent verifies credit before serving premium findings.
/// This is the economic engine of VaultWatch — not a flat API, a market.
///
/// FIX #8:  deposit() is now #[odra(payable)] — accepts real CSPR via attached value
///          withdraw() added for owner to withdraw collected revenue
/// FIX #11: Added Odra events (CreditDeposited, CreditDeducted, RevenueWithdrawn)

use odra::prelude::*;

// ─── Events ────────────────────────────────────────────────────────────────

#[odra::event]
pub struct CreditDeposited {
    pub account: String,
    pub amount_motes: U512,
    pub new_balance: U512,
}

#[odra::event]
pub struct CreditDeducted {
    pub account: String,
    pub amount_motes: U512,
    pub remaining_balance: U512,
    pub query_type: String,
}

#[odra::event]
pub struct RevenueWithdrawn {
    pub to: Address,
    pub amount_motes: U512,
}

// ─── Data types ────────────────────────────────────────────────────────────

#[odra::odra_type]
pub struct CreditAccount {
    pub owner: String,
    pub balance: U512,
    pub total_deposited: U512,
    pub total_spent: U512,
    pub query_count: u64,
}

// ─── Contract ──────────────────────────────────────────────────────────────

#[odra::module]
pub struct SentinelCredit {
    accounts: Mapping<String, CreditAccount>,
    query_price: Var<U512>,
    premium_price: Var<U512>,
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

    /// FIX #8: Deposit CSPR credits — now payable, accepts attached_value()
    /// Caller sends CSPR with the deploy; this records it as a credit balance.
    #[odra(payable)]
    pub fn deposit(&mut self, account_address: String) {
        // FIX #8: use env().attached_value() for real CSPR transfer
        let amount = self.env().attached_value();
        if amount == U512::zero() {
            self.env().revert(Error::ZeroDeposit);
        }

        let mut account = self.accounts.get(&account_address).unwrap_or(CreditAccount {
            owner: account_address.clone(),
            balance: U512::zero(),
            total_deposited: U512::zero(),
            total_spent: U512::zero(),
            query_count: 0u64,
        });

        account.balance += amount;
        account.total_deposited += amount;
        self.accounts.set(&account_address, account.clone());

        // FIX #11: emit event
        self.env().emit_event(CreditDeposited {
            account: account_address,
            amount_motes: amount,
            new_balance: account.balance,
        });
    }

    /// Deduct credits for a query — called by VaultWatch IntelAgent
    pub fn deduct_credit(
        &mut self,
        account_address: String,
        query_type: String,
    ) -> bool {
        self.assert_owner();

        let price = if query_type == "premium" {
            self.premium_price.get().unwrap_or(U512::zero())
        } else {
            self.query_price.get().unwrap_or(U512::zero())
        };

        let mut account = match self.accounts.get(&account_address) {
            Some(a) => a,
            None => return false,
        };

        if account.balance < price {
            return false;
        }

        account.balance -= price;
        account.total_spent += price;
        account.query_count += 1;
        let remaining = account.balance;
        self.accounts.set(&account_address, account);

        let rev = self.total_revenue.get().unwrap_or(U512::zero());
        self.total_revenue.set(rev + price);

        // FIX #11: emit event
        self.env().emit_event(CreditDeducted {
            account: account_address,
            amount_motes: price,
            remaining_balance: remaining,
            query_type,
        });

        true
    }

    /// FIX #8: Withdraw collected revenue to owner wallet
    pub fn withdraw(&mut self, amount: U512, to: Address) {
        self.assert_owner();
        let rev = self.total_revenue.get().unwrap_or(U512::zero());
        if amount > rev {
            self.env().revert(Error::InsufficientRevenue);
        }
        self.total_revenue.set(rev - amount);
        // Transfer CSPR to recipient
        self.env().transfer_tokens(&to, &amount);

        // FIX #11: emit event
        self.env().emit_event(RevenueWithdrawn { to, amount_motes: amount });
    }

    pub fn get_balance(&self, account_address: String) -> U512 {
        self.accounts
            .get(&account_address)
            .map(|a| a.balance)
            .unwrap_or(U512::zero())
    }

    pub fn get_query_price(&self) -> U512 {
        self.query_price.get().unwrap_or(U512::zero())
    }

    pub fn get_premium_price(&self) -> U512 {
        self.premium_price.get().unwrap_or(U512::zero())
    }

    pub fn total_revenue(&self) -> U512 {
        self.total_revenue.get().unwrap_or(U512::zero())
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
    InsufficientBalance = 2,
    InsufficientRevenue = 3,
    ZeroDeposit = 4,
}
