#!/usr/bin/env python3
"""Static knockback table for every JUS battle character: the per-hit bytes that
set launch speed, angle and spike, and the velocity they give the victim. No
emulator.

Research note: docs/research/findings/knockback-table-2026-09-25.md.
Schema: docs/rebuild/knockback-table.md. Output: docs/rebuild/knockback-table.json.

The chain, all static:

  Record. Each hit reads one 20-byte record (chr/col/<prefix>.bin, id - 0x100).
      arm9 0x020817E8-0x020817F4 loads type = u8[+1], kbX = s8[+0xC],
      kbY = s8[+0xD]. Which record a move uses comes from the move's
      animation (CollisionType tracks, move_records.py) and the move table
      at ov6 0x021712B8 (cancel_table.py).
  Stage. arm9 0x020817F8-0x02081978 turns them into the staged pair
      M+0x148 (x) / M+0x14A (y):
        s  = type == 6 ? band_table[hp_frac >> 6] : 0x100
        x  = ASR(s * (kbX << 7), 8);  y = ASR(s * kbY * -158, 8)
        crit (damage routine flag bit 0) doubles both
        type == 6: victim gate bit 7 -> -half, then bit 15 -> +half
        element +0x14 bit 0x01000000 -> both 0
        element +0x14 bit 0x04000000 and victim element +0x14 & 0x700 -> (0x300, -0x500)
        M+0x148 += or -= x (sign: facing helper, or relative position if
                  element +0x18 bit 4); M+0x14A += ASR(y * 223, 8)
      The element bits come from the record's propMask (+8) through the three
      32-word tables at arm9 0x0209FD44 (arm9 0x0207D684-0x0207D6E8).
  Impulse. ov6 0x0215AF98-0x0215AFC4: X = TZ(x * 100 / 100), Y = TZ(y * 72 / 100)
      into obj+0x10A/+0x10C; the reaction entry picked from ov6 0x021721A0
      by the hit type adds them to the element's impulse +0x30/+0x32, or not.
  Integrate. arm9 0x02082E10: v += impulse; clamp |v| to byte +0x3E << 8
      (128, physics.md 6.1: never reached); v -= ASR(k * v, 8) with k = +0x3C (x)
      / +0x3D (y); vy += gravity.
  Floor. On a standing victim the floor contact (arm9 0x0207ECE4-0x0207ECF4)
      zeroes a downward vy, so a spike only moves an airborne victim down.

Only the code facts the rules rest on are decoded here, straight from
arm9.bin and ov06.bin; `code_facts()` returns them and the test pins each one.

Usage:
    python3 scripts/analysis/knockback_table.py build   # write docs/rebuild/knockback-table.json
    python3 scripts/analysis/knockback_table.py check   # the gate: exit 0 = pass, 1 = any miss
    python3 scripts/analysis/knockback_table.py show yh_b_01
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import anim_events as E  # noqa: E402
import cancel_table as C  # noqa: E402
import move_records as mr  # noqa: E402

REPO = HERE.parent.parent
ARM9 = REPO / "jus_files" / "arm9" / "arm9.bin"
ARM9_BASE = 0x02000000
OUT = REPO / "docs" / "rebuild" / "knockback-table.json"
NOTE = "docs/research/findings/knockback-table-2026-09-25.md"
CHARS = REPO / "docs" / "confirmed-facts" / "characters"
PHYSICS = REPO / "docs" / "confirmed-facts" / "physics.md"
RR7 = REPO / "docs" / "research" / "feel-captures" / "register-2026-09-03" / "runtime-report-7-pops-launchers.md"
LXYT = REPO / "docs" / "research" / "findings" / "knockback-record-pointer-per-hit.md"

MOVE_IDS = range(1, 13)          # ids 13/14 take their anim from a per-fighter byte
BANDS = {"x1": 0x100, "x1.5": 0x180, "x2": 0x200, "x3": 0x300}
DRAG_X, DRAG_Y, GRAVITY = 0x20, 8, 41   # measured on victims (physics.md 1, 4.2); runtime fields

# ------------------------------------------------------------------ bytes

_ARM9 = None


def a9(addr: int) -> int:
    global _ARM9
    if _ARM9 is None:
        _ARM9 = ARM9.read_bytes()
    return struct.unpack_from("<I", _ARM9, addr - ARM9_BASE)[0]


def imm8r(w: int) -> int:
    rot, imm = (w >> 8) & 0xF, w & 0xFF
    return ((imm >> (2 * rot)) | (imm << (32 - 2 * rot))) & 0xFFFFFFFF


def mov_imm(w: int) -> int:
    """MOV/MVN rd,#imm -> value (MVN negated)."""
    op = (w >> 21) & 0xF
    if (w >> 25) & 7 != 1 or op not in (0xD, 0xF):
        raise ValueError(f"0x{w:08X} is not mov/mvn #imm")
    v = imm8r(w)
    return v if op == 0xD else ~v


