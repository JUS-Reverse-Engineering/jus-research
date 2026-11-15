"""cancel_table.py: unit tests, the pinned code facts, and the hard gate.

The gate (GateTest) fails, not skips, when jus_files is missing: every cancel
case from kakashi.md / yusuke.md (measured routes and negatives, their inferred
starts, the §8 register) and every owner case must pass, and the committed
docs/rebuild/cancel-table.json must equal a fresh build.
Run: python3 -m unittest scripts/tests/test_cancel_table.py
"""
import importlib.util
import contextlib
import io
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis", "cancel_table.py")
SPEC = importlib.util.spec_from_file_location("cancel_table", SCRIPT)
C = importlib.util.module_from_spec(SPEC)
sys.modules["cancel_table"] = C
SPEC.loader.exec_module(C)

HAVE_DATA = C.mr.CHRARC.exists() and C.OV6.exists()
NEED_DOCS = "needs docs/rebuild/characters/*.md, which are not part of this repository"
NEED = "jus_files is missing: run `git submodule update --init` (the gate never skips)"


def char(masks: dict, starts: dict, specials: dict | None = None) -> dict:
    """A fake character: id -> mask, id -> {kind: start}, id -> special ground start."""
    specials = specials or {}
    return {"moves": [{"id": i, "mask": f"0x{masks.get(i, 0xFFFFFFFF):08x}",
                       "cancel_start": starts.get(i), "reason": None if i in starts else "no key",
                       "special_cancel": ({"into": ["X", "up X"], "start": {"ground": specials[i]},
                                           "terminal": True} if i in specials else None),
                       "special_reason": None if i in specials else "no ground key"}
                      for i in C.MOVE_IDS]}


class SchemaDocTest(unittest.TestCase):
    def run_command(self, command, root):
        with patch.object(C, "REPO", root), \
                patch.object(C, "OUT", root / "table.json"), \
                patch.object(C, "SCHEMA", root / "table.md", create=True), \
                patch.object(C, "build", return_value={}), \
                patch.object(C, "gate", return_value=[]), \
                contextlib.redirect_stdout(io.StringIO()):
            return C.main([command])

    def test_build_corrects_the_special_row_and_preserves_other_prose(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = root / "table.md"
            doc.write_text("Before\n| `special_cancel` | ids 1-8; null for ids 9-10 | grade |\nAfter\n")
            self.assertEqual(self.run_command("build", root), 0)
            text = doc.read_text()
            self.assertIn("ids 1-10 with a ground key", text)
            self.assertNotIn("null for ids 9-10", text)
            self.assertTrue(text.startswith("Before\n"))
            self.assertTrue(text.endswith("\nAfter\n"))
            self.assertEqual(self.run_command("check", root), 0)

    def test_check_rejects_stale_schema_even_when_json_is_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "table.json").write_text(C.dump({}))
            (root / "table.md").write_text("| `special_cancel` | null for ids 9-10 | grade |\n")
            self.assertEqual(self.run_command("check", root), 1)


class FollowupsTest(unittest.TestCase):
    def test_ground_window_offers_ids_1_to_6_minus_mask(self):
        self.assertEqual(C.followups(0x2, "ground"), [2, 3, 4, 5, 6])
        self.assertEqual(C.followups(0xAE, "ground"), [4, 6])
        self.assertEqual(C.followups(0x1FE, "ground"), [])

    def test_air_window_offers_ids_9_and_10_minus_mask(self):
        self.assertEqual(C.followups(0x1FE, "air"), [9, 10])
        self.assertEqual(C.followups(0x3FE, "air"), [10])
        self.assertEqual(C.followups(0x7FE, "air"), [])

    def test_down_moves_are_never_offered(self):
        self.assertNotIn(7, C.followups(0, "ground"))
        self.assertNotIn(8, C.followups(0, "ground"))


