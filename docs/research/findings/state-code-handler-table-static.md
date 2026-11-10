# Findings: the fighter state-code enum, from its one install path (static)

Tracker item: `jus-bg5t` (absorbs `jus-npdv`). Grade: **PLAUSIBLE, static-only.** Codex
(`gpt-5.6-sol`, neutral framing, transcript below) independently confirms the
core dataflow reading. No emulator run in this pass (STATIC HALF).

**Correction pass (2026-09-12):** a Refuter review of commit `9b4a292`
failed the doc on four points — the table-driven site does not always
install state 9 (it installs 9/10/11/12, §3), two literal install sites
(codes 7 and 22) were missed by the original scan (§2), the code-24/27 flag
write lands on `M+0x3C` not `M+0x78` (§2), and `obj+0x18`/`obj+0x19` have
two writers, not one (a reset routine in addition to the commit routine,
§1) — plus a Thumb-mode caveat on the "34 sites" exhaustiveness claim and
four broken doc links. All are fixed below; this pass also folds in the
runtime corroboration for codes 10/11/12 already on record elsewhere
(`jus-state-code-enum-j39n`, `jus-jh7d`, `jus-kakashi-moveset-map-33lu`).

**Second correction pass (2026-09-12, same tracker item):** a Refuter failed the
supporting sentences around the (already-verified-correct) core anchor
table on several more points, all fixed below — the table's install-code
byte sits at record+4, not record+0 (§3, closing the earlier Codex
base-address open item with no off-by-4), index 0 of the table is a dead
sentinel, code 11's live observation was misattributed to Taikoubou when it
was Momotaro re-pressing his own hotkey (§2, §3.1/§5), two functions were
merged into one in the `M+0x78` writer trace (§6), a stale "0x08/0x80 have
no writer" line contradicted this doc's own findings (§6), 32 not 33 literal
sites have their `mov r1,#N` immediately before the call (§ "Summary"), and
two reverse citations into the combat notes were pointed at their primary sources
instead. See `physics.md §4.5`, the combat notes §2/§13, and the engine notes §3 for
the corresponding grading-axis fixes this pass makes alongside this doc.

## Summary

`obj+0x18`/`obj+0x19` (the fighter state code and its pending byte,
`jus-state-code-enum-j39n`) have **two writers each**, not one as this
finding first claimed and a Refuter pass caught: the commit routine
`0x02159CC4` (ov6), which copies the pending byte `obj+0x19` into the active
byte `obj+0x18`; and the reset routine `0x02159C90`, which zeros both
`obj+0x18` and `obj+0x19` directly (`strb r1,[r0,#0x19]` / `strb r1,[r0,#0x18]`
at `0x02159CAC`/`0x02159CB0`, `r1=0`) as part of zeroing the whole
handler/pending struct. `obj+0x19`'s **staging** writer (as opposed to the
reset) is still the single setter `0x02159D34`, called from exactly one
wrapper, `0x02157494` — and `0x02157494` is called from exactly **34** sites
in ov6 (verified exhaustively by grepping every `bl #0x2157494` in
`disasm/ov6.txt`; no other overlay or arm9 site can reach it, since `bl` is
PC-relative and ov6 is the only region holding this address range). **Caveat
on that exhaustiveness claim:** the grep is text-level over an ARM-mode
listing; ov6 also contains Thumb regions, and a Thumb `bl` to the same target
would not match the ARM-encoding grep pattern. The state-machine region
(`0x02157xxx`–`0x0215Exxx`) is itself ARM, which is why the 34-site count is
trusted for *this* region, but the claim does not cover a hypothetical
Thumb-mode caller elsewhere in ov6. This closes most of the "who writes the
pending pair" gap the closed tracker item `jus-state-code-enum-j39n` left open, and
turns "static candidate" into "static install site" for most of the residual
codes the combat notes §2 lists as static-only.

**Of the 34 call sites, 31 pass a literal `mov r1, #N` in the same basic
block as the call — N is read directly off the instruction, not inferred from
a branch gate.** Two sites, `0x0215C444` and `0x0215C45C`, share one literal
hoisted to `0x0215C424`, above the `+0xC8` gate at `0x0215C428–30` that
selects between them (§2, both install code 23) — same value, reached via a
shared literal load rather than a `mov r1,#N` after the last branch. The 34th
(`0x02159E64`) loads r1 from a byte table instead (`0x021712C0`, stride 12;
see §3). Combined, this is a from-code enumeration of every value the game
ever assigns to the pending state byte in this overlay, not a guess from
consumer behavior.

## 1. The two-stage writer chain (confirmed, Codex-agreed), plus the reset writer

