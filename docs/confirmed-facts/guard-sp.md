# Guard and SP gauges reference

> **Scope.** Tracker item `jus-map.10` (closed). Inventory verdict
> (INVENTORY.md §5): **guard gauge portable, SP thin**. The guard
> gauge is found and measured at runtime, see §0.5
> (`jus-guard-gauge-found-a55l`). The SP side is still thin: the *apply machinery*
> is confirmed at instruction level, but how SP meters get created and whether SP
> is deck-shared or per-character is not settled. A reimplementer can build the
> guard gauge now and the SP plumbing, but not the SP gauge model. See §2 GAPS.
> Preamble updated 2026-09-02.

Primary source: [Battle-Engine-Map.md §guard-sp-gauges](../research/Battle-Engine-Map.md)
(read its taint banner first; the sections cited here are the Phase-0 spec-B12 claim
table and the P157–P161 updates, none of which are in the banner's tainted list).
Tracker items: `jus-hp-block-at-char-0x56c-q86`, `jus-map.13`.

## Navigate this reference

| Topic | Section |
|---|---|
| Behavioral gauge model | [0](#0-gauge-model-owner-testimony-behavioral-ground-truth) |
| Runtime guard gauge | [0.5](#05-guard-gauge-found-at-runtime-2026-09-02) |
| Push attack (Down+X while guarding) | [0.7](#07-push-attack-downx-while-guarding-mapped-statically-2026-09-09) |
| Human guard release vs. CPU hold | [0.8](#08-human-input-guard-release-vs-the-cpus-122-frame-hold--plausible-2026-09-12-re-run-2026-09-12b) |
| Apply machinery and SP path | [1](#1-what-is-confirmed-the-apply-machinery) |
| Open implementation gaps | [2](#2-gaps-what-a-reimplementer-cannot-build-yet) |

## 0. Gauge model — owner testimony (behavioral ground truth)

The following is player testimony about observable gauge behavior. Any memory-level
finding must reconcile with it:

- **SP gauge and guard gauge are different mechanics.** SP is a spendable
  resource used for: special attacks (X button), summoning support panels,
  and an auto-guard passive that spends a small amount of SP to automatically
  guard incoming attacks.
- **"Guard gauge" is an anti-turtle mechanic**, not a meter in the SP sense:
  as a character blocks damage, they flash red increasingly with the amount
  blocked "in one sitting"; eventually the guard breaks and the character is
  put into a very long hitstun.
- **Known jank / emergent play:** spam-tapping the guard
  button effectively prevented the guard-"health" depletion from accumulating,
  so a player could turtle indefinitely.

Note the original `+0x558` vs `+0x56C` framing of the dispute is moot: both
offsets were later identified as other structures (`+0x56C` = character/HP
block, tracker item `jus-hp-block-at-char-0x56c-q86`; `+0x558` = the second
ability-source node list, tracker item `jus-second-ability-source-0x558-5rp`). The
actual gauge storage is now found in the per-victim hit-result block (§0.5,
`jus-guard-gauge-found-a55l`). `.13` stays waived.


## 0.5 Guard gauge — FOUND at runtime (2026-09-02)

`jus-guard-gauge-found-a55l` (closes the hunt in `jus-guard-gauge-discovery-7mr8`).
Evidence: hitstun-2026-09-02
`hs07`–`hs12`; states `pc-kenshin-{luffy,nami,franky}-guard`. Conditions:
Dark Tournament training, auto-heal OFF, CPU COM設定 = ガード, attacker Kenshin
B, distance held by a scripted re-step between jabs. Every number below is a
per-frame RAM read, and the threshold claims are poke tests.

The gauge is **not** the `{+0x16 max, +0x18 current}` clamp accumulator of §1.1
and not on `+0x558`/`+0x56C`. It lives in the per-victim **hit-result block**
(`0x02230D60` in these states; the same block that stages knockback in
physics.md §4.2). That block is the ov6 **fighter object** (physics.md §5,
`jus-fighter-object-identity-c56i`); "hit-result block" is the name this campaign gave it before that was
known. The Action Replay "Defense never wears" byte at `+0x102` is most likely
this field pinned at 0 (`jus-defense-duration-vs-guard-gauge-bclp`):

| field | meaning | evidence |
|---|---|---|
| `hit+0x102` (s16) | gauge **current**, whole displayed-damage units | +5 per blocked Kenshin B on Luffy, +7 on Nami/Franky |
| `hit+0x104` (s16) | gauge **max**, written when the guard starts | 65 on all three bodies |

**Rules (each measured):**

1. **Cost of a block = the hit's post-resistance damage, fraction dropped.**
   Kenshin B does 7.0 to Nami/Franky and 5.25 to Luffy (blunt passive); the
   gauge took 7 and 5. In code (ov6 `0x0215EAEC` — the per-frame guard
   update routine, not a block-handler entry (run 6, `jus-xcz0`) — store at
   `0x0215EC64`): `gauge += moveData[+0x13c] >> 6`, i.e. the 1/64-unit damage
   shifted to whole units. No weight term, no HP term.
2. **Max is 65** (`0x41`), or **130** (`0x82`) when bit `0x400000` (bit 22) of
   the fighter's ability bitset `obj+0x128` is set (`0x0215EBD0`–`0x0215EBE8`).
   `obj+0x128` is the cached ability-id bitset — writer ov6 `0x0215FB3C` sets
   bit `N` (`word = N>>5`, `bit = N&31`, no remap) for each ability id `N` the
   character carries — so bit 22 is **ability 22, "Guard ability +"**
   (helpers.md). Static: that bit has exactly one reader in ov6, `0x0215EBD4`
   (static-guard-max-130);
   no other guard parameter (drain, hold, block cost) is tied to it. Runtime:
   **poke-confirmed** (`jus-guard-max-130-ability-22-8gil`,
   runtime-report-1) —
   poking `obj+0x128 |= 0x400000` on the victim raised the measured max from
   65 to exactly 130, block cost (+5/blocked jab), hold (122 frames) and drain
   (1/frame) all unchanged.

   **Break threshold at the doubled max — confirmed 2026-09-03**
   (`jus-guard-max-130-ability-22-8gil`,
   runtime-report-2
   E5(iv), `pc-kenshin-luffy-guard`). The gauge was poked to one below and to
   exactly each max, then hit again, at both max values in the same session:

   | poke | max | gauge after poke | gauge after hit | `M+0x171` | `obj+0x110` | break? |
   |---|---|---|---|---|---|---|
   | 64 | 65 | 65 (clamped) | 65 | 0 | 24 | no |
   | **65** | 65 | 65 | **0** | **60** | **80** | **yes** |
   | 129, ability 22 | 130 | 130 (clamped) | 130 | 0 | 24 | no |
   | **130**, ability 22 | 130 | 130 | **0** | **60** | **80** | **yes** |

   **The break fires iff the gauge is already at max when the hit arrives**,
   confirmed at both 65 and 130; one below the max always clamps instead. A
   broken guard also lets the hit through as damage (336 raw), which the
   clamped hits do not. A supporting sweep (34 blocked-jab cycles, no gauge
   poke) is independent evidence the doubled max is a real accumulation
   ceiling: the control gauge climbs +5/jab and stops at 65, while with
   ability bit 22 set the same plan keeps accumulating past 65 to 75.
3. **Clamp, then break on the next hit.** When an add reaches or passes the
   max, the value is clamped to the max and bit `0x4000` is set in the
   move-data word `+0x40` (`0x0215ECEC`–`0x0215ED14`). The **next** blocked
   hit that arrives with the gauge at max breaks the guard: full damage, full
   −448 pushback, a 60-frame hitstun (physics.md §4.5), guard flag cleared,
   gauge reset to 0 by ov6 `0x0215EF48`. Poke tests: 61 → hit → 65 (block);
   64 → hit → 65 (block); 65 → hit → break; and, at the doubled max,
   129 → hit → 130 (block); 130 → hit → break (confirmed 2026-09-03, above).
4. **Guard holds for 122 frames after the last blocked hit**, regardless of
   gauge level (122 after one block, after two, and after eleven). The guard
   flag is the byte `H+0x7b` (`0x0220F50F`; 4 while guarding). The gauge does
   **not** decay while the guard is held. Measured with the CPU set to
   guard and after a blocked hit; a human release clears within single
   digits to low double digits of frames regardless of whether an incoming
   hit was just blocked or not (PLAUSIBLE, `jus-rsye`, §0.8) — **the
   122-frame value is CPU-AI behavior, not a property a human's release is
   also subject to.**
5. **Once the guard drops the gauge drains 1 per frame** (ov6 `0x0215EF24`:
   `if (g > 0) g--`, called every frame from `0x02156EB8`). This is the owner's
   tap-reset jank in §0: letting go of guard starts the drain, so tapping keeps
   the gauge near zero and the break never comes. Nothing resets the gauge on
   guard re-entry; only time drains it, and only the break zeroes it.
6. **Blocked-hit pushback is −224 raw**, half the clean jab, identical on the
   light, standard and heavy body.
7. The "flash red as it fills" in §0 matches the code at `0x0215ED18`–`0x0215ED84`:
   above 30 a blink counter (`obj+0x1e9`) runs with period `((max−g)>>6)+16`.
   Not measured visually.

**The break decision — FOUND (2026-09-02, `jus-guard-break-decision-obj-0x110-1xty`).**
Evidence guardbreak-2026-09-02
(runtime report,
second runtime report,
static reports, two neutral Codex
reads). Conditions: `pc-kenshin-luffy-guard`, the `hs09` plan (breaks at plan
frames 719 and 1439), `JUS_WATCH` write hook plus one GDB probe. The decision is
**not** a live compare of `+0x102` against `+0x104` on the hit. It is a
two-stage latch across the ColPrm scratch block `M = [[obj+0x1a8]+0x10]`
(victim `0x0220F494`):

1. **Per frame, while the gauge sits at max**, the ov6 clamp path
   (`0x0215ED14`, reached every frame from `0x0215EBF4` while guarding) stores
   `M+0x40 |= 0x4000`. `M+0x40` is rebuilt from scratch every frame by arm9
   (five to six stores per frame, torn down to `0x8`), so `0x4000` is a
   condition "gauge ≥ max right now", not a sticky event bit. It was present on
   exactly the 96 frames the gauge read 65 and on no other frame.
2. **On the hit-receive frame**, arm9 `0x02081740` (`ldr [M+0x40]; tst #0x4000`)
   is the instruction that decides. If set: `0x02081748` stores
   `M+0x40 |= 0x10000` (the "this hit broke guard" bit) and `0x02081754` adds
   `0x3C` = 60 to the byte `M+0x171` (cleared to 0 at `0x02081308` at the top of
   every hit-receive frame). Both stores fired exactly twice in 2197 frames, on
   the two break frames, and never on a clean jab or a blocked hit. The
   function is the arm9 hit-event processor `0x02080F14` (called from
   `0x02080C28`;
   static-arm9-hit-receive); at the decision `r5` is the
   victim's hit record (`[r5+0xc] = M`) and `r8 = M + 0xA4`, both pinned by
   the runtime store addresses, so the static report's attacker/victim labels
   for those two registers are inverted.
3. Later the same frame, ov6 `0x0215A978` (the per-frame fighter update, called
   from `0x02156EB0`) tests `M+0x40 & 0x10000` at `0x0215ABC0` and calls the
   gauge reset `0x0215EF48` (`bl` at `0x0215ABCC`, GDB backtrace `lr =
   0x0215ABD0`, gauge 65/max 65 at entry), then `0x0207342C(0x7a, 0x2c)`, the
   break sound/effect. The three "static callers" the old text listed were a
   mislabel: the call is inside `0x0215A978`, not at its entry.
4. The hitstun then comes out as 60 because `M+0x171 = 60` feeds the formula in
   [physics.md](physics.md) §4.5 (`clamp(60 + 20 + 0, 16, 60)`).

Why the poke tests fit: poking 61 or 64 leaves `0x4000` clear on the hit frame
(the clamp that sets it runs after the arm9 check), so the hit blocks and the
gauge clamps to 65; from the next frame `0x4000` is carried, so the following hit
breaks. Poking 65 satisfies "gauge ≥ max" immediately. ~~The "is guarding" test
that routes a hit into the block handler at all is `obj+0x128 & 0x10` in the ov6
guard router `0x0215E9A0` (`0x0215EA14`)~~ — **corrected 2026-09-03 (run 6,
`jus-xcz0`): `obj+0x128` is the ability bitset and read a flat `0x2000` while
guarding; the live "is guarding" flag is bit 26 of `M+0x78`, written only by
ov6 `0x0215E914`.** `H+0x7b` (`0x0220F50F`) is not a separate storage — it
is byte 3 of the same word at `M+0x78` (`0x0220F494 + 0x7B = 0x0220F50F`),
and bit 26 of the word is that byte's `0x04` bit (§0.8, `jus-rsye`). Not
state code `obj+0x18 == 3` (the router bails on state 3).

**Instant shatter (owner rule, measured 2026-09-03, `jus-xcz0`,
runtime-report-6):**
every down+Y shatters a live guard with the gauge untouched (0 → 0, no blocked
bit, no gauge add); the guard flag drops the next frame and the move's own
damage and reaction apply in full, byte-identical to the same hit on an
unguarded victim (Kakashi down Y: type 5, hitstun 40, 16.0; Sasuke down Y:
type 2, hitstun 20, 14.0). The shatter runs the same gauge-reset call
`0x0215ABCC` once, driven by `M+0x40 & 0x10000` set at arm9 `0x02081DC8`
(inside `0x02081D68`); the gauge-full break sets that bit from `0x02081748`
and **only that path adds 60 to `M+0x171`** (`0x02081754`), so the long
break stagger belongs to the gauge-full break alone. Forcing the `0x10000` bit
off did not stop the shatter: the block-vs-hit routing happens earlier, at
collision classification. Codex agreed on the control flow.

**The routing marker — CONFIRMED CAUSALLY (2026-09-12, `jus-ce7u`,
[shatter-classification-bit26](../research/findings/shatter-classification-bit26.md)):**
bit 26 (`0x04000000`) of the attacker hit element's `+0x14` word is the
discriminator itself, not a correlate. It has at least two readers: the
attacker-flag gate at `0x02081768` (`ldr r1,[r6,#0x14]; tst
r1,#0x4000000`, inside the routine at `0x02080F14`, already measured in
runtime-report-6) and the block/shatter pair-list sort itself, which walks
into the block list (`0x02081B20`) or the shatter list (`0x02081D68`)
depending on the bit. `0x0207F480` is the collision driver entry these
tests patched the word at — the write point, not a reader. In-memory patch
tests, both against a live Kakashi hit element with a same-launch
locate-then-patch recipe (pool slot addresses are stable across melonDS
launches for the same savestate and input plan — a different input plan
changes the slot rotation — so each test still located its element fresh in
the same launch it patched, as the standing recipe):
clearing the bit on a down Y's element degrades the hit to an ordinary block
(blocked-bit store and ov6 gauge-add fire, gauge rises 16, HP untouched, guard
survives); setting the bit on a plain B's element induces a shatter (the
shatter-tag store fires, guard drops, HP drops by the B's own 8.0, gauge never
touched). Both directions moved the call-site trace and the field trace
together. Still open: which authored file byte this live bit is copied from
(see the combat notes §7).

Outcome table: blocked B gauge 0→8 no stun; gauge-full break
65→0, hitstun 60, actionable +71; Kakashi shatter actionable +67; Sasuke
shatter actionable +23. Blocked hits set
`M+0x40 |= 0x1000` (arm9 `0x02081CC8`); received hits set `|= 0x10`
(`0x020811B0`). Bit `0x8000` (ov6 `0x0215EE68`) never fired in these runs — nobody
pressed X during guard. The "block-streak counter" label first written here was
wrong: it is the **push-attack arm bit**, see §0.7 (`jus-7cv7`).

**Forward pointer (`jus-1bkw`, 2026-09-14):** `0x02081CC8` is a per-hit-event
write — it fires once, at the moment a blocked hit is processed, not a
level that stays `1` for the guard's whole duration. A per-anchor-tick
*read* of the same bit taken while a fighter is merely standing in guard
(no hit landing that tick) is therefore expected to read `0`; that is not
evidence against this bit's meaning. `jus-1bkw`'s Part B rerun raised a
"doubt" from exactly that kind of per-tick read (§1.4 below,
[finding](../research/findings/sp-apply-0x020781E4-is-a-mixed-radix-pool-with-bar-count.md)):
its one `bit_1000=1` reading landed on a payout-decay tick, not on a
button press, which is consistent with a per-event marker that had
simply already cleared by the time of that read. What is still open is
narrower than "does this bit mean guarded" — it's whether a per-tick read
taken *at* the hit-event frame itself (not some arbitrary later tick)
reads `1` on a guarded press, which no session has attempted yet.

---

## 0.7 Push attack (Down+X while guarding) — mapped statically (2026-09-09)

Tracker item `jus-7cv7`. Worker static pass (deepseek-v4-flash, 2026-09-09), orchestrator
verification of every decisive excerpt, and a neutral Codex second opinion
(transcripts). **All claims
below are CONFIRMED_STATIC** (instructions quoted from the disassembly
databases); nothing here is runtime-measured yet — each rule carries its
falsification test. Motivating testimony: owner (`jus-ssk6`) — guarding and
pressing X as a melee attack connects pushes the attacker backward; Genroh
guide ([battle-system.md](../research/guides/systems/battle-system.md)) — "Down +
X = Push Attack (counterattack that pushes opponent back)"; in-game tutorial —
"hold down and press X when the box attacks you".

**It is not a move.** No state change, no move-id dispatch, no SP debit, no
damage. Pressing X while the fighter is in guard state 3 arms a short *push
window* that rewrites the next blocked hit's block response:

| stage | address | behaviour |
|---|---|---|
| arm | ov6 `0x0215EE24`–`0x0215EE30` | if latch byte `obj+0x1e7` == 0 and input word `obj+0x6c` bit `0x40` (X) is set → `obj+0x1e7 = 1`. Input bits: X = `0x40`, A = `0x10` (`0x0215DB70`), Down = `0x02` (`0x0215E9DC`), left/right = `0xc`; B and Y are `0x80`/`0x100` in unresolved order (classifier `0x0215A720`) |
| window | `0x0215EE34`–`0x0215EE58` | each frame the latch is live increments `obj+0x1e8`; the arm bit is set while the counter is below 10 |
| set | `0x0215EE5C`–`0x0215EE6C` | defender `M+0x40 \|= 0x8000` every frame of the window — **the push-armed condition**. 9 armed frames (press frame counts, counters 1–9), then 4 dead frames (10–13); the latch self-clears at counter > 12 (`0x0215EEA0`–`0x0215EEAC`), so holding X re-arms in a ~13-frame cycle |
| consume | arm9 block response `0x02081B20` (per hit-event, sole caller `0x02080C38` in the hit-event processor) | at `0x02081BAC` the routine tests the **defender's** `M+0x40 & 0x8000`. Clear → normal block: the staged pushback lands on the defender's `M+0x148`. Set → the target switches to the **attacker's** `M+0x148` and the attacker's `M+0x40 \|= 0x2000` (`0x02081BBC`–`0x02081BD0`) |
| magnitude | `0x02081BD4`–`0x02081C0C` | X case: `0x7d0` (2000 raw) + attacker's active-move `moveData[+0xc]` (signed kbX byte) × 64; **doubled** iff bit 0 of the damage routine `0x020823E4`'s return flag is set (`0x02081BF0`/`0x02081C00` — the return flag, not the damage amount, which travels by reference into `M+0x13c`); forced to 0 iff attacker side word `+0x14 & 0x1000000`. No-X case: base 0, so `kbX × 64` (same doubling condition) — reconciliation with the measured −224 blocked pushback is open (Kenshin B kbX = 4 → static 256 vs measured 224, the same 0.875 factor as the clean side 512 vs 448; ratio 1:2 exact, physics §4.6 open note) |
| sign | `0x02081C18`–`0x02081CB8` | direction resolved from attacker/victim pose x (`+0xc` of each pose at `M+0x5c`), recorded as bit `0x20` of the pushed side's `M+0x40`; in the X case the staged value is then **negated** (`0x02081CA0`–`0x02081CB8`; the −1 sits at `[sp+0x18]` from `mvn r0,#0` at `0x02081B30`) — the negation rewrites the whole accumulator, not just this hit's term |
| apply | ov6 move per-frame `0x0215A278`–`0x0215A2C8` | the attacker's own move callback tests its `M+0x40 & 0x2000` and adds `M+0x148/0x14A` to pose velocity `+0x30/+0x32` (zeroing `+0x24/+0x26` first) — the shove |

**The defender still blocks normally in every other respect.** The tail sets the
defender's `M+0x40 |= 0x1000` (blocked marker, `0x02081CC0`–`0x02081CC8`) in both
cases, so the gauge add (§0.5 rule 1, driven by that bit) still runs — arming the
push costs guard gauge as if you had stood and blocked. The defender's own
`M+0x148` stays 0, so the defender does not move. A block while the latch is
armed also increments the halfword counter at `[obj+0x1a4]+0x54`
(`0x0215EE88`–`0x0215EE9C`, capped at 0xffff; purpose unknown).

**Gates on the arm.** The X poll runs inside the per-frame guard callback
`0x0215EAEC` only after: the guard-entry lock `obj+0x11a` drains to 0 (manual
guard entry writes 6, auto-guard 12 — `0x0215E9F4`/`0x0215EA34`; 1/frame drain at
`0x0215ED98`), the down-attack poll `0x02159D7C(obj,2)` at `0x0215EDB8` (so
Down+Y and Down+B dispatch out of guard before the X test is reached), Down is
still held (`0x0215EDE4`), and the action-lock probe `0x021599B0`
(`[obj+0xa0] == 0x1b`) returns 0. On the callback's first frame the latch bytes
`obj+0x1e7/0x1e8` are zeroed (`0x0215EB0C`–`0x0215EB18`).

**Outside guard, Down+X is simply the X special.** The neutral attack classifier
`0x0215A720` selects `X → move id 0xd` at `0x0215A80C` **without consulting
Down** (up+X is the only direction-qualified X, `0x0215A7F0` → id `0x0e`), and
from any state other than guard 3 that classifier runs before guard entry in the
input priority chain. So the archived Goku damage table's `down+X` row (2.0 /
raw 128 — byte-identical to its `X` row) is the plain X special mislabeled; the
push attack deals no damage. (That table is stage-gimmick-tainted, `jus-f30` —
its damage numbers are wrong for gimmick-off play regardless.)

Conditions block: static reading of the prebuilt disassembly databases
(`scripts/analysis/query.py`), ARM/Thumb, ov6 + arm9; no runtime measurement yet.
Falsification tests (one guard session): (1) attacker `M+0x148` on a pushed block
reads ≈ −(2000 + kbX·64)·d, ×2 if the damage routine's return flag has bit 0 set,
with the attacker's `M+0x40 & 0x2000` set that frame; (2) defender `M+0x148`
reads 0 on the pushed block and ≈ −224 on a normal block; (3) SP word
`slot+0x5C8` flat across a push; (4) X tapped in guard with no incoming hit — no
state change, guard held, latch expires within ~13 frames; (5) gauge still adds
its normal per-hit cost on a pushed block. Codex second opinion agrees on every
stage; its two sharpenings are folded in above (return-flag predicate, whole-
accumulator negation).

---

<a id="08-human-input-guard-release-vs-the-cpus-122-frame-hold--plausible-2026-09-12-re-run-2026-09-12b-lock-gating-mechanism-confirmed-for-kakashi-2026-09-14b-confirmed-for-yusuke-and-formula-confirmed-on-a-third-character-kenshin-2026-09-14c-post-block-accept-boundary-confirmed-on-kakashi-and-yusuke-2026-09-14d--the-same-clear--maxlock_reaches_0--2-button_up--3-plan-basis-floor-as-taphold30-not-a-faster-constant-once-button_up-is-read-on-the-probes-word-basis"></a>
<a id="guard-sp-0-8"></a>

## 0.8 Human-input guard release vs. the CPU's 122-frame hold — PLAUSIBLE (2026-09-12, re-run 2026-09-12b; lock-gating mechanism CONFIRMED for Kakashi 2026-09-14b, CONFIRMED for Yusuke and formula CONFIRMED on a third character (Kenshin) 2026-09-14c; post-block accept-boundary CONFIRMED on Yusuke and on Muhyo (logged as Kakashi) 2026-09-14d; real Kakashi's post-block clear measured 2026-09-22, his k=0/k=1 boundary unmeasured — the SAME `clear = max(lock_reaches_0 + 2, button_up + 3)` plan-basis floor as tap/hold30, not a faster constant, once `button_up` is read on the probe's word basis)

Tracker item `jus-rsye`. Evidence:
guard-2026-09-12/RESULTS.md
§3 and
guard-2026-09-12b/RESULTS.md
§1–3, finding
[guard-release-and-auto-guard-cost.md](../research/findings/guard-release-and-auto-guard-cost.md).
Conditions: `pc-kenshin-npc-luffy-dark-tournament`, P1 (Kenshin) as the
guarder, `jusemu.py watch`/`tail`/`run`/`peek` (no GDB in either session).
This answers the TBD in §0.7/the combat notes §7 ("what a human release does").

**Same-storage note.** `H+0x7b` (`0x0220F50F`, §0.5 rule 4) is not a
distinct byte from `M+0x78` (`0x0220F494`) — it is byte 3 of that same
32-bit word (`0x0220F494 + 0x7B = 0x0220F50F`), and bit 26 of the word is
that byte's `0x04` bit. "4 while guarding" (rule 4) and "bit 26 set while
guarding" (this section) are the same observation read two ways.

Four hold lengths of the guard input (`DOWN`) were driven and watched
frame-by-frame on P1's own `obj+0x18` (state), `obj+0x11A` (guard-entry
lock), and `M+0x78` bit 26 (is-guarding flag): 30 frames and 5 frames
(2026-09-12), a 1-frame tap and a post-block release (2026-09-12b). Every
run corroborates the input identity itself: `obj+0x18 == 3` and
`obj+0x11A` arming to 6 match manual guard entry per §0.7, and the driven
input is `DOWN` = `0x02` (§0.5 run 6 input-bit table above).

| hold | lock (`obj+0x11A`) armed | flag/state on | button released | flag/state off | frames button-up → off |
|---|---|---|---|---|---|
| 1 frame (tap) | +3 | +4 | +1 | +11 | 10 (lock reaches 0 at +9, then +2 — matches the lock-gated prediction exactly, 6 frames later than a pure-latency prediction of +5) |
| 5 frames | +3 | +4 | +5 (1 frame after flag turned on) | +11 | 6 (entry lock had 4 frames left at release, reaching 0 at 309, then clearing 2 frames later at 311) |
| 30 frames | +3 | +4 | +30 | +34 | 4 |
| post-block (guard held well past the lock's drain, then released 10 frames after a real blocked hit) | — (already drained) | — (already on) | block+10 | block+13 | ~2–3 (chunk-boundary uncertainty in the adaptive driver used to catch the stochastic CPU's attack — see the RESULTS.md method note; not frame-exact like the other three rows) |

Owner testimony, 2026-09-12 (`jus-atns.3`): guard-release delay is short and
consistent across characters; Yusuke can use his fast neutral B near-immediately
after release. No exact frame count was supplied. The measurements below track
guard flag/state clearing, not the earliest accepted attack input. `jus-atns.5`
tracks those separately with continuous-plan cross-character captures. See the
[owner clarification](../research/findings/owner-feel-scope-2026-09-12.md).

**Rules (PLAUSIBLE, four hold lengths; one post-block point):**

1. **No 122-frame CPU-style hold applies to a human release — settled for
   both the no-incoming-hit case and the post-block case.** The flag/state
   cleared within a few frames to low-double-digit frames of the button
   going up in all four runs — nowhere near the CPU's 122-frame
   hold-after-last-block (§0.5 rule 4). That value is CPU-AI behavior
   scripted into the "-guard" savestates, not a property the guard-state
   machine also applies to a human, blocked or not.
2. **Lock-gated rather than purely latency-based — superseded 2026-09-14b
   (`jus-atns.5`, round 2).** The 1-frame tap rules out the pure-latency
   model by 6 frames (press+11 observed, press+5 predicted), but on its
   own did not separate "the flag waits for the guard-entry lock" from
   "guard has a ~7-frame minimum duration from flag-on": the lock arms at
   a fixed offset from guard entry, so both models predict press+11 for
   the tap and for the 5-frame hold. The discriminating test proposed
   here — a live poke overwriting the lock instead of waiting for an
   auto-guard entry to do it — has now been run on Kakashi (see the Round
   2 section below): forcing the lock to 12 delays clear by exactly the
   extra drain time, forcing it to 0 early advances clear to match, on 6
   trials with no exceptions. **Lock-gated wins; the flat minimum-duration
   alternative is refuted for Kakashi.** This is a mechanism confirmation
   for Kakashi specifically (one fixture, one session, poke-causal).
   **Superseded 2026-09-14b/c (`jus-atns.5`, rounds 2-3): the mechanism
   has since been shown poke-causal for Yusuke too** (round 3,
   byte-identical `lock_arm+14`/`+3` poke deltas, though Yusuke's own
   poke session is n=1 per direction plus a control, not Kakashi's 3+3
   both ways); it has not been poked for Kenshin (only the unpoked
   `lock_arm+8`/`+31` formula was reproduced there) — see item 2 of the
   Round 2 section below and the Round 3 section's Kenshin bullet.

   Across all four runs the clear frame is
   `max(lock_reaches_0 + 2, button_up + 4)`: the tap and the 5-frame hold
   are governed by the first term, the 30-frame hold and the post-block run
   by the second.
3. **New (2026-09-12b): a human who has just blocked does not inherit the
   CPU's hold either.** With CPU aggression enabled (`COM設定 → 戦う`, this
   time confirmed by `jusemu.py screendump` before and after the menu edit —
   the first session's screenshot-less attempt could not confirm this took
   effect), a real blocked hit landed on P1 (`M+0x40 |= 0x1000`, gauge
   `obj+0x102` +4) while P1 held guard, and releasing 10 frames after that
   block cleared the flag 13 frames after the block — the same order of
   magnitude as the no-incoming-hit cases, not 122 frames. The exact
   release-to-clear count here is noisier than the other three rows (an
   adaptive multi-call driver was needed to catch the CPU's non-deterministic
   attack timing, and the bridge reverts input to neutral between separate
   `run` calls, adding a few frames of boundary uncertainty at the release
   edge) — see the RESULTS.md method note for the full accounting. The
   qualitative finding (not 122 frames) does not depend on that precision.

**Positive controls.** 2026-09-12, P2/Luffy side, fresh addressing: a blocked
Kenshin B jab set `M+0x40 |= 0x1000` and moved the gauge from 0 to 5 —
reproducing §0.5 rule 1's documented block cost before the P1-side timing
above was trusted. 2026-09-12b adds the reverse-role control needed for the
post-block run: a Luffy hit landing on P1 (Kenshin, the guarder this time)
also set `M+0x40 |= 0x1000`, with the gauge rising 4→8 (+4, a different
move's damage than the +5 control, as expected) — same mechanism confirmed
from both attacker and defender roles.

Auto-Guard with an empty SP pool (gap 8 below) remains untested. The first
session found no savestate in
[`jus_files/save_states/INDEX.md`](../../jus_files/save_states/INDEX.md)
carrying an Auto-Guard (ability 4) carrier as the active koma by a name match
against [`../research/Passives-Reference.md`](../research/Passives-Reference.md)
line 188 and
[`../research/Helper-Passives-Catalog.md`](../research/Helper-Passives-Catalog.md)
line 140, matching an earlier session's independent conclusion
(`../research/feel-captures/sp-live-2026-09-12/SUMMARY.md`,
"Auto-Guard leg — not run"). **2026-09-12b adds a direct runtime check**: 8
savestates with varied P1 characters had both fighters' ability bitset
(`obj+0x128`) read live and bit `0x10` was clear on all 16 reads
(`../research/feel-captures/guard-2026-09-12b/RESULTS.md`
§4) — the same conclusion, now from reading the bit itself rather than
inferring from a character-name list, still over a sample rather than the
whole roster.

| P1 / P2 | P1 `obj+0x128` | P2 `obj+0x128` |
|---|---|---|
| kenshin / luffy | `0x6` | `0x2005200` |
| momotaro / nami | `0x600` | `0x1010008` |
| yusuke / nami | `0x0` | `0x1010008` |
| taikoubou / jotaro | `0x0` | `0x2000` |
| kakashi / jotaro | `0x2004` | `0x2000` |
| muhyo / jotaro | `0x1000000` | `0x2000` |
| sasuke / jotaro | `0x2004` | `0x2000` |
| eve / jotaro | `0x1000002` | `0x2000` |

Caveat: this is not 16 independent samples — five Jotaro P2 reads share one
deck (`0x2000`) and two Nami reads share another (`0x1010008`); Auto-Guard
comes from helper koma, so the deck is the real sampling unit, not the
fighter read — roughly 6 P1 decks and 3 P2 decks, not 16.

### Extension (2026-09-14, `jus-atns.5`): Kakashi, and earliest-accepted-attack

`jus-atns.5` extends the Kenshin-only rows above with Kakashi, using a new
GDB probe (`scripts/gdb/atns5_guard.gdb`) that reads P1/P2 off the fighter
table instead of hardcoded addresses, plus B-attack acceptance/hitbox
tracking the Kenshin session above did not attempt. Evidence:
guard-release-attack-2026-09-14/RESULTS.md.
Does not reopen the Kenshin rows above.

**Basis note (corrects a Refuter-caught error in this extension's first
pass).** The rows in this extension were first measured on the new
probe's own input-WORD edge (`obj+0x6c`, sampled at the `0x02082E10`
integrator entry) — a different basis than the table above, which is on
the plan's button press. The two are a fixed 2 frames apart: RESULTS.md's
`B_standalone` trial shows the word edge at frame 81 and the state commit
to 9 at frame 82, and kakashi.md §0 documents that commit as `press + 3`
on the plan basis, so the plan-basis press was frame 79 — 2 frames before
the word's own edge. **Every offset below is now given on the plan basis
(word-basis + 2), plus a basis-free `lock_arm` column**, so this table is
directly comparable to the Kenshin rows above.

| character / hold | lock-arm → clear (basis-free) | flag/state clear (plan basis) | model `max(lock0+2, button_up+4)` | matches? |
|---|---|---|---|---|
| Kakashi, 1-frame tap | **lock_arm+8** | **button_up+9** | max(+9, +4) = +9 | yes, exactly |
| Kakashi, 30-frame hold | **lock_arm+31** | **button_up+3** | max(≈0, +4) = +4 | close — measured +3, one frame under the model's +4 floor |

**Kakashi equals Kenshin on both rows, once both are read from lock-arm.**
Kenshin's own rows above give `lock_arm+8` for the tap (lock armed at
`press+3`, flag off at `press+11`) and `lock_arm+31` for the 30-frame hold
(lock armed at `press+3`, flag off at `press+34`) — identical to Kakashi.
**The earlier "+4 floor is refuted for Kakashi" claim in this section is
retracted**: it compared a word-basis number against the model's
plan-basis floor and reported a 3-frame gap that was a basis-mismatch
artifact, not a real per-character difference. The actual gap, once both
sides are on the plan basis, is 1 frame (+3 measured vs. +4 modeled) —
whether the model's floor should read `+3` is a small, character-neutral
open question, not evidence Kakashi behaves differently from Kenshin.

Also downgrading an earlier overclaim, itself now **superseded 2026-09-14b
(`jus-atns.5`, round 2)**: this round's own extension did not separate
lock-gating from a flat minimum-duration for Kakashi (its tap holds state
3 for exactly 7 frames, consistent with both models), so it should not
have been read as confirming "lock-gated" at the time. The discriminating
test rule 2 proposed (a live lock poke in place of waiting for an
auto-guard entry) has since been run — see the Round 2 section below and
rule 2 above: lock-gated is now confirmed for Kakashi.

**Earliest accepted attack = clear frame: CONFIRMED on three characters
(superseded 2026-09-14b/c, `jus-atns.5` rounds 2-3 — no longer
"Kakashi-only" / "bracketed").** On Kakashi, Yusuke, and Kenshin alike, a
B pressed strictly before the flag-clear frame is **dropped** (state
never reaches 9, no buffering observed); a B pressed AT or after
flag-clear is accepted, with the state transition to 9 landing exactly
`press+3` later on the plan basis (this matches kakashi.md §0's own
"press+3" state-commit convention by construction, since both numbers now
share a basis). So the earliest accepted attack input is the flag-clear
frame itself — not earlier, and not detectably later once press timing is
controlled for. `B_standalone` (no guard at all) also showed this same
`press+3` latency, so it looks like a general input-processing constant,
not something guard-specific. The tap boundary is now measured exactly
(not merely bracketed) on all three characters: Kakashi `k=6` dropped /
`k=7` accepted on the clear frame / `k=8` accepted (round 2); Yusuke's
full grid `k=5,6` dropped / `k=7` accepted on the clear frame / `k=8,9`
accepted (round 3, D2); Kenshin `k=6` dropped / `k=7` accepted on the
clear frame / `k=8` accepted (round 3, E).

**Cross-character sharing (guard-clear/acceptance) — established; B
startup speed — not shared.** **Superseded 2026-09-14b (`jus-atns.5`,
round 2):** the brief's Yusuke calibration case (L-switch from Taikoubou
on `pc-taikoubou-npc-jotaro-dark-tournament`) had no positive-control
confirmation of the switch itself at the time this paragraph was
written (neither `hp1` nor an attempted `chr_b`/active-roster-slot read
confirmed it took effect — RESULTS.md §4 has the detail); that identity
has since been verified — see the Round 2 section below and its item 3.
But the earlier claim that "every measured quantity came back numerically
identical" to Kakashi does not hold once the hitbox-detector bug below is
fixed: guard-clear and acceptance timing ARE identical (`lock_arm+8`/
`+31`, `press+3` acceptance, dropped-until-clear), but **first-hitbox
timing is exactly half** — `accept+4` for the taikoubou fixture (9/9
trials) vs. `accept+8` for Kakashi (13/13 trials), zero overlap over 22
trials. That was strong circumstantial evidence the taikoubou fixture's
P1 is not Kakashi and has a materially faster B, consistent with the
owner's "fast Yusuke B" testimony (`jus-atns.3`); with identity now
verified, it is a confirmed 2x speed difference rather than
circumstantial evidence (Round 2 section, item 3).

**First active hitbox and first contact — measured (a detector bug, not a
missing measurement).** The probe's attempt to isolate P1's own attack
hitbox by ownership found `wrap+0x18` does NOT equal the fighter-table
object pointer (that hypothesis is refuted, live-checked) — but the
original "first non-empty ids" detector had a separate bug: it returned
the first frame with ANY non-empty id, including one persistently-live id
(`6`, almost certainly a standing body/hurtbox record) present before
every attack, so it always reported baseline noise, never the actual
hitbox. Fixed by baselining the ids already live at/before the reference
frame and reporting only a genuinely new one (id `256`, kakashi.md's
documented B hitbox id, appears reliably once fixed). Re-run over the
same committed logs: Kakashi's first hitbox = `accept+8` (13/13 trials);
the taikoubou fixture's = `accept+4` (9/9 trials); first contact = `accept
+7` on the taikoubou fixture (3 trials; Kakashi's own fixture never
reaches contact range). See RESULTS.md §3 for the full accounting;
postblock captures and the Kenshin control were still skipped this session
for time, per RESULTS.md §5.

### Round 2 (2026-09-14b, `jus-atns.5`): tap boundary measured exactly, lock-gating CONFIRMED for Kakashi, Yusuke identity VERIFIED

Evidence:
guard-release-attack-2026-09-14b/RESULTS.md.
Reuses the same probe (`scripts/gdb/atns5_guard.gdb`) and driver
(`scripts/analysis/atns5_guard_run.py`), extended (not rewritten) with a
reactive lock poke for the discriminator below and a `GdbSession.extra_ex`
hook to select it per attach.

1. **Tap boundary, measured exactly.** `k=7` (press lands exactly on the
   flag-clear frame) is accepted, closing round 1's own bracket (`k=6`
   dropped, `k=8` accepted, `k=7` untested).
2. **Rule 2 answered: lock-gated is CONFIRMED for Kakashi (`jus-atns.5`),
   not a flat minimum duration. Superseded 2026-09-14c (`jus-atns.5`
   round 3): now
   CONFIRMED for Yusuke too** (see item 3's round-3 update below) —
   the mechanism, not just the `clear = lock0+2` formula, has been shown
   poke-causal on a second character with byte-identical deltas
   (`+14`/`+3`). Kenshin's own control was not poked this round (only
   the unpoked `lock_arm+8`/`+31` formula was re-measured on Kenshin —
   see item 3), so lock-gating is CONFIRMED for two characters
   (Kakashi, Yusuke) and the formula alone (not yet the poke-causal
   mechanism) is CONFIRMED for a third (Kenshin), `jus-atns.5`. A GDB
   poke overwrites the guard-entry lock — 12 instead of 6, on the same
   frame it is observed to arm — and clear moves **exactly 6 frames
   later** on all 3 tested `k` values (the extra drain time a lock of 12
   needs vs. 6; the minimum-duration model predicts no change and is
   refuted). The mirror poke — lock forced to 0 one frame after arm —
   advances clear to `lock_zero+2` on all 3 tested `k` values, far
   earlier than the unpoked `+7`; the same model term jus-rsye's Kenshin
   rows already use, now shown causally rather than just fit to unpoked
   data. Both directions also flip acceptance for a `k` on the wrong side
   of the unpoked boundary (`k=8` flips accepted→dropped under the delay
   poke; `k=2` flips dropped→accepted under the early-clear poke) — an
   independent confirming signal on top of the raw clear-frame shift. Six
   trials, zero exceptions. (A first pass at this discriminator reused
   one GDB attach across three `k` trials and found only the FIRST trial
   was actually poked — a GDB convenience-variable latch that a `state
   load` does not reset; fixed in `atns5_guard.gdb` by resetting the latch
   whenever P1 returns to idle, and re-run clean.)
3. **Yusuke identity VERIFIED, scope-limited (`jus-atns.5`).** The only
   committed artifact is `logs/yusuke_verified_summary.json`'s
   `identity_check` object, `{"slot2_active": 1, "slot2_chr_b": 32}` — one
   `jusemu.py peek` of the P1-side roster-slot array at `0x021DF1D4 +
   0x50*i`, decoded at slot 2 (`+0x25` bit 0 = active, `+0x29` = `chr_b`)
   after the L-tap, out-of-band, with no before/after comparison and no
   read of slot 0 or slot 1. That is: **slot 2 is active with `chr_b=32`
   after the L-tap** — matching the fixture's documented deck entry for
   Yusuke — not a three-slot dump, and not independently re-read inside
   a GDB session (an earlier pass of this document additionally reported
   a `slot0`/`slot1`/`slot2` triple with hp values that matches no
   committed log and has been retracted; RESULTS.md §3 has the detail).
   A 3-trial spot-check (`B_standalone`, `tap_B_k7`, `hold30_B_k1`)
   reproduces round 1's `accept+4` first-hitbox timing exactly on all 3 —
   **first-hitbox startup speed is now a confirmed 2x-faster-than-Kakashi
   measurement (`accept+4` vs. Kakashi's `accept+8`), not "strong
   circumstantial evidence"** — scoped to that one measurement, not a
   general "Yusuke's B is 2x faster" claim. **Superseded 2026-09-14c
   (round 3): the full 9-trial grid was run** (5 tap `k` values, 4 hold30
   `k` values) — every trial gives `clear = lock_arm+8` (tap) /
   `lock_arm+31` (hold30), byte-identical to Kakashi, with the same
   drop/accept boundary shape (tap drops through `k=6`, accepts from
   `k=7`; hold30 drops at `k=0`, accepts from `k=1`). **Yusuke's own
   lock-poke discriminator was also run this round**: `->12` at arm gives
   `clear = lock_arm+14`, `->0` at arm+1 gives `clear = lock_arm+3` —
   both byte-identical to Kakashi's own round-2 poke deltas. Cross-
   character sharing of the lock-gating MECHANISM (not just the formula)
   is now **CONFIRMED for Yusuke** (`jus-atns.5`), not PLAUSIBLE (round-3 evidence,
   guard-release-attack-2026-09-14c/RESULTS.md
   §D2).
4. **Correction 2026-09-22 (`jus-wmqi.2`, Round 5 below): this item's
   "Kakashi" trials ran on `pc-kakashi-npc-jotaro-fightcpu`, which loads
   with Muhyo active, so they were almost certainly Muhyo.** The original
   text follows.
   **Round 3 (2026-09-14c): Kakashi post-block measured, Kenshin control
   run, Yusuke bridge slot promoted.** Evidence:
   guard-release-attack-2026-09-14c/RESULTS.md.
   - **Kakashi post-block — SUPERSEDED by the round-3 fix-pass: this was
     never a post-block release measurement.** `plans/c1_kakashi_postblock.py`
     built its release-and-press plan as `hold_more = max(0, ...)`, and
     in all 7 committed trials the block-polling loop's own 15-frame
     chunks had already overshot the release target, so `hold_more == 0`
     and no `DOWN` was ever driven and released after the block — the
     reported "release" was the polling chunk expiring, not a driven
     post-block release. What was actually measured: a ~14-frame guard
     (from its own last lock-arm) that clears on the ordinary hold30
     schedule (`lock_arm+15` on 6/7 trials, `+16` on `k=4` with one
     sampling gap) and accepts every `B` because each one landed 16+k
     frames after release (see below), not because of anything
     block-specific. **Post-block release itself stays OPEN, unmeasured**
     (RESULTS.md §C1 has the corrected accounting) — **superseded by
     item 5 below (round 4, 2026-09-14d): post-block release is now
     measured on Yusuke and on Muhyo (logged as Kakashi; see the
     correction at the top of this item).**
   - **The `k+16..k+22`-frame delay is the documented per-`run`-call IPC
     warm-up, not an undiagnosed new hypothesis.** Because `hold_more ==
     0`, the `B` press was the first input of a brand-new `jusemu run`
     call, which incurs the ~15-16-frame subprocess/IPC warm-up already
     documented in `cancel_run.py`'s `Runner.run_one` docstring and
     `atns5_guard_run.py`'s own `run_one` (both cited in RESULTS.md §C1).
     Fixed in `plans/c1_kakashi_postblock.py` by forcing `hold_more >= 1`
     so `B` is never that call's first input, ready for the next live
     round to reuse.
   - **Kenshin control** (`pc-kenshin-npc-luffy-dark-tournament`, `tap_B_k`
     for `k` in `{6,7,8}`, `hold30_B_k` for `k` in `{0,1,2}`): matches
     `lock_arm+8`/`lock_arm+31` exactly, same drop/accept boundary shape,
     zero exceptions — a **third character** confirming the shared
     formula (see item 3's update above), reconciling cleanly with
     jus-rsye's original Kenshin numbers once the basis is made explicit
     (RESULTS.md §E has the full reconciliation).
   - **Yusuke fight-CPU bridge slot**: promoted (`pc-taikoubou-npc-jotaro-
     fightcpu`, same COM設定 dance as the Kakashi bridge slot) and
     identity re-verified with a full 3-slot peek (not just slot 2, per
     the round-2 Refuter's own finding) — slot 0 Taikoubou/inactive, slot
     1 Momotaro/inactive, slot 2 Yusuke/active, matching the deck exactly.
     **This peek is on the fightcpu bridge slot only.** The D2 grid and
     lock-poke sessions above ran directly against
     `pc-taikoubou-npc-jotaro-dark-tournament` (the idle-CPU fixture, a
     different savestate) with no identity read of their own — their
     identity rests on round 2's argument (same fixture, same `L`-tap as
     round 2's verified peek, deterministic reload), not on this peek.
     **Post-block timing on Yusuke was explicitly skipped**: re-running
     the same broken chunked-driver method that produced the Kakashi
     post-block's inconclusive boundary would spend budget reproducing a
     known gap rather than answering anything new.
5. **Correction 2026-09-22 (`jus-wmqi.2`, Round 5 below): the fightcpu
   fixture loads with Muhyo active, so this round's "Kakashi" leg
   (including "block at local frame 184", the `accept+10` trials and the
   k1 boundary pair) was almost certainly Muhyo. Read "Kakashi" in this
   item as Muhyo. The release rule still holds. Real Kakashi's post-block
   clear was measured in Round 5 (release + 3, plan). His k=0/k=1
   post-block boundary is unmeasured: Round 5 pressed B only at release
   +2/+4/+6 (tracked in `jus-wmqi.7`).** The original text follows.
   **Round 4 (2026-09-14d, `jus-atns.5`): post-block release MEASURED on
   both Kakashi and Yusuke — CONFIRMED, and it is the SAME plan-basis
   floor as tap/hold30, not a faster constant.** Evidence:
   guard-release-attack-2026-09-14d/RESULTS.md.
   The round-3 fix (`hold_more = max(1, ...)` so `B` is never a fresh
   call's first input) turned out to be insufficient on its own: the
   brief's own chunked-poll-then-one-combined-call method was tried
   first and found to let the guard fully clear and reset to idle in the
   real-time gap BETWEEN the polling loop's last chunk and the follow-up
   combined call — the bridge reverts input to neutral between separate
   `run` calls, and the emulator keeps running in real time during that
   gap, long enough (~15-25 frames, live-observed) to fully drain and
   reset a post-block guard before the "sustained hold" call ever
   starts. **Fixed by dropping the chunked-polling phase and driving
   each whole trial as ONE single, uninterrupted `run` call**, sized in
   advance from a per-character calibration run (a single continuous
   300-frame `DOWN` hold with no `B`, which confirmed `in_down` tracks
   the plan's `DOWN` segment with no lag at the segment's own start —
   this does NOT mean the release edge is lag-free too, see the basis
   note below). Kakashi's block lands deterministically at local frame
   184; Yusuke's first block at local 61 (a second block lands at local
   108, close enough to land inside some k-trials' own holds — see the
   Yusuke leg caveat below). **Result on both characters, 6 `k` trials
   each, zero gaps in any hold: `flag_clear = button_up + 1` on the
   probe's input-word basis** — the same basis every earlier round's
   `button_up` used, not plan-basis. **`clear = max(lock_reaches_0 + 2,
   button_up + 3) on the plan basis, for tap, 30-frame hold and
   post-block release alike, three characters (Kakashi, Yusuke,
   Kenshin), jus-atns.5 rounds 1–4. Round 4's post-block logs read
   flag_clear = button_up + 1 on the probe's input-word basis; the word
   lags the plan frame by 2, so +1 word = +3 plan.`** There is no new,
   faster post-block-specific constant to separate from a lock-drain
   alternative — the model holds. The QUALITATIVE rule — nothing
   accepted before the clear frame, everything from the clear frame on
   accepted — is confirmed for post-block exactly as it already was for
   tap/hold30: the earliest accepted `B` is exactly the clear frame
   (`k=1`, i.e. release+1 on the word basis) on both characters; `k=0`
   (press on the release frame itself) drops on both; `k=2..6` all
   accept, landing `accept = b_press+1` uniformly.
   **Resolved 2026-09-22 (see the correction at the top of this item):
   the `+10` below is Muhyo's; Kakashi is `accept+8` on both fixtures.**
   **Also this round: the `accept+10` (Kakashi fight-CPU fixture,
   post-block) vs. `accept+8` (Kakashi idle fixture, no block) `id 256`
   discrepancy remains OPEN, not closed** — every `+10` trial on record
   (this round's 5 plus round 3's C1 6/6) had an earlier CPU block in
   the same run on the `fightcpu` fixture, and every `+8` trial is on
   the idle fixture with no block, so fixture identity and the
   post-block condition are fully confounded, not separated. **Yusuke's
   own first-hitbox id (`259`) is anchored to the CPU's first block
   (lands at `first_block+59` in every trial including the dropped
   `k=0`), not to Yusuke's own release/accept timeline — it is NOT
   Yusuke's B attack hitbox; that hitbox id on this fixture remains
   unidentified.** **A second live bug caught and fixed before trusting
   any Yusuke trial:** the roster-slot identity decode used the wrong
   stride (`0x30`) and read garbage for slots 1/2; re-deriving the
   correct stride (`0x50`) from round 3's own committed raw peek and
   re-decoding this round's already-captured peek with it gives the
   expected identity cleanly (slot 2 Yusuke/active) — no new peek was
   needed. **The Kakashi hold30-no-block-on-fightcpu control is
   INVALID, not a surprise:** direct log check shows P1 sitting in
   `state=8` for the fixture's own ~79-frame post-load non-actionable
   window (local frames ~56-134) for the entire plan, never reaching
   guard (`state=3`) or accept (`state=9`) at all — rerun with the hold
   starting after local ~70. **A boundary-case flag disagreement:**
   Kakashi k1 and Yusuke k1 (the two trials where `B` lands ON the clear
   frame) show the STATE clearing guard one frame before `M+0x78` bit 26
   does (Kakashi 281 vs. 282; Yusuke 160 vs. 161) — Kakashi k2 shows the
   bit clear WITH the state, then flip back to 1 on the same frame the
   `B` press lands, before clearing again — read together, acceptance is
   gated by the STATE clear frame, not bit 26 (PLAUSIBLE, n=2 boundary
   trials).

### Round 5 (2026-09-22, `jus-wmqi.2`): the accept+10 confound is a fighter mix-up

Evidence:
wmqi2-guard-2026-09-22/RESULTS.md.
The probe now logs the input word, the active roster slot and chr_b on
every frame, and the screenshot HUD was checked on every trial.

- **`pc-kakashi-npc-jotaro-fightcpu` loads with P1 slot 1, Muhyo
  (chr_b 59), active.** Kakashi is slot 0 and benched. `jus-n4io` saw the
  same thing on 2026-09-16. Rounds 3 and 4 did not log the active slot, so
  their "Kakashi" fightcpu trials (round 3 C1, round 4's post-block leg,
  including the k1 boundary pair above) were almost certainly Muhyo
  (inferred: same state file, and every load today has Muhyo active).
- **First hitbox after accept is per fighter.** Kakashi: `accept+8`, 3
  rows (10/10 trials: idle fixture, fightcpu with Kakashi touched in, no
  guard, guard without a block, and post-block). Muhyo: `accept+10`, 4 rows
  (5/5 trials, fightcpu only: no guard, guard without a block, and
  post-block after a different hold, DOWN from plan 0 with three block
  bursts). Both are element id 256 on record 11. Within each fighter,
  guard and a prior block change nothing.
- **The release rule still holds, now on real Kakashi after a block.**
  Kakashi held DOWN plan 150..271 with a block at plan 244. Clear came at
  275 = release + 3 (plan). B at 274/276/278 was accepted at press + 3.
  Muhyo's post-block clears are also release + 3. Nothing here reopens the
  rule. It only swaps which fighter round 4's post-block point belongs to.
  **Not measured:** real Kakashi's post-block k=0/k=1 accept boundary. B
  was pressed only at release +2/+4/+6 (tracked in `jus-wmqi.7`).
- **Guard entry from idle:** state 3 and bit 26 go live at DOWN press + 3
  (plan). The lock arms at press + 2 (the DOWN word-edge row). 10/10
  trials.

---

## 1. What is confirmed: the apply machinery

### 1.1 The clamp-accumulator gauge primitive

One reusable gauge shape, `{+0x16 max (s16), +0x18 current (s16)}`, units 1/64
(raw `0x4000` = 256.0 displayed), with three arm9 accessors:

| addr | name | behaviour |
|---|---|---|
| `0x02078488` | Grow / ApplyDeltaToCurrent | clamped add into `[0, max]` |
| `0x020784B8` | GrowMax | raises max, capped at `0x4000` |
| `0x020784E4` | IsCurrentBelowPercentOfMax | both known callers pass `pct=25` |

Sources: [HP-Struct-From-Disassembly.md](../research/HP-Struct-From-Disassembly.md),
[findings/p173-char-0x56c-is-the-character-struct.md](../research/findings/p173-char-0x56c-is-the-character-struct.md),
tracker item `jus-hp-block-at-char-0x56c-q86`.

**Warning — do not resurrect the "it's a separate gauge" reading.** P172 floated
that the struct behind `char+0x56C` was a guard/SP gauge rather than HP. **P173
retracted that**: `char+0x56C` points at the character struct and `+0x16`/`+0x18`
are max/current HP; status id 19's −4 drains *current HP*
([p173](../research/findings/p173-char-0x56c-is-the-character-struct.md)). Any
guard/SP gauge instance must therefore live somewhere *other* than `+0x56C`.

### 1.2 Trampolines into the gauge

- **Fill trampoline `0x020783CC`**: loads `r0` from `[char+0x56C]`, tail-jumps into
  Grow. All **8** static call sites enumerated (ov6, unconditional `bl`):
  `0x02157DC0`, `0x021582C4`, `0x02158BC0`, `0x02159274`, `0x021592D0`,
  `0x0215952C`, `0x02159668`, `0x0215A318`
  (Battle-Engine-Map §guard-sp-gauges claim 1, CONFIRMED_STATIC).
- **Drain trampoline `0x020783B8`**: same `+0x56C` target, but negates the delta
  (`rsb r1,r1,#0`) first; caller ov6 `0x0215AC70`. Found only by a manual byte
  sweep — both trampolines jump via `bx ip` through an inline pool word, which
  `xrefs-to`/`pool-values` cannot see (claim 8). A reimplementer's takeaway:
  every "N callers" count in this subsystem is a floor, not a census.
- Deltas at the trampoline boundary are only ever scaled by **constant powers of
  two** (`lsl #6`, `lsl #8`, or unscaled) — there is **no chain-length or other
  non-constant damage scaling anywhere in this subsystem** (P157–P159,
  CONFIRMED_STATIC). Different opcodes deliberately take different units
  (×64 = ids `0x25`/`0x26`, ×256 = `0x27`–`0x29`, unscaled = id `0x04`).
- `0x02078428` sets HP to exactly **1** on every living character when called
  with `r1 = 0` (P157).

### 1.3 The `+0x558` meter-node list (the guard/SP candidate)

The **walker `0x020783DC`** is fully decoded (claim 11, CONFIRMED_STATIC):

- loads a list head from `char+0x558`;
- per node: skips if `node+0x40` (byte) or `node+0x3C` bit 0 is set — generic
  enable/pause gates, *not* a type discriminator (claim 12);
- calls `Grow(node, delta)` on unflagged nodes;
- advances via `node+0x00` (next pointer).

Exactly 2 static call sites reach the walker (`0x02157E0C`, `0x021592B4`).
`char+0x558/+0x55C/+0x560/+0x564` are zero-initialized together in one startup
loop at `0x02075FF8`–`0x02076008` (claims 13–14).

Headline negative result (spec B12): **no second *fixed* struct offset feeds
Grow/GrowMax anywhere in the enumerated call graph** — every path resolves to
`+0x56C` (HP) or to a dynamic `+0x558` node. So the `+0x558` list is the leading
candidate for guard-health/SP meters. Held at plausible, not confirmed: the
sweep that produced it is demonstrably non-exhaustive (it missed the drain
trampoline; claims 7/8/10).

### 1.4 The SP total and the live SP-apply path

- **SP total is a word at `player_slot+0x5C8`**, reached from a character as
  `[[char+0x1B4]+0x5C8]`. `char+0x1B4` is one of four `0x61C`-byte player slots
  starting at ComicDeck`+0x64`
  ([char-0x1b4-is-a-comicdeck-player-slot.md](../research/findings/char-0x1b4-is-a-comicdeck-player-slot.md)).
- **Runtime-confirmed 2026-09-03** (`jus-kakashi-moveset-map-33lu` phase 2,
  `docs/confirmed-facts/characters/kakashi.md`), **corrected 2026-09-12**
  (`jus-e2h3`, live re-measurement after a Refuter FAIL on an earlier
  correction attempt, commit `c1418c6`): **the `[[obj+0x1B4]+0x5C8]` chain
  is correct as written above — there is no offset and no need to derive
  the slot from the HP record.** P1's fractional SP pool word is
  `0x021DF72C` = player slot `+0x5C8`, with the slot itself at
  `0x021DF164` = `[obj+0x1B4]` (P2: slot `0x021DF780`). Two adjacent
  signed bytes at `slot+0x5CC`/`+0x5CD` (`0x021DF730`/`0x021DF731` for P1)
  are the max-bars/current-bars pair `m`/`c`, not part of the pool; a
  32-bit read starting at `+0x5CC` (i.e. at `0x021DF730`) — the mistake
  the 2026-09-03 pass and the first, failed 2026-09-12 correction both
  made — reads `m|c<<8` and looks like a plausible pool value by
  coincidence (Kakashi's baseline: `m=9, c=9`, misread as pool `0x0909`).
  Every Kakashi 4-koma special **spends one bar** (`c -= 1`) on its first
  frame, through a previously uncatalogued wrapper at `0x0207834C` calling
  the documented bar-borrow helper `0x0207830C`; refused when `c == 0`
  (never enters state 10, no trace). Landed normals (B 8.0, Y 24.0) add
  nothing to `c`, and `c`/`m` do not tick up over 900 idle frames — but
  `0x020781E4` itself *does* fire during the special with small per-hit
  gain amounts landing in the fractional pool `x`, so "adds nothing" is a
  bar-count statement, not evidence that the pool never gains. SELECT
  costs nothing. How SP is gained at the bar level is still open
  (`jus-b3k2` neighbourhood; the combat notes §13).
- **SP gain model, PLAUSIBLE (not CONFIRMED), `jus-e2h3`, live re-run
  2026-09-12** (finding doc:
  [sp-apply-0x020781E4-is-a-mixed-radix-pool-with-bar-count.md](../research/findings/sp-apply-0x020781E4-is-a-mixed-radix-pool-with-bar-count.md),
  "Live confirmation (re-run)"): the pool `x`, bar count `c`, and max
  bars `m` are as in §1.4 above; one bar `= 0x6400` (`100.00` in `1/256`
  units), confirmed live by the carry `x = 0x5DCC` + `5120` -> `c: 2 -> 3`
  -> `x = 0xDCC` (finding doc, "Live confirmation (re-run)"). A special
  costs one bar through the `0x0207834C` wrapper into the bar-borrow
  helper `0x0207830C` (`c -= 1`). The wrapper skips the charge and returns
  success when either free-pass byte `slot+0x5CE`/`slot+0x5CF` is
  nonzero; `+0x5CF` does double duty — free spend at the wrapper, and
  refusal of negative deltas inside `0x020781E4`. **Gains are
  deposit-and-payout, not per-hit**: a hit that connects or is absorbed by
  guard, and a special, each make one deposit into a pending cell
  (evidence: `pc-kenshin-luffy-guard` RESULTS §Result: identical
  `2560`/`3840` pair on three B presses, only the first of which dealt HP
  damage). `0x0215FFA0` pays a pending `u16` cell into `x` via
  `0x020781E4`, then halves the cell (`asr #1`),
  clearing it once it drops below `0x100`. A deposit `D` pays `D, D/2,
  D/4, D/8, ...` across ticks until the remaining half falls under
  `0x100`, for a total just under `2D`.
  - Two deposits were measured, for Kenshin's B jab (336 raw damage,
    `pc-kenshin-luffy-guard`) and for the Kakashi 4-koma X special in a
    different state with no damage figure recorded — so "not
    damage-scaled" rests on the two moves differing in damage, not on a
    shared measured damage value: **`3840`** (`15.00`) into the
    attacker's slot, paying out `3840 + 1920 + 960 + 480 = 7200` (`28.125`)
    when the gauge has headroom; **`2560`** (`10.00`) into the victim's
    slot, paying out `2560 + 1280 + 640 + 320 = 4800` (`18.75`) when the
    gauge has headroom. A third deposit amount, `1024` (`4.00`), was seen
    once on both slots in the guard run (`pc-kenshin-luffy-guard`) --
    now attributed to two independent sources, `+0x5C->+0x68` on the
    attacker and `+0x60->+0x6C` on the victim (see the deposit-writer
    bullet below).
  - **Clamp when full, on any add**: whenever `c >= m` at the moment of an
    add, the tail forces `x = 0` for that tick — observed
    on every payout tick of a full-gauge slot this session (the victim
    side above never showed `x` move even though the deposit and its
    decay chain both fired).
  - **Explicitly unmeasured**: the per-move/per-ability deposit table
    (what deposit each move or ability produces — the two measured moves
    share a basis that is move- or event-typed, not yet resolved); and
    the negative/spend-debit path at `0x0215AC64`
    (`amount = -(u32[[obj+0x1A8]+0x10]+0x138)`, read as zero in every run
    across both this session and the `jus-36wu` follow-up below, so no
    nonzero debit or refusal has ever been observed live). **Part B
    rerun, `jus-1bkw`, 2026-09-14**: found the bar-count byte itself
    (`s8[slot+0x5CD]`) drop twice live, neither through `0x0215AC64`
    nor through `0x020781E4` (added as a fallback breakpoint this
    session) — both stayed at `amount=0`/positive-only the whole
    session. **The enumeration of `0x020781E4` callers is not just the
    two sites already instrumented**: this session's `lr` breakdown on
    the `SPAPPLY` fallback breakpoint found a third live site,
    `0x2157dd4` (return address of the static caller list's
    `0x02157DD0`), firing 3 times (`amount=+256` at frames 964/976/988)
    — instrumented this session, still untraced beyond that. A
    same-frame correlate for the debit itself was also found, one tick
    *before* the drop becomes visible in the heartbeat, not on the same
    tick: `Q2_GATE64` idx `13` (`lr=0x21577d8`, a different address from
    the `0x2157dd4` SPAPPLY site above) fired at frames 712 and 851; the
    bar-count drops read at 713 and 852 — the same one-heartbeat lag the
    pool's own `+256` deposits show against their `SPAPPLY` firings
    (deposit at frame *N*, heartbeat shows the new pool value at
    *N+1*, an artifact of the heartbeat sampling after the writer on the
    same anchor tick). Not confirmed as the writer. See
    feel-captures/sp-deposit-2026-09-14/rerun/RESULTS.md.
  - **Deposit writer, mechanism CONFIRMED (`jus-36wu`) live for four of
    five pending cells; `+0x64` and the snapshot trigger PLAUSIBLE/open.**
    Five pending cells at `char+0x130+0x64/+0x66/+0x68/+0x6A/+0x6C` (ov6)
    are written by four small copy routines: `0x0215FCB8`
    (`+0x66`/`+0x68` = copy of `+0x5A`/`+0x5C`, found in a Refuter pass
    after the original probe missed it), `0x0215FCCC` (`+0x6A` = copy of
    `+0x5E`), `0x0215FCD8` (`+0x6C` = copy of `+0x60`), and `0x0215FCE4`
    (`+0x64` = a per-ability-indexed table entry, gated on a per-index
    valid bitmask — **CONFIRMED firing live for index 14, `jus-1bkw`
    2026-09-14**: `bit_set=1` in 11 of 23 idx-14 firings across all
    three fixtures (12 clear), writing `+0x64=0xa00` (`10.00`) each
    time — 8 of those 11 on `char=0x224ef00`, 3 on `char=0x2228e80`,
    not both fighters every time; index 8 reads `bit_set=0` in all 14
    of its firings, so the gate is index-specific, not permanently
    closed. 37 gate firings total this session (23 idx 14 + 14 idx 8)).
    `+0x5A`/`+0x5E`/`+0x60`/`+0x5C` are themselves
    snapshotted from a shared global config record
    (`[[0x02172984]+0xC]+{0,4,8,0xC,0x10}`, raw `{15,10,4,4,20}` in every
    deck measured, `raw<<8` conversion) by a routine at `0x0215FB88`;
    `+0x5A`/`+0x5C` are also live accumulators (`0x0215FD00` adds a
    per-ability value into them, `0x0215FD68` adds `+0x62` into `+0x5A`).
    All four previously "unattributed" deposits are now attributed by
    cell: `3840`(idx 0)→`+0x66`, `2560`(idx 1)→`+0x6A`, `1024` from two
    sources (idx 2→`+0x6C`, idx 3→`+0x68`); `5120` (idx 4, `+0x62`) has
    no direct-copy writer and is only a candidate at `+0x66` via the
    `+0x5A` accumulator, unconfirmed live. The guard run
    (`pc-kenshin-luffy-guard`) shows two attacker deposits (`3840`/`1024`)
    and one victim deposit (`2560`/`1024`) on the single unguarded hit,
    and no writer activity on either later, presumed-guarded hit — this
    is no longer "in tension" with the prior payout-decay reading (the
    payout routine halves its cell unconditionally every tick, so a fresh
    `3840` on a later press requires a fresh deposit); what is still open
    is whether those later hits were actually guarded. **`jus-1bkw`
    (2026-09-14) read `M+0x40` bit `0x1000` directly at the writer**
    (`M = [[char+0x1a8]+0x10]`, the same field `atns5_guard.gdb` already
    uses) and got one row: the unguarded press, with bit `0x1000=0`
    there. **Correction: the raw log
    (`feel-captures/sp-deposit-2026-09-14/logs/fixture2_gdb.log.gz`) is
    9 lines and ends at that same row (frame 160), then GDB itself
    aborts mid-target-run** — the session crashed before it's known
    whether presses 2 and 3 were even reached, and the plan-frame ↔
    probe-frame offset was never recorded. "Did not fire at all for the
    two later presses" is retracted for lack of data; the non-firing on
    guard **reverts to an HP-flat inference**, not a direct observation,
    until a clean rerun records the offset. The one unguarded-press row
    (`guard_bit_1000=0`) stands. **Part B rerun, `jus-1bkw`,
    2026-09-14**: `bit_1000` read every anchor tick for both fighters
    plus a 4th B press. **Correction: this rerun's own raw log still
    ends on the same GDB "target is running" abort** — the "reran
    cleanly, no crash" claim first published here was false; the driver
    fix that session actually made (`jusemu()`'s JSON parsing and
    `Runner.idle()`'s plan shape) never touched the abort, and the abort
    lands only after every scripted press window has already run its
    course (frame 680 of a 680-frame log whose last B press fires at
    probe frame 104), so it is benign end-of-session noise, not a
    mid-plan crash — see the Part A/B fix-and-rerun pass,
    2026-09-14. Only one hit landed the whole session; `bit_1000` read
    `0` at every tick around all four press windows except a
    single-frame pulse to `1` at frame 89, coincident with a
    payout-decay tick, not a button press. **This is new evidence
    against `bit_1000` being a stable "guarded" flag** — stays OPEN,
    with a fresh question about what the bit actually tracks; see the
    forward pointer in §0.5 above for the per-hit-event reading that
    is consistent with this result. See
    feel-captures/sp-deposit-2026-09-14/rerun/RESULTS.md
    and
    [sp-apply-0x020781E4-is-a-mixed-radix-pool-with-bar-count.md](../research/findings/sp-apply-0x020781E4-is-a-mixed-radix-pool-with-bar-count.md)
    "Deposit writer"/"Mechanism",
    feel-captures/sp-deposit-2026-09-12/, and
    feel-captures/sp-deposit-2026-09-14/RESULTS.md.
  - **Ability 55/56 tick — amount CONFIRMED (`jus-36wu`), rate CONFIRMED
    (`jus-1bkw`, 2026-09-14): 1 fire per `0x02082E10` anchor tick, zero
    skips.** `pc-momotaro-npc-nami-dark-tournament` (Momotaro,
    ability-56 carrier, active P1) fired arm9 `0x02077E3C`, every firing
    with `amount=-3`, each visibly decrementing the live pool word at
    `slot_P1+0x5C8` by exactly 3 raw units (`lr=0x02077E40` ties the
    store to this call site). A `jus-1bkw` session measured the firing
    rate directly against a dedicated per-frame breakpoint counter (the
    anchor PC `0x02082E10`, the same one `atns5_guard.gdb` uses) in one
    continuous GDB session: **3709 firings, all 3708 successive
    frame-to-frame deltas equal to exactly 1** (corrected count — the
    first pass through this session's log mis-transcribed it as
    2906/2905; the committed raw log has 3709 `Q5_ABILITY5556` rows).
    The 950-idle/320-active frame counts describe the driving plan's own
    segment lengths, not this anchor-tick total, so the frame basis this
    rate is measured against is open, not settled, pending a cross-check
    against `emu.framecount()`. **Part B cross-check (`jus-1bkw`,
    2026-09-14), corrected in the fix-and-rerun pass the same day**:
    the raw `1292`-anchor-ticks-vs-`904`-bridge-frames whole-session
    ratio (`1.429`) is an interval-boundary artifact, not evidence
    against 1:1. Within a single `run_plan()`/`idle()` call the anchor
    tick and the plan's own clock advance in exact lockstep — the
    `INPUT_HEARTBEAT` edges in the fixture-3 log sit a *constant* offset
    (`+356`) ahead of the plan's own frame numbers at all six segment
    starts (`320/360/400/420/440/460` → `676/716/756/776/796/816`,
    re-derived from the committed log and plan JSON by
    `framecount_crosscheck()` in `scripts/analysis/e1bkw_sp_run.py`,
    unit-tested against that exact file). The `1292` figure counts
    `373` extra ticks that accrue *after* the plan's own last
    `tail_frames` frame, while the bridge free-runs at ~60fps in the
    gap before the driver's next command (the same free-run behavior
    `loop-state-atlas.json` notes for `jus-vkj` (that tracker item's own harness
    fix was later retracted by runtime on an unrelated point; the
    free-run mechanism it measured is the one cited here), and
    `scripts/emu/agent_bridge.lua`'s own `finish_plan()`/`start_plan()`
    comments) — subtracting that tail gives an in-plan count of `919`
    ticks against the same `904` bridge frames, ratio `1.02`, consistent
    with **1 anchor tick per rendered frame**, matching
    [physics.md's](physics.md) `0x02082E10` integrator note (fires once
    per frame; per-element work happens inside that single call, not
    across extra frame-entries). The ability 55/56 tick is 1 fire per
    anchor tick (still exact, unchanged) = 1 fire per rendered frame =
    `−3` raw/frame, **CONFIRMED (`jus-1bkw`)**. The prior session's `1.11`/`0.68`
    brackets are explained the same way, on a different window: the
    pre-plan `idle(320)` call itself requests `321` bridge frames
    (`jus_plan.validate_plan()`'s own `total_frames` for that shape,
    also unit-tested) but the offset shows `355` anchor ticks elapsed
    by the time the next plan's own clock starts — `355/321 = 1.106`,
    the same reading as the original `1.11` bracket, on the bridge's
    own free-running/reload window rather than a distinct rate. There
    is no reciprocal-units mismatch to reconcile (the earlier "0.68 is
    the reciprocal of 1.429, at 0.70" framing compared fires-per-frame
    against frame-per-fire, an inverted-units artifact of the same
    interval-boundary confusion, not a second real number). See
    feel-captures/sp-deposit-2026-09-12/pc-momotaro-npc-nami-dark-tournament/RESULTS.md
    (superseded brackets),
    feel-captures/sp-deposit-2026-09-14/RESULTS.md,
    and
    feel-captures/sp-deposit-2026-09-14/rerun/RESULTS.md
    (corrected).
- **SP-apply `0x020781E4`** is three lines: `[slot+0x5C8] += amount`, refused when
  the amount is negative and the signed byte `slot+0x5CF` is non-zero — i.e.
  `+0x5CF` **blocks SP loss but never SP gain**. `+0x5CC`/`+0x5CD` are read the
  same way (untraced siblings)
  ([player-slot-sp-total-at-0x5c8.md](../research/findings/player-slot-sp-total-at-0x5c8.md),
  which also carries the 14-field slot map; note `+0x558` and `+0x56C` appear in
  that slot map too — the map does not settle which base object "char" is, see
  GAP 5).
- The **view is a live SP-apply path**: view selectors 9/12 tail-call
  `0x020781E4` with a per-slot `int16` from `view+0x16+N*2`; selectors 13/14
  apply the `view+0x64` scratch halfword if non-zero
  ([view-handlers-are-the-live-sp-apply-path.md](../research/findings/view-handlers-are-the-live-sp-apply-path.md)).
  Fine distinction a spec writer will get wrong: the 16-slot view handler
  *table* is dead in retail
  ([the-view-handler-table-is-dead.md](../research/findings/the-view-handler-table-is-dead.md)),
  but the view itself is not — hit resolution and the state dispatcher call it.

### 1.5 The status/effect dispatch around the gauges

(Shared with the damage spec; listed here because guard/SP deltas arrive
through it.)

- 42-entry, 8-byte-stride handler table at ov6 `0x02171168`; effect **ids 1–41,
  0 = none**. Ids `0x01`–`0x11` are gauge effects with no status byte (P157/P159).
- Dispatcher ov6 `0x02158ED0(battleObj, id)`; effect nodes at
  `battleObj+0x7C + slot*0x18`, two slots (P158/P159).
- On-hit flush `0x02158B20`: pending HP delta `scratch+0xE8`, pending second
  gauge `+0x130`, plus two staged effect ids at `X+0x172/0x173` (`+0x173` stored
  negated), `X = [[battleObj+0x1A8]+0x10]` (P159 Route B).
- Duration formula (`0x02158F44`): `duration = base + (base/10)*(stat*2)` —
  scales status *duration*, not damage; the meaning of `stat` is not claimed
  (P158/P160).
- GrowMax has exactly one caller (`0x0215C73C`), gated on bit `0x80` of
  `char+0x128`, fixed +0x400 delta — plausible home of the "max HP on respawn"
  passive, ability `0x07` (claim 9, PLAUSIBLE).

---

### Guide leads for SP-trigger passives

Owner testimony (`jus-atns.3`, 2026-09-12) confirms base SP gain from hitting and
being hit, with passives adding other triggers. The Genroh guide lists multi-hit,
repeated-special, chain-attack, last-moment-block, stationary, field-presence,
KO, and conditional attack/block gain categories. These are fan-guide claims,
not measured ability-to-deposit mappings. The
[source extraction](../research/findings/genroh-sp-trigger-leads.md) records
the categories and missing parameters under `jus-1bkw`.

The guide supplies no numeric tick cadence or repeated-special/multi-hit window.
It cannot replace the measured deposit-and-payout arithmetic above. Runtime work
must establish those thresholds and the mapping to the bonus table.

## 2. GAPS — what a reimplementer cannot build yet

The plumbing above moves numbers into gauges. **The gauge model itself is
unspecified.** Concretely:

1. **No node-insertion site for `char+0x558` exists in the database.** Of 37
   ROM-wide load/store hits on immediate `0x558`, exactly **1 is a store — the
   zero-init**. Nothing populates the list with a live node (likely a split-base
   `add`+register-offset store, invisible to immediate scans; see INVENTORY
   "Tooling hazards"). A spec cannot say how meters come into existence.
   (Battle-Engine-Map claim 14 + open questions; history in the archived
   [GDB-Validation-Queue.md](../research/archive/GDB-Validation-Queue.md)

   **Static-basis addition (2026-09-12, `jus-f86l`, static-only, no
   emulator/GDB).** The SP bar-count fields `slot+0x5CC`/`+0x5CD` *are*
   statically traced to init sites, even though the `+0x558` node-insertion
   question above stays open. Evidence:
   sp-init-2026-09-12/RESULTS.md,
   [sp-initial-state-and-bonus-table-static.md](../research/findings/sp-initial-state-and-bonus-table-static.md).

   | field | pc | value | function |
   |---|---|---|---|
   | `m` (`+0x5CC`) | `0x02077618` | `0` (entry zero) | `0x02077610` |
   | `m` (`+0x5CC`) | `0x020776CC`/`0x020776F0` | clamp to `0x10` (16) once a `+0x558`-list-derived accumulator at the same offset exceeds 16 | `0x02077610` |
   | `c` (`+0x5CD`) | `0x02076BA0` | `0x10` (16) | `0x020769CC` (caller of `0x02077610`) |
   | `c` (`+0x5CD`) | `0x02076BB0` | `m` if `c > m` (clamp) | `0x020769CC` |
   | `c`/`x` (`+0x5CD`/`+0x5C8`) | `0x0207878C`/`0x02078790` | `0` (reset, `+0x558`-non-empty-gated; also zeroes `+0x578`) | `0x0207871C` — a distinct leaf function, **not** the tail of `0x02078660`; **reachability [unverified]** (the 6 ov6 `bl` sites previously credited here target `0x02078660`, which returns at `0x02078718` and never reaches `0x0207871C` — a `functions.json` merge artefact, see finding doc) |

   **`m` is not constant, and the counting rule is weighted, not a flat
   tally.** Per `+0x558`-list node, classification is
   `[[node+0x34]+0xb] & 0xf` (one extra indirection through `node+0x34`).
   A node qualifies if that classification `!= 3` **and** `node+0x40 !=
   2`. A qualifying node increments the `+0x5CC` accumulator once, always,
   and again if `node+0x40 == 0` — so `m = 2·(qualifying, +0x40==0) +
   1·(qualifying, +0x40==1)`, clamped to 16. It's still a deck/
   ability-composition value, not a rule setting and not a fixed number.
   `c` starts at `min(16, m)` and is separately zeroed (with `x`) on a
   reset function whose reachability is now **[unverified]** (see the
   table row above). Two live `m` values — `7` on a 3-koma dream-attack
   deck and `9` on the 4-koma Kakashi state (§1.4 above) — fit `m = 2n+1`
   for `n` koma, and already refute a fixed-constant `m`; a live trace of
   each qualifying node's `(classification, +0x40)` pair would confirm the
   weighting hypothesis. **This still does not answer gap 1 itself**
   (`0x02077610` walks the list; it does not insert into it).

   **Object-layout: gap 5 resolves toward one shared object.**
   `0x02077610` touches `+0x558` and `+0x5CC` on the same register without
   ever dereferencing `char+0x1B4` — but its caller `0x020769CC` passes
   that same register (`sl`) both into `0x02077610` and into direct reads/
   writes of `[sl+0x558]` and `[sl+0x5cd]`, and `0x020769CC`'s own callee
   `0x02076C18` constructs that object as the player slot (`memset`s
   `r0+8` for `0x5E0` bytes, then writes `+0x5D7`). `slot+0x5CD` is also
   runtime-confirmed at `0x021DF731` (Kakashi trace, §1.4 above). This resolves
   gap 5's "base-object ambiguity" toward **`+0x558` also being a slot
   field**, not toward `char`/`slot` conflation.

   The bonus-table question in the same ticket (which ability indices feed
   ov6 `0x0215FD00`'s `+0x16+2*idx` add) is answered as far as statics go
   in the same finding: the array-fill function `0x0215FC20` — previously
   suspected dead in
   [view-slot-arm-and-the-unreachable-setter.md](../research/findings/view-slot-arm-and-the-unreachable-setter.md) —
   is reachable through a fixed dispatch table at ov6 `0x02172210`, keyed
   on **byte 0** of a per-id classification entry; the handler that entry
   selects then arms mask bit `N` = **byte 1 of that same classification
   entry** (not the id itself). So slot 5 (the one live call site found)
   is armed by whichever id's classification entry has byte 0 `== 1` and
   byte 1 `== 5` — not "whichever record has `+0xb == 5`" as an earlier
   draft claimed. Which named ability that is remains open (the
   classification table's base pointer `[0x0214BD80]` was not resolved).
   card 30, triaged still-live 2026-09-04 under `jus-ypi5`).
2. **Node-kind census is statically unresolvable.** How many gauge kinds live in
   the list (guard? SP? one shared "resource" node?) is unknown — the walker has
   no type dispatch (claim 13, SPECULATIVE).
3. **Closed 2026-09-03: SP is deck-shared** (maintainer ruling 2026-09-02, "no
   character-specific SP", and the runtime word sits on the per-player slot
   that also holds the team's HP records, §1.4). History follows.
   ~~Deck-shared vs per-character SP is unresolved — the biggest design question
   here.~~ SP is documented as deck-wide (shared across a player's 3-character
   team), and the confirmed SP total does sit on a *per-player* slot
   (`+0x5C8`). But the meter list sits at a per-character `+0x558`. Is SP a
   node aliased across the team's three character structs, or does each
   character feed a shared pool? Do not pick a model in a reimplementation
   without settling this. (Battle-Engine-Map §guard-sp-gauges open questions;
   INVENTORY §5 question 3.)
4. **The `+0x558` node vs `+0x56C` pointer identity dispute** — the campaign's
   top open dispute, **ticketed as `jus-map.13`** ("Settle or
   waive: +0x558 vs +0x56c gauge dispute", GDB card #1). The aliasing lens says
   yes (`0x02077E70` stores a raw candidate node into `char+0x56C` at
   `0x02077FDC`); the disasm-correctness lens says no (disjoint, fully-traced
   caller graphs). Everything in §1.3 that touches identity is contingent on it
   (Battle-Engine-Map §chrb-catalog "TOP OPEN DISPUTE", claims 3/11/16).
   **Closed 2026-08-23**: moot. `char+0x56C` is the HP block and `char+0x558` is
   an ability-source list (§0); neither is the guard gauge (§0.5). Kept as history.
5. **Base-object ambiguity.** The guard/SP findings write `char+0x558/+0x56C`,
   while the player-slot map lists `+0x558` and `+0x56C` as fields of the
   `0x61C` ComicDeck player slot. Whether these are one object under two names
   or a genuine offset coincidence is not pinned down in the corpus; it feeds
   directly into gap 3/4.
6. **87% of the player slot (`+0x000`–`+0x557`) is unmapped**, and `+0x059`–`+0x557`
   is untouched by `ComicDeck.cpp` itself — some other module owns it
   ([player-slot-sp-total-at-0x5c8.md](../research/findings/player-slot-sp-total-at-0x5c8.md)).
7. **A fixed-offset guard/SP gauge elsewhere is not excluded** — no byte-pattern
   scanner for the `ldr ip,[pc,#N] / ldr r0,[r0,#M] / bx ip` trampoline shape
   with `M != 0x56C` was ever run (Battle-Engine-Map open questions; claim 10
   held plausible only).
8. **Guard mechanics proper.** What blocking costs is now measured (§0.5),
   and what a human release does — with or without a just-blocked hit — is
   now measured (§0.8, PLAUSIBLE, `jus-rsye`). The Auto-Guard interaction
   with an empty SP pool is still untested — Auto-Guard's zero-damage
   measurement was taken with SP available (INVENTORY §9) — and remains
   unchecked; the deciding read is bit 4 (`0x10`) of the fighter's ability
   bitset `obj+0x128` (helpers.md §5; writer ov6 `0x0215FB3C`; fed by the
   character list and the deck `+0x558` chain), not a name match against the
   helper carrier list (ability 4's carriers are helper koma). **2026-09-12b
   checked this bit directly (not by name) across 8 savestates with varied
   P1 characters and found it clear on all 16 fighter reads** (guard §0.8;
   `../research/feel-captures/guard-2026-09-12b/RESULTS.md`
   §4) — still absence over a sample, not a roster-wide proof, so a carrier
   state still needs to be built before the Auto-Guard-with-empty-SP leg
   itself can run.

   | P1 / P2 | P1 `obj+0x128` | P2 `obj+0x128` |
   |---|---|---|
   | kenshin / luffy | `0x6` | `0x2005200` |
   | momotaro / nami | `0x600` | `0x1010008` |
   | yusuke / nami | `0x0` | `0x1010008` |
   | taikoubou / jotaro | `0x0` | `0x2000` |
   | kakashi / jotaro | `0x2004` | `0x2000` |
   | muhyo / jotaro | `0x1000000` | `0x2000` |
   | sasuke / jotaro | `0x2004` | `0x2000` |
   | eve / jotaro | `0x1000002` | `0x2000` |

   Caveat: not 16 independent samples — five Jotaro P2 reads share one deck
   (`0x2000`) and two Nami reads share another (`0x1010008`); Auto-Guard
   comes from helper koma, so the deck is the real sampling unit, not the
   fighter read — roughly 6 P1 decks and 3 P2 decks, not 16.

Resolution path (updated 2026-09-02): gap 4 is closed. Gaps 1, 2 and 3 are
runtime questions for the SP side; the `JUS_WATCH` write-watchpoint approach
that found the guard gauge (§0.5) is the instrument to try first.
