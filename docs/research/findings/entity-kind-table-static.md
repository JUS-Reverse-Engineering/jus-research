# The 27 ObjShot kind handlers: what each one does at spawn time, statically

Iteration 148. Static only. Region `ov6`.

## What this settles

Follows up
[objshot-manager-and-the-27-kind-dispatch-table](objshot-manager-and-the-27-kind-dispatch-table.md),
which pinned the 27-entry dispatch table's addresses but left every handler
body unread. This pass reads all 27 (fewer actual disassembly sessions,
since several kinds route through shared or wrapper code) and answers the
open questions that finding left:

1. **`0x0216EEF4` is not a stub.** It is a real spawn routine: it reads
   `+0x34`/`+0x3c` on `[owner+0x10]` (the owner's ColPrm record, one
   indirection deeper than the owner pointer itself), folds constants
   `0x1000`/`0x8400000` into them, calls the pooled-entity constructor `0x02083624`
   (`docs/confirmed-facts/entities.md` §3), stores the result at
   `element+0x2C`, and on failure sets `element+0x26` bit 3 — the exact bit
   tested at `0x0216ADF0` in the initializer, closing that half of GAPS
   item 7. On success it calls a further setup routine `0x0216F100`
   (unread, out of scope here). Kinds `0x00`, `0x0F`, `0x15`, `0x16` are
   genuine aliases of one implementation, not four different behaviors.

