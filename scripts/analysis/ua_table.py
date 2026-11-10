#!/usr/bin/env python3
"""Static Ultimate Action table (SELECT, move id 11, anim 0x18) for every battle character.
No emulator. Schema and cast summary: docs/rebuild/ua-table.md. Output: docs/rebuild/ua-table.json.

Reuses mash_table.py for the NoteTrack walk (node_events), the op 0 decoders (decode_event,
KINDS, move_label, guide_entries, GUIDE_FILES) and the code facts the mash decode rests on.
What is new here is the op 1 sub 3 impulse, the op 3 argument table, the spawn rows, and the
cast-wide store (sub 19) and stored-jump (sub 20) rows for every anim of every prefix.

The chain, all static:

  Trigger. The ground move reader (0x0215A720 slot 0) tests the SELECT edge 0x1000 at 0x0215A7D0
      and returns move id 11 = anim 0x18, state 0x0C (move table 0x021712B8 + 12*11). The air
      reader 0x0215A8C0 returns only ids 9 and 10, so SELECT in the air is not the UA.
  Team register. The controller byte ctrl+0xA3 is written by sub 19 (0x021560EC, `strb r1,[r0,#0xa3]`)
      and read and cleared by sub 20 (0x021560F8). The ctor sets it to -1 (0x0215542C). Only ov6
      writes it, and the switch does not clear it (review.md b3, b4), so it is a per-team register.
  Op 3 arguments. The handler (0x021568E8) passes arg = ev[2] and the s16 at ev[4..5] to the
      callback; the case table at 0x02157A68 + 4*arg is a branch per arg (review.md §3.5, uare2 §3):
        2 spawn (ev[4] = shot row index, shot file chr/shot/<prefix>.bin, 32-byte rows, art u32 at +12)
        7 invuln (+0xCE = s16 ticks)
        9 arm_substitute (decoy index = signed ev[4], -1 skipped; arm timer 121 ticks, 0x0215A980)
        10 status (u16 ev[4..5] indexes the byte table 0x0217215C, giving the status id; 0x02157C5C)
        17, 18 kept raw, grade lead (semantics not traced here)
        23 hp (amount_raw = s16 ev[4..5]; HP raw = displayed HP x 64)
        24 sp (amount_raw = s16 ev[4..5]; SP raw 25600 = one bar)
      Any other arg is kept raw with grade lead.
  Op 1 sub 3 impulse. x = ev[2] * 32 (facing-signed, +0x2C), y = ev[3] * -126 (`mvn r0,#0x7d`,
      +0x2E) from the op 1 table 0x02172020[3] = 0x0215669C. Element accel pair 0 (review.md f1).
  Op 3 sub 1 end key. Sets ctrl+0x90 |= 0x10000000 (0x0215693C); listed as `ends`, not an effect.
  Stores and jumps. Every sub 19 and sub 20 in every anim of the prefix (any member), with
      `targets` = {marker id: frame} for every Marker of that anim (the join to a stored value
      is the consumers column of ua-table.md).

Usage:
    python3 scripts/analysis/ua_table.py build   # write the .json and .md
    python3 scripts/analysis/ua_table.py check   # exit 0 = committed files are fresh
    python3 scripts/analysis/ua_table.py show bc_b_02
"""
from __future__ import annotations

import argparse
import functools
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import mash_table as M  # noqa: E402
import knockback_table as K  # noqa: E402

C = M.C
REPO = M.REPO
OUT = REPO / "docs" / "rebuild" / "ua-table.json"
OUT_MD = REPO / "docs" / "rebuild" / "ua-table.md"

UA_ANIM = 0x18
UA_MOVE_ID = 11
MOVE_TABLE = 0x021712B8                     # 12-byte rows: anim, mask, misc
GROUND_READER_TEST = 0x0215A7D0             # tst r0,#0x1000 (SELECT)
AIR_READER = (0x0215A8C0, 0x0215A8F8)       # returns ids 9 / 10 only
OP1_TABLE = 0x02172020
OP1_IMPULSE_SUB = 3
OP1_IMPULSE_MVN = 0x021566F4                # mvn r0,#0x7d = -126
IMPULSE_X_SHIFT = 5                         # x = ev[2] << 5 = ev[2] * 32
IMPULSE_Y_MUL = -126
OP3_CASE_TABLE = 0x02157A68                 # b per arg (arg index * 4)
OP3_CASES = {2: 0x02157BB0, 7: 0x02157C30, 9: 0x02157C4C, 10: 0x02157C5C, 17: 0x02157D2C,
             18: 0x02157D38, 23: 0x02157DB8, 24: 0x02157DC8}
