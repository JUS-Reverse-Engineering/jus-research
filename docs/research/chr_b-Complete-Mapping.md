# chr_b.bin Complete Reference

> **Retracted reading (banner only; body kept as history):** the claim `jus-base-2-is-jpower-damage1-10-mse`
> (a move's base damage = `jpower.damage1 / 5`) was retracted by `jus-jpower-retraction-cguk`.
> jpower.bin is the koma evolution price table (`jus-jpower-koma-price-table-uh9o`); battle reads the base byte from chr/col `+4`.

> **Provenance (E0, 2026-10-18).** The File column of rows 3-11, 22, 24, 48, 49 and 66 is corrected to the prefix measured by the E0 roster capture, bundle `docs/research/feel-captures/2026-10-18-e0-roster/` (`roster_reconciled.json`, grade **MEASURED**): each state's 1280-byte battle collision dump, read from raw saved states, equals the full `chr/col` archive it names, across 170 owner states. Rows 12, 20 and 70 stay ambiguous by byte join and rows 71-73 are unobserved in owner states; their File values are unchanged and annotated. The previous values for the corrected rows were predicted or sequential-within-prefix guesses.
>
> ### Cross-check 2026-08-14 (Loop-Atlas)
>
> **Series column validated: 74/74.** An independent derivation — `koma.bin` `abilityId` → `chr_b`
> index, names from `komatxt.bin`, series from `Koma.NameTable` — agrees with this table's series code
> on every one of the 74 rows. Strong mutual validation for both.
>
> **One narrow correction: `chr_b[24]` is Kyuubi Naruto, not Kakashi.** Three independent lines:
> `koma.bin` records 504/505 (sizes 7 and 8) carry `abilityId = 24`; `komatxt.bin` names those panels
> **ナルト（九尾）**; and `chr_b[24]`'s per-size HP slots 3/4 are **192, 208**, exactly the owner's
> observed Naruto size-7/8 HP, where `chr_b[21]` gives `176, 192`. So the *name-within-series* ordering
> is off for these rows while the series column is right.
>
> Likely cause: this table assumes the `0x020924B0` string-table index equals the `chr_b` index, and
> `Battle-Engine-Map.md` **demoted** that assumption (its claim that the table's 6-bit id equals
> `classId` was refuted on a range mismatch). The alignment was never verified.
>
> **Also: the tier field is located.** The tier table below (`1`→−1, `2`→+0, `3`→+1) is
> `chr_b` byte **`+0x01`**, copied to battle-struct `+0x11` by the init function `0x02077C0C`. Its
> distribution is `{1:11, 2:56, 3:7}`. See `findings/docs-coverage-sweep.md`.


Complete mapping of the `chr_b.bin` rows. Numeric fields come from the 60-byte
records; the file/name labels are joined independently from battle-panel
`koma.bin` `abilityId` values and `komatxt.bin` display names. The index is not
deck-builder order.

### Runtime reconciliation (2026-08-26)

The former labels in this table treated an ARM9 pointer-table order as the
`chr_b` row order. That was wrong for several rows. The runtime battle field at
`char+0x41` (the player-array `+0x29` byte) is the battle panel's `koma.bin`
`abilityId`, which indexes `chr_b.bin`. In the saved gate states, the live
`char+0x34` panel pointers and `komatxt.bin` names independently produced:

| state | raw `+0x29` bytes | resolved panel names |
|---|---|---|
| EDA | `[66, 48, 12]` | Edajima, Don Patch, Luffy |
| RAO | `[62, 15, 17]` | Raoh, Nami, Franky |
| JJ | `[28, 14, 36, 46]` | Jotaro, Sanji, Kenshin, Lenalee |

This is why the owner-visible decks were correct. The corrected rows below are
also reflected in `scripts/extract_character_data.py`; gate measurements must
use these runtime IDs, especially Edajima `66`, Don Patch `48`, and Franky
`17`.

## chr_b.bin → Collision File Mapping

> **File-column audit (2026-09-12, `jus-chrb-colfile-mapping-audit-x7i2`,
> child of `jus-lxyt`'s [knockback-record-pointer-per-hit.md](findings/knockback-record-pointer-per-hit.md)
> finding).** This column's original "variant forms take the highest
> number" assumption is **refuted on 4/4 rows tested against a live
> collision-record trace and confirmed on 6/6 non-deviating rows**. The rule
> the data actually supports: **files are numbered sequentially in chr_b
> order within a prefix** (e.g. `na_b_01`..`na_b_05` should line up with
> `chr_b` 20..24 in order), and this table's File column deviates from that
> rule on **28 rows across 7 prefixes**: `db` chr_b 2–11, `op` chr_b 13, 14,
> 16–19, `na` chr_b 21–24, `bc` chr_b 37–38, `bb` chr_b 48–49, `oj` chr_b
> 66–67, `dt` chr_b 71–72. (That 28 is the 2026-09-12 audit count and stays as history;
> `move_records.SUSPECT_CHRB` holds **25** rows on 2026-10-13: the 28 minus Momotaro 67,
> Franky 17 and Gear 2 Luffy 18.) Five rows are now live-verified and corrected
> (Kakashi, Sasuke, Vegeta, Eve, Momotaro — see the corrections list below
> the table); Franky (17) and Gear 2 Luffy (18) were added 2026-10-13 (see
> the "Sixth and seventh corrections" note below the table), and the four
> other `op` rows (13, 14, 16, 19) were re-pointed with them on the
> sequential rule, unmeasured; **the other suspect rows are unverified and unchanged** —
> do not trust their File column without a pointer trace, and do not assume
> they follow the sequential rule either until each is individually
> checked. `scripts/checks/check_chrb_labels.py` does not guard this column
> (it only checks index↔name), so nothing catches a File-column error here
> automatically.
>
> **Static + live audit pass (2026-09-12, `jus-chrb-colfile-mapping-audit-x7i2`):**
> a repo-wide search for byte-level record evidence found none for the
> other 24 rows (existing captures record addresses/ids/flags for these
> characters, never a record's own 20 authored bytes to byte-match against
> a file); a live bridge pass (`projectile_census.py`'s `authored_base`
> field, no GDB needed — see `docs/research/findings/knockback-record-pointer-per-hit.md`
> for the P1 base and this tracker item's corrections list for the P2 method)
> resolved Momotaro and attempted but could not verify Franky (the
> player-slot roster check failed — leading hypothesis is a slot-0 read
> instead of the active slot, `jus-franky-state-roster-mismatch-rkwf`, not
> a bad state load; Franky was later resolved by the 2026-10-13 UA capture) — see
> colfile-audit-2026-09-12/RESULTS.md.
> **Superseded by E0 (2026-10-18): the rows below for chr_b 3-11, 22, 24, 48, 49 and 66 are no longer predictions.** Measured values: 3-10 `db_b_04`..`db_b_11`, 11 `db_b_12`, 22 `na_b_03`, 24 `na_b_05`, 48 `bb_b_02`, 49 `bb_b_03`, 66 `oj_b_01` (see the table above and `feel-captures/2026-10-18-e0-roster/roster_reconciled.json`, grade MEASURED). The prediction text is kept as history; for those rows it is not current.
> The sequential-within-prefix rule predicts each remaining row's likely
> File value (**predicted, unmeasured** -- not applied to the table below (row 38 Train bc_b_02 applied below)):
> `db_b_04`(3) `db_b_05`(4) `db_b_06`(5) `db_b_07`(6) `db_b_08`(7)
> `db_b_09`(8) `db_b_10`(9) `db_b_11`(10) `db_b_12`(11) . `op_b_02`(13)
> `op_b_03`(14) `op_b_05`(16) `op_b_06`(17, measured) `op_b_07`(18, measured: store value 9 only) `op_b_08`(19) .
> `na_b_03`(22) `na_b_05`(24) . `bc_b_02`(38) . `bb_b_02`(48) `bb_b_03`(49)
> . `oj_b_01`(66) . `dt_b_02`(71) `dt_b_03`(72). See
> [findings/col-file-mapping-is-sequential-within-prefix.md](findings/col-file-mapping-is-sequential-within-prefix.md)
> for the rule, its grade, and its falsification condition.

| chr_b | File    | Character        | Series          | charId | classId | jpower Block |
| ----- | ------- | ---------------- | --------------- | ------ | ------- | ------------ |
| 0     | db_b_01 | Goku             | Dragon Ball     | 7      | 256     | 0            |
| 1     | db_b_02 | Goku (SSJ)       | Dragon Ball     | 7      | 256     | 0            |
| 2     | db_b_03 | Vegeta           | Dragon Ball     | 7      | 257     | 1            |
| 3     | db_b_04 | Vegeta (SSJ)     | Dragon Ball     | 7      | 257     | 1            |
| 4     | db_b_05 | Gohan (SSJ)     | Dragon Ball     | 7      | 258     | 2            |
| 5     | db_b_06 | Gohan (SSJ2)     | Dragon Ball     | 7      | 258     | 2            |
| 6     | db_b_07 | Gotenks          | Dragon Ball     | 7      | 259     | 3            |
| 7     | db_b_08 | Gotenks (SSJ)    | Dragon Ball     | 7      | 259     | 4            |
| 8     | db_b_09 | Piccolo          | Dragon Ball     | 54     | 516     | 5            |
| 9     | db_b_10 | Frieza           | Dragon Ball     | 41     | 261     | 6            |
| 10    | db_b_11 | Majin Buu        | Dragon Ball     | 54     | 262     | 6            |
| 11    | db_b_12 | Vegetto          | Dragon Ball     | 7      | 256     | 0            |
| 12    | op_b_01 (E0 2026-10-18: ambiguous by byte join) | Luffy            | One Piece       | 9      | 521     | 9            |
| 13    | op_b_02 | Zoro             | One Piece       | 14     | 522     | 10           |
| 14    | op_b_03 | Sanji            | One Piece       | 18     | 523     | 11           |
| 15    | op_b_04 | Nami             | One Piece       | 16     | 524     | 12           |
| 16    | op_b_05 | Robin            | One Piece       | 4      | 525     | 13           |
| 17    | op_b_06 | Franky           | One Piece       | 10     | 270     | 14           |
| 18    | op_b_07 | Gear 2 Luffy     | One Piece       | 9      | 521     | 9            |
| 19    | op_b_08 | PCT Nami         | One Piece       | 16     | 524     | 12           |
| 20    | na_b_01 (E0 2026-10-18: ambiguous by byte join) | Naruto           | Naruto          | 2      | 529     | 17           |
| 21    | na_b_02 | Sasuke           | Naruto          | 13     | 274     | 18           |
| 22    | na_b_03 | Sakura           | Naruto          | 8      | 275     | 19           |
| 23    | na_b_04 | Kakashi          | Naruto          | 13     | 532     | 20           |
| 24    | na_b_05 | Kyuubi Naruto    | Naruto          | 54     | 529     | 22           |
| 25    | sk_b_01 | Yoh              | Shaman King     | 6      | 534     | 22           |
| 26    | sk_b_02 | Yoh (White Swan) | Shaman King     | 6      | 534     | 22           |

> Owner (2026-09-03): Yoh (White Swan) `26` is regular Yoh `25` with a different sprite and slightly different hitboxes; the real difference is his X specials. The Yoh GameFAQs extract (`docs/research/gamefaqs-movesets/yoh--46755.json`) therefore covers his normals.

| 27    | sk_b_03 | Anna             | Shaman King     | 6      | 535     | 23           |
| 28    | jj_b_01 | Jotaro           | JoJo            | 13     | 281     | 25           |
| 29    | jj_b_02 | Dio              | JoJo            | 54     | 282     | 26           |
| 30    | hh_b_01 | Gon              | Hunter x Hunter | 42     | 545     | 33           |
| 31    | hh_b_02 | Killua           | Hunter x Hunter | 29     | 290     | 34           |
| 32    | yh_b_01 | Yusuke           | Yu Yu Hakusho   | 38     | 294     | 37           |
| 33    | yh_b_02 | Kurama           | Yu Yu Hakusho   | 28     | 295     | 39           |
| 34    | yh_b_03 | Hiei             | Yu Yu Hakusho   | 32     | 552     | 42           |
| 35    | yo_b_01 | Yugi             | Yu-Gi-Oh!       | 47     | 298     | 47           |
| 36    | rk_b_01 | Kenshin          | Rurouni Kenshin | 1      | 556     | 48           |
| 37    | bc_b_01 | Eve              | Black Cat       | 54     | 305     | 52           |
| 38    | bc_b_02 | Train            | Black Cat       | 25     | 562     | 54           |
| 39    | bl_b_01 | Ichigo           | Bleach          | 3      | 564     | 52           |
| 40    | bl_b_02 | Bankai Ichigo    | Bleach          | 3      | 564     | 52           |
| 41    | bl_b_03 | Rukia            | Bleach          | 3      | 565     | 56           |
| 42    | bl_b_04 | Renji            | Bleach          | 3      | 310     | 54           |
| 43    | bl_b_05 | Hitsugaya        | Bleach          | 3      | 567     | 65           |
| 44    | bu_b_01 | Kazuki           | Busou Renkin    | 54     | 575     | 63           |
| 45    | dg_b_01 | Allen            | D.Gray-man      | 32     | 576     | 65           |
| 46    | dg_b_02 | Lenalee          | D.Gray-man      | 3      | 577     | 65           |
| 47    | bb_b_01 | Bo-bobo          | Bobobo          | 14     | 581     | 70           |
| 48    | bb_b_02 | Don Patch        | Bobobo          | 14     | 582     | 71           |
| 49    | bb_b_03 | Shinsetsu        | Bobobo          | 14     | 581     | 70           |
| 50    | bb_b_04 | Super Patch      | Bobobo          | 14     | 582     | 70           |
| 51    | kk_b_01 | Ryotsu           | KochiKame       | 42     | 587     | 92           |
| 52    | gt_b_01 | Gintoki          | Gintama         | 5      | 596     | 93           |
| 53    | gt_b_02 | Kagura           | Gintama         | 55     | 341     | 187          |
| 54    | tr_b_01 | Tsuna            | Reborn          | 4      | 348     | 98           |
| 55    | pj_b_01 | Jaguar           | Jaguar          | 28     | 355     | 99           |
| 56    | ds_b_01 | Arale            | Dr. Slump       | 30     | 615     | 100          |
| 57    | ds_b_02 | Mashirito        | Dr. Slump       | 45     | 360     | 101          |
| 58    | ds_b_03 | Caramelman       | Dr. Slump       | 45     | 361     | 102          |
| 59    | mr_b_01 | Muhyo            | Muhyo           | 47     | 652     | 140          |
| 60    | nn_b_01 | Neuro            | Neuro           | 31     | 401     | 157          |
| 61    | hk_b_01 | Kenshiro         | Hokuto no Ken   | 13     | 658     | 146          |
| 62    | hk_b_02 | Raoh             | Hokuto no Ken   | 13     | 403     | 147          |
| 63    | ss_b_01 | Seiya            | Saint Seiya     | 13     | 662     | 150          |
| 64    | ss_b_02 | Gold Seiya       | Saint Seiya     | 13     | 662     | 150          |
| 65    | kn_b_01 | Kinnikuman       | Kinnikuman      | 14     | 667     | 166          |
| 66    | oj_b_01 | Edajima          | Otokojuku       | 23     | 419     | 172          |
| 67    | oj_b_02 | Momotaro         | Otokojuku       | 9      | 420     | 164          |
| 68    | hs_b_01 | Taikoubou        | Houshin Engi    | 47     | 684     | 172          |
| 69    | nk_b_01 | Fuusuke          | Ninku           | 2      | 443     | 179          |
| 70    | dt_b_01 (E0 2026-10-18: ambiguous by byte join) | Komaman Red      | Debug           | 0      | 446     | 190          |
| 71    | dt_b_02 (unobserved in owner states) | Komaman Green    | Debug           | 0      | 447     | 191          |
| 72    | dt_b_03 (unobserved in owner states) | Komaman Yellow   | Debug           | 0      | 448     | 192          |
| 73    | dt_b_04 (unobserved in owner states) | Taizo            | Debug           | 0      | 446     | 190          |

**File-column corrections (2026-09-12, `jus-lxyt` /
`jus-chrb-colfile-mapping-audit-x7i2`):** four rows above were corrected
against a live collision-record pointer trace (Kakashi, Sasuke) or a
byte-for-byte file search (Vegeta, Eve) — see
[findings/knockback-record-pointer-per-hit.md](findings/knockback-record-pointer-per-hit.md)
and `docs/confirmed-facts/characters/kakashi.md`:

- `chr_b` 2 (Vegeta): `db_b_04` → `db_b_03`
- `chr_b` 21 (Sasuke): `na_b_03` → `na_b_02`
- `chr_b` 23 (Kakashi): `na_b_05` → `na_b_04`
- `chr_b` 37 (Eve): `bc_b_02` → `bc_b_01`

**Fifth correction (2026-09-12, same tracker item, live pass):** the fighter-body
ColPrm record (`rec11`'s `[[record+0x6C]+0x0C]` authored-table base — no
hit needed, read directly via `scripts/emu/projectile_census.py`'s
`authored_base` field) for Momotaro as **P1 (active)** in
`pc-momotaro-npc-nami-dark-tournament` (chr_b index confirmed live via the
player-slot byte `+0x29` = `67`) byte-matched `oj_b_02.bin` rec 0/1
uniquely, not `oj_b_01.bin`:

- `chr_b` 67 (Momotaro): `oj_b_01` → `oj_b_02`

Positive controls for this live method (Vegeta and Kakashi as **P2**,
`pc-yugi-fb-npc-vegeta-fy` and `pc-taikoubou-upx-npc-kakashi-x`) reproduced
`db_b_03` and `na_b_04` rec 0 exactly before this new row was trusted. A
sixth attempt (Franky, `chr_b` 17, as P2 in
`pc-kenshin-npc-franky-dark-tournament`) was **not** trusted: the
player-slot byte read `28`/`62` (Jotaro/Raoh) instead of the expected
`36`/`17` (Kenshin/Franky) for that state, failing the same roster
verification step that passed for Momotaro — see
colfile-audit-2026-09-12/RESULTS.md
for the full account. `chr_b` 17 (Franky) was unmeasured at that point;
see the sixth and seventh corrections below.

**Sixth and seventh corrections (2026-10-13, `chrbop`):** the One Piece
rows 13, 14, 16-19 were a permutation of the files `op_b_02`, `op_b_03`,
`op_b_05`..`op_b_08` (the old table held 13 `op_b_03`, 14 `op_b_06`,
16 `op_b_07`, 17 `op_b_08`, 18 `op_b_02`, 19 `op_b_05`). All six now follow the
sequential-within-prefix rule. Two are measured by the
C-UA-Yusuke S0 capture
(no memory poked): the owner save states carry the ctrl+`0xA3` stored value
that each character's own consumer table interprets. Franky (chr 17) stores
`3` and `6` and jumps side Y f10 -> f52 / f103 and air Y f11 -> f89 / f158;
`docs/rebuild/ua-table.json` shows `op_b_06` is the only One Piece file with
exactly stores `3` and `6` and stored jumps side Y f9 `{3: 52, 6: 103}`, air
Y f10 `{3: 89, 6: 158}` (the table's jump frame is one below the capture's
live playhead frame), while `op_b_08` (the old Franky file) is a 40-frame UA anim with
no playhead events. G2 Luffy (chr 18) stores `9`; `op_b_07` is the only
`op_b_*` prefix with a store of `9` (anim `0x18` f110), so that identity
rests on the value alone (weaker). The four other rows are moved by the
sequential rule only and stay **unmeasured**: `13` Zoro -> `op_b_02`,
`14` Sanji -> `op_b_03`, `16` Robin -> `op_b_05`, `19` PCT Nami -> `op_b_08`
(`move_records.SUSPECT_CHRB` still lists 13, 14, 16, 19; 17 and 18 are
removed). The permutation also fits the jpower note below: Block 12 is
Nami (`op_b_04`) and PCT Nami (`op_b_08`), Block 9 is Luffy (`op_b_01`) and
Gear 2 Luffy (`op_b_07`).

Static corroboration of the four unmeasured rows (read from `docs/rebuild/ua-table.md` against the GameFAQs
Ultimate Action text; it does **not** promote them, they stay in `SUSPECT_CHRB`): Sanji's UA gives three
food outcomes and `op_b_03` carries three `op3_arg32` events (values 10, 2, 5); Robin's UA slowly restores SP and
`op_b_05` is the held-loop anim with the SP effect; the old Robin file `op_b_07` has neither. The guide
mash tags also moved onto the new files (Sanji Y -> `op_b_03` 0x1f, Robin X+up -> `op_b_05` 0x2c,
Nami Y on `op_b_08` 0x1f). One tag went the other way: Franky's guide Y ("hits rise after each UA") no longer
finds a mash event on `op_b_06` 0x1f, where the mechanism is the stored jump `0x1f f0 -> f91 (store 3)` instead.

> **Superseded by E0 (2026-10-18):** the collisions below are resolved by measurement. Measured values: Edajima 66 = `oj_b_01` (the table row is now measured, and the `⚠ refuted` annotation it mentions is no longer in the table), Momotaro 67 = `oj_b_02`; Sakura 22 = `na_b_03`, Kakashi 23 = `na_b_04`; Sasuke 21 = `na_b_02`, Kyuubi Naruto 24 = `na_b_05`; Don Patch 48 = `bb_b_02`, Shinsetsu 49 = `bb_b_03`; Vegeta 2 = `db_b_03`, Vegeta (SSJ) 3 = `db_b_04`, Vegetto 11 = `db_b_12` (no longer a shared `db_b_03` pair). Eve 37 / Train 38 (`bc_b_01` / `bc_b_02`) are unchanged; Train 38 is now live-measured by the E0 roster pin (its earlier `⚠` marker and the 2026-10-12 paragraph below are history). See the table above and `feel-captures/2026-10-18-e0-roster/roster_reconciled.json`. The paragraph below is history.

**Duplicate-File note (2026-09-12):** correcting `chr_b` 67 to `oj_b_02`
put it on the same File value as `chr_b` 66 (Edajima), which the table
still lists as `oj_b_02` under the old "variant forms take the highest
number" assumption this whole audit refutes. Edajima's row is annotated
`⚠ refuted by the 67 measurement; predicted oj_b_01, unmeasured` above
rather than changed outright, since `oj_b_01` for Edajima is a prediction,
not a measurement. `scripts/checks/check_chrb_labels.py`'s duplicate-File
check, added this session, turned up four such pairs in total (each a
row whose live-verified correction now collides with another row still
carrying the old, stale File value): `chr_b` 66/67 (`oj_b_02`,
Edajima/Momotaro), 22/23 (`na_b_04`, Sakura/Kakashi), 21/24 (`na_b_02`,
Sasuke/Kyuubi Naruto), and 37/38 (`bc_b_01` Eve / `bc_b_02` Train, resolved below). Each unmeasured
row in these pairs (Sakura, Kyuubi Naruto, Train) is annotated the same
way as Edajima. `chr_b` 2/11 (Vegeta/Vegetto, both `db_b_03` in the
table) are a fifth, different-shaped duplicate: not a stale-value
collision but a known shared-records case per the Refuter's finding that
`db_b_04` (at `+120`) shares records with `db_b_03` — flagged separately
below the table with a `⚠ shared-records case` marker instead of
`refuted`.

**Train's File value (2026-10-12, static):** `chr_b` 38 now
reads `bc_b_02`, the value the sequential rule predicted. Still not a live
measurement (no byte-for-byte rec 0 read for Train), so the row keeps its `⚠`
marker and `move_records.py` still treats 38 as suspect. Static evidence, in
`docs/rebuild/knockback-table.json` (`bc_b_02`'s 20 records, decoded from
`chr/col/bc_b_02.bin`): the damages match the GameFAQs Train guide where
Eve's file (`bc_b_01`) does not. B 7, Y 15 (Eve's Y is 16, measured), down Y
14, 5 per shot of the side-Y gunfire, and one 28-damage record of hit type 6
(the guide gives the 4-koma Rail Gun as 28 against Power). `chr/` holds two
Black Cat fighter archives, `bc_b_01` (Eve, live-measured) and `bc_b_02`; a
cast-art catalog lists `bc_b_02`, `bc_b_02_4` and `bc_b_02_5` as Train's native
prefixes. RAM evidence: the col/bc_b_02.bin rec 0-3 bytes are resident in both TRAIN HEARTNET owner states' RAM, with bc_b_01's bytes absent in TRAIN HEARTNET/5.mln.gz, and bc_b_02's absent in EVE/4.mln.gz (refuter check, state_identity reads). `chr_b[38]` itself:
nature 0 (Power), per-size HP 136 (4-koma) and 152 (5-koma).

The other 22 rows the audit flagged as suspect and did not measure or
attempt (see the header note above) are **not** changed by this pass;
`chr_b` 17 (Franky) was attempted and rejected on a roster-verification
failure (see above) and is also unchanged.

## Key Discoveries

### Shared jpower Blocks (≠ Shared Movesets!)

Characters sharing the same `classId & 0xFF` reference the same jpower block,
but **DO NOT necessarily share movesets**.

**Confirmed shared movesets:**

- db_b_01 + db_b_02 (Goku + Goku SSJ) - Block 0
- bb_b_03 + bb_b_04 (Don Patch + Super Patch) - Block 70

**Same jpower block, DIFFERENT movesets:**

- ~~**Block 0:** db_b_12 (Majin Buu) ≠ Goku~~ **VOID 2026-10-13:** Majin Buu is row 10 (`db_b_12` in the pre-E0 table; measured `db_b_11` since E0 2026-10-18, classId 262), Block 6, not Block 0. The row that shares Goku's Block 0 is Vegetto (row 11, classId 256); no moveset comparison is recorded for that pair.
- **Block 52:** bl_b_01 (Ichigo) ≠ bl_b_02 (Bankai Ichigo)
- **Block 70:** bb_b_01 (Bo-bobo) ≠ bb_b_03/04 (Don Patch variants)

**VOID 2026-10-13 (One Piece blocks):** this list used to carry "Block 9: Luffy
≠ Gear 2 Luffy" and "Block 12: Nami ≠ PCT Nami". Both claims came from the old
character-to-file pairing (the same claim read "Luffy ≠ Robin" and "Nami ≠ Franky"
there), and nothing under the corrected join supports "different movesets" for
them. The block pairs are chr_b ROW facts: Block 9 = rows 12 and 18 (Luffy, Gear 2
Luffy; `op_b_01`, `op_b_07`), Block 12 = rows 15 and 19 (Nami, PCT Nami; `op_b_04`,
`op_b_08`). Whether either pair shares a moveset is **unresolved**; see
[jpower-Mapping.md](jpower-Mapping.md).

**Conclusion:** jpower blocks are **template libraries**, not complete movesets.
Characters select specific entries from their assigned block via unknown
mechanism (possibly collision subType, type2, linkCategory, or other selection
logic).

### Damage Formula (SOLVED - see archive/Research-Status.md)

> Superseded (2026-09-02): the `damage1/5 + (tier-2)` formula below is retracted. The measured arithmetic is in `docs/confirmed-facts/damage.md` §1 and §4 [`jus-reduction-is-quarter-multiplier-xk1`]; nature is additive, see `docs/confirmed-facts/nature.md` §2.1 [`jus-nature-is-read-in-damage-path-hbt`]. Kept as history.

**Confirmed for all tested characters:**

```
damage = floor(jpower.damage1 / 5) + (tier - 2)
```

- Uses `damage1` (first component) ONLY - NOT the d1+d2+d3 total
- tier 1: -1 modifier (Bankai B = 9)
- tier 2: +0 modifier (Ichigo B = 10)
- tier 3: +1 modifier (Caramelman B = 13)
- Nature multiplier: 1.5x on advantage only

**Former "Goku paradox" (DEBUNKED):** An earlier total-based version of the
formula could not explain Goku B=8 and spawned a bogus ÷7 alternative. With
`damage1` alone there is no paradox: B=8 comes from `damage1=40` entries
(global indices 146, 195, 218, outside Block 0).

**Collision damage difference:**

- Goku: 2/25 collision entries have damageFlags (values: 1, 14)
- Ichigo: 19/20 collision entries have damageFlags (values: 2-14)
- Characters with more collision damage may bypass jpower entirely

### Block 52 Mystery

Block 52 (Ichigo+Bankai) points to **empty jpower entries** (all zeros at index
52-53). This suggests jpower block index may not directly map to jpower array
index.

**Possible interpretations:**

1. Block index counts DATA entries, not array index
2. Block index is multiplied/offset before lookup
3. Characters with collision damage don't need jpower

### Stat Template Groups (charId)

29 unique charIds for 74 characters:

- **charId=7**: Goku family (9 chars)
- **charId=3**: Bleach + Lenalee (6 chars)
- **charId=13**: Mixed group (7 chars including Raoh)
- **charId=16**: Nami + PCT Nami (rows 15, 19). VOID 2026-10-13: the former "Nami + Franky (opposites!)" pairing came from the old file join; Franky is row 17, charId 10.

## Weight (SOLVED 2026-09-01) & Walk Speed (SOLVED)

**Weight is not a stored stat.** It is two passive abilities, read as gate
bits by the knockback code — see `docs/confirmed-facts/physics.md` §4.1
(`jus-9lp.2`):

| passive (`chr_b +0x03..+0x07`) | gate bit | launcher knockback | who has it |
|---|---|---|---|
| 24 軽量級 Lightweight | 15 (`0x8000`) | ×1.5 | Nami, PCT Nami, Anna, Eve, Rukia, Hitsugaya, Lenalee, Muhyo, Fuusuke |
| 23 重量級 Heavyweight | 7 (`0x80`) | ×0.5 | Franky, Caramelman, Edajima |
| neither | — | ×1 | everyone else, including Luffy, Naruto and Raoh |

Raoh has neither passive and launches exactly like Luffy in every measured
band (physics.md §4.2). The earlier "Raoh is heavy" note was about a
different passive (`Take less damage from Special Attacks`), not launch
weight — drop Raoh from any heavy list.

**Walk speed IS in chr_b.bin** (`statC` field, threshold/tier-based):

The earlier conclusion that walk speed was "not in chr_b" was wrong — it was
confounded by **Edajima**, who has a normal statC value but is slowed by an
innate character passive (he is the heaviest/slowest character). See
archive/Research-Status.md for the confirmed tier data; exact thresholds are tracked
in JUS-n3p.

Weight is two passive abilities, not an unlocated stat (§4.1). Walk speed is
solved (statC).

## Appendix: E0 label consumers (2026-10-18)

`scripts/tests/test_e0_label_consumers.py` checks every live structured consumer of the
chr_b -> file -> character join against `feel-captures/2026-10-18-e0-roster/roster_reconciled.json`:
`extract_character_data.CHARACTER_MAP`, this doc's table, `character-index.json`,
`character-index.md`, the DamageFlags tables, `move_records` (`SUSPECT_CHRB`,
`MEASURED_CHRB_FILE`, `KNOWN_REC0`), `mash_table.GUIDE_FILES`, `decoder_roster.json` and the
`kit/*.toml` chr_b/prefix pairs, the gamefaqs-movesets chr_b notes, and the names in the mash, ua,
cancel and knockback tables. Every roster row must appear in all four tables. Ambiguous rows (12,
20, 70) and unobserved rows (71, 72, 73) keep this doc's label and stay flagged.

How the list was built: a sweep of the 362 files that name a `xx_b_NN` prefix flagged 58 files
with a line that pairs one prefix with a roster name other than E0's. Each was classified:

- **Live, covered by the test (12):** this doc, `character-index.md`,
  `DamageFlags-Character-Classification.md`, `extract_character_data.py`, `move_records.py`, the
  four `docs/rebuild/*-table.json`, and gamefaqs-movesets `eve`, `sakura` and `sasuke` (`goku` was
  also fixed). `character-index.json` was not flagged, because its lines carry no names, but the
  test covers it.
- **Live prose, fixed (4):** `kit/train.toml` (fixed after review r3), `characters/eve.md`, `characters/sasuke.md` and
  `characters/Goku-Character-Map.md`.
- **History, superseded note added (16):** `jpower-Mapping.md`;
  `guardbreak-2026-09-02/static-knockback-fields.md`;
  `register-2026-09-03/runtime-report-6-guard-shatter.md`;
  `register-2026-09-03/runtime-report-7-pops-launchers.md`, whose note covers
  `pops-launchers-2026-09-03/static-records-21.txt` and `-37.txt`;
  `register-2026-09-03/static-hitbox-record-selection.md`; `sp-live-2026-09-12/.../RESULTS.md`;
  `trio-2026-09-12/B/RESULTS.md`; `findings/knockback-record-pointer-per-hit.md`;
  `findings/node-0x18-...md`; `2026-10-13-yusuke-ua/README.md`, whose note covers
  `compare.json`; `2026-10-13-yusuke-ua/plans/analyze.py`; and
  `kakashi-2026-09-03/phase2-specials-notes.md`, whose note covers both `static-*-kakashi.txt`.
- **History, already noted (8):** `characters/Character-Mapping.md`,
  `archive/Combat-Mechanics.md`, `archive/Human-Testing-Queue.md`,
  `scripts/archive/classify_damage_flags.py`, `sasuke-2026-09-04/run-notes.md` (its erratum
  covers both `static-*-sasuke.txt`), and `colfile-audit-2026-09-12/RESULTS.md`, which writes
  old -> new inline.
- **False positives (18):** the line names a second character, or a base name inside a form name
  (Goku in "Goku SSJ", Ichigo in "Ichigo (Bankai)"). These are `Ichigo-Character-Map.md`,
  `2026-10-15-taikoubou-6kx-branches.md`,
  `findings/luffy-blunt-gate-2026-09-02.md`, the three `clash-tier-survey-2026-09-25` files,
  `2026-10-18-e0-roster/RESULTS.md`, `side-quests/ai-behaviour-data-layout.md`,
  `knockback_table.py`, `test_cancel_table.py`, `test_char_args.py` (deliberate negative cases),
  `test_chr_b_mapping.py`, `rebuild/mash-table.md`, `rebuild/ua-table.md` and
  `pops-launchers-2026-09-03/static-records-26.txt`.
