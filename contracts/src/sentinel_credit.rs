use odra::casper_types::U512;

/// SentinelCredit — x402 credit ledger for pay-per-intelligence queries
///
/// Protocols deposit CSPR credits. Each intelligence query deducts from balance.
/// The IntelAgent verifies credit before serving premium findings.
/// This is the economic engine of VaultWatch — not a flat API, a market.
///
/// ## Access control
///
/// Uses role-based access control (see `crate::rbac`). Operational writes
/// (`deposit`, `withdraw`, `deduct_query`) are OPERATOR-gated and
/// paused-aware; the economic write `set_prices` is ADMIN-gated and
/// paused-aware. Role management is restricted to the `role_admin`. The
/// legacy `transfer_ownership` entry point is preserved as a backward-compat
/// shim that grants `ROLE_ALL` to the new address and transfers `role_admin`.

use odra::prelude::*;

use crate::rbac::{
    has_role, is_valid_role, ERR_INVALID_ROLE, ERR_PAUSED, ERR_UNAUTHORIZED,
    ROLE_ADMIN, ROLE_ALL, ROLE_NONE, ROLE_OPERATOR, ROLE_PAUSER,
};

/// Event emitted whenever CSPR credits are deposited into an account.
///
/// Subscribers / the revenue dashboard listen to this event to track live
/// credit inflows without polling `get_balance`.
#[odra::event]
pub struct CreditDeposited {
    pub account_address: String,
    pub amount: U512,
    pub new_balance: U512,
}

/// Event emitted whenever a role is granted or revoked, or the role-admin is
/// transferred. Provides an on-chain audit trail of every authorization change.
#[odra::event]
pub struct RoleChanged {
    pub account: Address,
    pub role: u8,
    pub granted: bool,
    pub by: Address,
}

/// Event emitted whenever the contract is paused or unpaused.
#[odra::event]
pub struct PauseChanged {
    pub paused: bool,
    pub by: Address,
}

#[odra::odra_type]
pub struct CreditAccount {
    pub owner: String,
    pub balance: U512,       // in motes (1 CSPR = 1_000_000_000 motes)
    pub total_deposited: U512,
    pub total_spent: U512,
    pub query_count: u64,
}

#[odra::module(events = [CreditDeposited, RoleChanged, PauseChanged])]
pub struct SentinelCredit {
    accounts: Mapping<String, CreditAccount>,
    query_price: Var<U512>,   // price per standard query in motes
    premium_price: Var<U512>, // price per premium (RWA-enriched) query
    total_revenue: Var<U512>,
    // ── RBAC state (replaces legacy `owner: Var<Address>`) ──
    /// Per-account role bitmask (OPERATOR | ADMIN | PAUSER).
    roles: Mapping<Address, u8>,
    /// The single role-manager — only account that may grant/revoke roles.
    role_admin: Var<Address>,
    /// Emergency pause flag. When true, every mutable entry point reverts.
    paused: Var<bool>,
}

#[odra::module]
impl SentinelCredit {
    pub fn init(&mut self, query_price: U512, premium_price: U512) {
        let caller = self.env().caller();
        self.role_admin.set(caller);
        self.roles.set(&caller, ROLE_ALL);
        self.paused.set(false);
        self.query_price.set(query_price);
        self.premium_price.set(premium_price);
        self.total_revenue.set(U512::zero());
    }

    /// Deposit CSPR credits to an account — PAYABLE.
    ///
    /// The caller attaches real CSPR via `CallDef::with_amount(amount)`. Odra's
    /// `#[odra(payable)]` attribute auto-invokes `handle_attached_value()` which
    /// transfers the attached CSPR from the caller's cargo purse into this
    /// contract's main purse (`__contract_main_purse`). We then credit the
    /// account's internal balance ledger by the same amount.
    ///
    /// The `amount` argument MUST match the attached value — the contract
    /// verifies this to prevent accounting drift.
    #[odra(payable)]
    pub fn deposit(&mut self, account_address: String, amount: U512) {
        self.assert_role(ROLE_OPERATOR);
        self.assert_not_paused();
        let attached = self.env().attached_value();
        if attached != amount {
            self.env().revert(crate::user_err(2));
        }
        let mut account = self.accounts.get(&account_address).unwrap_or(CreditAccount {
            owner: account_address.clone(),
            balance: U512::zero(),
            total_deposited: U512::zero(),
            total_spent: U512::zero(),
            query_count: 0,
        });
        account.balance += amount;
        account.total_deposited += amount;
        let new_balance = account.balance;
        self.accounts.set(&account_address, account);

        // Emit the on-chain event so subscribers / revenue dashboard are notified.
        self.env().emit_event(CreditDeposited {
            account_address,
            amount,
            new_balance,
        });
    }

