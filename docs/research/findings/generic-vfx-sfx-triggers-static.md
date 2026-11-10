# Generic VFX/SFX trigger census — static read, no live capture

2026-09-12. Static disasm only, no emulator. Tracker item `jus-atns.2`. Full trigger
table, wrapper decode, and conditions block:
TRIGGERS.md. Codex second
opinion: codex_second_opinion_triggers.md.

## Headline

The generic sound-request wrapper is **arm9 `0x0207342C(category, id)`**: a
dedup-gated call — same-(category, id) requests already in flight are
dropped — with 316 static call sites (a floor; xref tooling misses at least
one comparable trampoline elsewhere in this game, per guard-sp.md). Of the
five requested trigger paths, four resolve to a concrete `(category, id)`
pair at a specific instruction; the fifth (KO) is unmeasured — two
independent KO-adjacent state-install handlers were checked and neither
directly calls the wrapper or the effect-spawn manager, but the transitive
path from what they do call was not traced.

| trigger | id (category) | confidence |
|---|---|---|
| Hit resolution (generic, all elements) | `0x28` (`0x7A`) | traced to instruction, unconditional on element/kind; gated on attacker flag bit 25 (`tst r0,#0x2000000; beq 0x0208247C` at `0x0208242C`) and a status-table test (`tst r1, r0 lsr #3; bne 0x0208247C` at `0x02082458`) |
| Guard hit / attack-vs-attack contact | `0x2A` (`0x7A`), two structurally identical sites | traced to instruction |
| Attack-vs-attack node teardown | `0x2B` (`0x7A`) | traced to instruction, event (create vs. free) unresolved |
| Dream-attack activation | `0xB` (`0x78`) | traced to instruction; caller of the dispatching function not found by static xref |
| SP/HP carry payout | `7` / `9` (`0x7A`) at the Fill/SP-apply flush site | traced to instruction; HP-vs-SP / full-bar-vs-any-gain distinction unresolved |
| KO | none found directly | unmeasured, not absent — checked both `0x0215C488` and `0x0215CA44`, neither directly reaches the wrapper; transitive path untraced |

Effect spawn: no separate spawn entry point beyond entities.md §5 (manager
`0x021729EC`, 27-kind dispatch `0x02172864`, element init `0x0216ACC8`). This
pass closes entities.md §5.2's open "sound-id banks at `+0x22`/`+0x24`" note
by reading the consumer at `0x0216AEAC-F0`: they are `category` operands for
`0x0207342C`, selected by which of three ranges the shot-element's param
byte `+0x1D` falls in (`< 0xC8`, `0xC8..0xDC`, `>= 0xDC`). That sound block
sits right after the same function's `0x02037c24`/`0x02037b98` list-unlink
calls and right before its `pop` — i.e. in the teardown tail, not at a shown
creation site — so whether "effect spawn" and this sound are one
instruction stream is open, the same create-vs-free question as the `0x2B`
node-teardown row above.

## What a live run must add

Static disassembly gives call sites and literal ids; it cannot show which of
these actually fire during real play, in what order, or with what
frame-accurate timing, and it can't resolve the three still-undecoded
callees inside `0x0207342C` (`0x0205DAAC`/`0x0205B910`/`0x0205B8C4` — one of
these is presumably the actual Nitro SDAT play call, not yet identified by
name). Emulator mute is irrelevant to any of this — log the call, not the
audio output. Concretely:

1. **Break at `0x0207342C` itself**, logging `(category, id, framecount)` on
   every call that gets past the dedup check (i.e., instrument after the
   `popeq` at `0x02073458` so dedup-skipped requests are distinguishable from
   ones that actually reached the play helpers).
2. Drive each of the five owner-scope triggers and confirm the ids predicted
   above actually appear:
   - **A blunt-ish hit and a sharp-ish hit** (pick two moves whose `elem+0x14`
     nibble differs) — confirm both log `id=0x28` at `0x02082478`, which
     would confirm the static finding that this call is not element-keyed.
     If a live run shows different ids between the two, the static read
     above is wrong and needs revisiting — this is the single highest-value
     falsification target in this document.
   - **A guard block** and **a projectile/attack-vs-attack collision** —
     confirm `id=0x2A` at both `0x02080D0C` and `0x02080EF8`, and look for
     `id=0x2B` at `0x02081D4C` on the same contact.
   - **A dream-attack activation** (the `jus-jh7d` hotkey self-re-press
     method already used in physics.md/deck-editor.md) — confirm `id=0xB,
     category=0x78` fires at `0x02157864`, reached via the dispatcher's
     `code==11` branch. Also check whether `id=0x36` (the dispatcher's
     separate `code==2` branch) fires for the same transition — TRIGGERS.md
     §3 does not establish that the two branches are mutually exclusive, so
     this is an open question, not a confirmation.
   - **An SP bar carry** (Kakashi 4-koma special per guard-sp.md's `jus-e2h3`
     measurement) — confirm `id=9` fires at `0x02158C0C`/`0x02158C2C`, and
     check whether it fires identically for a small SP tick vs. a full-bar
     carry (resolves the "full-bar vs. any gain" open question above).
   - **A KO** — confirm the negative result: does *anything* call
     `0x0207342C` or the effect manager during the KO transition, and if so,
     from where? If nothing fires, that's itself worth recording as a
     confirmed absence, not just an unexamined gap.
