#!/usr/bin/env python3
"""Clash-tier survey: every fighter's moveData table, read out of the owner's
melonDS save states, with the node flags each entry turns into.

Static and offline. It reads .mln files (raw or gzipped) and never touches the
emulator or the bridge. Inputs are read-only:

  states    ~/Desktop/savestates/character-mappings/<NAME>/<koma>.mln
            ~/Desktop/savestates/projectile-research/*.mln
  jus_files REPO/jus_files, or $JUS_FILES / --jus-files (col files, arm9.bin,
            ChrArc.aar)

Outputs (byte-stable, `--check` reruns and diffs):

  table.md   one section per moveData table (col file), one row per entry
  table.tsv  the same rows, flat
  live.md    per state: the fighters, their records, and every in-use ColPrm
             record with its nodes, checked against the node model

The decode, each step cited in RESULTS.md:

  .mln      "MELN" header (u16 major, u16 minor, u32 length, u32 0), then
            sections of (magic, u32 length incl. 16-byte header, 8 zero
            bytes, body). NDSG's body is a u32 console type, then main RAM.
            0x02000000 maps to NDSG body + 4 (4 MB, DS mask 0x3FFFFF).
  layout    a0.py's detect_layout(): the fighter table's first word equals
            [0x02181B28] and the ColPrm manager passes its self-pointer check.
  table     record M = [[fighter+0x1A8]+0x10]; moveData base
            = [[M+0x6C]+0x0C] (arm9 0x0207D4C4-0x0207D4D0); entry for id
            >= 0x100 is base + (id - 0x100) * 20.
  flags     build_node() models arm9 0x0207D440 for ids >= 0x100, and
            build_builtin_node() for the shared ids < 0x100 (0x0209FC2C).
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DESK = Path.home() / "Desktop" / "savestates"
STATE_DIRS = ("character-mappings", "projectile-research")

RAM_BASE, RAM_SIZE = 0x02000000, 0x400000
P1_PTR = 0x02181B28
LAYOUTS = {  # a0.py LAYOUTS (import-character-mapping-2026-09-24/plans/a0.py)
    "dark-tournament": {"FIGHTERS": 0x021DEB3C, "P1REC": 0x021DF1D4, "P2REC": 0x021DF7F0,
                        "MGR": 0x0220DDE0},
    "test-play": {"FIGHTERS": 0x021DEB1C, "P1REC": 0x021DF1B4, "P2REC": 0x021DF7D0,
                  "MGR": 0x0220DDC0},
}
REC_OFF, REC_COUNT, REC_STRIDE = 0x454, 128, 0x188
HP_STRIDE, HP_SLOTS = 0x50, 4
ENTRY = 20
OUTPUTS = ("table.md", "table.tsv", "live.md")

# arm9 0x0207D440's per-bit tables for entry +0x08 (literal 0x0207D854 =
# 0x0209FD44; T18 = +0x80, T1C = +0x100). Nonzero words only, from
# jus_files/arm9/arm9.bin; check_tables() re-reads them from every state.
T14 = {0: 0x04000000, 1: 0x08000000, 12: 0x01000000, 14: 0x02000000}
T18 = {5: 0x1, 6: 0x8, 7: 0x10, 8: 0x2, 9: 0x4, 10: 0x40, 11: 0x80, 13: 0x200,
       17: 0x400, 18: 0x1000, 19: 0x2000, 20: 0x10000, 21: 0x20000, 22: 0x40000}
T1C = {1: 0x689CFF00, 2: 0x10000000, 3: 0x20000000, 4: 0x30000000, 19: 0x700}
T14_ADDR = 0x0209FD44

# The id < 0x100 path's per-id tables (literals 0x0207D844/0x0207D848/
# 0x0207D84C), 14 words each, and the shared built-in entries they index:
# 20-byte entries at 0x0209FC2C + id * 20 (literal 0x0207D840), arm9 static
# data every fighter uses. check_tables() re-reads all of them.
A14 = (0x20000000, 0x10400000, 0x40000000, 0, 0x20000000, 0x20000000, 0x800,
       0x10000, 0x10000, 0x20000, 0x40000, 0x80000, 0x10800000, 0x20000000)
B18 = (0, 0, 0, 0, 0x1, 0, 0, 0, 0, 0, 0, 0, 0, 0)
C1C = (0x488FC000, 0x58DF28FF, 0x48DF0800, 0, 0x08AFC200, 0x08AFC200, 0,
       0x509FFFFF, 0x509FFFFF, 0x509EFFFF, 0xFFFFFFFF, 0x5FFFFFF0, 0x109EFFF0, 0x08AFC200)
A14_ADDR, B18_ADDR, C1C_ADDR = 0x0209FB84, 0x0209FBBC, 0x0209FBF4
BUILTIN_ADDR, BUILTIN_COUNT = 0x0209FC2C, 14


class SurveyError(RuntimeError):
    """A decode check failed; the survey stops rather than guess."""


# --------------------------------------------------------------------------- #
# .mln reader
# --------------------------------------------------------------------------- #
def parse_mln(blob: bytes) -> bytes:
    """-> the 4 MB of main RAM (0x02000000..0x023FFFFF) from a melonDS state."""
    if blob[:2] == b"\x1f\x8b":
        blob = gzip.decompress(blob)
    if blob[:4] != b"MELN":
        raise ValueError("not a melonDS state (no MELN magic)")
    major, _minor, length, _pad = struct.unpack_from("<HHII", blob, 4)
    if major != 14:
        raise ValueError(f"MELN major version {major}, reader written for 14")
    off = 0x10
    while off + 16 <= len(blob):
        magic = blob[off:off + 4]
        slen = struct.unpack_from("<I", blob, off + 4)[0]
        if slen < 16:
            break
        if magic == b"NDSG":
            body = blob[off + 16:off + slen]
            console = struct.unpack_from("<I", body, 0)[0]
            if console != 0:
                raise ValueError(f"NDSG console type {console}, expected 0 (DS)")
            if len(body) < 4 + RAM_SIZE:
                raise ValueError("NDSG section shorter than main RAM")
            return body[4:4 + RAM_SIZE]
        off += slen
    raise ValueError("no NDSG section")


class Ram:
    def __init__(self, main: bytes):
        self.m = main

    def _ok(self, a, n):
        return RAM_BASE <= a and a + n <= RAM_BASE + len(self.m)

    def u8(self, a):
        return self.m[a - RAM_BASE] if self._ok(a, 1) else None

    def u16(self, a):
        return struct.unpack_from("<H", self.m, a - RAM_BASE)[0] if self._ok(a, 2) else None

    def u32(self, a):
        return struct.unpack_from("<I", self.m, a - RAM_BASE)[0] if self._ok(a, 4) else None

    def blk(self, a, n):
        return self.m[a - RAM_BASE:a - RAM_BASE + n] if self._ok(a, n) else None


def ptr(ram, a):
    """[a] when it is a main-RAM pointer, else None."""
    v = ram.u32(a) if a is not None else None
    return v if v is not None and RAM_BASE <= v < RAM_BASE + RAM_SIZE else None


def detect_layout(ram: Ram) -> str:
    p1 = ram.u32(P1_PTR)
    hits = [n for n, L in LAYOUTS.items()
            if ram.u32(L["FIGHTERS"]) == p1 and ram.u32(L["MGR"]) == L["MGR"] + 0x454]
    if len(hits) != 1:
        raise SurveyError(f"no single RAM layout matches (p1 {p1}, matches {hits})")
    return hits[0]


def check_tables(ram: Ram):
    """The per-bit tables in this state's RAM must equal the constants."""
    for base, table in ((T14_ADDR, T14), (T14_ADDR + 0x80, T18), (T14_ADDR + 0x100, T1C)):
        got = [ram.u32(base + 4 * i) for i in range(32)]
        want = [table.get(i, 0) for i in range(32)]
        if got != want:
            raise SurveyError(f"per-bit table at {base:#x} differs from arm9.bin")
    for base, table in ((A14_ADDR, A14), (B18_ADDR, B18), (C1C_ADDR, C1C)):
        if [ram.u32(base + 4 * i) for i in range(BUILTIN_COUNT)] != list(table):
            raise SurveyError(f"per-id table at {base:#x} differs from arm9.bin")


