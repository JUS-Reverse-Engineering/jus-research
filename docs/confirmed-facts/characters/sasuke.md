# Sasuke (`chr_b` 21, `na_b_02`) — normals and the 7-koma X specials

Tracker item `jus-ssk6`, the third character of the roster campaign
`jus-roster-moveset-campaign-69it`. Sasuke is the campaign's first **status
carrier**: both of his 7-koma specials dispatch an effect on hit, and one of
them is the first damage-over-time this project has measured. He is also the
first character whose whole kit is his own body — no summon, no projectile,
one spawned element in the entire moveset.

Move checklist: [`sasuke--46543.json`](../../research/gamefaqs-movesets/sasuke--46543.json)
(GameFAQs, Danexedas 1/16/07 — player-written numbers, not ours). Owner quirks:
[OWNER-NOTES.md](../../research/moveset-notes/OWNER-NOTES.md). Raw per-frame
logs, plans, per-move summary JSON and the lab log:
feel-captures/sasuke-2026-09-04/
(`docs/research/feel-captures/sasuke-2026-09-04/run-notes.md`).
Driver:
[`scripts/emu/moveset_map.py`](../../../scripts/emu/moveset_map.py) (its
docstring is the CLI reference). SP word: guard-sp.md §1.4. Element array:
entities.md §5.5.

Out of scope for this file: the 4/5/6/8-koma X specials, which need other
decks. Per the owner the 8-koma X is the same launcher with more damage and a
different windup, so the rows below stand in for it launcher-wise.

---

## Conditions

| item | value |
|---|---|
| holder | `opus-sasuke-2026-09-04`, released at the end (`stop_emu.sh`, `/tmp/jus_emu/HOLDER` gone) |
| launcher | `bash scripts/emu/launch_emu.sh`, 1 launch, JIT off |
| fork build | `scripts/emu/build_info.json`, commit `c26edf0e0d75364823856c9272a103fe39e03999` |
| ROM | `jus.nds` sha256 `a9c9bf89e6d99548b7c87e822b217c3fb74ef25186535b06193a6fb73d0d6d27` (`scripts/emu/hashes.json`) |
| state | `pc-sasuke-npc-jotaro-dark-tournament` (owner build; loads with `ok:true`) |
| attacker | P1 **Sasuke `chr_b` 21**, object `0x02228E80`, `M` = `[[obj+0x1a8]+0x10]` = `0x0220F30C` (verified live), element `0x0220C068`, HP **184.0** = the guide's 7-koma 176 plus the 8 HP leader bonus, so this deck runs the **7-koma knowledge** form |
| attacker deck | `[21 Sasuke 184, 26 Yoh (White Swan) 192, 37 Eve 128, 23 Kakashi 16 (help koma)]`. No L/R hotkeys in this deck; neither button was pressed |
| SP | P1 **`0x021DF730`**, the player slot's `+0x5C8` (guard-sp.md §1.4); reads **`0x0707`** at battle start — the same total as the Taikoubou deck, against Kakashi's `0x0909` |
| victim | CPU **Jotaro `chr_b` 28**, opponent deck `[28 Jotaro 160, 14 Sanji 136, 36 Kenshin 152, 46 Lenalee 128]`, slot 0 active (`0x021DF7F0 + 0x50i + 0x25` bit 0), HP 160.0 |
| victim object | **`0x0222CFE0`** — read from the fighter table `0x021DEB3C` slot 1, matching `ADDRESSES["pc_sasuke"]`. *Not* Kakashi's `0x0224EF00` or Taikoubou's `0x02246A20` (see Hazards) |
| victim `M` | `0x0220F494`, verified live as `[[0x0222CFE0+0x1a8]+0x10]`; element `0x0220C0A8` |
| geometry | Sasuke x 636.64 px, Jotaro x 576.00 px, gap **60.64 px**; Sasuke faces/walks **LEFT**. Walk ~1.62 px/frame; `--approach 26` stops at **18.49 px**, `--approach 0` leaves 60.64 px |
| CPU | as-is (idle) for the damage runs; `COM設定 = ガード` (START, DOWN, A, A, START as five separate 1-frame plans, saved to the transient bridge slot `sasuke-guard-tmp`) for the block runs |
| guard reached | yes — `B_guardchk` landed its primer `B` for 7.0 and had the real `B` blocked (gauge 0 → 7, no HP move); the victim reads `obj+0x18` = 3 with `obj+0x104` = 65 in every block run |
| auto-heal | already OFF in this state; damage is read as the per-frame HP dip, never as a before/after difference |
| positive control | **Sasuke `B` on the first plan of the batch dropped the victim's HP record 160.0 → 153.0 = 7.0**, exactly the guide's B |
| identity | 21 `na_b_02` Sasuke, 28 `jj_b_01` Jotaro, 14 `op_b_03` Sanji, 26 `sk_b_02` Yoh (White Swan), 37 `bc_b_01` Eve, 23 `na_b_04` Kakashi — all from `docs/research/chr_b-Complete-Mapping.md` (Sasuke, Eve and Kakashi corrected 2026-10-13; the earlier `na_b_03`, `bc_b_02` and `na_b_05` were stale) |
| per-move plan | one `jusemu.py state load` + one plan per move; 498 watched bytes/frame over 21 watches with `--elements 6` (the narrow layout) |

