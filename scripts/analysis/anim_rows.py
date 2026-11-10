"""Per-character capture rows for anim_timing.py: which kit capture measures which move.

This is data, not roster: a character with no rows here (one with no
captures yet) still decodes; `anim_timing.build` reads `.get(char, [])`.
The roster itself (chr_b, prefix) lives in decoder_roster.json and on the
command line (char_args.py). Rows are keyed by the roster name.
"""

# Every move with a kit capture that measures it:
# (move, anim id, capture dir, anchor rule, options). Options:
#   upto   check only the first n anim frames (the move is cut short);
#   pause  (at, n): the clock stops for n game frames somewhere before anim
#          frame `at`, inside the span where the boxes do not change;
#   also   more captures that must pass the same check;
#   then   anim ids whose boxes must show while the fighter falls after `upto`;
#   cut    {at, state_at, then, cause}: the move stops being drawn at anim
#          frame `at`; the attack state ends at `state_at` (build checks both);
#   why    required when the idle return is not frames + 3;
#   cells_measured  {capture, key, upto?}: a capture whose checks.json read the live
#          cell per frame (build verifies it against the decoded cells; `upto`
#          limits it to the first n anim frames).
#   koma   a koma set's special that a plain box capture measures (Eve: no strip
#          sheet, no per-path special log): the row gains koma, archive and
#          koma_archive, and the vfx-sfx label carries the koma.
# P1 faces left in every capture listed here.
K = "kakashi-kit-2026-09-12"
XA = "yusuke-xcancel-airy-2026-09-25"
Y1 = "yusuke-kit-2026-09-22/geometry"
Y2 = "yusuke-kit2-2026-09-22/geometry1"
EB = "2026-10-12-eve-base/geometry/L"
ES = "2026-10-12-eve-specials/grids"
MOVES = {
    "kakashi": [
        ("B", 0x1E, f"{K}/neutral_b", "leave_idle", {}),
        ("side B", 0x20, f"{K}/forward_b", "leave_idle", {}),
        ("up B", 0x22, f"{K}/up_b", "leave_idle", {}),
        ("down B", 0x24, f"{K}/down_b", "leave_idle", {}),
        ("air B", 0x26, f"{K}/air_b", "state9", {
            "why": "ends in the air: state 6 (fall) at +29 = frames + 3, lands (state 13) at +43, "
                   "idle at +62. The fall and the landing window belong to the jump, not the move"}),
        ("Y", 0x1F, f"{K}/neutral_y_cap8", "leave_idle", {}),
        ("side Y", 0x21, f"{K}/forward_y", "leave_idle", {}),
        ("side Y (mashed)", 0x21, f"{K}/side_y_mash/a", "leave_idle", {
            "pause": (36, 30), "also": [f"{K}/side_y_mash/b"],
            "why": "mashing Y adds 30 game frames somewhere in anim frames 4 to 35 (the box key at "
                   "36 lands 30 late; the boxes do not change from 4 to 35). Idle at 56 + 30 + 3 = +89"}),
        ("up Y", 0x23, f"{K}/up_y", "leave_idle", {
            "why": "ends in the air: state 6 (fall) at +77 = frames + 3, idle at +96 with no "
                   "state-13 frame logged"}),
        ("down Y", 0x25, f"{K}/down_y", "leave_idle", {}),
        ("air Y", 0x27, f"{K}/air_y", "state9", {
            "why": "ends in the air: state 6 (fall) at +33 = frames + 3, lands (state 13) at +36, "
                   "idle at +55"}),
    ],
    "yusuke": [
        ("B", 0x1E, f"{Y2}/B_idle", "leave_idle", {"cells_measured": {"capture": XA, "key": "B"}}),
        ("side B", 0x20, f"{Y2}/side_B_idle", "leave_idle", {}),
        ("up B", 0x22, f"{Y2}/up_B_idle", "leave_idle", {
            "why": "ends in the air: state 6 (fall) at +36 = frames + 3, idle at +46 with no "
                   "state-13 frame logged"}),
        ("down B", 0x24, f"{Y2}/down_B_idle", "leave_idle", {}),
        ("air B", 0x26, f"{Y1}/air_B_idle", "state9", {
            "upto": 26,
            "cut": {"at": 26, "state_at": 27, "then": "landing (0x07 from anim frame 26, state 13 from +27)",
                    "cause": "the fighter lands"},
            "why": "lands before the animation ends: the landing starts at anim frame 26 (state 13 "
                   "at +27), idle at +46"}),
        ("Y", 0x1F, f"{Y2}/Y_idle", "leave_idle", {"cells_measured": {"capture": XA, "key": "Y"}}),
        ("side Y", 0x21, f"{Y1}/side_Y_idle", "leave_idle", {
            "upto": 51, "also": [f"{Y2}/side_Y_far", f"{Y1}/side_Y_mash"],
            "why": "the unempowered first phase ends at native End key 51, idle at +53; "
                   "all 51 captured frames match directly. The 136-frame header includes the stored-UA phases. "
                   "The old 0x28 fit required an artificial 8-frame pause before frame 8"}),
        ("up Y", 0x23, f"{Y2}/up_Y_idle", "leave_idle", {}),
        ("down Y", 0x25, f"{Y2}/down_Y_idle", "leave_idle", {}),
        ("air Y", 0x27, f"{Y2}/air_Y_idle", "state9", {
            "upto": 48, "then": [0x05, 0x06],
            "cells_measured": {"capture": XA, "key": "airY", "upto": 48},
            "cut": {"at": 48, "state_at": 48, "then": "fall (0x05/0x06 boxes from anim frame 48)",
                    "cause": "TBD (the attack state ends in the air, 79 frames before the 127-frame "
                             "animation would; jus-wmqi.6.10)"},
            "why": "the attack ends in the air at anim frame 48 (state 6), 79 frames short of the "
                   "127-frame animation; cause TBD. Lands (state 13) at +67, idle at +86. A different jump "
                   "(jump A 0-7, Y at plan 15) gives +94 instead, so +86 depends on the jump, "
                   "not on air Y alone (inferred; yusuke-xcancel-airy-2026-09-25/RESULTS.md)"}),
    ],
    # Eve: facing-left whiffs from a short hop (air) or the load spot (eve-base README, claims-base.json);
    # the set moves are the facing-left whiffs of E3's grids. Anim ids are the kit's jus_anim.
    "eve": [
        ("B", 0x1E, f"{EB}/B_idle", "leave_idle", {}),
        ("side B", 0x20, f"{EB}/side_B_idle", "leave_idle", {}),
        ("up B", 0x22, f"{EB}/up_B_idle", "leave_idle", {}),
        ("down B", 0x24, f"{EB}/down_B_idle", "leave_idle", {}),
        ("air B", 0x26, f"{EB}/air_B_idle", "state9", {
            "why": "ends in the air: state 6 (fall) at +32 = frames + 3, lands (state 13) at +43, "
                   "idle at +62 (a full hop lands at +49, idle at +71)"}),
        ("Y", 0x1F, f"{EB}/Y_idle", "leave_idle", {}),
        ("side Y", 0x21, f"{EB}/side_Y_idle", "leave_idle", {
            "upto": 61,
            "cut": {"at": 61, "state_at": 62,
                    "then": "the stand boxes (idle at +62)",
                    "cause": "the whiff path: the attack state ends at +62, 55 frames before the 117-frame "
                             "animation would; its later frames carry the type 259/260 boxes of the grab "
                             "follow-up, seen only on a connect (eve-base claims-grab.json)"},
            "why": "the whiff path ends at +62; the animation is 117 frames, and what follows frame 60 "
                   "belongs to the connect path (a grab follow-up), which this capture does not take"}),
        ("up Y", 0x23, f"{EB}/up_Y_idle", "leave_idle", {
            "why": "ends in the air: state 6 (fall) at +48 = frames + 3, idle at +67 with no "
                   "state-13 frame logged"}),
        ("down Y", 0x25, f"{EB}/down_Y_idle", "leave_idle", {}),
        ("air Y", 0x27, f"{EB}/air_Y_idle", "state9", {
            "why": "ends in the air: state 6 (fall) at +41 = frames + 3, lands (state 13) at +57, "
                   "idle at +76 (a full hop lands at +63, idle at +85)"}),
        ("X", 0x29, f"{ES}/k4-L/X_idle", "leave_idle", {"koma": 4}),
        ("up X", 0x2A, f"{ES}/k4-L/up_X_idle", "leave_idle", {"koma": 4}),
        ("X", 0x2B, f"{ES}/k5-L/X_idle", "leave_idle", {
            "koma": 5, "upto": 41,
            "why": "the whiff path: the boxes follow the animation straight through frame 40, then the "
                   "clock jumps inside the 112-frame animation (frames 42-44 at s 50-52, 57-60 at s 65-68, "
                   "73-85 at s 81-82); the attack state ends in the air (state 6) at +83 = idle at +85. "
                   "Which branch the later frames are is not pinned"}),
        ("up X", 0x2C, f"{ES}/k5-L/up_X_idle", "leave_idle", {
            "koma": 5, "upto": 20,
            "why": "a mash move (kit mash.frames 84): unmashed, the boxes follow the animation straight "
                   "through frame 19, then jump (frames 56-58 at s 20-22, 62-65 at s 26-31, 69-75 at "
                   "s 35-41) and idle comes at +53, 31 frames before the 84-frame animation ends"}),
    ],
}

