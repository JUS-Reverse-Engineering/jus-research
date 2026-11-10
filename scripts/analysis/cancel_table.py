#!/usr/bin/env python3
"""Static cancel table for every JUS battle character: when each move's cancel
window opens and which moves it can cancel into. No emulator.

Research note: docs/research/findings/cancel-windows-static-2026-09-25.md.
Schema: docs/rebuild/cancel-table.md. Output: docs/rebuild/cancel-table.json.

Two sources, both static:

  When. Each move's animation NoteTrack (`chr/<prefix>.aar` -> `<prefix>.amt`,
      read by anim_events.py) carries an op3 sub0 event. Arg 0x1 makes the
      fighter callback 0x02157A44 store 1 to fighter+0xF3 (ground flag); arg
      0x15 stores 1 to +0xF4 (air flag). The flags are cleared only when a
      move starts (0x0215A030-38). Predicted cancel start = the earliest such
      key frame + 2. The +2 is one constant read off Kakashi's six §8 register
      windows; the kit docs derive those starts (onset minus lag), so it is
      inferred, and Yusuke's four starts were held out as a check. Live
      checks measured it end to end for Kakashi B and air B (LIVE_STARTS).
  Into what. One 12-byte record per move id at ov6 0x021712B8: u32 anim,
      u32 mask, u32 misc. The state-9 handler (0x0215A4AC-0x0215A58C) drops a
      follow-up whose bit is set in fighter+0xC4 (C0 | C4 at the reader);
      C4 is the OR of the masks of every move in the chain so far.

Only the code facts the rules rest on are decoded here, straight from
ov06.bin; `code_facts()` returns them and the test pins each one.

Usage:
    python3 scripts/analysis/cancel_table.py build    # write JSON and the schema field row
    python3 scripts/analysis/cancel_table.py check    # the gate: exit 0 = pass, 1 = any miss
    python3 scripts/analysis/cancel_table.py show na_b_04
"""
from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import anim_events as E  # noqa: E402
import move_records as mr  # noqa: E402

REPO = HERE.parent.parent
OVERLAYS = REPO / "jus_files" / "overlays"
OV6 = OVERLAYS / "ov06.bin"
OUT = REPO / "docs" / "rebuild" / "cancel-table.json"
ANIM_TIMING = REPO / "docs" / "rebuild" / "anim-timing.json"
NOTE = "docs/research/findings/cancel-windows-static-2026-09-25.md"
DOCS = {"na_b_04": REPO / "docs" / "rebuild" / "characters" / "kakashi.md",
        "yh_b_01": REPO / "docs" / "rebuild" / "characters" / "yusuke.md"}

TABLE = 0x021712B8
STRIDE = 12
MOVE_IDS = range(1, 15)          # every id the three neutral readers return
# Every row a reader indexes: X and up X (ids 13, 14) read their anim from row
# id + 2*(byte - 3) (0x02159FB8-0x02159FDC), byte = koma size - 1 for koma 4-8,
# so koma 8's up X reads row 22; row 23 is all zero.
TABLE_ROWS = range(1, 23)
NORMAL_IDS = range(1, 11)        # ids whose follow-up check is the C4 mask test
KEY_OP, KEY_SUB = 3, 0
KEY_ARGS = {0x1: "ground", 0x15: "air"}
START_OFFSET = 2                 # cancel start = key frame + 2
# (prefix, id) -> where a live check timed key -> new move start end to end.
LIVE = "docs/research/feel-captures/cancel-live-checks-2026-09-25/RESULTS.md"
LIVE_STARTS = {("na_b_04", 1): f"{LIVE} (b): ground key +11, cancel start +12, Y starts +13",
               ("na_b_04", 9): f"{LIVE} (c): air key +14, cancel start +15, air Y starts +16"}

SPECIAL_IDS = (13, 14)           # X, up X: the ground reader's special targets
SPECIAL_INTO = ("X", "up X")     # their kit slot names
# (prefix, id) -> the live run that timed an X cancel out of that move.
XCANCEL = "docs/research/feel-captures/yusuke-xcancel-airy-2026-09-25/RESULTS.md"
PARITY = "docs/research/feel-captures/yusuke-matrix-2026-09-30/r1/matrix/RESULTS.md"
LIVE_SPECIAL = {("yh_b_01", 1): f"{XCANCEL} section 1 (B_X_k5..k20: X starts at s 11, state 9)",
                ("yh_b_01", 2): f"{XCANCEL} section 1 (Y_X_k20..k40: X starts at s 27, state 9)",
                ("yh_b_01", 4): f"{XCANCEL} section 1 (sideY_X: flag at s 29, X starts at s 30)",
                ("yh_b_01", 6): f"{PARITY} (up Y: source opening 29, state-9 special entry 30, one SP bar)"}
SPECIAL_GATE = ("grounded (0x0215A708) + 1 SP bar (0x0207834C), "
                "free if slot+0x5CE/+0x5CF")

NAMES = {1: "B", 2: "Y", 3: "side B", 4: "side Y", 5: "up B", 6: "up Y",
         7: "down B", 8: "down Y", 9: "air B", 10: "air Y",
         11: "id 11 (input 0x1000)", 12: "id 12 (fighter+0xD1 set)",
         13: "X (id 13)", 14: "up X (id 14)"}
NAMES.update({i: f"{'X' if i % 2 else 'up X'} (koma {(i-13)//2+4})" for i in range(15,23)})
IDS = {v: k for k, v in NAMES.items()}

# ------------------------------------------------------------------ ov6 bytes

_OV6 = None


def ov6() -> tuple[bytes, int]:
    global _OV6
    if _OV6 is None:
        meta = next(o for o in json.loads((OVERLAYS / "overlays.json").read_text())
                    if o["id"] == 6)
        _OV6 = (OV6.read_bytes(), meta["ram_address"])
    return _OV6


