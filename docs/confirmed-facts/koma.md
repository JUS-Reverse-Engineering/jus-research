# Koma and kshape reference

> **Scope.** Static analysis of the shipped files plus already-held RAM dumps; no
> claim depends on a live emulator run, except the native support-call subsection
> (section 2a.2), which summarises emulator captures and cites their bundles. Verdict per `INVENTORY.md` §8: **portable
> now** — the two data files, the placement rule, and the adjacency-ability
> mechanic are all closed. This reference owns the on-disk formats and koma
> semantics. For the editor-side validator call sequence, the ComicDeck memory
> block, and deck nodes, see [deck-editor.md](deck-editor.md) §4–§5 — not
> repeated here. Unresolved items are marked **OPEN**.

## Navigate this reference

| Topic | Section |
|---|---|
| koma.bin — the panel catalogue | [1](#1-komabin-the-panel-catalogue) |
| Nature (per-panel, sentinel-and-fallback) | [2](#2-nature-per-panel-sentinel-and-fallback) |
| kshape.bin — the shape catalogue | [3](#3-kshapebin-the-shape-catalogue) |
| The placement rule | [4](#4-the-placement-rule) |
| Adjacency grants abilities | [5](#5-adjacency-grants-abilities) |
| ov12 heap — battle RAM residency | [6](#6-ov12-heap-where-these-files-live-in-battle-ram) |
| Open items | [7](#7-open-items--triaged-by-relevance-tracker-item-jusmap16) |

---

## 1. koma.bin — the panel catalogue

`bin/koma.bin`, 10680 bytes = **890 records × 12 bytes**. One record per panel (koma).
Source: `docs/research/findings/koma-format-decoded.md` (field map stands; its
"nature is not in koma.bin" headline was later overturned — see §2). Tool:
`scripts/analysis/dump_koma.py`.

| Off | Type | Name | Evidence | Meaning |
|---|---|---|---|---|
| `0x0` | u16 | imageId | 890/890 records (source above) | `0..889`, always equals record index — redundant |
| `0x2` | u16 | characterId | 890/890 records (source above) | `1..312`, 312 distinct characters |
| `0x4` | u8 | seriesIdx | 890/890 records (source above) | `1..42`, index into `Koma.NameTable` (`src/JUS.Tool/Graphics/Koma.cs:33`, 43 slots, slot 0 null; strings from ARM9 pointers at `0x0209E840`) |
| `0x5` | u8 | panelOrdinal | 890/890 records (source above) | 0-based panel number within the character; `(seriesIdx, panelOrdinal)` is unique across all 890 |
| `0x6` | u8 | panelType | 890/890 records (source above) | `0` Battle, `1` Support, `2` Helper — cached, fully derivable from size (see below) |
| `0x7` | u8 | abilityId | inferred, see §2 | meaning depends on panelType (see below) |
| `0x8` | u8 | kshapeGroupId | 890/890 records (source above) | **panel size = value + 1** (66/66 rule, §3) |
| `0x9` | u8 | kshapeElementId | 890/890 records (source above) | which shape of that size |
| `0xA` | u8 | unkA | **OPEN** | `0..8`, always ≤ size; loosely tracks shape bounding box (width 474/890, height 500/890) — render anchor? sort key? |
| `0xB` | u8 | flags | 890/890 records (source above) | **high nibble = per-panel nature override** with sentinel `3` = "use base" (§2). **Low nibble bit 0 = female panel flag** (per panel; owner-confirmed consumer: Sanji's effects count female battle+support+helper panels in the deck; `jus-koma-female-flag-6yf5`). Low-nibble value `2` (7 helper panels, seriesIdx 42) OPEN |

Derived facts (all zero-exception over 890 records,
`../research/findings/koma-format-decoded.md`):

- **panelType is determined by size**: size 1 → Helper (312), size 2–3 → Support
  (188+184), size 4–8 → Battle (62+61+55+16+12).
- **312 characters, each with exactly one 1-cell helper panel** (312/312). 120
  characters have only the helper; only characters with a size-4+ panel are playable.
- **abilityId by type**: Helper — 47 distinct values in `0..55` (passive id space
  reaches `0x37`, wider than the cheat-code list's `0x30`); Battle — 74 distinct
  values = index into `chr_b.bin` (which has exactly 74 battle-character records);
  Support — 193 distinct in `0..192`, indexes `chr_s.bin` (see §2 support path).
- Worked example (Naruto, characterId 184, records 497–505, sizes `[1,2,3,4,4,5,6,7,8]`)
  verified against the owner's live table 9/9 in
  `../research/findings/koma-format-decoded.md` and
  `../research/findings/nature-SOLVED.md`.

## 2. Nature (per-panel, sentinel-and-fallback)

Source: `docs/research/findings/nature-SOLVED.md` (deck-editor accessor `0x0214E480`
in ov5; high-nibble predicate `0x02078CB8`). Nature *is* per-panel — the earlier
"not in koma.bin" negative in `../research/findings/koma-format-decoded.md` is
retracted (see the banner
correction and tracker item `jus-yw8m`). Enum: `0` 力 Power, `1` 知 Knowledge, `2` 笑 Laughter,
`3` なし Neutral.

```
helper  (type 2): nature = 3 (なし), unconditionally
battle  (type 0): nib = (flags >> 4) & 0xF
                  nature = nib                        if nib != 3
                  nature = chr_b[abilityId*0x3C + 0]  if nib == 3 (base nature)
support (type 1): nature = chr_s[abilityId*20 + (kshapeGroupId-1)*8]
```

`3` in the nibble is a "no override" sentinel, not a value. Only 32 battle panels
carry an explicit override. Verified 9/9 on Naruto against owner observation. Full
nature semantics (damage-path use etc.): `docs/confirmed-facts/nature.md`.

## 2a. Support payload: chr_s.bin rows

Reader: a support-record reader, not part of this export.
Source: the static decode in
`m14-decode-report.md` (external research note) ("Data and layout", "Worked records").

`bin/chr_s.bin` is 3860 bytes = 193 rows × 20 bytes, loaded at resource-manager
+0x48. A support panel (koma `type` 1, size 2 or 3) does not own a row; it
selects the variant at `v = 8 × (size − 2)` inside its row (koma `+7` is the row
index). Each name joins through the ARM9 table at `0x02092700 + 8 × index`
(`{u32 name pointer, u32 resource base}`), not through a linear series index.

| Field (row offset) | Type | Grade | Evidence | Meaning |
|---|---|---|---|---|
| `v+0` | u8 | STATIC | ARM9 `0x02077CB8`–`0x02077D30`; ov5 `0x0214E480`–`0x0214E4F4` | nature; copied to deck node `+0x13` |
| `v+1` | s8 | STATIC | ARM9 `0x02077D10`; ov6 `0x0215762C`–`0x02157658`, `0x021576C0`–`0x021576FC`, `0x02168D90`–`0x02168DB8` | placement mode (node `+0x2B`); 1 requests floor placement, 2 bypasses the grounded-call check; other values UNMEASURED |
| `v+2` | s8 | STATIC | callback-7 args `0x02078178`–`0x02078194`; ov6 `0x021576C8`/`0x021576F0`; factory `0x02168CF4` | spawn X in px (mirrored by factory relative to facing) |
| `v+3` | s8 | STATIC | same as `v+2` | spawn Y in px |
| `v+4` | s8 | STATIC | ARM9 `0x02077D08` (node `+0x2A`); ov6 `0x021576D0`, `0x02168DE8`–`0x02168DFC` | controller kind; not a shot row id |
| `v+5` | u8 | STATIC | ARM9 `0x02077CE8`–`0x02077CFC` (node `+0x16`/`+0x18`) | HP byte, raw ×64 |
| `v+6..7` | u8 × 2 | INFERRED | zero in all 386 variant slots | reserved; kept raw, not cooldown or charges |
| `+0x10` / `+0x12` | u16 | STATIC | ARM9 `0x02077D18` (node `+0x30`); ov6 `0x0215F4DC`–`0x0215F4EC` | sound bank for 2k / 3k; zero maps to −1 in PrmData `+0x1E` |
| `0x02092700 + 8×index` | u32 × 2 | STATIC | ARM9 name table | name pointer (NUL-terminated prefix) and resource base |

The reader keeps signed bytes signed (Taikoubou 3k spawn X is −32) and emits the
raw 20-byte row as `raw_row_hex` for provenance. Panel counts: 372 support
panels over 193 rows; koma men support panels are 879, 880, 881, all 2k.

### 2a.1 Support program export (M14 J2)

Exporter: a support-program exporter, not part of this export. All
fields below are STATIC (ROM bytes only; no emulator).

- Archives: `chr/ChrArc.aar` (ALAR v3) holds `chr/<prefix>.aar` (shared effect
  AMTs) and `chr/<prefix>_<size>.aar` (body `.amt/.aod/.dtx`, sometimes extra
  effect AMTs); both member lists are exported under `archives`. The base
  archive is optional: 24 prefixes have no `chr/<prefix>.aar` in ChrArc (STATIC;
  ARM9 `0x02074D3C`–`0x02074D74` branches to size-archive loading at
  `0x02074E4C` when it is absent). Absence is inventory (`archives.base` null),
  not an error. The base namespace is `[resource_base, resource_base+0x80)`
  (`0x02092704+8×index`, masked `0x00FFFF00`); size-local ids sit at `+0x80`
  (2k) and `+0xA0` (3k); shared `0x22xxxx`/`0x23xxxx` ids are outside the
  support namespace. A program with an FX request in the base namespace whose
  base archive is absent gets an `fx` unresolved item listing those ids. No
  panel in the current export has one.
- Program: body `<prefix>_<size>.amt`, main animation id 0 (2k) / 0x20 (3k),
  checked against the AMT per panel (absent id -> `unresolved`). Exported:
  `end_frame`, per-channel `CollisionType/Enable/Rect` keys plus
  `enabled_frames` (hold-last runs, end exclusive), NoteTrack commands (raw
  bytes plus `kind`), `markers`, `branches`,
  `fx` (effect id, frame, offset, node flags) and `sounds`. Sound sub 0 is bank
  0x7A, sub 2 is the panel's chr_s bank (0 -> `bank` null); sub 1 has no traced
  bank for supports and is listed in `unresolved`.
- Node decoding: the body AMT is read with the native cumulative node walk
  (ARM9 `0x0201F1C8`-`0x0201F1D8`: each ALMT v2 node delta is added to a running
  offset, zero omits the node), not the legacy `full_entry` node guess, which can
  return a wrong start (panel 196 GN02: 0x176 instead of 0x214, ok=False, so its
  two FX requests were dropped) or swapped node labels (panel 247). A node the
  walk cannot decode becomes a `node` unresolved item. Result: 8 panels gained
  FX requests (38, 64, 118, 127, 196, 247, 369, 460; +32 requests); program fx
  counts equal the `cast_relationships` cumulative path for all 372 panels.
  `anim_events.py` now applies the same validated rule to battle kits (AEFIX,
  docs/rebuild/vfx-sfx.md section 12), and the
  `_CumulativeNodesAlmt` shim stays for panels (it forces the walk for every
  extra node, so the recovered-only spawn fields are always present).
- NoteTrack op 3 dispatches by `sub` (table `0x02172000`, STATIC). Sub 0 ->
  `0x021568E8` is the callback action: `kind` `action`, `action` = arg,
  `action_arg` = signed s16 at event `+4` (Eve 589 frame 16: action 10, arg 10;
  Eve 590 frame 4: action 27, arg -50). Sub 1 (`0x0215693C`, animation
  state/flags) and sub 2 (`0x02156960`, collision flag through
  `0x0207CE7C`/`0x0207CEC8`) are not callbacks: `kind` `op3_sub1` /
  `op3_sub2`, with no `action` fields and raw bytes kept. Examples: sub 1
  es_s_23 2k (panel 7) frame 30 raw `01 03 00 00`; sub 2 Taikoubou hs_s_01 2k
  (panel 657) frame 0 raw `02 03 01 00`.
- Collision records: CollisionType >= 0x100 selects `chr/col/<prefix>.bin` row
  `(id-0x100)*20`; lower ids the shared ARM9 table at `0x0209FC2C`. Every
  referenced row is kept, including `hs_s_01` row 0 (FF effect bytes, flagged
  `legacy_terminator_flag` but enabled by CollisionType1=0x100). Row byte +4 is
  `damage_raw`, not the legacy `frameStart` label (`move_records.py:440`).
- Unresolved: a missing body archive, member, animation id, record, sound bank
  or referenced base-namespace effect archive is listed per panel in
  `unresolved`, never defaulted. Current run: 372 panels, 371 fully resolved,
  1 with unresolved items (the sound sub-1 bank of panel 889); every panel has
  a program. Effect ids are exported, not mapped to members, and spawned
  programs are not recursively evaluated, so "fully resolved" does not certify
  the effect closure.

### 2a.2 Support call, retirement and placement captures (M14 A, B/C, C3, C5)

Measured (emulator, hooks on the call gate, ov6 permission callback, controllers) facts live in the capture bundles, not here; read
their RESULTS before relying on any rule:

- Repeat boundary of the Eve panels (Eve 2k first accepted repeat at call+104, 3k at call+171): `docs/research/feel-captures/2026-10-18-m14-support/RESULTS.md`.
- Taikoubou 657 cure / 658 revive: `docs/research/feel-captures/2026-10-18-m14-support-bc/RESULTS.md`.
- Call gates and second-support rules, from the PARTIAL C3/C5 capture plus its remainder (neither closes the topic; the open cases are the
  UNMEASURED bullets of each RESULTS): no bar is refused at k_sp, and in the tested setup only (Eve 2k, one saved SP-gain setup) no cooldown follows
  that refusal (remainder N-02: the first attempt with a bar, tick 118, is accepted at the same tick with 0, 1 or 2 earlier refusals; other panels
  and conditions UNMEASURED), free-pass bytes `player+0x5CE` one-shot and `+0x5CF` persistent,
  the airborne bit of the permission callback (p_pflag, tst `P+0x78 & 2`) refuses the kind-1 supports (Eve 2k, Taikoubou 657, Eve 3k) when the
  caller is airborne and accepts them when grounded, including in hit-stun (action 8, ground flag 34, a controlled pair per variant, remainder H-01),
  while Taikoubou 658 (kind 2) has no such test and is accepted in both; hit-stun itself (p_de, action 8) is not a refusal cause. Seal row 24 allowed vs
  25 refused (both via a slot-1 RAM poke; a natural game-produced seal was not produced, UNMEASURED). One live support per player via status slot 1
  (a second press refused at p_slot1 leaves no added cooldown, C3-11). A caller tag switch does not end a support (Eve 3k remainder S-01; no owner
  change: the controller keeps the caller pointer 0x02228E80), and a caller KO / revive does not end a Taikoubou 658 support (D-01: it retires at
  its natural call+251). Early retirement: all 6 early retirements in the C3/C5 logs are on a tick where the support's own HP (controller `c18+8`,
  1024 at start) is <= 0, and the other 51 retirements have HP > 0 (MEASURED, remainder E-01); in the two tested controls (Taikoubou 658 and Eve 3k, one
  caller action-8 hit each) a caller hit neither damaged nor retired the support (MEASURED, remainder E-02; this excludes an unconditional caller-hit rule only). In the six early cases HP <= 0 and c_exitset appear on the same tick, so their order is not resolved (UNMEASURED). That HP <= 0 is the trigger is INFERRED and not isolated: the same attack could set a separate
  retirement condition (remainder E-03). That the HP loss is the same attack hitting the support body is INFERRED. A caller KO with a live Eve 2k support was not produced (UNMEASURED); a factory that returns no
  body (refund / extra cooldown) never occurred (UNMEASURED). Eve 3k mermaid placement: body x = victim x + 50 * (1 - 2 * victim flip), clamped at the
  stage walls x = 260 (left, measured 260.0) and x = 764 (right, measured 763.99609375); for an airborne (poked) victim the body takes the victim's y and
  x = victim x - 4.0039 (flip 1 only; platform edges and multi-opponent selection UNMEASURED). The playhead skips 3 frames at call+84 and 5 at call+143,
  which is how authored frame 120 becomes a hit at call+118. Bundles:
  `docs/research/feel-captures/2026-10-18-m14-c3c5/RESULTS.md` (findings C3-01..14, C5-01..08) and
  `docs/research/feel-captures/2026-10-19-m14-c3c5-rem/RESULTS.md` (remainder: N, H, D, S, W, E findings).

## 3. kshape.bin — the shape catalogue

`bin/kshape.bin`, 1648 bytes = 0x670. Sources:
`docs/research/findings/p229-koma-shapes-come-from-kshape-bin.md` (**read only the
last three sections** — the middle is self-superseded),
`../research/findings/koma-format-decoded.md` §kshape, tracker items
`jus-koma-shapes-come-from-kshape-bin-0j2` and `jus-d9a`. Parser:
`src/JUS.Tool/Graphics/Converters/BinaryKShape2SpriteCollection.cs`.

Layout:

| Offset | Size | Contents |
|---|---|---|
| `0x00`–`0x1F` | 32 | `u32 groupStart[8]` = `(0, 1, 3, 9, 21, 35, 49, 62)` — first entry index per size class |
| `0x20`–`0x3F` | 32 | `u32 groupCount[8]` = `(1, 2, 6, 12, 14, 14, 13, 4)`, sum **66** |
| `0x40`+ | 66 × 0x18 | shape records |

**Record base is `0x40`, not `0x54`.** Two earlier claims of base `0x3C` and `0x54`
were both retracted; tracker item `jus-d9a` (P0, labeled `correction`) settles it by file
size: `0x40 + 66*0x18 = 0x670` fits exactly, while `0x54 + 66*0x18 = 0x684` overruns
the file by `0x14` (and yields a fractional 65.17-record count — the tell). The `0x54`
reading had been "pinned" by a 65-test popcount check that was insensitive: bitmap
*addresses* are identical under both bases, so the check could not fail. Cite
`jus-d9a` before trusting any older base figure (the `0x54` comments on tracker item
`...-0j2` are superseded).

Each 0x18 record:

| Offset | Size | Contents |
|---|---|---|
| `+0x00` | 4 | real field, byte sequences like `01 02 03 04` loosely tracking cell count — **OPEN**, NOT a size field (only 1/66 records has word == popcount) |
| `+0x00`–`+0x13` | 20 | 20-byte cell map, one byte per grid cell in linear order: `0` = empty, nonzero = 1-based traversal ordinal (value − 1 = tileset index per the C# parser) |
| `+0x14` | 4 | **20-bit polyomino bitmap**, bit `i` = byte `i` of the cell map |

(The first 4 bytes are both the start of the 20-byte cell map and carry the ordinal
structure noted in `jus-d9a`; the map runs `+0x00..+0x13` and the bitmap is `+0x14`.)

Known data quirk: **record 59 has a duplicate ordinal** (repeats 4, skips 5) —
reproduced independently, likely a data bug in the shipped file (tracker item `jus-tv3a`,
"what survives" list). 65/66 records are clean.

Rules and geometry:

- **Grid is 5 wide × 4 tall (5 columns, 4 rows), 20 cells.** Bit `i` of the bitmap =
  cell `(col = i % 5, row = i / 5)`. Three independent confirmations: placement
  validator bounds, adjacency-gate bounds + `0x14` row stride, and owner live play
  (`docs/design/Koma-System-Design-Brief.md`). A "4 wide × 5 tall" transpose
  correction was **RETRACTED same-wake** (tracker item `jus-tv3a`): the deciding test is
  connectivity — 66/66 bitmaps are connected polyominoes at width 5, only 30/66 at
  width 4.
- **Size = group + 1**: every entry in group `g` has exactly `g+1` occupied cells,
  66/66 (`../research/findings/koma-format-decoded.md`, its P5 rule). So a koma's size is
  `kshapeGroupId + 1`; no separate size field exists.
- **Lookup**: `entryIndex = groupStart[kshapeGroupId] + kshapeElementId`;
  `fileOffset = 0x40 + entryIndex*0x18`. In code: arm9 `0x02076D00` resolves
  `(class, sub-index)` via the cumulative table (tracker item
  `jus-kshape-lookup-identified-a1j`; its "returns 0x14 short of the record" reading
  was degenerate — corrected by `jus-d9a`: it returns the record exactly, bitmap at
  `+0x14`).
- **Curated set, not all polyominoes**: fixed polyominoes number 1, 2, 6, 19, 63 for
  sizes 1–5; the file holds 1, 2, 6, 12, 14. Sizes 1–3 complete, 4+ hand-picked
  (533 free polyominoes exist for sizes 1–8; the game ships 66). koma.bin uses 64 of
  the 66 (one size-5 and one size-7 shape unused). Owner's size-5 filter screenshot
  showed 13 options — matches.
- The file loads **verbatim** into battle RAM: header + all 65 full records
  byte-identical at `0x021AF100` (file offset 0 → `0x021AF100`; records from
  `0x021AF154`). See §6.

## 4. The placement rule

arm9 `0x02076D30`, `f(deck, id, col, row)` — read end to end in
`docs/research/findings/p228-koma-shape-is-a-20bit-bitmap.md` (tracker item
`jus-koma-shape-is-a-20bit-bitmap-423`). Reimplementation:

```
reject if col >= 5 or row >= 4
shape = kshape bitmap for id                # via 0x02076C98 / 0x02076D00, [rec+0x14]
profile = union of the shape's four 5-bit row masks
reject if (profile << col) doesn't fit in 5 bits    # width check: no row wrap-around
mask = shape << (col + row*5)
reject if mask has any bit >= 20                    # spills off the bottom
reject if mask & deck.occupancy                     # deck+0x568, 20-bit occupancy mask
else place: return mask (caller ORs it in)
```

Editor-side call sequence, add-entry contract (`0x02076E38`), and the ComicDeck block
this operates on: `docs/confirmed-facts/deck-editor.md` §4–§5.

## 5. Adjacency grants abilities

Source: `docs/research/findings/p225-koma-adjacency-grants-abilities.md` — **read the
final sections**; the middle contains a base-address error and a retracted
"cross-side link" claim, both corrected in-file. Tracker items
`jus-koma-adjacency-grants-abilities-70l` (gate, 3/3 live hits),
`jus-second-ability-source-0x558-5rp` (the caller).

Mechanic: **a koma grants its ability to the character occupying the adjacent grid
cell in the direction it points.**

- Each side's deck-battle object holds: two unidentified words at `+0x000`; the 5×4
  pointer grid at `+0x008` (20 cells × 4 bytes, row stride `0x14`); **16** node slots
  of stride `0x50` at `+0x058` (count went 19.6 → 18 → 16; the fractional values were
  the error signal; `0x58 + 16*0x50 = 0x558` exactly); chain head pointer at `+0x558`.
  A `0xC0` gap before the other side's object is **OPEN** (unexplained).
- A node carries: own cell at `+0x0E` (low nibble = column, high nibble = row —
  own-cell verified 11/11), direction at `+0x0F` low nibble (`1..4`), type at
  `+0x40`, and `+0x41` = chr_b index (type 0) or ability id (type 2). Nothing in the
  node is safe to read without checking `+0x40` first.
- Gate arm9 `0x020779CC`: reject direction 0 or >4; step `(dx,dy)` from the 8-byte
  table at `0x02092E34` (`1`=down `(0,+1)`, `2`=left `(−1,0)`, `3`=up `(0,−1)`,
  `4`=right `(+1,0)`); reject off-grid (`x'<5`, `y'<4`, both ≥0); return the pointer
  at `grid[y'*5 + x']`, or fail on null. The caller (AddAbility) appends the node's
  ability id to the returned object's ability list (`+0x1A` count / `+0x1B` list —
  matches the established char-struct layout; object identity is one-usage evidence,
  flagged as such in the tracker item).
- Verified live 3/3 (predicted neighbour addresses matched grid contents), plus a
  perfect 20-cell tiling of the grid by 11 node footprints. The direction field was
  earlier mistaken for the nature enum (both are 1..4-ish); that reading is dead.
- **OPEN**: what writes the `+0x558` chain (the deck→battle bridge — INVENTORY §8
  open Q5); the two words at object `+0x000`.

## 6. ov12 heap — where these files live in battle RAM

Sources: tracker items `jus-ov12-window-is-a-tagged-heap-95p` (runtime-confirmed) and
`jus-heap-blocks-matched-to-files-v3e` (byte-comparison comments).

The ov12 window `0x021AC700..0x021C13A0` is a contiguous tagged heap of **19 blocks**
(header: tag `0x4D48` at `+0x00`, allocator base `0x021AC200` at `+0x0C`, size incl.
0x20 header at `+0x10`; zero gaps). Allocation granularity: payload `S` satisfies
`B − 0x40 < S ≤ B − 0x20` for block size `B`.

**15 of 19 blocks byte-matched to files** (identities, not size arguments).
The distinction is load-bearing: an earlier pass named blocks by matching a
payload size against the file list, which is a *filter* over candidates and not
an identification. It named two files wrong while the correct file was in its
own candidate set, and it reported two no-match blocks where there are four —
an undercount by construction, since every false positive takes a block off the
no-match list (tracker item `jus-size-matching-is-a-filter-3u1`). Report the candidate
set, not the pick. Every row below is a byte comparison.

| Block | Size | File |
|---|---|---|
| `0x021AC700` | `0x29E0` | `bin/koma.bin` |
| `0x021AF0E0` | `0x06A0` | `bin/kshape.bin` (payload at `0x021AF100`, verbatim) |
| `0x021AF780` | `0x1180` | `bin/chr_b.bin` |
| `0x021B0900` | `0x0F40` | `bin/chr_s.bin` |
| `0x021BA020` | `0x0380` | `chrbin/chr/col/item.bin` |
| `0x021BA3A0` | `0x0220` | `chrbin/chr/col/db_b_01.bin` |
| `0x021BA5C0` | `0x0260` | `chrbin/chr/col/yo_b_01.bin` |
| `0x021BA820` | `0x05A0` | `chrbin/chr/shot/yo_b_01.bin` |
| `0x021BADC0` | `0x03C0` | `chrbin/chr/col/na_b_01.bin` |
| `0x021BB180` | `0x03A0` | `chrbin/chr/shot/na_b_01.bin` |
| `0x021BB520` | `0x01C0` | `chrbin/chr/col/bl_b_03.bin` |
| `0x021BB6E0` | `0x01A0` | `chrbin/chr/shot/bl_b_03.bin` |
| `0x021BDB00` | `0x0320` | `chrbin/chr/col/op_b_01.bin` |
| `0x021BDE20` | `0x03C0` | `chrbin/chr/col/na_b_01.bin` (second copy) |
| `0x021BE1E0` | `0x03A0` | `chrbin/chr/shot/na_b_01.bin` (second copy) |

**OPEN — 4 blocks match no file** (runtime-assembled, not loaded): `0x021B1840`
(`0x85C0`), `0x021B9E00` (`0x0220`), `0x021BB880` (`0x2280`), `0x021BE580` (`0x2E20`).
Unidentified. Related observations, not promoted to claims: per-character blocks
below `0x021BDB00` group as player-side and at/above as opponent-side (na_b_01
appears twice because Naruto was in both chains); shot loading is conditional (Goku's
`0x80`-byte shot file exists on disk but is absent from the heap) — the heap is a
manifest of what has been *touched*, not what a battle needs.

So for a reimplementation: battle loads `koma.bin`, `kshape.bin`, `chr_b.bin`,
`chr_s.bin` whole and verbatim, plus per-fighter col/shot files per side.

## 7. Open items — triaged by relevance (tracker item `jus-map.16`)

Remaining questions:

### Open

1. **OPEN** koma.bin byte `0xA` (`0..8`, ≤ size — render anchor? sort key?).
2. **OPEN** `piece.bin` (35183 bytes, no 890-stride — variable-length or
   offset-indexed; not a per-koma table) and the P7 relationships table — feeds
   the confirmed +8-HP deck-bonus formula.
3. **OPEN** what writes the `+0x558` node chain (deck→battle bridge) — the
   *behaviour* (adjacency grants) is confirmed live; the writer matters only for
   confirming the bridge carries the same semantics as the editor UI
   (helper-facing identity, see `helpers.md` GAPS).

### Remaining original-game questions

4. ~~low nibble of koma.bin `+0xB`~~ — resolved: bit 0 is the female flag
   (`jus-koma-female-flag-6yf5`, §1 table); only the value-2 helper panels
   remain unexplained.
5. ~~kshape record `+0x00` word / five trailing u32s; record 59's duplicate
   ordinal~~ — the 20-byte map and `+0x14` bitmap are understood; the ordinal
   quirk is a data bug in the shipped file.
6. ~~do unlocks gate shapes?~~ — not established.
7. ~~the four unmatched ov12 heap blocks~~ — runtime-assembled scratch;
   identities not established. They would matter only if a block turns out to
   hold the relationships table (item 2).
8. Housekeeping (INVENTORY §8 Q4): the koma-side "size×k" HP speculation in
   `docs/research/Koma-System-Observed-Behavior.md` should be deleted — battle HP
   comes from chr_b per-size records (`docs/confirmed-facts/damage.md`).
