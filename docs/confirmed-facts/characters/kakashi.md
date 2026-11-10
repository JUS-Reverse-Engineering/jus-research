# Kakashi (`chr_b` 23, `na_b_04`) — normals and 4-koma specials

**File correction (2026-09-12, `jus-lxyt`):** `chr_b` 23 is confirmed live,
but this character's collision **records** live in `na_b_04.bin`, not
`na_b_05.bin` — see "The authored records" below.

Tracker item `jus-kakashi-moveset-map-33lu`. Phase 1: the **normals** (B, Y, SELECT),
ground / air / dash / direction variants. Phase 2: the **X specials** of the
4-koma knowledge form this state's deck runs, their SP cost and their effect
channel. The 5- and 6-koma specials need other decks and are listed under
"Not yet measured".

Move checklist: [`kakashi--46618.json`](../../research/gamefaqs-movesets/kakashi--46618.json)
(GameFAQs, MasterTurtle v2.0 — player-written numbers, not ours). Owner quirks:
[OWNER-NOTES.md](../../research/moveset-notes/OWNER-NOTES.md). Raw per-frame
logs, plans and per-move summary JSON:
feel-captures/kakashi-2026-09-03/.
Driver: [`scripts/emu/moveset_map.py`](../../../scripts/emu/moveset_map.py)
(its docstring is the CLI reference; the roster campaign
`jus-roster-moveset-campaign-69it` reuses it). Phase 2's run log, addresses and
poke tests:
phase2-specials-notes.md.

---

## Conditions

