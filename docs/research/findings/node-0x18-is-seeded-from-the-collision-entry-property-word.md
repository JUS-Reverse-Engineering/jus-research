# Findings: node `+0x18` is seeded from the collision entry's `+0x08` property word via table `T18`, not from `record+0x38`

> **Superseded labels (E0 roster pin, 2026-10-18):** the per-character table's file labels follow the 2026-09 mapping; Vegeta is db_b_03 (db_b_04 is Vegeta (SSJ)), Eve bc_b_01, Kakashi na_b_04, Momotaro oj_b_02. Current pairing: `docs/research/feel-captures/2026-10-18-e0-roster/roster_reconciled.json`. Kept as recorded.

Static. Tracker item `jus-2s9k`. Answers `jus-jv9d`. Extends `jus-hitbox-priority-clash-1evz.1`.

## 1. The question

`docs/research/findings/momotaro-yusuke-projectile-conflict.md` traced a live capture where a
projectile node's `+0x18` bit 0 read `1` on Yusuke's record and `0` on Momotaro's, and that
difference was the only gate term that split the two projectiles at `0x02080BE0`-`0x02080C1C`.
That doc inferred the bit came from `record+0x38` (the category bitmask, `record-0x38-is-a-
category-bitmask.md`), because the allocator is known to copy `record+0x38` into the node at
allocation time.

A census of 22 in-use, non-fighter ColPrm records across 12 states read `record+0x38 == 0` on
**every one** (`docs/research/feel-captures/projectile-census-2026-09-10/SUMMARY.md`, the
"in-use non-fighter records" table — the `+0x38` column is `0x00000000` in all 22 rows). So the
inference that `record+0x38` explains a live `node+0x18` bit 0 of `1` is wrong at read time: the
seed alone cannot produce that bit, because `record+0x38` never carries it in practice.

## 2. Writers of node `+0x18`

All the writers that touch this node live in the allocator `0x0207D440` (the record allocator
whose literal address is stored at the sub-object's `+0x1C` and dispatched from the installer at
`0x0207B198`), plus a documented flag API family that merges caller-supplied bits.

### 2.1 The allocator's own prologue and the seed

```
0x0207D440: push {r3, r4, r5, r6, r7, lr}
0x0207D444: mov r6, r1
0x0207D448: cmp r0, #0
0x0207D44C: cmpne r6, #0
0x0207D450: moveq r0, #0
0x0207D454: popeq {r3, r4, r5, r6, r7, pc}
0x0207D458: ldr r4, [r0, #0x28]          ; r4 = *(arg0 + 0x28)
0x0207D45C: cmp r4, #0
0x0207D460: moveq r0, #0
0x0207D464: popeq {r3, r4, r5, r6, r7, pc}
0x0207D468: ldr r0, [pc, #0x3c8]         ; = &0x0214BE10 (ColPrm manager singleton pointer)
0x0207D46C: ldr r0, [r0]
0x0207D470: ldr r5, [r0, #0x18]          ; r5 = manager's free-node-list head
0x0207D474: cmp r5, #0
0x0207D478: moveq r0, #0
0x0207D47C: popeq {r3, r4, r5, r6, r7, pc}
0x0207D480: mov r1, r5
0x0207D484: add r0, r0, #0x18
0x0207D488: bl 0x2037c24                 ; unlink(manager+0x18, r5)
0x0207D48C: mov r1, r5
0x0207D490: add r0, r4, #8
0x0207D494: bl 0x2037b98                 ; link(r4+8, r5)
0x0207D498: ldr r0, [r4, #0x34]
0x0207D49C: str r0, [r5, #0x14]
0x0207D4A0: ldr r0, [r4, #0x38]
0x0207D4A4: str r0, [r5, #0x18]          ; seed: node+0x18 = record+0x38
```

`r4 = *(arg0 + 0x28)` is not the function's raw `arg0` — `arg0` is a sub-object, and `r4` is
recovered from its backpointer. Traced to the installer at `0x0207C988`:

