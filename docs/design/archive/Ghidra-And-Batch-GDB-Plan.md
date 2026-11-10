# Ghidra Query Layer + Batch GDB Experiments Plan

> **Archived 2026-08-25:** Phases G0-G3 are complete. The parent epic
> `jus-ghidra-tooling-j4i2` is closed; five focused G2 contradiction children remain
> open for follow-up.

> **Scope: tooling + the Thumb audit sweep.** This plan installs the instruments, proves
> each one works with a test run, and runs one real job: the audit of negative claims the
> old tools' Thumb blind spot may have poisoned (Phase G2). The battle-gap investigations
> and the GDB experiment queue run later in the Pi.dev harness — see "First jobs for the
> harness" at the end. Update checkboxes here as tasks complete. File a tracker item per phase
> before starting it.
>
> Adversarially reviewed 2026-08-24 (Codex): `Ghidra-And-Batch-GDB-Plan-Review-2026-08-24.md`.
> The verified findings are folded in below; the harness-phase findings (probe isolation,
> zero-hit oracles, recovery policy) are flagged in the handoff section.

**Goal:** Put the missing static-analysis capability in place (Ghidra: decompilation +
P-code data flow + correct Thumb handling) and a batch GDB experiment generator, each
validated against a known ground truth, ready for the Pi harness to use on the open battle
gaps (spec blockers `.7`–`.13`).

**Why:** The handwritten static indexes have documented blind spots that already caused
retractions — `ov6.txt` decodes Thumb regions as ARM, `xrefs.json` misses Thumb `blx` sites
and ~89% of Thumb literal loads, register-computed store offsets are invisible
(`docs/research/findings/d03-ghidra-blocked-and-a-failed-tool.md`), and the existing call
graph has zero cross-binary edges (`docs/research/Overlay-Map.md`). Ghidra handles
ARM/Thumb interworking and P-code data flow natively. The install was blocked only on owner
authorization; Owner gave it 2026-08-24.

**Scope guard:** This is an instrument, not a platform. No provider registry, no plan
language, no evidence database. The deferred platform design lives in
`Reusable-RE-Platform.md`. Findings land in the existing confirmed-facts/tracker items workflow
unchanged.

**Relationship to `Decomp-Tier2-Plan.md`:** Task D0.3 there specifies a Ghidra project for
decompilation drafting, with different paths (`scripts/decomp/import_ghidra.sh`). When G0
completes, **amend D0.3 to delegate here** — replace its file list and recipe with a pointer
to this plan — rather than only checking its boxes, so its stale paths don't survive as
false instructions.

---

## Ground truth (as of 2026-08-24)

- Game data lives in the `jus_files` **submodule** — `git submodule update --init` first.
  A fresh checkout has an empty `jus_files/`; every phase below starts with a preflight
  that fails fast if the inputs are missing.
- **Authoritative input layout** (verified 2026-08-24): `jus_files/arm9/arm9.bin` +
  `jus_files/overlays/ov*.bin`, with manifests `jus_files/arm9/binaries.json` and
  `jus_files/overlays/overlays.json` — this is what the decomp scripts read.
  `jus_files/ripped_jus_files/ftc/` is the raw rip it was derived from; don't import from
  it. Overlay RAM ranges and residency: `docs/research/Overlay-Map.md`,
  `docs/research/Overlay-Residency-By-Mode.md`.
  **Ten overlays share `0x0214CD20` and are mutually exclusive at runtime** — the import
  topology must handle same-address overlays (G0 Step 2).
- Existing static DB: `jus_files/analysis/` (`functions.json`, `xrefs.json`, `disasm/`),
  queried via `scripts/analysis/query.py`. Keep it — it stays the fast path for
  **immediate ARM branches within one binary** (its measured coverage). Route Thumb,
  cross-binary, indirect-call, and data-flow questions to Ghidra.