# State animations some capture shows: (anim id, what, capture, rule, opts).
# Boxes only tell animations apart where their rects differ, so each check
# lists the other animations that fit the same frames (`also_fits`).
STATE_CHECKS = {
    "kakashi": [
        (0x02, "dash", f"{K}/dash_b", "leave_idle", {}),
        (0x08, "jump squat (state 4)", f"{K}/air_b", "4", {}),
        (0x04, "jump rise", f"{K}/air_b", "4+4", {}),
        (0x07, "landing (from the frame before state 13)", f"{K}/air_b", "13-1", {}),
        (0x08, "landing end, from the last frame of state 13", f"{K}/air_b", "13>0-1", {}),
        (0x08, "landing end, from one frame later (fits too)", f"{K}/air_b", "13>0", {}),
    ],
    "yusuke": [
        (0x02, "dash", f"{Y2}/dash_B_idle", "leave_idle", {}),
        (0x04, "jump rise", f"{Y1}/air_B_idle", "4+4", {}),
    ],
}


# State animations every fighter shares by id, for a fighter with no STATE_CHECKS row of its own for that id
# (no capture of this fighter): id -> the name vfx-sfx.json gives the row. INFERRED, never measured: the id is
# the state anim the engine plays, and the captures that name it are the fighters listed in STATE_CHECKS.
SHARED_STATES = {0x02: "dash"}

