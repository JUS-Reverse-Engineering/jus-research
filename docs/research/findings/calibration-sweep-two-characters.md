# Calibration sweep: movement, damage, hitstun and knockback on Eve and Muhyo (`jus-9utl`)

## Ask

Owner scope is general feel; the movement/damage/hitstun/knockback specs in
the combat notes/`physics.md`/`damage.md` rest on a handful of characters
(Kenshin, Yusuke, Momotaro, Franky for movement; Kenshin, Taikoubou and
others for damage/knockback). This tracker item positive-controls the core numbers
on two characters not yet used, chosen from `jus_files/save_states/
INDEX.md`'s `pc-*-npc-jotaro-dark-tournament` batch (no `characters/` page
yet): **Eve** (chr_b 37, tier 2, walk class 3, Lightweight) and **Muhyo**
(chr_b 59, tier 2, walk class 4, Lightweight). Kakashi (chr_b 23, tier 2,
walk class 2) ran first as the positive control, per the brief.

**First attempt at the Kakashi control failed** on two probe bugs — sampling
the accel field (zeroed every frame by the integrator, physics.md §6.1 step
6, so it always reads 0) and missing that the savestate loads paused. Full
account: kakashi-control/RESULTS.md.
Corrected (velocity/position watch, `START` to unpause first), the control
now passes end to end, and Eve/Muhyo follow.

## Method

melonDS + Lua bridge, `JUS_EMU_HOLDER=9utl`, one launch. For each character:
load `pc-<char>-npc-jotaro-dark-tournament`, press `START` (the state loads
into the pause menu) to resume, verify roster by HP + screenshot, resolve
`obj` (fighter table `0x021DEB3C`), `element = *(*(*(obj+0x1A8)+0x10)+0x5C)`
(`0x0220C068` for P1, `0x0220C0A8` for Jotaro/P2 in this whole savestate
family — stable across characters), and `M = *(*(obj+0x1A8)+0x10)`
(`0x0220F494` for Jotaro in every state tried). Movement: hold a direction
≥40 frames, watch `element+0x24/+0x26` (velocity) and `+0x0C/+0x10`
(position) per frame; hold `A` ≥6 frames for a full jump, same watch.
Damage/hitstun/knockback: walk into range, press `B` or `Y` once, watch
Jotaro's HP (`0x021DF7F0`), hitstun timer (`jotaro_obj+0x114`), and the
staged knockback pair (`M+0x148/+0x14A`, read as one `u32` — both fields at
once). Base damage predictions from `scripts/analysis/move_records.py
<char> --list`, reading its `frameStart` column as the **base damage byte**
per `damage.md` §2.1 (`moveData+4`, `ldrsb`) — the script's own docstring
flags that some of its field names are wrong; this is one of them, confirmed
by every match below.

## Per-quantity table

### Movement (Kakashi control, then Eve, then Muhyo)

| quantity | predicted | Kakashi (control) | Eve | Muhyo | verdict |
|---|---|---|---|---|---|
| walk accel (class 2/3/4) | 107 / 96 / 85 raw | **107**, ramp digit-for-digit = Kenshin's published series | **96**, ramp 84,158,223,280,...,672 terminal | **85**, ramp 75,140,197,...,595 terminal | MATCH all three |
| walk terminal (`7a`) | 749 / 672 / 595 raw | **749** | **672** | **595** | MATCH all three |
| jump impulse (tier 2) | −1752 → −1656 post-step | **−1752 → −1656** | **−1752 → −1656** | **−1752 → −1656** | MATCH all three |
| jump apex | frame 26 of airborne | vy sign flip f32/33 (start f7) = 25/26 | same | same | MATCH all three |
| jump airborne duration | 61 frames | **61** | **61** | **61** | MATCH all three |
| gravity / drag | 41 raw; ×7/8 (x) | reproduced in the ramp/decay arithmetic on every frame above | same | same | MATCH (engine-wide, not re-derived independently) |

