# Per-frame call order of the battle step

`jus-entity-frame-placement-4tok`. Grade: **PLAUSIBLE**.

## Question

Place, within one emulated frame, the order of: input sample, the collision
driver (hit events), fighter update / state commit, the integrator,
per-frame clears, the ObjShot per-frame entry, and the auxiliary ticks
(bench regen, status-node countdown, guard drain).

## Method

Static: read the anchor addresses each subsystem doc already cites
(entities.md §5.1, physics.md §4.5/§6.1, guard-sp.md §0.5, collision.md §5,
damage.md §8), then traced xrefs (`scripts/analysis/query.py xrefs-to`) to
find shared callers. Live: a 7-tag GDB entry-breakpoint probe
(`scripts/gdb/e4tok_order.gdb`) on two owner-made savestates, one with active
projectiles (`pc-momotaro-npc-yusuke-projectiles-about-to-collide`) and one
plain idle two-fighter state (`pc-momotaro-npc-nami-dark-tournament`). Full
conditions blocks and raw logs:
frame-order-2026-09-12.

## Static findings that shaped the probe

- **The fighter's own per-frame task is a single function, `0x02156DDC`**
  (ov6, size 360, registered via the generic per-frame task-list API
  `0x02028384` — confirmed by disassembly at its fighter-init call site,
  `0x02156AB8`/`0x02156AC0`). Reading its body end to end
  (`query.py disasm 0x02156E80 60 --overlay ov6`) shows, in straight-line
  instruction order, calls to: `0x02158B20`, `0x0215C278`, `0x0215C360`,
  then **`0x0215A978` (fighter update) at `0x02156EB0`, `0x0215EF24` (guard
  drain) at `0x02156EB8`, `0x02159CC4` (state-machine commit, the writer of
  `obj+0x18` per physics.md §4.5) at `0x02156EC0`** — in that order, all
  inside one function, one call per fighter object per frame. This
  contradicts the engine notes' current table, which lists guard drain only as
  part of phase 7 ("auxiliary ticks") separate from and after phase 3
  ("fighter update"); the static read already shows guard drain sitting
  *between* fighter update and the state commit that publishes `obj+0x18`,
  for the same fighter, in the same function call. Two callers of the same
  fighter object skip part of this triple: state `0x1B` (`ldrsb r0,[r4,#0x18];
  cmp r0,#0x1b; beq` at `0x02156E38`-`0x02156E40`) branches straight to the
  state-commit call, skipping both update and drain that frame; a second,
  alternate per-frame callback at `0x02156F48` (installed under the same
  sort key by the toggle at `0x02156F6C`, which swaps the function pointer
  at `obj+0x40` between `0x02156DDC` and `0x02156F48`) calls only fighter
  update and returns, skipping drain and commit entirely. Neither path was
  exercised by either capture in this session (see Gaps).
- **The collision driver `0x0207F480`** (arm9, size 1736, `callers=0` in
  functions.json — only reachable through the same generic task-list
  mechanism, confirmed by its own literal-load/registration site at
  `0x0207C5E8`/`0x0207C5F0`) is a sibling registration to the fighter task
  and to ObjShot's entry (`0x0216AF04`, registered via `0x02028384` per
  entities.md §5.1) and the integrator (`0x02082E10`, also registered via
  `0x02028384` at `0x02082AD8`, literal-loaded at `0x02082AD0`). All four —
  collision driver, fighter task, integrator, ObjShot entry — are tasks in
  one shared per-frame task list; **`0x02028384` only installs the callback
  at `obj+0x40` — it is not the ordering authority.** The ordering authority
  is a sort key each task registers through `0x02012940`, which forwards to
  the node vtable's `+0xA0` insert method. Each task's key is a literal
  loaded right before that call: fighter task `0x02156DDC` registers key
  `0x85000` at `0x02156A98`; ObjShot `0x0216AF04` registers key `0x88000` at
  `0x0216A820`; the collision driver `0x0207F480` registers key `0x9E000` at
  `0x0207C5D0`; the integrator `0x02082E10` registers key `0xA1000` at
  `0x02082AB8`. The insert routine itself, `0x0201CCA0`, confirms the keys
  are sorted, not FIFO by registration order: the halfword stored at
  `node+6` is not the raw key but `(key >> 4) & 0xFFFF` (codex's read,
  agreed against the disasm below); the routine loads that stored halfword
  (`ldrh r3,[r4,#6]`) and buckets on `stored >> 8` — net effect, external
  key bits 12–19 — giving 256 heads (at `manager+0xC`..`+0x40C`). It then
  walks the bucket's linked list in ascending key order (`cmp`/`blo` at
  `0x0201CCE4`-`0x0201CCEC`) or falls through to a forward bucket scan
  (`0x0201CD3C`) when the bucket is empty, inserting before the first node
  whose key is not lower — codex adds that ties (equal stored keys, e.g.
  the two fighter instances, both `0x85000`) insert newest-first (LIFO),
  not stable, so the two fighters' relative order is not guaranteed by the
  key alone. Ascending key order is therefore FIGHTER (`0x85000`) →
  OBJSHOT (`0x88000`) → HIT_EVENTS, the collision driver (`0x9E000`) →
  INTEGRATOR (`0xA1000`). All four tasks are enabled into the single
  global list at `*(0x020A0C34)+0x460` through the same path (`0x02027EDC`
  → `0x020119EC` → `0x0201CCA0`), so this is one list, not four
  independent registrations that happen to agree.
