# Clash-tier survey (2026-09-25): results

A static survey of every fighter's clash data, read offline from the owner's
save states. No emulator or bridge was run. The states stay on the Desktop
and are not in git; only derived numbers are here.

Grades: **measured** (read from bytes in RAM or files), **inferred** (read
from the disassembly, or a rule that fits every case checked), **unknown**.

Files in this folder:

- `survey.py`: the tool. `python3 survey.py` writes the three outputs;
  `python3 survey.py --check` reruns into a temp dir and diffs
  (it prints `byte-stable: yes`). Tests: `scripts/tests/test_clash_tier_survey.py`.
- `table.md` / `table.tsv`: one row per moveData entry, plus the shared
  built-in entries. They hold decoded fields and a SHA-256 of each entry,
  never the raw bytes (the no-release rule); a changed entry changes its
  digest, so `--check` fails. A digest hides nothing for an entry that is
  only its tier and +0x08 (13 of the 14 built-ins, and `db_b_01` idx 22);
  table.md says so.
- `live.md`: per state, the fighters and every in-use collision record.
- `codex-prompt.txt`, `codex-second-opinion.txt`: the Codex check.

## 1. Reading the states (measured)

- A melonDS `.mln` starts `MELN`, u16 version 14, u16 minor, u32 file
  length, u32 0. Sections follow from 0x10: 4-byte magic, u32 length
  (with the 16-byte header), 8 zero bytes, body. The `NDSG` body is a u32
  console type, then main RAM. So 0x02000000 is file offset 0x24.
- Layouts are a0.py's two (`import-character-mapping-2026-09-24/plans/a0.py`):
  dark tournament and test play. The survey picks one only if its fighter
  table matches `[0x02181B28]` and the collision manager points to itself
  +0x454. All 179 states passed.
- Known-value check: in `pc-kakashi-npc-jotaro-dark-tournament.mln.gz`,
  Kakashi's record is 0x0220F30C, the table is 0x021BA0E0, byte 0 is 3,
  and all 760 bytes equal `na_b_04.bin`. In `KAKASHI HATAKE/4.mln` the table
  is at 0x021BA240 with the same bytes. Codex found the same (section 11).
- The per-bit and per-id tables in every state's RAM equal `arm9.bin`
  (`check_tables()` stops the run if not).

## 2. Where moveData lives