# Case 10 (0x02157C5C): `ldrb r1,[0x0217215C + (u16)operand]`, then 0x02158ED0(self, r1). The 26
# bytes are read from arm9_ov06.bin (file offset 0x0217215C - 0x0214CD20) and pinned in code_facts.
OP3_STATUS_TABLE_ADDR = 0x0217215C
OP3_STATUS_TABLE = bytes.fromhex("0102030405060708090a0b0c0d0e0f1011" "2324252627282918" "21")
OP3_END_SUB = M.END_KEY_SUB                 # op 3 sub 1 = end key (sub byte, not arg)
STORE_SITE = 0x021560EC                     # sub 19 handler (ldrsb value at ev[2])
STORED_JUMP_SITE = 0x021560F8               # sub 20 handler (reads ctrl+0xA3)
INIT_SITE = 0x0215542C                      # ctor: strb r0,[r4,#0xa3] (-1)
STORE_OFFSET = 0xA3
HP_RAW_PER_POINT = 64                       # HP-Struct-From-Disassembly.md:136
SP_RAW_PER_BAR = 25600                      # guard-sp.md:914
SHOT_DIR = Path("jus_files") / "chrbin" / "chr" / "shot"
SHOT_ROW_BYTES = 32
SHOT_ART_OFFSET = 12

FIELD_GRADES = {
    "frame": "measured", "raw": "measured", "member": "measured", "anim": "measured",
    "frames": "measured", "markers": "measured", "ends": "measured", "targets": "measured",
    "value": "measured", "amount_raw": "measured", "decoy": "measured", "ticks": "measured",
    "row": "measured", "x_ev": "measured", "y_ev": "measured",
    "x_raw": "inferred (ev[2] * 32; the shift is read from the handler, review.md f1)",
    "y_raw": "inferred (ev[3] * -126; the multiplier is read from mvn r0,#0x7d at 0x021566F4)",
    "units": "inferred (HP raw / 64 per displayed HP; SP raw / 25600 per bar, uare2-findings §3)",
    "kind": "inferred (the name of each op 3 arg, from the handler it calls)",
    "art": "measured (u32 at byte 12 of the shot row, chr/shot/<prefix>.bin)",
    "has_kb_record": "inferred: kb_recs is non-empty (the art low byte = anim id join, review c4; see grade_notes.spawn)",
    "kb_recs": "inferred: the knockback records whose collision track keys an anim equal to the art low byte (review c4)",
    "grade": "measured for decoded args; lead for every other op 3 arg",
    "effect_class": "inferred (a summary of the kinds in the row)",
    "guide_check": "measured join: the GameFAQs select tag against the anim 0x18 rows of the mapped prefixes",
}

GRADE_NOTES = {
    "trigger": "measured: SELECT edge 0x1000 at 0x0215A7D0 (tst r0,#0x1000) returns move id 11 "
               "(anim 0x18, state 0x0C, no SP gate); the air reader returns only ids 9 and 10",
    "store": "measured bytes: sub 19 writes ev[2] (signed) to the team register ctrl+0xA3 (0x021560EC); "
             "the register is -1 at init (0x0215542C) and survives switches and hits (review.md b3-b5)",
    "stored_jump": "measured bytes: sub 20 reads ctrl+0xA3; if it is not -1 it queues a jump to that Marker "
                   "and resets it to -1 (0x021560F8). `targets` lists every Marker of the anim",
    "spawn": "measured bytes: the shot row (ev[4]) and its art (u32 at byte 12). kb join inferred: the art's "
             "low byte is an anim id, and kb_recs lists each knockback record whose collision track keys that "
             "anim (K.record_uses; review c4). Inferred, not proven, and it can be ambiguous: several records "
             "can match (ds_b_01 -> [11, 15]). has_kb_record is null only when the row is not in the file",
    "invuln": "measured: arg 7 stores s16 ev[4..5] to +0xCE (0x02157C30)",
    "arm_substitute": "measured: arg 9 stores the decoy index (signed ev[4]) and arms the substitution "
                      "(0x02157C4C -> 0x0215C034); behaviour is in uare2-findings §1",
    "status": "inferred (static only): arg 10 maps its u16 operand ev[4..5] through the byte table at 0x0217215C "
              "(26 bytes, pinned in code_facts) and calls 0x02158ED0(self, id) (0x02157C5C); the status lands on "
              "the acting fighter. No capture of the landing",
    "hp": "measured: arg 23 applies s16 ev[4..5] to the active koma's HP (0x02157DB8 -> 0x020783CC)",
    "sp": "measured: arg 24 applies s16 ev[4..5] to the team SP pool (0x02157DC8 -> 0x020781E4)",
    "lead": "args 17 and 18 and any other op 3 arg: bytes measured, semantics not traced",
    "impulse": "measured bytes: op 1 sub 3 (table 0x02172020[3] = 0x0215669C); x = ev[2] * 32 and "
               "y = ev[3] * -126 are the handler's arithmetic, read statically",
    "ends": "measured: op 3 sub 1 key frames (0x0215693C)",
    "guide": "measured join: each GameFAQs select tag maps to the prefixes of mash_table.GUIDE_FILES",
}

# ------------------------------------------------------------------ code facts


def s8(raw: bytes, off: int) -> int:
    return struct.unpack_from("<b", raw, off)[0]


