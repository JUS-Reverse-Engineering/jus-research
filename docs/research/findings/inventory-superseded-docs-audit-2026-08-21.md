# Superseded-docs audit from the 2026-08-21 portability sweep

Moved here from `docs/confirmed-facts/INVENTORY.md` on 2026-09-04 (doc cleanup board
`jus-iaoc`): this is a dated audit of which research pages carried refuted or superseded
banners at sweep time, i.e. history, not a current fact. The banners on the pages
themselves are the live record; `docs/research/README.md` lists the current set.


Verified against banners and `README.md` §"Documents currently marked refuted or superseded":

| Doc | Status |
|---|---|
| `../research/archive/Damage-Reduction-Is-Flat.md` | ⛔ REFUTED banner confirmed. Reduction is ×0.75 per gate (`jus-reduction-is-quarter-multiplier-xk1`); its DOWN+B 5.000 row is wrong (5.250). |
| `../research/archive/Combat-Mechanics.md` | Superseded-style: bare "CONFIRMED" prose, flat-reduction language, multiplicative composition. **Nuance:** its 1.5× nature claim is RIGHT and was restored (the 2026-08-19 refutation banner was itself the error — read the corrected banner). |
| `../research/archive/Combat-Mechanics-Reference.md` | Same as above. |
| `../research/archive/Menu-Nav-Oracle-Attempt-1.md` | 📕 Superseded banner confirmed; replaced by `../harness/Menu-Nav-Verified-From-Pixels.md`. Kept as failed-experiment record. |
| `findings/defence-candidates-ruled-out.md` | ⛔ REFUTED banner confirmed (reduction is not ability 0x09; `jus-w66`). |
| `../research/archive/Research-Status.md` | 📕 Unmaintained banner confirmed. Cites four tracker items that no longer exist (named in its own top banner); its "nature ×1.5 refuted" line is now wrong. |
| **Extensions found by this sweep:** | |
| `../research/archive/Move-Damage-Table-Goku.md` | Numbers superseded by heal-off re-measurement (B = 8.000 not 6.000); button labels wrong per owner (`jus-hbmn`). |
| `HP-And-Damage-Runtime-Findings.md` §2b | Self-superseded (HP formulas dead; struct now in `HP-Struct-From-Disassembly.md`). Keep §1 (1/64 encoding) and §2d warning. |
| `../research/archive/Nature-Damage-Controlled-Test.md` | Measurement valid, generalisation dead — superseded banner added 2026-08-21 (without it a standalone reader got the wrong answer). |
| `Damage-Path-Codex-Findings.md` §1 | Caller-1 ×0.5 refuted (P182). §2 (ability bitset) still stands. |
| `Passives-Reference.md` helper section | Superseded by `Helper-Passives-Catalog.md` (42 owner categories vs ~20 GameFAQs). Battle section still canon. |
| `findings/contact-array-is-not-a-damage-ledger.md` | Headline superseded by P208/P209 — its dismissed "sole producer" IS the damage formula. |
| **G1 tooling scope:** | The PyGhidra layer mitigates the Thumb and cross-Program blind spots only for the 25 claims and query types recorded in `../research/Thumb-Negative-Claim-Audit.json`. Its result was 7 confirmed, 5 contradicted, and 13 inconclusive; this bounded sweep is not a global all-clear. |
| `findings/player-slot-partial-field-map.md` | Superseded by `findings/player-slot-sp-total-at-0x5c8.md`. |
| `findings/char-0x1b4-is-a-per-player-array-slot.md` | Superseded by `findings/char-0x1b4-is-a-comicdeck-player-slot.md`. |
| `findings/shot-data-and-projectileid-refuted.md` | Superseded by `findings/projectileid-is-a-selector-not-an-index.md`. |
| `findings/nature-base-plus-override.md` | Mechanism corrected by `findings/nature-SOLVED.md`. |
| `findings/koma-format-decoded.md` (nature-negative headline only) | Overturned by `nature-SOLVED.md`; field map stands. |
| `Multi-Hitbox-Mechanics.md`, `DamageFlags-Character-Classification.md` | Not refuted, but Feb-2026 bare-"CONFIRMED" prose with no tracker items — treat as unverified per README rule. |
| `ARM9-Research-Guide.md` | Carries corrected notes re the `0x020924B0` "collision file pointer table" error; cite the corrections, not the original text. |

---