| item | value |
|---|---|
| holder | phase 1 `opus-kakashi-2026-09-03`, phase 2 `opus-kakashi2-2026-09-03` — both released at the end (`stop_emu.sh`, `/tmp/jus_emu/HOLDER` gone) |
| launcher | `bash scripts/emu/launch_emu.sh`, JIT off, 2 launches in phase 1 (the second only to redo `down B` with corrected slot watches), 1 in phase 2 |
| fork build | `scripts/emu/build_info.json`, commit `c26edf0e0d75364823856c9272a103fe39e03999` |
| ROM | `jus.nds` sha256 `a9c9bf89e6d99548b7c87e822b217c3fb74ef25186535b06193a6fb73d0d6d27` (`scripts/emu/hashes.json`) |
| state | `pc-kakashi-npc-jotaro-dark-tournament` (owner build, re-saved by run 5; loads with `ok:true`) |
| attacker | P1 **Kakashi `chr_b` 23**, object `0x02228E80`, `M` = `[[obj+0x1a8]+0x10]` = `0x0220F30C`, element `0x0220C068`, HP 144.0 = the guide's 4-koma 136 plus the 8 leader bonus, so this deck runs the **4-koma knowledge** form |
| SP | P1 **`0x021DF730`**, the player slot's `+0x5C8` (guard-sp.md §1.4); reads `0x0909` at battle start |
| victim | CPU **Jotaro `chr_b` 28**, opponent deck `[28 Jotaro, 14 Sanji, 36 Kenshin, 46 Lenalee]`, slot 0 active (`0x021DF7F0+0x50i+0x25` bit 0), HP 160.0 |
| victim object | **`0x0224EF00`** — read from the fighter table `0x021DEB3C` slot 1. *Not* the `0x02230D60` of the `pc-kenshin-*` states (see Hazards) |
| victim `M` | `0x0220F494`, verified live as `[[0x0224EF00+0x1a8]+0x10]`; element `0x0220C0A8` |
| geometry | Kakashi x 631.29 px, Jotaro x 576.00 px; Kakashi faces/walks **LEFT** to reach him. Default recipe walks LEFT for 26 frames, which stops at 17.55 px |
| CPU | as-is (`なにもしない`, idle) for the damage runs; `COM設定 = ガード` (START, DOWN, A, A, START as five 1-frame plans, then saved to the transient bridge slot `kakashi-guard-tmp`) for the block runs |
| auto-heal | already OFF in this state; damage is read as the per-frame HP step, never as a before/after difference |
| positive control | **Kakashi B on the first run of the batch dropped the victim's HP record 160.0 → 152.0 = 8.0**, the guide's figure. Every later run in the batch carries the same B either as the move under test or as the guard primer |
| per-move plan | one `jusemu.py state load` + one plan per move, so every measurement starts from the same frame; 468 watched bytes/frame over 14 watches in phase 1, 512 over 15 (the validator's cap) once the SP watch was added |

### What each column means

- **startup** — frames from the attack input to the frame the victim's
  `M+0x16C` latches the attacker's `moveData[+1]` (the hit frame). The HP drop
  and the hitstun write land on the **next** logged frame; the bridge samples
  mid-frame, so that offset is instrumentation, not game behaviour.
- **active** — first hit frame to last hit frame inclusive (1 for a single-hit
  move). Not a hitbox-lifetime measurement: a hitbox that is live but never
  overlaps the victim leaves no trace in these logs.
- **recovery** — frames from the last hit until the attacker's `obj+0x18`
  returns to 0 (idle) or 1 (walk). **total** is input → that same frame.
- **hit type** — the victim's `M+0x16C`, i.e. the attacker's `moveData[+1]`,
  max-latched over the hits that landed that frame (physics.md §4.5).
- **hitstun** — the victim's `obj+0x115` whole-frame byte on the frame after
  the hit. **kb** — the staged pair `M+0x148`/`M+0x14A`, raw (÷256 = px).
- **leaves ground** — the attacker's `obj+0x18` entered 4/5/6/7 or `M+0x78`
  changed during the move.

---

## B (light)

| input | startup | active | recovery | total | hits | damage | hit type | hitstun | kb raw (x,y) | handler `obj+0xFC` | leaves ground |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `B` | 12 | 1 | 23 | 35 | 1 | 8.0 | 1 | 20 | (−640, 0) | `0x0215B720` | no |
| `side B` | 12 | 10 | 18 | 39 | 2 | 2.0 + 6.0 | 1, 2 | 20, 20 | (−384, −689), (−1024, −2065) | `0x0215B720` both | no |
| `up B` | 21 | 1 | 19 | 40 | 1 | 8.0 | 2 | 20 | (−512, −1652) | `0x0215B720` | no |
| `down B` | 18 | 1 | 26 | 45 | 1 | 8.0 (`obj+0x112`) | 5 | 40 | (−2304, −826) | `0x0215B910` | no |
| `air B` | 13 | 1 | 52 | 65 | 1 | 8.0 | 1 | 20 | (−640, **+1789**) | `0x0215B720` | yes (jump) |
| `dash B` | 12 | 1 | 23 | 35 | 1 | 8.0 | 1 | 20 | (−640, 0) | `0x0215B720` | no |

- **`side B` is a two-piece move.** Hit 1 (2.0) lands at frame 12 and leaves
  the victim's `M+0x78` at 0x20; hit 2 (6.0) lands 9 frames later with a large
  upward `kbY` and drives `M+0x78` to 0x00. The victim ends up airborne, which
  is what the guide means by "knocks enemies into the air" — but **both hits
  route to the grounded reaction handler `0x0215B720` and take hitstun 20**,
  not the ×2 pop or ×3 launcher. The vertical travel is the knockback vector,
  not a launched state. That is exactly §4.6's "no branch for a jab, pop or
  launcher shape".
- **`up B` also pops without a pop handler**: type 2, handler `0x0215B720`,
  hitstun 20, `kbY` −1652 (about 2/3 of side B's −2065), matching the guide's
  "doesn't knock the target up as high".
- **`down B` forces a character switch.** At the hit frame the opponent's
  active flag moves from slot 0 (Jotaro, 160 HP) to slot 1 (Sanji, 128 HP).
  A naive HP read then shows a 32.0 "drop" that is the gap between two
  characters, not damage; `obj+0x112` reads 8 and the blocked run adds 8 to
  the guard gauge, so the damage is 8.0. This is the one move in the kit where
  the HP-record method needs the slot watches.
- **`down B` and `down Y` are the only two normals that reach a pop handler**
  (`0x0215B910`, type 5, hitstun ×2 = 40).
- **`air B` is the only normal with a downward `kbY`** (+1789), which is the
  guide's "knock enemies downwards and through thin floors".
- **`dash B` is `B`.** Startup, damage, type, hitstun and knockback are
  byte-identical out of a double-tap dash. A full 12-frame dash burst runs
  Kakashi *past* Jotaro and the attack whiffs, so the capture brakes one frame
  into the burst (`dashB_early`).

## Y (heavy)

| input | startup | active | recovery | total | hits | damage | hit type | hitstun | kb raw (x,y) | leaves ground |
|---|---|---|---|---|---|---|---|---|---|---|
| `Y` | 19 | 3 | 25 | 46 | 3 | 4.0 + 4.0 + 16.0 = **24.0** | 2, 1, 2 | 20, 20, 20 | (−640, 0), (−384, −1652), (−1792, 0) | no |
| `side Y` (no mash) | 24 | 9 | 30 | 62 | 2 | 3.0 + 3.0 | 2, 2 | 20 each | (−384, −138) each | no |
| `side Y` (Y mashed) | 24 | 44 | 25 | 92 | **6** | 3.0 × 6 = **18.0** | 2 × 6 | 20 each | (−384, −138) each | no |
| `up Y` (standalone) | — no hit — | — | — | 99 | 0 | — | — | — | — | yes |
| `up Y` (after `side B`) | 18 | 34 | 47 | 98 | 3 | 5.0 + 5.0 + 8.0 = **18.0** | 2, 1, 5 | (255), 20, 40 | (−1280, −1102), (−1024, −689), (−1920, −964) | yes |
| `down Y` | 34 | 1 | 18 | 52 | 1 | 16.0 | 5 | 40 | (−3840, −689) | no |
| `air Y` | 18 | 1 | 40 | 58 | 1 | 12.0 | 2 | 20 | (**+1280**, 0) | yes (jump) |
| `dash Y` | 19 | 3 | 25 | 46 | 3 | 4.0 + 4.0 + 16.0 | 2, 1, 2 | 20 each | same as `Y` | no |

- **`Y` is 4 + 4 + 16 on three consecutive frames**, not three evenly spaced
  hits: the latch fires at frames 19, 20, 21 (attacker animation frames 14, 15,
  16). Total 24.0 at 17.55 px.
- **`side Y` whiffs entirely at 17.55 px** — no latch, no HP move, in both the
  plain and the mashed version. From the state's own starting distance
  (55.29 px, no approach) it connects. The shuriken have a minimum range; the
  guide's "the range isn't as good as you'd hope" understates it.
- **Owner's mash rule reproduces exactly.** Unmashed, two shuriken connect
  (6.0). With `Y` tapped every 4 frames after the input, **six** connect for
  18.0 — the guide's "up to 6 ... total of 18" is the mashed count, as the
  owner said. Every shuriken is 3.0, type 2, hitstun 20, kb (−384, −138).
- **`up Y` standalone never touches a grounded victim** (owner, 2026-09-03).
  It still costs 99 frames from input to idle and carries Kakashi off the
  ground (`obj+0x18` 9 → 6 → 0), which is the useful number for a whiff.
  Driven as `side B` → `up Y` (the up-Y input 26 frames after the side-B
  input, capture `sideB_upY`) all three hits land on the popped victim:
  5.0 / 5.0 / 8.0, the guide's numbers. The third hit is a **type-5 pop**
  (hitstun 40); the first two are grounded-handler hits.
- **`down Y` is an instant guard shatter: gauge untouched, guard broken at
  once, pop applied.** Against a live guard it dealt its full 16.0 HP damage
  and **added nothing to the guard gauge** — the gauge never moved, the guard
  broke immediately instead of wearing down, and the move's own reaction (the
  type-5 pop, hitstun 40) then applied. Every other normal adds its whole-unit
  damage to the gauge and does 0 HP damage. Maintainer ruling 2026-09-03: this is
  not a Kakashi property — every character's `down Y` shatters guard this way;
  which routine does it and what stagger it leaves is
  `jus-xcz0`. Its 34-frame startup is the longest in the kit (the guide's
  "charges for about half a second"); recovery is the shortest of the heavies
  at 18.
- **`air Y`'s `kbX` is positive (+1280)** while every other move's is
  negative. Kakashi throws the kunai down and forward, so on this geometry the
  projectile reaches the victim from the far side and the sign flips — §4.6's
  "the x sign chosen by relative position".
- **`dash Y` is `Y`.** Same caveat as dash B about the burst overshooting.

## SELECT (ultimate action)

| input | startup | active | recovery | total | hits | attacker state |
|---|---|---|---|---|---|---|
| `SELECT` | — no hit — | — | — | 63 | 0 | `obj+0x18` = **12** for 60 frames (input+3 to input+62), then 0 |

The tree-stump dodge. It deals no damage and never latches `M+0x16C`. State
code 12 is the same code physics.md §4.5 measured as a landing/can't-act
window with hitstun-table row `T[12] = 16`. The guide's "next 4 seconds" of
dodge window is longer than the 60 frames Kakashi spends in state 12, so the
dodge armour must outlive the state — untested here.

## Specials (4-koma knowledge)

This deck's Kakashi is the 4-koma knowledge battle koma (HP 144 = 136 + 8
leader bonus), so the guide's two X specials for that koma are the two that
exist here: a beam and the ninja dogs. **Six X inputs were driven; they map to
two moves and one no-op.**

