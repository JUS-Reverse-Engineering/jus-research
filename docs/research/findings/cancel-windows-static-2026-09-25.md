# Where JUS defines cancels (static, 2026-09-25)

When a move's cancel window opens, and which moves it can cancel into,
read from the game files for every battle character. No emulator was used.
Tracker items: `jus-cancel-table-extractor-9qry` (the extractor, this note) and
`jus-cancel-live-checks-u9qr` (the three live checks in §8).

- Extractor: [scripts/analysis/cancel_table.py](../../../scripts/analysis/cancel_table.py),
  test [scripts/tests/test_cancel_table.py](../../../scripts/tests/test_cancel_table.py).
- Output: [docs/rebuild/cancel-table.json](../../rebuild/cancel-table.json),
  schema [docs/rebuild/cancel-table.md](../../rebuild/cancel-table.md).
- Disassembly cites are `jus_files/analysis/disasm/ov6.txt` addresses. Bytes
  are `jus_files/overlays/ov06.bin` (raw, loaded at 0x0214CD20) and
  `jus_files/ripped_jus_files/chr/ChrArc.aar`, submodule pointer `f99383fd`.

Grades: **measured** = read straight from bytes or a capture; **inferred** =
follows from measured pieces but is not traced end to end; **lead** = a
reading with a gate nobody has traced; **owner** = owner testimony.

Source: this started as a lead from the Kakashi fix agent (2026-09-25,
scratchpad `cancel-finding.md`, not committed). Everything below was
re-read from the bytes; §6 lists where the lead was wrong.

## 1. When a window opens

- Each move's animation NoteTrack (`chr/<prefix>.aar` → `<prefix>.amt`,
  node SP01) carries an event `op3 sub0 arg 0x1` (ground) or
  `op3 sub0 arg 0x15` (air) on one frame. `anim_events.py <who> --anim <id>`
  prints it. (measured: the bytes)
- op3 reaches the fighter callback 0x02157A44: the op table 0x0217200C
  sends op3 to 0x021569AC, whose sub table 0x02172000 sends sub0 to
  0x021568E8, which calls `[obj+0x70]` with the arg (event+2, 0x02156924)
  and the fighter (`[obj+0x74]`, 0x0215692C). The fighter init loads
  0x02157A44 from the literal at 0x02156D70 (0x02156CD0) and 0x021553E0
  stores it to +0x70 (0x02155438). It is the only literal naming 0x02157A44.
  (measured: code)
- The callback is a switch on the arg (jump table at 0x02157A60). Case 0x1
  stores 1 to fighter+0xF3 (0x02157B90). Case 0x15 stores 1 to +0xF4
  (0x02157B9C). Case 0x1D stores 0 to +0xC8, the buffered follow-up
  (0x02157BA8). (measured: code)
- +0xF3 and +0xF4 are written nowhere else except the move-start clear at
  0x0215A034-38, which also clears +0xC8. So a flag stays set from its key
  until the next move starts, and a second key in the same animation changes
  nothing. (measured: every `#0xf3]`/`#0xf4]` access in ov6.txt.) So the
  table uses the earliest key. That rests on the code reading only: 74 rows
  (69 of them ids 1-10) have two keys of one kind, and no gated case is one
  of them.
- The state-9 (attack) handler reads +0xF3 after the ground reader
  (0x0215A464-6C) and +0xF4 after the air reader (0x0215A4A0-A4). Which
  reader runs depends on 0x0215A708, read as "on the ground". (the calls:
  measured; what 0x0215A708 means: inferred)
- **Cancel start = earliest key frame + 2**, counted in animation frames
  from the move's anchor (anim frame 0 = anchor, anim-timing.md §1). The +2
  is one constant read off Kakashi's six §8 register starts; Yusuke's four
  starts were held out and fit too. Git can't show that order, so take it on
  this note's word. Those starts are not raw measurements either: the kit
  docs derive each one (successor onset minus the follow-up's standalone
  lag) and grade it inferred. The live checks then timed it end to end for
  Kakashi (RESULTS): ground key +11 → cancel start +12 → Y starts
  +13; air key +14 → +15 → air Y starts +16. The key writes the flag on one
  tick, the state-9 handler acts on it the next tick, and the new move
  starts the tick after. (measured for Kakashi B and air B in those trials;
  other moves and characters: inferred)
