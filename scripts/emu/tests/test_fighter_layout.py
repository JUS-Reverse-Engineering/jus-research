"""fighter_layout: layout detection and fighter-table watch chains, against a fake RAM."""
import json
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fighter_layout as fl  # noqa: E402


class FakeRam:
    def __init__(self):
        self.mem = {}

    def put32(self, addr, value):
        self.mem.update({addr + i: b for i, b in enumerate(struct.pack('<I', value))})

    def peek(self, addr, n):
        return int.from_bytes(bytes(self.mem.get(addr + i, 0) for i in range(n)), 'little')


def ram_for(layout):
    ram = FakeRam()
    L = fl.LAYOUTS[layout]
    ram.put32(fl.P1_PTR, 0x02228E80)
    ram.put32(L['FIGHTERS'], 0x02228E80)
    ram.put32(L['FIGHTERS'] + 4, 0x0222DD80)
    ram.put32(L['MGR'], L['MGR'] + 0x454)
    return ram


class DetectLayout(unittest.TestCase):
    def test_captured_clean_train596_layout(self):
        fixture = json.loads(Path(__file__).with_name('train596-clean-layout.json').read_text())
        ram = FakeRam()
        for address, value in fixture['words'].items():
            ram.put32(int(address), value)
        try:
            detected = fl.detect_layout(ram.peek)
        except fl.LayoutError as exc:
            self.fail(str(exc))
        self.assertEqual(detected, fixture['expected_layout'])

    def test_live_record_head_can_advance_after_crates_are_removed(self):
        # j9q: raw clean Train 596 state, manager+0 moved from slot 0 to 4.
        for name in fl.LAYOUTS:
            for slot in (0, 4, 127):
                with self.subTest(layout=name, slot=slot):
                    ram = ram_for(name)
                    L = fl.LAYOUTS[name]
                    ram.put32(L['MGR'], L['MGR'] + 0x454 + slot * 0x188)
                    try:
                        detected = fl.detect_layout(ram.peek)
                    except fl.LayoutError as exc:
                        self.fail(str(exc))
                    self.assertEqual(detected, name)

    def test_live_record_head_must_be_an_aligned_member_of_the_inline_pool(self):
        L = fl.LAYOUTS['test-play']
        for head in (0, L['MGR'] + 0x454 - 0x188,
                     L['MGR'] + 0x454 + 128 * 0x188, L['MGR'] + 0x455):
            with self.subTest(head=head):
                ram = ram_for('test-play')
                ram.put32(L['MGR'], head)
                with self.assertRaises(fl.LayoutError):
                    fl.detect_layout(ram.peek)

    def test_each_layout_is_detected(self):
        for name in fl.LAYOUTS:
            self.assertEqual(fl.detect_layout(ram_for(name).peek), name)

    def test_no_match_refuses(self):
        ram = ram_for('dark-tournament')
        ram.put32(fl.P1_PTR, 0x02200000)
        with self.assertRaises(fl.LayoutError):
            fl.detect_layout(ram.peek)

    def test_manager_must_self_verify(self):
        ram = ram_for('test-play')
        ram.put32(fl.LAYOUTS['test-play']['MGR'], 0)
        with self.assertRaises(fl.LayoutError):
            fl.detect_layout(ram.peek)

    def test_two_matches_refuse(self):
        ram = ram_for('test-play')
        L = fl.LAYOUTS['dark-tournament']
        ram.put32(L['FIGHTERS'], 0x02228E80)
        ram.put32(L['MGR'], L['MGR'] + 0x454)
        with self.assertRaises(fl.LayoutError):
            fl.detect_layout(ram.peek)

    def test_probe_values_round_trip(self):
        for name in fl.LAYOUTS:
            ram = ram_for(name)
            values = {w['name']: ram.peek(w['addr'], w['len']) for w in fl.probe_watches()}
            self.assertEqual(fl.detect_layout(fl.peek_from_probe(values)), name)

    def test_probe_peek_refuses_unprobed_address(self):
        with self.assertRaises(KeyError):
            fl.peek_from_probe({})(0x02000000, 4)


