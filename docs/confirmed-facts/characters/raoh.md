# Raoh (`chr_b` 62, `hk_b_02`)

Tracker item `jus-wthh` (jump-tier live-character campaign, positive-controlled on
Kakashi first — see
kakashi-control/RESULTS.md
and [movement-tiers-1-3-live.md](../../research/findings/movement-tiers-1-3-live.md)).
This page carries only the jump-arc row this pass measured — a movement
spot check, not a moveset map. `chr_b` index 62 confirmed live via a battle
screenshot showing the on-screen name "RAOH" next to this state's P1
character (committed:
raoh/name-plate.png),
agreeing with both `chr_b-Complete-Mapping.md` and the HP roster check
below.

## Identity

| Field | Value | Source |
|---|---|---|
| Character | Raoh | live screenshot ("RAOH" name plate, committed), `chr_b-Complete-Mapping.md` |
| Series | Hokuto no Ken | `chr_b-Complete-Mapping.md` |
| `chr_b` index | 62 | `chr_b-Complete-Mapping.md` |
| File prefix | `hk_b_02` | `chr_b-Complete-Mapping.md` |
| Walk-accel class byte (`chr_b+0x02`) | 6 | read directly from `chr_b.bin`, confirmed live (`obj+0xB8 = 62`) — second live character for class 6 (previously Franky only, a load-time field read, not a played ramp) |
| Tier byte (`chr_b+0x01`) | 3 | read directly from `chr_b.bin`, confirmed live (`obj+0xBA = -1689`) — **the first real tier-3 character jumped**, closing the poke-only gap in `physics.md` §6.4 |
| Weight | Neither Lightweight nor Heavyweight (`chr_b-Complete-Mapping.md`'s weight table; Raoh launches like Luffy, per `physics.md` §4.2 — the earlier "Raoh is heavy" note was about a damage-reduction passive, not launch weight) |

## Measurement conditions

| Item | Value | Tracker item |
|---|---|---|
| Capture/state | `pc-raoh-npc-luffy-j-arena` | `jus-wthh` |
| Different address family | J-Arena, not Dark Tournament: fighters are element-array slots 6/7 (`0x0220C1E8` P1 / `0x0220C228` P2), stage markers occupy slots 0–5; P1 fighter pointer `0x02228A00` (not `0x02228E80`) | `jus-wthh`, `INDEX.md` |
| Attacker | Raoh (P1), full HP (192.0) | `jus-wthh` |
| Victim | Luffy (P2, CPU), 152.0 HP | `jus-wthh` |
| Procedure | No `START` press needed before driving this state (see the control doc's correction) | `jus-wthh` |
| Measurement method | Fighter-object/element live reads (`physics.md` §5/§6.1), per-frame `jusemu.py run` watch logs | `jus-wthh` |

## Movement

| Quantity | Predicted (`physics.md` §6.2/§6.4, class 6 / tier 3, poke-derived) | Measured | Verdict |
|---|---|---|---|
| Walk accel | 62 raw/frame | **62** (`obj+0xB8`) | MATCH |
| Jump impulse | −1689 (tier 3) | **−1689** (`obj+0xBA`), −1595 after the first integrator step | MATCH |
| Peak height | 70.57 px | **70.57 px** | EXACT MATCH |
| Jump airborne duration | 60 frames (poke) | **60 frames** | EXACT MATCH — bit-identical to the poke's arc; an earlier pass reported a spurious +1-frame deviation here (poke miscounted as 59), retracted in `physics.md` §6.4 / [movement-tiers-1-3-live.md](../../research/findings/movement-tiers-1-3-live.md) (`jus-wthh`) |

Raw logs:
movement-tiers-2026-09-12/raoh/runs/jump-arc.jsonl.gz.

No damage/hitstun/knockback spot check was attempted this pass — out of
scope for `jus-wthh`, which is a movement-only campaign.
