"""Per-character moveset mapper: drive every base input and summarise each hit.

Built for `jus-kakashi-moveset-map-33lu`; the roster campaign
(`jus-roster-moveset-campaign-69it`) reuses it for the other 69 characters, so
everything character-specific lives in data, not code:

  * `MOVES` -- move name -> input recipe (approach, attack, mash, tail).
    Directions are written facing-relative (`SIDE`, `BACK`); `--facing`
    turns them into LEFT/RIGHT for the state you are driving.
  * `ADDRESSES` -- one entry per savestate family. Every `pc-*` Dark
    Tournament state shares the `pc` entry (HANDOFF "Session-local values").
    Absolute addresses only: the `[[obj+0x1a8]+0x10]` chain reads garbage on
    the victim object in these states, so `M` is given directly.

One move = one `state load` + one plan, so every measurement starts from the
same frame. Logs, plans and summaries are written side by side under
`--outdir`; the per-frame log is gzipped JSONL and is meant to be read by
`summ`, never by eye.

CLI
---
    # list the move table (no emulator needed)
    python3 moveset_map.py moves

    # one move, or several, or all of them
    python3 moveset_map.py run --state pc-kakashi-npc-jotaro-dark-tournament \
        --outdir docs/research/feel-captures/kakashi-2026-09-03 \
        --facing LEFT --chr-b 23 --move B --move sideB
    python3 moveset_map.py run ... --all

    # re-summarise an already captured log (cheap, no emulator)
    python3 moveset_map.py summ --outdir <dir> --name B
    python3 moveset_map.py table --outdir <dir>          # markdown rows

Options worth knowing:

  --facing L/R    which way the attacker must face to reach the victim.
  --approach N    frames of `--facing` held before the attack (closes distance).
                  Negative N walks the other way, to open distance past the
                  state's own starting gap.
  --guard         label the capture `-guard` and expect a blocked hit: the
                  summary then reports guard-gauge damage instead of HP damage.
                  Set COM設定 = ガード in the pause menu first (START, DOWN, A,
                  A, START as separate 1-frame plans) -- this flag does not do
                  it for you.
  --tail N        frames logged after the last input (default 180).
  --records       join each hit to the authored records of `--chr-b` via
                  scripts/analysis/move_records.py (static side of the map).
  --elements [N]  also watch N (default 6) slots of the element array at
                  0x0220C0E8 + 0x40*i (entities.md 5.5), which is where a
                  summoner's spawned creatures live. The fighter watches are
                  narrowed to their read fields to pay for it, so the byte
                  budget still balances; the narrow bases are written into the
                  capture's meta as `watch_bases` and captures without that
                  key (every pre-2026-09-03 Kakashi log) keep the wide layout.
                  The summary then carries `elem_tracks` (spawn/despawn,
                  anchor vs traveller) and `hit_owners` (nearest owner of each
                  hitbox, by proximity -- there is no runtime owner field).

Hazards this script already works around (all from HANDOFF):
  * a plan carrying `load_state` kills the bridge -- the load is a separate
    `jusemu.py state load` call;
  * training-mode auto-heal makes before/after diffs lie -- damage is the
    minimum of the per-frame dip, never a difference of two reads;
  * `jusemu.py peek` returns a scalar for len 1/2/4 and a byte array otherwise.
"""
import argparse
import gzip
import json
import os
import struct
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JUSEMU = os.path.join(REPO, "scripts", "emu", "jusemu.py")

