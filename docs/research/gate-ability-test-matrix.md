# Gate-ability test matrix — the 12 rows behind the ±25% damage gates

Asset for the settle-or-waive decision on the damage gate bits
(tracker item `jus-map.12`). Static mining only; no emulator.

Sources: [p213](findings/p213-flag-word-is-plus-0x44-ability-10-sets-bit-5.md),
[p227](findings/p227-kind2-abilities-are-stat-modifiers.md),
[abilities-all-57-named.md](findings/abilities-all-57-named.md),
[ability-descriptions-57.txt](findings/ability-descriptions-57.txt),
[chr_b-Complete-Mapping.md](chr_b-Complete-Mapping.md).
Tracker items cited inline. Table bytes re-read from disk for this doc, not copied
from p213.

## 1. The 12×3 table, dumped fresh

Read from `jus_files/overlays/ov06.bin` at file offset `0x2439C`
(= runtime `0x021710BC` − load base `0x0214CD20`, base from
`jus_files/overlays/overlays.json`: `ram_address` 34917664). Raw bytes:

```
09 00 01  0B 00 02  0A 01 01  0C 01 02  0D 02 01  15 02 02
10 04 01  11 04 02  12 05 01  13 05 02  17 03 01  18 03 02
```

Byte-identical to the table quoted in p213. Decoded with the mask tables
(`0x02092E78` = bits 4..9 subtract, `0x02092E90` = bits 12..17 add;
variant 1 = subtract table, variant 2 = add table):

| row | ability id | maskIdx | variant | gate-word bit | name (JP / gloss) | read by damage routine? |
|---|---|---|---|---|---|---|
| 0 | 9 | 0 | sub | **4** | 打撃耐性ＵＰ / Blunt resistance UP | yes |
| 1 | 11 | 0 | add | **12** | 打撃弱点 / Blunt weakness | yes |
| 2 | 10 | 1 | sub | **5** | 斬撃耐性ＵＰ / Slash resistance UP | yes |
| 3 | 12 | 1 | add | **13** | 斬撃弱点 / Slash weakness | yes |
| 4 | 13 | 2 | sub | **6** | 見切り / Evasion (less damage from Specials) | yes |
| 5 | 21 | 2 | add | **14** | 直撃 / Direct hit (more damage from Specials) | yes |
| 6 | 23 | 3 | sub | 7 | 重量級 / Heavyweight (knockback shorter) | no |
| 7 | 24 | 3 | add | 15 | 軽量級 / Lightweight (knockback longer) | no |
| 8 | 16 | 4 | sub | 8 | 収集 / Collection (more SP from coins) | no |
| 9 | 17 | 4 | add | 16 | 浪費 / Waste (less SP from coins) | no |
| 10 | 18 | 5 | sub | 9 | 調理 / Cooking (more HP from food) | no |
| 11 | 19 | 5 | add | 17 | 大食い / Big eater (less HP from food) | no |

### In-game descriptions (from ability-descriptions-57.txt)

- **9** 打撃耐性ＵＰ: 「相手から受けるパンチやキックなどの打撃ダメージが軽減される能力。」
- **11** 打撃弱点: 「打撃攻撃を受けた時のダメージが少し大きくなってしまうマイナス能力。」
- **10** 斬撃耐性ＵＰ: 「剣や刀の相手からの斬られるダメージが軽減される能力。」
- **12** 斬撃弱点: 「剣や刀の相手からの斬られるダメージが**軽減される**能力。」 —
  note: this is the *same "reduced" text as ability 10*. The name says
  weakness, the description says reduced. Looks like a copy error in the
  game's own text data; the code adds (bit 13, add table) regardless.
- **13** 見切り: 「相手の必殺技で受けるダメージが軽減される能力。」
- **21** 直撃: 「必殺技で受けるダメージが大きくなってしまうマイナス能力。」
- **23/24** 重量級/軽量級: knockback distance shorter/longer.
- **16/17** 収集/浪費: SP gained from coins bigger/smaller.
- **18/19** 調理/大食い: HP recovered from food bigger/smaller.

### Owner-context flags

The owner (experienced player) reports no passive is visibly described in
the UI as "damage up/down vs a class". Two findings, recorded as findings
and not errors:

1. **Rows 0–5 do carry class-damage wording in the JP text** — blunt
   ("punches and kicks"), slash ("swords and blades"), and specials. If the
   owner played a localization or skimmed menus, the wording may not have
   surfaced; either way the disk text and the code agree here.
