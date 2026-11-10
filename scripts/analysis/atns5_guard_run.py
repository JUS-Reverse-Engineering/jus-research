#!/usr/bin/env python3
"""atns5_guard_run.py -- jus-atns.5. Drives guard-release / attack-acceptance
plans against the live emulator and detects the five frames of interest
from scripts/gdb/atns5_guard.gdb's per-frame log:

  1. button-up frame          -- known from the plan itself
  2. guard flag-clear frame   -- state leaves 3, and M+0x78 bit 26 clears
     (reported separately, per the ticket brief -- they are not assumed
     to be the same frame)
  3. guard-entry lock zero frame -- obj+0x11A reaches 0
  4. attack acceptance frame  -- P1 state becomes 9 (or "dropped" if it
     never does before the trial ends)
  5. first live hitbox frame/id -- first frame at/after acceptance where a
     NEW id appears in P1's own id list (probe's "ids" field) that was not
     already present at/before the reference frame -- not simply the first
     frame the list is non-empty (a persistently-live id, e.g. Kakashi's
     own standing body/hurtbox record, is present from frame 1 and would
     make that check return the reference frame itself every time; see
     `find_first_hitbox`'s own docstring). Blind spot: because the
     baseline is collected up to and including the reference (acceptance)
     frame, a hitbox that is ALREADY live on that exact frame is folded
     into the baseline and cannot be reported as "new" -- this detector
     cannot see a hitbox with delta 0 from acceptance, only delta >= 1.
  6. first contact frame      -- first frame P2's hp drops below its own
     value at trial start

One launch, one GDB attach for a whole session (recipe shared with
cancel_run.py): after `jusemu.py state load`, this script attaches GDB
once (loading atns5_guard.gdb), then for every trial resets the probe's
frame counter by reloading state, drives `jusemu.py run <plan>`, and
slices the newly-appended lines out of the raw log into that trial's own
frames.jsonl -- same idiom as cancel_run.py's Runner (GdbSession.attach()/
resume() split, `set logging redirect on` before `enabled on` to avoid
the stdout-pipe wedge, `detach` before `quit`).

The detector functions below are pure (rows in, frames out) and are
exercised by the unit tests in this file's `_selftest()` (run with
`--selftest`, no live emulator needed) as well as
scripts/tests/test_atns5_guard_run.py (the real, maintained suite --
`_selftest()` is a small subset kept for a quick no-pytest smoke check).
"""

from __future__ import annotations

import argparse
import json
import os
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "emu"))
from jus_ipc import DEFAULT_DIR as IPC_ROOT  # noqa: E402  live emulator IPC root
JUSEMU = ROOT / "scripts" / "emu" / "jusemu.py"
LAUNCH = ROOT / "scripts" / "emu" / "launch_emu.sh"
GDB_SCRIPT = ROOT / "scripts" / "gdb" / "atns5_guard.gdb"

GUARD_STATE = 3
ACCEPT_STATE = 9
PRESS_LEN = 3  # a button "press" in these plans is held 3 frames, matching
               # cancel_plans.py's convention (kakashi-kit templates).


# --------------------------------------------------------------------------
# Plan builders (pure -- no emulator needed)
# --------------------------------------------------------------------------

def b_standalone_plan(name, load_state):
    """B alone from idle. button_up here is meaningless (no guard); kept
    None. Returns (plan, meta) where meta carries the frames this trial's
    detector needs (press frames), since jusemu plans don't round-trip
    that metadata themselves."""
    plan = {
        "name": name,
        "load_state": load_state,
        "tail_frames": 40,
        "segments": [{"from": 0, "to": PRESS_LEN - 1, "buttons": ["B"]}],
        "watches": [],
    }
    return plan, {"button_up": None, "b_press": 0}


def guard_only_plan(name, load_state, hold_frames):
    """DOWN held `hold_frames` frames (1 for a tap, 30 for a hold), no
    attack -- the flag-clear baseline."""
    plan = {
        "name": name,
        "load_state": load_state,
        "tail_frames": 60,
        "segments": [{"from": 0, "to": hold_frames - 1, "buttons": ["DOWN"]}],
        "watches": [],
    }
    return plan, {"button_up": hold_frames, "b_press": None}


