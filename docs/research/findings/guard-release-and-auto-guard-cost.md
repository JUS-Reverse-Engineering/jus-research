# Human-input guard release is lock-gated, not the CPU's 122-frame hold; same for a post-block release; Auto-Guard-with-empty-SP still untested (no carrier savestate in an 8-state runtime check)

Tracker items: `jus-rsye`, `jus-pb6n`.

Grade: PLAUSIBLE (settled on the lock-vs-latency question; one data point on
the post-block question). Re-run 2026-09-12b closed three of the four gaps a
Refuter found in the first session: a 1-frame tap now separates the
lock-gated model from pure latency, a post-block release was measured, and
every run this time has a committed, gzipped `tail.jsonl`. Auto-Guard-with-
SP itself is still not run — no carrier savestate exists — but that absence
is now backed by a direct 8-state runtime bit-read (`obj+0x128 & 0x10`), not
just a name match against the helper-carrier list.

## Claim

1. **A human release is not subject to the CPU's 122-frame guard-hold**,
   whether or not the guard just blocked a hit. Releasing the guard input
   (`DOWN`) clears the "is-guarding" flag (`M+0x78` bit 26) and the guard
   state code (`obj+0x18` low byte → 0; word `0x303` → `0x3` → `0x30000`,
   upper halfword `0x1` → `0x3`, in the post-block run) within single digits to low double digits of
   frames of the button going up — never anywhere near 122 frames.
2. **Settled (2026-09-12b): the release is lock-gated, not purely latency.**
   A 1-frame tap (`DOWN` held for exactly one plan frame) separates the two
   competing models by 6 frames and landed on the lock-gated prediction:
   press+11, not the pure-latency press+5. The guard-entry lock
   (`obj+0x11A`, guard-sp.md §0.7) arms to 6 at press+3 and drains 1/frame
   regardless of button state; the flag/state cannot clear before the lock
   reaches 0 (press+9), and then adds the same ~2-frame tail seen in the
   original 5-frame-hold data point. Once the lock has long drained (the
   30-frame hold, reproduced again this session with a committed log), only
   the ~4-frame release latency remains.
3. **New (2026-09-12b): a post-block human release also clears quickly, not
   at 122 frames.** With the CPU set to attack (`COM設定 → 戦う`, confirmed
   this time by screenshot before and after the menu edit — see Evidence),
   a real blocked hit landed on P1 while guarding (`M+0x40 |= 0x1000`, gauge
   +4), and releasing `DOWN` 10 frames after that block cleared the guard
   flag 13 frames after the block — the same order of magnitude as the
   no-incoming-hit releases above, not the CPU's 122-frame value. This
   answers guard-sp.md §0.5 rule 4's TBD: **the 122-frame hold is CPU-AI
   behavior scripted into the "-guard" savestates, not a property the
   guard-state machine also applies to a human who just blocked.** This run's
   exact release-to-clear count is noisier than points 1–2 (an adaptive,
   multi-call driver was needed to catch the stochastic CPU's attack timing,
   introducing a few frames of boundary uncertainty — see Evidence) and
   should not be read as a precise new constant, only as ruling out the
   122-frame hold.
4. Measured hold/release pairs, all four data points:

   | hold | button released | flag/state off | frames button-up → off |
   |---|---|---|---|
   | 1 frame (tap) | +1 | +11 | 10 (lock-gated: lock reaches 0 at +9, then +2) |
   | 5 frames | +5 | +11 | 6 (lock had 4 frames left at release) |
   | 30 frames | +30 | +34 | 4 (pure latency, lock long drained) |
   | post-block (guard held well past lock-drain, then released) | block+10 | block+13 | ~2–3 (chunk-boundary uncertainty; see Evidence) |

## Evidence

`docs/research/feel-captures/guard-2026-09-12/RESULTS.md` §3 (original two
points) and
`docs/research/feel-captures/guard-2026-09-12b/RESULTS.md` §1–3 (1-frame tap,
30-frame reproduction with a committed log, post-block release). State
`pc-kenshin-npc-luffy-dark-tournament`, P1 (Kenshin) fighter object
`0x02228E80`, `M = 0x0220F30C` (resolved live via the documented
`[[obj+0x1A8]+0x10]` chain, physics.md §5). Instrument: `scripts/emu/
jusemu.py` `watch`/`tail --every 1`/`run`/`peek`, no GDB either session.

Every run in the 2026-09-12b session has a committed, gzipped `tail.jsonl`
(`docs/research/feel-captures/guard-2026-09-12b/logs/*.tail.jsonl.gz`),
closing the first session's `§0.1` logging gap.

**Post-block setup, screenshot-confirmed.** No pre-built savestate has the
CPU attacking P1 while P1 guards, so this session drove the in-battle pause
menu itself and checked it with `jusemu.py screendump`:
`../feel-captures/guard-2026-09-12b/logs/menu_check.png`
shows COM設定 = なにもしない right after opening the menu;
`menu_check2.png`,
taken after one `DOWN` (move to the COM設定 row) and one `A` (cycle the
value), shows COM設定 = 戦う. This is the visual confirmation the first
session's RESULTS.md said it could not get. With 戦う set, the CPU
approached and attacked within roughly 50–95 frames of resuming (measured
twice, non-deterministically — see the method note below), including at
least one guard shatter/break later in the same exploratory window
(`obj+0x18 → 8`, `M+0x40 |= 0x10000`, gauge reset to 0).

