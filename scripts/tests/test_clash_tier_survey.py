"""The clash-tier survey's decode seams (clash-tier-survey-2026-09-25).

Checks the three things the survey's table rests on, with no save state or
jus_files needed:

- the melonDS .mln reader maps 0x02000000 onto the NDSG section's main RAM;
- the node-flag model of arm9 0x0207D440 reproduces the node +0x14/+0x18
  words C5 read live (RESULTS.md, "The records the predictions use");
- the melee/spawned rule sorts ALMT references the way the doc says.
"""
import gzip
import importlib.util
import struct
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "docs/research/clash-tier-survey-2026-09-25/survey.py"
spec = importlib.util.spec_from_file_location("clash_tier_survey", SRC)
sv = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sv)


def fake_mln(ram_words, ram_size=0x400000, blocks=None):
    """A minimal MELN v14 blob: header, one NDSG section holding the console
    word and main RAM, then a DMA0 section so the section walk has a tail."""
    ram = bytearray(ram_size)
    for addr, val in ram_words.items():
        struct.pack_into("<I", ram, addr - 0x02000000, val)
    for addr, blob in (blocks or {}).items():
        ram[addr - 0x02000000:addr - 0x02000000 + len(blob)] = blob
    ndsg_body = struct.pack("<I", 0) + bytes(ram) + bytes(0x1000000 - ram_size)
    ndsg = b"NDSG" + struct.pack("<I", 16 + len(ndsg_body)) + bytes(8) + ndsg_body
    dma = b"DMA0" + struct.pack("<I", 16 + 4) + bytes(8) + bytes(4)
    body = ndsg + dma
    return b"MELN" + struct.pack("<HHII", 14, 0, 16 + len(body), 0) + body


class MlnReader(unittest.TestCase):
    def test_main_ram_maps_to_0x02000000(self):
        blob = fake_mln({0x02181B28: 0x022286E0, 0x02000000: 0xE7FFDEFF})
        ram = sv.Ram(sv.parse_mln(blob))
        self.assertEqual(ram.u32(0x02181B28), 0x022286E0)
        self.assertEqual(ram.u32(0x02000000), 0xE7FFDEFF)
        self.assertIsNone(ram.u32(0x02400000))

    def test_gzip_is_read_the_same(self):
        blob = fake_mln({0x02100000: 0x12345678})
        self.assertEqual(sv.parse_mln(gzip.compress(blob))[0x100000:0x100004],
                         struct.pack("<I", 0x12345678))

    def test_bad_magic_refuses(self):
        with self.assertRaises(ValueError):
            sv.parse_mln(b"NOPE" + bytes(64))

    def test_layout_detect_picks_test_play(self):
        L = sv.LAYOUTS["test-play"]
        ram = sv.Ram(sv.parse_mln(fake_mln({
            0x02181B28: 0x022286E0, L["FIGHTERS"]: 0x022286E0,
            L["MGR"]: L["MGR"] + 0x454})))
        self.assertEqual(sv.detect_layout(ram), "test-play")

    def test_layout_detect_refuses_neither(self):
        ram = sv.Ram(sv.parse_mln(fake_mln({0x02181B28: 0x022286E0})))
        with self.assertRaises(sv.SurveyError):
            sv.detect_layout(ram)


def entry(tier, e08):
    """A 20-byte moveData entry with only the two fields build_node() reads:
    byte +0x00 (the tier) and the +0x08 property word. Everything else is
    zero, so no real entry's bytes are copied here."""
    return bytes([tier]) + bytes(7) + struct.pack("<I", e08) + bytes(8)


# (tier, +0x08) of entries in na_b_04 (Kakashi) and yh_b_01 (Yusuke), as C5
# and table.md have them.
KAKASHI_B = entry(3, 0x0)
KAKASHI_SIDE_Y = entry(2, 0x20)
KAKASHI_AIR_Y = entry(2, 0x220)
KAKASHI_BEAM = entry(4, 0x420)
KAKASHI_DOG = entry(4, 0x200800)
YUSUKE_X_L2 = entry(4, 0x420)


