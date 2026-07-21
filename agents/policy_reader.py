"""
On-chain RiskPolicy reader for SelfCorrectionAgent / SafetyGuard.

This module wires the ``policy_reader`` callable (consumed by
``SelfCorrectionAgent._evaluate`` and ``SafetyGuard.validate``) to the REAL
on-chain ``RiskPolicyManager`` contract — replacing the previous static-config
fallback.

How it works
------------
``RiskPolicyManager`` is an Odra 2.9.0 contract. Its ``current_policy`` field
is a ``Var<RiskPolicy>`` which Odra stores as a Casper Dictionary entry under
the contract's ``state`` URef. The dictionary item key is derived (per Odra's
``ContractEnv::current_key``) as:

    index_bytes   = u32::to_be_bytes(field_index)        # legacy encoding, idx ≤ 15
    hashed        = blake2b(index_bytes)                 # 32 raw bytes
    item_key      = hex(hashed)                          # 64 ASCII chars (valid UTF-8)
    dict_address  = blake2b(state_uref.addr() ++ item_key)   # 32 bytes — Key::Dictionary

The on-chain ``current_policy`` Var lives at field index 1 (index 0 is reserved
by the Odra module macro for the reentrancy-guard bookkeeping field — verified
empirically against the deployed testnet contract).

The stored CLValue is ``List<U8>`` (a ``Vec<u8>`` wrapper) whose inner bytes are
the ``bytesrepr``-serialised ``RiskPolicy`` struct:

    version: u32 (4 LE) | min_confidence_threshold: u8 | critical_score_threshold: u8
    high_score_threshold: u8 | medium_score_threshold: u8 | max_retry_count: u8
    safety_rejection_threshold: u8 | updated_at_block: u64 (8 LE)
    updated_by: String (u32 LE length ++ UTF-8)

All reads are free ``query_global_state`` JSON-RPC calls — no gas, no signing.
On any error the reader falls back to the contract's default policy
(min_confidence=75, max_retries=2, safety_rejection=80) so the pipeline never
blocks on a transient RPC failure.

Resources (per hackathon detail https://dorahacks.io/hackathon/casper-agentic-buildathon-finals/detail):
  - Odra Framework (odra.dev) — Var<T> storage, ContractEnv::current_key, blake2b
  - Casper docs (docs.casper.network) — query_global_state, Key::Dictionary
  - Casper testnet RPC (node.testnet.casper.network) — live reads
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import struct
import urllib.request
from typing import Any, Awaitable, Callable, Dict

logger = logging.getLogger("vaultwatch.policy_reader")

# ---------------------------------------------------------------------------
# Constants — the on-chain RiskPolicyManager (verified on testnet)
# ---------------------------------------------------------------------------
RISK_POLICY_MANAGER_HASH = "1027cb2a989b75d8b29b82cab60a8b12a892138a5704cdd4753a0862f65b1d85"
CASPER_RPC_URL = os.getenv("CASPER_RPC_URL", "https://node.testnet.casper.network/rpc")

# Odra field index for ``current_policy`` inside RiskPolicyManager.
# Index 0 is the hidden reentrancy-guard bookkeeping field; the first
# user-declared field (``current_policy``) is at index 1. Verified empirically
# — the computed dictionary address for index 1 matches the on-chain read
# observed in the execution effects of a ``get_current_version`` deploy.
CURRENT_POLICY_FIELD_INDEX = 1

# Default policy (matches RiskPolicyManager::init defaults) — used on any read
# failure so the pipeline never blocks.
DEFAULT_POLICY: Dict[str, Any] = {
    "version": 1,
    "min_confidence_threshold": 75,
    "critical_score_threshold": 80,
    "high_score_threshold": 60,
    "medium_score_threshold": 40,
    "max_retry_count": 2,
    "safety_rejection_threshold": 80,
    "updated_at_block": 0,
    "updated_by": "default",
    "source": "fallback",
}


# ---------------------------------------------------------------------------
# Low-level RPC helper
# ---------------------------------------------------------------------------
def _rpc(method: str, params: list) -> Dict[str, Any]:
    """Make a synchronous JSON-RPC call to the Casper node."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(
        CASPER_RPC_URL, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