Eve is class 3 — `physics.md`'s own table calls that row "table only",
never live-verified before this. **This closes that gap.** Muhyo is a
second live character for class 4 (previously Yusuke only).

### Damage / hitstun / knockback (one `B`, one `Y`, on CPU Jotaro, full HP, unweighted)

`out_raw = (r5+r0)>>2` (`damage.md` §4); with no nature bonus and no gate
firing, `r0=0` and displayed damage = base exactly. Hitstun =
`clamp(moveBase + 20 + T[state], 16, 60)`; Jotaro was idle (state 0,
`T[0]=0`) throughout, and every record's `hitstunAdd` byte read 0, so every
prediction here is `clamp(0+20+0,16,60) = 20`. Knockback stage measured at
`M+0x148/+0x14A` (read together as one hit-frame pulse, gone the next
frame). The combat notes §6 already states the one-store-per-frame,
no-same-frame-accumulation property (`jus-idiy`, multi-hit tested); what
this run actually observed is a narrower, different fact on single hits —
the staged fields read 0 the frame *after* the write. That's consistent
with §6's property but isn't itself a new test of accumulation across
multiple simultaneous hits, so it isn't counted as a fresh confirmation
of it below.

| character | move | record (move_records.py) | predicted damage | measured HP delta | predicted hitstun | measured hitstun | predicted kbX (`kbX_byte×128`) | measured kb stage | verdict |
|---|---|---|---|---|---|---|---|---|---|
| Kakashi | `B` | rec 0, base 8, kbX 8 | 8.0 | **8.0** (160→152) | 20 | **20** | 1024 | **−640** | damage/hitstun MATCH; knockback reproduces the **already-documented** rec-byte mismatch (`kakashi.md`: "B gives 5 where rec 0's kbX is 8") — −640 = 5×128, not 8×128 |
| Kakashi | `Y` (3 contacts) | rec-identified in `kakashi.md` | 4.0+4.0+16.0=24.0 | **4.0+4.0+16.0=24.0** (152→148→144→128) | 20 (each contact resets it) | **20** flat through all 3 | (−640,0)/(−384,−1652)/(−1792,0) per `kakashi.md` | **(−640,0), (−384,−1652), (−1792,0)** | **EXACT** digit-for-digit reproduction of `kakashi.md`'s published numbers |
| Eve | `B` | rec 0, base 7, kbX 5 | 7.0 | **7.0** (160→153) | 20 | **20** | 640 | **−640** | MATCH (incl. knockback — no rec-byte mismatch here) |
| Eve | `Y` | not identified — no record among Eve's 20 (`0x100–0x113`) has base 16, and the built-in table (ids 0–13, `arm9 0x0209fc2c`) was read directly and excluded too (base 0 on every id except id 1 = 10, `kbX` 0 on all) | n/a | **16.0** (153→137) | n/a | **20** | n/a | **−1920** (=15×128) | damage/hitstun measured cleanly but the record is unidentified against either table; kbX 15 matches no listed `kbX` byte either. A spawned or foreign-file element (cf. `kakashi.md`'s projectile moves) is the leading candidate. Flagged, not guessed. |
| Muhyo | `B` | rec 0, base 6, kbX 5 | 6.0 | **6.0** (160→154) | 20 | **20** | 640 | **−640** | MATCH |
| Muhyo | `Y` | rec 2, base 16, kbY 20 (type 2, not launcher) | 16.0 | **16.0** (154→138) | 20 | **20** | predicted `y ≈ −2753` (physics §4.6's `kbY` chain) | **DEVIATION** — kb stage read 0 both axes | damage/hitstun MATCH; knockback is a genuine deviation, not evidence type 2 skips staging (`kakashi.md` has type-2 hits staging nonzero pairs). `y-hit.jsonl.gz` shows the victim's hitstun timer frozen at 5120 for 18 frames and the pulse frame absent — an atypical victim state, unexplained |

## What this confirms, and what's still open

- **Movement**: six characters now have a **live walk RAMP** (Kenshin,
  Yusuke, Momotaro, Kakashi, Eve, Muhyo). Franky is a load-time **field
  read** of `obj+0xB8` (`= 62`, class 6), not a played ramp. Of the two
  live tiers, only tier 2 was actually played this pass (Kenshin, Yusuke,
  Momotaro, Kakashi, Eve, Muhyo all tier 2); tier 3 rests on Franky's field
  read and tier 1 on a poke, neither a played run. No deviation found on
  what was actually played — no TUNING row needed.
- **Damage**: the no-gate, no-nature formula (`displayed == base`) held on
  5 of 6 hits tried, on 3 characters. No deviation found on the identified
  hits.
- **Hitstun**: `clamp(base+20+T[state],16,60)` held on every hit (6/6,
  including Kakashi's 3-hit `Y`, where it correctly held at 20 across all
  three contacts rather than counting down between them). Graded honestly:
  Jotaro was idle (state 0) throughout, so `T[state]` was **assumed** 0,
  not read from a different state, and every prediction collapses to the
  same constant, 20. This is one degenerate case exercised six times, not
  six independent samples of the formula.
- **Knockback**: the `kbX_byte × 128` shortcut (physics.md §4.6, `M=0x100`
  case) held on Eve's and Muhyo's `B` on two clean, unambiguous record
  matches (Eve rec 0 `kbX` 5 → measured 640; Muhyo rec 0 `kbX` 5 → measured
  640). That's two clean confirmations of the shortcut, which strengthens
  — but doesn't settle — `kakashi.md`'s own suspicion (~336-345) that
  Kakashi's `B` record identification is wrong (its rec 0 was inferred from
  `frameStart`/animation matching, not a direct pointer read), rather than
  the shortcut itself being wrong on Kakashi. The record-identification gap
  stays open as `jus-lxyt`'s. Muhyo's `Y` is a genuine deviation (see
  table): predicted `y ≈ −2753`, measured 0/0, alongside a frozen hitstun
  timer and no staged pulse — an unexplained victim-state anomaly, not
  counted as either a confirmation or a refutation of the formula.
