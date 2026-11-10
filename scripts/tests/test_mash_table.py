"""mash_table.py: the field decode, the pinned code facts, the ground-truth rows
(Eve k4/k5, Kakashi side Y, Train side Y / air Y) and the freshness of the
committed docs/rebuild/mash-table.{json,md}.

The data tests fail, not skip, when jus_files is missing.
Run: python3 -m unittest scripts/tests/test_mash_table.py
"""
import copy
import importlib.util
import json
import os
import sys
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis", "mash_table.py")
SPEC = importlib.util.spec_from_file_location("mash_table", SCRIPT)
M = importlib.util.module_from_spec(SPEC)
sys.modules["mash_table"] = M
SPEC.loader.exec_module(M)

HAVE_DATA = M.mr.CHRARC.exists() and M.C.OV6.exists()
NEED = "jus_files is missing: run `git submodule update --init` (the gate never skips)"

_TABLE = None


def table():
    global _TABLE
    if _TABLE is None:
        _TABLE = M.build()
    return _TABLE


def anim(prefix, aid):
    char = next(c for c in table()["characters"] if c["prefix"] == prefix)
    return next(a for a in char["anims"] if a["anim"] == f"0x{aid:02x}")


class NeedsData(unittest.TestCase):
    def setUp(self):
        if not HAVE_DATA:
            self.fail(NEED)


class DecodeTest(NeedsData):
    """Every field gets its own byte value, so a swapped or shifted offset shows."""

    def test_sub0_each_field_reads_its_own_byte(self):
        facts = M.code_facts()
        raw = bytes([0, 0, 5, 3, 1, 9, 7, 0])         # marker 5, limit 3, button 1, window 9, threshold 7
        ev = M.decode_event(0, raw, facts, {5: 50})
        self.assertEqual((ev["marker"], ev["limit"], ev["button_idx"], ev["window"], ev["threshold"]),
                         (5, 3, 1, 9, 7))
        self.assertEqual((ev["marker_frame"], ev["button"], ev["button_mask"]), (50, "Y", 0x100))

    def test_sub0_limit_is_signed(self):
        ev = M.decode_event(0, bytes([0, 0, 1, 0xFF, 2, 12, 2, 0]), M.code_facts(), {1: 11})
        self.assertEqual((ev["limit"], ev["limit_unbounded"]), (-1, True))

    def test_sub0_only_limit_minus_one_is_unlimited(self):
        # 0 is a real limit (reached on the first evaluation), not unlimited; -2 is not unlimited either
        facts = M.code_facts()
        for raw_limit, unbounded in ((0, False), (1, False), (-2, False), (-1, True)):
            ev = M.decode_event(0, bytes([0, 0, 1, raw_limit & 0xFF, 2, 12, 2, 0]), facts, {1: 11})
            self.assertEqual((ev["limit"], ev["limit_unbounded"]), (raw_limit, unbounded), raw_limit)

    def test_sub18_each_field_reads_its_own_byte(self):
        raw = bytes([18, 0, 4, 7, 2, 6, 1, 0])        # false 4, true 7, button 2, window 6, threshold 1
        ev = M.decode_event(18, raw, M.code_facts(), {4: 38, 7: 56})
        self.assertEqual((ev["marker_false"], ev["marker_true"], ev["button_idx"], ev["window"],
                          ev["threshold"]), (4, 7, 2, 6, 1))
        self.assertEqual((ev["marker_false_frame"], ev["marker_true_frame"], ev["button"]), (38, 56, "X"))

    def test_k4_bytes(self):
        raw = bytes.fromhex("00 00 01 02 02 0c 02 00")
        ev = M.decode_event(0, raw, M.code_facts(), {0: 0, 1: 11})
        self.assertEqual({k: ev[k] for k in ("marker", "limit", "button_idx", "window", "threshold")},
                         {"marker": 1, "limit": 2, "button_idx": 2, "window": 12, "threshold": 2})
        self.assertEqual(ev["marker_frame"], 11)

    def test_sub1_unused_tier_has_no_frame(self):
        raw = bytes.fromhex("01 00 02 01 02 00 03 00 1e 00 04 00 5a 00 00 00 00 00")
        ev = M.decode_event(1, raw, M.code_facts(), {3: 93, 4: 128})
        self.assertEqual((ev["hold_1"], ev["marker_1"], ev["marker_1_frame"]), (30, 3, 93))
        self.assertEqual((ev["hold_2"], ev["marker_2"], ev["marker_2_frame"]), (90, 4, 128))
        self.assertEqual((ev["hold_3"], ev["marker_3_frame"]), (0, None))


