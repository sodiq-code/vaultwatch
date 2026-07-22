#!/usr/bin/env python3
"""Dump WASM section sizes, import count, and full export table for each
VaultWatch contract. Equivalent to `wasm-objdump -x` for audit-proof purposes
(wasm-objdump / wabt is unavailable in this environment)."""
from __future__ import annotations
import hashlib
import sys
from pathlib import Path


def read_uleb(data: bytes, i: int):
    r = 0; s = 0
    while True:
        b = data[i]; i += 1
        r |= (b & 127) << s
        if b < 128:
            return r, i
        s += 7


def skip_valtype(data, i):
    """Skip a single value type byte (WASM valtypes are 1 byte in practice)."""
    i += 1
    return i


def skip_limits(data, i):
    flag = data[i]; i += 1
    _min, i = read_uleb(data, i)
    if flag & 1:
        _max, i = read_uleb(data, i)
    return i


def parse_import_entry(data, i):
    ml, i = read_uleb(data, i)
    mod = data[i:i+ml].decode('utf-8', 'replace'); i += ml
    nl, i = read_uleb(data, i)
    name = data[i:i+nl].decode('utf-8', 'replace'); i += nl
    kind = data[i]; i += 1
    if kind == 0:  # func — typeidx
        _t, i = read_uleb(data, i)
    elif kind == 1:  # table — elemtype + limits
        i += 1  # elemtype (0x70 = funcref)
        i = skip_limits(data, i)
    elif kind == 2:  # memory — limits
        i = skip_limits(data, i)
    elif kind == 3:  # global — valtype + mut
        i = skip_valtype(data, i)
        i += 1  # mut
    return mod, name, kind, i


def parse(path: Path) -> str:
    data = path.read_bytes()
    lines = [f"File: {path.name}",
             f"Size: {len(data)} bytes ({len(data)/1024:.1f} KB)",
             f"sha256: {hashlib.sha256(data).hexdigest()}"]
    assert data[:4] == b'\x00asm', "not a wasm"
    lines.append(f"Magic: {data[:4].hex()}  Version: {data[4:8].hex()}")
    i = 8
    secnames = {0: 'Custom', 1: 'Type', 2: 'Import', 3: 'Function', 4: 'Table',
                5: 'Memory', 6: 'Global', 7: 'Export', 8: 'Start', 9: 'Element',
                10: 'Code', 11: 'Data', 12: 'DataCount', 13: 'Tag'}
    sections = {}
    exports = []
    import_count = 0
    casper_imports = 0
    while i < len(data):
        sid = data[i]; i += 1
        sz, i = read_uleb(data, i)
        body = data[i:i+sz]; i += sz
        name = secnames.get(sid, f'Unknown({sid})')
        sections[name] = sz
        if sid == 2:  # Import
            j = 0
            cnt, j = read_uleb(body, j)
            import_count = cnt
            for _ in range(cnt):
                mod, nm, kind, j = parse_import_entry(body, j)
                if mod == 'env':
                    casper_imports += 1
        if sid == 7:  # Export
            j = 0
            cnt, j = read_uleb(body, j)
            for _ in range(cnt):
                nl, j = read_uleb(body, j)
                nm = body[j:j+nl].decode('utf-8', 'replace'); j += nl
                kind = body[j]; j += 1
                idx, j = read_uleb(body, j)
                exports.append((nm, kind, idx))
    lines.append("Sections:")
    for n, sz in sorted(sections.items(), key=lambda x: -x[1]):
        lines.append(f"  {n:12s} {sz:>8} bytes")
    lines.append(f"Imports: {import_count}  (env / casper_* host functions: {casper_imports})")
    lines.append(f"Exports: {len(exports)}")
    kind_name = {0: 'func', 1: 'table', 2: 'memory', 3: 'global'}
    for nm, k, idx in sorted(exports):
        lines.append(f"  {kind_name.get(k, '?'):7s} {nm}")
    return "\n".join(lines)


def main():
    wasm_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("contracts/wasm")
    contracts = ["AgentBehaviorIndex", "AuditTrail", "RiskOracle", "RiskPolicyManager",
                 "RiskPolicyManagerV2", "SentinelAlertLog", "SentinelCredit",
                 "SentinelRegistry", "SubscriberVault"]
    for c in contracts:
        print(parse(wasm_dir / f"{c}.wasm"))
        print()
        print("-" * 78)
        print()


if __name__ == "__main__":
    main()