def ldr_imm_offset(w: int) -> tuple[str, int]:
    """LDRB/LDRSB with an immediate offset -> (kind, offset)."""
    if (w & 0x0E400000) == 0x04400000 and w & (1 << 20):          # ldrb rd,[rn,#imm12]
        return "ldrb", w & 0xFFF
    if (w & 0x0E4000F0) == 0x004000D0 and w & (1 << 20):          # ldrsb rd,[rn,#imm8]
        return "ldrsb", ((w >> 4) & 0xF0) | (w & 0xF)
    raise ValueError(f"0x{w:08X} is not a byte load")


def is_halfword_load(w: int, rn: int, off: int) -> bool:
    """LDRSH/LDRH rd,[rn,#off]."""
    return ((w & 0x0E5000B0) == 0x005000B0 and (w >> 16) & 0xF == rn
            and (((w >> 4) & 0xF0) | (w & 0xF)) == off)


def adds_impulse(entry: int) -> bool:
    """Does the reaction entry read obj+0x10A and +0x10C (as [r1,#0xA]/[r1,#0xC]
    with r1 = obj+0x100) before it returns?"""
    got = set()
    for a in range(entry, entry + 0x60, 4):
        w = C.word(a)
        for off in (0xA, 0xC):
            if is_halfword_load(w, 1, off):
                got.add(off)
        if (w & 0x0FFF0000) == 0x08BD0000 and w & (1 << 15) or w == 0xE12FFF1E:  # pop {..pc} / bx lr
            break
    return got == {0xA, 0xC}


def installs(entry: int) -> int | None:
    """The word the reaction entry stores to obj+0xFC (str rN,[r4,#0xFC] fed by
    ldr rN,[pc,#imm]) before it returns: the per-frame handler that runs next."""
    lit, got = {}, None
    for a in range(entry, entry + 0x100, 4):
        w = C.word(a)
        if (w & 0x0FFF0000) == 0x059F0000:                             # ldr rN,[pc,#imm]
            lit[(w >> 12) & 0xF] = C.word(a + 8 + (w & 0xFFF))
        elif (w & 0x0FF00FFF) == 0x058000FC and (w >> 16) & 0xF == 4:   # str rN,[r4,#0xfc]
            got = lit.get((w >> 12) & 0xF, got)
        if (w & 0x0FFF0000) == 0x08BD0000 and w & (1 << 15) or w == 0xE12FFF1E:
            break
    return got


def code_facts() -> dict:
    """The code facts the table rests on, decoded from arm9.bin / ov06.bin."""
    lit = 0x02081800 + 8 + (a9(0x02081800) & 0xFFF)               # ldreq r1,[pc,#imm]
    band_addr = a9(lit)
    flag_tables = a9(0x0207D854)
    tables = tuple([a9(flag_tables + 0x80 * t + 4 * i) for i in range(32)] for t in range(3))
    f = {
        "record_offsets": {"type": ldr_imm_offset(a9(0x020817EC))[1],
                           "kbX": ldr_imm_offset(a9(0x020817F0))[1],
                           "kbY": ldr_imm_offset(a9(0x020817F4))[1]},
        "kbx_shift": (a9(0x02081804) >> 7) & 0x1F,                 # lsl r4,r4,#7
        "kby_scale": mov_imm(a9(0x0208181C)),                      # mvn r2,#0x9d
        "y_scale": mov_imm(a9(0x02081968)),                        # mov r0,#0xdf
        "band_table_addr": band_addr,
        "band_table": [a9(band_addr + 4 * i) for i in range(5)],
        "ov6_x_scale": [mov_imm(C.word(0x0215AF8C)), mov_imm(C.word(0x0215AF8C))],
        "ov6_y_scale": [mov_imm(C.word(0x0215AFB0)), mov_imm(C.word(0x0215AFB8))],
        "flag_tables_addr": flag_tables,
        "zero_bits": [b for b in range(32) if tables[0][b] & 0x01000000],
        "override_bits": [b for b in range(32) if tables[0][b] & 0x04000000],
        "relative_sign_bits": [b for b in range(32) if tables[1][b] & 0x4],
        "entry_table_addr": C.pc_literal(0x0215AFDC)[1],
    }
    et = f["entry_table_addr"]
    f["entry"] = {t: [C.word(et + 4 * t), adds_impulse(C.word(et + 4 * t))] for t in range(16)}
    f["installs"] = {t: installs(e[0]) for t, e in f["entry"].items()}
    f["_tables"] = tables
    return f


# ------------------------------------------------------------------ arithmetic

def tz(a: int, b: int) -> int:
    """Signed divide truncating toward zero (arm9 0x0200D12C)."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def staged(kbx: int, kby: int, typ: int, band: int = 0x100, weight: int = 0,
           crit: bool = False) -> tuple[int, int]:
    """(x, y) added to M+0x148 / M+0x14A for one hit. x is the away-from-attacker
    magnitude with kbX's sign (the engine picks the screen sign); y < 0 is up."""
    s = band if typ == 6 else 0x100
    x = (s * (kbx << 7)) >> 8
    y = (s * (kby * -158)) >> 8
    if crit:
        x, y = x << 1, y << 1
    if typ == 6:
        if weight & 0x80:
            x, y = x - (x >> 1), y - (y >> 1)
        if weight & 0x8000:
            x, y = x + (x >> 1), y + (y >> 1)
    return x, (y * 223) >> 8


