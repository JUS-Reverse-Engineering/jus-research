#!/usr/bin/env python3
"""Static tap-extendable ("mash") move scanner for every JUS battle character:
every input-conditional NoteTrack event in the fighter animation data, decoded
field by field. No emulator.

Schema and cast summary: docs/rebuild/mash-table.md. Output:
docs/rebuild/mash-table.json. Basis: ov6 disassembly and the NoteTrack bytes of
each `chr/<prefix>.aar` motion table (parser: anim_events.py / move_records.py,
the same one knockback_table.py reads).

The chain, all static:

  Event. A NoteTrack key holds events of u8 sub, u8 op, then op-specific bytes.
      The per-frame loop (ov6 0x021557C0, op = byte 1 at 0x021557F0-0x021557F4)
      calls table 0x0217200C[op]. Only ops 0-4 occur in the data. Op 0 (handler
      0x02156188) calls table 0x02172084[sub], sub = byte 0.
  Sub 0 (0x02155A04), counter-limited loop. Returns early if [obj+0x78] is 0. Calls the
      counter (fn 0x021561A8) with limit ev[3] (signed). Only ov6 writes obj+0xA2 (one byte
      per object, reset on anim change at 0x021555D4), so every limited event of an anim
      SHARES it. `c = byte; byte = c + 1; if c >= limit: byte = 0, blocked`: it bumps on
      every evaluation, pressed or not, and the (limit+1)th evaluation is blocked and resets
      it to 0. A limit of -1 is unlimited and does not bump. A blocked event does nothing.
      Otherwise it counts presses of button ev[4] over window ev[5] (0x021613C4, rule below)
      and at ev[6] presses queues a jump to Marker ev[2] (0x021565A4).
  Sub 18 (0x02155A84), two-way branch. Same press count over ev[5] and threshold ev[6]
      on button ev[4]; fewer than the threshold queues Marker ev[2], else Marker ev[3].
      No counter; a jump is queued either way.
  Press counting (0x021613C4, over the history updater 0x02161148). The input history is
      a ring of 16 segments, each a run of an unchanged input word with its stored duration
      (length - 1), plus the current word and its duration. An edge (the button's edge mask,
      table 0x02171098) counts if its AGE <= the window, where age counts only the ticks on
      which the word stayed unchanged: raw age minus the number of word changes since the
      edge. A current word older than the window counts nothing. So a mash that changes the
      word every tick keeps every edge in the ring (up to 8) fresh, and a press from before
      the move counts: the history runs continuously across moves. Facing is not a bit of the
      word: when the fighter faces left the updater swaps the LEFT and RIGHT bits (4 and 8), so
      a turn is a word change only while a horizontal is held. Directions are held-only bits;
      the shoulder bits (0x4000, 0x8000) are edge-only. A run's duration rolls over at 600.
      The updater runs before the check in the same tick. This reproduces all 35 committed
      Kakashi wmqi2 side Y trials
      (31 distinct tap schedules in wmqi2-guard-2026-09-22/logs/mash_summary.json) and the
      historical +4,+12 row. The 15 review cases (14 of those schedules plus the historical row)
      fit 15 of 15; the plain "edges on elapsed ticks (t - window, t]" rule fits 11 of 15.
      Executable form: scripts/analysis/mash_path.py (Ring), pinned by
      scripts/tests/test_mash_path.py.
  Sub 1 (0x02155B04), hold tiers. Queues a type-1 slot (handler 0x021561E4,
      table 0x02172040) that reads how long the button ev[2] has been held and
      jumps to one of three markers by hold length.
  Sub 23 (0x02155BA0), direction branch. Reads the d-pad nibble of the input
      word (hist+0x50 & 0xF) and queues Marker ev[2] or the per-direction
      marker among ev[3..10].
  Marker. The anim's `Marker` track is (u16 frame, u16 marker) keys; the queued
      jump (slot loop 0x02155700, vtable+0xEC) lands on that marker's frame.

Only the code facts the decode rests on are read from ov06.bin here;
`code_facts()` returns them and the test pins each one.

Usage:
    python3 scripts/analysis/mash_table.py build   # write the .json and .md
    python3 scripts/analysis/mash_table.py check   # exit 0 = committed files are fresh
    python3 scripts/analysis/mash_table.py show bc_b_01
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
import cancel_table as C  # noqa: E402
import move_records as mr  # noqa: E402

REPO = HERE.parent.parent
OUT = REPO / "docs" / "rebuild" / "mash-table.json"
OUT_MD = REPO / "docs" / "rebuild" / "mash-table.md"

OP_TABLE = 0x0217200C
SUB_TABLE = 0x02172084
BUTTON_TABLE = 0x02171098
SLOT_TABLE = 0x02172040
BUTTON_COUNT = 4          # 0x02171098..0x021710A7 (the next table starts at 0x021710A8)

KINDS = {0: "count_loop", 18: "two_way", 1: "hold_tiers", 23: "direction",
         2: "loop", 3: "ground_wait", 4: "air_wait", 19: "store", 20: "stored_jump",
         **E.BRANCH_KINDS}
MASH_SUBS = (0, 18)
# Input or state branches counted as conditional (mash = MASH_SUBS, other = the rest).
INPUT_CONDITIONAL_SUBS = (0, 1, 5, 9, 14, 18, 23)
# bytes the handler reads from the event start (the raw column keeps exactly these)
RAW_LEN = E.SUB_EVENT_LEN
# a sub 1 with no hold tier set is a plain "press X, release -> marker" event
HOLD_RELEASE = "hold_release"
CORE_HOLD_RELEASE = ("button ev[2], default Marker ev[4]. Static trace (unverified live): a level poll from "
                     "the tick after creation that fires on the first tick the button is not down (0x02161440).")

# Button names, idx into table 0x02171098 (edge masks 0x80, 0x100, 0x40, 0x1000). The ground
# move reader maps 0x80 to the B moves, 0x100 to Y, 0x40 to X and 0x1000 to SELECT (the
# Ultimate Action, id 11), which names idx 0 = B and idx 3 = SELECT; idx 2 = X was the
# owner/findings reading and idx 1 = Y the Kakashi side Y mash.
BUTTON_NAMES = {0: "B", 1: "Y", 2: "X", 3: "SELECT"}

# handler -> {field: ARM address of the load that reads it from the event pointer r4}
SITES = {
    0: {"marker": 0x02155A74, "limit": 0x02155A28, "button": 0x02155A38,
        "window": 0x02155A40, "threshold": 0x02155A54},
    18: {"marker_false": 0x02155AF0, "marker_true": 0x02155AE4, "button": 0x02155AAC,
         "window": 0x02155AB0, "threshold": 0x02155AC4},
    1: {"button": 0x02155B34, "hold_flag": 0x02155B3C, "marker_default": 0x02155B28,
        "marker_1": 0x02155B44, "marker_2": 0x02155B4C, "marker_3": 0x02155B54,
        "hold_1": 0x02155B5C, "hold_2": 0x02155B64, "hold_3": 0x02155B6C},
    23: {"marker_default": 0x02155C6C},
    2: {"marker": 0x021559DC, "limit": 0x021559C8},
    3: {"marker": 0x02155CB0},
    4: {"marker": 0x02155D04},
    19: {"value": 0x021560EC},
    20: {},                      # reads no event byte: the jump target is the stored value
}
# the register the handler holds the event pointer in, where it is not r4
EVENT_REG = {3: 1, 4: 1, 19: 1}
SUB_ENTRY = {0: 0x02155A04, 18: 0x02155A84, 1: 0x02155B04, 23: 0x02155BA0,
             2: 0x021559C0, 3: 0x02155CAC, 4: 0x02155D00, 19: 0x021560EC, 20: 0x021560F8}
# ov6 words that carry the new decodes; pinned in code_facts.words
PINNED_WORDS = (
    0x021559C0, 0x021559C8, 0x021559DC,                  # sub 2: entry, limit ldrsb, marker ldrb
    0x02155CAC, 0x02155CB0, 0x02155CB4,                  # sub 3: entry, marker ldrsb, mov r1,#2 (kind)
    0x02155D00, 0x02155D04, 0x02155D08,                  # sub 4: entry, marker ldrsb, mov r1,#4 (kind)
    0x021560EC, 0x021560F0,                              # sub 19: ldrsb value, strb ctrl+0xA3
    0x021560F8, 0x02156100, 0x02156114, 0x0215611C,      # sub 20: entry, ldrsb A3, bl queue, strb -1
    0x021562E8, 0x021562EC, 0x021562F0,                  # grounded test: ldr, ldr +0x78, tst #2
    0x02156358, 0x02156360,                              # kind 4 handler: bl grounded test
    0x0215693C, 0x02156954,                              # op 3 sub 1 (end key): entry, orr #0x10000000
)
GROUND_TEST = 0x021562E8                 # returns 1 iff the grounded bit is set
GROUND_KIND_HANDLER = 0x021562D8         # slot-table handler of queue kind 2
AIR_KIND_HANDLER = 0x02156358            # queue kind 4
SLOT_FOR_KIND = 0x021710A8               # byte per queue kind -> slot (0..6)
OP3_SUB_TABLE = 0x02172000               # op 3 dispatches by sub through this table
END_KEY_SUB = 1                          # op 3 sub 1: sets ctrl+0x90 |= 0x10000000
DIRECTION_BASE_SITE = 0x02155C50      # ldrb r2,[r0,#3] with r0 = event + direction index
DIRECTIONS = (0x8, 0x9, 0x1, 0x5, 0x4, 0x6, 0x2, 0xA)   # nibble -> index 0..7 (0x02155BF0-0x02155C48)

# (prefix, anim) -> independent confirmations of a mash. Cites are repo paths or the
# brief that recorded them.
CONFIRMED = {
    ("bc_b_01", 0x29): [
        {"source": "capture", "cite": "docs/research/feel-captures/2026-10-12-eve-specials/README.md:119 "
                                      "(unmashed 4 hits = 18 HP) and :231 (full mash 10 hits = 30 HP)"},
        {"source": "owner", "cite": "docs/research/moveset-notes/OWNER-NOTES.md:632"}],
    ("bc_b_01", 0x2C): [
        {"source": "capture", "cite": "docs/research/feel-captures/2026-10-12-eve-specials/README.md:240-242 "
                                      "(id 275 appears only when mashed; the 8-hit maximum was not reproduced)"}],
    ("na_b_04", 0x21): [
        {"source": "owner", "cite": "docs/research/moveset-notes/OWNER-NOTES.md:47 (forward Y: mash Y for more shuriken)"},
        {"source": "capture", "cite": "docs/confirmed-facts/characters/kakashi.md:113-114 (side Y: 2 shuriken, 6 mashed)"}],
    ("bc_b_02", 0x21): [
        {"source": "owner", "cite": "docs/research/moveset-notes/OWNER-NOTES.md:632"}],
    ("bc_b_02", 0x27): [
        {"source": "owner", "cite": "docs/research/moveset-notes/OWNER-NOTES.md:632"}],
}

# GameFAQs move guides tag some moves "mash-extend" (docs/research/gamefaqs-movesets/*.json).
# stem -> the battle prefixes the guide's character can be (several where the guide covers
# a form family; a guide entry matches if any of them has the move flagged).
GUIDE_DIR = REPO / "docs" / "research" / "gamefaqs-movesets"
GUIDE_FILES = {
    "bankai-ichigo": ["bl_b_02"], "dio": ["jj_b_02"], "eve": ["bc_b_01"], "franky": ["op_b_06"],
    "frieza": ["db_b_10"], "gohan": ["db_b_05", "db_b_06"], "goku": ["db_b_01", "db_b_02"],
    "gotenks": ["db_b_07", "db_b_08"], "ichigo": ["bl_b_01"], "jotaro": ["jj_b_01"],
    "kagura": ["gt_b_02"], "kenshiro": ["hk_b_01"], "kurama": ["yh_b_02"], "lenalee": ["dg_b_02"],
    "luffy": ["op_b_01", "op_b_07"], "majin-buu": ["db_b_11"], "momotaro": ["oj_b_02"],
    "muhyo": ["mr_b_01"], "nami": ["op_b_04", "op_b_08"], "neuro": ["nn_b_01"],
    "nico-robin": ["op_b_05"], "renji": ["bl_b_04"], "rukia": ["bl_b_03"], "sanji": ["op_b_03"],
    "seiya": ["ss_b_01", "ss_b_02"], "train-heartnet": ["bc_b_02"], "tsuna": ["tr_b_01"],
    "vegeta": ["db_b_03", "db_b_04"],
    # E0 pin (feel-captures/2026-10-18-e0-roster/roster_reconciled.json): 48/22/66 measured.
    "don-patch": ["bb_b_02"], "edajima": ["oj_b_01"], "sakura": ["na_b_03"],
}
# E0 resolved Don Patch (48 = bb_b_02), Edajima (66 = oj_b_01) and Sakura (22 = na_b_03); nothing is unmapped now.
GUIDE_UNMAPPED: dict[str, str] = {}
GUIDE_INPUTS = {"X+up": "up X", "neutral/forward X": "X"}

# anims 0x29-0x2E: X and up X per koma size. Measured for Kakashi and Yusuke in
# anim-timing.json; ids 13/14 take their anim from a per-fighter byte
# (cancel-table.md), so for any other fighter this is a reading, not a read.
SPECIAL_ANIMS = {0x29: ("X", 4), 0x2A: ("up X", 4), 0x2B: ("X", 5), 0x2C: ("up X", 5),
                 0x2D: ("X", 6), 0x2E: ("up X", 6)}

# every key an event or an anim row can carry -> its grade
FIELD_GRADES = {
    "raw": "measured", "frame": "measured", "sub": "measured", "frames": "measured",
    "anim": "measured", "member": "measured", "markers": "measured", "events": "measured",
    "marker": "measured", "marker_false": "measured", "marker_true": "measured",
    "marker_default": "measured", "marker_1": "measured", "marker_2": "measured",
    "marker_3": "measured", "limit": "measured", "window": "measured", "threshold": "measured",
    "button_idx": "measured", "button_mask": "measured", "hold_flag": "measured",
    "hold_1": "measured", "hold_2": "measured", "hold_3": "measured",
    "markers_by_direction": "measured",
    "marker_frame": "measured", "marker_false_frame": "measured", "marker_true_frame": "measured",
    "marker_default_frame": "measured", "marker_1_frame": "measured", "marker_2_frame": "measured",
    "marker_3_frame": "measured", "frames_by_direction": "measured",
    "limit_unbounded": "inferred",
    "value": "measured", "targets": "measured", "ends": "measured",
    "disarm": "inferred (marker -1 empties the slot: sub 3 stores the arg, the slot loop skips -1)",
    "query": "STATIC (anim_events.decode_branch: sub 14 queries 0x42)",
    "queue_kind": "STATIC (sub 9 handler 0x02155DB8 queues kind 9; p230)",
    "poll": "STATIC (kind-9 poll table 0x02172040[9] = 0x021564E8; p230)",
    "tiers": "STATIC (anim_events.decode_branch/resolve_branch: descending thresholds and marker frames)",
    "input_conditional": "inferred (an anim with an input or state branch: sub 0, 1, 5, 9, 14, 18 or 23)",
    "ground_wait": "inferred (an anim with a sub 3 event that arms a marker)",
    "kind": "inferred (semantics of each field: press count over a window, jump to marker)",
    "button": "inferred (idx 2 = X findings/owner, idx 1 = Y Kakashi side Y, idx 0 = B and idx 3 = SELECT "
              "from the ground move reader's mask-to-move mapping)",
    "move": "inferred", "move_id": "inferred", "mash": "inferred (a sub 0 or sub 18 event)",
    "confirmed": "independent (guide, capture or owner), cite given",
    "guide_check": "measured join: the guide tag text against the scanner's anims for the mapped prefixes",
}

GRADE_NOTES = {
    "bytes": "measured: the event bytes, read from the character's motion table (raw)",
    "frame": "measured: the NoteTrack key frame",
    "layout": "measured: each field's byte offset is the immediate of the ldrb/ldrsb/ldrh in the "
              "handler (code_facts.layout, ARM addresses in code_facts.sites)",
    "fields": "measured bytes at the measured offsets: marker, limit, button, window, threshold",
    "marker_frame": "measured: the anim's Marker track key whose marker equals the field; null if absent",
    "semantics": "inferred: what a field means (press count over a window of input-history frames, "
                 "a jump queued to the marker) follows from the handler code read statically and "
                 "the ov6 handlers 0x02155A04 (sub 0) and 0x02155A84 (sub 18), and the eve-specials "
                 "README (docs/research/feel-captures/2026-10-12-eve-specials/README.md); live checks are in confirmed",
    "button": "button index is measured; the history mask is measured (table 0x02171098 low halfword); "
              "name X for idx 2 is the findings/owner reading, Y for idx 1 is inferred from Kakashi "
              "side Y; idx 0 = B (0x80) and idx 3 = SELECT (0x1000) follow the ground move reader "
              "(0x0215A7CC tests 0x1000 for move id 11), read statically",
    "move": "inferred: ids 1-12 are the global move table (cancel_table.move_table) anim; X and up X "
            "are the anim-timing.json rows (anims 0x29-0x2E), per-fighter byte not read",
    "hold_tiers": "lead: the field mapping follows the slot copy in the sub-1 handler; matches the "
                  "Yusuke/Kakashi X charge thresholds in OWNER-NOTES.md but is not traced end to end",
    "direction": "lead: marker per d-pad direction read from the handler; direction names not resolved",
    "hold_release": "unverified: a sub 1 with no hold tier set. " + CORE_HOLD_RELEASE,
    "loop": "measured bytes; inferred semantics: an unconditional jump to marker ev[2] through the shared "
            "counter (0x021561A8) with limit ev[3]; -1 never bumps or blocks",
    "ground_wait": "measured bytes; inferred semantics: arms slot 0 (queue kind 2, grounded test 0x021562E8) with "
                   "marker ev[2]; the slot loop jumps there from any frame once grounded; arg -1 disarms",
    "air_wait": "measured bytes; semantics inferred from the handler (queue kind 4: fires while NOT grounded); "
                "not modeled in mash_path.py",
    "store": "measured bytes: ev[2] (signed) is written to the team's controller byte ctrl+0xA3 "
             "(0x021560EC); what the stored value means is the UA scanner's concern",
    "stored_jump": "measured: reads no event byte. If ctrl+0xA3 != -1 it queues a jump to that marker and "
                   "clears it to -1 (0x021560F8); `targets` is every marker of the anim, not a join",
    "counter_wait": "STATIC: sub 9, handler 0x02155DB8 queues kind 9 in slot 2; signed marker ev[2], "
                    "-1 disarms. Poll 0x021564E8 tests ColPrm+0x40 & 0x20000; "
                    "p230-kenshin-status-counter-sound.md",
    "branches": "STATIC: sub 5 contact_wait, sub 9 counter_wait and sub 14 deck_count_branch "
                "reuse anim_events.py "
                "decode_branch/resolve_branch; marker_frame is null for contact disarm or a missing "
                "marker. Sub 14 tiers keep descending min_count, marker and frame. Semantics: "
                "docs/research/2026-10-15-taikoubou-6kx-branches.md sections 2-3 and "
                "docs/research/findings/p230-kenshin-status-counter-sound.md; no live measurement.",
    "ends": "measured: frames of the op 3 sub 1 end-key events (handler 0x0215693C sets ctrl+0x90 bit 0x10000000); "
            "inferred: the move ends 2 ticks after the playhead reaches the first one, else at frames + 3 "
            "(5 of 5 measured idles: Train side Y 51 = 49+2, up Y 45 = 43+2, air Y 60 = 58+2, Yusuke side Y "
            "53 = 51+2, Kakashi UA 60 = (34 + 24 loop frames) + 2)",
}

# ------------------------------------------------------------------ code facts


def load_site(word: int) -> tuple[str, int, int]:
    """ARM LDRB / LDRSB / LDRH with an immediate offset -> (kind, base register, offset)."""
    if (word & 0x0E500000) == 0x04500000:                    # ldrb rd,[rn,#imm12]
        return "ldrb", (word >> 16) & 0xF, word & 0xFFF
    if (word & 0x0E5000F0) == 0x005000D0:                    # ldrsb rd,[rn,#imm8]
        return "ldrsb", (word >> 16) & 0xF, ((word >> 4) & 0xF0) | (word & 0xF)
    if (word & 0x0E5000F0) == 0x005000B0:                    # ldrh rd,[rn,#imm8]
        return "ldrh", (word >> 16) & 0xF, ((word >> 4) & 0xF0) | (word & 0xF)
    raise ValueError(f"0x{word:08X} is not an immediate byte/halfword load")


def and_mask(word: int) -> int:
    """AND rd,rn,#imm (no S) -> the immediate."""
    if (word & 0x0FE00000) != 0x02000000:
        raise ValueError(f"0x{word:08X} is not and #imm")
    rot, imm = (word >> 8) & 0xF, word & 0xFF
    return ((imm >> (2 * rot)) | (imm << (32 - 2 * rot))) & 0xFFFFFFFF


