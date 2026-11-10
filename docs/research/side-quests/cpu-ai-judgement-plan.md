# Getting to a judgement patch: the Astra plan, and the corrections that precede it

**Provenance.** Consulted 2026-09-27 with `codex exec -m gpt-6-astra -s read-only`
(read-only, in-repo, so the model read the three side-quest documents, the patch builder
and the issue tracker's export itself). The model's final message verbatim is below the fold.

**The bottom line, in its words:** *"A patch that improves all four complaints is not
build-ready. Most remaining work is establishing which decision fails and why... The nearest
defensible target is repairing the freeze."* So the answer to "how much left" is: the
*build* is nearly free, the *knowledge* is the distance, and only one of the four complaints
is currently close enough to patch.

## The seven corrections it made, and how I verified each

I did not take these on trust. Every one was re-checked against the overlay bytes; all seven
hold. Several invalidate load-bearing claims of mine, now fixed in place in the source docs.

| # | Astra's correction | My verification | Result |
|---|---|---|---|
| 1 | The reaction table is at `0x02181438`, not `0x021811F0`, and has **14** entries; entry 13 is `(127,18,27)`, so the `0x7F` sentinel **fires**. | Read the literals at `0x0217AD6C`/`0x0217ADB8`: both `ldr` from `0x0217B070`, which holds `0x02181438`. **No** literal in ov11 points at `0x021811F0`. Table dumped: 14 entries + `(-1,-1,-1)`. | **Confirmed.** The doc's "the `0x7F` branch cannot fire" was measured against the wrong address. Retracted; §4.4 rewritten. |
| 2 | The reaction path is an **alternative** to the wheel, not a precursor. | `0x0217AD60 beq 0x217ae04` — the wheel setup is entered only when `([AI+0x2C]+0x38) & 3 == 0`. | **Confirmed.** §1/§2 corrected. |
| 3 | `ctx+0xC0` is **not** wheel-exclusive. | `bl`-target scan of ov11 for `0x02174EBC`: **ten** callers (`0x0217A7A8`, `0x0217AAC8`, `0x0217AC9C`, `0x0217AD40`, `0x0217ADFC`, `0x0217B050`, `0x0217BC48`, `0x0217C2A4`, `0x0217C620`, `0x0217C890`). | **Confirmed.** My "independent confirmation of the clamp" is **withdrawn**; it required wheel-only provenance. §2.2 corrected. |
| 4 | The `+0x18` partition is on the **sub-record** (`record+0xB4`), and `op_b_03`'s record-relative `+0x18` is zero. | My own accessor reads `rec[0x9C:0xBC][0x18]` — i.e. sub-record `+0x18`. A patch using record-relative `+0x18` would hit a different field. | **Confirmed.** Offset discipline added to §2.3 and the layout doc §5. |
| 5 | "`STRD` does not exist on ARMv5TE" is false, so that structural proof is void. | ARMv5TE does include `STRD`. A fresh scan of ov11 for `STRD`/`LDRD`-shaped words finds **none** in the immediate-offset encoding, so the conclusion survives *for this overlay* — but not on the stated grounds. | **Confirmed as an error.** Corrected in `cpu-ai-levels.md` §3.14; the honest basis is now the measurement (all-zero on every frame), not the encoding argument. |
| 6 | The `.ips` artifacts are a custom format, not standard IPS, and the applier skips the stored pre-images. | `verify_ips.py` requires a literal `@` before each record, then a 4-byte big-endian offset and a 1-byte size, and takes the "after" half of a doubled block. Standard IPS has no such marker and uses a 3-byte offset / 2-byte size. It never compares the "before" half to the ROM. | **Confirmed.** Documented below; the deliverable is a `.nds` anyway. |
| 7 | The listed code caves over-count: the 28 bytes at `0x021816A4` lie inside the 32-byte hole. | 28 ⊂ 32, so the two internal holes are **68** distinct bytes, not 96. My brief's arithmetic was the wrong one. | **Confirmed.** Corrected in `cpu-ai-levels.md` §3.15 area. |

Two further cautions from Astra that I accept without reservation: **player state zero is
correlated with the freeze, not proved to cause it**; and the remap byte `s8[*(ctx+4)+8]`
should stay unnamed until its identity is established — the constructor fills `ctx+4` from a
grid-indexed lookup at `0x021745D0`, which is not enough to call it the opponent's live combat
state. The arithmetic is real; "punish/anti-air selection" is not yet.

## What that does to the plan, and the one thing it opens

Correction 1 is the consequential one. The reaction table is a **live cumulative weighted
pick** over fourteen entries whose byte 0 is the behaviour id, byte 1 a novelty/veto class,
and byte 2 an index into a weight table at `[AI+0x2C]+8`. Its entries 10–12 issue ids
**11, 13 and 14** — ids the clamped `+0x48` wheel can never produce, and 13/14 are exactly
the opponent-state-remapped family. **So the claim I was carrying, "the clamp makes
punish/anti-air unreachable", is false.** They are reachable; what is unmeasured is whether
the roll `([AI+0x2C]+0x38)>>1` and the weights ever put the selection in that band. That is
one bridge-only capture, no patch, no GDB.

Astra's plan does not take that route — it targets the freeze first, which is defensible on
its own evidence. I flag the reaction table because it is the sharpest *judgement* lead
anyone has produced, and it is cheap. See `ai-behaviour-taxonomy.md` §4.4.

---

## Revision, same day: the plan's step 2 is done, and its leading hypothesis is refuted

Executed immediately after the review, **with no emulator run** — see
`cpu-ai-levels.md` §3.22 and `ai-capture-protocol.md`.

- **Step 2's falsifier fired.** The disarm at `0x02177BA4`–`0x02177BE4` is *working*: `+0x105`
  equals 1 on 20 frames, including fc 33415–33416, exactly when `BattleAIMove` `+0x180` drops
  to 0. Both movement objects are inert from fc 33416. So the freeze is not "phase 1 waiting
  for a movement expiry that never reaches the replan path" — the expiry reaches it, fires,
  and the CPU is still stuck.
- **Its target was right anyway.** The freeze is a **phase-1 park**: `AI+0x39 = 1` held 456
  frames, while attack state 9 is produced almost exclusively by phases 4 and 5 (172 of 178
  frames) and phase 1 produced **zero** attacks in 539 frames. The same id 2 in a healthy
  episode sits at phase 5 and attacks for 64 of 68 frames. So `0x0217B0F0` (phase 1) is the
  right handler, and the phase list walk `0x0217BA88`–`0x0217BACC` is the new target.
- **Therefore Astra's "single most likely patch" is not it.** Its own falsifier — "the
  corrected transition executes, but the CPU still cannot make purposeful progress" — is
  close to already observed. Do not build the movement-transition repair.
- **The next executable step replaces step 2**: *what advances phase 1 to 4/5, and why it
  stops during the freeze?* Static first (the phase list walk and the phase-1 handler), then
  the standing capture below.
- **Job budget revised down** (see `ai-capture-protocol.md` §5): 15–20 → **8–13**, because
  discovery collapses into one wide standing capture per (ROM, fixture) while validation —
  stock vs patched, and transfer to a second character and geometry — does not.

---

A patch that improves all four complaints is **not build-ready**. Most remaining work is establishing which decision fails and why. The existing builder solves only a small part of the eventual build work.

The nearest defensible target is **repairing the freeze**. It has a deterministic failure, a populated behaviour record, and identifiable movement-disarm and dispatch paths. Careless attacks and punishment still lack the connection between authored fields, eligibility tests, and actual moves. Self-KO still lacks a valid capture connecting autonomous movement to departure from the stage.

My estimate is **four bounded static passes and three diagnostic emulator jobs to a first freeze candidate**, then **two write-free ROM runs for its initial A/B**. That estimate is conditional on finding a small repair in existing control flow. It is not an estimate for solving all four complaints.

I made no changes. `br` could not read without opening a write lock, so I consulted the tracker's export. I also checked several disputed claims against the extracted ov11 bytes; its SHA-256 matches the research document.

**Several premises need correction before planning from them.**

| Claim | What I found | Planning consequence |
|---|---|---|
| Reaction table at `0x021811F0`, 18 entries, no `0x7F` entry | Both literal loads at `0x0217AD6C` and `0x0217ADB8` read the word at `0x0217B070`, which is **`0x02181438`**. There are **14 entries before the negative terminator**. Entry 13 is **`(127,18,27)`** at `0x0218145F`. | The dormant-sentinel hypothesis is false. Do not patch `0x021811F0` as this table. |
| Reaction selection falls through to the wheel | `0x0217ADEC` exits to `0x0217B054` when the selected id is zero. Otherwise `0x0217ADFC` issues it and `0x0217AE00` also branches to that exit. The wheel starts on the separate path at `0x0217AE04`. | Treat these as alternative selection paths. Moreover, the reaction loop accumulates bytes from `[AI+0x2C]+8+entry[2]`; it is not established as a tactical punish recognizer. |
| `ctx+0xC0` belongs only to the wheel | Its writer is inside shared issuer `0x02174EBC`. The reaction path calls that issuer with channel zero, and the unclamped consumer also calls it. | It records a successfully resolved id for a channel. The observed `{2,5,6}` histogram does not prove exclusive wheel provenance. Instrument the caller when provenance matters. |
| The partition is at **record** `+0x18`, with an exact split | The analysis script reads **sub-record** `+0x18`, meaning `record+0x9C+0x20*k+0x18`. In `op_b_03`, record `+0x18` is zero for the sampled ids. The corpus also contains exceptions to the split. | An edit using the stated record-relative offset would touch the wrong field. [Actual accessor](../../../scripts/analysis/aipm_slot_matrix.py:118). |
| `STRD` does not exist on ARMv5TE, proving no hidden writer | ARMv5TE supports double-word instructions. Independently, adjusted pointers, register offsets, `STM`, and bulk copies defeat an immediate-offset-only absence proof. [Arm documentation](https://documentation-service.arm.com/static/5ea04d399931941038de55af). | The observed zero values stand. “Never written anywhere” needs stronger evidence. This does not justify another broad writer hunt before a causal self-KO capture. |
| The listed caves provide independent capacities | The 28 bytes at `0x021816A4` lie inside the 32 bytes at `0x021816A0`. Together with the 36-byte hole at `0x0218161C`, those named regions provide **68 distinct bytes**. | Any additional trailing space must be separately identified and checked. ov10 shares ov11’s load base, so its free space is not automatically available during ov11 execution. |

Two further causal claims remain too strong.

First, **player state zero is correlated with the freeze, not yet proved to cause it**. The research itself preserves that qualification. Second, the remap byte should remain an unnamed byte until its identity is established. The constructor stores `ctx+4` from `0x02076CE0`, a grid-indexed lookup, at `0x021745D0`. That is not enough to call it the opponent’s live combat state. The arithmetic is real; its interpretation as punish or anti-air selection is not.

The old rankings in taxonomy §4–5 therefore cannot serve as the execution order. Some ranked questions are already answered, and others rest on incorrect addresses.

The following is the execution plan. A **job means one controlled replay**, not an emulator launch containing an unspecified number of trials. All jobs are serialized.

1. **Establish the experiment and acceptance contract. One static pass, zero jobs. Addresses all four complaints.**

   **Question:** Can the proposed measurements distinguish better decisions from more activity, and can the actual patched ROM be tested?

   Inventory existing captures and fixture sidecars. Resolve fighter identities, CPU mode, active AI block, emulator version, ROM hash, input script, and observation frame. Require `op_b_03.bin` by payload identity for the known freeze fixture.

   Define these measures before changing anything:

   | Complaint | Primary measure |
   |---|---|
   | Careless attacks | Impossible-to-connect commitments divided by attack commitments, classified using facing, spatial reach, and target vulnerability. Record ordinary whiffs separately. |
   | Bad punishes | Successful punishes divided by verified punishable opportunities. Also record response latency. An opportunity must permit the CPU’s approach and startup before the opponent can defend. |
   | Self-KOs | Unforced departures and confirmed resulting KOs, with edge exposures as a denominator. Exclude knockback, scripted player movement, and recoverable excursions. |
   | Freeze | Sustained loss of commands and purposeful movement while combat remains active and the CPU can act. Record onset, duration, recovery, and recurrence. |

   Record damage dealt and received, idle-frame fraction, action initiations per second, and guard-hold duration alongside these rates. Count command or move initiations, not frames holding an id. Read current HP as a two-byte value and account for healing and character switches.

   **Decision and patch unlocked:** A usable baseline and an explicit scope for each candidate.

   **Falsifier:** The fixture is not fighting autonomously, the character differs, a denominator is zero, or the required outcome cannot be classified. Such a run supplies no evidence for that complaint.

   **ROM-loading gate:** A stock savestate may restore stock overlay and data bytes over a patched-ROM session. Require a checkpoint before the relevant loads, or matched cold-boot setup. Verify the candidate bytes and decompressed payload in memory before accepting an A/B. Follow the [bridge hazards](../../../scripts/emu/README.md:415): standalone state loads, framecount-based timing, one GDB session per launch, and a bridge-only control.

2. **Trace the freeze’s movement-completion contract. One static pass, zero jobs. Addresses complaint 4.**

   **Question:** What is phase 1 waiting for after movement expires, and which transition should release that wait?

   Read these connected paths, preserving object identity:

   - Phase-1 handler `0x0217B0F0`, registered at `0x02181984`.
   - Movement-object accessor `0x0217B4F0`, returning `[ctx+8]`.
   - Movement request `0x02176D64`.
   - Re-arm sequence `0x02176F84–0x02177004`.
   - Timeout/disarm `0x02177BA4–0x02177BE4`.
   - Existing reset/replan paths at `0x0217B3FC–0x0217B408` and `0x0217B458–0x0217B46C`.

   The bytes already provide useful detail. Arming sets counter `+0x184` to `0xF0` and sets bits in `+0x180`. Expiration clears bits `0x40` and `0x20`, clears `+0x18B`, and requests another decision through `AI+0x105`.

   Phase 1 also has a close-range restart test at `0x0217B430–0x0217B454`, followed by a saturating counter at `AI+0x3E`. Trace that test’s units and preconditions. Do not assume it is a general timeout.

   **Decision and patch unlocked:** Identify either a missing failure/completion transition or a failed movement request whose result is mishandled. Prefer repairing that transition over adding a new timer.

   **Falsifier:** The disarm is normal, and the CPU is waiting on a separate valid constraint. Then this is not a movement-timeout repair.

3. **Locate the first failed transition and test it once. Three jobs. Addresses complaint 4.**

   - **J1: bridge-only stock control.** Cover healthy play, the disarm, and at least 3,000 frames after the known latch. Log `AI+0x39/+0x3A/+0x3E/+0x105`, both fighter states, positions, actual commands, and the live movement object’s `+0x180/+0x184/+0x18B`. Resolve the object dynamically; also watch the second known instance to catch mistaken attribution.
   - **J2: instrumented stock replay.** Log arguments and return values at movement request `0x02176D64`, the re-arm/disarm sites, and the phase-1 branches identified in step 2. Attribute issuer calls to their callers. Compare the healthy and frozen id-2 episodes within this run. Reject trajectory-based conclusions if instrumentation diverges from J1.
   - **J3: one targeted intervention.** Change only the diagnosed branch outcome or completion transition, once, after reproducing the failure. Keep opponent position and behaviour unchanged. This is a diagnostic probe, not the deliverable.

   **Decision and patch unlocked:** A specific transition repair, with the failure condition and legitimate exclusions established.

   **Falsifier:** The intervention changes phase/id bytes but produces no purposeful movement or legal attack, immediately relatches, or works only because it changes the opponent’s position. A phase-cycle improvement is not a freeze fix.

   Do not spend another job merely reproducing the known latch, empty-mask negative, or populated id-2 record.

4. **Construct one freeze candidate and verify its bytes. Two static/build passes, zero jobs. Addresses complaint 4.**

   **Question:** Can the diagnosed repair fit safely in resident code and survive independent application?

   The preferred candidate makes an expired or failed movement request reach the existing cleanup/replan path. Keep normal attack, hitstun, guard, and movement eligibility intact. Do not force id 2 to attack, disable movement expiration, or continually write `+0x180=0x60`.

   First try an in-place branch or condition repair. If a trampoline is necessary, audit the distinct holes for references, initialization, alignment, displaced instructions, register preservation, and flags. Do not budget ov10 space without a residency proof.

   The [current builder](../../../scripts/patches/make_cpu_ai_patch.py:88) expresses the three probability tiers only. Add a separate judgement variant with exact pre-images and an explicit edit manifest. For ov11:

   `ROM offset = 0x001D7E00 + address - 0x02172A60`.

   Independently apply the patch and require full-byte equality with the directly generated `.nds`, unchanged ROM size, and a diff matching the manifest exactly. Decode every changed instruction.

   The existing `.ips` writer/applier use a custom `@` record format; they are not standard IPS. The [applier](../../../scripts/patches/verify_ips.py:7) also skips stored pre-images. Preserve independent application, but strengthen verification and deliver the requested `.nds` without implying compatibility with ordinary IPS tools.

   **Decision and patch unlocked:** One reviewable, independently verified ROM candidate.

   **Falsifier:** The repair requires unknown scratch storage, unsafe cross-overlay execution, or broad changes to attack eligibility. Stop and redesign rather than squeeze it into an assumed cave.

5. **A/B the ROM, then check transfer. Two initial jobs, four additional validation jobs. Addresses complaint 4 and regressions in 1–3.**

   **J4/J5:** Stock and candidate ROM, identical setup and player script, bridge-only, no diagnostic writes. Verify loaded bytes first.

   Proposed acceptance criterion: the candidate produces purposeful progress within **240 emulated frames** of the diagnosed failure and does not relatch during the next 3,000 frames. That is an acceptance limit, not a claim that the native counter measures frames.

   Inspect damage, careless commitments, guard holds, and movement outcomes. Reject repeated replanning that merely produces more whiffs.

   If this passes, use **four more jobs** for stock/candidate pairs on one different character and one changed geometry or opponent-position case. Include legitimate waiting states.

   **Decision:** Ship a narrowly described freeze repair only if it transfers without disabling valid waits.

   **Falsifier:** The benefit depends on an absolute frame number, a heap address, one opponent movement, or restored stock bytes. Any of those invalidates the claimed repair.

6. **Decode only enough attack policy to repair one careless choice. Two static passes; up to two discovery jobs, then two A/B jobs. Addresses complaint 1 and prepares complaint 2.**

   **Question:** Which existing field decides whether a particular attack is feasible?

   Begin with the known `op_b_03` records for ids 1, 2, 5, and 6. Follow `0x021751CC` into the actual field consumers. The resolver already reads signed spatial-looking fields at `0x0217557C–0x021755C4` and forwards them to `0x0207B22C`. Trace through that call before assigning units or calling these attack ranges.

   Decode the high byte at record `+0x0C`, the optional header groups, and the sub-record `+0x14/+0x16` pair only where a consumer uses them. Their ordered values do not establish timing semantics.

   Use one compact script containing near/far, facing, and target-state cases. Spend a second instrumented job only where static tracing leaves a specific ambiguity.

   **Decision and patch unlocked:** Prefer a character-specific eligibility/range data correction. It must reject a documented impossible attack while retaining a documented valid one.

   **Build gate:** AIPM files are DSCP/LZ77 containers. A decompressed edit is not directly a ROM byte edit. Recompression must fit the existing allocation, or the builder must correctly update NitroFS allocation information. Independently decompress the patched ROM’s file and compare it with the intended payload.

   **Falsifier:** The field controls presentation, collision markers, or something other than decision eligibility; or changing it only suppresses attacks without improving feasible choices. Do not infer semantics from corpus correlations alone.

7. **Test whether the existing opponent model can identify punish windows. One bounded static pass; up to two discovery jobs, then two A/B jobs. Addresses complaint 2.**

   **Question:** Does an existing input distinguish actionable recovery from ordinary attack, guard, or idle?

   Establish the identity and writer of `s8[*(ctx+4)+8]`. Keep it separate from `fighter+0x18`. The constructor lookup makes “opponent combat state” a hypothesis requiring proof.

   Trace real target-state, vulnerability, and timing inputs into eligibility and commitment. Use the corrected table at `0x02181438` only if its consumers demonstrate a relevant role.

   Script verified whiff recovery, blocked recovery, and a matched non-opening. Do not count every attack state or every landing as punishable; the physics record shows that some movement lockouts still permit attacks.

   **Decision and patch unlocked:** If existing inputs and a populated response already express the distinction, change that response mapping or eligibility condition. If they do not, specify a small code predicate using proved inputs before considering injection.

   **Falsifier:** The supposed signal tracks character/koma metadata, the opportunity closes before any legal response could land, or the candidate merely attacks more often in both opening and non-opening controls.

   If no suitable resident implementation fits, punishment remains blocked. Renaming ids does not close that gap.

8. **Establish the self-KO path before touching bounds. Two static passes; up to three discovery/intervention jobs, then two A/B jobs. Addresses complaint 3.**

   **Question:** Does the CPU issue the movement that causes departure, and does the suspected bounds block participate?

   First inspect existing captures for a real autonomous event. The prior walk-off fixture had no changing AI decision loop and zero bounds-block hits; it cannot establish the proposed cause. [Recorded limitation](../../../docs/research/side-quests/cpu-ai-levels.md:868).

   Obtain one bridge-only event with autonomous CPU input, then one matched instrumented replay. Watch:

   - `0x021778B0–0x021778F4`, including comparison operands and resulting mask.
   - Live `BattleAIMove+0x150/+0x158`.
   - Engine wall flags at `[[r8+0x10]+0x78]`.
   - Movement commands, velocity, supporting surface, wall-break state, and subsequent KO outcome.

   Trace the live collision/surface source from the engine writers around `0x0207ED2C/0x0207ED88`. Reconcile walk walls, supporting floor, and outer containment. The three extents need not represent the same constraint, and the left floor observations do not even form one intersecting bracket. [Geometry evidence](../../../docs/confirmed-facts/physics.md:1407).

   **Decision and patch unlocked:**

   - If the bounds block participates and its bad values cause the bad movement permission, test initialization from the proved geometry source.
   - If the block is bypassed or its output ignored, repair the actual movement eligibility path.
   - If departure results from an attack’s displacement, a movement-only guard is insufficient.

   Reserve the third diagnostic job for one causal intervention. Then A/B the verified ROM.

   **Falsifier:** The event is knockback or recovery rather than self-KO; the bounds block is absent; corrected values do not change the responsible command; or the proposed geometry protects walls while still allowing unsupported movement.

**The single most likely patch is a repair to phase-1 handling of an expired or failed movement request.**

The mechanism would connect the timeout/failure result to the existing reset/replan logic, allowing a new valid movement or attack decision instead of holding phase 1 indefinitely. The strongest current targets are `0x02177BA4–0x02177BE4` and `0x0217B0F0–0x0217B4E8`, with `0x02176D64` supplying the request result.

That is a candidate mechanism, not a justified replacement instruction yet. Its decisive falsifier is straightforward: **the corrected transition executes, but the CPU still cannot make purposeful progress without the player changing state or position**. In that case, the repair addresses a symptom, and the blocked geometry or eligibility decision remains the problem.

The concrete budget is:

| Milestone | Static/build passes | Emulator jobs |
|---|---:|---:|
| Freeze candidate ready for ROM A/B | 4 | 3 |
| First scored ROM A/B complete | 4 total | 5 total |
| Freeze repair checked on two additional cases | 4 total, plus any necessary revision | 9 total |
| Fixture recreation, if no usable pre-load checkpoint exists | Setup work | Allow 2 additional jobs |

These are **stop budgets**, not promises of success. If three diagnostic jobs do not isolate a transition whose repair produces real progress, stop the freeze patch attempt and record the remaining blocker.

A freeze-only release would improve one explicitly defined judgement failure. It would establish nothing about attack choice, punishment, or self-preservation. Those claims require the separate gates above; none should inherit credit from increased activity or from eliminating the frozen tail.

---

## Step 6, first static pass (2026-09-28): the field that decides an attack's eligibility

Step 6 asks **which existing field decides whether a particular attack is feasible**. The answer is
the **AIPM sub-record's four leading `s16` fields**, and they decide it **statically**, through the
availability-mask builder. Astra's nominated fields — the high byte of `+0x0C`, the optional header
groups, the `+0x14/+0x16` pair — are **not** the eligibility fields.

### The builder, re-read from bytes

`0x02174330` (ov11) is the only writer of the nine availability words `+0x84`…`+0xA4` anywhere in
ov11: `query.py search-imm 0x84|0x90|0x9C` finds stores only at `0x02174868`, `0x021748B0`,
`0x021748F8`. Its first loop, `0x021747EC`–`0x0217491C`, runs for every id 1..23 and every
sub-record of that id's record: **[M]**

```
02174824  ldrsh fp, [r1]        ; s16[+0x00]
02174828  ldrsh r3, [r1, #4]    ; s16[+0x04]
0217482C  add   r3, fp, r3      ; A = s16[+0x00] + s16[+0x04]
02174830  cmp   r3, #0xa0       ; A >= 0xA0 -> +0x8C
02174844  cmp   r3, #0x50       ; A <  0x50 -> +0x84 ; else +0x88
0217486C  ldrsh fp, [r1, #2]    ; s16[+0x02]
02174870  ldrsh r3, [r1, #6]    ; s16[+0x06]
02174874  sub   r3, fp, r3      ; B = s16[+0x02] - s16[+0x06] -> +0x90 / +0x94 / +0x98
021748BC  add   r3, fp, r3      ; C = s16[+0x02] + s16[+0x06] -> +0x9C / +0xA0 / +0xA4
```

`orr r3, r3, sl, lsl r8` (`sl = 1`, `r8` = the id) sets bit *id* in the chosen word. Absent records
and zero-length records contribute nothing. **[M]**

A **second** loop, `0x0217493C`–`0x021749D4`, covers ids 1..12 (skipping 9 and 10) and stores at
`+0xC5` the id whose sub-record `s16[+0x14]` is the **minimum** among sub-records with `A >= 0x50`.
So `+0x14` does have a consumer — a "nearest" pick — but it is not the pick's eligibility. **[M]**

### The pick reads three of the nine words, and the band byte is inert for it

`0x0217AE0C`–`0x0217AE60` picks the band from `AI+0x10A` (`>0xA0` → 2, `<=0x50` → 0, else 1) and
ORs three words into `AI+0x48` through `0x0217B0A8/0x0217B0C0/0x0217B0D8`:

| band | words OR'd |
|---|---|
| 0 | `+0x84`, `+0x90`, `+0x9C` |
| 1 | `+0x88`, `+0x94`, `+0xA0` |
| 2 | `+0x8C`, `+0x98`, `+0xA4` |

then `& 0x7E` keeps bits 1–6.

**Reproduced offline** (`scripts/analysis/ai_mask_builder.py`) over all 74 `_b_` files: **every band
yields `0x7E` for 72 of them.** `AI+0x48 == 0x7E` is therefore true **by construction**, not by
fixture accident — §1.3.1's measurement becomes a theorem, and it holds for every battle character
and every band. The two exceptions are `db_b_10` (`0x3E` in every band: bit 6 never sets) and
`dt_b_04` (`0x00`: all 14 of its records are empty).

**Consequence for §1.2's "spacing ladder".** The band byte cannot change the pick's choice set for
72 of 74 battle characters, because all three bands give `0x7E`. The ladder is **inert for the
`AI+0x48` pick**; it can only matter to the second, unclamped consumer `0x0217C16C`. §1.2's "the
most promising thing in this document" is **withdrawn for the pick**.

### What this says about careless attacks

The generic pick has **no distance, facing, or target-state input at all**. It draws among whichever
of ids 1–6 survive the novelty valves, and for 72 of 74 characters all six are available at every
distance. Live state reaches behaviour only through (a) the novelty valves on bits 1–6, (b) the
reaction table at `0x02181438`, and (c) the direct-issue path. So the structural cause of "attacks
that cannot connect" is that **the pick is not the mechanism that could prevent them** — there is
nothing in it to gate on range. A repair has to add a gate or move the decision; retuning a field
that already exists cannot fix it. **[I]**

**The only data lever on the pick's choice set is record presence.** Every value of A, B and C lands
in exactly one band, and all three bands give `0x7E`, so moving a sub-record's quartet between bands
**cannot** change the pick. The only edits that can are `array[slot] = 0xFFFFFFFF` (absent) or
`count = 0` (empty) — which is exactly how `db_b_10` loses id 6 and `dt_b_04` loses all of them.
That lever is blunt and distance-independent: it suppresses an attack everywhere rather than where
it cannot connect, which is the plan's own second falsifier clause ("changing it only suppresses
attacks without improving feasible choices"). **[M]**

### Correction: the nine words sit one dereference further than §1.3.1 records

The reader does `ldr r0,[r0]` (`0x0217B0A8`) and the caller passes `[r4, #0x24]` (`0x0217AE18`), so
the word is `[[AI+0x24] + 0x84 + band*4]`, **not** `[AI+0x24] + 0x84 + band*4`. §1.3.1's table gives
absolute addresses `0x023A4284/0x023A4290/0x023A429C`, which is `[AI+0x24] + 0x84` — one dereference
short, and the capture confirms that address holds `0xC4000001` while the mask words are elsewhere.
`ctx = [[AI+0x24]]` is the object carrying both the block (`ctx+0xC`, the `AIPM` payload) and the
nine words (`ctx+0x84`…): live, `ctx = 0x022606A0` and the block is `0x02263400`. The builder returns
a separate 0x40-byte handle that the caller stores at `[AI+0x24]` (`0x023A4200` here), and that
handle's `+0` is `ctx`. **[M]**

Where the builder *writes* the words is less settled than the first draft of this section claimed.
It writes into `r6`, its first argument (`0x0217433C mov r6, r0`), but the caller passes `[AI+0x1c]`,
which in this capture is `0x023CA5D0` — **not** `ctx`. The epilogue advances `r6` by `0xcc` inside a
list walk (`0x02174D4C`, `0x02174D58`), so the builder writes a family of 0xcc-strided objects and
`ctx` is one of them. The exact list membership is not pinned; what *is* pinned is that the object
the **pick** reads carries the reproduced words.

So `0xC4000001 / 0x023A01FF / 0x0000C100` are the contents of the **handle + 0x84**, not of the mask
object, and the "independent match" §1.3.2 used to confirm object identity was two reads of the same
wrong address. The conclusion that survives is the one measured directly at `AI+0x48`.

### Confirmed live (2026-09-28, one bridge-only job)

`<TMP>/ai-step6/confirm_step6.py` loaded the fixture with `keep_neutral` and read the chain.
The fixture's CPU is **`jj_b_01`** (Jotaro) — the block header and the words agree, and the fixture's
own name says so.

| read | value |
|---|---|
| `AI+0x24` (handle) | `0x023A4200` |
| `[handle] = ctx` | `0x022606A0` |
| `ctx+0xC` (block) | `0x02263400`, head `41 49 50 4d …` (`AIPM`) |
| `AI+0x48` | `0x7E` |
| `AI+0x10A` | `0x50` → band 0 |
| `ctx+0x74` (skip mask) | `0x007F8000` = ids 15..22 |
| `ctx+0xC5` (nearest id) | `4` |

`ctx+0x84..+0xA4` live:
`0000676A 00005094 00004000 000077FE 00000000 00000000 000077FE 00000000 00000000`.

**The reproduction matches on bits 1..14 for `jj_b_01` and for no other file.** Every bit where the
full reproduction differs is a *skipped* id: `+0x74 = 0x007F8000` makes the loop skip ids 15..22, so
the reproduction's bits 15–17 are expected extras and the live words correctly lack them.
`ai_mask_builder.py --live <nine words>` re-runs the comparison.

Three things this settles at once:

- **The builder's arithmetic is right.** The nine words are `jj_b_01`'s sub-record quartets, bucketed
  exactly as the disassembly says. The mechanism and the field are confirmed together.
- **The band byte is inert, live.** All three bands OR to `& 0x7E == 0x7E` on this character's real
  data, so the pick's six choices are ids 1–6 whatever `AI+0x10A` says.
- **The object correction is right.** `ctx = 0x022606A0`, not `0x023A4200`, carries the block at
  `+0xC` and the words at `+0x84`; `0x023A4284` still holds `0xC4000001`, which is the handle's
  field. The apparent "second writer" for bits 0 and ≥24 was that handle, not the mask: the real
  words carry no bits outside 1..23.

**Ids 15..22 are excluded from the nine words by design**, not by absence: `+0x74` marks them, the
loop skips them, and the first phase adds nothing to these words for them. So the generic pick
cannot reach them at any band; they come only from the reaction table and the direct-issue path.

### What is still open

- `[AI+0x74]`'s writer — which phase marks ids 15..22 and why — is not decoded. It is the one
  structural gap left in the builder.
- Which of A/B/C is reach, height or reach-back is not established: the reproduction gives the
  buckets, not the units. The plan's `+0x14/+0x16` pair is a *different* mechanism (`+0xC5`).
- Astra's other two candidates, the `+0x0C` high byte and the `+0x10..+0x9B` "header groups", are
  still undecoded. Neither is on the pick's path, so neither can be the eligibility field; what
  they are is open but not on step 6's critical path.

---

## Step 7, first static pass + first discovery job (2026-09-28)

Step 7 asks **whether an existing input distinguishes actionable recovery from ordinary attack,
guard, or idle**. The answer is **no**, and the byte the code nominates is not a state at all.

### The accessor, and its writer

`0x02174F4C` is the accessor: `ldr r0,[r0,4]; ldrb r0,[r0,8]`. The 13/14 remap reads the same byte
**signed** inline (`0x02174EE8 ldrsb`), so the sign matters: values below 3 drive the id down.
29 caller references.

`[ctx+4]`'s writer is `0x021745D0`, **inside the mask builder `0x02174330`** — the same function
that builds the nine availability words — and it stores `0x02076CE0(table, row, col)`:

```
[ctx+4] = [[table + col*20 + row*4 + 8] + 0x34]
```

`row`/`col` come from `ctx+0xC2`/`ctx+0xC3`, themselves derived from the settings record at `[ctx]`
(`0x0217454C`, `0x02174568`). So the byte is **constructed from a grid lookup**, not read from the
opponent per frame.

### Measured: it is constant

One bridge-only replay, 3001 frames, stock fixture, no input script. The CPU attacked (state 9, 188
frames), dream-attacked (11, 113), walked (1, 82), went airborne (6, 28); both fighters crossed the
stage (`p1x` 0x34232→0x29a4b, `p2x` 0x2ec66→0x2446f). Over all of it:

| watch | value |
|---|---|
| `osb` = `[[ctx+4]+8]` | **3 on all 3001 frames** |
| `osb9` | 0 on all frames |
| `objA+0x18` / `objB+0x18` | 136 / 250, constant |
| `objA+0x68` / `objB+0x68` | 0x36D / 0x126, constant |
| CPU battleObj `+0x18` | 0, 1, 6, 9, 11 (varies) |
| `ctx+0x60` = `ctx+0x64` | 0x2800, then 0x2200 after the rebuild |
| `AI+0x48` | 0x7E on 2991 frames, 0 for the first 10 |

`osb` equals neither entity's `+0x18` nor the CPU's state on any frame.

**And the two branches that would use it as a state selector cannot fire anyway.** `0x0217E864`
needs `osb == 1` *and* `[sl+0x68] & 0x10000`; `0x0217E880` needs `osb == 2` *and*
`[sl+0x68] & 0x20000`. Neither entity's `+0x68` carries those bits, so both branches are dead in
this fixture whatever `osb` is.

**So the plan's falsifier fires: the supposed signal is not a live opponent state.**

### Two further results

- **The range gate is structurally real but inert.** `0x0217E8C0` compares `s16[record+0xB0]` — the
  first sub-record's `+0x14`, 0..280 — against `s16[ctx+0x60]`, a **per-build constant** (0x2800,
  then 0x2200). A 0..280 value never reaches 10240, so the gate never blocks. Astra's `+0x14` pair
  does gate eligibility here (a second consumer beside the `+0xC5` minimum), but as shipped it does
  not bite.
- **The AI object is rebuilt mid-fight.** At ~frame 465 `ctx` moves 0x22606a0 → 0x226076c, the block
  0x2263400 → 0x2260de0, and `[ctx]` 0x21df7d8 → 0x21df828 (0x50 apart, an array stride). `AI+0x24`
  is therefore not stable across a fight and any watch of it must handle the change.

### What step 7 asks next

Its "decision and patch unlocked" has two arms. The first — *existing inputs already express the
distinction, so change the response mapping* — is **closed by the above**. The second is *"specify a
small code predicate using proved inputs"*. The proved live inputs in this fixture are the two
fighters' **positions** and the CPU's own state; the entity flags (`+0x68`) and `+0x18` bytes are
constant and `osb` is constant. So a punish predicate has to be built from position, the CPU's own
state and the opponent's animation — **not from any existing "opponent state" field, because none
exists.**

> **Amended by the spec below.** The opponent's fighter object *is* resolvable — the fighter table
> at `0x021DEB3C` — so the opponent's own `+0x18` state code and `+0x114` hitstun timer are readable
> once that pointer is taken; the **animation frame** is the only input still missing. "None exists"
> above means "no field the AI currently reads", which remains true.

---

## Step 7, the predicate specification (2026-09-28)

> **CORRECTION 2026-09-28, after an adversarial check** (codex `gpt-6-sol`, read-only; every
> refutation below was re-verified here against the ROM bytes). The first version of this section
> made five claims that are wrong. Each is corrected in place, and named here so the earlier text
> is not trusted:
>
> 1. **"nothing in ov11 reads `+0x110`" is false.** `0x0217FD4C` and `0x021801A4` both read the
>    CPU's **own** fighter `+0x110` (`ldr r0,[AI+0x20]; add r0,r0,#0x100; ldrsh r0,[r0,#0x10]`),
>    gated on its own `+0x100`. The corrected claim is narrower — §2.
> 2. **`+0x110` is not a landing-lag field.** It reads 0 on every landing measured (47/47 rows,
>    physics §6.6); it is written only on an **unblocked hit** frame (physics §4.5). §1.
> 3. **The `6→13→0` "whiff signature" was overgeneralised.** It is one Kakashi air-X trace, and
>    the state-13 window is identical hit or whiff. §1.
> 4. **`0x02230D60`/`0x02230E00`/`0x0224EF00` are the *second* pointer's, not P1's.** P1's object
>    is the stable one — the opposite of what the first version said. §3.
> 5. **The pseudocode's `and`/`or` precedence did not express the intent, and the proposed veto
>    return was inverted** (`0x0217ADAC bne` skips the entry when the return is nonzero). §4, §5.

**The question.** What is the smallest predicate over inputs the AI already reads that distinguishes
an actionable opponent recovery from an ordinary attack, guard or idle, and where could it live?

**The answer in one line.** None exists today, and the reason is exact: **no ov11 site has been
found that reads the opponent's state code.** The fields that would carry the distinction are proved
and named below, and — as the check showed — the opponent's fighter object *is* resolvable.

### 1. What "actionable recovery" is in this engine's own terms [M]

The fighter object carries the state code at `+0x18` — two writers only, the commit routine
`0x02159CC4` and the reset `0x02159C90` (`docs/confirmed-facts/physics.md`, the state-code table):

| code | state | | code | state |
|---|---|---|---|---|
| 0 | idle | | 8 | hitstun |
| 1 | walk | | 9 | attack |
| 3 | guard | | 12 | SELECT ultimate |
| 4 | jump start | | 13 | landing |
| 6 | airborne | | | |

**`fighter+0x114`** is the **hitstun timer** (s16, 8.8 fixed frames, physics §4).

**`fighter+0x110` is *not* a landing timer.** It is `clamp(M[0x171] + 20, 24, 180)`, written by ov6
`0x0215B520` **only on unblocked hit frames**, never on blocked hits (physics §4.5); it counts down
after the launched victim lands (physics §4.5). A **self-initiated landing** — jump, air attack,
whiffed or connected — leaves it at **0**: "`obj+0x110` reads 0 on every landing measured: there is
no landing countdown field; the window is realised through the state machine" (physics §6.6, 47/47
rows). So on the *opponent*, `+0x110 > 0` means "I have hit them and they are still recovering" — a
combo-continuation signal, not a whiff window.