def impulse(x: int, y: int) -> tuple[int, int]:
    """ov6 0x0215AF98-0x0215AFC4: the pair the reaction entry adds to +0x30/+0x32."""
    return tz(x * 100, 100), tz(y * 72, 100)


def first_frame(ix: int, iy: int, vx0: int = 0, vy0: int = 0, ground: bool = False) -> tuple[int, int]:
    """Victim velocity after the next integrator pass (arm9 0x02082E10), no clamp.
    ground: the victim stands on the floor, and the floor contact at arm9
    0x0207ECE4-0x0207ECF4 zeroes a downward (positive) vy after the pass."""
    vx, vy = vx0 + ix, vy0 + iy
    vx -= (DRAG_X * vx) >> 8
    vy -= (DRAG_Y * vy) >> 8
    vy += GRAVITY
    return vx, (min(vy, 0) if ground else vy)


def element_flags(mask: int, tables) -> dict:
    e14 = e18 = 0
    for b in range(32):
        if mask >> b & 1:
            e14 |= tables[0][b]
            e18 |= tables[1][b]
    return {"zero": bool(e14 & 0x01000000), "override": bool(e14 & 0x04000000),
            "sign": "relative" if e18 & 0x4 else "facing"}


def px(v: int) -> float:
    return round(v / 256, 3)


def record_row(i: int, raw: bytes, tables, entry: dict) -> dict:
    d = mr.decode_record(raw)
    fl = element_flags(d["propMask"], tables)
    x, y = (0, 0) if fl["zero"] else staged(d["kbX"], d["kbY"], d["type"])
    _ent, adds = entry.get(d["type"], (None, False))
    row = {"rec": i, "id": f"0x{i + mr.CHAR_ID_BASE:03x}", "kind": d["kind"], "type": d["type"],
           "damage": raw[4] if raw[4] < 0x80 else raw[4] - 0x100, "hitstun_add": d["hitstunAdd"],
           "kbX": d["kbX"], "kbY": d["kbY"], "mask": f"0x{d['propMask']:08x}",
           "zero": fl["zero"], "override": fl["override"], "sign": fl["sign"],
           "staged": [x, y], "impulse": None, "px": None,
           "first_frame_air": None, "first_frame_ground": None}
    if d["statusRaw"]:
        row["status_raw"] = d["statusRaw"]          # the staged status byte, nonzero only
    if adds:
        ix, iy = impulse(x, y)
        row["impulse"] = [ix, iy]
        row["px"] = [px(ix), px(iy)]
        row["first_frame_air"] = list(first_frame(ix, iy))
        row["first_frame_ground"] = list(first_frame(ix, iy, ground=True))
    if d["type"] == 6 and not fl["zero"]:
        row["band"] = {k: list(staged(d["kbX"], d["kbY"], 6, band=v)) for k, v in BANDS.items()}
    return row


# ------------------------------------------------------------------ characters

def record_uses(prefix: str) -> tuple[dict, dict]:
    """-> ({anim: [(frame, rec)]} for the fighter .amt, {rec: ["member anim chan fN"]} for
    every parsed motion of the character)."""
    fighter = {}
    for _idx, node, aid, _fr, chan, keys in mr.anim_record_uses(E.load_almt(prefix)):
        for f, v in keys:
            if v >= mr.CHAR_ID_BASE:
                fighter.setdefault(aid, []).append((f, v - mr.CHAR_ID_BASE, node, chan))
    refs = {}
    for member, almt in mr.motions(prefix):
        for _idx, node, aid, _fr, chan, keys in mr.anim_record_uses(almt):
            for f, v in keys:
                if v >= mr.CHAR_ID_BASE:
                    refs.setdefault(v - mr.CHAR_ID_BASE, []).append(
                        f"{Path(member).name[:-4]} 0x{aid:02x}" + ("" if node == "SP01" else f" {node}"))
    return fighter, {k: sorted(set(v)) for k, v in refs.items()}  # "member anim [node]"


def move_rows(prefix: str, fighter: dict, nrec: int, table: dict) -> list[dict]:
    out = []
    for i in MOVE_IDS:
        anim = table[i]["anim"]
        keys = sorted(fighter.get(anim, []))
        order = []
        for _f, r, _n, _c in keys:
            if r not in order:
                order.append(r)
        row = {"id": i, "move": C.NAMES[i], "anim": f"0x{anim:02x}", "records": order, "reason": None}
        bad = [r for r in order if r >= nrec]
        if bad:
            row["reason"] = f"record(s) {bad} past the end of {prefix}.bin"
        elif not order:
            row["reason"] = ("no character record in this anim's CollisionType tracks: the hit "
                             "comes from a spawned object or another anim (see records[].refs)")
        out.append(row)
    return out


