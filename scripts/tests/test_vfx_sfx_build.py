import importlib.util
import json
import os
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis", "vfx_sfx_build.py")
SPEC = importlib.util.spec_from_file_location("vfx_sfx_build", SCRIPT)
V = importlib.util.module_from_spec(SPEC)
sys.modules["vfx_sfx_build"] = V
SPEC.loader.exec_module(V)

HAVE_DATA = (V.sf.SDAT.exists() and V.mr.CHRARC.exists() and V.er.EFC.exists()
             and V.EFFECT_DIR.exists() and (V.REPO / "jus_files" / "arm9").exists())

HAVE_KIT = all((V.REPO / "docs" / "rebuild" / "characters" / f"{c}.kit.json").exists() for c in ("eve", "train"))
NEED_KIT = "needs docs/rebuild/characters/*.kit.json, which are not part of this repository"


class FakeMap:
    def __init__(self, words):
        self.words = words

    def read(self, addr, size, overlay=None):
        return struct.pack("<I", self.words[addr])[:size]


def fake_rom(words):
    r = V.Rom.__new__(V.Rom)
    r.mm = FakeMap(words)
    return r


class DecodeTest(unittest.TestCase):
    def test_bl_target(self):
        # 0x02081D40 adaaffeb -> bl 0x0206C7FC (the guard-spark spawn call)
        self.assertEqual(fake_rom({0x02081D40: 0xEBFFAAAD}).bl_target(0x02081D40), 0x0206C7FC)
        # forward branch: 0x02081A24 af4803eb -> bl 0x02153CE8
        self.assertEqual(fake_rom({0x02081A24: 0xEB0348AF}).bl_target(0x02081A24), 0x02153CE8)
        with self.assertRaises(ValueError):
            fake_rom({0: 0xE3A0007A}).bl_target(0)

    def test_ldr_literal(self):
        # 0x02081D30 2c009fe5 = ldr r0, [pc, #0x2c] -> word at 0x02081D64
        r = fake_rom({0x02081D30: 0xE59F002C, 0x02081D64: 0x0021000C})
        self.assertEqual(r.ldr_literal(0x02081D30), 0x21000C)
        r = fake_rom({0x100: 0xE51F0004, 0x104: 0xAB})   # negative offset: pc+8-4
        self.assertEqual(r.ldr_literal(0x100), 0xAB)

    def test_mov_imm(self):
        r = fake_rom({0: 0xE3A0007A, 4: 0xE3A0102B, 8: 0xE3A0072A})
        self.assertEqual((r.mov_imm(0), r.mov_imm(4)), (0x7A, 0x2B))
        with self.assertRaises(ValueError):
            r.mov_imm(8)   # rotated immediate, not a plain imm8

    def test_expect_words_refuses_other_bytes(self):
        r = fake_rom({0x10: 0xE3A02000, 0x14: 0xE1A00001})
        V.expect_words(r, [(0x10, 0xE3A02000, "mov r2, #0"), (0x14, 0xE1A00001, "mov r0, r1")], None)
        with self.assertRaises(ValueError):
            V.expect_words(r, [(0x14, 0xE1A00002, "mov r0, r2")], None)

    def test_resolve_hit(self):
        disp = {"rows": [{"sound_name": "SE_HIT", "pair": ["0x210000", "0x210013"]}] * 16}
        table = [{"effect": "0x060440"}] * 6
        self.assertEqual(V.resolve_hit(-1, disp, table), {"kind": "none"})
        self.assertEqual(V.resolve_hit(0, disp, table)["pair"], ["0x210000", "0x210013"])
        self.assertEqual(V.resolve_hit(0x45, disp, table)["record"], {"effect": "0x060440"})
        self.assertIsNone(V.resolve_hit(0x46, disp, table)["record"])
        self.assertEqual(V.resolve_hit(20, disp, table), {"kind": "out of table"})

    def test_hit_boundary_at_0x40(self):
        disp = {"rows": [{"sound_name": "SE_HIT", "pair": ["0x210000", "0x210013"]}] * 16}
        table = [{"effect": "0x060440"}]
        self.assertEqual(V.resolve_hit(0x3F, disp, table), {"kind": "out of table"})
        self.assertEqual(V.resolve_hit(0x40, disp, table), {"kind": "per-character", "record": table[0]})

    def test_text_boundary_at_0x40(self):
        disp = {"rows": []}
        table = [{"effect": "0x060440"}]
        self.assertIsNone(V.resolve_text(-1, disp, table))
        self.assertEqual(V.resolve_text(0, disp, table), "0x240000")
        self.assertEqual(V.resolve_text(0x3F, disp, table), "0x24003f")
        self.assertEqual(V.resolve_text(0x40, disp, table), {"kind": "per-character", "record": table[0]})


