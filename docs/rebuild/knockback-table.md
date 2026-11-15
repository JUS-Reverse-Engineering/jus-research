# Knockback table: how hard and which way each hit sends the victim

For every JUS battle character (74 archives `chr/xx_b_NN.aar`), this lists
every hit record's knockback bytes and the velocity they give the victim,
and joins them to move ids 1-12. It is static: read from the game files, no
emulator. Capture spec for the next check:
`jus-yusuke-air-b-knockback-capture-3htm`.

- The machine-readable copy is [knockback-table.json](knockback-table.json).
  Use the JSON for machine-readable data.
- One tool writes and checks it:
  [scripts/analysis/knockback_table.py](../../scripts/analysis/knockback_table.py).
  The disassembly behind it, the fits and misses, and the grades:
  [knockback-table-2026-09-25.md](../research/findings/knockback-table-2026-09-25.md).

## 1. Run it

```bash
python3 scripts/analysis/knockback_table.py check    # the gate: exit 0 pass, 1 fail
python3 scripts/analysis/knockback_table.py build    # rewrite knockback-table.json
python3 scripts/analysis/knockback_table.py show yh_b_01
python3 -m unittest scripts/tests/test_knockback_table.py
```

`check` needs the `jus_files` submodule (`git submodule update --init`).
It prints one PASS, MISS or SKIP line per case and fails if any case
misses or the committed JSON differs from a fresh build. The exit code is
the answer. The unittest runs the same gate and fails, not skips, without
`jus_files`.

The gate's cases:

- every row with a `kb raw (x,y)` column in the confirmed-facts character
  tables for Kakashi, Sasuke and Taikoubou: each measured hit must match a
  record in the move's anim, and (`record set`) the move's record list must
  be exactly the records its hits match;
