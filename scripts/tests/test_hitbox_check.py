import contextlib
import io
import json
import os
import tempfile
import unittest

import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis"))
import hitbox_check  # noqa: E402


# Body record 11 = P1/slot 0 (BODY_RECORD_BY_SLOT), per RESULTS.md's
# Debugger/Re-capture sections. physx is the fixed physics-element read
# (raw 8.8, i.e. pos//16 units); body element pos[0] // 16 must agree.
GOOD_LINES = [
    {"type": "frame", "frame": 1},
    {"type": "record", "frame": 1, "record": 11, "wrap": "0x220e0c0"},
    {"type": "fighter", "frame": 1, "slot": 0, "obj": "0x2228e80", "state": 0,
     "physx": 25600, "physy": 0},
    {
        "type": "elem",
        "frame": 1,
        "record": 11,
        "elem": "0x220e100",
        "id": 0,
        "cnt": 1,
        "e20": "0x220e0c0",
        "pos": [409600, 819200, 0],
        "extent_off": [0, 0],
        "half_extent": [10, 20],
        "sub": [[1, 2, 3, 4]],
    },
    {
        "type": "elem",
        "frame": 1,
        "record": 11,
        "elem": "0x220e200",
        "id": 263,
        "cnt": 1,
        "e20": "0x220e0c0",
        "pos": [409600, 819200, 0],
        "extent_off": [5, 5],
        "half_extent": [12, 12],
        "sub": [[1, 1, 2, 2]],
    },
]

# Shaped after RESULTS.md's "Orchestrator verdict": old base pointer read
# as if `record+0x60` were the geometry object directly -- pos always
# [0,0,0], half-extent negative, cnt reading as the low half of a pointer,
# and (contrived here) a mismatched e20 to also exercise check A. physx is
# a real, non-zero physics read, so check B must fail too (pos//16 is 0).
BAD_LINES = [
    {"type": "frame", "frame": 1},
    {"type": "record", "frame": 1, "record": 11, "wrap": "0x220e0c0"},
    {"type": "fighter", "frame": 1, "slot": 0, "obj": "0x2228e80", "state": 0,
     "physx": 25600, "physy": 0},
    {
        "type": "elem",
        "frame": 1,
        "record": 11,
        "elem": "0x220e100",
        "id": 0,
        "cnt": 31624,
        "e20": "0x220e0c0",
        "pos": [0, 0, 0],
        "extent_off": [-24460, 28528],
        "half_extent": [-24460, 28528],
        "sub": [],
    },
    {
        "type": "elem",
        "frame": 1,
        "record": 11,
        "elem": "0x220e200",
        "id": 263,
        "cnt": 1,
        "e20": "0x220e999",  # disagrees with the logged rec+0x60 above
        "pos": [123456, 0, 0],
        "extent_off": [0, 0],
        "half_extent": [-9936, 571],
        "sub": [],
    },
]

# A capture that is otherwise well-formed (e20 matches wrap, bounds are
# sane) but whose body element position disagrees with the independently
# logged physics x -- must fail check B only.
MISMATCHED_X_LINES = [
    {"type": "frame", "frame": 1},
    {"type": "record", "frame": 1, "record": 11, "wrap": "0x220e0c0"},
    {"type": "fighter", "frame": 1, "slot": 0, "obj": "0x2228e80", "state": 0,
     "physx": 25600, "physy": 0},
    {
        "type": "elem",
        "frame": 1,
        "record": 11,
        "elem": "0x220e100",
        "id": 0,
        "cnt": 1,
        "e20": "0x220e0c0",
        # pos[0] // 16 == 12345, far from physx 25600
        "pos": [197520, 0, 0],
        "extent_off": [0, 0],
        "half_extent": [10, 20],
        "sub": [],
    },
]


# jus-atns.4.2: a well-formed-per-line capture with a `fighter` line and a
# body element, but on *different* frames -- so `check_body_position_agreement`
# never finds a matching (frame, slot/record) pair and makes 0 comparisons.
# Before the non-vacuity guard this reported PASS (empty error list).
ZERO_COMPARISON_LINES = [
    {"type": "frame", "frame": 1},
    {"type": "record", "frame": 1, "record": 11, "wrap": "0x220e0c0"},
    {"type": "fighter", "frame": 1, "slot": 0, "obj": "0x2228e80", "state": 0,
     "physx": 25600, "physy": 0},
    {"type": "frame", "frame": 2},
    {"type": "record", "frame": 2, "record": 11, "wrap": "0x220e0c0"},
    {
        "type": "elem",
        "frame": 2,
        "record": 11,
        "elem": "0x220e100",
        "id": 0,
        "cnt": 1,
        "e20": "0x220e0c0",
        "pos": [409600, 819200, 0],
        "extent_off": [0, 0],
        "half_extent": [10, 20],
        "sub": [],
    },
]


def _write(lines):
    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    )
    for line in lines:
        tmp.write(json.dumps(line) + "\n")
    tmp.close()
    return tmp.name


def _load(path):
    return (
        hitbox_check.load_elem_lines(path),
        hitbox_check.load_record_lines(path),
        hitbox_check.load_fighter_lines(path),
    )


