# The AIPM behaviour block — data layout

**Status: the block and record layout are measured; the parameter semantics are
not.** This settles what the CPU-AI behaviour *data* looks like on disk and in RAM,
which three earlier passes got wrong in different ways. It does not yet say what
behaviour id 7 *means*.

**Nothing was patched. No repo file was edited by the measurement. All numbers come
from extracted files and one read-only bridge dump** (`<TMP>/crew-nodedump2/`,
2026-09-27, no writes to guest memory).

Tag convention: **[M]** measured from raw bytes, **[D]** from disassembly,
**[I]** inference, **[X]** open.

---

## 1. The chain to the data [M]/[D]

```
consumer 0x0217C294  ldr r2,[r5,#0x24]      ; r5 = the AI slot, 0x02181C14
consumer 0x0217C29C  ldr r0,[r2]            ; r0 = [[AI+0x24]] = the AI context
consumer 0x0217C2A4  bl 0x2174ebc           ; r0 = ctx, r1 = chosen id
0x02174EF4           mov r0,r6              ; 0x02174EBC forwards its incoming r0
0x02174F00           bl 0x21751cc
0x021751EC (21751cc) ldr r2,[sl,#0xc]       ; r2 = [ctx+0xC] = the block
0x02175200           add r0, r2, sb, lsl #2 ; sb = table[0x02181100 + id]
0x02175204           ldr r1, [r0, #8]       ; u32 at block + 8 + slot*4
0x0217521C           add r4, r2, r1         ; record = block + that offset
```

So `slot = table[id]` and `record = block + u32(block + 8 + slot*4)`.

**`ctx = [[AI+0x24]]`, not `[AI+0x1C]`** — verified at both ends of the path, and
corroborated by the dump (`[AI+0x24] = 0x023A4200`, whose `+0x84/+0x90/+0x9C` are
`0xC4000001`/`0x023A01FF`/`0x0000C100`, matching the independent mask capture).
In the live fixture `ctx = 0x0226076C` and `block = [ctx+0xC] = 0x02260DE0`.

### 1.1 Live end-to-end confirmation, and the two conditional stores [M]/[D]

A read-only live run on 2026-09-27 (`<TMP>/crew-consumer-trace/`, no writes)
confirmed **every link of §1 at once, for the first time**: root `0x021DEA60`,
manager `0x02181A60`, slot 0 -> player battleObj `0x02228E80`, slot 1 -> opponent
`0x0224EF00`; the CPU is slot 1 at base `0x02181C14`; `A = [AI+0x24] = 0x023A4200`,
`ctx = [A] = 0x0226076C`, `block = [ctx+0xC] = 0x02260DE0`, and
`A+0x84/+0x90/+0x9C = 0xC4000001`/`0x023A01FF`/`0x0000C100` exactly as predicted.

The block also matched the corpus signature: `block+0x08` held **18** offsets spaced
exactly `0xBC` apart (`0x64`..`0xCE0`) with slots 18–22 `0xFFFFFFFF`. Six corpus files
share that signature — `bl_b_05`, `bu_b_01`, `hs_b_01`, `oj_b_02`, `op_b_02`, `op_b_03` —
and a byte comparison then resolved it: the live block **is `op_b_03.bin`**, all 3484
decompressed bytes identical, 162 bytes more than the runner-up `op_b_02`. **[M]**

Two consequences. First, the live AI file for this fixture is now *named*, which closes the
provenance hazard that voided the earlier dumps (two runs of this fixture loaded different
characters' files). Second, **slots 10 and 17 of `op_b_03` are empty** (`+0x0C = 0`, all-zero
sub-record), so ids 11 and 18 resolve to no behaviour for this character — which is exactly
what the earlier probe saw when it dispatched id 11 five times and the fighter never
changed state. The fixture is named `...npc-jotaro...`, and `op_b_03` is not a `jj_`
character; fixture names in this repo have lied about the active fighter before.

**`r6 = ctx`, and the id store is on the same object as the block.** `0x02174EBC`
begins `mov r6, r0`, and its caller passes `r0 = [[AI+0x24]]` (`0x0217C29C`). So the
`strbne r5,[r0,#0xc0]` at `0x02174F18` writes `ctx+0xC0+channel`, and the
`ldr r2,[sl,#0xc]` at `0x021751EC` reads the block from the *same* object. **[D]**

**Both of the function's stores are conditional**, which matters for anyone reading
these fields on a single frame:

```asm
02174F04  cmp   r0, #0
02174F10  strne r0, [r1, #0x14]     ; record pointer for channel r4 -- only on success
02174F18  strbne r5, [r0, #0xc0]    ; the id for channel r4        -- only on success
```