- **Per character, static** (measured). Record M = `[[fighter+0x1A8]+0x10]`;
  table = `[[M+0x6C]+0x0C]`. The bytes there equal a `chr/col/*.bin` file
  exactly. The address moves between states (it's on the heap); the bytes
  don't. Entry for id >= 0x100 is table + (id - 0x100) * 20. All 358
  fighters matched one col file (twins with equal bytes are joined, e.g.
  `dt_b_01=dt_b_02=dt_b_03`).
- **Shots use their owner's table** (measured). Every shot record's table
  pointer equals its fighter's.
- **Shared built-in entries** (measured). Ids below 0x100 point into arm9
  static data at 0x0209FC2C + id * 20, the same for every fighter. See
  section 6.

## 3. Where the node flags come from

The node builder is arm9 0x0207D440 (inferred from the listing; the model
matches every live node, see below).

- **Static part.** Entry byte +0x00 (the tier) sets +0x14 bit 0x10000000
  (attack) when nonzero, or 0x20000000 (body) when zero. The entry's
  +0x08 word ORs bits into +0x14/+0x18/+0x1C through the per-bit tables at
  0x0209FD44 (+0x14), +0x80 (+0x18) and +0x100 (+0x1C). Entry bit 5 is the
  only source of +0x18 bit 0 ("participates"). Entry bit 23 sets +0x14
  0x100. If +0x18 gets 0x1000 (entry bit 18), +0x14 loses its low nibble
  and gains 0x100.
- **Runtime part.** The builder seeds +0x14/+0x18/+0x1C from the record's
  +0x34/+0x38/+0x3C. Those hold the side nibble (1 or 2), the shot class
  0x1000, and whatever else the game has set. Save states only show what
  was live at the instant of the save. Nothing in this survey tells what a
  record's seed will be in a state not captured.
- **Model check** (measured): all 36 live authored nodes and all 3195 live
  built-in nodes in the 179 states match `build_node()` /
  `build_builtin_node()` with their own record's seed, on all three words.
- Not modelled: the +0x18 bit 0x10000 low-byte fix-up at
  0x0207D7C0-0x0207D818 (it walks the record's other nodes).

## 4. Corrections to the brief

- The table pointer is `[[M+0x6C]+0x0C]`, not `[M+0x6C]`: the builder does
  the extra +0x0C hop at 0x0207D4CC (inferred; measured by the col match).
- In the first pair loop (0x0207FBD0), the test at 0x0207FC40-0x0207FC48 is
  on node **+0x1C** bit 0x10000000 of the second node (r7), not +0x14.
  Codex agrees.
- One gate I had missed, which Codex lists: 0x0207FC08 skips a pair whose
  byte +0x10 has bit 0x4.

## 5. Record +0x44 bit 0x4 and the second route

- **The route is real** (inferred, confirms the earlier reading). At
  0x02080120-0x02080134 the second loop compares the two tier bytes and
  exits if they're equal, or (0x02080138) if the second node's +0x14 has
  bit 0x40000000. If the first record's +0x44 has bit 0x4 (0x02080140):
  when the second node's +0x14 has none of 0x24000100 (literal 0x020801F8)
  and `sl` is 0, it calls 0x020808C0 at 0x0208016C with no check of which
  tier is lower. Otherwise it calls the helper 0x020809C8 only if the first
  side's tier is lower (0x02080174-0x02080188).
- The bit-clear branch has its own 0x020808C0 call (0x020801B4): the first
  node's +0x14 has 0x40000000, the second's lacks 0x20000000, and `sl` is 0.
- **Agrees with C5.** C5's RESULTS
  (`docs/research/feel-captures/special-clash-rule-2026-09-25/RESULTS.md`,
  lines 131-132) says a pair whose byte +0x10 has 0x4 is skipped before
  either route. The `cmp sl, #0` tests at 0x02080158 (bit-set branch) and
  0x020801A0 (bit-clear branch) are that same condition read again, so
  they add nothing to C5's rule.
- **`sl` is always 0 there** (proven from the listing). `sl` is written only
  at 0x0207FCFC/0x0207FD04 (the first loop's tier load) and at
  0x02080014/0x02080018 (`sl` = pair byte +0x10 has 0x4, from r3 loaded at
  0x0207FE88). 0x0208001C-0x02080020 leaves the pair when `sl` is 1. The
  only branches to 0x02080120 are from 0x020800F0 and 0x020800F8, both
  after that exit, and nothing between writes `sl`. So both tests always
  pass.
- **What 0x020808C0 does** (inferred). With r1 = the first record, and the
  pair's two nodes:
  - if that record's +0x40 has 0x4000, or the second node's +0x14 has
    0x04000000: it clears bit 0x2 of the second object's +0x18 (if that
    node participates) and writes the first node's +0x20 contact mask;
  - otherwise, unless the second node has +0x14 0x100 and +0x1C
    0x40000000, it sets bit 0x2 on the second object's +0x18 (if it
    participates; 0x02080958-0x02080968), writes the first node's +0x22
    mask, and sets the first node's record +0x44 bit 0x100000 (second node
    has 0x100) or 0x200000.
- **Who sets +0x44 bit 0x4: runtime only** (inferred). The one setter is ov6
  0x0215EAB8. Its guards (0x0215EA10-0x0215EAB8): the fighter's ability
  word `obj+0x128` has bit 0x10 (ability 4, Auto-Guard, per
  `docs/confirmed-facts/helpers.md` section 5); the record's +0x40 bit
  0x1000 is clear (0x0215EAD4; when it's set, the same code instead pays
  0x3200 SP and starts the Auto-Guard); and 0x020782AC says half an SP bar
  (0x3200) can be paid. So bit 0x4 reads as "Auto-Guard is armed". It's
  cleared for every record each frame at arm9 0x0207FAB8. No col file
  or static table feeds it.
