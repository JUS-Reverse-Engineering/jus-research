# jpower.bin Mapping

> **Superseded labels (E0 roster pin, 2026-10-18):** the chr_b -> file labels in this doc's tables predate the measured mapping (for example chr_b 2 is Vegeta on db_b_03, 3 Vegeta (SSJ) on db_b_04, 8 Piccolo on db_b_09, 9 Frieza on db_b_10, 11 Vegetto on db_b_12). Current pairing: `docs/research/feel-captures/2026-10-18-e0-roster/roster_reconciled.json`. Kept as recorded.

## chr_b.bin → jpower.bin Linkage (CONFIRMED)

**Discovery:** The `classId` field in chr_b.bin links to jpower.bin ATTACK
blocks.

**Formula:**

```
jpower_block_index = classId & 0xFF  // Low byte of classId
```

### How It Works

1. chr_b.bin has 74 entries (one per battle character file)
2. jpower.bin has 311 entries organized into 43 ATTACK blocks separated by DATA
   entries
3. Each chr_b entry's `classId` low byte points to a jpower ATTACK block
4. Multiple characters can share the same jpower block (same moveset)

### Example: Dragon Ball Characters

| chr_b | File                  | classId | Low Byte | jpower Block | Block Damages         |
| ----- | --------------------- | ------- | -------- | ------------ | --------------------- |
| 0     | db_b_01 (Goku)        | 256     | 0        | Block 0      | [7,7,7,7,7,7,7,14,14] |
| 1     | db_b_02 (Goku SSJ)    | 256     | 0        | Block 0      | [7,7,7,7,7,7,7,14,14] |
| 2     | db_b_03 (Vegetto)     | 257     | 1        | Block 1      | [7,7]                 |
| 3     | db_b_04 (Vegeta)      | 257     | 1        | Block 1      | [7,7]                 |
| 8     | db_b_09 (Gotenks SSJ) | 516     | 4        | Block 4      | [7,7,7,28]            |
| 9     | db_b_10 (Piccolo)     | 261     | 5        | Block 5      | [7,3,2,1]             |
| 10    | db_b_12 (Majin Buu)   | 262     | 6        | Block 6      | not tabulated here    |
| 11    | db_b_03 (Vegetto, file ⚠ per chr_b doc) | 256 | 0 | Block 0 | [7,7,7,7,7,7,7,14,14] |

**Observations:**

- Goku and Goku SSJ share Block 0 and have the same moveset ✓
- ~~Majin Buu also uses Block 0 but has a DIFFERENT moveset than Goku~~ **VOID 2026-10-13:** Buu is chr_b row 10, classId 262, Block 6. The Block 0 partner of Goku is Vegetto (row 11, classId 256); no moveset comparison is recorded for that pair.
- Vegetto and Vegeta share Block 1 but have different movesets
- **Sharing a jpower block ≠ sharing a moveset**

### Example: One Piece Characters

| chr_b | File               | classId | Low Byte | jpower Block | Block Damages             |
| ----- | ------------------ | ------- | -------- | ------------ | ------------------------- |
| 12    | op_b_01 (Luffy)    | 521     | 9        | Block 9      | [57,7,7,7,7,7,7,7,7,7,14] |
| 13    | op_b_02 (Zoro)     | 522     | 10       | Block 10     | [7,7,7]                   |
| 14    | op_b_03 (Sanji)    | 523     | 11       | Block 11     | [7,7,7,7,7]               |
| 15    | op_b_04 (Nami)     | 524     | 12       | Block 12     | [7,7]                     |
| 16    | op_b_05 (Robin)    | 525     | 13       | Block 13     | [7,7,7]                   |
| 17    | op_b_06 (Franky)   | 270     | 14       | Block 14     | [57]                      |
| 18    | op_b_07 (Gear 2)   | 521     | 9        | Block 9      | [57,7,7,7,7,7,7,7,7,7,14] |
| 19    | op_b_08 (PCT Nami) | 524     | 12       | Block 12     | [7,7]                     |

**Observations:**

- Luffy and Gear 2 Luffy share Block 9 but have different files (`op_b_01` vs `op_b_07`)
- Nami and PCT Nami share Block 12 but have different files (`op_b_04` vs `op_b_08`)
- Robin (16) takes Block 13 and Franky (17) Block 14 (single entry `[57]`)

> Names corrected 2026-10-13: this table paired each chr_b row with the character of the same file number (`op_b_02` = Gear 2, ...).
> The File column now follows `chr_b-Complete-Mapping.md` (17 and 18 measured, the rest by the sequential rule), so the names follow the chr_b index.
> The earlier "Luffy and Robin" and "Nami and Franky" observations, and "PCT Nami gets her own block", came from the old pairing.
- **Conclusion:** jpower blocks are template libraries, not 1:1 movesets

---

## jpower.bin Structure

**Total entries:** 311 **Organization:** Alternating ATTACK and DATA blocks
**ATTACK blocks:** 43 total **Average:** ~4.2 jpower entries per character (but
shared across templates)

### Block Types

- **ATTACK blocks** (type1=1): Actual move data with damage/hitstun
- **DATA blocks** (type1=0): Separators or linked data (purpose unclear)

### Entry Structure

Each jpower entry (304 bytes) contains:

- **Main record (0x00-0x3F):** damage1, damage2, damage3, hitstun, linkCategory,
  nextId
  - **`jpower ID` is byte `+0x00`** — reproduces the block-0 ID column below exactly.
    Note IDs are not array indices: entry *n* has ID `3n` for the first seven.
  - **Offsets confirmed 2026-08-14** by reproducing the block-0 columns below, 9/9:
    `damage1` = byte at `+0x0C`, `damage2` = byte at `+0x0E`, `damage3` = byte at
    `+0x10`. File is 94544 bytes = 311 × 304 exactly.
  - **`damage1` stores displayed damage × 5.** Every value in the file is a multiple
    of 5 except `144`, so `floor(damage1/5)` is an exact division rather than a
    scaling heuristic.
- **Modifier sub-record (0x40-0x7F):** Powered/buffed state values (2x damage
  typically)
- **Extra data (0x80-0x12F):** Varies, 66/311 entries have non-zero data here

---

## Goku Move Mapping (Block 0)

**Block 0 jpower entries (indices 0-8):**

| Entry | jpower ID | damage1 | damage2 | damage3 | Total | In-Game | Likely Move     |
| ----- | --------- | ------- | ------- | ------- | ----- | ------- | --------------- |
| 0     | 0         | 30      | 20      | 0       | 50    | 7       | fwd B or down B |
| 1     | 3         | 10      | 40      | 0       | 50    | 7       | fwd B or down B |
| 2     | 6         | 50      | 0       | 0       | 50    | 7       | ?               |
| 3     | 9         | 30      | 0       | 20      | 50    | 7       | ?               |
| 4     | 12        | 25      | 25      | 0       | 50    | 7       | ?               |
| 5     | 15        | 20      | 0       | 30      | 50    | 7       | ?               |
| 6     | 18        | 25      | 25      | 0       | 50    | 7       | ?               |
| 7     | 21        | 60      | 40      | 0       | 100   | 14      | up Y            |
| 8     | 23        | 100     | 0       | 0       | 100   | 14      | down Y          |

> **Note (formula correction):** The "In-Game" and "Likely Move" columns above
> were attributed using the DEBUNKED total-based (÷7) formula. The confirmed
> formula is `floor(damage1 / 5) + (tier - 2)` (see archive/Research-Status.md), so
> the move attributions need re-verification.

**Not in Block 0:**

- B (8 damage) - **resolved:** uses `damage1=40` entries at global indices
  195, 218 (outside the block); selection mechanism still unknown.
  **CORRECTION (2026-08-14): index 146 has `damage1 = 35`, not 40** — verified
  directly against `jpower.bin` at the now-confirmed offset (`damage1` = byte at
  record `+0x0C`). `35` is exactly what **DOWN+B** (`7.000` displayed) requires, so
  146 is a DOWN+B candidate that was filed under B. See
  `findings/jpower-damage-located.md`.
- up B (3+3 damage) - multi-hit, might use nextId chains
- Y combo (4+4+6) - multi-hit, might be in collision

**Next Steps:** Check collision file subType mapping to jpower entries, and
investigate nextId chains for multi-hit moves.

---

## Critical Finding: jpower Blocks are Template Libraries

**Problem:** Characters sharing the same jpower block have DIFFERENT movesets.

**Examples:**
- ~~Goku and Majin Buu both use Block 0, but have completely different attacks~~ **VOID 2026-10-13:** Buu is Block 6 (chr_b row 10). See the Block 0 note above.
- **VOID 2026-10-13 (One Piece):** two earlier examples ("Luffy and Robin, Block 9, stretching vs
  arms" and "Nami and Franky, Block 12") came from the old character-to-file pairing and are
  dropped; no "different movesets" evidence exists for them under the corrected join. The block
  pairs are chr_b ROW facts: Block 9 = Luffy and Gear 2 Luffy (rows 12, 18; `op_b_01`, `op_b_07`),
  Block 12 = Nami and PCT Nami (rows 15, 19; `op_b_04`, `op_b_08`). Robin is Block 13, Franky Block 14.
  Whether those pairs share a moveset is unresolved.

**Implication:** The jpower block contains a **library of potential moves**, and each character selects a subset from that library.

**Selection mechanism unknown.** Possible methods:
1. Collision `subType` selects which jpower entry to use from the block
   — **QUESTIONED (2026-08-14):** now that the collision files are extracted, Goku's
   25 records give subType `{0:2, 1:6, 2:13, 5:2, 6:1, 7:1}` — **13 of 25 share
   subType 2**, which a one-to-one move selector wouldn't do. And subType is not the
   jpower ID (block 0's IDs are `0,3,6,…,23`; subTypes include `1,2,5,7`). At most a
   block-relative index. One character tested; see
   `findings/collision-subtype-vs-jpower.md`.
2. Collision `type2` or `linkCategory` performs selection
3. Another mapping file/table we haven't found
4. Hardcoded logic in game code per character index

---

## Open Questions

1. **Entry selection:** How do characters select specific jpower entries from their assigned block?
2. **Move-to-entry mapping:** How do moves (B, fwd B, Y) map to jpower entries?
3. ~~**Missing damage values:** Why doesn't Goku's B move (8 damage) exist in jpower?~~ **RESOLVED:** it does — `damage1=40` at indices 146/195/218 (confirmed formula uses damage1, not total)
4. **Multi-hit moves:** Where are combos (Y 4+4+6, up B 3+3) stored?
5. **DATA entries:** What purpose do type1=0 entries serve?
