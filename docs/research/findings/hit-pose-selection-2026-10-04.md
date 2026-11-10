# Hit-reaction sprite selection

Task `jus-b2o1`. The attack's authored reaction type selects the ordinary hit pose. Damage strength does not select a light or medium tier. Successive hits can specify different reaction types, which explains the apparent pose alternation.

Six natural-input captures establish the selectors. Decoded native animations and pixel matching identify the owner's Yusuke, Kakashi, Train, and Eve PNGs. The categorized pose sheet shows the resulting labels.

## Labels and natural triggers

| Label | Native animation | Natural contact measured in this session |
|---|---|---|
| `hit_type_0` | `0x0B` | Eve's grounded B |
| `hit_type_1` | `0x0A` | Kakashi's grounded B; first hit of side+B |
| `hit_type_2` | `0x0C` | Kakashi's up+B; second hit of side+B |
| `surprised` | `0x0D` | Mashirito's side+B fart, reaction type 7 |
| Separate outlined alternate pose | `0x0E` | Sasuke's down+Y, reaction type 2 with alternate selector 2 |

The numbers in the filenames are engine reaction IDs, not severity, hit count, or animation order. Kakashi keeps his existing `_left` and `_right` suffixes. `surprised` retains its existing name. Animation `0x0E` was not among the three ambiguous labels and has not been merged into those files.

Each capture uses Jotaro as the victim. The dispatcher is shared across fighters; each victim's animation resource supplies that fighter's pose. This establishes selection through natural contacts without pretending that all four owner characters were separately captured as victims.

## Corrections to the original classifications

| Character | Previous `light` | Previous `light_2?` | Previous `medium?` |
|---|---|---|---|
| Yusuke | `hit_type_1` | `hit_type_0` | `hit_type_2` |
| Kakashi | `hit_type_2` | `hit_type_0` | `hit_type_1` |
| Train | `hit_type_0` | `hit_type_1` | `hit_type_2` |
| Eve | `hit_type_1` | `hit_type_0` | `hit_type_2` |

Kakashi's light/medium pair and Train's light/light2 pair were reversed relative to the other characters. Fifteen PNGs were renamed; their SHA-256 values are unchanged. The rename manifest records every old and new path. Each character's `hitstun/REACTIONS.md` describes the triggers and keeps the original filename correspondence. Existing slicing observations remain in the READMEs.

## Selection rules and exceptions

The ordinary entry at `ov6 0x0215B6A0` reads the victim's reaction type at `obj+0x100`. It selects the animation from `0x021713E8`, or the alternate column at `0x021713EC` when signed `obj+0x11E == 2`. The four ordinary mappings are type 0 to `0x0B`, type 1 to `0x0A`, type 2 to `0x0C`, and type 7 to `0x0D`. That entry does not branch on damage, impulse magnitude, impulse direction, or an airborne flag. See [the disassembly](../../../jus_files/analysis/disasm/ov6.txt), instructions `0x0215B6D8–0x0215B700`.

The upstream reaction is collision-record byte `+1`, staged at victim `ColPrm+0x16C` and copied to `obj+0x100`. The alternate selector is authored byte `+2`, staged at `ColPrm+0x174` and copied to `obj+0x11E`. Arm9 `0x02081600–0x0208163C` keeps the minimum nonzero alternate value when contacts accumulate. Sasuke's down+Y provides a natural selector-2 control; being in the air alone does not select the outlined pose. Selector 2 is distinct from the status byte and the separate record field named `hitEffect`.

Other reactions reuse some of these images. Type 3 starts `0x0C`. Type 4 starts `0x0C`, then plays `0x0F` knockdown. Types 13, 14, and 15 reuse `0x0B`, `0x0A`, and `0x0A`. Type 8's handler does not select a new animation, despite its table entry. Pop and launcher handlers have their own rules; the table alone is insufficient to classify them. These branches are in the same disassembly, entries `0x0215B568`, `0x0215B68C`, `0x0215B72C`, `0x0215B7CC`, `0x0215B870`, and `0x0215BA40`.

