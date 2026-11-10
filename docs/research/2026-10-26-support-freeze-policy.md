# Native support freezing: static analysis

Static pass, 2026-10-26, no emulator. This memo describes the global-freeze mechanism and proposes
capture cells that would measure the open questions; it does not close them. Written by a
reverse-engineering pass and re-checked against raw ROM words through `rom_loader`: `0x02168CCC` tail-calls `0x020282F4`
and `0x02168CE0` tail-calls `0x02028330`; `0x02027F38..0x02027F50` is
`tst [O+0x248], U.mask3C | 0x80000000`; Thumb `0x0214E22C` stores the duration at `B+0x168`, ORs
`1 << user` into `B+0x16B` and sets `B+0x16C`/`B+0x16D`; the literal at `0x0214DDA8` is
`0x0FFDF900`, which keeps `0x00800000` and clears `0x10 << i` for i = 0..3.

Headline answers:
- Global freeze (the user-exempt case-8 path, likely DREAM/UA): both support update objects pause
  (STATIC), the controller by explicit suspension, every NoteTrack by the owner inclusion mask,
  whoever owns the support.
- Is hitstop needed first? **NO** for the traced global-freeze policy. Whether native
  per-fighter hitstop pauses supports is UNMEASURED (no hitstop setter was found); proposed cells
  1 and 2 (section 5) would decide it.
- Proposed capture: four cells, three repeats each (section 5).

Evidence grades: STATIC = instructions or data with addresses; MEASURED = committed capture; INFERRED = a conclusion beyond the directly observed path; UNMEASURED = unresolved behavior or a proposed capture. No emulator was used. 

`A` means ARM9 and `O6` means overlay 6. Instruction sources are `jus_files/analysis/disasm/{arm9,ov6}.txt`; the call index is `analysis/functions.json`. Fresh Thumb decoding of O6 is essential: the precomputed listing prints much of the battle driver as ARM and misses its real calls. Supporting fresh Thumb listings are `2026-10-26-support-freeze-policy/global-freeze-enter-exit.txt` and `global-freeze-request.txt`; the whole-overlay Thumb listing used to find them (1.7 MB) is not committed. Address citations below refer to the ROM instructions, not invented function names.

## 1 scheduler mechanism

[STATIC] The actual ordered update-object walk is A `0x02034500`. It saves the next `U+0x0C` link before running the current object, calls `0x020284C0` for the ordinary dispatch path at `0x02034570`, then advances at `0x02034584–0x02034598`. `0x020347BC/0x020347FC` insert/remove active-list objects and repair the saved next pointer. A `0x0201CCA0` orders insertion using the halfword at `U+0x06`; this order key is distinct from the category mask.

[STATIC] Relevant fields are `U+0x28` flags byte, `U+0x29` auxiliary flags, `U+0x34` owner-group pointer `O`, `U+0x38` pending-event queue, `U+0x3C` category mask and `U+0x40` callback. Constructor A `0x02027034–0x020270B4` links `U+0x20` into `O+0x23C` and copies the current owner from `G+0x24C`, where `G=0x020A0C34`. Therefore `G+0x24C` is an owner pointer, not a mask word.

[STATIC] The run mask is the owner-local inclusion word `O+0x248`. The normal category test is `(O.mask248 & (U.mask3C | 0x80000000)) != 0`, A `0x02027F38–0x02027F50`, `0x02027FDC–0x02027FF4`, `0x02028594–0x020285AC`. With owner bit 31 set, every ordinary category passes. With that bit clear, any overlapping category bit suffices. This is an inclusion test, not an exclusion test.

[STATIC] Local normal-update inhibition also uses `U.flags28 & 0x82` and `U.flags29 & 0x02`, A `0x02027F0C–0x02027F34`, `0x02027FB0–0x02027FD8`. `0x02027EDC` recomputes active-list membership and propagates state to attached children through `0x02027E7C`. The empty-event-queue dispatch at `0x02028608–0x02028634` trusts that list maintenance. A mask poke without recomputation is not equivalent to the native setter.

