# Movement and knockback physics — spec

This reference describes measured behavior in the original game.

## Navigate this reference

| Topic | Section |
|---|---|
| Gravity and falling | [1](#1-gravity-and-falling) |
| Fast-fall | [2](#2-fast-fall-writes-a-constant-into-y-velocity) |
| Jump arcs | [3](#3-jump-arcs) |
| Knockback and hitstun | [4](#4-knockback-from-a-launching-special) |
| Runtime structure | [5](#5-supporting-runtime-structure) |
| Walk, dash, jump, and landing | [6](#6-movement-walk-dash-jump-2026-09-02) |
| Per-frame task order | [7](#7-per-frame-task-order-2026-09-12) |
| Open research | [GAPS](#gaps) |

> **Source campaign:** `jus-golden-damage-vectors-mj25` (feel-capture campaign).
> Evidence is six owner-played captures in `docs/research/feel-captures/`
> (`m00`–`m06`), each with a notes file; `../research/feel-captures/m03-analysis-fable.md`
> carries the independent re-analysis. Everything below is runtime measurement from those
> logs. Code locations are claimed only where a section cites an address (the
> integrator, the launcher and pop formula in §4.6, the fast-fall writer in §2,
> the hitstun formula in §4.5). The terminal fall velocity and the drag
> coefficient are still unpinned — see §GAPS.

**Conditions block, applying to every number in this file unless stated
otherwise.** Training mode, items and gimmicks OFF, auto-heal OFF, JUS on
melonDS with the fork patches in `scripts/emu/build_info.json`. Positions are
s32 8.8 fixed-point pixels; velocities are per-frame position deltas in the
same units. HP is u16 with displayed = raw / 64. Captures are passive
per-frame RAM reads (`scripts/emu/capture_feel.py`), never injected input.
Player character was Kenshin (`chr_b 36`) for all attack measurements; the
attacker's panel matters (see §3).

## 1. Gravity and falling

**Falling is drag toward a terminal velocity, not constant acceleration.**
Both directions of approach were observed in one match (`m02`):

- Normal descent: per-frame downward delta climbs 3.0273 → 4.2383 px/frame
  with *shrinking* increments (raw +17, +17, +16, +16, +15, +15 …).
- Fast-fall descent: per-frame delta *decays* 11.7852 → 9.5547 px/frame
  (raw −53, −51, −50, −48, −47 …).

Normal falling approaches the terminal value from below and fast-falling from
above. Neither converged before landing in the captured arcs, so **the terminal
value and the drag coefficient are not pinned** (§GAPS).

Normal falling also produces a repeatable per-frame ramp of raw deltas — 21,
62, 102, 140, 177, 213, 248, 282, 315, 347, 378, 408 — each appearing 13–16
times across `m02`, i.e. once per jump. That ramp is the gravity integration.

**Horizontal knockback decay is exactly 7/8 per frame.** Confirmed in `m02`
and independently in `m04`–`m06` (e.g. 14.3555 × 0.875 = 12.5611 against
12.5586 observed on the next frame).

## 2. Fast-fall writes a constant into Y velocity

**Fast-fall does not scale gravity; it sets the Y velocity field.** On the
input frame the character is still rising and decelerating into apex, and the
very next frame is a large positive delta:

```
fc 17367  y 522.809  dy  -0.2500   <- still rising
fc 17368  y 534.594  dy +11.7852   <- fast-fall input; apex cancelled
fc 17369  y 546.172  dy +11.5781   <- then decays (drag, §1)
```

The constant is **raw 3017 = `0x0BC9` = 11.78516 px/frame**, observed as the
first fast-fall frame delta in 10 of `m02`'s 22 airborne segments, and
**identical for Kenshin and Lenalee** — so it is an engine-wide constant, not a
per-character stat.

**Found 2026-09-02 (`jus-fast-fall-input-em4b`, `movement-2026-09-02/mv11`).** The input is **DOWN+A in
the air**. ov6 `0x0215E118` stores `vy = 0` and writes the immediate **`0xC00` =
3072 raw = 12.0 px/frame** into the y accel field `element+0x2E`
(`mov r1, #0xc00` at `0x0215E138`, so no pool literal existed to find). The same
frame's 1/32 drag and +41 gravity turn that into the observed 3017. It works
during ascent, descent, and from a short hop, and takes effect on the frame after
the input registers. The routine also bumps a counter at `[obj+0x1A4]+0x50`.

## 3. Jump arcs

From `m02`'s sampler (Jotaro, Sanji, Kenshin, Lenalee):

- Single jumps are repeatable to the frame: six identical arcs of **61 frames
  peaking at 74.68 px**.
- **Ascent is not gravity reversed** — 26 frames up against 36 frames down for
  the same height.
- Double jumps peak near **149 px**, almost exactly twice the single.
- Ascent peak velocity is 6.11 px/frame for singles and 6.47 for doubles.

> These are the **held** jump (A ≥ 6 frames). A tap gives a 45-frame short hop; the impulses and the tier table behind them are in §6.4 (2026-09-02).

## 4. Knockback from a launching special

Measured with Kenshin's 5-koma X throughout. **The move is 9 hits** — eight HP
drops of 3.00 plus one of 10.00, totalling 34.00 true damage — spanning exactly
**23 frames**, deterministic in every rep across four matches. Launch velocity
must therefore be read from the frame after the *last* drop; that frame is also
always the peak.

**Damage dealt is fixed; knockback is not.** The same move dealt 34.00 in
`m03`–`m06` but 25.50 in `m02` with a different Kenshin panel, so **the
attacker's panel changes the move's damage** and must be held fixed across
compared runs.

### 4.1 "Weight" is a pair of passive abilities, not a stat

Owner-designed controlled experiment (`m03`): two victims of very different
weight with **max HP equalised using HP-only helpers**, so the body was the
only uncontrolled difference. At matched health, **Nami (`chr_b 15`, light)
launches ~3x faster than Franky (`chr_b 17`, heavy)** in both X and Y —
12.85/20.03/28.71 px/frame against 4.79/5.70/8.07 at three matched health
levels. Measured body factors for the launch kick are Nami 3/2, Luffy = Naruto
= Raoh 1, Franky 1/2 (§4.2, `jus-launch-tier-fraction-weight-r0nz`).

**Located (`jus-9lp.2`, evidence
weight-hunt-2026-09-01c).**
There is no per-character weight number anywhere. The factor is two bits of the
victim's **±25% gate word** (ColPrm scratch `+0x44`, [damage.md](damage.md) §5),
which the loader fills from the character's passive-ability list:

| ability (`chr_b +0x03..+0x07`, [helpers.md](helpers.md)) | gate bit | launcher knockback | who has it |
|---|---|---|---|
| 24 軽量級 **Lightweight** | 15 (`0x8000`) | × 1.5 | Nami, PCT Nami, Anna, Eve, Rukia, Hitsugaya, Lenalee, Muhyo, Fuusuke |
| 23 重量級 **Heavyweight** | 7 (`0x80`) | × 0.5 | Franky, Caramelman, Edajima |
| neither | — | × 1 | everyone else, including Luffy, Naruto and Raoh |

The consumer is arm9 `0x02081844`–`0x02081860` inside the hit handler
`0x02080F14`: after the base impulse is formed, `tst #0x80 → r −= r>>1` and
`tst #0x8000 → r += r>>1`, on both axes, **only when the hit type byte is 6**
(the launcher type, §4.3). Proven causally by poking the gate word on the
Luffy state before a scripted Kenshin X: bit 15 set gave Nami's −4800 raw,
bit 7 set gave Franky's −1600, both bits gave −2400 (= ×0.5 then ×1.5), and
clearing Nami's bit 15 dropped her to Luffy's −3200 (`06-gate-bit-poke-*.log`).

This resolves the Raoh question: Raoh has neither passive, so he launches like
Luffy. The owner's "Raoh heavy" note was about something else (he has
`Take less damage from Special Attacks`), not launch weight.

### 4.2 Knockback rises in steps as the victim's health falls

Within `m03`, the same move at the same damage produced 12.85 → 20.03 → 28.71
→ 41.59 px/frame as the victim's health fell from 95% to 33% — a 3.2x change,
far larger than the ~20% measurement artifact in §4.4.

**The health term is a step function of the victim's HP as a fraction of its
max, with multipliers 1, 1.5, 2, 3** (`jus-launch-tier-fraction-weight-r0nz`;
scripted, distance held constant, Kenshin X finisher on five victims,
`docs/research/feel-captures/hx20-*`..`hx24-*`; first seen on Jotaro up+X in
`jus-launch-hp-tiers-u1jw`, `hx10-*`..`hx12-*`). The band is read from the
victim's HP **before** the launching hit is applied:

| victim HP before the hit | multiplier M |
|---|---|
| ≥ 3/4 of max | 1 |
| ≥ 1/2 | 1.5 |
| ≥ 1/4 | 2 |
| < 1/4 | 3 |

Edges were probed to 1 HP on five different max values (Naruto 144: 108/72/36;
Nami 136: 102/68/34; Luffy 152: 114/76/38; Franky 176: 132/88/44; Raoh 192:
144/96/48). A flat threshold set is refuted: Naruto at 110 and 108 HP is in the
top band, at 76, 75 and 74 in the second.

**Weight scales the values, not the edges.** With F the body factor
(`jus-launch-tier-fraction-weight-r0nz`, Nami 3/2, Luffy = Naruto = Raoh 1,
Franky 1/2), the Kenshin X finisher's victim delta on the first frame after
the hit, in s32 8.8 raw, is:

    vx_after = D(vx_before − 3200·F·M)      where D(z) = z − (z >> 3)
    |vy_after| = 576·F·M − G                 G = 41 raw exactly (first-frame fall term)

`D` is the known 7/8 airborne drag (§1). The horizontal launch is **added to
the victim's existing velocity**, not assigned: Naruto and Luffy share F but
their measured vx differ by exactly the dragged pre-hit velocity (Naruto was
drifting at +502 raw, Luffy at −123, giving −2360 and −2907 for the same
−2800 kick). Every measured vx across 33 runs is reproduced exactly; vy is
within ±0.5 raw of the arithmetic-mean model below (the exact integer recipe,
closed 2026-09-03 just below, reproduces vy exactly too — the ±0.5 was the
floor of the integrator's drag shift, not an unresolved rounding of G).
Jotaro up+X on Luffy fits the same
M and G with vertical base 480: predicted 438.5/678.5/918.5/1398.5 vs
measured 439/678/919/1398. The fit was derived independently by codex from the
numbers alone (tracker item body).

Raoh's numbers equal Luffy's to the raw unit in every band, so Raoh is **not**
heavier than Luffy for launch purposes. The owner had listed Raoh as heavy
(HANDOFF 2026-09-01); recorded as measured, owner to confirm.

**Located in code (`jus-9lp.2`, same evidence dir).** The whole kick is
computed once per contact by arm9 `0x02080F14` at `0x020817E8`–`0x02081978`,
from three bytes of the move-data block `[elem+0x10]` ([damage.md](damage.md)
§2.1): `type = u8[+0x01]`, `kbX = s8[+0x0C]`, `kbY = s8[+0x0D]`.

```
frac  = u16 scratch+0x16E = current_HP * 256 / max_HP      ; rebuilt every frame by 0x0207F95C-0x0207F984
M     = type == 6 ? table_0x0209FB64[frac >> 6] : 0x100    ; table = {0x300, 0x200, 0x180, 0x100, 0x100}
x     = (kbX << 7) * M >> 8                                 ; = kbX * 128 * M/256
y     = (kbY * -158) * M >> 8
if [sp+0x18]: x <<= 1, y <<= 1                              ; some doubling flag, not yet exercised
if type == 6: gate bit 7 -> x,y -= x,y >> 1 ; gate bit 15 -> x,y += x,y >> 1   ; weight, §4.1
scratch+0x148 (X, s16) += ±x  (sign from facing/side tests at 0x0208188C-0x0208192C)
scratch+0x14A (Y, s16) += (y * 223) >> 8
```

`frac >> 6` is exactly the quarter band: 256 (full) and 192..255 both index
`0x100`, 128..191 → `0x180`, 64..127 → `0x200`, 0..63 → `0x300`. That is why
the edges are 3/4, 1/2, 1/4 of max to the HP unit, and why a *flat* threshold
was refuted.

**Exact integer recipe, first-frame vertical and horizontal term (closed
2026-09-03, `jus-first-frame-vertical-rounding-hmfg`,
runtime-report-2
E2).** `ASR(x,n)` is an arithmetic (floor) shift right; `TZ(a/b)` is a signed
divide via arm9 `0x0200D12C` (truncate toward 0):

```
by = ASR(ASR(s·kbY·−158, 8)·223, 8)          ; s = M above; staged into M+0x14A
Y  = TZ(by·72/100)                           ; ov6 0x0215AFB4-C4 -> obj+0x10C
; --- next frame, arm9 integrator 0x02082E10 ---
vy += Y                                      ; 0x02082F30
vy -= ASR(8·vy, 8)                           ; 0x0208306C
vy += 41                                     ; 0x02083084, unless [E+0x34] bit 1
```

Six measured values, Kenshin X finisher (record 20: `kbX 25, kbY 6, type 6`)
on Luffy, reproduced exactly at both ends of the HP-band table:

| band | `by` | `Y` (staged) | `vy` after +41 |
|---|---|---|---|
| full HP (`s=0x100`) | −826 | −594 | **−534** |
| low HP (`s=0x300`) | −2478 | −1784 | **−1687** |

and the horizontal axis (`ax = ASR(s·(kbX<<7), 8)`, `vx −= ASR(32·vx, 8)`
same drag pass): `vx` = **−2907** (full HP) / **−8507** (low HP), against a
pre-hit drift of −123. All eight intermediate values (`by`, `Y`, drag,
gravity, `ax`, `vx`) reproduced to the raw unit — see the runtime report for
the full ordered write log. Codex (`gpt-5.6-sol`, neutral prompt, disassembly
only, no measured numbers) independently derived the same `by`/`Y`/`vy`
triples and named the same two rounding modes; no disagreement. One
consequence: the ± sign is applied before the drag and floor is not
symmetric, so a left- and right-facing launch of the same move are not exact
mirror images.

The staged pair is then consumed by the victim's ov6 state handler
`0x0215AF34`: at `0x0215AF98`–`0x0215AFC4` it copies X through `×100/100`
and Y through `×72/100` into the hit object `+0x10A/+0x10C`
(`0x02230D60+…`), and the state entry routine `0x0215BA40` (finisher) or
`0x0215B6A0` (each small hit) **adds** them into the fighter element's
per-frame impulse fields `+0x30/+0x32`. The arm9 integrator `0x02082E10`
adds `+0x2C/+0x30` into `vx = element+0x24` and `+0x2E/+0x32` into
`vy = element+0x26` (s16), then zeroes the impulse fields, applies the
`×(256−k)/256` drag from `+0x3C/+0x3D` (`k = 0x20` → the 7/8 of §1), adds
gravity to `vy`, and integrates `+0x0C/+0x10` (the position pair of §5).
The impulses therefore live for **less than one frame**, which is why no RAM
diff ever saw them. Kenshin X's finisher record is `type 6, kbX ±25, kbY 6`
(−3200·M·F raw and 6·(−158)·M·F·0.72·0.72 ≈ −4.9·10²·M·F raw before gravity);
its eight small hits are `type ≠ 6, kbX ±6` → the fixed ±768 of §4.3.

**The band multiplier is per move, not universal**
(`jus-projectiles-not-hp-tiered-pcee`, `hx25-*`, `hx26-*`). Momotaro X (beam,
eight hits) and Yusuke X (one 46-damage projectile) move Nami with identical
velocity at every HP band, including under 1/4. Which hit types read the
band is now partly answered: the launcher does, the grounded jab does not
(§4.5).

### 4.3 The scaling belongs to the launcher, not to hits generally

Grounded 7.00-damage pokes produce **identical pushback of 2.34–2.35 px/frame
on Nami, Franky and Luffy at every health level**. So weight and health scaling
apply to the launching special specifically, not to every connecting hit. This
was owner testimony first and is now confirmed from RAM. In code this is
the hit type byte: only `type == 6` reads the HP band table and the weight
gate bits (§4.2).

### 4.4 Measurement hazard: distance confounds fine comparisons

**Attacker–victim distance at the final hit shifts launch velocity by ~20%**,
which is larger than the gap between the competing health-term models. `m04`
and `m06` were identical in deck, victim, max HP, move and health at each hit
yet differed 22% on the first launch (14.3555 vs 17.5781). The move itself is
not the noise source — its 23-frame span and the victim's height at the final
drop are identical across matches.

Consequence: any experiment intended to resolve the health term must hold
distance fixed, which hand play cannot do. Two further hazards on record:

- A launch that stops advancing in X while Y keeps climbing means the victim is
  **cornered against a wall**, not that knockback changed.
- **Resetting a victim's HP does not necessarily reset the internal state the
  launcher reads.** `m04` is contaminated this way — its victim was grazed and
  then healed to full, and both its launches sit ~12–15% above the curve from
  uncontaminated matches.

### 4.5 Hitstun by hit type

The owner names four hitstun types. All four are measured with the scripted,
distance-fixed method (`scripts/emu/experiments/hitstun_sweep.py`, evidence
hitstun-2026-09-02,
`jus-hitstun-types-0nxs`). The broken-guard type became scriptable once the
in-match pause menu's COM設定 was set to ガード (states
`pc-kenshin-{luffy,nami,franky}-guard`, `jus_files/save_states/INDEX.md`).

| type | move | victim state (`char+0x78`) | hitstun timer (frames) | knockback | weight / HP scaling |
|---|---|---|---|---|---|
| launcher | Kenshin X | launched 0xC0 | 60 on the finisher, ~20 on each windup hit | §4.2 formula | HP band **and** weight (§4.1–4.2) |
| light jab | Kenshin B | **stays 0x22 (grounded)** | **20** | vx set to −448 raw (−1.75 px), ×7/8 decay | **neither** |
| air knockback | Jotaro neutral Y | launched 0x24→0x40, **34 frames** | 40 on the pop | vertical only, multi-hit then a −345 raw pop | **neither** (weight bits poked on Luffy: identical; `wb-*`, `jus-air-knockback-weight-3gm4`) |
| broken guard | Kenshin B into a full guard gauge | **stays 0x22** | **60** | same −448 raw as the clean jab | **neither** (Luffy, Nami, Franky identical) |

**The victim hitstun timer is `hit+0x114`** (s16, 8.8 fixed frames, in the
per-victim hit-result block at `0x02230D60` in the `pc-*` states; `jus-9lp.2.2`
closed). It is written on the hit frame and counts down 1.0 per frame to 0,
then reads −1.0 while idle. A blocked hit leaves it at −1.0. Two independent
checks that it is the control lock and not a cosmetic counter: a second hit
resets it (the break's 60 was still at 13 when the next jab landed and it
restarted at 20), and the ガード CPU re-guards exactly **4 frames after it
reaches 0** (24 frames after a jab, 64 after a break) — the only visible
"control resumes" signal a CPU victim gives. `hit+0x110` holds a second
per-hit value (24 on a jab, 80 on a break); see "How the hitstun value is
chosen" below.

**How the hitstun value is chosen (2026-09-02,
`jus-hitstun-formula-state-table-zgq3`; evidence
guardbreak-2026-09-02).**
Conditions: `pc-kenshin-luffy-guard`, `hs09` plan, `JUS_WATCH` on
`obj+0x110/+0x112/+0x115` and on the ColPrm block `M+0x40/+0x171/+0x174`;
static reads in `static-obj-0x110.md`, `static-hitstun-table.md`; neutral Codex
read `codex-0x110-second-opinion.txt` agrees with every store.

- The timer is written only through its whole-frame byte `obj+0x115` (there are
  no 16-bit stores to `+0x114`; the fraction stays 0). The hit-frame writer is
  ov6 `0x0215AD58` inside the per-frame fighter update `0x0215A978`:

  `hitstun = clamp( M[0x171] + 20 + T[obj+0x18], 16, 60 )` frames,

  where `M = [[obj+0x1a8]+0x10]` is the victim's ColPrm scratch block
  (`0x0220F494`), `M+0x171` is a byte that the hit handler adds chr/col
  `+7` into (signed, arm9 `0x02081300`-`0x02081308`) and adds `0x3C` to on a
  guard break (arm9 `0x02081754`, guard-sp.md §0.5); where it is zeroed is not
  read here, and `T = 0x02171488` is a signed-byte
  table indexed by **`obj+0x18`, the fighter's state code** (0 idle, 1 walk,
  3 guard, 4 jump start, 6 airborne, 8 hitstun, 9 attack, 13 landing; measured
  0 for Luffy, Nami and Franky alike, so it is not a character id).

  **Ground/air byte** (`jus-fighter-object-ar-plus-0x78-p7um`, from the
  Action Replay code audit, [AR-Codes-Raw.md](../research/AR-Codes-Raw.md)):
  the fighter object's ground/air byte reads `0x22` grounded, `0x20` on the
  launch frame, `0x00` airborne, `0x02` on the landing frame; a launched
  victim also read `0x24` then `0x40` (§4.5). This is the same `M+0x78`
  ColPrm-relative flags word the combat notes §2 and §8 discuss (rebuilt
  every frame by arm9 `0x0207F8DC`/`0x0207ECC0`/`0x0207ED08`, not latched).
  Four bits of it were pinned down statically while tracing the mobility
  passives (§6.4, `jus-utus`, 2026-09-12): bit `0x2` set at `0x0207ECB4`
  (matches the `0x22`/`0x20` grounded values above — this is also the bit
  §6.4's jump-budget grounded test reads); bit `0x4` set at `0x0207ED2C`
  with the wall clamp on the left (`vx` clamped `lt`, `obj+0xDD = +1` pushes
  right); bit `0x8` set at `0x0207ED88` (the `orr`; the store is `0x0207ED8C`), the mirror on the right; bit `0x400`
  set at `0x0207ED58` from a signed-byte table indexed by `r8` (a
  surface-type flag). The `0x4`/`0x8`/`0x400` readings are the write side
  only — what each means to a *reader* like the wall-jump gate is still
  inferred from control flow, not a direct data-path proof (§6.4). The full
  bit enum is otherwise open under
  `jus-state-code-enum-j39n`. The AR "Ground/Air" code dereferences a
  different root (`[[0x023D2A74]+0x10]`) that holds garbage in local mode;
  the status/jump/defense codes dereference `[0x02181B28]` once, which live
  reads `0x02228E80` = the P1 fighter object.

  **State-code enum, closed 2026-09-03, writer chain completed 2026-09-12**
  (`jus-state-code-enum-j39n`,
  runtime-report-2
  E5; writer chain: `jus-bg5t`,
  [state-code-handler-table-static.md](../research/findings/state-code-handler-table-static.md)).
  `obj+0x18` has exactly **two game writers**: ov6 `0x02159D1C`
  (`strb r1,[r4,#0x18]`) inside the generic state-machine commit routine
  `0x02159CC4`, and the reset routine `0x02159C90` (zeros it, along with
  `obj+0x19` and the rest of the handler/pending struct). The commit's
  source operand is the **pending byte `obj+0x19`** — the commit fires only
  when `obj+0x04` (current handler) differs from `obj+0x0C` (pending
  handler). `obj+0x19`'s only non-zero staging writer is `0x02159D34`,
  reached from one wrapper, `0x02157494`, at 34 sites (33 literal, one
  table-driven — see the full table above). Confirmed live on P1 Kenshin,
  the commit is the only *promotion* writer across three launches and ~25
  plans. Runtime-confirmed new codes: **2 = dash** (held the whole 12-frame
  dash burst, both directions), **5 = double-jump start** (exactly 1 frame on
  the second `A`), **7 = fast-fall** (impulse frame to landing frame, all
  three fast-fall kinds, now also static-anchored at `0x0215E104`), **10 =
  special/X** (GDB capture on all four Kenshin X hits reads
  `obj+0x18 = 0x0A`; this is why a victim hit while the attacker's special is
  active takes `20 + T[10] = 44`, superseding the static guess that 10 was
  launch-family; now also static-anchored via the table-driven site's index
  13–21). Codes **16, 21** remain static-only candidates (hard-landing/
  fast-fall, range-boundary KO/ring-out —
  static-state-codes.md),
  not yet exercised live; **27** likewise static-only (can't-act window) but
  is now also known to share the `M+0x3C` bit `0x20000000` write with 24
  (not `M+0x78` — an earlier static guess on that bit is withdrawn, see the
  full table above). **Codes 24 and 25 are now confirmed live**
  (`jus-p6jm`,
  runtime-report-8):
  an accidental KO (an HP poke that overflowed signed 16-bit and killed the
  victim mid-run) showed `obj+0x18` going 24 then 25 as the deck switched to
  the next character — the KO/switch path, not the falldown itself.

  **Code 23 is confirmed live as well** (measured; `jus-zmdb`, grading
  corrected 2026-09-26). It was graded static-only in the sentence above and in
  the table below on 2026-09-25, one day *after* the 2026-09-24 capture that
  shows it; the grade is withdrawn, not the capture. Both fighters in
  `push-2026-09-24/wall` read `obj+0x18 = 23` while airborne in a pit ring-out
  — 34 frames each on P1 (plans 796–829) and
  P2 (plans 844–877) in `wall/Y_x8/frames.jsonl`, 33 frames on P2 (plans
  844–876) in `wall/Y_x6/frames.jsonl` — each followed by one frame of 24 and
  then 25 (push-2026-09-24/RESULTS.md,
  "The wall"). On-floor versus off-floor is decided by `y == 172031`
  (671.996 px). `obj+0x18` lags the geometry: P1 leaves the floor at plan 723
  still reading 1, and only reads 6 at plan 725.

  **23 is the pit ring-out** (this corrects the earlier knockdown reading; the
  static trace is in C1-static.md).
  The first reading of this capture called 23 "falling off the left edge", and
  the static path agrees. Over the 34 frames of 23, `y` *grows*, and `y` is
  down-positive, so the fighter falls. P1 is at 205789 (803.86 px) on plan 795,
  then 206846 → 207911 on plans 796–797, with `vy` a steady `+1039…+1065`. The
  foot is over type-7 pit cells: `0x0207EE58-6C` sets `0x400000`, and
  `0x0215C360` sets state 0x17 with sfx `0x7a/0x02`. P2 in `Y_x6` falls further,
  to 240072 (937.8 px, 265.8 px **below** the floor row). `vx` is `0` for the
  whole run. On the last frame of 23 (plan 829 for P1, 877 for P2) the fighter
  is placed at the respawn: `x` goes to exactly **448.0 px** (P1 `43377 → 114688`)
  and **576.0 px** (P2 `47872 → 147456`), and `y` to the floor row 172031
  (671.996 px). The respawn x is fixed, not the body. So the sequence is: walk off
  the ledge (6, from plan 725) → pit ring-out (23, 34 ticks) → respawn placed on
  the last frame of 23 → 24 (1 tick) → 25, with the fighter back on the floor.

  **What 23 *means* is now graded for this capture:** the pit ring-out, as the
  static read in C1-static.md (Q1 and Q5) gives it. P1 has HP 0 on the first
  frame of 23 (plan 796), and P2 shows the same 34-tick state 23 on plans
  844–877. The right side of the pit is STATIC (mirror geometry). Note also that
  the 24→25 pair recorded above as "the KO/switch path" also follows a pit
  ring-out respawn here (24 for 1 tick, 25 for 42 ticks), so 24→25 is not
  specific to the KO/switch path.

  **State-code addendum, 2026-09-03** (`jus-kakashi-moveset-map-33lu`,
[characters/kakashi.md](characters/kakashi.md)): state **12** is confirmed as
the SELECT ultimate-action code (60 frames on Kakashi) and state **13** is
confirmed as the landing state — `air X` on Kakashi shows jump (6) → 13 → idle
(0) with no attack state, which is how a whiffed air special is told apart
from `air B`/`air Y` (attack state 9 before 13). This is the same 13 the state
table above already lists as "landing"; it is now confirmed on a second
character, not just Kenshin.

**Full state-code table: static install sites + runtime grade, 2026-09-12**
(`jus-bg5t`, static reads
[state-code-handler-table-static.md](../research/findings/state-code-handler-table-static.md);
cite that doc for every address below). **Grading axis:** a code is graded
RUNTIME when a cited live capture shows that code on `obj+0x18`; PLAUSIBLE
static when only a static install-site anchor exists; unanchored when
neither is true. `obj+0x18`/`obj+0x19` have exactly
two writers between them: the commit routine `0x02159CC4` (promotes pending
`obj+0x19` to active `obj+0x18` when `obj+0x04 != obj+0x0C`) and the reset
routine `0x02159C90` (zeros both). The pending byte's only non-zero **staging**
writer is `0x02159D34`, reached from a single wrapper `0x02157494` at 34
call sites in ov6; 33 pass the code as a literal `mov r1,#N`, one (`0x02159E64`)
reads it from a stride-12 byte table at `0x021712BC`/`0x021712C0`. This
anchors every code from 0 through 25, plus 27 — 26 is not, and nothing above
27 is. (Caveat: the 34-site count is a text grep over ARM-mode disassembly;
ov6 also has Thumb regions, so this is not a proof of exhaustiveness against
a hypothetical Thumb-mode caller.)

| code | grade | install site (containing handler) | entry condition | structural note |
|---|---|---|---|---|
| 0 idle | RUNTIME | `0x0215D398` (`0x0215D2E4`) | idle/landing dispatcher branch on `obj+0xDB` | shared with 13 |
| 1 walk | RUNTIME | `0x0215D750` (`0x0215D6F8`) | two dash/other gates both false | |
| 2 dash | RUNTIME | `0x0215D8E0` (`0x0215D860`) | `obj+0xD9 < obj+0xD8` | 12-frame dash-burst counter |
| 3 guard | RUNTIME | `0x0215EA04`/`0x0215EA70` (`0x0215E9A0`) | | one path also sets `obj+0x11A=6`; live: CPU under ガード reads `obj+0x18 = 3` (runtime-report-2 §(ii)) |
| 4 jump start | RUNTIME | `0x0215DB90` (`0x0215DB50`) | `bl 0x2159930`==0 and `obj+0x6C` bit `0x10` clear | live: A press to the impulse frame reads `obj+0x18 = 4` (runtime-report-2 §(ii)) |
| 5 double-jump start | RUNTIME | `0x0215E280`/`0x0215E2C0` (`0x0215E1D0`) | | one path bumps `obj+0xDC` jump-count (a wall jump bumps it a second time on the same commit frame at a different site — §6.4 has the two addresses) |
| 6 airborne | RUNTIME | `0x0215DC84`/`0x0215DF00` | | two sites, same code; live: every jump reads `obj+0x18 = 6` (runtime-report-2 §(ii)) |
| 7 fast-fall | RUNTIME | `0x0215E104` (`0x0215E0CC`) | `obj+0x6C & 0x12 == 0x12` | impulse frame to landing frame |
| 8 hitstun | RUNTIME | `0x0215AE10` (`0x0215A978`) | | per-frame hit-receive routine |
| 9 attack | RUNTIME | `0x02159E64` table, index 1–10 → `0x09` | move-class classifier arg1∈{0,1,2} | see input-class table below |
| 10 special/X | RUNTIME | `0x02159E64` table, index 13–22 → `0x0A` | same classifier | Kenshin X reads `0x0A` live |
| 11 (dream attack) | RUNTIME | `0x02159E64` table, index 12 → `0x0B` | same classifier | hotkey self-re-press, `jus-jh7d`; Momotaro re-pressing his own hotkey R reads `0x0B` live (state `pc-taikoubou-npc-jotaro-dark-tournament`, dream-attack RESULTS.md Plan B — leader Taikoubou has no hotkey) |
| 12 (SELECT ultimate) | RUNTIME | `0x02159E64` table, index 11 → `0x0C` | same classifier | Kakashi SELECT reads `0x0C` live |
| 13 landing | RUNTIME | `0x0215D37C` (`0x0215D2E4`) | idle/landing dispatcher, else branch | confirmed 2nd character (Kakashi) |
| 14 | PLAUSIBLE static | `0x0215DD2C` (`0x0215DCAC`) | `obj+0x1D8` function pointer nonzero, OR'd | tentative combo/attack-string advance |
| 15 | PLAUSIBLE static | `0x0215E49C` (`0x0215E470`) | ColPrm `M+0x40` bit `0x400` | shares `M+0x40` with `GROUND_ENTRY` |
| 16 | PLAUSIBLE static | `0x0215E588`/`0x0215E700`/`0x0215E7F0`/`0x0215E80C`/`0x0215E8EC` | several, incl. `obj+0x100+0xE7` byte | one site also sets `obj+0xCE=10` (invincibility) |
| 17 | PLAUSIBLE static | `0x0215B0AC` (`0x0215AF34`) | preceded by sibling-setter `mov r1,#0xB; bl 0x2157450` | |
| 18 | PLAUSIBLE static | `0x0215B108` (`0x0215AF34`) | | two unidentified helper calls precede |
| 19 | PLAUSIBLE static | `0x0215BF0C` (`0x0215BEA8`) | preceded by sibling-setter `mov r1,#0xE; bl 0x2157450` | |
| 20 | PLAUSIBLE static | `0x0215AB98` (`0x0215A978`) | | clears staged knockback vx/vy first; hypothesis, not confirmed |
| 21 | PLAUSIBLE static | `0x0215C2CC` (`0x0215C278`) | | same fn as the `{8,0x17,0x18}` filter chain; groups with 8/23/24 |
| 22 | PLAUSIBLE static | `0x0215BFD4` (`0x0215BF70`) | early-return unless `obj+0x18 ∉ {8,0x17,0x18}` | preceded by sibling-setter `mov r1,#7`; writes `obj+0x119=0x78` after; no live capture yet |
| 23 | RUNTIME | `0x0215C444`/`0x0215C45C` (`0x0215C360`) | global byte `+0xC8 != 0` selects handler pair | code stable, only handler varies; live: both slots read `obj+0x18 = 23` airborne in the pit ring-out fall, x repositioned to the respawn 448.0/576.0 px on the last frame of 23 (plans 796–829 / 844–877 of `wall/Y_x8`, push-2026-09-24/RESULTS.md); **is** the pit ring-out (static path `0x0207EE58-6C` → `0x0215C360`, C1-static.md) |
| 24 | RUNTIME | `0x0215C5B8`/`0x0215C6F0`/`0x0215C80C` (`0x0215C488`) | | also sets `M+0x3C` bit `0x20000000` (not `M+0x78` — first-pass claim withdrawn); live: confirmed by the accidental-KO capture below, `obj+0x18` went 24 then 25 (runtime-report-8) |
| 25 | RUNTIME | `0x0215CACC` (`0x0215CA44`) | | 24→25 confirmed live on a real KO, deck-switch path |
| 26 | **unanchored** | none found | — | never observed live or statically, by literal, table, or branch gate |
| 27 | PLAUSIBLE static | `0x0215CD74` (`0x0215CD2C`) | preceded by sibling-setter `mov r1,#0xF; bl 0x2157450` | shares `M+0x3C` bit `0x20000000` write with 24 |
| >27 | **unanchored** | none found | — | hitstun table `0x02171488` runs to index 59, but no `obj+0x19` write ties to any index >27 |

**Input-class table for codes 9/10/11/12** (the one table-driven install
site, `0x02159E64` inside `0x02159D7C`): the table index `r4` comes from a
function-pointer call, `ldr r1,[r2, arg1<<2]; blx r1` at `0x02159D94-9C`
off the pointer table `0x02172178`, where `arg1` (this doc's "input class")
is `0x02159D7C`'s own first argument, and is one of exactly `{0, 1, 2}`
across all 11 call sites of `0x02159D7C`, i.e. `r4` is indexed by the value
returned by one of three classifier functions, not an open-ended slot/move
id. **Table base resolved:** the disassembly gives two literals — the
record base `0x021712BC` at `0x02159E08` (used by the word load at `0x02159E14`, OR'd into `obj+0xC4`, which is the move's **cancel mask**, not an unrelated word ([cancel-windows-static-2026-09-25.md](../research/findings/cancel-windows-static-2026-09-25.md) §2; live: C4 = `0x2` after a Kakashi neutral B and `0x3FE` after air B, cancel-live-checks-2026-09-25)) and `0x021712C0` at `0x02159E48`,
used by the `ldrsb` at `0x02159E50` that actually reads the install-code
byte. `0x021712C0` is `0x021712BC + 4`: the record base is `0x021712BC`,
stride 12, and the install-code byte sits at **record+4**, not record+0 (same bytes, other framing: the anim word is read from `0x021712B8` at `0x02159F4C`, so the record can also be read as starting at `0x021712B8`, with the mask at +4 and the install byte at +8) —
there is no off-by-4, and no discrepancy between the two literals. The
table has 23 records (index 0–22, `0x021712BC`–`0x021713C8`); **index 0 is
a dead sentinel** (`cmp r4,#0; beq` at `0x02159DBC-C0` returns before the
table lookup is reached for index 0), so no call site ever selects it live.
The last `0x0a` byte is at `0x021713C8` (index 22):

| table index (`r4`) | byte at record+4 (install code) |
|---|---|
| 0 | dead sentinel, never reached |
| 1–10 | `0x09` (9) |
| 11 | `0x0C` (12) |
| 12 | `0x0B` (11) |
| 13–22 | `0x0A` (10) |
| ≥23 | zero, not a live entry |

**Runtime-confirmed, full table** (`jus-hitstun-table-rows-runtime-7oxa`,
  runtime-report-1):
  `T = [0, 8, 8, 0, 8, 8, 0, 8, 0, 16, 24, 24, 16, 8, 8, 0]` for states 0–15.
  Ten of the sixteen rows were confirmed against a live hitstun read: states
  0, 1, 2 and 9 occurred naturally (COM set to 戦う and left to fight — idle
  20, walk 28, state 2 28, attack 36) and state 10 occurred naturally once
  (44); states 3, 4, 6, 12, 13, 15 were confirmed by poking `obj+0x18` while
  the victim stood idle and then landing a real jab (every poked run carried
  the real 336-raw HP drop on the victim's record as its positive control, so
  these are real unblocked hits, not synthetic writes). States 5, 7, 8, 11,
  14 are still static-only (§static-state-codes.md candidates below). A jab
  on a standing victim: `0 + 20 + 0 = 20`. A break: `60 + 20 + 0 = 80 → 60`
  (the clamp ceiling). The per-frame countdown is ov6 `0x0215B508`; the idle
  −1.0 is that decrement running past 0. **A second hit resets the timer, it
  does not add**: Kenshin X's 2–4-frame-apart hits go 20 → 19 → 18 → 20 (not
  38); the launcher finisher then overrides 18 → 60 (not 78) — see "the
  launched-state handler" below.
- **Launched victims get a second write the same frame** (run 3,
  `runtime-report-3.md`: 4 Jotaro Y pops, 10 Kenshin X hits). The formula
  store lands 20 first; then the launched-state entry handler adds to it
  through ov6 `0x0215B4C4` (`byte += r1`, clamp 16..60; store `0x0215B4D0`).
  The knockback-pop handler (continuation `0x0215B910`, start handler `0x0215B870`, call at `0x0215B8F8`) passes the
  current byte, so **hitstun doubles: 20 → 40** (Codex neutral read agrees,
  `codex-launch-second-opinion.txt`). The launcher handler (call at
  `0x0215BA98`) passes twice the current byte, so **20 → 60** (Codex agrees, `codex-launchC-second-opinion.txt`). Grounded hits
  (jab, windup hits, guard break) never reach these handlers. So the three
  measured values are one base with a ×1 / ×2 / ×3 state multiplier, clamped
  at 60. `M+0x171` stayed 0 on every non-break hit (14 of 14), so the `+7`
  move-data byte is 0 for these moves too; whether any move carries a nonzero
  `+7` is open (`jus-air-knockback-move-universality-8j0j`).
- **While airborne the timer counts down; on landing it stops** (40 → 19.0
  after the Jotaro pop, 60 → 35.0 after the Kenshin X launch, both frozen at the
  landing frame). Recovery after landing is then `obj+0x110`, which **does count
  down** 24 → 0 from about two frames after landing (`0x0215B550`, then a
  `0xFFFF` write and re-zero). That is the hitstun README's "24→0" note; the
  guard-break runs never saw it because the victim never left the ground. So
  `+0x110` is the **landing-recovery timer** (24 frames = the clamp floor when
  `M[0x171]` is 0) and `+0x115` the in-flight / grounded stun.
- `obj+0x110` = `clamp( M[0x171] + 20, 24, 180 )`, written by the same routine
  through the setter ov6 `0x0215B520` (store `0x0215B534`): 24 on a jab, 80 on
  a break. It is written only on unblocked hit frames, never on blocked hits.
  It did not count down in the guard-break runs but does after a landing (next
  bullets): it is the landing-recovery timer, seeded from the same base as the
  stun.
- `obj+0x112` = the hit's damage in whole units (`0x0215ACDC`, `r4 >> 6`), 5 on
  every Kenshin B against Luffy; cleared to 0 the frame the timer reaches −1.0.
- Open (`jus-m171-hitstun-base-source-fgpn`): the non-break base. Static
  (`static-arm9-hit-receive.md`): arm9 `0x02081300`–`0x02081308` does
  `M[0x171] += moveData[+7]` (signed byte off the hitbox's move-data record
  `[r6+0x10]`) on every hit, so Jotaro Y's 40 and Kenshin X's 60 should be a
  `+7` of 20 and ≥ 40 there; only the jab (0) and break (60) were watched.
  `M+0x174` was 0 throughout.

**How the reaction handler is chosen (runtime-confirmed,
`jus-air-knockback-move-universality-8j0j`,
runtime-report-1).**
The victim's per-frame reaction handler is `obj+0xFC`, a function pointer read
every frame at ov6 `0x0215B060`. It is set by a three-copy chain from the
attacker's move data:

1. Arm9 `0x020815F8` max-latches `moveData[+1]` (the hit-type byte, `u8`) into
   `M+0x16C` (`u16`, cleared to 0 every frame by `0x02051864`) — on a frame
   where several hits land, the largest `moveData[+1]` wins.
2. Ov6 `0x0215AAAC` copies `M+0x16C` into `obj+0x100`.
3. Ov6 `0x0215B008`, gated on `M+0x28 == 0` (checked at `0x0215AFD0-4`), sets
   `obj+0xFC = *(u32*)(0x021721A0 + 4·(u16)obj[0x100])` — a table lookup with
   `0x021721A0` a +4-word bias on the table §4.6 originally documented at
   `0x02172190`. If `M+0x28 != 0` instead, the fixed handler `0x0215B568` is
   installed and the victim element's `vx`/`vy` are zeroed; `M+0x28` read 0 on
   every measured hit, so that arm has never been exercised.

Measured `moveData[+1]` values: 1, 2 and 7 all route to the grounded handler
(Kenshin B jab, Kenshin X windup, Jotaro Y windup); **5** routes to the
vertical pop (hitstun ×2 — the Jotaro neutral Y finisher); **6** routes to the
launcher (hitstun ×3 — the Kenshin X finisher). Ids 0, 3, 4, 8, ≥9 are
arithmetic extrapolations of the same table, not measured.
**Reaction 4 = falldown, measured 2026-09-03** (`jus-p6jm`,
runtime-report-8,
Codex-agreed): the victim object's signed 16-bit **combo-damage accumulator
`obj+0x10E`** gets `+((damage_raw << 12) asr 16)` = 4 × displayed damage at
ov6 `0x0215AD70` (inside the hit-receive routine `0x0215A978`), clamped to
600 at `0x0215AD80`; it decays −2/frame at `0x0215AE6C`/`0x0215AE70`, floor
0, skipped while `obj+0x18 == 8`. At `0x0215AF5C` (`cmp acc, #0x258`) a hit
reaching ≥ 600 zeroes it and rewrites `obj+0x100` through table
`0x02171478` = `[4,4,4,4,4,6,6,4,4,-1×7]` (the 16 bytes just before the
hitstun table `T` at `0x02171488`). Reaction 4's table entry is the start handler `0x0215B7CC`, which
stores the continuation `0x0215B818` in `obj+0xFC` (`jus-reaction-table-start-handlers-8l0w`;
chain `0x0215B84C → 0x0215BC44 → 0x0215BC8C`): state 8 for 51 frames,
hitstun byte 6, and on the last frame ov6 `0x0215BD00` (in handler `0x0215BC8C`) writes the
**invincibility timer `obj+0xCE` = 40** (`jus-getup-invuln-store-site-gm12`; a second immediate-0x28 store to `obj+0xCE`, at `0x0215CCCC`, is in
`0x0215CCB0`, the exit callback of state 25 (KO/ring-out respawn), installed by the call at `0x0215CACC`.
It grants the respawn's 40 and is not on this path. `runtime-report-8-falldown.md` named that site
before the handler was traced); hits land again at frame 131.
Threshold is max-HP independent and damage-based (3.0 → +12, 8.0 → +32).
Falsification: poke `obj+0x10E` to 682 and jab (compare 596, normal); 694
(compare 608, falldown). Also: `obj+0xD7` is a combo *hit* counter (ov6
`0x0215AC90`–`0x0215ACA8`, +1 if already in state 8 else reset) with no
consumer found; a KO showed state codes **24 then 25** (deck-switch path)
live; max HP lives two bytes below current HP (`0x021DF7EE` for the Jotaro
record), capped at `0x4000` = 256.0, and HP is signed. No natural falldown
was driven: a jab loop nets −34 per cycle, Kakashi's Y loop +48, so a real
gapless ~150-damage combo is needed to see it unpoked.

**Handler pointer values, settled 2026-09-03** (run 7, 48 latched hits on 7
attackers incl. the Kenshin X / Jotaro up+X controls, `jus-launcher-move-spot-check-hiyh`,
runtime-report-7):
the value stored in `obj+0xFC` is **`0x0215B720` for types 1/2/7,
`0x0215B910` for type 5, `0x0215BAB8` for type 6**, uniformly. Correction
(`jus-reaction-table-start-handlers-8l0w`): the static table `0x021721A0` holds the
**start handlers** `0x0215B6A0`/`72C`/`7CC`/`870`/`A40`/`68C`/`568`. Each stores its
continuation into `obj+0xFC` and returns, and `0x0215B720`/`818`/`910`/`AB8` are those
continuations. So `0x0215B6A0` / `0x0215B870` / `0x0215BA40` are the table's pointer
values, and the runtime reads are their continuations (the pop's hitstun call at
`0x0215B8F8` still stands). An earlier version of this note said the static
addresses were not the table's pointer values; that was wrong.

Table contents (`jus-reaction-table-start-handlers-8l0w`):

- indices 0, 1, 2 and 7 hold `0x0215B6A0`; 3 holds `0x0215B72C`, 4 holds `0x0215B7CC`, 5 holds `0x0215B870`,
  6 holds `0x0215BA40`, 8 holds `0x0215B68C`, and 9-15 hold `0x0215B568`.
- reaction 3 installs `0x0215B784` (store at `0x0215B778`); reactions 8 and 9-15 install `0x0215B648`
  (stores at `0x0215B690` and `0x0215B61C`).

`obj+0x11E` is a **different field** (a signed byte read only at
`0x0215B01C`/`0x0215B044`) — it read 0 on every hit in this and the prior
run and is not the selector, despite superficially similar wiring.

**Pops and launchers on seven more characters, 2026-09-03**
(`jus-knockback-pop-spot-check-m4uy`, `jus-launcher-move-spot-check-hiyh`,
runtime-report-7).
72 `moveset_map.py` runs on Sasuke, Raoh, Muhyo, Eve, Yoh White Swan, Kenshin
and Jotaro, all against the same Jotaro/Luffy victims run 1's controls used.

- **All four measured pops (Sasuke `up+Y` hit 2, Raoh `up+Y` hit 10, Muhyo
  `forward+Y`, Jotaro `Y` control) are hit type 5, handler `0x0215B910`,
  hitstun 40, and read 0 on `M+0x171`.** Poking the victim to band-3 HP
  (<1/4 max) left staged `kb`, `vy`, hitstun, damage and airborne frames
  byte-identical to the full-HP run on both Sasuke and Raoh — **pops do not
  read the HP band** (the `type == 6` gate of §4.3 holds on real pops, not
  just on poked bits).
- **All four measured launchers (Sasuke `X`/`up+X`, Eve `X`, Yoh White Swan
  `X`, Kenshin `up+X`, plus the Kenshin `X`/Jotaro `up+X` controls) are hit
  type 6, handler `0x0215BAB8`, hitstun 60.** The §4.2 HP-band formula
  (`frac >> 6` table, `by = ASR(ASR(s·kbY·−158,8)·223,8)`) was bracketed to
  the HP unit on three more characters/three more max-HP values (Sasuke `X`
  on Jotaro max 160, Kenshin `up+X` on Luffy max 152, Eve `X` on Jotaro max
  160): every multiplier is exactly ×1/×1.5/×2/×3 on both axes, with the
  expected floor on the ×1.5 and ×3 rows. No windup hit inside any of these
  launchers reads the band — the multiplier attaches to the type-6 hit only,
  never to the move as a whole.
- **Muhyo `forward+Y`'s pop direction is the sign of `M+0x148` alone, chosen
  by which side of the *victim* the summoned hitbox emerges on — not by the
  attacker's own facing or position.** The monster anchor spawns 64.44 px in
  front of the attacker; landing past the victim throws the victim back
  toward the attacker (`kbX` positive), landing short of the victim throws
  them away (`kbX` negative). Magnitude, `kbY`, damage, hitstun and arc are
  identical in both signs — only the sign changes. This is §4.6's "x sign
  chosen by relative position" measured against a summoned hitbox rather than
  the attacker's body. Holding the input (30 or 60 frames) turns the anchor
  into a traveller that adds ~60 px of reach and changes nothing else about
  the hit; the extra travel saturates between 30 and 60 held frames.
- **The status dispatch node is `obj+0x94`** (slot 1 of the `battleObj+0x7C +
  slot*0x18` pair guard-sp.md §1.5 already names): `+0x0C` is the live status
  id, `+0x0E` the frames remaining, counting down 1/frame to 0 and clearing
  the node. Measured ids: **28** = blind, 180 frames (Yoh White Swan `X`),
  **31** = Sasuke `X` (shock), **30** = Sasuke `up+X` and Jotaro `up+X`
  (the same id from two different attackers, so 30 is a shared status, not
  Sasuke-specific). `X+0x172` is 0 on every staged status seen; `X+0x173` is
  the id stored negated (`256 − byte`), matching guard-sp.md §1.5's Route B.
- **This deck's Jotaro takes 0.75× damage from every special measured
  against it** (Sasuke `X`/`up+X`, Eve `X`, Yoh White Swan `X` — four
  attackers, four exact ×0.75 readings against the guide's numbers, while
  every normal against the same Jotaro is exact). Reads like the same *Take
  less damage from Special Attacks* passive §4.1 already notes on Raoh, but
  nothing here poked Jotaro's ability list to prove it — open, not yet a
  spec fact (`jus-8ur4`).
- **Hazard carried forward: `M+0x16C` is cleared every frame** (arm9
  `0x02051864`), so a single-frame hitbox can be missed by a once-per-frame
  sample even though the hit landed — cross-check `hp_drops`, never trust an
  empty `M+0x16C` alone to call a run a whiff (two of Eve's/Jotaro's `B`s in
  this run read 0 on `M+0x16C` on every logged frame despite landing).

~~Open discrepancy, 2026-09-03: Kakashi's measured `obj+0xFC` values
`0x0215B720` / `0x0215B910` vs this section's `0x0215B6A0` / `0x0215B870`~~
— **resolved by `jus-reaction-table-start-handlers-8l0w`: the table holds the start handlers, and the
measured values are their continuations.**

**Light jab (Kenshin B).** The hit sets the victim's horizontal velocity to
**−448 raw = −1.75 px/frame** and it decays by exactly ×7/8 (measured 0.875,
0.875, 0.8746, 0.8733 — the drift is integer truncation, §1). The state byte
never leaves 0x22, so a standing victim shows no launched state; the timer
says the victim is locked for 20 frames. The −448 is **identical** for Nami
(light), Franky (heavy) and Luffy, and identical at full / 76 / 30 HP, so the
jab carries no weight factor and no HP tier — the §4.3 grounded-poke result,
now on a real attack. The damage split (7.0 Nami/Franky, 5.25 Luffy) is
entirely Luffy's blunt-resistance passive (×0.75, [damage.md](damage.md) §5;
on-disk ability 9 confirmed, `jus-luffy-blunt-resist-source-92l3`), not knockback.

**Air knockback (Jotaro neutral Y).** The victim enters the launched state
(`char+0x78` = 0x24 then 0x40) and stays non-grounded for **34 frames** before
returning to 0x22. Motion is vertical only — Y moves, X is pinned. The move is
a multi-hit (three −150/−104/−59 windup pulses, then a −345 raw pop that arcs
up and falls back); the timer is set to 40 on the pop. Whether air knockback
carries the weight factor is settled: **it does not.** With Luffy's gate word
poked to lightweight (bit 15) or heavyweight (bit 7) the pop, its windup
pulses, damage, hitstun and the 34 airborne frames were byte-identical to the
unpoked run, while the same poke scaled a Kenshin X launch ×1.5 on both axes
in the same session (`weight-hunt-2026-09-01c/wb-*`,
`runtime-report-weight-bits.md`; `jus-air-knockback-weight-3gm4`,
`jus-untiered-hit-body-factor-t0m7`). The jab was likewise unchanged. So the
body factor is 1 on every untiered hit, exactly as §4.6's `type == 6` gate
predicts. `M+0x44` is not rebuilt per frame (one value per run).

**Broken guard (Kenshin B, guard gauge full).** Measured on Luffy, Nami and
Franky (`hs09`, `hs11`, `hs12`; gauge mechanics in
[guard-sp.md](guard-sp.md) §0.5, `jus-guard-gauge-found-a55l`). A blocked jab
does no HP damage, pushes the victim back **−224 raw** (exactly half the clean
jab) and adds the jab's whole-unit damage to the guard gauge. The jab that
arrives with the gauge already at its max (65) **breaks**: it lands as a normal
hit (full damage, −448 raw pushback, state byte still 0x22) but with a
**60-frame** hitstun timer, three times the jab's 20, and the guard flag drops.
The same sprite as the jab hitstun, held three times longer — exactly the
owner's description. Knockback and stun length were identical on the light,
standard and heavy body, so the break carries no weight term. Poke-proven:
gauge poked to 61 or 64 then hit → clamps to 65, blocks; poked to 65 then hit
→ break (`hs11-thr*`).

### 4.6 Where the knockback numbers come from (static, 2026-09-02)

`jus-air-knockback-move-universality-8j0j` (open: the per-move table and the
ov6 state selection are still being filled). Static reading of the arm9
hit-event processor `0x02080F14`, region `0x020817E8`–`0x02081978`
(guardbreak-2026-09-02
`static-knockback-fields.md`; neutral Codex read
`codex-knockback-second-opinion.txt` agrees on every stage). Runtime
anchors: the §4.2 formula and the §4.1 weight bits were measured live; the
field offsets and the extra stages below are static only.

- **One pipeline for every hit.** Two signed move-data bytes, `kbX =
  moveData[+0xC]` and `kbY = moveData[+0xD]`, give
  `x = (kbX << 7) · F >> 8` and `y = (kbY · −158) · F >> 8`; `y` is then
  scaled `×223/256` and both are accumulated into the staged pair
  `M+0x148` / `M+0x14A` (§4.2's staging; **correction 2026-09-03**: this was
  previously written as `M+0xA4`/`M+0xA6`, which is wrong — `jus-first-frame-vertical-rounding-hmfg`,
  runtime-report-2
  E2. Ov6 `0x0215AF98`/`0x0215AF9C` read `[(M+0x100)+0x48]`/`+0x4A`, and a live
  `JUS_WATCH` on `M+0xA4` never fired on any hit; §4.2's own pseudo-code
  already said `scratch+0x148/0x14A` and was right). There is **no branch for a "jab",
  "pop" or "launcher" shape**: a jab is `kbY = 0`, the Jotaro pop is
  `kbX = 0`.
- **`moveData[+1] == 6` is the launcher gate.** Only then is `F` the HP-band
  table (`{0x300, 0x200, 0x180, 0x100, 0x100}`, index `M+0xCA >> 6`) and only
  then do the weight bits apply (`M+0x44 & 0x80` → −½, `& 0x8000` → +½,
  sequential). Otherwise `F = 0x100`. This is §4.1–4.3 at instruction level;
  Kenshin X's record (`kbX 25, kbY 6, type 6`) reproduces the measured
  launch.
- Stages not yet seen live: a doubling of both components when a stack flag
  is set (`0x02081818`), zeroing when the victim record's `+0x14` has bit
  `0x01000000`, a fixed override to `(0x300, −0x500)` when victim `+0x14` bit
  `0x04000000` and attacker `+0x14 & 0x700` are both set, and the `x` sign
  chosen by relative position or a facing helper (`0x0206CF28`).
- **Same-frame accumulation into `M+0x148` is refuted live** (`jus-idiy`,
  2026-09-12, trio Check B RESULTS): 20 hits
  captured across Kakashi and two controls, every one showing exactly one
  `HITPROC` call and one store to `M+0x148`/`M+0x14A` per frame
  (`kbx_stores_prev`/`kby_stores_prev` never exceeded 1). Every store's
  `new_val` matched `kbX*128` exactly, but `M` (the multiplier) was `0x100`
  on every hit captured, so this run does not by itself distinguish "the
  shortcut holds for any `M`" from "the shortcut holds when `M == 0x100`."
  The discrepancy the GAPS row below described was **not** same-frame
  accumulation; it was a question of **which record the engine reads** —
  three of four non-mashed `(kbX,kbY)` pairs measured on Kakashi matched no
  record in `na_b_05.bin`. **Resolved 2026-09-12 (`jus-lxyt`,
  [knockback-record-pointer-per-hit.md](../research/findings/knockback-record-pointer-per-hit.md)):**
  a live pointer trace found every one of those pairs byte-identical to a
  record in `na_b_04.bin` — the file `chr_b-Complete-Mapping.md` wrongly
  attributed to `chr_b` 22 (Sakura) instead of Kakashi's `chr_b` 23. Wrong
  file, not a missing record or a second engine path; see
  [characters/kakashi.md](characters/kakashi.md).
- The **launched-state entry** (which ov6 handler runs, hence ×1/×2/×3
  hitstun, §4.5) is runtime-confirmed — see "How the reaction handler is
  chosen" in §4.5. The type byte does double duty: it is both the reaction-id
  that picks the grounded/pop/launcher handler and (via `moveData[+1] == 6`)
  the gate for the HP-band table and weight bits above.
- Export caveat: the `*_collision.json` field names (`width`/`height`/
  `knockback`/`projectileId`) were never checked against a consumer; bytes
  `+0xC`/`+0xD` are knockback, not geometry. `moveData[+7]` is 0 in all 156
  sampled records. **Static-only correction**
  (`jus-hitbox-record-selection-u3ig`,
  static-hitbox-record-selection.md):
  record bytes `+8..+0xB` are one 32-bit property bitmask read as a whole
  word (`ldr r7,[r7,#8]`), not separate `offsetX`/`offsetY`/`positionFlags`
  fields as the exported JSON implies — no consumer reads them as split
  signed positions.
- **Horizontal knockback open note, 2026-09-03** (`jus-kakashi-moveset-map-33lu`)
  reported the horizontal shortcut `raw_x/128 == record +0xC` did **not**
  consistently hold on Kakashi. **Resolved 2026-09-12 (`jus-lxyt`,
  [knockback-record-pointer-per-hit.md](../research/findings/knockback-record-pointer-per-hit.md)):**
  the mismatch was the same wrong-file bug as the note above, not a break in
  the shortcut — `raw_x/128 == record +0xC` holds bit-for-bit once compared
  against Kakashi's real file (`na_b_04.bin`); see
  [characters/kakashi.md](characters/kakashi.md).

## 5. Supporting runtime structure

Established while measuring the above, useful to any reimplementer reading the
original's RAM:

- The position array holds two coordinate pairs 0x40 apart, P1 then opponent,
  each duplicated at +8. The **single opponent pair follows the *active*
  opponent**, so an arc spanning a character switch belongs to two bodies.
- **`pos+0x3C` is a two-valued active-opponent identity word**, flipping one
  frame after each switch (19 of 19 switches in `m03`); constant in a
  single-victim match.
- **`rec+0x24` of the deck HP record is a live active flag** (`03` active,
  `00` benched). Every HP drop lands on the flagged record. The deck HP record
  is the 0x50-byte per-deck-character record at `0x021DF1D4 + 0x50·i` (player)
  and `+0x61C` (opponent) in these sessions, the same struct
  [HP-And-Damage-Runtime-Findings.md](../research/HP-And-Damage-Runtime-Findings.md)
  §1 maps around HP; record 0 is the deck leader, not necessarily the active
  fighter (`jus-slot-name-collision-agh5`).
  **Correction, 2026-09-03** (`jus-e2w4`,
  runtime-report-4-lr-switch-taikoubou.md
  §2): on a hotkey-switch deck, `+0x24` (u16, low byte) is an **action code**
  (`0x03` while attacking, `0x11`/`0x13` mid-move), not a clean active flag —
  it moves during ordinary play, not only on a switch. The bit that is a
  clean active/benched flag is **bit 0 of `+0x25`**, confirmed across all
  eleven `pc-*-npc-jotaro-dark-tournament` states in
  runtime-report-5-states.md
  §2. Test `+0x25 & 1`, not the `+0x24` word.
- **Victim x is `0x0220C0B4`**, the `+0x40` partner of the P1 x at
  `0x0220C074` (`jus-e2w4`,
  runtime-report-3-lr-switch.md
  §5b) — the same `+0x40` stride the element pair `0x0220C068`/`0x0220C0A8`
  above uses.
- **The victim object address is per-deck, not a constant.** The fighter
  table at `0x021DEB3C` holds exactly two live pointers; the first is P1's
  object and is stable across states, but the second (the victim/opponent
  object) differs per deck — e.g. `0x02230D60`, `0x02230E00`, `0x0224EF00`,
  `0x0222CFE0`, `0x022301C0` were all seen across the decks in
  runtime-report-3
  §5b and
  runtime-report-4
  §5. Resolve the victim object from `0x021DEB3C + 4` for every new state;
  never hard-code a previously-seen address.
- **Benched characters regenerate +1 raw HP per frame**, which contaminates any
  "damage taken" figure computed as start-minus-current.
- Healing a character back to full runs at **+128 raw (2.00 displayed) per
  frame**, a distinct mechanism from benched regen.
- `rec+0x03` is the chr_b `charId`; `rec+0x04..+0x07` is the chr_b flags word
  with zero bytes stripped, i.e. the ability-ID list. Neither is a body stat.
- Training mode has **no clock** — the battle timer field reads a constant 255.
- **Real (non-training) matches do have a clock: 144 frames per displayed
  `TIME` unit in versus rules (~2.41 s at the DS's ~59.83 Hz), `CROSS_CONFIRMED`.**
  ov1's versus-rule conversion `time_limit_frames = (じかん + 1) * 144 - 1`
  agrees end to end with `0x020AFEAC` = 4463 measured at じかん 30
  ([Battle-Engine-Map.md](../research/Battle-Engine-Map.md) rule/match
  settings; `jus-1g6`, `jus-6fo`). A follow-up session's three independent
  screenshot trials bracket the period to 137.3–150 frames/unit (both ends
  exclusive), containing 144 and excluding both 60 (じかん-as-seconds) and
  exactly 150 (`jus-uvs`, `jus-timed-match-timer-units-2jyu`). `じかん` is a
  **whole-match** frame budget (4463 frames at じかん 30, battle-object
  creation to the result screen), not a per-round limit; mission rules use
  `じかん * 60` instead. The backing RAM address `root+0x10` (`root` per
  `p166`; seeded from `0x020AFEAC`) and the decrement at ov6 `0x0214F9E0`
  are identified below, though whether the counter stalls during KO/cut-in
  windows is still untested. Full method, raw screenshots, and the
  falsification conditions: [match-timer-units.md](../research/findings/match-timer-units.md)
  (`jus-timed-match-timer-units-2jyu`).
- **`bin/rulemess.bin` is a 22-entry rule-mode *text* table (three self-relative
  Shift-JIS string pointers + one classifier int per 16-byte record), not a numeric
  settings-preset table** — it has no time-limit-value, round/stock-count, HP, or SP
  fields, and neither does the rule-select RAM struct at `0x020AFE90`. The classifier
  int (`0`/`1`/`2`) selects which of the two time-limit-to-frames formulas above
  applies, `CONFIRMED_STATIC`. See
  [match-presets-and-timeout-static.md](../research/findings/match-presets-and-timeout-static.md)
  (`jus-l77m`).
- **The match countdown's decrement instruction is located: `[root+0x10] -= 1`,
  once per rendered frame**, at ov6 `0x0214F9E0`-`0x0214F9E4`, inside a function
  (`0x0214F998`) tail-called from nine mode handlers — modes 0-7 and 21
  (`0x0214FADE`, `0x0214FC28`, `0x0214FDEE`, `0x0214FEE8`, `0x021500D0`,
  `0x0215025A`, `0x0215037E`, `0x021503D4`, `0x02150C86`) — including the
  point-battle (mode 0) per-tick handler `0x0214FA78`, the same address the
  runtime loop measured at `root+0x000` for mode 0
  ([p166-per-mode-handler-table.md](../research/findings/p166-per-mode-handler-table.md),
  `jus-hsc`). `CONFIRMED_STATIC`. The same function
  fires threshold events at `1440` and `720` frames remaining (warning cues,
  `[unverified]` as to their exact effect) and returns a "final unit" flag once the
  counter drops below `144`. **No winner-selection comparison is gated on expiry in
  the countdown function or the mode-0 tick handler; the expiry transition and
  match-end callback are traced** — via a trampoline at `0x0214F948` into the
  per-frame state function `0x0214DBCC`, which on expiry installs the default
  handler, invokes the match-end callback `0x0214DDBC` (iterates player objects,
  clears per-player state, re-fires an event, chains onward), and separately picks
  the first player whose `+0x4C` "beats" counter is zero and records that index at
  `0x02171AA0`. The per-tick handler's own all-pairs score comparison runs
  unconditionally every frame, not gated on the counter reaching zero, and none of
  the traced chain was found comparing two players' HP or score at expiry, so
  whether a tie at time-out resolves as a draw, sudden-death, or a default-winner
  tiebreak remains `[unverified]`; a live run poking equal HP at time-out is needed
  to settle it. See
  [match-presets-and-timeout-static.md](../research/findings/match-presets-and-timeout-static.md)
  (`jus-l77m`).
- **Live (`jus-l77m`, 2026-09-12), observed once, point mode, じかん 30, Goku vs
  CPU Luffy: at time-out no side is declared winner on remaining HP; the match
  continues in a further timed round (timer reseeded to the full budget; owner term
  "sudden death") and if that round also expires undecided the result screen marks
  both sides WINNER at placement 1 with 0 points (a draw).** HP at the expiry frame
  is unmeasured — no HP watch was set at the expiry instruction (`0x0214DD36`); the
  `EXPIRYTEST` breakpoint prints only `r0`. Round-start HP reset was seen once at 50%
  of each side's own max HP and once at full max HP (a genuine contradiction in this
  session's own data, not a settled rule); HP-based tiebreak is unobserved, not ruled
  out. A clean expiry (no KO in the preceding frames) calls `0x0215911C` for **both**
  players symmetrically (`(player, 1)` then `(player, 0)` each, fighter-table order).
  `0x0215911C(obj, r1)`'s `r1` is a **slot index** into `obj+0x7C + r1*0x18`
  ([Battle-Engine-Map.md](../research/Battle-Engine-Map.md) names this field `slot`; `p187` established `r1=0` clears
  flags there), so the `(player,1)` then `(player,0)` pair is status-effect
  teardown across two slots, carrying no outcome information. The draw screen's "1"
  badge on each side is a **placement badge** (see `ko-outcome-example.png`, which
  shows placement badges 1 and 2 on a one-sided KO result, both at 0 points), not a
  point value — delete any "1 pt each" reading. `0x02171AA0` read `0xFFFFFFFF`
  (never written) at every clean expiry captured, including the final draw: the
  write site it comes from scans an array inside `root` (bound at `root+0x14`) for a
  zero entry and skips the store when none is found, so `-1` here means "not
  written," not "index -1 selected." This session did not see that index driving the
  visible outcome. Mode word (`root+0x000`) and gimmick state were not RAM-read, so
  every claim above is scoped to point mode, じかん 30, Goku vs CPU Luffy, and does
  not generalize to other modes. Full session:
  `../research/feel-captures/match-timeout-2026-09-12/RESULTS.md`.
- **`obj+0x115` is P1's own hitstun countdown, and `0xFF` is its idle value —
  not a wrong address.** Confirmed 2026-09-03
  (`jus-qd8s`,
  runtime-report-9-regen-landing
  §2.5): in a live fight it read 20 → 17 then reset to 20 on the next hit,
  then 40 → 29, and `0xFF` on every frame P1 was not in hitstun. It also
  **freezes** mid-countdown (observed stuck at 29 for 40 more frames of
  state 8), so it is a trustworthy hitstun *flag* but not a reliable *timer*.
  This corrects runtime-report-4-lr-switch-taikoubou.md
  §4, which read the same constant-`0xFF` sampling as evidence the address
  was wrong.
- **J Arena relocates the shared element array, not just the fighter
  objects.** In `pc-raoh-npc-luffy-j-arena`
  (runtime-report-7
  Hazards), the element array's slots 0–5 (`0x0220C068`…`0x0220C1A8`) are six
  never-moving **stage markers** (three platform rows), and the two fighters
  occupy slots **6** (`0x0220C1E8`) and **7** (`0x0220C228`) instead of the
  usual 0/1 — 192 px apart, not the 511 px an earlier tracker item body claimed by
  reading the frozen slot-0/1 markers as the fighters. Resolve fighter slots
  from the fighter table (`0x021DEB3C`) every time in this state family;
  never assume slots 0/1.
- The block this doc and guard-sp.md call the **per-victim hit-result block**
  (`0x02230D60`; P1's is `0x02228E80`, table at `0x021DEB3C`) is the **ov6
  fighter object** itself: `[[obj+0x1A8]+0x10]+0x5C` is the fighter element,
  `obj+0xB8/+0xBA` are walk accel and jump impulse (§6), `obj+0x102/+0x104` the
  guard gauge, `obj+0x114` the hitstun timer (`jus-fighter-object-identity-c56i`).

## 6. Movement: walk, dash, jump (2026-09-02)

`jus-movement-speed-runtime-0luv`, `jus-fighter-object-identity-c56i`. Captures: movement-2026-09-02
(`mv00`–`mv10`), states `pc-kenshin-npc-luffy`, `pc-momotaro-npc-nami`,
`pc-yusuke-npc-nami` (Dark Tournament training, P1 driven by script, CPU idle).
Every number is a per-frame read of the P1 fighter element `0x0220C068` or a
`JUS_WATCH` write log; code reads were checked by a second reader (codex,
neutral prompt, `movement-2026-09-02/codex-second-opinion.txt`).

### 6.1 The integrator (arm9 `0x02082E10`), once per element per frame

Order matters because the logged values are the post-drag ones:

1. `vx += accel_x` where `accel_x = element+0x2C + element+0x30` (s16 each),
   `vy += accel_y` from `+0x2E + +0x32`. Stores at `0x02082F18` / `0x02082F30`.
2. Speed cap: `|v| ≤ element+0x3E << 8` (0x3E = 128 on fighter elements, so
   32768 raw; never reached by a fighter). Other elements keep the allocator's 0x20 (8192 raw, 32 px/frame)
   unless their creator overrides it (`jus-speed-cap-fighter-scope-uhs4`).
3. Drag: `v −= (k·v) >> 8` with `k = element+0x3C` for x (**32**, i.e. 1/8)
   and `element+0x3D` for y (**8**, i.e. 1/32). Stores `0x02083060` / `0x0208306C`.
4. Gravity, unless bit 1 of `element+0x34` is set (`tst [E+0x34], #2` at
   `0x02083074`; **correction 2026-09-03**, was previously written as bit 2 —
   `jus-first-frame-vertical-rounding-hmfg`,
   runtime-report-2
   E2): `vy += manager+0x2C`, which is **41 raw exactly** (`0x02083084`,
   confirmed by a live `JUS_WATCH` read of the literal store). The integer model
   `vy' = vy − ASR(8·vy, 8) + 41` reproduces every airborne frame of every capture.
5. `x += vx + element+0x38`; `y += vy`; both clamped to `[0, 0x40000)`.
6. The four accel fields are zeroed (`0x020830E0`), so movement code must
   write them again every frame.
7. Dead zone: `|v| < 16` raw snaps to 0 on each axis (`0x020830E8`–`0x0208310C`).

Units: velocity is s16 in 1/256 px per frame; position s32 8.8.

### 6.2 Walk: a per-character acceleration through a 1/8 drag

ov6 `0x0215EFC0(fighter, speed, flag)` writes `speed` (sign flipped when facing
left) into `element+0x2C` every frame the stick is held (store `0x0215F01C`,
`JUS_WATCH` `mv09`). `speed` is the fighter-object field **`obj+0xB8`**, set at
character init by ov6 `0x02158A10`:

```
obj+0xB8 = s16 table[0x02171108][ chr_b[2] ]      (char+0x10, the "2..6" field)
```

| chr_b byte 2 | walk accel (raw/frame) | terminal `7·a` (raw) | px/frame | measured on |
|---|---|---|---|---|
| 2 | 107 | 749 | 2.93 | Kenshin (`mv00`: 749 held from f41); Kakashi reproduces the identical 39-sample ramp to terminal, digit-for-digit (`jus-9utl`, [calibration-sweep-two-characters.md](../research/findings/calibration-sweep-two-characters.md)) |
| 3 | 96 | 672 | 2.63 | Eve, ramp to terminal 672 live (`jus-9utl`); previously table only (Goku, Naruto, Sanji) |
| 4 | 85 | 595 | 2.32 | Yusuke (`mv02`: 85 → 577 after 25 frames; terminal not reached); Muhyo, ramp to terminal 595 live (`jus-9utl`) |
| 5 | 74 | 518 | 2.02 | Momotaro (`mv02`: 74 → 503 after 25 frames); Luffy by table |
| 6 | 62 | 434 | 1.70 | Franky `obj+0xB8` read live = 62 (`mv10` session); Jotaro by table |

The ramp is the recursion `v' = (v + a) − ((v + a)·32 >> 8)`; Kenshin's logged
series is 94, 176, 248, 311, 366, 414, 456, 493, 525, 553, 578, 600, 619, 636,
651, 664, 675, 685, 693, 700, 707, 713, 718, 722, 726, 729, 732, 735, 737, 739,
741, 742, 743, 744, 745, 746, 747, 748, 749. Release: nothing is added, so
`v ×= 7/8` per frame until the 16-raw dead zone (726 → 636 → 557 → 488 …).
**Air drift uses the same field and the same ramp** (`mv02` jump+RIGHT logged
94, 176, 248 … identical to the ground walk). `moves.md` §4's "walk speed is
`statC`" is superseded: `statC` is not read by this path.

**Facing in the air (static, 2026-09-25).** The same helper turns the
fighter: in states 1, 6 and 7 (`0x0215EF58`, turn flag 1) a held direction
sets the facing that frame, with no delay and no change to the accel it
writes (static). State 5, the squat and attack states keep their facing
unless a move's script command 22 enables it (static); hitstun keeping it
is inferred (only direct calls were searched). State 6 skips the turn on a
frame an attack, jump or fast fall starts; state 7 turns on every frame.
Owner: air attacks never turn. Grades and cites:
[air-facing-static-2026-09-25.md](../research/findings/air-facing-static-2026-09-25.md).

Status modifiers, static only (`0x02158A68`, not exercised live): status id
`obj+0x88` = 8 or 0x24 → speed ×1.25; status word `obj+0xA0` = 0x16 → ×0.30.

### 6.3 Dash: engine-wide handler, per-character burst records

A double tap starts a dash. Entry (ov6 `0x021565C0`) zeroes `vx`, `vy` and sets
bit `0x1000` in `element+0x34`; the dash-state object then writes its `+0x9C`
into `element+0x2C` each frame while its `+0xA0` counter runs (`0x021558C4`,
store `0x021558EC`). The setup (`0x02156710`) fills those from a 5-byte record:
`+0xA0 = rec[4]` (duration), `+0x9C = rec[2] << 5`, `+0x9E = rec[3] × −126`
(vertical; 0 for the ground dash).

The handler and integrator are engine-wide; the ground-dash record is per
character. Kenshin's record, `chr/rk_b_01` animation 2, has `rec[2]=12` and
`rec[4]=12`: acceleration 384 raw for 12 frames. Momotaro's `oj_b_02` record
is identical. Yusuke's `yh_b_01` record supplies 384 raw for 10 ticks.
The refuter's animation-2 corpus census also found 10 records at 320/12,
6 at 1728/12 and 5 at 448/12; those values are not Kenshin defaults.
Starting from `v = 0`, each of Kenshin's twelve burst frames uses
`u = v + s*384`, then `v = u - ASR(32*u, 8)`, where `s = +1` for RIGHT and
`-1` for LEFT. ASR rounds toward negative infinity. The drag at ARM9
`0x02083040..0x0208306C` therefore gives Kenshin these exact signed sequences:

- RIGHT post-drag `vx`: 336, 630, 888, 1113, 1310, 1483, 1634, 1766, 1882,
  1983, 2072, 2149.
- LEFT post-drag `vx`, as magnitudes: 336, 630, 887, 1112, 1309, 1481, 1631,
  1763, 1878, 1979, 2067, 2144. The signed velocities are negative.

The earlier table came from `mv03`, whose dash variants are LEFT, not both
directions. The September raw independently contains two LEFT matches in
`mv03` and one match per direction in `mv12`. These use signed raw position
differences without rescaling. After the burst, drag continues without added
dash acceleration, even if the stick stays held. Running into the idle CPU
(x ≈ 584 in these states) cuts the burst short (`mv05`), so measure dashes
away from it. Tick 28's 43-raw onset step in capture c60 remains UNVERIFIED; it is
outside the twelve-entry recurrence and adds no timing or tolerance rule.
**Double-tap window (`jus-dash-input-window-mv1g`, `mv12`):** taps of 3–8 frames with a release gap of
3–10 frames all dashed; gaps of 15 and 20 did not (plain walk). One-frame taps
were unreliable under the bridge's ~3-frame input latency.

**Air Dash (ability 3, static-only, 2026-09-12, `jus-utus`).** Gated on ability
bitset bit 3 (`obj+0x128 & 0x08`, ov6 `0215E024`), checked inside the airborne
input dispatcher *after* a wall-jump attempt (§6.4) has already failed for the
frame. `0x0215D860` is the dash-entry function itself — the same entry a
ground dash reaches — not a separate jump gate; it inlines its own
`obj+0xD9 < obj+0xD8` budget check (the same fields Triple Jump raises,
`obj+0xD9` incremented at `0x0215D960` on a grant) before committing. A
successful grant installs the single commit site `0x0215D8E0`, which installs
the same handler as the ground dash, `0x0215D91C`, via the `0x2157494`
wrapper — the same handler, not merely the same state code. Whether that
handler indexes the same movement record this section's `0x02156710` setup
reads (i.e. the identical 384-raw/12-frame burst) for an airborne grant, or a
distinct record slot, was **not traced** this pass — that narrower question
is what's flagged [unverified] in
[mobility-passives-static.md](../research/findings/mobility-passives-static.md).
The one thing this pass does establish: Air Dash and a plain double/triple jump
**compete for the same per-hop counter**, so a character with both Triple Jump
and Air Dash gets two extra air actions total to split between them, not two of
each.

### 6.4 Jump: two impulses, a tier table, and a real double jump

`A` jumps. The impulse is written once into `element+0x2E` (ov6 `0x0215DC2C` /
`0x0215DC48`, `JUS_WATCH` `mv09`) and the integrator does the rest:

| input | impulse (raw) | source | `obj+0xDB` | airborne | peak |
|---|---|---|---|---|---|
| A held **≤ 5** frames | **−1213** | literal (ov6 pool at `0x0215DC40+0x58`) | 6 | 45 frames | 40.82 px |
| A held **≥ 6** frames | **`obj+0xBA`** = table[`0x02171118`][tier] | per character | 9 | 61 frames | 74.68 px (tier 2) |

In code the choice is bit `0x20` of `obj+0x6C` at the moment the jump state
starts (`0x0215DC14`); the 6-frame hold is what the input layer needs to set it.

`obj+0xBA` is set by the same init as walk speed, indexed by `char+0x11`
(the damage-formula tier, chr_b byte 1): **tier 1 −1816, tier 2 −1752, tier 3
−1689**. Kenshin, Yusuke and Momotaro (tier 2) all jumped −1752 → −1656 after
the same-frame drag and gravity, apex at frame 26, land at frame 61, peak 74.68
px — the arc §3 measured from the owner's `m02` captures is the held jump.
Kakashi, Eve and Muhyo (all tier 2) reproduce the same −1752 → −1656 step and
61-frame airborne duration exactly (`jus-9utl`,
[calibration-sweep-two-characters.md](../research/findings/calibration-sweep-two-characters.md)).
Franky's `obj+0xBA` reads −1689 (tier 3; not jumped). **Tier 1 and tier 3
arcs, by poke** (`mv16-tier1-poke`, `mv17-tier3-poke`, `jus-tier-1-tier-3-jump-arcs-0mq1`;
`obj+0xBA` poked on the P1 Kenshin object, `JUS_WATCH` on the field showed no
game write during the plans, control run reproduced the tier-2 arc to the
frame and 0.00 px):

| impulse | vy after the first step | apex frame | peak | airborne |
|---|---|---|---|---|
| −1816 (tier 1) | −1718 | 27 | 79.17 px | 63 frames |
| −1752 (tier 2) | −1656 | 26 | 74.68 px | 61 frames |
| −1689 (tier 3) | −1595 | 26 | 70.57 px | 60 frames |

**Counting convention:** airborne duration is `landing frame −
first-airborne frame`, counting every intervening frame including the one
apex frame where `vy` lands on exactly 0 — not a count of `vy != 0` frames.
Apex frame is 1-based from the first airborne frame, first frame with `vy >=
0`. Peak height is the raw sample `(y_ground − y_min)/256`; tier 1's is
`(172031 − 151763)/256 = 79.171875` px, which rounds to 79.17, not the
79.14 an earlier pass of this table transcribed. This table's numbers come
directly from `mv16-tier1-poke.jsonl.gz` / `mv17-tier3-poke.jsonl.gz`
(`docs/research/feel-captures/movement-2026-09-02/`); re-deriving them
frame-for-frame under this convention is what closed out the "+1-frame
deviation" reported by an earlier pass — see the retraction in
[movement-tiers-1-3-live.md](../research/findings/movement-tiers-1-3-live.md)
(`jus-wthh`).

The tapped short hop was bit-identical in all three runs (−1134 after the
first step, 45 frames, 40.82 px), so it never reads `obj+0xBA`.

**Confirmed live on real tier-1/tier-3 characters (2026-09-12, `jus-wthh`,
[movement-tiers-1-3-live.md](../research/findings/movement-tiers-1-3-live.md)):**
Sasuke (tier 1, `pc-sasuke-npc-jotaro-dark-tournament`) and Raoh (tier 3,
`pc-raoh-npc-luffy-j-arena`) both reproduce the impulse, the post-step `vy`,
the peak height, the apex frame and the airborne duration exactly, on real
played objects rather than a poked Kenshin — the live `(y, vy)` arcs are
bit-identical to the poked arcs for the full jump (66 frames), on both
characters. This promotes the poke from an arithmetic-only proof to a
full-arc validation on real objects; the table above needed a
counting-convention footnote and one corrected peak-height cell, not a
TUNING row (an earlier pass of this doc reported a spurious +1-frame
airborne-duration "deviation" here; retracted, `jus-wthh`). Reaching 3 real
characters per tier still needs new save states (only one live-playable
character exists per tier in the current `INDEX.md` set); flagged as a gap,
not attempted. The hold ladder
(`mv04`: 1, 2, 4, 5 → short; 6, 8, 10, 12, 14, 16, 25 → full) shows no third
level. Landing writes `vy = 0` through arm9 `0x0207ECF4`.

**Double jump:** a second `A` at least ~20 frames after the first applies a
fresh **full** impulse mid-air whatever the first was (tap then A+20 → 88 frames,
peak 114.18 px; hold then A+35 → peak 147.39 px, matching §3's ~149). A second
press within 6 frames of the first is swallowed (`mv02`).

**Static mechanism behind the double jump, Triple Jump, and Wall Jump
(2026-09-12, `jus-utus`, static only — no live capture in this pass).** Full
trace: [mobility-passives-static.md](../research/findings/mobility-passives-static.md).

- **The double jump is a budget, not a hardcoded "one extra."** `obj+0xD8` is
  the max number of extra air actions for the current hop. It has exactly two
  writers, both installing a default/ceiling rather than resetting a per-hop
  counter: `0x02158A58` (character init, default `1`) and `0x0215727C`
  (Triple Jump's apply site, raises it to `2` — below). **`obj+0xD8` is never
  reset.** What resets per hop is `obj+0xD9` (used-this-hop), `obj+0xDA`, and
  `obj+0xDC` (wall-jump-used-this-hop, below), and the reset fires on
  **touchdown**, not on a fresh ground jump starting: the shared reset
  routine `0x0215D53C` zeroes all three, and its only two callers are the
  state-0 (idle) handler `0x0215D3B4` and the state-13 (landing) handler
  `0x0215D564` — both selected by the state dispatcher `0x0215D2E4` (pure dispatch,
  no grounded read of its own); the grounded test `0x0215D904` (the same
  `M+0x78` bit-`0x2` check the ability-gate discussion below cites) runs in
  the callers' helper `0x0215DEC8`, which commits state 6 when airborne so the
  dispatcher only runs grounded. One more reset site exists: handler
  `0x0215E4AC`, installed as state 15 by `0x0215E470` when `M+0x40` bit
  `0x400` is set, zeroes `obj+0xD9`/`0xDC`/`0xDA` at `0215E4F4`–`0215E4FC`
  mid-air and writes `obj+0xBA << 1` into `element+0x2E` (`0215E4EC`), so that
  state regrants every air action with a doubled impulse; what state 15 is in
  gameplay is **[unverified]**. `obj+0xD9` also has a third increment at
  `0x02159F74` (with `0xDA` at `0x02159F80`, guarded by `obj+0xCA` in 9..10),
  a consumer not traced this pass. The budget
  check `obj+0xD9 < obj+0xD8` is not one shared gate function — it is inlined
  separately at each commit site: the double/triple-jump commit inlines it
  at `0x0215E28C`–`0x0215E2A4` inside the state-5 commit function
  `0x0215E1D0` (`obj+0xD9` incremented at `0x0215E368` on a grant), and the
  air-dash commit inlines the identical check at `0x0215D860` inside the
  dash-entry function (§6.3; `obj+0xD9` incremented at `0x0215D960` there).
  Both read the same two fields, so Triple Jump's raised ceiling benefits
  either consumer, but there is no single call target both share. On a
  jump grant, the commit commits state 5 ("double-jump start", §4.5's
  enum) and, on the frame that state's handler sees
  `obj+0xDD == 0` (no wall-jump direction pending), writes `obj+0xBA`
  straight into `element+0x2E` unhalved (`0215E38C`) — the static
  confirmation of "a fresh full impulse mid-air whatever the first was"
  above. The same commit adds `+9` to the landing-lag budget `obj+0xDB`
  (§6.6's `9 × (double-jumped?1:0)` term — this is that term's write site,
  `0215E3A0`–`0215E3A8`); the write fires once per state-5 entry, so the wall
  jump below (which also commits state 5) takes the same `+9` — see §6.6.

*(Note 2026-10-13: in a hop started by Eve's Ultimate Action the `+9` per grant
does not reproduce: one air jump gives a 10-tick state-13 window, two give 19.
See the note in §6.6; C-UA-Eve, `docs/research/feel-captures/2026-10-13-eve-ua`.)*

- **Ability 1, Triple Jump** (`obj+0x128 & 0x02`, ov6 `0215726C`) raises the
  same `obj+0xD8` ceiling to `2` at ability-load time, so a carrier gets two
  grants of the exact mechanism above (ground jump + 2 extra air actions —
  "３段ジャンプ", 3-stage jump) instead of one. No third code path exists; the
  ceiling is the only thing that changes.
- **Ability 2, Wall Jump** (`obj+0x128 & 0x04`, ov6 `0215E1F8`) is a *separate*
  trigger, tried before the air-dash entry's own budget check on every airborne A-press
  (`0215E018` calls the wall-jump function before `0215E024`'s air-dash test
  runs, §6.3). Trigger conditions, all required: A held (`obj+0x6C & 0x10`,
  the confirmed input bit — `guard-sp.md:275`), ability bit 2 set,
  `obj+0xDC == 0` (not already spent this hop), and a collision/touch flags
  word `M+0x78` (`[[obj+0x1a8]+0x10]+0x78]` — the same ColPrm flags word §4.5
  and the combat notes §2/§8 already document as rebuilt every frame by
  arm9 `0x0207F8DC`/`0x0207ECC0`/`0x0207ED08`, not a new field) reading bit
  `0x4` or `0x8` (wall on one side or the other, direction recorded as `±1`
  in `obj+0xDD`) with bit `0x400` clear. Any failed condition falls through
  to the same `obj+0xD8`/`obj+0xD9` gate a plain double/triple jump uses. On
  success: state 5 commits (same code as the plain double jump), but with a
  **4-frame windup** — `obj+0x1E8` is set to `12` and counts down one per
  frame the state-5 handler runs (observable as `12, 11, 10, 9, 8` across 5
  frames — `12` is written then decremented the same frame, so the visible
  sequence from the commit frame on is `11, 10, 9, 8`); when it reaches `8`
  the impulse fires: `element+0x2C` (vx accel-this-frame, §6.1) gets
  `direction × 0xA00` (**2560 raw ≈ 10.0 px/frame**, a code literal, not a
  per-character value), and `element+0x2E` (vy impulse) gets **half** of
  `obj+0xBA` — `asr` by 1 after a round-toward-zero adjustment
  (`add r1,r3,r3,lsr#31; asr r1,r1,#1` at `0215E438`–`0215E444`) — so for
  tier 3 (`obj+0xBA = −1689`) the instruction computes `(−1689 + 1) asr 1 =
  −844`, not `−845` (`asr` rounds toward zero here, not down); tier 1/2/3
  wall-jump vertical impulses are −908/−876/−844 (halves of the tier table
  two paragraphs up, not independently re-measured). On the commit frame,
  `obj+0xDC` (wall-jump-used-this-hop) is incremented twice for a wall jump —
  once generically at `0x0215E270` and again at `0x0215E33C` in the
  facing-flip path below — so it reaches `2` after a single wall jump rather
  than the `1` a plain budget-slot read would suggest; this is a quirk of
  the two increment sites, not two grants. The same commit frame also calls
  arm9 `0x02083950` with a 0/1 argument (at `0215E310`–`0215E328`,
  direction-dependent); it forwards through vtable slot `+0x5C` to a halfword
  at sub-object `+0x4C` (`0x020750D8`). Reading that as a facing flip is
  **[unverified]**, inferred from the flag's use only. Bit-meaning of the `0x4`/`0x8`/`0x400` collision
  flags (which physical side, and why `0x400` invalidates contact) is
  **[unverified]**, inferred from control flow only.

### 6.5 Constants that fall out

- **Gravity 41 raw/frame², vertical drag 1/32.** Terminal fall speed is the
  fixed point of step 3–4: `(8·v) >> 8 = 41` → `v ∈ [1312, 1343]` raw =
  **5.13–5.25 px/frame** (derived from the integrator; the longest capture
  reached 899 raw before landing, so it is not observed).
- **Stage walls in these states:** x = 260 and x = 764 (P1 stops dead;
  arm9 `0x0207ED90` zeroes a positive `vx` at the right wall).
- **Fast-fall is DOWN+A** (§2): plain DOWN in any form does nothing (`mv07`,
  `mv08`); DOWN+A writes 3072 raw (`mv11`).

### 6.6 Landing lag and the landing cancel

> **Correction 2026-09-23 (`jus-wvg5`,
> landing-lag-2026-09-23/RESULTS.md):
> the base `10` in the law below holds after a **full jump** only (run 11 ran
> full jumps only, A held 8 frames). After a **short hop** the base is **7**.
>
> - **Measured, Kakashi** (`pc-kakashi-npc-jotaro-dark-tournament`, A held 1
>   frame, n = 2 GDB + 2 Lua per cell): state-13 window 7 plain and 19 with
>   one air B or air Y, against 10 and 22 after a full jump. Hit or whiff makes
>   no difference (spacing about 18, 55 and 155 px).
> - **Measured, Kenshin, n = 1** (runtime report 2, `b1-shorthop` and
>   `b7-airB`, A held f0–4 = 5 frames): window 7 plain, 19 with one air B.
> - **Hold lengths:** data backs base 7 at holds of 1 and 5 frames. Holds of
>   2–4 are **TBD**, though the combat notes §3 counts every hold of 5 or less as a
>   short-hop arc.
> - **Every character: inferred.**
> - **Fast-fall is not covered.** Report 2's `b4-ff-short` (Kenshin, short hop
>   then fast-fall) reads window 4, lag 7. That fits neither base 7 nor the
>   ladder's "fast-fall 13" below, which holds for a full-jump fast-fall only.
> - Frames until movement after a short hop: **inferred** 10 plain and 22 with
>   one air attack (window + 3, the no-owed-frames case below). Report 2
>   measured 10 and 22 on Kenshin.
>
> So the kit's 19 (short hop) and run 11's 22 (full jump) are both right.

> **Conflict flagged 2026-09-23 (`jus-wvg5`):** the movement line of the law
> below says `owed + window + 1`, but the ladder and the banner above use
> window + 3. Checked against run 11's own table at HEAD (47 rows, its Lua
> basis: landing = the frame `M+0x78` reads 2, RIGHT held from there):
> `owed + window + 1` fits 7 rows, `window + 3` fits 40, and
> `max(owed, 2) + window + 1` fits all 47. So: **window + 3 when the attack
> owes nothing at touchdown** (measured on Kenshin, Yusuke and Kakashi, 40
> rows), **owed + window + 1 when it owes 6 or more** (measured on Kenshin and
> Kakashi only, n = 7: Kenshin ×6, Kakashi ×1, the 64 worst case; Yusuke has
> no owed row). Owed values of 1–5: TBD (never run).
> On the GDB integrator basis state 13 starts one frame after touchdown, not
> two, so the `+3` is tied to run 11's basis; movement was not measured on
> the GDB basis.

> **Correction 2026-09-23 (`jus-wmqi.6.4`,
> [anim-timing.md](../rebuild/anim-timing.md) §7):** `obj+0x72` is **not**
> animation-elapsed frames. Its two writes sit in the input sampler at ov6
> `0x02161148` (`r4 = obj+0x1C`, so `obj+0x72` is `[r4+0x56]`). It counts
> sampler calls while the input word stays the same, and resets to 0 when the
> word changes or reaches 600 (static; codex agrees). Measured over 186 landing
> logs: never above 599, and 948 of 1006 resets come with no state change.
> Read every `obj+0x72` / `anim72` value in this section and in runtime
> reports 2, 9 and 11 as "how long the input has been unchanged".
>
> **Still stands:** the state-13 window formula, the ladder, run 11's
> owed-frames law ("No row needs `obj+0x72`") and the landing-cancel numbers
> (13 → 8, 25 → 14, 22 → 11, 34 → 17). They come from state codes.
>
> **Falls**, in this section:
> - the falsifier sentence under the law ("Three falsifiers that varied only
>   `obj+0x72` at touchdown"). The runs and their lags stand; what they varied
>   was when the attack was thrown, not a measured animation position.
> - "DOWN+A … restarts the animation" in the Landing cancel bullet. That is
>   runtime report 9 §3.4's reading of `obj+0x72 = 0` at touchdown; a DOWN+A
>   press changes the input word, so the counter reads 0 whatever the animation
>   does.
> - "Plain full-jump airborne animation is 70 frames … Kenshin air Y 40,
>   Yusuke air Y 25". The 70 is `lag + obj+0x72 − 1` (report 9 §3.5). In the
>   ALMT data the jump is short held animations (0x04–0x08, 4 to 8 frames;
>   decoded for Kakashi and Yusuke only, not Kenshin or Taikoubou), and
>   Yusuke air Y is ALMT 0x27, 127 frames, whose attack ends in the air at
>   frame 48. Any "N-frame animation" built from `obj+0x72` falls;
>   anim-timing.md replaces those lengths.

**Law (run 11, `jus-4nta`,
runtime-report-11,
pre-registered, 47/47 rows on Kenshin, Yusuke and Kakashi).** Landing recovery
is an additive budget per hop, not leftover animation:

```
state-13 window          = 10 + 12 × (air attacks this hop) + 9 × (double-jumped ? 1 : 0)
frames until movement    = (frames the current attack still owes at touchdown) + window + 1
```

Ladder, identical on all three characters: jump / fast-fall 13, double jump
22, one air attack 25, double jump + attack 34, two air attacks 37, worst 64
(second attack one frame before touchdown). *(Correction 2026-09-23,
`jus-wmqi.6.4`: "varied only `obj+0x72`" in the next sentence means "varied
the throw frame"; see the banner above.)* Three falsifiers that varied only
`obj+0x72` at touchdown left the lag unchanged (Kenshin air B f40 vs f48 →
25/25; air Y f16 vs f60 → 40/40; Kakashi double-jump air B `obj+0x72` 65 vs 1
→ 34/34). A third air attack per hop, or a second after a double jump, is
refused. `obj+0x110` reads 0 on every landing measured: there is no landing
countdown field; the window is realised through the state machine.

**Static addendum (2026-09-12, `jus-utus`, not re-measured live this pass):**
the `+9` term is a per-grant write at state-5 commit (`0215E3A0`–`0215E3A8`,
§6.3/§6.4), not a one-time flag, so it is additive across every state-5
commit in a hop, not just "double-jumped y/n." Two Triple-Jump grants in one
hop add `+18` (not `+9`), and a wall jump — which also commits state 5 — adds
its own `+9`. The live-measured ladder above only exercised one double-jump
grant per hop; the Triple-Jump and wall-jump cases are static inference from
the shared write site, not independently measured.

*(Note 2026-10-13, C-UA-Eve,
README "Landing window",
`claims-ua.json` `ua_landing_after_air_jump`: a UA-started hop (no ground jump;
Eve's state 12 ends in the air and falls as state 6) breaks the ladder above.
0 air jumps: no state 13 (idle 2 ticks after touchdown). 1 air jump: state 13
lasts 10 ticks; the binary `9 × (double-jumped ? 1 : 0)` term predicts 19. 2 air
jumps: 19 ticks, equal to the binary term and in conflict with the static
addendum just above, which predicts 28 (`10 + 9 + 9`). The rule is not changed
here. Untested: the timing of the air jump inside the fall.)*

- **Movement-only.** A fresh 2-frame B press produces `obj+0x18 = 9` exactly 3
  frames after the press from inside every window measured (`jus-qd8s`). The
  ladder measures frames until the fighter can walk.
- **Landing cancel** (`jus-landing-cancel-e73z`, `mv13`–`mv15`, `jus-qd8s`):
  *(Correction 2026-09-23, `jus-wmqi.6.4`: "restarts the animation" in the next
  sentence falls; the numbers stand. See the banner above the law.)*
  DOWN+A from about two frames before landing through the landing frame restarts
  the animation: plain jump or fast-fall 13 → 8, post-air-attack 25 → 14
  (Kenshin air B, both Yusuke air attacks).
  *(Correction 2026-09-23, `jus-wmqi.6.2`: the next sentence is wrong.
  regen-landing-2026-09-03 `B4-cancel-K2airB` (Kenshin, state 9 f51–78,
  touchdown f73, cancels 34 → 17) and `B5-cancel-Y2airB` (Yusuke, state 9 at L−2
  and L−1, cancels 22 → 11) both cancel. Being in state 9 at landing − 2 does
  **not** block the cancel. The measured fails are the landings that owe 13 or
  more frames at touchdown with the press at about L (Kenshin's air Y, his
  three-air-B string). The one landing that owes 6 cancels. Where the reach sits
  for owed 7–12, and whether a press after L+2 in a deferred landing counts:
  TBD.)*
  It fails only when the fighter is
  still in state 9 at landing − 2 (Kenshin's air Y stays 40, Kenshin's
  three-air-B string stays 48). A dash-tap never cancels the lag. The owner
  reports a white flash on the cancel; not checked visually.
- *(Correction 2026-09-23, `jus-wmqi.6.4`: the 70, 40 and 25 below are not
  animation lengths; see the banner above the law. Yusuke air Y is ALMT 0x27,
  127 frames.)*
  **Plain full-jump airborne animation is 70 frames** on Kenshin, Yusuke and
  Taikoubou, with the same 13-frame lag: a shared engine animation. Per-move
  air animation lengths differ per character (Kenshin air Y 40, Yusuke air Y
  25) and enter the lag only through the owed-frames term.

*(Correction 2026-09-23, `jus-wmqi.6.4`: this bullet is wrong about what
the field means; see the banner before the run-11 law above.)*

- `obj+0x72` (u16 animation-elapsed frames) is written `+1` per frame at ov6
  `0x021612E4` and reset to 0 on an animation change at `0x02161334`.

**Retracted rule.** Runs 2 and 9 (`jus-landing-lag-variable-drivers-fe39`,
runtime-report-2
E1; `jus-qd8s`,
runtime-report-9-regen-landing
§3) fit `lag = animation_length − obj+0x72_at_landing + 1` on 12/12 and 11/11
rows within a run. Fed animation lengths from a prior run it predicted 6/21,
so it was an identity within one run, not a law, and is retracted as a
mechanic. The measurements in those reports stand; their "double jump 19 /
air B 22" rows are the state-13 window, three frames short of movement
return (22 / 25).

### 6.7 Camera, floor row and the Dark Tournament ledge (2026-09-23)

**Measured, Kakashi on `pc-kakashi-npc-jotaro-dark-tournament`, from
screendumps and RAM** (`jus-combo-truth-live-dcow`,
combo-truth-2026-09-23/RESULTS.md Q4;
the shift numbers come from `plans/camera.py`, which does row matching
between consecutive shots).

- **The top screen scrolls up with the fighter, with a few frames of lag.**
  At the double-jump peak (147.4 px above the floor, 28 frames after the
  second press), the camera has risen **142 px**. It peaks at 145 about 10
  frames later. On the way up, the sprite runs up to 17 px ahead of the
  camera, and on the way down it trails by up to 17 px. A single jump (74.7 px)
  moves the camera 71 px at its peak.
- **Floor row.** With the camera at rest, the lowest row of Kakashi's
  standing sprite is screen row **120** of 192 (floor y 672). The grey floor
  band is rows 118–122.
- **Dark Tournament has a ledge on the right.** Its top is **y 527.16, 144.84
  px above the floor**. Kakashi lands on it from double jumps at x 699 and
  746. Walking left off it, he starts to fall between x 634.4 and 631.6.
  There is no ledge at x 430 or 314. That it runs to the right wall at 764
  is inferred. A double jump from the ledge reaches y ≈ 390 (282 px up).
- **Walls** match §6.5 (P1 stops at x 260.0 and 763.996, about 504 px apart).
  Walking left, P1 passes through a standing Jotaro.
- **The arena's horizontal extent is not resolved: this project holds two
  irreconcilable extents, plus a third measurement that settles neither.
  Recorded 2026-09-26 (`jus-zmdb`); no figure below is retired and none is
  picked between.**
  - **Measured walk limit 763.996 px** (`0x2FBFF` = 195583 raw) — the right wall
    §6.5 already gives. `side-b-range-2026-09-23/main/far_R60` walks RIGHT at
    `vx` 749 and stops dead between plan 64 (763.4648) and plan 65 (763.9961,
    `vx` zeroed), held there to the end of the 187-row run
    (side-b-range-2026-09-23/RESULTS.md).
  - **arm9 immediates `0x4000` / `0x3C000`** = **64.0 / 960.0**, an 896 px box.
    The walker at `0x0207DD74`/`0x0207DD9C` tests an element's span against
    them and the rect getter at `0x0207DE88` emits them as the left and right
    wall regions. **They are 24.8 fixed point, not the 8.8 every position in
    this file uses** (`add r0, r2, r0, lsl #8` at `0x0207DD70`), and the source
    grades the pixel reading itself only PLAUSIBLE
    ([arena-bounds-and-the-merged-function.md](../research/findings/arena-bounds-and-the-merged-function.md) §2–3).
  - **Measured floor edges: 184.05–187.77 px on the left, 837.47–838.79 px on
    the right** — a floor about **654 px** wide, so the right floor edge is
    **roughly 74 px past** the 763.996 walk limit, and the arm9 pair describes a
    box 241 px wider than the floor. Bracketed from four ground-to-descent
    events, on-floor decided *solely* by `y == 172031` (671.996 px):
    - left, `push-2026-09-24/wall/Y_x8` P1 plans 722–723 (186.9258 on, 184.0508
      off) and `wall/Y_x6` P2 plans 659–660 (187.7695 on, 187.2070 off). **The
      two left brackets are disjoint by 72 raw (0.28 px)**, so no single left
      edge value satisfies both; 184.05–187.77 is the union, not one bracket.
    - right, `victim-body-box-2026-09-24/ycv/jump_300` P1 plans 798–799 (837.4688
      on, 838.7891 off) and
      `victim-body-box-2026-09-24/yv/jump_262` P1 plans 744–745 (836.5234 on,
      839.2891 off). These two **do** intersect, at (837.47, 838.79].
  - **Not established:** whether `64.0`/`960.0` is a global outer box, a
    different stage, or a different coordinate space. The space is already
    offset — the floor's y is 671.996, not 0 — and the immediates are 24.8
    while the captures are 8.8, so neither figure can be read against the
    others without a unit conversion nothing in the repo currently supplies.
  - **What would close it:** the per-stage floor edges' source in RAM, and a
    resolution of the 8.8-vs-24.8 question for the arm9 constants.
- **TBD** (`jus-combo-truth-residuals-sico`): the camera's x scroll and the
  ledges on other stages. **Measured for Eve only:** Dark Tournament has a
  ceiling at **-280 px** (floor-relative position y). In capture E1c
  (2026-10-13-eve-ua), her
  air-jump trial E1c_four_a clamps at tick 92, at raw y 100352 (392.000 px),
  exactly 280 px above the floor top at raw 172032 (static floor record 18; a
  standing fighter rests one raw above that top, at 172031). vy is zeroed on
  that tick and she falls on the next. Trials E1c_four_a, b and c are byte-identical. Stage
  `dark-tournament`. **Unmeasured:** whether every fighter clamps at this same
  position y or at a body edge, and whether the other stages have a ceiling.

## 7. Per-frame task order (2026-09-12)

Grade: **PLAUSIBLE**. `jus-entity-frame-placement-4tok`, `jus-pb6n`. Basis:
[per-frame-call-order-of-the-battle-step](../research/findings/per-frame-call-order-of-the-battle-step.md)
(static disassembly of the task-scheduler's sort-key insert, corroborated
live by a 730-combined-frame two-state GDB probe;
frame-order-2026-09-12).

The engine runs one shared per-frame task list, ordered by an ascending
sort key each task registers once (arm9 `0x02012940` → node vtable
`+0xA0`; enabled into the list via `0x02027EDC` → `0x020119EC` →
`0x0201CCA0`, the sorted-insert routine, into the single global list at
`*(0x020A0C34)+0x460`). `0x02028384` only installs the per-task callback
pointer at `obj+0x40`; it is not itself the ordering authority.

Ascending sort keys, and the tasks holding them:

| Key | Task | Entry address |
|---|---|---|
| `0x81000` | Bench regen (per benched koma, via an inner linked-list walk) | `0x02076510` (owning task; inner per-koma tick at `0x02077D40`) |
| `0x85000` | Fighter task (per fighter; two instances, tie order LIFO) | `0x02156DDC` |
| `0x88000` | ObjShot per-frame entry | `0x0216AF04` |
| `0x9E000` | Collision driver (hit events) | `0x0207F480` |
| `0xA1000` | Integrator pass | `0x02082E10` |

So the order is **bench regen → fighter task(s) → ObjShot → collision
driver (hit events) → integrator pass**, cyclically. Regen's key was
found `2026-09-12` (`jus-u7to`, round 2/3,
u7to-boundary-2026-09-12):
the routine at `0x02077D40` is only an inner per-koma tick called from a
linked-list walk inside `0x02076510`, which is the actual scheduler task
and registers key `0x81000` — the same `vtable[+0xA0]` insert pattern as
the other four tasks, confirmed live via a `$lr` chain landing on the
generic dispatch thunk's custom-callback exit
(`0x02028608`/`0x02028628`). `0x81000 < 0x85000`, so regen is now the
lowest-key task, replacing the fighter task as the frame's first task.
**The frame boundary sits before regen's scheduler pass, at the PAD call
that precedes it** (see below); the exact cut relative to the display
frame is open. This is not before the fighter task, as an earlier round
of this finding assumed.

Per fighter task call (one call per fighter object per frame, all inside
`0x02156DDC`): fighter update (`0x0215A978`) → guard drain (`0x0215EF24`)
→ state-machine commit (`0x02159CC4`, writer of `obj+0x18`). Guard drain
is not a separate pass over both fighters; it runs per-fighter, between
that fighter's own update and its own commit.

The integrator (`0x02082E10`) is a **pass**, not a per-element entry: its
own entry fires once per frame; an internal loop (head `0x02082E24`, body
`0x02082E40`-`0x02083160`, tail `0x02083164`-`0x0208316C`) iterates every
element inside that single call. A frame-entry probe cannot see the
per-element iterations. **Live-measured element count** (`jus-u7to`,
2026-09-12, a two-fighter + live-projectiles state): 3-14 elements per
pass, mode 3 (2 fighters + 1 projectile, 1,390 of 2,399 frames), with
1,009 of 2,399 frames (42%) at 4 or more — the projectile count churns
frame to frame as spawns/despawns happen.

Consequence for damage/hitstun sequencing: because the collision driver
(which stages contacts) runs and the integrator (which the staged
knockback is consumed by, §4.2) both fall in the same rotation before the
next fighter-task call, **a hit's contact is staged and its knockback
integrated in frame *N*, but the pending-damage HP drain and hitstun write
that the fighter update performs (the combat notes §1) happen at the *next*
fighter-task call — frame *N+1*.** Staged knockback stays same-frame
(produced in the collision driver, consumed by the integrator before the
next fighter update); damage drain crosses the frame boundary.

Open items (not resolved by this measurement):

- ~~Bench regen has no static registration/key anchor found; which side
  of the frame boundary it falls on is unknown.~~ **Closed 2026-09-12**
  (`jus-u7to`, round 2/3): regen's owning task is `0x02076510` (not the
  inner tick `0x02077D40`), key `0x81000`, the new lowest key — regen is
  the frame's first scheduler task. See the key table above and
  u7to-boundary-2026-09-12.
- Input sample now has a static anchor and was probed live (`jus-u7to`,
  2026-09-12): the pad routine at `0x0203A614`.. reads `REG_KEYINPUT`
  (`0x04000130`) at `0x0203A63C`, then ORs it with the ARM7 shared-WRAM
  extras at `0x027FFFA8`, measured once per battle-frame cycle sitting
  between the integrator and regen. **Round 2/3 (`jus-u7to`, 2026-09-12)
  traced PAD's live caller chain**: it is not a scheduler task — it is
  called by the fixed-count array walk `0x02028EE0`/`0x02028F24` (live
  `lr=0x02028f94` inside `0x02028F68`), which **lands between the
  integrator and regen every frame** (live-proven). Which of two static
  candidates drives that walk is unpicked: the fixed-timestep
  accumulator loop at `0x02034690` (`r4 = [r5,#0x18c] >> 12` steps, loop
  body at `0x02034738`) and the straight-line call inside `0x02041F9C`
  (at `0x020422BC`, after `blx [[r0,#0x1c8]+0x14]`). Both candidate
  drivers have zero static callers and no live probe broke on either
  this session, so **"the frame boundary sits immediately before PAD"
  is not established** — only "PAD is not a scheduler task; called by
  the fixed-count array walk `0x02028EE0`/`0x02028F24`; lands between
  the integrator and regen every frame" is live-proven. Falsification
  test for a future session: one battle run with breakpoints at
  `0x02034738` and `0x020422BC` — exactly one of the two should fire
  per frame, identifying the real driver. **Run 2026-09-12
  (`jus-u7to`, RESULTS-driver.md):
  falsification test done, one state, 1,974 battle frames. `0x020422BC`
  (inside `0x02041F9C`) fired exactly once per frame, every frame,
  constant caller `lr=0x02046c78`; `0x02034738` (the accumulator loop)
  fired zero times. So `0x020422BC`/`0x02041F9C` is the real driver of
  the pad walk in this state, not the accumulator loop — but this
  still does not pin the frame boundary itself: it only relocates which
  static candidate calls the already-measured PAD/regen adjacency, and
  no VBlank-wait exists anywhere in the ARM9 disassembly corpus (`grep
  swi` finds none) to anchor either candidate against a hardware frame (superseded: see `jus-vblank-wait-sdk-call-du3c`).
  Treat "the pad walk is the first action of each sim step" and "the
  step boundary sits before PAD" as still open — this run answers
  *which function calls the walk*, not *where the frame cuts*.** Codex's second opinion
  (codex_second_opinion_boundary.md)
  agrees on the accumulator and the key, and adds: infrastructure nodes with
  keys `0x40000` and `0xA0000` also exist in the sorted list, so regen
  is the first *gameplay* task, not the first node; `0x02012A14` and
  `0x02012AB8` are node callbacks, not the outer dispatcher; steps per
  real frame under load is unproven (see below). Status-node countdown
  still has no static anchor address found and was not probed.

  **In-function structure of `0x02041F9C`, read end to end (`jus-u7to`,
  same day,
  RESULTS-driver-structure.md):**
  within one call, the pad-walk pair (`0x02028EE0` at `0x020422BC`,
  `0x02028F24` at `0x020422C0`) and the scheduler dispatch (`0x020345D4`
  at `0x02042328`) are unconditional and strictly ordered — pad walk
  first, dispatch call last, with a fixed sequence of other calls between
  them (a single call each to `0x02020C04` and `0x020322FC`, then a
  4-iteration counted loop over `0x0203C5AC`) and nothing else that looks
  like scheduler work. Codex's second opinion on this reading
  (codex_driver_structure_answer.md)
  confirms the ordering directly from the disassembly and adds one
  correction: `0x020345D4` (the call at `0x02042328`) is an **outer/
  container dispatcher**, not the direct walker of the sorted task-list
  head `*(0x020A0C34)+0x460` — it never loads that offset. The direct
  walker is `0x02012A14`, reached only as `0x020345D4`'s own callback, so
  the chain is `0x02042328 → 0x020345D4 → 0x02012A14 → sorted battle
  tasks`, one hop more indirect than a same-session first draft assumed.
  Codex also confirms `0x02054B44` (called repeatedly through
  `0x02041F9C`) is a protected hardware-timer read (`0x04000100`), i.e.
  genuine profiling instrumentation bracketing sections, not disguised
  gameplay logic — so the function's non-pad, non-dispatch calls are, as
  far as this reading goes, exhausted by cleanup/maintenance work and
  timing, with no second scheduler-adjacent call hiding among them.
  Codex flags that the caller-side loop (`0x02046C40`-`0x02046CA0`,
  inside the full function `0x02046BD8`) is a **fixed 4-slot loop**, not
  a variable-length list walk, and that nothing in either function
  establishes a 1:1 relationship with hardware VBlank — the wait/gating
  mechanism, if any, must sit above `0x02046BD8`'s own caller, in
  interrupt plumbing, or on the ARM7 side; none of that was traced this
  session (superseded: see `jus-vblank-wait-sdk-call-du3c`).
- Steps per real frame: the accumulator is `0x020A0DC0` (20.12 fixed
  point, pool literal `0x020A0C34`); `N = acc >> 12` is the number of
  scheduler-pass iterations run per driver call, and the loop is
  zero-trip capable; after the loop `acc -= N << 12`. Measured
  (`jus-u7to`, round 2, one state,
  `pc-momotaro-npc-yusuke-projectiles-about-to-collide`): exactly 5
  `PAD_ENTRY` hits (5 pad objects) across 7,551/7,551 battle frames —
  one step per real frame in that state. Steps per real frame under
  load (e.g. frame-rate hitches) is unmeasured and open.
- No positive control exists for the live measurement; corroboration is
  the static key order derived independently of the runtime probe, now
  reinforced by a second, independent static reading (regen's key) that
  also matches the live `$lr` chain.
- Fighter state `0x1B` (skips update and drain, commits only) and the
  alternate per-fighter callback `0x02156F48` (installed under the same
  key by the toggle at `0x02156F6C`; runs update only, skips drain and
  commit) were not exercised by either capture.
- No VBlank-wait instruction was located inside `0x02034690` or its
  direct callees this session; the hardware vsync point relative to the
  accumulator loop is still open (`jus-u7to` Gaps) (superseded: see `jus-vblank-wait-sdk-call-du3c`). **Checked again
  2026-09-12** (RESULTS-driver.md):
  the ARM9 disassembly corpus contains zero `swi` instructions anywhere
  (no BIOS `IntrWait`/`VBlankIntrWait` call exists), and the three
  `DISPSTAT` (`0x04000004`) literal loads plus the one `VCOUNT`
  (`0x04000006`) literal load in the corpus are a one-time IRQ-enable
  bit set, a fixed mode write, a masked read-modify-write, and a
  one-time VCOUNT read feeding a hash/seed — none is a poll/busy-loop.
  That search was right about what it looked for (no `swi`, no
  DISPSTAT/VCOUNT busy-loop in game code), but its conclusion that no VBlank
  wait exists was wrong: the main loop's frame wait is `bl 0x020552A8`
  (`OS_WaitVBlankIntr`) at `0x02042250`, which waits through `OS_WaitIrq`
  (`0x02051B0C`). It is an SDK library call (`jus-vblank-wait-sdk-call-du3c`). `0x020552A8` first calls the
  Thumb stub `0x020000EA`, which is `svc 3`, so the "zero `swi`" result holds only for the ARM-mode grep. The
  vsync point is that call; where it sits relative to the accumulator loop follows
  from the call order.

## GAPS

| Gap | What would close it |
|---|---|
| ~~Where the fast-fall constant lives in code.~~ Closed 2026-09-02: ov6 `0x0215E118`, immediate `0xC00` (§2, `jus-fast-fall-input-em4b`). | — |
| ~~The `0x0BC9` literal is not in the ROM.~~ Closed: 3017 is `0xC00` after one drag step and one gravity step (§2). | — |
| **Terminal fall velocity observed.** Derived as 1312–1343 raw from the integrator (§6.5); never reached in a capture. | A fall from higher than the stage allows, or a poked `y`. |
| ~~Jump arc for a tier-1 or tier-3 character.~~ Measured by poke 2026-09-02 (§6.4: 79.17 px / 63 f and 70.57 px / 60 f), then measured live on a real played character (Sasuke tier 1, Raoh tier 3) 2026-09-12 — exact match, bit-identical arcs (`jus-wthh`, [movement-tiers-1-3-live.md](../research/findings/movement-tiers-1-3-live.md)). Surviving gap: only one live-playable character per tier exists in the current save-state set; reaching the usual 3-per-tier bar needs new save states. | New save states with a tier-1/tier-3 character as P1 (2 more per tier). |
| **Status speed modifiers** (×1.25 for status 8/0x24, ×0.30 for 0x16; §6.2) are static reads only. | A state with the status applied, walk 40 frames. |
| ~~Which hits read the HP band / body factor on untiered hits.~~ Closed 2026-09-02: only `moveData[+1] == 6` hits (§4.6); weight bits inert on the jab and the Jotaro pop by poke (§4.5). | — |
| ~~What `hit+0x110` is and how hitstun is chosen.~~ Closed 2026-09-02: `hitstun = clamp(M[0x171] + 20 + T[state], 16, 60)`, `+0x110` is the landing-recovery timer (§4.5). ~~Where a non-break move's base lands in `M+0x171`~~ Closed 2026-09-02: it never does; the 40 / 60 are the launched-state handlers multiplying the formula's 20 by ×2 / ×3 (§4.5, `jus-m171-hitstun-base-source-fgpn`). ~~What routes a hit to the grounded, pop or launcher handler~~ Closed 2026-09-03: `obj+0xFC = table[0x021721A0][(u16)obj+0x100]`, index copied from `moveData[+1]` via `M+0x16C`, gated on `M+0x28 == 0` (§4.5, `jus-air-knockback-move-universality-8j0j`). | — |
| ~~Does air knockback (Jotaro Y) carry the weight factor?~~ No (poke test, §4.5, `jus-air-knockback-weight-3gm4`). | — |
| ~~Exact rounding of the first-frame vertical term.~~ Closed 2026-09-03: G is exactly 41 raw, not ≈41.5; the ±0.5 was the floor of the integrator's drag shift (§4.2 exact integer recipe, `jus-first-frame-vertical-rounding-hmfg`). | — |
| ~~Frames per timer unit.~~ Closed: 144 frames/unit, `CROSS_CONFIRMED` (§5, [match-timer-units.md](../research/findings/match-timer-units.md); `jus-1g6`, `jus-6fo`, `jus-uvs`, `jus-timed-match-timer-units-2jyu`). | — |
| **Frames-per-unit backing RAM word, decrement pc, and KO/cut-in stall behavior.** Still open (§5, `jus-timed-match-timer-units-2jyu`). | GDB attaching cleanly on the first action after launch, or a `tail`-based per-frame watch of small candidate regions instead of full-RAM `dump`. |
| ~~Guard gauge break decision.~~ Closed 2026-09-02: arm9 `0x02081740` tests `M+0x40 & 0x4000` (gauge-at-max latch); [guard-sp.md](guard-sp.md) §0.5 (`jus-guard-break-decision-obj-0x110-1xty`). | — |
| ~~Reaction-handler pointer discrepancy~~ **closed 2026-09-03** by run 7: `obj+0xFC` = `0x0215B720` / `0x0215B910` / `0x0215BAB8` on all 7 attackers (`jus-launcher-move-spot-check-hiyh`). | — pass that identifies which address is the table entry and which is a point inside the routine. |
| ~~Horizontal knockback recipe.~~ **Closed 2026-09-12** (`jus-lxyt`, [knockback-record-pointer-per-hit.md](../research/findings/knockback-record-pointer-per-hit.md)). Breaking at `0x020817EC` (one instruction after the `moveData` load, not on it) and dumping the pointer's bytes shows every Kakashi hit reads a real, byte-exact record — the "no matching record" mismatch was `move_records.py`/`chr_b-Complete-Mapping.md` reading the wrong **file**: Kakashi's (`chr_b` 23, confirmed live via the player-slot `+0x29` byte) collision records live in `na_b_04.bin`, not the `na_b_05.bin` the mapping table currently attributes to `chr_b` 23 (label superseded by E0 2026-10-18: `chr_b` 23 Kakashi is `na_b_04`; `na_b_05` is Kyuubi Naruto, `chr_b` 24). `raw_x/128 == record +0xC` holds exactly once the right file's record is used; the earlier "does not consistently hold" was comparing against the wrong record, not a real recipe deviation. `jus-idiy`'s "shortcut" (`new_val == kbX*128`) is also revised: it holds because every hit `jus-idiy` measured had a weight-neutral HP-band term `F_band=0x100`; this session's type-6 control (Kenshin `X`, `F_band=0x180`) confirms the real relation is `new_val == kbX*128*F_band/256` (`F_band` is the HP-band table entry from §4.2, not the object-base pointer `M` used elsewhere in this doc — same-letter collision in the earlier write-up, corrected here). **New, narrower open question**: is the `na_b_04`/`na_b_05` mismatch a Kakashi/Sakura-specific swap or systemic across the `na_b_0*` series — not answered by this session, filed separately. | — |
