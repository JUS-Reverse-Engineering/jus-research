# How the offline CPU AI levels work

**Tracker item:** `jus-oubd`. Supersedes the investigation notes in
[cpu-ai-patch.md](cpu-ai-patch.md) for everything about profile structure, the
decision gate, and patching; that file stays as the dated record of the first
pass and keeps its original claims and their original limits.

This document describes what the static analysis of the shipped ROM shows about
the offline CPU. It does not claim any measured improvement. No patch described
here has been run in the emulator yet, and the empirical section at the end says
exactly what is still unmeasured.

Everything here is static: disassembly of overlay 11, the profile table, and
byte-level diffing of the ROM against those two artifacts. The artifacts were
located in the ROM by content search and each claim below was re-read from the
bytes. A second-opinion review (`deepseek-v4.1-flash`) challenged the first-pass
claims; four of its corrections are folded in and marked where they matter.

---

## 1. Where the AI lives

| Thing | Where |
|---|---|
| AI code | ARM9 **overlay 11**, load base `0x02172A60` |
| `BattleAI_Create` | `0x02172A60` |
| AI manager | battle root `+0x128`; battle root pointer `0x02172960` |
| Per-player AI state | battle root `+0x118`, four entries |
| Profile data | `chr/ai/ai_param.bin`, 4272 bytes, loaded at match start |
| Per-character AI data | `chr/ai/<char>_b_NN.bin` (not analysed here) |

The file is in NitroFS, so the loader reads it at match start and the game
re-reads it on every battle. That makes the profile table a **data** lever: it
can be edited without touching code.

`arm9_ov11.bin` sha256 `1ab547c71612726599ef063d0f5909dff41c03661d97567cca873f8ef2e80db9`
`ai_param.bin` sha256 `e744be3925fa448e2a7b9a0016065ca74855b54e8dc52929cfac3d0ca99ad319`

ROM offsets, each verified by unique content match against the live ROM:

| Artifact | ROM offset | Size |
|---|---|---|
| `arm9_ov11.bin` | `0x001D7E00` | 61440 |
| `chr/ai/ai_param.bin` | `0x00F73260` | 4272 |

> **Overlay ambiguity.** ov10 and ov11 share the load address `0x02172A60`. ov11
> spans `0x02172A60`–`0x02181A60`; past `0x02181A60` is ov10-only. An address in
> the shared window is only attributable to ov11 if something else pins it —
> the strings `chr/ai/ai_param.bin` and the battle-root references do. The
> threshold table at `0x0218190C` is inside the window but is reached through a
> code path that only ov11's AI setup can enter.

---

## 2. The profile table: 89 rows of 48 bytes

`0x02179684`–`0x0217968C` compute `table + index * 0x30` and copy `0x30` bytes
via the ARM9 memcpy at `0x02051890` (`r0` = source, `r1` = destination,
`r2` = length). 4272 / 48 = 89 exactly.

### 2.1 `+0x2E` is the difficulty level

Battle-AI setup reads it and stores it per player, clamped:

```
02173100  ldrb  r0, [r0, #0x2e]     ; profile byte +0x2E
02173104  add   r1, r7, r6, lsl #2
02173108  strb  r0, [r4, #0x104]     ; per-player AI difficulty
0217310C  cmp   r0, #8
02173110  movhs r0, #7               ; clamp
02173114  strbhs r0, [r4, #0x104]
```

`+0x104` is read at 20 sites in the decision code. Because the shipped data only
uses `+0x2E` values 0–7, **the clamp at `0x0217310C` never fires on stock data.**
It is dead as a difficulty control.

### 2.2 The table is 20 archetypes × 4 difficulty steps

Rows 1–80 form 20 groups of four consecutive rows. Group *k* is rows
`1+4k … 4+4k`, and the group's `+0x2E` values are the difficulty ladder
`1, 3, 5, 7`.

`+0x2F` is the character selector: **exactly one row per group** — the last
row, `4+4k` — carries `+0x2F = k` for `k` = 0…19. The other 69 rows are `0xFF`.

The second-opinion review corrected the first pass on two points here, both of
which hold up against the bytes:

- The groups are **not** byte-identical apart from `+0x2E`. The fourth row is a
  separately tuned per-character profile, not just the same profile with a
  higher difficulty byte. Group 2, for instance, also differs at `+0x08`, `+0x09`
  and `+0x23`.
- **Group 18 is the exception to the ladder**: rows 73–76 carry
  `+0x2E = 2, 4, 6, 7`, the only occurrence of 2, 4 or 6 anywhere in the file.

Rows 0 and 81–88 are outside the picker: the picker scans `0x51` = 81 rows
(`0x0217958C`), so row 80 is the last candidate. Row 0 looks like a default
template; rows 81–88 are a trailing blob.

### 2.3 `+0x2F` is a bitmask index, `0xFF` means generic

The profile picker at `0x021793A8`:

```
02179430  ldrb  r3, [r0, #0x2e]      ; candidate difficulty
02179434  ldrb  r1, [r5, #0x2e]      ; requested difficulty
02179438  cmp   r3, r1
0217943C  bhi   #0x02179588           ; too hard, skip
02179440  ldrsb r6, [r0, #0x2f]      ; signed; 0xFF -> -1
02179444  cmp   r6, #0
02179448  blt   #0x0217946C          ; negative -> generic, accept
02179450  lsr   r3, r6, #5
02179458  ldr   r1, [r1, #0xa14]     ; 32 bits per entry
0217945C  and   r3, r6, #0x1f
02179464  tst   r1, r6, lsl r3       ; is this character enabled?
```

### 2.4 What the picker actually returns — corrected

`0x02179588` is the shared loop increment, not a break:

```
02179588  add   r2, r2, #1
0217958C  cmp   r2, #0x51
02179590  add   r0, r0, #0x30
02179594  blt   #0x02179430          ; all 81 rows are scanned
```

Every row is scored into a byte array, and a second pass at `0x02179598` picks
the **last surviving row**, with one carve-out for rows `0x4D`–`0x50`
(`0x021795B8`–`0x021795D4`).

So the answer to "first match or best match?" is **neither**: it is
last-surviving-row, with no difficulty maximisation. Because the file is
archetype-major and difficulty-minor, that means the *last archetype* that
survives the filters wins, at whatever difficulty it happens to offer.

### 2.5 The picker is not the combat difficulty menu

This is the most consequential correction from the second opinion, and it
overturns the premise of the first pass.

The picker has exactly one caller: ov6 `0x0216077C`, via the ov11 thunk at
`0x02172FEC`, immediately after a check of the AI manager at battle root
`+0x128`. The value it treats as the *requested* difficulty is computed at
`0x02160408`–`0x02160440`:

```
02160408  ldrsb r0, [r0, #0xa]      ; some signed per-entry byte
0216040C  ldrh  r1, [sb, #0x4c]
02160414  addeq r0, r1, #2          ; else subne r0, r1, #1
0216042C  strh  r0, [sb, #0x4c]
02160430  asrs  r0, r0, #5          ; / 32
02160438  cmp   r0, #7
02160440  strb  r0, [sl, #0x2e]     ; "requested difficulty"
```

A 0–255 quantity divided by 32 and clamped to 0–7. That reads like a
**popularity or strength rating**, not a menu setting. The three combat
difficulty options are not shown to flow through here.

**The combat CPU takes a different path.** At `0x021730DC` it reads a byte at
`0x020B0038 + player_index * 0x4C` and passes it straight to
`BattleAIState_Create` at `0x02178FF8`, which uses it as a direct row index.
A saved difficulty of 0 is substituted when battle root `+0x154 == 5`, a mode
whose meaning is still unknown.

**Open:** who writes `0x020B0038 + i * 0x4C`, and does the menu set it, is not
established. This is the first thing to measure live, because it decides which
row the CPU actually gets.

---

## 3. The decision gate

Nearly every "should the CPU do X" test funnels through one function at
`0x02179130`.

```
02179130  cmp   r1, #0x1b
02179134  ble   #0x02179198           ; index <= 0x1B -> refuse
02179138  sub   ip, r1, #0x1b
02179140  ldrsh r2, [r2, #0x3c]      ; cooldown, 16-bit
02179144  cmp   r2, #0
02179148  movne r0, #0               ; cooling down -> refuse
02179150  ldrb  r3, [r0, r1]         ; profile byte at this offset
02179154  cmp   r3, #8
02179158  movhs r1, #1               ; >= 8 bypasses threshold comparison
02179160  ldr   r1, [pc, #0x38]      ; pool 0x021791A0 -> 0x0218190C
02179168  ldr   r1, [r1, r3, lsl #2] ; 8 x u32 thresholds
0217916C  and   r2, r2, #0xff        ; low byte of cached RNG at +0x38
02179170  cmp   r2, r1
02179174  movls r1, #1               ; RNG <= threshold -> take it
02179178  movhi r1, #0
02179188  moveq r1, #0x1e            ; else arm a 30-tick cooldown
```

Threshold table at `0x0218190C`, `u32 × 8`:

| index | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | ≥8 |
|---|---|---|---|---|---|---|---|---|---|
| value | 64 | 76 | 102 | 128 | 166 | 179 | 217 | 243 | — |
| acceptance fraction | unknown | unknown | unknown | unknown | unknown | unknown | unknown | unknown | threshold bypassed |

The first eight entries are thresholds, not measured acceptance rates. The
distribution and writer of the compared value at each call are unresolved (§3.10).

### 3.1 One call site is dead in the stock ROM

`0x0217A6C4` passes `r1 = 0x1A`. The gate refuses any index `≤ 0x1B`
(`0x02179134`), so that behaviour can never fire, and **no data edit can
revive it** — the early-out happens before the profile byte is read.

The live parameters are `0x1C, 0x1D, 0x1F, 0x21, 0x22, 0x23, 0x24, 0x25`. The
eleventh call site, `0x021801D4`, passes `0x25`; a `ldr r1, [r0, #0x34]` sits
four instructions earlier but is a separate flag test, not the gate argument.

### 3.2 Most archetypes sit at the lowest acceptance row

Across the 20 archetype groups, **91 of 160 live gate-parameter cells are 0**,
which selects the lowest threshold. Archetype 0 reads:

```
offset    0x1C 0x1D 0x1F 0x21 0x22 0x23 0x24 0x25
value       0   0   0   0   0   6   1   1
threshold  64  64  64  64  64 217 102 102
```

> **Correction (2026-09-26, after subagent review).** An earlier version of this
> section said 90 cells, described the threshold table as bytes, and rendered the
> row above as percentages (25%, 85%, 30%). All three were wrong:
>
> - The count is **90 or 91 depending on which row of a group you call the
>   archetype**, and the document had it wrong in *both* places at once. §3.2
>   illustrates archetype 0 using **row 1** (the first-row convention) but counts
>   using the **third-row** convention. The entire difference is one cell:
>   archetype 8's `+0x24`, which is `3` in rows 33–34 and `0` in rows 35–36. All
>   twelve of this document's own patch offsets land on the third row, so **91 is
>   the consistent figure for the patch** and 90 is the consistent figure for the
>   illustration. Pick one convention and state it. This is a convention artefact,
>   not a new fact about the data.
> - The table at `0x0218190C` is **8 words, not 8 bytes**. The gate indexes it
>   `ldr r1, [r1, r3, lsl #2]`, so reading it as bytes yields
>   `[64,0,0,0,76,0,0,0]` — a different table. The values were right; the width
>   was not.
> - **A profile byte of 0 *is* consulted.** It selects threshold row 0. Only a
>   *dead index* is skipped, not a zero byte. `0` is the floor, not a null.
> - The percentages are **not safe to state** and have been removed pending
>   §3.10. They assumed a roughly uniform roll; that assumption is not
>   established.
>
> The direction of the finding survives: most archetypes sit at the lowest
> acceptance row, which is the mechanical reason the CPU looks passive. The
> *size* of the effect does not, and no patch should be justified on a percentage
> from this table until §3.10 is settled.

### 3.10 The roll's distribution is unknown, so every percentage above is provisional

A subagent review established, and I confirmed against the bytes, that the
per-frame AI callback at `0x0217569C` **never touches the roll field**. It
touches `+0x3C` — twice, once zeroing it at `0x021756BC` and once incrementing it
at `0x021756FC`–`0x02175700`:

```asm
021756BC  strb   r0, [r8, #0x3c]    ; r0 = 0, zeroed each frame
...
021756F8  ldrb   r0, [r8, #0x3c]
021756FC  add    r0, r0, #1
02175700  strb   r0, [r8, #0x3c]    ; incremented each frame
```

> **Third correction (2026-09-26, after refutation) — the inference chain here is
> broken, and this section should not be read as establishing anything about the
> roll.** The refutation established that the per-frame callback's `r8` and the
> gate's `r0` are **different objects**. The callback's `r8` is reached via
> `ldr r1, [sl, #4]` then `ldr r8, [r1, #0x10]`, and the callback treats
> `[r8+0x24]` as a bitfield and rewrites it every frame. The gate's `r0` comes
> from `ldr r0, [r4, #0x2c]` and behaves as a 104-byte `new(0x68)` object with a
> one-time back-pointer at `+0x30`. A single object cannot be both: the callback
> would overwrite that back-pointer every frame.
>
> So when this section says "the callback never touches the roll field", it is
> describing a **different struct** from the one the gate reads. The observation
> is true and the conclusion is not licensed. Whether the roll is refreshed per
> frame is **open again**, and must be re-established on the correct object.
>
> The multi-writer finding below is unaffected — it is about the *gate's* object
> and was measured on sites that provably share the gate's base.

The per-frame callback at `0x0217569C` touches `+0x3C` and not `+0x38` on
its own object; it does not establish the gate object's writer set:

> **Second correction (2026-09-26).** An earlier version of this section said the
> roll has "exactly two writers". **That was an artefact of a broken scanner** and
> is now withdrawn. My offset filter matched only subtractively-offset
> word/halfword accesses, so it missed *every* byte access with a positive
> offset. This is the same bug class the subagents were warned about, and I
> committed it anyway.
>
> A corrected filter — validated against the known `ldrb r1, [r0, #0xAD]` at
> `0x02180774` before being trusted — finds **15 candidate stores** at offset
> `+0x38` in ov11. The offset match alone does not prove that each store
> addresses the gate's object:
>
> | provenance | sites | what it stores |
> |---|---|---|
> | PRNG draw (word) | `0x021790DC`, `0x021796D4` | `bl 0x2031070` then `str r0` |
> | caller-supplied (byte) | `0x0217AAB0`, `0x0217AB5C` | `strb r1` — the caller's own `r1` |
> | other (byte/word) | 11 sites | mixed bases, not yet attributed; includes an unrelated pointer store |
>
> One of the 15, `0x021765A4`, stores **r4** — a pointer — into an object whose
> base comes from `ldr r0, [r6]`, a different global. It is not a roll writer.
>
> **This makes the situation worse than "unknown distribution", and it is the
> correct reading:** confirmed stores have mixed provenance. Some sites feed a
> PRNG draw, others use a caller-supplied value. The gate reads the low byte of
> the word at `+0x38` (`ldr r2, [r0, #0x38]` then `and r2, r2, #0xff`), so
> whichever writer of that object ran last determines the value.
>
> The correct conclusion is therefore **site-dependent, not uniform**: there is no
> single distribution to reason about, and each of the 11 gate call sites may see
> a differently-sourced value. Any statement of the form "this gate accepts X% of
> the time" is unsupportable until the writer on each path is identified.
>
> The access-path finding in §3.6 survives: these gate routines read `+0x38`.
> The earlier claim that acceptance is perfectly nested is withdrawn. That
> requires the calls to observe the same unchanged value, which has not been
> established with mixed writers and per-call provenance still open.

**Not established:** the following are false as stated, per refutation.

- **The latch alarm dissolves.** The decrement loop at `0x021796A8` runs
  `k = 0..11`, covering `+0x3C..+0x52`, which **contains all eight live latches**,
  and it has a floor at 0. The latches therefore *do* reach zero; no reset store
  is needed. "No clear was found" was an artefact of offset scanning, which
  cannot prove absence — an exhaustive store scan over `+0x3A..+0x74` returns 41
  `strb` to `+0x3E` alone, nearly all of them other structs.
- **"The direction is uniform across all its call sites" is false.** Ten sites
  treat a return of 1 as "act"; the `0x1A` site **inverts** it; and the adjacent
  `0x1D` site uses the identical `cmp r0,#0` / `moveq` idiom with the *opposite*
  sense. The gate's return convention is therefore **not** uniform, which also
  means a blanket edit to the shared table is riskier than §4 assumed.

### 3.11 The dead `0x1A` site is a veto, not a behaviour

The tier-2 patch revives the `0x1A` call site by moving the gate's early-out. A
subagent review flagged, and I agree, that this was framed backwards: the
success branch at that site sets the step counter to 0, which **aborts** the
pending action rather than selecting one. So reviving it makes the AI *more
passive*, not more active, and 11 of 20 archetypes ship veto bytes there that
can currently never fire.

This is a third independent reason tier 2 should not be treated as an upgrade on
tier 1, alongside the per-archetype inconsistency already noted in §4.

### 3.3 The cooldown is a failure throttle, not a success throttle

The gate writes `30` only when the roll **fails**. A successful roll sets
nothing. Raising a parameter to `≥ 8` bypasses this threshold failure path;
it does not bypass cooldown or the caller's other preconditions. The 30-tick
throttle is not armed by that path, and the action can become reachable on each
eligible decision tick. This is the main reason the shipped `≥ 8` profiles are used
sparingly, and the main hazard of an aggressive patch. Section 5 returns to it.

`0x1E` is a count of callback updates decremented by `0x02179694`, not a
measured frame count. Whether that callback runs exactly once per frame is not
established by the code read here, so "30 ticks" should not be written down as
"30 frames".

### 3.4 The other gates, and the one that runs backwards

Three more probability gates read a value at state `+0x38`:

| Address | Test | Direction |
|---|---|---|
| `0x0217920C` | `(rng & 63) < profile[+0x11]` | higher byte → **more** |
| `0x02179278` | `(rng >> 3) & 31 > min(profile[+0x12], 31)` | higher byte → **less** |
| `0x02179228` | band scan on `profile[+0x0F]`, then `(rng >> 1) & 255 ≤ band` | higher byte → **more** |

`+0x12` is **inverted**. A blanket "raise every parameter" is wrong: it would
reduce that behaviour. The gate's return is also interpreted differently at
some call sites (§3.10), so the effects of a shared-table edit need site-level
review.

Five band gates use the shape of `0x02179228` (`+0x08`, `+0x0C`, `+0x0D`,
`+0x0F`, `+0x10`). The first pass reported only the `+0x0F` one as a discovery;
it is one of five. The band table at `0x021811F4` (stride 2) is
`[4, 16, 32, 64, 96, 128, 160, 192]`, with the interleaved acceptance table at
`0x021811F5` = `[12, 38, 76, 102, 128, 166, 204, 243]`.

### 3.5 The shared table is overloaded

The table at `0x0218190C` is the row→threshold table for `0x02179130`; the band
gates index it too (`0x021792D0`, `0x0217932C`, `0x0217B084`, `0x0217D428`,
`0x0217E400`, `0x0217F738`, `0x0217FE0C`). Editing it changes several unrelated
behaviours at once, which is why the conservative tier leaves it alone. It is
indexed as **words**, not bytes — see the correction in §3.2.

> **Correction (2026-09-26).** `0x0217B078` is not merely another indexer of this
> table — it is a **second, stripped copy of the main gate itself**. Same table
> (`ldr r2,[pc,#0x18]` → pool word at `0x0217B0A4` = `0x0218190C`), same
> `cmp r1,#8` / `movhs` bypass, same `and r1,r3,#0xff` / `movls`. It has **three**
> call sites, all with computed indices: `0x0217AC7C` (`[r4+0x104]`, raw
> difficulty), `0x0217ACF8` (`max(0, difficulty-5)` — this is the live pivot), and
> `0x0217B578` (`[r7+0x104]`). So **the pivot does not feed this gate through one
> of §3.1's live parameters `0x1C`…`0x25`**; its argument is `difficulty-5`
> clamped at zero. Any attribution of the pivot to those offsets is wrong. See
> [`ai-behaviour-taxonomy.md`](ai-behaviour-taxonomy.md) §0.2.

### 3.6 The gates read a shared field; per-call correlation is open

The main gate and three other gate routines read the `+0x38` field. In the
main `0x02179130` gate:

```asm
02179150  ldrb    r3, [r0, r1]       ; profile param for this index
02179154  cmp     r3, #8
02179158  movhs   r1, #1             ; >= 8 -> unconditional pass
0217915C  bhs     0x217917c
02179160  ldr     r1, [pc, #0x38]    ; threshold table 0x0218190C
02179164  ldr     r2, [r0, #0x38]    ; value later masked to its low byte
02179168  ldr     r1, [r1, r3, lsl #2]
0217916C  and     r2, r2, #0xff
02179170  cmp     r2, r1
```

The reads show shared storage, but the value may change between calls. The
mixed writers in §3.10 make the original inference of perfectly nested
acceptance and a causal explanation for repeated actions premature. If two
calls observe the same unchanged value, their threshold results are correlated;
whether that happens in play is the open per-call trace in
`jus-ai-roll-writer-trace-xgig` (`jus-tx3b` records the bounded static finding).

### 3.7 Where the roll comes from, and how far the trace goes

Two confirmed PRNG-fed word stores in ov11 follow this shape:

```asm
021796C4  ldr     r0, [pc, #0x10]
021796C8  ldr     r0, [r0]
021796CC  ldr     r0, [r0, #4]
021796D0  bl      0x2031070          ; draw
021796D4  str     r0, [r4, #0x38]    ; cache into the AI state
```

(the other is `0x021790DC`). The earlier count of three included
`0x021765A4`, a pointer store into another object, and is withdrawn. Two
caller-fed byte stores and other candidate sites remain to be attributed
(§3.10). `0x2031070` is not in ov11; it
resolves into the **main ARM9 binary** at offset `0x31070`. It is a
**xorshift128** generator:

```asm
020310A4  eor     r2, r2, r2, lsr #11
020310A8  and     r0, r0, r2, lsl #7
020310AC  eor     r2, r2, r0
020310B0  and     r0, r1, r2, lsl #15
020310B4  eor     r0, r2, r0
020310B8  eor     r0, r0, r0, lsr #18
```

with a draw counter at `+0x9C4` that forces a "reseed" every `0x270` = **624**
draws. That reseed (`0x2030F68`) has exactly one caller, and it deliberately does
**not** re-seed once the state is live:

```asm
02030F70  ldr     r1, [r5, #0x9c8]
02030F78  cmp     r1, #0
02030F7C  bne     0x2030f88          ; already seeded -> keep the state
```

The expansion routine `0x2030F24` that does run is **not an entropy source**. It
takes one 32-bit word and expands it into the 624-word table with a fixed
recurrence (`mla r3, r2, r1, lr`). No timer, no hardware register, no input.

That traces one source of values that can reach `AI+0x38`; it does not establish
that every gate call sees a PRNG draw. The seed itself comes from a virtual call:

```asm
02030DD8  ldr     r0, [pc, #0x20]    ; 0x020A0C34
02030DE0  ldr     r0, [r0, #0x2c8]
02030DE4  ldr     r1, [r0]
02030DE8  ldr     r1, [r1, #8]
02030DEC  blx     r1                 ; <- the seed
02030DF0  str     r0, [r4, #4]
```

**This is where the static trace stops.** Whether the CPU plays the same random
sequence in every match depends entirely on what that vtable slot returns. It
takes no visible argument and returns one word, so it is consistent with a tick
counter (varies) or with a constant / already-deterministic value (does not
vary). Resolving it needs the concrete vtable, or an empirical A/B: play the same
match twice and compare the AI's action sequence. That is `jus-kjo7`.

The earlier claim that shared-byte nesting independently causes repetition is
withdrawn. Writer attribution and values between gate calls remain open in
`jus-ai-roll-writer-trace-xgig`.

### 3.8 The threshold table is authored data in the cartridge

> **Corrected after refutation (2026-09-26).** An earlier version of this section
> said `0x0218190C` sits past `ram_size` and is therefore in BSS, "runtime-built,
> not authored". **That was wrong**, and I checked it rather than taking the
> refutation on trust. `0x0218190C − 0x02172A60 = 0xEEAC = 61,100`, and ov11's
> file is 61,440 bytes. The address is **340 bytes inside the file-backed image**,
> not past it. The table is ordinary authored data at ROM `0x001E6CAC`, and it
> reads straight from the file:
>
> ```
> words = [64, 76, 102, 128, 166, 179, 217, 243]
> bytes = [64, 0, 0, 0, 76, 0, 0, 0, 102, 0, 0, 0, 128, 0, 0, 0, ...]
> ```
>
> The "words vs bytes" trap is real and is exactly what bit me: the gate indexes
> with `ldr r1, [r1, r3, lsl #2]`, so reading the table as bytes yields a
> completely different, meaningless table.

This is good news for tier 3, which edits the shared table. It is a real,
authored, static target rather than a computed structure of unknown derivation.
The caveat from the original text still stands and is the reason tier 3 is not
the default: the table is indexed by **seven** sites, not one, so editing it
changes several unrelated behaviours at once.

### 3.9 One opponent-state accessor returns a byte

The AI reaches its opponent through a single accessor:

```asm
02174F4C  ldr     r0, [r0, #4]
02174F50  ldrb    r0, [r0, #8]      ; one byte
02174F54  bx      lr
```

**18 call sites** in ov11 use this accessor. The observed uses include:

| Use | Site | Meaning |
|---|---|---|
| `cmp r0, #1` | `0x0217E864` | opponent is in state 1 |
| `cmp r0, #2` | `0x0217E880` | opponent is in state 2 |
| `(r0 - 3) * 2 + 0x0D` | `0x0217E910` | state ≥ 3 selects a table index |

The third form distinguishes values 3, 4, 5, 6 by selecting indices 13, 15,
17, 19. Another use adds a value-dependent offset to an action:

```asm
0217BEB0  ldrsb   r1, [r4, #0x3b]    ; the action it already picked
0217BEB4  sub     r0, r0, #3
0217BEB8  add     r0, r1, r0, lsl #1 ; action += 2*(byte - 3)
```

Other opponent information includes a **flags word** at entity `+0x68`, of
which three bits are tested in this path (`0x40`, `0x10000`, `0x20000` at
`0x0217E900`, `0x0217E854`, `0x0217E870`), and a **position halfword** at `+0xB0`
and `+0xB4`, sign-extended through `lsl #16 / lsr #16` and compared as an
integer part.

The original claim that this byte is the AI's *entire* opponent model and the
root cause of poor punishment, careless attacks, and the Yugi beam problem is
withdrawn. The flags and position reads above already refute the "entire model"
part; the complaint explanations were never measured. The meanings of values
1 and 2, the selected rows for higher values, and any causal effect in play
remain open in `jus-ai-opponent-state-map-mbq6` (`jus-phqu` records the bounded
static accessor finding).

> **CORRECTED 2026-09-28 — the byte is not a state at all.** The writer of `[ctx+4]` is
> `0x021745D0`, inside the mask builder `0x02174330`, and it stores
> `0x02076CE0(table, row, col)` = `[[table + col*20 + row*4 + 8] + 0x34]`, with `row`/`col`
> derived from the settings record at `[ctx]`. So it is a **constructed grid lookup**, not a
> per-frame read.
>
> Measured over one 3001-frame replay in which the CPU attacked (state 9, 188 frames),
> dream-attacked (11, 113), walked (1, 82) and went airborne (6, 28) while both fighters crossed
> the stage: **the byte is 3 on all 3001 frames**, and it equals neither entity's `+0x18` nor the
> CPU's battleObj state on any frame. Its two would-be state branches (`osb == 1` at `0x0217E864`,
> `osb == 2` at `0x0217E880`) are additionally gated on entity `+0x68` bits `0x10000`/`0x20000`,
> which are **absent on both entities** (`0x36D`, `0x126`) — so those branches are dead here
> regardless of the byte.
>
> The value it *does* feed is the family selector `13 + 2*(osb - 3)` (`0x0217E910`), the same
> arithmetic as the issuer's 13/14 remap — a **static** family selection, not a punish signal.
> See the plan's step 7 first static pass.