- Validation anchors (known-true facts any Ghidra result must reproduce):
  - `0x02078488` = `ApplyDeltaToCurrent`, clamped add (Battle-Engine-Map.md). Decompile
    must show it. Compare against `python3 scripts/analysis/query.py disasm 0x02078488 20`
    (the `n` argument is required).
  - Thumb call site `0x02150DD8` producing `lr = 0x02150DDD` (live-GDB ground truth), and
    the pair `0x021540AA → 0x02078CB8` — **also a Thumb-side anchor** (`0x021540AA` is
    halfword-aligned, not an ARM instruction address; `find_callers.py` decodes both ARM
    and Thumb). ARM-mode candidate anchor: `ov5 0x02156C70` `arm-bl → 0x02078CB8`
    (word-aligned, reported by `find_callers.py` 2026-08-24) — hand-confirm the encoding
    during G1 validation before treating it as ground truth, since it comes from the same
    tool family being validated.
- GDB stub constraints (`scripts/emu/README.md`): one attach per emulator launch (the stub
  never survives a disconnect); breakpoint command lists must end in `continue`; use
  `handle SIGILL nopass`; savestate loads with GDB attached work, **but `load_state`
  embedded in a Lua plan kills the bridge** — savestate load is always its own
  `jusemu.py state load` step; **no hardware watchpoints** (`jus-fun`) — substitute
  breakpoints on statically-found candidate writers.
- Addresses are always recorded as (overlay, address), never bare — Overlay-Map.md rule.

---

## Phase G0 — Ghidra project

Exit criterion: `scripts/ghidra/import_project.sh` reproducibly builds a Ghidra project
containing arm9 + all non-stub overlays, same-address overlays included, and all smoke
tests pass.

- [x] **Step 0: Preflight.** Script checks before any import: submodule initialized, every
  input binary present with expected size, y9 table readable, output dir writable. Fail
  fast with the fix (`git submodule update --init`) when missing.
- [x] **Step 1: Install.** JDK comes from mise: `mise install` (repo `mise.toml` pins
  `java = "temurin-21"`). Ghidra itself is not in the mise registry (checked 2026-08-24) —
  installed via Homebrew **formula** (`brew install ghidra`, Cellar path — no Caskroom).
  **Pin versions:** Ghidra 12.1.3 + JDK temurin-21 are recorded in the import script
  header and verified at run time (NTRGhidra is not installed/used — see Step 2).
- [x] **Step 2: Decide the overlay topology, then import.** Decision: **one Ghidra Program
  per binary** (BinaryLoader), not NTRGhidra — NTRGhidra loads the whole ROM and would
  recreate the same-address collision (ov00–ov08 all at 0x0214CD20) in one address space,
  and has no release pinned to Ghidra 12.1.3. The (overlay, address) → program mapping is
  in the script header. Same-address overlays (ov5/ov6/ov0–ov8, ov10/ov11, ov12) each get
  their own Program. Project dir `scripts/ghidra/project/` is gitignored; rebuilds go to a
  fresh temp dir, validate, then atomic-swap into place.
- [x] **Step 3: Thumb seeding.** Seeded from `functions.json` starts: a `SeedThumb.java`
  postScript sets the TMode context register to 1 at every `mode:"thumb"` start (before
  disassembly, on a `-noanalysis` import) then creates a Function at every seed (arm and
  thumb). Ghidra's analysis then propagates BL/BLX/call edges. No aggressive instruction
  finders (false positives); the seed list is the deliberate, documented source.
