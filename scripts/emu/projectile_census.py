#!/usr/bin/env python3
"""Census every in-use ColPrm collision record and active ObjShot element.

Given a loaded battle save state, this reads two structures out of live
emulator RAM and cross-references them, writing a JSON dump and a Markdown
table. It is deliberately field-names-only: no gameplay names (beam, hit,
cancel, eat, damage, ...) appear anywhere in its output, only offsets.

Layout, all cited from repo docs (re-derive addresses if they ever look
stale -- the ColPrm manager address in particular is a per-state hypothesis,
not a constant):

- Battle root global `0x02172960` -> root object; `[root+0x110]` is the
  ObjShot manager pointer (`docs/confirmed-facts/entities.md:49-57`).
- ObjShot manager: element array base at `[manager+0x1C]`, 72 elements of
  `0x6C` bytes each, ending at `manager+0x1E7C`. Each element's own `+0x00`
  is an intrusive link node; the manager's `+0x00` is the active-list head
  and `+0x10` the free-list head (`docs/confirmed-facts/entities.md:145-160`,
  section "5.1 Manager"). Element `+0x1A` is the kind byte, `+0x18` the
  lifetime in frames, `+0x2C` the spawned entity pointer (same doc, section
  "5.2 Shot element").
- Entity `+0x10` is a pointer to that entity's ColPrm record
  (`docs/confirmed-facts/collision.md` §4, "ownership").
- ColPrm manager (`Battle_ColPrmMan`), `0xFB54` bytes total, hardcoded here
  at the address published for the known state
  (`docs/research/findings/p204-object-is-colprmman.md`); 128 inline records
  at `manager+0x454`, stride `0x188`
  (`docs/confirmed-facts/INVENTORY.md:151`). Treat the manager address as a
  hypothesis for any *new* state -- see the self-validation section below.
- Record fields dumped: `+0x34`, `+0x38`, `+0x3C`, `+0x40`, `+0x5C` (a
  pointer into a *different*, `0x40`-stride element array -- positions, not
  the ObjShot elements above), `+0x60`, `+0x150`, `+0x174`, `+0x17C`; the
  node list at `+0x08` (each `0x2C`-byte node's `+0x00` next, `+0x08` obj,
  `+0x0C` rec, `+0x14`, `+0x18`, `+0x2A` byte, and `obj+0x18` byte), capped
  at 16 nodes (`docs/confirmed-facts/collision.md` §3).
- "In use" = record `+0x40` bit `0x200` clear -- the bit is set at
  construction/teardown and cleared at install (`collision.md`, the `+0x40`
  row).
- The `0x40`-stride position element (reached via record `+0x5C`): `+0xC` x,
  `+0x10` y (s32 raw, `/256` = pixels), `+0x18` is nonzero when active
  (observed values `0x000281FF`, `0x000285FF`, `0x00027BAF` across states --
  the elem check is "nonzero", not a fixed word; the raw word is always
  printed)
  (`docs/research/feel-captures/projectile-conflict-2026-09-10/INSTRUMENT.md`,
  "Addresses" table).

Usage:
    python3 projectile_census.py --state <slot> --out <dir>
    python3 projectile_census.py --no-load --state <label> --out <dir>

Writes `<dir>/<slot>.census.json` and `<dir>/<slot>.census.md`.
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from jus_ipc import DEFAULT_DIR  # noqa: E402

JUSEMU = os.path.join(HERE, "jusemu.py")

# ---- layout constants (see module docstring for citations) ----------------

ROOT_GLOBAL = 0x02172960
ROOT_OBJSHOT_MGR_OFFSET = 0x110

OBJSHOT_MGR_SIZE = 0x3FD4
OBJSHOT_ACTIVE_HEAD_OFFSET = 0x00
OBJSHOT_ELEM_ARRAY_OFFSET = 0x1C
OBJSHOT_ELEM_COUNT = 72
OBJSHOT_ELEM_STRIDE = 0x6C
OBJSHOT_ELEM_NEXT_OFFSET = 0x00
OBJSHOT_ELEM_LIFETIME_OFFSET = 0x18
OBJSHOT_ELEM_KIND_OFFSET = 0x1A
OBJSHOT_ELEM_ENTITY_OFFSET = 0x2C

ENTITY_COLPRM_RECORD_OFFSET = 0x10

DEFAULT_COLPRM_MANAGER_ADDR = 0x0220DDE0
COLPRM_MGR_SIZE = 0xFB54
COLPRM_RECORDS_OFFSET = 0x454
COLPRM_RECORD_COUNT = 128
COLPRM_RECORD_STRIDE = 0x188
COLPRM_INUSE_FLAG_OFFSET = 0x40
COLPRM_INUSE_BIT = 0x200

RECORD_FIELD_OFFSETS = [0x34, 0x38, 0x3C, 0x40, 0x5C, 0x60, 0x150, 0x174, 0x17C]
RECORD_NODE_HEAD_OFFSET = 0x08

NODE_STRIDE = 0x2C
NODE_MAX_WALK = 16
NODE_NEXT_OFFSET = 0x00
NODE_OBJ_OFFSET = 0x08
NODE_REC_OFFSET = 0x0C
NODE_14_OFFSET = 0x14
NODE_18_OFFSET = 0x18
NODE_ENTRY_OFFSET = 0x10
NODE_2A_OFFSET = 0x2A
OBJ_18_OFFSET = 0x18

# Collision entry resolution (allocator 0x0207D440, see
# docs/research/findings/node-0x18-is-seeded-from-the-collision-entry-property-word.md).
BUILTIN_TABLE_BASE = 0x0209FC2C
BUILTIN_TABLE_COUNT = 14
ENTRY_STRIDE = 0x14
ENTRY_0x08_OFFSET = 0x08
ENTRY_0x0E_OFFSET = 0x0E
RECORD_AUTHORED_TABLE_PTR_OFFSET = 0x6C
AUTHORED_TABLE_BASE_OFFSET = 0x0C
AUTHORED_TABLE_MAX_COUNT = 0x400
BUILTIN_ID_BIT0 = 4

ELEMENT_X_OFFSET = 0xC
ELEMENT_Y_OFFSET = 0x10
ELEMENT_18_OFFSET = 0x18

RAM_LOW = 0x02000000
RAM_HIGH = 0x02400000


class ValidationError(RuntimeError):
    """A top-level self-validation check failed; the tool refuses to run."""


def hexw(v):
    return "0x%08X" % (v & 0xFFFFFFFF) if v is not None else None


def hexb(v):
    return "0x%02X" % (v & 0xFF) if v is not None else None


def in_ram(addr):
    return isinstance(addr, int) and RAM_LOW <= addr < RAM_HIGH


def classify_entry_ptr(entry_ptr, authored_base):
    """Classify a resolved collision-entry pointer and back-compute its id.

    Returns (id_kind, id) where id_kind is "builtin", "authored", or
    "unknown", and id is an int or None. See NODE_ENTRY_OFFSET's docstring
    citation for the allocator layout this mirrors.
    """
    if not entry_ptr:
        return "unknown", None
    builtin_hi = BUILTIN_TABLE_BASE + BUILTIN_TABLE_COUNT * ENTRY_STRIDE
    if BUILTIN_TABLE_BASE <= entry_ptr < builtin_hi:
        return "builtin", (entry_ptr - BUILTIN_TABLE_BASE) // ENTRY_STRIDE
    if authored_base:
        delta = entry_ptr - authored_base
        if delta >= 0 and delta % ENTRY_STRIDE == 0:
            idx = delta // ENTRY_STRIDE
            if 0 <= idx < AUTHORED_TABLE_MAX_COUNT:
                return "authored", 0x100 + idx
    return "unknown", None


def predicted_bit0_for(id_kind, id_, entry_0x08):
    """Predicted node+0x18 bit 0 for a classified entry, or None if unknown."""
    if id_kind == "builtin":
        return 1 if id_ == BUILTIN_ID_BIT0 else 0
    if id_kind == "authored":
        if entry_0x08 is None:
            return None
        return (entry_0x08 >> 5) & 1
    return None


class Ram:
    """RAM reader backed by `jusemu.py dump`, preferring a few large reads."""

    def __init__(self, tmp_dir, ipc_dir):
        self.tmp_dir = tmp_dir
        self.ipc_dir = ipc_dir
        self.segments = []  # list of (start, end, bytes)
        self.small_cache = {}
        self.dump_calls = 0

    def _run(self, args):
        cmd = [sys.executable, JUSEMU, "--ipc-dir", self.ipc_dir] + args
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
        if r.returncode != 0:
            raise RuntimeError("jusemu.py %s failed: %s%s" %
                               (" ".join(args), r.stdout, r.stderr))
        return r.stdout

    def _dump_raw(self, start, size):
        self.dump_calls += 1
        outfile = os.path.join(self.tmp_dir, "seg_%08x_%x.bin" % (start, size))
        self._run(["dump", hex(start), hex(start + size), outfile])
        with open(outfile, "rb") as f:
            data = f.read()
        if len(data) != size:
            raise RuntimeError("short dump at 0x%08X: got %d, wanted %d" %
                               (start, len(data), size))
        return data

    def load_segment(self, start, size):
        data = self._dump_raw(start, size)
        self.segments.append((start, start + size, data))
        return data

    def read(self, addr, length):
        for start, end, data in self.segments:
            if start <= addr and addr + length <= end:
                off = addr - start
                return data[off:off + length]
        key = (addr, length)
        cached = self.small_cache.get(key)
        if cached is not None:
            return cached
        data = self._dump_raw(addr, length)
        self.small_cache[key] = data
        return data

    def u32(self, addr):
        return struct.unpack_from("<I", self.read(addr, 4))[0]

    def s32(self, addr):
        return struct.unpack_from("<i", self.read(addr, 4))[0]

    def u16(self, addr):
        return struct.unpack_from("<H", self.read(addr, 2))[0]

    def u8(self, addr):
        return self.read(addr, 1)[0]


# ---------------------------------------------------------------------- #
# Roster verification: which HP slot is the fighter actually in the ring.
#
# jus-franky-state-roster-mismatch-rkwf: the chr_b-col-file audit's roster
# check read `side_base + 0x29` directly -- slot 0 -- instead of finding
# whichever of the four 0x50-apart HP slots per side (jus_addresses.py:
# hp_player_active/hp_opp_active are slot 0 of these arrays) has its
# `+0x25` bit 0 active flag set (moveset_map.py's `v_active`,
# runtime-report-5 2). That silently agreed with the documented roster for
# Momotaro (whose deck happened to have him in slot 0) and silently
# disagreed for Franky (`pc-kenshin-npc-franky-dark-tournament`: read
# Jotaro/Raoh, the two decks' slot-0 leaders, instead of Kenshin/Franky) --
# see docs/research/feel-captures/colfile-audit-2026-09-12/RESULTS.md. This
# walks all four slots and refuses instead of guessing when zero or more
# than one claims to be active.
# ---------------------------------------------------------------------- #
HP_SLOT_STRIDE = 0x50
HP_SLOT_COUNT = 4
HP_SLOT_ACTIVE_FLAG_OFFSET = 0x25
HP_SLOT_ACTIVE_FLAG_BIT = 0x01
HP_SLOT_CHRB_OFFSET = 0x29


def resolve_active_chrb(ram, side_base):
    """Return the chr_b index of the ACTIVE fighter on one side.

    `side_base` is HP slot 0's address for that side (e.g.
    `jus_addresses.ADDRESSES["hp_player_active"]` or `["hp_opp_active"]`).
    Iterates all four 0x50-apart slots, requires exactly one `+0x25` bit 0
    active flag set, and raises `RuntimeError` otherwise -- never returns a
    guess.
    """
    active = []
    for slot in range(HP_SLOT_COUNT):
        base = side_base + slot * HP_SLOT_STRIDE
        flag = ram.u8(base + HP_SLOT_ACTIVE_FLAG_OFFSET) & HP_SLOT_ACTIVE_FLAG_BIT
        if flag:
            active.append((slot, ram.u8(base + HP_SLOT_CHRB_OFFSET)))
    if not active:
        raise RuntimeError(
            "resolve_active_chrb: no HP slot at 0x%08X has +0x25 bit 0 set -- "
            "refusing to guess which fighter is active" % side_base)
    if len(active) > 1:
        raise RuntimeError(
            "resolve_active_chrb: %d HP slots at 0x%08X have +0x25 bit 0 set "
            "(slot, chr_b): %r -- refusing to guess which fighter is active"
            % (len(active), side_base, active))
    return active[0][1]


def status_json(ipc_dir):
    cmd = [sys.executable, JUSEMU, "--ipc-dir", ipc_dir, "status"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
    if r.returncode != 0:
        raise RuntimeError("jusemu.py status failed: %s%s" % (r.stdout, r.stderr))
    return json.loads(r.stdout)


def load_state(slot, ipc_dir):
    """`jusemu.py state load <slot>`.

    Dummy-sidecar states always ack ok:false ("did not settle") even though
    they genuinely loaded (scripts/emu/README.md, "Harness hazards found
    2026-09-03"). So the ack is logged but never treated as failure here --
    only the self-validation checks below decide that.
    """
    cmd = [sys.executable, JUSEMU, "--ipc-dir", ipc_dir, "state", "load", slot]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
    ack = None
    try:
        ack = json.loads(r.stdout)
    except ValueError:
        pass
    return {"returncode": r.returncode, "ack": ack, "stdout": r.stdout,
            "stderr": r.stderr}


def self_validate_1_root(ram):
    root = ram.u32(ROOT_GLOBAL)
    if root == 0:
        raise ValidationError("root global [0x%08X] is zero" % ROOT_GLOBAL)
    mgr = ram.u32(root + ROOT_OBJSHOT_MGR_OFFSET)
    if mgr == 0:
        raise ValidationError("[root+0x110] (ObjShot manager) is zero")
    if not in_ram(mgr):
        raise ValidationError(
            "[root+0x110]=0x%08X is outside 0x02000000..0x02400000" % mgr)
    return root, mgr


def self_validate_2_heartbeat(ipc_dir):
    hb_path = os.path.join(ipc_dir, "heartbeat.json")
    if not os.path.exists(hb_path):
        raise ValidationError("no heartbeat.json at %s -- is the emulator up?" %
                              hb_path)
    with open(hb_path) as f:
        hb1 = json.load(f)
    time.sleep(1.0)
    with open(hb_path) as f:
        hb2 = json.load(f)
    if hb1.get("framecount") == hb2.get("framecount"):
        raise ValidationError(
            "heartbeat framecount did not change across a 1s wait "
            "(hb1=%r hb2=%r) -- emulator may not be alive" % (hb1, hb2))
    return hb1, hb2


def walk_objshot_active_list(ram, manager_addr):
    """Walk the active list via each element's own +0x00 link node."""
    lo = manager_addr + OBJSHOT_ELEM_ARRAY_OFFSET
    hi = lo + OBJSHOT_ELEM_COUNT * OBJSHOT_ELEM_STRIDE
    head = ram.u32(manager_addr + OBJSHOT_ACTIVE_HEAD_OFFSET)
    elements = []
    visited = set()
    addr = head
    while addr != 0 and addr not in visited and len(elements) < OBJSHOT_ELEM_COUNT:
        visited.add(addr)
        in_array = lo <= addr < hi
        kind = ram.u8(addr + OBJSHOT_ELEM_KIND_OFFSET)
        lifetime = ram.u16(addr + OBJSHOT_ELEM_LIFETIME_OFFSET)
        entity = ram.u32(addr + OBJSHOT_ELEM_ENTITY_OFFSET)
        record_ptr = None
        if entity != 0 and in_ram(entity):
            try:
                record_ptr = ram.u32(entity + ENTITY_COLPRM_RECORD_OFFSET)
            except RuntimeError:
                record_ptr = None
        elements.append({
            "addr": addr, "in_declared_array": in_array,
            "kind": kind, "lifetime": lifetime,
            "entity_ptr": entity, "record_ptr": record_ptr,
        })
        addr = ram.u32(addr + OBJSHOT_ELEM_NEXT_OFFSET)
    return elements


def read_node_entry(ram, entry_ptr, authored_base):
    """Read entry+0x08/+0x0E and classify, given a resolved entry pointer
    and the record's authored-table base (`[[record+0x6C]+0x0C]`)."""
    id_kind, id_ = classify_entry_ptr(entry_ptr, authored_base)
    entry_0x08 = None
    entry_0x0e = None
    if entry_ptr and in_ram(entry_ptr):
        try:
            entry_0x08 = ram.u32(entry_ptr + ENTRY_0x08_OFFSET)
            entry_0x0e = ram.u16(entry_ptr + ENTRY_0x0E_OFFSET)
        except RuntimeError:
            pass
    predicted = predicted_bit0_for(id_kind, id_, entry_0x08)
    return {
        "entry_ptr": entry_ptr, "id_kind": id_kind, "id": id_,
        "entry_0x08": entry_0x08, "entry_0x0e": entry_0x0e,
        "predicted_bit0": predicted,
    }


def read_authored_base(ram, rec_addr):
    """`[[record+0x6C]+0x0C]`, guarding null pointers at each hop."""
    try:
        table_ptr = ram.u32(rec_addr + RECORD_AUTHORED_TABLE_PTR_OFFSET)
    except RuntimeError:
        return None, "record+0x6C read failed"
    if not table_ptr or not in_ram(table_ptr):
        return None, "record+0x6C is not a RAM pointer"
    try:
        base = ram.u32(table_ptr + AUTHORED_TABLE_BASE_OFFSET)
    except RuntimeError:
        return None, "[record+0x6C]+0x0C read failed"
    if not base:
        return None, "[record+0x6C]+0x0C is null"
    return base, None


def read_nodes(ram, head, authored_base=None):
    nodes = []
    addr = head
    visited = set()
    while addr != 0 and addr not in visited and len(nodes) < NODE_MAX_WALK:
        visited.add(addr)
        try:
            next_ = ram.u32(addr + NODE_NEXT_OFFSET)
            obj = ram.u32(addr + NODE_OBJ_OFFSET)
            rec = ram.u32(addr + NODE_REC_OFFSET)
            n14 = ram.u32(addr + NODE_14_OFFSET)
            n18 = ram.u32(addr + NODE_18_OFFSET)
            n2a = ram.u8(addr + NODE_2A_OFFSET)
            entry_ptr = ram.u32(addr + NODE_ENTRY_OFFSET)
        except RuntimeError as e:
            nodes.append({"addr": addr, "error": str(e)})
            break
        obj18 = None
        if obj != 0 and in_ram(obj):
            try:
                obj18 = ram.u8(obj + OBJ_18_OFFSET)
            except RuntimeError:
                obj18 = None
        node = {
            "addr": addr, "next": next_, "obj": obj, "rec": rec,
            "field_0x14": n14, "field_0x18": n18, "byte_0x2a": n2a,
            "obj_0x18": obj18, "entry_ptr": entry_ptr,
        }
        if entry_ptr:
            node.update(read_node_entry(ram, entry_ptr, authored_base))
            observed_bit0 = n18 & 1
            predicted = node["predicted_bit0"]
            node["observed_bit0"] = observed_bit0
            node["match"] = (None if predicted is None
                             else predicted == observed_bit0)
        else:
            node.update({
                "id_kind": "unknown", "id": None,
                "entry_0x08": None, "entry_0x0e": None,
                "predicted_bit0": None, "observed_bit0": n18 & 1,
                "match": None,
            })
        nodes.append(node)
        addr = next_
    return nodes


def census(state_label, ipc_dir, no_load, colprm_addr, out_dir, tmp_dir,
          trust_addr=False):
    notes = []
    load_result = None
    if not no_load:
        load_result = load_state(state_label, ipc_dir)
        notes.append("state load ack: %r" % load_result["ack"])

    ram = Ram(tmp_dir, ipc_dir)

    # ---- self-validation 1: root + manager pointer -----------------------
    root_addr, objshot_mgr_addr = self_validate_1_root(ram)

    # ---- self-validation 2: heartbeat ticks -------------------------------
    hb1, hb2 = self_validate_2_heartbeat(ipc_dir)

    # ---- bulk reads --------------------------------------------------------
    ram.load_segment(objshot_mgr_addr, OBJSHOT_MGR_SIZE)
    ram.load_segment(colprm_addr, COLPRM_MGR_SIZE)

    objshot_elements = walk_objshot_active_list(ram, objshot_mgr_addr)
    objshot_by_record = {}
    for el in objshot_elements:
        if el["record_ptr"]:
            objshot_by_record.setdefault(el["record_ptr"], []).append(el)

    # First pass over all 128 records: find in-use ones and their +0x5C refs.
    records_base = colprm_addr + COLPRM_RECORDS_OFFSET
    inuse = []
    for i in range(COLPRM_RECORD_COUNT):
        rec_addr = records_base + i * COLPRM_RECORD_STRIDE
        flags = ram.u32(rec_addr + COLPRM_INUSE_FLAG_OFFSET)
        if flags & COLPRM_INUSE_BIT:
            continue
        inuse.append((i, rec_addr))

    # Implementation note: prefer one bulk dump over many small element reads
    # when the +0x5C targets cluster (dump 0x40*64 bytes from the lowest
    # referenced address), else fall back to Ram.read's per-address dumps.
    elem_addrs = []
    for _, rec_addr in inuse:
        e = ram.u32(rec_addr + 0x5C)
        if e:
            elem_addrs.append(e)
    if elem_addrs:
        lo, hi = min(elem_addrs), max(elem_addrs) + 0x40
        span = hi - lo
        if span <= 0x40 * 64:
            try:
                ram.load_segment(lo, span)
            except RuntimeError:
                pass  # fall back to per-address small reads below

    record_rows = []
    elem_checks_failed = 0
    elem_checks_total = 0
    elem_checks_failed_indices = []
    for idx, rec_addr in inuse:
        fields = {}
        for off in RECORD_FIELD_OFFSETS:
            fields["0x%X" % off] = ram.u32(rec_addr + off)

        elem_addr = fields["0x5C"]
        elem_info = {"addr": elem_addr, "x_raw": None, "y_raw": None,
                    "x_px": None, "y_px": None, "word_0x18": None,
                    "elem_check": "fail", "elem_check_reason": None}
        elem_checks_total += 1
        if elem_addr and in_ram(elem_addr):
            try:
                x_raw = ram.s32(elem_addr + ELEMENT_X_OFFSET)
                y_raw = ram.s32(elem_addr + ELEMENT_Y_OFFSET)
                w18 = ram.u32(elem_addr + ELEMENT_18_OFFSET)
                elem_info.update({
                    "x_raw": x_raw, "y_raw": y_raw,
                    "x_px": x_raw / 256.0, "y_px": y_raw / 256.0,
                    "word_0x18": w18,
                })
                if w18 != 0:
                    elem_info["elem_check"] = "pass"
                else:
                    elem_info["elem_check_reason"] = (
                        "+0x18 == 0x%08X, expected nonzero" % w18)
            except RuntimeError as e:
                elem_info["elem_check_reason"] = str(e)
        else:
            elem_info["elem_check_reason"] = "+0x5C is not a RAM pointer"
        if elem_info["elem_check"] != "pass":
            elem_checks_failed += 1
            elem_checks_failed_indices.append(idx)

        authored_base, authored_base_err = read_authored_base(ram, rec_addr)
        nodes = read_nodes(ram, ram.u32(rec_addr + RECORD_NODE_HEAD_OFFSET),
                          authored_base=authored_base)

        objshot_matches = objshot_by_record.get(rec_addr, [])
        objshot_kind = (hexb(objshot_matches[0]["kind"])
                        if objshot_matches else "-")
        objshot_lifetime = (objshot_matches[0]["lifetime"]
                            if objshot_matches else "-")

        record_rows.append({
            "idx": idx, "addr": rec_addr, "fields": fields,
            "elem": elem_info, "nodes": nodes,
            "objshot_matches": objshot_matches,
            "objshot_kind": objshot_kind,
            "objshot_lifetime": objshot_lifetime,
            "authored_base": authored_base,
            "authored_base_error": authored_base_err,
        })

    if (elem_checks_total > 0 and elem_checks_failed == elem_checks_total
            and not trust_addr):
        raise ValidationError(
            "ColPrm manager address hypothesis failed: every in-use "
            "record's +0x5C element failed the +0x18!=0 check "
            "(manager addr 0x%08X). Pass --trust-addr if this address was "
            "already confirmed earlier in the same session (e.g. a "
            "post-run census where no projectile happens to be active "
            "in this exact frame)."
            % (colprm_addr,))

    result = {
        "meta": {
            "state": state_label,
            "no_load": no_load,
            "load_result": load_result,
            "root_addr": hexw(root_addr),
            "objshot_manager_addr": hexw(objshot_mgr_addr),
            "colprm_manager_addr": hexw(colprm_addr),
            "self_validation": {
                "root_and_manager_pointer": "pass",
                "heartbeat_before": hb1,
                "heartbeat_after": hb2,
                "heartbeat_ticked": "pass",
                "elem_checks_total": elem_checks_total,
                "elem_checks_passed": elem_checks_total - elem_checks_failed,
                "elem_checks_failed": elem_checks_failed,
                "elem_checks_failed_indices": elem_checks_failed_indices,
            },
            "dump_calls": ram.dump_calls,
            "notes": notes,
        },
        "colprm_records": record_rows,
        "objshot_elements": objshot_elements,
    }
    return result


def recheck_result(result):
    """Re-derive `elem_check`/`elem_check_reason` and the self-validation
    counts from an already-written `.census.json`, applying the *current*
    elem-check rule (`+0x18 != 0`) to the raw `word_0x18` each record
    already recorded. No RAM read, no emulator -- this only recomputes a
    result dict that was produced with a stale rule (e.g. the retired
    fixed-word `0x000281FF` check from commit adc3953).

    Every other field (fields, nodes, x/y, objshot matches, ...) is passed
    through unchanged; only `elem_check`/`elem_check_reason` per record and
    the `elem_checks_*` counters in `meta.self_validation` are rewritten.
    """
    elem_checks_total = 0
    elem_checks_failed = 0
    elem_checks_failed_indices = []
    for row in result["colprm_records"]:
        elem = row["elem"]
        elem_checks_total += 1
        w18 = elem.get("word_0x18")
        if w18 is not None:
            if w18 != 0:
                elem["elem_check"] = "pass"
                elem["elem_check_reason"] = None
            else:
                elem["elem_check"] = "fail"
                elem["elem_check_reason"] = (
                    "+0x18 == 0x%08X, expected nonzero" % w18)
        # else: word_0x18 was never read (no valid +0x5C pointer); leave
        # whatever reason the original run recorded.
        if elem["elem_check"] != "pass":
            elem_checks_failed += 1
            elem_checks_failed_indices.append(row["idx"])

    sv = result["meta"]["self_validation"]
    sv["elem_checks_total"] = elem_checks_total
    sv["elem_checks_failed"] = elem_checks_failed
    sv["elem_checks_passed"] = elem_checks_total - elem_checks_failed
    sv["elem_checks_failed_indices"] = elem_checks_failed_indices
    return result


def render_markdown(result):
    lines = []
    lines.append("# Projectile census: %s" % result["meta"]["state"])
    lines.append("")
    lines.append("root=%s objshot_manager=%s colprm_manager=%s" % (
        result["meta"]["root_addr"], result["meta"]["objshot_manager_addr"],
        result["meta"]["colprm_manager_addr"]))
    lines.append("")
    sv = result["meta"]["self_validation"]
    lines.append("elem_checks_passed=%s elem_checks_failed=%s (of %s total)"
                % (sv.get("elem_checks_passed"), sv.get("elem_checks_failed"),
                   sv.get("elem_checks_total")))
    if sv.get("elem_checks_failed_indices"):
        lines.append("elem_checks_failed_indices: %s"
                    % ", ".join(str(i) for i in sv["elem_checks_failed_indices"]))
    lines.append("")
    lines.append("## In-use ColPrm records")
    lines.append("")
    header = ["rec idx", "rec addr", "+0x34", "+0x38", "+0x3C", "+0x40",
              "+0x150", "+0x174", "+0x17C", "elem addr", "x px", "y px",
              "elem+0x18", "objshot kind", "objshot lifetime", "node count",
              "node+0x18 list", "obj+0x18 list"]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))
    for row in result["colprm_records"]:
        f = row["fields"]
        elem = row["elem"]
        node18s = ", ".join(hexw(n.get("field_0x18")) for n in row["nodes"]
                            if "field_0x18" in n)
        obj18s = ", ".join(
            (hexb(n["obj_0x18"]) if isinstance(n.get("obj_0x18"), int) else "-")
            for n in row["nodes"])
        cells = [
            str(row["idx"]), hexw(row["addr"]),
            hexw(f["0x34"]), hexw(f["0x38"]), hexw(f["0x3C"]), hexw(f["0x40"]),
            hexw(f["0x150"]), hexw(f["0x174"]), hexw(f["0x17C"]),
            hexw(elem["addr"]),
            ("%.4f" % elem["x_px"]) if elem["x_px"] is not None else "-",
            ("%.4f" % elem["y_px"]) if elem["y_px"] is not None else "-",
            hexw(elem["word_0x18"]) if elem["word_0x18"] is not None else "-",
            row["objshot_kind"], str(row["objshot_lifetime"]),
            str(len(row["nodes"])), node18s or "-", obj18s or "-",
        ]
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    lines.append("## Node collision entries")
    lines.append("")
    header3 = ["rec idx", "node addr", "entry ptr", "id kind", "id",
              "entry+0x08", "entry+0x0E", "predicted bit0", "observed bit0",
              "match"]
    lines.append("| " + " | ".join(header3) + " |")
    lines.append("|" + "---|" * len(header3))
    for row in result["colprm_records"]:
        for n in row["nodes"]:
            if "entry_ptr" not in n:
                continue
            predicted = n.get("predicted_bit0")
            observed = n.get("observed_bit0")
            match = n.get("match")
            cells = [
                str(row["idx"]), hexw(n["addr"]),
                hexw(n.get("entry_ptr")) if n.get("entry_ptr") else "-",
                n.get("id_kind") or "-",
                str(n.get("id")) if n.get("id") is not None else "-",
                hexw(n.get("entry_0x08")) if n.get("entry_0x08") is not None else "-",
                ("0x%04X" % n["entry_0x0e"]) if n.get("entry_0x0e") is not None else "-",
                str(predicted) if predicted is not None else "-",
                str(observed) if observed is not None else "-",
                ("-" if match is None else ("yes" if match else "no")),
            ]
            lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    lines.append("## Active ObjShot elements")
    lines.append("")
    header2 = ["idx", "elem addr", "kind", "lifetime", "entity ptr",
              "record ptr", "in declared array"]
    lines.append("| " + " | ".join(header2) + " |")
    lines.append("|" + "---|" * len(header2))
    for i, el in enumerate(result["objshot_elements"]):
        cells = [
            str(i), hexw(el["addr"]), hexb(el["kind"]), str(el["lifetime"]),
            hexw(el["entity_ptr"]) if el["entity_ptr"] else "-",
            hexw(el["record_ptr"]) if el["record_ptr"] else "-",
            "yes" if el["in_declared_array"] else "no",
        ]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines)


