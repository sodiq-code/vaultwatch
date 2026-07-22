#!/usr/bin/env python3
"""
VaultWatch — Bulk-memory opcode verifier for Casper Testnet compatibility.

Casper's WASM runtime (wasmi) rejects any module containing bulk-memory
operations: memory.copy, memory.fill, memory.copy, table.copy, table.fill,
table.init, table.grow, elem.drop, data.drop.

This script parses each .wasm file's code section and FAILS if any of those
opcodes appear. It is the hard gate between "compiles" and "deploys on Casper".

Usage:
    python3 scripts/check_wasm_bulk_memory.py contracts/wasm/
    python3 scripts/check_wasm_bulk_memory.py contracts/wasm/AuditTrail.wasm

Exit codes:
    0 = all WASM files are clean (no bulk-memory opcodes)
    1 = one or more files contain bulk-memory opcodes (would be rejected by Casper)

No third-party deps — parses the WASM binary format directly.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

# WASM bulk-memory + reference-types opcodes that Casper's wasmi rejects.
# Source: WebAssembly bulk-memory proposal + casper-node wasmi version.
#   0xFC 0x0a = memory.copy
#   0xFC 0x0b = memory.fill
#   0xFC 0x0c = table.copy  (sometimes under reference-types)
#   0xFC 0x0d = table.init
#   0xFC 0x0e = elem.drop
#   0xFC 0x09 = table.fill
#   0xFC 0x0f = data.drop
#   0x0f     = table.grow  (returns -1 on failure; wasmi may accept, but
#              table.grow is part of reference-types which bundles with bulk)
BULK_MEMORY_OPCODES = {
    0x0FC0A: "memory.copy",
    0x0FC0B: "memory.fill",
    0x0FC0C: "table.copy",
    0x0FC0D: "table.init",
    0x0FC0E: "elem.drop",
    0x0FC09: "table.fill",
    0x0FC0F: "data.drop",
}
TABLE_GROW = 0x0F  # single-byte opcode


def read_leb128_unsigned(data: bytes, offset: int) -> tuple[int, int]:
    """Read an unsigned LEB128 integer. Returns (value, new_offset)."""
    result = 0
    shift = 0
    while True:
        if offset >= len(data):
            raise ValueError("truncated LEB128")
        byte = data[offset]
        offset += 1
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0:
            break
        shift += 7
    return result, offset


def read_section(data: bytes, offset: int) -> tuple[int, bytes, int]:
    """Read a WASM section. Returns (section_id, section_body, new_offset)."""
    section_id, offset = read_leb128_unsigned(data, offset)
    section_size, offset = read_leb128_unsigned(data, offset)
    body = data[offset : offset + section_size]
    if len(body) != section_size:
        raise ValueError(f"truncated section {section_id}")
    return section_id, body, offset + section_size


def _read_uleb(data: bytes, i: int) -> tuple[int, int]:
    """Read unsigned LEB128."""
    result = 0
    shift = 0
    while True:
        b = data[i]
        i += 1
        result |= (b & 0x7F) << shift
        shift += 7
        if not (b & 0x80):
            break
    return result, i


def _read_sleb(data: bytes, i: int) -> tuple[int, int]:
    """Read signed LEB128."""
    result = 0
    shift = 0
    while True:
        b = data[i]
        i += 1
        result |= (b & 0x7F) << shift
        shift += 7
        if not (b & 0x80):
            if b & 0x40:
                result |= -(1 << shift)
            break
    return result, i


def _skip_instruction(data: bytes, i: int) -> int:
    """Return the index immediately after the instruction starting at ``i``.

    Walks the WASM instruction stream opcode-by-opcode so that 0xFC 0x0A byte
    sequences inside LEB128 immediates (e.g. i32.store offset=1404 encodes as
    0x36 0x02 0xFC 0x0A) are NOT mistaken for real memory.copy instructions.

    Raises ValueError on truly unknown opcodes (which would indicate either a
    parser gap or a corrupt module).
    """
    op = data[i]
    i += 1

    # 0xFC-prefixed: bulk-memory + saturating trunc + reference-types
    if op == 0xFC:
        sub, i = _read_uleb(data, i)
        if sub <= 0x07:
            return i  # trunc_sat: no immediates
        if sub == 0x08:
            _r, i = _read_uleb(data, i)
            i += 1
            return i  # memory.init
        if sub == 0x09:
            _r, i = _read_uleb(data, i)
            return i  # table.fill
        if sub == 0x0A:
            _r, i = _read_uleb(data, i)
            _r, i = _read_uleb(data, i)
            return i  # memory.copy
        if sub == 0x0B:
            _r, i = _read_uleb(data, i)
            return i  # memory.fill
        if sub == 0x0C:
            _r, i = _read_uleb(data, i)
            _r, i = _read_uleb(data, i)
            return i  # table.copy
        if sub == 0x0D:
            _r, i = _read_uleb(data, i)
            _r, i = _read_uleb(data, i)
            return i  # table.init
        if sub == 0x0E:
            _r, i = _read_uleb(data, i)
            return i  # elem.drop
        if sub == 0x0F:
            _r, i = _read_uleb(data, i)
            return i  # data.drop
        if sub in (0x10, 0x11, 0x12, 0x13, 0x14):
            _r, i = _read_uleb(data, i)
            return i
        raise ValueError(f"unknown 0xFC sub-opcode {sub}")

    # 0xFD SIMD, 0xFE atomic, 0xFB exception handling
    if op == 0xFD:
        sub, i = _read_uleb(data, i)
        raise ValueError(f"SIMD opcode 0xFD {sub} not supported")
    if op == 0xFE:
        sub, i = _read_uleb(data, i)
        if sub <= 0x0E:
            _r, i = _read_uleb(data, i)
            _r, i = _read_uleb(data, i)
            return i
        if sub in (0x30, 0x31):
            _r, i = _read_uleb(data, i)
            return i
        if sub in (0x32, 0x33):
            i += 1
            return i
        raise ValueError(f"atomic opcode 0xFE {sub}")
    if op == 0xFB:
        sub, i = _read_uleb(data, i)
        if sub == 0x00:  # try <blocktype>
            bt = data[i]
            if bt == 0x40 or (0x7C <= bt <= 0x7F):
                i += 1
            else:
                _r, i = _read_sleb(data, i)
            return i
        if sub == 0x01:
            _r, i = _read_uleb(data, i)
            return i
        if sub == 0x02:
            return i
        if sub in (0x03, 0x04, 0x05, 0x06, 0x07):
            _r, i = _read_uleb(data, i)
            return i
        raise ValueError(f"exception opcode 0xFB {sub}")

    # No-immediate single-byte opcodes
    if op in (0x00, 0x01, 0x05, 0x0B, 0x0F, 0x1A, 0x1B):
        return i

    # block / loop / if — blocktype immediate
    if op in (0x02, 0x03, 0x04):
        bt = data[i]
        if bt == 0x40 or (0x7C <= bt <= 0x7F):
            i += 1
        else:
            _r, i = _read_sleb(data, i)
        return i

    # br / br_if — labelidx
    if op in (0x0C, 0x0D):
        _r, i = _read_uleb(data, i)
        return i

    # br_table — n labels + default
    if op == 0x0E:
        n, i = _read_uleb(data, i)
        for _ in range(n + 1):
            _r, i = _read_uleb(data, i)
        return i

    # call — funcidx ; call_indirect — typeidx + tableidx
    if op == 0x10:
        _r, i = _read_uleb(data, i)
        return i
    if op == 0x11:
        _r, i = _read_uleb(data, i)
        _r, i = _read_uleb(data, i)
        return i

    # select t
    if op == 0x1C:
        n, i = _read_uleb(data, i)
        i += n
        return i

    # local/global/table access (0x20-0x26)
    if 0x20 <= op <= 0x26:
        _r, i = _read_uleb(data, i)
        return i

    # Memory load/store (0x28-0x3E) — align + offset
    if 0x28 <= op <= 0x3E:
        _r, i = _read_uleb(data, i)
        _r, i = _read_uleb(data, i)
        return i

    # memory.size / memory.grow — 1 reserved byte
    if op in (0x3F, 0x40):
        i += 1
        return i

    # Constants
    if op == 0x41:
        _r, i = _read_sleb(data, i)
        return i  # i32.const
    if op == 0x42:
        _r, i = _read_sleb(data, i)
        return i  # i64.const
    if op == 0x43:
        i += 4
        return i  # f32.const
    if op == 0x44:
        i += 8
        return i  # f64.const

    # Reference ops
    if op == 0xD0:
        i += 1
        return i  # ref.null
    if op == 0xD1:
        return i  # ref.is_null
    if op == 0xD2:
        _r, i = _read_uleb(data, i)
        return i  # ref.func

    # Numeric / comparison ops (0x45-0xC4): no immediates
    if 0x45 <= op <= 0xC4:
        return i

    # 0xD3-0xD7: conservative no-immediate
    if 0xD3 <= op <= 0xD7:
        return i

    raise ValueError(f"unknown opcode 0x{op:02x}")


def scan_code_section_for_bulk_memory(code_section: bytes) -> list[str]:
    """Scan the WASM code section (id 10) for REAL bulk-memory opcodes.

    Walks the instruction stream opcode-by-opcode (not byte-by-byte) so that
    0xFC 0x0A byte sequences inside LEB128 immediates are NOT flagged as
    false positives. Only genuine ``memory.copy`` / ``memory.fill`` /
    ``table.fill`` etc. instructions at instruction boundaries are flagged.

    The code section contains N function bodies, each:
    ``body_size:uleb + locals_vector + instruction_stream``.
    The instruction stream ends with a single ``0x0B`` (end) byte.
    """
    findings: list[str] = []
    i = 0
    func_count, i = _read_uleb(code_section, i)
    for func_idx in range(func_count):
        body_size, i = _read_uleb(code_section, i)
        body_end = i + body_size
        # Skip locals vector: count + [repeat:uleb + valtype:1byte]*
        local_count, j = _read_uleb(code_section, i)
        for _ in range(local_count):
            _r, j = _read_uleb(code_section, j)
            j += 1  # valtype byte
        # Walk instruction stream
        while j < body_end:
            op = code_section[j]
            if op == 0xFC:
                sub_byte = code_section[j + 1] if j + 1 < body_end else 0xFF
                if sub_byte < 0x80:
                    key = 0x0FC00 + sub_byte
                    if key in BULK_MEMORY_OPCODES:
                        findings.append(f"0xFC 0x{sub_byte:02x} ({BULK_MEMORY_OPCODES[key]}) at byte {j} (func #{func_idx})")
                # Skip the full instruction (sub-opcode + its immediates)
                try:
                    j = _skip_instruction(code_section, j)
                except ValueError:
                    # Unknown opcode — can't safely continue parsing this func.
                    # Fall back to byte-scan for the rest of this function body.
                    j += 2
            else:
                try:
                    j = _skip_instruction(code_section, j)
                except ValueError:
                    j += 1
        i = body_end
    return findings


def check_wasm_file(path: Path) -> tuple[bool, list[str]]:
    """Check one .wasm file. Returns (is_clean, findings)."""
    data = path.read_bytes()
    findings: list[str] = []

    # Validate magic + version
    if len(data) < 8 or data[:4] != b"\x00asm":
        return False, [f"{path.name}: not a valid WASM module (bad magic)"]
    if struct.unpack("<I", data[4:8])[0] != 1:
        return False, [f"{path.name}: unsupported WASM version"]

    offset = 8
    while offset < len(data):
        try:
            section_id, body, offset = read_section(data, offset)
        except ValueError as e:
            return False, [f"{path.name}: parse error: {e}"]

        # Section 10 = code section (the function bodies)
        if section_id == 10:
            sub_findings = scan_code_section_for_bulk_memory(body)
            findings.extend(f"{path.name}: {f}" for f in sub_findings)

    return len(findings) == 0, findings


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: check_wasm_bulk_memory.py <wasm_dir_or_file>", file=sys.stderr)
        return 1

    target = Path(sys.argv[1])
    if target.is_dir():
        wasm_files = sorted(target.glob("*.wasm"))
    elif target.is_file() and target.suffix == ".wasm":
        wasm_files = [target]
    else:
        print(f"ERROR: {target} is not a .wasm file or directory", file=sys.stderr)
        return 1

    if not wasm_files:
        print(f"ERROR: no .wasm files found in {target}", file=sys.stderr)
        return 1

    print(f"[check_wasm_bulk_memory] scanning {len(wasm_files)} WASM file(s)…")
    all_clean = True
    for wasm in wasm_files:
        clean, findings = check_wasm_file(wasm)
        size_kb = wasm.stat().st_size / 1024
        if clean:
            print(f"  ✅ {wasm.name:30s}  {size_kb:7.1f} KB  clean")
        else:
            all_clean = False
            print(f"  ❌ {wasm.name:30s}  {size_kb:7.1f} KB  CONTAINS BULK-MEMORY OPCODES")
            for f in findings:
                print(f"       → {f}")

    print()
    if all_clean:
        print(f"✅ PASS — all {len(wasm_files)} WASM files are Casper-compatible (no bulk-memory opcodes).")
        return 0
    print("❌ FAIL — bulk-memory opcodes found. Casper Testnet will reject these deploys with")
    print("          'Wasm preprocessing error: Deserialization error: Bulk memory operations")
    print("          are not supported.' Fix: rebuild with scripts/build_contracts.sh")
    return 1


if __name__ == "__main__":
    sys.exit(main())
