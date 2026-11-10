# Momotaro and Yusuke projectile-conflict trace

Tracker items: `jus-projectile-conflict-capture-prep-hnap`, `jus-964r`,
`jus-hitbox-priority-clash-1evz`.

## Result

In the deterministic state
`pc-momotaro-npc-yusuke-projectiles-about-to-collide`, Yusuke's forward+Y
projectile disappears without using the monitored damage accumulator or fold.
Its ColPrm record flags change from `0x8` to `0x9` to `0x209`, then its
element slot clears. Momotaro's projectile becomes live three frames later and
survives until it reaches the opponent.

This rules out the known `record+0xA4` to `record+0x134` damage path for this
replay. It does not prove that the `0x200` flag is a priority flag, exclude an
unknown attrition path, or identify the gameplay meaning of the nested field
that causes the flag change.

The nested bit is now traced one layer further, structurally: `record+0x38`
bit 0 seeds `node+0x18` bit 0 at pool allocation; that bit gates a store that
sets participant object `+0x18` bit 2 at `0x02080C18`; that object bit is what
the flag writer at `0x0207FB0C` reads to set `record+0x40` bit `0x200`. See
"Nested bit traced" below. This still does not name what bit `0x200` means.

## Conditions and positive control

- Emulator: patched melonDS 1.1, JIT off, launched through
  `scripts/emu/launch_emu.sh`.
- State-local Yusuke element and record: `0x0220CF28` and `0x02214D64`.
- State-local Momotaro element and record: `0x0220CF68` and `0x02214EEC`.
- Input: START on relative frames 0 through 2, no input through frame 64,
  START on frames 65 through 67.
- Instrument: corrected 440-byte `watch_spec.json`, sampled every emulator
  frame for 90 frames with zero gaps and zero dropped samples.
- Positive control: Yusuke's x position moved from 699.22 to 692.38 pixels;
  his flags changed; Momotaro's element spawned at x 681.64 and advanced to
  x 770.51 before clearing.
- State-load acknowledgement was `ok:false` because the archived sidecar has
  a dummy frame count. The live root pointer read `0x02228E80`, and the element
  positions reproduced the saved setup.

## Per-frame evidence

The decisive frames in the corrected run were:

| Emulator frame | Yusuke x | Yusuke flags | Momotaro x | Momotaro flags |
|---:|---:|---:|---:|---:|
| 12314 | 695.80 | `0x8` | inactive | `0x200` |
| 12315 | 692.38 | `0x209` | inactive | `0x200` |
| 12316 | cleared | `0x200` | inactive | `0x200` |
| 12319 | cleared | `0x200` | 681.64 | `0x8` |

Both `+0xA4` accumulator windows stayed all-zero. Both `+0x134` fold fields
stayed zero. Neither record gained bit `0x800`. Momotaro's `+0x174` changed
from zero to `0x100`; this trace does not assign that field a meaning.

## Teardown path

A simultaneous GDB census broke on `0x0216C958`, `0x0216E1C0`, and
`0x0216F398`. Only `0x0216F398` ran for these two projectiles. At each
endpoint, the generic dispatcher call at `0x0216B260` selected teardown wrapper
`0x0216F99C` and returned to `0x0216B264`. The wrapper called the common
destructor `0x02083648` at `0x0216F9C8`; `0x0216F9CC` is its return address.

This identifies the observed callback family and teardown route for these two
projectiles. It does not establish that every projectile kind uses that family.

## Flag writer

A `JUS_WATCH` run on `0x02214DA4..0x02214DA7` located the two relevant stores.
The hook reports ARM PC as instruction address plus 8:

| Transition | Reported PC | Store |
|---|---:|---:|
| `0x8` to `0x9` | `0x0207FADC` | `0x0207FAD4` |
| `0x9` to `0x209` | `0x0207FB14` | `0x0207FB0C` |

The first store ORs bit `0x1` when
`*(*(record+0x60)+0x10)` is nonzero. The second walks the null-terminated list
at `record+0x08` and ORs bit `0x200` when any node's `node+0x08` object has
bit `0x2` at object byte `+0x18`. After the list walk, the routine invokes the
callback at `record+0x50` when record bit `0x1` is set. The shown block does
not test record bit `0x200` before that call.

An independent `codex exec -m gpt-5.6-sol` reading agreed with the store
addresses, conditions, list traversal, and limits above. It specifically
rejected semantic names such as priority, damage, or hit-confirmed for the
nested bit without tracing its writers and readers.

## Nested bit traced (jus-hitbox-priority-clash-1evz.1)

