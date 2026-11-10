# Findings: the pair-entry creator is `0x0207ACB8`, called from the broad/narrow-phase overlap test in `0x0207B7F0`

Static only (no emulator). Tracker items: `jus-z87k` (this task), `jus-pb6n`. Grade: **PLAUSIBLE**.

## 1. The question

`docs/confirmed-facts/collision.md` §7 and the GAPS list for `jus-z87k` establish that the
pair loop `0x0207FBD0` only *reads* pair entries — it walks `*(*(rec+0x60)+0x10)`, where
`rec+0x60` is a ColObj (a `0x40`-byte struct created by `0x0207AEDC` with `+0x10` zeroed at
creation) — and tests/routes flag bits already present on each entry. Nothing in the prior
passes located the code that actually decides two objects overlap and allocates the entry.
This doc answers that: who allocates a pair node, writes its `+0x08`/`+0x0C`/`+0x10` fields,
links it where `0x0207FBD0` finds it, and what unlinks it.

## 2. Method

`callers 0x02037B98` (201 hits) and `callers 0x02037C24` (166 hits) turned out to be a dead
end for this specific list: the ColObj pair list is walked in `0x0207FBD0` as a **raw
singly-linked chain via the node's own `+0x00` field** (`ldr r4, [r4]`), not through the
generic head/tail struct that `0x02037B98`/`0x02037C24` maintain for the manager's 22 bucket
queues. So instead of trusting the generic-helper caller list, the search followed the
ColObj creator (`0x0207AEDC`) forward: its callers and its neighbor functions in the
`0x0207AC70`–`0x0207AE9C` block (the leads named in the brief) turned out to be exactly the
allocate/link/unlink trio for this list, confirmed by matching field offsets against
`0x0207FBD0`'s read side.

## 3. The creator: `0x0207ACB8`

```
0x0207ACB8: push {r4, r5, r6, lr}
0x0207ACBC: ldr r4, [r0]            ; r4 = pop head of the manager's node-0 free list (arg0 = manager)
0x0207ACC0: mov r6, r1              ; r6 = A (ColObj)
0x0207ACC4: cmp r4, #0
0x0207ACC8: mov r5, r2              ; r5 = B (ColObj)
0x0207ACCC: moveq r0, #0
0x0207ACD0: popeq {r4, r5, r6, pc}  ; free list exhausted -> return NULL, no pair created
0x0207ACD4: mov r1, r4
0x0207ACD8: bl 0x2037c24            ; unlink r4 from the manager's free list
0x0207ACDC: ldr r0, [r6, #0x20]     ; r0 = *(A + 0x20)
0x0207ACE0: mov r1, r4
0x0207ACE4: add r0, r0, #0x10       ; r0 = (*(A+0x20)) + 0x10  -- the pair list's head/tail struct
0x0207ACE8: bl 0x2037b98            ; tail-append r4 onto that list
0x0207ACEC: str r6, [r4, #8]        ; node+0x08 = A
0x0207ACF0: str r5, [r4, #0xc]      ; node+0x0C = B
0x0207ACF4: mov r1, #1
0x0207ACF8: mov r0, r4
0x0207ACFC: strb r1, [r4, #0x13]    ; node+0x13 = 1
0x0207AD00: pop {r4, r5, r6, pc}    ; return r4 (the new node) in r0
```

`node+0x08`/`node+0x0C` = A/B exactly matches the layout the pair loop reads
(`ldr r1,[r4,#8]` / `ldr r0,[r4,#0xc]` at `0x0207FC14`/`0x0207FC10`). The list-append target
is `(*(A+0x20))+0x10`; the consumer reads the head straight off `ColObj+0x10`
(`ldr r4, [r0, #0x10]` at `0x0207FBFC`, `r0` being the ColObj itself). The two are the same
list only if `*(A+0x20) == A` — a self-pointer set up somewhere in ColObj initialization
that this pass did not directly locate (see Limits, §7). Structural cross-check: the
per-frame unlink pass below (§5) computes the *same* list's head as `add r0, r2, #0x10` with
`r2` = the ColObj **directly**, no `+0x20` indirection — which only reconciles with the
creator's math if that self-pointer holds. Both sides land on offset `+0x10` of the same
kind of object, which is the strongest evidence available without a live watch.

