# Findings: contact-array semantics settled — a per-pair predicate source, not the damage hand-off

2026-09-09. Static. Tracker item `jus-contact-array-element-semantics-d7w8` (collision GAPS G5).
Worker: deepseek-v4-flash (general-purpose). Second opinion: `codex exec -m gpt-5.6-sol`,
neutrally framed (Q1–Q7), in full agreement on every load-bearing point; the two
disagreements are recorded as corrections below. Orchestrator spot-checks on the
stage-5 fold and the reader body matched both.

**Headline:** the contact array at `manager+0x154` is **not** the collision→damage
staging area. HP/SP application runs entirely through per-record accumulator arrays
(`record+0xA4..+0xE8` and `record+0xEC..+0x130`). The manager array's only reader is
NoteTrack query 0x47 (ov6 `0x02157EC4`), a pure boolean "did a class-4a contact occur
between me and any other participant?" that gates move-script note advancement.
G5 closes in the negative direction; the "B11 residue" question is re-located and
explained (§3).

## Corrections to prior readings

1. **4×4 cells, not 8 rows.** Stage 5 (`0x020821C4`, fold loop `0x020822C4–0x02082324`)
   iterates exactly 16 cells (`cmp r1,#0x10`, stride `0x30`, row stride `0xC0`).
   The "rows 0xC0" row in collision.md §2 / INVENTORY undercounted the extent
   implication; the array is 4 rows × 4 columns, `+0x154..+0x453`.
2. **Five routing classes, not four blocks.** The four RMW blocks plus their guard
   chain form a priority cascade; block 4 splits into 4a/4b on `elem+0x14 & 0x1700`.
   Only block 2's guard is `tst r0,#0xc0` (on `elem+0x18`, reloaded at `0x02081320`);
   the writer-found doc's "each preceded by tst #0xc0" was wrong.
3. **The index helper's out-of-range reads.** `0x02081A58` with a nibble value 9..15
   reads past the 9-word table at `0x0209FF34` into adjacent data (the worker claimed
   −1 for all of 3,5,6,7,9..15; codex: only 3,5,6,7 are −1, 9..15 read the string
   area at `0x0209FF58+`). Valid one-hot inputs are 1,2,4,8 → 0..3; sentinels: bits
   9/10/13 → 16, low byte empty → 17.

## 1. Cell map (0x30 bytes per cell, 16 cells)

| cell offset | content | writer | routing class (guard, in cascade order) |
|---|---|---|---|
| `+0x00` | HP damage, class 4b | `0x0208144C-58` | `elemA+0x18 & 0x100==0 && & 0xC0==0 && elemA+0x14 & 0xF0==0 && & 0xF!=0 && & 0x1700==0` |
| `+0x04` | HP damage, class 4a | `0x0208142C-38` | same but `& 0x1700 != 0` — **the only slots query 0x47 reads** |
| `+0x08` | HP damage, class 3 | `0x020813E0-EC` | `elemA+0x18 & 0x100==0 && & 0xC0==0 && elemA+0x14 & 0xF0 != 0` |
| `+0x0C` | HP damage, class 2 | `0x02081398-A4` | `elemA+0x18 & 0x100==0 && & 0xC0 != 0` |
| `+0x10` | HP damage, class 1 | `0x02081350-5C` | `elemA+0x18 & 0x100 != 0` |
| `+0x14` | folded HP total (stage 5) | `0x020822EC` | — |
| `+0x18` | SP damage, class 4b | `0x0208145C-64` | as `+0x00` |
| `+0x1C` | SP damage, class 4a | `0x0208143C-44` | as `+0x04` — **read by query 0x47** |
| `+0x20`/`+0x24`/`+0x28` | SP damage, classes 3/2/1 | `0x020813F0-F8`/`A8-B0`/`60-68` | as `+0x08`/`+0x0C`/`+0x10` |
| `+0x2C` | folded SP total (stage 5) | `0x02082318` | — |

A pair contributes to exactly **one** class slot-pair per frame (cascade order
1 > 2 > 3 > 4a > 4b). The whole feature is gated by
`(victim elem+0x14 & 0x37F0) == 0` (`0x020812E0`, pool `0x02081A4C`).

Accumulated quantities (same pair body `0x0208112C–0x02081A34`):