2. **Rows 6–11 sound completely unrelated to damage** (knockback, coins,
   food) — and that is *consistent*: the damage routine only reads bits
   4/5/6 and 12/13/14. Bits 7–9/15–17 exist in the same gate word but are
   consumed elsewhere (unlocated; damage.md §5). The "+0x44 word" is a
   general passive-flag word, not a damage-only word. Mismatched names for
   those rows are expected, not suspicious.

The extracted battle-character passive reference supplies these descriptions,
which are useful as a runtime identity check when selecting the target deck:

| fighter | owner-reported passives |
|---|---|
| Momotaro (`chr_b 67`) | takes less damage from Kick/Punch attacks; takes less damage from Sword attacks; SP gauge decreases when not fighting |
| Edajima (`chr_b 66`) | Solid Stance (hard to move when attacked); gains SP energy when KOing opponents |

These descriptions reinforce that Momotaro and Edajima are distinct fighters;
they are context for the live test, not a substitute for the runtime
`+0x29`/`+0x41` identity proof.

### MOMO deck context

The owner created a new deck named **MOMO** in visible deck-list position 6.
Its live runtime roster is `[67,68,32]`: Momotaro, Taikoubou, and Yusuke. The
saved target state is `ds8t_momo_battle_noheal`.

Owner-provided panel and attack notes:

- Momotaro 6-koma ALT: the panel's attacks deal Knowledge damage, while its
  specials still deal Power damage; Power is Momotaro's normal nature. His X
  special is a persistent energy beam while it is being fired.
- Yusuke 6-koma: X fires a large, very high-priority projectile that consumes
  many other projectiles on contact.
- Taikoubou: a summoner; many Y moves create another character sprite that
  behaves like a projectile. Neutral Y creates a downward slash whose hitbox
  behaves like a battle/support character, including stopping attacks that stop
  on those characters and slowing fighters who walk through it.

The MOMO state therefore supports both the gate-resistance run and a later
beam/projectile distinction run. The attack nature and summoned-hitbox notes
are owner observations, not yet engine classifications.

## 2. Carrier census (chr_b record +0x03, five sparse bytes)

Scanned all 74 records of `jus_files/ripped_jus_files/bin/chr_b.bin`
(74 × 60 B; list layout per tracker item `jus-ondisk-ability-list-at-chrb-0x03-kfc`,
p223). Names from chr_b-Complete-Mapping.md.

| ability | carriers (chr_b: name) |
|---|---|
| 9 | 12 Luffy, 18 Gear 2 Luffy, **67 Momotaro** |
| 11 | **none** — orphan, matches p227's inert-id list |
| 10 | 17 Franky, 56 Arale, **67 Momotaro** |
| 12 | 12 Luffy, 18 Gear 2 Luffy |
| 13 | 21 Sasuke, 23 Kakashi, 28 Jotaro, 54 Tsuna, 61 Kenshiro, 62 Raoh, 63 Seiya, 64 Gold Seiya |
| 21 | 47 Bo-bobo, 48 Don Patch, 49 Shinsetsu, 50 Super Patch |
| 23 | 17 Franky, 58 Caramelman, 66 Edajima |
| 24 | 15 Nami, 19 PCT Nami, 27 Anna, 37 Eve, 41 Rukia, 43 Hitsugaya, 46 Lenalee, 59 Muhyo, 69 Fuusuke |
| 16 | 15 Nami, 19 PCT Nami, 27 Anna |
| 17 | 31 Killua, 51 Ryotsu |
| 18 | 14 Zoro |
| 19 | 10 Frieza, 53 Kagura |

The runtime reconciliation in chr_b-Complete-Mapping.md corrects the former
row labels. In particular, record 66 is Edajima and record 67 is Momotaro;
record 21 is Sasuke, record 24 is Kyuubi Naruto, and record 17 is Franky.

**Every row except ability 11 has at least one carrier.** Ability 11
(打撃弱点 → bit 12, add, class 1) is carried by no character — the only
one of the six damage-readable bits that cannot be armed from a stock deck.

## 3. Test matrix for the six readable bits

Firing conditions per damage.md §4: class table `0x02092E68` maps the
attack's element class index → category (indices 0–1 → cat 1 "blunt",
2–11 → cat 2 "slash", 12–15 → cat 0 immune). Bits 6/14 use the element
condition instead: element type 4 or 5, else `[sl+0x14] & 0xF0` (specials).

