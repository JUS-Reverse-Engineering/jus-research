# Combat Data Format Specifications

Binary format specifications for Jump Ultimate Stars combat data files.

> **Trust rule (2026-09-04).** Offsets and strides here are verified against the
> files. Field *names* are the original exporter's labels unless a row cites a
> tracker item or a `docs/confirmed-facts/` section; treat unlabelled names as guesses.
> Where this page and `docs/confirmed-facts/` disagree, confirmed-facts wins.

## Overview

Combat data is split across multiple files:

| File | Location | Contents |
|------|----------|----------|
| `chr_b.bin` | `bin/` | Battle character stats (74 characters) |
| `chr_s.bin` | `bin/` | Support character stats |
| `jpower.bin` | `bin/` | Koma evolution price table (311 rows; `jus-jpower-koma-price-table-uh9o`) |
| `*.bin` | `ChrBin.aar/chr/col/` | Per-character collision/hitbox data |
| `*.bin` | `ChrBin.aar/chr/shot/` | Projectile parameters |
| `*.bin` | `ChrBin.aar/chr/ai/` | AI behavior parameters (LZSS compressed AIPM) |

---

## chr_b.bin - Battle Character Stats

**Record Size:** 60 bytes
**Total Records:** 74 battle characters
**Endianness:** Little-endian

### Record Structure

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| 0x00 | 1 | u8 | formType | 0=Normal, 1=Powered, 2=Transformed |
| 0x01 | 1 | u8 | tier | Damage/jump tier (1–3); indexes the jump-impulse table (`physics.md` §6.4) |
| 0x02 | 1 | u8 | walkClass | 2–6; indexes the walk-accel table `0x02171108` (`physics.md` §6.2, `jus-movement-speed-runtime-0luv`). Not a koma size |
| 0x03 | 5 | u8[5] | abilityIds | Five sparse on-disk ability ids, zero = empty (`helpers.md` §4, `jus-ondisk-ability-list-at-chrb-0x03-kfc`). The old `charId`/`flags` labels for `+0x03`/`+0x04` are retired |
| 0x08 | 2 | u16 | statA | Primary base stat |
| 0x0A | 2 | u16 | statB | Secondary base stat |
| 0x0C | 2 | u16 | statC | Unknown. **Not** walk speed: the movement path never reads it (`physics.md` §6.2) |
| 0x0E | 2 | u16 | classId | Character class (high byte=major, low=sub) |
| 0x10 | 4 | u16+u16 | combatStat1 | Value + modifier pair |
| 0x14 | 4 | u16+u16 | combatStat2 | Value + modifier pair |
| 0x18 | 4 | u16+u16 | combatStat3 | Value + modifier pair |
| 0x1C | 4 | u16+u16 | combatStat4 | Value + modifier pair |
| 0x20 | 4 | u16+u16 | combatStat5 | Value + modifier pair |
| 0x24 | 12 | u8[12] | battleParams | Movement, weight, timing, damage multipliers |
| 0x30 | 12 | u16[6] | textIds | Indices into chr_b_t.bin for names/moves |

### Notes

- **classId → jpower block** (`jpower_block_index = classId & 0xFF`, high byte
  1 or 2) was the exporter's reading (`docs/research/jpower-Mapping.md`) and is void:
  jpower.bin is not battle data
  (`jus-jpower-koma-price-table-uh9o`). The runtime damage path reads the base byte at chr/col `+4`
  (`damage.md` §1); the reading `jpower.damage1 / 5` (`jus-base-2-is-jpower-damage1-10-mse`) is retracted by
  `jus-jpower-retraction-cguk`.
- Combat stat modifiers: 0=none, 256/257=type1, 512/514=type2
- `textIds` reference strings in chr_b_t.bin (Shift-JIS encoded)
- **battleParams does not contain weight or walk speed.** See the [current
  physics reference](../confirmed-facts/physics.md) §4.1 and §6.2 for the
  runtime interpretation.