### What each column means

Same as [kakashi.md](kakashi.md) §"What each column means": **startup** is
input → the frame the victim's `M+0x16C` latches, **active** is first to last
hit frame, **recovery** is last hit → the attacker's `obj+0x18` back to 0/1,
**total** is input → that same frame, **hit type** is `M+0x16C`, **hitstun** is
`obj+0x115` on the following frame, **kb** is the staged `M+0x148`/`M+0x14A`
raw pair, **eff** is `M+0x173`. All rows are at 18.49 px unless the row says
otherwise.

---

## B (light)

| input | startup | active | recovery | total | hits | damage | hit type | hitstun | kb raw (x,y) | handler `obj+0xFC` | leaves ground |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `B` | 12 | 1 | 22 | 34 | 1 | **7.0** | 1 | 20 | (−768, 0) | `0x0215B720` | no |
| `side B` | 13 | 12 | 28 | 52 | 2 | 3.0 + 4.0 = **7.0** | 1, 2 | 20, 20 | (−512, 0), (−768, 0) | `0x0215B720` both | no |
| `up B` | 14 | 13 | 44 | 70 | 2 | 3.0 + 4.0 = **7.0** | 1, 2 | 20, 20 | (−512, −1239), (−1024, −1102) | `0x0215B720` both | yes |
| `down B` | 28 | 2 | 41 | 70 | 2 latches | **8.0** (`obj+0x112`) | 2, 2 | 20 | (−1024, 0) both | `0x0215B720` | no |
| `air B` | 15 | 1 | 42 | 57 | 1 | **7.0** | **5** | **40** | (−1024, **+1789**) | `0x0215B910` | yes (jump) |
| `dash B` (braked, at 60 px) | 12 | 1 | 22 | 34 | 1 | 7.0 | 1 | 20 | (−768, 0) | `0x0215B720` | no |

- **Every light is 7.0**, whether it is one hit or two, which is the guide's
  whole B column exactly.
- **`side B` and `up B` split 7 as 3 + 4** on a 11–12 frame gap (rel 13/25 and
  14/26). Both take hit type 1 then 2 and hitstun 20 twice: `up B`'s rise is a
  knockback vector (`kbY` −1239 then −1102), not a launched state.
- **`up B`'s second hit is cancellable**, exactly as the owner says. See
  "The up-B cancel" below.
- **`down B` forces a character switch at full victim HP.** At rel 29 the
  opponent's active flag moves from slot 0 (Jotaro, 160.0) to slot 1 (Sanji,
  136.0), so the naive HP read shows a 32.0 "drop" that is the gap between two
  characters. `obj+0x112` reads 8 and the blocked run adds 8 to the gauge, so
  the damage is **8.0** — the guide's number. It is the only forced switch in
  the kit and it does **not** switch on block.
- **`air B` is the kit's only light that pops** (type 5, handler
  `0x0215B910`, hitstun 40) and the only one with a **downward** `kbY`
  (+1789): the spiking heel kick drives the victim into the floor.
- **`dash B` is `B`.** Byte-identical out of a braked double-tap. From this
  state's default approach every dash overshoots (`dashB`/`dashB_early` run
  Sasuke from 636 to 546/558 px past a victim at 576), so this row was
  measured with `--approach 0`.

## Y (heavy)

| input | startup | active | recovery | total | hits | damage | hit type | hitstun | kb raw (x,y) | handler | leaves ground |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `Y` | 20 | 1 | 33 | 53 | 1 | **13.0** | 2 | 20 | (−1152, 0) | `0x0215B720` | no |
| `side Y` | 20 | 40 | 36 | 95 | 4 | 3.0 + 3.0 + 3.0 + 6.0 = **15.0** | 1, 2, 1, 2 | 20 each | (−512, 0), (−640, 0), (**+1024**, 0), (−1536, 0) | `0x0215B720` all | no |
| `side Y` (Y mashed) | 20 | 40 | 36 | 95 | 4 | same | same | same | same | same | no |
| `side Y` held 30 f | 20 | 40 | 36 | 95 | 4 | same | same | same | same | same | no |
| `up Y` | 19 | 16 | 50 | 84 | 2 | 6.0 + 8.0 = **14.0** | 2, **5** | 20, **40** | (−1024, −1377), (−1664, −1102) | `0x0215B720`, `0x0215B910` | yes |
| `down Y` | **50** | 1 | 27 | 77 | 1 | **14.0** | 2 | 20 | (−1024, 0) | `0x0215B720` | no |
| `down Y` held 30 f / 60 f | 50 | 1 | 27 | 77 | 1 | 14.0 | 2 | 20 | same | same | no |
| `air Y` | 19 | 1 | 54 | 73 | 1 | **14.0** | 2 | 20 | (−1024, 0) | `0x0215B720` | yes (jump) |
| `dash Y` (braked, at 60 px) | 20 | 1 | 33 | 53 | 1 | 13.0 | 2 | 20 | (−1152, 0) | `0x0215B720` | no |

