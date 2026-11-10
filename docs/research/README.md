# Research documentation

This directory holds the reverse-engineering research for Jump Ultimate Stars: explanations,
measurements, and the history of how each conclusion was reached. For the settled facts, start
with [`../confirmed-facts/`](../confirmed-facts/).

## Where things are

| Location | What it holds |
|---|---|
| [`../confirmed-facts/`](../confirmed-facts/) | Portable descriptions of how the original game works, one topic per file. |
| Markdown files in this directory | Current research explanations: data structures, damage and HP, the nature system, the deck editor, overlays, the battle engine map. |
| [`findings/`](findings/) | Findings journal, one file per investigation. Append-only; an entry can be superseded, so start from a current fact or explanation and follow its citations here. |
| [`side-quests/`](side-quests/) | Longer studies of the CPU opponent AI and related questions. |
| [`typesafe-experiments/`](typesafe-experiments/) | Small pre-registered experiments with a decision log. |
| [`clash-tier-survey-2026-09-25/`](clash-tier-survey-2026-09-25/) | Survey of hitbox clash tiers across the roster. |
| [`moveset-notes/`](moveset-notes/) | Notes from the game's players on how moves behave. `OWNER-NOTES.md` is cited by line from several tables; do not renumber it. |
| [`gamefaqs-movesets/`](gamefaqs-movesets/), [`guides/`](guides/) | Summaries derived from public GameFAQs guides (author handles only), used as a move checklist. |
| [`assets/`](assets/) | Screenshots of the game's menus. |
| [`archive/`](archive/) | Superseded plans, status notes, and test queues. |
| [`2026-10-26-support-freeze-policy.md`](2026-10-26-support-freeze-policy.md) | Static analysis of how support objects freeze. |

## Evidence

Claims carry a grade in prose (`STATIC`, `MEASURED`, `INFERRED`, `UNMEASURED`). Documents cite the
addresses, scripts and captures behind them. Raw capture directories under `feel-captures/` and
the original tracker are not part of this repository, so a citation to them is provenance only.

## Related

| Topic | Where |
|---|---|
| Research workflow | [RE session playbook](../harness/RE-Session-Playbook.md) |
| Emulator measurement tools | [Emulator scripts](../../scripts/emu/README.md) |
| Decoded tables | [`../rebuild/`](../rebuild/) |
| File formats | [`../formats/`](../formats/) |