```
0x02159CC4 (F0, the "commit" routine, called once per obj per something —
            scheduling not reconfirmed this pass, see physics.md §7 for the
            per-frame task order already established elsewhere):
  if obj+0x04 (active handler) != obj+0x0C (pending handler):
    call obj+0x08 (active exit-hook) if set, clear it
    obj+0x1A = obj+0x18            ; save previous state code
    obj+0x04 = obj+0x0C            ; promote pending handler -> active
    obj+0x08 = obj+0x10            ; promote pending exit-hook -> active
    obj+0x14 = obj+0x16            ; promote a pending halfword too
    obj+0x18 = obj+0x19            ; promote pending state code -> active
    obj+0x10 = 0
  call obj+0x04 (the now-active handler)

0x02159C90 (the reset routine, the other obj+0x18/obj+0x19 writer):
  zero the whole handler/pending struct on obj, including:
    obj+0x19 = 0   (0x02159CAC, strb)
    obj+0x18 = 0   (0x02159CB0, strb)
    obj+0x1a = 0, obj+0x14 = 0, obj+0x00/0x04/0x08/0x0c also (re)initialized

0x02159D34 (F2, "stage a pending transition", the only STAGING writer of
            obj+0x19 — obj+0x19 also gets zeroed by the reset above):
  set_pending(obj, newStateByte, newHandlerPtr, newExitHookPtr):
    if obj+0x10 (existing pending exit-hook) set: call it, clear it
    obj+0x19 = newStateByte
    obj+0x0C = newHandlerPtr
    obj+0x10 = newExitHookPtr
    obj+0x16 = 0

0x02157494 (F1, thin wrapper, the only caller of F2):
  F1(obj, newStateByte, newHandlerPtr, newExitHookPtr):
    F2(obj, r1, r2, r3)              ; tail-call, unconditional
    ; then unrelated work using its OWN 5th stack arg (a bit-0x10-gated
    ; OR/BIC of M+0x3C bit 0x2 off [[obj+0x1b4]+0x56c]+0x3c — nothing to do
    ; with the state machine; do not conflate this with the state install)
```

So `obj+0x18`/`obj+0x19` have exactly two writers between them: the promote
(`0x02159CC4`) and the reset-to-zero (`0x02159C90`). "The only obj+0x19
staging writer" (`0x02159D34`) remains true and is what the rest of this doc
traces; the reset writer only ever installs `0`, so it does not add any new
non-zero state code to the enum and does not change §2's table.

