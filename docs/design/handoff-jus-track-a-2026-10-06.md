# JUS Track A session handoff

## Goal

Resume matching source reconstruction under epic `jus-bjry`, using subagents. Start with tracker item `jus-bjry.39` in this repository. Work autonomously within its recorded scope.

## State

- [published] JUSDecomp `track-a/matching`, commit `1687b1bfb9eccec35aee58b5afda1735f8e04ccf`, at `<TMP>/jus-track-a-publish`. Clean; HEAD equals local origin tracking ref.
- [published] Tracker/plan commit `9c30ea57eb0fd2ddcb40fddb2a555e62821c32f2`, at `<TMP>/jus-track-a-record-publish`. Clean; HEAD equals origin/main.
- [in flight] `jus-bjry.39` is in Ground, partially complete. A fresh original split isolates one ARM function with sole44-byte text and no relocations, selected once by LCF. All62 incoming call sites across42 region-qualified functions preserve their targets. No task39 C body, design selection, compiler trial, native build or whole-ROM verification has occurred.
- [accepted] Seven parent source functions total304 bytes; ARM7 accepted source credit is zero; global coverage unknown. T06/T10/epic remain open. Task38 is closed.

Live state checked while writing this handoff. Main research checkout is behind origin/main and contains existing edits to the plan and `jus_files`, plus a stash. Preserve them. Its Git metadata is read-only in the current permission profile; use writable private publishing checkouts. Existing source and tracker pushes succeeded in the preceding session.

## Artifacts

- [Plan](https://github.com/JUS-Reverse-Engineering/jus-research/blob/main/docs/design/JUS-Matching-Decomp-Plan.md)
- [Local plan](JUS-Matching-Decomp-Plan.md)
- [Task39 resume notes](https://github.com/JUS-Reverse-Engineering/JUSDecomp/tree/track-a/matching/decomp/matching-notes/pilot-t06/physical-fold-source-trial/design)
- [Accepted original helper contract](https://github.com/JUS-Reverse-Engineering/JUSDecomp/tree/track-a/matching/decomp/matching-notes/pilot-t06/signed-byte-fold-contract)
- [Stopped initializer trial](https://github.com/JUS-Reverse-Engineering/JUSDecomp/tree/track-a/matching/decomp/matching-notes/pilot-t06/physical-storage-init-trial)

## Decisions

Read the plan's current checkpoint and task39 design README first; the README reconciles the earlier partial writer note with the later independent selected44 preflight. Check the owner's saved reuse map before repeating static analysis. Use isolated worktrees for every writer. Use rg for code discovery. Root owns tracker, synthesis/release, decision trail and publication.

Keep the existing pinned ARM946E MWbuild114 header-free `-O2` context. Types describe the physical experiment, not original SDK/C++ identity. Preserve `ld.lld` argv0. One frozen model/recipe and one unchanged verifier call per fresh replay; a strict miss stops the model. A match must continue actual native input selection, placement, module and entire-ROM verification. Canonical promotion is a separate scope. No emulator work is released here.

## Dead ends

Initializer37 compiled but differed at ten unmasked bytes and is stopped; do not tune or retry it here. Resolving `ld.lld` to generic `lld` broke driver selection. Whole-gap evidence does not establish selected-TU geometry. Static vectors are predictions, not original execution. An initial relocation negative control wrote unchanged bytes; controls must actually mutate their inputs. Raw recursive file enumeration picked up ignored bytecode; use Git-eligible file lists. Preserve the47 explicit Git-LF/checkout-CRLF relations instead of changing attributes.

## Next move

Finish task39 Ground with actual changed-original/comparison controls and frozen finite input/tool/config pins. The fresh selected44 positive already exists; read its evidence instead of treating it as unrun. Then produce two distinct unimplemented designs, cross-review, synthesize and publish release before writing C or invoking the compiler. Update findings in tracker items immediately.

At the last checkpoint, the published helper gate32 and task39 metadata gate8 passed in both the publisher and a fresh checkout. These were artifact checks, not a new target compilation. Run the appropriate actual checks after changes, maintain the plan and append-only trail, export owned tracker items, and commit/push both repositories before ending. Preserve unrelated local work.

## Suggested skills

Use `architect` and `arena` for the two designs and synthesis, `test-driven-development` for actual controls before implementation, `principle-prove-it-works` for real artifacts, and `show-me-your-work` for the decision trail. Apply `unslop` to prose.
