import importlib.util
import json
import os
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis", "anim_timing.py")
SPEC = importlib.util.spec_from_file_location("anim_timing", SCRIPT)
T = importlib.util.module_from_spec(SPEC)
sys.modules["anim_timing"] = T
SPEC.loader.exec_module(T)

HAVE_ROM = T.mr.CHRARC.exists()
HAVE_EVIDENCE = T.SPECIAL_STRIPS.exists() and T.CAPS.exists()
NEED_EVIDENCE = "needs capture evidence and docs/rebuild/special-strips.json, which are not part of this repository"
B_CAPTURE = T.CAPS / "kakashi-kit-2026-09-12" / "neutral_b" / "frames.jsonl"


def rect_key(f, *xy):
    return struct.pack("<H4h", f, *xy)


class SegmentsTest(unittest.TestCase):
    def test_keys_become_spans_and_end_marker_is_split_off(self):
        spans, end = T.segments([(0, 12), (3, 13), (6, 13), (9, 12), (12, 12)], 12)
        self.assertEqual(spans, [{"cell": 12, "start": 0, "len": 3},
                                 {"cell": 13, "start": 3, "len": 6},
                                 {"cell": 12, "start": 9, "len": 3}])
        self.assertEqual(end, 12)

    def test_no_end_marker_last_span_runs_to_frames(self):
        spans, end = T.segments([(0, 19)], 4)
        self.assertEqual(spans, [{"cell": 19, "start": 0, "len": 4}])
        self.assertIsNone(end)

    def test_end_marker_may_name_a_different_cell(self):
        # Kakashi up Y ends on the jump-rise cell 17
        spans, end = T.segments([(0, 128), (55, 129), (74, 17)], 74)
        self.assertEqual(spans[-1], {"cell": 129, "start": 55, "len": 19})
        self.assertEqual(end, 17)


class DecodeTrackTest(unittest.TestCase):
    def test_keyed_rect_is_ten_bytes_per_key(self):
        raw = rect_key(0, -8, -40, 12, 0) + rect_key(8, -9, -44, 12, 0) + b"\xff\xff"
        self.assertEqual(T.decode_track("CollisionRect0", "key", raw),
                         [(0, (-8, -40, 12, 0)), (8, (-9, -44, 12, 0))])

    def test_truncated_rect_key_is_dropped(self):
        raw = rect_key(0, 1, 2, 3, 4) + struct.pack("<Hh", 8, 5)
        self.assertEqual(T.decode_track("CollisionRect0", "key", raw), [(0, (1, 2, 3, 4))])

    def test_const_rect_texture_and_signed_type(self):
        self.assertEqual(T.decode_track("CollisionRect1", "const", struct.pack("<4h", -19, -43, 12, 0)),
                         [(0, (-19, -43, 12, 0))])
        self.assertEqual(T.decode_track("TextureID", "const", struct.pack("<I", 0x60400)), [(0, 0x60400)])
        self.assertEqual(T.decode_track("CollisionType0", "key", struct.pack("<Hh", 4, -1) + b"\xff\xff"),
                         [(4, -1)])
        self.assertEqual(T.decode_track("BoundsIndex", "key", struct.pack("<HH", 0, 75) + b"\xff\xff"),
                         [(0, 75)])


class PredictAndAgreeTest(unittest.TestCase):
    def anim(self):
        return T.Anim(0x1E, 12, 60, 0, {
            "CollisionType0": [(0, 0)], "CollisionRect0": [(0, (-12, -40, 10, 0))],
            "CollisionType1": [(0, 1)], "CollisionEnable1": [(0, 0), (4, 1), (6, 0)],
            "CollisionRect1": [(0, (0, -30, 20, -10))]})

    def test_facing_left_mirrors_x_and_enable_gates_a_box(self):
        an = self.anim()
        self.assertEqual(T.predict(an, 0, -1), {(0, 1.0, -20.0, 11.0, 20.0)})
        self.assertEqual(T.predict(an, 5, -1), {(0, 1.0, -20.0, 11.0, 20.0), (1, -10.0, -20.0, 10.0, 10.0)})
        self.assertEqual(T.predict(an, 5, 1) - T.predict(an, 5, -1), {(0, -1.0, -20.0, 11.0, 20.0),
                                                                      (1, 10.0, -20.0, 10.0, 10.0)})
        self.assertEqual(T.box_changes(an, 12), 2)

    def test_a_typed_channel_with_no_rect_track_puts_out_no_element(self):
        # Eve's side Y (0x21) types channel 2 and gives it no rect or enable track; the
        # live capture shows no element for it on any of the 117 frames
        an = T.Anim(0x21, 4, 60, 0, {"CollisionType0": [(0, 0)], "CollisionRect0": [(0, (-9, -47, 9, 0))],
                                     "CollisionType2": [(0, 0)]})
        self.assertEqual(T.predict(an, 0, 1), {(0, 0.0, -23.5, 9.0, 23.5)})

    def test_agrees_within_one_px_and_ignores_foreign_ids(self):
        pred = {(0, 1.0, -20.0, 11.0, 20.0)}
        self.assertTrue(T.agrees(pred, {(0, 2, -20, 11, 20), (293, 5, 5, 5, 5)}, {0}))
        self.assertFalse(T.agrees(pred, {(0, 3, -20, 11, 20)}, {0}))
        self.assertFalse(T.agrees(pred, {(0, 1, -20, 11, 20), (1, 0, 0, 4, 4)}, {0, 1}))

    def test_a_full_probe_may_hide_a_predicted_box(self):
        pred = {(0, 1.0, -20.0, 11.0, 20.0), (1, 9.0, 9.0, 9.0, 9.0)}
        four = {(0, 1, -20, 11, 20), (7, 0, 0, 1, 1), (7, 0, 0, 2, 2), (7, 0, 0, 3, 3)}
        self.assertTrue(T.agrees(pred, four, {0, 1}))
        self.assertFalse(T.agrees(pred, set(list(four)[:1]) | {(0, 1, -20, 11, 20)}, {0, 1}))


