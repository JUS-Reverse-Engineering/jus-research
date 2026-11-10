"""Reject incomplete or forged replay input and component provenance."""
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('legacy_tests', Path(__file__).with_name('test_validate_capture.py'))
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)
v = legacy.v


class NativeReplayValidation(unittest.TestCase):
    def setUp(self):
        self.base = legacy.NativeValidatorTest('test_valid')
        self.base.setUp()
        self.root = self.base.root
        self.watches = [{'name': 'component', 'chain': [0x02100000, 4, 8],
                         'offset': 2, 'len': 4, 'optional': True}]
        (self.root / 'schema.json').write_text(json.dumps({'version': 2, 'frames': 2, 'watch_count': 1}))
        (self.root / 'input-schedule.tsv').write_text('sequence\tkey_mask\n0\t3967\n1\t4095\n')
        (self.root / 'watches.tsv').write_text('address\tlength\toffsets\toffset\toptional\n34603008\t4\t4,8\t2\t1\n')
        (self.root / 'frames.tsv').write_text(
            'sequence\tnds_frame\tstart_tick\tend_tick\tkey_mask\taudio_offset\taudio_count\tram_hex\theld_left\theld_right\twatch_present\twatch_addresses\twatch_paths\n'
            '0\t77\t100\t2148\t3967\t0\t2\t07000000\t0\t0\t1\t34603530\t34603008:34603264,34603268:34603520\n'
            '1\t78\t2148\t4196\t4095\t2\t2\t00000000\t3\t4\t0\t0\t34603008:34603264,34603268:0\n')

    def tearDown(self):
        self.base.tearDown()

    def check(self):
        return v.validate(self.root, 2, self.watches, [3967, 4095])

    def change(self, old, new):
        p = self.root / 'frames.tsv'
        self.assertIn(old, p.read_text())
        p.write_text(p.read_text().replace(old, new))

    def test_present_then_absent_component_retains_path_and_null_value(self):
        result = self.check()
        self.assertEqual(result['rows'][0]['w']['component'], 7)
        self.assertIsNone(result['rows'][1]['w']['component'])
        self.assertEqual(result['rows'][0]['watch_resolutions']['component']['address'], 0x0210020A)

    def test_shifted_input_schedule_rejected(self):
        with self.assertRaises(ValueError):
            v.validate(self.root, 2, self.watches, [4095, 3967])

    def test_missing_version_rejected(self):
        (self.root / 'schema.json').unlink()
        with self.assertRaises(ValueError): self.check()

    def test_missing_chain_proof_rejected(self):
        self.change('34603008:34603264,34603268:34603520', '-')
        with self.assertRaises(ValueError): self.check()

    def test_forged_resolved_address_rejected(self):
        self.change('\t1\t34603530\t', '\t1\t34603531\t')
        with self.assertRaises(ValueError): self.check()

    def test_forged_absence_rejected(self):
        self.change('\t1\t34603530\t', '\t0\t0\t')
        with self.assertRaises(ValueError): self.check()

    def test_nonzero_absent_padding_rejected(self):
        self.change('\t00000000\t3\t4\t0', '\t01000000\t3\t4\t0')
        with self.assertRaises(ValueError): self.check()

    def test_nonzero_invalid_pointer_is_not_absence(self):
        self.change('34603268:0', '34603268:16777216')
        with self.assertRaises(ValueError): self.check()

    def test_wrong_pointer_read_address_rejected(self):
        self.change('34603268:34603520', '34603272:34603520')
        with self.assertRaises(ValueError): self.check()

    def test_wrong_registered_recipe_rejected(self):
        p = self.root / 'watches.tsv'; p.write_text(p.read_text().replace('4,8', '4,4'))
        with self.assertRaises(ValueError): self.check()

    def test_truncated_expected_schedule_rejected(self):
        with self.assertRaises(ValueError): v.validate(self.root, 2, self.watches, [3967])

    def test_non_boolean_optional_registration_rejected(self):
        p = self.root / 'watches.tsv'; p.write_text(p.read_text().replace('\t2\t1\n', '\t2\t2\n'))
        with self.assertRaises(ValueError): self.check()

    def test_non_boolean_expected_optional_rejected(self):
        self.watches[0]['optional'] = 'false'
        with self.assertRaises(ValueError): self.check()

    def test_non_integer_expected_address_rejected(self):
        self.watches[0]['chain'][0] = float(self.watches[0]['chain'][0])
        with self.assertRaises(ValueError): self.check()

    def test_non_integer_expected_length_rejected(self):
        self.watches[0]['len'] = 4.0
        with self.assertRaises(ValueError): self.check()

    def test_non_integer_expected_frames_rejected(self):
        with self.assertRaises(ValueError): v.validate(self.root, 2.0, self.watches, [3967, 4095])

    def legacy_fixture(self):
        self.base.tearDown(); self.base.setUp()
        self.root, self.watches = self.base.root, self.base.watches

    def test_v2_frame_columns_cannot_downgrade_without_schema(self):
        self.legacy_fixture()
        p = self.root / 'frames.tsv'; lines = p.read_text().splitlines()
        p.write_text(lines[0] + '\twatch_present\twatch_addresses\twatch_paths\n' +
                     ''.join(line + '\t000\t1,2,3\t-;-;-\n' for line in lines[1:]))
        with self.assertRaises(ValueError): v.validate(self.root, 2, self.watches, 4095)

    def test_v2_registration_cannot_downgrade_without_schema(self):
        self.legacy_fixture()
        p = self.root / 'watches.tsv'; lines = p.read_text().splitlines()
        p.write_text(lines[0] + '\toffsets\toffset\toptional\n' +
                     ''.join(line + '\t\t0\t0\n' for line in lines[1:]))
        with self.assertRaises(ValueError): v.validate(self.root, 2, self.watches, 4095)

    def test_v2_schedule_file_cannot_downgrade_without_schema(self):
        self.legacy_fixture()
        (self.root / 'input-schedule.tsv').write_text('sequence\tkey_mask\n0\t4095\n1\t4095\n')
        with self.assertRaises(ValueError): v.validate(self.root, 2, self.watches, 4095)

    def test_legacy_read_crossing_ram_end_rejected(self):
        self.legacy_fixture(); self.watches[0]['addr'] = 0x023FFFFF
        p = self.root / 'watches.tsv'; p.write_text(p.read_text().replace('34603008', '37748735'))
        with self.assertRaises(ValueError): v.validate(self.root, 2, self.watches, 4095)

    def test_unsupported_legacy_final_offset_rejected(self):
        self.legacy_fixture(); self.watches[0]['offset'] = 1
        with self.assertRaises(ValueError): v.validate(self.root, 2, self.watches, 4095)

    def test_extra_unnamed_frame_fields_rejected(self):
        self.legacy_fixture()
        p = self.root / 'frames.tsv'; lines = p.read_text().splitlines()
        p.write_text(lines[0] + '\n' + ''.join(line + '\t0\t123\t-\n' for line in lines[1:]))
        with self.assertRaises(ValueError): v.validate(self.root, 2, self.watches, 4095)

    def test_extra_unnamed_watch_fields_rejected(self):
        self.legacy_fixture()
        p = self.root / 'watches.tsv'; lines = p.read_text().splitlines()
        p.write_text(lines[0] + '\n' + ''.join(line + '\t7\n' for line in lines[1:]))
        with self.assertRaises(ValueError): v.validate(self.root, 2, self.watches, 4095)

    def test_extra_unnamed_schedule_fields_rejected(self):
        p = self.root / 'input-schedule.tsv'; p.write_text(p.read_text().replace('0\t3967\n', '0\t3967\t123\n'))
        with self.assertRaises(ValueError): self.check()

    def test_missing_audio_option_field_rejected_as_validation_error(self):
        p = self.root / 'audio-options.tsv'; p.write_text(p.read_text().replace('1024\t0\t1\t1\n', '1024\t0\t1\n'))
        with self.assertRaises(ValueError): self.check()


if __name__ == '__main__':
    unittest.main()
