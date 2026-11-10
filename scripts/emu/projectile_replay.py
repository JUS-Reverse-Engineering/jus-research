#!/usr/bin/env python3
"""Per-frame projectile-conflict replay for one savestate.

One command that takes a savestate slot from load through a per-frame tail
capture to a self-contained results directory. This is the "Part 1" tool
for tracker item `jus-2s9k`: it automates the manual recipe in
`docs/research/feel-captures/projectile-conflict-2026-09-10/INSTRUMENT.md`
so it can be repeated across several states without hand-building a new
watch spec each time.

Steps (see module functions for detail):

1. `jusemu.py state load <slot>`, verified the way `projectile_census.py`
   verifies it: heartbeat framecount ticks across a 1s wait, and
   `[0x02172960]` (the battle root global) is nonzero.
2. Baseline census via `projectile_census.py --no-load`, writing
   `<slot>.baseline.census.{json,md}`.
3. Build `watch_spec.json` from the baseline census, filling a 512-byte
   budget in the rank order in `build_watch_spec()`'s docstring, and
   validate it with `jus_plan.validate_watches` (the same validator
   `jusemu.py` itself uses). Records what was and was not included in
   `watch_spec.notes.md`.
4. `tail start --every 1`, run `run_plan.json` (START 0-2, no input to 149,
   START 150-152 -- the game keeps running after the last segment, so the
   re-pause matters), `tail stop`.
5. Post-run census via `projectile_census.py --no-load`, writing
   `<slot>.post.census.{json,md}`.
6. `RESULTS.md`: conditions, baseline table, a per-record timeline built
   from the tail log, the post-run table, and a positive-control line.
   Field-offsets-only -- no gameplay words (beam/hit/cancel/eat/damage)
   appear in any generated text, only field names.

Usage:
    python3 projectile_replay.py --state <slot> --out <dir>
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import projectile_census as pc  # noqa: E402
from jus_ipc import DEFAULT_DIR  # noqa: E402
from jus_plan import validate_watches, PlanError  # noqa: E402

JUSEMU = os.path.join(HERE, "jusemu.py")
CENSUS = os.path.join(HERE, "projectile_census.py")

WATCH_BUDGET = 512
RUN_PLAN_NAME_PREFIX = "projectile_replay"


# ---------------------------------------------------------------------------
# small subprocess wrappers
# ---------------------------------------------------------------------------

def run_jusemu(args, ipc_dir, timeout=120):
    cmd = [sys.executable, JUSEMU, "--ipc-dir", ipc_dir] + args
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE,
                       timeout=timeout)
    return r


def run_jusemu_ok(args, ipc_dir, timeout=120, allow_fail=False):
    r = run_jusemu(args, ipc_dir, timeout=timeout)
    if r.returncode != 0 and not allow_fail:
        raise RuntimeError("jusemu.py %s failed (rc=%d): %s%s" %
                           (" ".join(args), r.returncode, r.stdout, r.stderr))
    return r


def run_census(state_label, ipc_dir, out_dir, colprm_addr, trust_addr=False):
    cmd = [sys.executable, CENSUS, "--no-load", "--state", state_label,
          "--out", out_dir, "--ipc-dir", ipc_dir,
          "--colprm-addr", hex(colprm_addr)]
    if trust_addr:
        cmd.append("--trust-addr")
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
    if r.returncode != 0:
        raise RuntimeError("projectile_census.py failed for %s: %s%s" %
                           (state_label, r.stdout, r.stderr))
    json_path = os.path.join(out_dir, "%s.census.json" % state_label)
    with open(json_path) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Step 1: load + verify
# ---------------------------------------------------------------------------

def load_and_verify(slot, ipc_dir, tmp_dir):
    """`jusemu.py state load <slot>`, verified like projectile_census.py does.

    Returns (load_ack, hb1, hb2, root_addr, objshot_mgr_addr).
    """
    load_result = pc.load_state(slot, ipc_dir)
    ram = pc.Ram(tmp_dir, ipc_dir)
    root_addr, objshot_mgr_addr = pc.self_validate_1_root(ram)
    hb1, hb2 = pc.self_validate_2_heartbeat(ipc_dir)
    return load_result, hb1, hb2, root_addr, objshot_mgr_addr


# ---------------------------------------------------------------------------
# Step 3: build the watch spec from the baseline census
# ---------------------------------------------------------------------------

def record_addr(colprm_addr, idx):
    return colprm_addr + pc.COLPRM_RECORDS_OFFSET + idx * pc.COLPRM_RECORD_STRIDE


def free_record_addrs(colprm_addr, inuse_indices, count=2):
    used = set(inuse_indices)
    free_idxs = [i for i in range(pc.COLPRM_RECORD_COUNT) if i not in used]
    free_idxs.sort()
    out = []
    for i in free_idxs[:count]:
        out.append((i, record_addr(colprm_addr, i)))
    return out


def spawn_neighbor_free_addrs(colprm_addr, inuse_indices, center_idx, radius=2):
    """Free record indices within `radius` of `center_idx` (inclusive).

    A spawning record tends to land next to an already-active neighbour
    (tracker item `jus-2s9k`: in the control run the spawning record was idx 71,
    neighbour of in-use idx 70, and the old "two lowest-index free
    records" heuristic missed it).
    """
    used = set(inuse_indices)
    out = []
    lo = max(0, center_idx - radius)
    hi = min(pc.COLPRM_RECORD_COUNT - 1, center_idx + radius)
    for i in range(lo, hi + 1):
        if i == center_idx or i in used:
            continue
        out.append((i, record_addr(colprm_addr, i)))
    return out


ELEM_WINDOW = 0x28


def build_watch_spec(baseline, budget=WATCH_BUDGET):
    """Fill the watch budget in rank order.

    (a) every in-use record an active ObjShot element links to:
        record+0x3C 0xC bytes (covers +0x40 at relative offset 4),
        the linking element's +0x0 `ELEM_WINDOW` (0x28) bytes, covering
        +0xC x, +0x10 y, +0x18 sentinel word.
    (b) every other in-use record: record+0x3C 0x8 bytes (covers +0x40 at
        relative offset 4).
    (c) spawn-neighbour watches:
        (c1) for every in-use record linked to an active ObjShot element,
             the FREE records at idx-2..idx+2 (its immediate neighbours),
             +0x40, 4 bytes each.
        (c2) the two lowest-index FREE records' +0x40, 4 bytes each (not
             already added by (c1)).
    (d) if budget remains: for the same ObjShot-linked records, +0x130
        0x18 bytes (folds +0x134/+0x138/+0x140/+0x144) and +0xA4 0x10
        bytes (accumulator window).
    (e) if budget still remains: +0x17C 4 bytes per in-use record.

    Rank (c3) -- records 0-12's own +0x40, 4 bytes each -- was dropped:
    rank (b) already watches +0x3C 0x8 bytes for every in-use record
    (including 0-12), which covers +0x40 at relative offset 4, so (c3) was
    a duplicate watch. Removing it frees budget for (d)'s fold/accumulator
    windows, which rank ahead of it (tracker item `jus-2s9k`).

    Returns (watches, meta, notes, used) where `watches` is the plain
    name/addr/len list written to disk, `meta` maps watch name -> a small
    dict describing how to decode it for RESULTS.md, and `notes` is a list
    of human-readable lines for watch_spec.notes.md.
    """
    colprm_addr = int(baseline["meta"]["colprm_manager_addr"], 16)
    records = baseline["colprm_records"]
    inuse_idx = [r["idx"] for r in records]
    linked = [r for r in records if r["objshot_matches"]]
    unlinked = [r for r in records if not r["objshot_matches"]]

    watches = []
    meta = {}
    notes = []
    used = [0]

    def add(name, addr, length, kind, note, **extra):
        if len(watches) >= 32:
            notes.append("SKIPPED (32-watch count cap) %s addr=0x%08X len=0x%X"
                        " -- %s" % (name, addr, length, note))
            return False
        if used[0] + length > budget:
            notes.append("SKIPPED (budget %d/%d) %s addr=0x%08X len=0x%X -- %s"
                        % (used[0], budget, name, addr, length, note))
            return False
        watches.append({"name": name, "addr": int(addr), "len": int(length)})
        d = {"kind": kind, "addr": addr, "len": length}
        d.update(extra)
        meta[name] = d
        used[0] += length
        notes.append("included %s addr=0x%08X len=0x%X -- %s" %
                    (name, addr, length, note))
        return True

    # (a). "element" here is the record's own +0x5C position element (the
    # 0x40-stride array documented in projectile_census.py and
    # INSTRUMENT.md's "Addresses" table -- x at rel +0xC, y at rel +0x10,
    # sentinel word at rel +0x18), not the ObjShot manager's own 0x6C-stride
    # element (kind/lifetime); "linked" still means an active ObjShot
    # element's record_ptr resolves to this record.
    for r in linked:
        add("rec%d_flags" % r["idx"], r["addr"] + 0x3C, 0xC, "record_flags",
           "rank (a): record+0x3C, ObjShot-linked in-use record "
           "(covers +0x40 at rel +0x4)", rel_0x40=0x4, record_idx=r["idx"])
        elem_addr = r["elem"]["addr"]
        if elem_addr:
            add("rec%d_elem" % r["idx"], elem_addr, ELEM_WINDOW, "element",
               "rank (a): record's +0x5C position element +0x0, 0x%X "
               "bytes (x at rel +0xC, y at rel +0x10, word at rel +0x18)"
               % ELEM_WINDOW,
               record_idx=r["idx"])

    # (b)
    for r in unlinked:
        add("rec%d_flags" % r["idx"], r["addr"] + 0x3C, 0x8, "record_flags",
           "rank (b): record+0x3C, other in-use record (covers +0x40 "
           "at rel +0x4)", rel_0x40=0x4, record_idx=r["idx"])

    # (c1): free neighbours (idx-2..idx+2) of every ObjShot-linked in-use
    # record. Dedupe across linked records that share a neighbourhood.
    added_free = set()
    for r in linked:
        for i, addr in spawn_neighbor_free_addrs(colprm_addr, inuse_idx,
                                                 r["idx"], radius=2):
            if i in added_free:
                continue
            if add("free%d_0x40" % i, addr + 0x40, 4, "free_0x40",
                  "rank (c1): free record +0x40 neighbouring "
                  "ObjShot-linked in-use record idx %d (idx-2..idx+2), "
                  "4 bytes" % r["idx"], rel_0x40=0x0, record_idx=i):
                added_free.add(i)

    # (c2): the two lowest-index free records, skipping any already added
    # by (c1).
    for i, addr in free_record_addrs(colprm_addr, inuse_idx, 2):
        if i in added_free:
            notes.append("SKIPPED (already added by rank (c1)) "
                        "free%d_0x40" % i)
            continue
        if add("free%d_0x40" % i, addr + 0x40, 4, "free_0x40",
              "rank (c2): lowest-index free record +0x40, 4 bytes",
              rel_0x40=0x0, record_idx=i):
            added_free.add(i)

    # (d)
    for r in linked:
        add("rec%d_fold" % r["idx"], r["addr"] + 0x130, 0x18, "fold",
           "rank (d): fold window +0x130..+0x148 (folds +0x134/"
           "+0x138/+0x140/+0x144)", record_idx=r["idx"])
        add("rec%d_acc" % r["idx"], r["addr"] + 0xA4, 0x10, "acc",
           "rank (d): accumulator window +0xA4..+0xB4",
           record_idx=r["idx"])

    # (e)
    for r in records:
        add("rec%d_0x17C" % r["idx"], r["addr"] + 0x17C, 4, "0x17C",
           "rank (e): record+0x17C, 4 bytes", record_idx=r["idx"])

    return watches, meta, notes, used[0]


# ---------------------------------------------------------------------------
# Step 4: tail + run plan
# ---------------------------------------------------------------------------

def write_run_plan(path, slot):
    plan = {
        "name": "%s_%s" % (RUN_PLAN_NAME_PREFIX, slot.replace("-", "_")),
        "segments": [
            {"from": 0, "to": 2, "buttons": ["START"]},
            {"from": 150, "to": 152, "buttons": ["START"]},
        ],
        "tail_frames": 0,
    }
    with open(path, "w") as f:
        json.dump(plan, f, indent=1)
    return plan


def do_tail_capture(watch_spec_path, run_plan_path, tail_out, ipc_dir):
    run_jusemu_ok(["watch", "set", watch_spec_path], ipc_dir)
    start_r = run_jusemu_ok(
        ["tail", "start", "--every", "1", "--out", tail_out], ipc_dir)
    start_ack = json.loads(start_r.stdout).get("result", {})
    run_r = run_jusemu_ok(["run", run_plan_path], ipc_dir, timeout=180)
    stop_r = run_jusemu_ok(["tail", "stop"], ipc_dir)
    stop_ack = json.loads(stop_r.stdout).get("result", {})
    return start_ack, run_r.stdout, stop_ack


def read_tail_log(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# Step 6: RESULTS.md
# ---------------------------------------------------------------------------

def decode_watch_series(rows, watch_names, meta):
    """Return {name: [(fc, raw_bytes), ...]} across the tail log.

    `agent_bridge.lua`'s `read_watch()` returns a plain Lua/JSON integer
    (already `memory.read_u32_le`) for any 4-byte watch, and a byte array
    for anything longer. `bytes(int)` misreads the former as "make an
    all-zero buffer of that many bytes" (e.g. `bytes(0)` is an empty
    buffer, not a 4-byte zero word), which both silently corrupts nonzero
    4-byte values and throws on a genuine zero. Pack ints back into
    little-endian bytes instead.
    """
    series = {name: [] for name in watch_names}
    for row in rows:
        fc = row.get("fc")
        v = row.get("v", [])
        for i, name in enumerate(watch_names):
            if i < len(v):
                raw = v[i]
                if isinstance(raw, int):
                    b = struct.pack("<I", raw & 0xFFFFFFFF)
                else:
                    b = bytes(raw)
                series[name].append((fc, b))
    return series


def s32(b, off):
    return struct.unpack_from("<i", b, off)[0]


def u32(b, off):
    return struct.unpack_from("<I", b, off)[0]


def any_nonzero(b):
    return any(x != 0 for x in b)


def summarize_record_flags(name, points, meta):
    """Every frame the +0x40 value (at meta['rel_0x40']) changed."""
    rel = meta["rel_0x40"]
    out = []
    prev = None
    for fc, b in points:
        val = u32(b, rel)
        if prev is not None and val != prev:
            out.append("frame %s: 0x%X -> 0x%X" % (fc, prev, val))
        prev = val
    return out


def summarize_element(name, points):
    """First frame, last nonzero frame, first *teardown* zero frame for x.

    "First zero-x frame" means the first zero frame that comes AFTER the
    last nonzero frame -- i.e. genuine teardown, not a transient zero
    reading that happens to occur mid-life before x goes nonzero again.
    "never" (returned as `None`) if there is no such frame -- either x
    never went nonzero, or it never returned to zero after its last
    nonzero frame within the capture.
    """
    first_frame = points[0][0] if points else None
    last_nonzero = None
    for fc, b in points:
        x_raw = s32(b, 0xC)
        if x_raw != 0:
            last_nonzero = fc
    first_zero = None
    if last_nonzero is not None:
        seen_last_nonzero = False
        for fc, b in points:
            if not seen_last_nonzero:
                if fc == last_nonzero:
                    seen_last_nonzero = True
                continue
            if s32(b, 0xC) == 0:
                first_zero = fc
                break
    return first_frame, last_nonzero, first_zero


def x_series(points):
    """(frame, x_px) pairs for an element window."""
    return [(fc, s32(b, 0xC) / 256.0) for fc, b in points]


def first_nonzero_frame(points):
    for fc, b in points:
        if any_nonzero(b):
            return fc
    return None


def render_results(slot, out_dir, ctx):
    lines = []
    lines.append("# Projectile replay: %s" % slot)
    lines.append("")
    lines.append("Tracker item: `jus-2s9k`.")
    lines.append("")
    lines.append("## Conditions")
    lines.append("")
    lines.append("- Date: %s" % ctx["date"])
    lines.append("- Save state: `%s`" % slot)
    lines.append("- Emulator build: `fork_commit %s`, built `%s`, `app_path %s`"
                % (ctx["build"].get("fork_commit"), ctx["build"].get("built_at"),
                   ctx["build"].get("app_path")))
    lines.append("- Holder label: `%s`" % ctx["holder"])
    lines.append("- JIT: off (`[JIT] Enable=false`, repo default)")
    lines.append("- Framecount at tail start: %s" % ctx["fc_start"])
    lines.append("- Framecount at tail stop: %s" % ctx["fc_end"])
    lines.append("- Observed frames: %d" % ctx["observed_frames"])
    lines.append("- Gaps/dropped (per bridge tail_stop ack): gaps=%s dropped=%s"
                % (ctx["gaps"], ctx["dropped"]))
    lines.append("- `tail.jsonl` size: %s bytes (not committed, by precedent)"
                % ctx["tail_size"])
    lines.append("")

    lines.append("## Baseline (in-use ColPrm records)")
    lines.append("")
    lines.append("See `%s.baseline.census.md` for the full table. In-use "
                "record indices: %s. Active ObjShot elements: %d."
                % (slot, ctx["baseline_idx"], ctx["baseline_objshot_count"]))
    lines.append("- elem_checks_passed=%s elem_checks_failed=%s (of %s total)"
                % (ctx["baseline_elem_passed"], ctx["baseline_elem_failed"],
                   ctx["baseline_elem_total"]))
    if ctx["baseline_elem_failed_indices"]:
        lines.append("- elem_checks_failed_indices: %s"
                    % ", ".join(str(i) for i in ctx["baseline_elem_failed_indices"]))
    lines.append("")

    lines.append("## Watch spec")
    lines.append("")
    lines.append("%d watches, %d/%d bytes. See `watch_spec.json` and "
                "`watch_spec.notes.md` for what was included and skipped."
                % (len(ctx["watches"]), ctx["watch_bytes"], WATCH_BUDGET))
    lines.append("")

    lines.append("## Per-record timeline")
    lines.append("")
    for name in ctx["watch_names"]:
        m = ctx["meta"][name]
        points = ctx["series"].get(name, [])
        if not points:
            lines.append("- `%s` (%s): no samples" % (name, m["kind"]))
            continue
        if m["kind"] in ("record_flags", "free_0x40"):
            changes = summarize_record_flags(name, points, m)
            if changes:
                lines.append("- `%s` +0x40: " % name + "; ".join(changes))
            else:
                lines.append("- `%s` +0x40: no change (stayed 0x%X)"
                            % (name, u32(points[0][1], m["rel_0x40"])))
        elif m["kind"] == "element":
            first_frame, last_nonzero, first_zero = summarize_element(name, points)
            lines.append(
                "- `%s` element: first frame %s, last nonzero-x frame %s, "
                "first zero-x frame %s"
                % (name, first_frame, last_nonzero,
                   first_zero if first_zero is not None else "never"))
        elif m["kind"] in ("fold", "acc"):
            fnz = first_nonzero_frame(points)
            lines.append("- `%s` (%s window): first nonzero frame %s"
                        % (name, m["kind"], fnz if fnz is not None else "never"))
        elif m["kind"] == "0x17C":
            fnz = first_nonzero_frame(points)
            lines.append("- `%s`: first nonzero frame %s"
                        % (name, fnz if fnz is not None else "never"))
        else:
            lines.append("- `%s`: unrecognized kind %s" % (name, m["kind"]))
    lines.append("")

    lines.append("## Post-run (in-use ColPrm records)")
    lines.append("")
    lines.append("See `%s.post.census.md` for the full table. In-use record "
                "indices: %s. Active ObjShot elements: %d."
                % (slot, ctx["post_idx"], ctx["post_objshot_count"]))
    lines.append("- elem_checks_passed=%s elem_checks_failed=%s (of %s total)"
                % (ctx["post_elem_passed"], ctx["post_elem_failed"],
                   ctx["post_elem_total"]))
    if ctx["post_elem_failed_indices"]:
        lines.append("- elem_checks_failed_indices: %s"
                    % ", ".join(str(i) for i in ctx["post_elem_failed_indices"]))
    lines.append("")

    lines.append("## Positive control")
    lines.append("")
    lines.append(ctx["positive_control"])
    lines.append("")

    lines.append("## What this tool could not measure")
    lines.append("")
    lines.append("- Rank (c) watches, as a heuristic for a mid-run spawn: "
                "the free +0x40 neighbours (idx-2..idx+2) of every "
                "ObjShot-linked in-use record (c1) and the two "
                "lowest-index free records (c2). Rank (b) already watches "
                "+0x3C for every in-use record including 0-12, which "
                "covers their +0x40 at relative offset 4, so those "
                "fighter/sub-records are covered without a separate "
                "watch. A spawn landing outside all of these is not "
                "observed by this run's watch spec -- check the post-run "
                "census's in-use list against the baseline's to see if "
                "that happened here.")
    lines.append("")

    if ctx.get("hazards"):
        lines.append("## Hazards encountered")
        lines.append("")
        for h in ctx["hazards"]:
            lines.append("- %s" % h)
        lines.append("")

    return "\n".join(lines)


def compute_positive_control(ctx):
    for name in ctx["watch_names"]:
        m = ctx["meta"][name]
        if m["kind"] != "element":
            continue
        points = ctx["series"].get(name, [])
        xs = x_series(points)
        if len(xs) < 2:
            continue
        nonzero = [(fc, x) for fc, x in xs if x != 0]
        if len(set(x for _, x in nonzero)) > 1:
            first_fc, first_x = nonzero[0]
            last_fc, last_x = nonzero[-1]
            return ("`%s` x moved: frame %s x=%.4f -> frame %s x=%.4f "
                   "(nonzero span only; see per-record timeline for the "
                   "zero-clear frame)"
                   % (name, first_fc, first_x, last_fc, last_x))
    return "FAIL: no watched element x changed across the capture"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--state", required=True, help="savestate slot name")
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--ipc-dir", default=DEFAULT_DIR)
    p.add_argument("--colprm-addr", default=hex(pc.DEFAULT_COLPRM_MANAGER_ADDR))
    p.add_argument("--tmp-dir", default=None)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    slot = args.state
    out_dir = args.out
    ipc_dir = args.ipc_dir
    colprm_addr = int(args.colprm_addr, 0)
    os.makedirs(out_dir, exist_ok=True)
    tmp_dir = args.tmp_dir or os.path.join(out_dir, ".tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    hazards = []

    # 1. load + verify
    load_result, hb1, hb2, root_addr, objshot_mgr_addr = load_and_verify(
        slot, ipc_dir, tmp_dir)
    print("state load ack: %r" % load_result["ack"])
    print("root=0x%08X objshot_mgr=0x%08X heartbeat %s -> %s" %
         (root_addr, objshot_mgr_addr, hb1.get("framecount"),
          hb2.get("framecount")))

    # 2. baseline census. No --trust-addr: the elem check is now "+0x18
    # nonzero" (projectile_census.py), which a genuine in-use record passes
    # without needing to bypass the check. The "every record fails ->
    # abort" guard stays live, so a wrong --colprm-addr still aborts here
    # instead of silently producing a bogus census.
    baseline_label = "%s.baseline" % slot
    baseline = run_census(baseline_label, ipc_dir, out_dir, colprm_addr)
    print("baseline: %d in-use records, %d ObjShot elements" %
         (len(baseline["colprm_records"]), len(baseline["objshot_elements"])))

    # 3. build + validate watch spec
    watches, meta, notes, used = build_watch_spec(baseline)
    try:
        validate_watches(watches)
    except PlanError as e:
        print("error: watch spec failed validation: %s" % e, file=sys.stderr)
        return 1
    watch_spec_path = os.path.join(out_dir, "watch_spec.json")
    with open(watch_spec_path, "w") as f:
        json.dump(watches, f, indent=1)
    notes_path = os.path.join(out_dir, "watch_spec.notes.md")
    with open(notes_path, "w") as f:
        f.write("# watch_spec.json notes: %s\n\n" % slot)
        f.write("%d/%d bytes used.\n\n" % (used, WATCH_BUDGET))
        for line in notes:
            f.write("- %s\n" % line)

    # 4. tail + run plan
    run_plan_path = os.path.join(out_dir, "run_plan.json")
    write_run_plan(run_plan_path, slot)
    tail_out = os.path.join(out_dir, "tail.jsonl")
    try:
        start_ack, run_stdout, stop_ack = do_tail_capture(
            watch_spec_path, run_plan_path, tail_out, ipc_dir)
    except Exception as e:
        hazards.append("tail capture failed: %s" % e)
        raise

    rows = read_tail_log(tail_out)
    watch_names = [w["name"] for w in watches]
    series = decode_watch_series(rows, watch_names, meta)

    # 5. post-run census. No --trust-addr, same reasoning as the baseline
    # census above -- the "+0x18 nonzero" elem check should pass for a
    # genuine in-use record, and the abort guard stays live as a real check.
    post_label = "%s.post" % slot
    post = run_census(post_label, ipc_dir, out_dir, colprm_addr)

    # 6. RESULTS.md
    build_info_path = os.path.join(HERE, "build_info.json")
    with open(build_info_path) as f:
        build_info = json.load(f)
    holder_path = os.path.join(ipc_dir, "HOLDER")
    holder = "unknown"
    if os.path.exists(holder_path):
        with open(holder_path) as f:
            holder = f.readline().strip() or "unknown"

    ctx = {
        "date": time.strftime("%Y-%m-%d"),
        "build": build_info,
        "holder": holder,
        "fc_start": start_ack.get("framecount"),
        "fc_end": stop_ack.get("ended"),
        "observed_frames": len(rows),
        "gaps": stop_ack.get("gaps"),
        "dropped": stop_ack.get("dropped"),
        "tail_size": os.path.getsize(tail_out) if os.path.exists(tail_out) else 0,
        "baseline_idx": [r["idx"] for r in baseline["colprm_records"]],
        "baseline_objshot_count": len(baseline["objshot_elements"]),
        "baseline_elem_total": baseline["meta"]["self_validation"]["elem_checks_total"],
        "baseline_elem_passed": baseline["meta"]["self_validation"]["elem_checks_passed"],
        "baseline_elem_failed": baseline["meta"]["self_validation"]["elem_checks_failed"],
        "baseline_elem_failed_indices": baseline["meta"]["self_validation"]["elem_checks_failed_indices"],
        "post_idx": [r["idx"] for r in post["colprm_records"]],
        "post_objshot_count": len(post["objshot_elements"]),
        "post_elem_total": post["meta"]["self_validation"]["elem_checks_total"],
        "post_elem_passed": post["meta"]["self_validation"]["elem_checks_passed"],
        "post_elem_failed": post["meta"]["self_validation"]["elem_checks_failed"],
        "post_elem_failed_indices": post["meta"]["self_validation"]["elem_checks_failed_indices"],
        "watches": watches,
        "watch_bytes": used,
        "watch_names": watch_names,
        "meta": meta,
        "series": series,
    }
    ctx["positive_control"] = compute_positive_control(ctx)
    ctx["hazards"] = hazards

    results_md = render_results(slot, out_dir, ctx)
    with open(os.path.join(out_dir, "RESULTS.md"), "w") as f:
        f.write(results_md)

    print("wrote %s" % os.path.join(out_dir, "RESULTS.md"))
    print("positive control: %s" % ctx["positive_control"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
