#!/usr/bin/env python3
"""cancel_run.py -- jus-atns.4.3. Drives cancel_plans.py's plans against the
live emulator and detects cancel/follow-up acceptance from
scripts/gdb/atns43_cancel.gdb's per-frame log.

One launch, one GDB attach for the whole session (recipe in the ticket
brief): after the initial `jusemu.py state load`, this script attaches
GDB once, then for every (attack, follow-up, k) plan it resets the
probe's frame counter, resumes, drives `jusemu.py state load` + `jusemu.py
run <plan>`, and slices the newly-appended lines out of the raw log into
that combo's own frames.jsonl. GdbSession's attach()/interrupt()/resume()
split mirrors scripts/gdb/run_experiments.py's ShellRuntime.

Acceptance detector (rewritten per RESULTS.md "Refuter" 2026-09-13 06:55,
which FAILed the original window-based detector below): the original
detector only fired on a state-9 re-entry from a non-9 value, or on a
follow-up id within ACCEPT_WINDOW=3 frames of the press. A real cancel
goes 9 -> 9 with no dip in state, and a chained follow-up's own first
hitbox appears 6+ frames after the cancel actually starts, so neither
branch ever saw a real cancel -- the only event visible was the idle -> 9
blip after the first move's own recovery ended, which is why the old
"Measured" table always landed on "accept = idle-return + 1".

The detector is now a whole-capture diff against the SAME attack's own
`_idle` (no follow-up) baseline, anchor-aligned:
  - anchor = find_anchor(): the first frame P1's state code (obj+0x18)
    leaves idle/walk (not in {0, 1}) -- this is the press frame itself
    (Refuter's "Anchor" note: hitbox offsets in every capture already
    equal kakashi.md's own input-relative offsets).
  - `diff_vs_baseline()` walks the trial and the baseline frame-by-frame
    at the same anchor-relative offset (state, hitbox ids, physx) and
    returns the first offset D where they differ, or None if the trial
    is identical to the baseline through their shared overlap.
  - Accepted (a real cancel) iff D exists AND D is strictly before the
    baseline's own idle-return offset (`detect_idle_return`) -- a press
    landing exactly on the idle-return frame is a dead frame, not a
    cancel (Refuter: "a press landing exactly on the idle-return frame
    is dropped ... idle-return+1 accepts").
  - "After idle-return": D exists but is >= the baseline's idle-return
    -- the trial is byte-identical to the baseline all the way through
    recovery and only then diverges because of a fresh, ordinary move,
    not a cancel.
  - Rejected outright: D is None -- the trial is identical to the
    baseline over their whole shared overlap.
  - The follow-up's own START (when the cancel itself begins, before
    the follow-up's own move has grown its first hitbox) is
    `D - follow_box_offset`, where `follow_box_offset` is the offset of
    the follow-up move's OWN first hitbox in ITS OWN idle baseline (Y:
    +6, per Refuter's worked example `B_Y_k4`).

Frame basis (Alignment rule, RESULTS.md "Debugger"): each capture's own
OBSERVED anchor -- find_anchor()'s first frame where P1's state leaves
idle/walk -- not the plan's own nominal frame numbers, which drift by
roughly a frame relative to the observed anchor due to subprocess-spawn
warm-up between `state load` and `run` (harmless for this arithmetic
since anchor and press shift together, per Refuter's "Anchor" note).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import cancel_plans  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "emu"))
from jus_ipc import DEFAULT_DIR as IPC_ROOT  # noqa: E402  live emulator IPC root
JUSEMU = ROOT / "scripts" / "emu" / "jusemu.py"
LAUNCH = ROOT / "scripts" / "emu" / "launch_emu.sh"
GDB_SCRIPT = ROOT / "scripts" / "gdb" / "atns43_cancel.gdb"

ACCEPT_WINDOW = 3  # historical: the old window-based detector's width.
# Retained only as a comment anchor for the module docstring's account of
# why that detector was replaced (Refuter, RESULTS.md 2026-09-13 06:55);
# diff_vs_baseline()/detect_acceptance() below no longer use it.


# --------------------------------------------------------------------------
# Acceptance / idle-return detectors (pure functions -- unit-tested below)
# --------------------------------------------------------------------------

def _by_local_frame(frames):
    return {row["frame"]: row for row in frames}


def find_anchor(frames):
    """The observed anchor (Debugger 2026-09-13 03:05, RESULTS.md
    "Alignment rule"): the first frame (in frame order) where P1's state
    code (obj+0x18) leaves idle/walk (state not in {0, 1}). All cancel-
    window arithmetic is anchored on this OBSERVED frame, not on the
    plan's own nominal frame numbers -- those drift by roughly a plan
    frame (observed anchor sat at plan frame 26 -1..+2 across 10 runs)
    because of subprocess-spawn warm-up between `state load` and `run`.
    Returns None if no such frame is logged."""
    for row in sorted(frames, key=lambda r: r["frame"]):
        if row["state"] not in (0, 1):
            return row["frame"]
    return None


def diff_vs_baseline(trial_rows, baseline_rows):
    """Anchor-aligned whole-capture diff (Refuter, RESULTS.md 06:55, 09:55):
    find the first anchor-relative offset D where `trial_rows` differs
    from `baseline_rows` in state, hitbox ids, physx, or physy, comparing
    frame-by-frame at the SAME offset from each capture's own
    find_anchor().

    Returns (D, differing_fields):
      - D is the anchor-relative offset (an int >= 0) of the first
        difference, or None if the trial is identical to the baseline
        over their whole shared overlap (both anchored, both compared
        only from offset 0 onward -- frames before the anchor are the
        walk-in and are not compared).
      - differing_fields is a sorted list of the field names that
        differ at D ("state", "ids", "physx", "physy"), or None when D
        is None.

    ids are compared as sorted lists (NOT sets): a probe row like
    {"ids": [0, 0]} vs {"ids": [0]} is a real difference (one of the two
    tracked collision-record slots dropped its live count) that a set
    comparison would silently erase.

    physy is compared alongside physx (Refuter 09:55): the air routes
    (`up_Y -> air_B`/`air_Y`) first diverge on physy alone at +58 -- a
    physx-only diff missed both routes' real cancel start entirely.
    """
    trial_anchor = find_anchor(trial_rows)
    baseline_anchor = find_anchor(baseline_rows)
    if trial_anchor is None or baseline_anchor is None:
        return None, None
    trial_by_offset = {row["frame"] - trial_anchor: row for row in trial_rows}
    baseline_by_offset = {row["frame"] - baseline_anchor: row for row in baseline_rows}
    shared_offsets = sorted(
        o for o in (set(trial_by_offset) & set(baseline_by_offset)) if o >= 0)
    for offset in shared_offsets:
        t = trial_by_offset[offset]
        b = baseline_by_offset[offset]
        diffs = []
        if t["state"] != b["state"]:
            diffs.append("state")
        if sorted(t.get("ids", [])) != sorted(b.get("ids", [])):
            diffs.append("ids")
        if t.get("physx") != b.get("physx"):
            diffs.append("physx")
        if t.get("physy") != b.get("physy"):
            diffs.append("physy")
        if diffs:
            return offset, sorted(diffs)
    return None, None


def first_box_offset(idle_rows, target_ids):
    """The first anchor-relative offset (>= 0) at which any id in
    `target_ids` appears in `idle_rows` (a move thrown alone, no
    follow-up). Used to find a follow-up move's own startup lag -- e.g.
    Y's own first box is +6 in Y_idle -- so a cancel's real START can be
    recovered from the offset its follow-up's box first appears
    (Refuter: "the Y starts at max(earliest cancel start, press)").
    Returns None if no such id is ever logged."""
    anchor = find_anchor(idle_rows)
    if anchor is None:
        return None
    for row in sorted(idle_rows, key=lambda r: r["frame"]):
        offset = row["frame"] - anchor
        if offset < 0:
            continue
        if set(row.get("ids", [])) & target_ids:
            return offset
    return None


def first_new_follow_box_offset(trial_rows, baseline_rows, follow_ids):
    """First anchor-relative offset at which `trial_rows` shows one of the
    follow-up's own hitbox ids (`follow_ids`) that `baseline_rows` does
    NOT show at that SAME offset -- i.e. a box that cannot be explained
    by the first move's own hitbox already being live in both captures.

    This guards the same-button case (B -> B, Y -> Y, where the follow-
    up's own ids are identical to the first move's own ids): plain
    `first_box_offset(trial_rows, follow_ids)` would find the FIRST
    move's own box (present in both idle_fixture-shaped captures) and
    misreport it as follow-up evidence. Comparing against the baseline
    at the same offset excludes anything already explained by the first
    move alone.

    Returns None if either capture has no anchor, or no such offset
    exists in their shared overlap."""
    if not follow_ids:
        return None
    trial_anchor = find_anchor(trial_rows)
    baseline_anchor = find_anchor(baseline_rows)
    if trial_anchor is None or baseline_anchor is None:
        return None
    trial_by_offset = {row["frame"] - trial_anchor: row for row in trial_rows}
    baseline_by_offset = {row["frame"] - baseline_anchor: row for row in baseline_rows}
    shared_offsets = sorted(
        o for o in (set(trial_by_offset) & set(baseline_by_offset)) if o >= 0)
    for offset in shared_offsets:
        trial_ids = set(trial_by_offset[offset].get("ids", []))
        baseline_ids = set(baseline_by_offset[offset].get("ids", []))
        if follow_ids & (trial_ids - baseline_ids):
            return offset
    return None


def classify_divergence(trial_rows, baseline_rows, offset, follow_ids, own_ids=None):
    """Which of the two divergence shapes (Orchestrator note, RESULTS.md
    2026-09-13, "cancel-start rule for the two divergence shapes")
    produced the first difference at anchor-relative `offset`:

      "follow_appears": one of the follow-up's OWN hitbox ids
        (`follow_ids`) is present in the trial's ids at `offset` but was
        NOT present in the baseline's ids at that same offset -- the
        common case (B/side B/up B -> Y): the cancel start is BEFORE
        this box, so start = offset - the follow-up's own startup lag.
      "own_vanishes": an id present in the baseline's ids at `offset`
        (the first move's own still-live hitbox, per its idle capture)
        is ABSENT from the trial's ids at that offset, and no follow-up
        id has appeared yet -- down B -> Y's case: the first move's own
        recovery hitbox got cut short, which IS the cancel event, so
        start = offset directly, not offset minus anything.
      "ambiguous": neither condition holds (e.g. the only differing
        field was physx/state, not ids) -- reported rather than guessed;
        callers fall back to the "follow_appears" formula when a
        follow_box_offset is available, since that is the more common
        shape, but the shape is surfaced so this can be checked by hand.

    own_ids: the first move's own hitbox ids (a manifest's element_ids).
    When given, only those count toward "own_vanishes": a baseline
    element that is not the move's own box (Yusuke's up B leaves a
    falling-state id 9 live at +36..+44) can go missing because the
    follow-up changed the state, and that is not a box cut (69it.6).
    When None, any baseline id counts (the old rule, kept for the
    Kakashi-only live runner, which has no own-id table).

    Returns None if either capture has no anchor (can't align)."""
    trial_anchor = find_anchor(trial_rows)
    baseline_anchor = find_anchor(baseline_rows)
    if trial_anchor is None or baseline_anchor is None:
        return None
    trial_row = next((r for r in trial_rows if r["frame"] - trial_anchor == offset), None)
    baseline_row = next((r for r in baseline_rows if r["frame"] - baseline_anchor == offset), None)
    if trial_row is None or baseline_row is None:
        return None
    trial_ids = set(trial_row.get("ids", []))
    baseline_ids = set(baseline_row.get("ids", []))
    if follow_ids & (trial_ids - baseline_ids):
        return "follow_appears"
    vanished = baseline_ids - trial_ids
    if own_ids is not None:
        vanished &= set(own_ids)
    if vanished:
        return "own_vanishes"
    return "ambiguous"


def detect_acceptance(trial_rows, baseline_rows, follow, follow_box_offset=None,
                      follow_ids=None, own_ids=None):
    """Diff-vs-baseline acceptance detector (Refuter, RESULTS.md 06:55 and
    09:55), replacing the old window-based detector (see module docstring
    for why it missed every real cancel).

    trial_rows: the (attack, follow, k) combo's own capture.
    baseline_rows: the SAME attack's `_idle` (no follow-up) capture.
    follow: the follow-up's name ("B", "Y", "side_Y", "up_Y", "air_B",
    "air_Y") -- used to look up its own hitbox ids (cancel_plans.
    FOLLOWUP_IDS) for `classify_divergence`'s two-shape rule and for the
    box-scan fallback below.
    follow_ids: the follow-up's own hitbox ids. Optional -- when omitted
    they are looked up by `follow` in `cancel_plans.FOLLOWUP_IDS`, which
    holds KAKASHI's ids; a manifest-driven caller (scripts/kit/analyze.py)
    passes its own character's ids (Yusuke's side_Y is 261, not 262).
    own_ids: the first move's own hitbox ids, passed to
      `classify_divergence` (see there). Optional; None keeps the old
      any-id rule.
    follow_box_offset: the follow-up move's own first-hitbox offset in
    ITS OWN idle baseline (see `first_box_offset`). Optional -- when
    omitted, `follow_start` is left as None (the live runner path does
    not always have the follow-up's own idle capture on hand yet).

    Returns a dict:
      accepted: bool -- True iff a real cancel (the follow-up's own box
        can be shown to start strictly before the baseline's own idle-
        return offset).
      divergence: the anchor-relative offset D from `diff_vs_baseline`,
        or None if the trial is identical to the baseline.
      diffs: the differing field names at D, or None.
      shape: "follow_appears" / "own_vanishes" / "ambiguous" / None --
        which divergence shape produced D (Orchestrator note); None
        when there is no divergence to classify.
      idle_return: the baseline's own idle-return offset (may be None).
      after_idle_return: True iff no real cancel was found and any
        divergence that does exist is at or after the baseline's idle-
        return -- a fresh, ordinary move, not a cancel (Refuter: "a
        press landing exactly on the idle-return frame is dropped").
      follow_start: the recovered cancel-start frame when accepted --
        D - follow_box_offset for "follow_appears"; D itself for
        "own_vanishes"; the box-scan fallback's recovered start (see
        below) otherwise; None when nothing recovers a start.

    Box-scan fallback (Refuter 09:55 FAIL, "the same omission produced
    the four ambiguous / start unknown rows"): `diff_vs_baseline`'s own
    D is the first ANY-field difference, which is not always the follow-
    up's own box -- an unrelated early id/physx blip can land first
    ("ambiguous"), or D can land at/after the baseline's idle-return
    because the only field that differs before the follow's own box
    appears is something else entirely (B -> side_Y: the follow's own
    movement nudges physx/physy while side_Y's own box doesn't appear
    until well after B's idle-return, which the old detector read as
    "after idle-return" and gave up). Both cases are recoverable the
    same way: `first_new_follow_box_offset` finds where the follow's own
    box ACTUALLY appears (a box baseline never shows at that offset,
    so same-button follow-ups like B -> B are excluded automatically --
    see that function's docstring), and if the recovered start
    (box offset - follow_box_offset) lands strictly before the
    baseline's idle-return, that is real, earlier evidence of a cancel
    regardless of what `diff_vs_baseline` found first.
    """
    divergence, diffs = diff_vs_baseline(trial_rows, baseline_rows)
    baseline_anchor = find_anchor(baseline_rows)
    idle_return = (detect_idle_return(baseline_rows, baseline_anchor)
                   if baseline_anchor is not None else None)

    if follow_ids is None:
        follow_ids = cancel_plans.FOLLOWUP_IDS.get(follow, set())
    follow_ids = set(follow_ids)
    box_seen = first_new_follow_box_offset(trial_rows, baseline_rows, follow_ids)
    recovered_start = (box_seen - follow_box_offset
                        if box_seen is not None and follow_box_offset is not None
                        else None)
    early_cancel = (recovered_start is not None and idle_return is not None
                     and recovered_start < idle_return)

    if divergence is None:
        return {"accepted": False, "divergence": None, "diffs": None,
                "shape": None, "idle_return": idle_return,
                "after_idle_return": False, "follow_start": None,
                "follow": follow, "reason": "identical_to_baseline"}

    if idle_return is not None and divergence < idle_return:
        shape = classify_divergence(trial_rows, baseline_rows, divergence, follow_ids,
                                    own_ids=own_ids)
        if shape == "own_vanishes":
            follow_start = divergence
        elif shape == "follow_appears" and follow_box_offset is not None:
            follow_start = divergence - follow_box_offset
        elif early_cancel:
            # "ambiguous" at D, but the follow-up's own box was found
            # later in the same capture -- recover the start from that
            # instead of giving up (Refuter 09:55).
            follow_start = recovered_start
        else:
            follow_start = None
        return {"accepted": True, "divergence": divergence, "diffs": diffs,
                "shape": shape, "idle_return": idle_return,
                "after_idle_return": False, "follow_start": follow_start,
                "follow": follow, "reason": "cancel"}

    if early_cancel:
        # divergence here is the real diff-vs-baseline offset D (kept as
        # reported -- write_summary's per-k table cell always shows the
        # raw D, whatever it is), NOT box_seen: the follow-up's own box
        # independently proves a real, earlier cancel (Refuter 09:55:
        # "detect_acceptance returns 'after idle-return' ... and never
        # scans for the follow-up's own ids"), but D itself is still
        # whatever field differed first.
        return {"accepted": True, "divergence": divergence, "diffs": diffs,
                "shape": "follow_appears", "idle_return": idle_return,
                "after_idle_return": False, "follow_start": recovered_start,
                "follow": follow, "reason": "cancel"}

    return {"accepted": False, "divergence": divergence, "diffs": diffs,
            "shape": None, "idle_return": idle_return,
            "after_idle_return": True, "follow_start": None,
            "follow": follow, "reason": "after_idle_return"}


def detect_idle_return(frames, anchor):
    """First anchor-relative offset (RESULTS.md's "idle-return anchor+32"
    convention) at which P1's state returns to idle (0) or walk (1)
    after the anchor frame itself. Returns None if not found."""
    for row in sorted(frames, key=lambda r: r["frame"]):
        if row["frame"] <= anchor:
            continue
        if row["state"] in (0, 1):
            return row["frame"] - anchor
    return None


def detect_attack_end(frames, anchor):
    """First anchor-relative offset after the anchor at which P1's state
    differs from its state AT the anchor (the move's own attack state).
    For most moves this equals `detect_idle_return` (9 goes straight to
    0); for a move with an in-between state it is earlier (Yusuke's up B:
    9 until +35, fall state 6 from +36, idle +46). A follow-up that starts
    at or after this offset came out of that in-between state, not out of
    the attack (69it.6). Returns None if not found."""
    rows = sorted(frames, key=lambda r: r["frame"])
    attack_state = next((r["state"] for r in rows if r["frame"] == anchor), None)
    if attack_state is None:
        return None
    for row in rows:
        if row["frame"] <= anchor:
            continue
        if row["state"] != attack_state:
            return row["frame"] - anchor
    return None


# --------------------------------------------------------------------------
# GDB session plumbing (same idiom as scripts/gdb/run_experiments.py)
# --------------------------------------------------------------------------

def has_prompt_since(transcript, start):
    return b"(gdb)" in transcript[start:]


class GdbSession:
    def __init__(self, binary, script, timeout=20):
        self.process = subprocess.Popen(
            [binary, "-q", "-x", str(script)],
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

    def interrupt(self, timeout=45):
        self.process.send_signal(signal.SIGINT)
        self._wait_prompt(timeout)

    def drain(self):
        """Non-blocking drain of any GDB stdout that has arrived but was
        never read (fix list item 2, jus-atns.4.3). Root cause of the
        cancel-run wedge (RESULTS.md "Debugger"): GDB tees every per-
        frame printf to stdout as well as the log file unless `set
        logging redirect on` precedes `set logging enabled on`; an
        unread stdout pipe fills at ~65 KB (~830 of this probe's lines)
        and GDB blocks in write(), halting the ARM9. `redirect on` is
        the real fix, but this drain is a safety net in case anything
        (a stray prompt, a command echo) still lands on stdout."""
        while True:
            ready, _, _ = select.select([self.process.stdout], [], [], 0)
            if not ready:
                return
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                return
            self.transcript.extend(chunk)

    def close(self):
        """Detach before quitting -- found live, jus-atns.4.3 grid run:
        `quit` alone leaves melonDS's ARM9 halted at the probe's
        breakpoint (GDB never sent it a `continue`/`detach` first), so
        the NEXT session's `jusemu.py state load`/`run` hangs forever
        even though the melonDS process itself is alive and spinning at
        100% CPU. `detach` resumes the target before GDB lets go of the
        remote connection."""
        if self.process.poll() is None:
            try:
                self.command("detach", wait=False)
                time.sleep(0.2)
                self.command("quit", wait=False)
                self.process.wait(timeout=5)
            except Exception:
                self.process.terminate()


class EmulatorPausedError(RuntimeError):
    """jusemu reported the bridge as PAUSED -- GDB has the ARM9 halted
    (a breakpoint command list blocked in write(), a manual break, etc).
    Raised instead of letting a plain-text "emulator paused (GDB?)"
    reply (jusemu.py's own `run` ack-timeout message, printed instead of
    JSON) blow up as a raw json.JSONDecodeError, and instead of clearing
    pending.json out from under a run that may still complete once GDB
    resumes (fix list items 3/4, jus-atns.4.3)."""


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
    """Best-effort `jusemu status` check, used only to decide whether a
    stale pending.json is safe to clear (see jusemu() below). Treated as
    paused on any failure to parse, since an unparseable status reply is
    itself a symptom of a halted bridge."""
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
    """Run jusemu.py once. On a stale/unacked pending command (seen live,
    jus-atns.4.3: an occasional ack timeout on `run` leaves pending.json
    behind and every subsequent command refuses to publish), clear the
    pending marker and retry once -- this is exactly what
    jus_ipc.py's own error message tells an operator to do by hand.
    EXCEPT while `jusemu status` itself reads paused: GDB may still be
    holding the ARM9 and the pending command may yet be acked once it
    resumes, so clearing pending.json here would race a live halt
    instead of a truly stale command (fix list item 4, jus-atns.4.3)."""
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


# --------------------------------------------------------------------------
# Log slicing
# --------------------------------------------------------------------------

def read_new_lines(log_path: Path, offset: int):
    """Return (rows, new_offset). rows are parsed JSON objects with
    type=="frame" from lines [offset:] of log_path."""
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
            rows.append(obj)
    return rows, len(lines)


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------

def attach_commands(raw_log):
    """Ordered (command, wait) pairs Runner.attach() sends to GDB right
    after loading atns43_cancel.gdb. `set logging redirect on` MUST
    precede `set logging enabled on` -- without it GDB tees every per-
    frame printf to stdout as well as the log file, and an unread
    stdout pipe fills after ~830 of this probe's lines and wedges GDB in
    write() (RESULTS.md "Debugger", the root cause of the cancel-run
    wedge). `enabled on` is sent with wait=False because once `redirect
    on` has taken effect its own prompt is redirected too, so there is
    no stdout prompt left to wait for (fix list item 1, jus-atns.4.3).
    Pulled out as a pure function so it can be regression-tested without
    a live GDB attach."""
    return [
        (f"set logging file {raw_log}", True),
        ("set logging redirect on", True),
        ("set logging enabled on", False),
    ]


class Runner:
    def __init__(self, gdb_binary, raw_log, holder, state_slot, out_dir, launch=True):
        self.gdb_binary = gdb_binary
        self.raw_log = Path(raw_log)
        self.holder = holder
        self.state_slot = state_slot
        self.out_dir = Path(out_dir)
        self.should_launch = launch
        self.gdb = None
        self.offset = 0

    def launch(self):
        if not self.should_launch:
            return
        env = os.environ.copy()
        env["JUS_EMU_HOLDER"] = self.holder
        subprocess.run(["bash", str(LAUNCH), "--keep-ipc"], cwd=ROOT, env=env, check=True)

    def _load_state(self):
        result = jusemu("state", "load", self.state_slot)
        if not result.get("ok"):
            raise RuntimeError(f"state load failed (not ok): {result}")
        return result

    def attach(self):
        self._load_state()
        self.raw_log.parent.mkdir(parents=True, exist_ok=True)
        # `set logging overwrite off` (atns43_cancel.gdb) means GDB APPENDS
        # to whatever is already at this path. Delete any stale content
        # first -- a live debug session found leftover lines from an
        # earlier attach counted as "new" on the very first run_one() call
        # here, corrupting its frames.jsonl (docs/research/feel-captures/
        # kakashi-cancel-2026-09-13/ "Surprises").
        if self.raw_log.exists():
            self.raw_log.unlink()
        self.gdb = GdbSession(self.gdb_binary, str(GDB_SCRIPT))
        for command, wait in attach_commands(self.raw_log):
            self.gdb.command(command, wait=wait)
        # `set logging enabled on` was sent with wait=False above: once
        # `redirect on` has taken effect its own prompt is redirected to
        # the log file too, so there is nothing on stdout to wait for.
        # Give it a moment to land, then drain any stray stdout bytes
        # (fix list items 1/2, jus-atns.4.3 "Debugger").
        time.sleep(0.3)
        self.gdb.drain()
        self.offset = 0
        self.gdb.command("continue", wait=False)

    def run_one(self, plan: dict, timeout=None, ipc_root=None):
        """Reload the savestate, drive the plan, and return the new frame
        rows for this run, renumbered locally starting at 1.

        No GDB interrupt is used between runs: a SIGINT-based break never
        landed within 45s against this melonDS-lua gdbstub while the
        per-frame breakpoint keeps firing (tried live, jus-atns.4.3 debug
        session -- the probe's own frame counter climbed into the
        thousands during a single failed interrupt() wait). GDB just
        keeps `continue`-ing for the whole session (one attach, per the
        recipe) and this method instead slices the continuously-growing
        raw log by byte/line offset: state_load + run_plan happen while
        GDB free-runs in the background, so lines keep appending the
        whole time, including the ~15 frames of real emulator time that
        elapse from launching the two separate `jusemu.py` subprocesses
        (state load, then run) while GDB has no idea a new plan is about
        to start (found live: B_idle's corrected capture showed the walk
        starting at local frame 16 and the attack at local 42, both a
        consistent ~15-16 frames later than the plan's own frame 0/26 --
        pure IPC/subprocess warm-up, not game behaviour). jusemu's own
        `run` ack reports exactly how many frames the plan drove
        (`result.frames`), so only the LAST that many newly-appended
        lines belong to the plan; earlier ones are warm-up noise and are
        dropped. Kept rows are renumbered 1..N in call order for the
        acceptance/idle-return detectors, which only care about relative
        offsets.
        """
        self._load_state()
        root = Path(IPC_ROOT if ipc_root is None else ipc_root)
        plan_path = root / f"atns43_plan_{plan['name']}.json"
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        args = ["run", str(plan_path)]
        if timeout is not None:
            args += ["--timeout", str(timeout)]
        result = jusemu(*args, ipc_root=root)
        if not result.get("ok"):
            raise RuntimeError(f"plan run failed: {result}")
        # Give the log a brief moment to flush the tail frames to disk.
        time.sleep(0.2)
        # Non-blocking drain of anything GDB left on stdout (fix list
        # item 2, jus-atns.4.3) before trusting the log file's contents.
        if self.gdb is not None:
            self.gdb.drain()
        rows, self.offset = read_new_lines(self.raw_log, self.offset)
        driven = result.get("result", {}).get("frames")
        if isinstance(driven, int) and 0 < driven <= len(rows):
            rows = rows[-driven:]
        for i, row in enumerate(rows, start=1):
            row["raw_frame"] = row["frame"]
            row["frame"] = i
        return rows, result

    def close(self):
        if self.gdb is not None:
            self.gdb.close()


def write_frames(out_dir: Path, name: str, rows: list[dict], plan: dict):
    folder = out_dir / name
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "frames.jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    (folder / "plan.json").write_text(json.dumps(plan, indent=1) + "\n", encoding="utf-8")


def aggregate_combo(attack, follow, idle_rows, trials_by_k, grid,
                     follow_box_offset=None):
    """Fold a set of already-captured (attack, follow, k) trials for one
    combo, plus the SAME attack's `_idle` baseline, into the summary
    shape `write_summary` renders one row from. `trials_by_k` maps a
    subset of `grid`'s k values to that trial's own frame rows (a k
    missing from the map -- e.g. one skipped by a bisection search, or
    a combo folder that was never captured -- renders as "--").

    Verdict (RESULTS.md "Refuter", "Owed"): "cancel from +N" if any k
    was accepted (N = the smallest recovered follow-up start over all
    accepted k); else "after idle-return only" if some k diverged only
    at/after the baseline's own idle-return (a fresh move, not a
    cancel); else "no cancel through +K" (K = the largest k tested) --
    the trial was identical to the baseline for every k tried.
    """
    idle_anchor = find_anchor(idle_rows) if idle_rows is not None else None
    idle_return = (detect_idle_return(idle_rows, idle_anchor)
                   if idle_anchor is not None else None)

    per_k = {}
    accepted_starts = []
    any_accepted = False
    any_after_idle = False
    max_k_tested = None
    for k in grid:
        rows = trials_by_k.get(k)
        if rows is None:
            per_k[k] = None
            continue
        max_k_tested = k
        evidence = detect_acceptance(rows, idle_rows, follow,
                                      follow_box_offset=follow_box_offset)
        per_k[k] = evidence
        if evidence["accepted"]:
            any_accepted = True
            if evidence["follow_start"] is not None:
                accepted_starts.append(evidence["follow_start"])
        elif evidence["after_idle_return"]:
            any_after_idle = True

    if accepted_starts:
        cancel_start = min(accepted_starts)
        verdict = f"cancel from +{cancel_start}"
    elif any_accepted:
        cancel_start = None
        verdict = "cancel (start unknown -- no follow-up box offset given)"
    elif any_after_idle:
        cancel_start = None
        verdict = "after idle-return only"
    else:
        cancel_start = None
        k_reported = max_k_tested if max_k_tested is not None else (grid[-1] if grid else None)
        verdict = f"no cancel through +{k_reported}" if k_reported is not None else "no data"

    return {
        "attack": attack,
        "follow": follow,
        "idle_return": idle_return,
        "per_k": per_k,
        "cancel_start": cancel_start,
        "verdict": verdict,
    }


def run_combo(runner: Runner, out_dir: Path, attack: str, follow: str, grid=None,
              tail_frames=cancel_plans.DEFAULT_TAIL_FRAMES, timeout=None, log=print,
              follow_box_offset=None):
    """Live-emulator combo driver (recipe/cadence/GDB fixes unchanged --
    RESULTS.md "Debugger" and "New bug found and fixed"). Runs the
    attack's own `_idle` baseline once, then bisects the grid for the
    earliest k a real cancel is detected, using the diff-vs-baseline
    detector (`detect_acceptance`) instead of the retired window-based
    one. `follow_box_offset` is optional here (the live path may not
    have the follow-up's own idle capture on hand yet within one
    attack's combo loop); when omitted, `follow_start`/`cancel_start`
    are reported as None/"start unknown" rather than guessed.
    """
    grid = grid or cancel_plans.COARSE_GRID

    idle_plan = cancel_plans.build_idle_plan(attack, tail_frames=tail_frames)
    idle_rows, _ = runner.run_one(idle_plan, timeout=timeout)
    write_frames(out_dir, f"{attack}_idle", idle_rows, idle_plan)
    idle_anchor = find_anchor(idle_rows)
    idle_return = detect_idle_return(idle_rows, idle_anchor) if idle_anchor is not None else None
    log(f"{attack} anchor={idle_anchor} idle-return offset: {idle_return}")

    trials = {}  # k -> rows

    def try_k(k):
        if k in trials:
            return trials[k]
        plan = cancel_plans.build_plan(attack, follow, k, tail_frames=tail_frames)
        rows, _ = runner.run_one(plan, timeout=timeout)
        write_frames(out_dir, plan["name"], rows, plan)
        trials[k] = rows
        evidence = detect_acceptance(rows, idle_rows, follow,
                                      follow_box_offset=follow_box_offset)
        log(f"{attack} -> {follow} k={k}: "
            f"{'ACCEPT' if evidence['accepted'] else 'reject'} {evidence}")
        return rows

    def accepted_at(k):
        rows = try_k(k)
        return detect_acceptance(rows, idle_rows, follow,
                                  follow_box_offset=follow_box_offset)["accepted"]

    first_accept = None
    last_reject = None
    for k in grid:
        try:
            accepted = accepted_at(k)
        except Exception as exc:
            log(f"{attack} -> {follow} k={k}: RUN FAILED ({exc}); skipping")
            continue
        if accepted:
            first_accept = k
            break
        last_reject = k

    if first_accept is not None:
        lo = last_reject if last_reject is not None else 0
        hi = first_accept
        while hi - lo > 1:
            mid = (lo + hi) // 2
            try:
                accepted = accepted_at(mid)
            except Exception as exc:
                log(f"{attack} -> {follow} k={mid}: RUN FAILED ({exc}); stopping bisection")
                break
            if accepted:
                hi = mid
            else:
                lo = mid
        first_accept = hi
        last_reject = lo

    return aggregate_combo(attack, follow, idle_rows, trials, grid,
                            follow_box_offset=follow_box_offset)


def load_frames_file(path: Path):
    """Load a committed frames.jsonl (offline reanalysis; no live GDB or
    emulator involved). Ignores blank lines; every remaining line is
    expected to be one JSON frame row (the format `write_frames` writes
    and the live probe log slices into)."""
    rows = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


_IDLE_DIR_RE = re.compile(r"^(?P<attack>.+)_idle$")


def _trial_dir_re():
    """Build the trial-folder regex from cancel_plans' own attack/follow
    name lists (jus-atns.4.3 grid 2: directional follow-up names like
    "side_Y"/"up_Y"/"air_B"/"air_Y" broke the old hardcoded `B|Y`
    alternation -- a plain greedy `.+_(B|Y)_k\\d+` mis-splits a folder
    like "Y_side_Y_k4" as attack="Y_side", follow="Y". Anchoring the
    attack group to the KNOWN attack names (cancel_plans.ATTACKS,
    longest-first so "side_B" is tried before a bare "B" could ever
    apply) makes the split unambiguous: only one known attack name can
    ever be a literal prefix of a real trial folder name, so the regex
    engine's alternation order no longer matters for correctness, only
    for matching at all. The follow group is anchored the same way
    against cancel_plans.FOLLOWUPS, longest-first, so "side_Y" is tried
    before "Y" at the position right after the attack's own "_"."""
    def _alt(names):
        return "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    return re.compile(
        rf"^(?P<attack>{_alt(cancel_plans.ATTACKS)})_"
        rf"(?P<follow>{_alt(cancel_plans.FOLLOWUPS)})_k(?P<k>\d+)$")


_TRIAL_DIR_RE = _trial_dir_re()


def discover_combos(grid_dir: Path):
    """Scan a committed grid directory (e.g.
    docs/research/feel-captures/kakashi-cancel-2026-09-13/grid/) for its
    `<attack>_idle` and `<attack>_<follow>_k<k>` subfolders.

    Returns (idle_attacks: set[str], combos: dict[(attack, follow), dict[int, Path]]).
    `idle_attacks` is every attack with its own `_idle` folder (used both
    as a first-move baseline and, for "B"/"Y", as the follow-up move's
    own idle baseline for `first_box_offset`)."""
    idle_attacks = set()
    combos: dict[tuple, dict] = {}
    for child in sorted(grid_dir.iterdir()):
        if not child.is_dir():
            continue
        m = _IDLE_DIR_RE.match(child.name)
        if m:
            idle_attacks.add(m.group("attack"))
            continue
        m = _TRIAL_DIR_RE.match(child.name)
        if m:
            key = (m.group("attack"), m.group("follow"))
            combos.setdefault(key, {})[int(m.group("k"))] = child
    return idle_attacks, combos


def reanalyze(grid_dir: Path, grid=None):
    """Offline entry point (jus-atns.4.3 deliverable 2): re-run the
    diff-vs-baseline detector over every committed (attack, follow, k)
    folder under `grid_dir`, no emulator involved. Only k values in
    `grid` (default cancel_plans.COARSE_GRID) are reported, matching the
    Refuter's own table (RESULTS.md 06:55) -- the extra bisection points
    some combos also have on disk (e.g. B_Y_k33/34/36) are artifacts of
    the retired detector's search and are not part of this table.
    """
    grid = list(grid or cancel_plans.COARSE_GRID)
    idle_attacks, combos = discover_combos(grid_dir)

    idle_cache: dict[str, list] = {}

    def idle_rows_for(attack):
        if attack not in idle_cache:
            path = grid_dir / f"{attack}_idle" / "frames.jsonl"
            idle_cache[attack] = load_frames_file(path) if path.exists() else None
        return idle_cache[attack]

    box_offset_cache: dict[str, int] = {}

    def box_offset_for(follow):
        if follow not in box_offset_cache:
            rows = idle_rows_for(follow) if follow in idle_attacks else None
            box_offset_cache[follow] = (
                first_box_offset(rows, cancel_plans.FOLLOWUP_IDS[follow])
                if rows is not None else None)
        return box_offset_cache[follow]

    results = []
    for (attack, follow), by_k in sorted(combos.items()):
        idle_rows = idle_rows_for(attack)
        if idle_rows is None:
            results.append({"attack": attack, "follow": follow,
                            "idle_return": None, "per_k": {}, "cancel_start": None,
                            "verdict": "no data -- missing _idle baseline"})
            continue
        trials_by_k = {}
        for k, folder in by_k.items():
            if k not in grid:
                continue
            trials_by_k[k] = load_frames_file(folder / "frames.jsonl")
        agg = aggregate_combo(attack, follow, idle_rows, trials_by_k, grid,
                               follow_box_offset=box_offset_for(follow))
        results.append(agg)
    return results


def write_summary(out_dir: Path, results: list[dict], grid=None, invocation=None):
    """Render the per-(attack, follow) diff-vs-baseline table (RESULTS.md
    "Refuter" 06:55's shape): one row per combo, one column per grid k
    with that k's divergence offset ("same" when the trial is identical
    to the baseline, "--" when that k was never captured), then the
    recovered cancel start, the baseline's own idle-return offset, and
    the verdict. Used by both the live runner (`main`) and the offline
    `--reanalyze` entry point.

    invocation: the exact command line that produced this file (fix list
    item 4, jus-atns.4.7 -- "the committed cancel_windows.md needs the
    exact --reanalyze --grid list recorded"), written as a header line
    when given. None for the live runner path, which has no separate
    --grid invocation to record."""
    grid = list(grid or cancel_plans.COARSE_GRID)
    header = ["attack", "follow"] + [f"k{k}" for k in grid] + \
        ["cancel start", "idle-return", "verdict"]
    lines = [
        "# Kakashi cancel/follow-up windows -- jus-atns.4.3 (diff-vs-baseline)",
        "",
    ]
    if invocation:
        lines += [f"Invocation: `{invocation}`", ""]
    lines += [
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
    ]
    for r in results:
        row = [r["attack"], r["follow"]]
        for k in grid:
            cell = r.get("per_k", {}).get(k)
            if cell is None:
                row.append("--")
            elif cell["divergence"] is None:
                row.append("same")
            else:
                row.append(f"+{cell['divergence']}")
        cancel_start = r.get("cancel_start")
        idle_return = r.get("idle_return")
        row.append(f"+{cancel_start}" if cancel_start is not None else "n/a")
        row.append(f"+{idle_return}" if idle_return is not None else "n/a")
        row.append(r.get("verdict", "n/a"))
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    (out_dir / "cancel_windows.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selftest", action="store_true",
                        help="run the acceptance-detector unit tests on a fixture and exit")
    parser.add_argument("--gdb", default="arm-none-eabi-gdb")
    parser.add_argument("--holder", default=os.environ.get("JUS_EMU_HOLDER", "cancel-run"))
    parser.add_argument("--state", default="pc-kakashi-npc-jotaro-dark-tournament")
    parser.add_argument("--raw-log", default=os.path.join(IPC_ROOT, "atns43_raw.jsonl"))
    parser.add_argument("--out-dir", required=False,
                        default=str(ROOT / "docs/research/feel-captures/kakashi-cancel-2026-09-13"))
    parser.add_argument("--attacks", nargs="*", default=cancel_plans.ATTACKS)
    parser.add_argument("--follows", nargs="*", default=cancel_plans.FOLLOWUPS)
    parser.add_argument("--grid", nargs="*", type=int, default=cancel_plans.COARSE_GRID)
    parser.add_argument("--tail-frames", type=int, default=cancel_plans.DEFAULT_TAIL_FRAMES)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--no-launch", action="store_true")
    parser.add_argument("--reanalyze", metavar="GRID_DIR",
                        help="offline: re-run the diff-vs-baseline detector over an "
                             "already-committed grid directory (no emulator, no GDB) "
                             "and rewrite its cancel_windows.md/cancel_windows.json")
    args = parser.parse_args(argv)

    if args.selftest:
        import unittest
        sys.path.insert(0, str(ROOT / "scripts" / "tests"))
        import test_cancel_run  # noqa: E402
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromModule(test_cancel_run)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1

    if args.reanalyze:
        grid_dir = Path(args.reanalyze)
        results = reanalyze(grid_dir, grid=args.grid)
        invocation = "python3 scripts/analysis/cancel_run.py --reanalyze {} --grid {}".format(
            args.reanalyze, " ".join(str(k) for k in args.grid))
        write_summary(grid_dir, results, grid=args.grid, invocation=invocation)
        (grid_dir / "cancel_windows.json").write_text(
            json.dumps(results, indent=1) + "\n", encoding="utf-8")
        print(f"reanalyzed {len(results)} combo(s) under {grid_dir}; "
              f"wrote cancel_windows.md and cancel_windows.json")
        return 0

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    runner = Runner(args.gdb, args.raw_log, args.holder, args.state, out_dir,
                    launch=not args.no_launch)
    results = []
    try:
        runner.launch()
        runner.attach()
        for attack in args.attacks:
            for follow in args.follows:
                try:
                    r = run_combo(runner, out_dir, attack, follow, grid=args.grid,
                                 tail_frames=args.tail_frames, timeout=args.timeout)
                    results.append(r)
                except Exception as exc:
                    print(f"{attack} -> {follow}: COMBO FAILED ({exc}); skipping")
                    results.append({"attack": attack, "follow": follow,
                                    "idle_return": None, "per_k": {},
                                    "cancel_start": None, "verdict": "n/a",
                                    "error": str(exc)})
    finally:
        runner.close()

    write_summary(out_dir, results)
    (out_dir / "cancel_results_raw.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
