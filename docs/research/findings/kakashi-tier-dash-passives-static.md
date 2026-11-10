# Kakashi: jump tier, dash-speed record, `obj+0x128` passives, SFX/VFX — static only

2026-09-13. Tracker item `jus-atns.4.6`. Static disassembly and on-disk data only —
no emulator this pass (a separate Builder holds the live half). Scope:
Kakashi's jump-tier source, his dash-speed record, the mobility bits his
deck grants at `obj+0x128`, and any character-specific SFX/VFX ids
reachable without running the game. `[unverified]` marks anything inferred
rather than read directly off a primary source (ROM bytes or disassembly).

Conditions shared by every static read below: ROM files read directly —
`jus_files/arm9/arm9.bin`, `jus_files/analysis/disasm/ov6.txt`, overlay 6
via `scripts/analysis/rom_loader.py`, `jus_files/ripped_jus_files/bin/chr_b.bin`
(4440 bytes = 74 × 60-byte records), `jus_files/chrbin/chr/{col,shot,effect}/na_b_04.bin`.
Kakashi is `chr_b` **23**; his deck's helper koma are Kurama (**33**),
Mashirito (**57**), Muhyo (**59**) — indices from
[chr_b-Complete-Mapping.md](../chr_b-Complete-Mapping.md) rows 23/33/57/59,
confirmed against [characters/kakashi.md](../../confirmed-facts/characters/kakashi.md)'s
Conditions block. `docs/confirmed-facts/physics.md` §6.3/§6.4 and
`docs/confirmed-facts/helpers.md` §4/§5/§7 are cited throughout rather than
re-derived where they already answer the question; this doc adds a direct
byte-level read of `chr_b.bin` for Kakashi and his three helper koma, which
none of the cited docs had done by name.

## (a) `obj+0xBA` — jump tier

**Grade: CONFIRMED_STATIC.**

physics.md §6.4: on an `A` held ≥ 6 frames, the jump impulse written into
`element+0x2E` is `obj+0xBA = table[0x02171118][tier]`, tier 1/2/3 → raw
−1816/−1752/−1689. chr_b-Complete-Mapping.md's 2026-08-14 correction pins
the tier field: `chr_b` byte **`+0x01`**, copied to battle-struct `char+0x11`
by init function `0x02077C0C` (values 1/2/3 map to −1/0/+1 in that doc's own
framing, i.e. directly select the impulse table row).

Direct read of `chr_b.bin` record 23 (Kakashi), byte offset `+0x01`:
**`2`** — tier 2, obj+0xBA = **−1752** raw. This matches
physics.md's live citation ("Kakashi, Eve and Muhyo (all tier 2) reproduce
the same −1752 → −1656 step and 61-frame airborne duration exactly,
`jus-9utl`") — the static byte and the cited live measurement agree.

**Where the value comes from:** a character-file field (`chr_b` record
`+0x01`), not a deck field and not an engine-wide constant. The *table* of
three impulses is shared engine-wide; the *selector* into that table is
per-character.

**Tension with the maintainer ruling, stated plainly:** OWNER-NOTES
(2026-09-13) frames jump (and guard) as "uniform across characters." The
data says otherwise for jump: `chr_b.bin`'s tier byte has three distinct
values across the 74-row table (chr_b-Complete-Mapping.md's cited
distribution `{1:11, 2:56, 3:7}`), and three different impulse magnitudes
are live-confirmed on real objects (Kenshin/Momotaro/Yusuke/Kakashi/Eve/Muhyo
at tier 2, Sasuke at tier 1, Raoh at tier 3 — physics.md §6.4). Jump is
uniform only in the sense that everyone's arc comes out of the same
3-row table and the same integrator; the *tier selection* is a per-character
byte. Kakashi happens to sit in the 56-member majority tier (tier 2), so his
own arc numerically matches most of the cast, which may be why "jump feels
uniform" from playing him specifically — but the mechanism is not
character-independent.

## (b) Dash speed — the record, and what could not be located

**Grade: CONFIRMED_STATIC for the mechanism; [unverified] for Kakashi's own
record value.**

physics.md §6.3: ground-dash entry (`0x021565C0`)
zeroes `vx`/`vy` and sets bit `0x1000` in `element+0x34`; setup
`0x02156710` fills `element+0x9C/0x9E/0xA0` from a 5-byte record pointed to
by its `r1` argument: `+0xA0 = rec[4]` (duration), `+0x9C = rec[2] << 5`
(horizontal accel-per-frame, raw), `+0x9E = rec[3] × −126` (vertical, 0 for
a ground dash). Disassembly read directly this pass (`ov6.txt` lines
10298–10312) confirms the byte offsets and shift/multiply exactly as
physics.md states.

