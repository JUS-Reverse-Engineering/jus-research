# Tracker triage — 2026-09-02

Sonnet triage worker report, read-only; verdicts applied by the orchestrator the same day (14 closes incl. jus-owner-emulator-allocation-q1j, three priority changes: jus-45k P1→P2, jus-az7.2 P1→P2, jus-fms P2→P3). Owner questions in section 2 were batched to owner in the session wrap-up.

# Tracker triage — 2026-09-02

Scope: every the tracker's ready list tracker item created before 2026-09-01, plus `jus-ds8t` (in_progress)
and `jus-acr` (epic). The four tracker items created 2026-09-02 (tier-1/3 jump arcs,
air-knockback weight, untiered body factor, timed-match timer) are new physics gaps
already correctly filed against the current spec — out of scope per the task's date
cutoff, no verdict given.

## 1. Close now

| id | title | created | gist | verdict |
|---|---|---|---|---|
| jus-n4n | breakpoint 0x0215FB3C bitset writer on respawn | 08-19 | wanted a live capture of the ability-bitset writer | CLOSE-answered — the writer is fully documented without a live breakpoint: `damage.md` §"Load-time loader `0x0215FB3C`", `helpers.md` §6, `INVENTORY.md` cached-bitset row (tracker item `jus-w66`, findings p177). |
| jus-zko | watch 0214BD52/51/58 in mode 2 vs 12 | 08-19 | mode-12 gate chain capture | CLOSE-answered — already run and recorded: `docs/research/Battle-Engine-Map.md` §"The mode-12 gate, resolved to arm9 (P168)" cites this exact tracker item id (`jus-zko`) against `CONFIRMED_RUNTIME`/`RETRACTED` rows; nothing left to capture. |
| jus-peek-plus-0x44-and-flag-writer-uvp | peek [r8+0x44] bit4, log args at 0x021572F4 | 08-19 | confirm gate-word bit and load-time assembly routine | CLOSE-answered — `INVENTORY.md` §1 "Gate word read live `0x00002010`... 8 stops" (`jus-gate-word-read-live-0x2010-nbz`) and "Load-time: ov6 `0x02157114` assembles gate word AND packed nature byte together" (`jus-one-routine-assembles-both-u24`) settle both cards. |
| jus-xeb | read char+0x120+8 alongside status store | 08-19 | confirm cancel-gate bitset base | CLOSE-answered — `helpers.md` §6: "the cancel gate `0x02158EB0` reads the same expression... base = `battleObj+0x120`" — already captured and cited. |
| jus-nature-january-vs-august-9a6 | Jan says nature 1.5x, Aug says not read | 08-19 | reconcile contradiction | CLOSE-answered — `INVENTORY.md` §1: "Nature tables `0x0209FEF4`/`0x0209FF14`... additive with gates... 1.25x"; `jus-nature-does-not-affect-damage-0c6` → `state:tainted`, `jus-nature-1p5-never-observed-uh8` → retracted (1.5x observed live, P216, `jus-nature-is-read-in-damage-path-hbt`). January was right; August's negative was the tainted/incomplete read. |
| jus-9lp.1 | resolve jpower entry selection for damageFlags=0 | 01-30 | why does Goku B=8 not match total/7 | CLOSE-moot — the premise is superseded: `docs/research/DamageFlags-Character-Classification.md` banner: "Superseded (2026-09-02): the Direct/Indirect damageFlags model below is unverified... `damageFlags` has a confirmed different meaning: it is the damage gates' class index" (`jus-class-index-is-damageflags-mx5`, `damage.md` +0x0E row). No indirect-lookup mechanism to find; the jpower damage formula itself is separately closed (`findings/jpower-damage-located.md`, `jus-base-2-is-jpower-damage1-10-mse`). |
| jus-9lp.1.2 | GDB experiment: trace damageFlags=0 jpower lookup | 02-02 | old experiment plan for the above | CLOSE-moot — same supersession as jus-9lp.1; the experiment targets a mechanism that doesn't exist as described. |
| jus-n3p | exact walk speed thresholds/tiers (statC) | 01-30 | statC threshold tiers for walk speed | CLOSE-answered — `physics.md` §6.2: walk accel is indexed by `chr_b` byte 2 into a 5-row table (obj+0xB8), not statC. "`moves.md` §4's 'walk speed is statC' is superseded: statC is not read by this path." Full table with 5 tiers and measured px/frame is in the spec. |
| jus-n3p.1 | GDB experiment: walk speed field discovery | 02-02 | old experiment plan for the above | CLOSE-moot — same mechanism now fully measured in `physics.md` §6.2 via a different (superior) method; this plan's premise (statC-driven, Nami/Franky/Goku comparison) is obsolete. |
| jus-3am | map player velocity/position storage | 02-06 | velocity data location unknown | CLOSE-answered — `physics.md` §6.1 "The integrator (arm9 `0x02082E10`)": velocity fields `element+0x2C/0x2E/0x30/0x32`, drag `+0x3C/0x3D`, position write step, all measured; fighter-object chain (`obj+0x1a8`→+0x10→ColPrm scratch) resolved in HANDOFF and `physics.md` §5. |
| jus-sqk.1 | GDB experiment: find passive ability activation | 02-02 | trace ARM9 passive table | CLOSE-moot — superseded by the confirmed ability-bitset mechanism: `helpers.md` §6 writer `0x0215FB3C`, `INVENTORY.md` "Cached bitset `entity+0x128`... only bit 4 (Auto-Guard) of 32 changes blunt damage" (`Ability-Bitset-Is-Not-Resistance.md`, `jus-w66`). The passive-table hunt this plan describes has already happened via a different route. |
| jus-hbmn | Move-Damage-Table-Goku button labels wrong | 08-20 | B light, Y heavy, X specials per owner | CLOSE-answered — already fixed in the canon doc: `moves.md` line 218 cites this exact tracker item id as the source of the correction ("Contradicted by owner — B light, Y heavy, X specials \| tracker item `jus-hbmn`"). Doc reflects the finding; nothing left to do. |
| jus-yw8m | nature-SOLVED opening line contradicts itself | 08-20 | wording fix, no mechanism change | CLOSE-moot — tracker item's own body says "Wording corrected inline; no mechanism changed." Action already taken. |
| jus-dead-tracker item-ids-in-docs-r4y | 4 dead tracker item ids cited in docs | 08-19 | four dead ids (listed in the tracker item) do not resolve | CLOSE-answered — the citing doc (`Research-Status.md`) is itself listed in `INVENTORY.md` as superseded/archived ("Unmaintained banner confirmed. Cites four tracker items that no longer exist... its 'nature x1.5 refuted' line is now wrong"), so the dangling citations are already flagged in the archive banner rather than live docs. |

