# Special-damage resistance passive — ability id, gate bit, and site

Grade: **CONFIRMED, static + live**. Tracker item `jus-ehcp`. Answers "which ability,
which field, where in the damage formula does a special land at 0.75× on a
victim carrying it," and, as of the "Live" section below, confirms the
mechanism causally against real hits rather than static disassembly alone.

## The answer

- **Ability id 13**, kind 0 (appends to the runtime ability id list, cached
  as a bitset at `battleObj+0x128`), Japanese 見切り, English gloss "Less
  damage from Specials" / "Evasion" (`docs/confirmed-facts/helpers.md` §7;
  `docs/research/findings/abilities-all-57-named.md`).
- **Jotaro is a direct carrier**, not a helper pass-through: `chr_b` record
  28's on-disk ability list (record `+0x03`, five sparse bytes) includes id
  13 directly (`docs/research/gate-ability-test-matrix.md` §2 carrier
  census: "13 | 21 Sasuke, 23 Kakashi, **28 Jotaro**, 54 Tsuna, 61 Kenshiro,
  62 Raoh, 63 Seiya, 64 Gold Seiya"). This settles the open half of
  `jus-ehcp`'s comment thread ("look for the ability id in Jotaro's deck") —
  it is on Jotaro's own record, no koma-adjacency helper needed.
- **Field it sets**: the ability→gate-bit assembler (ov6 `0x02157114`,
  documented in `damage.md` §5 / `p213`) reads a 12×3-byte table at ov6
  `0x021710BC`. Row 4 of that table is `0D 02 01` = `(id=13, maskIdx=2,
  variant=1/subtract)`. Re-read fresh from the binary for this task via
  `scripts/analysis/rom_loader.py` (`mm.read(0x021710BC, 36, overlay="ov6")`)
  and confirmed byte-identical to the table already quoted in
  `p213-flag-word-is-plus-0x44-ability-10-sets-bit-5.md` and
  `gate-ability-test-matrix.md` §1 — three independent transcriptions now
  agree. `variant=1` selects the subtract mask table `0x02092E78` (bits
  4..9); `maskIdx=2` is word index 2 of that table = bit **6** (`0x40`).
  Handler `0x02083BE0` ORs that bit into **`[[battleObj+0x1a8]+0x10]+0x44`**
  — the victim-side gate word, same field documented in `damage.md` §2.2 as
  `[r8+0x44]`.
- **Formula site**: `arm9 0x020825AC`–`0x020825E0`, inside the six-gate block
  of `0x020823E4` (`damage.md` §4 Step 4). `tst r2, #0x40` (bit 6 of the
  gate word, loaded once at `0x02082574`); if set and the "is a special"
  predicate holds, `sub r0, r0, r4, asr #8` where `r4 = r5<<6` — i.e.
  `r0 -= r5/4`, exactly one of the six ±25% gate terms (`damage.md` §4 table
  row `0x020825DC | bit 6 | element cond. | − r5/4`). This lands in the
  additive accumulator `r0`, combined into `out = (r5 + r0) >> 2` at Step 5
  — a **flat −25% of the scaled base**, not a separate multiplicative 0.75
  on the whole hit. With no other gate armed and no nature bonus, `out =
  (r5 - r5/4)/4`, which is the same number a naive "×0.75" reading would
  predict for this one term, but the mechanism is additive-into-r0, per
  `damage.md`'s existing warning about nature+gates not compounding
  multiplicatively.

## How "is a special" is determined (the predicate, disassembled)

```
0x02082570  ldr   r3, [sl, #0x10]     ; r3 = moveData pointer
0x02082574  ldr   r2, [r8, #0x44]     ; r2 = victim gate word (loaded once)
0x02082580  ldrsb r1, [r3, #0xe]      ; class index (range-checked 0..15 elsewhere)
0x02082584  ldrb  r4, [r3]            ; r4 = moveData[+0x00], the "kind" byte
...
0x020825AC  tst   r2, #0x40           ; bit 6 (ability 13's gate)
0x020825B0  beq   0x20825e0           ; skip if bit clear
0x020825B4  cmp   r4, #4
0x020825B8  cmpne r4, #5
0x020825BC  beq   0x20825cc           ; kind==4 or kind==5 -> fire directly
0x020825C0  ldr   r3, [sl, #0x14]     ; else fall back to the hit-element flags byte
0x020825C4  tst   r3, #0xf0
0x020825C8  beq   0x20825e0           ; neither -> gate does not fire
0x020825CC  ...                        ; fire: r0 -= r5/4
```

So the classifier is **`moveData+0x00` (the same byte `move_records.py`
already calls "kind", documenting "0=plain box (no damage), 3/4/5 seen on
attacks")**, values 4 or 5 = "this hit is a special." If the kind byte is
neither 4 nor 5, the code falls back to `[hitElement+0x14] & 0xF0` (the
element-flags high nibble already named in `damage.md` §2.1 as feeding "the
bits-6/14 element condition"). The fallback is an OR, not an AND, and is
short-circuited — kind 4/5 never even reads `+0x14`. This is the same
"element condition" already named in `damage.md` §4 for both gate bit 6
(ability 13, subtract) and gate bit 14 (ability 21 直撃, add, the mirror-image
"more damage from specials" weakness) — one shared predicate function serves
both gates, which is why the table stores them at the same `maskIdx` (2).

This matches `docs/research/gate-ability-test-matrix.md` §3, which already
listed bit 6 as "armed by 13 見切り … fires when element cond. (specials) …
−25% … status: untested" — this task's static disassembly is the same
mechanism, confirmed a second way (fresh table read + fresh predicate
disassembly + an independent codex pass), and narrows "untested" to
"mechanism confirmed static; live positive/negative control still open."

## Second opinion (codex, neutral framing)

Ran `codex exec -m gpt-5.6-sol` against the raw disassembly with variables
renamed generically (r0/r1/r2/r4/r5/r6/sl, no mention of "ability",
"special", "Jotaro", or "0.75") and three neutral questions: what boolean
condition gates the subtraction, whether the kind-byte and flags-byte tests
are AND'd or OR'd, and what fraction of `r5` is subtracted. Full
prompt/answer: `prompt.txt`,
`answer.txt`.

Codex's independent read: `(r2 & 0x40) != 0 AND (r4==4 OR r4==5 OR
([sl+0x14]&0xF0)!=0)`, kind-byte cases short-circuit before the flags-byte
test is ever evaluated, and the subtracted magnitude is `(r5<<6) asr 8 ≈
r5 asr 2`, i.e. r5/4. No disagreement with the reading above.

## Live confirmation (2026-09-12, `jus-ehcp` LIVE HALF)

**No cached savestate pairs Jotaro himself as the defender against the same
attacker on both a carrier and a non-carrier victim** — every state that
names Jotaro as the opponent (`pc-*-npc-jotaro-dark-tournament`) uses a
*different* P1 attacker deck per state, and this session's own measurement
found that **reloading a savestate resets the active koma to deck slot 0**,
not whatever was active when the state was saved (the `pc-yusuke-npc-jotaro`
and `pc-yusuke-npc-nami` states, both documented in INDEX.md as "Yusuke
active," in fact reload as Taikoubou and Momotaro respectively — deck slot 0
in each case; INDEX.md lines 45 and 56 still read Yusuke active and are NOT
corrected here (out of this task's touched-files scope) — the label
described save-time state, not reload-time state). No same-
attacker, Jotaro-vs-non-carrier pair exists among the stored states.

**Substitution used instead:** Raoh (`chr_b` 62), the nearest available
carrier of the identical ability id 13 (same carrier list in this doc's §
above — Sasuke, Kakashi, Jotaro, Tsuna, Kenshiro, Raoh, Seiya ×2), paired
against Nami (`chr_b` 15, non-carrier of any damage-gate ability) as the
defender, with the **same attacker both times** — P1 resets to `chr_b` 28
(Jotaro, JJ deck slot 0) on reload of every `pc-kenshin-npc-*-dark-tournament`
state, so this pairing incidentally uses Jotaro *as the attacker*, which is
irrelevant to his own defensive gate but confirms the reload-quirk finding a
second way.

**Method.** One scripted plan (approach, `B`, `B`, `Y`, `X`) run against
`pc-kenshin-npc-raoh-dark-tournament` and `pc-kenshin-npc-nami-dark-tournament`,
GDB breakpoint at arm9 `0x02082588` — one instruction past this doc's own
`0x02082584` kind-byte load, so `r4` (kind byte), `r2` (gate word, already
loaded at `0x02082574`), `r3` (moveData pointer), and `r5` (scaled base) are
all live registers at the stop. Positive control: opponent HP word
(`0x021df7f0`) changed on every run.

**Result.** Raoh's gate word read `0x0040` (bit 6 armed, no other damage-gate
bit) on every one of 12 landed hits; Nami's read `0x8100` (bits 8/15, neither
a damage-gate bit per §4's table — bit 8 is ability 16 収集, bit 15 is
ability 24 軽量級, both unrelated to this mechanism) on all 11. The two runs
share eleven hits plus one extra Raoh jab (Raoh's first hit, a kind-3 jab,
has no Nami counterpart — the same plan's first `B` whiffed on Nami, whose
state starts P1 farther from the victim; see the RESULTS doc), so the two
capture sets are the same move sequence against two different defenders,
not a hit-for-hit reproduction. Feeding each hit's captured
`(r2, r4, r5)` back through damage.md §4's own arithmetic — subtract `r5/4`
when `r4` is 4 or 5 and bit 6 is set, otherwise add nothing — and summing
over the whole run reproduced the *measured* aggregate HP delta exactly on
both sides: predicted 2592 raw (40.500 displayed) vs. measured 12288→9696
(Δ2592) on Raoh; predicted 2688 raw (42.000 displayed) vs. measured
8704→6016 (Δ2688) on Nami. Zero residual on either side. The one shared
kind-3 (normal) hit in both runs used an identical `moveData` pointer and
`r5`, and both resolved to the same undiminished value (512 raw / 8.000
displayed) — bit 6 read armed on Raoh but did not fire, because the kind
byte fails the element-condition test for a kind-3 hit, exactly as this
doc's static predicate predicts. Full table, conditions block, and the
reload-quirk measurement: the RESULTS doc.

This settles the "Not yet done" item below in substance (causal
positive/negative control on the identical ability, a substituted carrier
standing in for Jotaro) even though it does not literally exercise Jotaro's
own record as the defender — no cached state makes that possible with a
repeatable same-attacker pair, per the reload-quirk finding above.

## Not yet done (still open; not run this task)

- **Jotaro himself as the measured defender** in a same-attacker pair is
  still open — it needs a fresh pair of savestates (not the cached ones)
  built with the *same* P1 deck against Jotaro and against a non-carrier,
  saved and reloaded once to confirm the active koma survives the
  slot-0 reset (e.g. by making the desired attacker deck slot 0 itself).
- Whether `moveData+0x00` kind values 3 vs 4 vs 5 map onto specific named
  move categories (e.g. distinguishing an X move from a charged/EX variant)
  is not established by this task; only that 4 and 5 both trip the "is a
  special" predicate while (implicitly) 3 does not, per the field's existing
  comment in `move_records.py` ("0=plain box, 3/4/5 seen on attacks").

## Provenance

Static half: `arm9.bin` disassembly via `python3
scripts/analysis/query.py disasm ... ` (unambiguous, arm9 region) for
`0x02082560`–`0x0208267C`. Table bytes at ov6 `0x021710BC` re-read via
`scripts/analysis/rom_loader.py` (`load_memory_map().read(...,
overlay="ov6")`), independent of both the listing text and the two prior
transcriptions in `p213` and `gate-ability-test-matrix.md` — all three now
agree byte-for-byte. Ability catalog entry and kind/append mechanics from
`docs/confirmed-facts/helpers.md` §3, §7. Carrier census from
`docs/research/gate-ability-test-matrix.md` §2 (chr_b 28 = Jotaro, `INDEX.md`
JJ deck `[28, 14, 36, 46]`). Codex second opinion per HANDOFF's
mandatory-by-default policy, neutral framing, cold-asked.

Live half (2026-09-12, same tracker item, "Live confirmation" section above):
`scripts/gdb/run_experiments.py` batch on `pc-kenshin-npc-raoh-dark-tournament`
and `pc-kenshin-npc-nami-dark-tournament`, one melonDS launch each
(hygiene required a relaunch between the two probes after the first
attempt's Nami run failed to land — see RESULTS.md's Concerns), holder
`ehcp`, one GDB attach per launch. Raw specs, compiled `.gdb` files, and
results JSON referenced from
the RESULTS doc.
