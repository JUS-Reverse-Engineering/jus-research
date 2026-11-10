# The Feb-2026 "physics region" is not the character struct

Tracker item: `jus-physics-region-identity-refuted-68d9`

Recorded 2026-08-26. Static cross-check by two independent workers plus
orchestrator follow-up, prompted by prep for the feel-vector capture campaign
(tracker item `jus-golden-damage-vectors-mj25`).

## The claim under test

[Character-State-Struct-2026-02.md](../archive/Character-State-Struct-2026-02.md) (2026-02-03 GDB
session, tracker item `jus-9lp.2.1`) mapped, on a struct reached via base pointers
`0x021E2A7C+`:

- `+0x6A–0xBA` — "physics/velocity region" (large deltas during knockback)
- `+0x78` — ground/air/hitstun byte flag (`0x00`/`0x22`/`0xC0`)
- `+0x98–0xBA` — countdown timers (run during hitstun/recovery)

The doc always carried a struct-identity caveat. That caveat is now the
finding.

## Evidence

**1. The offset cluster belongs to JPower.** An ARM-mode field-writer scan
(`scripts/decomp/find_field_writers.py`) found the cluster
`0x6C/0x74/0x78/0x7C/0x98/0xA0/0xA8/0xB0/0xB8` initialized together by a
constructor at ov5 `0x02162410`, which allocates **0x110 bytes** through the
tagged allocator `0x0201A21C`. The tag strings, resolved from the ov05 literal
pool (`[0x02163138]→0x02171360`, `[0x0216313C]→0x021711D8`), read
**`JPower.cpp` / `JPower_Add`**. The arm9 twin (`0x02053630`) is a lazy-init
singleton of the same family at static `0x020AAC44` (guard word `0x020AAB70`).
Note 0x110 ≈ the Feb doc's own "0x102+ bytes" size estimate — the Feb session
plausibly measured a JPower record.

**2. The combat entity has collision semantics there, not physics.** An
independent second pass (codex, neutral framing, not shown the Feb map),
anchored on the combat entity used by the collision/damage code (constructor
`0x0207C988`), read `+0x60..+0xC0` as collision bookkeeping throughout:
geometry/context pointers at `+0x60/64/68/6C/70/74`, a **32-bit flag word at
`+0x78`** (bits `0x10`, `0x10000`, `0x20000`, `0x40000`, `0x80000`,
`0x800000` — collision solver logic), computed boundary coordinates at
`+0x7C/+0x80`, a min-distance accumulator at `+0x84` (init `0x7fffffff`),
slot/result arrays `+0x90..+0xA0`, and an embedded 0xD0-byte state block at
`+0xA4` — which matches the `+0xA4` accumulator region already documented in
the [damage spec](../../confirmed-facts/damage.md), a good check that the
right struct was anchored. **No position or velocity fields** were found in
the range.

**3. The Feb `+0x78` byte-flag reading conflicts with both.** `0x00/0x22/0xC0`
byte semantics fit neither the JPower init nor the entity's 32-bit collision
flag word — a third struct, or a misread base.

## Verdict

- "Physics/velocity region `+0x6A–0xBA`" and "countdown timer region
  `+0x98–0xBA`" are **not** established character-struct facts. The offsets
  exist on JPower and collision-entity structs with unrelated semantics.
- **Character position, velocity, and hitstun-timer fields remain
  unlocated.**
- The Feb *behavioral* observations survive (something jiggles during
  knockback; weight lengthens recovery-time activity; see `jus-9lp.2.1`) —
  only the field-map interpretation is refuted.
- Convergence lead, untested: `jpower.bin` carries a per-move hitstun field
  (tracker item `jus-p5i`); if the Feb session watched a JPower record, its "timers"
  and jpower hitstun may be one mechanism.

## Caveats

- The field-writer scan is ARM-mode only (Thumb blind), and `stm` block
  copies were not scanned — absence-of-writers verdicts are weak.
- Codex's `+0xA8..+0xC0` verdicts are "no direct evidence," not proof of
  absence (several apparent hits resolved to manager objects or to
  `entity+0xA4`-relative addressing, i.e. parent offsets `+0x14C+`).
- One concrete false-positive on record for future scans: arm9 `0x020A6C14`
  matches the offsets but is a bit-decompressor writing to a stack buffer.

## Impact

- [Character-State-Struct-2026-02.md](../archive/Character-State-Struct-2026-02.md) — caution banner
  added to the struct map (this finding).
- Feel-vector campaign (`jus-golden-damage-vectors-mj25`) — Layer A capture
  cannot assume known velocity offsets; the first matches double as
  field-discovery (frame-diff a wide window; position identifies itself by
  integrating during plain walking, velocity by hit-frame discontinuities).
