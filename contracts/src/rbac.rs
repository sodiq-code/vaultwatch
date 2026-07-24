//! RBAC — Role-Based Access Control for VaultWatch contracts.
//!
//! Replaces the legacy single-`owner` pattern with three separation-of-duty
//! roles, encoded as a bitmask so a single Casper account (`Address`) may hold
//! multiple roles at once:
//!
//! | Role     | Bit | Constant        | Purpose                                                 |
//! |----------|-----|-----------------|---------------------------------------------------------|
//! | OPERATOR | 0   | `ROLE_OPERATOR` | Day-to-day operational writes: record findings, log     |
//! |          |     |                 | alerts, update scores, deduct credits, record decisions.|
//! | ADMIN    | 1   | `ROLE_ADMIN`    | Economic parameters: set prices, upgrade risk policy,   |
//! |          |     |                 | backward-compat `transfer_ownership`.                   |
//! | PAUSER   | 2   | `ROLE_PAUSER`   | Emergency pause / unpause of mutable entry points.      |
//!
//! ## Bootstrap
//!
//! `init()` grants the deployer **all three roles** (`ROLE_ALL`) AND sets the
//! deployer as the `role_admin` (the only account that may `grant_role` /
//! `revoke_role` / `transfer_role_admin`). This preserves the old single-owner
//! ergonomics on day one — the deployer can do everything — while allowing
//! fine-grained delegation afterwards.
//!
//! ## Casper-native identity
//!
//! Roles are keyed by `Address` (a Casper account hash or contract package
//! hash). Authorization is enforced against the real on-chain caller via
//! `self.env().caller()`, never a free-form string — so a caller cannot
//! spoof another account's authority.
//!
//! ## Role manager (`role_admin`)
//!
//! Inspired by OpenZeppelin's `DEFAULT_ADMIN_ROLE`, `role_admin` is a *single*
//! account (not a bitmask role) that owns role management. It is the only
//! account that may grant/revoke roles or transfer the role-admin to a
//! successor. Keeping role management separate from the OPERATOR/ADMIN/PAUSER
//! bits means a compromised OPERATOR cannot elevate itself to ADMIN.
//!
//! ## Emergency pause
//!
//! Every mutable entry point calls `assert_not_paused()` after the role check.
//! `pause()` / `unpause()` are PAUSER-gated and intentionally NOT guarded by
//! `assert_not_paused()` — otherwise a paused contract could never be
//! unpaused. Read-only entry points (`get_*`) never check pause.
//!
//! ## Error codes
//!
//! RBAC errors use codes ≥ 100 so they never collide with the legacy
//! business-logic codes (1 = unauthorized-owner, 2 = amount-mismatch,
//! 3 = insufficient-balance, 4 = no-account, 5 = locked).

/// No roles held (anonymous caller).
pub const ROLE_NONE: u8 = 0;
/// OPERATOR — operational writes (record / log / update / deduct).
pub const ROLE_OPERATOR: u8 = 1 << 0;
/// ADMIN — economic parameters (set prices, upgrade policy, transfer_ownership).
pub const ROLE_ADMIN: u8 = 1 << 1;
/// PAUSER — emergency pause / unpause.
pub const ROLE_PAUSER: u8 = 1 << 2;
/// All roles — granted to the deployer at `init()`.
pub const ROLE_ALL: u8 = ROLE_OPERATOR | ROLE_ADMIN | ROLE_PAUSER;

/// A bitmask that is not a valid single role (used to sanity-check inputs).
pub const ROLE_ANY_VALID: u8 = ROLE_OPERATOR | ROLE_ADMIN | ROLE_PAUSER;

// ── RBAC error codes (offset from 100 to avoid legacy 1–5 collisions) ──

/// Caller lacks the required role (or is not the role_admin).
pub const ERR_UNAUTHORIZED: u16 = 100;
/// Contract is paused — mutable entry points revert.
pub const ERR_PAUSED: u16 = 101;
/// `grant_role` / `revoke_role` / `transfer_role_admin` to a zero / invalid
/// address.
pub const ERR_ZERO_ADDRESS: u16 = 102;
/// `grant_role` / `revoke_role` called with an invalid role bitmask.
pub const ERR_INVALID_ROLE: u16 = 103;

/// Returns `true` iff `roles` contains every bit set in `role`.
///
/// A caller holding `ROLE_ALL` therefore satisfies any individual role check.
/// `role == ROLE_NONE` is always satisfied (and should never be passed — it
/// would authorise anonymous callers).
#[inline]
pub fn has_role(roles: u8, role: u8) -> bool {
    if role == ROLE_NONE {
        return true;
    }
    (roles & role) == role
}

/// Returns `true` iff `role` is exactly one of the three defined single-role
/// bits, OR the composite `ROLE_ALL`. Used to reject nonsense bitmasks such as
/// `0b1000_0000` in `grant_role` / `revoke_role`.
#[inline]
pub fn is_valid_role(role: u8) -> bool {
    role == ROLE_ALL || (role != ROLE_NONE && (role & ROLE_ANY_VALID) == role && role.count_ones() <= 3)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn role_all_contains_every_role() {
        assert!(has_role(ROLE_ALL, ROLE_OPERATOR));
        assert!(has_role(ROLE_ALL, ROLE_ADMIN));
        assert!(has_role(ROLE_ALL, ROLE_PAUSER));
    }

    #[test]
    fn operator_only_lacks_admin_and_pauser() {
        assert!(has_role(ROLE_OPERATOR, ROLE_OPERATOR));
        assert!(!has_role(ROLE_OPERATOR, ROLE_ADMIN));
        assert!(!has_role(ROLE_OPERATOR, ROLE_PAUSER));
    }

    #[test]
    fn multi_role_membership() {
        let combo = ROLE_OPERATOR | ROLE_PAUSER;
        assert!(has_role(combo, ROLE_OPERATOR));
        assert!(has_role(combo, ROLE_PAUSER));
        assert!(!has_role(combo, ROLE_ADMIN));
    }

    #[test]
    fn role_none_is_always_authorized_and_invalid_as_input() {
        // has_role with ROLE_NONE returns true (no role requested) — callers
        // must never pass ROLE_NONE to assert_role.
        assert!(has_role(ROLE_ALL, ROLE_NONE));
        assert!(has_role(ROLE_NONE, ROLE_NONE));
        // But ROLE_NONE is NOT a valid role to grant/revoke.
        assert!(!is_valid_role(ROLE_NONE));
    }

    #[test]
    fn invalid_roles_rejected() {
        assert!(!is_valid_role(0b1000_0000));
        assert!(!is_valid_role(0b0000_1000));
        assert!(is_valid_role(ROLE_OPERATOR));
        assert!(is_valid_role(ROLE_ADMIN));
        assert!(is_valid_role(ROLE_PAUSER));
        assert!(is_valid_role(ROLE_ALL));
    }
}