class NodeModel(unittest.TestCase):
    """C5's live node words; record +0x34 is 1 on P1's fighter record and
    0x1001 on a P1 shot record (C5 RESULTS, the +0x14 column)."""

    def check(self, entry, r34, n14, n18):
        n = sv.build_node(entry, r34=r34)
        self.assertEqual((hex(n["n14"]), hex(n["n18"])), (hex(n14), hex(n18)))

    def test_kakashi_b_on_fighter(self):
        self.check(KAKASHI_B, 0x1, 0x10000001, 0x0)

    def test_kakashi_side_y(self):
        self.check(KAKASHI_SIDE_Y, 0x1001, 0x10001001, 0x1)

    def test_kakashi_air_y(self):
        self.check(KAKASHI_AIR_Y, 0x1001, 0x10001001, 0x5)

    def test_kakashi_beam(self):
        self.check(KAKASHI_BEAM, 0x1001, 0x10001001, 0x41)

    def test_kakashi_dog(self):
        self.check(KAKASHI_DOG, 0x1001, 0x10001001, 0x20080)

    def test_yusuke_x(self):
        self.check(YUSUKE_X_L2, 0x1001, 0x10001001, 0x41)

    def test_zero_tier_is_body_class(self):
        n = sv.build_node(bytes(20), r34=0x1)
        self.assertEqual(n["n14"], 0x20000001)

    def test_prop_bit1_sets_0x08000000(self):
        self.assertTrue(sv.build_node(entry(3, 0x2))["n14"] & 0x08000000)

    def test_prop_bit18_sets_0x100_and_bars_the_b_side(self):
        n = sv.build_node(entry(3, 1 << 18), r34=0x1)
        self.assertEqual(n["n14"], 0x10000100)
        self.assertTrue(n["n1C"] & 0x10000000)

    def test_prop_bit23_sets_0x100(self):
        self.assertTrue(sv.build_node(entry(3, 1 << 23))["n14"] & 0x100)

    def test_shot_class_sets_1c_bit27(self):
        self.assertTrue(sv.build_node(KAKASHI_BEAM, r34=0x1001)["n1C"] & 0x08000000)
        self.assertFalse(sv.build_node(KAKASHI_B, r34=0x1)["n1C"] & 0x08000000)


class BuiltinNodeModel(unittest.TestCase):
    """The id < 0x100 path of 0x0207D440 (0x0207D570-0x0207D66C) against
    live nodes: C5's H23 guard node on P2 Kakashi (+0x14 0x40000002), and
    the save states' fighter body (id 0) and id 9 nodes on a P1 record
    whose +0x3C is 0x0063C011."""

    def test_guard_id2_on_p2(self):
        n = sv.build_builtin_node(2, entry(7, 0), r34=0x2)
        self.assertEqual((n["tier"], hex(n["n14"]), hex(n["n18"])), (7, "0x40000002", "0x0"))

    def test_body_id0(self):
        n = sv.build_builtin_node(0, bytes(20), r34=0x1, r3C=0x0063C011)
        self.assertEqual((hex(n["n14"]), hex(n["n1C"])), ("0x20000001", "0x48efc011"))

    def test_id9_clears_side_and_0x10000(self):
        n = sv.build_builtin_node(9, bytes(20), r34=0x1, r3C=0x0063C011)
        self.assertEqual((hex(n["n14"]), hex(n["n1C"])), ("0x20000", "0x50feffff"))

    def test_id4_participates_from_its_entry(self):
        self.assertEqual(sv.build_builtin_node(4, entry(0, 0x20), r34=0x100)["n18"], 0x1)


def engine_tables():
    """{address: bytes} for the arm9 tables check_tables() and run() verify."""
    out = {}
    for base, table in ((sv.T14_ADDR, sv.T14), (sv.T14_ADDR + 0x80, sv.T18),
                        (sv.T14_ADDR + 0x100, sv.T1C)):
        out[base] = b"".join(struct.pack("<I", table.get(i, 0)) for i in range(32))
    for base, table in ((sv.A14_ADDR, sv.A14), (sv.B18_ADDR, sv.B18), (sv.C1C_ADDR, sv.C1C)):
        out[base] = b"".join(struct.pack("<I", v) for v in table)
    out[sv.BUILTIN_ADDR + 2 * 20] = entry(7, 0)          # the guard's tier
    return out


class FakeMoveRecords:
    """Stands in for move_records: one ALMT per col prefix, given as
    {prefix: [(anim_id, prop, value)]}."""

    def __init__(self, anims):
        self.anims = anims

    def motions(self, prefix):
        return [(f"chr/{prefix}.aar", prefix)] if prefix in self.anims else []

    def anim_record_uses(self, almt):
        return [(0, "SP01", aid, 1, prop, [(0, v)]) for aid, prop, v in self.anims[almt]]