Callers of `0x0207ACB8` (all 3, confirmed via `query.py callers`): the function itself
(entry, not a real caller) plus exactly two `bl` sites, `0x0207B9C8` and `0x0207BA4C`, both
inside `0x0207B7F0`. No other code in the ROM calls this function.

## 4. The overlap test that gates the call (`0x0207B7F0`)

`0x0207B7F0` (size 728 bytes, 1 caller: `0x0207B3EC`) runs a nested double loop over the
manager's active-ColObj list (outer `r6`/`r4` = candidate A, inner `r7`/`r5` = candidate B,
both `+0x08` fields of list nodes built by the ColObj creator). For each `(A, B)` pair it
fetches each side's world position via `0x0207AFDC` (`buf[0..2] = *(*(obj+8)+4)+0x50 .. +0x14`,
i.e. three words read off the owning record's position block) into `sp+0x1c` (A) and
`sp+0x10` (B), then runs two 1-D interval overlap tests, one per axis:

```
; axis 0 (fields +0x2c/+0x30), operands loaded around 0x0207B864-0x0207B8AC
r1 = sp[0x1c]                          ; A position, axis 0
r0 = asr(r1,0xb); r0 = r1 + lsr(r0,20); r0 = lsl(r0,4)
r3 = ldrsh(A + 0x2c) + asr(r0, 16)     ; r3 = A's axis-0 center = extent-field + scaled position
r1 = sp[0x10]                          ; B position, axis 0
r0 = asr(r1,0xb); r0 = r1 + lsr(r0,20); r0 = lsl(r0,4)
r0 = ldrsh(B + 0x2c) + asr(r0, 16)     ; r0 = B's axis-0 center
r2 = |r3 - r0|                         ; abs(delta)
r0 = ldrsh(A + 0x30) + ldrsh(B + 0x30) ; sum of axis-0 half-extents
cmp r2, r0 ; bgt -> skip pair (no overlap on axis 0)
```

The same shape repeats immediately after for axis 1 using fields `+0x2e`/`+0x32` and
position words `sp+0x20`/`sp+0x14`. **The overlap inequality, as an inequality:**

```
|centerA_axis - centerB_axis| > (halfExtentA_axis + halfExtentB_axis)   =>  no overlap, skip
```
for each of the two axes (`+0x2c`/`+0x30` and `+0x2e`/`+0x32`), where `centerX_axis =
ColObj.extentField_axis + scale(position_axis)` and the position comes from
`0x0207AFDC` off the owning record.

If both axis tests pass (broad phase overlap), execution falls into a second, finer nested
loop (`0x0207B90C`–`0x0207BA3C`, outer index bounded by `A+0xc` halfword count, inner bounded
by `B+0xc` halfword count) that repeats the identical `|delta| > sum` test per pair of 8-byte
sub-elements at `A+0x3c + i*8` / `B+0x3c + j*8` (element layout: `+0x0`/`+0x2` = per-axis
center-offset halfwords, `+0x4`/`+0x6` = per-axis half-extent halfwords) — the same
inequality shape, applied per authored hitbox sub-box rather than per whole ColObj.

Each sub-element pair that survives both axis tests calls the creator directly:

```
0x0207B9BC: mov r0, [sp]      ; manager
0x0207B9C0: mov r1, r4        ; A
0x0207B9C4: mov r2, r5        ; B
0x0207B9C8: bl 0x207acb8      ; create node
0x0207B9CC: cmp r0, #0
0x0207B9D0: beq skip-mark
0x0207B9D4: mov r1, #2
0x0207B9D8: strb r1, [r0, #0x10]   ; node+0x10 = 2 (sub-element-level match)
0x0207B9DC: ldr r1, [sp, #0xc]
0x0207B9E0: strb r1, [r0, #0x11]   ; node+0x11 = A's sub-element index
0x0207B9E4: strb sl, [r0, #0x12]   ; node+0x12 = B's sub-element index
```

