import importlib.util
import os
import struct
import sys
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis", "sfx_render.py")
SPEC = importlib.util.spec_from_file_location("sfx_render", SCRIPT)
S = importlib.util.module_from_spec(SPEC)
sys.modules["sfx_render"] = S
SPEC.loader.exec_module(S)

HAVE_SDAT = S.SDAT.exists()
TARGETS = ["SE_HIT", "SE_HVYHIT", "SE_SLASH", "SE_HVYSLASH", "SE_KABOOM", "SE_GUARD", "SE_SOUSAI",
           "SE_DASH", "SE_DRON", "SE_FURI", "SE_HVYFURI", "SE_KO", "SE_CHRCHNG"]


def fake_player(code: bytes):
    """Player over `code` with one PCM instrument: a 4000-sample 0.5 square wave."""
    nd = {"type": 1, "swav": 0, "swar": 0, "key": 60, "adsr": (127, 127, 127, 127), "pan": 64}
    bank = [(1, [(0, 127, nd)])]
    wave_ = {"kind": 1, "rate": 32768, "loop": None, "samples": [0.5, -0.5] * 2000}
    return S.Player(code, 0, 0, bank, lambda slot, idx: wave_, 127)


class EnvelopeRateTest(unittest.TestCase):
    def test_attack_rate(self):
        self.assertEqual(S.attack_rate(127), 0)       # instant
        self.assertEqual(S.attack_rate(0x6D), 0x8F)
        self.assertEqual(S.attack_rate(0), 255)

    def test_fall_rate(self):
        self.assertEqual(S.fall_rate(127), 0xFFFF)
        self.assertEqual(S.fall_rate(126), 0x3C00)
        self.assertEqual(S.fall_rate(10), 21)
        self.assertEqual(S.fall_rate(100), 0x1E00 // 26)


class AdpcmTest(unittest.TestCase):
    def test_first_nibbles(self):
        # header: pred 0, index 0. Byte 0x87, low nibble first:
        #   7: step 7 -> 7>>3 + 7>>2 + 7>>1 + 7 = 11; index 0 + 8 = 8 (step 16)
        #   8: sign only -> -(16>>3) = -2 -> 9
        sw = struct.pack("<BBHHHI", 2, 0, 16000, 0, 1, 1) + struct.pack("<hBB", 0, 0, 0) + bytes([0x87, 0, 0, 0])
        w = S.decode_swav(sw)
        self.assertEqual(w["kind"], 2)
        self.assertAlmostEqual(w["samples"][0] * 32768, 11)
        self.assertAlmostEqual(w["samples"][1] * 32768, 9)
        self.assertIsNone(w["loop"])


class SequencerTest(unittest.TestCase):
    def test_loop_count_repeats_the_body(self):
        # program 0; loop 2 { note 60 vel 127 len 1 }; end
        p = fake_player(bytes([0x81, 0x00, 0xD4, 0x02, 0x3C, 0x7F, 0x01, 0xFC, 0xFF]))
        p.render(1.0)
        self.assertEqual([(n["key"], n["length"]) for n in p.notes], [(60, 1), (60, 1)])
        self.assertEqual(p.problems, [])

    def test_random_prefix_takes_the_midpoint(self):
        # random pitch bend in [-50, 100] -> 25; then a note
        p = fake_player(bytes([0xA0, 0xC4]) + struct.pack("<hh", -50, 100) + bytes([0x3C, 0x7F, 0x01, 0xFF]))
        p.render(0.5)
        self.assertEqual(p.tracks[0].bend, 25)

    def test_false_if_skips_one_command(self):
        # var0 = 0; if var0 >= 1 -> end (skipped); note; end
        code = bytes([0xB0, 0x00, 0x00, 0x00, 0xB9, 0x00, 0x01, 0x00, 0xA2, 0xFF, 0x3C, 0x7F, 0x01, 0xFF])
        p = fake_player(code)
        p.render(0.5)
        self.assertEqual(len(p.notes), 1)

    def test_zero_length_note_plays_to_the_sample_end(self):
        p = fake_player(bytes([0x3C, 0x7F, 0x00, 0xFF]))
        left, _ = p.render(1.0)
        st = S.stats(left, left)
        self.assertAlmostEqual(st["audible_seconds"], 4000 / 32768, places=2)


@unittest.skipUnless(HAVE_SDAT, "needs jus_files/ripped_jus_files/sound/JS2_sound.sdat")
class RealSdatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sdat = S.Sdat()
        cls.battle = cls.sdat.seqarc_index("SEQ_BATTLE")

    def row(self, name):
        names = self.sdat.d["symb"]["seqarc_seqs"][self.battle]
        return S.render_one(self.sdat, self.battle, names.index(name), None)

    def test_se_hit(self):
        r = self.row("SE_HIT")
        self.assertEqual((r["index"], r["bank_name"]), (0x0E, "BANK_SE_BATTLE"))
        self.assertEqual([(n["key"], n["velocity"], n["length"], n["swav"]) for n in r["notes"]],
                         [(57, 105, 24, 18)])
        self.assertFalse(r["silent"])
        self.assertTrue(0.15 < r["audible_seconds"] < 0.4, r["audible_seconds"])

    def test_targets_render_clean(self):
        for name in TARGETS:
            r = self.row(name)
            self.assertEqual(r["problems"], [], name)
            self.assertFalse(r["silent"], name)
            self.assertFalse(r["hit_cap"], name)

    def test_loop_body_is_not_misread_as_a_note(self):
        # SE_BURNING loops `rest 5; if var27 >= 1: release, end` 11 times after one note.
        self.assertEqual([(n["key"], n["velocity"]) for n in self.row("SE_BURNING")["notes"]], [(60, 127)])

    def test_kakashi_archive(self):
        sa = self.sdat.seqarc_index("SEQ_NA_B_04")
        self.assertEqual(sa, 0x17A)
        r = S.render_one(self.sdat, sa, 0, None)
        self.assertEqual(r["name"], "SE_CHR_KAKASHI_IN")
        self.assertFalse(r["silent"])


if __name__ == "__main__":
    unittest.main()