**New this pass: `0x02156710` is not reached by a direct `BL`/`BLX`.** A
scan of every ARM and Thumb branch in overlay 6 for a call to this address
found zero hits; the *only* reference to the literal `0x02156710` anywhere
in overlay 6 is a single data word at `0x02172030`. That word sits inside a
16-entry function-pointer table starting at `0x02172020` — index 0 of the
table is `0x021565C0`, the same dash-*entry* function physics.md §6.3
already cites, and index 4 is the setup function `0x02156710` this section
is about. The dispatch pattern (seen at `0x021567CC`: `ldrh r3,[r1]; and
r3,r3,#0xff; ldr r2,[tableBase, r3, lsl #2]; blx r2`) reads a state-code
byte out of the *same* pointer (`r1`) it then hands to the target function
as that function's own record argument — i.e. `r1` is one generic
"movement micro-command" record whose first halfword selects which of these
16 handlers runs, and whose later bytes (`+2`, `+3`, `+4`) are that
handler's own parameters. This is a materially different picture from a
per-character lookup table: it looks like a literal, shared command record
authored once for "perform a dash," not a per-character row.

**What supports that reading:** physics.md's own live measurement —
"Measured on Kenshin, Momotaro and Yusuke alike: accel 384 raw for 12
frames... The dash is not per-character" — is consistent with the record
being a single shared literal (`rec[2] = 12` → `12<<5 = 384`, `rec[4] = 12`
frames). Kakashi's own capture (characters/kakashi.md "B" row) confirms
the **12-frame duration** side of this ("A full 12-frame dash burst runs
Kakashi past Jotaro") but did not independently re-measure the accel value
for him — the `dash B`/`dash Y` rows in that table are byte-identical to
plain `B`/`Y` because the capture braked one frame into the burst, so no
distinct dash-speed number for Kakashi was ever recorded, live or static.

**What this pass could not locate:** who calls into the table-index-4
handler with which `r1`, i.e. where the record pointer itself is chosen —
whether it is one literal ROM address shared by every character (which
would make dash speed genuinely engine-wide, matching physics.md's "not
per-character" conclusion) or a pointer selected per-character before the
generic dispatch runs (which would make the owner's "dash is not \[uniform]"
framing correct and the 3-character match in physics.md a coincidence of
those three characters sharing a value). Tracing the caller of the
table-index-4 path — the function that actually commits the dash state and
supplies `r1` — was not completed this pass; xrefs.json's known blind spot
for Thumb `blx` sites (INVENTORY.md's "tooling hazards" note) is a
plausible reason the caller wasn't found by literal-pool or branch scanning
alone. **Kakashi's own dash-speed record value is therefore [unverified]
statically** — not read from a Kakashi-specific field, and not distinguished
from the 3-character engine-wide value already in physics.md.

**Owner-ruling tension, stated plainly (mirrors (a)):** the mechanism
(a 5-byte record with distinct duration/speed/vertical fields) *could*
support per-character values, and the owner's "dash is not \[uniform]"
framing assumes it does. But the only live evidence in this repo
(physics.md §6.3, 3 characters) found the value identical across all
three, and this pass's static trace did not find a second, per-character
table anywhere near the setup function — it found a single, generic,
state-code-indexed dispatch table instead. If dash truly varies by
character, the per-character selection has to happen *before* this generic
dispatch (i.e., in whatever installs the initial `r1`), and that step is
exactly what this pass didn't trace. This is the opposite tension from (a):
there, the data contradicts "jump is uniform"; here, the data available so
far is consistent with "dash is uniform" and in tension with the owner's
stated belief that it isn't. Neither is settled without the live half.

## (c) `obj+0x128` passive bits Kakashi's deck grants

**Grade: CONFIRMED_STATIC**, direct byte read plus the documented writer.

Mechanism (helpers.md §5, already confirmed prior to this pass): the
load-time ability bitset lives at `fighterObj+0x128` (word array,
`base = fighterObj+0x120`, bit `id & 0x1F` of word `base+0x8+4*(id>>5)`),
written by ov6 `0x0215FB3C`, reached only through a kind-dispatch table at
`0x02172210` — i.e. the writer runs once per ability id in the character's
*combined* list, at character init / battle start, and the whole bitset is
rebuilt on KO/respawn. The combined list is the on-disk five-slot record at
`chr_b+0x03..+0x07` (kind-0/1 ids) plus whatever the deck→battle-koma
bridge appends from the `+0x558` node chain (helpers.md §4) — the second
source that let Luffy's on-disk `[9, 25, 12]` become a runtime `[9, 25, 12,
14]` in the cited example.

**Direct read of `chr_b.bin`'s five ability-id slots (`+0x03..+0x07`), this
pass, for all four relevant rows:**

| chr_b idx | name | slots `+0x03..+0x07` | non-zero ids |
|---|---|---|---|
| 23 | Kakashi | `13 35 2 0 0` | 13, 35, **2** |
| 33 | Kurama | `28 29 44 0 0` | 28, 29, 44 |
| 57 | Mashirito | `45 47 0 0 0` | 45, 47 |
| 59 | Muhyo | `47 46 40 0 24` | 47, 46, 40, **24** |

Cross-check against the ability catalog (helpers.md §7 / owner taxonomy in
Helper-Passives-Catalog.md): Muhyo's id 24 = 軽量級 (Lightweight), and the
catalog's "Lightweight" carrier list independently names Muhyo — the two
sources agree, which is a sanity check on the record-size/offset
assumption (60 bytes/record, slots at `+0x03..+0x07`) used to read the
table.

**Result: Kakashi carries ability id 2 (三角飛び, Wall Jump) directly on his
own on-disk list.** Per helpers.md §5/§7 and
[mobility-passives-static.md](mobility-passives-static.md), ability 2 gates
bit `0x04` of `obj+0x128` at ov6 `0215E1F8`. **None** of Kakashi's own slots
or his three deck helper koma's slots (Kurama 28/29/44, Mashirito 45/47,
Muhyo 47/46/40/24) carry ability 1 (Triple Jump, bit `0x02`) or ability 3
(Air Dash, bit `0x08`).

**So, for this Kakashi battle state: bit `0x04` (Wall Jump) is set; bits
`0x02` (Triple Jump) and `0x08` (Air Dash) are not set** — sourced from
Kakashi's own `chr_b` record, not from Mashirito/Muhyo/Kurama. The deck's
helper koma contribute nothing to this specific bit range (they may still
contribute other abilities from the ids they do carry — 28/29/44, 45/47,
47/46/40/24 — which is outside this ticket's scope).

**Caveat: [unverified].** This is a static read of the on-disk five-slot
list only. Whether the `+0x558` deck-bridge append (helpers.md §4) ever
*removes* or reorders anything, and whether Kakashi's specific save state
(`pc-kakashi-npc-jotaro-dark-tournament`) is running the same on-disk
`chr_b` row this pass read (it should be — `chr_b` 23 is independently
confirmed live via the player-slot `+0x29` byte in characters/kakashi.md's
Conditions block) — were not re-confirmed by a live read this pass. The
five-slot table itself is read directly from ROM bytes, which is the
strongest static evidence available, but "no live write ever changes bit
`0x04` again mid-match" (helpers.md §5's KO/respawn re-cache note) is a
known exception this static read can't rule out for a specific match.

## (d) Character-specific SFX/VFX in Kakashi's move handlers

**Grade: negative result / [unverified] — no Kakashi-specific sound-id
literal was found; no VFX asset-id field was found either.**

**Sound.** The generic wrapper `0x0207342C(category, id)` is confirmed
element-agnostic for hit resolution: generic-vfx-sfx-triggers-static.md's
headline states the hit-resolution call (`id=0x28`, `category=0x7A` at
`0x02082478`) is "unconditional within the damage formula, not
element-keyed," and the guard/contact call (`id=0x2A`) is two structurally
identical, also generic, sites. Kakashi's B/Y normals route their reaction
handling through the shared handlers `0x0215B720` (types 1/2/7) and
`0x0215B910` (type 5) — physics.md §4.5 already establishes these are
uniform across all seven attackers checked (`jus-launcher-move-spot-check-hiyh`),
not per-character code. **No character-argument or character-keyed sound id
was found in or near these handlers this pass** — the sound call sites the
generic-sfx doc already traced are reached from the damage/collision path
generically, not from character-specific code Kakashi's moves branch into.

**Kakashi's own 20-byte collision records** (`na_b_04.bin`, read directly
this pass per characters/kakashi.md's "The authored records" table and
`move_records.py`'s field list) carry no field documented or attributable
as a sound id. The 20-byte layout's only two undecoded-but-suggestive
fields are `byte16` ("args 7 of ov6 `0x02153CE8` (`0x020819FC`); indexes
word table `0x02171E1C`") and `byte17` ("args 8 of ov6 `0x02153CE8`
(`0x02081A08`); indexes halfword table `0x02171E0C` -> vtable+0x104 call").
Neither is attributed to sound or VFX anywhere in `confirmed-facts/`; the
vtable `+0x104` call is a plausible dispatch point for *some* per-hit
side-effect (screen shake is already claimed by two *other* fields,
`shakeRowA`/`shakeRowB`), but this pass did not trace what `vtable+0x104`
resolves to. **This is the single most promising static lead this pass
found and did not close** — flagged [unverified], not claimed.

**VFX.** A previously-undocumented (in `confirmed-facts/`) on-disk file,
`jus_files/chrbin/chr/effect/na_b_04.bin`, exists per-character and is
loaded by the same loader that loads the collision/shot files
(`Battle_PrmDataInit 0x021702BC`, collision.md's citation). Kakashi's copy
is 56 bytes; a raw hex read shows what look like little-endian ROM-address-
shaped words (e.g. `0x00060440`, `0x0006046D`, `0x0006046E`...) followed by
2-byte tails, consistent with 7 short records rather than one big blob. No
confirmed-facts doc documents this file's record layout, and this pass did
not reverse it — flagged as an open static lead, not a result. The `chr/shot/`
file (projectiles — relevant to the beam/dogs specials) is similarly
undocumented at the field level; collision.md/INVENTORY.md's open
question "projectileId decode... still open" already flags this class of
gap.

**Conclusion for (d):** no Kakashi-specific SFX id is reachable statically
in his move handlers — the sounds that do fire are generic, element-agnostic
calls already documented elsewhere, and Kakashi's own move records don't
carry an attributed sound field. No VFX asset id was locatable either; the
per-character `chr/effect/` file is a real, unreversed candidate, not a dead
end, but reversing it was out of this pass's static budget.

## For the live half

Exact breakpoints the next emulator session should set, one B and one Y on
Kakashi, to confirm (a)–(d):

1. **`obj+0xBA` at battle start.** Read the P1 fighter object's `+0xBA`
   halfword once the state loads (before any jump input). Expect **−1752**
   (tier 2) for Kakashi. This is the cheapest possible confirmation of (a)
   and should be first.
2. **`obj+0x128` at battle start.** Read the word at `fighterObj+0x128`.
   Expect bit `0x04` set, bits `0x02`/`0x08` clear. This confirms (c)'s
   Wall-Jump-from-Kakashi's-own-record claim; also worth a `down+A`-next-to-
   a-wall input to confirm the ability actually fires for him (no live
   Wall-Jump capture exists anywhere in the repo yet for any character).
3. **`0x02156710` entry, log `r1` (record pointer) and its dereferenced
   bytes `[2]`/`[3]`/`[4]`**, on a Kakashi ground dash (`dash B`, driven far
   enough from the opponent not to brake early, unlike the existing
   `dashB_early` capture). Compare the resulting `+0x9C`/`+0xA0` writes
   against the 384-raw/12-frame value already measured on Kenshin/Momotaro/
   Yusuke. If Kakashi's numbers differ, dash is per-character and (b)'s
   "generic dispatch, not per-character table" reading is wrong; if they
   match, it's one more character confirming physics.md's "not
   per-character" conclusion, and the remaining question is purely which
   characters (if any) differ.
4. **`0x0207342C` entry, log `(category, id, framecount)`**, filtered to the
   frame windows of a Kakashi B, Y, and the 4-koma beam/dogs specials
   (reusing the generic-sfx doc's own instrumentation recipe). Confirm no
   id/category pair appears that isn't already in that doc's table
   (`0x28`/`0x7A` hit, `0x2A`/`0x7A` guard) — a positive would refute (d)'s
   negative result and should be chased immediately.

## Live half (2026-09-13)

Tracker item `jus-atns.4.6` live half, run in the same emulator session as
`jus-atns.4.5` (Kakashi SELECT). State `pc-kakashi-npc-jotaro-dark-tournament`,
probe `scripts/gdb/atns45_select.gdb`, raw logs in
`../feel-captures/kakashi-select-2026-09-13/logs/`
(`session1.log`). Full conditions and methodology in that folder's
`RESULTS.md`; this section only records the four values this ticket asked
for.

**1. `obj+0xBA` at battle start — CONFIRMED_LIVE.** Read at the first
frame anchor hit after a clean `state load`, before any input: **`-1752`**.
Matches (a)'s static prediction (tier 2) exactly.

**2. `obj+0x128` at battle start — CONFIRMED_LIVE, with an extra bit not
predicted.** Same first-frame read: **`0x2004`**. Bit `0x04` (Wall Jump)
is set, matching (c)'s prediction from Kakashi's own on-disk ability id 2.
Bit `0x2000` is also set, which (c)'s static pass did not predict (it only
traced bits `0x02`/`0x04`/`0x08` — Triple Jump / Wall Jump / Air Dash — and
did not attempt to decode every bit in the word). Not chased further this
pass; flagged as an open bit for whoever next needs the fuller ability
range. No `down+A`-near-a-wall Wall Jump firing was attempted (out of this
session's budget). A second read taken later in the session, after the
COM設定 menu was driven and the resulting state saved to a bridge slot,
came back `0x1000000` — a different bit entirely, taken well after battle
start (frame ~49, post-menu) rather than at load. That reading is **not**
used for this result; it is noted only as a caution that this word is not
safe to sample except at the true first frame, consistent with (c)'s own
"whole bitset is rebuilt on KO/respawn" caveat.

**3. `0x02156710` dash-setup record — CONFIRMED_LIVE, contradicts the
384-raw/12-frame value (b) cited from other characters.** A double-tap-LEFT
plan produced two `r1` hits:

| `r1` bytes `[0..15]` | `rec[2]` (accel field) | accel raw (`rec[2]<<5`) | `rec[3]` | `rec[4]` (duration) |
|---|---|---|---|---|
| `4,1,10,0,5,0,0,0,0,3,2,0,21,0,0,0` | 10 | 320 | 0 | 5 |
| `4,1,16,0,12,0,0,0,0,4,52,0,3,1,1,16` | 16 | 512 | 0 | 12 |

Both hits landed inside the same double-tap-LEFT plan window (the first
right as the input registered, the second ~110 frames later, plausibly a
second dash triggered by the held LEFT after the first burst's cooldown).
Neither matches physics.md §6.3's Kenshin/Momotaro/Yusuke value (accel 384,
12 frames) exactly; the second capture shares the 12-frame duration but not
the accel value, and the first shares neither. This is `[unverified]`
whether it means Kakashi's dash genuinely differs from those three
characters (supporting the owner's "dash is not \[uniform]" framing) or
whether the two live captures here are two different micro-commands routed
through the same setup function for a different reason (e.g. an initial
burst vs. a renewed one under continued input) — this pass did not
disassemble what selects `r1` before the call, which is exactly the open
question (b) already flagged. Reported as raw data, not a settled reading.

**4. `0x0207342C` sound wrapper — a positive result, refuting (d)'s
negative.** Filtered to the frame windows of one `B`, one `Y`, and one
double-tap-LEFT dash plan, `(category, id)` pairs observed (all
`category=0x7A` except one, framecount is this session's own probe
counter, not plan-local):

| frame | category | id |
|---|---|---|
| 90 | `0x17A` | `0x0` |
| 129 | `0x7A` | `0xD` |
| 694 | `0x7A` | `0x14` |
| 796 | `0x7A` | `0x43` |
| 802 | `0x7A` | `0x34` |
| 811 | `0x7A` | `0x15` |
| 812 | `0x7A` | `0xE` |
| 813 | `0x7A` | `0xE` |
| 814 | `0x7A` | `0xF` |
| 912 | `0x7A` | `0x34` |

None of these is `0x28` or `0x2A` — the two ids (d) said were the only
ones this wrapper ever carries. This directly refutes (d)'s "no
Kakashi-specific SFX id was found" framing insofar as it predicted no
positive would turn up: the wrapper plainly carries a much wider range of
per-event ids than the hit/guard pair, at least across a B, a Y and a dash.
This pass did not attribute any specific id to a specific move (the frame
numbers are this session's continuous probe counter across several plan
runs, not cleanly separated per move — see the folder's `RESULTS.md` for
the caveat), so **which id belongs to which move is `[unverified]`**; only
the existence of a wider id range is confirmed live.