- **In the states** (measured): 0 in-use records have +0x44 bit 0x4. 8
  fighters have `obj+0x128` bit 0x10: Kyuubi Naruto (`NARUTO UZUMAKI/7-` and
  `8-FORMCHANGE`, `na_b_05`, chr_b 24), Robin (`NICO ROBIN/4`, `5`, `6`,
  `op_b_05`, chr_b 16) and Tsuna (`TSUNA SAWADA/4`, `5`, `6`, `tr_b_01`,
  chr_b 54). Why none shows the bit is unknown: the SP bar, the frame
  order of the ov6 router against the clear, or both.
- No candidate move carries the bit statically, because no move can. It
  belongs to a record at runtime.

## 6. Shared built-in entries and the tier-7 guard (H23)

`table.md`'s "Shared built-in entries" section dumps all 14 (0x0209FC2C to
0x0209FD43; 0x0209FB84-0x0209FC2B holds the per-id tables, 0x0209FD44 on
the per-bit table). The id < 0x100 path (0x0207D570-0x0207D66C) never reads
the tier byte: the node's class comes from the per-id table A14 alone. Both
pair loops still read the tier byte through +0x10.

| id | tier | +0x14 class | used by (ALMT, fighter tables) | live in states |
|---|---|---|---|---|
| 0 | 0 | 0x20000000 body | nearly every animation, 70 tables | 358, every fighter |
| 1 | 6 | 0x10400000 attack | anims 0x10, 0x13 (0x12), 70 tables | 0 |
| 2 | **7** | **0x40000000** | anim 0x3 in 67 tables; 0x28 in 2 | 0 |
| 4 | 0 | 0x20000000, participates | no fighter anim | 12, on +0x34 0x100 records |
| 5 | 0 | 0x20000000 | no fighter anim | 673, on +0x34 0x200/0x400 records |
| 6 | 0 | 0x800 | no fighter anim | 10, on +0x34 0x800 records |
| 7, 8 | 2 | 0x10000 | no fighter anim | 1064 each, on +0x34 0x10000 records |
| 9 | 0 | 0x20000 | anims 0x5, 0x6, 0x14, 0x15, 70 tables | 14 fighters |
| 12 | 2 | 0x10800000 attack | 28 tables, attack anims (0x28, 0x1f, 0x21, ...) | 0 |
| 3, 10, 11, 13 | 0 | - | none | 0 |

- **Id 2 is the guard box** (inferred). Anim 0x3 is the "block" strip
  (`docs/rebuild/anim-timing.md`, Kakashi table). The three fighter tables
  without it are Mashirito (`ds_b_02`, chr_b 57), Gon (`hh_b_01`, chr_b 30)
  and Kyuubi Naruto (`na_b_05`, chr_b 24). C5's H23 node (entry
  0x0209FC54, +0x14 0x40000002 on P2 Kakashi's fighter record) is this
  entry with P2's side nibble; `build_builtin_node(2, ..., r34=2)` gives the
  same word (a unit test).
- **Which nodes carry high tiers** (measured): no fighter col entry is above
  5. Tier 6 is built-in id 1 and one item entry (id 0x10F, +0x34 0x400
  record in `NEURO /4.mln`). Tier 7 is only the guard.
- **What tier 7 does** (inferred): it can never equal an attack's tier, so
  both loops always take their different-tier branch with a guard.
  - First loop: the guard can't be the first side (that needs +0x14
    0x10000000). As the second side, 0x0207FDB4 sends it down the
    0x40000000 branch, which only writes the attacker's contact masks
    (+0x20, or +0x22 and +0x2A bit 0x2). It marks nothing and doesn't compare
    tier order.
  - Second loop: as the second side it exits at 0x02080138. As the first
    side, with +0x44 bit 0x4 clear, it takes the 0x020801B4 call to
    0x020808C0: the H23 route. That marks the attacker's object if the
    attacker participates and lacks +0x14 0x04000000 (and the guard's
    record +0x40 lacks 0x4000). In `taiko_kaka` the tornado doesn't
    participate, which fits C5's "marks nothing".
