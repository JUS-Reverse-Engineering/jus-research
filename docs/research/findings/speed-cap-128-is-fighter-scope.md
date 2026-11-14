# The 128 px/frame speed cap is scoped to fighter elements

Tracker item: `jus-speed-cap-fighter-scope-uhs4`. Static read, with a savestate check, 2026-11-13
intake. Cross-check source: Keshire's export ([keshire.md](../external/keshire.md)), whose
"max speed 0x20" is the allocator default described below.

The 128 px/frame cap (element byte +0x3E) applies to fighter elements. Other elements get
the allocator default of 32 px/frame unless their creator overrides it.

## Static evidence

- The element allocator at 0x02082C34 stores 0x20 to +0x3C (x drag), 8 to +0x3D (y drag)
  and 0x20 to +0x3E (cap). The cap is 0x20 << 8 = 8192 raw, which is 32 px per frame.
- Battle_CharaCreate overwrites the fighter's element cap with 0x80 at overlay 6
  0x02156BE8 (`strb`).

All eight archived savestates read 128, 32 and 8 on the P1 element.

The two readings agree once scoped. Docs that stated the cap as 128 with no scope gain the
fighter-only qualifier: the physics reference and the knockback table.

## Open

Overlay 11 (battle AI, resident in battle) writes +0x3E at about 25 sites. Those writes were
not traced to their element, so the fighter default is the only cap source read.
