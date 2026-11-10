# Deck editor reference

> **Scope.** Canonical spec for reimplementing the JUS deck editor without the
> original code. Static mining plus framebuffer-verified automated runs; every
> claim cites its source, tracker items cited as `[jus-...]` carry the evidence state
> (the issue tracker). Items still unproven are marked **OPEN**.

## Navigate this reference

| Topic | Section |
|---|---|
| The deck model | [1](#1-the-deck-model) |
| On-disk data the editor consumes | [2](#2-on-disk-data-the-editor-consumes) |
| Overlay residency | [3](#3-overlay-residency-which-code-runs-where) |
| The deck in memory | [4](#4-the-deck-in-memory) |
| Placement rules | [5](#5-placement-rules) |
| The RAM oracle at 0x020A0C00 | [6](#6-the-ram-oracle-at-0x020a0c00-what-it-can-and-cannot-validate) |
| L/R sticker hotkeys — in-battle switching | [6.5](#65-lr-sticker-hotkeys-in-battle-switching-runtime-2026-09-03) |
| Open items | [7](#7-open-items--triaged-by-relevance-tracker-item-jusmap16) |

---

## 1. The deck model

A deck is a **5-column x 4-row grid** (20 cells) onto which panels ("koma") are
placed. Confirmed three independent ways: the placement validator rejects
`col >= 5` / `row >= 4` with a `row*5` stride; the battle-side adjacency gate
bounds `x < 5, y < 4`; and the owner observed the grid in live play
(`[jus-koma-shape-is-a-20bit-bitmap-423]`,
`../research/findings/p225-koma-adjacency-grants-abilities.md`,
`../research/Deck-System.md`).

Panel classes, perfectly determined by cell count with zero exceptions across
all 890 koma
(`../research/findings/koma-format-decoded.md`):

| Size (cells) | Type | Count in koma.bin |
|---|---|---|
| 1 | Helper (passive) | 312 |
| 2–3 | Support (support attack) | 188 + 184 |
| 4–8 | Battle (playable fighter) | 62+61+55+16+12 |

Every one of the game's 312 characters has exactly one 1-cell helper
(`../research/findings/koma-format-decoded.md`).

A valid deck additionally needs a **leader sticker** on a battle koma; without
it the editor refuses to exit with 「リーダーが居ません…」
(`../research/Deck-Editor-Automated.md`).

---

## 2. On-disk data the editor consumes

### 2.1 koma.bin — the panel catalogue

890 records x 12 bytes
(`../research/findings/koma-format-decoded.md`).

The `koma.bin` record layout is documented once, in [koma.md](koma.md) §1 (890/890
records, evidence per field there); this page only uses `+0x7` abilityId, `+0x8`
kshapeGroupId (size − 1) and `+0xB` flags (nature override nibble).

**CORRECTED — nature IS in koma.bin** (flags byte `+0xB` high nibble, sentinel
`3` = use base; accessor ov5 `0x0214E480`; see [koma.md](koma.md) §2 /
`../research/findings/nature-SOLVED.md`, tracker item `jus-yw8m`). The paragraph below is the
retracted negative, kept as search history:

> **Nature is not stored in koma.bin at all** — Naruto's size-2 (Laughter) and
> size-3 (Power) panels are byte-identical in every candidate field. Where the
> editor's per-panel nature display comes from is **OPEN**; best candidate is a
> parallel table (piece.bin is variable-length, not a 890-stride table)
> (`../research/findings/koma-format-decoded.md`).

### 2.2 kshape.bin — the shape catalogue

1648 bytes (`../research/findings/koma-format-decoded.md`,
`../research/findings/p229-koma-shapes-come-from-kshape-bin.md`):

- Header: `int32 groupStart[8]` = (0,1,3,9,21,35,49,62), then
  `int32 numElements[8]` = (1,2,6,12,14,14,13,4), sum 66.
- Then 66 entries of 24 bytes at base 0x40: a **20-byte cell map over the 5x4
  grid** (0 = empty; nonzero = occupied, value-1 = tileset index) plus a
  trailing word that includes the packed **20-bit shape bitmap** (matches the
  runtime shape word, section 4.1).
- Lookup: `entry = groupStart[kShapeGroupId] + kShapeElementId`.
- Group g always has exactly g+1 occupied cells — so the group IS size-1.
- Sizes 1–3 are the complete polyomino sets; sizes 4+ are hand-picked subsets
  (e.g. 12 of 19 tetrominoes). Independently confirmed: the editor's size-5
  shape filter shows 13 options, matching the 13 shapes koma.bin actually uses.

An earlier record base of 0x54 was wrong and retracted; 0x40 is current
(`../research/findings/p229-koma-shapes-come-from-kshape-bin.md`, correction sections).

---

## 3. Overlay residency — which code runs where

ARM9 overlays 0–9 share load address 0x0214CD20, so only one is resident at a
time (`../research/Overlay-Residency-By-Mode.md`).

| Screen | Resident at 0x0214CD20 | Source files (modules.json) |
|---|---|---|
| Deck select list (デッキセレクト) | **ov01** (99.6% RAM match) | DeckSelect.cpp, StageSelect.cpp, RuleSelect.cpp |
| Deck editor (KomaEdit) | **ov05** (99.5% RAM match) | DeckMake.cpp, KomaList.cpp, KomaEdit.cpp, KomaState.cpp, KomaHelp.cpp, KomaIBook.cpp, Database.cpp, JPower.cpp |
| Battle | ov06 | — |

Measured byte-for-byte against live RAM, with the symbol table agreeing
independently (`../research/Overlay-Residency-Deck-Screens.md`). An earlier "ov01 is the
editor" reading was a mislabeled screen — it had measured the deck *list*, not
the editor. ov10 (WiFi) and ov12 (ALWidget/ALTextDS UI library) are resident on
both deck screens; ov12 is resident in battle too, partially overwritten from
the low end.

**Ownership:** of the 55 functions holding the deck global, 37 are in ov5
(KomaList/KomaEdit/KomaState/DeckMake/DatabasePersonal), 16 in arm9, 1 in ov6,
1 in ov11. The deck structure belongs to the editor; battle code touches it
once (`../research/findings/deck-global-holders-and-a-fourth-mask-bug.md`). The core
validators and add-entry live in **arm9** (always resident), so the editor UI
in ov5 drives shared arm9 deck logic.

**Consequence for reimplementers:** anything the editor computes at 0x0214CD20
addresses (e.g. the ov05 nature resolver at 0x0214E480) is unreachable in
battle — the editor's derived values must be treated as display/deck-bonus
logic, not battle logic (`../research/Overlay-Residency-Deck-Screens.md`).

---

## 4. The deck in memory

### 4.1 The ComicDeck block

Global holder at **[0x0214BD80]** points to a **0x1914-byte** block, `memset`
to zero at creation (`../research/findings/deck-validators-and-the-id-table.md`,
`../research/findings/shared-encoding-decoders-and-the-zeroed-deck.md`). Known fields:

| Offset | Field | Source |
|---|---|---|
| +0x30 | ID table base — 0xC-byte entries (the koma.bin record shape) | lookup fn 0x02076C98 |
| +0x38 | second table base, stride 0x18 (the kshape record shape), indexed via signed bytes at record +0x8/+0x9 | fn 0x02076D00 |
| +0x18EC | entry count for the ID table | fn 0x02076C98 |
| +0x558 | active node list head | add-entry 0x02076E38 |
| +0x560 | free node list head | add-entry 0x02076E38 |
| +0x568 | **20-bit occupancy mask** of the placed page | validator 0x02076D30 |

**OPEN:** no writer of +0x30 or +0x18EC was ever found despite an exhaustive
sweep of every store form among all 72 deck-pointer holders
(`../research/findings/shared-encoding-decoders-and-the-zeroed-deck.md`,
`../research/findings/dead-deck-residual-closed.md`). Either the tables are filled through
an unattributed path or this arm9 add-entry path is dead in practice
(`../research/findings/deck-add-entry-path-is-dead.md` — see that file before assuming the
path is live).

### 4.2 Deck nodes

Each placed koma is a **0x50-byte node** moved from the free list (+0x560) to
the active list (+0x558) (`../research/findings/deck-add-entry-contract.md`,
`../research/findings/the-0x50-deck-node-mapped.md`):

| Offset | Field |
|---|---|
| +0x00 | next pointer |
| +0x0C | u16 koma ID (init -1); zeroed 4 bytes then ID written on fill |
| +0x0E | packed cell: low nibble = column, high nibble = row |
| +0x0F | low nibble = helper direction, 1..4 (see 5.4); bit 0x10 gates a halving in a battle walker |
| +0x10..0x31 | memset to 0 on fill (0x22 bytes) |
| +0x16 / +0x18 | signed source / destination halfwords (battle-side walker halves +0x16 into +0x18) |
| +0x34 | pointer to the koma data record (first halfword = ID; used by the duplicate check) |
| +0x3C | flags word |
| +0x40 | non-zero = skip node |
| +0x41 | ability ID (read by the adjacency granter) |

### 4.3 Save-region and runtime addresses (from GDB dumps)

From `../research/Deck-Memory-Structure.md` (GDB dump diffs; treat as measured-once):

| Address | Meaning |
|---|---|
| 0x020A0C00–0x020B0000 | Deck-state region (the RAM oracle, section 6) |
| 0x020A0C98 | deck state flag; bit 1 = "no leader" (0x05 with leader, 0x07 without) |
| 0x020A1000–0x020A3000 | **pointer arrays, not raw koma IDs** — scanning for ID byte patterns here gives false positives |
| 0x020A2289 | leader boolean (1 = leader set) |
| 0x020A4368 | pointer to the leader koma's runtime data (0 when no leader) |
| 0x020AFEB4 | active deck slot index (0–7) |
| 0x020B0BAC | koma unlock bitmask |
| 0x020B9480 | koma master table in the save region: sequential u32 koma IDs; per-character sizes step by 0x0C (e.g. Eve: 1-koma 0x1DB0 … 4-koma 0x1DD4) |

**OPEN:** how these save-region structures map onto the ComicDeck block's ID
table (+0x30) has not been established. The relation between deck+0x568 (the
occupancy mask) and battleObj+0x558 (the battle node list head) is also just an
adjacent-looking pair of offsets in different structures, nothing more
(`[jus-koma-shape-is-a-20bit-bitmap-423]`).

---

## 5. Placement rules

### 5.1 Shapes are 20-bit polyomino bitmaps

The shape word at `shapeObject+0x14` is a 20-bit bitmap of the 5x4 grid: bits
0–4 = row 0, 5–9 = row 1, 10–14 = row 2, 15–19 = row 3
(`[jus-koma-shape-is-a-20bit-bitmap-423]`, arm9 0x02076D30). **OPEN:** the
identity of "shapeObject" (what 0x02076D00 returns) — the word is at +0x14 of
whatever that lookup yields, which reads deck+0x38 with stride 0x18, i.e. the
kshape-derived table.

### 5.2 The placement validator — arm9 `0x02076D30(deck, id, col, row)`

Reject in order (`[jus-koma-shape-is-a-20bit-bitmap-423]`,
`../research/findings/deck-validators-and-the-id-table.md`):

1. `col >= 5` or `row >= 4`.
2. ID fails the bounds-checked lookup `0x02076C98` (rejects -1, negative,
   `id >= [deck+0x18EC]`; else returns `[deck+0x30] + id*0xC`).
3. **Width check:** OR the shape word's four 5-bit row fields into a column
   profile, shift left by `col`; if anything escapes the low 5 bits the shape
   would wrap a row edge — reject.
4. Shift the whole 20-bit shape by `col + row*5`; if any bit >= 20 sets
   (spills off the bottom of the grid) — reject.
5. If the shifted shape overlaps the deck's occupancy mask `[deck+0x568]` —
   reject.
6. Otherwise return the shifted shape mask (the caller ORs it into occupancy).

### 5.3 Add-entry — arm9 `0x02076E38(slot, id, col, row, …)`

Error codes in the top nibble (`../research/findings/deck-add-entry-contract.md`):

| Condition | Return |
|---|---|
| free list [slot+0x560] empty | 0x20000000 |
| an active node already has this ID (no duplicate koma in a deck) | 0x40000000 |
| validator 0x02076D30 returns 0 | 0x10000000 |
| success | node unlinked from free list, linked to active list, ID at +0x0C, `(col & 0xF) | (row << 4)` at +0x0E |

### 5.4 Helper direction and adjacency abilities

Helpers point at a neighbour. Node +0x0F low nibble holds a direction 1..4
mapping through the table at arm9 0x02092E34 to (dy=+1 down, dx=-1 left,
dy=-1 up, dx=+1 right). Gate `0x020779CC` steps one cell from the node's
(col,row), rejects off-grid, reads the pointer in the neighbouring cell of a
5-wide, 4-byte-stride grid, and the caller appends the node's ability ID
(+0x41) to that object — **koma grant abilities by grid adjacency**
(`../research/findings/p225-koma-adjacency-grants-abilities.md`). This matches the owner's
rule that most helpers must point at a specific battle character; the whole-deck
+1 SP helpers are the exception (`../research/Deck-System.md`).

### 5.5 Rules observed in the editor (framebuffer-verified, no code path yet)

From `../research/Deck-Editor-Automated.md`, three identical automated runs accepted by the
game:

- **Placing over an occupied cell evicts** the koma underneath back to the
  list; it does not fail. **OPEN:** the code path for eviction (the validator
  above rejects overlap, so the UI must remove-then-add).
- **One-character rule:** committing a koma greys out every koma of that
  character, and the grouping includes alternate forms and fusions (Goku greyed
  SSJ Goku and Vegetto). A deck cannot be built from one character's koma
  alone. Consistent with, but wider than, the add-entry duplicate-ID check —
  the ID check alone would not grey other koma. **OPEN:** where the
  character-grouping table lives.
- **Leader:** cell cursor on a battle koma, R picks up the sticker, A stamps.
  B after pickup cancels the stamp while still drawing the badge — the failure
  only surfaces at exit.
- Editor UI grammar: nearly every control takes **two taps** (first focuses,
  second activates); a single cell tap only moves an uncommitted preview.
- The final validity check is the game's own exit caution — stronger than any
  memory or pixel signal.

Route in: top menu デッキメイク → deck select (ov01) → tap slot twice → 編集 →
editor (ov05) (`../research/Deck-Editor-Automated.md`).

---

## 6. The RAM oracle at 0x020A0C00 — what it can and cannot validate

The deck-state region 0x020A0C00–0x020B0000 is a useful but **coarse** oracle.
Measured byte-diff magnitudes (`../research/Deck-Editor-Automated.md`):

| Event | Bytes changed |
|---|---|
| idle after savestate load | 17–42 |
| a tap/press that does nothing | 95–190 |
| SELECT with no pixel change | 1041 |
| clearing a full deck | 361 |
| placing one 4-koma | 1326 |

Rules for using it:

- It confirms **that something large happened, and nothing finer**. An
  ineffective tap costs ~100–190 bytes, so mid-size diffs are not evidence of a
  state change (a 107-byte "deck cleared" reading was a false positive).
- An **uncommitted preview also moves ~1326 bytes**, indistinguishable from a
  real placement. Placement must be verified by round-tripping the canvas
  (toggle away and back) or by the game's own exit verdict.
- Specific bytes within it that ARE reliable field-level signals: 0x020A0C98
  (leader bit), 0x020A2289 (leader boolean), 0x020A4368 (leader pointer),
  0x020AFEB4 (deck slot) — see section 4.3.
- Occupancy is better read elsewhere: on-screen (`canvas_cells()`, 81 samples
  per cell, 1.00 empty vs 0.00 occupied) or, in a reimplementation, as the
  20-bit mask semantics of deck+0x568.

---

## 6.5 L/R sticker hotkeys — in-battle switching (runtime, 2026-09-03)

`jus-e2w4`. Two runs on savestates of the 20-cell grid described in §1:
runtime-report-3-lr-switch.md
(a deck with no hotkeys, null result) and
runtime-report-4-lr-switch-taikoubou.md
(a deck with hotkeys, the mechanism found).

- **L and R are per-deck sticker bindings to specific koma, not a
  "next/previous" cycle.** On the Taikoubou/Momotaro/Yusuke deck, L always
  switches to Yusuke (slot 2) and R always switches to Momotaro (slot 1),
  from any starting slot. The leader (slot 0) has no hotkey and L/R cannot
  return the player to it — pressing the hotkey of the koma already active
  instead drives that koma's own state `0x0b` move. Nine of the eleven
  states sampled in run 4 carry decks with **no** hotkey stickers at all and
  do not respond to L/R; run 3's null result was the deck, not the
  mechanism.
- **The press is cheap: a single frame is enough.** A 1-frame L or R press
  produces the identical timing as a 6- or 16-frame hold. The new fighter is
  **live 3 frames after the press** and **controllable (can attack) 4 frames
  after the press**. There is **no cooldown** — two switches 3 frames apart
  both land, and L+R pressed together always resolves to L.
- **Mid-move presses are queued, not dropped.** A press made while the
  fighter is in a busy state (attack, dash, etc.) commits on the first frame
  the fighter becomes interruptible; measured deferred latencies of 5, 10,
  11, 18, 19 and 28 frames in a live fight, always landing on the frame the
  busy state ended.
- **There is no second fighter object.** The P1 fighter object address never
  changes and the fighter table (`0x021DEB3C`) still holds exactly two
  pointers after a switch — the same object is refilled in place. The
  outgoing character has no state and no position of its own once benched.
- **The active-koma flag is bit 0 of the deck HP record's `+0x25` byte**,
  not the `+0x24` word an earlier note read as the active flag (see the
  correction in [physics.md](physics.md) §5 and
  [damage.md](damage.md)). `+0x24`'s low byte is an action code instead
  (`0x03` while attacking). The fighter object's `+0x1CC` becomes the active
  slot index after the first switch of a battle (before that it holds the
  leader's `chr_b`, a setup leftover — do not read it as a `chr_b` field
  before a switch has happened), and `+0x55` records which hotkey caused the
  last switch (`0x40` L, `0x80` R, `0xC0` both).
- **The handler is a single routine**, citable as `0x02157534` (the `bl`
  whose return address `0x02157538` both slot-flag writes and the `+0x1CC`
  write share) — not disassembled beyond that in the source reports.
- **A switch does not heal or damage anyone**, but a benched slot then
  regenerates ~1 raw HP/frame — **closed 2026-09-03**, this is per-character
  authored content (`koma+0x49`) and does not depend on the in-battle
  auto-recover setting at all; see [damage.md](damage.md) §8, `jus-b3k2`.
- **The queued-switch gate is the slot record's action byte
  (`+0x24` low byte), not `obj+0x18`** (`jus-qd8s`,
  runtime-report-9-regen-landing
  §2.5). Every press made while that byte reads **`0x01`** (idle) flips in
  exactly **3** frames; every press made while it reads **`0x03`** (busy —
  attacking or mid-hitstun) is deferred to the frame *after* the byte falls
  back to `0x01` (measured latencies from 5 to 66 frames, 24/24 presses in a
  live fight). **Landing lag does not defer a switch**: state 13 (landing,
  physics.md §6.6) is a busy-looking state code whose action byte stays
  `0x01`, so a switch pressed during landing lag still lands in 3 frames —
  `obj+0x18` is the wrong field to gate on, only the action byte is the true
  gate. **Only one switch request is queued, and the last press wins**:
  three presses inside a single hitstun window produced one flip, to the
  target of the final press. A hitstun-gated switch is otherwise the same
  mechanism as any other busy-state deferral, not a special case.
- **Re-pressing the active koma's own hotkey drives state `0x0b` in
  place instead of switching — the owner's "dream attack" (`jus-jh7d`,
  2026-09-12, dream-attack-2026-09-12/RESULTS.md).**
  This is the state code this section's run-4 note flagged and left
  unnamed. Confirmed on the same Taikoubou/Momotaro/Yusuke deck: the
  re-press starts a move in place at press+3 (slot action byte
  `0x01`→`0x13`, pending state `obj+0x19`→`0x0b`), committed at `obj+0x18`
  on press+4; no active-flag or `+0x1CC` change occurs on this press. The
  object stays in place and its state byte reads `0x0b` for 47 frames of
  committed state (frames 85–131 in the measured run; press-to-idle is 51
  frames total, since idle only returns the frame after `0x0b` clears)
  instead of switching. **Pressing the *other* hotkey while `0x0b` is
  running flips the `obj+0x1CC` active-slot index at press+3 — one frame
  *faster* than an ordinary switch's own press+4 `+0x1CC` flip — while the
  deck record's active-bit transfer lands at press+4, one frame *slower*
  than an ordinary switch's own press+3 active-flag transfer, in three of
  the four sampled chained switches. In the fourth — the shorter (+10)
  offset — that transfer was instead deferred by 12 frames to press+15,
  which is inside the documented 5–66-frame busy-deferral range above,
  not outside it. Whether the outgoing slot's mid-move action byte `0x13`
  is exempt from that deferral gate is unresolved — the two sampled
  chains are also both consistent with the active-bit transfer landing at
  `max(press+3, the outgoing move's own next state-boundary frame)`, not
  tested further. The incoming koma is idle for exactly one frame after
  becoming active, then busy the next — the same live-in-3/controllable-
  in-4 pipeline as an ordinary switch, not an immediate busy transition.**
  Pressing the first hotkey again switches back at the same fast latency
  and spends exactly one SP bar (guard-sp.md §1.4) on that press, landing
  on the switch-commit frame, one frame before the incoming slot is
  active — matching an ordinary special's cost, though the timing means
  "switch-back costs a bar" and "incoming special costs a bar" are not
  separable by frame alone; neither dream attack in the chain spends a
  bar. The chain is timing-sensitive on the second hotkey's press: 1 frame
  after the triggering re-press (before its own 3-frame commit resolves)
  did not chain — a result at least as well explained by the
  already-confirmed single-request switch queue (this section, above,
  "last press wins") as by a dedicated timing gate; 10 and 30 frames after
  did chain, at the same fast latency — the true minimum boundary is
  bracketed, not bisected. The fighter object's coarse state byte reads `0x0b`
  continuously through the **entire** chain (both dream attacks and the
  closing special); it does not disambiguate which sub-move is running.
  Only a two-hotkey deck was available, so a full three-member chain (per
  the owner's fuller testimony) was not exercised, and no hit was
  confirmed landing on P2 in any run this session — the dream attack's
  move record and any damage are open (`jus-jh7d`).

## 7. Open items — triaged by relevance (tracker item `jus-map.16`)

The deckbuilder is discrete logic; concept + the decoded data files suffice to
recreate it (rationale in the tracker item). Remaining questions split:

### Open

1. **Character-grouping (greying) table** — which koma grey together, incl.
   alternate forms and fusions; behaviour confirmed, data unextracted
   (was item 6 below).
2. **piece.bin relationships table** — which adjacencies grant +8 HP; feeds the
   confirmed HP formula (`chr_b[size−4] + 8×sources, cap +32`). Owned by
   `koma.md` §7.3.
3. **Helper facing semantics** — one cell vs row/column; UI behaviour vs the
   type-2 chain identity unproven. Owned by `helpers.md` GAPS.
4. **koma.bin `+0xA`** (0..8, ≤ size) — render anchor or sort key; cheap on any
   static pass (was item 4 below).

### Remaining original-game questions

5. ~~shapeObject identity~~ — the shape word's `+0x14` location and semantics
   are confirmed; the owning object's identity is original-code detail (was item 2).
6. ~~No writer for deck+0x30/+0x18EC / dead add-entry path~~ — the native writer
   path is unidentified; the validator + error codes specify the observed behaviour
   (was item 3).
7. ~~Eviction-on-overlap code path~~ — behaviour framebuffer-verified;
   the native evict code path is unidentified (was item 5).
8. ~~Save-region layout vs ComicDeck block~~ — the save layout is not decoded
   (was item 7).
9. ~~deck+0x568 vs battleObj+0x558~~ — adjacent-looking offsets in different
   structures; curiosity only (was item 8).

*Former item 1 (nature storage) is resolved — see the §2.1 correction above.*
