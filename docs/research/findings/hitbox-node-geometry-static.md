# Findings: where the live hitbox/hurtbox rectangle is read by the overlap test (static)

Static only (no emulator this pass — disassembly re-verified against ROM bytes with
`scripts/analysis/disasm_range.py`). Tracker item: `jus-atns.4.1`. Grade: **PLAUSIBLE** (geometry
shape and fixed-point extraction confirmed by direct disassembly; the fixed-point *scale*
and facing handling are inferred, not measured live — see Conditions/Open items below).

## 0. Live correction (2026-09-12, Debugger, one launch, 120 operand hits)

The operand `A = [list-node+0x08]` at `0x0207B824` is **not** `record+0x60`.
`record+0x60` is a **0x40-byte ColObj wrapper** (allocated by `0x0207AEDC`,
owner at `+0x18`, list head/tail of geometry elements at `+0x08`/`+0x0C`, pair
list at `+0x10`). The rectangle lives on **0x64-byte geometry elements**
(allocated by `0x0207B11C`, appended to `[wrapper+0x08]`, linked at `+0x00`):
`+0x08` owner (= `wrapper+0x18`), `+0x0C` u16 live sub-element count (0 or 1
seen; the active gate), `+0x0E` u16 id, `+0x18` flags (bit `0x80` tested by the
overlap test), `+0x20` back-pointer to the wrapper, `+0x2C/+0x2E` s16 centre
offset, `+0x30/+0x32` s16 half-extent, subs at `+0x3C + j*8`. Teardown
`0x0207B000` frees elements with size `0x64` and the wrapper with `0x40`. Live:
`A` was inside `[[A+0x20]+0x08]` on 120/120 hits; the wrapper of record 11
(Kakashi) held one element whose position `+0x0C` of the getter block equals
Kakashi's physics x ×16 on every walk frame (161610 → 151950, LEFT frames
1552–1577), rect `[-2,-20]/[10,20]` px. Up+B: input frame 1578, record 13
appears at 1588 with two elements, id 0 (body) and id 263, whose count is 1
from frame 1595 to 1601 (7 active frames) while its position travels. Rects
are integer pixels; `eo/he` stay stale after count drops to 0. Sections 2–3
below read correctly for the *element*; wherever they say "ColObj+0x2c" read
"element+0x2c". Grade for the geometry object identity: **MEASURED** (this
state, Kakashi vs Jotaro, one pass). Not seen: 3+ elements per wrapper; whether
flags bit `0x04` or the count is the better active gate.

## 1. The question

`jus-atns.4.1` asks: for a live hitbox/hurtbox node, where is its rectangle (x/y extents,
units, origin, facing) read by the overlap test that feeds the pair list docs/confirmed-
facts/collision.md describes downstream (the 22-bucket ColPrm pipeline, `0x0207F480` /
`0x020823E4`)?

That downstream pipeline does **not** do geometry. Disassembling `0x020823E4` (the
narrowphase pair test collision.md calls "the damage formula") and its caller `0x02080F14`
shows both operate purely on **class-bit routing and per-hit flag/accumulator state**
(node `+0x14` class bits, node `+0x18`/`+0x20` flag words, object `+0x40`/`+0x44`/`+0x64`
flags) — never a rectangle field, and no arithmetic shaped like an interval test. By the
time a pair reaches this layer, "do these two things overlap" has already been decided
upstream. The actual geometric test is one module up: **ColMan** (`BattleCol.cpp`,
ctor `Battle_ColManCreate 0x0207AD3C`), the layer collision.md §1/GAP G2 lists as
"untouched." This doc opens that layer far enough to answer the rectangle question, without
claiming the rest of ColMan is mapped.

## 2. Where the rectangle lives: the ColObj's own extent fields