class AnchorTest(unittest.TestCase):
    def cap(self, states):
        st = {100 + i: s for i, s in enumerate(states)}
        return T.Capture(Path("x"), st, {f: 0 for f in st}, {})

    def test_rules(self):
        cap = self.cap([0, 1, 4, 4, 6, 9, 9, 6, 13, 13, 0, 0])
        self.assertEqual(T.anchor_of(cap, "leave_idle"), 102)
        self.assertEqual(T.anchor_of(cap, "state9"), 105)
        self.assertEqual(T.anchor_of(cap, "4+4"), 106)
        self.assertEqual(T.anchor_of(cap, "13-1"), 107)
        self.assertEqual(T.anchor_of(cap, "13>0-1"), 109)
        with self.assertRaises(SystemExit):
            T.anchor_of(cap, "11")


def synth_capture(states, boxes):
    """A Capture where P1 (physx 0) shows `boxes[i]` (a set of (type, cx, cy, hx, hy)) on frame 100+i."""
    st = {100 + i: s for i, s in enumerate(states)}
    el = {}
    for i, bs in enumerate(boxes):
        el[100 + i] = [{"id": b[0], "pos": [0, 0, 0], "sub": [list(b[1:])]} for b in bs]
    return T.Capture(Path("synthetic"), st, {f: 0 for f in st}, el)


def box_anim(aid, frames, rects):
    """A one-channel animation: rects = [(frame, (x0, y0, x1, y1))], type 0."""
    return T.Anim(aid, frames, 60, 0, {"CollisionType0": [(0, 0)], "CollisionRect0": rects})


X = (0, -10, -40, 10, 0)      # rect giving box (0, 0.0, -20.0, 10.0, 20.0)
XB = (0, 0, -20, 10, 20)
YB = (0, 0, -15, 10, 15)      # from rect (-10, -30, 10, 0)
ZB = (0, 0, -5, 10, 5)
STAND = box_anim(0x00, 8, [(0, (-10, -10, 10, 0))])  # its box is ZB


class CheckGateTest(unittest.TestCase):
    def test_a_look_alike_animation_makes_the_check_refuse(self):
        anims = {0x00: STAND, 0x1E: box_anim(0x1E, 6, [(0, X[1:])]), 0x1F: box_anim(0x1F, 6, [(0, X[1:])])}
        cap = synth_capture([0] + [9] * 6 + [0], [set()] + [{XB}] * 6 + [set()])
        c = T.check_capture(anims, cap, "x", 0x1E, "leave_idle", {})
        self.assertEqual((c["agree"], c["also_fits"]), (6, ["0x1f"]))
        self.assertIn("other animations fit", T.refusal(c))

    def test_a_shorter_look_alike_is_not_a_rival(self):
        anims = {0x00: STAND, 0x1E: box_anim(0x1E, 6, [(0, X[1:])]), 0x09: box_anim(0x09, 2, [(0, X[1:])])}
        cap = synth_capture([0] + [9] * 6 + [0], [set()] + [{XB}] * 6 + [set()])
        c = T.check_capture(anims, cap, "x", 0x1E, "leave_idle", {})
        self.assertEqual(c["also_fits"], [])
        self.assertIsNone(T.refusal(c))

    def test_paused_frames_must_show_the_held_boxes(self):
        an = box_anim(0x28, 8, [(0, X[1:]), (4, (-10, -30, 10, 0))])
        anims = {0x00: STAND, 0x28: an}
        good = synth_capture([0] + [9] * 11 + [0], [set()] + [{XB}] * 4 + [{XB}] * 3 + [{YB}] * 4 + [set()])
        bad = synth_capture([0] + [9] * 11 + [0], [set()] + [{XB}] * 4 + [{ZB}] * 3 + [{YB}] * 4 + [set()])
        c = T.check_capture(anims, good, "x", 0x28, "leave_idle", {"pause": (4, 3)})
        self.assertEqual((c["agree"], c["pause"]["paused_frames_agree"]), (8, 3))
        self.assertIsNone(T.refusal(c))
        c = T.check_capture(anims, bad, "x", 0x28, "leave_idle", {"pause": (4, 3)})
        self.assertEqual((c["agree"], c["pause"]["paused_frames_agree"]), (8, 0))
        self.assertIn("paused frames", T.refusal(c))

    def test_state_end_and_the_fall_after_a_cut(self):
        fall = box_anim(0x05, 4, [(0, (-10, -30, 10, 0))])
        land = box_anim(0x07, 8, [(0, (-10, -10, 10, 0))])
        anims = {0x27: box_anim(0x27, 10, [(0, X[1:])]), 0x05: fall, 0x07: land}
        states = [0] + [9] * 3 + [6] * 4 + [13, 0]
        boxes = [set()] + [{XB}] * 3 + [{YB}] * 3 + [{ZB}] + [{ZB}, set()]
        c = T.check_capture(anims, synth_capture(states, boxes), "x", 0x27, "state9",
                            {"upto": 3, "then": [0x05]})
        self.assertEqual(c["state_end"], {"at": 3, "to": 6})
        self.assertEqual(c["then"], {"anims": ["0x05"], "from_anim_frame": 3, "fall_frames": 3,
                                     "agree": 3, "last_fall_frame_shows_landing": True})
        self.assertIsNone(T.refusal(c))
        boxes[5] = {XB}
        c = T.check_capture(anims, synth_capture(states, boxes), "x", 0x27, "state9",
                            {"upto": 3, "then": [0x05]})
        self.assertIn("fall after the cut", T.refusal(c))

    def test_a_fall_that_does_not_end_on_the_landing_box_refuses(self):
        fall = box_anim(0x05, 4, [(0, (-10, -30, 10, 0))])
        land = box_anim(0x07, 8, [(0, (-10, -10, 10, 0))])
        anims = {0x27: box_anim(0x27, 10, [(0, X[1:])]), 0x05: fall, 0x07: land}
        states = [0] + [9] * 3 + [6] * 4 + [13, 0]
        boxes = [set()] + [{XB}] * 3 + [{YB}] * 4 + [{ZB}, set()]
        c = T.check_capture(anims, synth_capture(states, boxes), "x", 0x27, "state9",
                            {"upto": 3, "then": [0x05]})
        self.assertEqual((c["then"]["agree"], c["then"]["fall_frames"]), (3, 3))
        self.assertFalse(c["then"]["last_fall_frame_shows_landing"])
        self.assertIn("fall after the cut", T.refusal(c))


