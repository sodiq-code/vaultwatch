#!/usr/bin/env python3
"""
VaultWatch WASM bulk-memory patcher v4 — dynamic index extraction.
"""

from __future__ import annotations
import sys
from pathlib import Path


def read_uleb(data, i):
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


def read_sleb(data, i):
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


def write_uleb(value):
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value == 0:
            out.append(byte)
            break
        else:
            out.append(byte | 0x80)
    return bytes(out)


def find_func_indices(data):
    i = 8
    while i < len(data):
        sec_id = data[i]
        i += 1
        size, i = read_uleb(data, i)
        if sec_id == 7:
            count, j = read_uleb(data, i)
            indices = {}
            for _ in range(count):
                name_len, j = read_uleb(data, j)
                name = data[j : j + name_len].decode("utf-8", "replace")
                j += name_len
                kind = data[j]
                j += 1
                idx, j = read_uleb(data, j)
                if kind == 0:
                    indices[name] = idx
            return indices
        i += size
    return {}


def skip_instruction(data, i):
    op = data[i]
    i += 1
    if op == 0xFC:
        sub, i = read_uleb(data, i)
        if sub <= 0x07:
            return i
        if sub == 0x08:
            _, i = read_uleb(data, i)
            i += 1
            return i
        if sub == 0x09:
            _, i = read_uleb(data, i)
            return i
        if sub == 0x0A:
            _, i = read_uleb(data, i)
            _, i = read_uleb(data, i)
            return i
        if sub == 0x0B:
            _, i = read_uleb(data, i)
            return i
        if sub == 0x0C:
            _, i = read_uleb(data, i)
            _, i = read_uleb(data, i)
            return i
        if sub == 0x0D:
            _, i = read_uleb(data, i)
            _, i = read_uleb(data, i)
            return i
        if sub == 0x0E:
            _, i = read_uleb(data, i)
            return i
        if sub == 0x0F:
            _, i = read_uleb(data, i)
            return i
        if sub in (0x10, 0x11, 0x12, 0x13, 0x14):
            _, i = read_uleb(data, i)
            return i
        raise ValueError(f"unknown 0xFC sub {sub} at byte {i}")
    if op == 0xFD:
        sub, i = read_uleb(data, i)
        raise ValueError(f"SIMD 0xFD {sub} at byte {i}")
    if op == 0xFE:
        sub, i = read_uleb(data, i)
        if sub <= 0x0E:
            _, i = read_uleb(data, i)
            _, i = read_uleb(data, i)
            return i
        if sub in (0x30, 0x31):
            _, i = read_uleb(data, i)
            return i
        if sub in (0x32, 0x33):
            i += 1
            return i
        raise ValueError(f"atomic 0xFE {sub} at byte {i}")
    if op == 0xFB:
        sub, i = read_uleb(data, i)
        if sub == 0x00:
            bt = data[i]
            if bt == 0x40 or (0x7C <= bt <= 0x7F):
                i += 1
            else:
                _, i = read_sleb(data, i)
            return i
        if sub == 0x01:
            _, i = read_uleb(data, i)
            return i
        if sub == 0x02:
            return i
        if sub in (0x03, 0x04, 0x05, 0x06, 0x07):
            _, i = read_uleb(data, i)
            return i
        raise ValueError(f"exception 0xFB {sub} at byte {i}")
    if op in (0x00, 0x01, 0x05, 0x0B, 0x0F, 0x1A, 0x1B):
        return i
    if op in (0x02, 0x03, 0x04):
        bt = data[i]
        if bt == 0x40 or (0x7C <= bt <= 0x7F):
            i += 1
        else:
            _, i = read_sleb(data, i)
        return i
    if op in (0x0C, 0x0D):
        _, i = read_uleb(data, i)
        return i
    if op == 0x0E:
        n, i = read_uleb(data, i)
        for _ in range(n + 1):
            _, i = read_uleb(data, i)
        return i
    if op == 0x10:
        _, i = read_uleb(data, i)
        return i
    if op == 0x11:
        _, i = read_uleb(data, i)
        _, i = read_uleb(data, i)
        return i
    if op == 0x1C:
        n, i = read_uleb(data, i)
        i += n
        return i
    if 0x20 <= op <= 0x26:
        _, i = read_uleb(data, i)
        return i
    if 0x28 <= op <= 0x3E:
        _, i = read_uleb(data, i)
        _, i = read_uleb(data, i)
        return i
    if op in (0x3F, 0x40):
        i += 1
        return i
    if op == 0x41:
        _, i = read_sleb(data, i)
        return i
    if op == 0x42:
        _, i = read_sleb(data, i)
        return i
    if op == 0x43:
        i += 4
        return i
    if op == 0x44:
        i += 8
        return i
    if op == 0xD0:
        i += 1
        return i
    if op == 0xD1:
        return i
    if op == 0xD2:
        _, i = read_uleb(data, i)
        return i
    if 0x45 <= op <= 0xC4:
        return i
    if 0xD3 <= op <= 0xD7:
        return i
    raise ValueError(f"unknown opcode 0x{op:02x} at byte {i - 1}")