class RouteTest(unittest.TestCase):
    MASKS = {1: 0x2, 2: 0xAE, 5: 0xAA, 9: 0x3FE, 10: 0x7FE}

    def test_masks_pile_up_along_a_chain(self):
        c = char(self.MASKS, {1: {"ground": 13}, 5: {"ground": 24}, 9: {"air": 16}})
        self.assertEqual(C.route(c, [1, 5]), (True, "allowed", 13))
        self.assertEqual(C.route(c, [1, 5, 2]), (True, "allowed", 24))
        ok, why, _ = C.route(c, [1, 5, 5])
        self.assertFalse(ok)
        self.assertIn("bit 5", why)

    def test_the_window_kind_must_match_the_target_reader(self):
        c = char(self.MASKS, {1: {"ground": 13}, 9: {"air": 16}})
        self.assertFalse(C.route(c, [1, 9])[0])          # ground window, air target
        self.assertEqual(C.route(c, [9, 10]), (True, "allowed", 16))

    def test_no_window_blocks(self):
        c = char(self.MASKS, {})
        ok, why, _ = C.route(c, [1, 2])
        self.assertFalse(ok)
        self.assertIn("no ground window", why)

    def test_ids_11_and_12_are_not_cancel_targets(self):
        c = char(self.MASKS, {1: {"ground": 13}}, {1: 13})
        self.assertFalse(C.route(c, [1, 11])[0])
        self.assertFalse(C.route(c, [1, 12])[0])

    def test_x_and_up_x_hop_needs_a_ground_special_window(self):
        c = char(self.MASKS, {1: {"ground": 13}, 6: {"air": 25}}, {1: 13})
        self.assertEqual(C.route(c, [1, 13]), (True, "allowed", 13))
        self.assertEqual(C.route(c, [1, 14]), (True, "allowed", 13))
        ok, why, _ = C.route(c, [6, 13])           # air-key-only move
        self.assertFalse(ok)
        self.assertIn("no ground window", why)
        self.assertFalse(C.route(c, [9, 13])[0])    # an air move

    def test_a_cancelled_x_is_terminal(self):
        c = char(self.MASKS, {1: {"ground": 13}, 2: {"ground": 21}}, {1: 13, 2: 21})
        self.assertTrue(C.route(c, [1, 2, 13])[0])
        for chain in ([1, 13, 2], [1, 13, 14], [1, 13, 1]):
            ok, why, _ = C.route(c, chain)
            self.assertFalse(ok, chain)
            self.assertIn("terminal", why)


class MoveRowTest(unittest.TestCase):
    REC = {"id": 1, "anim": 0x1E, "mask": 0x2, "misc": 0, "addr": C.TABLE + C.STRIDE}

    @classmethod
    def setUpClass(cls):
        if not HAVE_DATA:
            raise AssertionError(NEED)

    def test_a_failed_sp01_node_gives_null_not_no_key(self):
        ev = {0x1E: {"frames": 30, "notes": [], "undecoded_nodes": ["SP01"],
                     "node_errors": [{"node": "SP01", "error": "struct.error: x"}]}}
        row = C.move_row("zz_b_01", self.REC, ev, None)
        self.assertIsNone(row["cancel_start"])
        self.assertIsNone(row["followups"])
        self.assertIn("SP01", row["reason"])

    def test_a_failed_effect_node_leaves_the_keys(self):
        ev = {0x1E: {"frames": 30, "notes": [{"frame": 11, "events": [{"op": 3, "sub": 0, "arg": 1}]}],
                     "undecoded_nodes": ["GN02"], "node_errors": [{"node": "GN02", "error": "x"}]}}
        row = C.move_row("zz_b_01", self.REC, ev, None)
        self.assertEqual(row["cancel_start"], {"ground": 13})