def word(addr: int) -> int:
    buf, base = ov6()
    return struct.unpack_from("<I", buf, addr - base)[0]


def in_image(addr: int) -> bool:
    buf, base = ov6()
    return base <= addr < base + len(buf)


def branch_target(addr: int) -> int:
    """B/BL at addr -> target."""
    w = word(addr)
    if (w >> 25) & 0x7 != 0b101:
        raise ValueError(f"0x{addr:08X} is not a branch")
    off = w & 0xFFFFFF
    if off & 0x800000:
        off -= 1 << 24
    return addr + 8 + (off << 2)


def pc_literal(addr: int) -> tuple[int, int]:
    """LDR Rd,[pc,#imm] at addr -> (literal address, literal value)."""
    w = word(addr)
    if (w & 0x0F7F0000) != 0x051F0000:
        raise ValueError(f"0x{addr:08X} is not ldr rX,[pc,#imm]")
    imm = w & 0xFFF
    lit = addr + 8 + (imm if w & (1 << 23) else -imm)
    return lit, word(lit)


def strb_offset(addr: int) -> int:
    """STRB/LDRB Rd,[Rn,#imm] at addr -> imm."""
    w = word(addr)
    if (w & 0x0E400000) != 0x04400000:
        raise ValueError(f"0x{addr:08X} is not a byte load/store")
    return w & 0xFFF


def reader_returns(start: int, end: int) -> list[int]:
    """Values a reader returns: each `mov r0,#imm` followed by a `pop {..pc}`
    with the same condition, in [start, end)."""
    out = []
    for a in range(start, end - 4, 4):
        w, nxt = word(a), word(a + 4)
        is_mov = (w & 0x0FEFF000) == 0x03A00000
        is_pop = (nxt & 0x0FFF8000) == 0x08BD8000
        if is_mov and is_pop and (w >> 28) == (nxt >> 28):
            rot, imm = (w >> 8) & 0xF, w & 0xFF
            val = ((imm >> (2 * rot)) | (imm << (32 - 2 * rot))) & 0xFFFFFFFF
            if val not in out:
                out.append(val)
    return sorted(out)


def switch_case(table_addr: int, case: int) -> int:
    """0x02157A44's jump table: `addls pc,pc,r2,lsl #2` at table_addr, case -> handler."""
    return branch_target(table_addr + 8 + 4 * case)


def code_facts() -> dict:
    """The code facts the extractor rests on, decoded from ov06.bin."""
    sw = 0x02157A60
    f = {
        "notetrack_op3_handler": word(0x0217200C + 4 * KEY_OP),
        "op3_sub0_handler": word(0x02172000 + 4 * KEY_SUB),
        "fighter_callback_literal": pc_literal(0x02156CD0),
        "callback_case_1": switch_case(sw, 0x1),
        "callback_case_0x15": switch_case(sw, 0x15),
        "callback_case_0x1d": switch_case(sw, 0x1D),
        "store_0x02157B90": strb_offset(0x02157B90),
        "store_0x02157B9C": strb_offset(0x02157B9C),
        "store_0x02157BA8": strb_offset(0x02157BA8),
        "init_clears": [strb_offset(a) for a in (0x0215A034, 0x0215A038, 0x0215A044)],
        "ground_reader_call": branch_target(0x0215A464),
        "ground_flag_read": strb_offset(0x0215A46C),
        "air_reader_call": branch_target(0x0215A4A0),
        "air_flag_read": strb_offset(0x0215A4A4),
        "ground_returns": reader_returns(0x0215A720, 0x0215A824),
        "air_returns": reader_returns(0x0215A8C0, 0x0215A8F8),
        "down_returns": reader_returns(0x0215A8F8, 0x0215A968),
        "neutral_readers": [word(0x02172178 + 4 * i) for i in range(3)],
        "mask_literal_cancel": pc_literal(0x0215A56C),
        "mask_literal_neutral": pc_literal(0x02159E08),
        "anim_literal_init": pc_literal(0x02159F4C),
        "system_jump": [branch_target(a) for a in (0x0215A4FC, 0x0215A500, 0x0215A504, 0x0215A508)],
    }
    f["table_in_ov6_image"] = all(in_image(v) for _, v in (
        f["mask_literal_cancel"], f["mask_literal_neutral"], f["anim_literal_init"]))
    return f


def ov_word(ov: int, addr: int) -> int:
    """u32 at addr in overlay `ov` (stored raw, overlays.json)."""
    meta = next(o for o in json.loads((OVERLAYS / "overlays.json").read_text()) if o["id"] == ov)
    data = (OVERLAYS / f"ov{ov:02d}.bin").read_bytes()
    return struct.unpack_from("<I", data, addr - meta["ram_address"])[0]


def _imm(w: int) -> int:
    rot, imm = (w >> 8) & 0xF, w & 0xFF
    return ((imm >> (2 * rot)) | (imm << (32 - 2 * rot))) & 0xFFFFFFFF