The landing window is therefore the **state-13 dwell**, which is a *duration*, not a readable
counter: `10 + 12 × (air attacks this hop) + 9 × (double-jumped ? 1 : 0)` (physics §6.6, measured
47/47 on three characters). Two further corrections follow: the `6 → 13 → 0` trace is **Kakashi air
X**, not a general whiff rule, and "hit or whiff makes no difference" to that window — so state 13
does not by itself distinguish a whiffed attack from one that connected, and does not need to:
either way the opponent is in landing recovery. `M+0x16C` is *not* a whiff signature either, because
arm9 `0x02051864` clears it every frame.

The two recovery signals that survive as usable are therefore:

- **state 13** — the opponent is in landing recovery; the window is the law above.
- **state 8 with `+0x114 > 0`** — the opponent is locked in hitstun and cannot act at all.

### 2. What the AI reads today [M]

`[[AI+0x20]+0x18]` is the **CPU's own** state (`[AI+0x20]` = P2OBJ = `0x0224EF00`), and it gates the
finalizer's `0x0217BFE0` byte-table scan.

**The CPU's own `+0x110` is read twice** — `0x0217FD4C` (`ldr r0,[AI+0x20]; add r0,r0,#0x100;
ldrh r1,[r0]; sub r1,r1,#5; cmp r1,#1; bhi …; ldrsh r0,[r0,#0x10]`, so gated on its own `+0x100 ∈
{5,6}`) and `0x021801A4` (`cmp r0,#8`). Both are the *own* fighter, reached through `[AI+0x20]`;
neither is the opponent's.