class MoveGatesTest(unittest.TestCase):
    AN = box_anim(0x27, 10, [(0, X[1:])])

    def chk(self, state_return=13, end_at=None, checked=10):
        return {"state_return": state_return, "checked_frames": checked,
                "state_end": {"at": end_at, "to": 6 if end_at is not None else 0}}

    def test_an_idle_return_off_frames_plus_3_needs_a_why(self):
        self.assertEqual(T.move_gates("x", self.AN, self.chk(), {}), {})
        with self.assertRaisesRegex(SystemExit, "needs a 'why'"):
            T.move_gates("x", self.AN, self.chk(state_return=20), {})
        extra = T.move_gates("x", self.AN, self.chk(state_return=20), {"why": "held"})
        self.assertEqual(extra, {"idle_return_why": "held"})

    def test_a_cut_must_match_where_the_attack_state_ends(self):
        cut = {"at": 4, "state_at": 4, "then": "fall", "cause": "TBD"}
        opts = {"cut": cut, "why": "cut"}
        extra = T.move_gates("x", self.AN, self.chk(20, end_at=4, checked=4), opts)
        self.assertEqual(extra["draw"], {"anim_frames": 4, "then": "fall", "cause": "TBD"})
        with self.assertRaisesRegex(SystemExit, "the attack state ends"):
            T.move_gates("x", self.AN, self.chk(20, end_at=5, checked=4), opts)
        with self.assertRaisesRegex(SystemExit, "the attack state ends"):
            T.move_gates("x", self.AN, self.chk(20, end_at=4, checked=5), opts)


class StripForTest(unittest.TestCase):
    STRIPS = {
        "jump": [{"cells": [22]}, {"cells": [17]}, {"cells": [18]}, {"cells": [22]}],
        "b_up": [{"cells": [112]}, {"cells": [22, 115]}],
        "y_down": [{"cells": [62, 136]}, {"cells": [137]}, {"cells": [62, 136, 140]}],
        "projectiles/kunai": [{"cells": [17]}],
    }

    def test_in_order_pick_and_unused_frames(self):
        spans = [{"cell": 136}, {"cell": 137}, {"cell": 140}]
        r = T.strip_for(spans, self.STRIPS)
        self.assertEqual(r["strip"], "y_down")
        self.assertEqual([s["pick"] for s in spans], [0, 1, 2])
        self.assertEqual(spans[0]["strip_frames"], [0, 2])
        self.assertEqual(r["strip_frames_not_in_anim"], [])

    def test_more_frames_win_then_preferred_strip_breaks_a_tie(self):
        self.assertEqual(T.strip_for([{"cell": 22}], self.STRIPS)["strip"], "jump")
        tie = {"b_up": [{"cells": [17]}], "jump": [{"cells": [17]}]}
        r = T.strip_for([{"cell": 17}], tie)
        self.assertEqual((r["strip"], r["strip_also"]), ("b_up", ["jump"]))
        r = T.strip_for([{"cell": 17}], tie, {"jump"})
        self.assertEqual((r["strip"], r["strip_also"]), ("jump", []))

    def test_a_missing_cell_has_no_pick(self):
        spans = [{"cell": 115}, {"cell": 999}]
        r = T.strip_for(spans, self.STRIPS)
        self.assertEqual((r["strip"], spans[1]["pick"]), ("b_up", None))

    def test_one_look_alike_cell_does_not_claim_a_strip(self):
        spans = [{"cell": 62}, {"cell": 63}, {"cell": 64}]
        r = T.strip_for(spans, self.STRIPS)
        self.assertIsNone(r["strip"])
        self.assertEqual([s["strip_frames"] for s in spans], [[], [], []])


class GradeFrameTest(unittest.TestCase):
    def row(self, *c):
        return [{"cell": i, "cell_cover": a, "strip_cover": b} for i, a, b in c]

    def test_grades_and_ties(self):
        self.assertEqual(T.grade_frame(self.row((83, .98, 1), (133, .98, 1), (5, .5, .5)))["cells"], [83, 133])
        self.assertEqual(T.grade_frame(self.row((105, .94, .74)))["grade"], "extra")
        self.assertEqual(T.grade_frame(self.row((97, .76, .77)))["grade"], "weak")
        self.assertEqual(T.grade_frame(self.row((1, .38, .26)))["cells"], [])
        self.assertEqual(T.grade_frame([])["grade"], "none")
        self.assertEqual(T.grade_frame(None)["grade"], "blank")