- Inputs buffer. The reader runs every state-9 frame and latches an allowed
  press into +0xC8 (0x0215A4CC); the cancel fires on the tick after the flag
  is set (0x0215A4D0-0x0215A58C): the flag is set on +11 and the handler
  acts on +12, since inside a tick the handler reads F3 before the key writes
  it (RESULTS (b)). That is why presses at k = 4 in the grids come out
  at the window start. (measured: code and the one-tick gap, for Kakashi;
  the order inside a tick and the match to the grids: inferred)

## 2. What a move can cancel into

- **The move table** sits at 0x021712B8: 12 bytes per move id, u32 anim, u32
  mask, u32 misc. Ids 1-10 are B, Y, side B, side Y, up B, up Y, down B,
  down Y, air B, air Y (anims 0x1e-0x27). (the bytes: measured; the names:
  measured on Kakashi and Yusuke where a capture matched the move to the
  table anim, anim-timing.json, which leaves out Yusuke side Y; inferred for
  the other 72 archives)

  | id | move | anim | mask |
  |---|---|---|---|
  | 1 | B | 0x1e | 0x2 |
  | 2 | Y | 0x1f | 0xae |
  | 3 | side B | 0x20 | 0xaa |
  | 4 | side Y | 0x21 | 0x1fe |
  | 5 | up B | 0x22 | 0xaa |
  | 6 | up Y | 0x23 | 0x1fe |
  | 7 | down B | 0x24 | 0xaa |
  | 8 | down Y | 0x25 | 0x1fe |
  | 9 | air B | 0x26 | 0x3fe |
  | 10 | air Y | 0x27 | 0x7fe |
  | 11 | input 0x1000 | 0x18 | all ones |
  | 12 | fighter+0xD1 set | 0x28 | all ones |
  | 13, 14 | X, up X | per-fighter row | all ones |

- **The mask test.** Starting a move from neutral (0x02159D7C) sets
  C4 = 0, then ORs in the move's mask (0x02159DB8, 0x02159E08-20). In state
  9 a follow-up id j is latched only if bit j is clear in C0 | C4
  (0x0215A4B4-CC) and fires only if bit j is clear in C4 (0x0215A550-60).
  Then C4 |= mask[j] (0x0215A56C-78). So blocks pile up along a chain: after
  B → up B, C4 = 0x2 | 0xaa, and Y is still open. (measured: code)
- In this table the OR never changes an answer. Every allowed hop goes to a
  move whose mask contains the one before (checked over all ids 1-10 and both
  window kinds), so C4 always equals the latest move's mask. No case in the
  data can tell the OR apart from "latest mask only", and the gate can't
  catch a broken OR. The unit test `test_masks_pile_up_along_a_chain` does.
- **The readers** (return values decoded from the code):
  - ground 0x0215A720: 1-6, and 11, 12, 13, 14;
  - air 0x0215A8C0: 9, 10;
  - down 0x0215A8F8: 7, 8, 11. Only the neutral start uses it (reader
    table 0x02172178 slot 2), so **down B and down Y are never cancel
    targets**. (measured: code)
- Air attacks are capped: with +0xDA ≥ 2 the air reader is skipped
  (0x0215A484-98), and ids 9/10 add 1 to +0xDA at move start
  (0x02159F5C-80). (measured: code)
- **Ids 11-14 are special.** Id 11 is never a cancel target (0x0215A4FC).
  Id 12 skips C4 at the latch and has its own path (0x0215A590-0x0215A614);
  ids 13/14 need 0x0215A708 and 0x0207834C to return true
  (0x0215A50C-2C). Every normal mask leaves bits 12-14 clear, so a ground
  window may lead into them, but those gates are not read. Ids 13/14 pick
  their anim row from a per-fighter byte (0x02159FB8-DC), so their anim is
  not static. X = input bit 0x40 is from guard-sp.md. (the paths: measured;
  what they do in play: lead)