[STATIC] A `0x0202843C(U, mask)` stores `mask | 0x80000000` in `U+0x3C` and recomputes scheduling; base vtable slot `+0x94` points to it at `0x02099174`. A `0x020316E4(O, mask)` replaces `O+0x248`, walks `O+0x23C` and recomputes eligible objects. Constructor A `0x02031164–0x020311C8` initializes inclusion to `0xFFFFFFFF` and default category to `0x80000000`.

[STATIC, supplied facts retained] The support-manager/controller update category is `0x00800000`, set at O6 `0x02168C30–0x02168C44`; its stored word is consequently `0x80800000`. Each support NoteTrack has category `0x10 << callerIndex`, O6 `0x02157794–0x021577AC`, and its stored word includes the high bit. These are distinct update objects. The controller object updates the manager's live support list, O6 `0x021691CC–0x02169334`; it is not a separate scheduler allocation for every support node.

[STATIC, flag-number clarification] A `0x020282F4` suspends one object by ORing **mask `0x02`**, and A `0x02028330` resumes it by clearing that mask, at `0x0202831C/0x02028358`. This is zero-based bit 1; the supplied phrase "bit2" is accurate only as shorthand for mask value 2, not zero-based bit 2. Both APIs recompute scheduling and remove a pending `0x80020000` event if present.

[STATIC, supplied facts retained] Support creation enables its NoteTrack at O6 `0x02168EB0`; support exit disables it at `0x021692EC–0x021692FC`. Pending events can keep an object scheduled even when its normal callback is inhibited, A `0x02027F54–0x02028030`, `0x020284C0–0x020285AC`. Thus neither list membership nor flags28 alone proves that the NoteTrack runner executed.

[STATIC] A separate owner-wide freeze API exists: `0x020314C0(O,duration)` sets `O+0x244` and every member's flags28 mask `0x80`; `0x02031520` clears them. A `0x02031554` counts down except for zero and `0x7FFFFFFF`, then unfreezes. This is separate from category inclusion and from explicit mask-`0x02` suspension.

## 2 hit-freeze

[STATIC] The suggested A `0x020817EC` is inside hit processing, not a function entry. Its immediate block reads collision-record bytes `+0x0C/+0x0D` and computes knockback, `0x020817EC–0x02081978`. A `0x020823E4–0x02082688` computes damage/modifier results. Neither inspected block writes `O+0x248` or calls a support suspension API. That negative finding covers these blocks only.

[STATIC] The containing A hit receiver `0x02080F14–0x02081A44` accumulates collision/reaction data. For example `0x02081300–0x02081308` adds record byte `+7` to `M+0x171`; it is not a proved hitstop counter. The effect call at `0x02081A24 -> O6 0x02153CE8` dispatches sound/effect creation. Older notes calling the selector fields "hitstop/shake" do not establish a scheduling effect.

[STATIC, supplied facts retained] Kind-0/1 support update O6 `0x0216967C` has no caller-hitstun or hitstop check. The outer manager at `0x0216925C–0x02169278` handles own `P.flags78 & 0x400000` by retirement, not a countdown pause; A `0x0207EE58–0x0207EE78` sets this flag on the terrain/ring-out path. It must not be renamed hitstop. Support callback O6 `0x02157958` only has the known caller state-`0x1B` retirement veto, not a state-8 pause.

[STATIC, supplied facts retained] The NoteTrack runner is O6 `0x02155688–0x02155938`. It checks completion, polls branch slots and dispatches events against the animation playhead. A stationary integer animation frame does not prove the runner was unscheduled: branch polling occurs first. The constructor's immediate invocation at `0x02155490` also needs to be excluded from per-frame call counts.

[MEASURED, supplied fact retained] Caller hits did not change Eve 589's retirement/destruction boundary at call+103. Source: `docs/research/feel-captures/2026-10-14-eve-support-2/logs/s2/c3_stat/{events.json.gz,support-guard.json.gz}`. This does not independently establish nonzero caller hitstop during those rows.

