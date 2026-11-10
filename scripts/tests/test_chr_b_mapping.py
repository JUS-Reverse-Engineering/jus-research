import importlib.util
import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from extract_character_data import CHARACTER_MAP  # noqa: E402


class TestChrBMapping(unittest.TestCase):
    def test_runtime_gate_decks_use_koma_ability_ids(self):
        expected = {
            12: "Luffy",
            14: "Sanji",
            15: "Nami",
            17: "Franky",
            28: "Jotaro",
            36: "Kenshin",
            46: "Lenalee",
            48: "Don Patch",
            62: "Raoh",
            66: "Edajima",
        }

        for index, name in expected.items():
            self.assertEqual(CHARACTER_MAP[index][2], name, index)

    def test_one_piece_files_follow_the_measured_and_sequential_join(self):
        # 17 and 18 are measured by the 2026-10-13 stored-value capture (C-UA-Yusuke S0);
        # 13, 14, 16, 19 were pinned by the E0 roster join (2026-10-18).
        expected = {
            13: ("op_b_02", "Zoro"),
            14: ("op_b_03", "Sanji"),
            16: ("op_b_05", "Robin"),
            17: ("op_b_06", "Franky"),
            18: ("op_b_07", "Gear 2 Luffy"),
            19: ("op_b_08", "PCT Nami"),
        }
        for index, (prefix, name) in expected.items():
            self.assertEqual(CHARACTER_MAP[index][1:3], (prefix, name), index)
        self.assertEqual(len({CHARACTER_MAP[i][1] for i in range(12, 20)}), 8)

    def test_suspect_and_measured_sets_pin_the_one_piece_join(self):
        # move_records.py is a script, not a package: load it by path (as the table tests do).
        here = os.path.dirname(__file__)
        spec = importlib.util.spec_from_file_location(
            "move_records", os.path.join(here, "..", "analysis", "move_records.py"))
        move_records = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(move_records)
        suspect = move_records.SUSPECT_CHRB
        # E0 roster pin (2026-10-18) measured every row but the unobserved komamen 71/72.
        self.assertEqual(suspect, {71, 72})
        for index in (13, 14, 16, 17, 18, 19):
            self.assertNotIn(index, suspect, index)
            self.assertIn(index, move_records.MEASURED_CHRB_FILE, index)


if __name__ == "__main__":
    unittest.main()