def tap_or_hold_b_plan(name, load_state, hold_frames, k):
    """DOWN held `hold_frames` frames, then B at release+k (release =
    hold_frames, the first frame DOWN is no longer held)."""
    b_press = hold_frames + k
    segments = [{"from": 0, "to": hold_frames - 1, "buttons": ["DOWN"]}]
    segments.append({"from": b_press, "to": b_press + PRESS_LEN - 1, "buttons": ["B"]})
    plan = {
        "name": name,
        "load_state": load_state,
        "tail_frames": 40,
        "segments": segments,
        "watches": [],
    }
    return plan, {"button_up": hold_frames, "b_press": b_press}


# --------------------------------------------------------------------------
# Detectors (pure functions -- unit-tested)
# --------------------------------------------------------------------------

def _sorted_rows(rows):
    return sorted(rows, key=lambda r: r["frame"])


def find_state_clear_frame(rows, after_frame, guard_state=GUARD_STATE):
    """First frame > after_frame where P1's state is no longer
    `guard_state`. Returns None if never."""
    for row in _sorted_rows(rows):
        if row["frame"] > after_frame and row.get("state") != guard_state:
            return row["frame"]
    return None


def find_guard_bit_clear_frame(rows, after_frame, before_frame=None):
    """First frame > after_frame (and < before_frame, if given) where the
    guard_bit (M+0x78 bit 26) reads 0. Returns None if never (including
    if the field was never 1 -- an empty-guard baseline is a caller
    error, not a "clear" event).

    `before_frame` guards against a real contamination found live
    (jus-atns.5 RESULTS.md "M+0x78 bit 26 is not guard-exclusive"): the
    same bit was observed going 0->1 again during the FOLLOWING attack
    (state 9), unrelated to guarding -- an unbounded scan can walk past
    the real release-clear event and report that later, spurious toggle
    instead. Callers with a following B press should pass that press's
    own frame here so the scan stops before the attack begins."""
    saw_one = False
    for row in _sorted_rows(rows):
        if before_frame is not None and row["frame"] >= before_frame:
            break
        if row["frame"] <= after_frame:
            if row.get("guard_bit") == 1:
                saw_one = True
            continue
        if row.get("guard_bit") == 1:
            saw_one = True
        elif saw_one and row.get("guard_bit") == 0:
            return row["frame"]
    return None


def find_lock_zero_frame(rows, from_frame=0):
    """First frame >= from_frame where the guard-entry lock (obj+0x11A)
    reads 0, AFTER it has been seen armed (> 0) at least once at/after
    from_frame -- guards against a trial with no guard input at all,
    where lock simply sits at 0 the whole time and would otherwise look
    like an instant "zero" with no arm."""
    armed = False
    for row in _sorted_rows(rows):
        if row["frame"] < from_frame:
            continue
        lock = row.get("lock")
        if lock is not None and lock > 0:
            armed = True
        elif armed and lock == 0:
            return row["frame"]
    return None


def find_acceptance_frame(rows, press_frame, accept_state=ACCEPT_STATE):
    """First frame >= press_frame where P1's state becomes `accept_state`.
    Returns None ("dropped") if it never does."""
    for row in _sorted_rows(rows):
        if row["frame"] >= press_frame and row.get("state") == accept_state:
            return row["frame"]
    return None


def find_first_hitbox(rows, after_frame):
    """First (frame, ids) at/after `after_frame` where a NEW id appears in
    P1's own id list, ignoring `0` (padding, never a real id) and any id
    already live at/before `after_frame` (a persistently-live record --
    jus-atns.5 RESULTS.md/Refuter found id `6` present from well before
    any attack in every trial, almost certainly Kakashi's own standing
    body/hurtbox record, not B's own attack hitbox; the old "first
    non-empty ids" check returned that baseline noise on frame one every
    time). Returns (None, None) if no NEW id ever appears at/after
    `after_frame`.

    Blind spot: the baseline scan includes `after_frame` itself (`row["frame"]
    > after_frame` is the break condition, not `>=`), so any id already
    live ON `after_frame` is folded into `baseline_ids` and can never be
    reported as "new" even though it is a genuinely live hitbox on that
    exact frame. This detector can report a hitbox at `after_frame + 1`
    or later, never AT `after_frame` (delta 0) -- callers that pass
    `acceptance` as `after_frame` cannot distinguish "no hitbox on the
    acceptance frame" from "a hitbox live on the acceptance frame itself,
    undetectable by construction." Not hit in any committed jus-atns.5
    trial (every measured first-hitbox delta is >= +4), but a real gap in
    what this function can see."""
    sorted_rows = _sorted_rows(rows)
    baseline_ids = set()
    for row in sorted_rows:
        if row["frame"] > after_frame:
            break
        baseline_ids |= set(row.get("ids") or [])
    baseline_ids.discard(0)
    for row in sorted_rows:
        if row["frame"] < after_frame:
            continue
        new_ids = sorted(set(row.get("ids") or []) - baseline_ids - {0})
        if new_ids:
            return row["frame"], new_ids
    return None, None


