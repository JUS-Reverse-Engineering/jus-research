# Finding: node `+0x18` bit 0 predicts a record's teardown at contact, across 12 owner states

Runtime. Tracker item `jus-2s9k`. Follow-up `jus-b9sb`. Answers `jus-jv9d` in the negative for `+0x38`.
Parent `jus-hitbox-priority-clash-1evz`.

## 1. Result

Across the 12 owner pause-menu states and the 22 in-use non-fighter ColPrm records in
`docs/research/feel-captures/projectile-census-2026-09-10/SUMMARY.md` (the "in-use non-fighter
records" table), the record's `+0x40` word gained bit `0x200` on the contact frame (or the frame
after) for 10 records; 6 records instead showed a transient `0x8 -> 0x9 -> 0x8` at contact and
stayed in use for at least 10 more frames; and 6 were freed without another record's teardown
landing on the same frame in this dataset (3 of those 6 land within a ±2-frame window of another
teardown in the same state).

Every one of the 10 records that were freed at contact has at least one node on its `+0x08` list
with `+0x18` bit 0 set. Every one of the 6 records that survived the contact transient has that
bit clear on every node it has, or has no nodes at all. This split is exact — 16 of 22 records
carry a set bit and land in the two "freed" groups; the other 6 carry a clear bit (or no node) and
are exactly the "survived" group.

No other dumped field in the census table separates the two groups this cleanly:

- ObjShot kind `0x07` is one of the survivor group five times (`pc-yugi-fb-npc-vegeta-fy` idx 21,
  `pc-yugi-fb-npc-vegeta-x` idx 99, `pc-taikoubou-upx-npc-kakashi-x` idx 62,
  `pc-mashirito-fy-momotaro-x` idx 121, `pc-mashirito-fy-npc-momotaro-b` idx 99) but is also freed
  once (`pc-mashirito-y-npx-yusuke-fy` idx 16).
- `+0x3C` bit `0x800` splits the 5 distinct `+0x3C` values 5 ways among the freed rows and does
  not line up with the survive/freed split by itself.
- `+0x34`'s low nibble is `1` on one side of a state's pairing and `2` on the other (a
  left/right-side tag), not a survive/freed tag.
- `+0x38` reads `0x00000000` on all 22 rows (this is the finding `+0x38` was checked to close;
  see §6).
- `+0x150` reads `0x00000000` on all 22 rows.
- `+0x174` does not separate the groups: it is `0x00001500`/`0x00002900` on some freed rows and
  some survivor rows alike, and `0x00000000` on others of both kinds.

This is a correlation read off 16 classified records in one census, not a traced rule: nothing
here re-derives what sets bit `0x200`, or what the node bit itself does downstream. The node
bit's writer is already traced statically — the record allocator's built-in-table/character-array
lookup at `0x0207D440` resolves a hitbox id to a 20-byte collision entry, then OR's table
`T18@0x0209FDC4[b]` into node `+0x18` for every set bit `b` of that entry's own `+0x08` property
word, and bit 5 of that word is the only bit that contributes node `+0x18` bit 0 for an authored
per-character entry
(`docs/research/findings/node-0x18-is-seeded-from-the-collision-entry-property-word.md` §3-4).
This document only adds that the resulting bit, read live, lines up with which records got torn
down at contact and which did not, in this one census.

## 2. Conditions and positive control

- Date: 2026-09-10 for the batch this table cites; a same-day evening rerun regenerated all 12
  directories with fixed tooling (commit `717350a`) and produced no differences from the prior
  batch (SUMMARY.md, "Differences from the 9e92bc9 batch").
- Emulator build: `fork_commit c26edf0e0d75364823856c9272a103fe39e03999`, built
  `2026-09-01T19:26:00Z`, `app_path <SRC>/melonDS-lua/build/melonDS.app/Contents/MacOS/melonDS`
  (`scripts/emu/build_info.json`).