3. Log framecount alongside each call so the five events can be lined up
   against the state-code transitions (`obj+0x18`) physics.md already
   grades RUNTIME, to catch ordering (does the sound call precede or follow
   the state commit?) that static reading can't determine.

## Live confirmations, 2026-09-14b (P3 tail, `jus-atns.2`)

Full data: vfx-sfx-live-2026-09-14b/RESULTS.md.

- **Hit resolution (`0x28`)**: the bit-25 gate at `0x0208242C` is confirmed
  to be the one that closes, on the 16 landed Kakashi B/Y hits actually
  observed passing through it against an idle-CPU Jotaro (**corrected**:
  not 17/17 — `gate1` fired 17 times total at raw frames `39, 40, 41, 101,
  104, 213, 214, 381, 384, 441, 444, 551, 554, 610, 610, 611, 719`, which
  is a cancellation, not a 1:1 match: the `610`/`610`/`611` cluster is
  three fires against two landed hits, and the `jhp` drop at raw frame 702
  falls inside an unlogged inter-burst gap with no `gate1` row near it at
  all) — bit 25 of the attacker flag word is never set on any of the 16
  observed, so the second gate (`0x02082458`) is never reached and `0x28`
  never fires. This is a live-confirmed "unreachable on this attack class"
  result for the 16 hits actually observed at the gate, not a 17/17 claim.
  Untested on specials/dream attacks/status-inflicting hits.
- **Dream-attack activation (`0xB`, category `0x78`)**: not reached on this
  activation; cause now separated (Part B fix pass, 2026-09-14). A Yusuke
  dream attack that demonstrably lands (state 11 confirmed entered at raw
  frame 90 in the Part B rerun, hit timing and damage delta match
  `jus-atns.1` exactly) never fires `(0x78, 0xB)`, and never fires `0x36`
  either. It fires the same generic attack-start pair an ordinary jab uses
  instead (`0xE`/`0x20`, at raw frame 101, one frame before the `jhp` drop
  at raw frame 103). The dispatcher's jump table at `0x021574E8` index 11
  resolves to `0x02157840`, whose body (`ldr r0,[r4,#0x1ac]; cmp r0,#0; beq
  …; mov r0,#0x78; mov r1,#0xb; bl 0x207342c` at `0x02157864`) confirms
  this document's static read of the `0xB` site itself was correct. Part B
  broke on the dispatcher itself (`0x021574CC`) and found the two testable
  causes separated: it fires continuously through the capture (733 fires,
  `r2_code` histogram `{12: 488, 8: 244, 4: 1}`) but **never with
  `r2=11`**, and `[r4+0x1ac]` reads `0` in 732 of those 733 fires (the one
  exception, at raw frame 88, reads `0x1a00009b` — nonzero — but on
  `r2_code=4`, not `11`). Cause (a) is confirmed (never invoked with the
  code that would reach the call); cause (b) is ruled out (the call that
  would test `[r4+0x1ac]` under `r2=11` never happens at all, so its null
  status is moot).
- **SP/HP carry payout (`7`/`9`)**: confirmed negative at the SP-apply and
  payout sites specifically, gating cause unmeasured (Part B fix pass,
  2026-09-14). Two live attempts — an ordinary switch and a switch after
  landing several hits with the outgoing koma — produced zero fires at
  `sp_apply_bc0`/`sp_apply_bcc` (`0x02158BC0`/`0x02158BCC`) and all three
  payout call sites. No breakpoint sat at the routine's own entry gate
  (`0x02158BA0`) or its containing function's head, so whether that gate
  never opens or the routine itself is never called on an ordinary switch
  is unmeasured, not settled. A per-frame pool read (new this pass) found
  the raw pool word jump `0 -> 25597` and the bar-count pair go
  `0x0707 -> 0x0607` exactly at the switch commit, then decay `-3`/frame
  for the rest of both captures (130 and 131 frames respectively) — this
  is a same-total decomposition of one SP bar into the fractional pool,
  arithmetic-confirmed against the combat notes §1.4's bar unit (`0x6400` =
  25600), not a gain or loss; see the combat notes §8. The writer that performs
  the decomposition is not this routine and is otherwise unidentified.
- **KO**: measured for the first time. Three ids not seen in any prior
  capture — `(0x7A, 0x55)`, `(0x7A, 0x1)`, `(0x7A, 0x37)` — fire around the
  killing blow (one frame before/after `jhp` reads 0), from three
  previously-undocumented call sites. Of the three static state-24 install
  sites, `0x0215C690` is entered exactly once, one frame before the
  transition (KO−1), matching an install's shape; `0x0215C704` is also
  entered on that same frame but then recurs every frame state 24
  persists (a per-frame recheck, not an install); `0x0215C488` never
  fires. Only prologue breakpoints were used at all three sites, so this
  is the strongest claim the data supports, not a confirmed call graph —
  a positive-identification probe (breaking the shared setter `0x02157494`
  with `r1==0x18`) is still open. `state25_install` (`0x0215CA44`) fires
  once, 81 frames after KO, sharing a frame with a `0x36` fire from an
  unrelated call site (different `lr`) — evidence against, but not proof
  against, a transitive call from the handler into the wrapper.
