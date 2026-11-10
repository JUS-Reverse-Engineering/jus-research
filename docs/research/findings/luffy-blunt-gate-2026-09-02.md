# Luffy blunt ×0.75 gate — resolved as a stale decode (2026-09-02)

Tracker item `jus-luffy-blunt-resist-source-92l3`. Static worker report (Sonnet), verified by the orchestrator: `chr_b.bin` record 12 bytes +0x03..+0x07 = `09 19 00 00 0c` (read directly). Ability 9 is present; the tracker item premise quoted a pre-`jus-ondisk-ability-list-at-chrb-0x03-kfc` decode.

# Luffy's blunt x0.75 — source found: tracker item premise was based on a stale decode

Tracker item `jus-luffy-blunt-resist-source-92l3`. Verdict up front: **(d)-adjacent, but
not "the resist gate itself is misread" — the *chr_b ability list* was
misread.** Ability 9 (打撃耐性ＵＰ, blunt resistance) IS on Luffy's on-disk
chr_b record. The "no ability 9" premise in the tracker item description comes from
quoting a retracted line in `HP-And-Damage-Runtime-Findings.md` / an earlier
32-bit "flags word" decode that predates the byte-accurate read done in the
already-CLOSED tracker item `jus-ondisk-ability-list-at-chrb-0x03-kfc`. That tracker item
already answers this question; this report re-derives and cross-checks it.

## 1. The resist gate itself (already correctly documented)

`docs/confirmed-facts/damage.md` §4 is accurate and I re-derive the same
numbers below. Verbatim disassembly of the ±25% (x0.75 via subtraction)
gate that matters here, from `0x020823E4`:

```
0x02082574  ldr  r2, [r8, #0x44]        ; gate word, r8 = victim scratch
...
0x02082608  tst  r2, #0x1000            ; bit 12, ability 12 -> ADD, class==1
0x02082624  tst  r2, #0x2000            ; bit 13, ability 12 -> ADD, class==2
0x02082644  lsleq r4, r5, #6
0x0208264c  subeq r0, r0, r4, asr #8    ; bit 4 (0x10), class==1: r0 -= r5/4
0x02082674  ...                        ; bit 5 (0x20), class==2: r0 -= r5/4
0x02082678  add  r0, r5, r0            ; base + (nature + gates)
0x0208267c  asr  r1, r0, #2            ; 8.8 -> raw/64
```

`r5` is `base<<8` (scaled by f1/f2, both 1.0 in every capture). Each fired
gate is exactly `r5 >> 2` = 25% of the scaled base, additive into `r0`, not
multiplicative — see damage.md §1/§4 for the full derivation. One `-25%`
gate on base 7 (`r5=1792`) gives `out = (1792-448)>>2 = 336` raw =
**5.250** displayed — test vector #8 in damage.md §7, sourced from
`jus-reading-max-hp-not-current-2jo`. This is exactly the 5.25 the tracker item
cites for Luffy vs Kenshin B.

The class-index table (`0x02092E68`, 16 bytes) that turns the move's class
byte into a gate category:

```
01 01 02 02 02 02 02 02 02 02 02 02 00 00 00 00
```

index 0-1 -> category 1 ("blunt" gate pair: sub bit4/add bit12), index 2-11
-> category 2 ("slash" gate pair: sub bit5/add bit13), index 12-15 ->
category 0 (immune to both class gates).

## 2. What sets bit 4 in the victim's gate word

`docs/confirmed-facts/damage.md` §5 + closed tracker item
`jus-ondisk-ability-list-at-chrb-0x03-kfc` / `jus-one-routine-assembles-both-u24`:
the on-disk chr_b ability list (`chr_b record + 0x03`, 5 sparse bytes) is
loaded, cached as a bitset at `battleObj+0x128` (loader `0x0215FB3C`), then
ov6 `0x02157114` maps ability id -> (maskIdx, variant) via a 12x3 table at
ov6 `0x021710BC` and ORs the corresponding bit into `[target+0x44]` via
`arm9 0x02083BE0`. The mapping for the class-1 (blunt) pair is:
**ability 9 -> bit 4 (subtract/resist), ability 12 (=0x0C) -> bit 13
(add/weakness, class 2)**. This was measured live and predicted exactly:
gate word `0x00002010` for ability list `[9, 25, 12, 14]`
(`jus-gate-word-read-live-0x2010-nbz`, CLOSED, RUNTIME-confirmed).

