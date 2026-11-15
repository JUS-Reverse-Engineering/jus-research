# Animation timing: which art cell shows on which frame (Kakashi, Yusuke)

This page says, for every move and state strip Kakashi (`chr_b` 23) and
Yusuke (`chr_b` 32) draw, which art cell JUS shows on each frame, and which
frame of the hand-cut strips holds that cell. The specials section (pass 1)
adds four specials: Kakashi's 4-koma X and up X and Yusuke's 6-koma X and up X
(§8).

- The machine-readable copy is [anim-timing.json](anim-timing.json)
  (schema in §5). Use the JSON for machine-readable data.
- Both come from one tool:
  [scripts/analysis/anim_timing.py](../../scripts/analysis/anim_timing.py)
  (`build` writes the JSON, `tables` prints §2 and §3). Its test
  [scripts/tests/test_anim_timing.py](../../scripts/tests/test_anim_timing.py)
  fails if the JSON or these tables drift from a fresh build.

Grades: **measured** (a live capture, cited), **static** (read from the game
files), **inferred** (a rule, named), **TBD**.

The Kenshin rows use the production texture/cell identity join. Every span
in `other[5,9,12,13,14,16]` carries `pick`, `strip_frames`, `texture_id`,
`normalized_frame_ids` and `pick_source: texture_cell_identity` (87 spans).
`other[21]` adds the AMT 131 terminal-effect role, its four cells and its
17-frame one-shot playback. These are static identities, not measured live
playhead traces. See the E note
and native-readings reference.

## 0. Conditions behind every number

