#!/usr/bin/env python3
"""e1bkw_sp_run.py -- jus-1bkw. Drives the six-question SP-deposit-remainder
GDB session (scripts/gdb/e1bkw_sp_remainder.gdb) against one fixture at a
time: one launch, one GDB attach, several `jusemu.py run` trials, one raw
log per trial (offset-sliced, same idiom as scripts/analysis/atns5_guard_run.py's
Runner/GdbSession/attach_commands -- attach AFTER `state load`, `set
logging redirect on` before `enabled on`, one `continue` issued by the
driver after attach, not by the gdb script itself).

Unlike atns5_guard_run.py's Runner, this driver does NOT renumber the
`frame` field over the sliced rows: the probe's breakpoints are mixed
event types on a single shared frame counter ($e1bkw_frame, ticking off
the same per-frame anchor 0x02082E10 atns5_guard.gdb uses), and
renumbering per-trial would destroy the cross-event correlation the six
questions depend on (ticket brief's explicit discipline note). Rows keep
their raw frame number; `raw_offset` records where in the whole-session
log a trial's slice started, for provenance only.

The pure functions below (event parsing, the Q5 cadence histogram) are
unit-tested by scripts/tests/test_e1bkw_sp_run.py without a live
emulator.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import select
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "emu"))
from jus_ipc import DEFAULT_DIR as IPC_ROOT  # noqa: E402  live emulator IPC root
JUSEMU = ROOT / "scripts" / "emu" / "jusemu.py"
LAUNCH = ROOT / "scripts" / "emu" / "launch_emu.sh"
GDB_SCRIPT = ROOT / "scripts" / "gdb" / "e1bkw_sp_remainder.gdb"

EVENT_RE = re.compile(r"^([A-Z][A-Z0-9_]*) (.+)$")
FIELD_RE = re.compile(r"(\w+)=(#?-?0x[0-9a-fA-F]+|-?\d+|\w+)")


def _coerce(value: str):
    if value.startswith("0x") or value.startswith("#0x"):
        return int(value.lstrip("#"), 16)
    return int(value)


def parse_line(line: str):
    """Parse one raw gdb-log line into {"event": ..., **fields}, or None
    for lines that aren't one of this probe's printf rows (gdb prompt
    noise, `bt 3` backtrace text, blank lines). Pure, no I/O."""
    line = line.strip()
    m = EVENT_RE.match(line)
    if not m:
        return None
    event, rest = m.group(1), m.group(2)
    fields = {"event": event}
    for fm in FIELD_RE.finditer(rest):
        key, val = fm.group(1), fm.group(2)
        try:
            fields[key] = _coerce(val)
        except ValueError:
            fields[key] = val
    return fields


def parse_log(text: str):
    rows = []
    for line in text.splitlines():
        row = parse_line(line)
        if row is not None:
            rows.append(row)
    return rows


def guarded_contacts(rows):
    """Classify hit-writer contacts using the contact-time guard signal.

    A stable HP value is not enough to call a hit blocked.  The rerun probe's
    Q3 row is the contact event and carries the victim-side bit marker; the
    per-frame guard heartbeat supplies the adjacent guard-gauge samples.  A
    contact is ``guarded`` only when both the contact marker is set and the
    victim's gauge increased from the preceding heartbeat to the contact
    heartbeat.  Missing gauge samples are reported as insufficient evidence.
    Pure function, no I/O.
    """
    heartbeats = {}
    for row in rows:
        if row.get("event") != "GUARD_HEARTBEAT":
            continue
        who = row.get("who")
        frame = row.get("frame")
        if who in ("P1", "P2") and isinstance(frame, int):
            heartbeats.setdefault(who, []).append(row)
    for values in heartbeats.values():
        values.sort(key=lambda row: row["frame"])

    result = []
    for row in sorted(
        (row for row in rows if row.get("event") == "Q3_HITWRITER"),
        key=lambda row: row.get("frame", 0),
    ):
        if row.get("is_p1") == 1 and row.get("is_p2") == 0:
            victim = "P1"
        elif row.get("is_p2") == 1 and row.get("is_p1") == 0:
            victim = "P2"
        else:
            victim = None
        contact_frame = row.get("frame")
        before = at = None
        if victim is not None and isinstance(contact_frame, int):
            prior = [h for h in heartbeats.get(victim, []) if h["frame"] < contact_frame]
            same = [h for h in heartbeats.get(victim, []) if h["frame"] == contact_frame]
            before = prior[-1] if prior else None
            at = same[-1] if same else None
        has_gauge = (
            before is not None and at is not None
            and isinstance(before.get("gauge"), int)
            and isinstance(at.get("gauge"), int)
        )
        marker = row.get("guard_bit_1000")
        guarded = bool(marker == 1 and has_gauge and at["gauge"] > before["gauge"])
        result.append({
            "frame": contact_frame,
            "victim": victim,
            "guard_marker": marker,
            "gauge_before": before.get("gauge") if before else None,
            "gauge_at_contact": at.get("gauge") if at else None,
            "guarded": guarded,
            "evidence": "guard+gauge" if guarded else (
                "insufficient-gauge" if not has_gauge else "unguarded-or-no-gauge-rise"
            ),
        })
    return result


def sp_event_accounting(rows):
    """Return per-side writer values and SP apply tails from a parsed log.

    Writer rows are keyed by their character pointer; positive SPAPPLY rows
    are payout/credit observations and negative rows are debit observations,
    kept separate so a conserved pool/bar move is not mistaken for a gain.
    """
    writers = {}
    payouts = {}
    debits = {}
    for row in rows:
        event = row.get("event")
        if event == "WRITER_FCB8":
            key = f"{row.get('char', 0):#x}"
            entry = writers.setdefault(key, {})
            for field in ("val_66", "val_68"):
                if isinstance(row.get(field), int):
                    entry[field] = entry.get(field, 0) + row[field]
        elif event == "WRITER_FCCC":
            key = f"{row.get('char', 0):#x}"
            entry = writers.setdefault(key, {})
            if isinstance(row.get("val_6a"), int):
                entry["val_6a"] = entry.get("val_6a", 0) + row["val_6a"]
        elif event == "SPAPPLY" and isinstance(row.get("amount"), int):
            key = f"{row.get('slot', 0):#x}"
            amount = row["amount"]
            if amount >= 0:
                payouts[key] = payouts.get(key, 0) + amount
            else:
                debits[key] = debits.get(key, 0) + amount
    return {"writers": writers, "payouts_by_slot": payouts, "debits_by_slot": debits}


def cadence_histogram(rows, event="Q5_ABILITY5556"):
    """Given parsed rows (any order), return the sorted list of positive
    inter-fire deltas (in frames, from the shared $e1bkw_frame counter)
    between successive firings of `event`, plus the mean rate
    (fires/frame) over the observed span. Frames with frame<=0 or a
    missing `frame` field are ignored (defensive; the probe always sets
    frame, but a malformed/truncated log line shouldn't crash this).
    Pure function, no I/O -- unit tested."""
    frames = sorted(
        r["frame"] for r in rows
        if r.get("event") == event and isinstance(r.get("frame"), int) and r["frame"] > 0
    )
    if len(frames) < 2:
        return {"deltas": [], "fires": len(frames), "span_frames": 0, "rate": None}
    deltas = [b - a for a, b in zip(frames, frames[1:])]
    span = frames[-1] - frames[0]
    rate = (len(frames) - 1) / span if span > 0 else None
    return {"deltas": deltas, "fires": len(frames), "span_frames": span, "rate": rate}


def input_rising_edges(rows):
    """Rising edges of P1's `input6c` word from INPUT_HEARTBEAT rows
    (0 -> nonzero transitions), sorted by frame. Pure function, no I/O.

    jus-1bkw's Part B rerun used this to convert a plan-relative press
    ("the second B press") into an absolute `$e1bkw_frame` -- the exact
    gap a prior Refuter flagged as missing. The Part A/B fix-and-rerun
    pass found this offset is CONSTANT within one `run_plan()`/`idle()`
    call (the anchor tick and the plan clock advance 1:1 once a plan is
    executing) -- see `plan_probe_offset()` and `framecount_crosscheck()`.
    """
    ih = sorted(
        (r for r in rows
         if r.get("event") == "INPUT_HEARTBEAT" and isinstance(r.get("frame"), int)),
        key=lambda r: r["frame"],
    )
    edges = []
    prev = 0
    for r in ih:
        v = r.get("input6c", 0)
        if prev == 0 and v != 0:
            edges.append(r["frame"])
        prev = v
    return edges


def plan_probe_offset(edges, plan):
    """Given rising edges (probe/`$e1bkw_frame` values) and the plan dict
    that produced them, return the constant `probe_frame - plan_local_frame`
    offset, one edge expected per `plan["segments"]` entry in order. Raises
    ValueError if the edge/segment counts differ or the offsets aren't all
    equal -- the in-plan 1:1 lockstep jus-1bkw's framecount fix depends on.
    Pure function, no I/O."""
    starts = [s["from"] for s in plan["segments"]]
    if len(edges) != len(starts):
        raise ValueError(f"{len(edges)} edges vs {len(starts)} plan segments")
    offsets = [e - s for e, s in zip(edges, starts)]
    if len(set(offsets)) != 1:
        raise ValueError(f"non-constant probe/plan offsets: {offsets}")
    return offsets[0]


def framecount_crosscheck(rows, plan, idle_frames_requested):
    """Re-derive jus-1bkw's Part A/B framecount-ratio fix from a rerun log
    plus the plan that drove it, both committed artifacts -- no live
    emulator needed.

    The anchor tick ($e1bkw_frame) advances 1:1 with the plan's own clock
    while a plan is executing (constant offset, see `plan_probe_offset`).
    Once the plan's own `tail_frames` run out, the bridge free-runs at
    ~60fps until the driver's next command, and the anchor keeps ticking
    through that gap -- inflating a naive whole-session tick count. This
    computes:

    - `last_in_plan_frame`: the last anchor tick that is still "inside"
      the plan (its last segment's `to` + `tail_frames`, converted to a
      probe frame via the offset).
    - `free_run_ticks`: ticks after that point (the overcount).
    - `in_plan_ticks`: the corrected, plan-scoped tick count.
    - `pre_plan_ticks`/`pre_plan_ratio`: ticks that elapsed before this
      plan's own first segment started (i.e. during a prior `idle()` call
      whose requested frame count is `idle_frames_requested`, itself
      derived from `jus_plan.validate_plan()`, not measured) versus that
      request -- this reproduces the original session's `1.11` bracket
      as a same-artifact reading on a different window, not a new rate.

    Pure function, no I/O -- unit tested against the committed
    `sp-deposit-2026-09-14/rerun` logs and plans."""
    edges = input_rising_edges(rows)
    offset = plan_probe_offset(edges, plan)
    total_ticks = max(
        r["frame"] for r in rows if isinstance(r.get("frame"), int)
    )
    last_seg = plan["segments"][-1]
    local_last = last_seg["to"] + plan["tail_frames"]
    last_in_plan_frame = local_last + offset
    free_run_ticks = total_ticks - last_in_plan_frame
    in_plan_ticks = total_ticks - free_run_ticks
    pre_plan_ticks = offset - 1
    return {
        "offset": offset,
        "total_ticks": total_ticks,
        "last_in_plan_frame": last_in_plan_frame,
        "free_run_ticks": free_run_ticks,
        "in_plan_ticks": in_plan_ticks,
        "pre_plan_ticks": pre_plan_ticks,
        "idle_frames_requested": idle_frames_requested,
        "pre_plan_ratio": (
            pre_plan_ticks / idle_frames_requested if idle_frames_requested else None
        ),
    }


def has_prompt_since(buf: bytearray, start: int) -> bool:
    tail = bytes(buf[start:])
    return tail.rstrip().endswith(b"(gdb)")


class GdbSession:
    def __init__(self, binary, script, timeout=20):
        argv = [binary, "-q", "-x", str(script)]
        self.process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, bufsize=0,
        )
        self.transcript = bytearray()
        self._wait_prompt(timeout)

    def _wait_prompt(self, timeout=20):
        start = len(self.transcript)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.process.stdout], [], [],
                                         min(0.25, deadline - time.monotonic()))
            if not ready:
                if self.process.poll() is not None:
                    raise RuntimeError(f"GDB exited early: {self.transcript.decode(errors='replace')}")
                continue
            chunk = os.read(self.process.stdout.fileno(), 4096)
            if not chunk:
                break
            self.transcript.extend(chunk)
            if has_prompt_since(self.transcript, start):
                return
        raise TimeoutError(f"GDB prompt timeout: {self.transcript[-4096:].decode(errors='replace')}")

    def command(self, command, wait=True):
        self.process.stdin.write((command + "\n").encode())
        self.process.stdin.flush()
        if wait:
            self._wait_prompt()

    def drain(self):
        while True:
            ready, _, _ = select.select([self.process.stdout], [], [], 0)
            if not ready:
                return
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                return
            self.transcript.extend(chunk)

    def close(self):
        if self.process.poll() is None:
            try:
                self.command("detach", wait=False)
                time.sleep(1.0)
                self.command("quit", wait=False)
                self.process.wait(timeout=5)
            except Exception:
                self.process.terminate()
        time.sleep(1.5)


def attach_commands(raw_log):
    return [
        (f"set logging file {raw_log}", True),
        ("set logging redirect on", True),
        ("set logging enabled on", False),
    ]


def jusemu(*args, ipc_dir=None):
    # --ipc-dir is top-level (before the subcommand): always name the root.
    argv = [sys.executable, str(JUSEMU), "--ipc-dir",
            str(IPC_ROOT if ipc_dir is None else ipc_dir)]
    argv += list(args)
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(f"jusemu {args} failed: {proc.stderr}")
    # jusemu.py prints its JSON with `indent=1` (multi-line), so the
    # last LINE is just a closing brace -- splitlines()[-1] never
    # matched the CLI's real output. `run` additionally prints a
    # trailing plain-text "log: <path>" line AFTER its JSON ack, so
    # even a whole-stdout json.loads() fails with "Extra data". Decode
    # only the first JSON value and ignore anything after it. Two bugs
    # found live this session (jus-1bkw Part B): the first raised
    # JSONDecodeError on the very first `state load`, the second on
    # the first `run`.
    stripped = proc.stdout.strip()
    if not stripped:
        return {}
    return json.JSONDecoder().raw_decode(stripped)[0]


class Runner:
    def __init__(self, gdb_binary, raw_log, holder, launch=True, gdb_script=None):
        self.gdb_binary = gdb_binary
        self.raw_log = Path(raw_log)
        self.holder = holder
        self.should_launch = launch
        self.gdb = None
        # Defaults to the first session's probe (e1bkw_sp_remainder.gdb) for
        # byte-for-byte back-compat; pass gdb_script=".../e1bkw2_sp_rerun.gdb"
        # (or any other probe built on it) to drive a different script
        # without editing this file. Found needed live (jus-1bkw, Part B
        # rerun) when GDB_SCRIPT was hard-coded and the rerun's new probe
        # could only be run by hand-editing this module.
        self.gdb_script = Path(gdb_script) if gdb_script else GDB_SCRIPT

    def launch(self):
        if not self.should_launch:
            return
        env = os.environ.copy()
        env["JUS_EMU_HOLDER"] = self.holder
        subprocess.run(["bash", str(LAUNCH)], cwd=ROOT, env=env, check=True)

    def attach(self, state_slot):
        result = jusemu("state", "load", state_slot)
        if not result.get("ok"):
            raise RuntimeError(f"state load failed: {result}")
        self.raw_log.parent.mkdir(parents=True, exist_ok=True)
        if self.raw_log.exists():
            self.raw_log.unlink()
        self.gdb = GdbSession(self.gdb_binary, str(self.gdb_script))
        for command, wait in attach_commands(self.raw_log):
            self.gdb.command(command, wait=wait)
        time.sleep(0.3)
        self.gdb.drain()
        self.gdb.command("continue", wait=False)

    def run_plan(self, plan_path, timeout=None, ipc_root=None):
        args = ["run", str(plan_path)]
        if timeout is not None:
            args += ["--timeout", str(timeout)]
        result = jusemu(*args, ipc_dir=ipc_root)
        time.sleep(0.2)
        if self.gdb is not None:
            self.gdb.drain()
        return result

    def idle(self, frames, timeout=None, ipc_root=None):
        # jus_plan.validate_plan() rejects an empty `segments` list
        # outright ("plan has no segments") regardless of tail_frames --
        # found live this session (jus-1bkw Part B) when a bare
        # `segments: []` plan (matching the FORMAT the first Part A
        # session's committed plan JSON files use) failed to run
        # through this exact CLI path. A single zero-button filler
        # segment satisfies the validator and adds no real input; the
        # requested idle length still comes from `tail_frames`.
        plan = {
            "name": "e1bkw_idle",
            "segments": [{"from": 0, "to": 0, "buttons": []}],
            "tail_frames": frames,
        }
        root = Path(IPC_ROOT if ipc_root is None else ipc_root)
        plan_path = root / "e1bkw_idle_plan.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        return self.run_plan(plan_path, timeout=timeout, ipc_root=root)

    def close(self):
        if self.gdb is not None:
            self.gdb.close()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument(
        "--gdb-script", default=str(GDB_SCRIPT),
        help="Probe script to drive (default: %(default)s). Pass "
             "scripts/gdb/e1bkw2_sp_rerun.gdb to run the Part B rerun probe "
             "instead of the first session's e1bkw_sp_remainder.gdb.")
    args = ap.parse_args(argv)
    if args.selftest:
        sample = (
            "Q5_ABILITY5556 frame=10 slot=0x21df164 amount=-3 koma=0x1234 koma_4b=0 koma_4c=-3 lr=0x2077e40\n"
            "Q5_ABILITY5556 frame=11 slot=0x21df164 amount=-3 koma=0x1234 koma_4b=0 koma_4c=-3 lr=0x2077e40\n"
            "(gdb) some noise\n"
        )
        rows = parse_log(sample)
        assert len(rows) == 2, rows
        hist = cadence_histogram(rows)
        assert hist["fires"] == 2 and hist["deltas"] == [1], hist
        print("selftest OK")
        return 0
    print("This driver requires a live emulator session; see jus-1bkw's "
          "RESULTS.md for the manual invocation used.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
