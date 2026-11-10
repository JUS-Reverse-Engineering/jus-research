# Runtime deck indices reconciled

Tracker item: `jus-qz7z`  
Date: 2026-08-26

The apparent deck mismatch was a name-table error, not a deck-selection error.
The battle slot's player-array byte at `slot+0x29` is the character struct's
`+0x41` value. It is the battle panel's `koma.bin` `abilityId`, which indexes
the 74-row `chr_b.bin` table. It is not the deck-builder order used by the old
labels.

For each saved battle, the live `char+0x34` pointer was matched byte-for-byte
against `koma.bin`, then its parallel `komatxt.bin` entry was decoded. The
result is:

| state | slot | `+0x29` / `+0x41` | `koma.bin` record | `komatxt.bin` name |
|---|---:|---:|---:|---|
| EDA | 0 | 66 | 213 | Edajima |
| EDA | 1 | 48 | 700 | Don Patch |
| EDA | 2 | 12 | 823 | Luffy |
| RAO | 0 | 62 | 677 | Raoh |
| RAO | 1 | 15 | 839 | Nami |
| RAO | 2 | 17 | 861 | Franky |
| JJ | 0 | 28 | 275 | Jotaro |
| JJ | 1 | 14 | 846 | Sanji |
| JJ | 2 | 36 | 796 | Kenshin |
| JJ | 3 | 46 | 389 | Lenalee |

This independently confirms the owner's three deck descriptions and the raw
arrays `[66,48,12]`, `[62,15,17]`, and `[28,14,36,46]`. The corrected
`chr_b` labels are in `docs/research/chr_b-Complete-Mapping.md` and
`scripts/extract_character_data.py`; the mapping regression is covered by
`scripts/tests/test_chr_b_mapping.py`.

The correction changes the gate carrier interpretation. `chr_b 66` is
Edajima and has raw ability slots `[23,6,45]`; `chr_b 67` is Momotaro and has
`[9,10,0,0,56]`. Therefore the existing EDA deck does not arm bits 4 and 5;
a bit-4/5 measurement needs a deck containing Momotaro. The active gate matrix
has been updated accordingly.

The extracted battle-character passive reference independently gives the same
identity distinction in `docs/research/battle-chars-passives.json`: Momotaro
reduces Kick/Punch and Sword damage and loses SP while idle; Edajima has Solid
Stance and gains SP on KO. These are useful live-session sanity checks, but the
byte-level mapping above remains the authoritative index reconciliation. The
numeric categories in `Helper-Passives-Catalog.md` describe helper-koma
passives and must not be conflated with these `chr_b` ability IDs.
