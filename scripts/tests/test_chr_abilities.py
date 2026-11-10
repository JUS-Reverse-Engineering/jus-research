"""Five-slot loader oracle, independent of exporter labels and count byte +2."""
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/analysis/chr_abilities.py"
BIN = ROOT / "jus_files/ripped_jus_files/bin"

# Hand-decoded full chr_b records. P223's instruction walk reads offsets 3..7;
# P224's catalogue dispatch excludes kind 2, including Eve's id 54.
PORT_ORACLE = {
    "eve": (37, "0102033601000018d700d8000401310180010101900101016801010188100101881000000f0021200c000a0432141400000099019a01000000000000", [1, 24]),
    "kakashi": (23, "0102020d23020000b800ba00d80014028801010198010101a80101018804010188040000312024100b00000023231e017a017b0100007c0100000000", [13, 35, 2]),
    "kenshin": (36, "00020201020000002101200122012c028801000098010000a8010000a0100000a01000000f002020313004001e19190100000d020e020f0200000000", [1, 2]),
    "komamen": (70, "0002050000000000360137013301be016801000040010000981000004010000040100000030000000000000064000000000000000000000000000000", []),
    "taikoubou": (68, "0102042f2e280000ed00ef003d00ac028801010198010101a8010101b8100101b81000000b000d0031000a0419191900bf01c001c101c20100000000", [47, 46, 40]),
    "train": (38, "0001021902000000d600d800e200320288010000980100006801000088100000881000000f00180030000804281414009c019d019e01000000000000", [25, 2]),
    "yusuke": (32, "000204262b2c000019011a010301260198010000a8010000b8010000a0100000a01000000f0005011010112028191400000000000000000000000000", [38, 43, 44]),
}


class AbilityDecoderTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "missing five-slot ability decoder")
        spec = importlib.util.spec_from_file_location("chr_abilities", SCRIPT)
        self.decoder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.decoder)
        self.catalogue = (BIN / "ability.bin").read_bytes()

    def test_seven_kits_against_hand_decoded_records(self):
        preserved = json.loads((ROOT / "docs/rebuild/chr-natures.json").read_text())
        rows = {row["chr_b"]: bytes.fromhex(row["raw"]) for row in preserved["characters"]}
        native = (BIN / "chr_b.bin").read_bytes()
        for fighter, (index, raw, expected) in PORT_ORACLE.items():
            with self.subTest(fighter=fighter):
                record = bytes.fromhex(raw)
                self.assertEqual(len(record), 60)
                self.assertEqual(record, rows[index])
                self.assertEqual(record, native[index * 60:(index + 1) * 60])
                self.assertEqual(self.decoder.decode_record(record, self.catalogue), expected)

    def test_sparse_zero_is_empty_not_terminator(self):
        record = bytearray(60)
        record[3:8] = bytes([9, 25, 0, 0, 12])
        self.assertEqual(self.decoder.decode_record(record, self.catalogue), [9, 25, 12])

    def test_byte_two_is_not_a_variable_slot_count(self):
        record = bytearray(60)
        record[3:8] = bytes([54, 1, 0, 0, 24])
        for alleged_count in (0, 1, 3, 6, 255):
            with self.subTest(alleged_count=alleged_count):
                record[2] = alleged_count
                record[8] = 9
                self.assertEqual(self.decoder.decode_record(record, self.catalogue), [1, 24])

    def test_kind_dispatch_comes_from_catalogue(self):
        record = bytearray(60)
        record[3:8] = bytes([38, 54, 1, 0, 24])
        self.assertEqual(self.decoder.decode_record(record, self.catalogue), [38, 1, 24])
        changed = bytearray(self.catalogue)
        changed[54 * 4] = 0
        self.assertEqual(self.decoder.decode_record(record, changed), [38, 54, 1, 24])
        changed[38 * 4] = 2
        self.assertEqual(self.decoder.decode_record(record, changed), [54, 1, 24])

    def test_runtime_additions_are_not_invented(self):
        record = bytearray(60)
        record[3:8] = bytes([9, 25, 0, 0, 12])
        # P223/P224: Luffy's live extra 14 comes from the +0x558 list.
        self.assertNotIn(14, self.decoder.decode_record(record, self.catalogue))

    def test_preserved_records_match_rom_for_entire_roster(self):
        preserved = json.loads((ROOT / "docs/rebuild/chr-natures.json").read_text())
        native = (BIN / "chr_b.bin").read_bytes()
        self.assertEqual(len(native), 74 * 60)
        for row in preserved["characters"]:
            index = row["chr_b"]
            raw = bytes.fromhex(row["raw"])
            self.assertEqual(raw, native[index * 60:(index + 1) * 60])
            self.assertTrue(all(type(i) is int for i in self.decoder.decode_record(raw, self.catalogue)))
        for index in (70, 71, 72, 73):
            self.assertEqual(self.decoder.decode_record(native[index * 60:(index + 1) * 60], self.catalogue), [])

    def test_malformed_inputs_fail(self):
        for record, catalogue in ((bytes(59), self.catalogue), (bytes(61), self.catalogue),
                                  (bytes(60), b""), (bytes(60), self.catalogue[:-1])):
            with self.subTest(record=len(record), catalogue=len(catalogue)):
                with self.assertRaises(ValueError):
                    self.decoder.decode_record(record, catalogue)
        record = bytearray(60)
        record[3] = 255
        with self.assertRaisesRegex(ValueError, "ability id"):
            self.decoder.decode_record(record, self.catalogue)
        record[3] = 1
        catalogue = bytearray(self.catalogue)
        catalogue[4] = 3
        with self.assertRaisesRegex(ValueError, "kind"):
            self.decoder.decode_record(record, catalogue)

    def test_static_proof_names_loader_and_resolves_cites(self):
        self.assertEqual(self.decoder.PROOF_GRADE, "STATIC")
        self.assertEqual(self.decoder.LOADER_ADDRESSES, (0x02077768, 0x02077818, 0x02077A74))
        for cite in self.decoder.PROOF_CITES:
            path, line = cite.rsplit(":", 1)
            self.assertLessEqual(int(line), len((ROOT / path).read_text().splitlines()))


if __name__ == "__main__":
    unittest.main()