def c4_readers() -> dict:
    """Every reader of the masks the move table ORs into fighter+0xC4, and of its misc word.
    An immediate-offset load census of arm9 and every overlay finds three bit tests of a +0xC4
    word, the ones below; arm9's other +0xC4 loads are counters and vtable calls, and the
    overlays that load at ov6's base never run with it. PF-31e's laws rest on these facts.
      latch_skip  state 9 latches reader id r5 only if bit r5 of C0 | C4 is clear
                  (0x0215A4C8), but `cmp r5,#imm; ldrne r0,[r6,#0xC4]` (0x0215A4B4-BC) leaves
                  C4 out for this id; its fire path (system_jump[1], 0x0215A590-0x0215A614)
                  never reads C4 and the fire test 0x0215A55C sees only the other ids
      ai_load     ov11 0x0217BBE4 loads [[ai+0x20]+0xC4] (the offset) ...
      ai_mask     ... ORs this literal (0x0217BBE0) ...
      ai_ids      ... and offers each id in [start, bound) whose bit is clear (0x0217BBFC-C10)
      misc_bytes  (load site, address) of every read of the misc word: one ldrsb per byte, the
                  literals 0x02159E48 / 0x0215A0E0 / 0x0215A398; byte 3 has no reader
    """
    def ldrsb(a: int) -> bool:
        return (word(a) & 0x0E1000F0) == 0x001000D0
    sites = ((0x02159E48, 0x02159E50), (0x0215A0E0, 0x0215A0E8), (0x0215A398, 0x0215A3A0))
    return {
        "latch_skip": _imm(word(0x0215A4B4)) if (word(0x0215A4B4) & 0x0FFFF000) == 0x03550000 else None,
        "latch_skip_conditional_load": word(0x0215A4BC) >> 28 == 0x1 and (word(0x0215A4BC) & 0xFFF) == 0xC4,
        "ai_load": ov_word(11, 0x0217BBE4) & 0xFFF,
        "ai_mask": ov_word(11, 0x0217BBE0 + 8 + (ov_word(11, 0x0217BBE0) & 0xFFF)),   # ldr r0,[pc,#imm]
        "ai_ids": (_imm(ov_word(11, 0x0217BBE8)), _imm(ov_word(11, 0x0217BC0C))),
        "misc_bytes": [(load, pc_literal(lit)[1]) for lit, load in sites if ldrsb(load)],
    }


def c4_tested_bits() -> set[int]:
    """Bits of +0xC4 some reader tests: the state-9 reader ids except 0 and latch_skip, plus
    the AI's offered ids."""
    f, r = code_facts(), c4_readers()
    state9 = set(f["ground_returns"]) | set(f["air_returns"])
    start, bound = r["ai_ids"]
    ai = {i for i in range(start, bound) if not r["ai_mask"] >> i & 1}
    return (state9 - {0, r["latch_skip"]}) | ai


def table_row(i: int) -> dict:
    """Row i of the ov6 move table: u32 anim, u32 mask, u32 misc."""
    a = TABLE + STRIDE * i
    anim, mask, misc = (word(a + 4 * k) for k in range(3))
    return {"id": i, "anim": anim, "mask": mask, "misc": misc, "addr": a}


def move_table() -> dict[int, dict]:
    return {i: table_row(i) for i in MOVE_IDS}


def followups(mask: int, kind: str) -> list[int]:
    """Normal ids the reader of `kind` offers and the mask does not block."""
    targets = (1, 2, 3, 4, 5, 6) if kind == "ground" else (9, 10)
    return [t for t in targets if not mask & (1 << t)]


# ------------------------------------------------------------------ characters

def battle_prefixes() -> list[str]:
    d = mr.CHRARC.read_bytes()
    n = struct.unpack_from("<H", d, 6)[0]
    names = []
    for i in range(n):
        io_ = struct.unpack_from("<H", d, 0x12 + 2 * i)[0]
        end = d.index(b"\0", io_ + 0x12)
        names.append(d[io_ + 0x12:end].decode("ascii"))
    return sorted(m[4:-4] for m in names if re.fullmatch(r"chr/[a-z]{2}_b_\d\d\.aar", m))


def names_for(prefix: str) -> list[dict]:
    """chr_b rows for this prefix, annotated (ambiguous/unobserved) rows included:
    move_records.chrb_names_for, shared with the knockback, mash and ua tables."""
    return mr.chrb_names_for(prefix)


def keys_of(row: dict) -> dict[str, list[int]]:
    out = {"ground": [], "air": []}
    for key in row["notes"]:
        for ev in key["events"]:
            if ev["op"] == KEY_OP and ev["sub"] == KEY_SUB and ev["arg"] in KEY_ARGS:
                out[KEY_ARGS[ev["arg"]]].append(key["frame"])
    return out


def played_anims() -> dict[str, dict[str, int]]:
    """prefix -> move -> the anim a live capture matched (anim-timing.json)."""
    out = {}
    for char in json.loads(ANIM_TIMING.read_text(encoding="utf-8"))["characters"].values():
        out[char["prefix"]] = {m["move"]: int(m["anim"], 16) for m in char["moves"]
                               if m["move"] in IDS and m.get("grade") != "static"}
    return out


def special_cancel(prefix: str, row: dict) -> tuple[dict | None, str | None]:
    """(special_cancel, reason) for a finished row. A ground cancel window (the
    F3 flag) also offers X and up X (reader 0x0215A720), so the start is the
    ground cancel_start. Air windows give none (reader 0x0215A8C0 returns only
    9/10), so a move needs a ground key. The initial slot id does not select the window reader."""
    i = row["id"]
    if i > 10:
        return None, "not one of the ten normals; a cancelled X is terminal and ids 11-14 never cancel out"
    ground = (row["cancel_start"] or {}).get("ground")
    if ground is not None:
        return {"into": list(SPECIAL_INTO), "start": {"ground": ground},
                "gate": SPECIAL_GATE, "terminal": True}, None
    if row["key"] and "ground" not in row["key"]:
        return None, ("no ground key (air key only): the air reader 0x0215A8C0 returns only "
                      "ids 9 and 10, so no X")
    return None, f"no ground cancel window ({row['reason']})"


def move_row(prefix: str, rec: dict, ev: dict | None, err: str | None,
             played: int | None = None) -> dict:
    """One (character, move id) row, plus its special_cancel."""
    row = _move_row(prefix, rec, ev, err, played)
    g = row["grades"]
    row["special_cancel"], row["special_reason"] = special_cancel(prefix, row)
    if row["id"] <= 10:
        live = LIVE_SPECIAL.get((prefix, row["id"]))
        g["special_cancel"] = "measured" if live else "inferred"
        if live:
            row["cites"]["special_cancel"] = live
            if row["special_cancel"] is None:
                row["special_reason"] += (
                    "; live-measured that X cancels out of this move, but the static start "
                    "is unresolved")
    return row