def s16(raw: bytes, off: int) -> int:
    return struct.unpack_from("<h", raw, off)[0]


def air_reader_returns() -> set[int]:
    """Ids the air reader returns: the imm of each `movne r0,#imm` (0x13A00000 | imm) in its range."""
    lo, hi = AIR_READER
    out = set()
    for a in range(lo, hi, 4):
        w = C.word(a)
        if (w & 0xFFFFF000) == 0x13A00000:
            out.add(w & 0xFF)
    return out


def code_facts() -> dict:
    """The code facts the UA decode rests on, read from ov06.bin; each one raises if it moved."""
    mash = M.code_facts()
    cases = {}
    for arg, want in OP3_CASES.items():
        got = C.branch_target(OP3_CASE_TABLE + 4 * arg)
        if got != want:
            raise ValueError(f"op 3 arg {arg}: case at 0x{OP3_CASE_TABLE + 4 * arg:08X} branches to "
                             f"0x{got:08X}, expected 0x{want:08X}")
        cases[str(arg)] = f"0x{got:08X}"
    blob, base = C.ov6()
    off = OP3_STATUS_TABLE_ADDR - base
    if blob[off:off + len(OP3_STATUS_TABLE)] != OP3_STATUS_TABLE:
        raise ValueError(f"the op 3 arg 10 byte table at 0x{OP3_STATUS_TABLE_ADDR:08X} moved")
    op1 = C.word(OP1_TABLE + 4 * OP1_IMPULSE_SUB)
    if op1 != 0x0215669C:
        raise ValueError(f"op 1 sub 3 handler is 0x{op1:08X}")
    if C.word(OP1_IMPULSE_MVN) != 0xE3E0007D:
        raise ValueError(f"0x{OP1_IMPULSE_MVN:08X} is not mvn r0,#0x7d")
    if C.word(GROUND_READER_TEST) != 0xE3100A01:
        raise ValueError(f"0x{GROUND_READER_TEST:08X} is not tst r0,#0x1000")
    returns = sorted(air_reader_returns())
    if returns != [9, 10]:
        raise ValueError(f"air reader returns {returns}")
    if C.word(STORE_SITE) != 0xE1D110D2 or C.word(STORE_SITE + 4) != 0xE5C010A3:
        raise ValueError("sub 19 is not ldrsb r1,[r1,#2] / strb r1,[r0,#0xa3]")
    if C.word(INIT_SITE) != 0xE5C400A3:
        raise ValueError(f"0x{INIT_SITE:08X} is not strb r0,[r4,#0xa3]")
    return {
        "mash": mash,
        "move_id": UA_MOVE_ID,
        "move_row": f"0x{MOVE_TABLE + 12 * UA_MOVE_ID:08X}",
        "ground_reader_test": f"0x{GROUND_READER_TEST:08X}",
        "air_reader_returns": returns,
        "op1_impulse": f"0x{op1:08X}",
        "op1_impulse_mvn": f"0x{OP1_IMPULSE_MVN:08X}",
        "op3_cases": cases,
        "store_site": f"0x{STORE_SITE:08X}",
        "stored_jump_site": f"0x{STORED_JUMP_SITE:08X}",
        "init_site": f"0x{INIT_SITE:08X}",
        "store_offset": STORE_OFFSET,
        "end_key": {"op": 3, "sub": OP3_END_SUB, "handler": "0x0215693C"},
        "hp_raw_per_point": HP_RAW_PER_POINT,
        "sp_raw_per_bar": SP_RAW_PER_BAR,
    }


# ------------------------------------------------------------------ decoders (bytes only)


def decode_op3(raw: bytes) -> dict:
    """One op 3 sub 0 event: ev[2] is the arg, ev[4..5] the payload the handler reads."""
    raw = bytes(raw).ljust(6, b"\0")
    arg = raw[2]
    row = {"arg": arg, "raw": raw[:6].hex(" ")}
    if arg == 2:
        row.update(kind="spawn", row=raw[4], grade="measured")
    elif arg == 7:
        row.update(kind="invuln", ticks=s16(raw, 4), grade="measured")
    elif arg == 9:
        row.update(kind="arm_substitute", decoy=s8(raw, 4), grade="measured")
    elif arg == 10 and struct.unpack_from("<H", raw, 4)[0] < len(OP3_STATUS_TABLE):
        operand = struct.unpack_from("<H", raw, 4)[0]
        row.update(kind="status", operand=operand, status_id=OP3_STATUS_TABLE[operand], grade="inferred")
    elif arg == 23:
        row.update(kind="hp", amount_raw=s16(raw, 4), units="HP points = amount_raw / 64", grade="measured")
    elif arg == 24:
        row.update(kind="sp", amount_raw=s16(raw, 4), units="bars = amount_raw / 25600", grade="measured")
    else:
        row.update(kind=f"op3_arg{arg}", grade="lead")
    return row


