"""ua_table.py: the Ultimate Action (SELECT, move id 11, anim 0x18) decode, the pins
review.md §3.5 names, the cast counts, and the freshness of docs/rebuild/ua-table.{json,md}.

The data tests fail, not skip, when jus_files is missing (the same gate as test_mash_table).
Run: python3 -m unittest scripts/tests/test_ua_table.py
"""
import copy
import importlib.util
import os
import sys
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis", "ua_table.py")
SPEC = importlib.util.spec_from_file_location("ua_table", SCRIPT)
U = importlib.util.module_from_spec(SPEC)
sys.modules["ua_table"] = U
SPEC.loader.exec_module(U)
M = U.M

HAVE_DATA = M.mr.CHRARC.exists() and M.C.OV6.exists()
NEED = "jus_files is missing: run `git submodule update --init` (the gate never skips)"

_TABLE = None


def table():
    global _TABLE
    if _TABLE is None:
        _TABLE = U.build()
    return _TABLE


def char(prefix):
    return next(c for c in table()["characters"] if c["prefix"] == prefix)


def ua(prefix):
    return char(prefix)["ua"]


def anim_rows(prefix, aid):
    """Every sub 19 / sub 20 row of one anim id of a character (any member)."""
    c = char(prefix)
    return [r for r in c["stores"] + c["stored_jumps"] if r["anim"] == f"0x{aid:02x}"]


def effect(prefix, frame, kind):
    return next(e for e in ua(prefix)["effects"] if e["frame"] == frame and e["kind"] == kind)


class NeedsData(unittest.TestCase):
    def setUp(self):
        if not HAVE_DATA:
            self.fail(NEED)


# ------------------------------------------------------------------ pure decodes (bytes only)


class OpDecodeTest(unittest.TestCase):
    """Each field reads its own bytes, with the signedness the handlers use."""

    def test_arg23_hp_is_signed_s16_at_bytes_4_5(self):
        ev = U.decode_op3(bytes([0, 3, 23, 0, 0xC0, 0xFF]))
        self.assertEqual((ev["kind"], ev["amount_raw"]), ("hp", -64))

    def test_arg23_hp_high_byte_is_signed_s16(self):
        ev = U.decode_op3(bytes([0, 3, 23, 0, 0xC0, 0xFE]))
        self.assertEqual((ev["kind"], ev["amount_raw"]), ("hp", -320))

    def test_arg24_sp_raw_is_s16_at_bytes_4_5(self):
        ev = U.decode_op3(bytes([0, 3, 24, 0, 0x00, 0x08]))
        self.assertEqual((ev["kind"], ev["amount_raw"]), ("sp", 2048))

    def test_arg9_is_arm_substitute_with_signed_decoy(self):
        ev = U.decode_op3(bytes([0, 3, 9, 0, 0xFF, 0]))
        self.assertEqual((ev["kind"], ev["decoy"]), ("arm_substitute", -1))
        self.assertEqual(U.decode_op3(bytes([0, 3, 9, 0, 0, 0]))["decoy"], 0)

    def test_arg7_is_invuln_ticks(self):
        ev = U.decode_op3(bytes([0, 3, 7, 0, 10, 0]))
        self.assertEqual((ev["kind"], ev["ticks"]), ("invuln", 10))

    def test_arg7_invuln_ticks_is_s16_at_bytes_4_5(self):
        ev = U.decode_op3(bytes([0, 3, 7, 0, 0x2C, 0x01]))
        self.assertEqual((ev["kind"], ev["ticks"]), ("invuln", 300))

    def test_arg2_is_spawn_row_at_byte_4(self):
        ev = U.decode_op3(bytes([0, 3, 2, 0, 6, 0]))
        self.assertEqual((ev["kind"], ev["row"]), ("spawn", 6))

    def test_other_args_are_kept_raw_with_grade_lead(self):
        ev = U.decode_op3(bytes([0, 3, 5, 0, 1, 2]))
        self.assertEqual(ev["grade"], "lead")
        self.assertEqual(ev["raw"], "00 03 05 00 01 02")

    def test_impulse_formula(self):
        # Eve f42 bytes `03 01 00 1c`: y = 28 * -126
        ev = U.decode_impulse(bytes([3, 1, 0, 0x1C]))
        self.assertEqual((ev["x_raw"], ev["y_raw"]), (0, -3528))

    def test_impulse_x_is_facing_signed_shift(self):
        ev = U.decode_impulse(bytes([3, 1, 0xFE, 0]))
        self.assertEqual(ev["x_raw"], -64)

    def test_store_value_is_signed(self):
        # sub 19 bytes `13 00 ff 00`: ev[2] = -1
        ev = M.decode_event(19, bytes([0x13, 0, 0xFF, 0]), M.code_facts(), {})
        self.assertEqual(ev["value"], -1)

    def test_markers_resolve_to_frames(self):
        self.assertEqual(U.resolve_targets({0: 0, 3: 59}), {"0": 0, "3": 59})