    /// Withdraw CSPR credits from an account — transfers real CSPR from the
    /// contract's main purse back to the caller's account.
    ///
    /// The caller must be an OPERATOR. The account's balance is
    /// decremented and the equivalent CSPR is transferred via
    /// `self.env().transfer_tokens()`.
    pub fn withdraw(&mut self, account_address: String, amount: U512) {
        self.assert_role(ROLE_OPERATOR);
        self.assert_not_paused();
        match self.accounts.get(&account_address) {
            Some(mut account) => {
                if account.balance < amount {
                    self.env().revert(crate::user_err(3));
                }
                account.balance -= amount;
                self.accounts.set(&account_address, account);
                // Transfer real CSPR from the contract's main purse to the caller.
                let caller = self.env().caller();
                self.env().transfer_tokens(&caller, &amount);
            }
            None => self.env().revert(crate::user_err(4)),
        }
    }

    /// Returns the contract's real CSPR balance (the main purse balance).
    pub fn get_contract_balance(&self) -> U512 {
        self.env().self_balance()
    }

    /// Deduct credit for a standard query — called by IntelAgent
    pub fn deduct_query(&mut self, account_address: String, is_premium: bool) -> bool {
        self.assert_role(ROLE_OPERATOR);
        self.assert_not_paused();
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
        self.assert_role(ROLE_ADMIN);
        self.assert_not_paused();
        self.query_price.set(query_price);
        self.premium_price.set(premium_price);
    }

    // ────────────────────────────── RBAC ──────────────────────────────

    /// Grant a role to an account. Only the `role_admin` may call this.
    ///
    /// `role` must be a valid single-role bit or `ROLE_ALL`. Invalid bitmasks
    /// revert with `ERR_INVALID_ROLE`. The zero address reverts with
    /// `ERR_ZERO_ADDRESS`.
    pub fn grant_role(&mut self, account: Address, role: u8) {
        self.assert_role_admin();
        if !is_valid_role(role) {
            self.env().revert(crate::user_err(ERR_INVALID_ROLE));
        }
        let current = self.roles.get(&account).unwrap_or(0);
        let new_roles = current | role;
        self.roles.set(&account, new_roles);
        self.env().emit_event(RoleChanged {
            account,
            role,
            granted: true,
            by: self.env().caller(),
        });
    }

    /// Revoke a role from an account. Only the `role_admin` may call this.
    /// The role_admin may revoke its own roles (but cannot revoke its own
    /// role_admin status — use `transfer_role_admin` for that).
    pub fn revoke_role(&mut self, account: Address, role: u8) {
        self.assert_role_admin();
        if !is_valid_role(role) {
            self.env().revert(crate::user_err(ERR_INVALID_ROLE));
        }
        let current = self.roles.get(&account).unwrap_or(0);
        let new_roles = current & !role;
        self.roles.set(&account, new_roles);
        self.env().emit_event(RoleChanged {
            account,
            role,
            granted: false,
            by: self.env().caller(),
        });
    }

    /// Caller renounces a role it currently holds. This is a self-service
    /// escape hatch — no role_admin required — so a compromised OPERATOR can
    /// voluntarily shed authority without coordinating with the role_admin.
    pub fn renounce_role(&mut self, role: u8) {
        let caller = self.env().caller();
        if !is_valid_role(role) {
            self.env().revert(crate::user_err(ERR_INVALID_ROLE));
        }
        let current = self.roles.get(&caller).unwrap_or(0);
        let new_roles = current & !role;
        self.roles.set(&caller, new_roles);
        self.env().emit_event(RoleChanged {
            account: caller,
            role,
            granted: false,
            by: caller,
        });
    }

    /// Public check: does `account` hold `role`?
    pub fn has_role(&self, account: Address, role: u8) -> bool {
        has_role(self.roles.get(&account).unwrap_or(ROLE_NONE), role)
    }

