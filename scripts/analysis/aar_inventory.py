#!/usr/bin/env python3
"""Inventory and extract ALAR v2 containers (`.aar` files) with a real
per-entry file-info table, e.g. `efc/comm_*.aar` and `battle/{ko,get,hand,
marker_b,marker_t}.aar`.

Why (jus-atns.2): `scripts/analysis/extract_alar.py`'s `parse_v2()` assumes
an 8-byte no-name entry table starting at offset 0x0C, which is wrong for
every file this tool targets (they all have flags 0x01 or 0x03, i.e. "has
filenames" set) -- running it on `comm_a.aar` produced offsets/sizes far
past EOF. This is a FRESH parser (not a patch of extract_alar.py) written
from scratch by hex-dumping these specific files and cross-checking every
field against real byte offsets, magic bytes found at the offsets those
fields claim, and file-size bounds. It was independently cross-verified
against the public ALAR v2 spec and file tree in the sibling `JUSToolkit`
project at `../JUSToolkit/docs/articles/specs/alar.md` and
`../JUSToolkit/src/JUS.Tool/Containers/Converters/Binary2Alar2.cs` (external
reference only -- no code copied from there; see ASSETS.md's conditions
section) and matches its documented layout, plus its published file-tree
dump names our own decoded filenames exactly.

Confirmed v2 layout (verified against all 9 target files' real bytes):
    0x00 char[4] "ALAR"
    0x04 byte    version (2)
    0x05 byte    feature flags (bit0=has filenames, others unconfirmed
                  here; values seen: 0x01, 0x03)
    0x06 ushort  file count N
    0x08 uint    firstFileId (informational, not used for parsing)
    0x0C uint    lastFileId  (informational, not used for parsing)
    0x10 ... N entries, 16 bytes each, no gaps between them:
        +0x00 uint fileId -- top byte is a type tag (0x40=DSTX, 0x41=ALMT,
              0x42=DSIG, 0x43=ALOD seen in this game's files; low 3 bytes
              repeat the same "archive id" across every entry in one file)
        +0x04 uint dataOffset (absolute, from the start of the .aar)
        +0x08 uint dataSize
        +0x0C uint flags -- bit31 (0x80000000) set means this entry has an
              embedded name; the name lives in the 0x24 bytes *immediately
              before* dataOffset, laid out as [2 pad bytes][32-byte
              NUL-padded ASCII name][2-byte hash], i.e. the readable name
              text starts at `dataOffset - 0x22`.

This was NOT guessed from a spec first -- it was derived by hex-dumping
`battle/ko.aar` and `efc/comm_a.aar`, noticing the repeating `[00,00,ID,tag]`
words and the plaintext filenames sitting right before each entry's magic
bytes (`DSTX`, `ALMT`, `ALOD`, `DSIG`), then generalized and validated
against all 9 files (every dataOffset/dataSize pair lies inside the file
and every dataOffset's 4 bytes are a real, known magic).

Usage:
    python3 scripts/analysis/aar_inventory.py <archive.aar> [--extract OUTDIR]
    python3 scripts/analysis/aar_inventory.py --selftest

Read-only on the input; only writes under --extract's output directory.
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

MAGIC_BY_TAG = {
    0x40: "DSTX", 0x41: "ALMT", 0x42: "DSIG", 0x43: "ALOD",
    0x45: "NCCL", 0x46: "ALTM", 0x47: "ALAR", 0x00: "(raw)",
}


def parse_alar_v2(b: bytes) -> dict:
    if b[:4] != b"ALAR":
        raise ValueError(f"not an ALAR container: magic={b[:4]!r}")
    version, flags = b[4], b[5]
    if version != 2:
        raise ValueError(f"unsupported ALAR version {version} (only v2 handled)")
    n = struct.unpack_from("<H", b, 6)[0]
    first_id, last_id = struct.unpack_from("<II", b, 8)

    entries = []
    for i in range(n):
        base = 0x10 + i * 16
        file_id, data_off, data_size, eflags = struct.unpack_from("<IIII", b, base)
        tag = (file_id >> 24) & 0xFF
        name = None
        if eflags & 0x80000000:
            name_region_start = data_off - 0x24
            name_start = name_region_start + 2
            if 0 <= name_region_start and data_off <= len(b):
                raw = b[name_start:name_start + 32]
                end = raw.find(b"\0")
                name = raw[:end if end != -1 else 32].decode("ascii", "replace")
        entries.append(dict(index=i, file_id=file_id, tag=tag,
                             type_guess=MAGIC_BY_TAG.get(tag, f"?0x{tag:02X}"),
                             offset=data_off, size=data_size, flags=eflags,
                             name=name,
                             magic=b[data_off:data_off + 4] if data_off + 4 <= len(b) else b"",
                             within_bounds=(data_off + data_size <= len(b))))
    return dict(version=version, flags=flags, count=n, first_id=first_id,
                last_id=last_id, entries=entries)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archive", type=Path, nargs="?")
    ap.add_argument("--extract", type=Path, help="extract entries into this dir")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if not args.archive:
        ap.error("archive required unless --selftest")

    b = args.archive.read_bytes()
    d = parse_alar_v2(b)
    print(f"{args.archive.name}: ALAR v{d['version']} flags={d['flags']:#04x} "
          f"count={d['count']} firstId={d['first_id']:#x} lastId={d['last_id']:#x} "
          f"({len(b)} bytes)")
    bad = [e for e in d["entries"] if not e["within_bounds"]]
    if bad:
        print(f"  WARNING: {len(bad)} entries exceed file bounds -- layout "
              f"assumption may not hold for this file", file=sys.stderr)
    for e in d["entries"]:
        nm = e["name"] if e["name"] is not None else "(no embedded name)"
        print(f"  [{e['index']}] type={e['type_guess']:<6s} magic={e['magic']!r:8s} "
              f"off={e['offset']:#x} size={e['size']:<7d} "
              f"within_bounds={e['within_bounds']} name={nm!r}")

    if args.extract:
        outdir = args.extract
        outdir.mkdir(parents=True, exist_ok=True)
        stem = args.archive.stem
        for e in d["entries"]:
            if not e["within_bounds"]:
                continue
            base_name = e["name"] or f"{stem}_entry{e['index']:02d}"
            base_name = Path(base_name).name  # strip any path components
            ext = e["type_guess"].strip("()").lower() if e["type_guess"] != "(raw)" else "bin"
            if "." not in base_name:
                base_name = f"{base_name}.{ext}"
            dest = outdir / base_name
            dest.write_bytes(b[e["offset"]:e["offset"] + e["size"]])
        print(f"\nextracted {sum(1 for e in d['entries'] if e['within_bounds'])} "
              f"entries to {outdir}")

    return 0


def selftest() -> int:
    """Synthetic ALAR v2 archive with one named entry, checked in memory."""
    name = b"test.dtx" + b"\0" * (32 - len(b"test.dtx"))
    name_region = b"\0\0" + name + b"\0\0"  # 2 pad + 32 name + 2 hash = 0x24
    payload = b"DSTX" + b"\xAB" * 12
    data_off = 0x10 + 16 + len(name_region)
    header = (b"ALAR" + bytes([2, 0x01]) + struct.pack("<H", 1)
              + struct.pack("<II", 0x00AA0000, 0x00AA0000))
    entry = struct.pack("<IIII", 0x40AA0000, data_off, len(payload), 0x80000001)
    b = header + entry + name_region + payload
    d = parse_alar_v2(b)
    ok = (d["count"] == 1 and d["entries"][0]["name"] == "test.dtx"
          and d["entries"][0]["magic"] == b"DSTX"
          and d["entries"][0]["within_bounds"])
    print("selftest:", "PASS" if ok else "FAIL", d["entries"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