and, unconditionally once per `(A, B)` pair that passed the broad-phase test (reached whether
or not the sub-element loop found anything, at `0x0207BA40`), a second creator call sets
`node+0x10 = 6` and `node+0x11`/`node+0x12 = 0xff` (object-level match, no sub-element
identified). **`node+0x10` (byte, values `2` or `6` observed) is exactly the field the pair
loop's `bit 2` filter tests** (`0x0207FC04`: `ldrb r0,[r4,#0x10]; tst r0,#4`) — `6 & 4 != 0`
(drops), `2 & 4 == 0` (survives) — so the coarse object-level entry (`6`) is dropped by that
gate and only sub-element-level entries (`2`) reach the rest of the pipeline, unless
`2`'s own low bits happen to collide with other tests upstream. This matches collision.md
§7's drop-test description structurally (same `tst ..., #4`-shaped gate, different call
site than the one already documented there — this one is upstream, at entry-creation
granularity, not at bucket-fill time).

Both creator call sites are also gated on a shared object flag: after either mark, if
`(A+0x18 & 0x80) == 0 AND (B+0x18 & 0x80) == 0` fails the ready-check, the code additionally
ORs `0x10` into `node+0x10` (a "not yet armed" qualifier bit on top of the type code).

## 5. Call chain up

```
0x0207AE9C region (registration)        -- ColMan ctor 0x0207AD3C loads a callback table entry
  literal pool @0x0207AE94 = 0x0207B3EC -- registered via a callback-install call (0x02028384-adjacent)
0x0207B3EC  (size 40, 0 direct bl-callers -- reached only via that registered callback)
  -> bl 0x0207B414   (per-object per-frame bookkeeping / position refresh)
  -> bl 0x0207B7F0   (THE OVERLAP TEST + PAIR CREATION, §4)
  -> bl 0x0207BAC8   (THE UNLINK PASS, §5 below)
```

`0x0207B3EC` has zero `bl`/branch callers in the static index; `xrefs-to 0x0207B3EC` shows a
single `literal_load` at `0x0207ADFC` whose pool word (`0x0207AE94`) equals `0x0207B3EC`,
inside the ColMan constructor `0x0207AD3C`. That constructor loads this address and hands it
to what looks like a registration API (`blx` through a vtable slot at `+0xa0`/`+0x24`/`+0x94`
around `0x0207ADF4`-`0x0207AE34`) rather than calling it directly — consistent with this being
one step of a registered per-frame callback list rather than a hard-coded call, so ordinary
`bl`-caller search cannot find its invoker; only the literal-pool xref does.

## 6. The unlinker: `0x0207AD04`, driven per-frame by `0x0207BAC8`

```
0x0207AD04: push {r3, r4, r5, lr}
0x0207AD08: mov r5, r0        ; r5 = node to remove
0x0207AD0C: mov r4, r1        ; r4 = free-list owner (manager)
0x0207AD10: mov r1, r5
0x0207AD14: add r0, r2, #0x10 ; r0 = (arg2)+0x10  -- same list-head shape as the creator
0x0207AD18: bl 0x2037c24      ; unlink r5 from that list
0x0207AD1C: mov r2, #0
0x0207AD20: str r2, [r5, #8]  ; node+0x08 = 0
0x0207AD24: str r2, [r5, #0xc]; node+0x0C = 0
0x0207AD28: mov r0, r4
0x0207AD2C: mov r1, r5
0x0207AD30: strb r2, [r5, #0x13] ; node+0x13 = 0
0x0207AD34: bl 0x2037b98      ; return r5 onto the manager's free list (the pool the creator pops from)
```