class SpecialCancelRowTest(unittest.TestCase):
    """special_cancel on one finished row: a ground key gives X and up X."""

    @staticmethod
    def row(i, key, start, reason=None):
        return {"id": i, "key": key, "cancel_start": start, "reason": reason}

    def test_a_ground_key_gives_x_and_up_x_from_the_ground_start(self):
        sc, why = C.special_cancel("zz_b_01", self.row(1, {"ground": [11]}, {"ground": 13}))
        self.assertEqual(sc, {"into": ["X", "up X"], "start": {"ground": 13},
                              "gate": C.SPECIAL_GATE, "terminal": True})
        self.assertIsNone(why)
        self.assertIn("0x0215A708", C.SPECIAL_GATE)
        self.assertIn("0x0207834C", C.SPECIAL_GATE)

    def test_a_both_keys_row_uses_the_ground_start(self):
        sc, _ = C.special_cancel("zz_b_01", self.row(2, {"ground": [20], "air": [30]},
                                                     {"ground": 22, "air": 32}))
        self.assertEqual(sc["start"], {"ground": 22})

    def test_an_air_key_only_move_has_none(self):
        sc, why = C.special_cancel("zz_b_01", self.row(6, {"air": [23]}, {"air": 25}))
        self.assertIsNone(sc)
        self.assertIn("no ground key", why)

    def test_a_ground_key_on_an_air_slot_still_offers_the_ground_reader(self):
        for i in (9, 10):
            sc, why = C.special_cancel("zz_b_01", self.row(i, {"ground": [11]}, {"ground": 13}))
            self.assertEqual(sc['start'], {'ground':13})
            self.assertEqual(sc['into'], ['X','up X'])

    def test_no_key_at_all_is_null_with_the_rows_reason(self):
        sc, why = C.special_cancel("zz_b_01", self.row(1, {}, None, "no op3 sub0 key"))
        self.assertIsNone(sc)
        self.assertIn("no op3 sub0 key", why)

    def test_a_key_past_the_anim_end_is_null(self):
        sc, why = C.special_cancel("zz_b_01", self.row(1, {"ground": [40]}, None, "cancel key at or after"))
        self.assertIsNone(sc)
        self.assertIn("cancel key at or after", why)

    def test_ids_above_10_are_null(self):
        for i in range(11, 15):
            self.assertIsNone(C.special_cancel("zz_b_01", self.row(i, {"ground": [16]}, {"ground": 18}))[0])


class KeysTest(unittest.TestCase):
    def test_only_op3_sub0_args_1_and_0x15_count(self):
        notes = [{"frame": 11, "events": [{"op": 3, "sub": 0, "arg": 1}]},
                 {"frame": 20, "events": [{"op": 3, "sub": 0, "arg": 2}, {"op": 3, "sub": 1, "arg": 1}]},
                 {"frame": 55, "events": [{"op": 3, "sub": 0, "arg": 0x15}]},
                 {"frame": 60, "events": [{"op": 4, "sub": 0, "arg": 1}]}]
        self.assertEqual(C.keys_of({"notes": notes}), {"ground": [11], "air": [55]})


DOC = """x
<!-- kit:begin cancel-routes -->
| route | offsets tested | coverage | classification per k | cancel start (grade / derivation) | testimony |
|---|---|---|---|---|---|
| `B` → `Y` | 4, 8 | sampled | k=4: cancel (successor onset +19, id 12); k=8: cancel (successor onset +19, id 12) | k=4: +13 (inferred -- x); k=8: +13 (inferred -- y) | — |
| `up B` → `air B` | 12, 16 | sampled | k=12: no-effect; k=16: cancel (successor onset +29, id 264) | k=16: +20 (inferred -- x) | — |

| route | offsets tested | classification | coverage |
|---|---|---|---|
| `B` → `B` | 4, 8 | buffered/no-effect | sampled (offsets: 4, 8) |
<!-- kit:end cancel-routes -->
"""


