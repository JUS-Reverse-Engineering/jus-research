"""scripts/kit/feature_status.py -- static feature coverage of the kit exporter.

`FEATURE_STATUS` classifies every key of docs/rebuild/feature-census.json
(scripts/analysis/feature_census.py): handled, partial, out_of_band, unsupported or split, with a
reason that cites the exporter code path or says why the feature is unsupported.
`static_rows` walks one exported move's static anim closure in that census and returns an
`unsupported[]` row for each feature the kit does not carry.
export_kit.py calls `static_rows` from `_unsupported_static`; a census key missing here raises
`UnclassifiedFeature`, which the exporter turns into a refusal.
"""

from __future__ import annotations

from typing import NamedTuple, Optional


class UnclassifiedFeature(ValueError):
    """A census key FEATURE_STATUS does not know."""


def norm_anim(a) -> Optional[str]:
    """'0x1e' / '1e' / 30-as-hex-string -> '0x1e'; None when it is no hex number."""
    try:
        return f"0x{int(str(a), 16):02x}"
    except ValueError:
        return None


#
# The exporter is claim-driven: boxes, shots, motion and idle come from capture claims and the
# decoded tables. It never walked the static anim closure of a move, so JUS kit features it does
# not model were dropped without a trace. FEATURE_STATUS
# classifies every feature key of docs/rebuild/feature-census.json
# (scripts/analysis/feature_census.py); test_export_coverage.py fails on a key it lacks.
# `static_rows` walks a move's closure in that census and writes one `unsupported[]` row per
# feature the kit does not carry.

FEATURE_CENSUS = "docs/rebuild/feature-census.json"
STATIC_WHAT = "static feature not exported"
FEATURE_STATUSES = ("handled", "partial", "out_of_band", "unsupported", "split")
SHARED_ART_BANKS = (0x21, 0x22, 0x23, 0x24)    # comm_a..comm_g effect ids: the art low byte is no anim there
NOTE_LOCS = 3                                   # locations named per row


class Feature(NamedTuple):
    """One census key's status.
      handled      the exporter writes it; `why` names the code path.
      partial      written only in some cases; `covered_by` (COVERED_BY) says when the kit has it, and
                   the key writes a row when the move does not.
      out_of_band  FX/SFX: not modelled by the exporter; vfx-sfx.json and anim-timing carry them.
      unsupported  not exported; `why` says what is lost. Always written as a row.
      split        a parent key fully described by its `.variant` keys; writes nothing itself."""
    status: str
    why: str
    covered_by: str = ""


def _handled(why):
    return Feature("handled", why)


def _partial(why, covered_by):
    return Feature("partial", why, covered_by)


def _oob(why):
    return Feature("out_of_band", why)


def _unsup(why):
    return Feature("unsupported", why)


def _split(why):
    return Feature("split", why)


_FX = "not modelled downstream (docs/rebuild/vfx-sfx.json, anim-timing carry it)"
_FX_GEN = "not modelled downstream (docs/rebuild/vfx-sfx.json, anim-timing carry it)"
_SFX = "not modelled downstream (docs/rebuild/vfx-sfx.json carries it)"
_MASK = ("propMask bit sets element flag-table words (knockback_table.py code_facts flag tables at "
         "0x0209FD44); the record carries it only inside prop_mask, with no named field")
_NOPATH = "no exporter path reads it"
_SHOT_PLAIN = ("kind 0 family (aliases of handler 0x0216EEF4, docs/research/findings/entity-kind-table-static.md): "
               "the kit's shot is capture-timed (_plan_shots/_emit_shots)")
_SHOT_KIND = ("shot kind other than the plain kind-0 family: the kit's capture-timed shot (_plan_shots) records "
              "only the behaviour seen in the capture, not this kind's handler")