| item | value |
|---|---|
| game data | `jus_files` ChrArc: `chr/na_b_04.aar` (Kakashi) and `chr/yh_b_01.aar` (Yusuke), members `<prefix>.amt` (ALMT motion table) and `<prefix>_.dtx` (sprite list); art tiles in `chr/<prefix>c.aar` |
| Kakashi captures | kakashi-kit-2026-09-12: state `pc-kakashi-npc-jotaro-dark-tournament`, P1 Kakashi faces LEFT, victim CPU Jotaro idle. Conditions and identity: characters/kakashi.md §0 |
| Yusuke captures | yusuke-kit-2026-09-22 (`B`, `side Y`, `air B`) and yusuke-kit2-2026-09-22 (the rest): state `pc-taikoubou-npc-jotaro-dark-tournament`, P1 Yusuke faces LEFT. Every trial passed the roster identity check (`0x021DF1D4 + 0x50·i`, `+0x25` bit 0 active, `+0x29` = 32), e.g. B_idle/identity.json. Conditions: characters/yusuke.md §0 |
| probe | the kit hitbox dump: per frame, P1's state code and every live collision element (4 elements per record; Kakashi `Y` uses the 8-element rerun `neutral_y_cap8`) |
| hand-cut strips | a folder per fighter of hand-cut art strips (`sprites.json` and the strip PNGs); read only |
| special captures | kakashi-specials-2026-09-25 (C1, trials `K/*`: body element `ke1`) and yusuke-6koma-specials-2026-09-24 (C2, trials `H3/*`: the element's raw bytes; `G2/*`: `p1e1`). Frame 0 is s 0 = press + 3, the first frame out of idle |
| special sheets | `jus_files/sprites/characters/Naruto/kakashi/Kakashi.png` and `jus_files/sprites/characters/YuYu Hakusho/yusuke_urameshi/Yusuke_Urameshi.png` (untracked; jus_files b756b40 moved them, same bytes); boxes and SHA-256s in special-strips.json (§8.1) |
| Eve captures | 2026-10-12-eve-base (`geometry/L`: facing-left whiffs, short-hop air moves) and 2026-10-12-eve-specials (`grids/k4-L`, `k5-L`): state `pc-eve-npc-jotaro-dark-tournament` and the `cm-eve-4` / `cm-eve-5` deck-maker states, P1 Eve (`chr_b` 37, `bc_b_01`) faces LEFT |
| no new emulator run | everything here reuses committed captures |

## 1. How to read the tables

**Frame 0** is the move's anchor, the basis the kit tables use
(characters/kakashi.md §0):

- grounded moves: the first frame the state code leaves idle or walk (3
  frames after the press);
- `air B`, `air Y`: the first frame in state 9.

**One animation frame is one game frame.** Every entry's rate byte reads 60
(static), and every box change in every move below landed on its ALMT
frame (measured).

**Cells.** `cell@start+len→strip frame` means: show `cell` from animation
frame `start` for `len` frames. The strip frame is the frame of the
character's hand-cut strip that holds that cell. `0/4` means frames 0 and 4 both
hold it (the strip repeats a pose). `none` means the strip has no frame
with that cell.

**After the last frame** (measured on every move whose end boxes differ
from the stand boxes; `end_hold` and `stand_at` in the JSON):

- grounded moves show the **end cell** on animation frames `frames` and
  `frames + 1`. The stand animation starts at `frames + 2`, and the state
  code reads idle at `frames + 3` (the "+" column is that idle return);
- moves that end in the air (Kakashi `air B`, `air Y` and `up Y`, Yusuke
  `up B`) show the end cell for 3 frames; then the state turns to 6 (fall);
- the end cell is the key at frame `frames`. It is almost always the last
  cell again. Kakashi `up Y` ends on cell 17 and Yusuke `up B` on cell 17:
  the jump-rise cell.

**Loop or hold** (static, the loop byte): stand (0x00), walk (0x01), the
first `down` part (0x13) and 0x0e, 0x12, 0x14 and 0x16 loop. Every other
animation holds its last cell until the next animation starts.

**Two Yusuke air moves stop early.** The JSON gives each a `draw` record:
play only the first frames of the animation, then switch.

- `air B` (50 frames) lands. Its landing boxes (0x07) start at animation
  frame 26 and state 13 at +27. Draw frames 0 to 25, then the landing.
- `air Y` (127 frames) does **not** land early. Its attack state ends **in
  the air** at animation frame 48 (state 9 → 6, fall), 79 frames before the
  animation would end. From frame 48 the fall boxes (0x05/0x06) show on
  every fall frame; the fighter lands (state 13) at +67 and is idle at +86.
  Draw frames 0 to 47, then the fall art. Why the attack ends there is
  **TBD** (a hold or mash extension, or something else; `jus-wmqi.6.10`).

The cells after those frames are static only. The table after each
character's moves lists every move whose idle return is not `frames + 3`,
with the reason; each needs an override. A special is listed
when any of its paths is off, with every path's return. The build refuses
a row that is off with no reason.

### 1.1 What "measured" covers here

The grade `box clock measured, cells static` means:

1. The capture's collision boxes match the animation's collision keys on
   every checked frame, and the boxes change inside the move (at least one
   hitbox or hurtbox key). So the animation's frame counter runs one per
   game frame from the anchor. This is measured.
2. The art cell comes from the `BoundsIndex` track of the same ALMT entry,
   on the same frame axis. That the game steps both tracks with one counter
   is **inferred** from that shared entry and frame axis (the combat notes say
   the collision value is read at the current animation frame). No probe
   has read the live cell yet.
3. Which cell each key names is **static**.

`start measured` means the boxes never change inside the animation (a
single body box), so the capture only shows the animation is live from
its anchor.

The tool also refuses to pass a move when another animation fits the same
frames (`also_fits`). For the state checks, look-alikes are listed instead:
Kakashi's dash has the same body box as stand and walk.

### 1.2 Yusuke side Y follows animation 0x21's first phase

All three existing captures match native frames 0..50 directly: 51/51
frames, three body changes at 16/20/39, idle at +53. The first native End
key is 51; the 136-frame header also contains the stored-UA phases.
The earlier 0x28 association required an added eight-frame pause. Its keys
8/12/31 plus eight happen to equal 0x21's keys 16/20/39. That fit did not
establish a native pause. The corrected association agrees with move ID 4's
native selector and the independently captured ground cancel flag at s29.
See the J8 correction and the
independent raw replay.

### 1.3 How the hand-cut strips were matched (inferred)

The tool draws each cell from the game's tiles and sprite list and finds
it in each strip frame, comparing colours pixel by pixel at the best
offset. Two scores: how much of the cell is found (`cell_cover`), and how
much of the strip frame the cell explains (`strip_cover`).

- `clean`: both at least 0.9.
- `extra`: the cell is all there (0.85 or more), but the frame also holds
  other art, such as an effect cut into the same frame.
- `weak`: the best cell covers 0.6 to 0.85. Probably right; check by eye.
- `none`: nothing from the main sheet fits.

Cells that look the same are all listed (Kakashi's down B and down Y share
poses, for example). The move's strip is the one holding most of its
cells; `pick` in the JSON is the first strip frame at or after the last
pick, so a strip that runs in order maps in order.

## 2. Kakashi (`chr_b` 23, `na_b_04`)

<!-- generated:anim-timing kakashi -->

| move | anim | frames | cells: cell@start+len→strip frame | end cell | strip | check (capture: agree/checked, idle return) | grade |
|---|---|---|---|---|---|---|---|
| `B` | 0x1e | 29 | 75@0+4→0, 76@4+4→1, 77@8+3→2, 78@11+4→3, 79@15+6→4, 80@21+4→5, 81@25+4→6 | 81 | b_attack | `kakashi-kit-2026-09-12/neutral_b`: 29/29, +32 | box clock measured, cells static |
| `side B` | 0x20 | 33 | 92@0+2→0, 93@2+3→1, 94@5+3→2, 95@8+4→3, 96@12+5→4, 97@17+4→5, 98@21+4→6, 99@25+8→7 | 99 | b_forward | `kakashi-kit-2026-09-12/forward_b`: 33/33, +36 | box clock measured, cells static |
| `up B` | 0x22 | 34 | 112@0+6→0, 113@6+4→1, 114@10+4→2, 113@14+4→1, 114@18+4→2, 113@22+4→1, 114@26+4→2, 115@30+4→3 | 115 | b_up | `kakashi-kit-2026-09-12/up_b`: 34/34, +37 | box clock measured, cells static |
| `down B` | 0x24 | 39 | 130@0+2→0/4, 131@2+3→1, 132@5+3→2, 133@8+4→3, 134@12+3→5, 135@15+24→6 | 135 | y_down | `kakashi-kit-2026-09-12/down_b`: 39/39, +42 | box clock measured, cells static |
| `air B` | 0x26 | 26 | 143@0+3→0, 144@3+6→1, 145@9+2→2, 146@11+3→3, 147@14+4→4, 148@18+8→5 | 148 | b_jump | `kakashi-kit-2026-09-12/air_b`: 26/26, +62 | box clock measured, cells static |
| `Y` | 0x1f | 40 | 83@0+3→0, 84@3+3→1, 85@6+3→2, 86@9+3→3, 87@12+3→4, 88@15+4→5, 89@19+7→6, 90@26+9→7, 91@35+5→8 | 91 | y_attack | `kakashi-kit-2026-09-12/neutral_y_cap8`: 40/40, +43 | box clock measured, cells static |
| `side Y` | 0x21 | 56 | 100@0+4→0, 101@4+4→1, 102@8+13→2, 103@21+2→3, 104@23+2→none, 105@25+2→4/5, 106@27+2→6, 107@29+2→none, 108@31+2→8, 109@33+3→9, 110@36+16→11, 111@52+4→13 | 111 | y_forward | `kakashi-kit-2026-09-12/forward_y`: 56/56, +59 | box clock measured, cells static |
| `side Y (mashed)` | 0x21 | 56 | 100@0+4→0, 101@4+4→1, 102@8+13→2, 103@21+2→3, 104@23+2→none, 105@25+2→4/5, 106@27+2→6, 107@29+2→none, 108@31+2→8, 109@33+3→9, 110@36+16→11, 111@52+4→13 | 111 | y_forward | `kakashi-kit-2026-09-12/side_y_mash/a`: 56/56, +89; pause 30f before anim frame 36 | box clock measured, cells static |
| `up Y` | 0x23 | 74 | 116@0+11→0, 117@11+4→1, 118@15+3→2, 119@18+3→3, 120@21+4→4, 121@25+5→5, 122@30+3→6, 123@33+3→none, 124@36+4→8, 125@40+4→10, 126@44+4→11, 127@48+3→13, 128@51+4→14, 129@55+19→15 | 17 | y_up | `kakashi-kit-2026-09-12/up_y`: 74/74, +96 | box clock measured, cells static |
| `down Y` | 0x25 | 46 | 136@0+2→0/4, 137@2+3→1, 138@5+3→2, 139@8+8→3, 140@16+3→0/4, 141@19+3→5, 142@22+24→6 | 142 | y_down | `kakashi-kit-2026-09-12/down_y`: 46/46, +49 | box clock measured, cells static |
| `air Y` | 0x27 | 30 | 149@0+4→0/4, 150@4+11→1, 151@15+3→2, 152@18+4→none, 153@22+4→3, 149@26+4→0/4 | 149 | y_jump | `kakashi-kit-2026-09-12/air_y`: 30/30, +55 | box clock measured, cells static |

Specials (koma set, anim in the base amt, art in the koma archive):

| move | koma | anim | frames | cells: cell@start+len→strip frame | strip | plays (capture: agree/checked, idle return) | hits (col record: what) | grade |
|---|---|---|---|---|---|---|---|---|
| `X` | 4 | 0x29 | 79 | 1@0+4→0, 2@4+4→1, 3@8+15→2, 4@23+4→3, 5@27+4→4, 4@31+4→3, 5@35+4→4, 4@39+4→3, 5@43+4→4, 4@47+4→3, 5@51+8→4, 4@59+8→3, 5@67+4→4, 4@71+4→3, 6@75+4→5 | x_beam_k4 | X `kakashi-specials-2026-09-25/trials/K/X_near_1`: 79/79, +82 | 19: the emitter and all 17 bolts | box clock measured on 1 path, cells static, strip frames matched on the sheet (special-strips.json) |
| `up X` | 4 | 0x2a | 78 | 7@0+3→0, 8@3+3→1, 9@6+3→2, 10@9+3→3, 11@12+6→4, 12@18+3→5, 13@21+20→6, 12@41+3→5, 14@44+3→7, 15@47+3→8, 16@50+28→9 | up_x_dogs_k4 | up X `kakashi-specials-2026-09-25/trials/K/upX_near`: 78/78, +81 | 20: dog 1, 21: dog 2, 22: dog 3, 23: dog 4 | box clock measured on 1 path, cells static, strip frames matched on the sheet (special-strips.json) |
| `X` | 5 | 0x2b | 229 | 0@0+3→0, 1@3+3→1, 2@6+3→2, 3@9+3→3, 4@12+4→4, 5@16+4→5, 4@20+4→4, 5@24+4→5, 4@28+4→4, 5@32+4→5, 4@36+4→4, 5@40+4→5, 4@44+4→4, 5@48+14→5, 6@62+4→6, 7@66+4→7, 6@70+11→6, 11@81+12→11, 6@93+4→6, 7@97+4→7, 6@101+4→6, 7@105+2→7, 6@107+9→6, 11@116+12→11, 6@128+4→6, 7@132+4→7, 6@136+4→6, 7@140+4→7, 6@144+11→6, 11@155+12→11, 6@167+4→6, 8@171+4→8, 9@175+4→9, 10@179+4→10, 9@183+4→9, 10@187+37→10, 11@224+5→11 | x_raikiri_k5 | tap (level 1, near) `kakashi-5-6koma-specials-2026-09-27/trials/A/5X_tap`: 0/0, +96; hold 60 (level 2) `kakashi-5-6koma-specials-2026-09-27/trials/A/5Xm_h60`: 0/0, +88; hold 120 (level 3) `kakashi-5-6koma-specials-2026-09-27/trials/A/5X_h120`: 0/0, +156 | 24: the dash box (0 damage; enabled on the dash segments), 25: hit 1 (10, type 1), 26: hit 2 (10, type 2), 27: hit 3 (16, type 6) | start and idle return measured on 3 paths (no body box read, so no frame is checked), cells static, strip frames matched on the sheet (special-strips.json) |
| `up X` | 5 | 0x2c | 94 | 12@0+3→0, 13@3+3→1, 14@6+3→2, 15@9+3→3, 16@12+6→4, 17@18+3→5, 18@21+20→6, 17@41+3→5, 19@44+3→7, 20@47+3→8, 21@50+44→9 | up_x_dogs_k5 | the summon `kakashi-5-6koma-specials-2026-09-27/trials/A/5upX_tap`: 0/0, +97 | 28: a dog (4, type 2), 29: a dog (4, type 1), 30: a dog (1, type 1), 36: a dog (5, type 2) | start and idle return measured on 1 path (no body box read, so no frame is checked), cells static, strip frames matched on the sheet (special-strips.json) |
| `X` | 6 | 0x2d | 252 | 0@0+3→0, 1@3+3→1, 2@6+3→2, 3@9+3→3, 4@12+4→4, 5@16+4→5, 4@20+4→4, 5@24+4→5, 4@28+4→4, 5@32+4→5, 4@36+4→4, 5@40+4→5, 4@44+4→4, 5@48+14→5, 6@62+4→6, 7@66+4→7, 6@70+13→6, 11@83+12→11, 6@95+4→6, 7@99+4→7, 6@103+4→6, 7@107+4→7, 6@111+13→6, 11@124+12→11, 6@136+4→6, 7@140+4→7, 6@144+4→6, 7@148+4→7, 6@152+4→6, 7@156+4→7, 6@160+9→6, 11@169+12→11, 6@181+4→6, 8@185+4→8, 9@189+4→9, 10@193+4→10, 9@197+4→9, 10@201+46→10, 11@247+5→11 | x_chidori_k6 | tap (level 1, near) `kakashi-5-6koma-specials-2026-09-27/trials/A/6X_tap`: 0/0, +103; hold 60 (level 2) `kakashi-5-6koma-specials-2026-09-27/trials/A/6Xm_h60`: 0/0, +94; hold 120 (level 3) `kakashi-5-6koma-specials-2026-09-27/trials/A/6X_h120`: 0/0, +165 | 31: the dash box (0 damage; enabled on the dash segments), 32: hit 1 (2, type 1), 33: hit 2 (2, type 2), 34: hit 3 (40, type 6) | start and idle return measured on 3 paths (no body box read, so no frame is checked), cells static, strip frames matched on the sheet (special-strips.json) |
| `up X` | 6 | 0x2e | 56 | 12@0+4→0, 13@4+4→1, 14@8+4→2, 13@12+4→1, 14@16+4→2, 13@20+8→1, 14@28+4→2, 13@32+4→1, 14@36+4→2, 15@40+4→3, 16@44+4→4, 17@48+4→5, 18@52+4→6 | up_x_mangekyou_k6 | the eye `kakashi-5-6koma-specials-2026-09-27/trials/A/6upX_tap`: 0/0, +195 | 35: the eye (3, type 1, every 8 frames while it overlaps) | start and idle return measured on 1 path (no body box read, so no frame is checked), cells static, strip frames matched on the sheet (special-strips.json) |

Moves whose idle return is not `frames + 3` (each needs an override):

| move | anim | frames | frames + 3 | idle return | why |
|---|---|---|---|---|---|
| `air B` | 0x26 | 26 | 29 | +62 | ends in the air: state 6 (fall) at +29 = frames + 3, lands (state 13) at +43, idle at +62. The fall and the landing window belong to the jump, not the move |
| `side Y (mashed)` | 0x21 | 56 | 59 | +89 | mashing Y adds 30 game frames somewhere in anim frames 4 to 35 (the box key at 36 lands 30 late; the boxes do not change from 4 to 35). Idle at 56 + 30 + 3 = +89 |
| `up Y` | 0x23 | 74 | 77 | +96 | ends in the air: state 6 (fall) at +77 = frames + 3, idle at +96 with no state-13 frame logged |
| `air Y` | 0x27 | 30 | 33 | +55 | ends in the air: state 6 (fall) at +33 = frames + 3, lands (state 13) at +36, idle at +55 |
| `X` 5 | 0x2b | 229 | 232 | tap (level 1, near): +96; hold 60 (level 2): +88; hold 120 (level 3): +156 | the move (state 10) ends when the dash stops, not when the anim ends: each frame v = v - (v >> 3) + push, and a speed under 16 raw becomes 0 (C3 §2). So the idle return follows the level and the hold |
| `X` 6 | 0x2d | 252 | 255 | tap (level 1, near): +103; hold 60 (level 2): +94; hold 120 (level 3): +165 | the move (state 10) ends when the dash stops, not when the anim ends: each frame v = v - (v >> 3) + push, and a speed under 16 raw becomes 0 (C3 §2). So the idle return follows the level and the hold |
| `up X` 6 | 0x2e | 56 | 59 | +195 | the anim is 56 frames but Kakashi stays in state 10 for 195: he holds while the eye flies (C3 §6) |

| anim | frames | loop | cells: cell@start+len→strip frame | strip | evidence | grade |
|---|---|---|---|---|---|---|
| 0x00 | 52 | loop | 0@0+6→0, 1@6+6→1/5, 2@12+8→2/4, 3@20+12→3, 2@32+8→2/4, 1@40+12→1/5 | stand | none | static |
| 0x01 | 32 | loop | 4@0+4→0, 5@4+4→1, 6@8+4→2, 7@12+4→3, 8@16+4→4, 9@20+4→5, 10@24+4→6, 11@28+4→7 | walk | none | static |
| 0x02 | 12 | hold | 12@0+3→0, 13@3+6→1, 12@9+3→0 | dash | dash: 12/12, also fits 0x00/0x01 | start measured, cells static |
| 0x03 | 12 | hold | 14@0+4→0, 15@4+4→1, 16@8+4→2 | block | none | static |
| 0x04 | 8 | hold | 17@0+4→1/4, 18@4+4→2/5 | jump | jump rise: 8/8 | start measured, cells static |
| 0x05 | 4 | hold | 19@0+4→3 | jump | none | static |
| 0x06 | 8 | hold | 17@0+4→1/4, 18@4+4→2/5 | jump | none | static |
| 0x07 | 8 | hold | 20@0+4→6, 21@4+4→7 | jump | landing (from the frame before state 13): 8/8 | start measured, cells static |
| 0x08 | 4 | hold | 22@0+4→0/8 | jump | jump squat (state 4): 4/4; landing end, from the last frame of state 13: 4/4; landing end, from one frame later (fits too): 4/4 | start measured, cells static |
| 0x09 | 4 | hold | 23@0+4→none | none | none | static |
| 0x0a | 4 | hold | 25@0+4→1 | hit | none | static |
| 0x0b | 4 | hold | 24@0+4→2 | hit | none | static |
| 0x0c | 4 | hold | 26@0+4→0 | hit | none | static |
| 0x0d | 4 | hold | 38@0+4→3 | hit | none | static |
| 0x0e | 8 | loop | 29@0+4→none, 30@4+4→none | none | none | static |
| 0x0f | 16 | hold | 28@0+4→4, 27@4+4→5, 28@8+4→4, 33@12+4→6 | down | none | static |
| 0x10 | 4 | hold | 27@0+4→5 | down | none | static |
| 0x11 | 4 | hold | 28@0+4→4 | down | none | static |
| 0x12 | 8 | loop | 31@0+4→none, 32@4+4→none | none | none | static |
| 0x13 | 16 | loop | 34@0+4→0, 35@4+4→1, 36@8+4→2, 37@12+4→3 | down | none | static |
| 0x14 | 36 | loop | 39@0+10→none, 40@10+8→none, 41@18+10→none, 40@28+8→none | none | none | static |
| 0x15 | 17 | hold | 42@0+4→none, 43@4+2→none, 44@6+2→none, 45@8+3→none, 46@11+3→none, 47@14+3→none | none | none | static |
| 0x16 | 16 | loop | 48@0+4→none, 49@4+4→none, 50@8+4→none, 51@12+4→none | none | none | static |
| 0x17 | 16 | hold | 52@0+4→7, 53@4+4→8, 54@8+4→9, 55@12+4→10 | down | none | static |
| 0x18 | 34 | hold | 56@0+3→none, 57@3+3→none, 58@6+4→none, 59@10+4→none, 58@14+4→none, 59@18+4→none, 57@22+4→none, 56@26+8→none | none | none | static |
| 0x19 | 54 | hold | 61@0+8→none, 62@8+5→none, 63@13+5→none, 64@18+4→none, 65@22+4→none, 66@26+4→none, 67@30+4→none, 66@34+4→none, 67@38+4→none, 74@42+12→none | none | none | static |
| 0x1a | 36 | hold | 68@0+6→none, 69@6+4→none, 70@10+6→none, 71@16+8→none, 72@24+6→none, 73@30+6→none | none | none | static |
| 0x28 | 42 | hold | 83@0+3→0, 85@3+3→2, 86@6+3→3, 87@9+3→4, 88@12+4→5, 89@16+8→6, 90@24+8→7, 91@32+10→8 | y_attack | none | static |
| 0x33 | 4 | hold | 163@0+4→none | none | none | static |
| 0x34 | 4 | hold | 164@0+4→none | none | none | static |
| 0x35 | 4 | hold | 165@0+4→none | none | none | static |
| 0x36 | 4 | hold | 166@0+4→none | none | none | static |

<!-- /generated:anim-timing kakashi -->

Pointer for the `side Y (mashed)` row and the idle table above: the mash table and mash_path.py show the loop is f35 to f21, run twice (15 ticks each, 30 frames); see docs/rebuild/mash-table.md, "Reference model".

Notes for Kakashi:

- **Jump** (measured in `air_b` and `air_y` from P1's state codes and
  boxes). The squat is 0x08 (cell 22) for the 4 frames of state 4. The rise
  0x04 (cells 17, 18) starts on the fifth frame; its box stays until the
  air attack, so it holds cell 18 (the hold rule). After an air move, the
  fall shows 0x05 or 0x06. Their boxes are the same, so which one is TBD
  (0x05 is cell 19, strip frame 3; 0x06 is cells 17 and 18). The landing
  0x07 (cells 20, 21) starts one frame before state 13. On the last frame
  of state 13, 0x08's box (cell 22) shows for 5 frames, then stand's. 0x08
  is only 4 frames long and its box never changes, so its start fits on
  the last state-13 frame or one frame later (both checks are in the
  JSON), and one of the 5 frames is not accounted for. Where 0x08 starts,
  and what the extra frame shows, is TBD. The
  strip order (22, 17, 18, 19, 17, 18, 20, 21, 22) is that sequence. A
  plain jump with no attack has not been checked.
- **Dash** (start measured): 0x02 is live for the 12 frames of the dash
  burst. Its box equals stand's and walk's, so the cell timing inside it is
  static.
- **Hit and down** are static. The four `hit` strip frames are the one-cell
  animations 0x0c, 0x0a, 0x0b and 0x0d (cells 26, 25, 24, 38). 0x09 (cell
  23) is not in the strip. Which reaction plays which of them is TBD. The
  `down` strip is 0x13 (cells 34 to 37, loops), then 0x0f (cells 28, 27, 28,
  33), then 0x17 (cells 52 to 55): 11 frames in that order.
- **Down B has no `b_down` strip, but the `y_down` strip can draw it.**
  Down B's cells (130 to 135) look the same as down Y's (136 to 142), and
  both match the `y_down` frames in order (down B: frames 0, 1, 2, 3, 5, 6;
  down Y: all seven). Inferred from the image match.
- **Side Y, mashed** (`side_y_mash/a` and `/b`, idle +89): the same
  animation 0x21, with 30 extra game frames. The box key at animation
  frame 36 lands 30 frames late, and the boxes do not change between
  frames 4 and 35, so the 30 frames sit somewhere in there. The legacy
  captures throw 6 shuriken instead of 2 (kakashi.md §2), which suggests
  the throw cells 103 to 108 repeat (inferred). Which cells repeat, and
  how often, is TBD (`jus-wmqi.6.11`). The JSON records it as a 30-frame pause before frame
  36; that is only where the delay is measured, not where it is drawn.
  Pointer: the mash table and mash_path.py show the loop is f35 to f21, run twice (15 ticks each) (30 frames). Which cells repeat is still TBD; see docs/rebuild/mash-table.md, "Reference model".
- **0x28** is a 42-frame copy of `Y`'s cells without cell 84. No capture
  shows it; what plays it is TBD.

## 3. Yusuke (`chr_b` 32, `yh_b_01`)

<!-- generated:anim-timing yusuke -->

| move | anim | frames | cells: cell@start+len→strip frame | end cell | strip | check (capture: agree/checked, idle return) | grade |
|---|---|---|---|---|---|---|---|
| `B` | 0x1e | 27 | 71@0+4→0, 72@4+3→1, 73@7+12→2, 74@19+4→3, 75@23+4→4 | 75 | b_attack | `yusuke-kit2-2026-09-22/geometry1/B_idle`: 27/27, +30 | box clock measured, cells measured |
| `side B` | 0x20 | 34 | 83@0+4→0, 84@4+4→1, 85@8+4→2, 86@12+4→3, 87@16+6→4, 88@22+4→5, 89@26+4→6, 90@30+4→7 | 90 | b_forward | `yusuke-kit2-2026-09-22/geometry1/side_B_idle`: 34/34, +37 | box clock measured, cells static |
| `up B` | 0x22 | 33 | 100@0+3→0, 101@3+5→1, 102@8+3→2, 103@11+3→3, 104@14+8→4, 105@22+7→5, 17@29+4→6 | 17 | b_up | `yusuke-kit2-2026-09-22/geometry1/up_B_idle`: 33/33, +46 | box clock measured, cells static |
| `down B` | 0x24 | 43 | 108@0+11→0, 115@11+5→1, 116@16+5→none, 117@21+5→3, 118@26+7→4, 119@33+10→5 | 119 | b_down | `yusuke-kit2-2026-09-22/geometry1/down_B_idle`: 43/43, +46 | box clock measured, cells static |
| `air B` | 0x26 | 50 | 127@0+3→0, 128@3+6→1, 129@9+3→2, 130@12+9→3, 131@21+19→4, 130@40+6→3, 131@46+4→4 | 131 | b_jump | `yusuke-kit-2026-09-22/geometry/air_B_idle`: 26/26, +46; **draw anim frames 0–25 only, then landing (0x07 from anim frame 26, state 13 from +27)** | box clock measured to anim frame 25, cells static |
| `Y` | 0x1f | 56 | 76@0+8→0, 77@8+8→1/2/3/4, 78@16+10→5/6/7/8, 79@26+18→9, 80@44+4→10, 81@48+4→11, 82@52+4→12 | 82 | y_attack | `yusuke-kit2-2026-09-22/geometry1/Y_idle`: 56/56, +59 | box clock measured, cells measured |
| `side Y` | 0x21 | 136 | 92@0+12→0/1/2/3, 93@12+4→4, 94@16+4→5, 95@20+4→6, 96@24+5→7/8/9, 97@29+5→10, 98@34+5→11, 99@39+21→12, 94@60+4→5, 95@64+4→6, 96@68+5→7/8/9, 97@73+5→10, 98@78+5→11, 99@83+18→12, 94@101+4→5, 95@105+4→6, 96@109+5→7/8/9, 97@114+5→10, 98@119+5→11, 99@124+12→12 | 99 | y_forward | `yusuke-kit-2026-09-22/geometry/side_Y_idle`: 51/51, +53 | box clock measured to anim frame 50, cells static |
| `up Y` | 0x23 | 61 | 108@0+4→0, 109@4+12→1/2/3, 110@16+3→4/5, 111@19+4→6/7/8, 112@23+30→9/10, 113@53+4→11, 114@57+4→12 | 114 | y_up | `yusuke-kit2-2026-09-22/geometry1/up_Y_idle`: 61/61, +64 | box clock measured, cells static |
| `down Y` | 0x25 | 54 | 120@0+6→0, 121@6+7→1, 122@13+19→2, 123@32+3→3, 124@35+3→4, 125@38+12→5, 126@50+4→6 | 126 | y_down | `yusuke-kit2-2026-09-22/geometry1/down_Y_idle`: 54/54, +57 | box clock measured, cells static |
| `air Y` | 0x27 | 127 | 132@0+4→none, 133@4+12→0/1/2/3, 134@16+4→4, 135@20+4→none, 136@24+18→none, 137@42+16→8, 134@58+4→4, 135@62+4→none, 136@66+18→none, 137@84+13→8, 134@97+4→4, 135@101+4→none, 136@105+18→none, 137@123+4→8 | 137 | y_jump | `yusuke-kit2-2026-09-22/geometry1/air_Y_idle`: 48/48, +86; **draw anim frames 0–47 only, then fall (0x05/0x06 boxes from anim frame 48)** | box clock measured to anim frame 47, cells measured to anim frame 47 |

Specials (koma set, anim in the base amt, art in the koma archive):

| move | koma | anim | frames | cells: cell@start+len→strip frame | strip | plays (capture: agree/checked, idle return) | hits (col record: what) | grade |
|---|---|---|---|---|---|---|---|---|
| `X` | 4 | 0x29 | 61 | 0@0+4→0, 1@4+3→1, 2@7+3→2, 1@10+3→1, 2@13+3→2, 1@16+3→1, 3@19+4→3, 4@23+4→4, 5@27+4→5, 6@31+5→6, 7@36+4→7, 8@40+4→8, 16@44+7→none, 9@51+10→9 | x_spirit_gun_k4 | tap `yusuke-4-5koma-specials-2026-09-27/trials2/A/4X_tap`: 0/0, +64; hold 120 (the same) `yusuke-4-5koma-specials-2026-09-27/trials2/A/4X_h120`: 0/0, +64 | 22: the shot (28, type 5) | start and idle return measured on 2 paths (no body box read, so no frame is checked), cells static, strip frames matched on the sheet (special-strips.json) |
| `up X` | 4 | 0x2a | 71 | 10@0+3→0, 11@3+3→1, 12@6+3→2, 11@9+3→1, 12@12+3→2, 11@15+6→1, 12@21+3→2, 11@24+3→1, 13@27+8→none, 14@35+24→3, 15@59+4→4, 16@63+4→5, 17@67+4→6 | up_x_rei_kou_dan_k4 | tap `yusuke-4-5koma-specials-2026-09-27/trials2/K/4upX_tap`: 71/71, +74 | 23: hits 1-4 (2, type 1), 24: hit 5, the finisher (20, type 6) | box clock measured on 1 path, cells static, strip frames matched on the sheet (special-strips.json) |
| `X` | 5 | 0x2b | 120 | 0@0+4→0, 1@4+3→1, 2@7+3→2, 1@10+3→1, 2@13+3→2, 1@16+3→1, 2@19+3→2, 1@22+3→1, 2@25+3→2, 1@28+3→1, 2@31+3→2, 1@34+3→1, 2@37+3→2, 1@40+3→1, 2@43+3→2, 1@46+10→1, 3@56+4→3, 4@60+4→4, 5@64+4→5, 6@68+4→6, 7@72+4→7, 8@76+4→8, 9@80+12→9, 3@92+4→3, 4@96+4→4, 5@100+4→5, 6@104+4→6, 7@108+4→7, 8@112+4→8, 9@116+4→9 | x_spirit_gun_k5 | tap (level 1) `yusuke-4-5koma-specials-2026-09-27/trials2/Q/5X_tap`: 49/49, +50; hold 65 (level 1) `yusuke-4-5koma-specials-2026-09-27/trials2/Q/5X_h65`: 93/93, +94; hold 66 (level 2) `yusuke-4-5koma-specials-2026-09-27/trials2/Q/5X_h66`: 93/93, +96; hold 120 (level 2) `yusuke-4-5koma-specials-2026-09-27/trials2/Q/5X_h120`: 147/147, +150; hold 300 (level 2) `yusuke-4-5koma-specials-2026-09-27/trials2/Q/5X_h300`: 327/327, +330 | 25: level 1's shot (32, type 6), 26: level 2's shot (44, type 5) | box clock measured on 5 paths (held spans: which frame shows is not measured), cells static, strip frames matched on the sheet (special-strips.json) |
| `up X` | 5 | 0x2c | 96 | 10@0+4→0, 11@4+3→1, 12@7+3→2, 11@10+3→1, 12@13+3→2, 11@16+3→1, 12@19+3→2, 11@22+3→1, 12@25+3→2, 11@28+3→1, 13@31+6→none, 14@37+2→none, 15@39+2→3, 14@41+2→none, 15@43+2→3, 14@45+2→none, 15@47+2→3, 14@49+2→none, 15@51+2→3, 14@53+2→none, 15@55+2→3, 14@57+2→none, 15@59+25→3, 16@84+4→4, 17@88+4→5, 18@92+4→6 | up_x_rei_kou_dan_k5 | tap `yusuke-4-5koma-specials-2026-09-27/trials2/K/5upX_tap`: 96/96, +99; wait 42 first `yusuke-4-5koma-specials-2026-09-27/trials2/K/5upX_w42`: 96/96, +99 | 27: hits 1-7 (2, type 1), 28: the finisher (20, type 6) | box clock measured on 2 paths, cells static, strip frames matched on the sheet (special-strips.json) |
| `X` | 6 | 0x2d | 108 | 0@0+4→0, 1@4+3→1, 2@7+3→2, 1@10+3→1, 2@13+3→2, 1@16+3→1, 2@19+3→2, 1@22+3→1, 2@25+3→2, 1@28+3→1, 2@31+5→2, 3@36+4→3, 4@40+8→4, 5@48+4→5, 6@52+4→6, 7@56+4→7, 8@60+4→8, 9@64+12→9, 3@76+4→3, 4@80+8→4, 5@88+4→5, 6@92+4→6, 7@96+4→7, 8@100+4→8, 9@104+4→9 | x_spirit_gun_k6 | tap (level 1) `yusuke-6koma-specials-2026-09-24/trials/H3/X_tap`: 64/64, +67; hold 72 (level 1) `yusuke-6koma-specials-2026-09-24/trials/H3/X_h72`: 103/103, +106; hold 73 (level 2) `yusuke-6koma-specials-2026-09-24/trials/H3/X_h73`: 93/93, +94; hold 120 (level 2, charged pose) `yusuke-6koma-specials-2026-09-24/trials/H3/X_h120`: 140/140, +141 | 29: level 1's ball, 30: level 2's ball | box clock measured on 4 paths (held spans: which frame shows is not measured), cells static, strip frames matched on the sheet (special-strips.json) |
| `up X` | 6 | 0x2e | 132 | 36@0+3→0, 10@3+4→1, 12@7+3→2, 13@10+3→none, 14@13+3→3, 15@16+3→4, 16@19+9→5, 10@28+5→1, 36@33+10→0, 16@43+4→5, 17@47+3→6, 18@50+3→7, 19@53+3→8, 20@56+3→none, 21@59+2→9, 22@61+3→10, 23@64+3→11, 22@67+3→10, 24@70+3→12, 22@73+3→10, 23@76+3→11, 22@79+3→10, 24@82+3→12, 25@85+4→13, 26@89+3→14, 27@92+3→15, 28@95+3→16, 29@98+7→17, 30@105+3→18, 31@108+8→19, 32@116+3→20, 33@119+3→21, 34@122+4→22, 10@126+3→1, 36@129+3→0 | up_x_awakening_k6 | the rush hits `yusuke-6koma-specials-2026-09-24/trials/G2/upX_near`: 124/124, +127 | 16: hit 1, 17: hit 2, 18: hits 3 and 5, 19: hits 4 and 6, 20: hit 7, the launcher, 21: the finishing shot | box clock measured on 1 path (held spans: which frame shows is not measured), cells static, strip frames matched on the sheet (special-strips.json) |

Moves whose idle return is not `frames + 3` (each needs an override):

| move | anim | frames | frames + 3 | idle return | why |
|---|---|---|---|---|---|
| `up B` | 0x22 | 33 | 36 | +46 | ends in the air: state 6 (fall) at +36 = frames + 3, idle at +46 with no state-13 frame logged |
| `air B` | 0x26 | 50 | 53 | +46 | lands before the animation ends: the landing starts at anim frame 26 (state 13 at +27), idle at +46 |
| `side Y` | 0x21 | 136 | 139 | +53 | the unempowered first phase ends at native End key 51, idle at +53; all 51 captured frames match directly. The 136-frame header includes the stored-UA phases. The old 0x28 fit required an artificial 8-frame pause before frame 8 |
| `air Y` | 0x27 | 127 | 130 | +86 | the attack ends in the air at anim frame 48 (state 6), 79 frames short of the 127-frame animation; cause TBD. Lands (state 13) at +67, idle at +86. A different jump (jump A 0-7, Y at plan 15) gives +94 instead, so +86 depends on the jump, not on air Y alone (inferred; yusuke-xcancel-airy-2026-09-25/RESULTS.md) |
| `X` 5 | 0x2b | 120 | 123 | tap (level 1): +50; hold 65 (level 1): +94; hold 66 (level 2): +96; hold 120 (level 2): +150; hold 300 (level 2): +330 | the hold sets it, not the 120-frame anim: the anim waits in frames 4-55 while X is held, then level 1 plays 56-84 and idles 30 frames after the switch, level 2 plays 92-119 and idles 31 after it |
| `X` 6 | 0x2d | 108 | 111 | tap (level 1): +67; hold 72 (level 1): +106; hold 73 (level 2): +94; hold 120 (level 2, charged pose): +141 | the hold and the level set it, not the 108-frame anim: level 1 plays 76-107 and idles 35 frames after the switch, level 2 plays 48-68 and idles 22 after it |
| `up X` 6 | 0x2e | 132 | 135 | +127 | on a hit the anim skips frames 21-42 (22 frames) and waits 14 game frames in 100-104, so it runs 132 - 22 + 14 = 124 game frames and idles at 124 + 3. That is the hit path; a whiff stops after the first strike (C2's summary) |

| anim | frames | loop | cells: cell@start+len→strip frame | strip | evidence | grade |
|---|---|---|---|---|---|---|
| 0x00 | 60 | loop | 0@0+10→0, 1@10+10→1, 2@20+10→2, 3@30+10→3, 2@40+10→2, 1@50+10→1 | stand | none | static |
| 0x01 | 32 | loop | 4@0+4→0, 5@4+4→1, 6@8+4→2, 7@12+4→3, 8@16+4→4, 9@20+4→5, 10@24+4→6, 11@28+4→7 | walk | none | static |
| 0x02 | 12 | hold | 12@0+3→0, 13@3+3→1, 12@6+3→0, 13@9+3→1 | dash | dash: 12/12 | start measured, cells static |
| 0x03 | 12 | hold | 14@0+4→0, 15@4+4→1, 16@8+4→2 | block | none | static |
| 0x04 | 4 | hold | 17@0+4→1 | jump | jump rise: 4/4 | start measured, cells static |
| 0x05 | 4 | hold | 18@0+4→2 | jump | none | static |
| 0x06 | 4 | hold | 18@0+4→2 | jump | none | static |
| 0x07 | 8 | hold | 19@0+4→0/3/5, 20@4+4→4 | jump | none | static |
| 0x08 | 4 | hold | 19@0+4→0/3/5 | jump | none | static |
| 0x09 | 4 | hold | 21@0+4→none | none | none | static |
| 0x0a | 4 | hold | 23@0+4→0 | hit | none | static |
| 0x0b | 4 | hold | 22@0+4→2 | hit | none | static |
| 0x0c | 4 | hold | 24@0+4→1 | hit | none | static |
| 0x0d | 4 | hold | 32@0+4→3 | hit | none | static |
| 0x0e | 8 | loop | 33@0+4→none, 34@4+4→none | none | none | static |
| 0x0f | 16 | hold | 26@0+4→5, 25@4+4→none, 26@8+4→5, 27@12+4→6 | down | none | static |
| 0x10 | 4 | hold | 25@0+4→none | none | none | static |
| 0x11 | 4 | hold | 26@0+4→5 | down | none | static |
| 0x12 | 8 | loop | 35@0+4→none, 36@4+4→none | none | none | static |
| 0x13 | 16 | loop | 28@0+4→1, 29@4+4→2, 30@8+4→3, 31@12+4→none | down | none | static |
| 0x14 | 32 | loop | 37@0+8→none, 38@8+8→none, 39@16+8→none, 38@24+8→none | none | none | static |
| 0x15 | 24 | hold | 40@0+4→none, 41@4+4→none, 42@8+4→none, 43@12+4→none, 44@16+4→none, 45@20+4→none | none | none | static |
| 0x16 | 16 | loop | 46@0+4→none, 47@4+4→none, 48@8+4→none, 49@12+4→none | none | none | static |
| 0x17 | 16 | hold | 50@0+4→7, 51@4+4→8, 52@8+4→9, 53@12+4→10 | down | none | static |
| 0x18 | 57 | hold | 54@0+4→none, 55@4+4→none, 54@8+4→none, 55@12+4→none, 54@16+4→none, 55@20+4→none, 56@24+4→none, 57@28+4→none, 56@32+4→none, 57@36+4→none, 56@40+9→none, 54@49+4→none, 55@53+4→none | none | none | static |
| 0x19 | 40 | hold | 58@0+4→none, 59@4+8→none, 60@12+4→none, 61@16+4→none, 62@20+4→none, 63@24+4→none, 64@28+4→none, 65@32+4→none, 66@36+4→none | none | none | static |
| 0x1a | 52 | hold | 67@0+4→none, 68@4+6→none, 69@10+6→none, 70@16+6→none, 69@22+6→none, 68@28+6→none, 69@34+6→none, 70@40+6→none, 69@46+6→none | none | none | static |
| 0x28 | 43 | hold | 92@0+4→0/1/2/3, 93@4+4→4, 94@8+4→5, 95@12+4→6, 96@16+5→7/8/9, 97@21+5→10, 98@26+5→11, 99@31+12→12 | y_forward | none | static |
| 0x33 | 4 | hold | 147@0+4→none | none | none | static |
| 0x34 | 4 | hold | 148@0+4→none | none | none | static |
| 0x35 | 4 | hold | 149@0+4→none | none | none | static |
| 0x36 | 4 | hold | 150@0+4→none | none | none | static |

<!-- /generated:anim-timing yusuke -->

Notes for Yusuke:

- **Side Y** pauses for 8 game frames before animation frame 8 (§1.2). The
  same check passes on `side_Y_idle`, `side_Y_far` and `side_Y_mash`.
  Mashing did not change the matched box clock: all three fit 0x28.
  The native table-driven side-Y start selects 0x21, and its key 29 matches
  the live cancel flag. The geometry-capture identity remains unresolved;
  see the J8 evidence note.
- **The `y_attack` strip is neutral Y's art.** All 13 frames match Y's
  cells 76 to 82 in order. Frames 2 to 4 (cell 77) and 6 to 8 (cell 78)
  hold the body cell plus other art (`weak` or `extra`). So the earlier guess
  that this row is side Y's art does not hold; `y_forward` is side Y.
- **Jump.** Only the rise is measured: 0x04 (cell 17) starts on the fifth
  frame of state 4 and its box stays until the air attack. After an air
  move the fall shows 0x05 or 0x06 (both cell 18; same boxes). Squat 0x08
  and landing 0x07 have the stand box, so the capture cannot place them.
  The strip order (19, 17, 18, 19, 20, 19) matches Kakashi's sequence:
  squat, rise, fall, landing, squat again (inferred).
- **Hit and down** are static. `hit` = 0x0a, 0x0c, 0x0b, 0x0d (cells 23,
  24, 22, 32); 0x09 (cell 21) is not in the strip. `down` = frame 0 (no
  cell), 0x13 (cells 28 to 30; 31 not found), frame 4 (no cell), 0x0f
  (cells 26 and 27; 25 not found), 0x17 (cells 50 to 53).
- **Air B lands before its animation ends; air Y does not land, it stops**
  (§1). Air Y's attack state ends in the air at animation frame 48, and the
  fall boxes follow. Its 127 frames repeat cells 134 to 137 three times;
  only the first 48 frames are ever shown in this capture. Cause TBD
  (`jus-wmqi.6.10`).
- **B, Y and air Y's cells are now measured, not just static.** A live RAM
  field (`0x023C1712`/`0x023C1720` in `cm-yusuke-6`) read the same cell per
  frame as the static rows above for anim frames 0-47 of air Y, and for
  B and Y in full. Past anim frame 47, air Y's fall (18), landing (19/20/19)
  and idle cells never appear in the strip table above; they were measured
  at frame 18@48, 19@71, then landing 19/20/19 @72-93, idle @94. The shot
  spawns on anim frame 20 (measured; `yusuke-xcancel-airy-2026-09-25/RESULTS.md`,
  `checks.json`).

## 3a. Eve (`chr_b` 37, `bc_b_01`)

<!-- generated:anim-timing eve -->

| move | anim | frames | cells: cell@start+len→strip frame | end cell | strip | check (capture: agree/checked, idle return) | grade |
|---|---|---|---|---|---|---|---|
| `B` | 0x1e | 29 | 79@0+3→none, 80@3+5→none, 81@8+3→none, 82@11+10→none, 83@21+4→none, 84@25+4→none | 84 | none | `2026-10-12-eve-base/geometry/L/B_idle`: 29/29, +32 | box clock measured, cells static |
| `side B` | 0x20 | 31 | 91@0+4→none, 92@4+5→none, 93@9+4→none, 94@13+8→none, 95@21+4→none, 96@25+3→none, 97@28+3→none | 97 | none | `2026-10-12-eve-base/geometry/L/side_B_idle`: 31/31, +34 | box clock measured, cells static |
| `up B` | 0x22 | 25 | 111@0+4→none, 112@4+4→none, 113@8+3→none, 114@11+6→none, 115@17+4→none, 116@21+4→none | 116 | none | `2026-10-12-eve-base/geometry/L/up_B_idle`: 25/25, +28 | box clock measured, cells static |
| `down B` | 0x24 | 40 | 127@0+4→none, 128@4+8→none, 129@12+4→none, 130@16+4→none, 131@20+4→none, 132@24+4→none, 133@28+4→none, 134@32+4→none, 135@36+4→none | 135 | none | `2026-10-12-eve-base/geometry/L/down_B_idle`: 40/40, +43 | box clock measured, cells static |
| `air B` | 0x26 | 29 | 146@0+7→none, 147@7+2→none, 148@9+2→none, 149@11+9→none, 150@20+3→none, 151@23+3→none, 152@26+3→none | 152 | none | `2026-10-12-eve-base/geometry/L/air_B_idle`: 29/29, +62 | box clock measured, cells static |
| `Y` | 0x1f | 48 | 85@0+5→none, 86@5+11→none, 87@16+3→none, 88@19+3→none, 89@22+22→none, 90@44+4→none | 90 | none | `2026-10-12-eve-base/geometry/L/Y_idle`: 48/48, +51 | box clock measured, cells static |
| `side Y` | 0x21 | 117 | 98@0+11→none, 99@11+5→none, 100@16+4→none, 101@20+12→none, 109@32+7→none, 110@39+7→none, 97@46+20→none, 101@66+3→none, 102@69+8→none, 103@77+4→none, 104@81+4→none, 105@85+5→none, 106@90+6→none, 109@96+7→none, 110@103+7→none, 97@110+7→none | 97 | none | `2026-10-12-eve-base/geometry/L/side_Y_idle`: 61/61, +62; **draw anim frames 0–60 only, then the stand boxes (idle at +62)** | box clock measured to anim frame 60, cells static |
| `up Y` | 0x23 | 45 | 117@0+4→none, 118@4+11→none, 119@15+4→none, 120@19+4→none, 121@23+3→none, 122@26+3→none, 123@29+4→none, 124@33+4→none, 125@37+4→none, 126@41+4→none | 126 | none | `2026-10-12-eve-base/geometry/L/up_Y_idle`: 45/45, +67 | box clock measured, cells static |
| `down Y` | 0x25 | 56 | 136@0+5→none, 137@5+5→none, 138@10+5→none, 139@15+19→none, 140@34+4→none, 141@38+3→none, 142@41+7→none, 143@48+3→none, 144@51+3→none, 145@54+2→none | 145 | none | `2026-10-12-eve-base/geometry/L/down_Y_idle`: 56/56, +59 | box clock measured, cells static |
| `air Y` | 0x27 | 38 | 153@0+14→none, 154@14+2→none, 155@16+2→none, 156@18+8→none, 157@26+4→none, 158@30+4→none, 159@34+4→none | 159 | none | `2026-10-12-eve-base/geometry/L/air_Y_idle`: 38/38, +76 | box clock measured, cells static |
| `X` (koma 4) | 0x29 | 39 | 0@0+7→none, 1@7+4→none, 2@11+4→none, 3@15+4→none, 4@19+4→none, 2@23+4→none, 5@27+4→none, 6@31+4→none, 7@35+4→none | 7 | none | `2026-10-12-eve-specials/grids/k4-L/X_idle`: 39/39, +42 | box clock measured, cells static |
| `up X` (koma 4) | 0x2a | 79 | 8@0+4→none, 9@4+4→none, 10@8+4→none, 11@12+4→none, 12@16+4→none, 13@20+4→none, 14@24+4→none, 15@28+4→none, 16@32+4→none, 17@36+4→none, 18@40+4→none, 16@44+4→none, 17@48+4→none, 18@52+4→none, 19@56+4→none, 21@60+4→none, 22@64+15→none | 22 | none | `2026-10-12-eve-specials/grids/k4-L/up_X_idle`: 79/79, +82 | start measured, cells static |
| `X` (koma 5) | 0x2b | 112 | 13@0+3→none, 14@3+3→none, 15@6+3→none, 16@9+3→none, 17@12+3→none, 18@15+3→none, 19@18+3→none, 20@21+8→none, 21@29+4→none, 22@33+4→none, 23@37+4→none, 22@41+4→none, 23@45+4→none, 22@49+4→none, 24@53+4→none, 17@57+4→none, 16@61+4→none, 14@65+4→none, 13@69+17→none, 23@86+3→none, 24@89+3→none, 25@92+4→none, 26@96+4→none, 27@100+4→none, 28@104+4→none, 29@108+4→none | 29 | none | `2026-10-12-eve-specials/grids/k5-L/X_idle`: 41/41, +85 | box clock measured to anim frame 40, cells static |
| `up X` (koma 5) | 0x2c | 84 | 0@0+2→none, 1@2+2→none, 2@4+2→none, 3@6+3→none, 4@9+4→none, 5@13+4→none, 6@17+3→none, 7@20+3→none, 5@23+3→none, 6@26+3→none, 7@29+3→none, 5@32+3→none, 6@35+3→none, 7@38+3→none, 5@41+3→none, 6@44+3→none, 7@47+3→none, 5@50+3→none, 6@53+3→none, 7@56+3→none, 8@59+7→none, 9@66+3→none, 10@69+7→none, 11@76+4→none, 12@80+4→none | 12 | none | `2026-10-12-eve-specials/grids/k5-L/up_X_idle`: 20/20, +53 | box clock measured to anim frame 19, cells static |

Moves whose idle return is not `frames + 3` (each needs an override):

| move | anim | frames | frames + 3 | idle return | why |
|---|---|---|---|---|---|
| `air B` | 0x26 | 29 | 32 | +62 | ends in the air: state 6 (fall) at +32 = frames + 3, lands (state 13) at +43, idle at +62 (a full hop lands at +49, idle at +71) |
| `side Y` | 0x21 | 117 | 120 | +62 | the whiff path ends at +62; the animation is 117 frames, and what follows frame 60 belongs to the connect path (a grab follow-up), which this capture does not take |
| `up Y` | 0x23 | 45 | 48 | +67 | ends in the air: state 6 (fall) at +48 = frames + 3, idle at +67 with no state-13 frame logged |
| `air Y` | 0x27 | 38 | 41 | +76 | ends in the air: state 6 (fall) at +41 = frames + 3, lands (state 13) at +57, idle at +76 (a full hop lands at +63, idle at +85) |
| `X` 5 | 0x2b | 112 | 115 | +85 | the whiff path: the boxes follow the animation straight through frame 40, then the clock jumps inside the 112-frame animation (frames 42-44 at s 50-52, 57-60 at s 65-68, 73-85 at s 81-82); the attack state ends in the air (state 6) at +83 = idle at +85. Which branch the later frames are is not pinned |
| `up X` 5 | 0x2c | 84 | 87 | +53 | a mash move (kit mash.frames 84): unmashed, the boxes follow the animation straight through frame 19, then jump (frames 56-58 at s 20-22, 62-65 at s 26-31, 69-75 at s 35-41) and idle comes at +53, 31 frames before the 84-frame animation ends |

| anim | frames | loop | cells: cell@start+len→strip frame | strip | evidence | grade |
|---|---|---|---|---|---|---|
| 0x00 | 28 | loop | 0@0+7→none, 1@7+7→none, 2@14+7→none, 3@21+7→none | none | none | static |
| 0x01 | 32 | loop | 4@0+4→none, 5@4+4→none, 6@8+4→none, 7@12+4→none, 8@16+4→none, 9@20+4→none, 10@24+4→none, 11@28+4→none | none | none | static |
| 0x02 | 12 | hold | 12@0+3→none, 13@3+3→none, 12@6+3→none, 13@9+3→none | none | none | static |
| 0x03 | 12 | hold | 14@0+4→none, 15@4+4→none, 16@8+4→none | none | none | static |
| 0x04 | 8 | hold | 17@0+4→none, 18@4+4→none | none | none | static |
| 0x05 | 4 | hold | 19@0+4→none | none | none | static |
| 0x06 | 8 | hold | 20@0+4→none, 21@4+4→none | none | none | static |
| 0x07 | 8 | hold | 22@0+4→none, 23@4+4→none | none | none | static |
| 0x08 | 4 | hold | 24@0+4→none | none | none | static |
| 0x09 | 4 | hold | 25@0+4→none | none | none | static |
| 0x0a | 4 | hold | 27@0+4→none | none | none | static |
| 0x0b | 4 | hold | 26@0+4→none | none | none | static |
| 0x0c | 4 | hold | 28@0+4→none | none | none | static |
| 0x0d | 4 | hold | 40@0+4→none | none | none | static |
| 0x0e | 8 | loop | 32@0+4→none, 33@4+4→none | none | none | static |
| 0x0f | 16 | hold | 30@0+4→none, 29@4+4→none, 30@8+4→none, 31@12+4→none | none | none | static |
| 0x10 | 4 | hold | 29@0+4→none | none | none | static |
| 0x11 | 4 | hold | 30@0+4→none | none | none | static |
| 0x12 | 8 | loop | 34@0+4→none, 35@4+4→none | none | none | static |
| 0x13 | 16 | loop | 36@0+4→none, 37@4+4→none, 38@8+4→none, 39@12+4→none | none | none | static |
| 0x14 | 32 | loop | 41@0+8→none, 42@8+8→none, 43@16+8→none, 42@24+8→none | none | none | static |
| 0x15 | 24 | hold | 44@0+4→none, 45@4+4→none, 46@8+4→none, 47@12+4→none, 48@16+4→none, 49@20+4→none | none | none | static |
| 0x16 | 16 | loop | 50@0+4→none, 51@4+4→none, 52@8+4→none, 53@12+4→none | none | none | static |
| 0x17 | 16 | hold | 54@0+4→none, 55@4+4→none, 56@8+4→none, 57@12+4→none | none | none | static |
| 0x18 | 54 | hold | 58@0+7→none, 59@7+7→none, 60@14+7→none, 61@21+18→none, 59@39+3→none, 62@42+3→none, 63@45+3→none, 62@48+3→none, 63@51+3→none | none | none | static |
| 0x19 | 69 | hold | 64@0+4→none, 65@4+4→none, 66@8+4→none, 67@12+8→none, 68@20+4→none, 69@24+4→none, 70@28+4→none, 71@32+4→none, 72@36+4→none, 73@40+4→none, 74@44+4→none, 72@48+7→none, 73@55+7→none, 74@62+7→none | none | none | static |
| 0x1a | 14 | hold | 75@0+4→none, 76@4+3→none, 77@7+3→none, 78@10+4→none | none | none | static |
| 0x28 | 35 | hold | 85@0+4→none, 86@4+6→none, 87@10+3→none, 88@13+3→none, 89@16+15→none, 90@31+4→none | none | none | static |
| 0x33 | 4 | hold | 166@0+4→none | none | none | static |
| 0x34 | 4 | hold | 167@0+4→none | none | none | static |
| 0x35 | 4 | hold | 168@0+4→none | none | none | static |
| 0x36 | 4 | hold | 169@0+4→none | none | none | static |

<!-- /generated:anim-timing eve -->

Notes for Eve (static pass; move rows from the Eve captures):

- The base ten and the four set moves are `MOVES` rows (`anim_rows.py`), each checked by the same box replay as Kakashi's
  and Yusuke's, on the facing-LEFT whiffs the kit exports: `2026-10-12-eve-base/geometry/L/*` for the base moves,
  `2026-10-12-eve-specials/grids/k{4,5}-L/*` for the sets (`kit/eve.toml` names the same files). The base-move anims are
  the move table's (`knockback-table.json` `bc_b_01`: ids 1-10 = anims 0x1e-0x27, the kit's `jus_anim`). The set anims are
  the base amt's 0x29-0x2c (the kit's mash anims are 0x29 for koma 4 X and 0x2c for koma 5 up X); the boxes of 0x29 and 0x2a
  fit koma 4's X and up X on every frame, and 0x2b and 0x2c fit koma 5's X and up X to frames 40 and 19 (the later frames
  are a branch, see the idle-return table).
