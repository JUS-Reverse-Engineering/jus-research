#!/usr/bin/env python3
"""atns2_sound_run.py -- jus-atns.2 live half (generic VFX/SFX trigger
census). Drives a fixed list of plans against the live emulator under
scripts/gdb/atns2_sound.gdb and slices its per-plan output into
docs/research/feel-captures/vfx-sfx-live-2026-09-14/<plan>/log.jsonl.

Same GDB session idiom as scripts/analysis/cancel_run.py (GdbSession,
jusemu(), attach_commands' `set logging redirect on` BEFORE `enabled on`,
`detach` before `quit`) -- imported directly from that module rather than
re-implemented, since the wedge/hang fixes documented there (module
docstring, GdbSession.close()) apply unchanged to this probe. This driver
adds nothing to that plumbing except: (a) it does not reload the savestate
between every plan -- some calls in this session (the Y-mash-until-KO
sequence) need to accumulate HP damage across several plan runs against
the SAME session-in-progress -- and (b) it keeps every log line (not just
`type=="frame"`), since the sound wrapper's own `sound_entry`/`sound`
lines are the point of this capture.
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
JUSEMU = ROOT / "scripts" / "emu" / "jusemu.py"
LAUNCH = ROOT / "scripts" / "emu" / "launch_emu.sh"
GDB_SCRIPT = ROOT / "scripts" / "gdb" / "atns2_sound.gdb"


def read_all_new_lines(log_path: Path, offset: int):
    """Like cancel_run.read_new_lines but keeps every JSON line (frame,
    sound_entry, sound), not just type=="frame"."""
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
        self.current_state = None

    def launch(self):
        if not self.should_launch:
            return
        env = os.environ.copy()
        env["JUS_EMU_HOLDER"] = self.holder
        import subprocess
        subprocess.run(["bash", str(LAUNCH), "--keep-ipc"], cwd=ROOT, env=env, check=True)

    def load_state(self, state_slot):
        result = cancel_run.jusemu("state", "load", state_slot)
        if not result.get("ok"):
            raise RuntimeError(f"state load failed (not ok): {result}")
        self.current_state = state_slot
        return result

    def attach(self):
        self.raw_log.parent.mkdir(parents=True, exist_ok=True)
        if self.raw_log.exists():
            self.raw_log.unlink()
        self.gdb = cancel_run.GdbSession(self.gdb_binary, str(GDB_SCRIPT))
        # Diagnostic (jus-atns.2, batch-1 zero-sound-events finding): confirm
        # the three breakpoints from atns2_sound.gdb actually registered
        # before trusting a live batch's silence as a real behavioural
        # result rather than a probe bug. Printed to our own stdout, not the
        # log file (this runs before `set logging enabled on` below).
        before = len(self.gdb.transcript)
        self.gdb.command("info breakpoints", wait=True)
        print("=== info breakpoints (post-attach) ===")
        print(self.gdb.transcript[before:].decode(errors="replace"))
        for command, wait in cancel_run.attach_commands(self.raw_log):
            self.gdb.command(command, wait=wait)
        time.sleep(0.3)
        self.gdb.drain()
        self.offset = 0
        self.gdb.command("continue", wait=False)

    def run_plan(self, plan: dict, timeout=None, reload_state=None, ipc_root=None):
        """Optionally reload `reload_state` (a savestate slot), then drive
        `plan` and return its newly-appended log rows, renumbered locally.
        `reload_state=None` continues from wherever the previous run_plan
        (or the initial load_state()) left the match -- used for the
        Y-mash-until-KO sequence, which must NOT reset HP between bursts."""
        if reload_state is not None:
            self.load_state(reload_state)
        root = Path(IPC_ROOT if ipc_root is None else ipc_root)
        plan_path = root / f"atns2_plan_{plan['name']}.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        args = ["run", str(plan_path)]
        if timeout is not None:
            args += ["--timeout", str(timeout)]
        result = cancel_run.jusemu(*args, ipc_root=root)
        if not result.get("ok"):
            raise RuntimeError(f"plan run failed: {result}")
        time.sleep(0.2)
        if self.gdb is not None:
            self.gdb.drain()
        rows, self.offset = read_all_new_lines(self.raw_log, self.offset)
        driven = result.get("result", {}).get("frames")
        # Trim on type=="frame" rows only (jus-atns.2 Refuter, live-2026-09-14
        # pass 2): `rows` also holds interleaved `sound_entry`/`sound` rows,
        # so slicing the last `driven` entries of the combined list drops
        # real early frames to make room for sound rows, and can silently
        # cut a sound row's own pair (its `sound_entry` without its `sound`,
        # or vice versa) right at the trim boundary. Instead, find the
        # frame row that starts the last `driven` frames and keep everything
        # from there on, so every sound row between kept frames survives.
        if isinstance(driven, int) and driven > 0:
            frame_indices = [i for i, row in enumerate(rows) if row.get("type") == "frame"]
            if driven <= len(frame_indices):
                rows = rows[frame_indices[-driven]:]
        for i, row in enumerate(rows, start=1):
            row["raw_frame"] = row.get("frame")
            row["index"] = i
        return rows, result

    def close(self):
        if self.gdb is not None:
            self.gdb.close()


def write_log(out_dir: Path, name: str, rows: list[dict], plan: dict):
    folder = out_dir / name
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "log.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    (folder / "plan.json").write_text(json.dumps(plan, indent=1) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Plans
# --------------------------------------------------------------------------

def plan(name, segments, tail_frames=150):
    return {"name": name, "segments": segments, "tail_frames": tail_frames}


# jus_plan.py's validate_plan() requires at least one segment; a single
# 1-frame no-button-pressed segment is the standard "do nothing" idiom
# (BUTTONS has no "none" entry, so an explicit empty list is used).
IDLE_CONTROL = plan("idle_control_60", [{"from": 0, "to": 0, "buttons": []}], tail_frames=59)

BATCH1_PLANS = [
    ("neutral_b", plan("neutral_b", [
        {"from": 0, "to": 25, "buttons": ["LEFT"]},
        {"from": 26, "to": 28, "buttons": ["B"]},
    ])),
    ("neutral_y", plan("neutral_y", [
        {"from": 0, "to": 25, "buttons": ["LEFT"]},
        {"from": 26, "to": 28, "buttons": ["Y"]},
    ])),
    ("forward_y", plan("forward_y", [
        {"from": 0, "to": 25, "buttons": ["LEFT"]},
        {"from": 26, "to": 28, "buttons": ["LEFT", "Y"]},
    ])),
    ("dash_b", plan("dash_b", [
        {"from": 0, "to": 1, "buttons": ["LEFT"]},
        {"from": 8, "to": 12, "buttons": ["LEFT"]},
        {"from": 25, "to": 27, "buttons": ["B"]},
    ])),
    ("guard_hold", plan("guard_hold", [
        {"from": 0, "to": 25, "buttons": ["LEFT"]},
        {"from": 26, "to": 65, "buttons": ["DOWN"]},
    ])),
    ("idle_control_60", IDLE_CONTROL),
]

DREAM_ATTACK_PLAN = json.loads(
    (ROOT / "docs/research/feel-captures/dream-attack-2026-09-12/plans/B_dream.json")
    .read_text(encoding="utf-8"))

Y_MASH_BURST = plan("y_mash_burst", [
    {"from": f, "to": f + 1, "buttons": ["Y"]}
    for f in range(0, 76, 4)
], tail_frames=20)

# --------------------------------------------------------------------------
# jus-atns.2 P3 tail (2026-09-14b): Q1 (hit-resolution gate 0x0208242C),
# Q2 (dream-attack cue), Q3 (SP/HP carry cue), Q4 (KO). New batches 3/4,
# same Runner/fixture idiom as batches 1/2 above.
# --------------------------------------------------------------------------

# Q1/Q4 fixture: pc-kakashi-npc-jotaro-dark-tournament (idle CPU). A B/Y
# mash burst that lands several hits (reuses batch-1's confirmed-landing
# neutral_b/neutral_y timing, repeated) for Q1's "at least 5 hits" ask.
YB_MASH_BURST = plan("yb_mash_burst", [
    {"from": f, "to": f + 2, "buttons": (["B"] if (f // 6) % 2 == 0 else ["Y"])}
    for f in range(0, 120, 6)
], tail_frames=30)

# Q2/Q3 fixture: pc-taikoubou-npc-jotaro-dark-tournament. L -> Yusuke
# (slot 2), settle 60 frames, walk LEFT toward P2 (jus-atns.1 found w=0
# already lands, but the brief asks to walk toward P2 first), re-press L
# in place for the dream attack. Same shape as
# /tmp/jus_emu/atns1_plan_dream_L_w0.json (segments: L@0, L@31) but with
# the ticket's own 60-frame settle wait before the walk and an explicit
# LEFT walk segment (contact_w=0 per jus-atns.1 means the walk is a no-op
# for landing purposes, but the brief asks for it explicitly).
DREAM_L_PLAN = plan("q2_dream_L", [
    {"from": 0, "to": 0, "buttons": ["L"]},
    {"from": 60, "to": 62, "buttons": ["LEFT"]},
    {"from": 63, "to": 63, "buttons": ["L"]},
], tail_frames=180)

# Q3: ordinary L then R switches (Yusuke -> Momotaro), no dream re-press,
# to catch an ordinary switch's SP/HP carry delta.
SWITCH_LR_PLAN = plan("q3_switch_lr", [
    {"from": 0, "to": 0, "buttons": ["L"]},
    {"from": 60, "to": 60, "buttons": ["R"]},
], tail_frames=120)

# Q3 rev2: same as above but mashes B/Y for ~90 frames after the L switch
# (landed hits build SP per guard-sp.md) before switching to R, in an
# attempt to make the switch carry a nonzero SP delta -- the first attempt
# above switched with no attacks thrown first. (2026-09-14 fix pass Part B:
# the probe now DOES read the SP pool word (0x021DF72C) and bar-count pair
# (0x021DF730/31) every frame, in addition to the three payout call sites
# (still silent in both attempts). The pool read found a same-total
# decomposition of one SP bar into the fractional pool right at the switch
# commit in both plans -- see the combat notes §8 and fix/RESULTS.md Q3. The
# SP-apply calls (0x02158BC0/0x02158BCC) and payout sites are a confirmed
# negative at those specific sites; whether the routine's own entry gate
# is closed or the routine is never called was not separated.)
SWITCH_LR_BUILD_PLAN = plan("q3_switch_lr_build", (
    [{"from": 0, "to": 0, "buttons": ["L"]}] +
    [{"from": f, "to": f + 2, "buttons": (["B"] if (f // 6) % 2 == 0 else ["Y"])}
     for f in range(30, 120, 6)] +
    [{"from": 150, "to": 150, "buttons": ["R"]}]
), tail_frames=120)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gdb", default="arm-none-eabi-gdb")
    parser.add_argument("--holder", default=os.environ.get("JUS_EMU_HOLDER", "atns2-sound-run"))
    parser.add_argument("--raw-log", default=os.path.join(IPC_ROOT, "atns2_raw.jsonl"))
    parser.add_argument("--out-dir", default=str(
        ROOT / "docs/research/feel-captures/vfx-sfx-live-2026-09-14"))
    parser.add_argument("--batch", choices=["1", "2", "3", "4"], required=True)
    parser.add_argument("--no-launch", action="store_true")
    parser.add_argument("--ko-bursts", type=int, default=8,
                        help="max number of Y-mash bursts to try for KO in batch 2")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    runner = Runner(args.gdb, args.raw_log, args.holder, out_dir, launch=not args.no_launch)

    try:
        runner.launch()
        if args.batch == "1":
            runner.load_state("pc-kakashi-npc-jotaro-dark-tournament")
            runner.attach()
            for name, p in BATCH1_PLANS:
                rows, result = runner.run_plan(
                    p, timeout=30,
                    reload_state="pc-kakashi-npc-jotaro-dark-tournament")
                write_log(out_dir, name, rows, p)
                print(f"{name}: {len(rows)} rows, result={result.get('result')}")
        elif args.batch == "3":
            # Q1 (hit-resolution gate) + Q4 (KO), pc-kakashi fixture.
            runner.load_state("pc-kakashi-npc-jotaro-dark-tournament")
            runner.attach()
            all_rows = []
            jhp = None
            for i in range(args.ko_bursts):
                rows, result = runner.run_plan(YB_MASH_BURST, timeout=30)
                all_rows.extend(rows)
                frames = [r for r in rows if r.get("type") == "frame"]
                if frames:
                    jhp = frames[-1].get("jhp")
                print(f"yb_mash_burst {i}: {len(rows)} rows, jhp={jhp}")
                if jhp == 0:
                    break
            write_log(out_dir, "q1q4_yb_mash", all_rows, YB_MASH_BURST)
            print(f"q1q4_yb_mash: {len(all_rows)} rows total, final jhp={jhp}")
        elif args.batch == "4":
            # Q2 (dream-attack cue) + Q3 (SP/HP carry cue),
            # pc-taikoubou fixture.
            runner.load_state("pc-taikoubou-npc-jotaro-dark-tournament")
            runner.attach()
            rows, result = runner.run_plan(
                DREAM_L_PLAN, timeout=30,
                reload_state="pc-taikoubou-npc-jotaro-dark-tournament")
            write_log(out_dir, "q2_dream_L", rows, DREAM_L_PLAN)
            print(f"q2_dream_L: {len(rows)} rows, result={result.get('result')}")

            rows, result = runner.run_plan(
                SWITCH_LR_PLAN, timeout=30,
                reload_state="pc-taikoubou-npc-jotaro-dark-tournament")
            write_log(out_dir, "q3_switch_lr", rows, SWITCH_LR_PLAN)
            print(f"q3_switch_lr: {len(rows)} rows, result={result.get('result')}")

            rows, result = runner.run_plan(
                SWITCH_LR_BUILD_PLAN, timeout=30,
                reload_state="pc-taikoubou-npc-jotaro-dark-tournament")
            write_log(out_dir, "q3_switch_lr_build", rows, SWITCH_LR_BUILD_PLAN)
            print(f"q3_switch_lr_build: {len(rows)} rows, result={result.get('result')}")
        else:
            runner.load_state("pc-kakashi-npc-jotaro-fightcpu")
            runner.attach()

            idle_plan = plan("idle_300", [{"from": 0, "to": 0, "buttons": []}], tail_frames=299)
            rows, result = runner.run_plan(
                idle_plan, timeout=30,
                reload_state="pc-kakashi-npc-jotaro-fightcpu")
            write_log(out_dir, "idle_300", rows, idle_plan)
            print(f"idle_300: {len(rows)} rows")

            dream_plan = DREAM_ATTACK_PLAN
            rows, result = runner.run_plan(
                dream_plan, timeout=30,
                reload_state="pc-kakashi-npc-jotaro-fightcpu")
            write_log(out_dir, "dream_attack", rows, dream_plan)
            print(f"dream_attack: {len(rows)} rows")

            # Y-mash-until-KO: fresh reload, then repeated bursts WITHOUT
            # reloading in between so damage accumulates; stop once Jotaro's
            # HP (jhp in the frame log) reads 0, or after --ko-bursts tries.
            runner.load_state("pc-kakashi-npc-jotaro-fightcpu")
            all_ko_rows = []
            jhp = None
            for i in range(args.ko_bursts):
                rows, result = runner.run_plan(Y_MASH_BURST, timeout=30)
                all_ko_rows.extend(rows)
                frames = [r for r in rows if r.get("type") == "frame"]
                if frames:
                    jhp = frames[-1].get("jhp")
                print(f"y_mash_burst {i}: {len(rows)} rows, jhp={jhp}")
                if jhp == 0:
                    break
            write_log(out_dir, "y_mash_ko", all_ko_rows, Y_MASH_BURST)
            print(f"y_mash_ko: {len(all_ko_rows)} rows total, final jhp={jhp}")
    finally:
        runner.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
