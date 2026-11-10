# Complete character state struct map (historical, February 2026)

> Kind: Superseded. The current [in-battle character state reference](../Character-State-Struct.md) retains the init-copy table. This archive preserves the February 2026 map verbatim.

---

## Complete Struct Map (historical, February 2026)

> ⚠️ **2026-08-26 REFUTATION — read before citing any physics/timer row.**
> The "Physics/Velocity Region" (`+0x6A–0xBA`), the `+0x78` hitstun flag, and
> the "Countdown Timer Region" (`+0x98–0xBA`) below are **not established as
> character-struct fields**. Static cross-check found the same offset cluster
> initialized by `JPower_Add` (0x110-byte JPower record), and an independent
> pass on the actual combat entity found collision bookkeeping (32-bit flag
> word at `+0x78`, geometry pointers, min-distance accumulator) — no position
> or velocity fields in `+0x60..+0xC0`. Character velocity fields remain
> unlocated; the hitstun timer was found 2026-09-02 at `hit+0x114` in the
> per-victim hit-result block `0x02230D60`, not here (physics.md §4.5,
> `jus-9lp.2.2`). The behavioral observations from the 2026-02-03
> session stand; the field map does not. See
> [findings/physics-region-identity-refuted.md](../findings/physics-region-identity-refuted.md)
> (tracker item `jus-physics-region-identity-refuted-68d9`).

| Offset              | Size | Name                        | Research Status   | Notes                                                                                                                        |
| ------------------- | ---- | --------------------------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **0x0000 - 0x003F** | 64   | ~~Physics Region~~          | ❌ **DISPROVEN**  | Old hypothesis (X/Y position + velocity in first 64 bytes). 2026-02-03 GDB session showed physics deltas live at +0x006A-0x00BA instead. |
| 0x0000 - 0x003F     | 64   | Unknown                     | ❓ Unknown        | Purpose unknown (NOT position/velocity)                                                                                       |
| **0x0040 - 0x0069** | 42   | Unknown                     | ❓ Unknown        | Gap before physics/velocity region                                                                                             |
| **0x006A - 0x00BA** | 81   | **Physics/Velocity Region** | Feb-2026 guess, refuted     | 2026-02-03 GDB: fields `+0x006A/6C`, `+0x0072/74`, `+0x007A/7C` show large deltas during knockback. Exact velocity field not yet isolated. **REFUTED 2026-08-26** - see banner above; this is not the character struct. |
| **0x0078**          | 1    | **Ground/Air/Hitstun State**| AR-derived, Feb 2026      | `0x00` = In Air, `0x22` = On Ground, `0xC0` = **Launched/Hitstun** (state FLAG, not a timer; 2026-02-03 GDB)                   |
| **0x0079 - 0x0087** | 15   | Unknown                     | ❓ Unknown        | Within physics region - might contain fall velocity or air physics                                                             |
| **0x0088**          | 1    | **Positive Status ID**      | AR-derived, Feb 2026      | `0x00` = Nothing, `0x09` = Invincibility (visual only?)                                                                        |
| **0x0089 - 0x0097** | 15   | Unknown                     | ❓ Unknown        | Gap before countdown timer region                                                                                              |
| **0x0098 - 0x00BA** | 35   | **Countdown Timer Region**  | Feb-2026 guess, refuted     | 2026-02-03 GDB: timers at `+0x0098/9A`, `+0x00A0/A2`, `+0x00A8/AA`, `+0x00B0/B2`, `+0x00B8/BA`. Decrement in -5/-3 alternating pattern (32-bit values read as 16-bit?). Run during hitstun/recovery. **REFUTED 2026-08-26** - see banner above; the hitstun timer is `hit+0x114`, not here. |
| **0x00A0**          | 1    | **Negative Status Flags**   | AR-derived, Feb 2026      | Bit flags for negative status effects (immune to negative status cheat). NOTE: overlaps timer region above - needs reconciliation. |
| **0x00BB - 0x00D8** | 30   | **Combat State Region**     | 🔍 **CANDIDATE**  | Remaining unknown region - possibly attack frame counter, guard state                                                          |
| **0x00D9**          | 1    | **Jump Counter**            | AR-derived, Feb 2026      | Number of jumps remaining (infinite jumps cheat)                                                                               |
| **0x00DA**          | 1    | **Air Action Counter**      | AR-derived, Feb 2026      | Number of air actions remaining (infinite air actions cheat)                                                                   |
| **0x00DB - 0x00F1** | 23   | Unknown                     | ❓ Unknown        | Gap between air actions and defense timer                                                                                      |
| **0x00F0 - 0x0101** | 18   | **Timer Region**            | 🔍 **CANDIDATE**  | Around defense timer - might contain other timers (stun, guardstun, etc.)                                                      |
| **0x0102**          | 1    | **Defense Duration**        | AR-derived, Feb 2026      | Defense timer (defense never wears cheat). **Most likely the guard gauge** `obj+0x102` of the ov6 fighter object (`0x02230D60` block, guard-sp.md §0.5): a cheat that pins it at 0 makes the guard never break. Revised 2026-09-02 (`jus-defense-duration-vs-guard-gauge-bclp`, `jus-fighter-object-identity-c56i`) after the fighter object was identified: its `+0x88`/`+0xA0` are read as status id / status word and `+0xD9..+0xDB` as jump/air state, matching this table's AR offsets. The first poke test (`feel-captures/defdur-2026-09-02/`) had assumed the ColPrm scratch `H` was the AR struct because `H+0x78` is `0x22`; that was the only match, and `H+0x102` never moved. Open mismatch: `obj+0x78` stayed `0x00` through standing, walking and jumping, so the `+0x78` row below may be a transcription error. |
| **0x0103+**         | ?    | Unknown                     | ❓ Unknown        | Struct continues beyond 0x102 (exact size unknown)                                                                             |