`0x0207AD04` is generic (11 callers total across several call sites, some outside the pair
system — e.g. `0x0207B000`/`0x0207B06C`/`0x0207B088`, a different teardown loop). The pair-list-
specific unlink instances are the three inside `0x0207BAC8` (`0x0207BB18`, `0x0207BB9C`,
`0x0207BBF8`): `0x0207BAC8` walks the manager's active-ColObj list (`r4 = [r8+8]`, the same
list the overlap test's outer loop walks), and for each ColObj walks its pair list starting
at **`r5 = [r4, #0x10]`** — the ColObj's own `+0x10` field, read directly with no `+0x20`
indirection, matching the pair loop's read side exactly. For each node it clears bit 0 of
`node+0x10` (`bic r0, r0, #1`), checks for duplicate-payload nodes against the following
entry (same `+0x08`/`+0x0c` A/B pointers, same `+0x10` low bits `0x3` mask), and calls
`0x0207AD04(node, manager, ColObj)` to free stale/duplicate nodes back to the pool the
creator pops from. This is the **per-frame free**: run every frame, after the create pass
(`0x0207B7F0`) and before whatever consumes the surviving nodes later.

`0x0207BAC8`'s single caller is `0x0207B3EC` (§5), at `0x0207B40C`, immediately after the
create pass `0x0207B7F0` at `0x0207B404` in the same three-call sequence. So within one
registered per-object-manager step, the frame does: refresh positions (`0x0207B414`) ->
create new pair entries for currently-overlapping ColObjs (`0x0207B7F0`) -> unlink/free
stale or duplicate entries (`0x0207BAC8`) -- all before `0x0207FBD0` (the pair loop) runs
later in the frame and consumes whatever is left on each ColObj's `+0x10` list.

## 7. Table of insert/unlink sites

| site | role | evidence |
|---|---|---|
| `0x0207ACB8` | allocate + link node, write `+0x08`=A, `+0x0C`=B, `+0x13`=1 | disasm, §3 |
| `0x0207B9C8` (in `0x0207B7F0`) | call creator, tag `node+0x10=2` (sub-element match) | disasm, §4 |
| `0x0207BA4C` (in `0x0207B7F0`) | call creator, tag `node+0x10=6` (object-level match) | disasm, §4 |
| `0x0207AD04` | unlink node, zero `+0x08`/`+0x0C`, return to free pool | disasm, §6 |
| `0x0207BB18`/`0x0207BB9C`/`0x0207BBF8` (in `0x0207BAC8`) | per-frame stale/duplicate cleanup calling the unlinker | disasm, §6 |
| `0x0207B000`/`0x0207B06C`/`0x0207B088` | unlinker call sites *outside* the pair system (different list, same generic helper) | `callers 0x0207AD04`, not analyzed further |

## Falsification

A live break at `0x0207ACB8` (the creator) must fire once per newly-created pair, with `r1`
(A) and `r2` (B) at entry each resolving to a live ColObj whose owning record is
identifiable (`*(colobj+8)` should be a valid record-shaped pointer). The overlap test's
axis inequality can be checked directly: at the `bgt 0x0207ba90` branches in `0x0207B7F0`
(`0x0207B8AC` and `0x0207B8F8`), `r2` (abs delta) and `r0` (extent sum) should show
`r2 <= r0` on every call that reaches the creator, and `r2 > r0` on every skipped pair. A
watch on `0x0207AD34` (the unlinker's return-to-free-list append) should fire once per frame
per stale/duplicate node, always preceded in the same frame by a matching `0x0207B7F0` create
call for a node that is now being removed.

## Limits

- **Not directly proven:** that `*(A+0x20) == A` (the self-pointer needed to reconcile the
  creator's `(*(A+0x20))+0x10` append target with the consumer's and unlinker's direct
  `ColObj+0x10` read). ColObj creation (`0x0207AEDC`/`0x0207AE38`) sets `+0x20` from a shared
  pool constant (`0x0209FAE0`) at construction time, not to `self` — so either something else
  overwrites `+0x20` with the object's own address before the pair system runs (unlocated in
  this static pass), or the reconciliation is wrong and the creator's list and the consumer's
  list are only *usually* the same list by coincidence of layout. A live watch on ColObj+0x20
  for one object across its lifetime, checked against its own address, would settle this
  directly — this is the load-bearing unresolved piece of the whole finding.