class SpecialPlaysTest(unittest.TestCase):
    """The special checks: C1/C2 rows keyed by s (= press + 3), P1's body box."""

    def anim(self):
        # body box (type 0) steps at frames 0, 4 and 8
        an = T.Anim(0x29, 12, 60, 0)
        an.tracks["CollisionType0"] = [(0, 0)]
        an.tracks["CollisionRect0"] = [(0, (-4, -40, 4, 0)), (4, (-6, -40, 6, 0)), (8, (-8, -40, 8, 0))]
        return an

    def cap(self, boxes, idle_from):
        """boxes: {s: (x0, x1)} of the anim's rects, mirrored like a left-facing P1."""
        rows = {}
        for s in range(-2, idle_from + 3):
            if s in boxes:
                x0, x1 = boxes[s]
                body = ((-(x0 + x1)) // 2, -20, (x1 - x0) // 2, 20)
            else:
                body = (2, -22, 9, 22)
            rows[s] = {"state": 0 if s < 0 or s >= idle_from else 10, "body": body}
        return T.SpecialCapture("x", rows, {s: 100 + s for s in rows})

    def test_a_straight_play_agrees_and_counts_box_changes(self):
        boxes = {s: (-4, 4) if s < 4 else (-6, 6) if s < 8 else (-8, 8) for s in range(12)}
        c = T.check_plays(self.anim(), self.cap(boxes, 15), "leave_idle", [("play", 0, 0, 12)])
        self.assertEqual((c["agree"], c["checked_frames"], c["disagree_at"]), (12, 12, []))
        self.assertEqual((c["anchor_frame"], c["state_return"], c["box_changes"]), (100, 15, 2))

    def test_a_jump_is_checked_at_its_own_offset(self):
        # frames 0-3, then frames 8-11 from s 4: a frame-4 key never shows
        boxes = {s: (-4, 4) if s < 4 else (-8, 8) for s in range(8)}
        cap = self.cap(boxes, 10)
        ok = T.check_plays(self.anim(), cap, "leave_idle", [("play", 0, 0, 4), ("play", 4, 8, 4)])
        self.assertEqual(ok["agree"], 8)
        bad = T.check_plays(self.anim(), cap, "leave_idle", [("play", 0, 0, 8)])
        self.assertEqual(bad["disagree_at"], [4, 5, 6, 7])

    def test_a_hold_accepts_any_frame_in_its_range(self):
        # s 2 shows frame 3's box, s 3-8 frame 4-7's: a hold on 3..7 takes both
        boxes = {s: (-4, 4) if s < 3 else (-6, 6) for s in range(9)}
        cap = self.cap(boxes, 12)
        c = T.check_plays(self.anim(), cap, "leave_idle", [("play", 0, 0, 2), ("hold", 2, 9, 3, 7)])
        self.assertEqual((c["agree"], c["checked_frames"]), (9, 9))
        c = T.check_plays(self.anim(), cap, "leave_idle", [("play", 0, 0, 2), ("hold", 2, 9, 8, 11)])
        self.assertEqual(c["disagree_at"], list(range(2, 9)))
        c = T.check_plays(self.anim(), cap, "leave_idle", [("play", 0, 0, 3), ("hold", 3, 9, 3, 3)])
        self.assertEqual(c["disagree_at"], list(range(3, 9)))

    def test_box_match_is_exact_where_the_prediction_is_whole(self):
        # the capture is whole pixels; a half-pixel prediction may round either way
        self.assertTrue(T.box_matches((2.0, -23.5, 15.0, 23.5), (2, -23, 15, 23)))
        self.assertTrue(T.box_matches((2.0, -23.5, 15.0, 23.5), (2, -24, 15, 24)))
        self.assertFalse(T.box_matches((2.0, -23.5, 15.0, 23.5), (2, -24, 14, 24)))
        self.assertFalse(T.box_matches((2.0, -24.0, 14.0, 24.0), (2, -23, 14, 24)))
        self.assertFalse(T.box_matches((2.0, -23.5, 15.0, 23.5), (3, -23, 15, 23)))

    def test_two_body_boxes_never_match_one(self):
        an = self.anim()
        an.tracks["CollisionType1"] = [(0, 0)]
        # a second body box that also fits the capture on its own
        an.tracks["CollisionRect1"] = [(0, (-4, -40, 4, 1))]
        boxes = {s: (-4, 4) for s in range(4)}
        c = T.check_plays(an, self.cap(boxes, 6), "leave_idle", [("play", 0, 0, 4)])
        self.assertEqual(c["disagree_at"], [0, 1, 2, 3])

    def test_the_anchor_must_be_s_0(self):
        boxes = {s: (-4, 4) for s in range(4)}
        cap = self.cap(boxes, 6)
        cap.rows[0]["state"] = 0  # the attack starts a frame late
        with self.assertRaises(SystemExit):
            T.check_plays(self.anim(), cap, "leave_idle", [("play", 0, 0, 4)])

    def test_body_from_each_watch_set(self):
        e = {"cnt": 1, "id": 0, "sub0": [1, -2, 3, 4]}
        self.assertEqual(T.special_body({"ke1": e}), (1, -2, 3, 4))
        self.assertEqual(T.special_body({"p1e1": e}), (1, -2, 3, 4))
        self.assertIsNone(T.special_body({"p1e1": {**e, "id": 12}}))
        raw = [0] * 0x44
        raw[0x0C], raw[0x0E] = 1, 0
        for k, v in enumerate((1, -2, 3, 4)):
            raw[0x3C + 2 * k], raw[0x3D + 2 * k] = struct.pack("<h", v)
        self.assertEqual(T.special_body({"raw": {"h2": raw}}), (1, -2, 3, 4))


@unittest.skipUnless(HAVE_ROM and B_CAPTURE.exists(), "needs jus_files and the Kakashi kit capture")
class RealDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.anims = T.load_anims("na_b_04")

    def test_kakashi_b_cells_and_header(self):
        an = self.anims[0x1E]
        rec = T.anim_record(an)
        self.assertEqual((rec["frames"], rec["rate"], rec["loop"], rec["texture"]), (29, 60, False, 0x60400))
        self.assertEqual([(s["cell"], s["start"]) for s in rec["cells"]],
                         [(75, 0), (76, 4), (77, 8), (78, 11), (79, 15), (80, 21), (81, 25)])
        self.assertTrue(self.anims[0x00].loop and self.anims[0x01].loop)

    def test_kakashi_b_capture_pins_0x1e_on_the_anchor_basis(self):
        c = T.check(self.anims, "kakashi-kit-2026-09-12/neutral_b", 0x1E, "leave_idle", {})
        self.assertEqual((c["agree"], c["checked_frames"], c["also_fits"]), (29, 29, []))
        self.assertEqual((c["end_hold"], c["stand_at"], c["state_return"]), (2, 2, 32))
        hit = [t for t in range(29) if len(T.predict(self.anims[0x1E], t, -1)) > 1]
        self.assertEqual(hit, [8, 9, 10])

    def test_specials_are_moves_rows_and_base_rows_gain_koma(self):
        doc = json.loads(T.OUT_JSON.read_text())
        k = doc["characters"]["kakashi"]
        rows = {(m["move"], m["koma"]): m for m in k["moves"]}
        x = rows[("X", 4)]
        self.assertEqual((x["anim"], x["archive"], x["strip"], x["check"]["anchor_rule"]),
                         ("0x29", "chr/na_b_04.aar", "x_beam_k4", "leave_idle"))
        self.assertEqual((x["check"]["agree"], x["check"]["checked_frames"]), (79, 79))
        self.assertEqual([c["pick"] for c in x["cells"]][:4], [0, 1, 2, 3])
        self.assertIsNone(rows[("B", None)]["koma"])
        self.assertNotIn("0x29", [r["anim"] for r in k["other"]])
        for aid in ("0x2b", "0x2c", "0x2d", "0x2e"):
            self.assertNotIn(aid, [r["anim"] for r in k["other"]])
        y = {(m["move"], m["koma"]): m for m in doc["characters"]["yusuke"]["moves"]}
        self.assertEqual({p["path"]: p["agree"] == p["checked_frames"] for p in y[("X", 6)]["plays"]},
                         {p: True for p in ("tap (level 1)", "hold 72 (level 1)", "hold 73 (level 2)",
                                            "hold 120 (level 2, charged pose)")})

    def test_eve_rows_follow_the_kit_and_the_set_koma(self):
        kit = json.loads((T.REPO / "docs" / "rebuild" / "characters" / "eve.kit.json").read_text())
        doc = json.loads(T.OUT_JSON.read_text())
        rows = {m["anim"]: m for m in doc["characters"]["eve"]["moves"]}
        for km in kit["moves"]:
            if km["slot"] == "ULTIMATE":
                continue   # no box capture reads anim 0x18 (the UA run logged bridge rows only)
            aid = f"0x{int(km['jus_anim'], 16):02x}"
            if km["slot"] == "DREAM":
                # Native DREAM carriage does not manufacture a measured capture.
                self.assertNotIn(aid, rows)
                self.assertIsNone(km["idle_return"])
                self.assertEqual(kit["grades"]["DREAM.idle_return"]["grade"], "TBD")
                self.assertTrue(km["boxes"])
                self.assertTrue(all("native_rect" in box and box["contact_delay"] is None
                                    for box in km["boxes"]))
                continue
            self.assertEqual(rows[aid]["move"], km["slot"], aid)
            self.assertIsNone(rows[aid]["koma"])
            self.assertEqual(rows[aid]["check"]["disagree_at"], [])
        sets = {(m["move"], m["koma"]): m for m in doc["characters"]["eve"]["moves"] if m["koma"] is not None}
        self.assertEqual({k: v["anim"] for k, v in sets.items()},
                         {("X", 4): "0x29", ("up X", 4): "0x2a", ("X", 5): "0x2b", ("up X", 5): "0x2c"})
        for ss in kit["special_sets"]:
            for km in ss["moves"]:
                if km.get("mash"):
                    row = sets[(km["slot"], ss["koma"])]
                    self.assertEqual((row["anim"], row["frames"]), (km["mash"]["anim"], km["mash"]["frames"]))
                    self.assertEqual(row["koma_archive"], f"chr/bc_b_01_{ss['koma']}.aar")
                if km["idle_return"] is not None and ss["koma"] == 4:
                    self.assertEqual(sets[(km["slot"], 4)]["check"]["state_return"], km["idle_return"])
        # a row that cannot show its anim says why; none of these is a plays/special row
        self.assertTrue(all("plays" not in m and "hits" not in m for m in doc["characters"]["eve"]["moves"]))

    def test_a_shifted_eve_anim_id_is_refused_by_the_build(self):
        rows = [(n, 0x1F if a == 0x1E else a, c, r, o) for n, a, c, r, o in T.MOVES["eve"]]
        old, T.MOVES["eve"] = T.MOVES["eve"], rows
        try:
            with self.assertRaises(SystemExit):
                T.build(selection("--char", "eve", "--chr-b", "37"))
        finally:
            T.MOVES["eve"] = old

    def test_yusuke_x_jumps_are_pinned_to_their_frame(self):
        # The held box (frames 4-35) and frames 64-87 differ by under 1 px. So
        # moving the switch while keeping the frames after it where they are
        # passes a 1 px check anywhere in s 26-36 (tap) or 60-79 (hold 72);
        # only the exact check pins it
        an = T.load_anims("yh_b_01")[0x2D]
        tap = T.load_special_capture(f"{T.C2}/H3/X_tap")
        h72 = T.load_special_capture(f"{T.C2}/H3/X_h72")
        for sw in (26, 31, 32, 33, 36):
            c = T.check_plays(an, tap, "leave_idle", [("play", 0, 0, sw), ("play", sw, 44 + sw, 64 - sw)])
            self.assertEqual(c["disagree_at"] == [], sw == 32, f"tap switch at s {sw}")
        for sw in (60, 70, 71, 72, 79):
            c = T.check_plays(an, h72, "leave_idle",
                              [("play", 0, 0, 4), ("hold", 4, sw, 4, 35), ("play", sw, 5 + sw, 103 - sw)])
            self.assertEqual(c["disagree_at"] == [], sw == 71, f"hold 72 switch at s {sw}")
        for to in (75, 76, 77):
            c = T.check_plays(an, tap, "leave_idle", [("play", 0, 0, 32), ("play", 32, to, 32)])
            self.assertEqual(c["disagree_at"] == [], to == 76, f"tap jump to frame {to}")

    def test_special_cells_with_no_strip_frame_say_why(self):
        doc = json.loads(T.OUT_JSON.read_text())
        missing = {}
        for char, c in doc["characters"].items():
            for m in c["moves"]:
                if "plays" not in m:
                    continue
                self.assertNotIn("texture_archive", m)
                self.assertEqual(m["koma_archive"], f"chr/{c['prefix']}_{m['koma']}.aar")
                for cell in m["cells"]:
                    if cell["pick"] is None:
                        self.assertTrue(cell.get("why"), f"{char} {m['move']} cell {cell['cell']}")
                        missing.setdefault((char, m["move"], m["koma"]), set()).add(cell["cell"])
        self.assertEqual(missing, {("yusuke", "up X", 6): {13, 20}, ("yusuke", "X", 4): {16},
                                   ("yusuke", "up X", 4): {13}, ("yusuke", "up X", 5): {13, 14}})

    def test_pass_two_rows(self):
        doc = json.loads(T.OUT_JSON.read_text())
        rows = {(c, m["move"], m["koma"]): m for c, d in doc["characters"].items() for m in d["moves"]}
        want = {("kakashi", "X", 5): ("0x2b", "x_raikiri_k5"), ("kakashi", "up X", 5): ("0x2c", "up_x_dogs_k5"),
                ("kakashi", "X", 6): ("0x2d", "x_chidori_k6"),
                ("kakashi", "up X", 6): ("0x2e", "up_x_mangekyou_k6"),
                ("yusuke", "X", 4): ("0x29", "x_spirit_gun_k4"),
                ("yusuke", "up X", 4): ("0x2a", "up_x_rei_kou_dan_k4"),
                ("yusuke", "X", 5): ("0x2b", "x_spirit_gun_k5"),
                ("yusuke", "up X", 5): ("0x2c", "up_x_rei_kou_dan_k5")}
        for key, (aid, strip) in want.items():
            m = rows[key]
            self.assertEqual((m["anim"], m["strip"], m["check"]["anchor_rule"]), (aid, strip, "leave_idle"))
            self.assertTrue(all(p["disagree_at"] == [] for p in m["plays"]), key)
        # C3 logs no P1 body box: state-only checks, and the grade says so
        for key in [k for k in want if k[0] == "kakashi"] + [("yusuke", "X", 4)]:
            self.assertEqual({p["checked_frames"] for p in rows[key]["plays"]}, {0}, key)
            self.assertIn("no body box read", rows[key]["grade"])
        self.assertEqual(rows[("kakashi", "up X", 6)]["check"]["state_return"], 195)
        for key in [("kakashi", "X", 5), ("kakashi", "X", 6), ("kakashi", "up X", 6), ("yusuke", "X", 5)]:
            self.assertIn("idle_return_why", rows[key], key)
        y5 = rows[("yusuke", "X", 5)]
        self.assertEqual({p["path"]: p["checked_frames"] for p in y5["plays"]},
                         {"tap (level 1)": 49, "hold 65 (level 1)": 93, "hold 66 (level 2)": 93,
                          "hold 120 (level 2)": 147, "hold 300 (level 2)": 327})

    def test_yusuke_5x_level_switches_are_pinned(self):
        # Level 1 resumes at anim frame 56 and level 2 at 92; the exact box
        # check refuses the other level's target and a switch one frame off
        an = T.load_anims("yh_b_01")[0x2B]
        h65 = T.load_special_capture(f"{T.C4}/Q/5X_h65")
        h66 = T.load_special_capture(f"{T.C4}/Q/5X_h66")
        def ok(cap, sw, t0, n):
            return T.check_plays(an, cap, "leave_idle", [("play", 0, 0, 4), ("hold", 4, sw, 4, 55),
                                                         ("play", sw, t0, n)], 1)["disagree_at"] == []
        self.assertTrue(ok(h65, 64, 56, 29))
        self.assertFalse(ok(h65, 64, 92, 28))
        self.assertTrue(ok(h66, 65, 92, 28))
        self.assertFalse(ok(h66, 65, 56, 29))
        self.assertFalse(ok(h66, 66, 92, 28))

    def test_a_special_off_frames_plus_3_needs_a_why(self):
        # Raikiri idles at +88 to +156 against a 229-frame anim: without a
        # reason, a generator would default it to a 232-frame dash
        strips = json.loads(T.SPECIAL_STRIPS.read_text())["characters"]
        spec = dict(next(x for x in T.SPECIALS["kakashi"] if (x["move"], x["koma"]) == ("X", 5)))
        del spec["idle_return_why"]
        with self.assertRaisesRegex(SystemExit, "needs an 'idle_return_why'"):
            T.special_row("kakashi", spec, self.anims, strips)

    def test_committed_json_matches_a_fresh_build(self):
        want = json.loads(T.OUT_JSON.read_text())
        self.assertEqual(json.loads(json.dumps(T.build())), want)


def selection(*argv):
    import argparse
    ap = argparse.ArgumentParser()
    T.char_args.add_arguments(ap)
    return T.char_args.select(ap.parse_args(argv))


def code_strings_naming_a_character(path, pattern=r"kakashi|yusuke"):
    """String literals outside docstrings that name a character: the roster
    belongs in decoder_roster.json, not in the decoder."""
    import ast
    tree = ast.parse(Path(path).read_text())
    docs = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
            and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs
            and re.search(pattern, n.value, re.I)]


