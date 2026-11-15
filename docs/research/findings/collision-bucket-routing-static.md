# Findings: collision bucket routing, static-only pass

Tracker item `jus-tfr0` (static half only — the live-run half is NOT done here). Grade: **PLAUSIBLE** (static
disassembly + citation of already-live-verified datasets; no new emulator/GDB runs in this pass).

Background docs relied on and cited throughout, not re-derived: `docs/confirmed-facts/collision.md` §2/§5/§7,
`docs/research/findings/contact-queue-insert-writer-found.md`, `docs/research/findings/pair-entry-creation-site-static.md`,
`docs/research/findings/pair-loop-drops-class-0x1000-nodes-with-bit0-clear-at-0x0207FD50.md`,
`docs/research/findings/broadphase-bucket-fill.md`, `docs/research/findings/driver-is-the-primary-bucket-filler.md`,
`docs/research/findings/collision-bucket-dataflow.md`, `scripts/gdb/f58_routes.gdb` header,
`docs/research/feel-captures/projectile-conflict-2026-09-11/SUMMARY.md`.

---

## 0. Correction to the task brief's arithmetic

The brief that spawned this pass said "bucket 15 = `0x28+15*8=0x98`, bucket 16 = `0xA0`". That arithmetic is
wrong: `0x28 + 15*8 = 0x28 + 0x78 = 0xA0`, and `0x28 + 16*8 = 0x28 + 0x80 = 0xA8`. So **bucket 15 = `+0xA0`**,
**bucket 16 = `+0xA8`** — not `0x98`/`0xA0`. This matches `broadphase-bucket-fill.md`'s own table exactly
(`0xA0`→15, `0xA8`→16) and my own disassembly below, so I use the corrected values throughout. `+0x98` is
**bucket 14**, not bucket 15.

## 1. Buckets 15/16 append sites (my own disassembly, confirms broadphase-bucket-fill.md)

`query.py func 0x0207FBD0` → size 1572 bytes (393 instructions), body `0x0207FBD0`–`0x020801F0` (ends at the
`pop {r4,r5,r6,r7,r8,sb,sl,fp,pc}`). Grepping the full disassembly for `bl #0x2037b98` inside that range gives
exactly four hits — buckets 5, 7, 15, 16 (5 and 7 already attributed per background):

```
0x02080114: a00088e2  add r0, r8, #0xa0        ; bucket 15 head
0x02080118: 9edefeeb  bl  #0x2037b98            ; tail-append -> bucket 15

0x02080004: a80088e2  add r0, r8, #0xa8         ; bucket 16 head
0x02080008: e2defeeb  bl  #0x2037b98            ; tail-append -> bucket 16
```

(`r8` = the manager, `mov r8, r0` at `0x0207FBD8`, written exactly once in the whole function — same anchor
`broadphase-bucket-fill.md` uses.) Immediately before each: `mov r1, r5` (bucket 16, payload = a node popped
from free list `+0xD8` at `0x02080000`) / `mov r1, r5` (bucket 15, same shape, pop at `0x020800FC`), then
`str r7, [r5, #8]` after the call sets the queue node's payload. Both are the same FIFO tail-append shape as
buckets 1/4/5/7/8 (`contact-queue-insert-writer-found.md` §2).

## 2. The 12 "unattributed" buckets — mostly already attributed elsewhere, plus two new finds

Recomputed offsets for the task's unattributed set {0,9,10,11,12,13,14,17,18,19,20,21} (bucket i → `0x28+8i`):
`0x28, 0x70, 0x78, 0x80, 0x88, 0x90, 0x98, 0xB0, 0xB8, 0xC0, 0xC8, 0xD0`.

**A complete ROM-wide census settles almost all of these without a manual sweep.** `driver-is-the-primary-
bucket-filler.md` already censused all 145 `bl 0x02037B98` call sites ROM-wide and found the per-frame driver
`0x0207F480` links into buckets **0, 6, 9, 11, 12, 13, 14, 17, 20, 21** (ten buckets, each preceded by an
unlink from the free list at `+0xD8`, `0x0207F4B8`–`0x0207F81C`). That resolves 9 of the 12: {0, 9, 11, 12,
13, 14, 17, 20, 21}.

