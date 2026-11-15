# JUS damage calculation — confirmed spec

Canonical reference for reimplementing battle damage in Jump Ultimate Stars
(`jus.nds`, AJUJ). Everything here is backed by static disassembly of
`arm9.bin`/`arm9_ov06.bin` plus live-RAM measurements, cited inline. Tracker items
(the issue tracker) hold the raw measurement logs. The routine at the center is
**arm9 `0x020823E4`** (680 bytes), the damage formula.

> Avoid `docs/research/Battle-Engine-Map.md` as a source — parts of it are
> taint-flagged. This spec cites findings journal entries and
> runtime-confirmed tracker items instead.

## Navigate this reference

| Topic | Section |
|---|---|
| Damage model | [1](#1-overview) |
| Runtime and data layout | [2](#2-data-structures-field-level) |
| HP representation | [3](#3-hp-encoding) |
| Formula pipeline | [4](#4-the-algorithm-step-by-step-0x020823e4) |
| Ability-to-gate loading | [5](#5-how-the-gate-word-gets-filled-load-time) |
| Boundary behavior | [6](#6-edge-cases) |
| Regression vectors | [7](#7-test-vectors-cross_confirmed-measurements) |
| Gaps, follow-ups, and retractions | [8](#8-open-questions) |

---

## 1. Overview

One hit's damage is computed in a single routine, `0x020823E4`, called from
the collision pipeline at `0x02081280` (inside `0x02080F14`) with the result
returned through an out-parameter on the stack
([p208](../research/findings/p208-damage-formula-0x020823E4.md)).

The shape of the computation:

```
base   = signed byte, the move's base damage        (8.8 fixed point after <<8)
r5     = base<<8, scaled by two attacker multipliers and summed with
         a nature term and quarter-step gate terms  (all additive into r0)
out    = (r5 + r0) >> 2                             (8.8 -> raw HP units, 1/64)
```

Key facts an implementer must not get wrong:

- All internal math is **8.8 fixed point** (`0x100` = 1.0).
- Nature bonus and the ±25% gates land in **one accumulator and are
  additive with each other**, not multiplicative. Nature advantage with one
  resist gate is 1.25×, not 1.5 × 0.75
  ([p216](../research/findings/p216-nature-is-read-in-the-damage-path.md)).
- There is **no flat subtraction** anywhere; the historical "flat −2.0"
  reading was an artifact of base 8, where −25% happens to equal −2.0
  ([p209](../research/findings/p209-damage-formula-decoded.md),
  tracker item `jus-flat-refuted-with-attribution-doi`).
- With nothing armed, **displayed damage equals the base byte exactly**
  (tracker item `jus-unreduced-baseline-measured-7dj`, 50 stops, 7 distinct bases).

## 2. Data structures (field level)

### 2.1 The hit element (0x2C bytes, `arg1` = `sl`)

The element describing the contact. The move's data hangs off `arg1`; `arg1`
is the attacking side ([p213 §"Which side is r8"](../research/findings/p213-flag-word-is-plus-0x44-ability-10-sets-bit-5.md)).

| offset | type | meaning |
|---|---|---|
| `+0x0C` | ptr | attacker-side ColPrm scratch (start of the `+0x68` walk chain) |
| `+0x10` | ptr | move-data block (see below) |
| `+0x14` | u8 | element flags; `& 0xF0` feeds the bits-6/14 element condition |

Move-data block at `[elem+0x10]`:

| offset | type | meaning |
|---|---|---|
| `+0x00` | u8 | element kind; values 4 or 5 bypass the second test on gates 6/14 |
| `+0x01` | u8 | **hit type**; value 6 = launcher: the knockback bytes below are scaled by the victim's HP-quarter band and by the weight gate bits (`physics.md` §4.2, evidence `research/feel-captures/weight-hunt-2026-09-01c/`) |
| `+0x04` | s8 | **base damage byte** (`ldrsb` at `0x02082428`) |
| `+0x0C` | s8 | **knockback X base**; impulse = `kbX × 128 × M × F` raw (`0x020817F0`–`0x0208182C`; Kenshin X finisher kbX = ±25, its eight small hits ±6) |
| `+0x0D` | s8 | **knockback Y base**; impulse = `kbY × (−158) × M × F × 223/256` raw (Kenshin X finisher kbY = 6) |
| `+0x0E` | s8 | **class index**, packed byte: low 6 bits = class (range-checked 0..15 by the routine; `0x3F` is the "none" reset sentinel), bit 7 a separate flag ([p214](../research/findings/p214-class-index-is-a-packed-byte.md)). This byte is the collision damageFlags category (tracker item `jus-class-index-is-damageflags-mx5`). |

The base byte is design-time data read from chr/col `+4` (`ldrsb` at
`0x02082428`), with no table lookup. The older `jpower.damage1 / 5` reading is
retracted (`jus-jpower-retraction-cguk`); jpower.bin is the koma price table (`jus-jpower-koma-price-table-uh9o`).

### 2.2 The ColPrm scratch objects (`r4` = attacker side, `r8` = other side)

`r4` starts at `[elem+0x0C]` and the prologue walks `r4 = [r4+0x68]` while
`[r4+0x68] != 0` and bit 9 of `[r4+0x40]` is clear. `r8` is the participant
not supplying the move; both were named live in one read
(`r4 = 0x0220FC3C`, `r8 = 0x0220FDC4`, tracker item
`jus-gate-word-read-live-0x2010-nbz`).

| offset | type | side used | meaning |
|---|---|---|---|
| `+0x00` | ptr | — | `next` in a doubly-linked list of scratches; the player side is the head and the opponent side is the tail (`next` = 0). Not a vtable slot (tracker item `jus-9ie`). |
| `+0x04` | ptr | — | `prev` in the same list (tracker item `jus-9ie`). |
| `+0x40` | u32 | both | status flag word. Bit 30 = nature bypass (either side forces nature factor to 1.0); bit 25 tested in prologue; bit 9 stops the `+0x68` walk. Dynamic during a hit (read `0x01000018` mid-hit vs `0x00000008` at rest). |
| `+0x44` | u32 | `r8` | **the gate word** — the ±25% mask (see §4). Note: `+0x44`, not `+0x40` (tracker item `jus-gate-word-is-r8-0x44-fnz`). |
| `+0x50` | ptr | — | handler slot, held as a function pointer. Initialised to the arm9 empty stub `0x0207D9A0` (`bx lr`) by the same instruction pair that clears bit 9 of `+0x40` (`0x0207CB24`–`0x0207CB38`), so the flag bit and the slot are maintained together; read live as `0x0207D9A0` mid-battle (tracker item `jus-9ie`). |
| `+0x68` | ptr | `r4` | chain link for the prologue walk |
| `+0xA4` | array | `r4` | **HP pending-damage array, 18 words (idx 0..17)**: per-frame contribution accumulator (the formula's out-param is accumulated here by the caller, [p208](../research/findings/p208-damage-formula-0x020823E4.md)). Stage 5 sums idx 0..16 → `+0x134`. **Idx 17 = `+0xE8`, the "empty class nibble" sentinel** — excluded from the fold, read only by the bit-11-gated path (`0x02158BA8`, [contact-array-semantics-settled.md](../research/findings/contact-array-semantics-settled.md)) |
| `+0xEC` | array | — | **SP pending array, 18 words**, twin of `+0xA4` (accumulates `s8(moveData[+5])<<8`, the move's SP/meter damage; exporter's `durationMult` label for that byte is wrong). Fold → `+0x138`; idx 17 = `+0x130` (bit-11 path). Writer `0x020812C8-0x020812F4` |
| `+0x134` | s32 | — | folded HP total (stage 5, 17 passes); consumer `0x0215AC08` (halved `asr #1` under two predicates) → HP drain `0x020783B8` |
| `+0x138` | s32 | — | folded SP total; consumer `0x0215AC5C`, negated → SP apply `0x020781E4` |
| `+0x140` | s32 | — | pending HP gain, flushed `0x0215A308 → 0x020783CC` (non-negating) |
| `+0x144` | s32 | — | pending SP delta, flushed `0x0215A324 → 0x020781E4` (the guard/absorb arithmetic at `0x020814D8-0x02081500` lands here) |
| `+0x175` | u8 | both | packed **nature byte**: three candidate 2-bit fields (bits 1:0, 3:2, 5:4). Column = selected field of `[r4+0x175]` (selector by flags at `0x020824A4`/`0x020824B4`); row = `[r8+0x175] & 3`. |
| `+0x184` | u16 | `r4` | multiplier **f1**, 8.8 (1.0 = `0x100` by default; **runtime-confirmed** ×1.20 when 底力 (ability 14) + attacker HP < 25% of max, §8) |
| `+0x186` | u16 | `r4` | multiplier **f2**, 8.8 (**runtime-confirmed** unconditionally 1.0 in every case tested, §8) |

### 2.3 The character struct (HP lives here, not in the scratch)

From [HP-Struct-From-Disassembly.md](../research/HP-Struct-From-Disassembly.md):

| offset | type | meaning |
|---|---|---|
| `+0x16` | s16 | **max HP**, clamped to `0x4000` (= 256.0 displayed) |
| `+0x18` | s16 | **current HP** |
| `+0x41` | u8 | `chr_b` index |
| `+0x49` | u8 | regen byte (poke to 0 to disable regen in tests) |

Reached from the battle object as `char = [battleObj+0x56C]`
(p173, cited in that doc).

## 3. HP encoding

- HP and damage are stored in **raw units of 1/64 displayed HP**:
  `displayed = raw / 64`. Confirmed two ways: the `0x4000` max-HP cap = 256.0,
  and the routine's own `asr #6` scale appearing in the arithmetic
  ([HP-Struct-From-Disassembly.md](../research/HP-Struct-From-Disassembly.md),
  [p208](../research/findings/p208-damage-formula-0x020823E4.md)).
- Inside the formula the working unit is 8.8 fixed point (`raw × 4`); the
  final `>> 2` converts 8.8 → raw/64.
- Both HP fields are loaded with `LDRSH` — signed 16-bit.
- Damage is applied by negation: `0x020783B8` is a trampoline doing
  `rsb r1, r1, #0` then tail-calling the HP-apply function
  ([Damage-Path-Codex-Findings.md](../research/Damage-Path-Codex-Findings.md)).
- Known runtime HP addresses for the default dm_battle setup:
  opponent current HP `0x021DF7F0`, player `0x021DF1D4`; read 2 bytes **at**
  the address. Deck-slot current HP follows at `+0x50` strides: player
  `0x021DF224`/`0x021DF274`/`0x021DF2C4`, opponent
  `0x021DF840`/`0x021DF890`/`0x021DF8E0` (tracker item `jus-b4fr`).
  `0x021DF7EE` is max HP — reading it looks like a working
  measurement at full health and cost four sessions
  (tracker item `jus-reading-max-hp-not-current-2jo`,).
  **Re-confirmed live 2026-09-03** on a second character (`jus-p6jm`,
  runtime-report-8-falldown):
  Jotaro's max HP sits at `0x021DF7EE`, two bytes below current HP
  `0x021DF7F0`, clamps at `0x4000` on any poke above it, and is signed —
  poking current HP to `0xE100` (intending 900.0) read back as −128.0 and
  killed the victim on the spot. Poke max HP first, current HP second.

## 4. The algorithm, step by step (`0x020823E4`)

Arguments at the call site `0x02081280`: `r0` = element list, `r1` = the
0x2C hit element, `r2` = one bit from `[ColPrmMan+0x14D]` (selects which
nature table), `r3` = `&out` on the caller's stack
([p208](../research/findings/p208-damage-formula-0x020823E4.md)).

### Step 1 — prologue: resolve scratches, load base

```
0x020823E8  mov   sl, r1            ; the hit element
0x020823EC  ldr   r4, [sl, #0xc]    ; attacker-side scratch
            ; walk: while [r4+0x68] != 0 && !(bit9 of [r4+0x40]): r4 = [r4+0x68]
0x02082420  ldr   r1, [sl, #0x10]
0x02082428  ldrsb r5, [r1, #4]      ; BASE, signed byte
```

### Step 2 — base to 8.8, two scratch multipliers

```
0x0208247C  add  r0, r4, #0x100
0x02082480  ldrh r2, [r0, #0x84]    ; f1 = [r4+0x184]
0x02082484  ldrh r0, [r0, #0x86]    ; f2 = [r4+0x186]
0x0208248C  lsl  r3, r5, #8         ; r3 = base << 8   (8.8)
0x02082490  sub  r2, r2, #0x100     ; f1 - 1.0
0x02082494  mul  r2, r3, r2
0x02082498  add  r2, r3, r2, asr #8 ; r2 = base * f1 / 256
0x0208249C  sub  r0, r0, #0x100     ; f2 - 1.0
0x020824A0  mul  r0, r2, r0
0x020824A8  add  r5, r2, r0, asr #8 ; r5 = r2 * f2 / 256
```

i.e. `r5 = (base<<8) * f1/256 * f2/256`. Each multiplier is applied as
`x + x*(f-1)/256`, which is exact for 8.8 factors
([p209](../research/findings/p209-damage-formula-decoded.md)). Both factors
reset to 1.0 at load. `f1` scales ×1.20 only when the attacker carries 底力
(ability 14) **and** its HP is below 25% of max; `f2` read 1.0 in every case
tested. Writers and the live measurement: §8
(`jus-attacker-multipliers-halving-xls7`).

### Step 3 — nature term (additive, into `r0`)

Selection: column = one of three 2-bit fields of `[r4+0x175]` (bits 1:0,
3:2 or 5:4, chosen by flags at `0x020824A4`/`0x020824B4`); row =
`[r8+0x175] & 3`. Table = `0x0209FF14` if `arg2` (`ColPrmMan+0x14D` bit 0)
is set, else `0x0209FEF4` (`cmp sb, #0` at `0x020824FC`).
**Bypass:** if bit 30 of `[r8+0x40]` or `[r4+0x40]` is set, `0x020824F4`
forces the cell to `0x100` and the tables are never read
([p210](../research/findings/p210-nature-tables-and-prediction-failure.md),
[p216](../research/findings/p216-nature-is-read-in-the-damage-path.md)).

```
0x02082538  ldrsh r3, [r2, r1]      ; cell = s16 table[row*8 + col*2]
0x02082568  sub   r1, r3, #0x100    ; cell - 1.0
0x0208256C  mul   r1, r5, r1
0x02082578  add   r0, r0, r1, asr #8  ; r0 += r5 * (cell - 1.0) / 256
```

Every cell is `0x100` (1.0) or `0x180` (1.5) — the nature system is
**bonus-only**; advantage adds +50% of `r5`, disadvantage adds nothing.
Observed live: `r0 = 512` at `r5 = 1024`
(tracker item `jus-bit5-fired-and-nature-observed-w5n`).

Nature tables (8.8, row = defence category of `r8`, col = attack category
of `r4`; row stride 8 bytes, col stride 2):

```
Table B @ 0x0209FEF4 (arg2 clear)      Table A @ 0x0209FF14 (arg2 set)
      atk0  atk1  atk2  atk3                 atk0  atk1  atk2  atk3
def0  1.0   1.0   1.5   1.0            def0  1.0   1.5   1.0   1.0
def1  1.5   1.0   1.0   1.0            def1  1.0   1.0   1.5   1.0
def2  1.0   1.5   1.0   1.0            def2  1.5   1.0   1.0   1.0
def3  1.0   1.0   1.0   1.0            def3  1.0   1.0   1.0   1.0
```

The two tables are inverse 3-cycles of the 力/知/笑 triangle with なし
(category 3) inert. Category values follow the nature enum in
[Nature-System-Consolidated.md](../research/Nature-System-Consolidated.md)
(0 力, 1 知, 2 笑, 3 なし).

### Step 4 — quarter-step gates (additive, into `r0`)

The gate word is `r2 = [r8+0x44]`, loaded once at `0x02082574` and not
rewritten before the last gate. The class index is
`r1 = ldrsb [[sl+0x10]+0x0E]`, range-checked `0 <= r1 <= 15`; outside that
range **all four class gates are skipped** (legitimate no-class states:
sentinel `0x3F` reads 63, bit 7 set reads negative). The class table at
`0x02092E68` (16 bytes) maps index → category:

```
01 01 02 02 02 02 02 02 02 02 02 02 00 00 00 00
```

Indices 0–1 → category 1, 2–11 → category 2, 12–15 → category 0 (immune to
class gates). Six gates, each adding or subtracting exactly **25% of `r5`**
(`(r5 << 6) >> 8 = r5/4`), all conditional
([p213](../research/findings/p213-flag-word-is-plus-0x44-ability-10-sets-bit-5.md)):

| gate addr | bit of `[r8+0x44]` | extra condition | effect on `r0` |
|---|---|---|---|
| `0x020825A8` | 14 (`0x4000`) | element cond.* | **+** r5/4 |
| `0x020825DC` | 6 (`0x40`) | element cond.* | **−** r5/4 |
| `0x02082608` | 12 (`0x1000`) | class table byte == 1 | **+** r5/4 |
| `0x02082624` | 13 (`0x2000`) | class table byte == 2 | **+** r5/4 |
| `0x0208264C` | 4 (`0x10`) | class table byte == 1 | **−** r5/4 |
| `0x02082674` | 5 (`0x20`) | class table byte == 2 | **−** r5/4 |

\* element condition: fires if `[[sl+0x10]+0]` is 4 or 5 (bypasses the
second test), otherwise requires `[sl+0x14] & 0xF0`.

Gate arithmetic, verbatim:

```
0x02082644  lsleq r4, r5, #6
0x0208264C  subeq r0, r0, r4, asr #8   ; r0 -= r5/4
```

Live confirmations: bit 4 with category 1 fired for −512 at `r5 = 2048`
while an armed bit 13 was correctly **blocked** by the category mismatch
(tracker item `jus-gate-word-read-live-0x2010-nbz`); bit 5 with category 2 fired at
the pre-registered value (tracker item `jus-bit5-fired-and-nature-observed-w5n`).
**Bit 6 (ability 13 見切り, element condition) live-confirmed 2026-09-12**
(`jus-ehcp`): breaking one instruction past the kind-byte load
(`0x02082588`, so `r4` already holds `moveData+0x00`) on a carrier
(`chr_b` 62 Raoh, gate word `0x0040`) and a non-carrier (`chr_b` 15 Nami,
gate word `0x8100`, bits 8/15 unrelated to damage) receiving the identical
attacker/moveset sequence: every kind-5 hit's captured `(r2, r4, r5)` fed
back through this section's own arithmetic reproduced the measured
aggregate HP delta exactly on both victims (2592 raw / 40.500 displayed on
Raoh, 2688 raw / 42.000 on Nami), and the shared kind-3 hit landed
full-damage on both. See
the RESULTS doc
and the extended
[static finding](../research/findings/special-damage-resistance-passive-static.md)'s
"Live" section.

The routine also builds a **result flag word** alongside: `orreq r3, r6, #4`
/ `lsleq r3, r3, #0x10` at `0x0208263C` sets bit 2 = "resisted", returned in
`r0` at `0x02082680`. Do not mistake it for a damage value
([p211](../research/findings/p211-damage-formula-end-to-end.md)).

### Step 5 — final combine and output

```
0x02082678  add r0, r5, r0     ; scaled base + (nature term + gate terms)
0x0208267C  asr r1, r0, #2     ; 8.8 -> raw/64
0x02082684  str r1, [fp]       ; the out-parameter
```

So: **`out_raw = (r5 + r0) >> 2`**, where `r0` is the signed sum of the
nature term and every gate that fired. The caller accumulates `out` into a
per-frame array at `scratch+0xA4` (cleared every frame), from which the HP
drain is eventually applied. The confirmed residue path is described in
Step 6 ([p208](../research/findings/p208-damage-formula-0x020823E4.md)).

### Step 6 — accumulate the residue before the HP consumer

The formula returns its result through `sp+0x4C`. Stage 1 of the collision
pipeline adds that result to the per-frame array at `scratch+0xA4`:

```asm
0x020812C8  ldr  ip, [r8, r0, lsl #2]   ; previous array term
0x020812CC  ldr  r3, [sp, #0x4c]         ; formula result
0x020812D4  add  r3, ip, r3              ; accumulate
0x020812DC  str  r3, [r8, r0, lsl #2]    ; r8 = scratch+0xA4
```

The store address reported by the watchpoint was `0x020812E4`. ARM
watchpoints report the storing instruction eight bytes ahead, so the actual
store is `0x020812DC` (`jus-1rm`).

The array contains 17 words from `scratch+0xA4` through `scratch+0xE4` and
is cleared each frame. In the controlled two-hit capture, only slot 0 at
`scratch+0xA4` was nonzero. Each term was `384`, its previous value was `0`,
and the resulting sum was `384`. Therefore `scratch+0x134` is the final sum
for that hit, not an intermediate value and not a sum containing a negative
reduction term (`jus-kfy`).

Stage 5 writes that final sum at arm9 `0x020821F8`. The function builds an
interior pointer at `scratch+0xA4`, reads its `+0x90` field, and adds the array
terms. Because `0xA4 + 0x90 = 0x134`, the store writes `scratch+0x134` even
though `0x134` never appears as an encoded offset (`jus-iza`).

The pending-damage consumer reads `scratch+0x134` at `0x0215AC08`. The same
controlled capture read `384` there while `scratch+0xE8` remained `0`; an
earlier read at `0x0215A978` showed the same ordering (`+0x134 = 384`,
`+0xE8 = 0`) (`jus-qr8`). The field is already reduced before the ov6
per-character update runs at all: on two landed 6.000 hits, `+0x134` read
`384` (not `512`) at `0x02156DE8` — the first instruction after `r4` is
loaded — and at three later points in the same function, `+0xE8` staying `0`
throughout, and the two fighters resolved to two distinct scratches as a
validity check (`jus-w42`).

An end-to-end trace then connected the stages in one GDB session. Four landed
hits passed the independent HP positive control. On each hit, the formula
oracle at `0x02082584` was followed by the stage-1 store, the stage-5 store,
the ov6 consumer, and the negative HP delta at `0x02078488` (`jus-m92n`; full
conditions and values are in
[`B11-Residue-Transfer-Trace-Results.json`](../research/B11-Residue-Transfer-Trace-Results.json)).

For the opponent scratch `0x0220FDC4`, stage 1 wrote `384` to `0x0220FE68`
(`scratch+0xA4`) with a zero previous value. Stage 5 then had `r0 = 384`
immediately before its store to `0x0220FEF8` (`scratch+0x134`). The consumer
loaded `384` from that field. Its call at `0x0215AC70` reached the drain
trampoline, which negated the magnitude before `0x02078488` applied `-384` to
current HP. This closes the producer-to-consumer transfer question.
`scratch+0xE8` stayed zero throughout the observed path and is not the damage
carrier.

**Why `+0xE8` reads zero, settled 2026-09-09**
(`jus-contact-array-element-semantics-d7w8`,
[contact-array-semantics-settled.md](../research/findings/contact-array-semantics-settled.md)):
`+0xE8` and `+0x130` are **slot 17** of the twin 18-word accumulator arrays —
the index the class-nibble helper `0x02081A58` returns for "attacker element
class low byte empty." Slot 17 is deliberately outside the stage-5 fold
(which sums idx 0..16), and is read only by the second application path:
`0x02158B94` resolves the record via `[char+0x1A8]+0x10`, gates on
`scratch+0x40 & 0x800` (bit 11, damage pending), then negates and applies
`+0xE8` (HP, `bl 0x020783CC`) and `+0x130` (SP, `bl 0x020781E4`) at
`0x02158BA8-0x02158BCC`. The observed hits staged into slot 0 (`+0xA4`), so
`+0xE8` was legitimately empty. "Who sets bit 11" remains open (collision.md
G6).

### Control-flow summary

1. Resolve `r4` via the `+0x68` walk; test bit 25 of `[r4+0x40]`.
2. Load base; `r5 = (base<<8) * f1/256 * f2/256`.
3. Nature: bit-30 bypass check → selector flags → 2-bit row/col → table
   pick by `arg2` → additive term into `r0`.
4. Load gate word `[r8+0x44]` and class index; range-check 0..15.
5. Six conditional ±r5/4 adjustments into `r0`; build result flags.
6. `*out = (r5 + r0) >> 2`; return flag word.

## 5. How the gate word gets filled (load time)

Abilities never reach the damage routine directly — they are compiled into
`[+0x44]` bits once, which is why every mid-battle ability-array poke
measured zero effect ([p213](../research/findings/p213-flag-word-is-plus-0x44-ability-10-sets-bit-5.md),
[Damage-Path-Codex-Findings.md §2](../research/Damage-Path-Codex-Findings.md)):

- On-disk ability list: `chr_b` record `+0x03`, five sparse bytes
  (tracker item `jus-ondisk-ability-list-at-chrb-0x03-kfc`).
- Load-time loader `0x0215FB3C` caches ability IDs as a **bitset** at
  `battleObj+0x128` (bit index = ability ID).
- ov6 `0x02157114` reads that bitset once and assembles **both** the gate
  word and the packed nature byte (from record bytes `+3/+4/+5`)
  (tracker item `jus-one-routine-assembles-both-u24`). It drives helper
  `arm9 0x02083BE0`: `[target+0x44] |= tbl[variant-1][maskIdx]` (or clears
  both variants when `variant == 0`), with mask tables
  `0x02092E78` = bits 4..9 (subtract) and `0x02092E90` = bits 12..17 (add).
- The ability→(maskIdx, variant) mapping is a 12×3-byte table at ov6
  `0x021710BC` — six subtract/add couples, e.g. ability 9 → bit 4, ability
  12 → bit 13. Confirmed end-to-end live: bitset for abilities
  [9, 25, 12, 14] predicted `[r8+0x44] = 0x00002010`, and it read exactly
  that; writer object and the routine's `r8` are the same object
  (tracker item `jus-gate-word-read-live-0x2010-nbz`).
- Timing: the gate word is not settled at frame 0, and it is **not** a
  one-time assembly either — the assembler re-runs on each KO/respawn cycle
  (the bitset is re-cached in place, tracker item `jus-q2y`), so in active play the
  word **churns** between `0` and its assembled value. Tracked at 40-frame
  intervals in `dm_battle` it cycled `0 → 0x2010 → 0 → 0x2010 → 0`. A
  quiescent savestate such as `fight_base` holds it stable from +2 to +500
  frames. Sample it where the consumer reads it, not on a settling check: two
  samplings of the churning value each produced a clean, different,
  plausible story (tracker item `jus-gate-word-assembled-after-load-68g`, whose own
  "~30–80 frames after load, then stable" headline is retracted in its
  comments).

Note the damage routine reads only mask indices 0–2 (bits 4/5/6 and
12/13/14). **Mask index 3 is the weight pair**: bit 7 (ability 23, 重量級
Heavyweight) halves launcher knockback and bit 15 (ability 24, 軽量級
Lightweight) multiplies it by 1.5, read at arm9 `0x02081844`–`0x02081860`
inside the hit handler `0x02080F14` (`physics.md` §4.1; poke-verified on
Luffy, evidence `research/feel-captures/weight-hunt-2026-09-01c/`). Bits
8–9 / 16–17 (abilities 16–19) are still unlocated.

## 6. Edge cases

- **Base is a signed byte.** Bases are integral by construction; a base of
  0 is real (measured, produces 0 damage).
- **Class index out of 0..15** (sentinel `0x3F`, or bit 7 set → negative):
  all class gates skipped; not an error state
  ([p214](../research/findings/p214-class-index-is-a-packed-byte.md)).
- **Class categories 0 (indices 12–15)** match neither gate pair — immune
  to both class-gated resist and weakness.
- **Nature bypass:** bit 30 of either scratch's `+0x40` forces factor 1.0.
- **Multi-contact moves:** the routine runs once per contact. Goku's UP+B
  is two contacts of base 3, summing to 4.500 displayed
  (tracker item `jus-flat-refuted-with-attribution-doi`). A before/after HP
  diff on a multi-contact move sums the contacts. Log per frame and take the
  *first* drop. (An earlier jpower-pairing argument for this, tracker item `jus-base-2-is-jpower-damage1-10-mse`,
  is retracted by `jus-jpower-retraction-cguk`.)
- **The formula only runs on landed hits** — 4 hits → 4 stops, 7 misses →
  0 stops; a breakpoint at `0x02082584` is a hit oracle
  (tracker item `jus-first-attributed-measurement-d6u`; the earlier contrary claim
  `jus-formula-bp-not-a-hit-oracle-ve6` is retracted).
- **Downstream of the formula**, on the pending-damage consumer path
  (`0x0215AC00`): the magnitude at `obj+0x134` is **halved** (`asr #1`,
  signed) when either of two predicates is true — **static-only**
  (`jus-attacker-multipliers-halving-xls7`,
  static-damage-loose-ends,
  Codex-agreed): `0x02159A10` returns `obj+0x88 == 0x23` (status id 35) and
  `0x021598D0` returns `obj+0x88 == 0x0B` (status id 11), both reading the
  acting object's status-id field
  ([physics reference](physics.md) §6.2); neither
  status id has an attributed name yet, so "guard/defensive status" stays a
  plausible but unconfirmed reading. The halve is **not** on the ordinary hit
  path: on one landed 6.000 hit (training, items/gimmick/team 0/0/0, heal off)
  the containing routine `0x0215A978` was entered 7991 times — every frame,
  per fighter, from caller `0x02156EB4` — but `0x0215AC1C` was reached once,
  with `r4 = 384` raw matching the measured HP delta exactly, and the `asr #1`
  at `0x0215AC28` fired zero times (tracker item `jus-2fa`). Reasoning from "this
  routine ran" must not assume a damage event. A scripted path at `0x021518D6`
  (one case of a Thumb opcode-dispatch/jump-table function, shared epilogue
  `b #0x215199e`) applies a hardcoded `0x800` raw = **32.0 displayed** via
  the same HP-drain trampoline as `damage.md` §3, to a target resolved
  through an object-table lookup — **static-only**, and neither the
  jump-table index that selects this case nor the caller of the dispatch
  function was traced, so it is not yet shown unreachable in normal play
  ([Damage-Path-Codex-Findings.md](../research/Damage-Path-Codex-Findings.md),
  static-damage-loose-ends).
- **No 1-HP floor** on the drain path: HP reaches raw 0 and a KO follows
  (tracker item `jus-r3i`).
- **Max HP** adds are clamped to `0x4000` (256.0); the adder returns 0 if
  already at cap ([HP-Struct-From-Disassembly.md](../research/HP-Struct-From-Disassembly.md)).
- **A blocked hit adds its whole-unit HP damage to the guard gauge, dropping
  the fraction.** Measured on Kakashi (`jus-kakashi-moveset-map-33lu`,
  [characters/kakashi.md](characters/kakashi.md) "On block"): `B` (0 HP
  damage on hit) adds +8 gauge; `side B` adds +2 then +6 per hit. This is
  consistent with [guard-sp.md](guard-sp.md) §0.5's guard-gauge model; it
  does not change that model, just confirms the add is the integer damage,
  not the raw or displayed value.

## 7. Test vectors (CROSS_CONFIRMED measurements)

All from live RAM with items/gimmick/team = 0, regen disabled, values read
at breakpoint `0x02082584` and cross-checked against actual HP drops at
`char+0x18`. f1 = f2 = 1.0 throughout.

| # | base | r5 | nature term | gates fired | out raw | displayed | source tracker item |
|---|---|---|---|---|---|---|---|
| 1 | 8 | 2048 | 0 | none (gate word 0) | 512 | 8.000 | `jus-unreduced-baseline-measured-7dj` |
| 2 | 8 | 2048 | 0 | bit 4, cat 1: −512 (bit 13 armed, blocked by cat) | 384 | **6.000** | `jus-gate-word-read-live-0x2010-nbz`, `jus-first-attributed-measurement-d6u` |
| 3 | 3 | 768 | 0 | none | 192 | 3.000 | `jus-unreduced-baseline-measured-7dj` |
| 4 | 3 | 768 | 0 | bit 4, cat 1: −192 | 144 | 2.250 (×2 contacts = 4.500 measured) | `jus-flat-refuted-with-attribution-doi` |
| 5 | 4 | 1024 | 0 | none | 256 | 4.000 | `jus-unreduced-baseline-measured-7dj` |
| 6 | 4 | 1024 | 0 | bit 5, cat 2: −256 | 192 | 3.000 | `jus-bit5-fired-and-nature-observed-w5n` |
| 7 | 4 | 1024 | +512 (1.5 cell) | bit 5, cat 2: −256 | 320 | 5.000 | `jus-bit5-fired-and-nature-observed-w5n` |
| 8 | 7 | 1792 | 0 | one −25% gate | 336 | **5.250** (3 identical reps) | `jus-reading-max-hp-not-current-2jo` |
| 9 | 0,2,5,28 | base<<8 | 0 | none | base<<6 | = base exactly | `jus-unreduced-baseline-measured-7dj` |

Static-only worked example for nature at full strength
([p216](../research/findings/p216-nature-is-read-in-the-damage-path.md)):
base 8, advantage cell 1.5, no gates → `r0 = (2048·0x80)>>8 = 1024`,
`out = (2048+1024)>>2 = 768` = **12.000** — matching the owner's live-play
8 → 12 observation.

Note on vector 8: the move is unattributed (base inferred as 7 from
5.250/0.75 being integral), but the drop was measured three times under
controlled conditions; it is the vector that refuted the flat model on
integrality alone.

Degeneracy warning for test authors: base 8 is the point where
"−25%" and "flat −2.0" coincide (both give 6.000). Use base 3 or 4 vectors
to discriminate models. The gate/nature lattice collides at base 8 too: since
the terms are additive, 10.000 is reachable both as "add gate + neutral
nature" and as "no gate + 1.5 nature", and 6.000 both as "−25% gate + neutral
nature" and as "bit 5 fires on an id-10 target". Enumerate the lattice for the
chosen base before the run and pick a predicted value only one mechanism can
produce, or add a reading (the nature term at `0x02082584`, the class byte)
that separates them (tracker item
`jus-nature-term-was-zero-and-lattice-collides-if2`).

## 8. Open questions

Marked **OPEN** deliberately — do not treat as settled, do not guess:

- **OPEN — what sets the gate bits in `[r8+0x44]` beyond the ability path.**
  The ability→bit chain via ov6 `0x02157114` / `0x02083BE0` is confirmed for
  the observed bits, but only 2 of the 12 table rows have been exercised
  (bit 4 naturally, bit 5 poked); ability 10 → bit 5 specifically is
  untested (`jus-bit5-ability-10-untested-mvk`, cited in
  [p213 appendix](../research/findings/p213-flag-word-is-plus-0x44-ability-10-sets-bit-5.md)),
  and whether anything other than abilities (rules, koma adjacency, status)
  writes gate bits is unknown. What *is* known: other writers touch
  non-gate bits of the same word. `0x02080988`–`0x020809A0` sets **either**
  bit 20 or bit 21 of `[+0x44]`, mutually exclusive, selected by bit 8 of
  `[r1+0x14]`; neither is a mask-table bit and neither is read by the class
  gates, so a live gate word such as `0x00202010` is the usual `0x2010`
  plus an unrelated flag rather than an anomaly (tracker item
  `jus-bit5-armed-no-deck-needed-zp5`).
- **OPEN — which gate produced the −25% observation** in vector 8 (the
  5.250 reps): the character/move was never attributed, so bit 4 vs bit 6
  vs another −25% source is unresolved.
- **OPEN — the ability→damage-flag load-time link** as a single end-to-end
  observation: the natural route (ability arrives via koma append, bit
  arms, gate fires on a matching-class element in one capture) has not been
  demonstrated; the poked-gate and natural-bit halves exist separately
  (tracker item `jus-bit5-fired-and-nature-observed-w5n`).
- **CLOSED 2026-09-03 (`jus-b3k2`, `jus-qd8s`) — the bench-regen mechanism.**
  [physics.md](physics.md) §5 records benched regen at +1 raw HP/frame; run 9
  (runtime-report-9-regen-landing
  §2) found the routine: arm9 **`0x02077D40`** ticks every koma in the
  player's deck every frame off the flag word at `koma+0x3C` (= slot record
  `+0x24`), and picks one of three branches:

  | branch | condition | amount | store |
  |---|---|---|---|
  | bench regen | flag bit `0x0001` clear (koma not on the field) | `koma+0x49` | `0x02077E50` |
  | auto-recover (自動回復) | flag bit `0x0001` set | `koma+0x4A` | `0x02077E08` |
  | KO revive | flag bit `0x1000` set | `koma+0x49 << 1` | `0x02077DA4`, clears `0x1000` at full |

  All three clamp to `koma+0x16` (max HP). `koma+0x49` reads **1** on every
  real battle character measured (Taikoubou, Momotaro, Yusuke, Jotaro, Sanji,
  Kenshin, Lenalee) and **0** on the non-battle helper `chr_b` 118 — so bench
  regen is a **per-character authored byte**, not an engine constant, and it
  is not gated by the 自動回復 menu setting at all: `koma+0x4A` (the on-field
  auto-recover byte) read 0 in every state, matching "OFF," and is an
  independent field from the bench-regen byte by construction — the two rates
  cannot be compared as if one setting controlled both. Regen starts the
  frame a koma is benched with no grace period, stops the exact frame it
  becomes active again, and resumes the frame after it leaves. A live KO'd
  koma gets a `+2`/frame revive ramp (double `koma+0x49`) instead of `+1`,
  ending naturally when the flag's `0x1000` bit clears at full HP. Four
  falsification pokes (amount → 5, amount → 0, auto-recover byte on the
  active koma → 3, a benched koma poked to max − 100) all landed. Any damage
  figure computed as start-minus-current across a character switch must
  subtract this: a live fight run measured **+716 raw = +11.2 displayed HP**
  of bench regen on one benched leader over 820 frames.

**f1/f2 writers — runtime-confirmed 2026-09-03** (static chain Codex-agreed,
then measured live, table below; `jus-attacker-multipliers-halving-xls7`,
static-damage-loose-ends).
Two writers found for `+0x184` (f1) / `+0x186` (f2) on the ColPrm scratch:

- **Reset to 1.0** at arm9 `0x0207CA84`–`0x0207CA9C`: both fields forced to
  `0x100` alongside other fixed-offset resets — read as a load-time/reset
  default, not a condition.
- **f1 conditionally scaled ×1.20**, ov6 `0x02158D64`–`0x02158E08`: gated on
  bit 14 of the ability bitset `[sl+0x128]` **and** a runtime predicate
  `0x020784E4([sl+0x1b4], 0x19)` (id `0x19` = 25). f2 is unconditionally
  forced back to `0x100` in the same block, never scaled. Ability bit 14 is
  底力 ("Attack-Up at low HP", helpers.md id 14) and status id 25 matches the
  25%-of-max-HP query guard-sp.md §1.1 already uses elsewhere, so **f1 =
  ×1.20 when the attacker carries 底力 and its HP is below 25% of max** —
  static, Codex-agreed on the pointer chain, the bit test and the
  `r4×120/100` arithmetic.

  **Runtime-confirmed 2026-09-03** (`jus-attacker-multipliers-halving-xls7`,
  runtime-report-2
  E3). `pc-kenshin-npc-luffy-dark-tournament`, P1 Kenshin, three identical
  jabs per run, poking `obj+0x128 |= 0x4000` (bit 14) and Kenshin's HP record
  independently (owner, 2026-09-03: a flat damage increase at low health
  matches how it feels in play):

  | condition | f1 (`M+0x184`) | victim HP drop ×3 (raw) |
  |---|---|---|
  | control (neither) | `0x0100` = 1.000 | 336, 336, 336 |
  | bit 14 AND HP < 25% of max | `0x0133` = 307/256 = 1.1992 | 403, 403, 403 |
  | bit 14 only, full HP | 1.000 | 336, 336, 336 |
  | HP < 25% only, no bit | 1.000 | 336, 336, 336 |

  f1 scales ×1.20 **only** when both conditions hold; either alone leaves it
  at 1.000. `0x0133` = 307 = `trunc(256·120/100)`, matching the static
  `r4×0x78/0x64` read exactly, and `336·307/256 = 402.9 → 403` reproduces the
  measured damage. `f2` (`M+0x186`) read `0x0100` = 1.000 in every frame of
  every run, confirming the unconditional-1.0 reading. Untested: 底力 carried
  natively (not poked) and whether the predicate's `0x19` operand is read as
  a status id rather than just "25 percent".

Other loose ends (not required for reimplementation of the core formula):
which nature-table *cell* the selector picks (the 1.5 value is confirmed by
the term, not by reading the inputs — tracker item
`jus-nature-not-bypassed-selector-confirmed-zh2` confirmed the selector
decode but the per-cell map is inferred); consumers of gate bits 7–9/15–17;
what writes `elem+0x0E`.

### Footnoted retractions (do not resurrect)

- "Nature does not affect damage" (`jus-nature-does-not-affect-damage-0c6`,
  tainted): the byte-poke null had scope problems; nature **is** read, as a
  2-bit field on the scratch copy
  ([Nature-System-Consolidated.md banner](../research/Nature-System-Consolidated.md)).
- "Flat −2.0 reduction" ([../research/archive/Damage-Reduction-Is-Flat.md](../research/archive/Damage-Reduction-Is-Flat.md)):
  superseded by the proportional −25% gates
  (tracker item `jus-reduction-is-quarter-multiplier-xk1`).
- "Gate word at `[r8+0x40]`": corrected to `+0x44`
  (tracker item `jus-gate-word-is-r8-0x44-fnz`).
- "Class-1 gate is unconditional": all six gates are conditional
  ([p213](../research/findings/p213-flag-word-is-plus-0x44-ability-10-sets-bit-5.md)).
- "Formula breakpoint is not a hit oracle"
  (`jus-formula-bp-not-a-hit-oracle-ve6`): retracted; the evidence was a
  max-HP read (`jus-reading-max-hp-not-current-2jo`).
