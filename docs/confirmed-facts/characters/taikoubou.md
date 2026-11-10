# Taikoubou (`chr_b` 68, `hs_b_01`)

## Current export evidence, 2026-10-15

STATIC: The manifest/export reference
lists field coverage and remaining schema limits. The older September tables below
retain their original fixture, facing, resistance, and input-label conventions.
The attack specials are X and up+X only, per the owner's input ruling.

MEASURED: TKA
captures both facings, short/full-hop landings, base B/Y crosschecks at 5k/6k,
and SELECT below full SP. Two air-Y wristbands hit together at tick 21 for 8+8
against the close dummy; both last through tick 111, beyond ground idle at 60.
Neutral Y's actor lasts through tick 49, beyond idle at 22. These observations
replace the old claim that no element outlives its move.

MEASURED: SELECT gives +2048 raw SP at tick 56 on tap, or at 56/102/148 when
held long enough. Idle SP regeneration is +20 raw per tick in TKA's fixture.
INFERRED: The idle gain is Calm. UNMEASURED: Pool-to-bar carry timing.

MEASURED: TKB
captures X/up X at every koma. The 6k-X finishers are IDs 284/285/286 for
damage 16/24/30 at tally samples 3/8/12. STATIC: Thresholds are <7 / 7–10 /
>=11 from the query-0x42 analysis. MEASURED: Right-facing ground idle is
168/169/169, so the higher static animation end keys do not lengthen elapsed
move time by 34/68 ticks. UNMEASURED: Boundary tallies, blocked 6k X, poison
duration, and mid-fight tally changes.

STATIC: Koma 662 flags 0x20 is a Laughter-only
nature variant sharing the k6 moves; specials keep their base per-size natures.
No separate alt capture is required. TKB's summon/projectile trial is confounded.

Tracker item `jus-4ocm`, the second character of the roster campaign
`jus-roster-moveset-campaign-69it`. Taikoubou is the campaign's first
**summoner**: almost every attack in his kit is an ally who is spawned into the
element array and does the hitting for him, so this file carries an extra
column — **who owns the hitbox** — and a summon-lifecycle section that
`kakashi.md` does not have.

Move checklist: [`taikoubou--46293.json`](../../research/gamefaqs-movesets/taikoubou--46293.json)
(GameFAQs, Dojun Woo v1.11 — player-written numbers, not ours). Owner quirks:
[OWNER-NOTES.md](../../research/moveset-notes/OWNER-NOTES.md). Raw per-frame
logs, plans and per-move summary JSON:
feel-captures/taikoubou-2026-09-03/.
Driver: [`scripts/emu/moveset_map.py`](../../../scripts/emu/moveset_map.py)
(its docstring is the CLI reference). Element array: entities.md §5.5. SP word:
guard-sp.md §1.4.

---

## Conditions

| item | value |
|---|---|
| holder | `opus-taikoubou-2026-09-03`, released at the end (`stop_emu.sh`, `/tmp/jus_emu/HOLDER` gone) |
| launcher | `bash scripts/emu/launch_emu.sh`, 1 launch |
| fork build | `scripts/emu/build_info.json`, commit `c26edf0e0d75364823856c9272a103fe39e03999` |
| ROM | `jus.nds` sha256 `a9c9bf89e6d99548b7c87e822b217c3fb74ef25186535b06193a6fb73d0d6d27` (`scripts/emu/hashes.json`) |
| state | `pc-taikoubou-npc-jotaro-dark-tournament` (owner build; loads with `ok:true`) |
| attacker | P1 **Taikoubou `chr_b` 68**, object `0x02228E80`, `M` = `[[obj+0x1a8]+0x10]` = `0x0220F30C`, element `0x0220C068`, HP 144.0 |
| attacker deck | `[68 Taikoubou 144, 67 Momotaro 176, 32 Yusuke 184, 118 (HP 8.0, not a battle character)]`. **L and R are live hotkeys in this deck** (L = Yusuke, R = Momotaro, `jus-e2w4`); neither was ever pressed |
| SP | P1 **`0x021DF730`**, the player slot's `+0x5C8` (guard-sp.md §1.4); reads **`0x0707`** at battle start, where Kakashi's deck read `0x0909` |
| victim | CPU **Jotaro `chr_b` 28**, opponent deck `[28 Jotaro 160, 14 Sanji 136, 36 Kenshin 152, 46 Lenalee 128]`, slot 0 active, HP 160.0 |
| victim object | **`0x02246A20`** — read from the fighter table `0x021DEB3C` slot 1. *Not* Kakashi's `0x0224EF00` even though the state family is the same (see Hazards) |
| victim `M` | `0x0220F494`, verified live as `[[0x02246A20+0x1a8]+0x10]`; element `0x0220C0A8` |
| geometry | Taikoubou x 634.11 px, Jotaro x 576.00 px, gap **58.11 px**; Taikoubou faces/walks **LEFT** to reach him. `--approach 26` stops at 19.18 px, `--approach 13` at 38.60 px, `--approach 0` leaves 58.11 px |
| CPU | as-is (idle) for the damage runs; `COM設定 = ガード` (START, DOWN, A, A, START as five 1-frame plans, then saved to the transient bridge slot `taikoubou-guard-tmp`) for the block runs |
| guard confirmed | the ガード row **was** reached in this state: `B_guardchk` landed its primer `B` for 7.0 HP and then had the real `B` blocked (gauge 0 → 7, no HP drop). Every block row below comes from that saved slot |
| auto-heal | already OFF in this state; damage is read as the per-frame HP step |
| positive control | **Taikoubou `B` on the first run of the batch dropped the victim's HP record 160.0 → 153.0 = 7.0**, which is exactly the guide's "7 to knowledge komaman" |
| per-move plan | one `jusemu.py state load` + one plan per move; 498 watched bytes/frame over 21 watches with `--elements 6` (the narrow layout, see "What changed in the driver") |

