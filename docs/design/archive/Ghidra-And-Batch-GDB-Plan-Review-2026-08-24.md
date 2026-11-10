# Codex adversarial review: Ghidra-And-Batch-GDB-Plan (2026-08-24)

> **Archived 2026-08-25:** The completed plan is
> `Ghidra-And-Batch-GDB-Plan.md`. Its implementation incorporates the accepted
> findings from this review.

> Raw output of the Codex review, kept verbatim for the Pi harness. The plan was
> rewritten the same day: tooling-scope findings were folded in; the harness-phase
> findings (probe isolation, zero-hit oracles, recovery policy, per-item closure
> criteria) apply to "First jobs for the harness" and are NOT yet addressed anywhere
> else — read sections 3 and 4 before running those jobs.

## 1. Critical gaps

1. **The Ghidra overlay representation is undefined.**
   The plan requires “arm9 + all non-stub overlays at their y9 RAM addresses,” while ten overlays share `0x0214CD20` and are mutually exclusive ([plan](Ghidra-And-Batch-GDB-Plan.md:52), [overlay map](../../../docs/research/Overlay-Map.md:7)). Manual BinaryLoader imports normally create separate programs; putting them in one address space would collide. Separate programs, meanwhile, do not automatically provide cross-program callers/xrefs. This directly threatens G1’s API and its cross-binary validation.
   **Mitigation:** Specify one supported topology before implementation: either one Ghidra Program per binary plus a repository-level aggregator, or one Program using explicit overlay address spaces. Define how `(overlay,address)` selects a program/block and how cross-binary calls are synthesized. Test same-address queries against at least ov5 and ov6.

2. **Raw-binary Thumb discovery is not designed.**
   Selecting `ARM:LE:32:v5t` does not, by itself, tell a raw BinaryLoader import which regions/functions are Thumb. Yet G0’s only Thumb step is to “confirm” one region after import ([plan](Ghidra-And-Batch-GDB-Plan.md:61)). This is precisely the class of silent omission G2 is intended to eliminate.
   **Mitigation:** Define how entry points, function starts, and TMode context will be seeded—NDS loader metadata, known function metadata, odd function pointers, call-target propagation, or a checked-in post-import script. Add coverage tests across arm9, ov6, ov8, ov10, and ov12, which the overlay inventory shows all contain Thumb code.

3. **G4 lacks an executable orchestration model.**
   It says the generator emits “one GDB batch script + the `jusemu.py` invocations,” with savestate loads between experiments and every breakpoint command ending in `continue` ([plan](Ghidra-And-Batch-GDB-Plan.md:141)). But a synchronous GDB `continue` does not return while all breakpoint command lists auto-continue. The plan never specifies which process advances the experiment sequence, how it knows a Lua plan finished, or how external savestate commands are synchronized with GDB.
   **Mitigation:** Design an explicit supervisor/state machine. It should own emulator launch, initial standalone savestate load, GDB attach/readiness, probe enablement, Lua-plan execution, completion/timeout, result validation, and recovery. State whether it uses GDB Python, MI async mode, GDB `shell`, or a separate controller.

4. **Probe isolation and attribution are missing.**
   G4 installs all breakpoints up front, but shared functions such as `0x02078488` can fire during setup or another probe. Overlay breakpoints are worse: GDB receives only a runtime address even though the spec records `(overlay,address)`. A hit at a shared address can belong to the wrong resident overlay.
   **Mitigation:** Add an active-experiment identifier visible to every breakpoint command, enable/disable breakpoints per experiment, bracket logs with experiment markers, and verify the expected overlay using a byte signature or residency assertion before accepting a hit.

5. **There is no input/bootstrap preflight.**
   “Ground truth” asserts that extracted binaries and analysis databases exist under `jus_files/` ([plan](Ghidra-And-Batch-GDB-Plan.md:30)), but this checkout currently has an empty `jus_files/` directory. The plan provides no extraction/bootstrap command, expected hashes, filename validation, or required symlink check.
   **Mitigation:** Make G0 start with a fail-fast preflight that verifies every required binary, y9 entry, size/base, hash, analysis database, ROM identity, and writeability of output locations. Point to the exact extraction procedure when absent.