Prior static work (`jus-z87k`/`jus-pb6n`,
[pair-entry-creation-site-static.md](pair-entry-creation-site-static.md)) already located
and disassembled the overlap test as part of tracing who creates ColPrm pair-list nodes; this
doc re-verifies that disassembly byte-for-byte (`0x0207B7F0`–`0x0207B8FC` below matches its
transcript) and adds the position-getter's own disassembly (`0x0207AFDC`, not shown there)
plus the facing question that finding left open.

**The overlap test function: `0x0207B7F0`** (728 bytes, one caller `0x0207B3EC`, itself
reached only through a registered per-frame callback slot on the ColMan manager — see
§5 there). Nested double loop over the manager's active-ColObj list; for each `(A, B)` pair:

```
0x0207B824  ldr r4, [r6, #8]        ; A = list-node+0x08  (a ColPrm-owned ColObj, collision.md "record+0x60")
0x0207B828  add r1, sp, #0x1c
0x0207B82C  ldr r0, [r4, #8]        ; A+0x08
0x0207B830  bl  0x207afdc           ; -> sp+0x1c = {A.x, A.y, A.z}  (three words)
...
0x0207B85C  add r1, sp, #0x10
0x0207B860  bl  0x207afdc           ; -> sp+0x10 = {B.x, B.y, B.z}
```

`0x0207AFDC` (the position getter, disassembled this pass, bytes confirmed):

```
0x0207AFDC  ldr r0, [r0, #4]        ; arg is (A+8); deref +4
0x0207AFE0  ldr r2, [r0, #0x50]     ; *( *(A+8)+4 ) + 0x50  -- the owning record's position block
0x0207AFE4  ldr r0, [r2, #0xc]      ; x
0x0207AFE8  str r0, [r1]
0x0207AFEC  ldr r0, [r2, #0x10]     ; y
0x0207AFF0  str r0, [r1, #4]
0x0207AFF4  ldr r0, [r2, #0x14]     ; z
0x0207AFF8  str r0, [r1, #8]
0x0207AFFC  bx  lr
```

So each ColObj's world position is **not stored on the ColObj itself** — it is fetched
every call from `*( *(ColObj+0x08+4) ) + 0x50`, i.e. `+0xC/+0x10/+0x14` off a position block
owned by whatever `ColObj+0x08` points at (plausibly the owning fighter/effect element;
not independently confirmed this pass — see Open items). All three words are full 32-bit
loads (`ldr`, not `ldrh`/`ldrsh`), consistent with the `s32` 8.8 world-position fields
`physics.md` §5/§6.1 already documents for the fighter element, though this pass did not
cross-check the exact `+0xC` offset against that element's known layout — flagged
`[unverified]` below.

**The axis-0 (x) overlap test**, disassembled and confirmed against ROM bytes:

```
0x0207B864  ldr   r1, [sp, #0x1c]        ; r1 = A.x (raw world position, full precision)
0x0207B868  ldrsh r3, [r4, #0x2c]        ; r3 = A's ColObj+0x2c, s16 "extent-offset" field, axis 0
0x0207B86C  asr   r0, r1, #0xb
0x0207B870  add   r0, r1, r0, lsr #20    ; r0 = r1 + (unsigned round toward 0 on negatives)
0x0207B874  lsl   r0, r0, #4
0x0207B87C  add   r3, r3, r0, asr #16    ; r3 = A.center_x = A.extentOffset_x + scale(A.x)
0x0207B878  ldr   r1, [sp, #0x10]        ; r1 = B.x
0x0207B880  asr   r0, r1, #0xb
0x0207B884  add   r0, r1, r0, lsr #20
0x0207B888  ldrsh r2, [r5, #0x2c]        ; B's ColObj+0x2c
0x0207B88C  lsl   r0, r0, #4
0x0207B890  ldrsh r1, [r4, #0x30]        ; A's ColObj+0x30, s16 half-extent, axis 0
0x0207B894  add   r0, r2, r0, asr #16    ; r0 = B.center_x
0x0207B898  subs  r2, r3, r0             ; r2 = A.center_x - B.center_x
0x0207B89C  ldrsh r0, [r5, #0x30]        ; B's ColObj+0x30
0x0207B8A0  rsbmi r2, r2, #0             ; r2 = |delta_x|
0x0207B8A4  add   r0, r1, r0             ; r0 = halfExtent_x(A) + halfExtent_x(B)
0x0207B8A8  cmp   r2, r0
0x0207B8AC  bgt   0x207ba90             ; |delta_x| > sum-of-half-extents  -> no overlap, skip pair
```