- A set row here has `koma`, `archive` and `koma_archive` like a special, but no `plays`, `hits` or `strip`: Eve has no
  special log in the C1-C4 format, no `special-strips.json` entry (no hand-cut strips yet), and its hit records are the kit's,
  not read from a col record. Grades are the box check's: `box clock measured` (`start measured` for koma 4 up X, whose boxes
  never change), cells `static`. Cells map to no strip frame because there are no hand-cut strips.
- `side Y` (0x21, 117 frames) is cut at +62 on a whiff; its later frames carry the grab follow-up boxes (types 259/260),
  seen only on a connect. Anim 0x18 (the Ultimate Action) has no row: the live run (`2026-10-13-eve-ua`) logged bridge
  rows, not boxes, so the box replay cannot pin it (state 12 lasts 57 = 54 + 3 ticks, measured there).
- Anim 0x28 (the dream attack, move id 12, state 11, `fighter+0xD1` set; the Ultimate Action is anim 0x18, `docs/rebuild/ua-table.md`) is a 35-frame Y-shaped melee: the same type-257 box and rect as Y (0x1f,
  48 frames), active on anim frames 10-15 where Y's is 16-21. It reads KB record 1, Y's. The static data shows no grab
  (`docs/research/findings/cancel-windows-static-2026-09-25.md` §2 for the id-12 reader).