6. **`find_field_writes` has no correctness contract.**
   The plan describes a “P-code def-use walk” resolving stores to an offset, with optional `base_hint` ([plan](Ghidra-And-Batch-GDB-Plan.md:85)). It does not define intraprocedural versus interprocedural scope, alias handling, phi nodes, loops, pointer loads, writeback/post-index addressing, base-identity evidence, or false-negative behavior. Without this, unrelated `+0x134` stores can look authoritative.
   **Mitigation:** Define result categories such as `PROVEN_BASE`, `RESOLVED_OFFSET_ONLY`, and `RANKED_CANDIDATE`, with the complete P-code slice and provenance attached. Build positive and negative fixtures for immediate, register, split-base, post-indexed, loop-carried, and memory-loaded offsets.

7. **G3 has no item-level closure criteria.**
   “Decompile … and trace” is not a falsifiable acceptance condition, yet each item is allowed to close by updating confirmed facts ([plan](Ghidra-And-Batch-GDB-Plan.md:118)).
   **Mitigation:** Give every blocker a precise question, required evidence, success/failure/inconclusive outcomes, and a runtime fallback. “Decompiler output looks plausible” must not be enough to promote a fact.

## 2. Wrong or shaky assumptions

1. **The `+0x134` acceptance target is obsolete.**
   The plan calls this the “pending-damage writer” and acceptance test ([plan](Ghidra-And-Batch-GDB-Plan.md:124)). The canonical inventory explicitly says “`+0x134` / accumulator as the melee path — REFUTED” and names the real residue as transfer from `scratch+0xE8/+0x130` to the HP flush (inventory).
   **Mitigation:** Remove `+0x134` as the acceptance test. Replace it with a still-open, canonical question—most naturally the `+0xE8/+0x130` transfer or one of the actual `.7`–`.13` blockers.

2. **The supposed ARM caller anchor is not an ARM call-site anchor.**
   The plan labels `0x021540AA → 0x02078CB8` an “ARM caller pair” ([plan](Ghidra-And-Batch-GDB-Plan.md:41)). The referenced scanner is explicitly an ARM-and-Thumb scanner and cites this pair alongside the known Thumb site ([find_callers.py](../../../scripts/decomp/find_callers.py:1)). `0x021540AA` is only halfword-aligned, so it cannot be an ARM instruction address. Thus G1 effectively has two Thumb caller anchors and no known-positive ARM caller test.
   **Mitigation:** Correct the label and add a genuinely word-aligned ARM `BL` anchor with expected source overlay and target.

3. **The smoke-test command is invalid.**
   The plan runs `query.py disasm 0x02078488` ([plan](Ghidra-And-Batch-GDB-Plan.md:67)), but the referenced CLI requires `disasm <addr> <n>` ([query.py](../../../scripts/analysis/query.py:43)). The command currently exits 2. The older D0.3 recipe contains the same error.
   **Mitigation:** Supply an explicit count, such as `disasm 0x02078488 20`, and make the smoke test automated.

4. **A bad decompilation does not imply only a bad base address or processor spec.**
   G0 says failure to show clamped-add semantics means “the base address or processor spec is wrong” ([plan](Ghidra-And-Batch-GDB-Plan.md:67)). Other causes include failure to create a function, incorrect TMode context, incomplete analysis, analysis timeout, wrong program selection, decompiler limitations, or stale project state.
   **Mitigation:** Replace that diagnosis with a checklist that separately verifies bytes, address mapping, instruction mode, function boundary, references, analyzer completion, and decompiler output.

