# Mobility passives (Triple Jump, Wall Jump, Air Dash): the ability-bit gates, static trace

Tracker items: `jus-utus`.

## Grade: CONFIRMED_STATIC (bit addresses, gate conditions, wall-jump impulse), no Codex cross-check this pass / [unverified] (air-dash burst record, wall-touch bit semantics)

Static analysis only — no emulator, no GDB, per this ticket's scope. Raw evidence,
full disassembly listings, and the addressing-scheme grep table:
../feel-captures/mobility-passives-2026-09-12/RESULTS.md.
Codex second opinion was attempted but did not complete — see
../feel-captures/mobility-passives-2026-09-12/codex_second_opinion_mobility.md.
Everything below is a single-reviewer static trace, not yet independently
cross-checked.

## Conditions

- Static analysis against the checked-in ROM extraction and disassembly
  (`jus_files/analysis/disasm/ov6.txt`), read with `scripts/analysis/disasm_range.py
  --overlay 6` for every address cited; a small skip-on-stall wrapper around the
  same tool was used to get past literal-pool gaps in longer ranges (documented in
  the RESULTS.md preamble), and every finding was re-confirmed with the plain
  checked-in tool on the specific address it lands on.
- Builds on `docs/confirmed-facts/helpers.md` §5 (the ability bitset's addressing
  formula and ability-id catalog: 1 = Triple Jump, 2 = Wall Jump, 3 = Air Dash) and
  `docs/confirmed-facts/physics.md` §6.1/§4.5/§6.3/§6.4/§6.6 (the movement
  integrator's fields, the state-code enum, the dash-burst setup, the jump-impulse
  tier table, and the landing-lag budget formula) — cited, not re-derived.
- One input bit citation reused from `docs/confirmed-facts/guard-sp.md:275`
  (`obj+0x6C` bit `0x10` = A).

## The gate table

