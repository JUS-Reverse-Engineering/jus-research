# KeshireTheChaotic/JUMP-Ultimate-Stars

| Field | Value |
|---|---|
| Repository | <https://github.com/KeshireTheChaotic/JUMP-Ultimate-Stars> |
| Author | KeshireTheChaotic |
| Revision examined | `c20d9e73c0161087c14c551e33987301bc588b37` |
| Read from | a local clone, read-only |
| Licence | no licence file in the revision examined |
| Role in jus_re | cross-check source for static analysis of the game code |

## What it contains

- Ghidra function layouts for the ARM9 binary and the overlays, under its
  `reverse_engineering/functions_layout` directory.
- A C# port of the game in progress, with comments that describe what each routine does.
  The battle overlay carries its own battle map note (BATTLE_MAP.md in its tree).
- Python readers and editors for the game's resource formats, with notes under its
  `Editor/docs` directory.
- A gap audit of its own reverse-engineering coverage.

The repository states that it ships no game data. Its README names the ROM image its tools
support.

## Permission

The jus_re owner has Keshire's permission to fold Keshire's work into jus_re. Material that
jus_re takes in is restated in our own words and credited to this page, and each claim is
checked against our ROM before a tracker item records it.

## ROM identity

The ROM file Keshire's tools support has a SHA-256 starting `52e26216`. The ROM file jus_re
uses has a SHA-256 starting `a9c9bf89`. The two files differ, but the ARM9 binary and every
overlay are byte-identical between them. Addresses in ARM9 and the overlays therefore carry
over between the two projects without translation.

## What jus_re has taken in

The first intake took in these tracker items:

| Tracker item | Subject |
|---|---|
| `jus-jpower-retraction-cguk` | retraction of the jpower damage reading |
| `jus-jpower-koma-price-table-uh9o` | what jpower.bin holds |
| `jus-reaction-table-start-handlers-8l0w` | what the reaction pointer table holds |
| `jus-speed-cap-fighter-scope-uhs4` | which elements the speed cap covers |
| `jus-getup-invuln-store-site-gm12` | where the get-up invulnerability is stored |
| `jus-vblank-wait-sdk-call-du3c` | how the main loop waits for vertical blank |
| `jus-extract-jpower-fields-cleanup-ndty` | follow-up cleanup in the character extractor |

Each tracker item names its sources in its provenance line. Findings entries restate six of them
(the retraction, the price table, the reaction table, the speed cap, the get-up store and
the vertical-blank wait); those that draw on Keshire's work link back to this page.

## How to cite

Cite the tracker item for the claim, and link this page for the source. Name the revision above
when a doc depends on a specific reading.

## Contact

A public GitHub issue on Keshire's repository will link to this page, so Keshire can see
what jus_re took in and how it is credited. Corrections go through that issue.
