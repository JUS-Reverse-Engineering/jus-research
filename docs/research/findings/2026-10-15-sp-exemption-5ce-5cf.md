# Player-slot SP exemption bytes +0x5CE and +0x5CF: writers, clears, reach

Static only, no emulator. Grades: STATIC (read from
bytes or disassembly), INFERRED (follows from STATIC plus a stated assumption),
UNMEASURED (no evidence either way).

Setup for every command: `cd jus-research; source ~/.venvs/jus-re/bin/activate`, then
`jobq run -- python scripts/analysis/query.py ...` (abbreviated `Q` below).
`--overlay ovN` only on `disasm`/`func`/`callers`; the CLI rejects `--overlay arm9`.

## Answer in five lines

1. The stated searches (exact-offset `0x5CE`/`0x5CC` immediates and split-offset `0xCE`) find three identifiable byte stores to the slot offsets, all in ov6, belonging to two different features. INFERRED: this is a search result, not ROM-wide proof; a slot base built through an unsearched computation could hide another writer. No halfword or word store at these offsets was found.
2. +0x5CE is set by the handler for status effect id 13 and cleared when that effect leaves channel 0. Its name is probably the "Infinite" positive status, which the Jump Magazine field item grants (INFERRED).
3. +0x5CF is a copy of ability bit 37 ("Unlimited specials") rewritten by the loadout assembler. No shipped character carries ability 37 (STATIC), so it is a debug or hack route only.
4. No training-mode, cutscene, UA or story-mode writer exists (STATIC: no other store). A training-mode infinite-SP option, if one exists, is not in these flags (UNMEASURED).

## Q1. Writers (STATIC)

