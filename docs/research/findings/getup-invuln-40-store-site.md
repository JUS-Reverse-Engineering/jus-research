# The get-up invincibility of 40 is stored at 0x0215BD00

Tracker item: `jus-getup-invuln-store-site-gm12`, a correction. Static read, with measured support
for two of three routes, 2026-11-13 intake. A second reader (an independent capstone
disassembly, outside the original tooling) agreed.

The get-up invincibility of 40 is stored by `moveq r0,#0x28; strheq r0,[r4,#0xCE]` at
0x0215BD00, in handler 0x0215BC8C, on the last state-8 tick of the get-up. The store is
taken when `bl 0x0215BC10` returns 0. Falldown (reaction 4), clean pop (5) and launcher (6)
all reach 0x0215BC8C and share this one store.

## The other immediate-0x28 store

The other immediate-0x28 store to obj+0xCE, at 0x0215CCCC, is not on this path. It sits in
0x0215CCB0, the exit callback of state 0x19 (state 25, the KO and ring-out respawn).

- The only reference to 0x0215CCB0 is the literal at 0x0215CBF8. 0x0215CABC loads it as r3
  for the call at 0x0215CACC, `bl 0x02157494` with r1 = 0x19.
- 0x02157494 forwards to 0x02159D34. That function calls the old obj+0x10 callback, then
  stores r1 to obj+0x19, r2 to obj+0x0C and r3 to obj+0x10, so r3 is the state's exit callback.
- State 0x19 is entered only from state 24's per-frame handler 0x0215CA44.
- 0x0215CCB0 clears M+0x3C bit 0x20000000, which state 24 sets.

So 0x0215CCCC grants the respawn's 40. Two register-sourced stores to obj+0xCE (0x02157C30
and 0x02157D68) are untraced.

## What it corrects

The physics reference and an earlier falldown runtime note had attributed the falldown's 40 to
0x0215CCCC before the handler chain was traced.

## Evidence by route

- Clean pop: static and measured. The timer reads 40 on tick 162, the last state-8 tick,
  then 39 down to 1 on ticks 163 to 201.
- Falldown: static and measured. A runtime frame table shows state 8,
  obj+0xFC = 0x0215BC8C, and 40 at frame 89.
- Launcher: static only.

The reaction handler chains are in [reaction-table-holds-start-handlers.md](reaction-table-holds-start-handlers.md).
