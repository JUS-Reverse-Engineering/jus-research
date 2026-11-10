# AI reachable-behaviour taxonomy — `jus-xkxa`

**Status: partial map, deliberately.** The spine (how the CPU picks a behaviour at
all) is **measured and closed**. The per-behaviour semantics (what ids 7–23
*do*) are **not**, because they live in per-character data nobody has read
(`chr/ai/<char>_b_NN.bin`, explicitly "not analysed" in
`cpu-ai-levels.md` §1). Section 6 says which rows are solid and which are open.

**Nothing was patched. No emulator ran. No repo file was edited.** All
instructions below are read from the extracted overlay whose sha256 matches the
one `cpu-ai-levels.md` §1 records
(`1ab547c71612726599ef063d0f5909dff41c03661d97567cca873f8ef2e80db9`,
61440 bytes), not from a re-derived ROM read.

**Tag convention, used on every row below:**

- **[M] measured** — re-read from overlay bytes at the cited address, and the
  reading survived a self-tested scanner (see §7).
- **[L] live** — observed in the committed 1208-frame capture
  (`ai-action-probe-2026-09-26/logs/meta.json`, histograms).
- **[I] inferred** — a reading of what the code *means*. Not a measurement. The
  owner's verdicts and the pivot patch are in this class, not the first.
- **[X] open** — a named gap, with what would close it.

---

## 0. The two corrections this map rests on, and one retraction

### 0.1 `AI+0x39` and `AI+0x3A` are not what the action-probe writeup says they are

`docs/research/feel-captures/ai-action-probe-2026-09-26/RESULTS.md` Finding 1
says the action id lives at `+0x39`. **It does not.** At the dispatcher, `+0x3A`
receives the caller's behaviour constant and `+0x39` gets a *fixed* value: **[M]**

```
0217AB84  ldr  r3, [r0, #0x4c]
0217AB8C  tst  r3, r1, lsl #1        ; wait: r2=1; tst r3, r2, lsl r1
0217AB90  mov  r3, #2
0217AB94  strb r3, [r0, #0x39]      ; +0x39 := 2   <-- constant, not the id
0217AB9C  movne r1, #0               ; downgrade to id 0 if already used
0217ABA0  strb r2, [r0, #0x3e]      ; +0x3E := 0
0217ABA4  strb r1, [r0, #0x3a]      ; +0x3A := r1   <-- the id
```

Full text of `0x0217AB84`, 10 instructions, no branch: read the used-bit mask at
`+0x4C`, set `+0x39 = 2`, zero `+0x3E`, write the id to `+0x3A`, set `+0x105 = 2`,
and `OR` bit `0x400` into `+0xD4`. **So `+0x3A` is the behaviour id and `+0x39` is
a dispatch phase.** [M]

The live histograms are consistent with this and inconsistent with the writeup's
label: `+0x39` takes `0,1,2,3,4,5,8` **[L]** and `+0x3A` takes
`0,1,2,4,5,6,11,12` **[L]**, and `+0x39 ∈ {4,8}` are written together at
`0x0217BA60/6C/D4/E0` **[M]**, i.e. `+0x39` is a small state enum that a list
walk (`0x0217BA88`–`0x0217BACC`, which has no exit but `0x0217BAD0`) drives.
The writeup's "action 8" is therefore **phase 8**, and the thing that arms it —
`+0x3A = 0x0C` at `0x0217AD30` — is **behaviour id 12**, not "mode `0x0C`" in
some separate namespace. Same bytes, different name.

This does not change the pivot's mechanism. It changes what "action 8" means, and
it means the probe's `b39`-keyed detector is keyed on a phase enum.

### 0.2 The pivot's gate is not the documented `0x02179130` gate

The pivot edit at `0x0217ACE0` (`sub r0,r0,#5` → `#1`) feeds **`0x0217B078`**,
which `cpu-ai-levels.md` does not list among the gates: **[M]**

```
0217B078  cmp  r1, #8
0217B07C  movhs r0, #1               ; >= 8 bypasses
0217B084  ldr  r2, [pc, #0x18]       ; pool word at 0x0217B0A4 = 0x0218190C
0217B088  ldr  r3, [r0, #0x38]       ; same roll field
0217B08C  ldr  r0, [r2, r1, lsl #2]  ; same 8-word table
0217B090  and  r1, r3, #0xff
0217B094  cmp  r1, r0
0217B098  movls r0, #1
```

That is a second, stripped copy of `0x02179130`: same table address
`0x0218190C` (verified by reading the pool word at `0x0217B0A4` = `0x0218190C`),
same `>= 8` bypass, same `& 0xff`, same `movls`. **[M]** Its argument `r0` at
every call site is `ldr r0,[r4,#0x2c]` — the same object §3.10's third
correction identified as the gate's base. **[M]**

`0x0217B078` has **3** call sites in ov11, all with a *computed* index:
`0x0217AC7C` (`[r4+0x104]`, raw difficulty), `0x0217ACF8`
(`max(0, difficulty-5)`, the pivot) and `0x0217B578` (`[r7+0x104]`). **[M]**
**Consequence for the doc:** §3.1's list of "live parameters
`0x1C,0x1D,0x1F,0x21..0x25`" does not describe this gate, and the pivot's index
is `difficulty-5` clamped at 0, **not** one of those offsets. Any row in §4 that
attributes the pivot to `0x1C`…`0x25` is wrong. **[I on the doc, M on the code]**

### 0.3 Retracted: `0x0217AB28` is not a "behaviour query"

Its shape is a **bitmask test**, not a lookup: **[M]**

```
0217AB28  asr  r2, r1, #5
0217AB2C  add  r2, r0, r2, lsl #2
0217AB38  ldr  r2, [r2, #0x34]       ; word (n>>5) of the mask at AI+0x2C+0x34
0217AB3C  mov  r0, #1
0217AB40  tst  r2, r0, lsl r1        ; test bit (n & 31)
0217AB44  moveq r0, #0
```

So `0x0217AB28(AI+0x2C, n)` = **"has slot *n* already been consumed?"** — a
*novelty* filter, and the mask is 8 words (`+0x34`…`+0x50`, which is §3.10's
latch region). The dispatcher applies the same idea at `+0x4C` and *downgrades the
id to 0* rather than refusing it. **[I, from M bytes]** This is the mechanism
behind "the CPU repeats itself", and it is a **suppression valve, not a
probability**.

---

## 1. The spine: how the CPU picks a behaviour at all **[M]**

This is the finding the taxonomy needed, and it is new. The single decision
function is `0x0217ABBC`–`0x0217B068` (the `push {r3…lr}` / `pop {…pc}` pair).

### 1.1 The 24-slot candidate set

```
0217AE08  str  r1, [r4, #0x48]        ; +0x48 := 0   (accumulator)
0217AE1C  mov  r1, #2
0217AE20  bl   0x217b0a8              ; mask_A = list_A[band]
0217AE2C  orr  r0, r2, r0
0217AE30  str  r0, [r4, #0x48]        ; +0x48 |= mask_A
0217AE38  bl   0x217b0c0              ; mask_B = list_B[band]
0217AE60  str  r0, [r4, #0x48]        ; +0x48 |= mask_B
0217AE50  bl   0x217b0d8              ; mask_C = list_C[band]
...
0217AF08  ands r1, r0, #0x7e
0217AF0C  str  r1, [r4, #0x48]        ; +0x48 &= 0x7E      (kill bit 0)
0217AF10  bne  0x217af98
...
0217AFF4  mov  r3, r5
0217B000  tst  r6, r2, lsl r3         ; r2 = 1
0217B004  strbne r3, [r0, r5]         ; append id
0217B014  cmp  r3, #0x18              ; <<< 0..23
0217B018  blt  0x217b000
0217B024  ldr  r0, [pc, #0x48] ; 0x021811D0 -> the PRNG global
0217B030  bl   0x2031070              ; xorshift128 draw
0217B034  mov  r1, r5
0217B038  bl   0x200d338              ; pick index in [0, count)
0217B044  ldrb r1, [r0, r1]           ; the chosen id
0217B050  bl   0x2174ebc              ; issue it
```