# ---------------------------------------------------------------- addresses
# One entry per savestate family. All absolute; see the module docstring.
ADDRESSES = {
    "pc": {
        "a_obj": 0x02228E80,   # P1 fighter object: +0x18 state, +0x72 anim frame
        "a_elem": 0x0220C068,  # +0xC x, +0x10 y, +0x24 vx, +0x26 vy (raw/256 px)
        "a_M": 0x0220F30C,     # P1 ColPrm scratch: +0x78 ground/air, +0x17c HP
        "a_hp": 0x021DF1D4,    # P1 active-slot current HP (u16, raw/64)
        # Victim object is 0x0224EF00 in the pc-*-npc-jotaro-* states, NOT the
        # 0x02230D60 of the pc-kenshin-* states -- read it from the fighter
        # table 0x021DEB3C slot 1 for any new state (jus-kakashi-moveset-map-33lu).
        "v_obj": 0x0224EF00,
        "v_elem": 0x0220C0A8,
        "v_M": 0x0220F494,
        "v_hp": 0x021DF7F0,
        # Opponent deck slot array, stride 0x50 from the CURRENT-HP address:
        # +0x00 current HP, +0x25 bit 0 the active flag, +0x29 the chr_b
        # (runtime-report-5 2). Watched so a forced switch (Kakashi down B)
        # is visible instead of looking like huge damage.
        "v_slots": 0x021DF7F0,
        # SP: the player slot is 0x61C bytes and starts at HP-0x6C, so P1 is
        # 0x021DF168 and the SP total of guard-sp.md 1.4 (slot+0x5C8) is
        # 0x021DF730. Watched with the 8 bytes before it, which hold a
        # per-hit accumulator (jus-kakashi-moveset-map-33lu phase 2).
        "a_sp": 0x021DF730,
        "a_spacc": 0x021DF728,
        # Element array of entities.md 5.5: 0x0220C0E8 + 0x40*i. Slots 0 and 1
        # of the same array (0x0220C068, 0x0220C0A8) are the two fighters, so
        # the spawn slots start here. Only read with `--elements N`.
        "elems": 0x0220C0E8,
    },
    # pc-taikoubou-npc-jotaro-dark-tournament (jus-4ocm). Same P1 object, same
    # M pair and same HP records as the Kakashi state; the VICTIM OBJECT IS
    # DIFFERENT (0x02246A20, from fighter table 0x021DEB3C slot 1) -- resolve
    # it per state, never copy it.
    "pc_taikoubou": {
        "a_obj": 0x02228E80,
        "a_elem": 0x0220C068,
        "a_M": 0x0220F30C,
        "a_hp": 0x021DF1D4,
        "v_obj": 0x02246A20,
        "v_elem": 0x0220C0A8,
        "v_M": 0x0220F494,
        "v_hp": 0x021DF7F0,
        "v_slots": 0x021DF7F0,
        "a_sp": 0x021DF730,
        "a_spacc": 0x021DF728,
        "elems": 0x0220C0E8,
    },
    # pc-sasuke / pc-eve / pc-yohswan -npc-jotaro-dark-tournament: one deck
    # [21 Sasuke 184, 26 Yoh-White-Swan 192, 37 Eve 128, 23 help 16] with a
    # different slot active per state, so all three share these addresses.
    # VICTIM OBJECT 0x0222CFE0 (fighter table 0x021DEB3C slot 1) -- a third
    # value in the same pc-*-npc-jotaro family (jus-knockback-pop-spot-check-m4uy).
    "pc_sasuke": {
        "a_obj": 0x02228E80,
        "a_elem": 0x0220C068,
        "a_M": 0x0220F30C,
        "a_hp": 0x021DF1D4,
        "v_obj": 0x0222CFE0,
        "v_elem": 0x0220C0A8,
        "v_M": 0x0220F494,
        "v_hp": 0x021DF7F0,
        "v_slots": 0x021DF7F0,
        "a_sp": 0x021DF730,
        "a_spacc": 0x021DF728,
        "elems": 0x0220C0E8,
    },
    # pc-kenshin-npc-luffy-dark-tournament (and the other pc-kenshin-* JJ
    # states): victim object 0x02230D60.
    "pc_kenshin": {
        "a_obj": 0x02228E80,
        "a_elem": 0x0220C068,
        "a_M": 0x0220F30C,
        "a_hp": 0x021DF1D4,
        "v_obj": 0x02230D60,
        "v_elem": 0x0220C0A8,
        "v_M": 0x0220F494,
        "v_hp": 0x021DF7F0,
        "v_slots": 0x021DF7F0,
        "a_sp": 0x021DF730,
        "a_spacc": 0x021DF728,
        "elems": 0x0220C0E8,
    },
    # pc-raoh-npc-luffy-j-arena. J Arena moves EVERY fighter address and both
    # ColPrm scratch pointers; only the deck HP records and the element array
    # stay put. Resolved live 2026-09-03 (jus-knockback-pop-spot-check-m4uy).
    # J Arena also SHIFTS THE ELEMENT ARRAY: slots 0-5 (0x0220C068 ..
    # 0x0220C1A8) are six never-moving stage markers (x 256/767 at y
    # 640/704/768, the three platform rows), and the two FIGHTERS are slots 6
    # and 7 -- P1 0x0220C1E8 (Raoh, x 416) and the victim 0x0220C228 (Luffy,
    # x 608), 192 px apart, not the 511 px the marker pair suggests. Proven by
    # holding RIGHT for 40 frames and watching slot 6 move while slot 7 stood
    # still. A worker who copies the `pc` element addresses here gets a frozen
    # 256.0/767.0 pair and every distance is wrong.
    "pc_raoh_jarena": {
        "a_obj": 0x02228A00,
        "a_elem": 0x0220C1E8,
        "a_M": 0x0220FC3C,
        "a_hp": 0x021DF1D4,
        "v_obj": 0x02230BA0,
        "v_elem": 0x0220C228,
        "v_M": 0x0220FDC4,
        "v_hp": 0x021DF7F0,
        "v_slots": 0x021DF7F0,
        "a_sp": 0x021DF730,
        "a_spacc": 0x021DF728,
        "elems": 0x0220C268,
    },
}

# How many element slots `--elements` watches by default.
DEFAULT_ELEM_SLOTS = 6

# Field offsets, shared by both fighters.
O_STATE = 0x18       # obj+0x18 state code (physics.md 4.5 enum)
# obj+0x72 (u16) is the input sampler's hold counter: sampler calls since the
# input word last changed (ov6 0x02161148, capped at 600). It is NOT animation
# frames (docs/rebuild/anim-timing.md section 7, jus-wmqi.6.4).
O_ANIMF = 0x72
O_HANDLER = 0xFC     # obj+0xFC reaction handler pointer
O_REACT = 0x100      # obj+0x100 reaction id (copied from M+0x16C)
O_GAUGE = 0x102      # obj+0x102 guard gauge current / +0x104 max
O_LANDREC = 0x110    # obj+0x110 landing-recovery timer
O_DMG = 0x112        # obj+0x112 last hit's damage, whole units
O_HITSTUN = 0x115    # obj+0x115 hitstun whole-frame byte
M_GROUND = 0x78      # M+0x78 0x22 grounded / 0x24,0x40,0xC0 launched
M_KBX = 0x148        # M+0x148 / +0x14A staged knockback X/Y
M_KBY = 0x14A
M_HITTYPE = 0x16C    # M+0x16C max-latched moveData[+1]
M_STUNBASE = 0x171   # M+0x171 hitstun base (60 only on a guard break)
M_HP = 0x17C         # M+0x17c HP, raw/64