- Id 1 (tier 6, attack class, on the "down" anims 0x10/0x13) and id 12
  (tier 2, attack class) were never live in a save state; what they're for
  is unknown.

## 7. Summary counts (fighter tables only)

71 fighter tables, 2016 entries, from 179 states (the item table is apart
below). The tier bytes, +0x08 words and participation bits are
**measured**. Every split by kind (melee, spawned, both, unreferenced) is
**inferred**: it rests on the ALMT rule in section 8, which the live check
covers for only 16 of the 2016 entries.

- By tier byte (measured): 0: 44, 1: 1, 2: 240, 3: 888, 4: 306, 5: 537.
  None above 5.
- By kind (inferred, the ALMT rule): melee 1461, spawned 411, both 40,
  unreferenced 104.
- Tier by kind (inferred):

| kind | tier 1 | tier 2 | tier 3 | tier 4 | tier 5 |
|---|---|---|---|---|---|
| melee | 0 | 61 | 845 | 73 | 481 |
| spawned | 0 | 151 | 13 | 182 | 27 |
| both | 1 | 8 | 7 | 21 | 2 |
| unreferenced | 0 | 20 | 23 | 30 | 27 |

- Participating (tier > 0, +0x18 bit 0): 172 entries (measured). By tier:
  2: 93, 4: 78, 5: 1. **No tier-3 entry participates** (measured).
- By kind (inferred): spawned 156, both 12, unreferenced 4, melee 0. The
  "melee 0" holds only under the ALMT rule. Under the other rule in
  section 8, two participating entries become melee (Jotaro `jj_b_01` idx
  20, tier 4; Edajima `oj_b_01` idx 18, tier 2).
- The 4 participating "unreferenced" entries (no ALMT track names them):
  Gintoki `gt_b_01` idx 28, Muhyo `mr_b_01` idx 29, Robin `op_b_05` idx 31
  and Yusuke `yh_b_01` idx 9.
- 31 characters have a tier-2 melee entry and 27 a tier-4 one (inferred,
  same rule), so melee boxes span the same 2-5 bytes as shots.