**`cmp r3, #0x18` at `0x0217B014` is the 23.** The behaviour set is a **24-bit
availability mask at `AI+0x48`**; the AI expands the set bits to a stack array,
draws once, and **picks uniformly-ish among the survivors** before issuing.
**[M for the shape, I for "uniform-ish" — §3.10 is right that the draw's
distribution is unestablished, and here it is one draw over N survivors, which is
a different quantity from the per-gate roll.]**

`0x200d338` being a *count-bounded* picker means **the mask is the throttle.**
A behaviour that is not in the mask cannot be chosen at any roll. This is why
"the probability levers buy activity, not judgement" is the right prior, and it
gives a sharper version: **the levers that matter are the ones that set bits in
`+0x48`, and there are exactly three, and none of them is a `ai_param` gate.**

### 1.2 Where the three masks come from

The band index is chosen from `AI+0x10A`, a byte: **[M]**

```
0217AE0C  ldrb r0, [r4, #0x10a]
0217AE10  cmp  r0, #0xa0
0217AE14  bls  0x217ae68        ; then
0217AE68  cmp  r0, #0x50
0217AE70  bls  0x217aec0        ; band 0 if <= 0x50, else band 1
                                ; band 2 if > 0xA0
```

The three readers index **three parallel 32-bit arrays** in the object at
`[AI+0x24]`: **[M]**

| reader | array offset | call sites' band value |
|---|---|---|
| `0x0217B0A8` | `+0x84` | 0, 1, 2 |
| `0x0217B0C0` | `+0x90` | 0, 1, 2 |
| `0x0217B0D8` | `+0x9C` | 0, 1, 2 |

(each is `ldr r0,[r0]; cmp r0,#0; addne r0,r0,r1,lsl #2; ldrne r0,[r0,#off];
moveq r0,#0` — the same 6-instruction shape three times, distinguished only by
the displacement.)

**`AI+0x10A` is a three-band selector with cut-points `0x50` and `0xA0`.** **[I]**
The two other uses of `AI+0x10A` are `cmp #0xA0` at `0x0217AE10` and `cmp #0x50`
at `0x0217AE68`, so the byte is a magnitude. 80/160 in 8.8 is 2 and 5 units;
whether the unit is pixels, a signed distance, or an index into a per-character
range table is **[X]**. This is the **spacing ladder**: three regimes, each with
its own availability mask. It is the most promising thing in this document and it
is *entirely data-driven*, in the object at `AI+0x24`.

> **CORRECTION (2026-09-28, reproduced offline — `ai_mask_builder.py`).** The nine
> words are built by `0x02174330`'s first loop from each record's sub-record
> `s16[+0x00/+0x02/+0x04/+0x06]`, bucketed at the same `0x50`/`0xA0` cut points. Over
> all 74 `_b_` files **every one of the three bands yields `(w|w|w) & 0x7E == 0x7E`
> for 72 of them**, so the band byte **cannot change the `AI+0x48` pick's choice
> set**. The ladder is inert for that pick; it can only matter to the unclamped
> consumer `0x0217C16C`. "The most promising thing in this document" is withdrawn
> *for the pick*. See `cpu-ai-judgement-plan.md`, step 6 first static pass.

### 1.3 The suppression valves on `+0x48` **[M]**

| address | op | condition | effect |
|---|---|---|---|
| `0x0217AF0C` | `and r1,r0,#0x7E` | — | **always** clamps the mask to bits 1–6 (see correction below) |
| `0x0217AFB0` | `bic r0,r0,#0x2A` | if `0x0217AB28(AI+0x2C, 0) != 0` | kills bits 1, 3, 5 |
| `0x0217AFC8` | `bic r0,r0,#0x54` | if `0x0217AB28(AI+0x2C, 1) != 0` | kills bits 2, 4, 6 |

So **bits 0–6 of the availability mask are governed by the novelty counters, and
bit 0 is killed unconditionally.** Ids 0–6 are the repeat-suppressed classes;
ids 7–23 are governed purely by the three tables at `+0x84/+0x90/+0x9C`. **[M
for the mechanism, I for the "0–6 are basic movement" reading.]**

> **CORRECTION (2026-09-26, measured — `jus-mask-capture-cbxb`).** `and #0x7E`
> does **not** kill bit 0 alone. `0x7E` = `0b1111110`: it **keeps bits 1–6 and
> discards bit 0 *and every bit above 6***. The three tables at
> `+0x84/+0x90/+0x9C` are OR'd into the mask at `0x0217AE20`–`0x0217AE60`
> *before* this clamp, and they carry bits far above 6 — live, `0xC4000001`,
> `0x023A01FF`, `0x0000C100`, OR = `0xC63AC1FF`. Everything above bit 6 is thrown
> away, so **the `+0x48` pick can only ever return ids 1–6.** Measured directly:
> `AI+0x48` is `0x7E` on **every frame** of a 3420-frame run and never reaches 0.
>
> Two consequences. (1) §2's "23 selectable ids" is wrong for *this* pick — the
> pick has six choices, and the `+0x3A` values actually observed (0, 1, 2, 4, 5,
> 6, 11, 12) include three the pick cannot produce (0, 11, 12 — those come from
> the explicit branches at `0x0217AB84` and `0x0217AD2C`). (2) The empty-mask
> give-up at `0x0217AF7C` is **dead on this data**: its guard needs `mask & 0x7E
> == 0`, and `arr1` (`0x023A01FF`, static) always sets bits 1–6. Refuted
> dynamically *and* arithmetically — see §1.3.1.
>
> The clamp is in the code, so the fact is certain. Whether it is **intended**
> (bits 7+ reserved for another consumer) or a defect that starves the generic
> pick was **not** established when this was written — and it is now answered:
> the clamp is a **partition**, and bits 7–23 have an unclamped consumer. See
> §1.3.2.

### 1.3.1 The give-up is dead code, and the pick is six wide **[M]**

`jus-mask-capture-cbxb` ran the fixture bridge-only for 3420 contiguous frames
(fc 32585–36004) and watched `AI+0x48` plus every input to it:

| field | abs addr | value, all 3420 frames |
|---|---|---|
| `AI+0x48` (mask) | `0x02181C5C` | `0x7E` = **126**, min = max = 126, never 0 |
| band `AI+0x10A` | `0x02181D1E` | `0x50` (so band index 0 is selected) |
| `[AI+0x24]+0x84` | `0x023A4284` | `0xC4000001` |
| `[AI+0x24]+0x90` | `0x023A4290` | `0x023A01FF` |
| `[AI+0x24]+0x9C` | `0x023A429C` | `0x0000C100` |
| novelty flag `[AI+0x2C]+0x34` | `0x0239ED44` | `0` |

`OR = 0xC63AC1FF`; `& 0x7E = 0x7E`. Static and dynamic agree exactly, which is
why this is a certainty rather than a correlation. `AI+0x105` (the marker the
give-up sets to 1) reads **2** from fc 33508 through the latch and never 1, an
independent corroboration.

