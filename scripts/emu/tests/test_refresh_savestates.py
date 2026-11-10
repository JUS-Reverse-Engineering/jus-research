import json
import os
import tempfile
import unittest

from refresh_savestates import deck_selection_steps, load_manifest, roster_matches


class RefreshSavestatesTests(unittest.TestCase):
    def test_manifest_requires_unique_named_decks_with_expected_rosters(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "refresh.json")
            with open(path, "w") as stream:
                json.dump({"states": [
                    {"state": "eda", "deck": 3, "roster": [66, 48, 12]},
                    {"state": "momo", "deck": 6, "roster": [67, 68, 32]},
                ]}, stream)

            entries = load_manifest(path)

        self.assertEqual(entries[1]["deck"], 6)
        self.assertEqual(entries[0]["roster"], [66, 48, 12])

    def test_deck_selection_moves_from_first_row_to_requested_deck(self):
        self.assertEqual(deck_selection_steps(1), [("A",)])
        self.assertEqual(deck_selection_steps(6),
                         [("DOWN",)] * 5 + [("A",)])

    def test_roster_match_requires_ordered_runtime_roster(self):
        self.assertTrue(roster_matches([67, 68, 32], [67, 68, 32]))
        self.assertFalse(roster_matches([67, 32, 68], [67, 68, 32]))


if __name__ == "__main__":
    unittest.main()