> ## 3.12 CORRECTED — the AI is *not* blind to the ledge
>
> **Everything below the original §3.12 conclusion was wrong, and so were two
> things I told the owner. Correcting in place because the retraction is the
> useful part.**
>
> I claimed ov11 has no stage-edge awareness, on the evidence that no stage-width
> *immediate* appears anywhere in the overlay. The scan was correct and the
> inference was not. **The bounds are not immediates — they are data fields, and
> the AI reads them.** A refutation pass found this and I verified it at the byte
> level rather than accepting it:
>
> ```asm
> 021778B0  ldr   r1, [r5, #0x150]   ; a limit
> 021778B4  cmp   r2, r1
> 021778B8  bge   0x21778D4
> 021778BC  ldr   r1, [r8, #0x10]
> 021778C0  ldr   r1, [r1, #0x78]    ; the engine's flags word
> 021778C4  tst   r1, #8             ; RIGHT-wall bit — TESTED
> 021778C8  ldreq r1, [r4, #0xe4]
> 021778CC  orreq r1, r1, #4
> 021778D0  streq r1, [r4, #0xe4]    ; folded into the AI's own mask
>
> 021778D4  ldr   r2, [r5, #0x150]   ; the limit again
> 021778D8  ldr   r1, [r5, #0x158]   ; plus an extent
> 021778E0  add   r0, r2, r1         ; limit + extent == the OTHER limit
> 021778E4  cmp   r3, r0
> 021778F0  ldr   r0, [r0, #0x78]
> 021778F4  tst   r0, #4             ; LEFT-wall bit — TESTED
> ```
>
> Three corrections follow:
>
> 1. **The flags word is at `+0x78`, not `+0x68`.** The `+0x68` word I cited is a
>    *different* struct — a data-table-driven property bitset, read on two
>    unrelated types — and bits `0x4`/`0x8` are **never tested anywhere in ov11**.
>    My proposed fix would have patched the wrong variable.
> 2. **The AI does not merely read the wall bits, it acts on them** — folding them
>    into its own `+0xE4` mask. The engine's collision information reaches the AI.
> 3. **`[+0x150]` and `[+0x158]` are used as a limit and an extent**, so
>    `limit + extent` is the opposite limit. That is the shape of stage bounds. The
>    values were the open question here, and they are now answered — see §3.14.
>    **They are zero.** Not 64.0 and 896.0: zero, from construction onward.
>
> A second refutation found the `cmp r0, #0x4000` / `#0x3c000` clamp I verified in
> arm9 is probably **dead code**: 0 branch targets for any of the 20 entries in the
> arena function table, 0 PC-relative references, 0 stored pointers. The project's
> own confirmed-facts file names *different* live writers (`0x0207F8DC`,
> `0x0207ECC0`, `0x0207ED08`, with the wall bits specifically at `0x0207ED2C` and
> `0x0207ED88`). So the clamp is a real instruction sequence that appears to be
> unreachable, and my "verified engine wall collision" was verifying dead code.
>
> **The "0 of 9,772 live samples" figure that supported this is dead, and it was
> never a sample count.** `9772` occurs in the project only as a *frame number*. The
> wall bits do fire on contact: driving a fighter into the left wall yields
> `M+0x78 = 0x66` with bit `0x4` set on 221 of 690 frames, and into the right wall
> `0xAA` with bit `0x8` on 50 of 660. The original zero counts came from captures
> with **no wall contact in them**. A related claim of mine — that bit `0x1` is set
> and the source doc is therefore over-broad — was also wrong: bit `0x1` is set on 0
> of 6250 frames, and what accompanies `0x22` is `0x08000000`, not `0x1`.
>
> **And my corroboration for it was wrong.** I claimed a runtime note independently
> confirmed 956.0, and called it unusually strong. The note exists, but with
> x = −100.0 the *left* arm yields 68.0, not 956.0 — 956.0 requires x on the
> opposite end of the axis. The note also says the stage x *wraps*, which a
> reflecting clamp does not do. And `0x0003BC00` occurs **27 times** in the ROM,
> not once. I presented a circular argument as strong evidence.
>
> **Where this leaves the self-KO.** The code reads boundary-like fields at
> `+0x150`/`+0x158` and wall bits. Their live values and the branch taken before
> a self-KO have not been measured. The watchpoint in `jus-zmdb` must establish
> how this path behaves before choosing a patch.

### 3.13 A candidate-object comparison is not an arena bound

A refutation pass claimed ov11 *does* have stage-bounds awareness, with the arena
width carried as a per-object field at `+0xB0`. **That is an over-claim and the
bytes do not support it.** What `+0xB0` actually is:

```asm
0217E7DC  ldrsh   r1, [r0, #0xb0]     ; a per-OBJECT threshold
0217E7E0  ldrsh   r0, [r5, #0x60]     ; the AI's own position component
0217E7E4  cmp     r1, r0
0217E7E8  bge     0x217E810
0217E7EC  mov     r0, r5
0217E7F0  bl      0x217e3a0
0217E7F4  mov     r0, r5
0217E7F8  mov     r1, #0xb
0217E7FC  bl      0x217ab84           ; -> issue action 11
```

The shape is *"when my position component passes a threshold fetched from this
object, fire action 11."* It is a **proximity trigger against a looked-up
candidate**, not an arena boundary: the base `r0` comes from a table lookup, and
the field is used as a threshold to compare *against*, never as a width. The same
shape repeats at `0x0217E8B8` and `0x0217E954`. A capstone sweep of all 61,440
bytes with `skipdata` enabled finds `+0xB0` has **6 halfword reads and 0 writes**
in ov11 — it is populated from outside the overlay, and nothing in ov11 ever
compares a position against the arena.

This `+0xB0` path compares against a candidate object. The earlier conclusion
that *every* AI position comparison is fighter-relative, and that the engine
never tells the AI about arena bounds, is withdrawn: §3.12 identifies separate
reads of boundary-like fields at `+0x150`/`+0x158` and wall bits. The proposed
8–12 byte guard edits at `0x0217E7E4`, `0x0217E8C0`, and `0x0217E95C` were
based on that withdrawn premise. Test the existing boundary path first in
`jus-zmdb`.

**Not established, and it is one watchpoint away:** which of `AI+0x60` and
`AI+0x64` is X. The refutation confirmed the pair is *not swapped* and that
`+0x64`=X, but the assignment rests on reading two adjacent int16 fields at
entity `+0x18`/`+0x16` and cannot be settled statically. If `+0x60` turned out
to be X, the analysis above would need revisiting. Watching both fields while a
fighter moves horizontally settles it in one capture.

### 3.14 ROOT CAUSE: the AI's arena bounds are never populated

> **Status (2026-09-26): verified fields, unverified cause.** The zeroed fields,
> the absent writer and the dead right-wall block are all measured. The causal
> link to either symptom is **not**: the bounds block does not execute during the
> freeze, and it does not execute at all in the walk-off fixture. No measurement
> yet connects the zeroed fields to the CPU walking off. Read §3.17 before
> acting on this section.

This supersedes the open questions in §3.12 and §3.13, and it is the answer to
the ledge complaint. It is stated here rather than in a research note because it
changes what the patch should be.

**The AI reads its arena limits from a heap `BattleAIMove` object at `+0x150` and
`+0x158`. Both are zero, always.** The object is allocated at instance size
`0x190` and its creator zeroes the whole thing and never writes those fields again:

```asm
02176950  mov   r0, #0x190
02176960  bl    #0x201A21C      ; operator new(0x190)
02176984  mov   r2, #0x190
02176988  bl    #0x20517FC      ; memset(obj, 0, 0x190)
```

The function is `0x0217693C`–`0x02176BEC`; it is `BattleAIMove_Create` because both
`"BattleAIMove_Create"` (`0x02181888`) and `"BattleAI_Move.cpp"` (`0x0218189C`) are
loaded inside it. It initialises `+0x00..+0x0C`, the list links at `+0x08`/`+0x0C`,
the owner pointer at `+0x10`, and `+0x14..+0xE3` as seven `0x28`-byte records — and
then stops. **`+0xE4..+0x18F` is left at the memset's zero, and `+0x150`/`+0x158`
are inside that range.**

Confirmed three independent ways: the creator itself; a ROM-wide census of every
`bl` to the operator-new thunk, which finds 11 sites in ov11 of which **exactly one
allocates `0x190`** (the other four `0x190` allocations ROM-wide are
`ALWidgetImp.h`/`Create` in ov0/ov3/ov7, a different class in the `0x0214CD20`
window); and a live read showing `0` in every frame of every run, across three
separate match branches.

**There is no hidden writer, and this is structural rather than a failed search.**
**CORRECTION 2026-09-27:** the *reason* first given here was wrong. It said "`strd`
does not exist on ARMv5TE" — **it does exist**, so that argument is void. A fresh
scan of ov11 for `STRD`/`LDRD`-shaped words finds **none** in the immediate-offset
encoding, so the conclusion survives for this overlay; but the absence proof is
weaker than it was stated. Register-offset forms, `STM`, adjusted pointers and
bulk copies are all still outside what that scan excludes, and what actually
settles the field is the measurement: it reads 0 on every frame of every run.
The remaining instruction-width argument is unaffected — `ldrh`/`ldrsh`/`ldrsb` carry
only an 8-bit immediate in ARM state (max `0xFF`); only word `ldr`/`str` and
`ldrb`/`strb` get 12 bits. In Thumb-1 the largest immediate offset of any width is `0x7C`. The
class's sinit table has two entries and both zero large `.bss` arenas rather than
a `0x190` instance — the class is heap-only and correctly has no sinit entry.

**The consequence is worse than a stale value.** With both limits at zero the
AI's arena is the *empty interval* `[0, 0]`, so its boundary tests collapse to
`position <= 0`. And the zero limits have a second, sharper effect:

```asm
021778AC  ldr   r2, [r0, #0xc]     ; the fighter's x
021778B0  ldr   r1, [r5, #0x150]   ; == 0
021778B4  cmp   r2, r1              ; x vs 0
021778B8  bge   0x21778D4           ; taken for any x >= 0
021778BC  ldr   r1, [r8, #0x10]
021778C0  ldr   r1, [r1, #0x78]
021778C4  tst   r1, #8              ; RIGHT-wall bit — UNREACHABLE
```

That branch is always taken for a non-negative position, so the block containing
it is dead in practice — and `0x021778C4` is the **only** site in the function that
tests the engine's right-wall bit. The left-wall test at `0x021778F4` survives,
because its guard at `0x021778E8` is `ble 0x0217904` and a positive position falls
through it. **So the AI tests exactly one of its two wall senses, and never the
other.** The missing data has not merely made the AI slow to notice a wall; it has
deleted one of the two ways it could notice.

**What this retires.** The edge-guard injection plan is dead, and it was dead
twice over: first because the AI was not blind to the ledge after all, and now
because the blindness is not a missing-guard problem at all. Injecting a bounds
check into a function whose bound fields are unpopulated would have added a
second, competing source of geometry to a struct that already has one — and
would have left the real bug in place.

**The fix is to seed two fields — and it is a code change, not a data change.**
That reverses a claim this section made earlier, which called it "a data or
init-time change, not a code injection, and the cheapest class of fix available
on this board." §3.15 shows why: the table the values come from does not exist in
the ROM, so they cannot be authored as data.

### 3.15 Where the values come from: the bounds record is `0x021B9AA0`

**The pair `(0x4000, 0x37FFF)` that this section previously dismissed *is* the
arena bounds.**

| field | value | px |
|---|---|---|
| `+0x10` | `0x00004000` | 64.000 — left wall |
| `+0x00` | `0x00037FFF` | 895.996 — **w − 1** |

⇒ `x ∈ [64, 960)` exactly. Left wall `x = 64` at `0x021B98D8` and `0x021B9908`;
right wall `x = 0x3C000` = 960.000 at `0x021B98F0`. The table is 21 records of
stride `0x18` at `0x021B98D8..0x021B9ACF`, in an address range that also holds a
281-record stride-8 table and a stride-`0x10` one — an earlier reading of a single
325-record stride-`0x20` array here was wrong.

**The record layout is proved by arithmetic, not guessed.** Across 21 of 21
records `+0x10`/`+0x14` are *always* exact multiples of `0x100`, and `+0x00`/`+0x04`
are *always* exactly one `1/256` below a whole pixel and *never* whole: a half-open
rect with `w`/`h` stored as `size − 1`.

**Seed `+0x158 = 0x00038000`, not `0x00037FFF`.** The off-by-one is real — all six
`0x37FFF` occurrences in RAM are extent fields, and all 22 `0x38000` occurrences
are unrelated — and the consumer cannot add the one back: `add r0, r2, r1, #1` was
proposed and rejected by an `armv5te` assembly oracle, because ARM `add` has no
four-operand form and the sequence has no spare slot.

**This corrects a refutation of mine that was true and irrelevant.** I withdrew the
pair because `0x00037FFF` occurs **zero times ROM-wide** as a 32-bit word. The table
is absent from **all 64 MiB of `jus.nds`** — it is built at load time. Scanning the
ROM for a RAM-resident table was the wrong medium, so the negative carried no
information. *A negative scoped to the wrong medium is not evidence.*

**Not per-stage.** A tightened signature scan over all 4 MiB finds exactly 21
matching records in one cluster; records 8–17 are a staircase of ten 64×64 boxes.
One global table, no per-stage variation in RAM.

**The linked list at `0x02183Bxx` is not the arena** — 11 nodes plus 2, stride
`0x20`, `{next, prev, TAG, X, Y, w−1, h−1, id}`, its ten nodes being the *live
subset* of the staircase. It is a traversal cursor. Likewise the five-word run
`(0xC000, 0x2A000, 0x27FFF, 0x7FFF, 0x10012)` seen twice on `r5` is that list's
head-node quad, not a `64`/`960` pair. `+0x150` is 16 verified zero bytes.

**So the fix is a small code change at ov11 load time**, reading rec19 `+0x10` into
`+0x150` and `0x00038000` into `+0x158`. It needs a code cave. **Arithmetic
correction (2026-09-27):** the 28 bytes at `0x021816A4` lie *inside* the 32-byte hole at
`0x021816A0`, so the two internal holes are **68 distinct bytes**, not 96 — 36 at
`0x0218161C` plus 32 at `0x021816A0` (which contains the 28). With the 23 trailing bytes
that is ~91 bytes of ov11, and any further space must be identified and checked
separately. ov10 shares ov11's load base, so its free space is not automatically
available while ov11 is resident. Also note this fix is **untested**: no capture yet
shows the AI leaving the stage with `0x021778B0` instrumented (§3.17).