> **CORRECTION (2026-09-28).** The three word addresses in that table are **one
> dereference short**. The reader does `ldr r0,[r0]` (`0x0217B0A8`) and the caller
> passes `[r4,#0x24]` (`0x0217AE18`), so the word is `[[AI+0x24] + 0x84 + band*4]`,
> and `ctx = [[AI+0x24]]` is the object that also carries the block at `ctx+0xC`.
> `0x023A4284` is `[AI+0x24] + 0x84`, i.e. the handle's field, not the mask word; the
> "independent match" against the mask capture was two reads of the same wrong
> address. **`AI+0x48` is the one value in that table measured at its own address,
> and it is the one that carries the conclusion.** The mask is `0x7E` by
> construction anyway: the offline reproduction gives `0x7E` for 72 of 74 battle
> characters in every band. See the plan's step 6 first static pass.
>
> **CONFIRMED LIVE (2026-09-28).** One bridge-only read: `ctx = [[AI+0x24]] =
> 0x022606A0`, block `0x02263400`, `AI+0x48 = 0x7E`, `AI+0x10A = 0x50`. The nine words
> at `ctx+0x84` reproduce **exactly on bits 1..14** for `jj_b_01` (the fixture's CPU) and
> for no other file; every disagreement is an id the builder's skip mask
> (`ctx+0x74 = 0x007F8000`, ids 15..22) deliberately excludes. All three bands OR to
> `& 0x7E == 0x7E` on the live words too.

The band byte is constant, so **bands 1 and 2 are never read**: six of the nine
words at `[AI+0x24]+0x84..0xA4` are dormant in this fixture. That is a smaller,
separate dormant-data lead than the ids themselves.

### 1.3.2 The clamp is a partition, not starvation **[M]**

`jus-ai-mask-clamp-intent-umol`. The open question in §1.3 is answered, and the
answer refutes the "starved pick" reading: **bits 7–23 of the same word structure
have a second, unclamped consumer.**

The consumer is the routine at `0x0217C16C` (ov11), registered in the dispatch
table at `0x02181998` — the slot immediately after the clamp's own
`0x02181980` → `0x0217ABBC`. Re-read from bytes:

```
0217C1D0  ldr  r0, [r5, #0x24]
0217C1D4  mov  r1, r6          ; band index 0
0217C1D8  bl   0x217b0a8       ; the SAME reader the clamp uses
0217C1E0  ldr  r0, [r5, #0x24]
0217C1E4  mov  r1, #1
0217C1E8  bl   0x217b0a8
0217C1EC  orr  r6, r4, r0
...
0217C248  bic  r3, r6, #0x600  ; no &0x7E anywhere on this path
0217C254  tst  r3, r2, lsl ip  ; loop ip = 1 .. 0x17
0217C268  cmp  ip, #0x18
0217C284  bl   0x2031070       ; PRNG
0217C2A4  bl   0x2174ebc       ; issue the chosen id directly
```

So one three-word structure feeds **two** selection modes: the `AI+0x48` pick
(clamped to bits 1–6, §1.3.1) and this direct-issue path (bits 1–23, unclamped).
The clamp is therefore an intentional partition, and it does **not** remove
punish/anti-air/spacing by construction. Do not build a patch on the clamp.

The three readers are thin accessors, not logic — `[[AI+0x24] + 0x84 + idx*4]`,
`+0x90+idx*4`, `+0x9C+idx*4`, each returning the full 32-bit word unmasked
(`0x0217B0A8`, `0x0217B0C0`, `0x0217B0D8`, each 6 instructions). The nine words
are **runtime-built**, not a static ROM table: they are OR-accumulated with the
same `0x50`/`0xA0` band cut points at `0x0217482C`–`0x0217484C`.

Two residues, both smaller than the question they came from:

- The consumer reads only reader 1's group (the `+0x84` slot across its three
  band words). Readers 2 and 3 (`+0x90`, `+0x9C`) are called **only** by the
  clamp, so bits 7+ of those two groups are read nowhere else and are discarded.
  A smaller version of the same question, unanswered.
- The band byte `AI+0x10A` is written from per-character AI settings
  (`[AI+0x2C]+0x14/0x15/0x16`), not hardwired. The fixture sits exactly on the
  `0x50` cut point and so selects band 0; bands 1 and 2 are reachable in
  principle for other characters.

Two more suppression paths exist in the same function and are *not* reached from
the table: **[M]**

- `0x0217AFA0`–`0x0217AEC0`: if `+0x48 & 0x7E == 0` and the descending scan
  `0x0217AF14`–`0x0217AF78` (`sub r5,r5,#1` down to `-1`) also finds nothing, the
  AI **gives up for the tick**: `bl 0x0217AA58`, `+0x105 = 1`, branch to exit.
  **An empty availability mask is a hard no-op, not a fallback.** That is a
  candidate mechanism for the owner's frozen tail and it is a *data* condition.
- `0x0217ADF0`–`0x0217AE00`: if `+0x3A == 0` after the reaction table, it issues
  whatever is already in slot 0 — the only "repeat what I was doing" path.

### 1.4 Id remapping before dispatch **[M]**

```
02174ED4  cmp  r5, #0xd
02174ED8  blt  0x2174ef4              ; ids 0..12 pass through
02174EDC  sub  r0, r5, #0xd
02174EE0  cmp  r0, #1
02174EE4  ldrls r0, [r6, #4]
02174EE8  ldrsbls r0, [r0, #8]        ; <<< the opponent-state accessor, inlined
02174EEC  subls r0, r0, #3
02174EF0  addls r5, r5, r0, lsl #1     ; id += 2*(oppstate - 3)
```

**Ids 13 and 14 are the only opponent-state-indexed behaviours**, remapping to
13…18. `r6` is the incoming `r0` (`0x02174ECC mov r6,r0`) and the caller passes
`r0 = [[AI+0x24]]` — the same object whose `+0xC` is the block (§1) — so the accessor
is exactly `[[AI+0x24]+4] + 8`, a **signed byte**. That makes the
opponent-state byte observable with one chain of two dereferences plus an offset,
which is what `jus-ai-opponent-state-map-mbq6` needs. The sibling of this shape at
`0x0217BEB0` (`ldrsb r1,[r4,#0x3b]`, i.e. the already-picked id, then
`+= 2*(byte-3)`) is the same idiom applied to the
*current* slot rather than the argument, and is the one §3.9 records. **[M]**
This is the single most concrete **anti-air / punish** structure in the overlay:
the opponent-state byte feeds an arithmetic remap of the behaviour id. It is a
*selector*, not a veto, and §3.9's tracker item (`jus-ai-opponent-state-map-mbq6`) is
still needed to say which of 13–18 fires when.

### 1.5 What the id resolves to

`0x02174EBC` then calls `0x021751CC`, which does **not** switch on the id. It
calls `0x021733B4((int8_t)id)`, indexes the node list at `[node+0xC]` (count at
`+8`) and `[node+0x30]`, and caches a record at `node + slot*4 + 0x14`; the
**resolved** id is written to `node + 0xC0 + slot` (`0x02174F18`). **[M]**

**CORRECTION (2026-09-26, measured — `jus-name-ai-behaviour-ids-ksan`).**
`0x021733B4` is **not** where per-character AI data enters. It is a pure ROM
lookup, six instructions, re-read from bytes:

```
021733B4  cmp  r0, #0
021733B8  ldrlt r1, [pc, #0x14]   ; 0x021816C0
021733BC  ldrlt r2, [r1]
021733C0  addlt r2, r2, #1        ; id < 0 increments an error counter
021733C4  strlt r2, [r1]
021733C8  ldr  r1, [pc, #8]       ; 0x02181100
021733CC  ldrsb r0, [r1, r0]      ; r0 = table[id]
021733D0  bx   lr
```

`table[0] = -1`; `table[n] = n-1` for `n = 1..23`. So the map is **id 0 invalid,
ids 1–23 → slots 0..22**, and no file is read in it.

**And the per-character data does not carry the names.** All 267 files decode
(DSCP + LZ77 type `0x10`) to an `AIPM` payload whose only printable run is the
magic itself; there is no 24-entry table. Measured layout, for the record:

| offset | content |
|---|---|
| `0x00` | `AIPM`, then `00 01 ff fe` |
| `0x08` | u32 = `0x64` (100) |
| `0x0C`–`0x5C` | **21 slots**, u32 offset to a 188-byte record, `0xffffffff` = absent |
| `0x60` | `0xffffffff` on every file — a permanent fence |
| `0x64` / `0x68` / `0x6C` | `0` / `1` / `0` on every file |
| `0x70` | count of 32-byte records at `0x100` (1..5) |

