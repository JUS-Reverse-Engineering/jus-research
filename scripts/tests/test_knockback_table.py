"""knockback_table.py: unit tests for the arithmetic, the pinned code facts, and
the hard gate.

The gate (GateTest) fails, not skips, when jus_files is missing: every joined
measured case must pass, and the committed docs/rebuild/knockback-table.json
must equal a fresh build.
Run: python3 -m unittest scripts/tests/test_knockback_table.py
"""
import importlib.util
import os
import sys
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis", "knockback_table.py")
SPEC = importlib.util.spec_from_file_location("knockback_table", SCRIPT)
K = importlib.util.module_from_spec(SPEC)
sys.modules["knockback_table"] = K
SPEC.loader.exec_module(K)

HAVE_DATA = K.mr.CHRARC.exists() and K.ARM9.exists() and K.C.OV6.exists()
NEED = "jus_files is missing: run `git submodule update --init` (the gate never skips)"


def rec(kind=3, typ=1, dmg=8, kbx=5, kby=0, mask=0):
    b = bytearray(20)
    b[0], b[1], b[4] = kind, typ, dmg
    b[8:12] = mask.to_bytes(4, "little")
    b[0xC], b[0xD] = kbx & 0xFF, kby & 0xFF
    return bytes(b)


class StagedTest(unittest.TestCase):
    def test_full_hp_x_is_kbx_times_128(self):
        self.assertEqual(K.staged(5, 0, 1), (640, 0))
        self.assertEqual(K.staged(-10, 0, 2), (-1280, 0))

    def test_y_is_kby_times_minus_158_then_223_over_256_with_floor(self):
        # Kakashi air B rec 11 (kbY -13): measured +1789 (kakashi.md)
        self.assertEqual(K.staged(5, -13, 1)[1], 1789)
        # Kakashi up Y hit 1 (kbY 8): measured -1102, the floor of -1101.06
        self.assertEqual(K.staged(10, 8, 2)[1], -1102)

    def test_band_multiplier_only_on_type_6(self):
        self.assertEqual(K.staged(25, 6, 6, band=0x180), (4800, -1239))
        self.assertEqual(K.staged(25, 6, 2, band=0x180), (3200, -826))

    def test_weight_bits_scale_type_6_only_heavy_first(self):
        self.assertEqual(K.staged(25, 0, 6, weight=0x80)[0], 1600)
        self.assertEqual(K.staged(25, 0, 6, weight=0x8000)[0], 4800)
        self.assertEqual(K.staged(25, 0, 6, weight=0x8080)[0], 2400)
        self.assertEqual(K.staged(25, 0, 1, weight=0x8080)[0], 3200)

    def test_crit_doubles_before_weight(self):
        self.assertEqual(K.staged(5, -13, 1, crit=True), (1280, 3578))
        # the order shows on an odd value: band x1.5, kbY 1 -> y -237 before x223.
        # crit then light: -474 - (-237) = -237 -> floor(-237 * 223 / 256) = -207;
        # light then crit would give (-237 + 119) * 2 = -236 -> -206
        self.assertEqual(K.staged(0, 1, 6, band=0x180, crit=True, weight=0x80)[1], -207)
        # crit then heavy: -474 + (-237) = -711 -> -620; heavy first gives -712 -> -621
        self.assertEqual(K.staged(0, 1, 6, band=0x180, crit=True, weight=0x8000)[1], -620)


class ImpulseTest(unittest.TestCase):
    def test_y_through_72_over_100_truncates_toward_zero(self):
        self.assertEqual(K.impulse(-3200, -826), (-3200, -594))
        self.assertEqual(K.impulse(0, -2478), (0, -1784))
        self.assertEqual(K.impulse(0, 1789), (0, 1288))

    def test_grounded_victim_drops_the_downward_part(self):
        # kakashi-2026-09-03/airB.jsonl.gz frames 54-55: staged (-640, +1789) on a
        # standing victim, next frame v = (-560, 0); the floor clamp keeps vy <= 0
        self.assertEqual(K.first_frame(-640, 1288, ground=True), (-560, 0))
        self.assertEqual(K.first_frame(-640, 1288), (-560, 1289))
        self.assertEqual(K.first_frame(-3200, -594, ground=True), (-2800, -534))

    def test_first_frame_drag_then_gravity(self):
        # physics.md 4.2: Kenshin X finisher on Luffy, pre-hit drift -123
        self.assertEqual(K.first_frame(-3200, -594, vx0=-123), (-2907, -534))
        self.assertEqual(K.first_frame(-9600, -1784, vx0=-123), (-8507, -1687))


class FlagTest(unittest.TestCase):
    def test_flags_follow_the_element_tables(self):
        tables = ([0x04000000, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0x01000000] + [0] * 19,
                  [0] * 9 + [0x4] + [0] * 22,
                  [0] * 32)
        self.assertEqual(K.element_flags(0, tables), {"zero": False, "override": False, "sign": "facing"})
        self.assertEqual(K.element_flags(1 << 12, tables)["zero"], True)
        self.assertEqual(K.element_flags(1 << 0, tables)["override"], True)
        self.assertEqual(K.element_flags(1 << 9, tables)["sign"], "relative")