def build_char(prefix: str, facts: dict, table: dict) -> dict:
    recs = mr.read_records(prefix)
    base = {"prefix": prefix, "names": C.names_for(prefix)}
    try:
        fighter, refs = record_uses(prefix)
    except BaseException as ex:  # SystemExit from the loaders, struct errors
        fighter, refs, err = {}, {}, f"{type(ex).__name__}: {ex}"
    else:
        err = None
    rows = []
    for i, raw in enumerate(recs):
        r = record_row(i, raw, facts["_tables"], {k: tuple(v) for k, v in facts["entry"].items()})
        r["refs"] = refs.get(i, [])
        rows.append(r)
    moves = move_rows(prefix, fighter, len(recs), table)
    if err:
        for m in moves:
            m["records"], m["reason"] = [], f"ALMT parse failed: {err}"
    return {**base, "moves": moves, "records": rows}


GRADE_NOTES = {
    "record_bytes": "measured: read from chr/col/<prefix>.bin",
    "staged": "measured on the cases the gate lists (kakashi, sasuke, taikoubou, eve, muhyo, "
              "raoh, kenshin, jotaro, yoh, yusuke); the arithmetic is arm9 0x020817E8-0x02081978. "
              "Full HP band (x1), no crit, neutral weight, facing side of the sign rule",
    "impulse": "measured on the rest-start cases the gate lists; ov6 0x0215AF98-0x0215AFC4 and "
               "the entry table; null when the type's entry does not add obj+0x10A/+0x10C",
    "px": "impulse / 256, px per frame, before drag and gravity",
    "first_frame_air": "inferred: victim velocity one integrator pass after the hit, starting at "
                       "rest in the air: drag 32/256 (x) and 8/256 (y), gravity 41, cap 128 << 8 as "
                       "physics.md 6.1 measured (element +0x3C/+0x3D/+0x3E, [r3+0x2C]), not read here",
    "first_frame_ground": "as first_frame_air, but a downward vy becomes 0 on a standing victim. "
                          "One downward case is measured (Kakashi air B, na_b_04 rec 11: the gate reads "
                          "the capture, (-560, 0)); every other row is inferred from that rule. The floor "
                          "contact at arm9 0x0207ECE4-0x0207ECF4 zeroing a positive +0x26 is the inferred cause",
    "sign": "facing: the attacker's facing picks the screen sign (positive kbX pushes away); "
            "relative: the side the hitting element is on picks it (arm9 0x0208189C-0x020818E4)",
    "zero": "inferred: the propMask bit that sets element +0x14 bit 0x01000000 zeroes both "
            "components at arm9 0x0208186C; not seen live",
    "override": "lead: element +0x14 bit 0x04000000 plus victim element +0x14 & 0x700 replaces the "
                "pair with (0x300, -0x500); what sets the victim bits is not traced; not seen live",
    "band": "type 6 only: staged at the four HP-band multipliers (arm9 0x0209FB64); measured on "
            "Kenshin up X and X",
    "damage": "measured byte (+4, the base damage the damage formula reads at 0x02082428); the hit's "
              "real damage also goes through nature, abilities and resistances",
    "move_records": "records in the fighter anim's CollisionType tracks, first key order; a record "
                    "listed may never land (checked only where the gate joins one: Kakashi Y lists three "
                    "and all three land); a move whose anim has none hits from a spawned object",
    "installs": "measured: the per-frame handler each reaction entry stores to obj+0xFC (read "
                "statically); the live obj+0xFC values in physics.md (0x0215B720, 0x0215B910, "
                "0x0215BAB8, and 0x0215B818 for reaction 4) are these words",
}


def build() -> dict:
    facts = code_facts()
    table = C.move_table()
    chars = [build_char(p, facts, table) for p in C.battle_prefixes()]
    pub = {k: v for k, v in facts.items() if not k.startswith("_")}
    return {
        "_schema": "docs/rebuild/knockback-table.md",
        "_generated_by": "python3 scripts/analysis/knockback_table.py build",
        "_note": NOTE,
        "grade_notes": GRADE_NOTES,
        "code_facts": {k: (f"0x{v:08X}" if isinstance(v, int) and k.endswith("addr") else
                           {str(t): [f"0x{e[0]:08X}", e[1]] for t, e in v.items()} if k == "entry" else
                           {str(t): (f"0x{e:08X}" if e else None) for t, e in v.items()} if k == "installs" else v)
                       for k, v in pub.items()},
        "move_table": [{"id": i, "move": C.NAMES[i], "anim": f"0x{table[i]['anim']:02x}"} for i in MOVE_IDS],
        "characters": chars,
    }


# ------------------------------------------------------------------ the gate

MINUS = str.maketrans({"−": "-", "*": ""})
PAIR = re.compile(r"\(\s*([+-]?\d+)\s*,\s*([+-]?\d+)\s*\)")


def pairs(cell: str) -> list[tuple[int, int]]:
    return [(int(a), int(b)) for a, b in PAIR.findall(cell.translate(MINUS))]


# confirmed-facts character docs with a `kb raw (x,y)` column, and the file their
# records live in (move_records.KNOWN_REC0 for na_b_04 / na_b_02; hs_b_01 is one of
# the rows jus-chrb-colfile-mapping-audit-x7i2 confirms as listed)
DOC_PREFIX = {"kakashi": "na_b_04", "sasuke": "na_b_02", "taikoubou": "hs_b_01"}
ALIAS = {"dash B": "B", "dash Y": "Y"}