class Watches(unittest.TestCase):
    def test_object_watches_start_at_the_fighter_table(self):
        for name, L in fl.LAYOUTS.items():
            ws = {w['name']: w for w in fl.fighter_watches(name)}
            self.assertEqual(ws['p1st']['chain'], [L['FIGHTERS'], 0x18])
            self.assertEqual(ws['p2st']['chain'], [L['FIGHTERS'] + 4, 0x18])
            self.assertEqual(ws['p1cell'], {'name': 'p1cell', 'chain': [L['FIGHTERS'], 0x1A8, 8, 4, 0x64, 0x4A], 'len': 2})
            self.assertEqual(ws['p1tex'], {'name': 'p1tex', 'chain': [L['FIGHTERS'], 0x1A8, 8, 4, 0x64, 0x20, 8], 'len': 4})
            self.assertEqual(ws['p2tex']['chain'][0], L['FIGHTERS'] + 4)
            self.assertEqual(ws['p1hp'], {'name': 'p1hp', 'addr': L['P1REC'] - 2, 'len': 4})
            self.assertEqual(ws['p2identity'], {'name': 'p2identity', 'addr': L['P2REC'] + 0x25, 'len': 5})
            self.assertEqual(ws['fighters'], {'name': 'fighters', 'addr': L['FIGHTERS'], 'len': 8})
            self.assertEqual(ws['p1ptr'], {'name': 'p1ptr', 'addr': fl.P1_PTR, 'len': 4})

    def test_the_victim_colprm_record_and_guard_flag_word_are_watched(self):
        # jus-o0nw: the guard-block hook logs r1 = the defender's M = [[obj+0x1A8]+0x10]; the watch names the victim's.
        # M+0x78 as a word: bit 26 (byte 3, 0x04) is the is-guarding flag (guard-sp.md 0.5).
        for name, L in fl.LAYOUTS.items():
            ws = {w['name']: w for w in fl.fighter_watches(name)}
            self.assertEqual(ws['p2colprm'], {'name': 'p2colprm', 'chain': [L['FIGHTERS'] + 4, 0x1A8, 0x10], 'len': 4})
            self.assertEqual(ws['p1colprm'], {'name': 'p1colprm', 'chain': [L['FIGHTERS'], 0x1A8, 0x10], 'len': 4})
            self.assertEqual(ws['p2flags'], {'name': 'p2flags', 'chain': [L['FIGHTERS'] + 4, 0x1A8, 0x10, 0x78], 'len': 4})
            self.assertEqual(ws['p2ground']['len'], 1)      # the 1-byte ground flag keeps its meaning

    def test_reaction_watches_read_the_victim_reaction_block(self):
        for name, L in fl.LAYOUTS.items():
            ws = fl.reaction_watches(name)
            self.assertEqual(ws, [{'name': 'p2rx', 'chain': [L['FIGHTERS'] + 4, 0xFC], 'len': 0x28}])
            names = {w['name'] for w in fl.fighter_watches(name)} | {w['name'] for w in fl.roster_watches(name)}
            self.assertFalse(names & {w['name'] for w in ws})

    def test_reaction_watches_fit_beside_the_body_profile(self):
        ws = fl.fighter_watches('test-play') + fl.roster_watches('test-play') + fl.reaction_watches('test-play')
        self.assertLessEqual(sum(w['len'] for w in ws), 512)
        self.assertEqual(len({w['name'] for w in ws}), len(ws))

    def test_reaction_watches_unknown_layout_refuses(self):
        with self.assertRaises(fl.LayoutError):
            fl.reaction_watches('nowhere')

    def test_no_object_literal_survives(self):
        for name in fl.LAYOUTS:
            for w in fl.fighter_watches(name):
                start = w['chain'][0] if 'chain' in w else w['addr']
                self.assertFalse(0x02220000 <= start < 0x02400000, f'{w["name"]} starts at a heap literal')

    def test_fits_the_native_budget(self):
        ws = fl.fighter_watches('test-play')
        self.assertLessEqual(sum(w['len'] for w in ws), 512)
        self.assertLessEqual(len(ws), 64)
        self.assertTrue(all(len(w.get('chain', [0, 0])) <= 9 for w in ws))
        self.assertEqual(len({w['name'] for w in ws}), len(ws))

    def test_unknown_layout_refuses(self):
        with self.assertRaises(fl.LayoutError):
            fl.fighter_watches('nowhere')
        with self.assertRaises(fl.LayoutError):
            fl.roster_watches('nowhere')

    def test_roster_peek_reads_what_the_roster_watches_hold(self):
        ram = ram_for('test-play')
        L = fl.LAYOUTS['test-play']
        ram.mem[L['P2REC'] + 0x50 * 3 + 0x29] = 77
        values = {w['name']: ram.peek(w['addr'], w['len']) if w['len'] <= 4 else
                  list(bytes(ram.mem.get(w['addr'] + i, 0) for i in range(w['len']))) for w in fl.roster_watches('test-play')}
        peek = fl.roster_peek('test-play', values)
        self.assertEqual(peek(L['P2REC'] + 0x50 * 3 + 0x29, 1), 77)
        with self.assertRaises(KeyError):
            peek(L['P2REC'] + 0x50 * 3 + 0x30, 1)
        with self.assertRaises(KeyError):
            fl.roster_peek('test-play', {})

    def test_table_check_rejects_a_stale_table(self):
        row = {'p1ptr': 0x02228E80, 'fighters': [0x80, 0x8E, 0x22, 0x02, 0, 0, 0, 0]}
        fl.check_table(row)
        with self.assertRaises(fl.LayoutError):
            fl.check_table(dict(row, p1ptr=0x02228E84))


if __name__ == '__main__':
    unittest.main()
