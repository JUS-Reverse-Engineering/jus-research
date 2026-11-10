# SP initial state (m/c/x) and the `0x0215FD00` bonus table — static

Grade: **CONFIRMED_STATIC** for the init-site addresses and control flow;
**PLAUSIBLE** for what the ability-id classification values mean;
**[unverified]** for the reachability of the `0x0207871C` reset function.
Tracker item `jus-f86l`. Static-only (no emulator, no GDB). Evidence:
sp-init-2026-09-12/RESULTS.md,
Codex second opinion in the same directory.

**Correction pass (2026-09-12, same tracker item, after a Refuter FAILED the first
draft):** the `c`/`x` reset routine, the `m` counting rule, the bonus-table
gate, and the bonus-table selector were all wrong or overstated below and
have been corrected in place (marked "Corrected" at each site) rather than
re-drafted from scratch, so the reasoning that led to each mistake stays
visible next to its fix.

Fields, per `docs/confirmed-facts/guard-sp.md` §1.4: `slot = [char+0x1B4]`;
`m` = max bars (`slot+0x5CC`, s8); `c` = current bars (`slot+0x5CD`, s8);
`x` = fractional pool (`slot+0x5C8`, u32); `+0x5CE`/`+0x5CF` = free-pass
bytes.

## Conditions

Static reading of the prebuilt disassembly databases
(`scripts/analysis/query.py`, ARM, arm9 + ov6). No runtime measurement.
Falsification / what a live run must add: attach `JUS_WATCH` to
`slot+0x5C8..0x5CF` (8 bytes) from match/deck load through the first frame
of gameplay, and record every write's `pc`/`lr`. This settles (a) whether
`0x02077610`'s per-node weighting (classification, `+0x40`) actually maps
one-to-one with koma/deck-level nodes as the "Live consistency check"
below hypothesizes, (b) whether `0x0207871C` is ever reached at all — its
reachability is **[unverified]**, not "fires once at deck load or
repeatedly per round" as the first draft claimed (see the corrected `c`/`x`
section) — and (c) whether any ability id's classification entry actually
carries byte 0 `== 1` and byte 1 `== 5` on a real deck (this pass never
resolved `[0x0214BD80]`, so the live population of that dispatch is
unconfirmed).

## The init-site table

| field | pc | value | function | reachable from |
|---|---|---|---|---|
| `m` (`+0x5CC`) | `0x02077618` | `0` (entry zero) | `0x02077610` | 6 static callers, `0x02076B64` etc. |
| `m` (`+0x5CC`) | `0x020776CC`, `0x020776F0` | clamp to `0x10` (16) when an ability-walk accumulator at the same offset exceeds 16 | `0x02077610` | ditto |
| `c` (`+0x5CD`) | `0x02076BA0` | `0x10` (16) | `0x020769CC` | 15 static callers across several overlays; one traced example is a construction-shaped routine, ov0 `0x02155CB4` |
| `c` (`+0x5CD`) | `0x02076BB0` | `m` if `c > m` (clamp) | `0x020769CC` | same |
| `c` (`+0x5CD`) | `0x0207878C` | `0` | `0x0207871C` — a distinct leaf function (no prologue; `bxeq lr` at `0x02078724`, `bx lr` at `0x02078798`), *not* the tail of `0x02078660` (which pops and returns at `0x02078718`) | **reachability [unverified]** — see note below |
| `x` (`+0x5C8`) | `0x02078790` | `0` | same function, `0x0207871C` (also zeroes `+0x578` at `0x02078794`) | same, **[unverified]** |
| `+0x5CE` | `0x02159180` | `0` | `0x0215911C` | 6 ov6 callers |
| `+0x5CE` | `0x0215936C` | `1` | function starts `0x02159364` (dereferences `+0x1B4` first: `ldr r0,[r0,#0x1b4]`), not `0x0215936C` | **0 static callers found — a `functions.json` gap (no entry for `0x02159364` at all), not proof of unreachability; [unverified]** |
| `+0x5CF` | `0x02157298` | `1` iff `char+0x12C & 0x20` | `0x02157114` | 2 ov6 callers |

## Is `m` (max bars) constant? — corrected: it's a weighted count, not a plain tally

**No, and the counting rule is more specific than "count non-class-3
nodes."** `0x02077610` walks the linked list at `[r0+0x558]` (`node+0x00` =
next pointer). Per node:

- Classification is `[[node+0x34]+0xb] & 0xf` (`0x0207769C ldr sb,
  [r8, #0x34]`; `0x020776A0 ldrb sb, [sb, #0xb]`; `0x020776A4 and sb, sb,
  #0xf`) — one extra indirection through `node+0x34`, not a direct read of
  `node+0xb`.
- A node **qualifies** only if that classification `!= 3` **and**
  `node+0x40 != 2` (`0x020776A8`-`0x020776B4`: `cmp sb,#3`; if not 3,
  `ldrbne fp,[r8,#0x40]; cmpne fp,#2; beq skip`).
- A qualifying node increments the `+0x5CC` accumulator **once**, always
  (`0x020776B8`-`0x020776C0`, clamped to 16 right after), **and increments
  it again** if `node+0x40 == 0` (`0x020776D0`-`0x020776E4`: `ldrb
  fp,[r8,#0x40]; cmp fp,#0; bne skip-second`; second increment clamped the
  same way).

So **`m = 2 · (qualifying nodes with `node+0x40 == 0`) + 1 · (qualifying
nodes with `node+0x40 == 1`)`, clamped to 16** — not a flat per-node count.
(Only 0 and 1 are distinguished by the second-increment test; `2` is
already excluded by the qualify gate, so those are the only two weights a
qualifying node can carry.) This is still a **deck/ability-composition
count**, not a rule-setting lookup and not a fixed constant: different
decks with different qualifying `+0x558` nodes produce different `m`. What
"qualifying" and `node+0x40`'s values mean at the ability-name level is not
resolved by this pass — the classification field's mapping to a named
ability id was out of scope here (see `docs/confirmed-facts/guard-sp.md`
§1.3 for the walker's general shape, `0x020783DC`, which is a *different*
walker over the same list).

**Live consistency check.** Two independently-observed live `m` values fit
this `2n+1` shape for `n` koma (character pieces) plus one deck-level node:
`m = 7` on the 3-member dream-attack deck
(dream-attack-2026-09-12/RESULTS.md
~line 110, `n=3`: `2*3+1=7`) and `m = 9` on the Kakashi state
(`docs/confirmed-facts/guard-sp.md` ~line 522, `n=4`: `2*4+1=9`). The
hypothesis this suggests — one `node+0x40 == 1` node per deck (weight 1)
plus one `node+0x40 == 0` node per koma (weight 2 each) — is **not proven
by statics alone**; a live run that logs each qualifying node's
`(classification, +0x40)` pair against the known koma count would confirm
or refute it directly. These same two values also refute the "`m` is a
fixed constant" alternative in falsification test 4 below: two different
decks produced two different `m` (7 and 9), which a fixed constant cannot
do.

## Object-layout: gap 5 resolves toward one shared object; `+0x558` is a slot field

