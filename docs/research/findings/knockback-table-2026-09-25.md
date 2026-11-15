# Where JUS sets knockback (static, 2026-09-25)

> **Superseded in part (banner only; body kept as history):** the statement that the speed cap byte (+0x3E) is 128
> in every state holds for fighter elements only. Other elements get the allocator default of 32 px/frame.
> The scoping tracker item is `jus-speed-cap-fighter-scope-uhs4`; see
> [speed-cap-128-is-fighter-scope.md](speed-cap-128-is-fighter-scope.md) and the
> [physics reference](../../confirmed-facts/physics.md).

Which bytes decide how hard and which way a hit sends the victim, read from
the game files for every battle character. No emulator was used. Capture
spec for the next live check: `jus-yusuke-air-b-knockback-capture-3htm`.

- Tool: [scripts/analysis/knockback_table.py](../../../scripts/analysis/knockback_table.py),
  test [scripts/tests/test_knockback_table.py](../../../scripts/tests/test_knockback_table.py).
- Output: [docs/rebuild/knockback-table.json](../../rebuild/knockback-table.json),
  schema [docs/rebuild/knockback-table.md](../../rebuild/knockback-table.md).
- Bytes: `jus_files/arm9/arm9.bin` (loaded at 0x02000000),
  `jus_files/overlays/ov06.bin` (0x0214CD20) and the `chr/col/<prefix>.bin`
  record files in `ChrArc.aar`, submodule pointer `f99383fd`.
- Second opinion: Codex (`gpt-5.6-sol`, read-only), prompt
  [codex-prompt.txt](knockback-table-2026-09-25/codex-prompt.txt), answer
  [codex-answer.txt](knockback-table-2026-09-25/codex-answer.txt). §8.

Grades: **measured** = read straight from bytes, or matches a live capture;
**inferred** = follows from measured pieces but is not traced end to end or
seen live; **lead** = a reading nobody has seen fire; **unknown** = not
found.

## 1. The short answer

Knockback is static. Every hit record (20 bytes in `chr/col/<prefix>.bin`)
carries it:

| byte | field | role |
|---|---|---|
| +1 | `type` | reaction type: picks the reaction, and type 6 gets the HP band |
| +8 | propMask | bits that set "zero it", "override it" and "sign by position" |
| +0xC | `kbX` (signed) | horizontal strength |
| +0xD | `kbY` (signed) | vertical strength; negative kbY means a downward kick (a spike) |

There is no angle field: the angle is just the ratio of kbX to kbY. There
is no distance term in the code (§6). Grade: measured (the load
instructions, §2), and the decode fits every joinable live launch (§5).

Yusuke's air B has a **1.54 times larger downward impulse** than
Kakashi's, which shows only on an airborne victim (§4). A standing victim
keeps only the horizontal part: the floor drops the downward part.

## 2. The code path

All addresses are arm9 unless marked ov6.

**Stage** (hit processor 0x02080F14). Grade: measured unless marked.

- 0x020817E8 `ldr r3,[r6,#0x10]` loads the hit record. r6 is the hitting
  element, r5 the victim's element, r8 the victim's M block.
  0x020817EC/F0/F4 read `type` = u8 +1, `kbX` = s8 +0xC, `kbY` = s8 +0xD.
- Band: if type is 6, `s = table[hp_frac >> 6]` (hp_frac `[r8,#0xCA]`,
  table at 0x0209FB64 through the literal at 0x02081A54, values
  0x300, 0x200, 0x180, 0x100, 0x100). Otherwise `s = 0x100`.
- `x = ASR(s × (kbX << 7), 8)`, `y = ASR(s × kbY × −158, 8)` (−158 is
  `mvn r2,#0x9D` at 0x0208181C).
- `[sp+0x18]` set doubles both. It is bit 0 of what 0x020823E4 returns. One
  path sets it when attacker +0x40 has bit 0x2000000 and an RNG test
  (0x02031070) passes; the same path doubles damage and plays sound 0x7a.
  Reading it as a critical hit is **inferred**; the full condition is
  **unknown** (the rest of 0x020823E4 was not traced).
- Type 6 only: victim gate word bit 0x80 subtracts half, then bit 0x8000
  adds half (a weight rule; which characters set these bits: **unknown**).
- Hit element +0x14 bit 0x01000000 zeroes both (0x0208186C). **Inferred**:
  never seen live.
- Hit element +0x14 bit 0x04000000 plus victim element +0x14 & 0x700
  replaces the pair with (0x300, −0x500). **Lead**: never seen live, and
  what sets the victim bits is not traced.
- Sign: if hit element +0x18 bit 4, x's sign comes from comparing the two
  elements' positions (0x0208189C–0x020818E4); otherwise from the facing
  helper 0x0206CF28.