def decode_impulse(raw: bytes) -> dict:
    """One op 1 sub 3 event: x = ev[2] * 32 (facing-signed at use), y = ev[3] * -126."""
    raw = bytes(raw).ljust(4, b"\0")
    x_ev, y_ev = s8(raw, 2), s8(raw, 3)
    return {"x_ev": x_ev, "y_ev": y_ev, "x_raw": x_ev << IMPULSE_X_SHIFT, "y_raw": y_ev * IMPULSE_Y_MUL,
            "raw": raw[:4].hex(" ")}


def resolve_targets(markers: dict[int, int]) -> dict[str, int]:
    """Every Marker of an anim as {marker id: frame}; the stored value picks one of them."""
    return {str(k): v for k, v in sorted(markers.items())}


# ------------------------------------------------------------------ scan


def anim_scan(prefix: str) -> list[dict]:
    """Every SP01 animation of every member of a prefix (base koma first), with its events:
    [{member, anim, frames, markers, events: [{frame, sub, op, raw, note, event}], ends}]."""
    out = []
    for member, almt in M.mr.motions(prefix):
        native = M.E.anim_events(almt)
        for _idx, full in almt.full_animations():
            top = full["nodes"][0]
            if top["entry"] is None:
                continue
            aid, frames = top["entry"]["id"], top["entry"]["frames"]
            for node in full["nodes"]:
                if node["name"] != "SP01" or node["start"] is None:
                    continue
                markers, _keys = M.node_events(almt, node)
                events = []
                for ni, key in enumerate(native[aid]["notes"]):
                    for ei, event in enumerate(key["events"]):
                        raw = bytes.fromhex(event["raw"])
                        events.append({"frame": key["frame"], "sub": event["sub"],
                                       "op": event["op"], "raw": raw, "note": ni, "event": ei})
                ends = sorted({e["frame"] for e in events if e["op"] == 3 and e["sub"] == OP3_END_SUB})
                out.append({"member": member, "anim": aid, "frames": frames, "markers": markers,
                            "events": events, "ends": ends})
    return out


