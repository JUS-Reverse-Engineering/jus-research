#!/usr/bin/env python3
"""Capture one Ichigo Y-variant projectile's backing structures, byte for byte.

For a single savestate slot this loads the state, unpauses the battle, waits
for a P1-side kind-0x00 ObjShot element to exist, and then dumps every
structure behind it: the ObjShot element, the spawned entity's first 0x100
bytes, the whole ColPrm record, every node on the record's node list, and the
resolved collision entry. Two exact one-frame position deltas are sampled
through the bridge's per-frame tail log.

Output is deliberately field-offsets-only: no gameplay names appear anywhere,
only offsets, the same rule `projectile_census.py` follows.

Layout constants and the RAM reader are imported from `projectile_census.py`
rather than restated here -- see that module's docstring for the citations.

Spawn-detection rule
--------------------
A candidate is an element on the ObjShot manager's active list whose
`+0x1A` kind byte is 0x00 and whose ColPrm record (`[element+0x2C]+0x10`)
has `+0x34` low nibble == 1 (P1 side) and `+0x40 & 0x200 == 0` (in use).
The full 72-slot element array is also scanned each pass and its kind-0x00
slots recorded, but array membership alone never counts as a spawn.

Three phases, because the shot only lives ~22 frames
----------------------------------------------------
The emulator free-runs at ~60fps whenever no plan is executing
(`scripts/emu/README.md`, "Frame counting"), and one `jusemu.py dump` round
trip costs roughly 5 battle frames. These states are saved with the pause
menu open; a START press toggles it, so the battle only advances around a
plan. Two measured facts set the shape of this tool:

- The element for one of these shots is on the active list for about 22
  frames (its `+0x18` word counts down 19 -> 0), so a scan-then-step loop
  with a few dumps per scan cannot reliably land inside its life, and a
  half-dozen dumps of a *running* shot would read half of it after the
  teardown.
- The pause menu does not open on the frame START is pressed. Measured on
  `pc-ichigo-fy-vegeta`: a START press at plan frames 0-2 resumed the battle
  at frame 17, and a second press at frames 9-11 froze it at frame 21. So
  closing the menu costs ~16 frames and opening it ~11. A naive
  START / N frames / START step plan therefore freezes the battle ~11 frames
  later than intended, which is what made a first attempt miss every shot.

So a capture runs in phases:

0. Scan once while still paused at load. Some of these states already have
   the shot in flight at the moment of the save, and that is the easiest
   capture there is.
1. **Locate.** One tail run over a long no-input plan, watching only the
   ObjShot manager's 4-byte active-list head (`manager+0x00`). The first
   frame where it turns nonzero gives both the spawn frame and the element's
   address, at one watch and 4 bytes per frame.
2. **Freeze.** A fresh load and a plan that presses START
   `PAUSE_LATENCY` frames before the wanted frame, so the menu opens while
   the shot is a few frames into its life. A scan confirms the freeze, and
   several freeze offsets are tried before giving up.
3. **Dump.** With the battle frozen, every structure is dumped at leisure,
   then one velocity plan unpauses again with a per-frame tail running.

Progress is counted in *battle* frames (the plans' own frame counts), not in
heartbeat framecount deltas, which keep ticking while the battle is paused.
Both are recorded.

Why the velocity samples come from the tail log
-----------------------------------------------
A bare "advance one frame, read again" pair of commands straddles an unknown
number of free-run frames. The bridge's `tail start --every 1` does log
watched bytes once per emulated frame with that frame's count, so two
*consecutive* tail rows are a true one-frame delta. The velocity plan
unpauses, runs a handful of no-input frames, and re-pauses, with the tail
running the whole time; deltas across frozen (paused) frames are zero, so
the two reported samples are the first two consecutive-frame deltas that
moved, and the full per-frame series is recorded alongside them.
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import projectile_census as pc  # noqa: E402
from jus_plan import validate_plan  # noqa: E402

JUSEMU = os.path.join(HERE, "jusemu.py")

RECORD_SIDE_OFFSET = 0x34
RECORD_SIDE_P1_NIBBLE = 1
ELEMENT_OWNER_OFFSET = 0x08
ELEMENT_PREV_X_OFFSET = 0x14
ELEMENT_PREV_Y_OFFSET = 0x18
ENTITY_DUMP_LEN = 0x100
ENTRY_LEN = 0x14
ELEM_WATCH_LEN = 0x1C

# The ObjShot element's own `+0x0C`/`+0x10` hold RAM pointers, not positions
# (measured: `0x023DCB00` / `0x02228F68` on `pc-ichigo-fy-vegeta`). The x/y
# pair lives on the *other*, 0x40-stride element the ColPrm record points at
# through `+0x5C` -- that is the element `projectile_census.py` reads
# `+0x0C`/`+0x10` as `x_raw`/`y_raw` and sanity-checks at `+0x18`. Both are
# captured; positions and per-frame deltas come from this one.
RECORD_POS_ELEM_OFFSET = 0x5C
POS_ELEM_LEN = 0x40

DEFAULT_N_FRAMES = 3
MAX_TOTAL_FRAMES = 240
VELOCITY_PLAN_FRAMES = 6
HOLD_Y_FRAMES = 60

# Frames between the start of a START press and the pause menu actually
# opening, measured on `pc-ichigo-fy-vegeta` (press at plan frames 9-11,
# battle froze at frame 21).
PAUSE_LATENCY = 11
# Frames into the element's life to aim the freeze at, tried in order.
FREEZE_OFFSETS = [4, 8, 12, 2, 16]
# Frames of no input after the freeze press, so the plan does not end on a
# held button.
FREEZE_TAIL_FRAMES = 20


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def hexdump_rows(data, base=0, width=16):
    rows = []
    for off in range(0, len(data), width):
        chunk = data[off:off + width]
        rows.append("`+0x%04X` | %s" % (
            base + off, " ".join("%02X" % b for b in chunk)))
    return rows


def heartbeat_framecount(ipc_dir):
    path = os.path.join(ipc_dir, "heartbeat.json")
    with open(path) as f:
        return json.load(f).get("framecount")


def run_jusemu(args, ipc_dir, timeout=180):
    cmd = [sys.executable, JUSEMU, "--ipc-dir", ipc_dir] + args
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE,
                       timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError("jusemu.py %s failed (rc=%d): %s%s" %
                           (" ".join(args), r.returncode, r.stdout, r.stderr))
    return r


def write_plan(path, name, segments):
    plan = {"name": name, "segments": segments, "tail_frames": 0}
    validate_plan(plan)
    with open(path, "w") as f:
        json.dump(plan, f, indent=1)
    return plan


def record_index(colprm_addr, rec_addr):
    base = colprm_addr + pc.COLPRM_RECORDS_OFFSET
    delta = rec_addr - base
    if delta < 0 or delta % pc.COLPRM_RECORD_STRIDE:
        return None
    idx = delta // pc.COLPRM_RECORD_STRIDE
    return idx if idx < pc.COLPRM_RECORD_COUNT else None


def inuse_record_indices(ram, colprm_addr):
    base = colprm_addr + pc.COLPRM_RECORDS_OFFSET
    out = []
    for i in range(pc.COLPRM_RECORD_COUNT):
        rec = base + i * pc.COLPRM_RECORD_STRIDE
        if not (ram.u32(rec + pc.COLPRM_INUSE_FLAG_OFFSET)
                & pc.COLPRM_INUSE_BIT):
            out.append(i)
    return out


# ---------------------------------------------------------------------------
# scanning
# ---------------------------------------------------------------------------

def array_kind0_slots(ram, mgr_addr):
    """Every slot in the declared 72-element array whose `+0x1A` is 0x00."""
    base = ram.u32(mgr_addr + pc.OBJSHOT_ELEM_ARRAY_OFFSET)
    slots = []
    for i in range(pc.OBJSHOT_ELEM_COUNT):
        addr = base + i * pc.OBJSHOT_ELEM_STRIDE
        try:
            if ram.u8(addr + pc.OBJSHOT_ELEM_KIND_OFFSET) == 0:
                slots.append(i)
        except RuntimeError:
            break
    return slots


def fresh_read(ram, mgr_addr, colprm_addr):
    """Drop cached segments and re-dump the two managers in bulk.

    Bulk dumps matter: per-word reads of the 72 elements and 128 records cost
    ~200 `jusemu.py dump` round trips per scan.
    """
    ram.segments = []
    ram.small_cache = {}
    ram.load_segment(mgr_addr, pc.OBJSHOT_MGR_SIZE)
    ram.load_segment(colprm_addr, pc.COLPRM_MGR_SIZE)


def scan_for_candidate(ram, mgr_addr, colprm_addr):
    """One scan pass. Returns (candidate_or_None, scan_summary dict)."""
    fresh_read(ram, mgr_addr, colprm_addr)
    elements = pc.walk_objshot_active_list(ram, mgr_addr)
    candidate = None
    considered = []
    for el in elements:
        rec_addr = el.get("record_ptr")
        row = {"element_addr": pc.hexw(el["addr"]),
               "kind": pc.hexb(el["kind"]),
               "entity_ptr": pc.hexw(el["entity_ptr"]),
               "record_ptr": pc.hexw(rec_addr) if rec_addr else None,
               "reject": None}
        if el["kind"] != 0x00:
            row["reject"] = "kind != 0x00"
        elif not (rec_addr and pc.in_ram(rec_addr)):
            row["reject"] = "[entity+0x10] is not a RAM pointer"
        else:
            side = ram.u8(rec_addr + RECORD_SIDE_OFFSET) & 0x0F
            flags = ram.u32(rec_addr + pc.COLPRM_INUSE_FLAG_OFFSET)
            row["record_0x34_low_nibble"] = side
            row["record_0x40"] = pc.hexw(flags)
            if side != RECORD_SIDE_P1_NIBBLE:
                row["reject"] = "+0x34 low nibble != 1"
            elif flags & pc.COLPRM_INUSE_BIT:
                row["reject"] = "+0x40 & 0x200 != 0 (not in use)"
            elif candidate is None:
                candidate = {"element": el, "record_addr": rec_addr}
        considered.append(row)
    summary = {
        "objshot_active_count": len(elements),
        "objshot_array_kind0_slots": array_kind0_slots(ram, mgr_addr),
        "inuse_record_indices": inuse_record_indices(ram, colprm_addr),
        "active_elements": considered,
    }
    return candidate, summary


# ---------------------------------------------------------------------------
# structure dumps
# ---------------------------------------------------------------------------

def dump_structures(ram, candidate, colprm_addr):
    el = candidate["element"]
    el_addr = el["addr"]
    rec_addr = candidate["record_addr"]
    el_bytes = ram.read(el_addr, pc.OBJSHOT_ELEM_STRIDE)
    rec_bytes = ram.read(rec_addr, pc.COLPRM_RECORD_STRIDE)
    ent_addr = el["entity_ptr"]
    ent_bytes = ram.read(ent_addr, ENTITY_DUMP_LEN)

    authored_base, authored_err = pc.read_authored_base(ram, rec_addr)
    nodes = pc.read_nodes(ram, ram.u32(rec_addr + pc.RECORD_NODE_HEAD_OFFSET),
                          authored_base=authored_base)
    node_rows = []
    for n in nodes:
        addr = n["addr"]
        row = dict(n)
        row["bytes"] = ram.read(addr, pc.NODE_STRIDE).hex()
        entry_ptr = n.get("entry_ptr")
        if entry_ptr and pc.in_ram(entry_ptr):
            row["entry_bytes"] = ram.read(entry_ptr, ENTRY_LEN).hex()
        else:
            row["entry_bytes"] = None
        node_rows.append(row)

    pos_addr = struct.unpack_from("<I", rec_bytes, RECORD_POS_ELEM_OFFSET)[0]
    pos_elem = {"addr": pc.hexw(pos_addr), "bytes": None,
                "x_0x0C": None, "y_0x10": None, "word_0x18": None,
                "note": "[record+0x5C], the 0x40-stride element whose "
                        "+0x0C/+0x10 projectile_census.py reads as x/y"}
    if pos_addr and pc.in_ram(pos_addr):
        pb = ram.read(pos_addr, POS_ELEM_LEN)
        pos_elem.update({
            "bytes": pb.hex(),
            "x_0x0C": struct.unpack_from("<i", pb, pc.ELEMENT_X_OFFSET)[0],
            "y_0x10": struct.unpack_from("<i", pb, pc.ELEMENT_Y_OFFSET)[0],
            "word_0x18": struct.unpack_from("<I", pb, 0x18)[0],
        })

    return {
        "position_element": pos_elem,
        "element": {
            "addr": pc.hexw(el_addr),
            "bytes": el_bytes.hex(),
            "kind": pc.hexb(el["kind"]),
            "owner_obj_ptr": pc.hexw(struct.unpack_from(
                "<I", el_bytes, ELEMENT_OWNER_OFFSET)[0]),
            "entity_ptr": pc.hexw(ent_addr),
            "word_0x0C": pc.hexw(struct.unpack_from(
                "<I", el_bytes, pc.ELEMENT_X_OFFSET)[0]),
            "word_0x10": pc.hexw(struct.unpack_from(
                "<I", el_bytes, pc.ELEMENT_Y_OFFSET)[0]),
            "word_0x14": pc.hexw(struct.unpack_from(
                "<I", el_bytes, ELEMENT_PREV_X_OFFSET)[0]),
            "s32_0x18": struct.unpack_from("<i", el_bytes,
                                           ELEMENT_PREV_Y_OFFSET)[0],
            "u16_0x18": struct.unpack_from("<H", el_bytes,
                                           ELEMENT_PREV_Y_OFFSET)[0],
            "reading_note": (
                "+0x18 is read two ways: as a s32 and as the u16 word "
                "projectile_census.py labels the lifetime "
                "(OBJSHOT_ELEM_LIFETIME_OFFSET = 0x18, ram.u16). Both are "
                "recorded; u16_0x18 is the census reading. +0x0C/+0x10 on "
                "*this* element are RAM pointers, not x/y -- see "
                "position_element."),
        },
        "entity": {"addr": pc.hexw(ent_addr), "bytes": ent_bytes.hex(),
                   "len": ENTITY_DUMP_LEN},
        "record": {"addr": pc.hexw(rec_addr),
                   "idx": record_index(colprm_addr, rec_addr),
                   "bytes": rec_bytes.hex(),
                   "authored_base": pc.hexw(authored_base)
                   if authored_base else None,
                   "authored_base_error": authored_err},
        "nodes": node_rows,
    }


# ---------------------------------------------------------------------------
# velocity sampling
# ---------------------------------------------------------------------------

def sample_velocity(pos_addr, ipc_dir, tmp_dir):
    """Two exact one-frame (dx, dy) samples, from consecutive tail rows.

    `pos_addr` is `[record+0x5C]`, the element carrying x/y at
    `+0x0C`/`+0x10`.
    """
    spec_path = os.path.join(tmp_dir, "elem_watch.json")
    with open(spec_path, "w") as f:
        json.dump([{"name": "elem", "addr": pos_addr, "len": ELEM_WATCH_LEN}],
                  f)
    plan_path = os.path.join(tmp_dir, "velocity_plan.json")
    vel_segments = step_segments(VELOCITY_PLAN_FRAMES)
    write_plan(plan_path, "ichigo_y_velocity", vel_segments)
    tail_out = os.path.join(tmp_dir, "velocity_tail.jsonl")

    run_jusemu(["watch", "set", spec_path], ipc_dir)
    run_jusemu(["tail", "start", "--every", "1", "--out", tail_out], ipc_dir)
    try:
        run_jusemu(["run", plan_path], ipc_dir)
    finally:
        run_jusemu(["tail", "stop"], ipc_dir)

    positions = []
    if os.path.exists(tail_out):
        with open(tail_out) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                v = row.get("v") or []
                if not v:
                    continue
                raw = v[0]
                b = (struct.pack("<I", raw & 0xFFFFFFFF)
                     if isinstance(raw, int) else bytes(raw))
                if len(b) < pc.ELEMENT_Y_OFFSET + 4:
                    continue
                positions.append({
                    "fc": row.get("fc"),
                    "x": struct.unpack_from("<i", b, pc.ELEMENT_X_OFFSET)[0],
                    "y": struct.unpack_from("<i", b, pc.ELEMENT_Y_OFFSET)[0],
                })

    deltas = []
    for a, b in zip(positions, positions[1:]):
        if a["fc"] is None or b["fc"] is None or b["fc"] - a["fc"] != 1:
            continue
        deltas.append({"from_fc": a["fc"], "to_fc": b["fc"],
                       "dx": b["x"] - a["x"], "dy": b["y"] - a["y"]})
    samples = [d for d in deltas if d["dx"] or d["dy"]][:2]
    return {"positions": positions, "deltas": deltas, "samples": samples,
            "sample_rule": (
                "consecutive-framecount tail rows; the two reported samples "
                "are the first two such deltas with a nonzero dx or dy, "
                "because the plan's START frames re-pause the battle and "
                "paused frames give a zero delta. Every delta is in "
                "`deltas`."),
            "plan_segments": vel_segments,
            "tail_log": tail_out,
            "watch": {"addr": pc.hexw(pos_addr), "len": ELEM_WATCH_LEN,
                      "what": "[record+0x5C]"}}


# ---------------------------------------------------------------------------
# capture
# ---------------------------------------------------------------------------

def step_segments(n_frames):
    """START (unpause) / n_frames of no input / START (re-pause)."""
    return [
        {"from": 0, "to": 2, "buttons": ["START"]},
        {"from": 3, "to": 2 + n_frames, "buttons": []},
        {"from": 3 + n_frames, "to": 5 + n_frames, "buttons": ["START"]},
    ]


def locate_segments(total_frames, hold_y=False):
    """START (unpause) then no input (or Y held first) for `total_frames`."""
    segs = [{"from": 0, "to": 2, "buttons": ["START"]}]
    at = 3
    if hold_y:
        segs.append({"from": at, "to": at + HOLD_Y_FRAMES - 1,
                     "buttons": ["Y"]})
        at += HOLD_Y_FRAMES
    segs.append({"from": at, "to": at + total_frames - 1, "buttons": []})
    return segs


def freeze_segments(press_at, hold_y=False):
    """The locate plan, with a START press at plan frame `press_at`."""
    segs = [{"from": 0, "to": 2, "buttons": ["START"]}]
    at = 3
    if hold_y:
        segs.append({"from": at, "to": at + HOLD_Y_FRAMES - 1,
                     "buttons": ["Y"]})
        at += HOLD_Y_FRAMES
    if press_at > at:
        segs.append({"from": at, "to": press_at - 1, "buttons": []})
    segs.append({"from": press_at, "to": press_at + 2, "buttons": ["START"]})
    segs.append({"from": press_at + 3,
                 "to": press_at + 2 + FREEZE_TAIL_FRAMES, "buttons": []})
    return segs


def plan_frame_count(segments):
    return segments[-1]["to"] + 1


def tail_watch_series(spec, plan_segments, name, ipc_dir, tmp_dir):
    """Run one plan with a per-frame tail and return [(fc, bytes), ...]."""
    spec_path = os.path.join(tmp_dir, "%s_watch.json" % name)
    with open(spec_path, "w") as f:
        json.dump(spec, f)
    plan_path = os.path.join(tmp_dir, "%s_plan.json" % name)
    write_plan(plan_path, "ichigo_y_%s" % name, plan_segments)
    tail_out = os.path.join(tmp_dir, "%s_tail.jsonl" % name)
    run_jusemu(["watch", "set", spec_path], ipc_dir)
    run_jusemu(["tail", "start", "--every", "1", "--out", tail_out], ipc_dir)
    try:
        run_jusemu(["run", plan_path], ipc_dir, timeout=600)
    finally:
        run_jusemu(["tail", "stop"], ipc_dir)
    rows = []
    if os.path.exists(tail_out):
        with open(tail_out) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                v = row.get("v") or []
                if not v:
                    continue
                raw = v[0]
                b = (struct.pack("<I", raw & 0xFFFFFFFF)
                     if isinstance(raw, int) else bytes(raw))
                rows.append((row.get("fc"), b))
    return rows, tail_out


def locate_spawn(mgr_addr, total_frames, ipc_dir, tmp_dir, hold_y=False):
    """Watch `manager+0x00` per frame; report the first nonzero head.

    Returns a dict with `element_addr`, `spawn_plan_frame` (frames after the
    plan's first frame) and the head series.
    """
    segs = locate_segments(total_frames, hold_y=hold_y)
    rows, tail_out = tail_watch_series(
        [{"name": "head", "addr": mgr_addr + pc.OBJSHOT_ACTIVE_HEAD_OFFSET,
          "len": 4}], segs, "locate", ipc_dir, tmp_dir)
    series = [(fc, struct.unpack_from("<I", b, 0)[0]) for fc, b in rows]
    element_addr = None
    spawn_frame = None
    if series:
        f0 = series[0][0]
        for fc, head in series:
            if head:
                element_addr, spawn_frame = head, fc - f0
                break
    return {
        "plan_segments": segs,
        "plan_frames": plan_frame_count(segs),
        "tail_log": tail_out,
        "tail_rows": len(series),
        "head_nonzero_frames": [fc - series[0][0] for fc, h in series if h]
        if series else [],
        "element_addr": pc.hexw(element_addr) if element_addr else None,
        "element_addr_int": element_addr,
        "spawn_plan_frame": spawn_frame,
        "head_watch": pc.hexw(mgr_addr + pc.OBJSHOT_ACTIVE_HEAD_OFFSET),
    }


def capture(slot, ipc_dir, out_dir, colprm_addr, n_frames, tmp_dir,
            hold_y=False, max_total_frames=MAX_TOTAL_FRAMES):
    load_result = pc.load_state(slot, ipc_dir)
    ram = pc.Ram(tmp_dir, ipc_dir)
    root_addr, mgr_addr = pc.self_validate_1_root(ram)
    hb1, hb2 = pc.self_validate_2_heartbeat(ipc_dir)

    fc_at_load = heartbeat_framecount(ipc_dir)
    run_kind = "hold-Y" if hold_y else "no-input"

    # --- phase 0: already in flight at the save? ---------------------------
    scans = []
    candidate, summary = scan_for_candidate(ram, mgr_addr, colprm_addr)
    summary.update({"scan": 0, "phase": "0 (paused at load)",
                    "framecount": heartbeat_framecount(ipc_dir),
                    "battle_frames_stepped": 0,
                    "found": candidate is not None})
    scans.append(summary)

    locate = None
    freeze_attempts = []
    battle_frames = 0
    if candidate is None:
        # --- phase 1: locate the spawn frame and the element address -------
        locate = locate_spawn(mgr_addr, max_total_frames, ipc_dir, tmp_dir,
                              hold_y=hold_y)
        battle_frames = locate["plan_frames"]
        if locate["spawn_plan_frame"] is not None:
            # --- phase 2: freeze a few frames into the shot's life ---------
            for off in FREEZE_OFFSETS:
                press_at = max(3, locate["spawn_plan_frame"] + off
                               - PAUSE_LATENCY)
                segs = freeze_segments(press_at, hold_y=hold_y)
                pc.load_state(slot, ipc_dir)
                plan_path = os.path.join(tmp_dir, "freeze_plan.json")
                write_plan(plan_path, "ichigo_y_freeze", segs)
                run_jusemu(["run", plan_path], ipc_dir, timeout=600)
                battle_frames += plan_frame_count(segs)
                candidate, summary = scan_for_candidate(ram, mgr_addr,
                                                        colprm_addr)
                summary.update({
                    "scan": len(scans),
                    "phase": "2 (freeze, offset %d, START at plan frame %d)"
                             % (off, press_at),
                    "framecount": heartbeat_framecount(ipc_dir),
                    "battle_frames_stepped": battle_frames,
                    "found": candidate is not None})
                scans.append(summary)
                freeze_attempts.append({"freeze_offset": off,
                                        "press_at_plan_frame": press_at,
                                        "plan_segments": segs,
                                        "found": candidate is not None})
                if candidate is not None:
                    break

    fc_at_detect = heartbeat_framecount(ipc_dir) if candidate else None

    meta = {
        "slot": slot,
        "date": "2026-09-11",
        "run_kind": run_kind,
        "n_frames": n_frames,
        "max_total_frames": max_total_frames,
        "pause_latency_frames": PAUSE_LATENCY,
        "freeze_offsets_tried": [a["freeze_offset"] for a in freeze_attempts],
        "locate": locate,
        "freeze_attempts": freeze_attempts,
        "plan_shape_note": (
            "phase 0 scans the state as loaded (paused). Phase 1 runs "
            "START (frames 0-2) then no input for up to %d frames with a "
            "per-frame tail on the ObjShot manager's `+0x00` active-list "
            "head, which gives the spawn frame and the element address. "
            "Phase 2 reloads and runs the same plan with a START press %d "
            "frames before the wanted frame, so the pause menu opens a few "
            "frames into the shot's life; every structure dump then reads a "
            "frozen battle." % (max_total_frames, PAUSE_LATENCY)),
        "load_ack": load_result.get("ack"),
        "load_note": (
            "dummy-sidecar states ack ok:false 'did not settle' but do load; "
            "verified by [0x02172960] root pointer nonzero and an advancing "
            "heartbeat framecount"),
        "root_addr": pc.hexw(root_addr),
        "objshot_manager_addr": pc.hexw(mgr_addr),
        "colprm_manager_addr": pc.hexw(colprm_addr),
        "heartbeat_before": hb1,
        "heartbeat_after": hb2,
        "framecount_at_load": fc_at_load,
        "framecount_at_detect": fc_at_detect,
        "battle_frames_stepped": battle_frames,
        "frames_stepped_since_unpause": (
            locate["spawn_plan_frame"] if locate
            and locate["spawn_plan_frame"] is not None else battle_frames),
        "framecount_delta_since_load": (
            None if fc_at_detect is None or fc_at_load is None
            else fc_at_detect - fc_at_load),
        "frame_counting_note": (
            "`battle_frames_stepped` counts the frames every plan ran "
            "(including their own START press windows and the ~16 frames "
            "the pause menu takes to close). `frames_stepped_since_unpause` "
            "is the phase-1 spawn frame when phase 1 ran, i.e. plan frames "
            "from the unpause press to the frame the element appeared. The "
            "heartbeat framecount keeps ticking while the battle is paused, "
            "so a framecount delta is an upper bound, not battle time."),
        "scan_count": len(scans),
        "spawn_detection_rule": (
            "active-list element with +0x1A == 0x00 whose "
            "[[element+0x2C]+0x10] record has +0x34 low nibble == 1 and "
            "+0x40 & 0x200 == 0"),
        "dump_calls": ram.dump_calls,
    }

    result = {"meta": meta, "spawned": candidate is not None, "scans": scans}
    if candidate is not None:
        result.update(dump_structures(ram, candidate, colprm_addr))
        pos = result["position_element"]
        if pos["bytes"] is None:
            result["velocity"] = {
                "positions": [], "deltas": [], "samples": [],
                "error": "[record+0x5C] is not a RAM pointer; no position "
                         "element to sample"}
        else:
            pos_addr = int(pos["addr"], 16)
            result["velocity"] = sample_velocity(pos_addr, ipc_dir, tmp_dir)
            ram.segments = []
            ram.small_cache = {}
            after = ram.read(pos_addr, POS_ELEM_LEN)
            result["position_element_after_velocity_plan"] = {
                "framecount": heartbeat_framecount(ipc_dir),
                "x_0x0C": struct.unpack_from("<i", after,
                                             pc.ELEMENT_X_OFFSET)[0],
                "y_0x10": struct.unpack_from("<i", after,
                                             pc.ELEMENT_Y_OFFSET)[0],
                "bytes": after.hex(),
            }
    elif locate is not None and locate["spawn_plan_frame"] is None:
        result["not_spawned_note"] = (
            "the ObjShot manager's `+0x00` active-list head never turned "
            "nonzero across %d no-input frames after the unpause press, so "
            "no element spawned at all. Per-scan ObjShot element counts and "
            "in-use record indices are in `scans`; the head series is in "
            "`meta.locate`." % max_total_frames)
    else:
        result["not_spawned_note"] = (
            "an element did spawn (phase 1 saw the active-list head turn "
            "nonzero) but no freeze offset landed a P1-side kind-0x00 "
            "element with a resolvable `[entity+0x10]` record; see "
            "`meta.freeze_attempts` and `scans`")
    result["meta"]["dump_calls"] = ram.dump_calls

    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "%s.capture.json" % slot)
    with open(json_path, "w") as f:
        json.dump(result, f, indent=1)
    md_path = os.path.join(out_dir, "%s.capture.md" % slot)
    with open(md_path, "w") as f:
        f.write(render_markdown(result))
    return result, json_path, md_path


# ---------------------------------------------------------------------------
# markdown
# ---------------------------------------------------------------------------

def render_markdown(result):
    m = result["meta"]
    L = ["# Capture: `%s`" % m["slot"], ""]
    L.append("- run kind: %s, N = %d, scans = %d"
             % (m["run_kind"], m["n_frames"], m["scan_count"]))
    L.append("- framecount at load %s, at detect %s; battle frames stepped "
             "%s (%s)" % (m["framecount_at_load"], m["framecount_at_detect"],
                          m["battle_frames_stepped"],
                          m["frame_counting_note"]))
    L.append("- plan shape: %s" % m["plan_shape_note"])
    if m["locate"]:
        lo = m["locate"]
        L.append("- phase 1 (locate): plan `%r`, %d tail rows, active-list "
                 "head watch `%s`, first nonzero at plan frame %s, element "
                 "`%s`" % (lo["plan_segments"], lo["tail_rows"],
                           lo["head_watch"], lo["spawn_plan_frame"],
                           lo["element_addr"]))
    else:
        L.append("- phase 1 (locate) not needed: the shot was already in "
                 "flight in the savestate")
    for a in m["freeze_attempts"]:
        L.append("- phase 2 attempt: freeze offset %d, START at plan frame "
                 "%d, found %s" % (a["freeze_offset"],
                                   a["press_at_plan_frame"], a["found"]))
    L.append("- root `%s`, ObjShot manager `%s`, ColPrm manager `%s`"
             % (m["root_addr"], m["objshot_manager_addr"],
                m["colprm_manager_addr"]))
    L.append("- spawn-detection rule: %s" % m["spawn_detection_rule"])
    L.append("- load ack: `%r` (%s)" % (m["load_ack"], m["load_note"]))
    L.append("- spawned: **%s**" % result["spawned"])
    L.append("")

    L.append("## Scans")
    L.append("")
    L.append("| scan | phase | framecount | battle frames stepped | active "
             "elements | kind-0x00 array slots | in-use records | found |")
    L.append("|---|---|---|---|---|---|---|---|")
    for s in result["scans"]:
        L.append("| %d | %s | %s | %s | %d | %s | %s | %s |" % (
            s["scan"], s["phase"], s["framecount"],
            s["battle_frames_stepped"],
            s["objshot_active_count"],
            ",".join(str(i) for i in s["objshot_array_kind0_slots"]) or "-",
            ",".join(str(i) for i in s["inuse_record_indices"]) or "-",
            s["found"]))
    L.append("")

    if not result["spawned"]:
        L.append(result["not_spawned_note"])
        L.append("")
        return "\n".join(L)

    el = result["element"]
    L.append("## Element `%s` (0x6C bytes)" % el["addr"])
    L.append("")
    L.append("- `+0x1A` kind %s, `+0x08` %s, `+0x2C` %s"
             % (el["kind"], el["owner_obj_ptr"], el["entity_ptr"]))
    L.append("- `+0x0C` %s, `+0x10` %s, `+0x14` %s, `+0x18` s32 %d / u16 %d"
             % (el["word_0x0C"], el["word_0x10"], el["word_0x14"],
                el["s32_0x18"], el["u16_0x18"]))
    L.append("- %s" % el["reading_note"])
    L.append("")
    L.extend(_hex_table(el["bytes"]))

    pos = result["position_element"]
    L.append("## Position element `%s` (`[record+0x5C]`, 0x40 bytes)"
             % pos["addr"])
    L.append("")
    L.append("- %s" % pos["note"])
    if pos["bytes"] is None:
        L.append("- not a RAM pointer; not dumped")
        L.append("")
    else:
        L.append("- `+0x0C` x %d, `+0x10` y %d, `+0x18` %s"
                 % (pos["x_0x0C"], pos["y_0x10"], pc.hexw(pos["word_0x18"])))
        L.append("")
        L.extend(_hex_table(pos["bytes"]))

    ent = result["entity"]
    L.append("## Entity `%s` first 0x100 bytes" % ent["addr"])
    L.append("")
    L.extend(_hex_table(ent["bytes"]))

    rec = result["record"]
    L.append("## Record idx %s at `%s` (0x188 bytes)"
             % (rec["idx"], rec["addr"]))
    L.append("")
    L.append("- authored table base: %s%s" % (
        rec["authored_base"],
        " (%s)" % rec["authored_base_error"]
        if rec["authored_base_error"] else ""))
    L.append("")
    L.extend(_hex_table(rec["bytes"]))

    L.append("## Nodes (%d)" % len(result["nodes"]))
    L.append("")
    for i, n in enumerate(result["nodes"]):
        L.append("### Node %d at `%s` (0x2C bytes)" % (i, pc.hexw(n["addr"])))
        L.append("")
        L.append("- `+0x08` %s, `+0x0C` %s, `+0x10` entry %s, `+0x14` %s, "
                 "`+0x18` %s" % (pc.hexw(n.get("obj")), pc.hexw(n.get("rec")),
                                 pc.hexw(n.get("entry_ptr")),
                                 pc.hexw(n.get("field_0x14")),
                                 pc.hexw(n.get("field_0x18"))))
        L.append("- entry id %s (%s)" % (n.get("id"), n.get("id_kind")))
        L.append("- entry `+0x08` %s" % pc.hexw(n.get("entry_0x08"))
                 if n.get("entry_0x08") is not None else "- entry `+0x08` -")
        L.append("")
        L.extend(_hex_table(n["bytes"]))
        if n.get("entry_bytes"):
            L.append("Entry `%s` (0x14 bytes):" % pc.hexw(n["entry_ptr"]))
            L.append("")
            L.extend(_hex_table(n["entry_bytes"]))

    v = result["velocity"]
    L.append("## Per-frame position samples")
    L.append("")
    if "error" in v:
        L.append(v["error"])
        L.append("")
        return "\n".join(L)
    L.append("Watch `%s` (%s) len 0x%X, tail every 1 frame, plan `%r`."
             % (v["watch"]["addr"], v["watch"]["what"], v["watch"]["len"],
                v["plan_segments"]))
    L.append("")
    L.append("%s" % v["sample_rule"])
    L.append("")
    L.append("| framecount | `+0x0C` x | `+0x10` y |")
    L.append("|---|---|---|")
    for p in v["positions"]:
        L.append("| %s | %d | %d |" % (p["fc"], p["x"], p["y"]))
    L.append("")
    L.append("| framecount pair | dx | dy |")
    L.append("|---|---|---|")
    for dl in v["deltas"]:
        L.append("| %s -> %s | %d | %d |"
                 % (dl["from_fc"], dl["to_fc"], dl["dx"], dl["dy"]))
    L.append("")
    for i, s in enumerate(v["samples"]):
        L.append("- sample %d: fc %s -> %s, dx %d, dy %d"
                 % (i, s["from_fc"], s["to_fc"], s["dx"], s["dy"]))
    if not v["samples"]:
        L.append("- no nonzero one-frame delta was observed")
    L.append("")
    if "position_element_after_velocity_plan" in result:
        a = result["position_element_after_velocity_plan"]
        L.append("Direct read after the velocity plan (framecount %s): "
                 "`+0x0C` x %d, `+0x10` y %d."
                 % (a["framecount"], a["x_0x0C"], a["y_0x10"]))
        L.append("")
    return "\n".join(L)


def _hex_table(hexstr):
    data = bytes.fromhex(hexstr)
    L = ["| offset | bytes |", "|---|---|"]
    L.extend("| %s |" % row for row in hexdump_rows(data))
    L.append("")
    return L


# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--state", required=True, help="savestate slot label")
    p.add_argument("--out", required=True, help="output directory")
    p.add_argument("--frames", type=int, default=DEFAULT_N_FRAMES,
                   help="N: no-input frames per step (default %d)"
                        % DEFAULT_N_FRAMES)
    p.add_argument("--max-frames", type=int, default=MAX_TOTAL_FRAMES,
                   help="give up after this many frames since unpause")
    p.add_argument("--hold-y", action="store_true",
                   help="hold the Y button for %d frames after the START "
                        "press, then release" % HOLD_Y_FRAMES)
    p.add_argument("--colprm-addr", default=hex(pc.DEFAULT_COLPRM_MANAGER_ADDR))
    p.add_argument("--ipc-dir", default=pc.DEFAULT_DIR)
    p.add_argument("--tmp-dir", default=None)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    tmp = args.tmp_dir
    holder = tempfile.TemporaryDirectory() if tmp is None else None
    if holder is not None:
        tmp = holder.name
    else:
        os.makedirs(tmp, exist_ok=True)
    try:
        result, json_path, md_path = capture(
            args.state, args.ipc_dir, args.out,
            int(args.colprm_addr, 16), args.frames, tmp,
            hold_y=args.hold_y, max_total_frames=args.max_frames)
    finally:
        if holder is not None:
            holder.cleanup()
    print(json.dumps({"slot": args.state, "spawned": result["spawned"],
                      "frames_stepped_since_unpause":
                          result["meta"]["frames_stepped_since_unpause"],
                      "scans": result["meta"]["scan_count"],
                      "json": json_path, "md": md_path}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