def doc_rows(name: str) -> list[dict]:
    path = CHARS / f"{name}.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    out, col = [], None
    for n, line in enumerate(lines, 1):
        if not line.startswith("|"):
            col = None
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if "kb raw (x,y)" in cells:
            col = cells.index("kb raw (x,y)")
            first = cells[0]
            continue
        if col is None or len(cells) <= col or not cells[0].startswith("`"):
            continue
        if first != "input" or cells[1].startswith("—"):
            continue
        label = cells[0].split("`")[1]
        out.append({"move": label, "label": cells[0].replace("`", ""), "kb": pairs(cells[col]), "raw": cells[col],
                    "cite": f"{path.relative_to(REPO)}:{n}"})
    return out


def _case(name, basis, cite, result, detail):
    return {"case": name, "basis": basis, "cite": cite, "result": result, "detail": detail}


def line_of(path: Path, text: str) -> str:
    for n, l in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if text in l:
            return f"{path.relative_to(REPO)}:{n}"
    return f"{path.relative_to(REPO)}:? (text not found: {text!r})"


def signed(r: dict, facing_sign: int) -> tuple[int | None, int]:
    x, y = r["staged"]
    return (facing_sign * x if r["sign"] == "facing" else None), y


def match(pair, rows, facing_sign) -> dict | None:
    for r in rows:
        x, y = signed(r, facing_sign)
        if y == pair[1] and (pair[0] == x if x is not None else abs(pair[0]) == abs(r["staged"][0])):
            return r
    return None


def doc_cases(chars: dict) -> list[dict]:
    cases = []
    for name, prefix in DOC_PREFIX.items():
        char = chars[prefix]
        moves = {m["move"]: m for m in char["moves"]}
        recs = char["records"]
        rows = doc_rows(name)
        b = next(r for r in rows if r["move"] == "B")
        brec = recs[moves["B"]["records"][0]]
        s = 1 if (b["kb"][0][0] > 0) == (brec["staged"][0] > 0) else -1   # screen sign of "away"
        for r in rows:
            mv = ALIAS.get(r["move"], r["move"])
            label = f"{prefix} {r['label']}"
            if mv not in moves:
                cases.append(_case(label, "anim join", r["cite"], "SKIP",
                                   "move anim not static (ids 13/14 read a per-fighter byte)"))
                continue
            m = moves[mv]
            if not m["records"]:
                cases.append(_case(label, "anim join", r["cite"], "SKIP", f"not joined: {m['reason']}"))
                continue
            if not r["kb"]:
                cases.append(_case(label, "anim join", r["cite"], "SKIP", f"no pair in cell {r['raw']!r}"))
                continue
            cand = [recs[i] for i in m["records"]]
            got = [match(p, cand, s) for p in r["kb"]]
            ok = all(got)
            detail = "; ".join(
                f"measured {p} -> " + (f"rec {g['rec']} staged {signed(g, s)[0] if g['sign'] == 'facing' else '±' + str(abs(g['staged'][0]))},{g['staged'][1]} ({g['sign']})"
                                       if g else "no record in anim " + m["anim"] + " predicts it: "
                                       + ", ".join(f"rec {c['rec']} {signed(c, s)}" for c in cand))
                for p, g in zip(r["kb"], got))
            cases.append(_case(label, "anim join", r["cite"], "PASS" if ok else "MISS", detail))
            hit = sorted({g["rec"] for g in got if g})
            listed = sorted(set(m["records"]))
            cases.append(_case(label, "record set", r["cite"], "PASS" if ok and hit == listed else "MISS",
                               f"anim {m['anim']} lists recs {listed}; the measured hits match recs {hit}"))
    return cases


def rec_case(chars, label, prefix, rec, want, basis, cite, band="x1", sign=-1):
    r = chars[prefix]["records"][rec]
    got = r["band"][band] if band != "x1" else r["staged"]
    x = sign * got[0] if r["sign"] == "facing" else want[0] // abs(want[0] or 1) * abs(got[0])
    ok = [x, got[1]] == list(want)
    return _case(label, basis, cite, "PASS" if ok else "MISS",
                 f"rec {rec} (kbX {r['kbX']}, kbY {r['kbY']}, type {r['type']}) at {band}: "
                 f"predicted ({x}, {got[1]}), measured {tuple(want)}")