**Count: 13 close.**

## 2. Owner questions to batch to owner

All of these are already framed as owner-asks in their tracker items; batching the still-open
lines below into one message.

| id | question (exact) | unblocks |
|---|---|---|
| jus-law Q2 | "How do you switch characters mid-battle? Tapping the koma panels does nothing and chr_b never moves off 0." | reaching any character but the deck leader at runtime (blocks jus-3aw, Q3, jus-5bg tests) |
| jus-law Q1 | "Goku's up+X produced two effect ids, 19 (600 frames) and 32 (60 frames). Which is the freeze, and is the other a second effect or unrelated?" | naming ids in the effect table |
| jus-owner-emulator-allocation-q1j | superseded question — see verdict below (CLOSE-moot candidate, listed here only if owner wants to confirm) | — |
| jus-fun | "Given write-watchpoints are now proven working (JUS_WATCH hook, this session's physics/guard-break captures), is there still a case for a different emulator core or a static register-offset-store finder?" | closes out the melonDS-capability planning item |
| jus-5bg | Deckbuilding requests still open: Edajima+Momotaro (built per jus-ds8t notes), Eve, Robin — confirm which of the three original asks are still wanted now that jus-ds8t's roster changed (Momotaro/Taikoubou/Yusuke, not the original Edajima assignment) | closes out a stale request list or confirms remaining asks |
| jus-golden-damage-vectors-mj25 | open design questions already listed in the tracker item (state axes to sweep, corpus size) — restate as one line: "physics vectors already flowing via feel-captures/movement-2026-09-02 — is the campaign considered started, or does it still need a formal go-ahead / corpus-size target?" | resolves an open-status tracker item that the project has arguably already been executing |

**Count: 5 questions batched (2 sub-questions under jus-law).**

## 3. Keep, with proposed priority