@unittest.skipUnless(HAVE_ROM, "needs jus_files")
@unittest.skipUnless(HAVE_EVIDENCE, NEED_EVIDENCE)
class CharacterArgumentTest(unittest.TestCase):
    """The roster is an argument (tracker item jus-analysis-decoders-chr-arg-46dd)."""

    def test_the_decoder_names_no_character_in_code(self):
        self.assertEqual(code_strings_naming_a_character(SCRIPT), [])

    def test_check_passes_for_the_roster_each_roster_character_and_a_new_one(self):
        for argv in ([], ["--char", "kakashi"], ["--char", "yusuke"],
                     ["--char", "eve", "--chr-b", "37"]):
            self.assertEqual(T.main(["--check", *argv]), 0, argv)

    def test_a_wrong_chr_b_fails_the_check(self):
        for argv in (["--char", "eve", "--chr-b", "36", "--prefix", "bc_b_01"],
                     ["--char", "kakashi", "--chr-b", "24", "--prefix", "na_b_04"],
                     ["--char", "kakashi", "--chr-b", "32"]):
            with self.assertRaises(SystemExit, msg=argv):
                T.main(["--check", *argv])

    def test_a_stale_committed_entry_fails_the_check(self):
        doc = json.loads(T.OUT_JSON.read_text())
        doc["characters"]["yusuke"]["moves"][0]["frames"] += 1
        with tempfile.TemporaryDirectory() as d:
            stale = Path(d) / "anim-timing.json"
            stale.write_text(json.dumps(doc))
            self.assertEqual(T.main(["--check", "--out", str(stale), "--char", "yusuke"]), 1)
            self.assertEqual(T.main(["--check", "--out", str(stale), "--char", "kakashi"]), 0)
            self.assertEqual(T.main(["--check", "--out", str(stale)]), 1)

    def test_a_character_with_no_rows_decodes_to_states_and_other_only(self):
        self.assertNotIn("train", T.MOVES)
        sel = selection("--char", "train", "--chr-b", "38")
        train = T.build(sel)["characters"]["train"]
        self.assertEqual((train["chr_b"], train["prefix"], train["moves"]), (38, "bc_b_02", []))
        self.assertTrue(train["states"] and train["other"])

    def test_the_roster_built_from_arguments_is_the_committed_json(self):
        want = json.loads(T.OUT_JSON.read_text())["characters"]
        for char in ("kakashi", "yusuke"):
            sel = selection(
                "--char", char, "--chr-b", str(want[char]["chr_b"]), "--prefix", want[char]["prefix"])
            self.assertEqual(json.loads(json.dumps(T.build(sel)))["characters"][char], want[char])

    def test_writing_a_selection_over_the_committed_file_is_refused(self):
        with self.assertRaisesRegex(SystemExit, "--out"):
            T.main(["build", "--char", "eve", "--chr-b", "37"])


