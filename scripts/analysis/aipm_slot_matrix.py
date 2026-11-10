#!/usr/bin/env python3
"""Tabulate which of the 23 AIPM behaviour slots each `chr/ai/*.bin` defines.

Backs `docs/research/side-quests/ai-behaviour-data-layout.md` §3. No emulator,
no ROM: reads the extracted corpus and reports, per slot:

  present    `array[slot]` is a real offset into the block AND the record's
             `+0x04` reads back the 0-based slot index
  populated  present AND `+0x0C` >= 1, i.e. the record carries >= 1 of the
             32-byte sub-records at `+0x9C`

`present` and `populated` are different questions and give different numbers; a
present-but-unpopulated record is a 0xBC-byte record whose single sub-record is
zeroed. Conflating them once produced a wrong "slot 0 is absent in 34 files"
reading: 5 files have slot 0 absent, 29 have it present and empty.

Usage:
    python3 scripts/analysis/aipm_slot_matrix.py                 # tables
    python3 scripts/analysis/aipm_slot_matrix.py who 10          # who populates slot 10
    python3 scripts/analysis/aipm_slot_matrix.py who 10 --all     # b and s both
"""
import argparse
import struct
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))
from move_records import dscp  # noqa: E402

AI_DIR = REPO / "jus_files" / "chrbin" / "chr" / "ai"
N_SLOTS = 23


def slot_table(path: Path):
    """-> list of 23 entries, each None or (self_index, sub_record_count)."""
    try:
        payload = dscp(path.read_bytes())
    except ValueError:
        return None  # ai_param.bin is not a DSCP container
    if payload[:4] != b"AIPM":
        return None
    arr = struct.unpack_from("<%dI" % N_SLOTS, payload, 0x08)
    out = []
    for i, off in enumerate(arr):
        if off == 0xFFFFFFFF or off < 0x64 or off + 0x0C >= len(payload):
            out.append(None)
            continue
        out.append((struct.unpack_from("<I", payload, off + 0x04)[0], payload[off + 0x0C]))
    return out


def load_corpus():
    table = {}
    for p in sorted(AI_DIR.glob("*.bin")):
        t = slot_table(p)
        if t is not None:
            table[p.name] = t
    return table


def koma(name: str) -> str:
    return name.split("_")[1]


def cmd_table(table):
    print("files: %d   (_b_ battle koma: %d, _s_ support koma: %d)"
          % (len(table), sum(1 for n in table if koma(n) == "b"),
             sum(1 for n in table if koma(n) == "s")))
    print("series prefixes: %d" % len({n.split("_")[0] for n in table}))
    mism = [(n, i, table[n][i][0]) for n in table for i in range(N_SLOTS)
            if table[n][i] is not None and table[n][i][0] != i]
    print("self-index mismatches (+0x04 vs slot): %d" % len(mism))
    print()
    print("slot  id  present   b    s | populated   b    s")
    for i in range(N_SLOTS):
        pres = [n for n in table if table[n][i] is not None]
        pop = [n for n in pres if table[n][i][1] >= 1]
        print(" %2d   %2d   %5d  %4d %4d |    %4d   %4d %4d"
              % (i, i + 1, len(pres),
                 sum(1 for n in pres if koma(n) == "b"),
                 sum(1 for n in pres if koma(n) == "s"),
                 len(pop),
                 sum(1 for n in pop if koma(n) == "b"),
                 sum(1 for n in pop if koma(n) == "s")))
    print()
    nb = [n for n in table if koma(n) == "b"]
    ns = [n for n in table if koma(n) == "s"]
    print("slots present in every _b_ file: %s"
          % [i for i in range(N_SLOTS) if all(table[n][i] is not None for n in nb)])
    print("slots present in every _s_ file: %s"
          % [i for i in range(N_SLOTS) if all(table[n][i] is not None for n in ns)])
    print("populated-slot-count dist  _b_: %s"
          % sorted(Counter(sum(1 for i in range(N_SLOTS)
                               if table[n][i] is not None and table[n][i][1] >= 1)
                           for n in nb).items()))
    print("populated-slot-count dist  _s_: %s"
          % sorted(Counter(sum(1 for i in range(N_SLOTS)
                               if table[n][i] is not None and table[n][i][1] >= 1)
                           for n in ns).items()))
    empty = [n for n in table
             if all(table[n][i] is None or table[n][i][1] == 0 for i in range(N_SLOTS))]
    print("files where every present slot is empty: %d %s" % (len(empty), sorted(empty)))


def cmd_who(table, slot, both):
    pop = [n for n in table if table[n][slot] is not None and table[n][slot][1] >= 1]
    if not both:
        pop = [n for n in pop if koma(n) == "b"]
    print("slot %d (id %d) populated in %d files:" % (slot, slot + 1, len(pop)))
    for n in sorted(pop):
        print("  %-16s sub-records=%d" % (n, table[n][slot][1]))
    print("prefixes: %s" % Counter(n.split("_")[0] for n in pop).most_common())


def subrecord_offset_18(path: Path, slot: int):
    """-> the u8 at sub-record +0x18 for one slot, or None if absent/empty."""
    t = slot_table(path)
    if t is None or t[slot] is None or t[slot][1] < 1:
        return None
    payload = dscp(path.read_bytes())
    off = struct.unpack_from("<I", payload, 0x08 + slot * 4)[0]
    at = off + 0x9C + 0x18
    return payload[at] if at < len(payload) else None


def cmd_fields(battle_only=True):
    """Distribution of sub-record +0x18 per slot, across the `_b_` files.

    Backs the data-layout doc's section 5 claim: +0x18 partitions the id space at
    id 13 (0 = empty record; ids 1-12 -> {1,2,3}; ids 13-22 -> {4,5}).
    """
    files = [p for p in sorted(AI_DIR.glob("*.bin"))
             if "_b_" in p.name or not battle_only]
    per = {}
    n_seen = Counter()
    for slot in range(N_SLOTS):
        c = Counter()
        for p in files:
            v = subrecord_offset_18(p, slot)
            if v is not None:
                c[v] += 1
        per[slot] = c
        n_seen[slot] = sum(c.values())
    print("sub-record +0x18 per slot over %d files (%s)"
          % (len(files), "_b_ battle komas" if battle_only else "all"))
    print("slot  id    n   histogram")
    for slot in range(N_SLOTS):
        if not per[slot]:
            continue
        print(" %2d  %2d  %4d   %s" % (slot, slot + 1, n_seen[slot],
                                       sorted(per[slot].items())))
    print()
    print("partition check -- which ids carry each value:")
    for v in sorted({k for c in per.values() for k in c}):
        ids = [s + 1 for s in range(N_SLOTS) if per[s].get(v)]
        print("  +0x18=0x%02X -> ids %s" % (v, ids))


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    who = sub.add_parser("who", help="list the files that populate one slot")
    who.add_argument("slot", type=int, choices=range(N_SLOTS))
    who.add_argument("--all", action="store_true", help="include _s_ files")
    fields = sub.add_parser("fields", help="per-slot histogram of sub-record +0x18")
    fields.add_argument("--all", action="store_true", help="include _s_ files too")
    args = ap.parse_args()

    if args.cmd == "fields":
        cmd_fields(battle_only=not args.all)
        return 0

    table = load_corpus()
    if not table:
        print("no files under %s" % AI_DIR)
        return 1
    if args.cmd == "who":
        cmd_who(table, args.slot, args.all)
    else:
        cmd_table(table)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
