# The pair loop drops entries whose A node has `+0x14` bit `0x1000` set and `+0x18` bit 0 clear, at `0x0207FD50`

Tracker items: `jus-58bf`, `jus-dib9`, `jus-hitbox-priority-clash-1evz`.

## Question

`jus-dib9` showed the owner's pass-through pair (Yugi dice vs Momotaro
fwd-Y, both nodes bit 0 clear) reaching the pair loop but none of seven
instrumented append sites; four routes were blind. `jus-58bf` instrumented
those routes and every early exit in the loop body, and read the helper the
loop calls.

## Claim

1. Helper `0x020808A4(r0 = node+0x14, r1 = node+0x18)` returns 1 iff
   `(r0 & 0x1000) != 0` and `(r1 & 1) == 0`; else 0. Seven instructions, no
   memory access.
2. In the loop tail of `0x0207FBD0` (r4 pair entry, r6 node A, r7 node B):
   - `0x0207FD28-3C`: r3 = `B+0x14` (loaded at `0x0207FC20`); if
     `A+0x24 & (B+0x14 & 0xFFFFFF)` is nonzero the entry is skipped
     (`0x0207FD34`); else that mask is OR-ed into `A+0x24` (halfword;
     persistent, nothing in the loop clears it). This store is why the dice
     pair exits at `0x0207FD34` from frame 3 on: frame 2 fell through here.
   - `0x0207FD48-50`: helper on A; return 1 skips the entry.
   - `0x0207FD54-74`: if `B+0x24` overlaps B's own `+0x14` low bits, helper
     on B; return 0 skips the bucket-7 append and goes straight to the mark
     gate; else append then mark.
   - `0x0207FD98-AC`: if `A+0x18` bit 0, `A object +0x18 |= 0x2`.
3. Live: the dice/Momotaro pair (A and B both `+0x14 = 0x1000100x`, bit 0
   clear) exits at `0x0207FD50` in frame 2 and at `0x0207FD34` in frames 3-4;
   the four formerly blind routes (`bl 0x20808c0` at `0x0208016C`/
   `0x020801B4`, `bl 0x2080660` at `0x0207FED4`/`0x0207FF14`) have zero hits
   in that state. The naruto rec49/rec50 pair (both bit 0 set): one
   directional entry appends bucket 7 and marks; the other overlaps at B,
   helper returns 0 (bit 0 set), skips the append, still marks. The first
   entry's own `strh` to its A node's `+0x24` is the same field the second
   entry's shortcut reads on that node (A of entry 1 = B of entry 2), so the
   asymmetry is plausibly order-dependent; `+0x24` values were not logged at
   the exits, so this is unmeasured.

So, structurally: `+0x14` bit `0x1000` selects a node class for this helper,
and `+0x18` bit 0 suppresses the helper's skip. A class-`0x1000` node with
bit 0 clear is dropped as the A side before any enqueue or mark. No gameplay
name is attached; the owner's "pass-through" report is consistent with the
drop, not derived from it.

## Conditions

- Fork `c26edf0e0d75364823856c9272a103fe39e03999`
  (`scripts/emu/build_info.json`), JIT off, holder `f58`, probe
  `scripts/gdb/f58_routes.gdb` (37 breakpoints), plan
  `scripts/gdb/experiments/f58_plan.json` (START, 8 no-input frames, START),
  one attach per launch, clean detach (no truncation). Frames = `FLAG_0x9
  rec=0x220e234` markers; once-per-frame assumed for rec0 only.
- States: control `pc-momotaro-npc-yusuke-projectiles-about-to-collide`,
  `pc-naruto-fy-npc-yusuke-fy`, `pc-yugi-fb-npc-momotaro-fy`. Data:
  `docs/research/feel-captures/projectile-conflict-2026-09-11/` SUMMARY.md
  "Blind routes and exits (jus-58bf)", per-state RESULTS.md,
  `f58_routes.log.gz`.
- Positive control: the A=rec70 entry enters `0x020809C8`, appends bucket 8,
  marks, `0x209` next frame (as in `jus-dib9`).
- Disassembly: `scripts/analysis/query.py`; second opinion, neutral prompt:
  `codex_second_opinion_gate_20808a4.md` (gpt-5.6-sol), which reads the
  helper and the `+0x24` overlap mask the same way and notes the mask is
  accumulating, not exact-value, and persists until something else clears it.

## Evidence

See the state logs and the disassembly quoted in the codex prompt file
(`codex_prompt_gate_20808a4.txt`, lines from `0x0207FD20` to `0x0207FDB0` and
`0x020808A4-BC`).

## Limits

- The second walk (`0x0207FE54` re-loads the same list head `manager+0x58`;
  one list, two passes) and what clears `+0x24` are not characterised.
- `0x020808C0` (the buckets-2/3 helper, called at `0x0208016C`/`0x020801B4`;
  zero hits in these runs) contains at `0x020808F4-0x02080904` a predicated
  CLEAR of object `+0x18` bit `0x2`, gated on node `+0x14` bit `0x4000000`
  and node `+0x18` bit 0. [corrected 2026-09-12: an earlier draft placed it
  in `0x02080660`; `query.py func 0x020808F4` resolves to `0x020808C0`.] A third store to the restricted field; not yet
  instrumented.
- Two filters upstream of the loop header (`0x0207FBEC-F4` on `rec+0x34`
  vs `0x00080800`; `0x0207FC04-0C` on entry `+0x10` bit 2) were not
  instrumented, so "entry absent" and "entry filtered" are indistinguishable.
- Pair pass observed in frames 1-4 of each run (frame 5 has no pass entry).
- Frame-1 absence of the dice pair entry: no `LOOP_HDR` at all in frame 1;
  when the entry is linked in is unmeasured.
- rec51 (bit 0 set) appears in no pair entry; unexplained.
- Bit 0's owner-facing meaning remains unnamed; the code makes it a
  suppressor of one early exit and one append decision, nothing more.

## Falsification

An A node with `+0x14 & 0x1000` and bit 0 clear that reaches `0x0207FD54` or
`0x0207FD98` from `0x0207FD4C`; or the helper's arguments not being the
node's `+0x14`/`+0x18` at `0x0207FD40-48`.
