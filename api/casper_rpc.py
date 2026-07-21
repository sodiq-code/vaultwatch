"""Casper on-chain reader for VaultWatch contracts.

This module performs **read-only** ``query_global_state`` JSON-RPC calls
against the public Casper testnet node (no auth, no gas, no signing) to read
the live on-chain state of the ``AuditTrail`` and ``RiskOracle`` contracts.

It implements the EXACT Odra 2.9.0 storage-key derivation (verified against
the odra-core source at ``odra-core-2.9.0/src/contract_env.rs`` and
``mapping.rs``) so the reads resolve to the same dictionary addresses the
contracts write to.

Odra storage model (per the source)
-----------------------------------
* Every Odra module instance has a single ``state`` URef (a Casper dictionary
  seed) exposed as a contract named key called ``state``.
* A ``Var<T>`` at field index ``i`` stores its value under the dictionary
  address::

      index_bytes  = be32(i)                         # legacy encoding (i <= 15)
      hashed       = blake2b(index_bytes)             # 32 bytes
      item_key     = hex(hashed)                      # 64 ASCII chars
      dict_address = blake2b(state_uref_addr ++ item_key)   # 32 bytes

* A ``Mapping<K, V>`` at field index ``j`` stores the entry for key ``k``
  under the dictionary address::

      index_bytes  = be32(j)                          # legacy encoding (j <= 15)
      mapping_data = k.to_bytes()                     # bytesrepr of K
      combined     = index_bytes ++ mapping_data
      hashed       = blake2b(combined)                # 32 bytes
      item_key     = hex(hashed)                      # 64 ASCII chars
      dict_address = blake2b(state_uref_addr ++ item_key)   # 32 bytes

  (This is the only difference from ``Var``: the user key's ``to_bytes()``
  is appended to ``index_bytes`` BEFORE the blake2b. Verified in
  ``odra-core-2.9.0/src/mapping.rs::env_for_key`` which calls
  ``env.add_to_mapping_data(&key.to_bytes())``, and ``contract_env.rs::
  current_key`` which builds ``index_bytes ++ mapping_data``.)

* Every Odra value is stored wrapped as a ``List<U8>`` (``Vec<u8>``) CLValue
  — see ``odra-casper-wasm-env-2.9.0/src/host_functions.rs::set_value`` which
  does ``CLValue::from_t(value.to_vec())``. So the raw ``bytes`` field of the
  CLValue returned by ``query_global_state`` is::

      u32 LE length ++ <struct to_bytes() output>

Field indices
-------------
Odra reserves index 0 for the reentrancy-guard bookkeeping field, so the
first user-declared field is at index 1.

  AuditTrail:
    1 = findings      (Mapping<u64, Finding>)
    2 = finding_count (Var<u64>)
    3 = owner         (Var<Address>)

  RiskOracle:
    1 = scores        (Mapping<String, RiskScore>)
    2 = owner         (Var<Address>)

bytesrepr field layouts
-----------------------
``Finding`` (declaration order):

    id: u64 | address: String | risk_type: String | severity: String |
    confidence: u8 | description: String | rwa_enriched: bool |
    agent_model: String | block_height: u64 | timestamp: u64 | tx_hash: String

``RiskScore`` (declaration order):

    address: String | score: u8 | risk_type: String | confidence: u8 |
    last_updated: u64 | finding_id: u64

where ``u64`` = 8 bytes LE, ``u8`` = 1 byte, ``bool`` = 1 byte, and
``String`` = ``u32 LE length ++ UTF-8 bytes`` (Casper bytesrepr).

Resources (per hackathon detail https://dorahacks.io/hackathon/casper-agentic-buildathon-finals/detail):
  * Odra Framework (odra.dev) — Var<T> / Mapping<K,V> storage, ContractEnv
  * Casper docs (docs.casper.network) — query_global_state, Key::Dictionary
  * Casper testnet RPC (node.testnet.casper.network) — free live reads
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import struct
import time
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger("vaultwatch.casper_rpc")

# ---------------------------------------------------------------------------
# Configuration — contract hashes + RPC endpoint
# ---------------------------------------------------------------------------
CASPER_RPC_URL = "https://node.testnet.casper.network/rpc"

# Verified CONTRACT hashes on Casper Testnet (resolved from the deployer
# account's named keys via query_global_state — see deploy_hashes_live.json
# and worklog Task 1). These are the state-queryable contract hashes (NOT the
# deploy/transaction hashes in dashboard/src/liveApi.js::CONTRACT_HASHES,
# which are used only for explorer links). Override via env for tests.
AUDIT_TRAIL_HASH_DEFAULT = "cd1579001dcd923888baa9ea44b1df3b816de52ced44682a3042779d1d4d9932"
RISK_ORACLE_HASH_DEFAULT = "234a34a71fb04625971373b06b73ac6dbc5f7d701f7e96621c752d73ccde80ff"


def _audit_trail_hash() -> str:
    import os

    return os.getenv("AUDIT_TRAIL_HASH", AUDIT_TRAIL_HASH_DEFAULT)


def _risk_oracle_hash() -> str:
    import os

    return os.getenv("RISK_ORACLE_HASH", RISK_ORACLE_HASH_DEFAULT)


# Odra field indices (0 = hidden reentrancy guard; user fields start at 1).
AUDIT_TRAIL_FINDINGS_INDEX = 1
AUDIT_TRAIL_FINDING_COUNT_INDEX = 2
RISK_ORACLE_SCORES_INDEX = 1

# Cache the state-root-hash + per-contract state-URef for ~16s to avoid
# repeating the same two round-trips on every read. Casper block time is ~16s
# on testnet, so this is the natural freshness window.
_CACHE_TTL_SECONDS = 16.0
_state_root_cache: Dict[str, Any] = {"value": None, "expires_at": 0.0}
_state_uref_cache: Dict[str, Any] = {}  # contract_hash -> {addr, expires_at}


# ---------------------------------------------------------------------------
# Low-level JSON-RPC helpers
# ---------------------------------------------------------------------------
def _rpc(method: str, params: list, rpc_url: str = CASPER_RPC_URL) -> Dict[str, Any]:
    """Synchronous JSON-RPC call to the Casper node.

    Uses urllib (no extra deps). Raises RuntimeError on transport / HTTP error
    or on a JSON-RPC ``error`` field in the response.
    """
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    ).encode()
    req = urllib.request.Request(
        rpc_url, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    if "error" in data:
        raise RuntimeError(f"{method} RPC error: {data['error']}")
    return data


async def _async_rpc(method: str, params: list, rpc_url: str = CASPER_RPC_URL) -> Dict[str, Any]:
    """Async wrapper — runs the sync RPC in a worker thread."""
    return await asyncio.to_thread(_rpc, method, params, rpc_url)


def _get_state_root_hash(rpc_url: str = CASPER_RPC_URL) -> str:
    """Return the latest state root hash (cached for ``_CACHE_TTL_SECONDS``)."""
    now = time.time()
    cached = _state_root_cache
    if cached["value"] is not None and cached["expires_at"] > now:
        return cached["value"]  # type: ignore[return-value]
    r = _rpc("chain_get_state_root_hash", [], rpc_url)
    srh = r.get("result", {}).get("state_root_hash")
    if not srh:
        raise RuntimeError(f"no state root hash in response: {r}")
    cached["value"] = srh
    cached["expires_at"] = now + _CACHE_TTL_SECONDS
    return srh


def _get_state_uref_addr(contract_hash: str, rpc_url: str = CASPER_RPC_URL) -> bytes:
    """Return the 32-byte address of the contract's ``state`` URef (cached).

    Odra stores every contract's data inside a single dictionary seeded by the
    ``state`` URef (a named key on the contract). We read that URef once per
    contract per cache window.
    """
    now = time.time()
    cached = _state_uref_cache.get(contract_hash)
    if cached is not None and cached["expires_at"] > now:
        return cached["addr"]  # type: ignore[return-value]
    srh = _get_state_root_hash(rpc_url)
    r = _rpc(
        "query_global_state",
        [{"StateRootHash": srh}, f"hash-{contract_hash}", []],
        rpc_url,
    )
    named_keys = (
        r.get("result", {}).get("stored_value", {}).get("Contract", {}).get("named_keys", [])
    )
    for nk in named_keys:
        if nk.get("name") == "state":
            uref_str = nk["key"]  # e.g. "uref-dca768b2...-007"
            addr_hex = uref_str.split("-")[1]
            addr = bytes.fromhex(addr_hex)
            _state_uref_cache[contract_hash] = {"addr": addr, "expires_at": now + _CACHE_TTL_SECONDS}
            return addr
    raise RuntimeError(f"no 'state' named key on contract {contract_hash}")


# ---------------------------------------------------------------------------
# Odra storage-key derivation
# ---------------------------------------------------------------------------
def compute_var_dict_address(state_uref_addr: bytes, field_index: int) -> str:
    """Compute the Casper ``Key::Dictionary`` address for an Odra ``Var<T>``.

    Mirrors Odra 2.9.0 ``ContractEnv::current_key`` for a single-element path
    (legacy encoding, field_index <= 15) + ``casper_types::Key::dictionary``.
    """
    index_bytes = field_index.to_bytes(4, "big")
    hashed = hashlib.blake2b(index_bytes, digest_size=32).digest()
    item_key = hashed.hex().encode("ascii")  # 64 ASCII chars
    addr = hashlib.blake2b(state_uref_addr + item_key, digest_size=32).digest()
    return addr.hex()


def compute_mapping_dict_address(
    state_uref_addr: bytes, field_index: int, key_bytes: bytes
) -> str:
    """Compute the Casper ``Key::Dictionary`` address for a ``Mapping<K,V>`` entry.

    ``key_bytes`` must be the bytesrepr serialization of ``K`` (e.g.
    ``u64::to_bytes()`` = 8 bytes LE, ``String::to_bytes()`` = u32 LE len +
    UTF-8). This mirrors ``Mapping::env_for_key`` -> ``add_to_mapping_data``
    -> ``ContractEnv::current_key`` (which builds ``index_bytes ++
    mapping_data`` before blake2b).
    """
    index_bytes = field_index.to_bytes(4, "big")
    combined = index_bytes + key_bytes
    hashed = hashlib.blake2b(combined, digest_size=32).digest()
    item_key = hashed.hex().encode("ascii")  # 64 ASCII chars
    addr = hashlib.blake2b(state_uref_addr + item_key, digest_size=32).digest()
    return addr.hex()


# ---------------------------------------------------------------------------
# bytesrepr encoders for key types
# ---------------------------------------------------------------------------
def encode_u64_key(value: int) -> bytes:
    """bytesrepr of ``u64`` = 8 bytes little-endian."""
    return struct.pack("<Q", int(value))


def encode_string_key(value: str) -> bytes:
    """bytesrepr of ``String`` = u32 LE length prefix + UTF-8 bytes."""
    raw = value.encode("utf-8")
    return struct.pack("<I", len(raw)) + raw


# ---------------------------------------------------------------------------
# bytesrepr decoders for stored value types
# ---------------------------------------------------------------------------
def _decode_cl_value_list_u8(cl_value: Dict[str, Any]) -> bytes:
    """Extract the raw inner bytes from a stored ``List<U8>`` CLValue.

    Odra wraps every stored value in ``CLValue::from_t(value.to_vec())`` (a
    ``Vec<u8>``), so the CLValue ``bytes`` field is ``u32 LE len ++ bytes``.
    """
    raw_hex = cl_value.get("bytes", "")
    if not raw_hex:
        parsed = cl_value.get("parsed") or []
        return bytes(parsed)
    raw = bytes.fromhex(raw_hex)
    if len(raw) < 4:
        return b""
    length = struct.unpack_from("<I", raw, 0)[0]
    return raw[4 : 4 + length]


def _read_u64(data: bytes, offset: int) -> tuple[int, int]:
    if offset + 8 > len(data):
        raise ValueError(f"u64 read past end of buffer at offset {offset}")
    return struct.unpack_from("<Q", data, offset)[0], offset + 8


def _read_u8(data: bytes, offset: int) -> tuple[int, int]:
    if offset + 1 > len(data):
        raise ValueError(f"u8 read past end of buffer at offset {offset}")
    return data[offset], offset + 1


def _read_bool(data: bytes, offset: int) -> tuple[bool, int]:
    val, offset = _read_u8(data, offset)
    return bool(val), offset


def _read_string(data: bytes, offset: int) -> tuple[str, int]:
    if offset + 4 > len(data):
        raise ValueError(f"String length read past end of buffer at offset {offset}")
    length = struct.unpack_from("<I", data, offset)[0]
    offset += 4
    if offset + length > len(data):
        raise ValueError(
            f"String body read past end of buffer: need {length} bytes at {offset}, have {len(data)}"
        )
    raw = data[offset : offset + length]
    return raw.decode("utf-8", errors="replace"), offset + length


def parse_finding_bytes(data: bytes) -> Dict[str, Any]:
    """Parse the bytesrepr-serialised ``Finding`` struct.

    Field order (declaration order in contracts/src/audit_trail.rs):
      id: u64 | address: String | risk_type: String | severity: String |
      confidence: u8 | description: String | rwa_enriched: bool |
      agent_model: String | block_height: u64 | timestamp: u64 | tx_hash: String
    """
    offset = 0
    id_, offset = _read_u64(data, offset)
    address, offset = _read_string(data, offset)
    risk_type, offset = _read_string(data, offset)
    severity, offset = _read_string(data, offset)
    confidence, offset = _read_u8(data, offset)
    description, offset = _read_string(data, offset)
    rwa_enriched, offset = _read_bool(data, offset)
    agent_model, offset = _read_string(data, offset)
    block_height, offset = _read_u64(data, offset)
    timestamp, offset = _read_u64(data, offset)
    tx_hash, offset = _read_string(data, offset)
    return {
        "id": id_,
        "address": address,
        "risk_type": risk_type,
        "severity": severity,
        "confidence": confidence,
        "description": description,
        "rwa_enriched": rwa_enriched,
        "agent_model": agent_model,
        "block_height": block_height,
        "timestamp": timestamp,
        "tx_hash": tx_hash,
        "source": "on-chain",
    }


def parse_risk_score_bytes(data: bytes) -> Dict[str, Any]:
    """Parse the bytesrepr-serialised ``RiskScore`` struct.

    Field order (declaration order in contracts/src/risk_oracle.rs):
      address: String | score: u8 | risk_type: String | confidence: u8 |
      last_updated: u64 | finding_id: u64
    """
    offset = 0
    address, offset = _read_string(data, offset)
    score, offset = _read_u8(data, offset)
    risk_type, offset = _read_string(data, offset)
    confidence, offset = _read_u8(data, offset)
    last_updated, offset = _read_u64(data, offset)
    finding_id, offset = _read_u64(data, offset)
    return {
        "address": address,
        "score": score,
        "risk_type": risk_type,
        "confidence": confidence,
        "last_updated": last_updated,
        "finding_id": finding_id,
        "source": "on-chain",
    }


def parse_u64_bytes(data: bytes) -> int:
    """Parse a bare ``u64`` bytesrepr (8 bytes LE)."""
    val, _ = _read_u64(data, 0)
    return val


# ---------------------------------------------------------------------------
# Public high-level readers (async)
# ---------------------------------------------------------------------------
async def _query_dict(contract_hash: str, dict_address: str) -> Optional[Dict[str, Any]]:
    """Run ``query_global_state`` against a computed dictionary address.

    Returns the parsed ``CLValue`` dict, or ``None`` if the entry does not
    exist (Casper returns an error code for missing dictionary keys).
    """
    srh = await asyncio.to_thread(_get_state_root_hash)
    r = await _async_rpc(
        "query_global_state",
        [{"StateRootHash": srh}, f"dictionary-{dict_address}", []],
    )
    if "error" in r:
        # ValueNotFound == key not set yet. Anything else is a real error.
        err_code = r["error"].get("code")
        if err_code == -32000:
            return None
        raise RuntimeError(f"query_global_state error: {r['error']}")
    cl_value = r.get("result", {}).get("stored_value", {}).get("CLValue")
    if not cl_value:
        return None
    return cl_value


async def read_finding_count(
    contract_hash: Optional[str] = None,
) -> Optional[int]:
    """Read ``AuditTrail.finding_count`` (a ``Var<u64>``) from chain.

    Returns the integer count, or ``None`` if the read fails (RPC unreachable,
    contract not deployed, or the value has never been set).
    """
    ch = contract_hash or _audit_trail_hash()
    try:
        uref_addr = await asyncio.to_thread(_get_state_uref_addr, ch)
        dict_addr = compute_var_dict_address(uref_addr, AUDIT_TRAIL_FINDING_COUNT_INDEX)
        cl_value = await _query_dict(ch, dict_addr)
        if cl_value is None:
            return None
        inner = _decode_cl_value_list_u8(cl_value)
        if not inner:
            return None
        return parse_u64_bytes(inner)
    except Exception as exc:
        logger.debug("read_finding_count failed: %s", exc)
        return None


async def read_finding(
    finding_id: int,
    contract_hash: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Read a single ``Finding`` from ``AuditTrail.findings[id]``.

    Returns the parsed finding dict, or ``None`` if not found / read failed.
    """
    ch = contract_hash or _audit_trail_hash()
    try:
        uref_addr = await asyncio.to_thread(_get_state_uref_addr, ch)
        key_bytes = encode_u64_key(finding_id)
        dict_addr = compute_mapping_dict_address(
            uref_addr, AUDIT_TRAIL_FINDINGS_INDEX, key_bytes
        )
        cl_value = await _query_dict(ch, dict_addr)
        if cl_value is None:
            return None
        inner = _decode_cl_value_list_u8(cl_value)
        if not inner:
            return None
        return parse_finding_bytes(inner)
    except Exception as exc:
        logger.debug("read_finding(%s) failed: %s", finding_id, exc)
        return None


