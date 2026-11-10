"""scripts/gdb/fxo_initializers.py: the ROM census of animation-id initializer paths (fxo-initializers/v1).

The census decodes jus_files/arm9 (arm9.bin and the battle-resident ov06, ov11, ov12). These tests fail, not skip, when jus_files
is missing: the committed census is only as good as its agreement with the ROM.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/gdb"))
import fxo_initializers as fi  # noqa: E402
sys.path.insert(0, str(ROOT / "scripts/tests"))
import _deps  # noqa: E402


@_deps.needs("capstone")
class CensusTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = fi.census(ROOT)
        cls.sites = {e: {s["lr"]: s for s in v["sites"]} for e, v in cls.data["entries"].items()}

    def test_committed_census_equals_the_rom(self):
        self.assertEqual(fi.OUT.read_text(), fi.dumps(self.data))
        self.assertEqual(fi.main(["--check"]), 0)

    def test_only_two_entries_take_an_animation_id(self):
        self.assertEqual(sorted(self.data["entries"]), ["0x02023894", "0x02023924"])
        self.assertEqual(sorted(self.data["bind"]["callers"]), ["0x0201E8E4", "0x0201ED54", "0x020238D0", "0x02023914"])
        self.assertEqual(len(self.sites["0x02023894"]), 93)
        self.assertEqual(len(self.sites["0x02023924"]), 5)

    def test_gn01_handler_reaches_the_ordinary_entry_with_any_id(self):
        gn01 = self.sites["0x02023894"]["0x0206CB8C"]
        self.assertTrue(gn01["shared_id_possible"])
        self.assertEqual((gn01["image"], gn01["call"]), ("arm9", "0x0206CB88"))
        self.assertTrue(self.sites["0x02023894"]["0x02158810"]["shared_id_possible"])     # ov06 constant 0x220003
        self.assertEqual(self.sites["0x02023894"]["0x02158810"]["why"], "constant id 0x220003")

    def test_fx_spawn_guard_and_constant_ids_exclude_shared_registrations(self):
        guarded = self.sites["0x02023894"]["0x0206C978"]
        self.assertFalse(guarded["shared_id_possible"])
        self.assertIn("0x0206C814", guarded["why"])
        self.assertTrue(self.sites["0x02023924"]["0x0206C888"]["shared_id_possible"])
        self.assertFalse(self.sites["0x02023894"]["0x02154979"]["shared_id_possible"])     # constant 0x5f0017
        admissible = fi.load()
        self.assertEqual(len(admissible[0x02023894]), 71)
        self.assertEqual(len(admissible[0x02023924]), 5)

    def test_thumb_return_addresses_carry_the_thumb_bit(self):
        lrs = [int(lr, 16) for lr, s in self.sites["0x02023894"].items() if s["mode"] == "thumb"]
        self.assertTrue(lrs and all(lr & 1 for lr in lrs))
        self.assertIn("0x0215528D", self.sites["0x02023894"])     # the recorded 0x5f00 UI ANIM rows

    def test_a_changed_opcode_refuses_the_census(self):
        original = fi.OPCODES[0x0206C814]
        try:
            fi.OPCODES[0x0206C814] = original ^ 1
            with self.assertRaisesRegex(ValueError, "another ROM"):
                fi.census(ROOT)
        finally:
            fi.OPCODES[0x0206C814] = original

    def test_a_changed_bind_caller_set_refuses_the_census(self):
        original = dict(fi.BIND_CALLERS)
        try:
            del fi.BIND_CALLERS[0x0201ED54]
            with self.assertRaisesRegex(ValueError, "bind 0x020239B0 callers changed"):
                fi.census(ROOT)
        finally:
            fi.BIND_CALLERS.clear()
            fi.BIND_CALLERS.update(original)

    def test_load_rejects_another_schema(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "census.json"
            path.write_text(json.dumps({"schema": "other", "entries": {}}))
            with self.assertRaisesRegex(ValueError, "fxo-initializers/v1"):
                fi.load(path)


if __name__ == "__main__":
    unittest.main()
