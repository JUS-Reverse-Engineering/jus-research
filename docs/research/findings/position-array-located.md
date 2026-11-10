# Fighter world-position array located (runtime)

Tracker item: `jus-position-array-located-i1a5`

Recorded 2026-08-26. Session conditions: melonDS-lua, savestate
`ds8t_momo_battle_noheal` (MOMO deck, runtime chr_b roster 67,68,32), training
battle. Method: full-main-RAM snapshot diffs across scripted input bursts —
walk-RIGHT ×2, idle, walk-LEFT — so clocks (advance while idle) and position
(holds while idle, reverses on LEFT) separate cleanly. Positive control: a
scripted B press dipped opponent HP −800 raw, proving the input path live.

## The find

**Both fighters' world positions are (X, Y) pairs of s32 in 8.8-fixed pixels,
0x40 apart, each pair duplicated at +8.** This session: P1 at
`0x0220C1F4/0x0220C1F8`, opponent at `0x0220C234/0x0220C238`. The block is
**per-battle heap — re-locate every battle** (same drift class as the char
array, `find_battle_structs.py`).

Validation: P1 X tracked scripted walking live, per frame, with visible
accel/decel ramps (416.0 → 503.6 px), held during idle, reversed on LEFT.
Y stayed at ground (172031 = 672.0 px) throughout — no jump was ever
triggered (UP and X presses did not jump; jump identification is left to
owner-played captures).

Structure around the live pair:

- A **history ring of 8 stale copies** sits below it at 0x80 stride (9
  signature hits `0x0220BDF4..0x0220C1F4`; the live block is the highest).
- Negated **screen-space copies** near `0x0220FCC4/C8`.
- **16.16-scaled whole-px copies** near `0x020A5C68/98` (camera/sprite
  scale).
- **Sign-inverted X copies in ov11 BSS** (`0x02181BE8`, `0x02181CF0`) — the
  battle-AI overlay demonstrably consumes position, consistent with
  [physics-region-identity-refuted](physics-region-identity-refuted.md).
- Block-relative `+0x58` and `+0x74` (`0x0220C20C`, `0x0220C228`) changed
  only during motion — **velocity candidates, unresolved**.

## Correction to Cheat-Code-Analysis.md

Its position table (base `0x02181AF8`, +0x40/+0x44 per player, marked
untested there) **fails the functional test as literal coordinates**: those
words are pointers and never moved during a walk that demonstrably executed.
The 0x40-per-player *stride* matches the real pair array; the base was
stale or mode-specific.

## Tooling

`scripts/emu/capture_feel.py` re-locates the pair array by signature
(duplicated pair + shared ground Y + ring-top rule), identity-checks the char
records against the deck's expected roster (1–4 battle characters), and
tail-captures both fighters' position blocks + char records every frame.
Smoke-tested end to end: 370 frames at 60 fps, gzip + conditions sidecar.
Owner protocol: ../feel-captures/PROTOCOL.md.
Falsification for reuse: on any savestate, the armed X watch must track a
one-second walk and reverse on the opposite direction; a static read means a
ring slot or stale copy was armed.