- Store (0x02081968–0x02081978): `M+0x148 ±= x`, `M+0x14A += ASR(y × 223, 8)`.
- Spike mark: if the new `M+0x14A` > 0, victim ColPrm +0x78 gets bit
  0x80000 and +0x9E is set to 0 (0x0208197C–0x020819A0). The bit clears
  after 5 frames (0x0207F988–0x0207F9B4). While it is set, 0x020806B8
  skips a block. What that block does: **unknown** (lead).

**Element flags from the record.** The propMask at +8 goes through three
32-word tables at 0x0209FD44 (literal 0x0207D854, loop
0x0207D684–0x0207D6E8). Grade: measured (the tables).

| propMask bit | sets | effect |
|---|---|---|
| 0 | +0x14 bit 0x04000000 | the override (lead); seen on the guard-shatter down Y moves |
| 12 | +0x14 bit 0x01000000 | zero both (inferred) |
| 9 | +0x18 bit 0x4 | sign by position (fits Taikoubou up B and Kakashi air Y live) |
| 17 | +0x18 bit 0x400 | at 0x020817D0 sets victim +0x40 bit 0x40; seen on the down B moves; looks like their forced switch (lead) |
| 23 | +0x14 bit 0x100 | not traced |

**Impulse** (ov6 0x0215AF34). Grade: measured.

- 0x0215AF98–0x0215AFC4: `obj+0x10A = x × 100 / 100`,
  `obj+0x10C = y × 72 / 100`, both truncated toward zero (0x0200D12C).
- If the combo total `obj+0x10E` ≥ 600, the reaction becomes a falldown.
- The reaction entry comes from ov6 0x021721A0 by type. Types 0, 1, 2, 7
  (0x0215B6A0), 3 (0x0215B72C), 5 (0x0215B870) and 6 (0x0215BA40) add
  `obj+0x10A/+0x10C` into the victim element's impulse +0x30/+0x32. Types 4
  (0x0215B7CC), 8 (0x0215B68C) and 9–15 (0x0215B568) don't.
- Each entry then stores the per-frame handler to `obj+0xFC`
  (0x0215B70C for types 0–2 and 7). The stored words are 0x0215B720,
  0x0215B784, 0x0215B818, 0x0215B910 and 0x0215BAB8. These are the values
  physics.md read live (§7).

**Integrator** (0x02082E10). Grade: measured for the steps; the
per-victim bytes are runtime.

- `v += +0x2C/+0x2E + +0x30/+0x32` (0x02082F04–0x02082F30), then both
  impulse words are cleared (0x020830E0).
- Clamp |v| to byte +0x3E << 8 (0x02082F34–0x02082FA0). The byte is 128
  in every state (32768 raw, 128 px/frame;
  [physics.md](../../confirmed-facts/physics.md) §6.1), and the Kakashi
  air B capture reads 128 on the victim too. No table value reaches it.
- Drag `v −= floor(k × v / 256)`, k = +0x3C (32) for x, +0x3D (8) for y.
- Gravity `vy += [r3+0x2C]` (41) unless +0x34 bit 1.
- A velocity in −16..15 becomes 0 (0x020830E8–0x0208310C). No table row
  lands there.

**Floor.** On a standing victim a hit's downward part is dropped. The
Kakashi air B capture
(airB.jsonl.gz,
frames 54–67) stages (−640, +1789) on frame 54. From frame 55 the victim's
vx runs −560, −490, −428 … as the drag predicts, while vy stays 0 and y
stays 172031. Grade: measured. The cause is most likely the floor contact
in the collision pass at 0x0207ECAC–0x0207ECF4: it sets ColPrm+0x78 bit
0x2 (grounded), then zeroes element +0x26 when it is positive
(`movgt r0,#0` / `strhgt r0,[r1,#0x26]` at 0x0207ECF0/F4). Grade:
inferred (static read; the order against the integrator is taken from the
capture). The table carries both `first_frame_air` and
`first_frame_ground`.

So an airborne victim at rest ends its first frame with
`vx = X − floor(32X/256)` and `vy = Y − floor(8Y/256) + 41`. A standing
victim gets the same vx, and vy only if it is negative (else 0). Grade:
inferred (32, 8 and 41 are from measured victims, not read per character);
the standing case is measured once, on Kakashi air B.

## 3. Joining moves to records

The move table at ov6 0x021712B8 gives each move id its anim
([cancel-table.md](../../rebuild/cancel-table.md)). The fighter's `.amt`
CollisionType tracks for that anim list record ids ≥ 0x100
(`move_records.py`). The table lists them in first-key order.