def _move_row(prefix: str, rec: dict, ev: dict | None, err: str | None,
              played: int | None = None) -> dict:
    """One (character, move id) row. Grades per field; their qualifiers are in
    the JSON's top-level `grade_notes`."""
    i = rec["id"]
    # A move's name is measured only where a live capture matched the move to
    # this table anim (anim-timing.json: Kakashi, Yusuke); elsewhere it is the
    # shared table's id order, inferred.
    named = i <= 10 and played is not None and played == rec["anim"]
    g = {"move": "measured" if named else ("inferred" if i <= 10 or i >= 13 else "lead"),
         "anim": None, "key": None, "cancel_start": None, "mask": "measured", "followups": None,
         "special_cancel": None}
    row = {"id": i, "move": NAMES[i], "anim": None, "frames": None, "key": None,
           "cancel_start": None, "mask": f"0x{rec['mask']:08x}", "followups": None,
           "reason": None, "special_cancel": None, "special_reason": None, "grades": g,
           "cites": {"member": f"ChrArc.aar:chr/{prefix}.aar/{prefix}.amt", "anim": None,
                     "table": f"0x{rec['addr']:08X} (ov06.bin+0x{rec['addr'] - ov6()[1]:05x})"}}
    anim = rec["anim"]
    row["anim"] = row["cites"]["anim"] = f"0x{anim:02x}"
    g["anim"] = "measured"
    if err:
        row["reason"] = f"ALMT parse failed: {err}"
        return row
    if played is not None and played != anim:
        row["reason"] = (f"docs/rebuild/anim-timing.json measures anim 0x{played:02x} for this move, "
                         f"the table gives 0x{anim:02x}; which NoteTrack opens the window is unresolved")
        return row
    a = ev.get(anim)
    if a is None:
        row["reason"] = f"anim 0x{anim:02x} not in {prefix}.amt"
        return row
    sp01 = [e["error"] for e in a.get("node_errors", []) if e["node"] == "SP01"]
    if sp01:
        row["reason"] = f"the SP01 node (NoteTrack) failed to decode: {sp01[0]}"
        return row
    row["frames"] = a["frames"]
    row["key"] = {kind: v for kind, v in keys_of(a).items() if v}
    g["key"] = "measured"
    if not row["key"]:
        row["reason"] = "no op3 sub0 arg 0x1 or 0x15 key: no cancel window by this mechanism"
        row["followups"] = []
        g["followups"] = "inferred"
        return row
    if any(min(v) >= a["frames"] for v in row["key"].values()):
        row["reason"] = "cancel key at or after the anim's last frame"
        return row
    row["cancel_start"] = {kind: min(v) + START_OFFSET for kind, v in row["key"].items()}
    live = LIVE_STARTS.get((prefix, i))
    g["cancel_start"] = "measured" if live else "inferred"
    if live:
        row["cites"]["cancel_start"] = live
    row["followups"] = [NAMES[t] for kind in row["key"] for t in followups(rec["mask"], kind)]
    g["followups"] = "inferred"
    return row


GRADE_NOTES = {
    "measured": "read from bytes: ov06.bin (table, code facts) or the character's .amt (keys)",
    "inferred": "follows from measured pieces, not traced end to end; see the research note",
    "lead": "a reading with an untraced gate; do not build on it",
    "anim": "the table's anim is the one 0x02159EF8 hands to 0x02157450 at move start; a "
            "per-move handler can change what plays (Yusuke side Y plays 0x28, anim-timing.json)",
    "cancel_start": "earliest key + 2, in anim frames from the anchor (frame 0 = anim frame 0); "
                    "measured where cites.cancel_start names the live check, else inferred; "
                    "it equals game frames only while the anim clock runs (a charge pause or a "
                    "mash loop before the key adds frames)",
    "followups": "reader targets (ground window: ids 1-6; air window: ids 9-10) whose mask bit "
                 "is clear; assumes fighter+0xC0 (a second mask, never read statically) has the "
                 "bit clear; in a chain the masks OR together (route())",
    "special_cancel": "a ground cancel window (the F3 flag from the move's ground NoteTrack key) also "
                      "offers X (id 13) and up X (id 14). Reader 0x0215A720 returns 14 for input & "
                      "0x41 == 0x41 and 13 for input & 0x40, after its B/Y and id-11 tests, so a held "
                      "B or Y shadows X. No mask blocks them: every mask in ids 1-10 has bits 12-14 "
                      "clear. The window is the normals' (start = earliest ground key + 2, open until "
                      "the animation ends); an earlier press is buffered in +0xC8. Gates: grounded "
                      "([[fighter+0x1A8]+0x10]+0x78 & 2, 0x0215A708) and one SP bar (0x0207834C with "
                      "cost 1 at 0x0215A524: free if slot+0x5CE or +0x5CF is nonzero, refused at 0 "
                      "bars). A cancelled X runs in state 9 and C4 becomes all ones, so nothing "
                      "cancels out of it (terminal). A move needs a ground key: air-key-only moves "
                      "(Eve and Kakashi up Y, Yusuke up B) and every air window give no special "
                      "(reader 0x0215A8C0 returns only 9 and 10). Slot ids 9/10 may have ground windows. Not X "
                      "gates: id 12 (fighter+0xD1, a one-tick dream-attack request) and "
                      "+0x1CC/+0x1D0 (the active koma slot and its snapshot) only affect the id-12 "
                      "path (0x0215A590-0x0215A614); id 11 never cancels in (0x0215A4FC). Grade: "
                      "measured for the code; live-measured for Yusuke B, Y, side Y and up Y (cites."
                      "special_cancel: " + XCANCEL + " and " + PARITY + "), inferred for every other "
                      "move and character. Side Y is null there: its static start is unresolved "
                      "(anim conflict), though the live run timed the cancel.",
    "system_followups": "see special_cancel: ids 13 and 14 are the special cancels; id 12 and id 11 "
                        "are not followups of a normal.",
}


