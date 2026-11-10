# Finding: Ichigo's six Y-attack variants share the ObjShot kind and record layout, but each authors its own collision entry

Runtime. Tracker item `jus-puc7`.

## 1. The question

Owner, 2026-09-11, verbatim:

> "AirY and upY both fire the same projectile as fwd Y, at different angles.
> Do they use the same pointers / bytes / whatever in the backend too?"

And, mid-session, also verbatim:

> "I tried to make sure I paused at the very beginning of the animation for
> each of those saves. the projectile is not spawned yet on any of them."

## 2. Result

Six savestates -- `pc-ichigo-fy-vegeta`, `pc-ichigo-charged-fy-vegeta`,
`pc-ichigo-upy-uncharged`, `pc-ichigo-upy-charged`, `pc-ichigo-airy-uncharged`,
`pc-ichigo-airy-charged` -- each spawned a P1 ObjShot element with kind byte
`+0x1A = 0x00`. Every structure in the chain (ObjShot element, position
element, entity, ColPrm record) is byte-identical across all six once RAM
pointer words (`0x02000000..0x023FFFFF`) and the declared exclusions are
masked out -- **except** the first node on the record's `+0x08` list and the
20-byte collision entry it resolves to. Each of the six resolved to its own
entry, at consecutive ids 264-269.

### Per-state table

| state | record idx | id | entry `+0x08` | node `+0x18` | per-frame dx,dy | frames stepped to spawn |
|---|---:|---:|---|---|---|---|
| `pc-ichigo-fy-vegeta` | 115 | 264 | `0x20` | 1 | -962, 0 | in flight at save (phase 0) |
| `pc-ichigo-charged-fy-vegeta` | 114 | 265 | `0x00` | 0 | -1050, 0 | 18 |
| `pc-ichigo-upy-uncharged` | 23 | 266 | `0x20` | 1 | 677, -753 | 26 |
| `pc-ichigo-upy-charged` | 24 | 267 | `0x00` | 0 | 738, -822 | 31 |
| `pc-ichigo-airy-uncharged` | 26 | 268 | `0x20` | 1 | 680, 749 | 30 |
| `pc-ichigo-airy-charged` | 27 | 269 | `0x00` | 0 | 742, 817 | 26 |

"Frames stepped to spawn" counts plan frames from the unpause `START` press
and so includes roughly 16 frames of pause-menu closing; see
`CONDITIONS.md`, "Frames stepped per state," for the per-state breakdown.
`pc-ichigo-fy-vegeta` is an older state saved with the shot already mid-flight,
so phase 0 (a scan of the state as loaded) caught it directly.

dx sign follows the save's facing direction, not the move: the six saves do
not all have Ichigo facing the same way, so magnitudes are comparable across
rows but signs are not (`CONDITIONS.md`, "Velocity samples").

### Entry bytes, checked against ROM

The 20-byte collision entry at ids 264-269 is byte-identical between live RAM
(read at the pause point in each of the six states) and
`jus_files/chrbin/chr/col/bl_b_01.bin` indices 8-13 (`entries[i] = bytes[i*20 : i*20+20]`),
confirmed directly against the ROM file for this finding:

| id | entry bytes (live RAM == ROM index `id - 256`) |
|---|---|
| 264 | `020200000f000000200000000f040a1501000000` |
| 265 | `0205000012000000000000000f050a1501000000` |
| 266 | `020100000f000000200000000508081501000000` |
| 267 | `0205000012000000000000000c0c081501000000` |
| 268 | `020200000f0000002000000005fa0a1501000000` |
| 269 | `0205000012000000000000000cf60a1501000000` |

Differing entry offsets, listed with values only -- what these bits or bytes
mean is **not claimed** here:

| offset | `264` | `265` | `266` | `267` | `268` | `269` |
|---|---|---|---|---|---|---|
| `+0x01` | `0x02` | `0x05` | `0x01` | `0x05` | `0x02` | `0x05` |
| `+0x04` | `0x0F` | `0x12` | `0x0F` | `0x12` | `0x0F` | `0x12` |
| `+0x08` | `0x20` | `0x00` | `0x20` | `0x00` | `0x20` | `0x00` |
| `+0x0C..+0x0E` | `0F040A` | `0F050A` | `050808` | `0C0C08` | `05FA0A` | `0CF60A` |