def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--recheck", metavar="CENSUS_JSON",
                  help="offline mode: re-render CENSUS_JSON (and its "
                       ".md sibling) with the current elem-check rule and "
                       "byte width, no emulator, no RAM read. All other "
                       "arguments except --out are ignored in this mode.")
    p.add_argument("--state", required=False,
                  help="savestate slot name (also used to name output files)")
    p.add_argument("--out", required=False, help="output directory")
    p.add_argument("--no-load", action="store_true",
                  help="census the currently loaded state; skip `state load`")
    p.add_argument("--colprm-addr", default=hex(DEFAULT_COLPRM_MANAGER_ADDR),
                  help="Battle_ColPrmMan address hypothesis for this state "
                       "(default: %s, published for the known control state)"
                       % hex(DEFAULT_COLPRM_MANAGER_ADDR))
    p.add_argument("--ipc-dir", default=DEFAULT_DIR)
    p.add_argument("--tmp-dir", default=None,
                  help="scratch dir for dump files (default: a temp dir)")
    p.add_argument("--trust-addr", action="store_true",
                  help="skip the 'every in-use record failed elem_check' "
                       "refusal; use when --colprm-addr was already "
                       "confirmed earlier in this session and a frame with "
                       "no active projectile is expected (e.g. a post-run "
                       "census)")
    p.add_argument("--verify-roster", nargs=2, metavar=("P1_BASE", "P2_BASE"),
                  help="skip the census; read the ACTIVE chr_b index on "
                       "each side via resolve_active_chrb (iterates the "
                       "four 0x50-apart HP slots per side, requires "
                       "exactly one +0x25 bit-0 active flag) instead of "
                       "slot 0, and refuses on ambiguity "
                       "(jus-franky-state-roster-mismatch-rkwf). Bases are "
                       "hex addresses, e.g. 0x021DF1D4 0x021DF7F0.")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.recheck:
        with open(args.recheck) as f:
            result = json.load(f)
        result = recheck_result(result)

        out_dir = args.out or os.path.dirname(args.recheck) or "."
        base = os.path.basename(args.recheck)
        if base.endswith(".json"):
            base = base[:-len(".json")]
        os.makedirs(out_dir, exist_ok=True)
        json_path = os.path.join(out_dir, base + ".json")
        md_path = os.path.join(out_dir, base + ".md")

        with open(json_path, "w") as f:
            json.dump(result, f, indent=1, sort_keys=True)
        with open(md_path, "w") as f:
            f.write(render_markdown(result))
        print("rechecked %s" % args.recheck)
        print("wrote %s" % json_path)
        print("wrote %s" % md_path)
        return 0

    if args.verify_roster:
        p1_base, p2_base = (int(x, 0) for x in args.verify_roster)
        tmp_dir = args.tmp_dir or tempfile.mkdtemp(prefix="projectile_census_")
        os.makedirs(tmp_dir, exist_ok=True)
        ram = Ram(tmp_dir, args.ipc_dir)
        try:
            p1_chrb = resolve_active_chrb(ram, p1_base)
            p2_chrb = resolve_active_chrb(ram, p2_base)
        except RuntimeError as e:
            print("error: %s" % e, file=sys.stderr)
            return 1
        print(json.dumps({"p1_base": hexw(p1_base), "p1_chrb": p1_chrb,
                          "p2_base": hexw(p2_base), "p2_chrb": p2_chrb}))
        return 0

    if not args.state or not args.out:
        print("error: --state and --out are required "
             "(unless --recheck or --verify-roster)",
             file=sys.stderr)
        return 2

    colprm_addr = int(args.colprm_addr, 0)
    os.makedirs(args.out, exist_ok=True)
    tmp_dir = args.tmp_dir or tempfile.mkdtemp(prefix="projectile_census_")
    os.makedirs(tmp_dir, exist_ok=True)

    try:
        result = census(args.state, args.ipc_dir, args.no_load, colprm_addr,
                        args.out, tmp_dir, trust_addr=args.trust_addr)
    except ValidationError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1

    json_path = os.path.join(args.out, "%s.census.json" % args.state)
    md_path = os.path.join(args.out, "%s.census.md" % args.state)
    with open(json_path, "w") as f:
        json.dump(result, f, indent=1, sort_keys=True)
    with open(md_path, "w") as f:
        f.write(render_markdown(result))

    print("wrote %s" % json_path)
    print("wrote %s" % md_path)
    print("in-use records: %d, active ObjShot elements: %d" % (
        len(result["colprm_records"]), len(result["objshot_elements"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
