# Match rule-settings table, and the time-out counter: static trace (jus-l77m)

Tracker items: `jus-l77m`.

## Grade: mixed — CONFIRMED_STATIC (settings struct, rulemess.bin format, timer decrement site) / observed once (time-out draw-vs-sudden-death shape, point mode, じかん 30, Goku vs CPU Luffy; HP at the expiry frame unmeasured, HP-based tiebreak unobserved and not ruled out)

**Static analysis only** — no emulator, no GDB, per this ticket's scope. Two of the
ticket's premises turned out not to hold once checked against the bytes, and are
corrected below rather than forced into the requested shape.

## Conditions

- Static analysis against the checked-in ROM extraction and disassembly:
  `jus_files/ripped_jus_files/bin/rulemess.bin` (1682 bytes) and
  `jus_files/analysis/disasm/{arm9,ov0..ov13}.txt`, read via `scripts/analysis/query.py`
  and `scripts/decomp/thumb_disasm.py` (the latter needed because the Thumb code in
  this finding lives inside the documented "`ov6.txt` decodes Thumb regions as ARM"
  tooling hazard — `docs/confirmed-facts/INVENTORY.md`).
- Builds on three prior `CONFIRMED_STATIC`/`CROSS_CONFIRMED` findings, not re-derived
  here: `p163-rule-select-screen-mapped-to-memory.md` (the six-setting rule-select
  struct at `0x020AFE90`), `p165-mode-table-is-rulemess-bin.md` (`rulemess.bin` is the
  22-entry rule-mode table, and the `144`-frame constant), `p166-per-mode-handler-table.md`
  (the 31-entry, ov6, 12-byte-stride per-mode handler table at `0x02170EAC`).
