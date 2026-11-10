# CPU AI patches for the JUS ROM

Static-analysis patch set for the offline CPU opponent. Tracker item `jus-oubd`.
Read **[cpu-ai-levels.md](../../docs/research/side-quests/cpu-ai-levels.md)** first —
it explains the profile table, the decision gate, and why each tier does what it
does. This file is just how to run the tools.

## Tools

| File | What it does |
|---|---|
| `make_cpu_ai_patch.py` | Builds an `.ips` (or a whole patched `.nds`) for a chosen tier |
| `verify_ips.py` | Re-applies a patch with an independent applier and asserts the result |
| `factcheck_cpu_ai.py` | Re-derives every structural claim from the ROM bytes (44 checks) |

All three read the ROM named by `$JUS_ROM` (default `jus.nds`) and the
extracted binaries under `jus_files/`. Nothing is written outside `--out`.

## Tiers

| Tier | Bytes | Change |
|---|---|---|
| 1 | 482, data only | live gate parameters in `ai_param.bin` rows 1–80 → 50% acceptance |
| 2 | 477 | tier-1 data at 95%, plus revives a dead AI call site in `ov11` |
| 3 | 478 | tier 2, plus the shared threshold table → unconditional |

Tier 1 is the defensible default. Tier 2 revives a behaviour that has never run
in this build and, as `cpu-ai-levels.md` §4 explains, does so at inconsistent
rates per archetype. Tier 3 also moves five unrelated band gates.

## Usage

```sh
# build a patch
python3 scripts/patches/make_cpu_ai_patch.py --tier 1 --out cpu-ai-t1.ips

# check it applies and only touches what it should
python3 scripts/patches/verify_ips.py cpu-ai-t1.ips

# re-derive the structural claims from the ROM
python3 scripts/patches/factcheck_cpu_ai.py

# build a full patched ROM instead of a patch file
python3 scripts/patches/make_cpu_ai_patch.py --tier 1 --out jus-t1.nds --whole-rom
```

`make_cpu_ai_patch.py` refuses to emit anything if the ROM offsets have moved
(it re-derives both by content search), if a pre-image does not match, or if two
edits overlap. Builds are deterministic.

## Status

Not yet run in the emulator. See `cpu-ai-levels.md` §5 for the six open
questions, the first of which is which profile row the combat CPU actually
loads — that governs the patch's real blast radius.