class CommittedJsonTest(unittest.TestCase):
    """Reads the committed JSON and doc only, so it runs without jus_files."""

    doc = json.loads(T.OUT_JSON.read_text())

    def test_every_move_off_frames_plus_3_says_why(self):
        for char, c in self.doc["characters"].items():
            for m in c["moves"]:
                if m.get("grade") == "static":
                    self.assertNotIn("check", m)
                    self.assertTrue(m.get("label_src"))
                    continue
                backs = {m["check"]["state_return"]} | {p["state_return"] for p in m.get("plays", [])}
                if backs != {m["frames"] + 3}:
                    self.assertTrue(m.get("idle_return_why"), f"{char} {m['move']} koma {m['koma']}: {backs}")

    def section_8(self):
        md = (T.REPO / "docs" / "rebuild" / "anim-timing.md").read_text()
        return md[md.index("## 8. Specials"):md.index("### 8.1")]

    def test_section_8_hand_tables_match_the_json(self):
        # §8's special table sits outside the generated markers, so the doc
        # test can't see it drift (it once said +133 where the JSON says +94).
        # Each row names every path's idle return, and nothing else
        seen, problems = section_8_problems(self.section_8(), self.doc)
        self.assertEqual(problems, [])
        self.assertEqual(seen, {(ch, m["move"], m["koma"]) for ch, c in self.doc["characters"].items()
                                for m in c["moves"] if "plays" in m})

    def test_section_8_reads_press_offsets_apart_from_idle_returns(self):
        self.assertEqual(section_8_offsets("fires at press + 95, press+30; idle at +96 (tap), + 88 (hold 60)"),
                         ([96, 88], [95, 30]))

    def test_section_8_guard_catches_a_wrong_return(self):
        sec = self.section_8()
        self.assertIn("+94 (hold 60)", sec)
        _, problems = section_8_problems(sec.replace("+94 (hold 60)", "+133 (hold 60)"), self.doc)
        self.assertEqual(len(problems), 1)
        self.assertIn("kakashi X 6", problems[0])
        _, problems = section_8_problems(sec.replace("+94 (hold 60)", "+ 133 (hold 60)"), self.doc)
        self.assertEqual(len(problems), 1)