def find_button_release_frame(rows, bit_field, from_frame=0):
    """First frame > the frame the bit last read 1 (at/after `from_frame`)
    where `bit_field` reads 0 -- an observed 1->0 edge. Returns None if
    the bit is never seen at 1, or never drops after that.

    Captures drift by a warm-up offset between `state load` and `run`
    (documented at length in cancel_run.py's own module docstring for
    its captures); trusting the plan's OWN nominal frame numbers against
    this probe's renumbered-from-1 rows was found live to be off by
    several frames (jus-atns.5 smoke test, RESULTS.md). Every button-up/
    press frame this module reports is therefore an OBSERVED edge in
    `in_down`/`in_x80`/`in_x100`, not a nominal plan frame."""
    saw_one = False
    for row in _sorted_rows(rows):
        if row["frame"] < from_frame:
            continue
        val = row.get(bit_field)
        if val == 1:
            saw_one = True
        elif saw_one and val == 0:
            return row["frame"]
    return None


def find_button_press_frame(rows, bit_field, from_frame=0):
    """First frame >= from_frame where `bit_field` reads 1, having read 0
    immediately before (a 0->1 edge), OR simply the first frame >=
    from_frame it reads 1 if the field is already 1 at from_frame (a
    press that started at/before the window this call was given -- the
    common case when `from_frame` is itself a just-observed release)."""
    for row in _sorted_rows(rows):
        if row["frame"] >= from_frame and row.get(bit_field) == 1:
            return row["frame"]
    return None


def find_first_contact(rows, baseline_hp2=None):
    """First frame P2's hp (hp2) drops below its value at trial start (or
    below `baseline_hp2` if given). Returns None if hp2 never drops."""
    rows = _sorted_rows(rows)
    if not rows:
        return None
    if baseline_hp2 is None:
        baseline_hp2 = rows[0].get("hp2")
    for row in rows:
        hp2 = row.get("hp2")
        if hp2 is not None and baseline_hp2 is not None and hp2 < baseline_hp2:
            return row["frame"]
    return None


def summarize_trial(rows, meta, guard_state=GUARD_STATE, accept_state=ACCEPT_STATE,
                     b_bit_field="in_x80"):
    """Fold one trial's frame rows + its plan meta into the five-frame
    report the ticket brief asks for.

    button_up/b_press are OBSERVED from the probe's own `in_down`/
    `<b_bit_field>` input-word bits, not trusted from the plan's nominal
    frame numbers -- a live smoke test (RESULTS.md) found the renumbered
    capture's local frame 1 already several frames past the plan's own
    frame 0 (subprocess/IPC warm-up between `state load` and `run`, the
    same phenomenon cancel_run.py's module docstring documents for its
    own captures), so nominal-frame arithmetic silently misreports every
    downstream number. `meta["button_up"]`/`meta["b_press"]` (the plan's
    OWN nominal frames) are kept in the output only as `nominal_button_up`
    /`nominal_b_press` for cross-checking, never used in the detectors
    below.

    `b_bit_field`: which of the probe's two ambiguous B/Y input bits
    ("in_x80"/"in_x100", guard-sp.md §0.7's "B and Y are 0x80/0x100 in
    unresolved order") tracks B on this fixture -- the caller resolves
    this once per character from a B_standalone trial (the bit that goes
    high at the B press and stays high for exactly the press length) and
    passes it in; default "in_x80" is only a placeholder for callers that
    have not resolved it yet.
    """
    nominal_button_up = meta.get("button_up")
    nominal_b_press = meta.get("b_press")

    button_up = None
    if nominal_button_up is not None:
        button_up = find_button_release_frame(rows, "in_down", from_frame=0)

    b_press = None
    if nominal_b_press is not None:
        search_from = button_up if button_up is not None else 0
        b_press = find_button_press_frame(rows, b_bit_field, from_frame=search_from)

    out = {"button_up": button_up, "b_press": b_press,
           "nominal_button_up": nominal_button_up, "nominal_b_press": nominal_b_press}

    if button_up is not None:
        out["state_clear"] = find_state_clear_frame(rows, button_up, guard_state)
        out["guard_bit_clear"] = find_guard_bit_clear_frame(rows, button_up, before_frame=b_press)
        out["lock_zero"] = find_lock_zero_frame(rows, 0)
        clears = [f for f in (out["state_clear"], out["guard_bit_clear"]) if f is not None]
        out["flag_clear"] = max(clears) if clears else None
    else:
        out["state_clear"] = out["guard_bit_clear"] = out["lock_zero"] = out["flag_clear"] = None

    if b_press is not None:
        accept = find_acceptance_frame(rows, b_press, accept_state)
        out["acceptance"] = accept if accept is not None else "dropped"
        search_from = accept if isinstance(accept, int) else b_press
        hit_frame, hit_ids = find_first_hitbox(rows, search_from)
        out["first_hitbox_frame"] = hit_frame
        out["first_hitbox_ids"] = hit_ids
    else:
        out["acceptance"] = None
        out["first_hitbox_frame"] = out["first_hitbox_ids"] = None

    out["first_contact"] = find_first_contact(rows)
    return out