@unittest.skipUnless(HAVE_DATA, "needs jus_files (ROM dump, ChrArc.aar, efc/, chrbin/, SDAT)")
class RealBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = json.loads(json.dumps(V.build()))

    def test_dispatch_tables(self):
        rows = self.d["hit_dispatch"]["rows"]
        self.assertEqual([r["sound"] for r in rows],
                         [0xE, 0xF] + [0x10] * 5 + [0x11] * 5 + [0x3A, 0x3A, 0xE, 0xE])
        self.assertEqual((rows[0]["sound_name"], rows[0]["pair"]), ("SE_HIT", ["0x210000", "0x210013"]))
        self.assertEqual(rows[11]["pair"], ["0x21000b", "0x21001e"])
        self.assertEqual((rows[12]["sound_name"], rows[12]["pair"]), ("SE_KABOOM", ["0x23000e"] * 2))
        self.assertEqual((rows[14]["pair"], rows[15]["pair"]), (["0x220010"] * 2, ["0x230014"] * 2))
        self.assertEqual(set(self.d["hit_dispatch"]["callers"].values()), {"0x02153ce8"})

    def test_guard_and_clash_sites(self):
        s = {r["what"]: r for r in self.d["spawn_sites"]}
        g = s["guard spark"]
        self.assertEqual((g["effect"], g["is_spawn_call"], g["sound"]["name"]), ("0x21000c", True, "SE_GUARD"))
        clash = [r for r in self.d["spawn_sites"] if r["what"].startswith("clash")]
        self.assertEqual(sorted(r["effect"] for r in clash), ["0x21000d", "0x21000e"])
        self.assertTrue(all(r["is_spawn_call"] and r["sound"]["name"] == "SE_SOUSAI" for r in clash))
        ko = {r["effect"]: r for r in self.d["spawn_sites"] if r["what"].startswith("KO")}
        self.assertEqual(sorted(ko), ["0x21000f", "0x210010"])
        # 0x210010: the helper 0x0215F6E4 is itself a spawn wrapper; r2 = 0
        # takes its 0x0215F718 path, whose bl at 0x0215F73C is the spawn.
        k = ko["0x210010"]
        self.assertEqual((k["call_target"], k["is_spawn_call"]), ("0x0215f6e4", True))
        self.assertEqual(k["via"], [{"call": "0x0215f73c", "call_target": "0x0206c7fc"}])
        # 0x21000F: one hop on it reaches 0x02023894, a lookup, not the spawn.
        k = ko["0x21000f"]
        self.assertEqual((k["call_target"], k["is_spawn_call"]), ("0x02159b8c", False))
        self.assertEqual(k["via"], [{"call": "0x02159ba0", "call_target": "0x02023894"}])
        self.assertTrue(all(r["via"] == [] for r in self.d["spawn_sites"] if not r["what"].startswith("KO")))

    def test_seq_battle_names(self):
        n = {r["id"]: r["name"] for r in self.d["seq_battle"]}
        self.assertEqual(len(n), 87)
        self.assertEqual((n["0x0e"], n["0x2b"], n["0x43"], n["0x01"]), ("SE_HIT", "SE_GUARD", "SE_DRON", "SE_KO"))

    def test_kakashi_hit_records(self):
        t = self.d["character_effect_tables"]["na_b_04"]
        self.assertEqual(t[5], {"index": "0x45", "effect": "0x06044a", "slot": 1, "sound": "0x0e"})
        r = {x["record"]: x for x in self.d["hit_records"]["kakashi"]}
        self.assertEqual([r[i]["hit_effect"] for i in (1, 2, 3, 13, 14)], [0, 0, 1, 0x45, 0x45])
        self.assertEqual(r[13]["effect"]["record"]["effect"], "0x06044a")

    def test_kakashi_neutral_y(self):
        y = next(m for m in self.d["moves"]["kakashi"] if m["anim"] == "0x1f")
        self.assertEqual(y["move"], "Y")
        self.assertEqual([(s["frame"], s["effect"], s["x"], s["y"]) for s in y["spawns"]],
                         [(0, "0x060442", 0, 0), (6, "0x230000", 0, 1)])
        self.assertEqual([(s["frame"], s["name"]) for s in y["sounds"]],
                         [(0, "SE_DRON"), (6, "SE_DASH"), (15, "SE_HVYFURI")])

    def test_specials_carry_move_koma_archive_and_hits(self):
        m = {(c, r["anim"]): r for c in V.CHARS for r in self.d["moves"][c]}
        beam = m[("kakashi", "0x29")]
        self.assertEqual((beam["move"], beam["koma"], beam["archive"], beam["koma_archive"]),
                         ("X", 4, "chr/na_b_04.aar", "chr/na_b_04_4.aar"))
        self.assertEqual([(s["frame"], s["effect"]) for s in beam["spawns"]], [(8, "0x060460")])
        self.assertEqual([(h["record"], h["kind"]) for h in beam["hits"]], [(19, 4)])
        dogs = m[("kakashi", "0x2a")]
        self.assertEqual([(h["record"], h["kind"]) for h in dogs["hits"]], [(20, 4), (21, 4), (22, 4), (23, 4)])
        gun = m[("yusuke", "0x2d")]
        self.assertEqual((gun["move"], gun["koma"], gun["koma_archive"]), ("X", 6, "chr/yh_b_01_6.aar"))
        self.assertEqual([(h["record"], h["kind"]) for h in gun["hits"]], [(29, 4), (30, 4)])
        awake = m[("yusuke", "0x2e")]
        self.assertEqual([(h["record"], h["kind"]) for h in awake["hits"]],
                         [(16, 5), (17, 5), (18, 5), (19, 5), (20, 5), (21, 4)])
        # base rows: koma null, no hits; unmapped rows: no move, no koma, a reason
        y = m[("kakashi", "0x1f")]
        self.assertEqual((y["koma"], y["archive"], "hits" in y), (None, "chr/na_b_04.aar", False))
        self.assertIsNone(m[("kakashi", "0x18")]["move"])
        self.assertNotIn("koma", m[("kakashi", "0x18")])
        self.assertTrue(m[("kakashi", "0x18")]["why_no_move"])

    def test_pass_two_rows_carry_their_set_and_records(self):
        m = {(c, r["anim"]): r for c, rows in self.d["moves"].items() for r in rows}
        want = {("kakashi", "0x2b"): ("X", 5, [(24, 5), (25, 5), (26, 5), (27, 5)]),
                ("kakashi", "0x2c"): ("up X", 5, [(28, 4), (29, 4), (30, 4), (36, 4)]),
                ("kakashi", "0x2d"): ("X", 6, [(31, 5), (32, 5), (33, 5), (34, 5)]),
                ("kakashi", "0x2e"): ("up X", 6, [(35, 4)]),
                ("yusuke", "0x29"): ("X", 4, [(22, 4)]),
                ("yusuke", "0x2a"): ("up X", 4, [(23, 5), (24, 5)]),
                ("yusuke", "0x2b"): ("X", 5, [(25, 4), (26, 4)]),
                ("yusuke", "0x2c"): ("up X", 5, [(27, 5), (28, 5)])}
        for key, (move, koma, hits) in want.items():
            r = m[key]
            self.assertEqual((r["move"], r["koma"], r["koma_archive"]),
                             (move, koma, f"chr/{r['archive'][4:11]}_{koma}.aar"))
            self.assertEqual([(h["record"], h["kind"]) for h in r["hits"]], hits)
            self.assertNotIn("why_no_move", r)
            self.assertTrue(all(h["grade"] == "measured" or h["grade"].startswith("inferred")
                                for h in r["hits"]))

    def test_smoke_effect(self):
        e = self.d["effects"]["na_b_04"]["0x060442"]
        self.assertEqual((e["frames"], e["dtx"]), (18, "na_b_04_e00.dtx"))
        self.assertEqual([c for f, c in e["cells"] if f < e["frames"]], list(range(24, 31)))

    def test_sounds_cover_targets_and_notetracks(self):
        rows = {(r["seqarc_name"], r["name"]): r for r in self.d["sounds"]}
        for name in V.WAV_TARGETS + ("SE_ELECSHOCK", "SE_BEAM", "SE_AURA_TAME"):
            r = rows[("SEQ_BATTLE", name)]
            self.assertFalse(r["silent"] or r["hit_cap"] or r["problems"], name)
        self.assertTrue(rows[("SEQ_NA_B_04", "SE_CHR_KAKASHI_WATER")]["silent"])

    def test_eves_sound_names_are_wav_targets_and_lead_the_sounds_table(self):
        self.assertIn("SE_HVYSWDFURI", V.WAV_TARGETS)   # Eve's Y (0x1f) and anim 0x28
        self.assertIn("SE_TUKI", V.WAV_TARGETS)         # Eve's up B (0x22)
        self.assertEqual([r["name"] for r in self.d["sounds"][:len(V.WAV_TARGETS)]], list(V.WAV_TARGETS))
        used = {s["name"] for r in self.d["moves"]["eve"] for s in r["sounds"] if s["name"]}
        self.assertTrue({"SE_HVYSWDFURI", "SE_TUKI"} <= used)

    @unittest.skipUnless((V.REPO / "jus_files" / "extracted" / "vfx-sfx" / "render" / "wav"
                          / "manifest_battle.json").exists(), "needs the rendered WAVs")
    def test_the_rendered_battle_manifest_holds_every_wav_target_first(self):
        wav = V.REPO / "jus_files" / "extracted" / "vfx-sfx" / "render" / "wav"
        rows = json.loads((wav / "manifest_battle.json").read_text())
        self.assertEqual([r["name"] for r in rows[:len(V.WAV_TARGETS)]], list(V.WAV_TARGETS))
        self.assertTrue({"SE_HVYSWDFURI", "SE_TUKI"} <= {r["name"] for r in rows})   # Eve's Y and up B
        files = {r["name"]: f"{r['seqarc_name']}_{r['index']:02x}_{r['name']}.wav" for r in rows}
        for r in self.d["sounds"][:len(V.WAV_TARGETS)]:
            self.assertEqual(r["wav"], files[r["name"]])
            self.assertTrue((wav / r["wav"]).exists(), r["wav"])

    @unittest.skipUnless(HAVE_KIT, NEED_KIT)

    def test_every_eve_kit_anim_is_labelled_with_its_slot_or_set_move(self):
        kit = json.loads((V.REPO / "docs" / "rebuild" / "characters" / "eve.kit.json").read_text())
        rows = {r["anim"]: r for r in self.d["moves"]["eve"]}
        for km in kit["moves"]:
            r = rows[f"0x{int(km['jus_anim'], 16):02x}"]
            if km['slot']=='DREAM':
                self.assertIsNone(r['move'])
                self.assertIn('why_no_move',r)
                continue  # native boxes do not supply an animation/SFX capture
            self.assertEqual((r["move"], r["koma"]), (km["slot"], None), km["slot"])
            self.assertNotIn("why_no_move", r)
            self.assertEqual("label_src" in r, km["slot"] == "ULTIMATE", km["slot"])   # only the box-less one
        want = {"0x29": ("X", 4), "0x2a": ("up X", 4), "0x2b": ("X", 5), "0x2c": ("up X", 5)}
        for aid, (move, koma) in want.items():
            r = rows[aid]
            self.assertEqual((r["move"], r["koma"], r["koma_archive"]), (move, koma, f"chr/bc_b_01_{koma}.aar"))
        labelled = [a for a, r in rows.items() if r["move"] is not None]
        self.assertEqual(len(labelled), 16)
        self.assertEqual(sorted(a for a, r in rows.items() if r["move"] is None), ["0x19", "0x28"])
        self.assertTrue(rows["0x18"]["label_src"].startswith("kit jus_anim"))
        self.assertEqual(rows["0x02"]["move"], "dash")
        self.assertIn("INFERRED", rows["0x02"]["label_src"])

    @unittest.skipUnless(HAVE_KIT, NEED_KIT)

    def test_box_less_labels_reach_train_and_leave_the_captured_fighters_alone(self):
        m = {(c, r["anim"]): r for c, rows in self.d["moves"].items() for r in rows}
        self.assertEqual((m[("train", "0x18")]["move"], m[("train", "0x02")]["move"]), ("ULTIMATE", "dash"))
        self.assertTrue(m[("train", "0x18")]["label_src"].startswith("kit jus_anim"))
        for c in ("kakashi", "yusuke"):
            self.assertEqual(m[(c, "0x02")]["move"], "dash")
            self.assertIsNone(m[(c, "0x18")]["move"])
            self.assertFalse([a for (cc, a), r in m.items() if cc == c and "label_src" in r])

    @unittest.skipUnless(HAVE_KIT, NEED_KIT)

    def test_committed_json_matches_a_fresh_build(self):
        self.assertEqual(json.loads(V.OUT_JSON.read_text()), self.d)

    @unittest.skipUnless(HAVE_KIT, NEED_KIT)

    def test_doc_tables_are_the_generated_ones(self):
        doc = (V.REPO / "docs" / "rebuild" / "vfx-sfx.md").read_text()
        for t in V.render_tables(self.d):
            self.assertIn(t, doc, "regenerate with vfx_sfx_build.py --tables")