# ------------------------------------------------------------------- moves
# Each recipe: attack buttons, and optional approach/mash/tail overrides.
#   dirs: SIDE = towards the victim, BACK = away, UP/DOWN literal.
#   pre:  extra segments before the attack, e.g. a jump or a setup move.
#   mash: [button, period, count] repeated taps after the attack input.
MOVES = {
    "B":        {"attack": ["B"]},
    "sideB":    {"attack": ["SIDE", "B"]},
    "upB":      {"attack": ["UP", "B"]},
    "downB":    {"attack": ["DOWN", "B"]},
    "airB":     {"attack": ["B"], "pre": [("A", 0, 1)], "attack_at": 14},
    "Y":        {"attack": ["Y"]},
    "sideY":    {"attack": ["SIDE", "Y"]},
    "sideY_mashed": {"attack": ["SIDE", "Y"], "mash": ["Y", 4, 10]},
    "upY":      {"attack": ["UP", "Y"]},
    # Owner 2026-09-03: up Y only connects on a victim who is already
    # airborne, so the hit data comes from side B (the pop) into up Y.
    "sideB_upY": {"attack": ["SIDE", "B"], "pre": [], "then": [("UP+Y", 26, 3)]},
    "downY":    {"attack": ["DOWN", "Y"]},
    "airY":     {"attack": ["Y"], "pre": [("A", 0, 1)], "attack_at": 14},
    "SELECT":   {"attack": ["SELECT"]},
    # X specials (phase 2 of jus-kakashi-moveset-map-33lu). `X_held` holds the
    # button for 60 frames to catch a charge; ATTACK_HOLD covers the taps.
    "X":        {"attack": ["X"]},
    "sideX":    {"attack": ["SIDE", "X"]},
    "upX":      {"attack": ["UP", "X"]},
    "downX":    {"attack": ["DOWN", "X"]},
    "airX":     {"attack": ["X"], "pre": [("A", 0, 1)], "attack_at": 14},
    "X_held":   {"attack": ["X"], "hold": 60},
    # Taikoubou's 4-koma up X is a charge move ("damage scales from a light
    # charge to a max charge", taikoubou--46293.json), so it needs a tap, a
    # short hold and a long hold. Generic: any charge special can reuse these.
    "upX_held":  {"attack": ["UP", "X"], "hold": 60},
    "upX_held30": {"attack": ["UP", "X"], "hold": 30},
    # Muhyo's forward Y is held to make the monster emerge farther away
    # (OWNER-NOTES.md), so the same tap / 30 f / 60 f ladder is needed on a
    # directional heavy (jus-knockback-pop-spot-check-m4uy).
    "sideY_held30": {"attack": ["SIDE", "Y"], "hold": 30},
    "sideY_held60": {"attack": ["SIDE", "Y"], "hold": 60},
    "upX_held120": {"attack": ["UP", "X"], "hold": 120},
    # Guide combo starters (B -> up B, B -> side B) and the pop-then-up-Y
    # sequence that is the only way an up-Y that only hits airborne victims
    # can be measured.
    "B_upB":    {"attack": ["B"], "then": [("UP+B", 20, 3)]},
    "B_sideB":  {"attack": ["B"], "then": [("SIDE+B", 20, 3)]},
    "upB_upY":  {"attack": ["UP", "B"], "then": [("UP+Y", 40, 3)]},
    # Muhyo's up Y is an anti-air that whiffs a standing victim (guide, and
    # confirmed 2026-09-03), and his side Y is the pop that gets the victim
    # airborne, so this is the only way to measure it.
    "sideY_upY": {"attack": ["SIDE", "Y"], "then": [("UP+Y", 30, 3)]},
    "sideY_upY40": {"attack": ["SIDE", "Y"], "then": [("UP+Y", 40, 3)]},
    "sideY_long_upY": {"pre": [("SIDE", 0, 8)], "attack": ["SIDE", "Y"],
                       "attack_at": 2, "then": [("UP+Y", 30, 3)]},
    "sideY_long_upY40": {"pre": [("SIDE", 0, 8)], "attack": ["SIDE", "Y"],
                         "attack_at": 2, "then": [("UP+Y", 40, 3)]},
    "sideY_upY50": {"attack": ["SIDE", "Y"], "then": [("UP+Y", 50, 3)]},
    # A negative `--approach` backs away, which leaves the attacker facing the
    # WRONG way, so a directional attack after it reads as back+button. These
    # two spend 8 frames walking forward first purely to turn around, then
    # fire; use them with `--approach -N` to reach a range the state's own
    # geometry cannot.
    "sideY_long": {"pre": [("SIDE", 0, 8)], "attack": ["SIDE", "Y"],
                   "attack_at": 2},
    "sideB_long": {"pre": [("SIDE", 0, 8)], "attack": ["SIDE", "B"],
                   "attack_at": 2},
    # Held side Y at a range the state's own geometry cannot reach: Muhyo's
    # held forward Y sends the monster ~60 px PAST its emergence point, so the
    # attacker has to stand ~66 px farther back than the state starts him
    # (jus-knockback-pop-spot-check-m4uy).
    "sideY_long_held30": {"pre": [("SIDE", 0, 8)], "attack": ["SIDE", "Y"],
                          "attack_at": 2, "hold": 30},
    "sideY_long_held60": {"pre": [("SIDE", 0, 8)], "attack": ["SIDE", "Y"],
                          "attack_at": 2, "hold": 60},
    # Summoner check (jus-4ocm): fire a move whose spawned element is still
    # alive, then a plain B, so the summary carries both a "summon present"
    # B and the element track that proves it was out.
    "upX_then_B": {"attack": ["UP", "X"], "then": [("B", 90, 3)]},
    "downY_then_B": {"attack": ["DOWN", "Y"], "then": [("B", 40, 3)]},
    # X pressed at the apex instead of just after take-off, to rule out a
    # timing artifact behind "air X does nothing".
    "airX_late": {"attack": ["X"], "pre": [("A", 0, 1)], "attack_at": 24},
    # down B forces the opponent to switch character; firing X afterwards
    # shows whether SP is read off the same (per-player, deck-shared) word.
    "downB_X":  {"attack": ["DOWN", "B"], "then": [("X", 60, 3)]},
    # Sasuke (jus-ssk6). OWNER-NOTES.md: "Up B: a two-hit rising kick. The
    # second hit can be cancelled into a different move by inputting another
    # action before the second kick fires (up B into X, up B into Y)." Measured
    # up B lands hit 1 at rel 14 and hit 2 at rel 26, so the cancel window is
    # somewhere in 15..25; two timings each bracket it.
    "upB_X":    {"attack": ["UP", "B"], "then": [("X", 16, 3)]},
    "upB_X20":  {"attack": ["UP", "B"], "then": [("X", 20, 3)]},
    "upB_Y":    {"attack": ["UP", "B"], "then": [("Y", 16, 3)]},
    "upB_Y20":  {"attack": ["UP", "B"], "then": [("Y", 20, 3)]},
    # sasuke--46543.json combo "Select, X. 3 hits for 48 damage": the Ultimate
    # Action (replacement jutsu) into the Chidori.
    "SELECT_X": {"attack": ["SELECT"], "then": [("X", 30, 3)]},
    # sasuke--46543.json's "Basic Combo": B, B+forward, Y, Y+forward,
    # 8 hits / 42 damage.
    "combo_BsideBYsideY": {"attack": ["B"],
                           "then": [("SIDE+B", 20, 3), ("Y", 45, 3),
                                    ("SIDE+Y", 75, 3)]},
    # sasuke--46543.json marks down Y "charge" and X "Hold X to charge", so
    # both need a tap / short hold / long hold ladder.
    "downY_held30": {"attack": ["DOWN", "Y"], "hold": 30},
    "downY_held60": {"attack": ["DOWN", "Y"], "hold": 60},
    "X_held120": {"attack": ["X"], "hold": 120},
    # Double-tap dash (gap <= 10 frames), then attack out of the dash burst.
    # Keep the hold short: a full 12-frame dash runs Kakashi past the victim.
    "dashB":    {"attack": ["B"], "pre": [("SIDE", 0, 2), ("SIDE", 6, 5)],
                 "attack_at": 12},
    "dashY":    {"attack": ["Y"], "pre": [("SIDE", 0, 2), ("SIDE", 6, 5)],
                 "attack_at": 12},
    # ... and the same two braked one frame into the burst, for a state where
    # the full burst overshoots the victim.
    "dashB_early": {"attack": ["B"], "pre": [("SIDE", 0, 2), ("SIDE", 6, 1)],
                    "attack_at": 8},
    "dashY_early": {"attack": ["Y"], "pre": [("SIDE", 0, 2), ("SIDE", 6, 1)],
                    "attack_at": 8},
    # ... and braked with no hold at all, for a state where even `dashB_early`
    # overshoots (jus-ssk6: Sasuke's dash covers ~37 px from 18 px out).
    "dashB_brake": {"attack": ["B"], "pre": [("SIDE", 0, 2)], "attack_at": 4},
    "dashY_brake": {"attack": ["Y"], "pre": [("SIDE", 0, 2)], "attack_at": 4},
    # sasuke--46543.json's "Select, X" combo: the Ultimate Action holds state
    # 12 for 61 frames and swallows an X pressed inside it, so the X has to
    # come after the taunt ends (jus-ssk6).
    "SELECT_X70": {"attack": ["SELECT"], "then": [("X", 70, 3)]},
}

