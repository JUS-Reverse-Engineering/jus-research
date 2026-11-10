# Battle Character Mapping

Complete mapping of all 74 battle characters to their file prefixes, verified
via in-game deck order. Promoted from `docs/research/` to confirmed-facts
2026-08-22: the identity mapping is fully verified (owner-checked deck order,
Otokojuku swap corrected). Note the deck-builder order table below is
**deck-builder order**, not `chr_b` index order — see Battle-Engine-Map's
warning before using row numbers as indices.

---

## Series Prefix Reference

| Prefix | Series                   | Characters |
| ------ | ------------------------ | ---------- |
| bb     | Bobobo-bo Bo-bobo        | 4          |
| bc     | Black Cat                | 2          |
| bl     | Bleach                   | 5          |
| bu     | Busou Renkin             | 1          |
| db     | Dragon Ball              | 12         |
| dg     | D.Gray-man               | 2          |
| ds     | Dr. Slump                | 3          |
| dt     | Meta/Debug               | 4          |
| gt     | Gintama                  | 2          |
| hh     | Hunter x Hunter          | 2          |
| hk     | Hokuto no Ken            | 2          |
| hs     | Houshin Engi             | 1          |
| jj     | JoJo's Bizarre Adventure | 2          |
| kk     | KochiKame                | 1          |
| kn     | Kinnikuman               | 1          |
| mr     | Muhyo                    | 1          |
| na     | Naruto                   | 5          |
| nk     | Ninku                    | 1          |
| nn     | Neuro                    | 1          |
| oj     | Otokojuku                | 2          |
| op     | One Piece                | 8          |
| pj     | Pyuu to Fuku Jaguar      | 1          |
| rk     | Rurouni Kenshin          | 1          |
| sk     | Shaman King              | 3          |
| ss     | Saint Seiya              | 2          |
| tr     | Katekyo Hitman Reborn    | 1          |
| yh     | Yu Yu Hakusho            | 3          |
| yo     | Yu-Gi-Oh!                | 1          |

**Total: 74 battle characters**

---

## Complete Character List

> **Superseded by E0 (2026-10-18) for the chr_b mapping.** Rows marked `⚠ E0 legacy label` use legacy deck-builder-order file labels. The measured chr_b -> file mapping (`docs/research/feel-captures/2026-10-18-e0-roster/roster_reconciled.json`, grade MEASURED) is recorded in `docs/research/chr_b-Complete-Mapping.md`; use that for chr_b.

### bb - Bobobo-bo Bo-bobo

| File    | Character         | Entries | Notes                                                         |
| ------- | ----------------- | ------- | ------------------------------------------------------------- |
| bb_b_01 | Bo-bobo           | 24      | Base form                                                     |
| bb_b_02 | Shinsetsu Bo-bobo | 33      | Same animations, bigger hitboxes, form change during specials; ⚠ E0 legacy label: measured occupant of bb_b_02 is Don Patch |
| bb_b_03 | Don Patch         | 18      | Base form; ⚠ E0 legacy label: measured occupant of bb_b_03 is Shinsetsu |
| bb_b_04 | Super Patch       | 18      | Same kit as Don Patch                                         |

### bc - Black Cat

| File    | Character      | Entries | Notes |
| ------- | -------------- | ------- | ----- |
| bc_b_01 | Train Heartnet | 22      | ⚠ E0 legacy label: measured occupant of bc_b_01 is Eve |
| bc_b_02 | Eve            | 20      | ⚠ E0 legacy label: measured occupant of bc_b_02 is Train |

### bl - Bleach

| File    | Character          | Entries | Notes                       |
| ------- | ------------------ | ------- | --------------------------- |
| bl_b_01 | Ichigo Kurosaki    | 20      | Buff via Y spin or taunt    |
| bl_b_02 | Ichigo (Bankai)    | 26      | 7-8 koma, different moveset |
| bl_b_03 | Rukia Kuchiki      | 20      |                             |
| bl_b_04 | Renji Abarai       | 33      |                             |
| bl_b_05 | Toushiro Hitsugaya | 24      |                             |

### bu - Busou Renkin

| File    | Character    | Entries | Notes |
| ------- | ------------ | ------- | ----- |
| bu_b_01 | Kazuki Mutou | 31      |       |

### db - Dragon Ball