What the AI reads of the **other** fighter is position-shaped, not state-shaped: `0x0217E834` walks
the node list at `[handle+0x1c]`, takes each node's entity from `[node+8]` (`0x0217E848`), and reads
that entity's `+0x68` flags (`0x0217E850`) and `+0xC2`/`+0xC3` cell coordinates (`0x0217E8C8`). The
nearby `+0xB0` read (`0x0217E8B8`) is **not** the entity's — it is a resolved AIPM **record's**,
compared against the per-build constant `ctx+0x60`.

**No ov11 site has been found that reads the opponent's `+0x18`, `+0x110` or `+0x114`.** That is a
search result over the disassembly, not a proof; the only candidate ever nominated, the byte at
`[[ctx+4]+8]`, is a constructed grid lookup and constant in the fixture (pass above).

### 3. The inputs, and where the opponent's object comes from

| input | source | width | why the predicate needs it |
|---|---|---|---|
| opponent's state code | `OPPOBJ+0x18` | u8 | tells 13 (landing) and 8 (hitstun) from 0, 3 and 9 |
| opponent's hitstun timer | `OPPOBJ+0x114` | s16 8.8 | whether the opponent can still act |
| opponent's post-hit recovery | `OPPOBJ+0x110` | u16 | nonzero only if the CPU has already hit them |
| distance to the opponent | derived | — | the predicate is range-dependent |

