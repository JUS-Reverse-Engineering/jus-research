# JUS GDB tools

Memory analysis and batch experiment tools for Jump Ultimate Stars using the
project's patched melonDS fork and GDB.

The full launcher and batch workflow is verified on macOS. The GDB command files use
`gdb-multiarch` on Linux, but the emulator launcher still needs porting. See
[`NOTES_FOR_LINUX.md`](../../NOTES_FOR_LINUX.md) before using this workflow on Linux.

## Build the required emulator

Do not use a packaged or upstream melonDS build for these tools. The project depends on
the pinned `NPO-197/melonDS-lua` fork and the patches under `scripts/emu/patches/`.

On macOS, install `arm-none-eabi-gdb`, then run the project build script:

```bash
brew install arm-none-eabi-gdb
bash scripts/emu/build_melonds_lua.sh
```

The script enables the GDB stub, installs the build dependencies, checks out the pinned
fork commit, and applies the local patches. See the [emulator tool guide](../emu/README.md)
for the patch set and current build constraints.

## Run a batch experiment

`compile_experiments.py` validates an experiment spec and writes one GDB
command file. `run_experiments.py` launches melonDS, loads each savestate as a
standalone `jusemu.py state load` command, attaches GDB once, and runs the
probes in order.

Compile the known-positive HP-delta probe:

```bash
JUS_EMU_HOLDER="$USER-g3-boot-$$" \
  python3 scripts/emu/boot_verified.py --slot g3_verified --runs 1

python3 scripts/gdb/compile_experiments.py \
  scripts/gdb/experiments/hp-delta-dry-run.json \
  --output /tmp/hp-delta-dry-run.gdb \
  --log /tmp/hp-delta-dry-run.log
```

Run it on macOS:

```bash
python3 scripts/gdb/run_experiments.py \
  scripts/gdb/experiments/hp-delta-dry-run.json \
  --compiled /tmp/hp-delta-dry-run.gdb \
  --log /tmp/hp-delta-dry-run.log \
  --results /tmp/hp-delta-dry-run-results.json \
  --holder "$USER-g3-hp-delta-$$" \
  --gdb arm-none-eabi-gdb
```

Use `--gdb gdb-multiarch` on Linux. Before a real experiment, run an attach
smoke test on that machine. The melonDS stub permits one GDB attach per launch.
`--holder` is required. Use a unique value for each orchestrator process. A live
HOLDER record cannot be bypassed, even by a caller that repeats its label.

Each probe specifies an `(overlay,address)` breakpoint, register or memory
captures, a savestate, a Lua plan, an expected hit count, and a positive
control. The compiler rejects Lua plans that contain `load_state`. A plan with
embedded state loading freezes the bridge.

Use a `plan_watch_change` positive control when the watched value can change
and recover before the plan ends. The HP dry run reads `hp_all.o1` from the
per-frame plan log, so auto-heal cannot hide a transient dip. Set
`timeout_seconds` when breakpoint traffic slows emulation below the ordinary
plan timeout. An optional GDB `condition` can filter a shared function before
the command list logs captures.

The generated GDB file enforces these session rules:

- `handle SIGILL stop nopass noprint` prevents the stub from trying to pass
  `SIGILL` to the remote target.
- Every breakpoint command list logs the experiment ID and ends in `continue`.
- `jus-arm-<probe-id>` disables every breakpoint before it enables the active
  probe.
- Session, probe, and hit markers separate log sections.

The supervisor preserves completed probe results if the stub disconnects. It
marks the current and later probes invalid and records `resume_from` as the
first probe to rerun after a new emulator launch. It does not resume
automatically. Preserve the failed result, create a reduced spec beginning at
`resume_from`, and use a new result path for the rerun.

The 2026-08-25 dry run is committed at
`docs/research/G3-HP-Delta-Dry-Run-Results.json`. It completed 2,020 frames,
captured four negative deltas at arm9 `0x02078488`, and observed opponent HP
change from 9,728 to 9,472 raw units. Every capture reported `r1=0xFFFFFE80`
and `lr=0x0215AC74`.