- [x] **Step 4: Smoke tests (scripted, not eyeballed).** `SmokeTest.java` postScript:
  (a) Decompile `0x02078488`; the C must show clamped-add semantics (signed hw load at
  +0x18, clamp low at 0, clamp high at max from +0x16, store back, boolean return). On
  failure, walk a checklist — bytes at address, base mapping, instruction mode, function
  boundary, analyzer completion — not just "base address wrong";
  (b) confirms `0x02150DD8` disassembles as Thumb (`TMode=true`) and its `blx` resolves to
  `0x020783CC`, plus ARM `bl` anchor `0x02156C70 → 0x02078CB8`;
  (c) `analysisTimeoutOccurred()` must be false — the orchestrator greps the build log for
  `Analysis timed out` and any `SMOKE_*_FAIL` and fails the build rather than shipping a
  half-analyzed project. Plus an explicit same-address distinct-bytes test: ov5/ov6 both
  base 0x0214CD20 must each hold their own bytes (first 32B, a deeper region, and the
  byte just past ov5's end that only exists in ov6) — the per-program topology is proven,
  not assumed.
- [x] **Step 5: Docs.** Updated the Ghidra section in `NOTES_FOR_LINUX.md` (Cellar vs
  Caskroom path, NTRGhidra decision, topology decision, analyzeHeadless exit-code quirk).
  Amended D0.3 in `Decomp-Tier2-Plan.md` to delegate here (DONE-BY-DELEGATION).
- [x] **Step 6: Commit** the script + `.gitignore` entry (project dir never committed).

## Phase G1 — Thin PyGhidra query layer

Exit criterion: the queries below run from the repo root against the persistent project and
return correct results for the validation anchors, including one hand-confirmed ARM-mode
caller and one Thumb caller.

- [x] **Step 1:** Install PyGhidra **pinned to the G0 Ghidra release** (the bundled wheel
  under `ghidra_*/Ghidra/Features/PyGhidra` guarantees the match). Verify it opens the G0
  project without re-analyzing.
- [x] **Step 2:** Create `scripts/ghidra/analysis.py` — one class, no registry:
  `decompile(addr)`, `callers(addr)`, `callees(addr)`, `xrefs_to(addr)`,
  `xrefs_from(addr)`, `find_field_writes(offset, base_hint=None)`. Every function takes
  and reports (overlay, address) pairs, resolved per the G0 topology decision.
  `find_field_writes` labels each result with a confidence category — at minimum
  `PROVEN_BASE` (base identity established), `RESOLVED_OFFSET_ONLY` (offset proven, base
  not), `RANKED_CANDIDATE` — and attaches the P-code slice it walked. An unlabeled store
  list looks authoritative and isn't; that failure mode has bitten this project before.
- [x] **Step 3:** CLI wrapper `scripts/ghidra/query.py`, mirroring
  `scripts/analysis/query.py` subcommand style. Output convention: full results as JSON to
  `jus_files/analysis/ghidra/` with deterministic names (query, overlay, address) and the
  Ghidra/project versions embedded in each file; a count-and-highlights summary to stdout.
  Never print thousand-row dumps.
- [x] **Step 4: Validate** against the anchors: the clamped-add decompile, the Thumb caller
  at `0x02150DD8`, one hand-confirmed word-aligned ARM `BL` pair, and one arm9↔ov6
  cross-binary call. For `find_field_writes`, build small positive/negative fixtures:
  immediate offset, register offset, split base, post-indexed — pass criteria per
  category, not "looks right".
- [x] **Step 5: Docs.** Add the query layer to `docs/AI-ASSISTANT-GUIDE.md`'s tooling
  section, one line: what it answers that `scripts/analysis/query.py` cannot (Thumb,
  cross-binary, indirect calls, data flow, decompilation). Commit.

## Phase G2 — Thumb audit sweep

The first real job for the new layer, and its acceptance test at scale: wrong "no caller /
dead / sole producer" claims baked into specifications are the most expensive error this
project produces, and the old tools' Thumb blind spot is the likeliest source.

Exit criterion: every claim in the audit manifest re-checked through the G1 layer, with
contradictions filed as tracker items and the manifest committed.

- [x] **Step 1: Build the audit manifest.** Start from INVENTORY.md's tooling-hazard
  catalog and the taint tracker items, then supplement with a search of canon docs (not
  `findings/` — that journal is history, not current) for negative claims: "no caller",
  "dead", "vestigial", "unreachable", "sole producer", "only writer", plus variants —
  "never referenced", "zero hits", "no producer", "only direct caller". Include negative
  claims in tables, not just prose. The manifest lists (claim, doc, address) and is the
  completeness record — grep output alone is not.
- [x] **Step 2: Re-check each claim** through the G1 layer. Diff against the original
  conclusion. Record the result per manifest row: confirmed / contradicted / inconclusive.
- [x] **Step 3: For each contradiction:** file a tracker item, banner the doc section, and note
  whether any confirmed-facts entry or spec ticket (`.7`–`.13`) leaned on it. Do not
  silently edit numbers — follow the existing taint protocol (INVENTORY.md ground rules).
- [x] **Step 4: Scope the all-clear honestly.** Update INVENTORY.md's tooling-hazards
  note to say the Thumb blind spot is mitigated **for the audited claims and validated
  query types** — not globally. Commit the manifest alongside.

## Phase G3 — Batch GDB experiment generator

One emulator launch, one GDB attach, several experiments. Justified by the stub constraints
(see Ground truth), not by token savings. This phase builds and proves the tool; running
the real experiment queue is harness work.

Exit criterion: a spec file describing probes compiles to a runnable session, the dry run
below completes end-to-end, and per-probe results land in a session log with health
markers.

- [x] **Step 1:** Define the experiment spec (JSON, matching the existing plan-file
  style). Fields per probe: name, breakpoint (overlay, address), registers/memory to
  capture, savestate, Lua plan, expected-hit criterion, and a **positive control** — the
  behavioral evidence that makes a zero-hit result admissible (an HP change, a plan
  completion marker), since the README documents silent whiffs that read as clean misses.
- [x] **Step 2:** Generator `scripts/gdb/compile_experiments.py` plus a small supervisor
  that owns the sequence: launch, standalone `jusemu.py state load` (never inside a Lua
  plan — that kills the bridge), heartbeat confirmation, GDB attach, enable **only the
  active probe's breakpoints** (a shared function like `0x02078488` fires during other
  probes' runs if left enabled), run the Lua plan, collect, next. Hard rules baked in:
  command lists end in `continue`, `handle SIGILL nopass`, experiment-ID markers bracket
  every log section.
- [x] **Step 3: Dry run** with a known-positive: break `0x02078488` (HP-delta apply) on a
  scripted hit — the unfinished experiment at the bottom of `scripts/emu/README.md`. One
  launch, one attach, damage plan, confirm `r1`/`lr` capture and that the health markers
  plus positive control appear in the log.
- [x] **Step 4: Docs.** Document the generator in `scripts/gdb/README.md`. Note in
  `NOTES_FOR_LINUX.md` which pieces are portable (the generator/supervisor are Python +
  GDB scripts, but macOS uses `arm-none-eabi-gdb` and Linux `gdb-multiarch` — verify with
  an attach smoke test on each OS, don't assume).

---

## First jobs for the harness (out of scope here)

The Pi.dev harness runs these once the tooling above lands. Recorded so the handoff is
explicit, not to be executed under this plan:

1. **The open battle gaps**, in spec-blocker order, each with a falsifiable closure
   criterion (question, required evidence, success/failure/inconclusive outcomes) before
   starting: the B11 residue transfer — how the formula's output at `scratch+0xE8`/`+0x130`
   reaches the HP flush at `0x02158B20` (the natural first `find_field_writes` target;
   **not** `+0x134`, whose melee-path role is REFUTED per INVENTORY); contact-array
   magnitudes (`.7`); move priority (`.8`); projectileId selector (`.9`); SP model
   (`.10`/`.13`).
2. **The ready-queue GDB-experiment tickets** in batched sessions — weight (`jus-9lp.2.1`),
   position fields (`jus-9lp.2.3`), hitstun (`jus-9lp.2.2`), walk speed (`jus-n3p.1`),
   jpower lookup (`jus-9lp.1.2`), the atlas asks (`jus-45k`, `jus-zko`, `jus-n4n`).
   Grouped by savestate to minimize launches. The review's recovery findings apply here:
   on a mid-batch disconnect, completed probes keep their results, everything after is
   invalid, relaunch resumes from the first incomplete probe.

## Standing doc-maintenance rules for this plan

- Every phase that adds a tool updates the tool's own README plus the one-line pointer in
  `docs/AI-ASSISTANT-GUIDE.md`.
- Anything install- or OS-specific lands in `NOTES_FOR_LINUX.md` in the same commit.
- Findings never live only in this plan: confirmed facts go to `docs/confirmed-facts/`,
  contradictions become tracker items, retractions follow the taint protocol.
- Check boxes here as tasks complete; this file is the roadmap's single source of progress.