### What each column means

Same as [kakashi.md](kakashi.md) §"What each column means" — **startup** is
input → the frame the victim's `M+0x16C` latches, **active** is first to last
hit frame, **recovery** is last hit → the attacker's `obj+0x18` back to 0/1,
**hit type** is `M+0x16C`, **hitstun** is `obj+0x115` on the following frame,
**kb** is the staged `M+0x148`/`M+0x14A` raw pair. Two columns are new:

- **owner** — who the hitbox belonged to: `self` for Taikoubou's own body,
  `el<N>` for slot `N` of the element array at `0x0220C0E8 + 0x40·i`. There is
  **no runtime field that names the owner**, so this is a proximity call: on
  the latch frame the driver compares the attacker's distance to the victim
  against every live element's, and takes the nearest. Read it next to the
  summon-lifecycle section, which gives the element's whole track.
- **dist** — the **attacker's** distance to the victim on the latch frame, not
  the element's. For a summoner the two are very different (side Y lands at 135
  px of attacker distance).

---

## B (light)

| input | startup | active | recovery | total | hits | damage | hit type | hitstun | kb raw (x,y) | handler `obj+0xFC` | owner | dist |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `B` | 13 | 1 | 24 | 37 | 1 | **7.0** | 1 | 20 | (−640, 0) | `0x0215B720` | self | 19.18 |
| `side B` | 12 | 1 | 29 | 41 | 1 | **7.0** | 2 | 20 | (−1280, −551) | `0x0215B720` | el0 (1 frame) | 21.36 |
| `up B` | 15 | 17 | 23 | 54 | **5** | 1.0 × 4 + 2.0 = **6.0** | 2, 1, 2, 1, 2 | 20 each | (+896, −413), (+640, −276), (−896, −413), (−640, −276), (−1664, −1377) | `0x0215B720` all | self | 16.5 → 4.0 |
| `down B` | 26 | 2 | 41 | 68 | 2 | **8.0** (`obj+0x112`) | 2, 2 | 20 | (−1024, 0) both | `0x0215B720` | el0 | 19.18 |
| `air B` | 16 | 1 | 79 | 95 | 1 | **7.0** | 2 | 20 | (−1408, 0) | `0x0215B720` | self | 19.06 |
| `dash B` (braked) | 13 | 1 | 24 | 37 | 1 | **7.0** | 1 | 20 | (−640, 0) | `0x0215B720` | self | 19.18 |

- **`B` and `air B` are Taikoubou's own Paopei; every other B is a summon.**
  `B`, `up B` and `dash B` spawn no element at all, so the light chain is the
  half of the kit the summoner label does *not* apply to.
- **`up B`'s five hits are 1 + 1 + 1 + 1 + 2 = 6.0**, on a strict 4-frame
  period (rel 15, 19, 23, 27, 31), alternating hit type 2 / 1 and ending on a
  big upward `kbY` (−1377). The guide's "5-hit combo, 6 total" is exact. The
  first two hits' `kbX` is **positive** and the last three negative: the swing
  crosses the victim, so the sign flips mid-move (physics.md §4.6's "x sign
  chosen by relative position", seen inside one move for the first time).
- **`down B` forces a character switch, exactly like Kakashi's.** At rel 27 the
  opponent's active flag moves from slot 0 (Jotaro, 160.0) to slot 1 (Sanji,
  136.0), so the naive HP read shows a 32.0 "drop" that is the gap between two
  characters. `obj+0x112` reads 8 and the blocked run adds 8 to the guard
  gauge, so the damage is **8.0** — the guide's number. Bukichi is a real
  spawned element (el0, alive rel +19…+74, travels 35 px and rises 18 px).
- **`down B` is the only forced switch in the kit** and it does *not* switch on
  block: `downB_guard` shows `switch_on_hit` false and no slot change.
- **`dash B` is `B`.** Byte-identical out of a braked double-tap. The full
  12-frame dash burst carries Taikoubou from 634 to 559 px, *past* the victim
  at 576, and whiffs — same hazard as Kakashi's.