That measured ability list, `[9, 25, 12, 14]`, **is Luffy's list**. It
matches the runtime ability array documented for Luffy everywhere else in
this project (chr_b index 12, runtime appends id 14 = latent power). So the
gate-word derivation that proves bit 4 fires for a "blunt resist" character
was run *against Luffy himself* — the tracker item's question was already answered
by a different, already-closed tracker item, just not linked back to this one.

## 3. Reading the chr_b record directly (this session, static)

Read `jus_files/ripped_jus_files/bin/chr_b.bin`, record size `0x3C` (74
records), ability window `record[0x03:0x08]` (5 bytes, sparse, zeros =
empty slot, per `jus-ondisk-ability-list-at-chrb-0x03-kfc`):

```python
data = open("jus_files/ripped_jus_files/bin/chr_b.bin","rb").read()
rec = 0x3C
for idx in (0, 12, 15, 17, 18):
    window = data[idx*rec+3 : idx*rec+8]
    print(idx, list(window))
```

Result (the file names in parentheses were corrected 2026-10-13: Franky `op_b_08` -> `op_b_06`,
Gear 2 Luffy `op_b_02` -> `op_b_07`; the window bytes are chr_b.bin rows and are unaffected):

| chr_b idx | character         | window bytes            | ability ids       |
|---|---|---|---|
| 0  | Goku (`db_b_01`)        | `07 0f 00 00 00` | 7, 15 |
| 12 | **Luffy** (`op_b_01`)   | `09 19 00 00 0c` | **9**, 25, 12 |
| 15 | Nami (`op_b_04`)        | `10 03 2a 00 18` | 16, 3, 42, 24 |
| 17 | Franky (`op_b_06`)      | `0a 17 29 00 14` | 10, 23, 41, 20 |
| 18 | Gear 2 Luffy (`op_b_07`)| `09 19 00 00 0c` | **9**, 25, 12 (identical to Luffy) |

Character identities read from `docs/research/chr_b-Complete-Mapping.md`
(chr_b 12 = Luffy, 15 = Nami, 17 = Franky — table confirms all three; the
mapping doc flags an earlier collision-file-order mixup as fixed, and these
three rows are unaffected by that correction).

**Luffy (and Gear 2 Luffy) carry ability 9 on disk. Nami and Franky do
not.** Nami carries 16/3/42/24 — none map to bit4/bit5 (checked against the
carrier census in `jus-ondisk-ability-list-at-chrb-0x03-kfc`: ability 9's
only carriers are records `[12, 18, 67]`, ability 10 (slash-resist, bit5)
carriers are `[17, 56, 67]`). Wait — Franky's window shows id `10` (`0x0a`)
present, which *is* the slash-resist id (bit5, class 2) — consistent with
Franky's file-format `charId`/class data and with damage.md's separate,
unrelated weight-passive note (heavyweight, bit7, is a different mask
index, mask index 3, and not part of this gate pair). Franky's ability 10
does not affect a *blunt* (class-1) hit, so it doesn't contradict the
Kenshin-B result — Franky still takes the un-resisted 7.0 from a blunt hit
because his resistance is on the slash side, not blunt.

I did not have a stored Goku-vs-Kenshin-B measurement to compare, so Goku
is reported for completeness only (ids 7, 15 — no bit4/bit5 carrier ids
here either; per damage.md test vectors, Goku's own gate hits in captures
are id 9/12, i.e. those were Luffy's or a shared-ability character's, not
Goku's — Goku was the *attacker* in `jus-gate-word-read-live-0x2010-nbz`,
not the resistor).

## 4. The attacker side: Kenshin's move class byte