| input | move | startup | active | recovery | total | hits | damage | hit type | hitstun | kb raw (x,y) | handler `obj+0xFC` | SP | effect `M+0x172/0x173` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `X` | beam | 26 | 40 | 20 | 85 | 13 | 3.0 + 1.5 × 12 = **21.0** | 2 (all) | 20 (all) | (−768, 0) then (−384, 0) × 12 | `0x0215B720` (all) | −0x100 | 0 / 0 |
| `side X` | beam | 25 | 40 | 20 | 84 | 13 | same | 2 | 20 | same | `0x0215B720` | −0x100 | 0 / 0 |
| `down X` | beam | 26 | 40 | 20 | 85 | 13 | same | 2 | 20 | same | `0x0215B720` | −0x100 | 0 / 0 |
| `X` held 60f | beam | 26 | 40 | 20 | 85 | 13 | same | 2 | 20 | same | `0x0215B720` | −0x100 | 0 / 0 |
| `up X` | dogs | 80 | 13 | — see below | 84 | 4 | 4.5 × 4 = **18.0** | 2, 1, 2, 1 | 20 (all) | (**0, 0**) × 4 | `0x0215B720` (all) | −0x100 | 0 / 0 |
| `air X` | — nothing — | — | — | — | — | 0 | — | — | — | — | — | **0** | — |

- **`X`, `side X`, `down X` and a held `X` are one move.** Startup differs by a
  frame, every other byte is identical, and all four debit the same `0x100` of
  SP. Holding the button for 60 frames changes nothing, so the 4-koma beam has
  no charge (unlike the 5-koma Raikiri the guide describes).