The node list at `record+0x08` held one `0x2C`-byte node per record: Yusuke
`0x0221b3c8`, Momotaro `0x0221b4a4`
(`docs/research/feel-captures/projectile-conflict-2026-09-10/nodes/RESULTS.md`,
Table (b)). `node+0x08` pointed, for both, at address `0x023a5bf8`, whose
payload words differed per record and whose `+0x1C` equalled the pointing
node's address (same file, Table (c)). The artifacts do not distinguish one
shared object from a recycled slot.

The `+0x18` bit `0x2` of that object was written once, by
`strb r0,[r1,#0x18]` at `0x02080C18` inside `0x020809C8`, the contact bucket
filler called from `0x0207FBD0`
(cite `docs/research/findings/contact-queue-insert-writer-found.md:38`). At
the hit `r1=0x023a5bf8`, `r4=0x0221b3c8` (Yusuke's node), `r5=0x0221b44c`
(`docs/research/feel-captures/projectile-conflict-2026-09-10/b18-writer/RESULTS.md`,
"GDB capture at the bit-0x2 write").

The store gate (quote of the disasm at `0x02080BE0`-`0x02080C1C`):

```
0x02080BE0  ldr r0, [r4, #0x18]
0x02080BE4  tst r0, #1
0x02080BE8  beq #0x2080c1c
0x02080BEC  ldr r0, [r5, #0x14]
0x02080BF0  tst r0, #0x300
0x02080BF4  beq #0x2080c0c
0x02080BF8  ldr r0, [r4, #0x10]
0x02080BFC  ldrb r0, [r0]
0x02080C00  cmp r0, #3
0x02080C04  cmpne r0, #4
0x02080C08  beq #0x2080c1c
0x02080C0C  ldr r1, [r6, #8]
0x02080C10  ldrb r0, [r1, #0x18]
0x02080C14  orr r0, r0, #2
0x02080C18  strb r0, [r1, #0x18]
```

executes iff `(nodeA+0x18 & 1) != 0` AND `((nodeB+0x14 & 0x300)==0 OR byte at
[*(nodeA+0x10)] not in {3,4})`; `nodeA = *(*(arg2+8)+0x1c)`,
`nodeB = *(*(arg2+0xc)+0x1c)` (confirmed from the function prologue at
`0x020809C8`-`0x020809DC`). An independent codex read agreed on the
pointer-then-byte reading of `+0x10`.

Node comparison from
`docs/research/feel-captures/projectile-conflict-2026-09-10/nodes/gdb.log`
dumps: Yusuke node `+0x14=0x10001002`, `+0x18=0x00000001`; Momotaro node
`+0x14=0x10001001`, `+0x18=0x00000000`
(`docs/research/feel-captures/projectile-conflict-2026-09-10/nodes/RESULTS.md`,
Table (d)). `+0x14` differs in value (`0x10001002` vs `0x10001001`) but both
give `(+0x14 & 0x300)==0`, so the only gate term whose outcome differs is
`+0x18` bit 0, which fails Momotaro at the first test. Node `+0x18` is
seeded from `record+0x38` at
allocation (`docs/research/findings/colprm-pool-allocator.md:43-46`;
`record+0x38` is the category bitmask per
`docs/confirmed-facts/collision.md:96`).

Record bit `0x200` set at `0x0207FB0C` is the same bit set at record
construction (`0x0207C7A4`) and teardown (`0x0207CE6C`) and cleared at
install (`0x0207CB2C`), per
`docs/research/findings/record-free-flag-and-the-linking-loop.md:14-38`. That
is the structural link; this document does not name what the bit means.

Unverified/open: the byte at `*(nodeA+0x10)` (`0x021c808c` /
`0x021ba8d8`) and node B `+0x14` were not dumped; the writer of `record+0x38`
for these two records is untraced. Follow-up tracker item: `jus-jv9d`.

## Correction (2026-09-10)

The "Nested bit traced" section above inferred that node `+0x18` bit 0 came from
`record+0x38`. A census of 22 in-use, non-fighter ColPrm records across 12 states
(`docs/research/feel-captures/projectile-census-2026-09-10/SUMMARY.md`) read
`record+0x38 == 0` on every one, including both the Yusuke and Momotaro records from this
capture — so that inference is wrong at read time. The node bit's actual writer is the
record allocator's (`0x0207D440`) built-in-table/character-array entry lookup: it resolves
a hitbox id to a 20-byte collision entry and OR's table `T18@0x0209FDC4[b]` into node
`+0x18` for each set bit `b` of the entry's own `+0x08` property word (bit 5 is the only
bit that contributes node `+0x18` bit 0 for authored per-character entries). See
`docs/research/findings/node-0x18-is-seeded-from-the-collision-entry-property-word.md`
(tracker item `jus-2s9k`).