def imm_operand(word: int, opcode: int) -> int:
    """Rotated immediate of a data-processing word whose opcode bits (0x0FF00000) equal `opcode`."""
    if (word & 0x0FF00000) != opcode:
        raise ValueError(f"0x{word:08X} is not opcode 0x{opcode:08X}")
    rot, imm = (word >> 8) & 0xF, word & 0xFF
    return ((imm >> (2 * rot)) | (imm << (32 - 2 * rot))) & 0xFFFFFFFF


def index_byte(mask: int) -> int:
    """Which byte of the event halfword an `and ...,#mask` keeps."""
    return {0xFF: 0, 0xFF00: 1}[mask]


def code_facts() -> dict:
    """The code facts the decode rests on, read from ov06.bin."""
    sites = {}
    layout = {}
    for sub, fields in SITES.items():
        layout[sub], sites[sub] = {}, {}
        for name, addr in fields.items():
            kind, base, off = load_site(C.word(addr))
            reg = EVENT_REG.get(sub, 4)     # r4 = the event pointer unless the table says otherwise
            if base != reg:
                raise ValueError(f"sub {sub} {name}: load at 0x{addr:08X} is not [r{reg},#n]")
            layout[sub][name] = [kind, off]
            sites[sub][name] = f"0x{addr:08X}"
    dkind, dbase, doff = load_site(C.word(DIRECTION_BASE_SITE))
    buttons = [C.word(BUTTON_TABLE + 4 * i) for i in range(BUTTON_COUNT)]
    return {
        "op_table": f"0x{OP_TABLE:08X}",
        "sub_table": f"0x{SUB_TABLE:08X}",
        "button_table": f"0x{BUTTON_TABLE:08X}",
        "slot_table": f"0x{SLOT_TABLE:08X}",
        "op_index_byte": index_byte(and_mask(C.word(0x021557F0))),    # and r2,r2,#0xff00; asr #8
        "sub_index_byte": index_byte(and_mask(C.word(0x02156194))),   # and r3,r3,#0xff
        "op_table_pool": f"0x{C.word(0x02155948):08X}",               # literal after the slot loop
        "sub_table_literal": f"0x{C.pc_literal(0x02156190)[1]:08X}",  # ldr r2,[pc] in the op 0 handler
        "button_table_literal": f"0x{C.pc_literal(0x02155A3C)[1]:08X}",  # ldr r0,[pc] in sub 0
        "sub_handler": {str(s): f"0x{C.word(SUB_TABLE + 4 * s):08X}" for s in KINDS},
        "op0_handler": f"0x{C.word(OP_TABLE):08X}",
        "layout": {str(s): v for s, v in layout.items()},
        "sites": {str(s): v for s, v in sites.items()},
        "direction_marker_table": [dkind, doff],              # event + direction index + 3
        "directions": list(DIRECTIONS),
        "button_mask": [w & 0xFFFF for w in buttons],         # edge mask the count tests
        "button_held_mask": [w >> 16 for w in buttons],
        "counter_offset": 0xA2,
        "unlimited_limit": -1,
        "sub1_slot_handler": f"0x{C.word(SLOT_TABLE + 4):08X}",
        "kind_handler": {"2": f"0x{C.word(SLOT_TABLE + 8):08X}", "4": f"0x{C.word(SLOT_TABLE + 16):08X}"},
        "slot_for_kind": list(b"".join(C.word(SLOT_FOR_KIND + 4 * i).to_bytes(4, "little") for i in range(2))),
        "grounded_test": f"0x{GROUND_TEST:08X}",       # [[obj+0x7C]+0x10]+0x78 & mask
        "grounded_offset": C.word(GROUND_TEST + 4) & 0xFFF,
        "grounded_mask": imm_operand(C.word(GROUND_TEST + 8), 0x03100000),   # tst r0,#2
        "store_offset": C.word(0x021560F0) & 0xFFF,    # strb r1,[r0,#0xA3]
        "end_key": {"op": 3, "sub": END_KEY_SUB, "sub_table": f"0x{OP3_SUB_TABLE:08X}",
                    "handler": f"0x{C.word(OP3_SUB_TABLE + 4 * END_KEY_SUB):08X}",
                    "flag_offset": C.word(0x02156958) & 0xFFF,
                    "flag": f"0x{imm_operand(C.word(0x02156954), 0x03800000):08X}"},   # orr r0,r0,#
        "words": {f"0x{a:08X}": f"0x{C.word(a):08X}" for a in PINNED_WORDS},
    }