class BranchEventsTest(NeedsData):
    def test_taikoubou_contact_and_deck_branches_resolve_markers(self):
        row = anim("hs_b_01", 0x2D)
        self.assertTrue(row["input_conditional"])
        self.assertEqual([(e["sub"], e["frame"]) for e in row["events"]],
                         [(5, 43), (5, 81), (2, 104), (14, 109)])
        arm, disarm, _, deck = row["events"]
        self.assertEqual((arm["kind"], arm["marker"], arm["marker_frame"], arm["disarm"]),
                         ("contact_wait", 1, 81, False))
        self.assertEqual((disarm["marker"], disarm["marker_frame"], disarm["disarm"]),
                         (-1, None, True))
        self.assertEqual((deck["kind"], deck["query"], deck["tiers"]),
                         ("deck_count_branch", 0x42, [
                             {"min_count": 11, "marker": 4, "frame": 177},
                             {"min_count": 7, "marker": 3, "frame": 143}]))
        self.assertEqual(row["ends"], [79, 141, 175, 209])

    def test_kazuki_deck_branch_is_conditional_without_pad_events(self):
        char = next(c for c in table()["characters"] if c["prefix"] == "bu_b_01")
        rows = [a for a in char["anims"] if a["anim"] == "0x2d"]
        self.assertTrue(rows, "Kazuki's sub14-only anim must be scanned")
        row, = rows
        self.assertTrue(row["input_conditional"])
        deck, = [e for e in row["events"] if e["sub"] == 14]
        self.assertEqual([t["min_count"] for t in deck["tiers"]], [11, 7])
        self.assertTrue(all(t["frame"] is not None for t in deck["tiers"]))


class CodeFactsTest(NeedsData):
    def test_pinned(self):
        f = M.code_facts()
        self.assertEqual(f["op0_handler"], "0x02156188")
        self.assertEqual(f["sub_handler"], {"0": "0x02155A04", "1": "0x02155B04",
                                            "18": "0x02155A84", "23": "0x02155BA0",
                                            "2": "0x021559C0", "3": "0x02155CAC", "4": "0x02155D00",
                                           "5": "0x02155D3C", "9": "0x02155DB8", "14": "0x02155E90",
                                            "19": "0x021560EC", "20": "0x021560F8"})
        self.assertEqual((f["op_index_byte"], f["sub_index_byte"]), (1, 0))
        self.assertEqual((f["op_table_pool"], f["sub_table_literal"], f["button_table_literal"]),
                         ("0x0217200C", "0x02172084", "0x02171098"))
        self.assertEqual(f["button_mask"], [0x80, 0x100, 0x40, 0x1000])
        self.assertEqual(f["button_held_mask"], [0x400, 0x800, 0x200, 0x2000])
        self.assertEqual(f["sub1_slot_handler"], "0x021561E4")
        self.assertEqual(f["counter_offset"], 0xA2)

    def test_layout(self):
        lay = M.code_facts()["layout"]
        self.assertEqual(lay["0"], {"marker": ["ldrb", 2], "limit": ["ldrsb", 3], "button": ["ldrb", 4],
                                    "window": ["ldrb", 5], "threshold": ["ldrb", 6]})
        self.assertEqual(lay["18"], {"marker_false": ["ldrb", 2], "marker_true": ["ldrb", 3],
                                     "button": ["ldrb", 4], "window": ["ldrb", 5], "threshold": ["ldrb", 6]})
        self.assertEqual(lay["1"]["hold_3"], ["ldrh", 0x10])
        self.assertEqual(M.code_facts()["direction_marker_table"], ["ldrb", 3])