def fixed_cases(chars: dict) -> list[dict]:
    cases = []
    pc = line_of(LXYT, "| `up B` | `0x21ba16c`")
    cases.append(rec_case(chars, "na_b_04 up B (pointer-traced rec 7)", "na_b_04", 7, (-512, -1652),
                          "pointer-traced record", pc))
    cases.append(rec_case(chars, "na_b_04 down Y (pointer-traced rec 13)", "na_b_04", 13, (-3840, -689),
                          "pointer-traced record", line_of(LXYT, "| `down Y` | `0x21ba1e4`")))
    cases.append(rec_case(chars, "rk_b_01 X finisher x1.5 (pointer-traced rec 20)", "rk_b_01", 20, (-4800, -1239),
                          "pointer-traced record", line_of(LXYT, "| Kenshin `X` finisher"), band="x1.5"))
    kd = CHARS / "kakashi.md"
    cases.append(rec_case(chars, "na_b_04 down B (field-matched rec 14)", "na_b_04", 14, (-2304, -826),
                          "field-matched record (tests the y rounding only)", line_of(kd, "| `down B` | 5 | (18, 6)")))
    cases.append(rec_case(chars, "na_b_04 air Y (field-matched rec 12, relative sign)", "na_b_04", 12, (1280, 0),
                          "field-matched record (tests the y rounding only)", line_of(kd, "| `air Y` | 2 | (10, 0)")))
    for label, prefix, rec, want, text, sign in [
        ("rk_b_01 X finisher x1 (rec 20)", "rk_b_01", 20, (-3200, -826), "| Kenshin `X` finisher (control)", -1),
        ("rk_b_01 up X finisher x1 (rec 16)", "rk_b_01", 16, (-1024, -2065), "| Kenshin `up+X` finisher |", -1),
        ("jj_b_01 up X (rec 20)", "jj_b_01", 20, (-1920, -689), "| Jotaro `up+X` (control)", -1),
        ("jj_b_01 Y finisher (rec 3)", "jj_b_01", 3, (-2560, -689), "| Jotaro `Y` (control)", -1),
        ("sk_b_02 X hit 1 (rec 10)", "sk_b_02", 10, (-3328, -2753), "| Yoh `X` hit 1 |", -1),
        ("sk_b_02 X finisher (rec 12)", "sk_b_02", 12, (-2432, -413), "| Yoh White Swan `X` hit 2", -1),
        ("hk_b_02 up Y hit 10 (rec 7)", "hk_b_02", 7, (2560, -826), "| Raoh `up+Y` hit 10", 1),
        ("mr_b_01 forward Y (rec 5)", "mr_b_01", 5, (1536, -2340), "| Muhyo `forward+Y` tap |", 1),
    ]:
        cases.append(rec_case(chars, label, prefix, rec, want,
                              "field-matched record (tests the y rounding only)", line_of(RR7, text), sign=sign))
    ku = line_of(RR7, "**Kenshin `up+X`** on Luffy")
    for band, want in [("x1.5", (-1536, -3097)), ("x2", (-2048, -4129)), ("x3", (-3072, -6194))]:
        cases.append(rec_case(chars, f"rk_b_01 up X finisher {band} (rec 16)", "rk_b_01", 16, want,
                              "field-matched record, HP band", ku, band=band))
    # pops do not read the HP band: runtime-report-7 poked Raoh's victim to band 3
    r = chars["hk_b_02"]["records"][7]
    got = list(staged(r["kbX"], r["kbY"], r["type"], band=0x300))
    cases.append(_case("hk_b_02 up Y hit 10 (type 5) at HP band x3", "field-matched record, HP band",
                       line_of(RR7, "**No pop reads the HP band.**"), "PASS" if got == [2560, -826] else "MISS",
                       f"rec 7 type {r['type']} predicted {got} at band 0x300, measured (+2560, -826) "
                       "byte-identical to full HP"))
    # plain B through the fighter anim: staged x (runtime-report-7's control table, the eve
    # spot check) and the first-frame vx where the report logged it
    for prefix, want, vx1, cite in [
        ("na_b_02", -768, -672, line_of(RR7, "| Sasuke | **7.0**")),
        ("rk_b_01", -512, -448, line_of(RR7, "| Kenshin | **5.25**")),
        ("hk_b_02", 512, 448, line_of(RR7, "| Raoh | **7.5**")),
        ("mr_b_01", -640, -560, line_of(RR7, "| Muhyo | **6.0**")),
        ("sk_b_02", -640, -560, line_of(RR7, "| Yoh White Swan | **8.0**")),
        ("bc_b_01", -640, None, line_of(CHARS / "eve.md", "| `B` | grounded")),
    ]:
        char = chars[prefix]
        m = next(m for m in char["moves"] if m["move"] == "B")
        r = char["records"][m["records"][0]] if m["records"] else None
        got = r and (-1 if want < 0 else 1) * r["staged"][0]
        ok = r is not None and got == want and r["staged"][1] == 0
        cases.append(_case(f"{prefix} B staged x", "anim join", cite, "PASS" if ok else "MISS",
                           f"rec {r and r['rec']} predicted x {got}, measured {want}"))
        if vx1 is not None:
            # through the row, so the entry table's add/no-add decides: no impulse, no vx
            ff = r and r["first_frame_ground"] and (-1 if want < 0 else 1) * r["first_frame_ground"][0]
            cases.append(_case(f"{prefix} B first vx", "rest start", cite,
                               "PASS" if ff == vx1 else "MISS",
                               f"rec {r and r['rec']} type {r and r['type']} entry adds impulse: "
                               f"{r is not None and r['impulse'] is not None}; predicted first vx {ff}, "
                               f"measured {vx1}"))
    # first-frame vy from rest: only single-hit or grounded-windup moves
    for label, prefix, rec, want, cite in [
        ("rk_b_01 X finisher first vy", "rk_b_01", 20, -534, line_of(RR7, "| Kenshin `X` finisher (control)")),
        ("rk_b_01 up X finisher first vy", "rk_b_01", 16, -1398, line_of(RR7, "| Kenshin `up+X` finisher |")),
        ("jj_b_01 up X first vy", "jj_b_01", 20, -439, line_of(RR7, "| Jotaro `up+X` (control)")),
        ("mr_b_01 forward Y first vy", "mr_b_01", 5, -1590, line_of(RR7, "| Muhyo `forward+Y` tap |")),
    ]:
        r = chars[prefix]["records"][rec]
        got = r["first_frame_ground"] and r["first_frame_ground"][1]
        cases.append(_case(label, "rest start", cite, "PASS" if got == want else "MISS",
                           f"rec {rec} impulse {r['impulse']} -> predicted vy {got}, measured {want}"))
    # the exact recipe, both HP ends (physics.md 4.2), with the measured pre-hit drift
    cite = line_of(PHYSICS, "| low HP (`s=0x300`)")
    r = chars["rk_b_01"]["records"][20]
    for band, want in [("x1", (-2907, -534)), ("x3", (-8507, -1687))]:
        sx, sy = r["band"][band]
        got = first_frame(*impulse(-sx, sy), vx0=-123, ground=True) if r["impulse"] else None
        cases.append(_case(f"rk_b_01 X finisher {band} first frame, drift -123", "exact recipe", cite,
                           "PASS" if got == want else "MISS", f"predicted {got}, measured {want}"))
    # the moves where the victim was already moving: a rest-start model cannot be checked
    for label, prefix, rec, want, text in [
        ("hk_b_02 up Y hit 10 first vy", "hk_b_02", 7, -510, "| Raoh `up+Y` hit 10"),
        ("jj_b_01 Y finisher first vy", "jj_b_01", 3, -399, "| Jotaro `Y` (control)"),
        ("sk_b_02 X finisher first vy", "sk_b_02", 12, -1222, "| Yoh White Swan `X` hit 2"),
    ]:
        r = chars[prefix]["records"][rec]
        cases.append(_case(label, "rest start", line_of(RR7, text), "SKIP",
                           f"victim moving before the hit (earlier hits of the same move); rest model "
                           f"gives {r['first_frame_ground'][1]}, measured {want}"))
    cases += capture_cases(chars) + yusuke_cases(chars)
    return cases