- **Every heavy matches the guide's number exactly**: 13 / 15 / 14 / 14 / 14.
- **`side Y`'s four slashes are 3 + 3 + 3 + 6** at rel 20, 32, 45, 59 — about
  12–13 frames apart, not a fast flurry. Mashing `Y` changes nothing (four
  hits either way), and neither does holding the input. Hit 3's `kbX` is
  **positive** (+1024) while the others are negative: the flurry carries the
  victim past Sasuke and the sign flips mid-move (physics.md §4.6's
  "x sign chosen by relative position").
- **`up Y`'s second hit is a type-5 pop** (hitstun 40) and it lands on a
  **grounded** victim — unlike Kakashi's up Y, which needs the victim already
  airborne. It also lands the same 6.0 + 8.0 on a victim already popped by
  `side B` (`sideB_upY`: 3.0 + 4.0 + 6.0 + 8.0).
- **`down Y` is the guard shatter with no pop.** Startup 50 is the longest in
  the kit; the hit is **type 2 with hitstun 20**, no pop and no launch, and
  against a live guard it dealt its full 14.0 with the gauge **untouched**
  (victim `obj+0x18` 3 → 8 at the hit, gauge flat at 0 with max 65 the whole
  time). That is the universal `down Y` shatter (`jus-xcz0`) on a fourth
  character, and it is the case the owner predicted: a shatter whose own
  knockback is an ordinary hit.
- **`down Y`'s "charge" buys nothing.** The guide marks it `charge`; a 30- and
  a 60-frame hold are byte-identical to a tap, startup 50 in all three.
- **`dash Y` is `Y`**, measured at `--approach 0` for the same overshoot
  reason as `dash B`.

## SELECT (ultimate action)

| input | startup | active | recovery | total | hits | attacker state |
|---|---|---|---|---|---|---|
| `SELECT` | — no hit — | — | — | 64 | 0 | `obj+0x18` = **12** for 61 frames (input+3 to input+63), then 0 |

The replacement jutsu. No damage, no `M+0x16C` latch, **no SP cost**, and no
element spawn. State code 12 is the same can't-act code Kakashi's tree-stump
dodge (60 frames) and Taikoubou's fishing (94 frames) used, so the taunt
length stays per-character. The guide's 3–4 second counter window is much
longer than the 61 frames Sasuke spends in state 12, so the counter armour
must outlive the state — untested, because it needs a CPU that attacks.

An `X` pressed inside the taunt is **swallowed**: `SELECT_X` (X at rel 30)
produces no attack state and no SP debit at all. `SELECT_X70` (X at rel 70,
after the taunt) gives the ordinary Chidori.

## Specials (7-koma knowledge)

HP 184 = the guide's 7-koma 176 plus the 8 leader bonus, so the two specials
below are the 7-koma pair: Chidori and Koukana Kisote. **Nine X inputs were
driven; they map to two moves and one no-op.**

| input | move | startup | active | recovery | total | hits | damage | hit type | hitstun | kb raw (x,y) | handler | SP | effect `M+0x173` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `X` | Chidori | 28 | 15 | 38 | 80 | 4 latches | 0 + 7.5 + 7.5 + 15.0 = **30.0** | 1, 2, 1, **6** | 20, 20, 20, **60** | (−1280, −413), (**+1024**, −276), (−1024, −276), (−3072, −1102) | `0x0215B720` ×3, **`0x0215BAB8`** | **−0x100** | 0, **225**, 225, 225 |
| `side X` | Chidori | 28 | 15 | 38 | 80 | 4 | same | same | same | same | same | −0x100 | same |
| `down X` | Chidori | 28 | 15 | 38 | 80 | 4 | same | same | same | same | same | −0x100 | same |
| `X` held 60 f | Chidori | **64** | 15 | 38 | 116 | 4 | same | same | same | same | same | −0x100 | same |
| `X` held 120 f | Chidori | **124** | 15 | 38 | 176 | 4 | same | same | same | same | same | −0x100 | same |
| `up X` | Koukana Kisote | 22 | 64 | 74 | 159 | 5 | 4.5 × 4 + 15.031 = **33.03**, plus **14.88 burn** | 2, 1, 2, **5**, **6** | 20, 20, 20, **40**, **60** | (−2048, −2203), (−512, −551), (−256, −1102), (−2560, **+275**), (−2560, −1102) | `0x0215B720` ×3, `0x0215B910`, **`0x0215BAB8`** | **−0x100** | 0, 0, 0, 0, **226** |
| `up X` held 30 f / 60 f / 120 f | Koukana Kisote | 22 | 64 | 74 | 159 | 5 | same | same | same | same | same | −0x100 | same |
| `air X` | — nothing — | — | — | — | 46 | 0 | — | — | — | — | — | **0** | — |