class RowTest(unittest.TestCase):
    TABLES = ([0x04000000] + [0] * 11 + [0x01000000] + [0] * 19, [0] * 9 + [0x4] + [0] * 22, [0] * 32)
    ENTRY = {1: (0x0215B6A0, True), 2: (0x0215B6A0, True), 4: (0x0215B7CC, False), 6: (0x0215BA40, True)}

    def test_zeroed_record_has_no_impulse(self):
        r = K.record_row(3, rec(typ=2, kbx=0, kby=15, mask=1 << 12), self.TABLES, self.ENTRY)
        self.assertEqual(r["staged"], [0, 0])
        self.assertEqual(r["impulse"], [0, 0])

    def test_entry_without_impulse(self):
        r = K.record_row(0, rec(typ=4, kbx=5), self.TABLES, self.ENTRY)
        self.assertEqual(r["staged"], [640, 0])
        self.assertIsNone(r["impulse"])

    def test_row_carries_air_and_ground_first_frames(self):
        r = K.record_row(0, rec(typ=1, kbx=5, kby=-13), self.TABLES, self.ENTRY)
        self.assertEqual(r["first_frame_air"], [560, 1289])
        self.assertEqual(r["first_frame_ground"], [560, 0])

    def test_launcher_carries_band_rows(self):
        r = K.record_row(20, rec(typ=6, kbx=25, kby=6), self.TABLES, self.ENTRY)
        self.assertEqual(r["band"], {"x1": [3200, -826], "x1.5": [4800, -1239],
                                     "x2": [6400, -1652], "x3": [9600, -2478]})
        self.assertNotIn("band", K.record_row(0, rec(), self.TABLES, self.ENTRY))


class ParseTest(unittest.TestCase):
    def test_pairs(self):
        self.assertEqual(K.pairs("(−640, **+1789**)"), [(-640, 1789)])
        self.assertEqual(K.pairs("(−384, −689), (−1024, −2065)"), [(-384, -689), (-1024, -2065)])
        self.assertEqual(K.pairs("(−1024, 0) both"), [(-1024, 0)])
        self.assertEqual(K.pairs("same as `Y`"), [])


class CodeFactsTest(unittest.TestCase):
    def setUp(self):
        if not HAVE_DATA:
            self.fail(NEED)

    def test_pinned(self):
        f = K.code_facts()
        self.assertEqual(f["record_offsets"], {"type": 1, "kbX": 0xC, "kbY": 0xD})
        # the table reads records through mr.decode_record: it must read those offsets
        d = K.mr.decode_record(rec(typ=6, kbx=-3, kby=7))
        self.assertEqual((d["type"], d["kbX"], d["kbY"]), (6, -3, 7))
        self.assertEqual(f["kbx_shift"], 7)
        self.assertEqual(f["kby_scale"], -158)
        self.assertEqual(f["y_scale"], 223)
        self.assertEqual(f["band_table"], [0x300, 0x200, 0x180, 0x100, 0x100])
        # x: one register (r1 = 100) is both the multiplier and the divisor at 0x0215AF8C
        self.assertEqual(f["ov6_x_scale"], [100, 100])
        self.assertEqual(f["ov6_y_scale"], [72, 100])
        self.assertEqual(f["zero_bits"], [12])
        self.assertEqual(f["override_bits"], [0])
        self.assertEqual(f["relative_sign_bits"], [9])
        self.assertEqual(f["entry"][1], [0x0215B6A0, True])
        self.assertEqual(f["entry"][5], [0x0215B870, True])
        self.assertEqual(f["entry"][6], [0x0215BA40, True])
        self.assertEqual(f["entry"][4], [0x0215B7CC, False])
        self.assertEqual(f["entry"][8], [0x0215B68C, False])

    def test_entries_install_the_live_handlers(self):
        # physics.md: obj+0xFC read live as 0x0215B720 (types 1/2/7),
        # 0x0215B910 (5), 0x0215BAB8 (6); each entry stores that word itself
        f = K.code_facts()
        self.assertEqual(f["installs"][1], 0x0215B720)
        self.assertEqual(f["installs"][7], 0x0215B720)
        self.assertEqual(f["installs"][5], 0x0215B910)
        self.assertEqual(f["installs"][6], 0x0215BAB8)


class GateTest(unittest.TestCase):
    @unittest.skipUnless(K.RR7.exists() and K.KAKASHI_AIRB.exists(), "needs capture evidence that is not part of this repository")
    def test_gate(self):
        if not HAVE_DATA:
            self.fail(NEED)
        table = K.build()
        cases = K.gate(table)
        miss = [c for c in cases if c["result"] == "MISS"]
        self.assertFalse(miss, "\n".join(f"{c['case']}: {c['detail']}" for c in miss))
        self.assertGreaterEqual(sum(c["result"] == "PASS" for c in cases), 85)
        kinds = {c["basis"] for c in cases}
        self.assertLessEqual({"record set", "capture", "field-matched record, anim-keyed"}, kinds)
        self.assertEqual(K.OUT.read_text(encoding="utf-8"), K.dump(table),
                         "docs/rebuild/knockback-table.json is stale: run build")


if __name__ == "__main__":
    unittest.main()