KAKASHI_AIRB = REPO / "docs" / "research" / "feel-captures" / "kakashi-2026-09-03" / "airB.jsonl.gz"


def capture_cases(chars: dict) -> list[dict]:
    """Read the committed Kakashi air B capture (standing victim): the latch frame's
    staged pair, and the victim velocity on the next frame."""
    cite = str(KAKASHI_AIRB.relative_to(REPO))
    if not KAKASHI_AIRB.exists():
        return [_case("na_b_04 air B on a standing victim", "capture", cite, "MISS", "capture missing")]
    with gzip.open(KAKASHI_AIRB, "rt", encoding="utf-8") as fh:
        frames = [json.loads(line) for line in fh]
    latch = next(i for i, f in enumerate(frames) if any(f["w"]["v_M140"][8:12]))
    m = struct.unpack_from("<hh", bytes(frames[latch]["w"]["v_M140"]), 8)
    v = struct.unpack_from("<hh", bytes(frames[latch + 1]["w"]["v_elem"]), 0x24)
    r = chars["na_b_04"]["records"][11]
    sign = -1 if m[0] < 0 else 1
    want_m = (sign * r["staged"][0], r["staged"][1])
    ground = r["first_frame_ground"]
    want_v = ground and (sign * ground[0], ground[1])
    air = r["first_frame_air"]
    return [
        _case("na_b_04 air B (rec 11) staged pair, capture", "capture", cite,
              "PASS" if m == want_m else "MISS",
              f"frame {frames[latch]['f']}: predicted {want_m}, read {m}"),
        _case("na_b_04 air B (rec 11) first frame on a standing victim, capture", "capture", cite,
              "PASS" if v == want_v else "MISS",
              f"frame {frames[latch + 1]['f']}: predicted ground {want_v} (air model would give "
              f"{air and (sign * air[0], air[1])}), read {v}"),
    ]