```
0x0207CA1C: ldr r1, [pc, #0x120]          ; r1 = 0x0207D440 literal (this very allocator's address)
0x0207CA20: str r0, [r4, #0x60]           ; record+0x60 = sub-object (r0 = result of bl 0x207aedc)
0x0207CA24: str r1, [r0, #0x1c]           ; sub-object+0x1c = &0x0207D440
0x0207CA48: ldr r1, [r4, #0x60]
0x0207CA50: str r4, [r1, #0x28]           ; sub-object+0x28 = r4  <-- the record, this is the backpointer
0x0207CA64: str r7, [r4, #0x34]           ; record+0x34 = r7  (installer's own first write)
0x0207CA6C: str r6, [r4, #0x38]           ; record+0x38 = r6  (installer's own first write)
```

At install time `r4` is the ColPrm record itself; the sub-object at `record+0x60` gets vtable
slot `+0x1c = &0x0207D440` and backpointer `+0x28 = record`. So when the vtable slot is later
called with the sub-object as `arg0`, `0x0207D440`'s `r4 = [arg0+0x28]` recovers the record, and
`[r4,#0x38]` at `0x0207D4A0` genuinely is `record+0x38`. This one-hop chain confirms the seed —
but the seed alone cannot explain the live observation, because the census shows `record+0x38`
is `0` on every in-use record.

### 2.2 The id branch, right after the seed, in the same function

```
0x0207D444: mov r6, r1                    ; r6 = arg1 (ColWork, per-instance runtime work struct)
0x0207D4A8: ldrh r3, [r6, #0xe]           ; r3 = hitbox id, copied at animation time from the
                                           ;   ALMT CollisionTypeN keyframe track
0x0207D4AC: cmp r3, #0x100
0x0207D4B0: blo #0x207d570                ; id < 0x100 branch
```

`r6+0x0E` is a 16-bit hitbox id on the runtime `ColWork` object (`docs/confirmed-facts/
collision.md` §G1) — **not** a copy of the on-disk collision record's own `+0x0E` byte
(`DamageFlags` per `Binary2Collision.cs`); the two share an offset by coincidence, on different
structs.

**Path id < 0x100** — the 14-entry built-in table, stride `0x14`, at `0x0209FC2C`:

```
0x0207D57C: str r0, [r5, #0x10]           ; r5+0x10 = &built-in-table[r3]   (id < 0x100)
```

and, in the same branch, writer #1 ORs `tableB@0x0209FBBC[id]` into node `+0x18` with **no
bounds check**:

```
0x0207D5A8: ldr r0, [r5, #0x18]
            ldr r1, tableB[r3]            ; tableB @ 0x0209FBBC, r3 = [r6,#0xe] & 0xffff
            orr r0, r0, r1
            str r0, [r5, #0x18]           ; node+0x18 |= tableB[r3]   <-- writer #1
```

**Path id >= 0x100** — the character's own `chr/col` array (`docs/confirmed-facts/collision.md`
§4):

```
entry = [[record+0x6C]+0x0C] + 0x14*(id-0x100)
0x0207D4D4: str r0, [r5, #0x10]           ; r5+0x10 = &character-array[id-0x100]
```

Writer #1 (`tableB`) does not run on this path — the id branch that fires it requires
`id < 0x100`, and every authored per-character hitbox id is `0x100 + array index` (§G1).

Both paths converge on `r5+0x10 = entry` (the resolved 20-byte collision-entry pointer, `r5` =
the node just allocated). Then, further down the same function, the 32-iteration loop reads the
entry's own `+0x08` property word and OR's a per-bit table into node `+0x18`:

```
0x0207D684: ldr r7, [r5, #0x10]           ; r7 = entry pointer
0x0207D688: ldr r7, [r7, #8]              ; r7 = *(entry+0x08)  <- the property word
0x0207D68C: tst r7, r1, lsl r2            ; test bit r2 (r2 = 0..0x1f)
0x0207D6AC: ldr ip, [r7', #0x80]          ; T18[r2]  (r7' = &T14[r2], T18 = T14+0x80 = 0x0209FDC4)
0x0207D6B4: str ip, [r5, #0x18]           ; node+0x18 |= T18[r2]   <-- writer #2
```