So the semantics are **not** behind `0x021733B4`, and they are **not** literal
strings in the data. But the data is **not** irrelevant, and the claim below is
corrected: **the list at `[obj+0xC]` is built by loading the per-character AIPM
file.** Verified from bytes — the constructor at `0x02174330` builds the filename
and loads it:

```
021745F4  ldr   r1, [r1, #4]     ; [0x021817D0 + 4] = "chr/ai/"
021745F8  bl    0x2074000        ; strcpy(buf, "chr/ai/")
02174600  mov   r1, r8           ; r8 = per-character token (table[r], 8-byte stride)
02174604  bl    0x20741bc        ; strcat(buf, token)
02174610  ldr   r1, [r1]         ; [0x021817D0] = ".bin"
02174614  bl    0x20741bc        ; strcat(buf, ".bin")
02174634  bl    0x2033410        ; load "chr/ai/<token>.bin"
02174668  blx   r2               ; virtual method -> the derived list
0217466C  str   r0, [r6, #0xc]   ; [behaviour_obj + 0xC] = list
```

So the per-id semantics **are derivable in principle**, but the static route stops
short of them. The follow-up resolved the virtual method and it is a **dead end**:

- vtable `0x02094AC4` slot `+0x2C` = **`0x0200F751`** (arm9, Thumb), verified by
  reading the vtable word directly.
- Its body is a trivial accessor: `push {r3,r4,r5,lr}; mov r5,r0; mov r4,r1;
  ldr r1,[r5,#0x20]; …; ldr r0,[r5,#0x20]; add r0,r0,r4; pop` — i.e.
  `return [F+0x20] + index`, with a lazy-init call when `+0x20` is null.

So the list is populated at **file-open** time, not by this method. The builder is
`0x201a228`, whose dispatch tree the follow-up could not resolve statically.
**The AIPM → node field mapping is therefore unresolved.**

The follow-up refuted the earlier node layout (`+0x0C` a "type selector clamped
≤4"; 32-byte array at `+0xA4`) but **I could not verify its replacements either**
— it claims `+0x0C` is a 1..5 record count used as a loop bound and that the array
sits at `+0x9C`, and I found no such loop. Worse, `+0xC` is used as a *fixed-point
coordinate* (`lsl r0,r0,#0xc`, `0x02175380`) on a different object inside the same
function, so a bare `+0xC` reading is ambiguous. **Treat the node layout as
unknown**, not as either agent's version.

**CORRECTED 2026-09-26 — the target was wrong, and the first dump proves it.** The
runtime dump was run; it confirmed the chain *and* refuted part of the premise:

- The resolver's `sl` is **`[[AI+0x24]]`, not the object at `[AI+0x1C]`.** Verified
  at both ends: the consumer `0x0217C16C` issues at `0x0217C2A4` with
  `r0 = r2` where `0x0217C294 ldr r2,[r5,#0x24]` and `0x0217C29C ldr r0,[r2]`;
  and `0x02174EBC` forwards its incoming `r0` unchanged (`0x02174EF4 mov r0,r6`)
  into `0x021751CC` at `0x02174F00`, which reads `[sl+0xC]` at `0x021751EC`.
- `[AI+0x24] = 0x023A4200`, and that object's `+0x84`/`+0x90`/`+0x9C` are
  **`0xC4000001`/`0x023A01FF`/`0x0000C100`** — an exact match to the independently
  measured mask capture, so the object identity is doubly confirmed. Its `+0`
  points to `0x0226076C`, which is therefore the real `obj`.
- The object at `[AI+0x1C]` (`0x023CA5D0`) has `+0xC = 0x023DBC90`, and that region
  is **not an `offsets[23]` array** — it is a table of `0x30`-byte records whose
  first word is vtable `0x02094AC4`, i.e. the same file-object vtable whose
  `+0x2C` slot is the trivial accessor. So "the behaviour object is `[AI+0x1C]` and
  its `+0xC` is the list" is **refuted**, and `list+8` landing on a plausible small
  integer was the size field of one of those records, not an offset.

So the measurement is: `obj = [[AI+0x24]]`, `list = [obj+0xC]` — and a corrected
re-run is dispatched. **[M]** for the chain and the mask match; **[X]** still for
the node layout.

**RESOLVED 2026-09-27.** The corrected re-run landed, and the block turns out to be
the per-character AIPM payload itself (`AIPM` magic at `[obj+0xC]`), with a 23-entry
record-offset array at `+0x08` and one 188-byte behaviour record per id. The record
layout, the id→slot map, and the refutation of `+0x0C` as a "type selector" are in
**[the AIPM behaviour block — data layout](ai-behaviour-data-layout.md)**, which is
now the reference for the data side. The ids are backed by readable per-id records;
what remains open is their *semantics*, not their existence.

---

## 2. Table of reachable behaviours

`Profile control` = what shipped data can actually change about it. The right
column is the point of the exercise.

| id | what it appears to do | evidence (address / table row / trace) | measured vs inferred | profile controls | suppressed by |
|---|---|---|---|---|---|
| **0** | always masked out before the pick; the dispatcher's "already used" downgrade target | `0x0217AF08` `and #0x7E`; `0x0217AB9C` `movne r1,#0`; live: never picked | **[M]** the masking; **[I]** that it is a placeholder | **none** — unconditionally dead as a *candidate*; reachable only as a downgrade | unconditional `and #0x7E` |
| **1** | first novelty-suppressed class | `0x0217AFB0` `bic #0x2A`; live: not in the `+0x3A` histogram **[L]** | **[M]** mask; **[I]** semantics | nothing in `ai_param` | bit set by consumption of flag 0 |
| **2** | second novelty-suppressed class | `0x0217AFC8` `bic #0x54`; live: `+0x3A==2` on 524 rows **[L]** | **[M]** mask; **[I]** semantics | nothing in `ai_param` | flag 1 |
| **3** | novelty-suppressed class | `0x0217AFB0` `bic #0x2A`; live: 0 rows of `+0x3A==3` **[L]** | **[M]** mask; **[I]** semantics | nothing in `ai_param` | flag 0 |
| **4** | novelty-suppressed class | `0x0217AFC8` `bic #0x54`; live: 5 rows **[L]** | **[M]** mask; **[I]** semantics | nothing in `ai_param` | flag 1 |
| **5** | novelty-suppressed class | `0x0217AFB0` `bic #0x2A`; live: 84 rows **[L]** | **[M]** mask; **[I]** semantics | nothing in `ai_param` | flag 0 |
| **6** | novelty-suppressed class | `0x0217AFC8` `bic #0x54`; live: 54 rows **[L]** | **[M]** mask; **[I]** semantics | nothing in `ai_param` | flag 1 |
| **7** | first class **outside** the novelty mask | loop bound `cmp r3,#0x18` at `0x0217B014`; live: 0 rows of `+0x3A==7` **[L]** | **[M]** reachable; **[X]** semantics | **none** — governed by the three tables at `+0x84/90/9C` only | table mask |
| **8** | **the mode the probe called `0x0C`** — armed at `0x0217AC8C`, requires `opp.node+0x18 == 3` **and** `AI+0xDC[slot] <= 0x50` **and** gate index `[r4+0x104]` | `0x0217AC40`–`0x0217ACAC`; live: `+0x3A==8` **0 rows** in 1208 **[L]** | **[M]** the conditions; **[L]** never observed | gate `0x0217B078` with `r1 = [AI+0x104]` (raw difficulty) | `cmp r0,#0x50` on `AI+0xDC[slot]`, and `node+0x18 == 3` |
| **9, 10** | — | in the `cmp #0x18` range; live: 0 rows **[L]** | **[M]** reachable; **[X]** semantics | tables at `+0x84/90/9C` | table mask |
| **11** | issued unconditionally on a proximity trigger | `0x0217E7F8` `mov r1,#0xb` → `0x0217E7FC bl 0x0217AB84` (self-test T1); live: 5 rows **[L]** | **[M]** the call site; **[I]** "proximity" (the guard is `ldrh [r0+0xb0]` vs `[r5+0x60]`, §3.13) | none directly — the threshold lives in the candidate object, not `ai_param` | candidate-object field `+0xB0`, never written in ov11 (§3.13) |
| **12** | **the pivot's target.** Cancels bit `0x400` on every node of the linked list at `[AI+0x24]+0x14`, then issues | `0x0217ACC4`–`0x0217AD50`; the cancel loop is `0x0217AD10`–`0x0217AD20` (`bic r0,r0,#0x400` at `0x0217AD18`) — the *same* bit the dispatcher ORs in at `0x0217ABB0`; live: 64 rows in 3 episodes **[L]** | **[M]** the loop, the bit, the conditions; **[I]** "interrupt the opponent" | gate `0x0217B078` with `r1 = max(0, difficulty-5)` | `+0x24+0x3C >= 2` **and** `+0x24+0x36 >= 1` (doc §4's "target byte ≥ 0xD") |
| **13** | opponent-state-indexed, base value | `0x02174ED4`–`0x02174EF0`; live: 0 rows **[L]** | **[M]** the remap; **[X]** semantics | tables + opponent state | table mask |
| **14** | opponent-state-indexed, base value | same; live: 0 rows **[L]** | **[M]** the remap; **[X]** semantics | tables + opponent state | table mask |
| **15–18** | `13/14` after `id += 2*(oppstate-3)`, i.e. the remapped forms | `0x02174EEC`–`0x02174EF0`; live: 0 rows **[L]** | **[M]** the arithmetic; **[X]** which opponent state selects which | tables + opponent state | table mask **and** opponent state |
| **19–23** | in the `cmp #0x18` range, never remapped | `0x0217B014`; live: 0 rows **[L]** | **[M]** reachable; **[X]** semantics | tables at `+0x84/90/9C` | table mask |
| *(not an id)* | **the reaction table** — a *separate* 14-entry weighted decision, taken **instead of** the `+0x48` pick (not before it), and able to set `+0x3A` itself | `0x0217AD54`–`0x0217ADE4`; table at **`0x02181438`** — the literal at `0x0217B070` holds that address and is the only such literal in ov11 — 14 entries of 3 signed bytes then `(-1,-1,-1)` at entry 14 (decode in §4.4) | **[M]** the loop, the table, the terminator; **[I]** that it is "reaction" | **none** — fully authored ROM data | terminates on a negative byte 0; entered only when `([AI+0x2C]+0x38) & 3 != 0`, otherwise control goes to the wheel at `0x0217AE04` |
| *(not an id)* | **the `0x7F` sentinel branch — LIVE, correcting an earlier claim in this document** | `0x0217ADBC` `ldrsb r0,[r0,sb]`; `0x0217ADC0 cmp r0,#0x7F`; `0x0217ADC4 moveq r0,#0x10`; `0x0217ADC8 strbeq [r4+0x40]`; `0x0217ADD0 strbeq [r4+0x3a]` | **[M]** entry **13** of the real table is `(127, 18, 27)`, so byte 0 **is** `0x7F` on shipped data; the earlier "cannot fire" read byte 0 of the wrong table (§4.4) | none | **live**: selects a null outcome — `+0x40 = 0x10` and `+0x3A = 0` — i.e. a deliberate "no behaviour" band at the top of the distribution |
| *(not an id)* | **the give-up path** | `0x0217AF7C`–`0x0217AF94`; `+0x105 = 1`, `bl 0x0217AA58`, exit | **[M]**; **[I]** that it produces the frozen tail | none — a function of `+0x48` being empty | the masks at `+0x84/90/9C` |

