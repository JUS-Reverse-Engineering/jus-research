"""chr_natures.py: the B/C nature byte offsets, the synthetic table build, the
pinned rows of the real chr_b.bin (Eve 37, Kakashi 23, Yusuke 32), and the
freshness of the committed docs/rebuild/chr-natures.{json,md}.

The real-data tests fail, not skip, when jus_files/ripped_jus_files/bin/chr_b.bin is
absent (the gate never skips). The committed-table pins and the synthetic tests need no ROM.
Run: python3 -m unittest scripts/tests/test_chr_natures.py
"""
import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(ROOT, "scripts", "analysis", "chr_natures.py")
SPEC = importlib.util.spec_from_file_location("chr_natures", SCRIPT)
M = importlib.util.module_from_spec(SPEC)
sys.modules["chr_natures"] = M
SPEC.loader.exec_module(M)

HAVE_CHR_B = M.CHR_B.exists()
NEED = "jus_files is missing (chr_b.bin): run `git submodule update --init` (the gate never skips)"


def committed():
    with open(M.OUT, encoding="utf-8") as fh:
        return json.load(fh)


def row(table, index):
    return next(c for c in table["characters"] if c["chr_b"] == index)


class OffsetTest(unittest.TestCase):
    def test_b_and_c_offsets_per_size(self):
        # arm9 0x02077C0C: char+0x14 = chr_b[0x10+(size-4)*4+2], char+0x15 = chr_b[...+3]
        self.assertEqual(M.slot_offset(4, "B"), 0x12)
        self.assertEqual(M.slot_offset(4, "C"), 0x13)
        self.assertEqual(M.slot_offset(5, "B"), 0x16)
        self.assertEqual(M.slot_offset(5, "C"), 0x17)
        self.assertEqual(M.slot_offset(8, "B"), 0x22)
        self.assertEqual(M.slot_offset(8, "C"), 0x23)

    def test_sizes_outside_4_to_8_are_refused(self):
        for size in (3, 9):
            with self.assertRaises(ValueError):
                M.slot_offset(size, "B")

    def test_stride_is_60(self):
        self.assertEqual(M.STRIDE, 60)


class SyntheticBuildTest(unittest.TestCase):
    def test_build_reads_base_and_each_size_slot(self):
        rec0 = bytes(range(60))                # byte i = i, so every offset is its own value
        rec1 = bytes([0xFF]) * 60
        table = M.build_table(rec0 + rec1)
        self.assertEqual(len(table["characters"]), 2)
        c0 = row(table, 0)
        self.assertEqual(c0["base"], 0)
        self.assertEqual(c0["by_size"]["4"], {"B": 0x12, "C": 0x13})
        self.assertEqual(c0["by_size"]["5"], {"B": 0x16, "C": 0x17})
        self.assertEqual(c0["by_size"]["8"], {"B": 0x22, "C": 0x23})
        self.assertEqual(sorted(c0["by_size"]), ["4", "5", "6", "7", "8"])
        self.assertEqual(c0["raw"], rec0.hex())
        c1 = row(table, 1)
        self.assertEqual(c1["base"], 0xFF)
        self.assertEqual(c1["by_size"]["4"], {"B": 0xFF, "C": 0xFF})

    def test_a_partial_record_is_refused(self):
        with self.assertRaises(ValueError):
            M.build_table(bytes(59))


class CommittedTableTest(unittest.TestCase):
    """The committed table pins the values the exporter reads, with no ROM needed."""

    def test_committed_files_exist(self):
        self.assertTrue(M.OUT.exists())
        self.assertTrue(M.OUT_MD.exists())

    def test_eve_37_sizes_4_and_5_are_knowledge(self):
        c = row(committed(), 37)
        self.assertEqual(c["base"], 1)
        for size in ("4", "5"):
            self.assertEqual(c["by_size"][size], {"B": 1, "C": 1}, size)

    def test_kakashi_23_set_sizes_are_knowledge(self):
        c = row(committed(), 23)
        for size in ("4", "5", "6"):
            self.assertEqual(c["by_size"][size], {"B": 1, "C": 1}, size)

    @unittest.skipUnless((M.REPO / "docs" / "research" / "feel-captures").exists(), "capture evidence is not part of this repository")

    def test_eve_capture_is_recorded_and_exists(self):
        cap = [c for c in committed()["captured"] if c["chr_b"] == 37]
        self.assertEqual(len(cap), 1)
        self.assertTrue((M.REPO / cap[0]["file"]).exists(), cap[0]["file"])

    def test_yusuke_32_is_power_everywhere(self):
        c = row(committed(), 32)
        self.assertEqual(c["base"], 0)
        for size in ("4", "5", "6", "7", "8"):
            self.assertEqual(c["by_size"][size], {"B": 0, "C": 0}, size)


class RealDataTest(unittest.TestCase):
    def setUp(self):
        if not HAVE_CHR_B:
            self.fail(NEED)

    def test_real_table_has_74_characters(self):
        self.assertEqual(len(M.build()["characters"]), 74)

    def test_real_table_matches_committed_files(self):
        table = M.build()
        self.assertEqual(M.OUT.read_text(encoding="utf-8"), M.dump(table))
        self.assertEqual(M.OUT_MD.read_text(encoding="utf-8"), M.render_md(table))

    def test_check_command_is_fresh(self):
        self.assertEqual(M.main(["check"]), 0)


if __name__ == "__main__":
    unittest.main()
