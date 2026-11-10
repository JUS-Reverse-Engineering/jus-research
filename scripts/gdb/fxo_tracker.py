#!/usr/bin/env python3
"""Shared FXO effect-object tracker: probe generation and offline reduction. This packages the existing family D gdb probes; it is not a new recorder.

generate(lo, hi, extra_banks, life=, capacity=) -> gdb script text
    Starts from docs/research/feel-captures/2026-10-19-pt19-common/plans/make_probe_pt19.py (the newest shared generator: atns41 hitbox dump +
    kit_hit_probe + ANIM/FXG/FXS/SND/SNDOK/PH + the FXO tracker with the parent element's position, `par=`) and patches it, each patch
    asserted to occur exactly once:
      * the ordinary initializer 0x02023894 registers the fighter banks and the shared ROM range 0x210000 <= id < 0x250000, the same
        range the added shared-entry hook 0x02023924 registers. The GN01 handler and other ov06 callers initialize shared ids at the
        ordinary entry (scripts/gdb/fxo_initializers.py, the ROM census), so one table and one registration rule cover both hooks;
      * `$fxo_life` and the `$fxo_n < 400` capacity test become parameters, and a full table prints `FXOVF` instead of dropping the object;
      * every dump tick prints `FXT gfc= n= life= cap=` (the heartbeat): an empty inventory is an observed fact only with it;
      * the FXPOS pointer chase of 2026-10-16-taikoubou-fx2/plans/make_probe_s4.py:207-216 (effect object +0x60 -> group, group +0x24 -> body,
        body +0x5C.. position, element +0xC.. position, P1 physics element) runs for EVERY tracked object on EVERY tick of the window.
        In the s4 probe that read sat in the FXRAW scouting block, limited to `$s4_fxid` and age <= 40. A chain that does not resolve
        prints `FXPOS ... unresolved=group|body`, so a failure is a row, not silence.
    The s4 probe's experimental pokes, the FXRAW/FXCH* raw dumps and the 200-tick/80-track session limits are not carried.

reduce(lines, ..., banks=, baseline=, legacy=) -> dict (schema fxo-tracks/v1)
    Reducer input contract. The reducer parses a probe log (the s4/tk/pt19 FXO line formats: ANIM, FXS, FXO, optional
    `par=`, FXPOS, FXT, FXOVF) into an immutable ordered event list (parse_events), executes every event the way the generated probe runs
    (the registration table as the authority) and builds ONE validated Snapshot of the window. `ok`, the inventory and the carried proof
    all derive from it, and the next window reads the carried proof back through the same validator (validate_carried).
    A freed end is the first dump observing dead graphics, not an instruction-level free timestamp. In j9q the native heap-free
    call follows the last live sample in that frame; the following dump observes death. Join native calls with their sampling phase.
      scope       `banks` (CLI --banks), the probe's tracked id >> 8 set, is proof input: a tracked ANIM (not the body setter, its bank
                  declared, not dropped by the FXOVF right after it) appends the exact entry (object, id, birth) at the current count.
                  Without it the banks are inferred from the FXO rows for inspection only (banks_undeclared): never ok, never
                  inventory_empty, no carried proof. A registering ANIM must come through a ROM-proven path (fxo_initializers.json):
                  an initializer other than 0x02023894 (no `pc=`) or 0x02023924 is unknown_initializer, and a shared id whose lr is
                  not a census call site of that entry admitting shared ids is unproven_initializer_path. Bank ids keep their rule.
      clock       every event reads the one frame counter, so the gfc never runs backward across ANIM, FXS, FXT, FXOVF, FXO and FXPOS
                  (event_clock_regression), and no heartbeat counts an entry born after it (future_registration_in_count).
      dump        FXT opens a closed dump phase: at most six PH rows (ph_above_capacity), then the FXO/FXPOS loop.
                  Any game event closes it; later rows at that tick are dump_interleaved.
                  Rows past age life are row_past_life, a count over capacity is count_above_capacity, and
                  configuration changes within a stream or chain are probe_config_changed. Every registered entry needs its FXO row
                  at each dump through age == life, including ended and carried entries (fxo_missing names the object and tick).
                  Once per tick the dump prints `FXT n=<count>` and then `while $fxo_i < $fxo_n` prints, per entry in index order, its FXO
                  row and one FXPOS row. One heartbeat per tick in increasing gfc (fxt_duplicate, dump_order); the count is the table
                  length (fxt_inconsistent) and never decreases, within a tick or below the baseline's count (fxt_count_regress); every
                  FXO row sits in its tick's dump block (dump_outside), below that dump's count (index_beyond_count), in loop order
                  (dump_order), after its entry was appended and not before the generation's first tick (sample_before_registration),
                  with exactly that entry's object and id (identity_mismatch) and clock (clock_mismatch). A rejected row is never a sample.
      position    an FXPOS row is bound to the FXO row printed immediately before it (one per FXO) and repeats its gfc, index, age and id
                  (identity_mismatch); any other FXPOS row is fxpos_orphan; an FXO row without its FXPOS row is fxpos_missing. Only a
                  bound, matching FXPOS row of an accepted FXO row is a chain or a p1phys observation. `legacy=True` (--legacy) admits
                  logs older than the generated probe (FXO without FXPOS); it never certifies placement (legacy_uncertified, never ok).
      generation  (index, object, effect id, birth gfc) from its table entry. Every FXO row of the index carries that object and id, gfc =
                  birth + age and increasing ages, checked on every row including those after the end; its registration ANIM is in the
                  log. The first ANIM on the object printed after the registration ends it (reinit, as analyze2_fx.py:22-53; an ANIM
                  after its tick's dump takes effect from the next tick); a freed object (vtable change, state 0 with no parent,
                  `e=none`) ends it.
      cut         the window's cut clock is its last observed dump. A registration after the final dump, or a reinit landing past it,
                  is past_cut: missing evidence until a later dump observes it.
      snapshot    {banks, count, last_gfc = the cut, last_event_gfc, life, capacity, generations: [{n, obj, id, birth_gfc, end,
                  provenance: {first_tick, live_ages}}]}
                  and validate_snapshot's invariants: declared banks (banks_undeclared), a cut clock (no_heartbeat), every index
                  0..count-1 has a generation (unaccounted_index) and none is above it (index_beyond_count), each ended at a recorded
                  free or reinit (incomplete_window: a window cut while a generation lives is not ok), in a declared bank (bank_scope),
                  max(birth_gfc, end.gfc) <= last_gfc (past_cut), at least one live tick (unmodeled_zero_duration: same-tick repeated
                  registrations and same-tick reinits fail closed), and no two generations at one object overlap (generation_overlap).
      carried     the snapshot's JSON form, present only when ok. reduce() runs validate_carried on it before declaring ok, so every
                  ok result is accepted as the next window's `baseline`; a chain of ok windows carries what one reduction over their
                  union carries. A segmentation dump boundary is a cut immediately before an FXT row. Cutting after a dump's rows
                  but before a same-tick post-dump game event splits the tick and is refused with baseline_chronology.
                  A baseline that is not ok or fails the validator accounts nothing (baseline_unproven; a generation past
                  its own cut is baseline_chronology); one proved for other banks is baseline_scope.
      chronology  every event of the window is after the baseline's last_gfc (baseline_chronology), and no earlier than its
                  last_event_gfc (event_clock_regression). The dump cut stays separate from this event-clock bound. Carried proof
                  without last_event_gfc, life or capacity is rejected as baseline_unproven.
      banks       with declared banks, every table entry they append must be a generation (registered_without_stream).
    Units are the element's 20.12 values (`q12`); world positions are Q8 (`world_q8`, the same unit as the native body x/y and raw
    positions).
    SPACE IS NEVER GUESSED FROM A MAGNITUDE. The analyzers' absolute-magnitude local-vs-world test (analyze2_fx.py:67, analyze_tkfx.py:77) is not
    used. A sample is resolved only by independent evidence at that tick:
      follow_fighter  parent word 0 and the FXPOS chain's body position (Q12 >> 4) equals exactly one fighter's Q8 position (the log's own
                      p1phys unless the caller supplies the fighter); a nonzero element offset also needs the facing (negated x for facing 1,
                      analyze2_fx.py header), else `transform_unmeasured`
      world           the element position equals exactly one caller-supplied world object at that tick (`inventory.world_objects`, e.g. the
                      native shot rows), or the track was born at a positioned fx_spawn (FXS integer px, not both zero) that equals its age-0
                      element position, and it has not moved since
      unresolved      anything else (an unresolved parent, a chain body that is no fighter, an ambiguous match)
    A parent pointer alone is not a follow target. The FXS row with r1 = r2 = 0 (the spawn entry's omitted coordinates, native_events.py:41-59)
    never establishes a position. Birth placement of GN01 and shot-vanish effects is the age-0 sample of the resolved object.
    Missing evidence kinds: no_birth_sample, gap, unresolved_space, transform_unmeasured, wrong_follow_target, capacity_overflow,
    short_window, incomplete_window (no recorded free or reinit ends the interval), no_live_sample, clock_mismatch (row gfc != birth + age),
    age_order, identity_mismatch (a row of the index with another object/id, or an FXPOS row with another id/age), no_registration,
    generation_overlap, unaccounted_index, fxt_inconsistent (an FXT count that contradicts a generation's registration position),
    fxt_duplicate, dump_order, dump_outside, index_beyond_count, sample_before_registration, baseline_unproven,
    registered_without_stream (banks cross-check), fxt_count_regress, no_heartbeat, window_gap, fxpos_orphan, baseline_chronology,
    banks_undeclared, bank_scope, baseline_scope, event_clock_regression, future_registration_in_count, past_cut, fxpos_missing,
    unmodeled_zero_duration, legacy_uncertified, snapshot_malformed, row_past_life, count_above_capacity, fxo_missing,
    probe_config_changed, probe_config_invalid, dump_interleaved, overflow_inconsistent, ph_above_capacity,
    element_malformed (e= must be none or exactly six numeric fields), unknown_initializer, unproven_initializer_path. A track is complete only
    when every age from its first sample to the recorded free/reinit is present. `ok` is true only with no missing evidence.
    UNMEASURED: shot-vanish 0x220007 birth placement has no recorded FXO row in the repo (only ANIM/FXG).
"""
import argparse
import ast
import functools
import hashlib
import importlib.util
import json
import re
import sys
from collections import namedtuple
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
MP_PATH = ROOT / "docs/research/feel-captures/2026-10-19-pt19-common/plans/make_probe_pt19.py"
VFX_SFX = ROOT / "docs/rebuild/vfx-sfx.json"

DEFAULT_LIFE = 260           # the pt19 probe's value, now an explicit parameter
DEFAULT_CAPACITY = 400       # the pt19 probe's table size, now an explicit parameter
BODY_LR = 0x0215F2BC         # ANIM from the body animation setter: not an effect object
ANIM_ENTRY, SHARED_ENTRY = 0x02023894, 0x02023924   # the two animation-id initializers (fxo_initializers.py); an ANIM row without
                                                    # `pc=` is the ordinary entry's