[MEASURED] A separate committed study found no RAM hitstop for its sampled Kakashi B, Kakashi X and Yusuke Spirit Gun contacts: attacker animation, knockback and hitstun countdown advanced. Source: `docs/research/2026-10-08-presentation-lag.md`, verdict and results, with capture bundle `docs/research/2026-10-08-presentation-lag/attempt-2/`. This is evidence about those contacts only, not all attacks.

[UNMEASURED] A dedicated per-fighter hit-freeze counter, its hit-triggered setter and the complete update-suppression path were **not identified**. Consequently this pass cannot prove either "native fighter hitstop never pauses supports" or "it pauses supports." No hitstop mask value or authoritative hitstop writer is assigned. Caller hitstun, own-support damage, ice status and global time-stop must remain separate cases.

[INFERRED] The known independent categories and absence of a caller-state pause in the support controller favor continued support execution during caller-local hitstop. This is a hypothesis for the proposed capture, not a STATIC verdict.

## 3 global freeze (DREAM/UA)

[STATIC] A concrete user-exempt global-freeze mechanism is closed. Let `B=*(u32*)0x02172960`, and `O=*(u32*)(*(u32*)(B+0x140)+4)`. O6 Thumb `0x0214E22C(duration, userIndex)` writes signed16 `B+0x168=duration`, ORs `1<<userIndex` into byte `B+0x16B`, and sets bytes `B+0x16C` and `B+0x16D` to 1, `0x0214E236–0x0214E254`. Repeated requests overwrite duration and accumulate exempt-user bits until restoration.

[STATIC] The battle frame handler O6 Thumb `0x0214DBCC` handles nonzero `B+0x168`. On the pending-entry flag it performs these operations:

- `0x0214DBF4–0x0214DC12` calls A `0x02083810(1)` and two other manager freeze helpers.
- `0x0214DC16–0x0214DC20` calls support helper `0x02168CCC` on `B+0x10C`.
- `0x0214DC24` loads literal `0x0FFDF900` from `0x0214DDA8`. The loop at `0x0214DC2C–0x0214DC72` adds low bit `1<<i` for every exempt player in `B+0x16B`; other fighters get callback toggle `0x02156F6C(fighter,1)`.
- `0x0214DC74–0x0214DC7E` calls A `0x020316E4` on `O` with that inclusion mask. This is a real caller missing from the precomputed ARM listing and functions index.
- `0x0214DC8C–0x0214DC98` decrements the global duration. The following zero-counter frame performs restoration; capture the actual boundary rather than assuming input tick equals freeze-entry tick.

[STATIC] Support helper `0x02168CCC–0x02168CDC` resolves the shared controller update object and tail-calls A `0x020282F4`. Hence the controller is paused by explicit flags28 mask `0x02`, even though the allow mask still includes its category: `0x0FFDF900 & 0x00800000 = 0x00800000`.

[STATIC] Every support NoteTrack category fails the global inclusion test: `0x0FFDF900 & (0x10<<i) = 0` for player indices 0–3. Adding exempt users' **low** bits 0–3 cannot add support bits 4–7. Thus NoteTracks are paused even for supports belonging to the exempt user. Their explicit suspension bit need not change; mask recomputation removes ordinary callback eligibility.

[STATIC] Restoration is O6 Thumb `0x0214DC9C–0x0214DD2A`: clear the freeze bookkeeping, restore inclusion to `0xFFFFFFFF` at `0x0214DCCA`, reverse the other manager freezes, call support helper `0x02168CE0` at `0x0214DCFA`, and reset fighter callback toggles. `0x02168CE0–0x02168CF0` tail-calls A `0x02028330` on the controller. NoteTrack eligibility resumes through the owner-mask setter, subject to its own lifecycle suspension/completion.