**Count discipline.** The `cmp r3,#0x18` bound is `0x18` = **24** slots, ids
`0..23`, and the `+0x3A` domain can hold any of them. **[M]** **But the `+0x48`
pick is clamped to bits 1–6 before its loop runs (§1.3 correction), so that pick
has six choices, 1–6 — not 23.** The "23 behaviours" of the RESULTS.md playtest
verdict is the *id-space size*, not the number of choices the pick makes. Of the
`+0x3A` values actually seen live (0, 1, 2, 4, 5, 6, 11, 12), three are
unreachable from the pick and come from the explicit branches instead.

### 2.1 The id is written *before* the action, and the state splits the ids into two groups **[M, n=9]**

The single most useful thing the existing probe log can still answer, because it
also logged the CPU's *own* fighter state code. Source:
`jus_files/captures/ai_actions/tail.jsonl`, slot 1, the 752 pre-latch frames
(`fc` 32755–33508), one character, one match. `st18` in that log is address
`0x0224EF18` = **P2 battleObj `+0x18`**, the CPU's state code (`physics.md`: 0
idle, 1 walk, 6 airborne, 9 attack, 11 dream attack). Method: take each maximal
run of constant `+0x3A`, and cross it against that state code.

| id | runs | state codes inside the run | state the frame *before* the id appeared | frames from the id to the first state change | reading |
|---|---|---|---|---|---|
| **1** | 1 (38 f) | 9 ×32, 0 ×6 | 0 | +6 | attack mode |
| **2** | 2 (68 f, 456 f) | 9 ×64, 0 ×4 — and 0 ×456 in the frozen run | 0 | +4, and **never** in the frozen run | attack mode that did not fire |
| **4** | 1 (5 f) | 0 ×4, 1 ×1 | 0 | +4 | no action observed |
| **5** | 1 (84 f) | 0 ×51, 9 ×33 | 0 | +7 | sometimes attack |
| **6** | 1 (54 f) | 9 ×49, 0 ×3, 1 ×2 | **1 (walk)** | +2 | attack mode, entered from a walk |
| **11** | 1 (5 f) | 0 ×5 | 0 | +14 | **no action at all** — consistent with `aipm_slot_matrix.py who 10` showing slot 10 empty for 60 of the 74 battle characters |
| **12** | 3 (47 f, 12 f, 5 f) | 0 ×58, 11 ×5, 1 ×1 | 0 | +19, +7, +1 | mostly no action |
| **0** | 9 runs, 434 f | 0 ×334, 1 ×42, 11 ×30, 6 ×28 | — | — | **walking, airborne and dream attacks all happen while no behaviour id is issued** |

Two things this settles:

1. **The id precedes the action in all 9 runs** (offset +1 to +19 frames), never
   follows it. So the id is a *cause-side* signal, not a report of something the
   fighter already did. A 4–6 frame startup separates the dispatch from state 9.
2. **Movement is not under this id.** Id 0 — no dispatched behaviour — covers
   walk, airborne and dream-attack frames. So the behaviour ids govern the
   action/attack layer, and the masquerade of "the AI is doing nothing" during a
   long id-0 run is false: the fighter is moving.

**Caveat, stated because it matters:** n = 9 runs, one character, one match, and
the runs are not independent (each id appears once or twice). This is a lead that
splits the id set into "attack" {1, 2, 6} and "no observed action" {4, 11, 12},
not a naming. The consumer trace now queued (`crew-consumer-trace`) logs the same
fields plus positions on a fresh run and will either extend this or refute it.

### 2.2 The fresh run: `ctx+0xC0` is the *wheel's* id only, and it confirms the clamp **[M]**

The queued trace ran on 2026-09-27 (`<TMP>/crew-consumer-trace/pairing.tsv`):
3420 frames, fc 32865–36284, **0 dropped, 0 gaps**, same fixture, and the live block
is now *named* — `op_b_03.bin`, all 3484 bytes (see the data-layout doc §1.1).