FEATURE_STATUS: dict = {
    # --- effect nodes (anim_events.py) ---
    "gn.GN01": _oob(_FX),
    "gn.GN02": _oob(_FX),
    "gn.GN03": _oob(_FX),
    "gn.GN04": _oob(_FX),
    # --- NoteTrack op 0: waits and branches (mash_table.py decode_event; handlers in ov6) ---
    "op0.sub0": _partial("count_loop: _row_events sub 0 writes a mash count_loop event on an attached row",
                   "mash:count_loop"),
    "op0.sub1": _split("hold_release / hold_tiers / disarm variants"),
    "op0.sub1.hold_release": _partial("_row_events sub 1 writes a mash hold_release event", "mash:hold_release"),
    "op0.sub1.hold_release.null_marker": _unsup("hold_release whose default marker has no frame: _row_events "
                                            "returns None and the whole mash is dropped"),
    "op0.sub1.hold_release_disarm": _unsup("marker 0xFFFF disarms slot 5 natively; mash_table.decode_event reads it as "
                                       "a hold_release with a null marker, so _row_events drops the whole mash "
                                       "(exporter-silent-drops.md section 3; decoder fix pending)"),
    "op0.sub1.hold_tiers": _partial("_row_events sub 1 hold tiers write mash.hold_tiers", "mash:hold_tiers"),
    "op0.sub2": _partial("loop: _row_events sub 2 writes a mash loop event on a mash row; otherwise the capture "
                   "replays the loop in elapsed time (boxes and idle_return come from claims)", "loop"),
    "op0.sub2.null_marker": _unsup("loop whose marker has no frame: _row_events skips it"),
    "op0.sub3": _split("arm / disarm variants"),
    "op0.sub3.arm": _partial("ground_wait: _row_events sub 3 writes a mash ground_wait event on an attached row",
                       "mash:ground_wait"),
    "op0.sub3.disarm": _partial("ground_wait disarm: _row_events sub 3 writes a ground_wait event with to = null",
                          "mash:ground_wait"),
    "op0.sub4": _split("arm / disarm variants"),
    "op0.sub4.arm": _unsup("air_wait: _row_events has no sub 4 branch; ATTACH_SUBS omits it"),
    "op0.sub4.disarm": _unsup("air_wait disarm: _row_events has no sub 4 branch"),
    "op0.sub5": _split("arm / disarm variants"),
    # Legacy unsupported wording applies to captures without a proven projected contact path.
    # Kenshin 5k X's root f8/f51 pair is handled in static_rows below; other kit bytes stay pinned.
    "op0.sub5.arm": _unsup("contact_wait: the simulator follows the whiff timeline; native contact-triggered jumps are not modeled"),
    "op0.sub5.disarm": _unsup("contact_wait disarm: not attached (see op0.sub5.arm)"),
    "op0.sub6": _unsup("wait kind 0: handler not decoded for the kit; " + _NOPATH),
    "op0.sub7": _unsup("undecoded op 0 sub; " + _NOPATH),
    "op0.sub8": _unsup("victim contact branch; " + _NOPATH),
    "op0.sub9": _partial("counter_wait: _row_counter_waits writes the resolved arm and disarm waits as "
                         "mash.counter_wait (STATIC decode; a Marker absent from the anim is a native no-op "
                         "and writes nothing, so that occurrence keeps its row)", "mash:counter_wait"),
    "op0.sub10": _unsup("wall_wait; " + _NOPATH),
    "op0.sub12": _unsup("undecoded op 0 sub; " + _NOPATH),
    "op0.sub14": _partial("deck-count branch: only a manifest [[export.sets.deck_tiers]] row (_deck_tiers) writes it, as "
                    "on_hit_levels; a mash row with sub 14 is refused (_row_events 'mash deck-count branch')",
                    "levels"),
    "op0.sub15": _unsup("held-shot contact branch (0x02155FF0); " + _NOPATH),
    "op0.sub16": _unsup("random branch (0x021560B0); " + _NOPATH),
    "op0.sub18": _partial("two_way: _row_events sub 18 writes a mash two_way event", "mash:two_way"),
    "op0.sub19": _partial("store: _row_events sub 19 writes a mash store event", "mash:store"),
    "op0.sub20": _partial("stored_jump: _row_events sub 20 writes a mash stored_jump event", "mash:stored_jump"),
    "op0.sub22": _unsup("undecoded op 0 sub; " + _NOPATH),
    "op0.sub23": _unsup("direction branch; " + _NOPATH),
    "op0.sub24": _unsup("undecoded op 0 sub; " + _NOPATH),
    "op0.sub26": _unsup("hit-confirm wait (0x02155D64); " + _NOPATH),
    "op0.sub27": _unsup("undecoded op 0 sub; " + _NOPATH),
    "op0.sub28": _unsup("undecoded op 0 sub; " + _NOPATH),
    # --- NoteTrack op 1 (motion), op 2, op 4 ---
    **{f"op1.sub{n}": _partial("motion: the kit takes motion from capture claims (_motion writes all-zero segments only) "
                         "and grades anything else TBD (_build_move motion); the static op 1 event is not read"
                         + ("; the UA impulse alone is read (_ua_accel)" if n == 3 else ""), "motion")
       for n in (0, 1, 2, 3, 4)},
    "op1.sub5": _unsup("op 1 sub 5 flags; " + _NOPATH),
    "op1.sub6": _unsup("op 1 sub 6 flags; " + _NOPATH),
    "op2.sub0": _unsup("undecoded op 2 sub; " + _NOPATH),
    "op2.sub1": _unsup("undecoded op 2 sub; " + _NOPATH),
    "op4.sub0": _oob(_SFX),
    "op4.sub1": _oob(_SFX),
    "op4.sub2": _oob(_SFX),
    # --- NoteTrack op 3 sub 0 by arg (ua_table.decode_op3) and other op 3 subs ---
    "op3.arg1": _partial("cancel key: _build_move writes cancel from the CT row (ct_cancel)", "cancel"),
    "op3.arg2": _partial("spawn row: shots come from capture claims (_plan_shots/_emit_shots); the static row is not "
                   "reconciled with them", "shots"),
    "op3.arg3": _unsup("release held shots; " + _NOPATH),
    # arg 4/5 FX node toggles: vfx_sfx_build.py emits GN spawns and sounds only, never NoteTrack op 3
    "op3.arg4": _unsup("FX node toggle; no owner path carries it (vfx_sfx_build.py reads GN spawns and sounds, "
                       "not op 3)"),
    "op3.arg5": _unsup("FX node toggle; no owner path carries it (vfx_sfx_build.py reads GN spawns and sounds, "
                       "not op 3)"),
    "op3.arg6": _unsup("undecoded op 3 arg; " + _NOPATH),
    "op3.arg7": _unsup("invuln: the kit has an invuln effect kind but _ua_effects never writes it (warned 'phase 2')"),
    "op3.arg8": _unsup("undecoded op 3 arg; " + _NOPATH),
    "op3.arg9": _partial("arm_substitute: _ua_effects writes it for the ULTIMATE move only", "effect:arm_substitute"),
    "op3.arg10": _partial("status: _status_effects writes self-status events from ua-table status_effects",
                    "effect:status"),
    **{f"op3.arg{n}": _unsup("undecoded op 3 arg; " + _NOPATH) for n in (11, 12, 13, 14, 17, 18, 19, 21, 25, 26, 29, 33)},
    "op3.arg22": _unsup("fighter steer; " + _NOPATH),
    "op3.arg23": _unsup("hp: the kit has an hp effect kind but _ua_effects never writes it (warned 'phase 2')"),
    "op3.arg24": _partial("sp: _ua_effects writes it for the ULTIMATE move only", "effect:sp"),
    "op3.arg32": _unsup("team heal; " + _NOPATH),
    "op3.sub1": _partial("end key: mash rows carry it as mash.ends (_mash_info); a plain move's end comes from the "
                   "capture's idle_return", "idle_return"),
    "op3.sub2": _unsup("body flag 0x20000000; only a manifest [[export.unsupported]] row names it"),
    # --- 20-byte KB records (move_records.FIELDS, knockback_table.record_row) ---
    **{f"rec.type.{n}": _handled("type, damage, kb and hitstun columns: _record_entry") for n in range(15)},
    # Keep the legacy census keys and unsupported membership; only this reader is decoded.
    **{f"rec.kind.{n}": _unsup("record byte 0 is the record priority (counter pair gate 0x0207FC9C); other readers not decoded") for n in range(6)},
    "rec.statusRaw.nonzero": _handled("_record_entry writes status_raw and status_id"),
    "rec.byte2.nonzero": _unsup("unattributed record byte 2, carried as the record's byte2; no reader is identified"),
    "rec.byte16.nonzero": _unsup("hit-effect call argument (ov6 0x02153CE8), carried as the record's byte16; "
                                 "vfx_sfx_build.py reads hitEffect and onomatopoeia only, so no downstream path draws it"),
    "rec.byte17.nonzero": _unsup("hit-effect call argument (ov6 0x02153CE8), carried as the record's byte17; "
                                 "vfx_sfx_build.py reads hitEffect and onomatopoeia only, so no downstream path draws it"),
    "rec.hitEffect.nonzero": _oob("hit spark and sound index, carried as the record's hit_effect: " + _FX_GEN),
    "rec.onomatopoeia.nonzero": _oob("hit text index, carried as the record's onomatopoeia: " + _FX_GEN),
    "rec.shakeScale.nonzero": _unsup("SP drained per contact from the struck team's pool (arm9 0x020812A0, "
                                     "ov6 0x0215AC5C), carried as the record's sp_drain; not modelled downstream"),
    "rec.mask.bit1": _handled("_record_entry writes counter_pair; node words from collision-node-flags.json; closure debt REC_MASK_NODE_WORD_READER_CLOSURE_OPEN"),
    "rec.mask.bit17": _handled("_record_entry writes forced_switch; node words from collision-node-flags.json; closure debt REC_MASK_NODE_WORD_READER_CLOSURE_OPEN"),
    "rec.mask.bit0": _handled("override bit: _record_entry writes through_guard and kb_override"),
    "rec.mask.bit9": _handled("KB relative-sign bit: _record_entry writes kb_relative when the table row's sign is relative"),
    "rec.mask.bit10": _handled("nature slot B: _nature_slot_of (SLOT_MASK_BITS); node 0x40 also selects accumulation bank 8 (0x02081A8C); neutral to combat totals per the bit11 note"),
    "rec.mask.bit11": _handled("nature slot C: _nature_slot_of (SLOT_MASK_BITS); routes HP/SP to bank8+owner index "
        "(0x02081A8C; table0x0209FF34). Owner word chooses slots16 (0x2600) and17 (empty byte) "
        "before node flags (0x02081A5C..74), so bit11 cannot reach them. Reducer0x020821C4..0x02082210 "
        "sums0..16 and excludes17 for every record. Readers/clears0..16 are uniform "
        "(docs/research/static/2026-11-05-kenshin-k7a/e/step0-banks.json reader_clear_listing), "
        "so bank choice is neutral to combat totals. Received flag increments match statistic0x19 "
        "(0x0215AF24 ->0x0215AED0), not a combat resource; closure debt REC_MASK_NODE_WORD_READER_CLOSURE_OPEN"),
    "rec.mask.bit12": _handled("zero bit: _record_entry writes kb_zero and the victim-hold unsupported row"),
    **{f"rec.mask.bit{n}": _unsup(_MASK) for n in (2, 3, 5, 6, 7, 13, 14, 15, 16, 18, 19, 20, 21, 22, 23)},
    # --- shot rows (chr/shot/<prefix>.bin, 32 bytes; ua_table.shot_rows) ---
    **{f"shot.kind.0x{n:02x}": _partial(_SHOT_PLAIN, "shots") for n in (0x00, 0x0f, 0x15, 0x16)},
    "shot.kind.0x0d": _unsup("held summon (position tracker): " + _SHOT_KIND),
    "shot.kind.0x06": _unsup("homing: " + _SHOT_KIND),
    "shot.kind.0x11": _unsup("steered: " + _SHOT_KIND),
    "shot.kind.0x13": _unsup("steered: " + _SHOT_KIND),
    "shot.kind.0x12": _unsup("kind 0x12 (extends the kind-6 handler): " + _SHOT_KIND),
    "shot.kind.0x0b": _unsup("aimed (kind 0x0B precomputes an aim vector): " + _SHOT_KIND),
    **{f"shot.kind.0x{n:02x}": _unsup(_SHOT_KIND)
       for n in (0x01, 0x05, 0x07, 0x09, 0x0a, 0x0c, 0x10, 0x14, 0x17, 0x19)},
    "shot.b1.nonzero": _unsup("unattributed shot byte 1; " + _NOPATH),
    "shot.b28.nonzero": _unsup("successor shot row on end (flag 0x40); " + _NOPATH),
    "shot.b29.nonzero": _unsup("successor row on contact, body flag or landing, or a random-offset size (flags 0x80, "
                           "0x40000, 0x100000, 0x4000, 0x80000); " + _NOPATH),
    "shot.b30.nonzero": _unsup("unattributed shot byte 30; " + _NOPATH),
    "shot.bytes16_27.nonzero": _unsup("unattributed shot bytes 16-27; " + _NOPATH),
    **{f"shot.flag.0x{f:x}": _unsup(why + "; the capture-timed shot keeps only the observed behaviour") for f, why in {
        0x40: "successor row on end, from +28", 0x80: "successor row on contact, from +29",
        0x40000: "successor row on the body flag, from +29", 0x100000: "successor row when grounded, from +29",
        0x4000: "random x offset of +-(+29) px per spawn", 0x80000: "random y offset of +-(+29) px per spawn",
        0x8000: "floor snap (inferred meaning)", 0x400: "terrain follow (inferred meaning)"}.items()},
    **{f"shot.flag.0x{f:x}": _unsup("shot flag not decoded; " + _NOPATH)
       for f in (0x1, 0x4, 0x8, 0x10, 0x20, 0x200, 0x800, 0x1000, 0x2000, 0x10000, 0x20000, 0x200000, 0x400000)},
}