# Fighters whose box-less kit moves (docs/rebuild/characters/<id>.kit.json, a move with a jus_anim and no
# boxes: the Ultimate Action) label their anim in vfx-sfx.json. Opt-in. Kakashi's and Yusuke's kits carry
# the same ULTIMATE / 0x18 move and are not listed yet, so their 0x18 rows stay unlabelled.
KIT_LABELS = ("eve", "train")


NO_SIDE_X = ("no side X or down X rows: the owner ruled \"side X and down X are not a thing. only "
             "neutral and up\" (OWNER-NOTES.md, 2026-09-25), so X with any direction but up is just X. "
             "C1 §14 and C2 §2 saw the same latches and damage for those inputs as for X")

C1 = "kakashi-specials-2026-09-25/trials"
C2 = "yusuke-6koma-specials-2026-09-24/trials"
C3 = "kakashi-5-6koma-specials-2026-09-27/trials"
C4 = "yusuke-4-5koma-specials-2026-09-27/trials2"

# Each special animation a set plays (one row per JUS animation). `plays`
# are (path, capture, segments) checked by check_plays; the first is the
# row's `check`. `hits`: the col records the special's hits use (record =
# element id - 0x100; the moveData entry's address moves between loads),
# as (record, what, source[, grade]). The grade is "measured" (a capture
# read that record) unless given; an inferred one names its rule. Pass 1
# (capture batch 1): Kakashi 4 and Yusuke 6. Pass 2: Kakashi 5 and 6,
# Yusuke 4 and 5.
K_DOG_WHY = ("inferred: kind 4, and their damage and type are C3's dog hits (4 type 2, 4 type 1, 1 type 1, "
             "5 type 2); no animation's track and no measured shot claims them. C3 read no dog records, so "
             "which dog uses which is unknown. C3's 8-damage hit (type 2) matches no record: two 4s landing "
             "on one frame would explain it (inferred)")