## 3b. Train (`chr_b` 38, `bc_b_02`)

<!-- generated:anim-timing train -->

| move | anim | frames | cells: cell@start+len→strip frame | end cell | strip | check (capture: agree/checked, idle return) | grade |
|---|---|---|---|---|---|---|---|

Moves whose idle return is not `frames + 3` (each needs an override):

| move | anim | frames | frames + 3 | idle return | why |
|---|---|---|---|---|---|

| anim | frames | loop | cells: cell@start+len→strip frame | strip | evidence | grade |
|---|---|---|---|---|---|---|
| 0x00 | 32 | loop | 0@0+8→none, 1@8+8→none, 2@16+8→none, 3@24+8→none | none | none | static |
| 0x01 | 32 | loop | 4@0+4→none, 5@4+4→none, 6@8+4→none, 7@12+4→none, 8@16+4→none, 9@20+4→none, 10@24+4→none, 11@28+4→none | none | none | static |
| 0x02 | 12 | hold | 12@0+3→none, 13@3+3→none, 12@6+3→none, 13@9+3→none | none | none | static |
| 0x03 | 12 | hold | 14@0+4→none, 15@4+4→none, 16@8+4→none | none | none | static |
| 0x04 | 8 | hold | 17@0+4→none, 18@4+4→none | none | none | static |
| 0x05 | 8 | hold | 19@0+8→none | none | none | static |
| 0x06 | 8 | hold | 19@0+4→none, 20@4+4→none | none | none | static |
| 0x07 | 8 | hold | 21@0+4→none, 22@4+4→none | none | none | static |
| 0x08 | 4 | hold | 21@0+4→none | none | none | static |
| 0x09 | 4 | hold | 23@0+4→none | none | none | static |
| 0x0a | 4 | hold | 24@0+4→none | none | none | static |
| 0x0b | 4 | hold | 25@0+4→none | none | none | static |
| 0x0c | 4 | hold | 26@0+4→none | none | none | static |
| 0x0d | 4 | hold | 27@0+4→none | none | none | static |
| 0x0e | 8 | loop | 28@0+4→none, 29@4+4→none | none | none | static |
| 0x0f | 16 | hold | 30@0+4→none, 31@4+4→none, 30@8+4→none, 32@12+4→none | none | none | static |
| 0x10 | 4 | hold | 30@0+4→none | none | none | static |
| 0x11 | 4 | hold | 31@0+4→none | none | none | static |
| 0x12 | 8 | loop | 33@0+4→none, 34@4+4→none | none | none | static |
| 0x13 | 16 | loop | 35@0+4→none, 36@4+4→none, 37@8+4→none, 38@12+4→none | none | none | static |
| 0x14 | 32 | loop | 39@0+8→none, 40@8+8→none, 41@16+8→none, 40@24+8→none | none | none | static |
| 0x15 | 24 | hold | 42@0+4→none, 43@4+4→none, 44@8+4→none, 45@12+4→none, 46@16+4→none, 47@20+4→none | none | none | static |
| 0x16 | 16 | loop | 48@0+4→none, 49@4+4→none, 50@8+4→none, 51@12+4→none | none | none | static |
| 0x17 | 16 | hold | 52@0+4→none, 53@4+4→none, 54@8+4→none, 55@12+4→none | none | none | static |
| 0x18 | 67 | hold | 56@0+4→none, 57@4+8→none, 58@12+5→none, 59@17+5→none, 60@22+23→none, 61@45+4→none, 62@49+4→none, 63@53+10→none, 64@63+4→none | none | none | static |
| 0x19 | 54 | hold | 65@0+4→none, 66@4+8→none, 67@12+8→none, 68@20+4→none, 69@24+8→none, 70@32+13→none, 79@45+9→none | none | none | static |
| 0x1a | 56 | hold | 71@0+6→none, 72@6+6→none, 73@12+16→none, 74@28+4→none, 75@32+4→none, 76@36+4→none, 77@40+8→none, 78@48+8→none | none | none | static |
| 0x1e | 30 | hold | 80@0+3→none, 81@3+5→none, 82@8+3→none, 83@11+4→none, 84@15+11→none, 85@26+4→none | none | none | static |
| 0x1f | 50 | hold | 86@0+4→none, 87@4+3→none, 88@7+3→none, 89@10+5→none, 90@15+6→none, 91@21+25→none, 92@46+4→none | none | none | static |
| 0x20 | 34 | hold | 93@0+4→none, 94@4+4→none, 95@8+3→none, 96@11+4→none, 97@15+9→none, 98@24+6→none, 92@30+4→none | none | none | static |
| 0x21 | 95 | hold | 99@0+4→none, 100@4+11→none, 101@15+4→none, 102@19+18→none, 103@37+4→none, 104@41+4→none, 57@45+14→none, 100@59+7→none, 101@66+4→none, 102@70+13→none, 103@83+4→none, 104@87+4→none, 57@91+4→none | none | none | static |
| 0x22 | 39 | hold | 105@0+3→none, 106@3+6→none, 107@9+2→none, 108@11+4→none, 109@15+5→none, 110@20+5→none, 111@25+5→none, 112@30+5→none, 113@35+4→none | none | none | static |
| 0x23 | 94 | hold | 114@0+4→none, 115@4+3→none, 116@7+7→none, 117@14+4→none, 116@18+17→none, 115@35+4→none, 114@39+21→none, 116@60+5→none, 117@65+4→none, 116@69+17→none, 115@86+4→none, 114@90+4→none | none | none | static |
| 0x24 | 57 | hold | 118@0+4→none, 119@4+4→none, 120@8+4→none, 121@12+4→none, 122@16+4→none, 123@20+4→none, 124@24+4→none, 125@28+4→none, 126@32+4→none, 127@36+4→none, 126@40+13→none, 128@53+4→none | none | none | static |
| 0x25 | 69 | hold | 118@0+4→none, 119@4+4→none, 120@8+4→none, 121@12+4→none, 122@16+6→none, 123@22+4→none, 124@26+4→none, 125@30+4→none, 126@34+14→none, 127@48+4→none, 126@52+13→none, 128@65+4→none | none | none | static |
| 0x26 | 44 | hold | 140@0+4→none, 141@4+5→none, 142@9+4→none, 143@13+19→none, 144@32+4→none, 145@36+4→none, 146@40+4→none | none | none | static |
| 0x27 | 145 | hold | 147@0+3→none, 148@3+3→none, 149@6+3→none, 150@9+6→none, 151@15+4→none, 150@19+9→none, 149@28+21→none, 152@49+19→none, 149@68+3→none, 150@71+5→none, 151@76+4→none, 150@80+9→none, 149@89+21→none, 152@110+23→none, 19@133+4→none, 21@137+4→none, 22@141+4→none | none | none | static |
| 0x28 | 109 | hold | 99@0+3→none, 100@3+7→none, 101@10+4→none, 100@14+4→none, 101@18+4→none, 100@22+4→none, 101@26+4→none, 102@30+18→none, 103@48+4→none, 104@52+4→none, 57@56+14→none, 100@70+6→none, 101@76+3→none, 102@79+18→none, 103@97+4→none, 104@101+4→none, 57@105+4→none | none | none | static |
| 0x33 | 4 | hold | 159@0+4→none | none | none | static |
| 0x34 | 4 | hold | 160@0+4→none | none | none | static |
| 0x35 | 4 | hold | 161@0+4→none | none | none | static |
| 0x36 | 4 | hold | 162@0+4→none | none | none | static |