- `0x0207B3EC`'s invocation is inferred from a literal-pool xref into a registration call in
  the ColMan constructor, not from a direct `bl`; the exact per-frame timing of this step
  relative to `0x0207FBD0` (same frame vs. previous frame) was not traced end-to-end through
  the registration/dispatch mechanism.
- No gameplay naming applied anywhere in this doc, per instructions.

## Second opinion and corrections (2026-09-12)

Codex (gpt-5.6-sol, neutral prompt with the full disassembly of
`0x0207B7F0`, `0x0207ACB8`, `0x0207AD04`;
`docs/research/feel-captures/projectile-conflict-2026-09-11/codex_second_opinion_overlap_test.md`)
agrees the test is a two-level inclusive 2D AABB test: broad phase on
`|C_A - C_B| <= H_A + H_B` per axis with `C = s16(obj+0x2C/0x2E) +
trunc(pos/4096)` and `H = s16(obj+0x30/0x32)`; fine phase on sub-elements at
`obj+0x3C + i*8` (`+0` x centre offset, `+2` y centre offset, `+4`/`+6`
half-extents; count u16 at `obj+0x0C`), signed, equality passes, no margin.
Preliminary gates: `A != B` and `(A+0x14 & B+0x10) == 0`.

Corrections to the text above:

- A and B here are `0x64`-byte geometry records allocated by `0x0207B11C`,
  not the `0x40`-byte ColObj; `0x0207B190` writes the owning `0x40` wrapper
  pointer to `A+0x20`. The creator therefore appends to
  `(*(A+0x20))+0x10` = the wrapper's list, which is what the pair loop reads
  as `*(rec+0x60)+0x10`. This resolves the "self-pointer" gap flagged above:
  no self-pointer is needed.
- `node+0x10 = 2` marks a passing fine element pair (`+0x11`/`+0x12` = i, j);
  `node+0x10 = 6` is emitted once per broad-phase overlap with no fine pair
  (`0xFF, 0xFF`). The pair loop's `tst r0,#4` at `0x0207FC04` drops type 6.
  So a **type-2 pair entry present in the list** is the measured definition
  of geometric contact for the projectile layer; loop-header residency of
  type-6 entries (the 148-frame case) is broad-phase-only candidacy.
- Lists are persistent and reconciled per frame (`0x0207BAC8` dedupes and
  frees stale nodes via `0x0207AD04`); node identity can survive frames.

## Live correction (2026-09-12, `jus-z87k`, `pc-taikoubou-upx-npc-yusuke-x`)

The break-at-`0x0207ACB8` falsification above ran
(RESULTS). It confirms the
type-2/type-6 creation mechanics exactly, but the "node identity can
survive frames" language above is wrong for this list and is replaced:

- Over 5,128 captured frames there are 9,094 `CREATE_ENTRY` events and
  9,097 `UNLINK` events. **Zero node addresses recur between two
  consecutive frames.** Every node created in frame N is unlinked by frame
  N+1 (or, from frame 154 onward, within the same frame's window — see
  below) and a fresh node address from the same small pool
  (`0x2209xxx`/`0x220axxx`) is allocated for the same logical (A, B)
  pairing on the next create pass. **The pairing recurs; the node does
  not.**
- The unlink/create ordering itself is not fixed across the whole capture:
  for frames 0-153, a frame's nodes are unlinked at the very start of the
  *next* frame's create pass, before that frame's own creates. From frame
  154 onward, a frame's own creates land first and its unlink block lands
  afterward, inside the same frame's window.
- Wrapper-by-address stability (`*(A+0x20)`) holds only in windows of
  roughly 30-150 frames, not for the life of the record: for
  `A=0x23a03d0`, the wrapper is stable `0x23913e0` for frames 0-158, then
  changes at frame 159 and takes 10 distinct values total across the
  capture.