- Gate bits (tier > 0): +0x14 0x04000000: 107; +0x14 0x08000000: 11;
  +0x14 0x100: 2; +0x18 0x10000: 63; +0x18 0x2000: 18; +0x18 0x20000: 31;
  +0x1C 0x10000000: 36; tier 3 or 4 (the helper's exception): 1194.
  +0x14 0x40000000 and 0x200: 0.
- Item table (`item.bin`, used by the item records): tiers 1: 33,
  2: 7, 3: 2, 6: 1.

## 8. Melee vs spawned (inferred rule)

An animation whose `CollisionType0` track holds an authored id (>= 0x100)
belongs to a spawned element; every other animation is the fighter's
(from `scripts/analysis/move_records.py`'s motion decode). The live check
covers 16 of the 2016 fighter entries: those were live in some state. For 13 the rule gives the same kind as
the record that carried them. One is "both" and was live as spawned. The
rule misses two: Taikoubou's tornado (`hs_b_01` idx 14/15) is
"unreferenced" by the rule but live on a shot record. None contradicts it.
"Both" means one entry shows up under both kinds of animation, often in
another motion member (for example `db_b_02_6`).

**A second rule gives a different split.** "An animation is the fighter's
if one of its CollisionType tracks names built-in id 0 (the body box)."
The two rules disagree on 8 animations. Each has an authored
CollisionType0 and also names id 0: `ds_b_01:0x4c`, `hs_b_01:0x53`,
`jj_b_01:0x25`, `jj_b_01_4:0x60`, `jj_b_01_4:0x65`, `oj_b_01:0x48`,
`op_b_05:0x4c` and `rk_b_01_5:0x80`. Under the second rule 17 entries
change kind, all from spawned (to 11 melee, 6 both). Two of them
participate: Jotaro `jj_b_01` idx 20 (tier 4) and Edajima `oj_b_01` idx 18
(tier 2). No live entry tells the rules apart, so which is right is
unknown. Those 8 animations are the ones to check.

## 9. Live notes (measured)

- **Kurama and Taikoubou, C5's addresses.** In `kurama-x-yusuke-x.mln`, record
  r58's table is `hs_b_01` at 0x021BA6E0, Taikoubou's own base in
  `taikoubou-upx-yusuke-x.mln`. This matches C5's updated reading (r58 is
  the tornado). Kurama's fighter record r11 holds ids 0x113/0x114
  (entries 0x021BB49C/0x021BB4B0) at the save. C5's 0x021BB4C4 is idx 21
  (id 0x115) of the same table: tier 5, +0x08 0x400, +0x18 0x40, the same
  as 19 and 20. Taikoubou's 0x021BA80C is idx 15 (id 0x10F): tier 4,
  +0x18 0x80, live on r57 in `taikoubou-upx-yusuke-x.mln`.
- **Items carry the rare bits.** Records with +0x34 0x100 (they use
  `item.bin`; likely item boxes, not verified) hold
  built-in id 4 (+0x14 0x20000100, +0x18 0x8001) with item attack nodes
  (tier 1, +0x14 0x10000100), live in `NEURO /4`, `KENSHIN HIMURA/5`,
  `MONKEY D. LUFFY/4` and `BOBOBO-BO BO-BOBO/7-SPRITECHANGE`. Records with
  +0x34 0x200 (id 5, +0x14 0x20000200) are in 169 of 179 states. Records
  with +0x34 0x10000 (ids 7/8, +0x14 0x10000, +0x1C 0x50BFFFFF, tier 2) are
  in every state.
- Fighter records' +0x44: Sasuke has 0x40 and Momotaro 0x30 in the
  projectile-research states. Neither is bit 0x4.

## 10. Candidate moves

"One-player" means the owner plays one side against a CPU using a state
that already exists. Predictions are inferred from the listing and C5's
rule; none is measured. States are under `~/Desktop/savestates/`.

**Q1. Do melee boxes use the same byte scale as shots?** Both loops read
the tier byte the same way for any node, so the listing says yes. C5
measured tier-5 melee (Sasuke idx 17, Kurama idx 19-21) marking the tier-4
X. What's untested is a lower melee tier.

| move | entry | state | predicted | one-player |
|---|---|---|---|---|
| Sasuke (`na_b_02`, chr_b 21) B, anim 0x1e | idx 0, tier 3 | `projectile-research/sasuke-x-yusuke-x.mln` | tier 3 < 4: the X (participates) is not marked and flies on | yes: press B into the CPU's X |
| Sasuke, anim 0x32 | idx 26/27, tier 4 | same | equal tiers, C5's rule 1 (each participating side is marked): the box doesn't participate, the X does, so the X is marked | yes |
| Naruto (`na_b_01`, chr_b 20) B, anim 0x1e | idx 0, tier 3 | `naruto-fy-yusuke-fy.mln` (CPU side Y, tier 2, participates) | 3 > 2: the side-Y shot is marked | yes |
| Naruto, anim 0x23 | idx 6, tier 2 | same | equal, rule 1: the side-Y shot participates and is marked; the box isn't | yes |
| Naruto B | idx 0, tier 3 | `naruto-fy-yusuke-x.mln` | 3 < 4: the X flies on | yes |
| Taikoubou (`hs_b_01`, chr_b 68) B | idx 0, tier 3 | `taikoubou-upx-yusuke-x.mln` | the X flies on | yes |
| Taikoubou, anim 0x2c | idx 32, tier 4 | same | equal, rule 1: the box doesn't participate, so the X is marked | yes |

Anim 0x1e is B only by analogy with Kakashi (C1). The input for the other
anims is unknown; the owner would find it by trying.

**Q2. Is there a participating melee box?** Not among melee-only entries (0
of 1461) under the ALMT rule (inferred). The candidates are the 12 "both"
entries that participate (each is on a fighter animation and on a spawned
one), plus Jotaro `jj_b_01` idx 20 and Edajima `oj_b_01` idx 18, which are
melee under the second rule (section 8). The 12 "both" entries:

| character | entries | states | one-player? |
|---|---|---|---|
| Goku (SSJ) (`db_b_02`, chr_b 1) | idx 0 (anim 0x1e), 3, 6, 9, 14, tier 4 | `SON GOKU/6`, `7` (P1) | no: needs a CPU shooting at Goku |
| Vegeta (SSJ) (`db_b_04`, chr_b 3) | idx 1, 3 (tier 4), 11 (tier 2) | `VEGETA/5`, `6` (P1) | no: needs a CPU shooting at Vegeta |
| Vegetto (`db_b_12`, chr_b 11) | idx 0 (tier 4), 8 (tier 2) | `SON GOKU/8-SPRITECHANGE` (P1) | no: needs a CPU shooting at Vegetto |
| Arale (`ds_b_01`, chr_b 56) | idx 8 (tier 2) | `ARALE NORIMAKI/4`-`7` (P1) | no: needs a CPU shooting at Arale |
| Yusuke (`yh_b_01`, chr_b 32) | idx 26 (tier 4, anim 0x2c) | P1 in `yusuke-firing-fy.mln` | no: that CPU fires only a tier-2 shot, which is lower, so idx 26 couldn't be marked whether or not it participates. A tier-4 shot (equal) or a tier-5 one would be needed |

A non-participating melee box is the norm: all 1460 melee-only entries
with tier > 0 have +0x18 bit 0 clear (the count is measured; the "melee"
label is inferred, section 7). **No existing state tests any of these
five.** Each needs a new state with the CPU shooting at that character.

**Q3. Which moves reach the 3/4 exception?** The helper 0x020809C8 has
two versions of it. On the shot path, it skips marking the lower side
when that side is tier 3 or 4 and the other node's +0x14 has 0x300. On the
body path (0x02080B30-0x02080B58, the lower side is a body node), it
skips marking the second node, which is the higher one, when *that* node
is tier 3 or 4 and the lower (body) node's +0x14 has 0x300.

- Between two authored moves it looks unreachable (inferred). Only two
  entries have +0x14 0x100 (Hiei `yh_b_03` idx 21, tier 4, spawned; and
  Taikoubou `hs_b_01` idx 31, tier 1). No tier-3 entry participates, so a
  tier-3 lower side has nothing to mark anyway.
- Items reach it: the item records' body nodes (+0x14 0x20000100 or
  0x20000200) meet the helper's body path. A participating tier-4 shot
  against one would not be marked; a tier-2 one would. Candidate: Shinsetsu (`bb_b_03`, chr_b 49)
  idx 15, tier 4, participates, anim 0x3b, in
  `BOBOBO-BO BO-BOBO/7-SPRITECHANGE.mln`, against Neuro (`nn_b_01`, chr_b 60)
  idx 14 (anim 0x3b) or 16 (0x53), tier 2, participates, in
  `NEURO /4.mln`. One-player: yes, fire into the item. The item records
  are live at load, but where the items sit on screen is unknown.