On another art file (TextureID is not the main sheet's, so the hand-cut strips cannot show them): 0x29, 0x2a, 0x2b, 0x2c.

<!-- /generated:anim-timing train -->

Notes for Train (static only):

- Same as Eve: no capture ties an animation to a move yet, so the move rows are empty and every grade is `static`. The
  base-move anims are the move table's (`knockback-table.json` `bc_b_02`: ids 1-10 = anims 0x1e-0x27). The prefix is
  `bc_b_02`, the value the mapping doc's sequential rule predicts and a static damage match supports (not a live
  measurement; `chr_b-Complete-Mapping.md`, "Train's File value").
- Anim 0x28 (move id 12, state 11, `fighter+0xD1` set) is the dream attack, 109 frames. It repeats side Y's (0x21, 95 frames)
  firing cycle with the pairs of cells 100 and 101 run three times before the shot instead of once; `vfx-sfx.md` shows 4
  shot spawns in it (frames 10, 18, 26, 76) against 2 in side Y (15, 66). Its shots are row 11 three times (frames 10, 18,
  26) then row 2 (frame 76).
- The Ultimate Action is anim 0x18 (move id 11, state 12, SELECT), not anim 0x28. It stores 3 at f49 (`ctrl+0xA3`). Side Y,
  up Y and air Y consume the store and jump to a second shot cycle (f59, f60, f68) that fires ids 262, 264 and 266 (KB recs
  6, 8, 10). Measured in `docs/research/feel-captures/2026-10-12-train-ua/README.md`.
- Anims 0x29, 0x2a, 0x2b and 0x2c sit on another art file (see above). 0x29 and 0x2b spawn a run of
  `SE_ELECSHOCK` sounds (frames 8 to 51 and 4 to 49), probably the Rail Gun charge; which koma owns which anim is for the
  capture jobs.

## 3c. Taikoubou (`chr_b` 68, `hs_b_01`)

<!-- generated:anim-timing taikoubou -->

| move | anim | frames | cells: cell@start+len→strip frame | end cell | strip | check (capture: agree/checked, idle return) | grade |
|---|---|---|---|---|---|---|---|

Moves whose idle return is not `frames + 3` (each needs an override):

| move | anim | frames | frames + 3 | idle return | why |
|---|---|---|---|---|---|

| anim | frames | loop | cells: cell@start+len→strip frame | strip | evidence | grade |
|---|---|---|---|---|---|---|
| 0x00 | 32 | loop | 0@0+8→none, 1@8+8→none, 2@16+8→none, 3@24+8→none | none | none | static |
| 0x01 | 32 | loop | 4@0+4→none, 5@4+4→none, 6@8+4→none, 7@12+4→none, 8@16+4→none, 9@20+4→none, 10@24+4→none, 11@28+4→none | none | none | static |
| 0x02 | 12 | hold | 12@0+3→none, 13@3+3→none, 12@6+3→none, 13@9+3→none | none | none | static |
| 0x03 | 12 | hold | 14@0+4→none, 15@4+4→none, 16@8+4→none | none | none | static |
| 0x04 | 8 | loop | 17@0+4→none, 18@4+4→none | none | none | static |
| 0x05 | 4 | hold | 19@0+4→none | none | none | static |
| 0x06 | 8 | loop | 19@0+4→none, 20@4+4→none | none | none | static |
| 0x07 | 8 | hold | 21@0+4→none, 22@4+4→none | none | none | static |
| 0x08 | 4 | hold | 23@0+4→none | none | none | static |
| 0x09 | 4 | hold | 24@0+4→none | none | none | static |
| 0x0a | 4 | hold | 25@0+4→none | none | none | static |
| 0x0b | 4 | hold | 26@0+4→none | none | none | static |
| 0x0c | 4 | hold | 27@0+4→none | none | none | static |
| 0x0d | 4 | hold | 28@0+4→none | none | none | static |
| 0x0e | 8 | loop | 36@0+4→none, 37@4+4→none | none | none | static |
| 0x0f | 16 | hold | 30@0+4→none, 29@4+4→none, 30@8+4→none, 31@12+4→none | none | none | static |
| 0x10 | 4 | hold | 29@0+4→none | none | none | static |
| 0x11 | 4 | hold | 30@0+4→none | none | none | static |
| 0x12 | 8 | loop | 38@0+4→none, 39@4+4→none | none | none | static |
| 0x13 | 16 | loop | 32@0+4→none, 33@4+4→none, 34@8+4→none, 35@12+4→none | none | none | static |
| 0x14 | 32 | loop | 40@0+8→none, 41@8+8→none, 42@16+8→none, 41@24+8→none | none | none | static |
| 0x15 | 24 | hold | 43@0+4→none, 44@4+4→none, 45@8+4→none, 46@12+4→none, 47@16+4→none, 48@20+4→none | none | none | static |
| 0x16 | 16 | loop | 49@0+4→none, 50@4+4→none, 51@8+4→none, 52@12+4→none | none | none | static |
| 0x17 | 16 | hold | 53@0+4→none, 54@4+4→none, 55@8+4→none, 56@12+4→none | none | none | static |
| 0x18 | 92 | hold | 57@0+4→none, 58@4+4→none, 59@8+6→none, 60@14+8→none, 61@22+10→none, 62@32+8→none, 63@40+8→none, 62@48+8→none, 61@56+12→none, 60@68+6→none, 59@74+6→none, 58@80+6→none, 57@86+6→none | none | none | static |
| 0x19 | 88 | hold | 64@0+8→none, 65@8+6→none, 66@14+5→none, 68@19+5→none, 69@24+6→none, 70@30+6→none, 72@36+4→none, 70@40+4→none, 71@44+6→none, 70@50+6→none, 72@56+8→none, 73@64+8→none, 74@72+8→none, 75@80+8→none | none | none | static |
| 0x1a | 28 | hold | 76@0+6→none, 77@6+6→none, 78@12+8→none, 79@20+4→none, 80@24+4→none | none | none | static |
| 0x1e | 31 | hold | 81@0+4→none, 82@4+5→none, 83@9+3→none, 85@12+15→none, 84@27+4→none | none | none | static |
| 0x1f | 19 | hold | 98@0+2→none, 99@2+3→none, 100@5+3→none, 101@8+4→none, 99@12+3→none, 98@15+3→none, 102@18+1→none | none | none | static |
| 0x20 | 35 | hold | 91@0+6→none, 92@6+3→none, 93@9+3→none, 95@12+4→none, 94@16+4→none, 96@20+11→none, 97@31+4→none | none | none | static |
| 0x21 | 29 | hold | 86@0+2→none, 87@2+3→none, 88@5+3→none, 89@8+7→none, 88@15+4→none, 87@19+3→none, 86@22+3→none, 90@25+4→none | none | none | static |
| 0x22 | 48 | hold | 103@0+11→none, 104@11+4→none, 105@15+4→none, 106@19+4→none, 107@23+4→none, 106@27+7→none, 108@34+6→none, 109@40+8→none | none | none | static |
| 0x23 | 45 | hold | 110@0+4→none, 111@4+4→none, 112@8+4→none, 113@12+4→none, 112@16+4→none, 113@20+13→none, 111@33+4→none, 110@37+4→none, 114@41+4→none | none | none | static |
| 0x24 | 62 | hold | 115@0+4→none, 116@4+4→none, 117@8+4→none, 118@12+4→none, 117@16+4→none, 118@20+20→none, 117@40+4→none, 116@44+3→none, 115@47+3→none, 119@50+12→none | none | none | static |
| 0x25 | 67 | hold | 120@0+3→none, 121@3+3→none, 122@6+3→none, 123@9+42→none, 122@51+4→none, 121@55+4→none, 120@59+4→none, 124@63+4→none | none | none | static |
| 0x26 | 47 | hold | 125@0+12→none, 126@12+4→none, 127@16+4→none, 126@20+4→none, 127@24+4→none, 125@28+10→none, 128@38+9→none | none | none | static |
| 0x27 | 32 | hold | 128@0+2→none, 129@2+3→none, 130@5+3→none, 131@8+4→none, 132@12+4→none, 131@16+4→none, 129@20+4→none, 128@24+8→none | none | none | static |
| 0x28 | 33 | hold | 133@0+9→none, 134@9+3→none, 135@12+3→none, 137@15+4→none, 136@19+4→none, 138@23+6→none, 139@29+4→none | none | none | static |
| 0x33 | 4 | hold | 140@0+4→none | none | none | static |
| 0x34 | 4 | hold | 141@0+4→none | none | none | static |
| 0x35 | 4 | hold | 142@0+4→none | none | none | static |
| 0x36 | 4 | hold | 143@0+4→none | none | none | static |

On another art file (TextureID is not the main sheet's, so the hand-cut strips cannot show them): 0x29, 0x2a, 0x2b, 0x2c, 0x2d, 0x2e.

<!-- /generated:anim-timing taikoubou -->

Notes for Taikoubou (static only):

- No capture and no kit file (`kit/taikoubou.toml` does not exist) ties an animation to a move yet, so the
  move rows are empty and every grade is `static`. The prefix `hs_b_01` is the mapping doc's (static match
  only, not live-measured).
- Anims 0x29 to 0x2e sit on another art file (see above), as for Train.

## 3d. Koma men (`chr_b` 70, `dt_b_01`)

<!-- generated:anim-timing komamen -->

