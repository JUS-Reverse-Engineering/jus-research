# Horizontal knockback: every per-character/per-victim input on the kbX → element+0x30 path (static-only)

Tracker items: `jus-idiy` (child of `jus-pb6n`). Grade: **PLAUSIBLE, static-only** — no
emulator run in this pass; every claim below is a disassembly read against
`python3 scripts/analysis/query.py disasm` and `scripts/analysis/move_records.py`,
cross-checked against the runtime capture JSON already on disk in
`docs/research/feel-captures/kakashi-2026-09-03/`.

## Task

`physics.md` §4.6 GAPS (echoed in the engine notes §4C) says horizontal knockback
calibration is "exact on two characters and off by a fixed ratio on Kakashi."
Find every per-character or per-victim read on the kbX path from `moveData+0xC`
to `element+0x30`, and check whether any of it could produce a *fixed
per-character ratio* the way the §4.1 weight bits (×0.5/×1.5) do for the
already-solved weight case.

## The path, disassembled end to end

**Stage 1 — arm9 hit processor, region `0x020817E8`–`0x02081978`** (inside
`0x02080F14`; `r6` = the hitbox/moveData context, `r3 = [r6+0x10]` = moveData
pointer, `r5` = attacker context, `r8 = M+0xA4` where `M` is the victim's
ColPrm scratch block):

```
0x020817F0  ldrsb r4, [r3, #0xc]     ; kbX  (moveData+0xC, s8)
0x020817F4  ldrsb r3, [r3, #0xd]     ; kbY  (moveData+0xD, s8)
0x020817F8  cmp   r0, #6             ; r0 = moveData[+1] (hit type)
0x020817FC  ldrsheq r2, [r8, #0xca]  ; if type==6: HP frac from M+0xCA
0x02081800..0812  table lookup -> r1 = M (HP-band table, or literal 0x100 if type!=6)
0x02081810  ldr r2, [sp, #0x18]      ; "doubling" flag, cmp #0 (flags kept live)
0x0208181C  mvn r2, #0x9d            ; r2 = -158
0x02081820  mul r2, r3, r2           ; r2 = kbY * -158
0x02081824  mul r3, r1, r4           ; r3 = M * (kbX<<7)   [r4 was lsl #7 at 0x02081804]
0x02081828  mul r2, r1, r2           ; r2 = M * kbY*-158
0x0208182C  asr r7, r3, #8           ; r7 = x = (kbX<<7)*M>>8
0x02081830  asr r4, r2, #8           ; r4 = y = (kbY*-158)*M>>8
0x02081834/38  lslne r7,r7,#1 / lslne r4,r4,#1   ; doubling flag, both axes equally
0x0208183C..1860  weight gate: r0=[[r5+0xc]+0x44] (victim M+0x44)
                   tst #0x80  -> r7 -= r7>>1 ; r4 -= r4>>1     (both axes)
                   tst #0x8000 -> r7 += r7>>1 ; r4 += r4>>1    (both axes)
0x02081864..1888  zero/override bits from victim record +0x14 (0x01000000 zeroes
                   both r4 and r7; 0x04000000 + attacker +0x14&0x700 overrides
                   both to a fixed (0x300, r7-0x800))
0x0208188C..192C  sign selection for X only: either a relative-position compare
                   (victim record +0x18 bit 4) or a call to the facing helper
                   0x0206CF28; either way the result ADDS or SUBTRACTS r7 into
                   [r8,#0xa4] = M+0x148  (accumulate: ldrsh, add/sub, strh — a
                   += / -=, not an assignment)
0x02081968..1978  y-only extra scale: r0 = y*223 (0xdf=223 decimal), asr #8,
                   added into [r8,#0xa6] = M+0x14A (the documented ×223/256)
```

X gets **no** equivalent of the y `×223/256` step — it is accumulated into
`M+0x148` raw, matching physics.md's pseudocode exactly (the `M+0xA4`/`M+0xA6`
labels the doc already flagged as wrong resolve to `M+0x148`/`M+0x14A` once
`r8 = M+0xA4` is accounted for: `r8+0xA4 = M+0x148`).