def build() -> dict:
    facts = code_facts()
    table = move_table()
    played = played_anims()
    chars = []
    for p in battle_prefixes():
        err, ev = None, None
        try:
            ev = E.anim_events(E.load_almt(p))
        except BaseException as ex:  # SystemExit from the loaders, struct errors
            err = f"{type(ex).__name__}: {ex}"
        chars.append({"prefix": p, "names": names_for(p),
                      "moves": [move_row(p, table[i], ev, err, played.get(p, {}).get(NAMES[i]))
                                for i in MOVE_IDS]})
    return {
        "_schema": "docs/rebuild/cancel-table.md",
        "_generated_by": "python3 scripts/analysis/cancel_table.py build",
        "_note": NOTE,
        "grade_notes": GRADE_NOTES,
        "move_table": [{"id": r["id"], "move": NAMES[r["id"]], "anim": f"0x{r['anim']:02x}",
                        "mask": f"0x{r['mask']:08x}", "misc": f"0x{r['misc']:08x}",
                        "addr": f"0x{r['addr']:08X}"} for r in table.values()],
        "move_table_grade": "measured (ov06.bin bytes)",
        "code_facts": {k: (f"0x{v:08X}" if isinstance(v, int) and not isinstance(v, bool) else
                           [f"0x{x:08X}" for x in v] if isinstance(v, (list, tuple)) else v)
                       for k, v in facts.items()},
        "characters": chars,
    }


# ------------------------------------------------------------------ routes

def route(char: dict, ids: list[int]) -> tuple[bool, str, int | None]:
    """Is the chain ids[0] -> ids[1] -> ... allowed? -> (ok, why, start of last hop)."""
    moves = {m["id"]: m for m in char["moves"]}
    c4 = int(moves[ids[0]]["mask"], 16)
    start = None
    for src, dst in zip(ids, ids[1:]):
        m = moves[src]
        if src in SPECIAL_IDS:
            return False, f"{NAMES[src]} is terminal (C4 is all ones after a cancelled X)", None
        kind = "air" if dst in (9, 10) else "ground"
        if dst in SPECIAL_IDS:
            sc = m.get("special_cancel")
            if not sc or "ground" not in sc["start"]:
                return False, (f"{NAMES[src]} has no ground window for {NAMES[dst]} "
                               f"({m.get('special_reason') or m.get('reason')})"), None
            start = sc["start"]["ground"]
            continue
        if dst not in NORMAL_IDS:
            return False, f"{NAMES[dst]} is not a normal cancel target", None
        if m["cancel_start"] is None or kind not in m["cancel_start"]:
            return False, f"{NAMES[src]} has no {kind} window ({m['reason']})", None
        if c4 & (1 << dst):
            return False, f"bit {dst} set in C4 0x{c4:x}", None
        start = m["cancel_start"][kind]
        c4 |= int(moves[dst]["mask"], 16)
    return True, "allowed", start


# ------------------------------------------------------------------ the gate

ROW = re.compile(r"^\| `([^`]+)` → `([^`]+)` \|(.*)$")
START = re.compile(r"k=(\d+): \+(\d+) \((\w+)")
CLASS = re.compile(r"k=(\d+): ([a-z-]+)")


def doc_routes(path: Path) -> list[dict]:
    """Rows of the generated cancel-routes block (declared routes + measured negatives)."""
    text = path.read_text(encoding="utf-8")
    m = re.search(r"<!-- kit:begin cancel-routes -->(.*?)<!-- kit:end cancel-routes -->", text, re.S)
    if not m:
        raise SystemExit(f"{path}: no cancel-routes block")
    out = []
    first = text[:m.start()].count("\n") + 1
    for n, line in enumerate(m.group(1).splitlines()):
        r = ROW.match(line)
        if not r:
            continue
        cells = [c.strip() for c in r.group(3).split("|")]
        if len(cells) >= 5:        # declared route: offsets, coverage, classes, starts, testimony
            classes = dict((int(k), c) for k, c in CLASS.findall(cells[2]))
            found = START.findall(cells[3])
            starts = {int(k): int(v) for k, v, _ in found}
            start_grades = sorted({g for _, _, g in found})
        else:                      # measured negative: offsets, classification, coverage
            classes = {0: cells[1]}
            starts, start_grades = {}, []
        out.append({"src": r.group(1), "dst": r.group(2), "classes": classes,
                    "starts": starts, "start_grades": start_grades, "line": first + n})
    return out


def _case(name, grade, cite, ok, detail):
    return {"case": name, "grade": grade, "cite": cite, "pass": bool(ok), "detail": detail}


def doc_start(r: dict) -> tuple[int, bool] | None:
    """A cancelling row's start: (earliest start, exact?). Exact when an early
    press waited for the window (start later than the earliest cancelling k);
    otherwise the window may open earlier, so it is an upper bound."""
    if not r["starts"]:
        return None
    got = min(r["starts"].values())
    k_min = min(k for k, c in r["classes"].items() if c == "cancel")
    return got, got > k_min


def kind_of(move: str) -> str:
    return "air" if IDS.get(move) in (9, 10) else "ground"


