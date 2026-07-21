"""Integration tests — on-chain RiskPolicy reader (Fix B)

Verifies that ``agents.policy_reader.read_current_policy`` reads the REAL
on-chain ``RiskPolicyManager.current_policy`` value from the Casper testnet
via ``query_global_state``, with correct Odra storage-key derivation and
RiskPolicy bytesrepr parsing.

These tests hit the live testnet (read-only ``query_global_state`` calls —
no gas, no signing). They verify the actual deployed RiskPolicyManager
contract (hash ``1027cb2a...``) whose current policy was upgraded to v3
via the demo_upgrade_policy script.
"""

import hashlib
import struct

import pytest

from agents.policy_reader import (
    CURRENT_POLICY_FIELD_INDEX,
    DEFAULT_POLICY,
    RISK_POLICY_MANAGER_HASH,
    _decode_cl_value_list_u8,
    _get_state_uref_addr,
    compute_dict_address,
    make_policy_reader,
    parse_risk_policy_bytes,
    read_current_policy,
)


# ---------------------------------------------------------------------------
# Pure-function unit tests (no network)
# ---------------------------------------------------------------------------


def test_compute_dict_address_matches_odra_formula():
    """compute_dict_address must reproduce Odra's current_key + Casper's
    Key::dictionary address derivation.

    For a known state URef addr + field index 1, the output must match the
    on-chain dictionary address observed in the execution effects of a real
    get_current_version deploy (verified on testnet).
    """
    state_uref_addr = bytes.fromhex(
        "dca768b2e203f0019a96626d800a7c5c9b0658df56c861346298a61b2b0117bf"
    )
    # The on-chain current_policy dictionary address for RiskPolicyManager
    # (field index 1) — observed in the execution effects of deploy
    # 7d6c26c91d3311521cb9832934cec2e895651ce92c8381e07c7af00908d8ffdf.
    expected = "ef857c5ddcafeb0e3e98c8960068151a9dc8bef32de4115227517056e01db58b"
    actual = compute_dict_address(state_uref_addr, CURRENT_POLICY_FIELD_INDEX)
    assert actual == expected, (
        f"dict address mismatch: expected {expected}, got {actual}. "
        "Odra storage-key derivation is broken."
    )


def test_compute_dict_address_distinct_per_index():
    """Different field indices must produce different dictionary addresses."""
    state_uref_addr = bytes(32)
    addrs = {i: compute_dict_address(state_uref_addr, i) for i in range(5)}
    assert len(set(addrs.values())) == 5, "dictionary addresses collided across indices"


def test_parse_risk_policy_bytes_round_trip():
    """parse_risk_policy_bytes must correctly decode a serialised RiskPolicy
    with a legacy String ``updated_by`` (the currently-deployed v1 format)."""
    # Build a minimal RiskPolicy bytesrepr: version=2, thresholds, block, updated_by
    updated_by = b"admin"
    data = (
        struct.pack("<I", 2)  # version: u32
        + bytes([60, 80, 55, 35, 3, 90])  # 6 u8 thresholds
        + struct.pack("<Q", 1500000)  # updated_at_block: u64
        + struct.pack("<I", len(updated_by))  # String length
        + updated_by  # String bytes
    )
    policy = parse_risk_policy_bytes(data)
    assert policy["version"] == 2
    assert policy["min_confidence_threshold"] == 60
    assert policy["critical_score_threshold"] == 80
    assert policy["high_score_threshold"] == 55
    assert policy["medium_score_threshold"] == 35
    assert policy["max_retry_count"] == 3
    assert policy["safety_rejection_threshold"] == 90
    assert policy["updated_at_block"] == 1500000
    assert policy["updated_by"] == "admin"
    assert policy["source"] == "on-chain"


def test_parse_risk_policy_bytes_address_updated_by():
    """parse_risk_policy_bytes must decode the NEW Address-typed ``updated_by``
    (Casper Key: 1-byte tag + 32-byte hash) emitted by the updated Rust source.

    Tag 0 = Key::Account → ``account-hash-<64 hex>``.
    Tag 1 = Key::Hash     → ``hash-<64 hex>``.
    """
    account_hash_bytes = bytes.fromhex(
        "3b4ffcfb21411ced5fc1560c3f6ffed86f4885e5ea05cde49d90962a48a14d95"
    )
    # Address::Account → Key tag 0 + 32-byte account hash
    data = (
        struct.pack("<I", 5)  # version: u32
        + bytes([70, 85, 65, 45, 2, 88])  # 6 u8 thresholds
        + struct.pack("<Q", 2000000)  # updated_at_block: u64
        + bytes([0])  # Key tag 0 = Account
        + account_hash_bytes  # 32-byte AccountHash
    )
    policy = parse_risk_policy_bytes(data)
    assert policy["version"] == 5
    assert policy["min_confidence_threshold"] == 70
    assert policy["safety_rejection_threshold"] == 88
    assert policy["updated_at_block"] == 2000000
    assert policy["updated_by"] == "account-hash-" + account_hash_bytes.hex()
    assert policy["source"] == "on-chain"

    # Address::Contract → Key tag 1 + 32-byte package hash
    pkg_hash_bytes = bytes.fromhex(
        "7ba9daac84bebee8111c186588f21ebca35550b6cf1244e71768bd871938be6a"
    )
    data2 = (
        struct.pack("<I", 6)
        + bytes([70, 85, 65, 45, 2, 88])
        + struct.pack("<Q", 2000001)
        + bytes([1])  # Key tag 1 = Hash
        + pkg_hash_bytes
    )
    policy2 = parse_risk_policy_bytes(data2)
    assert policy2["version"] == 6
    assert policy2["updated_by"] == "hash-" + pkg_hash_bytes.hex()


