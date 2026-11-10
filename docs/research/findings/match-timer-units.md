# Frames per timed-match timer unit: 144, CROSS_CONFIRMED (bracket 137.3–150)

Tracker items: `jus-timed-match-timer-units-2jyu`.

## Grade: CROSS_CONFIRMED (frames/unit), NOT FOUND (address/decrement pc)

**Search the record first.** This ticket re-derived a number that was already
closed. `../Battle-Engine-Map.md` (rule/match settings,
`p165-mode-table-is-rulemess-bin.md`) already carries `144` as
`CROSS_CONFIRMED`: ov1's versus-mode conversion `time_limit_frames =
(じかん + 1) * 144 - 1` agrees end to end with `0x020AFEAC` = 4463 measured at
じかん 30 (`jus-1g6`, `jus-6fo`). Tracker item `jus-uvs` (closed 2026-08-18) already
ran a wall-clock/frame check of a じかん-30 point battle and reported ~152
frames/unit with a quantisation range of 122–203, noting 144 sits inside and
that じかん-as-seconds (60 f/unit) is refuted by ~2.5×. This session's fresh
trials narrow that bracket further but do not overturn it, and should have
started from `jus-uvs` rather than re-running the same measurement from
scratch. What is genuinely new here is the tighter bracket below and the
open questions that remain (backing RAM word, decrement pc, KO/cut-in stall
behavior).

`じかん` is a **whole-match** frame budget (4463 frames at じかん 30 — the
span from battle-object creation to the ポイントバトル result screen), not a
per-round limit. Mission rules use `じかん * 60` (a different, `+0xC == 1`
code path; not exercised this session). The RAM word backing the on-screen
`TIME` counter, its decrement pc, and whether the counter stalls during
KO/cut-in windows are still open.

## Question

the combat notes §11 has "Frames per timer unit: TBD" for the real
(non-training) match clock. Training mode's clock field reads a constant 255
(`docs/confirmed-facts/physics.md` §5) -- no clock exists there. This ticket
needed a genuine timed match to observe a counting-down clock at all, and to
check the already-closed `144` against fresh, independently-timed trials.

## Conditions

- Emulator: pinned fork commit `c26edf0e0d75364823856c9272a103fe39e03999`
  (`scripts/emu/build_info.json`), JIT off, launched via
  `scripts/emu/launch_emu.sh` under `JUS_EMU_HOLDER=2jyu`, one live holder for
  the whole session (`pgrep -fl melonDS` empty and no stale `HOLDER` file
  confirmed before each launch).
- **No pre-existing savestate is a real timed match.** Every `pc-*`/`ds8t_*`
  state in `jus_files/save_states/INDEX.md` is training (no clock); the one
  historically-timed slot (`luffy_battle`) was deliberately not kept
  (INDEX.md "Not kept" -- CPU-controlled, non-reproducible). A fresh timed
  match state was built this session by navigating J Arena's **バトル**
  (`VS`/"BATTLE") menu, not トレーニング, choosing a deck, stage, and the
  default rule screen (`ルール: ポイント`, `じかん: 30`, `COM: 1人`), then
  saving mid-round as `/tmp/jus_emu/states/timer_probe_battle.mln`.
  **This savestate was not committed** -- it is session-local, and only the
  navigation recipe (below, "How to rebuild the state") is preserved in the
  repo. Note also, per `p163-rule-select-screen-mapped-to-memory.md`
  §"Consequences for the harness": all six rule-select settings, including
  `じかん`, can be written directly from RAM (`0x020AFEAC` for the frame
  count, bypassing the two-branch converter entirely) instead of navigating
  the menu each time -- a faster route for a future session's setup.
- Frame basis: the bridge's own `framecount` (`jusemu.py screendump`/`run`
  report it directly). The suggested pad-read address
  `0x0203A640` was not used as a GDB frame marker because GDB never attached
  successfully this session.
- Measurement method: load `timer_probe_battle`, `screendump` immediately
  (baseline `TIME` digit read by eye from the framebuffer PPM, plus
  `framecount`), run a fixed no-input frame count via
  `scripts/emu/jusemu.py run` (`{"segments":[{"from":0,"to":N,"buttons":[]}]}`),
  `screendump` again immediately after, read the new `TIME` digit and
  `framecount`. Repeated from the *same* reloaded savestate (fc 13477 at
  load, `TIME` reads 25 once settled) for `N` = 600, 1200, and 3000, plus two
  earlier trials that additionally did full-RAM (`0x02000000-0x02400000`)
  dumps bracketing the run. All trials share one savestate phase (same load
  point, same `TIME` value at load) -- see Falsification.
- Positive control: the bridge's own `framecount` delta always matched the
  requested plan length exactly (e.g. `run` reported `frames: 601` for a
  600-frame no-input segment, `fc_end - fc_start == 601` in every trial) --
  the harness's own frame accounting is trustworthy; what is *not* nailed
  down is which real-time span the *displayed clock* consumes per unit.

## Evidence

Baseline for every trial below: reload `timer_probe_battle`, settle
framecount 13477->13483, `TIME` reads **25**.

| trial | Δ framecount (from fc 13483) | `TIME` end | ΔTIME | naive frames/unit |
|---|---|---|---|---|
| run 600 (screenshot-only, no RAM dump) | 620 | 21 | 4 | 155.0 |
| run 1200 (screenshot-only) | 1220 | 17 | 8 | 152.5 |
| run 3000 (screenshot-only) | 3020 | 4 | 21 | 143.8 |
| run 600 + full-RAM dump before/after | 640 | 18 (from 23) | 5 | 128.0 |
| run 600 + full-RAM dump, separate trial | 1730 | 13 (from 25) | 12 | 144.2 |

### Quantisation, not a dump confound

The on-screen `TIME` digit is an integer, and each trial only reads it twice
(before/after), so the *true* decrement count during a window can be off by
up to one from the naive `ΔTIME` reading -- the counter may have just ticked
right before the "before" read or right after the "after" read. That gives
each trial a quantisation-consistent frames/unit range of
`Δfc/(ΔTIME+1)` to `Δfc/(ΔTIME-1)`, not a single point estimate:

| trial | Δfc | ΔTIME | quantisation range (frames/unit) |
|---|---|---|---|
| run 600 | 620 | 4 | (124.0, 206.7) |
| run 1200 | 1220 | 8 | (135.6, 174.3) |
| run 3000 | 3020 | 21 | (137.3, 151.0) |
| run 600 + dump | 640 | 5 | (106.7, 160.0) |
| run 1730 + dump | 1730 | 12 | (133.1, 157.3) |

Under this accounting, **both dump trials are consistent** with the three
screenshot-only trials -- their ranges overlap the same band instead of
sitting systematically lower. There is no need to invoke the dump's
synchronous Lua callback distorting real-time throttling; ordinary
±1-unit read quantisation explains the spread on its own. (The previous
version of this finding raised that dump-confound hypothesis and is
retracted here.)

### The bracket

Treating the three screenshot-only trials as sharing one common (unknown)
phase `p` -- i.e. `decrements(Δfc) = floor((p + Δfc) / R)` for a single period
`R` and a single `p` in `[0, R)`, since all three reloaded the identical
savestate -- and solving for the range of `R` for which a consistent `p`
exists across all three trials (620/Δ4, 1220/Δ8, 3020/Δ21) gives:

**137.3 < R < 150** (both ends exclusive).

This bracket **contains 144** (the already-`CROSS_CONFIRMED` value from
`../Battle-Engine-Map.md`/`jus-1g6`/`jus-6fo`) and **excludes both 60** (じかん
as seconds; already refuted by `jus-uvs`) **and exactly 150** (the earlier
draft of this finding's "no rounding" reading, which does not survive the
tighter three-trial system -- retracted). At the DS's ~59.83 Hz, 144 frames
is ~2.41 real seconds per displayed unit.

## Round/match structure, observed incidentally

The rule screen's `じかん 30` is a **whole-match** frame budget, not a
per-round limit. The earlier draft of this finding read a "TIME back at 30
several thousand frames after a KO" observation as a per-round reset; that
observation is instead the **next match**, not a new round of the same
match -- the session's extended idle period ran the match to its own
conclusion and reached a "ポイントバトル リザルト" (point battle result)
screen unattended, matching the whole-match accounting already established
by `jus-6fo` (battle-object creation to result screen == the configured
frame count). No round-reset behavior was actually observed this session.

## What did not work

- **GDB attach failed three separate times** (`vMustReplyEmpty` timeout on
  `target remote localhost:3333`), both mid-session and after a full
  `stop_emu.sh --force` + relaunch. `pgrep -fl melonDS` showed the process
  healthy and `jusemu.py status` kept reporting an advancing `framecount`
  throughout, so the core was not halted -- the GDB *stub* connection itself
  was refusing new attaches. One clean attach+`jus-scan`+detach cycle did
  succeed earlier in the session (used only to confirm the stub was live at
  all); every attach attempted afterward, including from a fresh emulator
  process, failed identically. Root cause not diagnosed this session; flagged
  for whoever picks this back up (possibly stub state left over from the
  first detach, contra the "clean detach or the core halts" hazard in
  the session handoff -- the core did not halt, but the stub may
  have wedged).
- **The Action Replay code-list candidate is not the displayed clock, and
  the earlier draft of this finding mis-stated which address that is.**
  `docs/research/Cheat-Code-Analysis.md` lists this as a 2-byte field:
  a u16 at `0x021DEA70` ("Battle timer (wifi)") and a u8 at `0x021DEA71`
  ("Battle timer (local)") — the same field, read at two widths, not two
  different addresses. `scripts/emu/match_run.py` already carries this
  candidate, but resolved **root-relative**, since the battle root itself
  relocates (`root = [0x02172960]`, `TIMER_IN_ROOT = 0x11`, i.e. `root+0x11`
  == `0x021DEA71` only in the default layout where `root == 0x021DEA60`) —
  and flags it there as refuted: sampled across 1800 frames it went
  `16 -> 13 -> 11 -> 8`, which does not fit a じかん-30 counter's range or
  monotonic countdown. This session's own peek at the same address
  independently reproduced non-monotonic behavior across multiple points in
  one match (`13 -> 14 -> ... -> 17`, i.e. it *increased*), against `TIME`
  which only ever counts down. Both refutations agree; the legacy
  `jus_gdb_watcher.py`/`jus_addresses.py` name for this address (`battle_timer`)
  is misleading and should not be trusted as the on-screen counter's backing
  word.
- **A byte-level diff of two full-RAM dumps, filtered to the delta matching
  the displayed `TIME` change, is dominated by false positives.** In the
  narrowed `0x02170000-0x02220000` battle-object range, a cluster of
  addresses around `0x02202200-0x02202400` all showed exactly the expected
  `-5` delta matching a `TIME 23->18` window -- but a full dump of that page
  shows chaotic, wide-range byte churn typical of a video/text-rendering
  buffer (the on-screen digit glyphs being redrawn), not a scalar game
  variable; `../Battle-Engine-Map.md`'s standing warning about
  naive immediate-offset/byte-value sweeps producing false positives applies
  directly here. No candidate outside that suspect VRAM-like region survived
  a second, independently-timed trial with a different starting frame.

## How to rebuild the state

From the ROM boot title screen (no save-state shortcut needed): top menu ->
Jアリーナ (tap `(93,49)` + `A`) -> J Arena menu, tap `(180,111)` + `A` for
**バトル** (the 3rd of 4 rows: ランキング/ミッショントライ/バトル/トレーニング,
row pitch ~31px starting at y=49) -> deck select (`A`) -> stage select (`A`)
-> rule select screen (`ルール: ポイント`, `じかん: 30`, `COM: 1人` are the
defaults; not changed this session) -> `START` ("バトルスタート"). Save with
`jusemu.py state save <slot>` once in battle. As noted above, the rule
settings can also be written directly from RAM (`p163-rule-select-screen-mapped-to-memory.md`)
instead of navigating the menu.

## Recommendation

Cite **144 frames per displayed TIME unit in versus rules (~2.41 s at
~59.83 Hz), `CROSS_CONFIRMED`** in `docs/confirmed-facts/physics.md` and
the combat notes §11/§13, citing `../Battle-Engine-Map.md`
(`jus-1g6`, `jus-6fo`, `jus-uvs`) as the primary source and this tracker item for the
independent-trial bracket that confirms it. The backing RAM word, its
decrement pc, and whether the counter stalls during KO/cut-in windows remain
open -- a follow-up session should retry the GDB attach cold (fresh
emulator, first action after launch, before any other bridge command) to
rule out the stub-wedge hypothesis; if GDB still will not attach, use the
bridge's `tail` per-frame watch feature (`jusemu.py tail start`, budget 512
bytes / 32 watches) against small (≤512 B) candidate regions instead of full-
RAM `dump`.

## Falsification

This finding is wrong if: (a) a future session finds the real backing
address and its measured decrement cadence is not close to 144 frames/unit;
or (b) the bracket above is itself an artifact of this session's specific
savestate phase (all trials shared the same starting alignment, fc
13483/`TIME`=25 -- a trial starting from a different phase within the
current unit was not tried and could shift the bracket).