- **HP:** `[sp,#0x4c]` — the damage formula's out-parameter (`0x02081280 bl 0x020823E4`,
  `*out = (r5+r0)>>2`, raw HP/64). elemB = attacker (its CollisionEntry supplies base
  damage in `0x020823E4`), elemA = victim; `r8 = scratchA+0xA4` is the victim's record.
- **SP:** `r7 = s8(moveData[+5]) << 8` (`0x020812A0 ldrsb [elemB+0x10],+5`). This byte
  is the move's **SP-damage** (meter damage), not a duration: it shares the
  guard/absorb arithmetic with victim `record+0x176` and lands in the pending SP
  delta `record+0x144` (`0x020814D8-0x02081500`), which the per-character update
  flushes to the SP-apply function at `0x0215A324 → bl 0x020781E4`. The exporter's
  `durationMult` label for CollisionEntry byte `+0x05` is wrong (the `+0x08..+0x0B`
  byte schema is already known-wrong, collision.md §G1).

Cell index = `helper(elemAttacker+0x14 high nibble)*0xC0 + helper(elemVictim+0x14 low
nibble)*0x30` (both one-hot-compacted 0..3 via `0x02081A58`, table `0x0209FF34`).

## 2. The only reader: NoteTrack query 0x47

ov6 `0x02157EC4` (inside the 73-case dispatcher `0x02157A44`, case 0x47): loops
columns `0..[battleCtx+0x158]-1`, row = `char+0x1E0` (`ldrsb [r2,#0xe0]`), skips
`col == row`, reads **only** cell `+0x04` and `+0x1C` (`[r4,#0x158]`/`[r4,#0x170]`
off the cell), returns 1 if either is nonzero in any non-skipped cell, else 0.
Pure predicate — no value escapes, no stores.

Installed as a note callback in the character-create path (`0x02156CD0 → 0x021553E0`,
`r3 = 0x02157A44` becomes `note+0x70`); invoked by the note engine at `0x02156564`;
the return value gates note-cursor advance (`0x02156568-78`: on true, `note+1 :=
note+2`). The claimed ov4 caller `0x02159BB8` is an **aliasing phantom**
(jus-query-xref-overlay-aliasing-pti9 class): ov4's `0x02157A44` is a different,
unrelated 24-byte function.

`char+0x1E0` indexes the same per-participant slot space as `[battleCtx+0x158]`/`+0x15C`
(clamped as a count at `0x02085510`; indexes the per-slot table at `battleCtx+0x4C`,
`0x02158F74`) — which forces "row = participant slot, skip self" on the reader side.

## 3. The real damage staging: the record's twin 18-word arrays

The same pair body also accumulates into the **victim's record**, and this — not the
manager array — is the collision→damage hand-off:

- **HP array:** `record+0xA4`, 18 words (idx 0..17); **SP array:** `record+0xEC`
  (i.e. `+0xA4+0x48`), 18 words. Writer `0x020812C8-0x020812F4`; index from
  `0x02081A58(elemAttacker+0x14, elemAttacker+0x18)` — the full 0..17 helper space
  (16 = "bits 9/10/13" bank, 17 = "low byte empty" sentinel).
- Stage 5 (`0x020821F8`, 17 passes, `cmp r6,#0x11`) sums idx 0..16 only →
  `record+0x134` (HP) / `record+0x138` (SP).
- Consumers: `0x0215AC08` reads `+0x134` (halved `asr #1` under two predicates,
  `0x0215AC28`) → `bl 0x020783B8` (HP drain, negating trampoline); `0x0215AC5C`
  reads `+0x138`, negated → `bl 0x020781E4` (SP apply, sign-preserving).
  Bit 0x40 of `scratch+0x40` adds `0x02078660(target,1,1)` on that path.

**The B11 residue, explained.** `+0xE8`/`+0x130` are **slot 17** of the twin arrays —
the "empty class nibble" sentinel — deliberately outside the 0..16 fold. They are read
only by the bit-11-gated second application path: `0x02158B94` resolves the record via
`[char+0x1A8]+0x10`, gates on `scratch+0x40 & 0x800` (`0x02158BA0`), then negates and
applies `+0xE8` (HP, `bl 0x020783CC`) and `+0x130` (SP, `bl 0x020781E4`) at
`0x02158BA8-0x02158BCC`. This is why every landed-hit capture read `+0xE8 == 0` while
`+0x134` carried the damage (damage.md Step 6, `jus-qr8`/`jus-w42`/`jus-m92n`): those
hits staged into slot 0, and slot 17 only fills when the attacker element's class low
byte is empty. "Who sets bit 11" (G6) remains open; the consumer side is now fully
mapped.