- Raw evidence (hex dumps, decode script, full disassembly excerpts, the overlay-
  ambiguity check, and Codex's full second-opinion transcript): `../feel-captures/
  match-presets-2026-09-12/RESULTS.md` and
  `../feel-captures/match-presets-2026-09-12/codex_second_opinion_timeout.md`.
- Codex second opinion: `codex exec -m gpt-5.6-sol`, given the raw hex/disasm with no
  hypothesis stated, asked to conclude independently and flag disagreements with my
  framing. It agreed with the structural reads below and independently flagged two
  precision issues (noted inline) that are folded into this write-up.

## Premise correction: `rulemess.bin` is not a settings-preset table

The ticket asked for a preset table with columns "time | rounds/stock | HP setting |
SP setting". That table doesn't exist in `bin/rulemess.bin`, and the rule-select RAM
struct it was meant to cross-check against doesn't have those fields either.

`CONFIRMED_STATIC`: `rulemess.bin` is 22 records of 16 bytes, each holding **three
self-relative Shift-JIS string-fragment pointers and one small classifier int**
(`0`, `1`, or `2` — no other values occur), not a numeric match-settings table. Decoded
in full in `../feel-captures/match-presets-2026-09-12/RESULTS.md` §2. The three strings per record concatenate into one
word-wrapped in-game rule description (verified for record 0: "KO the opponent for
points; −1 for being KO'd, −2 for a wipe"). There is no time-limit-value field, no
round/stock-count field, no HP field, and no SP field anywhere in this file. Codex,
given only the hex bytes and the self-relative decoding rule, reached the same
structure independently and explicitly said it would not call this a settings-preset
table.

`CONFIRMED_STATIC` (already established by `p163`, re-checked here): the rule-select
screen's RAM struct at `0x020AFE90` likewise has no HP or SP field. Its six settings are
rule/mode (`+0x10`), time (`+0x1C`), COM count (`+0x33`, `PLAUSIBLE`), and three
booleans — items, gimmick, team battle (`+0x2B`/`+0x2C`/`+0x2D`). "Rounds/stock" isn't
a setting on this screen either; nothing in either the RAM struct or the file suggests
this game's versus rules have a per-round or per-stock concept exposed at rule-select.

So Task 1's requested table becomes a **rule-mode table**, not a settings-preset table:

| mode idx | classifier (`+0xC`) | time-limit formula selected | description (abridged) | evidence |
|---|---|---|---|---|
| 0 | 0 | `(じかん+1)*144-1` | KO for points, point battle | text @ file offset 0x160 self-relative decode; formula per `p163`/`p165` |
| 1 | 2 | `(じかん+1)*144-1` | no respawn, survive (death match) | same |
| 2 | 2 | `(じかん+1)*144-1` | collect J-symbols | same |
| 3 | 0 | `(じかん+1)*144-1` | tutorial | same |
| 4 | 2 | `(じかん+1)*144-1` | collect items | same |
| 5 | 1 | `じかん*60` | mission: evade with target for set time | same |
| 6 | 1 | `じかん*60` | mission: break all walls in time | same |
| 7 | 1 | `じかん*60` | mission: KO target in time | same |
| 8 | 1 | `じかん*60` | mission: surprise every opponent | same |
| 9 | 1 | `じかん*60` | mission: char-change everyone | same |
| 10 | 1 | `じかん*60` | mission: protect target | same |
| 11 | 1 | `じかん*60` | mission: evade full time | same |
| 12 | 0 | `(じかん+1)*144-1` | treasure chests, target grab | same |
| 13 | 0 | `(じかん+1)*144-1` | point battle, mirrored decks | same |
| 14 | 0 | `(じかん+1)*144-1` | point battle, handicap start | same |
| 15 | 1 | `じかん*60` | mission: capture target in time | same |
| 16 | 0 | `(じかん+1)*144-1` | no respawn survive (variant text) | same |
| 17 | 2 | `(じかん+1)*144-1` | collect items (dup of 4) | same |
| 18 | 0 | `(じかん+1)*144-1` | point battle (dup of 0) | same |
| 19 | 2 | `(じかん+1)*144-1` | death match (dup of 1) | same |
| 20 | 2 | `(じかん+1)*144-1` | J-symbols (dup of 2) | same |
| 21 | 1 | `じかん*60` | mission: KO target in time (short form) | same |

Byte offsets within a record (stride 16 bytes, `CONFIRMED_STATIC`, verified by decode
script producing valid strings for all 22 records with zero decode failures):

| field | offset | width | meaning | evidence |
|---|---|---|---|---|
| text line 1 pointer | `+0x00` | `s32`, self-relative | first line of rule description | decodes to valid Shift-JIS string for all 22 records |
| text line 2 pointer | `+0x04` | `s32`, self-relative | second line | same |
| text line 3 pointer | `+0x08` | `s32`, self-relative | third line (often empty for short descriptions) | same |
| classifier | `+0x0C` | `s32` | `0`/`1`/`2`; selects the time-conversion branch and separates "mission" (1) from "versus" (0, 2) rule families | `p163`'s time-conversion disasm branches on this exact classifier; `p166`'s handler table confirms modes 0-2 by pill-name cross-check |

`0x020AFE90` struct fields (already `CONFIRMED_STATIC`/`CROSS_CONFIRMED` in `p163`; not
re-derived, included for completeness against the ticket's ask):

| field | dest offset | address | width | evidence |
|---|---|---|---|---|
| rule/mode | `+0x10` | `0x020AFEA0` | byte | `p163`; `CROSS_CONFIRMED` by `p165` against runtime pill-tap |
| time limit, frames | `+0x1C` | `0x020AFEAC` | word (converted from a menu halfword) | `p163`/`p165`, `CROSS_CONFIRMED` (`4463` measured at じかん 30) |
| items | `+0x2B` bit 0 | `0x020AFEBB` | bit | `p163`, confirmed at runtime by `justoolkit-ed` |
| gimmick | `+0x2C` bit 1 | `0x020AFEBC` | bit | same |
| team battle | `+0x2D` bit 2 | `0x020AFEBD` | bit | `p163`, by elimination |
| COM count | `+0x33` | `0x020AFEC3` | byte | `p163`, `PLAUSIBLE` |

## Task 2: the time-out counter, traced to its decrement instruction

`CONFIRMED_STATIC`: a live per-frame countdown exists at **battle-root-relative offset
`+0x10`** on the object dispatched through the per-mode handler table (`p166`'s
`0x02170EAC`, ov6). It is read, decremented by exactly 1, and written back at ov6
`0x0214F9E0`-`0x0214F9E4`:

```
0x0214f9e0: ldr r0, [r4, #0x10]
0x0214f9e2: sub r0, r0, #1
0x0214f9e4: str r0, [r4, #0x10]
```

This function (`0x0214F998`, ov6, full disasm in `../feel-captures/match-presets-2026-09-12/RESULTS.md` §4b) is tail-called, once
per rendered frame, from the mode-0 (point-battle) per-tick handler `0x0214FA78` — the
same address `p166`'s runtime cross-check (`jus-hsc`) measured at `root+0x000` when
mode 0 was poked. The call chain (mode-0 tick handler -> countdown function) is
`CONFIRMED_STATIC` from the disassembly.

`CONFIRMED_STATIC`: the countdown function is not mode-0-specific. A scan of the
per-mode handler block (ov6 Thumb, `0x0214F800`-`0x02152800`) finds exactly **nine**
`bl 0x0214F998` call sites, at `0x0214FADE`, `0x0214FC28`, `0x0214FDEE`, `0x0214FEE8`,
`0x021500D0`, `0x0215025A`, `0x0215037E`, `0x021503D4`, and `0x02150C86`, mapping to
rule modes 0, 1, 2, 3, 4, 5, 6, 7, and 21 respectively (`p166`'s 12-byte-stride handler
table order). Modes 8-20 were not observed calling `0x0214F998` in this scan; whether
they have their own separate countdown or none at all is `[unverified]`.

Guard and thresholds, also `CONFIRMED_STATIC` from the same function:

- `[root+0x10] == 0xFFFFFFFF` (i.e. `-1` signed) is checked **first**, before any
  decrement, and short-circuits to a `0` return with no further decrement.
  `CONFIRMED_STATIC`, correcting the earlier "not claimed" qualifier: `-1` **is**
  explicitly assigned elsewhere. The root initialiser `0x0214F804` (ov6) reads byte
  `0x020AFEBA` at `0x0214F882`-`0x0214F88E`; when that byte is set, it stores
  `-1` (`mov r0,#0`; `mvn r0,r0`) into `[root+0x10]` and returns before the mode
  dispatch runs — i.e. `-1` = timer disabled, matching "training mode has no clock"
  (`docs/confirmed-facts/physics.md` §5). Ordinary unsigned underflow after the
  counter passes 0 remains a second, independent way to reach the same sentinel value.
- At exactly `1440` (`10 x 144`) remaining, and only if a flag byte at `root+0xCC` is
  set, it fires `event(0x7A, 3)`.
- At `<= 720` (`5 x 144`) remaining, and only when a helper at `0x0200D12C` (assumed
  divmod, `not claimed` from this snippet alone) returns a zero remainder against 144,
  it fires `event(0x7A, 4)`.
- After the decrement, if the new value is `< 144` (one TIME unit), it fires
  `event(0x7A, 6)` and **returns 1**; otherwise it returns **0**.

`CONFIRMED_STATIC`: `root+0x10`'s seed is the same `p166` root, and it comes straight
from the rule-select time limit. The root initialiser (`0x0214F804`, ov6) sets
`[root+0]` to the default handler `0x02150F65`, `[root+8]` to the mode index,
`[root+0x14]`/`[root+0x18]` to the player count, and then at `0x0214F8A4`-`0x0214F8A8`
loads `r0 = 0x020AFE90` (the `p163` rule-select struct base), reads `[r0+0x1C]`
(`0x020AFEAC`, the time limit in frames), and stores it into **both** `root+0x10` and
`root+0xC` — i.e. the countdown's backing word and the "total frames" word it is
diffed against in the divmod helpers below share one seed. Modes 3 and 7 skip this
read entirely and hard-code the pool value at `0x0214F8C0` = `0x116F` = `4463` =
`(30+1)*144-1` into both fields instead (`0x0214F892`-`0x0214F8A2`).

`CONFIRMED_STATIC`, a third independent leg for physics.md §5's 144-frames-per-unit:
the divmod helper `0x0200D12C` has three neighbouring call sites sharing the same
`-1` guard as the decrement function — `0x0214F8C4` computes `(root+0xC − root+0x10)
÷ 144` (frames elapsed, divmod with `r1=0x90`), `0x0214F8E0` computes `root+0x10 ÷
144` (the displayed `TIME` units remaining, divmod with `r1=0x90`), and `0x0214F8F8`
computes the plain difference `root+0xC − root+0x10` with no divmod call (used by the
`1440`-frame threshold check above). All three read `root+0x10` under the identical
`[root+0x10] == 0xFFFFFFFF -> return 0` guard as the decrement function.

`[unverified]`: that `event(0x7A, N)` calls are UI/audio countdown cues rather than
something else. Plausible from the fixed thresholds and event-style call shape, but the
event dispatcher (`0x0207342C`'s target) was not traced in this pass.

### What this counter is not shown doing: no winner-selection comparison gated on expiry

No winner-selection comparison is gated on expiry in the countdown function or the
mode-0 tick handler; the expiry transition and match-end callback are traced below.

`[unverified]` — more precisely, refuted as *findable in this pass*: **no code was
located, in the countdown function or its caller, that compares two players' HP or
score specifically when the counter reaches zero to decide a winner.**

The countdown function (`0x0214F998`) touches only the counter word and the `+0xCC`
flag — never a per-player field, never a second player's data. Its caller
(`0x0214FA78`, disasm in `../feel-captures/match-presets-2026-09-12/RESULTS.md` §4a) does run a continuous, unconditional,
every-tick all-pairs comparison of a per-player field at `+0x1C` (incrementing a
per-player "beats" counter at `+0x4C` for every opponent with a lower value, and a
saturating "streak" byte at `+0xC0` tracking unbroken leads) — but this ranking update
runs on **every tick regardless of the counter's value**, not conditionally on the
counter reaching zero. Nothing in the disassembled code branches on "counter has hit
zero, now pick a winner." The return value from the countdown function (`0`/`1`,
signalling "under one TIME unit remains") passes straight through as this handler's own
return value to whatever dispatches it, and that dispatcher was not traced this pass.

Codex, given the same bytes independently, reached the identical conclusion: "There is
no winner-selection comparison in the shown countdown function... the actual win, draw,
or tiebreak decision is not present in the supplied instructions." It also flagged that
the return-1 condition is `< 144`, not `== 0` — a whole TIME unit's worth of frames
where the handler returns 1, not a single-frame event — which matters if some later
state machine treats "return 1" as the completion signal rather than watching for the
counter to hit exactly zero or the `-1` sentinel.

So, against the ticket's three options:

- (a) draw
- (b) sudden-death continuation
- (c) P1/P2 default-winner tiebreak

**None can be confirmed or refuted from this pass.** `[unverified]` all three. The only
concrete, load-bearing fact traced all the way to a store instruction is the decrement
site itself and its three threshold branches (all `CONFIRMED_STATIC`); the branch that
actually resolves a tie was not located in the code reachable from here within this
ticket's scope.

### The expiry transition and match-end callback, traced

`CONFIRMED_STATIC`: the countdown's return value flows upward through a small,
fully-traced chain into a match-end callback, even though that callback does not
itself compare HP or score. Ov6 addresses throughout:

- `0x0214F948` (`push {r3,lr}`; `ldr r1,[r0]`; `blx r1`; `pop {r3,pc}`) is a thin
  trampoline that calls whatever function pointer sits at `[root+0]` — the countdown
  function chain's caller uses this to invoke the per-tick handler indirectly.
- `0x0214DBCC` is the in-battle per-frame state function. It unconditionally bumps a
  global frame counter at `0x020A0F10` (confirmed via the literal pool at
  `0x0214DDA0`, which decodes to the word `0x020A0F10`) on every call, then runs its
  own per-tick dispatch.
- Inside that function, at `0x0214DD32` it calls `0x0214F948` (the trampoline above)
  and tests the result at `0x0214DD36` (`cmp r0,#0`); `beq 0x0214DD56` skips the
  expiry-only block when the countdown has not signalled completion.
- When taken (non-zero, i.e. expiry), `0x0214DD3E` (`bl 0x0214F938`) installs the
  default handler `0x02150F65` into `[root+0]` and clears `root+0xC8` — resetting the
  per-mode dispatch back to its default state. `0x0214DD4A` (`blx [[root]+0xD4]`)
  invokes another indirect handler. `0x0214DD52` (`blx 0x02028384`, with `r1` loaded
  from the literal pool at `0x0214DDB4` = `0x0214DDBD`, i.e. Thumb function
  `0x0214DDBC`) registers that address as a callback with the game's generic
  callback-registration routine — this is the "match-end callback."
- `0x0214DDBC` (the registered callback) iterates player objects via
  `root+0xDC + i*4` (loop bound read from `root+0x158`, i.e. `[root + 0x56*4]`, a
  player-count field), and for each player calls `0x0215911C(player, 1)` then
  `0x0215911C(player, 0)`, clears byte `player+0xF5`, and calls `0x0215B460(player)`.
  After the loop it re-fires `event(0x7A, 6)` (`0x0214DE3E`, `blx 0x0207342C` with
  `r0=0x7A`, `r1=6`) and chains into `0x0214DE64` -> `0x0214DEAC`, two more small
  handlers gated on flag bytes that fire further `event`s and re-enter this same
  chain recursively (`bl 0x0214DEEC`, a two-flag-check helper, at the tail of each).
- Separately, `0x0214DD76`-`0x0214DD98` (inside the same function as the mode-0
  handler's continuous ranking update) reads each player's `+0x4C` "beats" counter in
  a loop, picks the index of the first player whose `+0x4C` is zero (i.e. the first
  unbeaten player), writes that index to `0x02171AA0` (confirmed via the literal pool
  at `0x0214DDB8`, which decodes to the word `0x02171AA0`), and then calls
  `blx 0x02152078(that index)`.

None of this chain compares two players' HP or score at the moment of expiry — the
`+0x4C`/`+0x1C` ranking machinery it reads from was already established above as
running unconditionally every tick, not gated on the counter. What is now traced,
that was not traced before, is: the countdown's `1`/`0` return value does reach a
real match-end callback and a "first unbeaten player" index write, not a dead end.
Whether `0x02152078`, `0x0215911C`, or `0x0215B460` contain the actual
win/draw/tiebreak *decision* (as opposed to consuming a decision already made
elsewhere) is `[unverified]` — they were not disassembled past their entry points in
this pass.

One corroborating but non-conclusive data point, carried over from prior (unrelated)
static work rather than newly found here: `p166-per-mode-handler-table.md` observed
(via runtime screenshot, not statically) that **modes 18 and 20** — which never build a
battle object at all — go straight to a result screen showing **both players marked
WINNER simultaneously at 0 points**. That is direct evidence the engine's result-screen
code *can* express a tie as "both sides marked WINNER," which is consistent with (a) as
a real code path somewhere in this engine — but it was observed for a degenerate
never-starts-a-battle case, not for a real match hitting `[root+0x10] == 0`, and is not
itself evidence about the timeout path specifically.

## Overlay-ambiguity check (why the addresses above are trustworthy)

`0x0214F998` and `0x0214FA78` sit inside the shared `0x0214CD20` overlay window that
`ov0`-`ov9` alias at runtime (`docs/confirmed-facts/INVENTORY.md`, "Tooling hazards").
`query.py func 0x0214F998` (no overlay pinned) resolves the address to **ov8**, and
`thumb_disasm.py ov8 0x0214f998` decodes a different function entirely at the same raw
address. The reads in this finding are pinned to **ov6** specifically because `p166`
already tied the containing table (`0x02170EAC`) to ov6 through three independent lines
of evidence, including a runtime cross-check against seven measured `root+0x000`
values across seven poked rule modes. Details and the ov8 decode (used only as a
falsification check, not cited for any claim) are in `../feel-captures/match-presets-2026-09-12/RESULTS.md` §4c.

## What a live run must add

This ticket is static-only and cannot itself confirm the tie behavior dynamically. The
expiry transition and match-end callback are now traced statically (above), so the
live run no longer needs to establish that a transition exists — it only needs to
resolve the **outcome**: what `0x0215911C`'s second argument (`1` then `0`, called
per player) and the `+0x4C`-based "first unbeaten player" pick actually do when HP is
equal at expiry. A follow-up runtime session should run **one timed match with HP
poked equal on both sides at the moment the on-screen `TIME` display reaches its last
unit**, and observe what the result screen actually shows: a draw, a sudden-death
continuation (extra time, extra round, or similar), or one side declared the winner by
some tiebreak rule — ideally while watching `0x0215911C`'s arguments and
`0x02171AA0`'s written value. That single observation would resolve all three
`[unverified]` tags in this finding's "Task 2" section, and should also record whether
`[root+0x10]` (or whatever RAM word turns out to back it — the runtime backing address
for the on-screen counter is itself still not identified per `match-timer-units.md`)
is readable at all from outside the battle-root chain, so a future static-plus-runtime
pass can watch it directly instead of inferring it from the tick-handler disassembly.

## Falsification

This finding is wrong if: (a) `[root+0x10]` is not actually reachable from the same
`root` object `p166` and `docs/confirmed-facts/physics.md` §5 already name, i.e. this
is a different per-mode-handler-local counter that happens to share a small offset by
coincidence; (b) some other rule mode's tick handler does not route through
`0x0214F998` at all — **checked in this pass**: nine `bl 0x0214F998` call sites were
found mapping to modes 0-7 and 21; modes 8-20 were not observed calling it, so if a
live run finds one of those modes' timers decrementing a different word, this finding's
"shared match-timer decrement" framing would need to narrow to "modes 0-7 and 21
specifically," not all rule modes; or (c) a live run finds the actual win/draw/tiebreak
branch and it does not key off this counter's value or the traced match-end callback at
all (e.g. a separate "match ended" flag set by something upstream of the tick
handlers).

## Live (`jus-l77m`, 2026-09-12)

**At time-out no side is declared winner on remaining HP; the match continues in a
further timed round (timer reseeded to the full budget; owner term "sudden death")
and if that round also expires undecided the result screen marks both sides WINNER
at placement 1 with 0 points (a draw). Observed once, point mode, じかん 30, Goku
vs CPU Luffy; HP at the expiry frame unmeasured; round-start HP reset seen once at
50% and once at full. HP-based tiebreak unobserved, not ruled out.** Full session,
GDB logs, and screenshots:
`../feel-captures/match-timeout-2026-09-12/RESULTS.md`.

- `luffy_battle`, the state this ticket's live half was written against, does not exist
  as a committed or session-local asset — `jus_files/save_states/INDEX.md`'s own "Not
  kept" section says so. A fresh timed point-battle state (Goku `chr_b 0` vs. CPU Luffy
  `chr_b 12`, じかん 30) was built via the recipe in
  [`match-timer-units.md`](match-timer-units.md) instead and used for all three runs.
- The expiry signature is: `root+0x10` underflows -> the countdown function's `1`
  return reaches `0x0214DD36` (`r0=1`) -> `0x0214DDBC` (`MATCHEND_CB`) entry ->
  `0x0215911C` called for **both** players, fighter-table order, each `(player, 1)`
  then `(player, 0)` -- symmetric across players, not special-cased for a "loser."
  `0x0215911C(obj, r1)`'s `r1` is a **slot index** into `obj+0x7C + r1*0x18`
  ([Battle-Engine-Map.md](../Battle-Engine-Map.md)'s `slot` field; `p187`: `r1=0` clears flags there), so this
  pair is status-effect teardown across two slots, carrying no outcome information.
  Observed identically in the **two** fully clean captures (no `HPDELTA` hits and no
  solo `PLAYERCB` pair in the preceding ~40 frames) — RESULTS' Run A and Run C
  expiries; Run B's expiry followed 17 `HPDELTA` hits during its wait and is not one
  of the clean pair.
- **First clean expiry with (near-)equal HP and no pending KO: the timed round
  continues rather than ending.** `root+0x10` is reseeded to the full frame budget
  (`4463`, the same seed as a fresh match) with **no result screen** and no
  player-count change -- the match silently continues (owner term "sudden death").
  Confirmed both from the GDB/RAM trace and from the owner watching live ("and then
  the match went to sudden death").
- **HP at the expiry frame was never measured**: no HP watch was armed at
  `0x0214DD36`, and the `EXPIRYTEST` breakpoint prints only `r0`. Round-start HP
  after the reset was read as exactly 50% of each side's own max HP once (Run B),
  and as full max HP once (Run C's post-expiry peek, `10240`/`9728`) -- a
  contradiction within this session's own data, not a settled reset rule. Run B's
  own read-back mixes a pre-hit poked value with the post-reset value and is not a
  measurement of HP at expiry; state it as: HP at Run B's expiry not measured, P1
  inferred ~5632 immediately before the reset overwrote it, P2 unread.
- **A second, later clean expiry (the further timed round also expiring without a
  decisive result) produced a genuine draw**: the result screen marked **both** `1P`
  and `2P` as WINNER simultaneously, each at **placement 1, 0 points** (the circled
  "1" is a placement badge, not a point value -- `ko-outcome-example.png` shows
  placement badges 1 and 2 on a one-sided KO result, both also at 0 points), and the
  root object was fully torn down (unlike the sudden-death transition, where `root`
  persisted). This is the same "both sides WINNER" shape `p166` observed for the
  unrelated degenerate modes-18/20 case, now confirmed for a real fought match's
  timeout path specifically.
- `0x02171AA0` (the traced "first player whose `+0x4C` is zero" write) read
  `0xFFFFFFFF` at every clean expiry observed, including the final draw, because it
  was **never written**: the write site's loop at `0x0214DD6C`-`98` scans an array
  inside `root` (bound at `root+0x14`) for a zero entry and skips the store when none
  is found, so `-1` means "not written," not "index -1 selected." (A separate
  `+0x4C` spot-check mid-match peeked player structs directly, the wrong base for
  this field, and is not cited as evidence here.) The static finding's
  `+0x4C`/`0x02171AA0` chain remains real per the disassembly but was not seen
  driving the visible outcome. Whether it matters when one side has a genuine points
  lead at expiry (as opposed to this session's equal-points case) is untested and
  open. Conditions: mode word (`root+0x000`) and gimmick state were not RAM-read, so
  every claim in this section is scoped to point mode, じかん 30, Goku vs CPU Luffy.
- Against the ticket's three original options: (a) draw and (b) a further timed
  round **both happen**, in that order; (c) a fixed P1/P2 default winner was **not
  observed** in any clean capture -- every clean expiry treated both players
  identically.