# ------------------------------------------------------------------ event decode


def field_value(raw: bytes, kind: str, off: int) -> int:
    if kind == "ldrsb":
        return struct.unpack_from("<b", raw, off)[0]
    if kind == "ldrh":
        return struct.unpack_from("<H", raw, off)[0]
    return raw[off]


def decode_event(sub: int, raw: bytes, facts: dict, markers: dict[int, int]) -> dict:
    """Fields of one op-0 event from its raw bytes, using the layout read from the code."""
    branch = E.decode_branch(sub, raw, 0)
    if branch is not None:
        row = E.resolve_branch(branch, markers)
        if sub in (5, 9):
            row["marker_frame"] = row.pop("frame")
        return dict(row, sub=sub, raw=raw.hex(" "))
    lay = facts["layout"][str(sub)]
    row = {"sub": sub, "kind": KINDS[sub], "raw": raw.hex(" ")}
    f = {name: field_value(raw, *spec) for name, spec in lay.items()}
    for name, v in f.items():
        row["button_idx" if name == "button" else name] = v
    if "button" in f:
        row["button"] = BUTTON_NAMES.get(f["button"], f"idx{f['button']}")
        mask = facts["button_mask"]
        row["button_mask"] = mask[f["button"]] if f["button"] < len(mask) else None
    for name in [n for n in f if n.startswith("marker")]:
        tier = name[-1] if name.startswith("marker_") and name[-1].isdigit() else None
        used = tier is None or f[f"hold_{tier}"] != 0
        row[name + "_frame"] = markers.get(f[name]) if used else None
    if sub in (0, 2):
        row["limit_unbounded"] = f["limit"] == -1
    if sub == 1 and not any(f[f"hold_{i}"] for i in (1, 2, 3)):
        row["kind"] = HOLD_RELEASE
    if sub in (3, 4):
        row["disarm"] = f["marker"] == -1          # arg -1 empties the slot
    if sub == 20:
        # reads no event byte: the stored value is the marker id, so every marker of the anim
        # is a possible target; which ones a stored value reaches is the UA scanner's join
        row["targets"] = {str(k): v for k, v in sorted(markers.items())}
    if sub == 23:
        _kind, off = facts["direction_marker_table"]
        row["markers_by_direction"] = list(raw[off:off + len(facts["directions"])])
        row["frames_by_direction"] = [markers.get(m or f["marker_default"]) for m in row["markers_by_direction"]]
    return row


