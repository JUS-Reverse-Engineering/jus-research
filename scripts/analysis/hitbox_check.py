#!/usr/bin/env python3
"""hitbox_check.py -- regression checks for `atns41_hitbox_dump.gdb` captures.

Why this exists
----------------
`jus-atns.4.1` step 2: the previous version of the probe read `record+0x60`
(a ColObj *wrapper*) as if it were the geometry rectangle itself, producing
captures that silently "worked" (valid JSON, non-crashing renders) while
every value was garbage -- `pos` always `[0,0,0]`, half-extents negative,
"sub count" the low half of a pointer (see
`docs/research/feel-captures/kakashi-kit-2026-09-12/RESULTS.md`,
"Orchestrator verdict"). This script exists so that mistake (or one shaped
like it) fails loudly and specifically instead of shipping a silently wrong
render.

Checks
------
1. **Element/wrapper identity (check A)** -- every element's `e20`
   (back-pointer to its wrapper, read off the element itself) must equal
   the `wrap` value the probe logs *independently* per record (a "record"
   line, `rec+0x60`, emitted before the element walk starts -- see
   `atns41_hitbox_dump.gdb`). The probe walks one wrapper's element list
   per record, so every element logged under the same `record` index
   shares that record's `wrap`; if `e20` disagrees, either the element
   walk or the record's own `rec+0x60` read is wrong.
2. **Fighter body-position agreement (check B)** -- on the fighter body
   record (record 11 for P1, record 12 for P2, per RESULTS.md's
   "Debugger" and "Re-capture" sections), the body element's own position
   (`pos[0] // 16`) must equal that frame's independently-logged fighter
   physics x (`fighter` line, `physx`, read off the fixed physics-element
   address `0x0220C068`/`+0x40` -- physics.md §5 (`0x0220C074` = element+0x0C) and §6, not derived from
   the ColPrm chain), within ±1 raw unit for sampling slop. The Refuter
   (2026-09-12 19:10) found the previous version of this check vacuous:
   every element on a wrapper shares `elem+0x08`, so comparing elements'
   `pos` to each other never fails even when the whole record's position
   chain is wrong. This check instead cross-references a value read from
   an entirely different address (the fixed physics element), so it fails
   for real when the ColPrm position chain is broken.
3. **Bounds sanity (check C)** -- `0 <= cnt <= 8` always (the probe itself
   caps the sub walk at 8; a value outside that range means the field was
   misread), and whenever `cnt > 0`, both half-extent components must be
   `>= 0` (a real, active rectangle cannot have a negative half-extent;
   the old bug produced exactly this).

Only `type: "elem"`/`"record"`/`"fighter"` lines (the current, fixed probe
format) are checked. Legacy `type: "node"` lines (pre-fix captures) carry
no `id`/`e20` and are skipped with a note -- `hitbox_strip.py` still
renders them for backward compatibility, but this checker has nothing to
verify without element identity.

Usage
-----
    python3 hitbox_check.py CAPTURE.jsonl

Exits non-zero and prints one line per failure if any check fails.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict


# Body-record index per fighter slot, per RESULTS.md's "Debugger" (16:50)
# and "Re-capture" (18:46) sections: record 11 is P1 Kakashi's own body,
# record 12 is P2 Jotaro's own body, on this state
# (`pc-kakashi-npc-jotaro-dark-tournament`, fixed fighter slots 0/1).
BODY_RECORD_BY_SLOT = {0: 11, 1: 12}


def load_elem_lines(path: str) -> list[dict]:
    """Return every `type: "elem"` object in file order. Non-elem lines
    (GDB console noise, `frame`/`fighter`/`record`/`manager` lines, and
    legacy `node` lines -- see module docstring) are dropped without
    counting as malformed. Malformed/non-JSON lines ARE counted and
    reported to stderr (jus-atns.4.2) -- see `_load_lines`/`_load_and_report`."""
    return _load_and_report(path, "elem")


def load_record_lines(path: str) -> list[dict]:
    """Return every `type: "record"` object (the independently-logged
    `rec+0x60` wrapper pointer per live record) in file order."""
    return _load_and_report(path, "record")


def load_fighter_lines(path: str) -> list[dict]:
    """Return every `type: "fighter"` object (includes `physx`/`physy`,
    the fixed physics-element position) in file order."""
    return _load_and_report(path, "fighter")


def _load_lines(path: str, wanted_type: str) -> tuple[list[dict], int]:
    """Return (`objects of type wanted_type`, count of malformed/non-JSON
    lines encountered). jus-atns.4.2: malformed lines used to be skipped
    silently (indistinguishable from "this file just has no lines of this
    type"); they are now counted here and reported by the public
    `load_*_lines` wrappers below instead of disappearing."""
    out = []
    malformed = 0
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if obj.get("type") == wanted_type:
                out.append(obj)
    return out, malformed


def _load_and_report(path: str, wanted_type: str) -> list[dict]:
    out, malformed = _load_lines(path, wanted_type)
    if malformed:
        print(
            "warning: %s: %d malformed/non-JSON line(s) skipped while "
            "loading %r lines" % (path, malformed, wanted_type),
            file=sys.stderr,
        )
    return out


def check_e20_consistency(elems: list[dict], records: list[dict] | None = None) -> list[str]:
    """Check A: every element's `e20` (its own back-pointer to its
    wrapper) must equal the `wrap` value the probe logged independently
    for that (frame, record) -- a "record" line emitted before the
    element walk starts (`rec+0x60`, read off the record, not off any
    element). This is a real cross-check, not two reads of the same
    pointer arithmetic: `e20` comes from `*(elem+0x20)`, `wrap` comes from
    `*(rec+0x60)`.

    `records` is optional for backward compatibility with captures that
    predate the "record" line (falls back to comparing elements' `e20`
    values to each other, the old, weaker check)."""
    errors = []
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for e in elems:
        groups[(e["frame"], e["record"])].append(e)

    wrap_by_key: dict[tuple, str] = {}
    if records:
        for r in records:
            wrap_by_key[(r["frame"], r["record"])] = r.get("wrap")

    for (frame, record), group in groups.items():
        e20s = {g.get("e20") for g in group}
        expected = wrap_by_key.get((frame, record))
        if expected is not None:
            if e20s != {expected}:
                errors.append(
                    "frame %d record %d: element e20 %s != logged rec+0x60 %r"
                    % (frame, record, sorted(e20s), expected)
                )
        elif len(e20s) > 1:
            errors.append(
                "frame %d record %d: elements disagree on e20 (wrapper) -- %s"
                % (frame, record, sorted(e20s))
            )
    return errors


def _pos16(e: dict):
    pos = e.get("pos", [0, 0, 0])
    return pos[0] // 16, pos[1] // 16, pos[2] // 16


def check_body_position_agreement(
    elems: list[dict],
    fighters: list[dict],
    tolerance: int = 1,
    _stats: dict | None = None,
) -> list[str]:
    """Check B: on the fighter body record (record 11 for slot 0/P1,
    record 12 for slot 1/P2 -- BODY_RECORD_BY_SLOT), the body element's
    (`id == 0`) `pos[0] // 16` must equal that frame's independently-
    logged `physx` (the fixed physics-element read, not the ColPrm chain),
    within `tolerance` raw units either way (sampling slop between the two
    reads on the same frame). The Refuter (2026-09-12 19:10) found the
    prior version of this check -- comparing elements on the same wrapper
    to each other -- vacuous, since they share `elem+0x08` by construction
    and so always agree regardless of whether the position chain is
    correct.

    jus-atns.4.2: that same vacuity trap still applied at one remove -- a
    capture with no matching (body element, fighter physics) pair at all
    made zero comparisons and this check reported PASS (an empty error
    list) despite never actually checking anything. This now fails loudly
    when it makes zero comparisons instead. Pass `_stats` (a dict) to also
    get the comparison count back out under `_stats["comparisons"]` --
    used by `run_checks`/`main` to report the count regardless of pass/
    fail."""
    errors = []
    comparisons = 0
    physx_by_frame_slot: dict[tuple, int] = {}
    for f in fighters:
        physx_by_frame_slot[(f["frame"], f.get("slot"))] = f.get("physx")

    body_by_key: dict[tuple, dict] = {}
    for e in elems:
        if e.get("id") == 0:
            body_by_key[(e["frame"], e["record"])] = e

    for slot, record in BODY_RECORD_BY_SLOT.items():
        for (frame, rec), body in body_by_key.items():
            if rec != record:
                continue
            physx = physx_by_frame_slot.get((frame, slot))
            if physx is None:
                continue
            comparisons += 1
            body_x = _pos16(body)[0]
            if abs(body_x - physx) > tolerance:
                errors.append(
                    "frame %d record %d (slot %d): body pos[0]//16 %d != "
                    "physics physx %d (tolerance %d)"
                    % (frame, record, slot, body_x, physx, tolerance)
                )

    if _stats is not None:
        _stats["comparisons"] = comparisons

    if comparisons == 0:
        errors.append(
            "check B made 0 comparisons -- no (body element, fighter "
            "physics) pair matched by (frame, slot/record); this would "
            "otherwise PASS vacuously (jus-atns.4.2 non-vacuity guard)"
        )
    return errors


def check_bounds(elems: list[dict]) -> list[str]:
    """0 <= cnt <= 8 always; half_extent components >= 0 whenever cnt > 0."""
    errors = []
    for e in elems:
        cnt = e.get("cnt", 0)
        if not (0 <= cnt <= 8):
            errors.append(
                "frame %s record %s elem %s: cnt %r out of range [0, 8]"
                % (e.get("frame"), e.get("record"), e.get("elem"), cnt)
            )
            continue
        if cnt > 0:
            hx, hy = e.get("half_extent", [0, 0])
            if hx < 0 or hy < 0:
                errors.append(
                    "frame %s record %s elem %s: cnt %d but half_extent %s has a "
                    "negative component"
                    % (e.get("frame"), e.get("record"), e.get("elem"), cnt, [hx, hy])
                )
    return errors


def run_checks(
    elems: list[dict],
    records: list[dict] | None = None,
    fighters: list[dict] | None = None,
    stats: dict | None = None,
) -> dict[str, list[str]]:
    """Run all three checks (A, B, C). `records`/`fighters` are optional
    for callers/tests that only care about a subset of checks; omitting
    `fighters` means check B makes 0 comparisons, which now fails loudly
    (jus-atns.4.2) rather than reporting an empty, vacuously-passing error
    list. Pass `stats` (a dict) to also get check B's comparison count
    back out under `stats["body_position_comparisons"]`, reported by
    `main` regardless of pass/fail."""
    body_stats: dict = {}
    body_errors = check_body_position_agreement(elems, fighters or [], _stats=body_stats)
    if stats is not None:
        stats["body_position_comparisons"] = body_stats.get("comparisons", 0)
    return {
        "e20 consistency": check_e20_consistency(elems, records),
        "fighter position agreement": body_errors,
        "bounds sanity": check_bounds(elems),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("jsonl", help="capture file from atns41_hitbox_dump.gdb")
    args = ap.parse_args(argv)

    elems = load_elem_lines(args.jsonl)
    records = load_record_lines(args.jsonl)
    fighters = load_fighter_lines(args.jsonl)
    if not elems:
        print(
            "%s: no `elem` lines found (only legacy `node` lines, or an "
            "empty/paused capture) -- nothing to check." % args.jsonl,
            file=sys.stderr,
        )
        return 2

    stats: dict = {}
    results = run_checks(elems, records, fighters, stats=stats)
    failed = False
    for name, errors in results.items():
        suffix = ""
        if name == "fighter position agreement":
            suffix = " (%d comparison(s) made)" % stats.get("body_position_comparisons", 0)
        if errors:
            failed = True
            print("FAIL: %s%s (%d issue(s))" % (name, suffix, len(errors)))
            for err in errors[:10]:
                print("  - %s" % err)
            if len(errors) > 10:
                print("  ... and %d more" % (len(errors) - 10))
        else:
            print("PASS: %s%s" % (name, suffix))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