def shot_rows(prefix: str) -> list[dict]:
    """chr/shot/<prefix>.bin as 32-byte rows: shot kind (byte 0) and art id (u32 at byte 12)."""
    path = M.mr.ROOT / SHOT_DIR / f"{prefix}.bin"
    if not path.exists():
        return []
    raw = path.read_bytes()
    rows = []
    for i in range(len(raw) // SHOT_ROW_BYTES):
        r = raw[i * SHOT_ROW_BYTES:(i + 1) * SHOT_ROW_BYTES]
        rows.append({"index": i, "shot_kind": r[0],
                     "art": f"0x{struct.unpack_from('<I', r, SHOT_ART_OFFSET)[0]:08x}"})
    return rows


@functools.lru_cache(maxsize=None)
def _kb_refs(prefix: str) -> dict:
    _f, refs = K.record_uses(prefix)
    return refs


def kb_recs_for_art(prefix: str, art: int) -> list[int]:
    """Knockback records keyed to the anim whose id is the art's low byte (inferred join, review c4).
    record_uses' strings are "member 0x<anim>[ node]", so split()[1] is the anim."""
    want = f"0x{art & 0xFF:02x}"
    return sorted(rec for rec, uses in _kb_refs(prefix).items()
                  if any(u.split()[1] == want for u in uses))


def ua_row(sc: dict, facts: dict, shots: list[dict], prefix: str) -> dict:
    """The anim 0x18 row: frames, ends, playhead events, effects, impulses and spawn rows."""
    markers = sc["markers"]
    row = {"member": sc["member"], "anim": f"0x{sc['anim']:02x}", "frames": sc["frames"],
           "markers": resolve_targets(markers), "ends": sc["ends"],
           "playhead": [], "effects": [], "impulses": [], "spawns": []}
    for ev in sorted(sc["events"], key=lambda e: (e["frame"], e["sub"], e["op"])):
        sub, op, raw, frame = ev["sub"], ev["op"], ev["raw"], ev["frame"]
        if op == 0 and sub in M.KINDS:
            d = M.decode_event(sub, raw[:M.RAW_LEN[sub]], facts["mash"], markers)
            d["frame"] = frame
            row["playhead"].append(d)
        elif op == 3 and sub == 0:
            d = decode_op3(raw)
            d["frame"] = frame
            if d["kind"] == "spawn":
                shot = shots[d["row"]] if d["row"] < len(shots) else None
                art = int(shot["art"], 16) if shot else None
                kb_recs = None if art is None else kb_recs_for_art(prefix, art)
                row["spawns"].append({"frame": frame, "row": d["row"], "raw": d["raw"],
                                      "art": shot["art"] if shot else None,
                                      "in_file": shot is not None,
                                      "has_kb_record": None if kb_recs is None else bool(kb_recs),
                                      "kb_recs": kb_recs,
                                      "grade": "measured bytes; kb join inferred (art low byte = anim id "
                                               "keyed to the record's collision id, review c4)"})
            else:
                row["effects"].append(d)
        elif op == 3 and sub != OP3_END_SUB:
            row["effects"].append({"frame": frame, "kind": f"op3_sub{sub}", "raw": raw[:6].hex(" "),
                                   "grade": "lead"})
        elif op == 1 and sub == OP1_IMPULSE_SUB:
            d = decode_impulse(raw)
            d["frame"] = frame
            row["impulses"].append(d)
    return row


def stored_rows(sc: dict, prefix: str, table: dict, facts: dict) -> tuple[list[dict], list[dict]]:
    """(sub 19 rows, sub 20 rows) of one anim member."""
    stores, jumps = [], []
    move, move_id = M.move_label(sc["anim"], table)
    for ev in sc["events"]:
        if ev["op"] != 0 or ev["sub"] not in (19, 20):
            continue
        d = M.decode_event(ev["sub"], ev["raw"][:M.RAW_LEN[ev["sub"]]], facts["mash"], sc["markers"])
        d.update(frame=ev["frame"], anim=f"0x{sc['anim']:02x}", member=sc["member"],
                 move=move, move_id=move_id, prefix=prefix)
        (stores if ev["sub"] == 19 else jumps).append(d)
    return stores, jumps


def status_rows(sc: dict) -> list[dict]:
    """Every op 3 arg 10 (self status) event of one anim member, on any anim: the writer
    selects them by a move's resolved anim and member. `scanned` lists (space-joined, hex ids) the anims the member
    holds, so a koma member without the anim can fall back to the base member."""
    rows = []
    for ev in sc["events"]:
        if ev["op"] != 3 or ev["sub"] != 0 or ev["raw"][2] != 10:
            continue
        d = decode_op3(ev["raw"])
        if d["kind"] != "status":
            continue
        rows.append({"member": sc["member"], "anim": f"0x{sc['anim']:02x}", "frame": ev["frame"],
                     "operand": d["operand"], "status_id": d["status_id"], "raw": d["raw"]})
    return rows


def build_char(prefix: str, facts: dict, table: dict) -> dict:
    out = {"prefix": prefix, "names": M.names_for(prefix), "ua": None, "stores": [],
           "stored_jumps": [], "status_effects": [], "scanned": {}, "error": None}
    try:
        scans = anim_scan(prefix)
        shots = shot_rows(prefix)
    except BaseException as ex:  # SystemExit from the loaders, struct errors
        out["error"] = f"{type(ex).__name__}: {ex}"
        return out
    for sc in sorted(scans, key=lambda s: (s["anim"], s["member"])):
        stores, jumps = stored_rows(sc, prefix, table, facts)
        out["stores"] += stores
        out["stored_jumps"] += jumps
        out["scanned"].setdefault(sc["member"], []).append(f"0x{sc['anim']:02x}")
        out["status_effects"] += status_rows(sc)
    ua_scans = [s for s in scans if s["anim"] == UA_ANIM]
    if ua_scans:
        out["ua"] = ua_row(ua_scans[0], facts, shots, prefix)
    out["status_effects"].sort(key=lambda r: (r["member"], r["anim"], r["frame"]))
    for member, anims in out["scanned"].items():
        out["scanned"][member] = " ".join(sorted(set(anims)))
    out["stores"].sort(key=lambda r: (r["anim"], r["member"], r["frame"]))
    out["stored_jumps"].sort(key=lambda r: (r["anim"], r["member"], r["frame"]))
    return out


def effect_class(ua: dict | None) -> str:
    if ua is None:
        return "no anim 0x18"
    kinds = {e["kind"] for e in ua["playhead"]}
    kinds |= {e["kind"] for e in ua["effects"]}
    if ua["impulses"]:
        kinds.add("impulse")
    if ua["spawns"]:
        kinds.add("spawn")
    if ua["ends"]:
        kinds.add("end_key")
    return ", ".join(sorted(kinds)) or "none"


def guide_select_entries() -> list[dict]:
    """Every GameFAQs move tagged input "select" (the Ultimate Action), sorted. Unlike
    mash_table.guide_entries() this does not need the mash-extend tag."""
    out = []

    def walk(o, stem, who):
        if isinstance(o, dict):
            if o.get("input") == "select":
                out.append({"file": stem, "character": who, "input": "select", "name": o.get("name")})
            for v in o.values():
                walk(v, stem, who)
        elif isinstance(o, list):
            for v in o:
                walk(v, stem, who)

    for path in sorted(M.GUIDE_DIR.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        walk(doc, path.name.split("--")[0], doc.get("character"))
    return sorted(out, key=lambda r: (r["file"], r["name"] or "", r["character"] or ""))


def guide_check(chars: list[dict]) -> list[dict]:
    """Each GameFAQs select tag joined to the anim 0x18 rows of its prefixes (mash_table.GUIDE_FILES):
    ua_effects (an effect, spawn, impulse, store or consume), playhead_only (loop, hold, wait or
    mash events only), no_events, unmapped."""
    by_prefix = {c["prefix"]: c for c in chars}
    rows = []
    for g in guide_select_entries():
        row = dict(g)
        if g["file"] in M.GUIDE_UNMAPPED:
            row.update(status="unmapped", prefixes=[], note=M.GUIDE_UNMAPPED[g["file"]])
        elif g["file"] not in M.GUIDE_FILES:
            row.update(status="unmapped", prefixes=[], note="no prefix mapping in mash_table.GUIDE_FILES")
        else:
            prefixes = M.GUIDE_FILES[g["file"]]
            status = "no_events"
            for p in prefixes:
                ua = by_prefix[p]["ua"]
                if ua is None:
                    continue
                if ua["effects"] or ua["spawns"] or ua["impulses"] or \
                        any(e["kind"] in ("store", "stored_jump") for e in ua["playhead"]):
                    status = "ua_effects"
                    break
                if ua["playhead"]:
                    status = "playhead_only"
            row.update(prefixes=prefixes, status=status)
        rows.append(row)
    return rows


def build() -> dict:
    facts = code_facts()
    table = C.move_table()
    chars = [build_char(p, facts, table) for p in C.battle_prefixes()]
    guide = guide_check(chars)
    return {
        "_schema": "docs/rebuild/ua-table.md",
        "_generated_by": "python3 scripts/analysis/ua_table.py build",
        "field_grades": FIELD_GRADES,
        "grade_notes": GRADE_NOTES,
        "code_facts": facts,
        "counts": counts(chars),
        "guide_check": guide,
        "characters": chars,
    }


def counts(chars: list[dict]) -> dict:
    """Cast-wide event counts: events, anims and characters carrying them."""
    def over(rows_of):
        ev = [(c["prefix"], e) for c in chars for e in rows_of(c)]
        return {"events": len(ev), "anims": len({(p, e.get("anim"), e.get("member")) for p, e in ev}),
                "characters": len({p for p, _ in ev})}
    uas = [c["ua"] for c in chars if c["ua"] is not None]
    out = {
        "store": over(lambda c: c["stores"]),
        "stored_jump": over(lambda c: c["stored_jumps"]),
        "ua_anims": {"events": len(uas), "anims": len(uas), "characters": len(uas)},
        "spawn": over(lambda c: [s for u in ([c["ua"]] if c["ua"] else []) for s in u["spawns"]]),
        "impulse": over(lambda c: [s for u in ([c["ua"]] if c["ua"] else []) for s in u["impulses"]]),
        "end_key": over(lambda c: [{"anim": "0x18", "member": c["prefix"]} for _ in
                                   (c["ua"]["ends"] if c["ua"] else [])]),
    }
    for kind in ("arm_substitute", "invuln", "hp", "sp", "status", "lead"):
        out[kind] = over(lambda c, k=kind: [e for u in ([c["ua"]] if c["ua"] else []) for e in u["effects"]
                                             if (e["kind"] == k) or (k == "lead" and e.get("grade") == "lead")])
    return out


# ------------------------------------------------------------------ output


def dump(table: dict) -> str:
    return json.dumps(table, indent=1, ensure_ascii=False, sort_keys=True) + "\n"


def consumers_of(c: dict, value: int) -> list[str]:
    """Jumps of the same character whose Marker list holds the stored value."""
    out = []
    for j in c["stored_jumps"]:
        if str(value) in j["targets"]:
            out.append(f"{j['anim']} f{j['frame']} -> f{j['targets'][str(value)]}")
    return out


def char_summary(c: dict) -> dict:
    stores = [f"{s['anim']} f{s['frame']} = {s['value']}" for s in c["stores"]]
    values = sorted({s["value"] for s in c["stores"]})
    consumers = []
    for v in values:
        for line in consumers_of(c, v):
            consumers.append(f"{line} (store {v})")
    return {"prefix": c["prefix"],
            "names": ", ".join(n["name"] for n in c["names"]) or "(no name)",
            "frames": c["ua"]["frames"] if c["ua"] else None,
            "ends": c["ua"]["ends"] if c["ua"] else [],
            "effect_class": effect_class(c["ua"]),
            "stores": stores, "consumers": consumers, "error": c["error"]}


def render_md(table: dict) -> str:
    rows = [char_summary(c) for c in table["characters"]]
    n_ua = sum(c["ua"] is not None for c in table["characters"])
    cnt = table["counts"]
    g = table["guide_check"]
    gn = {k: sum(r["status"] == k for r in g) for k in ("ua_effects", "playhead_only", "no_events", "unmapped")}
    L = [
        "# Ultimate Action table (SELECT, move id 11, anim 0x18)",
        "",
        "Generated by `scripts/analysis/ua_table.py build`; do not edit. "
        "`python -B scripts/analysis/ua_table.py check` verifies freshness. Machine-readable copy: "
        "[ua-table.json](ua-table.json). Static: read from each character's motion table, the shot files and "
        "ov6, no emulator. Owner statements on the Ultimate Actions: "
        "[OWNER-NOTES.md](../research/moveset-notes/OWNER-NOTES.md#ultimate-actions-owner-2026-10-12).",
        "",
        "## Rules",
        "",
        "- **Trigger.** The ground reader tests SELECT (0x1000) at 0x0215A7D0 and returns move id 11 = anim 0x18,"
        " state 0x0C, with no SP cost. The air reader returns only ids 9 and 10, so an airborne SELECT is not"
        " the UA. Every battle prefix has an anim 0x18 row below.",
        "- **Team register.** `ctrl+0xA3` is a per-team byte, -1 at init (0x0215542C). Sub 19 (`store`, 0x021560EC)"
        " writes its signed value ev[2]. Sub 20 (`stored_jump`, 0x021560F8) queues a jump to the Marker whose id"
        " is the stored value and resets the byte to -1, even when the anim has no such Marker. Only ov6 writes"
        " it; the switch and the hit path do not clear it (review.md b3-b5).",
        "- **Op 3 arguments** (case table 0x02157A68, one branch per arg): 2 spawn (shot row ev[4]), 7 invuln"
        " (+0xCE, s16 ticks), 9 arm_substitute (decoy index ev[4], signed; the arm lasts 121 ticks, 0x0215A980),"
        " 10 status (u16 ev[4..5] indexes the byte table at 0x0217215C, giving the status id the acting fighter"
        " receives; 0x02157C5C), 23 hp (s16 ev[4..5]; HP raw = displayed HP x 64), 24 sp (s16 ev[4..5]; SP raw 25600 = one bar)."
        " Args 17 and 18 and any other arg are kept raw with grade `lead`.",
        "- **Op 1 sub 3 impulse.** x = ev[2] * 32 (facing-signed), y = ev[3] * -126 (table 0x02172020[3] ="
        " 0x0215669C, `mvn r0,#0x7d` at 0x021566F4).",
        "- **Op 3 sub 1** is the end key (0x0215693C): `ends` per anim. The playhead events (sub 0, 1, 2, 3, 4,"
        " 18, 19, 20, 23) decode with the mash table's decoders.",
        "- **Spawn rows** are op 3 arg 2 events. The shot row (chr/shot/<prefix>.bin, 32 bytes, art u32 at byte 12)"
        " is measured. `kb_recs` is an inferred join (review c4): the art's low byte is an anim id, and `kb_recs`"
        " lists the knockback records whose collision track keys that anim (`knockback_table.record_uses`)."
        " The join can be ambiguous: several records can match one row (ds_b_01 spawns list [11, 15]),"
        " and bc_b_02 row 0 (art 0x00074241) matches none. `has_kb_record` is true when `kb_recs` is non-empty"
        " and null only when the row is not in the file.",
        "- **Stores and jumps** are cast-wide: every sub 19 and sub 20 in every anim of the prefix (any member),"
        " with `targets` = {Marker id: frame} for every Marker of that anim. The consumers column joins a stored"
        " value to the jumps of the same character that list it.",
        "",
        "## Cites",
        "",
        "| address | what | review.md |",
        "|---|---|---|",
        "| 0x0215A7D0 | `tst r0,#0x1000`, SELECT edge in the ground reader | §1 a1 |",
        "| 0x0215A8C0-0x0215A8F8 | air reader: `movne r0,#9` / `#0xa` only | §1 a2 |",
        "| 0x021712B8 + 12*11 | move id 11 = (0x18, -1, 0xffff0c) | §1 a4 |",
        "| 0x02171098 | button masks 0x80, 0x100, 0x40, 0x1000 = B, Y, X, SELECT | §1 g3 |",
        "| 0x0215542C | ctor `strb r0,[r4,#0xa3]`: the store byte is -1 | §1 b3 |",
        "| 0x021560EC | sub 19 store, `strb r1,[r0,#0xa3]` at 0x021560F0 | §1 b1 |",
        "| 0x021560F8 | sub 20 stored jump, clears ctrl+0xA3 at 0x0215611C | §1 b2 |",
        "| 0x0215693C | op 3 sub 1 end key (ctrl+0x90 bit 0x10000000) | §3.1 |",
        "| 0x02157A68 | op 3 case table (branch per arg): 2 0x02157BB0, 7 0x02157C30, 9 0x02157C4C, "
        "17 0x02157D2C, 18 0x02157D38, 23 0x02157DB8, 24 0x02157DC8 | §3.5 |",
        "| 0x02172020[3] = 0x0215669C | op 1 sub 3 impulse; `mvn r0,#0x7d` at 0x021566F4 | §1 f1 |",
        "| 0x02157C4C -> 0x0215C034 | arm_substitute (decoy ev[4]) | §1 d1 |",
        "| 0x0215A980 | arm timer (121 ticks) | §1 d2 |",
        "| 0x02157C5C, 0x0217215C | status (op 3 arg 10): operand -> id byte table, then 0x02158ED0 | status-system-design 2.1 A1, A3 |",
        "| 0x020783CC / 0x020781E4 | HP and SP apply targets of args 23 and 24 | uare2 §3 |",
        "",
        "## Counts (cast-wide)",
        "",
        "| kind | events | anims | chars |",
        "|---|---|---|---|",
    ]
    for k in ("store", "stored_jump", "spawn", "impulse", "end_key", "arm_substitute", "invuln", "hp", "sp", "status", "lead"):
        v = cnt[k]
        L.append(f"| {k} | {v['events']} | {v['anims']} | {v['characters']} |")
    L += [
        "",
        f"{n_ua} of {len(rows)} battle prefixes have an anim 0x18 row.",
        "",
        "## Per character",
        "",
        "`effect class` is the set of kinds in the anim 0x18 row. `store` lists the sub 19 rows of the character"
        " (anim, frame, value); `consumers` lists the sub 20 jumps that hold a stored value (anim, frame, target"
        " frame). `ends` are the op 3 sub 1 frames.",
        "",
        "| prefix | name | frames | ends | effect class | store | consumers |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        L.append(f"| {r['prefix']} | {r['names']} | {r['frames'] if r['frames'] is not None else '-'} | "
                 f"{', '.join(map(str, r['ends'])) or '-'} | {r['effect_class']} | "
                 f"{'; '.join(r['stores']) or '-'} | {'; '.join(r['consumers']) or '-'} |")
    L += [
        "",
        "## Guide cross-check",
        "",
        "The GameFAQs extracts tag the select input (the Ultimate Action). Joined by prefix (mash_table.GUIDE_FILES):",
        f"{gn['ua_effects']} with an effect, store, consume or spawn in anim 0x18; {gn['playhead_only']} with only"
        f" playhead events; {gn['no_events']} with none; {gn['unmapped']} unmapped.",
        "",
        "| guide | name | status | prefixes |",
        "|---|---|---|---|",
    ]
    for r in g:
        L.append(f"| {r['file']} | {r['name'] or '-'} | {r['status']} | {', '.join(r['prefixes']) or r.get('note', '-')} |")
    L += [
        "",
        "## Open questions",
        "",
        "- has_kb_record and kb_recs: the join (art low byte = anim id, review c4) is inferred, not traced to a"
        " hitbox. One row can match several records (ds_b_01: [11, 15]), so kb_recs is a candidate list, not a"
        " single record.",
        "- Args 17 and 18 have addresses but no traced semantics; they are `lead` rows.",
        "- Stored values are a team register; the stored value persists across character switches (review.md b4)"
        " and the consumers listed here are per prefix, so a cross-prefix consume is not joined.",
        "- Owner statements on the Ultimate Actions: [OWNER-NOTES.md](../research/moveset-notes/OWNER-NOTES.md#ultimate-actions-owner-2026-10-12).",
        "",
    ]
    return "\n".join(L)


def show(char: dict) -> str:
    out = [char["prefix"] + " " + (", ".join(f"{n['name']} (chr_b {n['chr_b']})" for n in char["names"])
                                   or "(no name)")]
    ua = char["ua"]
    if ua is None:
        out.append("  no anim 0x18")
        return "\n".join(out)
    out.append(f"  anim {ua['anim']} frames {ua['frames']} ends {ua['ends']} markers {ua['markers']}")
    for e in ua["playhead"]:
        out.append(f"     f{e['frame']:>3} playhead {e['kind']:<12} {e['raw']}")
    for e in ua["effects"]:
        out.append(f"     f{e['frame']:>3} effect {e['kind']:<16} grade {e['grade']} {e['raw']}")
    for e in ua["impulses"]:
        out.append(f"     f{e['frame']:>3} impulse x {e['x_raw']} y {e['y_raw']}")
    for e in ua["spawns"]:
        out.append(f"     f{e['frame']:>3} spawn row {e['row']} art {e['art']} kb {e['kb_recs']}")
    for s in char["stores"]:
        out.append(f"  store {s['anim']} f{s['frame']} value {s['value']}")
    for j in char["stored_jumps"]:
        out.append(f"  jump {j['anim']} f{j['frame']} targets {j['targets']}")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="write docs/rebuild/ua-table.json and .md")
    sub.add_parser("check", help="exit 0 iff the committed files equal a fresh build")
    s = sub.add_parser("show", help="print one character's Ultimate Action")
    s.add_argument("prefix")
    a = ap.parse_args(argv)
    table = build()
    if a.cmd == "build":
        OUT.write_text(dump(table), encoding="utf-8")
        OUT_MD.write_text(render_md(table), encoding="utf-8")
        print(f"wrote {OUT.relative_to(REPO)} and {OUT_MD.relative_to(REPO)}")
        return 0
    if a.cmd == "show":
        print(show(next(c for c in table["characters"] if c["prefix"] == a.prefix)))
        return 0
    fresh = OUT.exists() and OUT.read_text(encoding="utf-8") == dump(table) \
        and OUT_MD.exists() and OUT_MD.read_text(encoding="utf-8") == render_md(table)
    print("fresh" if fresh else "STALE: run build")
    return 0 if fresh else 1


if __name__ == "__main__":
    raise SystemExit(main())
