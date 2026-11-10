#!/usr/bin/env python3
"""find_pos_array must return every survivor, never silently pick one.

Regression test for the tiebreak that cost m01 its entire movement dataset and
killed one arm each in m03 and m06: the function used to collapse a tie by
taking the highest address, which returns a stale ring copy whenever the live
block is missing from the candidate list.
"""
import os
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import capture_feel as CF  # noqa: E402

BASE = CF.MAIN_RAM[0]
SIZE = 0x4000


def make_ram():
    return bytearray(SIZE)


def put_pair_block(ram, off, x1, y, x2, preceded_by_pointer=True):
    """Write a block matching the position-array signature.

    Two coordinate pairs 0x40 apart, equal Y, different X, each duplicated
    at +8. Optionally preceded at -4 by a main-RAM pointer.
    """
    def w(o, v):
        struct.pack_into("<i", ram, o, v)
    if preceded_by_pointer:
        w(off - 4, BASE + 0x1000)
    else:
        w(off - 4, 0x12345678)          # not a main-RAM address
    w(off, x1); w(off + 4, y)
    w(off + 8, x1); w(off + 12, y)
    o2 = off + CF.POS_STRIDE
    w(o2, x2); w(o2 + 4, y)
    w(o2 + 8, x2); w(o2 + 12, y)


class TestFindPosArray(unittest.TestCase):
    def test_returns_all_pointer_preceded_survivors_sorted(self):
        ram = make_ram()
        # three plausible blocks, all pointer-preceded: a ring plus a live one
        for i, off in enumerate((0x400, 0x480, 0x500)):
            put_pair_block(ram, off, 100000 + i * 256, 172031, 147456)
        got = CF.find_pos_array(bytes(ram))
        self.assertEqual(got, [BASE + 0x400, BASE + 0x480, BASE + 0x500])
        self.assertEqual(got, sorted(got), "must be sorted")

    def test_does_not_collapse_to_the_highest(self):
        """The old bug: several survivors reduced to max(), which arms a corpse."""
        ram = make_ram()
        for off in (0x400, 0x480, 0x500):
            put_pair_block(ram, off, 100000, 172031, 147456)
        got = CF.find_pos_array(bytes(ram))
        self.assertGreater(len(got), 1,
                           "a tie must be reported, not silently resolved")
        self.assertNotEqual(got, [max(got)])

    def test_pointer_filter_still_applies(self):
        ram = make_ram()
        put_pair_block(ram, 0x400, 100000, 172031, 147456,
                       preceded_by_pointer=True)
        put_pair_block(ram, 0x800, 110000, 172031, 147456,
                       preceded_by_pointer=False)
        got = CF.find_pos_array(bytes(ram))
        self.assertIn(BASE + 0x400, got)
        self.assertNotIn(BASE + 0x800, got)

    def test_falls_back_to_raw_hits_when_none_are_pointer_preceded(self):
        ram = make_ram()
        put_pair_block(ram, 0x400, 100000, 172031, 147456,
                       preceded_by_pointer=False)
        got = CF.find_pos_array(bytes(ram))
        self.assertEqual(got, [BASE + 0x400])

    def test_single_candidate_is_returned_plainly(self):
        ram = make_ram()
        put_pair_block(ram, 0x400, 100000, 172031, 147456)
        self.assertEqual(CF.find_pos_array(bytes(ram)), [BASE + 0x400])


if __name__ == "__main__":
    unittest.main(verbosity=2)
