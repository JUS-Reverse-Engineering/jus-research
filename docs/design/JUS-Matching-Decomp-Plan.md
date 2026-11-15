# JUS matching decompilation plan

## Session checkpoint and resume, 2026-10-06

The owner requested a stop before the next source trial. This checkpoint supersedes older progress paragraphs below; those paragraphs retain the evidence history.

- A working macOS build path is established, with native linking and the recovered Metrowerks compiler running through Wibo. Fresh accepted verification reproduces the entire 67,108,864-byte original ROM.
- Seven reviewed parent functions compile to the original bytes: 304 bytes total, split into 272 game bytes and 32 SDK/runtime bytes. This is partial source reconstruction; the global source denominator is still unknown.
- The secondary processor and embedded Download Play program have checked binary reconstruction and research integration. Seven experimental ARM7 objects cover 460 distinct bytes and preserve both program images and the entire ROM. ARM7 accepted source credit remains zero; research matches do not close T10.
- `jus-bjry.35` through `.38` are closed. The constructor contract, one stopped initializer trial and the helper's exact arithmetic contract are published. The initializer trial differed at ten unmasked byte positions and was rejected without tuning. Original C++ identity, complete ownership and remaining pilot functions are still unresolved.
- The owner's reuse map is saved under “Reusable evidence for later source reconstruction.” Check those records before repeating static analysis. Original helper `020326b0` has 62 actual incoming call sites across 42 region-qualified functions; the saved query omits two Thumb calls.
- `jus-bjry.39` is in progress at the build-path grounding stage. An independent fresh extraction isolates the exact forty-four-byte helper and preserves all sixty-two calls; root confirms its original-object comparison. Changed-original controls and final input pins are still pending. No candidate design has been selected, no target C body written and no new compiler trial run. T06, T10 and the epic remain open; T07/T11 emulator work remains gated.

