# Cancel table: when each move's cancel opens, and what it cancels into

For every JUS battle character (74 archives `chr/xx_b_NN.aar`) and every
move id 1-14, this gives the frame a move's cancel window opens and the
moves it can cancel into. It is static: read from the game files, no
emulator. Tracker item: `jus-cancel-table-extractor-9qry`.

- The machine-readable copy is [cancel-table.json](cancel-table.json).
  Use the JSON for machine-readable data.
- One tool writes and checks it:
  [scripts/analysis/cancel_table.py](../../scripts/analysis/cancel_table.py).
  How it works, the disassembly behind it, and the grades:
  [cancel-windows-static-2026-09-25.md](../research/findings/cancel-windows-static-2026-09-25.md).

## 1. Run it

```bash
python3 scripts/analysis/cancel_table.py check    # the gate: exit 0 pass, 1 fail
python3 scripts/analysis/cancel_table.py build    # rewrite JSON and this special_cancel field row
python3 scripts/analysis/cancel_table.py show na_b_04
python3 -m unittest scripts/tests/test_cancel_table.py
```

`check` needs the `jus_files` submodule (`git submodule update --init`).
It prints one PASS or MISS line per case and fails if any case misses or
the committed JSON or generated special_cancel field row differs from a fresh build. No judgment is needed: the
exit code is the answer. The unittest runs the same gate and fails, not
skips, without `jus_files`.

The gate's cases, each labelled with the grade its source gives:

- every row of the generated cancel-routes blocks in
  kakashi.md and yusuke.md.
  A route that cancels gives two cases: "allowed" (measured) and "start",
  graded inferred as the kit docs grade it (successor onset minus the
  follow-up's standalone lag). A measured negative must be predicted blocked;
- Kakashi's §8 register starts. §8 calls them measured, and the gate keeps that
  label but names the split: the route rows grade the same starts inferred;
- three prose negatives. The jump/dash/guard one checks only what the state-9
  readers return;
- six owner routes from
  [OWNER-NOTES.md](../research/moveset-notes/OWNER-NOTES.md), found by their
  text, including Sasuke's up B → Y. B → up B → Y also checks the last hop's
  start against the kit doc (+24, inferred).

## 2. The rule

- **Cancel start** = the earliest NoteTrack key `op3 sub0 arg 0x1`
  (ground window) or `arg 0x15` (air window) in the move's animation, + 2.
  Frames count from the move's anchor, where animation frame 0 is the
  anchor ([anim-timing.md](anim-timing.md) §1). Grade: measured for
  Kakashi (`na_b_04`) B and air B, where a live check timed it end to end
  (ground key +11 → start +13, air key +14 → start +16;
  RESULTS);
  inferred for every other move and character. "Earliest"
  rests on the code reading only (the flag stays set until the next move):
  74 rows (69 of them ids 1-10) have two keys of one kind, and no gated
  case is one of them.
- **Follow-ups.** A ground window offers ids 1-6; an air window offers ids
  9-10. A follow-up is allowed if its bit is clear in the move's mask. In a
  chain the masks OR together: after B → up B the blocks are
  `0x2 | 0xaa`. Grade: inferred.
- Down B and down Y are never cancel targets (no state-9 reader returns
  them). Grade: measured.

## 3. JSON layout

Top level:

| key | what |
|---|---|
| `grade_notes` | what each grade means, and the caveats on `anim`, `cancel_start`, `followups`, and `special_cancel` (X and up X); `system_followups` points to it |
| `move_table` | the 14 records of the shared ov6 table at 0x021712B8: `id`, `move`, `anim`, `mask`, `misc`, `addr` |
| `code_facts` | the code readings the rule rests on, decoded from ov06.bin each build (the test pins every one) |
| `characters[]` | one entry per battle archive, sorted by prefix |

Each `characters[]` entry: `prefix` (e.g. `na_b_04`), `names` (the
[chr_b mapping](../research/chr_b-Complete-Mapping.md) rows whose File cell is
exactly this prefix, each with `chr_b`, `name` and `basis`: whether that
File cell is live-verified, flagged suspect, or not flagged), and `moves[]`.

Each `moves[]` row (one line in the file):

| field | what | grade |
|---|---|---|
| `id`, `move` | move id and name (ids 11-14 are system moves). The name is measured only where a capture matched the move to this anim (Kakashi, Yusuke, Eve), otherwise inferred from the shared table | `grades.move` |
| `anim` | the table's anim id, hex | `grades.anim` |
| `frames` | that animation's frame count | measured |
| `key` | `{"ground": [frames], "air": [frames]}`: every cancel key in the NoteTrack | `grades.key` |
| `cancel_start` | `{"ground": n}` and/or `{"air": n}`: earliest key + 2 | `grades.cancel_start` (measured only where `cites.cancel_start` is set) |
| `mask` | the table mask, hex | `grades.mask` |
| `followups` | allowed follow-up move names | `grades.followups` |
| `reason` | why a field is null, or null | |
| `special_cancel` | ids 1-10 with a ground key: `{"into": ["X", "up X"], "start": {"ground": n}, "gate": "...", "terminal": true}`. `start` is the ground `cancel_start`. Initial air slots 9-10 can have ground windows. `null` for a move with no ground key (air-key-only, no key, key at the anim's end) and for ids 11-14 | `grades.special_cancel` (measured only where `cites.special_cancel` is set: Yusuke B, Y, side Y, up Y) |
| `special_reason` | why `special_cancel` is null, or null | |
| `cites.member`, `cites.anim`, `cites.table` | archive member, anim id, table record address | |
| `cites.cancel_start` | the live check that timed this start; only on rows where one did | |
| `cites.special_cancel` | the live run that timed X out of this move; only on those rows | |

`null` means not known; the row's `reason` says why. The reasons:

- no cancel key in the NoteTrack: no window opens this way, so
  `followups` is `[]`;
- the move's SP01 node (the NoteTrack) fails to decode. No row has this
  today. An effect node that fails (anim 0x19 GN02 in db_b_06, db_b_07,
  db_b_08, op_b_07) is listed in anim_events' `node_errors` and does not
  touch the keys;
- a capture's box-clock match disagrees with the table's start animation
  (the Yusuke captures labelled side Y have a 0x28 box clock in
  [anim-timing.json](anim-timing.json), while the table start and live key
  agree with 0x21; see the J8 identity conflict);
- ids 13 and 14 take their anim row from a per-fighter byte.

## 4. Limits

- The anim is the one the table hands over at move start. A per-move
  handler can change what plays. This is checked only where a capture
  measured the played anim (Kakashi, Yusuke).
- `cancel_start` is in animation frames. A charge pause or mash loop before
  the key (Yusuke side Y, Kakashi mashed side Y) adds game frames.
- A second mask, fighter+0xC0, can block more follow-ups. It read 0 in
  every Kakashi live trial (RESULTS); for other characters it was
  never read, and the table assumes it blocks nothing.
- Id 12 (a one-tick dream-attack request, fighter+0xD1) and id 11 are not
  followups of a normal. Ids 13 and 14 are: see `special_cancel` below and
  `grade_notes.special_cancel`.
- The +2 is measured only for Kakashi B and air B
  (`jus-cancel-live-checks-u9qr`); elsewhere it is inferred.

## 5. Cancelling into X

Measured on one character only, Yusuke (6-koma):
RESULTS,
`checks.json`.

- B, Y and side Y each cancel into X one frame after the fighter's
  `+0xF3` flag goes to 1 (B window at s10 → X starts s11; Y window at
  s26 → X starts s27; side Y window at s29 → X starts s30). An X press
  before the window opens is buffered (`+0xC8` = 13) and fires on the
  first window frame.
- B's window closes somewhere between s19 and s27 (the exact close frame
  wasn't run).
- The cancelled X runs in state 9, not neutral X's state 10. One SP bar
  is spent, same as neutral X.
- Air B never cancels into X: `+0xF4` goes to 1 on the air B press, but
  no X is ever buffered, no X starts, and no SP is spent.
- Side Y's window key (29) has no row in
  [cancel-table.json](cancel-table.json); id 4 (side Y) is unresolved
  there. The live key 29 agrees with native anim 0x21, not 0x28's key 16;
  the J8 note
  identifies the unresolved geometry-capture identity.

Static (Codex session `01a0da1d-d46b-7921-ba7a-61a23c870054`), not varied
in this capture: the ground move-id reader returns 14 for up+X, 13 for X;
the air reader has no X entry; neutral X gates on `+0xF5` and `+0xC0`
(both read as expected on every row here, but neither was varied, so the
gating itself is unverified). The ov6 follow-up masks read in this capture
(B `0x02`, Y `0xAE`, side Y `0xFE`) leave bits 13/14 clear, so they don't
block X.

### The `special_cancel` field

A ground cancel window (the F3 flag, set by the move's ground NoteTrack key)
also offers X (id 13) and up X (id 14).

- Reader 0x0215A720 returns 14 for `input & 0x41 == 0x41` and 13 for
  `input & 0x40`, after its B/Y and id-11 tests, so a held B or Y shadows X.
  No mask blocks them: every mask in ids 1-10 has bits 12-14 clear.
- The window is the normals': start = earliest ground key + 2, open until the
  animation ends. An earlier press is buffered in `+0xC8`.
- Gates: grounded (`[[fighter+0x1A8]+0x10]+0x78 & 2`, 0x0215A708) and one SP
  bar (0x0207834C with cost 1, called at 0x0215A524; free if slot+0x5CE or
  +0x5CF is nonzero, refused at 0 bars).
- A cancelled X runs in state 9 and C4 becomes all ones, so nothing cancels
  out of it: `route()` ends the chain at X.
- A move needs a ground key. Air-key-only moves (Eve and Kakashi up Y,
  Yusuke up B) and every air window give no special: reader 0x0215A8C0
  returns only 9 and 10.
- Grade: the code is measured. The live runs above timed Yusuke B, Y, side Y
  and up Y; every other move and character is inferred. Yusuke side Y reads
  `null` here because its timing-source association is unresolved despite
  the table start and live key agreeing on 0x21; X is not refused.
- Basis: `start` is the cancel start (key + 2). The live X start is one tick
  after the flag (key + 1), as in the list above. The
  J8 note
  keeps these animation-frame and game-frame conventions separate.
