# Eve (`chr_b` 37, `bc_b_01`)

Tracker item `jus-9utl` (calibration sweep, positive-controlled on Kakashi first —
see kakashi-control/RESULTS.md
and [calibration-sweep-two-characters.md](../../research/findings/calibration-sweep-two-characters.md)).
This page carries only the rows that sweep measured — a movement/damage/
hitstun/knockback spot check, not a moveset map. `chr_b` index 37 confirmed
live: a battle screenshot in this run shows the on-screen name "EVE" next to
this state's P1 character (committed:
eve/name-plate.png).
Note: `character-index.json`'s row for `chr_b`
index 37 says "Train" (`bc_b_01`) — that disagrees with both the screenshot
and `chr_b-Complete-Mapping.md`'s row (then `37 | bc_b_02 | Eve | Black Cat`; the mapping now reads `bc_b_01`, `:133` and `:181`,
the pre-commit label check's source of truth). This is one instance of a
systematic **off-by-one across the range**: `character-index.json` lists
Eve at index 38 (not 37) and Kakashi at index 24 (not 23, which
`character-index.json` gives to Kyuubi Naruto) — `chr_b-Complete-Mapping.md`
is the corrected source of truth throughout. (History: `character-index.json`
was fixed later. Eve is 37 / `bc_b_01`, and since the E0 roster pin (2026-10-18) every
pinned row's Collision File matches `roster_reconciled.json`, checked by
`scripts/tests/test_e0_label_consumers.py`.)

## Identity

| Field | Value | Source |
|---|---|---|
| Character | Eve | live screenshot ("EVE" name plate, committed), `chr_b-Complete-Mapping.md` |
| Series | Black Cat | `chr_b-Complete-Mapping.md` |
| `chr_b` index | 37 | `chr_b-Complete-Mapping.md`; `chr_b.bin` record read directly |
| File prefix | `bc_b_01` | `chr_b-Complete-Mapping.md:133` (Eve's row, chr_b 37), `:181` (the correction `bc_b_02` → `bc_b_01`), `scripts/analysis/char_args.py` / `move_records.py:102` |
| Walk-accel class byte (`chr_b+0x02`) | 3 | read directly from `chr_b.bin`, confirmed live (`obj+0xB8 = 96`) |
| Tier byte (`chr_b+0x01`) | 2 | read directly from `chr_b.bin`, confirmed live (`obj+0xBA = -1752`) |
| Weight | Lightweight (gate bit 15) | `chr_b-Complete-Mapping.md` §weight table |

## Measurement conditions

| Item | Value | Tracker item |
|---|---|---|
| Capture/state | `pc-eve-npc-jotaro-dark-tournament` | `jus-9utl` |
| Emulator build | `scripts/emu/build_info.json`, commit `c26edf0e...` | `jus-9utl` |
| ROM hash | `scripts/emu/hashes.json` | `jus-9utl` |
| Attacker | Eve (P1), full HP, standard/no items | `jus-9utl` |
| Victim | Jotaro (P2, CPU "do nothing"), 160.0 HP | `jus-9utl` |
| Geometry | Melee range, both grounded, P1 approaching from the right | `jus-9utl` |
| Measurement method | Fighter-object/element live reads (`physics.md` §5/§6.1), per-frame `jusemu.py run` watch logs | `jus-9utl` |

## Movement

| Quantity | Predicted (`physics.md` §6.2/§6.4, class 3 / tier 2) | Measured | Verdict |
|---|---|---|---|
| Walk accel | 96 raw/frame | **96** (`obj+0xB8`, and reproduced in the live ramp) | MATCH — first live confirmation of the class-3 row, previously table-only |
| Walk terminal (`7a`) | 672 raw = 2.63 px/frame | **672** | MATCH |
| Jump impulse | −1752 (tier 2) | **−1752** (`obj+0xBA`), −1656 after the first integrator step | MATCH |
| Jump airborne duration | 61 frames | **61** | MATCH |

Raw ramp (per-frame `element+0x24`, RIGHT held from frame 0): 0, 0, 0, 84,
158, 223, 280, 329, 372, 410, 443, 472, 497, 519, 539, 556, 571, 584, 595,
605, 614, 622, 629, 635, 640, 644, 648, 651, 654, 657, 659, 661, 663, 665,
666, 667, 668, 669, 670, 671, 672 (terminal, held). Raw logs:
calibration-2026-09-12/eve/runs/walk-ramp.jsonl.gz,
jump-arc.jsonl.gz.

## Normal moves (spot check only — not a moveset map)

| Input | Condition | Damage | Hit type | Hitstun | Knockback (staged `M+0x148/+0x14A`) | Tracker item |
|---|---|---:|---|---:|---|---|
| `B` | grounded, melee range, victim full HP | **7.0** (predicted 7.0 exactly, no gate/nature) | non-launcher | **20** (predicted `clamp(0+20+0,16,60)=20`) | −640 (matches `kbX_byte 5 × 128` exactly) | `jus-9utl` |
| `Y` | grounded, melee range, victim full HP | **16.0** (measured; record not identified — see below) | unidentified | **20** | −1920 | `jus-9utl` |

`B` resolves cleanly to `bc_b_01.bin` record 0 (kind 3, type 0, base 7,
`kbX` 5) via `scripts/analysis/move_records.py eve --list`. **`Y`'s record
could not be identified**: none of Eve's 20 authored records (`0x100–
0x113`) has base 16 or `kbX` 15. The built-in arm9 table (ids 0–13,
`0x0209FC2C`) was read directly (`jus_files/arm9/arm9.bin`, base
`0x02000000`, the constant `move_records.py` names `BUILTIN_TABLE`) and
excluded too: every id's base byte (`+0x04`) is 0 except id 1 = 10, and
every id's `kbX` (`+0x0C`) is 0 — none is a candidate for base 16 / `kbX`
15 either. Both tables checked and ruled out; the source is open. A
spawned or foreign-file element (cf. [kakashi.md](kakashi.md): Kakashi's
projectile moves — `side Y`, `down B`, `down Y`, `air Y` — spawn a
separate object and match no record in his own file either) is the
leading candidate. Not guessed — left open. Raw logs:
b-hit.jsonl.gz,
y-hit.jsonl.gz.

## Not yet measured

| Question | Why it matters | Tracker item |
|---|---|---|
| Which authored (or built-in) record `Y` actually fires | Needed to fully close the damage/knockback prediction for this move | `jus-9utl` follow-up |
| Eve X (launcher, already spot-checked in the combat notes §6.10 for HP-band/weight scaling) — a fresh `M+0x148` launcher trace | This sweep only exercised non-launcher hits; the launcher staging path (weight ×1.5, HP band) was not re-verified here | `jus-9utl` follow-up |
| Everything else in a full moveset map (specials, air normals, guard behavior) | Out of this tracker item's scope (a calibration spot check, not `jus-kakashi-moveset-map-33lu`-style coverage) | not filed |

## Sources

| Source | Purpose | Tracker item |
|---|---|---|
| [calibration-sweep-two-characters.md](../../research/findings/calibration-sweep-two-characters.md) | Full per-quantity table, both characters, positive control | `jus-9utl` |
| calibration-2026-09-12/eve/ | Raw per-frame logs | `jus-9utl` |

Shared mechanics: [Physics](../physics.md), [Damage](../damage.md).
