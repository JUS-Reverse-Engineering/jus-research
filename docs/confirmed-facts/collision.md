# Collision system reference

> **Scope note.** The ColPrm layer below was built from static mining
> (`docs/research/findings/` and tracker items). Since 2026-09-03 the runtime hitbox
> parser is closed (`jus-hitbox-record-selection-u3ig`, §G1: hitbox id from
> ALMT keyframes → `prmData+0x0C`, verified live on Kenshin). Since 2026-09-09
> the contact-array semantics are closed in the negative direction
> (`jus-contact-array-element-semantics-d7w8`, §G5: it is a per-pair predicate
> source for the move-script engine, **not** the damage hand-off — that runs
> through the record's twin accumulator arrays, damage.md §2.2/Step 6). The
> contact-queue insert (G3) closed the same day
> (`jus-contact-queue-insert-writer-j2ur`: manager bucket 4, FIFO tail-append,
> 512-node pool; also refuted the buckets-1/8-no-producer claim). Still
> open: ColMan/ColJoint (INVENTORY §2, GAPS G2).
> Spec tracker item: `jus-map.7`.

> **Supersession warning.** The iteration-59 headline "the contact array is NOT
> damage" is superseded and actively misleading: the producer it dismissed *is*
> the damage formula (P208–P211). Do not cite
> [../research/archive/findings/contact-array-is-not-a-damage-ledger.md](../research/archive/findings/contact-array-is-not-a-damage-ledger.md)
> or Battle-Engine-Map §collision-data "Settled (iteration 59)" for a
> "no collision→damage link" conclusion. Same for §hitbox-priority (the
> most-refuted section) and the `0x020924B0` "collision table" (refuted — it keys
> sprite archives).

## Navigate this reference

| Topic | Section |
|---|---|
| Architecture | [1](#1-architecture-three-modules) |
| Runtime data structures | [2](#2-the-colprm-manager-battle_colprmman) and [3](#3-the-colprm-record-0x188-bytes) |
| Wiring and loading | [4](#4-wiring-and-loading) |
| Collision-to-damage pipeline | [5](#5-the-per-frame-pipeline) and [6](#6-bit-11-the-collision-resolution-damage-pending-flag) |
| Attack-vs-attack contact (projectile layer) | [7](#7-attack-vs-attack-contact-projectile-layer) |
| Closed hitbox selection | [G1](#g1-the-runtime-hitbox-parser-closed) |
| Open research | [G2-G7](#g2-colman-and-coljoint-untouched-layers-settle-or-waive) |

---

## 1. Architecture: three modules

Collision is three source modules, recovered from assert strings
([collision-is-three-modules.md](../research/findings/collision-is-three-modules.md),
[symbol-names-recovered-from-assert-strings.md](../research/findings/symbol-names-recovered-from-assert-strings.md)):

| module | constructor | mapped? |
|---|---|---|
| `BattleCol.cpp` (ColMan) | `Battle_ColManCreate 0x0207AD3C` | **no** — untouched |
| `BattleColJoint.cpp` | `0x0207BD40` | **no** — untouched |
| `BattleColPrm.cpp` (ColPrmMan) | `Battle_ColPrmManCreate 0x0207C4C0` | yes — this document |

Everything below is the ColPrm layer. Iterations 52–126 mapped only this layer.

## 2. The ColPrm manager (Battle_ColPrmMan)

- **Identity:** the runtime object at `0x0220DDE0` IS Battle_ColPrmMan, settled
  after the P202/P203 retractions
  ([p204-object-is-colprmman.md](../research/findings/p204-object-is-colprmman.md),
  tracker item `jus-s5q`). Runtime addresses are session-local — re-derive with
  `scripts/emu/find_battle_structs.py`.
- **Allocation:** `Battle_ColPrmManCreate 0x0207C4C0`, size `0xFB54` bytes.
- **Zero unaccounted bytes.** The full tiling
  ([colprm-manager-layout-closed.md](../research/findings/colprm-manager-layout-closed.md),
  [colprm-manager-fully-accounted.md](../research/findings/colprm-manager-fully-accounted.md)):

| offset | contents |
|---|---|
| `+0x28`–`+0xD7` | 22 bucket list heads, cleared pairwise at construction; **all damage-path buckets have producers** — 1/4/8 via the computed-base helper `0x020809C8` (`0x02080AF4`/`0x02080AAC`/`0x02080BD8`), 2/3 via `0x020808C0`, 5/7/15/16 inline in the filler `0x0207FBD0`, 6 by the driver. (The old "buckets 1 and 8 have no producer" claim is refuted — same computed-base blind spot as the contact-array writer; [contact-queue-insert-writer-found.md](../research/findings/contact-queue-insert-writer-found.md)) |
| `+0xE0` | per-frame callback slot; the driver `0x0207F480` is registered here in the ctor at `0x0207C860` ([collision-pipeline-closed.md](../research/findings/collision-pipeline-closed.md)) |
| `+0xFC` | phase table, 19 entries — mostly tiny accessors ([phase-table-is-mostly-tiny-accessors.md](../research/findings/phase-table-is-mostly-tiny-accessors.md)) |
| `+0x14D` | flag byte; **bit 0 is arg2 of the damage formula** `0x020823E4` ([p208](../research/findings/p208-damage-formula-0x020823E4.md)) |
| `+0x154` | contact array: **4×4 cells**, rows stride `0xC0`, cells stride `0x30`, ends exactly at `+0x454`; per cell, five HP class slots `+0x00..+0x10` + fold `+0x14` and five SP class slots `+0x18..+0x28` + fold `+0x2C` ([contact-array-semantics-settled.md](../research/findings/contact-array-semantics-settled.md); indexed by two `mla`s at `0x02081340`/`0x0208134C`; only reader = NoteTrack query 0x47) |
| `+0x454` | **128 inline ColPrm records**, stride `0x188` (record size independently confirmed by the manager's own stride) |

## 3. The ColPrm record (0x188 bytes)

One object, three names: the entity constructor's *owner*, the ColObj owner,
and the damage-path *scratch*. 24 fields are mapped across six anchor
functions; the map is explicitly **partial, not the full struct**
([colprm-record-field-map.md](../research/findings/colprm-record-field-map.md) §4 —
unmapped spans `+0x00`–`+0x2C`, `+0x44`–`+0x4C`, `+0x70`–`+0x8C`, and most of
the `+0xA4`–`+0x173` scratch region). Note the distinction: the *manager* is
fully tiled; the *record* is not.

Structural fields:

| offset | what | source |
|---|---|---|
| `+0x08` | list head of `0x2C`-byte pool nodes (the record's own list, distinct from manager `+0x08`) | field map |
| `+0x34` | mutable flag API; `0x800` here is a **pairwise filter**, part of category routing | [record-0x34-is-a-mutable-flag-api-and-0x800-is-category-routing.md](../research/findings/record-0x34-is-a-mutable-flag-api-and-0x800-is-category-routing.md), [bit-0x800-is-a-pairwise-filter-not-an-axis.md](../research/findings/bit-0x800-is-a-pairwise-filter-not-an-axis.md) |
| `+0x38` | category bitmask; bits `0x4000`/`0x8000` pick an axis | [record-0x38-is-a-category-bitmask.md](../research/findings/record-0x38-is-a-category-bitmask.md), [category-mask-confirmed-selects-an-axis.md](../research/findings/category-mask-confirmed-selects-an-axis.md) |
| `+0x40` | flags word, reached from **both** arm9 (installer clears `0x200` at `0x0207CB2C`) and ov6 (damage flush tests `0x800` at `0x02158BA0`) — the cross-binary proof that collision and damage share one object | field map §3 |
| `+0x60` | the ColObj **wrapper** (0x40 bytes): `+0x08`/`+0x0C` head/tail of its 0x64-byte geometry elements (rect at element `+0x2C..+0x32`, live count `+0x0C`, id `+0x0E`), `+0x10` pair list, `+0x18` owner; zeroed by the teardown | field map; [hitbox-node-geometry-static.md](../research/findings/hitbox-node-geometry-static.md) §0 (live 2026-09-12) |
| `+0x68` | object whose `+0x20` list holds this record's bucket nodes; unresolved tension — flagged "vestigial, no writer" vs the formula's live `[r4+0x68]` walk ([record-0x68-is-never-set-second-vestigial-field.md](../research/findings/record-0x68-is-never-set-second-vestigial-field.md)) | field map |
| `+0xA4`–`+0x173` | `0xD0`-byte per-hit scratch region, memset by the installer | field map |

**Damage-side scratch fields** (`+0x40` bits, `+0xE8`, `+0x130`, `+0x140`,
`+0x144`, `+0x175` nature selector, `+0x184`/`+0x186` 8.8 multipliers) are
already specced field-by-field in [damage.md §2.2](damage.md) — that is the
canonical table; this document does not restate it.

## 4. Wiring and loading

- **No standalone registration.** The installer `0x0207C988` is called inside
  the entity constructor `0x020834D4` and returns the owner (a ColPrm record);
  `entity+0x10` = owner = damage scratch
  ([collision-wired-by-the-entity-constructor.md](../research/findings/collision-wired-by-the-entity-constructor.md),
  [entity-0x10-is-the-colobj-owner-and-the-damage-scratch-object.md](../research/findings/entity-0x10-is-the-colobj-owner-and-the-damage-scratch-object.md)).
- **Authoring data loader:** `Battle_PrmDataInit 0x021702BC` loads `chr/col/`,
  `chr/shot/`, `chr/effect/`; prmData pointer at `char+0x84`, collision array at
  `prmData+0x00`
  ([prmdatainit-is-the-collision-loader.md](../research/findings/prmdatainit-is-the-collision-loader.md),
  [prmdata-at-char-0x84...](../research/findings/prmdata-at-char-0x84-and-why-offset-scans-cannot-find-the-walker.md)).
- **On-disk format:** 281 collision files in `ChrBin.aar`, 20-byte record
  stride, 2837 records total. Full-roster facts: hitModifier is *not*
  constant, damageFlags==0 in 46.86% of records, projectileId spans −34..36
  ([collision-data-extracted.md](../research/findings/collision-data-extracted.md)).
  Round-1 claims (−32 sentinel, constant hitModifier, one terminator per file,
  knockback monotonicity) are all broken — use only the full-roster numbers.
- damageFlags is the damage gates' class index (tracker item
  `jus-class-index-is-damageflags-mx5`; `damage.md` move-data block `+0x0E`).
  The Feb-2026 "two systems, 10 direct / 64 indirect" reading in
  [DamageFlags-Character-Classification.md](../research/DamageFlags-Character-Classification.md)
  is **superseded**; that page carries the banner.

## 5. The per-frame pipeline

Driver `0x0207F480` (440 instructions), registered on manager `+0xE0`
([collision-pipeline-closed.md](../research/findings/collision-pipeline-closed.md),
[driver-is-the-primary-bucket-filler.md](../research/findings/driver-is-the-primary-bucket-filler.md)):

- Drains the buckets and is also their **primary filler**; runs an 8-stage
  pipeline via forwarder `0x02080C28` → `0x02080F14`.
- **Queue mechanics (G3, closed 2026-09-09):** the pre-pipeline filler
  `0x0207FBD0` (called at `0x0207FA64`) walks bucket 6's records and each
  record's pair list `[[record+0x60]+0x10]`, and enqueues pairs into the
  buckets as **FIFO tail-appends** of 0xC-byte nodes from a 512-node shared
  pool (free list `manager+0xD8`, **no overflow guard**), via the generic
  list helpers `0x02037B98`/`0x02037C24`. Insert sites:
  bucket 4 `0x02080AA4-0x02080AAC`, bucket 1 `0x02080AF4-0x02080AF8`,
  bucket 8 `0x02080BD8-0x02080BDC`. No dedup at insert; stage 4 arbitrates
  same-key pairs at consumption (payload `+0xC` compare, `0x02031070` bit 4)
  ([contact-queue-insert-writer-found.md](../research/findings/contact-queue-insert-writer-found.md)).
- The narrowphase pair test **is the damage formula** `0x020823E4`
  ([narrowphase-pair-test.md](../research/findings/narrowphase-pair-test.md)) —
  collision does not hand off to a separate damage step; the pair test computes it.
- Results accumulate twice from the same pair body: into the **victim record's
  twin 18-word accumulator arrays** (`record+0xA4` HP / `record+0xEC` SP, writer
  `0x020812C8-0x020812F4`) — this is the collision→damage hand-off (damage.md
  Step 6) — and into the contact array at `manager+0x154` via a five-class
  routing cascade (priority 1 > 2 > 3 > 4a > 4b) across `0x02081340`–`0x02081464`
  ([contact-array-writer-found.md](../research/findings/contact-array-writer-found.md),
  [contact-array-semantics-settled.md](../research/findings/contact-array-semantics-settled.md)).
- The per-frame clear of the contact array is **partial** (0xC0 bytes, cells
  `[0][*]` only, `0x0207FA50`); the record scratch is cleared fully
  (`0x0207F8AC`, 0xD0 bytes).
- **Bucket routing table, live-basis rows (`jus-tfr0`, 2026-09-12).** Full
  static + live pass:
  [collision-bucket-routing-static.md](../research/findings/collision-bucket-routing-static.md)
  §7; run detail:
  bucket-routing-2026-09-12/RESULTS.md.
  Node `+0x14` class bits observed live: `0x2000000x` = fighter body,
  `0x1000000x` = bit 24, raw — unnamed in the static doc
  ([collision-bucket-routing-static.md](../research/findings/collision-bucket-routing-static.md)
  line 92); the "attack hitbox (no persistence)" reading below is inferred
  from the driving plan (a `B` press landed, HP dropped) and from the
  bit-12 contrast with true projectiles, not read off the bit itself.
  `0x1000100x` = true projectile (bit `0x1000` on top of the bit-24 class,
  subject to the `0x020808A4` drop-test). Confirmed routes (per-row grade
  and conditions; counts verified against the decompressed logs in
  `bucket-routing-2026-09-12/logs/`):

  | bucket | live participants | count/state | grade | conditions |
  |---|---|---|---|---|
  | (none) | fighter body (`0x2000000x`) vs fighter body, no active attack | 78 pair-loop entries (39 per directional entry, pairs `0x220963c`/`0x2209664`), 0 appends | CONFIRMED_LIVE | `ds8t_jj_battle_noheal`; attached window 403 bridge frames (84 pair-loop passes total in this window, of which these 78 are body/body) |
  | 1 | attack (`0x1000000x`) vs fighter body (`0x2000000x`) | 6 pair-loop entries (pairs `0x220a334`/`0x220a384`, ticks 654-656), 1 append | CONFIRMED_LIVE | `ds8t_jj_battle_noheal`; attached window 403 bridge frames; append at pair-loop pass "frame=654" (a pass index, not a bridge frame — see G4 note below) |
  | 1 | true projectile (`0x1000100x`) vs fighter body (`0x2000000x`); class-only, character/survivor attribution dropped per Refuter | 1 logged append, same pair repeats for 14 pair-loop passes with no further append | CONFIRMED_LIVE | `pc-momotaro-npc-yusuke-projectiles-about-to-collide`, run 2b; attached window 78 bridge frames (54 pair-loop passes) |
  | 8 | attack (`0x1000000x`) vs true projectile (`0x1000100x`) — the projectile clash itself | 1 append, reproduced in both sub-runs of the same launch | CONFIRMED_LIVE | `pc-momotaro-npc-yusuke-projectiles-about-to-collide`, runs 2a+2b; attached windows 24 and 78 bridge frames |
  | 7 | true projectile (`0x1000100x`) vs true projectile, one directional entry only | 1 append; mirror entry 0 (asymmetry reproduced) | CONFIRMED_LIVE, nodeB14 at the append site itself unreliable (see tfr0_routing.gdb caveat; the `LOOP_HDR` reading is used instead) | `pc-naruto-fy-npc-yusuke-fy`; attached window 24 bridge frames |
  | 10 | — | 0 writes on a write-watch across all 4 launches | waive candidate, not proven | attached windows per run: 403 + 24 + 78 + 24 = 529 bridge frames combined (the watchpoint lived only while each session's GDB was attached; three of four sessions ended early on SIGTRAP/stdin error at pass 5, 5, and 54 respectively — only the melee launch gave a long attached window) |
  | 2, 3, 4, clash | — | not exercised live this batch (feel-over-roster) | blank, not inferred | — |

  The "403 bridge frames" figure for `ds8t_jj_battle_noheal` is the
  session's own self-reported `fc_start`/`fc_end`/`observed_frames`, not a
  committed bridge-output artifact — the live run detail doc marks it
  `[unrecoverable: bridge output not committed]`. The pair-loop append
  counts above (78/6/0/1) are independently verified against the
  committed, decompressed `.log.gz` files and do not depend on that
  number; only the bridge-frame *denominators* (403, 24, 78, 24, and their
  529 sum) carry this caveat.

  Bucket 8 is not a general "projectile" bucket — it fired only for the
  attack-hitbox-vs-true-projectile clash; a true-projectile-vs-body pair
  routed to bucket 1 instead, in the same state one extended run later.
  Bucket 1 is the broad fallback across at least three class combinations
  now, not one narrow category.

## 6. Bit 11: the collision-resolution damage-pending flag

Confirmed
([p187-scratch-0x40-flag-word-and-arm9-collision.md](../research/findings/p187-scratch-0x40-flag-word-and-arm9-collision.md)):

- `scratch+0x40` is a bitfield; the ov6 damage flush gates on **bit 11
  (`0x800`, damage pending)** at `0x02158BA0` before reading the amount at
  `+0xE8`. Bit-11 semantics are ESTABLISHED (the flush reads it live).
- Known bits: 11 (damage pending), 25 and 30 (three-instruction setters
  `0x021591F4`/`0x02159210`, cleared by the expiry handler; bit 30 also
  forces the nature factor to 1.0, see damage.md).
- A static setter exists in arm9 collision resolution: `0x02081DDC` (992
  bytes, one caller) ORs `0x800` onto **both** participants' scratches at
  `0x02081ED0`/`0x02081EE0`, deriving the scratch via `[[participant+0x1C]+0xC]`.
- **However**, the runtime card was rejected: `0x02081ED0`/`0x02081EE0` never
  execute on a landed hit (control fired, card did not — tracker item `jus-x6j`). The
  reason is one level up: `0x02081DDC` *is* called (6 entries), but its loop
  body never runs — unconditional counters gave 0 fires at `0x02081EA8` for
  any element, so the list at `[sl+0x48]` is empty on a landed hit and the two
  `orr` sites are unreachable on that path rather than merely unvisited
  (training mode 0, items/gimmick/team 0/0/0, heal off, two landed −6.000 hits
  against an in-session positive control). Cited for the reachability
  measurement only: tracker item `jus-e1c` is itself a retraction — it refutes an
  earlier candidate at `0x02081F5C` inside the same function — so do not read
  it as support for anything about that instruction. So
  bit 11's *semantics* are confirmed, but its live setter on a landed hit is
  still unidentified (see GAPS). 7 of the 12 `orr 0x800` sites sit in
  overlays that were never resolved — unchecked, not clear (P187).

## 7. Attack-vs-attack contact (projectile layer)

**Grade: PLAUSIBLE.** Tracker items: `jus-hitbox-priority-clash-1evz` (parent),
`jus-pebk`, `jus-qqiy`, `jus-8zoi`, `jus-dib9`, `jus-58bf`.

This section describes the mechanism now measured for two attack hitboxes
(most often two projectile-class ColPrm records) touching each other, as
distinct from an attack hitting a fighter's body (§5–6 and damage.md).

- **Slot-agreeing field.** Every ColPrm record carries a two-valued field
  that agrees with player slot (1 = P1 side, 2 = P2 side) on 49/49
  independently attributed records; not yet separated from controller
  port / collision team / spawn-parent channel: the low nibble of
  `record+0x34` reads `1` / `2` and the low byte of `record+0x3C` reads
  `0x11` / `0x22` for player slot 1 / player slot 2. The 49 independently
  attributed records: fighter bodies in 21 states examined (42 records),
  the positive-control record (1, rec70), Naruto's rec49/50/51 (3),
  `pc-ichigo-fy-vegeta` rec115 (1), `pc-mashirito-fy-npc-momotaro-b`
  rec99 (1), and the created record from the one-fighter-two-slots
  separating test (`jus-rp0y`, 1)
  ([colprm-record-0x34-0x3c-low-bits-agree-with-player-slot.md](../research/findings/colprm-record-0x34-0x3c-low-bits-agree-with-player-slot.md), `jus-qqiy`, `jus-rp0y`).
  **Separating test done (`jus-rp0y`, 2026-09-12):** the same fighter
  (Yusuke) firing the same move (forward Y) once as P1 and once as P2
  reads `0x1001`/`0x63C811` (slot 1) as P1 and `0x1002`/`0x63C822` (slot 2)
  as P2 — not falsified; agrees with "player slot," not "character
  identity" (slot-p1-2026-09-12/RESULTS.md).
  Controller port / collision team / spawn-parent channel remain
  unseparated from "player slot" by this test.

- **Pair list.** Each collision produces two directional pair entries — one
  with participant A / partner B, one with the sides swapped — in one shared
  list at `manager+0x58`, walked twice per frame by the pre-pipeline filler
  `0x0207FBD0` ([pair-loop-drops-class-0x1000-nodes-with-bit0-clear-at-0x0207FD50.md](../research/findings/pair-loop-drops-class-0x1000-nodes-with-bit0-clear-at-0x0207FD50.md),
  `jus-58bf`, extending `jus-dib9`). **Live-confirmed (`jus-z87k`,
  [pair-entry-creation-site-static.md](../research/findings/pair-entry-creation-site-static.md)):** these are per-wrapper lists —
  each geometry-record wrapper (`*(record+0x20)`) owns its own list at
  `wrapper+0x10`, reconciled every frame using a shared node pool
  (`0x0207ACB8` allocates, `0x0207AD04` frees). The September12 capture
  measured zero recurrence among 9,094 creates / 9,097 unlinks; this does
  not establish universal node replacement. October2 recovery traces
  (`jus-peon`, routing evidence)
  show the same fine-pair nodes retained across continuous melee/body
  overlap. Fresh `0x10` becomes recurring `0x11`; `020800E8` skips that
  recurring pair before the helper, even after protection expires. A broad-phase pair with no passing fine
  sub-element still yields a type-6 (object-level) entry via the
  unconditional companion call at `0x0207BA4C` — that entry is dropped by
  the pair loop's `tst r0,#4` gate (`0x0207FC04`) rather than never being
  created; **contact is the type-2 (fine sub-element) entry**, created at
  `0x0207ACB8` after the inclusive two-axis `|Δc| <= ΣH` test passes on
  both the broad phase (fields `+0x2C..+0x32`) and the fine phase (per
  sub-element, `+0x3C + i*8`), live-confirmed `jus-z87k`.

- **Tier compare (measured 2026-09-25, capture C5,
  `jus-special-clash-rule-3x02`,
  RESULTS
  "The tier rule in the code").** Before the tests below, the pair loop
  compares byte `+0x00` of the two nodes' moveData entries (the tier) at
  `0x0207FD08`. The drop test, the enqueue and the `0x0207FDAC` mark below
  run only for **equal** tiers. For different tiers, `0x0207FE0C` (`bls`)
  ends the orientation with the lower A; the other writes the contact masks
  (A `+0x22`, B `+0x20`) and marks nothing. Helper `0x020809C8` then marks
  the lower-tier side only, at `0x02080C18`, gated on its bit 0. The
  caller (from `0x0207FE54`, a walk of each object's own contact list, the
  one the pair loop reads) loads both tiers at `0x02080120`-`012C`
  and skips equal tiers (`0x02080134`). When the first record's `+0x44`
  bit 0x4 is clear, `0x020801BC`-`01C0` (`bhs`) skip the helper call unless
  the first side is lower, and every measured `H18` line (151) came from
  that call (return `0x020801D4`). So on that route a higher tier is never
  marked by a lower one. When the bit is set (`0x02080140`-`016C`) and the
  second node's `+0x14` has none of 0x24000100, the caller calls
  `0x020808C0`, gated only on "the tiers differ"; it marks the second
  object if its `+0x18` bit 0 is set (`0x02080958`-`0968`). No measured
  line took that route, and record `+0x44` wasn't read.
  All nine C5 pair states fit the bit-clear route;
  the participation-only rule misses two pairs, three states with a
  preroll (Yusuke's X, tier 4, against
  Naruto's shuriken and Yugi's wave, tier 2). This supersedes the older
  "no strength comparison" reading (the combat notes).

- **Drop test.** Helper `0x020808A4(nodeA+0x14, nodeA+0x18)` returns 1 iff
  class bit `0x1000` is set in `+0x14` **and** bit 0 is clear in `+0x18`. An A
  node for which the helper returns 1 is dropped at `0x0207FD50`, before
  either the bucket enqueue or the object mark below — it never becomes a
  contact for this pass ([pair-loop-drops-class-0x1000-nodes-with-bit0-clear-at-0x0207FD50.md](../research/findings/pair-loop-drops-class-0x1000-nodes-with-bit0-clear-at-0x0207FD50.md)).
  A persistent per-node `+0x24` overlap mask: if `A+0x24 & (B+0x14 &
  0xFFFFFF)` is nonzero the entry is skipped; otherwise that masked value
  is OR-ed into `A+0x24` (halfword). **Object-base correction, 2026-10-01:**
  A/B here are 0x2C-byte ColPrm participants loaded via the pair geometry
  elements' `+0x1C`, not the 0x14-byte pair entries. Participant release
  clears all 0x2C bytes at `0x0207D91C–928`; owner teardown also clears
  them. The per-frame clear changes `+0x20/+0x22`, leaving `+0x24` intact.
  Pair-entry recycling does not establish a stale carry in this mask.
  Its writer is an equal-tier route, distinct from ordinary body/attack
  protection rejection; do not infer a spent normal attack from it.
  See [the static correction](../research/findings/participant-overlap-mask-lifetime-static.md)
  for source hashes, allocation/reset sites and the separate CE gate.

- **Mark.** An A node with `+0x18` bit 0 **set** has its participant object's
  `+0x18 |= 0x2`, at two structurally identical sites gated on the same test
  (`nodeA+0x18` bit 0): `0x02080C18`, reached via the helper for buckets
  1/4/8 ([contact-queue-insert-writer-found.md](../research/findings/contact-queue-insert-writer-found.md)), and `0x0207FDAC`, inline on the bucket-7 enqueue path and also
  reached via the `0x0207FD74` skip that bypasses the append entirely
  ([contact-marks-object-bit-0x2-via-two-sites-gated-on-node-bit0.md](../research/findings/contact-marks-object-bit-0x2-via-two-sites-gated-on-node-bit0.md),
  `jus-8zoi`, refined by `jus-dib9`). A third, uninstrumented site at
  `0x020808C0` (buckets-2/3 helper; corrected 2026-09-12 from `0x02080660`)
  contains at `0x020808F4-0x02080904` a predicated **clear** of the same
  object bit. **Gate, verified by disassembly (jus-yv70, `query.py disasm
  0x020808C0 80`):** reached when `(record+0x40 bit 0x4000 set) OR
  (nodeB+0x14 bit 0x4000000 set)`, **and then** `nodeB+0x18 bit 0` must
  also be set for the `strbne` to actually execute. This is the **same
  participant** (`B`) on both sides of the gate: `objB+0x18` is cleared,
  gated on `nodeB`'s own bit 0 (`r1`=nodeB and `r2`=objB throughout, per
  the disassembly's register roles) -- not "the other participant's node
  bit 0" as this doc previously said. A structurally symmetric `orrne`
  site at `0x02080964`, reached only when the first (record+0x40
  bit 0x4000) branch was *not* taken and a second, distinct condition
  (`nodeB+0x14` bit `0x100`, then `nodeB+0x1c` bit `0x40000000` clear)
  holds, **sets** the same `objB+0x18` bit `0x2`, gated on the same
  `nodeB+0x18` bit 0 -- not a role-swapped mirror of the clear, the same
  participant B, uninstrumented — never observed to fire in these
  runs ([pair-loop-drops-class-0x1000-nodes-with-bit0-clear-at-0x0207FD50.md](../research/findings/pair-loop-drops-class-0x1000-nodes-with-bit0-clear-at-0x0207FD50.md),
  Limits).

- **Next-frame free.** The flag writer at `0x0207FAF8`–`0x0207FB0C` reads that
  object bit (`tst r0,#2`) the frame after the mark and, if set, stores
  `record+0x40 = 0x209`; the record is torn down and freed shortly after
  ([contact-marks-object-bit-0x2-via-two-sites-gated-on-node-bit0.md](../research/findings/contact-marks-object-bit-0x2-via-two-sites-gated-on-node-bit0.md);
  [momotaro-yusuke-projectile-conflict.md](../research/findings/momotaro-yusuke-projectile-conflict.md)).

- **Seed of the participation bit.** Node `+0x18` bit 0 is seeded, per
  authored hitbox, from the resolved collision entry's `+0x08` property word:
  for every authored per-character entry (hitbox id `>= 0x100`) bit 0 is set
  iff `entry+0x08` bit 5 is set, via table `T18@0x0209FDC4[5] = 1` — the only
  index in that 32-entry table whose value has bit 0 set
  ([node-0x18-is-seeded-from-the-collision-entry-property-word.md](../research/findings/node-0x18-is-seeded-from-the-collision-entry-property-word.md),
  `jus-2s9k`; verified against 28 resolved nodes across 12 census states, 0
  mismatches). This is authored per-move data, not a runtime computation.

**Owner-facing correlates** (`docs/research/moveset-notes/OWNER-NOTES.md`,
"Owner projectile-conflict states for jus-pebk"; pair test in
[projectile-conflict-pair-test-2026-09-11.md](../research/findings/projectile-conflict-pair-test-2026-09-11.md), `jus-pebk`):

This plausibly
explains melee moves such as Sasuke X destroying Yusuke X: a separately
measured ordinary-attack-versus-true-projectile pair routed through bucket 8
with the ordinary attack bit-clear and the projectile bit-set, so only the
projectile takes the teardown mark. The Sasuke rerun found no Sasuke-shaped
projectile record, which agrees with the owner's description of X as melee.
The actual Sasuke-hitbox/Yusuke-projectile pair was not logged, so applying the
generic rule to that exact move remains inferred (`jus-m2iq`).

- **Bit-clear vs bit-clear passes through.** Yugi's dice (record 45, entry
  property bit 5 clear) against Momotaro's forward+Y (record 50, entry
  property bit 5 clear): neither record ever reaches `0x209`; both projectiles
  visibly pass through each other with no collision effect and no damage.
- **Bit-set vs bit-set: both vanish with the collision effect.** Yusuke's
  forward+Y (bit 5 set) against one of Naruto's three shuriken (bit 5 set)
  (move identity inferred from owner testimony plus x direction and entry
  pointer; the census has no owner field): both records reach `0x209` on
  the same frame pair, matching the owner's report that Yusuke's
  forward+Y and one shuriken vanish together with the collision effect.

**GAPS.**

- Contact itself is now defined (type-2 pair entry, live-confirmed
  `jus-z87k`, see the Pair-list bullet above) — no longer open.
- What writes or clears the per-node `+0x24` overlap mask, given that
  nodes are recycled from a shared pool every frame and the unlinker never
  zeroes `+0x24` (see the Drop-test bullet's hazard note above), is
  unmeasured. It is unclear whether `+0x24` is meant to be read as a
  per-object persistent mask at all, or whether the apparent persistence
  in prior runs was actually stale data left by an unrelated pair that
  previously occupied the same recycled node.
- The clear site at `0x020808F4` in `0x020808C0` (`objB+0x18` bit `0x2`
  cleared, gated on **`nodeB`'s own** bit 0 -- the same participant, not
  "the other participant" as this doc previously said; see the Mark
  bullet above for the full disassembly-verified gate) has zero hits in
  every run so far — uninstrumented, not ruled out.
- Why record 51 of Naruto's three shuriken (bit 0 set, like the marked pair)
  was never paired in any logged pass is unexplained; it never appears as
  participant A or B and never reaches `0x209`
  ([pair-loop-drops-class-0x1000-nodes-with-bit0-clear-at-0x0207FD50.md](../research/findings/pair-loop-drops-class-0x1000-nodes-with-bit0-clear-at-0x0207FD50.md),
  Limits).
- Two upstream loop filters — `rec+0x34` against `0x00080800`
  (`0x0207FBEC`–`0x0207FBF4`) and entry `+0x10` bit 2
  (`0x0207FC04`–`0x0207FC0C`) — were never instrumented, so "entry absent"
  and "entry filtered before the pair loop" are indistinguishable.
- A mixed bit-set-vs-bit-clear pair was captured once at the mechanism
  level (`jus-yv70`, `pc-taikoubou-upx-npc-yusuke-x` frame 62, feel-captures
  SUMMARY "Mixed pair and clear site"): reverse entry (A = tornado, bit 0
  clear) dropped at `0x0207FD50`; forward entry (A = created slot-2 record,
  bit 0 set) took bucket 7 and marked its own object at `0x0207FDAC`; that
  record read `0x209` next frame, the tornado never did. Not established:
  the bit-clear record's fate beyond the encounter (it left the pool 10
  frames later, cause unlogged); the yugi-fb candidate dropped at an
  unrelated gate (`0x0207FC48`) and is uninformative; and "contact" itself,
  since the pair loop tests only flag bits and pair-entry creation (the
  geometric decision) is unmeasured (`jus-z87k`). The earlier `jus-8zoi`
  control run paired rec70 with the P1 fighter body, not another attack.
- No gameplay name exists for node `+0x18` bit 0 beyond "attack-contact
  participation" — the code makes it a boolean qualifier for the mark/drop
  tests above; nothing traces it to a "priority," "cancel," or "clash tier"
  concept the game exposes (the second-opinion review that makes this
  point is `codex_second_opinion_obj18_writers`, cited in the
  contact-marks finding; the gate review agreed on the helper and mask
  reading only).

---

## GAPS — settle-or-waive candidates

Each item: what's missing, what an implementer would have to invent if we
waive it, and how risky that invention is.

### G1. The runtime hitbox parser — CLOSED

**Fully closed 2026-09-03** (`jus-hitbox-record-selection-u3ig`,
static-hitbox-record-selection,
runtime-report-2
E4). An animation frame writes `ColWork+0x0E` (the hitbox id) through
the character's ALMT motion file's per-node `CollisionTypeN` keyframe track
(`(frame, value)` pairs; `CollisionEnableN` is only the on/off toggle, a
different property). At spawn time (arm9 `0x0207D440`):

- id `≥ 0x100` → the character's own `chr/col` file: record pointer =
  `[[ColPrm_record+0x6C]+0x0C] + (id − 0x100) × 20` (the col array base is
  `prmData+0x0C`, not `+0x00` — this is why every earlier `prmData+0x00`
  offset scan came up empty).
- id `< 0x100` → one of 14 engine built-in boxes, `0x0209FC2C + id × 20`
  (index 0 = the all-zero, no-damage box every idle animation uses). Not
  exercised live — nothing here probes the `id < 0x100` arm.

Record bytes `+8..+0xB` are one 32-bit property bitmask (`ldr` as a whole
word, confirmed as the record's `type` byte at `moveData[+1]`), not the
`offsetX`/`offsetY`/`positionFlags` the exported `*_collision.json` implies —
see `physics.md` §4.6's export caveat. `scripts/analysis/move_records.py`
walks the ALMT tracks (now decoding every node of every entry, not just node
0 — the ALMT full-node decode, see
static-hitbox-record-selection.md)
and prints, per authored record, the referencing animation/channel/frame, or
"unreferenced."

**GDB-confirmed live** (`0x0207D4AC`, one instruction past the tracker item's proposed
`0x0207D4A8` — that address is the stale `ldrh r3,[r6,#0xe]` itself and cannot
be conditioned; `0x0207D4AC` is the `cmp r3,#0x100` where `r3` holds the id,
condition `$r3 >= 0x100`). Kenshin B jab hit 1 → `r3 = 0x100` → **record 0**
(type 1); Kenshin X hits 1–4 → `r3 = 0x113/0x111/0x112/0x114` → **records
19, 17, 18, 20** in that order, colbase `0x021BAA00` in all five captures.
All five live 20-byte dumps are byte-identical to
`move_records.py 36 --record N` — "Kenshin X = record 20" (the finisher,
kind 5 type 6 kbX 25 kbY 6) is now a measurement, not an inference. The
walker also maps record 20 to animation `0x80` (frames 22/25) of
`rk_b_01_5.aar`. A move-to-record walker must follow **spawned elements**,
not just the fighter: the X special's hits 2–4 are owned by a different
ColPrm record (a spawned effect element) than hit 1 (owned by Kenshin
himself).

**Coverage after the ALMT full-node decode fix:** Kenshin 29/29 attack
records referenced; Luffy 37/38 (record 30 unreferenced); Franky 9/12
(records 16, 17, 20 unreferenced). These remainders are an **open note, not a
TBD** — they may sit on a still-undecoded `GN0N` sub-block, or (Luffy's
single unreferenced record in particular) may be genuinely unused authored
data; `move_records.py --nodes` lists every undecoded block and why it failed
its self-check, for anyone who wants to chase it further.

Owner testimony (2026-09-03, on `jus-hitbox-record-selection-u3ig`) points at
where they probably live: Luffy's up+Y keeps hitting for as long as Y is
mashed (the GameFAQs guide says "keep pressing Y to increase the amount of
hits"), and Franky's Y moves are powered up in two steps by his Ultimate
Action (SELECT, drinking cola). Records reached only by a mash-extension or a
powered-up branch would never show up in the base animation walk.

> **Correction (2026-10-18, E0 roster):** the file labels in this lead are
> wrong. `na_b_03` is Sakura (chr_b 22) and `bc_b_02` is Train (chr_b 38);
> Sasuke is `na_b_02` (chr_b 21) and Eve is `bc_b_01` (chr_b 37), per
> roster_reconciled.json.
> The "joins nothing" observation below was made on the Sakura and Train
> files and says nothing about Sasuke or Eve. Kept as history.

**Open lead, 2026-09-03** (run 7,
runtime-report-7-pops-launchers):
Sasuke (`na_b_03`, 22 records) and Eve (`bc_b_02`, 20 records) join **nothing**
against `move_records.py` — not their launchers, not their pops, not even
their plain `B`. Both files are much smaller than the 28–40 records the five
joining characters (Muhyo, Raoh, Yoh White Swan, Kenshin, Jotaro) carry, and
both have per-koma sibling archives on disk the flat `chr/col/<file>.bin`
does not cover (`na_b_03_4c.aar`/`_5c.aar`/`_6c.aar` alongside `na_b_03c.aar`;
`bc_b_02_4c.aar`/`_5c.aar` alongside `bc_b_02c.aar`). The reading offered
there: `chr/col/<file>.bin` may be one koma's record set, and a deck running
a different koma may author its hitboxes in the `_Nc` sibling instead — which
would also explain the Kakashi `B`/`up B` mismatch physics.md §4.6 already
records as "a Kakashi-specific problem." Not established here (Muhyo joins
from the base file at 4 koma, so the base file is not always the small koma).
Belongs to `jus-hitbox-record-selection-u3ig`, not to run 7's own tracker items.

### G2. ColMan and ColJoint — untouched layers (settle-or-waive)

Two of the three modules (`Battle_ColManCreate 0x0207AD3C`, ColJoint
`0x0207BD40`, ColJoint manager `*(0x0214BE0C)`) have no field map at all.
**If waived, invent:** whatever these layers do — plausibly world/terrain
collision (walls, floors, panel boundaries) and joint/attachment collision.
**Risk: medium.** The damage path demonstrably runs entirely through ColPrm,
so combat damage may not need them; but movement/terrain response would be
invented from black-box behavior. A cheap partial settle: run the constructor
map (guards 8/9/13) on the two ctors to at least size and skeleton them.

### G3. The `+0x48` list insert — CLOSED 2026-09-09

**Settled** (`jus-contact-queue-insert-writer-j2ur`,
[contact-queue-insert-writer-found.md](../research/findings/contact-queue-insert-writer-found.md);
codex second opinion in agreement): the list stage 4 walks is **manager
bucket 4** (`manager+0x48/+0x4C`), not a field on the record/element. The
insert is `0x02080AA4 add r0,manager,#0x48` + `bl 0x02037B98` (tail-append,
FIFO) inside the pre-pipeline filler `0x0207FBD0`; nodes are 0xC bytes from a
512-node shared pool with no overflow guard; no dedup at insert (stage 4
arbitrates at consumption). p205's immediate-store sweep was null because the
insert is a computed-base `add` + helper call, not a store at the offset —
same blind-spot class as the contact-array writer. **By-product:** buckets 1
and 8 DO have producers (`0x02080AF4`/`0x02080BD8`), refuting the §2 claim
above and the iteration-67 finding (now banner-marked). The ColPrm record's
own `+0x48/+0x4C` pair is cleared per frame at `0x0207F87C` but has **no
writer anywhere** — likely dead state (one-frame watchpoint settles it).

### G4. Phase tables and pipeline attribution (narrowed 2026-09-12, settle-or-waive on bucket 10 only)

The manager's 19-entry phase table at `+0xFC` is "mostly tiny accessors"
([phase-table-is-mostly-tiny-accessors.md](../research/findings/phase-table-is-mostly-tiny-accessors.md);
the phase interface passes a `0x10` struct,
[phase-interface-passes-a-0x10-struct.md](../research/findings/phase-interface-passes-a-0x10-struct.md)).
**Narrowed by the static + live bucket-routing pass** (`jus-tfr0`,
[collision-bucket-routing-static.md](../research/findings/collision-bucket-routing-static.md)
§§1-7): buckets 1/8 are **not** dead — both have confirmed producers and
bucket 1 was live-confirmed firing (melee attack-vs-body, projectile-vs-body);
21 of 22 buckets now have a static producer (buckets 18/19 via the newly
found helper `0x02081AB0`), and 4 of those (1, 7, 8, plus the write-watched
absence on 10) are live-confirmed. **Only bucket 10 (`manager+0x78`) remains
genuinely unattributed** — no producer anywhere in a complete 100-site arm9
census, and no static producer was found in the 100-site census; it was
not exercised in the one long attached window (403 bridge frames,
`ds8t_jj_battle_noheal`). The write-watch's combined attached window across
all four launches sums to 529 bridge frames (403+24+78+24), not ~212 — that
figure was unsourced; but the watchpoint only lives while GDB stays
attached, and three of the four sessions ended early (SIGTRAP/stdin error
at pair-loop pass 5, 5, and 54 respectively), so only the melee launch gave
a long window. **Risk: low-to-medium; waive candidate pending one
long-window write-watch in a state exercising buckets 2/3/4.** **If
waived, invent:** only bucket 10's category, plus buckets 2/3/4/clash-list's
exact live gating (statically attributed, not yet exercised live) and
pipeline stages 4-7's per-stage meaning. The load-bearing stages (bucket
fill, narrowphase = damage formula, contact accumulation) are attributed
and now partly live-confirmed; bucket 10 alone, with zero writes observed
in the one long window, is a plausible waive (dead list) once that
follow-up window is run.

### G5. Contact-array element semantics (CLOSED 2026-09-09, negative)

**Settled** (`jus-contact-array-element-semantics-d7w8`,
[contact-array-semantics-settled.md](../research/findings/contact-array-semantics-settled.md);
codex second opinion in agreement): the array is **not** the damage staging
area. It is a per-pair contact record — 4×4 cells, five HP + five SP routing
class slots + folded totals per cell — whose only reader is NoteTrack query
0x47 (ov6 `0x02157EC4`), a boolean "class-4a contact with any other
participant?" predicate gating move-script note advance. The damage hand-off
runs through the record's twin 18-word arrays (`+0xA4`/`+0xEC` → folds
`+0x134`/`+0x138`), which also explains the old B11 residue: `+0xE8`/`+0x130`
are slot 17 ("empty class nibble" sentinel), read only under the bit-11 gate.
Open remainders (U1–U6 in the finding): index = participant-slot vs class
(the load-bearing ambiguity), the partial per-frame clear, routing-class
names, and write reachability — all carry one-line falsification tests.

### G6. Who sets bit 11 on a landed hit (settle)

Semantics confirmed (§6), and since 2026-09-09 the **consumer side is fully
mapped** (G5 close): the bit-11 path at `0x02158B94-0x02158BCC` reads the
slot-17 pair `record+0xE8`/`+0x130`, negates, and applies HP via `0x020783CC`
and SP via `0x020781E4` — a second application path parallel to the
`+0x134`/`+0x138` fold consumers at `0x0215AC08`/`0x0215AC5C`. What remains
open is the setter: the only located setter never executes on a
landed hit (tracker item `jus-x6j` — and since the G3 close, explained: ordinary
hits route to bucket 1, and the bucket-4 insert gate at `0x020809C8` requires
A `elem+0x14` bit 29 set with B bit 8 set, a combination normal
character-vs-character hits do not present), and 7 of 12 `orr 0x800` sites are
in unresolved
overlays. **If waived, invent:** the trigger condition for "this contact
becomes damage this frame". **Risk: high** — this is the collision→damage
edge itself. Cheap settle path: resolve the 7 unchecked overlay sites
statically before any emulator work.

### G7. Collision↔jpower join key (waive-leaning)

isTerminator as a per-move sub-list delimiter is untested (INVENTORY §2 open
Q5). The old "jpower entry selection for damageFlags==0" question is closed as
moot (`jus-9lp.1`): damageFlags is the class index, and a move's base damage
is the chr/col `+4` byte, not a jpower lookup (`jus-jpower-retraction-cguk`; the old jpower reading
`jus-base-2-is-jpower-damage1-10-mse` is retracted).
**If waived, invent:** the record-to-move grouping inside each collision file.
**Risk: low-to-medium** — it's a data-pipeline question answerable later by
cross-referencing extracted data ([collision-data-extracted.md](../research/findings/collision-data-extracted.md))
against measured move damage, without touching the binary.