### 3.16 The freeze is a *different bug*, and not the wall bit

§3.14 explains the walk-off. It does **not** explain the freeze, and treating them
as one bug was wrong. Measured over 12,939 consecutive frames, one dropped frame,
no input.

**The wall-bit theory is refuted.** Letting the AI freeze, then walking the player
back from 834 px through the wall line, the wall bit **never returns** — bit `0x8`
on 0 of 711 frames, bit `0x4` on 0 of 711 — yet `AI+0x39` cycles all seven ids and
`hp_p1` drops 9216 → 6144. Identical wall state, opposite behaviour. And
`AI+0xE4 = 0xFFFFFFFF` on every frame of both passes: the mask ov11 folds wall bits
into is all ones and carries no wall information, agreeing with the `+0xE4` census
in §3.12.

**The AI is the last casualty, not the first.** `+0x180`/`+0x184` die at fc 33187,
the wall breaks at 33341, `M+0x78` locks at 33363, the CPU state code locks at
33372, and *only then* does `AI+0x39` latch at 33509 — 322 frames after everything
else had already stopped.

**The AI is wedged, not deliberating.** `+0x184` counts down to 0 at fc 33186 and
sits at 0 for 12,518 frames without incrementing, while the engine runs normally —
`obj+0xD2` cycles all 256 values in both fighters, last change on the final frame.

**The gate is the player's fighter state code.** Recovery takes ten frames: fc
33553 the player's state code *leaves* `0` — the first thing to move after 12,000
dead frames — then fc 33557 the whole `BattleAIMove` re-arms (flag `0 → 0x60`,
counter restarts, `+0x17C` halves back), then fc 33563 `AI+0x39` is live. **The
player was still outside the arena when the AI came back**; it got inside 230
frames later. So the gate is whether the *player's* state code sits at `0`.

Caveat not papered over: three candidates move within 7 frames of the injection
(P1 state, P1 movement, CPU state). Only P1 state leads, and a clean attribution
needs an intervention that changes P1 state *without moving it* — not yet run.

**A correction to my own discriminator.** This section previously named
`r5+0x18B` as what would separate the two hypotheses. It cannot: a capstone sweep of
all 61,440 bytes of ov11 finds `#0x18b` in **no operand**, and the literal
`0x02181864` is loaded by **no instruction** in ov11, arm9, or any of the 14
overlays. The blob is class-registration metadata — `BattleAI_Deck.cpp` → char
array → pointer array → nine code pointers → `"BattleAIMove"` →
`"BattleAIMove_Create"` — not a dispatch table, and its entries are not even uniform
(`[0]` is a bare `bx lr`; `[4][5][6]` are the same function). `+0x18B` does not
latch anyway: 3 transitions in 12,939 frames, last change 187 frames *before* the
break.

**Three candidate extents, none reconciled.** All centred at 512:

| extent | left | right | source |
|---|---|---|---|
| outer collision box | 64.0 | 960.0 | `0x021B9AA0`, §3.15 |
| measured floor | 184.05–187.77 | 837.47–838.79 | 4 ground→descent events |
| measured walk limit | 260.000 | 763.996 | `side-b-range-2026-09-23` |

They nest, which is suggestive, but **which belongs in the AI's bounds is not
established.** `0x2FBFF` and `0x2FC00` occur **zero times in 4 MiB of RAM**, so
260/764 is *computed at runtime, not stored*; finding that computation is the
critical path (`jus-i7h9`). Seeding 64/960 would model the AI 196 px wider on each
side than the region the engine clamps it to.

### 3.17 The seed experiment: the unit is settled, the fix is *not* this field, and the reach statistic was framed wrong

A live RAM-poke experiment (`ai_patch_ram.py`, not ROM — write `px * 256` into
`+0x150`/`+0x158`) ran three seeded trials against two controls.