**The opponent's fighter object is resolvable, and the first version said it was not.** The fighter
table at **`0x021DEB3C` holds exactly two live pointers** — `[0]` is P1's object, **stable across
states**, and `[1]` is the victim/opponent object, which **differs per deck** (`0x02230D60`,
`0x02230E00`, `0x0224EF00`, `0x0222CFE0`, `0x022301C0` all seen) — physics.md, "the victim object
address is per-deck", and `0x02228E80` is identified there as **P1's** in this fixture. So: resolve
the opponent from `0x021DEB3C + 4` (or `+0` when the CPU is the second slot), never hard-code an
address. That is the pointer the predicate needs, and it exists.

### 3.1 The motion/animation object: located, one link unproven (2026-09-28 static pass)

The previous version said no chain to the opponent's motion object existed. A bounded static pass
(no emulator; every address read in the bytes) splits the question in two. The per-fighter
**animation id** is a clean field; the **frame** is not on the fighter at all.

**The animation id is one dereference from the fighter.** `char+0x1A0` is the CharaData object
(`0x1C4`, alloc ov6 `0x0215F064`, `BattleCharaDataLoad.cpp`). Its `+0x1BC` is a u32 animation id in
`0..23`:

- only writer `0x0215F29C str r5,[r6,#0x1bc]` inside `0x0215F278(CharaData, id)`; the allocation
  zeroes it at `0x0215F080`;
