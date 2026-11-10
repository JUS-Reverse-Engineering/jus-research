# GDB Validation Queue — Battle Engine Atlas

> ## ⚠️ SUPERSEDED — archived 2026-09-04, do not work this queue
>
> Triage tracker item `jus-ypi5`. All 30 cards were cross-referenced against the
> August/September runtime campaign and the subsystem references in
> `docs/confirmed-facts/`. Tally:
>
> | verdict | cards | which |
> |---|---:|---|
> | SETTLED | 16 | 2, 3, 6, 7, 9, 10, 13, 14, 16, 17, 18, 20, 25, 26, 27, 28 |
> | REFUTED | 2 | 5, 8 |
> | SUPERSEDED | 7 | 1, 4, 11, 12, 15, 19, 21 |
> | STILL LIVE | 5 | 22, 23, 24, 29, 30 |
>
> Each card carries its verdict and citations in a "Triage 2026-09-04" block
> under its session table. The five live cards left this document: card 22 was
> already ticketed as tracker item `jus-45k`; the other four are now tracker items
> `jus-n53r` (card 23), `jus-964r` (card 24), `jus-98i8` (card 29) and
> `jus-wqth` (card 30), each with its discriminator and spec doc. New live tests are tracker items tickets now, never
> entries here.
>
> **Current authority is the subsystem references**, not this page:
> [damage](../../confirmed-facts/damage.md),
> [physics](../../confirmed-facts/physics.md),
> [guard and SP](../../confirmed-facts/guard-sp.md),
> [entities](../../confirmed-facts/entities.md),
> [helpers](../../confirmed-facts/helpers.md), with
> INVENTORY as the map. Validation runs
> through runtime captures (`JUS_WATCH`, `capture_feel.py`) and the tracker items
> ledger.
>
> Kept as history. No card below was ever run against a live emulator; the
> settled ones were answered by other work.

> **FROZEN 2026-08-22.** The Phase-0 gap-closing loop this queue served is
> closed. Kept as history - no card below was run against a live emulator
> before the loop closed.

Every `PLAUSIBLE` and `SPECULATIVE` claim (post-verification, i.e. final
scored confidence) produced by the static RE campaign and its Phase-0
gap-closing loop (`docs/research/Battle-Engine-Map.md`). Every subsystem in
the Map now has adversarial lens verification (3 lenses, or — for the
data-only `collision-data` subsystem — the standard single data-consistency
lens); no claim is carried here purely because verification was skipped. No
claim below has ever been checked against a running emulator; this document
exists so a human can do that with the minimum number of sessions and
breakpoints.

**Cards are grouped into sessions** by overlay/moment so one emulator sitting
can knock out several cards without reloading state. Within a session, set
up the scenario once, then walk the numbered breakpoints in order.

**Card 1 is the single highest-priority breakpoint in this queue.** It
settles the Phase-0 campaign's top open dispute (chrb-catalog claims
3/11/16: does the `+0x558` per-technique node land, unmodified, in the
`+0x56c` gauge pointer ov6 hit-resolution reads?) in one shot, and it reuses
Session 1's setup — nothing extra to configure.

**Total estimate: 30 cards across 8 sessions, ≈230 human-minutes (~3.8
hours)** — see the time table at the end. (The prior version of this queue's
data-only Session 8 — 7 collision-data re-export cards — is retired:
Phase-0's round-2 re-mining already answered every one of those cards
statically; see "Resolved by Phase-0" below.)


> ### Triage 2026-08-14 (Loop-Atlas C5)
>
> **Card 3's parenthetical note was the most valuable line in this document.** Its aside that "a
> sibling DRAIN trampoline exists at `0x020783B8` (same `+0x56c` target, negates its delta)" is
> confirmed, and it unstuck a thread that had cost five loop iterations. Damage passes a *positive*
> magnitude to the drain trampoline, which is why enumerating callers of the plain `0x020783CC`
> found only heals and status ticks. See `../findings/c5-damage-field-0x134.md`.
>
> **Cards now settled without an emulator:**
> - **Card 2** — CONFIRMED. `+0x16` = max HP, `+0x18` = current HP, verified live by the harness
>   session *and* statically (`0x02078488` does `ldrsh +0x18` / `adds` / `ldrsh +0x16` / `strh +0x18`,
>   clamped at `0x4000` = 256 displayed).
> - **Card 9** — CONFIRMED, same evidence. `0x020783CC`/`0x02078488` is the HP clamp, not a velocity
>   writer.
> - **Card 3, first half** — CONFIRMED statically: `0x020783CC` resolves `r0` via `ldr r0,[r0,#0x56C]`.
>   The formula half is *not* settled and should be re-derived: the harness measured resistance as a
>   **flat −2**, not a ratio, and the queue's `floor(damage1/5)+(tier-2)` predates the u16 HP
>   correction.
> - **Card 10** — REFRAMED. `+0x6A` is not a standalone field at all; it's record 1, field `+0x6` of a
>   12-byte-strided array. See `../findings/c4-physics-is-an-array.md`.
> - **Card 8** — partly settled. `0x020781E4` is the **SP-apply sibling** of the HP apply (19 call
>   sites, each immediately following an HP apply), which supports "a gauge, not velocity".
>
> **Card 12** advanced but not settled: `0x02159EF8` does contain concrete mechanism (the pending-delta
> family at `+0x134`/`+0x138`/`+0x140`/`+0x144`), but no two-entity comparison has been found in it.
>
> The highest-value remaining live check was **CARD D1b** in the (now archived)
> `Human-Testing-Queue.md` — one number, `+384`, on one landed hit. Its prediction was
> CONFIRMED 2026-08-14 (read 512, net of one auto-heal frame).

---

## Session 1 — Live Hit-Landing (ov6, function `0x02158B20` and its direct callees)

**Setup:** start a battle, control one attacker landing normal hits on a
defender with the on-screen HP bar visible. For card 6, additionally get the
attacker down to ≤25% of their own gauge to test the desperation-gated path.
For card 12, get two characters' hitboxes to overlap on the same frame
(a clash).

