# Notes for moving the melonDS harness to Linux

## Status: ported and verified on Fedora 44 (GNOME/Wayland), 2026-10-08

- `build_melonds_lua.sh` builds on Linux. It checks the distro dependencies and
  prints the `dnf` command if any are missing. The binary is `build/melonDS`.
- `launch_emu.sh` and `stop_emu.sh` default to the Linux binary path. On Linux,
  `stop_emu.sh` matches the melonDS executable by argv[0] only.
- `jusemu.py screenshot` is macOS-only and says so. Use `jusemu.py screendump`,
  which reads the framebuffer in-core and needs no window or focus.
- melonDS config lives at `~/.config/melonDS/melonDS.toml`. Let melonDS write
  it on first launch, then set `[Instance0.Gdb] Enabled = true`. A hand-written
  partial file crashes its TOML serializer. JIT is off by default.
- Fedora's stock `gdb` handles ARMv5TE. Symlink it as `arm-none-eabi-gdb`
  (the name `run_experiments.py` defaults to), or pass `--gdb gdb`.
- Verified: bridge heartbeat, `jusemu.py status`/`selftest`, `screendump`, and
  GDB attach on :3333 reading ARM9 memory.

The rest of this file is the original porting plan.

The emulator driving setup under `scripts/emu/` was built and tested on macOS
(Apple Silicon, Homebrew). This is what's involved in bringing it over.

## Straightforward to port

- **Language runtimes come from `mise.toml`** — `mise install` gives you the
  same Python, Lua 5.4, JDK 21, and CMake on either OS. Only C libraries and
  GUI apps below need the distro's package manager.
- Build deps for the pinned melonDS-lua fork (`scripts/emu/build_melonds_lua.sh`):
  swap Homebrew for your distro's package manager — `pkg-config`,
  `qt6-base`/`qt6-multimedia` dev packages, `sdl2`, `libarchive`, `enet`,
  `zstd`, `libfaad2`. Caveat: the build script still hardcodes Homebrew
  `lua@5.4` paths — point it at the mise-provided Lua (or distro lua5.4 dev
  headers) when reworking it for Linux.
- `ENABLE_GDBSTUB=ON` and `USE_QT6=ON` CMake flags carry over unchanged.
- The GDB stub control plane and the file-based IPC bridge (`/tmp/jus_emu/`)
  are plain POSIX — no changes needed.
- `jusemu.py` is Python stdlib-only and fine as-is, except for the
  screenshot/window-finding piece below.

## Needs rewriting — not optional

- **Screenshots and window-finding are 100% macOS.** `jusemu.py`'s
  `melonds_window_id()` shells out to a custom `scripts/emu/tools/winid.c`
  linked against CoreGraphics/CoreFoundation, and `do_screenshot()` calls the
  macOS `screencapture` CLI. Neither exists on Linux. Replace with an X11 (or
  Wayland) equivalent: `xdotool`/`wmctrl` to find the melonDS window by
  *owning process*, not title — there's a comment in the code documenting a
  past bug where title-matching grabbed the terminal window instead of the
  emulator, because the terminal's title happened to contain "melonDS" — plus
  something like `maim`/`scrot`/`import` (ImageMagick) that can capture an
  occluded window by ID the way `screencapture -x -o -l <wid>` does.
- `build_melonds_lua.sh` writes `app_path` in `build_info.json` pointing at a
  `.app/Contents/MacOS/melonDS` bundle. A Linux build produces a plain binary
  at a different path — update the build script and anything that reads
  `app_path`.
- Read through `scripts/emu/launch_emu.sh` and `scripts/emu/stop_emu.sh`
  before relying on them — they also showed up when grepping for
  macOS-specific bits (`darwin`, `osascript`, bundle paths), and likely
  encode process/window assumptions that don't hold on Linux.

## One known bug that's macOS-specific and is now fixed

There's a documented incident
where focusing the melonDS window after a savestate load froze the emulator.
Root cause: the Lua fork ran state loads on the Qt UI thread, and
`ARMJIT::Reset` left that thread with JIT pages write-enabled (Apple Silicon
`pthread_jit_write_protect_np`), so Qt's own PCRE2 JIT faulted on focus and
melonDS's fault handler recursed on a null thread-local. Fixed by
`scripts/emu/patches/lua-savestate-on-emu-thread.patch`. The write-protect
toggle is Apple-only, so the fault itself won't reproduce on Linux, but the
patch's other two parts (state load on the emu thread, null check in the
handler) are correct everywhere.

