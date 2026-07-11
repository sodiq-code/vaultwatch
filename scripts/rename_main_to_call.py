#!/usr/bin/env python3
"""Rename 'main' export to 'call' in each WASM file (Casper 2.x requirement)."""
from __future__ import annotations
import sys
from pathlib import Path

def read_leb128(data, offset):
    result = 0; shift = 0
    while True:
        byte = data[offset]; offset += 1
        result |= (byte & 0x7F) << shift
        if (byte & 0x80) == 0: break
        shift += 7
    return result, offset

def write_leb128(value):
    result = []
    while True:
        byte = value & 0x7F
        value >>= 7
        if value == 0: result.append(byte); break
        else: result.append(byte | 0x80)
    return bytes(result)

def rename_main_to_call(data):
    if len(data) < 8 or data[:4] != b"\x00asm":
        return data, False
    output = bytearray(data[:8])
    offset = 8
    was_renamed = False
    while offset < len(data):
        section_id, offset = read_leb128(data, offset)
        section_size, offset = read_leb128(data, offset)
        section_body = data[offset : offset + section_size]
        if section_id == 7 and not was_renamed:
            new_body = bytearray()
            j = 0
            num_exports, j = read_leb128(section_body, j)
            new_body.extend(write_leb128(num_exports))
            for _ in range(num_exports):
                name_len, j = read_leb128(section_body, j)
                name = section_body[j : j + name_len]
                j += name_len
                if name == b"main":
                    new_name = b"call"
                    was_renamed = True
                else:
                    new_name = name
                new_body.extend(write_leb128(len(new_name)))
                new_body.extend(new_name)
                export_kind = section_body[j]
                new_body.append(export_kind)
                j += 1
                idx, j = read_leb128(section_body, j)
                new_body.extend(write_leb128(idx))
            new_body.extend(section_body[j:])
            section_body = bytes(new_body)
        output.append(section_id)
        output.extend(write_leb128(len(section_body)))
        output.extend(section_body)
        offset += section_size
    return bytes(output), was_renamed

if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "contracts/wasm")
    wasm_files = sorted(target.glob("*.wasm")) if target.is_dir() else [target]
    print(f"[rename] processing {len(wasm_files)} WASM file(s)…")
    for wasm_path in wasm_files:
        data = wasm_path.read_bytes()
        new_data, was_renamed = rename_main_to_call(data)
        if was_renamed:
            wasm_path.write_bytes(new_data)
            print(f"  ✅ {wasm_path.name:30s} renamed 'main' → 'call'")
        elif b"call" in data:
            print(f"  ⏭️  {wasm_path.name:30s} already has 'call'")
        else:
            print(f"  ❌ {wasm_path.name:30s} no 'main' found")
    print("✅ Done")