This loop runs for each set bit `b` of `*(entry+0x08)` (bytes `0x08`-`0x0B` of the 20-byte
on-disk record, treated as one combined 32-bit bitmask per `contact-array-semantics-settled.md`
§4 and `collision.md` §G1), OR'ing `T18[b]` into node `+0x18` on every set bit.

### 2.3 The flag API family

Four more writers merge a caller-supplied bitmask into whichever node is current in the list
walk from `record+0x08`:

- `0x0207D064`/`0x0207D098` — OR: `[ip,#0x18] |= r2`
- `0x0207D0BC`/`0x0207D0F8` — AND/clear: `[r3,#0x18] &= ~r2`
- `0x0207CF18`/`0x0207CF54` — gated OR, only when the node's own `+0x14` already has bit
  `0x20000000` set
- `0x0207CF78`/`0x0207CFBC` — gated AND, only when the node's own `+0x14`/`+0x18` already has bit
  `0x60000000` set

No matching word `str [..,#0x18]` writer was found in ov6 in the searched range
(`0x02158000`-`0x02172000`); every candidate there is either a plain overwrite with no
`ldr;orr;str` merge pattern, or a differently-shaped struct's field at the same offset.

## 3. Tables read from `jus_files/arm9/arm9.bin`

`tableB @ 0x0209FBBC`, 14 word entries (bounded by the next table at `0x0209FBF4`):

```
idx:   0  1  2  3  4  5  6  7  8  9 10 11 12 13
val: 0  0  0  0  1  0  0  0  0  0  0  0  0  0
```

Only index 4 has bit 0 set.

`T18 @ 0x0209FDC4` (= `0x0209FD44 + 0x80`, the "per-bit" table addressed via `T14+0x80`), 32
entries, indexed by bit position of the entry's `+0x08` word:

```
idx: 0..4  -> 0
idx: 5     -> 0x00000001   <-- only entry with bit 0 set
idx: 6     -> 0x00000008
idx: 7     -> 0x00000010
idx: 8     -> 0x00000002
idx: 9     -> 0x00000004
idx: 10    -> 0x00000040
idx: 11    -> 0x00000080
idx: 13    -> 0x00000200
idx: 17    -> 0x00000400
idx: 18    -> 0x00001000
idx: 19    -> 0x00002000
idx: 20    -> 0x00010000
idx: 21    -> 0x00020000
idx: 22    -> 0x00040000
idx: 12,14,15,16,23-31 -> 0
```

**Consequence.** For authored per-character entries (whose hitbox id is always `>= 0x100`,
so writer #1/`tableB` never fires): node `+0x18` bit 0 = 1 iff `entry+0x08 & 0x20` (bit 5) is
set — only `T18` index 5 carries bit 0. For built-in ids (`< 0x100`), only id 4 yields bit 0 via
`tableB[4] == 1`.

## 4. Per-character prediction

Predicted node `+0x18` = OR over set bits `b` of `entry+0x08` of `T18[b]` (the `record+0x38`
seed contribution assumed 0, per the census in §1). Full per-record dumps for all ten characters
were captured during this pass; this table summarizes them:

| character | file | total entries | type-4/5 entries | type-4/5 with `+0x08` bit 5 | ALL entries with bit 5 |
|---|---|---:|---:|---:|---:|
| Ichigo | bl_b_01 | 20 | 4 | 0 | 4 |
| Hitsugaya | bl_b_05 | 24 | 7 | 1 | 1 |
| Vegeta | db_b_04 | 20 | 7 | 3 | 4 |
| Yugi | yo_b_01 | 28 | 9 | 3 | 5 |
| Eve | bc_b_02 | 20 | 4 | 2 | 12 |
| Taikoubou | hs_b_01 | 39 | 23 | 1 | 3 |
| Kakashi | na_b_05 | 26 | 10 | 0 | 0 |
| Mashirito | ds_b_02 | 33 | 17 | 4 | 7 |
| Momotaro | oj_b_01 | 22 | 3 | **0** | 2 |
| Yusuke | yh_b_01 | 32 | 15 | **6** | 14 |

Correction: the "type-4/5 entries" columns undercount, because the entry a live record actually
resolves to is not restricted to type 4/5 — see the "Resolved (2026-09-11)" paragraph below for
the case this filter miscounted (Ichigo).

Yusuke's 6 type-4/5 entries predicting node `+0x18` bit 0 = 1, against Momotaro's 0, matches the
live pair the owner measured (Yusuke bit 0 = 1, Momotaro bit 0 = 0) — this is a concrete
mechanism consistent with that observation.

**Resolved (2026-09-11):** the read-time join in
`docs/research/feel-captures/projectile-census-2026-09-10/ENTRIES.md` resolved the actual
collision entry pointer for every node on every in-use non-fighter record across all 12 census
states (28 nodes), instead of scanning a character's whole authored table by type. For Ichigo's
forward Y projectile (`pc-ichigo-fy-vegeta` rec 115 and `pc-hitsugaya-airy-npc-ichigo-fy` rec 20),
the node resolves to id 264 (`0x108`), entry index 8 in `jus_files/chrbin/chr/col/bl_b_01.bin`,
bytes `02 02 00 00 0F 00 00 00 20 00 00 00 0F 04 0A 15 01 00 00 00` — type 2, `entry+0x08 = 0x20`
(bit 5 set), matching the observed node `+0x18` bit 0 = 1. The type-4/5 filter used to build the
per-character table above only counts entries of those two types, so it missed this type-2 entry
and undercounted Ichigo's bit-5 entries as 0 in that column (the "ALL entries with bit 5" column
already showed 4, which included it). All 28 resolved nodes across the 12 states matched their
predicted bit, 0 mismatches, 0 unresolved pointers — see `ENTRIES.md` for the full per-node table
and conditions.