# --------------------------------------------------------------------------- #
# node model: arm9 0x0207D440, id >= 0x100 path
# --------------------------------------------------------------------------- #
def build_node(entry: bytes, r34=0, r38=0, r3C=0) -> dict:
    """Node +0x14/+0x18/+0x1C as 0x0207D440 builds them for an authored id
    (>= 0x100), seeded from the record's +0x34/+0x38/+0x3C. Leaves out the
    record-side writes and the +0x18 bit 0x10000 low-byte fix-up at
    0x0207D7C0-0x0207D818, which walks the record's other nodes."""
    tier = entry[0]
    e08 = struct.unpack_from("<I", entry, 8)[0]
    n14, n18 = r34, r38                                   # 0x0207D498-0x0207D4A4
    n1C = r3C & ~0x30000000                               # 0x0207D4B4-0x0207D4C0
    if tier:                                              # 0x0207D4D8
        n14 = (n14 | 0x10000000) & ~0x20000000
        if n14 & 0x1000:                                  # 0x0207D4F4
            n1C |= 0x08000000
    else:
        n14 = (n14 | 0x20000000) & 0xEFFFEFFF             # 0x0207D508-0x0207D518
    if n14 & 0x100 and n14 & 0x10000000:                  # 0x0207D51C-0x0207D538
        n1C |= 0x9F0 | 0x10000000
    if n1C & 0xF:                                         # 0x0207D53C-0x0207D548
        n1C |= (n1C & 0xF) << 4
    return _node_tail(tier, e08, n14, n18, n1C)