class DocRoutesTest(unittest.TestCase):
    def test_parses_declared_routes_and_negatives(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "k.md"
            p.write_text(DOC, encoding="utf-8")
            rows = C.doc_routes(p)
        self.assertEqual([(r["src"], r["dst"]) for r in rows], [("B", "Y"), ("up B", "air B"), ("B", "B")])
        self.assertEqual(rows[0]["starts"], {4: 13, 8: 13})
        self.assertEqual(rows[1]["classes"], {12: "no-effect", 16: "cancel"})
        self.assertEqual(rows[2]["classes"], {0: "buffered/no-effect"})
        self.assertEqual(rows[0]["line"], 5)


class CodeFactsTest(unittest.TestCase):
    """Each fact is the reading the note cites; ov6.txt line numbers in comments."""

    @classmethod
    def setUpClass(cls):
        if not HAVE_DATA:
            raise AssertionError(NEED)
        cls.f = C.code_facts()

    def test_notetrack_op3_reaches_the_fighter_callback(self):
        self.assertEqual(self.f["notetrack_op3_handler"], 0x021569AC)     # op table 0x0217200C
        self.assertEqual(self.f["op3_sub0_handler"], 0x021568E8)          # sub table 0x02172000
        self.assertEqual(self.f["fighter_callback_literal"], (0x02156D70, 0x02157A44))  # :10706

    def test_notetrack_callback_cases(self):
        self.assertEqual(self.f["callback_case_1"], 0x02157B8C)       # :11537 -> :11609
        self.assertEqual(self.f["callback_case_0x15"], 0x02157B98)    # :11557 -> :11612
        self.assertEqual(self.f["callback_case_0x1d"], 0x02157BA4)    # :11565 -> :11615
        self.assertEqual(self.f["store_0x02157B90"], 0xF3)
        self.assertEqual(self.f["store_0x02157B9C"], 0xF4)
        self.assertEqual(self.f["store_0x02157BA8"], 0xC8)

    def test_move_start_clears_both_flags_and_the_buffer(self):
        self.assertEqual(self.f["init_clears"], [0xF4, 0xF3, 0xC8])   # :13955-13959

    def test_state9_reads_ground_flag_with_ground_reader_air_with_air(self):
        self.assertEqual((self.f["ground_reader_call"], self.f["ground_flag_read"]), (0x0215A720, 0xF3))
        self.assertEqual((self.f["air_reader_call"], self.f["air_flag_read"]), (0x0215A8C0, 0xF4))

    def test_reader_returns(self):
        self.assertEqual(self.f["ground_returns"], [0, 1, 2, 3, 4, 5, 6, 11, 12, 13, 14])
        self.assertEqual(self.f["air_returns"], [0, 9, 10])
        self.assertEqual(self.f["down_returns"], [0, 7, 8, 11])
        self.assertEqual(self.f["neutral_readers"], [0x0215A720, 0x0215A8C0, 0x0215A8F8])

    def test_table_comes_from_ov6_literals_in_the_ov6_image(self):
        self.assertEqual(self.f["mask_literal_cancel"], (0x0215A65C, 0x021712BC))
        self.assertEqual(self.f["mask_literal_neutral"], (0x02159ECC, 0x021712BC))
        self.assertEqual(self.f["anim_literal_init"], (0x0215A63C, 0x021712B8))
        self.assertTrue(self.f["table_in_ov6_image"])

    def test_system_ids_jump(self):
        # C8 - 11 = 0..3 -> id 11 no cancel, 12 special path, 13/14 gated path
        self.assertEqual(self.f["system_jump"], [0x0215A618, 0x0215A590, 0x0215A50C, 0x0215A50C])

    def test_move_table_rows(self):
        t = C.move_table()
        self.assertEqual([(t[i]["anim"], t[i]["mask"]) for i in range(1, 11)],
                         [(0x1E, 0x2), (0x1F, 0xAE), (0x20, 0xAA), (0x21, 0x1FE), (0x22, 0xAA),
                          (0x23, 0x1FE), (0x24, 0xAA), (0x25, 0x1FE), (0x26, 0x3FE), (0x27, 0x7FE)])
        self.assertEqual([t[i]["mask"] for i in range(11, 15)], [0xFFFFFFFF] * 4)

    def test_every_indexed_row(self):
        # X / up X at koma 8 read row 14 + 2 * (8 - 4) = 22; row 23 is the zero terminator.
        rows = {i: C.table_row(i) for i in C.TABLE_ROWS}
        self.assertEqual((min(rows), max(rows)), (1, 22))
        self.assertEqual([rows[i]["anim"] for i in range(11, 23)], [0x18, *range(0x28, 0x33)])
        self.assertEqual([rows[i]["misc"] for i in (1, 2, 11, 12, 13, 22)],
                         [0x110809, 0x120909, 0xFFFF0C, 0x140B0B, 0x130A0A, 0x130A0A])
        self.assertEqual({k: v for k, v in C.table_row(23).items() if k != "addr"},
                         {"id": 23, "anim": 0, "mask": 0, "misc": 0})

    def test_c4_readers(self):
        r = C.c4_readers()
        self.assertEqual(r["latch_skip"], 12)
        self.assertTrue(r["latch_skip_conditional_load"])
        self.assertEqual((r["ai_load"], r["ai_mask"], r["ai_ids"]), (0xC4, 0x7F9980, (1, 24)))
        self.assertEqual(r["misc_bytes"], [(0x02159E50, 0x021712C0), (0x0215A0E8, 0x021712C1),
                                           (0x0215A3A0, 0x021712C2)])

    def test_c4_tested_bits(self):
        # id 12's latch skips C4; the AI tests 23, which no state-9 reader returns.
        self.assertEqual(sorted(C.c4_tested_bits()), [1, 2, 3, 4, 5, 6, 9, 10, 11, 13, 14, 23])


@unittest.skipUnless(all(p.exists() for p in C.DOCS.values()), NEED_DOCS)
class GateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not HAVE_DATA:
            raise AssertionError(NEED)
        cls.table = C.build()

    def test_every_measured_and_owner_case_passes(self):
        cases = C.gate(self.table)
        miss = [f"{c['case']}: {c['detail']} ({c['cite']})" for c in cases if not c["pass"]]
        self.assertEqual(miss, [])
        grades = {c["grade"] for c in cases}
        self.assertEqual(grades, {"measured", "inferred", "owner"})
        self.assertGreaterEqual(len(cases), 51)

    def test_route_starts_carry_the_kit_docs_grade(self):
        # kakashi.md / yusuke.md grade each start "inferred -- successor onset minus lag"
        cases = C.gate(self.table)
        starts = [c for c in cases if c["case"].endswith("start") and "->" in c["case"]
                  and "(§8 register)" not in c["case"] and "chain" not in c["case"]]
        self.assertGreaterEqual(len(starts), 20)
        self.assertEqual({c["grade"] for c in starts}, {"inferred"})
        allowed = [c for c in cases if c["case"].endswith("allowed")]
        self.assertEqual({c["grade"] for c in allowed}, {"measured"})

    def test_register_cases_name_the_grade_disagreement(self):
        reg = [c for c in C.gate(self.table) if "(§8 register)" in c["case"]]
        self.assertEqual(len(reg), 6)
        for c in reg:
            self.assertEqual(c["grade"], "measured")
            self.assertIn("route rows grade it inferred", c["detail"])

    def test_owner_cases_cite_the_owner_notes(self):
        owner = [c for c in C.gate(self.table) if c["grade"] == "owner"]
        names = {c["case"] for c in owner}
        self.assertIn("na_b_02 up B -> Y", names)
        self.assertIn("na_b_04 B -> up B -> Y", names)
        notes = (C.REPO / "docs/research/moveset-notes/OWNER-NOTES.md").read_text(encoding="utf-8").splitlines()
        for c in owner:
            path, line = c["cite"].rsplit(":", 1)
            self.assertEqual(path, "docs/research/moveset-notes/OWNER-NOTES.md", c["case"])
            self.assertTrue(notes[int(line.split("-")[0]) - 1].strip(), c["case"])

    def test_chain_last_hop_start_is_checked(self):
        chain = [c for c in C.gate(self.table) if c["case"] == "na_b_04 B -> up B -> Y chain start"]
        self.assertEqual(len(chain), 1)
        self.assertTrue(chain[0]["pass"], chain[0]["detail"])
        self.assertEqual(chain[0]["grade"], "inferred")
        self.assertIn("+24", chain[0]["detail"])

    def test_the_four_bad_gn02_archives_now_have_rows(self):
        rows = {c["prefix"]: {m["move"]: m for m in c["moves"]} for c in self.table["characters"]}
        self.assertEqual(rows["db_b_06"]["B"]["cancel_start"], {"ground": 16})
        self.assertEqual(rows["db_b_07"]["side B"]["cancel_start"], {"air": 21})
        self.assertEqual(rows["db_b_08"]["side B"]["cancel_start"], {"air": 21})
        self.assertEqual(rows["op_b_07"]["air B"]["cancel_start"], {"air": 19})
        # op_b_07 is chr_b 18 (Gear 2 Luffy), measured 2026-10-13, not Robin
        names = {c["prefix"]: c["names"] for c in self.table["characters"]}
        self.assertEqual([(n["chr_b"], n["name"]) for n in names["op_b_07"]], [(18, "Gear 2 Luffy")])
        self.assertTrue(names["op_b_07"][0]["basis"].startswith("File column measured"))
        self.assertEqual([(n["chr_b"], n["name"]) for n in names["op_b_06"]], [(17, "Franky")])
        parse = [m for r in rows.values() for m in r.values() if "parse" in (m["reason"] or "")]
        self.assertEqual(parse, [])

    def test_move_name_grade_is_measured_only_where_a_capture_matched_the_anim(self):
        rows = {c["prefix"]: {m["move"]: m for m in c["moves"]} for c in self.table["characters"]}
        self.assertEqual(rows["na_b_04"]["up B"]["grades"]["move"], "measured")
        self.assertEqual(rows["yh_b_01"]["B"]["grades"]["move"], "measured")
        self.assertEqual(rows["yh_b_01"]["side Y"]["grades"]["move"], "measured")
        self.assertEqual(rows["na_b_02"]["up B"]["grades"]["move"], "inferred")

    def test_committed_json_is_fresh(self):
        self.assertTrue(C.OUT.exists(), "run: python3 scripts/analysis/cancel_table.py build")
        self.assertEqual(C.OUT.read_text(encoding="utf-8"), C.dump(self.table),
                         "stale: run python3 scripts/analysis/cancel_table.py build")

    def test_every_null_has_a_reason(self):
        for c in self.table["characters"]:
            for m in c["moves"]:
                if m["cancel_start"] is None:
                    self.assertTrue(m["reason"], f"{c['prefix']} id {m['id']}")

    def test_yusuke_side_y_first_phase_and_native_cancel_now_agree(self):
        y = next(c for c in self.table['characters'] if c['prefix']=='yh_b_01')
        row = next(m for m in y['moves'] if m['id']==4)
        self.assertEqual((row['anim'],row['frames']),('0x21',136))
        self.assertEqual(row['key'],{'ground':[29,70,109]})
        self.assertEqual(row['cancel_start'],{'ground':31})
        self.assertEqual(row['followups'],[])
        self.assertEqual(row['special_cancel']['start'],{'ground':31})

    def test_start_is_measured_only_where_a_live_check_timed_it(self):
        live = {("na_b_04", 1): {"ground": 13}, ("na_b_04", 9): {"air": 16}}
        for c in self.table["characters"]:
            for m in c["moves"]:
                if m["cancel_start"] is None:
                    continue
                want = live.get((c["prefix"], m["id"]))
                grade = m["grades"]["cancel_start"]
                if want:
                    self.assertEqual((m["cancel_start"], grade), (want, "measured"))
                    self.assertIn("cancel-live-checks-2026-09-25", m["cites"]["cancel_start"])
                else:
                    self.assertEqual(grade, "inferred", f"{c['prefix']} id {m['id']}")
                    self.assertNotIn("cancel_start", m["cites"])

    def rows(self, prefix):
        return {m["move"]: m for m in next(c for c in self.table["characters"]
                                           if c["prefix"] == prefix)["moves"]}

    def test_eve_special_cancel_starts(self):
        eve = self.rows("bc_b_01")
        want = {"B": 13, "Y": 24, "side B": 15, "side Y": 48, "up B": 16, "down B": 26, "down Y": 40}
        got = {n: m["special_cancel"]["start"]["ground"] for n, m in eve.items() if m["special_cancel"]}
        self.assertEqual(got, want)
        for n in want:
            sc = eve[n]["special_cancel"]
            self.assertEqual(sc["into"], ["X", "up X"])
            self.assertIs(sc["terminal"], True)
            self.assertEqual(sc["start"]["ground"], eve[n]["cancel_start"]["ground"])
            self.assertEqual(eve[n]["grades"]["special_cancel"], "inferred", n)
        # side Y and down Y: no normal followups, so a special-only window
        self.assertEqual(eve["side Y"]["followups"], [])
        self.assertEqual(eve["down Y"]["followups"], [])

    def test_eve_up_y_and_air_moves_have_no_special(self):
        eve = self.rows("bc_b_01")
        for n in ("up Y", "air B", "air Y"):
            self.assertIsNone(eve[n]["special_cancel"], n)
            self.assertTrue(eve[n]["special_reason"], n)
        self.assertIn("air key only", eve["up Y"]["special_reason"])

    def test_air_slots_offer_specials_only_when_they_key_a_ground_window(self):
        for c in self.table["characters"]:
            for m in c["moves"]:
                if m['id'] > 10:
                    self.assertIsNone(m['special_cancel'], (c['prefix'],m['id']))
                elif m['id'] in (9,10):
                    ground=(m.get('cancel_start') or {}).get('ground')
                    self.assertEqual(m['special_cancel'] is not None,ground is not None,
                                     (c['prefix'],m['id']))

    def test_special_cancel_is_never_without_a_ground_window_or_a_reason(self):
        for c in self.table["characters"]:
            for m in c["moves"]:
                sc = m["special_cancel"]
                if sc is None:
                    self.assertTrue(m["special_reason"], (c["prefix"], m["id"]))
                else:
                    self.assertIsNone(m["special_reason"])
                    self.assertEqual(sc["start"], {"ground": m["cancel_start"]["ground"]})
                    self.assertIn("ground", m["key"], (c["prefix"], m["id"]))

    def test_special_grade_is_measured_only_for_yusukes_four_live_moves(self):
        for c in self.table["characters"]:
            for m in c["moves"]:
                if m["id"] > 10:
                    self.assertIsNone(m["grades"].get("special_cancel"))
                    continue
                live = c["prefix"] == "yh_b_01" and m["move"] in ("B", "Y", "side Y", "up Y")
                self.assertEqual(m["grades"]["special_cancel"], "measured" if live else "inferred",
                                 (c["prefix"], m["move"]))
                self.assertEqual("special_cancel" in m["cites"], live, (c["prefix"], m["move"]))

    def test_yusuke_b_special_is_measured_and_cites_both_runs(self):
        y = self.rows("yh_b_01")
        self.assertEqual(y["B"]["special_cancel"]["start"], {"ground": 12})
        self.assertEqual(y["B"]["grades"]["special_cancel"], "measured")
        self.assertIn("yusuke-xcancel-airy-2026-09-25/RESULTS.md", y["B"]["cites"]["special_cancel"])
        self.assertIn("yusuke-matrix-2026-09-30/r1/matrix/RESULTS.md", y["up Y"]["cites"]["special_cancel"])
        self.assertEqual(y["up Y"]["special_cancel"]["start"], {"ground": 28})
        self.assertIsNone(y["up B"]["special_cancel"])           # air-key-only
        self.assertEqual(y["up B"]["grades"]["special_cancel"], "inferred")
        self.assertEqual(y["side Y"]["special_cancel"]["start"], {"ground": 31})
        self.assertIsNone(y["side Y"]["special_reason"])
        notes = self.table["grade_notes"]
        self.assertIn("yusuke-xcancel-airy-2026-09-25/RESULTS.md", notes["special_cancel"])
        self.assertIn("yusuke-matrix-2026-09-30/r1/matrix/RESULTS.md", notes["special_cancel"])
        self.assertIn("special_cancel", notes["system_followups"])

    def test_route_to_x_and_terminal_on_the_built_table(self):
        eve = next(c for c in self.table["characters"] if c["prefix"] == "bc_b_01")
        self.assertEqual(C.route(eve, [C.IDS["side Y"], 13]), (True, "allowed", 48))
        self.assertEqual(C.route(eve, [C.IDS["B"], C.IDS["Y"], 14]), (True, "allowed", 24))
        self.assertFalse(C.route(eve, [C.IDS["up Y"], 13])[0])
        self.assertFalse(C.route(eve, [C.IDS["air B"], 13])[0])
        self.assertFalse(C.route(eve, [C.IDS["B"], 13, C.IDS["Y"]])[0])

    def test_every_battle_archive_is_listed(self):
        self.assertEqual(len(self.table["characters"]), 74)


if __name__ == "__main__":
    unittest.main()


class DreamEntryFactsTest(unittest.TestCase):
    """The two id-12 entry paths and every write of fighter+0xC4 (finding
    docs/research/findings/dream-cancel-c4-inheritance.md)."""

    @classmethod
    def setUpClass(cls):
        if not HAVE_DATA:
            raise AssertionError(NEED)
        cls.f = C.dream_entry_facts()

    def test_ov6_writes_c4_at_five_sites_only(self):
        # 0x02159D7C resets it, ORs the row's mask, and ORs ~0 for 13/14 and for 12;
        # 0x0215A578 ORs a chained id's mask. No byte or halfword store reaches +0xC4..C7.
        self.assertEqual(self.f["c4_stores"],
                         [0x02159DB8, 0x02159DF4, 0x02159E20, 0x02159E84, 0x0215A578])

    def test_neutral_start_resets_then_makes_the_dream_all_ones(self):
        self.assertTrue(self.f["neutral_reset"])
        self.assertTrue(self.f["neutral_or_mask"])
        self.assertTrue(self.f["neutral_dream_all_ones"])
        self.assertEqual(self.f["neutral_snapshot"], (0x1CC, 0x1D0))

    def test_the_id_12_fire_path_neither_reads_nor_writes_c4(self):
        self.assertEqual(self.f["fire_path"], (0x0215A590, 0x0215A618))
        self.assertEqual(self.f["fire_path_c4_access"], [])
        self.assertEqual(self.f["fire_compare"], (0x1CC, 0x1D0))
        self.assertEqual(self.f["fire_ids"], [12, 13, 14])

    def test_the_fire_restarts_the_same_handler(self):
        self.assertEqual(self.f["restart"], (0xCA, 0x14))
        self.assertEqual(self.f["reader_gates"], [0x0215A390])
        self.assertTrue(self.f["misc_counter_rejoins"])

    def test_offered_masks_nest(self):
        # A reader-entered chain's C4 is the last move's own mask.
        self.assertEqual(C.unnested_offers(), [])


class DreamOffersTest(unittest.TestCase):
    def test_neutral_dream_offers_nothing(self):
        self.assertEqual(C.dream_offers(None), ([], False))

    def test_cancel_entry_offers_the_inherited_projection(self):
        self.assertEqual(C.dream_offers(0x2), (["Y", "side B", "side Y", "up B", "up Y"], True))
        self.assertEqual(C.dream_offers(0x1FE), ([], True))
        self.assertEqual(C.dream_offers(0xFFFFFFFF), ([], False))