**`ctx+0xC0` is NOT wheel-exclusive, correcting what this section first said.** Its
writer is the shared issuer `0x02174EBC`, and a `bl` scan of ov11 finds **ten**
callers: `0x0217A7A8`, `0x0217AAC8`, `0x0217AC9C`, `0x0217AD40`, `0x0217ADFC`
(the reaction path), `0x0217B050` (the wheel), `0x0217BC48`, `0x0217C2A4`,
`0x0217C620`, `0x0217C890`. So `ctx+0xC0` is "the last id that any of ten issuers
resolved successfully", and `+0x3A` is the same quantity written by whichever
producer ran. The two are not separable by inspection; only the *caller* tells
you the producer.

| id0 | frames | fc range | `p2x-p1x` start → end | CPU state code |
|---|---|---|---|---|
| `0xFF` | 287 | 32865–33151 | −20726 → −4061 | 0:218, 1:34, 11:35 |
| 5 | 9 | 33152–33160 | −4061 → −4061 | 0:7, 9:2 |
| 6 | 347 | 33161–33507 | −4061 → −21964 | 0:218, 9:127, 1:2 |
| 2 | 2776 | 33509–36284 | −21964 → −21964 | **0:2776** |

Two things drop out of this, and one earlier claim of mine is withdrawn:

1. **Withdrawn: "the clamp is confirmed from an independent observable."** That
   argument needed `ctx+0xC0` to be wheel-only, and it is not — the reaction path
   and the unclamped consumer write it too, and neither is clamped. The clamp
   itself is still certain (it is `and r1,r0,#0x7e` on the mask, §1.3.1), but the
   histogram is not independent evidence of it. Nothing else here depends on the
   claim. For producer attribution, log the caller, not the field.
2. **Movement is not under this id, reproduced.** During the 287-frame `0xFF` run the
   fighter walks (34 frames) and is airborne/dream-attacking (35) while no behaviour id
   is issued. §2.1's finding holds on a second run.

**And the freeze, sharper.** id 2 is held for **2776 frames** (fc 33509–36284) with the
CPU's state code at 0 on *all* of them and `p2x-p1x` constant at −21964, i.e. neither
fighter moves at all. That is the same id 2 whose record is *populated* (`+0x0C = 0x101`,
count 1) and whose healthy instance attacked 200 frames earlier in the older capture. So
the freeze is not a missing record: a real behaviour is selected, repeatedly held, and its
action never begins.

### 2.3 The **sub-record's** `+0x18` byte is a partition, and it agrees with the code's boundary **[M]**

**Offset discipline, because an edit could hit the wrong byte:** the field below is the
**sub-record's** `+0x18`, i.e. `record + 0x9C + 0x20*k + 0x18`. Record-relative `+0x18` is
a *different* byte, and in `op_b_03` it is zero for the ids this document samples — so a
patch derived from this section must use the sub-record offset. The accessor is
`subrecord_offset_18()` in `scripts/analysis/aipm_slot_matrix.py`.

Decoding `op_b_03.bin`'s 18 records (every one is size `0xBC`, one sub-record) made
`+0x18 = 5` look confined to ids 13–17. **Tested across all 74 battle characters in
the corpus, that is wrong**, and the real structure is better. Over every record with
`count >= 1` in every `_b_` file:

| `+0x18` | ids it occurs on | |
|---|---|---|
| `0x00` | anywhere | an **empty** or near-empty record (`+0x0C = 0` for the true empties) |
| `0x01` | 18 (once) | |
| `0x02`, `0x03` | **ids 1–12**, plus one file each on ids 15 and 19 | the "low half" |
| `0x04`, `0x05` | **ids 13–22** | the "high half" |

So the rule is ids ≤ 12 → `{2,3}` and ids ≥ 13 → `{4,5}`, **with three odd records out of
roughly 1,870** (one file reads `0x01` on id 18, and one file each reads `0x03` on ids 15
and 19). The split otherwise lands exactly on **id 13**, the same boundary §1.4's remap
tests with `cmp r5, #0xd`. Reproduce with `aipm_slot_matrix.py fields`.

`+0x18` is therefore a **class/partition byte, not a semantic label** — worth having,
because it independently confirms the remap boundary, but it does not name anything.
Two further bounds on reachability for this character: **ids 11 and 18 have empty
records in `op_b_03`**, which explains the earlier probe's five frames of dispatched
id 11 with no state change as a data fact rather than a dispatch bug.

A caveat on cross-run comparison: the two captures start at different frames and one is a
free-run tail while the other is plan-driven, so their id sequences are **not** comparable
run-to-run even though both latch the freeze at fc 33509. Pair ids with actions *within* a
run only.

---

## 3. A correction to my own §1.2, before it becomes a wrong claim

The reaction table at `0x021811F0` and the `+0x48` pick are **not** the same
mechanism, and I nearly merged them. `0x0217AD54` runs *only* when the id-8 and
id-12 branches both fall through, i.e. on the common path, and it accumulates a
score and picks against a threshold `(roll & 0xff) >> 1`. It writes `+0x3A`
directly at `0x0217ADD0`/`0x0217ADD4`. **[M]**

So **`+0x3A` has two independent producers**: the 24-bit mask wheel
(`0x0217B050` → `0x02174EBC`) and this reaction table. Which one produced the 64
live `+0x3A == 12` rows is **not** determined here — `0x0217AD30` is the sole
writer of `0x0C` to `+0x3A` **[M]** and the writeup measured that, so those rows
came from the pivot branch, not from the reaction table. **[M]** The reaction
table's own output ids are unmeasured. **[X]**

---

## 4. Dormant-but-smart candidates, ranked

Ranked by (evidence strength × plausibility that the symptom is caused by its
suppression).

### 4.1 The `+0x48` empty-mask give-up — the strongest candidate **[M]**

`0x0217AF7C`–`0x0217AF94`: if the accumulated availability mask is zero, the AI
does **not** fall back to anything. It calls `0x0217AA58`, sets `+0x105 = 1`, and
returns. **[M]** And the masks come from three arrays in an object ov11 never
writes (`[AI+0x24]` → `+0x84/+0x90/+0x9C`, populated from outside the overlay, the
same "populated from outside" problem as `+0xB0` in §3.13). **[M for the reads,
X for the writer.]**

Why this ranks first: it is the only path in the taxonomy where a **pure data
condition produces a total no-op with no fallback**, which matches the owner's
"the CPU sits there and does nothing" better than any probability story. It is
also **not reachable by any `ai_param` edit** — it is reachable by the per-move
lists, which is why the pivot bought activity and not judgement.

**What would settle it:** read `+0x84/+0x90/+0x9C` for the live band and log
`+0x48` per frame. One capture, no patch.

### 4.2 The three-band spacing ladder at `AI+0x10A` **[M]**

`≤0x50` / `(0x50,0xA0]` / `>0xA0` selecting three independent mask sets
(§1.2). **[M]** This is a **spacing mechanism that already exists**, is
data-driven, and has never been read. **[I]** If those three arrays are the
spacing policy, then "the CPU has no spacing judgement" would be a *contents*
problem in three 4-byte arrays, not a missing feature. That is the cheapest
judgement win on this list and it needs a file read, not a patch.

**What would settle it:** dump `+0x84/+0x90/+0x9C` for band 0/1/2 in a live
match, and log `AI+0x10A` against the true fighter separation to fix its unit.
**Open:** which of X and Y the 0x50/0xA0 cut-points are in.

### 4.3 Ids 13–18, the opponent-state remap **[M]**

`id += 2*(oppstate-3)` at `0x02174EF0` is a real **threat-conditioned
behaviour switch**: six distinct behaviours exist, and the opponent's state byte
chooses between them. **[M for the arithmetic, I for "threat-conditioned".]**
The AI therefore *does* have punish/anti-air slots and *does* have a signal that
distinguishes them. **Live, all six were unused — 0 of 1208 rows.** **[L]**