| passive | ability id | bit @ `obj+0x128` | gate pc | effect pc | field | magnitude source |
|---|---|---|---|---|---|---|
| Triple Jump (３段ジャンプ) | 1 | `0x02` (bit 1) | `0215726C` (ability-load apply site, not re-checked every frame) | `0215727C` sets `obj+0xD8=2`; jump-side inline budget check `0215E28C`–`0215E2A4` inside `0215E1D0`; jump write at `0215E38C` | `obj+0xD8` = max extra air actions (default 1, `02158A58`; this ceiling is **never reset**, only installed by these two writers); `obj+0xD9` = used this hop, reset on **touchdown** by `0215D53C` (called from state-0/state-13 handlers `0215D3B4`/`0215D564`, not from a fresh ground-jump start; a second mid-air reset lives in the state-15 handler `0215E4AC` at `0215E4F4`–`0215E4FC`, meaning of state 15 [unverified]) | literal `2` in apply code; jump magnitude = existing tiered table `obj+0xBA` (`docs/confirmed-facts/physics.md` §6.4), unhalved, full re-application |
| Wall Jump (三角飛び) | 2 | `0x04` (bit 2) | `0215E1F8`, re-checked every airborne A-press | `0215E280` commits pending state 5; delayed impulse at `0215E420`/`0215E444` (4-frame windup, `obj+0x1E8` 12→8) | `obj+0xDC` = uses this hop, reset on touchdown by `0215D53C` (reaches `2` after one wall jump — incremented once at the gate, `0215E270`, and again at the commit handler's wall branch, `0215E33C`); `obj+0xDD` = push direction ±1 from `M+0x78` (`[[obj+0x1a8]+0x10]+0x78]`, the existing ColPrm flags word, not a new field) bits `0x4`/`0x8`, invalid if `0x400` set | horizontal: literal `0xA00` (2560 raw) × direction; vertical: `obj+0xBA` (existing tiered jump table) **halved** via `asr 1` (round-toward-zero, tier 3 → **−844**) |
| Air Dash (空中ダッシュ) | 3 | `0x08` (bit 3) | `0215E024`, re-checked every airborne A-press, after the wall-jump attempt fails | reaches the **dash entry** `0215D860` (not a jump-shared gate — see below), commits pending state 2 (dash) via `0x2157494` with `r1=2`, installs handler `0215D91C` — the same install site/handler the ground dash reaches | shares `obj+0xD8`/`obj+0xD9` with Triple Jump — same two fields, but its own inline check inside `0215D860`, incrementing `obj+0xD9` at `0215D960` when airborne (skipped when grounded) | **[unverified]** — commits to the generic dash state (2) via the same handler the ground dash uses; whether the burst reuses the ground dash's `rec[2]<<5`/12-frame table (`docs/confirmed-facts/physics.md` §6.3) or a distinct record slot was not traced this pass |

All three gates read the word at `obj+0x128` (`obj` = the fighter object itself,
register `r4`/`sl` throughout movement code — no double indirection through a
separate "battleObj"; `docs/confirmed-facts/helpers.md` §5's "base = battleObj+0x120" language refers to
the same fighter object). Confirmed by re-deriving the addressing arithmetic from
the bitset builder and bit-setter (RESULTS.md §0) rather than assuming
`docs/confirmed-facts/helpers.md`'s wording.

## What each passive actually does, mechanically

**Triple Jump** doesn't add a third code path. It raises a single shared
"extra air action" ceiling from 1 (baseline double jump) to 2. That ceiling,
`obj+0xD8`, is **never reset** — it only has two writers, the default and
Triple Jump's apply site. What resets per hop is the used-counter `obj+0xD9`,
and the reset fires on **touchdown** (`0215D53C`, reached from the state-0/
state-13 handlers), not on a fresh ground jump starting. The budget check
itself is not one shared gate function: the jump-input path inlines its own
copy at `0215E28C`–`0215E2A4` inside `0215E1D0`, and the air-dash path
reaches a separate function, the dash entry `0215D860` (below), which
inlines the identical check. Both read the same two fields, so Triple
Jump's ceiling benefits either consumer, but there is no single call target
both share. "３段ジャンプ" (3-stage jump) = ground jump + two grants of the same
mechanism the game already uses for a plain double jump. The jump write on a grant
is a full, unhalved re-application of `obj+0xBA` (the character's existing tiered
jump-impulse constant, `docs/confirmed-facts/physics.md` §6.4) — this statically confirms
`docs/confirmed-facts/physics.md` §6.4's runtime note that a second `A` "applies a fresh full impulse
mid-air whatever the first was," and locates the write site (`0215E38C`) and the
landing-lag `+9` write (`docs/confirmed-facts/physics.md` §6.6's `9 × (double-jumped?1:0)` term, write
site `0215E3A0`–`0215E3A8`).

**Wall Jump** is a distinct trigger, not a variant of the shared jump gate — it is
tried *first*, and only falls through to the double/triple-jump budget check if
the ability is absent, the wall isn't touched, or the once-per-hop slot
(`obj+0xDC`) is already spent. Trigger: A pressed while airborne (`obj+0x6C`
bit `0x10`), ability bit 2 present, `obj+0xDC == 0`, and `M+0x78`
(`[[obj+0x1a8]+0x10]+0x78]` — the existing ColPrm flags word §4.5/the combat notes
§2/§8 already document as rebuilt every frame by arm9, not a new field) reads a
wall-touch bit (`0x4` one side, `0x8` the other) with `0x400` clear. On
success it commits state 5 (the same state code the plain double jump uses —
"double-jump start" per `docs/confirmed-facts/physics.md` §4.5's enum, so the
engine treats a wall jump as a variant of that state, distinguished at commit
time by whether `obj+0xDD` (push direction) is nonzero). The impulse itself
is **delayed 4 frames** (`obj+0x1E8` counts 12→8, one decrement per frame the
state-5 handler runs, impulse fires when it reaches 8) and applies:

- horizontal: `dir × 0xA00` (2560 raw ≈ 10.0 px/frame) into `element+0x2C`
  (the movement integrator's vx-accel-this-frame field, `docs/confirmed-facts/physics.md` §6.1 step 1)
- vertical: `obj+0xBA` (the tiered jump impulse) **halved**, arithmetic-shift-right
  by 1 after a round-toward-zero adjustment (`add r1,r3,r3,lsr#31; asr r1,r1,#1`),
  into `element+0x2E` (the same field the ground/full jump writes)

Using the already-published tier table (`docs/confirmed-facts/physics.md` §6.4): tier 1 −1816→−908,
tier 2 −1752→−876, tier 3 −1689→**−844** (asr rounds toward zero: `(−1689 + 1)
asr 1 = −844`, not −845; halves of the existing published values, not
independently re-measured). `obj+0xDC` is incremented twice on a wall-jump
commit frame (`0215E270` and `0215E33C`), so it reads `2` after one wall
jump, not `1`. The commit frame also flips the fighter's facing via arm9
`0x02083950` (called at `0215E310`–`0215E328`).

**Air Dash**'s ability bit gates whether it reaches the dash entry
(`0215D860`, shared with the ground dash — same install site, same handler
`0215D91C`) when a dash input is read while airborne; that entry inlines its
own `obj+0xD8`/`obj+0xD9` check — the same two fields Triple Jump raises,
but its own inline copy, not a call into the jump path's inline check — and
a successful grant commits the generic dash state (2) rather than writing
any dash-specific velocity directly at the gate site. This means Air Dash
and Triple Jump/double-jump
**compete for the same single per-hop resource** — whichever the player triggers
first on a given airborne trip consumes it, and the other becomes unavailable for
the rest of that hop. Raising the Triple Jump bit to get `obj+0xD8=2` therefore
also grants a second usable air dash (or a mix of one jump + one dash), since both
draw from the same two fields via their own inline checks — this is inferred
from the shared fields, not independently exercised per-passive-combination.

## What a live run must add

This pass is static-only and does not confirm any of the following against real
gameplay:

- **Carriers.** No `chr_b` record or koma-helper carrier was checked this pass for
  ids 1/2/3 — `docs/confirmed-facts/helpers.md` §4/§9 already documents the general on-disk ability-list
  mechanism; a live run should read `obj+0x128` on a save state where the roster
  entry (`jus_files/save_states/INDEX.md`) is known to carry (or not carry) each of these three ids, and
  confirm the bit reads 1 accordingly before and after a KO/respawn re-cache
  (`docs/confirmed-facts/helpers.md` §5's "bitset is re-cached in place on KO/respawn" caveat applies
  here too, untested for these three ids specifically).
- **Extra jump count.** Poke or observe `obj+0xD8` on a carrier vs. non-carrier —
  static trace predicts `1` without the ability, `2` with it, and predicts a
  character can chain ground-jump + 2 extra grants (3 total airborne segments) only
  with the ability present.
- **Wall-jump impulse.** A live capture reading `element+0x2C`/`+0x2E` on the frame
  `obj+0x1E8` reaches `8` after a wall-jump input should show vx accel exactly
  `±2560` raw and vy impulse exactly half the character's tier value from
  `docs/confirmed-facts/physics.md` §6.4's published table (tier 2: `−876`). The predicted 4-frame
  windup (`obj+0x1E8` visibly counting 12,11,10,9,8 across 5 frames from wall
  contact) is also falsifiable live and was not checked here.
- **Air-dash burst.** A live capture of `vx` across the frames after a successful
  air-dash grant, compared against the ground dash's already-measured 384-raw/12-
  frame ramp (`docs/confirmed-facts/physics.md` §6.3), would settle whether air dash is the identical
  burst or a distinct record — the single biggest open item from this pass.
- **Shared-budget interaction.** A live run alternating a double jump then an
  air-dash attempt (or vice versa) on a carrier of both abilities, within the same
  airborne trip, should show the second action denied — falsifiable directly
  against `obj+0xD9` reaching `obj+0xD8`.
- **Wall-touch bit semantics.** Which literal side `0x4` vs `0x8` corresponds to,
  and what `0x400` actually represents, are inferred from control flow only; a live
  capture of `[[obj+0x1a8]+0x10]+0x78]` while standing against a real left vs.
  right wall would settle this.

## Sources

- `docs/confirmed-facts/helpers.md` §5 (bitset addressing, ability catalog)
- `docs/confirmed-facts/physics.md` §4.5 (state-code enum), §6.1 (integrator
  fields), §6.3 (dash burst setup), §6.4 (jump tier table, double-jump runtime
  note), §6.6 (landing-lag budget formula)
- `docs/confirmed-facts/guard-sp.md:275` (input bit map, A = `0x10`)
- Raw disassembly and the full addressing-scheme grep:
  `../feel-captures/mobility-passives-2026-09-12/RESULTS.md`
- Codex second opinion:
  `../feel-captures/mobility-passives-2026-09-12/codex_second_opinion_mobility.md`
