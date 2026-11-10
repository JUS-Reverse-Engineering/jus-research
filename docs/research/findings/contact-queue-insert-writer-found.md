# Findings: the contact-queue insert found — manager bucket 4, tail-append from the pre-pipeline filler

2026-09-09. Static. Tracker item `jus-contact-queue-insert-writer-j2ur` (collision GAPS G3).
Worker: deepseek-v4-flash (general-purpose). Second opinion: `codex exec -m gpt-5.6-sol`,
neutrally framed (Q1–Q6), in full agreement; codex added the stage-4 consumption-side
dedup (§4). Orchestrator spot-checks on the insert site and the append helper matched
both.

**Headline:** the `+0x48` list that stage 4 (`0x02081DDC`, the bit-11 setter) walks is
**`Battle_ColPrmMan + 0x48` = bucket 4**, not a field on the ColPrm record or element.
It is a doubly-linked **FIFO** of 0xC-byte queue nodes; the insert is
`0x02080AA4 add r0, manager, #0x48` + `bl 0x02037B98` (generic tail-append) inside the
pre-pipeline bucket filler `0x0207FBD0`. The p205 "644 immediate-store sweep" was null
because **the insert is not a store to `+0x48`** — the computed-base `add` + helper
call is the same blind-spot class as the contact-array writer.

## 1. Owner and layout (proven, not assumed)

Manager identity: ctor `Battle_ColPrmManCreate 0x0207C4C0` allocates; the driver
`0x0207F480` resolves `r6 = [[arg0+4]+0x10]` and uses it for all 22 bucket heads
(`r6+0x28+i*8`), the active-record list `[r6+0]`, the free lists, and the `+0x154`
contact-array memset — `r6` is the ctor object, and every pipeline stage receives it
as `r0`. Pools built by the ctor:

| pool | base | node | count | free list |
|---|---|---|---|---|
| ColPrm records | `+0x454` | `0x188` | 128 | `manager+0x08` |
| pool nodes | `+0xC854` | `0x2C` | 128 | `manager+0x18` |
| **queue nodes** | **`+0xE354`** | **`0xC`** | **512** | **`manager+0xD8`** |
| clash nodes | `+0xDE54` | `0x10` | 80 | `manager+0x20` |

22 bucket list headers span `+0x28`–`+0xD8`; `manager+0x48` = bucket 4 head,
`+0x4C` = tail. Queue-node layout: `+0x00 next`, `+0x04 prev`, `+0x08 payload` (the
pair-struct pointer).

## 2. The insert

Inside `0x020809C8` (called only from `0x0207FBD0`, at `0x02080188`/`0x020801D0`):

```
0x02080A90  ldr r4, [r7, #0xd8]     ; pop head of 0xC free list
0x02080A94  add r0, r7, #0xd8
0x02080A9C  bl  0x2037c24           ; unlink from free list
0x02080AA0  mov r1, r4
0x02080AA4  add r0, r7, #0x48       ; destination = bucket 4
0x02080AA8  str r6, [r4, #8]        ; node payload = pair pointer
0x02080AAC  bl  0x2037b98           ; TAIL-append
```

`0x02037B98` is a standard doubly-linked tail-append (`node->prev = old_tail;
node->next = 0; old_tail->next = node; list->tail = node`). Removal is `0x02037C24`.
Stage 4 pops from `sl+0x48` (`0x02081E48`/`0x02081E6C`) and returns nodes to
`+0xD8` (`0x02081E54`/`0x02081E5C`), payload zeroed.

**Discipline:** FIFO (tail-append, head-pop). **Dedup: none at insert** — no bucket
search; each call allocates a fresh node. **Capacity: 512 nodes shared by ALL
buckets, no overflow check** (`ldr` yields 0 on exhaustion and `0x02037C24` would
dereference null — the design assumes < 512 contacts/frame).

## 3. Frame position and bucket→stage map

Filled **pre-pipeline, once per frame** by `0x0207FBD0` (called at `0x0207FA64`,
after the frame-start drain of all 22 buckets back into `+0xD8` and after the
contact-array clear, before the pipeline `0x02080C28` at `0x0207FA9C`). The filler
iterates bucket 6 (`manager+0x58`, records filled by the driver's per-record loop at
`0x0207F68C-0x0207F6B4`), walks each record's pair list at `[[record+0x60]+0x10]`,
and enqueues pairs via inline code (buckets 5/7/15/16) and helpers: `0x02080660`
(clash nodes → `record+0x10`), `0x020808C0` (buckets 3/2), `0x020809C8`
(buckets 1/4/8).