`ctx+0x14+4k` and `ctx+0xC0+k` therefore **retain whatever the allocation left until a
resolve succeeds**. Measured on a live frame with no behaviour resolved: `ctx+0xC0` =
**`0xFF`** and `ctx+0x14` = `0`. **[M]** `0xFF` at `ctx+0xC0` is the *unset* value, not
evidence against the mapping — and it is common, because the AI is idle on 434 of the
752 pre-latch frames of the existing probe, in runs of 91–179 frames. Any test of this
field has to sample a distribution, not one frame.

### 1.2 `ctx+0xC0` is the id; `ctx+0x14` is NOT the record [M]/[D]

A 3420-frame read-only capture (`<TMP>/crew-consumer-trace/`, 2026-09-27, 0 dropped,
0 gaps) settled both halves, and one of them corrects the model above.

**`ctx+0xC0` is the live behaviour id.** Over 3420 frames it took a value in 1..23 on
**3132** of them and `0xFF` on 288; histogram `{0xFF: 288, 2: 2776, 5: 9, 6: 347}`; `0`
never appeared. It first went non-zero at fc 33152, the same frame `ctx+0x14` did — the
paired stores, confirmed. **[M]**

**`ctx+0x14` is not the record.** The store puts the *resolver's return value* there, and
`0x021751CC` returns `fp`:

```asm
02175218  add   r4, r2, r1     ; r4 = block + array[slot]  -- the record, but INTERNAL
02175608  mov   r0, fp         ; ...and the function returns fp
```

`ctx+0x14` held `0x02396CC0` on every frame of ids 2, 5 and 6 — constant across an id
change, and **outside the block**. So the primary consistency gate this document's plan
assumed (`ctx+0x14 == block + array[id-1]`) fails on 0 of 3132 frames, and that is a defect
in the model, not in the id field. **[M]/[D]**

**The record is still reachable, statically.** `0x021751CC` calls `0x021733B4(id)`, which
is exactly the table this document's §2 documents — the literal at `0x021733D8` resolves to
`0x02181100`:

```asm
021733C8  ldr   r1, [pc, #8]        ; r1 = 0x02181100
021733CC  ldrsb r0, [r1, r0]        ; slot = (s8)table[id]
```

So `slot = id - 1` is confirmed at the instruction level, and

```
record = block + u32(block + 8 + (id-1)*4)
```

is computable from the id alone, with no live pointer. Since the block for this fixture is
a known corpus file (§1.1), every record for every observed id can be decoded offline.

## 2. The id → slot table [M]

`0x02181100`, 24 signed bytes: `ff 00 01 02 03 ... 16` → `[-1, 0, 1, 2, ..., 22]`.
`id 0` is invalid; **`slot = id - 1`** for ids 1..23.

## 3. The block layout [M]

`block` begins with the ASCII magic **`AIPM`** (`0x4D504941`) and is the per-character
file `chr/ai/<token>.bin`'s payload, decompressed and loaded. Verified: the live
block's first 0x100 bytes equal those of `op_b_03.bin`, and its slots 0..4 match the
run-1 dumps byte-for-byte.

```
+0x00  "AIPM"
+0x04  00 01 FF FE
+0x08  u32 array[23]     ; slot s -> record offset, or 0xFFFFFFFF = absent
+0x64  records, packed back to back, variable size
```

`array[0]` is `0x64` in 262 of 267 files, because the header is exactly `8 + 23*4`
bytes. The **5 exceptions** — `bl_s_25`, `ds_s_21`, `ds_s_22`, `es_s_28`, `es_s_29` —
have slot 0 absent (`array[0] = 0xFFFFFFFF`) and slot 1's record first, at `0x64`. The
code's `[block + 8 + slot*4]` reads this array directly, so `slot` spans 0..22.

**Which ids a file defines** [M], reproducible with
`python3 scripts/analysis/aipm_slot_matrix.py`. Two different questions, two different
numbers:

- **present** — `array[slot]` is a real offset into the block *and* the record's `+0x04`
  reads back the 0-based slot index.
- **populated** — present *and* `+0x0C` ≥ 1, so it carries at least one 32-byte
  sub-record at `+0x9C`. A present-but-unpopulated record is a full `0xBC`-byte record
  whose one sub-record is zeroed (verified byte-for-byte on `bb_s_23.bin` record 0 and
  `dt_b_04.bin` records 0..13).