SHARED_IDS = (0x210000, 0x250000)                   # fx_spawn's shared-effect range (0x0206C814..0x0206C820), half-open
KINDS = {0x0206CB8C: "gn01_effect", 0x0216EBEC: "shot_element", 0x0216C6D4: "shot_element"}   # analyze_tkfx.py:30
# sha256 of generate() output for the pinned argument sets (regenerate with `fxo_tracker.py pins`); a change is a reviewed change
PINNED_SHA256 = {"7c1+2200": "95c529e1ea9c8dad8b1b917b981c2ce74c5e66d75b191bf1930332d20136d51a"}


def _load_mp():
    spec = importlib.util.spec_from_file_location("make_probe_pt19", MP_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _once(text, old, new, what):
    if text.count(old) != 1:
        raise RuntimeError("fxo_tracker: %s: expected exactly one %r in the pt19 probe, found %d" % (what, old, text.count(old)))
    return text.replace(old, new)


FXPOS_BLOCK = r'''      set $fxp_g = *(unsigned int*)($fxo_cobj + 0x60)
      if $fxo_el >= 0x02000000 && $fxo_el < 0x02400000 && $fxp_g >= 0x021d0000 && $fxp_g < 0x02400000
        set $fxp_b = *(unsigned int*)($fxp_g + 0x24)
        if $fxp_b >= 0x021d0000 && $fxp_b < 0x02400000
          printf "FXPOS gfc=%d n=%d age=%d id=0x%x grp=0x%x body=0x%x bodypos=%d,%d,%d elpos=%d,%d,%d p1phys=%d,%d\n", $fxo_gf, $fxo_i, $fxo_gf - $fxo_cg, $fxo_cid, $fxp_g, $fxp_b, *(int*)($fxp_b + 0x5c), *(int*)($fxp_b + 0x60), *(int*)($fxp_b + 0x64), *(int*)($fxo_el + 0xc), *(int*)($fxo_el + 0x10), *(int*)($fxo_el + 0x14), *(int*)($atns41_physel0 + 0xc), *(int*)($atns41_physel0 + 0x10)
        else
          printf "FXPOS gfc=%d n=%d age=%d id=0x%x grp=0x%x unresolved=body\n", $fxo_gf, $fxo_i, $fxo_gf - $fxo_cg, $fxo_cid, $fxp_g
        end
      else
        printf "FXPOS gfc=%d n=%d age=%d id=0x%x unresolved=group\n", $fxo_gf, $fxo_i, $fxo_gf - $fxo_cg, $fxo_cid
      end
'''


SHARED_ANIM = r'''
break *0x02023924
commands
  silent
  printf "ANIM gfc=%d r0=0x%08x r1=0x%08x lr=0x%08x pc=0x02023924\n", *(unsigned int*)0x020A0F10, $r0, $r1, $lr
  if $r1 >= 0x210000 && $r1 < 0x250000
    if $fxo_n < @CAP@
      eval "set $fxo_obj_%d = $r0", $fxo_n
      eval "set $fxo_id_%d = $r1", $fxo_n
      eval "set $fxo_g_%d = *(unsigned int*)0x020A0F10", $fxo_n
      set $fxo_n = $fxo_n + 1
    else
      printf "FXOVF gfc=%d id=0x%x obj=0x%x cap=@CAP@\n", *(unsigned int*)0x020A0F10, $r1, $r0
    end
  end
  continue
end
'''


def generate(lo, hi, extra_banks=(), *, life=DEFAULT_LIFE, capacity=DEFAULT_CAPACITY, root=ROOT, lifecycle=False):
    """Generate the ordinary bank filter plus the full shared ROM ID range; declare SHARED_BANKS when reducing new probes.
    lifecycle=True adds the instruction-time lifecycle, shot-art, NoteTrack, sound-player and draw rows of fxo_lifecycle.splice."""
    if life < 1 or capacity < 1:
        raise ValueError("life and capacity must be positive")
    base = _load_mp().generate(lo, hi, list(extra_banks), False, root)
    text = base.split("\n", 1)[1]
    text = _once(text, "set $fxo_life = %d\n" % 260, "set $fxo_life = %d\n" % life, "window")
    text = _once(text, "    if $fxo_n < 400\n", "    if $fxo_n < %d\n" % capacity, "capacity")
    text = _once(text, "      set $fxo_n = $fxo_n + 1\n    end\n",
                 "      set $fxo_n = $fxo_n + 1\n    else\n"
                 '      printf "FXOVF gfc=%%d id=0x%%x obj=0x%%x cap=%d\\n", *(unsigned int*)0x020A0F10, $r1, $r0\n    end\n' % capacity, "overflow")
    text = _once(text, "  set $fxo_gf = *(unsigned int*)0x020A0F10\n  set $ph_i = 0\n",
                 "  set $fxo_gf = *(unsigned int*)0x020A0F10\n"
                 '  printf "FXT gfc=%%d n=%%d life=%d cap=%d\\n", $fxo_gf, $fxo_n\n  set $ph_i = 0\n' % (life, capacity), "heartbeat")
    text = _once(text, "      end\n    end\n    set $fxo_i = $fxo_i + 1\n", "      end\n" + FXPOS_BLOCK + "    end\n    set $fxo_i = $fxo_i + 1\n", "FXPOS")
    # The ordinary entry takes the shared ROM range as well: the GN01 handler 0x0206CA8C and other ov06 callers initialize shared ids
    # there (fxo_initializers.json), so both hooks append to the one table under the reducer's single registration rule.
    text = _once(text, "  if $lr != 0x0215f2bc && ((",
                 "  if $lr != 0x0215f2bc && (($r1 >= 0x%x && $r1 < 0x%x) || (" % SHARED_IDS, "ordinary shared range")
    shared = SHARED_ANIM.replace('@CAP@', str(capacity))
    text = _once(text, 'break *0x0206CA8C\n', shared + '\nbreak *0x0206CA8C\n', 'shared animation entry')
    head = ("# GENERATED by scripts/gdb/fxo_tracker.py (make_probe_pt19.py + FXPOS chase for every object + heartbeat/overflow rows; "
            "banks 0x%x..0x%x%s; life %d capacity %d); do not edit.\n"
            % (lo, hi, "".join(",0x%x" % b for b in extra_banks), life, capacity))
    if lifecycle:
        sys.path.insert(0, str(HERE.parent))
        import fxo_lifecycle
        return fxo_lifecycle.splice(head + text, life, capacity)
    return head + text


def registration_predicate(text):
    """The generated ordinary-entry registration condition of probe `text` as a function (effect id, lr) -> bool. Only the
    comparison grammar the generator writes is admitted; anything else is a changed producer and raises ValueError."""
    match = re.search(r"^  if \$lr != 0x0215f2bc && (.+)$", text, re.MULTILINE)
    if match is None:
        raise ValueError("FXO registration predicate changed; qualify against the current producer")
    expression = match[1].replace("$r1", "effect").replace("&&", " and ").replace("||", " or ")
    tree = ast.parse(expression, mode="eval")
    allowed = (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.BinOp, ast.RShift, ast.Compare, ast.GtE, ast.LtE, ast.Gt, ast.Lt,
               ast.Eq, ast.NotEq, ast.Constant, ast.Name, ast.Load)
    if any(not isinstance(n, allowed) or isinstance(n, ast.Name) and n.id != "effect" for n in ast.walk(tree)):
        raise ValueError("unsupported FXO registration predicate")
    code = compile(tree, "<generated FXO registration predicate>", "eval")
    return lambda effect, lr: lr != BODY_LR and bool(eval(code, {"__builtins__": {}}, {"effect": effect}))


@functools.lru_cache(maxsize=1)
def initializer_paths():
    """{entry pc: frozenset of return addresses the ROM census admits for a shared-id initialization} (fxo_initializers.json)."""
    spec = importlib.util.spec_from_file_location("fxo_initializers", HERE.with_name("fxo_initializers.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load()


def initializer_refusal(anim):
    """None when a registering ANIM row came through a ROM-proven path, else (kind, detail). An initializer other than the two
    hooked entries is unknown_initializer; a shared id from a return address that is no census site of its entry, or a site the ROM
    excludes for shared ids, is unproven_initializer_path. Bank ids keep their existing rule."""
    if anim.pc not in (ANIM_ENTRY, SHARED_ENTRY):
        return "unknown_initializer", "log line %d: object 0x%x id 0x%x at pc 0x%08x" % (anim.line + 1, anim.obj, anim.id, anim.pc)
    if SHARED_IDS[0] <= anim.id < SHARED_IDS[1] and anim.lr not in initializer_paths()[anim.pc]:
        return "unproven_initializer_path", "log line %d: object 0x%x id 0x%x at 0x%08x from lr 0x%08x" % (
            anim.line + 1, anim.obj, anim.id, anim.pc, anim.lr)
    return None


SHARED_RANGE = (0x2100, 0x2500)   # half-open bank range of the shared animation entry's 0x210000 <= id < 0x250000
SHARED_BANKS = tuple(range(*SHARED_RANGE))


def inventory_banks(fighter, vfx_sfx=VFX_SFX, shared=()):
    """Inventory banks (id >> 8) and caller additions outside the shared range: the explicit
    banks a tracking plan stores beside `shared_range` (and the extras generate() needs)."""
    data = json.loads(Path(vfx_sfx).read_text())
    banks = {int(s["effect"], 16) >> 8 for m in data["moves"][fighter] for s in m.get("spawns", [])}
    return sorted(b for b in banks | set(shared) if not SHARED_RANGE[0] <= b < SHARED_RANGE[1])


def banks_for_fighter(fighter, vfx_sfx=VFX_SFX, shared=()):
    """Inventory banks (id >> 8), the engine-wide shared ROM range, and caller additions."""
    return sorted(set(inventory_banks(fighter, vfx_sfx, shared)) | set(SHARED_BANKS))


def plan_banks(plan, key):
    """The banks a plan's `key` list covers, with the plan's `shared_range` expanded."""
    lo, hi = plan.get("shared_range", (0, 0))
    return sorted(set(plan.get(key, [])) | set(range(lo, hi)))


def capability_errors(plan):
    """Offline capability validation of a tracking plan: banks, window and capacity."""
    errs = []
    if "shared_range" in plan and list(plan["shared_range"]) != list(SHARED_RANGE):
        errs.append("shared_range %s is not the engine-wide shared bank range [0x%x, 0x%x)"
                    % (plan["shared_range"], *SHARED_RANGE))
    for b in sorted(set(plan_banks(plan, "required_banks")) - set(plan_banks(plan, "banks"))):
        errs.append("omitted bank 0x%x: the shared FXO pass must track every inventory and shared-effect bank" % b)
    if plan.get("life", 0) < plan.get("required_ticks", 0):
        errs.append("tracking window %s is shorter than the required tail %s" % (plan.get("life"), plan.get("required_ticks")))
    if plan.get("capacity", 0) < plan.get("expected_objects", 0):
        errs.append("capacity %s is below the expected object count %s" % (plan.get("capacity"), plan.get("expected_objects")))
    return errs


# ---------------------------------------------------------------------------------------------------------------------------------------
# reduction

ANIM = re.compile(r"ANIM gfc=(\d+) r0=(0x\w+) r1=(0x\w+) lr=(0x\w+)(?: pc=(0x\w+))?")
FXS = re.compile(r"FXS gfc=(\d+) r0=(0x\w+) r1=(-?\d+) r2=(-?\d+)")
FXO = re.compile(r"FXO gfc=(\d+) n=(\d+) id=(0x\w+) obj=(0x\w+) age=(\d+) o=(0x\w+),(0x\w+),(0x\w+) e=(\S*)(?: par=(-?\d+),(-?\d+))?")
FXPOS = re.compile(r"FXPOS gfc=(\d+)(?: n=(\d+))? age=(\d+) id=(0x\w+) (.*)")
FXT = re.compile(r"FXT gfc=(\d+) n=(\d+)(?: life=(\d+) cap=(\d+))?")
FXOVF = re.compile(r"FXOVF gfc=(\d+) id=(0x\w+) obj=(0x\w+) cap=(\d+)")

# The ordered event list. Every event keeps its line number; nothing is keyed by tick in a way that can overwrite another observation.
Anim = namedtuple("Anim", "line gfc obj id lr pc")
Fxs = namedtuple("Fxs", "line gfc id x y")
Fxt = namedtuple("Fxt", "line gfc n life cap")
Ovf = namedtuple("Ovf", "line gfc id obj cap")
Fxo = namedtuple("Fxo", "line gfc n id obj age o0 o1 e par")
Fxpos = namedtuple("Fxpos", "line gfc n age id row")
ProbeEvent = namedtuple("ProbeEvent", "line gfc kind")

# Rejections of the event interpreter (a row so marked is never a sample) and their missing-evidence kinds.
REJECT = {"outside": "dump_outside", "beyond": "index_beyond_count", "order": "dump_order", "early": "sample_before_registration",
          "interleaved": "dump_interleaved", "life": "row_past_life"}


def _ints(text):
    return [int(v) for v in text.split(",")]


IDENTITY_BLOCK = [0, 0x1000, 0x1000, 0x1000, 0, 0, 0x1000]   # node words +0x30..+0x48 of every untransformed node in the j6rec captures


def _chain(text):
    """A lifecycle-layer chain field (node:x:y:z:flags:w30.w34.w38.w3c.w40.w44.w48;...;end=0x..) -> [{node, q12, flags, block}]."""
    nodes = []
    for part in text.split(";"):
        if not part or part.startswith("end="):
            break
        f = part.split(":")
        nodes.append({"node": int(f[0], 16), "q12": [int(f[1]), int(f[2]), int(f[3])], "flags": int(f[4], 16),
                      "block": [int(v, 16) for v in f[5].split(".")] if "." in f[5] else None})
    return nodes


HEARTBEAT_ROW = re.compile(r"(LFF) gfc=(\d+)\b")


def parse_events(lines):
    """A probe log -> ordered typed FXO events plus other clocked probe rows (PH or game events). Unclocked lines are ignored.
    A heartbeat-stop row (HEARTBEAT_ROWS: the lifecycle layer's LFF, printed by the FXT stop's own commands) is part of that stop
    only on the lines directly after its FXT at the same gfc; anywhere else it is an ordinary clocked row and closes the dump."""
    out, beat = [], None
    for i, ln in enumerate(lines):
        m = HEARTBEAT_ROW.match(ln)
        if m and beat is not None and beat == (i - 1, int(m[2])):
            beat = (i, beat[1])
            continue
        beat = None
        m = ANIM.match(ln)
        if m:
            out.append(Anim(i, int(m[1]), int(m[2], 16), int(m[3], 16), int(m[4], 16), int(m[5], 16) if m[5] else ANIM_ENTRY))
            continue
        m = FXS.match(ln)
        if m:
            out.append(Fxs(i, int(m[1]), int(m[2], 16), int(m[3]), int(m[4])))
            continue
        m = FXT.match(ln)
        if m:
            out.append(Fxt(i, int(m[1]), int(m[2]), int(m[3]) if m[3] else None, int(m[4]) if m[4] else None))
            beat = (i, int(m[1]))
            continue
        m = FXOVF.match(ln)
        if m:
            out.append(Ovf(i, int(m[1]), int(m[2], 16), int(m[3], 16), int(m[4])))
            continue
        m = FXPOS.match(ln)
        if m:
            kv = dict(re.findall(r"(\w+)=(\S+)", m[5]))
            row = {"unresolved": kv["unresolved"]} if "unresolved" in kv else {
                "grp": int(kv["grp"], 16), "body": int(kv["body"], 16), "body_q12": _ints(kv["bodypos"]), "el_q12": _ints(kv["elpos"]),
                "p1phys": _ints(kv["p1phys"])}
            if "chain" in kv:
                row["chain"] = _chain(kv["chain"])
            out.append(Fxpos(i, int(m[1]), int(m[2]) if m[2] is not None else None, int(m[3]), int(m[4], 16), row))
            continue
        m = FXO.match(ln)
        if m:
            out.append(Fxo(i, int(m[1]), int(m[2]), int(m[3], 16), int(m[4], 16), int(m[5]), int(m[6], 16), int(m[7], 16), m[9],
                           (int(m[10]), int(m[11])) if m[10] is not None else None))
            continue
        m = re.match(r"([A-Z][A-Z0-9]*) gfc=(\d+)\b", ln)
        if m:
            out.append(ProbeEvent(i, int(m[2]), m[1]))
    return tuple(out)


def reduce(lines, *, inventory=None, expect_targets=None, anchor_gfc=None, required_ticks=None, life=None, banks=None, baseline=None,
           legacy=False, lifecycle=False):
    """One probe log -> fxo-tracks/v1. The ordered events are executed the way the generated probe runs (_interpret) and the result is
    one validated Snapshot (_snapshot, validate_snapshot); `ok`, the inventory and the carried proof all derive from it:

    * the table starts at zero (or at the baseline's carried entries); a tracked ANIM appends the exact entry (object, id, birth gfc) at
      the current count; each dump tick prints `FXT n=<count>` and then `while $fxo_i < $fxo_n` prints each entry's FXO row and one
      FXPOS row in index order. Membership, identity, pairing and clocks are validated before any sample or position is accepted.
    * `banks` (the probe's tracked id >> 8 set) is proof input. Without it the tracked banks are inferred from the FXO rows for
      inspection only: `banks_undeclared`, never ok, never inventory_empty, no carried proof.
    * the cut clock is the last observed dump. The snapshot holds every index 0..count-1 as an ended generation no later than the cut;
      a registration after the final dump, or a reinit landing past it, is `past_cut` until a later window's dump observes it.
    * `legacy=True` admits FXO rows without their FXPOS row (logs older than the generated probe). It never certifies placement: the
      result carries `legacy_uncertified` and is never ok.
    * `carried` is the snapshot in its JSON form, present only when ok; the next window's `baseline` is read back through the same
      validator (validate_carried), and must declare the same banks.
    * `lifecycle=True` reads the rows of generate(..., lifecycle=True) as further evidence (_Lifecycle): successful initializations
      decide registrations and reinits, instruction-time frees and replacements are checked against the dump-observed ends, the draw
      rows decide what was rendered and when, and the FXPOS parent chain resolves space through the native transform graph."""
    inv = inventory or {}
    fighters = {k: dict(v) for k, v in inv.get("fighters", {}).items()}
    world_objects = inv.get("world_objects", {})
    facing = inv.get("facing", {})
    expect_targets = expect_targets or {}
    declared = tuple(sorted(set(banks))) if banks is not None else None
    events = parse_events(lines)
    anims = [e for e in events if isinstance(e, Anim)]
    beats = [e for e in events if isinstance(e, Fxt)]
    overflow = [{"gfc": e.gfc, "id": e.id, "obj": e.obj, "cap": e.cap} for e in events if isinstance(e, Ovf)]
    fxs = {}
    for e in events:
        if isinstance(e, Fxs):
            fxs.setdefault(e.gfc, []).append((e.id, e.x, e.y))
    probe_life = next((b.life for b in beats if b.life is not None), None)
    probe_cap = next((b.cap for b in beats if b.cap is not None), None)

    missing = []
    carried_in = _carried_baseline(baseline, declared, missing)
    base = carried_in["generations"]
    _chronology(events, carried_in, missing)
    # the probe's breakpoint condition: the declared banks; inspection mode infers them from the FXO stream and the baseline
    tracked = set(declared) if declared is not None else {e.id >> 8 for e in events if isinstance(e, Fxo)} | {g["id"] >> 8 for g in base.values()}
    rows_of, order = {}, []
    for e in events:
        if isinstance(e, Fxo):
            if e.n not in rows_of:
                rows_of[e.n] = []
                order.append(e.n)
            rows_of[e.n].append(e)
    # each dump tick's position in the log: its FXT row (heartbeat probe) or, in a log that predates FXT, its first FXO row
    dump_at = {}
    for e in events:
        if isinstance(e, Fxt) or (isinstance(e, Fxo) and not beats):
            dump_at.setdefault(e.gfc, e.line)
    table, rejected, fault, pos = _interpret(events, beats, tracked, carried_in, legacy, missing)
    p1_seen = {e.gfc: tuple(e.row["p1phys"]) for e in pos["accepted"].values() if "p1phys" in e.row}
    life_ev = _Lifecycle(lines, anims, dump_at, missing) if lifecycle else None
    if life_ev is not None:
        for label, seen in life_ev.fighters.items():
            fighters.setdefault(label, seen)
    if "p1" not in fighters and p1_seen:
        fighters["p1"] = p1_seen

    tracks = {}
    for n in order:
        if n in base:
            _check_baseline_rows(base[n], rows_of[n], missing)
            continue
        tracks[n] = _generation(n, rows_of[n], table[n] if n < len(table) else None,
                                life_ev.successful if life_ev is not None else anims, dump_at, rejected, fault)
    ended = {n: t["end"]["gfc"] for n, t in tracks.items()
             if t["end"] and t["end"]["kind"] in ("freed", "reinit")}
    ended.update({n: t["end"]["gfc"] for n, t in base.items()
                  if t["end"] and t["end"]["kind"] in ("freed", "reinit")})
    for problem in missing:
        if problem["kind"] != "fxo_missing":
            continue
        n = int(problem["track"].rsplit("#", 1)[1])
        dump_gfc = int(re.search(r"at gfc (\d+)", problem["detail"])[1])
        if n in ended and ended[n] <= dump_gfc:
            problem["detail"] += ", even after its end"
    for f, e in pos["bad"]:
        if f.n in tracks:
            tracks[f.n]["identity"].append({"gfc": e.gfc, "kind": "FXPOS", "id": e.id, "age": e.age, "n": e.n})
        else:
            missing.append({"track": "0x%06x#%d" % (f.id, f.n), "kind": "identity_mismatch",
                            "detail": "the FXPOS row at log line %d contradicts its FXO row" % (e.line + 1)})
    for n in order:
        if n not in tracks:
            continue
        t = tracks[n]
        t["gen"] = sum(1 for u in list(tracks.values()) + list(base.values()) if u["obj"] == t["obj"] and u["birth_gfc"] < t["birth_gfc"])
        t["creator_class"] = KINDS.get(t["creator_lr"], "unknown")
        pos_anchor = _positioned_birth(t, fxs)
        for s, line in zip(t["samples"], t["_rows"]):
            chain = pos["accepted"][line].row if line in pos["accepted"] else None
            _resolve(s, chain, fighters, world_objects, facing, pos_anchor)
            if life_ev is not None and s["why"] != "transform_unmeasured" and chain and chain.get("chain"):
                if s["space"] == "unresolved":
                    life_ev.resolve(s, chain["chain"], fighters, pos["accepted"].values())
                else:
                    independent = dict(s, space="unresolved", world_q8=None)
                    life_ev.resolve(independent, chain["chain"], fighters, pos["accepted"].values())
                    if independent["space"] != "unresolved" and independent["world_q8"] != s["world_q8"]:
                        missing.append({"track": "0x%06x#%d" % (t["id"], n), "kind": "space_rule_disagreement",
                                        "detail": "parent chain and position witness disagree at gfc %d" % s["gfc"]})
        t["birth"] = {"source": "positioned_spawn" if pos_anchor and t["samples"] and t["samples"][0]["target"] == "fxs" else "object_sample"}
        if life_ev is not None:
            life_ev.track(t, table[n] if n < len(table) else None, fighters, pos["accepted"].values(), missing)
        del t["_rows"], t["vt"], t["_last_age"]
        t["id_hex"] = "0x%06x" % t["id"]
        _judge_track(t, expect_targets, probe_life if life is None else life, missing)

    _reconcile(tracks, table, declared, missing)
    if overflow:
        missing.append({"track": None, "kind": "capacity_overflow", "detail": "%d object(s) dropped at capacity %d" % (len(overflow), overflow[0]["cap"])})
    if beats and required_ticks is not None and anchor_gfc is not None:
        have = {b.gfc for b in beats}
        absent = [g for g in range(anchor_gfc, anchor_gfc + required_ticks) if g not in have]
        if absent:
            missing.append({"track": None, "kind": "window_gap", "detail": "no heartbeat at gfc %s" % absent[:8]})
    if legacy:
        missing.append({"track": None, "kind": "legacy_uncertified",
                        "detail": "legacy mode admits FXO rows without FXPOS: it never certifies placement and is never ok"})
    out_tracks = [tracks[n] for n in order if n in tracks]
    snap = _snapshot(declared, beats, table, out_tracks, base, pos["state"])
    candidate = _carried_json(snap)
    # the producer reads its own carried proof back through the baseline reader's validator: what it certifies, the next window accepts
    have = {m["kind"] for m in missing}
    missing += [p for p in validate_carried(candidate) if p["kind"] not in have]
    ok = not missing
    return {"schema": "fxo-tracks/v1", "mode": "legacy" if legacy else "proof" if declared is not None else "inspection",
            "banks": list(declared) if declared is not None else None,
            "probe": {"life": probe_life, "capacity": probe_cap, "heartbeat": bool(beats)},
            "inventory": _inventory(snap, out_tracks, base),
            "inventory_empty": ok and snap.count == 0,
            "tracks": out_tracks, "carried": candidate if ok else None,
            "missing": missing, "ok": ok}


def _interpret(events, beats, tracked, carried_in, legacy, missing):
    """Run the generated probe over the ordered events, the table as the authority. The table starts as the baseline's carried entries;
    a tracked ANIM (not the body setter, its bank in `tracked`, not dropped at capacity by the FXOVF printed right after it) appends the
    exact entry (object, id, birth gfc) at the current count. Every event reads the one frame counter, so the clock never runs backward
    across event kinds (event_clock_regression). Each FXT observes that table: its count is the table length (fxt_inconsistent), never
    below the previous count (fxt_count_regress), one per tick in increasing gfc (fxt_duplicate, dump_order), and no entry it counts
    was born after it (future_registration_in_count). Each FXO row is a print of entry n inside its tick's dump: in the block
    (dump_outside), below the count (index_beyond_count), in loop order (dump_order), with the entry already appended
    (sample_before_registration) and carrying exactly that entry's object and id (identity_mismatch) and gfc - age == its birth
    (clock_mismatch). Each FXPOS row belongs to the FXO row printed immediately before it, one per FXO, with the same gfc, index, age
    and id; any other FXPOS row is an orphan (fxpos_orphan) and never evidence, and an FXO row without its FXPOS row is fxpos_missing
    (outside legacy mode). A registration after the final dump is past_cut: no dump of this window counts it.
    An entry never changes once appended, so every row whose index has an entry is checked against it, whatever its membership.
    The phase starts with PH rows at FXT, advances to the paired table rows at the first FXO, and closes on any game event.
    Life/capacity come from the baseline or first heartbeat, constrain every row/append, and never change at later heartbeats.
    The returned state preserves the last event clock separately from the dump cut, for union-equivalent continuation.
    Returns (table, {FXO line: membership rejection}, {FXO line: "identity" | "clock"}, {"accepted": {FXO line: FXPOS}, "bad": [(FXO,
    FXPOS)]})."""
    table = [{"n": n, "obj": g["obj"], "id": g["id"], "birth_gfc": g["birth_gfc"], "anim": None} for n, g in sorted(carried_in["generations"].items())]
    rejected, pairs, orphans, notes, rows = {}, {}, [], {}, []
    prev = block = last_ev = None
    def finish_dump():
        if block is not None:
            for t in block["pending"].values():
                missing.append({"track": "0x%06x#%d" % (t["id"], t["n"]), "kind": "fxo_missing",
                                "detail": "object 0x%x entry %d requires an FXO row at gfc %d (age %d <= life %d)"
                                % (t["obj"], t["n"], block["fxt"].gfc, block["fxt"].gfc - t["birth_gfc"], life)})
            block["pending"].clear()

    floor = carried_in["count"]
    # The generated dump has no inferior resume between FXT, PH and the final FXPOS. Only a game event closes it.
    # Keep its clock bound even when the final game event is later than the last observed dump (the cut).
    clock = carried_in["last_event_gfc"]
    config = (carried_in["life"], carried_in["capacity"])
    if config == (None, None) and beats:
        config = (beats[0].life, beats[0].cap)
    life, capacity = config
    last_dump = max((i for i, e in enumerate(events) if isinstance(e, Fxt)), default=None)
    for i, e in enumerate(events):
        if clock is not None and e.gfc < clock:
            notes.setdefault("event_clock_regression", []).append("log line %d: gfc %d after gfc %d" % (e.line + 1, e.gfc, clock))
        clock = e.gfc if clock is None else max(clock, e.gfc)
        if isinstance(e, (Anim, Fxs, Ovf)) or (isinstance(e, ProbeEvent) and e.kind != "PH"):
            finish_dump()
            if block is not None:
                block["phase"] = "closed"
        if isinstance(e, Anim):
            nxt = events[i + 1] if i + 1 < len(events) else None
            dropped = isinstance(nxt, Ovf) and (nxt.gfc, nxt.id, nxt.obj) == (e.gfc, e.id, e.obj)
            if e.lr != BODY_LR and (e.id >> 8) in tracked and not dropped:
                if capacity is not None and len(table) >= capacity:
                    notes.setdefault("count_above_capacity", []).append("registration at log line %d requires FXOVF at capacity %d" % (e.line + 1, capacity))
                table.append({"n": len(table), "obj": e.obj, "id": e.id, "birth_gfc": e.gfc, "anim": e})
                refusal = initializer_refusal(e)
                if refusal is not None:
                    notes.setdefault(refusal[0], []).append(refusal[1])
                if last_dump is not None and i > last_dump:
                    notes.setdefault("past_cut", []).append("entry %d (object 0x%x id 0x%x) registered at gfc %d after the final dump" % (
                        len(table) - 1, e.obj, e.id, e.gfc))
        elif isinstance(e, Fxt):
            finish_dump()
            if (e.life, e.cap) != config:
                notes.setdefault("probe_config_changed", []).append("log line %d: %s instead of %s" % (e.line + 1, (e.life, e.cap), config))
            if life is None or capacity is None or life < 1 or capacity < 1:
                notes.setdefault("probe_config_invalid", []).append("life and capacity must be declared positive integers")
            if capacity is not None and e.n > capacity:
                notes.setdefault("count_above_capacity", []).append("gfc %d: count %d exceeds capacity %d" % (e.gfc, e.n, capacity))
            if prev is not None and e.gfc == prev.gfc:
                notes.setdefault("fxt_duplicate", []).append("gfc %d: n=%d then n=%d" % (e.gfc, prev.n, e.n))
            elif prev is not None and e.gfc < prev.gfc:
                notes.setdefault("dump_order", []).append("dump at gfc %d after gfc %d" % (e.gfc, prev.gfc))
            low = prev.n if prev is not None else floor
            if e.n < low:
                notes.setdefault("fxt_count_regress", []).append("gfc %d: n=%d after n=%d%s" % (
                    e.gfc, e.n, low, "" if prev is not None else " carried by the baseline"))
            if e.n != len(table):
                notes.setdefault("fxt_inconsistent", []).append("gfc %d: n=%d, table %d" % (e.gfc, e.n, len(table)))
            future = [t["n"] for t in table[:e.n] if t["birth_gfc"] > e.gfc]
            if future:
                notes.setdefault("future_registration_in_count", []).append("gfc %d counts entries %s born later" % (e.gfc, future[:8]))
            prev, block = e, {"fxt": e, "last": -1, "phase": "ph", "ph_count": 0,
                             "pending": {t["n"]: t for t in table if life is not None and 0 <= e.gfc - t["birth_gfc"] <= life}}
        elif isinstance(e, Fxo):
            why = None
            if e.e != "none" and not re.fullmatch(r"0x[0-9a-fA-F]+,0x[0-9a-fA-F]+,-?\d+,-?\d+,-?\d+,0x[0-9a-fA-F]+", e.e):
                notes.setdefault("element_malformed", []).append("FXO at log line %d requires e=none or six numeric fields" % (e.line + 1))
                why = "element"
            if beats:
                if block is None or e.gfc != block["fxt"].gfc:
                    why = "outside"
                elif block["phase"] == "closed":
                    why = "interleaved"
                elif e.n >= block["fxt"].n:
                    why = "beyond"
                elif e.n <= block["last"]:
                    why = "order"
                if block is not None and e.gfc == block["fxt"].gfc:
                    block["last"] = max(block["last"], e.n)
                    if block["phase"] != "closed":
                        block["phase"] = "rows"
            if life is not None and e.age > life:
                notes.setdefault("row_past_life", []).append("log line %d: age %d exceeds life %d" % (e.line + 1, e.age, life))
                why = why or "life"
            if why is None and e.n >= len(table):
                why = "early"                 # printed before its entry exists (resolved below)
            if why:
                rejected[e.line] = why
            elif block is not None:
                block["pending"].pop(e.n, None)
            rows.append(e)
        elif isinstance(e, Fxpos):
            if beats and block is not None and block["phase"] == "closed" and e.gfc == block["fxt"].gfc:
                notes.setdefault("dump_interleaved", []).append("FXPOS at log line %d after a game event closed the dump" % (e.line + 1))
            if life is not None and e.age > life:
                notes.setdefault("row_past_life", []).append("FXPOS at log line %d exceeds life %d" % (e.line + 1, life))
            if isinstance(last_ev, Fxo) and last_ev.line not in pairs:
                pairs[last_ev.line] = (last_ev, e)
            else:
                orphans.append(e.line)
        elif isinstance(e, ProbeEvent) and e.kind == "PH" and beats:
            if block is None or e.gfc != block["fxt"].gfc or block["phase"] != "ph":
                notes.setdefault("dump_interleaved", []).append("PH at log line %d outside the PH phase" % (e.line + 1))
            else:
                block["ph_count"] += 1
                if block["ph_count"] > 6:
                    notes.setdefault("ph_above_capacity", []).append("PH at log line %d exceeds the six-row dump limit" % (e.line + 1))
        elif isinstance(e, Ovf):
            if e.cap != capacity:
                notes.setdefault("probe_config_changed", []).append("FXOVF capacity contradicts the probe configuration")
            if not isinstance(last_ev, Anim) or (last_ev.gfc, last_ev.id, last_ev.obj) != (e.gfc, e.id, e.obj) or len(table) != capacity:
                notes.setdefault("overflow_inconsistent", []).append("FXOVF at log line %d without a matching full-table registration" % (e.line + 1))
        last_ev = e
    finish_dump()
    # a row printed before its entry existed is early if a later ANIM appends that entry; with no entry ever, the generation is
    # unregistered (no_registration, its first row fixes it) and the FXT counts already disagree with the table
    fault = {}
    for e in rows:
        if e.n >= len(table):
            if rejected.get(e.line) == "early":
                del rejected[e.line]
        elif (e.obj, e.id) != (table[e.n]["obj"], table[e.n]["id"]):
            fault[e.line] = "identity"
        elif e.gfc - e.age != table[e.n]["birth_gfc"]:
            fault[e.line] = "clock"
    accepted, bad = {}, []
    for f, e in pairs.values():
        if (e.gfc, e.age, e.id) != (f.gfc, f.age, f.id) or e.n not in (None, f.n):
            bad.append((f, e))
        elif f.line not in rejected and f.line not in fault:
            accepted[f.line] = e
    unpaired = [e.line for e in rows if e.line not in pairs]
    if unpaired and not legacy:
        notes["fxpos_missing"] = ["FXO rows at log lines %s" % [r + 1 for r in unpaired[:8]]]
    details = {"probe_config_changed": "probe configuration is constant within and across windows: %s",
               "element_malformed": "the probe prints e=none or exactly six numeric fields: %s",
               "ph_above_capacity": "the probe PH table holds at most six objects: %s",
               "probe_config_invalid": "probe configuration cannot establish evidence: %s",
               "count_above_capacity": "the probe cannot append above capacity without FXOVF: %s",
               "row_past_life": "the probe age <= life guard excludes these rows: %s",
               "dump_interleaved": "a game event closed the atomic dump: %s",
               "overflow_inconsistent": "FXOVF requires a full table and its preceding tracked ANIM: %s",
               "event_clock_regression": "every event reads one frame counter, so the clock never runs backward: %s",
               "fxt_duplicate": "one dump per tick: the heartbeat is printed twice for %s",
               "dump_order": "dump ticks must increase: %s",
               "fxt_count_regress": "the cumulative FXT object count decreased: %s",
               "fxt_inconsistent": "the FXT count is not the registration table's length: %s",
               "future_registration_in_count": "a heartbeat counts an entry born after it: %s",
               "past_cut": "missing evidence until a later dump counts it: %s",
               "fxpos_missing": "the generated probe prints one FXPOS row after every FXO row; a modern capture needs complete pairs: %s",
               "unknown_initializer": "only 0x02023894 and 0x02023924 initialize an animation by id (fxo_initializers.json): %s",
               "unproven_initializer_path": "a shared id from a return address the ROM census does not admit for that entry: %s"}
    for kind, what in notes.items():
        missing.append({"track": None, "kind": kind, "detail": details[kind] % what[:8]})
    for why, kind in REJECT.items():
        rows_ = sorted(line for line, w in rejected.items() if w == why)
        if rows_ and why != "early":      # early rows are reported per track with the first-tick check (_judge_track)
            missing.append({"track": None, "kind": kind, "detail": "FXO rows at log lines %s rejected" % [r + 1 for r in rows_[:8]]})
    if orphans:
        missing.append({"track": None, "kind": "fxpos_orphan", "detail": "FXPOS rows at log lines %s do not follow their own FXO row in a "
                        "dump: never evidence" % [r + 1 for r in orphans[:8]]})
    return table, rejected, fault, {"accepted": accepted, "bad": bad,
                                  "state": {"last_event_gfc": clock, "life": life, "capacity": capacity}}


def _chronology(events, carried_in, missing):
    """A window follows its baseline: every event is after the baseline's last dump tick (baseline_chronology)."""
    last = carried_in["last_gfc"]
    first = min((e.gfc for e in events), default=None)
    if last is not None and first is not None and first <= last:
        missing.append({"track": None, "kind": "baseline_chronology",
                        "detail": "the window starts at gfc %d, not after the baseline's last dump at gfc %d" % (first, last)})


def _generation(n, rows, entry, anims, dump_at, rejected, fault):
    """The generation of table index n from its FXO rows (log order). Its table entry fixes (object, id, birth); with no entry (no ANIM
    ever registered index n) the first row does, and the generation is unregistered.
    Ticks are dump ticks: an ANIM at gfc g printed after that tick's dump takes effect from g+1, so the old object's row at g is still its
    own sample and the new generation's first sample is at age 1. The reinit is the first ANIM on the object printed after the
    registration (a same-tick repeat included: that makes a zero-duration generation, which the snapshot rejects as unmodeled).
    Every row has its clock and order checked, including rows after the end; a row the interpreter rejected, or one before the
    generation's first tick, is never a sample."""
    def tick(g, i):
        return g if i < dump_at.get(g, i + 1) else g + 1
    m0 = rows[0]
    reg = entry["anim"] if entry else None
    obj, rid, birth = (entry["obj"], entry["id"], entry["birth_gfc"]) if entry else (m0.obj, m0.id, m0.gfc - m0.age)
    reinit = min((tick(a.gfc, a.line) for a in anims if a.obj == obj and (a.line > reg.line if reg else a.gfc > birth)), default=None)
    first_tick = tick(birth, reg.line) if reg else birth
    t = {"n": n, "id": rid, "obj": obj, "birth_gfc": birth, "first_tick": first_tick, "vt": None,
         "end": None, "samples": [], "creator_lr": reg.lr if reg else None, "registered": reg is not None, "_rows": [], "clock": [],
         "age_order": [], "identity": [], "early": [], "_last_age": None}
    for m in rows:
        # a registered index is judged by the interpreter against its table entry; an unregistered one against its first row
        f = fault.get(m.line) if entry else "identity" if (m.obj, m.id) != (obj, rid) else "clock" if m.gfc != birth + m.age else None
        if f == "identity":
            t["identity"].append({"gfc": m.gfc, "kind": "FXO", "id": m.id, "obj": m.obj, "age": m.age})
            continue
        if t["_last_age"] is not None and m.age <= t["_last_age"]:
            t["age_order"].append(m.age)
        t["_last_age"] = m.age
        if f == "clock":
            t["clock"].append({"age": m.age, "gfc": m.gfc, "birth_gfc": birth})
            continue
        if t["vt"] is None:
            t["vt"] = m.o0
        if rejected.get(m.line) == "early" or m.gfc < first_tick:
            t["early"].append(m.gfc)
            continue
        if m.line in rejected or t["end"] is not None:
            continue
        if reinit is not None and birth + m.age >= reinit:
            t["end"] = {"kind": "reinit", "gfc": reinit, "age": reinit - birth}
            continue
        state = m.o1 & 0xF
        if m.e == "none":
            t["end"] = {"kind": "freed", "gfc": m.gfc, "age": m.age}
            continue
        e = m.e.split(",")
        parent = int(e[5], 16)
        if m.o0 != t["vt"] or (state == 0 and parent == 0):
            t["end"] = {"kind": "freed", "gfc": m.gfc, "age": m.age}
            continue
        t["samples"].append({"age": m.age, "gfc": m.gfc, "state": state, "q12": [int(e[2]), int(e[3]), int(e[4])], "parent": parent,
                             "par_q12": list(m.par) if m.par is not None else None})
        t["_rows"].append(m.line)
    if t["end"] is None and reinit is not None:
        t["end"] = {"kind": "reinit", "gfc": reinit, "age": reinit - birth}
    return t


# ---------------------------------------------------------------------------------------------------------------------------------------
# the validated snapshot: the one type the producer certifies and the next window's baseline reader consumes

Snapshot = namedtuple("Snapshot", "banks count last_gfc last_event_gfc life capacity generations")
ENDED = ("freed", "reinit")


def _snapshot(declared, beats, table, tracks, base, state):
    """The window's state at its cut: the declared banks, the table length the dumps establish (the largest FXT count, or the table's
    final length when it grew after the last dump), the cut clock (the last observed dump) and one generation per index: the baseline's
    carried ones unchanged plus every one observed here (an end that is not a recorded free or reinit is open: None)."""
    gens = {n: dict(g) for n, g in base.items()}
    for t in tracks:
        end = {k: t["end"][k] for k in ("kind", "gfc", "age")} if t["end"] is not None and t["end"]["kind"] in ENDED else None
        ages = [s["age"] for s in t["samples"]]
        gens[t["n"]] = {"n": t["n"], "obj": t["obj"], "id": t["id"], "birth_gfc": t["birth_gfc"], "end": end,
                        "provenance": {"first_tick": t["first_tick"], "live_ages": [ages[0], ages[-1]] if ages else None}}
    count = max([b.n for b in beats] + [len(table)]) if beats else None
    last = max(b.gfc for b in beats) if beats else None
    return Snapshot(declared, count, last, state["last_event_gfc"], state["life"], state["capacity"],
                    tuple(gens[n] for n in sorted(gens)))


def _carried_json(snap):
    return {"banks": list(snap.banks) if snap.banks is not None else None, "count": snap.count, "last_gfc": snap.last_gfc,
            "last_event_gfc": snap.last_event_gfc, "life": snap.life, "capacity": snap.capacity,
            "generations": [dict(g) for g in snap.generations]}


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _snapshot_of(carried):
    """A carried proof (JSON) -> Snapshot, or None when its shape is not a snapshot's."""
    if not isinstance(carried, dict):
        return None
    banks, count, last, gens = (carried.get(k) for k in ("banks", "count", "last_gfc", "generations"))
    if banks is not None and not (isinstance(banks, list) and all(_is_int(b) for b in banks)):
        return None
    if count is not None and not (_is_int(count) and count >= 0):
        return None
    if (last is not None and not _is_int(last)) or not isinstance(gens, list):
        return None
    event, life, capacity = (carried.get(k) for k in ("last_event_gfc", "life", "capacity"))
    if not all(k in carried for k in ("last_event_gfc", "life", "capacity")) or any(
            v is not None and not _is_int(v) for v in (event, life, capacity)):
        return None
    for g in gens:
        if not isinstance(g, dict) or not all(_is_int(g.get(k)) for k in ("n", "obj", "id", "birth_gfc")):
            return None
        prov, end = g.get("provenance"), g.get("end")
        if not isinstance(prov, dict) or not _is_int(prov.get("first_tick")):
            return None
        ages = prov.get("live_ages")
        if ages is not None and not (isinstance(ages, list) and len(ages) == 2 and all(_is_int(a) for a in ages)):
            return None
        if end is not None and not (isinstance(end, dict) and end.get("kind") in ENDED and _is_int(end.get("gfc"))):
            return None
    if len({g["n"] for g in gens}) != len(gens):
        return None
    return Snapshot(tuple(banks) if banks is not None else None, count, last, event, life, capacity,
                    tuple(sorted(gens, key=lambda g: g["n"])))


def validate_snapshot(snap):
    """The snapshot invariants, one list of missing-evidence entries (empty: valid):
      banks_undeclared         the bank scope is a declared, non-empty set
      no_heartbeat             there is a cut clock (an observed dump)
      index_beyond_count       no generation above the count
      unaccounted_index        every index 0..count-1 has a generation
      incomplete_window        every generation ended at a recorded free or reinit (open generations are not carried)
      bank_scope               every generation's bank is declared
      probe_config_invalid     life and capacity are positive, fixed proof inputs
      count_above_capacity     table count does not exceed capacity
      row_past_life            live observations and recorded free rows obey the life guard
      snapshot_malformed       last_event_gfc is no earlier than the cut
      past_cut                 max(birth_gfc, end.gfc) <= last_gfc, the cut clock
      unmodeled_zero_duration  a generation lives at least one tick (first tick < end); same-tick repeats are not modeled
      generation_overlap       generations at one object do not overlap: the older ends no later than the newer's first tick"""
    out = []

    def bad(kind, track, detail):
        out.append({"track": track, "kind": kind, "detail": detail})
    if not snap.banks:
        bad("banks_undeclared", None, "no declared bank set (banks= / --banks): inferred scope is inspection only, never a proof")
    if snap.last_gfc is None:
        bad("no_heartbeat", None, "no FXT rows: the registered inventory, the window and an empty inventory cannot be established")
    if snap.last_gfc is not None and (snap.last_event_gfc is None or snap.last_event_gfc < snap.last_gfc):
        bad("snapshot_malformed", None, "last_event_gfc is below the cut clock")
    if snap.life is None or snap.capacity is None or snap.life < 1 or snap.capacity < 1:
        bad("probe_config_invalid", None, "life and capacity must be positive")
    if snap.count is not None and snap.capacity is not None and snap.count > snap.capacity:
        bad("count_above_capacity", None, "table count exceeds the probe capacity")
    gens = {g["n"]: g for g in snap.generations}
    if snap.count is not None:
        over = sorted(n for n in gens if n >= snap.count)
        if over:
            bad("index_beyond_count", None, "generations %s are above the table count %d" % (over[:8], snap.count))
        absent = sorted(set(range(snap.count)) - set(gens))
        if absent:
            bad("unaccounted_index", None, "table index(es) %s registered (count %d from zero) with no observed or baseline generation"
                % (absent[:8], snap.count))
    for g in snap.generations:
        name = "0x%06x#%d" % (g["id"], g["n"])
        end, first = g["end"], g["provenance"]["first_tick"]
        ages = g["provenance"].get("live_ages")
        if snap.life is not None and ((ages and max(ages) > snap.life) or
                                      (end is not None and end["kind"] == "freed" and end["gfc"] - g["birth_gfc"] > snap.life)):
            bad("row_past_life", name, "carried live or free evidence exceeds the probe life")
        if end is None:
            bad("incomplete_window", name, "no recorded free or reinit ends the generation by the cut: it is open, not carried")
        if snap.banks and (g["id"] >> 8) not in snap.banks:
            bad("bank_scope", name, "bank 0x%x is not declared %s" % (g["id"] >> 8, ["0x%x" % b for b in snap.banks]))
        latest = max(g["birth_gfc"], end["gfc"] if end else g["birth_gfc"])
        if snap.last_gfc is not None and latest > snap.last_gfc:
            bad("past_cut", name, "born or ended at gfc %d after the cut (last observed dump %d): missing evidence until a later dump "
                "observes it" % (latest, snap.last_gfc))
        if not g["birth_gfc"] <= first <= g["birth_gfc"] + 1:
            bad("snapshot_malformed", name, "first tick %d is neither the birth %d nor the tick after" % (first, g["birth_gfc"]))
        if end is not None and end["gfc"] <= first:
            bad("unmodeled_zero_duration", name, "ends at gfc %d, not after its first tick %d (a same-tick repeated registration or "
                "reinit): zero-duration generations are not modeled" % (end["gfc"], first))
    by_obj = {}
    for g in snap.generations:
        by_obj.setdefault(g["obj"], []).append(g)
    for obj, gs in sorted(by_obj.items()):
        gs.sort(key=lambda g: (g["birth_gfc"], g["n"]))
        for old, new in zip(gs, gs[1:]):
            first = new["provenance"]["first_tick"]
            if old["end"] is None or old["end"]["gfc"] > first:
                bad("generation_overlap", "0x%06x#%d" % (old["id"], old["n"]), "object 0x%x: generation born %d has no evidenced free or "
                    "reinit by the next generation's first tick %d (end %s)" % (obj, old["birth_gfc"], first, old["end"]))
    return out


def validate_carried(carried):
    """The baseline reader's validator on a carried proof (JSON): its shape, then validate_snapshot. reduce() runs it on its own output."""
    snap = _snapshot_of(carried)
    if snap is None:
        return [{"track": None, "kind": "snapshot_malformed", "detail": "the carried proof is not a snapshot (banks, count, last_gfc, last_event_gfc, life, capacity, "
                 "generations with n/obj/id/birth_gfc, provenance.first_tick and a free/reinit end)"}]
    return validate_snapshot(snap)


def _carried_baseline(baseline, declared, missing):
    """The proof an earlier reduction carries, read through validate_carried. Only an ok reduction counts, its snapshot must be valid
    (a generation past its own cut is baseline_chronology, anything else baseline_unproven) and its bank scope must be this window's
    declared one (baseline_scope). Anything else accounts nothing."""
    empty = {"count": 0, "last_gfc": None, "last_event_gfc": None, "life": None, "capacity": None, "generations": {}}
    if baseline is None:
        return empty
    c = baseline.get("carried") if isinstance(baseline, dict) else None
    if not isinstance(baseline, dict) or baseline.get("ok") is not True:
        missing.append({"track": None, "kind": "baseline_unproven", "detail": "the baseline reduction is not ok: it accounts no index"})
        return empty
    problems = validate_carried(c)
    if problems:
        kind = "baseline_chronology" if any(p["kind"] == "past_cut" for p in problems) else "baseline_unproven"
        missing.append({"track": None, "kind": kind, "detail": "the carried proof fails the snapshot validator (%s): it accounts no index"
                        % sorted({p["kind"] for p in problems})})
        return empty
    if declared is None or tuple(c["banks"]) != declared:
        missing.append({"track": None, "kind": "baseline_scope", "detail": "the baseline was proved for banks %s, this window declares %s: "
                        "it accounts no index" % (c["banks"], list(declared) if declared is not None else None)})
        return empty
    return {"count": c["count"], "last_gfc": c["last_gfc"], "last_event_gfc": c["last_event_gfc"],
            "life": c["life"], "capacity": c["capacity"], "generations": {g["n"]: dict(g) for g in c["generations"]}}


def _check_baseline_rows(b, rows, missing):
    """Rows of a baseline index in this log still carry its table entry (object, id, birth): gfc - age is the birth, so this is also
    each row's clock. After its end they are not samples."""
    bad = [m.gfc for m in rows if (m.obj, m.id, m.gfc - m.age) != (b["obj"], b["id"], b["birth_gfc"])]
    if bad:
        missing.append({"track": "0x%06x#%d" % (b["id"], b["n"]), "kind": "identity_mismatch",
                        "detail": "rows at gfc %s contradict the baseline generation" % bad[:8]})


def _inventory(snap, tracks, base):
    """The inventory view of the snapshot: every table index from zero to its count against the observed and baseline generations."""
    obs = sorted(t["n"] for t in tracks)
    if snap.count is None:
        return {"count": None, "observed": obs, "baseline": sorted(base), "unaccounted": []}
    return {"count": snap.count, "observed": obs, "baseline": sorted(base),
            "unaccounted": sorted(set(range(snap.count)) - set(obs) - set(base))}


def _reconcile(tracks, table, banks, missing):
    """The banks cross-check: every entry an ANIM on a declared bank appended (not the body setter, not dropped at capacity) is an
    observed generation."""
    if banks is None:
        return
    for e in table:
        if e["anim"] is not None and e["n"] not in tracks:
            missing.append({"track": "0x%06x" % e["id"], "kind": "registered_without_stream",
                            "detail": "ANIM at gfc %d registered object 0x%x (entry %d) with no FXO stream" % (e["birth_gfc"], e["obj"], e["n"])})


FRAME_ROW = re.compile(r'\{"type":"frame","frame":\d+,"gfc":(\d+)')
FIGHTER_ROW = re.compile(r'\{"type":"fighter","frame":\d+,"slot":(\d+),.*"physx":(-?\d+),"physy":(-?\d+)')


def _s32(v):
    return v - (1 << 32) if v >= 1 << 31 else v


class _Lifecycle:
    """The lifecycle layer's evidence (fxo_lifecycle.splice rows, decoded by fxo_lifecycle.lifecycle). Its pairing refusals are this
    window's missing evidence too.

    registration  the ANIM row and its LAE row are printed by the same stop, so the LAE on the next log line is that call. A registration
                  whose call failed is `init_failed_registration`: the probe's table holds an entry that never presented. Only
                  successful calls reinit an object (`successful`), so a failed initialization never ends the previous generation.
    ends          the instruction-time free of the object's allocation generation, or its next successful initialization, takes
                  effect at the dump of its tick when printed before that dump's FXT row, else at the next tick. The dump-observed end
                  must be that kind at that tick (`end_mismatch`). A free followed, before the same dump, by a successful
                  initialization of the reused address is what the dump calls a reinit; it is accepted only with that recorded
                  successor call; a dump-observed free or reinit with no recorded cause is
                  `end_unrecorded`.
    rendered      an LDX row is the draw of node `node` for `owner` past the draw function's cell, resource and frame-data gates
                  (0x01FF80FC). Each sample carries its tick's draw or None: cell, flip, attr and the rendered pose (pose()). The draw
                  runs after the dump, so a moving element is drawn where the next dump finds it (`moved`): the rendered position is
                  the draw's, never the dump sample's; `rendered` lists the first and last
                  drawn tick and the live ticks without a draw.
    birth         when the first dump sample is at age 1: a draw of the object at its birth tick after its successful return is the
                  age-0 sample (phase `draw`: element position and parent chain read by the draw stop). Without one, the birth is
                  `after_draw` only when that tick's draw pass ran entirely before the return and the object's first draw is at the
                  next tick, after its age-1 dump row: the age-1 sample is then the first state ever rendered. Otherwise
                  no_birth_sample stands.
    frames        an LFF row (frame anchor) is fighter `slot`'s transform node [[[collision element+8]+4]+0x50] and its parent chain.
                  When that node is the fighter's node (below) its parent names the fighters' frame at that tick, with no effect needed.
    space         an element whose parent node is a fighter's node (the node's position equals exactly one fighter's Q8 position x 16
                  at that tick and its words +0x30..+0x48 are the untransformed block) follows that fighter: world = (node + element)
                  >> 4. An element whose parent is the parent of such a fighter node (an LFF row's or an accepted FXPOS chain's) at the
                  same tick is in the fighters' own frame:
                  world = element >> 4. Fighter positions come from the probe's frame-anchor fighter rows unless the caller supplies
                  them."""

    def __init__(self, lines, anims, dump_at, missing):
        sys.path.insert(0, str(HERE.parent))
        import fxo_lifecycle as lc
        rows = lc.parse(lines)
        out = lc.lifecycle(rows)
        for m in out["missing"]:
            missing.append({"track": None, "kind": m["kind"], "detail": "log line %s: %s" % (m["line"], m["detail"])})
        self.calls = {c["line"]: c for c in out["calls"]}
        self.pres = {p["line"]: p for p in out["presentations"]}
        self.dump_at = dump_at
        self.draws, self.births, self.frames = {}, {}, {}
        for r in rows:
            if r.tag == "LFF" and isinstance(r.kv.get("chain"), str):
                self.frames.setdefault(r.gfc, {})["p%d" % (r.kv["slot"] + 1)] = _chain(r.kv["chain"])
            elif r.tag == "LDX":
                self.draws.setdefault(r.gfc, []).append(r)
            elif r.tag == "LBR":
                self.births[r.line] = r
        self.fighters, cur = {}, None
        for ln in lines:
            m = FRAME_ROW.match(ln)
            if m:
                cur = int(m[1])
                continue
            m = FIGHTER_ROW.match(ln)
            if m and cur is not None:
                self.fighters.setdefault("p%d" % (int(m[1]) + 1), {})[cur] = (int(m[2]), int(m[3]))
        self.successful = [a for a in anims if (self.call(a) or {}).get("ok")]
        self._roots = None

    def _tick(self, gfc, line):
        """The dump tick at which an event printed at log line `line` during tick `gfc` is first visible."""
        return gfc if line < self.dump_at.get(gfc, line + 1) else gfc + 1

    def call(self, a):
        c = self.calls.get(a.line + 1)
        return c if c is not None and (c["obj"], c["anim"]) == (a.obj, a.id) else None

    @staticmethod
    def _fighter_node(node, gfc, fighters):
        if node["block"] != IDENTITY_BLOCK:
            return None
        hits = [lab for lab, pos in fighters.items() if gfc in pos and node["q12"][:2] == [pos[gfc][0] * 16, pos[gfc][1] * 16]]
        return hits[0] if len(hits) == 1 else None

    def _frames(self, fighters, accepted):
        if self._roots is None:
            self._roots = {}
            for g, per in self.frames.items():
                for lab, ch in per.items():
                    if len(ch) >= 2 and self._fighter_node(ch[0], g, fighters) == lab:
                        self._roots.setdefault(g, set()).add(ch[1]["node"])
            for e in accepted:
                ch = e.row.get("chain")
                if ch and len(ch) >= 2 and self._fighter_node(ch[0], e.gfc, fighters) is not None:
                    self._roots.setdefault(e.gfc, set()).add(ch[1]["node"])
        return self._roots

    def resolve(self, s, nodes, fighters, accepted, at=None):
        """Resolve sample s (element q12, parent pointer) from its parent chain `nodes` (nodes[0] is the parent). `at` is the dump tick
        whose fighter positions the chain was read against (a draw row: the tick at which it is first visible, see _tick)."""
        if not nodes or nodes[0]["node"] != s["parent"]:
            return
        gfc, (x, y, _z) = s["gfc"] if at is None else at, s["q12"]
        lab = self._fighter_node(nodes[0], gfc, fighters)
        if lab is not None and len(nodes) >= 2:
            px, py = nodes[0]["q12"][:2]
            s.update(space="follow_fighter", target=lab, world_q8=[(px + x) >> 4, (py + y) >> 4], why=None, via="parent_node")
        elif nodes[0]["node"] in self._frames(fighters, accepted).get(gfc, ()):
            s.update(space="world", target="frame:0x%x" % nodes[0]["node"], world_q8=[x >> 4, y >> 4], why=None, via="fighter_frame")

    def pose(self, r, s, fighters, accepted, name, missing):
        """The rendered pose of draw row r (LDX): the element and parent chain the draw stop read, the draw transform r0 (words 0..3 the
        2x2 matrix, words 4..5 the translation, Q12 pixels) and the cell/flip/hflip/attr it drew (hflip None from a probe before it). Checked against the chain, never assumed:
        the translation must be the sum of the chain's positions and every parent block the untransformed one (draw_uncomposed
        otherwise), and the matrix must be diag(element +0x34, element +0x38) with no rotation word (draw_matrix_mismatch)."""
        nodes = _chain(r.kv["chain"]) if isinstance(r.kv.get("chain"), str) else []
        mw = [_s32(int(v, 16)) for v in r.kv["mw"].strip(",").split(",")] if isinstance(r.kv.get("mw"), str) else []
        out = {"node": r.kv.get("node"), "cell": r.kv.get("cell"), "flip": r.kv.get("flip"), "hflip": r.kv.get("hflip"),
               "attr": r.kv.get("attr"), "q12": None, "screen_q12": None, "scale_q12": None, "space": "unresolved", "target": None, "world_q8": None,
               "priority": _priority(r.kv)}
        if not nodes or nodes[0]["node"] != r.kv.get("el") or len(mw) < 6:
            missing.append({"track": name, "kind": "draw_uncomposed", "detail": "draw at gfc %d has no element chain or transform" % r.gfc})
            return out
        el, parents = nodes[0], nodes[1:]
        if any(n["block"] != IDENTITY_BLOCK for n in parents) or [sum(n["q12"][k] for n in nodes) for k in (0, 1)] != mw[4:6]:
            missing.append({"track": name, "kind": "draw_uncomposed",
                            "detail": "draw at gfc %d: translation %s is not the untransformed chain's sum" % (r.gfc, mw[4:6])})
            return out
        b = el["block"]
        if b is None or b[0] != 0 or mw[1] != 0 or mw[2] != 0 or [mw[0], mw[3]] != [b[1], b[2]]:
            missing.append({"track": name, "kind": "draw_matrix_mismatch",
                            "detail": "draw at gfc %d: matrix %s against element block %s" % (r.gfc, mw[:4], b)})
            return out
        d = {"age": s["age"], "gfc": r.gfc, "q12": el["q12"], "parent": parents[0]["node"] if parents else 0}
        d.update(space="unresolved", target=None, world_q8=None)
        # a draw runs after the update that the next dump reports: its chain is read against that dump's fighters
        self.resolve(d, parents, fighters, accepted, at=self._tick(r.gfc, r.line))
        out.update(q12=el["q12"], screen_q12=mw[4:6], scale_q12=[mw[0], mw[3]], space=d["space"], target=d["target"],
                   world_q8=d["world_q8"], moved=el["q12"] != s["q12"])
        if d["space"] == "unresolved":
            missing.append({"track": name, "kind": "unresolved_space", "detail": "rendered pose at gfc %d" % r.gfc})
        return out

    def track(self, t, entry, fighters, accepted, missing):
        name = "0x%06x#%d" % (t["id"], t["n"])
        reg = entry["anim"] if entry else None
        c = self.call(reg) if reg is not None else None
        if c is None:
            if reg is not None:
                missing.append({"track": name, "kind": "init_unpaired", "detail": "ANIM at log line %d has no paired initializer call" % (reg.line + 1)})
            return
        if not c["ok"]:
            missing.append({"track": name, "kind": "init_failed_registration",
                            "detail": "the call registered at gfc %d returned at 0x%08x without binding: no presentation" % (c["gfc"], c["ret_pc"] or 0)})
            return
        t["init"] = {"gfc": c["ret_gfc"], "ret_pc": c["ret_pc"]}
        p = self.pres.get(c["ret_line"])
        t["alloc"] = None if p is None or p["alloc"] is None else {"block": p["alloc"]["block"], "gen": p["alloc"]["gen"]}
        b = self.births.get(c["ret_line"] + 1)
        if b is not None:
            t["birth"]["init_return"] = {"el": b.kv.get("el"), "el_vtable": b.kv.get("elvt"),
                                         "chain": _chain(b.kv["chain"]) if isinstance(b.kv.get("chain"), str) else []}
        end_tick = t["end"]["gfc"] if t["end"] is not None and t["end"]["kind"] in ENDED else None
        last = end_tick - 1 if end_tick is not None else max(self.draws, default=t["birth_gfc"])
        drawn = {}
        for g in range(t["birth_gfc"], last + 1):
            for r in self.draws.get(g, []):
                if r.kv.get("owner") == t["obj"] and (g != t["birth_gfc"] or r.line > c["ret_line"]):
                    drawn.setdefault(g, r)
        ss = t["samples"]
        if ss and ss[0]["age"] != 0:
            g = t["birth_gfc"]
            if g in drawn:
                r = drawn[g]
                nodes = _chain(r.kv["chain"]) if isinstance(r.kv.get("chain"), str) else []
                if nodes and nodes[0]["node"] == r.kv.get("el"):
                    s0 = {"age": 0, "gfc": g, "state": None, "q12": nodes[0]["q12"], "parent": nodes[1]["node"] if len(nodes) > 1 else 0,
                          "par_q12": nodes[1]["q12"][:2] if len(nodes) > 1 else None, "phase": "draw",
                          "space": "unresolved", "target": None, "world_q8": None, "why": "no independent evidence resolves the space",
                          "chain": None}
                    self.resolve(s0, nodes[1:], fighters, accepted, at=self._tick(r.gfc, r.line))
                    ss.insert(0, s0)
                    t["birth"]["phase"] = "draw"
            else:
                passed = self.draws.get(g, [])
                nxt = [r for r in self.draws.get(g + 1, []) if r.kv.get("owner") == t["obj"]]
                if (passed and all(r.line < c["ret_line"] for r in passed) and ss[0]["age"] == 1 and nxt
                        and nxt[0].line > t["_rows"][0]):
                    t["birth"]["phase"] = "after_draw"
        for s in ss:
            r = drawn.get(s["gfc"])
            s["drawn"] = None if r is None else self.pose(r, s, fighters, accepted, name, missing)
        t["rendered"] = {"first_gfc": min(drawn, default=None), "last_gfc": max(drawn, default=None),
                         "live_undrawn_gfc": sorted({s["gfc"] for s in ss} - set(drawn))}
        ne = p["end"] if p is not None else None
        if ne is not None:
            tick = self._tick(ne["gfc"], ne["line"])
            want = "freed" if ne["kind"] == "freed" else "reinit"
            t["end_native"] = dict(ne, tick=tick)
            if want == "freed" and t["end"] is not None and t["end"]["kind"] == "reinit":
                # the dump calls a pointer registered again a reinit; natively the block was freed and its address re-initialized
                nxt = next((d for d in sorted(self.calls.values(), key=lambda d: d["line"])
                            if d["obj"] == t["obj"] and d["ok"] and d["line"] > ne["line"]), None)
                if nxt is not None and self._tick(nxt["gfc"], nxt["line"]) == tick:
                    want = "reinit"
                    t["end_native"]["successor"] = {"gfc": nxt["gfc"], "line": nxt["line"], "anim": nxt["anim"],
                                                    "tick": self._tick(nxt["gfc"], nxt["line"])}
            if t["end"] is None or t["end"]["kind"] != want or t["end"]["gfc"] != tick:
                missing.append({"track": name, "kind": "end_mismatch",
                                "detail": "native %s at gfc %d (dump tick %d), dump observed %s" % (ne["kind"], ne["gfc"], tick, t["end"])})
        elif t["end"] is not None and t["end"]["kind"] in ENDED:
            missing.append({"track": name, "kind": "end_unrecorded",
                            "detail": "the dump observed %s at gfc %d with no recorded free or successful initialization" % (t["end"]["kind"], t["end"]["gfc"])})


def _priority(kv):
    """The draw-order and depth facts an LDX row read (fxo_lifecycle LDX stop): the node's sort key (+0x06, larger draws first in the
    manager's list), the manager (+0x34), the manager's Z slot counter (+0x4BC) and the polygon alpha. None when the row predates them."""
    if "key" not in kv:
        return None
    return {"key": kv["key"], "mgr": kv.get("mgr"), "zslot": kv.get("zslot"), "alpha": kv.get("alpha")}


def _positioned_birth(t, fxs):
    """(x_q12, y_q12) when a positioned fx_spawn at the birth tick equals the age-0 element position; zero coordinates never count."""
    if not t["samples"] or t["samples"][0]["age"] != 0:
        return None
    x, y = t["samples"][0]["q12"][:2]
    hits = [(r1, r2) for rid, r1, r2 in fxs.get(t["birth_gfc"], []) if rid == t["id"] and (r1, r2) != (0, 0) and (x >> 12, y >> 12) == (r1, r2)]
    return (x, y) if len(hits) == 1 else None


def _resolve(s, chain, fighters, world_objects, facing, pos_anchor):
    gfc, (x, y, _z) = s["gfc"], s["q12"]
    s.update(space="unresolved", target=None, world_q8=None, why=None)
    s["chain"] = chain
    if chain and "body_q12" in chain and s["parent"] == 0:
        bx, by = chain["body_q12"][0] >> 4, chain["body_q12"][1] >> 4
        cands = [lab for lab, pos in fighters.items() if tuple(pos.get(gfc, ())) == (bx, by)]
        if len(cands) == 1:
            fx, fy = fighters[cands[0]][gfc]
            if (x, y) == (0, 0):
                s.update(space="follow_fighter", target=cands[0], world_q8=[fx, fy])
                return
            f = facing.get(gfc)
            if f is None:
                s.update(why="transform_unmeasured")
                return
            sign = -1 if f == 1 else 1
            s.update(space="follow_fighter", target=cands[0], world_q8=[fx + sign * (x >> 4), fy + (y >> 4)])
            return
    cands = [lab for lab, m in world_objects.items() if tuple(m.get(gfc, ())) == (x, y)]
    if len(cands) == 1:
        s.update(space="world", target=cands[0], world_q8=[x >> 4, y >> 4])
        return
    if pos_anchor is not None and (x, y) == pos_anchor:
        s.update(space="world", target="fxs", world_q8=[x >> 4, y >> 4])
        return
    s["why"] = "no independent evidence resolves the space" if not chain or "body_q12" not in chain else "chain body is no known fighter"


def _judge_track(t, expect_targets, life, missing):
    name = "%s#%d" % (t["id_hex"], t["n"])
    ss = t["samples"]
    if t["identity"]:
        missing.append({"track": name, "kind": "identity_mismatch",
                        "detail": "rows of index %d carry another object/id/age at gfc %s" % (t["n"], [c["gfc"] for c in t["identity"]][:8])})
    if not t["registered"]:
        missing.append({"track": name, "kind": "no_registration",
                        "detail": "no ANIM registers object 0x%x id 0x%x at its birth %d" % (t["obj"], t["id"], t["birth_gfc"])})
    if t["clock"]:
        missing.append({"track": name, "kind": "clock_mismatch",
                        "detail": "sample gfc != birth %d + age at ages %s" % (t["birth_gfc"], [c["age"] for c in t["clock"]][:8])})
    if t["age_order"]:
        missing.append({"track": name, "kind": "age_order", "detail": "ages not strictly increasing at %s" % t["age_order"][:8]})
    if t["early"]:
        missing.append({"track": name, "kind": "sample_before_registration",
                        "detail": "rows at gfc %s precede the registration (first tick %d)" % (t["early"][:8], t["first_tick"])})
    if not ss:
        missing.append({"track": name, "kind": "no_live_sample", "detail": "no live FXO sample between the birth and %s" % (t["end"] or "the log end")})
        return
    if ss[0]["age"] != 0 and t.get("birth", {}).get("phase") != "after_draw":
        missing.append({"track": name, "kind": "no_birth_sample", "detail": "first sample at age %d" % ss[0]["age"]})
    # the live interval is [first age, terminal age): a recorded free or reinit at age E means the object was live through E-1
    last = t["end"]["age"] - 1 if t["end"] is not None else ss[-1]["age"]
    have = {s["age"] for s in ss}
    gap = sorted(set(range(ss[0]["age"], last + 1)) - have)
    if gap:
        missing.append({"track": name, "kind": "gap", "detail": "ages %s" % gap})
    bad = [s["age"] for s in ss if s["space"] == "unresolved" and s["why"] != "transform_unmeasured"]
    if bad:
        missing.append({"track": name, "kind": "unresolved_space", "detail": "ages %s" % bad[:8]})
    tr = [s["age"] for s in ss if s["why"] == "transform_unmeasured"]
    if tr:
        missing.append({"track": name, "kind": "transform_unmeasured", "detail": "facing missing for ages %s" % tr[:8]})
    want = expect_targets.get(t["id"])
    if want is not None and any(s["target"] != want for s in ss if s["space"] != "unresolved"):
        missing.append({"track": name, "kind": "wrong_follow_target", "detail": "expected %s, saw %s" % (want, sorted({s["target"] for s in ss}))})
    if t["end"] is None:
        t["end"] = {"kind": "log_end", "age": ss[-1]["age"]}
        if life is not None and ss[-1]["age"] >= life:
            t["end"]["kind"] = "window"
            missing.append({"track": name, "kind": "short_window", "detail": "still live at age %d, window %d" % (ss[-1]["age"], life)})
        else:
            missing.append({"track": name, "kind": "incomplete_window",
                            "detail": "no recorded free or reinit after age %d: the interval to the object's end is not evidenced" % ss[-1]["age"]})


def frame_birth(t):
    """A track's birth on the dump clock, which is W3's frame-end clock: its first tick. birth_gfc is the counter the
    initializer read. The counter increments inside a frame, after the fighters' update and before the dump, so an ANIM
    printed after its tick's dump (a move's first-frame effect, GN01 lr 0x0201630C on the move's own anim-set path) reads
    one less than the frame it is born in; an ANIM before the dump has first_tick == birth_gfc. A sample before the first
    tick (the lifecycle layer's draw-phase age-0 sample) has no proven frame and is refused.
    Evidence: docs/research/feel-captures/2026-10-30-fxo-birth-tick."""
    first = t["first_tick"]
    early = [s["gfc"] for s in t["samples"] if s["gfc"] < first]
    if early:
        raise ValueError("%s: sample at gfc %d precedes the dump tick %d of its registration" % (t["id_hex"], early[0], first))
    return first


def normalize(reduced, anchor_gfc):
    """The comparison form: per (id, ordinal) the birth tick relative to the anchor, the world Q8 place of every age and the end kind.
    Birth and ages are on the dump clock (frame_birth), the clock of the anchor."""
    seen, out = {}, []
    for t in sorted(reduced["tracks"], key=lambda t: (t["id"], t["birth_gfc"])):
        k = seen[t["id"]] = seen.get(t["id"], -1) + 1
        birth = frame_birth(t)
        out.append({"id": t["id_hex"], "ordinal": k, "birth_tick": birth - anchor_gfc,
                    "places": {str(s["gfc"] - birth): s["world_q8"] for s in t["samples"]}, "end": (t["end"] or {}).get("kind")})
    return out


def diff(a, b):
    """Differences between two normalized reductions (a = reference, b = candidate): birth tick, end kind (freed/reinit/...) and the
    first differing place; empty when they agree exactly."""
    ia, ib = {(t["id"], t["ordinal"]): t for t in a}, {(t["id"], t["ordinal"]): t for t in b}
    out = []
    for k in sorted(set(ia) | set(ib)):
        if k not in ib:
            out.append("%s#%d: track missing from the candidate" % k)
        elif k not in ia:
            out.append("%s#%d: extra track in the candidate" % k)
        else:
            x, y = ia[k], ib[k]
            if x["birth_tick"] != y["birth_tick"]:
                out.append("%s#%d: birth_tick %d != %d" % (k + (x["birth_tick"], y["birth_tick"])))
            if x["end"] != y["end"]:
                out.append("%s#%d: end %s != %s" % (k + (x["end"], y["end"])))
            for age in sorted(set(x["places"]) | set(y["places"]), key=int):
                if x["places"].get(age) != y["places"].get(age):
                    out.append("%s#%d: place@age %s %s != %s" % (k + (age, x["places"].get(age), y["places"].get(age))))
                    break
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("banks", nargs="+", help="LO HI [EXTRA ...] in hex")
    g.add_argument("--life", type=int, default=DEFAULT_LIFE)
    g.add_argument("--capacity", type=int, default=DEFAULT_CAPACITY)
    g.add_argument("--out", type=Path)
    r = sub.add_parser("reduce")
    r.add_argument("log", type=Path)
    r.add_argument("--anchor", type=int)
    r.add_argument("--required", type=int)
    r.add_argument("--life", type=int)
    r.add_argument("--banks", nargs="*", help="the probe's tracked banks (id >> 8, hex): proof input, the registrations the table takes and "
                   "the cross-check that every entry they append has an FXO stream. Without it the banks are inferred for inspection only "
                   "(never ok, no carried proof)")
    r.add_argument("--legacy", action="store_true", help="admit FXO rows without FXPOS (pre-generator logs); never certifies placement, never ok")
    r.add_argument("--baseline", type=Path, help="the JSON result of the previous window's reduce (its `carried` proof accounts the "
                   "indices it ended); chain windows by passing each result to the next")
    sub.add_parser("pins")
    a = p.parse_args(argv)
    if a.cmd == "generate":
        banks = [int(x, 16) for x in a.banks]
        text = generate(banks[0], banks[1], banks[2:], life=a.life, capacity=a.capacity)
        (a.out.write_text(text) if a.out else sys.stdout.write(text))
        return 0
    if a.cmd == "pins":
        print(json.dumps({"7c1+2200": hashlib.sha256(generate(0x7C1, 0x7C1, [0x2200]).encode()).hexdigest()}, indent=1))
        return 0
    import gzip
    op = gzip.open if str(a.log).endswith(".gz") else open
    with op(a.log, "rt", errors="replace") as fh:
        red = reduce(fh.read().splitlines(), anchor_gfc=a.anchor, required_ticks=a.required, life=a.life,
                     banks=[int(b, 16) for b in a.banks] if a.banks is not None else None, legacy=a.legacy,
                     baseline=json.loads(a.baseline.read_text()) if a.baseline else None)
    json.dump({k: v for k, v in red.items() if k != "tracks"} | {"tracks": len(red["tracks"])}, sys.stdout, indent=1)
    return 0 if red["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