| bit | armed by | carriers (deck options) | fires when | effect | status |
|---|---|---|---|---|---|
| 4 | 9 打撃耐性ＵＰ | Luffy, Gear 2 Luffy, **Momotaro** | class cat == 1 | −25% of base | **live-confirmed** (`jus-gate-word-read-live-0x2010-nbz`) |
| 5 | 10 斬撃耐性ＵＰ | Franky, Arale, **Momotaro** | class cat == 2 | −25% | **live-confirmed** (`jus-bit5-fired-and-nature-observed-w5n`; earlier untested per `jus-bit5-ability-10-untested-mvk`) |
| 6 | 13 見切り | Sasuke, Kakashi, Jotaro, Tsuna, Kenshiro, Raoh, Seiya ×2 | element cond. (specials) | −25% | **live-confirmed** (jus-ehcp, carrier substituted: Raoh) |
| 12 | 11 打撃弱点 | **nobody** | class cat == 1 | +25% | **uncoverable from stock decks** |
| 13 | 12 斬撃弱点 | Luffy, Gear 2 Luffy | class cat == 2 | +25% | armed-but-blocked observed live (cat 1 hit); firing untested |
| 14 | 21 直撃 | Bo-bobo, Don Patch, Shinsetsu, Super Patch | element cond. (specials) | +25% | untested |

**Cheapest carrier: chr_b 67 Momotaro**, ability slots `[9, 10, 0, 0, 56]` —
arms bits 4 **and** 5 in one fighter. The saved EDA deck's `chr_b 66`
Edajima has `[23, 6, 45]` instead, so it is not the bit-4/5 target despite
the former matrix labeling it as one.

## 4. Suggested live session plan

Minimal coverage of all six readable bits, three decks:

1. **A deck containing Momotaro (chr_b 67)** as target. One blunt (cat-1) hit →
   bit 4 fires (−25%); one slash (cat-2) hit → bit 5 fires (−25%). Both
   already live-confirmed; re-running them is a free sanity anchor,
   `[r8+0x44]` should read `0x0030`.
2. **Deck B — Luffy (chr_b 12)** as target (abilities `[9, 25, 12]`,
   gate word predicts `0x2010`). One cat-2 (slash) hit → **bit 13 fires**
   (+25%) — the add path, never yet seen firing. Same capture with a cat-1
   hit reproduces the armed-but-blocked observation in reverse (bit 4
   fires, bit 13 blocked).
3. **Deck C — any 見切り carrier (e.g. Jotaro, chr_b 28) vs any 直撃
   carrier (e.g. Don Patch, chr_b 48)**. Land one special each way:
   special into Jotaro → **bit 6** (−25%); special into Don Patch →
   **bit 14** (+25%). One match covers both element-condition gates.

Total: 3 decks, ~6 landed hits (breakpoint `0x02082584` is a hit oracle,
tracker item `jus-first-attributed-measurement-d6u`).

### Waive candidates

- **Bit 12 (ability 11)**: no carrier exists → cannot be exercised from
  stock content. Automatic waive candidate unless someone edits a chr_b
  ability slot or pokes the bitset *before* an ov6 `0x02157114` assembly
  pass. The pass is not one-time: it re-runs per KO/respawn cycle, so the
  gate word churns in active play and is stable only on a quiescent
  savestate (tracker item `jus-gate-word-assembled-after-load-68g`, headline
  retracted in its own comments; tracker item `jus-q2y`).
- **Rows 6–11 (bits 7–9 / 15–17)**: not read by the damage routine at all;
  their consumers are unlocated. Out of scope for the damage-gate tracker item —
  waive from *this* tracker item regardless of carriers. Of these, all six
  abilities have carriers, so they stay testable later if the consumers
  are ever found.

  > Superseded (2026-09-02): bits 7 and 15 are located - they are the
  > launcher-knockback weight pair (ability 23 Heavyweight ×0.5, ability 24
  > Lightweight ×1.5), consumed at arm9 `0x02081844`-`0x02081860` inside the
  > hit handler `0x02080F14` on hit type 6 - see
  > `docs/confirmed-facts/physics.md` §4.1 [`jus-9lp.2`]. Bits 8-9/16-17 are
  > still unlocated.

So of the 12 table rows: 2 confirmed (9, 10), 3 testable now (12, 13, 21),
1 uncoverable (11), 6 out of damage scope (23, 24, 16, 17, 18, 19).
