"""Unit tests — api/casper_rpc.py bytesrepr parser + Odra key derivation.

Verifies the on-chain state decoder WITHOUT touching the network:
  * bytesrepr round-trip for Finding + RiskScore + u64
  * u64 / String key encoders
  * Odra Var + Mapping dictionary-address derivation (matches the proven
    policy_reader.compute_dict_address pattern for Var, and extends it
    correctly for Mapping by appending the key's to_bytes())
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from api import casper_rpc  # noqa: E402


# ---------------------------------------------------------------------------
# bytesrepr encoders (the inverse of the parsers) — build known-good bytes
# ---------------------------------------------------------------------------
def enc_u64(v: int) -> bytes:
    return struct.pack("<Q", v)


def enc_u8(v: int) -> bytes:
    return bytes([v & 0xFF])


def enc_string(s: str) -> bytes:
    raw = s.encode("utf-8")
    return struct.pack("<I", len(raw)) + raw


def enc_finding(
    id_: int = 1,
    address: str = "casper1abc",
    risk_type: str = "whale_dump",
    severity: str = "CRITICAL",
    confidence: int = 91,
    description: str = "Large whale dump detected",
    rwa_enriched: bool = False,
    agent_model: str = "llama-3.3-70b-versatile",
    block_height: int = 1_500_000,
    timestamp: int = 1_750_000_000,
    tx_hash: str = "",
) -> bytes:
    return b"".join(
        [
            enc_u64(id_),
            enc_string(address),
            enc_string(risk_type),
            enc_string(severity),
            enc_u8(confidence),
            enc_string(description),
            enc_u8(1 if rwa_enriched else 0),
            enc_string(agent_model),
            enc_u64(block_height),
            enc_u64(timestamp),
            enc_string(tx_hash),
        ]
    )


def enc_risk_score(
    address: str = "casper1xyz",
    score: int = 87,
    risk_type: str = "whale_concentration",
    confidence: int = 92,
    last_updated: int = 1_500_000,
    finding_id: int = 1,
) -> bytes:
    return b"".join(
        [
            enc_string(address),
            enc_u8(score),
            enc_string(risk_type),
            enc_u8(confidence),
            enc_u64(last_updated),
            enc_u64(finding_id),
        ]
    )


# ===========================================================================
# parse_u64_bytes
# ===========================================================================
def test_parse_u64_bytes_roundtrip():
    assert casper_rpc.parse_u64_bytes(enc_u64(0)) == 0
    assert casper_rpc.parse_u64_bytes(enc_u64(42)) == 42
    assert casper_rpc.parse_u64_bytes(enc_u64(2**64 - 1)) == 2**64 - 1


def test_parse_u64_bytes_too_short_raises():
    with pytest.raises(ValueError):
        casper_rpc.parse_u64_bytes(b"\x01\x02\x03")


# ===========================================================================
# parse_finding_bytes
# ===========================================================================
def test_parse_finding_bytes_roundtrip():
    raw = enc_finding(
        id_=7,
        address="account-hash-abcdef",
        risk_type="flash_loan",
        severity="HIGH",
        confidence=78,
        description="Flash loan attack pattern detected",
        rwa_enriched=True,
        agent_model="llama-3.1-8b-instant",
        block_height=9_876_543,
        timestamp=1_751_111_111,
        tx_hash="deadbeef" * 16,
    )
    f = casper_rpc.parse_finding_bytes(raw)
    assert f["id"] == 7
    assert f["address"] == "account-hash-abcdef"
    assert f["risk_type"] == "flash_loan"
    assert f["severity"] == "HIGH"
    assert f["confidence"] == 78
    assert f["description"] == "Flash loan attack pattern detected"
    assert f["rwa_enriched"] is True
    assert f["agent_model"] == "llama-3.1-8b-instant"
    assert f["block_height"] == 9_876_543
    assert f["timestamp"] == 1_751_111_111
    assert f["tx_hash"] == "deadbeef" * 16
    assert f["source"] == "on-chain"


def test_parse_finding_bytes_empty_strings():
    raw = enc_finding(address="", description="", tx_hash="", agent_model="")
    f = casper_rpc.parse_finding_bytes(raw)
    assert f["address"] == ""
    assert f["description"] == ""
    assert f["tx_hash"] == ""
    assert f["agent_model"] == ""


def test_parse_finding_bytes_unicode_description():
    raw = enc_finding(description="Whale dump — 2.4M CSPR moved ✓")
    f = casper_rpc.parse_finding_bytes(raw)
    assert f["description"] == "Whale dump — 2.4M CSPR moved ✓"


def test_parse_finding_bytes_truncated_raises():
    # Cut the tail off so a String length prefix points past the buffer end.
    raw = enc_finding()[:-5]
    with pytest.raises(ValueError):
        casper_rpc.parse_finding_bytes(raw)


# ===========================================================================
# parse_risk_score_bytes
# ===========================================================================
def test_parse_risk_score_bytes_roundtrip():
    raw = enc_risk_score(
        address="account-hash-1234",
        score=65,
        risk_type="depeg",
        confidence=88,
        last_updated=1_234_567,
        finding_id=42,
    )
    rs = casper_rpc.parse_risk_score_bytes(raw)
    assert rs["address"] == "account-hash-1234"
    assert rs["score"] == 65
    assert rs["risk_type"] == "depeg"
    assert rs["confidence"] == 88
    assert rs["last_updated"] == 1_234_567
    assert rs["finding_id"] == 42
    assert rs["source"] == "on-chain"


def test_parse_risk_score_bytes_minimal():
    raw = enc_risk_score(address="a", score=0, risk_type="x", confidence=0, last_updated=0, finding_id=0)
    rs = casper_rpc.parse_risk_score_bytes(raw)
    assert rs["score"] == 0
    assert rs["finding_id"] == 0


# ===========================================================================
# Key encoders
# ===========================================================================
def test_encode_u64_key_is_8_bytes_le():
    assert casper_rpc.encode_u64_key(1) == b"\x01\x00\x00\x00\x00\x00\x00\x00"
    assert casper_rpc.encode_u64_key(256) == b"\x00\x01" + b"\x00" * 6
    assert len(casper_rpc.encode_u64_key(2**64 - 1)) == 8


def test_encode_string_key_is_u32_len_plus_utf8():
    assert casper_rpc.encode_string_key("") == b"\x00\x00\x00\x00"
    assert casper_rpc.encode_string_key("ab") == b"\x02\x00\x00\x00ab"
    # Unicode: UTF-8 byte count in the length prefix, not char count.
    assert casper_rpc.encode_string_key("✓") == b"\x03\x00\x00\x00" + "✓".encode("utf-8")


# ===========================================================================
# Odra dictionary-address derivation
# ===========================================================================
def test_compute_var_dict_address_matches_policy_reader_pattern():
    """The Var derivation must match the proven policy_reader algorithm
    (which successfully reads the on-chain RiskPolicyManager.current_policy)."""
    uref = bytes.fromhex("dca768b2" * 8)  # 32 bytes
    # Recompute using the exact policy_reader formula.
    import hashlib

    index_bytes = (2).to_bytes(4, "big")
    hashed = hashlib.blake2b(index_bytes, digest_size=32).digest()
    item_key = hashed.hex().encode("ascii")
    expected = hashlib.blake2b(uref + item_key, digest_size=32).digest().hex()

    assert casper_rpc.compute_var_dict_address(uref, 2) == expected


def test_compute_mapping_dict_address_differs_from_var():
    """A Mapping entry's address must differ from the bare Var address for
    the same field index (the key bytes are appended before hashing)."""
    uref = bytes(range(32))
    var_addr = casper_rpc.compute_var_dict_address(uref, 1)
    map_addr_empty_key = casper_rpc.compute_mapping_dict_address(uref, 1, casper_rpc.encode_u64_key(0))
    map_addr_5 = casper_rpc.compute_mapping_dict_address(uref, 1, casper_rpc.encode_u64_key(5))
    assert var_addr != map_addr_empty_key
    assert var_addr != map_addr_5
    assert map_addr_empty_key != map_addr_5  # different keys → different addresses


def test_compute_mapping_dict_address_deterministic():
    uref = bytes(range(32))
    a1 = casper_rpc.compute_mapping_dict_address(uref, 1, casper_rpc.encode_u64_key(42))
    a2 = casper_rpc.compute_mapping_dict_address(uref, 1, casper_rpc.encode_u64_key(42))
    assert a1 == a2
    assert len(a1) == 64  # 32-byte hex


def test_compute_mapping_dict_address_string_key():
    """RiskOracle uses Mapping<String, RiskScore> — verify the String key
    derivation produces a stable, distinct address."""
    uref = bytes(range(32))
    a = casper_rpc.compute_mapping_dict_address(uref, 1, casper_rpc.encode_string_key("account-hash-abc"))
    b = casper_rpc.compute_mapping_dict_address(uref, 1, casper_rpc.encode_string_key("account-hash-xyz"))
    assert a != b
    assert len(a) == 64


# ===========================================================================
# _decode_cl_value_list_u8
# ===========================================================================
def test_decode_cl_value_list_u8_roundtrip():
    inner = enc_finding(id_=3)
    # CLValue List<U8> bytes = u32 LE len ++ inner
    cl_bytes = struct.pack("<I", len(inner)) + inner
    cl_value = {"bytes": cl_bytes.hex(), "parsed": list(inner)}
    assert casper_rpc._decode_cl_value_list_u8(cl_value) == inner


def test_decode_cl_value_list_u8_falls_back_to_parsed():
    cl_value = {"bytes": "", "parsed": [1, 2, 3]}
    assert casper_rpc._decode_cl_value_list_u8(cl_value) == b"\x01\x02\x03"


def test_decode_cl_value_list_u8_empty():
    assert casper_rpc._decode_cl_value_list_u8({"bytes": ""}) == b""
    assert casper_rpc._decode_cl_value_list_u8({}) == b""


# ===========================================================================
# Field index constants
# ===========================================================================
def test_field_indices_match_contract_layout():
    """Odra reserves index 0 for the reentrancy guard; user fields start at 1.
    AuditTrail declares: findings, finding_count, owner.
    RiskOracle declares: scores, owner."""
    assert casper_rpc.AUDIT_TRAIL_FINDINGS_INDEX == 1
    assert casper_rpc.AUDIT_TRAIL_FINDING_COUNT_INDEX == 2
    assert casper_rpc.RISK_ORACLE_SCORES_INDEX == 1