- **The measured ring (see below) is this ascending-key order rotated by
  one cut point**, not a different order: FIGHTER → OBJSHOT → HIT_EVENTS →
  INTEGRATOR, cut and restarted at HIT_EVENTS because that was the only tag
  with no better frame-boundary candidate available (see "Frame boundary"
  below). The true frame boundary — the point the sort-key order actually
  starts a new frame at — sits **before the lowest-key task, the fighter
  task**, not at the collision driver as the cut used for logging implies.
- No static anchor was found for **input sample** or **status-node
  countdown** after checking physics.md, guard-sp.md, entities.md,
  collision.md, damage.md, the combat notes and the engine notes. Neither is probed here;
  both stay open (see Gaps).

## Measured order (both states, 54 and 676 complete frames respectively, zero deviation in tag sequence)

```
HIT_EVENTS (0x0207F480, collision driver)
  -> INTEGRATOR (0x02082E10)                      [once/frame, see caveat]
  -> REGEN_TICK x N (0x02077D40)                  [N = benched-koma count]
  -> FIGHTER_UPD (0x0215A978)   fighter A
  -> GUARD_DRAIN (0x0215EF24)   fighter A
  -> STATE_COMMIT (0x02159CC4)  fighter A
  -> FIGHTER_UPD (0x0215A978)   fighter B
  -> GUARD_DRAIN (0x0215EF24)   fighter B
  -> STATE_COMMIT (0x02159CC4)  fighter B
  -> OBJSHOT (0x0216AF04)
  -> [next frame's HIT_EVENTS]
```

This is the SAME shape in both states (projectile state: 6 regen ticks;
plain state: 4 regen ticks — the deck's benched-koma count, not a phase
change). `OBJSHOT` fires every frame in both states, including the plain
one with no active projectiles, confirming entities.md §5's "unconditional
per-frame entry, possibly over an empty list" framing.

Frame boundary used for logging: entry to the collision driver itself,
since no VBlank/main-loop frame-advance routine is documented anywhere in
the corpus (checked exhaustively, see Method). This makes `HIT_EVENTS`
double as the phase-2 tag and the frame marker in the log — read the
sequence above as a cycle, not as "hit events happens once, before
something called frame 1". The static sort-key order (previous section)
places the actual boundary **before the fighter task** (the lowest key),
one cut point earlier than the logging cut; that shift does not change the
cycle's tag adjacency, only which tag is conventionally called "first."
Bench regen (`0x02077D40`) has no static registration anchor found this
session — its key, and therefore which side of the boundary it falls on,
is unknown; it is measured adjacent to the boundary (immediately after the
integrator, immediately before the fighter task) but that position could
be either the last task of one frame or the first of the next.

There is no positive control for this measurement: no run in this session
forced a known, independently-verified frame count or event to cross-check
the tag sequence against. The corroborating evidence is the static key
order derived independently of the runtime probe (previous section) and
the fact that 730 combined measured frames across two states never
deviated from one tag sequence — not an external ground truth.

## What this resolves in the engine notes' phase table

Row 6 (Entities/projectiles) and row 7 (Auxiliary ticks) both said
"Placement within phases 1-5: TBD" / "Intra-frame order vs phases 1-5:
TBD". Measured:

- **ObjShot's per-frame entry runs LAST in the cycle**, after both
  fighters' complete update/guard-drain/commit triple, not interleaved
  within phases 1-5.
- **Bench regen runs immediately after the integrator and BEFORE either
  fighter's update**, not after phase 5 as the row-7 wording implied.
- **Guard drain is not a separate aggregate pass over both fighters.** It
  runs per-fighter, sandwiched between that fighter's own update and its
  state commit — i.e., it is part of the same per-fighter task call as
  fighter update and state commit, not a standalone phase-7 tick.
- **Status-node countdown was not anchored or measured this session** (no
  static address found) and stays TBD.

## What did not run / could not be measured

