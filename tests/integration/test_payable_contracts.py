"""
Critical Fix 8 — Payable contracts verification.

Verifies that SentinelCredit and SubscriberVault contracts are payable:
  - SentinelCredit.deposit transfers real CSPR via main_purse
  - SubscriberVault.open_vault transfers real CSPR via main_purse
  - SubscriberVault.top_up transfers real CSPR via main_purse
  - withdraw() entry points exist on both contracts
  - get_contract_balance() entry points exist on both contracts
  - The #[odra(payable)] attribute is present on deposit/open_vault/top_up
  - self.env().attached_value() is checked (amount == attached_value)
  - self.env().transfer_tokens() is used for withdrawals
  - self.env().self_balance() is used for get_contract_balance
  - The compiled WASM artifacts contain the new entry points + __contract_main_purse

Official resources (per hackathon detail):
  - Odra Framework (odra.dev) — #[odra(payable)] attribute, attached_value(),
    self_balance(), transfer_tokens(), __contract_main_purse
  - Casper docs (docs.casper.network) — contract payable patterns, main_purse
  - Casper Testnet RPC — on-chain verification of contract entry points
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent.parent
CONTRACTS_SRC = ROOT / "contracts" / "src"
CONTRACTS_WASM = ROOT / "contracts" / "wasm"


# ---------------------------------------------------------------------------
# §1  SentinelCredit — payable deposit + withdraw
# ---------------------------------------------------------------------------


def test_sentinel_credit_deposit_has_payable_attribute():
    """SentinelCredit.deposit must have #[odra(payable)] attribute."""
    src = (CONTRACTS_SRC / "sentinel_credit.rs").read_text()
    # Find the deposit function and check it has #[odra(payable)]
    deposit_match = re.search(
        r'#\[odra\(payable\)\]\s*\n\s*pub fn deposit\(',
        src,
    )
    assert deposit_match is not None, (
        "SentinelCredit.deposit must have #[odra(payable)] attribute — "
        "without it, the contract cannot accept real CSPR transfers."
    )


def test_sentinel_credit_deposit_checks_attached_value():
    """deposit() must verify attached_value() == amount to prevent accounting drift."""
    src = (CONTRACTS_SRC / "sentinel_credit.rs").read_text()
    assert "self.env().attached_value()" in src, (
        "SentinelCredit.deposit must call self.env().attached_value() to "
        "verify the attached CSPR matches the amount argument."
    )
    assert "attached != amount" in src or "attached != amount" in src, (
        "deposit() must revert if attached_value != amount."
    )


def test_sentinel_credit_has_withdraw_entry_point():
    """SentinelCredit must have a withdraw() entry point that transfers real CSPR."""
    src = (CONTRACTS_SRC / "sentinel_credit.rs").read_text()
    assert "pub fn withdraw(" in src, (
        "SentinelCredit must have a withdraw() entry point."
    )
    # withdraw must use transfer_tokens to send real CSPR back to caller
    # Extract the withdraw function body (from 'pub fn withdraw' to the next 'pub fn' or end of impl)
    withdraw_start = src.index("pub fn withdraw(")
    # Find the next 'pub fn' after withdraw to bound the search
    next_fn = src.find("pub fn ", withdraw_start + 10)
    if next_fn == -1:
        withdraw_section = src[withdraw_start:]
    else:
        withdraw_section = src[withdraw_start:next_fn]
    assert "transfer_tokens" in withdraw_section, (
        "SentinelCredit.withdraw must call self.env().transfer_tokens() to "
        "transfer real CSPR from the contract's main purse back to the caller. "
        f"Withdraw section: {withdraw_section[:300]}"
    )


def test_sentinel_credit_withdraw_checks_balance():
    """withdraw() must check the account has sufficient balance before transferring."""
    src = (CONTRACTS_SRC / "sentinel_credit.rs").read_text()
    withdraw_section = re.search(
        r'pub fn withdraw\([^)]*\)\s*\{.*?\n    \}',
        src,
        re.DOTALL,
    )
    assert withdraw_section is not None
    withdraw_code = withdraw_section.group(0)
    assert "account.balance < amount" in withdraw_code, (
        "withdraw() must check account.balance < amount and revert if insufficient."
    )


