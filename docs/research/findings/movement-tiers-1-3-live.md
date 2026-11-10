# Jump tiers 1 and 3: closing the poke-only gap with real characters (`jus-wthh`)

## Ask

`jus-wthh` (child of `jus-atns`): the combat notes §3 graded movement
"Partial" for one reason only — walk, dash, fast-fall and landing lag were
each already confirmed on 3+ characters, but the tier-1 and tier-3 jump
impulses (`physics.md` §6.4) had only ever been **poked** onto a Kenshin
(tier-2) object (`jus-tier-1-tier-3-jump-arcs-0mq1`), never measured on a
real played tier-1/tier-3 character. This tracker item runs that measurement.

## Method

Same method as `jus-9utl`'s
[calibration-sweep-two-characters.md](calibration-sweep-two-characters.md):
melonDS + Lua bridge, one `JUS_EMU_HOLDER=wthh` launch, `A` held ≥6 frames
from a loaded battle state, `element+0x26`/`+0x10` (velocity/position)
watched per bridge frame. Positive control ran first on Kakashi (tier 2,
reproduces the already-published numbers exactly — see
kakashi-control/RESULTS.md),
including a **procedure correction**: this savestate family needs **no**
`START` press before driving it (a fresh load already shows the resumed
battle screen; pressing `START` opens the pause menu instead of closing
one — the reverse of what the `jus-9utl` `kakashi-control` doc found for
this same family). The control's walk ramp and jump arc both reproduce the
documented numbers to the frame after dropping the `START` press.

## Character selection (static, chr_b.bin)

Read directly via `scripts/extract_character_data.py`'s
`read_battle_character_entry` against
`jus_files/ripped_jus_files/bin/chr_b.bin` (`tier = data[offset+1]`). Tier
distribution: `{1: 11 characters, 2: 56, 3: 7}`. Cross-referencing tier-1 and
tier-3 rows against `jus_files/save_states/INDEX.md`'s `pc-*` batch (states
where the target character is P1/active, not just an NPC victim) found
**exactly one candidate for each tier**:

- **Tier 1: Sasuke** (`chr_b` 21) — active in
  `pc-sasuke-npc-jotaro-dark-tournament`.
- **Tier 3: Raoh** (`chr_b` 62) — active in `pc-raoh-npc-luffy-j-arena`
  (the only tier-3 character active, rather than an NPC victim, in any
  existing state).

Both names resolved against
[chr_b-Complete-Mapping.md](../chr_b-Complete-Mapping.md) before being
written here. No other tier-1 or tier-3 character has a save state where
they are the played character — see Gaps below.

## Per-quantity table

Airborne duration is counted as `landing frame − first airborne frame`
(inclusive of the airborne frames where `vy` passes through exactly 0, e.g.
the single apex frame); this is the same convention the poke logs
(`mv16-tier1-poke.jsonl.gz`, `mv17-tier3-poke.jsonl.gz`,
`docs/research/feel-captures/movement-2026-09-02/`) use once re-derived
frame-for-frame — see Retraction below. Apex offset is counted 1-based from
the first airborne frame, first frame with `vy >= 0`.

| Quantity | Tier | Predicted (poke, `physics.md` §6.4) | Measured (real character) | Verdict |
|---|---|---|---|---|
| Jump impulse (raw, static `obj+0xBA`) | 1 (Sasuke) | −1816 | **−1816** | MATCH |
| Jump impulse (raw, static `obj+0xBA`) | 3 (Raoh) | −1689 | **−1689** | MATCH |
| `vy` after first integrator step | 1 (Sasuke) | −1718 | **−1718** | MATCH |
| `vy` after first integrator step | 3 (Raoh) | −1595 | **−1595** | MATCH |
| Peak height | 1 (Sasuke) | 79.17 px | **79.17 px** | EXACT MATCH |
| Peak height | 3 (Raoh) | 70.57 px | **70.57 px** | EXACT MATCH |
| Apex offset from airborne start | 1 (Sasuke) | 27 frames | **27 frames** | EXACT MATCH |
| Apex offset from airborne start | 3 (Raoh) | 26 frames | **26 frames** | EXACT MATCH |
| Airborne duration | 1 (Sasuke) | 63 frames | **63 frames** | EXACT MATCH |
| Airborne duration | 3 (Raoh) | 60 frames | **60 frames** | EXACT MATCH |

(Tier 2, Kakashi, control: impulse −1752 → −1656, 61 frames airborne, 74.68 px
peak — all exact, per the control doc.)

## Retraction: the "+1-frame airborne-duration deviation" does not exist