def build_builtin_node(idx: int, entry: bytes, r34=0, r38=0, r3C=0) -> dict:
    """The same words for a built-in id (< 0x100), whose entry is the shared
    0x0209FC2C + id * 20. This path never reads the tier byte: the node's
    class bits come from A14[id] alone."""
    tier = entry[0]
    e08 = struct.unpack_from("<I", entry, 8)[0]
    n14 = r34 | A14[idx]                                  # 0x0207D580-0x0207D594
    n18 = r38 | B18[idx]                                  # 0x0207D598-0x0207D5A8
    n1C = r3C | C1C[idx]                                  # 0x0207D5AC-0x0207D5B8
    if n14 & 0x20000:                                     # 0x0207D5C0-0x0207D5CC
        n1C &= ~0x10000
    if idx == 1:                                          # 0x0207D5D0-0x0207D5DC
        n1C |= 0xFF
    if idx == 9:                                          # 0x0207D608-0x0207D614
        n14 &= ~0xFF
    if n14 & 0x10F0:                                      # 0x0207D618-0x0207D62C (literal 0x0207D850)
        n1C |= 0x100
    return _node_tail(tier, e08, n14, n18, n1C)


def _node_tail(tier, e08, n14, n18, n1C) -> dict:
    """0x0207D670 on, shared by both id paths."""
    for b in range(32):                                   # 0x0207D684-0x0207D6E8
        if e08 >> b & 1:
            n14 |= T14.get(b, 0)
            n18 |= T18.get(b, 0)
            n1C |= T1C.get(b, 0)
    if e08 & 0x800000:                                    # 0x0207D6D4-0x0207D6E0
        n14 |= 0x100
    n1C |= 0x200000                                       # 0x0207D774-0x0207D77C
    if n18 & 0x1000:                                      # 0x0207D780-0x0207D7BC
        n1C = (n1C | 0xFF | 0x10000000) & ~(n14 & 0xF)
        n14 = (n14 & ~0xF) | 0x100
    return {"tier": tier, "e08": e08, "n14": n14 & 0xFFFFFFFF,
            "n18": n18 & 0xFFFFFFFF, "n1C": n1C & 0xFFFFFFFF}


def gate_notes(n: dict) -> list[str]:
    """The pair-loop and helper gates an entry's static node bits touch.
    Addresses are the tests in arm9 0x0207FBD0 and 0x020809C8."""
    n14, n18, n1C, tier = n["n14"], n["n18"], n["n1C"], n["tier"]
    out = []
    if n14 & 0x08000000:
        out.append("14:08000000")       # 0x0207FC5C: A takes the other compare path
    if n14 & 0x40000000:
        out.append("14:40000000")       # 0x0207FC38 / 0x0207FD18
    if n14 & 0x100:
        out.append("14:100")            # helper 0x02080A24 / 0x02080B40
    if n14 & 0x200:
        out.append("14:200")
    if n14 & 0xF0:
        out.append("14:F0")
    if n14 & 0xB0000:
        out.append("14:B0000")          # helper 0x02080BA4 / 0x02080BB0
    if n14 & 0x04000000:
        out.append("14:04000000")       # 0x02080B18, 0x020808EC
    if n1C & 0x10000000:
        out.append("1C:10000000")       # 0x0207FC44: can't be the B side
    if n18 & 0x800:
        out.append("18:800")            # helper 0x02080A30
    if n18 & 0x20000:
        out.append("18:20000")          # helper 0x02080AC8
    if n18 & 0x2000:
        out.append("18:2000")           # 0x0207C020 -> record +0x40 bit 0x80
    if n18 & 0x10000:
        out.append("18:10000")          # 0x0207C044 -> record +0x44 bit 0x2
    if tier in (3, 4):
        out.append("exc3/4")            # helper 0x02080B50 / 0x02080C00
    return out


# --------------------------------------------------------------------------- #
# melee vs spawned, from the character's ALMT motion files
# --------------------------------------------------------------------------- #
def classify_records(anims) -> dict:
    """anims: [(member, anim_id, {prop: set(values)})]. -> {record index:
    (kind, [ref, ...])}. An animation whose CollisionType0 carries an
    authored id (>= 0x100) is a spawned element's; any other is the
    fighter's. kind is melee, spawned or both."""
    kinds = defaultdict(set)
    refs = defaultdict(set)
    for member, aid, props in anims:
        spawned = any(v >= 0x100 for v in props.get("CollisionType0", ()))
        for prop, vals in props.items():
            if not prop.startswith("CollisionType"):
                continue
            for v in vals:
                if v >= 0x100:
                    i = v - 0x100
                    kinds[i].add("spawned" if spawned else "melee")
                    refs[i].add(f"{member}:{aid:#x}")
    out = {}
    for i, ks in kinds.items():
        kind = "both" if len(ks) == 2 else next(iter(ks))
        out[i] = (kind, sorted(refs[i]))
    return out


def builtin_refs(anims) -> dict:
    """{built-in id: {"member:anim", ...}} from CollisionType tracks whose
    value is below 0x100 (a shared 0x0209FC2C entry, not the character's)."""
    out = defaultdict(set)
    for member, aid, props in anims:
        for prop, vals in props.items():
            if prop.startswith("CollisionType"):
                for v in vals:
                    if v < 0x100:
                        out[v].add(f"{member}:{aid:#x}")
    return out