def event_layout_check(facts: dict) -> None:
    """Fail loudly if the code facts moved: the subs below must keep the fields below."""
    layout = facts["layout"]
    need = {"0": {"marker", "limit", "button", "window", "threshold"},
            "18": {"marker_false", "marker_true", "button", "window", "threshold"},
            "2": {"marker", "limit"}, "3": {"marker"}, "4": {"marker"}, "19": {"value"}, "20": set()}
    for sub, names in need.items():
        if set(layout[sub]) != names:
            raise ValueError(f"layout for sub {sub} is {sorted(layout[sub])}")
    if facts["direction_marker_table"] != ["ldrb", 3]:
        raise ValueError(f"direction marker table is {facts['direction_marker_table']}")


# ------------------------------------------------------------------ scan


def node_events(almt, node) -> tuple[dict[int, int], list[dict]]:
    """({marker: frame}, [{frame, offs: [absolute event start]}]) for one SP01 node."""
    buf = almt.buf
    tr = E.node_tracks(buf, node["start"], almt.hdr_end, almt.props)
    markers = {}
    if "Marker" in tr and tr["Marker"][0] == "key":
        off, k = tr["Marker"][1], 0
        while off + 4 * k + 4 <= len(buf):
            fr = struct.unpack_from("<H", buf, off + 4 * k)[0]
            if fr == 0xFFFF:
                break
            markers.setdefault(struct.unpack_from("<H", buf, off + 4 * k + 2)[0], fr)
            k += 1
    keys = []
    if "NoteTrack" in tr and tr["NoteTrack"][0] == "key":
        off, k = tr["NoteTrack"][1], 0
        while off + 4 * k + 4 <= len(buf):
            fr = struct.unpack_from("<H", buf, off + 4 * k)[0]
            if fr == 0xFFFF:
                break
            rel = struct.unpack_from("<H", buf, off + 4 * k + 2)[0]
            rec = off + 2 * (2 * k + rel)
            n = struct.unpack_from("<H", buf, rec)[0]
            starts = [rec + 2 * struct.unpack_from("<H", buf, rec + 2 + 2 * i)[0] for i in range(n)]
            keys.append({"frame": fr, "starts": starts})
            k += 1
    return markers, keys