2. **`0x0216B4F4` is a 7-instruction (`0x1C`-byte) wrapper**, not a handler
   in its own right: it calls `0x0216B514` (kind `0x02`'s own handler) and
   then sets `element+0x26` bit 1. Kinds `0x01`, `0x03`, `0x04` all run
   kind `0x02`'s full body. (The two-instruction shape belongs only to
   kind `0x1A`'s stub, `0x0216B2A0`; it does not describe this wrapper.)

3. **A structural surprise: `0x0216B514` does not call the pooled-entity
   constructor at all.** It stores the *owner pointer* (the handler's `r1`
   argument) directly into `element+0x2C`, then separately claims a slot in
   a small fixed 9-entry, `0x108`-stride table (bit 0 of a byte at
   slot`+0x100` marks occupancy) and records that slot at `element+0x30`.
   For kinds `0x01/0x05/0x0E/0x17/0x18/0x19` this is moot — `0x0216A910`'s
   existing six-kind exclusion (objshot-manager-and-the-27-kind-dispatch-table.md §5.3) zeroes
   `element+0x2C` before anything downstream reads it regardless of what
   the handler wrote. But for kinds `0x02/0x03/0x04` — which are **not** on
   that exclusion list — the value the rest of the pipeline treats as "the
   spawned entity" is an alias of the owner object, not a new pool
   allocation. This is new: the existing six-kind/twenty-one-kind entity
   split in entities.md §5.2 describes *whether* `+0x2C` is read as zero
   or nonzero, not *what kind of object* sits behind a nonzero value.

4. **Family structure beyond the dispatch table itself.** Several handlers
   call each other directly (not through the table), which the table alone
   doesn't show:
   - `0x0216EEF4` (kind `0x00`'s handler) is also called directly by kind
     `0x0B`'s handler, after `0x0B` precomputes an aim/distance vector.
   - `0x0216B514` (kind `0x02`'s handler) is called directly by kinds
     `0x05`, `0x0E`, `0x17`, `0x19` (via tiny wrappers — `0x0E`'s call sits
     at `0x0216B838` inside handler `0x0216B768`), and its 9-slot-claim
     logic is duplicated inline (not called) by kind `0x18`.
   - `0x0216D88C` (kind `0x06`'s handler) is called directly by kinds
     `0x0A`, `0x10`, `0x12`, each of which adds its own extra setup
     afterward (`0x0A` calls `0x0216DD38`; `0x10` and `0x12` both call
     `0x0216DE40`).
   - `0x0216D1CC` (a shared subroutine, not itself a table entry) contains
     the actual `0x02083624` call used by both kind `0x0C`'s handler
     (`0x0216D05C`) and kind `0x14`'s handler (`0x0216D0C8`).
   - `0x02170500` (kind `0x11`'s handler) is called directly by kind
     `0x13`'s handler, which afterward clears a bit on the owner's record
     and populates a secondary position-tracker node — the same node shape
     (`+0xc/+0x10` copied to `+0x14/+0x18`, `+0x34 |= 0x100`) also set up
     inline by kind `0x0D`'s handler.

5. **Kind `0x1A`'s handler is a genuine two-instruction no-op**
   (`mov r0,#0; bx lr`, 8 bytes: `0x0216B2A0`-`0x0216B2A7`). It never
   touches `element+0x2C`, `+0x18`, or `+0x26`. This resolves the
   `functions.json` gap from the earlier finding differently than
   expected: the bytes immediately after (`0x0216B2A8` onward) are **not**
   part of kind `0x1A`'s handler at all — they belong to a separate,
   unrelated function that decrements a signed halfword at `[r0+0x18]` and
   returns whether it's still non-negative. That shape (read `+0x18`,
   decrement, test sign) is the generic per-frame lifetime-countdown
   routine implied by entities.md's lifetime field, encountered here as
   a byproduct of resolving the `0x1A` gap, not as this task's target.

6. **No handler writes `element+0x18`.** Grepped every handler body for
   halfword stores to offset `0x18`; none exist. Two functions incidentally
   *read* `+0x18` (kind `0x12`'s handler mirrors the lifetime value into
   `+0x54`; the unrelated function found under (5) decrements it). This
   confirms, for all 27 kinds, that the lifetime source is the initializer's
   default (30 frames, `0x0216ACC8`) or the caller-supplied param — never a
   per-kind override.

7. **No gravity/integrator flag was found in any handler read.** Several
   handlers compute velocity- or angle-looking halfwords (kinds `0x02`,
   `0x0C`, `0x0E`'s family via `0x0216B514`, `0x14`, `0x18`) via a shared
   angle routine `0x0216E898` or arm9 fixed-point helpers, but `0x0216E898`
   is not distinctive to that family: its `ov6` callers also include
   `0x0216D92C` (kind `0x06`), `0x021700D8` (kind `0x08`), `0x02170594`
   (kind `0x11`), and `0x0216F14C` — so angle setup does not characterise
   the owner-alias family on its own. None of these callers sets a
   distinguishable "apply gravity" bit on the entity or element. The only
   `element+0x26` bits identified are: bit 0 (set by `0x0216AC10`, outside
   any handler), bit 1 (set unconditionally near the end of most handlers
   — reads as a generic "handler ran" flag, not physics), and bit 3 (set
   on `0x02083624` allocation failure at `0x0216ADF0`-adjacent sites, and
   also, in kind `0x07`'s handler, on two pre-allocation gate failures at
   `0x0216DFF0` and `0x0216E004` that branch to `0x0216E1B4` before the
   `0x02083624` call at `0x0216E0B8` is ever reached). This is a negative result, not
   a proof of absence — see CONFIRMED_STATIC/PLAUSIBLE breakdown below.

Full per-kind table:
`docs/research/feel-captures/entity-kinds-2026-09-12/RESULTS.md`.

## Confidence breakdown

**CONFIRMED_STATIC:**
- The dispatch table contents (already confirmed by the prior finding;
  re-cited here, not re-derived).
- `0x0216EEF4`'s body: owner-field read, constant fold, `0x02083624` call,
  `+0x2C` store, bit-3-on-failure, `0x0216F100` on success. (row `0x00`,
  `0x0F`, `0x15`, `0x16`)
- `0x0216B4F4` is a 7-instruction (`0x1C`-byte) wrapper over `0x0216B514`.
  (rows `0x01`, `0x03`, `0x04`)
- `0x0216B514` writes the owner pointer (not a `0x02083624` result) to
  `+0x2C`, and separately runs a 9-slot/`0x108`-stride occupancy scan
  storing the claimed slot at `+0x30`. (row `0x02`, inherited by `0x01`,
  `0x03`, `0x04`, `0x05`, `0x0E`, `0x17`, `0x19`)
- The direct (non-table) call edges listed in point 4 above, cited by
  instruction address in the RESULTS.md table.
- Kind `0x1A`'s handler is `mov r0,#0; bx lr` and nothing else; the
  following bytes are a different, unrelated function. (row `0x1A`)
- No handler halfword-stores to `+0x18`. (all rows, "Lifetime source"
  column)
- The `0x02083624` alloc-fail idiom (bit 3 on `+0x26`) is byte-identical
  across every handler that calls it directly: `0x00`-family, `0x06`,
  `0x07`, `0x08`, `0x09`, `0x0C`/`0x14` (via `0x0216D1CC`), `0x0D`, `0x11`.

**PLAUSIBLE (structural inference, not proven by a labeled string or a
live read):**
- The "owner-aliased" family name for kinds `0x01-0x05`, `0x17-0x19` — the
  code shape supports it, but no live read confirms that treating an owner
  pointer as "the entity" downstream doesn't corrupt the owner record or
  is otherwise semantically intentional versus a code-reuse artifact.
- "Handler ran" as the meaning of `element+0x26` bit 1 — inferred from it
  being set unconditionally near the end of most handlers regardless of
  entity presence, kind, or success/failure; never independently confirmed
  against a reader of that bit.
- Family groupings for `0x0A/0x10/0x12` (extending `0x06`) and `0x0D/0x13`
  (position-tracker node) — based on shared callee addresses and matching
  code shapes, not on a shared label or string.

**[unverified]:**
- Whether kinds `0x03`/`0x04`'s params differ enough from `0x02`'s to
  change the velocity/angle computation path inside `0x0216B514` — params
  block contents were not read per-kind.
- The full bodies of `0x0216B768` (kind `0x0E`), `0x0216EF7C` (kind `0x0B`,
  partially read), and the callee functions `0x0216F100`, `0x0216DD38`,
  `0x0216DE40`, `0x0216E898`, `0x2170B84`, `0x02028384`/`0x020282F4` — read
  only enough to classify the caller, not disassembled themselves.
- Whether `0x0216EEF4`'s owner-field constant fold (`0x1000`/`0x8400000`)
  versus `0x0216B2C8`'s (`0x700`/`0x18400000`/`0x1000`) encodes a
  meaningful category (collision type, damage class, etc.) — only that the
  values differ per handler.
- Any gravity/physics-integration flag — not found in the handlers read,
  but a frame-pass routine (`0x0216AF04`, still unread) could apply gravity
  unconditionally without a per-kind flag at all, which would make "not
  found in the handler" the expected result rather than informative.

## Despawn site — still unresolved, now with a concrete negative result

Attempted call-graph tracing from all 27 handlers to the three despawn
candidates (`0x0216C958`, `0x0216E1C0`, `0x0216F398`,
`docs/confirmed-facts/entities.md` §7). **No kind handler has a traceable
static call edge to any of the three.** Their known callers
(`0x0216C430`/`0x0216CD10` for the first, none found for the second,
`0x0216F7AC`/`0x0216F8D8` for the third) are distinct functions elsewhere in
`BattleObjShot.cpp`, not any of the 27 handlers. This is the expected shape
— despawn runs in the per-frame sweep, not the one-shot spawn handler — but
it means static analysis alone cannot assign a despawn family per kind.
Full detail in the RESULTS.md "Despawn-site tracing" section.

## What a live run must add

None of this static pass observed at runtime. To close GAPS item 2/7
(entities.md), a live run should, for a captured savestate, read:

- the shot element's kind byte (`elem+0x1A`)
- its lifetime field (`elem+0x18`) over several frames, to check whether it
  actually counts down at the generic rate this pass found no override for
- which of the three despawn callbacks (`0x0216C958` / `0x0216E1C0` /
  `0x0216F398`) fires when the element is torn down

across the projectile-census states already captured under
`docs/research/feel-captures/projectile-census-2026-09-10/` — this finding
does not read or interpret those capture files itself; it only flags them
as the right corpus to check the kind-byte-to-despawn-site mapping against,
extending the single Momotaro/Yusuke data point already on record in
[momotaro-yusuke-projectile-conflict](momotaro-yusuke-projectile-conflict.md).

## Live

Iteration for jus-68cu. Follows up the "What a live run must add" section
above with an actual live run: four `pc-*-2026-09-10` savestates, one
melonDS launch and one GDB attach per state, new probe
`scripts/gdb/e68cu_kind_despawn_probe.gdb`. Full corpus census, per-entity
table, state list, and frame-basis caveat in
RESULTS.md "Live".
This section states only the update/teardown rule as this specific sample
shows it; see that section for the raw data and the corrected census.

### Conditions

Same fork_commit/build/JIT state as the rest of this ticket's static pass;
no separate build was used for the live probe. Tool:
`scripts/gdb/e68cu_kind_despawn_probe.gdb`, one melonDS launch + one GDB
attach per state, `press_start.json` to leave the pause menu, then
`scripts/emu/plans/e68cu_probe_run.json` (361 frames, periodic
`RIGHT+Y`/`LEFT+Y`/`RIGHT+X`/`LEFT+X` taps). States and characters (chr_b
indices via [chr_b-Complete-Mapping.md](../chr_b-Complete-Mapping.md)):
`pc-momotaro-npc-yusuke-projectiles-about-to-collide` (Momotaro 67 vs.
Yusuke 32 NPC), `pc-vegeta-x-ichigo-x` (Vegeta 2 vs. Ichigo 39), `pc-taikoubou-upx-npc-kakashi-x`
(Taikoubou 68 vs. Kakashi 23 NPC), `pc-mashirito-y-npx-yusuke-fy`
(Mashirito 57 vs. Yusuke 32 NPC). Full detail, including the corpus census
this section's numbers are drawn from, in
RESULTS.md "Conditions".

**Revision (2026-09-12, same ticket):** a Refuter pass failed the original
version of this section on interpretation. Two corrections carry over from
RESULTS.md's revision and change the vocabulary below: `0x0216F398` and
`0x0216E1C0` are per-frame update/predicate functions, not despawn sites —
neither writes `elem+0x18` or `elem+0x2c`; `0x0216F398` is the tail call of
updater `0x0216F8D8` (`bl 0x216f398` at `0x0216F990`), and `0x0216E1C0`
returns 0/1 through five `pop` exits without ever calling the destructor.
The actual teardown call is `bl 0x2083648` at `0x0216F9C8` inside wrapper
`0x0216F99C` (kind `0x00`'s path) and at `0x0216E3C8` inside wrapper
`0x0216E39C` (kind `0x07`'s path) — the two wrappers are 52-byte structural
twins (`push {r4,lr}` → optional callback through `elem+0x34`/`elem+0x48`
→ `bl 0x2083648` on `[elem+0x2c]` → `pop {r4,pc}`). "Despawns via X" below
now means "last update check at X, teardown through the paired wrapper" —
`DESTRUCT_FIRE`'s `arg0` was never observed to equal an element pointer (0
of 339 fires), so the `elem+0x2c` link to the destructor argument is read
off the disassembly, not independently proven per element this session.

**CONFIRMED_LIVE (this sample: kinds `0x00`, `0x07`, and `0x0b` — not a
claim about the other 24 kinds):**

- Kind `0x00`'s last update check runs at `0x0216F398`; the majority of
  instances reach teardown wrapper `0x0216F99C` and the shared destructor
  `0x02083648` (return address `0x216f9cc`, matching
  [momotaro-yusuke-projectile-conflict.md](momotaro-yusuke-projectile-conflict.md)'s
  teardown trace exactly, now with a kind byte attached: `0x00`). Terminal
  lifetime is exactly `−1` in 39 of the 41 instances that reach the
  lifetime-zero group (1 in the other 2 — an atypical minority, not a
  second mechanism). A second, smaller-check-count group (2 checks,
  lifetime still ~29-31) terminates early for a cause this probe did not
  instrument — see the correction below; the earlier "hit-driven" label
  for this group is retracted.
- Kind `0x07`'s last update check runs at `0x0216E1C0`, on a lifetime-zero
  countdown that reaches exactly `−1` in **63 of 63** instances corpus-wide
  (RESULTS.md corpus census), with a corpus-level 63:63 match to
  `lr=0x216e3cc` fires (not a per-element proof — one specific element
  checked this session had its last update check at seq 55 and the next
  `0x216e3cc` fire at seq 62 belonged to a different element). This still
  confirms kinds `0x00` and `0x07` — both classified "generic/gated
  pooled-entity spawner" by the static read above — use **different**
  wrapper/lr pairs, something static analysis alone could not show.
- Kind `0x0b` (new this revision): 8 creations, all in one state, all
  checked at `0x0216F398`; 6 of 8 checked 33-34 times before terminating at
  lifetime −1 or 0 — the same update-site/wrapper adjacency as kind `0x00`.
  This is a **third kind** sharing that adjacency, updating the earlier
  "2 of 27 kinds" figure to **3 of 27**.

**PLAUSIBLE (structural match, downgraded from a stronger claim this
revision, or not tied to a live kind-byte observation):**

- Kind `0x01` (owner-aliased family): checked every frame at `0x0216C958`
  with lifetime never observed to move, consistent with the static
  no-`elem+0x18`-write finding. **5 of 7** instances corpus-wide end with
  an immediately-adjacent `DESTRUCT_FIRE lr=0x216c588` (three in
  `pc-vegeta-x-ichigo-x`, one each in `pc-momotaro-...` and
  `pc-taikoubou-...`); applying the same adjacency standard used for
  `0x00`/`0x07`/`0x0b`, `0x216c588` is attributed to kind `0x01` on that
  5-of-7 basis (same caveat: not an `elem+0x2c` write-watch proof). The
  earlier "never despawned" framing for this kind cherry-picked the 2 of 7
  instances that don't show the adjacency.
- The self-registered-callback family (kinds `0x05`/`0x19`, per rows above)
  was structurally linked to return address `0x2170040`, but the live
  adjacency evidence now favors kind `0x0d` instead: 15 of 31 kind-`0x0d`
  creations are immediately followed by `lr=0x2170040` (vs. 0 live
  kind-`0x05`/`0x19` CREATEs observed this session) — downgraded to
  PLAUSIBLE against the `0x0d` adjacency rather than asserted for
  `0x05`/`0x19`.
- `0x0216C958`'s own internal "age vs 32 frames" branch (entities.md §7)
  was seen live reaching the destructor (return address `0x216ca90`), but
  this probe cannot attribute that specific hit to a kind byte (the
  element pointer this probe tracks is not the value `0x0216C958` passes to
  the destructor at that call site — see the probe script's header).

**Still open, now with a partial live census instead of zero data:**

- Kind `0x12`: 2 creations, both immediately followed by
  `DESTRUCT_FIRE lr=0x216f9cc` with `arg0` equal to the CREATE's own
  `owner` pointer (an owner-matched adjacency, stronger than a bare lr
  match) — corrected from "never observed reaching the destructor" to
  "no destructor fire independently confirmed via `elem+0x2c`, but an
  owner-matched fire occurs immediately after both creations."
- Kind `0x0d`: 31 creations, none checked at any of `0x0216F398`/
  `0x0216E1C0`/`0x0216C958` in-window; 15 of 31 immediately followed by
  `lr=0x2170040` (see PLAUSIBLE above), 1 by `lr=0x2168ffc`, 15 with no
  adjacent fire. Not settled which lr, if any, is `0x0d`'s real teardown
  path.
- The other 24 kinds not listed above were not exercised live this
  session at all — no claim is made about them.

**Correction — "hit-driven teardown" retracted (item 3):** the earlier
draft called kind `0x00`'s 2-check terminations "hit-driven" with no
contact evidence in the log, and for `pc-vegeta-x-ichigo-x` this directly
contradicts the savestate's own owner testimony
([`INDEX.md:62`](../../../jus_files/save_states/INDEX.md): "the projectile
passes through the beam and does no damage/knockback"). The correct label,
used in RESULTS.md's revision, is **"terminated early, cause not
instrumented"**. A cause-attribution follow-up should add the known
contact-mark breakpoints (`0x02080C18`/`0x0207FDAC`, per
[contact-marks-object-bit-0x2-via-two-sites-gated-on-node-bit0.md](contact-marks-object-bit-0x2-via-two-sites-gated-on-node-bit0.md)),
which this session's probe did not instrument.

## Codex second opinion

`docs/research/feel-captures/entity-kinds-2026-09-12/codex_second_opinion_kinds.md`.
Given the raw dispatch table and three handler listings (`0x0216EEF4`,
`0x0216B910`, `0x0216B2C8`) with no commentary on what they were believed to
do, an independent `codex exec -m gpt-5.6-sol` read reached the same
structural conclusions reached here: `0x0216EEF4` is a shared
creation-backed handler for its four kinds; `0x0216B910` "runs the complete
kind `0x02` initialization, then adds kind `0x05` behavior" (matching the
wrapper/composition read of `0x0216B514` above); and `0x0216B2C8` uses "the
same factory" (`0x02083624`) as `0x0216EEF4` "but not the same high-level
initialization logic." Its output was checked against the actual listings
before being cited here; no hallucinated instruction or address was
propagated.

## Not claimed

- No gameplay/character-move name is used anywhere above for any kind — see
  the task's naming restriction; nothing in the string pool or a
  live/runtime source labels any of these 27 kinds, so every name here is
  structural only.
- This pass does not claim `0x0216F100`, `0x0216DD38`, `0x0216DE40`,
  `0x0216E898`, or `0x2170B84` do or don't touch lifetime/gravity/kill
  conditions — they were identified as callees but not disassembled.
- This pass does not claim which, if any, despawn site pairs with which
  kind. That mapping remains open.