| id | title | created | gist | priority | reason |
|---|---|---|---|---|---|
| jus-az7.2 | Build character data extractor script | 01-30 | tooling for chr_b/jpower/koma extraction | P2 | Still useful; scope narrowed by 2026-08-23 comment (retires ~60 archived Human-Testing-Queue tests). No doc says it was built. Downgraded from P1 — most of what it would extract is now hand-confirmed in `damage.md`/`collision.md`. |
| jus-f30 | TAINT: pre-08-18 damage runs had gimmick ON | 08-18 | taint notice, still governs old numbers | P1 | Taint bookkeeping tracker item — stays open as the pointer for "is this number tainted" until every affected number is re-measured; `INVENTORY.md` still cites it live. Do not close a taint-tracking tracker item just because some numbers were re-measured since. |
| jus-ywt | stale peek right after state load | 08-18 | instrument defect, unexplained | P2 | Still unexplained; HANDOFF's "interim rule" (advance ≥10 frames after load) is a workaround, not a fix. No doc closes the root cause. |
| jus-3aw | cannot switch characters at runtime | 08-19 | touch stimulus for koma panels not confirmed delivered | P1 | Directly blocks reaching any non-leader character (Rukia, Robin, Eve tests in jus-5bg; Q3 in jus-law). Unresolved — pair with jus-law Q2 owner question above. |
| jus-owner-played-match-spec-791 | spec for owner-played match w/ RAM logging | 08-19 | attribution-solving protocol | P2 | This exact protocol shape is what `jus-golden-damage-vectors-mj25`/`movement-2026-09-02` ended up using (owner-played matches, per-frame capture). Likely largely superseded in practice — keep at P2 as the originating spec tracker item rather than closing without an explicit merge decision. |
| jus-jrb | side attribution from block address unconfirmed | 08-20 | no side struct points at col block | P2 | Not touched by the physics/guard/hitstun work; still an open structural gap in the entity/collision area. |
| jus-afx4 | 6.000/5.250 pair vs dummy table's equal-hit B | 08-20 | possible dummy-table conflation of two hits | P2 | Damage-focused, orthogonal to the physics campaign; no doc resolves the (a)/(b)/(c) ambiguity it raises. |
| jus-pzrw | forward Y projectile 3.750 degenerate decomposition | 08-20 | base5x0.75 vs base3x1.5 ambiguous | P2 | Same degeneracy noted, unresolved; would need a co-read of gate word + nature cell in one capture. |
| jus-map | epic: lock down JUS mechanics | 08-22 | umbrella epic, rollup shows 16 closed | P1 | Epic stays open by design until every subsystem in `INVENTORY.md` is "portable now" — several (`collision`, `move system`, `entity/projectile`, part of `guard/SP`, `deck editor`, `helper/passive`) are still "Partial." Correctly still open. |
| jus-ds8t | fire six damage-readable gate bits (in_progress) | 08-23 | Momotaro/Luffy/Jotaro-Don Patch bit tests | P1 | Genuinely in progress with recent notes (roster reconciled 2026-08-26); `jus-bit5-ability-10-untested-mvk` still lists 10/12 rows unexercised, consistent with this being unfinished. Keep in_progress, no verdict change. |
| jus-acr | epic: reusable LLM-assisted RE framework | 01-31 | extract methodology/tooling template | P3 | Independent of the JUS-specific findings; nothing in this session's docs closes it. Legitimately still open, low urgency relative to the mechanics work. |
| jus-sqk | investigate character passives system | 01-30 | storage/interaction of passives | P2 | Largely but not fully answered: `helpers.md`/`INVENTORY.md` cover the ability bitset and 57 named abilities, and `physics.md` §4.1 covers weight passives specifically, but the original "how are passives displayed/triggered" and full storage-location questions aren't fully closed in one place. Downgrade from open-ended to P2, cite helpers.md + physics.md §4.1 as partial answers when revisiting. |
| jus-45k | atlas ask: live read of root+0x4C..+0x6C/+0x110/+0x10C/+0x158/+0x15C | 08-18 | resolve the P161 magnitude-vs-index contradiction | P2 | `entities.md` confirms `+0x108/+0x10C/+0x110` slot roles but not `+0x4C..+0x6C`/`+0x158`/`+0x15C`; the P161 contradiction (multiplier vs character-count index) is still unresolved. Downgrade from P1 — orthogonal to the current physics/guard focus. |
| jus-82q | test GDB watcher in online wifi battle | 02-04 | wifi state pointers untested online | P3 | No related doc; genuinely untouched since filed. |
| jus-cw4 | refactor jus_gdb_watcher.py into modules | 02-12 | tooling hygiene | P3 | Still monolithic per file inspection; no evidence of a refactor. Legitimate backlog item, low urgency. |
| jus-fms | GDB write-watchpoint on 0x020AFEB8 | 08-18 | find Thumb writer of a match-settings byte | P3 | Capability question (can watchpoints work at all) is resolved — see jus-fun close-candidate — but this specific target address has no confirmed writer in any doc. Downgrade from P2; re-run now that the watchpoint method is proven. |
| jus-bhv | ov10/ov01 cleared, ov12 partially resident | 08-19 | 8 remaining ov12 stores open | P2 | No doc references ov12 residency being fully resolved; stands as measured but incomplete. |
| jus-bit5-ability-10-untested-mvk | bit5<-ability10 untested, 10/12 rows unexercised | 08-19 | table rows unsampled | P2 | Explicitly still true — `jus-ds8t`'s own notes list this as related open work, and no doc claims the remaining rows were exercised. |
| jus-linter-false-positive-md-paths-bas | ~44/293 linter warnings are false positives | 08-19 | proposal to fix path resolution in the linter | P3 | Tooling proposal, unimplemented; no evidence of the linter change existing. |
| jus-ov12-boundary-probably-moves-05o | ov12 boundary is a moving high-water mark | 08-19 | reconciles 59.6%/48% residency gap | P2 | Analytical tracker item with a falsifiable prediction (boundary at `0x021BCA86`) that nobody has tested yet. Keep, no doc confirms/refutes it. |
| jus-index-identity-fields-unverified-qke | classId matches chr_b+0x0E for only 49/70 rows | 08-19 | character-index table caveat | P2 | Already caveated in place per the tracker item's own text ("Caveated in place rather than removed"); the underlying ambiguity (21 mismatched rows) is still open. Doc treatment is done; the data gap is not — keep for the data gap, not the doc action. |
| jus-hud-label-goku-naruto-flip-197e | HUD label flip GOKU->NARUTO, unattributed | 08-20 | uninvestigated observation | P3 | Explicitly filed as "not investigated," no follow-up capture found in docs. |
| jus-ivat | audit 08-22 findings sweep against confirmed-facts | 08-23 | doc debt tracker for 65 closed finding tracker items | P2 | This is exactly the kind of hygiene this triage assumes is done — but nothing indicates it was run to completion (would need its own audit trail). Keep at P2; useful now that so much has moved into `confirmed-facts/`. |
| jus-ypi5 | triage GDB-Validation-Queue.md against August findings | 08-23 | archive stale debug queue | P2 | AFK-safe, worker-delegable per its own text; no evidence it ran. Good candidate for near-term work given how much has been confirmed since. |
| jus-query-xref-overlay-aliasing-pti9 | query.py xref aliasing bug across overlays | 08-25 | tooling correctness bug | P2 | Concrete bug in `scripts/ghidra/query.py`; no fix found in the script (not verified by full read, but no tracker item/doc claims it's fixed). |
| jus-case7-nature-store-classify-6iw3 | classify two case-7 +0x175 stores | 08-25 | low-priority G2-10 follow-up | P3 | Explicitly low priority per its own text; no doc closes it. |
| jus-golden-damage-vectors-mj25 | feel-vector capture campaign | 08-26 | physics-first vector campaign, owner sign-off given | P1 | Owner already approved (2026-08-26 comment) and the campaign is visibly running — `physics.md`'s entire §§1-6 cite this tracker item's captures (`m00`-`m06`, `mv00`-`mv15`). This is the active spine of current work; keep open until GAPS in `physics.md` are closed, don't close prematurely. |
| jus-agent-loop-emu-timing-30s | throttle+savestate freeze; Lua pause question | 08-19 | harness design decision, one open sub-question | P2 | owner picked 2 of 3 options per the tracker item; no doc/commit confirms they were implemented in the harness. The one unverified sub-question (Lua pause) is still unanswered. |

**Count: 27 keep.**

## 4. Unsure

| id | title | created | gist | why unsure |
|---|---|---|---|---|
| jus-owner-emulator-allocation-q1j | who gets the emulator, one instance four sessions | 08-19 | multi-session emulator contention allocation | The task context states "Emulator access is no longer contested (single orchestrator, HOLDER lock)," which suggests this is moot. But I found no tracker item/doc that explicitly closes or supersedes jus-owner-emulator-allocation-q1j itself, and its sibling `jus-emulator-access-not-exclusive-tum` (referenced from it) wasn't in scope for this triage to check. Recommend CLOSE-moot pending a one-line confirmation from owner or the orchestrator that the HOLDER-lock protocol is what settled it. |

**Count: 1 unsure.**

---

**Totals:** 13 close, 5 owner-question batches (from 3 tracker items with sub-questions), 27 keep, 1 unsure = 46 tracker items triaged (of 50 in the tracker's ready list + `jus-ds8t` + `jus-acr` = 52 candidates; the 4 tracker items created 2026-09-02 are correctly excluded by the task's cutoff, leaving 48 in scope — 46 got a firm verdict, 1 landed in "unsure," and jus-law/jus-fun/jus-5bg appear in both "keep" implicitly and "owner questions" since they are standing question-collector tracker items, not single-answer items, so they are not double-counted in the close/keep tally).