[STATIC] O6 `0x02156F6C` switches non-exempt fighter callbacks to `0x02156F48`, which calls hit-receive logic with argument 1 and omits the ordinary state/guard sequence. The exempt-player distinction is therefore explicit in code; "freeze" does not mean every fighter-related callback vanishes.

[STATIC] Known request callers are fighter NoteTrack callback case **8**, O6 `0x02157A88 -> 0x02157C38–0x02157C44`, which passes its duration argument and fighter index; and status handler `0x02159344–0x02159358`, which reads a signed duration from the status data. O6 `0x02159140–0x0215914C` clears the global duration through `0x0214E26C` when slot-0 status 12 is removed.

[INFERRED] The case-8 user-exempt mechanism is the likely shared path for the requested DREAM/UA full-screen freeze. [UNMEASURED] This pass did not bind a specific DREAM/UA animation resource and event to case 8. Therefore the proved statement is **both support update objects pause whenever this mechanism is entered**. It does not establish that every move called DREAM or every SELECT/UA uses it.

[STATIC] Ordinary pause is another mechanism: O6 `0x0214E1D4–0x0214E1F4` calls owner-wide freeze with `0x7FFFFFFF`, and `0x0214E204–0x0214E222` clears it. Do not use pause-menu behavior to prove user-exempt cut-in behavior.

## 4 Does the global freeze depend on hitstop?

The global-freeze mechanism has a duration, exempt-player bits, an owner-mask setter and explicit controller suspension. The separate per-fighter hitstop path remains unidentified; its effects on supports are unmeasured.

## 5 Proposed capture cells

[UNMEASURED, proposed protocol] Run **each cell three times from the same baseline state**, with a matched no-trigger/whiff control for each trigger cell. Use accepted support creation as relative tick `t=0`; feed the support press on absolute tick 6. Record input-feed, processed-input and actual contact/freeze-entry ticks separately. Absolute trigger ticks in the table assume creation was tick 6; shift them by any measured acceptance delay, preserving the relative schedule. Continue through destruction/re-call eligibility and at least 30 ticks after every freeze ends. Do not identify freeze from rendered cells alone.

[UNMEASURED, common per-tick log L] Resolve pointers from each new call rather than retaining old heap addresses. Log DS tick; support panel/caller index; controller-manager `U_C` and support NoteTrack `U_N` pointers; each `flags28`, `flags29`, category `+0x3C`, owner `+0x34` and pending queue `+0x38`; each owner's inclusion `+0x248` and freeze count `+0x244`; and actual callback-entry counts at O6 `0x021691CC` and `0x02155688`, correlated to the correct support.

[UNMEASURED, common per-tick log L continued] Log wall age since creation and accumulated callback invocations separately; `C+0x20` HP, pending damage, `C+0x38/+0x39/+0x3A`, live-list presence, exit/retire/destructor/reentry ticks; NoteTrack flags `N+0x90`, animation identity `N+0x94`, integer last-frame `N+0x98`, branch slots and current animation Q12 playhead; support Q8 position/velocity; caller and victim position, HP, state and playhead; global `B+0x168/+0x16B/+0x16C/+0x16D`; freeze-request/setter calls and arguments. Use O6 `0x02155998–0x021559BC` for the playhead accessor and `0x02155780–0x021557BC` for the last-frame field; do not guess a model-field offset.

[UNMEASURED, validity rule] A hitstop cell is valid only if an actual nonzero local freeze interval is established by a counter/setter trace or calibrated per-tick execution/playhead evidence. HP loss or state 8 alone is insufficient. If the chosen attack produces zero hitstop, report "no hitstop produced" and retain the cell as a control; do not score it as proof that supports run during hitstop. The preliminary calibration belongs to the later emulator job.