def gate(table: dict) -> list[dict]:
    chars = {c["prefix"]: c for c in table["characters"]}
    cases = []
    for prefix, path in DOCS.items():
        char = chars[prefix]
        rel = path.relative_to(REPO)
        for r in doc_routes(path):
            name = f"{prefix} {r['src']} -> {r['dst']}"
            cite = f"{rel}:{r['line']}"
            if r["src"] not in IDS or r["dst"] not in IDS:
                cases.append(_case(name, "measured", cite, False, "move name not in the move table"))
                continue
            ok, why, start = route(char, [IDS[r["src"]], IDS[r["dst"]]])
            cancelled = any(c == "cancel" for c in r["classes"].values())
            if not cancelled:
                cases.append(_case(f"{name} blocked", "measured", cite, not ok,
                                   f"measured no cancel; predicted {why}"))
                continue
            cases.append(_case(f"{name} allowed", "measured", cite, ok,
                               f"measured cancel; predicted {why}"))
            # The start is the kit doc's derivation (successor onset minus the
            # follow-up's standalone lag, or the frame the first box is cut),
            # graded as the doc grades it.
            grade = "/".join(r["start_grades"]) or "ungraded"
            ds = doc_start(r)
            if not ok or ds is None:
                cases.append(_case(f"{name} start", grade, cite, False,
                                   f"no start to compare (predicted {why}; doc starts {r['starts']})"))
                continue
            got, exact = ds
            hit = start == got if exact else start <= got
            cases.append(_case(f"{name} start", grade, cite, hit,
                               f"doc start +{got} ({'exact' if exact else 'upper bound'}), "
                               f"predicted +{start}"))
    cases += fixed_cases(chars)
    return cases


REGISTER = ("| Cancel windows | measured: one cancel frame per normal (B +13, side B +23, up B +24, "
            "down B +21, Y +21 into side/up Y, up Y +57 into air B/Y); nothing → B, jump, dash or guard.")
REGISTER_STARTS = {"B": ("ground", 13), "side B": ("ground", 23), "up B": ("ground", 24),
                   "down B": ("ground", 21), "Y": ("ground", 21), "up Y": ("air", 57)}
YUSUKE_277 = "**`side B` does not cancel into `up B`.**"
OWNER_NOTES = REPO / "docs" / "research" / "moveset-notes" / "OWNER-NOTES.md"
# (prefix, case, chain, first quoted line, last quoted line): cites are found by text.
KAK_2509 = "\"kakashi's b should cancel into his upB … B upB Y is a valid combo in JUS\""
OWNER = [
    ("na_b_04", "B -> up B", ["B", "up B"], KAK_2509, None),
    ("na_b_04", "B -> up B -> Y", ["B", "up B", "Y"], KAK_2509, None),
    ("na_b_04", "air B -> air Y", ["air B", "air Y"], "\"his air B cancels into his air Y as well\"", None),
    ("na_b_04", "up Y -> air B", ["up Y", "air B"], "up Y cancels into air B or", 'air Y." Context'),
    ("na_b_04", "up Y -> air Y", ["up Y", "air Y"], "up Y cancels into air B or", 'air Y." Context'),
    # Sasuke: "up B into X, up B into Y"; the Y half is checked here, X is a special cancel.
    ("na_b_02", "up B -> Y", ["up B", "Y"], "The second hit can be cancelled", "(up B into X, up B into Y)"),
]


def owner_cite(first: str, last: str | None) -> str:
    lines = OWNER_NOTES.read_text(encoding="utf-8").splitlines()
    a = next((n for n, l in enumerate(lines, 1) if first in l), None)
    b = next((n for n, l in enumerate(lines, 1) if last in l and n >= (a or 0)), None) if last else a
    rel = OWNER_NOTES.relative_to(REPO)
    if a is None or b is None:
        return f"{rel}:?? (quote not found: {first!r})"
    return f"{rel}:{a}" if a == b else f"{rel}:{a}-{b}"


def fixed_cases(chars: dict) -> list[dict]:
    cases = []
    kak = chars["na_b_04"]
    kdoc = DOCS["na_b_04"].read_text(encoding="utf-8")
    kline = next((n for n, l in enumerate(kdoc.splitlines(), 1) if l.startswith(REGISTER)), None)
    cite = f"docs/rebuild/characters/kakashi.md:{kline}"
    moves = {m["move"]: m for m in kak["moves"]}
    krows = doc_routes(DOCS["na_b_04"])
    for mv, (kind, want) in REGISTER_STARTS.items():
        got = (moves[mv]["cancel_start"] or {}).get(kind)
        same = [r for r in krows if r["src"] == mv and r["starts"]]
        grades = "/".join(sorted({g for r in same for g in r["start_grades"]})) or "ungraded"
        where = ", ".join(f":{r['line']}" for r in same)
        # §8 calls these starts measured; the route rows derive the same numbers
        # and grade them inferred. The gate keeps §8's label and names the split.
        cases.append(_case(f"na_b_04 {mv} cancel start (§8 register)", "measured", cite,
                           kline is not None and got == want,
                           f"register +{want} ({kind}), predicted {got}; §8 grades it measured, "
                           f"the cancel-routes route rows grade it {grades} (kakashi.md{where})"
                           + ("" if kline else "; register row text not found")))
    ground_into_b = [m["move"] for m in kak["moves"][:8] if "B" in m["followups"]]
    cases.append(_case("na_b_04 nothing cancels into B on the ground", "measured", cite,
                       kline is not None and not ground_into_b,
                       f"moves offering B: {ground_into_b or 'none'}"))
    facts = code_facts()
    offered = sorted(set(facts["ground_returns"]) | set(facts["air_returns"]))
    extra = [v for v in offered if v and v not in MOVE_IDS]
    cases.append(_case("na_b_04 no cancel into jump, dash or guard", "measured", cite,
                       kline is not None and not extra,
                       (f"the state-9 readers return only move ids {offered}" if not extra
                        else f"readers return non-move values {extra}")
                       + "; limit: this checks only what the readers return, not a jump, dash "
                         "or guard press inside a window"))
    ydoc = DOCS["yh_b_01"].read_text(encoding="utf-8")
    yline = next((n for n, l in enumerate(ydoc.splitlines(), 1) if YUSUKE_277 in l), None)
    ok, why, _ = route(chars["yh_b_01"], [IDS["side B"], IDS["up B"]])
    cases.append(_case("yh_b_01 side B -> up B dropped (prose)", "measured",
                       f"docs/rebuild/characters/yusuke.md:{yline}", yline is not None and not ok,
                       f"predicted {why}"))
    for prefix, name, chain, first, last in OWNER:
        ok, why, start = route(chars[prefix], [IDS[x] for x in chain])
        oc = owner_cite(first, last)
        found = "quote not found" not in oc
        cases.append(_case(f"{prefix} {name}", "owner", oc, ok and found,
                           f"predicted {why}" + (f" from +{start}" if ok else "")
                           + ("" if found else "; the owner quote is missing from OWNER-NOTES.md")))
        if prefix != "na_b_04" or len(chain) < 3:
            continue
        # The last hop of a chain: its start must be the doc's start for that
        # first move and window kind (a route row with an exact start).
        src, kind = chain[-2], kind_of(chain[-1])
        rows = [(r, doc_start(r)) for r in krows if r["src"] == src and kind_of(r["dst"]) == kind
                and doc_start(r) and doc_start(r)[1]]
        want = rows[0] if rows else None
        cases.append(_case(
            f"na_b_04 {name} chain start", "/".join(want[0]["start_grades"]) if want else "ungraded",
            f"docs/rebuild/characters/kakashi.md:{want[0]['line']}" if want else cite,
            bool(ok and want and start == want[1][0]),
            (f"last hop {src} -> {chain[-1]}: doc start +{want[1][0]} (exact, `{src}` -> "
             f"`{want[0]['dst']}`), predicted +{start}") if want else "no exact doc start for the last hop"))
    return cases