A sufficiently large combo accumulator, `obj+0x10E >= 600`, overrides ordinary types 0–4, 7, and 8 to type 4. This can turn a late hit into knockdown. It does not explain the ordinary type-1/type-2 alternation. See `ov6 0x0215AF60–0x0215AF84` and the previous knockdown research.

Stun duration uses a separate state-based calculation. Native animations `0x0A–0x0D` each have a four-frame single-cell track whose final cell holds; that track length does not mean four frames of hitstun. The [animation decoder](../../../scripts/analysis/anim_timing.py) reads the native ALMT tracks.

## Native cell identities

| Character | Archive prefix | `0x0A` | `0x0B` | `0x0C` | `0x0D` |
|---|---|---:|---:|---:|---:|
| Yusuke | `yh_b_01` | 23 | 22 | 24 | 32 |
| Kakashi | `na_b_04` | 25 | 24 | 26 | 38 |
| Train | `bc_b_02` | 24 | 25 | 26 | 27 |
| Eve | `bc_b_01` | 27 | 26 | 28 | 40 |
| Jotaro, live victim | `jj_b_01` | 26 | 27 | 28 | 29 |

All renamed images match the stated native cells. Most match exactly under the existing decoder's color tolerance. Kakashi's ripped left-facing cells and the Train type-1 cut have small pixel differences; every renamed image has more than 93% coverage in both directions. The verification output records individual scores and PNG hashes.

The actual Black Cat archives contradict older calibration prose that calls Eve `bc_b_02`. Eve graphics and animation TextureID `0x074100` belong to `bc_b_01`; Train graphics and `0x074200` belong to `bc_b_02`. The live Eve name plate, roster ID 37, and B cell 81 agree with `bc_b_01`. `move_records.KNOWN_REC0` already uses that prefix. The broader documentation audit is tracked separately in `jus-4wss`.

## Retained live evidence

All six traces are continuous across plan frame, emulator callback, and source frame counter, with `d == 1` and no torn samples. These are full accepted attack traces, not selected windows cut from a rejected run.

| Capture | Contact plan frame | Source frame | Reaction | Alternate | Selected animation | Jotaro cell |
|---|---:|---:|---:|---:|---|---:|
| Kakashi B | 18 | 8762 | 1 | 0 | `0x0A` | 26 |
| Kakashi up+B | 27 | 8771 | 2 | 0 | `0x0C` | 28 |
| Kakashi side+B, first hit | 18 | 8762 | 1 | 0 | `0x0A` | 26 |
| Same move, second hit | 27 | 8771 | 2 | 0 | `0x0C` | 28 |
| Eve B | 18 | 8276 | 0 | 0 | `0x0B` | 27 |
| Mashirito side+B | 21 | 9589 | 7 | 0 | `0x0D` | 29 |
| Sasuke down+Y | 56 | 7149 | 2 | 2 | `0x0E` | 37 |

The observed selector is the body ALMT player's table index at `child+0x2A`, joined to its decoded BoundsIndex cell. Fighter `obj+0x1BC` is a pointer and is retained only as `obj1bc_raw`; it is not an animation ID. The initial capture driver used that misleading field name; its decoded output was corrected without changing raw samples.

One setup attempt failed before any attack. Eighty two-frame walking pulses left the fighter's position unchanged. Its plans, logs, executed driver, and rejection record are retained separately. The replacement control used six-frame walking pulses on the same emulator session. That failed setup supplies no combat evidence.

Run `plans/verify.py` in the capture directory with the source repository's Pillow environment to check raw hashes, frozen driver hashes, clock continuity, every natural contact, native cell IDs, renamed PNG hashes, and pixel coverage. Initial framebuffers establish fixture identity; they are not pictures of the later hit poses.

Animation `0x09` remains an inventoried native pose with no demonstrated hit-reaction trigger. None of the renamed files maps to it. The broader jump, knockdown, getup, and uncaptured animation work remains in `jus-wmqi.6.8`.
