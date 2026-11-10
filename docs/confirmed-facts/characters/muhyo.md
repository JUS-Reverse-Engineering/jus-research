# Muhyo (`chr_b` 59, `mr_b_01`)

Tracker item `jus-9utl` (calibration sweep, positive-controlled on Kakashi first —
see kakashi-control/RESULTS.md
and [calibration-sweep-two-characters.md](../../research/findings/calibration-sweep-two-characters.md)).
This page carries only the rows that sweep measured — a movement/damage/
hitstun/knockback spot check, not a moveset map. `chr_b` index 59 confirmed
live via a battle screenshot showing the on-screen name "MUHYO" next to
this state's P1 character (committed:
muhyo/name-plate.png),
agreeing with both `chr_b-Complete-Mapping.md` and `character-index.json`.

## Identity

| Field | Value | Source |
|---|---|---|
| Character | Muhyo | live screenshot ("MUHYO" name plate, committed), `chr_b-Complete-Mapping.md` |
| Series | Muhyo to Rouji no Mahouritsu Soudan Jimusho | `chr_b-Complete-Mapping.md` |
| `chr_b` index | 59 | `chr_b-Complete-Mapping.md` |
| File prefix | `mr_b_01` | `chr_b-Complete-Mapping.md` |
| Walk-accel class byte (`chr_b+0x02`) | 4 | read directly from `chr_b.bin`, confirmed live (`obj+0xB8 = 85`) |
| Tier byte (`chr_b+0x01`) | 2 | read directly from `chr_b.bin`, confirmed live (`obj+0xBA = -1752`) |
| Weight | Lightweight (gate bit 15) | `chr_b-Complete-Mapping.md` §weight table |

## Measurement conditions

| Item | Value | Tracker item |
|---|---|---|
| Capture/state | `pc-muhyo-npc-jotaro-dark-tournament` | `jus-9utl` |
| Emulator build | `scripts/emu/build_info.json`, commit `c26edf0e...` | `jus-9utl` |
| ROM hash | `scripts/emu/hashes.json` | `jus-9utl` |
| Attacker | Muhyo (P1), full HP, standard/no items | `jus-9utl` |
| Victim | Jotaro (P2, CPU "do nothing"), 160.0 HP | `jus-9utl` |
| Geometry | Melee range, both grounded, P1 approaching from the right | `jus-9utl` |
| Measurement method | Fighter-object/element live reads (`physics.md` §5/§6.1), per-frame `jusemu.py run` watch logs | `jus-9utl` |

## Movement

| Quantity | Predicted (`physics.md` §6.2/§6.4, class 4 / tier 2) | Measured | Verdict |
|---|---|---|---|
| Walk accel | 85 raw/frame | **85** (`obj+0xB8`, and reproduced in the live ramp) | MATCH — second live character for class 4 (previously Yusuke only) |
| Walk terminal (`7a`) | 595 raw = 2.32 px/frame | **595** | MATCH |
| Jump impulse | −1752 (tier 2) | **−1752** (`obj+0xBA`), −1656 after the first integrator step | MATCH |
| Jump airborne duration | 61 frames | **61** | MATCH |

Raw ramp (per-frame `element+0x24`, RIGHT held from frame 0): 0, 0, 0, 75,
140, 197, 247, 291, 329, 363, 392, 418, 441, 461, 478, 493, 506, 518, 528,
537, 545, 552, 558, 563, 567, 571, 574, 577, 580, 582, 584, 586, 588, 589,
590, 591, 592, 593, 594, 595 (terminal, held). Raw logs:
calibration-2026-09-12/muhyo/runs/walk-ramp.jsonl.gz,
jump-arc.jsonl.gz.

## Normal moves (spot check only — not a moveset map)

| Input | Condition | Damage | Hit type | Hitstun | Knockback (staged `M+0x148/+0x14A`) | Tracker item |
|---|---|---:|---|---:|---|---|
| `B` | grounded, melee range, victim full HP | **6.0** (predicted 6.0 exactly, no gate/nature) | non-launcher | **20** (predicted `clamp(0+20+0,16,60)=20`) | −640 (matches `kbX_byte 5 × 128` exactly) | `jus-9utl` |
| `Y` | grounded, melee range, victim full HP | **16.0** (predicted 16.0 exactly) | non-launcher (type 2; `kbY`-only record) | **20** | **DEVIATION** — 0/0 measured against a predicted `y ≈ −2753` (`kbY 20`, physics §4.6's chain: `y = kbY·−158·F>>8`, then `×223/256`, `F=0x100`) | `jus-9utl` |

Both moves resolve cleanly to `mr_b_01.bin` records via
`scripts/analysis/move_records.py muhyo --list`: `B` = record 0 (kind 3,
type 1, base 6, `kbX` 5); `Y` = record 2 (kind 2, type 2, base 16, `kbY`
20, `kbX` 0). The combat notes §6.10 already documents Muhyo's forward+`Y` as a
separate move (a pop, type 5) — this plain `Y` is a different input from
that one. **The 0/0 knockback stage is a deviation, not a confirmation
that type 2 skips the launcher stage** — `kakashi.md` has type-2 hits
staging nonzero pairs on the same `M+0x148/+0x14A` (`air Y` `(+1280,0)`,
`up B` `(−512,−1652)`, `side Y` `(−384,−138)`), and the combat notes §6 says
every hit writes one store per frame. `y-hit.jsonl.gz` shows the victim
in an atypical state instead: the hitstun timer (`hitstun2`) is frozen at
5120 (20.0) for 18 frames (frames 26–43) and never decrements, and the
staged-knockback pulse frame is entirely absent (`kb2` reads 0 every
frame). That's an unexplained victim-state anomaly, not evidence the
formula doesn't apply to type 2. Marked DEVIATION / unexplained; not
folded into the "confirmed" tally. Raw logs:
b-hit.jsonl.gz,
y-hit.jsonl.gz.

## Not yet measured

| Question | Why it matters | Tracker item |
|---|---|---|
| A launcher (type 6) hit's `M+0x148` staging, weight/HP-band scaling | This sweep's two hits were both non-launcher; the staged-knockback formula's weight/HP-band terms weren't re-exercised on Muhyo | `jus-9utl` follow-up |
| Everything else in a full moveset map (specials, air normals, guard behavior) | Out of this tracker item's scope (a calibration spot check, not full moveset mapping) | not filed |

## Sources

| Source | Purpose | Tracker item |
|---|---|---|
| [calibration-sweep-two-characters.md](../../research/findings/calibration-sweep-two-characters.md) | Full per-quantity table, both characters, positive control | `jus-9utl` |
| calibration-2026-09-12/muhyo/ | Raw per-frame logs | `jus-9utl` |

Shared mechanics: [Physics](../physics.md), [Damage](../damage.md).
