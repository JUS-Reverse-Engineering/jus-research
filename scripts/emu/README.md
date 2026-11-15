# melonDS agent control layer

Everything in this directory lets an agent play Jump Ultimate Stars hands-free.
A patched melonDS fork runs a Lua bridge script (`agent_bridge.lua`) inside the
emulator; the `jusemu.py` CLI talks to it through files — sending button plans,
reading memory, and driving savestates. The GDB stub is still available for
breakpoints, so Lua and GDB work side by side on the same session.

## Other entry points

Scripts not otherwise documented in this README, one line each from their own
docstring/description:

| Script | What it does |
|---|---|
| `ai_patch_ram.py` | Patches the battle AI **in the running emulator's RAM** so a change is visible next frame. No ROM rebuild; `--reload` reverts. See `AI_PATCH_RAM.md`. |
| `boot_to_battle.py` | Drives JUS from ROM boot into a battle, hands-free, by pressing buttons and waiting N frames. |
| `boot_verified.py` | Boots into a training battle, verifying every screen before moving on (replaces `boot_to_battle.py`'s blind press-and-wait). |
| `build_deck.py` | Builds a multi-koma deck in the editor, verifying every step from pixels. |
| `capture_boot_trace.py` | Walks the boot-to-battle sequence and dumps RAM after every step, several times, to make menu navigation reliable. |
| `capture_feel.py` | Passively logs feel-vectors for owner-played matches, every frame (tracker item `jus-golden-damage-vectors-mj25`). |
| `deck_editor.py` | Drives the deck-make editor (ov05 / KomaEdit) end to end. |
| `emu_health.py` | Detects and recovers from a hung emulator. |
| `find_battle_structs.py` | Locates the battle character array in RAM by signature. |
| `find_screen_id.py` | Finds a RAM byte that identifies which menu screen the game is on. |
| `ichigo_y_capture.py` | Captures one savestate's kind-0x00 P1 projectile byte for byte: locates its spawn frame from the ObjShot active-list head, re-pauses a few frames into its life, dumps every backing structure frozen, and samples two one-frame position deltas. |
| `ichigo_y_diff.py` | Byte-diffs a directory of `ichigo_y_capture.py` captures, masking RAM pointers and listing every excluded offset with its reason. |
| `l77m_fast.py` | Thin single-process `IpcClient` wrapper (peek/poke/state_load/run_plan) that avoids per-call subprocess spawn, reducing (not eliminating) inter-call free-run drift when forcing RAM values close to a deadline (e.g. match-timer expiry). |
| `learn_walk.py` | Walks boot -> training battle, learning a pixel fingerprint for each screen. |
| `match_run.py` | Plays a training match from boot to finish, sampling RAM the whole way. |
| `overlay_residency.py` | Reports which ARM9 overlay is resident right now. |
| `screen_fp.py` | Fingerprints the DS screen from the emulator's own framebuffer. |

## Quick start

```bash
export JUS_EMU_HOLDER=my-re-session
bash scripts/emu/launch_emu.sh          # boots ROM + bridge, no clicking needed
cd scripts/emu
python3 jusemu.py status                # state=idle, live framecount
python3 jusemu.py selftest              # read_ok=true
python3 jusemu.py peek 0x021DF1D4 2     # player HP, raw (divide by 64)
python3 jusemu.py peek 0x021DEB3C 4 --state path/to/luffy_training.mln.gz  # offline, from a savestate file (no emulator)
python3 jusemu.py run plans/damage_probe.json
python3 jusemu.py run --timeout 180 plans/damage_probe.json  # slower GDB run
bash stop_emu.sh                        # stop the melonDS recorded in HOLDER (only that pid)
```

`peek --state` takes a savestate file path; a bare state name needs a state-store
module that is not part of this export.

`launch_emu.sh` records `JUS_EMU_HOLDER` in `/tmp/jus_emu/HOLDER`. It refuses
to launch while a live holder owns melonDS. After that check, it clears a dead
holder's record (stopping only the recorded melonDS pid, never other melonDS
processes) and starts from clean transient IPC state.
Savestates remain under `/tmp/jus_emu/states`. On a fresh machine or after a
reboot (Linux `/tmp` is tmpfs), run `bash scripts/emu/restore_states.sh` to
unpack the committed bridge states from the `jus_files` submodule's `save_states`
directory there. An unpopulated submodule has no local state directory. A live HOLDER blocks launch
even when its label matches yours; stop your own session explicitly before
relaunching.

The launcher starts melonDS in its own process session, with stdin closed and
stdout and stderr written to the IPC directory. This lets melonDS survive
cleanup of the command runner that launched it. `emu.pid` and `HOLDER` record
the melonDS PID, and `HOLDER` line 4 records its start time (`/proc/<pid>/stat`
field 22; `ps lstart` on macOS).

**Stopping is PID-scoped.** `stop_emu.sh` (alone or with `--force`) stops only the
pid recorded in `HOLDER`; `stop_emu.sh --pid N [--start-time T]` stops exactly
pid N. Real guarantees:

- Identity is the executable (argv[0] on Linux, `ps comm` on macOS; matched
  literally on a path boundary, never against arguments) plus the start token
  from launch. It is re-checked before every signal, TERM and KILL. A
  mismatch, an empty executable, or a reader that fails refuses with exit 4
  and signals nothing.
- **Linux:** every signal goes through `pidfd_signal.py`, which opens a pidfd,
  re-checks identity, and signals through that pidfd, so a reused PID cannot
  be signalled. If that cannot happen (no python3, helper missing, no pidfd
  support in the kernel or Python, or `pidfd_open`/`pidfd_send_signal`
  failing), stop fails closed: exit 5, nothing signalled, HOLDER kept. There
  is no plain-kill fallback on Linux.
- **macOS** (no pidfd): stop prints a note and uses a plain `kill`, re-checking
  identity immediately before each one. A PID that dies and is reused between
  that check and the kill could still be signalled; the gap is not bounded.
  The macOS readers (`ps lstart`, `ps comm`) are untested on native macOS; the
  tests fake `uname` on Linux.
- An `emu.pid`-only record has no start token, so a live pid there is refused
  until you pass `--start-time T`. Legacy three-line HOLDER files behave the same.
- `stop_emu.sh` always takes `flock` on `$IPC_DIR/.lock` before reading HOLDER,
  creating `$IPC_DIR` first if it is absent; no environment variable skips it. `launch_emu.sh` holds that lock from its
  HOLDER check until it publishes the new HOLDER, and runs its dead-holder
  stop by sourcing `stop_emu_lib.sh` under that lock rather than re-entering
  `stop_emu.sh`. Without `flock` (e.g. stock macOS) both print a note and
  nothing is serialized. HOLDER is removed only if it still names the exact
  record that was read.
- `--pid`/`--start-time` need a value that does not start with `-`; otherwise
  exit 2 before the lease is read. `--force` only skips the "another holder" warning.
- With no record, nothing is killed. The old kill-every-melonDS behaviour exists
  only as `stop_emu.sh --all-melonds-i-am-sure [PATTERN]` (keeps a live HOLDER
  its pattern did not match); no script uses it and it can destroy another
  session's emulator.

## Batch, resident client, inspected load errors and `info`

**`batch`: several ops, one command.** `jusemu.py batch steps.json` (or `-` for stdin) takes
`[{"op": "poke", "args": {...}}, {"op": "peek", "args": {...}}]` (or `{"steps": [...]}`) and publishes ONE `batch`
command: one id, one ack, one epoch and native-lock check. The bridge runs the steps in order inside one `_Update()`
callback (`bridge_core.run_batch`, wired in `poll_commands`) and the ack's `result` is
`{results: [{op, ok, result|error}], completed, failed_index}`.

- A step that errors stops the batch. The ack is `ok:false`, `error` names the step (`step 1 (tail_stop): ...`) and
  `result` keeps the results so far plus `failed_index` (0-based). `jusemu.py batch` exits 1 then.
- `run_plan`, `state_load`, `state_save` and `batch` are refused with "not allowed in a batch". They are
  multi-callback state machines (the bridge leaves `idle`; see the `load_state`-in-plan item under Known issues), so they
  cannot finish inside one callback. Refusals, unknown ops and bad shapes are found before any step runs, so a refused
  batch has executed nothing. At most 64 steps.
- The native-capture lock is re-checked per step, so a `native_capture_start` step locks the steps after it. While a
  native capture is active the whole batch is refused (`batch` is not `status`).
- It is not frame-atomic. Lua runs on the GUI thread while the core free-runs (see "Frame counting"), so a batch
  saves poll waits (one wait per sequence instead of one per verb); it does not freeze emulation between steps.