# --------------------------------------------------------------------------
# GDB session plumbing (same idiom as cancel_run.py / run_experiments.py)
# --------------------------------------------------------------------------

def has_prompt_since(transcript, start):
    return b"(gdb)" in transcript[start:]


class GdbSession:
    def __init__(self, binary, script, timeout=20, extra_ex=None):
        """`extra_ex`: extra -ex commands run BEFORE the script loads (e.g.
        jus-atns.5 round 2 job B's `set $atns5_poke_mode = N`, read by
        atns5_guard.gdb's own header) -- gdb processes -ex/-x in the order
        given on the command line, so these land before the script's own
        `set $atns5_poke_done = 0` etc. initialize."""
        argv = [binary, "-q"]
        for cmd in (extra_ex or []):
            argv += ["-ex", cmd]
        argv += ["-x", str(script)]
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
        # Give melonDS's gdbstub a moment to fully release the remote
        # connection before any caller tries a fresh attach -- found live
        # (jus-atns.5 session log): a `detach`+`quit` that returns
        # immediately can still leave the stub in a state that rejects
        # the NEXT gdb connection with "Ignoring packet error" /
        # "unrecognized item 'timeout' in qSupported response", requiring
        # a full melonDS relaunch to recover. Not fully understood; this
        # sleep is a mitigation, not a fix.
        time.sleep(1.5)


class EmulatorPausedError(RuntimeError):
    pass


def _json_prefix(output):
    try:
        return json.JSONDecoder().raw_decode(output.lstrip())[0]
    except json.JSONDecodeError:
        if "emulator paused" in output:
            raise EmulatorPausedError(output.strip()) from None
        raise


def pending_file(ipc_root=None):
    """<root>/cmd/pending.json for the injected root, else the live IPC_ROOT."""
    return Path(IPC_ROOT if ipc_root is None else ipc_root) / "cmd" / "pending.json"


def _ipc_argv(ipc_root=None):
    """Top-level `--ipc-dir` for jusemu.py (it precedes the subcommand). The
    child client and the plan writer must share one root, so every jusemu
    call names it: the injected root, else the live IPC_ROOT."""
    return ["--ipc-dir", str(IPC_ROOT if ipc_root is None else ipc_root)]


def _bridge_is_paused(ipc_root=None):
    proc = subprocess.run([sys.executable, str(JUSEMU), *_ipc_argv(ipc_root), "status"],
                          cwd=ROOT,
                           text=True, capture_output=True)
    if proc.returncode != 0:
        return False
    try:
        status = _json_prefix(proc.stdout)
    except (json.JSONDecodeError, EmulatorPausedError):
        return True
    return status.get("state") == "paused"


def jusemu(*args, retries=1, ipc_root=None):
    proc = subprocess.run([sys.executable, str(JUSEMU), *_ipc_argv(ipc_root), *args],
                          cwd=ROOT,
                           text=True, capture_output=True)
    if proc.returncode != 0:
        if retries > 0 and "a command is pending" in (proc.stderr or ""):
            if _bridge_is_paused(ipc_root):
                raise EmulatorPausedError(
                    "pending command left behind while the bridge status "
                    "reads paused; not clearing pending.json under a live "
                    "GDB halt")
            pending = pending_file(ipc_root)
            if pending.exists():
                pending.unlink()
            return jusemu(*args, retries=retries - 1, ipc_root=ipc_root)
        raise RuntimeError(f"jusemu {args} failed: {proc.stderr}")
    return _json_prefix(proc.stdout)