- callers pass an integer — `0x02157450(char, id)` does `r0=[char+0x1A0]; bl 0x0215F278`;
- a reader clamps it — `0x021573DC ldr r1,[r0,#0x1bc]; cmp r1,#0x17; movhi r1,#0` then re-issues;
  `0x0215DF38 cmp r1,#6` re-selects idle.

Chain: `char → [char+0x1A0] → CharaData+0x1BC`. **[D]**

**The frame is not a fighter field; it is the middleware ALMT clip's evaluated frame.**

- getter = clip vtable `+0x14C` = arm9 `0x0204ADE4 ldrh r0,[r0,#0x2a]; bx lr`;
- only writer = the clip's seek method, arm9 `0x0201F12C strh r4,[sl,#0x2a]` inside `0x0201F11C`
  (clip vtable `+0xD4`), which stores the frame it is asked to evaluate. No `+0x2A` increment exists
  anywhere in arm9 or ov6, so the value reflects whatever frame the owner last requested;
- the clip class is allocated by arm9 `0x0204B04C` (`0x74` bytes, ctor `0x0201E744`), with the
  "ALMT" format-tag accessor at `0x0204B024`; total frames is probably `clip+0x68` (vtable `+0x10C`
  = `0x0204B084`) — **[D], medium**, a copy of a source halfword, not proven equal to ALMT entry `+4`.