| move | anim | frames | cells: cell@start+len→strip frame | end cell | strip | check (capture: agree/checked, idle return) | grade |
|---|---|---|---|---|---|---|---|
| `B` | 0x1e | 30 | 61@0+3→none, 62@3+7→none, 63@10+20→none | 63 | none | art clock unmeasured | static |
| `Y` | 0x1f | 56 | 64@0+16→none, 66@16+2→none, 67@18+10→none, 68@28+4→none, 65@32+4→none, 64@36+20→none | 64 | none | art clock unmeasured | static |
| `side B` | 0x20 | 32 | 69@0+2→none, 73@2+2→none, 74@4+6→none, 70@10+4→none, 71@14+12→none, 72@26+6→none | 72 | none | art clock unmeasured | static |
| `side Y` | 0x21 | 98 | 84@0+4→none, 85@4+12→none, 75@16+2→none, 76@18+2→none, 77@20+3→none, 78@23+3→none, 79@26+2→none, 75@28+2→none, 76@30+2→none, 77@32+3→none, 78@35+3→none, 79@38+2→none, 75@40+2→none, 76@42+2→none, 77@44+3→none, 78@47+3→none, 79@50+4→none, 83@54+4→none, 80@58+4→none, 81@62+4→none, 82@66+32→none | 82 | none | art clock unmeasured | static |
| `up B` | 0x22 | 50 | 86@0+12→none, 87@12+4→none, 88@16+4→none, 87@20+4→none, 88@24+4→none, 87@28+4→none, 88@32+4→none, 89@36+2→none, 86@38+12→none | 86 | none | art clock unmeasured | static |
| `up Y` | 0x23 | 48 | 90@0+4→none, 91@4+3→none, 94@7+8→none, 93@15+3→none, 98@18+4→none, 99@22+10→none, 95@32+4→none, 96@36+4→none, 97@40+4→none, 90@44+4→none | 90 | none | art clock unmeasured | static |
| `down B` | 0x24 | 36 | 100@0+16→none, 101@16+4→none, 102@20+2→none, 103@22+2→none, 104@24+4→none, 101@28+4→none, 100@32+4→none | 100 | none | art clock unmeasured | static |
| `down Y` | 0x25 | 66 | 105@0+36→none, 106@36+4→none, 107@40+2→none, 108@42+10→none, 109@52+4→none, 106@56+4→none, 105@60+6→none | 105 | none | art clock unmeasured | static |
| `air B` | 0x26 | 18 | 110@0+6→none, 111@6+4→none, 112@10+4→none, 113@14+4→none | 113 | none | art clock unmeasured | static |
| `air Y` | 0x27 | 19 | 114@0+4→none, 115@4+3→none, 116@7+12→none | 116 | none | art clock unmeasured | static |
| `dream` | 0x28 | 34 | 117@0+10→none, 119@10+2→none, 120@12+8→none, 121@20+4→none, 118@24+4→none, 117@28+6→none | 117 | none | art clock unmeasured | static |
| `X` (koma 4) | 0x29 | 60 | 0@0+4→none, 1@4+4→none, 2@8+4→none, 0@12+4→none, 2@16+4→none, 1@20+4→none, 2@24+4→none, 1@28+4→none, 2@32+4→none, 1@36+4→none, 2@40+4→none, 1@44+4→none, 2@48+4→none, 3@52+4→none, 4@56+4→none | 4 | none | art clock unmeasured | static |
| `up X` (koma 4) | 0x2a | 56 | 5@0+5→none, 6@5+5→none, 7@10+6→none, 8@16+16→none, 9@32+4→none, 10@36+4→none, 11@40+4→none, 7@44+4→none, 6@48+8→none | 6 | none | art clock unmeasured | static |

Moves whose idle return is not `frames + 3` (each needs an override):

| move | anim | frames | frames + 3 | idle return | why |
|---|---|---|---|---|---|

| anim | frames | loop | cells: cell@start+len→strip frame | strip | evidence | grade |
|---|---|---|---|---|---|---|
| 0x00 | 47 | loop | 0@0+12→none, 1@12+12→none, 2@24+12→none, 1@36+11→none | none | none | static |
| 0x01 | 16 | loop | 3@0+8→none, 4@8+8→none | none | none | static |
| 0x02 | 12 | hold | 5@0+3→none, 6@3+3→none, 5@6+3→none, 6@9+3→none | none | none | static |
| 0x03 | 12 | hold | 7@0+4→none, 8@4+4→none, 9@8+4→none | none | none | static |
| 0x04 | 8 | hold | 10@0+4→none, 11@4+4→none | none | none | static |
| 0x05 | 4 | hold | 10@0+4→none | none | none | static |
| 0x06 | 8 | hold | 12@0+4→none, 13@4+4→none | none | none | static |
| 0x07 | 4 | hold | 14@0+4→none | none | none | static |
| 0x08 | 4 | hold | 15@0+4→none | none | none | static |
| 0x09 | 4 | hold | 16@0+4→none | none | none | static |
| 0x0a | 4 | hold | 19@0+4→none | none | none | static |
| 0x0b | 4 | hold | 18@0+4→none | none | none | static |
| 0x0c | 4 | hold | 17@0+4→none | none | none | static |
| 0x0d | 4 | hold | 20@0+4→none | none | none | static |
| 0x0e | 8 | loop | 28@0+4→none, 29@4+4→none | none | none | static |
| 0x0f | 16 | hold | 22@0+4→none, 21@4+4→none, 22@8+4→none, 23@12+4→none | none | none | static |
| 0x10 | 4 | hold | 21@0+4→none | none | none | static |
| 0x11 | 4 | hold | 22@0+4→none | none | none | static |
| 0x12 | 8 | loop | 30@0+4→none, 31@4+4→none | none | none | static |
| 0x13 | 16 | loop | 24@0+4→none, 25@4+4→none, 26@8+4→none, 27@12+4→none | none | none | static |
| 0x14 | 32 | loop | 32@0+8→none, 33@8+8→none, 34@16+8→none, 33@24+8→none | none | none | static |
| 0x15 | 24 | hold | 34@0+4→none, 35@4+4→none, 36@8+4→none, 37@12+4→none, 38@16+4→none, 39@20+4→none | none | none | static |
| 0x16 | 16 | loop | 39@0+4→none, 40@4+4→none, 41@8+4→none, 42@12+4→none | none | none | static |
| 0x17 | 16 | hold | 43@0+4→none, 44@4+4→none, 45@8+4→none, 46@12+4→none | none | none | static |
| 0x18 | 52 | hold | 47@0+4→none, 48@4+4→none, 49@8+4→none, 50@12+4→none, 51@16+4→none, 50@20+4→none, 49@24+4→none, 52@28+4→none, 53@32+4→none, 52@36+4→none, 49@40+4→none, 48@44+4→none, 47@48+4→none | none | none | static |
| 0x19 | 32 | hold | 54@0+8→none, 55@8+12→none, 56@20+12→none | none | none | static |
| 0x1a | 40 | hold | 57@0+16→none, 58@16+8→none, 59@24+8→none, 60@32+8→none | none | none | static |
| 0x33 | 4 | hold | 122@0+4→none | none | none | static |
| 0x34 | 4 | hold | 123@0+4→none | none | none | static |
| 0x35 | 4 | hold | 124@0+4→none | none | none | static |
| 0x36 | 4 | hold | 125@0+4→none | none | none | static |

<!-- /generated:anim-timing komamen -->

Notes for the koma men (static only):

- Red (`chr_b` 70, `dt_b_01`) is the roster row. Yellow (`dt_b_03`, 72) and Green (`dt_b_02`, 71) share its
  `chr/col` bytes and every table row once the prefix is normalised, so they get no rows of their own; only
  their effect banks differ (`vfx-sfx.md` §5).
- No capture ties an animation to a move here, so the move rows are empty and every grade is `static`.

## 3e. Kenshin (`chr_b` 36, `rk_b_01`)

<!-- generated:anim-timing kenshin -->

| move | anim | frames | cells: cell@start+len→strip frame | end cell | strip | check (capture: agree/checked, idle return) | grade |
|---|---|---|---|---|---|---|---|

Moves whose idle return is not `frames + 3` (each needs an override):

| move | anim | frames | frames + 3 | idle return | why |
|---|---|---|---|---|---|

| anim | frames | loop | cells: cell@start+len→strip frame | strip | evidence | grade |
|---|---|---|---|---|---|---|
| 0x00 | 32 | loop | 0@0+8→none, 1@8+8→none, 2@16+8→none, 3@24+8→none | none | none | static |
| 0x01 | 32 | loop | 4@0+4→none, 5@4+4→none, 6@8+4→none, 7@12+4→none, 8@16+4→none, 9@20+4→none, 10@24+4→none, 11@28+4→none | none | none | static |
| 0x02 | 12 | hold | 12@0+3→none, 13@3+3→none, 12@6+3→none, 13@9+3→none | none | none | static |
| 0x03 | 12 | hold | 14@0+4→none, 15@4+4→none, 16@8+4→none | none | none | static |
| 0x04 | 8 | hold | 17@0+4→none, 18@4+4→none | none | none | static |
| 0x05 | 4 | hold | 19@0+4→none | none | none | static |
| 0x06 | 8 | hold | 19@0+4→none, 20@4+4→none | none | none | static |
| 0x07 | 8 | hold | 21@0+4→none, 22@4+4→none | none | none | static |
| 0x08 | 4 | hold | 21@0+4→none | none | none | static |
| 0x09 | 4 | hold | 23@0+4→none | none | none | static |
| 0x0a | 4 | hold | 25@0+4→none | none | none | static |
| 0x0b | 4 | hold | 24@0+4→none | none | none | static |
| 0x0c | 4 | hold | 26@0+4→none | none | none | static |
| 0x0d | 4 | hold | 34@0+4→none | none | none | static |
| 0x0e | 8 | loop | 35@0+4→none, 36@4+4→none | none | none | static |
| 0x0f | 16 | hold | 28@0+4→none, 27@4+4→none, 28@8+4→none, 29@12+4→none | none | none | static |
| 0x10 | 4 | hold | 27@0+4→none | none | none | static |
| 0x11 | 4 | hold | 28@0+4→none | none | none | static |
| 0x12 | 8 | loop | 37@0+4→none, 38@4+4→none | none | none | static |
| 0x13 | 16 | loop | 30@0+4→none, 31@4+4→none, 32@8+4→none, 33@12+4→none | none | none | static |
| 0x14 | 32 | loop | 39@0+8→none, 40@8+8→none, 41@16+8→none, 40@24+8→none | none | none | static |
| 0x15 | 24 | hold | 42@0+4→none, 43@4+4→none, 44@8+4→none, 45@12+4→none, 46@16+4→none, 47@20+4→none | none | none | static |
| 0x16 | 16 | loop | 48@0+4→none, 49@4+4→none, 50@8+4→none, 51@12+4→none | none | none | static |
| 0x17 | 16 | hold | 52@0+6→none, 53@6+5→none, 54@11+5→none | none | none | static |
| 0x18 | 30 | hold | 55@0+4→none, 56@4+4→none, 57@8+4→none, 58@12+4→none, 59@16+10→none, 60@26+4→none | none | none | static |
| 0x19 | 46 | hold | 61@0+6→none, 62@6+6→none, 63@12+10→none, 64@22+6→none, 65@28+6→none, 66@34+6→none, 67@40+6→none | none | none | static |
| 0x1a | 64 | hold | 68@0+8→none, 69@8+8→none, 70@16+12→none, 71@28+12→none, 70@40+12→none, 72@52+12→none | none | none | static |
| 0x1e | 29 | hold | 73@0+5→none, 74@5+3→none, 75@8+3→none, 76@11+14→none, 77@25+4→none | none | none | static |
| 0x1f | 52 | hold | 73@0+8→none, 78@8+4→none, 105@12+4→none, 79@16+3→none, 80@19+3→none, 81@22+3→none, 82@25+3→none, 83@28+3→none, 84@31+3→none, 85@34+6→none, 86@40+6→none, 87@46+6→none | none | none | static |
| 0x20 | 29 | hold | 88@0+8→none, 89@8+3→none, 90@11+6→none, 91@17+4→none, 92@21+4→none, 93@25+4→none | none | none | static |
| 0x21 | 48 | hold | 94@0+5→none, 95@5+3→none, 96@8+3→none, 97@11+3→none, 98@14+3→none, 99@17+3→none, 100@20+13→none, 101@33+5→none, 102@38+5→none, 103@43+5→none | none | none | static |
| 0x22 | 33 | hold | 104@0+5→none, 105@5+4→none, 106@9+3→none, 107@12+3→none, 108@15+6→none, 109@21+4→none, 110@25+4→none, 111@29+4→none | none | none | static |
| 0x23 | 54 | hold | 73@0+5→0, 90@5+7→1, 112@12+4→2, 113@16+3→3, 114@19+3→4, 115@22+3→5, 117@25+3→6, 118@28+3→7, 119@31+3→8, 120@34+4→9, 121@38+10→10, 122@48+3→11, 123@51+3→12 | up_y_body | none | static |
| 0x24 | 33 | hold | 124@0+5→none, 125@5+5→none, 126@10+5→none, 127@15+3→none, 128@18+3→none, 129@21+4→none, 130@25+4→none, 131@29+4→none | none | none | static |
| 0x25 | 69 | hold | 132@0+4→none, 133@4+4→none, 134@8+27→none, 135@35+3→none, 136@38+3→none, 135@41+3→none, 136@44+3→none, 135@47+3→none, 136@50+3→none, 134@53+4→none, 137@57+4→none, 138@61+4→none, 139@65+4→none | none | none | static |
| 0x26 | 25 | hold | 140@0+3→none, 141@3+5→none, 142@8+3→none, 143@11+5→none, 144@16+5→none, 145@21+4→none | none | none | static |
| 0x27 | 33 | hold | 146@0+4→0, 147@4+6→1, 148@10+3→2, 149@13+3→3, 150@16+4→4, 151@20+10→5, 152@30+3→6 | air_y_body | none | static |
| 0x28 | 39 | hold | 95@0+3→none, 96@3+3→none, 97@6+3→none, 98@9+3→none, 99@12+3→none, 100@15+9→none, 101@24+5→none, 102@29+5→none, 103@34+5→none | none | none | static |
| 0x33 | 4 | hold | 163@0+4→none | none | none | static |
| 0x34 | 4 | hold | 164@0+4→none | none | none | static |
| 0x35 | 4 | hold | 165@0+4→none | none | none | static |
| 0x36 | 4 | hold | 166@0+4→none | none | none | static |
| 0x83 | 16 | hold | 1@0+4→0, 2@4+4→1, 3@8+4→2, 4@12+4→3 | k5_x_move_component_rk_b_01_e5_amt_id_131_node_0 | none | static |