class NewKindsDecodeTest(NeedsData):
    """Subs 2, 3, 4, 19, 20 and sub 1 without tiers: each field gets its own byte value."""

    def test_sub2_loop_fields_and_unlimited(self):
        facts = M.code_facts()
        ev = M.decode_event(2, bytes([2, 0, 8, 3]), facts, {8: 62})
        self.assertEqual((ev["kind"], ev["marker"], ev["marker_frame"], ev["limit"], ev["limit_unbounded"]),
                         ("loop", 8, 62, 3, False))
        ev = M.decode_event(2, bytes([2, 0, 8, 0xFF]), facts, {8: 62})
        self.assertEqual((ev["limit"], ev["limit_unbounded"]), (-1, True))

    def test_sub3_arm_and_disarm(self):
        facts = M.code_facts()
        arm = M.decode_event(3, bytes([3, 0, 9, 0]), facts, {9: 66})
        self.assertEqual((arm["kind"], arm["marker"], arm["marker_frame"], arm["disarm"]),
                         ("ground_wait", 9, 66, False))
        off = M.decode_event(3, bytes([3, 0, 0xFF, 0]), facts, {9: 66})
        self.assertEqual((off["marker"], off["marker_frame"], off["disarm"]), (-1, None, True))

    def test_sub4_reads_its_own_byte(self):
        ev = M.decode_event(4, bytes([4, 0, 7, 1]), M.code_facts(), {7: 40})
        self.assertEqual((ev["kind"], ev["marker"], ev["marker_frame"], ev["disarm"]), ("air_wait", 7, 40, False))

    def test_sub19_store_value_is_signed(self):
        facts = M.code_facts()
        self.assertEqual(M.decode_event(19, bytes([19, 0, 3, 0]), facts, {})["value"], 3)
        self.assertEqual(M.decode_event(19, bytes([19, 0, 0xFF, 0]), facts, {})["value"], -1)

    def test_sub20_reads_no_byte_and_lists_the_anim_markers(self):
        ev = M.decode_event(20, bytes([20, 0, 0, 0]), M.code_facts(), {0: 0, 1: 12, 3: 59})
        self.assertEqual((ev["kind"], ev["targets"]), ("stored_jump", {"0": 0, "1": 12, "3": 59}))

    def test_sub1_without_tiers_is_hold_release(self):
        facts = M.code_facts()
        plain = M.decode_event(1, bytes.fromhex("01 00 03 00 05" + " 00" * 13), facts, {5: 49})
        self.assertEqual((plain["kind"], plain["button"], plain["button_idx"], plain["marker_default_frame"]),
                         ("hold_release", "SELECT", 3, 49))
        tiered = M.decode_event(1, bytes.fromhex("01 00 02 01 02 00 03 00 1e 00 04 00 5a 00 00 00 00 00"),
                                facts, {3: 93, 4: 128})
        self.assertEqual(tiered["kind"], "hold_tiers")
        # any one tier makes it tiered (hold_3 alone, hold_2 alone)
        for at in (8, 12, 16):
            raw = bytearray(18)
            raw[0], raw[2], raw[4], raw[at] = 1, 2, 5, 9
            self.assertEqual(M.decode_event(1, bytes(raw), facts, {})["kind"], "hold_tiers", at)

    def test_button_names(self):
        self.assertEqual(M.BUTTON_NAMES, {0: "B", 1: "Y", 2: "X", 3: "SELECT"})
        facts = M.code_facts()
        for idx, name, mask in ((0, "B", 0x80), (3, "SELECT", 0x1000)):
            ev = M.decode_event(0, bytes([0, 0, 1, 2, idx, 6, 1, 0]), facts, {1: 11})
            self.assertEqual((ev["button"], ev["button_mask"]), (name, mask))