- **C0 is a second mask** tested at both the neutral start and the latch.
  No ov6 instruction stores to +0xC0 with an immediate offset, so its value
  is unknown statically. The extractor assumes the bit is clear. Live, C0
  read `0x00000000` on every row of every Kakashi trial (RESULTS).
  (measured for Kakashi in that fixture; other characters: lead)

## 3. Is the move table shared? Yes (inferred; every static part is measured)

- Every read of the table uses an ov6 literal-pool constant, not a
  per-character pointer: 0x0215A63C = 0x021712B8 (anim, 0x02159F4C and
  0x02159FC4), 0x0215A65C and 0x02159ECC = 0x021712BC (mask, 0x0215A56C and
  0x02159E08), 0x02159ED0 = 0x021712C0 (misc byte, 0x02159E48), and
  0x0215A64C/0x0215A658 (0x0215A0E0, 0x0215A398). All seven uses are loads.
  (measured: every pc-relative load in ov06.bin that resolves to these
  literals)
- 0x021712B8 is inside ov06.bin's file image (0x0214CD20-0x02172960; bss
  starts after it), and ov6 is stored raw. So the table's bytes are in the
  overlay, not in character data. (measured)
- Among the other disassemblies, only ov5 has words in this range, and ov5
  loads at the same base as ov6, so the two are never in memory together.
  (measured: overlays.json)
- The ground reader 0x0215A720 does not load the table; it only returns an
  id. The table is read by the neutral start (0x02159D7C) and the state-9
  handler (0x02159EF8).
- Residual: a store through a computed pointer can't be ruled out
  statically, so the conclusion stays inferred until that path is closed. A
  read-only dump of 0x021712B8 with a different character loaded would close
  it.

## 4. The gate: 79 of 79 cases pass

`python3 scripts/analysis/cancel_table.py check` rebuilds the table and
checks it against every cancel row in the two kit docs: the generated
cancel-routes blocks (declared routes and measured negatives), Kakashi's §8
register row, Kakashi's "nothing → B, jump, dash or guard", and Yusuke's
"side B does not cancel into up B". It also checks the owner routes in §5.
Each case carries the grade its source gives. It exits 1 on any miss or if
the committed JSON is stale.

| set | cases | grade | result |
|---|---|---|---|
| Kakashi routes that cancel: allowed | 16 | measured | all allowed |
| Kakashi routes that cancel: start | 16 | inferred (kit doc: onset minus lag) | +13, +23, +24, +21, +21, +57 all match |
| Kakashi measured negatives (B → B, Y → B/Y, down B → B, down Y → B/Y, side B → B, side Y → B/Y, up B → B) | 10 | measured | all blocked by the mask |
| Kakashi §8 register starts | 6 | measured per §8 | pass; §8 grades them measured, the route rows grade the same starts inferred |
| Kakashi nothing → B; no jump/dash/guard | 2 | measured (§8) | pass |
| Yusuke routes that cancel: allowed | 10 | measured | all allowed |
| Yusuke routes that cancel: start | 10 | inferred (kit doc) | +12, +18, +28, +20 all match |
| Yusuke side B → up B dropped (table row and :277 prose) | 2 | measured | blocked by bit 5 of 0xaa |
| Owner routes (Kakashi five, Sasuke one) | 6 | owner | pass (§5) |
| B → up B → Y: start of the last hop | 1 | inferred (kit doc) | +24, the doc's exact up B → Y start |

Limits:

- The kit docs disagree on the grade. §8's register says "measured: one
  cancel frame per normal", and the route rows grade the same starts
  inferred. The gate keeps each source's label and names the split in the
  case text.
- The +2 is one constant read off Kakashi's six register starts, with
  Yusuke's four held out (§1). Git can't show that order. The live checks
  later measured it for Kakashi B (ground key +11 → start +13) and air B
  (air key +14 → start +16) (RESULTS); for every other move and
  character it stays inferred.
- The jump/dash/guard case checks only what the state-9 readers return (move
  ids and 0). It doesn't test a jump, dash or guard press inside a window.
- The gate can't catch a broken mask OR (§2); the unit test does.

## 5. Owner testimony used by the gate

All six are cited from
[OWNER-NOTES.md](../moveset-notes/OWNER-NOTES.md); the gate finds each quote
by its text.

