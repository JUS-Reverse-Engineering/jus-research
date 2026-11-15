# Taikoubou 6-koma X (anim 0x2d): contact and deck-count branches

Static reverse engineering, 2026-10-15. No
emulator. jus_files `548c5cd0`.

Labels: **STATIC** = read from ROM bytes or disassembly in this session (address
or path cited). **INFERRED** = derived from STATIC facts plus a stated
assumption. Nothing here is MEASURED; session B confirms or refutes it.

Tools: `scripts/analysis/anim_events.py hs_b_01 --anim 0x2d` (now decodes the
two branch subs, see section 5), `scripts/analysis/disasm_range.py`,
`scripts/analysis/query.py`. Pinned by `scripts/tests/test_anim_events.py`
(`BranchDecodeTest`, `TaikoubouSixKomaXTest`, `BranchCodeFactsTest`).

## 1. The event bytes

`hs_b_01.amt` is the only member of `chr/hs_b_01.aar` that has anim 0x2d. The
koma archives `hs_b_01_{4,5,6}.aar` hold only effect tables `hs_b_01_e{4,5,6}.amt`
(STATIC). The ChrArc.aar index names them without a suffix; the extracted
files under `ripped_jus_files/chr/` carry a `c` suffix (`hs_b_01c.aar`,
`hs_b_01_{4,5,6}c.aar`). Anim 0x2d is 209 frames. Its Marker track is
`{0: f0, 1: f81, 2: f89, 3: f143, 4: f177}` (STATIC).

| frame | bytes | decode |
|---|---|---|
| f43 | `05 00 01 00` | op0 sub5 **contact_wait**, Marker 1 (f81) |
| f79 | `01 03 ..` | op3 sub1 end key (A) |
| f81 | `05 00 ff 00` | op0 sub5, Marker -1: disarm |
| f104 | `02 00 02 02` | op0 sub2 loop to Marker 2 (f89), limit 2 (already in mash-table) |
| f109 | `0e 00 07 03 0b 04` | op0 sub14 **deck_count_branch**: count >= 11 -> Marker 4 (f177); else count >= 7 -> Marker 3 (f143); else no jump |
| f141, f175, f209 | `01 03 ..` | end keys (B, C, D) |

The remaining keys are op1/op3 sub0/op4 sounds, as `anim_events.py` lists them.
The three finisher segments f109-f141, f143-f175 and f177-f209 have the same
layout 34 frames apart. Each has an op1 sub3 `0x6d8` key, a spawn of `0x07c1a9`
at (54,-4), an op3 sub0 arg 5 key, an op1 sub1 key and an end key (STATIC).

## 2. The handlers

The op0 sub table is `0x02172084`. Sub 5 maps to `0x02155D3C` and sub 14 to
`0x02155E90` (STATIC, pinned).

**Sub 5 (`0x02155D3C`).** The code is `ldrsb r2,[r1,#2]; mov r1,#6; bx 0x021565A4`.
It queues kind 6 with marker ev[2]. Kind 6 lands in slot 2: table `0x021710A8`
holds byte 2 at index 6 (STATIC).

The slot loop (`0x021556E0`-`0x02155740`) polls 7 slots through table `0x02172040`.
It skips any slot whose marker is -1 (`mvn r8,#0`, `cmp r0,r8`). When a poll
returns nonzero, the loop takes that slot's marker, writes -1 back (so the slot
fires once) and jumps (vtable `+0xEC`, `0x02155768`).

The whole loop is skipped once `ctrl+0x90` bit `0x10000000` is set
(`0x021556D8`). The end key handler `0x0215693C` sets that bit at `0x02156954`
(STATIC). So the f81 disarm only matters if the move has already jumped.

**Kind 6 poll (`0x021563B4`, table `0x02172040[6]`).** It returns 1 iff
`[[[ctrl+0x7C]+0x10]+0x158] & 0xF` is nonzero (STATIC).

- `[ctrl+0x7C]+0x10` is the object that ground_wait reads at `+0x78`
  (`docs/rebuild/mash-table.md`). INFERRED: it is the entity's ColPrm record
  (`entity+0x10`, `docs/confirmed-facts/collision.md` section 3).
- `+0x158` lies in that record's `0xD0`-byte scratch region (`+0xA4`-`+0x173`).
  The collision driver `0x0207F480` clears this region on every pass:
  `add r5,r4,#0xa4` at `0x0207F888`, then `mov r2,#0xd0` and `bl memset` at
  `0x0207F8A4`-`0x0207F8AC` (STATIC).
- The contact processor `0x02080F14` ORs the other participant's element word
  `+0x14` (low 24 bits) into it at `0x02081588`-`0x02081598` (STATIC). This is
  the function whose `0x02081280` call computes damage
  (`docs/confirmed-facts/damage.md` section 1).