def patch_instructions(instr, repl_copy, repl_fill, repl_table):
    out = bytearray()
    i = 0
    n = len(instr)
    stats = {"memory.copy": 0, "memory.fill": 0, "table.fill": 0}
    while i < n:
        if i + 1 < n and instr[i] == 0xFC:
            sub_byte = instr[i + 1]
            if sub_byte < 0x80:
                if sub_byte == 0x0A:
                    j = i + 2
                    mem_dst, j = read_uleb(instr, j)
                    mem_src, j = read_uleb(instr, j)
                    if mem_dst == 0 and mem_src == 0:
                        out.extend(repl_copy)
                        stats["memory.copy"] += 1
                        i = j
                        continue
                elif sub_byte == 0x0B:
                    j = i + 2
                    mem_dst, j = read_uleb(instr, j)
                    if mem_dst == 0:
                        out.extend(repl_fill)
                        stats["memory.fill"] += 1
                        i = j
                        continue
                elif sub_byte == 0x09:
                    j = i + 2
                    _, j = read_uleb(instr, j)
                    out.extend(repl_table)
                    stats["table.fill"] += 1
                    i = j
                    continue
        next_i = skip_instruction(instr, i)
        out.extend(instr[i:next_i])
        i = next_i
    return bytes(out), stats


def patch_wasm(in_path, out_path):
    data = Path(in_path).read_bytes()
    assert data[:4] == b"\x00asm"
    assert data[4:8] == b"\x01\x00\x00\x00"
    indices = find_func_indices(data)
    memcpy_idx = indices.get("memcpy")
    memset_idx = indices.get("memset")
    if memcpy_idx is None or memset_idx is None:
        raise RuntimeError("memcpy/memset not in exports")
    print(f"Found memcpy={memcpy_idx}, memset={memset_idx}")
    repl_copy = b"\x10" + write_uleb(memcpy_idx) + b"\x1a"
    repl_fill = b"\x10" + write_uleb(memset_idx) + b"\x1a"
    repl_table = b"\x1a\x1a\x1a"
    output = bytearray(data[:8])
    i = 8
    total = {"memory.copy": 0, "memory.fill": 0, "table.fill": 0}
    while i < len(data):
        sec_id = data[i]
        i += 1
        sec_size, i = read_uleb(data, i)
        sec_body = data[i : i + sec_size]
        i += sec_size
        if sec_id == 10:
            j = 0
            func_count, j = read_uleb(sec_body, j)
            new_body = bytearray(write_uleb(func_count))
            for fi in range(func_count):
                body_size, j = read_uleb(sec_body, j)
                body_bytes = sec_body[j : j + body_size]
                j += body_size
                k = 0
                local_count, k = read_uleb(body_bytes, k)
                for _ in range(local_count):
                    _, k = read_uleb(body_bytes, k)
                    k += 1
                locals_bytes = body_bytes[:k]
                instr_bytes = body_bytes[k:]
                try:
                    new_instr, stats = patch_instructions(instr_bytes, repl_copy, repl_fill, repl_table)
                except ValueError as e:
                    print(f"  WARN func #{fi}: {e} - verbatim")
                    new_instr = instr_bytes
                    stats = {"memory.copy": 0, "memory.fill": 0, "table.fill": 0}
                for key in total:
                    total[key] += stats[key]
                new_func = locals_bytes + new_instr
                new_body.extend(write_uleb(len(new_func)))
                new_body.extend(new_func)
            sec_body = bytes(new_body)
        output.append(sec_id)
        output.extend(write_uleb(len(sec_body)))
        output.extend(sec_body)
    Path(out_path).write_bytes(bytes(output))
    return total


if __name__ == "__main__":
    in_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else in_path
    stats = patch_wasm(in_path, out_path)
    print(f"Patched: memory.copy={stats['memory.copy']} memory.fill={stats['memory.fill']} table.fill={stats['table.fill']}")