def test_parse_risk_policy_bytes_too_short_raises():
    """A byte string shorter than the 18-byte minimum must raise ValueError."""
    with pytest.raises(ValueError):
        parse_risk_policy_bytes(b"\x01\x02\x03")


def test_decode_cl_value_list_u8_from_bytes():
    """_decode_cl_value_list_u8 must strip the u32 LE length prefix."""
    inner = bytes([1, 2, 3, 4, 5])
    cl_value = {"bytes": struct.pack("<I", len(inner)).hex() + inner.hex()}
    assert _decode_cl_value_list_u8(cl_value) == inner


def test_decode_cl_value_list_u8_from_parsed():
    """_decode_cl_value_list_u8 falls back to the parsed list when bytes absent."""
    cl_value = {"parsed": [10, 20, 30], "bytes": ""}
    assert _decode_cl_value_list_u8(cl_value) == bytes([10, 20, 30])


def test_decode_cl_value_list_u8_empty():
    """_decode_cl_value_list_u8 returns empty bytes for an empty CLValue."""
    assert _decode_cl_value_list_u8({}) == b""
    assert _decode_cl_value_list_u8({"bytes": "", "parsed": None}) == b""


def test_default_policy_has_required_keys():
    """DEFAULT_POLICY must contain every field the agents consume."""
    required = {
        "version",
        "min_confidence_threshold",
        "critical_score_threshold",
        "high_score_threshold",
        "medium_score_threshold",
        "max_retry_count",
        "safety_rejection_threshold",
        "updated_at_block",
        "updated_by",
        "source",
    }
    assert required.issubset(DEFAULT_POLICY.keys())
    assert DEFAULT_POLICY["source"] == "fallback"
    assert DEFAULT_POLICY["min_confidence_threshold"] == 75
    assert DEFAULT_POLICY["max_retry_count"] == 2


# ---------------------------------------------------------------------------
# Live testnet read tests (network required — marked integration)
# ---------------------------------------------------------------------------


def test_get_state_uref_addr_finds_state_key():
    """_get_state_uref_addr must find the 'state' named key on RiskPolicyManager."""
    uref_addr = _get_state_uref_addr(RISK_POLICY_MANAGER_HASH)
    assert isinstance(uref_addr, bytes)
    assert len(uref_addr) == 32, f"state URef addr must be 32 bytes, got {len(uref_addr)}"


@pytest.mark.asyncio
async def test_read_current_policy_returns_on_chain_data():
    """read_current_policy must return the REAL on-chain RiskPolicy (not the default)."""
    policy = await read_current_policy()
    # Must be the on-chain policy, not the fallback
    assert policy["source"] == "on-chain", (
        f"expected on-chain policy, got source={policy['source']}. "
        "Either the testnet is unreachable or the storage-key derivation is broken."
    )
    # The on-chain policy was upgraded to v3 (via demo_upgrade_policy).
    assert policy["version"] >= 1, f"version must be >= 1, got {policy['version']}"
    # Sanity-check threshold ranges
    assert 0 <= policy["min_confidence_threshold"] <= 100
    assert 0 <= policy["safety_rejection_threshold"] <= 100
    assert 0 <= policy["max_retry_count"] <= 10


@pytest.mark.asyncio
async def test_make_policy_reader_callable_returns_on_chain_policy():
    """make_policy_reader must return an async callable that reads the live policy."""
    reader = make_policy_reader()
    import inspect

    assert inspect.iscoroutinefunction(reader), "policy_reader must be async"
    policy = await reader()
    assert policy["source"] == "on-chain"
    assert "min_confidence_threshold" in policy
    assert "max_retry_count" in policy


@pytest.mark.asyncio
async def test_policy_reader_falls_back_on_bad_contract_hash():
    """read_current_policy must return DEFAULT_POLICY when the contract hash is bogus."""
    policy = await read_current_policy("00" * 32)
    assert policy["source"] == "fallback"
    assert policy == DEFAULT_POLICY


# ---------------------------------------------------------------------------
# Odra storage-key derivation reference (self-documenting)
# ---------------------------------------------------------------------------


def test_odra_key_derivation_reference():
    """Document the Odra 2.9.0 storage-key derivation formula in code.

    For a Var<T> at field index i (legacy encoding, i ≤ 15):
      index_bytes = u32::to_be_bytes(i)              # 4 bytes, big-endian
      hashed      = blake2b(index_bytes)             # 32 raw bytes
      item_key    = hex(hashed)                      # 64 ASCII chars (UTF-8)
      dict_addr   = blake2b(uref.addr(32) ++ item_key_bytes(64))  # 32 bytes

    This test re-derives the address independently to ensure
    compute_dict_address matches the reference formula.
    """
    state_uref_addr = bytes.fromhex(
        "dca768b2e203f0019a96626d800a7c5c9b0658df56c861346298a61b2b0117bf"
    )
    idx = CURRENT_POLICY_FIELD_INDEX
    # Reference formula (hand-rolled)
    index_bytes = idx.to_bytes(4, "big")
    hashed = hashlib.blake2b(index_bytes, digest_size=32).digest()
    item_key = hashed.hex().encode("ascii")
    expected = hashlib.blake2b(state_uref_addr + item_key, digest_size=32).hexdigest()
    # Must match compute_dict_address
    assert compute_dict_address(state_uref_addr, idx) == expected