DEFAULT_TAIL = 180
DEFAULT_APPROACH = 26
ATTACK_HOLD = 3


# ------------------------------------------------------------------ plumbing
def emu(*a, timeout=400):
    r = subprocess.run(["python3", JUSEMU, *a], capture_output=True,
                       text=True, timeout=timeout)
    if r.returncode:
        raise SystemExit("jusemu %s failed:\n%s\n%s" % (a, r.stdout[-600:],
                                                        r.stderr[-600:]))
    return r.stdout


def peek(addr, n):
    """Bytes at addr. Handles jusemu's scalar-vs-array return."""
    v = json.loads(emu("peek", hex(addr), str(n)))["result"]["value"]
    if isinstance(v, list):
        return bytes(v)
    return struct.pack("<I", v & 0xFFFFFFFF)[:n]


def u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def s16(b, o):
    return struct.unpack_from("<h", b, o)[0]


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def s32(b, o):
    return struct.unpack_from("<i", b, o)[0]


# Where byte 0 of each watch sits inside its struct. The reader below asks for
# a field by its struct offset and subtracts the watch's base, so a watch can
# be narrowed without touching a single field offset.
#
# WIDE is the original Kakashi layout: 512 bytes over 15 watches, exactly the
# plan validator's budget, so it has no room for element slots. SLIM trims
# every watch to the bytes the summariser actually reads (258 bytes) and spends
# the rest on the element array. Old logs carry no `watch_bases` in their meta
# and fall back to WIDE, so every Kakashi capture still summarises byte for
# byte.
WIDE_BASES = {
    "a_obj": 0x00, "a_elem": 0x00, "a_M60": 0x60, "v_obj": 0x00,
    "v_objF": 0xF8, "v_elem": 0x00, "v_M60": 0x60, "v_M140": 0x140,
    "v_slot": 0x20,
}
SLIM_BASES = {
    "a_obj": 0x18, "a_elem": 0x0C, "a_M60": 0x78, "v_obj": 0x18,
    "v_objF": 0xFC, "v_elem": 0x0C, "v_M60": 0x78, "v_M140": 0x148,
    "v_slot": 0x25,
}
# name -> (base key, length) for the SLIM layout.
SLIM_LENS = {"a_obj": 0x5C, "a_elem": 0x08, "a_M60": 0x04, "v_obj": 0x04,
             "v_objF": 0x1A, "v_elem": 0x1C, "v_M60": 0x04, "v_M140": 0x38,
             "v_slot": 0x05}
WIDE_LENS = {"a_obj": 0x80, "a_elem": 0x30, "a_M60": 0x20, "v_obj": 0x20,
             "v_objF": 0x20, "v_elem": 0x40, "v_M60": 0x20, "v_M140": 0x40,
             "v_slot": 0x10}
# Bytes of each element slot: +0x00 the allocator link word, +0xC/+0x10 x/y,
# +0x24/+0x26 vx/vy.
ELEM_LEN = 0x28