- INFERRED: kind 6 means "this fighter's collision made contact this frame". Its
  sibling polls test the same word: kind 8 at `0x02156434` adds `+0x15C`/`+0x164`
  bit `0x20`, and kind 14 at `0x02156480` adds query 0x46.
- **Not resolved:** which contacts set the low nibble (a landed hit only, or a
  block or a clash too), and which side of the pair is the owner. Session B
  must settle this.

**Sub 14 (`0x02155E90`) (STATIC).**

```
ip = [ctrl+0x70]; if ip == 0 return
if ip(ctrl, [ctrl+0x74], 0x42, s8 ev[4], 0,0,0,0,0): queue kind 0 -> Marker u8 ev[5]   ; 0x02155EC4-0x02155EE8
elif ip(ctrl, [ctrl+0x74], 0x42, s8 ev[2], 0,...):   queue kind 0 -> Marker u8 ev[3]   ; 0x02155F08-0x02155F34
```

Kind 0 goes to slot 6, the plain playhead jump queue (the one loop uses).

## 3. What query 0x42 reads

`[ctrl+0x70]` is the fighter callback `0x02157A44`. It is stored at `0x02155438`
(`docs/research/findings/cancel-windows-static-2026-09-25.md`), and here r1 is the
fighter `[ctrl+0x74]`. The callback switches on r2 through the jump table at
`0x02157A68`; slot 0x42 at `0x02157B70` branches to `0x02157E68` (STATIC):

```
0x02157E68  ldr   r0, [r5, #0x1b4]   ; fighter+0x1B4 = its player slot
0x02157E6C  add   r0, r0, #0x500
0x02157E70  ldrsb r0, [r0, #0xdf]    ; s8 slot+0x5DF
0x02157E74  cmp   r0, r4             ; r4 = threshold (r3 on entry)
0x02157E78  blt   0x02157F90         ; -> return 0
0x02157E7C  mov   r0, #1
```

So **query 0x42(n) = (s8 `[[fighter+0x1B4]+0x5DF]` >= n)**. `fighter+0x1B4` is
one of the four `0x61C` player slots in the ComicDeck block
(`docs/research/findings/char-0x1b4-is-a-comicdeck-player-slot.md`).

`slot+0x5DF` has exactly one immediate-offset store in the ROM:
`query.py search-imm 0x5df` returns only `0x02077624 strb [r0,#0x5df]` (STATIC).
That store is the zeroing at the start of the deck tally `0x02077610`. The same
function then increments the byte through `lr = r0+0xDF+0x500`
(`0x0207764C`, `0x0207765C`). For each node of the slot's deck list `[slot+0x558]`
(`next = [node]`), it does the following (STATIC):

- `+0x5DD` += 1 for every node.
- `+0x5DF` += 1 if `cls = [[node+0x34]+0xB] & 0xF` is neither 2 nor 3
  (`0x020776F4`-`0x02077704`).
- `+0x5E0`/`+0x5E1`/`+0x5E2` += 1 by `node+0x40` = 0/1/2. The koma type is
  0 battle, 1 support, 2 helper (`docs/confirmed-facts/koma.md` section 5).
- `+0x5DE` += 1 if `node+0x12 == 1`.
- `+0x5CC` is the SP maximum (`docs/confirmed-facts/guard-sp.md`).

`node+0x34` is an entry of the `0xC`-byte table at `deck+0x30`. INFERRED: that
table is koma.bin (`docs/confirmed-facts/deck-editor.md`:143 says it has
koma.bin's record shape). So `cls` is the low nibble of the koma.bin flags byte
`+0xB`. In the 890 koma.bin records that nibble is 0 (726), 1 (157) or 2 (7).
Value 2 belongs only to the series-42 helper panels 870-875 and 888; value 3
never occurs (STATIC, read from `bin/koma.bin`).

**INFERRED: `+0x5DF` counts the deck's panels of every type (battle, support
and helper), except those 7 special helpers.** This is the "characters in your
deck" of the kit text. Taikoubou's own koma is one of them.

STATIC: two writers reach `+0x5DF`.

- The initializer `0x02076C18` clears the slot struct: `0x02076C20 add r0, r7, #8`,
  `0x02076C24 mov r1, #0`, `0x02076C28 mov r2, #0x5e0`, `0x02076C2C bl #0x20517fc`.
  That clears 0x5E0 bytes from slot+8, which covers +0x5DF.
- The tally `0x02077610` stores the count: `0x0207764C add r3, r0, #0xdf`,
  `0x0207765C add lr, r3, #0x500`, and the conditional `0x02077704 strbne sb, [lr]`.
  Its zero store is `0x02077624 strb r3, [r0, #0x5df]`.

A reviewer's alias and copy search found no other confirmed writer. That does not
prove there is none. INFERRED: the count is taken when the slot is built
(`0x020769CC` calls `0x02077610`; there are 6 callers). Whether the count changes
during a fight is UNMEASURED.

