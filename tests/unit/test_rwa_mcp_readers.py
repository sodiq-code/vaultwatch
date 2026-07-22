"""Unit tests for vaultwatch_rwa_mcp.readers — bytesrepr parsers + key derivation.

No network access. These verify the Odra storage-key derivation and the
bytesrepr decoders for every contract value type, using hand-constructed
byte sequences (and round-trip checks via the encoders).
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

# Make the vaultwatch repo root importable.
_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))

from vaultwatch_rwa_mcp import readers as R
from vaultwatch_rwa_mcp import contracts as C


# ---------------------------------------------------------------------------
# Key-derivation primitives
# ---------------------------------------------------------------------------
class TestKeyDerivation:
    """Verify the Odra 2.9.0 blake2b key derivation matches the spec."""

    def test_var_dict_address_is_64_hex_chars(self):
        uref = bytes.fromhex("dca768b2" + "11" * 28)  # 32-byte fake uref addr
        addr = R._var_dict_address(uref, 2)  # AuditTrail.finding_count index
        assert len(addr) == 64
        int(addr, 16)  # valid hex

    def test_mapping_dict_address_differs_from_var(self):
        uref = bytes(range(32))
        var_addr = R._var_dict_address(uref, 1)
        map_addr = R._mapping_dict_address(uref, 1, R._enc_u64(5))
        assert var_addr != map_addr

    def test_mapping_address_depends_on_key(self):
        uref = bytes(range(32))
        a = R._mapping_dict_address(uref, 1, R._enc_u64(1))
        b = R._mapping_dict_address(uref, 1, R._enc_u64(2))
        assert a != b  # different keys → different addresses

    def test_var_address_matches_reference_implementation(self):
        """Cross-check against the proven api/casper_rpc.py implementation."""
        from api import casper_rpc as ref

        uref = bytes(range(32))
        for idx in (1, 2, 3):
            assert R._var_dict_address(uref, idx) == ref.compute_var_dict_address(uref, idx)

    def test_mapping_address_matches_reference_implementation(self):
        from api import casper_rpc as ref

        uref = bytes(range(32))
        for key in (b"", R._enc_u64(42), R._enc_string("account-hash-abc")):
            assert R._mapping_dict_address(uref, 1, key) == ref.compute_mapping_dict_address(uref, 1, key)


# ---------------------------------------------------------------------------
# Key encoders
# ---------------------------------------------------------------------------
class TestKeyEncoders:
    def test_enc_u64_is_8_bytes_little_endian(self):
        assert R._enc_u64(1) == struct.pack("<Q", 1)
        assert R._enc_u64(0) == b"\x00" * 8
        assert len(R._enc_u64(2**64 - 1)) == 8

    def test_enc_u32_is_4_bytes_little_endian(self):
        assert R._enc_u32(1) == struct.pack("<I", 1)
        assert len(R._enc_u32(0)) == 4

    def test_enc_string_is_length_prefixed_utf8(self):
        s = "account-hash-deadbeef"
        enc = R._enc_string(s)
        assert enc[:4] == struct.pack("<I", len(s.encode()))
        assert enc[4:] == s.encode()


# ---------------------------------------------------------------------------
# bytesrepr primitive decoders
# ---------------------------------------------------------------------------
class TestPrimitiveDecoders:
    def test_rd_u8(self):
        assert R._rd_u8(b"\x05", 0) == (5, 1)
        assert R._rd_u8(b"\xff", 0) == (255, 1)

    def test_rd_u8_past_end_raises(self):
        with pytest.raises(ValueError):
            R._rd_u8(b"", 0)

    def test_rd_u64_little_endian(self):
        assert R._rd_u64(struct.pack("<Q", 123456789), 0) == (123456789, 8)

    def test_rd_bool(self):
        assert R._rd_bool(b"\x01", 0) == (True, 1)
        assert R._rd_bool(b"\x00", 0) == (False, 1)

    def test_rd_string(self):
        raw = struct.pack("<I", 5) + b"hello"
        assert R._rd_string(raw, 0) == ("hello", 9)

    def test_rd_u512_zero(self):
        # U512(0) = length 0
        data = struct.pack("<I", 0)
        assert R._rd_u512(data, 0) == (0, 4)

    def test_rd_u512_small(self):
        # U512(1000) = length 1 + 0xe8 0x03 (little-endian)
        data = struct.pack("<I", 2) + (1000).to_bytes(2, "little")
        assert R._rd_u512(data, 0) == (1000, 6)

    def test_rd_u512_large(self):
        # 5 CSPR = 5_000_000_000 motes — fits in 5 bytes
        motes = 5_000_000_000
        mag = motes.to_bytes((motes.bit_length() + 7) // 8, "little")
        data = struct.pack("<I", len(mag)) + mag
        assert R._rd_u512(data, 0) == (motes, 4 + len(mag))


# ---------------------------------------------------------------------------
# Struct parsers — round-trip via hand-built byte sequences
# ---------------------------------------------------------------------------
def _wrap_as_list_u8(inner: bytes) -> bytes:
    """Wrap inner bytes as the Odra List<U8> CLValue payload (u32 len ++ bytes)."""
    return struct.pack("<I", len(inner)) + inner


class TestFindingParser:
    def test_parse_minimal_finding(self):
        # Build a Finding in declaration order:
        # id: u64, address: String, risk_type: String, severity: String,
        # confidence: u8, description: String, rwa_enriched: bool,
        # agent_model: String, block_height: u64, timestamp: u64, tx_hash: String
        inner = (
            struct.pack("<Q", 1)                                   # id
            + R._enc_string("account-hash-abc")                    # address
            + R._enc_string("wash_trading")                        # risk_type
            + R._enc_string("HIGH")                                # severity
            + bytes([88])                                          # confidence
            + R._enc_string("suspicious volume pattern")           # description
            + bytes([1])                                           # rwa_enriched (true)
            + R._enc_string("AnomalyAgent")                        # agent_model
            + struct.pack("<Q", 5000)                              # block_height
            + struct.pack("<Q", 1700000000)                        # timestamp
            + R._enc_string("deadbeef")                            # tx_hash
        )
        f = R.parse_finding_bytes(inner)
        assert f["id"] == 1
        assert f["address"] == "account-hash-abc"
        assert f["risk_type"] == "wash_trading"
        assert f["severity"] == "HIGH"
        assert f["confidence"] == 88
        assert f["description"] == "suspicious volume pattern"
        assert f["rwa_enriched"] is True
        assert f["agent_model"] == "AnomalyAgent"
        assert f["block_height"] == 5000
        assert f["timestamp"] == 1700000000
        assert f["tx_hash"] == "deadbeef"
        assert f["source"] == "on-chain"


class TestRiskScoreParser:
    def test_parse_risk_score(self):
        inner = (
            R._enc_string("account-hash-xyz")   # address
            + bytes([72])                        # score
            + R._enc_string("liquidity")         # risk_type
            + bytes([90])                        # confidence
            + struct.pack("<Q", 1700000000)      # last_updated
            + struct.pack("<Q", 7)               # finding_id
        )
        rs = R.parse_risk_score_bytes(inner)
        assert rs["address"] == "account-hash-xyz"
        assert rs["score"] == 72
        assert rs["risk_type"] == "liquidity"
        assert rs["confidence"] == 90
        assert rs["last_updated"] == 1700000000
        assert rs["finding_id"] == 7
        assert rs["source"] == "on-chain"


class TestAlertRecordParser:
    def test_parse_alert_with_account_address(self):
        # subscriber_address: Address::Account = tag 0 + 32-byte hash
        acct_hash = bytes.fromhex("0d" + "eb" * 31)  # 32 bytes
        inner = (
            struct.pack("<Q", 42)                            # log_id
            + bytes([0]) + acct_hash                          # subscriber_address (Account)
            + struct.pack("<Q", 9)                            # finding_id
            + R._enc_string("CRITICAL")                       # severity
            + R._enc_string("price_crash")                    # risk_type
            + struct.pack("<Q", 4100)                         # block_height
            + struct.pack("<Q", 1700000001)                   # timestamp
            + bytes([1])                                      # delivered (true)
        )
        ar = R.parse_alert_record_bytes(inner)
        assert ar["log_id"] == 42
        assert ar["subscriber_address"] == f"account-hash-{acct_hash.hex()}"
        assert ar["finding_id"] == 9
        assert ar["severity"] == "CRITICAL"
        assert ar["risk_type"] == "price_crash"
        assert ar["delivered"] is True
        assert ar["source"] == "on-chain"

    def test_parse_alert_with_hash_address(self):
        # subscriber_address: Address::Hash = tag 1 + 32-byte hash
        h = bytes.fromhex("ab" * 32)
        inner = (
            struct.pack("<Q", 1)
            + bytes([1]) + h
            + struct.pack("<Q", 1)
            + R._enc_string("LOW")
            + R._enc_string("oracle_drift")
            + struct.pack("<Q", 100)
            + struct.pack("<Q", 1700000002)
            + bytes([0])
        )
        ar = R.parse_alert_record_bytes(inner)
        assert ar["subscriber_address"] == f"hash-{h.hex()}"
        assert ar["delivered"] is False


class TestSubscriberParser:
    def test_parse_subscriber(self):
        inner = (
            R._enc_string("account-hash-sub")      # address
            + R._enc_string("https://hook.x/wh")    # webhook_url
            + R._enc_string("HIGH")                 # min_severity
            + bytes([1])                            # active
            + struct.pack("<Q", 1700000003)         # registered_at
            + struct.pack("<Q", 3)                  # alert_count
        )
        sub = R.parse_subscriber_bytes(inner)
        assert sub["address"] == "account-hash-sub"
        assert sub["webhook_url"] == "https://hook.x/wh"
        assert sub["min_severity"] == "HIGH"
        assert sub["active"] is True
        assert sub["registered_at"] == 1700000003
        assert sub["alert_count"] == 3


class TestAgentMetricsParser:
    def test_parse_metrics(self):
        inner = (
            R._enc_string("AnomalyAgent")       # agent_name
            + struct.pack("<Q", 100)             # total_decisions
            + struct.pack("<Q", 5)               # corrections_applied
            + struct.pack("<Q", 2)               # safety_rejections
            + bytes([87])                        # avg_confidence
            + struct.pack("<Q", 80)              # high_confidence_count
            + struct.pack("<Q", 20)              # low_confidence_count
            + struct.pack("<Q", 4500)            # last_updated_block
            + bytes([75])                        # trust_score
        )
        m = R.parse_agent_metrics_bytes(inner)
        assert m["agent_name"] == "AnomalyAgent"
        assert m["total_decisions"] == 100
        assert m["corrections_applied"] == 5
        assert m["safety_rejections"] == 2
        assert m["avg_confidence"] == 87
        assert m["high_confidence_count"] == 80
        assert m["low_confidence_count"] == 20
        assert m["last_updated_block"] == 4500
        assert m["trust_score"] == 75


class TestCreditAccountParser:
    def test_parse_credit_account(self):
        motes = 5_000_000_000
        mag = motes.to_bytes(5, "little")
        inner = (
            R._enc_string("account-hash-cred")              # owner
            + struct.pack("<I", len(mag)) + mag              # balance
            + struct.pack("<I", len(mag)) + mag              # total_deposited
            + struct.pack("<I", 1) + (1).to_bytes(1, "little")  # total_spent
            + struct.pack("<Q", 42)                          # query_count
        )
        acct = R.parse_credit_account_bytes(inner)
        assert acct["owner"] == "account-hash-cred"
        assert acct["balance"] == motes
        assert acct["total_deposited"] == motes
        assert acct["total_spent"] == 1
        assert acct["query_count"] == 42


class TestVaultAccountParser:
    def test_parse_vault_account(self):
        deposit = 10_000_000_000
        mag = deposit.to_bytes(5, "little")
        zero = b""
        inner = (
            R._enc_string("account-hash-vault")              # owner_address
            + struct.pack("<I", len(mag)) + mag              # escrowed_balance
            + struct.pack("<Q", 1000)                         # locked_until_block
            + bytes([1])                                      # auto_renew
            + struct.pack("<I", len(mag)) + mag              # monthly_spend_limit
            + struct.pack("<I", 1) + (5).to_bytes(1, "little")  # current_period_spent
            + struct.pack("<I", len(mag)) + mag              # total_deposits
            + struct.pack("<I", len(zero)) + zero            # total_withdrawals (0)
            + struct.pack("<Q", 500)                         # created_at_block
        )
        va = R.parse_vault_account_bytes(inner)
        assert va["owner_address"] == "account-hash-vault"
        assert va["escrowed_balance"] == deposit
        assert va["locked_until_block"] == 1000
        assert va["auto_renew"] is True
        assert va["monthly_spend_limit"] == deposit
        assert va["current_period_spent"] == 5
        assert va["total_deposits"] == deposit
        assert va["total_withdrawals"] == 0
        assert va["created_at_block"] == 500


class TestRiskPolicyParser:
    def test_parse_policy_with_string_updated_by(self):
        # v1 deployed contract: updated_by is a String label
        label = "admin"
        inner = (
            struct.pack("<I", 1)                 # version (u32)
            + bytes([75])                         # min_confidence_threshold
            + bytes([80])                         # critical_score_threshold
            + bytes([60])                         # high_score_threshold
            + bytes([40])                         # medium_score_threshold
            + bytes([2])                          # max_retry_count
            + bytes([80])                         # safety_rejection_threshold
            + struct.pack("<Q", 4000)             # updated_at_block
            + R._enc_string(label)                # updated_by (String)
        )
        p = R.parse_risk_policy_bytes(inner)
        assert p["version"] == 1
        assert p["min_confidence_threshold"] == 75
        assert p["critical_score_threshold"] == 80
        assert p["high_score_threshold"] == 60
        assert p["medium_score_threshold"] == 40
        assert p["max_retry_count"] == 2
        assert p["safety_rejection_threshold"] == 80
        assert p["updated_at_block"] == 4000
        assert p["updated_by"] == "admin"
        assert p["source"] == "on-chain"

    def test_parse_policy_with_account_address_updated_by(self):
        # A redeployed contract may store updated_by as Address::Account
        acct = bytes.fromhex("01" + "23" * 31)  # 32 bytes
        inner = (
            struct.pack("<I", 2)
            + bytes([80]) + bytes([85]) + bytes([65]) + bytes([45])
            + bytes([3]) + bytes([90])
            + struct.pack("<Q", 5000)
            + bytes([0]) + acct  # Address::Account (tag 0)
        )
        p = R.parse_risk_policy_bytes(inner)
        assert p["version"] == 2
        assert p["updated_by"] == f"account-hash-{acct.hex()}"
        assert p["min_confidence_threshold"] == 80

    def test_parse_policy_too_short_raises(self):
        with pytest.raises(ValueError):
            R.parse_risk_policy_bytes(b"\x00\x00\x00\x01")


# ---------------------------------------------------------------------------
# CLValue list-u8 wrapper
# ---------------------------------------------------------------------------
class TestDecodeListU8:
    def test_decode_from_bytes_hex(self):
        inner = b"hello"
        cl = {"bytes": _wrap_as_list_u8(inner).hex()}
        assert R._decode_list_u8(cl) == inner

    def test_decode_from_parsed_fallback(self):
        cl = {"bytes": "", "parsed": [1, 2, 3]}
        assert R._decode_list_u8(cl) == bytes([1, 2, 3])

    def test_decode_empty(self):
        assert R._decode_list_u8({}) == b""


# ---------------------------------------------------------------------------
# Contract registry sanity
# ---------------------------------------------------------------------------
class TestContractRegistry:
    def test_all_8_contracts_present(self):
        expected = {
            "AuditTrail", "RiskOracle", "SentinelCredit", "SentinelRegistry",
            "SentinelAlertLog", "AgentBehaviorIndex", "RiskPolicyManager",
            "SubscriberVault",
        }
        assert set(C.CONTRACTS.keys()) == expected

    def test_all_hashes_are_64_hex(self):
        for name, h in C.CONTRACT_HASHES.items():
            assert len(h) == 64, f"{name} hash not 64 chars: {len(h)}"
            int(h, 16)  # valid hex

    def test_all_package_hashes_prefixed(self):
        for name, h in C.CONTRACT_PACKAGE_HASHES.items():
            assert h.startswith("hash-"), f"{name} package hash missing prefix"
            assert len(h) == 69  # "hash-" + 64

    def test_field_indices_cover_core_fields(self):
        # Every contract must at least have roles + role_admin + paused
        for name, fields in C.FIELD_INDICES.items():
            assert "roles" in fields, f"{name} missing roles index"
            assert "role_admin" in fields, f"{name} missing role_admin index"
            assert "paused" in fields, f"{name} missing paused index"

    def test_get_contract_hash_env_override(self, monkeypatch):
        monkeypatch.setenv("AUDITTRAIL_HASH", "ab" * 32)
        assert C.get_contract_hash("AuditTrail") == "ab" * 32

    def test_list_contracts_is_serialisable(self):
        import json
        data = C.list_contracts()
        # Must round-trip through JSON (the MCP resource returns JSON).
        json.dumps(data)
        assert len(data) == 8
        assert data[0]["name"] in C.CONTRACTS