`0x02077610` reads and writes both `+0x558` and `+0x5CC` on the same
register `r0`, and never dereferences `char+0x1B4`. Rather than leaving
this as an unresolved tension against guard-sp.md §2 gap 5 ("base-object
ambiguity"), the surrounding caller `0x020769CC` settles which way it
resolves: its callee `0x02076C18` `memset`s `r0+8` for `0x5E0` bytes
(`0x02076C24`-`0x02076C2C`, `bl 0x20517fc`) and then writes `+0x5D7`
(`0x02076C6C`, a 3-entry loop) on that *same* freshly-zeroed object — this
is a construction/reset of the player slot itself, not the character. The
very same register `sl` that `0x020769CC` later passes as `r0` into
`0x02077610` (`0x02076B60`-`0x02076B64`, `mov r0,sl; bl 0x2077610`) is also
used to read `[sl+0x558]` at `0x02076B24` and to write `[sl+0x5cd]` at
`0x02076BA0` — i.e. `+0x558`, `+0x5CC`(via `0x02077610`), and `+0x5CD` are
all read/written through the one `sl` register in this function, with no
separate `char`/`slot` dereference between them. `slot+0x5CD` is also
runtime-confirmed at `0x021DF731` (guard-sp.md, Kakashi live trace). Taken
together, this resolves gap 5 toward **`+0x558` also being a slot field**,
not evidence of `char`/`slot` conflation — the free-pass writers
(`+0x5CE`/`+0x5CF`) are the ones that actually dereference `+0x1B4` first
(`0x02157290` inside `0x02157114`; `0x02159364`, see the corrected function
start below), consistent with `char` and `slot` being distinct objects
elsewhere in the same file, just not at this call site.

## `c` and `x`: full-then-clamp at construction, zero on reset, never on `m`

`0x020769CC` sets `c = 16` unconditionally right after its own call into
`0x02077610`, then clamps `c` down to `m` if `m < 16` — net `c = min(16,
m)`. Separately, a reset function (`0x0207871C`-`0x02078798`, guarded on
`[r0+0x558] != 0`) zeroes `c`, `x`, and `+0x578` together but never touches
`m`. **Correction**: `0x0207871C` is its own leaf function (no prologue,
`bxeq lr` at `0x02078724`, `bx lr` at `0x02078798`), not the tail of the
function at `0x02078660`. That earlier reading came from `functions.json`,
which merges `0x02078660`, `0x0207871C`, and `0x0207879C` into one reported
function (`addr 0x02078660`, `size 436` / `0x1B4`, spanning through
`0x02078814`) — a tooling artefact, not a real shared-function boundary;
see the "functions.json hazard" note below. The 6 ov6 `bl` sites previously
cited as this reset's callers (`0x02157D44`, `0x0215AC4C`, `0x0215CAA8`,
`0x0215CAF0`, `0x0215CCE8`, `0x0215CE40`) all target `0x02078660`, which
pops and returns at `0x02078718` — they never reach `0x0207871C` or
`0x02078790`. No static call, branch, or literal-pool word (`1c870702` /
`0x0207871C`) targeting `0x0207871C` was found anywhere in arm9 or ov0-ov13.
**`0x0207871C`'s reachability is therefore [unverified]** — the "per-round
or state-re-entry reset" inference in the previous draft is withdrawn; it
was built on the false premise that the 6 known callers reached this code.
**No static site sets `x` (`+0x5C8`) to any nonzero value outside the apply
routine `0x020781E4`** — its nonzero content only ever comes from runtime
gains (guard-sp.md §1.4), never from a fixed init constant.

**functions.json hazard**: this is now the second function-boundary error
this campaign has hit from `functions.json` merging adjacent leaf functions
into one reported span (see also the `0x0215936C`/`0x02159364` correction
below). Treat its `size`/`callers` fields as unreliable near any address
that ends in an early `bx`/`pop`-and-return with no preceding `push` at the
next label.

## The `0x0215FD00` bonus table: idx is the selector, and the feeding path is reachable

`docs/research/findings/char-0x130-is-a-gated-handler-table.md` established
the 16-entry table at ov6 `0x0217221C`, `table[5] = 0x0215FD00`, gated by
`view+0xC` bit 5 (`view = char+0x130`). This pass confirms:

- The gate `0x0215FC78` preserves `r1` unmodified into the `blx`, so the
  handler's own index argument always equals the selector that picked it.
- **Corrected — the handler is gated, not run "on every call."**
  `0x0215FC78` is `ldr r3,[r0,#0xc]; tst r3, r2 lsl r1; popeq {r3,pc}` —
  `table[5] = 0x0215FD00` only runs if bit 5 of `view+0xC` is already set;
  otherwise `popeq` returns without ever reaching the `blx`. And
  `0x0215FAC4` — the same function that unconditionally calls the gate
  with literal selector 5 at `0x0215FB28`-`0x0215FB2C` — **clears the mask
  first**, at its own entry (`0x0215FAD4 bl 0x0215FB88` → `0x0215FB8C mov
  r3,#0` → `0x0215FC08 str r3,[r0,#0xc]`, `r3 = 0`). So `0x0215FD00`'s
  read of `view+0x16+2*5 = view+0x20` and its adds into `view+0x5A`,
  `+0x5C`, `+0x56`, `+0x58` (all four confirmed by full disassembly
  through `0x0215FD44`) run **iff bit 5 got re-armed earlier in the same
  invocation of `0x0215FAC4`** — i.e. iff `0x0215FC20` armed bit 5 during
  that invocation's per-record loop (see below). Not unconditional.
