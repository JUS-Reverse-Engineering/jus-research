# Harness docs

How to measure — the agentic melonDS harness, the melonDS-lua fork, and GDB session
tooling. Game findings do not live here (trust rule: see `../README.md`); the code
itself is in `scripts/emu/` (see `scripts/emu/README.md`).

| Doc | What it covers |
|---|---|
| `Menu-Nav-Verified-From-Pixels.md` | Screen-verified boot-to-battle navigation; the framebuffer `screendump` path |
| `RE-Session-Playbook.md` | Strategies for human+LLM RE sessions (GDB diffing, experiment design) |
| `2026-08-14-melonds-agent-control.md` | Plan for agent control of melonDS |
| `2026-08-14-melonds-agent-control-design.md` | Design spec for the same |

Historical procedures live under [`archive/`](archive/). The
[Phase-1 GDB guide](archive/Phase1-GDB-Guide.md) and its HTML rendering describe the
superseded July 2026 workflow.

## Operational rules (folded from project memory, 2026-08-21)

- **Never click/focus the melonDS-lua window after a savestate load** — it can freeze
  the emulator in a permanent SIGSEGV-handler loop that looks like a pause. Focus it
  BEFORE loading a state; sample the process before killing a beachball.
- **Savestates in `/tmp/jus_emu/states` DO survive a stop/relaunch cycle** — relaunch
  is cheap recovery.
- **Pressing Start skips the opening intro** — needed by scripted boot-to-battle.
- **The emulator is a single shared resource guarded by HOLDER.** Start it through
  `scripts/emu/launch_emu.sh` with a unique `JUS_EMU_HOLDER`. The launcher refuses
  to replace another live holder's process. Record the holder in every measurement's
  provenance block.