- **`X`, `side X`, `down X` and a held `X` are one move**, byte-identical in
  every field except startup. The guide's "hold X to charge" is real as a
  *delay* only: a 60-frame hold pushes startup 28 → 64 and a 120-frame hold to
  124, and the damage, hit count, types, hitstun and knockback never change.
  The 7-koma Chidori therefore has **no damage charge**.
- **The Chidori's first latch does 0 damage.** It is a type-1 grab-shaped hit
  (kb −1280, −413, hitstun 20) that lands on rel 28 and moves no HP; the three
  damaging hits follow at rel 34, 38 and 42. So the guide's "Hits: 3" is right
  and the runtime latches four times.
- **The Chidori is a rush that stops on contact.** Against an idle victim
  Sasuke's x is arrested at the victim (596 → 565) and the three hits land.
  **Against a guarding victim the rush passes straight through**: at 20.6 px
  from a victim in `obj+0x18` = 3 — the same distance the unguarded version
  connects from — Sasuke ran 576 → 461 px, about 90 px past, with no latch, no
  gauge step and no HP move. Retried at ~40 px and ~48 px, same result. The
  guard row for `X` is therefore **not measurable this way** (see Not yet
  measured); the SP is spent regardless.
- **The 7-koma and 8-koma `X` moves are vulnerable to the guard counter.** If
  the defender guards and presses `X` as a melee attack connects, the attacker
  is pushed backward. The owner's human-played check confirms this interaction
  for both koma sizes. The guard CPU pass-through above does not test it.
  **Mechanic now mapped** (`jus-7cv7`, guard-sp §0.7): this is the push attack
  — X while guarding arms a 9-frame window that redirects the next blocked
  hit's pushback onto the attacker (base 2000 raw + the attacker's own
  moveData kbX × 64); no SP, no damage, gauge still charges. Static-only; the
  runtime magnitude is unmeasured.
- **`up X` breaks the guard and takes the full damage through it.** Against a
  live guard all five hits land (4.5 × 4 + 15.031) plus the burn, and the
  gauge never moves — the guide's "hits the opponent upward into the air,
  breaking his guard". Only `down Y` and `up X` do this in the kit.
- **`up X` is the kit's only element spawn.** One anchor appears in element
  slot 0 on the frame of the fifth hit (rel 85) and is gone the next frame —
  the fire jutsu. The other 25 hits in the whole moveset are Sasuke's own body.
- **`up X`'s charge buys nothing at all**: 30, 60 and 120-frame holds are
  byte-identical to a tap, including startup 22.
- **Both specials cost exactly `0x100` of SP**, debited on the move's first
  frame before any hit lands (`0x0707 → 0x0607`), the same figure Kakashi's
  and Taikoubou's specials cost. **`up X` whiffs entirely at 60.64 px and the
  `0x100` is still spent.**
- **`air X` produces no action**: `obj+0x18` goes jump (6) → landing (13) →
  idle (0) with no attack state and no SP debit, at both 14 and 24 frames
  after take-off. Identical to Kakashi and Taikoubou.
- **Both specials reach the type-6 launcher handler `0x0215BAB8`** with
  hitstun 60, matching the launcher spot-check (`jus-launcher-move-spot-check-hiyh`).
  `up X`'s fourth hit is a type-5 pop with a **positive** `kbY` (+275), i.e. it
  pushes the airborne victim back down before the launcher fires.

### Status effects

The effect channel `M+0x173` (guard-sp.md §1.5) is a **per-hit dispatch, not a
flag to poll**: it reads its value on the latch frame only and is back to 0 the
next frame. Nothing in the kit ever writes `M+0x172`.

| move | `M+0x173` | what it did |
|---|---|---|
| `X` (Chidori), latches 2–4 | **225** | no measurable consequence: the victim's HP moved exactly three times over a 600-frame tail |
| `up X` (Koukana Kisote), hit 5 only | **226** | **a damage-over-time**: 0.031 HP (2 raw units) per frame for **480 consecutive frames**, starting 82 frames after the finisher's HP drop and ending cleanly = **14.88 HP** |
| every normal, `SELECT`, `air X` | 0 | — |

The guide calls 225 shock (Chidori) and 226 burn (Koukana Kisote), and the burn
is the one with teeth: 14.88 HP on top of the 33.03 direct, i.e. **45%** more
than the move's listed damage. This is the first damage-over-time measured in
this project. The owner confirms that the burn applies to all battle characters
unless a character has burn immunity from an inherent passive or a helper. The
exact tick scaling remains untested on a second victim. It is a different id
scale from the blind effect 28 recorded for Yoh (White Swan)
(`jus-launcher-move-spot-check-hiyh`), so the field's encoding is not settled.

## The up-B cancel

Owner testimony (OWNER-NOTES.md, 2026-09-03): "Up B: a two-hit rising kick.
The second hit can be cancelled into a different move by inputting another
action before the second kick fires (up B into X, up B into Y)." Reproduced.