I independently re-ran this census (arm9 only, complete: `grep -n 'bl.*2037b98' jus_files/analysis/disasm/arm9.txt`
→ 100 sites, each site's immediately preceding `add r0, rX, #imm` extracted) and it reproduces the driver's
ten targets exactly, plus buckets 1–8/15/16/clash-list per the existing docs, **plus two new targets not in
any prior doc**:

```
0x02081AEC: b80086e2  add r0, r6, #0xb8
0x02081AF4: 27d8feeb  bl  #0x2037b98            ; -> bucket 18

0x02081B10: c00086e2  add r0, r6, #0xc0
0x02081B18: 1ed8feeb  bl  #0x2037b98            ; -> bucket 19
```

These are inside a previously-unnamed helper at `0x02081AB0` (`query.py func 0x02081AB0` → size 112,
callers = `0x02080F14` and `0x02081DDC`, i.e. it is called **from inside the stage-1 and stage-4 forwarders**
— `contact-queue-insert-writer-found.md`'s table names both of those as the consumers of buckets 1 and 4
respectively). Disassembly (`query.py disasm 0x02081AB0 112`):

```
0x02081AB0: push {r4,r5,r6,lr}
0x02081AB4: r3 = *(r1+0x14)            ; r1 = node arg, r6 = mov r0 (manager), r5 = mov r2 (payload)
0x02081AC0: tst r3, #0x1000000
0x02081AC4: beq 0x2081afc              ; bit CLEAR -> straight to bucket 19 append (0x02081B10-18)
0x02081AC8: r0 = *(r1+0xc)             ; bit SET: r0 = *(node+0xc) = the node's owning record
0x02081ACC: r0 = *(r0+0x28)
0x02081AD0: cmp r0, #0
0x02081AD4: popne {r4,r5,r6,pc}        ; r0 != 0 -> return, NO append to either bucket
                                        ; r0 == 0 -> fall to bucket 18 append (0x02081AD8-F4)
```

Both call sites (`0x020819D4/D8` inside the stage-1 forwarder, `0x02082074/78` inside the stage-4 forwarder)
gate the *call itself* on the record's own `+0x40` word: `tst [record+0x40], #0x4000000; bne <skip the call>`
— the helper is only invoked when that bit is CLEAR. `0x4000000` (bit 26) is record-side, not node-side —
DO NOT confuse with the node `+0x14` bit-26 shatter-classification bit (`shatter-classification-bit26.md`);
this is a different struct at a different offset, same numeric bit position, unnamed here.

So: **buckets 18 and 19 both have producers now** — a third fork of the "computed-base blind spot" pattern,
this time reached only from inside stage-1/stage-4 consumption rather than from the pre-pipeline filler or
driver. Node `+0x14` bit `0x1000000` (bit 24) has no prior name; flagged as a raw bit, not invented meaning.

**Producer coverage after this pass: 21 of 22 buckets.** Only **bucket 10 (`+0x78`)** has zero append call
anywhere in the complete 100-site arm9 census (and the overlay side was already swept by
`contact-queue-insert-writer-found.md` §6's "38-site audit... ov6's 14 append sites all target other
offsets" for the same helper). **Bucket 10 is genuinely open — no producer found anywhere in the ROM by this
method.** (It is possible bucket 10 is filled by a direct pointer store bypassing `0x02037B98` entirely, the
same class of blind spot `buckets-1-and-8-confirmed-against-complete-index.md` and
`contact-queue-insert-writer-found.md` originally worried about for buckets 1/8 before those were found —
not ruled out here.)

**Consumer side**, from `collision-bucket-dataflow.md`'s register-lifetime-restricted scan (stages 4-7) and
`contact-queue-insert-writer-found.md`'s table (stages 1-3):

| bucket | producer | consumer |
|---|---|---|
| 0 | driver `0x0207F648` | not found |
| 9 | driver `0x0207F744` | **unconfirmed candidate**: `ldr r0/r1,[sl,#0x70]` at `0x020803F8`/`0x02080488`, inside stage 7's body but *outside* the register-lifetime window `collision-bucket-dataflow.md` verified (stage 7 reassigns its arg0 24×) — flagged unconfirmed, not claimed |
| 10 | **none found** | not found |
| 11 | driver `0x0207F5C4` | stage 7 `0x020802D0` (`collision-bucket-dataflow.md`) |
| 12 | driver `0x0207F7C4` | **unconfirmed candidate**: `ldr r4,[r7,#0x88]` at `0x020821CC`, register provenance not traced |
| 13 | driver `0x0207F688` | **unconfirmed candidate**: `ldr r1/r0,[r5,#0x90]` at `0x020821E8`/`0x02082214`, register provenance not traced |
| 14 | driver `0x0207F610` | not found |
| 17 | driver `0x0207F77C` | **unconfirmed candidate**: `ldr r1/r2,[r8,#0xb0]` at `0x02081578`/`0x02081F8C`, register provenance not traced |
| 18 | helper `0x02081AB0` (called from stage-1 fwd `0x02080F14`) | not found |
| 19 | helper `0x02081AB0` (called from stage-4 fwd `0x02081DDC`) | not found |
| 20 | driver `0x0207F7F0` | not found |
| 21 | driver `0x0207F81C` | stage 6 `0x020805E8` (`collision-bucket-dataflow.md`) |

None of the "unconfirmed candidate" consumer sites are claimed — they are grep hits on the right immediate
offset without a verified manager-register anchor, exactly the trap `collision-bucket-dataflow.md` §1's "scan
bug" and `buckets-1-and-8-confirmed-against-complete-index.md` §2's "filter bug" both document. Live test
spec §6 covers how to settle them.

## 3. Routing table — predicate path to each append site

Chain 1 begins at loop header `0x0207FC20` (r4=pair entry, r6=nodeA, r7=nodeB — `f58_routes.gdb` header).
EXIT_A–EXIT_N as defined in that header (task background reproduces them verbatim; not restated here except
where needed for the row). "Survives" = every earlier EXIT test in the list evaluates false (not taken).

| append site | bucket | predicate (survives listed EXITs, then...) | source |
|---|---|---|---|
| `0x0207FF98` | 5 | inline in `0x0207FBD0`, chain-2 classification region (`0x0207FE5C`+); per codex's independent read (§5, UNVERIFIED): low bytes of `A+0x14`/`B+0x14` both nonzero AND `[[A+0xC]+0x78] & 0x20` set; processing continues past this append rather than terminating | collision.md §2, `broadphase-bucket-fill.md`; gating detail: codex §5 (unverified) |
| `0x0207FD94` | 7 | survives EXIT_A..EXIT_M, then EXIT_N false, then `0x0207FD6C` `helper_20808A4(nodeB+0x14,nodeB+0x18)` returns 1 (bit `0x1000` set AND `+0x18` bit0 clear) — OR the naruto-observed shortcut that skips the helper call entirely and appends directly (`SUMMARY.md` "Blind routes and exits" answer 2); codex's §5 reading resolves the shortcut condition as `halfword[nodeB+0x24] & low24(nodeB+0x14) == 0` (UNVERIFIED) | `f58_routes.gdb` header; `SUMMARY.md`; codex §5 (unverified) |
| `0x02080118` | 15 | inline in `0x0207FBD0`, chain-2; per codex (UNVERIFIED): `[A+0x14] & 0x20000` set AND `[B+0x14] & 0x10000` set | this doc §1, `broadphase-bucket-fill.md`; gating: codex §5 (unverified) |
| `0x02080008` | 16 | inline in `0x0207FBD0`, chain-2; per codex (UNVERIFIED): survives type-byte/`+0x1C`-bit-28 tests, then `[[A+0xC]+0x38] & 0x800` and `[[B+0xC]+0x38] & 0x800` both clear | this doc §1, `broadphase-bucket-fill.md`; gating: codex §5 (unverified) |
| `0x02080AF4`/`0x02080AF8` | 1 | via helper `0x020809C8`; narrow flag combination on nodeA/nodeB `+0x14`/`+0x20`/`+0x24` bytes (ordinary character-vs-character hits route here per §5 below) | `contact-queue-insert-writer-found.md` §5 |
| `0x02080AAC` | 4 | via helper `0x020809C8`; **A-participant `elem+0x14` bit `0x20000000` set with bits `0x100\|0x200\|0x400\|0xf0` clear; B-participant `elem+0x14` bit `0x100` set; plus low-byte disjointness tests against `B+0x20/+0x24/+0x1C`** | `contact-queue-insert-writer-found.md` §5 verbatim |
| `0x02080BDC` | 8 | via helper `0x020809C8`; the branch not taken by bucket 1 or 4's gates (control dataset's rec70-as-A/rec11-as-B took this route) | `contact-queue-insert-writer-found.md`; `SUMMARY.md` control outcome |
| `0x020809B8` | 2 | via helper `0x020808C0`; internal flag-test fork not taken by bucket 3 (see next row) | `f58_routes.gdb` header's `0x020808C0` bullet |
| `0x02080934` | 3 | via helper `0x020808C0`; entry r0=manager, r1=record, r2=pair entry; reads objA=`*(r2+8)`, objB=`*(r2+0xc)`, record's own `+0x40`; a chain of node/record flag tests `0x020808D8`-`0x02080990` selects bucket 3 vs bucket 2 — exact bit values not disambiguated in any doc, flagged GAP | `f58_routes.gdb` header verbatim |
| `0x0208087C` | clash list (`record+0x10`, NOT a numbered bucket) | via helper `0x02080660`; entry r0=manager, r1=record, r2=pair entry, r6=nodeB (`*(objB+0x1c)`); gated by a swept-AABB-shaped chain of position/velocity comparisons `0x020806D8`-`0x0208081C` on nodeB `+0x28`-derived shorts and record `+0x2c..0x3a` shorts, not a flag test; node popped from manager free list `+0x20` | `f58_routes.gdb` header verbatim |
| `0x02081AF4` | 18 | via new helper `0x02081AB0`, called from inside stage-1/stage-4 forwarders only when consumer-side record `+0x40` bit `0x4000000` is CLEAR; then node `+0x14` bit `0x1000000` SET and `*(*(node+0xc)+0x28) == 0` | this doc §2 |
| `0x02081B18` | 19 | same call, but node `+0x14` bit `0x1000000` CLEAR (unconditional once the call happens) | this doc §2 |

Step-12 ambiguity from the task background (the `nodeB+0x24 & (nodeB+0x14 & 0xFFFFFF)` test's exact branch
gating before the `helper_20808A4(nodeB)` call) is **not resolved by this pass** — flagged as a live GAP per
the brief's own instruction not to invent an answer.

## 4. Node-class → bucket predictions vs the three datasets

Class values used directly per the task background (fighter body `0x2000000x`, projectile `0x1000100x`),
not re-derived.

**(fighter body, projectile) — dataset 1 control.** Fighter body has node`+0x14` bit `0x1000` clear (not a
`0x1000100x` value), so `helper_20808A4` on either node returns 0 regardless of `+0x18`. The chain-1
predicate for bucket 7 (EXIT_N false, then helper(nodeB) == 1) requires nodeB's class bit `0x1000` set — true
here only if nodeB is the projectile. Predicted outcome from the chain alone is ambiguous without the exact
bucket-1/4/8 gate values (§3's flagged GAP for `0x020808C0`'s fork and the full `0x020809C8` gate), so the
chain does not by itself predict "bucket 8" — it predicts "possibly bucket 7 if nodeB=projectile survives to
EXIT_N/helper, otherwise falls to chain 2's helper-based routing (1/2/3/4/8)." **Dataset 1 observed: bucket 8**
(`SUMMARY.md` control outcome, rec70-as-A [projectile] → helper path → bucket 8). This is **consistent** with
chain 1 not claiming bucket 7 for this pair (EXIT_A tests `nodeB+0x14 & 0x00080800`, which is plausible to be
set for a fighter-body B given the `0x800`-class bits `record-0x34-is-a-mutable-flag-api...md` documents) and
chain 2 (helper `0x020809C8`) resolving it to bucket 8 instead. **No disagreement found**, but this is a weak
confirmation — the chain does not independently derive "bucket 8" without citing the already-known bucket-8
gate, which itself is undocumented in bit-level detail (§3 GAP).

**(projectile, projectile), both bit0 set — dataset 2 naruto.** Both nodes have `+0x14` bit `0x1000` set. If
bit0 (`+0x18`) is set on both (as background states for this dataset), `helper_20808A4` returns 0 for both
(needs bit0 CLEAR to return 1), so EXIT_N (helper(nodeA)==1) is FALSE for both directional entries — survives.
Then at step 12, `helper_20808A4(nodeB)`: also 0 for both by the same logic → **chain predicts NO bucket-7
append, straight to mark gate, for both directional entries.** **Dataset 2 observed:** entry `0x220968c`
(rec49 as A) DID append to bucket 7 (via an observed "shortcut" that skips the helper call entirely — not
predicted by the documented step-12 branch shape) while entry `0x2209e70` (rec50 as A) did not append but
still marked. **Disagreement:** the chain-predicted symmetric "no append, mark only" outcome does not match
one of the two directional entries — the naruto capture shows an asymmetric route (one shortcuts to bucket 7,
the other doesn't) that is not accounted for by the EXIT_N/step-12 predicate chain as documented. This
mirrors `SUMMARY.md`'s own finding under "Blind routes and exits" answer 2 and the order-dependence caveat
there (entry `0x220968c` writes nodeA's `+0x24` before entry `0x2209e70` reads the same node as nodeB) — cited,
not re-derived. **Both objects marked either way**, which the chain does predict (mark gate is reached
regardless of the bucket-7 branch).

**(projectile, projectile), both bit0 clear — dataset 3 yugi/dice.** Both nodes `+0x14` = `0x1000100x`
(bit `0x1000` set), bit0 (`+0x18`) CLEAR on both. `helper_20808A4(nodeA)` = 1 (bit `0x1000` set AND bit0
clear) → **EXIT_N fires, chain predicts DROP at EXIT_N.** **Dataset 3 observed: frame 2 dropped at EXIT_N,
frames 3-4 dropped at EXIT_M instead** (not EXIT_N) — `pair-loop-drops-class-0x1000-nodes-with-bit0-clear...md`;
`SUMMARY.md` cross-state table. **Partial match**: the chain correctly predicts a drop with no bucket/no mark
for this class combination, but the *specific* EXIT differs frame-to-frame (EXIT_N once, then EXIT_M twice) —
consistent with EXIT_M's own persistent side effect (`nodeA+0x24` OR'd on a prior frame's fallthrough) changing
which test fires later, not a contradiction of the drop-vs-append prediction itself. Chain 2 (all
helper/clash sites) recorded zero hits for either directional entry, also as predicted (nothing survives
chain 1 to reach chain 2 for either direction). **No disagreement on the headline outcome (drop, no bucket,
no mark); disagreement only on which single EXIT fires in which frame, which the chain's own EXIT_M
persistent-state note explains rather than contradicts.**

**(body, body) — no dataset available.** Both nodes have `+0x14` bit `0x1000` clear (fighter-body class is
`0x2000000x`, not `0x1000100x`), so `helper_20808A4` returns 0 for both regardless of `+0x18` (needs bit
`0x1000` set as a precondition). EXIT_N never fires for either. The pair would fall through chain 1's
class-bit-27 fork (EXIT_F/EXIT_G/EXIT_H, gated on nodeA `+0x14` bit `0x8000000`) — whether that bit is set for
a fighter body is not stated anywhere in the given background and is **not derived here** (would require
tracing the bit's writer, out of this pass's scope). **Unverified, no live data** — the chain's prediction
for (body, body) cannot be completed without that one bit's meaning, which this pass does not claim to know.

## 5. Codex second opinion

Ran `codex exec -m gpt-5.6-sol --skip-git-repo-check` in the background with a neutrally-framed prompt (no
mention of "EXIT_A..N" naming or any conclusion) asking it to read the raw disassembly of the gate chain
`0x0207FC20`+ and the four helpers (`0x020808A4`, `0x020809C8`, `0x020808C0`, `0x02080660`, plus the newly
found `0x02081AB0`) and state each branch's condition and bucket target in its own words. The full transcript was not kept.

**Agreement.** Codex's own trace of the `0x0207FC20`-`0x0207FD98` chain lines up address-for-address with
every EXIT_A–EXIT_N test in the task background (same bit masks, same struct offsets, same drop-vs-continue
direction), and its reading of `0x020808A4` (`return (arg0&0x1000)!=0 && (arg1&1)==0`) and the bucket-1/4/8
gate inside `0x020809C8` matches `contact-queue-insert-writer-found.md` §5's summary, just with far more
bit-level detail (e.g. bucket 4 requires `flagsA & 0x20000000` set, `B+0x14 & 0x100` set, and `flagsA`'s
`0x100/0x200/0x400/0xF0` bits all clear; bucket 1 is the fallback inside the same `0x20000000`-set branch
when `B+0x14 & 0x100` is clear or the bucket-4 bit combination fails). No disagreement on logic anywhere in
regions 2–4 and 6; region 6 (`0x02081AB0`) matches my own reading exactly (bit `0x01000000`, same three-way
split into bucket 19 / drop / bucket 18), modulo a naming difference — codex calls the argument at `r1`
"record", I called it "node"; the struct role (has a `+0x14` flags word and a `+0xC` pointer to something
with its own `+0x28` field) is identical in both readings, this is terminology only.

**New material codex added that this pass's own disassembly reading did not derive**, all from its
independent read of `0x0207FE5C`-`0x020801E8` ("second pair loop", i.e. what `SUMMARY.md` calls chain 2's
own inline classification, distinct from the `0x020809C8`/`0x020808C0`/`0x02080660` helper calls chain 2 also
makes):

- **Exact bucket-5 gating** (flagged "not documented" in §3 above before this run): `0x0207FF60`/`0x0207FF68`
  test the low bytes of `A+0x14`/`B+0x14` nonzero, then `0x0207FF78` tests `[[A+0xC]+0x78] & 0x20`; if all
  three pass, append to bucket 5 (`+0x50`) — and processing continues past this append (does not end the
  entry the way the other bucket appends do).
- **Exact bucket-16 gating**: survives a chain of type-byte and `+0x1C`-bit-28 tests, then
  `[[A+0xC]+0x38] & 0x800` and `[[B+0xC]+0x38] & 0x800` both clear → append bucket 16 (`+0xA8`).
- **Exact bucket-15 gating**: `[A+0x14] & 0x20000` set AND `[B+0x14] & 0x10000` set → append bucket 15
  (`+0xA0`).
- **A candidate resolution of the task background's flagged step-12 ambiguity** ("the exact gating of what
  happens on each branch of this test is NOT fully disambiguated"): codex reads `0x0207FD64`
  (`halfword[nodeB+0x24] & low24(nodeB+0x14)`) as: if **zero**, append to bucket 7 *directly, no helper call*;
  if **nonzero**, call `helper_20808A4(nodeB+0x14, nodeB+0x18)` and append to bucket 7 only if it returns
  nonzero (matching my doc's reading of `0x0207FD70/74`, but codex's reading additionally explains *why* the
  direct-append branch exists at all). This lines up with `SUMMARY.md`'s naruto observation that one
  directional entry (`0x220968c`) reached bucket 7 with "no `CMP_20808A4` line logged, straight to bucket-7
  append" — under codex's reading that happens exactly when the `nodeB+0x24` AND-test is zero, which is
  consistent with that entry's nodeB not yet having had its `+0x24` written by the *other* directional entry
  (the order-dependence `SUMMARY.md` itself flags as unsettled). **This is codex's reading, not a live
  re-verification** — flagged as UNVERIFIED, a candidate answer to hand to the live half of jus-tfr0, not
  adopted as settled fact here.

**No disagreement found** between codex's reading and the background predicate chain or my own disassembly on
any bucket-append site or bit test; codex's contribution was filling in gaps (bucket 5/15/16 exact gates, the
step-12 candidate resolution) rather than contradicting anything.

## 6. Live test spec (hand-off, NOT run here)

For each item, "confirm" means: instrument the listed breakpoint(s)/watch(es) on the listed field(s), on the
listed states, and check the listed condition.

| target | states | fields to watch | breakpoints | what would confirm/refute |
|---|---|---|---|---|
| Bucket 10 (`+0x78`) producer | any state with high pair-entry volume (e.g. control) | `manager+0x78` (both list-head words) | write-watch on `manager+0x78`/`+0x7C`; if it never changes across N frames while other buckets churn, corroborates "no producer" | any write at all refutes "no producer"; a direct-pointer-store producer (bypassing `0x02037B98`) would still show up here even though it's invisible to the `bl` census |
| Buckets 9/12/13/17 candidate consumers | control + naruto | `sl+0x70` / `[r7,#0x88]` / `[r5,#0x90]` / `[r8,#0xb0]` register provenance at `0x020803F8`, `0x020821CC`, `0x020821E8`, `0x02081578` | breakpoint at each address, log the base register's value and confirm it equals the manager pointer (compare against known manager address from `PASS_ENTRY`) | if base != manager, the candidate is a false positive (same class as the `buckets-1-and-8-confirmed...md` §3 false positive) |
| Buckets 18/19 gating | a state with recorded `+0x40` bit `0x4000000`-clear records | `record+0x40`, `node+0x14` bit `0x1000000`, `*(node+0xc)+0x28` | breakpoint `0x02081AB0` entry; log r1 (node), r6 (manager), r5 (payload); breakpoint `0x02081AC4` (beq taken/not) and `0x02081AD4` (popne taken/not) | confirms the three-way fork (bucket 18 / bucket 19 / no-append) actually exercises all three branches live |
| Step-12 ambiguous B+0x24 gate | naruto-like state (both projectiles, mixed bit0) | `nodeB+0x24`, `nodeB+0x14 & 0xFFFFFF` | breakpoint at `0x0207FD5C`-`0x0207FD6C`, log both operands and which side of the AND is nonzero | settles what the background flags as "exact gating of what happens on each branch of this test is NOT fully disambiguated" |
| Naruto order-dependence (bucket-7 shortcut asymmetry) | naruto, re-run with entry-order swapped if possible | `nodeA+0x24` (the node written first) | breakpoint at `0x0207FD3C` (the strh writing nodeA+0x24) and at the shortcut-fork test the second entry hits | settles whether the asymmetry (§4 dataset 2) is order-dependent (as `SUMMARY.md` suspects) or an intrinsic per-node difference |
| (body, body) pair, EXIT_F/G/H fork bit `0x8000000` on nodeA `+0x14` | any state with two fighter bodies colliding (e.g. two characters clashing, not projectiles) | `nodeA+0x14` bit `0x8000000`, `nodeB+0x14` bit `0x1000` | breakpoint at `0x0207FC5C` (the tst), log both operands | the only missing input needed to complete the §4 "(body,body)" prediction |
| Buckets 5/7/15/16 exact inline gating inside `0x0207FBD0` | control (already has bucket-7/5 traffic) | nodeA/nodeB `+0x14`/`+0x18` at each of the four inline `add r0,r8,#imm` sites | breakpoints at `0x0207FF94`, `0x0207FD8C`, `0x02080114`, `0x02080004` | would give the missing branch conditions this doc's §3 table marks "not documented" for buckets 5/15/16 |

## Predictions status

| Claim | Verdict |
|---|---|
| Buckets 15/16 = `+0x98`/`+0xA0` (task brief's arithmetic) | **REFUTED** — correct values are `+0xA0`/`+0xA8` (§0) |
| Bucket 15 append at `0x02080118`, bucket 16 at `0x02080008` | **CONFIRMED_STATIC** — matches `broadphase-bucket-fill.md` independently |
| 12 buckets genuinely unattributed | **REFUTED** — 9 already resolved by `driver-is-the-primary-bucket-filler.md`; 2 more (18, 19) resolved here via a new helper `0x02081AB0`; only bucket 10 remains open |
| Bucket 10 has a producer somewhere in arm9 | **not found** — complete 100-site census, no hit |
| Chain predicts dataset 1 (fighter+projectile → bucket 8) | **weak CONFIRMED** — consistent but not independently derived (bucket 1/4/8 gate bits undocumented) |
| Chain predicts dataset 2 (projectile+projectile, bit0 set → bucket 7, symmetric) | **REFUTED (partial)** — bucket-7 shortcut asymmetry between the two directional entries not predicted by the documented chain |
| Chain predicts dataset 3 (projectile+projectile, bit0 clear → drop) | **CONFIRMED_STATIC** on the headline outcome; which EXIT fires varies frame to frame, explained not contradicted |
| Chain predicts (body, body) outcome | **not claimed** — missing one bit's meaning (nodeA+0x14 bit 0x8000000 on fighter bodies), unverified |

## 7. Live (jus-tfr0, 2026-09-12)

Live half of this ticket. Full run: `docs/research/feel-captures/bucket-routing-2026-09-12/RESULTS.md`.
Probe `scripts/gdb/tfr0_routing.gdb`, three states/four launches (fighter-vs-fighter melee
`ds8t_jj_battle_noheal`, projectile-vs-projectile + projectile-vs-fighter
`pc-momotaro-npc-yusuke-projectiles-about-to-collide` two runs, naruto asymmetry re-check
`pc-naruto-fy-npc-yusuke-fy`), bridge framecount as the frame basis per the ticket.

- **(body, body) settled in the negative, corrected count** (§4's flagged open item, §6's
  live-test-spec row): the melee run has 84 `LOOP_HDR` entries total, of which 78 are
  body-vs-body (both nodes class `0x2000000x`, `+0x18` bit 0 clear on both sides; pairs
  `0x220963c`/`0x2209664`) and the remaining 6 are attack-vs-body (`0x10000001` vs
  `0x20000002`, pairs `0x220a334`/`0x220a384`, pair-loop passes 654-656) — **zero of the 78
  body-vs-body entries reached any bucket append; one of the 6 attack-vs-body entries did**
  (`BUCKET n=1 frame=654 pair=0x220a384`, "frame" here being a pair-loop pass, not a bridge
  frame — see the FRAME-counter correction below). Which specific EXIT drops the 78
  body-vs-body entries (the EXIT_F/G/H fork on `nodeA+0x14` bit `0x8000000`) was not logged by
  this probe and is still open; only the headline "no bucket for body-vs-body" is settled.
- **The probe's `FRAME` counter is pair-loop passes, not bridge frames**: it increments once
  per `PASS_ENTRY` (`0x0207FAD4`), and the collision driver runs 2-16x per bridge frame. In
  `ds8t_jj_battle_noheal` it reached 1168 (matching 1168 `PASS_ENTRY` hits) against
  `observed_frames=403` — about 2.9 pair-loop passes per bridge frame. Every prior
  counter-derived "frame" figure in this doc and in the live run detail doc should be read as
  "pair-loop passes," not frames (e.g. the momotaro run 2b pair recurring "14 frames" is 14 pair-loop
  passes against that run's 78 bridge frames; the extended momotaro log's own `FRAME` counter
  reached 54 passes in that window).
- **Melee attack-vs-body confirmed live, bucket 1**: one landed hit, `nodeA14=0x20000002`
  (body) / `nodeB14=0x10000001` (attack-hitbox, bit `0x1000000` set, bit `0x1000` clear) →
  bucket 1, matching `contact-queue-insert-writer-found.md` §5's fallback-gate prediction.
- **New class distinction confirmed live**: node `+0x14` bit `0x1000` (not just bit `0x1000000`)
  separates "true projectile" (`0x1000100x`, persists, subject to the `0x020808A4` drop-test) from
  a plain "attack hitbox" (`0x1000000x` only, e.g. a melee move's active frames) — both share the
  bit-24 "attack" class but only the former sets bit 12. This was implicit in prior docs but not
  stated as a live-confirmed distinction until this pass (`pc-momotaro-...`'s frame-1 pair:
  attack-hitbox `0x10000001` vs true-projectile `0x10001002` → bucket 8; its own frame-18+ pair:
  the surviving true-projectile `0x10001001` vs a fighter body `0x20000002` → bucket 1).
- **Bucket 8 vs bucket 1 for "projectile" pairs, disambiguated live**: bucket 8 is not a general
  "projectile involved" bucket — it fired for attack-hitbox-vs-true-projectile (the projectile
  clash itself), while a true-projectile-vs-fighter-body pair (post-clash, one projectile
  surviving) fell to bucket 1 instead, in the same state one extended run later. Bucket 1 is the
  broader fallback across at least three distinct class combinations now (melee-vs-body,
  projectile-vs-body, and — per the static §4 dataset-1 analysis — projectile-vs-fighter-body in
  the pos_base-family control), not a single narrow category.
- **Naruto asymmetry reproduced by an independently-written probe** (§4 dataset 2, §6's live-test
  row): one directional pair entry reaches bucket 7, its mirror does not — same headline result as
  `pair-loop-drops-class-0x1000-nodes-with-bit0-clear-at-0x0207FD50.md` and
  `contact-marks-object-bit-0x2-via-two-sites-gated-on-node-bit0.md`, now confirmed under a second,
  differently-derived instrumentation rather than a rerun of the same script. The order-dependence
  question itself (which directional entry gets the shortcut, and why) is **not** settled by this
  pass — `nodeB+0x24` was not logged here (see the RESULTS.md caveat on a register-read defect at
  the bucket-7 site).
- **Bucket 10 write-watch: zero writes across all four launches, attached window corrected.**
  The watchpoint only lives while GDB stays attached; per-run attached windows were
  `ds8t_jj_battle_noheal` 403 bridge frames, momotaro run 2a 24, momotaro run 2b 78, naruto 24 —
  summing to 529, not the previously stated ~212 (that figure was unsourced). Three of the four
  sessions ended early (SIGTRAP/stdin error, at pair-loop pass 5, 5, and 54 respectively for the
  short runs); only the melee launch (`ds8t_jj_battle_noheal`) gave a long attached window with
  active pair traffic. No static producer was found in the 100-site census; bucket 10 was not
  exercised in that one long window either. Risk low-to-medium; this is a waive candidate
  pending one long-window write-watch run in a state that exercises buckets 2/3/4, not a
  settled "no producer."
- **Buckets 2, 3, 4, and the clash list: not exercised live in this batch** (feel-over-roster —
  three states, not a bucket-by-bucket chase). Left blank in the live table, not inferred.
- Codex second opinion not re-run in this live pass; §5's existing `gpt-5.6-sol` reading was
  checked against this pass's live class-bit values and not contradicted by any of them.