---

## Known Fields Detail

### Ground/Air/Hitstun State (`+0x0078`)

| Value  | Meaning              | Source                            |
| ------ | -------------------- | --------------------------------- |
| `0x00` | In Air               | "Always on Ground/Air" cheat code |
| `0x22` | On Ground            | "Always on Ground/Air" cheat code |
| `0xC0` | Launched/Hitstun     | 2026-02-03 GDB session            |
| `0x20` / `0x02` | launch frame / landing frame | `feel-captures/guardbreak-2026-09-02/` `gb-jump3` (this byte is `H+0x78` on the ColPrm scratch block, not the fighter object; see the AR base note above) |

**Research Notes:**

- Single byte field
- Changes when character jumps or lands
- `0xC0` (192) is a state FLAG indicating launched/hitstun, NOT a timer
  (confirmed 2026-02-03 GDB session)
- Used by `jus-auto-snapshot-on-state` trigger

### Positive Status (`+0x0088`)

| Value  | Meaning                      | Source                            |
| ------ | ---------------------------- | --------------------------------- |
| `0x00` | No positive status           | "Have Positive Status" cheat code |
| `0x09` | Invincibility (visual only?) | "Have Positive Status" cheat code |

**Research Notes:**

- Single byte field
- May encode buffs, invulnerability states
- Other values unknown - need testing

### Negative Status Flags (`+0x00A0`)

| Value     | Meaning                         | Source                                 |
| --------- | ------------------------------- | -------------------------------------- |
| Bit flags | Various negative status effects | "Immune to negative status" cheat code |

**Research Notes:**

- Single byte field (bit flags)
- May encode debuffs, hitstun, stun states
- Bit meanings unknown - need testing

### Jump Counter (`+0x00D9`)

| Value | Meaning                   | Source                      |
| ----- | ------------------------- | --------------------------- |
| 0-255 | Number of jumps remaining | "Infinite Jumps" cheat code |

**Research Notes:**

- Decrements on each jump
- Resets on landing?
- Used to enforce jump limits

### Air Action Counter (`+0x00DA`)

| Value | Meaning                         | Source                            |
| ----- | ------------------------------- | --------------------------------- |
| 0-255 | Number of air actions remaining | "Infinite Air Actions" cheat code |

**Research Notes:**

- Decrements on air attacks/dashes
- Resets on landing?
- Used to enforce air action limits