| capture | second input | at rel | hits | damage |
|---|---|---|---|---|
| `upB` | — | — | 2 | 3.0 + 4.0 |
| `upB_X` | `X` | 16 | 1 + 4 latches | 3.0 + (0 + 7.5 + 7.5 + 15.0) = **33.0** |
| `upB_X20` | `X` | 20 | 1 + 4 latches | same 33.0 |
| `upB_Y` | `Y` | 16 | 2 | 3.0 + **13.0** = 16.0 |
| `upB_Y20` | `Y` | 20 | 1 | 3.0 (the `Y` came out and whiffed) |

Up B's second kick (4.0 at rel 26) is **gone** in every cancelled run, so the
cancel replaces the hit rather than adding to it. Both `X` timings work; `Y`
works at rel 16 and misses at rel 20, because by then the first kick's pop has
carried the victim out of `Y`'s reach.

## Range

Measured at two distances only. At **60.64 px** (the state's own gap):

| connects | whiffs |
|---|---|
| `side B`, `Y`, `side Y`, `up Y`, `down Y`, `X` | `B`, `up B`, `down B`, `air B`, `air Y`, `up X` |

Everything connects at **18.49 px**. So the light chain, the aerials and
`up X` are point-blank moves and the sword heavies plus the Chidori rush reach
at least 60 px. Nothing in the kit showed a *minimum* range: no move that
lands at 60 px failed at 18 px, which is the opposite of Taikoubou's summons.

## SP

| event | SP delta |
|---|---|
| `X`, `side X`, `down X`, `X` held 60 f / 120 f | **−0x100** |
| `up X` (tap, 30 f, 60 f, 120 f hold) | **−0x100** |
| `up X` whiffing entirely (at 60 px) | **−0x100** anyway |
| `X` passing through a guarding victim | **−0x100** anyway |
| `air X` | 0 |
| `SELECT`, and an `X` swallowed by `SELECT` | 0 |
| every normal (`B`, `side B`, `up B`, `down B`, `air B`, `Y`, `side Y`, `up Y`, `down Y`, `air Y`, dash) | **0** |

Starting total `0x0707` — the same as the Taikoubou deck and not Kakashi's
`0x0909`, so the per-deck starting SP is not per-character either. `0x100` per
special is now measured on three characters and two starting totals.

## On block (`COM設定 = ガード`)

Each run presses `B` first as a throwaway primer 60 frames before the move
under test, because the ガード CPU stands still until the first hit lands and
only then holds guard. A blocked hit does **not** latch `M+0x16C`; the only
trace is the guard gauge `obj+0x102` stepping up.

| move | HP damage on block | guard gauge added | breaks guard |
|---|---|---|---|
| `B` | 0 | +7 | no |
| `side B` | 0 | +3 then +4 | no |
| `up B` | 0 | +3 then +4 | no |
| `down B` | 0 | **+8** | no (and no forced switch) |
| `air B` | 0 | +7 | no |
| `Y` | 0 | **+13** | no |
| `side Y` | 0 | +3, +3, +3, +6 | no |
| `up Y` | 0 | +6 then +8 | no |
| `air Y` | 0 | **+14** | no |
| `down Y` | **14.0** | **0** | **shatters the guard** |
| `up X` | **33.03 + burn** | **0** | **shatters the guard** |
| `X` | — not measurable by the guard-CPU run — | — | the rush passes through a guarding victim; the owner confirms that 7-koma and 8-koma `X` are vulnerable to the human guard counter |

- **Every blockable hit adds its whole-unit damage to the gauge**, matching
  physics.md §4.5 and guard-sp.md §0.5, including the split moves hit by hit.
- **`down B`'s gauge row is the clean read of its damage**: +8, the guide's
  number, with no character switch to confuse the HP address.
- **`down Y` and `up X` both bypass the gauge entirely** and land their full
  damage and their own reaction. In both the victim's state goes 3 (guard) → 8
  (hitstun) on the hit frame with the gauge flat at 0 and its max at 65, so the
  guard was genuinely up: this is a shatter, not a whiff.
- Gauge decay is 1 per frame starting **123 frames** after the last blocked hit
  (7 → 0 over frames 222–228 in `B_guardchk`), matching Kakashi and Taikoubou.

## The authored records

> **WARNING (2026-10-18): this table was read from na_b_03 (Sakura per E0 roster); Sasuke is na_b_02. Values are NOT Sasuke's until re-read. Ticket SASUKE-REREAD.**
> The offline re-dump for Sasuke is `source ~/.venvs/jus-re/bin/activate && python3 scripts/analysis/move_records.py na_b_02 --list > docs/research/feel-captures/sasuke-2026-09-04/static-records-sasuke-na_b_02.txt` (30 records, ids `0x100`–`0x11d`, self-check OK). The record ids and joins below are not yet re-derived from that dump.

Static side, from `python3 scripts/analysis/move_records.py 21 --list` and
`--anim all` (dumps saved next to the logs as `static-records-sasuke.txt` and
`static-anim-records-sasuke.txt`). The file it read, `chr/col/na_b_03.bin` (the 2026-09 mapping; E0 2026-10-18 pins Sasuke to `na_b_02` and `na_b_03` to Sakura, so re-dump from `na_b_02` before relying on this table), holds
**22 records, ids `0x100`–`0x115`** — the smallest of the three characters
mapped so far.

`kbY` is recovered from the staged `M+0x14A` by physics.md §4.6's chain
(`kbY = raw_y / −137.6`) and the multiplier from `raw_x / 128`. Full measured
pair table: `docs/research/feel-captures/sasuke-2026-09-04/run-notes.md`
§"Static side".

**The vertical half of §4.6 reproduces.** `kbY` comes out an exact integer on
all 26 hits, on a fourth character.

*(Correction 2026-09-23, `jus-wmqi.6.4`: `attack_anim_frames` below is
`max(obj+0x72)` over the attack (`scripts/emu/moveset_map.py`), and `obj+0x72`
is the input sampler's hold counter (sampler calls since the input word last
changed), not animation frames ([anim-timing.md](../../rebuild/anim-timing.md)
§7). So "exactly `B`'s measured `attack_anim_frames`" is no evidence that
`0x1e` is `B`. The ALMT decode backs that on its own: `0x1e` is `B` on Kakashi
and Yusuke, where anim-timing.md's box-clock check matches its boxes to the B
captures. Sasuke's ALMT is not decoded, so for Sasuke it is inferred from that
shared slot layout. The kbX argument that follows does not depend on the 28.)*