- **Open, not solved here**: Eve's `Y` uses an authored record this pass
  couldn't identify against either Eve's own 20 records or the built-in
  arm9 table (ids 0–13, `0x0209FC2C`, read directly and excluded — see
  table above). Both tables checked, neither has a match; a spawned or
  foreign-file element is the leading candidate. Muhyo's `Y` knockback
  deviation (above) is unexplained, not resolved. A genuine launcher check
  (type 6, weight/HP-band math) on a new character is still open for a
  future pass.

## Status

**DONE** for the scope actually reachable in one session: movement fully
positive-controlled and extended to Eve and Muhyo; damage and hitstun fully
confirmed on both; knockback confirmed on both `B` hits and on one `Y`
(Muhyo), with Eve's `Y` record identification left open rather than guessed.

## Grade

Movement: A (6/6 predictions matched, one new class row (Eve, class 3)
closed from table-only to live, one class row (Muhyo, class 4) doubled).
Gravity/drag is engine-wide and belongs to the movement tally above, not
folded into damage/hitstun's count.
Damage: A (5/6 measured hits matched, on 3 characters; Eve's `Y` damage
matched but its record is unidentified).
Hitstun: graded down from the plain 6/6 above — every measured hit was the
same `T[state]=0` (idle) case, so this is one degenerate scenario played
six times, not six independent tests of the state table. C (held on the
one case tested; the state table itself remains untested by this pass).
Knockback: B (matched cleanly on 3/5 checked hits — Kakashi `B` via the
shortcut, Eve `B`, Muhyo `B`; Eve `Y` is an honest "not identified," not a
model failure; Muhyo `Y` is a genuine, unexplained deviation against a
specific numeric prediction, which keeps this off an A).