### Defense Duration (`+0x0102`)

| Value | Meaning                 | Source                           |
| ----- | ----------------------- | -------------------------------- |
| 0-255 | Defense timer countdown | "Defense never wears" cheat code |

**Research Notes:**

- Timer that decrements while defending
- When reaches 0, defense ends?
- Exact behavior unknown
- **Probably the guard gauge** (`obj+0x102`, guard-sp.md §0.5), revised 2026-09-02 (`jus-defense-duration-vs-guard-gauge-bclp`, `jus-fighter-object-identity-c56i`). See the table row above.

---

## Candidate Regions for Research

### ~~1. Physics Region (`0x0000 - 0x003F`)~~ - DISPROVEN

**Old hypothesis:** Contained position and velocity data in the first 64 bytes.

**DISPROVEN (2026-02-03 GDB session):** Movement/knockback snapshots showed no
physics deltas in this range. Physics/velocity data lives in the
`+0x006A - 0x00BA` region instead (see below).

### 1. Physics/Velocity Region (`0x006A - 0x00BA`) - LIKELY

**Finding (2026-02-03 GDB session):** Fields `+0x006A/6C`, `+0x0072/74`, and
`+0x007A/7C` show large deltas during knockback.

**Still open:**

- Exact velocity field not yet isolated (light vs heavy comparisons showed
  differences, but position/timing variations made isolation difficult)
- Which fields are position vs velocity vs derived values

**GDB Commands:**

```gdb
jus-char-dump 1 0x60 0x60      # Dump physics/velocity region
jus-velocity-watch 1           # Monitor physics region
jus-baseline-noise 1 5 idle    # Filter timer noise first
```

### 2. Air Physics Region (`0x0070 - 0x0088`)

**Hypothesis:** Contains fall velocity or air-specific physics near ground/air
state (overlaps the physics/velocity region above)

**Research Strategy:**

- Compare snapshots: ground idle vs air falling
- Look for values that correlate with fall speed
- May contain vertical velocity when airborne

**GDB Commands:**

```gdb
jus-auto-snapshot-on-state 1 air_physics
# Jump/land to trigger snapshots
jus-char-diff air_physics_state1 air_physics_state2
```

### 3. Countdown Timer Region (`0x0098 - 0x00BA`) - NOT THE HITSTUN TIMER

> **2026-09-02:** the victim hitstun timer is `hit+0x114` (s16, 8.8 frames;
> jab 20, guard break 60) in the hit-result block `0x02230D60` (physics.md
> §4.5, `jus-9lp.2.2`). During a launch this region reads −1. Whatever these
> fields are, they are not the stun clock.

**Finding (2026-02-03 GDB session):** Contains countdown timers that run
during hitstun/recovery:

- Fields: `+0x0098/9A`, `+0x00A0/A2`, `+0x00A8/AA`, `+0x00B0/B2`, `+0x00B8/BA`
- Decrement in a -5/-3 alternating pattern (suggests 32-bit values read as
  16-bit halves)
- Heavier characters (Raoh) show longer timer activity than lighter (Nami)

**Still open:**

- Which specific timer controls hitstun vs recovery vs other states
- Mapping of jpower hitstun values to timer initial values
- Reconciling with the known Negative Status Flags byte at `+0x00A0`

**GDB Commands:**

```gdb
jus-auto-snapshot-on-hit 1 combat
# Take damage to trigger
jus-char-diff combat_hit1 combat_hit2
```

### 4. Timer Region (`0x00F0 - 0x0101`)

**Hypothesis:** Contains additional timers near defense timer

**Research Strategy:**

- Compare snapshots: different combat states
- Look for values that decrement over time
- May contain: guardstun timer, stun timer, recovery timer

**GDB Commands:**

```gdb
jus-char-dump 1 0xF0 0x20      # Dump timer region
jus-baseline-noise 1 5 idle    # Identify timer noise
```

---

## Research Workflow

### Step 1: Baseline Noise Filtering

**Goal:** Identify timer fields that change even when idle (noise to filter out)