- At-most-once as before: a timed-out batch has an unknown fate, its `pending.json` stays, and a second `batch` raises
  until `abandon`. Nothing resends.

**Resident client.** `jus_ipc.resident()` is the one long-lived `IpcClient` per IPC dir; `jus_ipc.batch(steps)`,
`jus_ipc.state_load(slot)` and `IpcClient.call(op, args)` use it, and `l77m_fast.py` now imports it (same functions,
plus `batch`). The client re-reads the heartbeat session before each call, so a bridge restart does not leave it sending
a stale epoch. Existing verbs are unchanged.

**Inspected load errors.** When `state load` (or `IpcClient.state_load`) returns `ok:false` (a settle timeout acks that) or
times out, the Python side adds `inspection` and `hint`: the `.mln` header and version, whether the sidecar is present
and parseable (and whether the bridge's own `"framecount_at_save":N` regex can read it), the sha256 against the archive's
`<slot>.meta.json` when it lists one, the ROM on disk against `hashes.json`, and the last heartbeat framecount. It never
changes bridge timing or the settle rule, and a dummy `framecount_at_save:0` still reads "did not settle"; the hint says to
check the framecount and `[0x02181B28]` (see Harness hazards). The `.mln` version is read as `u16 major, u16 minor` at
offset 4 of the header; that layout has been checked against a synthetic file only.

**`jusemu.py info`.** Reports the bridge state (read-only: no client, no directories made), the ops this checkout's
`agent_bridge.lua` dispatches, the build record (`build_info.json` and the native Linux record) and the ROM hash
against `hashes.json`. The bridge has no op that lists its own ops, so `ops.source` is `bridge-file`: it says what the
file dispatches, not what the running emulator loaded. With no bridge it prints `bridge.up: false` and the rest.

## Emulator lease (runner-owned)

`lease.py` is the runner-owned lease for unattended campaigns. The
campaign runner process, not an agent, holds it. State lives in the IPC dir:
`LEASE.json` (replaced only by atomic rename), `LEASE.epoch` (highest epoch ever issued;
never goes backwards, even after release) and `.lock`, the one operation lock (flock) shared with `launch_emu.sh` / `stop_emu.sh`. A lease records
`token`, `epoch`, `pid`, `start` (the `/proc` start token, same identity as `HOLDER`
line 4), `campaign`, `trial_index`, `heartbeat_ts`, `acquired_ts`, `stale_after`,
`heartbeat_mono`, `boot_id` and `took_over`. It is separate from
`HOLDER`, which still records the melonDS pid.

**Takeover and fencing.** `acquire` over an existing lease succeeds only if the holder is
provably dead (different Linux boot ID, pid gone, zombie, or start token mismatch = pid reuse)
or its same-boot monotonic heartbeat age exceeds the holder's own `stale_after`
(default 120 s, `JUS_EMU_LEASE_STALE`) and its wall-clock age is nonnegative.
Acquisition and heartbeat record both clocks. A wall-clock forward step alone cannot
expire a live runner; a negative wall-clock age never counts as stale. A backward
step can delay timeout recovery until wall time catches up or the runner heartbeats,
but a provably dead process remains takeable immediately. The boot ID prevents
comparing monotonic stamps across reboots. This uses no observation sidecar or polling delay. A fresh
heartbeat from a live pid raises `LeaseHeld`. Every takeover bumps the epoch. The old
holder's `assert_current()`, `heartbeat()` and `release()` then raise `LeaseFenced`.
`assert_current()` must run before every emulator-touching operation. That Python-side
check-then-act gap is NOT bounded by the stale threshold (the threshold only permits takeover;
a suspended or blocked process can act arbitrarily late), so it is closed only for the shell
effects, below. Existing dead-melonDS handling in `launch_emu.sh` (HOLDER pid dead) is unchanged.

**File validation.** Every listed field is required. Unknown keys are rejected, so they
cannot override status fields or introduce unvalidated values for callers. Tokens and
campaigns are nonempty strings, start tokens are decimal strings, boot IDs are UUIDs,
pids and epochs are positive integers, and trial indices are null or nonnegative integers.
Clock values must be finite numbers, monotonic stamps nonnegative, and `stale_after`
positive. Booleans are not numbers. `took_over` is null, `stale`, or `dead`.
Malformed JSON, unreadable files and invalid fields fail closed, including `acquire`.
Old leases missing the new clock fields also fail closed; release them with the old
runner before upgrading. No automatic migration guesses their clock or ownership.

**Manual removal of a dead runner's old-format lease.** Remove it only when you hold the
lease, or have verified that no holder is alive. Verify first: read the `pid` in
`LEASE.json`, confirm `ps -p <pid>` prints nothing, and confirm `pgrep melonDS` finds no
emulator process. Then remove only that one file: `rm /tmp/jus_emu/LEASE.json`. Leave
`LEASE.epoch`, `.lock` and `HOLDER` in place. If any check fails, do not remove it.

**Locking protocol.** There is one lock, `$IPC_DIR/.lock`, so no lock order exists to violate.
Lease transitions (`acquire`, takeover, `release`, `heartbeat`, legacy recovery) take it via
`lease.py`; `launch_emu.sh` and `stop_emu.sh` take it, then re-validate the caller's lease
with `lease.py guard --locked` (which must not lock again), and hold it through the effect
(stop signalling, launch through HOLDER publication). A takeover therefore waits for an
in-progress effect, and a launch/stop that waited for the lock sees the post-takeover lease
and is refused (exit 6). Never call `lease.py` while holding `.lock` from another process
that will wait on it, other than via `guard --locked`.

**Shell authority is token plus epoch.** `JUS_EMU_LEASE_TOKEN` and `JUS_EMU_LEASE_EPOCH` must
both equal the current lease (`Lease.env()` returns the pair issued by `acquire`); a token
without an epoch is refused. Reusing a token in a later epoch therefore does not revive an
old shell environment.

**Legacy recovery is fenced.** With no lease file, a tokenless caller is unchanged. With a
stale or dead lease, a tokenless launch/stop first retires the lease under the lock (epoch
bumped, `LEASE.json` removed), so the old holder's `heartbeat()` / `assert_current()` raise
`LeaseFenced`. A held or corrupt lease still refuses.

**Safe lease tests.** `scripts/emu/tests/test_lease_safety.py` never touches the live
`/tmp/jus_emu` and can run while another job holds the emulator (`test_lease.py` is not in
the safe set). From the repo root:
`PYTHONPATH=scripts:scripts/tests:scripts/emu python -B -m unittest scripts.emu.tests.test_lease_safety -v`.

**Runner API.**

```python
from scripts.emu import lease              # or run scripts/emu/lease.py standalone
l = lease.acquire(campaign, token)         # LeaseHeld if a live fresh holder exists
l.assert_current()                         # LeaseFenced if taken over / released
owned.Owned(l).section()                   # lock + assert_current around every shared write
l.heartbeat(trial_index)                   # every trial
lease.bridge_stale(max_age)                # True: stop new dispatch (heartbeat.json mtime)
l.release()
```

**Launch and stop.** `JUS_EMU_LEASE_TOKEN=<token> JUS_EMU_LEASE_EPOCH=<epoch>` makes
`launch_emu.sh` / `stop_emu.sh` proceed only if both are the current lease. Without a token:
- `launch_emu.sh` needs an explicit `JUS_EMU_HOLDER=<label>` (the legacy path; an unset
  label no longer launches, exit 6) and both scripts refuse (exit 6) while a lease is held
  by a live runner with a fresh heartbeat. A dead or stale lease does not block but is retired first (above); an absent lease does not block.
- With no lease file and no token, behaviour is the legacy one for explicitly labelled
  launch callers (an unlabelled launch refuses, exit 6). Callers that launch without setting
  `JUS_EMU_HOLDER` themselves must export one first: `boot_to_battle.py`, `boot_verified.py`,
  `capture_boot_trace.py`, `emu_health.py` (relaunch; also used by `match_run.py` and
  `build_deck.py`) and `match_run.py --boot`.

**Operator steps.**
- Runner: `acquire` at campaign start, `heartbeat(i)` each trial, `assert_current()` before
  each emulator op, `release()` at the end. Launch with `env JUS_EMU_LEASE_TOKEN=T JUS_EMU_LEASE_EPOCH=E bash launch_emu.sh` (`lease.env()`).
  The operator agent may exit after queueing; its absence is not an expiry.
- Inspect: `python3 scripts/emu/lease.py status` (JSON; `state` is `free`, `held`, `stale`,
  `dead` or `corrupt`, plus `heartbeat_age` and `holder_alive`).
- Lock reconcile: `held` means leave it. `stale` or `dead` means the runner is gone or
  wedged: stop new dispatch, checkpoint or reconcile the in-flight trial, then a new runner's
  `acquire` takes over (new epoch) and the new owner runs the PID-scoped
  `JUS_EMU_LEASE_TOKEN=T JUS_EMU_LEASE_EPOCH=E stop_emu.sh --pid N --start-time T` (from `HOLDER`)
  to shut down the old melonDS. `corrupt` refuses acquisition and all guards; inspect and
  repair the file only after establishing ownership independently. Free a valid lease by hand only with
  `python3 scripts/emu/lease.py release --token T`; it refuses a wrong token.

**`pkill` doesn't work from a sandboxed shell here.** It returns 0 and claims a
match, but the signal is silently dropped. `stop_emu.sh` resolves PIDs with
the target pid, signals it directly, and checks it is actually gone.

### Projectile census

`projectile_census.py --state <slot> --out <dir>` loads a savestate, walks
every in-use ColPrm collision record (128 inline records at the
`Battle_ColPrmMan`, `manager+0x454` stride `0x188`) and every active ObjShot
element (via the manager's active-list link, `manager+0x00`), cross-references
ObjShot elements to ColPrm records through `entity+0x10`, and writes
`<dir>/<slot>.census.json` and `<dir>/<slot>.census.md`. It refuses to run if
the root/manager pointer chain looks wrong, the heartbeat framecount doesn't
tick across a 1s wait, or every in-use record fails its `+0x5C` element
sanity check (`elem+0x18 != 0`, i.e. nonzero -- not a fixed word; observed
values vary by state) — the last case means the hardcoded `--colprm-addr`
(default `0x0220DDE0`, only verified for the known control state) is
probably wrong for this state. `--trust-addr` skips this "zero passes ->
abort" guard for a census where the address was already confirmed earlier
in the same session (e.g. a post-run census with no active projectile in
that exact frame); it does not change what counts as a pass. Use
`--no-load` to census whatever state is already loaded. Output is
field-offsets-only, no gameplay names.

### Projectile replay

`projectile_replay.py --state <slot> --out <dir>` runs the whole per-frame
projectile-conflict recipe for one savestate in a single command: load and
verify the state, baseline census (`--no-load`), build and validate a
512-byte watch spec from the baseline (in-use ObjShot-linked records first,
then other in-use records, then the two lowest-index free records' `+0x40`,
then fold/accumulator windows, then `+0x17C`, in that priority order --
budget overflow is recorded, not silently dropped), a per-frame tail across
a START/no-input/START run plan (the re-pause matters -- the game keeps
running after the plan's last segment), a post-run census, and a generated
RESULTS.md with the per-record timeline. RESULTS.md reports each
census's `elem_checks_passed`/`elem_checks_failed` counts and, when any
records fail, which record indices failed -- a failing record is expected
for non-projectile ColPrm records, not a sign of a wrong address. If
*every* in-use record's elem check fails, `projectile_census.py` aborts
(raises rather than writing a census) instead of silently producing a
census built on a wrong `--colprm-addr` hypothesis. Field-offsets-only
output, same as the census tool. See
`docs/research/feel-captures/projectile-conflict-2026-09-10/INSTRUMENT.md`
for the manual recipe this automates.

## Per-trial resume for the capture runner

The batch runner and its per-trial checkpoints live in tooling that this repository does not include.

Liveness checks scan `/proc` for `melonds` in the process `comm` or executable basename, case-insensitively.
Command arguments containing `melonDS` do not count. A live PID from the client's `emu.pid` or `HOLDER` line 2
also counts, covering a renamed `$MELONDS` binary. An unlistable `/proc` or an unreadable or malformed PID
record counts as alive. A reused PID can therefore conservatively keep the bridge `PAUSED`.
`jusemu status` uses the same check with its selected IPC directory.

## Build

Use the [NPO-197/melonDS-lua fork](https://github.com/NPO-197/melonDS-lua)
at commit `c26edf0e0d75364823856c9272a103fe39e03999`, with every patch in
`scripts/emu/patches/` applied. A stock melonDS download or the unpatched fork
lacks the control and measurement behavior this harness requires.

The current build script targets macOS with Homebrew. Its default source tree
is `$HOME/src/melonDS-lua`, outside this repository. The binary
lands at `$HOME/src/melonDS-lua/build/melonDS.app/Contents/MacOS/melonDS`.
Use a disposable source checkout: the build script resets tracked files and
removes untracked files in that tree before applying the project patches.

```bash
bash scripts/emu/build_melonds_lua.sh
export JUS_EMU_HOLDER=my-re-session
export ROM="$HOME/roms/jus.nds"
bash scripts/emu/launch_emu.sh
python3 scripts/emu/jusemu.py status
python3 scripts/emu/jusemu.py selftest
```

Expect a bridge heartbeat, `state=idle`, and a successful read self-test.
Keep your local ROM outside the repositories and verify its hash below.
No BIOS or firmware dump is required. The launcher otherwise defaults to
`<ROM_PATH>`.

To change the macOS source location, set `SRC_DIR` for the build, then set
`MELONDS` to the resulting executable when launching. `build_info.json` records
the build but does not configure the launcher's path. Do not publish your
machine's paths as shared configuration.

Windows and Linux require build and harness changes, not only a different
`MELONDS` value. The stop script matches a macOS bundle process path and the
window screenshot helper links Apple frameworks. See
Windows setup and
[Linux port notes](../../NOTES_FOR_LINUX.md). Windows capture verification is
tracked separately.

The build needs Lua 5.4 from Homebrew. `lua5.4` and `luac5.4` live in
`/opt/homebrew/opt/lua@5.4/bin` and are **not** on `PATH` by default — use the
full path, or add that directory to `PATH` yourself.

Things the build script already handles (listed so nobody rediscovers them):

- The CMake option is `ENABLE_GDBSTUB`, not `ENABLE_GDB_STUB`. The wrong name
  is silently ignored.
- Deps: `enet`, `faad2`, `pkg-config`. `libslirp` is *not* needed.
- `brew install lua` now pulls Lua **5.5** and unlinks 5.4; the fork needs 5.4.
- `qt@6` is only an alias — `brew --prefix qt@6` points nowhere until the real
  `qt` formula is installed.
- Keg-only prefixes must be in `CMAKE_PREFIX_PATH` or `find_package(Lua)` fails.

### Native per-frame recorder build (separate binary)

The native recorder (`native_media/`, Lua `capture.start`/`capture.stop`,
bridge ops `native_capture_start`/`native_capture_stop`) needs its own melonDS
build. It records RAM watches, both screens and SPU audio once per completed
frame on the emulator thread, and can replay a key-mask schedule. The default
build does not contain it; the bridge loads on both and the native ops reject
with "native capture unavailable in this build" on the default one.

```bash
python3 scripts/emu/native_media/prepare_replay_build.py \
  --repository "$HOME/src/melonDS-lua" --out "$HOME/src/melonDS-native"
cmake -S "$HOME/src/melonDS-native" -B "$HOME/src/melonDS-native/build" \
  -DCMAKE_BUILD_TYPE=Release -DENABLE_GDBSTUB=ON -DUSE_QT6=ON
cmake --build "$HOME/src/melonDS-native/build" -j"$(nproc)"
MELONDS="$HOME/src/melonDS-native/build/melonDS" bash scripts/emu/launch_emu.sh
```

`prepare_replay_build.py` reads only git objects from the repository (`git
archive`), so it leaves that checkout and its binary alone. It verifies every
source file by sha256 against the committed manifests. The Linux build record is
`native_media/build_info.linux.json`. `MELONDS` selects the binary; without it
the launcher keeps the default build. `stop_emu.sh` matches either binary.

### Native hooks build: call log and list walks (third binary)

`native_media/native-hooks.patch` adds two per-capture instruments over the
replay build. It is pinned as `hooks_layer` in `build_info.linux.json`, and
`prepare_hooks_build.py` recreates the source. The binary is
`<SRC>/melonDS-hooks-build/build/melonDS`, built from the source tree
`<SRC>/melonDS-hooks-build` (see "The Linux hooks instrument" below),
outside campaign scratch. The base binary stays the guard/release control
instrument.

Source recreation now also applies `native_media/gdb-eof.patch`. Its patch hash,
input `GdbProto.cpp` and `GdbStub.cpp` hashes and corrected source hashes are pinned under
`hooks_layer.gdb_eof_fix`. A zero-byte socket receive returns `ReadResult::Eof`
before the existing idle branch. This lets `Enter(true)` disconnect a dead GDB
peer and return to the Lua bridge. All disconnect paths now clear breakpoints
and watchpoints through `DelAllBpWp()`, including EOF, socket errors, and detach
packets. Otherwise a later breakpoint hit can wait forever without a client.
Negative receives keep their existing behavior.
The follow-up `native_media/gdb-reconnect.patch` resets `NoAck` and
`RecvBufferFilled` on disconnect. The EOF build retains both fields, so a second
GDB client can hang during its initial ACK handshake. `prepare_hooks_build.py`
now applies this third layer after the verified EOF layer. Its patch, input and
output hashes are pinned under `hooks_layer.gdb_reconnect_fix`.
`plans/test_gdb_eof.py` compiles the real stub with both patches and exercises
the negotiated-mode and buffered-input reset. j9q's own build and its
binary/source hashes are retained with the qualification artifacts. Disabling
no-ACK negotiation makes this memory-heavy probe too slow for the bridge start
bound and is not the runtime fix.
The `baseline.json` hashes describe the historical source before these
layers. Keep them unchanged; the EOF fix records its final source hash separately.

The repository record selects the reconnect-corrected executable, SHA-256
`b7d870f9982b166a327ec0242aea73c3912190647fb0fae20f7f4bff252419c4`, with
`hooks_layer.binary_includes_gdb_eof_fix=true` and
`hooks_layer.binary_clears_gdb_breakpoints=true` and
`hooks_layer.binary_resets_gdb_negotiation=true`. The earlier EOF-only build at
`<SRC>/melonDS-hooks-eof/build/melonDS`, SHA
`f61efff2f20cf04844a43a847c73eaf63ff03c41fcf09e9655011384562d5ac0`,
clears breakpoints but retains negotiated no-ACK state on disconnect. The old executable at
`<SRC>/melonDS-hooks/build/melonDS` has the GDB EOF stub defect and must
not be used for GDB-attaching captures. Preserve it and the shared `build_info.json`.

The build steps below need the Linux build record (`build_info.linux.json`),
which is not part of this export: `prepare_hooks_build.py` and
`prepare_gpu_build.py` both read it.

To rebuild, choose an absent durable source directory and recreate it with
`prepare_hooks_build.py`; this verifies hooks, EOF and reconnect layers.
For example, with `HOOKS_SOURCE` set to that new directory and `TMPDIR` set to
private scratch, run:

```sh
python3 scripts/emu/native_media/prepare_hooks_build.py \
  --repository <SRC>/melonDS-lua --out "$HOOKS_SOURCE"
jobq run --nice 15 -- cmake -S "$HOOKS_SOURCE" -B "$HOOKS_SOURCE/build" \
  -DCMAKE_BUILD_TYPE=Release -DENABLE_GDBSTUB=ON -DUSE_QT6=ON -DCMAKE_PREFIX_PATH=""
jobq run --nice 15 -- cmake --build "$HOOKS_SOURCE/build" -j4
sha256sum "$HOOKS_SOURCE/build/melonDS"
```

The Linux build record (`build_info.linux.json`, not part of this export) pins
the layer hashes; `prepare_hooks_build.py` and `prepare_gpu_build.py` need it.
Keep the EOF patch and source pins above.
The batch runner that reads `hooks_layer.app_path` and `binary_sha256` from
the repository's Linux record is not part of this export.

The focused offline regression for these patches (it recreates the hash-checked
hooks source and compiles its GDB stub; no emulator runs) is not part of this
export either.

Nativewatch downgrades a GDB kill fallback to `WARNING` only when its hash-pinned
runtime build record names the running binary hash and asserts both fix flags.
Two bridge status reads one second apart must prove frame advance after the
kill. The cleanup record retains those hashes, flags, frame counts, and verdict
for crash recovery. A missing proof interrupts the attempt without credit.
Normal detaches and historical capture commands, delays, and timeouts stay
unchanged. Offline probes establish stub behavior only. Live capture coverage
must come from the retained campaign report. The pinned GPU binary was not
rebuilt and has both fix flags false, even though future GPU source recreation
inherits the corrected hooks source.

Request call logs and list walks with two extra `native_capture_start` arguments. With neither
argument, the hooks build writes exactly the files the replay build writes.

- `calls`: up to 64 ARM9 instruction addresses, even, in main RAM or ITCM.
  Whenever the interpreter is about to execute one of them, the hit is logged.
  This includes a conditional instruction whose condition then fails. The JIT
  bypasses the hook, and native capture already refuses JIT.
- `lists`: up to 4 list walks:
  `{address, offsets, next, limit, fields: [{path, length, optional}]}`.
  - The head is resolved the way a watch chain is: start at `address`, then for
    each entry of `offsets` read a pointer and add the entry. The word at the
    final address is the first node. A null hop marks the list absent.
  - From each node, follow the pointer at `node+next`, for at most `limit`
    (≤ 32) nodes.
  - Each field starts at `node+path[0]`. Every later `path` entry is a pointer
    hop plus an offset. A null hop on an `optional` field marks that field
    absent; on a required field it fails the capture with
    `required_list_field_absent`.
  - A nonzero pointer outside main RAM fails the capture with
    `list_pointer_unreachable`.
  - Limits: 16 fields and 128 bytes per node.

The logs are flushed per frame, before that frame's `frames.tsv` row is written.
`sequence` and `nds_frame` therefore equal the `frames.tsv` row of the frame in
which the hit or the read happened. All numbers are unsigned decimal.

| file | columns / content |
|---|---|
| `hooks.json` | `{"version":1,"call_pcs":N,"lists":M}` |
| `call-pcs.tsv` | `pc`, sorted |
| `calls.tsv` | `sequence nds_frame pc insn r0 r1 r2 r3 r4 r5 r6 r7 lr`, one row per hit in execution order. `insn` is the opcode at `pc` (16-bit in Thumb), so a reader can check which overlay was resident. Registers are their values before the instruction executes. |
| `lists.tsv` | `list address offsets next limit fields`, where `fields` is `path:length:optional` joined with `;` and `path` is comma-joined |
| `list-frames.tsv` | `sequence nds_frame list present count truncated head_path`, one row per frame per list. `head_path` holds `location:value` pairs for every head read; the last value is the first node. `truncated=1` means `limit` nodes were read and the next pointer was still nonzero. |
| `list-nodes.tsv` | `sequence nds_frame list node address next field_present field_addresses data_hex`, one row per node in walk order. `field_present` has one `0`/`1` per field. `field_addresses` holds each field's resolved address, or 0 when absent. `data_hex` is the fields' bytes in order, little-endian as stored, with absent fields zero-filled. |

`validate_capture.validate(..., calls=[pcs], lists=[recipes with names])`
checks all of these files. That includes frame alignment with `frames.tsv`, the
node links and the field presence rules. It returns `calls` (rows as ints) and
`lists[name]`, one walk per frame with decoded `nodes`. Fields of up to 4 bytes
decode as unsigned ints, and longer fields as byte lists. The hook-spec shot
list and call set used for traces are `SHOT_LIST` and `CALLS` in
`docs/research/feel-captures/2026-10-08-native-trace-hooks/plans/trace_capture.py`.

### Native GPU-media build: consumed OAM and clocks (fourth binary)

`native_media/native-gpu.patch` applies over the hooks source. It adds a
bounded GPU-media side stream, separate from the RAM watches (the 512-byte watch
limit and its validator are unchanged). It is pinned as `gpu_layer` in
`build_info.linux.json`, and `prepare_gpu_build.py --repository
<SRC>/melonDS-lua --out DIR` recreates the source exactly (it runs
`prepare_hooks_build.py`, applies the patch, checks every changed-file sha256
and that `NativeGpuMedia.h` equals the repo copy). The binary is
`<SRC>/melonDS-gpu-gdbfix/build/melonDS` (sha256 `3778de26…`, built
2026-10-28 over the hooks source with the GDB EOF, breakpoint and
reconnect fixes). The 2026-10-19 binary at `<SRC>/melonDS-gpu/` predates
those fixes; it stays on disk and is kept under `superseded`, and must not be
used for GDB-attaching captures. The hooks binary stays the default campaign
instrument. `NativeCapture.h` is not modified, because the replay
build record pins it.

Request the stream with `gpu = 1` among the `native_capture_start` hook
arguments (`native_capture.lua` passes `args.gpu`). Without it the build writes
exactly the hooks build's files; the 2026-10-19 live check found frames.tsv,
every PPM and audio.bin byte-identical with the stream on and off
(`docs/research/feel-captures/2026-10-19-vis-v2-oam-clocks/`).

What is recorded, and when (melonDS soft renderer, `GPU2D_Soft.cpp`):

- `obj` stream: at each `DrawSprites(line)` (run one line ahead, line 0 during
  VCount 262 of the previous `RunFrame`): the engine's OAM bank (1 KiB,
  including the affine filler words), its OBJ VRAM flat copy as 1 KiB pages
  (main 256, sub 128) and 12 sprite register bytes. These are the bytes that
  line's sprites are built from.
- `compose` stream: at each `DrawScanline(line)`: the standard OBJ palette
  (512 bytes), the OBJ extended palette (8 KiB) and 36 compose register bytes.
- post-frame: after `RunFrame`, both OAM banks and both palette RAM halves
  (4096 bytes) plus 18 register bytes.
- Line 0 of the first captured frame is drawn before the capture starts and is
  written as an explicit unobserved span. A missing or extra line, a wrong
  buffer size, an out-of-order line or a budget overflow fails the capture
  (`gpu_scanline_coverage`, `gpu_scanline_order`, `gpu_bad_observation`,
  `gpu_blob_overflow` at 128 MiB of unique blobs, `gpu_span_overflow` at 192
  spans per frame per stream).

Register layouts (little-endian):

| block | bytes |
|---|---|
| sprite (12) | `DispCnt`(4) `OBJEnable` `Enabled` pad(2) mosaic latch distance(4) = `(line - OBJMosaicLine) & 0xFF` |
| compose (36) | `DispCnt`(4) `LayerEnable` `ForcedBlank` `Enabled` `ScreenSwap`; `BlendCnt`(2) `BlendAlpha`(2) at 8; `EVA` `EVB` `EVY` `Win0Active` at 12; `Win0Coords`(4) at 16, `Win1Coords`(4) at 20, `WinCnt`(4) at 24; `Win1Active` at 28, `OBJMosaicSize`(2) at 29; `MasterBrightness`(2) at 32 |
| post (18) | `VRAMCNT`[9] `ScreenSwap` `DispCnt` A(4) `DispCnt` B(4) |

Files (all numbers unsigned decimal, hex only where named `_hex`):

| file | columns / content |
|---|---|
| `gpu-media.json` | `{"version":1,"frames","page_bytes":1024,"vram_pages":[256,128],"sprite_reg_bytes":12,"compose_reg_bytes":36,"post_reg_bytes":18}` |
| `gpu-blobs.bin` / `gpu-blobs.tsv` | unique byte blobs, deduplicated by exact bytes per kind; `blob kind offset length crc32`, kinds `oam`, `pal`, `extpal`, `page` |
| `gpu-vram-sets.tsv` | `set engine pages`: a full OBJ VRAM image as comma-joined page blob ids |
| `gpu-spans.tsv` | `sequence nds_frame engine stream first_line last_line observed oam vram_set pal extpal regs_hex`. Consecutive lines with identical inputs merge into one span; `-` marks a field the stream does not carry. |
| `gpu-post.bin` / `gpu-frames.tsv` | 4096 bytes per frame (OAM main, OAM sub, palette 0x000-0x3FF, palette 0x400-0x7FF); `sequence nds_frame post_crc32 post_regs_hex` |

`validate_capture.validate(..., gpu=True)` requires the files exactly when
asked for and rejects: a blob CRC mismatch, non-contiguous or unindexed blob
bytes, a duplicate blob, a wrong page count or kind, a post record count or CRC
mismatch (torn record), rows misaligned with `frames.tsv`, out-of-order spans,
a gap or overlap in lines 0-191, an unobserved span anywhere but sequence 0 obj
line 0, unmerged identical neighbours and a reference to the wrong blob kind.
It returns `gpu` with `frames[i]['spans'][(engine, stream)]`, `post_oam`,
`post_pal` and `blobs`. `gpu_vram(gpu, set)` rebuilds a VRAM image and
`gpu_phase(gpu)` gives per frame and engine `obj_spans`, `oam_versions`,
`compose_spans`, `line0_eq_prev_post` and `eq_post`.

Measured phase contract (koma men X / up+X, both facings, 3 repeats; detail
in the bundle README): one consumed OAM version per frame per engine; the OAM
consumed by frame N equals the post-frame OAM after frame N-1 on every observed
frame. Use consumed OAM, not post-frame OAM, as the display truth.

The reducer measures per OBJ palette bank. Bank 0's art changes exactly 2
frames after 10/19, 9/14, 10/19 and 10/15 of p1's RAM cell changes (four
trials). Its art changes at t=64 after the X idle cell (t=62) and state exit
(t=63). Gameplay state, RAM art cell, consumed OBJ and presented GX are
separate clocks. Bank 0 being the attacker is INFERRED, not measured: screen
order against RAM x, resting on one-bank-per-fighter and same-phase projection
premises. It is graded `inferred` only where a motion witness agrees (the
left-facing trials), else `unknown`. Every actor-attributed timing carries that
grade. The unattributed changes and all 3D-drawn art are unresolved.

The independent oracle is `oam_read.obj_layer` (see below) over the consumed
inputs, compared by exact RGB with the engine-A screen; misses whose 6-bit red
or blue is odd are attributed to the 3D layer (the 2D path cannot produce them
unblended). JUS draws the stage and much fighter art in 3D in front of the OBJ
layer, so the OBJ oracle covers only 2D-visible pixels. The rate scores
predicted pixels only, so a sprite missing from the prediction yields no
mismatch. `oracle_completeness` in the bundle reducer checks the composed
prediction for three cases: frames with no composed pixel, banks drawable in
the consumed OAM but not composed, and an absent attacker bank (only when
ownership is not unknown). It does not detect OAM the recorder never captured,
or partial omissions. Affine, bitmap and
mosaic OBJ entries are reported as unsupported rather than guessed.

### Pinned commit

`c26edf0e0d75364823856c9272a103fe39e03999` (see `build_info.json`).

### ROM/BIOS hashes

See `hashes.json`. No external BIOS/firmware dumps are needed — melonDS boots
JUS in DS mode with its built-in FreeBIOS.

| File | SHA-256 |
| --- | --- |
| ROM (`jus.nds`) | `a9c9bf89e6d99548b7c87e822b217c3fb74ef25186535b06193a6fb73d0d6d27` |
| Save (`jus.sav`) | `f2a794a9dcc2f34be76682c2377315d5f45bc8eeb95f725478c5f2cc31edb83b` |
| BIOS9 / BIOS7 / Firmware | not used (direct boot) |

The melonDS config lives at `~/Library/Preferences/melonDS/melonDS.toml` —
**Preferences**, not Application Support. `[JIT] Enable=false` matters: the GDB
stub can't run alongside the JIT recompiler.

## Our patches

`patches/joypad-set.patch` carries four changes to the fork. Regenerate it with
`cd $SRC_DIR && git diff > scripts/emu/patches/joypad-set.patch`.

1. **`joypad.set(table|nil)` / `joypad.get_committed()`** — button injection.
   The fork's `joypad` was read-only. `set(t)` overrides with `t` as the
   complete pressed set (physical input ignored), `set({})` forces neutral,
   `set(nil)` releases the override. `get_committed()` reads back the mask the
   core actually used — that's what you want for timing. The existing
   `joypad.get` reads the *physical* mask and doesn't reflect the override.
2. **`--lua-script <path>`** — the fork had **no** non-GUI way to load a Lua
   script (no CLI flag, no config key, no env var; the console is append-only).
   Without this flag, none of this tooling can run unattended.
3. **Fixed `Lua_ReadData` in `lua/libs/LuaMemory.cpp`.** Upstream reads bytes
   into the *high* end of an `s64`, so on a little-endian host `read_u8`
   returned `byte << 56` — e.g. 0xEE came back as `-1297036692682702848`. Now
   it shifts back down, arithmetically for signed types. The adjacent `isSigned`
   trait was also inverted (`((T)0-1 > 0)` is false for every 8/16-bit type
   after integer promotion, and true for `u32`), so `u32` reads sign-extended
   and `s8`/`s16` never did. Both fixed. `read_bytes_as_array` was always
   correct, which is why the selftest passed while `peek` returned garbage.
4. **Reset `flagStop`** in `createLuaState()`. Upstream never cleared it, so
   after one Stop-button press every later script was killed instantly — fatal
   for repeated unattended runs.

5. **`write-watchpoint.patch` — CPU write-watchpoints that actually fire.**
   The GDB stub acks `Z2` packets but never triggers them, and gdb's software
   fallback single-steps at ~2k instr/s (5 min per frame). This patch hooks
   `ARMv5::DataWrite8/16/32` in `src/CP15.cpp` instead. Set the env var
   **before** launching (the list is parsed once, so changing addresses means a
   relaunch with `--keep-ipc`):

   ```bash
   JUS_WATCH=0x0220C0CC,0x0220C0CE JUS_WATCH_LOG=/path/watch.log \
     bash scripts/emu/launch_emu.sh --keep-ipc
   ```

   Every write touching a listed address logs
   `[JUSWATCH] w16 addr=0220C0CC val=0000ED40 pc=0215AFB4 lr=...`. **`pc` is
   R15 at write time = the store instruction + 8 in ARM mode (+4 in Thumb)**,
   so `pc=0215AFB4` means the `strh` at `0x0215AFAC`. `lr` is whatever R14
   holds and is often a scratch register, not a return address. Interpreter
   only — the JIT bypasses these paths (JIT is already off in the config).
   Savestate loads and memclears show up as `01FF…` / `0205…` pcs; ignore
   them. This closed the weight hunt in one session
   (`docs/research/feel-captures/weight-hunt-2026-09-01c/`) and makes the
   `jus-fun` software-watchpoint plan moot.

Don't call `memory.usememorydomain`: it stores a pointer to a stack local. Pass
the domain string (`"ARM9 System Bus"`) per call instead.

## Verified behavior (spike findings)

**Lua runs on the GUI thread, not the emu thread, via a queued Qt connection**
(`EmuThread.cpp` emits `signalLuaUpdate`; `LuaConsoleDialog` lives on the GUI
thread with a default `AutoConnection`). Two consequences:

- One `_Update()` call is **not** one emulated frame. `agent_bridge.lua` drives
  plan progress off `emu.framecount()` deltas and logs the delta as `d` in every
  row so skipped frames are visible. Host load can produce `d > 1`; see
  `jus-bridge-elapsed-skip-u54n`.
  Reject affected timing evidence according to the capture protocol.
- `joypad.set()` writes and the core's mask commit happen concurrently — that's
  why the patch uses `std::atomic`.

`_Update()` also fires while the emulator is paused and during ROM boot, so any
logic gated on "a frame passed" must check `framecount`, not callback count.

**Savestates work and are portable across launches.** `state save` acks only
after the file size stabilizes and the sidecar is written; `state load` settles
by waiting for `framecount` to match the sidecar's `framecount_at_save`. A state
saved in one process loaded correctly into a fresh launch, restoring framecount
exactly.

Offline fixture staging must copy the archived `<name>.meta.json` from the
same revision as `<name>.mln.gz`. Validate its `sha256` against the decompressed
state and `gz_sha256` against the archive. Preserve the measured
`framecount_at_save`, `saved_at` and original save `session`; when relocating,
set `slot` to the destination basename. Write compact JSON without whitespace
after the `framecount_at_save` colon, as required by `read_sidecar` in
`agent_bridge.lua`. That reader consumes only the saved frame counter; the
producer writes all four fields. There is no neutral frame-counter value for
importing a state. A guessed value can load the bytes and still time out.
The nativewatch wrapper validates the provenance fields and binds the archived
sidecar and all staged files to its checkpoint identity. Its `.mln.sha256`
contains the full decompressed-state SHA as provenance; the Lua load path
does not read that hash file.

**Test-play crates (items): turn them off with one poke per load.** Four crates sit in every deck-maker test-play state, and new ones spawn every 300 frames. The rule bytes (`0x020AFEBB`, `+0x2A`/`+0x2D`/`+0x2F`) do not stop them, because ov6 caches the item count at load in the BattleMapItem manager. **Recipe (measured in all five test-play states, 1800 moving frames each):** after each state load, read the little-endian word at `0x02172988` (`P`) and poke the byte at `P+0x14C` to `00` (it reads 8 at load). Then free the crates already on the field once: each ColPrm record with `+0x3C == 0x08AFC200` and `+0x40 == 0x40000008`, poke `+0x40` to `0x209` (manager `0x0220DDC0` in test play). Freeing drops a short-lived record with the same signature that clears itself within 200 frames, so free before any 200+ idle frames (the regen-off sequence is 665). No re-free timer is needed. `docs/research/feel-captures/item-poke-2026-09-25/plans/nospawn.py` is the check (item-poke-2026-09-25, part 4).

The ColPrm manager's first word is its active-list head. It need not point to
record zero. In j9q's clean Train 596 setup, crate removal advanced it from
`0x0220E214` to `0x0220E834`, record 4. The retained state contains a consistent
forward/backward list through record 17. `fighter_layout.detect_layout` checks
that the head is an aligned member of the 128-record pool at manager `+0x454`,
stride `0x188`, alongside the local fighter pointer. It rejects a null head,
out-of-pool head, misalignment, and ambiguous layouts. The old record-zero
equality rejected this valid clean state. The raw three-word regression fixture
is `tests/train596-clean-layout.json`; the full state and list audit are retained
in the external j9q artifacts. Historical GDB probes that discover a manager
using the record-zero equality still need an explicitly validated manager passed
through `atns41_manager` and `atns41_manager_resolved` for this setup.

### Refreshing a batch of deck-dependent savestates

When the cartridge deck roster changes, refresh all measurement states from one
manifest instead of editing them individually. First save the deck in-game, then
run:

```bash
python3 scripts/emu/refresh_savestates.py scripts/emu/savestate_refresh.json
```

The command cold-boots one emulator session per manifest entry, selects the
listed deck number from a known first-row position, verifies every navigation
screen, reads the live `char+0x41` (`+0x29` in the player slot) roster, checks it
against the manifest, turns auto-heal off, and saves the named state. It stops on
the first roster mismatch; it does not silently produce a state for the wrong
deck. Add or remove entries in `savestate_refresh.json` when the measurement
set changes. Use `--keep-open` to leave the final battle running for inspection.

The `deck` value is the visible deck-list number. The `roster` values are the
runtime `chr_b` indices, not deck-builder row numbers or helper-passive IDs.
Keep the manifest's expected order identical to the active battle-character
order. The script owns and releases the emulator holder automatically, but it
still refuses to interfere with another live holder.

**Menu input granularity:** a **1-frame** press is exactly one menu step. A
4-frame hold triggers auto-repeat and moves two steps. Hold length is the
difference between reliable and unreliable navigation.

**Boot-to-battle input path** (all via `jusemu.py run`, no hand input):
`START` (skips the intro) → `LEFT` to Jアリーナ → `A` → three `DOWN` to
トレーニング → `A` → `A` (deck select) → `A` (stage select) → `START`
(rule screen, "バトルスタート").

**Screenshots:** `jusemu.py screenshot <out.png>` builds the C helper
`scripts/emu/tools/winid.c` with CoreGraphics/CoreFoundation and calls macOS
`screencapture` for the emulator window. It needs a C compiler and the host's
Screen Recording permission. It does not use AppleScript or PyObjC. Check the
saved image yourself; permissions on owner's machine do not establish permissions
on another developer's machine.

`jusemu.py screendump <out.bin>` reads the patched emulator framebuffer through
the bridge. Its raw RGB payload needs conversion before viewing. This avoids
macOS window capture, but does not establish Windows launch or IPC support.

### Harness hazards found 2026-09-03 (register)

Sources: runtime-report-3-lr-switch.md,
runtime-report-4-lr-switch-taikoubou.md,
runtime-report-5-states.md,
tracker item `jus-e2w4`.

- **`jusemu.py state save` overwrites the sidecar; it does not merge.** Any
  hand-added notes in a repo sidecar (`menu_saved`, `savestate_major`, roster
  comments) are lost on re-save. If they need to survive, re-add them by hand
  after copying the new `.mln`/`.meta.json` back — but the bridge's sidecar
  reader is a regex over `"framecount_at_save":(%d+)`, so any hand-edit must
  stay compact JSON with no space after the colon (`json.dump` defaults add
  one and will be silently rejected).
- **A load that comes back `ok:false` is not necessarily a failed load.** A
  sidecar-patched state (dummy `"framecount_at_save":0`) always acks
  `ok:false` with "state load did not settle", but the state genuinely
  loaded — confirm with the framecount and `[0x02181B28]`, never with the
  ack alone. A genuine failure looks the same on the ack, so always check
  those two reads afterward.
- **`refresh_savestates.py` uses `JUS_EMU_HOLDER` if it is exported**, and
  falls back to its own `codex-refresh-savestates-<pid>` name only if it
  isn't. With your own holder exported, the script will `stop_emu.sh` your
  own running instance as its first act — `stop_emulator` only refuses when
  the recorded holder *differs* from the one it's about to use. Stop your
  own emulator first if you have a holder exported.
- **`refresh_savestates.py` cannot pick a stage.** `build_steps` presses one
  bare `A` on `stage_select`, so anything it builds lands on the default J
  Arena stadium stage, never Dark Tournament. A Dark Tournament state still
  needs a hand save (or a manifest `stage` key, not yet implemented).
- **The input-history ring is the cheapest no-GDB arrival check.** A pressed
  button's flag shows up in the 4-entry ring at `0x023D6B00` (index
  `0x023D6B60`) 2 frames after the press and drains within ~4 frames of
  release; watch it before concluding an injected plan had no in-game effect.
- **Select is not a neutral filler input.** Pressing it moves the player
  object to state code `0x0c` and can shift its x position (~23 px measured).
  Use an empty button list `{"buttons": []}` for a genuinely neutral control
  segment, not a Select press.
- **The victim/opponent fighter object address is per-deck, not a constant.**
  Resolve it from the fighter table at `0x021DEB3C + 4` for every new state;
  hard-coding a previously-seen address (e.g. `0x02230D60`) will silently
  read a stale, inert object on a different deck.
- **Unused deck slots hold garbage `chr_b`** (118, 119, … — anything above the
  valid range). Gate any roster read on `chr_b <= 73`.

### Reading HP correctly

HP is a **16-bit little-endian value in 1/64 units**. The "1/4 scale" byte from
older notes is just its high byte. Read 2 bytes **at the address**, not at
`addr-1` — that older instruction is wrong and it silently returns the high byte
alone (38 rather than 9728, i.e. 0.594 rather than 152.000).

| slot | player | opponent |
|---|---|---|
| active (CURRENT HP) | `0x021DF1D4` | `0x021DF7F0` |
| deck 1/2/3 | `+0x50` each | `+0x50` each |

**These are CURRENT HP. Two bytes earlier is MAX HP and it is not what you
want** [`jus-reading-max-hp-not-current-2jo`]. The pair sits in the character
struct as `+0x16` max / `+0x18` current, so the addresses above are `+0x18`:

| field | player | opponent |
|---|---|---|
| max HP (`char+0x16`) | `0x021DF1D2` | `0x021DF7EE` |
| **current HP** (`char+0x18`) | `0x021DF1D4` | `0x021DF7F0` |

The two read **identically at full health**, so a max-HP read looks exactly like
a working measurement and stays perfectly stable while damage lands. That cost
four sessions of "no hits landing" which were charged to game behaviour, to
experiment design, and to another session's interference before anyone checked
the field. If HP is not moving, verify which of the two you are reading before
concluding anything about the game.

Nearby fields on the same struct, for orientation: `char+0x13..0x15` are the
three packed nature slots, `char+0x1A` the live ability count, `char+0x1B` the
ability ids, `char+0x41` the chr_b index, `char+0x49` the regen rate (poke to 0
to stop healing).

`displayed_HP = raw / 64`. Full write-up and measured damage values in
`docs/research/HP-And-Damage-Runtime-Findings.md`.

Two traps when measuring damage: **training mode heals to full within a few
frames**, so never diff before/after — log every frame and take the minimum of
the dip. And **facing decides whether an attack connects**; walking past the
opponent leaves you facing away, and every button whiffs.

## The in-battle training menu (press START) — read this before measuring damage

> **Which battles have this menu (corrected 2026-09-02).** On `fight_base` (J Arena
> training) a START press opens no menu at all. On the `pc-*` / `ds8t_*` Dark
> Tournament training states START opens the **J Arena pause menu**: バトル再開 /
> **COM設定** (なにもしない / 戦う / **ガード** / ジャンプ) / **自動回復** (ON/OFF) / リトライ /
> デッキセレクト / Jアリーナメニューにもどる. So the CPU-behaviour and auto-heal rows
> ARE reachable there, contrary to the older note (`jus-nature-menu-not-in-these-modes-43m`
> was about `fight_base`/`dm_battle`). 相手の属性 (opponent nature) is only in the
> deck-maker test-play menu below. Navigation is the same: DOWN/UP to move, A to
> cycle a value, START to resume. Three ready-made states with COM設定 = ガード are
> in the `jus_files` submodule's `save_states` directory
> (`pc-kenshin-{luffy,nami,franky}-guard`). With ガード
> the CPU stands still until the first hit lands, then holds guard until 122 frames
> pass without a blocked hit (physics.md §4.5). The row has a fourth value,
> ジャンプ (jump), after ガード; A wraps back to なにもしない. The values live in
> a RAM byte, listed below.

### Two state-identity RAM bytes (stage and COM)

Both are read from the savestate file by `state_identity.py` and checked by
`check_state.py` (found by A-3).
Evidence: 2026-10-09-a3-dt-states/RESULTS.md
(the stage and CPU rows of the identity table; `menu-bytes.json`, `plans/find_menu_bytes.py`).

| address | width | meaning | status |
|---|---|---|---|
| `0x020AFE9C` | u8 | J Arena stage-list index. **32 = 暗黒武術会会場 (Dark Tournament)**, 0 = the default J Arena stadium stage. The visible list position of Dark Tournament is 33 (1-based). Next to the rule bytes `0x020AFEBB..BD` (items, gimmick, team). | **verified** dynamically: 80 of the 83 dark-tournament-layout states in the store read 32; the 3 that read 0 were built on the default stage (`pc-raoh-npc-luffy-j-arena`, `ds8t_jj_battle_noheal`, `luffy_training`); choosing Dark Tournament in the stage list wrote 32 before the battle started. Deck-maker test play keeps the last J Arena pick here, so read it only in the dark-tournament layout. |
| `0x02181D1C` | u8 | The pause menu's COM設定: **0 なにもしない (idle), 1 戦う (fight), 2 ガード (guard), 3 ジャンプ (jump)**. | **verified** dynamically: cycling the row over two dumps per setting made this the only byte reading 0,1,2,3,0 outside UI scratch; on the store the three `pc-kenshin-*-guard` states read 2, both `fightcpu` states and `e1-cpu` read 1, the idle fixtures read 0. Its writer is **not** confirmed statically (below). |

Static check of the COM byte's writer (2026-10-09, `scripts/analysis/query.py`),
status **plausible, writer unresolved**: `xrefs-to 0x02181D1C` finds no direct
literal load. The byte is `0x1F4` past the fighter pointer `0x02181B28`, and
`0x2BC` past the ov11 pool base `0x02181A60`, but `pool-values` over the
`0x02180D1D..0x02181D1C` window finds 107 ov11 literal loads of 76 candidate bases, and
`search-imm` on each base-to-byte offset found no `ldrb`/`strb` in ov11 that pairs
with one of them (the byte hits fall in arm9 or in other overlays, so they are
unrelated structs). The menu code reaches the byte through a pointer or from an
overlay not yet mapped. To close this: break on write to `0x02181D1C` while cycling
the row in the pause menu.

### OAM entry reader (`oam_read.py`)

Reader step. The decoder is covered by synthetic-buffer tests
(`tests/test_oam_read.py`). The live main-engine OAM was measured against game state in
`docs/research/feel-captures/2026-10-18-p06-oam-map/` (Taikoubou and Train, 3-4 repeats each):

- Update (`docs/research/feel-captures/2026-10-18-p06c-fx-channel/RESULTS.md`): rendering channel identified: the effects in the two captured scenarios are drawn by the main 3D layer (BG0), class B drawables submitted as GX display lists, not OAM. Taikoubou object association is demonstrated for one summon/shot relationship and Train association is partial. Plans can carry `actions` (`poke`, `clrbits`, `scene`, `screendump`) for such probes, but only through a custom driver that is not included: `jus_plan.validate_plan` drops the `actions` key (`jus_plan.py:66,110`), so the regular plan interface does not support them yet.
- Historical (see the update above): this capture did not identify an FX/shot/summon channel in main OAM (it covers main OAM only: no sub OAM, BG or 3D;
  the OBJ-off probe was not saved). Whether a direct channel exists there is unresolved.
- Shadow OAM is `0x020A3C00` (manager `0x020A374C` + `0x4B4`; free-entry count at `0x020A3BF0`).
  Hardware OAM equals the shadow of the previous tick for 99.86 to 99.91 % of entries (pooled, dominated by unchanged
  entries). Among entries whose shadow changed, previous-only is 354/375, 172/197 and 299/330; the rest are current-only
  or neither (cause unresolved, not shown torn).
- A body part is placed at `x = floor(Qx) - cam + c(cell, part)`, `y = floor(Qy) + c(cell, part)`
  (`Q` = scene node world position at node `+0x0C/+0x10`, 20.12; `cam` = int word `0x020A5C68`).
  `Q` equals the collision element position exactly on Taikoubou; on Train the P2 origin mismatches at one tick per run
  (tick 162 in runs 1, 3, 4; tick 165 in run2; run2 `p1Q` x at tick 162 also differs from run1; unresolved). The residual is 0 for 97 to 99 % of visible entries
  (fitted and evaluated on the same rows); the rest are mostly cell-change ticks or part groups seen once, plus two
  unexplained `tkb_ywhit` tick-43 entries on a tick without a cell change.
- `jusemu.py peek`/`validate_watches` still refuse OAM; the bundle's `plans/p06_drive.py` adds the raw
  watch specs and a `load_state` plan start.

Pixel step (vis-v2): `obj_tile_offset(entry, dispcnt, tx, ty)` gives the OBJ VRAM byte offset of a tile (1D mapping
with the DISPCNT boundary shift, or 2D 32x32-tile rows), `obj_pixels(entry, dispcnt, vram, pal, extpal=None)` renders
one normal entry to `{(x, y): rgb555}` (flips, 4bpp banks, 8bpp standard or extended palette, screen wrap; `None`
for affine, bitmap or mosaic entries, `{}` for hidden ones), `obj_layer(oam, dispcnt, vram, pal, extpal, engine)`
resolves the front OBJ pixel per position (lower priority value, then lower index) and lists unsupported entries,
and `rgb555_to_rgb888` matches melonDS output expansion (green takes bit 15 as its low 6-bit bit). On live GPU-media
captures this reproduces the 2D-visible OBJ pixels (see the GPU-media build section for the measured rate).

Decodes the Nintendo DS sprite attribute memory: 128 entries of 8 bytes per
engine, 1 KiB each. Main engine OAM is `0x07000000`, sub engine OAM is
`0x07000400`. Entries 4n..4n+3 filler halfwords hold affine group n (PA, PB,
PC, PD, signed 8.8).

- `decode_oam(buf, engine)` returns 128 dicts per entry: `y`, `y_signed` (Y >= 192
  wraps negative), `x` (9-bit, sign-extended), `shape`, `size`, `width`, `height`
  (from the 12-entry shape/size table; shape 3 is prohibited and gives `None`),
  `rot_scale`, `hidden` (rot_scale 0 and bit 9 set), `hflip`/`vflip` for plain
  entries or `rotscale_param` for rot/scale entries, `tile`, `priority`,
  `palette`, `obj_mode`, `mosaic`, `color_256`, `affine_group`.
- `decode_affine(buf)` returns the 32 affine groups, each with `PA`/`PB`/`PC`/`PD`
  as floats and `*_raw` as the signed integer.
- `read_oam(peek, engine)` and `read_oam_buffer(peek, engine)` take any
  `peek(addr, n)`. The live path, `make_live_peek`, uses `jusemu.py dump` over
  the same IPC bridge as `projectile_census.py`. `jusemu.py peek` is not used
  because `jus_plan.validate_watches` refuses addresses outside main RAM.

```
python3 oam_read.py --engine main --json oam_main.json          # live bridge
python3 oam_read.py --engine sub --from-dump raw.bin --json o.json  # offline 1 KiB dump
```

Output JSON: `{"engine", "base", "source": "live"|"dump", "entries", "affine"}`.

## Known issues

- **A plan with `load_state` set stops the bridge.** Running a plan whose JSON
  has `load_state` kills the `_Update()` callback: the heartbeat freezes while
  the emulator keeps running at full speed, and nothing prints to the Lua
  console (so it's not a Lua error, and not the force-stop hook — that only
  fires when `flagStop` is set). Isolated by elimination: the same plan with the
  same 32-byte block watches runs fine once `load_state` is removed, and a
  standalone `state load` works repeatedly. **Workaround:** issue
  `jusemu.py state load <slot>` as its own command first, then run the plan.
  Root cause not yet found.
- Pointer chains through `0x023D2A74` resolve, but `+0x78` reads 0 in training
  mode where the notes expect `0x22` on the ground. Absolute addresses are
  reliable; treat chain-based watch specs as unverified.
- Window screenshots use the macOS helper described above; use the framebuffer
  dump for captures that do not need the host window.

## Combined Lua+GDB workflow

The G3 dry run proved one emulator launch, one GDB attach, a standalone
savestate load, a 2,020-frame Lua plan, four breakpoint captures, and an HP
positive control. See `docs/research/G3-HP-Delta-Dry-Run-Results.json`.

**The `paused` design works exactly as intended.** With `arm-none-eabi-gdb`
attached and the core halted, `jusemu.py status` reported:

```
"state": "paused",  heartbeat.state: "plan_running",  framecount frozen
```

That is the designed behavior: the heartbeat goes stale while the emulator
process stays alive, so the client infers `paused` rather than `dead`, and an
in-flight plan reads as frozen rather than failed. A running plan survived the
halt in exactly that state.

**The GDB stub does not survive a disconnect.** The first `target remote
localhost:3333` connects cleanly and `break *0x02078488` sets fine. After that
session ends (or is killed), every later connection fails during the handshake:

```
Ignoring packet error, continuing...
warning: unrecognized item "timeout" in "qSupported" response
Remote replied unexpectedly to 'vMustReplyEmpty': timeout
```

and the emulator stays halted, so the bridge is stuck at `paused` forever. The
only recovery found is relaunching the emulator.

Practical rules:

- **One GDB session per emulator launch.** Plan the whole debugging session
  before attaching; you don't get a second attempt.
- Load the first savestate before attaching GDB. For later probes, resume the
  target, issue a standalone `jusemu.py state load`, and confirm heartbeat
  health before arming the next breakpoint group.
- **A standalone savestate load with GDB attached works.** This lets one GDB
  session cover several battles. Keep state loading out of Lua plans.
- **`handle SIGILL ... pass` fails on this stub** ("Can't send signals to this
  remote system") and aborts the whole batch script. Use `nopass`.
- **A no-hit result is worthless unless the log shows the session stayed
  healthy.** Two of three attempts at one negative were invalid -- one where GDB
  detached on SIGILL, one where the script errored -- and both printed exactly
  the same "0 hits" as the valid run.

## Frame counting: the emulator free-runs

`nav.advance(N)` is accurate -- 2300 requested measured 2301 observed against the
emulator's own framecount, and it now RETURNS that observed delta.

The thing to watch is that **the emulator keeps running at ~60fps whenever no plan
is executing.** Three seconds of caller sleep costs 180 emulated frames. So any
framecount delta measured across your own dumps, screenshots or conversions
includes that free-run time. A reported 2300 -> 5310 "overshoot" was this: ~50
seconds of caller work between two reads, not plan error.

Use `nav.advance()`'s return value to attribute frames to a plan. Use a difference
of two emulator-reported framecounts to measure in-game duration -- that counts
free-run frames too, which is correct, since the game does not care where its
frames came from.

**The pause menu does not toggle on the frame START is pressed** (measured
2026-09-11 on `pc-ichigo-fy-vegeta`, tracker item `jus-puc7`): a START press at plan
frames 0-2 resumed the battle at frame 17, and a second press at frames 9-11
froze it at frame 21. Closing the menu costs ~16 frames, opening it ~11. A
`START` / N frames / `START` step plan therefore freezes the battle ~11 frames
*later* than its last plan frame. That matters for anything short-lived: one of
these projectiles is on the ObjShot active list for only ~22 frames (its `+0x18`
word counts down 19 -> 0), and one `jusemu.py dump` round trip costs roughly 5
free-run battle frames, so a scan-then-step loop will miss it. Watch the ObjShot
manager's 4-byte `+0x00` active-list head with `tail --every 1` to find the exact
spawn frame first, then aim a START press 11 frames ahead of the frame you want
frozen. `ichigo_y_capture.py` does exactly this.
- Because the halt freezes `_Update()`, the bridge cannot drive input while the
  core is stopped. Breakpoint commands must end in `continue` so the core keeps
  running and the bridge stays alive; a blocking prompt deadlocks the pair.
- Relaunch with `launch_emu.sh --keep-ipc` to recover without losing savestates.

The completed G3 experiment broke at `0x02078488`, landed scripted melee hits,
and captured `r1=0xFFFFFE80` with `lr=0x0215AC74` four times. Use
`scripts/gdb/run_experiments.py` for repeatable multi-probe sessions. Its format,
health checks, recovery behavior, and known-positive example are documented in
`scripts/gdb/README.md`.