def motion_anims(prefix, mr):
    """[(member, anim_id, {prop: set(values)})] for one col-file prefix."""
    out = []
    for member, almt in mr.motions(prefix):
        per = defaultdict(lambda: defaultdict(set))
        for (_i, node, aid, _frames, prop, keys) in mr.anim_record_uses(almt):
            for _f, v in keys:
                per[(node, aid)][prop].add(v)
        for (node, aid), props in sorted(per.items()):
            name = Path(member).stem + ("" if node == "SP01" else "/" + node)
            out.append((name, aid, dict(props)))
    return out


def load_move_records(jus_files: Path):
    sys.path.insert(0, str(REPO / "scripts" / "analysis"))
    import move_records as mr  # noqa: E402
    mr.COL_DIRS = [jus_files / "chrbin" / "chr" / "col"]
    mr.CHRARC = jus_files / "ripped_jus_files" / "chr" / "ChrArc.aar"
    return mr


# --------------------------------------------------------------------------- #
# one state
# --------------------------------------------------------------------------- #
def chrb_names():
    rows = {}
    for line in (REPO / "docs/research/chr_b-Complete-Mapping.md").read_text().splitlines():
        cells = [c.strip() for c in line.split("|")]
        if len(cells) > 3 and cells[1].isdigit() and cells[3]:
            rows.setdefault(int(cells[1]), cells[3])
    return rows


def match_col(ram, base, cols):
    """The longest col file whose whole contents sit at base. -> [name], or
    [] when none does. Files with the same bytes come back as one name
    joined by '='; a shorter file that is a prefix of the match is dropped."""
    hits = [(len(d), n) for n, d in cols.items() if d and ram.blk(base, len(d)) == d]
    if not hits:
        return []
    top = max(n for n, _ in hits)
    return ["=".join(sorted(name for n, name in hits if n == top))]


def read_nodes(ram, rec):
    nodes, a, seen = [], ptr(ram, rec + 0x08), set()
    while a and a not in seen and len(nodes) < 32:
        seen.add(a)
        nodes.append({"addr": a, "entry": ram.u32(a + 0x10), "n14": ram.u32(a + 0x14),
                      "n18": ram.u32(a + 0x18), "n1C": ram.u32(a + 0x1C),
                      "id": ram.u16(a + 0x26), "rec": ram.u32(a + 0x0C)})
        a = ptr(ram, a)
    return nodes


def survey_state(path: Path, cols: dict):
    ram = Ram(parse_mln(path.read_bytes()))
    layout = detect_layout(ram)
    check_tables(ram)
    L = LAYOUTS[layout]
    mgr = L["MGR"]
    fighters = []
    for k, hp in ((0, L["P1REC"]), (1, L["P2REC"])):
        obj = ptr(ram, L["FIGHTERS"] + 4 * k)
        M = ptr(ram, ptr(ram, obj + 0x1A8) + 0x10) if obj else None
        prm = ptr(ram, M + 0x6C) if M else None
        base = ptr(ram, prm + 0x0C) if prm else None
        active = [s for s in range(HP_SLOTS) if (ram.u8(hp + s * HP_STRIDE + 0x25) or 0) & 1]
        chrb = ram.u8(hp + active[0] * HP_STRIDE + 0x29) if len(active) == 1 else None
        if base is None:
            raise SurveyError(f"{path}: fighter {k} has no moveData base")
        files = match_col(ram, base, cols)
        fighters.append({
            "side": k + 1, "obj": obj, "M": M, "prm": prm, "base": base,
            "chrb": chrb, "files": files,
            "abil": ram.u32(obj + 0x128),
            "r34": ram.u32(M + 0x34), "r38": ram.u32(M + 0x38), "r3C": ram.u32(M + 0x3C),
            "r40": ram.u32(M + 0x40), "r44": ram.u32(M + 0x44),
            "M_index": (M - mgr - REC_OFF) // REC_STRIDE,
        })
    records = []
    for i in range(REC_COUNT):
        rec = mgr + REC_OFF + i * REC_STRIDE
        r40 = ram.u32(rec + 0x40)
        if r40 is None or r40 & 0x200:
            continue
        prm = ptr(ram, rec + 0x6C)
        base = ptr(ram, prm + 0x0C) if prm else None
        owner = next((f["side"] for f in fighters if base and f["base"] == base), None)
        r34, r38, r3C = ram.u32(rec + 0x34), ram.u32(rec + 0x38), ram.u32(rec + 0x3C)
        nodes = read_nodes(ram, rec)
        for n in nodes:
            n["model"] = None
            if n["id"] is not None and n["id"] >= 0x100 and base:
                idx = n["id"] - 0x100
                e = ram.blk(base + idx * ENTRY, ENTRY)
                if n["entry"] == base + idx * ENTRY and e:
                    m = build_node(e, r34, r38, r3C)
                    n["model"] = (m["n14"] == n["n14"] and m["n18"] == n["n18"],
                                  m["n1C"] == n["n1C"])
                    n["tier"] = e[0]
                else:
                    n["model"] = "entry-mismatch"
            elif n["id"] is not None and n["id"] < BUILTIN_COUNT:
                e = ram.blk(BUILTIN_ADDR + n["id"] * ENTRY, ENTRY)
                if n["entry"] == BUILTIN_ADDR + n["id"] * ENTRY and e:
                    m = build_builtin_node(n["id"], e, r34, r38, r3C)
                    n["model"] = (m["n14"] == n["n14"] and m["n18"] == n["n18"],
                                  m["n1C"] == n["n1C"])
                    n["tier"] = e[0]
                else:
                    n["model"] = "entry-mismatch"
        records.append({"i": i, "addr": rec, "r34": r34, "r38": r38, "r3C": r3C,
                        "r40": r40, "r44": ram.u32(rec + 0x44), "owner": owner, "base": base,
                        "files": match_col(ram, base, cols) if base and owner is None else [],
                        "fighter": next((f["side"] for f in fighters if f["M"] == rec), None),
                        "nodes": nodes})
    return {"layout": layout, "fighters": fighters, "records": records, "ram": ram}


