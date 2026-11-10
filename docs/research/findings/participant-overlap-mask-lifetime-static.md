# Participant overlap mask: correct object base and reset

Offline follow-up, 2026-10-01. This corrects the recycling
explanation in `pair-entry-creation-site-static.md`; its geometric pair-creation
finding remains valid. No emulator or new capture was used.

Static inputs at corpus `200f9ae`:

- `analysis/disasm/arm9.txt`, SHA-256
  `227af219f0f1b68102a85050c87d397066eec2a1ddd758d2678d824ee1546e91`.
- `analysis/disasm/ov6.txt`, SHA-256
  `f39c2999b9f8b180e5ef723b67b5ff028d17820996df0baa59b0cbcf3e0e6579`.

## Object identity and reset

`0x0207ACB8` allocates a 0x14-byte pair entry; the pool stride is visible at
`0x0207AE54`. It cannot own `+0x24`. At `0x0207FC10–1C`, the consumer loads
the pair's geometry elements from `+0x08/+0x0C`, then follows their `+0x1C`
participant pointers into r6/r7. The `0x0207FD28/3C` mask accesses use r6.

The actual participant is a 0x2C-byte ColPrm node. `0x0207D440` allocates it
from manager `+0x18`, links owner record `+0x08` at `0x0207D490/494`, stores
the owner at participant `+0x0C` at `0x0207D670`, and stores its geometry
element at `+0x08` at `0x0207D830`. Geometry element `+0x1C` receives that
participant at `0x0207B1A8`.

The release callback `0x0207D858` clears all 0x2C bytes at
`0x0207D91C–928`, then returns the node to its pool at `0x0207D938/93C`.
Owner teardown also clears all 0x2C bytes at `0x0207CDA4–B0`.
The per-frame clear at `0x0207F9C4–CC` changes `+0x20/+0x22`, leaving
`+0x24` intact. The short-lived pair pool's reuse therefore does not establish
a stale carry in this participant's mask.

## Protection rejection is a separate route

Overlay 6 `0x0215A9C4–D8` conditionally decrements fighter `+0xCE`.
`0x0215AA08–28` tests its updated value and calls `0x0215B4A8` with 1 or 0.
`0x0215B4A8–BC` sets or clears owner record `+0x40` bit `0x10000000`.

The ordinary body-versus-attack branch in helper `0x020809C8` rejects at
`0x02080AB4–C0` when the body's owner flags intersect `0x10000080`.
The literal is at `0x02080C24`; rejection precedes bucket-1 insertion at
`0x02080AF4/F8`. That helper does not write participant `+0x24`.

The mask writer `0x0207FD38/3C` is behind the equal collision-data tier
comparison at `0x0207FD08/0C`. Ordinary body/attack routing uses the
unequal-tier second sweep through `0x02080120–D0`. The mask's corrected
identity and reset do not justify marking ordinary B attacks spent when
protection rejects them.

## Remaining observation

For source B212 versus the adjacent B213 positive, trace frames 219–221:
geometry-element activation/count, participant identity, collision-data tier,
and the actual rejecting branch. The existing sampled timer and overlap rows
do not identify that branch.