class NoBoxLabelTest(unittest.TestCase):
    """An anim with no hit boxes is labelled from the kit's jus_anim, or (the dash) from its shared state id."""

    KIT = {"moves": [
        {"slot": "ULTIMATE", "jus_anim": "0x18", "boxes": []},
        {"slot": "B", "jus_anim": "0x1e", "boxes": [{"rect": [1, 2, 3, 4]}]},
        {"slot": "DREAM", "jus_anim": None, "boxes": []},
        {"slot": "X", "boxes": []},
    ]}

    def test_only_a_box_less_kit_move_with_a_jus_anim_names_its_anim(self):
        self.assertEqual(V.kit_nobox_slots(self.KIT), {0x18: "ULTIMATE"})
        self.assertEqual(V.kit_nobox_slots(None), {})

    def test_the_ultimate_takes_its_slot_name_and_a_kit_source(self):
        move, src = V.nobox_label("eve", 0x18, self.KIT)
        self.assertEqual(move, "ULTIMATE")
        self.assertTrue(src.startswith("kit jus_anim"), src)
        self.assertNotIn("captured", src.replace("no capture", ""))

    def test_only_a_listed_fighter_takes_its_kit_labels(self):
        self.assertIn("eve", V.at.KIT_LABELS)
        self.assertIn("train", V.at.KIT_LABELS)
        for char in ("kakashi", "yusuke", "someone-new"):
            self.assertIsNone(V.nobox_label(char, 0x18, self.KIT), char)

    def test_a_kit_move_with_boxes_or_an_unknown_anim_gets_no_label(self):
        self.assertIsNone(V.nobox_label("eve", 0x1E, self.KIT))
        self.assertIsNone(V.nobox_label("eve", 0x19, self.KIT))
        self.assertIsNone(V.nobox_label("eve", 0x28, None))

    def test_the_dash_of_a_fighter_with_no_dash_capture_is_inferred(self):
        move, src = V.nobox_label("eve", 0x02, None)
        self.assertEqual(move, "dash")
        self.assertIn("INFERRED", src)
        self.assertIn("state anim id 0x02, captured on Kakashi and Yusuke; not captured for Eve", src)

    def test_a_fighter_with_a_dash_capture_keeps_the_captured_label_and_no_source(self):
        self.assertIsNone(V.nobox_label("kakashi", 0x02, None))
        self.assertEqual(V.move_label("kakashi", 0x02, None), ("dash", None, None))
        self.assertEqual(V.move_label("yusuke", 0x02, None), ("dash", None, None))

    def test_a_box_capture_beats_a_kit_label(self):
        kit = {"moves": [{"slot": "ZZZ", "jus_anim": "0x1e", "boxes": []}]}
        self.assertEqual(V.move_label("eve", 0x1E, kit), ("B", None, None))
        self.assertEqual(V.move_label("eve", 0x18, self.KIT)[:2], ("ULTIMATE", None))
        self.assertEqual(V.move_label("eve", 0x19, self.KIT), (None, None, None))