- fixed cases from [physics.md](../confirmed-facts/physics.md) and
  runtime-report-7:
  Kenshin's X and up X (the HP band), Jotaro, Yoh, Raoh, Muhyo, Eve, and
  first-frame velocities of victims hit from rest (through the entry
  table, so a type that adds no impulse can't pass);
- the committed Kakashi air B capture
  (airB.jsonl.gz),
  read directly: the latch-frame staged pair and the next frame's velocity
  on a standing victim;
- eight Yusuke special hits from yusuke.md (up X
  hits 1-8, X levels 1 and 2), each matched to the one record keyed in its
  motion with the same staged pair, type and damage.

A SKIP is a case the table cannot join: the hit comes from a spawned
object, the move is an X, the cell says "same", or the victim was already
moving from earlier hits. Every SKIP prints its reason.

## 2. The rule

For one hit with record bytes `type` (+1), `kbX` (+0xC, signed) and `kbY`
(+0xD, signed), at full HP, no crit, neutral weight:

- **Staged pair** (victim `M+0x148` x, `M+0x14A` y; y < 0 is up):
  `x = kbX × 128`, `y = floor(floor(kbY × −158) × 223 / 256)`.
  Type 6 (launcher) first multiplies both by the HP band:
  x1 at full HP, then x1.5, x2, x3 as HP falls. Grade: measured.
- **Impulse** (what the reaction adds to the victim's velocity):
  `X = x`, `Y = trunc(y × 72 / 100)`. Only reaction types 0-3 and 5-7 add
  it; types 4 and 8-15 don't (`impulse` is null). Grade: measured on the
  rest-start cases.
- **px per frame**: impulse / 256.
- **First frame from rest, in the air**: `vx = X − floor(32X/256)`,
  `vy = Y − floor(8Y/256) + 41`. Grade: inferred (drag and gravity are
  runtime fields, taken from measured victims).
- **First frame from rest, standing**: the same, but a downward vy becomes
  0. The floor contact (arm9 0x0207ECE4–0x0207ECF4) zeroes a positive
  +0x26. Grade: measured on Kakashi air B (−560, 0); the cause is inferred.
- **Sign**: usually the attacker's facing (positive kbX pushes away). A
  record with propMask bit 9 takes the sign from which side the hitting
  element is on instead.
- **Spike**: a positive staged y. It moves only an airborne victim down;
  a standing victim keeps only the horizontal part. The game marks the
  victim for 5 frames (ColPrm+0x78 bit 0x80000). What reads that mark is
  not known.

## 3. JSON layout

Top level:

| key | what |
|---|---|
| `grade_notes` | what each grade means, field by field |
| `code_facts` | the code readings the rule rests on, decoded from arm9.bin and ov06.bin each build (the test pins them) |
| `move_table` | move ids 1-12: `id`, `move`, `anim` (from the shared ov6 table at 0x021712B8) |
| `characters[]` | one entry per battle archive, sorted by prefix |

`code_facts`: `record_offsets`, `kbx_shift` (7), `kby_scale` (−158),
`y_scale` (223), `band_table_addr`/`band_table`, `ov6_x_scale`/`ov6_y_scale`
(multiply, divide), `flag_tables_addr`, `zero_bits`, `override_bits`,
`relative_sign_bits` (propMask bits), `entry_table_addr`, `entry` (per
reaction type: the entry routine and whether it adds the impulse), and
`installs` (per type: the per-frame handler the entry stores to
`obj+0xFC`; these are the values physics.md read live).

Each `characters[]` entry: `prefix`, `names` (chr_b mapping rows for this
prefix: `chr_b`, `name`, `basis`), `moves[]`, `records[]`.

Each `moves[]` row: `id`, `move`, `anim`, `records` (record indexes in the
anim's CollisionType tracks, in the order their first key appears, which
is not hit order: Kakashi Y lists [1, 3, 2] and lands 1, 2, 3), `reason` (why `records`
is empty, or null).

Each `records[]` row (one line in the file):

| field | what | grade |
|---|---|---|
| `rec`, `id` | index in `chr/col/<prefix>.bin` and the hit id (index + 0x100) | measured |
| `kind`, `type` | bytes +0 and +1; `type` is the reaction type | measured |
| `status_raw` | byte +3 (signed), present only when nonzero: a signed lane value, stored raw to the struck fighter's work byte `+0x172` if positive or `+0x173` if negative (arm9 `ldrsb` at 0x0208169C; ov6 0x02158B34 negates the `+0x173` lane when it reads it; `jus-chrcol-03-status-lanes-4exo`). Formerly "arbTag" | measured byte |
| `damage`, `hitstun_add` | byte +4 (signed); byte +7 (signed, added to `M+0x171` at arm9 0x02081300, per move_records.py) | measured bytes |
| `kbX`, `kbY` | bytes +0xC and +0xD, signed | measured |
| `mask` | propMask, word +8, hex | measured |
| `zero` | propMask sets the "zero both" flag | inferred |
| `override` | propMask sets the (0x300, −0x500) override flag | lead |
| `sign` | `facing` or `relative` | inferred |
| `staged` | [x, y] at full HP | `grade_notes.staged` |
| `impulse` | [X, Y], or null | `grade_notes.impulse` |
| `px` | impulse / 256 | as `impulse` |
| `first_frame_air` | [vx, vy] one frame after a hit from rest, victim in the air | inferred |
| `first_frame_ground` | the same for a standing victim (downward vy → 0) | measured on Kakashi air B |
| `band` | type 6 only: `x1`, `x1.5`, `x2`, `x3` staged pairs | measured on Kenshin |
| `refs` | where the record is used: `member anim [node]` | measured |

## 4. Limits

- Moves whose hit comes from a spawned object (214 of 888 move rows, for
  example Kakashi up B and all of Taikoubou's Y moves) have no record in
  the fighter's anim. Their records are in `records[]` but not joined to a
  move.
- X and up X are not in the move table; their records are listed but not
  joined.
- The anim is the one the move table hands over. A handler can play a
  different one (Yusuke side Y plays 0x28), so that row can be wrong.
- The staged pair assumes full HP, no crit and neutral weight bits. Crit
  doubles both; the weight bits halve or add half on type 6 only.
- The first-frame numbers assume a victim at rest. A victim already moving
  keeps its velocity, and the kick adds to it.
- A downward kick (positive y) shows only on an airborne victim. On a
  standing one the floor drops it, so compare spikes with
  `first_frame_air` and grounded hits with `first_frame_ground`.
- The speed cap is element byte +0x3E = 128 in every state (32768 raw,
  [physics.md](../confirmed-facts/physics.md) §6.1; the Kakashi air B
  capture reads 128 too). No table value reaches it. Fighters only; other elements
  default to 32 px/frame (`jus-speed-cap-fighter-scope-uhs4`).
