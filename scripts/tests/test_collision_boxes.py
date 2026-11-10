import importlib.util
import json
import os
import sys
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis", "collision_boxes.py")
SPEC = importlib.util.spec_from_file_location("collision_boxes", SCRIPT)
C = importlib.util.module_from_spec(SPEC)
sys.modules["collision_boxes"] = C
SPEC.loader.exec_module(C)

HAVE_ROM = C.at.mr.CHRARC.exists()
COMMITTED = json.loads(C.OUT_JSON.read_text())["characters"]


def guard(name):
    chans = COMMITTED[name]["animations"]["03"]["channels"]
    return {c["channel"]: c for c in chans}


class FakeAnim:
    frames = 12

    def __init__(self, tracks):
        self.tracks = tracks

    def keys(self, prop):
        return self.tracks.get(prop, [])


class AnimationTest(unittest.TestCase):
    def test_rect_channels_only(self):
        an = FakeAnim({"CollisionType0": [(0, 0)], "CollisionRect0": [(0, (-1, -2, 3, 0))],
                       "CollisionType1": [(0, 2)], "CollisionEnable1": [(0, 1)]})
        rec = C.animation(an)
        self.assertEqual(rec["frames"], 12)
        self.assertEqual([c["channel"] for c in rec["channels"]], [0])
        self.assertEqual(rec["channels"][0]["rect"], [[0, [-1, -2, 3, 0]]])
        self.assertEqual(rec["channels"][0]["enable"], [])

    def test_no_rect_channel_is_no_record(self):
        self.assertIsNone(C.animation(FakeAnim({"BoundsIndex": [(0, 4)]})))


class CommittedTest(unittest.TestCase):
    def test_guard_animation_carries_a_type_2_box_for_each_character(self):
        want = {"yusuke": [-15, -47, 14, 0], "kakashi": [-19, -43, 12, 0], "jotaro": [-16, -61, 20, 0]}
        for name, rect in want.items():
            g = guard(name)
            self.assertEqual(g[1]["type"], [[0, 2]], name)
            self.assertEqual(g[1]["rect"], [[0, rect]], name)
            self.assertEqual(g[0]["type"], [[0, 0]], name)

    def test_body_rects_of_the_guard_animation(self):
        want = {"yusuke": [-11, -45, 7, 0], "kakashi": [-12, -40, 10, 0], "jotaro": [-8, -54, 9, 0]}
        for name, rect in want.items():
            self.assertEqual(guard(name)[0]["rect"], [[0, rect]], name)

    @unittest.skipUnless(HAVE_ROM, "needs the ROM extract (jus_files)")
    def test_committed_file_is_fresh(self):
        text = json.dumps(C.build(), indent=None, separators=(",", ":")) + "\n"
        self.assertEqual(C.OUT_JSON.read_text(), text)


if __name__ == "__main__":
    unittest.main()
