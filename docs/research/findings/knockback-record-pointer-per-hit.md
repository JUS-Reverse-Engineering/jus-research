# Knockback record identification: the moveData pointer, per hit — and a file-mapping bug it exposed

> **Superseded labels (E0 roster pin, 2026-10-18):** this finding's file-mapping bug is now settled; Kakashi (23) is na_b_04, and na_b_05, which the mapping doc then assigned to Kakashi, is Kyuubi Naruto (24). Current pairing: `docs/research/feel-captures/2026-10-18-e0-roster/roster_reconciled.json`. Kept as recorded.

Tracker item `jus-lxyt` (child of `jus-pb6n`). Grade: **CONFIRMED, live**. Closes
physics.md §4.6's last GAP ("which record the engine reads") and refutes the
kbX/kbY-only heuristic that `move_records.py`/`kakashi.md` used to identify
Kakashi's records.

## Task

`jus-idiy` (closed) proved the horizontal-knockback staging arithmetic is
exact and universal (`M+0x148 == kbX*128`, one write per frame, no
accumulation), but its probe broke at `0x020817E8` — the `moveData`-load
instruction itself — so every logged pointer read `0x0`. Three of Kakashi's
measured `(kbX,kbY)` pairs, `(5,0)`, `(3,5)`, `(8,15)`, matched no record in
`na_b_05.bin` (the file `chr_b-Complete-Mapping.md` assigns to Kakashi,
`chr_b` 23). This session re-runs the probe breaking one instruction later,
at `0x020817EC`, captures the pointer and its bytes for every Kakashi hit
plus one type-6 (launcher) control, and resolves the mismatch.

## Method

`scripts/gdb/lxyt_kbrecord.gdb` (printf probe, register values only) and
`scripts/gdb/lxyt_kbrecord_dump.gdb`/`lxyt_kbrecord_dump2.gdb` (full 20-byte
`x/20xb $r3` dumps, used to cross-check the printf probe's byte reads
byte-for-byte — they agree exactly on every pointer both captured). Breakpoint
`HITPTR`/`HIT` at `0x020817EC`: at that address `r3` already holds the
just-loaded `moveData` pointer. The instruction sequence is
`0x020817E8 ldr r3,[r6,#0x10]` (loads `moveData` into `r3`), then
`0x020817EC ldrb r0,[r3,#1]` (reads the type byte into `r0`, `r3` untouched —
this is the breakpoint address, so `r3` is intact when the probe reads it),
then `0x020817F0 ldrsb r4,[r3,#0xC]` (reads `kbX` into `r4`, `r3` still
untouched), then `0x020817F4 ldrsb r3,[r3,#0xD]` (reads `kbY` — **this** is
the instruction that clobbers `r3`, one further ahead than the breakpoint).
States: `pc-kakashi-npc-jotaro-dark-tournament` (holder `lxyt`, three
separate launches — one GDB attach each, per the stub's one-attach-per-launch
limit) and `pc-kenshin-npc-luffy-dark-tournament` (type-6 control, victim HP
poked from 152 to 100 — `0x21df7f0`, the fixed opponent-slot HP word — to
put Luffy in the 1/2-to-3/4 HP band, `F_band=0x180`, before firing Kenshin's
`X`). Plans: `scripts/emu/plans/idiy_mash.json`, `idiy_sideb.json`, a new
`lxyt_kakashi_downb_y_downy.json` (Down+B, `Y`, Down+Y), and small ad-hoc
plans for a fresh `B` and Kenshin's `X` (`/tmp/plainb.json`,
`/tmp/approach_b.json`, `/tmp/kenshin_x2.json`). These three were not
committed and were not found in `/tmp/jus_emu` when this correction pass
checked; they are **not reconstructed here** — treat the fresh-`B` and
Kenshin-`X` plan contents as lost, not as recoverable from this document.
Raw logs: `docs/research/feel-captures/kb-record-2026-09-12/`.

**Independent cross-check on the instrument itself:** after the first dump
pass, the emulator was left running (GDB `detach`, not `kill -9`) and
`jusemu.py peek` (the Lua bridge, a completely separate channel from the GDB
stub) re-read the same two addresses the GDB dump had just reported
(`0x21ba16c`, `0x21ba144`) and returned byte-for-byte identical content. The
pointer reads are not a GDB-side artifact.