| File    | Character   | Entries | Notes                                |
| ------- | ----------- | ------- | ------------------------------------ |
| db_b_01 | Goku        | 25      | Base form                            |
| db_b_02 | Goku SSJ    | 36      | 22 type4 projectiles                 |
| db_b_03 | Vegetto     | 15      | 8 koma, same moveset except specials; ⚠ E0 legacy label: measured occupant of db_b_03 is Vegeta |
| db_b_04 | Vegeta      | 20      | Base form; ⚠ E0 legacy label: measured occupant of db_b_04 is Vegeta (SSJ) |
| db_b_05 | Vegeta SSJ  | 15      | ⚠ E0 legacy label: measured occupant of db_b_05 is Gohan (SSJ) |
| db_b_06 | Gohan SSJ   | 14      | No base Gohan exists; ⚠ E0 legacy label: measured occupant of db_b_06 is Gohan (SSJ2) |
| db_b_07 | Gohan SSJ2  | 27      | Different from SSJ; ⚠ E0 legacy label: measured occupant of db_b_07 is Gotenks |
| db_b_08 | Gotenks     | 22      | Base form; ⚠ E0 legacy label: measured occupant of db_b_08 is Gotenks (SSJ) |
| db_b_09 | Gotenks SSJ | 18      | ⚠ E0 legacy label: measured occupant of db_b_09 is Piccolo |
| db_b_10 | Piccolo     | 25      | ⚠ E0 legacy label: measured occupant of db_b_10 is Frieza |
| db_b_11 | Frieza      | 23      | ⚠ E0 legacy label: measured occupant of db_b_11 is Majin Buu |
| db_b_12 | Majin Buu   | 18      | ⚠ E0 legacy label: measured occupant of db_b_12 is Vegetto |

### dg - D.Gray-man

| File    | Character    | Entries | Notes              |
| ------- | ------------ | ------- | ------------------ |
| dg_b_01 | Allen Walker | 22      |                    |
| dg_b_02 | Lenalee Lee  | 29      | Light weight class |

### ds - Dr. Slump

| File    | Character     | Entries | Notes                                       |
| ------- | ------------- | ------- | ------------------------------------------- |
| ds_b_01 | Arale         | 28      |                                             |
| ds_b_02 | Dr. Mashirito | 33      | Persistent trap projectiles                 |
| ds_b_03 | Caramelman J  | 23      | Counts as Mashirito, entirely different kit |

### dt - Meta/Debug

| File    | Character      | Entries | Notes                          |
| ------- | -------------- | ------- | ------------------------------ |
| dt_b_01 | Komaman Red    | 15      | Unavailable in normal gameplay |
| dt_b_02 | Komaman Green  | 15      | Unavailable in normal gameplay |
| dt_b_03 | Komaman Yellow | 15      | Unavailable in normal gameplay |
| dt_b_04 | Taizo          | 1       | Can only move, no attacks      |

### gt - Gintama

| File    | Character      | Entries | Notes |
| ------- | -------------- | ------- | ----- |
| gt_b_01 | Gintoki Sakata | 41      |       |
| gt_b_02 | Kagura         | 32      |       |

### hh - Hunter x Hunter

| File    | Character      | Entries | Notes |
| ------- | -------------- | ------- | ----- |
| hh_b_01 | Gon Freecss    | 21      |       |
| hh_b_02 | Killua Zoldyck | 26      |       |

### hk - Hokuto no Ken

| File    | Character | Entries | Notes                            |
| ------- | --------- | ------- | -------------------------------- |
| hk_b_01 | Kenshiro  | 43      |                                  |
| hk_b_02 | Raoh      | 28      | Heavy weight, buff via neutral Y |

### hs - Houshin Engi

| File    | Character | Entries | Notes                        |
| ------- | --------- | ------- | ---------------------------- |
| hs_b_01 | Taikoubou | 39      | Y summon has hittable hitbox |

### jj - JoJo's Bizarre Adventure

| File    | Character   | Entries | Notes                                  |
| ------- | ----------- | ------- | -------------------------------------- |
| jj_b_01 | Jotaro Kujo | 37      |                                        |
| jj_b_02 | Dio Brando  | 37      | Stand attacks via down B, fwd Y, air B |

### kk - KochiKame

| File    | Character       | Entries | Notes                       |
| ------- | --------------- | ------- | --------------------------- |
| kk_b_01 | Ryotsu Kankichi | 28      | Persistent trap projectiles |

### kn - Kinnikuman

| File    | Character  | Entries | Notes                                   |
| ------- | ---------- | ------- | --------------------------------------- |
| kn_b_01 | Kinnikuman | 60      | Most collision entries of any character |

### mr - Muhyo

| File    | Character  | Entries | Notes |
| ------- | ---------- | ------- | ----- |
| mr_b_01 | Toru Muhyo | 40      |       |

### na - Naruto