Also: `record+0x140` is flushed at `0x0215A308 → bl 0x020783CC` (non-negating gain
trampoline) and `record+0x144` at `0x0215A324 → bl 0x020781E4` — the pending
HP-gain/SP-delta pair.

## 4. Class nibble sources (writer side)

Element `+0x14/+0x18/+0x1C` are copied from the record's `+0x34/+0x38/+0x3C` at
element construction (`0x0207D498-0x0207D4C0`), then OR-extended from three 32-entry
tables indexed by CollisionEntry `+0x08` property-word bits (`T14 @ 0x0209FD44`,
`T18 @ 0x0209FDC4`, `T1C @ 0x0209FE44`; per-builtin-box-id twins at
`0x0209FB84/BC/F4`). Only `T14` writes the low nibble: entry bits 0,1,12,14 →
`elem+0x14` bits 2,3,0,1 — a one-hot 4-way class nibble. Corpus cross-check
(2351 non-terminator records): the nibble is absent in 2158 (92%) and non-one-hot
in 12. Runtime propagation exists (`record+0x150/+0x154` ORed with the *partner*
element's flags at `0x02081564-0x020815E4`; `record+0x34/+0x38` OR-extended via
`0x0207CFE0`/`0x0207D064` from `[record+0x150]` low byte at ov6 `0x02165F9C`).

## 5. Per-frame clear is partial (anomaly)

`0x0207FA50` clears only `0xC0` bytes (`memset(manager+0x154, 0, 0xC0)` via
`0x020517FC`) — cells `[0][0..3]` only. No second clear for cells 4..15 was found
(`search-op-imm 340` exhausts `#0x154` sites). The record's scratch is cleared
**fully** every frame (`0x0207F8AC`, `memset(record+0xA4, 0, 0xD0)`).

## 6. Unresolved (with falsification tests)

- **U1 — index = participant slot or hitbox class?** The one load-bearing ambiguity.
  Reader side forces participant slot (`char+0x1E0`, skip-self). Writer side derives
  both indices from one-hot nibbles of the element flag words, whose authored source
  is absent in 92% of records. If class, the reader reads a different bin space than
  the writer fills. *Falsify:* GDB watchpoint on `manager+0x154` during a landed hit;
  derive `(row,col)` and compare with both characters' `+0x1E0`.
- **U2 — no per-frame clear for cells 4..15.** *Falsify:* read `manager+0x214`
  (cell `[1][0]`) on consecutive idle frames; persistence ⇒ the partial clear is real.
- **U3 — writer completeness.** A writer computing `((row<<2)+col)*0x30` evades the
  stride scan. *Falsify:* poke `manager+0x158` to a sentinel, step one frame with a
  known contact.
- **U4 — the five routing classes' meaning.** Only bit patterns proven; bits
  suggestive of guard/status flags (`0x021656F8 tst #0x600`, `0x0215AD9C tst
  #0x3000000`) but no naming evidence. *Falsify:* instrument `elem+0x14/+0x18` on a
  normal / guarded / projectile hit.
- **U5 — `moveData[+5]` authored intent.** Runtime role (SP damage) proven; exporter
  name `durationMult`. *Falsify:* poke the byte, read the SP gauge delta.
- **U6 — reachability of the contact-array writes.** The victim-gate
  `elem+0x14 & 0x37F0` excludes victims whose record carries the installer-seeded
  `+0x34` bit 8 (`arg2 = 0x100` at the two ov6 character sites); the class nibble is
  absent in most authored records, routing accumulation to slot 17 (inside the
  record-array region at `+0x154+row*0xC0+0x330` when row > 0). Shipped latent bug or
  runtime nibble we have not located — unresolved. *Falsify:* watch `manager+0x484`
  and `manager+0x158` during an ordinary character-vs-character hit.

## 7. Reachability summary

Written only from arm9 stage 1 `0x02080F14` (chain `0x0207F480 → 0x02080C28 →
0x02080F14`); folded by stage 5 `0x020821C4`; read only by ov6 `0x02157EC4`
(NoteTrack query 0x47, installed `0x02156CD0 → 0x021553E0`, invoked `0x02156564`,
result gating note advance at `0x02156578`). HP/SP application never reads the array.
