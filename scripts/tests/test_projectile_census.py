import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "emu"))
import projectile_census as pc  # noqa: E402


def make_result(rows):
    """Build a minimal census result dict with the given elem rows.

    Each row is (idx, word_0x18_or_None, stale_check, stale_reason).
    """
    records = []
    for idx, w18, stale_check, stale_reason in rows:
        records.append({
            "idx": idx,
            "elem": {
                "word_0x18": w18,
                "elem_check": stale_check,
                "elem_check_reason": stale_reason,
            },
        })
    return {
        "meta": {
            "self_validation": {
                "elem_checks_total": len(rows),
                "elem_checks_failed": sum(
                    1 for _, _, c, _ in rows if c != "pass"),
                "elem_checks_passed": sum(
                    1 for _, _, c, _ in rows if c == "pass"),
                "elem_checks_failed_indices": [
                    idx for idx, _, c, _ in rows if c != "pass"],
            },
        },
        "colprm_records": records,
    }


class TestRecheckResult(unittest.TestCase):
    def test_flips_stale_fixed_word_fails_to_pass_under_nonzero_rule(self):
        # Old rule: "expected 0x000281FF" -- these all failed even though
        # +0x18 was nonzero. New rule: nonzero passes.
        result = make_result([
            (0, 0x00021000, "fail",
             "+0x18 == 0x00021000, expected 0x000281FF"),
            (1, 0x0001A000, "fail",
             "+0x18 == 0x0001A000, expected 0x000281FF"),
            (70, 0x000281FF, "pass", None),
        ])
        out = pc.recheck_result(result)
        checks = {r["idx"]: r["elem"]["elem_check"]
                 for r in out["colprm_records"]}
        self.assertEqual(checks, {0: "pass", 1: "pass", 70: "pass"})
        sv = out["meta"]["self_validation"]
        self.assertEqual(sv["elem_checks_total"], 3)
        self.assertEqual(sv["elem_checks_failed"], 0)
        self.assertEqual(sv["elem_checks_passed"], 3)
        self.assertEqual(sv["elem_checks_failed_indices"], [])

    def test_zero_word_still_fails_under_nonzero_rule(self):
        result = make_result([
            (5, 0x00000000, "fail", "+0x18 == 0x00000000, expected 0x000281FF"),
        ])
        out = pc.recheck_result(result)
        elem = out["colprm_records"][0]["elem"]
        self.assertEqual(elem["elem_check"], "fail")
        self.assertIn("expected nonzero", elem["elem_check_reason"])
        sv = out["meta"]["self_validation"]
        self.assertEqual(sv["elem_checks_failed"], 1)
        self.assertEqual(sv["elem_checks_failed_indices"], [5])

    def test_missing_word_0x18_leaves_original_reason(self):
        result = make_result([
            (9, None, "fail", "+0x5C is not a RAM pointer"),
        ])
        out = pc.recheck_result(result)
        elem = out["colprm_records"][0]["elem"]
        self.assertEqual(elem["elem_check"], "fail")
        self.assertEqual(elem["elem_check_reason"], "+0x5C is not a RAM pointer")


class TestClassifyEntryPtr(unittest.TestCase):
    def test_builtin_id_4_predicted_bit0_is_1(self):
        entry_ptr = pc.BUILTIN_TABLE_BASE + 4 * pc.ENTRY_STRIDE
        id_kind, id_ = pc.classify_entry_ptr(entry_ptr, authored_base=0)
        self.assertEqual((id_kind, id_), ("builtin", 4))
        self.assertEqual(pc.predicted_bit0_for(id_kind, id_, entry_0x08=0), 1)

    def test_builtin_id_0_predicted_bit0_is_0(self):
        entry_ptr = pc.BUILTIN_TABLE_BASE + 0 * pc.ENTRY_STRIDE
        id_kind, id_ = pc.classify_entry_ptr(entry_ptr, authored_base=0)
        self.assertEqual((id_kind, id_), ("builtin", 0))
        self.assertEqual(pc.predicted_bit0_for(id_kind, id_, entry_0x08=0xFF), 0)

    def test_authored_with_bit5_set_predicted_bit0_is_1(self):
        authored_base = 0x02100000
        entry_ptr = authored_base + 3 * pc.ENTRY_STRIDE
        id_kind, id_ = pc.classify_entry_ptr(entry_ptr, authored_base)
        self.assertEqual((id_kind, id_), ("authored", 0x100 + 3))
        self.assertEqual(
            pc.predicted_bit0_for(id_kind, id_, entry_0x08=0x20), 1)

    def test_authored_with_bit5_clear_predicted_bit0_is_0(self):
        authored_base = 0x02100000
        entry_ptr = authored_base + 3 * pc.ENTRY_STRIDE
        id_kind, id_ = pc.classify_entry_ptr(entry_ptr, authored_base)
        self.assertEqual(
            pc.predicted_bit0_for(id_kind, id_, entry_0x08=0x00), 0)

    def test_unaligned_pointer_is_unknown_with_null_id_and_predicted(self):
        authored_base = 0x02100000
        entry_ptr = authored_base + 3 * pc.ENTRY_STRIDE + 1  # off-stride
        id_kind, id_ = pc.classify_entry_ptr(entry_ptr, authored_base)
        self.assertEqual((id_kind, id_), ("unknown", None))
        self.assertIsNone(pc.predicted_bit0_for(id_kind, id_, entry_0x08=0x20))

    def test_null_entry_ptr_is_unknown(self):
        id_kind, id_ = pc.classify_entry_ptr(0, authored_base=0x02100000)
        self.assertEqual((id_kind, id_), ("unknown", None))

    def test_no_authored_base_and_not_builtin_is_unknown(self):
        id_kind, id_ = pc.classify_entry_ptr(0x02155555, authored_base=0)
        self.assertEqual((id_kind, id_), ("unknown", None))


if __name__ == "__main__":
    unittest.main()