| slot | id | present | `_b_` / `_s_` | populated | `_b_` / `_s_` |
|---|---|---|---|---|---|
| 0 | 1 | 262 | 74 / 188 | 233 | 73 / 160 |
| 1 | 2 | 258 | 74 / 184 | 240 | 73 / 167 |
| 2–9 | 3–10 | 74 each | 74 / 0 | 72 or 73 each | 72 or 73 / 0 |
| 10 | 11 | 74 | 74 / 0 | **14** | 14 / 0 |
| 11 | 12 | 74 | 74 / 0 | 73 | 73 / 0 |
| 12 | 13 | 55 | 55 / 0 | 54 | 54 / 0 |
| 13 | 14 | 55 | 55 / 0 | 43 | 43 / 0 |
| 14 | 15 | 51 | 51 / 0 | 49 | 49 / 0 |
| 15 | 16 | 51 | 51 / 0 | 41 | 41 / 0 |
| 16 | 17 | 41 | 41 / 0 | 41 | 41 / 0 |
| 17 | 18 | 41 | 41 / 0 | 33 | 33 / 0 |
| 18 | 19 | 16 | 16 / 0 | 15 | 15 / 0 |
| 19 | 20 | 16 | 16 / 0 | 14 | 14 / 0 |
| 20 | 21 | 11 | 11 / 0 | 10 | 10 / 0 |
| 21 | 22 | 11 | 11 / 0 | 11 | 11 / 0 |
| 22 | 23 | **0** | 0 / 0 | 0 | 0 / 0 |

Self-index check (`+0x04 == slot`): **0 mismatches** over 23 slots × 267 files.

The earlier "slot 0 is absent in 34 files" reading came from conflating the two columns.
The correct split is **5 absent** (`array[0] = 0xFFFFFFFF`) and **29 present-but-empty**.
Five files also have slot 1 absent: `db_s_10`, `db_s_11`, `ds_s_03`, `dt_s_01`, `dt_s_02`,
`dt_s_03`, `hk_s_02`, `na_s_02`, `oj_s_01` — note `dt_s_01..03` appear in both lists.