# ------------------------------------------------------------------ cli

def dump(table: dict) -> str:
    """Indented, but each move row on one line so the file stays small."""
    rows = {}

    def mark(obj):
        if isinstance(obj, dict) and "grades" in obj:
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


SCHEMA = OUT.with_suffix(".md")


def schema_doc(text: str) -> str:
    """Regenerate the special-cancel field row without rewriting authored prose."""
    row = ('| `special_cancel` | ids 1-10 with a ground key: '
           '`{"into": ["X", "up X"], "start": {"ground": n}, "gate": "...", "terminal": true}`. '
           '`start` is the ground `cancel_start`. Initial air slots 9-10 can have ground windows. '
           '`null` for a move with no ground key (air-key-only, no key, key at the anim\'s end) '
           'and for ids 11-14 | `grades.special_cancel` (measured only where '
           '`cites.special_cancel` is set: Yusuke B, Y, side Y, up Y) |')
    result, count = re.subn(r"^\| `special_cancel` \|[^\n]*", lambda _: row, text, flags=re.M)
    if count != 1:
        raise ValueError(f"expected one special_cancel schema row, found {count}")
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="write cancel-table.json and the Markdown special_cancel field row")
    sub.add_parser("check", help="the gate: committed JSON/schema row are fresh and every doc case passes")
    s = sub.add_parser("show", help="print one character's rows")
    s.add_argument("prefix")
    a = ap.parse_args(argv)
    table = build()
    if a.cmd == "build":
        schema = schema_doc(SCHEMA.read_text(encoding="utf-8"))
        OUT.write_text(dump(table), encoding="utf-8")
        SCHEMA.write_text(schema, encoding="utf-8")
        print(f"wrote {OUT.relative_to(REPO)}")
        print(f"updated special_cancel row in {SCHEMA.relative_to(REPO)}")
        return 0
    if a.cmd == "show":
        char = next(c for c in table["characters"] if c["prefix"] == a.prefix)
        print(a.prefix, ", ".join(f"{n['name']} (chr_b {n['chr_b']})" for n in char["names"]) or "(no name)")
        for m in char["moves"]:
            print(f"  {m['id']:>2} {m['move']:<24} anim {m['anim']} key {m['key']} start {m['cancel_start']} "
                  f"mask {m['mask']} -> {m['followups']}" + (f"  [{m['reason']}]" if m["reason"] else ""))
        return 0
    try:
        cases = gate(table)
    except FileNotFoundError as e:
        fresh = OUT.exists() and OUT.read_text(encoding="utf-8") == dump(table)
        print(f"gate skipped: needs an input that is not part of this repository ({e.filename})")
        print(f"committed JSON {'is fresh' if fresh else 'is STALE: run build'}")
        return 0 if fresh else 1
    fresh = OUT.exists() and OUT.read_text(encoding="utf-8") == dump(table)
    schema = SCHEMA.read_text(encoding="utf-8")
    schema_fresh = schema == schema_doc(schema)
    for c in cases:
        print(f"{'PASS' if c['pass'] else 'MISS'}  [{c['grade']}] {c['case']}: {c['detail']}  ({c['cite']})")
    miss = [c for c in cases if not c["pass"]]
    print(f"{len(cases) - len(miss)}/{len(cases)} cases pass; committed JSON "
          f"{'is fresh' if fresh else 'is STALE: run build'}")
    print(f"committed schema row {'is fresh' if schema_fresh else 'is STALE: run build'}")
    return 0 if fresh and schema_fresh and not miss else 1


def _mem_imm(w: int) -> tuple[bool, int, int, int] | None:
    """ARM immediate-offset load/store at word w -> (load, size, rn, imm); size 4 word,
    1 byte, 2 halfword, 8 doubleword. None for anything else (register offsets included)."""
    if (w >> 28) == 0xF:
        return None
    if (w & 0x0E000000) == 0x04000000:                       # LDR/STR/LDRB/STRB #imm12
        return bool(w >> 20 & 1), 1 if w >> 22 & 1 else 4, w >> 16 & 0xF, w & 0xFFF
    if (w & 0x0E400090) == 0x00400090 and w >> 5 & 3:          # LDRH/STRH/LDRSB/LDRSH/LDRD/STRD #imm8
        load, sh = bool(w >> 20 & 1), w >> 5 & 3
        size = 2 if sh == 1 or sh == 3 and load else 1 if load else 8
        return load, size, w >> 16 & 0xF, (w >> 4 & 0xF0) | (w & 0xF)
    return None