## 3. Identical vs. different, structure by structure

Byte-identical across all six (masking RAM pointer words `0x02000000..0x023FFFFF`
and the declared exclusions: entity first `0x100` bytes, ColPrm record `0x188`
bytes):

- **Entity** (first `0x100` bytes): identical.
- **ColPrm record** (`0x188` bytes): identical.
- **ObjShot element**: identical except `+0x20` (`0x4C` uncharged / `0xB0`
  charged), `+0x34..+0x36`, `+0x38/+0x39`, `+0x3C..+0x3F`. `+0x28` and `+0x30`
  are pointer words that target the same two addresses (`0x0220F30C`,
  `0x02206838`) on all six.
- **Position element** (the 0x40-stride element at `[record+0x5C]`):
  identical except position/lifetime bytes; its s16 pair at `+0x24/+0x26`
  equals the measured per-frame dx/dy on all six (see below).
- **First node on the record's `+0x08` list**: differs at `+0x18` (1
  uncharged / 0 charged) and `+0x26` (`== id - 0x100` on every state).
- **Collision entry**: six distinct 20-byte entries, one per state, at
  consecutive ids 264-269. See tables above.

## 4. Velocity vectors and the position-element match

Per-frame dx/dy (two consecutive-framecount samples, identical on both
samples for every state):

| state | dx | dy |
|---|---:|---:|
| `pc-ichigo-fy-vegeta` | -962 | 0 |
| `pc-ichigo-charged-fy-vegeta` | -1050 | 0 |
| `pc-ichigo-upy-uncharged` | 677 | -753 |
| `pc-ichigo-upy-charged` | 738 | -822 |
| `pc-ichigo-airy-uncharged` | 680 | 749 |
| `pc-ichigo-airy-charged` | 742 | 817 |

The position element's s16 pair at `+0x24/+0x26` equals these measured dx/dy
values exactly on all six states (`DIFF.md`, "(d) Two derived relations,
checked against the captures").

A naming note, not a new claim: the 0x6C ObjShot element also has fields at
`+0x0C`/`+0x10`, but those are RAM pointers, not position -- the x/y pair
lives on the separate 0x40-stride element at `[record+0x5C]` that
`docs/research/findings/element-0x0C-is-the-owners-world-position.md` and
`projectile_census.py` already read as `x_raw`/`y_raw` (`CONDITIONS.md`,
"Reading `+0x18`, and a correction to the assumed layout").

## 5. Plain-language answer

Yes and no. AirY, upY, and fwd Y (charged and uncharged) all fire the same
kind of shot object (ObjShot kind `0x00`), built from the same record and
entity layout, with byte-identical fields once RAM addresses are masked out.
But each of the six spawns links to its **own** authored 20-byte collision
entry -- six consecutive ids, 264 through 269, one per state -- so the
angle and charge state are not just different velocity numbers layered on
one shared entry; they are six distinct authored entries. The charged
variants are exactly the ones whose entry `+0x08 = 0` and whose first node's
`+0x18 = 0`; the uncharged variants have entry `+0x08 = 0x20` and node
`+0x18 = 1`.

## 6. What is NOT claimed

- What `+0x01`, `+0x04`, or `+0x0C..+0x0E` on the collision entry mean.
  They differ between the six entries; values are listed above, nothing
  more.
- Any gameplay label for these bits -- no "priority," "cancel," "eat," or
  "hit-priority" terms are used. "Damage" is reserved for the documented
  DamageFlags field, which is not one of the fields discussed here.
- Why `+0x0C..+0x0E` on entries 266/267 (up Y) differ in pattern from the
  fwd Y and air Y pairs -- only that they differ, and by how much.
- Anything about the ObjShot element's `+0x34..+0x3F` region beyond "it
  differs and is not analyzed here."

## 7. Links

- Capture directory: `docs/research/feel-captures/ichigo-y-variants-2026-09-11/`
- `docs/research/feel-captures/ichigo-y-variants-2026-09-11/DIFF.md`
- `docs/research/feel-captures/ichigo-y-variants-2026-09-11/CONDITIONS.md`
- `docs/research/findings/element-0x0C-is-the-owners-world-position.md`
- `docs/research/findings/projectile-census-node-bit0-predicts-freed-at-contact.md`
- Tracker item: `jus-puc7`