def watches(A, elem_slots=0):
    """Per-frame watch list.

    `elem_slots` = 0 keeps the original 512-byte layout (Kakashi's). Any other
    value switches to the narrow layout and adds that many element slots of
    the `0x0220C0E8 + 0x40*i` array (entities.md 5.5), which is how a
    summoner's hitbox owner and summon lifetime become visible.
    """
    b = SLIM_BASES if elem_slots else WIDE_BASES
    ln = SLIM_LENS if elem_slots else WIDE_LENS
    ws = [
        {"name": "a_obj", "addr": A["a_obj"] + b["a_obj"], "len": ln["a_obj"]},
        {"name": "a_elem", "addr": A["a_elem"] + b["a_elem"],
         "len": ln["a_elem"]},
        {"name": "a_M60", "addr": A["a_M"] + b["a_M60"], "len": ln["a_M60"]},
        {"name": "a_hp", "addr": A["a_hp"], "len": 2},
        {"name": "v_obj", "addr": A["v_obj"] + b["v_obj"], "len": ln["v_obj"]},
        {"name": "v_objF", "addr": A["v_obj"] + b["v_objF"],
         "len": ln["v_objF"]},
        {"name": "v_elem", "addr": A["v_elem"] + b["v_elem"],
         "len": ln["v_elem"]},
        {"name": "v_M60", "addr": A["v_M"] + b["v_M60"], "len": ln["v_M60"]},
        {"name": "v_M140", "addr": A["v_M"] + b["v_M140"], "len": ln["v_M140"]},
        {"name": "v_hp", "addr": A["v_hp"], "len": 2},
        {"name": "a_sp", "addr": A["a_spacc"], "len": 0x0C},
    ] + [{"name": "v_slot%d" % i,
          "addr": A["v_slots"] + 0x50 * i + b["v_slot"], "len": ln["v_slot"]}
         for i in range(4)]
    for i in range(elem_slots):
        ws.append({"name": "el%d" % i, "addr": A["elems"] + 0x40 * i,
                   "len": ELEM_LEN})
    return ws


def expand(buttons, facing):
    """SIDE/BACK -> LEFT/RIGHT for this state's geometry."""
    back = "RIGHT" if facing == "LEFT" else "LEFT"
    out = []
    for b in buttons:
        for part in b.split("+"):
            out.append({"SIDE": facing, "BACK": back}.get(part, part))
    return out


def build_segments(recipe, facing, approach, primer=0):
    """Turn a recipe into sorted, non-overlapping plan segments.

    `primer` (frames) prepends a B press and delays the real attack by that
    many frames. The ガード CPU stands still until the first hit lands and only
    then holds guard, so a blocked-hit measurement needs one throwaway hit
    first (physics.md 4.5).
    """
    segs = []
    t = 0
    if approach:
        # A NEGATIVE approach walks BACK instead of forward, which is how you
        # reach a longer range than the state's own starting distance -- needed
        # by summoned allies that spawn ahead of the attacker and so have a
        # minimum range (jus-4ocm: Taikoubou's Y whiffs at 19 px and connects
        # at 58 px).
        n = abs(approach)
        back = "RIGHT" if facing == "LEFT" else "LEFT"
        segs.append({"from": 0, "to": n - 1,
                     "buttons": expand([facing if approach > 0 else back],
                                       facing)})
        t = n
    if primer:
        segs.append({"from": t, "to": t + 2, "buttons": ["B"]})
        t += primer
    for buttons, at, dur in recipe.get("pre", []):
        f = t + at
        segs.append({"from": f, "to": f + dur - 1,
                     "buttons": expand([buttons], facing)})
        t = max(t, f + dur)
    af = t + recipe.get("attack_at", 0)
    if af <= (segs[-1]["to"] if segs else -1):
        af = segs[-1]["to"] + 1
    hold = recipe.get("hold", ATTACK_HOLD)
    segs.append({"from": af, "to": af + hold - 1,
                 "buttons": expand(recipe["attack"], facing)})
    t = af + hold
    if "mash" in recipe:
        btn, period, count = recipe["mash"]
        for i in range(count):
            f = t + i * period
            segs.append({"from": f, "to": f + 1,
                         "buttons": expand([btn], facing)})
        t = t + count * period
    for buttons, at, dur in recipe.get("then", []):
        f = max(t, af + at)
        segs.append({"from": f, "to": f + dur - 1,
                     "buttons": expand([buttons], facing)})
        t = f + dur
    segs.sort(key=lambda s: s["from"])
    return segs, af


