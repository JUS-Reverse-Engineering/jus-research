# Attacker hit element `+0x14` bit 26 (`0x04000000`) is the shatter-classification discriminator, tested causally in both directions

Tracker items: `jus-ce7u`, `jus-xcz0`, `jus-pb6n`.

Grade: **CONFIRMED**. Two in-memory patch tests, both against the candidate
named in
runtime-report-6
§4/§7, both succeeded on the first attempt with call-site confirmation
agreeing with every logged field. Full raw data, GDB logs and per-frame
tables: `../feel-captures/shatter-2026-09-12/RESULTS.md`.

## Claim

At collision classification, the attacker hit element's `+0x14` word decides
which of the two pair lists a hit's pairing lands in — the block list
(`0x02081B20`) or the shatter list (`0x02081D68`). Bit 26 (`0x04000000`) of
that word is that decision, independent of every other bit in the word. The
word has at least two readers: the attacker-flag gate at `0x02081768`
(`ldr r1,[r6,#0x14]; tst r1,#0x4000000`, inside the routine at `0x02080F14`,
already measured in runtime-report-6) and the pair-list sort itself.
`0x0207F480` (the collision driver entry) is where these tests wrote the
patched value each frame, before either reader ran — the patch point, not a
reader:

- **Clearing** bit 26 on a down Y's hit element (Kakashi, `+0x14 =
  0x14001001 -> 0x10001001`) before the frame's collision driver call turns
  the shatter into an ordinary block: the blocked-bit store (`0x02081CC8`)
  and the ov6 guard-gauge add (`0x0215EC64`) fire instead of the shatter-tag
  store (`0x02081DC8`); `M+0x40` carries `0x1000` instead of `0x10000` on the
  hit frame; the guard flag survives; the gauge rises by 16; HP is
  untouched. This negative was observed directly: all five breakpoints
  (`0x0207F480`, `0x02081D90`, `0x02081CC8`, `0x0215EC64`, `0x02081DC8`) were
  armed at once, and the shatter-side pair confirmed silent.
- **Setting** bit 26 on a plain B's hit element (Kakashi, `+0x14 =
  0x10000001 -> 0x14000001`) induces a shatter on a move that normally can't
  produce one: the pair now reaches the shatter-list breakpoint
  (`0x02081D90`) and the shatter-tag store fires; the guard flag drops; HP
  drops by B's own damage (8.0); the gauge is never touched. That the
  unpatched B never reaches `0x02081D90` is an inference from the block-list
  behavior, not a direct observation in this session: the unpatched locate
  pass (`ce7u_shatter_locateB.gdb`) armed only `0x02081CC4`, not `0x02081D90`.

Both tests patched *only* the one bit, conditioned on the move's own known
unpatched `+0x14` signature (so a slot-reuse frame is never touched by
accident), and left every other bit — including the already-ruled-out
`0x1000`/`0x10000` bits from runtime-report-6's falsification 1 — alone.

## Method note: pool-slot addresses are stable for a given state+plan

The attacker/defender hit-element addresses are heap-ish pool slots, but they
are **stable across melonDS launches for the same state and input plan**:
`register-2026-09-03/run6-gdb-obs3.log:5` has the byte-identical `BLKPAIR`
line (`r4=0221a89c r5=0221a8c8 ...`) that this session's own locate pass
(`gdb-locate-B.log`) reproduced, and `run6-gdb.log:74` has `r6=0221a8f4`
matching this session's down-Y locate pass (`gdb-locate-downY.log`) — nine
days and separate launches apart, both patch runs were separate launches
from their locate passes and matched at the same addresses. What changes the
slot rotation is a **different input plan**: runtime-report-6's own
`ip=0221a920` observation came from a different plan, not a different
launch. So the workable recipe is still: locate pass (read-only breakpoint,
same launch, same plan) immediately before the patched replay, rather than a
hardcoded address carried in from an old report written against a different
plan.

Also confirmed the hard way: **the stub's one-GDB-attach-per-launch limit is
real**, not a convention. A same-launch reattach attempt (after a clean
detach) hangs on `qSupported`/"Ignoring packet error" and never reaches a
breakpoint; a fresh melonDS launch is required for every new attach.

## Falsification

Both directions were run with a positive/negative pair of call-site
breakpoints (block-path stores vs. shatter-path stores) so the result is not
just "the field changed" but "the code took the other branch." Either
direction failing to move the call-site trace, while still moving the field
trace, would have meant a downstream effect rather than the discriminator
itself; that didn't happen — the two traces agree in both tests.

## Open (unchanged from runtime-report-6, out of this ticket's scope)

Which authored file byte becomes this live bit is still not located. The
live parameter block's `+8..+0xB = 01 00 00 00` marker (runtime-report-6 §5)
remains the best lead, but Kakashi's `down Y` box is a spawned element (its
own col record, not `na_b_05.bin`), and that record has not been read yet.
Left as a `TBD` in the combat notes §7.