# ------------------------------------------------------------------ code pins (review §3.5)


class PinnedCode(NeedsData):
    def test_sub_table_entries(self):
        C = M.C
        self.assertEqual(C.word(M.SUB_TABLE + 4 * 19), 0x021560EC)
        self.assertEqual(C.word(M.SUB_TABLE + 4 * 20), 0x021560F8)

    def test_sub_table_words(self):
        C = M.C
        self.assertEqual(C.word(0x021560EC), 0xE1D110D2)       # bytes d2 10 d1 e1: ldrsb r1,[r1,#2]
        self.assertEqual(C.word(0x021560F0), 0xE5C010A3)       # bytes a3 10 c0 e5: strb r1,[r0,#0xa3]

    def test_init_writes_store_byte(self):
        self.assertEqual(M.C.word(0x0215542C), 0xE5C400A3)     # strb r0,[r4,#0xa3] (ctor, -1)

    def test_op3_case_addresses(self):
        facts = U.code_facts()
        self.assertEqual(facts["op3_cases"], {
            "2": "0x02157BB0", "7": "0x02157C30", "9": "0x02157C4C", "10": "0x02157C5C",
            "17": "0x02157D2C", "18": "0x02157D38", "23": "0x02157DB8", "24": "0x02157DC8"})

    def test_op1_impulse_handler_and_multiplier(self):
        C = M.C
        self.assertEqual(C.word(0x02172020 + 4 * 3), 0x0215669C)
        self.assertEqual(C.word(0x021566F4), 0xE3E0007D)       # mvn r0,#0x7d = -126

    def test_button_table_words(self):
        C = M.C
        self.assertEqual([C.word(0x02171098 + 4 * i) for i in range(4)],
                         [0x04000080, 0x08000100, 0x02000040, 0x20001000])

    def test_move_table_id_11(self):
        mt = M.C.move_table()
        self.assertEqual((mt[11]["anim"], mt[11]["mask"], mt[11]["misc"]), (0x18, 0xFFFFFFFF, 0xFFFF0C))

    def test_ground_reader_tests_select(self):
        self.assertEqual(M.C.word(0x0215A7D0), 0xE3100A01)     # tst r0,#0x1000

    def test_air_reader_returns_9_and_10(self):
        self.assertEqual(U.air_reader_returns(), {9, 10})

    def test_reset_range_does_not_clear_store_byte(self):
        C = M.C
        words = [C.word(a) for a in range(0x021555C4, 0x021555FC, 4)]
        self.assertFalse(any((w >> 20) == 0xE5C and (w & 0xFF) == 0xA3 for w in words))
        self.assertEqual(C.word(0x021555C8), 0xE5C410A0)
        self.assertEqual(C.word(0x021555D4), 0xE5C410A2)
        self.assertEqual(C.word(0x021555E0), 0xE5C410A1)


class KbJoinTest(NeedsData):
    """Spawn rows -> knockback records: inferred from the art low byte = anim id (review c4)."""

    def test_kb_recs_for_art_is_the_low_byte_join(self):
        self.assertEqual(U.kb_recs_for_art("bc_b_02", 0x074248), [6])
        self.assertEqual(U.kb_recs_for_art("bc_b_02", 0x074249), [8])
        self.assertEqual(U.kb_recs_for_art("bc_b_02", 0x07424A), [10])
        self.assertEqual(U.kb_recs_for_art("bc_b_02", 0x074241), [])

    def test_spawn_row_without_a_kb_anim_is_false(self):
        self.assertIs(ua("bc_b_02")["spawns"][0]["has_kb_record"], False)
        self.assertEqual(ua("bc_b_02")["spawns"][0]["kb_recs"], [])

    def test_every_in_file_spawn_has_a_bool_kb_flag(self):
        for c in table()["characters"]:
            for s in c["ua"]["spawns"]:
                if s["in_file"]:
                    self.assertIsInstance(s["has_kb_record"], bool, f"{c['prefix']} row {s['row']}")