- 674 of 888 move rows (ids 1–12, 74 archives) join to records.
- 214 don't: the hit comes from a spawned object (Kakashi up B, down B,
  side Y, down Y, air Y; Taikoubou side B, down B and every Y). Their
  records are listed with `refs` but not joined.
- X and up X read their anim from a per-fighter byte, so they are not
  joined either.
- The prefix map follows the audit `jus-chrb-colfile-mapping-audit-x7i2`
  (Kakashi `na_b_04`, Sasuke `na_b_02`).

2047 records total. 88 kick downward (staged y > 0; this moves only an airborne victim). 93 have the zero bit,
109 the override bit, 340 the position sign.

## 4. Yusuke's air B next to Kakashi's

Both use anim 0x26. Yusuke's is confirmed by a box-clock capture
([anim-timing.md](../../rebuild/anim-timing.md) air B row); Kakashi's is
in [kakashi.md](../../confirmed-facts/characters/kakashi.md).

| | Yusuke | Kakashi |
|---|---|---|
| record | `yh_b_01` rec 8 | `na_b_04` rec 11 |
| type | 2 | 1 |
| damage byte | 9 | 8 |
| kbX, kbY | 6, −20 | 5, −13 |
| staged (x, y) | (768, +2752) | (640, +1789), **measured** |
| impulse (X, Y) | (768, +1981) | (640, +1288) |
| px/frame | 3.0 across, **7.74 down** | 2.5 across, **5.03 down** |
| first frame, airborne victim (vx, vy) | (672, 1961) | (560, 1289) |
| first frame, standing victim (vx, vy) | (672, 0) | (560, 0), **measured** (−560, 0) |

Both types go through entry 0x0215B6A0 and handler 0x0215B720.

Yusuke's air B has a 1.54 times larger downward impulse than Kakashi's
(2.71 px/frame more down), which shows only on an airborne victim. Across,
it is 0.5 px/frame more, and that part shows on any victim. On a standing
victim both moves push only sideways (the measured Kakashi (−560, 0)).

Grades for Yusuke: his record file and the y formula are **measured** (the
gate matches eight of his special hits, §5). The air B join (anim 0x26 →
rec 8) is **inferred**: his air B never landed live (the kit capture
whiffed). The damage byte 9 answers
yusuke.md's air B TBD, also
inferred. The capture tracker item checks it on an airborne victim.

For reference: Sasuke's air B is rec 12, type 5 (a pop), staged
(−1024, +1789). Taikoubou's is horizontal only (−1408, 0).

## 5. The gate: 89 pass, 0 miss, 41 skip

`python3 scripts/analysis/knockback_table.py check` prints every case with
its source line.

What passes:

- 22 anim-join rows from the confirmed-facts tables (Kakashi, Sasuke,
  Taikoubou), one to five hits per row. Both halves must match. Facing-sign
  records match with their sign; the position-sign hits (Taikoubou up
  B, Sasuke air Y) compare size only.
- 22 record-set rows, one per joined doc row: the move's record list must be
  exactly the records its hits match. Giving every move every record fails
  22 of them; ignoring x fails 3.
- 3 pointer-traced records (Kakashi up B rec 7, down Y rec 13; Kenshin X
  rec 20 at ×1.5), from
  [knockback-record-pointer-per-hit.md](knockback-record-pointer-per-hit.md).
- 10 field-matched records (Kakashi down B and air Y, Kenshin, Jotaro, Yoh,
  Raoh, Muhyo). These were picked by matching bytes, so they only test the
  rounding, not the join.
- 8 Yusuke special hits (up X hits 1–8, X levels 1 and 2; yusuke.md §6),
  each matched to the one `yh_b_01` record keyed in its motion with the
  same staged pair, type and damage: recs 16–21 (the up X motion 0x2e and
  the shot in `yh_b_01_6` 0xab), 29 and 30 (`yh_b_01_6` 0xa5, 0xa6). Rec 23
  repeats rec 18's bytes but is keyed in 0x2a, so the motion check matters.
- Eve Y through the anim join: anim 0x1f → `bc_b_01` rec 1, (−1920, 0),
  as eve.md measured.
- 2 cases read from the Kakashi air B capture itself: the latch-frame
  staged pair (−640, +1789) and the standing victim's next-frame velocity
  (−560, 0). The air model would give (−560, 1289), so this case fails if
  the floor rule is removed.
- 4 HP-band cases: Kenshin up X at ×1.5, ×2 and ×3, and a type-5 hit that
  stays the same at ×3 (Raoh).
- 6 staged-x rows for B (Sasuke, Kenshin, Raoh, Muhyo, Yoh, Eve), 9
  rest-start rows (first vx for five of those B hits, first vy for four
  launches), all taken from the table's own rows. So a type whose entry adds
  no impulse can't pass. And the exact Kenshin recipe with pre-hit drift −123:
  (−2907, −534) and (−8507, −1687).

