# ColPrm record `+0x34` low nibble and `+0x3C` low byte agree with the owning player slot

Tracker items: `jus-qqiy`, `jus-hitbox-priority-clash-1evz`.

## Question

`jus-flp3` logged 26 records created mid-run across seven states and could
not tie any of them to a character: the creator pointer `r1` at record
install never equals a fighter object and lives in its own arena.
`jus-qqiy` asked whether any word in the creator object, the record header,
or the first node points at a fighter. None does. But a two-valued field in
the record itself splits every independently attributed record by player
slot.

## Claim

On every ColPrm record checked, the low nibble of the u32 at `record+0x34`
and the low byte of the u32 at `record+0x3C` read `1` / `0x11` when the
record belongs to player slot 1 (the `pc-` side in owner states) and `2` /
`0x22` when it belongs to player slot 2 (the `npc-` side). Node 0 mirrors
the low halves at `node+0x14` and `node+0x1C`. The high bits (`0x1000` in
`+0x34`, `0x800` and `0x63C000` in `+0x3C`) vary independently of the low
bits and are not read here.

This is a two-valued field that agrees with player slot. It is not named
as an owner field, team, or any gameplay meaning; see "What would separate
the readings".

## Conditions

- Live runs: `scripts/gdb/qqiy_creator_probe.gdb` (as committed in
  `4a7a4f4`/`7293f4d`; the `SELFCHECK` line and mark fix in `6c110d5`
  post-date the logs), holder `qqiy`, JIT off, fork
  `c26edf0e0d75364823856c9272a103fe39e03999`
  (`scripts/emu/build_info.json`), run plan
  `flp3_run_plan600.json` (START, 600 no-input frames, START), 596
  `FLAG_0x9 rec=0x220e234` frame markers per run, both runs ended clean.
  States: `pc-momotaro-npc-yusuke-projectiles-about-to-collide` (P1
  Momotaro, P2 Yusuke) and `pc-naruto-fy-npc-yusuke-fy` (P1 Naruto, P2
  Yusuke); P1/P2 read live from the fighter table `0x021DEB3C` / `+4`.
- Static: baseline censuses of the 12 states in
  `docs/research/feel-captures/projectile-census-2026-09-10/` and the
  owner states in `projectile-conflict-2026-09-11/` (20 distinct states
  total; the momotaro control is one state run in both batches; the
  derived `-preroll` state is excluded as an invalid run), plus
  `pc-yusuke-fy-npc-unverified-preroll` (`jus-rp0y`, 2026-09-12, the
  separating test below) for 21 distinct states total.
- Full tables, word dumps, and the independence split:
  `docs/research/feel-captures/projectile-conflict-2026-09-11/SUMMARY.md`,
  sections "Creator resolution (jus-qqiy)", "Candidate owner/slot field",
  "Independence recount".
- Second opinion, neutrally framed:
  `docs/research/feel-captures/projectile-conflict-2026-09-11/codex_second_opinion_side_field.md`
  (gpt-5.6-sol). Its prompt supplied "rec11/rec12 are the fighters'
  bodies" as context, so its agreement on that leg is not independent.

## Evidence

Only records whose side label does not come from this field, or from
matching an entry pointer previously associated with it, test the claim.

**(a) Independently labelled, 49 records, 49 agree, 0 disagree:**

- Fighter bodies rec11 (`0x0220F30C`, element `0x0220C068`) and rec12
  (`0x0220F494`, element `0x0220C0A8`) in all 20 states: `0x1`/`0x63C011`
  and `0x2`/`0x63C022`. Basis: `docs/confirmed-facts/characters/kakashi.md`
  line 35 (also `taikoubou.md`, `sasuke.md`): attacker
  `M = [[obj+0x1a8]+0x10] = 0x0220F30C`, element `0x0220C068`; victim
  `0x0220F494`, verified live via the fighter table slot 1, element
  `0x0220C0A8`. Six different P1 characters, all `1`.
- Control rec70 (`0x02214D64`): owner testimony (Yusuke fwd-Y), fighter
  pointers, x and timing. `0x1002`/`0x63C822`, slot 2.
- `pc-naruto-fy-npc-yusuke-fy` rec49 (owner: Yusuke fwd-Y, x increasing,
  entry `0x021BD8A4`): `0x1002`/`0x63C822`, slot 2. rec50, rec51 (owner:
  Naruto shuriken flying left, entry `0x021BAB50`): `0x1001`/`0x63C811`,
  slot 1.
