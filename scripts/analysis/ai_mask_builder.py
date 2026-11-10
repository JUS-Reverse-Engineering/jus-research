#!/usr/bin/env python3
"""ai_mask_builder.py -- reproduce the AI availability-mask builder from ROM data.

The builder is ov11 `0x02174330`, first loop `0x021747EC`-`0x0217491C`. For every
behaviour id 1..23 it looks up that id's AIPM record, walks the record's 32-byte
sub-records, and ORs the id's bit into one of nine words depending on three
values computed from the sub-record's four leading s16 fields:

    A = s16[+0x00] + s16[+0x04]      -> +0x84 (<0x50) / +0x88 (0x50..0xA0) / +0x8C (>=0xA0)
    B = s16[+0x02] - s16[+0x06]      -> +0x90 / +0x94 / +0x98
    C = s16[+0x02] + s16[+0x06]      -> +0x9C / +0xA0 / +0xA4

The `AI+0x48` pick reads the three `<0x50` words (+0x84, +0x90, +0x9C) through
the band selector `AI+0x10A` (0 -> those three, 1 -> the middle three, 2 -> the
top three). So the sub-record quartet is what decides whether an attack id is
*eligible*, and it does so statically, per character, from ROM data.

This script reproduces the arithmetic offline and compares the result with the
words measured live in the freeze fixture (0xC4000001 / 0x023A01FF / 0x0000C100).

Caveats it cannot resolve statically:
  * the builder skips an id whose bit is already set in `[AI+0x74]`, a runtime
    mask; the reproduction assumes 0.
  * the loop covers ids 1..23 and sets bit `id`, so it cannot produce bit 0 or
    bits >= 24. The measured words have bits 0, 30 and 31 set, so a second
    writer exists and this script does not model it.

Read-only.  Usage:
  python3 scripts/analysis/ai_mask_builder.py op_b_03
  python3 scripts/analysis/ai_mask_builder.py op_b_03 --expect 0xC4000001,0x023A01FF,0x0000C100
  python3 scripts/analysis/ai_mask_builder.py --all --summary
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AI_DIR = ROOT / "jus_files" / "chrbin" / "chr" / "ai"

sys.path.insert(0, str(Path(__file__).parent))
from move_records import dscp  # noqa: E402

BAND_CUTS = (0x50, 0xA0)
WORDS = ("+0x84", "+0x88", "+0x8C",
         "+0x90", "+0x94", "+0x98",
         "+0x9C", "+0xA0", "+0xA4")
BAND0 = (0, 3, 6)          # the three `<0x50` words the clamp reads


def band_of(v: int) -> int:
    """0 if v < 0x50, 1 if 0x50 <= v < 0xA0, 2 if v >= 0xA0. Signed compare."""
    if v >= BAND_CUTS[1]:
        return 2
    if v < BAND_CUTS[0]:
        return 0
    return 1


def load_block(token: str) -> bytes:
    p = AI_DIR / f"{token}.bin"
    block = dscp(p.read_bytes())
    if block[:4] != b"AIPM":
        raise SystemExit(f"{p}: payload does not start with AIPM")
    return block


def slot_offset(block: bytes, slot: int) -> int | None:
    off = struct.unpack_from("<i", block, 0x08 + slot * 4)[0]
    return None if off < 0 else off


def subrecords(block: bytes, slot: int):
    """Yield (index, bytes32) for a slot's sub-records; empty if absent/empty."""
    off = slot_offset(block, slot)
    if off is None:
        return
    rec = block[off:]
    if rec[0x04] != slot:
        raise SystemExit(f"slot {slot}: self-index {rec[0x04]} != {slot}")
    count = rec[0x0C] & 0xFF
    for i in range(count):
        yield i, rec[0x9C + 32 * i: 0x9C + 32 * i + 32]


def s16(b: bytes, o: int) -> int:
    return struct.unpack_from("<h", b, o)[0]


def build(block: bytes):
    """Return (words[9], per_id) exactly as the first loop would."""
    words = [0] * 9
    per_id = {}
    for bid in range(1, 24):
        slot = bid - 1
        triples = []
        for _i, sr in subrecords(block, slot):
            a = s16(sr, 0x00) + s16(sr, 0x04)
            b = s16(sr, 0x02) - s16(sr, 0x06)
            c = s16(sr, 0x02) + s16(sr, 0x06)
            triples.append((a, b, c))
            for row, val in enumerate((a, b, c)):
                words[row * 3 + band_of(val)] |= 1 << bid
        if triples:
            per_id[bid] = triples
    return words, per_id