def scan_almt(almt, facts: dict) -> list[dict]:
    """One row per animation that has at least one event of a kind in KINDS. `ends` are the
    frames of its op 3 sub 1 end keys (data only: an anim with end keys and no KINDS event has no row)."""
    rows = []
    for _idx, full in almt.full_animations():
        top = full["nodes"][0]
        if top["entry"] is None:
            continue
        aid, frames = top["entry"]["id"], top["entry"]["frames"]
        for node in full["nodes"]:
            if node["name"] != "SP01" or node["start"] is None:
                continue
            markers, keys = node_events(almt, node)
            events, ends = [], set()
            for key in keys:
                for s in key["starts"]:
                    sub, op = almt.buf[s], almt.buf[s + 1]
                    if op == 3 and sub == END_KEY_SUB:
                        ends.add(key["frame"])
                    if op != 0 or sub not in KINDS:
                        continue
                    raw = bytes(almt.buf[s:s + RAW_LEN[sub]])
                    ev = decode_event(sub, raw.ljust(RAW_LEN[sub], b"\0"), facts, markers)
                    ev["frame"] = key["frame"]
                    events.append(ev)
            if events:
                rows.append({"anim_id": aid, "frames": frames, "markers": markers, "events": events,
                             "ends": sorted(ends)})
    return rows


def move_label(aid: int, table: dict) -> tuple[str | None, int | None]:
    for i, row in table.items():
        if row["anim"] == aid and i <= 12:
            return C.NAMES[i], i
    if aid in SPECIAL_ANIMS:
        name, koma = SPECIAL_ANIMS[aid]
        return f"{name} (koma {koma})", 13 if name == "X" else 14
    return None, None


def names_for(prefix: str) -> list[dict]:
    """move_records.chrb_names_for, the join shared with the cancel, knockback and ua tables."""
    return mr.chrb_names_for(prefix)


def build_char(prefix: str, facts: dict, table: dict) -> dict:
    out = {"prefix": prefix, "names": names_for(prefix), "anims": [], "error": None}
    try:
        found = []
        for member, almt in mr.motions(prefix):
            for row in scan_almt(almt, facts):
                found.append((member, row))
    except BaseException as ex:  # SystemExit from the loaders, struct errors
        out["error"] = f"{type(ex).__name__}: {ex}"
        return out
    for member, row in sorted(found, key=lambda t: (t[1]["anim_id"], t[0])):
        move, move_id = move_label(row["anim_id"], table)
        evs = sorted(row["events"], key=lambda e: (e["frame"], e["sub"]))
        mash = [e for e in evs if e["sub"] in MASH_SUBS]
        entry = {"anim": f"0x{row['anim_id']:02x}", "member": member, "frames": row["frames"],
                 "move": move, "move_id": move_id, "mash": bool(mash),
                 "input_conditional": any(e["sub"] in INPUT_CONDITIONAL_SUBS for e in evs),
                 "ground_wait": any(e["sub"] == 3 and not e["disarm"] for e in evs),
                 "markers": {str(k): v for k, v in sorted(row["markers"].items())},
                 "ends": row["ends"],
                 "events": evs}
        conf = CONFIRMED.get((prefix, row["anim_id"]))
        if conf:
            entry["confirmed"] = [dict(c) for c in conf]
        out["anims"].append(entry)
    return out


