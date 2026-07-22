"""Odra-aware on-chain readers for vaultwatch-rwa-mcp.

Reads live state from all 8 RWA / risk contracts on Casper testnet using
**free** ``query_global_state`` JSON-RPC calls (no gas, no signing).

Storage model
-------------
Every Odra 2.9.0 contract stores its data inside a single Casper dictionary
seeded by the contract's ``state`` URef (a named key). Field addresses are
derived via blake2b:

  Var<T> at index i:
      index_bytes = be32(i)
      item_key    = blake2b(index_bytes)            # 32 bytes, hex-encoded
      dict_addr   = blake2b(state_uref ++ item_key) # 32 bytes

  Mapping<K,V> at index j, key k:
      index_bytes = be32(j)
      mapping_data = bytesrepr(k)                    # K's to_bytes()
      item_key    = blake2b(index_bytes ++ mapping_data)
      dict_addr   = blake2b(state_uref ++ item_key)

Every stored value is wrapped as ``List<U8>`` (a Vec<u8> CLValue), so the
``bytes`` field of the returned CLValue is ``u32 LE length ++ struct bytes``.

This module is self-contained (stdlib + the local ``contracts`` registry) so
the MCP package can be published + used independently of the rest of the
VaultWatch codebase.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import struct
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from . import contracts as C

logger = logging.getLogger("vaultwatch_rwa_mcp.readers")

__all__ = [
    "reset_caches",
    "read_u64_var",
    "read_u512_var",
    "read_bool_var",
    "read_finding",
    "read_finding_count",
    "read_recent_findings",
    "read_risk_score",
    "read_current_policy",
    "read_policy_version",
    "read_current_policy_version",
    "read_subscriber",
    "read_subscriber_count",
    "read_alert_log",
    "read_alert_log_count",
    "read_credit_account",
    "read_credit_balance",
    "read_credit_prices",
    "read_total_revenue",
    "read_vault_account",
    "read_vault_balance",
    "read_total_locked",
    "read_agent_metrics",
    "read_agent_trust_score",
    "read_agent_count",
    "query_contract",
    "query_contract_package",
    "get_block_height",
    "parse_finding_bytes",
    "parse_risk_score_bytes",
    "parse_alert_record_bytes",
    "parse_subscriber_bytes",
    "parse_agent_metrics_bytes",
    "parse_credit_account_bytes",
    "parse_vault_account_bytes",
    "parse_risk_policy_bytes",
]


# ---------------------------------------------------------------------------
# Low-level JSON-RPC (stdlib urllib — no extra deps)
# ---------------------------------------------------------------------------
_CACHE_TTL = 16.0  # Casper testnet block time
_state_root_cache: Dict[str, Any] = {"value": None, "expires_at": 0.0}
_state_uref_cache: Dict[str, Any] = {}


def _rpc(method: str, params: list, rpc_url: str = C.DEFAULT_RPC_URL) -> Dict[str, Any]:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(rpc_url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    return data


async def _async_rpc(method: str, params: list, rpc_url: str = C.DEFAULT_RPC_URL) -> Dict[str, Any]:
    return await asyncio.to_thread(_rpc, method, params, rpc_url)


def _get_state_root_hash(rpc_url: str = C.DEFAULT_RPC_URL) -> str:
    now = time.time()
    if _state_root_cache["value"] is not None and _state_root_cache["expires_at"] > now:
        return _state_root_cache["value"]
    r = _rpc("chain_get_state_root_hash", [], rpc_url)
    srh = r.get("result", {}).get("state_root_hash")
    if not srh:
        raise RuntimeError(f"no state root hash in response: {r}")
    _state_root_cache["value"] = srh
    _state_root_cache["expires_at"] = now + _CACHE_TTL
    return srh


def _get_state_uref_addr(contract_hash: str, rpc_url: str = C.DEFAULT_RPC_URL) -> bytes:
    now = time.time()
    cached = _state_uref_cache.get(contract_hash)
    if cached is not None and cached["expires_at"] > now:
        return cached["addr"]
    srh = _get_state_root_hash(rpc_url)
    r = _rpc("query_global_state", [{"StateRootHash": srh}, f"hash-{contract_hash}", []], rpc_url)
    named_keys = r.get("result", {}).get("stored_value", {}).get("Contract", {}).get("named_keys", [])
    for nk in named_keys:
        if nk.get("name") == "state":
            uref_str = nk["key"]  # "uref-<64hex>-007"
            addr = bytes.fromhex(uref_str.split("-")[1])
            _state_uref_cache[contract_hash] = {"addr": addr, "expires_at": now + _CACHE_TTL}
            return addr
    raise RuntimeError(f"no 'state' named key on contract {contract_hash}")


# ---------------------------------------------------------------------------
# Odra key derivation
# ---------------------------------------------------------------------------
def _var_dict_address(state_uref: bytes, field_index: int) -> str:
    index_bytes = field_index.to_bytes(4, "big")
    item_key = hashlib.blake2b(index_bytes, digest_size=32).hexdigest().encode("ascii")
    return hashlib.blake2b(state_uref + item_key, digest_size=32).hexdigest()


def _mapping_dict_address(state_uref: bytes, field_index: int, key_bytes: bytes) -> str:
    index_bytes = field_index.to_bytes(4, "big")
    item_key = hashlib.blake2b(index_bytes + key_bytes, digest_size=32).hexdigest().encode("ascii")
    return hashlib.blake2b(state_uref + item_key, digest_size=32).hexdigest()


# ---------------------------------------------------------------------------
# bytesrepr key encoders
# ---------------------------------------------------------------------------
def _enc_u64(value: int) -> bytes:
    return struct.pack("<Q", int(value))


def _enc_u32(value: int) -> bytes:
    return struct.pack("<I", int(value))


def _enc_string(value: str) -> bytes:
    raw = value.encode("utf-8")
    return struct.pack("<I", len(raw)) + raw


# ---------------------------------------------------------------------------
# bytesrepr value decoders
# ---------------------------------------------------------------------------
def _decode_list_u8(cl_value: Dict[str, Any]) -> bytes:
    raw_hex = cl_value.get("bytes", "")
    if not raw_hex:
        parsed = cl_value.get("parsed") or []
        return bytes(parsed)
    raw = bytes.fromhex(raw_hex)
    if len(raw) < 4:
        return b""
    length = struct.unpack_from("<I", raw, 0)[0]
    return raw[4 : 4 + length]


def _rd_u8(data: bytes, off: int) -> Tuple[int, int]:
    if off + 1 > len(data):
        raise ValueError(f"u8 read past end at {off}")
    return data[off], off + 1


def _rd_bool(data: bytes, off: int) -> Tuple[bool, int]:
    v, off = _rd_u8(data, off)
    return bool(v), off


def _rd_u32(data: bytes, off: int) -> Tuple[int, int]:
    if off + 4 > len(data):
        raise ValueError(f"u32 read past end at {off}")
    return struct.unpack_from("<I", data, off)[0], off + 4


def _rd_u64(data: bytes, off: int) -> Tuple[int, int]:
    if off + 8 > len(data):
        raise ValueError(f"u64 read past end at {off}")
    return struct.unpack_from("<Q", data, off)[0], off + 8


def _rd_string(data: bytes, off: int) -> Tuple[str, int]:
    if off + 4 > len(data):
        raise ValueError(f"String length read past end at {off}")
    length = struct.unpack_from("<I", data, off)[0]
    off += 4
    if off + length > len(data):
        raise ValueError(f"String body read past end: need {length} at {off}, have {len(data)}")
    return data[off : off + length].decode("utf-8", errors="replace"), off + length


def _rd_u512(data: bytes, off: int) -> Tuple[int, int]:
    """U512 bytesrepr = u32 LE length + little-endian magnitude bytes."""
    if off + 4 > len(data):
        raise ValueError(f"U512 length read past end at {off}")
    length = struct.unpack_from("<I", data, off)[0]
    off += 4
    if off + length > len(data):
        raise ValueError(f"U512 body read past end: need {length} at {off}, have {len(data)}")
    magnitude = data[off : off + length]
    off += length
    # little-endian magnitude → int
    return int.from_bytes(magnitude, "little", signed=False), off


# Casper Key tags for the Odra Address type
_KEY_TAG_ACCOUNT = 0
_KEY_TAG_HASH = 1
_KEY_TAG_UREF = 2
_KEY_PAYLOAD_LEN = 32


def _rd_address(data: bytes, off: int) -> Tuple[str, int]:
    """Read an Odra ``Address`` (Casper Key): 1-byte tag + payload.

    Returns a formatted string:
      tag 0 (Account) → ``account-hash-<64 hex>`` (33 bytes)
      tag 1 (Hash)    → ``hash-<64 hex>``         (33 bytes)
      tag 2 (URef)    → ``uref-<64 hex>-<access>`` (34 bytes)
    Falls back to a hex string for unknown tags.
    """
    tag, off = _rd_u8(data, off)
    if tag == _KEY_TAG_ACCOUNT:
        if off + _KEY_PAYLOAD_LEN > len(data):
            raise ValueError("Address::Account payload past end")
        h = data[off : off + _KEY_PAYLOAD_LEN].hex()
        off += _KEY_PAYLOAD_LEN
        return f"account-hash-{h}", off
    if tag == _KEY_TAG_HASH:
        if off + _KEY_PAYLOAD_LEN > len(data):
            raise ValueError("Address::Hash payload past end")
        h = data[off : off + _KEY_PAYLOAD_LEN].hex()
        off += _KEY_PAYLOAD_LEN
        return f"hash-{h}", off
    if tag == _KEY_TAG_UREF:
        if off + _KEY_PAYLOAD_LEN + 1 > len(data):
            raise ValueError("Address::URef payload past end")
        h = data[off : off + _KEY_PAYLOAD_LEN].hex()
        access = data[off + _KEY_PAYLOAD_LEN]
        off += _KEY_PAYLOAD_LEN + 1
        return f"uref-{h}-{access:03d}", off
    # Unknown tag — best-effort
    return f"<unknown-key-tag-{tag}>", off


# ---------------------------------------------------------------------------
# Struct parsers (declaration order from contracts/src/*.rs)
# ---------------------------------------------------------------------------
def parse_finding_bytes(data: bytes) -> Dict[str, Any]:
    """Finding { id: u64, address: String, risk_type: String, severity: String,
    confidence: u8, description: String, rwa_enriched: bool, agent_model: String,
    block_height: u64, timestamp: u64, tx_hash: String }"""
    off = 0
    id_, off = _rd_u64(data, off)
    address, off = _rd_string(data, off)
    risk_type, off = _rd_string(data, off)
    severity, off = _rd_string(data, off)
    confidence, off = _rd_u8(data, off)
    description, off = _rd_string(data, off)
    rwa_enriched, off = _rd_bool(data, off)
    agent_model, off = _rd_string(data, off)
    block_height, off = _rd_u64(data, off)
    timestamp, off = _rd_u64(data, off)
    tx_hash, off = _rd_string(data, off)
    return {
        "id": id_, "address": address, "risk_type": risk_type, "severity": severity,
        "confidence": confidence, "description": description, "rwa_enriched": rwa_enriched,
        "agent_model": agent_model, "block_height": block_height, "timestamp": timestamp,
        "tx_hash": tx_hash, "source": "on-chain",
    }


def parse_risk_score_bytes(data: bytes) -> Dict[str, Any]:
    """RiskScore { address: String, score: u8, risk_type: String, confidence: u8,
    last_updated: u64, finding_id: u64 }"""
    off = 0
    address, off = _rd_string(data, off)
    score, off = _rd_u8(data, off)
    risk_type, off = _rd_string(data, off)
    confidence, off = _rd_u8(data, off)
    last_updated, off = _rd_u64(data, off)
    finding_id, off = _rd_u64(data, off)
    return {
        "address": address, "score": score, "risk_type": risk_type,
        "confidence": confidence, "last_updated": last_updated,
        "finding_id": finding_id, "source": "on-chain",
    }


def parse_alert_record_bytes(data: bytes) -> Dict[str, Any]:
    """AlertRecord { log_id: u64, subscriber_address: Address, finding_id: u64,
    severity: String, risk_type: String, block_height: u64, timestamp: u64,
    delivered: bool }"""
    off = 0
    log_id, off = _rd_u64(data, off)
    subscriber_address, off = _rd_address(data, off)
    finding_id, off = _rd_u64(data, off)
    severity, off = _rd_string(data, off)
    risk_type, off = _rd_string(data, off)
    block_height, off = _rd_u64(data, off)
    timestamp, off = _rd_u64(data, off)
    delivered, off = _rd_bool(data, off)
    return {
        "log_id": log_id, "subscriber_address": subscriber_address,
        "finding_id": finding_id, "severity": severity, "risk_type": risk_type,
        "block_height": block_height, "timestamp": timestamp,
        "delivered": delivered, "source": "on-chain",
    }


def parse_subscriber_bytes(data: bytes) -> Dict[str, Any]:
    """Subscriber { address: String, webhook_url: String, min_severity: String,
    active: bool, registered_at: u64, alert_count: u64 }"""
    off = 0
    address, off = _rd_string(data, off)
    webhook_url, off = _rd_string(data, off)
    min_severity, off = _rd_string(data, off)
    active, off = _rd_bool(data, off)
    registered_at, off = _rd_u64(data, off)
    alert_count, off = _rd_u64(data, off)
    return {
        "address": address, "webhook_url": webhook_url, "min_severity": min_severity,
        "active": active, "registered_at": registered_at, "alert_count": alert_count,
        "source": "on-chain",
    }


def parse_agent_metrics_bytes(data: bytes) -> Dict[str, Any]:
    """AgentMetrics { agent_name: String, total_decisions: u64,
    corrections_applied: u64, safety_rejections: u64, avg_confidence: u8,
    high_confidence_count: u64, low_confidence_count: u64,
    last_updated_block: u64, trust_score: u8 }"""
    off = 0
    agent_name, off = _rd_string(data, off)
    total_decisions, off = _rd_u64(data, off)
    corrections_applied, off = _rd_u64(data, off)
    safety_rejections, off = _rd_u64(data, off)
    avg_confidence, off = _rd_u8(data, off)
    high_confidence_count, off = _rd_u64(data, off)
    low_confidence_count, off = _rd_u64(data, off)
    last_updated_block, off = _rd_u64(data, off)
    trust_score, off = _rd_u8(data, off)
    return {
        "agent_name": agent_name, "total_decisions": total_decisions,
        "corrections_applied": corrections_applied,
        "safety_rejections": safety_rejections,
        "avg_confidence": avg_confidence,
        "high_confidence_count": high_confidence_count,
        "low_confidence_count": low_confidence_count,
        "last_updated_block": last_updated_block,
        "trust_score": trust_score, "source": "on-chain",
    }


def parse_credit_account_bytes(data: bytes) -> Dict[str, Any]:
    """CreditAccount { owner: String, balance: U512, total_deposited: U512,
    total_spent: U512, query_count: u64 }"""
    off = 0
    owner, off = _rd_string(data, off)
    balance, off = _rd_u512(data, off)
    total_deposited, off = _rd_u512(data, off)
    total_spent, off = _rd_u512(data, off)
    query_count, off = _rd_u64(data, off)
    return {
        "owner": owner, "balance": balance, "total_deposited": total_deposited,
        "total_spent": total_spent, "query_count": query_count, "source": "on-chain",
    }


def parse_vault_account_bytes(data: bytes) -> Dict[str, Any]:
    """VaultAccount { owner_address: String, escrowed_balance: U512,
    locked_until_block: u64, auto_renew: bool, monthly_spend_limit: U512,
    current_period_spent: U512, total_deposits: U512, total_withdrawals: U512,
    created_at_block: u64 }"""
    off = 0
    owner_address, off = _rd_string(data, off)
    escrowed_balance, off = _rd_u512(data, off)
    locked_until_block, off = _rd_u64(data, off)
    auto_renew, off = _rd_bool(data, off)
    monthly_spend_limit, off = _rd_u512(data, off)
    current_period_spent, off = _rd_u512(data, off)
    total_deposits, off = _rd_u512(data, off)
    total_withdrawals, off = _rd_u512(data, off)
    created_at_block, off = _rd_u64(data, off)
    return {
        "owner_address": owner_address, "escrowed_balance": escrowed_balance,
        "locked_until_block": locked_until_block, "auto_renew": auto_renew,
        "monthly_spend_limit": monthly_spend_limit,
        "current_period_spent": current_period_spent,
        "total_deposits": total_deposits, "total_withdrawals": total_withdrawals,
        "created_at_block": created_at_block, "source": "on-chain",
    }


def parse_risk_policy_bytes(data: bytes) -> Dict[str, Any]:
    """RiskPolicy { version: u32, min_confidence_threshold: u8,
    critical_score_threshold: u8, high_score_threshold: u8,
    medium_score_threshold: u8, max_retry_count: u8,
    safety_rejection_threshold: u8, updated_at_block: u64,
    updated_by: Address|String }

    The ``updated_by`` field is type-polymorphic across contract versions:
    currently-deployed v1 stores a String (u32 LE len + UTF-8); a redeployed
    contract may store an Address (1-byte Key tag + 32 bytes). Auto-detect.
    """
    if len(data) < 18:
        raise ValueError(f"RiskPolicy bytes too short: {len(data)} bytes")
    off = 0
    version, off = _rd_u32(data, off)
    min_conf, off = _rd_u8(data, off)
    crit, off = _rd_u8(data, off)
    high, off = _rd_u8(data, off)
    med, off = _rd_u8(data, off)
    max_retry, off = _rd_u8(data, off)
    safety_rej, off = _rd_u8(data, off)
    updated_at_block, off = _rd_u64(data, off)
    remaining = data[off:]
    # Detect Address vs String
    if len(remaining) == 33 and remaining[0] in (_KEY_TAG_ACCOUNT, _KEY_TAG_HASH):
        updated_by, _ = _rd_address(data, off)
    elif len(remaining) >= 4:
        updated_by, _ = _rd_string(data, off)
    else:
        updated_by = remaining.decode("utf-8", errors="replace")
    return {
        "version": version, "min_confidence_threshold": min_conf,
        "critical_score_threshold": crit, "high_score_threshold": high,
        "medium_score_threshold": med, "max_retry_count": max_retry,
        "safety_rejection_threshold": safety_rej,
        "updated_at_block": updated_at_block, "updated_by": updated_by,
        "source": "on-chain",
    }


def _parse_u64(data: bytes) -> int:
    v, _ = _rd_u64(data, 0)
    return v


def _parse_u512(data: bytes) -> int:
    v, _ = _rd_u512(data, 0)
    return v


def _parse_bool(data: bytes) -> bool:
    v, _ = _rd_bool(data, 0)
    return v


# ---------------------------------------------------------------------------
# Core read primitive
# ---------------------------------------------------------------------------
async def _query_dict(contract_hash: str, dict_address: str) -> Optional[Dict[str, Any]]:
    srh = await asyncio.to_thread(_get_state_root_hash)
    r = await _async_rpc("query_global_state",
                         [{"StateRootHash": srh}, f"dictionary-{dict_address}", []])
    if "error" in r:
        # -32000 == ValueNotFound (key not set yet) — normal for fresh entries
        if r["error"].get("code") == -32000:
            return None
        raise RuntimeError(f"query_global_state error: {r['error']}")
    cl_value = r.get("result", {}).get("stored_value", {}).get("CLValue")
    if not cl_value:
        return None
    return cl_value


async def _read_var(contract: str, field: str, parser) -> Optional[Any]:
    """Read an Odra ``Var<T>`` and parse with ``parser`` (bytes → T)."""
    ch = C.get_contract_hash(contract)
    try:
        uref = await asyncio.to_thread(_get_state_uref_addr, ch)
        idx = C.get_field_index(contract, field)
        addr = _var_dict_address(uref, idx)
        cl = await _query_dict(ch, addr)
        if cl is None:
            return None
        inner = _decode_list_u8(cl)
        if not inner:
            return None
        return parser(inner)
    except Exception as exc:
        logger.debug("read_var(%s.%s) failed: %s", contract, field, exc)
        return None


async def _read_mapping(contract: str, field: str, key_bytes: bytes, parser) -> Optional[Any]:
    """Read an Odra ``Mapping<K,V>`` entry and parse with ``parser``."""
    ch = C.get_contract_hash(contract)
    try:
        uref = await asyncio.to_thread(_get_state_uref_addr, ch)
        idx = C.get_field_index(contract, field)
        addr = _mapping_dict_address(uref, idx, key_bytes)
        cl = await _query_dict(ch, addr)
        if cl is None:
            return None
        inner = _decode_list_u8(cl)
        if not inner:
            return None
        return parser(inner)
    except Exception as exc:
        logger.debug("read_mapping(%s.%s) failed: %s", contract, field, exc)
        return None


# ---------------------------------------------------------------------------
# Public high-level readers — AuditTrail
# ---------------------------------------------------------------------------
async def read_finding_count() -> Optional[int]:
    return await _read_var("AuditTrail", "finding_count", _parse_u64)


async def read_finding(finding_id: int) -> Optional[Dict[str, Any]]:
    return await _read_mapping("AuditTrail", "findings", _enc_u64(finding_id), parse_finding_bytes)


async def read_recent_findings(limit: int = 20) -> List[Dict[str, Any]]:
    count = await read_finding_count()
    if not count or count <= 0:
        return []
    start = max(1, count - limit + 1)
    ids = range(start, count + 1)
    findings = await asyncio.gather(*(read_finding(i) for i in ids))
    out = [f for f in findings if isinstance(f, dict)]
    out.sort(key=lambda f: f.get("id", 0), reverse=True)
    return out


# ---------------------------------------------------------------------------
# RiskOracle
# ---------------------------------------------------------------------------
async def read_risk_score(address: str) -> Optional[Dict[str, Any]]:
    return await _read_mapping("RiskOracle", "scores", _enc_string(address), parse_risk_score_bytes)


# ---------------------------------------------------------------------------
# RiskPolicyManager
# ---------------------------------------------------------------------------
async def read_current_policy() -> Optional[Dict[str, Any]]:
    return await _read_var("RiskPolicyManager", "current_policy", parse_risk_policy_bytes)


async def read_policy_version(version: int) -> Optional[Dict[str, Any]]:
    return await _read_mapping("RiskPolicyManager", "policy_history", _enc_u32(version), parse_risk_policy_bytes)


async def read_current_policy_version() -> Optional[int]:
    """Read the ``version`` field of the current policy (a u32)."""
    policy = await read_current_policy()
    if policy is None:
        return None
    return policy.get("version")


# ---------------------------------------------------------------------------
# SentinelRegistry
# ---------------------------------------------------------------------------
async def read_subscriber(address: str) -> Optional[Dict[str, Any]]:
    return await _read_mapping("SentinelRegistry", "subscribers", _enc_string(address), parse_subscriber_bytes)


async def read_subscriber_count() -> Optional[int]:
    return await _read_var("SentinelRegistry", "subscriber_count", _parse_u64)


# ---------------------------------------------------------------------------
# SentinelAlertLog
# ---------------------------------------------------------------------------
async def read_alert_log(log_id: int) -> Optional[Dict[str, Any]]:
    return await _read_mapping("SentinelAlertLog", "logs", _enc_u64(log_id), parse_alert_record_bytes)


async def read_alert_log_count() -> Optional[int]:
    return await _read_var("SentinelAlertLog", "log_count", _parse_u64)


# ---------------------------------------------------------------------------
# SentinelCredit
# ---------------------------------------------------------------------------
async def read_credit_account(account_address: str) -> Optional[Dict[str, Any]]:
    return await _read_mapping("SentinelCredit", "accounts", _enc_string(account_address), parse_credit_account_bytes)


async def read_credit_balance(account_address: str) -> Optional[int]:
    acct = await read_credit_account(account_address)
    if acct is None:
        return None
    return acct.get("balance")


async def read_credit_prices() -> Optional[Dict[str, int]]:
    q = await _read_var("SentinelCredit", "query_price", _parse_u512)
    p = await _read_var("SentinelCredit", "premium_price", _parse_u512)
    if q is None and p is None:
        return None
    return {"query_price": q or 0, "premium_price": p or 0}


async def read_total_revenue() -> Optional[int]:
    return await _read_var("SentinelCredit", "total_revenue", _parse_u512)


# ---------------------------------------------------------------------------
# SubscriberVault
# ---------------------------------------------------------------------------
async def read_vault_account(subscriber_address: str) -> Optional[Dict[str, Any]]:
    return await _read_mapping("SubscriberVault", "accounts", _enc_string(subscriber_address), parse_vault_account_bytes)


async def read_vault_balance(subscriber_address: str) -> Optional[int]:
    acct = await read_vault_account(subscriber_address)
    if acct is None:
        return None
    return acct.get("escrowed_balance")


async def read_total_locked() -> Optional[int]:
    return await _read_var("SubscriberVault", "total_locked", _parse_u512)


# ---------------------------------------------------------------------------
# AgentBehaviorIndex
# ---------------------------------------------------------------------------
async def read_agent_metrics(agent_name: str) -> Optional[Dict[str, Any]]:
    return await _read_mapping("AgentBehaviorIndex", "metrics", _enc_string(agent_name), parse_agent_metrics_bytes)


async def read_agent_trust_score(agent_name: str) -> Optional[int]:
    m = await read_agent_metrics(agent_name)
    if m is None:
        return None
    return m.get("trust_score")


async def read_agent_count() -> Optional[int]:
    return await _read_var("AgentBehaviorIndex", "agent_count", _parse_u64)


# ---------------------------------------------------------------------------
# Generic Var<bool) (paused flag) + contract/package introspection
# ---------------------------------------------------------------------------
async def read_bool_var(contract: str, field: str) -> Optional[bool]:
    return await _read_var(contract, field, _parse_bool)


async def read_u64_var(contract: str, field: str) -> Optional[int]:
    return await _read_var(contract, field, _parse_u64)


async def read_u512_var(contract: str, field: str) -> Optional[int]:
    return await _read_var(contract, field, _parse_u512)


async def query_contract(contract_name: str) -> Dict[str, Any]:
    """Return the raw ``Contract`` stored value (entry_points, named_keys)."""
    ch = C.get_contract_hash(contract_name)
    srh = await asyncio.to_thread(_get_state_root_hash)
    r = await _async_rpc("query_global_state", [{"StateRootHash": srh}, f"hash-{ch}", []])
    if "error" in r:
        return {"exists": False, "error": r["error"]}
    sv = r.get("result", {}).get("stored_value", {}).get("Contract", {})
    return {
        "exists": True,
        "contract": contract_name,
        "contract_hash": ch,
        "contract_package_hash": sv.get("contract_package_hash", ""),
        "entry_points": [ep.get("name", "") for ep in sv.get("entry_points", [])],
        "named_keys": [nk.get("name", "") for nk in sv.get("named_keys", [])],
    }


async def query_contract_package(contract_name: str) -> Dict[str, Any]:
    """Return the ``ContractPackage`` stored value (versions, disabled, lock)."""
    ph = C.get_package_hash(contract_name)
    srh = await asyncio.to_thread(_get_state_root_hash)
    r = await _async_rpc("query_global_state", [{"StateRootHash": srh}, ph, []])
    if "error" in r:
        return {"exists": False, "error": r["error"]}
    pkg = r.get("result", {}).get("stored_value", {}).get("ContractPackage", {})
    versions = []
    for v in pkg.get("versions", []):
        versions.append({
            "protocol_version": v.get("protocol_version", {}),
            "contract_hash": v.get("contract_hash", ""),
        })
    return {
        "exists": True,
        "contract": contract_name,
        "package_hash": ph,
        "versions": versions,
        "disabled_versions": pkg.get("disabled_versions", []),
        "lock_status": pkg.get("lock_status", {}),
    }


async def get_block_height() -> Optional[int]:
    """Return the latest block height from the Casper node.

    Uses ``info_get_status`` (Casper 2.x) which exposes
    ``last_added_block_info.height`` — a single round-trip that works on every
    node version. Falls back to ``chain_get_block`` if the status call fails.
    """
    try:
        r = await _async_rpc("info_get_status", [])
        info = r.get("result", {}).get("last_added_block_info", {})
        h = info.get("height")
        if h is not None:
            return int(h)
        # Fallback: chain_get_block → {result: {block: {header: {height}}}}
        r2 = await _async_rpc("chain_get_block", [])
        block = r2.get("result", {}).get("block", {})
        h2 = block.get("header", {}).get("height")
        return int(h2) if h2 is not None else None
    except Exception as exc:
        logger.debug("get_block_height failed: %s", exc)
        return None


def reset_caches() -> None:
    """Clear the state-root-hash + state-URef caches (for tests)."""
    _state_root_cache["value"] = None
    _state_root_cache["expires_at"] = 0.0
    _state_uref_cache.clear()
