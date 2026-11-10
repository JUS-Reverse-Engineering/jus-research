# SP apply routine `0x020781E4` keeps a mixed-radix resource: pool `slot+0x5C8` in 1/256 units, bar count `slot+0x5CD`, max bars `slot+0x5CC`, one bar = `0x6400`

Tracker items: `jus-e2h3`, `jus-pb6n`, `jus-36wu`, `jus-1bkw`.

Grade: PLAUSIBLE. Partial live confirmation 2026-09-12 (`jus-e2h3`): the
gain path (`0x020781E4` into `x`) and the bar-borrow path (`c` against `m`,
via a previously uncatalogued wrapper) are both confirmed for one caller
(Kakashi's 4-koma X special); see Live confirmation below. Auto-Guard and
the ability-55/56 per-frame rate remain unconfirmed live.

## Claim

`0x020781E4(slot, amount)`:

- `amount < 0`: refused (early return) if `s8[slot+0x5CF] != 0`. Else
  `x += amount`; while `x < 0`: `0x0207830C` tries `c -= 1` (refuses below 0);
  on success `x += 0x6400`, on failure `x = 0`.
- `amount >= 0`: `x += amount`; while `x >= 0x6400`: `0x02078328` tries
  `c += 1` bounded by `m`; on success `x -= 0x6400`, on failure `x = 0`.
- Tail `0x02078290-A4`: if `c >= m` then `x = 0`.

with `x = u32[slot+0x5C8]`, `c = s8[slot+0x5CD]`, `m = s8[slot+0x5CC]`.
Invariant on the gain path: `0 <= x < 0x6400`, `0 <= c <= m`, `c == m`
implies `x == 0`.

`0x020782AC(slot, amount)` is the read-only affordability check: same
arithmetic on a local copy, returns 1 if affordable, stores nothing, ignores
`+0x5CF` and `m`. The documented "refused silently below 0x100" behaviour
plausibly comes from this check being called before the apply.

Unit reading (codex, consistent with all constants): 8-bit fraction,
`0x100 = 1.00`, `0x6400 = 100.00 = one bar`, `0x3200 = 50.00`. **Correction
(2026-09-12, `jus-e2h3`, live):** the "observed in-play pool value `0x0909`"
was a misread — it is `m=9, c=9` packed into one little-endian 32-bit read
of `slot+0x5CC..0x5CF`, not a fractional-pool reading of the `x` word at
`slot+0x5C8`. See the Live confirmation section below.

## Callers (static)

- 16 `bl 0x020781E4` sites (arm9 `0x02077E3C`; ov6 `0x02157978`,
  `0x02157DD0`, `0x021582D4`, `0x02158370`, `0x021586A4`, `0x02158BCC`,
  `0x02159294`, `0x021592EC`, `0x0215A334`, `0x0215AC64`, `0x0215EA40`,
  `0x0215ECB8`, `0x0215FE9C`, `0x0215FED0`, `0x0215FF98`, `0x0215FFB8`); one
  `bl 0x020782AC` at ov6 `0x0215EAA0`.
- `0x0215EA40`: inside the guard router, gated on ability bitset bit `0x10`
  (Auto-Guard); sets `obj+0x11A = 12` then applies `amount = -0x3200` (half a
  bar) and plays the block sound; when the probe branch is false it calls the
  affordability check with `-0x3200` and only sets `M+0x44 |= 4` if
  affordable. Candidate Auto-Guard cost: 50.00, static only.
- `0x02077E3C`: inside per-frame routine `0x02077D40` (the HP regen tick,
  damage.md §8), reached only when `koma+0x3C` bits `0x4000`/`0x2000` are
  clear and a vtable predicate passes; applies `s8[koma+0x4B] + s8[koma+0x4C]`
  (the bytes written by kind-2 abilities 55 "SP regen" and 56 "SP drain",
  helpers.md). This is the first located consumer of those two abilities. If
  it runs at 60 Hz with net +3/frame, one bar takes 8533 frames (142 s);
  the rate is unmeasured.
- `0x0215A334`: on-hit flush, gated on `[[obj+0x1A8]+0x10]+0x144` nonzero,
  sibling of the HP-fill flush at `0x0215A318` (`+0x140`). Writer of `+0x144`
  untraced.
- `0x0215FE9C`: plain `bl` site in the view-handler cluster, not
  independently characterized live this session.
- `0x0215FED0` (`lr=0x0215FED4` at the return): **not** the ability-56
  carrier tick (retracted 2026-09-12, `jus-e2h3`, live re-run below).
  `amount = u16[obj+0x36+2*idx]`, read after a 288-count warmup on
  `obj+0x10` that never resets; this is an *unsigned* 16-bit read, so it
  cannot carry ability 56's signed `-3` value. Fires once per
  collision-driver entry (`0x0207F480`, "`FRAME#`"), not once per
  emulator frame.
- `0x0215FF98` (`lr=0x0215FF9C` at the return): same shape as
  `0x0215FED0` above — constant `+10`, gated on a counter at `obj+0x14`
  compared against `720`. Also not independently tied to any named
  ability this session.
- Ability 53 handler `0x020779A4` does `+0x5CC += 1` clamp `0x10` ("Max SP
  gauge +1"): same offset as `m`; base-object identity not independently
  proven.

## Conditions

Static: `jus_files/analysis/disasm/{arm9,ov6}.txt` via
`scripts/analysis/query.py` (disasm quoted in
`docs/research/feel-captures/sp-static-2026-09-12/codex_prompt_sp_apply.txt`).
Second opinion, neutral prompt: codex_second_opinion_sp_apply.md
(gpt-5.6-sol), agrees on every point above; notes instructions
`0x020782FC-0x02078308` were not in the prompt and B's helper is inferred to
test `c >= 1`.

## Live confirmation (2026-09-12)

Tracker item `jus-e2h3`, state `pc-kakashi-npc-jotaro-dark-tournament`. Fork commit
`c26edf0e0d75364823856c9272a103fe39e03999`, full trace in
../feel-captures/sp-live-2026-09-12/pc-kakashi-npc-jotaro-dark-tournament/RESULTS.md.
A first pass at this live test (commit `c1418c6`) FAILED Refuter review by
introducing a spurious `+4` player-slot offset and misreading the debit as
a byte decrement; this section reflects the corrected re-measurement, not
that first pass.

- **`c` decrement measured**: the Kakashi 4-koma X special's cost dropped
  `c` from `9` to `8` at `slot+0x5CD = 0x021DF731` (`slot = 0x021DF164`,
  no offset). The discriminating poke test (`c=0` refused, `c=1` accepted
  and decremented to `0`) reproduced the same write.
- **Gains measured into `x`**: `0x020781E4` fired repeatedly during the
  special's active frames on both player slots, with halving per-hit
  amounts (`3840, 1920, 960, 480` on the acting P1 slot; `2560, 1280, 640,
  320` on P2), landing in the fractional pool `x` at `slot+0x5C8 =
  0x021DF72C`.
- **Tail clamp measured**: the tail zeroes `x` on any add where `c >= m`
  at that moment; observed directly on the P2 slot (already full — every
  hit's post-add value equals just that hit's amount, no accumulation) and,
  after the poke set `m = -1`, on the P1 slot too. Where `c < m` (P1, before
  the poke), `x` accumulated across hits (`0xF00 -> 0x1680 -> 0x1A40 ->
  0x1C20`).
- **Wrapper `0x0207834C` is the spend-bars entry**, not `0x02078350` (that
  address is the wrapper's *second* instruction). It checks the free-pass
  bytes `slot+0x5CE`/`slot+0x5CF`: **either** nonzero skips the charge and
  returns 1 (a free-pass mode), not "both must be zero." Otherwise it calls
  `0x0207830C` (H1) with `r0 = slot` unmodified and `r1 = 1`, which is the
  measured `c` decrement above. Static callers of `0x0207834C`:
  `0x02078138` (inside `0x02078110`), ov6 `0x02159DD8`, `0x0215A524`,
  `0x0215A5D0` — not independently exercised live beyond the one hit
  measured here.

## Live confirmation (re-run)

Tracker item `jus-e2h3`, session `sp-live-2026-09-12b` (a second, independent
builder's re-run over six states, with the same corrected field map,
summarized in
../feel-captures/sp-live-2026-09-12b/SUMMARY.md).
This section extends, and in three places corrects, the live confirmation
above.

- **Gains are deposit-and-payout, not per-hit.** `0x0215FFA0` (ov6) is a
  payout-and-decay routine on a pending `u16` cell: it pays `u16[cell]`
  into `x` via `0x020781E4` (`bl` at `0x0215FFB8`, `lr=0x0215FFBC`), then
  halves the cell (`asr #1`), zeroing it once it drops below `0x100`. One
  deposit `D` therefore pays `D, D/2, D/4, ...` across successive ticks,
  for a total just under `2D` — not `D` once per hit. The pending cells
  sit at `obj+0x64`/`+0x6A`/`+0x6C`, reached through thunks
  `0x0215FF64`/`0x0215FED8`/`0x0215FF3C`. Two deposits were measured: `3840`
  (`15.00`) attacker, `2560` (`10.00`) victim, for Kenshin's B jab (336 raw
  damage, `pc-kenshin-luffy-guard`) and for the Kakashi 4-koma X special in
  a different state with no damage figure recorded — so "not
  damage-scaled" rests on the two moves differing in damage, not on a
  shared measured damage value — payout totals `3840+1920+960+480 = 7200`
  (`28.125`) and `2560+1280+640+320 = 4800` (`18.75`) respectively, before
  any tail clamp cuts a total short. A `5120` (`20.00`) deposit was also
  measured on P2 in `pc-naruto-fy-npc-yusuke-fy`'s projectile state. A
  third deposit amount, `1024` (`4.00`), was seen once on both slots in
  `pc-kenshin-luffy-guard`'s guard run, unattributed.
- **Spend-and-earn loop example.** `pc-naruto-fy-npc-yusuke-fy` recorded
  19x `amount=5120` deposits on P2 and 19x `amount=2560` on P1, each with
  a full decay chain, interleaved with 5 bar spends (`WRAPPER` entry
  `lr=0x2159ddc`/`lr=0x215a528` -> `H1(borrow)`, `c: 3->2`) and 5 bar
  gains (`H2(carry)` entry `lr=0x2078270`, `c: 2->3`) — e.g. `x=0x5DCC`
  plus a `5120` deposit carries the bar (`c: 2->3`), leaving `x=0xDCC`,
  which the tail then clamps to `0` on the next add once `c>=m` again.
  This is the first live example of the full spend-then-earn cycle in one
  run.
- **The 16-site caller census missed at least one Thumb `BLX` site.**
  `0x02150DEA` (ov6) is a Thumb `BLX` to `0x020781E4`, `lr=0x02150DEF`,
  paying a constant `2<<8 = 512` (`2.00`) in `pc-naruto-fy-npc-yusuke-fy`'s
  projectile state. The earlier static census searched for ARM `bl`
  instructions only, so this Thumb call was never enumerated;
  `lsls r1,r1,#8` immediately before the call is the instruction-level
  evidence for the `1/256` unit.
- **Three distinct per-collision-entry-driven ticks, and what's confirmed
  about each:**
  - `0x0215FED0` (`lr=0x0215FED4`): live-measured at `+20` per
    collision-driver entry (2774 `APPLY` events over 601 emulator frames
    in `pc-taikoubou-npc-jotaro-dark-tournament`, 601-frame idle window,
    Momotaro benched as an ability-56 carrier). **Confirmed**: the amount,
    the unsigned 16-bit source (`u16[obj+0x36+2*idx]`), the 288-count
    warmup on `obj+0x10`. **Not confirmed**: any link to ability 56 --
    the amount is unsigned and cannot carry ability 56's signed `-3`, and
    no control run isolated the benched carrier from other deck
    differences.
  - `0x0215FF98` (`lr=0x0215FF9C`): live-measured at `+10`, gated on a
    counter at `obj+0x14` vs `720`, firing once per `FRAME#` marker in
    `pc-naruto-fy-npc-yusuke-fy` (4000 times over 300 emulator frames).
    **Confirmed**: amount and gating counter. **Not confirmed**: what
    consumes or resets the counter, or any ability tie.
  - `0x0215AC64` (`lr=0x0215AC68`): the negative/spend path, `amount =
    -(u32[[obj+0x1A8]+0x10]+0x138)` -- a pending debit. **Confirmed**:
    the read location and that it fired 13/3/33/0/0/0 times across the
    six runs. **Not confirmed**: any nonzero debit was ever observed, so
    this is not shown live to be an idle no-op vs. an unexercised spend
    path -- both readings are consistent with the zero data collected.
- **`FRAME#` is not a per-emulator-frame basis.** The marker at
  `0x0207F480` fires once per collision-driver entry, observed at 2.2 to
  4.6 per emulator frame depending on object count across this session's
  six runs (e.g. `pc-taikoubou-npc-jotaro-dark-tournament`: 2773 markers /
  601 frames = 4.6/frame). Any per-frame rate claim in this campaign must
  use the bridge `emu.framecount()` delta, not a `FRAME#` count.
- **Ability 55/56 path still unmeasured live.** The true consumer, arm9
  `0x02077E3C` inside `0x02077D40` (`s8[koma+0x4B] + s8[koma+0x4C]`),
  fired in **no run** across all six states this session, including the
  one run with a benched ability-56 carrier in the deck (Momotaro). Its
  rate and its relationship (if any) to the `0x0215FED0`/`0x0215FF98`
  ticks above remain open.

## Live test (next)

State with `x = 0x00FF`, `c = 0`, `+0x5CF = 0`: the `-0x100` special must be
refused; set `c = 1`: accepted, leaving `x = 0x63FF`, `c = 0`; the visible
gauge should drop by one bar and show the remainder. Then `JUS_WATCH` on
`slot+0x5C8..0x5CD` across an Auto-Guard trigger (expect `-0x3200`) and
across on-field frames for a koma carrying ability 55 or 56 (expect the
per-frame delta and its Hz).

## Deposit writer (2026-09-12, `jus-36wu`)

Grade: mechanism CONFIRMED (`jus-36wu`) live for the four observed cells
(`+0x66`/`+0x68`/`+0x6A`/`+0x6C`); the `+0x64` gated path and the Fragment
A snapshot trigger remain PLAUSIBLE/open. There are **five** pending cells
(`+0x64/+0x66/+0x68/+0x6A/+0x6C`) and **four** writers, not three — see
the fourth-writer correction immediately below.
Cites `docs/research/feel-captures/sp-deposit-2026-09-12/`.

**Refuter-pass correction (`jus-36wu`): a fourth writer exists,
`0x0215FCB8`.** It was missed by this session's original GDB probe
(`scripts/gdb/deposit_writer_36wu.gdb`, which only bracketed
`0x0215FCCC`/`0x0215FCD8`/`0x0215FCE4`) and is visible only in the raw
`JUS_WATCH` logs, which the original write-up wrongly treated as noise:

```
0x0215FCB8: ldrh r1,[r0,#0x5a]; strh r1,[r0,#0x66]
            ldrh r1,[r0,#0x5c]; strh r1,[r0,#0x68]; bx lr
```

It is the only `strh` to `+0x66`/`+0x68` in ov6, and it is called at
`0x0215A074` (`lr 0x0215A078`) inside `0x02159EF8` — two instructions
before the `0x0215A080` call the original probe already bracketed. Live
in the Kakashi run's `watch.log.gz`:

```
w16 addr=02229016 val=00000F00 pc=0215FCC4 lr=0215A078   # char+0x130+0x66 = 3840
w16 addr=02229018 val=00000400 pc=0215FCCC lr=0215A078   # char+0x130+0x68 = 1024
```

(also twice in the Kenshin guard run — see that RESULTS.md). This
**retracts "the attacker's `3840` deposit was not observed at these
writer PCs" everywhere it was previously written** — it was observed, at
a writer this session's probe hadn't enumerated yet. Copies:
`+0x5A -> +0x66`, `+0x5C -> +0x68`.

**`1024` has two independent sources, not one**: `+0x5C -> +0x68`
(attacker, via `0x0215FCB8`) and `+0x60 -> +0x6C` (victim, via
`0x0215FCD8`). Both land on the same figure because `cfg+0x08` and
`cfg+0x0C` — the global config-record fields feeding `+0x60` and `+0x5C`
respectively — are both raw `4` in every deck measured.

**Guard run, corrected reading**: the guard-block-gain state
(`pc-kenshin-luffy-guard`) shows two attacker deposit events (`3840`,
then `1024`) and one victim event (`2560`, then `1024`) in
`watch.log.gz` for the single unguarded hit. The earlier Kakashi run's
payout sequence (`2560`/`3840` repeating x3, then `1024`/`1024`, at
`lr=0x215ffbc`) proves these are **fresh full deposits per press**: the
payout routine (`0x0215FFA0`/`0x0215FFCC`) halves its cell unconditionally
every tick, so seeing the same `3840` again on a later press requires a
re-deposit, not a continuing decay. This retracts the prior "in tension
with the payout-level reading" framing — the two readings agree once the
fourth writer is counted. What remains open: `record+0x40` bit `0x1000`
was never instrumented in either session, so "the two later presses were
guarded, and guarded presses deposit nothing" rests on an HP-flat
inference about which presses were guarded, not a direct flag read tied
to each press.

**Live update (same day, second pass):** `0x0215FCCC` (the `+0x6A` writer)
was confirmed firing live in two states
(`pc-kakashi-npc-jotaro-dark-tournament`, `pc-naruto-fy-npc-yusuke-fy`),
both times with `src_5E = 0xA00 = 2560` (`10.00`) — an exact match to the
`2560` deposit already measured by the prior `jus-e2h3` campaign, and
confirmation that `char+0x130` really is the writers' base pointer
(`state_block - 0x130 == char`, read from the live `r0` register, not
assumed). `+0x5E` fired on the *victim* slot in the Kakashi run and on the
*attacker* slot (P1) in the naruto-fy run with the same value both times —
weakening an attacker/victim framing in favor of `+0x5E` being a fixed,
hit-type-keyed constant. `0x0215FCD8` (`+0x6C`) did not fire in either
run; the attacker's `3840` deposit *was* observed, but at the fourth
writer `0x0215FCB8`, not at these three PCs — see the correction above
(this paragraph's original "not observed... in either run" claim for
`3840` is retracted). `0x0215FCE4` (`+0x64`) fired repeatedly in both
runs (corrected counts: 17 on the naruto-fy run's `0x0215FCCC`, 34 total
on `0x0215FCE4`, 31 on `0x0215AC64` — see that RESULTS.md's correction
note) but its gating bit was never set, so no `+0x64` write was observed
live this session either; the naruto-fy recount also found the `+0x64`
gating *mask* itself changing mid-run (`0` -> `0x6000` on 6 of 17 P1
hits), a new detail not previously noted.

**Live update: the ability 55/56 tick's existence and amount are now
CONFIRMED (`jus-36wu`); its firing rate is TBD, not "not unmeasured."**
`pc-momotaro-npc-nami-dark-tournament` (Momotaro, chr_b 67, ability-56
carrier, active on P1) fired `0x02077E3C` at roughly 0.7-1.1 times per
bridge-framecount frame (two brackets, an unexplained >60% spread — rate
TBD), every firing with `amount=-3`
(`koma+0x4B=0, koma+0x4C=-3`), and the resulting call into `0x020781E4`
visibly decremented the live SP pool word `slot_P1+0x5C8 = 0x021DF72C` by
exactly 3 raw units per firing (`0x5ED2 -> 0x5ECF -> 0x5ECC`, `lr=0x02077E40`
tying the store to this exact call site). This reverses the prior
session's "fired in no run" reading for this mechanism — see
`docs/research/feel-captures/sp-deposit-2026-09-12/pc-momotaro-npc-nami-dark-tournament/RESULTS.md`.
No ability-55 carrier state exists among the available savestates (already
established by the prior session, not re-checked here).

**Live update, guard block-gain (fourth state)**: run against
`pc-kenshin-luffy-guard` (a substitution for the named
`pc-kenshin-npc-luffy-dark-tournament`, whose CPU does not guard — see the
RESULTS.md for why). New attribution: `+0x60 -> +0x6C` (`0x0215FCD8`,
`lr=0x0215EB40`, the on-hit-resolution handler) deposited `1024` (`4.00`)
on the same hit that `+0x5E -> +0x6A` deposited `2560` — the first live
identification of the previously "unattributed" `1024` figure. The guard
flag (`M+0x78` bit 26) was read live at `0` then `1` across the run (a
real transition), but **no deposit-writer fired for either of the two
guarded `B` presses that followed** — only the first, unguarded hit
produced a `0x0215FCCC`/`0x0215FCD8` hit (and, per the fourth-writer
correction above, a `0x0215FCB8` hit too). **Retraction: this is not in
tension with** the prior `jus-e2h3` session's "deposit fires at the same
amount whether guarded or not" — see the guard-run correction above; the
two readings agree once the fourth writer is counted, and the payout
routine's unconditional per-tick halving explains why a fresh full
deposit is required for the same amount to reappear. `record+0x40` bit
`0x1000` was not instrumented, so which presses were actually guarded
still rests on an HP-flat inference, not a direct per-press flag read.
The write-watch on `M+0x78` (`0x220F50C`) itself turned out
to be unusable (aliased with an unrelated subsystem — dominant PCs
`0x0207ECC0`/`0x0207ED08`/`0x0207F8DC`, not `0x01FFA*` as first
misread — same trap as
`char+0x130`); only direct GDB-breakpoint reads of the flag are trustworthy
for this address. See
feel-captures/sp-deposit-2026-09-12/pc-kenshin-npc-luffy-dark-tournament/RESULTS.md.

Found by `search-imm` for `strh` stores at offsets `0x64`/`0x6a`/`0x6c` (ov6
only, filtering out other regions and other opcodes): the three routines
that write the pending payout cells sit in the same 0x0215FB88-0x0215FD00
block as the payout thunks already documented above, not somewhere in the
hit-resolution code proper. Second opinion: codex_second_opinion_deposit_writer.md
(gpt-5.6-sol, prompt: codex_prompt_deposit_writer.txt),
run with a neutral, no-context prompt. Codex's independent read matches
this section on every structural point below (state block with a snapshot
layer, a lazily-cached per-index layer gated by a bitmask, and a
copy-only "working field" layer); it could not and did not guess the
SP/deposit meaning, which is expected from a neutral prompt with no game
context.

- **Snapshot ("Fragment A"), `0x0215FB88`–`0x0215FC18`**: on some
  per-event trigger (caller not traced this session), copies five `u16`
  fields from a **global, shared config record** — reached as
  `[[literal_at_0x0215FC1C]]+0xc + {0,4,8,0xc,0x10}` (a pointer-to-pointer
  chain: a fixed literal holds the address of a global slot, that slot
  holds an "owner" pointer, `owner+0xc` is the record) — into the local
  state block's `+0x5A/+0x5E/+0x60/+0x5C/+0x62`, each **left-shifted by 8**
  (`raw << 8`, an 8.8 fixed-point conversion: `raw=15` becomes `3840`,
  matching the `1/256`-unit reading used throughout this finding). `+0x5A`
  is duplicated to `+0x56`, `+0x5C` to `+0x58`. Also zeroes the per-index
  valid-bitmask at `+0xC` and a couple of housekeeping fields (`+0x10`,
  `+0x14` cleared; `+0x12 = 0x1B0`).
  - **Refuter-pass resolution (`jus-36wu`)**: the literal at `0x0215FC1C`
    is `.word 0x02172984` — the global slot is `[0x02172984]`, the record
    is `[[0x02172984]+0xC] + {0,4,8,0xC,0x10}`. Raw values in every deck
    measured so far: `{15, 10, 4, 4, 20}` for indices 0-4 (derived from
    the four observed `<<8` deposits — `3840=15<<8`, `2560=10<<8`,
    `1024=4<<8` (twice, indices 2 and 3) — plus the `+0x62`/index-4
    increment amount, `20<<8=5120`, below). This is still a single
    deck-independent snapshot, not per-move data; whether it varies by
    deck is untested (only one deck configuration measured).
  - **Static read, `jus-1bkw`, 2026-09-14 (offline, no emulator)**:
    tried to dump the idx-indexed table (`record + idx*4`, the same
    record generalized past the fixed indices 0-4 above — its offsets
    `{0,4,8,0xC,0x10}` are exactly `idx*4` for `idx=0..4`) straight from
    `jus_files/overlays/ov06.bin` using `scripts/decomp` conventions plus
    `capstone`. The literal `.word 0x02172984` appears 5 times in ov06;
    besides the already-known read at `0x0215FC1C`, a second function
    (`0x02161500`-`0x02161568`) is the record's ALLOCATION site — it
    stores the return value of a virtual call
    (`ldr r2,[[r0]+0x2C]; blx r2`) into `owner+0xC`
    (`str r0, [r2, #0xc]` at `0x02161560`), where `owner = *0x02172984`.
    **The record's address is set at runtime by that call, not baked
    into the ROM/overlay image, so its byte contents cannot be dumped
    statically** — searching all `arm9`/overlay `.bin` files for the
    raw `u16` sequence `{15,10,4,4,20}` found no matches, consistent
    with this. A neutral codex second opinion (prompt:
    feel-captures/sp-deposit-2026-09-14/codex_prompt_static_table_read.txt,
    transcript:
    feel-captures/sp-deposit-2026-09-14/codex_second_opinion_static_table_read.md)
    independently read the same
    instructions and confirmed the stored value is a call's return, not
    an embedded literal, and that establishing the pointed-to contents
    "requires further tracing of the callees ... or runtime
    observation." **The ability-id ↔ idx mapping (what idx 6, 8, 14
    correspond to) stays OPEN**; the only known raw values remain the
    ones measured live: `{15,10,4,4,20}` for idx 0-4, and idx 14's
    `table_val` raw `10` (`0xa00`).
  - **`+0x5A`/`+0x5C` are accumulators, not fixed constants; `+0x5E`/`+0x60`
    are constants.** Three more stores inside this block chain into them:
    `0x0215FD00` adds a per-ability table value (`[r0+0x16+2*idx]`, the
    Fragment B cache below) into `+0x5A`, `+0x5C`, `+0x56`, and `+0x58`;
    `0x0215FD68` adds `+0x62` (the index-4 snapshot field) into `+0x5A`
    (`ldrh +0x5a; ldrh +0x62; add; strh +0x5a`); `0x0215FD7C` then
    restores `+0x5A`/`+0x5C` from the untouched duplicates `+0x56`/`+0x58`.
    `+0x5E`/`+0x60` are written only by the Fragment A snapshot itself —
    nothing else stores to them.
- **Per-index lazy cache ("Fragment B"), `0x0215FC20`–`0x0215FC6C`**: takes
  an index `r1`; tests bit `r1` of the state block's `+0xC` bitmask and
  returns immediately if already set (idempotent, load-once). Otherwise
  sets that bit and reads a **second global table**, `[[global]+0xc] +
  r1*4`, a 4-byte record with two `u16` fields: the first (`<<8`, same
  fixed-point conversion) is written to `+0x16 + 2*r1`; the second
  (unshifted) to `+0x36 + 2*r1`. `+0x36+2*idx` is the table already
  documented above as feeding the `0x0215FED0`/`0x0215FF98` per-collision
  ticks — so this is the shared cache both those ticks and the `+0x64`
  writer below draw from, populated per-index on first use.
- **Deposit writers ("Fragment C"), `0x0215FCB8`–`0x0215FCFC`**, each 3-6
  instructions and each called directly (`bl`), not through a table:
  - `0x0215FCB8` (**fourth writer, found in the Refuter pass**):
    `strh [r0+0x66], [r0+0x5A]; strh [r0+0x68], [r0+0x5C]` —
    unconditional copy of both accumulators in one call. The only `strh`
    to `+0x66`/`+0x68` in ov6.
  - `0x0215FCCC`: `strh [r0+0x6A], [r0+0x5E]` — unconditional copy.
  - `0x0215FCD8`: `strh [r0+0x6C], [r0+0x60]` — unconditional copy.
  - `0x0215FCE4(r0, r1)`: conditional on bit `r1` of `+0xC` (the same
    Fragment B bitmask); if set, `strh [r0+0x64], [r0+0x16+2*r1]`.
  So **`+0x66`/`+0x6A`/`+0x6C` deposits are straight copies of the
  Fragment A/accumulator fields `+0x5A`/`+0x5E`/`+0x60`, and `+0x68` is a
  copy of the `+0x5C` accumulator**, while **`+0x64`'s deposit is a
  per-ability-indexed lookup**, gated on whether that ability slot was
  ever touched. There is no writer that copies `+0x62` directly to a
  cell — it only feeds `+0x5A` via the `0x0215FD68` increment above, so
  the `5120` payout (`20<<8`, index 4) most likely surfaces at `+0x66`
  (through the accumulated `+0x5A`) rather than at a dedicated cell of
  its own; not confirmed live this session (see Open).
- **Call sites ("Fragment D")**: `r0 = obj+0x130` at both sites (`obj`
  here is the `char`/fighter record already used for `+0x1A8`/`+0x1B4`
  elsewhere in this doc, so the pending cells sit at `char+0x130+0x64` etc,
  consistent with "obj+0x64" as written throughout this finding once "obj"
  is read as that `+0x130` sub-object).
  - Inside the per-object tick function `0x0215A978` (the same function
    that hosts the negative-debit call at `0x0215AC64`, see below), at
    `0x0215ACAC`–`0x0215ACCC`: `bl 0x215fccc` (write `+0x6A`), then
    `bl 0x215fce4(r1=8)` (conditionally write `+0x64` from index 8), then
    `bl 0x215fed8` (the already-documented `+0x6A` **payout** thunk), then
    `bl 0x215fc78(r1=8)` (an unexamined sibling dispatcher, also indexed
    by 8, not traced further this session).
  - Inside a separate on-hit-resolution handler, `0x0215EAEC` (resets hit
    flags `+0x1E7/+0x1E8/+0x1E9`, the hit-cooldown timer `+0xDC`, calls a
    guard predicate at `0x215d6c0`), at `0x0215EB3C`: `bl 0x215fcd8`
    (write `+0x6C`) — this is the writer that fires on a landed/absorbed
    hit, consistent with the doc's "a hit that connects or is absorbed by
    guard... makes one deposit."
  - The fourth writer, `0x0215FCB8`, is called at `0x0215A074` (`lr
    0x0215A078`) inside `0x02159EF8` — two instructions before the
    `0x0215A080` call site that reaches `0x0215ACAC` above, i.e. the same
    per-object tick function's caller, not a separate handler.

## Mechanism

The pending-deposit mechanism is **CONFIRMED (`jus-36wu`)** for the parts
this session directly observed: a per-object state block at
`char+0x130` holds five `u16` pending cells (`+0x64/+0x66/+0x68/+0x6A/+0x6C`)
fed by four small, unconditional-copy writer routines
(`0x0215FCB8/0x0215FCCC/0x0215FCD8`, plus the gated `0x0215FCE4`), each
called directly (not through a table) from one of two sites: the
per-object tick (`0x0215A978`, called from `0x02159EF8`) or the
on-hit-resolution handler (`0x0215EAEC`). The values these writers copy
trace back to a single global config record (index-selected fields
`{15,10,4,4,20}` in every deck measured, `<<8` fixed-point converted) and
two of its five indices (`+0x5A`, `+0x5C`) are accumulators that other
code can add into before the snapshot is copied out, not fixed constants
— so "the deposit amount" is deck-configured but not necessarily
per-firing-constant for every cell. What is still open (not yet checked
live): what triggers the Fragment A snapshot itself (once per hit, per the
observed cadence, but the caller wasn't traced); whether the `+0x64`
gated path ever actually fires (its bit was read but never set live, in
every run); and whether a guarded hit deposits through a different path
entirely versus simply not depositing (the guard run's HP-flat inference
covers this but `record+0x40` bit `0x1000` itself was never read live).

**Answer to goal (1):** the amount is neither a fixed constant embedded at
the call site nor a per-move byte read directly off the move data — it is
a **snapshot of a shared global config record** (Fragment A, indices 0-4,
now resolved to `[[0x02172984]+0xC]+{0,4,8,0xC,0x10}`, raw
`{15,10,4,4,20}`) for the `+0x66`/`+0x68`/`+0x6A`/`+0x6C` cells, and a
**per-ability-indexed table** (Fragment B/C, `+0x16+2*idx`) for the
`+0x64` cell. The ability-table literal inside Fragment B was not
resolved to a specific table address or dumped. Confidence: the
copy-only-writer mechanism is **CONFIRMED (`jus-36wu`)** live for
`+0x66/+0x68/+0x6A/+0x6C` (the fourth writer closed the gap that made
`+0x66`/`+0x68` look unobserved); PLAUSIBLE for `+0x64`, whose gating bit
has never been observed set.

**Answer to goal (2), the four observed deposit sizes**: all four divide
exactly by 256 with no remainder (`3840/256=15`, `2560/256=10`,
`5120/256=20`, `1024/256=4`), matching Fragment A's `raw<<8` conversion
exactly. **Now attributed by cell, live**: `3840` (index 0, `+0x5A`) at
`+0x66`; `2560` (index 1, `+0x5E`) at `+0x6A`; `1024` at two independent
cells — index 2 (`+0x60`) at `+0x6C`, and index 3 (`+0x5C`) at `+0x68`
(both raw `4`, hence the same figure from two sources). `5120` (index 4,
`raw=20`) is still not attributed to a specific writer firing: `+0x62`
only feeds the `+0x5A` accumulator (via `0x0215FD68`), never a cell
directly, so the best candidate is that it surfaces through `+0x66`
(the same cell as index 0) once accumulated into `+0x5A` — untested live.
Falsification for the open point: watch `char+0x130+0x56..+0x62` and
`+0x66` in the naruto-fy `5120` state through the sequence that produces
it, and check whether `+0x5A` reaches `0x1400` before the `+0x66` copy.

## Open

- Initializer for `+0x5C8/+0x5CC/+0x5CD` (meter creation, guard-sp.md §2
  gap 1) not found; the `+0x558` list init is a different field group, and
  the mechanism here has no node structure, so the `+0x558` list may not be
  the SP meter at all (gap 2/3 reframed, unverified).
- Writer of the pending SP delta `+0x144`.
- Caller and rate of `0x02077D40`.
- **New, `jus-36wu`**: the caller of Fragment A (`0x0215FB88`) — what
  triggers the snapshot itself, once per hit? — and the address/contents
  of the global config record (base now known, `0x02172984`, but the raw
  table behind `[[0x02172984]+0xC]` itself was not dumped) and the
  ability-indexed table Fragment B reads from.
  - **Resolved (partial), `jus-1bkw`, 2026-09-14**: caller chain named
    three levels (`0x02157114` → wrapper `0x0215FAC4` → `0x0215FB88`,
    codex-checked). Live on `pc-kakashi-npc-jotaro-fightcpu`, the
    snapshot fired **periodically** (9 times, two clusters with a
    194-214-frame period, one fighter only) rather than once per
    landed/blocked hit or special — none of that session's driven Y
    jabs/X special produced a new firing.
    **Correction, second pass same day**: the earlier "wrapper clears
    the same `+0x14` field the latch tests" claim is retracted — three
    distinct fields were conflated. `0x0215FB88` itself clears
    `state_block+0xc/+0x10/+0x14` and sets `+0x12=0x1B0` (see the
    Snapshot/Fragment A section above). The wrapper `0x0215FAC4` clears
    `[r7+0xc]`/`[r7+8]` where `r7 = char+0x120`, not `+0x14`. The latch
    `0x02159EF8` tests (`ldrh r0,[r6,#0x14]`, `r6` = CHAR base, confirmed
    by `add r0,r6,#0x130` at `0x0215A064`/`70`/`78` and the log rows'
    `char=0x224ef00`/`state_block=0x224f030`) is `char+0x14`, `0x130`
    bytes away from `state_block+0x14` — a different field the wrapper
    and the snapshot's own clear never touch. Still open: what rearms
    `char+0x14` (the actual ~200-frame timer source), `0x02157114`'s own
    two callers (`0x02156A38`/`0x02157328`), and the global config
    record's raw table contents. Full write-up:
    feel-captures/sp-deposit-2026-09-14/RESULTS.md.
- Which ability indices feed `0x0215FD00` (the accumulator add into
  `+0x5A/+0x5C/+0x56/+0x58`) — not traced this session.
- **New, 2026-09-14 (`jus-atns.2` P3 tail fix pass, Part B).** A koma
  switch (`pc-taikoubou-npc-jotaro-dark-tournament`, `L` then `R`, n=2:
  `q3_switch_lr` and `q3_switch_lr_build`) decomposes exactly one SP bar
  into the fractional pool at the switch-commit frame — pool
  `0 -> 25597`, bars `0x0707 -> 0x0607` — with total SP conserved
  (`7*25600+0 = 6*25600+25597` less one frame of the already-CONFIRMED
  `-3`/frame ability-55/56 tick landing the same frame). Not this
  routine: `0x02158BC0`/`0x02158BCC` never fired in either capture. The
  writer that performs the decomposition is unidentified. Full data:
  the combat notes §8, fix/RESULTS.md Q3.
  - **Resolved (null result), `jus-1bkw`, 2026-09-14**: `0x0215FD00`
    fired zero times across three fixtures (`pc-kakashi-npc-jotaro-fightcpu`,
    `pc-kenshin-luffy-guard`, `pc-momotaro-npc-nami-dark-tournament`) and
    every trial driven against them this session — no index has been
    observed reaching this site yet. Fragment B (`0x0215FC20`) itself
    only ever loaded indices 6 and 14, always freshly (paired 1:1 with
    every snapshot firing).
- The `+0x64` gate: whether its bit is ever actually set live (every run
  this session read `bit_set=0`, including the naruto-fy run where the
  underlying mask itself changed mid-run from `0` to `0x6000`).
  - **Retracted, `jus-1bkw`, 2026-09-14**: the bit DOES read set live,
    for index 14 specifically. 11 of 23 idx-14 firings across all three
    fixtures this session (12 clear) read `bit_set=1`, each writing
    `+0x64=0xa00` (`2560`, `10.00`) — 8 of those 11 on
    `char=0x224ef00`, 3 on `char=0x2228e80` (NOT both fighters every
    time), from a previously-uncatalogued call site (`0x0215A080`,
    `lr=0x0215A084`, hard-coded `mov r1,#0xe` — the same latch-gated
    block the snapshot resolution above names). Index 8 (the
    already-known per-object-tick call, `lr=0x0215ACBC`) reads
    `bit_set=0` in all 14 of its firings this session — the gate is
    index-specific, not permanently closed. 37 gate firings total this
    session (23 idx 14 + 14 idx 8), corrected from an earlier
    single-fixture count of 17/20.
- Whether flag-guarded presses deposit at all: **retracted as "in
  tension" — see the Mechanism section and the guard-run correction
  above** — but `record+0x40` bit `0x1000` itself is still never
  instrumented, so "guarded" is inferred from HP-flatness, not read
  directly.
  - **Resolved (partial), `jus-1bkw`, 2026-09-14, then DOWNGRADED same
    day**: re-ran `pc-kenshin-luffy-guard` reading `M+0x40` bit `0x1000`
    directly at the `0x0215EB3C` writer (`M = [[char+0x1a8]+0x10]`,
    matching `atns5_guard.gdb`'s own field — a first attempt at this
    same session read only `[char+0x1a8]`, one indirection short, got a
    pointer-shaped non-bitmask value, and was caught and fixed before
    any conclusion was drawn from it) and got one row: the unguarded
    press, bit `0x1000=0`. **Correction**: the raw log
    (`feel-captures/sp-deposit-2026-09-14/logs/fixture2_gdb.log.gz`) is
    9 lines and ends at that same row (frame 160), then GDB itself
    aborts mid-target-run ("Cannot execute this command while the
    target is running") — the session crashed before it's known
    whether the plan's second and third B presses were ever reached,
    and the plan-frame ↔ probe-frame offset was never recorded. "Did
    not fire at all for the two later presses" is retracted for lack
    of data. **"The later presses were guarded" reverts to an
    HP-flat inference**, not a direct observation, until a clean rerun
    records the offset; the one unguarded-press row (bit `0x1000=0`)
    stands on its own.
  - **Part B rerun, `jus-1bkw`, 2026-09-14, corrected in the
    fix-and-rerun pass the same day**: `bit_1000` read every anchor
    tick for both fighters, plus a 4th B press. **Correction: "clean
    rerun, no crash" was false** — this rerun's own raw log still ends
    on the same GDB "target is running" abort as the first attempt; the
    driver bugs actually fixed that session (`jusemu()`'s JSON parsing,
    `Runner.idle()`'s plan shape) never touched it. It is benign
    end-of-session noise, not a mid-plan crash: the log runs the full
    680 frames requested (not 300), and the abort lands only after all
    four scripted B presses (probe frames 45/64/79/104) have already
    fired. Only one hit landed the whole session (`Q3_HITWRITER` at
    probe frame 79). Input-edge analysis (`+14` constant offset,
    confirmed at all four presses) shows press 1 (probe 45) missed;
    **the single writer firing at frame 79 coincides exactly with
    press 3's own edge**, so it cannot be assigned to press 2 versus
    press 3 — presses 3/4 produced no writer firing AND no `bit_1000=1`
    reading either way, which is consistent with either "guarded" or
    "missed" and does not distinguish them.
    `bit_1000` read `0` at every tick around all four press windows
    except one single-frame pulse to `1` at frame 89 — coincident with
    a payout-decay tick, not any button press. **New concern: this
    casts doubt on `bit_1000` being a stable "guarded" flag at all**
    (see guard-sp.md §0.5's forward pointer for the per-hit-event
    reading this is consistent with). Stays OPEN. See
    feel-captures/sp-deposit-2026-09-14/rerun/RESULTS.md
    (corrected).
- The `5120` deposit's specific writer firing (candidate cell `+0x66` via
  the `+0x5A` accumulator, per the falsification test above — not
  confirmed live).
  - **Still open, `jus-1bkw`, 2026-09-14**: `0x0215FD68` fired zero times
    across all three fixtures this session either; the falsification
    test could not be run.
- The negative-debit trigger (`0x0215AC64`, still zero in every firing
  observed, across all four live states now, corrected counts included).
  - **Still open, `jus-1bkw`, 2026-09-14**: 33 more firings measured
    (three fixtures, idle/jabs/X-special/guard presses), `amount=0` in
    every one; no support call was available to test in any of the
    three fixtures. Unexercised, not proven always-zero.
  - **Part B rerun, `jus-1bkw`, 2026-09-14, corrected in the
    fix-and-rerun pass the same day**: added `0x020781E4` itself as a
    fallback breakpoint per the ticket brief; still no negative amount
    anywhere. But the bar-count byte (`s8[slot+0x5CD]`) DID drop twice
    live in the rerun (`pc-kakashi-npc-jotaro-fightcpu`, slot
    `0x21df780`), on the CPU/Jotaro side: `9->8` at frame 713, `8->7`
    at frame 852. **Correction: "the pool word stayed 0 through both
    drops" is false** — `SP_HEARTBEAT` reads `pool=0` at the first
    drop but `pool=3840` at the second; this is a one-bar debit with
    the pool remainder untouched, not evidence the debit bypasses
    `0x020781E4`'s arithmetic, and that inference is retracted.
    **Correction: the `0x020781E4` caller enumeration was not just the
    two sites already instrumented.** The `SPAPPLY` fallback logged 77
    rows total on this fixture: 49 at `lr=0x215ffbc` (payout-decay,
    positive only), 25 at `lr=0x215ac68` (`=0x0215AC64`, `amount=0`),
    and a previously uncatalogued third site, `lr=0x2157dd4` (return
    address of the static caller list's `0x02157DD0` above), firing 3
    times — `amount=+256` at frames 964/976/988, matching a `pool`
    increase of exactly `+256` one tick later (965/977/989). Not
    through either of the two sites already enumerated; `0x2157dd4` is
    now instrumented but still untraced. Separately, the `0x0215FCE4`
    `idx=13` correlate (`lr=0x21577d8`, a different address from the
    `0x2157dd4` site above) fires at frames 712 and 851 — **one frame
    before the drop is visible** (713/852), not the same frame as
    first published; still not a confirmed writer identification. See
    feel-captures/sp-deposit-2026-09-14/rerun/RESULTS.md
    (corrected).
  The ability 55/56 tick is no longer open for its amount/mechanism — see
  the live update above — but its firing *rate* is: two brackets in
  `pc-momotaro-npc-nami-dark-tournament` measured 1.11 and 0.68
  fires/bridge-frame respectively, an unexplained >60% spread.
  - **Resolved (partial), `jus-1bkw`, 2026-09-14**: measured directly
    against a dedicated per-frame breakpoint counter (the anchor PC
    `0x02082E10`, the same one `atns5_guard.gdb` uses) in one
    continuous session: 3709 firings, all 3708 successive frame deltas
    equal to exactly 1 — 1 fire per `0x02082E10` anchor tick, zero
    skips (corrected count: the first pass through this session's own
    log mis-transcribed this as 2906/2905; the committed raw log has
    3709 `Q5_ABILITY5556` rows, and the 950-idle/320-active figures
    describe the driving plan's segment lengths, not this total).
    **Whether this supersedes the 1.11/0.68 reading above is left
    open** until a cross-check against `emu.framecount()` settles
    whether the two readings share a frame basis.
  - **Resolved, Part B rerun, `jus-1bkw`, 2026-09-14, corrected in the
    fix-and-rerun pass the same day**: ran `emu.framecount()` (bridge)
    beside `$e1bkw_frame` (anchor tick) over the same interval: 1292
    anchor ticks (matching 1292 `Q5_ABILITY5556` firings exactly)
    against 904 bridge frames. **Correction: the raw `1292/904 =
    1.429` ratio is an interval-boundary artifact, not evidence
    against 1:1.** Within one `run_plan()`/`idle()` call the anchor
    tick and the plan's own clock advance in exact lockstep — fixture
    3's `INPUT_HEARTBEAT` edges sit a *constant* `+356` ahead of the
    plan's own segment-start frames at all six points
    (`320/360/400/420/440/460` → `676/716/756/776/796/816`, identical
    gaps throughout; re-derived from the committed log and plan JSON by
    `framecount_crosscheck()` in `scripts/analysis/e1bkw_sp_run.py`,
    unit-tested against that exact file). `373` of the `1292` ticks
    accrue *after* the plan's own last `tail_frames` frame, while the
    bridge free-runs at ~60fps in the gap before the driver's next
    command (the same behavior `loop-state-atlas.json` notes for
    `jus-vkj`, whose own harness-fix conclusion was later retracted on
    an unrelated point — the free-run mechanism it measured is the one
    cited here). Subtracting the free-run tail gives an in-plan count
    of `919` ticks against the same `904` bridge frames — ratio
    `1.02`, consistent with **1 anchor tick per rendered frame**
    (physics.md's `0x02082E10` integrator note: fires once per frame).
    The ability 55/56 tick is therefore **1 fire per rendered frame =
    `-3` raw/frame, CONFIRMED (`jus-1bkw`)**. The original session's
    `1.11`/`0.68` brackets are the same artifact on a different window:
    the pre-plan `idle(320)` call requests `321` bridge frames
    (`jus_plan.validate_plan()`'s own `total_frames`, also
    unit-tested) but `355` anchor ticks elapse before the next plan's
    own clock starts — `355/321 = 1.106`, the original `1.11` bracket,
    on the same free-run window rather than a distinct rate. There is
    no reciprocal-units mismatch to reconcile either: comparing `0.68`
    fires/frame against `1.429`'s reciprocal `0.70` frames/fire mixed
    the two units, an artifact of the same interval-boundary confusion,
    not a second real rate.