---

## Collision Files (col/*.bin) - Hitbox Data

**Record Size:** 20 bytes
**Endianness:** Little-endian
**File naming:** `{series}_{type}_{variant}.bin` (e.g., `db_b_01.bin` = Dragon Ball Battle Character 01)

### Record Structure

| Offset | Size | Type | Field | Description |
|--------|------|------|-------|-------------|
| 0x00 | 1 | u8 | collisionType | See collision types below |
| 0x01 | 1 | u8 | subType | Move/animation index |
| 0x02 | 1 | u8 | extFlags | Extended flags (0-3) |
| 0x03 | 1 | s8 | statusRaw | Signed lane value: positive is staged to work byte `+0x172`, negative to `+0x173` (arm9 `0x0208169C`). Exporter label was `projectileId`; the id's meaning is not established here (`jus-chrcol-03-status-lanes-4exo`) |
| 0x04 | 1 | s8 | damage_raw | Signed base damage, read with `ldrsb` at arm9 `0x02082428` with no table lookup ([damage.md](../confirmed-facts/damage.md) §1 and §2.1). Exporter label was `frameStart`; it is not an activation frame |
| 0x05 | 1 | s8 | spDrain | SP drain per contact, 1/100 bar; the byte `<< 8` is added into a per-cell sum (arm9 `0x020812A0`, [damage.md](../confirmed-facts/damage.md) `+0xEC`). Exporter label was `durationMult` |
| 0x06 | 1 | u8 | reserved0 | Always 0 |
| 0x07 | 1 | s8 | hitstunAdd | Signed add into work byte `+0x171`, an add term of the hitstun formula `clamp(M[0x171] + 0x14 + table, 0x10, 0x3C)` (arm9 `0x02081300`; read at ov6 `0x0215AD34`, [physics.md](../confirmed-facts/physics.md) §4.5). Exporter label was `hitModifier` |
| 0x08 | 1 | s8 | offsetX | Hitbox X position (signed) |
| 0x09 | 1 | u8 | offsetY | Hitbox Y position |
| 0x0A | 1 | u8 | positionFlags | Position modifiers |
| 0x0B | 1 | u8 | reserved1 | Always 0 |
| 0x0C | 1 | s8 | knockbackX | Knockback X base; impulse = `kbX × 128 × M × F` raw (`damage.md` move-data block `+0x0C`). Exporter label was `width` |
| 0x0D | 1 | s8 | knockbackY | Knockback Y base (`damage.md` `+0x0D`). Exporter label was `height` |
| 0x0E | 1 | u8 | classIndex | Damage-gate class index: low 6 bits = class 0..15, `0x3F` = none, bit 7 a separate flag (`damage.md` `+0x0E`, `jus-class-index-is-damageflags-mx5`). Exporter label was `damageFlags`; it is not a jpower index and not a flags byte |
| 0x0F | 1 | u8 | knockback | Knockback force (0xFF=terminator) |
| 0x10 | 1 | u8 | hitTier | Attack strength: 0=passive, 1=light, 2=medium, 3=heavy |
| 0x11 | 1 | u8 | hitProperties | 0=default, 1=force blunt damage |
| 0x12 | 2 | u8[2] | reserved | Always 0 |

Offsets `+0x03`, `+0x04`, `+0x05`, `+0x07`, `+0x0C`, `+0x0D` and `+0x0E` carry consumer-based labels; the rest are exporter
labels. Roster-wide statistics and the live 20-byte dumps are in
`docs/confirmed-facts/collision.md` (on-disk format bullet).

### Collision Types

| Value | Name | Description |
|-------|------|-------------|
| 0 | Terminator | End of record list |
| 2 | Attack | Standard attack hitbox |
| 3 | Extended | Extended/melee hitbox |
| 4 | Projectile | True projectile (travels across screen) |
| 5 | Summon | Summoned entity or spawned hitbox |

