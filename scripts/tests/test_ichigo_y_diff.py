import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "emu"))
import ichigo_y_diff as d  # noqa: E402


def blob(words):
    """Little-endian bytes for a list of 32-bit words."""
    out = bytearray()
    for w in words:
        out += w.to_bytes(4, "little")
    return bytes(out)


class TestPointerWords(unittest.TestCase):
    def test_ram_range_word_is_a_pointer_word(self):
        blobs = {"a": blob([0x0221A000, 0x00000005]),
                 "b": blob([0x0221B000, 0x00000005])}
        self.assertEqual(d.pointer_word_offsets(blobs), [0x00])

    def test_word_below_ram_low_is_not_a_pointer(self):
        blobs = {"a": blob([0x01FFFFFF]), "b": blob([0x01FFFFFF])}
        self.assertEqual(d.pointer_word_offsets(blobs), [])

    def test_word_at_or_above_ram_high_is_not_a_pointer(self):
        blobs = {"a": blob([0x02400000]), "b": blob([0x02400000])}
        self.assertEqual(d.pointer_word_offsets(blobs), [])

    def test_pointer_in_only_one_capture_still_marks_the_word(self):
        blobs = {"a": blob([0x0221A000]), "b": blob([0x00000000])}
        self.assertEqual(d.pointer_word_offsets(blobs), [0x00])


class TestDiffStructure(unittest.TestCase):
    def test_pointer_words_are_reported_separately_not_as_byte_diffs(self):
        blobs = {"a": blob([0x0221A000, 0x11223344]),
                 "b": blob([0x0221B000, 0x11223344])}
        out = d.diff_structure(blobs)
        self.assertEqual([p["offset"] for p in out["pointer_words"]], [0x00])
        self.assertFalse(out["pointer_words"][0]["same_target"])
        self.assertEqual(out["differing_offsets"], [])
        self.assertTrue(out["identical_after_masking"])

    def test_same_pointer_target_is_marked_same(self):
        blobs = {"a": blob([0x0221A000]), "b": blob([0x0221A000])}
        out = d.diff_structure(blobs)
        self.assertTrue(out["pointer_words"][0]["same_target"])

    def test_differing_non_pointer_bytes_are_listed_with_per_state_values(self):
        blobs = {"a": blob([0x11223344]), "b": blob([0x11223399])}
        out = d.diff_structure(blobs)
        self.assertEqual([o["offset"] for o in out["differing_offsets"]], [0x00])
        self.assertEqual(out["differing_offsets"][0]["values"],
                         {"a": 0x44, "b": 0x99})
        self.assertFalse(out["identical_after_masking"])

    def test_identical_blobs_have_no_differing_offsets(self):
        blobs = {"a": blob([0x11223344]), "b": blob([0x11223344])}
        out = d.diff_structure(blobs)
        self.assertEqual(out["differing_offsets"], [])
        self.assertTrue(out["identical_after_masking"])

    def test_excluded_offsets_are_skipped_and_reported(self):
        blobs = {"a": blob([0x11223344]), "b": blob([0x99887766])}
        out = d.diff_structure(blobs, excluded={0x00: "position",
                                                0x01: "position"})
        self.assertEqual([o["offset"] for o in out["differing_offsets"]],
                         [0x02, 0x03])
        self.assertEqual(out["excluded"],
                         [{"offset": 0x00, "reason": "position"},
                          {"offset": 0x01, "reason": "position"}])

    def test_short_blob_is_diffed_over_the_common_length_only(self):
        blobs = {"a": blob([0x11223344, 0x55667788]), "b": blob([0x11223344])}
        out = d.diff_structure(blobs)
        self.assertEqual(out["length"], 4)
        self.assertEqual(out["differing_offsets"], [])
        self.assertEqual(out["length_note"], {"a": 8, "b": 4})

    def test_compared_surface_counts_only_informative_bytes(self):
        # +0x00..+0x03 is a pointer word, +0x04..+0x07 is excluded, so four
        # bytes are actually compared, of which two are nonzero somewhere.
        blobs = {"a": blob([0x0221A000, 0xFFFFFFFF, 0x00002211]),
                 "b": blob([0x0221A000, 0xFFFFFFFF, 0x00002211])}
        excluded = {o: "excluded" for o in range(0x04, 0x08)}
        out = d.diff_structure(blobs, excluded=excluded)
        self.assertEqual(out["compared_bytes"], 4)
        self.assertEqual(out["nonzero_compared_bytes"], 2)

    def test_single_capture_is_trivially_identical(self):
        out = d.diff_structure({"a": blob([0x11223344])})
        self.assertTrue(out["identical_after_masking"])
        self.assertEqual(out["differing_offsets"], [])