- JIT off (`[JIT] Enable=false`, repo default).
- Holder label `replay12-run1`: all twelve states regenerated in one continuous emulator session,
  no relaunches, `scripts/emu/emu_health.py` reporting an advancing framecount before every load.
- Owner testimony and per-state framing come from
  `docs/research/moveset-notes/OWNER-NOTES.md`, "Owner projectile-interaction save states
  (2026-09-10)", and the state descriptions in `jus_files/save_states/INDEX.md`.
- Run plan: START on relative frames 0-2, no input through frame 149, START on frames 150-152;
  170 emulator frames tailed per state with `gaps=0 dropped=0` on every state's `RESULTS.md`
  ("Gaps/dropped (per bridge tail_stop ack)"), i.e. zero gaps, Refuter-recomputed.
- Every frame in the tail window was watched; the watch spec held to a 512-byte, 32-watch budget
  per state, with the windowed ranks described in each state's `watch_spec.notes.md`. `tail.jsonl`
  is present locally but uncommitted for every state, per precedent; sizes are recorded in each
  state's own `RESULTS.md` (e.g. `pc-hitsugaya-airy-npc-ichigo-fy`: 127732 bytes).
- Positive control: `control` reproduces the published capture from
  `docs/research/findings/momotaro-yusuke-projectile-conflict.md` — record `0x02214D64` (record
  index 70 in this census's addressing) went `0x8 -> 0x209 -> 0x200` at frames 13085/13086 while
  its element's x position moved 699.22 -> 692.38 -> 0, matching that document's per-frame
  evidence table exactly.
- The two states with zero ObjShot elements active at baseline census
  (`pc-ichigo-charged-fy-vegeta`, `pc-vegeta-x-ichigo-x`) report no element motion for the
  duration of the tail and contribute no rows to the index->=13 table — their only rows are in
  the records 0-12 table (fighter/sub-records, not in scope for this finding).
- Classification: Refuter-recomputed from the raw tails (round-two review, 2026-09-10), not
  inferred.

## 3. Evidence table

Values below are copied from `SUMMARY.md`'s "in-use non-fighter records" table; obj/node lists are
rendered exactly as in each state's census `.md`. Class: **A** = the record's `+0x40` gained bit
`0x200` on the same frame or the frame after ANY other watched record's `+0x40` — including
fighters' records 0-12 — first gained bit `0x1` or `0x200`; **B** = a non-`0x200` transient then
in use `>=10` more frames; **C** = freed but no partner frame matched under ±1 (marked
`C (A under ±2)` where a ±2-frame window turns up a match instead). Because the A rule counts
fighter records as partners, class A means "freed on a frame when some watched record registered
contact," not "freed by a projectile" — `pc-ichigo-fy-vegeta` idx 115 has no other live projectile
to pair against and still classifies A, because fighter record 12 gained `+0x40` bit `0x1`
(`0x19`) on the same frame, 64704, that idx 115's `+0x40` first left `0x8`.

| state | idx | class | node `+0x18` | `+0x3C` | kind | `+0x174` | `+0x34` | `+0x40` sequence (frames) | owner testimony |
|---|---:|:---:|---|---|---|---|---|---|---|
| `pc-hitsugaya-airy-npc-ichigo-fy` | 19 | B | - (no nodes) | `0x0063C811` | `0x00` | `0x00001500` | `0x00001001` | 53493: `0x8->0x9`; 53494: `0x9->0x8`; 53543: `0x8->0x200` | "Hitsugaya air Y ice chunk in the air; Ichigo uncharged fwd Y about to contact it." |
| `pc-hitsugaya-airy-npc-ichigo-fy` | 20 | A | `0x00000001` | `0x0063C822` | `0x00` | `0x00000000` | `0x00001002` | 53493: `0x8->0x209`; 53494: `0x209->0x200` | "Hitsugaya air Y ice chunk in the air; Ichigo uncharged fwd Y about to contact it." |
| `pc-ichigo-fy-vegeta` | 115 | A | `0x00000001` | `0x0063C811` | `0x00` | `0x00000000` | `0x00001001` | 64704: `0x8->0x209`; 64705: `0x209->0x200` | "Ichigo uncharged fwd Y in flight, no projectile collision (single-projectile control)." |
| `pc-momotaro-npc-yusuke-projectiles-about-to-collide` | 70 | A | `0x00000001` | `0x0063C822` | `0x00` | `0x00000000` | `0x00001002` | 13085: `0x8->0x209`; 13086: `0x209->0x200` | "Momotaro fwd+Y projectile and Yusuke fwd+Y projectile about to collide, paused right before they meet. Owner testimony: Momotaro's wins every time." |
| `pc-yugi-fb-npc-vegeta-fy` | 21 | B | `0x00000000`, `0x00000004` | `0x0063C011` | `0x07` | `0x00001500` | `0x00001001` | 31530: `0x8->0x9`; 31531: `0x9->0x8`; 31578: `0x8->0x100009`; 31579: `0x100009->0x9`; 31586: `0x9->0x200` | "Yugi fwd B dice thrown down-right vs Vegeta fwd Y. The dice are \"high priority\", persist for their whole animation, go through beams." |
| `pc-yugi-fb-npc-vegeta-fy` | 23 | A | `0x00000001` | `0x0063C822` | `0x00` | `0x00000000` | `0x00001002` | 31530: `0x8->0x209`; 31531: `0x209->0x200` | "Yugi fwd B dice thrown down-right vs Vegeta fwd Y. The dice are \"high priority\", persist for their whole animation, go through beams." |
| `pc-yugi-fb-npc-vegeta-x` | 99 | B | `0x00000000`, `0x00000004` | `0x0063C011` | `0x07` | `0x00001500` | `0x00001001` | six `0x9<->0x8` flips 59451-59470; 59511: `0x8->0x200` | "Yugi dice on the left, Vegeta X beam from the right. The beam hits the dice, the dice keep moving; the beam hits Yugi; the dice keep \"contacting\" the beam." |
| `pc-yugi-fb-npc-vegeta-x` | 106 | A | `0x00000041` | `0x0063C022` | - | `0x00000000` | `0x00001002` | 59453: `0x9->0x40209`; 59454: `0x40209->0x200` | "Yugi dice on the left, Vegeta X beam from the right. The beam hits the dice, the dice keep moving; the beam hits Yugi; the dice keep \"contacting\" the beam." |
| `pc-yugi-fb-npc-vegeta-x` | 107 | A | `0x00000041` | `0x0063C022` | - | `0x00000000` | `0x00001002` | 59455: `0x9->0x209`; 59456: `0x209->0x40309`; 59457: `0x40309->0x200` | "Yugi dice on the left, Vegeta X beam from the right. The beam hits the dice, the dice keep moving; the beam hits Yugi; the dice keep \"contacting\" the beam." |
| `pc-yugi-fb-npc-vegeta-x` | 110 | C (A under ±2) | `0x00000041` | `0x0063C022` | - | `0x00000000` | `0x00001002` | 59457: `0x9->0x209`; 59458: `0x209->0x309`; 59459: `0x309->0x200` | "Yugi dice on the left, Vegeta X beam from the right. The beam hits the dice, the dice keep moving; the beam hits Yugi; the dice keep \"contacting\" the beam." |
| `pc-yugi-fb-npc-vegeta-x` | 111 | C (A under ±2) | `0x00000041` | `0x0063C022` | - | `0x00000000` | `0x00001002` | 59453: `0x8->0x9`; 59459: `0x9->0x209`; 59460: `0x209->0x309`; 59461: `0x309->0x200` | "Yugi dice on the left, Vegeta X beam from the right. The beam hits the dice, the dice keep moving; the beam hits Yugi; the dice keep \"contacting\" the beam." |
| `pc-yugi-fb-npc-vegeta-x` | 112 | C | `0x00000041` | `0x0063C022` | - | `0x00000000` | `0x00001002` | 59455: `0x8->0x9`; 59461: `0x9->0x209`; 59462: `0x209->0x200` | "Yugi dice on the left, Vegeta X beam from the right. The beam hits the dice, the dice keep moving; the beam hits Yugi; the dice keep \"contacting\" the beam." |
| `pc-eve-x-npc-vegeta-x` | 112 | C | `0x00000081` | `0x0063C811` | `0x00` | `0x00001500` | `0x00001001` | 90702: `0x8->0x209`; 90703: `0x209->0x200` | "Eve X feathers aimed left; Vegeta X beam right. The beam eats the feathers then hits Eve." |
| `pc-taikoubou-upx-npc-kakashi-x` | 50 | C | `0x00000041` | `0x0063C022` | - | `0x00001500` | `0x00001002` | 67078: `0x8->0x200` | "Taikoubou (right) up X tornado; Kakashi (left) X beam. The beam stops on the tornado wherever it is as it travels left." |
| `pc-taikoubou-upx-npc-kakashi-x` | 62 | B | `0x00000000`, `0x00000080`, `0x00000080` | `0x0063C011` | `0x07` | `0x00001500` | `0x00001001` | thirteen `0x9<->0x8` flips 67053-67077; 67118: `0x8->0x200` | "Taikoubou (right) up X tornado; Kakashi (left) X beam. The beam stops on the tornado wherever it is as it travels left." |
| `pc-taikoubou-upx-npc-kakashi-x` | 63 | A | `0x00000041` | `0x0063C022` | - | `0x00001500` | `0x00001002` | 67055: `0x8->0x209`; 67056: `0x209->0x200` | "Taikoubou (right) up X tornado; Kakashi (left) X beam. The beam stops on the tornado wherever it is as it travels left." |
| `pc-taikoubou-upx-npc-kakashi-x` | 64 | A | `0x00000041` | `0x0063C022` | - | `0x00001500` | `0x00001002` | 67057: `0x8->0x9`; 67059: `0x9->0x209`; 67060: `0x209->0x200` | "Taikoubou (right) up X tornado; Kakashi (left) X beam. The beam stops on the tornado wherever it is as it travels left." |
| `pc-taikoubou-upx-npc-kakashi-x` | 65 | C (A under ±2) | `0x00000041` | `0x0063C022` | - | `0x00001500` | `0x00001002` | 67059: `0x8->0x209`; 67060: `0x209->0x200` | "Taikoubou (right) up X tornado; Kakashi (left) X beam. The beam stops on the tornado wherever it is as it travels left." |
| `pc-mashirito-y-npx-yusuke-fy` | 16 | A | `0x00000000`, `0x00000005` | `0x0063C011` | `0x07` | `0x00002900` | `0x00001001` | 91244: `0x8->0x209`; 91245: `0x209->0x200` | "Mashirito Y chest (explodes on contact) vs Yusuke fwd Y. The chest and its explosion seem to be classified differently." |
| `pc-mashirito-y-npx-yusuke-fy` | 17 | A | `0x00000001` | `0x0063C822` | `0x00` | `0x00000000` | `0x00001002` | 91244: `0x8->0x209`; 91245: `0x209->0x200` | "Mashirito Y chest (explodes on contact) vs Yusuke fwd Y. The chest and its explosion seem to be classified differently." |
| `pc-mashirito-fy-momotaro-x` | 121 | B | `0x00000000`, `0x00000000` | `0x0063C011` | `0x07` | `0x00002900` | `0x00001001` | five `0x9<->0x8` flips 114157-114187; 114187: `0x9->0x200` | "Mashirito fwd Y walking poop (traveling left) hit by Momotaro X. The poop persists, is never canceled, and explodes at the end of its travel." |
| `pc-mashirito-fy-npc-momotaro-b` | 99 | B | `0x00000000`, `0x00000000` | `0x0063C011` | `0x07` | `0x00002900` | `0x00001001` | repeated `0x9<->0x100009` flips 121428-121508; 121517: `0x9->0x200` | "Momotaro B melee hitting the walking poop. Melee attacks also have priority-like outcomes (one side loses and takes damage, or hitboxes cancel and nobody is hurt)." |

Class counts: A = 10, B = 6, C = 6 (3 of the 6 flip to A under a ±2-frame window: idx 65 in
`pc-taikoubou-upx-npc-kakashi-x`, and idx 110/111 in `pc-yugi-fb-npc-vegeta-x`, each marked
`C (A under ±2)` above). Node `+0x18` bit 0: set on every A and C row, clear (or absent) on every
B row — matching the split reported in §1.

## 4. Observations

- (a) `pc-ichigo-fy-vegeta` idx 115 is a single-projectile control with no other live projectile
  record to pair against, yet it classifies **A**: fighter record 12 gained `+0x40` bit `0x1`
  (`0x19`) at frame 64704, the same frame idx 115's `+0x40` first left `0x8` on its way to
  `0x209 -> 0x200`. Because the A rule counts fighter records as partners, this is class A meaning
  "freed on a frame when some watched record registered contact," not "freed by a projectile."
  Idx 20 in `pc-hitsugaya-airy-npc-ichigo-fy` is also class **A**, and for a more direct reason:
  its `+0x40` reached `0x209` at frame 53493, the same frame idx 19's `+0x40` first gained bit
  `0x1` (`0x8 -> 0x9`).
- (b) The kind-`0x07` records each carry 2-3 nodes and a `+0x174` of `0x00001500` or
  `0x00002900`; every kind-`0x07` row in this census is a survivor (class B) except
  `pc-mashirito-y-npx-yusuke-fy` idx 16, which was freed in the same frame as its paired idx 17.
- (c) The records with no ObjShot link at baseline and node `+0x18 = 0x00000041` — idx 106, 107,
  110, 111, 112 in `pc-yugi-fb-npc-vegeta-x`, and idx 50, 63, 64, 65 in
  `pc-taikoubou-upx-npc-kakashi-x` — were torn down one after another, one to a few frames apart,
  over the same span in which the kind-`0x07` record on the other side of that same state (idx 99
  and idx 62 respectively) showed its own repeated `0x8 -> 0x9 -> 0x8` transient.
- (d) In `pc-hitsugaya-airy-npc-ichigo-fy`, idx 19 has no nodes at all and survived the contact
  transient (class B), while idx 20 — one node, bit 0 set — had its `+0x40` first change at the
  same frame, 53493, and was fully freed one frame later.
- (e) `pc-mashirito-y-npx-yusuke-fy` idx 16 and idx 17 were both freed on the same frame, 91245 —
  the only exact-frame match between two strictly class-A rows in this census.
  `pc-taikoubou-upx-npc-kakashi-x` idx 64 (class A) and idx 65 (class C, flipping to A only under
  the ±2-frame window) also cleared at the identical frame, 67060; idx 63 (class A) cleared
  earlier, at frame 67056.
- (f) In the records 0-12 table (fighter/sub-records, not part of the 22 rows above), several
  states show `+0x40` transients on the same contact frames as the table above, using patterns
  `0x8 -> 0x400019 -> 0x8`, `0x8 -> 0x200008 -> 0x8`, `0x8 -> 0x1009 -> 0x9 -> 0x8`, and
  `0x8 -> 0x100009 -> 0x8` (`SUMMARY.md`, "Records 0-12: observed +0x40 transitions"). These are
  listed here by pattern only, without naming which state or record index carried each one.
- (g) The `+0x134` fold window and the `+0xA4` accumulator window, in every state and record where
  either was watched, read "never" for first-nonzero across the whole 170-frame tail (`SUMMARY.md`
  main table, "fold +0x134 first-nonzero frame" and "+0xA4 first-nonzero frame" columns, all
  "never").

## 5. What this does not show

- What node `+0x18` bit 0 means in gameplay terms, or what `entry+0x08` bit 5 means on the
  authored collision entry that sets it.
- ~~Which collision entry id each live record in this census actually resolved to at runtime~~
  Resolved 2026-09-11 under tracker item `jus-b9sb`: see the section "Authored source confirmed at read
  time" below and the live allocator probe under
  gdb-alloc-2026-09-11/RESULTS.md.
- Whether the 6 class-C records had a partner record outside this run's watch set — the watch
  spec was capped at 32 watches / 512 bytes per state, and several states' notes record windows
  skipped for that cap (`SUMMARY.md`, "Windows skipped for budget").
- Anything about the objects in the two states with zero ObjShot elements active at baseline
  (`pc-ichigo-charged-fy-vegeta`, `pc-vegeta-x-ichigo-x`) — those objects were not linked to
  ObjShot at baseline and contribute no idx->=13 rows here.
- Any HP or knockback effect of these teardowns — fighter HP was not watched in this campaign.

## 6. Tracker items

- `jus-2s9k` — this campaign.
- `jus-b9sb` — follow-up: which collision entry id each live record resolves to.
- `jus-jv9d` — the `+0x38` question; answered negative here and in
  `docs/research/findings/node-0x18-is-seeded-from-the-collision-entry-property-word.md` (`+0x38`
  reads 0 on all 22 in-use records, so it cannot be the live source of node `+0x18` bit 0).
- `jus-hitbox-priority-clash-1evz` — parent.

## 7. Authored source confirmed at read time (2026-09-11)

`docs/research/feel-captures/projectile-census-2026-09-10/ENTRIES.md` resolved, at the pause
point in each of the 12 census states, the collision entry pointer each node's `+0x10` actually
points at (`[[record+0x6C]+0x0C] + 0x14*(id-0x100)`), read `entry+0x08` from it, and compared bit
5 of that word against the observed node `+0x18` bit 0. Every in-use non-fighter record's node
(28 nodes total) resolved to an authored entry; none fell back to the built-in table.

| state | rec idx | class | id | entry+0x08 | predicted | observed |
|---|---|---|---|---|---|---|
| control | 70 | A | 287 | 0x20 | 1 | 1 |
| pc-hitsugaya-airy-npc-ichigo-fy | 19 | B | (no nodes) | - | - | - |
| pc-hitsugaya-airy-npc-ichigo-fy | 20 | A | 264 | 0x20 | 1 | 1 |
| pc-ichigo-fy-vegeta | 115 | A | 264 | 0x20 | 1 | 1 |
| pc-yugi-fb-npc-vegeta-fy | 21 | B | 273 / 258 | 0x0C / 0x200 | 0 / 0 | 0 / 0 |
| pc-yugi-fb-npc-vegeta-fy | 23 | A | 261 | 0x20 | 1 | 1 |
| pc-yugi-fb-npc-vegeta-x | 99 | B | 273 / 258 | 0x0C / 0x200 | 0 / 0 | 0 / 0 |
| pc-yugi-fb-npc-vegeta-x | 106,107 | A | 269 | 0x420 | 1 | 1 |
| pc-yugi-fb-npc-vegeta-x | 110,111,112 | C | 269 | 0x420 | 1 | 1 |
| pc-eve-x-npc-vegeta-x | 112 | C | 271 | 0x820 | 1 | 1 |
| pc-taikoubou-upx-npc-kakashi-x | 50 | C | 275 | 0x420 | 1 | 1 |
| pc-taikoubou-upx-npc-kakashi-x | 62 | B | 277 / 270 / 271 | 0x0C / 0x800 / 0x800 | 0 / 0 / 0 | 0 / 0 / 0 |
| pc-taikoubou-upx-npc-kakashi-x | 63,64 | A | 275 | 0x420 | 1 | 1 |
| pc-taikoubou-upx-npc-kakashi-x | 65 | C | 275 | 0x420 | 1 | 1 |
| pc-mashirito-y-npx-yusuke-fy | 16 | A | 287 / 257 | 0x0C / 0x220 | 0 / 1 | 0 / 1 |
| pc-mashirito-y-npx-yusuke-fy | 17 | A | 287 | 0x20 | 1 | 1 |
| pc-mashirito-fy-momotaro-x | 121 | B | 287 / 259 | 0x0C / 0x00 | 0 / 0 | 0 / 0 |
| pc-mashirito-fy-npc-momotaro-b | 99 | B | 287 / 259 | 0x0C / 0x00 | 0 / 0 | 0 / 0 |

Totals: 28 nodes matched (entry+0x08 bit 5 or builtin-id-4 rule agreed with node +0x18 bit 0), 0
mismatched, 0 unknown (entry pointer did not resolve to either the builtin table or the record's
authored table); all resolved ids were authored (no builtin ids appeared in this dataset).

**Conditions** (copied from `ENTRIES.md`):

- Date: 2026-09-11
- Emulator build: `fork_commit c26edf0e0d75364823856c9272a103fe39e03999` (`scripts/emu/build_info.json`)
- Holder label: `b9sb-entries-<pid>` (`JUS_EMU_HOLDER` per `scripts/emu/launch_emu.sh`)
- States loaded via standalone `jusemu.py state load <slot>` against dummy sidecars under
  `/tmp/jus_emu/states/` (ack `ok:false`, "did not settle" — expected for these sidecars, verified
  instead by root pointer and heartbeat per `projectile_census.py`'s self-validation)
- Paused at the save point each state was captured at; no frames were advanced before reading
- Tool: `scripts/emu/projectile_census.py --no-load --state <slot>.entries --out <dir>`, one run
  per state, no `--trust-addr`

**Tool caveats** (from the Refuter that checked this pass): `AUTHORED_TABLE_MAX_COUNT = 0x400` in
the census tool is an invented bound — the real authored-entry count lives at `[record+0x6C]` and
was not cross-checked against it here; and the tool reads `+0x0E` as a u16, so that field spans
the documented one-byte `+0x0E` property and the following byte at `+0x0F`.

This confirms the entry is read from the authored table at the moment the node is examined. The
allocator write itself was then observed live the same day: one GDB attach with breakpoints at
`0x0207D4A8` (id read), `0x0207D4D8` / `0x0207D580` (after the entry-pointer stores) and
`0x0207D834` (function return) on `pc-mashirito-fy-npc-momotaro-b` and
`pc-mashirito-y-npx-yusuke-fy` logged 24 allocations: 21 authored-path rows, all with
node `+0x18` bit 0 equal to `(entry +0x08 >> 5) & 1`, and one row with `entry +0x08 = 0xE0`
producing node `+0x18 = 0x19` (`T18[5]|T18[6]|T18[7]`, seed 0). The 3 built-in rows (ids 0, 2)
logged node `+0x18` of `0x800`, `0x0`, `0x800`, which the seed from `record +0x38` must
supply since `tableB[0] = tableB[2] = 0` and those entries' `+0x08` are 0. Conditions and raw
log: gdb-alloc-2026-09-11/RESULTS.md.
A Refuter reproduced all 24 rows and the T18 math from the raw log and arm9.bin.
The `0x800` seed was then traced the same day (`jus-8bjc`): a write-watch on record 20's
`+0x38` found it written once at record creation with the literal `0x800` from ov6 `0x02168E3C`
and never changed during the run, while the baseline census records were created through the arm9
wrapper `0x02083624` that hardcodes the seed to 0. The post-run census files already recorded
`0x800` on records 103 and 20. See
watch-0x38-2026-09-11/RESULTS.md.

## 8. Ichigo's six Y-variant entries (2026-09-11)

The six Ichigo Y-attack variants captured under tracker item `jus-puc7` (ids 264-269,
one entry per state) split into the same two groups this document already
describes: the three uncharged variants (fwd Y, up Y, air Y) have entry
`+0x08 = 0x20` and node `+0x18` bit 0 set, and the three charged variants
have entry `+0x08 = 0x00` and node `+0x18` bit 0 clear. See
`docs/research/findings/ichigo-y-variants-share-objshot-kind-and-record-but-each-has-its-own-collision-entry.md`.