Survey: `Q search-imm 0x5CE --all`, `Q search-imm 0x5CF --all`. Result: 2 hits
and 1 hit, all `strb`, all ov6. Split-offset forms (`add rX,rY,#0x500` then
`[rX,#0xCE]`) were swept with `Q search-imm 0xCE --all` and `Q search-imm 0xCF
--all` (stores only). The arm9 `strb [r8,#0xce/#0xcf]` stores at
0x020816BC/D0/F4/0x02081708 and 0x02081FE4/F8/0x0208201C/30 are on a hit record
in the damage routine (base r8, no #0x500 add), not the player slot. The ov6
`strh [..,#0xce]` hits are halfword fields on other structs. `Q search-op-imm
0x5CE` and `0x5CF` return 0 hits, so no `mov`-built offset. Neighbouring byte
+0x5CD (SP bars) is stored at 0x02076BA0/B0, 0x0207831C, 0x02078340,
0x0207878C; +0x5CC at 0x02077618 etc. No word or halfword store at +0x5CC
overlaps +0x5CE (`Q search-op-imm`/`search-imm 0x5CC` shows `strb` only).

| addr (ov6) | function | value | runs when |
|---|---|---|---|
| 0x02159180 | 0x0215911C `(obj, channel)` | `r1 = 0` (clear) | teardown of effect channel 0 |
| 0x0215936C | 0x02159364 | `r1 = 1` | start handler of status effect id 13 |
| 0x02157298 | 0x02157114 (loadout assembler) | `(obj+0x12C & 0x20) != 0` | spawn and every switch/respawn re-setup |

Reproduce: `Q disasm 0x0215911C 56 --overlay ov6`, `Q disasm 0x02159344 36
--overlay ov6`, `Q disasm 0x02157114 130 --overlay ov6`.

### +0x5CE writer chain

- 0x02159364 is the 13th entry (index 13) of the 8-byte-stride effect handler
  table at ov6 0x02171168: entry address 0x021711D0 = handler 0x02159364,
  descriptor 0xFF050B0D. STATIC. Pointer scan: the word 0x02159364 appears once
  in ov06.bin, at table slot 0x021711D0 (python `-I` scan of
  jus_files/overlays/ov06.bin in the main checkout, base 0x0214CD20). Table base is loaded by
  0x02158EE4 (`Q pool-values 0x02171168 0x02171168`).
- 0x02158ED0 `(battleObj, id)` is the dispatcher. It picks channel `r7 = (param.flags & 0x10) != 0` (0x02158F04..0x02158F0C), calls
  0x0215911C(obj, r7) at 0x02158F3C, then calls the table handler at 0x02158F94. STATIC.
- Effect id 13 parameter (docs/research/findings/p169-state-bin-is-the-param-array.md:53): flags 0x0002 (bit 0x10 clear, so channel 0), duration 300 frames. Doc-derived, so the flags column is STATIC only through that doc.
- Callers of the dispatcher and the id source: Route A script operand (id = operand+1 for operands 0..0x10, so operand 12) and Route B staged ids `X+0x172/0x173` flushed at 0x02158B68 (docs/research/findings/p159-effect-id-table-and-selection-routes.md, docs/research/Battle-Engine-Map.md:1149). Runtime row "id 13 ... 300/300" exists there. STATIC for the routes, CONFIRMED_RUNTIME in that doc for one dispatch.
- Identity of id 13: INFERRED to be the positive "Infinite" status ("Special Gauge becomes effectively infinite", granted by the Jump Magazine item: docs/research/guides/systems/battle-system.md:101 and :137). Basis: id 13's only side effect is setting the SP free-pass byte, and "Infinite" is the only SP-exempting status in the guide. The id-to-name table was not decoded. A second-opinion check would read the status icon/name table for id 13.

### +0x5CF writer

- 0x02157290..0x02157298: `r1 = ((uint32)obj[0x12C] & 0x20) ? 1 : 0; strb r1,[slot+0x5CF]` with `slot = [obj+0x1B4]`, inside a 6-iteration loop that stores the same value each pass (0x0215729C..0x021572B4). STATIC.
- obj+0x128 is the load-time ability bitset (docs/confirmed-facts/helpers.md section 5: word `+0x128+4*(id>>5)`, bit `id&31`). Word 1 bit 5 is ability id 32+5 = 37. STATIC bit arithmetic, doc-derived layout.
- Ability 37 is 必殺技無制限 "Unlimited special moves", kind 0 (docs/confirmed-facts/helpers.md:245, docs/research/findings/abilities-all-57-named.md:102). It is listed as one of 11 orphan ids carried by no chr_b record (helpers.md section 8). The four all-zero chr_b records 70..73 are the unselectable Debug series (helpers.md section 4). docs/research/Deck-System.md:111 lists an "infinite SP helper" under hack-only debug content. Delivery would have to come through the deck helper-koma chain at +0x558 (helpers.md section 4); no known helper koma carries it (UNMEASURED for the full koma table).

## Q2. Clears

- +0x5CE: `0x0215911C(obj, 0)` at 0x02159180. Branch: only the `r1 == 0` path (channel 0) clears; `r1 == 1` jumps to 0x02159188 and does not (0x02159134). STATIC. Call sites (`Q callers 0x0215911C --overlay ov6`):
  - 0x02158D0C: per-frame tick in 0x02158B20 when duration (node+0xE) reaches 0 (docs/research/findings/p174-effect-tick-driver.md). Natural expiry.
  - 0x02158F3C: dispatcher replacing whatever sits in the target channel before starting a new effect.
  - 0x02159114: via 0x021590FC `(obj, channel, id)`, which clears only if the node's id (node+0xC) equals `id`. Its five calls in 0x02157328 (switch/respawn re-setup) pass ids 0x0C, 0x0E, 0x0F, 0x23, 0x24 on channel 0 (0x02157370..0x021573B0). Id 13 is not in that list, so a switch or respawn does not clear +0x5CE (STATIC; this matches the guide rule that effects carry over on switch).
  - 0x0215C3C4/0x0215C3D0 (in 0x0215C360) and 0x0215C6C8/0x0215C6D4 (in 0x0215C690): `(obj,1)` then `(obj,0)`, unconditional. Called from KO transitions (roles INFERRED from the unconditional pair and from physics.md:933 for time-out expiry, which also calls the pair for both players).
  - Not found: any clear at battle init other than allocation zeroing. The ComicDeck allocator 0x02075FBC calls `0x020517FC(ptr, 0, size)` at 0x0207603C (`Q disasm 0x02075FD0 60`); 0x020517FC looks like a memset (`cmp r2,#0 / bxeq lr / alignment head`), INFERRED. It zeroes only per-element +0x558..+0x564 explicitly, so the zero start of +0x5CE/+0x5CF at battle start rests on that memset.
- +0x5CF: never cleared separately. Each run of 0x02157114 overwrites it from the bitset (callers: 0x02156D0C in the fighter constructor 0x02156A38, and 0x021573D4 in 0x02157328). So it follows the bitset: 0 unless ability 37 is in the loaded list. STATIC.

## Q3. Which features reach them

Readers (to see where the effect lands): `Q search-imm 0xCE --all` and `0xCF` loads, filtered to slot-base users.

| reader | what it does | grade |
|---|---|---|
| 0x0207835C / 0x0207836C in wrapper 0x0207834C | either byte nonzero: return 1, no spend (0x02078358..0x02078378). Else call 0x0207830C, which computes +0x5CD minus cost and returns 0 if negative | STATIC |
| 0x020780C0 / 0x020780D0 in 0x02078038 | same either-byte test returning "usable"; callers 0x02078110 and 0x02078120 (arm9), 0x02152F90 (ov6) | STATIC; gate semantics INFERRED from the return value (support-koma path) |
| 0x020781F8 in 0x020781E4 | for a negative delta, +0x5CF != 0 returns early (SP loss refused). Gains pass. +0x5CE is not read here | STATIC |

- Normal versus: +0x5CE is reachable whenever effect 13 can be applied, for example by the Jump Magazine item (INFERRED name, STATIC route). +0x5CF is not reachable from any shipped character (STATIC for chr_b; UNMEASURED for helper koma).
- Training mode, cutscene, Ultimate Action, story or mission mode: no store exists outside the three above, so none writes the bytes directly. The mode could still apply effect 13 through the normal script or item routes (UNMEASURED; no evidence either way).
- Repo-wide search (`rg -i '5ce|5cf|sp_lock|infinite' docs`) found only restatements of this wrapper behaviour, the guide status text, the cheat codes (docs/research/Cheat-Code-Analysis.md:56, which write the SP meter value, not these flags), and Deck-System.md:111.
