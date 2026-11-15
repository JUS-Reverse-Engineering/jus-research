# VFX and SFX: hit sparks, effect spawns and sounds (Kakashi, Yusuke, shared)

This page says which effect and which sound JUS plays for a hit, a guard, a
clash and each move of Kakashi (`chr_b` 23) and Yusuke (`chr_b` 32). It also
says where the effect art and the sounds live, and how to render them.
Tracker item: `jus-wmqi.6.12`. The effect renderer is the `jus-wmqi.6.7` tool.

- The machine-readable copy is [vfx-sfx.json](vfx-sfx.json).
  Use the JSON for machine-readable data.
- One tool writes the JSON and prints the tables marked *generated* below:
  [scripts/analysis/vfx_sfx_build.py](../../scripts/analysis/vfx_sfx_build.py)
  (`--tables` prints them, `--check` says if the JSON is stale). Its test
  [scripts/tests/test_vfx_sfx_build.py](../../scripts/tests/test_vfx_sfx_build.py)
  fails if the JSON or these tables drift from a fresh build.
- The decoders it uses:
  [anim_events.py](../../scripts/analysis/anim_events.py) (effect spawns and
  NoteTrack events),
  [effect_render.py](../../scripts/analysis/effect_render.py) (effect art to
  PNG),
  [sfx_render.py](../../scripts/analysis/sfx_render.py) (sounds to WAV) and
  [sdat_inventory.py](../../scripts/analysis/sdat_inventory.py) (the sound
  archive's names). Each has a test in `scripts/tests/`.
- **NOT FOR RELEASE.** The PNG and WAV renders are ripped JUS assets. They
  live only in `jus_files/extracted/vfx-sfx/render/` (untracked) and are
  never committed, uploaded or published. This page and the JSON keep ids,
  frames and numbers only.

Grades: **static** (read from the game files or the ROM code, cited),
**measured** (a live capture, cited), **visual** (read by eye from a render),
**inferred** (a rule, named), **TBD** (a tracker item is open).

## 0. Conditions behind every number

| item | value |
|---|---|
| ROM code | `jus_files/arm9`, overlay 6 through `rom_loader.load_memory_map()`; addresses are RAM addresses |
| effect art | `jus_files/ripped_jus_files/chr/ChrArc.aar` members `chr/na_b_04.aar`, `chr/yh_b_01.aar` and their `_4`/`_5`/`_6` special-move archives; `jus_files/ripped_jus_files/efc/comm_a.aar` … `comm_c.aar`, `comm_g.aar` |
| hit records | `jus_files/chrbin/chr/col/<prefix>.bin` (20-byte collision records, `move_records.py`) |
| per-character hit effects | `jus_files/chrbin/chr/effect/<prefix>.bin` (66 files; none for Yusuke) |
| sound | `jus_files/ripped_jus_files/sound/JS2_sound.sdat` |
| live cross-checks | vfx-sfx-live-2026-09-14 (Kakashi on `pc-kakashi-npc-jotaro-dark-tournament`; `y_mash_ko` used `pc-kakashi-npc-jotaro-fightcpu`, whose active P1 is Muhyo, not Kakashi, per `jus-fightcpu-state-not-kakashi-w63s`) |
| no new emulator run | this pass is static; open questions carry a capture plan in their tracker item |

## 1. Formats

Each tool's docstring holds the full byte layout. In short:

- **Effect art (DSIG v1).** A header, 16-colour BGR555 palettes (colour 0 is
  clear), then pixel rows of 32 bytes, raw or one LZ77 block (flag `0x10`).
  The same buffer holds two kinds of art. A segment with shape bit 6 set
  reads it as 2 bpp, 128 px wide (colours 0-3). With bit 6 clear it reads it
  as 4 bpp, 64 px wide. **static:** every file's pixel count is height × 32,
  and every segment fits its view (`test_every_segment_fits_the_texture`).
  The fighter's main sheet is DSIG v2 (`anim_timing.py`), a different layout.
- **Sprite list (DSTX).** Sprites made of 6-byte segments (source cell,
  x, y, shape, palette). Version 2 adds an 8-byte bounds trailer; version 1
  (the `comm_*` banks) has none. The texture is embedded, or a u32 id that
  names a `.dig` in the same bundle.
- **Effect animation (ALMT `<bundle>.amt`).** The `BoundsIndex` track picks
  the sprite; `TextureID` picks the `.dtx`. Effect id =
  `(amt file id & 0xFFFF00) | anim id`, so Kakashi's anim `0x42` is effect
  `0x060442`.
- **Spawn tracks (GN nodes of a move's animation).** STATIC: `GenerateID`
  keys are (u16 frame, u32 effect id), and `2DPos` gives (x, y) per frame.
  The native key reader at arm9 `0x02016220` dispatches nonzero IDs on the
  matching frame through the effect node's spawn method. Section 12 gives
  the native framing, flags and attachment evidence. Rendered placement
  remains UNMEASURED (`jus-wmqi.6.13` plan logs the spawn position).
- **NoteTrack (SP01 node).** Keyed (frame, rel) → a list of events (u8 sub,
  u8 op, s16 arg). The per-frame loop at ov6 `0x021557C0` calls op table
  `0x0217200C[op]`. **static:** op 4 is sound; `0x02156A18` calls table
  `0x02171FF4[sub]` from `0x02156A2C`. sub 0 plays `(0x7A, arg)`; sub 1
  plays `([obj+0xA4], arg)`; sub 2 plays `([obj+0xA6], arg)`; subs 1 and 2
  skip when that halfword is 0. Ops 0-3 are TBD (`jus-wmqi.6.18`).

## 2. Hit-effect dispatcher

**static** (ov6 `0x02153CE8`; callers `0x02081A24` and `0x02082134`, both
decoded by the builder). A landed hit calls it with two selector bytes
from the move's collision record:

- `r1` = record byte `+0x0E`, the **hit effect**. It is the same byte
  [damage.md](../confirmed-facts/damage.md) calls the class index (step 4;
  low 6 bits, range 0-15, `0x3F` = none). Caller `0x02081A24` loads it at
  `0x0208125C`. It stores −1 (no hit effect) instead when `fp & 0x1600`
  and `sb & 0x100` are both set (`0x02081240`-`0x02081254`); what those
  bits mean is not traced.
- `r2` = record byte `+0x0F`, the **onomatopoeia** (loaded at
  `0x02081238`). It stores −1 (no text) instead when `fp & 0x100` and
  `sb & 0x10000000` are both set (`0x0208121C`-`0x02081230`); what those
  bits mean is not traced. `move_records.py` used to call these two bytes
  `shakeRowB`/`shakeRowA`; they are the dispatcher's selectors.

What each selector does (−1 skips it):

| selector | effect spawn `0x0206C7FC(id, x, y, flag)` | sound `0x0207342C` |
|---|---|---|
| `r1` < `0x40` | `pair[r1][sel]` from `0x02171E6C`, flag 0 | `(0x7A, sound[r1])` from `0x02171E2C` |
| `r1` ≥ `0x40` | per-character record `[r1 − 0x40]` word `+0`, flag 1 | `(ctx[+0x18 + 2·slot], record +6)`, skipped if that halfword is −1 |
| `r2` < `0x40` | `0x240000 \| r2` (a `comm_g` text), `0x20` units higher (`y − 0x20`; px if the units are px, §1), flag 0 | none |
| `r2` ≥ `0x40` | as `r1` ≥ `0x40` | as `r1` ≥ `0x40` |

`sel` is the dispatcher's entry `[sp+0x10]`: 0 or 2 pick `pair[i][0]`, 1
picks `pair[i][1]`. Caller `0x02082134` passes 0; caller `0x02081A24`
passes its own `[sp+0x28]`. What sets that is TBD (`jus-wmqi.6.14`). The
two small tables the dispatcher also indexes (`0x02171E1C` by record
`+0x10`, `0x02171E0C` by `+0x11`) are all zero in this ROM.

The shared table (*generated*):

| index | sound (SEQ_BATTLE) | spark pair [0] / [1] |
|---|---|---|
| 0 | `0x0e` SE_HIT | `0x210000` / `0x210013` |
| 1 | `0x0f` SE_HVYHIT | `0x210001` / `0x210014` |
| 2 | `0x10` SE_SLASH | `0x210002` / `0x210015` |
| 3 | `0x10` SE_SLASH | `0x210003` / `0x210016` |
| 4 | `0x10` SE_SLASH | `0x210004` / `0x210017` |
| 5 | `0x10` SE_SLASH | `0x210005` / `0x210018` |
| 6 | `0x10` SE_SLASH | `0x210006` / `0x210019` |
| 7 | `0x11` SE_HVYSLASH | `0x210007` / `0x21001a` |
| 8 | `0x11` SE_HVYSLASH | `0x210008` / `0x21001b` |
| 9 | `0x11` SE_HVYSLASH | `0x210009` / `0x21001c` |
| 10 | `0x11` SE_HVYSLASH | `0x21000a` / `0x21001d` |
| 11 | `0x11` SE_HVYSLASH | `0x21000b` / `0x21001e` |
| 12 | `0x3a` SE_KABOOM | `0x23000e` / `0x23000e` |
| 13 | `0x3a` SE_KABOOM | `0x23000f` / `0x23000f` |
| 14 | `0x0e` SE_HIT | `0x220010` / `0x220010` |
| 15 | `0x0e` SE_HIT | `0x230014` / `0x230014` |

**Reading (inferred from the sound names):** indices 0-1 are blunt hits
(`SE_HIT`, `SE_HVYHIT`), 2-6 are slashes (`SE_SLASH`), 7-11 heavy slashes
(`SE_HVYSLASH`), 12-13 explosions (`SE_KABOOM`). The sound table splits
where damage.md's class-to-category table splits (0-1 → category 1, 2-11
→ category 2, 12-15 → category 0). So the blunt/sharp split lives in byte
`+0x0E`. **visual:** pair[0] sparks are orange/red, pair[1] sparks are blue
(§6).

**static:** Kakashi records 1-2 carry index 0 and record 3 carries index 1
(`vfx-sfx.json` `hit_records`); the researcher reads them as `Y`'s three
hits. **measured:** in the live `neutral_y` log the dispatcher's own
sound call (`lr 0x02153D30`) asks for `(0x7A, 0xE)` at raw frames 278 and
279 and `(0x7A, 0xF)` at 280. The HP drops at 280, 281 and 282. So three
dispatcher sounds lead three HP drops, each by 2 frames: `0xE`, `0xE`,
`0xF`, like records 1-3. The frame-279 call has no `sound` row after its
`sound_entry` in the log, so the sound wrapper seems to have dropped it
as a repeat (inferred).

## 3. Other spawn sites

**static**, *generated*. The builder reads each effect id from its
`ldr` literal and decodes each `bl` target:

| site | effect | id load | call → target | sound |
|---|---|---|---|---|
| guard spark | `0x21000c` | `0x02081d30` | `0x02081d40` → `0x0206c7fc` | (0x7a, 0x2b) SE_GUARD |
| clash spark (0x02080E5C) | `0x21000d` | `0x02080e7c` | `0x02080eec` → `0x0206c7fc` | (0x7a, 0x2a) SE_SOUSAI |
| clash spark (0x02080C70) | `0x21000e` | `0x02080c90` | `0x02080d00` → `0x0206c7fc` | (0x7a, 0x2a) SE_SOUSAI |
| grab text (block at 0x020826E8) | `0x230003` | `0x02082714` | `0x0208272c` → `0x0206c7fc` | — |
| 0x210012 (arm9) | `0x210012` | `0x0207e7a8` | `0x0207e7b0` → `0x0206c7fc` | — |
| 0x210012 (ov6) | `0x210012` | `0x02167178` | `0x02167188` → `0x0206c7fc` | — |
| KO-state load (ov6 0x0215C7C8) | `0x21000f` | `0x0215c7c8` | `0x0215c7d0` → `0x02159b8c`; its `0x02159ba0` → `0x02023894` (not the spawn call) | — |
| KO-state load (ov6 0x0215C4F8) | `0x210010` | `0x0215c4f8` | `0x0215c504` → `0x0215f6e4`; its `0x0215f73c` → `0x0206c7fc` | — |

- **Guard** (**measured** too): the `y_mash_ko` log plays `(0x7A, 0x2B)`
  five times from `lr 0x02081D50`, the return address of this site's sound
  call.
- **Grab text `0x230003`.** The block runs when bit `0x10` of `r1` is clear
  (`0x020826E8`). Its compare `[r3+0xE] == 7` (a halfword) picks flag bit 2
  or 4 of `[r2+0x40]` and the value in `sb`; it does **not** gate the
  spawn. Trigger TBD (`jus-wmqi.6.15`).
- **`0x210012`:** trigger TBD (`jus-wmqi.6.15`).
- **KO `0x210010`** (**static**; the builder checks the words it relies
  on). The KO state code passes it to `0x0215F6E4(r4, id, 0)`. That helper
  is itself a spawn wrapper: both its branches copy the id (r1) to r0 and
  call `0x0206C7FC`. With r2 = 0 (`0x0215C500`) it takes the `0x0215F718`
  path: spawn `0x210010` at x = `[[[[r4+0x1A8]+0x10]+0x5C]+0xC] >> 8`,
  y = `[… +0x10] >> 8`, flag 0. **inferred:** that point is the fighter's
  position (the pointer chain is not traced further).
- **KO `0x21000F`** (**static** for the calls). The KO state code passes it
  to `0x02159B8C`, which passes it on to
  `0x02023894([[r4+0xAC]+4], id, 0)`. That function looks the id up
  through `0x0201C170` in `[r0+0x68]` and, if it finds it, stores the result
  in `[r0+0x68]` (`0x020239B0`). No direct call to `0x0206C7FC` is on that
  path. **inferred:** it sets an existing effect object's animation to
  `0x21000F`.
- Whether, when and where each KO effect shows is TBD (`jus-wmqi.6.16`).
- **Dash dust `0x230000`** comes from the moves' own spawn tracks (§5), not
  from a fixed site.
- **Landing and guard break:** no site found. TBD (`jus-wmqi.6.13`).

## 4. Per-character hit effects (`chr/effect/<prefix>.bin`)

**static:** each file is 8-byte records (u32 effect id, u16 slot, u16
sound id); a hit index `0x40 + n` picks record `n`. The dispatcher reads
the table at `[ctx+0x14]` (ctx = `[[obj+0xC]+0x6C]`). **inferred:** that
`[ctx+0x14]` is this file (the record layout matches the dispatcher's
reads, and Kakashi's indices land on his own effects). Kakashi's
`na_b_04.bin`:

| index | effect | slot | sound id | notes |
|---|---|---|---|---|
| `0x40` | `0x060440` | 0 | `0x00` | the substitution log (visual) |
| `0x41`-`0x44` | `0x06046d`, `0x06046e`, `0x060470`, `0x06046f` | 1 | `0x0e` | in `na_b_04_4`; yellow lightning sparks (visual) |
| `0x45` | `0x06044a` | 1 | `0x0e` | Kakashi records 13-14 (down Y, per the researcher's move read); yellow electric spark (visual) |
| `0x46` | `0x06048d` | 1 | `0x0e` | in `na_b_04_5`; yellow lightning spark (visual) |

The slot picks a signed halfword at `ctx+0x18`; its value is the sound's
archive. **inferred:** slot 1 with sound `0x0e` plays `SE_HIT` from
`SEQ_BATTLE`. Where `ctx+0x18` is filled is TBD (`jus-wmqi.6.18`). Yusuke
has no file here; his records only use indices 0, 1 and 14 (`hit_records`).
All 66 files are in `vfx-sfx.json` `character_effect_tables`.

## 5. Per-move spawns and sounds

**static**, *generated* from each move's GN01 `GenerateID`/`2DPos` and its
SP01 NoteTrack. The specials' animations are in the base motion table too;
the koma archives hold only effect tables, so every row is here. Move
names come from anim-timing.md's captured moves, or from `label_src` (the kit, or a shared state anim id);
other rows have none.
A sound row with a category is sub 1 (`obj+0xA4`) or sub 2 (`obj+0xA6`),
whose archive is not a fixed id.

Each row in `vfx-sfx.json` `moves` has these keys:

| key | on | meaning |
|---|---|---|
| `anim`, `move`, `frames` | every row | the ALMT id; the move name, or null; the animation's length |
| `koma` | named rows | the special's koma set (4, 5 or 6), or null for the base kit. Rows with no move have no `koma`. The table's koma column shows it |
| `archive` | every row | the archive holding the animation (`chr/<prefix>.aar`). An addition to the original column list, kept so a row names its file |
| `why_no_move` | rows with no move | the reason: no capture ties the animation to a move. An addition to the original column list |
| `label_src` | named rows no capture named | where the name came from. Absent on a captured name. Labels without a box capture are inferred from move-slot labels; they are not live measurements. `INFERRED: state anim id …`: the id is a state animation (`anim_rows.py` `SHARED_STATES`, the dash `0x02`) that a capture names only for other fighters, so the name is carried over, not measured for this one. |
| `koma_archive` | specials | the koma archive (`chr/<prefix>_<koma>.aar`), where the spawn ids resolve (`effects` in the JSON, under that source). anim-timing.json's `koma_archive` is the same archive |
| `hits` | specials | `{record, kind, what, source, grade}`: the col records the special's hits use (record = the hit element's id − 0x100), each with its kind byte (record `+0x00`, also the clash tier; static) and where the record came from. `grade` is `measured` when a capture read that element, or `inferred: …` with its rule. The measured bytes match the moveData the captures read with GDB: C1 §9 for Kakashi 4, C2 §4 for Awakening, C3 §6 for the eye, C4 §2-4 for Yusuke 4 and 5. anim-timing.md §8 lists pass 2's records and grades |
| `spawns`, `sounds`, `undecoded_nodes` | every row | as the table shows; nodes the decoder could not read |

Kakashi (`na_b_04.amt`):

| anim | move | koma | spawns: frame → effect (x, y) | sounds: frame → id name | hits: record (kind) |
|---|---|---|---|---|---|
| `0x02` | dash | — | 0 → `0x230000` (0, 0) | 0 → `0x34` SE_DASH | — |
| `0x18` | — | — | — | 3 → obj+0xA4 `0x00`; 18 → `0x0d` SE_PLUSFEEL | — |
| `0x19` | — | — | 0 → `0x060446` (32, -52); 22 → `0x060447` (-38, -24); 34 → `0x060442` (0, 0) | — | — |
| `0x1a` | — | — | 24 → `0x060448` (25, -31) | — | — |
| `0x1e` | B | — | — | 8 → `0x14` SE_FURI | — |
| `0x1f` | Y | — | 0 → `0x060442` (0, 0); 6 → `0x230000` (0, 1) | 0 → `0x43` SE_DRON; 6 → `0x34` SE_DASH; 15 → `0x15` SE_HVYFURI | — |
| `0x20` | side B | — | 8 → `0x230000` (0, 1) | 5 → `0x34` SE_DASH; 8 → `0x18` SE_SWDFURI; 17 → `0x14` SE_FURI | — |
| `0x21` | side Y | — | 21 → `0x06044e` (45, -24); 29 → `0x06044e` (50, -24) | 21 → `0x22` SE_HVYKUNAI; 29 → `0x22` SE_HVYKUNAI | — |
| `0x22` | up B | — | 6 → `0x060443` (12, -24) | 6 → `0x43` SE_DRON | — |
| `0x23` | up Y | — | — | 0 → `0x34` SE_DASH; 15 → `0x14` SE_FURI; 33 → `0x18` SE_SWDFURI; 48 → `0x15` SE_HVYFURI | — |
| `0x24` | down B | — | 15 → `0x060443` (12, -24) | 2 → obj+0xA4 `0x00`; 15 → `0x43` SE_DRON | — |
| `0x25` | down Y | — | 22 → `0x060442` (12, 0) | 2 → obj+0xA4 `0x00`; 22 → `0x43` SE_DRON | — |
| `0x26` | air B | — | — | 9 → `0x18` SE_SWDFURI | — |
| `0x27` | air Y | — | 15 → `0x06043e` (34, -16) | 15 → `0x21` SE_KUNAI | — |
| `0x28` | — | — | 0 → `0x060442` (0, 0); 3 → `0x230000` (0, 1) | 0 → `0x43` SE_DRON; 3 → `0x34` SE_DASH; 12 → `0x15` SE_HVYFURI | — |
| `0x29` | X | 4 | 8 → `0x060460` (-36, -50) | 4 → obj+0xA4 `0x00`; 23 → obj+0xA6 `0x00` | 19 (4) |
| `0x2a` | up X | 4 | 15 → `0x06046a` (-38, -48); 50 → `0x06046c` (-38, -48) | 6 → obj+0xA4 `0x00` | 20 (4), 21 (4), 22 (4), 23 (4) |
| `0x2b` | X | 5 | 12 → `0x060481` (0, 0); 62 → `0x060482` (-8, -36); 93 → `0x060482` (-8, -36); 128 → `0x060482` (-8, -36); 171 → `0x060483` (48, -30); 179 → `0x060485` (48, -30); 187 → `0x060484` (48, -30); 12 → `0x060480` (0, 16); 16 → `0x060480` (0, 18); 20 → `0x060480` (0, 16); 24 → `0x060480` (0, 18); 28 → `0x060480` (0, 16); 32 → `0x060480` (0, 18); 36 → `0x060480` (0, 16); 40 → `0x060480` (0, 18); 44 → `0x060480` (0, 15); 48 → `0x060480` (0, 20); 62 → `0x230000` (0, 0); 93 → `0x230000` (0, 0) | 3 → obj+0xA4 `0x00`; 12 → `0x26` SE_ELECSHOCK; 20 → `0x26` SE_ELECSHOCK; 28 → `0x26` SE_ELECSHOCK; 36 → `0x26` SE_ELECSHOCK; 44 → `0x26` SE_ELECSHOCK; 63 → `0x35` SE_HVYDASH; 94 → `0x35` SE_HVYDASH; 129 → `0x35` SE_HVYDASH; 171 → `0x1e` SE_ELECFURI; 175 → `0x26` SE_ELECSHOCK; 183 → `0x26` SE_ELECSHOCK | 24 (5), 25 (5), 26 (5), 27 (5) |
| `0x2c` | up X | 5 | 15 → `0x060493` (-38, -48); 50 → `0x060487` (-38, -48) | 6 → obj+0xA4 `0x00` | 28 (4), 29 (4), 30 (4), 36 (4) |
| `0x2d` | X | 6 | 12 → `0x0604a1` (0, 0); 62 → `0x0604a2` (-8, -36); 95 → `0x0604a2` (-8, -36); 136 → `0x0604a2` (-8, -36); 185 → `0x0604a3` (44, -28); 193 → `0x0604a5` (44, -28); 201 → `0x0604a4` (44, -28); 12 → `0x0604a0` (0, 16); 16 → `0x0604a0` (0, 18); 20 → `0x0604a0` (0, 16); 24 → `0x0604a0` (0, 18); 28 → `0x0604a0` (0, 16); 32 → `0x0604a0` (0, 18); 36 → `0x0604a0` (0, 16); 40 → `0x0604a0` (0, 18); 44 → `0x0604a0` (0, 15); 48 → `0x0604a0` (0, 20); 62 → `0x230000` (0, 0); 95 → `0x230000` (0, 0); 136 → `0x230000` (0, 0) | 3 → obj+0xA4 `0x00`; 12 → `0x26` SE_ELECSHOCK; 20 → `0x26` SE_ELECSHOCK; 28 → `0x26` SE_ELECSHOCK; 36 → `0x26` SE_ELECSHOCK; 44 → `0x26` SE_ELECSHOCK; 62 → `0x35` SE_HVYDASH; 95 → `0x35` SE_HVYDASH; 136 → `0x35` SE_HVYDASH; 185 → `0x1e` SE_ELECFURI; 189 → `0x26` SE_ELECSHOCK; 197 → `0x26` SE_ELECSHOCK | 31 (5), 32 (5), 33 (5), 34 (5) |
| `0x2e` | up X | 6 | 24 → `0x0604a8` (10, -30) | 4 → obj+0xA4 `0x00`; 24 → obj+0xA6 `0x00`; 32 → obj+0xA6 `0x00` | 35 (4) |

Yusuke (`yh_b_01.amt`):

| anim | move | koma | spawns: frame → effect (x, y) | sounds: frame → id name | hits: record (kind) |
|---|---|---|---|---|---|
| `0x02` | dash | — | 0 → `0x230000` (0, 1) | 0 → `0x34` SE_DASH | — |
| `0x18` | — | — | 8 → `0x098146` (0, 1); 16 → `0x098146` (0, 1); 24 → `0x09814e` (0, 1); 32 → `0x09814e` (0, 1) | 8 → `0x46` SE_AURA_TAME; 16 → `0x46` SE_AURA_TAME; 24 → `0x46` SE_AURA_TAME; 32 → `0x46` SE_AURA_TAME | — |
| `0x19` | — | — | 12 → `0x09814c` (0, 7); 20 → `0x09814d` (0, -26) | 12 → `0x46` SE_AURA_TAME; 20 → `0x20` SE_HVYKOUDAN | — |
| `0x1e` | B | — | — | 4 → `0x14` SE_FURI | — |
| `0x1f` | Y | — | 8 → `0x098138` (0, 1); 16 → `0x230000` (0, 1) | 16 → `0x15` SE_HVYFURI | — |
| `0x20` | side B | — | 12 → `0x230000` (0, 1) | 12 → `0x15` SE_HVYFURI | — |
| `0x21` | side Y | — | 0 → `0x098139` (0, 1); 12 → `0x09813c` (0, 1); 20 → `0x09813d` (25, -30); 64 → `0x09813d` (25, -30); 105 → `0x09813d` (25, -30) | 0 → `0x46` SE_AURA_TAME; 20 → `0x20` SE_HVYKOUDAN; 64 → `0x20` SE_HVYKOUDAN; 105 → `0x20` SE_HVYKOUDAN | — |
| `0x22` | up B | — | — | 11 → `0x15` SE_HVYFURI | — |
| `0x23` | up Y | — | 4 → `0x098141` (0, 1) | 4 → `0x46` SE_AURA_TAME; 19 → `0x20` SE_HVYKOUDAN | — |
| `0x24` | down B | — | 11 → `0x230000` (0, 1) | 11 → `0x34` SE_DASH; 21 → `0x16` SE_OMOFURI | — |
| `0x25` | down Y | — | 32 → `0x230000` (0, 1) | 35 → `0x16` SE_OMOFURI | — |
| `0x26` | air B | — | — | 9 → `0x14` SE_FURI | — |
| `0x27` | air Y | — | 10 → `0x098145` (0, 1); 20 → `0x098148` (14, -21); 62 → `0x098148` (14, -21); 101 → `0x098148` (14, -21) | 4 → `0x46` SE_AURA_TAME; 20 → `0x20` SE_HVYKOUDAN; 62 → `0x20` SE_HVYKOUDAN; 101 → `0x20` SE_HVYKOUDAN | — |
| `0x28` | — | — | 0 → `0x098139` (0, 1); 4 → `0x09813c` (0, 1); 12 → `0x09813d` (25, -30) | 12 → `0x20` SE_HVYKOUDAN | — |
| `0x29` | X | 4 | 7 → `0x09813a` (0, 1); 19 → `0x09813c` (0, 1); 27 → `0x09813d` (25, -30); 27 → `0x098160` (-46, -49); 27 → `0x098161` (51, -51) | 7 → `0x46` SE_AURA_TAME; 27 → `0x23` SE_BEAM | 22 (4) |
| `0x2a` | up X | 4 | 6 → `0x09813b` (0, 0); 18 → `0x098164` (0, 0); 27 → `0x098165` (-6, 1); 35 → `0x098166` (-6, 1); 27 → `0x098163` (-28, -48); 27 → `0x230000` (0, 1) | 6 → `0x46` SE_AURA_TAME; 12 → `0x46` SE_AURA_TAME; 18 → `0x46` SE_AURA_TAME; 24 → `0x46` SE_AURA_TAME; 27 → `0x23` SE_BEAM | 23 (5), 24 (5) |
| `0x2b` | X | 5 | 7 → `0x09813a` (0, 1); 34 → `0x098182` (0, 1); 56 → `0x09813c` (0, 1); 64 → `0x09813d` (25, -30); 92 → `0x09813c` (0, 1); 100 → `0x09813d` (25, -30); 64 → `0x098180` (-46, -49); 100 → `0x098180` (-46, -49); 64 → `0x098181` (52, -51); 100 → `0x098181` (52, -51) | 7 → `0x46` SE_AURA_TAME; 13 → `0x46` SE_AURA_TAME; 19 → `0x46` SE_AURA_TAME; 25 → `0x46` SE_AURA_TAME; 31 → `0x46` SE_AURA_TAME; 37 → `0x46` SE_AURA_TAME; 43 → `0x46` SE_AURA_TAME; 64 → `0x23` SE_BEAM; 100 → `0x23` SE_BEAM | 25 (4), 26 (4) |
| `0x2c` | up X | 5 | 7 → `0x09813b` (0, 0); 19 → `0x098186` (0, -2); 31 → `0x098187` (0, 0); 37 → `0x098188` (-6, 1); 60 → `0x098189` (-6, 1); 37 → `0x098185` (-28, -48); 37 → `0x230000` (0, 1) | 7 → `0x46` SE_AURA_TAME; 13 → `0x46` SE_AURA_TAME; 19 → `0x46` SE_AURA_TAME; 25 → `0x46` SE_AURA_TAME; 31 → `0x34` SE_DASH; 37 → `0x23` SE_BEAM | 27 (5), 28 (5) |
| `0x2d` | X | 6 | 7 → `0x09813a` (0, 0); 36 → `0x09814f` (0, 1); 40 → `0x0981a2` (0, 1); 48 → `0x0981a4` (25, -30); 76 → `0x09814f` (0, 1); 80 → `0x098150` (0, 1); 88 → `0x0981a3` (25, -30); 48 → `0x0981a0` (-46, -49); 88 → `0x0981a0` (-46, -49); 48 → `0x0981a1` (50, -51); 88 → `0x0981a1` (50, -51); 48 → `0x098151` (0, 1); 88 → `0x098151` (0, 1) | 7 → `0x46` SE_AURA_TAME; 13 → `0x46` SE_AURA_TAME; 19 → `0x46` SE_AURA_TAME; 25 → `0x46` SE_AURA_TAME; 31 → `0x46` SE_AURA_TAME; 40 → `0x46` SE_AURA_TAME; 44 → `0x46` SE_AURA_TAME; 48 → `0x23` SE_BEAM; 88 → `0x23` SE_BEAM | 29 (4), 30 (4) |
| `0x2e` | up X | 6 | 7 → `0x230000` (0, 1); 47 → `0x230000` (0, 1); 61 → `0x0981a7` (0, 1); 89 → `0x230000` (0, 1); 116 → `0x0981a9` (11, -62); 64 → `0x0981a8` (42, -25); 116 → `0x0981aa` (9, -38) | 7 → `0x34` SE_DASH; 16 → `0x16` SE_OMOFURI; 50 → `0x16` SE_OMOFURI; 64 → `0x1f` SE_KOUDAN; 70 → `0x1f` SE_KOUDAN; 76 → `0x1f` SE_KOUDAN; 82 → `0x1f` SE_KOUDAN; 92 → `0x16` SE_OMOFURI; 116 → `0x23` SE_BEAM | 16 (5), 17 (5), 18 (5), 19 (5), 20 (5), 21 (4) |

Eve (`bc_b_01.amt`); the base ten and the four set moves carry their move (box-capture checks in
`anim_rows.py`, `anim-timing.json`; the set rows name their koma). Anim `0x18` is the Ultimate Action,
labelled `ULTIMATE` from the kit (`label_src`: no hit boxes, so no capture; its live run logged bridge
rows), and `0x02` is the dash, labelled by its state anim id (`label_src`, INFERRED). `0x19` and `0x28`
have no move:

| anim | move | koma | spawns: frame → effect (x, y) | sounds: frame → id name | hits: record (kind) |
|---|---|---|---|---|---|
| `0x02` | dash | — | 0 → `0x230000` (0, 1) | 0 → `0x34` SE_DASH | — |
| `0x18` | ULTIMATE | — | 21 → `0x07413c` (-19, -26); 24 → `0x07413d` (19, -41); 27 → `0x07413e` (-6, -59) | 42 → `0x34` SE_DASH | — |
| `0x19` | — | — | 10 → `0x07413d` (17, -48); 32 → `0x074140` (26, -32); 40 → `0x07413f` (11, -70); 8 → `0x07413c` (-23, -30); 12 → `0x07413e` (29, -29); 28 → `0x07413f` (-14, -19); 36 → `0x074141` (-18, -63) | — | — |
| `0x1e` | B | — | — | 8 → `0x14` SE_FURI | — |
| `0x1f` | Y | — | 16 → `0x07413b` (0, 1) | 16 → `0x19` SE_HVYSWDFURI | — |
| `0x20` | side B | — | — | 9 → `0x14` SE_FURI | — |
| `0x21` | side Y | — | — | 20 → `0x14` SE_FURI; 85 → `0x14` SE_FURI | — |
| `0x22` | up B | — | — | 11 → `0x1a` SE_TUKI | — |
| `0x23` | up Y | — | 29 → `0x07413c` (-16, -23); 33 → `0x07413e` (22, -42); 31 → `0x07413d` (11, 1) | 19 → `0x15` SE_HVYFURI | — |
| `0x24` | down B | — | 16 → `0x230000` (0, 1) | 20 → `0x16` SE_OMOFURI | — |
| `0x25` | down Y | — | 0 → `0x230000` (0, 1) | 34 → `0x16` SE_OMOFURI | — |
| `0x26` | air B | — | — | 7 → `0x14` SE_FURI | — |
| `0x27` | air Y | — | — | 14 → `0x15` SE_HVYFURI | — |
| `0x28` | — | — | 0 → `0x230000` (0, 1); 10 → `0x07413b` (0, 1) | 0 → `0x34` SE_DASH; 10 → `0x19` SE_HVYSWDFURI | — |
| `0x29` | X | 4 | 10 → `0x074139` (-35, -42); 11 → `0x230000` (-4, 1) | 11 → `0x14` SE_FURI; 13 → `0x14` SE_FURI; 15 → `0x14` SE_FURI; 17 → `0x14` SE_FURI; 19 → `0x14` SE_FURI; 21 → `0x14` SE_FURI | — |
| `0x2a` | up X | 4 | 16 → `0x074163` (30, -14); 32 → `0x074138` (-35, -49); 36 → `0x074164` (29, -51); 44 → `0x074164` (25, -40); 52 → `0x074164` (10, -33); 8 → `0x074160` (-1, 1); 12 → `0x074163` (-13, -64); 16 → `0x074165` (16, -52); 20 → `0x074163` (56, -64); 32 → `0x074164` (15, -37); 40 → `0x074164` (11, -51); 48 → `0x074164` (20, -45) | 12 → obj+0xA6 `0x00`; 32 → `0x21` SE_KUNAI; 36 → `0x21` SE_KUNAI; 40 → `0x21` SE_KUNAI; 44 → `0x21` SE_KUNAI; 48 → `0x21` SE_KUNAI; 52 → `0x21` SE_KUNAI | — |
| `0x2b` | X | 5 | 21 → `0x07413c` (28, -59); 29 → `0x07413e` (-3, -59); 33 → `0x230000` (0, 1); 25 → `0x07413d` (-21, -32); 32 → `0x07413c` (25, -9) | 12 → `0x14` SE_FURI; 32 → obj+0xA6 `0x00` | — |
| `0x2c` | up X | 5 | 14 → `0x074142` (0, -34); 32 → `0x074142` (0, -34); 13 → `0x07413a` (-45, -32) | 14 → obj+0xA6 `0x01`; 23 → obj+0xA6 `0x01`; 32 → obj+0xA6 `0x01`; 41 → obj+0xA6 `0x01`; 50 → obj+0xA6 `0x01` | — |

Train (`bc_b_02.amt`); no capture ties a row to a move yet. Only `0x18` (`ULTIMATE`, from the kit) and
`0x02` (dash, by its state anim id, INFERRED) carry a move, each with a `label_src`; the rest are empty:

| anim | move | koma | spawns: frame → effect (x, y) | sounds: frame → id name | hits: record (kind) |
|---|---|---|---|---|---|
| `0x02` | dash | — | 0 → `0x230000` (0, 1) | 0 → `0x34` SE_DASH | — |
| `0x18` | ULTIMATE | — | 12 → `0x074238` (37, -37); 45 → `0x074239` (37, -37); 45 → `0x07423f` (12, -33) | 12 → obj+0xA4 `0x02`; 45 → `0x14` SE_FURI | — |
| `0x19` | — | — | 4 → `0x074240` (0, 1); 32 → `0x07423a` (28, -49) | — | — |
| `0x1e` | — | — | — | 8 → `0x14` SE_FURI | — |
| `0x1f` | — | — | 4 → `0x230000` (-7, 1); 15 → `0x074243` (-7, 0) | 4 → `0x34` SE_DASH; 15 → `0x15` SE_HVYFURI | — |
| `0x20` | — | — | 0 → `0x230000` (0, 1) | 1 → `0x34` SE_DASH; 8 → `0x14` SE_FURI | — |
| `0x21` | — | — | 15 → `0x07423b` (43, -39); 66 → `0x07423b` (43, -39) | 15 → obj+0xA4 `0x00`; 66 → obj+0xA4 `0x00` | — |
| `0x22` | — | — | — | 9 → `0x14` SE_FURI | — |
| `0x23` | — | — | 14 → `0x07423c` (18, -51); 65 → `0x07423c` (18, -51) | 14 → obj+0xA4 `0x00`; 65 → obj+0xA4 `0x00` | — |
| `0x24` | — | — | 36 → `0x07423b` (43, -36) | 36 → obj+0xA4 `0x00` | — |
| `0x25` | — | — | 48 → `0x07423b` (43, -36) | 48 → obj+0xA4 `0x00` | — |
| `0x26` | — | — | — | 9 → `0x14` SE_FURI | — |
| `0x27` | — | — | 15 → `0x07423d` (36, -9); 76 → `0x07423d` (36, -9) | 15 → obj+0xA4 `0x00`; 76 → obj+0xA4 `0x00` | — |
| `0x28` | DREAM | — | 10 → `0x07423b` (43, -39); 18 → `0x07423b` (43, -39); 26 → `0x07423b` (43, -39); 76 → `0x07423b` (43, -39) | 10 → obj+0xA4 `0x00`; 18 → obj+0xA4 `0x00`; 26 → obj+0xA4 `0x00`; 76 → obj+0xA4 `0x00` | — |
| `0x29` | — | — | 0 → `0x074262` (38, -59); 8 → `0x074263` (-34, -32); 9 → `0x074260` (13, -61); 25 → `0x074260` (27, -19); 31 → `0x074260` (24, -57); 37 → `0x074260` (35, -22); 43 → `0x074260` (36, -55); 51 → `0x074264` (-28, -39); 8 → `0x074261` (13, -45); 25 → `0x074261` (18, -45); 29 → `0x074261` (31, -39); 51 → `0x074266` (37, -40); 52 → `0x074265` (44, -45); 87 → `0x07426a` (0, 1) | 8 → `0x26` SE_ELECSHOCK; 16 → `0x26` SE_ELECSHOCK; 25 → `0x26` SE_ELECSHOCK; 33 → `0x26` SE_ELECSHOCK; 41 → `0x26` SE_ELECSHOCK; 51 → `0x26` SE_ELECSHOCK; 55 → obj+0xA6 `0x00` | — |
| `0x2a` | — | — | 13 → `0x07426f` (0, 1); 35 → `0x07426d` (0, 1); 39 → `0x07426c` (-23, -31); 0 → `0x07426b` (-39, -42); 9 → `0x230000` (0, 1); 35 → `0x074270` (0, 1) | 9 → obj+0xA6 `0x01`; 35 → `0x16` SE_OMOFURI | — |
| `0x2b` | — | — | 0 → `0x074280` (-13, 1); 4 → `0x074282` (-2, -5); 23 → `0x074281` (-13, 1); 53 → `0x074286` (45, -37); 4 → `0x074283` (27, -44); 8 → `0x074283` (24, -48); 12 → `0x074283` (26, -45); 16 → `0x074283` (23, -47); 23 → `0x074285` (-39, -44); 53 → `0x074284` (48, -63) | 4 → `0x26` SE_ELECSHOCK; 10 → `0x26` SE_ELECSHOCK; 16 → `0x26` SE_ELECSHOCK; 23 → `0x26` SE_ELECSHOCK; 32 → `0x26` SE_ELECSHOCK; 41 → `0x26` SE_ELECSHOCK; 49 → `0x26` SE_ELECSHOCK; 53 → obj+0xA6 `0x00` | — |
| `0x2c` | — | — | 14 → `0x07428e` (0, 1); 62 → `0x07428a` (67, -44); 10 → `0x230000` (0, 1); 11 → `0x07428b` (-43, -50); 62 → `0x07428d` (5, -50); 10 → `0x07428c` (0, 0) | 10 → obj+0xA6 `0x01`; 62 → `0x11` SE_HVYSLASH | — |


Taikoubou (`hs_b_01.amt`); no capture or kit file ties a row to a move yet, so the move column is empty:

| anim | move | koma | spawns: frame → effect (x, y) | sounds: frame → id name | hits: record (kind) |
|---|---|---|---|---|---|
| `0x02` | dash | — | 0 → `0x230000` (0, 0) | 0 → `0x34` SE_DASH | — |
| `0x19` | — | — | 14 → `0x07c144` (0, 1); 72 → `0x07c145` (0, 1) | — | — |
| `0x1e` | — | — | 9 → `0x07c138` (38, -28) | 9 → `0x18` SE_SWDFURI | — |
| `0x20` | — | — | — | 9 → `0x18` SE_SWDFURI | — |
| `0x22` | — | — | 11 → `0x07c146` (12, -8) | 11 → `0x18` SE_SWDFURI; 15 → `0x18` SE_SWDFURI; 19 → `0x18` SE_SWDFURI; 23 → `0x18` SE_SWDFURI; 27 → `0x18` SE_SWDFURI | — |
| `0x26` | — | — | 0 → `0x07c15a` (0, 1); 12 → `0x07c15b` (0, 1); 28 → `0x07c15a` (0, 1); 38 → `0x220007` (9, 17) | 12 → `0x34` SE_DASH | — |
| `0x28` | — | — | — | 12 → `0x18` SE_SWDFURI | — |
| `0x29` | — | — | 6 → `0x07c142` (0, 0); 21 → `0x07c16f` (0, 1); 22 → `0x230000` (0, 1); 21 → `0x07c16e` (-44, -52) | 21 → `0x19` SE_HVYSWDFURI | — |
| `0x2a` | — | — | 19 → `0x07c142` (0, 0); 31 → `0x07c16c` (0, 0); 65 → `0x07c16c` (0, 0); 99 → `0x07c16c` (0, 0); 31 → `0x07c13e` (-38, -54); 65 → `0x07c13e` (-38, -54); 99 → `0x07c13e` (-38, -54) | 31 → obj+0xA6 `0x00`; 65 → obj+0xA6 `0x00`; 99 → obj+0xA6 `0x00` | — |
| `0x2b` | — | — | 6 → `0x07c142` (4, 0); 18 → `0x07c180` (-28, -52) | 18 → `0x18` SE_SWDFURI; 21 → obj+0xA6 `0x01` | — |
| `0x2c` | — | — | 4 → `0x07c142` (0, 0); 10 → `0x07c186` (52, -62); 16 → `0x07c143` (52, -62); 22 → `0x07c186` (-18, -88); 28 → `0x07c143` (-18, -88); 34 → `0x07c186` (-50, -18); 40 → `0x07c143` (-50, -18); 46 → `0x07c186` (64, -22); 52 → `0x07c143` (64, -22); 58 → `0x07c186` (22, -90); 64 → `0x07c143` (22, -90); 70 → `0x07c186` (-42, -56); 76 → `0x07c143` (-42, -56); 106 → `0x07c185` (0, 0); 153 → `0x07c185` (0, 0); 200 → `0x07c185` (0, 0); 247 → `0x07c185` (0, 0); 294 → `0x07c185` (0, 0); 341 → `0x07c185` (0, 0); 106 → `0x07c13f` (-52, -52); 153 → `0x07c13f` (-52, -52); 200 → `0x07c13f` (-52, -52); 247 → `0x07c13f` (-52, -52); 294 → `0x07c13f` (-52, -52); 341 → `0x07c13f` (-52, -52) | 4 → `0x46` SE_AURA_TAME; 16 → `0x46` SE_AURA_TAME; 28 → `0x46` SE_AURA_TAME; 40 → `0x46` SE_AURA_TAME; 52 → `0x46` SE_AURA_TAME; 64 → `0x46` SE_AURA_TAME; 76 → `0x46` SE_AURA_TAME; 88 → `0x46` SE_AURA_TAME; 106 → `0x21` SE_KUNAI; 153 → `0x21` SE_KUNAI; 200 → `0x21` SE_KUNAI; 247 → `0x21` SE_KUNAI; 294 → `0x21` SE_KUNAI; 341 → `0x21` SE_KUNAI | — |
| `0x2d` | — | — | 4 → `0x07c1a0` (-3, 1); 16 → `0x07c1a5` (0, -32); 31 → `0x07c1a3` (0, 1); 81 → `0x07c1a6` (16, 1); 105 → `0x07c1a8` (0, 1); 117 → `0x07c1a9` (54, -4); 151 → `0x07c1a9` (54, -4); 185 → `0x07c1a9` (54, -4); 0 → `0x07c1a4` (-54, -52); 16 → `0x07c1a1` (-32, -48); 17 → `0x07c1a2` (26, -24); 81 → `0x07c1a7` (0, 1); 89 → `0x07c1a7` (0, 1); 97 → `0x07c1a7` (0, 1) | 31 → `0x46` SE_AURA_TAME; 43 → `0x34` SE_DASH; 81 → `0x14` SE_FURI; 85 → `0x14` SE_FURI; 89 → `0x14` SE_FURI; 93 → `0x14` SE_FURI; 97 → `0x14` SE_FURI; 101 → `0x14` SE_FURI; 117 → `0x3a` SE_KABOOM | — |
| `0x2e` | — | — | 10 → `0x07c1aa` (0, 8); 10 → `0x07c141` (-52, -48); 28 → `0x07c1ab` (-36, -58); 29 → `0x07c1ac` (32, -20) | 36 → obj+0xA6 `0x00` | — |

Koma men (Red, `dt_b_01.amt`); Green `dt_b_02` (bank `0x0a82xx`) and Yellow `dt_b_03` (bank `0x0a83xx`) are the same rows with their own effect bank. No capture ties a row to a move, so the move column is empty:

| anim | move | koma | spawns: frame → effect (x, y) | sounds: frame → id name | hits: record (kind) |
|---|---|---|---|---|---|
| `0x02` | dash | — | 0 → `0x230000` (-9, 0) | 0 → `0x34` SE_DASH | — |
| `0x1e` | B | — | 10 → `0x0a8140` (33, -18) | 10 → `0x14` SE_FURI | — |
| `0x1f` | Y | — | — | 16 → `0x15` SE_HVYFURI | — |
| `0x20` | side B | — | 10 → `0x0a813e` (41, -26) | 10 → `0x14` SE_FURI | — |
| `0x21` | side Y | — | 16 → `0x230000` (0, 1) | 16 → `0x34` SE_DASH; 18 → `0x14` SE_FURI; 30 → `0x14` SE_FURI; 42 → `0x14` SE_FURI | — |
| `0x22` | up B | — | 12 → `0x0a8141` (1, -45) | 12 → `0x47` SE_JUMPFURI | — |
| `0x23` | up Y | — | — | 18 → `0x15` SE_HVYFURI | — |
| `0x24` | down B | — | — | 20 → `0x14` SE_FURI | — |
| `0x25` | down Y | — | — | 40 → `0x15` SE_HVYFURI | — |
| `0x26` | air B | — | — | 6 → `0x14` SE_FURI; 14 → `0x14` SE_FURI | — |
| `0x27` | air Y | — | 7 → `0x0a813f` (0, -18); 7 → `0x230001` (0, 1) | 0 → `0x34` SE_DASH; 7 → `0x29` SE_FLOORDWN | — |
| `0x28` | dream | — | — | 10 → `0x15` SE_HVYFURI | — |
| `0x29` | X | 4 | 16 → `0x0a8160` (0, 1) | 12 → `0x14` SE_FURI; 16 → `0x13` SE_HVYGAGHIT | — |
| `0x2a` | up X | 4 | 16 → `0x0a8161` (0, 0) | 16 → `0x23` SE_BEAM | — |

Notes:

- **measured:** Kakashi's live logs match the NoteTrack sounds: `neutral_y`
  plays `0x43`, `0x34`, `0x15` at raw frames 262, 268 and 277 (gaps 6 and
  9, like keys 0, 6 and 15), `neutral_b` and `dash_b` play `0x14`, and
  `forward_y` plays `0x22` twice. All come from `lr 0x02156A30`, the return
  of the op-4 call at `0x02156A2C`.
- **measured:** sub 1 plays from the fighter's own sequence archive. In
  `y_mash_ko` (active P1 Muhyo) the sub-1 return address `0x021569F8` plays
  `(0x1EF, 2)` (`SEQ_MR_B_01`) and `(0xF6, 0)` (`SEQ_JJ_B_01`, Jotaro). So
  for Kakashi, sub 1 id 0 would be `SEQ_NA_B_04` #0 `SE_CHR_KAKASHI_IN`
  (inferred; `jus-wmqi.6.18`).
- **Specials (capture C6, passes 1 and 2).** What each spawn shows and
  which sheet strip draws it: anim-timing.md §8. Pass 2's shot effects
  (Kakashi's pack `0x060495`, dogs `0x06048b`-`0x060492` and eye
  `0x0604a9`; Yusuke's `0x098162`, `0x098183` and `0x098184`) aren't in
  their animations' spawn keys either. The shot effects (the beam's
  `0x060461`-`0x060463`, the dogs' `0x060464`-`0x060469`, Awakening's
  finishing shot `0x0981ab`) are in none of these spawn keys; what spawns
  them is not traced. Yusuke's `0x0981a2` (X, anim frame 40) is the aura
  C2 saw around a long hold: an effect that loops, not a fighter strip.
- Yusuke's side Y is anim `0x28` (anim-timing.md). Anim `0x21` carries the
  same shots three times over 136 frames; what plays it is unknown.
- `0x230000` (dust, visual): every key of it in the tables above is at
  (0, 1), except Kakashi's dash, at (0, 0). Many share a frame with
  `SE_DASH` or a swing sound. **inferred:** it is the dust of a step or
  lunge (from the render and those sounds; what picks the frames is not
  traced).

Kenshin (`rk_b_01.amt`); no capture ties a row to a move yet, so the move column is empty:

| anim | move | koma | spawns: frame → effect (x, y) | sounds: frame → id name | hits: record (kind) |
|---|---|---|---|---|---|
| `0x02` | dash | — | 0 → `0x230000` (0, 1) | 0 → `0x34` SE_DASH | — |
| `0x18` | — | — | — | 8 → `0x34` SE_DASH | — |
| `0x19` | — | — | 0 → `0x09c146` (0, 1) | — | — |
| `0x1e` | — | — | — | 8 → `0x14` SE_FURI | — |
| `0x1f` | — | — | 16 → `0x09c14b` (0, 1) | 16 → `0x19` SE_HVYSWDFURI; 25 → `0x15` SE_HVYFURI | — |
| `0x20` | — | — | 8 → `0x09c147` (0, 1) | 8 → `0x18` SE_SWDFURI | — |
| `0x21` | — | — | 5 → `0x09c143` (0, 1); 17 → `0x09c149` (0, 1); 5 → `0x230000` (0, 1) | 5 → `0x35` SE_HVYDASH; 17 → `0x19` SE_HVYSWDFURI | — |
| `0x22` | — | — | 9 → `0x09c148` (0, 1) | 9 → `0x18` SE_SWDFURI | — |
| `0x23` | — | — | 16 → `0x09c14c` (0, 1) | 16 → `0x19` SE_HVYSWDFURI | — |
| `0x24` | — | — | 0 → `0x230000` (0, 1); 15 → `0x09c149` (0, 1) | 1 → `0x34` SE_DASH; 16 → `0x18` SE_SWDFURI | — |
| `0x25` | — | — | 35 → `0x09c144` (0, 1) | 0 → `0x44` SE_CHAKI; 35 → `0x49` SE_ETHIT | — |
| `0x26` | — | — | 8 → `0x09c14a` (0, 1) | 8 → `0x18` SE_SWDFURI | — |
| `0x27` | — | — | 10 → `0x09c14d` (0, 1); 20 → `0x09c14f` (0, 1); 20 → `0x09c145` (25, 0) | 10 → `0x19` SE_HVYSWDFURI; 20 → `0x29` SE_FLOORDWN | — |
| `0x28` | — | — | 0 → `0x09c143` (0, 1); 12 → `0x09c149` (0, 1); 0 → `0x230000` (0, 1) | 1 → `0x35` SE_HVYDASH; 12 → `0x19` SE_HVYSWDFURI | — |
| `0x29` | — | — | 0 → `0x230000` (0, 1); 12 → `0x09c160` (25, -28); 12 → `0x09c161` (14, -19); 12 → `0x09c13a` (-24, -36) | 1 → `0x34` SE_DASH; 12 → obj+0xA6 `0x00` | — |
| `0x2a` | — | — | 6 → `0x09c163` (37, -22); 47 → `0x09c164` (0, 1); 53 → `0x09c165` (45, -31) | 6 → `0x44` SE_CHAKI; 47 → `0x19` SE_HVYSWDFURI; 53 → `0x44` SE_CHAKI | — |
| `0x2b` | — | — | 0 → `0x09c138` (-27, -47); 54 → `0x09c181` (23, -29); 63 → `0x09c182` (0, 1); 0 → `0x230000` (0, 1); 54 → `0x09c13d` (-45, -39) | 1 → `0x34` SE_DASH; 54 → obj+0xA6 `0x00`; 80 → `0x44` SE_CHAKI | — |
| `0x2c` | — | — | 12 → `0x09c14d` (0, 1); 23 → `0x09c14f` (0, 1); 29 → `0x09c14e` (0, 1); 23 → `0x09c13b` (-36, -36); 38 → `0x09c13c` (-36, -36); 23 → `0x09c145` (23, 0) | 12 → `0x19` SE_HVYSWDFURI; 23 → `0x29` SE_FLOORDWN; 29 → `0x19` SE_HVYSWDFURI | — |
| `0x2d` | — | — | 0 → `0x09c138` (-33, -46); 16 → `0x09c1a5` (0, 1); 23 → `0x09c1a7` (0, 1); 26 → `0x09c1a6` (0, 1); 34 → `0x09c1a9` (0, 1); 0 → `0x09c139` (-49, -14); 16 → `0x09c1aa` (6, 1); 34 → `0x09c141` (-53, -34) | 16 → `0x19` SE_HVYSWDFURI; 30 → obj+0xA6 `0x01`; 60 → `0x44` SE_CHAKI | — |
| `0x2e` | — | — | 14 → `0x09c1a0` (0, 1); 26 → `0x09c14f` (0, 1); 32 → `0x09c1a1` (0, 1); 57 → `0x09c142` (-24, 1); 59 → `0x09c1a2` (0, 1); 65 → `0x09c143` (0, 1); 74 → `0x09c1a3` (0, 1); 80 → `0x09c1a4` (0, 1); 26 → `0x09c145` (28, 0); 26 → `0x09c13b` (-38, -28); 38 → `0x09c13c` (-38, -28); 59 → `0x09c13e` (-38, -28); 74 → `0x09c13f` (-38, -28); 89 → `0x09c140` (-38, -28) | 14 → `0x19` SE_HVYSWDFURI; 26 → `0x29` SE_FLOORDWN; 32 → `0x19` SE_HVYSWDFURI; 57 → `0x19` SE_HVYSWDFURI; 65 → `0x34` SE_DASH; 74 → `0x19` SE_HVYSWDFURI; 80 → `0x19` SE_HVYSWDFURI | — |

## 6. Effect animations and what the renders show

All effect animations with their cells and frame keys are in
`vfx-sfx.json` `effects` (12 sources: Kakashi's and Yusuke's base and
`_4`/`_5`/`_6` archives, and `comm_a`/`b`/`c`/`g`). Six special-move
effects key their `TextureID` and are skipped (`jus-wmqi.6.18`).

**The neutral Y puff is effect `0x42`, and it is the sheet's smoke row.**
**static:** `0x060442` is 18 frames and shows cells 24-30 at frames 0, 2,
4, 6, 9, 12 and 15 (so 2, 2, 2, 3, 3, 3, 3 frames each). Drawn, its seven
cells match the seven blobs of `jus_files/sprites/characters/Naruto/kakashi/Kakashi.png`
y 1430-1525 in order (the report's y 1446-1512 is the same row, trimmed).
Cell 25's shape matches pixel for pixel (`test_smoke_cell_25_is_pixel_exact_on_the_sheet`).
Its colours, compared as 5-bit values, match on 651 of 656 pixels
(`test_smoke_cell_25_colours_match_the_sheet`). Each of the other 5 sits
under one segment only, and 3 of them hold a grey that the cell's palette
does not have, so the sheet differs there, not the draw.
The mask overlap per cell is 1.0, 1.0, 1.0, 0.975, 0.982, 0.952 and 1.0.
The three below 1.0 differ by one pixel row or column.

**Draw order.** Where two segments of a sprite overlap, the later one in
the list is on top. **static** (checked against the sheet): cells 49 and 50
(effects `0x060446` / `0x060447`) have many such pixels, and every pixel
matches `Kakashi.png` in colour only in that order
(`test_overlap_order_matches_the_sheet`). With the first segment on top,
808 of 1004 and 1348 of 1628 match. Renders written before this rule was
fixed have wrong colours where segments overlap; rerun `effect_render.py`. Effect `0x43` is 20
frames with six cells (31, 32, 33, 34, 36, 35 at frames 0, 2, 5, 9, 13, 17).

Renders: `jus_files/extracted/vfx-sfx/render/<source>/<effect id>.png`
(one strip per animation, a red cross at the origin) and
`sheet_<dtx>_{2,4}bpp.png`. Written by `effect_render.py <source> --all
--sheets`. What they show (**visual**):

| effects | what they look like |
|---|---|
| `comm_a` `0x210000` / `0x210001` | small blunt burst / big starburst (orange/red) |
| `comm_a` `0x210002`-`0x210006` | a slash streak in five directions: flat, rising, up, falling, down |
| `comm_a` `0x210007`-`0x21000b` | the same five streaks with extra side sparks |
| `comm_a` `0x210013`-`0x21001e` | the blue versions of `0x210000`-`0x21000b` |
| `comm_a` `0x21000c` | a blue crescent (guard) |
| `comm_a` `0x21000d` / `0x21000e` | a four-point star then a blue orb and crescent / an expanding blue ring (clash) |
| `comm_a` `0x21000f` | a fiery explosion with a blue ring and a floor ripple |
| `comm_a` `0x210010` / `0x210011` | a burst then rising blue/orange orbs / a burst then scattered orange dots |
| `comm_a` `0x210012` | a white burst with debris flakes |
| `comm_b` `0x220010` | a cyan ice burst with shards |
| `comm_c` `0x23000e` / `0x23000f` | a small / a bigger explosion |
| `comm_c` `0x230014` | a yellow star burst |
| `comm_c` `0x230000` | a ground dust cloud |
| `comm_c` `0x230003` | the text ガシッ over a red/yellow impact |
| `comm_g` `0x240000`-`0x240022` | one-cell katakana sound words, white with a grey outline: 00 ドカッ, 01 ゴッ, 02 ガン, 03 ゴン, 04 ガスッ, 05 ガッ, 06 ドゴッ, 07 ガガッ, 08 ズガッ, 09 ドッ, 0a ドスッ, 0b ビシッ, 0c バシ, 0d バスッ, 0e ドン, 0f ドドン, 10 ドーン, 11 ガキッ, 12 ザシュ, 13 ズシャ, 14 シュバッ, 15 ザン, 16 ズバッ, 17 シュ, 18 バシュ, 19 ザクッ, 1a ダッ, 1b バッ, 1c ド, 1d ガ, 1e ゴ, 1f ドキッ, 20 ボン, 21 ズンッ, 22 ガーン |
| Kakashi `0x060438`-`0x06043d` | kunai variants |
| Kakashi `0x06043e` / `0x06043f` | a small yellow flame (air Y) / a yellow flash |
| Kakashi `0x060440` / `0x060441` | the substitution log / a spinning shuriken |
| Kakashi `0x060442` / `0x060443` / `0x060445` | ground smoke (neutral Y) / a centred smoke puff (up B, down B) / wide ground smoke |
| Kakashi `0x060444` / `0x060449` | the text ボン / the text ガブ |
| Kakashi `0x060446` / `0x060447` / `0x060448` | white speech-bubble capsules (win) / a small smoke wisp (lose) |
| Kakashi `0x06044a` / `0x06044e` | a yellow electric spark / a yellow spark ring (side Y) |
| Kakashi `0x06044b` / `0x06044c` / `0x06044d` | the summoned ninja dog (`e02`) / a small running dog / a Kakashi figure (`e03`) |
| Kakashi `0x06046d`-`0x060470`, `0x06048d` | yellow lightning sparks |
| Yusuke `0x098138`, `0x098139` | cyan charge starbursts |
| Yusuke `0x09813a`-`0x09813c`, `0x098147` | cyan energy gathering into an orb; the orb with a curved trail |
| Yusuke `0x09813d` | a shockwave arc |
| Yusuke `0x09813e`-`0x098140` | Reigun shots, small / medium / large |
| Yusuke `0x098141` / `0x098142`-`0x098144` | a charge then a rising comet / pellets |
| Yusuke `0x098145` / `0x098148` | a burst then curved trails / an arc swoosh |
| Yusuke `0x098146`, `0x09814e` | aura silhouettes |
| Yusuke `0x09814a`, `0x09814b` / `0x09814c` / `0x09814d` | a big diagonal comet / a ground pillar / a white-and-black text effect |
| Yusuke `0x098149` | not yet viewed. It now decodes cell 0 at frame 0 and cell 1 at frames 3 and 6 of texture `0x098141`. TextureID is constant; the cells come from BoundsIndex, its last track, which the old decoder clipped to no keys (before that fix: no drawable cells) |

## 7. Sound names (`SEQ_BATTLE`)

**static.** Sound category `0x7A` is sequence archive 122, `SEQ_BATTLE`
(FAT file 61, 4740 bytes, 87 sequences, all on bank 55 `BANK_SE_BATTLE`,
which uses the wave archives `WAVE_SE_BATTLE` and `WAVE_SE_STATIC`).
Category `0x17A` is `SEQ_NA_B_04` (Kakashi: `SE_CHR_KAKASHI_IN`,
`SE_CHR_KAKASHI_WATER`); `0xF6` is `SEQ_JJ_B_01` (Jotaro); `0x1EF` is
`SEQ_MR_B_01` (Muhyo); `0x78` is `SEQ_STATIC`. Yusuke's base form has no
archive of his own. The full `SEQ_BATTLE` table (*generated*):

| id | name | id | name | id | name | id | name |
|---|---|---|---|---|---|---|---|
| `0x00` | SE_READY | `0x01` | SE_KO | `0x02` | SE_FALLDOWN | `0x03` | SE_WARNING |
| `0x04` | SE_COUNTDOWN | `0x05` | SE_SUDDETH | `0x06` | SE_TIMEUP | `0x07` | SE_JSOUL_UP |
| `0x08` | SE_JSOUL_RCV | `0x09` | SE_SSOUL_UP | `0x0a` | SE_SSOUL_CHG | `0x0b` | SE_ICEBRK |
| `0x0c` | SE_MINUSFEEL | `0x0d` | SE_PLUSFEEL | `0x0e` | SE_HIT | `0x0f` | SE_HVYHIT |
| `0x10` | SE_SLASH | `0x11` | SE_HVYSLASH | `0x12` | SE_GAGHIT | `0x13` | SE_HVYGAGHIT |
| `0x14` | SE_FURI | `0x15` | SE_HVYFURI | `0x16` | SE_OMOFURI | `0x17` | SE_OMOHVYFURI |
| `0x18` | SE_SWDFURI | `0x19` | SE_HVYSWDFURI | `0x1a` | SE_TUKI | `0x1b` | SE_HVYTUKI |
| `0x1c` | SE_FIREFURI | `0x1d` | SE_HVYFIREFURI | `0x1e` | SE_ELECFURI | `0x1f` | SE_KOUDAN |
| `0x20` | SE_HVYKOUDAN | `0x21` | SE_KUNAI | `0x22` | SE_HVYKUNAI | `0x23` | SE_BEAM |
| `0x24` | SE_BEAM_LP | `0x25` | SE_BURNING | `0x26` | SE_ELECSHOCK | `0x27` | SE_FROZEN |
| `0x28` | SE_CRITICAL | `0x29` | SE_FLOORDWN | `0x2a` | SE_SOUSAI | `0x2b` | SE_GUARD |
| `0x2c` | SE_GCLASH | `0x2d` | SE_DCOMBO1 | `0x2e` | SE_DCOMBO2 | `0x2f` | SE_DCOMBO3 |
| `0x30` | SE_DCOMBO4 | `0x31` | SE_DCOMBO5 | `0x32` | SE_STARTSP | `0x33` | SE_APPEAR |
| `0x34` | SE_DASH | `0x35` | SE_HVYDASH | `0x36` | SE_CHRCHNG | `0x37` | SE_WALLCLS |
| `0x38` | SE_BOXCLS | `0x39` | SE_COINGET | `0x3a` | SE_KABOOM | `0x3b` | SE_POINTUP |
| `0x3c` | SE_CHG_ZOKUSEI | `0x3d` | SE_KAMEHAME | `0x3e` | SE_KHSYOUSHA | `0x3f` | SE_KHEND |
| `0x40` | SE_KIAITAME_LP | `0x41` | SE_BEAM2 | `0x42` | SE_BEAM2_LP | `0x43` | SE_DRON |
| `0x44` | SE_CHAKI | `0x45` | SE_MGUN | `0x46` | SE_AURA_TAME | `0x47` | SE_JUMPFURI |
| `0x48` | SE_PICUP | `0x49` | SE_ETHIT | `0x4a` | SE_STG_QUAKE | `0x4b` | SE_STG_BIGQUAKE |
| `0x4c` | SE_STG_FLAME | `0x4d` | SE_STG_ELECATK | `0x4e` | SE_STG_CANNON | `0x4f` | SE_SMALLKABOOM |
| `0x50` | SE_EAT | `0x51` | SE_OBJFALL | `0x52` | SE_ELECHIT | `0x53` | SE_JITEMGET |
| `0x54` | SE_OBJTHROW | `0x55` | SE_EFXFLASH | `0x56` | SE_EFXFLASH2 |  |  |

## 8. The SDAT stride fix

`sdat_inventory.py` read SYMB sequence-archive records at a 4-byte stride.
They are 8 bytes (a name offset and a sub-name-list offset). **static:**
at the old stride, entry 244 was taken for `SEQ_BATTLE`; it is really
`SEQ_SK_S_21_2` (`SE_SPT2_PHAO`, FAT 159, 116 bytes). With the fix,
435 of the 579 sequence archives are named (the old read said 291). The bank (`fat_0549_SBNK`) and wave (`fat_0650_SWAR`)
files extracted before were the right ones. The fixed tool's test
fails on the old stride. Re-extracted:
`jus_files/extracted/vfx-sfx/sdat/fat_0061_SSAR.ssar` (`SEQ_BATTLE`),
`fat_0293_SSAR.ssar` (`SEQ_NA_B_04`), `fat_0547_SBNK.sbnk`
(`BANK_SE_STATIC`) and `fat_0648_SWAR.swar` (`WAVE_SE_STATIC`).

## 9. WAV renders

`sfx_render.py` is a small offline player for these one-shot sequences:
SSEQ commands, SBNK instruments (PCM, PSG and noise), IMA-ADPCM and PCM
waves, ADSR, pan, pitch bend, sweep and LFO. Output:
`jus_files/extracted/vfx-sfx/render/wav/` (32768 Hz stereo 16-bit) plus
`manifest_battle.json`. **static** cross-check: after its loop fix, 85 of the
89 sequences in `SEQ_BATTLE` and `SEQ_NA_B_04` play the same notes, bank
and volume as ndspy 4.2.0's parse. The four that differ are three sequences that fall through into the
next one when their `if` is false (`SE_HVYSWDFURI`, `SE_KAMEHAME`,
`SE_KHSYOUSHA`; only `SE_HVYSWDFURI` is used, by Eve's Y and anim `0x28`, and the render follows the `if`
with variable 0x14 as the sequence itself sets it (1, then 0, so both compares are false and all 4 notes play), which is not checked against a live run) and the empty
`SE_CHR_KAKASHI_WATER`.

Rebuild the `SEQ_BATTLE` WAVs and `manifest_battle.json` by passing every
`SEQ_BATTLE` name in the table below to
`python3 scripts/analysis/sfx_render.py SEQ_BATTLE <names> --manifest
jus_files/extracted/vfx-sfx/render/wav/manifest_battle.json` (it overwrites the
manifest, so list them all; keep the committed manifest's row order, with the
16 `WAV_TARGETS` first). Add a sound to `WAV_TARGETS` in
`vfx_sfx_build.py` and rerun both. `SE_FLOORDWN` (`0x29`) is there for the
touchdown effect; `SE_HVYSWDFURI` (`0x19`) and `SE_TUKI` (`0x1a`) for Eve's Y and up B.

The set is the 16 key battle sounds, every `SEQ_BATTLE` sound Kakashi's
and Yusuke's NoteTracks name, and `SEQ_NA_B_04` (*generated*; "audible" =
time above −60 dBFS):

| archive | id | name | notes | audible s | peak dBFS | file |
|---|---|---|---|---|---|---|
| SEQ_BATTLE | `0x0e` | SE_HIT | 1 | 0.245 | -11.5 | `SEQ_BATTLE_0e_SE_HIT.wav` |
| SEQ_BATTLE | `0x0f` | SE_HVYHIT | 1 | 0.288 | -9.8 | `SEQ_BATTLE_0f_SE_HVYHIT.wav` |
| SEQ_BATTLE | `0x10` | SE_SLASH | 1 | 0.222 | -7.2 | `SEQ_BATTLE_10_SE_SLASH.wav` |
| SEQ_BATTLE | `0x11` | SE_HVYSLASH | 1 | 0.275 | -7.2 | `SEQ_BATTLE_11_SE_HVYSLASH.wav` |
| SEQ_BATTLE | `0x3a` | SE_KABOOM | 1 | 0.753 | -7.7 | `SEQ_BATTLE_3a_SE_KABOOM.wav` |
| SEQ_BATTLE | `0x2b` | SE_GUARD | 1 | 0.213 | -8.5 | `SEQ_BATTLE_2b_SE_GUARD.wav` |
| SEQ_BATTLE | `0x2a` | SE_SOUSAI | 2 | 0.245 | -10.7 | `SEQ_BATTLE_2a_SE_SOUSAI.wav` |
| SEQ_BATTLE | `0x34` | SE_DASH | 1 | 0.363 | -15.2 | `SEQ_BATTLE_34_SE_DASH.wav` |
| SEQ_BATTLE | `0x43` | SE_DRON | 1 | 0.442 | -7.2 | `SEQ_BATTLE_43_SE_DRON.wav` |
| SEQ_BATTLE | `0x14` | SE_FURI | 1 | 0.213 | -9.2 | `SEQ_BATTLE_14_SE_FURI.wav` |
| SEQ_BATTLE | `0x15` | SE_HVYFURI | 1 | 0.253 | -10.6 | `SEQ_BATTLE_15_SE_HVYFURI.wav` |
| SEQ_BATTLE | `0x01` | SE_KO | 22 | 1.959 | -4.6 | `SEQ_BATTLE_01_SE_KO.wav` |
| SEQ_BATTLE | `0x36` | SE_CHRCHNG | 1 | 0.289 | -8.6 | `SEQ_BATTLE_36_SE_CHRCHNG.wav` |
| SEQ_BATTLE | `0x29` | SE_FLOORDWN | 1 | 0.331 | -6.0 | `SEQ_BATTLE_29_SE_FLOORDWN.wav` |
| SEQ_BATTLE | `0x19` | SE_HVYSWDFURI | 4 | 0.369 | -9.2 | `SEQ_BATTLE_19_SE_HVYSWDFURI.wav` |
| SEQ_BATTLE | `0x1a` | SE_TUKI | 1 | 0.076 | -8.6 | `SEQ_BATTLE_1a_SE_TUKI.wav` |
| SEQ_BATTLE | `0x0d` | SE_PLUSFEEL | 11 | 0.617 | -8.9 | `SEQ_BATTLE_0d_SE_PLUSFEEL.wav` |
| SEQ_BATTLE | `0x18` | SE_SWDFURI | 1 | 0.146 | -9.3 | `SEQ_BATTLE_18_SE_SWDFURI.wav` |
| SEQ_BATTLE | `0x22` | SE_HVYKUNAI | 2 | 0.235 | -14.4 | `SEQ_BATTLE_22_SE_HVYKUNAI.wav` |
| SEQ_BATTLE | `0x21` | SE_KUNAI | 1 | 0.194 | -14.6 | `SEQ_BATTLE_21_SE_KUNAI.wav` |
| SEQ_BATTLE | `0x26` | SE_ELECSHOCK | 1 | 0.412 | -20.0 | `SEQ_BATTLE_26_SE_ELECSHOCK.wav` |
| SEQ_BATTLE | `0x35` | SE_HVYDASH | 1 | 0.513 | -15.2 | `SEQ_BATTLE_35_SE_HVYDASH.wav` |
| SEQ_BATTLE | `0x1e` | SE_ELECFURI | 8 | 0.359 | -8.7 | `SEQ_BATTLE_1e_SE_ELECFURI.wav` |
| SEQ_BATTLE | `0x46` | SE_AURA_TAME | 5 | 0.327 | -24.3 | `SEQ_BATTLE_46_SE_AURA_TAME.wav` |
| SEQ_BATTLE | `0x20` | SE_HVYKOUDAN | 3 | 0.661 | -12.1 | `SEQ_BATTLE_20_SE_HVYKOUDAN.wav` |
| SEQ_BATTLE | `0x16` | SE_OMOFURI | 1 | 0.315 | -9.9 | `SEQ_BATTLE_16_SE_OMOFURI.wav` |
| SEQ_BATTLE | `0x23` | SE_BEAM | 2 | 1.247 | -4.2 | `SEQ_BATTLE_23_SE_BEAM.wav` |
| SEQ_BATTLE | `0x1f` | SE_KOUDAN | 1 | 0.443 | -8.7 | `SEQ_BATTLE_1f_SE_KOUDAN.wav` |
| SEQ_BATTLE | `0x47` | SE_JUMPFURI | 2 | 0.707 | -7.5 | `SEQ_BATTLE_47_SE_JUMPFURI.wav` |
| SEQ_BATTLE | `0x13` | SE_HVYGAGHIT | 3 | 0.526 | -7.1 | `SEQ_BATTLE_13_SE_HVYGAGHIT.wav` |
| SEQ_BATTLE | `0x44` | SE_CHAKI | 1 | 0.278 | -9.7 | `SEQ_BATTLE_44_SE_CHAKI.wav` |
| SEQ_BATTLE | `0x49` | SE_ETHIT | 3 | 1.046 | -6.9 | `SEQ_BATTLE_49_SE_ETHIT.wav` |
| SEQ_NA_B_04 | `0x00` | SE_CHR_KAKASHI_IN | 4 | 0.474 | -19.2 | `SEQ_NA_B_04_00_SE_CHR_KAKASHI_IN.wav` |
| SEQ_NA_B_04 | `0x01` | SE_CHR_KAKASHI_WATER | 0 | silent | None | `SEQ_NA_B_04_01_SE_CHR_KAKASHI_WATER.wav` |

**Faithfulness.** Close, not exact. Sample steps use linear
interpolation. The volume curves come from a log formula, not the SDK's
tables. The LFO is a sine. There is no channel stealing. Random pitch
rolls take their midpoint. The wrapper `0x0207342C`'s own volume and pan
are not modelled. An emulator recording pass is `jus-wmqi.6.17`.
`SE_CHR_KAKASHI_WATER` is an empty sequence (only an end command), so
silence is right.

## 10. The researcher's claims, checked

| claim | result |
|---|---|
| 1. Dispatcher at ov6 `0x02153CE8`, callers, `+0x0E`/`+0x0F`, tables, `0x240000 \| idx` 32 px up, `[r8+0x14]` table | held (static, §2), but the shift is `0x20` spawn units; that they are px is TBD (§1). The per-character table is `[ctx+0x14]` with ctx = `[[obj+0xC]+0x6C]`; it being `chr/effect/<prefix>.bin` is inferred (§4). The sound for `≥ 0x40` comes from `ctx+0x18` by slot, not a fixed `0x7A` |
| 1. `+0x0E` is damage.md's class index; blunt/sharp lives there | held (static; the blunt/sharp names are inferred from the sound names) |
| 2. Guard `0x21000C` then `SE_GUARD`; clash `0x21000D`/`0x21000E` then `0x2A` | held (static, §3; guard also measured) |
| 2. KO loads of `0x21000F`/`0x210010` | held, and one call further (static, §3): the helper for `0x210010` spawns it (flag 0, at a point read through r4); `0x21000F` goes to a lookup (`0x02023894`), not the spawn call. What that lookup does is inferred; whether either shows is TBD |
| 2. `0x230003` "gated on `[rec+0xE]==7`" | overturned in part: the compare picks flag bits, not the spawn (§3) |
| 3. Kakashi GN01 spawns (Y, up B, down B, down Y, side Y, air Y, dash) | held, all seven (static, §5); the dash dust is at (0, 0). Key widths static; "spawn" inferred |
| 3. Yusuke Y and "side Y (`0x21`)" | Y held. The spawns listed for `0x21` are right, but Yusuke's side Y is anim `0x28` (§5) |
| 4. `0x42` = 7 cells (24-30) at 0, 2, 4, 6, 9, 12, 15, 18 frames; `0x43` = 6 cells | held (static) |
| 4. `0x42` is the sheet's smoke row | held (static: drawn cells match the sheet, §6) |
| 5. SDAT stride bug; the real `SEQ_BATTLE` is FAT 61, 4740 bytes | held and fixed (§8) |
| 6. Sound id → name map | held for every id listed (§7) |
| 7. NoteTrack keys 0, 6, 15, 19, 35 and sounds `0x43`, `0x34`, `0x15` via `0x02156A2C` | held (static and measured, §1, §5); event format decoded |

## 11. Open

- `jus-wmqi.6.13`: landing and guard-break effects and sounds.
- `jus-wmqi.6.14`: the spark pair select (orange vs blue).
- `jus-wmqi.6.15`: triggers of `0x230003` and `0x210012`.
- `jus-wmqi.6.16`: KO effects: when and where `0x210010` spawns, and what
  the `0x21000F` lookup does.
- `jus-wmqi.6.17`: record the battle sounds from the emulator.
- `jus-wmqi.6.18`: NoteTrack ops 0-3, where `obj+0xA4`, `obj+0xA6` and
  `ctx+0x18` are filled. STATIC: keyed TextureID and cumulative GN02+
  recovery are implemented by child `jus-wmqi.6.18.1`, described in section 12.
- `jus-wmqi.6.7`: map the hand-cut projectile strips to these effect cells
  (the renderer is done; the strip match is not).
- The spawn position units (pixels, x mirrored with facing?) are TBD; the
  `jus-wmqi.6.13`-`6.16` capture plans log `x`, `y` at the spawn call.

## 12. Keyed textures and GN02, 2026-10-18

STATIC: `jus-wmqi.6.18.1` decodes keyed TextureID tracks and recovers GN02
count blocks that the older independent-offset parser rejected. The exported
JSON retains existing cells, frame counts and sound data. These additions also
apply to the same previously undecoded fields in the other exported characters.

### TextureID layout

STATIC: a constant is one LE u32. Each key is LE `(u16 frame, u32 texture_id)`,
6 bytes, followed by a standalone `u16 0xffff`; trailing alignment bytes are
not another key. The low 24 bits identify a DSTX member, not an animation.
No flip, scale or position is packed into this key. Taikoubou's effect ALMT
property lists contain no separate scale or flip track. DSTX segment shape
bits 4/5 still supply per-segment x/y flips as described by `effect_render.py`.

STATIC native cross-check: TextureID registration at arm9 `0x020211E0..1F0`
installs descriptor `0x0209A660`. Its size callback at +0x68 is
`0x0204A788`, which returns 4. The generic keyed reader `0x0201E1E4`
computes `2 * (ceil(size/2) + 1)` at `0x0201E20C..220`, advances that stride
at `0x0201E268..288`, and passes key+2 to the setter at `0x0201E290..2A4`.
TextureID setter `0x0202507C` consumes the resource ID. The decoded ID and
framing are STATIC; actual drawn-frame selection remains UNMEASURED.

STATIC hex examples below use byte offsets in decompressed
`ChrArc.aar:chr/hs_b_01.aar/hs_b_01_e0.amt`. Fixtures independently compare
these literals to the archive bytes in `scripts/tests/test_tkfxdecode.py`.

| effect | offset | complete track hex | decoded frame -> texture |
|---|---|---|---|
| `0x07c14a` | `0x638` | `000041c10700 030045c10700 060043c10700 090041c10700 ffff 0000` | 0->07c141, 3->07c145, 6->07c143, 9->07c141 |
| `0x07c14c` | `0x6d6` | `000046c10700 040047c10700 ffff` | 0->07c146, 4->07c147 |
| `0x07c14d` | `0x770` | `000045c10700 040041c10700 070045c10700 ffff` | 0->07c145, 4->07c141, 7->07c145 |

STATIC export contract: changing textures retain `texture: null` and use
`texture_keys: [[frame, "0x......"], ...]` plus matching `dtx_keys` member
names. `skip: null` means the decoder supports the track. Consumers must use
these keys together with BoundsIndex cells. `render_anim` takes the union of
both key times and renders each interval's selected DSTX. Its held-key rule is
INFERRED for rendering, consistent with the generic native keyed reader;
synchronized raster output is UNMEASURED. Existing single-texture rows keep
their original shape. `0x07c1a7` is in `chr/hs_b_01_6.aar/hs_b_01_e6.amt`,
TextureID at `0x1d0`, keys 0/2/4/6 -> 07c1a1/07c1a0/07c1a1/07c1a0.

### GN02 layout and fields

STATIC: ALMT v2 nodes share the animation header. Start with `entry-0x20`;
read the LE u16 delta for node i at `entry+8+2*i`, add each nonzero delta to
the running base, and omit zero-delta nodes without resetting that base.
The resulting base points to `u8 constant_count, u8 keyed_count`, then the
property-index bytes, absolute-even alignment, then LE u16 track offsets
relative to that count block. GN02 is the third node, not a distinct record
type. The native reader accumulates deltas at arm9 `0x0201F1B8..1DC`, omits
zero slots at `0x0201F200..208`, and resolves track offsets at
`0x0201F6BC..728`.

STATIC node-framing rule in `anim_events.anim_events` (AEFIX, same rule as the
support-program path; the walk matched 372/372 support records). SP01 keeps
its legacy `full_entry` start and is the walk origin. Every other node uses
the legacy start only while its tracks equal the block the native walk gives
that label. A missing start, a wrong start (legacy `ok` is not trusted: an
`ok` node can frame an empty block, ds_b_01 0x1a GN02) and swapped labels
(gt_b_02 0x29 GN01/GN02) are all recovered with the walk, and the recovered
node also carries `parent_link`, `effect_flags` and `draw_prio` on its spawns.
If the walk cannot run (v1 ALMT, boundary check fails) the legacy node is
kept only when `full_entry` marked it `ok`; a node neither path can frame is
listed in `undecoded_nodes`, and a node whose tracks fail while decoding adds
a `node_errors` entry. `full_entry` parses keyed tracks at the
per-property widths in `move_records.KEY_STRIDE` (GenerateID, TextureID and the
other 4-byte values at 6, CollisionRect at 10), and parses node 0's tracks up
to the next node's native count block, not to that node's legacy start, so
SP01's last track is no longer cut short (node `end` stays the legacy boundary); `Almt.native_nodes` frames every node the
loader's way (field_closure.witness.md "ALMT node repair"). Result over the 1075 roster AMTs: 25 animation
records changed (every one a spawn-count change, 4 to 29); db_b_06/07/08 and
op_b_07 anim 0x19 GN02 are no longer undecoded. Tests:
`CumulativeRecoveryTest` and `BadNodeTest` in `scripts/tests/test_anim_events.py`.

STATIC: GenerateID uses the same `(u16 frame, u32 id)` stride 6 and `ffff`
terminator. Descriptor `0x02099E50`, registered at `0x02015C54..6C`, has
size callback `0x0204A788` and custom key reader `0x02016220`. It computes
stride 6 at `0x02016248..254`, ignores zero IDs, requires the current frame
to equal the key frame, assembles both ID halves and calls node vtable+0x124
at `0x020162C4..0x02016308`. Effect GN vtable `0x0209E114` routes that slot
to `0x0206CA8C`, which loads the effect through `0x02023894` at `0x0206CB88`.

STATIC hex examples below are in decompressed
`ChrArc.aar:chr/hs_b_01.aar/hs_b_01.amt`. GenerateID examples include the
zero initialization key, which is omitted from exported spawns.

| body anim | header delta words | GN02 count block | GenerateID offset and complete hex | decoded nonzero keys |
|---|---|---|---|---|
| `0x29` | `002e 010c 0058` | `0x1a3a` | `0x1a58`: `000000000000 15006ec10700 ffff 0000` | f21 -> 07c16e |
| `0x2a` | `002e 0202 0054` | `0x1ccc` | `0x1cea`: `000000000000 1f003ec10700 41003ec10700 63003ec10700 ffff` | f31/65/99 -> 07c13e |
| `0x2e` | `002e 03b2 002e` | `0x32ea` | `0x332e`: `000000000000 0a0041c10700 1c00abc10700 1d00acc10700 ffff` | f10 -> 07c141, f28 -> 07c1ab, f29 -> 07c1ac |

STATIC: recovered spawns add optional `parent_link`, `effect_flags` and
`draw_prio` values sampled at the GenerateID frame. All exported frame, ID,
x/y and these three numeric fields have grade STATIC. `2DPos` is a constant
s16 pair or keyed `(u16 frame, s16 x, s16 y)`. ParentLink is a byte boolean
with alignment padding, keyed stride 4. EffectFlags is u16, keyed stride 4;
DrawPrio is u32, keyed stride 6.
For anim29, constant bytes at `0x1a4c` are `d4ff ccff` = (-44,-52),
ParentLink at `0x1a50` is `0100`, DrawPrio at `0x1a52` is `00e00700`,
and EffectFlags at `0x1a56` is `0200`.

STATIC attachment semantics: ParentLink descriptor `0x02099DA4` uses size
callback `0x0204AAD8`, which returns 1. Setter `0x02016348..358` reads a
byte, normalizes nonzero to 1 and writes boolean node+0x78. EffectFlags registration
`0x0206C404..438` selects u16 descriptor `0x02099640`, field offset 0x80;
its setter `0x0202CF54` stores a halfword. Effect spawn `0x0206CB8C..BC4`
checks flag bit 0 before mirroring the x offset with owner facing and bit 1
before inheriting owner facing. ParentLink gates the attachment branch at
`0x0206CBC4..BE0`, which passes node+0x44 as parent to vtable+0xd4.
Thus flags=2 still mirror x but suppress facing inheritance; flags=3
suppress both. The parent's identity as the moving fighter and the resulting
rendered pose are INFERRED until a runtime parent/pixel trace confirms them.
No separate scale field occurs in these GN02 tracks. DrawPrio's numeric
value is STATIC; its full renderer ordering semantics are UNMEASURED.

MEASURED capture births must be compared on each trial's timeline, not
silently equated with the authored frames above. The existing
effect-anim.json
contains playhead-class summaries only. Per-trial births are in the adjacent
`derived-*.json`; raw ANIM/FXO records are under
`<CAPTURE_BUNDLE>`. Branches, repeated phases and child effects
can move births away from the authored frame. Drawn-frame selection, precise
parent following and the unobserved `0x07c157` still need a targeted capture
if runtime parity is required. Static extraction itself needs no new capture.

STATIC downstream maintenance: regeneration of `feature-census.json` exposes
GN03/GN04 and removes obsolete undecoded-node keys. The kit feature-status
catalog classifies the new decoded keys as out-of-band VFX. Regenerated kits
remove only stale `node.undecoded.GNxx` warning rows, with all gameplay fields
unchanged. Runtime validation is tracked by `jus-wmqi.6.18.2`.