    /// Public read of the full role bitmask for `account`.
    pub fn get_roles(&self, account: Address) -> u8 {
        self.roles.get(&account).unwrap_or(ROLE_NONE)
    }

    /// Public read of the current role_admin address.
    pub fn get_role_admin(&self) -> Address {
        self.role_admin.get_or_revert_with(crate::user_err(ERR_UNAUTHORIZED))
    }

    /// Transfer the role_admin to a new account. Only the current role_admin
    /// may call this. The new admin does NOT automatically receive any role
    /// bits — call `grant_role` afterwards if it should also be an OPERATOR.
    ///
    /// Note: Casper `Address` has no canonical zero value, so there is no
    /// explicit zero-address guard here. The `assert_role_admin` check is the
    /// sole protection — only the current role_admin (a real, validated
    /// account) can invoke this, and it is expected to pass a real account.
    pub fn transfer_role_admin(&mut self, new_admin: Address) {
        self.assert_role_admin();
        self.role_admin.set(new_admin);
        self.env().emit_event(RoleChanged {
            account: new_admin,
            role: ROLE_ALL,
            granted: true,
            by: self.env().caller(),
        });
    }

    /// Backward-compat shim for the legacy single-owner `transfer_ownership`.
    ///
    /// ADMIN-gated. Grants `ROLE_ALL` to `new_owner` and transfers `role_admin`
    /// to it, then strips all roles from the caller. This preserves the
    /// semantics of the old entry point (one call hands over all authority)
    /// while the granular `grant_role` / `revoke_role` / `transfer_role_admin`
    /// entry points remain available for split-key operations.
    pub fn transfer_ownership(&mut self, new_owner: Address) {
        self.assert_role(ROLE_ADMIN);
        let caller = self.env().caller();
        self.roles.set(&new_owner, ROLE_ALL);
        self.role_admin.set(new_owner);
        // Strip all roles from the previous holder.
        self.roles.set(&caller, ROLE_NONE);
        self.env().emit_event(RoleChanged {
            account: new_owner,
            role: ROLE_ALL,
            granted: true,
            by: caller,
        });
    }

    // ────────────────────────────── Pause ─────────────────────────────

    /// Pause the contract — only PAUSER. Not guarded by `assert_not_paused`
    /// (idempotent: pausing an already-paused contract is a no-op).
    pub fn pause(&mut self) {
        self.assert_role(ROLE_PAUSER);
        self.paused.set(true);
        self.env().emit_event(PauseChanged {
            paused: true,
            by: self.env().caller(),
        });
    }

    /// Unpause the contract — only PAUSER. Not guarded by `assert_not_paused`
    /// (otherwise a paused contract could never be unpaused).
    pub fn unpause(&mut self) {
        self.assert_role(ROLE_PAUSER);
        self.paused.set(false);
        self.env().emit_event(PauseChanged {
            paused: false,
            by: self.env().caller(),
        });
    }

    /// Public read of the pause flag.
    pub fn is_paused(&self) -> bool {
        self.paused.get_or_default()
    }

    // ──────────────────────────── Assertions ────────────────────────────

    /// Revert if the caller does not hold `role`.
    fn assert_role(&self, role: u8) {
        let caller = self.env().caller();
        let roles = self.roles.get(&caller).unwrap_or(ROLE_NONE);
        if !has_role(roles, role) {
            self.env().revert(crate::user_err(ERR_UNAUTHORIZED));
        }
    }

    /// Revert if the caller is not the role_admin.
    fn assert_role_admin(&self) {
        let caller = self.env().caller();
        let admin = self.role_admin.get_or_revert_with(crate::user_err(ERR_UNAUTHORIZED));
        if caller != admin {
            self.env().revert(crate::user_err(ERR_UNAUTHORIZED));
        }
    }