This is the candidate that matches the owner's "poor punishment" report most
directly, and the tracker item that names it
(`jus-ai-opponent-state-map-mbq6`) is still open. **[X]**

**What would settle it:** the state-byte map (existing tracker item) *plus* the contents
of `chr/ai/<char>_b_NN.bin` so ids 13–18 have names. Neither needs a patch.

### 4.4 The `0x7F` sentinel and the reaction table's real structure — **the earlier reading is WITHDRAWN** **[M]**

**The withdrawn claim.** This section used to say `cmp r0,#0x7F` at `0x0217ADC4`
"cannot fire on shipped data". That was measured against a table at `0x021811F0`,
and **that address is wrong**. The loop loads its table from the literal at
`0x0217B070`, which holds **`0x02181438`**, and it is the *only* literal in ov11
that points at either address. On the real table, entry **13** is
`(127, 18, 27)` — byte 0 **is** `0x7F`. So the sentinel fires, and it is a
deliberate **null outcome**: it sets `+0x40 = 0x10` and `+0x3A = 0`, i.e. "no
behaviour this frame", as one band of the distribution.

**The real table** (14 entries, 3 signed bytes, `(-1,-1,-1)` terminator at 14):

| entry | byte 0 | byte 1 | byte 2 |
|---|---|---|---|
| 0 | 1 | 0 | 15 |
| 1 | 2 | 1 | 16 |
| 2 | 3 | 0 | 17 |
| 3 | 4 | 1 | 18 |
| 4 | 5 | 0 | 19 |
| 5 | 6 | 1 | 20 |
| 6 | 1 | 2 | 21 |
| 7 | 1 | 3 | 22 |
| 8 | 7 | 5 | 23 |
| 9 | 8 | 6 | 24 |
| 10 | **11** | 17 | 25 |
| 11 | **13** | 4 | 26 |
| 12 | **14** | 4 | 26 |
| 13 | **127** | 18 | 27 |

**The weights are `[20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 15, 21]`** for byte-2 indices
15…27 — measured **constant on all 3420 frames** of the freeze capture
(`docs/research/side-quests/ai-phase-capture-2026-09-28/`), with `[AI+0x2C]` = `0x0239ED10`
stable and the roll source taking all 256 values. Cumulative, against a roll capped at 255:

| cumulative | entries | ids | share |
|---:|---|---|---:|
| 0–219 | 0–10 | 1,2,3,4,5,6,1,1,7,8,11 | 220/256 |
| **220–249** | **11–12** | **13, 14 — the punish band** | **30/256 ≈ 11.7 %** |
| 250–255 | 13 | 127 (sentinel) | 6/256 ≈ 2.3 % |

So the punish band is the **second-largest single share** in the table. It is not starved by
weight and not out of roll range. Whatever keeps ids 13/14 out of 1208 live frames is therefore
a **veto** — the `0x0217AB28` call at `0x0217ADA4`, whose argument is byte 1 (class 4 for both
punish entries) — and not the distribution. See `jus-ai-reaction-band-fwik`.

**The loop is a cumulative weighted pick, and the three bytes all mean
something** (`0x0217AD54`–`0x0217ADE4`, re-read from bytes):

```asm
0217AD58  ldr  r0, [r0, #0x38]      ; r0 = [AI+0x2C]+0x38
0217AD5C  tst  r0, #3
0217AD60  beq  0x217ae04            ; bits 0-1 clear -> the WHEEL path, not this one
0217AD64  lsr  r0, r0, #1
0217AD74  and  r8, r0, #0xff        ; r8 = the ROLL, 7 bits
0217AD7C  ldrsb r0, [r5, sb]        ; byte 0; < 0 terminates
0217AD9C  ldrb  r2, [r2, #8]        ; r2 = u8[ [AI+0x2C] + 8 + byte2 ]
0217ADA0  add  r7, r7, r2           ; r7 = running total
0217ADA4  bl   0x217ab28            ; veto([AI+0x2C], byte1) -- skip entry if nonzero
0217ADB0  cmp  r7, r8
0217ADB4  blo  0x217addc            ; not yet over the roll -> next entry
0217ADD4  strbne r0, [r4, #0x3a]    ; byte 0 -> the behaviour id
```

So: **byte 0 is the id, byte 1 is a novelty/veto class passed to `0x0217AB28`,
and byte 2 indexes a weight table at `[AI+0x2C]+8`.** The pick walks entries,
accumulating weights, and takes the first entry that both clears the veto and
pushes the total past the 7-bit roll `([AI+0x2C]+0x38) >> 1`.

**This reverses a load-bearing inference of mine, and it matters for the
judgement question.** Entries 10, 11 and 12 issue ids **11, 13 and 14** — ids
that the `and #0x7E` clamp on the `+0x48` pick can never produce (§1.3.1), and
13/14 are exactly the opponent-state-remapped family (ids 13–18). So
**"the clamp makes punish/anti-air unreachable" is false.** Those behaviours are
reachable through this table. The live capture saw `+0x3A` take 11 but never 13
or 14, so the real question is narrower and answerable: *what roll and weights
would select entries 11–12, and does that band ever occur?*

**What would settle it:** one bridge-only capture logging `[AI+0x2C]+0x38`,
the resolved `[AI+0x2C]` pointer, the 13 weight bytes at `+8+15 .. +8+27`, and
`+0x3A`, per frame. That decides whether the punish band is unreachable (roll
range too small), vetoed (`0x0217AB28` always nonzero for classes 4/17/18), or
simply rare. It needs no patch and no GDB.

**ANSWERED 2026-09-28 — it is not vetoed, and "rare" is not established.**
The capture was run (`jus_files/captures/reaction-veto-2026-09-28/veto1.jsonl`,
3420 frames) with the veto word added. `u32[[AI+0x2C]+0x34] == 0` on **every
frame**, so the class-4 veto that this section nominated is **not** the blocker:
no class is vetoed at all. Two further corrections follow from the same run and
its adversarial review — `AI+0x48` is **derived and clamped in code**, not a data
cap; and there are **four** producers of `+0x3A`, not two, including a third that
enumerates mask bits 1..23 *without* the `0x7E` clamp. The remap rewrites only
ids **13 and 14**, not 13–18. See `cpu-ai-levels.md` §3.27 for the measurements,
the refutation, and the ranked next step (hook the `0x02174EBC` funnel).

### 4.5 The novelty valves on bits 0–6 **[M]**

`bic #0x2A` / `bic #0x54` gated on the flags at `AI+0x2C+0x34`, and the
unconditional `and #0x7E`. **[M]** Whatever ids 1–6 are, the AI is
**structurally prevented from repeating them within a window**, and prevented
from id 0 entirely. **[I]** If ids 1–6 are the "walk forward / walk back /
approach / retreat" set, this is a **spacing defect by construction** — the
repeat-suppression is applied to the movement classes. Live evidence is
consistent and unhelpful: `+0x3A==2` for 524 of 1208 rows and `+0x3A==5` for 84
**[L]**, so 2 and 5 *are* used heavily despite the valve — which means the valve
clears on a short window, or the wheel is reached from the reaction table too
(§3). **[X]**

**What would settle it:** log `AI+0x2C+0x34` and `+0x48` together for one match.
The two are the same object and the same frame, so one capture answers both 4.1
and 4.5.

### 4.6 What is *not* on this list, and why

The `0x1A` site stays off. §3.11 and the tracker item's own refutation already settle
it: it is a **veto** that aborts a pending action, reviving it makes the CPU
*more* passive, and 11 of 20 archetypes ship bytes that can never fire. Adding
it to a "dormant but smart" list would be re-litigating a refuted reading. The
correct entry is in the table above as **suppressed-by-construction, and
correctly so**.

---

## 5. Ranked recommendation for judgement

Grounded in the trace evidence I have. **I am not able to support a single
recommendation from the traces alone**, and I will say so plainly rather than
rank something I cannot defend. What the evidence supports is an *order of
measurement*, and the first two are file reads.