# ------------------------------------------------------------------ cast counts and anchors


class CastTest(NeedsData):
    def test_74_battle_rows(self):
        self.assertEqual(len(table()["characters"]), 74)
        self.assertTrue(all(c["ua"] is not None for c in table()["characters"]))

    def test_18_stores_and_42_stored_jumps(self):
        self.assertEqual(table()["counts"]["store"]["events"], 18)
        self.assertEqual(table()["counts"]["stored_jump"]["events"], 42)

    def test_train_consume_rows(self):
        # bc_b_02 (Train): store 3 is consumed at f4 in 0x21, f7 in 0x23, f6 in 0x27
        for anim_id, frame, want in ((0x21, 4, 59), (0x23, 7, 60), (0x27, 6, 68)):
            row = next(s for s in anim_rows("bc_b_02", anim_id) if s["sub"] == 20 and s["frame"] == frame)
            self.assertEqual(row["targets"]["3"], want, f"0x{anim_id:02x} f{frame}")

    def test_yusuke_consume_targets(self):
        # yh_b_01 (Yusuke): 0x21 {1: 60, 3: 101}; 0x27 {1: 58, 3: 97}
        for anim_id, want in ((0x21, {1: 60, 3: 101}), (0x27, {1: 58, 3: 97})):
            row = next(s for s in anim_rows("yh_b_01", anim_id) if s["sub"] == 20)
            for k, v in want.items():
                self.assertEqual(row["targets"][str(k)], v, f"0x{anim_id:02x} marker {k}")

    def test_ends_are_op3_sub1_frames_only(self):
        self.assertEqual(ua("yh_b_01")["ends"], [43, 57])
        self.assertEqual(ua("na_b_04")["ends"], [34])
        self.assertEqual(ua("bc_b_02")["ends"], [])

    def test_bc_b_02_spawn_row_zero_is_the_first_shot(self):
        s = ua("bc_b_02")["spawns"][0]
        self.assertEqual((s["row"], s["art"], s["frame"]), (0, "0x00074241", 12))

    def test_kakashi_arm_on_f18_decoy_zero(self):
        e = effect("na_b_04", 18, "arm_substitute")
        self.assertEqual(e["decoy"], 0)
        self.assertEqual(e["grade"], "measured")

    def test_eve_f42_impulse_y_28(self):
        imp = next(i for i in ua("bc_b_01")["impulses"] if i["frame"] == 42)
        self.assertEqual(imp["y_raw"], -3528)

    def test_stores_and_consumes_have_anim_and_frame(self):
        for c in table()["characters"]:
            for s in c["stores"]:
                self.assertIsInstance(s["frame"], int)
                self.assertIn("anim", s)


# ------------------------------------------------------------------ freshness and determinism


class FreshnessTest(NeedsData):
    def test_committed_files_are_fresh(self):
        self.assertTrue(U.OUT.exists() and U.OUT_MD.exists(), "run ua_table.py build")
        self.assertEqual(U.OUT.read_text(encoding="utf-8"), U.dump(table()))
        self.assertEqual(U.OUT_MD.read_text(encoding="utf-8"), U.render_md(table()))

    def test_dump_is_deterministic(self):
        self.assertEqual(U.dump(table()), U.dump(copy.deepcopy(table())))


if __name__ == "__main__":
    unittest.main()


class EventCoordinateTest(NeedsData):
    def test_every_event_has_the_exact_note_coordinate_and_bounded_bytes(self):
        for prefix in ('bc_b_02', 'hs_b_01', 'dt_b_01', 'bc_b_01', 'na_b_04', 'yh_b_01'):
            native = {}
            for member, almt in M.mr.motions(prefix):
                native.setdefault(member, {}).update(M.E.anim_events(almt))
            for scan in U.anim_scan(prefix):
                expected = [(ni, ei, n['frame'], bytes.fromhex(e['raw']))
                            for ni, n in enumerate(native[scan['member']][scan['anim']]['notes'])
                            for ei, e in enumerate(n['events'])]
                actual = [(e.get('note'), e.get('event'), e['frame'], e['raw'])
                          for e in scan['events']]
                self.assertEqual(actual, expected, (prefix, scan['member'], scan['anim']))
