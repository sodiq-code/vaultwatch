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


def scan_code_section_for_bulk_memory(code_section: bytes) -> list[str]:
    """Scan the WASM code section (id 10) for bulk-memory opcodes.

    The code section contains N function bodies, each: size + locals + expr.
    We walk the bytes looking for the 0xFC prefix (multi-byte opcodes used by
    bulk-memory) followed by one of the bulk-memory sub-opcodes, plus the
    standalone 0x0F (table.grow).
    """
    findings: list[str] = []
    i = 0
    n = len(code_section)
    while i < n:
        byte = code_section[i]
        if byte == 0xFC:
            # Multi-byte opcode: 0xFC followed by a LEB128 sub-opcode
            if i + 1 < n:
                sub = code_section[i + 1]
                # Sub-opcodes < 128 are single-byte; we only care about the
                # bulk-memory ones (0x09..0x0f)
                key = 0x0FC00 + sub
                if key in BULK_MEMORY_OPCODES:
                    findings.append(f"0xFC 0x{sub:02x} ({BULK_MEMORY_OPCODES[key]}) at byte {i}")
            i += 2
            continue
        # Note: we deliberately do NOT flag table.grow (0x0f) alone — Casper's
        # wasmi accepts table.grow in some builds. The bulk-memory proposal
        # proper is the 0xFC-prefixed family. If Casper rejects table.grow in
        # your specific testnet version, uncomment the next 3 lines:
        # if byte == TABLE_GROW:
        #     findings.append(f"0x0f (table.grow) at byte {i}")
        i += 1
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
