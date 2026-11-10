# Komamen form resource views

PF-31i, static ROM evidence, no emulation. The native battle panels exported in
`kit.character.battle_panels` select chr_b 70, 71 and 72, prefixes dt_b_01,
dt_b_02 and dt_b_03. Their `cite.refs` points to
`prmdatainit-is-the-collision-loader.md:54`, the native name table selection.
The table entries at ARM9 0x020926E0, E8 and F0 are eight bytes each, a prefix
pointer followed by resource base 0xA8100, 0xA8200 and 0xA8300. The tests read
all three entries from ROM, including their prefix strings.

GenerateID's native reader is ARM9 0x02016220, described and decoded by
`scripts/analysis/anim_events.py:12`. The reader dispatches a full u32 ID at
the keyed frame. GN method 0x0206CA8C saves this ID in fp at 0x0206CAA0.
At 0x0206CAC0 `mov r1, fp`, 0x0206CAC4 `mov r0, #0`, and 0x0206CAC8
`bl 0x02010ADC` pass the unchanged full ID to the resource lookup.
At 0x02010B08..20, lookup loads the namespace base at +8 and size at +12,
tests base <= ID < base+size, then invokes its loader callback at 0x02010B30.
The later 0x0206CB70 passes the same ID to animation loading at 0x0206CB88.
There is no runtime addition of a form delta at these sites. The form's ROM
already stores its full ID. Comparing IDs after subtracting their panel base
preserves their local resource index. Rule F requires this exact equality,
and restricts GenerateIDs to the conservative [base, base+0x80) acceptance bound.

The saved inventory has six differing GenerateIDs per alternate form, at
animations 1e, 20, 22, 27, 29 and 2a, all at `spawns[0].effect`. Every one is
checked against its actual base row. Deltas are 0x100 and 0x200 respectively.
The fifteen remaining differing fields per form are fourteen
`cancel_row.cites.member` strings and `ua_row.member`, exact prefix labels.

Two further differing rows per form are `anim_event.notes[3].events[0].raw`
in animations 24 and 25. They are NOT effect operands. The decoder's final
16-byte raw window crosses an animation boundary. The op1 sub3 impulse is
four bytes `03 01 fb 00`; the following twelve bytes start the next
animation header. `move_records.Almt` describes its u32 animation ID; the
namespace relation is proved here. The test walks all three ALMTs' offsets and
checks event_offset+4 == next_animation_start, then reads the u32 there.
For animation 24 it is base+0x25, and for 25 it is base+0x26. Only that word
is translated; the impulse bytes and remaining eight header bytes must
match exactly. The resource byte therefore changes 81 -> 82 or 83.

The complete decoded-row census is 23 per form, 46 total. The older memo's
27 per form included UA raw-window copies removed by the landed PF-31g
re-key. Current UA views use actual event coordinates. No differing decoded
row is exempted. Tests enumerate all 46 and inject a separate tamper in each.

This census covers decoded D3 rows, not every archive byte. Each alternate
main .amt has 94 differing bytes: 44 animation-header namespace bytes,
44 TextureID namespace bytes, and six GenerateID namespace bytes. Two
header words also occur in decoded raw windows, leaving 86 bytes outside
decoded rows. The remaining archive differences are panel namespace and art
data outside D3, including .dtx namespace words and .dig palette bytes.
`test_komamen_resource_namespaces` walks all 44 main headers and 44 TextureID
words and all 11 effect _e0.amt headers and 11 TextureID words for each form.
Every word must equal its panel base plus the base form's local index.
The test separately tampers each of these 220 alternate-form words by one.
This pins the namespace evidence without asserting byte parity of art data.

## Namespace bound

`RESOURCE_BOUND = 0x80` is a conservative acceptance bound, not a decoded
runtime namespace extent. The native lookup's actual extent is the size word
at descriptor +0xC, loaded at ARM9 0x02010B14 and used at 0x02010B18..20.
Its descriptor array is runtime state; this job has not located a static size
table. The ROM instruction bytes are pinned by the handler test. All actual
main/effect header and TextureID words, plus all differing GenerateIDs, lie
within the conservative bound. A larger local index stays open for further
proof rather than being assumed to belong to this panel's archive.