- **`side B` is an energy wave whose element lives exactly one logged frame**
  (el0 at rel +12, at 565.71 — 47 px in front of Taikoubou). It is a spawn,
  but nothing like a persistent summon.

## Y (heavy)

| input | startup | active | recovery | total | hits | damage | hit type | hitstun | kb raw (x,y) | owner | attacker dist |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `Y` | 21 | 1 | 4 | 25 | 1 | **19.0** | 2 | 20 | (−1280, 0) | el1 | 58.11 (also hits at 38.60) |
| `side Y` | 18 | 1 | 17 | 35 | 1 | **14.0** | 2 | 20 | (−1280, 0) | el0 | **134.64** |
| `up Y` | 24 | 1 | 27 | 51 | 1 | **16.0** | 2 | 20 | (−1280, −1377) | el0 | 58.11 |
| `up Y` (after `up B`) | 50 from the up-B input | 1 | 27 | — | 1 | **16.0** | 2 | 20 | (−1280, −1377) | el0 | on a popped victim |
| `down Y` | **49** | 1 | 24 | 73 | 1 | **14.0** | **5** | **40** | (−1280, −1377) | el0 | 19.18 |
| `air Y` | 24 | 1 | 39 | 63 | 1 | **16.0** | 2 | 20 | (**+1408**, −551) | el4 | 19.06 |
| `dash Y` | 21 | 1 | 4 | 25 | 1 | **19.0** | 2 | 20 | (−1280, 0) | el1 | same as `Y` |

All seven route to `0x0215B720` except `down Y`, which routes to the type-5 pop
handler `0x0215B910`.

- **Every heavy is a summon.** `Y` is Kou Hiko, `side Y` Kou Tenka, `up Y`
  Youzen, `down Y` Fugen, `air Y` Nataku — and each one's damage matches the
  guide's knowledge-koma figure exactly (19 / 14 / 16 / 14 / 16).
- **`Y` has both a minimum and a maximum range.** It **whiffs** at 15.5 px
  (`Y_close`), 19.2 px (`Y`) and 78 px (`Y_d78`), and **connects for 19.0** at
  38.6 px (`Y_d39`) and 58.1 px (`Y_far`). Kou Hiko is placed 16 px in front of
  Taikoubou, stands still for 12 frames, drifts 5 px, and swings on the frame
  his element slot is handed off (rel 21) — the sword reaches ~37 px past him
  and has a dead zone at the hilt. The guide gives no range caveat.
- **`side Y` is a long-range move that whiffs up close.** Kou Tenka spawns 16 px
  in front and decelerates forward (8.75 px/frame down to 0.3), slashing at
  rel 18. At an attacker distance of 58 px he is already 15 px *past* the
  victim by rel 18 and the forward slash points away — no hit at all, at 19,
  39 and 58 px. Backed off to 135 px he is 61 px short of the victim at rel 18
  and the slash connects for the guide's **14.0**. Usable band: roughly
  80–135 px, measured only at 135.
- **`up Y` hits a grounded victim**, unlike Kakashi's. At 58 px it lands 16.0
  on a standing Jotaro; after `up B`'s pop it lands the same 16.0 on an
  airborne one. This is a real difference between the two characters' up Y and
  the guide's plain damage number is right as written.
- **`down Y` is an instant guard shatter with the longest startup in the kit
  (49 frames).** Against a live guard it dealt its full **14.0** HP damage and
  **added nothing to the guard gauge**. That is the universal `down Y` shatter
  (maintainer ruling, `jus-xcz0`), reproduced on a third character. It is also the
  kit's only type-5 pop.
- **`air Y`'s `kbX` is positive (+1408)** while every other move's is negative:
  Nataku's wristbands reach the victim from the far side, so the sign flips —
  the same effect as Kakashi's air Y.
- **`dash Y` is `Y`**, measured by backing off 30 frames and dashing into the
  38–58 px band (`dashY_long`). From the state's own geometry a dash always
  ends inside Y's dead zone, so this needed the negative-approach feature.

## SELECT (ultimate action)

| input | startup | active | recovery | total | hits | attacker state |
|---|---|---|---|---|---|---|
| `SELECT` | — no hit — | — | — | 97 | 0 | `obj+0x18` = **12** for 94 frames (input+3 to input+96), then 0 |

Taikoubou sits down to fish. No damage, no `M+0x16C` latch, **no SP cost**, and
no element spawns. State code 12 is the same landing/can't-act code Kakashi's
tree-stump dodge used, but Taikoubou holds it for **94** frames against
Kakashi's 60 — so the taunt length is per-character, not a property of state 12.

MEASURED: This September fixture starts at full SP. TKA's below-full trials
establish the SP gain and hold loop described in the current-evidence section.

## Specials (4-koma knowledge)

Taikoubou's HP is 144.0 and the guide gives no koma HP figures for him, so the
koma size cannot be read off HP the way Kakashi's was. What the runs show is
that **two X specials exist and they are the 4-koma pair** the guide lists (a
"stronger forward B" and a charging vertical whirlwind), so this deck runs the
4-koma battle koma.