| File    | Character      | Entries | Notes                             |
| ------- | -------------- | ------- | --------------------------------- |
| na_b_01 | Naruto Uzumaki | 46      | Shadow clones (22 type5)          |
| na_b_02 | Kyuubi Naruto  | 30      | 7-8 koma, different moveset; ⚠ E0 legacy label: measured occupant of na_b_02 is Sasuke |
| na_b_03 | Sasuke Uchiha  | 22      | Lightning specials, slash + blunt; ⚠ E0 legacy label: measured occupant of na_b_03 is Sakura |
| na_b_04 | Sakura Haruno  | 38      | Throws projectiles; ⚠ E0 legacy label: measured occupant of na_b_04 is Kakashi |
| na_b_05 | Kakashi Hatake | 26      | Summons dogs, slashing shuriken; ⚠ E0 legacy label: measured occupant of na_b_05 is Kyuubi Naruto |

### nk - Ninku

| File    | Character | Entries | Notes                                       |
| ------- | --------- | ------- | ------------------------------------------- |
| nk_b_01 | Fuusuke   | 45      | Buff via taunt, shares buff group with Raoh |

### nn - Neuro

| File    | Character    | Entries | Notes |
| ------- | ------------ | ------- | ----- |
| nn_b_01 | Neuro Nogami | 31      |       |

### oj - Otokojuku

| File    | Character        | Entries | Notes |
| ------- | ---------------- | ------- | ----- |
| oj_b_01 | Heihachi Edajima | 22      |       |
| oj_b_02 | Momotaro Tsurugi | 26      |       |

### op - One Piece

| File    | Character       | Entries | Notes                            |
| ------- | --------------- | ------- | -------------------------------- |
| op_b_01 | Monkey D. Luffy | 38      | 21 type5 (stretching)            |
| op_b_02 | Gear 2 Luffy    | 28      | 7-8 koma, 11 type4 (jet attacks) |
| op_b_03 | Roronoa Zoro    | 51      | Multi-hit combos, blade damage   |
| op_b_04 | Nami            | 22      | Base form                        |
| op_b_05 | PCT Nami        | 37      | 6 koma, weather attacks          |
| op_b_06 | Sanji           | 41      | Kick combos                      |
| op_b_07 | Nico Robin      | 32      | Arm spawns                       |
| op_b_08 | Franky          | 21      | Buff via taunt for fwd Y         |

### pj - Pyuu to Fuku Jaguar

| File    | Character      | Entries | Notes |
| ------- | -------------- | ------- | ----- |
| pj_b_01 | Jaguar Junichi | 26      |       |

### rk - Rurouni Kenshin

| File    | Character      | Entries | Notes                                        |
| ------- | -------------- | ------- | -------------------------------------------- |
| rk_b_01 | Himura Kenshin | 29      | Blade visual, blunt damage (hitProperties=1) |

### sk - Shaman King

| File    | Character        | Entries | Notes                  |
| ------- | ---------------- | ------- | ---------------------- |
| sk_b_01 | Yoh Asakura      | 14      | Base form              |
| sk_b_02 | Yoh (White Swan) | 19      | 6 koma, extended range |
| sk_b_03 | Anna Kyoyama     | 23      |                        |

### ss - Saint Seiya

| File    | Character    | Entries | Notes                     |
| ------- | ------------ | ------- | ------------------------- |
| ss_b_01 | Seiya        | 45      |                           |
| ss_b_02 | Seiya (Gold) | 21      | 8 koma, neutral Y knockup |

### tr - Katekyo Hitman Reborn

| File    | Character             | Entries | Notes |
| ------- | --------------------- | ------- | ----- |
| tr_b_01 | Tsuna Sawada & Reborn | 35      |       |

### yh - Yu Yu Hakusho

| File    | Character       | Entries | Notes                              |
| ------- | --------------- | ------- | ---------------------------------- |
| yh_b_01 | Yusuke Urameshi | 32      | Energy blasts, buff via held taunt |
| yh_b_02 | Kurama          | 32      | Roses and vines                    |
| yh_b_03 | Hiei            | 27      | Slashes and fiery punches          |

### yo - Yu-Gi-Oh!

| File    | Character | Entries | Notes                                       |
| ------- | --------- | ------- | ------------------------------------------- |
| yo_b_01 | Yugi Moto | 28      | Summons for all attacks except fwd B (trap) |

---

## Notes

### Form Variants