class NewKindsCodeFactsTest(NeedsData):
    def test_handlers_and_slots(self):
        f = M.code_facts()
        self.assertEqual(f["kind_handler"], {"2": "0x021562D8", "4": "0x02156358"})
        self.assertEqual(f["slot_for_kind"], [6, 5, 0, 0, 0, 1, 2, 2])      # table 0x021710A8
        self.assertEqual((f["grounded_test"], f["grounded_offset"], f["grounded_mask"]),
                         ("0x021562E8", 0x78, 0x02))
        self.assertEqual(f["store_offset"], 0xA3)
        self.assertEqual(f["end_key"], {"op": 3, "sub": 1, "sub_table": "0x02172000",
                                        "handler": "0x0215693C", "flag_offset": 0x90,
                                        "flag": "0x10000000"})

    def test_layout_of_the_new_kinds(self):
        lay = M.code_facts()["layout"]
        self.assertEqual(lay["2"], {"marker": ["ldrb", 2], "limit": ["ldrsb", 3]})
        self.assertEqual((lay["3"], lay["4"], lay["19"]), ({"marker": ["ldrsb", 2]}, {"marker": ["ldrsb", 2]},
                                                           {"value": ["ldrsb", 2]}))
        self.assertEqual(lay["20"], {})
        sites = M.code_facts()["sites"]
        self.assertEqual((sites["2"]["marker"], sites["2"]["limit"]), ("0x021559DC", "0x021559C8"))
        self.assertEqual((sites["3"]["marker"], sites["4"]["marker"], sites["19"]["value"]),
                         ("0x02155CB0", "0x02155D04", "0x021560EC"))

    def test_pinned_code_words(self):
        w = M.code_facts()["words"]
        self.assertEqual(w["0x021560EC"], "0xE1D110D2")        # ldrsb r1,[r1,#2]
        self.assertEqual(w["0x021560F0"], "0xE5C010A3")        # strb r1,[r0,#0xa3]
        self.assertEqual(w["0x021560F8"], "0xE92D4010")        # sub 20 entry: push {r4, lr}
        self.assertEqual(w["0x0215611C"], "0xE5C400A3")        # strb r0,[r4,#0xa3]  (reset to -1)
        self.assertEqual(w["0x021562F0"], "0xE3100002")        # tst r0,#2: the grounded bit
        self.assertEqual(w["0x02155CB0"], "0xE1D120D2")        # sub 3: ldrsb r2,[r1,#2]
        self.assertEqual(w["0x02155D04"], "0xE1D120D2")        # sub 4: ldrsb r2,[r1,#2]
        self.assertEqual(w["0x021559C8"], "0xE1D410D3")        # sub 2: ldrsb r1,[r4,#3] (limit)
        self.assertEqual(w["0x021559DC"], "0xE5D42002")        # sub 2: ldrb r2,[r4,#2] (marker)
        self.assertEqual(w["0x02156954"], "0xE3800201")        # orr r0,r0,#0x10000000 (end key)

    def test_kinds_queue_the_expected_slots(self):
        w = M.code_facts()["words"]
        self.assertEqual(w["0x02155CB4"], "0xE3A01002")        # sub 3 queues kind 2
        self.assertEqual(w["0x02155D08"], "0xE3A01004")        # sub 4 queues kind 4