- **Input sample** — no address found anywhere in the corpus; not probed.
  Falsification test for a future session: find the pad-read writer of
  `obj+0x6C` (currently only its *readers* are documented, e.g. guard-sp.md
  §0.7's `0x0215EE24`-`0x0215EE30`) and add it as an eighth tag.
- **Status-node countdown** — physics.md §4.5 documents the node fields
  (`obj+0x94`: id at `+0x0C`, frames-remaining at `+0x0E`, "−1/frame") but
  not the decrementing routine's address. Not probed.
- **Fighter state `0x1B` and the alternate per-frame callback `0x02156F48`**
  — neither capture put a fighter into state `0x1B`, and neither exercised
  the toggle at `0x02156F6C` that swaps the registered callback away from
  `0x02156DDC`. Both are static-only findings this session (see "Static
  findings" above); the measured triple order (update → drain → commit)
  is confirmed only for the common path, not for either skip case.
- **INTEGRATOR fired exactly once per frame in every single frame of both
  54-frame and 676-frame runs**, logging the same constant address each
  time (`0x023DE248` / `0x023DE350` in the two captures). Reading
  `0x02082E10` end to end resolves what this is: the routine is a
  **pass**, not a per-element entry point. Its head (`0x02082E24`,
  `ldr ip,[r3,#0x10]`) loads a list, the body (`0x02082E40`-`0x02083160`)
  runs once per element inside that list (element pointer `ldr lr,[ip,#8]`
  at `0x02082E40`), and the tail (`0x02083164`-`0x0208316C`) advances the
  list and loops. The GDB probe's breakpoint sits at the routine's entry,
  which fires once per frame by construction — it cannot see the per-
  element iterations of the internal loop; nothing needs to be "gated
  off" to explain a single hit. `r0` at entry is **not an element** — the
  dispatcher thunk that calls task callbacks (`0x02025EF8`: `mov r0, r1;
  blx [obj+0x40]`) passes through whatever the task-list walker supplied
  as the second argument, and the logged constant addresses read as a
  manager/owner pointer, not a battle element. A probe that wants
  per-element granularity needs a breakpoint inside the loop, at
  `0x02082E40`, not at the entry `0x02082E10`.

## Falsification test

Any frame in either 54-frame or 676-frame capture whose tag sequence
deviates from the cycle above would falsify this order. None did. A future
falsification would be: a frame where a real hit lands (this probe did not
distinguish hit-landing frames from idle ones) showing collision-driven
side effects reordering fighter update relative to the collision driver —
open, since neither state's plain frames exercised an actual contact this
session.

## What a next probe should break on

- **`0x02082E40`**, not `0x02082E10`, to see the integrator's per-element
  iterations rather than one hit per frame at the pass's entry.
- **The pad-read writer of `obj+0x6C`**, once located, to add input sample
  as an eighth tag (see "Input sample" above).
- **Fighter state `0x1B`** (drive a fighter into that state, e.g. via a
  save state or a poke) and **the `0x02156F6C` toggle path**, to confirm
  the skip behavior read statically for both.
- **A contact frame**, to check whether a landed hit reorders anything
  relative to the idle-frame cycle measured here.
- **Codex's candidate pad-sampling breakpoint, `0x0203A658`** — cited in
  its second opinion as "the known pad-sampling point," not independently
  verified by this session. Adding it as an eighth tag would both answer
  the open input-sample question and, per codex's falsification note #4,
  pin the exact frame boundary (e.g. a trace reading `I -> regen -> PAD ->
  F` would place the boundary immediately before the fighter task).

## Live follow-up (`jus-u7to`, 2026-09-12, round 2/3)

u7to-boundary-2026-09-12
found bench regen's real scheduler task; the frame-cut question is
still open. The routine previously searched for (`0x02077D40`) is only
an inner per-koma tick; its owning task, `0x02076510`, registers sort
key **`0x81000`** — lower than the fighter task's `0x85000` — via the
same `vtable[+0xA0]` insert used by fighter/ObjShot/collision/integrator
(confirmed by disassembly and by a live `$lr` chain landing on the
generic dispatch thunk's custom-callback exit). Corrected ascending
order among gameplay tasks: **REGEN (`0x81000`) → FIGHTER ×2 (`0x85000`)
→ OBJSHOT (`0x88000`) → COLLISION (`0x9E000`) → INTEGRATOR (`0xA1000`)**,
wrap to REGEN — codex's second opinion notes this omits two
infrastructure nodes (keys `0x40000` and `0xA0000`) that also live in the
sorted list, so regen is the first *gameplay* task, not the first node
overall. `PAD` (`0x0203A614`..) is not a scheduler task at all: its live
caller chain traces to the fixed-count array walk
`0x02028EE0`/`0x02028F24` (live `lr=0x02028f94`), which lands between the
integrator and regen every frame — live-proven. Which of two static
candidates drives that walk (the accumulator loop `0x02034690` vs. the
straight-line call inside `0x02041F9C`) is unpicked: both have zero
static callers and neither broke live this session. So **"the frame
boundary sits immediately before `PAD`" is not established** — only
`PAD`'s position between integrator and regen is live-proven. Grade on
this round: PLAUSIBLE, not CROSS_CONFIRMED. Codex's second opinion
(codex_second_opinion_boundary.md)
agrees on the accumulator and the key, and adds: `0x02012A14`/`0x02012AB8`
are node callbacks, not the outer dispatcher; steps per real frame is
unproven.

### Driver pick and in-function order (`jus-u7to`, same day, later)

The falsification test this section called for was run
(RESULTS-driver.md):
1,974/1,974 battle frames hit `0x020422BC` (inside `0x02041F9C`) with a
constant caller; `0x02034738` (the accumulator loop) hit zero. **`0x02041F9C`
is the real driver of the pad walk in this state, not the accumulator
loop.** Reading `0x02041F9C` end to end
(RESULTS-driver-structure.md)
shows the pad-walk pair (`0x02028EE0`/`0x02028F24`) and a
scheduler-dispatch call (`0x020345D4`) are unconditional and strictly
ordered within one call — pad walk first, dispatch last, with only
maintenance/timing calls between them. Codex's second opinion on that
reading
(codex_driver_structure_answer.md)
confirms the ordering but corrects one claim: `0x020345D4` is an
outer/container dispatcher, not the direct walker of the sorted
task-list head `*(0x020A0C34)+0x460` — that direct walk is
`0x02012A14`, reached only as `0x020345D4`'s own callback. Codex also
finds the caller-side loop (`0x02046C40`-`0x02046CA0`, inside
`0x02046BD8`) is a **fixed 4-slot loop**, not a variable-length list
walk, and that neither `0x02041F9C` nor `0x02046BD8` contains a
VBlank/DISPSTAT/VCOUNT wait — so the display-frame boundary is *still*
not pinned; this round only pins the intra-call order (pad before
dispatch), not which side of a real display frame that call falls on.

### Earlier live follow-up (round 1: PAD ordering, `REG_KEYINPUT` read)

Trio Check C
(`pc-momotaro-npc-yusuke-projectiles-about-to-collide`, 2,399 battle-frame
cycles) probed the two items this finding left open: `PAD`'s exact position
and whether the pad routine reads `REG_KEYINPUT`.

- **Measured adjacency**: `PAD` sits between `INTEGRATOR`'s last element
  and `REGEN_TICK`'s first tick — i.e. immediately after the integrator
  pass, immediately before regen, not between `REGEN_TICK` and
  `FIGHTER_TASK` as either candidate placement above implied. Per-cycle
  counts: `REGEN_TICK` × 6 (in 2,398 of 2,399 cycles — the one truncated
  fragment at capture start is the exception), `FIGHTER_TASK` × 2,
  `PAD` × 1, matching this finding's per-frame counts exactly modulo the
  fragment.
- **Input-sample anchor found.** The pad routine at `0x0203A614`.. does
  read `REG_KEYINPUT` (`0x04000130`), at `0x0203A63C` — loaded from a
  literal pool (`0x0203A798` = `0x04000130`) alongside an active-low mask
  (`0x0203A79C` = `0x00002FFF`) — then ORs it with the ARM7 shared-WRAM
  extras at `0x027FFFA8` (read at `0x0203A640`) before the
  `eor`/`and`/mask decode feeding the `tst r1,#1` bit tests. This
  **answers the old falsification question "does it read the register"
  with yes** — the earlier live draft's "never `REG_KEYINPUT`" conclusion
  was a probe-placement error (its breakpoint at `0x0203A640` only caught
  the OR's second operand), corrected in the trio Check C RESULTS.
- **Boundary side still unresolved.** Which gap in the ring is the actual
  frame cut, and which side `REGEN_TICK` falls on relative to it, is not
  settled by this run — see trio Check C RESULTS' "Where the frame
  boundary falls" section. Do not assert that input naturally belongs at
  the start of a frame as a substitute for a measurement; that framing is
  withdrawn.

## Provenance

Probe: `scripts/gdb/e4tok_order.gdb`. Raw logs and RESULTS.md (conditions
blocks, termination, build hash):
frame-order-2026-09-12. Tracker item:
`jus-entity-frame-placement-4tok`. Codex second opinion:
codex_second_opinion_task_order.md.
Codex agrees with the ascending-key order, the rotation reading of the
measured ring, and the frame boundary sitting between the integrator and
the fighter task (unpinned exactly because of regen's unknown key); it
corrects the bucket arithmetic to `(key >> 4) >> 8` rather than `key >> 8`
(folded into the static findings above) and adds the newest-first tie
rule for equal keys and the `0x0203A658` pad-sample breakpoint candidate
(folded into "What a next probe should break on"). No unresolved
disagreement.