def show(token: str, expect: list[int] | None) -> dict:
    block = load_block(token)
    words, per_id = build(block)
    print(f"# {token}.bin  AIPM payload {len(block)} bytes")
    print("#   word     value       bits (1..23)")
    for i, name in enumerate(WORDS):
        bits = [b for b in range(1, 24) if words[i] >> b & 1]
        star = "  <- band 0 (read by the clamp)" if i in BAND0 else ""
        print(f"#   {name:<6} 0x{words[i]:08X}  {bits}{star}")
    if expect:
        trio = [words[i] for i in BAND0]
        print(f"# expected (measured live) 0x{expect[0]:08X} 0x{expect[1]:08X} 0x{expect[2]:08X}")
        print(f"# reproduced              "
              f"0x{trio[0]:08X} 0x{trio[1]:08X} 0x{trio[2]:08X}")
        print("# MATCH" if trio == expect else "# MISMATCH")
    print()
    print("# id  slot  n  sub-record (A=s16[0]+s16[4], B=s16[2]-s16[6], C=s16[2]+s16[6])  bands")
    for bid in range(1, 24):
        slot = bid - 1
        tr = per_id.get(bid)
        if tr is None:
            print(f"  {bid:>3}  {slot:>4}  0  (absent or empty)")
            continue
        rows = []
        for (a, b, c) in tr:
            rows.append(f"A={a:>6}(b{band_of(a)}) B={b:>6}(b{band_of(b)}) C={c:>6}(b{band_of(c)})")
        print(f"  {bid:>3}  {slot:>4} {len(tr):>2}  " + " | ".join(rows))
    return {"token": token, "words": words}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("token", nargs="?", help="e.g. op_b_03 (file chr/ai/<token>.bin)")
    ap.add_argument("--all", action="store_true", help="every _b_ file, summary only")
    ap.add_argument("--expect", help="comma-separated 0x84,0x90,0x9C to compare")
    ap.add_argument("--live", help="comma-separated nine live words w0..w8; "
                                   "finds which files reproduce bits 1..14")
    ap.add_argument("--summary", action="store_true", help="one line per file")
    a = ap.parse_args()

    expect = None
    if a.expect:
        expect = [int(x, 0) for x in a.expect.split(",")]

    if a.live:
        live = [int(x, 0) for x in a.live.split(",")]
        if len(live) != 9:
            ap.error("--live needs nine words")
        # The builder's loop skips any id whose bit is set in [ctx+0x74]; in the
        # fixture that mask is 0x007F8000 (ids 15..22), so those bits come from an
        # earlier phase this script does not model. Compare bits 1..14 only.
        LO, HI = 1, 14
        keep = sum(1 << i for i in range(LO, HI + 1))
        print(f"# live    " + " ".join(f"{w:08X}" for w in live))
        print(f"# comparing bits {LO}..{HI} only (ids 15..22 are skipped by the "
              f"loop in the fixture, mask 0x007F8000)")
        hits = []
        for f in sorted(AI_DIR.glob("*_b_*.bin")):
            try:
                w, _ = build(load_block(f.stem))
            except SystemExit:
                continue
            if all((w[i] & keep) == (live[i] & keep) for i in range(9)):
                hits.append(f.stem)
        if hits:
            print(f"# MATCH on bits {LO}..{HI}: {', '.join(hits)}")
            w, _ = build(load_block(hits[0]))
            print("# reproduced " + " ".join(f"{x:08X}" for x in w))
        else:
            print(f"# NO file reproduces bits {LO}..{HI}")
            # show the closest
            best = None
            for f in sorted(AI_DIR.glob("*_b_*.bin")):
                try:
                    w, _ = build(load_block(f.stem))
                except SystemExit:
                    continue
                d = sum(bin((w[i] ^ live[i]) & keep).count("1") for i in range(9))
                if best is None or d < best[0]:
                    best = (d, f.stem, w)
            if best:
                print(f"# closest: {best[1]} with {best[0]} differing bits in 1..14")
                print("# reproduced " + " ".join(f"{x:08X}" for x in best[2]))
        return 0

    if a.all:
        files = sorted(AI_DIR.glob("*_b_*.bin"))
        print(f"# {len(files)} _b_ files.  For each band b the pick does "
              f"(w[3b]|w[3b+1]|w[3b+2]) & 0x7E; that is the choice set's ids 1..6 mask.")
        print(f"{'file':<10} {'band0':<9} {'band1':<9} {'band2':<9} band0_or  band0_ids")
        all7e = True
        for f in files:
            try:
                w, _ = build(load_block(f.stem))
            except SystemExit as e:
                print(f"{f.stem:<10} ERROR {e}")
                continue
            m = [(w[3 * b] | w[3 * b + 1] | w[3 * b + 2]) & 0x7E for b in range(3)]
            all7e = all7e and all(x == 0x7E for x in m)
            ids = [i for i in range(1, 7) if (w[0] | w[3] | w[6]) >> i & 1]
            print(f"{f.stem:<10} {m[0]:08X}  {m[1]:08X}  {m[2]:08X}  "
                  f"{(w[0]|w[3]|w[6]):08X}  {ids}")
        print(f"# every band yields 0x7E for every file: {all7e}")
        return 0

    if not a.token:
        ap.error("give a token or --all")
    show(a.token, expect)
    return 0


if __name__ == "__main__":
    sys.exit(main())
