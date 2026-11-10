# chr_b col-file mapping: files are numbered sequentially in chr_b order within a prefix

Tracker item: `jus-chrb-colfile-mapping-audit-x7i2` (child of `jus-lxyt`). Grade:
**CONFIRMED on 5/5 measured rows, predicted-only on the other 22, 1
attempted-and-rejected (failed roster verification), out of 28 total
suspect rows.**

## The rule

`chr_b-Complete-Mapping.md`'s File column was built on the assumption that
"variant forms take the highest number" within a prefix (e.g. a character's
SSJ/Bankai/White-Swan variant gets the last file in its series). That
assumption is refuted: the data instead supports **files numbered
sequentially in `chr_b` order within a prefix** — the Nth character (by
`chr_b` index, ascending) in a given series prefix gets that series'
`_0N.bin` file, with no gaps and no "variants go last" exception.

## Coverage

- **Measured (7 of 28):** `chr_b` 2 (Vegeta -> `db_b_03`), 21 (Sasuke ->
  `na_b_02`), 23 (Kakashi -> `na_b_04`), 37 (Eve -> `bc_b_01`) — all four
  resolved by a live pointer trace or byte-for-byte record search
  (`docs/research/findings/knockback-record-pointer-per-hit.md`) — and
  `chr_b` 67 (Momotaro -> `oj_b_02`), resolved this session by a live but
  hit-free method: reading `rec11`/`rec12` (the fixed fighter-body ColPrm
  records, always present on both sides) via
  `scripts/emu/projectile_census.py`'s `authored_base` field
  (`[[record+0x6C]+0x0C]`), no GDB or per-hit probe needed. All five land
  exactly where the sequential rule predicts. **2026-10-13 update:** `chr_b` 17 (Franky
  -> `op_b_06`, stored jumps match the C-UA-Yusuke S0 capture) and 18 (Gear 2 Luffy -> `op_b_07`,
  stored value 9 only, weaker) are now confirmed; both were the rejected/predicted rows below.
- **Attempted, rejected (1 of 28), superseded 2026-10-13 (17 now measured):** `chr_b` 17 (Franky), same method,
  `pc-kenshin-npc-franky-dark-tournament`. The player-slot roster
  verification (byte `+0x29`) read `28`/`62` instead of the state's
  documented `36`/`17`, so the dump this run produced is not trusted as
  Franky's — see
  `docs/research/feel-captures/colfile-audit-2026-09-12/RESULTS.md`.
- **Predicted, unmeasured (21 of 28):** every other suspect row (`db` 3-11,
  `op` 13/14/16/19, `na` 22/24, `bc` 38, `bb` 48/49, `oj` 66, `dt`
  71/72). See the full table in
  `docs/research/feel-captures/colfile-audit-2026-09-12/RESULTS.md`. A
  static pass over every capture in the repo that touches these characters
  (census `ENTRIES.md`, projectile-conflict traces, guard/shatter reports)
  found record *addresses*, *ids*, and *flag words*, but no case dumped a
  record's own 20 authored bytes for any of these characters — so none of
  them can be byte-matched against a candidate file that way. No save
  state in `jus_files/save_states/INDEX.md` currently has any of these 22
  as an active P1 or a roster-verified P2, so the live `authored_base`
  method (confirmed general by the Momotaro measurement) has nothing to
  read yet for these rows either. These rows are flagged in
  `chr_b-Complete-Mapping.md`'s header as "predicted, unmeasured"; their
  File-column values are **not** changed.
- **Non-suspect rows (6/6 tested before this tracker item, unchanged):** Yugi
  `yo_b_01`, Ichigo `bl_b_01`, Mashirito `ds_b_02`, Yusuke `yh_b_01`,
  Taikoubou `hs_b_01`, Kenshin `rk_b_01` — all confirmed correct as listed,
  and all also consistent with the sequential rule (single-file or
  first-position prefixes, where "sequential" and "old" coincide).

## Falsification condition

This rule is falsified by **one measured row (a live pointer trace or a
byte-for-byte record match, not a static guess) that breaks sequential
order within its prefix** — e.g. if a future trace on Sakura (`chr_b` 22)
turned up `na_b_05.bin` instead of the predicted `na_b_03.bin`. No such row
exists yet. Until each of the 21 predicted-only rows (17 and 18 now measured, 2026-10-13) is individually checked,
treat their predicted values as a strong hypothesis, not a fact —
`chr_b-Complete-Mapping.md`'s header note and `move_records.py`'s
`SUSPECT_CHRB` warning both still apply to them.

## Why this matters beyond the collision file

`move_records.py` resolves both the collision file and the `ChrArc.aar`
animation member from the same File column (see its module docstring and
`jus-chrb-colfile-mapping-audit-x7i2`'s tracker item body, "blast radius"). A wrong
File-column entry for any of the 21 unmeasured rows (predicted only, 2026-10-13) is therefore also a
wrong animation-member lookup for that character, not just a wrong
collision-record lookup, until it is individually measured.

## Provenance

`docs/research/feel-captures/colfile-audit-2026-09-12/RESULTS.md` (this
session's static pass, method, and full 28-row table).
`docs/research/findings/knockback-record-pointer-per-hit.md` (the four
measured rows). `docs/research/chr_b-Complete-Mapping.md` (header note,
File column). `scripts/analysis/move_records.py` (`KNOWN_REC0`,
`SUSPECT_CHRB`, `validate_file_choice` — unchanged this session; already
implements the refuse/warn behavior the parent tracker item's "remaining scope"
item asked for).
