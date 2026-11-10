import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).with_name('replay_plan.py')


class ReplayPlanTests(unittest.TestCase):
    def helpers(self):
        self.assertTrue(path.exists(), 'reusable input schedule compiler is missing')
        spec = importlib.util.spec_from_file_location('replay_plan', path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    def test_guard_hold_release_and_followup_have_exact_native_boundaries(self):
        module = self.helpers()
        segments = [{'from': 10, 'to': 129, 'buttons': ['DOWN']},
                    {'from': 155, 'to': 157, 'buttons': ['B']}]
        masks = module.compile_masks(segments, 440)
        self.assertEqual(len(masks), 598)
        self.assertEqual(masks[:10], [4095] * 10)
        self.assertEqual(masks[10:130], [3967] * 120)
        self.assertEqual(masks[130:155], [4095] * 25)
        self.assertEqual(masks[155:158], [4093] * 3)
        self.assertEqual(masks[158:], [4095] * 440)
        self.assertEqual(module.compile_masks(segments, 440), masks)
        self.assertEqual(segments[0]['buttons'], ['DOWN'])

    def test_up_x_and_guard_x_preserve_complete_chords(self):
        module = self.helpers()
        masks = module.compile_masks([{'from': 0, 'to': 0, 'buttons': ['UP', 'X']},
                                      {'from': 2, 'to': 2, 'buttons': ['DOWN', 'X']}], 1)
        self.assertEqual(masks, [3007, 4095, 2943, 4095])

    def test_invalid_or_ambiguous_segments_are_rejected(self):
        module = self.helpers()
        for segments, tail in (([{'from': 0, 'to': 0, 'buttons': ['SIDE_X']}], 1),
            ([{'from': 0, 'to': 3, 'buttons': []}, {'from': 3, 'to': 4, 'buttons': []}], 1),
            ([{'from': -1, 'to': 0, 'buttons': []}], 1), ([], 4097), ([], 0)):
            with self.assertRaises(ValueError): module.compile_masks(segments, tail)

    def test_native_watch_arguments_preserve_chain_and_optional_null(self):
        module = self.helpers()
        watches = [{'name': 'direct', 'addr': 0x02100000, 'len': 4},
                   {'name': 'body', 'chain': [0x02100004, 4, 0], 'offset': 12, 'len': 56, 'optional': True}]
        wire = module.watch_arguments(watches)
        self.assertEqual(wire[1], {'address': 0x02100004, 'length': 56, 'offsets': [4, 0], 'offset': 12, 'optional': True})
        self.assertEqual(wire[0], {'address': 0x02100000, 'length': 4, 'offsets': [], 'offset': 0, 'optional': False})


if __name__ == '__main__':
    unittest.main()