Don't take that as "window focus is now safe," though — test it. Linux
Qt/X11 has its own set of focus-related crash patterns that could bite in a
different way. Input to a live emulator instance also needs coordinating across sessions
regardless of OS.

## Ghidra / PyGhidra layer (see docs/design/archive/Ghidra-And-Batch-GDB-Plan.md, Phase G0)

The static-analysis additions are deliberately portable:

- **Ghidra itself is Java** — on Linux, download the release zip from
  https://ghidra-sre.org instead of the Homebrew cask (Ghidra is not in the
  mise registry). The JDK it needs comes from `mise install` — no distro JDK
  required. Everything else is identical.
- **The Ghidra project directory is never committed.** Rebuild it on the new
  machine by running `scripts/ghidra/import_project.sh` — nothing to copy over.
  The script header records the Ghidra/JDK versions it was written against.
- `scripts/ghidra/scripts/*.java` (G0 seeding + smoke tests) and
  `scripts/gdb/compile_experiments.py` and `scripts/gdb/run_experiments.py` are
  plain Java and Python. The batch generator and supervisor need no OS-specific
  changes. The emulator launch and screenshot code still needs the porting work
  above.

### Batch GDB experiments

Use `arm-none-eabi-gdb` on macOS and `gdb-multiarch` on Linux. The generated
command file is portable, but the executable name is not. Run an attach smoke
test on each OS before you trust a batch. Confirm that the log contains
`JUS_SESSION_READY`, that a breakpoint command captures registers, and that the
Lua bridge resumes after the command list's `continue`.

The supervisor starts `scripts/emu/launch_emu.sh`, so its current macOS melonDS
path remains the Linux blocker. Once the launch script can find the Linux
binary, the rest of the sequence uses Python, GDB commands, and the file-based
IPC directory.

### Install learnings (G0, on this Mac)

- **Ghidra here is a Homebrew *formula* (Cellar/ghidra/…), not the cask** — there is
  no `Caskroom` path. Find `analyzeHeadless` at
  `Cellar/ghidra/<ver>/libexec/support/analyzeHeadless`. `import_project.sh`
  locates it robustly (Cellar, then Caskroom glob, then PATH); don't hardcode a
  Caskroom glob. On Linux point it at your unzipped
  `ghidra_*/support/analyzeHeadless`.
- **NTRGhidra is NOT used.** It loads the whole ROM with overlays at their real
  addresses, which recreates the same-address collision (ov00–ov08 all map onto
  one address range) and has no release pinned to Ghidra 12.1.3. The chosen
  topology is **one Ghidra Program per binary** (BinaryLoader), so addresses never
  collide; (overlay,address) → owning-program is recorded in the script header and
  resolved by the G1 query layer for cross-program xrefs.
- **analyzeHeadless returns exit 0 even when a postScript throws or analysis times
  out.** The importer therefore greps the build log for the script's own
  machine-readable `SMOKE_*_OK/FAIL` markers and the `Analysis timed out at` log
  line, rather than trusting the exit code.
- **Python 3 headless scripts** (PyGhidra) and Java `postScript`s both work in
  Ghidra 12.1.3; G0 uses Java `GhidraScript`s for the two-phase	seed (run on a
  `-noanalysis` import so the TMode context set doesn't conflict with existing
  ARM disassembly) + analyze flow.
- **Same-address overlays are smoke-tested.** The smoke suite includes an
  explicit ov5/ov6 distinct-bytes check (both base 0x0214CD20): it asserts the
  raw bytes at 0x0214CD20 and 0x021700E0 differ between the two programs, and
  that the byte just past ov5's end (0x02172280) exists in ov6 only — each
  program holds its own copy of the shared address range, proving the
  per-program topology resolves the collision.
- **arm9 entry 0x02005080 is seeded explicitly as ARM** (`SeedThumb` arg 2),
  so the true entry is a recorded, forced TMode=0 function rather than an
  implicit ARM-by-default. (Ghidra's default language mode is ARM, so this is
  belt-and-braces, but it pins the entry in the seeding record.)
- Version pin: Ghidra 12.1.3 + JDK temurin-21 (both pre-verified by
  `import_project.sh`'s preflight). Unpinned trio = incompatible; edit the trio in
  the script header together.

## Suggested order of attack

1. Rewrite `winid.c` + `do_screenshot()` first — until that works you can't
   see what the emulator is doing at all.
2. Get the build working (package substitutions, fix `app_path`).
3. Re-verify `launch_emu.sh` / `stop_emu.sh`.
4. Re-test the window-focus-after-savestate-load sequence specifically —
   don't assume it's fixed just because the macOS root cause doesn't apply.
