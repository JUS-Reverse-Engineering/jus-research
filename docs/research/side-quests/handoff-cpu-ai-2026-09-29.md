# Handoff — JUS offline CPU AI, step 7 (2026-09-29)

## Goal
Make the offline CPU AI in the patched `.nds` "vastly better" against four owner complaints:
careless attacks, bad punishes, self-KOs, the broken-wall freeze. You orchestrate: pick the work,
write briefs, delegate mechanical/emulator work to subagents, interpret the numbers.
**Never drive the emulator yourself.**

This session advanced **step 7 (bad punishes)**: the punish predicate. The predicate's inputs are
now located, and its justifying measurement is answered from existing data — the band fires on an
idle opponent, so the predicate has a target.

## State
Repo `jus_re`, branch `main`, **up to date with origin at `eb2dcd4c`**. Emulator slot **free**
(no `JUS_EMU_HOLDER`, no `/tmp/jus_emu/HOLDER`).

- **Step 7 static pass done** `[verified, shipped eb2dcd4c]`. The motion object is located:
  - **Animation id**: `[[char+0x1A0]+0x1BC]` (CharaData+0x1BC, u32 0..23; sole writer ov6
    `0x0215F29C`). One dereference. `[verified]`
  - **Frame**: not on the fighter. It is the middleware ALMT clip's `+0x2A` (getter arm9
    `0x0204ADE4`, clip vtable `+0x14C`; sole writer the clip seek `0x0201F12C`). Chain from the
    fighter: `char+0x1B8 -> [+8] -> [+4] -> +0x68 -> +0x2A`. The last hop (`player+0x68 = clip`) is
    **medium** confidence; a shallower `[[char+0x1BC]+4]` candidate is open. `[verified static;
    frame link needs one live read]`
- **ov11 -> opponent fighter object: closed** `[verified]`. `AI` is its own slot in the AI manager
  array (`manager+0xa8+idx*0x10C`, stride `0x10C`, one slot per player), and `[slot+0x20]` is that
  slot's fighter object. The sibling slot (`AI ± 0x10C`) is the opponent; the existing
  `ai_actions` capture's `meta.json` confirms both slots populated. No fighter table needed.
- **Step 7 section-6 measurement, first half: answered from existing data, zero jobs**
  `[verified]`. Of the 17 band fires (ids 13/14) in the funnel census arm B, the opponent was
  **idle (state 0) on 16** and in **hitstun (8) on 1**; it was **never in landing (13) and never in
  attack (9)** in all 3842 frames. The band fired on only 1 of the opponent's 1030 hitstun frames.
  So the band is not tracking recoveries: **the predicate has a measured target**; the "adds
  nothing, stop" branch is refuted.
- `jus-ai-step7-punish-predicate-gi2n` is now labelled `act:gated-emulator` (next work is a capture).

## Artifacts
- **Plan of record**: `docs/research/side-quests/cpu-ai-judgement-plan.md` — step-7 spec §3–§5, and
  the new **§3.1** (motion object) and **§6.1** (the census result, with the 17-row table).
- Tracker item: `jus-ai-step7-punish-predicate-gi2n` (description + three finding comments).
- Funnel census (the §6.1 source, **ephemeral**): `<TMP>/ai-funnel/` —
  `B-idle_in_action_set.gdb.jsonl` (per-frame `st1`/`st2`/`c0`), `B-idle_in_action_set.result.json`
  (78 issue rows), `ai_funnel.gdb`. The decisive 17 rows are copied into plan §6.1.
- Measurements: `cpu-ai-levels.md` §3.25–§3.29; protocol `ai-capture-protocol.md`.
  Standing capture: `docs/research/side-quests/ai-phase-capture-2026-09-28/`.
  Durable bridge captures: `jus_files/captures/` (submodule).
- Bridge: `scripts/emu/agent_bridge.lua` (`plan_step`, `read_watch`, `state_load`,
  `keep_neutral`). Emulator contract: `scripts/emu/launch_emu.sh` / `stop_emu.sh`.
  RAM AI patch: `scripts/emu/ai_patch_ram.py --set idle_in_action_set|... --show`.