**The chain from a fighter to its clip runs through the render model:**

```
char+0x1B8          ; the 0x2C model ctrl, made by ov6 0x02161608(entity);
                    ;   sole writer 0x02156C2C str r0,[r4,#0x1b8]
  -> [ctrl+8]       ; the model            (0x02161698)
  -> [model+4]      ; the animation player (0x021616A4; 0x02156C64 ldr r0,[r0,#4])
  -> [player+0x68]  ; the current ALMT clip (0x02155954 ldr r0,[r5,#0x68], r5=[x+4])
  -> [clip+0x2A]    ; the current frame
```

`ctrl → model → player` is confirmed: `0x02156C54-0x02156C8C` seeks `[model+4]` through vtable
`+0xD4`, and `0x021616A4-0x021616B8` registers the same `[model+4]`. `player+0x68 = clip` is
supported by `0x0215594C-0x02155990`, where a wrapper's `+4` is read, its `+0x68` taken as the clip,
and the clip's frame (`+0x14C`) re-applied to another player — but that function's wrapper is **not
proven** to be the same `[model+4]`, so the depth is **[D], medium**.

**A second, shallower candidate.** `char+0x1BC` is a pointer set once at creation
(`0x02156B00 str r1,[r4,#0x1bc]`, `r1=[descriptor+4]`), and `[[char+0x1BC]+4]` is consumed as a seek
frame — `0x02156C84 ldr r1,[r1,#4]` immediately before the vtable-`+0xD4` call; `0x021544C8` is the
same shape; `0x0215F818` passes it on a re-bind. If that object is updated per frame it is the
cheapest read (one dereference); if it is a creation-time snapshot it is not. Not decided
statically. **[D], open**