async def _async_rpc(method: str, params: list) -> Dict[str, Any]:
    """Async wrapper — runs the sync RPC call in a thread."""
    return await asyncio.to_thread(_rpc, method, params)


def _get_state_root_hash() -> str:
    r = _rpc("chain_get_state_root_hash", [])
    srh = r.get("result", {}).get("state_root_hash")
    if not srh:
        raise RuntimeError(f"no state root hash: {r}")
    return srh


# ---------------------------------------------------------------------------
# Odra storage-key derivation
# ---------------------------------------------------------------------------
def compute_dict_address(state_uref_addr: bytes, field_index: int) -> str:
    """Compute the Casper ``Key::Dictionary`` address for an Odra ``Var<T>``.

    Mirrors Odra 2.9.0's ``ContractEnv::current_key`` (which hex-encodes the
    blake2b of the index bytes) and ``casper_types::Key::dictionary`` (which
    blake2b-hashes ``uref.addr() ++ item_key_bytes``).
    """
    # Odra legacy encoding: index_bytes = u32 big-endian of the packed path.
    # For a single-element path [i], fold gives i, so index_bytes = be32(i).
    index_bytes = field_index.to_bytes(4, "big")
    hashed = hashlib.blake2b(index_bytes, digest_size=32).digest()
    # Odra hex-encodes the 32-byte hash into a 64-char ASCII string (the
    # dictionary item key passed to casper_dictionary_put).
    item_key = hashed.hex().encode("ascii")
    # Casper Key::dictionary = blake2b(uref.addr(32) ++ item_key_bytes(64))
    addr = hashlib.blake2b(state_uref_addr + item_key, digest_size=32).digest()
    return addr.hex()


def _get_state_uref_addr(contract_hash: str) -> bytes:
    """Read the ``state`` URef (Odra's dictionary seed) from a contract's named keys."""
    srh = _get_state_root_hash()
    r = _rpc(
        "query_global_state",
        [{"StateRootHash": srh}, f"hash-{contract_hash}", []],
    )
    if "error" in r:
        raise RuntimeError(f"query contract {contract_hash}: {r['error']}")
    named_keys = (
        r.get("result", {}).get("stored_value", {}).get("Contract", {}).get("named_keys", [])
    )
    for nk in named_keys:
        if nk.get("name") == "state":
            uref_str = nk["key"]  # e.g. "uref-dca768b2...-007"
            # Extract the 32-byte addr (between "uref-" and "-<access>")
            addr_hex = uref_str.split("-")[1]
            return bytes.fromhex(addr_hex)
    raise RuntimeError(f"no 'state' named key on contract {contract_hash}")


# ---------------------------------------------------------------------------
# RiskPolicy CLValue parser
# ---------------------------------------------------------------------------
def parse_risk_policy_bytes(data: bytes) -> Dict[str, Any]:
    """Parse the ``bytesrepr``-serialised ``RiskPolicy`` struct bytes.

    Field layout (Casper bytesrepr, little-endian):
      version: u32 | min_confidence_threshold: u8 | critical_score_threshold: u8
      high_score_threshold: u8 | medium_score_threshold: u8 | max_retry_count: u8
      safety_rejection_threshold: u8 | updated_at_block: u64 | updated_by: String
    """
    if len(data) < 18:  # 4 + 1*6 + 8 = 18 bytes minimum (before the String)
        raise ValueError(f"RiskPolicy bytes too short: {len(data)} bytes")
    offset = 0
    version = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    min_conf = data[offset]
    offset += 1
    crit_score = data[offset]
    offset += 1
    high_score = data[offset]
    offset += 1
    med_score = data[offset]
    offset += 1
    max_retry = data[offset]
    offset += 1
    safety_rej = data[offset]
    offset += 1
    updated_at_block = struct.unpack_from("<Q", data, offset)[0]
    offset += 8
    # String: u32 LE length ++ UTF-8 bytes
    str_len = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    updated_by = data[offset : offset + str_len].decode("utf-8", errors="replace")
    return {
        "version": version,
        "min_confidence_threshold": min_conf,
        "critical_score_threshold": crit_score,
        "high_score_threshold": high_score,
        "medium_score_threshold": med_score,
        "max_retry_count": max_retry,
        "safety_rejection_threshold": safety_rej,
        "updated_at_block": updated_at_block,
        "updated_by": updated_by,
        "source": "on-chain",
    }