**The horizontal half does not.** `raw_x` is a clean multiple of 128
everywhere (so `F = 0x100` and the `<< 7` are right), but the multiplier is
not the record's `kbX` byte. The cleanest counterexample is `B`: its animation
`0x1e` is 28 frames long, exactly `B`'s measured `attack_anim_frames`, and it
carries **one** damaging record — rec 0 `0x100`, kind 3, type 1, `kbX` **4**,
`frameStart` 9 — against a measured multiplier of **6**. There is no second
candidate to blame. The arm9 built-in table `0x0209FC2C` was dumped live for
ids 0–13 and **every entry is type 0 with kbX = kbY = 0**, so the built-ins
cannot be the home of the 6 either. Sasuke behaves like Kakashi here, not
Taikoubou; two of four characters now disagree with the byte, which makes
"the multiplier is the record's `kbX`" a Taikoubou-shaped coincidence rather
than the rule.

Joins that do agree on type and both knockback bytes:

| move | measured type | `(raw_x/128, kbY)` | record | agreement |
|---|---|---|---|---|
| `air B` | 5 | (−8, −13) | rec 20 `0x114` kind 3 type 5 kbX 5 kbY **−13** `frameStart` 11 | type, `kbY`, `frameStart` (animf 10); `kbX` 5 vs 8 |
| `down B`, `down Y`, `air Y` | 2 | (−8, 0) | rec 11 `0x10b` kind 3 type 2 kbX **8** kbY **0** | type and both bytes; the three moves are indistinguishable from each other |

Unmatched records, i.e. the other koma and the effect siblings:

- recs 12–19 (`0x10c`–`0x113`), all `kind 5`, on the long special animations
  `0x29` (55 f), `0x2a` (80 f), `0x2b` (79 f) and `0x2d` (62 f). They include
  the file's **two `type 6` launchers** `0x10c` (kbX 20, kbY 3, `frameStart`
  36) and `0x110` (kbX 25, kbY 1, `frameStart` 44), and the `type 5` `0x113`
  with the file's largest kbX, **40**. The 7-koma pair measured above reaches
  a `type 6` with a multiplier of 24 and 20, so `0x10c` is the plausible home
  of one of them by `kbX` — but the `kbY` bytes (3 and 1) match neither
  measured 8, so the assignment is not made here.
- recs 2, 3, 4 and 10 (`kind 2`, propMask `0x60`/`0x61`) sit on 4–6 frame
  animations `0x3b`, `0x3c`, `0x40`, `0x44` — the effect/sibling animations,
  not anything a base input reaches.
- **`frameStart` is a weak join key here.** It matches the latch animation
  frame for `air B` (11 vs 10) and misses for `down B` (12 vs 23), `down Y`
  (12 vs 45) and both specials' finishers, so it separates candidates only
  inside a move whose animation is already identified.

---

## Does not match the guide