K_X_HIT_WHY = ("inferred: the anim's track enables it, and its damage and type are C3's hit; C3 read "
               "no record numbers for X")
K_X_IDLE_WHY = ("the move (state 10) ends when the dash stops, not when the anim ends: each frame "
                "v = v - (v >> 3) + push, and a speed under 16 raw becomes 0 (C3 §2). So the idle return "
                "follows the level and the hold")
K_X_LEVELS = ("one animation for the press and all three levels, so one row, `X`. Level 1 is a hold of 3-30, "
              "level 2 40-92, level 3 93 or more; level 3 fires by itself at press + 95, even while X is held. "
              "The damage is the same at every level (C3 §2). The markers at anim frames 62, {m2} and {m3} "
              "are where levels 1, 2 and 3 start and {hit} is the hit sequence played on contact (inferred: "
              "C3 logs no P1 body box, so no frame is checked)")

SPECIALS = {
    "kakashi": [
        {"move": "X", "anim": 0x29, "koma": 4, "strip": "x_beam_k4", "rule": "leave_idle",
         "plays": [("X", f"{C1}/K/X_near_1", [("play", 0, 0, 79)])],
         "hits": [(19, "the emitter and all 17 bolts", "C1 RESULTS §9 (moveData 0x021BA25C)")],
         "aliases": NO_SIDE_X},
        {"move": "up X", "anim": 0x2A, "koma": 4, "strip": "up_x_dogs_k4", "rule": "leave_idle",
         "plays": [("up X", f"{C1}/K/upX_near", [("play", 0, 0, 78)])],
         "hits": [(20, "dog 1", "C1 RESULTS §9 (0x021BA270)"), (21, "dog 2", "C1 RESULTS §9 (0x021BA284)"),
                  (22, "dog 3", "C1 RESULTS §9 (0x021BA298)"), (23, "dog 4", "C1 RESULTS §9 (0x021BA2AC)")]},
        {"move": "X", "anim": 0x2B, "koma": 5, "strip": "x_raikiri_k5", "rule": "leave_idle",
         "plays": [("tap (level 1, near)", f"{C3}/A/5X_tap", []),
                   ("hold 60 (level 2)", f"{C3}/A/5Xm_h60", []),
                   ("hold 120 (level 3)", f"{C3}/A/5X_h120", [])],
         "hits": [(24, "the dash box (0 damage; enabled on the dash segments)", "static track, 0x2B",
                   "inferred: the anim's track enables it, no capture read it"),
                  (25, "hit 1 (10, type 1)", "C3 RESULTS §2 (damage and type)", K_X_HIT_WHY),
                  (26, "hit 2 (10, type 2)", "C3 RESULTS §2 (damage and type)", K_X_HIT_WHY),
                  (27, "hit 3 (16, type 6)", "C3 RESULTS §2 (damage and type)", K_X_HIT_WHY)],
         "idle_return_why": K_X_IDLE_WHY,
         "levels": K_X_LEVELS.format(m2=93, m3=128, hit=167) + ". The 5-koma dash goes the way he faced "
                   "when the charge began; nothing pressed later changes it (C3 §3)",
         "aliases": NO_SIDE_X},
        {"move": "up X", "anim": 0x2C, "koma": 5, "strip": "up_x_dogs_k5", "rule": "leave_idle",
         "plays": [("the summon", f"{C3}/A/5upX_tap", [])],
         "hits": [(28, "a dog (4, type 2)", "static records", K_DOG_WHY),
                  (29, "a dog (4, type 1)", "static records", K_DOG_WHY),
                  (30, "a dog (1, type 1)", "static records", K_DOG_WHY),
                  (36, "a dog (5, type 2)", "static records", K_DOG_WHY)],
         "levels": "no charge: seven hits on the same frames near, far, held 120 and facing away (C3 §5)"},
        {"move": "X", "anim": 0x2D, "koma": 6, "strip": "x_chidori_k6", "rule": "leave_idle",
         "plays": [("tap (level 1, near)", f"{C3}/A/6X_tap", []),
                   ("hold 60 (level 2)", f"{C3}/A/6Xm_h60", []),
                   ("hold 120 (level 3)", f"{C3}/A/6X_h120", [])],
         "hits": [(31, "the dash box (0 damage; enabled on the dash segments)", "static track, 0x2D",
                   "inferred: the anim's track enables it, no capture read it"),
                  (32, "hit 1 (2, type 1)", "C3 RESULTS §2 (damage and type)", K_X_HIT_WHY),
                  (33, "hit 2 (2, type 2)", "C3 RESULTS §2 (damage and type)", K_X_HIT_WHY),
                  (34, "hit 3 (40, type 6)", "C3 RESULTS §2 (damage and type)", K_X_HIT_WHY)],
         "idle_return_why": K_X_IDLE_WHY,
         "levels": K_X_LEVELS.format(m2=95, m3=136, hit=181) + ". The 6-koma dash steers: back held into "
                   "the frame before it starts reverses it, and a side press mid-flight flips the push 2 "
                   "frames later and sticks (C3 §3)",
         "aliases": NO_SIDE_X},
        {"move": "up X", "anim": 0x2E, "koma": 6, "strip": "up_x_mangekyou_k6", "rule": "leave_idle",
         "plays": [("the eye", f"{C3}/A/6upX_tap", [])],
         "hits": [(35, "the eye (3, type 1, every 8 frames while it overlaps)",
                   "C3 RESULTS §6 (element 291)")],
         "levels": "no charge. The eye is steered: it eases toward the held heading, ignores a direction "
                   "straight behind or straight ahead of it, keeps its heading on release, and passes walls "
                   "and the floor. It spawns at press + 31 and lives 124 frames (C3 §6)",
         "idle_return_why": "the anim is 56 frames but Kakashi stays in state 10 for 195: he holds while "
                            "the eye flies (C3 §6)"},
    ],
    "yusuke": [
        {"move": "X", "anim": 0x29, "koma": 4, "strip": "x_spirit_gun_k4", "rule": "leave_idle",
         "facing": 1,
         "plays": [("tap", f"{C4}/A/4X_tap", []), ("hold 120 (the same)", f"{C4}/A/4X_h120", [])],
         "missing": {16: "not on the sheet: no fighter frame matches it (best colour cover 0.47)"},
         "hits": [(22, "the shot (28, type 5)", "C4 RESULTS §2 (element 278)")],
         "levels": "no charge: holds of 3 to 1500 play the same frame for frame, and the shot fires at "
                   "press + 30 even while X is held (C4 §2)",
         "aliases": NO_SIDE_X},
        {"move": "up X", "anim": 0x2A, "koma": 4, "strip": "up_x_rei_kou_dan_k4", "rule": "leave_idle",
         "facing": 1,
         "plays": [("tap", f"{C4}/K/4upX_tap", [("play", 0, 0, 71)])],
         "missing": {13: "not on the sheet: the rush is only drawn under the blasts 0x098165 and 0x098166 "
                         "(best colour cover 0.39)"},
         "hits": [(23, "hits 1-4 (2, type 1)", "C4 RESULTS §4 (element 279)"),
                  (24, "hit 5, the finisher (20, type 6)", "static track, 0x2A frame 43",
                   "inferred: damage and type match C4's fifth hit; its box wasn't read")],
         "levels": "no charge, against the guide (KMY :19): holds to 600 play the same (C4 §4)"},
        {"move": "X", "anim": 0x2B, "koma": 5, "strip": "x_spirit_gun_k5", "rule": "leave_idle",
         "facing": 1,
         "plays": [
             ("tap (level 1)", f"{C4}/Q/5X_tap", [("play", 0, 0, 4), ("hold", 4, 20, 4, 55), ("play", 20, 56, 29)]),
             ("hold 65 (level 1)", f"{C4}/Q/5X_h65",
              [("play", 0, 0, 4), ("hold", 4, 64, 4, 55), ("play", 64, 56, 29)]),
             ("hold 66 (level 2)", f"{C4}/Q/5X_h66",
              [("play", 0, 0, 4), ("hold", 4, 65, 4, 55), ("play", 65, 92, 28)]),
             ("hold 120 (level 2)", f"{C4}/Q/5X_h120",
              [("play", 0, 0, 4), ("hold", 4, 119, 4, 55), ("play", 119, 92, 28)]),
             ("hold 300 (level 2)", f"{C4}/Q/5X_h300",
              [("play", 0, 0, 4), ("hold", 4, 299, 4, 55), ("play", 299, 92, 28)]),
         ],
         "hits": [(25, "level 1's shot (32, type 6)", "C4 RESULTS §3 (element 281)"),
                  (26, "level 2's shot (44, type 5)", "C4 RESULTS §3 (element 282)")],
         "levels": "two levels, not the guide's charge: level 2 iff X is held 66 frames or more, and no "
                   "auto-fire through a 3600-frame hold (C4 §3). One animation, so one row, `X`: the hold "
                   "sits in anim frames 4-55; level 1 jumps to frame 56, level 2 to frame 92 (a tap at "
                   "s 20, hold 65 at s 64, hold 66 at s 65). The switch frames and targets are pinned by "
                   "the exact box check",
         "idle_return_why": "the hold sets it, not the 120-frame anim: the anim waits in frames 4-55 while X is "
                            "held, then level 1 plays 56-84 and idles 30 frames after the switch, level 2 "
                            "plays 92-119 and idles 31 after it",
         "aliases": NO_SIDE_X},
        {"move": "up X", "anim": 0x2C, "koma": 5, "strip": "up_x_rei_kou_dan_k5", "rule": "leave_idle",
         "facing": 1,
         "plays": [("tap", f"{C4}/K/5upX_tap", [("play", 0, 0, 96)]),
                   ("wait 42 first", f"{C4}/K/5upX_w42", [("play", 0, 0, 96)])],
         "missing": {13: "not on the sheet: the rush is only drawn under the blasts 0x098188 and 0x098189",
                     14: "not on the sheet: the rush is only drawn under the blasts 0x098188 and 0x098189"},
         "hits": [(27, "hits 1-7 (2, type 1)", "C4 RESULTS §4 (element 283)"),
                  (28, "the finisher (20, type 6)", "static track, 0x2C frame 65",
                   "inferred: damage and type match C4's last hit; its box wasn't read")],
         "levels": "no charge, against the guide (KMY :19): holds to 1500 play the same. The hit count "
                   "depends on the gap: up to eight (C4 §4)"},
        {"move": "X", "anim": 0x2D, "koma": 6, "strip": "x_spirit_gun_k6", "rule": "leave_idle",
         "plays": [
             ("tap (level 1)", f"{C2}/H3/X_tap", [("play", 0, 0, 32), ("play", 32, 76, 32)]),
             ("hold 72 (level 1)", f"{C2}/H3/X_h72",
              [("play", 0, 0, 4), ("hold", 4, 71, 4, 35), ("play", 71, 76, 32)]),
             ("hold 73 (level 2)", f"{C2}/H3/X_h73",
              [("play", 0, 0, 4), ("hold", 4, 72, 4, 35), ("play", 72, 48, 21)]),
             ("hold 120 (level 2, charged pose)", f"{C2}/H3/X_h120",
              [("play", 0, 0, 4), ("hold", 4, 96, 4, 35), ("play", 96, 36, 4),
               ("hold", 100, 119, 40, 47), ("play", 119, 48, 21)]),
         ],
         "hits": [(29, "level 1's ball", "C2 RESULTS §2 (moveData 0x021BA324)"),
                  (30, "level 2's ball", "C2 RESULTS §2 (moveData 0x021BA338)")],
         "levels": "one animation for the press and both levels, so one row, `X`: level 1 jumps from "
                   "its frozen frame to anim frame 76 (a tap at s 32, hold 72 at s 71); level 2 jumps "
                   "to anim frame 48 (hold 73 at s 72). The switch frames and targets are pinned by "
                   "the exact box check; that the switch is two frames after the release is C2 §3's. "
                   "A hold past s 96 shows frames 36-39 and then frame 40 (cell 4) until the release",
         "idle_return_why": "the hold and the level set it, not the 108-frame anim: level 1 plays 76-107 and "
                            "idles 35 frames after the switch, level 2 plays 48-68 and idles 22 after it",
         "aliases": NO_SIDE_X},
        {"move": "up X", "anim": 0x2E, "koma": 6, "strip": "up_x_awakening_k6", "rule": "leave_idle",
         "plays": [("the rush hits", f"{C2}/G2/upX_near",
                    [("play", 0, 0, 21), ("play", 21, 43, 62), ("hold", 83, 97, 100, 104),
                     ("play", 97, 105, 27)])],
         "missing": {13: "not on the sheet: row 1's frame 3 is cell 14, a look-alike (special-strips.json)",
                     20: "not on the sheet: row 1's frame 9 redraws this pose too loosely (shape cover "
                         "0.77), so the strip leaves it out"},
         "hits": [(16, "hit 1", "C2 RESULTS §4 (0x021BA220)"), (17, "hit 2", "C2 RESULTS §4 (0x021BA234)"),
                  (18, "hits 3 and 5", "C2 RESULTS §4 (0x021BA248)"),
                  (19, "hits 4 and 6", "C2 RESULTS §4 (0x021BA25C)"),
                  (20, "hit 7, the launcher", "C2 RESULTS §4 (0x021BA270)"),
                  (21, "the finishing shot", "C2 RESULTS §4 (0x021BA284)")],
         "levels": "on a hit the anim jumps from frame 21 to frame 43 at s 21, waits in frames "
                   "100-104 (Marker 2; the boxes of 95-104 are equal, so where it waits is inferred) "
                   "from s 83 to 96, then plays 105-131. A whiff stops after the first strike (C2's "
                   "summary); no body box was read on a whiff",
         "idle_return_why": "on a hit the anim skips frames 21-42 (22 frames) and waits 14 game frames in "
                            "100-104, so it runs 132 - 22 + 14 = 124 game frames and idles at 124 + 3. That is the "
                            "hit path; a whiff stops after the first strike (C2's summary)"},
    ],
}


# STATIC kit animation joins. These are labels and decoded cells, not a captured art clock.
STATIC_MOVES = {"komamen": [(name, aid, koma) for name, aid, koma in (
    ("B", 0x1e, None), ("Y", 0x1f, None), ("side B", 0x20, None),
    ("side Y", 0x21, None), ("up B", 0x22, None), ("up Y", 0x23, None),
    ("down B", 0x24, None), ("down Y", 0x25, None), ("air B", 0x26, None),
    ("air Y", 0x27, None), ("dream", 0x28, None), ("X", 0x29, 4), ("up X", 0x2a, 4))]}
