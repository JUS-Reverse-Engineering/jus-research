#!/usr/bin/env python3
"""dream_run.py -- jus-atns.1 (dream attack hit-landing rerun, follow-up to
closed jus-jh7d). Drives a fixed list of plans against the live emulator
under scripts/gdb/atns1_dream.gdb and writes each plan's frame/hit rows to
docs/research/feel-captures/dream-attack-2026-09-14/<plan>/log.jsonl.

Same GDB session idiom as scripts/analysis/cancel_run.py / atns2_sound_run.py
(GdbSession, jusemu(), attach_commands' `set logging redirect on` BEFORE
`enabled on`, `detach` before `quit`) -- imported directly rather than
re-implemented. One launch, one attach, many plan runs, each preceded by a
fresh `state load` of the fixture (pc-taikoubou-npc-jotaro-dark-tournament)
unless `reload_state=None` is passed.

Fixture facts (see the ticket brief / RESULTS.md "Conditions"): a state
reload resets the active koma to slot 0 (Taikoubou, no hotkey). L -> Yusuke
(slot 2), R -> Momotaro (slot 1). Every plan therefore switches first, waits
~30 frames for the switch to land, walks in, then throws either a control
jab (B) or the dream attack (re-press the same hotkey).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import cancel_run  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "emu"))
from jus_ipc import DEFAULT_DIR as IPC_ROOT  # noqa: E402  live emulator IPC root
GDB_SCRIPT = ROOT / "scripts" / "gdb" / "atns1_dream.gdb"
STATE_SLOT = "pc-taikoubou-npc-jotaro-dark-tournament"


def read_all_new_lines(log_path: Path, offset: int):
    """Keep every JSON line (frame, state11_enter, hit), not just
    type=="frame" -- same idiom as atns2_sound_run.read_all_new_lines."""
    if not log_path.exists():
        return [], offset
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    new = lines[offset:]
    rows = []
    for line in new:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows, len(lines)


class Runner:
    def __init__(self, gdb_binary, raw_log, holder, out_dir, launch=True):
        self.gdb_binary = gdb_binary
        self.raw_log = Path(raw_log)
        self.holder = holder
        self.out_dir = Path(out_dir)
        self.should_launch = launch
        self.gdb = None
        self.offset = 0

    def launch(self):
        if not self.should_launch:
            return
        env = os.environ.copy()
        env["JUS_EMU_HOLDER"] = self.holder
        import subprocess
        subprocess.run(["bash", str(ROOT / "scripts/emu/launch_emu.sh"), "--keep-ipc"],
                        cwd=ROOT, env=env, check=True)

    def load_state(self, state_slot=STATE_SLOT):
        result = cancel_run.jusemu("state", "load", state_slot)
        if not result.get("ok"):
            raise RuntimeError(f"state load failed (not ok): {result}")
        return result

    def attach(self):
        self.load_state()
        self.raw_log.parent.mkdir(parents=True, exist_ok=True)
        if self.raw_log.exists():
            self.raw_log.unlink()
        self.gdb = cancel_run.GdbSession(self.gdb_binary, str(GDB_SCRIPT))
        for command, wait in cancel_run.attach_commands(self.raw_log):
            self.gdb.command(command, wait=wait)
        time.sleep(0.3)
        self.gdb.drain()
        self.offset = 0
        self.gdb.command("continue", wait=False)

    def run_plan(self, plan: dict, timeout=30, reload_state=STATE_SLOT, ipc_root=None):
        if reload_state is not None:
            self.load_state(reload_state)
        root = Path(IPC_ROOT if ipc_root is None else ipc_root)
        plan_path = root / f"atns1_plan_{plan['name']}.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        result = cancel_run.jusemu("run", str(plan_path), "--timeout", str(timeout),
                                   ipc_root=root)
        if not result.get("ok"):
            raise RuntimeError(f"plan run failed: {result}")
        time.sleep(0.2)
        if self.gdb is not None:
            self.gdb.drain()
        rows, self.offset = read_all_new_lines(self.raw_log, self.offset)
        driven = result.get("result", {}).get("frames")
        # Trim on type=="frame" rows only, and renumber into row["index"]
        # rather than clobbering row["frame"] (jus-atns.1 Refuter,
        # dream-attack-2026-09-14: `rows` also holds interleaved
        # state11_enter/hit rows, so slicing/renumbering the combined list
        # both drops real early frames to make room for event rows and
        # makes later frame numbers inflate over event rows that share no
        # real frame count -- same bug atns2_sound_run.py fixed for
        # sound_entry/sound rows). Mirrors atns2_sound_run.py:126-140.
        if isinstance(driven, int) and driven > 0:
            frame_indices = [i for i, row in enumerate(rows) if row.get("type") == "frame"]
            if driven <= len(frame_indices):
                rows = rows[frame_indices[-driven]:]
        for i, row in enumerate(rows, start=1):
            row["raw_frame"] = row.get("frame")
            row["index"] = i
        # Health check (README.md "Combined Lua+GDB workflow": "a no-hit
        # result is worthless unless the log shows the session stayed
        # healthy" -- a silently-halted GDB session, e.g. from a stray
        # SIGILL, prints exactly the same "0 hits" as a real one). Confirm
        # GDB is still alive and the per-frame anchor kept firing roughly
        # in step with this plan's own frame count before trusting `rows`.
        if self.gdb is not None and self.gdb.process.poll() is not None:
            raise RuntimeError(
                f"GDB process died during plan {plan['name']!r} "
                f"(exit {self.gdb.process.poll()}) -- results before this "
                f"point are suspect")
        frame_rows = [r for r in rows if r.get("type") == "frame"]
        if isinstance(driven, int) and driven > 5 and len(frame_rows) < driven * 0.5:
            raise RuntimeError(
                f"plan {plan['name']!r} drove {driven} frames but the "
                f"per-frame anchor only logged {len(frame_rows)} -- GDB "
                f"likely stalled/halted mid-plan (e.g. an unhandled signal); "
                f"treat this plan's result as unhealthy, not a real no-hit")
        return rows, result

    def close(self):
        if self.gdb is not None:
            self.gdb.close()


def write_log(out_dir: Path, name: str, rows: list, plan: dict):
    folder = out_dir / name
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "log.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    (folder / "plan.json").write_text(json.dumps(plan, indent=1) + "\n", encoding="utf-8")


def hp_summary(rows):
    frames = [r for r in rows if r.get("type") == "frame"]
    if not frames:
        return None
    p1_start, p2_start = frames[0]["p1hp"], frames[0]["p2hp"]
    p1_min = min(r["p1hp"] for r in frames)
    p2_min = min(r["p2hp"] for r in frames)
    return {
        "p1_start": p1_start, "p2_start": p2_start,
        "p1_min": p1_min, "p2_min": p2_min,
        "p1_delta": p1_start - p1_min, "p2_delta": p2_start - p2_min,
        "n_frames": len(frames),
        "hits": len([r for r in rows if r.get("type") == "hit"]),
        "state11": len([r for r in rows if r.get("type") == "state11_enter"]),
    }


# --------------------------------------------------------------------------
# Plan builders
# --------------------------------------------------------------------------

def plan(name, segments, tail_frames=90):
    return {"name": name, "segments": segments, "tail_frames": tail_frames}


def switch_walk_press(name, hotkey, walk_frames, press_buttons, press_hold=3,
                       switch_settle=30, tail_frames=120, walk_dir="LEFT"):
    """switch (hotkey, f0) -> idle `switch_settle` frames -> `walk_dir` for
    `walk_frames` -> `press_buttons` held for `press_hold` frames.

    `walk_dir` defaults to LEFT: batch-1 calibration (jab_w10..jab_w90, all
    RIGHT) found P1 (x=162332 raw) already sitting to the RIGHT of P2
    (x=147456 raw, a ~58px gap, matching the state's known starting gap)
    immediately after the switch settles -- holding RIGHT walks P1 further
    AWAY from P2, which is also consistent with five of jus-jh7d's six
    prior "no hit landed" runs holding RIGHT (RESULTS.md; the sixth,
    A_baseline, has no walk direction to compare).
    """
    segs = [{"from": 0, "to": 0, "buttons": [hotkey]}]
    walk_start = switch_settle + 1
    if walk_frames > 0:
        segs.append({"from": walk_start, "to": walk_start + walk_frames - 1,
                     "buttons": [walk_dir]})
    press_start = walk_start + walk_frames
    segs.append({"from": press_start, "to": press_start + press_hold - 1,
                 "buttons": press_buttons})
    return plan(name, segs, tail_frames=tail_frames)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gdb", default="arm-none-eabi-gdb")
    parser.add_argument("--holder", default=os.environ.get("JUS_EMU_HOLDER", "atns1-dream-run"))
    parser.add_argument("--raw-log", default=os.path.join(IPC_ROOT, "atns1_raw.jsonl"))
    parser.add_argument("--out-dir", default=str(
        ROOT / "docs/research/feel-captures/dream-attack-2026-09-14"))
    parser.add_argument("--no-launch", action="store_true")
    parser.add_argument("--walk-values", default="0,5,10,15,20,25,30,40,55",
                        help="comma-separated hold-frame counts to calibrate contact distance")
    parser.add_argument("--walk-dir", default="LEFT", choices=["LEFT", "RIGHT"],
                        help="direction P1 walks before the press (jus-atns.1 Refuter: "
                        "RIGHT walks P1 AWAY from P2 from this fixture's starting "
                        "positions, so LEFT is the direction that lands; a prior "
                        "session's RIGHT run overwrote its own logs under these same "
                        "plan names because write_log() keys only on plan name -- logs "
                        "are now suffixed with the direction so reruns in the other "
                        "direction cannot collide)")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    runner = Runner(args.gdb, args.raw_log, args.holder, out_dir, launch=not args.no_launch)

    walk_values = [int(w) for w in args.walk_values.split(",") if w.strip()]
    dir_suffix = args.walk_dir.lower()

    try:
        runner.launch()
        runner.attach()

        # -- Step 1: calibration -- jab (B) from Yusuke at several walk
        # lengths, to find the contact distance and prove p2_hp/hit probe
        # are both live before trusting either signal's silence on the
        # dream-attack plans (Facts item 3, "prove the p2_hp watch moves
        # with a control jab first").
        contact_w = None
        for w in walk_values:
            name = f"jab_w{w}_{dir_suffix}"
            p = switch_walk_press(name, "L", w, ["B"], walk_dir=args.walk_dir)
            rows, result = runner.run_plan(p)
            write_log(out_dir, name, rows, p)
            summary = hp_summary(rows)
            print(f"{name}: {summary}")
            if summary and (summary["p2_delta"] > 0 or summary["hits"] > 0) and contact_w is None:
                contact_w = w

        if contact_w is None:
            # Nothing landed anywhere in the swept range -- try walking
            # further (in case the contact range is smaller than the
            # state's starting gap and P1 needs to walk PAST it, or the
            # gap estimate is off) before giving up on calibration.
            for w in [70, 85, 100]:
                name = f"jab_w{w}_{dir_suffix}"
                p = switch_walk_press(name, "L", w, ["B"], walk_dir=args.walk_dir)
                rows, result = runner.run_plan(p)
                write_log(out_dir, name, rows, p)
                summary = hp_summary(rows)
                print(f"{name}: {summary}")
                if summary and (summary["p2_delta"] > 0 or summary["hits"] > 0) and contact_w is None:
                    contact_w = w

        print(f"contact_w = {contact_w}")

        # -- Step 2: dream attack (re-press L) at the contact distance and
        # neighbours, if calibration found one; else fall back to the
        # widest calibrated walk (closest approach tried).
        dream_ws = []
        if contact_w is not None:
            dream_ws = sorted(set([max(contact_w - 10, 0), contact_w, contact_w + 10]))
        else:
            dream_ws = [20]

        for w in dream_ws:
            name = f"dream_L_w{w}_{dir_suffix}"
            p = switch_walk_press(name, "L", w, ["L"], press_hold=1, tail_frames=180,
                                   walk_dir=args.walk_dir)
            rows, result = runner.run_plan(p)
            write_log(out_dir, name, rows, p)
            summary = hp_summary(rows)
            print(f"{name}: {summary}")

        # -- Step 3: Momotaro (R) variant at the same contact distance, if
        # one was found (Do item 2, "a Momotaro (R) variant").
        if contact_w is not None:
            name = f"dream_R_w{contact_w}_{dir_suffix}"
            p = switch_walk_press(name, "R", contact_w, ["R"], press_hold=1, tail_frames=180,
                                   walk_dir=args.walk_dir)
            rows, result = runner.run_plan(p)
            write_log(out_dir, name, rows, p)
            summary = hp_summary(rows)
            print(f"{name}: {summary}")

    finally:
        runner.close()


if __name__ == "__main__":
    main()