def _run_main(path):
    """hitbox_check.main(path) with its report captured: (rc, stdout, stderr).

    The negative-case tests feed deliberately bad captures, so main() prints
    FAIL lines by design; capturing keeps them out of the suite log (where
    they read as real failures) and lets the tests assert on them instead."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = hitbox_check.main([path])
    return rc, out.getvalue(), err.getvalue()


class TestHitboxCheck(unittest.TestCase):
    def test_good_capture_passes_all_checks(self):
        path = _write(GOOD_LINES)
        self.addCleanup(os.remove, path)
        elems, records, fighters = _load(path)
        results = hitbox_check.run_checks(elems, records, fighters)
        for name, errors in results.items():
            self.assertEqual(errors, [], "%s should have no failures: %s" % (name, errors))

    def test_good_capture_main_exits_zero(self):
        path = _write(GOOD_LINES)
        self.addCleanup(os.remove, path)
        rc, out, _ = _run_main(path)
        self.assertEqual(rc, 0)
        self.assertNotIn("FAIL", out)
        self.assertEqual(out.count("PASS:"), 3)

    def test_old_base_capture_fails_e20_consistency_check_a(self):
        path = _write(BAD_LINES)
        self.addCleanup(os.remove, path)
        elems, records, _ = _load(path)
        errors = hitbox_check.check_e20_consistency(elems, records)
        self.assertTrue(errors)

    def test_old_base_capture_fails_body_position_agreement_check_b(self):
        path = _write(BAD_LINES)
        self.addCleanup(os.remove, path)
        elems, _, fighters = _load(path)
        errors = hitbox_check.check_body_position_agreement(elems, fighters)
        self.assertTrue(errors)

    def test_old_base_capture_fails_bounds_sanity_check_c(self):
        path = _write(BAD_LINES)
        self.addCleanup(os.remove, path)
        elems, _, _ = _load(path)
        errors = hitbox_check.check_bounds(elems)
        # both the out-of-range cnt (body) and the negative half_extent
        # (other, cnt=1) should be flagged
        self.assertGreaterEqual(len(errors), 2)

    def test_old_base_capture_main_exits_nonzero(self):
        path = _write(BAD_LINES)
        self.addCleanup(os.remove, path)
        rc, out, _ = _run_main(path)
        self.assertEqual(rc, 1)
        self.assertIn("FAIL: e20 consistency", out)
        self.assertIn("FAIL: bounds sanity", out)

    def test_mismatched_x_fails_only_check_b(self):
        path = _write(MISMATCHED_X_LINES)
        self.addCleanup(os.remove, path)
        elems, records, fighters = _load(path)
        results = hitbox_check.run_checks(elems, records, fighters)
        self.assertEqual(results["e20 consistency"], [])
        self.assertEqual(results["bounds sanity"], [])
        self.assertTrue(results["fighter position agreement"])

    def test_no_elem_lines_exits_nonzero(self):
        path = _write([{"type": "frame", "frame": 1}])
        self.addCleanup(os.remove, path)
        rc, out, err = _run_main(path)
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertIn("no `elem` lines found", err)

    def test_zero_comparisons_fails_check_b(self):
        """jus-atns.4.2 non-vacuity guard: a capture where check B never
        finds a matching (body element, fighter physics) pair must FAIL,
        not report an empty (vacuously passing) error list."""
        path = _write(ZERO_COMPARISON_LINES)
        self.addCleanup(os.remove, path)
        elems, records, fighters = _load(path)
        errors = hitbox_check.check_body_position_agreement(elems, fighters)
        self.assertTrue(errors)
        self.assertIn("0 comparisons", errors[0])

    def test_zero_comparisons_reports_comparison_count(self):
        path = _write(ZERO_COMPARISON_LINES)
        self.addCleanup(os.remove, path)
        elems, records, fighters = _load(path)
        stats: dict = {}
        hitbox_check.check_body_position_agreement(elems, fighters, _stats=stats)
        self.assertEqual(stats["comparisons"], 0)

    def test_good_capture_reports_nonzero_comparison_count(self):
        path = _write(GOOD_LINES)
        self.addCleanup(os.remove, path)
        elems, records, fighters = _load(path)
        stats: dict = {}
        errors = hitbox_check.check_body_position_agreement(elems, fighters, _stats=stats)
        self.assertEqual(errors, [])
        self.assertGreater(stats["comparisons"], 0)

    def test_zero_comparisons_main_exits_nonzero(self):
        path = _write(ZERO_COMPARISON_LINES)
        self.addCleanup(os.remove, path)
        rc, out, _ = _run_main(path)
        self.assertEqual(rc, 1)
        self.assertIn("FAIL: fighter position agreement (0 comparison(s) made)", out)

    def test_load_lines_counts_malformed_lines_not_silently(self):
        """jus-atns.4.2: `_load_lines` used to skip malformed/non-JSON
        lines silently (indistinguishable from "no lines of this type").
        It must now count them and return the count alongside the parsed
        objects."""
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        )
        tmp.write(json.dumps(GOOD_LINES[3]) + "\n")  # one real "elem" line
        tmp.write("{this is not valid json\n")
        tmp.write("also not json at all\n")
        tmp.close()
        self.addCleanup(os.remove, tmp.name)

        elems, malformed = hitbox_check._load_lines(tmp.name, "elem")
        self.assertEqual(len(elems), 1)
        self.assertEqual(malformed, 2)

    def test_load_elem_lines_reports_malformed_to_stderr(self):
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        )
        tmp.write(json.dumps(GOOD_LINES[3]) + "\n")
        tmp.write("{not json\n")
        tmp.close()
        self.addCleanup(os.remove, tmp.name)

        import io
        import contextlib

        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            elems = hitbox_check.load_elem_lines(tmp.name)
        self.assertEqual(len(elems), 1)
        self.assertIn("malformed", err.getvalue().lower())


if __name__ == "__main__":
    unittest.main()