def guide_entries() -> list[dict]:
    """Every "mash-extend" move in the GameFAQs extracts, sorted."""
    out = []

    def walk(o, stem, who):
        if isinstance(o, dict):
            if "mash-extend" in (o.get("properties") or []):
                out.append({"file": stem, "character": who, "input": o.get("input"),
                            "name": o.get("name")})
            for v in o.values():
                walk(v, stem, who)
        elif isinstance(o, list):
            for v in o:
                walk(v, stem, who)

    for path in sorted(GUIDE_DIR.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        walk(doc, path.name.split("--")[0], doc.get("character"))
    return sorted(out, key=lambda r: (r["file"], r["input"] or "", r["name"] or "", r["character"] or ""))


def base_move(name: str | None) -> str:
    return (name or "").split(" (koma")[0]


def guide_check(chars: list[dict]) -> list[dict]:
    """Join each guide "mash-extend" tag to the scanner: flagged (a sub 0 or 18 event on that
    move for a candidate prefix), other_event (only hold or direction events), not_found."""
    by_prefix = {c["prefix"]: c for c in chars}
    rows = []
    for g in guide_entries():
        row = dict(g)
        inp = GUIDE_INPUTS.get(g["input"], g["input"])
        if g["input"] == "select":
            row.update(status="not_a_move", prefixes=[], note="select-button Ultimate Action, not a move input")
        elif g["file"] in GUIDE_UNMAPPED:
            row.update(status="unmapped", prefixes=[], note=GUIDE_UNMAPPED[g["file"]])
        else:
            prefixes = GUIDE_FILES[g["file"]]
            hits = [(p, a) for p in prefixes for a in by_prefix[p]["anims"] if base_move(a["move"]) == inp]
            flagged = [f"{p} {a['anim']}" for p, a in hits if a["mash"]]
            other = [(p, a) for p, a in hits if a.get("input_conditional", True)]
            row.update(prefixes=prefixes,
                       status="flagged" if flagged else "other_event" if other else "not_found",
                       matched=flagged or [f"{p} {a['anim']}" for p, a in other])
        rows.append(row)
    return rows


def attach_guide(chars: list[dict], rows: list[dict]) -> None:
    """Record each flagged guide tag as a confirmation on the anims it matched."""
    by_prefix = {c["prefix"]: c for c in chars}
    for r in rows:
        if r["status"] != "flagged":
            continue
        for m in r["matched"]:
            prefix, anim = m.split()
            a = next(a for a in by_prefix[prefix]["anims"] if a["anim"] == anim)
            cite = {"source": "guide", "cite": f"docs/research/gamefaqs-movesets/{r['file']}--*.json: "
                                               f"{r['input']} {r['name'] or ''}".rstrip()}
            if len(r["prefixes"]) > 1:
                cite["cite"] += f" (guide covers {', '.join(r['prefixes'])})"
            if cite not in a.setdefault("confirmed", []):
                a["confirmed"].append(cite)
    for c in chars:
        for a in c["anims"]:
            if "confirmed" in a:
                a["confirmed"].sort(key=lambda x: (x["source"], x["cite"]))


def cast_end_keys() -> dict:
    """Cast-wide op 3 sub 1 end keys over every SP01 node of every member: distinct key frames per
    node (events) and the nodes that have one (anims). Not limited to the anims that have a row."""
    events = anims = 0
    for prefix in C.battle_prefixes():
        for _member, almt in mr.motions(prefix):
            for _idx, full in almt.full_animations():
                if full["nodes"][0]["entry"] is None:
                    continue
                for node in full["nodes"]:
                    if node["name"] != "SP01" or node["start"] is None:
                        continue
                    _markers, keys = node_events(almt, node)
                    ends = {k["frame"] for k in keys for st in k["starts"]
                            if almt.buf[st] == END_KEY_SUB and almt.buf[st + 1] == 3}
                    events += len(ends)
                    anims += bool(ends)
    return {"events": events, "anims": anims}


def build() -> dict:
    facts = code_facts()
    event_layout_check(facts)
    table = C.move_table()
    chars = [build_char(p, facts, table) for p in C.battle_prefixes()]
    guide = guide_check(chars)
    attach_guide(chars, guide)
    return {
        "_schema": "docs/rebuild/mash-table.md",
        "_generated_by": "python3 scripts/analysis/mash_table.py build",
        "field_grades": FIELD_GRADES,
        "grade_notes": GRADE_NOTES,
        "code_facts": facts,
        "guide_check": guide,
        "characters": chars,
        "end_keys_cast": cast_end_keys(),
    }


# ------------------------------------------------------------------ summary


def summary(table: dict) -> list[dict]:
    """One row per character with a mash or other input-conditional event, or a wait loop."""
    rows = []
    for c in table["characters"]:
        mash = [a for a in c["anims"] if a["mash"]]
        other = [a for a in c["anims"] if a["input_conditional"] and not a["mash"]]
        buttons = sorted({e["button"] for a in mash for e in a["events"] if e["sub"] in MASH_SUBS})
        rows.append({"prefix": c["prefix"], "names": ", ".join(n["name"] for n in c["names"]) or "(no name)",
                     "mash": len(mash), "other": len(other), "buttons": buttons,
                     "ground_wait": sum(a["ground_wait"] for a in c["anims"]),
                     "moves": [(a["move"] or f"anim {a['anim']}") + f" [{a['anim']}]" for a in mash],
                     "confirmed": [a["anim"] for a in mash if a.get("confirmed")],
                     "error": c["error"]})
    return rows


def counts(table: dict) -> dict:
    """Cast-wide event counts per new kind: events, anims and characters carrying them."""
    def over(pred):
        ev = [(c["prefix"], a["anim"], e) for c in table["characters"] for a in c["anims"]
              for e in a["events"] if pred(e)]
        return {"events": len(ev), "anims": len({(p, a) for p, a, _ in ev}),
                "characters": len({p for p, _, _ in ev})}
    out = {
        "ground_wait_arm": over(lambda e: e["sub"] == 3 and not e["disarm"]),
        "ground_wait_disarm": over(lambda e: e["sub"] == 3 and e["disarm"]),
        "air_wait_arm": over(lambda e: e["sub"] == 4 and not e["disarm"]),
        "air_wait_disarm": over(lambda e: e["sub"] == 4 and e["disarm"]),
        "loop": over(lambda e: e["sub"] == 2),
        "loop_unlimited": over(lambda e: e["sub"] == 2 and e["limit_unbounded"]),
        "store": over(lambda e: e["sub"] == 19),
        "stored_jump": over(lambda e: e["sub"] == 20),
        "hold_release": over(lambda e: e["kind"] == HOLD_RELEASE),
    }
    anims = [a for c in table["characters"] for a in c["anims"]]
    out["end_keys"] = {"anims": sum(bool(a["ends"]) for a in anims),
                       "events": sum(len(a["ends"]) for a in anims)}
    return out


def dump(table: dict) -> str:
    """Sorted keys; each event, marker map and small list on one line."""
    rows = {}

    def mark(obj, key=None):
        if isinstance(obj, dict) and "sub" in obj and "raw" in obj \
                or isinstance(obj, dict) and key == "markers" \
                or isinstance(obj, dict) and "source" in obj \
                or isinstance(obj, dict) and "status" in obj and "file" in obj \
                or isinstance(obj, list) and obj and all(isinstance(v, (int, str)) for v in obj) \
                and key in ("button_mask", "button_held_mask", "directions", "direction_marker_table"):
            k = f"@@row{len(rows)}@@"
            rows[k] = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            return k
        if isinstance(obj, dict):
            if key == "layout" or key == "sites":
                return {k: mark_inline(v) for k, v in obj.items()}
            return {k: mark(v, k) for k, v in obj.items()}
        if isinstance(obj, list):
            return [mark(v, key) for v in obj]
        return obj

    def mark_inline(obj):
        k = f"@@row{len(rows)}@@"
        rows[k] = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return k

    text = json.dumps(mark(table), indent=1, ensure_ascii=False, sort_keys=True)
    for k, v in rows.items():
        text = text.replace(f'"{k}"', v)
    return text + "\n"


def render_md(table: dict) -> str:
    rows = summary(table)
    mash_total = sum(r["mash"] for r in rows)
    chars_mash = [r for r in rows if r["mash"]]
    L = [
        "# Mash table: tap-extendable moves for every character",
        "",
        "Generated by `scripts/analysis/mash_table.py build`; do not edit. "
        "`python -B scripts/analysis/mash_table.py check` verifies freshness. Machine-readable copy:",
        "[mash-table.json](mash-table.json). Static: read from each character's motion table and ov6",
        "disassembly, no emulator.",
        "",
        "A mash move is an animation with a NoteTrack event that counts presses of a button in the input",
        "history and branches (ov6 op 0 sub 0 or sub 18). Sub 1 (hold), sub 23 (direction), sub 5",
        "(contact), sub 9 (counter) and sub 14 (deck count) are other input or state branches. "
        "`input_conditional`",
        "includes those state branches. Subs 2, 3, 4, 19 and 20 (loop, ground wait, air",
        "wait, store, stored jump) do not read the pad; they are decoded here because they move the same",
        "playhead (see Event kinds).",
        "",
        "## Field layout (op 0, `ev` = event bytes, `ev[0]` = sub, `ev[1]` = op = 0)",
        "",
        "| sub | kind | handler | fields |",
        "|---|---|---|---|",
    ]
    f = table["code_facts"]
    for sub in ("0", "18", "1", "23", "2", "3", "4", "19", "20"):
        lay = f["layout"][sub]
        cols = ", ".join(f"`{n}` ev[{o}] ({f['sites'][sub][n]})" for n, (_k, o) in lay.items()) \
            or "(no event byte read)"
        name = KINDS[int(sub)] + (f" / {HOLD_RELEASE}" if sub == "1" else "")
        L.append(f"| {sub} | {name} | {f['sub_handler'][sub]} | {cols} |")
    for sub in E.BRANCH_KINDS:
        L.append(f"| {sub} | {KINDS[sub]} | {f['sub_handler'][str(sub)]} | "
                 "STATIC: `anim_events.decode_branch` / `resolve_branch` |")
    L += [
        "",
        f"Button index into the table at {f['button_table']}: edge masks {[hex(m) for m in f['button_mask']]}"
        f" (held masks {[hex(m) for m in f['button_held_mask']]}). Names: idx 2 = X, idx 1 = Y (inferred);"
        " idx 0 = B and idx 3 = SELECT (the ground move reader maps 0x80 to the B moves and 0x1000 to the"
        " Ultimate Action, id 11). A marker is a frame of the anim's `Marker` track. The counter (fn 0x021561A8)"
        " bumps on every evaluation of a limited event, pressed or not; the (limit+1)th evaluation is blocked and"
        " resets it to 0; a limit of -1 is unlimited and does not bump. Only ov6 writes the byte (obj+0xA2), so"
        " every limited event of an anim shares it (Train's two events on 0x21 share one count).",
        "",
        "## Press counting",
        "",
        "Counter 0x021613C4 over the history updater 0x02161148. The input history is a ring of 16 segments,"
        " each a run of an unchanged input word with its stored duration (length - 1), plus the current word"
        " and its duration. An edge (the button's edge mask above) counts if its age is at most the window,"
        " where age counts only the ticks on which the word stayed unchanged: the raw age minus the number of"
        " word changes since the edge. A current word older than the window counts nothing. The history runs"
        " continuously across moves, so presses from before the move count. Facing is not a bit of the word:"
        " when the fighter faces left the updater swaps the LEFT and RIGHT bits (4 and 8), so a turn is a word"
        " change only while a horizontal is held. Directions are held-only bits; the shoulder bits (0x4000,"
        " 0x8000) are edge-only. A run's duration rolls over at 600. The updater runs before the check in the"
        " same tick. This reproduces all 35 committed Kakashi side Y trials of wmqi2-guard-2026-09-22 (31"
        " distinct tap schedules in `logs/mash_summary.json`) and the historical +4,+12 row. The 15 review"
        " cases (14 of those schedules plus the historical row) fit 15 of 15; counting plain edges in the last"
        " `window` elapsed ticks fits 11 of 15. A jump queued by an event lands on the next tick, so a loop"
        " adds (check - marker + 1) ticks. Sub 0 returns before the counter when [obj+0x78] is 0.",
        "",
        "## Event kinds",
        "",
        "Op 0 events of these subs are decoded (rows in the JSON; fields in the layout table). All are measured"
        " bytes at measured offsets; the meaning is read from the handler code unless marked.",
        "",
        "- **loop** (sub 2, 0x021559C0): an unconditional jump to Marker ev[2] through the shared counter with"
        " limit ev[3] (-1 = unlimited, no bump). It queues on slot 6 (queue kind 0, `slot_for_kind`).",
        "- **ground_wait** (sub 3, 0x02155CAC): arms slot 0 with queue kind 2 and Marker ev[2]; ev[2] = -1"
        " (`disarm`) empties it. Each callback polls slot 0 first (slot loop 0x02155700); handler 0x021562E8"
        " returns 1 iff `[[obj+0x7C]+0x10]+0x78` bit 0x02 (grounded). Grounded: jump to the armed marker from"
        " any frame, slot 0 empties, and the slot-6 jump queued the tick before is dropped. Not grounded: the"
        " queued slot-6 jump applies. Eve 0x2c: arm Marker 9 (f66) at f62, loop to Marker 8 (f62) at f65,"
        " disarm at f66.",
        "- **air_wait** (sub 4, 0x02155D00): the same slot 0 with queue kind 4, whose handler (0x02156358)"
        " returns 1 iff NOT grounded. Decoded, not modeled.",
        "- **counter_wait** (sub 9, 0x02155DB8): STATIC: queues kind 9 in slot 2 with signed Marker ev[2];"
        " -1 disarms. Poll 0x021564E8 tests ColPrm+0x40 & 0x20000. Kenshin rk_b_01 anim 0x2a arms"
        " marker 1 at f6, targets f47 and disarms at f47. The rec-7 counter box is active f6-22;"
        " the armed wait is not an invulnerability window. Decoded data only, not modeled in mash_path.py."
        " See p230.",
        "- **contact_wait** (sub 5, 0x02155D3C): STATIC: arms a marker jump on contact; marker -1"
        " disarms. `marker_frame` is the resolved target, null for disarm or an absent marker.",
        "- **deck_count_branch** (sub 14, 0x02155E90): STATIC: query 0x42 selects the first matching"
        " `tiers` entry in descending `min_count` order. Each entry has `marker` and resolved `frame`;"
        " no matching threshold falls through. Both branch decoders come from `anim_events.py`."
        " See [the static branch analysis](../research/2026-10-15-taikoubou-6kx-branches.md)."
        " UNMEASURED: live contact conditions and deck-count behavior. Neither branch is modeled in"
        " `mash_path.py`.",
        "- **hold_release** (sub 1 with no hold tier set, 0x02155B04): " + CORE_HOLD_RELEASE +
        " Tiered sub 1 events keep the kind `hold_tiers` (a lead).",
        "- **store** (sub 19, 0x021560EC): writes ev[2] (signed) to ctrl+0xA3. **stored_jump** (sub 20,"
        " 0x021560F8): if ctrl+0xA3 is not -1, queue a kind-0 jump to that Marker and reset it to -1 (also when"
        " the anim lacks the marker). The event bytes are recorded here only; `targets` lists every marker of"
        " the anim, and the join to stored values belongs to the UA scanner. `mash_path.simulate(stored=v)`"
        " models the read (a MashEvent of kind `stored_jump` with `targets`): it consumes `v` on its first"
        " pass and jumps if `v` is a target.",
        "- **ends** (op 3 sub 1, 0x0215693C): per anim, the frames of end keys; it sets ctrl+0x90 |= 0x10000000.",
        "",
        "## Reference model",
        "",
        "`scripts/analysis/mash_path.py` is a deterministic simulator of the rules above: from an anim's mash"
        " events (this table), its frame count and an input word per tick it returns the playhead frame per"
        " elapsed tick, the jumps taken, the idle tick, and the tick on which each box key frame is entered with"
        " its contact tick. `scripts/tests/test_mash_path.py` pins it against the Kakashi trials, Eve k4/k5 (with the"
        " landing) and Train's shared counter.",
        "",
        "- Idle: `idle_tick = M_IDLE + (elapsed - playhead)` with `M_IDLE = frames + 3` for a grounded move."
        " Each loop pushes idle later (Eve k4: 42, 55, 68).",
        "- Per tick: if slot 0 is armed and `t >= grounded_from`, the playhead goes to the armed frame, slot 0"
        " empties and a pending slot-6 jump is dropped; otherwise the pending jump applies. Events run, then"
        " the playhead advances by 1 (a jump queued on tick t lands on t + 1).",
        "- **TUNING, contact on a jump landing** (5 of 5 cases): a box key entered on tick t touches on t + 1,"
        " except that when the jump target is not check + 1, the box keyed at the target frame touches with"
        " delay 0. Eve k4 contacts at +12, +16, +20, +24, +29, +33, +37, +42, +46, +52 (24 and 37 are the"
        " landings); k5 unmashed 276 at +0; k5's adjacent jumps f19 to f20 and f25 to f26 stay +1.",
        "- **Jump landing (static RE, why the delay is 0)**: a jump queued on tick t lands on tick t + 1."
        " NoteTrack (task key 0x86000, callback 0x02155688) applies the queued jump through the motion"
        " controller's vtable[0xEC] (0x0201BFA0), which reaches setFrame (0x0201F9B8). setFrame returns early"
        " when the target equals the current frame; otherwise it stores the frame and dispatches every"
        " frame-keyed track through vtable[0xCC] (0x0201F734) at once, so the hit type (CollisionType listener"
        " 0x0207A2F4), enable, rect, hurt box and sprite all change before the collision driver (key 0x9E000,"
        " 0x0207F480) runs in the same tick: contact delay 0. A normal advance (Step 0x0201BDEC) only arms a"
        " pending-dispatch flag; Tick (0x0201C118) dispatches it later, after collision, so the box is first"
        " seen one tick later: +1. An adjacent jump (target = check + 1) is a normal advance (+1). The"
        " Tick-after-collision placement is inferred, not found by a caller search; the rule fits the 5 cases"
        " above.",
        "- **TUNING, history scope**: the ring is modeled as one history per fighter that runs across"
        " moves. Whether the native history is per fighter or per team is not tested (Kakashi trials ran"
        " one active fighter).",
        "- **Ground wait (Eve k5 up X, Train air Y)**: the hop's 2 to 5 tick idle residual is the sub 3 /"
        " sub 2 pair in the anim (Event kinds). `simulate(..., grounded_from=L + 1)` over `events_from_row(row, waits=True)` reproduces all 8 measured"
        " idles for 2 to 9 hits (landing ticks 31, 39, 45, 52, 58, 64, 70, 76 give idles 53, 61, 67, 74, 80,"
        " 86, 92, 98; E3b capture, docs/research/feel-captures/2026-10-12-eve-mash/compare.json). The landing"
        " tick is an input, not derived: the model has no physics. With no landing given the wait is not"
        " modeled (the arms and the wait loop are skipped), which gives 51 unmashed and 81 all-true, the old"
        " numbers. Not reproduced: air wait (sub 4) is decoded but not simulated; a sub 2 or sub 3 whose marker"
        " is absent from the anim has no frame and is left out of the model; the landing of Train air Y needs"
        " its own capture.",
        "- **End keys**: a move ends 2 ticks after the playhead reaches the first end key (op 3 sub 1,"
        " `ends` per anim), else at frames + 3. Train side Y (key f49) idles at 51, up Y (f43) at 45, air Y"
        " (f58) at 60, all measured; `mash_path.end_idle` computes it. The five measured idles behind the"
        " 5 of 5 grade note: Train side Y 51 = 49+2, up Y 45 = 43+2, air Y 60 = 58+2, Yusuke side Y 53 = 51+2,"
        " Kakashi UA 60 = (34 + 24 loop frames) + 2.",
        "",
        "Grades: bytes, frames, offsets and marker frames are measured; what a field means is inferred from",
        "the handler code; sub 1 and sub 23 decodes are leads. See `grade_notes` in the JSON.",
        "",
        f"## Cast summary ({mash_total} mash animations on {len(chars_mash)} of {len(rows)} characters)",
        "",
        "`conf` marks an independent confirmation (guide, capture or owner) recorded in the JSON; the rest are new.",
        "`other` counts the animations with hold (sub 1), contact (sub 5), deck-count (sub 14) or"
        " direction (sub 23) events and no press-count event (sub 0 or 18).",
        "`wait` counts the animations that arm a ground wait (sub 3).",
        "",
        "Counts of the other kinds over the cast (events / animations / characters):",
        "",
        "| kind | events | anims | chars |",
        "|---|---|---|---|",
    ] + [f"| {k} | {v['events']} | {v['anims']} | {v.get('characters', '-')} |"
         for k, v in counts(table).items()] + [
        "",
        f"`end_keys` counts only the animations that have a row above ({counts(table)['end_keys']['events']} "
        f"end keys on {counts(table)['end_keys']['anims']} rows). Cast-wide, op 3 sub 1 has "
        f"{table['end_keys_cast']['events']} events on {table['end_keys_cast']['anims']} animations "
        "(every SP01 node of every member; see the end-key idle rule in Reference model).",
        "",
        "| prefix | name | mash | other | wait | buttons | mash moves |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if not (r["mash"] or r["other"] or r["ground_wait"] or r["error"]):
            continue
        moves = "; ".join(m + (" conf" if m.split("[")[1].rstrip("]") in r["confirmed"] else "")
                          for m in r["moves"]) or "-"
        L.append(f"| {r['prefix']} | {r['names']} | {r['mash']} | {r['other']} | {r['ground_wait']} | "
                 f"{', '.join(r['buttons']) or '-'} | {moves}{' ERROR ' + r['error'] if r['error'] else ''} |")
    quiet = [r["prefix"] for r in rows if not (r["mash"] or r["other"] or r["ground_wait"] or r["error"])]
    L += ["", f"No input-conditional or ground-wait events: {', '.join(quiet) or 'none'}.", ""]
    g = table["guide_check"]
    n = {k: sum(r["status"] == k for r in g) for k in ("flagged", "other_event", "not_found", "unmapped", "not_a_move")}
    L += [
        "## Guide cross-check",
        "",
        "The GameFAQs extracts tag moves `mash-extend` (docs/research/gamefaqs-movesets). Joined to the",
        "scanner by character and move input (X and up X in any koma size):",
        f"{n['flagged']} flagged, {n['other_event']} only a hold or direction event, "
        f"{n['not_found']} not found, {n['unmapped']} unmapped character, {n['not_a_move']} not a move input.",
        "",
        "| guide | input | name | status | detail |",
        "|---|---|---|---|---|",
    ]
    for r in g:
        if r["status"] == "flagged":
            continue
        detail = r.get("note") or ", ".join(r.get("matched") or []) or ", ".join(r["prefixes"])
        L.append(f"| {r['file']} | {r['input']} | {r['name'] or '-'} | {r['status']} | {detail} |")
    L += ["", "Flagged rows are listed as `guide` confirmations on the anim in the JSON.", ""]
    L += [
        "## Open questions",
        "",
        "- Franky Y, Vegeta X and Goku Kaio Ken are guide-tagged mash but have no NoteTrack input event (Franky's Y grows with the stored UA value, a stored jump, not a mash event).",
        "- The press counter 0x021613C4 also has two non-NoteTrack callers (functions 0x02158B20 and 0x0215D564),"
        " so code-driven mash isn't covered by this scan.",
        "- Anims 0x2f-0x31 carry mash events but have no move label.",
        "- Move labels come from the shared ov6 move table and are measured only for Kakashi and Yusuke"
        " (anim-timing.json). Yusuke side Y plays 0x28, not the table's 0x21, so other fighters may be"
        " remapped too. Ids 13 and 14 take their anim from a per-fighter byte that wasn't read.",
        "",
    ]
    return "\n".join(L)


def show(char: dict) -> str:
    out = [char["prefix"] + " " + (", ".join(f"{n['name']} (chr_b {n['chr_b']})" for n in char["names"])
                                   or "(no name)")]
    for a in char["anims"]:
        out.append(f"  anim {a['anim']} {a['move'] or '-'} {'MASH' if a['mash'] else ''} markers {a['markers']}")
        for e in a["events"]:
            out.append(f"     f{e['frame']:>3} sub{e['sub']:>2} {e['kind']:<10} {e['raw']}")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="write docs/rebuild/mash-table.json and .md")
    sub.add_parser("check", help="exit 0 iff the committed files equal a fresh build")
    s = sub.add_parser("show", help="print one character's events")
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