On another art file (TextureID is not the main sheet's, so the hand-cut strips cannot show them): 0x29, 0x2a, 0x2b, 0x2c, 0x2d, 0x2e.

<!-- /generated:anim-timing kenshin -->

Notes for Kenshin (static only):

- No capture ties an animation to a move, so the move rows are empty and every grade is `static`.
- The special animations 0x29-0x2e use another art file; their cells have no hand-cut strip match.

## 4. What does not map

Strip frames with no main-sheet cell, and cells with no strip frame:

| character | strip or move | detail |
|---|---|---|
| Kakashi | `side Y` (`y_forward`) | cells 104 and 107 have no strip frame; strip frames 7, 10 and 12 hold no main-sheet cell (probably the throw's effect pieces) |
| Kakashi | `up Y` (`y_up`) | cell 123 has no strip frame; strip frames 7, 9 and 12 hold no main-sheet cell |
| Kakashi | `air Y` (`y_jump`) | cell 152 has no strip frame |
| Kakashi | weak matches | walk frame 3 (cell 7), `b_forward` frames 5 and 6 (cells 97, 98), `y_attack` frame 4 (cell 87), `b_jump` frame 0 (cell 143), `y_jump` frame 3 (cell 153): the right cell, probably, but check by eye |
| Kakashi | `hit` | 0x09 (cell 23) has no strip frame |
| Yusuke | `down B` (`b_down`) | cell 116 has no strip frame; strip frame 2 holds no main-sheet cell |
| Yusuke | `air Y` (`y_jump`) | cells 132, 135 and 136 have no strip frame; strip frame 5 fits side Y's cell 95 only weakly; frames 6 and 7 hold no main-sheet cell; frame 9 is cell 18, the fall cell |
| Yusuke | `up B` (`b_up`) | strip frame 7 is cell 18 (the fall cell), after up B's end cell 17 |
| Yusuke | `down` | strip frames 0 and 4 hold no main-sheet cell; cells 25 and 31 have no strip frame |
| Yusuke | `hit` | 0x09 (cell 21) has no strip frame |
| both | projectile strips | no frame of `shuriken`, `ninken`, `kunai`, `spirit_gun`, `spirit_shotgun`, `spirit_gun_big` or `spirit_gun_air` is a main-sheet cell. Shot and effect art lives in other files (static inventory: Kakashi's `na_b_04_e0` holds a DSIG, DSTX lists and an ALMT). `ninken` and `pakkun` are not the 4-koma dogs (§8.3) |

Animations with no strip at all (0x0e, 0x12, 0x14 to 0x16, 0x18 to 0x1a on
both, Yusuke's 0x10, and 0x33 to 0x36) are not drawn from the strips. What plays them is TBD.

## 5. JSON schema (`anim-timing.json`)

Top level:

| key | meaning |
|---|---|
| `_schema`, `_generated_by`, `_strip_map`, `_special_strips` | this section; the command that wrote the file; the cell-to-strip map it read; the special strips it read (§8.1) |
| `characters.<name>` | `kakashi` or `yusuke`: `chr_b`, `prefix` (file prefix), `main_texture` (the TextureID of the main art sheet), `moves`, `states`, `other`, `projectile_strips` |

Each record in `moves`, `states` and `other`:

| key | meaning |
|---|---|
| `move` | moves only: `B`, `side B`, `up B`, `down B`, `air B`, `Y`, `side Y`, `up Y`, `down Y`, `air Y`, Kakashi's `side Y (mashed)` (a variant of `side Y`, same animation), and the specials `X` and `up X` |
| `koma` | moves only: the special's koma set (4, 5 or 6), or null for the base kit. A `MOVES` row can carry it too (Eve's `X` and `up X`, a `koma` option in `anim_rows.py`); such a row has a `check` and no `plays` |
| `archive`, `koma_archive` | specials only (and `MOVES` rows with a `koma`): the archive holding the animation (the base `chr/<prefix>.aar`), and the koma archive (`chr/<prefix>_<koma>.aar`): its sprite list and tiles (`CHR/<prefix>_<koma>c.aar`) are what the cells index. vfx-sfx.json's `koma_archive` is the same archive, where the spawn ids resolve |
| `plays` | specials only: one check per captured path (`path` names it), each with its `segments` and the check keys below. `check` is the first |
| `hits` | specials only: `{record, what, source, grade}` for each col record the special's hits use. The record is the hit element's id − 0x100 (the moveData entry's address moves between loads, so pass 1's `0x021BA0E0` + 20 × record holds for C1 and C2 only; the entry bytes equal the static record). `grade` is `measured` when a capture read that element, or `inferred: …` with its rule (a track enables it, or its damage and type match a measured hit). The kind bytes are in vfx-sfx.json |
| `levels`, `aliases` | specials only, optional: how levels and holds play the one animation; why X has no side X or down X rows (a maintainer ruling) |
| `anim` | ALMT animation id, hex string |
| `frames`, `rate`, `loop` | animation length in frames; the rate byte (60); the loop byte as a boolean |
| `cells` | list of `{cell, start, len, strip_frames, pick}`: show `cell` from animation frame `start` for `len` frames; `strip_frames` are the strip frames that hold it; `pick` is the in-order choice or null. On a special, a null `pick` comes with `why` (the build refuses one without) |
| `end_cell` | the key at frame `frames` (null when there is none) |
| `texture` | the animation's TextureID |
| `strip`, `strip_also`, `strip_frames_not_in_anim` | the hand-cut strip holding most of the cells (null when none holds half); ties; that strip's frames no cell of this animation claims. A special's `strip` is its special-strips.json key, and `strip_frames` index that entry's `cells` |
| `check` | moves only: the capture check (below) |
| `check_also` | moves only, optional: the same check on more captures |
| `idle_return_why` | moves only, when the idle return is not `frames + 3` (on a special: on any path): the reason. The build refuses a row without one |
| `draw` | moves only, when the move stops early: `{anim_frames, then, cause}`. Draw animation frames `0 … anim_frames − 1`, then switch to `then` |
| `checks` | states only, optional: a list of checks, each with a `what` label |
| `grade` | `box clock measured, cells static`, `start measured, cells static`, or `static`; "to anim frame n" when the check stops early. A special's grade says how many paths were checked and whether any span is held; "start and idle return measured … (no body box read, so no frame is checked)" when no capture of it logs a P1 body box |
| `note` | set when the cells index another art file |

A check:

| key | meaning |
|---|---|
| `capture`, `anchor_rule`, `anchor_frame` | the capture file; how frame 0 was found (`leave_idle`, `state9`, or a state chain like `13>0-1`); the capture frame it found |
| `compared` | specials only: what was compared, P1's body box (element id 0) or, when the capture logs none, P1's state only (then `segments` is empty and `checked_frames` is 0) |
| `checked_frames`, `agree`, `disagree_at` | how many animation frames were compared, how many agreed, and which did not (always empty in a written file) |
| `box_changes` | box changes inside the checked frames; 0 means only the start is measured |
| `also_fits` | other animations that fit the same frames (always empty for moves) |
| `state_return` | frames from the anchor to the first idle or walk frame |
| `state_end` | `{at, to}`: frames from the anchor to the first frame in another state, and that state (0 idle, 6 fall, 13 landing) |
| `then` | Yusuke air Y: `{anims, from_anim_frame, fall_frames, agree, last_fall_frame_shows_landing}`, the fall check after the cut |
| `end_hold`, `stand_at` | game frames that still show the end key's boxes, and frames until stand's boxes show, both counted from animation frame `frames`; null when the two sets of boxes match |
| `pause` | Yusuke side Y: `{before_anim_frame, game_frames, paused_frames_agree}` |
| `segments` | specials only: `["play", s0, t0, n]` (s0 … s0+n−1 show anim frames t0 … t0+n−1) or `["hold", s0, s1, lo, hi]` (s0 … s1−1 each show some frame in lo … hi; the boxes can't say which) |

`projectile_strips` maps each projectile strip to the grade of each of its
frames (§1.3).

`special-strips.json` (the specials' sheet strips) is described in §8.1.

## 6. How it was decoded (static)

- **ALMT entry header**: `+0` u32 id (low byte), `+4` u16 frames, `+6` u8
  rate (60 on every entry here), `+7` u8 loop flag. Tracks as in
  [move_records.py](../../scripts/analysis/move_records.py) `Almt`; a keyed
  `CollisionRect` key is 10 bytes (frame, then s16 x0, y0, x1, y1).
- **Collision channels, whole**: [collision-boxes.json](collision-boxes.json)
  (`scripts/analysis/collision_boxes.py build`) holds every animation's
  `CollisionType/Enable/Rect` keys per character (Kakashi, Yusuke, and Jotaro
  as a victim fixture). Anim 0x03 (guard) keeps the body rect on channel 0
  and adds channel 1 with type 2, the guard box
  ([clash-tier survey §6](../research/clash-tier-survey-2026-09-25/RESULTS.md)).
  The box replay (`predict`) puts out one element per typed channel that has a
  `CollisionRect` track: Eve's side Y (0x21) types channel 2 and gives it no rect,
  and her 117-frame capture shows no element for it (Kakashi's 0x18 has the same
  shape, unchecked; no Kakashi or Yusuke move row reads either).
- **`BoundsIndex` is the art cell.** Its values index the `<prefix>_.dtx`
  sprite list. Rendering those sprites from the tiles gives the strip poses
  (§1.3), which is how the meaning was settled.
- **`TextureID`** is a u32 file id: Kakashi's main sheet is `0x60400`
  (`na_b_04c.aar`); 0x29 to 0x2e use `0x60401` to `0x60403`
  (`na_b_04_4c`, `_5c`, `_6c`). Yusuke's main sheet is `0x98100`
  (`yh_b_01c.aar`); 0x29 to 0x2e use `0x98101` to `0x98103`.
- **DSIG** (`<prefix>c.aar`, one ALAR v2 member): `+6` palette count,
  palettes at `+0x0C` (16 BGR555 colours each), then a u32, then the u32
  frame count, then a `(u16 offset, u16 size)` table. Frame data is LZ77 at
  `table + offset × 4`, raw 4bpp tiles.
- **DSTX type 0x83** (`<prefix>_.dtx`): `+6` u16 sprite count, u16 offsets
  at `0x0A + 2i` (relative to `0x0A`). A sprite is a u16 segment count, then
  6-byte segments: u16 DSIG frame, s8 x, s8 y, u8 shape (low 4 bits size,
  bits 4 and 5 flip), u8 palette. Tiles are used one after another.
- Kakashi's sprites 167 to 333 repeat 0 to 166 with other colours; no
  animation uses them.

## 7. `obj+0x72` is not an animation counter

The brief for this work asked to check the timing against `obj+0x72`, which
[physics.md](../confirmed-facts/physics.md) §6.6 and the engine notes
§2.1 call animation-elapsed frames. It is not one, so the check above uses
the collision boxes instead.

- **Static.** The writes at ov6 `0x021612E4` and `0x02161334` are in the
  input sampler at `0x02161148`, with `r4 = obj + 0x1C`. `[r4+0x56]` is
  `obj+0x72`. It counts sampler calls while the input word stays the same,
  and is set to 0 when the word changes or when it reaches 600. The
  sampler runs about once per frame, so the count is close to frames, but
  not exactly: see the +2 and 0 steps below. Each finished run
  (word, count) goes into a 16-slot history ring at `obj+0x28`. A second
  reading by codex agrees
  (second opinion).
- **Measured.** Over 186 landing logs
  (obj72_resets.py,
  output):
  the largest value is 599; 948 of 1006 resets happen with no state change;
  840 of 1006 are within 3 frames of a change in the logged input latch
  (most often 2 frames after it). 31 steps are +2 and 32 are 0 between two
  logged frames: the sampler ran twice, or not at all, in those frames.

So a landing log's `anim72` is how long the input has been held, not how
far the animation has run.

## 8. Specials (passes 1 and 2)

Twelve specials from static files: four in pass 1, checked against the C1
and C2 captures, and eight in pass 2, checked against C3 and C4 (no new
emulator run in either). The rows are in §2 and §3 and in the JSON's
`moves`; their spawns, sounds and record kinds are in
[vfx-sfx.md](vfx-sfx.md) §5.

**Where the files are (static).** A special's animation is in the base
motion table (`chr/na_b_04.aar` or `chr/yh_b_01.aar`), not in the koma
archive. Its `TextureID` names the koma set's sprite list
(`<prefix>_<koma>_.dtx` in `chr/<prefix>_<koma>.aar`, tiles in
`CHR/<prefix>_<koma>c.aar`). The koma archives hold that list, the effect
lists (`e40`, `e41`; `e60` to `e63`) and an effect table
(`na_b_04_e4.amt`, `yh_b_01_e6.amt`), and no fighter motion table.

**How the rows were checked (measured).** A special's check replays its
animation along `segments` and compares P1's body box (element id 0) on
each frame. The capture is in whole pixels and the prediction has half
pixels, so a whole-pixel value must be equal and a half-pixel one within
half a pixel. A 1 px margin would not do: X's held box (frames 4-35) and
frames 64-87 are within 1 px of each other, so it would pass a switch
anywhere in s 26-36 (tap) or s 60-79 (hold 72). With the exact rule only
s 32 and s 71 pass, and only a jump to frame 76; the test checks the
neighbours fail. Frame 0 is s 0, the first frame out of idle, on every
trial here.

**No side X or down X rows.** The owner ruled "side X and down X are not a
thing. only neutral and up"
([OWNER-NOTES.md](../research/moveset-notes/OWNER-NOTES.md), 2026-09-25):
X with any direction but up is just X. C1 §14 and C2 §2 saw the same
latches and damage for those inputs as for X.

| special | anim, frames, rate, loop | texture | what plays (grade) |
|---|---|---|---|
| Kakashi `X` (the beam) | 0x29, 79, 60, holds (static) | `0x060401`, koma 4 | straight through, 79/79 on `K/X_near_1`, idle at +82 (measured) |
| Kakashi `up X` (the dogs) | 0x2a, 78, 60, holds | `0x060401`, koma 4 | straight through, 78/78 on `K/upX_near`, idle at +81 (measured) |
| Yusuke `X` (Super Spirit Gun, both levels) | 0x2d, 108, 60, holds | `0x098103`, koma 6 | one animation for the tap and both levels (measured on 4 paths): a tap plays 0-31, then jumps to frame 76 at s 32. A hold freezes in frames 4-35; then level 1 jumps to 76 (hold 72: at s 71) and level 2 to 48 (hold 73: at s 72). The switch frames and targets are measured (the exact check fails one frame either side). That the switch comes two frames after the release is C2 §3's measurement. A hold past s 96 plays 36-39 and then holds frame 40 (cell 4) until the release. Idle at +67 (tap), +106 (hold 72), +94 (hold 73), +141 (hold 120) |
| Yusuke `up X` (Awakening) | 0x2e, 132, 60, holds | `0x098103`, koma 6 | on a hit (`G2/upX_near`, 124/124, idle at +127): 0-20, a jump to 43 at s 21, 43-104, a wait in frames 100-104 from s 83 to 96, then 105-131. That the wait sits in 100-104 is inferred (Marker 2; the boxes of 95-104 are equal) |

Which frame shows inside a held span is not measured: the boxes there
don't change. C2 §3 infers X's start-up hold sits at anim frame 32, where
the tap's box changes.

**Pass 2: Kakashi 5 and 6, Yusuke 4 and 5.** The TextureID's low byte
names the koma set (`0x060402` = Kakashi 5, `0x060403` = 6; `0x098101` =
Yusuke 4, `0x098102` = 5). C3 logs no P1 body box, and neither does C4's
set A (Yusuke's 4-koma X), so those rows check only that the move leaves
idle at s 0 and when it returns (`compared` says so). C4's sets K and Q
log it, so Yusuke's 4 up X, 5 X and 5 up X are box-checked frame by frame.

| special | anim, frames, rate, loop | texture | what plays (grade) |
|---|---|---|---|
| Kakashi `X` 5 (Raikiri) | 0x2b, 229, 60, holds | `0x060402`, koma 5 | a charged dash: level 1 is a hold of 3-30, level 2 40-92, level 3 93 or more, and level 3 fires by itself at press + 95. The damage is 36 at every level. The dash keeps the facing from the start of the charge (C3 §2-3, measured). State only on 3 paths: idle at +96 (tap), +88 (hold 60), +156 (hold 120). The markers at anim frames 62, 93 and 128 as the level starts and 167 as the hit sequence are inferred |
| Kakashi `up X` 5 (Kuchiyose) | 0x2c, 94, 60, holds | `0x060402`, koma 5 | the dogs; idle at +97 (state only). No charge (C3 §5) |
| Kakashi `X` 6 (Chidori) | 0x2d, 252, 60, holds | `0x060403`, koma 6 | the same three levels and auto-fire; 44 damage at every level. It steers: back held into the frame before the dash reverses it, and a side press mid-flight flips it (C3 §3). State only: idle at +103 (tap), +94 (hold 60), +165 (hold 120). Markers 62, 95, 136 and 181, inferred as above |
| Kakashi `up X` 6 (Mangekyou) | 0x2e, 56, 60, holds | `0x060403`, koma 6 | the anim is 56 frames, but he stays in state 10 for 195 while the eye flies (idle at +195, state only). The eye eases toward the held heading, ignores straight back and straight ahead, keeps its heading on release, and passes walls and the floor (C3 §6, measured) |
| Yusuke `X` 4 (Spirit Gun) | 0x29, 61, 60, holds | `0x098101`, koma 4 | no charge: a tap and a hold of 120 both return at +64 (state only). The shot fires at press + 30 even while X is held (C4 §2) |
| Yusuke `up X` 4 (Rei Kou Dan) | 0x2a, 71, 60, holds | `0x098101`, koma 4 | straight through, 71/71 on `K/4upX_tap`, idle at +74 (measured). No charge, against the guide |
| Yusuke `X` 5 (Spirit Gun, two levels) | 0x2b, 120, 60, holds | `0x098102`, koma 5 | one animation for the tap and both levels (measured on 5 paths). A hold sits in frames 4-55; level 1 jumps to 56 (tap at s 20, hold 65 at s 64) and level 2 to 92 (hold 66 at s 65, hold 120 at s 119, hold 300 at s 299). The exact check fails the other level's target and a switch one frame late. Level 2 iff X is held 66 or more; no auto-fire to 3600 frames, against the guide and the owner's note (C4 §3). Idle at +50 (tap), +94 (hold 65), +96 (hold 66), +150 (hold 120), +330 (hold 300) |
| Yusuke `up X` 5 (Rei Kou Dan) | 0x2c, 96, 60, holds | `0x098102`, koma 5 | straight through, 96/96 on `K/5upX_tap` and `K/5upX_w42`, idle at +99 (measured). No charge, against the guide |

**Hit records (pass 2).** The kind byte (record `+0x00`) is also the clash
tier; vfx-sfx.json `moves` carries it.

| special | records (kind) | grade |
|---|---|---|
| Kakashi `X` 5 | 24 (5), the dash box, 0 damage; 25, 26, 27 (5): 10 type 1, 10 type 2, 16 type 6 | inferred: 0x2b's track enables them and the damage and type are C3's three hits. C3 read no record numbers for X |
| Kakashi `up X` 5 | 28, 29, 30, 36 (4): 4 type 2, 4 type 1, 1 type 1, 5 type 2 | inferred: the only kind-4 records no track and no measured shot claims, and their damage and type are C3's dog hits. Which dog uses which is unknown. C3's 8-damage type-2 hit matches no record (two 4s on one frame would explain it: inferred) |
| Kakashi `X` 6 | 31 (5), the dash box; 32, 33, 34 (5): 2 type 1, 2 type 2, 40 type 6 | inferred, as for 5 |
| Kakashi `up X` 6 | 35 (4): 3 type 1 | measured (element 291, C3 §6) |
| Yusuke `X` 4 | 22 (4): 28 type 5 | measured (element 278, C4 §2) |
| Yusuke `up X` 4 | 23 (5): hits 1-4; 24 (5): the finisher, 20 type 6 | 23 measured (element 279, C4 §4); 24 inferred (0x2a's track at frame 43, and its damage and type; its box wasn't read) |
| Yusuke `X` 5 | 25 (4): level 1, 32 type 6; 26 (4): level 2, 44 type 5 | measured (elements 281 and 282, C4 §3) |
| Yusuke `up X` 5 | 27 (5): hits 1-7; 28 (5): the finisher, 20 type 6 | 27 measured (element 283, C4 §4); 28 inferred (0x2c's track at frame 65) |

### 8.1 The special strips (`special-strips.json`)

scripts/analysis/special_strips.py
writes special-strips.json; its test
scripts/tests/test_special_strips.py
fails when the JSON drifts from a fresh build. It holds boxes, frame
indices and SHA-256s, no pixels. The sheets stay in `jus_files`.

- **Anim strips** (`<move>_k<koma>`, no `@`) are the fighter's frames;
  **shots** (`<shot>@k<koma>`) are the effect frames. `file` is the key with
  `@` turned into `_`. Copy `box`, `frames`, `fps`, `loop` and `file` of
  every `strips` entry as they are.
- `uncut` (pass 2) holds art that is on the sheet but that no box cuts
  cleanly, with the same fields as a strip plus `uncut`, the reason. It is
  evidence, not a cut. The one entry is
  `eye@k6` (§8.4).
- Each entry has `sheet` and `sheet_sha256`, `cells` (the koma cell each
  frame shows, in order), `source` (the anim or effect id and the archives
  its cells come from), `what`, `frame_check` (each frame's sheet rect,
  cell, `colour_cover`, `shape_cover` and grade) and `grade` (the worst
  frame's).
- `boxes` replaces `box` and `frames` when a strip spans two sheet rows
  (Awakening): a list of `{box, pick}` in play order. **The join rule:**
  cut each `box` on its own (frames split on 4 or more empty
  columns), keep that box's `pick` frames in the order listed, then put
  the lists end to end. Frame k of the joined strip is `cells[k]`. (Not
  `parts`: the strips' sprites.json already uses that for
  `{part: [start, end)}`.)
- Grades, from the cell drawn from the game's tiles against the sheet
  frame: `clean` (both colour covers 0.9+), `extra` (the cell is all there,
  plus other art), `palette` (the shape fits 0.9+, the colours don't),
  `near` (both shape covers 0.8+: a redraw), `part` (the cell's shape is
  all in the frame, which is bigger), `by eye`.
- Frames are split on 4 or more empty columns.
- `fps` is 60 over the commonest cell length (ties go to the shorter);
  `loop` is the animation's or effect's loop byte. `fps` is one number for
  a strip whose cells play at different lengths, so it is not a real frame
  rate. `up_x_rei_kou_dan_k5` gets 30 from the rush's 2-frame ping-pong
  of cells 14 and 15 (11 of its 26 spans; cell 14 isn't on the strip),
  where the 4-koma gets 20 from its 3-frame spans. The real timing is
  anim-timing.json's `cells` (each cell's start and length).
- `overlaid` (pass 2, optional) lists fighter cells the sheet only draws
  under an effect, so they grade `palette` at best (Raikiri's and
  Chidori's cells 5 and 7, drawn inside the lightning).

| key | frames on the sheet | fps, loop | grade | what |
|---|---|---|---|---|
| `x_beam_k4` | Kakashi row y 5580, frames 1-6 = cells 1-6 | 15, no | clean | the beam's fighter frames |
| `up_x_dogs_k4` | row y 5885, frames 0-5, 7, 9, 10, 12 = cells 7-16 | 20, no | clean | the dogs' fighter frames |
| `beam_park@k4`, `beam_head@k4`, `beam_bolt@k4` | row y 5580, frames 7-8, 11-12, 13-14 | 15, loop | palette, extra, palette | the emitter (0x060461), the first bolt (0x060463), bolts 2-17 (0x060462) |
| `dog_pack@k4` | row y 5885, frame 20 | 2, no | part | the anchor (0x060464), the pack that never hits |
| `dog_1@k4` … `dog_4@k4` | row y 5985, frames 2-3, 4-5, 6-7, 0-1 | 15, loop | palette, part, palette, palette | dogs 1-4 (0x060466, 0x060469, 0x060468, 0x060467) |
| `x_spirit_gun_k6` | Yusuke row y 1812, frames 0-5, 8-11 = cells 0-9 | 15, no | extra | X's fighter frames (cell 5 is drawn with its firing arc) |
| `up_x_awakening_k6` | rows y 2038 and y 2110 (`boxes`) | 20, no | near | Awakening's fighter frames; row 2's cells 28, 30, 33 and 34 are redraws |
| `spirit_gun_l1@k6`, `spirit_gun_l2@k6` | row y 1812 frame 7; row y 1900 frame 14 | 20, loop | palette, clean | level 1's ball (0x0981a5), level 2's (0x0981a6); one of each ball's two cells |
| `finisher@k6` | row y 2110, frame 11 | 20, loop | by eye | Awakening's finishing shot (0x0981ab) |
| `x_raikiri_k5` | Kakashi row y 6380, frames 0-4, 8, 15, 10-14 = cells 0-11 | 15, no | palette | Raikiri's fighter frames (cells 5 and 7 are overlaid) |
| `up_x_dogs_k5` | row y 7045, frames 0-5, 7, 9, 10, 12 = cells 12-21 | 20, no | clean | Kuchiyose's fighter frames |
| `dog_pack@k5` | row y 7045, frame 20 | 2, no | part | the pack (0x060495); tied to C3's kind-13 entity by its 29-frame life (inferred) |
| `dog_8b@k5`, `dog_8c@k5`, `dog_8e@k5`, `dog_92@k5`, `dog_8f@k5`, `dog_91@k5`, `dog_90@k5` | row y 7153, frames 0-1, 2-3, 5-4, 6-7, 8-9, 10-11, 12-13 | 15, loop | palette or part | seven dogs (0x06048b, 8c, 8e, 92, 8f, 91, 90), for C3's seven shots; which shot is which dog is unknown |
| `x_chidori_k6` | row y 7550, frames 0-4, 8, 11, 10, 12-15 = cells 0-11 | 15, no | palette | Chidori's fighter frames (cells 5 and 7 are overlaid) |
| `up_x_mangekyou_k6` | row y 8230, frames 0-6 = cells 12-18 | 15, no | clean | Mangekyou's fighter frames |
| `x_spirit_gun_k4` | Yusuke row y 1290, frames 0, 1, 5, 8-10, 16-19 = cells 0-9 | 15, no | extra | 4-koma X's fighter frames |
| `spirit_gun@k4` | row y 1290, frames 12-13 | 20, loop | clean | the shot (0x098162) |
| `up_x_rei_kou_dan_k4` | row y 1391, frames 0, 6, 1, 16-19 = cells 10-12, 14-17 | 20, no | extra | 4-koma up X's fighter frames |
| `x_spirit_gun_k5` | row y 1505, frames 0-2, 6-8, 10-13 = cells 0-9 | 20, no | extra | 5-koma X's fighter frames |
| `spirit_gun_l1@k5`, `spirit_gun_l2@k5` | row y 1585, frames 12-13; 14-15 | 20, loop | clean | level 1's shot (0x098183), level 2's (0x098184) |
| `up_x_rei_kou_dan_k5` | row y 1703, frames 0, 6, 1, 16-19 = cells 10-12, 15-18 | 30, no | extra | 5-koma up X's fighter frames |

**Screenshots agree (by eye).** C1's `upX_near-dog2-f109` shows a
white dog with blue speed lines running in from the right, as the render
of 0x060469 (dog 2) does. C2's `upX_near-finisher-f151` shows a cyan comet
flying up-left at the launched Goku, as the render of 0x0981ab does.

### 8.2 The hold, and C2's aura

- **No fighter strip loops during a hold.** C2's hold-300 screenshots show
  one start-up pose held at plans 60 and 83, and one pointing pose at 115,
  200, 201, 205 and 250 (C2 §11; only the aura around it changes). The body
  box stays the same over the whole start-up hold (anim frames 4-35 share
  one box) and over the later hold (frames 40-47), measured. So the
  fighter holds a pose; which frame of the span it holds is not measured
  (§8).
- **C2's aura is an effect, not a strip.** From s 100 of a long hold
  (anim frame 40) 0x2d spawns effect `0x0981a2` (static; vfx-sfx.md §5).
  It loops (loop byte 1) over 8 frames, cells 2 and 3 of `yh_b_01_e60_.dtx`.
  That's plan 113 in hold 300, and C2's screenshot at plan 115 is the first
  to show the aura (C2 §3, item 4). The render of 0x0981a2 is the same
  white-cyan glow around a pointing figure, and its two cells explain why
  plans 200 and 201 differ inside the aura (inferred, by eye). The sheet's
  X row 2, frames 5-6, draw cell 4 with those two cells (colour cover 1.0).
- The orb at the finger during the start-up hold is effect `0x09813a`,
  spawned at anim frame 7 (static; C2's plan-60 screenshot shows it).

### 8.3 Are Kakashi's `ninken` and `pakkun` strips the dogs' art?

**No** (inferred from the image match). The hand-cut `ninken` strip
(Kakashi.png box (0, 4789, W, 4845), frames 7-9) and `pakkun` (box (0, 3651,
W, 3724), frames 6-7) were compared with every cell of the koma-4 dog lists
(`na_b_04_e40_.dtx` cells 0-13, `na_b_04_e41_.dtx` cells 0-2):

- no ninken frame fits any `e40`/`e41` cell by colour: the best cover
  either way is 0.31 (frame 8 on `e40` cell 6, a 23×21 dog). For pakkun it
  is 0.07;
- ninken's frames 7-9 fit the base archive's `na_b_04_e02_.dtx` cells 0-2
  instead (shape 0.71-0.79 and 1.0, colour 0.48-0.55): base-kit art;
- pakkun's frames fit nothing well (best: `na_b_04_e00.dtx` cells 59 and 60,
  colour 0.10-0.16).

The special's dogs are the `dog_*@k4` strips (§8.1), drawn on the sheet's
"4 koma special attack 2" rows.

### 8.4 Not found

| what | searched |
|---|---|
| Awakening's cells 13 and 20 on the sheet (frame 3 is cell 14, a look-alike; the cell-20 pose is too loose, shape 0.77) | `jus_files/sprites/characters/YuYu Hakusho/yusuke_urameshi/Yusuke_Urameshi.png`, rows y 2038-2192 |
| the finishing shot's cells as drawn (only a by-eye fit: the sheet's comet is about 80% of the 80×80 cell) | the same rows; render `jus_files/extracted/vfx-sfx/render/yh_b_01_6/0981ab.png` |
| the balls' second cells (`e61` cells 6 and 8) | `Yusuke_Urameshi.png`, rows y 1812-2020; renders in `jus_files/extracted/vfx-sfx/render/yh_b_01_6/` |
| the beam row's frames 9-10 and 15-26 (smaller beam pieces) | every cell of `chr/na_b_04_4.aar`'s lists and of the base `na_b_04_e00` to `e04` lists; renders in `jus_files/extracted/vfx-sfx/render/na_b_04_4/` |
| the source of the burst of lines C2 saw at plan 100 of hold 300 (s 87, inside the held span) | 0x2d's spawn keys (vfx-sfx.json `moves`); none fires between anim frames 8 and 35 |
| what spawns the shot effects (the beam's 0x060461-0x060463, the dogs' 0x060464-0x060469, Awakening's 0x0981ab): none is in its animation's spawn keys | vfx-sfx.json `moves` for 0x29, 0x2a and 0x2e |
| Yusuke 4-koma X's cell 16 (anim frames 44-50) on the sheet: no fighter frame fits (best colour cover 0.47) | `jus_files/sprites/characters/YuYu Hakusho/yusuke_urameshi/Yusuke_Urameshi.png`, X rows y 1290-1380; render `jus_files/extracted/vfx-sfx/render/yh_b_01_4/`; the cells of `chr/yh_b_01_4.aar` |
| Yusuke 4-koma up X's cell 13 (the rush, frames 27-34): the sheet draws it only under the blasts 0x098165 and 0x098166 (best 0.39) | the same sheet, rows y 1391-1475; render `jus_files/extracted/vfx-sfx/render/yh_b_01_4/098165.png` (0x098166 has no render in that folder) |
| Yusuke 5-koma up X's cells 13 and 14 (the rush): drawn only under the blasts 0x098188 and 0x098189 | the same sheet, rows y 1703-1785; renders in `jus_files/extracted/vfx-sfx/render/yh_b_01_5/` |
| Kakashi's dog effects 0x06048a and 0x060489 (the fan) on the sheet | `jus_files/sprites/characters/Naruto/kakashi/Kakashi.png`, rows y 7045-7210; renders in `jus_files/extracted/vfx-sfx/render/na_b_04_5/` |
| which dog record (28, 29, 30, 36) and which dog effect each of C3's seven shots uses | C3 read no dog records (no set G on them); static records and tracks only |
| what spawns the pass-2 shot effects (the pack 0x060495, the dogs 0x06048b-0x060492, the eye 0x0604a9, Yusuke's 0x098162, 0x098183, 0x098184): none is in its animation's spawn keys | vfx-sfx.json `moves` for Kakashi 0x2c, 0x2e and Yusuke 0x29, 0x2b |
| a frame-by-frame box check of Kakashi's four pass-2 rows and Yusuke's 4-koma X | C3 `trials/A`, `C`, `G26-27` and C4 `trials2/A` log no P1 body box; a capture that does would need the emulator (not run) |
| which frame shows inside a held span | the boxes don't change there (§8) |
| a clean cut of Mangekyou's eye (0x0604a9, record 35). The sheet draws its four cells at row y 8230, frames 7-10, but each frame also holds the ズズ glyphs (effect 0x0604a7, the same 526 black and 138 grey pixels in every frame) fused to the splash, about 35% wider than the cell (shape cover 0.95-0.98 of the cell, 0.62-0.73 of the frame). The glyphs sit left of the splash, but the splash's red reaches into their columns in every frame, so a box that drops the glyphs clips the splash: 1.2-6.3% of each frame's red pixels (33/1105, 68/1082, 43/1013, 18/1522) lie in the 25 columns that hold a black or grey glyph pixel. Red is the splash's three reds (174,0,0), (255,121,121) and (56,0,0), counted over the frame's `sheet_rect` (`special_strips.glyph_red`). special-strips.json keeps it under `uncut`, not `strips`. The four frames come from `na_b_04_e61_.dtx` cells 0-3, as the render `0604a9.png` does | `jus_files/sprites/characters/Naruto/kakashi/Kakashi.png`, row y 8230-8331; cells from `chr/na_b_04_6.aar`'s `na_b_04_e61_.dtx` (texture 0x0604a1); render `jus_files/extracted/vfx-sfx/render/na_b_04_6/0604a9.png` |


Komamen's `moves` rows are STATIC animation labels and decoded cells from `anim_rows.STATIC_MOVES`.
Session A measured motion and state timing, not the art clock. X/up X labels bind the frame-16
spawns and sound events; their motion and live animation appearance await capture.
`cancel_table.played_anims` excludes these static labels from its measured move joins.