- "up Y cancels into air B or air Y" (Kakashi, 2026-09-13, :338-339).
  Predicted from +57.
- "kakashi's b should cancel into his upB … B upB Y is a valid combo in JUS"
  and "his air B cancels into his air Y as well" (Kakashi, relayed
  2026-09-25, :495 and :497). Predicted: B → up B from +13; Y after up B
  from +24 (C4 = 0xaa leaves bit 2 clear), which matches the kit doc's
  up B → Y start; air B → air Y from +16 (air B's air key at f14). None of
  the three chains has a live measurement.
- Sasuke up B "into X, up B into Y" (2026-09-03, :68-70). Up B → Y is
  predicted from +15 (na_b_02 up B key f13; bit 2 clear in 0xaa). Up B → X
  is id 13, whose gates are not read, so it is not gated.

## 6. Where the lead was wrong or short

- The ground reader returns 11-14 as well as 1-6 (the lead said 1-6 only).
- "Down moves are never a target" is measured, not inferred: 0x02159990
  only tests +0xA0 == 0x1A, and neither state-9 reader returns 7 or 8.
- Kakashi side Y has an `op3 sub0 arg 0x1` key at f36 (the lead's
  "no arg 0x1 key" is wrong). Predicted start +38, not measured; its mash
  loop adds 30 frames before f36 (anim-timing.md), so in game frames it
  would open later when mashed.
- Kakashi down Y has a ground key at f34 (+36); its mask allows no ground
  follow-up, so nothing changes.
- Case 0x1D of the callback clears the buffered follow-up; the lead did not
  list it.

## 7. Conflicts with other docs

- [state-code-handler-table-static.md](state-code-handler-table-static.md)
  :186 and [physics.md](../../confirmed-facts/physics.md) :480 called the word
  load at 0x02159E14, OR'd into +0xC4, "unrelated". It is the cancel mask
  (§2). Both docs also frame the record base as 0x021712BC with the install
  byte at record+4; with the anim word read from 0x021712B8 (0x02159F4C),
  the record starts at 0x021712B8 and the install byte is at record+8. Same
  bytes, different framing. Both docs now say so (2026-09-25).
- `jus-wmqi.6.18` lists NoteTrack ops 0-3 as TBD. op3 sub0 args 0x1, 0x15
  and 0x1D are now decoded (§1).
- **Yusuke side Y plays anim 0x28** (anim-timing.json, measured on three
  captures), but the table gives id 4 anim 0x21. 0x28 is id 12's table
  anim. So the anim a move plays can differ from the table's; the extractor
  gives Yusuke side Y null with that reason. Why it differs is not known.

## 8. Still open, and the three live checks

Open: what C0 holds for characters other than Kakashi; what 0x0215A708
tests; what ids 11-14 are in play; how many other moves play a different anim than the
table's (only Kakashi and Yusuke have played anims measured); and how
charge pauses or mash loops shift the start in game frames. In four
archives (db_b_06, db_b_07, db_b_08, op_b_07) anim 0x19's GN02 node runs past
the buffer. That node is not a move anim; anim_events now lists it in
`node_errors`, and the four archives' move rows are read like the rest
(db_b_06 B +16, db_b_07 side B air +21, op_b_07 air B air +19).

The live checks, filed as `jus-cancel-live-checks-u9qr`
(fixture `pc-kakashi-npc-jotaro-dark-tournament`, plan-press basis, anchor
as anim-timing.md §1):

- **(a)** GDB break on pc 0x02157B90 (the +0xF3 write) during one Kakashi
  neutral B. Positive control: 0x0215A030 fires on the anchor. Pass: it
  fires once, on anchor + 11.
- **(b)** At that break in a B then Y trial (Y at k = 4), log r5, u32
  +0xC0, u32 +0xC4, u8 +0xC8, s8 +0xCA, u8 +0xF3, u8 +0xF4; break again on
  0x0215A624 and log r4 and the same fields. Pass: C4 = 0x2, C8 = 2, C0 bit 2
  clear, then r4 = 2 on anchor + 13. Record C0 in full.
- **(c)** Kakashi jump, air B, then air Y at k = 4, 8, 12, 14, 15, 16, 17,
  20, 24, 28 from the air B anchor, plus an air B baseline. Pass: presses up
  to +16 start air Y at +16 plus its own lag; later presses start at press
  plus lag. Negative control: air B then air B at k = 8 and 20 does not
  cancel.

When all three pass, update the two docs in §7 and regrade the +2.

Done 2026-09-25 (RESULTS): (a) and (c) pass. (b) fails one clause:
`0x0215A624` fires on + 12, not + 13, and Y's own move start is on + 13.
The session lead ruled that clause a spec error: the rule in §1 puts + 13 on
the new move's start, not on that pc (only (b)'s pass line above did), and
the kit's k is press-to-press (cancel_plans.py:232). So the checks count as
passed; the two docs in §7 are fixed and the +2 is regraded
above.

