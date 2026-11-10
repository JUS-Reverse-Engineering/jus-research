# B11 residue transfer: one-session live trace

Tracker item `jus-m92n` records the raw measurement. The durable result is also in
[`B11-Residue-Transfer-Trace-Results.json`](../B11-Residue-Transfer-Trace-Results.json).

## Conditions

- One melonDS launch and one ARM9 GDB attach.
- Savestate `g3_verified`.
- Lua plan `scripts/emu/plans/g3_hp_delta_seek.json`.
- Four landed hits. The independent positive control at opponent current HP
  `0x021DF7F0` changed from `9728` to `9472` raw units, and the HP-apply
  breakpoint at `0x02078488` fired four times with `r1 = 0xFFFFFE80`.

## Trace

The same ordered sequence appeared four times:

1. The formula hit oracle at `0x02082584` fired.
2. At `0x020812DC`, the stage-1 store had `r3 = 0x180` (384 raw),
   `r0 = 0`, and `r8 = 0x0220FE68`. The destination was
   `0x0220FE68 = 0x0220FDC4 + 0xA4`, and its previous value was zero.
3. At `0x020821F8`, the pre-store value was `r0 = 0x180`, with
   `r5 - 0xA4 = 0x0220FDC4`. The store therefore targeted
   `0x0220FDC4 + 0x134 = 0x0220FEF8`. The first nonzero store saw
   `scratch+0xE8 = 0`.
4. At `0x0215AC08`, the pre-load base was `r1 = 0x0220FDC4`. Memory at
   `r1 + 0x134` was `0x180`, while memory at `r1 + 0xE8` was zero.
5. The consumer's call returned at `0x0215AC74`, proving the call at
   `0x0215AC70` reached the damage drain trampoline. At `0x02078488`, the
   delta was `0xFFFFFE80` (−384 raw) for the character at `0x021DF7D8`.

The stage-5 breakpoint sits before the `str`, and the consumer breakpoint sits
before the `ldr`. The value in `r0` at stage 5 and the memory read at the
consumer are therefore the useful observations. The supervisor timed out while
interrupting the slowed session, but that transport failure did not remove the
four ordered traces or the HP positive control from the raw log.

This closes the B11 producer-to-consumer transfer question. It does not claim
that `+0xE8` participates in damage; the trace supplies the opposite result.