**Stage 2 — victim-side scaler, ov6 `0x0215AF88`–`0x0215AFC4`:**

```
r0 = [[r4+0x1a8]+0x10] + 0x100         ; M+0x100
r2 = ldrsh [r0,#0x48]                  ; M+0x148 (staged X)
r5 = ldrsh [r0,#0x4a]                  ; M+0x14A (staged Y)
r0 = smulbb(r2, 0x64)                  ; X * 100
     bl 0x200d12c (signed div, r0/r1=100)   -> stored obj+0x10A   ; X*100/100
r0 = smulbb(r5, 0x48)                  ; Y * 72
     bl 0x200d12c (r0/100)             -> stored obj+0x10C        ; Y*72/100
```

Both constants (`0x64`=100, `0x48`=72) are **immediates**, not table reads —
no per-character or per-victim input exists in this stage either.

## Candidate table

| candidate | read anywhere on this path? | per-character? | could give an X-only fixed ratio? |
|---|---|---|---|
| Weight bits, victim `M+0x44` (§4.1) | Yes, `0x02081844`–`0x02081860` | Passive-list-derived, not a stat | **No** — scales `r7` (x) and `r4` (y) with the *same* two `tst`/shift pairs; any weight value that changed x would change y identically, and Kakashi's vertical recipe already reproduces exactly (kakashi.md), so weight can't be the X-only culprit |
| HP-band table (§4.2), `M+0xCA>>6` | Yes, `0x020817FC`–`0x0208180C`, gated on `type==6` | Per-victim-HP, not per-character | **No**, same reason — `r1` (M) multiplies both `mul r3,r1,r4` (x) and `mul r2,r1,r2` (y) identically; also none of the four Kakashi normals inspected here are `type==6`, so `M` is the literal `0x100` identity for all of them |
| chr_b table read (attacker or victim index → multiplier) | **Not found** anywhere in `0x020817E8`–`0x02081978` or `0x0215AF88`–`0x0215AFC4` | — | No — no such load exists on this path |
| Victim `M+0x184`/`M+0x186` (f1/f2, damage.md §2.2/§8) | **Not found** on this path | They live in the *damage* formula (`0x02082480`–`0x02082484`), never referenced in the knockback stage/scale routines above | No |
| Ground/air byte (`char+0x78`) | Only **written** (`0x02081990`–`0x02081998`, sets bit `0x80000` on the attacker's `+0x78` iff staged Y > 0) — never read for scaling | — | No — it's a side effect of the pipeline, not an input to it |
| Doubling flag `[sp+0x18]` | Yes, `0x02081810`/`0x02081834`/`0x02081838` | Per-call-site stack value, not per-character | Gives a `×2`, not a fractional "ratio" |
| Zero/override bits, record `+0x14` (both sides) | Yes, `0x02081864`–`0x02081888` | Per-record flag, not per-character | Gives `0` or a fixed `(0x300, r7-0x800)` override, not a proportional ratio |
| Sign/facing (`+0x18` bit 4 or `0x0206CF28`) | Yes, `0x0208188C`–`0x02081930` | Per-hit relative position | Flips sign, doesn't rescale magnitude |

**Conclusion: none of the candidates match.** Every load that reaches the X
accumulator is either shared bit-for-bit with the Y path (weight, HP-band,
doubling, zero/override) or is a sign/boolean selector, not a magnitude
scale. Because weight and the HP-band factor multiply x and y through the
*same* `M` register in the *same* instructions, any hypothesis routed through
either one is refuted by the fact that Kakashi's vertical recipe already
reproduces exactly (physics.md §4.6, kakashi.md) while the horizontal side
does not — a shared-`M` bug would break both axes together.

## Checking the "fixed ratio" framing itself

Live capture data already on disk (`docs/research/feel-captures/kakashi-2026-09-03/`)
does not support a *fixed* ratio at all:

| move | authored record | authored `kbX` (`+0xC`) | measured `kb[0]/128` | ratio | `v_ground` | `hit_type` |
|---|---|---|---|---|---|---|
| `B` | rec 0 (`0x100`) | 8 | −5 | 0.625 | `0x22` (grounded) | 1 |
| `up B` | rec 5 (`0x105`) | 4 | −4 | 1.0 | `0x20` (launch-frame) | 2 |
| `side B` hit 1 | no record matches `(kbX 3, kbY 5, type 1)` | — | −3 | undefined | `0x20` | 1 |
| `side B` hit 2 | rec 3 (`0x103`) by `kbY` only; its `kbX` is 0 | 0 | −8 | undefined (0→8) | `0x0` | 2 |

Two findings from this table:

1. **The comparisons are not like-with-like.** `B`'s victim is grounded
   (`0x22`) at the hit; `up B`'s and `side B`'s are not (`0x20`/`0x0`, i.e. on
   the launch frame or airborne). The brief's third check — same hit type,
   same HP band, same grounded state — **fails**: none of these four rows
   share a `v_ground` value, and `side B`'s two hits are different `hit_type`s
   (1 then 2). A single number called "the Kakashi ratio" is being computed
   across rows that differ in exactly the state bits the pipeline is shown
   above to test (`+0x18` bit 4, the record `+0x14` zero/override bits).
2. **`side B` hit 1's measured `(kbX 3, kbY 5)` matches no authored record in
   `na_b_05.bin` at all** (checked every `type == 1` record: `0x100 (8,0)`,
   `0x102 (7,0)`, `0x104 (2,0)`, `0x105 (4,12)`, `0x106 (−4,4)`, `0x113 (−4,2)`,
   `0x117 (0,6)`, `0x119 (8,14)`). A ratio against *any single* record cannot
   be fixed if one of the four data points has no candidate record to be a
   ratio *of*. The "0.625" and "1.0" rows above are two different numbers, not
   one fixed ratio, and the fourth row isn't a ratio at all.

The most code-consistent explanation that needs **no new per-character
input**: `M+0x148` is accumulated with `+=`/`-=` (confirmed in the disasm
above, `0x020818C0`–`0x020818C8` and the sibling branches), not assigned. If a
move fires more than one hitbox record in the same frame — plausible for
Kakashi's `side B` two-hit sequence, or for any move where a windup hitbox and
the main hitbox land on the same input frame — the measured `kb[0]` for "the
hit" is the **sum** of two (or more) records' individually-correct `kbX`
contributions, not one record's own byte. That reproduces a Kakashi-only-looking
discrepancy with zero per-character code, because the accumulation is
universal — it would just never have been *visible* on Nami/Luffy if their
tested moves happened to be single-hitbox-per-frame.

This is offered as the most economical hypothesis, not a closed finding: it
is not yet checked whether Kakashi's `B`/`side B` have >1 live hitbox record on
the hit frame, and the `move_records.py` field-extraction offsets have not
been independently re-verified against the runtime pointer arithmetic beyond
the one instruction pair quoted above.

## What this rules in/out for physics.md §4.6 / the engine notes §4C

- **Ruled out** as the source of an X-only Kakashi ratio: weight bits
  (`M+0x44`), the HP-band table, chr_b index tables, `M+0x184`/`M+0x186`
  (those are the damage formula's f1/f2, a different routine entirely), and
  the ground/air byte (write-only on this path).
- **Not ruled out, needs a live test**: record accumulation (`M+0x148 +=`)
  across multiple same-frame hitboxes, and/or a mismatch between
  `move_records.py`'s printed field offsets and the runtime pointer's actual
  base (both would look like a "Kakashi-specific ratio" without requiring any
  per-character code path).
- The GAPS entry's "off by a fixed ratio" phrasing should probably be
  softened: the raw numbers in kakashi.md are not one fixed ratio, and at
  least one of the four rows compared isn't a same-hit-type/same-ground-state
  comparison at all.

## Live test spec

Three characters: **Kakashi** (the anomaly), **Nami** and **Luffy** (already
"exact" per physics.md §4.2's cross-character checks).

1. `JUS_WATCH` on `M+0x148` as a **write log** (not a single post-hit read) —
   every store to `[[obj+0x1a8]+0x10]+0x148` during the input frame of a hit,
   with the call-site PC, so a single-write hit and a multi-write (accumulated)
   hit are distinguishable.
2. Drive the same three Kakashi moves (`B`, `up B`, `side B`) each in a
   dedicated run, holding: victim HP band (full HP, so the type-6 gate never
   fires and `M` stays the `0x100` identity for a clean read), victim grounded
   state at the hit (script the setup so all three land on a grounded victim,
   or explicitly log `v_ground` and only compare same-value rows), and
   distance (per physics.md §4.4, hold attacker–victim distance fixed).
3. For each write, log the moveData record pointer (`[r6+0x10]`) address next
   to the write, so the exact record consumed by the hardware can be diffed
   byte-for-byte against `move_records.py`'s dump for that id — this directly
   tests the offset-mismatch hypothesis.
4. Repeat step 1–3 on one Nami and one Luffy move already confirmed exact
   (e.g. the Kenshin-X-style single-hit normals used in physics.md §4.2), to
   confirm the same watch shows exactly one write per hit there — the control
   that would tell "accumulation is universal but usually invisible" apart
   from "accumulation is Kakashi-specific."

If step 1 shows two writes to `M+0x148` on a single Kakashi hit frame and one
write on the Nami/Luffy controls, the accumulation hypothesis is confirmed and
no new per-character multiplier needs to be found. If it shows one write on
all three but the record pointer diffs from `move_records.py`'s dump, the
offset-mismatch hypothesis is confirmed instead — and `move_records.py`'s
field table (not the runtime code) is what needs fixing.

## Live (`jus-idiy`, 2026-09-12)

The live test spec above ran (mostly) as designed —
trio Check B RESULTS, states
`pc-kakashi-npc-jotaro-dark-tournament` (Kakashi attacking) and
`pc-kenshin-npc-nami-dark-tournament`/`pc-kenshin-npc-luffy-dark-tournament`
(controls; no Nami/Luffy-attacker savestate exists in the repo, so the two
control characters were exercised as physics.md measured them, as victims of
Kenshin's attacks rather than as attackers themselves).

- **Accumulation hypothesis: refuted.** 20 hits captured (7 Kakashi/Jotaro, 7
  Kenshin/Luffy, 6 Kenshin/Nami) across 12,280 frames. Every hit showed
  exactly one `HITPROC` call, one `KBX_STORE`, one `KBY_STORE` per frame;
  `kbx_stores_prev`/`kby_stores_prev` never exceeded 1. `M+0x148` never
  receives two writes on the same frame for any move driven in this
  session, including Kakashi's two-hit `side B`.
- **Offset-mismatch hypothesis: not tested by this run.** The probe did not
  log the moveData record pointer — the break address (`0x020817E8`) turned
  out to be the `moveData` load instruction itself, so every logged
  `moveData` read `0x0`. A re-run breaking one instruction later, at
  `0x020817EC`, is needed to capture a valid pointer and diff it against
  `move_records.py`'s dump.
- **Every store's `new_val` matched `kbX*128` exactly**, but `M` (the
  multiplier) was `0x100` on every single hit measured, on Kakashi and both
  controls — this run drove no hit with `M != 0x100`, so it cannot
  distinguish "the shortcut holds unconditionally" from "the shortcut holds
  when `M == 0x100`."
- **Record cross-check** (`move_records.py kakashi --list`): of the four
  distinct non-mashed `(kbX,kbY)` pairs measured on Kakashi, `(4,12)`
  matches record 5 exactly; `(5,0)`, `(3,5)`, and `(8,15)` match no record
  in `na_b_05.bin`. This points the discrepancy at **which record the
  engine reads**, not at the staging arithmetic this doc's "offset
  mismatch" hypothesis anticipated (a mismatch between `move_records.py`'s
  field offsets and the runtime pointer's base) — the earlier draft's
  "decayed velocity"/measurement-methodology explanation is withdrawn as
  unsupported by this data (this run never measured downstream, post-move
  velocity, only the staging write).
- **Next step, unchanged in substance**: a HITPROC re-run breaking at
  `0x020817EC` to capture the moveData pointer, plus a driven hit with
  `M != 0x100` to close the constant-`M` gap. See physics.md §4.6 GAPS.