class RunEndToEnd(unittest.TestCase):
    """run() and write_outputs() on one synthetic test-play state: P1 on
    table aa_b_01 (a tier-3 melee box and a tier-2 participating shot),
    P2 on zz_b_01, one live shot record and one built-in body node."""

    L = sv.LAYOUTS["test-play"]
    P1, P2 = 0x02228000, 0x02229000
    BASE1, BASE2 = 0x021BA000, 0x021BB000
    COL1 = entry(3, 0x0) + entry(2, 0x20)
    COL2 = entry(5, 0x400)

    def rec(self, i):
        return self.L["MGR"] + sv.REC_OFF + i * sv.REC_STRIDE

    def state(self):
        L, w = self.L, {}
        blocks = engine_tables()
        blocks[self.BASE1], blocks[self.BASE2] = self.COL1, self.COL2
        w[0x02181B28] = self.P1
        w[L["FIGHTERS"]], w[L["FIGHTERS"] + 4] = self.P1, self.P2
        w[L["MGR"]] = L["MGR"] + 0x454
        for i in range(sv.REC_COUNT):
            w[self.rec(i) + 0x40] = 0x200                  # not in use
        prm = {11: 0x02300000, 12: 0x02300100, 20: 0x02300200}
        for i, (obj, side, base, chrb) in {11: (self.P1, 1, self.BASE1, 23),
                                           12: (self.P2, 2, self.BASE2, 32)}.items():
            w[obj + 0x1A8] = obj + 0x400
            w[obj + 0x400 + 0x10] = self.rec(i)
            w[self.rec(i) + 0x34], w[self.rec(i) + 0x40] = side, 0x8
            w[self.rec(i) + 0x6C], w[prm[i] + 0x0C] = prm[i], base
            hp = L["P1REC"] if side == 1 else L["P2REC"]
            w[hp + 0x24] = 0x01 << 8                         # +0x25 bit 0: active
            w[hp + 0x28] = chrb << 8                         # +0x29 chr_b
        # P1's fighter record: the built-in body node (id 0), then its
        # melee box id 0x100
        n, n2 = 0x02310000, 0x02310080
        w[self.rec(11) + 0x08] = n
        w[n + 0x10], w[n + 0x14], w[n + 0x1C] = sv.BUILTIN_ADDR, 0x20000001, 0x48AFC000
        w[n + 0x24] = 0
        w[n] = n2
        m = sv.build_node(self.COL1[:20], r34=0x1)
        w[n2 + 0x10], w[n2 + 0x14], w[n2 + 0x18], w[n2 + 0x1C] = (
            self.BASE1, m["n14"], m["n18"], m["n1C"])
        w[n2 + 0x24] = 0x100 << 16
        # a P1 shot record (+0x34 0x1001) holding id 0x101
        w[self.rec(20) + 0x34], w[self.rec(20) + 0x40] = 0x1001, 0x8
        w[self.rec(20) + 0x6C], w[prm[20] + 0x0C] = prm[20], self.BASE1
        m = sv.build_node(self.COL1[20:], r34=0x1001)
        n = 0x02310100
        w[self.rec(20) + 0x08] = n
        w[n + 0x10], w[n + 0x14], w[n + 0x18], w[n + 0x1C] = (
            self.BASE1 + 20, m["n14"], m["n18"], m["n1C"])
        w[n + 0x24] = 0x101 << 16
        # a P2 shot record whose node doesn't match the model (+0x18 off)
        w[self.rec(21) + 0x34], w[self.rec(21) + 0x40] = 0x1002, 0x8
        w[self.rec(21) + 0x6C], w[prm[20] + 0x10 + 0x0C] = prm[20] + 0x10, self.BASE2
        m = sv.build_node(self.COL2, r34=0x1002)
        n = 0x02310200
        w[self.rec(21) + 0x08] = n
        w[n + 0x10], w[n + 0x14], w[n + 0x18], w[n + 0x1C] = (
            self.BASE2, m["n14"], m["n18"] ^ 0x1, m["n1C"])
        w[n + 0x24] = 0x100 << 16
        return fake_mln(w, blocks=blocks)

    def run_once(self, tmp):
        tmp = Path(tmp)
        jf = tmp / "jf"
        (jf / "chrbin/chr/col").mkdir(parents=True)
        (jf / "arm9").mkdir()
        (jf / "chrbin/chr/col/aa_b_01.bin").write_bytes(self.COL1)
        (jf / "chrbin/chr/col/zz_b_01.bin").write_bytes(self.COL2)
        arm9 = bytearray(0xA0000)
        for a, b in engine_tables().items():
            arm9[a - 0x02000000:a - 0x02000000 + len(b)] = b
        (jf / "arm9/arm9.bin").write_bytes(arm9)
        st = tmp / "states"
        st.mkdir()
        (st / "one.mln").write_bytes(self.state())
        out = tmp / "out"
        out.mkdir()
        mr = FakeMoveRecords({
            "aa_b_01": [(0x1e, "CollisionType0", 0x0), (0x1e, "CollisionType1", 0x100),
                        (0x3, "CollisionType1", 0x2),
                        (0x41, "CollisionType0", 0x101)],
            "zz_b_01": [(0x1e, "CollisionType1", 0x100)],
        })
        sv.run(jf, out, paths=[st / "one.mln"], mr=mr, root=st)
        return {n: (out / n).read_text() for n in sv.OUTPUTS}

    def test_outputs(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            first, second = self.run_once(a), self.run_once(b)
        self.assertEqual(first, second)                   # byte-stable
        t, live = first["table.md"], first["live.md"]
        self.assertIn("- states read: 1; tables: 2; entries: 3", t)
        self.assertIn("- entries by tier byte: 2: 1, 3: 1, 5: 1", t)
        self.assertIn("- entries by kind: melee: 2, spawned: 1", t)
        self.assertIn("- tier > 0, by kind and P: melee P0: 2, spawned P1: 1", t)
        self.assertIn("| 0 | 3 | 0x00000000 | 0x10000000 | 0x00000000 | 0x00200000 | 0 "
                      "| exc3/4 | melee | melee | aa_b_01:0x1e |", t)
        self.assertIn("| 1 | 2 | 0x00000020 | 0x10000000 | 0x00000001 | 0x00200000 | 1 "
                      "| - | spawned | spawned | aa_b_01:0x41 |", t)
        # the built-in section: id 2 is tier 7, named by one table's anim 0x3;
        # id 0 is live once on a fighter and matches the model
        self.assertIn("| 2 | 0x0209FC54 | 7 |", t)
        self.assertIn("1 tables: 0x3 x1", t)
        self.assertRegex(t, r"\| 0 \| 0x0209FC2C \|.*\| 1 \(1 ok\): fighter 1 \|")
        self.assertIn("| 20 | P1 shot | 0x00001001 |", live)
        self.assertIn("0x101 t2 0x10001001 0x00000001", live)
        self.assertIn("0x101 t2 0x10001001 0x00000001 0x08200000 (14/18 ok, 1C ok)", live)
        self.assertIn("| 21 | P2 shot | 0x00001002 |", live)
        self.assertIn("(14/18 DIFF, 1C ok)", live)
        out = t + first["table.tsv"] + live
        for e in (self.COL1[:20], self.COL1[20:], self.COL2, entry(7, 0)):
            self.assertNotIn(e.hex(), out)                # no raw entry bytes


class ColMatch(unittest.TestCase):
    def test_longest_match_wins_and_twins_join(self):
        base = 0x02100000
        long = bytes(range(1, 41))
        ram = sv.Ram(sv.parse_mln(fake_mln({})))
        ram.m = bytearray(ram.m)
        ram.m[base - 0x02000000:base - 0x02000000 + 40] = long
        cols = {"a_b_01": long[:20], "a_b_02": long, "a_b_03": long, "z": b"", "q": b"x" * 20}
        self.assertEqual(sv.match_col(ram, base, cols), ["a_b_02=a_b_03"])
        self.assertEqual(sv.match_col(ram, base + 4, cols), [])


class MeleeSpawnedRule(unittest.TestCase):
    """An animation whose CollisionType0 carries an authored id (>= 0x100)
    is a spawned element's; one whose CollisionType0 is built-in or absent
    is the fighter's."""

    def test_rule(self):
        anims = [
            ("a.aar", 0x1e, {"CollisionType0": {0x0}, "CollisionType1": {0x100}}),
            ("a.aar", 0x41, {"CollisionType0": {0x106}}),
            ("a.aar", 0x3d, {"CollisionType0": {0x12c}, "CollisionType1": {0x101}}),
            ("a.aar", 0x20, {"CollisionType1": {0x101}}),
        ]
        kinds = sv.classify_records(anims)
        self.assertEqual(kinds[0][0], "melee")
        self.assertEqual(kinds[6][0], "spawned")
        self.assertEqual(kinds[0x2c][0], "spawned")
        self.assertEqual(kinds[1][0], "both")
        self.assertNotIn(5, kinds)


if __name__ == "__main__":
    unittest.main()
