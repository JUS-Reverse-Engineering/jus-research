import csv
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import _deps

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis", "hitbox_strip.py")
SPEC = importlib.util.spec_from_file_location("hitbox_strip", SCRIPT)
hitbox_strip = importlib.util.module_from_spec(SPEC)
sys.modules["hitbox_strip"] = hitbox_strip
SPEC.loader.exec_module(hitbox_strip)


FIXTURE_LINES = [
    {"type": "manager", "addr": "0x220dde0"},
    {"type": "frame", "frame": 1},
    {
        "type": "fighter",
        "frame": 1,
        "slot": 0,
        "obj": "0x2228e80",
        "state": 0,
        "M": "0x220f30c",
        "flags78": "0x0",
    },
    {
        "type": "fighter",
        "frame": 1,
        "slot": 1,
        "obj": "0x224ef00",
        "state": 0,
        "M": "0x220f494",
        "flags78": "0x0",
    },
    {
        "type": "elem",
        "frame": 1,
        "record": 0,
        "elem": "0x220e100",
        "id": 0,
        "cnt": 0,
        "flags": "0x0",
        "e20": "0x220e0c0",
        "pos": [409600, 819200, 0],
        "extent_off": [0, 0],
        "half_extent": [10, 10],
        "rec34": "0x0",
        "rec38": "0x0",
        "rec40": "0x0",
        "sub": [],
    },
    {"type": "frame", "frame": 2},
    {
        "type": "elem",
        "frame": 2,
        "record": 0,
        "elem": "0x220e100",
        "id": 0,
        "cnt": 1,
        "flags": "0x0",
        "e20": "0x220e0c0",
        "pos": [409600, 819200, 0],
        "extent_off": [0, 0],
        "half_extent": [10, 10],
        "rec34": "0x0",
        "rec38": "0x800",
        "rec40": "0x0",
        "sub": [[5, 0, 20, 8]],
    },
    {"type": "frame", "frame": 3},
    {
        "type": "elem",
        "frame": 3,
        "record": 0,
        "elem": "0x220e100",
        "id": 0,
        "cnt": 1,
        "flags": "0x0",
        "e20": "0x220e0c0",
        "pos": [409600, 819200, 0],
        "extent_off": [0, 0],
        "half_extent": [10, 10],
        "rec34": "0x0",
        "rec38": "0x800",
        "rec40": "0x0",
        "sub": [[5, 0, 20, 8]],
    },
    {"type": "frame", "frame": 4},
]

# Legacy (pre-jus-atns.4.1-fix) capture shape: `record+0x60` read directly
# as if it were the geometry element, per RESULTS.md's "Orchestrator
# verdict" section -- pos always [0,0,0], subcount/half_extent garbage.
LEGACY_FIXTURE_LINES = [
    {"type": "frame", "frame": 1},
    {
        "type": "node",
        "frame": 1,
        "record": 13,
        "colobj": "0x220e100",
        "pos": [0, 0, 0],
        "extent_off": [-24460, 28528],
        "half_extent": [-24460, 28528],
        "subcount": 31624,
        "rec34": "0x0",
        "rec38": "0x0",
        "rec40": "0x0",
        "colobj18": "0x0",
        "sub": [],
    },
]


class TestHitboxStrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.jsonl_path = os.path.join(self.tmp.name, "capture.jsonl")
        with open(self.jsonl_path, "w", encoding="utf-8") as fh:
            for line in FIXTURE_LINES:
                fh.write(json.dumps(line) + "\n")

    def test_load_jsonl_groups_by_frame_in_order(self):
        frames = hitbox_strip.load_jsonl(self.jsonl_path)
        self.assertEqual([f.frame for f in frames], [1, 2, 3, 4])
        self.assertEqual(len(frames[0].fighters), 2)
        self.assertEqual(len(frames[0].nodes), 1)
        # frame 1's element has cnt 0 -> only its own rect, no subs
        self.assertEqual(len(frames[0].nodes[0]["rects"]), 1)
        self.assertEqual(frames[0].nodes[0]["rects"][0].kind, "elem")

    def test_node_with_cnt_gets_sub_rect(self):
        frames = hitbox_strip.load_jsonl(self.jsonl_path)
        node = frames[1].nodes[0]  # frame 2
        rects = node["rects"]
        self.assertEqual(len(rects), 2)  # elem rect + one sub
        sub = [r for r in rects if r.kind == "sub"][0]
        self.assertEqual((sub.off_x, sub.off_y, sub.half_x, sub.half_y), (5, 0, 20, 8))
        self.assertEqual(node["id"], 0)
        self.assertEqual(node["e20"], "0x220e0c0")

    def test_active_records_first_last(self):
        frames = hitbox_strip.load_jsonl(self.jsonl_path)
        first, last = hitbox_strip.active_records(frames)
        # record 0, id 0 has cnt > 0 on frames 2 and 3, not 1 or 4 -- keyed
        # by (record, id), not record alone
        self.assertEqual(first[(0, 0)], 2)
        self.assertEqual(last[(0, 0)], 3)

    def test_active_records_groups_by_record_and_id(self):
        """A record with two coexisting elements (a body id 0 and a
        move-specific id) must report separate first/last windows per id,
        not merged under the record -- the Refuter's fix (2026-09-12
        19:10): grouping by record alone hides this."""
        lines = [
            {"type": "frame", "frame": 1},
            {
                "type": "elem", "frame": 1, "record": 13, "elem": "0x1", "id": 0,
                "cnt": 1, "e20": "0x9", "pos": [0, 0, 0],
                "extent_off": [0, 0], "half_extent": [10, 10], "sub": [],
            },
            {"type": "frame", "frame": 2},
            {
                "type": "elem", "frame": 2, "record": 13, "elem": "0x1", "id": 0,
                "cnt": 1, "e20": "0x9", "pos": [0, 0, 0],
                "extent_off": [0, 0], "half_extent": [10, 10], "sub": [],
            },
            {
                "type": "elem", "frame": 2, "record": 13, "elem": "0x2", "id": 263,
                "cnt": 1, "e20": "0x9", "pos": [0, 0, 0],
                "extent_off": [0, 0], "half_extent": [12, 12],
                "sub": [[-8, -13, 24, 21]],
            },
            {"type": "frame", "frame": 3},
            {
                "type": "elem", "frame": 3, "record": 13, "elem": "0x1", "id": 0,
                "cnt": 1, "e20": "0x9", "pos": [0, 0, 0],
                "extent_off": [0, 0], "half_extent": [10, 10], "sub": [],
            },
        ]
        path = os.path.join(self.tmp.name, "two_elem.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for line in lines:
                fh.write(json.dumps(line) + "\n")
        frames = hitbox_strip.load_jsonl(path)
        first, last = hitbox_strip.active_records(frames)
        self.assertEqual(first[(13, 0)], 1)
        self.assertEqual(last[(13, 0)], 3)
        # the move-specific id is live only on frame 2 -- distinct from
        # the body element's 1-3 window
        self.assertEqual(first[(13, 263)], 2)
        self.assertEqual(last[(13, 263)], 2)

    def test_rect_bounds_use_pos_over_4096_as_origin(self):
        r = hitbox_strip.Rect(off_x=5, off_y=-3, half_x=2, half_y=1, kind="sub")
        # pos [409600, 819200] / 4096 == [100, 200]
        x0, y0, x1, y1 = r.bounds(pos_x=409600, pos_y=819200)
        self.assertEqual((x0, y0, x1, y1), (103, 196, 107, 198))

    def test_write_csv_one_row_per_active_element(self):
        frames = hitbox_strip.load_jsonl(self.jsonl_path)
        out_path = os.path.join(self.tmp.name, "frames.csv")
        hitbox_strip.write_csv(frames, out_path)
        with open(out_path, encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        # only cnt>0 rows, once per element: frame1 (cnt=0) contributes
        # nothing, frame2 and frame3 (cnt=1 each) contribute one row each,
        # frame4 has no element at all
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["frame"], "2")
        self.assertEqual(rows[0]["rect_kind"], "sub")
        self.assertEqual(rows[0]["pos_x"], "409600")
        self.assertIn("e20", rows[0])

    def test_write_csv_two_sub_element_yields_two_rows(self):
        """jus-atns.4.2: write_csv used to emit only `_display_rects(node)[0]`,
        silently dropping every sub past the first. An element with two
        subs must now produce two CSV rows (rect_index 0 and 1)."""
        lines = [
            {"type": "frame", "frame": 1},
            {
                "type": "elem",
                "frame": 1,
                "record": 11,
                "elem": "0x220e100",
                "id": 256,
                "cnt": 2,
                "e20": "0x220e0c0",
                "pos": [409600, 819200, 0],
                "extent_off": [0, 0],
                "half_extent": [10, 10],
                "sub": [[-8, -13, 24, 21], [1, 2, 3, 4]],
            },
        ]
        path = os.path.join(self.tmp.name, "two_sub.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for line in lines:
                fh.write(json.dumps(line) + "\n")
        frames = hitbox_strip.load_jsonl(path)
        out_path = os.path.join(self.tmp.name, "two_sub.csv")
        hitbox_strip.write_csv(frames, out_path)
        with open(out_path, encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["rect_index"], "0")
        self.assertEqual(rows[1]["rect_index"], "1")
        self.assertEqual((rows[0]["off_x"], rows[0]["half_x"]), ("-8", "24"))
        self.assertEqual((rows[1]["off_x"], rows[1]["half_x"]), ("1", "3"))

    def test_write_markdown_table_reports_first_last(self):
        frames = hitbox_strip.load_jsonl(self.jsonl_path)
        out_path = os.path.join(self.tmp.name, "active_frames.md")
        hitbox_strip.write_markdown_table(frames, out_path, "test-attack")
        with open(out_path, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("test-attack", text)
        self.assertIn("| 0 | 0 | 2 | 3 |", text)

    @_deps.needs("PIL")
    def test_render_strip_produces_one_png(self):
        frames = hitbox_strip.load_jsonl(self.jsonl_path)
        out_path = os.path.join(self.tmp.name, "strip.png")
        hitbox_strip.render_strip(frames, out_path, "test-attack")
        self.assertTrue(os.path.exists(out_path))
        self.assertGreater(os.path.getsize(out_path), 0)

    @_deps.needs("PIL")
    def test_main_end_to_end(self):
        out_dir = os.path.join(self.tmp.name, "out")
        rc = hitbox_strip.main(
            [self.jsonl_path, "--out-dir", out_dir, "--attack", "b"]
        )
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "strip.png")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "frames.csv")))
        self.assertTrue(os.path.exists(os.path.join(out_dir, "active_frames.md")))

    def test_main_empty_capture_fails_loudly(self):
        empty = os.path.join(self.tmp.name, "empty.jsonl")
        with open(empty, "w") as fh:
            fh.write(json.dumps({"type": "meta", "note": "no frames"}) + "\n")
        out_dir = os.path.join(self.tmp.name, "out_empty")
        import io, contextlib
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rc = hitbox_strip.main([empty, "--out-dir", out_dir, "--attack", "b"])
        self.assertNotEqual(rc, 0)
        self.assertIn("pause", err.getvalue().lower())
        self.assertFalse(os.path.exists(os.path.join(out_dir, "strip.png")))

    def test_legacy_node_format_still_parses(self):
        legacy_path = os.path.join(self.tmp.name, "legacy.jsonl")
        with open(legacy_path, "w", encoding="utf-8") as fh:
            for line in LEGACY_FIXTURE_LINES:
                fh.write(json.dumps(line) + "\n")
        frames = hitbox_strip.load_jsonl(legacy_path)
        self.assertEqual(len(frames), 1)
        node = frames[0].nodes[0]
        self.assertEqual(node["record"], 13)
        self.assertIsNone(node["id"])
        self.assertIsNone(node["e20"])
        self.assertEqual(node["cnt"], 31624)

    @_deps.needs("PIL")
    def test_legacy_capture_still_renders_without_crashing(self):
        legacy_path = os.path.join(self.tmp.name, "legacy.jsonl")
        with open(legacy_path, "w", encoding="utf-8") as fh:
            for line in LEGACY_FIXTURE_LINES:
                fh.write(json.dumps(line) + "\n")
        out_dir = os.path.join(self.tmp.name, "legacy_out")
        rc = hitbox_strip.main([legacy_path, "--out-dir", out_dir, "--attack", "legacy"])
        self.assertEqual(rc, 0)
        self.assertTrue(os.path.exists(os.path.join(out_dir, "strip.png")))


if __name__ == "__main__":
    unittest.main()