> **CORRECTION 2026-09-27 — do not execute this ranking as written.** An external
> review (GPT-6 Astra, full plan in `a saved plan file`) checked this
> document against the overlay and found that several entries below rest on wrong
> addresses, all of which I then re-verified from bytes:
>
> - the reaction table is at **`0x02181438`**, not `0x021811F0` (the only ov11 literal
>   pointing at either address holds `0x02181438`), and its `0x7F` sentinel **does**
>   fire — see the corrected §4.4, which also decodes the loop as a cumulative weighted
>   pick over ids `{1..8, 11, 13, 14, 127}`;
> - the reaction path and the `+0x48` wheel are **alternative per-frame paths**, not
>   sequential (`0x0217AD60 beq 0x217ae04`);
> - `ctx+0xC0` has **ten** writers, so it is not a wheel-only observable (§2.2);
> - the `+0x18` partition is on the **sub-record**, i.e. `record+0xB4` (§2.3);
> - "`strd` does not exist on ARMv5TE" in `cpu-ai-levels.md` §3.14 is **false**.
>
> The consequence for the execution order is that rank 1 below ("the data route is
> closed") understates what is now open: the reaction table is a *live* weighted
> decision whose punish-band entries (ids 13/14) are reachable, and it is unmeasured.
> Treat rank 1 as **superseded by §4.4's settle-it capture**.

| rank | action | why | cost | what it decides |
|---|---|---|---|---|
| **1** | **Corrected 2026-09-26: the data files do not name the ids, and `0x021733B4` is a ROM byte map, not a file reader.** The route is code-side: the map at `0x02181100` (id → slot, slots 0..22) and then the behaviour-node list that slot indexes (`[obj+0xC]`). Find what fills that list. | the data route is closed by measurement (§1.4 correction) | one static trace | turns 13 of the 19 table rows from **[X]** to named |
| **2** | One capture: `AI+0x48`, `AI+0x10A`, `AI+0x2C+0x34`, `+0x105`, band, per frame | distinguishes 4.1 (empty mask = no-op) from 4.5 (windowed novelty) in a single capture, and fixes the unit of `0x10A` | one bridge capture, no patch | whether the frozen tail is an empty-mask no-op — the only row here that explains "does nothing" with no fallback |
| **3** | Map the opponent-state byte for ids 13–18 (`jus-ai-opponent-state-map-mbq6`, existing tracker item) | the remap arithmetic is measured; only the state's meaning is missing | existing tracker item, already scoped | whether punish/anti-air slots exist and are simply unselected |
| **4** | Only then consider *any* edit, and expect it to be in the per-move lists, **not** in `ai_param` | the mask is the throttle (§1.1) and the masks are not `ai_param` | — | — |

**What I will not recommend.** No `ai_param` byte, and no `0x0218190C` edit. The
playtest already priced both: the pivot raised activity with no judgement gain
because it moves the frequency of one branch inside a **uniform pick over a
suppressed set**. The levers that could change judgement are upstream of
`ai_param` — in the runtime behaviour-node list that the `0x02181100` slot map
indexes. The three mask arrays at `[AI+0x24]` have since been read (they are the
`+0x48` pick, and its `and #0x7E` clamp is a partition, not starvation — §1.3.2),
and `chr/ai/*.bin` does not carry the names (§1.4 correction). The node list is
the unread one.

**One caveat on my own confidence.** The spine in §1 is measured from bytes I
re-read at the cited addresses, and every scanner that produced it cleared four
named self-tests (§7). The *labels* in the "what it appears to do" column are
inferred, and ids 7–23 have no labels at all. A reader who takes §1 as settled
and §2 as speculative is reading it correctly.

---

## 6. What is solid and what is open

**Solid (re-read from bytes, self-tested scanner):** the 24-slot `cmp #0x18`
bound; `AI+0x48` as a 24-bit availability mask; the expand-then-weighted-pick at
`0x0217B000`–`0x0217B050`; the three mask readers at `+0x84/+0x90/+0x9C` and
the `AI+0x10A` three-band selector; the three suppression valves; the
give-up-on-empty-mask path; `0x0217B078` as a second gate sharing table
`0x0218190C`; the `+0x39`-is-a-phase / `+0x3A`-is-the-id correction; ids 13/14
being opponent-state-remapped; the reaction table's 18 live entries and its `-1`
terminator; the `0x7F` branch being dead on shipped data.

**Open, in the order I would close it:** the *names* of ids 7–23; the writer of
`[AI+0x24]+0x84/90/9C`; the unit and meaning of `AI+0x10A`; the live value of
`AI+0x48` (i.e. whether the empty-mask path ever fires); the opponent-state
semantics (`jus-ai-opponent-state-map-mbq6`); the meaning of `127` in the
reaction table; whether the 64 live `+0x3A==12` rows are representative of
anything — one 1208-frame capture with a 455-frame inert tail is not a base rate,
and the tail is unexplained.

**Not attempted, and I would not claim it:** that any of this is *the* cause of
the owner's complaints. The owners' reports are testimony; the three reports
(punishment, spacing, self-KO) are not in this document, and the self-KO root
cause in §3.14 is a separate, already-diagnosed, still-untested bug
(`jus-zmdb`).

---

## 7. Scanner and self-tests

Two scanners, both written fresh for this tracker item into `<TMP>/crew-xkxa/`,
both validated against **named known instructions** before any count was
believed. (Eight scanners on this project have previously been wrong; §3.10 of
`cpu-ai-levels.md` records one that missed every positive byte offset, and the
`+0xE4` census in §3.12 records one that asserted a dead-code result.)

`sweep.py` — capstone linear sweep of the 61,440-byte ov11 with `skipdata`,
sha256-checked against the doc. Four fixtures, all **PASS**:

| fixture | address | decoded |
|---|---|---|
| dispatcher head | `0x0217AB84` | `ldr r3, [r0, #0x4c]` |
| the id store | `0x0217ABA4` | `strb r1, [r0, #0x3a]` |
| the phase-8 store | `0x0217BAD4` | `strb r0, [r5, #0x39]` |
| §3.10's own fixture | `0x02180774` | `ldrb r1, [r0, #0xad]` |
| the documented gate | `0x02179130` | `cmp r1, #0x1b` |

`lib.py` — call-site and constant-argument enumeration, plus store-site
enumeration by memory displacement. Four fixtures, all **PASS**: `0x0217E7FC`
resolves `r1 = 11` from the `mov r1,#0xb` at `0x0217E7F8` (**the §3.13 action-11
claim, reproduced**); `0x0217ABA4` is found as a `+0x3A` store; `0x0217BAD4` as a
`+0x39` store; `0x02179150` decodes as the gate's profile read.

**Two bugs I introduced and caught, recorded because the pattern is the point:**
`ARM_REG_R1` is **67**, not 66 — I had hardcoded 66, which made every
`mov r1, #imm` read as "no definition" and would have reported the action-11
site as carrying an unknown argument. And the memory-operand detector tested
`type == 2` (immediate) where the memory operand is `type == 3`, which made
**every** store-site scan return empty. Both failed loudly on a named fixture,
which is the only reason they did not become wrong counts.

**Method limits, stated so the next reader does not over-trust the tables.** The
backward constant-propagation stops at any control transfer and looks back at
most 40 instructions, so a "DYN" in the tables means "not proven constant by this
scan", not "dynamic". The sweep is **linear**, so a handful of store sites in
`0x0217C418`–`0x0217C4FC` are almost certainly data decoded as instructions;
they are excluded from every claim above. Literal-pool words are read as
`ldr`-target arithmetic and were each checked against the address the `ldr`
implies (`0x0217B0A4` → `0x0218190C`, `0x0217AD6C`+`0x2FC` and
`0x0217ADB8`+`0x2B0` → `0x021811F0`), not assumed.