def test_sentinel_credit_has_get_contract_balance():
    """SentinelCredit must have get_contract_balance() that reads the main purse."""
    src = (CONTRACTS_SRC / "sentinel_credit.rs").read_text()
    assert "pub fn get_contract_balance" in src, (
        "SentinelCredit must have a get_contract_balance() entry point."
    )
    assert "self.env().self_balance()" in src, (
        "get_contract_balance() must use self.env().self_balance() to read "
        "the contract's main purse balance."
    )


# ---------------------------------------------------------------------------
# §2  SubscriberVault — payable open_vault + top_up + withdraw
# ---------------------------------------------------------------------------


def test_subscriber_vault_open_vault_has_payable_attribute():
    """SubscriberVault.open_vault must have #[odra(payable)] attribute."""
    src = (CONTRACTS_SRC / "subscriber_vault.rs").read_text()
    open_vault_match = re.search(
        r'#\[odra\(payable\)\]\s*\n\s*pub fn open_vault\(',
        src,
    )
    assert open_vault_match is not None, (
        "SubscriberVault.open_vault must have #[odra(payable)] attribute — "
        "without it, the contract cannot accept real CSPR for escrow."
    )


def test_subscriber_vault_open_vault_checks_attached_value():
    """open_vault() must verify attached_value() == initial_deposit."""
    src = (CONTRACTS_SRC / "subscriber_vault.rs").read_text()
    assert "self.env().attached_value()" in src, (
        "SubscriberVault.open_vault must call self.env().attached_value()."
    )


def test_subscriber_vault_top_up_has_payable_attribute():
    """SubscriberVault.top_up must have #[odra(payable)] attribute."""
    src = (CONTRACTS_SRC / "subscriber_vault.rs").read_text()
    top_up_match = re.search(
        r'#\[odra\(payable\)\]\s*\n\s*pub fn top_up\(',
        src,
    )
    assert top_up_match is not None, (
        "SubscriberVault.top_up must have #[odra(payable)] attribute — "
        "topping up should also transfer real CSPR."
    )


def test_subscriber_vault_has_withdraw_entry_point():
    """SubscriberVault must have a withdraw() entry point."""
    src = (CONTRACTS_SRC / "subscriber_vault.rs").read_text()
    assert "pub fn withdraw(" in src, (
        "SubscriberVault must have a withdraw() entry point."
    )
    # Extract the withdraw function body
    withdraw_start = src.index("pub fn withdraw(")
    next_fn = src.find("pub fn ", withdraw_start + 10)
    if next_fn == -1:
        withdraw_section = src[withdraw_start:]
    else:
        withdraw_section = src[withdraw_start:next_fn]
    assert "transfer_tokens" in withdraw_section, (
        "SubscriberVault.withdraw must call self.env().transfer_tokens()."
    )


def test_subscriber_vault_withdraw_respects_lock_period():
    """withdraw() must respect the locked_until_block period."""
    src = (CONTRACTS_SRC / "subscriber_vault.rs").read_text()
    withdraw_start = src.index("pub fn withdraw(")
    next_fn = src.find("pub fn ", withdraw_start + 10)
    if next_fn == -1:
        withdraw_section = src[withdraw_start:]
    else:
        withdraw_section = src[withdraw_start:next_fn]
    assert "locked_until_block" in withdraw_section, (
        "withdraw() must check the locked_until_block period and revert if "
        "the vault is still locked."
    )


def test_subscriber_vault_has_get_contract_balance():
    """SubscriberVault must have get_contract_balance()."""
    src = (CONTRACTS_SRC / "subscriber_vault.rs").read_text()
    assert "pub fn get_contract_balance" in src, (
        "SubscriberVault must have a get_contract_balance() entry point."
    )


# ---------------------------------------------------------------------------
# §3  WASM artifacts — verify the compiled WASMs contain payable code
# ---------------------------------------------------------------------------


def test_sentinel_credit_wasm_exists():
    """SentinelCredit.wasm must exist in the wasm directory."""
    assert (CONTRACTS_WASM / "SentinelCredit.wasm").exists(), (
        "SentinelCredit.wasm not found in contracts/wasm/"
    )


def test_subscriber_vault_wasm_exists():
    """SubscriberVault.wasm must exist in the wasm directory."""
    assert (CONTRACTS_WASM / "SubscriberVault.wasm").exists(), (
        "SubscriberVault.wasm not found in contracts/wasm/"
    )