## 4. Each end frame and its condition

| end | path | finisher | condition |
|---|---|---|---|
| **f79** | f0 -> f79 | none | no kind-6 contact from the f43 arming to the f79 end key (STATIC chain; edges INFERRED) |
| **f141** | contact -> f81 -> loop x2 -> f109, no jump -> f141 | rec 28 `0x11c`, 16, hit id 284 at f117-f128 | contact, and deck count < 7 |
| **f175** | ... f109 -> Marker 3 f143 -> f175 | rec 29 `0x11d`, 24, hit id 285 at f151-f162 | contact, and 7 <= count <= 10 |
| **f209** | ... f109 -> Marker 4 f177 -> f209 | rec 30 `0x11e`, 30, hit id 286 at f185-f196 | contact, and count >= 11 |

Hit ids are from a scratch `collision_boxes.py build --char taikoubou --chr-b 68
--prefix hs_b_01`. Damage values are from `docs/rebuild/knockback-table.json`
characters[39] (STATIC).

The shared segment is identical on every contact path (STATIC):

- f43-f62: id 278 (rec 22, damage 0, kbX 10). This is the contact probe.
- f81-f103: ids 279/280 (recs 23/24, damage 2 each), alternating windows every
  4 frames. That is 6 windows on the first pass and 4 on each of the 2 loop
  passes (f104 -> f89, limit 2), 14 in all.
- f105-f108: id 281 (rec 25, damage 10).

## 5. Deck-size damage scaling

Within anim 0x2d's sub 14 branch the count only picks one of three finisher
records (16/24/30). That branch has no multiplier table (STATIC).

A separate count-scaled path exists (STATIC). `0x02159378` reads
`[[P1 char+0x1B4]+0x5DF]` (`0x02159380 ldrsb r1, [r1, #0xdf]`) and sets
fighter+0xBC = 0x100 + 16*count (`0x02159398 strh r1, [r0, #0xbc]`). The update at
`0x02158DF8 strh r4, [r0, #0x84]` moves it into the collision multiplier at +0x184,
which `0x02082480 ldrh r2, [r0, #0x84]` consumes. The scanned Taikoubou keys do not
invoke this path (STATIC). Whether anything in Taikoubou's kit triggers it is
UNMEASURED.

INFERRED: if every window lands once, the raw totals are 14x2 + 10 + {16,24,30}
= **54 / 62 / 68**. The guide in `character-mappings/TAIKOUBOU/kit.md`:122 gives
"54 total ... (up to 68 max)" to power and knowledge, and 81/102 (x1.5) to
laughter. That matches the low and high tiers exactly.

Cross-check: four other anims use sub 14 with query 0x42 (a roster scan in
scratch):

- `bu_b_01` (Kazuki) 0x2d uses thresholds 11/7, ends 74/137/200. Its guide
  (`KAZUKI MUTOU/kit.md`:110) says "2-5 Koma 40, 6-9 Koma 48, 10+ Koma 56".
- `db_b_02` (Goku) 0x2e/0x30 uses 11/7 ("power increases per character in your
  Deck").
- `kn_b_01` 0x2f uses 10/5.

INFERRED: Kazuki's cut points 6 and 10 against the thresholds 7 and 11 suggest
`+0x5DF` = (the guide's koma count) + 1. The cause is open: either the guide
leaves out the fighter's own koma, or the list holds one more node than the
deck shows. With the + 1, Taikoubou's tiers would be about <= 5, 6-9 and >= 10
koma by the guide's way of counting.

## 6. Decoder addition

`anim_events.py` now tags op0 sub5 and sub14 events with a `branch` field and
lists them per anim in `branches` (marker frames resolved from the Marker track).
The other subs and ops are unchanged.

## 7. What session B must measure

1. A 6-koma Taikoubou X that whiffs ends at f79 (actionable at about f79 + idle
   lag). A connecting X runs on to f81.
2. A blocked X: does a guarded contact set the kind-6 nibble (jump to f81) or
   not? Also an X that meets only a projectile.
3. Read `[[P1 char+0x1B4]+0x5DF]` live in three decks (for example 1, 7 and 11
   counted panels, plus one deck holding a series-42 helper). Check that the
   finisher is rec `0x11c`/`0x11d`/`0x11e` and that the end is f141/f175/f209.
   Also check whether the byte includes Taikoubou's own koma.
4. Total damage per tier against a knowledge target (expected raw 54/62/68
   before resistances, x0.75 special resist gives 40.5/46.5/51). Also the
   number of 279/280 hits (expected 14).
5. Whether `+0x5DF` changes in mid-battle (for example after a koma is lost).
6. INFERRED: `+0x158` has a bucket-4 producer at `0x02081FAC` (`str r1, [r0, #0x158]`),
   so guarded body contact can probably satisfy the contact test.
7. UNMEASURED: Taikoubou's blocked and clash activation (see item 2).