def read_new_lines(log_path: Path, offset: int):
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
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("type") == "frame":
            rows.append(normalize_row(obj))
    return rows, len(lines)


def normalize_row(row):
    """Fill `ids` from `recs` for rows logged by the jus-wmqi.2 probe.

    Since jus-wmqi.2 the probe logs `recs`, a list of
    `[record_index, element_id]` pairs capped at 64 per frame (and 8 per
    record), instead of the older `ids` list capped at 8 entries. Detectors read `ids`, so derive it here in the
    same order. Rows that already carry `ids` (older logs) pass through."""
    if "ids" not in row and "recs" in row:
        row["ids"] = [pair[1] for pair in row["recs"]]
    return row


def attach_commands(raw_log):
    return [
        (f"set logging file {raw_log}", True),
        ("set logging redirect on", True),
        ("set logging enabled on", False),
    ]


class Runner:
    def __init__(self, gdb_binary, raw_log, holder, out_dir, launch=True, poke_mode=0):
        self.gdb_binary = gdb_binary
        self.raw_log = Path(raw_log)
        self.holder = holder
        self.out_dir = Path(out_dir)
        self.should_launch = launch
        self.gdb = None
        self.offset = 0
        self.poke_mode = poke_mode

    def launch(self):
        if not self.should_launch:
            return
        env = os.environ.copy()
        env["JUS_EMU_HOLDER"] = self.holder
        subprocess.run(["bash", str(LAUNCH)], cwd=ROOT, env=env, check=True)

    def _load_state(self, slot):
        result = jusemu("state", "load", slot)
        if not result.get("ok"):
            raise RuntimeError(f"state load failed (not ok): {result}")
        return result

    def attach(self, state_slot):
        self._load_state(state_slot)
        self.raw_log.parent.mkdir(parents=True, exist_ok=True)
        if self.raw_log.exists():
            self.raw_log.unlink()
        extra_ex = [f"set $atns5_poke_mode = {self.poke_mode}"]
        self.gdb = GdbSession(self.gdb_binary, str(GDB_SCRIPT), extra_ex=extra_ex)
        for command, wait in attach_commands(self.raw_log):
            self.gdb.command(command, wait=wait)
        time.sleep(0.3)
        self.gdb.drain()
        self.offset = 0
        self.gdb.command("continue", wait=False)

    def run_one(self, plan: dict, timeout=None, ipc_root=None):
        self._load_state(plan["load_state"])
        root = Path(IPC_ROOT if ipc_root is None else ipc_root)
        plan_path = root / f"atns5_plan_{plan['name']}.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        args = ["run", str(plan_path)]
        if timeout is not None:
            args += ["--timeout", str(timeout)]
        result = jusemu(*args, ipc_root=root)
        if not result.get("ok"):
            raise RuntimeError(f"plan run failed: {result}")
        time.sleep(0.2)
        if self.gdb is not None:
            self.gdb.drain()
        rows, self.offset = read_new_lines(self.raw_log, self.offset)
        # NOT trimmed to the plan's own reported `frames` count (unlike
        # cancel_run.py's Runner.run_one -- see its comment for why that
        # trim is right for ITS captures). Live diagnosis here
        # (RESULTS.md "Diagnosis: the driven-frame trim") found far more
        # ambient idle frames appended BEFORE a run's own input than
        # cancel_run.py's ~15-16-frame warm-up: 159 total new lines for a
        # `frames: 63` B_standalone run, with the real B press's own
        # input-bit edge landing at line 80 -- inside the leading ~96
        # lines a last-N trim would have discarded, which is exactly why
        # an early smoke test's sliced capture opened already mid-attack
        # (state 9 at its very first row) with every input bit reading 0.
        # The detectors above (find_button_release_frame et al.) are
        # written to scan forward from frame 0 for the button's own
        # first edge regardless of how much leading idle precedes it, so
        # keeping every row is both correct and required.
        for i, row in enumerate(rows, start=1):
            row["raw_frame"] = row["frame"]
            row["frame"] = i
        return rows, result

    def close(self):
        if self.gdb is not None:
            self.gdb.close()