## 5. The `+0x150` chain

The API at `0x0207D064` does:

```
ldr r3,[r0,#0x34]; orr r3,r3,r1; str r3,[r0,#0x34]
ldr r3,[r0,#0x38]; orr r3,r3,r2; str r3,[r0,#0x38]
ldr ip,[r0,#8]                       ; first node on record+0x08 list
loop: ldr r0,[ip,#0x14]; orr r0,r0,r1; str r0,[ip,#0x14]
      ldr r0,[ip,#0x18]; orr r0,r0,r2; str r0,[ip,#0x18]
      ldr r3,[ip,#8]; ldr r0,[r3,#0x10]; orr r0,r0,r1; str r0,[r3,#0x10]
      ldr ip,[ip]; cmp ip,#0; bne loop
```

`record+0x34 |= r1`, `record+0x38 |= r2`, mirrored into every node on `record+0x08`
(node `+0x14`/`+0x18` get the same merge, and each node's child `+0x10` gets `r1` merged too).

ov6 `0x02165F9C`-`0x02165FB8` (inside `0x02165ECC`) ORs `[record+0x150] & 0xFF` through this API:

```
0x02165F98: ldr r0,[r5,#0x10]        ; r0 = record (ptr lives at wrapper+0x10)
0x02165FA8: ldr r0,[r5,#0x10]; mov r2,#0
0x02165FB0: ldr r1,[r0,#0x150]; and r1,r1,#0xff
0x02165FB8: bl 0x207d064             ; record+0x34 |= byte, +0x38 |= 0
```

`record+0x150` is written via an interior pointer, `r8 = record+0xA4`, by **two separate
functions** — the earlier scratch draft of this trace wrongly merged both into one function and
cited the leading `ldr`s instead of the stores; corrected here:

- `0x02080F14` sets `r8 = record+0xA4` at `0x02081160`, and stores at `0x02081574`:

  ```
  0x02081564: ldr r0,[r6,#0x14]; ldr r1,[r8,#0xac]; bic r0,r0,#0xfc000000
  0x02081574: orr r0,r1,r0; str r0,[r8,#0xac]     ; record+0x150 |= (partner_elem+0x14 & 0x3FFFFFF)
  ```

- `0x02081DDC` sets `r8 = record+0xA4` at `0x02081EC8`, and stores at `0x02081F88`:

  ```
  0x02081F78: ldr r1,[r7,#0x14]; ldr r2,[r8,#0xac]; bic r1,r1,#0xfc000000
  0x02081F88: orr r1,r2,r1; str r1,[r8,#0xac]     ; same, other element in the pair
  ```

`[r8,#0xac] = record+0x150` in both cases (`r8 = record+0xA4`, `0xA4+0xAC = 0x150`).

**Label:** the code path above (the API, the ov6 `&0xFF` read, and both `record+0x150` writers)
is **CONFIRMED_STATIC**. The claim that `entry+0x08` bits reach `elementA+0x14` via
`T14`/`T18`/`T1C` — the step that would close the loop back to per-hitbox authoring data — is
**PLAUSIBLE**: it rests on `docs/research/findings/contact-array-semantics-settled.md` §4, and
was not re-derived from raw bytes in this pass.

## 6. Second opinions

All three transcripts are `codex exec -m gpt-5.6-sol`, run with only raw disassembly and no
hint of the conclusion being checked.

**On the node `+0x18` writers** (`codex_node18_opinion.txt`): full agreement on all seven stores
and the seed's dataflow. One representative line:

> "`node->field_18 = record->field_38;`... The instructions alone do not prove that every
> possible caller passes a properly installed Block C sub-object. They prove the narrower
> statement: Block A copies `[object_argument->field_28 + 0x38]` into `r5+0x18`."

**On the `r6`/entry resolution** (`codex_alloc_r6_opinion.txt`): full agreement that `r6` is the
`ColWork*`, not the collision entry, and that the property word is `*(entry+0x08)`. One
representative line:

> "`r6` points to the runtime `ColWork` object, not to a 20-byte collision record... the word
> tested against bits 0..31 is the `+0x08` field of the resolved collision record. It is not
> `*(r6+0x08)`."

**On the `+0x150` chain** (`codex_0x150_opinion.txt`): full agreement on the API semantics, the
`[record+0x150]&0xFF` source, and both `record+0xA4`-interior-pointer writers. One representative
line:

> "`record->field_150 |= source_element->field_14 & 0x03FFFFFF;`" — matching the
> `0x02081F78`-`0x02081F88` writer above.

**One wording nitpick, no substantive disagreement:** on the node `+0x18` writers, codex pushed
back on describing the seed as "the SEED store writes into `record+0x38`" — the store's
*destination* is `r5+0x18`, and `record+0x38` is only the *source*. Same fact, phrased more
precisely.

## 7. What this does not show

- Which specific entry id each live projectile in the census actually resolves to — this needs a
  GDB breakpoint at `0x0207D4A8` logging `r3` (the id) and the resolved entry pointer
  (`[r5,#0x10]` after the branch), per state.
- The gameplay meaning of `entry+0x08` bit 5 (or of the other `T18`-indexed bits).
- Whether the `+0x150` path (§5) ever actually sets node bit 0 at runtime — the census read
  `record+0x150 == 0` on all 22 in-use records, so this pass found no live case where that chain
  contributes to node `+0x18`.

## 8. Resolved (2026-09-11, `jus-8bjc`): the seed's `0x800` is a creation constant

The live allocator probe showed node `+0x18 = 0x800` on two built-in id 0 nodes whose seed had to
come from `record+0x38`, while the baseline census read `+0x38 = 0` everywhere. A CPU write-watch
on record 20's `+0x38` across a 173-frame plan on `pc-mashirito-y-npx-yusuke-fy` (three runs)
found exactly three writes: the installer's first write at `0x0207CA6C` (value `0x800`), the
allocator's own writeback at `0x0207D770` (`+0x38 |= node+0x18 & 0x18`, unchanged), and a
flag-clear call from ov6 `0x02157748` whose mask left `0x800` in place. GDB at the installer and
wrapper entries showed that record's `r3` argument is the literal `0x800` from ov6 `0x02168E3C`,
while all eleven other records created in the run came through the arm9 wrapper `0x02083624`,
which hardcodes `r3 = 0`. So `+0x38` is not transient: the baseline records were all of the
`r3 = 0` kind, and the post-run census files already carried `0x800` on records 103 and 20. This
is the live confirmation of the call-site table in `record-0x38-is-a-category-bitmask.md`.
Conditions, logs and codex agreement:
watch-0x38-2026-09-11/RESULTS.md.
