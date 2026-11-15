# JUS entities and projectiles reference

> **Scope.** Static pool/ownership analysis, live kind/lifetime captures, and
> labeled owner testimony. Unmeasured kind predicates and early termination
> remain in GAPS. Projectile tokens remain opaque.

Reference for the battle entity pool and projectile machinery in Jump
Ultimate Stars (`jus.nds`, AJUJ). Backed by static disassembly of `arm9.bin`
and `arm9_ov06.bin`, cited inline. Tracker items (the issue tracker) hold raw logs.

> Battle-Engine-Map.md carries a taint banner; only its
> §projectile-entities claims (verified through 3 lenses, 2026-08-15/17
> updates) are cited here, alongside findings journal entries.

## Navigate this reference

| Topic | Section |
|---|---|
| Manager architecture | [1](#1-architecture-three-modules-one-root-object) |
| Object-manager identity and retraction | [2](#2-battle_objman-and-a-naming-retraction-to-know-about) |
| Pooled entity lifecycle and fields | [3](#3-pooled-entity-lifecycle) |
| Character ownership and spawn dispatch | [4](#4-ownership) |
| Projectile manager, elements, and spawning | [5](#5-objshot-the-projectile-layer) |
| Opaque `projectileId` semantics | [6](#6-projectileid-an-opaque-token-do-not-decode-it) |
| Despawn candidates | [7](#7-despawn-identified-candidates-no-promotion-blocker) |
| Open research | [GAPS](#gaps-settle-or-waive-candidates-for-the-spec-wayfinder-epic-spec-tracker item-9) |

---

## 1. Architecture: three modules, one root object

The subsystem spans three source files, recovered from assert-string symbols
([module-map-and-attribution-limits](../research/findings/module-map-and-attribution-limits.md),
Battle-Engine-Map §projectile-entities):

| layer | module | constructor |
|---|---|---|
| generic object pool | arm9 `BattleObj.cpp` | `Battle_ObjManCreate` `0x02083204` |
| object control | ov6 `BattleObjCtrl.cpp` | `Battle_ObjCtrlManCreate` `0x02168B88` |
| projectile specialisation | ov6 `BattleObjShot.cpp` | `Battle_ObjShotManCreate` `0x0216A7BC` |

All three land in the battle root object (`0x170` bytes, global pointer
`0x02172960`), built by `Battle_Add`
([battle-add-root-object-map](../research/findings/battle-add-root-object-map.md)):

| root slot | manager |
|---|---|
| `+0x108` | Battle_ObjMan |
| `+0x10C` | ObjCtrl manager |
| `+0x110` | ObjShot manager |

(ObjCtrl and ObjShot are wired by two Thumb `blx` pairs 14 bytes apart at
`0x0214D818`/`0x0214D826`. `xrefs.json` does not record Thumb `BLX(1)` → ARM
calls, so both constructors show "0 references" while being live —
never read "0 callers" as "dead" in this subsystem
([objshot-manager-and-the-27-kind-dispatch-table §Reachability](../research/findings/objshot-manager-and-the-27-kind-dispatch-table.md)).)

## 2. Battle_ObjMan — and a naming retraction to know about

`Battle_ObjManCreate` `0x02083204` allocates **`0x42D8`** bytes via the tagged
allocator (`__FILE__ = BattleObj.cpp`), holds an 8-byte-stride table at
`+0x24`–`+0x74`, and its singleton global is `0x0214BE14` (all 22 ROM
references live in `BattleObj.cpp`)
([census-literal-sizes-and-seven-hidden-managers](../research/findings/census-literal-sizes-and-seven-hidden-managers.md),
Battle-Engine-Map §projectile-entities 2026-08-15 note).

> **Retraction to cite, not repeat:** P202 named the live object at
> `0x0220DDE0` "Battle_ObjMan". **Wrong — it is `Battle_ColMan`**
> (`0x219C` bytes, `BattleCol.cpp` / `Battle_ColManCreate`, allocated by
> `0x0207AD3C`). The error was mixing up "constructed by a function called
> from `Battle_ObjManCreate`" with "is the ObjMan"
> ([p203-three-managers-colman-retraction](../research/findings/p203-three-managers-colman-retraction.md)).
> Any doc saying "ObjMan" about `0x0220DDE0`, its `+0x48` list, or the
> 19-slot `0x188`-stride array means the ColMan.

Manager list heads (working model, control-flow only — **never confirmed
against a live dump**, Battle-Engine-Map §projectile-entities open questions):
`+0x0C` active, `+0x14` free, `+0x1C` pending/retire.

## 3. Pooled entity lifecycle

Confirmed static, Battle-Engine-Map §projectile-entities claims 1–2:

- **Constructor `0x020834D4`** (reached via thin shim `0x02083624`):
  dereferences the manager global `0x0214BE14`, NULL-checks the free head
  `+0x14`, pops an entity, invokes a caller-supplied ctor callback via
  `blx ip` storing its return at `entity+0x30`, unlinks from free and appends
  to active `+0x0C` (or `+0x1C` on failure).
- The constructor **also wires collision**: at `0x02083560` it calls the
  installer `0x0207C988` and stores the return at `entity+0x10`. There is no
  standalone collision registration
  ([collision-wired-by-the-entity-constructor](../research/findings/collision-wired-by-the-entity-constructor.md)).
- **Destructor `0x02083648`**: sets `entity+0x2C` bit 0 ("marked dead"),
  calls the on-destroy hook, unlinks from active, appends to retire `+0x1C`.
  **30 real call sites** (2 arm9 + 28 ov6) — it is shared pool
  infrastructure, not projectile-specific.

### Entity fields (as known)

| offset | contents | source |
|---|---|---|
| `+0x04` | u16 age counter (per-frame, threshold `0x20` in the despawn candidate) | Battle-Engine-Map claim 5 |
| `+0x10` | the **owner**: a `0x188`-byte ColPrm record — simultaneously the ColObj's owner (ColObj at `owner+0x60`) and the damage pipeline's scratch object. One object, three names. | [entity-0x10-is-the-colobj-owner-and-the-damage-scratch-object](../research/findings/entity-0x10-is-the-colobj-owner-and-the-damage-scratch-object.md) |
| `+0x18` | the `0xA8`-byte NoteTrack (built right after construction) | [character-entity-link-and-a-reversed-setter §3](../research/findings/character-entity-link-and-a-reversed-setter.md) |
| `+0x2C` | bit 0 = marked dead | claim 2 |
| `+0x30` | back-pointer to the character (ctor callback's return) | [character-entity-link](../research/findings/character-entity-link-and-a-reversed-setter.md) |
| `+0x38` | `strb -1` at init; finalizers `0x2083C44`/`0x2083CD8` index a per-category table by it — possible type tag, unexplored | same + Battle-Engine-Map open questions |

## 4. Ownership

All confirmed static
([character-entity-link-and-a-reversed-setter](../research/findings/character-entity-link-and-a-reversed-setter.md),
[allocations-are-tagged-and-the-battle-character-is-0x1F0](../research/findings/allocations-are-tagged-and-the-battle-character-is-0x1F0.md)):

- The ov6 battle character is exactly **`0x1F0` bytes** — attribution from
  the allocator's `__FILE__/__FUNC__/__LINE__` tags, the strongest
  attribution mechanism in the corpus. The arm9 `char+0x56C` HP struct
  belongs to a *different*, arm9-side character object; don't merge the two.
- Bidirectional link, set up synchronously inside `Battle_CharaCreate` via
  callback `0x021570EC`: **`character+0x1A8` = the pooled entity**,
  **`entity+0x30` = the character**.
- **Spawn dispatch** ov6 `0x021574CC`: a 13-way switch on its 3rd argument,
  operating on `char+0x1A4` (hit tally) and `char+0x1A8`; reaches the
  spawn/ownership routine `0x02168CF4`, gated by a one-active-spawn cap on
  `char+0x1AC` (Battle-Engine-Map claim 3).
- **Spawn + ownership** `0x02168CF4` (ObjCtrl module): obtains a wrapper from
  the ov6-local manager (literal `0x02172990`), calls the pool allocator,
  and records ownership on the *wrapper*: `+0x08` new entity, `+0x0C` the
  attacker's MoveInfo pointer, `+0x18` the raw character struct (stored by
  the dispatcher's caller `0x02157720`) (Battle-Engine-Map claim 4).

## 5. ObjShot: the projectile layer

All from
[objshot-manager-and-the-27-kind-dispatch-table](../research/findings/objshot-manager-and-the-27-kind-dispatch-table.md),
CONFIRMED_STATIC, attribution from the constructor's own allocator strings.

### 5.1 Manager (`0x3FD4` bytes, singleton `0x021729EC`)

| offset | contents |
|---|---|
| `+0x00` | active-list head |
| `+0x10` | free-list head |
| `+0x18` | resource/track object from `0x02026F94`, id `0x88000` |
| `+0x1C` | element array: **72 × `0x6C`**, ends `+0x1E7C` |
| `+0x1E7C`… | **`0x2158` bytes unaccounted (54% of the manager)** |

Per-frame entry point `0x0216AF04`, registered via `0x02028384`.
Note these offsets are a *different* struct from the generic pool manager's
`+0x0C`/`+0x14`/`+0x1C` — do not merge.

### 5.2 Shot element (`0x6C` bytes), from initializer `0x0216ACC8`

| offset | width | meaning |
|---|---|---|
| `+0x00` | | link node |
| `+0x08` | word | retained parameter block |
| `+0x10` | word | pointer to a signed byte, decremented when `+0x26 & 8` (ref/slot counter?) |
| `+0x18` | half | lifetime in frames; **default 30** (`0x1E`) when param is zero |
| `+0x1A` | byte | **kind** — the dispatch index |
| `+0x1C` | word | conditional payload (`[r6+0x14]` if `[r6+8] & 1`) |
| `+0x22`/`+0x24` | half | sound-id banks (param byte `0x1D` partitions modes at `0xC8`/`0xDC`) |
| `+0x26` | half | flags; bit 0 set by `0x0216AC10`, bit 3 tested at `0x0216ADF0` |
| `+0x2C` | word | the spawned entity — written by the kind handler; **six kinds (`0x01, 0x05, 0x0E, 0x17, 0x18, 0x19`) carry no entity**, the other 21 do (but see §5.3: for the owner-alias kinds this is an alias of the owner) |

### 5.3 The 27-kind dispatch — confirmed arity

Kind byte `elem+0x1A` indexes a **27-entry function-pointer table at
`0x02172864`** (kinds `0x00`–`0x1A`), **no bounds check** in the caller. The
arity is pinned by data on both sides (table start to the
`"BattleObjShot.cpp"` string at `0x021728D0` = exactly `0x6C` bytes).
`0x0216EEF4` serves four kinds (`0x00/0x0F/0x15/0x16`); `0x0216B4F4` serves
three. Kind names are unknown — nothing in the string pool labels them.
Kind `0x1A`'s handler `0x0216B2A0` is **missing from functions.json** (a
known binning gap). Full handler table in the finding. Tracker item `jus-cvx` queues
a live kind-byte walk.

**Static handler read, CONFIRMED_STATIC** (from
[entity-kind-table-static](../research/findings/entity-kind-table-static.md),
full per-kind table in
RESULTS.md):

- `0x0216EEF4` is **not a stub** — it calls the pooled-entity constructor
  `0x02083624` (§3), stores the result at `elem+0x2C`, and on failure sets
  `elem+0x26` bit 3 (the bit tested at `0x0216ADF0`). Kinds `0x00/0x0F/0x15/0x16`
  are true aliases of one implementation. It is also called directly (not via
  the table) by kind `0x0B`'s handler after an aim/distance precompute.
- `0x0216B4F4` is a 7-instruction (`0x1C`-byte) wrapper over kind `0x02`'s
  own handler `0x0216B514` (kinds `0x01/0x03/0x04`) — not the
  two-instruction shape that only describes kind `0x1A`'s stub.
- `0x0216B514` (kind `0x02`, and reused by `0x01/0x03/0x04` via wrapper
  `0x0216B4F4`, and directly by `0x05/0x0E/0x17/0x19`, duplicated inline by
  `0x18`) does **not** call `0x02083624` at all — it
  stores the *owner pointer* into `elem+0x2C` and separately claims a slot
  in a fixed 9-entry table. For `0x02/0x03/0x04` (not on the six-kind
  no-entity exclusion list, §5.2), the "entity" the rest of the pipeline
  reads back is therefore an alias of the owner object, not a new pool
  allocation — a distinction the six-kind/twenty-one-kind split above does
  not capture on its own.
- No handler writes `elem+0x18` (lifetime) in any of the 27 kinds — the
  lifetime source is always the initializer's default/caller param, never a
  per-kind override.
- No gravity/physics-integration flag was found in any handler read (a
  negative result, not proof of absence — the frame pass `0x0216AF04` could
  apply gravity unconditionally, out of scope here).
- Kind `0x1A`'s handler is a genuine two-instruction no-op
  (`mov r0,#0; bx lr`, `0x0216B2A0`-`0x0216B2A7`); the `functions.json` gap
  is because the *next* bytes belong to an unrelated generic
  lifetime-decrement routine, not to kind `0x1A`'s handler.
- No static call-graph edge was found from any of the 27 handlers to any of
  the three despawn candidates in §7 — despawn runs in the per-frame sweep,
  not the one-shot spawn handler, so this is expected but leaves the
  kind-to-despawn-site mapping open (see GAPS item 2). `0x0216E1C0`'s zero
  callers are explained: it is a vtable slot in a table at `0x0217278C`
  (also holding `0x0216F398`), reached by `blx`, not a Thumb-caller gap. An
  indirect-edge check on the three callbacks the handlers register via
  `0x02028384` found none reaching a despawn site either — full detail in
  RESULTS.md's "Despawn-site tracing" section.

### 5.4 Spawn path `0x0216A944` and the collision interaction

Two arms, selected by a byte at `[[r1+0x10] + slot*32]`:

- **Arm A (multi-target)**: walks a list from `0x0208369C(9)` and filters
  targets by their ColPrm-record fields: skip when target `+0x38 & 0x800`
  (category routing), when `+0x3C & 0xF` overlaps the attacker's nibble,
  when `+0x17C == 0`, or when the attacker's `+0x34` low nibble equals the
  target's. The attacker-vs-target nibble test is a spawn-*selection* filter
  — it drops same-nibble targets outright, which reads as a **team/side
  filter (PLAUSIBLE)**, explicitly *not* an attack-nature system.
- **Arm B (single)**: pops the free head and runs the initializer.

`record+0x17C` was new to the ColPrm map here. On attach, the initializer
stores the shot element into `entity+0x30`, and clears bit `0x200` in the
MoveMan element's flags (`[[entity+0x10]+0x5C]+0x34`) — a sibling of the
known `0x100` snapshot suppressor.

The chain **`entity+0x10 → ColPrm record → record+0x5C → MoveMan element →
element+0x0C position`** is independently re-confirmed by two byte-identical
leaves in this module (`0x0216B3D8`/`0x0216B740`). Collision and damage share
one object: the entity's `+0x10` owner *is* the damage scratch base whose
`+0x40` bit `0x800` gates delta application
([entity-0x10 finding](../research/findings/entity-0x10-is-the-colobj-owner-and-the-damage-scratch-object.md)).

### 5.5 A second element array, anchor + travellers (2026-09-03)

`jus-kakashi-moveset-map-33lu`, [characters/kakashi.md](characters/kakashi.md)
§Specials. Distinct from the ObjShot manager's own `+0x1C` array (§5.1) — this
one sits at **`0x0220C0E8`, stride `0x40` per entry** (`0x0220C0E8 + 0x40·i`),
observed spawning the two elements of Kakashi's 4-koma beam and the three of
his dogs special. Neither special's spawned elements gain a fighter-table
entry, confirming they are elements rather than fighters:

- **Beam**: one anchor element parks next to the attacker 28 frames after the
  input; a second element (the traveller) moves off at ~9.4 px/frame, through
  the victim and past him, and clears before the attacker's recovery ends.
  One anchor, one traveller.
- **Dogs**: an anchor element appears 28 frames in; three traveller elements
  appear together (relative frame 70) and run off on three different arcs
  (one rising, one left, one right). One anchor, three travellers.

**Update 2026-09-25 (capture C1,
RESULTS
§3, §8).** C1 read the ColPrm records behind these specials, and there are
more than this array showed:
- The beam is **18 records**: an emitter that parks 48 px ahead (26 frames
  in) and 17 bolts. The first bolt spawns with the emitter, the other 16
  one every 2.56 frames. Each bolt lands at most one hit.
- The dogs are **5 records**: an anchor that lands nothing and **four** dogs,
  spawned at rel 65, 69, 73 and 77, one hit each.

GDB names each contact's owner record.

The pattern — one stationary anchor plus N travelling hit elements, all in the
same `0x40`-stride array — is a general shape for multi-element specials, not
specific to Kakashi's kit; not yet checked against a second character's
special.

## 6. projectileId — an opaque token. Do not decode it.

Authoring-data field: **sbyte at collision-record offset `0x03`**
(`src/JUS.Tool/Combat/Converters/Binary2Collision.cs:81`). Across all 2837
records: 211 negative (contiguous band −18…−34, nothing in −1…−17),
24 positive, 2602 zero.

Consumer (`jus-chrcol-03-status-lanes-4exo`): `projectileId` is the exporter's label, not the byte's meaning. The hit handler reads it with `ldrsb`
at arm9 `0x0208169C`. A positive value is stored to the struck fighter's work byte `+0x172` (`0x020816D0`) and a negative value to `+0x173`
(`0x02081708`), both as the signed byte; a lane that is already set is replaced only by a lower signed value. The decoder calls it `statusRaw`
(`scripts/analysis/move_records.py`). What the lane value selects is not read here, and the spawn-selector reading below stays unsettled.

What IS confirmed
([projectileid-is-a-selector-not-an-index](../research/findings/projectileid-is-a-selector-not-an-index.md)):

- It attaches to projectile machinery: 92% of negatives sit on
  CollisionType 4 (projectile) / 5 (summon).
- It is **one value per character**, not per record: 92 of 120 characters
  with negatives use exactly one distinct value file-wide.

**Four refuted decodings** — a spec must treat the value as an opaque token:

| hypothesis | verdict | where |
|---|---|---|
| per-character shot-record index (`\|v\|`, `\|v\|-1`) | REFUTED — 2.4% in-bounds | [shot-data-and-projectileid-refuted](../research/archive/findings/shot-data-and-projectileid-refuted.md) |
| biased index `-v-18` into the character's shot file | REFUTED — 28% in-bounds; only 17/184 characters even have 17+ records | [projectileid-is-a-selector-not-an-index §2](../research/findings/projectileid-is-a-selector-not-an-index.md) |
| a global 17-entry table in `ChrBin.aar` | REFUTED — 0 files with 17 records, 4 dirs × 6 strides | same, §1 |
| `chr/col/item.bin` as that table | REFUTED — 43 records; it *consumes* the negative band itself | same, §1 |

Standing hypothesis (**PLAUSIBLE, untested**): a code-side spawn-behaviour
selector dispatched by a switch in ov6 (the 13-way `0x021574CC` shows the
architecture works this way, though 13 ≠ 17). No data-level predictor for
which value a character gets was found.

## 7. Despawn callbacks

Battle-Engine-Map claim 5, **capped PLAUSIBLE**: ov6 `0x0216C958` has four
per-frame kill conditions converging on the destructor `0x02083648` —
(a) a flag/boundary gate; (b) age `entity+0x04` vs 32 frames, suppressible
by `[entity+6] & 0x2`; (c)/(d) a bounded-range check `[0x100, 0x3FF00]` on a
separate field. But two siblings, `0x0216E1C0` and `0x0216F398`, reuse the
identical scaffolding, and all three live inside `BattleObjShot.cpp` — the
static evidence cannot say **which is *the* projectile despawn**. The
mechanics are confirmed.

A live census on the Momotaro forward+Y and Yusuke forward+Y projectiles saw
only `0x0216F398` among the three sibling callbacks. Both objects later used
teardown wrapper `0x0216F99C`, which calls the common destructor at
`0x0216F9C8`. This confirms that callback family for those two projectile
instances, not for all 27 kinds. The same trace found no activity in the known
damage accumulator or fold before Yusuke's projectile disappeared. See
[the runtime finding](../research/findings/momotaro-yusuke-projectile-conflict.md)
and `jus-964r`.

**CONFIRMED_LIVE, kind byte now attached (jus-68cu, 2026-09-12, revised
same day after a Refuter pass on interpretation):** a four-state live probe
([entity-kind-table-static.md §Live](../research/findings/entity-kind-table-static.md#live),
full corpus census in
RESULTS.md "Live")
put a kind byte on the Momotaro/Yusuke-family teardown and found two more
distinct families. Terminology correction carried through below: `0x0216C958`/
`0x0216E1C0`/`0x0216F398` are per-frame update/predicate checks, not
teardown sites — `0x0216F398` is the tail call of updater `0x0216F8D8`,
and `0x0216E1C0` returns 0/1 through five `pop` exits without calling the
destructor. The actual teardown calls are `bl 0x2083648` inside two
52-byte structural-twin wrappers, `0x0216F99C` (kind `0x00`'s path,
callback slot `elem+0x48`) and `0x0216E39C` (kind `0x07`'s path, callback
slot `elem+0x34`).

- **Kind `0x00`** (the shared pooled-entity-spawner handler `0x0216EEF4`,
  §5.3): last update check at `0x0216F398`, teardown through wrapper
  `0x0216F99C` → `0x02083648` (return `0x216f9cc`), reproducing the exact
  path above. Terminal lifetime is exactly `−1` in 39 of the 41 instances
  that reach the lifetime-zero group (1 in the other 2). A second group
  terminates after only 2 update checks with lifetime still ~29-31 —
  **"terminated early, cause not instrumented"** (retracted from
  "hit-driven": no contact evidence in the log, and for
  `pc-vegeta-x-ichigo-x` this directly contradicts that savestate's own
  owner testimony that the projectile passes through with no
  damage/knockback, `jus_files/save_states/INDEX.md:62`).
- **Kind `0x07`** (the gated pooled-entity-spawner handler `0x0216DF50`):
  last update check at `0x0216E1C0`, on a lifetime-zero countdown that
  reaches exactly `−1` in **63 of 63** instances corpus-wide, with a
  corpus-level 63:63 match against `lr=0x216e3cc` destructor fires (a
  corpus count match, not a per-element proof) — confirming the sibling
  update sites are not interchangeable: kinds `0x00` and `0x07` each pair
  with a different wrapper/return-address.
- **Kind `0x0b`** (new): 8 creations, 6 checked 33-34 times at `0x0216F398`
  terminating at lifetime −1 or 0 — the same update/wrapper adjacency as
  kind `0x00`. A **third** kind with a live-confirmed adjacency (3 of 27,
  up from 2 of 27).
- **Kind `0x01`** (owner-aliased family): checked every frame at
  `0x0216C958` with lifetime never observed to move, extending the
  no-`+0x18`-write finding. 5 of 7 instances corpus-wide end with an
  immediately-adjacent `DESTRUCT_FIRE lr=0x216c588` — PLAUSIBLE attribution
  of `0x216c588` to kind `0x01` on that basis (retracted from "never
  despawned," which cherry-picked the 2 of 7 that don't show it).
- Kind `0x12`: 2 creations, both immediately followed by `DESTRUCT_FIRE
  lr=0x216f9cc` with `arg0` equal to the CREATE's own `owner` pointer — an
  owner-matched adjacency. Kind `0x0d`: 31 creations, 15 immediately
  followed by `lr=0x2170040` (an lr-only adjacency, no owner match), 15
  with none; not settled which lr, if any, is `0x0d`'s real path. Both
  corrected from "never observed reaching the destructor" to "no
  destructor fire could be attributed" — fires do occur adjacent to both.
- The other 24 kinds were not exercised live this session; no claim is
  made about them.

Full re-derivation script, corpus counts, and per-item corrections in
RESULTS.md's "Corpus census" subsection. This remains a 2-of-27-kinds-confirmed sample, not a general
  rule.

---

## GAPS — settle-or-waive candidates for the spec (wayfinder epic, spec tracker item `.9`)

1. **projectileId semantics** (highest-value blocker). Settle: search ov6 for
   a ~17-case jump table or a `0x12`/`0x22` bias on a signed byte; or
   breakpoint `0x02168CF4` for a known single-value character. Waive: spec
   it as an opaque per-character token copied verbatim (the 4 refutations
   above justify this).
2. **Despawn coverage — narrowed (jus-68cu, 2026-09-12; revised same day
   after a Refuter pass found the first draft's interpretation, not its
   logs or pointer matches, unsound).** A four-state live kind-byte walk
   (§7 above,
   [entity-kind-table-static.md §Live](../research/findings/entity-kind-table-static.md#live),
   RESULTS.md "Live")
   confirmed the Momotaro/Yusuke-family teardown is **kind `0x00`**: last
   update check at `0x0216F398` (a per-frame predicate/tail-call function,
   not a teardown site itself — teardown is `bl 0x2083648` inside wrapper
   `0x0216F99C`), reaching the shared destructor `0x02083648`. A **second,
   distinct family** was found: kind `0x07`'s last update check is at
   `0x0216E1C0`, teardown through the structural-twin wrapper `0x0216E39C`,
   reaching the shared destructor at a different return address — a
   corpus-level 63:63 match against kind-`0x07` creations, not a per-element
   proof. A **third** kind, `0x0b`, shares kind `0x00`'s exact adjacency (6
   of 8 instances). Kind `0x01` is PLAUSIBLY attributed to a third teardown
   lr (`0x216c588`, 5 of 7 instances) on the same adjacency standard. Kinds
   `0x0d`/`0x12` have destructor fires adjacent to their CREATEs (an
   owner-matched fire for `0x12`, an lr-only one for `0x0d`) but no fire
   could be independently attributed to a specific element of either kind.
   The earlier draft's "hit-driven" label for kind `0x00`'s short-lived
   instances is retracted — no contact evidence exists in the log, and it
   contradicts the owner testimony for `pc-vegeta-x-ichigo-x`
   (`jus_files/save_states/INDEX.md:62`); relabeled "terminated early, cause
   not instrumented." A cause-attribution follow-up should add the known
   contact-mark breakpoints (`0x02080C18`/`0x0207FDAC`). The other 24 kinds
   were not exercised live at all. **This gap is narrowed, not closed**: 3
   of 27 kinds now have a live-confirmed update/teardown adjacency each
   (`0x00`/`0x07`/`0x0b`), 1 more has a PLAUSIBLE one (`0x01`), not a general
   per-kind mapping.
3. **54% of the ObjShot manager (`0x2158` bytes past `+0x1E7C`) unaccounted**;
   nothing addresses the boundary with a literal.
4. **Pool-manager list semantics** (`+0x0C`/`+0x14`/`+0x1C` =
   active/free/retire) — inferred from control flow only, never checked
   against a live dump. Tracker item `jus-45k` queues the root/manager live read.
5. **Q5: persistence across character switch**: settled by
   owner testimony, 2026-09-12 (`jus-atns.3`). Projectiles survive switching once
   the spawning animation has ended; the animation constrains the switch, and
   switching itself does not despawn the projectile. No owner-liveness check was
   found in the despawn candidates, consistent with that testimony. This is not
   a new runtime capture or a measured earliest switch frame. Source:
   [owner clarification](../research/findings/owner-feel-scope-2026-09-12.md).
6. **`record+0x17C`** — gates the multi-target spawn filter; otherwise
   unexplored.
7. **Kind names for the 27 handlers.** Settled statically for
   structure/behavior category (not gameplay names — none exist in the
   string pool) by
   [entity-kind-table-static](../research/findings/entity-kind-table-static.md),
   §5.3 above, and the full table in
   RESULTS.md.
   `0x0216EEF4` and `0x0216B4F4` are now read (real spawn logic and a
   wrapper, respectively); kind `0x1A`'s handler `0x0216B2A0` is confirmed a
   two-instruction no-op, and the `functions.json` gap is explained (the
   next bytes are a different, unrelated function). Still open: the bodies
   of `0x0216B768`, the tail of `0x0216EF7C`, and callees `0x0216F100`/
   `0x0216DD38`/`0x0216DE40`/`0x0216E898`/`0x2170B84`/`0x02028384`/
   `0x020282F4` were not disassembled beyond classifying the caller. Tracker item
   `jus-cvx`. Live confirmation of two kinds' despawn sites (jus-68cu) is
   now folded into item 2 above; it does not add gameplay names.
8. **`entity+0x38`** as a projectile-vs-other type tag (finalizer table
   index) — unexplored.
9. **`entity+0x10` residual tension**: the owner record's `+0x68` is claimed
   "vestigial, no writer" while the damage formula walks `[r4+0x68]` live
   (INVENTORY §2 disputes) — inherited from the collision spec, flagged here
   because the entity carries the object.
10. The 17 negatives on non-projectile CollisionTypes 1/2/3, and the 24
    positive projectileId values — unexplained.
11. **ObjCtrl layer** (`0x02168B88`, `BattleObjCtrl.cpp`) — only the spawn
    routine `0x02168CF4` has been read; the manager itself is unmapped.