**Q4. Do the unusual node bits turn up?**

- +0x14 0x08000000 (entry bit 1): 11 entries, 10 melee: Kakashi `na_b_04`
  idx 15 (anim 0x18), Dio `jj_b_02` idx 13, Hiei `yh_b_03` idx 13,
  Gintoki `gt_b_01` idx 8/13, Kenshiro `hk_b_01` idx 39, Raoh `hk_b_02` idx
  19, Zoro `op_b_02` idx 16, Kenshin `rk_b_01` idx 7, Anna `sk_b_03` idx 16;
  plus Naruto `na_b_01` idx 14 (unreferenced). None was live. Against a shot
  it needs a CPU shooting at that character (**new state**); against melee
  it needs two fighters timed against each other (**not practical**).
- +0x14 0x40000000: only the guard (built-in id 2). No authored entry.
- +0x14 0x100/0x200: items (live) and the two entries above.
- +0x14 0xB0000 (the helper's early exit): only built-in ids 7, 8 (0x10000),
  9 (0x20000) and 11 (0x80000). Ids 7/8 are live on the +0x34 0x10000
  records, id 9 on 14 fighter records.

**Q5 (new). Does guarding a participating shot mark it?** The H23 route
(section 6) says it should, when the guard node is the pair's first side.
Candidate: hold guard against the CPU's Yusuke X (tier 4, participates,
no 0x04000000) in any `*-yusuke-x.mln` state. Predicted: the X object gets
+0x18 bit 0x2 on contact, and the guard's record gets +0x44 bit 0x200000.
One-player: yes. Unknown: the pair order, and what record +0x40 bit 0x4000
means (it turns the mark into a clear).

