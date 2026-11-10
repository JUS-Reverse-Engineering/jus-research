# Finding: hotkey self-re-press drives state `0x0b` ("dream attack"); chaining is timing-sensitive and has a one-bar cost on the closer

Tracker item `jus-jh7d` (child `jus-atns`). Grade: **CONFIRMED** for the core
mechanism (state `0x0b`, the chain existing, the one-bar cost on the final
press); **PLAUSIBLE** for the chain's minimum timing (bracketed, not
bisected) and for whether the chained switch's active-bit transfer is
simply an ordinary busy-deferral rather than a distinct fast path (a prior
"bypasses the busy gate" reading is **withdrawn** — refuted against the
logs, see Input rule item 2); **UNCONFIRMED** for the move-record identity
and any P2-side damage (no hit landed this session). Evidence:
dream-attack-2026-09-12/RESULTS.md.

## Input rule (as measured)

On a deck with L/R sticker hotkeys assigned (`jus-e2w4`; only
`pc-taikoubou-npc-jotaro-dark-tournament`'s deck has them: L→Yusuke slot 2,
R→Momotaro slot 1, leader Taikoubou slot 0 has none):

1. **Switching to a hotkeyed member, then pressing that same hotkey again
   while that member is already active** starts a move in place instead of
   switching: slot action byte `0x01`→`0x13` and pending state
   `obj+0x19`→`0x0b` at press+3, committed at `obj+0x18` on press+4 — no
   active-flag or `obj+0x1CC` change happens on this press. This is the
   owner's "dream attack" ([OWNER-NOTES.md](../moveset-notes/OWNER-NOTES.md)
   2026-09-12), and is the same code deck-editor.md §6.5 and
   runtime-report-4-lr-switch-taikoubou.md already observed and left
   unnamed ("pressing the hotkey of the character already active instead
   drives that koma's own state `0x0b` move"). The move runs 47 frames of
   committed state `0x0b` (frames 85–131 in the measured run); 51 frames is
   the press-to-idle total, since idle only lands the frame after `0x0b`
   clears.
2. **Pressing the *other* hotkey while state `0x0b` is still running**
   switches the active koma. The `obj+0x1CC` active-slot-index field flips
   at press+3 — one frame *faster* than an ordinary switch's own press+4
   `+0x1CC` flip. **This does not bypass the busy-switch gate.** In
   ordinary switches (Plans A, D) the active-bit and `+0x1CC` flip within
   one frame of each other (flag at press+3, index at press+4). In all
   four chained switches measured this session, that order inverts:
   `+0x1CC` flips at press+3, while the deck record's active-bit transfer
   lands at press+4 — one frame slower than an ordinary switch's own
   press+3 active-flag transfer — in three of four chained switches. In
   the fourth, the *shorter* L offset (`C_chain_p10`, L pressed at frame
   91 = trigger+10), the transfer instead landed at frame 106 — press+15
   — squarely inside the documented 5–66-frame busy-deferral range
   (`jus-b3k2`, the combat notes §12), not outside it. During state `0x0b` the
   outgoing slot's action byte reads `0x13`, a value the busy-deferral rule (§6.5: `0x01` idle →
   3-frame flip, `0x03` busy → deferred) does not name, so **whether `0x13`
   defers is unresolved** — both `C_chain_p10` and `C_chain_p30` are
   equally consistent with the active-bit transfer landing at
   `max(press+3, the outgoing move's own next state-boundary frame)`, a
   hypothesis for the next session to test rather than a settled rule. The
   incoming koma is idle for exactly one frame after becoming active
   (press+4-equivalent), then busy the next — the ordinary
   live-in-3/controllable-in-4 pipeline already in runtime-report-4, not an
   immediate busy transition with no idle frame.
3. **Pressing the first hotkey again** (switching back) commits at the same
   fast (press+3) latency and **spends exactly one SP bar** on that press
   (`slot+0x5CC/+0x5CD`: current-bar byte drops by 1, max unchanged) —
   matching the known "a special spends one bar" rule (guard-sp.md §1.4).
   This is the owner's "switches back... and fires a special." The debit
   lands on the switch-commit frame, one frame before the incoming slot
   becomes active, so "switch-back costs a bar" and "incoming special
   costs a bar" are not separable by timing alone in this data. No bar was
   spent on either of the two dream attacks in the chain — only on this
   closing press.
4. **The chain is timing-sensitive on the *second* hotkey's press.** Pressed
   1 frame after the triggering re-press (before that re-press's own
   3-frame commit resolves), the second hotkey did *not* do nothing —
   `C_chain_imm`'s slot1 (Momotaro) action byte moved from `0x13` to `0x03`
   (the attacking action code) at frame 115 (the plan's later, queued R
   press at 112, +3), held to frame 130, then read `0x01` at 131 — versus
   `0x11` at 131 in the unchained `B_dream` baseline. No SP bar was spent
   and the active-slot index never left Momotaro's slot, so the chain
   still did not fire, but the run is not "indistinguishable from a lone
   dream attack" as first written. This partial effect is at least as well
   explained by the already-confirmed single-request switch queue
   (`jus-b3k2`, "only one request queues, last press wins") as by any
   dedicated timing gate — and it sits oddly against "last press wins": the
   L press at frame 82 came after the triggering R press at 81 yet L lost
   entirely (no switch, no chain), while the *later* R press at 112
   registered a partial effect. Pressed 10 or 30 frames after (7 or 27
   frames after the commit), the chain fired both times, with identical
   fast-latency `+0x1CC` switching. **The true minimum boundary is
   bracketed between "before commit" and "commit+7 frames," not
   bisected.**