**The suffix is a koma class, not a size.** `b`/`s` is the ROM's own naming — the archives
are `chr/<series>_b_<nn>.aar` (`scripts/analysis/cancel_table.py` matches them) — and the
game separates **Battle koma** (`B#`) from **Support koma** (`S#`) (gamefaqs guide §"Support
Characters"; `docs/research/Passives-Reference.md`). The corpus has 42 series prefixes, 74
`_b_` files and 193 `_s_` files, and **74 is exactly the count of distinct battle
`abilityId` values into `chr_b.bin`**. So the `_b_` files are the game's 74 battle
characters and the `_s_` files are the non-battle komas. [I]

This makes the shape of the two classes exact. `_s_` files define **only** slots 0 and 1 —
never any slot ≥ 2, in 193/193. Populated-slot counts: 144 at {0,1}, 23 at {1}, 16 at {0},
10 at none. A support koma never needs more than the one or two behaviours that carry its
assist action. Every `_b_` file defines slots 0..11 and 12–20 populated slots:
`12→3, 13→14, 14→6, 15→20, 16→6, 17→13, 18→6, 19→2, 20→3` files. One battle character,
`dt_b_04`, is the exception in the other direction: all 14 of its present slots are empty,
so its AI file carries no behaviour at all.

Two facts that constrain naming:

- **Slot 10 (id 11) is present in every battle character but populated in only 14**
  (`bb_b_01`, `bb_b_03`, `bl_b_03`, `bl_b_05`, `dg_b_01`, `ds_b_01`, `ds_b_02`, `hk_b_01`,
  `jj_b_02`, `nn_b_01`, `op_b_04`, `op_b_08`, `yh_b_02`, `yh_b_03`). For the other 60, id 11
  resolves to an empty record.
- **Slot 22 (id 23) is present in no file at all** — the 23rd array entry is always
  `0xFFFFFFFF`. The `[-1, 0, ..., 22]` table in §2 is therefore one entry longer than any
  real behaviour set.

So the vocabulary a battle CPU can actually draw on is ids 1..12, of which ids 1 and 2
(slots 0 and 1) are the pair that even a support koma has. Which characters populate the
rarer slots is listed by `aipm_slot_matrix.py who <slot>`.

## 4. The record layout, and the decisive size test [M]

Across all 267 `chr/ai/*.bin` files (1642 records):

| field | meaning | evidence |
|---|---|---|
| `+0x04` | **0-based slot index** | equals the array index for **1608/1608** valid records |
| `+0x0C` | low byte = **count of 32-byte sub-records** (0..5); high byte = flag | see below |
| `+0x9C` | the 32-byte sub-records, contiguous | record grows by exactly 32 B per count |

**The size test is what settles `+0x0C`.** The record's length is a near-perfect
function of `+0x0C & 0xFF`:

| `+0x0C` low byte | record size |
|---|---|
| 0 or 1 | `0xBC` (188) |
| 2 | `0xDC` (220) = 188 + 32 |
| 3 | `0xFC` (252) = 188 + 64 |
| 4 | `0x11C` (284) = 188 + 96 |
| 5 | `0x13C` (316) = 188 + 128 |

i.e. `size = 0xBC + (count - 1) * 0x20`. The high byte (`0x101`, `0x201`, …) is an
independent flag: it changes no size. `+0x70` is **not** a separate file-level field;
it is record 0's `+0x0C`, because record 0 starts at `+0x64`.

So:
- **`+0x0C` is a count of 32-byte sub-records** — the record literally lengthens by
  32 bytes per increment. The competing "u8 type selector" reading is refuted.
- **The 32-byte sub-records are at `+0x9C`** — consistent with the same arithmetic.

The behaviour id of a record is `record[+0x04] + 1` (slot index + 1).

## 5. The 32-byte sub-record — field table [M] with [I] readings

Decoded over the whole corpus (1,608 valid records, 1,884 sub-records). **All values are
little-endian**: the printed word `ffe20014` is `u16[+0x00] = 0x0014 (20)` and
`u16[+0x02] = 0xFFE2 (−30)` — the *second* field is the negative one.

| sub-offset | width | measured range / property | reading |
|---|---|---|---|
| `+0x00`, `+0x02` | s16 ×2 | −509..2675 and −2680..1071; first positive in 1699, second negative in 1741 | a changing pair — **likely coordinates** [I] |
| `+0x04`, `+0x06` | u16 ×2 | −20..949 and 1..1082 | extents or sizes [I] |
| `+0x08` | u32 | `+0x0A/+0x0B` always zero; across adjacent sub-records within a record it increases by **exactly `0x1000` (432/432)** | an **ordered sequence key** [M] |
| `+0x0C` | s32 | −50..24300; constant within a record | shared parameter [I] |
| `+0x10` | s32 | −50..200; 1712 zero, 114 equal 100; constant within a record | optional modifier [I] |
| `+0x14`, `+0x16` | u16 ×2 | 0..280 and 5..827; **`+0x14 < +0x16` in 1884/1884** | an **ordered (lower, upper) pair** [M] |
| `+0x18`, `+0x19` | u8 ×2 | `+0x18` ∈ `{0,1,2,3,4,5,7}`; `+0x19` ∈ `{0..8,13}` | **`+0x18` partitions by id half** [M] — see below; `+0x19` meaning unknown [X] |
| `+0x1A` | s8 | −34..36; nonzero in 193 | optional signed parameter [X] |
| `+0x1B`, `+0x1C` | u8 ×2 | binary, 23 and 99 ones | flags [X] |
| `+0x1D..+0x1F` | 3 B | zero in all 1,884 | reserved [M] |

**The leading quartet has a consumer, and it is the eligibility gate [M].** `0x02174330`'s first
loop (`0x021747EC`–`0x0217491C`) reads exactly `s16[+0x00/+0x02/+0x04/+0x06]` and forms
`A = s16[0]+s16[4]`, `B = s16[2]-s16[6]`, `C = s16[2]+s16[6]`, buckets each at `0x50`/`0xA0`, and
ORs the behaviour id's bit into one of nine availability words at `+0x84`…`+0xA4`. The `AI+0x48`
pick reads three of those words. So this quartet is not free-form data: it is what decides whether
the id is available to the generic pick. Reproduce with
`python3 scripts/analysis/ai_mask_builder.py <token>`. The `+0x14` field is read too, but by a
*second* loop (`0x0217493C`) that stores a minimum at `+0xC5`; that is a different mechanism.

Two constraints are structural rather than interpretive, and both are exhaustively
verified: the `+0x08` key steps by exactly `0x1000`, and `+0x14 < +0x16` always. Together
they say a sub-record is an **indexed entry with an ordered range**, not an opaque blob.

**`+0x18` is a partition, and it agrees with the code.** Measured over every record with
`count >= 1` in all 74 `_b_` files: ids **1–12** carry `+0x18` ∈ `{2,3}` and ids **13–22**
carry `{4,5}`, with three odd records out of roughly 1,870 (one `0x01` on id 18, one `0x03`
each on ids 15 and 19); `0` marks an empty or near-empty record anywhere. The split otherwise
lands exactly on id 13, which is the boundary the remap at `0x02174ED4` tests
(`cmp r5, #0xd`). So the authored class byte and the dispatch code independently agree on
where the opponent-state family starts. The value within each half (`2` vs `3`, `4` vs `5`)
varies per character and per id and is not yet explained — `+0x18` is a class byte, not a
semantic label. See the taxonomy §2.3; reproduce with
`python3 scripts/analysis/aipm_slot_matrix.py fields`.

The `+0x00/+0x02` pair is the only field that changes between sub-records while
`+0x0C..+0x1C` stay fixed, which is why a spatial reading is tempting: in `ig_s_22.bin`
slot 0 the five pairs run `(53,−41)`, `(183,−115)`, `(314,−189)`, `(444,−262)`,
`(571,−334)`. **But no pixel scale, timing unit, or action meaning is established** — the
sub-record's *semantics* remain the open item, and the units are unknown.

**The rest of the record is not padding.** `+0x10..+0x9B` is nonzero in 291 of 1,608
records, with repeating **12-byte groups** at `+0x28`, `+0x34`, `+0x40`, `+0x4C`, `+0x58`,
`+0x64` (`bc_b_01.bin` slot 15 fills all six). That region is optional parameter data.

## 6. The block is the file byte-for-byte — and two runs loaded *different characters* [M]

The dumped records were matched against all 267 corpus files, slot by slot. The result
**kills an earlier version of this section**:

| live dump | matches |
|---|---|
| `node_00`..`node_04` | **`op_b_03.bin`** slots 0..4 |
| `node_05`..`node_13` | **`jj_b_01.bin`** slots 5..13 |
| `node_14`..`node_17` | nothing (past the payload; misaligned) |

So the two dump runs — `measure.py` at 09:41 and `dump_remaining.py` at 11:33 — loaded
**two different per-character AI files**. The 12–16-byte "differences" that this section
previously read as *runtime mutation* are simply `op_b_03` vs `jj_b_01`. **The
runtime-mutation claim is refuted.** The block is the authored file, unmodified;
cross-run record comparisons are invalid, and any future dump must identify which corpus
file its bytes match before those bytes are trusted.

**Consequence for method.** The fixture did *not* pin one AI file across those two
`state_load`s, so a dump must be tied to its file identity, not just to its address. This
is the same class of error as dumping the wrong object: a plausible-looking byte set from
the wrong source.

## 7. What this settles, and what it does not

- The data route is **open and direct**: the ids are backed by readable, per-id,
  per-character records, and the record layout is measured and multiply confirmed.
- `block = [ctx+0xC]` where `ctx = [[AI+0x24]]`; the block carries the `AIPM` magic and
  is the authored file, unmodified.
- Record offsets, the id→slot map, `+0x04`, `+0x0C`, `+0x9C`, and the sub-record field
  table are **[M]**.
- Which slots exist is **[M]** across the whole corpus (§3): the 74 `_b_` battle komas all
  define ids 1..12, the 193 `_s_` support komas define only ids 1 and 2, and id 23 is
  defined nowhere.

**Refuted in this document (each by raw bytes, not argument):** the `[AI+0x1C]` route;
`+0x0C` as a "type selector"; "`array[0]` is always `0x64`"; "most characters define
14–23 slots"; "the records are mutated in RAM at runtime"; "`+0x70` is a file-level
count"; and the "offsets[23] at `block+8` is not an array" reading.

### The incoming id is not always the selected id [D]

`0x02174ED4`–`0x02174EF0`, before the resolver is called:

```
02174ED4  cmp  r5, #0xd          ; r5 = incoming id
02174ED8  blt  0x2174ef4
02174EDC  sub  r0, r5, #0xd
02174EE0  cmp  r0, #1            ; r5 in {13, 14}
02174EE4  ldrls r0, [r6, #4]
02174EE8  ldrsbls r0, [r0, #8]   ; a signed byte off ctx
02174EEC  subls r0, r0, #3
02174EF0  addls r5, r5, r0, lsl #1
```

So ids **13 and 14 are rewritten** by a signed byte found off the context before the
record is looked up. An incoming id therefore need not be the record id, which matters
for any future trace that pairs ids with observed behaviour.

### No behaviour *names* are derivable from this corpus alone [X]

The corpus gives ordinal ids and parameters. It does not name intents. The only
defensible label it supports is the code-anchored one: **id 12 → the phase-8 branch**
(`+0x3A == 0xC`). Naming the rest needs a **read-only consumer trace** that pairs the
sub-record field values with the choices actually made, which is the next measurement
and needs the emulator slot.