| input | move | startup | active | recovery | total | hits | damage | hit type | hitstun | kb raw (x,y) | handler | owner | SP | effect `M+0x172/0x173` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `X` | energy wave | 24 | 1 | 37 | 61 | 1 | **19.5** | **5** | **40** | (−3840, −1652) | `0x0215B910` | self / el0 | **−0x100** | 0 / 0 |
| `side X` | energy wave | 24 | 1 | 37 | 61 | 1 | 19.5 | 5 | 40 | same | `0x0215B910` | self | −0x100 | 0 / 0 |
| `down X` | energy wave | 24 | 1 | 37 | 61 | 1 | 19.5 | 5 | 40 | same | `0x0215B910` | self | −0x100 | 0 / 0 |
| `X` held 60f | energy wave | 24 | 1 | 37 | 61 | 1 | 19.5 | 5 | 40 | same | `0x0215B910` | self | −0x100 | 0 / 0 |
| `up X` (tap) | whirlwind | 22 | 79 | — see below | 48 | **16** | 0.75 × 16 = **12.0** | 2/1 alternating | 20 | (+128, −276) / (−384, −276) | `0x0215B720` | el1, el2 | −0x100 | 0 / 0 |
| `up X` held 60f | whirlwind | 54 | 65 | — | — | **17** | 0.75 × 17 = **12.75** | 2/1 alternating | 20 | same | `0x0215B720` | el1 | −0x100 | 0 / 0 |
| `up X` held 120f | whirlwind | 54 | 65 | — | — | 17 | 12.75 | 2/1 | 20 | same | `0x0215B720` | el1 | −0x100 | 0 / 0 |
| `air X` | — nothing — | — | — | — | 46 | 0 | — | — | — | — | — | **0** | — |

- **`X`, `side X`, `down X` and a held `X` are one move**, byte-identical, all
  debiting `0x100`. It is the kit's hardest single hit: 19.5 in one frame, a
  type-5 pop, hitstun 40, `kb` (−3840, −1652) — the largest staged pair
  measured on any character so far.
- **`X` also spawns a travelling wave that never hit.** el0 appears on the same
  frame as the hit (rel +24), 36 px in front of Taikoubou, and travels 155 px
  away at 4.44 px/frame before clearing at rel +59. The 19.5 lands whether the
  attacker is 11 px or 36 px away, and the wave contributed nothing either
  time — because the pop throws the victim out of its path.
- **`up X`'s charge saturates.** A tap gives 16 hits (12.0), a 60-frame hold 17
  hits (12.75), and a 120-frame hold is byte-identical to the 60-frame one. The
  hold delays the first hit from rel 22 to rel 54 and shortens the active
  window from 79 to 65 frames; the per-hit damage never changes. So the charge
  buys timing, not damage — a 6% total at most.
- **The whirlwind holds the victim in place.** Hits land every 4 frames and the
  staged `kbX` alternates +128 / −384, i.e. it pushes the victim back and forth
  across the element instead of away from it. Over `up X` the victim moved from
  576.0 to 570.8 px — 5 px in 36 frames.
- **`up X`'s "recovery" is not measurable the usual way.** Taikoubou is
  actionable 48 frames after the input; the whirlwind's last hit lands at rel
  100, so the summariser's last-hit-to-idle recovery comes out **−52**. Read it
  as: actionable at 48, the summon keeps hitting for ~52 frames after that.
- **`air X` produces no action.** `obj+0x18` goes jump (6) → landing (13) →
  idle (0) with no attack state and **no SP debit** — the input is ignored in
  the air, not a special that whiffed. Identical to Kakashi.
- **Nothing in the kit dispatches a status effect.** Every hit measured —
  normals, both specials, blocked and unblocked — reads `M+0x172 = 0` and
  `M+0x173 = 0`. The guide's only status move is the 6-koma up X (poison),
  which this deck cannot reach.

## Summon lifecycle

Every hitbox owner is either Taikoubou's own body or a slot of the element array
at **`0x0220C0E8 + 0x40·i`** (entities.md §5.5). Tracks are relative to the
attack input; "anchor" means the slot never moved more than 0.5 px/frame.

