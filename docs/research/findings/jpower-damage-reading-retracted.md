# The jpower damage reading is retracted

Tracker item: `jus-jpower-retraction-cguk`, a retraction of `jus-base-2-is-jpower-damage1-10-mse`
(the reading "base byte equals jpower damage1 / 5"). Static read, 2026-11-13 intake.
Cross-check source: Keshire's independent decode of jpower.bin
([keshire.md](../external/keshire.md)). What the file holds is in
[jpower-bin-is-the-koma-price-table.md](jpower-bin-is-the-koma-price-table.md).

## Why the reading fails

- The two live matches the retracted tracker item rested on (Goku B base 8 against 40, and Goku
  DOWN+B base 7 against 35) are entry prices of koma 540, 605 and 380. The retracted tracker item
  already noted that those rows are not in Goku's block.
- That every value is a multiple of 5 is price granularity: 2,346 of the 2,349 non-zero
  cost words are multiples of 5.

## What battle reads

The damage formula at 0x020823E4 loads the base from the chr/col record at +4
(`ldrsb r5,[r1,#4]` at 0x02082428), doubles it on a critical, then applies the two 8.8
multipliers. There is no table lookup.

The only loader of jpower.bin is the overlay 5 routine at 0x02165314. The JPower source-name
strings occur only in overlay 3 (JArenaGetJPower.cpp), overlay 4 (JQuizResultJPowerGraph.cpp)
and overlay 5 (JPower.cpp), and none of those overlays is resident in battle.

## What stands and what is void

The base-byte measurements themselves (Goku B = 8, DOWN+B = 7) stand. Void is the jpower
conversion and everything derived from it: the tier-offset claim, the chr_b class-id to
jpower-block link, and the idea that damageFlags is a jpower index.

`scripts/extract_character_data.py` still emits the jpower-derived keys; follow-up is `jus-extract-jpower-fields-cleanup-ndty`.