def section_8_offsets(text):
    """(idle returns, press offsets) a §8 cell names: every `+N`, spaced or
    not. One written `press + N` is a press offset; any other is a return."""
    idle, press = [], []
    for pre, n in re.findall(r"(press\s*)?\+\s*(\d+)", text):
        (press if pre else idle).append(int(n))
    return idle, press


def section_8_problems(sec, doc):
    """(rows seen, mismatches) between §8's hand tables and the JSON."""
    rows = {(ch, m["move"], m["koma"]): m for ch, c in doc["characters"].items()
            for m in c["moves"] if "plays" in m}
    seen, problems = set(), []
    for line in sec.splitlines():
        cols = [x.strip() for x in line.strip("|").split("|")]
        if len(cols) != 4 or not cols[0].startswith(("Kakashi `", "Yusuke `")) or "koma" not in cols[2]:
            continue
        char = cols[0].split()[0].lower()
        move = cols[0].split("`")[1]
        koma = int(cols[2].rsplit("koma", 1)[1])
        m = rows[(char, move, koma)]
        aid, frames, rate, loop = [x.strip() for x in cols[1].split(",")]
        if (aid, int(frames), int(rate), loop.split()[0]) != (m["anim"], m["frames"], m["rate"],
                                                             "loops" if m["loop"] else "holds"):
            problems.append(f"{char} {move} {koma}: anim, frames, rate, loop")
        if cols[2].split("`")[1] != f"0x{m['texture']:06x}":
            problems.append(f"{char} {move} {koma}: texture")
        named = set(section_8_offsets(cols[3])[0])
        backs = {p["state_return"] for p in m["plays"]}
        if named != backs:
            problems.append(f"{char} {move} {koma}: §8 names {sorted(named)}, the idle returns are {sorted(backs)}")
        seen.add((char, move, koma))
    return seen, problems