def run_move(name, state, recipe, A, outdir, facing, approach, tail, label,
             primer=0, elem_slots=0, pokes=()):
    segs, attack_frame = build_segments(recipe, facing, approach, primer)
    plan = {"name": label, "segments": segs, "tail_frames": tail,
            "watches": watches(A, elem_slots)}
    os.makedirs(outdir, exist_ok=True)
    ppath = os.path.join(outdir, label + ".plan.json")
    with open(ppath, "w") as f:
        json.dump(plan, f, indent=1)

    emu("state", "load", state)
    time.sleep(2.5)
    # Pokes go in AFTER the load and BEFORE the plan, because a plan that
    # carries `load_state` kills the bridge (HANDOFF). Used for the launcher
    # HP-band test: poke the victim's deck HP record to either side of 3/4,
    # 1/2 and 1/4 of max and repeat the same plan (physics.md 4.2).
    for addr, blob in pokes:
        emu("poke", hex(addr), blob.hex())
        time.sleep(0.2)
        got = peek(addr, len(blob))[:len(blob)]
        if got != blob:
            raise SystemExit("poke did not stick at %s: %s != %s"
                             % (hex(addr), got.hex(), blob.hex()))
    out = emu("run", ppath, "--timeout", "300")
    logline = [l for l in out.splitlines() if l.startswith("log:")]
    if not logline:
        raise SystemExit("plan produced no log:\n" + out[-800:])
    rows = [json.loads(l) for l in open(logline[0].split()[1])]
    gz = os.path.join(outdir, label + ".jsonl.gz")
    with gzip.open(gz, "wt") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    meta = {"move": name, "label": label, "state": state, "facing": facing,
            "pokes": [[hex(a), b.hex()] for a, b in pokes],
            "approach": approach, "attack_frame": attack_frame,
            "recipe": recipe, "primer": primer,
            "elem_slots": elem_slots,
            "watch_bases": SLIM_BASES if elem_slots else WIDE_BASES,
            "elem_base": hex(A["elems"]) if elem_slots else None,
            "addresses": {k: hex(v) for k, v in A.items()},
            "frames": len(rows), "plan": ppath}
    with open(os.path.join(outdir, label + ".meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return meta


# ---------------------------------------------------------------- summarise
def _buf(w, name):
    """A watch's bytes, whatever jusemu returned for it."""
    v = w[name]
    if isinstance(v, int):
        return struct.pack("<I", v & 0xFFFFFFFF)
    return bytes(v)


def frames_of(outdir, label, bases=None):
    """Per-frame rows. `bases` comes from the capture's meta (`watch_bases`);
    a capture written before the narrow layout existed has none and gets the
    original WIDE offsets."""
    b = bases or WIDE_BASES
    gz = os.path.join(outdir, label + ".jsonl.gz")
    fr = []
    for line in gzip.open(gz, "rt"):
        r = json.loads(line)
        w = r["w"]

        def sl(name, key):
            """Slice a watch so it can be indexed by struct offset."""
            return b"\0" * b[key] + _buf(w, name)

        a = sl("a_obj", "a_obj")
        ae = sl("a_elem", "a_elem")
        aM = sl("a_M60", "a_M60")
        vo = sl("v_obj", "v_obj")
        vf = sl("v_objF", "v_objF")
        ve = sl("v_elem", "v_elem")
        vM6 = sl("v_M60", "v_M60")
        vM1 = sl("v_M140", "v_M140")
        els = []
        for i in range(64):
            k = "el%d" % i
            if k not in w:
                break
            eb = _buf(w, k)
            els.append(dict(
                slot=i, link=u32(eb, 0),
                x=s32(eb, 0xC) / 256, y=s32(eb, 0x10) / 256,
                vx=s16(eb, 0x24), vy=s16(eb, 0x26)))
        fr.append(dict(
            elems=els,
            f=r["f"], fc=r["fc"],
            a_state=a[O_STATE], a_animf=u16(a, O_ANIMF),
            a_x=s32(ae, 0xC) / 256, a_y=s32(ae, 0x10) / 256,
            a_ground=aM[M_GROUND],
            a_hp=(w["a_hp"] if isinstance(w["a_hp"], int)
                  else u16(bytes(w["a_hp"]), 0)) / 64,
            v_state=vo[O_STATE],
            v_handler=u32(vf, O_HANDLER),
            v_react=u16(vf, O_REACT),
            v_gauge=u16(vf, O_GAUGE),
            v_gauge_max=u16(vf, O_GAUGE + 2),
            v_landrec=s16(vf, O_LANDREC),
            v_dmg=u16(vf, O_DMG),
            v_hitstun=vf[O_HITSTUN],
            v_x=s32(ve, 0xC) / 256, v_y=s32(ve, 0x10) / 256,
            v_vx=s16(ve, 0x24), v_vy=s16(ve, 0x26),
            v_ground=vM6[M_GROUND],
            v_kbx=s16(vM1, M_KBX), v_kby=s16(vM1, M_KBY),
            v_hittype=u16(vM1, M_HITTYPE),
            v_stunbase=vM1[M_STUNBASE],
            v_hp=u32(vM1, M_HP) / 64,
            # M+0x172 / +0x173 staged effect ids (guard-sp.md 1.5); +0x173 is
            # stored negated. 0 on both = no status dispatch.
            v_eff172=vM1[0x172], v_eff173=vM1[0x173],
            # SP total (slot+0x5C8) and the 8 bytes before it.
            a_sp=u16(bytes(w["a_sp"]), 0x08) if "a_sp" in w else None,
            a_spacc=u32(bytes(w["a_sp"]), 0x04) if "a_sp" in w else None,
            # Older captures (before the slot watches existed) lack these.
            v_active=[sl("v_slot%d" % i, "v_slot")[0x25] & 1
                      for i in range(4)] if "v_slot0" in w else [],
            v_chrb=[sl("v_slot%d" % i, "v_slot")[0x29] for i in range(4)]
            if "v_slot0" in w else [],
        ))
    return fr


def elem_tracks(fr, af):
    """Element-array lifetimes for a summoner's kit (entities.md 5.5).

    A free slot reads x = y = 0 (the allocator only links it through +0x00), so
    a slot counts as LIVE on the frames its position is non-zero. Per slot:
    spawn/despawn relative to the attack input, first and last position, peak
    speed, and whether it moved at all (anchor vs traveller).
    """
    if not fr or not fr[0]["elems"]:
        return []
    tracks = []
    n = len(fr[0]["elems"])
    for i in range(n):
        live = [r for r in fr if (r["elems"][i]["x"] or r["elems"][i]["y"])]
        if not live:
            continue
        # A slot can be reused inside one capture; split on gaps.
        runs, cur = [], [live[0]]
        for prev, r in zip(live, live[1:]):
            if r["f"] == prev["f"] + 1:
                cur.append(r)
            else:
                runs.append(cur)
                cur = [r]
        runs.append(cur)
        for run in runs:
            xs = [r["elems"][i]["x"] for r in run]
            ys = [r["elems"][i]["y"] for r in run]
            steps = [round(abs(b - a_), 2) for a_, b in zip(xs, xs[1:])]
            tracks.append(dict(
                slot=i, spawn=run[0]["f"] - af, despawn=run[-1]["f"] - af,
                frames=len(run),
                first=[round(xs[0], 2), round(ys[0], 2)],
                last=[round(xs[-1], 2), round(ys[-1], 2)],
                travel=round(max(xs) - min(xs), 2),
                rise=round(max(ys) - min(ys), 2),
                peak_px_per_frame=max(steps) if steps else 0.0,
                kind="anchor" if (max(steps) if steps else 0) < 0.5
                     else "traveller"))
    return sorted(tracks, key=lambda t: (t["spawn"], t["slot"]))


def hit_owner(fr, hit_frame, victim_x):
    """Who owned the hitbox: the attacker's own body or a spawned element.

    There is no runtime field naming the owner, so this is a proximity call:
    on the latch frame, report the attacker's distance to the victim and every
    live spawned element's distance, and name the nearest. Read it together
    with the element track -- an element that spawned before the hit and sits
    on the victim owned it.
    """
    row = next((r for r in fr if r["f"] == hit_frame), None)
    if row is None:
        return None
    cands = [("attacker", round(abs(row["a_x"] - victim_x), 2))]
    for e in row["elems"]:
        if e["x"] or e["y"]:
            cands.append(("el%d" % e["slot"], round(abs(e["x"] - victim_x), 2)))
    cands.sort(key=lambda c: c[1])
    return dict(nearest=cands[0][0], dists=cands)


def summarise(outdir, label, guard=False):
    meta = json.load(open(os.path.join(outdir, label + ".meta.json")))
    fr = frames_of(outdir, label, meta.get("watch_bases"))
    af = meta["attack_frame"]

    # The hit frame is the frame M+0x16C latches the attacker's moveData[+1]
    # (the byte is cleared every frame, so nonzero == a hit landed now). The
    # HP drop and the hitstun write show up on the NEXT logged frame, because
    # the bridge samples mid-frame (HANDOFF instrument hazard).
    hits = []
    for i, cur in enumerate(fr[:-1]):
        if not cur["v_hittype"]:
            continue
        nxt = fr[i + 1]
        hits.append(dict(
            frame=cur["f"], rel=cur["f"] - af,
            damage=round(max(0.0, cur["v_hp"] - nxt["v_hp"]), 3),
            dmg_byte=nxt["v_dmg"], hit_type=cur["v_hittype"],
            handler=hex(nxt["v_handler"]), react=nxt["v_react"],
            hitstun=max(cur["v_hitstun"], nxt["v_hitstun"]),
            stun_base=max(cur["v_stunbase"], nxt["v_stunbase"]),
            kb=[cur["v_kbx"], cur["v_kby"]],
            landrec=nxt["v_landrec"],
            gauge=[cur["v_gauge"], nxt["v_gauge"], nxt["v_gauge_max"]],
            # A forced switch (Kakashi down B) swaps which character the HP
            # address and M belong to, so the "damage" on that frame is the
            # HP gap between two characters. Trust dmg_byte there.
            switch_on_hit=(cur["v_active"] != nxt["v_active"]),
            eff=[max(cur["v_eff172"], nxt["v_eff172"]),
                 max(cur["v_eff173"], nxt["v_eff173"])],
            v_state=nxt["v_state"], v_ground=hex(nxt["v_ground"]),
            a_state=cur["a_state"], a_animf=cur["a_animf"],
            v_x=round(cur["v_x"], 2),
            dist=round(abs(cur["a_x"] - cur["v_x"]), 2)))

    hp_drops = [[c["f"], round(p_["v_hp"] - c["v_hp"], 3)]
                for p_, c in zip(fr, fr[1:]) if c["v_hp"] < p_["v_hp"] - 1e-9]

    # Guard: gauge steps up while the victim blocks.
    guard_steps = []
    for prev, cur in zip(fr, fr[1:]):
        if cur["v_gauge"] != prev["v_gauge"]:
            guard_steps.append([cur["f"], prev["v_gauge"], cur["v_gauge"]])

    # A blocked hit does not latch M+0x16C, so the only trace it leaves is the
    # guard gauge stepping up (obj+0x102). Gauge decay is -1/frame and starts
    # 122 frames after the last blocked hit, so only rises count as hits.
    blocked = [dict(frame=f, rel=f - af, gauge_add=b - a_)
               for f, a_, b in guard_steps if b > a_]

    first = hits[0]["frame"] if hits else None
    last = hits[-1]["frame"] if hits else None
    # Recovery: back to idle(0)/walk(1) after the attack state ran.
    rec_end = None
    saw_attack = False
    scan_from = max(af, first if first is not None else af)
    for r in fr:
        if r["f"] < scan_from:
            continue
        if r["a_state"] not in (0, 1):
            saw_attack = True
        elif saw_attack:
            rec_end = r["f"]
            break

    a_states = []
    for r in fr:
        if r["f"] < af - 1:
            continue
        if not a_states or a_states[-1][0] != r["a_state"]:
            a_states.append([r["a_state"], r["f"], r["f"]])
        else:
            a_states[-1][2] = r["f"]

    left_ground = any(r["a_ground"] != fr[0]["a_ground"] or r["a_state"] in (4, 5, 6, 7)
                      for r in fr if r["f"] >= af)

    out = dict(
        move=meta["move"], label=label, state=meta["state"],
        attack_frame=af, frames=len(fr),
        startup=(first - af) if first is not None else None,
        active=(last - first + 1) if first is not None else None,
        hit_frames=[h["frame"] - af for h in hits],
        recovery=(rec_end - last) if (rec_end and last) else None,
        total_to_idle=(rec_end - af) if rec_end else None,
        hits=hits, hit_count=len(hits),
        damage_total=round(sum(h["damage"] for h in hits), 3),
        attacker_states=[[s, f - af, t - af] for s, f, t in a_states],
        # Name kept for the stored *.summary.json files: this is the largest
        # obj+0x72 hold count during the attack, not an animation length.
        attack_anim_frames=max([r["a_animf"] for r in fr
                                if af <= r["f"] <= (rec_end or af)
                                and r["a_state"] not in (0, 1)] or [0]),
        leaves_ground=bool(left_ground),
        a_x=[round(fr[0]["a_x"], 2), round(fr[-1]["a_x"], 2)],
        v_x=[round(fr[0]["v_x"], 2), round(fr[-1]["v_x"], 2)],
        guard_gauge_steps=guard_steps, blocked_hits=blocked,
        hp_drops=hp_drops,
        sp_steps=[[c["f"] - af, p_["a_sp"], c["a_sp"]]
                  for p_, c in zip(fr, fr[1:])
                  if c["a_sp"] is not None and c["a_sp"] != p_["a_sp"]],
        sp_first_last=[fr[0]["a_sp"], fr[-1]["a_sp"]],
        spacc_steps=[[c["f"] - af, p_["a_spacc"], c["a_spacc"]]
                     for p_, c in zip(fr, fr[1:])
                     if c["a_spacc"] is not None
                     and c["a_spacc"] != p_["a_spacc"]],
        effects=sorted({tuple(h["eff"]) for h in hits}),
        active_slot_changes=[[r["f"] - af, r["v_active"], r["v_chrb"]]
                             for p_, r in zip(fr, fr[1:])
                             if r["v_active"] != p_["v_active"]],
        elem_tracks=elem_tracks(fr, af),
        hit_owners=[dict(rel=h["rel"], **(hit_owner(fr, h["frame"], h["v_x"])
                                          or {}))
                    for h in hits],
        victim_arc=[[r["f"] - af, round(r["v_x"], 2), round(r["v_y"], 2),
                     r["v_vx"], r["v_vy"], r["v_hitstun"], hex(r["v_ground"])]
                    for r in fr if first is not None and
                    first - 1 <= r["f"] <= first + 45],
    )
    with open(os.path.join(outdir, label + ".summary.json"), "w") as f:
        json.dump(out, f, indent=1)
    return out


def brief(s):
    if not s["hit_count"]:
        return ("%-14s NO HIT  states %s  anim %d  x %s sp %s  elems %s" %
                (s["label"], s["attacker_states"][:4], s["attack_anim_frames"],
                 s["a_x"], s["sp_first_last"],
                 [(t["slot"], t["spawn"], t["despawn"], t["kind"])
                  for t in s.get("elem_tracks", [])]))
    h = s["hits"]
    return ("%-14s startup %-4s active %-3s rec %-4s hits %d dmg %s "
            "types %s stun %s kb %s sp %s eff %s%s" %
            (s["label"], s["startup"], s["active"], s["recovery"],
             s["hit_count"], [x["damage"] for x in h],
             [x["hit_type"] for x in h], [x["hitstun"] for x in h],
             [x["kb"] for x in h], s["sp_first_last"], s["effects"],
             ("  own " + ",".join(o.get("nearest", "?")
                                  for o in s.get("hit_owners", []))
              if s.get("hit_owners") else "")))


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("moves")

    r = sub.add_parser("run")
    r.add_argument("--state", required=True)
    r.add_argument("--outdir", required=True)
    r.add_argument("--facing", default="LEFT", choices=["LEFT", "RIGHT"])
    r.add_argument("--family", default="pc")
    r.add_argument("--move", action="append", default=[])
    r.add_argument("--all", action="store_true")
    r.add_argument("--approach", type=int, default=DEFAULT_APPROACH)
    r.add_argument("--tail", type=int, default=DEFAULT_TAIL)
    r.add_argument("--suffix", default="")
    r.add_argument("--chr-b", type=int, default=None)
    r.add_argument("--hp", type=float, default=None,
                   help="poke the victim's deck HP record (--hp-addr) to this "
                        "many HP before the plan runs; raw = hp*64")
    r.add_argument("--hp-addr", default=None,
                   help="HP record to poke (default the family's v_hp)")
    r.add_argument("--poke", action="append", default=[],
                   help="ADDR=HEXBYTES applied after the state load "
                        "(repeatable)")
    r.add_argument("--primer", type=int, default=0,
                   help="frames: press B first, then the move (guard runs)")
    r.add_argument("--elements", type=int, nargs="?", default=0,
                   const=DEFAULT_ELEM_SLOTS,
                   help="also watch N slots of the 0x0220C0E8 element array "
                        "(default %d). Needed for summoner kits; narrows the "
                        "fighter watches to fit the 512-byte budget."
                        % DEFAULT_ELEM_SLOTS)

    s = sub.add_parser("summ")
    s.add_argument("--outdir", required=True)
    s.add_argument("--name", required=True)

    t = sub.add_parser("table")
    t.add_argument("--outdir", required=True)

    a = ap.parse_args()

    if a.cmd == "moves":
        for k, v in MOVES.items():
            print("%-14s %s" % (k, v))
        return

    if a.cmd == "summ":
        print(brief(summarise(a.outdir, a.name)))
        return

    if a.cmd == "table":
        rows = []
        for fn in sorted(os.listdir(a.outdir)):
            if fn.endswith(".summary.json"):
                rows.append(json.load(open(os.path.join(a.outdir, fn))))
        print("| move | startup | active | recovery | hits | damage | hit type "
              "| hitstun | kb (x,y) |")
        print("|---|---|---|---|---|---|---|---|---|")
        for s in rows:
            h = s["hits"]
            print("| `%s` | %s | %s | %s | %d | %s | %s | %s | %s |" % (
                s["label"], s["startup"], s["active"], s["recovery"],
                s["hit_count"], "+".join(str(x["damage"]) for x in h) or "-",
                "/".join(str(x["hit_type"]) for x in h) or "-",
                "/".join(str(x["hitstun"]) for x in h) or "-",
                "/".join("%d,%d" % tuple(x["kb"]) for x in h) or "-"))
        return

    A = ADDRESSES[a.family]
    pokes = [(int(x.split("=")[0], 16), bytes.fromhex(x.split("=")[1]))
             for x in a.poke]
    if a.hp is not None:
        hp_addr = int(a.hp_addr, 16) if a.hp_addr else A["v_hp"]
        pokes.insert(0, (hp_addr, struct.pack("<H", int(round(a.hp * 64)))))
    names = list(MOVES) if a.all else a.move
    if not names:
        raise SystemExit("give --move NAME (repeatable) or --all")
    results = []
    for n in names:
        if n not in MOVES:
            raise SystemExit("unknown move %r; `moves` lists them" % n)
        label = n + a.suffix
        run_move(n, a.state, MOVES[n], A, a.outdir, a.facing, a.approach,
                 a.tail, label, a.primer, a.elements, pokes)
        s = summarise(a.outdir, label)
        results.append(s)
        print(brief(s))
        sys.stdout.flush()
    return results


if __name__ == "__main__":
    main()