## States

- State `0x0b` is entered on the self-re-press and persists, unchanged, as
  the *coarse* fighter-object state code (`obj+0x18/+0x19`) through **the
  entire chain** — both dream attacks and the closing special all read
  `0x0b`. The brief's hypothesis that the chain would show distinct codes
  (`0x0b` vs `9` "attack" vs `10` "special" per the engine notes §3's enum) is
  **not supported** by this measurement: the coarse state byte does not
  distinguish which sub-move is running once you are inside this input
  path. Only the deck-record action byte (idle `0x01` → busy `0x13` →
  transitional `0x33` → idle again) and (unconfirmed this session) the
  moveData pointer would disambiguate which specific move is active.
- Total chain duration (press of the first re-press to fully idle): 51
  frames for a lone dream attack (Plan B), 112 frames for the 10-frame-offset
  chain, 132 frames for the 30-frame-offset chain — i.e. roughly the sum of
  each sub-move's own busy span plus the gap the player inserted between
  presses; not independently decomposed into per-sub-move durations this
  session.

## Costs

- Dream attack (both the triggering one and the chained one on the other
  character): **no SP bar spent**, and no visible extra SP-pool deposit
  beyond whatever the active character's own passive ability is already
  doing (e.g. Momotaro's ability-56 -3/frame tick, unrelated and
  pre-existing).
- The chain-closing switch-back move ("fires a special" per testimony):
  **spends exactly one SP bar**, same cost as an ordinary special
  (guard-sp.md §1.4). This is the only SP-bar cost observed anywhere in
  this session. The debit lands on the switch-commit frame, one frame
  before the incoming slot goes active — so this timing alone cannot
  separate "the switch-back itself costs a bar" from "the incoming
  special costs a bar."

## What did not reproduce / was not confirmed

- **No hit ever landed on P2** in any of the six runs (HP flat at 10240 raw
  throughout). The moveData-pointer probe (`0x020817EC`, reused from
  `scripts/gdb/lxyt_kbrecord.gdb`) never fired because it only executes on
  a connecting hit; the arm9 hit-processor entry (`0x02080F14`) fired every
  frame regardless of any hit and gave no discriminating signal. **The
  dream attack's move record, whether it creates a hitbox at all, and any
  damage to P2 are all unconfirmed** — this is a gap against the original
  ask, not a settled "no damage" finding. Distance to P2 was not
  independently verified as closed before the dream-attack presses.
- `obj+0x55` (documented sticky "last-switch hotkey" byte) read `0` on
  every sample of every run, including after confirmed switches — either a
  wrong address for this session or a probe defect; not used to contradict
  the existing, independently-confirmed claim about that field
  (runtime-report-4).
- Whether the owner's "dream attack" is the same input as the Genroh
  guide's "Dream Combo" ([battle-system.md](../guides/systems/battle-system.md) ~151-160: tap current koma,
  then others, then the first again) was not tested — the guide's flow
  (tap 1st, 2nd, 3rd, then 1st again) does not obviously match the
  two-hotkey re-press pattern measured here, and this deck only has two
  hotkeyed slots to test with (no 3-member hotkeyed deck was available).
- The `c=7`→`c=6` bar drop the moment Momotaro first became active (before
  any special or dream attack) is **not an artifact** — it is a bar-borrow.
  `sp_pool` jumps `0`→`25594` the same frame the packed bars go
  `0x0707`→`0x0607` (Plan A, frames 3→4): `c -= 1, x += 0x6400`, minus two
  frames of the already-documented `-3`/frame Momotaro ability-56 tick —
  SP is conserved across the conversion (guard-sp.md §1.4 corroborated).
  The chain's closing press (`0x0607`→`0x0507`) has **no** matching
  `sp_pool` gain, so the one-bar spend on that press stands as a real cost,
  not a rebalancing of the same borrowed bar. Not folded into the
  "specials spend one bar" claim, which rests independently on the
  bar-drop lining up with the closing press in three separate runs
  (Plan C ×3).

## Next run

A hit-landing rerun on this deck must:

1. Verify facing and both fighters' x-positions independently before any
   dream-attack press, rather than assuming the 50-frame `RIGHT` hold
   closed distance.
2. Prove the `p2_hp` watch itself moves, with a plain control jab landing
   on P2 first — this session never confirmed the watch is live against a
   real hit.
3. Log the fighter object's active bit (`obj+0x25` bit 0, or the
   equivalent live field) and `obj+0x1CC` as two separate watch columns
   instead of inferring one from the other, so the transfer-lag measured
   here (§ above) can be read directly per frame.
4. Sweep the L offset at `+4`, `+6`, `+8`, and `+20..+26` past the
   triggering press, to narrow the bracketed chain minimum between "before
   commit" and "commit+7 frames" and to test the
   `max(press+3, outgoing-move state-boundary)` hypothesis.
5. Sample both slots' action bytes (`+0x24` low byte) every frame through
   the whole chain, not just the active slot, to catch transitional values
   like `0x33`/`0x03` that this session found only by chance.