5. **The existing DB is not a generally safe “ARM-mode branch/caller” fast path.**
   The plan routes only Thumb-sensitive and data-flow questions to Ghidra ([plan](Ghidra-And-Batch-GDB-Plan.md:35)). The supporting map says the existing call graph is intra-binary only and has zero cross-binary edges ([overlay map](../../../docs/research/Overlay-Map.md:114)); the atlas also documents ARM indirect `bx ip` references invisible to the old xref tools.
   **Mitigation:** Narrow the claim to immediate ARM branches within the DB’s measured coverage. Route cross-binary and indirect-call questions through the new layer or a dedicated raw decoder.

6. **Recording dependency versions is not reproducibility.**
   G0 pins Java via mise but installs whichever Ghidra release Homebrew or the release page supplies, tries an unpinned plugin, and G1 installs an unpinned PyGhidra package or bundled wheel ([plan](Ghidra-And-Batch-GDB-Plan.md:57)). Plugin, Ghidra, and PyGhidra versions may be mutually incompatible.
   **Mitigation:** Pin Ghidra, NTRGhidra commit/release, and PyGhidra source/version; verify them at runtime; document checksums and a supported compatibility matrix.

7. **“Pure Python + GDB scripts” does not establish portability.**
   The plan and Linux notes claim only the emulator harness needs porting ([plan](Ghidra-And-Batch-GDB-Plan.md:165), [Linux notes](../../../NOTES_FOR_LINUX.md:63)). The referenced GDB guide uses different binaries on macOS and Linux and already contains stale configuration guidance. GDB Python availability, command syntax, shell paths, and output formatting can differ.
   **Mitigation:** Define supported GDB implementations and add a Linux/macOS generator golden test plus an actual attach smoke test on each.

8. **G0 is not actually “the same project” as D0.3 yet.**
   G0 uses `scripts/ghidra/import_project.sh` and `scripts/ghidra/project/`; D0.3 specifies `scripts/decomp/import_ghidra.sh` and `scripts/decomp/ghidra/` ([D0.3](../../../docs/design/Decomp-Tier2-Plan.md:145)). Simply checking D0.3’s boxes would leave its prescribed paths and commands false.
   **Mitigation:** Amend D0.3 to delegate explicitly to G0 and replace its old file list/recipe, rather than merely checking it complete.

## 3. Failure modes

1. **Imports succeed but produce missing or false xrefs.** Separate overlay programs lose cross-program references; one combined program collides at shared addresses.
   **Mitigation:** Add acceptance tests for arm9↔ov6 calls, same-address ov5/ov6 queries, and explicit negative tests preventing cross-overlay phantom edges.

2. **A partial analysis is mistaken for a complete project.** The inherited D0.3 recipe allows per-file analysis timeouts, while G0 has no manifest recording which analyzers completed.
   **Mitigation:** Build into a temporary project, fail on timeout/analyzer error, write an analyzed-program manifest, and atomically promote only after all validation passes.

3. **Re-running the import leaves duplicate or stale programs.** No idempotency or rollback behavior is specified.
   **Mitigation:** Default to rebuilding a new project directory from scratch, validate it, then swap it into place. Never mutate the last known-good project in place.

4. **Concurrent sessions lock or mutate the persistent project.** The roadmap is explicitly multi-session, but there is no project lock or read-only query policy.
   **Mitigation:** Serialize rebuilds, open query sessions read-only where possible, and record the project generation/hash in every result.

5. **JSON results become stale or overwrite each other.** G1 writes under one directory but does not define filenames, schema version, binary hash, project generation, atomic writes, or overlay disambiguation.
   **Mitigation:** Use deterministic names including query, overlay, address, and input hash; write atomically; include tool/project/binary versions in every result.

6. **The Lua bridge silently dies during savestate handling.** The referenced README says embedding `load_state` in a plan freezes `_Update()` and requires a separate `jusemu.py state load` command ([emulator README](../../../scripts/emu/README.md:229)). G4’s per-probe `savestate` plus `Lua plan` model does not encode that ordering constraint.
   **Mitigation:** Make savestate load a distinct supervisor step, then require fresh heartbeat/framecount confirmation before starting the Lua plan.