**Axis-1 (y)** repeats the identical shape at `0x0207B8B0`–`0x0207B8F8`, using fields
`ColObj+0x2e` (extent-offset, axis 1) and `ColObj+0x32` (half-extent, axis 1), and the y
words at `sp+0x20`/`sp+0x14` (the third position-getter output, `+8`/z, is never read by
this function — loaded and discarded, or consumed elsewhere; not traced this pass).

**Classic separating-axis / AABB test, two axes:**

```
overlap  <=>  |centerA_axis - centerB_axis| <= halfExtentA_axis + halfExtentB_axis   (both axes)
centerX_axis = ColObj.extentOffset_axis (s16, +0x2c/+0x2e) + scale(ColObj's owning position, axis)
```

The `scale()` op (`asr r,#0xb` then `+lsr(.,20)` then `lsl #4` then, at the add site,
`asr #16` on the sum) is a fixed-point conversion from the raw position word's scale into
the same fixed-point domain as the s16 extent fields — a rounding right-shift by roughly
11 bits net, folded into the add. The exact bit-width of the resulting "world unit" was not
independently pinned down this pass (see Open items); it is presented here as the shift
sequence, not as a named unit.

## 3. The finer sub-element loop (per-hitbox rectangles, not just per-object)

If both axes pass (the whole-ColObj AABB overlaps), execution falls into a second nested
loop, `0x0207B90C`–`0x0207BA3C`:

- Outer loop bound: a halfword count read off `A+0xC`. Inner loop bound: the same off
  `B+0xC`.
- Per iteration, indexes a sub-element array at `A+0x3C + i*8` (and `B+0x3C + j*8`):
  - `+0x0`/`+0x2`: per-axis **center-offset** halfwords (x, y) — same role as
    `ColObj+0x2c`/`+0x2e` above, but per sub-box rather than per whole object.
  - `+0x4`/`+0x6`: per-axis **half-extent** halfwords (x, y) — same role as
    `ColObj+0x30`/`+0x32`.
- Runs the identical `|delta| > sum-of-half-extents` inequality per axis, per sub-element
  pair, using the *same* whole-object world position from `0x0207AFDC` (the sub-element
  offsets are added on top of the object-level center, not re-fetched from RAM).

This is the actual per-hitbox/per-hurtbox rectangle: **origin = the owning object's world
position (from `0x0207AFDC`, off the position block at `owningPos+0x50`), offset by a
per-sub-element `(centerOffsetX, centerOffsetY)` in the ColObj's local fixed-point frame,
extent = `(halfWidth, halfHeight)` — i.e. an axis-aligned rectangle stored as
center-offset + half-extent, not as min/max corners.**

Every sub-element pair that survives both axis tests, and every whole-object pair that
passes the outer test (whether or not any sub-element matched), calls the ColPrm pair-node
creator `0x0207ACB8` and tags `node+0x10` = `2` (sub-element-level match) or `6`
(object-level, no sub-element identified) respectively — this is the hand-off into the
pair list `docs/confirmed-facts/collision.md` §5/§7 and
[pair-entry-creation-site-static.md](pair-entry-creation-site-static.md) §4–7 already
document; this doc does not re-derive that part.

## 4. Facing

**Not found in this function.** `0x0207B7F0`'s two loops never read a facing/mirror flag,
never branch on sign of a position delta beyond the `rsbmi` absolute-value idiom, and never
negate a sub-element's `centerOffsetX` conditionally. Two readings are consistent with that
absence, neither confirmed this pass:

1. Facing is baked into the s16 extent-offset fields (`ColObj+0x2c`/`+0x2e`, and the
   sub-element `+0x0`/`+0x2` halfwords) themselves, i.e. something upstream of this test
   (plausibly the per-frame rebuild the ticket brief flags at "`M+0x78` flags rebuilt per
   frame") already flips the sign of `centerOffsetX` when the owning fighter faces left,
   so the AABB test itself never needs to know facing.
2. Facing does not affect hitbox extents at all in this engine (symmetric boxes only), and
   what looks like "facing-dependent range" in move data (kakashi.md's side B/side Y range
   notes) comes entirely from the fighter's world-position offset, not from a mirrored box.

`[unverified]` — settling this needs either a live diff of a sub-element's `+0x0` byte
between a left-facing and right-facing capture of the same move, or a static trace of who
writes `ColObj+0x2c`/`+0x2e` per frame. Not attempted this pass (static-only, per the ticket
scope for step 1; step 2's GDB probe below logs facing alongside node fields, which gives a
live cross-check for a future pass without committing to an interpretation now).

## 5. Conditions

| item | value |
|---|---|
| method | static disassembly, `scripts/analysis/disasm_range.py` against the checked-in ROM; no emulator session this step |
| functions read | `0x020823E4` (145 instr, narrowphase/damage — confirmed non-geometric), `0x02080F14` (bucket walker, confirmed non-geometric), `0x0207FBD0` (ColObj pair-list reader, confirmed structural-only), `0x0207B7F0` (overlap test, this doc), `0x0207AFDC` (position getter, this doc) |
| prior art relied on | [pair-entry-creation-site-static.md](pair-entry-creation-site-static.md) (`jus-z87k`/`jus-pb6n`) for the pair-node creator/unlinker and the call chain into `0x0207B7F0`; this doc independently re-verified its `0x0207B7F0` transcript against ROM bytes and did not find any discrepancy |
| grade | PLAUSIBLE — instruction-level disassembly confirms the AABB shape and field offsets; the fixed-point scale factor and facing handling are inferred, marked `[unverified]` |

## 6. Answer, summarized

| question | answer | confidence |
|---|---|---|
| Where is a node's rectangle read? | `0x0207B7F0`, both the whole-ColObj test (`ColObj+0x2c/+0x2e` offset, `+0x30/+0x32` half-extent) and the per-sub-element test (`+0x3c + i*8`, `+0x0/+0x2` offset, `+0x4/+0x6` half-extent) | CONFIRMED_STATIC (disassembly) |
| Units | s16 halfwords in the ColObj's local fixed-point frame; world position is full-precision `s32` off `*( *(ColObj+8)+4 )+0x50` (`+0xC/+0x10/+0x14` = x/y/z), converted into that frame by a ~11-bit rounding right-shift folded into the add | PLAUSIBLE (shift sequence confirmed; exact bit-width/named unit not cross-checked against a known px scale) |
| Origin | the owning object's live world position (fetched fresh every call, not cached on the ColObj), plus a per-object or per-sub-element center offset — **not** a fixed local origin, and **not** min/max corners | CONFIRMED_STATIC |
| Facing | not read by this test | unverified whether it's pre-baked upstream or genuinely absent — see §4 |

## Next angles, ranked

1. Live GDB diff of a sub-element's offset fields between a left-facing and right-facing
   capture of the same attack, to settle §4.
2. Trace who writes `ColObj+0x2c`/`+0x2e`/`+0x30`/`+0x32` per frame (this pass only
   confirmed they are *read* here) — likely inside the per-frame ColObj refresh
   `0x0207B414` this same registered callback calls just before `0x0207B7F0`.
3. Confirm the `*( *(ColObj+8)+4 )+0x50` position block against a known fighter-element
   address (e.g. Kakashi's `0x0220C068` from kakashi.md's Conditions block) in a live
   session, to pin the exact px scale.