**Reachability from ov11 is still the live gap.** ov11 does not reference any of these: no literal in
the ROM targets `0x021DEB3C` (checked over `[0x021DEA00,0x021DED00]`), no ov11 site reads a fighter's
`+0x1A0`/`+0x1B8`/`+0x1BC`, and the fighter-table address is never hardcoded.

ov11 does hold a per-player slot array, and it may not need the table. `BattleAI_Create` (ov11
`0x02172A60`) builds one slot per player — the count is `r6 = [root+0x158] & 0xff`,
`root = [0x02172960]` — at `manager+0xa8`, stride `0x10C` (`0x02172DC4`). (Whether that rule field
counts players or only AI-controlled players is not settled here.) The phase-1 handler's own AI
pointer *is* its slot: it computes `r5 = r8 + 0xa8 + [AI+0x38]*0x10C` and then reads `[r5+0x20]` as
the fighter (`0x0217B104`-`0x0217B128`, `0x0217B410`). So the opponent's slot is the sibling
`AI ± 0x10C`, and `[sibling+0x20]` would be the opponent's fighter object. The writer of `+0x20` is
ov11 `0x02173024` (`mla r4, idx, 0x10C, manager+0xa8; str r1, [r4, #0x20]`); it has **no direct or
literal caller** in the image (a computed call), so whether the human player's slot is populated is
**not proved statically** — the capture must read it. **That, or the table's in-code base, is the
remaining static task, and §6's capture can pin the frame link in the same run.**