| guide | measured | reading |
|---|---|---|
| `B` 7, `side B` 7 over 2 hits, `up B` 7 over 2 hits, `down B` 8, `air B` 7 | 7.0, 3+4 = 7.0, 3+4 = 7.0, 8.0, 7.0 | All exact. |
| `Y` 13, `side Y` 15 over 4 hits, `up Y` 14 over 2, `down Y` 14, `air Y` 14 | 13.0, 3+3+3+6 = 15.0, 6+8 = 14.0, 14.0, 14.0 | All exact. |
| Basic Combo "B, B+forward, Y, Y+forward … 8 hits and 42 damage total" | `combo_BsideBYsideY` = 7 + 3 + 4 + 13 + 3 + 3 + 3 + 6 = **42.0** over **8** hits | Exact, hit count and total. |
| `down B` "the forced switch attack; using it on a low-health opponent forces a character switch" | the switch fired on a **full-HP** Jotaro (160.0 of 160.0) at rel 29 | The low-health condition is wrong, or is not a condition at all. Kakashi's and Taikoubou's `down B` behave the same way, so the forced switch looks unconditional. |
| `down B` "8" damage | 8.0 by `obj+0x112` and by the guard gauge, but the HP record appears to drop 32.0 | Not a real disagreement — the switch moves the HP address to Sanji. Recorded because the naive read is a trap. |
| `side Y` "four flashy, **rapid** slashes" | four slashes 12–13 frames apart over a 40-frame active window; mashing `Y` adds none | "Rapid" oversells it, and unlike Kakashi's `side Y` there is no mash extension. Not a damage mismatch. |
| `down Y` marked `charge` ("grab ahold of sword, charging it with lightning") | 30- and 60-frame holds are byte-identical to a tap; startup 50 either way | The charge is in the animation, not in the input. Nothing to hold. |
| 7-koma `X` Chidori "**40** neutral / 60 dominant, hits 3, hold X to charge" | **30.0** over 3 damaging hits (4 latches) on Jotaro; **40.0** on Sanji in the same capture (`downB_X`) | Resolved, and this is the cleanest evidence yet for the 0.75 special factor (`jus-8ur4`): 30 = 0.75 × 40, and the guide's 40 is exact against a different victim. The "charge" only delays the release. |
| 7-koma `up X` Koukana Kisote "**44** / 66, hits 5, guard break, burn" | **33.03** direct over **5** hits on Jotaro = 0.75 × 44, plus **14.88** of burn; guard broken; effect id 226 | Hit count, guard break and the burn all match. 33.03 is the same 0.75 factor. The burn is 45% more damage than the guide's figure accounts for. |
| the guide names no inputs for the 7-koma specials beyond "X" and "up + X" | `X`, `side X`, `down X` and a held `X` all give the Chidori; `up X` gives Koukana Kisote; `air X` does nothing | This is the mapping. |
| combo "Select, X. 3 hits for **48** damage" | `SELECT_X70` gives the plain Chidori, 30.0 on Jotaro / 40.0 on Sanji; an `X` pressed inside the taunt is swallowed entirely | 48 is not reachable from the guide's own `X` figure of 40, so the guide contradicts itself. No damage bonus from the taunt was seen. |
| combo "Up+B, X. 3 hits for **48** damage" | `upB_X` = 3.0 + 30.0 = **33.0** over 4 damaging hits on Jotaro (43.0-worth on a Sanji-grade victim) | The cancel works, the total does not. Same 48 as the Select combo, so both figures are suspect. |
| combos "B, Y+up, B — 4 hits for 28" and "Up+B, B — 3 hits for 14" | not driven in that order; the per-move numbers add up exactly (7 + 6 + 8 + 7 = 28; 3 + 4 + 7 = 14) | Arithmetically consistent with our rows. Recorded as unverified, not as a match. |
| Weaknesses: "none of Sasuke's basic ground attacks causes the opponent to fall to the ground" | agrees for the ground normals — the only type-5 pops in the kit are `air B` and `up Y`'s second hit, and `up Y` sends the victim up, not down | Consistent. `air B` is an air attack, so it is outside the claim. |
| `air Y` "has lag time after the attack whether it hits or misses" | recovery 54, total 73 — the longest of the heavies | Matches. |
| Ultimate Action: 3–4 second replacement window, then half a second of invincibility | state 12 lasts **61 frames** (about 1 second) and the move deals nothing and costs nothing | The state is much shorter than the claimed window, so the counter armour must outlive state 12 — untested, it needs a CPU that attacks. |
| 4/5/6/8-koma specials (Chidori Nagashi, the 8-koma Chidori) | not driven | Need other decks. Records `0x10c`–`0x113` stay unassigned until then. |
| the guide's damage tables as "neutral / dominant" | every normal matched the neutral column exactly; both specials came in at 0.75 × the neutral column against Jotaro and at the neutral column against Sanji | Normals are unscaled on this victim; specials are not. |

## Does not match the owner

Empty. Both Sasuke entries in
[OWNER-NOTES.md](../../research/moveset-notes/OWNER-NOTES.md) reproduce, and so
do the two general notes that apply:

- **"Up B: a two-hit rising kick. The second hit can be cancelled into a
  different move"** — reproduced, into both `X` and `Y`, with the second kick
  removed rather than added to. See "The up-B cancel".
- **"Sasuke's down Y, a charge and sword swing … shatter moves without
  pop/launch knockback are believed not to inflict the very long hitstun of a
  real gauge-full break"** — reproduced exactly: `down Y` is type 2 with
  hitstun **20**, full 14.0 damage, gauge untouched. No 60-frame stagger.
- **"8-koma X vs 7-koma X: functionally about the same launcher"** — the
  7-koma `X` reaches the type-6 launcher handler `0x0215BAB8` with hitstun 60,
  which is the property the owner said carries over. The 8-koma's extra damage
  and windup are not measurable from this deck.
- **"Down+Y shatters guard instantly for every character"** — a fourth
  character.

## Not yet measured