class Occ(NamedTuple):
    """One occurrence of a feature key in a move's closure: where it sits and what it names."""
    key: str
    loc: str                 # census anim key "<member>#<anim>", or the shot row's owner member
    frame: int = -1          # NoteTrack/GN frame; -1 for a node or a non-frame occurrence
    row: Optional[str] = None    # shot row index for a shot-row key
    rec: Optional[int] = None    # record id for a record key
    nth: int = 0             # ordinal among the spawn events of the same anim and frame
    via: Optional[str] = None    # a shot-row occurrence: the anim whose spawn event names the row (None: a successor)


class _View(NamedTuple):
    move: dict
    shots: list
    root: str                # the census loc of the move's own anim
    joined: frozenset        # (frame, nth) of the root anim's spawn events a kit shot is joined to


def _at_root(v, o) -> bool:
    return o.loc == v.root


def _event_at(events, o, frame_key="frame") -> bool:
    return any(e.get(frame_key) == o.frame for e in events)


# name -> predicate(view, arg, occurrence); `covered_by` is "name" or "name:arg". Every predicate
# matches the occurrence's own anim and frame (or shot row), never the move as a whole: an event of a
# child anim (a spawned summon) is the kit's only when the kit names that child, and the kit's
# events, effects and shots belong to the move's own anim.
COVERED_BY: dict = {
    "mash": lambda v, kind, o: _at_root(v, o) and (
        _event_at((v.move.get("mash") or {}).get("hold_tiers", []), o, "poll_frame") if kind == "hold_tiers"
        else _event_at((v.move.get("mash") or {}).get("counter_wait", []), o) if kind == "counter_wait"
        else _event_at([e for e in (v.move.get("mash") or {}).get("events", []) if e.get("kind") == kind], o)),
    "effect": lambda v, kind, o: _at_root(v, o) and _event_at(
        [e for e in v.move.get("effects", []) if e.get("kind") == kind], o),
    "loop": lambda v, _a, o: _at_root(v, o) and (bool(v.move.get("boxes")) or COVERED_BY["mash"](v, "loop", o)),
    "motion": lambda v, _a, o: _at_root(v, o) and "motion" in v.move,     # a value or a TBD-graded leaf
    "cancel": lambda v, _a, o: _at_root(v, o) and (v.move.get("cancel") is not None
                                                   or v.move.get("slot") == "ULTIMATE"),
    # a kit shot stands for the root anim's spawn event it is joined to (_join_shots), and for the shot
    # row that event names; successor rows and the spawns of a child anim are never covered
    "shots": lambda v, _a, o: ((o.via == v.root if o.row is not None else _at_root(v, o))
                               and (o.frame, o.nth) in v.joined),
    "levels": lambda v, _a, o: _at_root(v, o) and bool(v.move.get("on_hit_levels")),
    "idle_return": lambda v, _a, o: _at_root(v, o) and (
        v.move.get("idle_return") is not None or bool((v.move.get("mash") or {}).get("ends"))),
}