def yusuke_cases(chars: dict) -> list[dict]:
    """Yusuke's specials: yusuke.md's measured staged push, type and damage per hit,
    each matched to one yh_b_01 record, and the anim that record is keyed in."""
    yd = REPO / "docs" / "rebuild" / "characters" / "yusuke.md"
    upx = line_of(yd, "| staged push | (-768, 0), (-640, 0)")
    xl = line_of(yd, "| staged push (raw, Yusuke facing left) | L1")
    recs = chars["yh_b_01"]["records"]
    cases = []
    for label, want, typ, dmg, rec, ref, cite in [
        ("up X hit 1", (-768, 0), 2, 5, 16, "yh_b_01 0x2e", upx),
        ("up X hit 2", (-640, 0), 1, 5, 17, "yh_b_01 0x2e", upx),
        ("up X hits 3, 5", (-256, -138), 1, 2, 18, "yh_b_01 0x2e", upx),
        ("up X hits 4, 6", (-128, -413), 2, 2, 19, "yh_b_01 0x2e", upx),
        ("up X hit 7", (-1920, -2891), 5, 13, 20, "yh_b_01 0x2e", upx),
        ("up X hit 8 (shot)", (-3840, -1377), 6, 20, 21, "yh_b_01_6 0xab", upx),
        ("X level 1", (-4096, -1927), 5, 46, 29, "yh_b_01_6 0xa5", xl),
        ("X level 2", (-4608, -1927), 6, 56, 30, "yh_b_01_6 0xa6", xl),
    ]:
        # the one record keyed in the move's motion whose staged pair, type and damage
        # all match (rec 23, keyed in 0x2a, repeats rec 18's bytes)
        hits = [r for r in recs if (-r["staged"][0], r["staged"][1]) == want
                and r["type"] == typ and r["damage"] == dmg and any(u.startswith(ref) for u in r["refs"])]
        ok = [h["rec"] for h in hits] == [rec]
        cases.append(_case(f"yh_b_01 {label} (rec {rec})", "field-matched record, anim-keyed", cite,
                           "PASS" if ok else "MISS",
                           f"measured {want} type {typ} damage {dmg} -> recs {[h['rec'] for h in hits]}"
                           f" (want [{rec}], keyed in {ref})"))
    # Eve Y through the anim join (eve.md spot check: -1920, 16 damage)
    char = chars["bc_b_01"]
    m = next(m for m in char["moves"] if m["move"] == "Y")
    got = [(-char["records"][i]["staged"][0], char["records"][i]["staged"][1]) for i in m["records"]]
    cases.append(_case("bc_b_01 Y staged x", "anim join", line_of(CHARS / "eve.md", "| `Y` | grounded"),
                       "PASS" if got == [(-1920, 0)] and m["records"] == [1] else "MISS",
                       f"anim {m['anim']} recs {m['records']} predicted {got}, measured [(-1920, 0)]"))
    return cases


def gate(table: dict) -> list[dict]:
    chars = {c["prefix"]: c for c in table["characters"]}
    return doc_cases(chars) + fixed_cases(chars)


# ------------------------------------------------------------------ cli

def dump(table: dict) -> str:
    """Indented, but each record and move row on one line so the file stays small."""
    rows = {}

    def mark(obj):
        if isinstance(obj, dict) and ("rec" in obj or "move" in obj and "anim" in obj) \
                or isinstance(obj, list) and len(obj) == 2 and isinstance(obj[1], bool) \
                or isinstance(obj, list) and obj and all(isinstance(v, int) for v in obj):
            k = f"@@row{len(rows)}@@"
            rows[k] = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
            return k
        if isinstance(obj, dict):
            return {k: mark(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [mark(v) for v in obj]
        return obj

    text = json.dumps(mark(table), indent=1, ensure_ascii=False)
    for k, v in rows.items():
        text = text.replace(f'"{k}"', v)
    return text + "\n"


def show(char: dict) -> str:
    out = [char["prefix"] + " " + (", ".join(f"{n['name']} (chr_b {n['chr_b']})" for n in char["names"])
                                   or "(no name)")]
    recs = char["records"]
    for m in char["moves"]:
        out.append(f"  {m['id']:>2} {m['move']:<24} anim {m['anim']}" + (f"  [{m['reason']}]" if m["reason"] else ""))
        for i in m["records"]:
            r = recs[i]
            out.append(f"       rec {i:>3} type {r['type']:>2} dmg {r['damage']:>3} kb ({r['kbX']:>4},{r['kbY']:>4}) "
                       f"staged {r['staged']} impulse {r['impulse']} px {r['px']} sign {r['sign']}"
                       + (" ZERO" if r["zero"] else "") + (" OVERRIDE" if r["override"] else ""))
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="write docs/rebuild/knockback-table.json")
    sub.add_parser("check", help="the gate: committed JSON is fresh and every joined case passes")
    s = sub.add_parser("show", help="print one character's moves and records")
    s.add_argument("prefix")
    a = ap.parse_args(argv)
    table = build()
    if a.cmd == "build":
        OUT.write_text(dump(table), encoding="utf-8")
        print(f"wrote {OUT.relative_to(REPO)}")
        return 0
    if a.cmd == "show":
        print(show(next(c for c in table["characters"] if c["prefix"] == a.prefix)))
        return 0
    try:
        cases = gate(table)
    except FileNotFoundError as e:
        fresh = OUT.exists() and OUT.read_text(encoding="utf-8") == dump(table)
        print(f"gate skipped: needs an input that is not part of this repository ({e.filename})")
        print(f"committed JSON {'is fresh' if fresh else 'is STALE: run build'}")
        return 0 if fresh else 1
    fresh = OUT.exists() and OUT.read_text(encoding="utf-8") == dump(table)
    for c in cases:
        print(f"{c['result']}  [{c['basis']}] {c['case']}: {c['detail']}  ({c['cite']})")
    n = {k: sum(c["result"] == k for c in cases) for k in ("PASS", "MISS", "SKIP")}
    print(f"{n['PASS']} pass, {n['MISS']} miss, {n['SKIP']} skip (not joinable, listed above); "
          f"committed JSON {'is fresh' if fresh else 'is STALE: run build'}")
    return 0 if fresh and not n["MISS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