7. **One disconnect invalidates the whole batch and leaves the emulator halted.** This is documented behavior ([emulator README](../../../scripts/emu/README.md:261)), but G4 has no recovery or partial-result policy.
   **Mitigation:** Mark all not-yet-completed probes invalid, preserve completed logs, relaunch cleanly with controlled IPC preservation, and resume from the first incomplete probe.

8. **Breakpoints collect hits from the wrong experiment.** Installing all breakpoints up front means setup, savestate settling, or another Lua plan can trigger them.
   **Mitigation:** Enable only the active probe group, tag every event with the current experiment ID and frame window, and reject hits outside that window.

9. **A “healthy” zero-hit result is still behaviorally invalid.** Health markers alone do not prove the intended move occurred, connected, faced correctly, or ran from the expected savestate. The README documents silent whiffs and free-running frame drift.
   **Mitigation:** Require a behavioral oracle per experiment—HP change, animation/state transition, Lua completion marker, expected frame interval, or a paired known-positive control.

10. **Memory capture can dereference invalid or session-local pointers.** The inventory warns runtime addresses are session-local, and the emulator README calls pointer-chain watches unverified in some modes.
    **Mitigation:** Let capture expressions declare width, signedness, endianness, pointer-validation range, and failure policy. Re-resolve dynamic roots after every savestate load.

11. **G2 misses load-bearing claims despite satisfying its grep step.** The fixed phrase list excludes variants such as “never referenced,” “zero hits,” “no producer,” “only direct caller,” and negative claims stored in tables or findings that canonical docs cite.
    **Mitigation:** Start from the inventory’s disputed/tooling-hazard catalog and tracker items, then supplement it with a broader semantic search. Track audited claims in a manifest rather than treating grep output as complete.

12. **Documentation can declare the blind spot fixed too early.** G2 updates the inventory to say the Thumb gap is mitigated after a small anchor set, even though raw-import mode recovery may still be incomplete.
    **Mitigation:** Publish measured coverage and known exclusions. Say “mitigated for these validated regions/query types,” not globally mitigated.

## 4. Open questions the plan should answer before execution

1. Will each binary be a separate Ghidra Program, or will overlays use Ghidra overlay address spaces? How will G1 aggregate cross-program references?

2. What exact mechanism seeds ARM/Thumb mode and function entry points for raw imports?

3. Which Ghidra, NTRGhidra, PyGhidra, Java, and processor-spec versions are supported and pinned?

4. What canonical input layout is authoritative: `jus_files/ripped_jus_files/ftc/` from the plan, or `jus_files/arm9`/`jus_files/overlays` used by the referenced caller scripts? How is a missing external data tree restored?

5. What replaces the refuted `+0x134` acceptance test?

6. What is the exact result and confidence schema for `find_field_writes`, especially when `base_hint` cannot be proven?

7. What constitutes successful, inconclusive, and failed completion for each G3 blocker?

8. Which process orchestrates GDB, `jusemu.py`, savestates, and Lua plans, and how does it synchronize transitions without disconnecting?

9. How are breakpoints scoped to the active experiment and verified against the expected resident overlay?

10. What are the timeout, retry, rollback, and resume rules after a GDB error, bridge freeze, emulator crash, or partial batch?

11. What exact positive control and behavioral oracle makes each zero-hit result admissible?

12. Should G0 replace D0.3’s old paths and recipe, and which file becomes the sole authoritative Ghidra setup documentation?

13. Is G2 auditing only canonical prose, or also findings/tracker items that canonical claims depend on? How will audit completeness be demonstrated?

14. Why does the plan use the tracker's ready list while its referenced playbook still prescribes the legacy client's `ready` and `sync` commands ([playbook](../../../docs/harness/RE-Session-Playbook.md:8))? Which workflow is authoritative for phase tracking and landing work?