def _is_covered(feature: Feature, view, occ: Occ) -> bool:
    name, _, arg = feature.covered_by.partition(":")
    return COVERED_BY[name](view, arg, occ)


def kit_records(move: dict, set_records: Optional[list] = None) -> set:
    """Record ids the kit carries for a move: its own, its contact levels' and, for a special-set move,
    the set's (the set's shots point there)."""
    recs = {r["rec"] for r in move.get("records", [])}
    for level in move.get("on_hit_levels", []):
        recs |= {r["rec"] for r in level.get("records", [])}
    return recs | {r["rec"] for r in (set_records or [])}


def dedupe_rows(rows: list) -> list:
    seen, out = set(), []
    for r in rows:
        k = (r["slot"], r["what"], r["note"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def _anim_loc(char: dict, member: str, anim: str) -> Optional[str]:
    """The census anim key for `anim`: the requested member when it holds the anim, else the base member."""
    for m in (member, char["prefix"]):
        loc = f"{m}#{anim}"
        if loc in char["anims"]:
            return loc
    return None


def _spawn_events(char: dict, loc: str) -> list:
    """(frame, row, nth) per spawn event of an anim; nth numbers the events of one frame."""
    seen: dict = {}
    out = []
    for frame, row in char["anims"][loc]["spawns"]:
        out.append((frame, str(row), seen.get(frame, 0)))
        seen[frame] = seen.get(frame, 0) + 1
    return out


def _closure(char: dict, member: str, anim: str) -> tuple:
    """(anim locs, shot rows, edges) reachable from one anim: op 3 arg 2 spawn rows, each row's art anim
    (low byte, unless the art is a shared effect bank) and the successor rows its flags select (+28 on 0x40,
    +29 on 0x80 / 0x40000 / 0x100000). `member` is the requested resource context (the base prefix, or a
    koma member): the root anim may fall back to the base archive, but every descendant is looked up in
    `member` first, so a base-archive root keeps its koma children. Rows are expanded once, but every
    reference to one is an edge `(row, via, frame, nth)`: `via` is the anim whose spawn event names the row,
    or None for a successor reference. INFERRED: the art-low-byte join (ua_table.kb_recs_for_art, review c4)."""
    locs, rows, edges, todo = [], [], [], []
    start = _anim_loc(char, member, anim)
    if start is not None:
        todo.append(("anim", start))
    seen = set()
    while todo:
        kind, ref = todo.pop(0)
        if (kind, ref) in seen:
            continue
        seen.add((kind, ref))
        if kind == "anim":
            locs.append(ref)
            for frame, row, nth in _spawn_events(char, ref):
                edges.append((row, ref, frame, nth))
                todo.append(("shot", row))
            continue
        shot = char["shots"].get(ref)
        if shot is None:
            continue
        rows.append(ref)
        art = int(shot["art"], 16)
        if art >> 16 not in SHARED_ART_BANKS:
            loc = _anim_loc(char, member, f"0x{art & 0xFF:02x}")
            if loc is not None:
                todo.append(("anim", loc))
        flags = shot["flags"]
        for bit, field in ((0x40, "b28"), (0x80 | 0x40000 | 0x100000, "b29")):
            if flags & bit and shot[field]:
                edges.append((str(shot[field]), None, -1, 0))
                todo.append(("shot", str(shot[field])))
    return locs, rows, edges


def _feature(key: str) -> Feature:
    f = FEATURE_STATUS.get(key)
    if f is None:
        raise UnclassifiedFeature(f"feature key {key!r} is in {FEATURE_CENSUS} but not in FEATURE_STATUS; "
                                  "classify it (scripts/kit/feature_status.py) before exporting")
    return f


def _where(places: list) -> str:
    shown = ", ".join(places[:NOTE_LOCS])
    return shown + (f", +{len(places) - NOTE_LOCS} more" if len(places) > NOTE_LOCS else "")


def _places(occs: list) -> list:
    """Occurrences as note locations: one `<loc> f<frames>` per anim, `shot row` / `rec` entries as is."""
    out, frames = [], {}
    for o in occs:
        if o.row is not None:
            out.append(f"shot row {o.row}")
        elif o.rec is not None:
            out.append(f"rec {o.rec}")
        else:
            if o.loc not in frames:
                frames[o.loc] = []
                out.append(o.loc)
            frames[o.loc].append(o.frame)
    res = []
    for p in out:
        if p in frames:
            fs = frames[p]
            res.append(f"{p} " + (",".join(f"f{f}" for f in fs[:4]) if fs[0] >= 0 else "node"))
        else:
            res.append(p)
    return list(dict.fromkeys(res))


def _join_shots(char: dict, root: str, shots: list) -> frozenset:
    """(frame, nth) of the root anim's spawn events that kit shots are joined to. The kit's only join key
    is the shot's `tick` against the spawn frame (a kit shot carries no census row or anim). A frame with
    at least as many shots as events joins them all; with fewer shots it joins that many events only when
    the events are identical (the same row), since any of them is then the one the shot stands for; with
    differing events it is ambiguous and joins none."""
    native = []
    legacy = []
    for shot in shots:
        (native if isinstance(shot.get("spawn"), dict) else legacy).append(shot)
    joined = set()
    member, anim = root.rsplit("#", 1)
    normalize_member = lambda value: value.removeprefix("chr/").removesuffix(".aar")
    for frame, row, nth in _spawn_events(char, root):
        for shot in native:
            spawn = shot["spawn"]
            if (spawn.get("root_anim") == int(anim, 16)
                    and normalize_member(spawn.get("root_member", "")) == normalize_member(member)
                    and spawn.get("authored_frame") == frame
                    and str(shot.get("row")) == row and spawn.get("occurrence") == nth):
                joined.add((frame, nth))
    shots = legacy
    ticks: dict = {}
    for shot in shots:
        t = shot.get("tick")
        if isinstance(t, int) and not isinstance(t, bool):
            ticks[t] = ticks.get(t, 0) + 1
    by_frame: dict = {}
    for frame, row, nth in _spawn_events(char, root):
        by_frame.setdefault(frame, []).append((row, nth))
    for frame, events in by_frame.items():
        k = ticks.get(frame, 0)
        if k >= len(events) or (k and len({r for r, _n in events}) == 1):
            joined |= {(frame, n) for _r, n in events[:k]}
    return frozenset(joined)


def native_shot_feature(shot, key):
    """A handled reading for one verified native kind/flag occurrence only."""
    if not isinstance(shot.get("spawn"), dict):
        return None
    kind, flags = shot.get("kind"), shot.get("flags")
    allowed = 1 if kind == 0 else 0x400 if kind == 7 else 0
    if kind not in (0, 7) or not isinstance(flags, int) or isinstance(flags, bool) or flags < 0 or flags & ~allowed:
        return None
    notes = {
        f"shot.kind.0x{kind:02x}": "native kind motion, presence and collision tracks from ROM/NoteTrack join",
        "shot.flag.0x1": "selects row+0x14 terminal effect (0x0216ADC0); spawned at teardown (0x0216E5B8 -> 0x0206C7FC)",
        "shot.flag.0x400": "kind7 native terrain repair0x0216E6D4/0x0216E730; initial closed probe per reviewed decode",
        "shot.bytes16_27.nonzero": "row+0x14 exported as end_effect; +0x10/+0x18 are zero alternate end-effect/unused fields on this path",
    }
    if kind == 7 and shot.get("integration", {}).get("direction_rule") == "reverse_if_byte_plus64_ge128":
        notes["shot.b1.nonzero"] = "row+1 -> scratch+0x24 (0x0216AD6C/74); kind7 facing reversal (0x0216E104..0x0216E11C)"
    if key not in notes:
        return None
    if key == "shot.flag.0x1" and (kind != 0 or not flags & 1 or not isinstance(shot.get("end_effect"), dict)):
        return None
    if key == "shot.flag.0x400" and (kind != 7 or not flags & 0x400):
        return None
    if key == "shot.bytes16_27.nonzero" and (kind != 0 or not isinstance(shot.get("end_effect"), dict)):
        return None
    return _handled(notes[key])


def static_rows(char: dict, slot: str, anim: str, move: dict, kit_recs: set, shots: list,
                koma: Optional[int], contact_polls_proven: Optional[bool] = None,
                native_op1_proven: bool = False) -> list:
    """The `unsupported[]` rows of one move's static closure in the feature census `char` (one
    character row). Every occurrence of a key is judged on its own: it writes a row when
    FEATURE_STATUS says `unsupported`, or `partial` and the kit does not cover that occurrence
    (COVERED_BY matches anim, frame and shot row). A KB record the closure names but the kit does not
    carry writes one row naming it; its other fields are not repeated. Rows are deduplicated per key
    and slot; the note names the first uncovered locations, and `@k<koma>` marks a special set's move."""
    if contact_polls_proven is None:
        contact_polls_proven = any(shot.get("move") == slot and shot.get("rehit_windows")
                                   for shot in shots)
    suffix = f" @k{koma}" if koma is not None else ""
    prefix = char["prefix"]
    anim = norm_anim(anim) or norm_anim((move.get("mash") or {}).get("anim")) or ""    # a set move may name its anim only in mash
    if not anim:
        return [{"slot": slot, "what": f"{STATIC_WHAT}: no anim",
                 "note": f"{prefix}{suffix}: the move resolved no anim, so its static closure was not scanned"}]
    member = f"{prefix}_{koma}" if koma is not None else prefix
    locs, shot_rows, edges = _closure(char, member, anim)
    if not locs:
        return [{"slot": slot, "what": f"{STATIC_WHAT}: anim not in census",
                 "note": f"{prefix}{suffix} {anim}: the feature census has no such anim"}]
    root = locs[0]
    view = _View(move, shots, root, _join_shots(char, root, shots))
    occs: list = []
    recs = set()
    for loc in locs:
        a = char["anims"][loc]
        for key, frames in a["keys"].items():
            count: dict = {}
            for f in frames:
                occs.append(Occ(key, loc, f, nth=count.get(f, 0)))
                count[f] = count.get(f, 0) + 1
        recs |= set(a["recs"])
    for row, via, frame, nth in edges:
        if row in shot_rows:
            occs += [Occ(key, member, frame, row=row, nth=nth, via=via) for key in char["shots"][row]["keys"]]
    missing = []
    for rec in sorted(recs):
        keys = char["records"].get(str(rec))
        if keys is None or "rec.kind.0" in keys:        # kind 0: a plain box, no hit
            continue
        if rec not in kit_recs:
            missing.append(rec)
            continue
        occs += [Occ(key, member, rec=rec) for key in keys]
    uncovered: dict = {}
    for o in occs:
        if native_op1_proven and prefix == "rk_b_01" and o.key in {f"op1.sub{n}" for n in range(5)}:
            continue
        f = _feature(o.key)
        if o.row is not None:
            if any(str(shot.get("row")) == str(o.row)
                   and (o.frame, o.nth) in view.joined
                   and native_shot_feature(shot, o.key) is not None for shot in shots):
                continue
        # The exporter proves this from the manifest's native contact branch.
        if (contact_polls_proven and o.loc == root
                and o.key in ("op0.sub5.arm", "op0.sub5.disarm")):
            polls = move.get("mash", {}).get("contact_wait", [])
            if any(p["frame"] == o.frame and (p["to"] is None) == o.key.endswith("disarm")
                   for p in polls):
                continue
        if f.status in ("handled", "out_of_band", "split"):
            continue
        if f.status == "partial" and _is_covered(f, view, o):
            continue
        uncovered.setdefault(o.key, []).append(o)
    out = [{"slot": slot, "what": f"{STATIC_WHAT}: {key}",
            "note": f"{FEATURE_STATUS[key].status}: {FEATURE_STATUS[key].why}; {prefix}{suffix} "
                    f"{_where(_places(uncovered[key]))}"} for key in sorted(uncovered)]
    if missing:
        out.append({"slot": slot, "what": f"{STATIC_WHAT}: record not in the kit",
                    "note": f"{prefix}{suffix} " + ", ".join(f"rec {r}" for r in missing[:NOTE_LOCS * 3])
                    + (f", +{len(missing) - NOTE_LOCS * 3} more" if len(missing) > NOTE_LOCS * 3 else "")
                    + ": named by the move's anim closure, in no kit record list"})
    return dedupe_rows(out)