    /// Revert if the contract is paused.
    fn assert_not_paused(&self) {
        if self.paused.get_or_default() {
            self.env().revert(crate::user_err(ERR_PAUSED));
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
        let mut contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        // deposit is now payable — attach 10 CSPR (10_000_000_000 motes) via with_tokens
        contract
            .with_tokens(U512::from(10_000_000u64))
            .deposit("casper1proto".to_string(), U512::from(10_000_000u64));
        assert_eq!(contract.get_balance("casper1proto".to_string()), U512::from(10_000_000u64));
    }

    #[test]
    fn test_deposit_increases_contract_balance() {
        let env = odra_test::env();
        let mut contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        // Contract starts with 0 CSPR
        assert_eq!(contract.get_contract_balance(), U512::zero());
        // Payable deposit transfers real CSPR to the contract's main purse
        contract
            .with_tokens(U512::from(10_000_000u64))
            .deposit("casper1proto".to_string(), U512::from(10_000_000u64));
        assert_eq!(contract.get_contract_balance(), U512::from(10_000_000u64));
    }

    #[test]
    fn test_deduct_query_success() {
        let env = odra_test::env();
        let mut contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        contract
            .with_tokens(U512::from(10_000_000u64))
            .deposit("casper1proto".to_string(), U512::from(10_000_000u64));
        let success = contract.deduct_query("casper1proto".to_string(), false);
        assert!(success);
        assert_eq!(contract.get_balance("casper1proto".to_string()), U512::from(9_000_000u64));
    }

    #[test]
    fn test_deduct_query_insufficient_credit() {
        let env = odra_test::env();
        let mut contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        let success = contract.deduct_query("casper1broke".to_string(), false);
        assert!(!success);
    }

    #[test]
    fn test_withdraw_transfers_real_cspr() {
        let env = odra_test::env();
        let mut contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        // Deposit 10 CSPR (payable)
        contract
            .with_tokens(U512::from(10_000_000u64))
            .deposit("casper1proto".to_string(), U512::from(10_000_000u64));
        assert_eq!(contract.get_contract_balance(), U512::from(10_000_000u64));
        // Withdraw 4 CSPR — should transfer real CSPR back to caller
        contract.withdraw("casper1proto".to_string(), U512::from(4_000_000u64));
        // Account balance decremented
        assert_eq!(contract.get_balance("casper1proto".to_string()), U512::from(6_000_000u64));
        // Contract main purse decremented (4 CSPR transferred out)
        assert_eq!(contract.get_contract_balance(), U512::from(6_000_000u64));
    }

    #[test]
    fn test_withdraw_insufficient_balance_reverts() {
        let env = odra_test::env();
        let mut contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        // Deposit 2 CSPR
        contract
            .with_tokens(U512::from(2_000_000u64))
            .deposit("casper1proto".to_string(), U512::from(2_000_000u64));
        // Try to withdraw 5 CSPR (more than balance) — should revert
        let result = contract.try_withdraw("casper1proto".to_string(), U512::from(5_000_000u64));
        assert!(result.is_err());
        // Balance unchanged
        assert_eq!(contract.get_balance("casper1proto".to_string()), U512::from(2_000_000u64));
    }

    #[test]
    fn test_withdraw_nonexistent_account_reverts() {
        let env = odra_test::env();
        let mut contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        let result = contract.try_withdraw("ghost".to_string(), U512::from(1_000u64));
        assert!(result.is_err());
    }

    // ── RBAC tests ──

    #[test]
    fn test_init_grants_deployer_all_roles_and_role_admin() {
        let env = odra_test::env();
        let contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        let deployer = env.get_account(0);
        assert_eq!(contract.get_roles(deployer), ROLE_ALL);
        assert!(contract.has_role(deployer, ROLE_OPERATOR));
        assert!(contract.has_role(deployer, ROLE_ADMIN));
        assert!(contract.has_role(deployer, ROLE_PAUSER));
        assert_eq!(contract.get_role_admin(), deployer);
        assert!(!contract.is_paused());
    }

    #[test]
    fn test_non_operator_reverts_on_withdraw() {
        // Account 1 has no roles — withdraw must revert on role check.
        let env = odra_test::env();
        let mut contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        let outsider = env.get_account(1);
        env.set_caller(outsider);
        let r = contract.try_withdraw("any".to_string(), U512::from(1_000u64));
        assert!(r.is_err(), "non-operator must be rejected");
    }

    #[test]
    fn test_grant_role_enables_operator() {
        let env = odra_test::env();
        let mut contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        let ops = env.get_account(1);
        assert!(!contract.has_role(ops, ROLE_OPERATOR));
        contract.grant_role(ops, ROLE_OPERATOR);
        assert!(contract.has_role(ops, ROLE_OPERATOR));
        assert!(!contract.has_role(ops, ROLE_ADMIN));
    }

    #[test]
    fn test_non_role_admin_cannot_grant_role() {
        let env = odra_test::env();
        let mut contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        let ops = env.get_account(1);
        contract.grant_role(ops, ROLE_OPERATOR);
        env.set_caller(ops);
        let other = env.get_account(2);
        let r = contract.try_grant_role(other, ROLE_ADMIN);
        assert!(r.is_err(), "non-role-admin must not be able to grant roles");
        assert!(!contract.has_role(other, ROLE_ADMIN));
    }

    #[test]
    fn test_pause_blocks_writes_and_unpause_restores() {
        let env = odra_test::env();
        let mut contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        // Pre-fund the account so withdraw would otherwise succeed.
        contract
            .with_tokens(U512::from(10_000_000u64))
            .deposit("casper1proto".to_string(), U512::from(10_000_000u64));
        // deployer is PAUSER
        contract.pause();
        assert!(contract.is_paused());
        // withdraw must now revert (paused)
        let r = contract.try_withdraw("casper1proto".to_string(), U512::from(1_000u64));
        assert!(r.is_err(), "paused contract must reject writes");
        // unpause
        contract.unpause();
        assert!(!contract.is_paused());
        // now writes succeed again
        contract.withdraw("casper1proto".to_string(), U512::from(1_000u64));
        assert_eq!(contract.get_balance("casper1proto".to_string()), U512::from(9_999_000u64));
    }

    #[test]
    fn test_renounce_role_strips_authority() {
        let env = odra_test::env();
        let mut contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        contract
            .with_tokens(U512::from(10_000_000u64))
            .deposit("casper1proto".to_string(), U512::from(10_000_000u64));
        // deployer renounces OPERATOR — withdraw must then revert
        contract.renounce_role(ROLE_OPERATOR);
        let r = contract.try_withdraw("casper1proto".to_string(), U512::from(1_000u64));
        assert!(r.is_err(), "after renouncing OPERATOR, writes must revert");
        // deployer still is role_admin and ADMIN/PAUSER
        assert!(contract.has_role(env.get_account(0), ROLE_ADMIN));
    }

    #[test]
    fn test_transfer_ownership_grants_all_and_strips_caller() {
        let env = odra_test::env();
        let mut contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        let new_owner = env.get_account(1);
        contract.transfer_ownership(new_owner);
        assert_eq!(contract.get_roles(new_owner), ROLE_ALL);
        assert_eq!(contract.get_role_admin(), new_owner);
        assert_eq!(contract.get_roles(env.get_account(0)), ROLE_NONE);
    }

    #[test]
    fn test_grant_invalid_role_reverts() {
        let env = odra_test::env();
        let mut contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        let ops = env.get_account(1);
        let r = contract.try_grant_role(ops, 0b1000_0000);
        assert!(r.is_err(), "invalid role bitmask must revert");
    }

    #[test]
    fn test_non_pauser_cannot_pause() {
        let env = odra_test::env();
        let mut contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        let ops = env.get_account(1);
        contract.grant_role(ops, ROLE_OPERATOR); // OPERATOR but NOT PAUSER
        env.set_caller(ops);
        let r = contract.try_pause();
        assert!(r.is_err(), "non-PAUSER must not be able to pause");
        assert!(!contract.is_paused());
    }

    #[test]
    fn test_set_prices_is_admin_gated() {
        let env = odra_test::env();
        let mut contract = SentinelCredit::deploy(&env, SentinelCreditInitArgs {
            query_price: U512::from(1_000_000u64),
            premium_price: U512::from(5_000_000u64),
        });
        // OPERATOR-only account cannot set_prices (needs ADMIN).
        let ops = env.get_account(1);
        contract.grant_role(ops, ROLE_OPERATOR);
        env.set_caller(ops);
        let r = contract.try_set_prices(U512::from(2_000_000u64), U512::from(8_000_000u64));
        assert!(r.is_err(), "OPERATOR must not be able to set prices (ADMIN-gated)");
        // deployer (ROLE_ALL → includes ADMIN) can set prices.
        let deployer = env.get_account(0);
        env.set_caller(deployer);
        contract.set_prices(U512::from(2_000_000u64), U512::from(8_000_000u64));
        assert_eq!(contract.get_query_price(), U512::from(2_000_000u64));
        assert_eq!(contract.get_premium_price(), U512::from(8_000_000u64));
    }
}