def _touches(w: int, lo: int, hi: int, store: bool | None = None) -> bool:
    m = _mem_imm(w)
    return bool(m) and (store is None or m[0] != store) and m[3] < hi and m[3] + m[1] > lo


def dream_entry_facts() -> dict:
    """The two ways move id 12 starts, and what each does to C4 (PF-31o).
      c4_stores   every ARM immediate store in ov6 that reaches fighter+0xC4..+0xC7
      neutral_*   0x02159D7C (a neutral reader's id): C4 = 0 (0x02159DB8), C4 |= mask[id]
                  (0x02159E1C-20), and for id 12 C4 |= ~0 (0x02159E68-84), with the active
                  koma +0x1CC copied to the snapshot +0x1D0 (0x02159E88-90)
      fire_path   system_jump[1], state 9's fire case for a latched 12 (0x0215A590 up to the
                  common 0x0215A618): no access to +0xC4; it compares +0x1CC with +0x1D0 and
                  starts 12 when they differ, else X (13) or up X (14, +0x6C bit 0) for a bar
      restart     the fire tail stores the id to +0xCA and clears +0x14, so the same handler
                  (0x02159EF8) re-initialises the new move next tick; reader_gates lists any
                  load of the move id (+0xCA, +0xCB) or the state byte +0x18 on the path from the
                  per-frame entry to the window test (0x0215A148-0x0215A4D0); the only one is a
                  counter index whose two branches rejoin, so the reader runs for every move id
    """
    buf, base = ov6()
    stores = [base + o for o in range(0, len(buf) - 3, 4)
              if _touches(struct.unpack_from("<I", buf, o)[0], 0xC4, 0xC8, store=True)]

    def is_(addr: int, mask: int, want: int) -> bool:
        return word(addr) & mask == want

    def ldr(addr: int, rd: int, rn: int, imm: int) -> bool:
        return word(addr) & 0x0FFFFFFF == 0x05900000 | rn << 16 | rd << 12 | imm

    def str_(addr: int, rd: int, rn: int, imm: int) -> bool:
        return word(addr) & 0x0FFFFFFF == 0x05800000 | rn << 16 | rd << 12 | imm

    lo, hi = system_jump = branch_target(0x0215A500), 0x0215A618
    fire = range(lo, hi, 4)
    fire_ids = sorted({_imm(word(a)) for a in fire if is_(a, 0x0FFFF000, 0x03A04000)})
    return {
        "c4_stores": stores,
        "neutral_reset": is_(0x02159DB4, 0x0FFFFFFF, 0x03A00000) and str_(0x02159DB8, 0, 6, 0xC4),
        "neutral_or_mask": ldr(0x02159E10, 1, 6, 0xC4) and is_(0x02159E1C, 0x0FFFFFFF, 0x01810000)
                           and str_(0x02159E20, 0, 6, 0xC4),
        "neutral_dream_all_ones": _imm(word(0x02159E68)) == 12 and is_(0x02159E68, 0x0FFFF000, 0x03540000)
                                  and is_(0x02159E74, 0xF0000000, 0x10000000)       # bne past it
                                  and is_(0x02159E7C, 0x0FFFFFFF, 0x03E00000)       # mvn r0,#0
                                  and str_(0x02159E84, 0, 6, 0xC4),
        "neutral_snapshot": (_mem_imm(word(0x02159E88))[3], _mem_imm(word(0x02159E90))[3])
                            if ldr(0x02159E88, 0, 6, 0x1CC) and str_(0x02159E90, 0, 6, 0x1D0) else None,
        "fire_path": system_jump,
        "fire_path_c4_access": [a for a in fire if _touches(word(a), 0xC4, 0xC8)],
        "fire_compare": (0x1CC, 0x1D0) if ldr(0x0215A5B4, 1, 6, 0x1CC) and ldr(0x0215A5B8, 0, 6, 0x1D0)
                        and is_(0x0215A5C0, 0x0FFFFFFF, 0x01510000) else None,
        "fire_ids": fire_ids,
        "restart": (0xCA, 0x14) if is_(0x0215A62C, 0x0FFFFFFF, 0x05C640CA)
                   and _mem_imm(word(0x0215A634))[:4] == (False, 2, 6, 0x14) else None,
        "reader_gates": [a for a in range(0x0215A148, 0x0215A4D0, 4)
                         if (m := _mem_imm(word(a))) and m[0] and m[2] == 6
                         and (m[3] in (0xCA, 0xCB) or m[3] <= 0x18 < m[3] + m[1])],
        # The one id load there (+0xCB at 0x0215A390) indexes misc byte 2 for a counter call;
        # its skip (beq at 0x0215A3AC) and the call (0x0215A3B0) both reach 0x0215A3B8.
        "misc_counter_rejoins": branch_target(0x0215A3AC) == 0x0215A3B8
                                and branch_target(0x0215A3B4) == 0x0215A660
                                and word(0x0215A3B4) >> 24 & 0xF == 0xB,
    }


def unnested_offers() -> list[tuple[int, int]]:
    """(m, t) where a window of move m offers t but mask[t] lacks a bit of mask[m]. Empty
    means a chain entered through the readers ends with C4 = its last move's own mask."""
    t = move_table()
    out = []
    for m in NORMAL_IDS:
        for kind in ("ground", "air"):
            for n in followups(t[m]["mask"], kind):
                if t[m]["mask"] & ~t[n]["mask"]:
                    out.append((m, n))
    return out


def dream_offers(c4: int | None) -> tuple[list[str], bool]:
    """(normal follow-ups, X/up X offered) of the dream attack's ground window. None is a
    neutral start, whose C4 is all ones; an int is the C4 a cancel entry leaves in place.
    Assumes C0 clear, as `followups` does."""
    c4 = 0xFFFFFFFF if c4 is None else c4
    return ([NAMES[t] for t in followups(c4, "ground")],
            not any(c4 >> i & 1 for i in SPECIAL_IDS))


if __name__ == "__main__":
    raise SystemExit(main())