| Cell, repetitions | Setup and trigger schedule | Per-tick log | Discriminating outcomes |
|---|---|---|---|
| Cell 0, 3x | Eve 590, kind 4. Press tick 6; no caller hit and no global activation. Arrange its eventual attack to whiff in this control; record actual relocation/attack/exit boundaries. Also retain no-trigger controls in the matched geometry for each later row. | L, especially natural controller/NoteTrack progression and retirement. | Establish each clock's normal sequence and wall-age boundary. A stationary support position or authored wait is not a pause unless callbacks/playhead also establish it. The known 160-tick active life is a setup reference, not a new measurement. |
| Cell 1, 3x | Same Eve 590. Schedule an isolated opponent hit on **caller only** at `t=+20`, absolute 26, by calibrating attack windup beforehand. Keep the support body out of the hitbox; avoid global/cut-in events. Use a demonstrably nonzero-hitstop attack. | L plus caller freeze entry/exit and attacker hit record. Confirm support HP unchanged. | Running hypothesis: support callback/playhead sequences remain aligned with matched control through caller freeze; retirement has no extension attributable to it. Paused hypothesis: one or both support clocks acquire plateaus or skipped calls; retirement may shift by the paused progression. Log split outcomes rather than forcing a shared clock. |
| Cell 2, 3x | Eve 590 **lands its own attack** once; press tick 6, aim for the already documented contact neighborhood `t=+118`, absolute 124, and use the observed contact as the trigger. Caller stays clear. Pair with a whiff of the same support program. Reject as a hitstop test if this hit produces no local support/attacker freeze. | L plus support hit-source ownership, victim damage and the support/body animation's freeze evidence. | Support-local pause: only this contact run gains a support clock plateau and possibly later retirement. Running: support controller/NoteTrack continue during the verified contact freeze. Compare callback calls separately from animation advancement: a running NoteTrack with frozen playhead can still poll branches. An altered authored hit branch alone is not hitstop. |
| Cell 3, 3x per ownership variant | Eve 590, call tick 6; request a calibrated DREAM/UA global action at `t=+20`, absolute 26. Run one variant with caller as user and one with opponent as user, each three times. Keep combat contacts absent during the freeze. Trace whether the real action calls O6 `0x0214E22C`; anchor duration to its actual entry. | L plus request duration/index, the new `O+0x248`, controller explicit-suspension bit, exempt-player bits and restoration. | Traced-path prediction: controller bit `0x02` sets, its callback stops; NoteTrack bit `0x02` may stay clear but its category intersection becomes zero and its callback stops. Both resume after restoration for either ownership. Running or partial-clock outcomes refute the action-to-path attribution or expose another update route. Compare timeline shifts to actual omitted callbacks, not a presumed fixed cut-in duration. |

[MEASURED, setup provenance] Eve 590's +118 contact is in `docs/research/feel-captures/2026-10-13-eve-support/README.md`, table claim `mermaid_hits`; +160 exit/+170 destruction are in `docs/research/feel-captures/2026-10-18-m14-support/RESULTS.md`, section A2. [UNMEASURED] Their preservation in these new geometries and under freeze is what the proposed capture must establish. A short follow-up with Taikoubou 658, kind 1, would check generalization after these four cells; it is not silently covered by Eve-only measurements.

## 6 open questions

- [UNMEASURED] Identify the actual fighter hitstop counter/setter, if present, and prove its complete path through animation, movement, collision and scheduler gates.
- [UNMEASURED] Bind a named DREAM/UA resource/event to the proved case-8 global mechanism. Distinguish cut-in, character-specific time-stop status, ordinary pause and ice status.
- [UNMEASURED] Measure entry/expiry phase, callback omission counts, retirement extension and same-frame contacts. Counter duration alone does not settle frame ordering.
- [STATIC/UNMEASURED] O6 Thumb `0x0214E284–0x0214E300` also computes `(B[0x14C] & B[0x150]) | 0x800` and writes two scene-object `+0x4C` masks; A `0x02031EDC–0x02031F00` has a separate scene-member mask test. The full relation to fighter-local animation/physics stopping remains unresolved. Log these masks if a hitstop calibration points there.
- [UNMEASURED] Generalize to kind 0/1, support-received hits, spawned shots/effects and overlapping freeze requests. This memo does not declare all support-dependent objects paused merely because the two requested update objects pause.