## 9. Second opinion (Codex)

Codex (`gpt-5.6-sol`, run 2026-09-25) got
the raw ov6 listings and the table words with neutral questions and no
hypothesis: which switch cases store to +0xF3/+0xF4/+0xC8, what each reader
returns, when the state-9 block latches and fires a follow-up, which
addresses the pc-relative loads read, and which transitions pass for ids
1-10. Its answers match §1-§3 on every point, including the reader return
sets, the literal addresses, id 12's C4 bypass and the i = 1 → 5 → 2 chain.

One point Codex flagged and could not settle (codex-answer.txt:301, :358).
Question 6 said "starting move i" without saying what i was. Codex read i
as the reader's return value (the id stored to +0xCA), which is this note's
reading. It said the other reading, i as 0x02159D7C's dispatch argument r1,
can't be decided for i = 3..10 from the data shown, since only dispatch
entries 0-2 were given. That is a gap in the question, not a disagreement
with §2, but it is not a confirmation of the dispatch either. Prompt and
answer:
[cancel-windows-static-2026-09-25/](cancel-windows-static-2026-09-25/).

## Addendum (2026-10-27): the other readers of the table

Three points above are incomplete. `cancel_table.c4_readers()` re-reads each one
from the ROM, and `test_cancel_table.CodeFactsTest` pins it.

- **+0xC4 has a third reader.** An immediate-offset load census of arm9 and
  every overlay finds three bit tests of a +0xC4 word: the state-9 latch
  (0x0215A4C8), the fire test (0x0215A55C), and the ov11 AI at
  0x0217BBE4-0x0217BC10. The AI loads [[ai+0x20]+0xC4], ORs the literal
  0x7F9980 (0x0217BFBC), and offers each id in 1..23 whose bit is clear. Bit 23
  is therefore tested, though no state-9 reader returns 23. arm9's other
  +0xC4 loads are counters and vtable calls. ov0-5/7/8 load at ov6's base, so
  they never run alongside it. The tested bits are 1-6, 9-11, 13, 14 and 23,
  and no reader tests 0, 7, 8, 12, 15-22 or 24-31. Limit: the census sees only
  `ldr rD,[rN,#0xC4]`. A read through a register offset or a block copy would
  not show up.
- **misc is three ldrsb bytes.** Byte 0 (0x02159E50) is the state the move
  starts in: 9 for the normals, 0x0a for X / up X, 0x0b for the dream attack,
  0x0c for the Ultimate Action. Byte 1 (0x0215A0E8) is a battle-record counter
  index that the move start increments: fighter stats +0x6e + 2k via
  0x0215A660, saturating, and -1 means none. Byte 2 (0x0215A3A0) is the counter
  a contact increments. Byte 3 has no reader: the literal census finds only the
  seven loads listed in §3.
- **X / up X anim rows follow the koma.** The state init (0x02159FB8-0x02159FDC)
  reads the anim from row `id + 2 * (byte - 3)`, where byte is
  [[[fighter+0x1A0]+0x174]]+0x8c. The exported kits identify byte as the koma
  size minus 1: every exported set X / up X `jus_anim` equals row 13 / 14 +
  2 * (koma - 4), and `export_kit._move_table_rows` refuses any mismatch. So
  rows 15-22 (anims 0x2b-0x32) are koma 5-8's, and row 23 is all zero. The
  move start still reads mask and state byte from row 13 / 14.