class TestDerivedChecks(unittest.TestCase):
    def node_cap(self, id_, node26):
        node = bytearray(0x2C)
        node[0x26] = node26
        return {"spawned": True, "meta": {},
                "nodes": [{"bytes": bytes(node).hex(), "id": id_,
                           "entry_bytes": "00" * 0x14}]}

    def test_node_0x26_matches_id_low_byte(self):
        caps = {"a": self.node_cap(264, 0x08), "b": self.node_cap(269, 0x0D)}
        out = d.check_node_0x26_vs_id(caps)
        self.assertTrue(out["holds"])
        self.assertEqual(out["exceptions"], [])

    def test_node_0x26_mismatch_is_reported(self):
        caps = {"a": self.node_cap(264, 0x09)}
        out = d.check_node_0x26_vs_id(caps)
        self.assertFalse(out["holds"])
        self.assertEqual(out["exceptions"][0]["slot"], "a")

    def pos_cap(self, dx, dy, sx, sy):
        pos = bytearray(0x40)
        pos[0x24:0x26] = dx.to_bytes(2, "little", signed=True)
        pos[0x26:0x28] = dy.to_bytes(2, "little", signed=True)
        return {"spawned": True, "meta": {},
                "position_element": {"bytes": bytes(pos).hex()},
                "velocity": {"samples": [{"dx": sx, "dy": sy}]}}

    def test_pos_0x24_word_pair_matches_measured_delta(self):
        caps = {"a": self.pos_cap(-962, 0, -962, 0)}
        out = d.check_pos_velocity_words(caps)
        self.assertTrue(out["holds"])

    def test_pos_velocity_word_mismatch_is_reported(self):
        caps = {"a": self.pos_cap(-962, 0, 677, -753)}
        out = d.check_pos_velocity_words(caps)
        self.assertFalse(out["holds"])
        self.assertEqual(out["exceptions"][0]["slot"], "a")


class TestCaptureCollection(unittest.TestCase):
    def test_only_spawned_captures_are_diffed(self):
        caps = {
            "a": {"spawned": True,
                  "element": {"bytes": blob([0x11223344]).hex()}},
            "b": {"spawned": False},
        }
        blobs = d.collect_blobs(caps, "element")
        self.assertEqual(list(blobs), ["a"])

    def test_node_blobs_come_from_the_first_node(self):
        caps = {"a": {"spawned": True,
                      "nodes": [{"bytes": blob([0x1]).hex()},
                                {"bytes": blob([0x2]).hex()}]}}
        self.assertEqual(d.collect_blobs(caps, "node0"),
                         {"a": blob([0x1])})

    def test_entry_blobs_come_from_the_first_node_with_entry_bytes(self):
        caps = {"a": {"spawned": True,
                      "nodes": [{"bytes": blob([0x1]).hex(),
                                 "entry_bytes": None},
                                {"bytes": blob([0x2]).hex(),
                                 "entry_bytes": blob([0xAB]).hex()}]}}
        self.assertEqual(d.collect_blobs(caps, "entry"),
                         {"a": blob([0xAB])})


if __name__ == "__main__":
    unittest.main()