class GroundTruthTest(NeedsData):
    def test_eve_k4_x(self):
        a = anim("bc_b_01", 0x29)
        self.assertEqual((a["move"], a["move_id"], a["mash"]), ("X (koma 4)", 13, True))
        (e,) = a["events"]
        self.assertEqual((e["frame"], e["sub"], e["raw"]), (23, 0, "00 00 01 02 02 0c 02 00"))
        self.assertEqual((e["limit"], e["window"], e["threshold"], e["button"], e["button_mask"]),
                         (2, 12, 2, "X", 0x40))
        self.assertEqual((e["marker"], e["marker_frame"]), (1, 11))
        self.assertEqual({c["source"] for c in a["confirmed"]}, {"capture", "owner", "guide"})

    def test_eve_k5_up_x(self):
        a = anim("bc_b_01", 0x2C)
        self.assertEqual((a["move"], a["mash"]), ("up X (koma 5)", True))
        evs = [e for e in a["events"] if e["sub"] == 18]
        self.assertEqual([e["frame"] for e in evs], [19, 25, 31, 37, 43, 49])
        self.assertTrue(all(e["window"] == 6 and e["threshold"] == 1 and e["button"] == "X" for e in evs))
        self.assertEqual([e["marker_true"] for e in evs], [1, 2, 3, 4, 5, 7])
        self.assertEqual([e["marker_false"] for e in evs], [7, 7, 7, 7, 7, 4])
        self.assertEqual([e["marker_true_frame"] for e in evs], [20, 26, 32, 38, 44, 56])
        self.assertEqual(evs[0]["marker_false_frame"], 56)       # the unmashed path
        self.assertEqual(evs[-1]["marker_false_frame"], 38)      # f49 unpressed loop-back

    def test_eve_k5_ground_wait_and_loop(self):
        # sub 3 at f62 arms Marker 9 (f66), sub 2 at f65 loops to Marker 8 (f62) unlimited, sub 3 at
        # f66 disarms: the hop's wait (findings: the 2 to 5 tick idle residual)
        a = anim("bc_b_01", 0x2C)
        self.assertEqual((a["markers"]["8"], a["markers"]["9"]), (62, 66))
        wait = [(e["frame"], e["sub"], e["raw"]) for e in a["events"] if e["sub"] in (2, 3)]
        self.assertEqual(wait, [(62, 3, "03 00 09 00"), (65, 2, "02 00 08 ff"), (66, 3, "03 00 ff 00")])
        arm, loop, disarm = (e for e in a["events"] if e["sub"] in (2, 3))
        self.assertEqual((arm["marker_frame"], arm["disarm"]), (66, False))
        self.assertEqual((loop["marker_frame"], loop["limit"], loop["limit_unbounded"]), (62, -1, True))
        self.assertEqual((disarm["marker_frame"], disarm["disarm"]), (None, True))
        self.assertTrue(a["mash"] and a["ground_wait"] and a["input_conditional"])
        self.assertEqual(a["ends"], [])

    def test_kakashi_side_y(self):
        a = anim("na_b_04", 0x21)
        self.assertEqual((a["move"], a["mash"]), ("side Y", True))
        (e,) = a["events"]
        self.assertEqual((e["frame"], e["sub"], e["button"], e["limit"], e["window"], e["threshold"],
                          e["marker_frame"]), (35, 0, "Y", 2, 14, 2, 21))
        self.assertEqual({c["source"] for c in a["confirmed"]}, {"owner", "capture"})

    def test_kakashi_x_is_hold_not_mash(self):
        a = anim("na_b_04", 0x2B)
        self.assertFalse(a["mash"])
        self.assertTrue(a["input_conditional"])
        self.assertEqual([(e["sub"], e["kind"]) for e in a["events"]],
                         [(1, "hold_tiers"), (2, "loop")] + [(5, "contact_wait")] * 5)
        self.assertEqual(a["events"][1]["marker_frame"], 44)

    def test_train_forward_y_and_air_y_are_flagged(self):
        char = next(c for c in table()["characters"] if c["prefix"] == "bc_b_02")
        self.assertEqual([n["name"] for n in char["names"]], ["Train"])
        self.assertEqual(char["names"][0]["chr_b"], 38)
        for aid, move in ((0x21, "side Y"), (0x27, "air Y")):
            a = anim("bc_b_02", aid)
            self.assertEqual((a["move"], a["mash"]), (move, True))
            evs = [e for e in a["events"] if e["sub"] == 0]
            self.assertEqual([e["frame"] for e in evs], {0x21: [18, 69], 0x27: [18, 79]}[aid])
            self.assertTrue(all(e["button"] == "Y" and e["window"] == 6 and e["threshold"] == 1
                                for e in evs))
            self.assertEqual({c["source"] for c in a["confirmed"]}, {"owner", "guide"})


class StoreConsumeTest(NeedsData):
    """Train's Ultimate Action stores 3 at f49 of anim 0x18; the Y moves consume at the top."""

    def test_train_store(self):
        a = anim("bc_b_02", 0x18)
        (e,) = a["events"]
        self.assertEqual((e["frame"], e["sub"], e["kind"], e["raw"], e["value"]),
                         (49, 19, "store", "13 00 03 00", 3))
        self.assertEqual((a["move_id"], a["mash"], a["ends"], a["markers"]), (11, False, [], {}))

    def test_train_stored_jump(self):
        want = {0x21: (4, {"0": 0, "1": 12, "3": 59, "4": 63}, [49]),
                0x23: (7, {"0": 0, "1": 11, "3": 60, "4": 62}, [43]),
                0x27: (6, {"0": 0, "1": 12, "3": 68, "4": 73, "5": 133}, [58, 119])}
        for aid, (frame, targets, ends) in want.items():
            a = anim("bc_b_02", aid)
            (e,) = [e for e in a["events"] if e["sub"] == 20]
            self.assertEqual((e["frame"], e["kind"], e["raw"], e["targets"]),
                             (frame, "stored_jump", "14 00 00 00", targets), hex(aid))
            self.assertEqual(a["ends"], ends, hex(aid))

    def test_train_air_y_arms_marker_5_and_disarms_at_f133(self):
        waits = [(e["frame"], e["marker_frame"], e["disarm"]) for e in anim("bc_b_02", 0x27)["events"]
                 if e["sub"] == 3]
        self.assertEqual(waits, [(32, 133, False), (93, 133, False), (133, None, True)])

    def test_yusuke_ultimate_hold_release_and_tiers(self):
        a = anim("yh_b_01", 0x18)
        hold = next(e for e in a["events"] if e["sub"] == 1)
        self.assertEqual((hold["kind"], hold["frame"], hold["button"], hold["marker_default"],
                          hold["marker_default_frame"]), ("hold_release", 4, "SELECT", 5, 49))
        self.assertEqual([(e["frame"], e["value"]) for e in a["events"] if e["sub"] == 19], [(8, 1), (24, 3)])
        self.assertEqual(a["ends"], [43, 57])