| Pattern                   | Example                 | Entries |
| ------------------------- | ----------------------- | ------- |
| Same kit, same data       | Don Patch / Super Patch | 18 / 18 |
| Same animations, enhanced | Bo-bobo / Shinsetsu     | 24 / 33 |
| Different moveset         | Ichigo / Bankai         | 20 / 26 |
| Different moveset         | Luffy / Gear 2          | 38 / 28 |
| Different moveset         | Naruto / Kyuubi         | 46 / 30 |
| Different moveset         | Nami / PCT Nami         | 22 / 37 |

### Characters Without Base Forms

- **Gohan**: Only SSJ and SSJ2 exist (no base form in game)

### Collision Entry Count Leaders

1. Kinnikuman: 60
2. Zoro: 51
3. Naruto: 46
4. Fuusuke: 45
5. Seiya: 45
6. Kenshiro: 43
7. Gintoki: 41
8. Sanji: 41

### Lowest Entry Counts

1. Taizo: 1 (can only move)
2. Yoh: 14
3. Gohan SSJ: 14
4. Vegetto: 15
5. Vegeta SSJ: 15
6. Komaman variants: 15 each

---

## Deck-Builder Order (merged from chr_b-Mapping.md)

The table below lists the 74 battle characters in **deck-builder series
order** (0 = Tsuna, ... 73 = Taizo).

> **CAUTION:** the old chr_b-Mapping.md called this column "chr_b Index", but
> it is DECK-BUILDER order, NOT the ARM9/file order used by
> `chr_b-Complete-Mapping.md` (where 0 = Goku / db_b_01). Same column name,
> different data - do not mix them up.