## Kit hit-trial probe (`kit_hit_probe.gdb`)

The contact probe for kit hit trials. It breaks at arm9 `0x020817EC` (every
contact), `0x0208182C` and `0x02081978`, and prints per contact the moveData
pointer, the authored base it is relative to (`[[node->ColPrm +0x6C]+0x0C]`),
the 20 record bytes, the node words (whose id word is `0x100 + rec`), the
contact's order within its frame (`n=`), the victim's staged pair
(`M+0x148` / `M+0x14A`) and the `M+0x16C` latch. The latch is the claim's
`hit_type_latch`: a u16 running max per frame of the hit-type byte (moveData[+1]),
cleared each frame at `0x02051864`. It is NOT hitstun frames, and a second same-frame
contact can show another record's type. A claim converter, which is not
part of this export, turns the log into `<move>_hit_record_<j>` claims. The
registers are in the probe's header. It replaces `c4_contacts.gdb` in a
driver's GDB launch; the committed Kakashi and Yusuke specials logs
(`c1`/`c4` probes, no `base=`, `h16c=` or `STAGE`) parse too.

Launch, from the repo root, after the emulator's GDB stub is listening on
`:3333` (the same way `c4.py gdb` does it; the driver sends `continue` after
each "Program received signal" and cuts the log into per-trial byte windows,
`*.marks.json`):

```bash
arm-none-eabi-gdb -q -nx \
  -ex "set logging file <out>/gdb/gdb-<epoch>.log" -ex "set logging redirect on" \
  -x scripts/gdb/kit_hit_probe.gdb
# wait for PROBE_ARMED in the log, then drive the trials
```

The hit-trial analysis step and its test are not part of this export.

## Connect GDB

### 1. Configure melonDS on macOS

Open melonDS, go to **Config → Emu Settings → Devtools**:

- ☑ Enable GDB stub
- ARM9 Port: `3333`
- ARM7 Port: `3334`

melonDS stores the macOS configuration at
`~/Library/Preferences/melonDS/melonDS.toml`. Confirm that the `Instance0.Gdb`
settings enable the stub on ARM9 port `3333`. Disable the JIT recompiler because the GDB
stub cannot run alongside it.

### 2. Load ROM

Start melonDS and load the JUS ROM. The game will run normally.

### 3. Connect GDB

```bash
# From the jus-research checkout
arm-none-eabi-gdb -x scripts/gdb/jus_gdb_watcher.py

# Or on Linux with gdb-multiarch
gdb-multiarch -x scripts/gdb/jus_gdb_watcher.py
```

Then in GDB:

```gdb
(gdb) target remote localhost:3333
```

The emulator will pause. Use `continue` to resume.

## Commands

### Basic Status

| Command            | Description                                     |
| ------------------ | ----------------------------------------------- |
| `jus-status`       | Show current battle state (HP, timer, special)  |
| `jus-check-hp`     | Show HP for you and opponent (active + deck)    |
| `jus-find-hp <n>`  | Search memory for HP value (to find addresses)  |
| `jus-addresses`    | List all known memory addresses                 |
| `jus-read-char N`  | Read player N's character state struct          |

### Watchpoints & Breakpoints

| Command                | Description                                        |
| ---------------------- | -------------------------------------------------- |
| `jus-watch-hp`         | Set watchpoints on all player HP addresses         |
| `jus-watch-code`       | Set breakpoint at health calculation function      |
| `jus-trace <addr> on`  | Log function calls at address with register values |
| `jus-trace <addr> off` | Stop tracing                                       |

### Memory Analysis

| Command                          | Description                                              |
| -------------------------------- | -------------------------------------------------------- |
| `jus-dump <start> <end> <file>`  | Dump memory region to file                               |
| `jus-scan <start> <end> <value>` | Search for byte value in range                           |
| `jus-snapshot <name> [region]`   | Save memory snapshot (regions: `battle`, `char`, `full`) |
| `jus-diff <snap1> <snap2\|now>`  | Compare two snapshots or snapshot vs current             |
| `jus-bt`                         | Backtrace with ARM9 offset translation                   |