def _decode_cl_value_list_u8(cl_value: Dict[str, Any]) -> bytes:
    """Extract the raw bytes from a CLValue of type ``List<U8>`` (Vec<u8>).

    The ``bytes`` field is the serialised CLValue: a u32 LE length prefix
    followed by the byte array. The ``parsed`` field (if present) is a list of
    ints — we prefer ``bytes`` for exactness.
    """
    raw_hex = cl_value.get("bytes", "")
    if not raw_hex:
        # Fall back to parsed (list of ints)
        parsed = cl_value.get("parsed") or []
        return bytes(parsed)
    raw = bytes.fromhex(raw_hex)
    if len(raw) < 4:
        return b""
    length = struct.unpack_from("<I", raw, 0)[0]
    return raw[4 : 4 + length]


# ---------------------------------------------------------------------------
# Public API — the policy_reader callable
# ---------------------------------------------------------------------------
async def read_current_policy(contract_hash: str = RISK_POLICY_MANAGER_HASH) -> Dict[str, Any]:
    """Read the current ``RiskPolicy`` from the on-chain RiskPolicyManager.

    Returns a dict with keys matching the ``RiskPolicy`` struct fields plus a
    ``source`` field (``"on-chain"`` or ``"fallback"``). Falls back to
    ``DEFAULT_POLICY`` on any error so callers never block.
    """
    try:
        srh = _get_state_root_hash()
        state_uref_addr = await asyncio.to_thread(_get_state_uref_addr, contract_hash)
        dict_addr = compute_dict_address(state_uref_addr, CURRENT_POLICY_FIELD_INDEX)
        r = await _async_rpc(
            "query_global_state",
            [{"StateRootHash": srh}, f"dictionary-{dict_addr}", []],
        )
        if "error" in r:
            logger.warning("policy read failed (query): %s — using defaults", r["error"])
            return dict(DEFAULT_POLICY)
        cl_value = (
            r.get("result", {}).get("stored_value", {}).get("CLValue", {})
        )
        inner_bytes = _decode_cl_value_list_u8(cl_value)
        if not inner_bytes:
            logger.warning("policy read returned empty CLValue — using defaults")
            return dict(DEFAULT_POLICY)
        policy = parse_risk_policy_bytes(inner_bytes)
        logger.info(
            "on-chain policy v%s: min_conf=%s max_retry=%s safety_rej=%s updated_by=%s",
            policy["version"],
            policy["min_confidence_threshold"],
            policy["max_retry_count"],
            policy["safety_rejection_threshold"],
            policy["updated_by"],
        )
        return policy
    except Exception as exc:
        logger.warning("policy read error: %s — using defaults", exc)
        return dict(DEFAULT_POLICY)


def make_policy_reader(
    contract_hash: str = RISK_POLICY_MANAGER_HASH,
) -> Callable[[], Awaitable[Dict[str, Any]]]:
    """Return an async callable suitable for ``SelfCorrectionAgent(policy_reader=...)``.

    The callable takes no args and returns the current on-chain policy dict.
    """
    # Resolve the env override at call time so tests can point at a different
    # contract / RPC without restarting the process.
    async def _reader() -> Dict[str, Any]:
        ch = os.getenv("RISK_POLICY_MANAGER_HASH") or contract_hash
        return await read_current_policy(ch)

    return _reader