| Deck Order | File    | Character             | Series                |
| ---------- | ------- | --------------------- | --------------------- |
| 0          | tr_b_01 | Tsuna Sawada & Reborn | Katekyo Hitman Reborn |
| 1          | gt_b_01 | Gintoki Sakata        | Gintama               |
| 2          | gt_b_02 | Kagura                | Gintama               |
| 3          | kn_b_01 | Kinnikuman            | Kinnikuman            |
| 4          | kk_b_01 | Ryotsu Kankichi       | KochiKame             |
| 5          | oj_b_02 | Heihachi Edajima ⚠ E0 legacy label (measured occupant: Momotaro) |
| 6          | oj_b_01 | Momotaro Tsurugi ⚠ E0 legacy label (measured occupant: Edajima) |
| 7          | sk_b_01 | Yoh Asakura           | Shaman King           |
| 8          | sk_b_02 | Yoh (White Swan)      | Shaman King           |
| 9          | sk_b_03 | Anna Kyoyama          | Shaman King           |
| 10         | jj_b_01 | Jotaro Kujo           | JoJo                  |
| 11         | jj_b_02 | Dio Brando            | JoJo                  |
| 12         | ss_b_01 | Seiya                 | Saint Seiya           |
| 13         | ss_b_02 | Seiya (Gold)          | Saint Seiya           |
| 14         | dg_b_01 | Allen Walker          | D.Gray-man            |
| 15         | dg_b_02 | Lenalee Lee           | D.Gray-man            |
| 16         | ds_b_01 | Arale                 | Dr. Slump             |
| 17         | ds_b_02 | Dr. Mashirito         | Dr. Slump             |
| 18         | ds_b_03 | Caramelman J          | Dr. Slump             |
| 19         | db_b_01 | Goku                  | Dragon Ball           |
| 20         | db_b_02 | Goku (SSJ)            | Dragon Ball           |
| 21         | db_b_03 | Vegetto ⚠ E0 legacy label (measured occupant: Vegeta) |
| 22         | db_b_04 | Vegeta ⚠ E0 legacy label (measured occupant: Vegeta (SSJ)) |
| 23         | db_b_05 | Vegeta (SSJ) ⚠ E0 legacy label (measured occupant: Gohan (SSJ)) |
| 24         | db_b_06 | Gohan (SSJ) ⚠ E0 legacy label (measured occupant: Gohan (SSJ2)) |
| 25         | db_b_07 | Gohan (SSJ2) ⚠ E0 legacy label (measured occupant: Gotenks) |
| 26         | db_b_08 | Gotenks ⚠ E0 legacy label (measured occupant: Gotenks (SSJ)) |
| 27         | db_b_09 | Gotenks (SSJ) ⚠ E0 legacy label (measured occupant: Piccolo) |
| 28         | db_b_10 | Piccolo ⚠ E0 legacy label (measured occupant: Frieza) |
| 29         | db_b_11 | Frieza ⚠ E0 legacy label (measured occupant: Majin Buu) |
| 30         | db_b_12 | Majin Buu ⚠ E0 legacy label (measured occupant: Vegetto) |
| 31         | na_b_01 | Naruto Uzumaki        | Naruto                |
| 32         | na_b_02 | Kyuubi Naruto ⚠ E0 legacy label (measured occupant: Sasuke) |
| 33         | na_b_03 | Sasuke Uchiha ⚠ E0 legacy label (measured occupant: Sakura) |
| 34         | na_b_04 | Sakura Haruno ⚠ E0 legacy label (measured occupant: Kakashi) |
| 35         | na_b_05 | Kakashi Hatake ⚠ E0 legacy label (measured occupant: Kyuubi Naruto) |
| 36         | nk_b_01 | Fuusuke               | Ninku                 |
| 37         | hh_b_01 | Gon Freecss           | Hunter x Hunter       |
| 38         | hh_b_02 | Killua Zoldyck        | Hunter x Hunter       |
| 39         | pj_b_01 | Jaguar Junichi        | Pyuu to Fuku Jaguar   |
| 40         | bu_b_01 | Kazuki Mutou          | Busou Renkin          |
| 41         | bc_b_01 | Train Heartnet ⚠ E0 legacy label (measured occupant: Eve) |
| 42         | bc_b_02 | Eve ⚠ E0 legacy label (measured occupant: Train) |
| 43         | bl_b_01 | Ichigo Kurosaki       | Bleach                |
| 44         | bl_b_02 | Ichigo (Bankai)       | Bleach                |
| 45         | bl_b_03 | Rukia Kuchiki         | Bleach                |
| 46         | bl_b_04 | Renji Abarai          | Bleach                |
| 47         | bl_b_05 | Toushiro Hitsugaya    | Bleach                |
| 48         | hs_b_01 | Taikoubou             | Houshin Engi          |
| 49         | hk_b_01 | Kenshiro              | Hokuto no Ken         |
| 50         | hk_b_02 | Raoh                  | Hokuto no Ken         |
| 51         | bb_b_01 | Bo-bobo               | Bobobo                |
| 52         | bb_b_02 | Shinsetsu Bo-bobo ⚠ E0 legacy label (measured occupant: Don Patch) |
| 53         | bb_b_03 | Don Patch ⚠ E0 legacy label (measured occupant: Shinsetsu) |
| 54         | bb_b_04 | Super Patch           | Bobobo                |
| 55         | nn_b_01 | Neuro Nogami          | Neuro                 |
| 56         | mr_b_01 | Toru Muhyo            | Muhyo                 |
| 57         | yo_b_01 | Yugi Moto             | Yu-Gi-Oh!             |
| 58         | yh_b_01 | Yusuke Urameshi       | Yu Yu Hakusho         |
| 59         | yh_b_02 | Kurama                | Yu Yu Hakusho         |
| 60         | yh_b_03 | Hiei                  | Yu Yu Hakusho         |
| 61         | rk_b_01 | Himura Kenshin        | Rurouni Kenshin       |
| 62         | op_b_01 | Monkey D. Luffy       | One Piece             |
| 63         | op_b_02 | Gear 2 Luffy          | One Piece             |
| 64         | op_b_03 | Roronoa Zoro          | One Piece             |
| 65         | op_b_04 | Nami                  | One Piece             |
| 66         | op_b_05 | PCT Nami              | One Piece             |
| 67         | op_b_06 | Sanji                 | One Piece             |
| 68         | op_b_07 | Nico Robin            | One Piece             |
| 69         | op_b_08 | Franky                | One Piece             |
| 70         | dt_b_01 | Komaman Red           | Debug                 |
| 71         | dt_b_02 | Komaman Green         | Debug                 |
| 72         | dt_b_03 | Komaman Yellow        | Debug                 |
| 73         | dt_b_04 | Taizo                 | Debug                 |

> **Superseded by E0 (2026-10-18) for the chr_b mapping.** The table rows marked `⚠ E0 legacy label` use legacy deck-builder-order file labels. Measured chr_b values (roster_reconciled.json): Edajima = `oj_b_01`, Momotaro = `oj_b_02`; Vegeta = `db_b_03`, Vegeta (SSJ) = `db_b_04`, Vegetto = `db_b_12`; Sasuke = `na_b_02`, Sakura = `na_b_03`, Kakashi = `na_b_04`, Kyuubi Naruto = `na_b_05`; Don Patch = `bb_b_02`, Shinsetsu = `bb_b_03`; Eve = `bc_b_01`, Train = `bc_b_02`. Use `docs/research/chr_b-Complete-Mapping.md` for chr_b.

**Correction:** the Otokojuku file assignments were swapped in the original
chr_b-Mapping.md; they are fixed here per the verified identity mapping
(oj_b_01 = Momotaro Tsurugi, oj_b_02 = Heihachi Edajima).