| # | Subsystem / claim | Breakpoint | What to check | Expected if TRUE | Expected if FALSE |
|---|--------------------|-----------|----------------|--------------------|----------------------|
| 1 | **[TOP PRIORITY — chrb-catalog's top open dispute]** Is the `+0x558` per-technique node the same object as the `+0x56c` gauge pointer? Settles 3 claims (3/11/16) at once. | `0x020784E4` (or `0x02077E70`) | At `0x020784E4`: dump the pointer `r4=[r0+0x56c]` right before it reads `+0x16`/`+0x18`. Separately (or in the same session), at `0x02077E70`'s store `0x02077FDC` (`str r5,[r6,#0x56c]`), dump `r5` and compare it against the node addresses the `+0x558` list walker (`0x020783DC`) visits. | The pointer landing in `charPtr+0x56c` is a live node from the `+0x558` list — the aliasing lens's reading is confirmed; the technique-setup cache DOES feed ov6 hit-resolution | `charPtr+0x56c` is a distinct, fixed gauge object never touched by the `+0x558` walker's call graph — the disasm-correctness lens's reading is confirmed; the two mechanisms are genuinely separate |
| 2 | damage-pipeline — `char+0x56c` is a 2-field gauge; `0x02078488`=clamped-add accessor | `0x02078488` | Watch `[r0+0x16]` (max) and `[r0+0x18]` (current) while landing hits that visibly change on-screen HP | `[r0+0x16]` tracks max-HP-like stat; `[r0+0x18]` drops by the delta in `r1` matching the visible HP loss | Fields don't correlate with the HP bar (e.g. track a different gauge — super/guard meter) |
| 3 | damage-pipeline — `0x020783CC` trampoline into the gauge accessor. **Note (Phase-0): a sibling DRAIN trampoline exists at `0x020783B8`** (same `+0x56c` target, negates its delta) — if `r1` here comes back unexpectedly positive on a hit that should decrement HP, check whether that hit routed through `0x020783B8` instead (called from `0x0215AC70`). | `0x020783CC` (and, if needed, `0x020783B8`) | Confirm `r0` resolves to the defender's `char+0x56c` gauge pointer; confirm `r1` (delta) is negative, magnitude == `floor(damage1/5)+(tier-2)` | `r0`/`r1` match as described | `r0` points elsewhere, or `r1` doesn't match the known-good formula |
| 4 | damage-pipeline — `0x02158BC0` call site actually decrements gauge on a real hit | `0x02158BC0` | Same check as card 3, at this specific call site | Same as card 3 | Same as card 3 |
| 5 | damage-pipeline — scratch `+0xE8` = pre-computed per-hit damage magnitude | `0x02158BA8` | Read `[r1+0xE8]`; compare to `floor(damage1/5)+(tier-2)` for the hit that just landed; trace backward for the last store to this field this frame | Value matches formula output; a store instruction is found earlier in the same frame | Value doesn't match, or no write is found this frame (implying a cached/different source) |
| 6 | damage-pipeline — ×1.20 scale = desperation-gated universal `attack_boost`, not nature/combo bonus | `0x02158DC4` | Log `r4` before/after and byte at `[sl+0xf8]`; correlate against attacker's own gauge % (per cards 2–3) vs. combo position vs. nature-type advantage | Flag/scale triggers specifically when attacker's gauge ≤25% max, independent of combo position or opponent's nature | Scale correlates with first-hit-in-combo or nature-type-advantage instead (resurrects a refuted reading), or with neither |
| 7 | physics-writers — `+0xE8`/`+0x130` dispatch to two writers on `[sl+0x1b4]` | `0x02158BC0` and `0x02158BCC` | Confirm `r1` at each call == `-(scratch->0xE8)` / `-(scratch->0x130)`; dump `*(r0)=[sl+0x1b4]` at `+0x5C8`/`+0x56C` before/after each call | `r1` magnitudes match; `+0x56C` changes at one call (HP), `+0x5C8` changes at the other (percent-meter) | `r1` doesn't match scratch fields, or neither target field changes as predicted |
| 8 | physics-writers — `0x020781E4` accumulates into `object+0x5C8` (percent/hitstun meter, not velocity) | `0x02078204` | Watch `object+0x5C8` across a single knockback hit | Behaves like a percentage/hitstun meter (monotonic-ish, wraps at 25600) | Decays every frame like a velocity component |
| 9 | physics-writers — `0x020783CC`/`0x02078488` is the HP/gauge clamp, NOT a velocity writer | `0x02078488` | Dump `*r0` at `+0x16`/`+0x18` before/after; compare against any visible debug HP readout | `+0x16`/`+0x18` track current/max HP — settles the question definitively | Values don't track HP — reopens the velocity possibility |
| 10 | physics-writers — ov6 wrapper `+0x6A` (`0x021607C0`) = min-tracker + saturating hit counter, not velocity | `0x021607C0` | Confirm `r0` == wrapper/player pointer (not the deeper char struct); watch `+0x6a`/`+0x38` across several hits | Behaves like a hit-priority/lockout tracker | `+0x6a` decays/accumulates every frame like a velocity component |
| 11 | hitstun-timers — `0x0207D16C` writes `[r0+0xa0]` + sets `[r0+0x78]` bit `0x800000` (hitstun-init candidate; already 2/3-lens-REFUTED as a per-hitbox slot index) | `0x0207D16C` | On a live hit-landing, dump `r0` (diff against the `0x023D2A74` pointer chain) and `r1` (compare to the jpower move's hitstun value); confirm whether `[r0+0x78]&0xFF` becomes `0xC0`-family while `[r0+0xa0]` decrements to 0 | `r0` == known character struct; `r1` matches jpower hitstun; states transition as predicted (would REVERSE the lens's refutation) | `r0` is a per-hitbox record (not the character struct); the `0x800000` OR touches `+0x7A`, not `+0x78` (confirms the lens's refutation) |
| 12 | hitbox-priority — ov6 `0x02159EF8` per-character state dispatcher is the clash-resolution neighborhood | `0x02159EF8` (during a two-character clash) | Dump `r0` (character struct) each hit; inter-frame-diff `r0+0xCB`/`+0xD2`/`+0xD3`/`+0x1A4`/`+0x1A8` and the callee-visible fields inside `0x0215FC78`'s target struct | One of these fields holds an opponent's collision-entry pointer or `hitTier` at the moment both hitboxes overlap | None of these fields ever reflect opponent state — clash resolution lives elsewhere entirely |

> ### Triage 2026-09-04 (`jus-ypi5`)
>
> - **Card 1 — SUPERSEDED.** The `+0x558`-vs-`+0x56C` identity dispute is moot:
>   `char+0x56C` is the HP block (`jus-hp-block-at-char-0x56c-q86`,
>   [damage.md](../../confirmed-facts/damage.md) §2.3) and `char+0x558` is the
>   second ability-source node list (`jus-second-ability-source-0x558-5rp`);
>   neither is a guard or SP gauge — the guard gauge sits on the fighter object
>   at `+0x102`/`+0x104` (`jus-guard-gauge-found-a55l`,
>   [guard-sp.md](../../confirmed-facts/guard-sp.md) §0.5). Decision ticket
>   `jus-map.13` was waived on that basis
>   ([guard-sp.md](../../confirmed-facts/guard-sp.md) §0, GAP 4).
> - **Card 2 — SETTLED.** `{+0x16 max, +0x18 current}`, units 1/64, cap `0x4000`
>   (`jus-hp-block-at-char-0x56c-q86`;
>   [guard-sp.md](../../confirmed-facts/guard-sp.md) §1.1,
>   [damage.md](../../confirmed-facts/damage.md) §2.3 and §3). The same gauge
>   shape carries bench regen, clamped to `koma+0x16` (`jus-b3k2`).
> - **Card 3 — SETTLED, both halves.** The trampoline pair resolves `r0` from
>   `[char+0x56C]`, and the drain sibling negates
>   ([guard-sp.md](../../confirmed-facts/guard-sp.md) §1.2). The formula half was
>   re-derived from scratch: base byte × two 8.8 multipliers, additive nature
>   term, six ±25% gates on `[r8+0x44]`, `>>2`
>   (`jus-reduction-is-quarter-multiplier-xk1`, `jus-gate-word-is-r8-0x44-fnz`,
>   `jus-nature-is-read-in-damage-path-hbt`;
>   [damage.md](../../confirmed-facts/damage.md) §4). The card's
>   `floor(damage1/5)+(tier−2)` is retracted — the base byte is `damage1/5` with
>   no tier term (`jus-base-2-is-jpower-damage1-10-mse`,
>   `jus-flat-refuted-with-attribution-doi`).
> - **Card 4 — SUPERSEDED.** The producer-to-consumer path was traced end to end
>   in one session: formula result → `scratch+0xA4` → `scratch+0x134` → consumer
>   at `0x0215AC08` → drain trampoline → `0x02078488` (`jus-m92n`, `jus-iza`,
>   `jus-kfy`; [damage.md](../../confirmed-facts/damage.md) §4 step 6). This card's
>   call site `0x02158BC0` is one of the eight fill-trampoline sites, not the
>   melee damage route ([guard-sp.md](../../confirmed-facts/guard-sp.md) §1.2).
> - **Card 5 — REFUTED.** `scratch+0xE8` is not the damage carrier; it read zero
>   through the whole traced path while `+0x134` carried the magnitude
>   (`jus-qr8`, `jus-m92n`; [damage.md](../../confirmed-facts/damage.md) §4 step 6,
>   `../findings/owner-0xE8-has-no-writer-b11-narrowed.md`).
> - **Card 6 — SETTLED, and the desperation reading holds.** `f1` at
>   `scratch+0x184` is ×1.1992 exactly when the attacker carries ability 14
>   (底力) and sits below 25% HP; `f2` is always 1.0
>   (`jus-attacker-multipliers-halving-xls7`;
>   [damage.md](../../confirmed-facts/damage.md) §2.1, §8). The competing
>   "nature advantage" label on `0x02158DC4` is refuted
>   ([nature.md](../../confirmed-facts/nature.md) §2.3), and combo position never
>   entered it.
> - **Card 7 — SETTLED.** The staged fields are a four-member pending-delta family
>   on `[[char+0x1A8]+0x10]`: `+0x134` HP damage, `+0x138` SP drain, `+0x140` HP
>   heal, `+0x144` SP add (`../findings/c5-damage-field-0x134.md`). `[char+0x1B4]`
>   is a `0x61C`-byte ComicDeck player slot and `+0x5C8` on it is the SP total, not
>   a percent meter ([guard-sp.md](../../confirmed-facts/guard-sp.md) §1.4).
> - **Card 8 — REFUTED.** `0x020781E4` is the SP-apply: `[slot+0x5C8] += amount`,
>   refused on a negative amount when `slot+0x5CF` is non-zero. No percentage
>   behaviour, no 25600 wrap, no velocity
>   ([guard-sp.md](../../confirmed-facts/guard-sp.md) §1.4). Hitstun is a separate
>   mechanism entirely (see card 11).
> - **Card 9 — SETTLED**, same evidence as card 2.
> - **Card 10 — SETTLED in the negative direction.** The "physics region
>   `+0x6A`–`+0xBA`" does not belong to the battle character struct at all — those
>   offsets belong to a JPower record and to collision bookkeeping
>   (`jus-physics-region-identity-refuted-68d9`). Position and velocity live in the
>   shared element array driven by the arm9 integrator `0x02082E10`
>   (`jus-position-array-located-i1a5`, `jus-fighter-object-identity-c56i`;
>   [physics.md](../../confirmed-facts/physics.md) §5, §6.1). Whatever `+0x6A`
>   counts, no spec depends on it.
> - **Card 11 — SUPERSEDED.** Hitstun init was found elsewhere: ov6 `0x0215AD58`
>   writes the whole-frame byte `obj+0x115` as
>   `clamp(M[0x171] + 20 + T[state], 16, 60)`, with the countdown at `hit+0x114`
>   (`jus-hitstun-formula-state-table-zgq3`, `jus-hitstun-table-rows-runtime-7oxa`,
>   `jus-9lp.2.2`, `jus-qd8s`; [physics.md](../../confirmed-facts/physics.md) §4.5).
>   The `+0x78` word with bit `0x800000` is the collision entity's flag word, which
>   is what the lens said (`jus-physics-region-identity-refuted-68d9`).
> - **Card 12 — SUPERSEDED.** `0x02159EF8` is the per-character state dispatcher,
>   and its concrete job at `0x0215A318` is flushing the pending-delta family
>   (`../findings/c6c-damage-accumulator.md`,
>   `../findings/c5-damage-field-0x134.md`,
>   `../findings/p157-status-dispatch-table-and-hp-delta-census.md`); no two-entity
>   comparison lives in it. Move and attack priority stays open as a spec question
>   in its own right (INVENTORY.md §3,
>   [moves.md](../../confirmed-facts/moves.md)), not as a field dump at this
>   address.

---

## Session 2 — Move-Start / MoveInfo Allocation (arm9, fires whenever any attack begins)

| # | Subsystem / claim | Breakpoint | What to check | Expected if TRUE | Expected if FALSE |
|---|--------------------|-----------|----------------|--------------------|----------------------|
| 13 | jpower-indirect — MoveInfo alloc (`0x02156A58`, size `0x1F0`) installed into `char+0x1a8` by `0x021570EC` | `0x02156A58`, then `0x021570F4` | Log size arg (`r0=#0x1f0`) and returned pointer; then confirm `r0` stored into `char+0x1a8` equals that same pointer | Lifecycle confirmed — pointer round-trips cleanly | Different pointer stored, or size differs — the MoveInfo identity assumption is wrong |

> ### Triage 2026-09-04 (`jus-ypi5`)
>
> - **Card 13 — SETTLED.** `character+0x1A8` is the pooled entity and
>   `entity+0x30` the character, wired inside `Battle_CharaCreate` through the
>   `0x021570EC` callback; the `0x1F0` battle-character allocation is attributed by
>   the allocator's `__FILE__`/`__FUNC__`/`__LINE__` tags
>   ([entities.md](../../confirmed-facts/entities.md) §3,
>   `../findings/allocations-are-tagged-and-the-battle-character-is-0x1F0.md`).
>   The `[[obj+0x1A8]+0x10]` chain was then read live every frame in the guard and
>   hitstun campaigns (`jus-guard-break-decision-obj-0x110-1xty`,
>   `jus-hitstun-formula-state-table-zgq3`), which is the round-trip this card
>   asked for.

---

## Session 3 — Character-ID Table `0x020924B0` (arm9 load-time site + ov0 consumer)

**Setup:** trigger a character load (battle start / roster browse) for card 14; trigger the ending/credits sequence (the known consumer context) for card 15.

| # | Subsystem / claim | Breakpoint | What to check | Expected if TRUE | Expected if FALSE |
|---|--------------------|-----------|----------------|--------------------|----------------------|
| 14 | hitbox-priority — `word0` = ASCII char-ID string, used to build a resource key | `0x0207478C` (or `0x02074790`) | Single-step the copy loop; confirm copied string content; backtrace to see what resource path/filename it ultimately builds | The string ends up in a **collision** resource path | The string ends up in a different resource path (sprite archive, sound, AI, etc. — consistent with the loop-state finding that at least one consumer builds a `.aar` ending-credits key) |
| 15 | hitbox-priority — ov0 `0x0214EFAC` 74-entry scan; 6-bit id in `word1` bits 14–19 (already refuted as chr_b's `classId` by range mismatch: classId spans 256–684, can't fit in 6 bits) | `0x0214EFD8` | Dump the extracted 6-bit id and caller-supplied `r7` across several calls; backtrace the call to `0x0214EFAC` to see what feature (ending/credits vs. gameplay) triggers the scan | The id correlates with something battle-relevant after all (unlikely, given the range mismatch) | Confirms the id is purely an ending/credits-internal index, closing this lead entirely |

> ### Triage 2026-09-04 (`jus-ypi5`)
>
> - **Card 14 — SETTLED, on the card's FALSE branch.** The 8-byte-stride table at
>   `0x020924B0` holds per-character short codes that build the sprite-archive path
>   `battle/chr/??_?_??.aar` — asset selection, no collision resource and no damage
>   arithmetic (`../findings/c0-nature-in-battle.md` §1;
>   INVENTORY.md §2 disputes,
>   [nature.md](../../confirmed-facts/nature.md) non-damage uses).
> - **Card 15 — SUPERSEDED.** The lead it belonged to is closed: `0x020924B0` is not
>   a collision table, and the ov0 6-bit id was already out of range for chr_b's
>   `classId`. Nothing in a current spec reads that id, and the damage class index
>   came from a different place — collision `+0x0E`, low 6 bits
>   (`jus-class-index-is-damageflags-mx5`;
>   [damage.md](../../confirmed-facts/damage.md) §2.1).

---

## Session 4 — Character-Select / Roster Screen (ov5)

> **G2 correction (`jus-ghidra-tooling-j4i2.3.4`):** ov05 `0x0214E480` has two
> direct callers, `0x02151B74` and `0x02151B88`, in the same record-builder.
> Probe 17 now covers both sites. The old sole-caller conclusion is retracted.

| # | Subsystem / claim | Breakpoint | What to check | Expected if TRUE | Expected if FALSE |
|---|--------------------|-----------|----------------|--------------------|----------------------|
| 16 | weight-hunt — chr_b getter `0x0214E480` reads record `+0x0`, gated on `work+6==0` & `work[0xb]>>4==3` | `0x0214E4B8` | When gate conditions hold, confirm `r1` (post-load) equals the byte at `chr_b_record_base + charIndex*0x3C + 0x0` for that `charIndex`; cross-check against `chr_b.json` field 0 | Matches exported `chr_b.json` field 0 (likely FormType) for that roster slot | Mismatch — the getter reads a different offset/table than assumed |
| 17 | weight-hunt — both callers of the offset-`+0x0` getter fill a roster/select-screen display record, not a battle physics object | `0x02151B74` and `0x02151B88` (after `r7` fields are filled) | Inspect memory at `r7` (fields `+2..+7`) at both sites; inspect the call stack/context | Both returns are remapped into the display record (`r7+6` and `r7+7`) — rules OUT weight for this offset | Either return feeds a live battle/physics object — reopens `+0x0` as a weight candidate |
| 18 | movement — only statC consumer (`0x020771C4`/caller `0x0215A31C`) is a koma-technique eligibility check, not a walk-speed selector | `0x020771C4` (or caller `0x0215A31C`) | During ordinary walking/dashing (no koma/technique menu open), confirm whether this function is ever hit purely from movement input | Function fires during plain movement too — walk-speed hypothesis survives | Function is NEVER hit outside menu/eligibility contexts — confirms the cached walk-speed value (if any) must be read from elsewhere |
| 19 | **[NEW, chrb-catalog]** ov5 "special form" family getters `0x0214E238`/`0x0214E284` — is the FormType read (record `+0`) genuine ARM `ldrb`, or does the disasm DB's apparent Thumb-mode decode past the index computation reflect a real mode switch? | `0x0214E268` and `0x0214E2B8` (right after the `mla`/`smulbb` index computation) | Single-step 2–3 instructions past the breakpoint; confirm the CPU executes an `ldrb`-with-register-offset (reading chr_b record `+0`) | CPU executes a normal ARM `ldrb` — confirms this is a disasm-listing artifact (shared-tail-veneer), not real Thumb code; the `+0` (FormType) reading is confirmed for these 2 sites too | CPU genuinely switches to Thumb mode here — a surprising, previously-undocumented mode switch inside otherwise-pure-ARM ov5 |

> ### Triage 2026-09-04 (`jus-ypi5`)
>
> - **Card 16 — SETTLED.** `0x0214E480` is the nature-resolution accessor, and
>   chr_b record `+0x00` is the character's base nature under a
>   sentinel-and-fallback scheme, matched 9/9 against the exported tables
>   ([nature.md](../../confirmed-facts/nature.md) §3.1,
>   `../findings/nature-SOLVED.md`). It is not FormType.
> - **Card 17 — SETTLED, weight ruled out.** Weight is not a chr_b byte: the
>   knockback "weight" term is a pair of passive abilities (23/24) acting as gate
>   bits, and only on launchers (`jus-cb0.1`, `jus-untiered-hit-body-factor-t0m7`,
>   `jus-air-knockback-weight-3gm4`;
>   [physics.md](../../confirmed-facts/physics.md) §4.1). chr_b bytes 0–7 are not
>   weight ([moves.md](../../confirmed-facts/moves.md) §4).
> - **Card 18 — SETTLED.** `0x020771C4` is a koma-technique eligibility check, and
>   walk speed came from somewhere else entirely: a per-character acceleration at
>   `obj+0xB8` through a 1/8 drag, measured per character
>   (`jus-movement-speed-runtime-0luv`, `jus-fighter-object-identity-c56i`;
>   [physics.md](../../confirmed-facts/physics.md) §6.2,
>   [moves.md](../../confirmed-facts/moves.md) §4). The residual statC threshold
>   question is tracked separately, not here.
> - **Card 19 — SUPERSEDED.** The ov5 getter family's live output is the nature
>   value ([nature.md](../../confirmed-facts/nature.md) §3.1), so the FormType
>   framing is gone; and ARM-decoded Thumb regions are a known, documented listing
>   hazard rather than a per-site question
>   (INVENTORY.md, "Tooling hazards").

---

## Session 5 — Shared-Window Move-Flag Test (resident overlay ambiguous: one of ov0/ov2/ov3/ov4/ov5/ov7)

| # | Subsystem / claim | Breakpoint | What to check | Expected if TRUE | Expected if FALSE |
|---|--------------------|-----------|----------------|--------------------|----------------------|
| 20 | weight-hunt — `+0x60` per-index bitfield accessor off the chr_b singleton (`GetFlag(idx)`); one located call site indexes by move-id, not `charIndex` (already 2/3-lens-REFUTED as the passive table) | `0x0214D5A4` | Log `r0` (flag index) across an entire match, across every overlay sharing this address (ov0/ov2/ov3/ov4/ov5/ov7) | ANY call site ever passes a `charIndex`-derived (0–73) value rather than a move-id composite — confirms an innate-passive/ability dispatch table after all | Every call site passes a move-id composite — confirms this is NOT the per-character passive table; the real Edajima-style passive lookup lives elsewhere (see the PassiveIndex lead in the Map's weight-hunt section) |

> ### Triage 2026-09-04 (`jus-ypi5`)
>
> - **Card 20 — SETTLED, and not as the passive table.** The passive path is mapped
>   end to end: five sparse on-disk slots at `chr_b+0x03`
>   (`jus-ondisk-ability-list-at-chrb-0x03-kfc`) → runtime list at `char+0x1A`
>   count / `char+0x1B..` ids, appended by `0x02077A74` → cached bitset
>   `obj+0x128`, written bit-per-id by ov6 `0x0215FB3C`
>   ([helpers.md](../../confirmed-facts/helpers.md) §4–§6). That bitset is what
>   feeds the damage gates (`jus-bit5-is-ability-10-rxl`) and the guard-gauge max
>   (`jus-guard-max-130-ability-22-8gil`), and it is re-cached in place on a
>   respawn (`jus-q2y`). No spec needs `0x0214D5A4`.

---

## Session 6 — ov4 Position-vs-Timer Disambiguation

| # | Subsystem / claim | Breakpoint | What to check | Expected if TRUE (position) | Expected if FALSE (timer / distinct object) |
|---|--------------------|-----------|----------------|--------------------------------|-----------------------------------------------|
| 21 | hitstun-timers — ov4 `0x02151E04`/`0x02151E7C` reads `+0xa0`/`+0xa2` as an (x,y) position pair (already 2/3-lens-REFUTED as a 3rd, distinct vtable-dispatched per-effect struct) | ov4 equivalent of `0x02151E7C` (whichever overlay is resident) | Dump `r4` (`=[r5+4]`), compare against the live `0x023D2A74` character-struct chain; log `[r4+0xa0]`/`[r4+0xa2]` across several frames of a knockback/fall | Large, motion-consistent X/Y deltas | Small monotonic countdown, OR `r4` doesn't match the character struct at all (confirms the lens's "3rd distinct object" reading) |

> ### Triage 2026-09-04 (`jus-ypi5`)
>
> - **Card 21 — SUPERSEDED.** The conflict this card was written to resolve is
>   retired at the source: the Feb-2026 physics/timer regions are not
>   character-struct fields (`jus-physics-region-identity-refuted-68d9`, and the
>   banner on `Character-State-Struct-2026-02.md`). Position lives in the shared
>   element array (`jus-position-array-located-i1a5`;
>   [physics.md](../../confirmed-facts/physics.md) §5) and the per-hit countdowns
>   are `hit+0x114` and `obj+0x115` (§4.5). Neither answer needed this breakpoint.

---

## Session 7 — Projectile Lifecycle (arm9 + ov6)

**Setup:** use a character with a known projectile move (`bb_b_01` or
`db_b_01` per `collision-data.round1.json` — both characters' only
nonzero-`projectileId` entries have `collisionType=4`). Spawn the projectile,
let it fly until it despawns naturally or hits something.

**3-lens verification completed this phase (P3):** 4/5 original claims are
now CONFIRMED_STATIC (alloc, free, spawn dispatch, spawn+ownership); only
the despawn function remains PLAUSIBLE. Two former cards were dropped as
answered statically — see "Resolved by Phase-0" below. The cards remaining
below check open semantic/behavioral questions the static verification
could *not* settle.

| # | Subsystem / claim | Breakpoint | What to check | Expected if TRUE | Expected if FALSE |
|---|--------------------|-----------|----------------|--------------------|----------------------|
| 22 | projectile-entities — manager `0x0214BE14`'s `+0xc`/`+0x14`/`+0x1c` are active/free/pending lists (mechanism CONFIRMED; semantic role labels still inferred from control flow only, never proven against a live dump) | `0x020834D4` entry (or `0x020834E4`) | Dump `*0x0214BE14` and walk its `+0xc`/`+0x14`/`+0x1c` list anchors before/after the projectile spawns | `+0x14` shrinks (free-list) on alloc, `+0xc` grows (active-list); `+0x1c` untouched on success | Anchors behave differently than this role assignment |
| 23 | projectile-entities — spawn dispatch: `[r8+0x1b]` byte correlates with on-disk `ProjectileId`/`CollisionType`. **Note: the confirmed dispatcher case selector is `r2=7`, not 8 as originally labeled** — the dispatch mechanism itself is otherwise CONFIRMED_STATIC. | `0x021576C0` | Dump byte at `[r8+0x1b]`; compare with the current move's on-disk `CollisionEntry.ProjectileId`/`CollisionType` (expect `CollisionType==4` per the collision-data sample) | `[r8+0x1b]` correlates with `ProjectileId`/`CollisionType==4` | No correlation — the `+0x1b` byte encodes something unrelated |
| 24 | projectile-entities — despawn: age counter (32-frame cap, with a suppression bit at `[entity+6]&0x2` found this phase) + boundary/threshold checks. **Capped PLAUSIBLE — cannot be statically proven specific to projectiles** (the aliasing lens found ≥2 sibling ov6 functions reusing the identical scaffolding). | `0x0216CA28`, `0x0216CA74`, and `0x0216CA98` | Watch `entity+4` (age counter) increment to `0x20` (32) and trigger destroy unless `[entity+6]&0x2` suppresses it; identify the object behind `r4` (the `+0x100`/second-threshold field) and helper `0x216ee14`'s behavior as the projectile travels off-screen; separately, break the same age-counter idiom in sibling functions `0x0216E1C0`/`0x0216F398` to check whether THIS is projectile-specific or shared | Age counter caps lifetime at 32 frames (modulo the suppression bit); `r4`/helper implement an off-screen or wall-collision check; sibling functions handle a *different* entity kind | Projectile persists past 32 frames even with the suppression bit clear, or the sibling functions turn out to handle the SAME entity kind (would mean `0x0216C958` isn't uniquely "the" projectile despawn routine even architecturally) |

> ### Triage 2026-09-04 (`jus-ypi5`)
>
> - **Card 22 — STILL LIVE, already ticketed.** The `+0x0C`/`+0x14`/`+0x1C`
>   active/free/retire labels are still inferred from control flow only
>   ([entities.md](../../confirmed-facts/entities.md) GAP 4); the live manager read
>   is tracker item `jus-45k`.
> - **Card 23 — STILL LIVE.** `projectileId` remains an opaque token with four
>   decode refutations behind it; entities.md carries it as the top blocker with an
>   explicit settle-or-waive ([entities.md](../../confirmed-facts/entities.md) §6,
>   GAP 1). Ticket proposed under `jus-ypi5`.
> - **Card 24 — STILL LIVE.** Despawn identity is unchanged: three ov6 siblings
>   share the scaffolding and static evidence cannot pick one
>   ([entities.md](../../confirmed-facts/entities.md) §7, GAP 2). Ticket proposed
>   under `jus-ypi5`.

---

## Session 8 — Guard/SP Gauge Mechanics (guard-sp-gauges, new this phase)

**Setup:** a single "combo dojo"/practice-mode session against a dummy
covers cards 25–28 (trigger a mix of guard blocks, SP-spending specials, and
a status effect). Card 29 needs a "max HP on respawn"-style passive
equipped (candidate ability `0x07`). Card 30 needs a full match plus a
save-state reload (to observe `char+0x558` from a cold start).

| # | Subsystem / claim | Breakpoint | What to check | Expected if TRUE | Expected if FALSE |
|---|--------------------|-----------|----------------|--------------------|----------------------|
| 25 | guard-sp-gauges — dispatchers `0x02157A44`/`0x0215807C` route battle-event opcodes to the HP trampoline vs. the `char+0x5c8` counter vs. the `+0x558` list walker | `0x02157A44` and `0x0215807C` | Log `r2` (opcode, dispatcher 1) / `r3` (opcode, dispatcher 2) and the delta register on entry across many distinct battle events (guard block, SP spend, status tick, HP hit) to build an opcode→target table | A cluster of opcode values routes specifically to the `+0x558` walker (candidate guard/SP opcodes), distinct from the HP-trampoline opcode cluster | Opcodes routing to the `+0x558` walker are indistinguishable in kind from HP-trampoline opcodes — no clean guard/SP-vs-HP opcode split exists |
| 26 | guard-sp-gauges — scaling wrapper trio `0x02159260`/`0x021592C0` (×64/unscaled, target HP) and `0x02159280` (×256, target `+0x5c8`) all read the same `[[r1+4]+4]` signed halfword source | `0x02159260`, `0x021592C0`, `0x02159280` | Dump `[[r1+4]+4]` and its sign at each; determine what kind of object `r1` (2nd wrapper argument) is, and whether the ×64/×256 scale factors convert a shared "raw stat" unit into each target's own units | A single shared raw-stat source feeds all three gauges via different fixed scale factors (unit-conversion reading confirmed) | The three wrappers' source values are unrelated/uncorrelated in practice — the shared-template reading is cosmetic only |
| 27 | guard-sp-gauges — eligibility codes `0x1b`(27)/`0x1d`(29) gate wrappers `0x02159500`/`0x02159624` via predicate `0x0215986C`→`0x2158eb0(charPtr+0x120, code)` | `0x0215986C` | Log `r5` (char ptr), the `r2` code (`0x1b`/`0x1d`), and the return of `0x2158eb0` across different attack/status types (guard-break, poison/burn per the existing ailment-code hypothesis, elemental match, etc.) | Codes 27/29 map cleanly onto two known status-effect types (e.g. Burn/Poison) — confirms these gate a battle-*effect* type, orthogonal to gauge selection | Codes correlate with something gauge-specific instead — reopens the "these select a gauge kind" alternative |
| 28 | guard-sp-gauges — `0x0215A318`/`0x02159EF8` feeds the HP trampoline from `[[charPtr+0x1a8]+0x10]+0x140`, unnegated (passive-fill/DoT-tick candidate) | `0x0215A2D0` and `0x0215A308` | Log the signed value at `[[charPtr+0x1a8]+0x10]+0x140` and its sign every frame on a status-effect-afflicted character; also check the `+0xcc` enable-gate and the "run once" sticky flag at `[r6+0x14]` bit 0 | Value is negative during a damage-over-time effect (poison/burn tick) and/or positive during a regen effect — confirms a per-frame passive/DoT tick, not a one-shot hit | Value stays at 0 outside of a specific one-shot event, or behaves like a one-shot-hit magnitude instead |
| 29 | guard-sp-gauges — `GrowMax` caller `0x0215C73C` = "max HP on respawn" passive (bit `0x80` of `char+0x128`, fixed `+0x400` delta) | `0x0215C73C` | Equip a candidate "max HP up" passive, trigger a respawn/tag-in; confirm bit `0x80` of `char+0x128` is set and that `[charPtr+0x56c]+0x16` (max) increases by exactly `0x400` (1024) | Matches — identifies the concrete equip/passive that sets this bit | Bit never sets for any equipped passive tested, or the max-HP field doesn't move by exactly 1024 — reopens what triggers this path |
| 30 | guard-sp-gauges — `+0x558` node census + insertion-site watch (no store into `char+0x558` other than the one zero-init was found statically) | `watch *(charPtr+0x558)` for writes; also break `0x020783DC` across a full match | Catch the actual node-constructor/insertion write (candidate: a split `add rX,#0x558`+register-offset store, invisible to static `search-imm`); separately, log every distinct node address and its `+0x00`(next)/`+0x16`(max)/`+0x18`(cur)/`+0x3c`/`+0x40`(flags) fields walked by `0x020783DC` to census how many node "kinds" exist (guard? SP? both? shared across a 3-character deck?) | A concrete insertion site is found; the node census reveals ≥2 distinct node kinds (or a single shared node referenced by multiple character structs, resolving the SP deck-shared-vs-per-character tension) | No insertion write is ever caught (nodes might be statically pre-linked at ROM-load rather than dynamically inserted); all census'd nodes look identical (single generic node type, tension unresolved) |

> ### Triage 2026-09-04 (`jus-ypi5`)
>
> - **Card 25 — SETTLED statically.** The 73-case per-character dispatcher is
>   enumerated: cases 23/24/32 reach the HP apply, the SP apply and the `+0x558`
>   walker, and the 64–73 band are boolean predicates that mutate nothing
>   (`../findings/73-case-dispatcher-enumerated.md`,
>   `../findings/commands-are-predicates.md`;
>   [damage.md](../../confirmed-facts/damage.md) §1 dispatch row,
>   [moves.md](../../confirmed-facts/moves.md) NoteTrack `+0x70`). The opcode→target
>   table this card wanted to build already exists.
> - **Card 26 — SETTLED.** Five thin wrappers share one shape, each reading the
>   signed halfword at `node->[4]->[4]`, and the only scaling anywhere at the
>   trampoline boundary is a constant power of two — ×64 for ids `0x25`/`0x26`,
>   ×256 for `0x27`–`0x29`, unscaled for `0x04`
>   ([guard-sp.md](../../confirmed-facts/guard-sp.md) §1.2,
>   `../findings/p157-status-dispatch-table-and-hp-delta-census.md`,
>   `../findings/c6c-damage-accumulator.md`). Unit conversion, as the card guessed;
>   no chain-length term exists.
> - **Card 27 — SETTLED.** The two codes are status-effect types, not gauge
>   selectors: `0x1D` is the poison tick through wrapper `0x02159500` and `0x1B`
>   the burn tick through `0x02159624`
>   (`../findings/c6b-poison-burn-opcodes.md`,
>   `../findings/c6c-damage-accumulator.md`;
>   [guard-sp.md](../../confirmed-facts/guard-sp.md) §1.5).
> - **Card 28 — SETTLED.** `+0x140` is the pending HP *heal* of the pending-delta
>   family, applied through the plain trampoline, which is why it read zero on every
>   damaging hit; damage rides `+0x134`
>   (`../findings/c5-damage-field-0x134.md`, live-traced in `jus-m92n`). Both
>   mechanisms this card proposed for it turned out to live elsewhere: damage-over-
>   time ticks route through the status opcodes above, and regeneration is an
>   authored per-koma byte ticked by arm9 `0x02077D40` (`jus-b3k2`;
>   [damage.md](../../confirmed-facts/damage.md) §8).
> - **Card 29 — STILL LIVE.** `GrowMax`'s single caller `0x0215C73C`, gated on bit
>   `0x80` of `char+0x128` with a fixed `+0x400`, is still a candidate rather than an
>   identified passive, and it collides with the kind-2 stat modifier id 52 (both
>   raise max HP under the same `0x4000` cap)
>   ([guard-sp.md](../../confirmed-facts/guard-sp.md) §1.5,
>   [helpers.md](../../confirmed-facts/helpers.md) §6,
>   INVENTORY.md §9). Ticket proposed under
>   `jus-ypi5`.
> - **Card 30 — STILL LIVE, reframed.** The insertion-site half stands: of 37
>   ROM-wide hits on immediate `0x558`, the single store is the zero-init, so nothing
>   in the database populates the list
>   ([guard-sp.md](../../confirmed-facts/guard-sp.md) GAP 1). The node-census half is
>   reframed — the nodes are ability-source nodes, not gauge nodes
>   (`jus-second-ability-source-0x558-5rp`), and the guard gauge was found on the
>   fighter object instead (`jus-guard-gauge-found-a55l`). Ticket proposed under
>   `jus-ypi5` as an ability-chain population question, with the base-object
>   ambiguity (`char` vs the ComicDeck player slot, guard-sp GAP 5) folded in.

---

## Resolved by Phase-0 (no longer queued)

These cards from the prior version of this queue are dropped — the question
each was designed to answer is now settled statically (via 3-lens
verification or full-roster re-mining), with no live-behavior question left
to check.

- **Former Session 7 card — destructor active→pending symmetry.** CONFIRMED via 3-lens verify (P3): the destructor's mechanics (`entity+0x2c` bit-0 set, `+0xc`→`+0x1c` list transfer) were re-confirmed byte-for-byte by independent re-disassembly.
- **Former Session 7 card — ownership wrapper `+0xc` = MoveInfo, not character struct.** CONFIRMED via 3-lens verify; the aliasing lens additionally found the direct character-struct back-pointer at wrapper `+0x18` (written by the dispatcher's caller), closing the "more direct back-pointer" open question too. See `../Battle-Engine-Map.md` § projectile-entities claim 4.
- **Former Session 8 (collision-data data-only re-export), all 7 cards.** Superseded wholesale: P1+P2 ran the full 74-battle + 206-support re-export and re-mining this phase.
  - `hitTier` range `{0,1,2,3}` — holds at full scale.
  - `collisionType`→`hitTier` skew generalizing — REFUTED; the real rule is `collisionType ∈ {4,5}` (union), not a clean per-type skew, and both individual correlations weaken to near-coin-flip (47.58% / 58.98%).
  - Knockback monotonic once `bl_b_01` excluded — REFUTED again at full scale; 55/74 (74%) characters are individually non-monotonic.
  - `projectileId=-32` sentinel — REFUTED; 15 distinct nonzero values in battle files, 25 in support.
  - `collisionType=4` necessary for nonzero `projectileId` — REFUTED; real rule is the `{4,5}` union.
  - `hitProperties` per-character constancy — PARTIALLY REFUTED; 26/74 (35%) characters DO mix values within one file (65% remain constant).
  - Opposite-`hitProperties`-on-projectiles pattern — REFUTED; `hitProperties=1` dominates (68%) the nonzero-`projectileId` subset instead.

  See `../Battle-Engine-Map.md` § collision-data for the full round-2 table.

---

## Critic's GDB-first recommendations (refreshed, Phase-0)

These are the highest cross-subsystem-leverage picks in the current queue.
Each substantially overlaps with the sessions above; where a recommendation
adds a static (non-GDB) follow-up alongside a breakpoint, that is noted.

> **Triage 2026-09-04 (`jus-ypi5`):** all five picks are retired — cards 1, 11
> and 21 are superseded, cards 5/7 and 3 are covered by the settled entries
> above, and card 6 is settled. Do not set these breakpoints; read the session
> triage blocks instead.

1. **chr_b cache identity** (= Session 1, card 1) — **new top pick this
   phase.** Break `0x020784E4` (or `0x02077E70`); compare the pointer
   landing in `charPtr+0x56c` against `+0x558`-rooted node addresses.
   Settles chrb-catalog claims 3/11/16 (3 claims) in one shot — the single
   highest-leverage item this phase discovered.
2. **Object identity** (→ Session 1, cards 5/7/11) — break `ov6 0x02158BA8`
   (right after `ldr r0,[r1,#0xe8]`); dump `r1` and separately the live
   pointer chain rooted at `0x023D2A74`; compare equality. If equal, every
   open "is this object the documented character struct or a wrapper"
   question from damage-pipeline/physics-writers/hitstun-timers/weight-hunt
   collapses at once.
3. **Drain-trampoline / `bx ip` sibling sweep** (→ Session 1, card 3;
   Session 8, card 30) — **new this phase.** Confirm `0x020783B8`'s `rsb`
   negation feeds the same `+0x56c` HP gauge (not a hidden second gauge);
   alongside that breakpoint, manually sweep the ROM for further
   `ldr ip,[pc,#N]/ldr r0,[r0,#M]/bx ip`-shaped trampolines with `M != 0x56c`
   — this closes the `xrefs-to`/`pool-values` blind spot this phase
   demonstrated is real and load-bearing, not theoretical.
4. **Hitstun-timer init** (= Session 1, card 11) — break `arm9 0x0207D16C`;
   confirm/deny against a real hit-landing.
5. **Position-vs-timer conflict** (= Session 6, card 21) — break
   `ov4 0x02151E7C`; directly resolves the pre-existing `+0xA0` conflict in
   `docs/research/archive/Character-State-Struct-2026-02.md`.

(Two items from the pre-Phase-0 top-5 — velocity/position-field dumping and
combo-scale flag scope — remain queued as Session 1 cards 7 and 6
respectively; they're no longer in the top 5 given this phase's higher-leverage
discoveries, but are unchanged and still worth doing in the same sitting.)

---

## Time estimate

| Session | Cards | Estimate |
|---------|-------|----------|
| 1 — Live Hit-Landing (ov6) | 12 | 12×5 + 10 = 70 min |
| 2 — Move-Start/MoveInfo | 1 | 1×5 + 10 = 15 min |
| 3 — Character-ID Table | 2 | 2×5 + 10 = 20 min |
| 4 — Character-Select/Roster (ov5) | 4 | 4×5 + 10 = 30 min |
| 5 — Shared-Window Move-Flag Test | 1 | 1×5 + 10 = 15 min |
| 6 — ov4 Position-vs-Timer | 1 | 1×5 + 10 = 15 min |
| 7 — Projectile Lifecycle | 3 | 3×5 + 10 = 25 min |
| 8 — Guard/SP Gauge Mechanics | 6 | 6×5 + 10 = 40 min |
| **Total** | **30** | **≈230 min (~3.8 hours) across 8 sessions** |