An earlier pass of this finding reported a genuine +1-frame airborne-duration
deviation (poke 62/59 vs. live 63/60) and a stale 79.14 px peak-height
prediction for tier 1. Both were counting artifacts, not physics
differences, caught by a Refuter re-deriving the poke logs frame-for-frame:

- The poke logs (`mv16-tier1-poke.jsonl.gz`, `mv17-tier3-poke.jsonl.gz`)
  give the exact same `landing − first-airborne` durations as this tracker item's
  live runs — **63 frames (tier 1), 60 frames (tier 3)** — once every
  airborne frame between the first-airborne frame and landing is counted.
  The earlier poke report's 62/59 counted only frames with `vy != 0`; tier-1
  and tier-3 arcs have exactly one frame where `vy` lands on exactly 0 (the
  apex frame), so counting `vy != 0` frames undercounts the true airborne
  span by one. The tier-2 control arc has no exact-zero apex frame, which is
  why the discrepancy never showed up there and went unnoticed until this
  tracker item re-derived the raw logs.
- Sasuke's peak height was reported against a stale `79.14 px` poke
  prediction; the poke's own raw sample is `(172031 − 151763)/256 =
  79.171875 px` (rounds to **79.17 px**, not 79.14), and the tier-1 live run
  lands on the same value. There is no quantization gap — this was a
  transcription error in the earlier write-up, now corrected at its source
  (`docs/confirmed-facts/physics.md` §6.4).
- Apex offset is restated under the poke report's own counting convention
  (first frame with `vy >= 0`, 1-based from the first airborne frame):
  Sasuke **27**, Raoh **26** — exact matches against the poke, not
  "within rounding."

Re-derived directly from the committed logs: the live `(y, vy)` arcs
(`docs/research/feel-captures/movement-tiers-2026-09-12/sasuke/runs/jump-arc.jsonl.gz`,
`.../raoh/runs/jump-arc.jsonl.gz`) are **bit-identical** to the poked arcs
(`docs/research/feel-captures/movement-2026-09-02/mv16-tier1-poke.jsonl.gz`,
`mv17-tier3-poke.jsonl.gz`) for all 66 frames of the jump (frame the impulse
lands through landing), on both characters. This is a stronger result than
the original ask: the poke is not merely "arithmetically right" — it is a
full-arc validation on real objects. The poke's numbers in
`docs/confirmed-facts/physics.md` §6.4 needed a counting-convention footnote and one corrected peak-height
cell, not a TUNING row; both are fixed at the source table, with the
convention stated next to it (`jus-wthh`).

## Gaps

- **Only one live-playable character exists per tier in the current save-state set.** Tier 1 has 11 chr_b rows and tier 3 has 7, but scanning
  `jus_files/save_states/INDEX.md` for states where a tier-1 or tier-3
  character is the *active* (P1) fighter rather than an NPC victim turned up
  exactly one match each (Sasuke, Raoh). Reaching 3 real characters per tier,
  as the tracker item's ideal target states, needs new save states built from
  scratch (a menu-driven deck/roster build) — explicitly out of scope for
  this pass per the brief ("choose the nearest available character and NOTE
  THE GAP rather than building new save states this pass"). This finding
  closes the "poke-only, zero real characters" gap to "one real character
  each," which is enough to move the combat notes §3's tier-1/tier-3 caveat from
  "poke-measured only" to "one real character confirmed, more would
  strengthen it further" — see the combat notes update.
- Dash, fast-fall and landing lag were not re-measured this pass:
  the combat notes §3's own Portability note already listed them as confirmed on
  3+ characters before this tracker item started, and the brief's scope was framed
  around the specific remaining blocker (tier-1/tier-3 jump), which this
  finding closes to the extent the current save-state set allows.

## Status

**PARTIAL** (by the tracker item's own >=3-characters-per-rule target; **DONE** for
the actual blocker the combat notes §3 named). Tier-1 and tier-3 jump impulses,
post-step `vy`, peak height, apex offset and airborne duration are now each
confirmed exact matches on one real played character instead of zero; the
live arcs are bit-identical to the poke's own logs for the full jump,
promoting the poke from an arithmetic-only proof to a full-arc validation on
real objects (`jus-wthh`, retraction above). Reaching 3 characters per tier
needs new save states, flagged above as a gap rather than attempted this
pass.

## Grade

Jump tier 1/3: A− — every measured quantity (impulse, post-step vy, peak
height, apex offset, airborne duration) is an exact match on the one
character each currently available to test, and the live arcs are
bit-identical to the poke's logs for the full jump; held off an A only
because the tracker item's >=3-characters-per-tier target is not met (Gaps above).
