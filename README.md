# jus-research

Reverse-engineering notes, decoded data tables and tooling for **Jump Ultimate Stars** (Nintendo DS,
2006). The work combines static analysis of the ROM (ARM9 and overlay disassembly, file-format
decoding) with dynamic measurement in an instrumented emulator. Every claim is meant to be
checkable: documents cite the addresses, scripts and captures behind them and grade their own
evidence (`STATIC`, `MEASURED`, `INFERRED`, `UNMEASURED`).

This repository holds no game data. ROM-derived files live in the `jus_files` submodule (see below),
and you supply your own copy of the game.

## What is here

| Path | Contents |
|---|---|
| [`docs/confirmed-facts/`](docs/confirmed-facts/) | Settled descriptions of how the original game works, one topic per file: moves, damage, guard and SP, physics, collision, entities, the nature system, koma, the deck editor, helpers, the CPU AI. Start here. |
| [`docs/formats/`](docs/formats/) | Binary layouts: `chr_b.bin`, collision records, `jpower.bin`, sprite archives. |
| [`docs/research/`](docs/research/README.md) | The research record: explanations (battle engine map, HP and damage, deck memory, overlays), the append-only findings journal, CPU-AI side quests, small pre-registered experiments, clash-tier survey, player notes on move behaviour, summaries of public GameFAQs guides, menu screenshots. |
| [`docs/rebuild/`](docs/rebuild/) | Decoded tables generated from the ROM (JSON plus a readable Markdown view): cancel rules, knockback, button-mash, UA, character natures, collision boxes and node flags, animation timing, VFX/SFX, feature census. Each is produced by a generator in `scripts/analysis/`. |
| [`docs/harness/`](docs/harness/README.md) | How to measure: the emulator harness, menu navigation, RE session playbook. |
| [`docs/design/`](docs/design/) | Plans for matching decompilation and reusable RE tooling, plus a session handoff and archived plans. |
| [`scripts/analysis/`](scripts/analysis/) | ROM readers, table generators, disassembly and cross-reference helpers, renderers. |
| [`scripts/decomp/`](scripts/decomp/), [`scripts/ghidra/`](scripts/ghidra/README.md) | Symbol and struct extraction, Thumb disassembly, a PyGhidra project builder and query tools. |
| [`scripts/emu/`](scripts/emu/README.md) | A melonDS-based harness: launcher, file-IPC bridge, savestate and RAM recorders, hook sources, experiment sweeps. See [`NOTES_FOR_LINUX.md`](NOTES_FOR_LINUX.md) for the Linux port. |
| [`scripts/gdb/`](scripts/gdb/) | GDB scripts and drivers for batch memory probes over the emulator's GDB stub. |
| [`scripts/patches/`](scripts/patches/README.md) | IPS patch builders and verifiers. |
| [`scripts/tests/`](scripts/tests/README.md), `scripts/emu/tests/` | Unit tests for the generators and the emulator tooling. |
| [`data/owner-matches/`](data/owner-matches/) | Anonymised RAM traces and hang samples from recorded matches. |
| [`sources/gamefaqs/`](sources/gamefaqs/) | Fetch and parse scripts for the public GameFAQs guides (the guides themselves are not included). |
| [`resources/`](resources/) | `desmume_jus.diff`, an emulator patch. |

## Setup

Toolchain versions are pinned in [`mise.toml`](mise.toml):

```bash
mise install            # Python 3.12, Lua 5.4, JDK 21 (Ghidra), CMake
```

`mise` does not provide C libraries or GUI apps. Building the emulator fork needs `pkg-config`, Qt6
(base and multimedia), SDL2, enet, faad2, libarchive and zstd from your package manager;
`arm-none-eabi-gdb` (or plain `gdb` on Fedora) and Ghidra are needed for the GDB and Ghidra
tooling. Python packages for the tests and some tools are listed in
[`scripts/tests/requirements.txt`](scripts/tests/requirements.txt) (numpy, jsonschema, Pillow,
capstone); `pyghidra` is needed for `scripts/ghidra`.

### The `jus_files` submodule

```bash
git clone --recurse-submodules git@github.com:JUS-Reverse-Engineering/jus-research.git
# or, in an existing clone:
git submodule update --init
```

`jus_files` (<https://github.com/JUS-Reverse-Engineering/jus_files>) holds the ROM-derived working
files: extracted `ftc/` contents, overlays and analysis output. Scripts read them from
`jus_files/ripped_jus_files/ftc`. Many tests require the initialized `jus_files` submodule; missing
inputs may fail or skip. The ROM itself is not distributed.

### Running things

```bash
python -B -m unittest discover -s scripts/tests            # table-generator tests
PYTHONPATH=scripts:scripts/tests:scripts/emu \
  python -B -m unittest discover -s scripts/emu/tests -t . # emulator tooling tests
lua scripts/emu/tests/test_bridge_core.lua                 # bridge core
python3 scripts/analysis/mash_table.py check               # a generated table is fresh
```

Generated tables in `docs/rebuild/` are never edited by hand: change the generator and rebuild.
Some generators (`cancel_table`, `knockback_table`, `anim_timing`, `feature_census`,
`vfx_sfx_build`) also cross-check against captures and per-character files that are not in this
repository; without them their `check` prints `skipped` and verifies only what it can.

## Provenance notes

Some source captures and historical research notes are not included. Documents sometimes cite
raw capture directories (`feel-captures/`), tracker ids (`jus-xxxx`), per-character manifests
(`kit/*.toml`) or specs that are not part of this repository. Those citations are provenance only: the
claim they support is stated in the text, and the cited artefact is simply not included. Treat
`OWNER-NOTES.md` (`docs/research/moveset-notes/`) as raw player observations, with some lines
blanked; do not renumber it, because tables cite it by line.

Related public projects: [JUSDecomp](https://github.com/JUS-Reverse-Engineering/JUSDecomp) (matching
decompilation) and [JUSToolkit](https://github.com/JUS-Reverse-Engineering/JUSToolkit).