## Positive control

**Artifact labelling (correction pass, 2026-09-12):** the only committed log
with an `M`/staged printf trace this session is
`lxyt_kbrecord-kenshin-pass.log` (the Kenshin control, `MSTAGE` lines). The
Kakashi rows' `M`/staged column values below are **not** backed by a
committed printf log from this session — the two committed Kakashi logs
(`lxyt_kbrecord_dump-pass1.log`, `lxyt_kbrecord_dump2.gdb`'s
`lxyt_kbrecord_dump2-pass2.log`) contain only the pointer + raw-byte dumps,
not `M`/staged output. The Kakashi `M`/staged figures are carried over from
`jus-idiy`'s earlier session rather than freshly captured here; they were
not found under `/tmp/jus_emu` when this correction pass checked, so they
cannot be re-verified from that source either. Demoted accordingly: this is
not a fresh positive control on the `M`/staged path for Kakashi, only on the
pointer/byte-dump path (which the raw logs above do back). The **type-6
control's** `M`/staged trace (Kenshin `X`, `MSTAGE frame=729 M=384
xproduct=1228800`) is the one live, committed positive control this session
has for the staging arithmetic.

Kakashi's `up B` reproduces physics.md's documented exact-recipe numbers:
`F_band=256` (0x100), staged `M+0x148 = -512`, `M+0x14A = -1652`, matching
kakashi.md's `up B` row (`kb raw (-512, -1652)`) to the raw unit — carried
from `jus-idiy`, not re-captured this session (see labelling note above).
This confirms the probe and the frame/hit correlation are sound before
trusting the pointer identifications below, which the pointer/byte-dump logs
this session *did* commit fully back.

## Per-hit pointer table

| hit | pointer | b+0x04 | b+0x07 | b+0x0C (kbX) | b+0x0D (kbY) | b+0x0E | `F_band` | staged (X,Y) |
|---|---|---|---|---|---|---|---|---|
| `B` | `0x21ba0e0` | 8 | 0 | 5 | 0 | 0 | 256 | (-640, —) |
| `up B` | `0x21ba16c` | 8 | 0 | 4 | 12 | 0 | 256 | (-512, -1652) |
| `side B` hit 1* | — (not re-captured this session; staged values `(-384,-689)` matched `jus-idiy`'s trio run) | — | — | 3 | 5 | — | 256 | (-384, -689) |
| `side B` hit 2 | `0x21ba144` | 6 | 0 | 8 | 15 | 0 | 256 | (-1024, -2065) |
| `Y` hit 1 | `0x21ba0f4` | 4 | 0 | 5 | 0 | 0 | 256 | (-640, 0) |
| `Y` hit 2 | `0x21ba108` | 4 | 0 | 3 | 12 | 0 | 256 | (-384, -1652) |
| `Y` hit 3 | `0x21ba11c` | 16 | 0 | 14 | 0 | 1 | 256 | (-1792, 0) |
| `down Y` | `0x21ba1e4` | 16 | 0 | 30 | 5 | 0x45 | 256 | (-3840, -689) |
| Kenshin `X` finisher (type-6 control) | `0x21bab90` | 10 | 0 | 25 | 6 | 1 | **384 (0x180)** | (-4800, -1239) |

(`F_band` is the HP-band table entry from physics.md §4.2, not the object
base `M` used elsewhere in this doc for the staged-pair addresses — the
earlier draft called both "M"; renamed here to stop the collision.)

\* `side B` hit 1 whiffed or missed the breakpoint budget in every re-run
attempted this session (Kakashi drifted out of range after repeated
mash/side-B plans); its staging values are carried over from `jus-idiy`'s
trio session, not re-verified against a pointer this session. Flagged as a
scope gap, not a contradiction — see Concerns.

**Type-6 control succeeded:** poking Luffy's HP to 100 (fixed opponent-slot
HP word `0x21df7f0`, victim's max unaffected) put him in the 1/2-3/4 band
(`F_band = 0x180 = 384`, per physics.md §4.2's table; `frac = 168 >> 6 = 2`,
consistent only with the 100 poke, not a 64 poke — the earlier draft's
"100/64" was an unresolved ambiguity, resolved here in favor of 100). Luffy
carries neither weight passive, so this control is weight-neutral — the
`×0.5`/`×1.5` bits do not confound the `F_band` reading. Kenshin's `X` (the
finisher, record `0x114` in `rk_b_01.bin`) staged `x = (25<<7)*384>>8 = 4800`
and logged `M=384` directly (log's own variable name, quoted verbatim in
"Positive control" above) — the constant-`F_band=0x100` gap `jus-idiy` left
open is closed: the shortcut `raw_x/128 == record kbX` holds at
`F_band != 0x100` too (`4800/128 = 37.5`... no — the shortcut is
`raw_x = kbX*128*F_band/256`, not `kbX*128` unconditionally; at
`F_band=256` those are the same number, which is why `jus-idiy`'s
`F_band=0x100`-only data looked like `raw_x==kbX*128`. At `F_band=384` the
measured `-4800` matches `kbX*128*F_band/256 = 25*128*384/256 = 4800`
exactly, not `kbX*128 = 3200`. **`jus-idiy`'s "shortcut" was `F_band`-dependent
all along; it only looked unconditional because every hit it measured had
`F_band=0x100`.**)

## Concerns

- **`side B` hit 1 is field-matched, not pointer-traced.** Its record
  identification (rec 4) rests on `kbX`/`kbY`/`frameStart`/kind/type matching
  the file exactly, carried from `jus-idiy`'s trio session — no
  `0x020817EC` pointer read backs it this session (see the per-hit table's
  footnote). `na_b_04.bin` rec 17 is byte-identical to rec 4 on every field
  the pointer trace reads, differing only in unread fields
  (`shakeRowB`/`shakeRowA`/`byte16`); rec 4 vs rec 17 is not settled by a
  pointer read (see kakashi.md's "authored records" section).
- **`down B` whiffed this session.** No pointer capture for `down B` was
  attempted/succeeded (it is not in the per-hit pointer table above); its
  `na_b_04.bin` rec 14 identification (kakashi.md) is a field match against
  `jus-kakashi-moveset-map-33lu`'s measured `(kbX,kbY)`, not a pointer read
  from this tracker item.
- **Three ad-hoc plans were not committed and could not be recovered.**
  `/tmp/plainb.json`, `/tmp/approach_b.json`, `/tmp/kenshin_x2.json` are
  referenced in Method but do not exist in `/tmp/jus_emu` as of this
  correction pass; the fresh-`B` and Kenshin-`X` runs they drove are not
  reproducible from this repo.
- **The Kakashi rows of the `M`/`F_band`-and-staged table are not backed by
  a committed artifact from this session** — see the "Positive control"
  section's labelling note. Only the pointer + raw-byte dumps (which the
  per-hit table's `pointer`/`b+0x04`.. columns cite) are freshly committed
  for Kakashi; the `F_band`/staged numbers for Kakashi are carried from
  `jus-idiy`.
- **Instrument-discipline lesson for reuse elsewhere:** verify a
  character's collision-record file by a live pointer trace, not by
  `chr_b-Complete-Mapping.md`'s File column or file-name convention — this
  tracker item's whole finding is that convention was wrong for Kakashi. See
  `jus-chrb-colfile-mapping-audit-x7i2` for the mapping-wide audit this
  opened.

## The mismatch, resolved: wrong file, not wrong mechanism

Every Kakashi pointer above was checked against `move_records.py`'s
`na_b_05.bin` dump (Kakashi's file per `chr_b-Complete-Mapping.md`, `chr_b`
23) and matched **no record**, even though several fields (kind,
`frameStart`, `hitstunAdd`, sometimes `kbX`/`kbY`) were close to one entry.
A byte-for-byte search of every `na_b_0*.bin` file in
`jus_files/chrbin/chr/col/` for each measured 20-byte record found every
single one — **exactly**, at clean 20-byte-aligned offsets — in
**`na_b_04.bin`**, not `na_b_05.bin`:

| move | `na_b_04.bin` record index | file bytes | measured live bytes | match |
|---|---|---|---|---|
| `B` | 0 | `03 01 00 00 08 00 00 00 00 00 00 00 05 00 00 0c 01 01 00 00` | identical | exact |
| `Y` hit 1 | 1 | `03 02 00 00 04 00 00 00 00 00 00 00 05 00 00 05 01 01 00 00` | identical | exact |
| `Y` hit 2 | 2 | `03 01 00 00 04 00 00 00 00 00 00 00 03 0c 00 05 01 01 00 00` | identical | exact |
| `Y` hit 3 | 3 | `03 02 00 00 10 00 00 00 00 00 00 00 0e 00 01 00 02 01 00 00` | identical | exact |
| `side B` hit 1 | 4 | `03 01 00 00 02 00 00 00 00 00 00 00 03 05 04 16 01 01 00 00` | (kbX 3, kbY 5 — the trio-session value) | field match (pointer not re-captured, see above) |
| `side B` hit 2 | 5 | `03 02 00 00 06 00 00 00 00 00 00 00 08 0f 00 00 02 01 00 00` | identical | exact |
| `up B` | 7 | `03 02 00 00 08 00 00 00 00 00 00 00 04 0c 00 00 01 01 00 00` | identical | exact |
| `down Y` | 13 | `03 05 00 00 10 00 00 00 01 00 00 00 1e 05 45 00 03 01 00 00` | identical | exact |

Every field the earlier finding flagged as unmatched — `(5,0)`, `(3,5)`,
`(8,15)` — is exactly `na_b_04.bin`'s record 1, 4, and 5 respectively.
`move_records.py kakashi --list` reads `na_b_05.bin` because
`chr_b-Complete-Mapping.md` maps `chr_b` 23 → `na_b_05`; that chr_b index was
independently re-verified this session by peeking the live save state's
player-slot byte `+0x29` (`0x21df1d4+0x29`), which reads `23` — **the running
character genuinely is `chr_b` 23**, so the mapping's chr_b identification is
not the error. The error is specifically the **file name** attached to that
index: Kakashi's collision records live in `na_b_04.bin`, the file the same
mapping table currently attributes to `chr_b` 22 (Sakura). This is either an
off-by-one in the `na_b_0*` file series for these two rows, or the two
characters' files are genuinely swapped; this session does not have the
evidence to tell which, and does not touch Sakura's confirmed facts or
`move_records.py`'s file-resolution logic to avoid extending an unverified
claim past its evidence (see Concerns / follow-up).

**Positive control that the pointer-tracing method itself is sound:**
Kenshin's type-6 hit, captured on `rk_b_01.bin` — the file
`chr_b-Complete-Mapping.md` attributes to Kenshin, unchanged — matched its
own file's record 20 (`id 0x114`) exactly on every field logged
(`frameStart 10, hitstunAdd 0, kbX 25, kbY 6`, and the `+0x0E` byte `1`, all
identical to the file's bytes). The method finds the right record when the
file mapping is right; the discrepancy is confined to Kakashi's file
assignment, not the pointer-read technique or `move_records.py`'s field
offsets.

## What this closes

- **physics.md §4.6 GAP ("which record the engine reads"): CLOSED for
  Kakashi's tested normals.** Every runtime record this session captured is
  byte-identical to a `na_b_04.bin` entry; there is no accumulation, no
  offset mismatch in `move_records.py`'s field table, and no missing/hidden
  record — the engine reads exactly the record physics.md's recipe assumes,
  from the correct file once the file is identified correctly.
- **kakashi.md's `B`/`side B`/`up B`/`Y`/`down Y` record identifications are
  corrected** (see kakashi.md's own update, this tracker item) to cite `na_b_04.bin`
  indices instead of the `na_b_05.bin` guesses the original table used
  (which were kbX/kbY-only heuristics, never pointer-verified).
- **A new, narrower question opens**: is `na_b_04.bin` ↔ `na_b_05.bin` a
  one-off swap (Kakashi/Sakura only) or a systemic off-by-one across the
  `na_b_0*` series? Not answered here — see Concerns.

## Provenance

Probes: `scripts/gdb/lxyt_kbrecord.gdb`, `lxyt_kbrecord_dump.gdb`,
`lxyt_kbrecord_dump2.gdb`. Plans: `scripts/emu/plans/idiy_mash.json`,
`idiy_sideb.json`, `scripts/emu/plans/lxyt_kakashi_downb_y_downy.json`. Raw
logs: `docs/research/feel-captures/kb-record-2026-09-12/`. `build_info.json`
commit unchanged from `jus-idiy`'s session
(`c26edf0e0d75364823856c9272a103fe39e03999`).