async def read_risk_score(
    address: str,
    contract_hash: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Read a ``RiskScore`` from ``RiskOracle.scores[address]``.

    ``address`` is the String key the contract stores (typically a Casper
    account hash string like ``"account-hash-<hex>"`` or a public key). Returns
    the parsed risk-score dict, or ``None`` if not found / read failed.
    """
    ch = contract_hash or _risk_oracle_hash()
    try:
        uref_addr = await asyncio.to_thread(_get_state_uref_addr, ch)
        key_bytes = encode_string_key(address)
        dict_addr = compute_mapping_dict_address(
            uref_addr, RISK_ORACLE_SCORES_INDEX, key_bytes
        )
        cl_value = await _query_dict(ch, dict_addr)
        if cl_value is None:
            return None
        inner = _decode_cl_value_list_u8(cl_value)
        if not inner:
            return None
        return parse_risk_score_bytes(inner)
    except Exception as exc:
        logger.debug("read_risk_score(%s) failed: %s", address, exc)
        return None


async def read_recent_findings(
    limit: int = 20,
    contract_hash: Optional[str] = None,
) -> list[Dict[str, Any]]:
    """Read the latest ``limit`` findings from AuditTrail (newest first).

    Queries ``finding_count`` first, then reads IDs ``[count-limit+1 .. count]``
    in parallel. Skips any IDs that come back missing (defensive against gaps).
    Returns ``[]`` if the chain is unreachable or no findings exist.
    """
    count = await read_finding_count(contract_hash)
    if count is None or count <= 0:
        return []
    start = max(1, count - limit + 1)
    ids = list(range(start, count + 1))
    # Parallel reads — each is a free query_global_state call.
    findings = await asyncio.gather(
        *(read_finding(i, contract_hash) for i in ids),
        return_exceptions=False,
    )
    out: list[Dict[str, Any]] = []
    for f in findings:
        if isinstance(f, dict):
            out.append(f)
    # Newest first (highest id first).
    out.sort(key=lambda f: f.get("id", 0), reverse=True)
    return out


def reset_caches() -> None:
    """Clear the state-root-hash + state-URef caches (for tests)."""
    _state_root_cache["value"] = None
    _state_root_cache["expires_at"] = 0.0
    _state_uref_cache.clear()


__all__ = [
    "CASPER_RPC_URL",
    "AUDIT_TRAIL_HASH_DEFAULT",
    "RISK_ORACLE_HASH_DEFAULT",
    "AUDIT_TRAIL_FINDINGS_INDEX",
    "AUDIT_TRAIL_FINDING_COUNT_INDEX",
    "RISK_ORACLE_SCORES_INDEX",
    "compute_var_dict_address",
    "compute_mapping_dict_address",
    "encode_u64_key",
    "encode_string_key",
    "parse_finding_bytes",
    "parse_risk_score_bytes",
    "parse_u64_bytes",
    "read_finding_count",
    "read_finding",
    "read_risk_score",
    "read_recent_findings",
    "reset_caches",
]