| bucket | head | producer | consumer (forwarder order) |
|---|---|---|---|
| 1 | `+0x30` | `0x02080AF4` (in 0x020809C8) | stage 1 `0x02080F14` |
| 2 | `+0x38` | `0x020809B8` (in 0x020808C0) | stage 2 `0x02081B20` |
| 3 | `+0x40` | `0x02080934` (in 0x020808C0) | stage 3 `0x02081D68` |
| **4** | **`+0x48`** | **`0x02080AAC` (in 0x020809C8)** | **stage 4 `0x02081DDC`** |
| 5 | `+0x50` | `0x0207FF98` | stage 5-adjacent |
| 6 | `+0x58` | driver `0x0207F6B4` | `0x0207FBD0` |
| 7 | `+0x60` | `0x0207FD94` | `0x02080C70` |
| 8 | `+0x68` | `0x02080BDC` (in 0x020809C8) | `0x02080E5C` |

**This refutes collision.md §2's "buckets 1 and 8 have no producer anywhere"** —
both are produced by the same computed-base blind spot
([buckets-1-and-8-confirmed-against-complete-index.md](buckets-1-and-8-confirmed-against-complete-index.md)
now carries the refutation banner).

## 4. Stage-4 consumption-side dedup (codex addition)

Stage 4 does not process blindly: for each outer node it rescans the same bucket,
skipping nodes with an identical payload pointer, and for different payloads whose
`[payload+0xC]` words are equal, calls `0x02031070` and uses **bit 4 of its return**
to select which node drains (`0x02081E10-0x02081E24`). So same-key pairs are
arbitrated at consumption, not insertion.

## 5. Bucket-4 gating (why the `jus-x6j` observation saw it empty)

`0x020809C8` reaches the `+0x48` insert only for a narrow flag combination:
A-participant `elem+0x14` bit `0x20000000` set with bits `0x100|0x200|0x400|0xf0`
clear; B-participant `elem+0x14` bit `0x100` set; plus low-byte disjointness tests
against `B+0x20/+0x24/+0x1C`. Ordinary character-vs-character hits route to bucket
1 instead — the static explanation for the runtime observation that `[sl+0x48]` is
empty and the two `orr 0x800` sites are unreachable on a landed hit (tracker item
`jus-x6j` — a retraction tracker item: it rejected the bit-11-setter card, and its
observation of the empty list stands).

## 6. The ColPrm record's own `+0x48`/`+0x4C` — cleared, never written

`0x0207F874-0x0207F87C` (walking the active-record list `[manager+0x00]`) clears
`record+0x48/+0x4C` per frame alongside the `record+0xA4` scratch memset — but
**no writer to record+0x48 exists** anywhere: p205's 644-hit store sweep, the
whole-ROM `add/sub #0x48` scan (5 collision-range hits, all accounted), the
`#0x4C` scan, and a complete 38-site audit of every `bl 0x02037B98` call site in
the collision range (only `0x02080AAC` targets `+0x48`; ov6's 14 append sites all
target other offsets). The record pair is **likely dead state**; a one-frame
watchpoint on a live record's `+0x48` (expect only the `0x0207F87C` clear) settles
it. p205's "cleared as a pair by the pipeline's caller (head/tail reading)" was
about this pair — the load-bearing queue was never here.

## 7. Falsification tests

| claim | test |
|---|---|
| insert = `0x02080AAC` | breakpoint there; assert `r7` = manager, `[r4+8]` = the pair |
| FIFO | watch `0x02037BD0`; node `[+0x04]` must equal previous `[manager+0x4C]` |
| capacity 512, unguarded | no `cmp #0x200` guard at `0x02080A90`; free-list depth never negative |
| bucket-4 gate | break at `0x02080A48` on a landed normal hit — must NOT fire |
| record+0x48 dead | one-frame watchpoint on a live record's `+0x48`; only the clear fires |

Unresolved: (U1) the record `+0x48/+0x4C` writer-if-any (runtime watchpoint); (U2)
whether the asymmetric A→B-only gate is the intended dedup or half of one; (U3)
`0x02031070`'s semantics (the consumption-side arbitration key).