Durable records are the [JUSDecomp Track A branch](https://github.com/JUS-Reverse-Engineering/JUSDecomp/tree/track-a/matching) and this plan in [the tracker repository](https://github.com/JUS-Reverse-Engineering/jus-research/blob/main/docs/design/JUS-Matching-Decomp-Plan.md). The latest accepted helper result is `1ebd198`; its separately reviewed audit copy is `90da82e`. The helper capsule contains twenty files and passes its thirty-two-pin committed-artifact gate. The next-trial grounding checkpoint is saved in `1687b1b`; its eight metadata pins and the helper gate also pass in a fresh Git checkout. The final publication audit inspects the accepted result, not later source-trial notes.

Resume with tracker item `jus-bjry.39`. Read [the session handoff](handoff-jus-track-a-2026-10-06.md) for saved decisions and next steps. Read its saved grounding notes in `decomp/matching-notes/pilot-t06/physical-fold-source-trial/design/` on the Track A branch, then finish any explicitly unrun original-reference checks. The next required step is two distinct unimplemented designs, independent comparison, root synthesis and a published release before writing C or compiling. Use the existing pinned ARM946E MW build114 header-free `-O2` context. One frozen model and recipe are allowed; a strict miss stops the model, while a strict match must continue actual native-input, placement, module and whole-ROM checks. Canonical promotion remains a separate scope. Do not retry the stopped initializer as part of this helper trial.

Use a fresh isolated worktree from the published Track A branch. Temporary checkout paths are conveniences, not the durable record. Keep the main research checkout's existing uncommitted files and stash intact. Its Git checkout predates the published tracker commits; this local checkpoint was inserted without replacing the owner's existing plan edits.


> Kind: Working design. This is a plan for source reconstruction, not evidence about game mechanics.
> Planning record: `jus-h8ob`. Type: enhancement. Complexity: complex.

Resurrect Track A in a branch of JUSDecomp. Preserve its binary reconstruction work,
then replace original code with maintainable, matching C and C++ one translation unit
at a time. Keep this effort separate from the
[nonmatching Tier-2 roadmap](Decomp-Tier2-Plan.md).

This plan authorizes no implementation by itself. The current deliverable is the plan
and its task backlog. On execution, use a dedicated JUSDecomp checkout at
`<TMP>/jus-track-a` on branch `track-a/matching`; keep this repository as the
research and planning record. Use persistent remote commits, not the temporary path,
as the durable source of work. At T01, use a JUSDecomp fork owned by the authenticated
GitHub account as `origin`, and piuzera/JUSDecomp as read-only `upstream`. Reuse an
existing fork only after checking its parent repository. If that account has an unrelated
repository with the same name, create the fork as `JUSDecomp-track-a` instead. Record
the resolved remote URL in the baseline report. Do not change upstream's Track C default branch.

## Execution amendment: native linker baseline

On 2026-10-04 the owner confirmed that the private Metrowerks linker is unavailable
and authorized a Unix or macOS alternative, followed by autonomous continuation.
T01 keeps upstream `6a061e3897f10a8800bf7ec9afde82fa8c9dbe1b`, dsd 0.12.0,
original ROM identity, and all module/layout acceptance gates. LLVM lld 23.1.2
replaces the unavailable linker. Its binary and the Clang attributes generator are
pinned separately. This does not claim the original Metrowerks binary was reproduced.

The native adapter normalizes copied reference ELF metadata and translates the
pinned LCF. All 17 ARM9 modules, including autoloads and zero stubs, pass original
dsd module checking, direct original-ROM bytes, load addresses, and BSS extents.
Original dsd symbol checking passes on a separate compatibility ELF that adjusts
section names and Thumb symbol parity without changing native linked payloads.
The native ELF remains available for relocation and instruction-mode validation.
Source coverage is zero. ARM7 and the embedded `ChildRom/JSS2Child.srl` programs
are inventoried but unbuilt. Proprietary container executable scope remains open.

Execution evidence is committed in the owned
[Track A branch](https://github.com/JUS-Reverse-Engineering/JUSDecomp/tree/track-a/matching/decomp/matching-notes/baseline-t01).
Tracker item `jus-bjry.12` records the native experiment. This verified replacement satisfies
the amended T01 baseline gate; T02 keeps all strict rejection and relocation tests.
The original tool preference below remains historical planning context.

### Compiler recovery and first source milestone

During execution, the official decomp.me compiler index supplied a public Metrowerks
archive. Its pinned linker also reproduced all 17 modules. The original absence of a
local linker no longer blocks this work. The native linker remains the strict pipeline
backend; the recovered original linker provides an independent baseline comparison.

T03 then compiled and linked one ordinary C function through Metrowerks and Wibo on
macOS. The accepted function owns 24 bytes, including a four-byte literal pool. All
17 modules and 87,493 relocation slots pass. A changed call target fails before link
and receives zero source credit. ARM7, embedded programs, and container scope remain
unbuilt or unresolved, so full-project source coverage remains unknown. The committed
[source evidence](https://github.com/JUS-Reverse-Engineering/JUSDecomp/tree/track-a/matching/decomp/matching-notes/source-t03)
includes the positive run, negative run, and independent review.

T04 and T08 also passed at producer `9495e76`. Source and reference pipelines now
require the complete ROM gate and reproduce the original 67,108,864-byte ROM
exactly. The accepted source remains 24 bytes. Three reviewed aliases preserve
module identity and tracker item provenance. A 288-trial compiler sweep on four larger
functions found no exact matches, so those compiler choices remain unresolved.
The [ROM evidence](https://github.com/JUS-Reverse-Engineering/JUSDecomp/tree/track-a/matching/decomp/matching-notes/rom-t08)
records 124 passing tests and independent review with no flags. Runtime captures
remain queued for T07. T05 donor matching, T10 CPU-specific reconstruction, and
follow-up `jus-bjry.13` for compiler header dependency capture are in progress;
live tracker items carry their current findings.

## Define completion before counting progress

The first milestone is a reproduced ARM9 module baseline. The final target includes
ARM9 main, ITCM, DTCM, every ARM9 overlay, ARM7 and any ARM7 overlays present in the
selected ROM. Enumerate Download Play or other embedded executables during intake;
include executable payloads in the final source denominator if present. Preserve
NitroFS and other non-code content byte-for-byte. Editable art and audio exporters are
outside this matching-source project.

Track three independent results:

- Source coverage: bytes and functions compiled from reviewed C/C++, per module and
  separately for game code and SDK/runtime code. Assembly fallback, copied objects,
  incbin code, and generated instruction arrays contribute zero source coverage.
- Module integrity: linked loadable bytes, addresses, relocation targets, section
  placement, BSS extents, autoload records, and initialization ordering match.
- ROM integrity: reconstructed raw ROM bytes match the pinned original hash, including
  header, tables, filesystem order, compression, padding, and executable payloads.

Byte-perfect assembly reconstruction is a baseline, not source completion. Original
source names and file boundaries are usually unrecoverable. Reconstructed TU boundaries
are working hypotheses and can change while retaining identity/provenance records.
Document genuinely handwritten assembly separately. Do not call the result 100% C/C++
if such exceptions remain.

## Evidence and corrections

Inspection date: 2026-10-04. Luna agents shallow-cloned the reference repositories.
No original-ROM rebuild or proprietary compiler run was performed for this plan.
Upstream build results below are reported results until T01 reproduces them.

| Evidence | Consequence for this plan |
|---|---|
| [JUSDecomp TODO at 6a061e3](https://github.com/piuzera/JUSDecomp/blob/6a061e3897f10a8800bf7ec9afde82fa8c9dbe1b/decomp/docs/TODO.md) reports ARM9 main and all 14 overlays passing `dsd check modules`. Track A was deprioritized. | Branch existing infrastructure; reproduce it before upgrading tools. This is not yet a full-ROM result. |
| [Compiler notes](https://github.com/piuzera/JUSDecomp/blob/6a061e3897f10a8800bf7ec9afde82fa8c9dbe1b/decomp/docs/FUNCTIONS.md) record a single 24-byte function matching multiple `2.0/*` and `dsi/*` compilers. | Start sweeps there; keep multiple candidates until discriminating functions narrow them. Do not infer one compiler for every TU. |
| [Build orchestration](https://github.com/piuzera/JUSDecomp/blob/6a061e3897f10a8800bf7ec9afde82fa8c9dbe1b/tools/scripts/build.py) delinks, generates linker/objdiff inputs, and optionally links/checks. Missing linker can be skipped with a successful exit. | Add a strict verification command and prove source objects actually replace reference objects. |
| [ARM9 config](https://github.com/piuzera/JUSDecomp/blob/6a061e3897f10a8800bf7ec9afde82fa8c9dbe1b/decomp/arm9/config.yaml) includes autoload regions and overlays. No ARM7 reconstruction tree was found. | Inventory all ROM executables explicitly. Check stub overlays even where there is no committed gap-assembly file. |
| Local tracker item `jus-jusdecomp-crosscheck-x1cf` resolves the upstream module-label conflict. | Use [our overlay map](../research/Overlay-Map.md) and its evidence. ARM9/ov6 battle work precedes treating ov11 as an AI subsystem; upstream strings alone do not establish ownership. |

Reference snapshots used for workflow design:

| Repository and pinned source | Specific lesson |
|---|---|
| [ds-decomp c408063](https://github.com/AetiasHax/ds-decomp/tree/c4080635ac38aaf9608ca23751defa9fa19cf81a) | Current tooling reference; not an automatic replacement for JUS's original pin. |
| [SM64DS linkcheck b3de552](https://github.com/tangosdev/sm64ds-decomp/blob/b3de552bb01d2e573c07fb74de44a6be5e2a993b/tools/linkcheck.py) | Resolve relocation sections with ELF `sh_info`, apply addends, and expose unresolved slots. Its game-specific symbol and veneer rules need adaptation. |
| [MKDS linkcheck c6e18fa](https://github.com/ai-tdd-labs/mkds-decomp/blob/c6e18fa4b346643b74c402b605a84b43cba16c01/tools/linkcheck.py) | Check destination instruction mode as well as address. Audit file licensing; the tooling license does not grant the same terms to all game source. |
| [PictoChat cross matcher 897c5f1](https://github.com/tangOS-decomps/pictochat-decomp/blob/897c5f150ce39faa9abb5759d7ac34491a5a5cc2/tools/cross_match.py) | Donor cache and address-base assumptions are project-specific. Replace them with JUS module identities. |
| [KHDays ea39ead](https://github.com/Yokimitsuro/khdays-decomp/tree/ea39ead5e3c4f284bb243b9082e948847038bcd4) | Separate C, assembly, data, and SDK accounting; preserve real per-file compiler overrides. Its ARM9 completion claim does not settle ARM7 scope. |
| [DQIX 94cc9c8](https://github.com/DQIX/dqix-decomp/tree/94cc9c872266f0a6d15d3fb037fba24b8d3696d6) | Separate module verification from the ROM hash gate. Its final ROM workflow needs an ARM7 BIOS input; inventory any equivalent JUS requirement. |
| [Spirit Caller 5a66003](https://github.com/cntrl-alt-lenny/gx-spirit-caller/blob/5a660035d6faef87902b9f51793b1aff91fa64f9/BUILD.md) | Keep per-TU compiler selection and exact assembly fallback while reporting real source progress separately. |

The older Tier-2 plan provides research leads, not build instructions for this project.
Do not reuse its stale environment assumptions or promote Ghidra output to matching source.

## Solution approach

Pin upstream JUSDecomp `6a061e3897f10a8800bf7ec9afde82fa8c9dbe1b` and first reproduce its
reported dsd 0.12.0 workflow. Record exact binaries, hashes, host architecture, compiler
runner, compiler and linker versions independently. The upstream scripts assume Windows
executables. Default the reproducible worker to Linux x86_64 with a tested Windows-tool
runner; accept native Windows as a fallback. Do not assume `wibo` works on the local Mac.
A missing ROM or proprietary tool is a concrete input blocker, never a passing build.

Treat a dsd upgrade as an isolated experiment after the baseline passes. Adopt it only
when reference objects, generated metadata, linked modules, and ROM hashes remain
accounted for. Keep the old pin if the upgrade cannot demonstrate equivalence.

Use `(ROM hash, CPU, module ID, section, address, instruction mode)` as the identity of
an original symbol. Names are aliases. Overlays can share addresses; no tool may merge
functions solely by address. Let dsd own link-facing symbols, relocations, delinks, and
ordering. Import local research as provenance-linked aliases and type hypotheses, then
review each promotion to dsd metadata.

Start with the existing trampoline, then a bounded pilot of at most 20 functions across
one SDK/runtime family and one small C++ class. The pilot must contain a real call or
reference relocation, a constructor, a destructor or ownership routine, and a vtable
reference if the chosen class has one. Prefer candidates with known boundaries, few
external dependencies, and local evidence. Do not begin with a large combat update loop.

Use objdiff for iteration, followed by relocation-aware linked validation and all-module
checks. Keep unresolved functions as exact assembly or reference objects. A candidate
must prove that its source-built object was selected into the final link. Each promotion
carries the compiler hash, flags, include context, source hash, target identity, diff
report, link report, and module-check result.

Run signatures and donor discovery before manually reconstructing each batch. Do not
make a complete donor corpus a prerequisite for all progress: start with two useful
SDK/runtime families, measure accepted matches, and expand only where it saves work.

## Tool choices

| Tool or reference | Planned use and boundary |
|---|---|
| dsd | Keep authoritative module/link metadata; use signatures as identification leads. Pin first, upgrade after equivalence checks. |
| objdiff | Default local matching loop; a percentage alone is not acceptance. |
| SM64DS and MKDS | Study relocation validation, per-symbol compiler selection, near-miss records, and family matching. Adapt contracts and test fixtures before importing code. |
| PictoChat | Model the donor-search workflow. Structural similarity and identical tiny stubs produce candidates, not automatic names or accepted source. |
| KHDays, DQIX, Spirit Caller | Study TU/module organization, C++ context, build integration, and ROM checks. Their own completeness labels are not proof of JUS readiness. |
| NTRGhidra | Optional static analysis with separate overlay address spaces. Pin and test the loader/Ghidra pair during setup; no dependency on an unverified version claim. |
| melonDS + GDB | Runtime oracle for object layout and semantics. Use the existing repository's emulator lease and capture workflow. |
| dsv | Optional type viewer. First validate one reconstructed object against raw GDB reads; retain GDB if the viewer or type pipeline is incompatible. |
| decomp.me | Escalation for a bounded difficult function after preserving a local reproducer. Do not make hosted availability part of the build. |
| ndspy, NitroPacker | ROM layout automation and independent cross-checks. Extraction agreement does not prove exact repacking. |
| JUSToolkit and asset viewers | Format research when needed. Preserve raw asset bytes for ROM reproduction; do not put sprite/audio conversion on the source-matching critical path. |
| Capstone, pyelftools, GNU ARM tools, Ninja | Use where required by the adopted scripts. Pin versions and keep one canonical build command. |

Audit each donor file's license at its pinned commit before copying it. Missing or
incompatible permission means implement the idea independently or exclude that donor.
Keep compiler binaries, original ROMs, and extracted game content out of published
source artifacts. A public checkout must explain how private inputs are supplied.

## Relevant files

Existing JUSDecomp integration points are `tools/scripts/build.py`,
`decomp/arm9/config.yaml`, the sibling symbols/relocs/delinks files,
`decomp/src/ov000/test_trampoline.c`, and the upstream compiler notes linked above.
Preserve their generated-output contracts while extending the pipeline.

Proposed files in the Track A branch are `decomp/toolchain.lock.json`,
`decomp/rom-manifest.json`, `decomp/source-manifest.json`, `decomp/donors.json`,
`decomp/matching-notes/`, `tools/scripts/verify.py`, and `tests/matching/`.
These are future deliverables, not files already available in this checkout.
The source manifest references dsd identities rather than maintaining a competing
symbol-address database. Machine-generated progress is derived from the manifest
and actual link inputs.

Local evidence entry points are [the overlay map](../research/Overlay-Map.md),
[the character-state reference](../research/Character-State-Struct.md),
[the battle-engine map](../research/Battle-Engine-Map.md), and
[the emulator playbook](../harness/RE-Session-Playbook.md). Their cited tracker items decide
claim status. Resolve conflicting names without overwriting stronger local evidence.

## Task sequence

Execution epic: `jus-bjry`. Dependencies below are hard finish-to-start gates.
Owners describe execution roles, not permission to share a writable checkout.
Each agent that writes uses an isolated worktree; one integrator updates dsd metadata.

### T01: Reproduce the pinned baseline

Owner: build agent. Dependencies: none. Ticket: `jus-bjry.1`.

Create the dedicated branch from the pinned upstream commit. Inventory the available
private ROM and tools without modifying them. Record the ROM revision/hash and all
executable regions in the manifest; reject a different revision. Pin the original tool
versions and record the host/runner recipe. Run extraction, delink, linker generation,
link, and module checking in a fresh output directory. Acceptance: reproducible logs
for main, autoload regions, all 14 overlays including stubs, and an explicit inventory
of currently unbuilt ARM7/embedded code. Missing inputs leave this task blocked with
an exact input list. Do not substitute documentation for a build result.

### T02: Make verification fail on missing or stale evidence

Owner: verification agent. Dependencies: T01. Ticket: `jus-bjry.2`.

First add failing regression fixtures for skipped linker, missing module, stale output,
wrong ROM, wrong relocation target, and overlapping overlay addresses. Implement one
strict command that builds and verifies the declared target set and writes a structured
report. Adapt linked-relocation validation with symbol/addend/mode handling and explicit
unresolved status. Match relocation sections through ELF `sh_info`, preserve RELA
addends, and test ARM/Thumb transitions. Do not accept a different destination merely
because it contains identical code. Linker veneers must match the final layout. Acceptance: each negative fixture fails, the original baseline
passes, and no skipped or unresolved check is reported as success. Fresh output and
input hashes prevent old objects from satisfying a new build.

### T03: Link real source and establish honest progress

Owner: build agent. Dependencies: T02. Ticket: `jus-bjry.3`.

First add a test that changes the trampoline's return value or call destination and
confirm that compilation changes its object bytes, while reference bytes remain
unchanged: verification must fail. Compile the existing source with an explicitly
selected compiler and replace its reference object at the correct link position.
Generalize selection to whole TUs without duplicate symbols. Acceptance: restored source
matches, link-map provenance identifies its source-built object, altered source fails,
and coverage changes only for source actually linked. Report functions, code bytes,
rodata/data, unknown regions, and fallback separately without double counting aliases.

### T04: Reconcile symbols and establish compiler experiments

Owner: analysis agent. Dependencies: T03. Ticket: `jus-bjry.4`.

Test identity import with two overlays sharing an address and contradictory aliases.
Import reviewed local names/types with tracker item provenance; retain uncertain names as aliases.
Keep per-TU compiler, flags, ABI settings, and include context in the manifest, with
explicit per-symbol experimental overrides. Sweep the existing compiler family on
representative nontrivial functions and record unresolved equivalence sets. Acceptance:
no address-only merges, no compiler chosen solely from the tiny trampoline, and each
experiment reproducible from saved source/context/target inputs. Linker remains separately
pinned. Test any dsd upgrade here against T02/T03, or retain the baseline pin.

### T05: Build a small donor matcher with rejection tests

Owner: tooling agent. Dependencies: T04. Ticket: `jus-bjry.5`.

First test tiny-stub collisions, altered relocation targets, ARM/Thumb differences,
literal pools, and data mistaken for instructions. Pin two donor families and their
licenses, source paths, compiler contexts, and hashes. Run dsd signatures and a staged
raw-byte/relocation-normalized/structural search. Acceptance: report candidates with
confidence and provenance; ambiguous candidates stay unresolved. Recompile any imported
source with JUS context and pass T02/T03 before counting it. Record accepted matches
and analyst time so corpus expansion has an observed benefit.

### T06: Complete the SDK and C++ matching pilot

Owner: matching agent. Dependencies: T05. Ticket: `jus-bjry.6`.

Select the bounded pilot by the rules above and publish its target list before writing
source. Add ABI/layout checks for reconstructed types before replacing functions.
Recover constructor initialization, vtable slots, ownership/destruction, and static
initialization where present. Use bounded compiler experiments and a near-miss record.

When source work depends on an unresolved caller invariant, object lifetime, or virtual
dispatch, request a targeted original-ROM diagnostic capture during the pilot. Track
each capture as a separate emulator-gated child of `jus-bjry.6`. These child issues
require the pinned original ROM from T01 and published pilot targets. They do not
depend on completion of T06 or T08. Acquire the single emulator lease before capture
and release it afterward.

State the hypothesis and capture scenario before running the emulator. Record ROM and
loaded-overlay identity, call arguments, incoming saved registers, lookup results,
relevant fields, and virtual targets. For the configuration method, investigate the
caller conditions around failed lookups and the saved-register dependencies. Record
observed paths and remaining assumptions separately. Failure to observe a path does
not prove a universal caller invariant. Write findings to the capture issue and T06
before source work relies on them. Diagnostic captures add no source credit.

Acceptance: every promoted function passes object, linked-target, and module checks;
uncertain members remain exact fallback and are excluded from progress. Finish one
complete small class/family and document the measured effort per accepted function
before opening broad subsystem work.

### T07: Validate reconstructed objects at runtime

Owner: runtime agent. Dependencies: T06, T08. Ticket: `jus-bjry.7`.

Run the final original-versus-rebuilt comparison after pilot completion and the exact
ROM rebuild gate. Early diagnostic captures run through the T06 child issues above;
they do not satisfy this final validation gate.

Acquire the single emulator lease. Reuse early original-ROM traces when their pinned
ROM, scenario, and capture conditions match the final comparison. Otherwise, capture
fresh original-ROM traces. Compare them with rebuilt-ROM traces from T08.
Record loaded overlay identity,
object addresses, field widths/offsets, lifetimes, call arguments, and vtable targets.
Test dsv on one object against independent raw GDB reads before using it broadly.
Acceptance: original and rebuilt captures both exist, the agreed object traces match,
and boot plus scene-transition smoke cases pass on the rebuilt ROM. Captures support
the promoted type claims and list untouched fields as unknown; a viewer failure does not block direct GDB validation. Release the lease and
write findings to tracker items immediately. This task is emulator-gated.

### T08: Establish a complete-ROM round trip

Owner: ROM tooling agent. Dependencies: T03. Ticket: `jus-bjry.8`.

First test intentional changes to header, overlay table, filesystem ordering, compression,
and one executable byte. Repack using rebuilt ARM9 modules while preserving original
ARM7 and raw asset payloads initially. Acceptance: a clean build produces the exact raw
ROM hash, every mutation fails the corresponding check, and boot/scene smoke checks are
queued for T07. If a packer normalizes padding or compression, preserve the original
layout/encoding metadata or change the packer; do not redefine a mismatch as success.
Record preserved binaries as zero source coverage. This gate must pass before T09.

### T09: Expand matching by subsystem

Owner: matching lead with isolated workers. Dependencies: T06, T07, T08. Ticket: `jus-bjry.9`.

Generate finite work batches from the remaining inventory, each with one TU/class family,
one owner, dependencies, tests, and an acceptance record. Prioritize shared SDK/runtime
and shared classes, then evidence-backed ARM9/ov6 combat functions and ov11 AI; cover
menus, deck systems, networking, sound, and other overlays for the full target. Do not
exclude subsystems because Track C's POC excluded them. Acceptance: each batch preserves
all gates and updates per-module source coverage. Record intermediate residual work in
child tickets; T09 remains open until all ARM9 executable regions have matching reviewed
source and all such residuals are closed.
Measure throughput from the pilot and revise forecasts; do not promise a completion
date before observing sustained matching rates.

### T10: Reconstruct ARM7 and other executable payloads

Owner: CPU/toolchain agent. Dependencies: T04, T08. Ticket: `jus-bjry.10`.

First test that a change in ARM7 or an embedded executable breaks verification and that
ARM9 compiler defaults cannot silently apply to ARM7. Establish CPU-specific extraction,
compiler/ISA settings, SDK signatures, link metadata, and source coverage using the same
contracts. Preserve exact fallback while replacing code. Acceptance: every non-ARM9 executable
identified by T01 is fully source-built; all module checks and the whole-ROM hash pass.
During partial progress, list precise residual symbols and leave T10 open. Asset files that contain executable code
must not escape the denominator by being classified as opaque NitroFS data.

### T11: Audit completion and reproduce from a clean checkout

Owner: independent verification agent. Dependencies: T09, T10. Ticket: `jus-bjry.11`.

Test the completion checker against hidden original objects, inline assembly substitutes,
incbin executable regions, excluded overlays, and unaccounted code. Rebuild from a fresh
checkout with only declared private inputs. Acceptance: every executable region is
built from reviewed C/C++ with link provenance; no executable fallback or residual
source tasks remain; exact module/ROM checks pass; provenance/licenses
and reproducible commands are published. Run final runtime smoke cases through a
serialized emulator session, including overlay transitions, save/load, and available
local communication paths. Record unavailable external services as runtime-test limits,
not as reasons to exclude their executable code. If original handwritten assembly
cannot be expressed as matching C/C++, publish the exact exception inventory and a
partial-source result. Keep this full-C/C++ completion gate open; do not quietly change
the denominator or declare completion from an audited assembly rebuild.

## Test requirements

Write the failing contract tests before changing each build/tooling seam. Prefer small
synthetic ELF/ROM fixtures for rejection paths; reserve private-ROM integration tests
for a controlled worker with the declared inputs. Public CI can run fixture checks
without ROMs or proprietary tools. A release or matching promotion also requires the
private integration report for its exact source commit and input/tool hashes.

For every promoted source change, run compile/objdiff, relocation validation, link-input
provenance, and all declared module checks. After T08, require the full-ROM comparison
on every integrated change as well. Run runtime checks for new semantic/layout claims,
not for every syntactic near-miss edit. Emulator captures corroborate meaning; they do
not replace byte comparisons. Compile-time sizeof/offset checks protect the recovered
ABI even when the host uses a different pointer size or alignment.

A relocation checker must reject or explicitly report unsupported relocation kinds,
unresolved symbols, wrong addends, wrong sections, instruction-state changes, and wrong
overlay destinations. A matching percentage cannot override those results.

## Edge cases and risks

- Tool upgrades can change extraction, relocation discovery, or generated ordering.
  Decision: preserve the initial pin until an isolated comparison passes all gates.
- Donor functions can share bytes without sharing meaning, especially tiny wrappers.
  Decision: treat donor similarity as a lead; require source rebuild and link validation.
- TU boundaries and compiler families remain hypotheses.
  Decision: retain evidence and equivalent candidates; broaden sweeps only after a
  documented failure with the current candidates and tested flags.
- C++ reconstruction includes static initialization, ABI padding, thunks, exception
  support where present, and lifetime semantics. Decision: leave uncertainty as fallback,
  never invent a clean-looking class layout merely to raise source coverage.
- Shared writable metadata causes integration conflicts.
  Decision: isolate workers and serialize dsd metadata integration and emulator use.
- Private tools or ROMs may be absent. Decision: T01 reports exact blockers and downstream
  work remains dependent. No source-progress claim is made from an unavailable build.
- The full source target is larger than the existing battle research.
  Decision: maintain its own backlog without assigning other phase labels or diverting
  ongoing research work.

## Review dispositions

A Luna reviewer inspected the draft and local overlay evidence. Dispositions:

| Finding | Severity | Resolution |
|---|---|---|
| Residual-symbol lists could satisfy final completion without full source. | Important | T09/T10 stay open while residual code exists; T11 requires reviewed source for every executable region. Assembly exceptions produce a partial result, not a closed full-source objective. |
| Runtime comparison could finish before rebuilt ROM availability. | Important | Final T07 validation depends on both T06 and T08 and requires original/rebuilt traces plus smoke cases. Targeted original-ROM diagnostics run as emulator-gated T06 children once T01 and pilot target publication are complete. T09 still waits for T07. |
| A source mutation may optimize to unchanged machine code. | Minor | T03 requires a changed return value or call destination and checks that candidate object bytes changed. |
| Durable remote destination was unspecified. | Minor | T01 resolves an authenticated-account fork, verifies its parent, and records origin/upstream URLs. |

No unresolved design decisions remain. ROM/tool availability, compiler identification,
and remaining source boundaries are explicit investigation outputs with failure gates.

## Ticket index

Read live status from tracker items rather than treating this table as a second status database.


| Task | Owner role | Ticket | Depends on |
|---|---|---|---|
| T01 | build agent | `jus-bjry.1` | none |
| T02 | verification agent | `jus-bjry.2` | T01 |
| T03 | build agent | `jus-bjry.3` | T02 |
| T04 | analysis agent | `jus-bjry.4` | T03 |
| T05 | tooling agent | `jus-bjry.5` | T04 |
| T06 | matching agent | `jus-bjry.6` | T05 |
| T06 diagnostic captures | runtime agent | emulator-gated children of `jus-bjry.6` | T01, published pilot targets, and the single emulator lease; no T06 or T08 completion dependency |
| T07 | runtime agent | `jus-bjry.7` | T06, T08 |
| T08 | ROM tooling agent | `jus-bjry.8` | T03 |
| T09 | matching lead with isolated workers | `jus-bjry.9` | T06, T07, T08 |
| T10 | CPU/toolchain agent | `jus-bjry.10` | T04, T08 |
| T11 | independent verification agent | `jus-bjry.11` | T09, T10 |

Start execution with tracker item `jus-bjry.1`, then claim that task with
marking `jus-bjry.1` in progress. Follow T01 in the dedicated
JUSDecomp branch. Claiming a task does not waive its input or verification gates.

## Dependency and CPU follow-up, 2026-10-05

T13 is closed. Reviewed producer `a2ffe1d` passed all 19 source verification
stages, the exact whole-ROM comparison, and 159 tests without skips.
The dependency gate captures actual consumed headers before and during compilation.
Evidence is pushed in JUSDecomp branch `track-a/matching` through `b5a29d4`.
Source coverage remains 24 bytes. T10 has fresh ARM7 and child extraction evidence,
but every other CPU program instance remains unbuilt from source. A strict child
analysis defect in BIOS wrapper discovery has a concrete repair in progress.
T05 remains in progress; preliminary donor search has zero high-confidence matches.

## Donor and child baseline follow-up, 2026-10-05

T05 is closed with zero donor source matches. Reviewed producer `dd8a4fd`
passes 174 tests without skips and the exact 19-stage parent source ROM.
The licensed corpus retains 868 tiny ambiguous leads. Public evidence is
pushed through `f6fb6a7`. T10 has a tested dsd startup-wrapper repair and
a three-module child ARM9 binary baseline with 35,092 validated relocations.
It remains open for compression, ARM7 and residual source work.
T06 is now in progress; its candidate class has four vtable overrides,
including the previously omitted callback installer. Its target list and
ABI prerequisites must be published before implementation.

## Partial source and child round-trip follow-up, 2026-10-05

Reviewed producer `47aa4b8` passes all 19 verification stages, all 17 module
images, 87,493 relocation checks and the exact original whole-ROM comparison.
All 204 tests pass without skips. Three registered source functions total
76 bytes: 44 game and 32 SDK. The runtime lookup and destructor ABI bridge
join the existing overlay trampoline. Six published class targets remain
exact fallback; T06 remains open. The bridge does not establish a complete
native virtual class or recover base ownership. Evidence and independent
review are [pushed through `4416ce3`](https://github.com/JUS-Reverse-Engineering/JUSDecomp/tree/4416ce3).

The split source objects exposed a cross-object ARM/Thumb normalization bug.
Selected-input global/weak target resolution now preserves the correct
execution mode without changing payload bytes. Nineteen focused native-link
regressions and the full source pipeline pass; `jus-bjry.15` is closed.

T10 now has an independently reproduced exact whole-child-ROM round trip
using the unchanged locked codec and the original layout. It earns zero
source credit. ARM7 startup establishes two distinct autoload RAM regions
and an ARM entry seed, plus two external RAM-copy dependencies whose
contents and executable status are unresolved. CPU-specific analysis and
source reconstruction remain open, as does recursive executable discovery
in proprietary containers. The global source percentage remains unknown.

The next reviewed source milestone is producer `c7c61f2`, pushed through
`cb0c6ad`: four functions total 104 bytes (72 game, 32 SDK), with 92
instruction bytes and 12 literal bytes. The deleting-destructor entry adds
28 bytes and preserves both original calls and the observed pointer-return
interface without asserting ownership. All 19 verification stages and 206
tests pass without skips; five published class targets remain fallback.
T06 stays open. Complete original-code review also corrects the large
virtual method's role: it configures a looked-up object, rather than
installing a callback table. Its failing lookup path has an unresolved
register-initialization invariant; candidate source cannot invent a safe
early return.

The factory milestone, producer `4457e49`, is reviewed and pushed through
`3cddb66`: five source functions total 160 bytes (128 game, 32 SDK). All 19
stages and 208 tests pass without skips; four pilot class targets remain.
The constructor candidate separately passes its 224-byte full-ROM proof
and awaits independent review. An initializer sweep preserves its near
misses but accepts no source.

The checked ARM7 library view passes both real programs and public fixture
tests, with no analysis, linked baseline, source credit, or production-pin
change. Independent adversarial fixtures exposed reserved FAT IDs causing
a parser panic and decoded filename ambiguity bypassing exact selection.
Those defects are recorded in T10 and must pass new rejection regressions
before candidate integration.

## Progress checkpoint: reviewed clone and checked ARM7 views

The reviewed source milestone is pushed through `d7b5538` in JUSDecomp.
Producer `4d84b69` is preserved in its ancestry, and all 72 current source
hashes match. Seven functions total 304 bytes: 272 game and 32 SDK, comprising
260 instruction bytes and 44 literal bytes. All 19 verifier stages, 87,493
original relocation slots, the exact whole-ROM comparison and 216 tests pass
without skips. Only initializer and virtual configuration method remain
fallback in the published pilot; ownership and runtime verification remain
open, so T06 is incomplete. The second bounded initializer attempt records
60 strict trials with zero exact matches and earns no source credit.

ARM7 checked physical views are independently rebuilt and reviewed, pushed
through `5a23d3d`. All 29 Rust tests and clippy pass. The reserved-overlay panic
and decoded-name ambiguity are fixed and their preserved reproducers reject
cleanly. Parent and embedded child identities, autoload extents and hashes are
verified against unchanged originals. ARM7 analyzer integration, ISA policy,
symbol/relocation recovery and linking remain open; physical views earn zero
source credit and cannot close T10. Production tool pins remain unchanged.

## Progress checkpoint: ARM7 span adapter and initializer diagnostics

Reviewed matching-source evidence is pushed through `dbdc396` in JUSDecomp.
Coverage stays at seven functions and 304 bytes; the complete 19-stage proof,
87,493 original relocation slots and byte-identical ROM remain the accepted
source milestone. The latest combined suite passes 229 tests without skips.
Initializer member bridging and external native placement construction earn
zero source credit. The latter restores argument/pool order but adds a null
check and emits 604 bytes against 596. The virtual configuration method's
entry-state blocker and the remaining ownership/runtime evidence keep T06 open.

The checked ARM7 module adapter is independently reviewed and published. It
preserves full program/CPU/region identity, initialized bytes separately from
BSS, and fixed V4T complete-span decoding. All 41 Rust tests and clippy pass.
Parent/child metadata is unchanged, and an isolated experimental tool pin
passes the full 19-stage ARM9/whole-ROM compatibility proof. Production tool
pins remain unchanged. This is physical/ISA tooling, not ARM7 function,
relocation, linked-baseline or source credit. Two isolated design candidates
now compare a shared Function policy migration with a separate bounded ARM7
control-flow observer; implementation and review of that seam are pending.

## Progress checkpoint: bounded ARM7 observer

The selected bounded observer is implemented, independently reviewed and
pushed through `146ce2b` in JUSDecomp. Experimental tool producer `67e9a8b`
passes 55 Rust tests and clippy. Actual parent and child probes preserve
distinct identities across four explicit spans, eight instructions and ten
transfer observations. Fresh initialization metadata matches all 51 parent
and nine child files. Experimental compatibility producer `73eee8d` passes
all 19 stages, 17 ARM9 modules and BSS, 87,493 relocation slots and the exact
67,108,864-byte ROM. Production tool pins remain unchanged.

Source coverage remains seven functions and 304 bytes; the combined Python
suite still passes 229 tests without skips. The observer establishes neither
ARM7 function extents nor executable classification, original relocations,
a linked baseline or source coverage. T06 and T10 remain open.

The observer tests exposed signed branch-displacement defects in locked
`unarm 1.9.2`. Follow-up `jus-bjry.16` is in progress in isolated tool and
dependency checkouts. Direct parser regressions confirm ARM B/BL, ARM BLX,
combined Thumb BL and combined Thumb BLX boundary defects; short Thumb
branches already decode correctly. Shared dependency repair requires a
reviewed fresh compatibility proof before changing production pins. A
separate native ARM7 physical-baseline design is underway and has no build
or verification claim yet.

## Progress checkpoint: shared decoder repair accepted

Shared decoder follow-up `jus-bjry.16` is complete. Source producer `d38bad6`
fixes signed ARM B/BL/BLX and combined Thumb BL/BLX displacement arithmetic,
plus immediate Thumb BLX source-address alignment. Public exact-source patches,
MIT notice and pinned local dependency preparation are pushed through
`691e578` in JUSDecomp. Independent gpt-6.1-sol review of `a86f78b` reports
No flags after resolving an executed ignored-Cargo-build-script counterexample.

Root reproduces 532 upstream tests, 63 DSD tests, ten preparation tests and 32
independent native LLVM cases. Its release binary exactly matches the worker.
Fresh parent/child initialization matches all 51/nine metadata files. Isolated
producer `17e244a` passes all 19 stages, 17 ARM9 modules/BSS, all 87,493
relocation slots and the exact 67,108,864-byte ROM. Of 72 source-input hashes,
71 match the prior observer proof; the sole intended change is the isolated
experimental tool lock. Canonical production pins and seven source functions
totaling 304 bytes remain unchanged. T06 and T10 remain open.

The ARM7 native physical baseline is now in isolated test-first implementation.
Parent and independent gpt-6-sol comparison selected actual VMA/LMA/BSS ELF
placement over a flat stored-image container. A first invented 120-byte fixture
passes actual pinned clang/lld linking and ELF-only reconstruction with six
segments. Additional malformed-ELF/input/provenance tests, original parent/child
proof and root review remain pending. This fixture grants no original ARM7
linked-baseline, function, relocation, executable-classification or source credit.

## Progress checkpoint: native ARM7 physical producer accepted

JUSDecomp `7cf119c` publishes the reviewed opaque physical producer at tool
source `7b3513f`, tree `42448bc6`. Root applies the exact durable patch,
passes all 80 Rust tests and strict clippy, and reproduces the worker's release
hashes. Fresh parent and exact child builds each reconstruct 165,552 stored
bytes solely from the actual ELF. Each proves six load segments and 21,424
separate BSS bytes. Independent gpt-6.1-sol review of `a3e3dd6` reports No flags
for the source, proof bundle and trail. The approved capsule pins 16 durable
source artifacts, native tools, layout and producer binary.

Fresh strict initialization retains all 51 parent and nine child metadata
files byte-for-byte. Isolated producer `741b44d` passes every stage of the
19-stage ARM9/source/ROM compatibility pipeline, all 17 ARM9 modules and
87,493 relocation slots, with an exact 67,108,864-byte ROM and 304 source
bytes. Of 72 source hashes, 71 remain unchanged; the sole intentional delta
is the experimental lock. Canonical production pins remain unchanged.

The 19-stage pipeline preserves ARM7 from the original template. Canonical
consumption is separate work in progress. Its optional paired-build stage
must retain a live immutable producer result; detached audit JSON cannot
establish a fresh native build. The original functions, executability and
relocations remain unknown, ARM7 source credit is zero, and T10 stays open.

A separate read-only initializer audit executes exact artifact/count checks:
15 reference objects, five runtime call relocations, 71 constructor records
across 11 modules, and 121 completed contexts over ten hashed source files.
Static/global lifetime and ordinary-new allocation policy are unproved, so
no new compiler trial or source promotion follows. T06 remains open.

## Progress checkpoint: canonical paired ARM7 integration accepted

JUSDecomp `e2bd6ea` publishes the optional native paired ARM7 stage. Independent
gpt-6.1-sol review of `e38bf84` reports No flags after verifying the immutable
live-operation handoff, detached-JSON rejection and all 243 artifact hashes.
Root runs 248 Python tests with zero skips and the actual 20-stage pipeline.
Seventeen ARM9 and two ARM7 disjoint writes reproduce all 67,108,864 ROM bytes;
all 87,493 original ARM9 relocation slots pass. Production analyzer pins remain
unchanged. Seven matching-source functions still total 304 bytes.

The next bounded scope adds fresh strict child ARM9 initialization, native
linking, all 35,092 original child relocation slots and exact recompression.
Its compressed slice is disjoint from child ARM7. Two isolated architecture
candidates and a separate child analyzer/codec approval precede implementation.
ARM7 and child ARM9 source credit remain zero, original ARM7 functions and
relocations remain unresolved, T10 stays open, and emulator smoke is not run.

## Progress checkpoint: child tool roles accepted

The child-only architecture is selected after two isolated designs and an
independent gpt-6-sol comparison. It retains the ARM7 owner and adds one child
operation. All 20 physical write extents validate before any application.

JUSDecomp `27b8458` publishes the separate analyzer and codec approval capsule
from `f5bf585`. Independent gpt-6.1-sol review of `4e9f6b7` reports No flags.
A clean codec checkout uses exact upstream `9f6c1b1`, the unchanged example and
original Cargo.lock. Root and independent release builds match `5c04f266`.
Both audits compare all 113 local files and 116 locked registry packages with
6,352 actual files against verified crate archives. The invented codec fixture
passes. The accepted analyzer CLI remains `3f18db59`; canonical parent pin
`22258743` stays unchanged. Tool approval grants no canonical or source credit.

The first worker 21-stage trial reproduces the exact ROM and validates all
35,092 original child relocations. Canonical acceptance is pending. Root found
that later child snapshots could overwrite earlier shared-script expectations;
the writer proves conflicting unions fail atomically and is rerunning the final
source-pinned candidate. Matching source remains 304 bytes, T06 and T10 open.

## Progress checkpoint: canonical child ARM9 integration accepted

JUSDecomp `fe8ee314` publishes the accepted child native operation. Independent
gpt-6.1-sol review reports No flags for source `320ea2a` and proof/trail
`8b7cc6a`. Root runs all 257 tests with zero skips and reproduces the actual
21-stage source-plus-ARM7-plus-child build. All 302 artifacts, 80 initial
source hashes and 46 child input/tool pins are independently checked.

Twenty disjoint writes consume 17 parent ARM9 images, the 1,955,956-byte
compressed child ARM9 slice and two 165,552-byte ARM7 images. All 87,493 parent
and 35,092 child original ARM9 relocation slots pass. The complete 2,141,384-byte
child and 67,108,864-byte parent match their original inputs. The real standalone
packer rejects detached child report JSON without creating a ROM; 21 separate
late-mutation checks reject changes and the restored operation passes. A fresh
default 19-stage build also matches the original ROM.

The snapshot-union defect and missing initial child source inputs are fixed
with failing-then-passing public regressions. Existing ARM7 approvals and
canonical parent DSD pins remain unchanged. Matching source remains seven
parent functions totaling 304 bytes; child ARM9 and ARM7 source credit are zero.
Global coverage is unknown, emulator smoke is not run, and T06/T10 stay open.

Next is read-only grounding for evidence-based ARM7 reachable-code observations,
using checked module inputs and real direct transfers. Function extents,
executability, indirect targets and startup RAM dependencies remain unresolved;
this scope does not promote source or generic ARM9 function assumptions.

## Accepted bounded ARM7 candidate graph

`jus-bjry.17` is complete, published in JUSDecomp `8f9e27e`. Frozen research
DSD source `71e766e` adds one pure native `connect` operation borrowing checked
observations. The Rust and Python design candidates remain reviewable; an
independent judge selected native ownership. Reports retain explicit root
assumptions, separate program identities, original guards and unresolved frontiers.
No decoding extends beyond caller selections.

Root and independent review pass 97 behavior tests, one authority compile-fail
doctest and one CLI unit, with zero ignored. All three release binaries match
worker, root and independent builds. Actual call and startup reports match
byte for byte; each call graph has five nodes and seven transfers. Startup
roots preserve the conditional loop and unknown BX. A complete dependency
source audit covers 157 local files, 349 registry packages/15,458 files,
three pinned Git dependencies and 47 prepared decoder files, unchanged across
builds. Fresh legacy checks reproduce 51 parent/nine child strict ARM9 metadata
records and both 165,552-byte ARM7 images from native ELF outputs.

The independent final publication review accepts all 69 original evidence pins
with no flags. Retained memory is `O(N + E + R*(N + E))`; the checked observer's
`E <= 3N` invariant gives the selected `O(N + E + R*N)` bound. The public package
preserves the finding and its source-grounded disposition. All 28 existing
approval/canonical snapshots remain unchanged.

Matching source remains seven parent functions totaling 304 bytes; ARM7 and
child source credit remain zero. Original function extents, executability,
relocations, indirect targets and external startup RAM dependencies are unresolved.
Global coverage is unknown and emulator smoke is not run. T06/T10 remain open.

The 24-byte ARM callee prefix at `037fd02c` is independently grounded and
published in JUSDecomp `026c3d9`. Original FNT/FAT, ARM7 headers and loader tables,
LLVM decode and fresh full producer output agree. Each program has 11 nodes,
14 edges, ten joins and four guarded frontiers. NE exits at `037fd0c0` or
`037fd044`; call-return continuations remain unselected. It grants no function
extent or execution/branch-feasibility claim.

The branch/literal scope is accepted in JUSDecomp `f932205` after independent
original, LLVM, fresh producer and public-artifact replay. Explicit selections
cover 32 bytes at `037fd044` and eight at `037fd0c0`; each graph has 21 nodes,
27 edges and seven guarded frontiers. Literal `037fd0cc` points to `03808430`
in autoload0 BSS, so runtime value and branch feasibility remain unknown.
The next instruction at `037fd0c8` stays outside selection.

`jus-bjry.18` evaluates one small plain-C leaf hypothesis at direct target
`037fcf18`. Five straight-line ARM instructions end in `BX LR`; a candidate
20-byte span stores `r1` at `027ffdc4 + (r0 << 2)`. Plain C with the established
ARM7 `-O4,p` recipe reproduces all 20 bytes in both programs; the baseline
recipe emits 36 mismatching bytes. Independent actual objects and ELF readback
agree. The public reproducer's missing private triage inputs are fixed with five
receipts and five request sidecars. Independent fresh compiler/ELF checks and
all five complete graph replays pass; final review has no flags. The accepted
package is published in JUSDecomp `6fb2bc5`, and `jus-bjry.18` is closed. Original symbol boundary, full ABI, return type,
external store-address contract and execution remain unproved. Source credit
stays zero and canonical integration is unchanged.

`jus-bjry.19` is accepted and closed, published in JUSDecomp `77a616c`.
Pinned LLD consumes the actual compiled MW ARM7 ELF `.text` at `037fcf18`,
between opaque autoload0 prefix/suffix, preserving separate BSS. Independent
fresh links reproduce the complete ELF hash and both original 165,552-byte
images, six load segments and 21,424 BSS bytes. The wrong 36-byte object fails
actual linker assertions; corrupt segment offsets are rejected. This validates
native object acceptance and placement for a relocation-free candidate,
without original relocation, function extent, ABI or source ownership credit.

`jus-bjry.20` is accepted and closed, published in JUSDecomp `84a2530`.
Shared table bases, sibling stores, enum IDs and initializer call order
corroborate an SDK arena interpretation. Independent original-ROM/graph replay
and a separate seven-source citation review pass with no flags. The public
note keeps the community reconstruction separate from original JUS authority;
another game's linked constants and SDK version cannot be imported into JUS.
Source credit remains zero.

`jus-bjry.21` is accepted and closed, published in JUSDecomp `27fd039`.
Independent original, donor, full-graph and public replay checks agree on
47 instructions and seven separately read literal words. The JUS value
`027f9c08` equals the checked autoload1 BSS end, instead of the Pokemon
reconstruction's `027fafcc`. Conditional exchanges and HI/LT/GE arithmetic
conditions remain explicit. Each graph has 81 nodes, 95 edges and fifteen
frontiers; no pool is decoded as instructions. Source credit stays zero.

`jus-bjry.22` is accepted and closed, published in JUSDecomp `0b95fe5`.
Independent original, LLVM and complete graph replay agree on the remaining
ID-7/8 caller pairs and epilogue. Each graph has 55 nodes, 70 edges and eleven
frontiers. A fresh checkout preserves all 86 accepted evidence hashes across
the arena, getter and caller-tail packages.

`jus-bjry.23` is complete, published in JUSDecomp `6ec389f`, with independently
accepted rejection evidence. Its 88-byte MW object has two real absolute
relocations, but the ID-8 case swaps two instructions relative to JUS. Native
linking is not attempted after that mismatch. Root and independent actual
replays and all four tests agree; the exact object-setup command is documented.
`jus-bjry.24` is accepted and closed, published in JUSDecomp `b7ec2f1`.
Root and independent actual compiles/replays and four tests agree that the
operand reversal produces the identical rejected object. This change has no
code-generation effect under the fixed recipe.

`jus-bjry.25` is accepted and closed, published in JUSDecomp `b2f7212`.
Changing only the WRAM declaration from an external byte object to an external
void function also produces the identical rejected object. Its undefined ELF
symbol remains `NOTYPE`. Root and independent replays and four tests agree;
the evidence gate verifies 22 worker pins and 27 acceptance pins against Git
and working files. The eight-byte instruction discrepancy remains.

`jus-bjry.27` is accepted and closed, published in JUSDecomp `de4ea1e`.
Six independently fetched primary files establish that the donor's ARM7 library
selects package `1.2/sp2p3` through a target override, uses `-O4,s`, and marks the
getter as ARM code. Local executable readbacks distinguish selected build 82
from the previous build 114. These establish donor settings; original JUS
settings remain unproved.

`jus-bjry.28` is accepted and closed, published in JUSDecomp `6a39bce`.
The unchanged original low-getter C matches all 80 instruction bytes with the
donor-selected compiler/optimization recipe. Actual native LLD resolves its two
real absolute relocations and reconstructs both complete ARM7 images exactly.
Root and independent fresh replay and seven tests pass; the gate verifies
29 worker and 36 acceptance artifact pins. Wrong symbol binding, earlier object
and malformed-segment controls reject. The coupled recipe comparison does not
identify its causal input or establish original JUS source ownership. ARM7
source credit remains zero.

`jus-bjry.29` is accepted and closed, published in JUSDecomp `574c01f`.
One frozen high-getter model matches all 108 original instructions and five
literal slots. Native LLD resolves its three real absolute relocations and
reconstructs both complete original ARM7 images exactly. Root and independent
fresh replay and five tests pass; the gate verifies 34 worker and 41 acceptance
pins. Public IRQ and independent WRAM wrong-binding controls change their
distinct expected bytes and reject, as do malformed-segment controls. Original
source identity and ARM7 source credit remain unchanged.

`jus-bjry.30` is accepted and closed, published in JUSDecomp `6813a22`.
The two-file replay owns its pinned checked layout and directly links both
unchanged getter objects. Five real absolute relocations use four checked
bindings, including the shared WRAM symbol. Both complete original ARM7 images
match. Root and independent fresh replay and four tests pass; the gate verifies
24 worker and 31 acceptance pins. Changing WRAM changes only stored offsets
20784 and 20908 in each image. Omitted low and high objects, swapped roles and
malformed loads reject. Existing capsules and source credit remain unchanged.

`jus-bjry.31` is accepted and closed, published in JUSDecomp `8b282d5`.
One frozen lower-store model matches the original 20-byte selection with the
established build 82 recipe, without a literal pool or relocations. Direct
native linking reconstructs both complete original ARM7 images. Root and
independent fresh replay and two tests pass; the gate verifies 19 worker and
26 acceptance pins. Omitted-object, wrong-placement and malformed-load controls
reject. The two native producers use different boundary symbol names; their
allocated sections and payloads agree, and both container hashes are recorded.
Original source ownership remains unproved and source credit is unchanged.

`jus-bjry.32` is accepted and closed, published in JUSDecomp `2a44091`.
Both stores and both getters coexist in one native link, with unchanged sources,
objects and accepted recipes. Both complete original ARM7 images match. Root and
independent fresh replay and four tests pass; the gate verifies 34 worker and
42 acceptance pins. All four omitted inputs reject. Reversing the equal-sized
stores links successfully, then rejects on actual function and map placement;
only stored instruction bytes 20672 and 20692 change. The separate shared-WRAM
negative changes 20784 and 20908. Malformed loads reject. Native container hashes
remain distinct where helper symbol names differ, with identical loaded
sections and images. Source credit and existing canonical approval stay fixed.

`jus-bjry.33` is accepted and closed, published in JUSDecomp `1bc9488`.
One frozen initializer model adds 160 ARM instruction bytes and a four-byte
relocated guard literal at `0x037fd02c`. Twelve actual PC24 call relocations
resolve through the four unchanged accepted store/getter objects. Both complete
original ARM7 images match, with six loads and 21424 bytes of separate BSS.
The two preceding table-load sequences remain an opaque 40-byte bridge.
Root and independent fresh replay and five tests pass; the committed gate
verifies 49 worker and 58 acceptance pins. All five omissions, wrong placement
and malformed loads reject. A guard binding moved by four bytes changes only
stored-image byte 21116. Swapping the equal-sized stores links successfully,
changes six actual initializer call targets, then fails strict role readback.
Root full-image comparison measures changes only at 20672, 20692, 21000, 21020,
21040, 21060, 21080 and 21100. Native container hashes remain separate where
marker metadata differs; loaded sections and images agree. Source credit stays
zero, canonical 304 stays fixed, and T06/T10 remain open.

`jus-bjry.34` is accepted and closed, published in JUSDecomp `cde0211`.
Two frozen unsigned-word load models match the original twenty-byte selections
at `0x037fd004` and `0x037fd018` with one current82/O4s trial each. Seven real
compiler objects now fill the 460-byte selection `[0x037fcf04,0x037fd0d0)`;
the former opaque 40-byte bridge is replaced by the two actual load objects.
The five previously accepted source/object pins and mixed recipes are unchanged.
Both complete ARM7 images match, with six loads and 21424 separate BSS bytes.
Root and independent fresh replay and six tests pass; the gate verifies 56
worker and 65 acceptance pins. All seven omissions, placement and malformed
loads reject. The equal-load swap links, changes only stored bytes 20928/20948,
keeps all twelve initializer calls stable, and fails actual role checks.
The store-swap and guard controls retain their previously measured changes.
Separate native container hashes preserve marker metadata differences while
all loaded sections/images/call contracts agree. Source credit remains zero;
canonical 304 and T06/T10 status stay fixed. The audit found and corrected a
late tracker item comment for the native design release; precompile gates preceded
compiler release and the corrected chronology is recorded explicitly.

`jus-bjry.26` fixes acceptance lists that incorrectly included six ignored
Python cache files. Correct public artifact counts are 27 and 26 for the two
compiler rejection packages. The new verification CLI checks every recorded
pin against Git HEAD and working bytes. Four real Git-fixture tests pass;
independent fresh checkout verifies all 139 pins across the five new packages
and rejects exactly the six entries in the actual old manifests. Compiler
sources, objects, experimental outcomes and older capsules remain unchanged.

## Reusable evidence for later source reconstruction

Owner-supplied reuse map, saved on 2026-10-05 for T06 and later subsystem
matching. Check these records before repeating static analysis. The ROM catalog
query CLI complements the MCP graph of repository source code; its saved
function/xref/disassembly evidence concerns the original game.

| Reuse | How it speeds up later source work |
|---|---|
| [Function/xref query CLI](../../scripts/analysis/query.py) over saved catalogs and disassembly | Retrieve constructor callers, callees, literals and instruction windows. Verified `func 0x0202c4ac` reports 84 ARM instruction bytes and eight catalog caller functions. Later original ELF readback establishes a 92-byte full extent including two literal words. |
| [Loop Atlas state](../../scripts/analysis/loop-state-atlas.json) | Search saved investigations before repeating static analysis. |
| [CommonEffect vtable/copy-chain research](../research/findings/vtable-diff-names-slot-0x18-as-clone.md) | Reuse clone-slot and embedded-member `+0x6C` leads. The old 44-slot census is superseded by T06's 76-entry table. |
| [Tagged allocation census](../../scripts/decomp/alloc_census.py) and [allocator argument research](../research/findings/allocator-arg3-is-line-number.md) | Recover source-file/function/line tags and allocation sizes. The two CommonEffect create/clone allocations are `0x84` bytes. |
| [Getter research](../research/findings/0206cf28-is-a-boolean-getter.md) | Reuse the established pointer chain and virtual slot `+0x5C` call shape when checking nearby object layouts. |
| [Overlay cross-check](../research/findings/jusdecomp-external-crosscheck.md), tracker item `jus-jusdecomp-crosscheck-x1cf` | Avoid upstream subsystem mislabeling: combat core is ARM9/ov6; ov11 is AI. |

Run from the `jus-research` root:

```bash
python3 scripts/analysis/query.py func 0x0202c4ac
python3 scripts/analysis/query.py callers 0x0202c4ac
python3 scripts/analysis/query.py disasm 0x0206ca8c 260
```

All three commands were rerun when saving this map. The eight-caller count is
from the function catalog. `callers` currently returns 21 mixed references,
including caller-function entries, instruction call sites and ov12 references;
those entries are not 21 distinct calling functions. Preserve each reference's
region and verify cross-region instruction sites before using them as evidence.
These leads do not resolve the existing T06 ABI/constructor blockers or grant
additional matching source credit.

## Research whole-ROM integration checkpoint

`jus-bjry.35` is accepted and closed, published in JUSDecomp `dc61c14`. The fresh research pipeline consumes the seven real ARM7 objects through unchanged verification and packing helpers with genuine parent and child live operations. Twenty disjoint writes combine seventeen parent ARM9 buffers, the checked child-native ARM9 slice and two ELF-derived ARM7 buffers. Root and independent fresh rebuilds match the entire 67108864-byte original ROM and complete child image. Parent verification retains its original nineteen stages and outputs; a separate nineteen-stage module checkpoint and seven-stage experiment describe the actual research work.

Direct checks cover 916 output artifacts, 153 actual input pins, 198 trial artifacts, all seven objects, both six-load native ELFs, twelve calls and five bindings per program. Twelve independent tests pass in 173.405 seconds. Root reproduced a real final-receipt mutation defect before accepting the first positive, and confirmed the fixed replay rejects a changed ROM without returning a receipt. Historical red and fixed regression evidence are published separately. The committed gate verifies 98 raw-equal artifact pins against Git HEAD and working bytes. A separate check verifies all 119 repository inputs and exact LF Git blob to CRLF checkout provenance for 47 existing text inputs under unchanged attributes.

The [public proof](https://github.com/JUS-Reverse-Engineering/JUSDecomp/tree/track-a/matching/decomp/matching-notes/other-cpus/arm7-arena-rom-proof) contains scripts and compact root/independent readbacks. Canonical approvals, previous capsules, C models and compiler recipes remain unchanged. The seven objects cover 460 distinct candidate bytes, or 920 across the two physical images. ARM7 accepted source credit stays zero, canonical source stays 304 bytes and global coverage remains unknown. T06 and T10 stay open for original source/ABI/ownership evidence and remaining opaque routines. This checkpoint makes no boot or emulator claim. A gpt-6-astra trail review used a manually selected bounded excerpt; its final publication follow-up is recorded in the decision trail.

## Constructor storage grounding checkpoint

`jus-bjry.36` is accepted and closed, published in JUSDecomp `94690c1`. Original `0202c4ac` has 84 instruction bytes and eight literal bytes, for a full 92-byte extent. Fresh original objects and ROM instructions prove four outgoing relocations and thirteen direct call sites across eleven functions. Nine calls are in main and four are in ov012, including two Thumb BLX sites. The eight main catalog caller functions and twenty-one mixed query references remain separate counts. The contract records the minimum twenty-byte storage, ordered field writes, helper calls, counter update, return and observed caller allocations.

Root and independent fresh original-only replay pass. A root-discovered optimized-Python assertion bypass is fixed; both `-O` and `-OO` reject before output. The strict gate verifies twenty-seven published pins, including the final independent publication audit. All fifty-six runtime repository pins are owned, nine as raw-equal Git/working bytes and forty-seven through the unchanged explicit LF/CRLF provenance record. Original C++ identity, ownership and allocator failure policy remain unresolved. Canonical source remains 304 bytes, ARM7 zero and global coverage unknown.

The [public contract](https://github.com/JUS-Reverse-Engineering/JUSDecomp/tree/track-a/matching/decomp/matching-notes/pilot-t06/constructor-storage-contract) and independent review support a distinct physical initializer design over preallocated storage. New `jus-bjry.37` bounds that design and one frozen source recipe. Compilation requires a separate recorded design release; the existing C++ near-misses are not reopened.

## Physical initializer trial design release

`jus-bjry.37` now has two frozen designs and a gpt-6-astra cross-review. The typed minimum twenty-byte record scores 11/12; the fixed-offset access design scores 8/12. Root chose the typed record and added a fresh complete ninety-two-byte DSD reference check before compilation in every replay. The physical counter prefix preserves the original symbol and observed offset without claiming an original global declaration or size.

The isolated source worktree starts at `94690c1`. Its design release authorizes original-artifact controls before writing the C body, then one ordinary C model with the existing MW build114 ARM946E `-O2` recipe. One unchanged verifier invocation performs the actual compile. A strict miss ends the model; a match continues actual native input selection, placement, module and whole-ROM checks. Receipt publication must recheck source, tools, reference, diagnostic outputs and final receipt bytes. No canonical source promotion or second model is authorized by this trial. Implementation is in progress; no compiler result is claimed here.

## Frozen physical initializer result

The reviewed design is published in JUSDecomp `3d6281b`. Its first replay stopped before compilation because resolving the `ld.lld` symlink changed the executable name to generic `lld`. The wrapper now preserves the driver name while pinning the actual tool bytes. The C model, CPU and MW compiler flags did not change.

The subsequent frozen trial compiled once and failed strict initialized-byte comparison. The compiled function retains the full ninety-two-byte extent, sole allocated text section and exact four named relocations. Ten unmasked byte positions differ across four instructions at offsets 20, 24, 28 and 32. Two additional raw branch placeholder words differ but are correctly masked by the matching relocation records. The model is stopped without tuning; no source object is accepted and no native or ROM stage runs. Root actual-object readback confirms the result. Final public replay, independent reproduction and publication checks passed; the bounded trial is closed and published in JUSDecomp `70235e9`. Canonical source remains 304 bytes, ARM7 zero and global coverage unknown; T06 and T10 remain open.

The result commit contains forty-four new files and an append-only decision trail. A final publication audit reports no flags for that committed scope and actual push records. Its later metadata copy is published in `576207b`, bringing the capsule to forty-five files and the committed gate to sixty-seven raw-equal pins. The metadata copy lies outside the audited result commit. This is distinct from the sixty-six runtime repository inputs, whose provenance is nineteen raw-equal files plus forty-seven exact Git LF to consumed CRLF relations. Root and independent final replays each rehash 2,566 ordinary output files and 157 inputs. Eleven current tests pass. The final bounded gpt-6-astra runtime review reports no flags; its historical flags and real red/fixed controls remain in the capsule. No initializer tuning follows the measured rejection.

## Hash helper grounding scope

New `jus-bjry.38` is an original-only T06 prerequisite for the forty-four-byte helper `020326b0`. It checks saved research before analysis and distinguishes inherited signed-byte/NUL/16-bit facts from any new exact arithmetic contract. A new capsule is warranted only if useful recurrence or boundary facts remain unrecorded. Pure arithmetic examples are predictions from static evidence. No C/C++ body, compiler trial, emulator job, source credit or initializer retry is released. Root records findings and publishes; an isolated writer and independent reader check the original evidence.

Fresh original evidence and independent static review recover `h_next = h XOR ((sign8(b) OR (h << 1)) & 0xffff)`, seeded at zero. The loop prechecks each signed byte, then rereads it with postincrement before updating. Sequence predictions assume stable readable memory through NUL. All sixty-two actual incoming relocation sites decode to the helper and belong to forty-two region-qualified functions across nine objects. The saved query has sixty branch observations plus seventeen function summaries; it misses two Thumb BLX sites in ov001 and ov005. Original SDK identity and C/C++ declarations remain unestablished. The bounded grounding is accepted and closed, published in JUSDecomp `1ebd198`. Root and independent fresh replays each verify 539 input/artifact hashes and 477 generated artifacts plus the checked receipt. The artifact gate verifies thirty-one Git HEAD and working pins; the separate input check proves ten raw-equal inputs and forty-seven exact LF/CRLF relations. Four genuine ELF mutations and nine CLI/input negatives reject. The initial unchanged-addend control and a root packaging count that included ignored bytecode are recorded and corrected. The independent frozen runtime review reports no flags; it excludes later acceptance metadata and publication. The accepted result contains nineteen new files and an append-only trail. A final publication audit reports no flags for source `1ebd198` and tracker `c878122e`, including actual push records. Its later metadata copy in `90da82e` brings the capsule to twenty files and the artifact gate to thirty-two pins; that copy is outside the audited result commit. Source credit remains unchanged; a future source trial requires its own design and release.

## Physical helper trial scope

New `jus-bjry.39` investigates one physical source model for the accepted forty-four-byte helper contract. Ground the actual unchanged verification and selected-object authority first, then freeze two distinct unimplemented designs, cross-review them and publish root synthesis/release before writing C or invoking a compiler. The existing MW build114 ARM946E header-free `-O2` context is fixed. A strict miss stops the one model; a strict match continues real native input, placement, module and whole-ROM checks. Canonical credit and manifests remain unchanged during this research trial. The stopped initializer is not retried.