class CountsTest(NeedsData):
    """Cast-wide counts, measured from the bytes."""

    def test_headline_is_unchanged(self):
        rows = M.summary(table())
        self.assertEqual(len(rows), 74)
        self.assertEqual(sum(r["mash"] for r in rows), 98)
        self.assertEqual(sum(1 for r in rows if r["mash"]), 53)

    def test_input_conditional_keys_the_other_count(self):
        # an anim with only loop / wait / store events is neither mash nor "other"
        for c in table()["characters"]:
            for a in c["anims"]:
                self.assertEqual(a["input_conditional"], any(e["sub"] in M.INPUT_CONDITIONAL_SUBS
                                                             for e in a["events"]))
        eve = anim("bc_b_01", 0x2B)
        self.assertTrue(eve["input_conditional"])
        self.assertFalse(eve["mash"])
        self.assertEqual([(e["sub"], e["frame"]) for e in eve["events"]],
                         [(2, 40), (5, 42), (5, 86)])

    def test_new_kind_counts(self):
        c = M.counts(table())
        self.assertEqual(c["ground_wait_arm"], {"events": 95, "anims": 76, "characters": 44})
        self.assertEqual(c["ground_wait_disarm"]["events"], 91)
        self.assertEqual(c["air_wait_arm"], {"events": 14, "anims": 8, "characters": 6})
        self.assertEqual(c["loop"], {"events": 232, "anims": 201, "characters": 68})
        self.assertEqual(c["loop_unlimited"]["events"], 136)
        self.assertEqual(c["store"]["events"], 18)
        self.assertEqual(c["stored_jump"]["events"], 42)
        self.assertEqual(c["hold_release"]["events"], 49)
        self.assertEqual(c["end_keys"], {"anims": 252, "events": 469})

    def test_summary_counts_ground_wait_anims(self):
        rows = M.summary(table())
        self.assertEqual(sum(r["ground_wait"] for r in rows), 76)