**The unit is 8.8, multiplier 1.0.** At `0x021778B0`, over 255 hits with
`r0 = 0x0220C0A8` (`P2EL`, the CPU's **own** fighter element), `r2 == [r0+0xC]
== p2x` bit-identically in **255/255**. `p2x` is 8.8 (`47853/256 = 186.92578125`
px) and `r2` is that same word, so the factor is 1. A 16.16 reading needs
`r2 = p2x << 4`; the smallest hit had `p2x = 182193`, so `<<4 = 2915088`, and
`r2` held **182193**. Ratio 1, not 16. So the fields take **8.8 directly**, and
the AI compares its *own* fighter's x, not the player's. The wall word it tests
is `[r8+0x10]+0x78 = 0x0220F50C` (`r8 = 0x02206878`).

**`r5` is not stable.** Two `BattleAIMove` objects alternate as the active one,
`0x02260AC0` and `0x0225F020`. A hard-coded seed address silently misses about
half the time; this voided one trial, and the real patch must find the live
object or patch both.

**Neither symptom moved.** Seeding `[184, 838]` left the walk-off trajectory
byte-identical, and the freeze still latched at the same `p1x = 834.195` px with
the same `AI+0x39 = 1`. `64/960` would be *more* inert, not less: the CPU's x
over every hit is `694.934..763.996` px, so any bracket containing that range
makes the `cmp`/`bge` take its branch and leaves `0x021778BC` dead. In the one
run where the right-wall block *did* execute (93 counted entries under a
`[900, 900]` probe), the engine's bit-8 flag was clear every time and the CPU
froze anyway.

**The reach statistic from that run was framed wrong.** It reported
"`0x021778B0` reached 58×/3000 frames = 0.97% of entries, so a 58-in-3000
condition cannot hold a 3000-frame freeze". The conclusion survives; the
arithmetic misdescribes the event. Re-derived from the run's own raw log, those
58 hits are a **contiguous burst of 58 consecutive frames**, once per run:
`265–322`, `645–702`, `3770–3792`, `6885–6942`, `7171–7228`. The enclosing
function `0x02177444` is entered **2×/frame continuously**; the bounds site runs
in one window and then never again. The stronger, simpler statement is: **the
bounds block is not executing at all during the freeze.** It is a
movement/approach path, and in the walk-off fixture it never executes either
(0 hits, and `AI+0x39`/`+0x3A` never change once — that fixture contains no AI
decision loop).

**The hole this leaves.** No fixture so far executes the bounds block *while the
AI is walking off*. §3.14's root cause is therefore **untested, not refuted**:
the fields are genuinely zero and genuinely read, but nothing yet connects them
to the walk-off. The next test must be a capture in which the AI is actively
playing and leaves the stage, with `0x021778B0` instrumented.

The driver's counter reported 93 `0x021778BC` entries but only 60 were logged;
treat 93 as unverified.

### 3.18 The freeze fixture is deterministic — and the caveat above was wrong

§3.17 initially recorded that this fixture was not reproducible run-to-run. A
five-run control says otherwise: **5/5 runs latch at exactly fc 33509, spread 0
frames.** Each from a fresh `state load`, bridge-only, writing nothing. All five
agree on the entire cascade — wall break fc 33341, `st2` last transition fc
33372, final `p1x` 213554 (834.195 px), CPU x 191590 (748.398 px),
`(a39, a3a) = (1, 2)` — and the five raw logs agree with the seed crew's
bridge-only pre-check.

So the divergent run that prompted the caveat was **not** fixture nondeterminism.
It was the only run in that session that poked memory, and unperturbed runs
cannot be made to diverge. The operational rule: a bridge-only, write-free run is
deterministic and a single-run A/B on it *is* interpretable; a run that writes
memory, and possibly one that attaches GDB, may not be, so seeded trials and
GDB-derived trajectories need a bridge-only control beside them.

**The latch is a hold, not a first appearance.** `AI+0x39` is not quiet before
the freeze — it is transiently `1` on roughly 102–112 of the ~950 pre-latch
frames and cycles `0/2/3/4/5/8` as the AI plays. The fc 33509 event is a
transition to a *held* state. Any detector keyed on `a39 == 1` without a hold
requirement fires early and often, which is why the census tests "1 from here
on", and why isolated `a39 = 1` frames read earlier in this file are not onset
evidence.

**And `a39` is misnamed throughout this file.** `+0x39` is a dispatch *phase*
enum; `+0x3A` carries the chosen behaviour id. The dispatcher writes a constant
`2` to `+0x39` and the caller's id to `+0x3A` (`0x0217AB90` / `0x0217AB94` /
`0x0217ABA4`), and the common exit increments `+0x39` (`0x0217B060`). So the
freeze holds **phase 1 with last behaviour id 2**, and every "AI+0x39 action" in
earlier sections means the phase, not the action. See
[`ai-behaviour-taxonomy.md`](ai-behaviour-taxonomy.md) §0.1.

**One open cross-crew discrepancy, localized.** The P2 wall word `0x0220F50C`
locks at `0x00000022` in all five runs here and oscillates
`0x04000022 ↔ 0x00000022`; the earlier GDB run recorded a lock at
`0x08000022`. Two independent bridge implementations agree with each other — the
seed crew's bridge pre-check also shows `0x4000022` — so the outlier is the GDB
read path, whether from a different frame phase or from the attach itself. It does
not affect the latch or any onset frame. Flagged, not resolved.

### 3.19 The clamp search is closed to four encodings

`jus-i7h9` remains open, but the space is now bounded by four independent
negatives, each self-tested:

| encoding | result |
|---|---|
| stored in RAM as a word | negative (this section) |
| ARM modified immediate | negative for `0x10400`/`0x2FBFF`/`0x2FC00`; `0x2FBFF` is not encodable at all |
| Thumb-2 `MOVW` | impossible — `0x10400`/`0x2FC00`/`0x20000` exceed the 16-bit `imm16` |
| literal pool + `LDR` | zero 4-byte-aligned hits for all three in all 15 regions |

A reachability pass reduced the 574 `0x20000` hits to 23 coherent `AL` survivors,
all `0x20000` — and `0x20000` is far too common to be the centre (`ov2` alone has
ten; `arm9 0x0207D160` is `bic r1, r1, #0x20000`). The 9 pooled `0x00020000`
words have **zero** `LDR [pc,#k]` references.

So the clamp is definitely **arithmetic** — an `add`/`sub`/`rsb` against a
register value, or a half-width read from the stride-`0x18` table at
`0x021B98D8..0x021B9ACF`. Neither was searched, and the table path is the shape
static analysis is worst placed to settle. The ov7 `(512.0, 288.0)` lead proves a
centre-plus-half-extent idiom exists, but with half-extent 288, not 252.

### 3.20 The freeze's hold condition is the player's state code at 0

`jus-ixd9`. A bridge-only probe (`<TMP>/crew-zmdb-freezehold/`) ran the
fixture unperturbed for 3414 frames and reproduced the latch at exactly fc 33509.
Every claim below was re-derived from the raw per-frame log by the orchestrator,
not taken from the crew's summary.

| fc | event | value |
|---|---|---|
| 33257 | `p2x` stops | 191590 |
| 33342 | P2 wall word `w2` locks | `0x00000022` |
| 33363 | P1 wall word `w1` locks | `0x08000022` |
| 33372 | `st2` (CPU state code) locks | 9 → 0 |
| 33381 | `p1x` stops | 213554 |
| **33407** | **`st1` (player state code) locks — the gate** | **8 → 0** |
| 33415 | live `BattleAIMove` `0x0225F020` counter `+0x184` exhausts | 1 → 0 |
| 33416 | same object's armed flag `+0x180` drops | `0x60` → `0x00` |
| 33417–33508 | 92 frames in which no watched field changes | — |
| **33509** | **`AI+0x39` latches; `AI+0x3A` follows** | **0 → 1, 0 → 2** |

`st1` is the last engine-side quantity to stop, and it leads the AI-side wedge by 8
frames (counter) and 9 (flag) and the latch by 102. The AI-side wedge is a
**disarmed** `BattleAIMove`: flag 0, counter 0, and the re-arm signature never
fires again (`+0x180`: 0→`0x60`, `+0x184`: 0→239, `+0x18B`: 0→1). After the latch
the watch set is constant for the remaining 2485 frames.

Two corrections to the crew's report, both found by re-deriving from the raw log:

- **The re-arm signature was misattributed to the live object.** `fc 32753` is the
  **dormant** object `0x02260AC0` arming (it dies at 33187); the live `0x0225F020`
  has exactly **one** arm event, at **fc 32962**. The signature itself is confirmed
  on both objects.
- **The silent span is 33417–33508 (92 frames), not 33416–33508 (93).** The
  `+0x180` disarm *is* the change on frame 33416.

**The tracker item's prime suspect is refuted by measurement.** `AI+0xD4` holds
`0x10000013` from fc 32880 through the whole freeze — bit `0x4000000` is clear on
every frame. The in-range geometry flag does not latch. This does not touch §3.14's
separate walk-off root cause; it removes the geometry flag as the *freeze's* hold
condition.

**Two caveats, stated because they bound what this buys.** (1) The gate causality
— that `st1 == 0` is *why* the re-arm never fires — is **inferred** from ordering
plus the earlier recovery experiment, not from a clean intervention; §3.16's caveat
still stands. (2) The probe did **not** watch `AI+0x48`, so the taxonomy's
give-up path was untested by this run. That capture has since run; it **refutes**
the give-up. See §3.21.

Bounds `+0x150`/`+0x158` remain 0 on every frame of every run — the freeze does not
populate them (§3.14).

### 3.21 The empty-mask give-up is dead code — and the behaviour pick is six wide

`jus-mask-capture-cbxb`. The measurement §3.20 named as missing has now run: the
same fixture, bridge-only, 3420 contiguous frames (fc 32585–36004), watching
`AI+0x48` and every input to it. The latch reproduced at exactly fc 33509.

**Result: `AI+0x48` = `0x7E` (126) on every frame. Min = max = 126. Never 0.** So
the empty-mask give-up at `0x0217AF7C` cannot fire — its guard is
`mask & 0x7E == 0`. The freeze is **not** a data-side availability collapse; it
lives on the dispatch side (the disarmed `BattleAIMove`, §3.20). `AI+0x105`, the
marker the give-up sets to 1, reads 2 from fc 33508 and never 1 — independent
corroboration.

**The negative is arithmetic, not coincidence.** The mask is built by OR'ing three
static words read from `[AI+0x24]` at `+0x84/+0x90/+0x9C`, then clamped:

```
0217AE20  bl   0x217b0a8      ; r0 = [[AI+0x24] + 0x84 + band*4]
0217AE2C  orr  r0, r2, r0
0217AE30  str  r0, [r4, #0x48]
...
0217AF08  ands r1, r0, #0x7e  ; <-- keeps bits 1-6 only
0217AF0C  str  r1, [r4, #0x48]
```

Live values: `0xC4000001 | 0x023A01FF | 0x0000C100` = `0xC63AC1FF`; `& 0x7E` =
`0x7E`. The band byte `AI+0x10A` is `0x50` on every frame, selecting band index 0,
so those are the three words actually read. Static and measured agree exactly.

**The consequence for the judgement work is larger than the freeze result.**
`0x7E` keeps bits 1–6, so **the `+0x48` pick — the generic behaviour selection —
can only ever return ids 1–6.** The three source words carry bits up to 31 and
every one above bit 6 is discarded. `ai-behaviour-taxonomy.md` §1.3 read
`and #0x7E` as "kills bit 0"; that understates it and is corrected in place, as is
its §2 count of "23 selectable ids" — this pick has six choices.

Whether the clamp is **intended** (bits 7+ reserved for another consumer) or a
defect that starves the generic pick is **answered, and the answer refutes the
candidate.** A static follow-up (`jus-ai-mask-clamp-intent-umol`) found that bits
7–23 of the same words **do** have a live consumer: the routine at `0x0217C16C`,
registered in the dispatch table at `0x02181998` right beside the clamp's own
`0x02181980`, reads the same words through the same reader with **no `&0x7E`**,
expands bits 1–23, and issues a chosen id directly via `0x02174EBC`. So the clamp
is an intentional partition, not starvation, and it does **not** remove
punish/anti-air/spacing by construction. **Do not build a patch on the clamp**,
and do not pursue it as an explanation for the CPU's failure to punish.

Residues kept: readers 2 and 3 are called only by the clamp, so bits 7+ of the
`+0x90`/`+0x9C` word groups are discarded; and bands 1 and 2 are never selected in
this fixture, because the band byte is constant, leaving six of the nine words at
`[AI+0x24]+0x84..0xA4` unread.

---

### 3.22 The freeze is a **phase-1 park** — and it was answered from dumps already on disk

**No emulator ran for this section.** Two captures that were already written to disk were
joined on framecount: the committed `ai_actions` probe (`tail.jsonl`, fc 32755–33964, which
carries `AI+0x39/+0x3A/+0x105` and both fighters' state codes) and the freezehold dump
(`<TMP>/crew-zmdb-freezehold/hold1.jsonl`, fc 32565–35994, which carries both
`BattleAIMove` objects at `+0xC0..+0x18F`). Their overlap is the whole freeze window.

**The discriminator is `AI+0x39`, the dispatch phase — not the id, not the movement, not the
pick.** `AI+0x39` against the CPU's own fighter state code (`P2OBJ+0x18`) over 1208 frames:

| phase `+0x39` | frames | fighter state code | ids seen |
|---|---:|---|---|
| 0 | 374 | 0:314, 1:2, 6:28, 11:30 | id 0 for 371 |
| **1** | **539** | **0:497, 1:42 — no attacks at all** | id 2 for 456 |
| 2 | 6 | 0:5, 1:1 | — |
| 3 | 69 | 0:61, 1:1, 9:6, 11:1 | id 12 for 49 |
| **4** | 163 | 0:44, **9:119** | ids 1, 2, 5, 6 |
| **5** | 53 | **9:53** | ids 1, 2, 5 |
| 8 | 4 | 11:4 | id 12 |

Attack state 9 is produced almost entirely by phases 4 and 5 (172 of 178 frames). **Phase 1
produced zero attacks in 539 frames.**

**The same behaviour id lands in different phases, and that is the whole freeze.** A
controlled comparison inside one capture:

| | healthy id 2, fc 33304–33371 | frozen id 2, fc 33509–33964 |
|---|---|---|
| fighter state | **9 in 64 of 68** | **0 in 456 of 456** |
| `+0x39` | **5**, then 4 | **1, held for 456** |
| `+0x3A` | 2 | 2 |
| `+0x105` | 2 | 2 |
| `BattleAIMove` `+0x180` | `0x60` — armed, countdown running | `0x00` |
| `+0x184` | counting down 111 → 44 | 0 |
| `+0x150`/`+0x158` | 0 / 0 | 0 / 0 |

So the id, the `+0x105` marker, and the arena bounds are **identical** in both episodes. The
difference is the phase the behaviour was dispatched into.

**This refutes the movement-timeout explanation of the freeze, and it does so with a
mechanism, not an absence.** `0x02177BA4`–`0x02177BE4` is the expiry: while `+0x180` bit
`0x40` is set it decrements `+0x184`, and when the count goes negative it clears bits
`0x40`/`0x20`, zeroes `+0x18B`, and writes **`+0x105 = 1`** to request another decision. On
disk that path is **firing normally and often**: `+0x105` takes `{0, 1, 2, 8}` and equals 1 on
20 frames, including fc 33415–33416 — exactly when `BattleAIMove` `+0x180` drops to 0. There
is nothing to repair: the expiry already reaches the request. Both movement objects are
inert (`+0x180 = +0x184 = 0`) from **fc 33416** onward, 93 frames before the latch, and
neither is re-armed.

**What that leaves, and it is a sharper question than the one it replaces.** Phase 1 is
normally transient (the longest healthy phase-1 run is 40 frames, fc 32872–32911). The freeze
is phase 1 held 456+ frames with a real behaviour (id 2) already dispatched into it. So the
question is **what advances phase 1 to 4/5, and why it stops** — which points at the phase
list walk around `0x0217BA88`–`0x0217BACC` and the phase-1 handler `0x0217B0F0`, not at the
movement object. Note `0x0217B0F0` opens by indexing an AI slot with the **signed byte at
`+0x38`** (`ldrsb r2,[sl,#0x38]` then `mla r5,r2,#0x10C,r3`), so `+0x38` is not only the
pick's roll source — it is also a slot index on this path, and it read 255 on fc 33505–33507.

**Caveat.** `+0x105` is not in the freezehold watch set, so its freeze-window values come
from the `ai_actions` probe; the two dumps agree wherever they overlap but they are separate
runs, and the fixture is deterministic to the frame only when unperturbed.

---

### 3.23 The dispatch phase machine: a 16-entry handler table

Static, no emulator. `AI+0x39` is not a mode enum — it is a **step counter into a table of
handlers**, and the freeze is step 1 of that table. This refines §3.22, which called it a
"dispatch phase".

**The dispatcher.** `0x0217A608`–`0x0217A620`:

```
0217A614  ldrb r2, [r4, #0x39]        ; the step
0217A618  ldr  r1, [pc, #0x430]       ; -> 0x02181980  (the table)
0217A61C  ldr  r1, [r1, r2, lsl #2]   ; handler = table[step]
0217A620  blx  r1                     ; run the step
0217A624  ldrb r1, [r4, #0x40]        ; then a second jump table on +0x40
0217A628  cmp  r1, #0x11
0217A62C  addls pc, pc, r1, lsl #2    ; 18 post-step outcomes
```

**The table at `0x02181980`, 16 entries** (each a pointer into ov11; verified as words, and
`0x02181984` is the only reference to the phase-1 handler anywhere in ov11):

| step | handler | | step | handler |
|---:|---|---|---:|---|
| 0 | `0x0217ABBC` | | 8 | `0x0217C508` |
| **1** | **`0x0217B0F0`** | | 9 | `0x0217CAB4` |
| 2 | `0x0217B7F0` | | 10 | `0x0217CCF8` |
| 3 | `0x0217B8F8` | | 11 | `0x0217CDBC` |
| 4 | `0x0217BB58` | | 12 | `0x0217D0B0` |
| 5 | `0x0217BBAC` | | 13 | `0x0217D1E4` |
| 6 | `0x0217C16C` | | 14 | `0x0217D350` |
| 7 | `0x0217C2C0` | | 15 | `0x0217D558` |

The live steps `{0,1,2,3,4,5,8}` (§3.22) are exactly these handlers; e.g. the `+0x39` writers
at `0x0217C420/4A0/4C8/4E0/4FC` sit inside step 7 (`0x0217C2C0`–`0x0217C508`), which is why
step 8 is reachable.

**Step 0 is the pick, and its exit advances the step.** `0x0217B054` (inside step 0):

```
0217B054  ldrb r1, [r4, #0x39]
0217B05C  add  r1, r1, #1
0217B060  strb r1, [r4, #0x39]        ; step += 1
0217B064  strb r0, [r4, #0x3e]        ; sub-step := 0
```

So the wheel/reaction pick at step 0 commits by moving to step 1 — which is where the freeze
sits. That is why "the pick chose id 2" and "the CPU is frozen" are both true: the pick
succeeded, and the *first execution step* is the thing that never completes.

**There is a second counter, `+0x3E`, a sub-step within a step.** The predicate
`0x0217C01C` switches on it (`cmp r1,#5; addls pc,pc,r1,lsl #2`, `r1 = +0x3E`), so a single
step can be a multi-frame script. Step 0 zeroes `+0x3E` on every commit.

**Where step 1 can go.** Every phase-changing and phase-preserving exit of `0x0217B0F0`:

| site | effect | gate |
|---|---|---|
| `0x0217B138` | step := 0 | `+0x3A == 8` and `[[opp]+0x20]+0x18 != 3` |
| `0x0217B268` | **step += 1** | a candidate was found (`r4 >= 0`) |
| `0x0217B310` | **step := 3** | the class loop found ids 9/10 |
| `0x0217B3B0` | **step += 1**, or **step := 7** if `+0x3A == 0` | the second mask test |
| `0x0217B45C` | **step := 0** | the close-range restart, after `+0x3E > 2` |
| `0x0217B4B8` | **step := 0** | predicate `0x02083ACC` false |
| `0x0217B32C` | none | `r1 == 1` |
| `0x0217B368` | **none** | predicate `0x0217C01C` false |
| `0x0217B41C` | **none** | `[[opp]+0x20]+0x18 == 0x17` |
| `0x0217B3E4` | none, but `+0x105 := 1` and the abort routine runs | the give-up |

**The freeze's route, by elimination.** The handler reaches the "no candidate" path
(`0x0217B324`, `r1 = 0`), then the `+0x180` bit-2 test at `0x0217B348`:

```
0217B344  ldr r0, [r0, #0x180]
0217B348  tst r0, #4
0217B34C  movne r0, #1
0217B350  moveq r0, #0
0217B354  cmp r0, #0
0217B358  beq 0x217b410            ; bit 2 clear -> the close-range restart
```

`+0x180` bit 2 is "a movement request is in flight"; it is cleared by `bic #4` at
`0x0217B3C8`/`0x0217B3F0`. **Both movement objects read `+0x180 = 0` throughout the freeze**
(measured, §3.22), so the handler takes `0x0217B410` — the close-range restart.

Every exit from `0x0217B410` either restarts (step := 0), increments `+0x3E`, or issues a
movement request — except **`0x0217B41C`**, which returns without touching anything:

```
0217B410  ldr r0, [r5, #0x20]
0217B414  ldrsb r0, [r0, #0x18]
0217B418  cmp r0, #0x17
0217B41C  beq 0x217b4e8            ; opponent in state 23 -> do nothing, keep step 1
```

**State `0x17` is 23, and 23 is a confirmed live state — an airborne knockdown**
(`docs/confirmed-facts/physics.md`: `obj+0x18 = 23` while airborne, in the
`push-2026-09-24/wall` capture; the sequence is launch 6 → airborne 23 → landed 24 → up 25).
That is a close fit to the owner's account of this fixture: the CPU hits the opponent until
the wall breaks, leaves him in the gap, and stops. If the opponent is parked in the
knockdown state inside the broken-wall gap, this exit fires on every frame forever.

**But there is a second silent exit and it is not yet excluded.** `0x0217B368` also returns
without changing anything, and it is reached when the movement accessor `0x0217B4F0`
(`r0 = [AI+0x24] ? [[AI+0x24]+8] : 0`) returns null, because `0x0217B338`–`0x0217B340`
substitutes `r0 = 1` for a missing object and so routes *past* `0x0217B410` into the
predicate. `0x0217B4F0` is the same accessor whose `+0x180` the freezehold dump watched at
`0x02260AC0`/`0x0225F020`, but **that the dump's two objects are `[[AI+0x24]+8]` is assumed,
not proved** — if they are not, the bit-2 reading above is about the wrong structure and this
route is live.

**What this settles and what it does not.**

- *Settled:* the phase machine's identity and layout; that `+0x39` is a step counter whose
  handlers are the behaviour's steps; that step 0 is the pick and advances to step 1; that the
  freeze is step 1 held; that the give-up (`0x0217B3E4`, which sets `+0x105 = 1`) is **not**
  firing, because the freeze reads `+0x105 = 2` on all 456 frames; and that `+0x38` is
  initialised from character data (`0x02174408`/`0x02174418` read `ldrsb [char+0x500+0xE0]`
  and `[+0xE1]` into `+0x38` and `+0x39`), not derived from the fight.
- *Not settled:* which of `0x0217B41C` and `0x0217B368` holds the step. Both are silent.
- *Discriminating test, one capture, no GDB:* watch `[[AI+0x20]+0x18]` (the opponent state as
  this handler reads it), `[AI+0x24]` and `[[AI+0x24]+8]` (the accessor's inputs, which decide
  whether `0x0217B410` is reached at all), and `+0x3E` (which stays 0 on `0x0217B41C` and
  climbs on the `0x0217B410` route). If the opponent reads 23, this is a knockdown-state
  gate; if the accessor reads null, it is a missing-movement-object gate. **`+0x3E` alone
  separates the two**, and it belongs in the standing capture.

---

### 3.24 The freeze: the phase-1 park, and the exit that turned out to be blocked

> **The diagnosis below is corrected by §3.25, which ran the A/B.** Everything §3.24 measures is
> right; what it concludes about the finalizer is wrong. The finalizer is **not** the escape
> hatch: its write path is never taken in any arm — including healthy stock play — and the code
> arm proves its downstream gates block it on their own. The guard table is a **lever** on the
> AI's decision path, not the freeze's own escape.

**Measured**, one capture, `<TMP>/jus-phase-capture/` — 3420 rows, 0 gaps, 0 dropped,
latch fc 33509 confirmed (23 watches / 510 bytes; the same run also carries the reaction band).
Values over the 2506-frame phase-1 tail:

| field | value in the tail |
|---|---|
| `AI+0x39` | 1 on every frame |
| `AI+0x3E` | climbs 1/frame, **saturates at 255** from fc 33764 (2251 of 2506) |
| `AI+0x40` | **0 on every frame** |
| `AI+0x105` | 2 on every frame |
| `AI+0x20` | 0x0224EF00, constant |
| `[[AI+0x20]+0x18]` | 0 (2550 frames) / 1 (42) |
| `AI+0x24` | 0x023A4200, constant |
| `[[AI+0x24]+8]` | 0x022606A0, constant |
| `[[AI+0x24]+8]+0x180` | 0x001E00A8, constant (bit 2 clear) |
| `AI+0x2C` | 0x0239ED10, constant |

**The chain, each step verified.**

1. **`+0x3E` climbing refutes the knockdown exit.** `0x0217B41C` returns at `0x0217B4E8`
   *before* the increment at `0x0217B480`, so a frozen `+0x3E` would have been the signature
   of that exit. It climbs instead: step 1 takes `0x0217B410` → `0x0217B474`, increments
   `+0x3E`, and leaves `+0x39` alone.
2. **`+0x180` bit 2 is clear** (`0x001E00A8`), so the `0x0217B348` test routes to
   `0x0217B410` — now measured on the object the handler actually tests (see the corrections
   below).
3. **`+0x40 = 0` → the dispatcher's second table takes index 0 → the finalizer `0x0217A968`**
   (verified: index 0 of the `+0x40` table is `b 0x217A968`).
4. `0x0217A968 mov r0,r4` / `0x0217A96C bl 0x0217BFE0`. **That guard scans a byte table at
   `0x021813CC` = `{9, 10, 11, 12, 26, -1}`** and returns 1 only if `[[AI+0x20]+0x18]` — the
   CPU's **own** fighter state code — appears in it.
5. **The CPU's own state is 0 (2550 frames) or 1 (42). Neither is in the table.** The guard
   returns 0, `0x0217A974 beq 0x0217AA48` fires, and the finalizer returns having written
   nothing — so `+0x39` stays 1 while `+0x3E` climbs to saturation.

**So the freeze is a deadlock, not a missing branch.** The only escape from step 1 that does
not require a target candidate is the finalizer, and the finalizer fires only when the CPU is
already in `{9, 10, 11, 12, 26}` — the attack and hitstun states that step 1 is what would
produce. Idle ⇒ no advance; no advance ⇒ idle. The owner's account is the trigger, not the
mechanism: the fight reaches a geometry where no candidate is found, the CPU's state returns
to 0, and nothing can restart it.

**Two candidate patches, both tiny, neither tested.**

- **Data, 2 bytes, at `0x021813D1`/`0x021813D2`.** The table is `{9,10,11,12,26,0xFF}` at
  `0x021813CC` and `0x021813D2` is already `0x00`. Setting `0x021813D1 = 0x00` (accept state
  0) and `0x021813D2 = 0xFF` (the new terminator) adds "idle" to the accepted set and removes
  nothing. **Blast radius: `0x0217BFE0` has 17 callers** — `0x02175BD8`, `0x02175DA0`,
  `0x0217A96C`, `0x0217BB60`, `0x0217BEF8`, `0x0217CABC`, `0x0217CD00`, `0x0217CEB0`,
  `0x0217D0CC`, `0x0217D238`, `0x0217D39C`, `0x0217D5A8`, `0x0217EE94`, `0x0217F018`,
  `0x0217F0EC`, `0x0217F13C`, `0x02180540` — so it changes every state gate that uses it.
- **Code, 4 bytes, at `0x0217A974`.** Replace `beq 0x0217AA48` with a nop so the finalizer
  proceeds to its `[obj+0x94]` and `[P2OBJ+0xCC]` gates instead of returning. Blast radius:
  this finalizer only. ov11 has ~91 bytes of code space, so it fits.

Neither is a fix until an A/B shows purposeful action resuming. A patch that advances `+0x39`
from 1 to 9 without producing movement is exactly the failure mode Astra named.

**Corrections to §3.22 and §3.23 — both mine.**

- §3.22 measured `+0x180` on `objA`/`objB` (0x02260AC0, 0x0225F020). **Those are not the
  object the step-1 handler tests.** The accessor `0x0217B4F0` returns `[[AI+0x24]+8]` =
  **0x022606A0**, a third object; in the capture `[[AI+0x24]+8]+0x180` = `0x001E00A8` on all
  3420 frames and agreed with `objA`/`objB` on **0 of 3420** frames. §3.23 flagged this as an
  unproven assumption; it is now proved false. §3.22's conclusion survives — the bit is clear
  on the correct object too — but its movement-object claim does not.
- `[[AI+0x20]+0x18]` is the CPU's **own** state, not the opponent's: `[AI+0x20]` = 0x0224EF00
  = P2OBJ, and the watch tracked `st2` exactly (0 and 1).
- I briefed the static pass with "the freeze holds `AI+0x40 = 0x10`". **That was my error in
  the brief, not a doc claim.** `0x10` is what the *sentinel* writes
  (`ai-behaviour-taxonomy.md` §4.4); the freeze measures `+0x40 = 0`. The static pass's table
  and writer list are correct and verified; its "the value must be re-seeded" tension was the
  symptom of my wrong premise, and `+0x40 = 0` resolves it into index 0.

---

### 3.25 The A/B: the patch works, the mechanism does not — and the refuter was right

**Design.** One emulator session, stock ROM, the savestate loaded fresh before each arm, 3400
frames, the same 23-watch set. Arms: `control` (no poke), `data` (the two-byte guard-table
patch), `code` (the four-byte NOP at `0x0217A974`). Both patches are RAM pokes at the ov11
virtual address, so the stock ROM is also the treatment ROM, and reloading the savestate reverts
each arm. Both pre-images were verified stock before every arm, and both pokes verified present
after every run.

**The control is exact.** Aligned on framecount, the control is **bit-identical to the durable
stock capture** (`jus_files/captures/ai-phase-machine-2026-09-28/cap1.jsonl`) on all 23 watched
fields across 3400 shared frames — **0 differences**. The fixture is frame-exact reproducible, so
a difference between arms is attributable to the poke.

| arm | `+0x39` post-latch | `+0x3E` | own state post | attack frames | CPU x changes | opponent state |
|---|---|---|---|---|---|---|
| control | `{1: 2486}` | saturates 255 | `{0: 2486}` | 0 | 0 | `{0: 2486}` |
| **data** | `{0:582, 1:345, 2:17, 3:79, 4:1334, 5:87, 6:38, 7:9, 8:35}` | max 103 | `{0:1545, 1:117, 3:30, 9:402, 10:129, 11:303}` | **834** | **478** | `{0:1872, 8:577, 23:34, 24:1, 25:42}` |
| code | `{1: 2506}` | saturates 255 | `{0: 2506}` | 0 | 0 | `{0: 2506}` |

**The data patch eliminates the freeze in this fixture.** The phase machine cycles, the CPU
enters attack states 9/10/11 for 834 frames, its x position changes 478 times, and — the
independent evidence — the **opponent** enters `8, 23, 24, 25`, the hit-and-launch sequence. The
CPU's own state 9 coincides with the opponent's state 8.

**The code patch is inert.** `+0x39` stays 1 and the arm is bit-identical to the control.

**But the diagnosis in §3.24 is wrong, and the A/B is what shows it.** A refuter pass over the
raw logs found, and I verified independently: **`AI+0x39` never reaches 9 or 0xA in any arm —
including the healthy stock control** (`{0,1,2,3,4,5,8}`). Those are the only two values the
finalizer writes (`0x0217AA10`, `0x0217AA38`). The finalizer is entered on 3406–3412 of 3420
frames in every arm, and its write path is **never taken**. Therefore:

- **The finalizer is not the escape hatch.** Its phase-advance write is dead on this fixture
  even in normal play. §3.24's "the guard failing is why the loop never exits" does not hold.
- **The finalizer is doubly blocked**, and the code arm proves the *downstream* gates suffice
  alone: with the guard bypassed by the NOP, it still writes nothing.
- **The data patch works through the guard's other 16 callers, not through the finalizer.** The
  first data-vs-control divergence is at **fc 32760**, 749 frames *before* the latch, and the
  columns that move first are `ai_act`, `ai_d4`, `ai_3e`.

So the honest statement is narrower than §3.24: the lock is in the AI's normal decision path, the
guard table at `0x021813CC` is a **lever** on that path rather than the freeze's own escape, and
the data patch is a working but **blunt** fix.

**Read the row, not the word.** The driver printed "FIXED (action followed the advance)" for the
data arm. That is true of the *outcome* and misleading as a *mechanism*: its criterion (`+0x39`
left 1 after fc 33509, the state entered `{9,10,11,12}`, x moved) is satisfied trivially, because
in the data arm there is no freeze at 33509 to escape — the phase left 1 at fc 32760 and revisited
it dozens of times.

**One refuter finding I refute.** The refuter called the 367-frame pin at exactly 764.0 px
(fc 32889–33255) a regression, "the CPU stuck while the opponent moves freely". It is not.
During the pin the CPU's own state is `{0:235, 11:73, 12:59}` — 132 frames in attack states — and
the opponent is in `{0:174, 8:116, 23:34, 24:1, 25:42}`, being hit and launched. It is corner
pressure, not a stuck state. 764.0 px is where the CPU stops advancing; it keeps attacking there.

**A §3.14 data point.** In the data arm the opponent reaches x = **81.7** and x = **956.0**
without ringing out, and the CPU reaches 764.0. That **refutes the `184..838` and `260..764`
candidate extents** and supports `[64, 960)` as the real bound.

**What is still unknown, and it is the right next question.** Which of the guard's 16
non-finalizer callers is the actual lock. The lever is identified; the mechanism is not. An arm
that patches the finalizer's downstream gates (`0x021733B4` / `0x0217B7CC` / `[obj+0x94]` /
`[P2OBJ+0xCC]`) would settle both that and whether the finalizer can ever advance the phase on
shipped data.

**The fix is available two ways.** `scripts/emu/ai_patch_ram.py --set idle_in_action_set` applies
it to live RAM, refusing unless the 4-byte pre-image at `0x021813D0` is stock; `--reload` reverts
by reloading the savestate. The ROM equivalent is the two bytes at `0x001E6771` and `0x001E6772`.
**The ROM patch is masked by any savestate load** — a savestate carries the overlay in RAM, which
is why the A/B verified the pre-image was stock after every load — so the freeze *fixture* needs
the RAM tier, while a fresh boot picks the patch up from the ROM.

---

### 3.26 What the patch actually modifies, and why the tier is no longer called "freeze"

`gpt-6-sol` (codex, read-only) was consulted for a characterisation and a name. Its three
load-bearing call-site claims were re-checked against the bytes and hold, as do its physics
citations.

**The guard is an attack-family state test, not a "can act" test.** `0x0217BFE0` returns 1 iff the
fighter's own state code is in `{9, 10, 11, 12, 26}`: 9 and 10 are attacks, 11 a dream attack, 12
a SELECT ultimate (`docs/confirmed-facts/physics.md`). 26 is unanchored.

**All 17 call sites, and what each does with a 1 versus a 0.** This is the "what does it modify"
answer, and the reason the tier cannot honestly be named after the freeze:

| call site | in | return 1 | return 0 |
|---|---|---|---|
| `0x02175BD8` | fn `0x02175AD0` | passes `0` to an object helper, exits | passes `1`, calls `0x021760E4` |
| `0x02175DA0` | fn `0x02175AD0` | continues object updates | cleanup via `0x021760A4`, clears `AI+0xA8` bits `0x180` |
| `0x0217A96C` | dispatcher / finalizer | enters the finalizer's later gates | returns at `0x0217AA48` |
| `0x0217BB60` | step 4 | leaves the phase alone (`popne`) | resets the phase and sub-step |
| `0x0217BEF8` | step 5 | **keeps waiting** | **phase := 4**, sub-step := 0 (`moveq`) |
| `0x0217CABC` | step 9 | runs the decision logic | calls `0x0217AA58` and returns |
| `0x0217CD00` | step 10 | runs the decision logic | calls `0x0217AA58` and returns |
| `0x0217CEB0` | step 11 | **phase := 4**, sub-step := 0 (`movne`) | leaves the phase alone |
| `0x0217D0CC` | step 12 | updates the selected action record | returns before the update |
| `0x0217D238` | step 13 | may continue the action sequence | falls back via `0x0217D750` |
| `0x0217D39C` | step 14 | may continue the timed sequence | falls back via `0x0217D750` |
| `0x0217D5A8` | step 15 | may continue the timed sequence | falls back via `0x0217D750` |
| `0x0217EE94` | fn `0x0217EE38` | skips a nearby-entity interaction | may enter it, subject to another gate |
| `0x0217F018` | fn `0x0217EE38` | skips a target/assist decision | continues into it |
| `0x0217F0EC` | fn `0x0217EE38` | permits checks of a **selected other fighter's** slot | skips them |
| `0x0217F13C` | fn `0x0217EE38` | skips a later decision | may take it after further checks |
| `0x02180540` | fn `0x021803A4` | returns early | may set object flag `0x10` and advance `AI+0xA1` |

**The polarity is mixed, and that is the point.** Steps 4 and 5 reset on 0 and leave on 1; step 11
does the reverse — verified at `0x0217BF00` (`moveq r0,#4`) and `0x0217CEC0` (`movne r0,#4`). So
the patch is not "idle now escapes": it is a redistribution of which branch every gate takes. That
is exactly why it moves the fight 749 frames before the freeze, and why it is a working lever
rather than a freeze fix.

**Named for the edit, not the symptom.** The tier is now `idle_in_action_set` — it says what the
table change is (idle enters the attack-family set) and leaves room for all 17 callers. Two
alternatives were offered and set aside: `idle_ai_state_gates` says less about the value change,
and `idle_counts_as_attack` overstates what is known about state 26.

**No narrower lever is identified.** Step 1 — where the freeze parks — does not call the guard at
all, and the isolated finalizer change is inert. Codex's inference, which this experiment does not
settle: the pre-phase calls at `0x02175BD8` and `0x02175DA0` are the likeliest place for a
narrower sufficient change.

**What to watch in play, given the call sites.** Decisions taken while idle: premature phase
resets, repeated actions, attacks starting from neutral at odd times, interrupted action
sequences, and changed target / assist / nearby-object choices. `0x0217F0EC` tests a *selected
other fighter's* slot, so watch the second fighter too. The fixture proves that movement and hits
resume; it does not establish that those decisions stay sound over a full session.

---

### 3.27 The reaction band: the veto is clear, and ten sites can issue

`jus-ai-reaction-band-fwik` asked which of three explanations keeps ids 13/14 out: unreachable,
vetoed, or rare. One capture settles the veto question and undercuts the third's support.

**The capture.** `jus_files/captures/reaction-veto-2026-09-28/veto1.jsonl` — stock ROM, fixture
`pc-kakashi-npc-jotaro-fightcpu`, 3420 rows, fc 32605–36024, 0 gaps, 0 dropped, 23 watches /
102 bytes. It is the standing set with `objA`/`objB` dropped (416 of the 510 bytes) and two
watches added: `[AI+0x2C]+0x34` (the veto word) and `AI+0x48`.

**Measured.**
- `u32[[AI+0x2C]+0x34] == 0` on **all 3420 frames**. That word is what `0x0217AB28` tests, at bit
  `class & 0x1F`. So **no class is vetoed** — the punish band's class 4 is clear. Hypothesis (b)
  is **refuted**.
- `AI+0x48 == 0x7E` on all 3420 frames.
- `AI+0x3A` took `{0:586, 1:38, 2:2584, 4:5, 5:84, 6:54, 11:5, 12:64}` and **changed only 18
  times**.
- `AI+0x40` took `{0:3412, 2:2, 3:2, 4:2, 5:2}` — the sentinel's `0x10` **never appears**.

**Refuted by adversarial review** (`gpt-6-sol`, read-only; its three load-bearing claims were
re-checked against the bytes and hold):
- **"Rare" is not established.** 18 `+0x3A` changes are not 18 picks — the pick writes `+0x3A`
  at `0x0217ADD4` and can write the same value repeatedly. The capture cannot separate selection,
  branch timing, and resolver failure.
- **`+0x48` is derived, not a data cap.** Cleared at `0x0217AE04`, OR-ed from mask words, then
  clamped to `0x7E` at `0x0217AF08`. The mask words come from
  `0x0217B0A8(ctx,k) = u32[[[ctx]+0]+0x84+4k]` for k = 0..2 — that data is where the repertoire
  actually lives.
- **"There are four producers, not two" — the refuter's count; superseded by the byte scan below
  (there are ten).** A third, `0x0217C248–0x0217C2A4`, enumerates mask bits
  **1..23 without the `0x7E` clamp**, collects the set ones into a stack array, PRNG-picks among
  them, and issues via `0x02174EBC` — so ids 7–23 are reachable in *code*, limited only by the
  mask data. A fourth, `0x0217ACC4–0x0217AD40`, issues id 12 directly (`mov r1,#0xc`), which
  explains the one observed id outside both the table and the `0x7E` mask.

**Corrected against the bytes: ten call sites, not four.** A byte scan of the whole overlay for
`BL` to `0x02174EBC` (ov11 base `0x02172A60`, size 61440) finds ten, and the funnel's own `LR` at
`0x02174ED0` names which one fired, so this count is a directly measurable quantity rather than a
reading of the control flow:

| site (`LR`) | call | what it issues |
|---|---|---|
| `0x0217A7AC` | `0x0217A7A8` | PRNG pick from a pointer list; id = a stack byte |
| `0x0217AACC` | `0x0217AAC8` | setter; id arrives in `r2` |
| `0x0217ACA0` | `0x0217AC9C` | id 8 direct (`mov r1,#8`) |
| `0x0217AD44` | `0x0217AD40` | id 12 direct — the "pivot" gate (`mov r1,#0xc`) |
| `0x0217AE00` | `0x0217ADFC` | id = `AI+0x3A`, the reaction-table pick |
| `0x0217B054` | `0x0217B050` | mask-bit enumeration + PRNG pick |
| `0x0217BC4C` | `0x0217BC48` | signed-byte stack table pick |
| `0x0217C2A8` | `0x0217C2A4` | mask-bit enumeration + PRNG pick |
| `0x0217C624` | `0x0217C620` | PRNG pick from a pointer list; id 12 direct |
| `0x0217C894` | `0x0217C890` | ids 13/14 direct (`r7 = 0xd + 2*(0x02174F4C(r4) - 3)`) |

So "third" and "fourth" above name two of ten, and the two mask-bit enumerators (`0x0217B050`,
`0x0217C2A4`) are a pair, not a singleton. The `0x7E`-clamp reading still stands for the reaction
loop's `AI+0x48`, and the reachability conclusion is unchanged — but *which* of the ten is live
was never established, and that is what the census measures.

**Corrected: the remap is ids 13 and 14 only.** `0x02174ED4`: `cmp r5,#0xd` / `blt` / `sub
r0,r5,#0xd` / `cmp r0,#1` — only 13 and 14 pass, then `r5 += 2*(s8[[r6+4]+8] - 3)`. A second path
of the same shape is at `0x0217A984–0x0217A9B8`. `[r6+4]` is written at `0x021745D0` from the
return of `0x02076CE0`, so **"opponent state" stays an inference** (Astra's caution stands). The
earlier "ids 13–18 are the opponent-state-remapped family" is **wrong**.

**The AIPM class byte is not the veto class.** In `jus_files/chrbin/chr/ai/bb_b_01.bin` and
`jus_files/chrbin/chr/ai/op_b_03.bin` the sub-record `+0x18` byte partitions at id 13 (`{2,3}`
below, `{4,5}` at 13 and above) — real structure, and the parse is validated (the record chain
tiles both payloads exactly; every `+0x04` self-index matches its slot). But the reaction loop
passes the *table's* byte 1 to `0x0217AB28` and never reads an AIPM sub-record; a consumer at
`0x0217B77C` compares `+0x18` with 4. The correlation does not identify the two.

**What would settle it**, ranked:
1. Hook the single funnel every producer drains — the `bl 0x21751CC` reached from `0x02174EBC` —
   logging at `0x02174F00` (r5 = post-remap id, r0 = ctx) and `0x02174F04` (r0 = resolver
   return). This separates never-selected from selected-but-remapped from selected-but-refused.
   **In flight.** The breakpoint pair is `0x02174ED0` (stash `LR`, the incoming id, ctx and slot)
   and `0x02174F04` (one row per issue), plus the per-frame anchor at arm9 `0x02082E10`. `LR` is
   the discriminator: it names which of the ten sites above issued the call. Two arms, same ROM
   and fixture — stock, then stock plus the `idle_in_action_set` RAM tier, so the second arm is
   its own positive control.
2. Log the **full** `u32[[AI+0x2C]+0x38]` at picker executions, not per frame — the 1-byte watch
   cannot tell roll 85 from 213.
3. Log `[ctx+4]` and its signed `+8` when incoming 13 or 14 reaches `0x02174EE4`.

**Candidate changes, and their status.** A data-first review (`space-bunny-free`, re-checked by
me) proposed four. Two are grounded:
- **Raise the shared weight** at `[AI+0x2C]+8+26` (fixture `0x0239ED32`, value `0x0F`): entries
  11 and 12 both carry byte 2 = 26, so one byte widens both. Side effect: the cumulative total
  then exceeds 256, pushing the sentinel's band off the roll, so the "no behaviour" outcome
  disappears. It is a RAM poke with unknown savestate survival, and it presumes the table is the
  live producer.
- **Retarget the table's id bytes** `0x02181459` / `0x0218145C`: the only ROM-data lever on
  *which* behaviour the band emits. **Not defensible yet** — no id is named, and ids 19–23 have
  no record in either file.

The other two are withdrawn. The mask-word candidate named `0x023A4284`, but that is
`[AI+0x24]+0x84`; the reader dereferences first, so the real address is `[[AI+0x24]]+0x84`, and
the quoted value `0xC4000001` was never in any capture. Widening the `0x7E` clamp duplicates the
third producer rather than adding repertoire.

---

### 3.28 The funnel census: the freeze starves the reaction path, and that is why the punish band never fires

The measurement 3.27 asked for. Two arms, stock ROM, fixture `pc-kakashi-npc-jotaro-fightcpu`,
3842 frames each, one GDB attach per arm. `LR` is stashed at `0x02174ED0` — before
`bl 0x2175144` clobbers it — so it names which of the ten call sites issued; the post-remap id
and the resolver's return are read at `0x02174F04`. Arm B is stock plus the `idle_in_action_set`
RAM tier, so it is its own positive control.

| producer (`LR`) | arm A stock | arm B patched |
|---|---|---|
| `reaction_table_AI3A` `0x0217AE00` | 5 | 27 |
| `mask_enum_B` `0x0217C2A8` | **0** | 20 |
| `direct_id12_pivot` `0x0217AD44` | 4 | 12 |
| `mask_enum_A` `0x0217B054` | 5 | 7 |
| `stack_s8_table` `0x0217BC4C` | 3 | 5 |
| `direct_id12_list` `0x0217C624` | 2 | 4 |
| `P1_list_rand_byte` `0x0217A7AC` | 2 | 3 |
| `direct_id8` `0x0217ACA0` | 0 | 0 |
| `setter_r2` `0x0217AACC` | 0 | 0 |
| `direct_13_14` `0x0217C894` | 0 | 0 |
| **total issues** | **21** | **78** |

**Nothing is ever refused.** The resolver returned 0 on 0 of 21 issues in A and 0 of 78 in B.
"Selected but refused" is not a phenomenon on this fixture; the resolver never rejects. The
three never-firing sites are also not a refusal story — they are simply not reached.

**The freeze is a silence of the funnel itself.** Arm A's last issue is at **frame 930 of 3842**
— 2912 frames in which the AI never even asks. At that same frame `p1x` jumps to 213554
(834.2 px, the 1/256 px unit confirmed against the known 764.0 px pin) and both positions pin.
Arm B's last issue is at **frame 3697**: the patched AI acts until the run ends.

**The punish band is a symptom, not a property.** Arm A issued ids `{1,2,4,5,6,9,11,12}`. Arm B
issued those plus `{3,7,8,10,13,14}`. So **ids 13 and 14 fire 17 times under the patch and zero
times in stock**, and they arrive from three different producers:

| producer | 13 | 14 |
|---|---|---|
| `reaction_table_AI3A` (entries 11/12) | 3 | 4 |
| `mask_enum_B` (bits 13/14) | 6 | 1 |
| `stack_s8_table` | 0 | 3 |

3.27 killed the veto (the word is 0 on every frame) and the weight story (the band holds 30/256 =
11.7%). This settles the third option with a count instead of a caveat: **stock runs the reaction
path about 5 times in 3842 frames, so an 11.7% band is expected to fire ~0.6 times.** The band was
never rare — it was *starved upstream*. Restore the path and the band fires. The punish band's
absence was a symptom of the freeze.

**And the patch is not merely an unfreeze.** P2's own state histogram, A then B:
`{0:3476, 1:47, 6:28, 9:178, 11:113}` → `{0:2007, 1:280, 3:30, 9:451, 10:217, 11:638, 12:219}`.
State 11 is the dream attack (the combat notes §12, via `atns1`/`jh7d`), so dream-attack frames go
113 → 638; states 10 and 12 are the SELECT ultimate and they are absent in stock. P1's HP falls
**9216 → 2975, having dipped to 2175**, in B; in A it is 9216 on every frame and never moves. The
patch does not just stop the freeze; it produces a fight.

**Caveat, and it is load-bearing.** Arm B is **one sample**. A live playtest reports that the
patched build no longer reproduces across savestate loads, where stock did
(`jus-freeze-state-gate-sol3` comment, 2026-09-28). If that holds, B is not a trajectory that can
be re-derived, every patched claim needs N repeats rather than one capture, and the patch should
be suspected of reading state the savestate does not define. Test it before relying on any single
patched capture.

---

### 3.29 The fixture is deterministic; the bridge's reads are not atomic

A live playtest reported that the patched build no longer replays the same sequence across
savestate loads where stock did. That is a claim about the fixture, and it is falsifiable with the
bridge alone — no GDB, no breakpoints. Driver: `<TMP>/ai-determinism/determinism_run.py`.
Eight replays per arm, 1500 frames each, no input, from a savestate. The plan carries
`load_state`, so `agent_bridge.lua` makes the load and the first plan frame atomic
(`begin_state_load` → `settle_step` → `start_plan`); every rep therefore starts at the same
emulator framecount with no variable idle window and no physical-input exposure.

**Result: no trajectory split in either arm.** Four of eight stock reps are bit-identical to rep
0 across all 1501 rows × 23 watches. Three differ, each in **one or two rows out of 1501**. Seven
of eight patched reps are bit-identical; the eighth differs in one row, and that one has `d=2`
with the same `fc` recorded twice — `plan_step` advanced two steps in one callback and read the
same memory twice, so the log duplicated a frame. That is a logging artifact, not a game event.

**With the comparison keyed on `fc` and rows carrying `torn` or `d > 1` dropped**, the patched arm
is clean: 7 of 7 reps identical to rep 0, and the eighth's blip disappears because both of its rows
were `d=2` duplicates. The stock arm keeps three blips, all first differing in `ai_3e`, at
**fc 32540, 32541 and 32550** — one to eleven frames after the load. Those carry the torn-read
signature below, and the new bridge flag is what identifies them rather than inference.

The comparison must be keyed on `fc`, never on row index: cleaning drops rows, and a dropped row
shifts every later index and manufactures a divergence. An earlier revision of this driver did
exactly that and reported the patched arm as nondeterministic when its only blip was a duplicate.

**The blips carry a signature.** At each stock blip the divergent rep's values equal the
reference rep's **next** row, in every differing field at once — including `react_roll`, a 0-255
draw, and `p1x`/`p2x`, fixed-point positions. Matching the next row in all fields by chance is
implausible. It is not a one-frame lag of the series either: shifting a whole series by one row
produces ~1493 mismatching rows, not two.

**The mechanism, confirmed against the melonDS source (codex, `opencode/gpt-6-sol`).**
`EmuThread.cpp:451` emits `signalLuaUpdate` after `RunFrame()` and message handling. The connected
Lua slot runs on the **Qt GUI thread**, while emulation continues on its **own thread**.
`LuaMain.cpp:167` calls `_Update`, and `agent_bridge.lua:456` reads `emu.framecount()` **first**
and the watches **after**. `framecount()` reads `NDS::NumFrames`, which is incremented near the
**end** of `RunFrame` (`NDS.cpp:1067`). So the emulation thread can begin writing the next game
frame's RAM after Lua has read the counter but before Lua has read a watch. Two callbacks can
record the same `fc` with different RAM phases. The 23 watches are also read **sequentially**, so
a row is not an atomic snapshot even in principle.

**Cross-launch is clean.** The reported variance came from agents each launching their own
emulator and loading the savestate, so the matching test is separate launches, not one. Two
launches 45 s apart, five reps each, both arms, both slots re-verified after the relaunch: every
rep identical to rep 0 within its launch, and rep 0 of launch 1 identical to rep 0 of launch 2 on
all 1501 frames. Wall-clock/RTC-derived state is therefore **not** a source of variation, and
neither arm carries a sustained divergence.

**The `torn` flag cannot fire on the actual case, and the source says why.** `EmuThread.cpp:451`
emits `signalLuaUpdate` **after** `RunFrame()`; the signal is **queued**, so the slot runs on the
GUI thread at an arbitrary point in the emulation thread's *next* frame. `NDS::NumFrames` is
incremented near the **end** of `RunFrame` (`NDS.cpp:1067`), and the `emu.*` Lua surface is only
`getsystemid` and `framecount` — there is no pause. So a read that straddles a **mid-frame**
boundary sees the same counter before and after and is not flagged. The flag catches only the case
where a whole frame completed during the read: necessary, not sufficient.

**The working detector is therefore the signature, not the flag.** A torn read shows the *next*
frame's values — the divergent row equals the base's next frame in every differing field, and the
series re-converges. `determinism_run.py` classifies each divergence that way (`looks_torn`),
counts differing frames, and reports `BLIPS ONLY` when that count is small, `NONDETERMINISTIC`
only when it is large. On the current data every divergence is 1–2 frames and carries the
signature: **arm S is BLIPS ONLY, arm P is DETERMINISTIC, and both arms are DETERMINISTIC ACROSS
LAUNCHES.**

**The only fully sound fix is a C++ one:** snapshot the watched bytes on the emulation thread
after `RunFrame()` (or expose a mid-frame progress signal) and have Lua read that. Until then the
rule stands: a one-row blip that matches an adjacent frame is an artifact; only a divergence that
persists is real.

**The remaining driver-path hazard is now opt-out-able.** A bare `state_load` calls
`release_override()` at settle, so the pad returns to physical input and the game runs with it
live until the next plan latches it. `state_load {slot, keep_neutral: true}` now holds the pad
neutral instead, and the ack reports `kept_neutral`. Deterministic replays should pass that flag
or, better, use `run_plan`'s `load_state`, which is atomic and latches input for the whole replay.

**Consequences.**

- **Bit-identity is the wrong criterion for a capture.** The right one is *no divergence that
  persists beyond one row*. §3.25's "control arm bit-identical to cap1 on all 23 fields across
  3400 frames" should be read as "no sustained divergence": torn rows run at roughly 5 per
  12008 here (~0.04%), so 3400 rows has an expected ~1.4 blips and an exact match was partly
  luck, not proof of a stronger property.
- **The patch is not implicated.** Neither arm shows a sustained divergence. Do **not** claim the
  patched arm was "cleaner" than stock as a *rate*: the two saved slots begin 40 emulator frames
  apart (`fc=32539` vs `32579`) as well as differing in the guard word, so only the within-arm
  comparison is valid, and three blips versus zero is well inside sampling noise. Codex's caveat
  stands: a genuine divergence that reconverges by the next sample is not excluded by this data.
- **The bridge flags torn rows, partially.** `agent_bridge.lua` brackets the watch batch with two
  `emu.framecount()` reads and writes `"torn":true` when they differ, in `plan_step` and
  `tail_step`; `tail_stop` reports a `torn` count. It did not fire on any observed blip, because
  the mid-frame case leaves the counter unchanged. Drop `torn` and `d > 1` rows, compare on `fc`,
  and treat a single-frame divergence that matches an adjacent frame as an artifact.
- **The reported variance is not a determinism break.** Cross-launch is clean on both arms, so
  neither RTC/wall-clock state nor the patch is implicated. The remaining explanation is that the
  agents were observing *different windows of the same trajectory* — different run lengths,
  different fixtures, different driver paths — plus a ~0.04% torn-read rate. A frozen CPU makes
  that invisible; an active CPU makes it look like variance.
- **One driver-path hazard remains, and is now opt-out-able.** A bare `state_load` leaves the pad
  live until the next plan; pass `keep_neutral`, or use `run_plan`'s `load_state`.

---

## 4. The patch

`scripts/patches/make_cpu_ai_patch.py` builds the patches;
`scripts/patches/verify_ips.py` re-applies them with an independent applier and
asserts the result. Both are committed. The builder re-derives both ROM offsets
by content search on every run and refuses to emit a patch if either has moved,
if any pre-image does not match, or if two edits overlap.

```sh
python3 scripts/patches/make_cpu_ai_patch.py --tier 1 --out cpu-ai-t1.ips
python3 scripts/patches/make_cpu_ai_patch.py --tier 2 --out cpu-ai-t2.ips
python3 scripts/patches/make_cpu_ai_patch.py --tier 3 --out cpu-ai-t3.ips
python3 scripts/patches/verify_ips.py cpu-ai-t1.ips
```

| Tier | Bytes | What it changes | Intended effect |
|---|---|---|---|
| **1** | 482, all in `ai_param.bin` | live gate params in rows 1–80 → index 3 (threshold 128) | may change action frequency; failure throttle remains reachable |
| **2** | 477, 476 data + 1 code | → index 7 (threshold 243), plus gate `cmp r1,#0x1B` → `#0x19` | also exposes the `0x1A` veto; behavior needs a live comparison |
| **3** | 478, 476 data + 2 code | tier 2 plus the shared table → all 255 | also speeds the five band gates; broadest and least predictable |

Tier 2 exposes the `0x1A` veto described in §3.11. The patch does not set
`+0x1A`; it only stops the gate from refusing the index. The profile bytes
would select different threshold paths:

| `+0x1A` in the profile | rows | gate path |
|---|---|---|
| 0 | 36 | threshold 64; acceptance fraction unmeasured |
| ≥ 8 (10, 12, 20, 25, 32, 50, 64, 96, 100, 128) | 44 | threshold comparison bypassed, subject to cooldown and caller preconditions |

The earlier prediction that this makes a behavior near-unconditional for some
characters and 25% likely for others is withdrawn. The branch can veto a
pending action, and its observed rate is unresolved. Tier 2 therefore remains
experimental.

The 4-byte code edit in tiers 2 and 3 is `0xE351001B` → `0xE3510019`, the `cmp`
at `0x02179130`. The verifier decodes it back and asserts the compare form and
its AL condition survived.

### Design choices worth arguing about

**Data over code, and all rows.** Tier 1 edits every archetype in rows 1–80
rather than trying to name "the CPU row". That is deliberate: the selector byte
at `0x020B0038` is unresolved, so patching all candidates is robust to not
knowing which one is live. It also means the patch cannot be undone by choosing
a different character.

**Index 3, not 7, for the default.** Section 3.3 explains the failure
throttle. Index 3 selects threshold 128 and index 7 selects 243, but the
failure rates and resulting pace are unknown until the per-call values are
measured. Tier 1 is the smaller data edit; tier 2 also changes control flow.

**No `≥ 8`.** Making a parameter `≥ 8` bypasses the threshold comparison.
Nothing in the parameter bytes shows what that does to spacing or recovery, and
the existing high-aggression archetype (group 18) still leaves `+0x1F` at 6 and
several cells deliberately below unconditional. The shipped design does not go
to "always", and neither does tier 1 or 2.

**What the patch does not touch.** The gate sits behind other preconditions —
at `0x0217BE30`–`0x0217BEBC` the code first requires a selected target, a
target byte `≥ 0xD`, and a non-zero pointer at `[state+0x24]+0x36`. Those remain.
The movement AI, the `+0x11` and `+0x12` gates, the band gates, and the ledge
and recovery logic are all untouched. So a higher action rate does **not** by
itself produce better spacing or fewer self-KOs; it produces more attempts.

### Build and verification state

| Check | Result |
|---|---|
| ROM offsets located by content match | unique, both |
| Pre-images verified against live ROM | all |
| IPS applies, size preserved | yes |
| All diffs confined to `ov11` / `ai_param.bin` | yes |
| Gate `cmp` still decodes as `cmp r1,#imm` with AL | yes |
| Threshold table values in range | yes |
| Three consecutive builds byte-identical | yes |

**No patch has been run in the emulator.** Every statement about play quality
above is a prediction.

### Playtest result (2026-09-26) — the prediction was half right

The pivot edit was applied live in emulator RAM and the owner played against it.
The patch was verified live before, during and after, so this is a result rather
than a setup failure.

> "It does seem more active at least."
>
> "I'm still seeing the walk right off the side and it doesnt seem to be much
> smarter or more difficult to fight."

More activity: confirmed, so the pivot's mechanism works as described.
More intelligence: **not delivered, and not deliverable by this lever.** The pivot
raises how often one behaviour out of 23 is armed. That is a frequency knob on a
weighted-random selector. It changes how busy the CPU looks, not what it decides.

Self-KO: unchanged, and section 5's item 6 is now a hard negative rather than an
open question. Every `cmp`/`add`/`sub` immediate in ov11 was scanned against ten
plausible stage widths in 8.8 fixed point and got **zero hits**. The only spatial
limits in the movement code are fighter-relative (`cmp r2,#0x400` at `0x0217F430`
for separation, `cmp r0,#0x8000` at `0x0217F540` for repulsion).

> **The conclusion drawn from that scan was WRONG, and is retracted.** The scan was
> correct; the inference was not. It established that no stage bound appears as an
> *immediate* in ov11 — not that the AI lacks bounds. The AI reads them as **data
> fields**: a limit at `+0x150` and an extent at `+0x158`, used together as
> `limit + extent` for the opposite limit, plus the engine's wall bits at
> `[M+0x78]`. See §3.12. The "structurally blind to the ledge" claim, which I
> repeated to the owner, was wrong.

That reframes the ticket. The live pivot increased activity without the owner
seeing better decisions; the remaining explanations are hypotheses to test:

| Report | Levers that could actually move it |
|---|---|
| Accidental self-KOs | **RETRACTED — see §3.12.** The AI reads both a limit and an extent at `+0x150`/`+0x158` and tests the engine's wall bits at `[M+0x78]`. It is not blind to the edge. |
| Careless attacks | attack *selection* code, not selection probability |
| Poor punishment | the reaction path, which is lockout-gated |
| Yugi beam dead zone | threat-representation geometry |

Whether any requires ARM code depends on the open traces. `ov11` is not out of room, merely fragmented: 23 trailing
bytes plus internal holes of 36 and 32 bytes at `0x0218161C` and `0x021816A0`,
~91 bytes total, and larger runs exist in `ov10` (896 B) and `ov00` (204 B) if
co-residency allows. Because `ov11` loads to its own virtual address, a code edit
is a poke at that address — see
[`ai_patch_ram.py`](../../../scripts/emu/ai_patch_ram.py).

---

## 5. What is not known, and what to measure first

Ordered by how much each answer would change the patch.

1. **Which row does the combat CPU actually load?** Read
   `0x020B0038 + i * 0x4C` and the 0x30 bytes at `table + that * 0x30` in a live
   match. Everything about tier 1's blast radius depends on it. Also settles
   whether the three menu settings change this byte at all, which the picker
   analysis in 2.4–2.5 does **not** answer.
2. **Is the 30-tick cooldown throttling anything now?** If tier 1 shows no
   change, the gate is not on the path that matters and the work moves to the
   band gates and the `+0x11` / `+0x12` pair.
3. **Does the dead `0x1A` behaviour (tier 2) help or hurt?** It has never run in
   this build, so its effect is genuinely unknown.
4. **`0x02179278` inverts.** If a later step wants to raise the CPU's
   aggression further, that parameter must go *down*. Confirm which visible
   behaviour it drives before touching it.
5. **Why is group 18 different?** Its `+0x2E` ladder is `2, 4, 6, 7` and its
   parameters are the most aggressive in the file. Whether that is a hidden
   difficulty, a boss mode, or an unused tuning pass is open. It is also the
   best available reference for "what aggressive looks like" in shipped data.
6. **Ledge safety and self-KO — answered, and the answer is in §3.14.** The scan
   for stage-width *immediates* found nothing, but the AI reads its arena limits
   from data fields at `r5+0x150`/`+0x158`, and **both are zero** because the
   constructor memsets the object and never writes them. This is a data/init fix,
   not a code injection.

The owner's reported weaknesses map onto this as follows, with the honest
status of each:

| Report | Status |
|---|---|
| Careless attacks | partially addressed: more actions attempted, but attack *selection* is not touched |
| Poor punishment | not addressed; needs the reaction path, not the action rate |
| Excessive defense (Yugi beam dead zone) | not addressed; needs threat-representation geometry |
| Accidental self-KOs | **root cause found, §3.14** — the AI's arena limits are never populated, so its arena is the empty interval `[0,0]` and one of its two wall senses is unreachable. A data fix, not a code injection. |

The first-pass document proposed judgement fixes — ledge safety, threat
recognition, attack selection, punishment. None of those are reachable by
editing probability bytes. They need the decision code, and the honest read is
that this ticket delivers a *more active* CPU, not a *smarter* one. Whether that
is the same thing is an empirical question, and it is the first thing to test.

---

## 6. Evidence

```sh
python3 scripts/analysis/disasm_range.py 0x021730D0 0x02173120 --overlay 11
python3 scripts/analysis/disasm_range.py 0x02179130 0x021791A4 --overlay 11
python3 scripts/analysis/disasm_range.py 0x0217920C 0x021792A0 --overlay 11
python3 scripts/analysis/disasm_range.py 0x021793A8 0x02179480 --overlay 11
python3 scripts/analysis/disasm_range.py 0x02179570 0x02179620 --overlay 11
python3 scripts/analysis/query.py xrefs-to 0x02172FEC
python3 scripts/patches/make_cpu_ai_patch.py --tier 3 --out /tmp/t3.ips
python3 scripts/patches/verify_ips.py /tmp/t3.ips
```

Addresses without an overlay label are overlay 11. Linear disassembly decodes
data pools as instructions, so only the spans above support the claims here.