Codex's neutral read (asked without being told this framing) reaches the
same conclusion independently: "F2 stages a transition descriptor, and F0
promotes it to the active descriptor... that lifecycle strongly supports
pending versus active state machinery," and on the literal-argument question:
"the literal `r1 = N` is the best available evidence that the call site
stages state/category code N... interpreting N as the requested
state/category code is much stronger than interpreting it as an unrelated
animation ID or sub-index." Full transcript:
`docs/research/feel-captures/register-2026-09-12-statecode/codex-statecode-install-sites.txt`
(saved from this session's `codex exec` run; see §4 for the exact prompt).

One caveat Codex raises and this pass agrees with: F0 detects a transition
*only* via `active_handler != pending_handler`, not via the code byte alone.
If two call sites stage the same code with different handlers (seen: state
16 has five distinct handler-pointer pairs across five call sites, state 24
has three, state 23 has two), F0 still promotes on handler change; the code
byte is best read as **state-code metadata carried by a handler-defined
transition**, not an independent selector.

## 2. Every literal state-code install site (33 of 34)

Table format: **code** (hex/dec) | **install call site** | **containing
function** (the state's own per-frame handler/decision routine — this is
"which handler installs code N", i.e. the combat notes §2's missing "structural
description") | what the surrounding code reads/writes, in brief.

| code | call site | containing fn | structural note |
|---|---|---|---|
| 0 idle | `0x0215D398` | `0x0215D2E4` (24 callers) | shared idle/landing dispatcher, reached right after invoking the victim's per-frame **reaction handler** `obj+0xFC` (`ldr r1,[r0,#4]->[+0x68]->[0]->[+0xFC]; blx r1` — the same pointer physics.md §4.5 documents); branches on `obj+0xDB` to install 0 (idle) here or 13 (landing) at the sibling site below |
| 1 walk | `0x0215D750` | `0x0215D6F8` | installed only when two gate calls (`0x2159910`, `0x21599D0`) both return false — i.e. "no dash-start condition, no [other] condition, so plain walk" |
| **2 dash** | `0x0215D8E0` | `0x0215D860` | gated on `obj+0xD9 < obj+0xD8` (`ldrb`/`ldrb`/`cmp`/`movlo`) — a counter-vs-limit pair, plausibly the dash-burst frame counter and its 12-frame limit (physics.md §6.3) |
| 3 guard | `0x0215EA04`, `0x0215EA70` | `0x0215E9A0` (2 sites, same fn) | one path also writes `obj+0x11A = 6` (unrelated field, not the state code — do not conflate) right before installing 3 |
| 4 jump start | `0x0215DB90` | `0x0215DB50` | gated on `bl 0x2159930` returning 0 and `obj+0x6C` bit `0x10` clear |
| **5 double-jump start** | `0x0215E280`, `0x0215E2C0` | `0x0215E1D0` (2 sites, same fn) | one path increments `obj+0xDC` (`ldrsb`, `+1`, `strb`) gated on `obj+0xDD` — plausibly the jump-count/charge tracker |
| 6 airborne | `0x0215DC84` | `0x0215DBA4` | reached after `obj+0xDB += 6` and `obj+0x1E8 += 1` (two counters bumped just before) |
| 6 airborne (alt) | `0x0215DF00` | `0x0215DEC8` | reached when `bl 0x215D904` returns false |
| **7** | `0x0215E104` | `0x0215E0CC` | omitted from the first pass, added after a Refuter re-check; gated on `obj+0x6C & 0x12 == 0x12` (`and r1,r1,#0x12; cmp r1,#0x12`) — runtime-confirmed as fast-fall (runtime-report-2 §(ii); physics.md §4.5) |
| **8 hitstun** | `0x0215AE10` | `0x0215A978` | this is the per-frame fighter-update / hit-receive routine physics.md §4.5 already names (contains the hitstun-formula store `0x0215AD58`); reached via `bl 0x215AF1C` |
| **13 landing** | `0x0215D37C` | `0x0215D2E4` | the "else" branch of the idle/landing dispatcher above — same reaction-handler-driven fork as code 0 |
| 14 | `0x0215DD2C` | `0x0215DCAC` | reached when a function pointer read off `obj+0x1D8` returns nonzero, OR'd with a second condition into r5; tentative "combo/attack-string advance" reading not confirmed |
| 15 | `0x0215E49C` | `0x0215E470` | gated on ColPrm scratch `M+0x40` bit `0x400` (`[[obj+0x1a8]+0x10]+0x40`) — the same `M+0x40` field physics.md §4.5's `GROUND_ENTRY` write (`orr M+0x40, #8`) touches, so this is a ColPrm-flag-driven transition, not an input-driven one |
| **16** | `0x0215E588` | `0x0215E534` | also writes `obj+0xCE = 0xA` (10) just before installing 16 — `obj+0xCE` is physics.md §4.5's **invincibility timer** (set to 40 after a falldown reaction); this site sets a shorter 10-frame grant, consistent with a landing-adjacent recovery window |
| 16 (alt) | `0x0215E700` | `0x0215E5C0` | gated on a byte at `obj+0x100+0xE7` (the reaction-selector neighborhood, physics.md §4.5's `obj+0x100` copy of the latched hit-type) |
| 16 (alt) | `0x0215E7F0`, `0x0215E80C` | `0x0215E724` | both arms of a 3-way switch on the same `obj+0x100+0xE7` byte (values 1 and 2) land on 16 — the third arm (value else) is untraced this pass |
| 16 (alt) | `0x0215E8EC` | `0x0215E854` | reached on the "else" arm of an `obj+0x6C` field write, mirrors the pattern at 0x0215E9E4 (which installs 6, not 16) |
| 17 | `0x0215B0AC` | `0x0215AF34` | reached after a sibling call `mov r1,#0xB(11); bl 0x2157450` (§3.1 — a *different* setter, not this state machine; do not read that 11 as a state-code observation) |
| 18 | `0x0215B108` | `0x0215AF34` (same fn as 17, second call) | preceded by `mov r1,#0x20; bl 0x215B2B0` then `mov r1,#0; bl 0x215F2D8` — two unidentified helper calls |
| 19 | `0x0215BF0C` | `0x0215BEA8` | preceded by `mov r1,#0xE(14); bl 0x2157450` (same sibling-setter pattern as 17) |
| **22** | `0x0215BFD4` | `0x0215BF70` | omitted from the first pass, added after a Refuter re-check; early-returns if `obj+0x18 ∈ {8, 0x17, 0x18}` before reaching the install, preceded by `mov r1,#7; bl 0x2157450` (sibling-setter pattern), and writes `obj+0x119 = 0x78` immediately after installing 22 |
| **20** | `0x0215AB98` | `0x0215A978` (same fn as 8, different site) | clears two halfwords at a scratch object's `+0x24`/`+0x26` (plausibly staged knockback vx/vy — matches physics.md §4.5's "fixed handler `0x0215B568` ... victim element's vx/vy zeroed" fallback pattern) before installing 20; **hypothesis, not confirmed**: 20 may be the victim-side launch/knockback-reset entry that is distinct from 8 (hitstun) itself |
| **21** | `0x0215C2CC` | `0x0215C278` | this is the exact function containing the `cmpne r0,#0x15; cmpne r0,#8; cmpne r0,#0x17; cmpne r0,#0x18` filter chain `research/feel-captures/register-2026-09-03/static-state-codes.md` already flagged at `0x0215C290` — direct confirmation that 21's install site and that filter chain are the same routine, i.e. 21 genuinely groups with {8, 23, 24} here |
| **23** | `0x0215C444`, `0x0215C45C` | `0x0215C360` | two paths, selected by a global byte (`[pc-loaded ptr]+0xC8 != 0`), install the **same** code 23 with two different handler-pointer pairs — confirms the static "23 is a range-boundary/class code" reading: the code is stable, only the handler varies |
| **24** | `0x0215C5B8` | `0x0215C488` | also sets ColPrm flags word **`M+0x3C` bit `0x20000000`** via the OR helper `0x0207CE7C` (`mov r1,#0x20000000; bl 0x207ce7c`; confirmed at the disasm level — `ldr/orr/str [r0,#0x3c]`, not `+0x78`) immediately before installing 24. **Withdraw** the first pass's claim that this "corrects" `research/feel-captures/register-2026-09-03/static-state-codes.md`'s `M+0x78` bit `0x10000000` guess — a Refuter re-check found the write is to `M+0x3C`, a different field entirely, so it neither confirms nor corrects the `M+0x78` guess |
| 24 (alt) | `0x0215C6F0` | `0x0215C690` | two calls to `0x215911C` with r1=1 then r1=0 immediately before (a set/clear pair on some other flag) |
| 24 (alt) | `0x0215C80C` | `0x0215C704` | reached only when two prior checks (`0x215CCD4`, `0x215C824`) both return nonzero |
| **25** | `0x0215CACC` | `0x0215CA44` | preceded by `ldr r0,[r5,#0x1B4]; mov r1,#1; mov r2,#0; bl 0x2078660` — `obj+0x1B4` is the slot-base field the orchestrator's HANDOFF notes as `*(obj+0x1B4)`, consistent with physics.md §4.5's "24 then 25 as the deck switched to the next character" (deck-switch path touches the slot base right before installing 25) |
| **27** | `0x0215CD74` | `0x0215CD2C` | preceded by `mov r1,#0xF(15); bl 0x2157450` (sibling-setter pattern again) **and** the **same** `M+0x3C` bit `0x20000000` write (`mov r1,#0x20000000; bl 0x207ce7c`) that state 24's site makes — 24 and 27 share this flag write on `M+0x3C` (not `M+0x78`), which is internally consistent with both being on the static "KO/can't-act" side of the enum |

## 3. The one table-driven site, corrected: it installs 9, 10, 11, *or* 12, not always 9

**Correction (Refuter FAIL on the first pass of this doc):** the first pass
of this doc sampled only the first 8 of the table's entries and all 8
happened to read `0x09`, so it concluded the table-driven site "always
installs pending state 9." A Refuter re-check pulled the full table and
found that claim is wrong past entry 10 — the table installs four different
codes depending on which entry is selected. Corrected reading below.

`0x02159E64` (inside `0x02159D7C`) is the lone non-literal install site:
`r1` is loaded via `ldrsb r1, [r0, r5]` from a byte table with record base
**`0x021712BC`**, where `r5 = r4 * 0xC` (`mov r0,#0xC; mul r5,r4,r0` at
`0x02159E00-04`) — a **stride-12** array, not stride-1 or stride-4. **Table
base resolved, no off-by-4:** the disassembly gives two distinct literals —
`0x021712BC` at `0x02159E08`, used by the word load at `0x02159E14`, OR'd into `obj+0xC4`, which is the move's **cancel mask**, not an unrelated word ([cancel-windows-static-2026-09-25.md](../findings/cancel-windows-static-2026-09-25.md) §2; live: C4 = `0x2` after a Kakashi neutral B and `0x3FE` after air B, cancel-live-checks-2026-09-25), and `0x021712C0` at `0x02159E48`, used
by the `ldrsb` at `0x02159E50` that actually reads the install-code byte.
`0x021712C0` is `0x021712BC + 4`: the record base is `0x021712BC` and the
install-code byte sits at **record+4**, not record+0. (Same bytes, other framing: the anim word is read from `0x021712B8` at `0x02159F4C`, so the record can also be read as starting at `0x021712B8`, with the mask at +4 and the install byte at +8.) The table has **23
records** (index 0–22, `0x021712BC`–`0x021713C8`), with the last `0x0a` byte
at `0x021713C8` (index 22); index 0 is a **dead sentinel** — `cmp r4,#0;
beq` at `0x02159DBC-C0` returns before the table lookup is ever reached for
index 0, so no call site selects it live.

`r4` (the table index) is not a raw slot id read off the fighter object; it
comes from a **function-pointer-table call**, `ldr r1,[r2, arg1<<2]; blx r1`
at `0x02159D94-9C` off the pointer table at **`0x02172178`**, where `arg1` is
this function's (`0x02159D7C`) own first argument. Across all 11 call sites
of `0x02159D7C`, `arg1` only ever takes the values `{0, 1, 2}` — i.e. `r4` is
produced by one of exactly **three classifiers** selected by the caller, not
an open-ended slot/move id. `r4` is also range-checked against `0xD`/`0xE`
(13/14) just after (`cmp r4,#0xD; cmpne r4,#0xE`) on one path, consistent
with it being a small, bounded move-class id.

**The install-code byte of each 12-byte record (record+4), read across the table (verified via
`query.py disasm 0x021712BC 200 --overlay 6` this pass, file byte order,
sanity-checked against the `bl 0x2157494` encoding at `0x02159E64` itself —
`8af5ffeb` == word `0xEBFFF58A` == `bl 0x2157494`, matching):**

| table index (`r4`) | install-byte address (record+4) | byte at record+4 (install code) |
|---|---|---|
| 0 | `0x021712C0` | dead sentinel, never reached (§3) |
| 1–10 | 10 entries, `0x021712CC`–`0x02171338` | `0x09` (9, attack) |
| 11 | `0x02171344` | `0x0c` (12) |
| 12 | `0x02171350` | `0x0b` (11) |
| 13–22 | 10 entries, `0x0217135C`–`0x021713C8` | `0x0a` (10) |
| ≥23 | — | table reads zero from `0x021713D4` on; not a live entry |

So this call site installs pending state **9, 10, 11, or 12**, selected by
the move-class id `r4`, not a constant 9 — this is the missing install site
for states 9, 10, 11, and 12, and explains why no `mov r1,#9/10/11/12`
literal exists anywhere in the literal-site scan above (`0x02159D7C`
reaching this point also clears the same `+0x24`/`+0x26` staged-velocity
halfwords the code-20 site clears, and checks `obj+0xC0` against a
bitmask — plausibly an attack-availability mask).

**This closes three of the "no install site" gaps §5 previously listed**:
codes 10 and 12 get a static install site here for the first time, and code
11 gets a static site that matches the runtime finding already on record
(`jus-jh7d`, the hotkey-self-re-press "dream attack": pending at
`obj+0x19` press+3, committed `obj+0x18` press+4, runs 47 frames, no SP
cost — see `docs/research/feel-captures/dream-attack-2026-09-12/RESULTS.md`
and `dream-attack-hotkey-repress.md`). It also **corroborates live**, beyond
jus-jh7d: Kenshin's X move reads `0x0A` (10), Momotaro re-pressing his own
hotkey R reads `0x0B` (11) (state `pc-taikoubou-npc-jotaro-dark-tournament`,
dream-attack RESULTS.md Plan B — the leader, Taikoubou, has no hotkey; the
prior wording misattributed this observation to Taikoubou), and Kakashi's
SELECT ultimate reads `0x0C` (12) — three of the four table outputs each
have an independent runtime observation on the same value the table
produces.

Codex agrees this is sound dataflow, not analogy ("the selected table byte
supplies the pending state/category code for that transition, for the
selected table entry"), while correctly declining to extrapolate the table's
*full* extent or the meaning of the other two bytes per entry (which do
vary — `ff/ff`, `08/11`, `09/12` alternating) beyond what this pass showed
it (see §4).

### 3.1 A second setter exists and must not be confused with this one

Several call sites above are preceded by `mov r1, #N; bl 0x2157450` where N
∈ {7, 0xB(11), 0xE(14), 0xF(15)} — this looked, before disassembly, exactly
like more literal state installs. **It is a different function.**
`0x02157450` takes `(obj, value)`; it is gated on `obj+0x1A8` being non-null
(`cmp r0,#0; beq`), and only when set does it pass `[obj+0x1A8]+0x14` to
`0x0207A878` before continuing unconditionally to `0x215f278(obj+0x1A0,
value)`, then computing something via `0x2157434` and passing it to
`0x2083950` alongside `obj+0x1A8`. None of this
touches `obj+0x19`/`obj+0xC`/`obj+0x10` (verified: it is not `0x2159D34` and
does not call it). **The values 7, 11, 14, 15 seen here are not state-code
observations** — they are arguments to whatever `0x2157450` installs (a
move/attack sub-id or similar), and should not be read into the state enum
despite the superficial resemblance to the real setter's calling pattern.
This is exactly the kind of "leading premise" trap;
flagging it explicitly so no later pass re-introduces it.

## 4. Codex second opinion (neutral framing, transcript)

**Two Codex runs exist.** The first (below) is the original pass's; a
Refuter re-check flagged it as "partially leading" — it supplied labels
("pending state byte", "already independently confirmed to be a small
state/category enum") in the question text itself, and withheld the table's
contents beyond one call site, so Codex could not have caught the "table is
not constant 9" error even in principle. A second, more neutral run was
made this pass: field names are stripped of interpretive labels
(`Function A`/`B`/`C` instead of `F0`/`F1`/`F2`, no "pending"/"active"
in the prompt itself, disagreement invited on every label), and the full
23-record table (indices 0–22, install byte at record+4) is given instead of 8 samples. Transcript:
`docs/research/feel-captures/register-2026-09-12-statecode/codex-statecode-install-sites-neutral.txt`,
prompt: `codex-statecode-install-sites-neutral-prompt.txt`, same model
(`gpt-5.6-sol`).

The neutral run reaches the same three conclusions as the original run
(two-stage transition reading sound; literal `r1=N` is direct evidence for
staging `N` at `+0x19`; the table produces four different values, not one),
and additionally **flagged a real inconsistency this doc had not caught at
the time**: the table's base address was given in two places as
`0x021712BC` and `0x021712C0`, four bytes apart, and Codex correctly noted
that `ldrsb r1, [r0, r5]` with `r0 = 0x021712BC` and `r5 = index*12` would
put index 0 at `0x021712BC`, not `0x021712C0`.

**This open item is now closed** (jus-bg5t, this pass): re-reading the
disassembly resolves it as neither a base-address discrepancy nor an
off-by-4. There are two distinct literals for two distinct purposes —
`0x021712BC` at `0x02159E08`, used by an unrelated word load at
`0x02159E14` (OR'd into `obj+0xC4`), and `0x021712C0` at `0x02159E48`, used
by the `ldrsb` at `0x02159E50` that actually reads the install-code byte.
The record base is `0x021712BC`; the install-code byte lives at
**record+4**, not record+0, which is exactly the missing +4 Codex flagged.
`r0` is not "loaded with a +4 already applied" as a base-pointer quirk —
the addressing is `record_base + index*12 + 4`, and `0x021712C0` is simply
`0x021712BC + 4`, i.e. the install-byte address for index 0 (§3 above).

No disagreement between the two Codex runs, and no disagreement between
either run and this doc's readings, beyond the base-address flag above,
which this pass's re-read now resolves.

Original run's transcript (kept for provenance):
`docs/research/feel-captures/register-2026-09-12-statecode/codex-statecode-install-sites.txt`.
Prompt gave Codex only the raw disassembly (F0, F2, the F1 call-site literal
list, and the one table-indexed site) with three independent questions and
explicit instruction to disagree if the framing was wrong. Codex's answers,
condensed:

1. "Yes, with high confidence" that F2 stages a pending transition (code +
   handler + exit-hook) that F0 promotes — matching this doc's §1.
2. "Yes" — the literal `r1=N` is the strongest available evidence for "this
   site stages code N," stronger than any animation-id/sub-index reading,
   *given* the independent (pre-existing, not re-derived by Codex) evidence
   that `obj+0x18` is a small state/category enum.
3. "Yes, for the selected table entry" — the table-byte-to-pending-code
   dataflow is direct, not an analogy — but Codex correctly declines to
   extrapolate the table's size, full contents, or the other bytes per entry
   from what it was shown, matching §3's own caveats.

No disagreement between this pass and Codex on any of the three questions.

## 5. Enum size and remaining gaps

**No single "enum size" constant was found this pass.** There is no bounds
check on `obj+0x19`/`obj+0x18` itself in either writer pair (the commit
`0x02159CC4`/reset `0x02159C90` pair for `obj+0x18`, or the staging setter
`0x02159D34` for `obj+0x19`) — unlike the earlier-suspected `cmp r2,#0xc`
jump table at `0x02157494+0x38` (size 13), which this pass traced and found
is a **different**, unrelated 13-entry dispatcher (indexed by its own 3rd
argument, not by the state code — do not cite it as the state enum's bound;
it lives immediately after F1 in the same function block and was the
initial false lead in this pass). The practical bound is empirical: the
highest value assigned by any literal or table-driven site is **27**
(`0x1B`), matching the combat notes §2's existing candidate list; nothing in this
pass found a value above 27.

**Anchored set is now {0..25, 27}** — every value from 0 through 25, plus
27 (26 unanchored, nothing above 27 anchored):
- **0, 1, 2, 3, 4, 5, 6, 7, 8, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23,
  24, 25, 27** — literal `mov r1,#N; bl 0x2157494` install sites (§2; 7 and
  22 added this pass after the Refuter re-check found the first pass's scan
  had omitted them).
- **9, 10, 11, 12** — the single table-driven site `0x02159E64` (§3,
  corrected this pass): table index 1–10 installs 9, index 11 installs 12,
  index 12 installs 11, index 13–22 installs 10; index 0 is a dead sentinel
  (`cmp r4,#0; beq` at `0x02159DBC–C0`). This is a from-code anchor,
  not a consumer-side inference, for all four codes:
  - **9 (attack)** — table-anchored, as the first pass already found for
    its 8 sampled entries.
  - **10 (special/X)** — table-anchored this pass (index 13–22); also
    runtime-confirmed independently (`jus-state-code-enum-j39n`, GDB;
    Kenshin's X move observed reading `0x0A` live, corroborating the same
    value the table produces).
  - **11** — table-anchored this pass (index 12). This is also the
    hotkey-self-re-press "dream attack" the runtime finding
    `jus-jh7d` names: pending at `obj+0x19` press+3, committed at `obj+0x18`
    press+4, runs 47 frames, no SP-bar cost (Momotaro re-pressing his own
    hotkey R observed reading `0x0B` live — state
    `pc-taikoubou-npc-jotaro-dark-tournament`, dream-attack RESULTS.md
    Plan B; the leader, Taikoubou, has no hotkey, so this was never
    Taikoubou's own move). The first pass's claim that "11
    was never observed as a real state-code install, only as the sibling
    setter's argument" is **withdrawn** — that caveat is still true of the
    *specific* `0x0215B08C` sighting (§3.1's sibling setter really does take
    an unrelated argument value of 11 there), but it no longer means state
    code 11 itself lacks an install site; it has one, via the table.
  - **12 (SELECT ultimate)** — table-anchored this pass (index 11); also
    runtime-confirmed on Kakashi (`jus-kakashi-moveset-map-33lu`, SELECT
    input observed reading `0x0C` live).

**Codes still without any install-site anchor after this pass:**
- **26** — never observed live or statically, by literal, by table, or by
  any consumer-side branch gate.
- Anything **above 27** — no evidence either way; the hitstun table
  `0x02171488` has entries out to index 59 (physics.md §4.5 already notes this),
  but nothing in this pass ties any index above 27 to a real `obj+0x19` write.

## 6. `obj+0x78` ground/air byte: partial, mostly unresolved this pass

**Start here next pass (Refuter lead, not yet fully traced):** `M+0x78` is
not a latched flags byte — it is **rebuilt every frame** by arm9 code, not
just OR'd/BIC'd occasionally by ov6 state installs. Confirmed this pass:
- `0x0207ECC0` and `0x0207ED08` are **not** in the same function as
  `0x0207F8DC` — this pass's first-draft grouping was wrong. `0x0207ECC0`
  and `0x0207ED08` are both inside arm9 function `0x0207E864` (size 1976
  bytes), while `0x0207F8DC` is inside a separate arm9 function `0x0207F480`
  (size 1736 bytes, ending `0x0207FB48`). Two distinct per-frame functions,
  not one. Both perform conditional `orr`/`bic` writes to `[r4, #0x78]`
  every call — e.g. `orreq r0,r0,#0x100` then `streq r0,[r4,#0x78]` at
  `0x0207ECD8-E0`, `bic r0,r0,#0x40000` at `0x0207ECF8-0x0207ED00`, and
  `orr r0,r0,#4` at `0x0207ED28-30`.
- `0x0207F8DC`'s own function additionally **replaces** the low bits of
  `[r4,#0x78]` each pass with `(r7 & mask2) | ((r7 & mask1) << 4)`
  (`0x0207F8BC-D4`), i.e. part of the byte is a shifted copy of another part
  of itself, recomputed from two pc-relative literal masks — this is
  consistent with "not latched" and explains why no isolated static writer
  for bits `0x08`/`0x80` was ever found by searching for a literal store of
  just those bits: they may only ever appear as **transients** produced by
  this per-frame recombination (transient byte values `0x2A`, `0xA2`, one
  frame each, seen immediately after a dash ends —
  runtime-report-2
  §(iii), an 11,400-frame `JUS_WATCH` on `M+0x78` that recorded every write
  from `0x0207F8DC`/`0x0207ECC0`/`0x0207ED08`), not written directly
  anywhere.
- **Not yet done:** tracing the exact mask literals at `0x0207F8C0`/`0x0207F8C4`
  bit-for-bit against `0x08`/`0x80`, and confirming which of `0x0207ECC0`/
  `0x0207ED08`/`0x0207F8DC` runs first each frame. That is the concrete next
  step, not a re-scan of ov6 static writers (already exhausted, see below).

The rest of this section is the first pass's ov6-only findings, kept for
context:

- The existing static write-site catalog
  (`research/feel-captures/register-2026-09-03/static-state-codes.md`)
  analyzed **`M+0x78`** (`[[obj+0x1a8]+0x10]+0x78`, the ColPrm scratch
  object's flags word) exclusively, and found no isolated writer for bits
  `0x08`/`0x80` — only the combined `0x22` literal and several high bits
  (`0x100000`, `0x30000`, `0x200000`, `0x4000000`, and — corrected §2 —
  `M+0x3C`'s `0x20000000` for code 24/27, which is a **different field**,
  not `M+0x78`).
- This pass found **two direct `strb`-to-`obj+0x78`** sites that write the
  fighter **object's own** `+0x78` byte directly — `0x0215918C`
  (`mov r0,#0; strb r0,[r5,#0x78]`, `r5=obj`, inside `0x0215911C`) and
  `0x02159568-6C` (`movne r0,#1; strbne r0,[r5,#0x78]`, inside `0x02159538`).
  **These are candidate direct writers of a byte the task calls "obj+0x78"
  as opposed to the ColPrm-relative "M+0x78" the earlier pass analyzed** —
  but this pass could not confirm `0x0215911C`'s `obj+0x78` is the *same*
  ground/air byte the AR-code tracker item (`jus-fighter-object-ar-plus-0x78-p7um`)
  reads, versus an unrelated byte that happens to share the offset. The
  function's own logic (an array-slot activation helper, `obj+0x7C` as a
  0x18-byte-stride array base, gated on its own `r1` index argument) reads
  more like general fighter-substate bookkeeping than ground/air tracking,
  and the values written (`0`, `1`) don't match the documented ground/air
  byte-values (`0x22`/`0x20`/`0x00`/`0x02`/`0x24`/`0x40`/`0xC0`) cleanly —
  `0` is consistent with "air" but `1` is not one of the documented values
  at all. **Do not cite these two sites as ground/air writers without
  disambiguating obj-direct vs. ColPrm-relative `+0x78` first** — flagging
  this explicitly since it is exactly the kind of same-offset/different-struct
  trap the repo's own hazard notes warn about elsewhere (see `record+0x18`/
  `+0x20` dual-use note in `research/Battle-Engine-Map.md`).
- **Bits `0x08` and `0x80` do have writers** — they are not a residual gap.
  This first-pass line contradicted this section's own opening: they are
  produced every frame by the `0x0207F8DC`/`0x0207ECC0`/`0x0207ED08`
  rebuild traced above, and the 11,400-frame watch in
  runtime-report-2
  §(iii) shows every write from those three pcs, including the `0x2A`/`0xA2`
  transients that carry the two bits. What is still unresolved is only the
  bit-for-bit mask trace and write-order item flagged above, not the
  existence of a writer.

**Live test spec for the next runtime pass** (ride-along, cheap):
1. Drive a launcher hit through to landing while logging `obj+0x18` at 60Hz
   on the victim — falsifies/confirms the code-20 hypothesis (§2: predict a
   frame or two at 20 between the hitstun(8) entry and the eventual
   airborne/landing sequence, distinct from the already-confirmed 10/11
   launch-family static guess that runtime already disproved for 10).
2. Same capture, watch for 16 immediately before/at a landing that follows a
   fast-fall or a knockback pop specifically (not a plain jump landing) —
   falsifies/confirms "16 = hard-landing/brief-invincibility variant" (§2:
   the `obj+0xCE=10` write at one of 16's five install sites is the strongest
   lead so far).
3. Drive an actual KO and log `obj+0x18` plus `M+0x78` across it — confirm
   23→24→25 order and check whether `M+0x78` bit `0x20000000` (not
   `0x10000000`) actually appears set at that point, correcting or
   confirming §2's code-24/27 finding live.
4. Log `obj+0x78` (both the object-direct byte at `0x0215918C`'s site and the
   ColPrm-relative `M+0x78` low byte) side by side during a normal
   grounded-to-airborne transition, to settle whether they are the same
   field read two ways or two different fields sharing an offset.
5. No live lead found this pass for state 10's write site, 11, 12, 26, or
   `M+0x78` bits `0x08`/`0x80` — a `JUS_WATCH` on `obj+0x19` (not `obx+0x18`,
   to catch the pending write a frame earlier) across a special (X) input
   would show the actual PC of state 10's real install site, which static
   analysis in this pass could not locate.

## Provenance

- Static reads: `python3 scripts/analysis/query.py` (func/callers/disasm) and
  direct `grep`/byte-order reading of
  `jus_files/analysis/disasm/ov6.txt`, original pass, 2026-09-12.
- Correction pass (same day): re-verified via
  `python3 scripts/analysis/query.py disasm ... --overlay 6` at
  `0x02159C90` (reset writer), `0x0207CE7C` (confirms `M+0x3C`, not
  `M+0x78`), `0x0215E0CC`/`0x0215E104` (code 7), `0x0215BF70`/`0x0215BFD4`
  (code 22), `0x021712BC` (full 23-record table dump), and `0x02157450`
  (sibling-setter gate) — all against `ov6`/`arm9`, per tracker item `jus-bg5t`.
- Second correction pass (same day, docs-only, no emulator): re-checked the
  table addressing at `0x02159E08`/`0x02159E14` and `0x02159E48`/
  `0x02159E50` (record+4 resolution, closing the Codex base-address open
  item), the `0x02159DBC-C0` index-0 sentinel gate, `0x0207E864`/
  `0x0207F480` function bounds (query.py func/size), and re-read
  dream-attack RESULTS.md
  and runtime-report-2
  for the code-11 attribution and the `0x08`/`0x80` writer citations.
- Codex second opinions: `codex exec -m gpt-5.6-sol`. Original (leading)
  prompt: `codex-statecode-install-sites-prompt.txt` /
  `codex-statecode-install-sites.txt`. Neutral re-run (this pass):
  `codex-statecode-install-sites-neutral-prompt.txt` /
  `codex-statecode-install-sites-neutral.txt`. Both under
  `docs/research/feel-captures/register-2026-09-12-statecode/`.
- No emulator run (STATIC HALF in effect this session and the correction
  pass); runtime corroboration cited above (codes 10/11/12) is from other
  tracker items' GDB sessions (`jus-state-code-enum-j39n`, `jus-jh7d`,
  `jus-kakashi-moveset-map-33lu`), not re-run here.
