#!/usr/bin/env python3
"""pb6n1_spinit_run.py -- jus-pb6n.1. Drives a fresh boot through
scripts/emu/boot_verified.py's navigation into a battle, with
scripts/gdb/pb6n1_spinit.gdb attached from before the top menu is even
reached, so the SP max-bar/current-bar initialiser (arm9 0x02077610) is
caught live during the menu -> battle transition instead of being missed
by a savestate that already starts mid-battle.

Same GDB session idiom as scripts/analysis/cancel_run.py (GdbSession,
jusemu(), attach_commands()'s `set logging redirect on` BEFORE `enabled
on`, detach before quit) -- imported directly rather than re-implemented,
per that module's own precedent (scripts/analysis/atns2_sound_run.py does
the same). Unlike cancel_run.py's Runner, there is no savestate to load
before attaching here: a cold ROM boot already satisfies "state load
before attach" trivially (there is no state), so GDB attaches to the
just-launched, unpaused title screen and scripts/emu/boot_verified.py's
`boot()` then drives the whole menu sequence while GDB free-runs
`continue`-ing in the background, exactly like cancel_run.py's Runner
drives plans while its per-frame probe free-runs.

Usage:
    python3 pb6n1_spinit_run.py --holder H --raw-log /tmp/jus_emu/pb6n1_batch1.log \\
        --slot pb6n1_batch1_reached
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "analysis"))
sys.path.insert(0, str(ROOT / "scripts" / "emu"))
import cancel_run  # noqa: E402
import boot_verified  # noqa: E402

GDB_SCRIPT = ROOT / "scripts" / "gdb" / "pb6n1_spinit.gdb"
LAUNCH = ROOT / "scripts" / "emu" / "launch_emu.sh"


def launch(holder):
    env = os.environ.copy()
    env["JUS_EMU_HOLDER"] = holder
    subprocess.run(["bash", str(LAUNCH)], cwd=ROOT, env=env, check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holder", required=True)
    parser.add_argument("--gdb", default="arm-none-eabi-gdb")
    parser.add_argument("--raw-log", required=True)
    parser.add_argument("--slot", required=True,
                        help="savestate slot name to save the reached battle as")
    parser.add_argument("--no-launch", action="store_true",
                        help="assume the emulator is already up (skip launch_emu.sh)")
    args = parser.parse_args(argv)

    raw_log = Path(args.raw_log)
    raw_log.parent.mkdir(parents=True, exist_ok=True)
    if raw_log.exists():
        raw_log.unlink()

    if not args.no_launch:
        launch(args.holder)

    gdb = cancel_run.GdbSession(args.gdb, str(GDB_SCRIPT))
    base = None
    boot_error = None
    try:
        for command, wait in cancel_run.attach_commands(raw_log):
            gdb.command(command, wait=wait)
        # `set logging enabled on` is sent with wait=False (attach_commands'
        # own convention -- once redirect is on, its prompt is redirected
        # too, so there is no stdout prompt left to wait for).
        time.sleep(0.3)
        gdb.drain()
        gdb.command("continue", wait=False)

        print("GDB attached and armed (pb6n1_spinit.gdb); driving "
              "boot_verified.boot(%r)..." % args.slot)
        try:
            base = boot_verified.boot(args.slot)
            print("boot() reached a verified battle, character array 0x%08X" % base)
        except Exception as exc:  # noqa: BLE001 -- report, don't hide
            boot_error = exc
            print("boot() FAILED: %s" % exc)

        # Let a few more frames free-run so any post-battle-load SPINIT
        # calls (e.g. the opponent's slot, if it lands after the player's)
        # land in the log too.
        time.sleep(1.0)
        gdb.drain()
    finally:
        gdb.close()

    lines = raw_log.read_text(encoding="utf-8", errors="replace").splitlines() \
        if raw_log.exists() else []
    tagged = [l for l in lines if l.startswith(("SPINIT", "FRAME"))]
    print("raw log %s: %d lines total, %d SPINIT/FRAME lines"
          % (raw_log, len(lines), len(tagged)))
    for l in tagged[:40]:
        print(" ", l)
    if boot_error is not None:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
