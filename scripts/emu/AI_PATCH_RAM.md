# Live RAM patching for the battle AI

**Tracker items:** `jus-oubd` (parent), `jus-kk1k` (A/B the pivot), `jus-qgiy` (decision
loop). Read
[cpu-ai-levels.md](../../docs/research/side-quests/cpu-ai-levels.md) for what the
bytes mean.

`ai_patch_ram.py` edits the AI **in the running emulator's RAM**, so a change is
visible in the next frame. No ROM rebuild, no patch file, and nothing to undo by
hand — reloading the savestate discards it. The on-disk ROM is never written.

## Why it works

ov11 is loaded from ROM to RAM at `0x02172A60`, so its code is live at its own
virtual addresses: a code edit is a poke at the address itself. The AI profile
is likewise already copied into RAM at `[AI+0x2C]` by the time a battle is
running, so a data edit pokes that live copy rather than `ai_param.bin`. The
addresses are derived at runtime from the battle root; nothing about the profile
row is hardcoded.

## Usage

```bash
cd <REPO>

# dry run: what would change, writes nothing
python3 scripts/emu/ai_patch_ram.py --set pivot --show

# apply, leave the emulator running
python3 scripts/emu/ai_patch_ram.py --set pivot

# back to stock (reloading the state discards every RAM edit)
JUS_EMU_HOLDER=<holder> python3 scripts/emu/ai_patch_ram.py --reload

# shut the emulator down
JUS_EMU_HOLDER=<holder> bash scripts/emu/stop_emu.sh
```

`--show` is only meaningful **together with `--set <tier>`**; a bare `--show`
reports nothing. The tool reads each target byte back before writing and
**refuses** if the live value is not the expected original — that is a signal
that the build is not the one the edit table was written against, not something
to bypass.

## Tiers

| `--set` | Address | Change | Effect |
|---|---|---|---|
| `pivot` | `0x0217ACE0` | `sub r0,r0,#5` → `#1` | The arming roll for the `0x0C` behaviour mode. At difficulty 5 this moves the threshold index 0 → 4, i.e. 25% → 65%. Predicted **2.6×** more arm events. |
| `active` | live profile | gate bytes → table index 3 | Lowest acceptance row → index 3 for the shipped archetypes. Deliberately **not** `≥ 8`: the gate arms its 30-tick cooldown only on failure, so "unconditional" also disarms the throttle. |

> **The percentages in the table above are thresholds out of 256, not measured
> probabilities.** The roll field has only two writers in ov11 and the per-frame
> callback never refreshes it, so its distribution is unestablished. Reason about
> threshold *indices*, not percentages. See
> [cpu-ai-levels.md §3.2, §3.10](../../docs/research/side-quests/cpu-ai-levels.md).
| `react` | `0x0217FDB0`, `0x0217E3E4` | `#0x5A`→`#0x14`, `#0x1E`→`#0x14` | Failure-only lockouts 90 → 20 and 30 → 20 frames. Shortening them cannot change *which* branch is chosen, only how soon the CPU may reconsider. |
| `gate` | `0x02179130` | `cmp r1,#0x1B` → `#0x19` | Revives the call site at `0x1A` that the gate early-outs. **Experimental**: the profile bytes it reads are not uniform across archetypes, so it fires at very different rates per character. |
| `all` | `pivot` + `react` | | |

## What has and has not been shown

Applied and read back on 2026-09-26: `pivot` (`0x0217ACE0` live-read as
`0xE2400001`, with the other three addresses still stock, and the ROM sha256
unchanged).

**No claim is made that any tier plays better.** Nothing here has been measured
for play quality; see the probe results
for what is and is not established, and `jus-kk1k` for the A/B that would settle
it.

## Gotchas the tool already handles

- **Never destroys the battle it is about to patch.** It attaches to a live
  bridge when one is already up; `launch_emu.sh` force-stops every melonDS and
  wipes the IPC directory, so calling it while a fight is running would kill it.
- **Rebuilds the IPC client after a launch.** The bridge stamps sessions with an
  epoch, so a client built before the launch would have every command rejected
  as stale.
- **Slot identity is checked, not assumed.** `u32(AI+0xD4) >> 28 == i`, and slots
  that are not constructed (`0xD4 == 0`, as 2 and 3 are in a 2-fighter battle)
  are skipped rather than read as stale memory.
- The node chain is dereferenced once so `[AI+0x20]->+0x18` can be watched past
  the bridge's 3-deep chain cap.