**Q6 (new). The +0x44 bit-4 route.** It needs an armed Auto-Guard fighter
(Robin, Tsuna or Kyuubi Naruto with at least half an SP bar) as the first
side against a node lacking 0x24000100. Nothing static carries it.
Testing it needs the CPU to shoot at one of these (**new state**).

## 11. Codex second opinion

`codex exec`, read-only, with a neutral prompt: six questions, no answers
given (`codex-prompt.txt`). Its answer is `codex-second-opinion.txt`.

It agrees on:

- Q1: RAM at file offset 0x24, checked against `arm9.bin`.
- Q2: P 0x022286E0, R 0x0220FA94, B 0x021BA240, `na_b_04.bin`, byte 3
  (my `live.md` has the same for `KAKASHI HATAKE/4.mln`).
- Q3: both id paths, the 0x0209FC2C built-in base, the per-id tables and
  the per-bit mapping, bit for bit.
- Q4: the gates, including the +0x1C test on the second node, and the
  0x08000000 branch.
- Q5: the 0x020808C0 calls don't check which tier is lower; the helper
  calls do.
- Q6: the ov6 0x0215EAB8 setter behind 0x020782AC, and the clear at
  0x0207FAB8.

It differs on:

- **Q5 mask**: Codex says the bit-set branch tests the second node's
  +0x14 against 0x00080800. The load at 0x0208014C is `ldr r0, [pc,
  #0xa4]`, which is 0x020801F8 = 0x24000100. Codex read the neighbouring
  literal (0x020801F4 = 0x00080800, used by the first loop). I keep
  0x24000100, which matches C5.
- **Q5, 0x020808C0**: Codex describes only the clear branch. It reads the
  `beq` at 0x020808F0 as "doesn't proceed", but that `beq` goes to
  0x02080944, the mark branch (0x02080958-0x02080968). I keep both
  branches.
- **Omissions, not conflicts**: Codex doesn't list entry bit 23 to +0x14
  0x100, the +0x18 0x1000 fix-up, or the per-id tweaks for ids 1 and 9. For
  Q6 it gives only the 0x020782AC guard, not the ability bit or record
  +0x40 0x1000. It adds two points I had missed: the pair-byte test at
  0x0207FC08, and the `sl` test on the bit-clear 0x020808C0 call. Both
  are in sections 4 and 5. The `sl` test turns out to be C5's own
  pair-byte skip read a second time (section 5).

## 12. Open unknowns

- Which button each anim id is. Only 0x1e = B (Kakashi, C1) and anim 0x3 =
  block (strip name) are known.
- Which melee/spawned rule is right (section 8's 8 animations), and whether
  the "both" entries really participate as melee boxes or only when
  spawned.
- What the item records are (+0x34 0x100, 0x200, 0x400, 0x800, 0x10000),
  and where they sit on screen.
- Whether the ov6 router 0x0215E9A0 runs before or after the pair loops in
  a frame. That decides if +0x44 bit 0x4 is ever set when the loops read
  it.
- What record +0x40 bit 0x4000 means (it turns 0x020808C0's mark into a
  clear; cleared each frame with 0xC000 at 0x0207FAB8).
- The pair order in the second loop, which decides whether a guard node is
  the first side (Q5).
- What built-in ids 1 (tier 6) and 12 (tier 2) are for.
- Stores to +0x44 through computed registers weren't traced exhaustively;
  the known writers are 0x0207C060 (bit 0x2), 0x0207F834/0x0207F85C (bit
  0x1), 0x020809A0 (0x100000/0x200000), 0x020817A8 (bit 0x8), 0x02083BE0
  (bits 0x10-0x20000) and ov6 0x0215EAB8 (bit 0x4).
- The +0x18 bit 0x10000 low-byte fix-up isn't modelled.