- `pc-ichigo-fy-vegeta` rec115 and `pc-mashirito-fy-npc-momotaro-b` rec99:
  owner says only the P1 side had a projectile out
  (`OWNER-NOTES.md` lines ~155-157, ~184). Both `0x1001`, slot 1.
- `pc-yusuke-fy-npc-unverified-preroll` (`jus-rp0y`, the 21st state, the
  separating test below): fighter bodies rec11 (`0x0220F30C`) and rec12
  (`0x0220F494`), same basis as the other 20 states: `0x1`/`0x63C011` and
  `0x2`/`0x63C022`. The created record `0x220f7a4` (Yusuke firing forward
  Y as P1): `0x1001`/`0x63C811`, slot 1 — see "Separating test done"
  below for the full result.

**(b) Labelled by the field or by entry band, 27 records, all consistent,
circular:** the four control-created and three naruto-created records, rec52
(shared entry with rec50/51), and 19 census records in states where the
side split came from the shape. These do not test the claim.

**Not a Yusuke marker.** Slot-2 records with P2 = Ichigo
(`pc-hitsugaya-airy-npc-ichigo-fy` rec20), Vegeta (`pc-yugi-fb-npc-vegeta-fy`
rec23, `pc-yugi-fb-npc-vegeta-x` recs 106-112), Kakashi
(`pc-taikoubou-upx-npc-kakashi-x` recs 50, 63-65) all read `2`. These are
in group (b) for side, but they rule out "2 = Yusuke" regardless, because
Yusuke is not in those states.

**Not a move signature.** In the control, created records with entry
`0x021C808C` (same as rec70) and `0x021C7FC4` (different) both read
`0x1002`/`0x63C822`. In `pc-naruto-fy-npc-yusuke-fy`, created `0x0221366C`
reads `0x1002`/`0x63C022`: `0x800` clear, low byte still `0x22`.

## Consequence

Every `0x1002`/`0x63C822` record created in the six Yusuke-X states of the
`jus-xyqc`/`jus-flp3` batches carries the slot-2 value, and P2 is Yusuke in
all six. Those records are attributable to Yusuke's side. They are not
attributable to a specific move; the earlier "Yusuke X signature" claim
stays retracted.

## What would separate the readings

Codex lists alternatives that fit all data: collision team, controller
port, spawning-parent channel, allocation class correlated with the
fighter. None is separated from "player slot" by current data. The
separating test is one fighter firing one attack once as P1 and once as
P2; a Yusuke-as-P1 state was requested by the owner and built as
`pc-yusuke-fy-npc-unverified-preroll`.

**Separating test done (`jus-rp0y`, 2026-09-12).** Yusuke as P1, firing
forward Y (`RIGHT+Y` input; the move does not fire on its own in a
no-input run — see the test's `RESULTS.md`): record `0x220f7a4` reads
`+0x34 = 0x1001` (low nibble `1`), `+0x3C = 0x63c811` (low byte `0x11`) —
the slot-1 value. Positive control (fighter-body records) confirmed
`0x1`/`0x63C011` for P1 and `0x2`/`0x63C022` for P2 in the same run.
**Not falsified.** Combined with the six states where Yusuke was P2 and
produced the slot-2 value, this is the one-fighter-two-slots test the
claim asked for, and the result agrees with "player slot," not
"character identity." 49/49 independently attributed records now agree
with player slot, 0 disagree (the 46 from the prior 20 states, plus this
state's rec11, rec12, and the created record). Full data, GDB log, and
the harness hazards hit along the way:
slot-p1-2026-09-12/RESULTS.md.
The state's opponent read as `chr_b` 32 (Yusuke) on both `--verify-roster`
bases — a caveat, not independently confirmed visually (only one HP bar
ever renders); see that file's "Roster" section.

## Falsification

An independently attributed, fully initialised record whose low nibble
names the other slot; or the same fighter and move keeping its nibble
after switching player slots. **Tested and not triggered** (`jus-rp0y`,
above): Yusuke's nibble changed from `2` (as P2, six prior states) to `1`
(as P1, this test).

## Limits

- Ownership testimony is per state and per move, not per record; in
  two-projectile states the per-record split rests on this field.
- ~~No state has Yusuke as P1.~~ Closed by `jus-rp0y`
  (`pc-yusuke-fy-npc-unverified-preroll`), see "Separating test done" above.
- P1/P2 identity in 18 of 20 states rests on the `pc-`/`npc-` filename
  convention plus owner testimony; the fighter table was read live only in
  the two `jus-qqiy` states.
- The high halves of `node+0x14`/`node+0x1C` are unresolved.