- **`view+0x16`'s array is populated, not dead.** A prior finding
  (`view-slot-arm-and-the-unreachable-setter.md`) found the array-fill
  function `0x0215FC20` had 0 direct static xrefs and could not prove it
  reachable. This pass resolves it: `0x0215FAC4` loops over **a byte list
  at `r6+0xb`** (`count = ldrsb[r6+0xa]`, id `= ldrsb[r6+i+0xb]` at
  `0x0215FAF4`/`0x0215FAFC` — not a "character/ability record array"; the
  loop's own stride is 1 byte, and nothing here establishes these ids as
  ability *records*, only as a byte-per-entry id list). For each id, looks
  up a 4-byte classification entry at `[[0x0214BD80]+0x50] + id*4`, reads
  its **byte 0** to select a dispatch table entry (`0x0215FB08`, `ldrb
  r2,[r3,r1,lsl#2]`), then indexes a **fixed, ROM-resolvable** 3-entry
  table at ov6 `0x02172210` (`{0x0215FB3C, 0x0215FB64, 0x0215FB78}`) with
  that raw byte — **`0x0215FB10`'s `ldr r2,[sb,r2,lsl#2]` has no range
  check on `r2`**, so any classification byte outside `0..2` reads past the
  3-entry table. Entry 1, `0x0215FB64`, is a trampoline that reads **byte 1
  of the same classification entry** (`0x0215FB68 ldrb r1,[r1,#1]`, where
  `r1` is the entry pointer `r3 + id*4` computed at `0x0215FB0C add
  r1,r3,r1,lsl#2` — *not* the id itself) and hands that byte to
  `0x0215FC20` as the arm target `N`. **Corrected**: `0x0215FC20` arms bit
  `N`/table-slot `N` where `N` = **byte 1 of the classification entry**, not
  the id/record field itself. So the ability id that feeds bonus-table slot
  5 is **whichever id's classification entry has byte 0 == 1 (selecting the
  trampoline into `0x0215FC20`) and byte 1 == 5 (the value that gets
  armed)** — not "whichever record has `+0xb == 5`."

**What is still open**: `[0x0214BD80]` itself is a further indirection not
identified this pass (it is not the `r6+0xb` id list, nor the
`[0x02172984]+0xC` config table already documented in guard-sp.md §1.4 for
the payout deposits). Which named ability(ies) actually have an id whose
classification entry carries byte 0 == 1 and byte 1 == 5 is not settled
statically here — that requires either resolving
`[0x0214BD80]+0x50`'s contents byte-by-byte or a live trace.

## Codex second opinion — what changed

Full transcript in
sp-init-2026-09-12/codex_second_opinion_sp_init.md.
Codex flagged two things that changed this write-up from its first draft:

1. The `0x02077610` object-layout tension (§ above) — added as a caveat
   against guard-sp.md's existing gap 5, not resolved.
2. **Pushed back on a "dead code" claim.** The draft asserted `0x0215FC20`
   was unreachable (0 direct xrefs). Codex noted an unexamined indirect
   `blx r2` nearby and called the dead-code claim under-supported. Chasing
   that down (after the Codex pass) found the `0x02172210` dispatch table
   and confirmed `0x0215FC20` *is* reachable through it — Codex's
   skepticism held up; the original claim in this finding's draft was
   wrong and has been corrected in the text above, not silently dropped.

## Falsification tests (for the live pass)

1. `JUS_WATCH` on `slot+0x5C8..0x5CF` from deck/match load through the
   first frame of gameplay — expect the first writes to be `m` (via
   `0x02077610`) then `c = 16` then `c` clamped to `m` (via `0x020769CC`),
   all before any `0x0215FC20`/`0x0215FD00` activity.
2. Break at `0x02077610`'s entry and read `r0` against the known character
   pointer and `[character+0x1B4]` — settles the object-layout question in
   one stop.
3. Break at `0x0215FB08`/`0x0215FB68` across a full deck of abilities and
   record every `(id, classification-entry byte0, byte1)` triple — settles
   which id(s), if any, actually carry byte0 `== 1` and byte1 `== 5` on a
   real roster (corrected target: byte1 of the classification entry, not
   the id's own `+0xb` field — see above).
4. Vary deck composition (character/koma count, ability loadout) across
   multiple runs and diff the resulting `m` — **already partially done**:
   two live values on hand (`m=7` on a 3-koma deck, `m=9` on a 4-koma
   state, see "Live consistency check" above) already refute a
   fixed-constant `m` and are consistent with the `2n+1` weighted-count
   hypothesis. A live run that also logs each qualifying node's
   `(classification, +0x40)` pair would confirm the weighting itself, not
   just that `m` varies.