- **The beam is spawned elements, not a hitbox on Kakashi.** The C1
  capture (C1 §3-§4) replaces the first reading here ("two elements, 28
  frames in"):
  - 26 frames after the input an emitter parks 48 px in front of him. It
    lands only the first hit and stays 45 frames, unless it spawns past the
    wall line, which ends it at once.
  - 17 bolts: the first spawns with the emitter, then one every 2.56
    frames. Each is its own ColPrm record (18 records with the emitter) at
    9.375 px/frame. Each bolt lands at most one hit.
  - GDB names the record behind every contact. The fighter table
    `0x021DEB3C` never gains an entry, and Kakashi's own record has no hit
    node during X.
- **The beam pushes the victim out of itself.** Every hit stages kb (−384, 0),
  the measured distance grows 17.55 → 137.16 px over the move, and the gaps
  between latches widen from 2–3 frames to 4. That, not the per-hit damage, is
  what makes the total move. C1 (C1) measured 13 latches from 14 contacts
  (the first latch is two contacts), **21.0**, in all five near trials and
  in side, down and held X. The "19.5" first written here was an arithmetic
  slip for the same 13 hits. On a guarding victim it measured 16 blocked
  latches from 17 contacts. The one 14-hit run was the `sp_refuse` poke's
  artifact.
- **The dogs are spawned elements and land no knockback at all.** C1
  (C1 §8) corrects the count:
  - an anchor appears 24 frames in and lands nothing;
  - **four** dogs spawn at rel 65, 69, 73 and 77, each at a fixed offset
    from the victim;
  - each flies a straight line at a constant speed for 33 frames and lands
    one hit.

  (The first reading here saw three travellers at rel 70.)
  Their four hits stage kb exactly (0, 0) and the victim never moves a pixel.
- **`up X`'s "recovery" is not measurable the usual way.** Kakashi's own attack
  state ends at rel 83, but the last dog hit lands at rel 92, so the
  summariser's `recovery` (last hit → idle) goes **negative**. Read it as:
  Kakashi is actionable 84 frames after the input, and his dogs keep hitting
  for about 9 frames after that.
- **`air X` produces no action.** At both 14 and 24 frames after take-off the
  attacker goes jump (6) → landing (13) → idle (0) with no attack state and no
  SP debit; `air B` and `air Y` from the same setup show state 9 first. The
  input is ignored in the air, not a special that whiffed.
- **Neither special dispatches a status effect.** All eight hits read
  `M+0x172 = 0` and `M+0x173 = 0` (guard-sp.md §1.5), on both the latch frame
  and the frame after. A clean zero — the expected result for this koma, and
  now a measured one.
- **Neither special produces a `type 6` hit**, so Kakashi's four `type 6`
  records (`0x112`, `0x115`, `0x116`, `0x118`, `na_b_05.bin` ids — **now
  suspect**, see "The authored records" below: this character's normals turned
  out to live in `na_b_04.bin`, so these X-special ids have not been
  re-checked against `na_b_04.bin`'s equivalent range and may also be
  misidentified) still have nothing pointing at them and must belong to the
  bigger koma. Their measured knockback pairs match no record in
  `na_b_05.bin` — untested against `na_b_04.bin` (unlike the projectile
  *normals*, `side Y`/`down B`/`air Y`, which now do match `na_b_04.bin`
  records; see "The authored records" below).

## SP

**Correction (2026-09-12, `jus-e2h3`, live re-measurement; supersedes the
two-bytes-vs-one-word open question below):** the word this section calls
"the SP total" (`0x021DF730` for P1) is **not** the pool. It is two signed
bytes, `+0x730` = max bars `m` and `+0x731` = current bars `c` (Kakashi:
`m=9, c=9` at battle start, misread here as pool `0x0909`). The real
fractional SP pool is a u32 at `slot+0x5C8` = `0x021DF72C` — four bytes
below `+0x730`, the address this section's last bullet had flagged as an
unidentified "moves only while a special is live" counter and mislabeled
`slot+0x5C4` (arithmetic check: `0x021DF72C - 0x021DF164 = 0x5C8`, not
`0x5C4`). `[[obj+0x1B4]+0x5C8]` **does** reach it, with no offset —
see [guard-sp.md](../guard-sp.md) §1.4.

The player slot is `0x61C` bytes; P2's is `0x021DF780`. **One `m`/`c` pair
per player slot, with the four deck characters' HP as `0x50`-stride entries
inside that same slot** — the structural half of guard-sp.md GAP 3's
deck-shared question.

| event | bar delta (`c`) | pool delta (`x`, `slot+0x5C8`) |
|---|---|---|
| beam (`X`, `side X`, `down X`, `X` held) | **−1** | `+7200` gained across the hit (see below; net final pool value not independently read) |
| dogs (`up X`) | **−1** | `+3840` gained across the hit |
| `air X` | 0 | 0 |
| `SELECT` | 0 | 0 |
| `B` lands (8.0) | **0** | untested |
| `Y` lands (24.0 over 3 hits) | **0** | untested |
| 900 idle frames | 0 | untested (outside the watch range used for this row) |

- **A special spends one bar (`c -= 1`), debited on its first frame**, before
  any hit lands, through the wrapper `0x0207834C` calling the bar-borrow
  helper `0x0207830C` — not the pool word. Two beams in one run step
  `c: 9 -> 8 -> 7` (`m` unchanged at `9`).
- **Below `c = 1` the special is refused silently.** Poked `c` to `0`, `X`
  never enters attack state 10, deals nothing and leaves `c` alone; poked to
  `c = 1` it fires and leaves `c = 0`. So the starting `c = 9` is nine
  specials' worth.
- **Landing a normal adds no bar, and the bar count does not tick up on its
  own.** `B` (8.0) and `Y` (24.0 over three hits) both leave `c`/`m`
  untouched, and they are unchanged over 900 idle frames. This is a
  bar-count statement, not a pool statement: `0x020781E4` itself fires
  during the special with small per-hit gain amounts landing in the pool
  `x`, and the tail zeroes any such gain on arrival whenever `c >= m` — which
  was true at every baseline measured here (`c == m == 9`). Whether a
  normal ever feeds `x` while the gauge has room is untested.
- The beam and dogs pool gains (`+7200`, `+3840` above) are `0x020781E4`
  amounts accumulating in `x` during the special's active frames — a
  halving sequence per hit (beam: `3840, 1920, 960, 480`, summing to
  `7200`; the dogs figure here is the campaign's single static
  measurement, not independently broken into hits). `x` never carried
  across specials in these tests (each special's gain is measured, then
  the bar spend and any subsequent tail clamp reset the visible pool), so
  whether `x` itself persists between specials at a nonzero value is still
  open.

## On block (`COM設定 = ガード`)

The ガード CPU stands still until the first hit lands and only then holds
guard, so each of these runs presses `B` first as a throwaway primer and the
move under test 60 frames later. A blocked hit does **not** latch `M+0x16C`;
the only trace it leaves is the guard gauge `obj+0x102` stepping up.

| move | HP damage on block | guard gauge added | breaks guard |
|---|---|---|---|
| `B` | 0 | +8 | no |
| `side B` | 0 | +2 then +6 (per hit) | no |
| `up B` | 0 | +8 | no |
| `down B` | 0 | +8 | no |
| `Y` | 0 | +4, +4, +16 | no |
| `air B` | 0 | +8 | no |
| `air Y` | 0 | +12 | no |
| `down Y` | **16.0** | **0** | **bypasses the guard entirely** |
| `X` (beam) | 0 | +3, then +1 per 1.5 hit (18 over 16 hits) | no |
| `up X` (dogs) | 0 | +4 × 4 = 16 | no |

Every blockable hit adds exactly its whole-unit damage to the gauge, matching
physics.md §4.5's jab result — including the specials' fractional hits, where
the fraction is dropped (1.5 → +1, 4.5 → +4), which is guard-sp.md §0.5's
`gauge += damage >> 6` seen at a granularity the normals never reach. Both
specials are fully blockable: no HP damage, no break, and the SP is spent
anyway. The gauge decays 1 per frame starting 123 frames
after the last blocked hit (measured 0 → 8 at frame 99, then 8 → 0 over frames
222–229). `obj+0x104` (gauge max) read 0 in these samples because it holds 65
**only while the guard is up** (run 6, `jus-xcz0`); the max here is 65.

`side Y`'s gauge damage is **not measured**: the primer `B` whiffs at the
distance side Y needs, so the CPU never enters guard on that run.

## The authored records

**Correction (2026-09-12, `jus-lxyt`, live pointer trace,
[knockback-record-pointer-per-hit.md](../../research/findings/knockback-record-pointer-per-hit.md)):
Kakashi's collision records are in `chr/col/na_b_04.bin`, not `na_b_05.bin`.**
[collision-file mapping](../../research/chr_b-Complete-Mapping.md) maps `chr_b` 23 (Kakashi, independently
re-verified this session by peeking the live save state's player-slot byte
`+0x29`, which reads `23`) to file `na_b_05`, and everything below this note
through 2026-09-12 identified records against that file by
`frameStart`/`kbX`/`kbY` heuristics, never a direct pointer read. A GDB break
at `0x020817EC` (one instruction after the `moveData` load) captured the
actual pointer the hit processor reads for `B`, `up B`, both `side B` hits,
all three `Y` hits and `down Y`; every one of the 20 bytes at that pointer
matches a `na_b_04.bin` record **exactly**, at a clean 20-byte-aligned
offset — none match `na_b_05.bin` at all, at any offset. `na_b_04.bin` is
the file the same mapping table attributes to `chr_b` 22 (Sakura); whether
that is a one-off swap or a wider indexing bug in the `na_b_0*` series is
unresolved and out of this tracker item's scope (filed separately, see
`jus-lxyt`'s finding, "Concerns"). The table below is corrected to
`na_b_04.bin` indices; the pre-2026-09-12 `na_b_05.bin` identifications this
section used to carry (rec 0 for `B`, rec 3 for `side B` hit 2, rec 5 for
`up B`, rec 1 for `air Y`) are **retracted** — they were never pointer-verified
and, per the live trace, are simply wrong (right-looking numbers in the
wrong file).

Static side, from `python3 scripts/analysis/move_records.py 23 --list`
(still reads `na_b_05.bin` — **not yet updated for this correction**, so its
output no longer matches the live records identified below; treat its
Kakashi output as stale until `move_records.py`'s file resolution is fixed).
`na_b_04.bin` holds 38 records (760 bytes ÷ 20).

Matches confirmed by a direct GDB pointer read at `0x020817EC` (not
inference from `frameStart`/animation matching):

| move / hit | measured type | measured `(kbX, kbY)` | `na_b_04.bin` record | pointer (this session) |
|---|---|---|---|---|
| `B` | 1 | (5, 0) | rec 0 (kind 3, type 1, `frameStart` 8) | `0x21ba0e0` |
| `Y` hit 1 | 2 | (5, 0) | rec 1 (kind 3, type 2, `frameStart` 4) | `0x21ba0f4` |
| `Y` hit 2 | 1 | (3, 12) | rec 2 (kind 3, type 1, `frameStart` 4) | `0x21ba108` |
| `Y` hit 3 | 2 | (14, 0) | rec 3 (kind 3, type 2, `frameStart` 16) | `0x21ba11c` |
| `side B` hit 1 | 1 | (3, 5) | rec 4 (kind 3, type 1, `frameStart` 2) | not re-captured this session; field values match rec 4 exactly |
| `side B` hit 2 | 2 | (8, 15) | rec 5 (kind 3, type 2, `frameStart` 6) | `0x21ba144` |
| `up B` | 2 | (4, 12) | rec 7 (kind 3, type 2, `frameStart` 8) | `0x21ba16c` |
| `down Y` | 5 | (30, 5) | rec 13 (kind 3, type 5, `frameStart` 16) | `0x21ba1e4` |

`up B`'s hit type is **2**, not 1 — the live pointer's own type byte, not the
`na_b_05.bin` rec 5 guess (type 1) this section used to cite. Recheck any
downstream note that relied on the old type.

**Field-match extension (not pointer-traced this session):** the remaining
seven measured hits — the moves table above already lists their `kb raw
(x,y)` pairs — each match exactly one more `na_b_04.bin` record on
kind/type/frameStart/kbX/kbY. No GDB pointer was captured for these; the
match is a byte-for-byte field comparison against the same file the eight
pointer-traced hits above confirmed:

| move / hit | measured type | measured `(kbX, kbY)` | `na_b_04.bin` record |
|---|---|---|---|
| `side Y` (each hit) | 2 | (3, 1) i.e. raw (−384, −138) | rec 6 (kind 2, type 2, `frameStart` 3) |
| `up Y` hit 1 | 2 | (10, 8) i.e. raw (−1280, −1102) | rec 8 (kind 3, type 2, `frameStart` 5) |
| `up Y` hit 2 | 1 | (8, 5) i.e. raw (−1024, −689) | rec 9 (kind 3, type 1, `frameStart` 5) |
| `up Y` hit 3 | 5 | (15, 7) i.e. raw (−1920, −964) | rec 10 (kind 3, type 5, `frameStart` 8) |
| `air B` | 1 | (5, 0xF3) i.e. raw (−640, +1789) | rec 11 (kind 3, type 1, `frameStart` 8; `kbY` byte is `0xF3` = −13, the downward sign) |
| `air Y` | 2 | (10, 0) i.e. raw (+1280, 0) | rec 12 (kind 2, type 2, `frameStart` 12) |
| `down B` | 5 | (18, 6) i.e. raw (−2304, −826) | rec 14 (kind 3, type 5, `frameStart` 8) |

With these seven, `na_b_04.bin` records 0–14 account for all 15 hits this
character's normals have measured — every normal-attack knockback pair
Kakashi has produced resolves to a record in this one file, none left
over and none missing.

> **Update 2026-09-23 (tracker item `jus-wmqi.6.12`; the decode is written up in
> [vfx-sfx.md](../../rebuild/vfx-sfx.md) §2):** `shakeRowB`/`shakeRowA`
> below are record bytes `+0x0E`/`+0x0F`, the two selectors of the
> hit-effect dispatcher (ov6 `0x02153CE8`). They do not touch knockback, but
> they pick the hit spark and sound, and the onomatopoeia text. Rec 4 picks index 4
> (`SE_SLASH`, text `0x240016`) and rec 17 index 0 (`SE_HIT`, text
> `0x240004`), so a sound log of side B hit 1 would also tell them apart.

**Open ambiguity, `side B` hit 1 (rec 4):** `na_b_04.bin` rec 17
(`03 01 00 00 02 00 00 00 00 00 00 00 03 05 00 04 02 01 00 00`) is
byte-identical to rec 4 on every field the pointer trace reads (kind 3,
type 1, `frameStart` 2, `kbX` 3, `kbY` 5); the two records differ only in
`shakeRowB`/`shakeRowA`/`byte16` (unattributed/cosmetic fields, not part of
`move_records.py`'s knockback chain). Because side B hit 1's pointer was not
re-captured this session (see the per-hit pointer table in the finding), rec
4 vs rec 17 is not settled by a direct read — it is the lowest-indexed match,
consistent with the other seven pointer-traced hits landing at rec 0–13 in
move order, but that is an inference, not a pointer read. Re-run side B hit 1
under the `0x020817EC` breakpoint before treating rec 4 as fully confirmed.

**`move_records.py`'s file lookup is still stale.** `move_records.py kakashi
--list` resolves `chr_b` 23 to `na_b_05.bin` via
[collision-file mapping](../../research/chr_b-Complete-Mapping.md)'s File column, which this session's live trace
shows is wrong for this row (see "The authored records" above and
`jus-chrb-colfile-mapping-audit-x7i2`). Its output for Kakashi will stay
wrong until the mapping's File column and/or the script's resolution logic
are fixed; do not trust `move_records.py kakashi` until that lands.

`kbY` is recovered from the staged `M+0x14A` by §4.6's exact chain
(`y = kbY · −158 · F >> 8`, then `×223/256`, `F = 0x100` off a launcher), i.e.
`kbY = raw_y / −137.6`. It comes out an exact integer on every hit measured
here, so the vertical half of §4.6 reproduces on a second character.

**The horizontal half also reproduces exactly, once the right file is
used.** `raw_x/128 == record +0xC` holds bit-for-bit for every hit in the
table above (`jus-idiy`'s "does not consistently hold on Kakashi" framing is
retracted — it was comparing against `na_b_05.bin`'s wrong-file guesses).

**Positive result: `na_b_04.bin` records 0–14 account for all 15 measured
Kakashi hits, including the spawned-element moves.** `side Y` (shuriken),
`down B` (Pakkun) and `air Y` (kunai) do spawn a visible projectile element,
but the knockback the victim receives still field-matches an ordinary
`na_b_04.bin` collision record — recs 6, 14 and 12 respectively, same table
shape as every melee normal (see the field-match table above). The earlier
"these moves' knockback matches no record" claim was measured against the
wrong file (`na_b_05.bin`); against the right one, it does not hold. `down Y`
was already confirmed not to be a projectile (rec 13). Records
`0x10f`–`0x118` in the old (`na_b_05.bin`) static dump (`kind` 4/5, `type 6`
finishers, the X-special ids) were never re-derived against `na_b_04.bin`'s
equivalent id range — the X-special record identification in this section is
unaffected by this correction but also unconfirmed by it.

---

## Does not match the guide

| guide | measured | reading |
|---|---|---|
| `down B` "8" damage | 8.0 by `obj+0x112` and by the guard gauge, but the HP record appears to drop 32.0 | Not a real disagreement — the forced switch moves the HP address to a different character. Recorded here because the naive read is a trap. |
| `side Y` "throws up to 6 shurikens in a line", no range caveat beyond "the range isn't as good as you'd hope" | **zero** shuriken connect at 17.55 px; 2 unmashed / 6 mashed connect at 55.29 px | The move has a minimum range, which the guide never says. |
| `up Y` "will not hit the opponent unless they're above you" | agrees — but the guide lists it as a normal move with plain damage numbers | The 5/5/8 only exist as a follow-up. Recorded as owner behaviour, not a mismatch. |
| `Y` "24 damage at close range" | 24.0 exactly at 17.55 px | Matches. |
| `side B` "2 + 6", "knocks enemies into the air" | 2.0 + 6.0, victim leaves the ground | Matches, but the launch is a knockback vector, not a launched state: both hits take the grounded handler and hitstun 20, so a launcher-specific rebuild path would be wrong here. |
| `down Y` "Breaks guard" | it does not touch the guard gauge; the guard breaks at once and the move's own pop applies with full damage | Matches. The mechanism is an instant shatter, not the gauge wear-down-then-break of physics.md §4.5, and it is universal to `down Y` rather than a Kakashi trait (owner, `jus-xcz0`). |
| battle-koma HP 136 / 152 / 168 | this state's Kakashi reads **144.0** | Resolved: 144 = the 4-koma 136 plus the 8 HP leader bonus, so the deck runs the 4-koma knowledge form and the guide's numbers are pre-bonus. |
| 4-koma X "beam attack ... up to 30 damage if the enemy is right next to you" | 3.0 + 1.5 per hit, **21.0** over 13 latches (14 contacts) at 17.55 px and at 55.29 px | The per-hit damage is stable; the hit count is not, because the beam's own knockback pushes the victim out of it (17.55 → 137 px). 30.0 is 3.0 + 1.5 × 18, i.e. 20 contacts on 19 latches (the first latch holds two). Against Jotaro at the wall, C1 got 18 contacts and 27.0, and the wall broke after the 14th latch (C1 §6; graded partial, since the wall state has him at 64 HP). Not reproduced. |
| 4-koma X "summons some of his ninja dogs ... 24 damage if all the dogs hit" | **18.0** = 4.5 × 4, from four dogs of one hit each (C1), at both 17.55 and 55.29 px and at the wall | 24 is not 4.5 × an integer. Four dogs spawn every time, and each hits once, so the guide's figure is not this koma's, or it counts something else. Unmatched. |
| the two 4-koma specials, listed without inputs | `X`, `side X`, `down X` and a held `X` all give the beam; `up X` gives the dogs; `air X` does nothing | The guide names no inputs at all for either special. This is the mapping. |
| 5-koma Raikiri "how long you charge just changes the distance" | the **4-koma** beam has no charge: a 60-frame hold is byte-identical to a tap | Not a disagreement — the guide only claims the charge for the 5-koma move, which this deck cannot reach. Recorded so nobody reads the 4-koma beam as a charge move. |
| specials (Chidori / Raikiri / Mangekyou, and the 5-koma dogs) | not driven | Need 5- and 6-koma decks. |

## Does not match the owner

Empty. The one Kakashi note in
[OWNER-NOTES.md](../../research/moveset-notes/OWNER-NOTES.md) — "forward Y
throws more shuriken when Y is mashed, and the guide's 'up to 6' is the mashed
count" — reproduces exactly: 2 shuriken unmashed, 6 mashed, 3.0 each. The
owner's mid-session note that `up Y` only connects on an airborne victim also
reproduces: standalone `up Y` never latches, and `side B` → `up Y` lands all
three hits.

## Not yet measured

- **The other koma sizes' X specials** — 5-koma Raikiri and dogs, 6-koma
  Chidori and Mangekyou Sharingan, and the laughter 6-koma. Each needs a deck
  built with that koma; this state's deck is the 4-koma knowledge form and
  nothing in a savestate can change which koma is equipped. The `type 6`
  launcher records `0x112`, `0x115`, `0x116` and `0x118` stay unmatched until
  someone drives those decks.
- **SP observation limit in this capture.** No gain was observed here, but
  this is not evidence that normals or specials cannot generate SP. Later
  work established the deposit-and-payout model and discarding of gains at
  full bars (`jus-e2h3`, `jus-36wu`; [guard-sp.md](../guard-sp.md)). Gameplay
  triggers and passive cadence continue under `jus-1bkw`.
- **`slot+0x5C4`**, the word next to the SP total that only moves while a
  special is live.
- ~~The beam against a cornered victim.~~ **Closed 2026-09-25, partial,** by C1 (C1 §6):
  18 contacts and 27.0 at the wall, which breaks after the 14th latch. That
  is partial: the wall state has Jotaro at 64 HP, and whether the owner will
  make a full-HP wall state is open.
- ~~Whether more than three dog elements can spawn.~~ **Closed 2026-09-25:**
  four spawn every time (C1 §8), for 18.0; the guide's 24 is still unmatched.
- **`side Y` guard-gauge damage** — needs a primer that connects at shuriken
  range.
- **Hitbox lifetime** as opposed to contact frames: the logs only see a hitbox
  that overlaps the victim. **Still open.** C1 (§3, §8) measured part of it
  for the specials: the beam's emitter lives 45 frames (four misses) and
  each dog 33 frames. In two right-facing misses from the wall state
  70.44 px apart, every bolt clear of the wall, the first four bolts end
  after 33 frames. A bolt still flying at s 63 stops there and ends at s 67
  with the emitter instead, so bolt 5 lives 36 frames and bolt 6 34. The
  reads can't tell a 33-frame timer from a ~300 px travel cap (constant
  speed from the spawn); the frames match either way. Bolts also end on a
  hit or at the wall. The normals are open.
- **Whether a `B` press during recovery registers as a new attack.** Recovery
  here is "`obj+0x18` back to 0/1"; the earliest actionable frame was not
  probed with a follow-up input.
- **`SELECT`'s dodge window** — the guide's 4 seconds against the 60 frames
  Kakashi holds state 12. Its frame data reproduced exactly in phase 2 (state
  12 for frames 3–62, total 63) and it costs **no** SP.
- **The `up Y` hit-1 hitstun byte** read 255 (the idle −1) on the sample after
  the hit; the other two hits read 20 and 40. Treat that one cell as
  instrumentation noise, not a value.
- **Support / help koma effects** and the passives (wall-jump, sees invisible
  opponents, reduced special damage) — no runtime probe.

## Hazards

- **The victim fighter object is per-state.** In
  `pc-kakashi-npc-jotaro-dark-tournament` it is `0x0224EF00`, not the
  `0x02230D60` that HANDOFF's "Session-local values" lists for the
  `pc-kenshin-*` states. `0x02230D60` still *reads* plausible numbers there —
  a stable state code, a `+0x110` of 10, a `+0x112` of 11, a gauge of 1/1 —
  and **not one byte of it moves when a hit lands**, so a run that used it
  looked like a working measurement with a strangely inert victim. Resolve
  slot 1 of the fighter table `0x021DEB3C` for every new state; the
  `[[obj+0x1a8]+0x10]` chain then reaches `M` correctly, and it reads garbage
  (`0x00090009`) off the wrong base, which is the cheap check.
- **The opponent slot fields are offset from the current-HP address, not from
  a struct base 0x18 earlier.** `+0x25` active and `+0x29` `chr_b` are
  relative to `0x021DF7F0`. Reading them relative to `0x021DF7F0 − 0x18`
  returns all zeros, which looks like "no switch happened" — and that is
  exactly the wrong answer for `down B`.
- **The hit's own fields are one frame ahead of the HP drop.** `M+0x16C`,
  `M+0x148`/`M+0x14A` and the reaction id are only readable on the latch
  frame; hitstun, `obj+0x112` and the HP step appear on the next sample. A
  summariser that reads everything on the HP-drop frame reports hit type 0,
  hitstun 0 and knockback 0 for a real hit.
- **Reaction handler addresses differ from physics.md §4.5's.** Measured
  `obj+0xFC` is `0x0215B720` for types 1 and 2 and `0x0215B910` for type 5,
  where §4.5 records `0x0215B6A0` and `0x0215B870` for the same ids
  (+0x80 and +0xA0). The routing behaviour is identical (grounded vs ×2 pop);
  which of the two addresses is the table entry and which is a point inside
  the routine is not settled here.
- **A double-tap dash overshoots a nearby victim.** The full 12-frame burst
  carries Kakashi from 631 px to about 500 px past a victim at 576 px, and
  every dash attack whiffs from behind. Brake one frame into the burst.
- *(Correction 2026-09-23, `jus-wmqi.6.4`: `obj+0x72` counts frames of
  unchanged input, not animation frames, so this bullet's premise is moot;
  see [anim-timing.md](../../rebuild/anim-timing.md) §7. The attack
  animations' real lengths are in that page.)*
  **`obj+0x72` does not reset when an attack ends**, so "the attack
  animation's length" cannot be taken as the maximum of that counter over the
  whole capture. There is no animation-id field anywhere in `obj+0x00..0x80`,
  which is why the record match above leans on `frameStart` and the hit type
  rather than on a runtime animation id.
- **`obj+0x104` (guard gauge max) reads 0 unless the guard is up** — a
  sampling artifact of phase 1; run 6 (`jus-xcz0`) read 65 while guarding and
  reached the gauge-full break on the tenth blocked B.
- **`[[obj+0x1B4]+0x5C8]` is the wrong way to the SP total.** `obj+0x1B4` reads
  `0x021DEBE4` here and `+0x5C8` off that base is a flat 0 that never moves —
  which reads as "the meter is empty", not as "wrong address". The SP word is at
  the player slot found from the current-HP address (`HP − 0x6C`, then
  `+0x5C8`): `0x021DF730`. Re-derive it per state the same way.
- **A special with too little SP leaves no trace at all.** The attacker never
  enters attack state 10, no animation plays and SP is not touched, so a capture
  of a refused special is indistinguishable from a whiff unless the SP word is
  watched. Read SP before trusting a "the special did nothing" run.
- **`recovery` is meaningless for a move whose spawned elements outlive the
  attacker.** `up X`'s dogs land their last hit 9 frames after Kakashi is back
  to idle, so the summariser's last-hit-to-idle recovery comes out negative.
- **State 13 is the landing state, not an air attack.** `air X` shows jump (6) →
  13 → idle (0), which looks like an air move that whiffed; `air B` and `air Y`
  show attack state 9 *before* 13, which is how you tell them apart.
- **The watch budget is now full.** `moveset_map.py` watches exactly 512 bytes
  over 15 watches, which is the plan validator's cap; a sixteenth watch needs
  one of the existing ones shortened.
