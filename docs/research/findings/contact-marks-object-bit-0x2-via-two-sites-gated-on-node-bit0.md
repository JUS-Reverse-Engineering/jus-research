# Contact marks the participant object (`+0x18` bit `0x2`) at two sites, both gated on the marking node's own `+0x18` bit 0

Tracker items: `jus-8zoi`, `jus-hitbox-priority-clash-1evz`.

## Question

The pair-test finding (`projectile-conflict-pair-test-2026-09-11.md`) rested
on a correlation: records with node `+0x18` bit 0 set reached the `0x209`
store when the owner reported contact, but contact itself was never
measured. `jus-8zoi` set out to measure the pairing at the traced site
`0x02080C18` and show the `0x209` store follows it. (An earlier HANDOFF named
`0x020823E4` as "the pair test"; that address is the damage formula.)

## Claim

1. In the control state, the traced mechanism reproduces live: the helper
   `0x020809C8` (called from the per-frame pass `0x0207FBD0`) stores
   `object+0x18 |= 0x2` at `0x02080C18` once, pairing Yusuke's fwd-Y record
   rec70 (slot 2, node bit 0 set) with the P1 fighter body rec11 (slot 1),
   in frame 1; rec70's `+0x40` reaches `0x209` in frame 2's node walk.
2. In `pc-naruto-fy-npc-yusuke-fy`, that site never executes, yet the same
   object bit flips clear-to-set between frames 1 and 2 for both rec49
   (slot 2) and rec50 (slot 1). The writer is `strbne r0,[r1,#0x18]` at
   `0x0207FDAC`, inline in `0x0207FBD0` on the bucket-7 enqueue path (tail
   append `0x0207FD94`, per `contact-queue-insert-writer-found.md`). Both
   records get `0x209` in frame 2. rec51 (slot 1, bit 0 set) never receives
   the `0xA7` write and never reaches `0x209`.
3. The two sites are structurally identical: each tests participant A's node
   `+0x18` bit 0 and marks participant A's object `+0x18` bit `0x2`. At
   `0x0207FD98`, r4 is the pair entry (`+0x08` = A's object, `+0x0C` = B's
   object) and r6 = `*(*(r4+8)+0x1C)` = A's node, per the loop header
   `0x0207FC10-0x0207FC1C`; live, `*(r4+8) == *(r6+8)` on both hits.
4. That object bit is what the flag writer `0x0207FAF8-0x0207FB0C` tests
   (`tst r0,#2`) before the `strne` that sets `record+0x40` to `0x209`.

So: node `+0x18` bit 0 is a boolean qualifier that permits the record's own
object to be marked when the pair pass processes it; the mark is consumed
next frame as the `0x209` store. Bit 0 is not named beyond that.

## Conditions

- Fork `c26edf0e0d75364823856c9272a103fe39e03999`
  (`scripts/emu/build_info.json`), JIT off, one GDB attach per launch,
  frames counted as `FLAG_0x9 rec=0x220e234` markers (596 per 600-frame
  plan; 605 vs 596 unexplained).
- Probes: `scripts/gdb/zoi_contact_probe.gdb` (holder `zoi`, plans 600
  frames), `zoi_obj18_writer.gdb` with `JUS_WATCH` on the three object bytes
  (holder `zoi-watch`, 10 frames), `zoi_fd98_regs.gdb` (holder `zoi-regs`,
  10 frames), `zoi_baseline_bit.gdb` (paused reads; stepped reads
  unverified).
- Data: `docs/research/feel-captures/projectile-conflict-2026-09-11/`
  SUMMARY.md "Contact proof (jus-8zoi)" and, per state, RESULTS.md,
  `zoi_contact_*.log.gz`, `zoi_obj18_writer.md`, `zoi_fd98_regs.md`.
- Second opinion: `codex_second_opinion_obj18_writers.md` (gpt-5.6-sol).
  Its prompt wrongly called r4 a node; its cross-node question does not
  apply. Its point that the code alone makes bit 0 a boolean qualifier with
  no gameplay meaning derivable stands.
- Positive control: the `JUS_WATCH` run on the control state logged the
  known writer `0x02080C18` (pc `0x02080C20`) and the byte moving
  `0xA1 -> 0xA5 -> 0xA7 -> 0x00 -> 0x20 -> 0xA0 -> 0xA1`.

## Evidence

- Control `zoi_contact_control.log.gz`: `PROBE_ARMED` before marker 1;
  `PAIR_STORE` once at marker 1 (`nodeA=0x221b3c8` -> rec70, partner node
  `0x221a818` -> rec11); rec70 `FLAG_0x209 r0=0xa1` at marker 1 (object byte,
  bit `0x2` clear, store not executed), `r0=0x209` at marker 2.
- Naruto `zoi_contact_naruto.log.gz`: `PAIR_STORE` 0 hits in 596 markers;
  rec49 and rec50 `r0=0xa1` at marker 1, `r0=0x209` at marker 2; rec51
  `r0=0xa1` only, last seen marker 23.
- Naruto `zoi_obj18_writer/watch.log.gz`: bytes `0x023A33D8` (rec49 object),
  `0x02397418` (rec50), `0x02397348` (rec51): 7 writes each to the first two,
  exactly one `0xA7` each at pc `0x0207FDB4`; rec51 only `0xA1`.
- Naruto `zoi_fd98_regs`: two hits at `0x0207FD98`, `r6+0x18 = 0x1`,
  `*(r4+8) == *(r6+8)` (`0x23a33c0`, `0x2397400`), store executed both.
- Disassembly (`scripts/analysis/query.py`): `0x0207FD98 ldr r0,[r6,#0x18];
  tst r0,#1; ldrne r1,[r4,#8]; ldrbne r0,[r1,#0x18]; orrne r0,r0,#2; strbne
  r0,[r1,#0x18]`; routine entry `0x0207FBD0 push {r4-r8,sb,sl,fp,lr}`.

## Refinement (jus-dib9)

Claim 2 called the `0x0207FDAC` writer inline "on the bucket-7 enqueue
path" — that is imprecise. The `dib9_pairs.gdb` pair-level probe on this
same naruto state shows `0x0207FDAC` is reached two ways: after the
bucket-7 append (`0x0207FD94`) fires, and via a branch at `0x0207FD74`
(`beq 0x0207FD98`, gated on `bl 0x20808a4`'s return value) that skips the
append entirely and lands on the mark gate directly. Both of naruto's two
directional pair entries reach `0x0207FDAC` and fire, but only one of them
has a logged bucket-7 append; see naruto `dib9_pairs.log.gz` and
`RESULTS.md` "Pair-level pass (jus-dib9)".

## What was not established

- `pc-yugi-fb-npc-momotaro-fy` (both records bit 0 clear, owner:
  pass-through): rec45 and rec50 coexist only in markers 1-25 and the helper
  was entered once in that span, for rec11. Whether the pair was considered
  and rejected, or never considered, is unmeasured. The earlier "gate
  rejected every call" wording is withdrawn.
- Which bucket a given pair lands in, and why the naruto pair takes the
  inline path while the control pair takes the helper.
- Why rec51 was not marked while rec50 was.
- Any gameplay meaning of bit 0, the object bit, or `0x209`.

## Falsification

A record whose object gets the `0xA7` write while its node bit 0 is clear at
that instant; or a record with bit 0 set that is processed as participant A
in a pair yet never marked, with the pair-processing call logged.