### SubType Values

| Value | Name | Description |
|-------|------|-------------|
| 0 | Special | Special case |
| 1 | Jab/Light | B button attacks |
| 2 | Combo | Follow-up attacks |
| 5 | Launcher | Launching attacks |
| 6 | Aerial | Air attacks |
| 7 | Heavy | Y button attacks |

---

## jpower.bin - Koma Evolution Price Table

Not battle data. Earlier revisions of this page read it as move/power parameters
(`damage1` etc.); that reading is retracted by `jus-jpower-retraction-cguk`. Layout and provenance:
`jus-jpower-koma-price-table-uh9o` (static; Keshire's `jus_formats/jpower.py`, cross-checked against our ROM).

**Row Size:** 304 bytes (0x130)
**Total Rows:** 311
**Endianness:** Little-endian
**Loader:** ov05 `0x02165314` (`JPowerData_Create`); readers per Keshire's trace, not re-read here: ov05 `0x021653AC` (cell address), `0x021646F4` (award dispatch), `0x02164458` (six resource costs). "Nothing in ARM9, ov06 or ov11 reads it" is inferred from the single loader.

### Row Structure

| Offset | Size | Section |
|--------|------|---------|
| 0x00 | 4 | root koma index |
| 0x04-0x12F | 15 x 0x14 | 15 cells, grouped 5 x 3 slots (Keshire's grouping) |

(4 + 15 x 0x14 = 0x130 exactly.)

### Cell (0x14 bytes)

Words: `[kind, 1, koma id, 0, cost x6]`. The second word is usually 1, not always; the kind word takes values such as 6403 and 6146.

Example: row 146 (root koma 379) has cells for koma 380, 382, 381, 383, 384 and 385, with first non-zero costs 35, 150, 60, 300, 400 and 500: an evolution tree with rising prices.

The old "main record / modifier sub-record / extra data" field tables (id, type1, damage1-3, hitstun, link fields) were a misparse of these rows and are removed.

---

## Shot Files (shot/*.bin) - Projectile Data

**Record Size:** 32 bytes
**Endianness:** Little-endian

Referenced by negative `projectileId` values in collision data.
**REFUTED as stated (2026-08-14)** — negative `ProjectileId` (collision offset `0x03`, `sbyte`) does
*not* index the owning character's shot records: 2.4% in-bounds, and the set relation fails in both
directions. The negatives occupy a contiguous −18..−34 band. The 32-byte stride below is confirmed.
See `../research/archive/findings/shot-data-and-projectileid-refuted.md`.
The follow-up "global 17-entry table" reading is **also REFUTED** — no file in any `chr/`
subdirectory has 17 records at any of six strides. The field is a per-character **selector** (92 of
120 users have exactly one distinct value) sitting on `CollisionType` 4/5 records (92% of negatives);
PLAUSIBLE that a code switch dispatches on it. See
`../research/findings/projectileid-is-a-selector-not-an-index.md`.

**Field offsets (32-byte record), from a profile of all 1258 records** — previously undocumented.
`+0x0C`/`+0x10`/`+0x14` appear to be a 3-element array of `{u16 magnitude, u16 tag}` (PLAUSIBLE);
`+0x18`/`+0x1A` are effectively dead (>99% zero).

### Shot Types

| Value | Type | Description |
|-------|------|-------------|
| 0x00 | Projectile | True projectile that travels |
| 0x0D | Summon | Summoned entity |
| High duration | Trap | Persistent/trap projectile |

---

## Export tooling

The C# `JUS.CLI` exporter left this repo at the 2026-08-21 split. Use:

```bash
# chr_b (and, with --col-dir/--jpower, collision + jpower) to JSON
python3 scripts/extract_character_data.py --chr-b <chr_b.bin> --output <dir>

# already-exported JSON
ls jus_files/exported_combat/
```