class CharacterArgumentTest(unittest.TestCase):
    """The roster is an argument (tracker item jus-analysis-decoders-chr-arg-46dd)."""

    def test_the_builder_names_no_character_in_code(self):
        import ast
        tree = ast.parse(Path(SCRIPT).read_text())
        docs = {id(n.body[0].value) for n in ast.walk(tree)
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        hits = [n.value for n in ast.walk(tree)
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs
                and re.search(r"kakashi|yusuke|na_b_|yh_b_|NA_B", n.value, re.I)]
        self.assertEqual(hits, [])

    def test_effect_sources_follow_the_prefixes_and_skip_missing_koma_archives(self):
        chars = {"a": {"chr_b": 1, "prefix": "na_b_04"}, "b": {"chr_b": 2, "prefix": "bc_b_01"}}
        have = {"na_b_04", "na_b_04_4", "na_b_04_5", "na_b_04_6", "bc_b_01", "bc_b_01_4", "bc_b_01_5"}
        self.assertEqual(V.effect_sources(chars, exists=have.__contains__),
                         ["na_b_04", "na_b_04_4", "na_b_04_5", "na_b_04_6",
                          "bc_b_01", "bc_b_01_4", "bc_b_01_5",
                          "comm_a", "comm_b", "comm_c", "comm_g"])
        with self.assertRaisesRegex(SystemExit, "bc_b_01"):
            V.effect_sources(chars, exists=lambda s: s != "bc_b_01")

    def test_sound_archives_come_from_the_resolved_characters(self):
        chars = {"a": {"chr_b": 1, "prefix": "x", "sound_seqarc": "SEQ_X"},
                 "b": {"chr_b": 2, "prefix": "y"}}
        self.assertEqual(V.sound_archives(chars), ["SEQ_X"])

    @unittest.skipUnless(HAVE_DATA, "needs jus_files")
    @unittest.skipUnless(HAVE_KIT, NEED_KIT)
    def test_check_passes_for_the_roster_each_roster_character_and_a_new_one(self):
        for argv in ([], ["--char", "kakashi"], ["--char", "yusuke"],
                     ["--char", "eve", "--chr-b", "37"]):
            self.assertEqual(V.main(["--check", *argv]), 0, argv)

    @unittest.skipUnless(HAVE_DATA, "needs jus_files")
    def test_a_wrong_chr_b_fails_the_check(self):
        for argv in (["--char", "eve", "--chr-b", "36", "--prefix", "bc_b_01"],
                     ["--char", "kakashi", "--chr-b", "24", "--prefix", "na_b_04"]):
            with self.assertRaises(SystemExit, msg=argv):
                V.main(["--check", *argv])

    @unittest.skipUnless(HAVE_DATA, "needs jus_files")
    def test_a_stale_committed_entry_fails_that_characters_check_only(self):
        doc = json.loads(V.OUT_JSON.read_text())
        doc["moves"]["yusuke"][0]["frames"] += 1
        with tempfile.TemporaryDirectory() as d:
            stale = Path(d) / "vfx-sfx.json"
            stale.write_text(json.dumps(doc))
            self.assertEqual(V.main(["--check", "--out", str(stale), "--char", "yusuke"]), 1)
            self.assertEqual(V.main(["--check", "--out", str(stale), "--char", "kakashi"]), 0)
            self.assertEqual(V.main(["--check", "--out", str(stale)]), 1)

    @unittest.skipUnless(HAVE_DATA, "needs jus_files")
    def test_writing_a_selection_over_the_committed_file_is_refused(self):
        with self.assertRaisesRegex(SystemExit, "--out"):
            V.main(["--char", "eve", "--chr-b", "37"])


if __name__ == "__main__":
    unittest.main()