| move | element slots | lifetime (rel) | shape |
|---|---|---|---|
| `B`, `up B`, `dash B`, `SELECT`, `air X` | — none — | — | Taikoubou's own body only |
| `side B` | el0 | +12 … +12 | a single-frame anchor 47 px in front (the wave) |
| `down B` | el0 | +19 … +74 (56 f) | traveller, 35 px along and 18 px up (Bukichi) |
| `Y` | el0 then el1 | +5 … +20, +21 … +52 | anchor 16 px in front, handed to el1 at the swing frame (Kou Hiko) |
| `side Y` | el0 then el1 | +5 … +31, +32 … +65 | traveller decelerating 8.75 → 0.3 px/frame over 68 px, then el1 holds the endpoint (Kou Tenka) |
| `up Y` | el0 | +11 … +55 (45 f) | traveller, 75 px along and 54 px up (Youzen) |
| `down Y` | el0 | +12 … +75 (64 f) | anchor 16 px in front (Fugen's explosion) |
| `air Y` | el0–el5 | +5 … +114 | **three anchors** at +5, then **two travellers** at +24 that climb 155 px, plus a sixth anchor at +31 (Nataku and his two wristbands) |
| `X` | el0 | +24 … +59 (36 f) | traveller, 155 px away at 4.44 px/frame (the wave) |
| `up X` | el0 → el1 → el2 | +14 … +18, +19 … +92, +93 … +118 | one logical whirlwind creeping forward at 0.17 px/frame, handed down three consecutive slots |

Three findings:

1. **No summon persists between moves.** The longest-lived element is `air Y`'s
   at 114 frames and `up X`'s at 118, and both die inside their own move's
   window; the shortest is `side B`'s single frame. No capture ever showed an
   element alive from one input to the next, and no move behaved differently
   with an earlier move's element out. The "run each move twice, summon absent
   and summon present" half of the recipe therefore **has no second case for
   Taikoubou** — his allies are per-input spawns, not a pet. `up X` → `B` at
   +90 and `down Y` → `B` at +40 both produced no second hit at all (the
   attacker is still in the special, or the victim is airborne), so the
   negative is an absence of evidence for those two windows specifically; it is
   the element tracks, not those two runs, that carry the claim.
2. **One logical summon can occupy several array slots in sequence.** `Y`,
   `side Y` and `up X` all hand off to the next consecutive slot at the same
   position, on the frame the phase changes (`Y` hands off on the exact swing
   frame). A reader who treats "slot freed" as "summon gone" will cut every one
   of these moves short. This extends entities.md §5.5's anchor-plus-travellers
   shape: the slots are a **sequence**, not just a set.
3. **The summon is not a fighter, so it has no HP and cannot be hit as one.**
   A dedicated capture (`fightertable-downY`) watched the fighter table
   `0x021DEB3C` across the whole of `down Y`: Fugen's element is live for frames
   38–101 and the table stays `[0x02228E80, 0x02246A20, 0, 0]` the entire time.
   No entry, no HP record, no guard gauge. Whether an *attack* can destroy the
   element early is untested — it needs a CPU that attacks.

## SP

The SP total is the word at the player slot's `+0x5C8` (guard-sp.md §1.4),
`0x021DF730` for P1, derived from the current-HP address minus `0x6C`. It reads
**`0x0707`** at battle start in this state, where Kakashi's deck read `0x0909`
— so the starting SP is per-deck, not a constant.

| event | SP delta |
|---|---|
| `X`, `side X`, `down X`, `X` held | **−0x100** |
| `up X` (tap, 60f hold, 120f hold) | **−0x100** |
| `air X` | 0 |
| `SELECT` | 0 |
| every normal (`B`, `up B`, `down B`, `side B`, `air B`, `Y`, `side Y`, `up Y`, `down Y`, `air Y`, dash) | **0** |
| a blocked special | **−0x100** anyway |

A special costs `0x100` debited on its first frame, before any hit lands — the
same figure Kakashi's cost, on a different character and a different starting
total, which is the first evidence that `0x100` is a system constant rather than
a per-character number. Charging `up X` does not change the price.

## On block (`COM設定 = ガード`)

Each run presses `B` first as a throwaway primer 60 frames before the move under
test, because the ガード CPU stands still until the first hit lands and only then
holds guard. A blocked hit does **not** latch `M+0x16C`; the only trace is the
guard gauge `obj+0x102` stepping up.

| move | HP damage on block | guard gauge added | breaks guard |
|---|---|---|---|
| `B` | 0 | +7 | no |
| `side B` | 0 | +7 | no |
| `up B` | 0 | +1, +1, +1, +1, +2 = 6 | no |
| `down B` | 0 | **+8** | no (and no forced switch) |
| `air B` | 0 | +7 | no |
| `Y` | 0 | **+19** | no |
| `air Y` | 0 | **+16** | no |
| `down Y` | **14.0** | **0** | **shatters the guard** |
| `X` | 0 | **+19** | no |
| `up X` | 0 | +5 seen as one step | no |

- **Every blockable hit adds its whole-unit damage to the gauge**, matching
  physics.md §4.5 — including `X`'s 19.5, which adds 19 in a single step and so
  independently confirms that `X` is one hit rather than a burst.
- **`down B`'s gauge row is the clean read of its damage:** +8, the guide's
  number, with no character switch to confuse the HP address.
- **`up X`'s gauge row is weak.** The whirlwind's per-hit 0.75 floors to 0 in
  guard-sp.md §0.5's `gauge += damage >> 6`, so most of its hits should add
  nothing; the single +5 step at rel 117 is consistent with fractions
  accumulating somewhere, but the run cannot separate that from gauge decay
  merging several steps. Treat +5 as a lower bound, not a measurement.
- **`side Y`'s gauge damage is not measured.** It needs a primer that connects
  at 135 px and `B` reaches ~20 px, so the CPU never enters guard on that run —
  the same gap Kakashi's `side Y` left.
- Gauge decay is 1 per frame starting 123 frames after the last blocked hit
  (measured 7 → 0 over frames 223–229 in `B_guardchk`), matching Kakashi's.

## The authored records

Static side, from `python3 scripts/analysis/move_records.py 68 --list` (dump
saved next to the logs as `static-records-taikoubou.txt`). Taikoubou's file
`chr/col/hs_b_01.bin` holds **39 records, ids `0x100`–`0x126`**.

`kbY` is recovered from the staged `M+0x14A` by physics.md §4.6's chain
(`kbY = raw_y / −137.6`) and the multiplier from `raw_x / 128`.

| move / hit | measured type | `(raw_x/128, kbY)` | record | agreement |
|---|---|---|---|---|
| `B` | 1 | (−5, 0) | rec 0 `0x100` kind 3 type 1 kbX 5 kbY 0 | type, both kb |
| `side B` | 2 | (−10, 4) | rec 2 `0x102` kind 2 type 2 kbX 10 kbY 4 | type, both kb |
| `up B` hit 1, 3 | 2 | (∓7, 3) | rec 4 `0x104` kind 3 type 2 kbX −7 kbY 3 | type, both kb |
| `up B` hit 2, 4 | 1 | (∓5, 2) | rec 5 `0x105` kind 3 type 1 kbX −5 kbY 2 | type, both kb |
| `up B` hit 5 | 2 | (−13, 10) | rec 6 `0x106` kind 3 type 2 kbX 13 kbY 10 | type, both kb |
| `down B` both hits | 2 | (−8, 0) | rec 11 `0x10b` / rec 12 `0x10c`, both type 2 kbX 8 kbY 0 | type, both kb; the two records are indistinguishable |
| `air B` | 2 | (−11, 0) | rec 8 `0x108` kind 3 type 2 kbX 11 kbY 0 | type, both kb |
| `up Y` | 2 | (−10, 10) | rec 7 `0x107` kind 3 type 2 kbX 10 kbY 10 | type, both kb (rec 10 has the same kb but type 5) |
| `down Y` | 5 | (−10, 10) | rec 10 `0x10a` kind 3 type 5 kbX 10 kbY 10 | type, both kb |
| `air Y` | 2 | (**+11**, 4) | rec 9 `0x109` kind 2 type 2 kbX 11 kbY 4 | type, both kb |
| `X` | 5 | (−30, 12) | rec 13 `0x10d` kind 4 type 5 kbX 30 kbY 12 | type, both kb |
| `up X` even hits | 2 | (+1, 2) | rec 14 `0x10e` kind 4 type 2 kbX −1 kbY 2 | type, both kb |
| `up X` odd hits | 1 | (−3, 2) | rec 15 `0x10f` kind 4 type 1 kbX 3 kbY 2 | type, both kb |
| `Y` / `side Y` / `dash Y` | 2 | (−10, 0) | rec 1 `0x101` (frameStart 14), rec 3 `0x103` (frameStart 19) or rec 20 `0x114` — all type 2 kbX 10 kbY 0 | type and kb only; three candidates |

**Both halves of §4.6 reproduce on Taikoubou.** `raw_x` is a clean multiple of
128 on every hit *and* the multiplier is the record's `kbX` byte on every one of
the 13 distinct pairs above — where Kakashi's `B` and `up B` disagreed with
their records' `+0xC`. So the horizontal chain is right and the Kakashi
mismatch is a Kakashi-specific problem, not a hole in the formula.

**`frameStart` is not a usable join key for a summoner.** It matches for the two
moves Taikoubou performs himself (`B` animation frame 8 vs `frameStart` 7,
`side B` 7 vs 7) and matches nothing for the summoned ones: `down Y` hits at
attacker animation frame 44 against a `frameStart` of 14, `X` at 19 against 26,
and `up X`'s recs 14/15 carry `frameStart` 1/2 while the hits land every 4
frames from animation frame 17 on. The natural reading is that a summoned
element's `frameStart` is counted from **the element's own (looping) animation**,
not the attacker's — which is also why `up B`'s recs 4/5 read `frameStart` 1/2
for hits at animation frames 10–26.

Unmatched records, i.e. the bigger koma:

- recs 16–19 (`0x110`–`0x113`, kind 4) — one type-5 with `kbY` 18 and a type-1
  with `kbX` **40**, the largest in the file.
- recs 21–30 (`0x115`–`0x11e`), including **three `type 6` launchers**
  `0x11c`/`0x11d`/`0x11e` with `kbX` 20 / 25 / 30 and `kbY` −13 and
  `frameStart` 16 / 24 / 30 — an escalating triple, the shape of a
  charge-scaled finisher. Nothing in the 4-koma kit reaches a `type 6`.
- rec 31 (`0x11f`, kind 1, status byte −19 (`statusRaw`, effect 0x13 poison)) — the only negative `projectileId` in
  the file (entities.md §6: an opaque token, do not decode).
- **recs 32–37 (`0x120`–`0x125`) are six byte-identical kind-4 type-2 records**
  (kbX 5, kbY 0, `frameStart` 2). That is almost certainly the guide's 5-koma
  "six miniature whirlwinds"; it is the cleanest static-to-guide match in this
  file and it costs a 5-koma deck to confirm.
- rec 38 (`0x126`, kind 0 type 0) and rec 21 (`0x115`, kind 0 type 0) — no
  damage, the plain-box shape.

---

## Does not match the guide

| guide | measured | reading |
|---|---|---|
| `B` 7, `up B` 6 total over 5 hits, `down B` 8, `side B` 7, `air B` 7 | 7.0, 1+1+1+1+2 = 6.0, 8.0, 7.0, 7.0 | All exact. |
| `Y` 19, `side Y` 14, `up Y` 16, `down Y` 14, `air Y` 16 | 19.0, 14.0, 16.0, 14.0, 16.0 | All exact. |
| combo "B Up+B — 13 total" | `B_upB` = 7.0 + 6.0 = **13.0** | Exact. |
| `air Y` "hits twice (for each projectile)", 16 total | **one** hit of 16.0, though **two** traveller elements spawn together at rel +24 | The two wristbands are real elements but only one hitbox landed at 19 px. Either the second needs a different height/range, or 16 is the single-hit figure and the guide added a hit it saw on screen. Unresolved. |
| `Y` "Kou Hiko swings his two-handed sword", no range caveat | whiffs at 15.5, 19.2 and 78 px; connects for 19.0 at 38.6 and 58.1 px | The move has a **dead zone at close range** and a hard maximum, neither of which the guide mentions. |
| `side Y` "Kou Tenka rushes forward and slashes" | **zero** hits at 19, 39 and 58 px; 14.0 at 135 px | The rush overshoots a nearby victim and the slash points away from him. It is a long-range move that fails up close — the opposite of what "rushes forward" suggests. |
| `down Y` "can break the opponent's guard" | gauge untouched, guard shatters at once, full 14.0 damage and the type-5 pop applies | Matches. The mechanism is an instant shatter, not gauge wear-down, and it is universal to `down Y` (owner, `jus-xcz0`). |
| 4-koma `X` "stronger version of the Forward-B", **26 total** to a knowledge komaman | **19.5** in one hit, at 11 px and at 36 px | The spawned wave travels 155 px away and hit nothing in either run, because `X`'s own type-5 pop throws the victim clear. 26 is plausibly 19.5 plus the wave, i.e. a victim who cannot be popped away (a corner, or a heavier target). Not reproduced. |
| 4-koma `up X` "damage scales from a light charge to a max charge", **14–30 total** | 12.0 tapped (16 hits), 12.75 held (17 hits), identical at 60 f and 120 f of hold | The charge is real (startup 22 → 54) but it buys almost no damage here. 30 needs many more hits than 17, which the guide's own corner-infinite note suggests come from a victim who cannot be pushed out. The floor 14 is also above our 12.75, so even the light charge under-delivers at this range. Unmatched. |
| the guide's damage tables as "knowledge based … to knowledge komaman" | every number that landed matched the knowledge-vs-knowledge column | Confirms Jotaro is a knowledge target for damage purposes and this Taikoubou koma is knowledge-natured. |
| the guide names no inputs for the specials | `X`, `side X`, `down X` and a held `X` all give the energy wave; `up X` gives the whirlwind; `air X` does nothing | This is the mapping. |
| 5- and 6-koma specials (horizontal whirlwind, six mini whirlwinds, Fukki barrage, Fukki poison) | not driven | Need 5- and 6-koma decks. Six identical records `0x120`–`0x125` are the likely home of the six mini whirlwinds. |

## Does not match the owner

Empty. OWNER-NOTES has no Taikoubou-specific entry beyond the kit type, and the
two general notes that apply both reproduce:

- **"Taikoubou … is a summoner; his kit works through a summoned creature"** —
  reproduced, with one correction of emphasis rather than fact: it is not *one*
  creature but a different named ally per input, spawned and freed inside the
  move. `B`, `up B`, `dash B` and `SELECT` are Taikoubou himself and spawn
  nothing at all.
- **"Down+Y shatters guard instantly for every character"** — reproduced
  exactly on a third character.
- **"Only the Taikoubou deck has the L/R hotkeys set"** — the deck is
  `[68, 67 Momotaro, 32 Yusuke, 118]`, matching the owner's L = Yusuke,
  R = Momotaro. Neither button was pressed in any run.

## Not yet measured

- **UNMEASURED: Special follow-ups.** TKB resolves the per-koma move inventory,
  sampled holds, and 6k-X tally tiers. Remaining checks include blocked 6k X,
  exact tally boundaries, mid-fight tally changes, and poison duration.
- **`side Y`'s guard-gauge damage** — needs a primer that connects at 135 px.
- **`side Y`'s exact usable band.** Measured hit at 135 px and misses at 19, 39
  and 58; the 60–130 px range is unprobed.
- **`Y`'s exact minimum and maximum.** Bracketed to (19, 39] and [58, 78).
- **`X` against a victim who cannot be popped away**, which is the reading that
  would explain the guide's 26; and **`up X` in a corner**, which is what the
  guide's own infinite note and its 30 would need.
- **Whether an attack can destroy a summoned element early.** The elements have
  no fighter-table entry, so they have no HP record to watch; deciding whether
  they can be *struck* needs a CPU that attacks.
- **Whether a move behaves differently while another move's element is out.**
  MEASURED: TKA/TKB establish outliving elements. UNMEASURED: Follow-up inputs
  during those tails; the September overlap attempts produced no second hit
  for unrelated reasons.
- **UNMEASURED: SP sources beyond TKA's SELECT gains and idle regeneration.**
- **`SELECT`'s dodge window**, if Taikoubou's fishing pose has one. He holds
  state 12 for 94 frames; the guide calls the taunt "useless".
- **Support / help koma effects** (the 1-koma SP-on-support-attack passive, the
  2-koma ailment cure, the 3-koma revive) and the ally-boost system — no runtime
  probe.

## Hazards

- **The victim fighter object is per-state even inside one state family.**
  `pc-taikoubou-npc-jotaro-dark-tournament` and
  `pc-kakashi-npc-jotaro-dark-tournament` share the P1 object, both `M`
  pointers and both HP records, and differ in the victim object:
  `0x02246A20` here against `0x0224EF00` there. Kakashi's value reads
  plausible-looking, never-moving numbers off this state. Resolve slot 1 of the
  fighter table `0x021DEB3C` for every new state, then check
  `[[obj+0x1a8]+0x10]` lands on a sane `M`.
- **A summoner's `dist` column is not the hitbox's distance.** `side Y` latches
  at an attacker distance of 135 px. Any range conclusion drawn from `dist`
  alone will be wrong by the length of the summon's travel; use the element
  track.
- **A single-frame element is easy to miss.** `side B`'s element is live on
  exactly one logged frame. A sampler that reads the array every few frames will
  report `side B` as a self-owned move.
- **"Slot freed" is not "summon gone".** `Y`, `side Y` and `up X` hand off to
  the next consecutive array slot mid-move, at the same position. `Y`'s handoff
  is the swing frame itself, so the hit is attributed to the *new* slot.
- **`leaves_ground` is a false positive on a summoner's heavies.** `Y` and
  `dash Y` report it, but the attacker's `obj+0x18` never enters 4/5/6/7 — the
  flag fires on the attacker's `M+0x78` changing while the summon is out. Trust
  the `attacker_states` list, not the flag.
- **`recovery` is meaningless for a move whose element outlives the attacker.**
  `up X` comes out at **−52**.
- **The full dash burst overshoots**, exactly as with Kakashi: 634 → 559 px past
  a victim at 576. Brake one frame in (`dashB_early`), and for `dash Y` back off
  first so the braked dash lands inside Y's 38–58 px band.
- **A negative `--approach` leaves the attacker facing the wrong way**, so the
  next directional attack reads as *back*+button and comes out as the plain
  version. `sideY_far` at `--approach -20` produced a 19-frame animation (plain
  `Y`) instead of `side Y`'s 29. The `sideY_long` / `sideB_long` recipes spend 8
  frames walking forward purely to turn around before firing.
- **The hit's own fields are one frame ahead of the HP drop**, unchanged from
  Kakashi: `M+0x16C`, `M+0x148`/`M+0x14A` on the latch frame, hitstun,
  `obj+0x112` and the HP step on the next.
- **`down B`'s HP read is a trap**: the forced switch moves the HP address to a
  different character and the naive read is 32.0. Watch the slot array (offsets
  from the current-HP address, `+0x25` active, `+0x29` `chr_b`) or read the
  block row.
- **Starting SP is per-deck.** `0x0707` here, `0x0909` in the Kakashi state.
  A worker who hard-codes `0x0909` as "full" will mis-read every SP delta.
- **One hitstun byte read 255** (the idle −1) on a sample after a hit, in
  `upB_upY` hit 6, `B_upB` hit 2 and `upX` hit 16 — the same instrumentation
  noise Kakashi's `up Y` hit 1 showed. Treat 255 as "not read", not as a value.

## Owner addendum (2026-09-03)

The neutral Y summon has a body: attacks and abilities that stop on a
character stop on it, unlike Taikoubou's other summons (owner testimony,
outranks the "cannot be hit as a fighter" reading above, which only says it
is not in the fighter table). Open experiment: `jus-kq7n`.

Air Y's "hits twice" (guide) is not a mismatch: the owner says the second hit
lands only when the victim is against a wall or is knocked back into the
projectiles' return path, and the first hit's own knockback usually prevents
that. The one-hit row above is the open-ground case.
