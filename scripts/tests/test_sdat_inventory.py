import importlib.util
import os
import struct
import sys
import unittest
from pathlib import Path

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis", "sdat_inventory.py")
SPEC = importlib.util.spec_from_file_location("sdat_inventory", SCRIPT)
S = importlib.util.module_from_spec(SPEC)
sys.modules["sdat_inventory"] = S
SPEC.loader.exec_module(S)

SDAT = Path(SCRIPT).resolve().parents[2] / "jus_files" / "ripped_jus_files" / "sound" / "JS2_sound.sdat"


def symb_block(seqarcs):
    """A SYMB block whose only record is SEQARC: [(name, [sequence names])]."""
    head = 8 + 8 * 4
    rec = head
    body = bytearray(struct.pack("<I", len(seqarcs)))
    body += b"\0" * (8 * len(seqarcs))           # (name offset, sub-record offset) pairs
    strings = bytearray()
    subs = bytearray()
    pairs = []
    # sub-records first, then strings, all after the pair table
    after = rec + len(body)
    sub_offs = []
    for _, seqs in seqarcs:
        sub_offs.append(after + len(subs))
        subs += struct.pack("<I", len(seqs)) + b"\0" * (4 * len(seqs))
    str_base = after + len(subs)

    def add(s):
        o = str_base + len(strings)
        strings.extend(s.encode() + b"\0")
        return o

    for i, (name, seqs) in enumerate(seqarcs):
        pairs.append((add(name), sub_offs[i]))
        so = sub_offs[i] - after
        for j, sq in enumerate(seqs):
            struct.pack_into("<I", subs, so + 4 + 4 * j, add(sq))
    for i, (no, so) in enumerate(pairs):
        struct.pack_into("<II", body, 4 + 8 * i, no, so)
    recoffs = [0, rec, 0, 0, 0, 0, 0, 0]
    blk = b"SYMB" + b"\0\0\0\0" + struct.pack("<8I", *recoffs) + bytes(body) + bytes(subs) + bytes(strings)
    return blk[:4] + struct.pack("<I", len(blk)) + blk[8:]


class SeqarcStrideTest(unittest.TestCase):
    """SYMB's SEQARC record holds 8-byte entries (name, sub-record); a 4-byte
    stride reads entry i's name at index 2*i (the old bug)."""

    def test_names_and_sequence_names(self):
        blk = symb_block([("SEQ_A", ["SE_X", "SE_Y"]), ("SEQ_B", ["SE_Z"]), ("SEQ_C", [])])
        out = S.parse_symb(blk, 0)
        self.assertEqual(out["seqarc"], ["SEQ_A", "SEQ_B", "SEQ_C"])
        self.assertEqual(out["seqarc_seqs"], [["SE_X", "SE_Y"], ["SE_Z"], []])


@unittest.skipUnless(SDAT.exists(), "needs jus_files JS2_sound.sdat")
class RealSdatTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b = SDAT.read_bytes()
        cls.d = S.parse_sdat(cls.b)

    def test_seq_battle_is_seqarc_122_fat_61(self):
        d = self.d
        self.assertEqual(d["symb"]["seqarc"][122], "SEQ_BATTLE")
        self.assertEqual(S.seqarc_file_id(self.b, d, 122), 61)
        self.assertEqual(d["fat"][61][1], 4740)
        seqs = d["symb"]["seqarc_seqs"][122]
        self.assertEqual(len(seqs), 87)
        self.assertEqual((seqs[0x0E], seqs[0x2B], seqs[0x55]), ("SE_HIT", "SE_GUARD", "SE_EFXFLASH"))

    def test_old_misread_entry(self):
        # ASSETS.md's "SEQ_BATTLE = fileId 159" was entry 244's file.
        d = self.d
        self.assertEqual(d["symb"]["seqarc"][244], "SEQ_SK_S_21_2")
        self.assertEqual(S.seqarc_file_id(self.b, d, 244), 159)

    def test_ssar_records_use_bank_se_battle(self):
        d = self.d
        off, size = d["fat"][61]
        ssar = S.parse_ssar(self.b[off:off + size])
        self.assertEqual(len(ssar["records"]), 87)
        self.assertEqual({r["bank"] for r in ssar["records"]}, {55})
        self.assertEqual(d["symb"]["bank"][55], "BANK_SE_BATTLE")
        info = S.bank_info(self.b, d, 55)
        names = [d["symb"]["wavarc"][w] for w in info["wavarcs"] if w != 0xFFFF]
        self.assertEqual(names, ["WAVE_SE_BATTLE", "WAVE_SE_STATIC"])


if __name__ == "__main__":
    unittest.main()