### Hitstun/Velocity Research

| Command                                    | Description                                           |
| ------------------------------------------ | ----------------------------------------------------- |
| `jus-char-dump [player] [offset] [length]` | Dump character struct bytes with annotations          |
| `jus-char-snapshot <name> [player]`        | Save character struct snapshot                        |
| `jus-char-diff <snap1> <snap2\|now>`       | Compare char struct snapshots (find velocity/hitstun) |
| `jus-char-values <snap> [start] [end]`     | Show actual values in snapshot (not just diffs)       |
| `jus-compare-field <off> <snaps...>`       | Compare one field across multiple snapshots           |
| `jus-velocity-watch [player]`              | Show physics region values                            |

### Automated Triggers

The main working command for automatic capture:

| Command                                                | Description                                |
| ------------------------------------------------------ | ------------------------------------------ |
| `jus-auto-snapshot-on-damage <target> [prefix]`        | Capture when HP decreases (WORKS!)         |
| `jus-auto-snapshot-off`                                | Disable all auto-triggers + show summary   |

**Target options:**

| Target              | Description                        |
| ------------------- | ---------------------------------- |
| `me` / `player` / `1` | Your active character            |
| `2-4`               | Your deck members (supports)       |
| `opp` / `enemy` / `o1` | Opponent's active character     |
| `o2-o4`             | Opponent's deck members            |

**Examples:**

```gdb
jus-auto-snapshot-on-damage me goku       # Track damage to your character
jus-auto-snapshot-on-damage opp enemy     # Track damage to opponent
```

**Important notes:**

- HP is stored in **1/64 units** (160 displayed HP = 10240 raw)
- The damage code fires constantly during idle, but the command filters to only
  capture when HP actually decreases.
- Use `jus-check-hp` to see current HP values for both sides.