### 4. The predicate

Written with explicit parentheses, because the first version's `and`-before-`or` precedence made
`A or B or (C and D and E)` rather than what was intended:

```
punishable :=
      cpu.state in {0, 1}                               # the CPU is free to act
  and distance(cpu, opp) <= reach(punish_move)          # and in range
  and (
          opp.state == 13                               # landing recovery (window: 10+12a+9d)
       or (opp.state == 8  and opp.hitstun(+0x114) > 0) # locked in hitstun
       or (opp.state == 9  and move_in_recovery(opp))   # attack tail -- needs the motion frame
      )
```

`move_in_recovery` is the one clause with no proved field behind it: state 9 spans the whole attack,
and the motion object's frame is what says which part of it the opponent is in. It is exactly why
the plan says *"do not count every attack state or every landing as punishable."* The other clauses
are proved.

`opp.post_hit_recovery(+0x110) > 0` is deliberately **not** a clause: it is nonzero only when the
CPU has already hit the opponent, so it is a combo signal, not an opening signal.

### 5. The resident location

The predicate's natural host is the **existing per-entry test** in the reaction loop. `0x0217ADA4`
calls `0x0217AB28([AI+0x2C], table_byte1)` once per entry, and **`0x0217ADAC bne 0x217addc` skips
the entry when the return is nonzero** — so the polarity is *veto-on-nonzero*, not
*allow-on-true*. Entries 11 and 12 carry byte 1 = 4 and issue ids 13 and 14 (stock bytes
`(13,4,26)`, `(14,4,26)`), the band the census watched. A predicate host here must therefore
return **`!punishable`** for class 4, leaving every other class untouched. (The first version said
to return `punishable`, which is the exact inverse — it would skip the band precisely when the
opponent *was* recovering.)

That is the smallest host: one call site, no new table, no new branch, and the "skip this entry"
semantics already exist. ov11 has ~91 bytes of contiguous zero space (§3.24) if a stub is needed;
the byte count does not by itself prove a stub fits safely.

Two caveats on the host, both from the check:
- byte 1 is a **novelty/veto class**, not a measured semantic (§4.4). "Punish band" is an
  *inference* from ids 13/14 being the opponent-state-remapped pair, not a measured meaning; the
  live evidence is that ids 13/14 fired 17 times in the patched arm of the funnel census and 0
  times in stock.
- `0x0217AB28` itself is a bitmask test — "has slot *n* already been consumed?" — over the words at
  `[AI+0x2C]+0x34`, testing bit `n & 31`. Overriding its return for one class is a new meaning for
  an existing call site, not a use of an existing "veto" abstraction.

The predicate **cannot** be hosted on the `AI+0x48` pick: that mask is clamped to bits 1–6, so ids
13/14 can never enter it (step 6).

### 6. The measurement that justifies it, and the falsifier

The spec is only worth building if the punish band currently fires **wrongly**. So the first job is
not an A/B of a patch; it is a capture that logs, for every frame ids 13/14 are issued, the
opponent's `+0x18`, `+0x114` and `+0x110` — resolved through `[0x021DEB3C]`/`[0x021DEB3C+4]`, which
also *proves the resolver works* on the fixture. If every punish-band issue already lands in a
proved recovery, the predicate adds nothing and the work stops there. If most do not, the predicate
has a measured target.

#### 6.1 Result, from the existing funnel census (2026-09-29; zero emulator jobs)

The measurement was already in hand. `cpu-ai-levels.md` §3.28's funnel census (fixture
`pc-kakashi-npc-jotaro-fightcpu`, arm B = stock + the `idle_in_action_set` RAM tier, 3842 frames)
logged **both fighters' state codes every frame** (`st1 = *(u8*)0x02228E98` = P1 +0x18,
`st2 = *(u8*)0x0224EF18` = P2 +0x18) and every issue with its id and producer
(`<TMP>/ai-funnel/`). The AI is P2 (slot 1, `0x02181C14`), so the opponent is **P1 = `st1`**.

Of the 78 issues in arm B, **17 carried post-id 13 or 14**. On those 17:

| frames (rel.) | producer | id | opp `st1` |
|---|---|---|---|
| 648 | `mask_enum_B` | 14 | 0 |
| 797, 803, 809, 815, 821 | `mask_enum_B` | 13 | 0 |
| 914 | `stack_s8_table` | 14 | 0 |
| 1612, 1689 | `reaction_table_AI3A` | 14 | 0 |
| 1874 | `stack_s8_table` | 14 | 0 |
| 2156 | `reaction_table_AI3A` | 13 | 0 |
| 2456 | `mask_enum_B` | 13 | 0 |
| 2462 | `reaction_table_AI3A` | 14 | 0 |
| **3058** | `reaction_table_AI3A` | 13 | **8** |
| 3072 | `stack_s8_table` | 14 | 0 |
| 3599, 3697 | `reaction_table_AI3A` | 14, 13 | 0 |

**16 of 17 fires had the opponent in state 0 (idle)** — not a recovery, by the spec's own predicate.
The ±3-frame window is state 0 throughout for all 16, so no frame alignment rescues them. One fire
(frame 3058) had the opponent in state 8 (hitstun, the spec's second clause), and the CPU itself was
in state 9 (attacking).

**No landing and no attack was ever available to key on.** Arm B's opponent (`st1`) histogram is
`{0: 2628, 8: 1030, 23: 93, 24: 2, 25: 84, 6: 5}` — the opponent is a passive target and is **never
in state 13 (landing) and never in state 9 (attack) on any of the 3842 frames**. So the state-13 and
state-9 clauses of the predicate are **untestable on this fixture**; only "idle" vs "hitstun" is.

**What this settles, and what it does not.**

- *Settled:* the band does fire when the opponent is **not** recovering — 16/17 on an idle
  opponent. The predicate has a measured target, and the "adds nothing, stop" branch does **not**
  fire. It also confirms the resolver premise: P1's `+0x18` is readable and non-trivial here.
- *Also settled, in the other direction:* the band is not *tracking* recoveries either. The opponent
  spent **1030 frames in hitstun (state 8)** and the band fired on **1** of them; it spent **0**
  frames in landing and **0** in attack. So over the whole arm the band's 17 fires bear almost no
  relation to the opponent's state.
- *Not settled:* whether the band would *also* fire on a real recovery. The fixture never presents
  a landing or an attack for the opponent, so "fires wrongly" is confirmed but "fires wrongly
  **instead of** correctly" is not. That needs a fixture whose opponent actually jumps or attacks.
  (State 8 with `+0x114 > 0` is in hand as the hitstun clause, but `+0x114` was not logged, and
  hitstun alone is not the same as hitstun that still forbids acting.)
- *Caveat carried from §3.28/§3.29:* arm B is one GDB-instrumented sample; §3.29 found the patched
  arm deterministic under an `fc`-keyed comparison, but the `torn`/duplicate handling still applies.

**Falsifier (the plan's, restated for this shape):** the candidate merely attacks more often in both
opening and non-opening controls; or the opportunity closes before any legal response could land; or
the "recovery" the predicate keys on is character/koma metadata rather than live state.