def test_sentinel_credit_wasm_contains_withdraw():
    """SentinelCredit.wasm must contain the 'withdraw' entry point string."""
    wasm_path = CONTRACTS_WASM / "SentinelCredit.wasm"
    data = wasm_path.read_bytes()
    assert b"withdraw" in data, (
        "SentinelCredit.wasm does not contain 'withdraw' — the WASM was not "
        "rebuilt with the new payable source code."
    )


def test_sentinel_credit_wasm_contains_get_contract_balance():
    """SentinelCredit.wasm must contain 'get_contract_balance' string."""
    wasm_path = CONTRACTS_WASM / "SentinelCredit.wasm"
    data = wasm_path.read_bytes()
    assert b"get_contract_balance" in data, (
        "SentinelCredit.wasm does not contain 'get_contract_balance'."
    )


def test_subscriber_vault_wasm_contains_withdraw():
    """SubscriberVault.wasm must contain the 'withdraw' entry point string."""
    wasm_path = CONTRACTS_WASM / "SubscriberVault.wasm"
    data = wasm_path.read_bytes()
    assert b"withdraw" in data, (
        "SubscriberVault.wasm does not contain 'withdraw' — the WASM was not "
        "rebuilt with the new payable source code."
    )


def test_subscriber_vault_wasm_contains_get_contract_balance():
    """SubscriberVault.wasm must contain 'get_contract_balance' string."""
    wasm_path = CONTRACTS_WASM / "SubscriberVault.wasm"
    data = wasm_path.read_bytes()
    assert b"get_contract_balance" in data, (
        "SubscriberVault.wasm does not contain 'get_contract_balance'."
    )


def test_wasm_files_contain_main_purse():
    """Both WASMs must reference __contract_main_purse (the Odra payment URef)."""
    for name in ["SentinelCredit.wasm", "SubscriberVault.wasm"]:
        wasm_path = CONTRACTS_WASM / name
        data = wasm_path.read_bytes()
        assert b"__contract_main_purse" in data, (
            f"{name} does not contain '__contract_main_purse' — the payable "
            "main purse URef is not present. The contract was not compiled "
            "with the payable code."
        )


# ---------------------------------------------------------------------------
# §4  Odra payable pattern — verify the correct Odra API is used
# ---------------------------------------------------------------------------


def test_sentinel_credit_uses_odra_payment_api():
    """SentinelCredit must use Odra's payment API (attached_value, self_balance, transfer_tokens)."""
    src = (CONTRACTS_SRC / "sentinel_credit.rs").read_text()
    assert "self.env().attached_value()" in src, (
        "Must use self.env().attached_value() to read the attached CSPR."
    )
    assert "self.env().self_balance()" in src, (
        "Must use self.env().self_balance() to read the contract's main purse."
    )
    assert "self.env().transfer_tokens(" in src, (
        "Must use self.env().transfer_tokens() to transfer CSPR back to caller."
    )


def test_subscriber_vault_uses_odra_payment_api():
    """SubscriberVault must use Odra's payment API."""
    src = (CONTRACTS_SRC / "subscriber_vault.rs").read_text()
    assert "self.env().attached_value()" in src
    assert "self.env().self_balance()" in src
    assert "self.env().transfer_tokens(" in src


# ---------------------------------------------------------------------------
# §5  Error codes — verify the new error codes are documented
# ---------------------------------------------------------------------------


def test_sentinel_credit_has_payment_error_codes():
    """SentinelCredit must have error codes for payment failures."""
    src = (CONTRACTS_SRC / "sentinel_credit.rs").read_text()
    # Error code 2 = attached_value != amount
    assert "ExecutionError::User(2)" in src, (
        "Must revert with User(2) when attached_value != amount."
    )
    # Error code 3 = insufficient balance for withdraw
    assert "ExecutionError::User(3)" in src, (
        "Must revert with User(3) when withdraw amount > balance."
    )
    # Error code 4 = account not found
    assert "ExecutionError::User(4)" in src, (
        "Must revert with User(4) when account doesn't exist."
    )


def test_subscriber_vault_has_payment_error_codes():
    """SubscriberVault must have error codes for payment + lock failures."""
    src = (CONTRACTS_SRC / "subscriber_vault.rs").read_text()
    assert "ExecutionError::User(2)" in src, (
        "Must revert with User(2) when attached_value != initial_deposit."
    )
    assert "ExecutionError::User(3)" in src, (
        "Must revert with User(3) when withdraw amount > balance."
    )
    assert "ExecutionError::User(5)" in src, (
        "Must revert with User(5) when vault is still locked."
    )