What skips (the reason is printed):

- 15 rows whose hit is a spawned object.
- 19 X rows.
- 4 cells that say "same".
- 3 victims already moving from earlier hits. The rest model misses these,
  and the gate shows it: Raoh up Y hit 10 predicts −534, measured −510;
  Jotaro Y finisher −439 vs −399; Yoh X finisher −246 vs −1222. The kick
  adds to the victim's velocity, so a moving victim can't be checked with a
  rest model. These are not fits.

Not joinable, and not in the gate: Muhyo Y measured (0, 0), but anim 0x1f
has no record, so the table can't say.

**Mutations** (each break made the gate go red, then was undone):

| break | result |
|---|---|
| −158 → −157 | 45 MISS |
| ×72 → ×73 | 6 MISS |
| force the facing sign | 3 MISS |
| floor → truncate on ×223 | 36 MISS |
| band on every type | 1 MISS (Raoh at ×3) |
| give every joined move every record | 22 MISS (record set) |
| `match()` ignores x | 3 MISS (record set) |
| drop the floor rule | 1 MISS (the capture case) |
| type 1's entry adds no impulse | 6 MISS |
| the `obj+0xFC` store match | the installs unit test fails |

## 6. Distance

[physics.md](../../confirmed-facts/physics.md) §4.4 reports a ~20% launch
gap that follows attacker–victim distance. The staging code has no distance
term: position only picks x's sign, and only for records with the position
bit. The HP band can't explain the gap either: physics.md §4.4 says the two
matches had the same health at each hit. One reading fits: Kenshin X is
multi-hit, the kick adds to whatever velocity the victim already has, and
the distance at the last hit reflects how the earlier hits moved the
victim. Grade: inferred. The cause of the 22% gap is otherwise unknown.

## 7. Conflicts with other docs (left unedited)

- **physics.md §4.6 (the "stages not yet seen live" bullet) swaps the two
  sides.** It says the zero bit is on the victim's `+0x14`, and the
  override needs victim bit 0x04000000 plus attacker `& 0x700`. The code
  reads both bits from r6, the element holding the hit record (the hitter),
  and `& 0x700` from r5, the victim's element. Grade: inferred (r6 is the
  hitter because it holds the record).
- **physics.md "Handler pointer values, settled 2026-09-03"** says not to
  cite 0x0215B6A0 / 0x0215B870 / 0x0215BA40 as the table's values. They are
  the table's values; they are one-shot entry routines. Each one stores the
  live value (0x0215B720 / 0x0215B910 / 0x0215BAB8) to `obj+0xFC` before it
  returns. Reaction 4's entry stores 0x0215B818, which physics.md also read
  live. Both readings are right. Grade: measured (the stores).
- physics.md §4.4 distance: see §6.

## 8. Second opinion (Codex)

The prompt gave the disassembly and asked eight neutral questions, with
three test records (A = Kakashi rec 11, B = Yusuke rec 8, C = kbX 25,
kbY 6, type 6).

It agrees on:

- the staging formula, step order, rounding (all floors), and the spike
  mark;
- A → (+640, +1789), B → (+768, +2752), C → (+3200, −826) at full HP and
  (+4800, −1239) at hp_frac 0xA8, the same as the table;
- `[sp+0x18]` = bit 0 of 0x020823E4's result, and the visible path that
  sets it;
- propMask bits 0, 12 and 9 and the bit-23 side effect;
- ×100/100 and ×72/100 truncating toward zero; the entry table for types
  0–11; the four entries that add the impulse;
- the integrator order, and the first-frame vy values −534, −1206, +1961
  and +1289.

It adds or differs:

- The position-sign branch needs a position compare, not just the listed
  fields. The table already models it only as `relative`, and compares
  magnitudes for it.
- It could not decide the full crit condition or what 0x0215B568 does past
  its first lines. The prompt didn't include those parts. This note calls
  crit inferred and 0x0215B568 "no impulse" from a scan to its return.
- The integrator also adds +0x2C/+0x2E and has a −16..15 dead zone. Both
  are checked in §2: the extra word is cleared each frame, and no table
  row lands in the dead zone.

No point where Codex's numbers differ from the table.

## 9. Still open

- The override trigger (who sets victim +0x14 & 0x700).
- The crit condition in full (0x020823E4 past 0x0208247C).
- What reads the spike mark (the block at 0x020806B8).
- Which spawned objects carry which records (214 move rows).
- The X and up X anims.
- Where exactly the floor rule runs against the integrator (the capture
  settles the result, not the code order).

**RAM needed?** Only for the capture tracker item. Nothing in the
table needs RAM. The save-state reader being built elsewhere could read
the latch frame instead of a live run.
