# jpower.bin is the koma evolution price table

Tracker item: `jus-jpower-koma-price-table-uh9o`. Static read of the ROM bytes, 2026-11-13 intake.
Cross-check source: Keshire's decoder of the same file ([keshire.md](../external/keshire.md)).

jpower.bin is the koma evolution (purchase and award) price table. It is not battle data.

## Layout

All 311 rows parse. Each row is 0x130 bytes: a 4-byte root koma index, then 15 cells of
0x14 bytes (4 + 15 x 0x14 = 0x130 exactly). The older layout needed 176 bytes of extra
data and padding to reach the row size; this one needs none.

The cell words read `[kind, usually 1, koma id, 0, cost x6]`. The kind word
takes values beyond small codes (6403 and 6146 occur), and the second word is not always 1
(row 0, cell 1 holds 9). Keshire groups the cells as 5 groups of 3 slots. That grouping is
his reading and was not re-derived here.

## Example

Row 146, root koma 379, has cells for koma 380, 382, 381, 383, 384 and 385. Their first
non-zero costs are 35, 150, 60, 300, 400 and 500, and koma 385's first cost word is 0.
That is an evolution tree with rising prices.

## Consumers

The loader is the overlay 5 routine at 0x02165314 (JPowerData_Create). Keshire traces its
readers to 0x021653AC (cell address), 0x021646F4 (award dispatch) and 0x02164458 (the six
resource costs); those three were not re-read here. That nothing in ARM9, overlay 6 or
overlay 11 reads the file is inferred from the single loader and from where the JPower
source strings sit, not from a reader sweep.

The code is byte-identical across the two ROM dumps.

## What it replaces

It replaces the damage reading in `jus-base-2-is-jpower-damage1-10-mse`, which is
retracted. See [jpower-damage-reading-retracted.md](jpower-damage-reading-retracted.md).