Rule F replaces existing intra-form view edges, so an altered form frame
cannot close indirectly through an unchanged form event frame. It adds
edges to all matching base rows, refusing conflicting duplicate values.
Closure propagates after the ordinary kit, native-law and allow rules.
A base row that remains open leaves all its form views open.

Base Komamen has one open requirement, `cancel_row.followups`, record 12.
The decoded key frame 14 and cancel_start 16 are independent of inherited C4.
`cancel_table.keys_of` selects op3/sub0/arg1 key frames from NoteTrack;
`_move_row` at lines 373-389 computes cancel_start = min(key) + START_OFFSET.
Rule F depends on base static-window views of the complete carried NoteTrack.
The derived row-12 anim must equal every decoded native `cancel.anim` value
for record 12, which is 0x28 from ov6 table address 0x02171348. Both native
and derived animation rows are dependencies; this rule does not trust the
derived anim's value-blind legacy view. Missing or changed
source fields reopen the static views. These are decoder quantities; 16 is
the decoder's inferred window-start value, not proved elapsed game time or
an assertion that the DREAM can execute a normal cancel. `special_cancel`
at lines 301-308 excludes ids 11-14 only from that separate special-cancel
classification. It does not invalidate the raw NoteTrack key or resolve C4.

The remaining question is the id-12 reader path, not unknown mask arithmetic.
Native row 12 has mask 0xFFFFFFFF and misc 0x140B0B, with state byte 0x0B.
Both the start OR at ov6 0x02159E1C and chain-fire OR at 0x0215A578 make C4
all-ones, so [] is the decoder's mask projection. It is not established as
the DREAM window's actual followup list. Id 12 is the latch-skip ID at
0x0215A4B4; the conditional C4 load at 0x0215A4BC and state-9 fire test at
0x0215A55C do not by themselves establish the state-0x0B DREAM dispatch.
The DREAM cancel path has no kit representation. The base `followups` row
and its two form views require proof of the id-12 dispatch/window reader and
state transitions with a kit representation, or captures tracing that path
from neutral and each reachable chain entry. Retain reader PCs, input edges,
attack anchor, animation ID/frame, state, C0/C4 and ground/air cancel flags.
These three rows remain requirements; no waiver or stand-in was introduced.

PF-31o closed them. The id-12 fire path (0x0215A590-0x0215A618) neither reads
nor writes C4, and a neutral start makes C4 all ones. So [] is the neutral
window's list, and a cancel entry inherits the cancelled window's offers. The
kit says so with `cancel.inherit` (`dream-cancel-c4-inheritance.md`). The base
`followups` row closes as a view of that law, and the forms follow Rule F.

## Ref2 window guard witnesses

Swapping the base derived anim to 0x1e, which also has key 14, reopens the
exact base/form key and start rows. Missing, changed or mistyped native anim
sources cannot establish the view. The saved native identity is also checked
against `cancel_table.table_row(12)` in the ROM-backed test; closure itself
reads the inventory and needs no live ROM access.

Synthetic fixtures cover conflicting duplicate animations, keys at the last
frame, and multiple keys whose start must use the earliest key. Exact-prefix
assertions detect a base value closed incorrectly while form rows stay open.
New dependencies are merged with existing edges and deduplicated, so a future
source obligation cannot be silently overwritten. Namespace tests use
`form_views.RESOURCE_BOUND`; they do not independently hardcode its value.

## Guard witnesses

Synthetic fixtures cover missing base keys, wrong native chr_b identity,
incorrect raw header identity, incorrect impulse bytes, GenerateIDs outside
the conservative bound, non-GN numeric fields and translated form frames.
Reviewer mutants M05/M09/M10/M13/M19/M20 are tested on these fixtures.
M07/M08 remain equivalent on the current inventory: raw anim/member gates
are implied by record matching and those two raw-field locations. M15 is
also equivalent on current data: BASE ownership already restricts this lane.