- **The exact burn tick scaling.** The owner confirms the burn's character
  coverage and immunity exception. The 2 raw units per frame for 480 frames
  measurement came from one 160 HP Jotaro and does not distinguish a flat tick
  from a fraction of max HP.
- **What effect id 225 (shock) actually does.** It is dispatched by three of
  the Chidori's four latches and produced no measurable HP, hitstun,
  knockback or state difference over a 600-frame tail.
- **The effect-id encoding.** 225 / 226 here against 28 for Yoh's blind: the
  field is one byte at `M+0x173`, so either the scale is not a flat enum or the
  two readings are of different things.
- **`SELECT`'s counter window** — the guide's 3–4 seconds against the 61
  frames Sasuke holds state 12, and the half-second of invincibility after.
  Needs a CPU that attacks.
- **The other koma sizes' X specials** — the 8-koma Chidori and Chidori
  Nagashi, and any 4/5/6-koma forms. Each needs a deck built with that koma.
  The unmatched records `0x10c`–`0x113`, including both `type 6` launchers,
  stay unassigned.
- **Exact range edges.** Measured at 18.49 px and 60.64 px only; every
  boundary in between is unprobed.
- **`up B`'s cancel window edges.** `X` works at rel 16 and 20, `Y` at 16 and
  not at 20 (because the victim has left `Y`'s reach, not because the cancel
  failed). The earliest and latest cancellable frames are unknown.
- **Hitbox lifetime** as opposed to contact frames: the logs only see a hitbox
  that overlaps the victim.
- **What charges SP**, unchanged from Kakashi and Taikoubou: no normal, no
  special and no idle time adds any.
- **Support / help koma effects** — this deck's fourth slot is a Kakashi help
  koma (`chr_b` 23, HP 16) whose listed effect is "decreases damage taken by
  special attacks"; no runtime probe.

## Hazards

- **The victim fighter object is per-state, and this is now the third distinct
  value in one state family.** `pc-sasuke-npc-jotaro-dark-tournament` uses
  **`0x0222CFE0`**, against `0x0224EF00` in the Kakashi state and `0x02246A20`
  in the Taikoubou state, with the same P1 object, the same `M` pair and the
  same HP records in all three. Resolve slot 1 of the fighter table
  `0x021DEB3C` for every state and check `[[obj+0x1a8]+0x10]` lands on a sane
  `M`; a wrong base reads plausible, never-moving numbers.
- **The guard primer moves the target.** The throwaway `B` pushes the victim
  about 30 px away, so a guard capture needs a *larger* `--approach` than the
  unguarded one. `X` and `air Y` both whiffed their first guard run for this
  reason alone; `air Y` connected at `--approach 45`.
- **`--approach` is spent before the primer**, so the gap the primer opens can
  only be paid for by walking farther at the start.
- **An empty `guard_gauge_steps` list is ambiguous.** It means "nothing was
  blocked", which covers both a shatter and a whiff. Separate them with the
  victim's `obj+0x18`: 3 → 8 on the hit frame is a shatter, 3 all the way
  through is a whiff.
- **`M+0x172`/`M+0x173` are per-hit dispatch fields, not status flags.** Both
  read their value on the latch frame only and are 0 the next frame, so a
  sampler that polls them a few frames later sees a clean zero on a move that
  definitely applied a status. The burn is visible only as the HP tick.
- **A damage-over-time makes the default 180-frame tail lie.** `up X`'s burn
  starts at frame 194 — *after* the default tail ends — so the standard
  capture reports 33.03 for a move that deals 47.9. Any character the guide
  marks with a status needs a long tail.
- **The forced switch on `down B` is a trap for both the HP read and any
  follow-up.** The naive HP read is 32.0, and every move after it is hitting a
  different character with a different damage scale (`downB_X` reads the
  guide's full 40 because the victim is Sanji, not Jotaro).
- **`moveset_map.py --records` does not exist.** The module docstring
  advertises it; `argparse` never defines it, so the flag is a hard error. Run
  `scripts/analysis/move_records.py` separately for the static join.
- **Every dash overshoots from the default approach.** The full burst runs
  Sasuke from 636 to 546 px past a victim at 576, and even `dashB_early`
  reaches 558. `dash B` / `dash Y` need `--approach 0`; a 2-frame tap
  (`dashB_brake`) is not a dash at all and its attack whiffs at 60 px.
- **The hit's own fields are one frame ahead of the HP drop**, unchanged from
  Kakashi and Taikoubou: `M+0x16C`, `M+0x148`/`M+0x14A` on the latch frame;
  hitstun, `obj+0x112` and the HP step on the next.
- **Six hitstun cells read 255** (the idle −1) on the sample after the hit, in
  `upB_Y` hit 2, `B_upB` hit 2, `combo_BsideBYsideY` hit 5, `upX_guard` hits 2
  and 4, and `downB_X` hit 3 — the same instrumentation noise Kakashi and
  Taikoubou showed. Treat 255 as "not read", not as a value.
- **`X`'s first latch reads damage 0 and `obj+0x112` 0.** A summariser that
  drops zero-damage latches loses the grab that starts the Chidori; one that
  keeps them reports 4 hits where the guide says 3.