Kenshin = chr_b 36 (`rk_b_01`), per `chr_b-Complete-Mapping.md`. Collision
data from `jus_files/exported_combat/rk_b_01_collision.json` (29 entries).
The field is `damageFlagsLow` = the move-data class-index byte (`+0x0E` low
6 bits), confirmed in damage.md §2.1/§6 to be the same field the community
doc called "damageFlags" (`jus-class-index-is-damageflags-mx5`). Sample of
Kenshin's early physical-hit entries (his sword/saya normals, frame-start
6–8, non-terminator):

```
damageFlagsLow: 0, 0, 0, 0, 0, 1, ...
```

All are 0 or 1 -> class table `01 01 ...` -> **category 1**, the same
category gated by bit4 (ability 9, resist) / bit12 (ability 12, weakness).
I did not isolate which specific entry index is "B" vs Kenshin's other
normals from the JSON alone (no move-name field in this export), but every
early physical entry in the dump is category 1, so Kenshin B being a
category-1 (blunt-class) hit is consistent with, not contradicted by, this
data. This piece is the weakest link in the chain — falsifiable per §6
below.

## 5. Verdict

The tracker item's four candidates:
- (a) per-character class/nature field outside the ability list — **not
  needed**, ruled out by §3: the ability list itself, read correctly,
  already contains id 9.
- (b) ability-table off-by-one — **this is effectively what happened**,
  but the off-by-one was in an *earlier decode of the chr_b bytes*
  (a naive contiguous-bytes/flags-word read that missed the sparse zero
  gap `09 19 [00 00] 0c`), not in the code's ability-id numbering. The
  code's id->bit mapping (id 9 -> bit 4) is correct and already confirmed
  live.
- (c) koma/deck-granted — not needed; no deck/koma read required, it's
  baseline chr_b.
- (d) damage.md's resist-gate decode is wrong — **no**, damage.md §4/§5 is
  self-consistent and reproduces 5.25 exactly from the recorded gate
  arithmetic.

**Verdict: (b)-flavored, resolved.** Luffy's x0.75 vs Kenshin B is ability 9
(blunt resistance UP), present on-disk at chr_b record 12 bytes
`+0x03..+0x07 = 09 19 00 00 0c`, compiled at load time into gate-word bit 4
of his battle-object scratch (`[r8+0x44]`), fired against Kenshin's
category-1-class hit. This closes the tracker item; no runtime work is strictly
required, but §6 gives a cheap confirming test since the chain has never
been observed end-to-end against Kenshin specifically (the confirmed gate
word 0x2010 measurement used Goku as attacker, not Kenshin).

Confidence: HIGH on chr_b bytes and the id->bit mapping (both re-derived
here and independently confirmed by two prior closed, cross-checked
tracker items). MEDIUM on Kenshin's B move specifically being class-index 0/1
(inferred from the collision JSON's early entries, not from a
move-name-labeled field).

## 6. Falsifiable runtime prediction

Attach during a Luffy-defends-vs-Kenshin-B rep (same setup as the existing
5.25 measurement, `weight-hunt-2026-09-01c`). Break at `0x02082584`
(damage.md's confirmed hit-oracle) and read `r2 = [r8+0x44]` where `r8` is
Luffy's ColPrm scratch:

- **Prediction:** `r2 & 0x10` (bit 4) is set, `r1` (class index from
  `[[sl+0x10]+0x0E]`) resolves via the class table to category 1, and
  `0x0208264C` (`subeq r0, r0, r4, asr #8`) executes (its `eq` condition is
  satisfied). `out = 336` raw = 5.250 displayed, matching the existing
  measurement.
- **Poke test:** clear bit 4 at `[r8+0x44]` (AND with `~0x10`) immediately
  before the swing lands, leaving everything else unchanged. Expected
  effect: the same Kenshin B hit now reads `out = 448` raw = **7.000**
  displayed on Luffy — matching Nami/Franky exactly — because the only
  thing distinguishing Luffy's damage taken from theirs in this formula is
  that one bit.
- If instead damage stays at 5.25 with bit 4 cleared, that would falsify
  this report's chain and reopen the tracker item — but this specific bit/gate
  pairing was already confirmed live once (`jus-gate-word-read-live-0x2010-nbz`,
  albeit as attacker-side observation, not a before/after poke), so a clean
  failure here would be a genuinely new and important result.