def write_frames(out_dir: Path, name: str, rows: list, plan: dict, summary: dict):
    folder = out_dir / name
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "frames.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    (folder / "plan.json").write_text(json.dumps(plan, indent=1) + "\n", encoding="utf-8")
    (folder / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Self-test (no emulator) -- exercises the detectors against small,
# hand-built fixture logs. Run with --selftest.
# --------------------------------------------------------------------------

def _selftest():
    failures = []

    def check(name, cond):
        if not cond:
            failures.append(name)

    # Fixture: a 1-frame tap. DOWN pressed at frame 0 only (button_up=1).
    # Lock arms to 6 at frame 3, drains 1/frame, reaches 0 at frame 9.
    # state=3 while guarding (frames 1..10), leaves at 11. guard_bit
    # mirrors state (1 while ==3). No B press in this trial.
    tap_rows = []
    for f in range(0, 15):
        if f == 0:
            state, lock, gb = 0, 0, 0
        elif 1 <= f <= 10:
            state = 3
            lock = max(0, 6 - (f - 3)) if f >= 3 else 6
            gb = 1
        else:
            state, lock, gb = 0, 0, 0
        in_down = 1 if f == 0 else 0  # 1-frame tap: DOWN held frame 0 only
        tap_rows.append({"frame": f, "state": state, "state2": 0, "lock": lock,
                          "guard_bit": gb, "blocked_latch": 0, "in_down": in_down,
                          "in_x80": 0, "in_x100": 0, "hp1": 160, "hp2": 160,
                          "ids": []})
    meta = {"button_up": 1, "b_press": None}
    summary = summarize_trial(tap_rows, meta)
    check("tap state_clear==11", summary["state_clear"] == 11)
    check("tap guard_bit_clear==11", summary["guard_bit_clear"] == 11)
    check("tap lock_zero==9", summary["lock_zero"] == 9)
    check("tap flag_clear==11", summary["flag_clear"] == 11)

    # Fixture: B_standalone. B pressed at frame 0, state becomes 9 at
    # frame 3 (press+3), first hitbox id 256 appears at frame 6.
    b_rows = []
    for f in range(0, 20):
        state = 9 if f >= 3 else 0
        ids = [256] if f >= 6 else []
        in_x80 = 1 if f <= 2 else 0  # B held PRESS_LEN=3 frames from frame 0
        b_rows.append({"frame": f, "state": state, "state2": 0, "lock": 0,
                        "guard_bit": 0, "blocked_latch": 0, "in_down": 0,
                        "in_x80": in_x80, "in_x100": 0, "hp1": 160, "hp2": 160,
                        "ids": ids})
    meta = {"button_up": None, "b_press": 0}
    summary = summarize_trial(b_rows, meta)
    check("B accept==3", summary["acceptance"] == 3)
    check("B first_hitbox_frame==6", summary["first_hitbox_frame"] == 6)
    check("B first_hitbox_ids==[256]", summary["first_hitbox_ids"] == [256])
    check("B first_contact is None", summary["first_contact"] is None)

    # Fixture: acceptance never happens (dropped input).
    dropped_rows = [{"frame": f, "state": 0, "state2": 0, "lock": 0,
                      "guard_bit": 0, "blocked_latch": 0, "in_down": 0,
                      "in_x80": 1 if f >= 2 else 0, "in_x100": 0,
                      "hp1": 160, "hp2": 160, "ids": []} for f in range(0, 10)]
    summary = summarize_trial(dropped_rows, {"button_up": None, "b_press": 2})
    check("dropped acceptance == 'dropped'", summary["acceptance"] == "dropped")

    # Fixture: contact drops P2's hp at frame 8.
    contact_rows = [{"frame": f, "state": 9, "state2": 0, "lock": 0,
                      "guard_bit": 0, "blocked_latch": 0, "hp1": 160,
                      "hp2": 160 if f < 8 else 153, "ids": []} for f in range(0, 12)]
    check("contact frame==8", find_first_contact(contact_rows) == 8)

    if failures:
        print("SELFTEST FAILED:", failures)
        return 1
    print("SELFTEST OK")
    return 0


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--holder", default="atns5")
    parser.add_argument("--gdb", default="gdb-multiarch")
    parser.add_argument("--state", help="fixture savestate name")
    parser.add_argument("--out", help="output directory for this session's trials")
    parser.add_argument("--no-launch", action="store_true")
    parser.add_argument("plans", nargs="*", help="k values for tap/hold trials, or trial names")
    args = parser.parse_args(argv)

    if args.selftest:
        return _selftest()

    parser.error("live-run CLI is driven by shell wrapper calls in the "
                 "RESULTS.md session log, not this entrypoint; use --selftest "
                 "for the pure-function unit tests")


if __name__ == "__main__":
    raise SystemExit(main())