**Broken with melonDS** (these use GDB hardware watchpoints, which the melonDS stub acks but never fires — use the fork's `JUS_WATCH` env var instead, see `scripts/emu/README.md` patch 5):

| Command                         | Status                          |
| ------------------------------- | ------------------------------- |
| `jus-auto-snapshot-on-hit`      | ❌ Uses watchpoints, fails      |
| `jus-auto-snapshot-on-state`    | ❌ Uses watchpoints, fails      |
| `jus-auto-snapshot-on-status`   | ❌ Uses watchpoints, fails      |

### Manual Capture Commands

These require manual continue/Ctrl+C between captures (stepi doesn't work with melonDS):

| Command                                         | Description                    |
| ----------------------------------------------- | ------------------------------ |
| `jus-burst-snapshot <count> <prefix> [player]`  | Capture one, then c/Ctrl+C     |
| `jus-baseline-noise <player> [count] [prefix]`  | Capture one, then c/Ctrl+C     |

### Velocity Logging (Lightweight Alternative)

Instead of capturing full 288-byte snapshots, you can log just the physics
region values:

| Command                          | Description                              |
| -------------------------------- | ---------------------------------------- |
| `jus-velocity-log <player> [file]` | Log physics offsets when HP decreases  |
| `jus-velocity-show [last_n]`     | Show velocity log entries                |
| `jus-velocity-clear`             | Clear velocity log                       |

This logs offsets 0x006A-0x007E (likely velocity), 0x0078 (ground/air state),
and 0x0098-0x009A (timer region) each time damage is taken.

### Snapshot Management

| Command                      | Description                              |
| ---------------------------- | ---------------------------------------- |
| `jus-snapshot-list [prefix]` | List all snapshots with metadata         |

### Noise filtering

Before analyzing combat data, capture baseline "noise" to identify timer fields:

| Command                                              | Description                                |
| ---------------------------------------------------- | ------------------------------------------ |
| `jus-baseline-noise <player> [count] [prefix]`         | Capture one idle snapshot per invocation |
| `jus-baseline-timed <player> [count] [prefix]`       | Capture idle state (continue-based)        |
| `jus-find-timers <prefix>`                           | Identify always-changing fields (timers)   |

Fields that change during idle time are timers/counters - **not** physics data.
After running `jus-find-timers`, these offsets are marked `[TIMER - ignore]` in
diff output.

Run `jus-baseline-noise` once, continue the game, wait, and press Ctrl+C. Invoke the
command again with the same arguments to capture the next snapshot. Repeat until it
reports that the requested count is complete, then run `jus-find-timers`.

### Binary Dump Scripts

For detailed analysis, use the standalone GDB scripts:

```gdb
# Dump deck builder memory to /tmp/jus_dumps/
source scripts/gdb/dump_deck_binary.gdb

# Dump to named subdirectories for comparison
source scripts/gdb/dump_deck_named.gdb
dump-state1    # saves to /tmp/jus_dumps/state1/
dump-state2    # saves to /tmp/jus_dumps/state2/
```

Then analyze with Python:

```bash
python scripts/analyze_deck_dump.py --dir /tmp/jus_dumps/state1
python scripts/analyze_deck_dump.py --diff /tmp/jus_dumps/state1/deck_0a1000.bin /tmp/jus_dumps/state2/deck_0a1000.bin
```

## Workflows

### Finding What Changes During an Attack

```gdb
(gdb) target remote localhost:3333
(gdb) continue
# Start a battle in-game, then Ctrl+C to pause

(gdb) jus-snapshot before
# Resume, do ONE attack, Ctrl+C again
(gdb) continue
# ... do attack ...
# Ctrl+C

(gdb) jus-diff before now
# Shows all bytes that changed
```

### Tracing Damage Calculation

```gdb
(gdb) jus-watch-hp
(gdb) continue
# Attack an enemy, GDB breaks when HP changes

(gdb) jus-bt          # See call stack
(gdb) info registers  # See CPU state
(gdb) x/20i $pc-20    # Disassemble nearby code
```

### Logging Function Calls

```gdb
# Log every call to health code with arguments
(gdb) jus-trace 0x020784FC on
(gdb) continue

# Output shows R0-R3 (function arguments) and LR (return address)
# TRACE 0x020784fc: R0=021df1a0 R1=0000000a R2=00000002 R3=00000000 LR=0207a234
```

### Finding Velocity/Position Fields

```gdb
(gdb) target remote localhost:3333
(gdb) continue
# Start a battle, have character stand still, Ctrl+C

(gdb) jus-char-snapshot idle 1
# Resume, have character walk right, Ctrl+C
(gdb) continue
# Ctrl+C when walking

(gdb) jus-char-snapshot walking 1
(gdb) jus-char-diff idle walking
# Fields that changed are likely velocity X or position X
```

### Capture baseline noise first

Before analyzing combat data, identify timer fields that always change:

```gdb
# Start battle, have both characters STAND STILL
(gdb) jus-baseline-noise 1 5 idle
# Captures idle_0
(gdb) c
# Wait about one second, then press Ctrl+C
(gdb) jus-baseline-noise 1 5 idle
# Captures idle_1. Repeat continue, pause, and capture through idle_4.

# Analyze which fields change during idle time
(gdb) jus-find-timers idle
# Output shows always-changing fields (these are timers, not physics)
# Example:
#   +0012: 1234 -> 1235 -> 1236 ...  (frame counter)
#   +0054: 100 -> 99 -> 98 ...       (animation timer)

# Now these fields will be marked [TIMER - ignore] in future diffs!
```

`jus-baseline-noise` does not advance the emulator. You must continue and pause the game
between invocations. If `jus-find-timers` reports no changes, increase the time between
captures.

### Finding Hitstun/Knockback Fields

> Superseded (2026-09-02): the victim hitstun timer is confirmed at `hit+0x114`
> (s16, 8.8 fixed frames, in the per-victim hit-result block), not in the
> `+0x0098-0x00BA` region hunted below - see `docs/confirmed-facts/physics.md`
> §4.5 [`jus-9lp.2.2`].

```gdb
# Start battle, position characters, Ctrl+C before getting hit
(gdb) jus-char-snapshot before_hit 1
(gdb) continue
# Get hit with a known attack (light vs heavy)
# Ctrl+C while in hitstun

(gdb) jus-char-snapshot in_hitstun 1
(gdb) jus-char-diff before_hit in_hitstun
# Look for:
#   - Velocity fields (large signed values ~100-500)
#   - Hitstun timer (countdown values 5-15 for light, 10-30 for heavy)
# Timer fields from baseline are marked [TIMER - ignore]
```

### Comparing Weight Classes

```gdb
# Test same attack on different weight characters
# Raoh (heavy) vs Lenalee (light)

# 1. Set up: Raoh gets hit by Goku's B
(gdb) jus-char-snapshot raoh_before 1
(gdb) continue
# ... get hit ...
(gdb) jus-char-snapshot raoh_hit 1
(gdb) jus-char-diff raoh_before raoh_hit

# 2. Set up: Lenalee gets hit by same attack
(gdb) jus-char-snapshot lenalee_before 1
(gdb) continue
# ... get hit ...
(gdb) jus-char-snapshot lenalee_hit 1
(gdb) jus-char-diff lenalee_before lenalee_hit

# Compare velocity values - Lenalee should have higher knockback velocity
```

### Using Automated Triggers (Recommended!)

The manual Ctrl+C approach has a focus problem - you can't control the game AND
the terminal simultaneously. Use the damage-based trigger instead:

```gdb
# Connect and get into a battle first
(gdb) target remote localhost:3333
(gdb) continue
# ... start a 1v1 battle, then Ctrl+C to set up triggers ...

# Track when YOU take damage
(gdb) jus-auto-snapshot-on-damage me mychar
(gdb) continue

# ... play the game, get hit multiple times ...
# Snapshots are captured automatically in background!
# You'll see: [AUTO] Snapshot 'mychar_dmg1' captured (player_active HP: 160 -> 148, dmg: 12)

# When done, Ctrl+C to analyze
(gdb) jus-auto-snapshot-off
(gdb) jus-char-diff mychar_dmg1 mychar_dmg2
```

### Tracking Opponent Damage

```gdb
# Track when OPPONENT takes damage
(gdb) jus-auto-snapshot-on-damage opp enemy
(gdb) continue

# ... attack the opponent ...
# You'll see: [AUTO] Snapshot 'enemy_dmg1' captured (opponent_active HP: 160 -> 140, dmg: 20)

(gdb) jus-auto-snapshot-off
```

### Burst Snapshots for Movement Analysis

```gdb
# Capture sequence during movement (manual continue/Ctrl+C between each)
(gdb) jus-burst-snapshot 5 walking 1
# Captured: walking_0 (1/5)
(gdb) c
# (wait, Ctrl+C)
(gdb) jus-burst-snapshot 5 walking 1
# Captured: walking_1 (2/5)
# ... repeat ...

(gdb) jus-char-diff walking_0 walking_4
# See position/velocity change over time
```

## Known Addresses

### Deck Builder State

| Address      | Size | Description                                       |
| ------------ | ---- | ------------------------------------------------- |
| `0x020A0C98` | 1    | Deck state flag (0x05=has leader, 0x07=no leader) |
| `0x020A2289` | 1    | Leader boolean (1=leader set, 0=no leader)        |
| `0x020A4368` | 4    | Pointer to leader koma data (0 if no leader)      |
| `0x020AFEB4` | 4    | Active deck slot index (0-7)                      |
| `0x020B9480` | -    | Koma master table (sequential 4-byte IDs)         |

### Battle State (RAM)

| Address      | Size | Description     |
| ------------ | ---- | --------------- |
| `0x021DEA71` | 1    | Battle timer    |
| `0x021DF731` | 1    | Special meter 1 |

### HP Addresses

HP is stored as a **16-bit fixed-point value in 1/64 units** (160 displayed = 10240 raw).
Current HP lives at the even addresses below (little-endian u16); the old +1 addresses
were the HIGH byte of MAX HP and read identically at full health (fixed 2026-08-23).

**Your side:**

| Address      | Description                    |
| ------------ | ------------------------------ |
| `0x021DF1D4` | Your active character HP       |
| `0x021DF224` | Your deck slot 1 (support/tagged out) |
| `0x021DF274` | Your deck slot 2               |
| `0x021DF2C4` | Your deck slot 3               |

**Opponent side** (0x61C offset from your side):

| Address      | Description                    |
| ------------ | ------------------------------ |
| `0x021DF7F0` | Opponent active character HP   |
| `0x021DF840` | Opponent deck slot 1           |
| `0x021DF890` | Opponent deck slot 2           |
| `0x021DF8E0` | Opponent deck slot 3           |

Deck slots are spaced 0x50 apart. Use `jus-check-hp` to see all values at once.

### Character State Struct (offsets from pointer)

**Confirmed offsets (from Action Replay codes + GDB testing 2026-02-03):**

| Offset    | Description                                        |
| --------- | -------------------------------------------------- |
| `+0x0078` | Ground/Air state (0=air, 0x22=ground, **0xC0=LAUNCHED/HITSTUN**) |
| `+0x0088` | Positive status ID                                 |
| `+0x00A0` | Negative status flags                              |
| `+0x00D9` | Jump counter                                       |
| `+0x00DA` | Air action counter                                 |
| `+0x0102` | Defense timer                                      |

**Timer region (discovered 2026-02-03):**

These fields decrement in a -5/-3 alternating pattern during hitstun/recovery.
They appear to be 32-bit countdown timers read as 16-bit pairs:

| Offset Pair     | Description          |
| --------------- | -------------------- |
| `+0x0098/0x009A` | Timer pair 1        |
| `+0x00A0/0x00A2` | Timer pair 2 (overlaps negative_status) |
| `+0x00A8/0x00AA` | Timer pair 3        |
| `+0x00B0/0x00B2` | Timer pair 4        |
| `+0x00B8/0x00BA` | Timer pair 5        |

**Physics/combat data region:**

| Region        | Description                                       |
| ------------- | ------------------------------------------------- |
| `+0x006A-0x007C` | Shows large deltas during knockback - possible velocity |
| `+0x0070-0x0092` | Near ground_air - state/physics data             |
| `+0x0098-0x00BA` | Timer region - countdown timers during hitstun   |

> Superseded (2026-09-02): the victim hitstun timer is confirmed at
> `hit+0x114`, not in this `+0x0098-0x00BA` span - see
> `docs/confirmed-facts/physics.md` §4.5 [`jus-9lp.2.2`].

Total struct size: at least 0x120 bytes (~288 bytes)

### Code Hooks

| Address      | Description                 |
| ------------ | --------------------------- |
| `0x020784FC` | Health calculation function |

## Tips

- **Ctrl+C** in GDB pauses the emulator
- **continue** (or just `c`) resumes
- **stepi** steps one ARM instruction
- **x/10i $pc** disassembles 10 instructions at current position
- Snapshots use regions to avoid dumping all 4MB of RAM:
  - `battle` = `0x021D0000-0x02200000` (battle state, default)
  - `deck` = `0x020A0000-0x020C0000` (deck builder, menu state)
  - `save` = `0x020B0000-0x020C0000` (currency, unlocks)
  - `koma` = `0x02280000-0x022A0000` (koma holder during deck building)
  - `char` = `0x021DF000-0x021E0000` (character data in-battle)
  - `full` = `0x02000000-0x02400000` (all main RAM, slow)

## Known Limitations

### Wifi Pointers Don't Work in Offline/Training Mode

The character state pointers (`player1_state_ptr` at `0x021E2A7C` etc.) were
extracted from **wifi mode** cheat codes and contain **invalid data** in
training or offline battle modes:

```
(gdb) x/1xw 0x021E2A7C
0x21e2a7c:  0xe8100842   # NOT a valid 0x02xxxxxx pointer
```

This means `jus-read-char`, `jus-char-snapshot`, and other commands that use
these pointers will fail to capture meaningful data in offline modes.

**Investigation Status (JUS-98z):**

**SOLUTION FOUND (2026-02-03):**

> Caveat added 2026-09-02: this chain resolves, but `+0x78` reads 0 in
> training mode where these notes expect `0x22` on the ground. Treat
> chain-based watch specs as unverified; absolute addresses are reliable -
> see `scripts/emu/README.md:291-293`.

The working pointer chain for offline/training mode is:
```
0x023D2A74 (alt_state_base) -> read dword -> +0x10 -> character struct
```

**Recommended commands:**

| Command                          | Description                              |
| -------------------------------- | ---------------------------------------- |
| `jus-read-char-offline`          | Read char state using working pointer chain |
| `jus-snapshot-offline <name>`    | Take snapshot using working pointer chain |
| `jus-snapshot-at <name> <addr>`  | Take snapshot from direct address        |

**Example workflow for offline mode:**
```gdb
(gdb) jus-read-char-offline           # View current state
(gdb) jus-snapshot-offline standing   # Take snapshot while standing
(gdb) c
# (jump, Ctrl+C while in air)
(gdb) jus-snapshot-offline jumping    # Take snapshot while jumping
(gdb) jus-char-diff standing jumping  # Compare the two
```

### Opponent State Pointer (JUS-nqp)

**SOLUTION FOUND (2026-02-03):**

The opponent uses a **different pointer chain** than the player:

```
PLAYER:   0x023D2A74 -> intermediate -> +0x10 -> player struct
OPPONENT: 0x023D2A74 -> intermediate -> +0x00 -> ptr -> +0x10 -> opponent struct
```

The intermediate structure at `alt_state_base` contains:
- `+0x00`: Pointer to another struct (follow +0x10 for opponent)
- `+0x10`: Direct pointer to player struct

**Opponent commands:**

| Command                        | Description                              |
| ------------------------------ | ---------------------------------------- |
| `jus-read-opponent`            | Read opponent state using pointer chain  |
| `jus-snapshot-opponent <name>` | Take opponent snapshot                   |

**Example workflow for analyzing opponent:**
```gdb
(gdb) jus-read-opponent                # View opponent's current state
(gdb) jus-snapshot-opponent opp_idle   # Snapshot while opponent idle
(gdb) c
# (opponent jumps, Ctrl+C while in air)
(gdb) jus-snapshot-opponent opp_jump   # Snapshot while opponent jumping
(gdb) jus-char-diff opp_idle opp_jump  # Compare states
```

**Ground/Air state values (updated):**

| Value  | State              |
| ------ | ------------------ |
| `0x00` | Air (jumping/rising) |
| `0x02` | Fast fall (down+jump in air) |
| `0x22` | Ground             |
| `0xC0` | Launched/Hitstun   |

### Hardware Watchpoints Not Supported

The melonDS GDB stub does not properly support hardware watchpoints. Commands
that use watchpoints (`jus-auto-snapshot-on-hit`, `jus-auto-snapshot-on-state`,
`jus-auto-snapshot-on-status`) will fail with errors like:

```
Hardware watchpoint 1: *0x21dea71
Python Exception <class 'RuntimeError'>: Breakpoint 0 is invalid.
```

**Workaround for "who writes this address":** don't use GDB at all. The fork
has a CPU-side write hook — launch with `JUS_WATCH=0xADDR,... JUS_WATCH_LOG=file`
and every store logs `pc` (= instruction + 8 in ARM) and value. See
`scripts/emu/README.md` patch 5 and the worked chain in
`docs/research/feel-captures/weight-hunt-2026-09-01c/`. Use GDB execution
breakpoints afterwards, at the PC the watch named, to read registers.

**Workaround for snapshots:** `jus-auto-snapshot-on-damage`, which uses a
regular breakpoint at the damage calculation function.

### stepi Doesn't Work Reliably

The melonDS GDB stub crashes or hangs when executing large `stepi` counts. The
`jus-baseline-noise` and `jus-burst-snapshot` commands now require manual
continue/Ctrl+C between captures instead of automatic stepping.

### HP Memory Layout

The battle has separate addresses for **active characters** (currently fighting)
and **deck slots** (supports, tagged out characters):

- **Your active** + **Your deck 1-3**: Starting at `0x021DF1D4`, spaced 0x50 apart
- **Opponent active** + **Opponent deck 1-3**: Starting at `0x021DF7F0`, spaced 0x50 apart
- **Offset between sides**: 0x61C (1564 bytes)

HP values are stored as a **u16 in 1/64 of displayed value**:
- 160 HP displayed = 10240 raw (u16 at the even address)
- 128 HP displayed = 8192 raw

Use `jus-check-hp` to see all HP values, or `jus-find-hp <value>` to search for
specific HP values in memory.

## Troubleshooting

**"Connection refused"**

- Make sure melonDS GDB stub is enabled
- Check the port number (default 3333)
- Try restarting melonDS

**"Remote connection closed"**

- melonDS may have crashed or closed
- Try a different ARM9 port in melonDS settings

**GDB hangs on connect**

- The ROM might not be loaded yet in melonDS
- Load the ROM first, then connect GDB

**Emulator silently freezes right after a hand-written GDB script attaches**
(found 2026-09-10, `jus-hitbox-priority-clash-1evz.1`)

- `target remote` halts the ARM9 CPU the instant it connects. If your `.gdb`
  script only does `break ...` / `commands ... continue end` and never issues
  a bare `continue` after the last breakpoint is armed, the CPU stays halted
  forever — the script just sits at an idle `(gdb)` prompt. Nothing in-game
  moves, framecount stops advancing, and `jusemu.py status` reports
  `"state": "paused"` (its `PAUSED` value means "heartbeat stale, GDB has the
  CPU stopped" — not the in-game pause menu). Fix: end the script with a
  top-level `continue` right after the last `break`/`commands` block, e.g.
  see `scripts/gdb/experiments/projectile-conflict-nodes.gdb`.
  `compile_experiments.py`/`run_experiments.py` handle this for you; a
  hand-rolled script does not.
- If you run `arm-none-eabi-gdb -x foo.gdb` backgrounded with `&` under a
  harness/CI shell, GDB reads EOF on stdin almost immediately and detaches
  ("error detected on stdin" / "[Inferior 1 (Remote target) detached]") —
  breakpoints get pulled mid-session. Keep stdin open with a never-ending
  pipe: `tail -f /dev/null | nohup arm-none-eabi-gdb -q -x foo.gdb > out.log
  2>&1 &`.
- **The melonDS GDB stub tolerates exactly one clean attach per emulator
  launch.** If a previous GDB session on the same emulator process was
  killed (e.g. `pkill -f arm-none-eabi-gdb`) instead of cleanly detaching, or
  detached due to the stdin-EOF issue above, the *next* `target remote` on
  that same launch hangs: you'll see `Ignoring packet error, continuing...`
  followed eventually by `Remote replied unexpectedly to 'vMustReplyEmpty':
  timeout`, and no breakpoints get set. There is no in-session recovery —
  `bash scripts/emu/stop_emu.sh --force` and relaunch
  (`scripts/emu/launch_emu.sh`) to get a fresh stub, then attach GDB exactly
  once and keep it attached for the whole capture.
- **Operator note (observed 2026-09-12, `jus-ce7u`):** the same hang happens
  even after a *clean* detach, not only after a killed or stdin-EOF-dropped
  session — a same-launch GDB reattach produced no artifact, just the
  `qSupported`/"Ignoring packet error" hang above with no breakpoint ever
  reached. One clean attach per launch is the rule, full stop; don't try to
  save a launch by reattaching.

## See Also

- `docs/design/archive/ARM9-Analysis-Pipeline.md` - Full analysis pipeline documentation
- `docs/research/Cheat-Code-Analysis.md` - Memory addresses from cheat codes
- `scripts/archive/jus_watcher.lua` - Archived alternative for Windows/DeSmuME users (superseded by this GDB watcher)