class TableTest(NeedsData):
    def test_every_event_decodes_a_known_kind_and_button(self):
        for c in table()["characters"]:
            self.assertIsNone(c["error"], c["prefix"])
            for a in c["anims"]:
                self.assertEqual(a["mash"], any(e["sub"] in M.MASH_SUBS for e in a["events"]))
                for e in a["events"]:
                    self.assertIn(e["kind"], (M.KINDS[e["sub"]], M.HOLD_RELEASE))
                    if e["sub"] in M.MASH_SUBS:
                        self.assertIn(e["button_idx"], range(4), (c["prefix"], a["anim"], e))
                        self.assertIsNotNone(e.get("marker_frame", e.get("marker_true_frame")),
                                             (c["prefix"], a["anim"], e))

    def test_every_field_is_graded(self):
        grades = table()["field_grades"]
        for c in table()["characters"]:
            for a in c["anims"]:
                for k in a:
                    self.assertIn(k, grades, (c["prefix"], k))
                for e in a["events"]:
                    for k in e:
                        self.assertIn(k, grades, (c["prefix"], a["anim"], k))

    def test_guide_check_joins_the_tags(self):
        rows = table()["guide_check"]
        status = {}
        for r in rows:
            status.setdefault(r["status"], []).append(r)
        self.assertGreaterEqual(len(status["flagged"]), 45)
        # every Train tag is a mash the scanner flags
        train = {r["input"]: r["status"] for r in rows if r["file"] == "train-heartnet"}
        self.assertEqual(train, {"side Y": "flagged", "up Y": "flagged", "air Y": "flagged",
                                 "select": "not_a_move"})
        # tags the scanner cannot see stay visible, not hidden
        missing = {(r["file"], r["input"]) for r in status["not_found"]}
        self.assertIn(("franky", "Y"), missing)
        self.assertIn(("edajima", "side B"), missing)
        # E0 pin: the Vegeta guide covers db_b_03 and db_b_04 (Vegeta SSJ), and db_b_04 has the X mash
        self.assertNotIn(("vegeta", "X"), missing)
        self.assertTrue(any(r["file"] == "vegeta" and r["input"] == "X" for r in status["flagged"]))
        # a flagged tag is recorded on the anim
        self.assertIn("guide", {c["source"] for c in anim("bc_b_01", 0x2C)["confirmed"]})

    def test_guide_x_plus_up_maps_to_up_x(self):
        self.assertEqual(M.GUIDE_INPUTS["X+up"], "up X")
        # the real data: Robin (op_b_05, chr_b 16) has an up X mash anim, so the tag flags it
        (real,) = [r for r in table()["guide_check"] if r["input"] == "X+up"]
        self.assertEqual((real["file"], real["status"], real["matched"]),
                         ("nico-robin", "flagged", ["op_b_05 0x2c"]))
        # the join itself: take Robin's up X anims away on a copy and the tag is not_found,
        # give her a new one and it flags that one
        chars = copy.deepcopy(table()["characters"])
        robin = next(c for c in chars if c["prefix"] == "op_b_05")
        robin["anims"] = [a for a in robin["anims"] if a["move"] is None or "up X" not in a["move"]]
        row = next(r for r in M.guide_check(chars) if r["file"] == "nico-robin" and r["input"] == "X+up")
        self.assertEqual(row["status"], "not_found")
        robin["anims"].append({"anim": "0x2a", "move": "up X (koma 4)", "mash": True, "events": []})
        row = next(r for r in M.guide_check(chars) if r["file"] == "nico-robin" and r["input"] == "X+up")
        self.assertEqual((row["status"], row["matched"]), ("flagged", ["op_b_05 0x2a"]))

    def test_cast_counts(self):
        rows = M.summary(table())
        self.assertEqual(len(rows), 74)
        self.assertEqual(sum(r["mash"] for r in rows), 98)

    def test_committed_files_are_fresh(self):
        self.assertEqual(M.OUT.read_text(encoding="utf-8"), M.dump(table()),
                         "docs/rebuild/mash-table.json is stale: run build")
        self.assertEqual(M.OUT_MD.read_text(encoding="utf-8"), M.render_md(table()),
                         "docs/rebuild/mash-table.md is stale: run build")

    def test_dump_is_deterministic_and_sorted(self):
        text = M.dump(table())
        self.assertEqual(text, M.dump(table()))
        self.assertEqual(M.dump(json.loads(text)), text)


class EndKeyAndHoldReleaseNotesTest(NeedsData):
    """Caption and grade-note wording for the end keys and hold_release (mash-table review fixes)."""

    def test_cast_wide_end_keys_are_534_on_301_anims(self):
        self.assertEqual(table()["end_keys_cast"], {"events": 534, "anims": 301})

    def test_end_key_caption_says_it_covers_only_rows(self):
        md = M.render_md(table())
        self.assertIn("counts only the animations that have a row above", md)
        self.assertIn("534 events on 301 animations", md)

    def test_five_measured_idles_are_named_in_the_ends_note(self):
        note = M.GRADE_NOTES["ends"]
        for part in ("Train side Y 51 = 49+2", "up Y 45 = 43+2", "air Y 60 = 58+2",
                     "Yusuke side Y 53 = 51+2", "Kakashi UA 60 = (34 + 24 loop frames) + 2"):
            self.assertIn(part, note)

    def test_hold_release_wording_is_the_static_trace(self):
        core = ("button ev[2], default Marker ev[4]. Static trace (unverified live): a level poll from "
                "the tick after creation that fires on the first tick the button is not down (0x02161440).")
        self.assertIn(core, M.GRADE_NOTES["hold_release"])
        self.assertNotIn("taken when", M.GRADE_NOTES["hold_release"])
        md = M.render_md(table())
        self.assertIn(core, md)
        self.assertNotIn("taken when the button is released", md)


if __name__ == "__main__":
    unittest.main()