**Method note on the post-block run's timing precision.** CPU approach
timing is not frame-deterministic run-to-run from the same savestate and
scripted inputs (two otherwise-identical setups landed the first hit 47 and
87 frames apart), so a single upfront static plan cannot pre-target "release
10 frames after the block." The post-block run used an adaptive driver
(`logs/run3_postblock_driver.py`) that holds `DOWN` in 15-frame chunks,
inspects each chunk's newly appended tail rows for a real block while
actually guarding, then issues one final chunk holding `DOWN` through
`block_fc + 9`. Chunk boundaries are separate `jusemu.py run` calls, and the
bridge reverts input to neutral between calls ("physical input untouched" —
no override between plans), which produced a brief, real guard-drop/re-entry
cycle in the chunks *before* the one containing the qualifying block. The
reported block itself sits inside one continuous held chunk (no gap), so the
block detection and the +10 target are frame-exact; the release-to-clear
count carries a few frames of uncertainty from the real-time gap between the
detecting chunk's end and the follow-up call, and is reported honestly as
"~2–3, with uncertainty" rather than forced to match the frame-exact
precision of the other three data points. A follow-up with a single
continuous plan call spanning hold-through-release (once the block's
approximate timing is known from a first pass) would remove this gap.

**Positive controls.** Same first session, P2 (Luffy) side, fresh addressing:
a blocked Kenshin B jab set `M+0x40 |= 0x1000` and moved the gauge
`obj+0x102` from 0 to 5 (guard-sp.md §0.5 rule 1's documented block cost). The
2026-09-12b post-block run adds a second, independent block-cost control on
the *other* side of the matchup: a Luffy hit landing on Kenshin (P1, this
time the guarder) also set `M+0x40 |= 0x1000` with the gauge rising 4→8
(+4) — a different move's damage than the +5 Kenshin-on-Luffy control, as
expected, but the same mechanism, confirmed from both attacker/defender
roles now.

## Auto-Guard with empty SP — still not run, now with a direct 8-state check

**2026-09-12b adds a runtime confirmation, not just a name match.** Per the
assignment's own instruction (read the ability bit directly rather than
inferring from character names), 8 savestates with varied P1 characters
(Kenshin, Momotaro, Yusuke, Taikoubou, Kakashi, Muhyo, Sasuke, Eve; P2s
Luffy/Nami×2/Jotaro×5) were loaded and both fighters' `obj+0x128` read live
(`obj = *(0x021DEB3C)` for P1, `*(0x021DEB3C+4)` for P2; helpers.md §5).
**Bit `0x10` (ability 4, Auto-Guard) was clear on all 16 reads** — see
`docs/research/feel-captures/guard-2026-09-12b/RESULTS.md` §4 for the full
table and `logs/run4_autoguard_check.py` for the driver:

| P1 / P2 | P1 `obj+0x128` | P2 `obj+0x128` |
|---|---|---|
| kenshin / luffy | `0x6` | `0x2005200` |
| momotaro / nami | `0x600` | `0x1010008` |
| yusuke / nami | `0x0` | `0x1010008` |
| taikoubou / jotaro | `0x0` | `0x2000` |
| kakashi / jotaro | `0x2004` | `0x2000` |
| muhyo / jotaro | `0x1000000` | `0x2000` |
| sasuke / jotaro | `0x2004` | `0x2000` |
| eve / jotaro | `0x1000002` | `0x2000` |

Not 16 independent samples: five Jotaro P2 reads share one deck (`0x2000`)
and two Nami reads share another (`0x1010008`); Auto-Guard comes from
helper koma, so the deck is the real sampling unit, roughly 6 P1 decks and
3 P2 decks, not 16. This agrees with,
and now independently confirms by a different method, the name-match
conclusion from `docs/research/Passives-Reference.md` line 188 and
`docs/research/Helper-Passives-Catalog.md` line 140 (carriers: Genzo
Wakabyashi, Roberto Hongo, Kamesennin, Gaara, Biscuit Kruger, Captain Bravo,
Page, Genkai, Masa-chan, Nico Robin, plus Kyuubi Naruto and Tsuna+Reborn
noted elsewhere) and the identical conclusion an earlier session reached
independently
(`../feel-captures/sp-live-2026-09-12/SUMMARY.md`).
**This is still absence-of-evidence over a sample (8 of the full roster),
not proof no carrier state exists anywhere** — building a fresh carrier
state (deck edit, roster verification, a scripted "CPU hits while not
guarding, SP full vs. SP poked to 0" sequence) remains out of scope for this
session, per the brief's own skip-and-say-so instruction. The static
candidate stands unchanged: `0x0215EA40` (ov6 guard router), gated on
ability bitset bit `0x10` = ability 4, applies `amount = -0x3200` (half a
bar) via `0x020781E4`, with an affordability check at `0x020782AC`
(`sp-apply-0x020781E4-is-a-mixed-radix-pool-with-bar-count.md`) — static
only, no live confirmation exists yet in this campaign.

## Conditions

Fork commit `c26edf0e0d75364823856c9272a103fe39e03999`. Both sessions used
the Lua bridge only (`watch`/`tail`/`run`/`peek`), no GDB. 2026-09-12b did not
attempt a GDB attach at all (unlike the first session's tooling smoke test),
since nothing in this re-run's assignment needed "who writes this address."

## Open

- The post-block release's exact frame count (13 frames measured, ~2–3
  release-to-clear) carries chunk-boundary uncertainty; a single continuous
  plan call would tighten it once the CPU's approximate attack timing is
  known from a first pass.
- Auto-Guard, with and without SP, entirely (no carrier savestate found in
  either the name-match search or this session's 8-state runtime check).
- Whether any state outside the 8 checked here carries Auto-Guard on either
  fighter remains open (absence over a sample, not a roster-wide proof).