## Decisions (do not silently reverse)
- **Step 7's next work is emulator-gated.** The first half of §6 is done from disk; do not re-run to
  reproduce it.
- **The predicate is not yet worth building**, because the fixture's opponent never attacks, so the
  state-13 and state-9 clauses are untestable. Build it only after the capture below.
- **Section 6.1's fixture detail**: the AI is **P2 (slot 1, `0x02181C14`)**; the opponent is **P1**
  (`st1 = *(u8*)0x02228E98`). Slot0 (`0x02181B08`) is P1, slot1 is P2 — from `ai_actions/meta.json`.
- **The frame is middleware, not a fighter field.** `obj+0x6C/+0x70/+0x72` are the input sampler
  (ov6 `0x02161148`, `r4 = obj+0x1C`), not animation. Do not revive them.
- **Patched arm = a RAM poke, never a ROM build** (savestates mask ROM patches).
- **Compare captures on `fc`, never row index.** Determinism criterion is "no divergence persisting
  beyond one row"; the `torn` flag is too weak. `opencode/gpt-6-sol` via the subagent tool fails
  ("insufficient funds"); use `codex exec -m gpt-6-sol -s read-only -C <repo>`.
- Subagents write only to `<TMP>`; **the orchestrator owns all commits**.
- Data patches beat code edits where possible. One emulator job at a time.

## Dead ends (don't repeat)
- **The `ai_actions`/standing captures cannot answer §6's second half.** The opponent (P1) is idle
  or hitstun there too — never state 13 or 9. Agreeing with §6.1.
- **`0x02173024` (the slot+0x20 writer) has no direct/literal caller** in arm9 or any overlay
  (arm+thumb BL/BLX scan, and a literal-word scan). It is a computed call; do not spend a static
  pass hunting it.
- **`[ctx+8]` is AI-behaviour-builder territory** (`ctx = [[AI+0x24]]`, a 0xCC object); it is not
  the opponent's motion object. Do not re-derive it as the animation link.
- **ids 13/14 are not "a punish band" by measurement** — that is still an inference. §6.1 shows only
  that they fire without a recovery. Do not promote the label.
- Never `pkill`; release with `bash scripts/emu/stop_emu.sh --force`.

## Next move
1. **One bridge-only capture on a fixture where the opponent (P1) actually attacks** — script P1
   with a plan (`scripts/emu/plans/*.json`, e.g. jump + B, via the bridge's input mask), apply
   `ai_patch_ram.py --set idle_in_action_set` after `state_load`, and watch per frame: the AI slot
   `0x02181C14` (`+0x39`, `+0x3A`, `+0x48`, `+0x105`, `+0x10A`, `+0x2C`, `+0x24`), `ctx+0xC0..+0xC3`
   (the live resolved ids, to detect 13/14 without a breakpoint), and **P1** `0x02228E80`
   (`+0x18`, `+0x114`, `+0x110`) plus **P2** `0x0224EF00` (same). The question: does the band
   *also* fire when P1 is in a true recovery (state 13, or state 8 with `+0x114 > 0`)? Model the
   driver on `<TMP>/ai-determinism/determinism_run.py` and `ai_patch_ram.py`.
   **Then** decide whether the predicate is worth building (§5's resident site, veto-on-nonzero
   polarity at `0x0217ADAC`). If it is, run `interrogate` before injecting.
2. Fallbacks: pin the frame link (`clip+0x2A`) in the same capture with one resolved read; or
   `1kz8`'s open question; or step 8 (self-KO path, parked).

## Suggested skills
- `recall` — reconstruct this session's context if this doc is thin.
- `diagnosing-bugs` — if a capture contradicts §6.1 or §3.1.
- `interrogate` — before any patch is injected, to challenge the predicate independently.
- `unslop` — for doc edits. `handoff` again at the end of the next session.