class CellsMeasuredTest(unittest.TestCase):
    """A move's cells are graded measured only when a committed capture read them live."""
    CELLS = [{"cell": 71, "start": 0, "len": 4}, {"cell": 72, "start": 4, "len": 3},
             {"cell": 73, "start": 7, "len": 20}]

    def caps(self, entry):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name) / "cap"
        d.mkdir()
        (d / "checks.json").write_text(json.dumps({"anim": {"B": entry}}))
        return Path(tmp.name)

    def entry(self, **kw):
        return {"matches_anim_timing_static": True, "state9_cells": [[0, 71], [4, 72], [7, 73]], **kw}

    def test_full_agreement_is_measured(self):
        cm = {"capture": "cap", "key": "B"}
        self.assertEqual(T.cells_grade("x", self.CELLS, 27, cm, self.caps(self.entry())), "cells measured")

    def test_a_partial_span_says_how_far(self):
        cm = {"capture": "cap", "key": "B", "upto": 5}
        e = self.entry(state9_cells=[[0, 71], [4, 72]])
        self.assertEqual(T.cells_grade("x", self.CELLS, 27, cm, self.caps(e)),
                         "cells measured to anim frame 4")

    def test_a_capture_that_disagrees_with_the_decoded_cells_is_refused(self):
        cm = {"capture": "cap", "key": "B"}
        for bad in (self.entry(matches_anim_timing_static=False),
                    self.entry(state9_cells=[[0, 71], [4, 99], [7, 73]]),
                    self.entry(state9_cells=[[0, 71], [4, 72]])):
            with self.assertRaisesRegex(SystemExit, "does not measure"):
                T.cells_grade("x", self.CELLS, 27, cm, self.caps(bad))

    def test_committed_yusuke_rows_cite_the_xcancel_capture(self):
        rows = {m["move"]: m["grade"] for m in
                json.loads(T.OUT_JSON.read_text())["characters"]["yusuke"]["moves"]}
        self.assertTrue(rows["B"].endswith("cells measured"))
        self.assertTrue(rows["Y"].endswith("cells measured"))
        self.assertTrue(rows["air Y"].endswith("cells measured to anim frame 47"))
        self.assertTrue(rows["side B"].endswith("cells static"))


class DocTablesTest(unittest.TestCase):
    def test_doc_tables_are_the_generated_ones(self):
        doc = (T.REPO / "docs" / "rebuild" / "anim-timing.md").read_text()
        data = json.loads(T.OUT_JSON.read_text())
        for char in T.CHARS:
            self.assertIn(T.render_tables(data, char), doc, f"regenerate the {char} tables")


if __name__ == "__main__":
    unittest.main()

@unittest.skipUnless(HAVE_EVIDENCE, NEED_EVIDENCE)
class YusukeSideYFirstPhaseTest(unittest.TestCase):
    def test_existing_captures_pin_native_first_phase_without_an_added_pause(self):
        row=next(r for r in T.MOVES['yusuke'] if r[0]=='side Y')
        self.assertEqual(row[1],0x21)
        self.assertNotIn('pause',row[4])
        self.assertEqual(row[4]['upto'],51)
        anims=T.load_anims('yh_b_01')
        for path in [row[2]]+row[4]['also']:
            out=T.check(anims,path,0x21,row[3],row[4])
            self.assertEqual((out['agree'],out['checked_frames'],out['disagree_at']),(51,51,[]))
            self.assertEqual((out['state_end'],out['state_return']),({'at':53,'to':0},53))
            self.assertEqual(out['also_fits'],[])