# --------------------------------------------------------------------------- #
# the whole survey
# --------------------------------------------------------------------------- #
def state_paths():
    out = []
    for d in STATE_DIRS:
        for p in sorted((DESK / d).rglob("*.mln")):
            out.append(p)
    return out


def shown_only(e: bytes) -> bool:
    """True when an entry is nothing but its tier byte and +0x08 word (the
    two fields the tables print), so its SHA-256 can be recomputed from them."""
    return e == bytes([e[0]]) + bytes(7) + e[8:12] + bytes(8)


def rel(p: Path, root=None) -> str:
    return str(p.relative_to(root or DESK))


def h(v, w=8):
    return "-" if v is None else f"0x{v:0{w}X}"


def run(jus_files: Path, out_dir: Path, paths=None, mr=None, root=None):
    """The whole survey. `paths` (the .mln files), `mr` (the move_records
    module) and `root` (what state names are relative to) default to the
    Desktop states and the real decoder; tests pass small synthetic ones."""
    cols = {p.stem: p.read_bytes() for p in sorted((jus_files / "chrbin/chr/col").glob("*.bin"))}
    arm9 = (jus_files / "arm9" / "arm9.bin").read_bytes()
    for base, table in ((T14_ADDR, T14), (T14_ADDR + 0x80, T18), (T14_ADDR + 0x100, T1C)):
        got = [struct.unpack_from("<I", arm9, base - RAM_BASE + 4 * i)[0] for i in range(32)]
        if got != [table.get(i, 0) for i in range(32)]:
            raise SurveyError(f"arm9.bin table at {base:#x} differs from the constants")
    for base, table in ((A14_ADDR, A14), (B18_ADDR, B18), (C1C_ADDR, C1C)):
        if list(struct.unpack_from(f"<{BUILTIN_COUNT}I", arm9, base - RAM_BASE)) != list(table):
            raise SurveyError(f"arm9.bin table at {base:#x} differs from the constants")
    names = chrb_names()
    mr = mr or load_move_records(jus_files)

    states = {}
    for p in (state_paths() if paths is None else paths):
        states[rel(p, root)] = survey_state(p, cols)

    # tables: one per matched col file
    tables = defaultdict(lambda: {"seen": [], "chrb": set()})
    unmatched = []
    for s, st in states.items():
        for f in st["fighters"]:
            if len(f["files"]) != 1:
                unmatched.append((s, f["side"], f["files"]))
                continue
            t = tables[f["files"][0]]
            t["seen"].append((s, f["side"], f["base"]))
            if f["chrb"] is not None:
                t["chrb"].add(f["chrb"])

    # tables only non-fighter records use (items): seen, never a fighter's
    for s, st in states.items():
        for r in st["records"]:
            if r["owner"] is None and len(r["files"]) == 1 and any(
                    n["id"] is not None and n["id"] >= 0x100 for n in r["nodes"]):
                t = tables[r["files"][0]]
                t["seen"].append((s, f"rec {r['i']}", r["base"]))
                t["nonfighter"] = True

    # live observations: which record kind carried each authored id
    live_kind = defaultdict(set)   # (file, idx) -> {"melee", "spawned"}
    for s, st in states.items():
        fmap = {f["side"]: f for f in st["fighters"]}
        for r in st["records"]:
            if r["owner"] is not None and len(fmap[r["owner"]]["files"]) == 1:
                fname = fmap[r["owner"]]["files"][0]
            elif r["owner"] is None and len(r["files"]) == 1:
                fname = r["files"][0]
            else:
                continue
            for n in r["nodes"]:
                if n["id"] is not None and n["id"] >= 0x100 and n["model"] != "entry-mismatch":
                    live_kind[(fname, n["id"] - 0x100)].add(
                        "melee" if r["fighter"] and r["fighter"] == r["owner"] else
                        "spawned" if r["owner"] else "other-record")

    rows = []
    bi_refs = defaultdict(lambda: defaultdict(set))   # id -> file -> {"member:anim"}
    for fname in sorted(tables):
        data = cols[fname.split("=")[0]]
        anims = [a for part in fname.split("=") for a in motion_anims(part, mr)]
        kinds = classify_records(anims)
        if not tables[fname].get("nonfighter"):
            for i, refs in builtin_refs(anims).items():
                bi_refs[i][fname] |= refs
        for idx in range(len(data) // ENTRY):
            e = data[idx * ENTRY:(idx + 1) * ENTRY]
            n = build_node(e)
            kind, refs = kinds.get(idx, ("unreferenced", []))
            if tables[fname].get("nonfighter") and not tables[fname]["chrb"]:
                kind = "item-table"
            live = "/".join(sorted(live_kind.get((fname, idx), ())))
            rows.append({"file": fname, "idx": idx, "id": 0x100 + idx, "tier": e[0],
                         "e08": n["e08"], "n14": n["n14"], "n18": n["n18"], "n1C": n["n1C"],
                         "part": n["n18"] & 1, "gates": gate_notes(n), "kind": kind,
                         "live": live, "refs": refs, "sha256": hashlib.sha256(e).hexdigest(),
                         "shown_only": shown_only(e)})

    builtins = []
    for i in range(BUILTIN_COUNT):
        e = arm9[BUILTIN_ADDR - RAM_BASE + i * ENTRY:BUILTIN_ADDR - RAM_BASE + (i + 1) * ENTRY]
        n = build_builtin_node(i, e)
        live, ok, carriers = 0, 0, Counter()
        for st in states.values():
            for r in st["records"]:
                for nd in r["nodes"]:
                    if nd["id"] != i:
                        continue
                    live += 1
                    ok += isinstance(nd["model"], tuple) and all(nd["model"])
                    carriers["fighter" if r["fighter"] else "shot" if r["owner"] else
                             f"other +0x34 {h(r['r34'])}"] += 1
        anim_ids = Counter(a for refs in bi_refs[i].values()
                           for a in {ref.rsplit(":", 1)[1] for ref in refs})
        builtins.append({"id": i, "addr": BUILTIN_ADDR + i * ENTRY, "tier": e[0],
                         "sha256": hashlib.sha256(e).hexdigest(), "shown_only": shown_only(e),
                         "e08": n["e08"], "n14": n["n14"], "n18": n["n18"], "n1C": n["n1C"],
                         "files": len(bi_refs[i]), "anims": anim_ids, "live": live, "ok": ok,
                         "carriers": carriers})

    write_outputs(out_dir, states, tables, rows, names, unmatched, builtins)


def fmt_chrb(chrbs, names):
    return ", ".join(f"chr_b {c} {names.get(c, '?')}" for c in sorted(chrbs)) or "-"


def write_outputs(out_dir, states, tables, rows, names, unmatched, builtins):
    by_tier = Counter(r["tier"] for r in rows)
    by_kind = Counter(r["kind"] for r in rows)
    part_kind = Counter((r["kind"], r["part"]) for r in rows if r["tier"])
    gate_count = Counter(g for r in rows for g in r["gates"])
    atk = [r for r in rows if r["tier"]]

    L = ["# Clash-tier survey: the generated table", "",
         "Generated by `survey.py` (don't edit by hand). One section per moveData",
         "table (a `chr/col` file whose bytes sit at `[[M+0x6C]+0x0C]` in a state).",
         "Columns: `idx` entry index (id = 0x100 + idx), `tier` byte +0x00,",
         "`+0x08` the property word, `n14`/`n18`/`n1C` the node words",
         "`build_node()` gives with a zero record seed (so no side nibble and no",
         "0x1000 shot class), `P` node +0x18 bit 0 (participates), `gates` the",
         "gate bits it touches (see RESULTS.md), `kind` from the ALMT rule",
         "(melee = on a fighter animation, spawned = on an animation whose",
         "CollisionType0 is authored), `live` = the record kind that carried it",
         "in a state's RAM.", "",
         "## Summary", "",
         f"- states read: {len(states)}; tables: {len(tables)}; entries: {len(rows)}",
         f"- fighters with no single col-file match: {len(unmatched)}",
         "- entries by tier byte: " + ", ".join(f"{k}: {v}" for k, v in sorted(by_tier.items())),
         "- entries by kind: " + ", ".join(f"{k}: {v}" for k, v in sorted(by_kind.items())),
         "- tier > 0, by kind and P: " + ", ".join(
             f"{k} P{p}: {v}" for (k, p), v in sorted(part_kind.items())),
         "- tier > 0, gate bits: " + ", ".join(f"{k}: {v}" for k, v in sorted(gate_count.items())),
         ""]
    tk = Counter((r["kind"], r["tier"]) for r in atk)
    L += ["| kind | " + " | ".join(f"tier {t}" for t in sorted({r['tier'] for r in atk})) + " |",
          "|---|" + "---|" * len({r['tier'] for r in atk})]
    for k in sorted({r["kind"] for r in atk}):
        L.append(f"| {k} | " + " | ".join(str(tk.get((k, t), 0))
                                          for t in sorted({r['tier'] for r in atk})) + " |")
    L.append("")
    L += ["## Shared built-in entries (arm9 0x0209FC2C)", "",
          "Not any character's moves: 14 static 20-byte entries in arm9 data that",
          "ALMT tracks name with a value below 0x100 (entry = 0x0209FC2C + id * 20,",
          "literal 0x0207D840). 0x0209FB84-0x0209FC2B holds the three per-id tables",
          "A14/B18/C1C this path ORs in; 0x0209FD44 on is the per-bit table. The id",
          "path never reads the tier byte, so the node class comes from A14 only;",
          "both pair loops still compare the tier byte (0x0207FD00-0x0207FD08,",
          "0x02080128-0x02080130). `n14`/`n18`/`n1C` are `build_builtin_node()`",
          "with a zero record seed. `refs` counts the fighter tables (of the ones",
          "above) whose animations name the id, then the animation ids with how",
          "many tables use each. `live` counts nodes in the states' RAM, how many",
          "match the model with their record's own seed, and who carried them.",
          "`sha256` is the first 16 hex digits of the entry's SHA-256; no raw",
          "game bytes are written (table.tsv has the full digest per entry).",
          f"The digest hides nothing for an entry that is only its tier and +0x08",
          f"(every other byte zero): {sum(b['shown_only'] for b in builtins)} of "
          f"{len(builtins)} built-in entries here and "
          f"{sum(r['shown_only'] for r in rows)} col-file "
          f"entr{'y' if sum(r['shown_only'] for r in rows) == 1 else 'ies'} below "
          f"({', '.join(r['file'] + ' idx ' + str(r['idx']) for r in rows if r['shown_only']) or 'none'})",
          "are like that,",
          "so their bytes can be rebuilt from the printed fields (for example",
          "the SHA-256 of 20 zero bytes). For the rest the digest only detects a",
          "change.", "",
          "| id | addr | tier | +0x08 | n14 | n18 | n1C | P | refs | live | sha256 |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for b in builtins:
        top = sorted(b["anims"].items(), key=lambda x: (-x[1], int(x[0], 16)))
        anims = ", ".join(f"{a} x{c}" for a, c in top[:12]) + (
            f", +{len(top) - 12} more" if len(top) > 12 else "")
        car = ", ".join(f"{k} {v}" for k, v in sorted(b["carriers"].items()))
        L.append(f"| {b['id']} | {h(b['addr'])} | {b['tier']} | {h(b['e08'])} | {h(b['n14'])} "
                 f"| {h(b['n18'])} | {h(b['n1C'])} | {b['n18'] & 1} "
                 f"| {b['files']} tables{': ' + anims if anims else ''} "
                 f"| {b['live']} ({b['ok']} ok){': ' + car if car else ''} | {b['sha256'][:16]} |")
    L.append("")
    if unmatched:
        L += ["## Fighters with no single col-file match", ""]
        for s, side, files in unmatched:
            L.append(f"- `{s}` P{side}: {files or 'none'}")
        L.append("")
    for fname in sorted(tables):
        t = tables[fname]
        L += [f"## {fname} ({fmt_chrb(t['chrb'], names)})", "",
              "Seen in: " + "; ".join(f"`{s}` {side if isinstance(side, str) else 'P%d' % side} @ {h(b)}"
                                      for s, side, b in sorted(t["seen"], key=str)),
              "", "| idx | tier | +0x08 | n14 | n18 | n1C | P | gates | kind | live | refs |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            if r["file"] != fname:
                continue
            refs = ", ".join(r["refs"][:4]) + (f" +{len(r['refs']) - 4}" if len(r["refs"]) > 4 else "")
            L.append(f"| {r['idx']} | {r['tier']} | {h(r['e08'])} | {h(r['n14'])} | {h(r['n18'])} "
                     f"| {h(r['n1C'])} | {r['part']} | {' '.join(r['gates']) or '-'} | {r['kind']} "
                     f"| {r['live'] or '-'} | {refs or '-'} |")
        L.append("")
    (out_dir / "table.md").write_text("\n".join(L))

    T = ["file\tchr_b\tidx\tid\ttier\te08\tn14\tn18\tn1C\tpart\tgates\tkind\tlive\trefs\tsha256"]
    for r in rows:
        T.append("\t".join([r["file"], ",".join(str(c) for c in sorted(tables[r["file"]]["chrb"])),
                            str(r["idx"]), f"{r['id']:#x}", str(r["tier"]), h(r["e08"]),
                            h(r["n14"]), h(r["n18"]), h(r["n1C"]), str(r["part"]),
                            " ".join(r["gates"]), r["kind"], r["live"], " ".join(r["refs"]),
                            r["sha256"]]))
    (out_dir / "table.tsv").write_text("\n".join(T) + "\n")

    V = ["# Clash-tier survey: what was live in each state", "",
         "Generated by `survey.py`. Per state: the layout, both fighters (object,",
         "record M and its index, moveData base, matched col file, the active",
         "slot's chr_b, the ability word `obj+0x128`, record +0x34/+0x38/+0x40/+0x44),",
         "then every in-use ColPrm record (+0x40 bit 0x200 clear) that holds a",
         "node with an authored id. `model` is `build_node()` with that record's",
         "own +0x34/+0x38/+0x3C against the live node: `14/18 ok` or `14/18 DIFF`,",
         "then the same for +0x1C. These are runtime values at the instant of the",
         "save, nothing more. Built-in nodes (ids below 0x100) aren't listed per",
         "state; table.md's built-in section counts them and their model check.", ""]
    b4 = [(s, r["i"]) for s in sorted(states) for r in states[s]["records"] if (r["r44"] or 0) & 4]
    ag = [(s, f["side"], f["abil"]) for s in sorted(states) for f in states[s]["fighters"]
          if (f["abil"] or 0) & 0x10]
    V += ["## Record +0x44 bit 0x4 and the ability word", "",
          f"- in-use records with +0x44 bit 0x4 set, all states: {len(b4)}"
          + ("" if not b4 else " (" + "; ".join(f"`{s}` rec {i}" for s, i in b4) + ")"),
          f"- fighters whose `obj+0x128` has bit 0x10 (the ov6 0x0215EA10 test): {len(ag)}"]
    V += [f"  - `{s}` P{side}: {h(a)}" for s, side, a in ag]
    V.append("")
    sig = defaultdict(list)
    for s in sorted(states):
        for r in states[s]["records"]:
            if r["fighter"] or r["owner"]:
                continue
            key = (" ".join(r["files"]) or "no col match", r["r34"], r["r40"],
                   tuple((n["id"], n["n14"], n["n18"], n["n1C"]) for n in r["nodes"]))
            sig[key].append(s)
    V += ["## Records no fighter owns, by signature", "",
          "Every in-use record whose moveData base is neither fighter's, grouped by",
          "(table, +0x34, +0x40, nodes). Ids below 0x100 are built-in boxes",
          "(0x0209FC2C + id * 20).", "",
          "| table | +0x34 | +0x40 | nodes (id n14 n18 n1C) | records | states | first state |",
          "|---|---|---|---|---|---|---|"]
    for key in sorted(sig, key=lambda k: (k[0], k[1] or 0, k[2] or 0, str(k[3]))):
        f, r34, r40, nodes = key
        ns = "; ".join(f"{i:#x} {h(a)} {h(b)} {h(c)}" if i is not None else "?" for i, a, b, c in nodes)
        V.append(f"| {f} | {h(r34)} | {h(r40)} | {ns or '-'} | {len(sig[key])} "
                 f"| {len(set(sig[key]))} | `{sig[key][0]}` |")
    V.append("")
    for s in sorted(states):
        st = states[s]
        V += [f"## `{s}` ({st['layout']})", "",
              "| P | obj | M (idx) | base | file | chr_b | obj+0x128 | M+0x34 | M+0x38 | M+0x40 | M+0x44 |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for f in st["fighters"]:
                    V.append(f"| {f['side']} | {h(f['obj'])} | {h(f['M'])} ({f['M_index']}) | {h(f['base'])} "
                     f"| {' '.join(f['files']) or 'none'} | {fmt_chrb([f['chrb']] if f['chrb'] is not None else [], names)} "
                     f"| {h(f['abil'])} | {h(f['r34'])} | {h(f['r38'])} | {h(f['r40'])} | {h(f['r44'])} |")
        V += ["", "| rec | owner | +0x34 | +0x38 | +0x40 | +0x44 | nodes (id tier n14 n18 n1C model) |",
              "|---|---|---|---|---|---|---|"]
        for r in st["records"]:
            auth = [n for n in r["nodes"] if n["id"] is not None and n["id"] >= 0x100]
            if not auth and r["r44"] in (0, None):
                continue
            who = ("fighter P%d" % r["fighter"]) if r["fighter"] else (
                "P%d shot" % r["owner"] if r["owner"] else
                f"other, base {h(r['base'])} {' '.join(r['files']) or 'no col match'}")
            ns = []
            for n in auth:
                m = n["model"]
                ms = m if isinstance(m, str) else (
                    f"14/18 {'ok' if m[0] else 'DIFF'}, 1C {'ok' if m[1] else 'DIFF'}" if m else "-")
                ns.append(f"{n['id']:#x} t{n.get('tier', '?')} {h(n['n14'])} {h(n['n18'])} "
                          f"{h(n['n1C'])} ({ms})")
            V.append(f"| {r['i']} | {who} | {h(r['r34'])} | {h(r['r38'])} | {h(r['r40'])} "
                     f"| {h(r['r44'])} | {'; '.join(ns) or '-'} |")
        V.append("")
    (out_dir / "live.md").write_text("\n".join(V))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jus-files", type=Path,
                    default=Path(os.environ.get("JUS_FILES", REPO / "jus_files")))
    ap.add_argument("--out", type=Path, default=HERE)
    ap.add_argument("--check", action="store_true",
                    help="regenerate into a temp dir and diff against --out; exit 1 on any change")
    a = ap.parse_args()
    if not a.check:
        run(a.jus_files, a.out)
        return
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        run(a.jus_files, Path(tmp))
        bad = [n for n in OUTPUTS if (Path(tmp) / n).read_bytes() != (a.out / n).read_bytes()]
    print("byte-stable: " + ("no, differs: " + " ".join(bad) if bad else "yes"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