- Falsification rate, precisely: of 9,094 creations, only 2,545 are
  immediately preceded by a fine-axis `pass=1` (type-2, sub-element
  match); 4,086 are the unconditional type-6 companion call following a
  type-2 creation for the same pair, and 2,463 are a type-6 companion with
  no preceding type-2 in the same pass. `2,545 + 4,086 + 2,463 = 9,094`.
- The frame-62 mixed-pair prediction itself holds exactly as stated below,
  and it turns out to be **one** new wrapper pairing (`0x2391220` x
  `0x2391860`) logged as three directional/per-record entries, not three
  independent new object pairs — one of the three records involved
  (`0x2391900`) was already a habitual partner of `A=0x23a03d0` since
  frame 46, 16 frames before frame 62.

### Node-address mapping to `jus-yv70`

The frame-62 pair nodes this live run tagged map directly onto the
contact-node instances `jus-yv70`
measured earlier from the same probe session:

- `node=0x220a1f4` == yv70's `pair=0x220a1f4` (the mark-path entry).
- `node=0x2209c90` == yv70's `pair=0x2209c90` (the A/B-swapped reverse,
  dropped at `EXIT_N`).
- `node=0x2209de4` == yv70's `pair=0x2209de4` (the third, separate entry
  that drops at `EXIT_D`).

And the record identities: `0x2391aa0` is the tornado record (yv70's rec
`0x2213b04`)'s geometry record, under wrapper `0x2391220`. `0x2391b70` is
the created record (yv70's rec `0x2213c8c`)'s geometry record, under
wrapper `0x2391860`. `0x2391900` is the tornado wrapper's **second**
geometry record — this answers yv70's open question about a "third
contact-node instance": there is no third instance, there is a second
geometry record under the tornado's wrapper, and the pair-generation step
pairs both of that wrapper's records against the new object's one record.

### Hazard: `+0x24` is a per-node carry, not a per-object persistent field

> Superseded, 2026-10-01: this explanation conflates a 0x14-byte pair entry
> with the separate 0x2C-byte participant loaded through geometry `+0x1C`.
> The participant owns `+0x24`, and its release clears all 0x2C bytes. See
> [the object-base and reset correction](participant-overlap-mask-lifetime-static.md).
> The historical reasoning below is retained; the geometric pair-creation
> finding above remains valid.

`0x0207AD04` (the unlinker) zeroes only `+0x08`/`+0x0C`/`+0x13` on a freed
node. It does **not** zero `+0x24`. Because nodes are drawn from a small,
reused pool and node identity does not survive a frame boundary (above), a
node's `+0x24` value — the field the pair loop treats as a per-object
overlap mask that looks persistent within one pairing's lifetime — is
whatever the *previous occupant* of that pool slot left there. A node that
looks like it is "carrying" an overlap mask across frames may in fact be
carrying a stale value left by an unrelated pair that used the same slot
last frame. This is unresolved: no run has yet checked whether `+0x24` is
re-initialized by the creator (`0x0207ACB8`, which does not touch it
either) or by some other write between allocation and the pair loop's
read.

Original falsification note (now executed, see above): a live break at
`0x0207ACB8` in `pc-taikoubou-upx-npc-yusuke-x`; the frame-62 mixed pair
must appear as a type-2 creation with i, j identifying overlapping
sub-elements, and the fine inequalities must hold on the logged values.

## Recovery correction (2026-10-02, `jus-peon`)

The September12 zero-recurrence observation is capture-specific. Accepted
B212/B213 routing traces
show reconciliation retaining the same fine-pair nodes from B212 plan220
through221, changing fresh0x10 to recurring0x11. The bit1 gate at020800E8
skips the recurring pair before the helper. Newly allocated candidates are
not evidence that the routed node is replaced; inspect the reconciled list.
The earlier blanket node-lifetime conclusion is superseded.