```gdb
# 1. Get into battle, have characters stand still
# 2. Capture baseline snapshots
jus-baseline-noise 1 5 idle

# 3. Identify timer fields
jus-find-timers idle

# Result: Fields that always change are timers - ignore these in physics analysis
```

### Step 2: Velocity Discovery

**Goal:** Find position and velocity fields

```gdb
# 1. Capture snapshots during movement
jus-burst-snapshot 10 walking 1

# 2. Compare first and last snapshot
jus-char-diff walking_0 walking_9

# 3. Look for fields with large deltas (position) or consistent changes (velocity)
# Filter out timer fields identified in Step 1
```

### Step 3: Hitstun/Knockback Discovery

**Goal:** Find hitstun timer and knockback velocity

```gdb
# 1. Set up automated capture on hit
jus-auto-snapshot-on-hit 1 hit

# 2. Resume game and take damage
continue

# 3. Compare snapshots before/after hit
jus-char-diff hit_hit1 hit_hit2

# 4. Look for:
#    - Timer that appears/disappears (hitstun)
#    - Velocity spike (knockback)
#    - Status field changes
```

### Step 4: Status Field Decoding

**Goal:** Understand status flag meanings

```gdb
# 1. Watch status changes
jus-auto-snapshot-on-status 1 status both

# 2. Resume game, trigger various status effects
continue

# 3. Analyze snapshots to correlate status values with game state
jus-char-diff status_positive1 status_positive2
```

---

## Struct Size Analysis

**Minimum Size:** `0x102` bytes (258 bytes) - based on highest known offset

**Likely Size:** `0x120` bytes (288 bytes) - common struct alignment, matches
GDB dump size

**Maximum Size:** Unknown - may extend beyond 0x120

**Evidence:**

- Known offsets scattered: 0x78, 0x88, 0xA0, 0xD9, 0xDA, 0x102
- Large gaps suggest struct is not densely packed
- May contain padding or reserved fields

---

## Memory Access Pattern

### Local Battle Mode

- Direct memory addresses (e.g., `0x021DF1D5` for Player 1 HP)
- Character struct may be at fixed addresses

### Wifi Battle Mode

- Pointer-indirect access
- Base pointers at: `0x021E2A7C`, `0x021E2A80`, `0x021E2A84`, `0x021E2A88`
- Character struct accessed via: `[pointer] + offset`

**Example (Player 1, wifi mode):**

```python
ptr = read_dword(0x021E2A7C)  # Get character struct pointer
ground_state = read_byte(ptr + 0x0078)  # Read ground/air state
```

---

## Related Documentation

- `../Cheat-Code-Analysis.md` - Source of known offsets
- `scripts/gdb/jus_gdb_watcher.py` - GDB tools for struct research
- `Combat-Mechanics-Reference.md` - Game mechanics context, **archived/historical**
- `docs/confirmed-facts/physics.md` - current physics/knockback/hitstun facts
- `docs/confirmed-facts/guard-sp.md` - current guard/SP gauge facts

---

## Research Status Summary

Historical; the counts that stood here were hand-maintained and are gone. Current
field knowledge is in `confirmed-facts/physics.md` §5 and the init-copy table above.

**Next Steps:**

> Superseded (2026-09-02): steps 1 and 2 below target the `+0x006A-0x00BA` region, which the
> 2026-08-26 refutation banner above says is not a character-struct region at all (it is
> `JPower_Add`'s record and collision bookkeeping). Character velocity fields remain unlocated;
> the hitstun timer is `hit+0x114` in the per-victim hit-result block, not here. See
> `docs/confirmed-facts/physics.md` §4.5 [`jus-physics-region-identity-refuted-68d9`].

1. ~~Isolate the exact velocity fields within `+0x006A - 0x00BA`~~ (region refuted, see above)
2. ~~Map jpower hitstun values to the `+0x0098 - 0x00BA` countdown timers~~ (region refuted, see above)
3. Reconcile Negative Status Flags (`+0x00A0`) with the timer region overlap
4. Decode status flag bit meanings

---

_Last updated: 2026-09-04 (fact review). Current measurement tooling: `scripts/emu/`._
