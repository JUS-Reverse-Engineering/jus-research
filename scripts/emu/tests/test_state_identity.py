"""state_identity: the savestate RAM image and the identity read, against synthetic RAM."""
import gzip
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import fighter_layout as fl  # noqa: E402
import state_identity as si  # noqa: E402

B = 0x02000000
KOMA = {520: {'chr_b': 23, 'panel': 4}, 521: {'chr_b': 23, 'panel': 5}, 776: {'chr_b': 32, 'panel': 6}}


def mln(ram, extra_sections=()):
    """A minimal melonDS savestate: header, then sections; NDSG holds a u32 console type and main RAM."""
    def section(magic, payload):
        return magic + struct.pack('<III', 16 + len(payload), 0, 0) + payload
    body = b''.join(section(m, p) for m, p in extra_sections) + section(b'NDSG', struct.pack('<I', 0) + bytes(ram))
    return b'MELN' + struct.pack('<HHII', 14, 0, 16 + len(body), 0) + body


class Ram:
    def __init__(self):
        self.b = bytearray(si.MAIN_RAM_SIZE)

    def put(self, addr, value, n):
        self.b[addr - B:addr - B + n] = value.to_bytes(n, 'little', signed=value < 0)

    def peek(self, addr, n):
        return int.from_bytes(self.b[addr - B:addr - B + n], 'little')


def battle(layout='dark-tournament', p1=(23, 520), p2=(32, 776), stage=32, items=0, com=0):
    r = Ram()
    L = fl.LAYOUTS[layout]
    objs = (0x02228E80, 0x0222DD80)
    r.put(fl.P1_PTR, objs[0], 4)
    r.put(L['FIGHTERS'], objs[0], 4)
    r.put(L['FIGHTERS'] + 4, objs[1], 4)
    r.put(L['MGR'], L['MGR'] + 0x454, 4)
    r.put(si.STAGE_SELECT, stage, 1)
    r.put(si.RULE_ITEMS, items, 1)
    r.put(si.COM_SETTING, com, 1)
    for k, (rec, (chr_b, koma)) in enumerate(((L['P1REC'], p1), (L['P2REC'], p2))):
        r.put(rec - 2, 9216, 2)
        r.put(rec, 9216, 2)
        r.put(rec + 0x25, 1, 1)                 # active flag
        r.put(rec + 0x29, chr_b, 1)
        r.put(rec - 0x0C, koma, 2)
        r.put(rec + 0x50 + 0x29, 118, 1)        # an inactive bench slot holding a garbage chr_b
        obj = objs[k]
        wrapper, colprm, el = obj + 0x400, obj + 0x500, obj + 0x600
        r.put(obj + 0x18, 0, 1)
        r.put(obj + 0x1A8, wrapper, 4)
        r.put(wrapper + 0x10, colprm, 4)
        r.put(colprm + 0x5C, el, 4)
        r.put(colprm + 0x78, 1, 1)
        r.put(el + 0x0C, 114688 + 32768 * k, 4)
        r.put(el + 0x10, 172031, 4)
    return r


class MlnRamTests(unittest.TestCase):
    def test_reads_main_ram_after_the_console_word(self):
        r = Ram()
        r.put(0x02181B28, 0x02228E80, 4)
        for blob in (mln(r.b, [(b'ARM9', b'\0' * 8)]), gzip.compress(mln(r.b))):
            self.assertEqual(si.RamImage(si.mln_ram(blob)).peek(0x02181B28, 4), 0x02228E80)

    def test_refuses_a_file_that_is_not_a_savestate(self):
        with self.assertRaises(si.IdentityError):
            si.mln_ram(b'NOPE' + b'\0' * 64)

    def test_refuses_a_savestate_without_main_ram(self):
        blob = b'MELN' + struct.pack('<HHII', 14, 0, 16, 0)
        with self.assertRaises(si.IdentityError):
            si.mln_ram(blob)


class RosterTests(unittest.TestCase):
    def test_read_roster_is_the_part_of_read_side_the_guard_watches(self):
        r = battle()
        L = fl.LAYOUTS['dark-tournament']
        r.put(L['P1REC'] + 0x25, 0, 1)             # p1's slot 0 benched, slot 2 active
        r.put(L['P1REC'] + 0x50 * 2 + 0x25, 1, 1)
        r.put(L['P1REC'] + 0x50 * 2 + 0x29, 23, 1)
        r.put(L['P1REC'] + 0x50 * 2, 4000, 2)
        r.put(L['P1REC'] + 0x50 * 2 - 2, 9216, 2)
        self.assertEqual(si.read_roster(r.peek, 'dark-tournament', 0),
                         {'active_slot': 2, 'chr_b': 23, 'hp': 4000, 'hp_max': 9216})
        side = si.read_side(r.peek, 'dark-tournament', 1, KOMA)
        self.assertEqual({k: side[k] for k in ('active_slot', 'chr_b', 'hp', 'hp_max')},
                         si.read_roster(r.peek, 'dark-tournament', 1))

    def test_read_roster_refuses_no_active_slot(self):
        r = battle()
        r.put(fl.LAYOUTS['dark-tournament']['P1REC'] + 0x25, 0, 1)
        with self.assertRaises(si.IdentityError):
            si.read_roster(r.peek, 'dark-tournament', 0)


class IdentityTests(unittest.TestCase):
    def test_reads_both_fighters_panel_stage_and_rules(self):
        ident = si.read_identity(battle().peek, KOMA)
        self.assertEqual(ident['layout'], 'dark-tournament')
        self.assertEqual(ident['stage'], 'dark-tournament')
        self.assertEqual(ident['items'], 0)
        self.assertEqual((ident['p1']['chr_b'], ident['p1']['koma'], ident['p1']['panel']), (23, 520, 4))
        self.assertEqual((ident['p2']['chr_b'], ident['p2']['panel']), (32, 6))
        self.assertEqual(ident['p1']['active_slot'], 0)
        self.assertEqual(ident['p1']['y_raw'], 172031)
        self.assertTrue(ident['p1']['hp_full'])
        self.assertTrue(ident['at_rest'])

    def test_a_fighter_mid_action_is_not_at_rest(self):
        r = battle()
        r.put(0x0222DD80 + 0x18, 9, 1)
        self.assertFalse(si.read_identity(r.peek, KOMA)['at_rest'])

    def test_a_koma_whose_chr_b_disagrees_is_refused(self):
        with self.assertRaises(si.IdentityError):
            si.read_identity(battle(p1=(23, 776)).peek, KOMA)

    def test_two_active_slots_are_refused(self):
        r = battle()
        r.put(fl.LAYOUTS['dark-tournament']['P1REC'] + 0x50 + 0x25, 1, 1)
        with self.assertRaises(si.IdentityError):
            si.read_identity(r.peek, KOMA)

    def test_hp_full_needs_both_fighters_at_full_hp(self):
        L = fl.LAYOUTS['dark-tournament']
        self.assertTrue(si.read_identity(battle().peek, KOMA)['hp_full'])
        for who, rec in (('p1', L['P1REC']), ('p2', L['P2REC'])):
            r = battle()
            r.put(rec, 9000, 2)                 # hurt below hp_max (9216)
            ident = si.read_identity(r.peek, KOMA)
            self.assertFalse(ident[who]['hp_full'], who)
            self.assertFalse(ident['hp_full'], f'only {who} hurt')

    def test_stage_and_cpu_are_unknown_outside_the_dark_tournament_layout(self):
        ident = si.read_identity(battle(layout='test-play').peek, KOMA)
        self.assertIsNone(ident['stage'])
        self.assertIsNone(ident['cpu'])

    def test_the_com_byte_names_the_cpu_setting(self):
        self.assertEqual([si.read_identity(battle(com=c).peek, KOMA)['cpu'] for c in range(4)],
                         ['idle', 'fight', 'guard', 'jump'])


class ExpectTests(unittest.TestCase):
    EXPECT = {'layout': 'dark-tournament', 'stage': 'dark-tournament', 'items': 0,
              'p1': {'chr_b': 23, 'panel': 4}, 'p2': {'chr_b': 32, 'panel': 6}, 'hp_full': True}

    def test_matching_identity_has_no_failures(self):
        self.assertEqual(si.check_expect(si.read_identity(battle().peek, KOMA), self.EXPECT), [])

    def test_each_mismatch_is_named(self):
        ident = si.read_identity(battle(p1=(23, 521), stage=0, items=1, com=2).peek, KOMA)
        fails = si.check_expect(ident, dict(self.EXPECT, cpu='idle'))
        self.assertEqual(sorted(f.split(':')[0] for f in fails), ['cpu', 'items', 'p1.panel', 'stage'])

    def test_hp_full_expectation_fails_when_only_p2_is_hurt(self):
        r = battle()
        r.put(fl.LAYOUTS['dark-tournament']['P2REC'], 9000, 2)
        fails = si.check_expect(si.read_identity(r.peek, KOMA), {'hp_full': True})
        self.assertEqual([f.split(':')[0] for f in fails], ['hp_full'])

    def test_floor_y_raw_passes_when_both_fighters_stand_on_it(self):
        ident = si.read_identity(battle().peek, KOMA)
        self.assertEqual(si.check_expect(ident, {'floor_y_raw': 172031}), [])

    def test_floor_y_raw_names_each_fighter_off_the_floor(self):
        r = battle()
        r.put(0x0222DD80 + 0x600 + 0x10, 170000, 4)          # P2's element y
        ident = si.read_identity(r.peek, KOMA)
        fails = si.check_expect(ident, {'floor_y_raw': 172031})
        self.assertEqual(len(fails), 1)
        self.assertTrue(fails[0].startswith('floor_y_raw: p2 y 170000'), fails)
        self.assertEqual(len(si.check_expect(ident, {'floor_y_raw': 170000})), 1)      # now it is P1 that is off
        r.put(0x02228E80 + 0x600 + 0x10, 170000, 4)
        self.assertEqual(len(si.check_expect(si.read_identity(r.peek, KOMA), {'floor_y_raw': 170000})), 0)

    def test_an_unknown_expect_key_is_refused(self):
        with self.assertRaises(si.IdentityError):
            si.check_expect(si.read_identity(battle().peek, KOMA), {'stagee': 'dark-tournament'})


class KomaTableTests(unittest.TestCase):
    def test_battle_panels_carry_chr_b_and_size(self):
        rec = struct.pack('<HHBBBBBBBB', 520, 187, 13, 3, 0, 23, 3, 0, 0, 0x30)
        helper = struct.pack('<HHBBBBBBBB', 521, 187, 13, 0, 2, 5, 0, 0, 0, 0x30)
        table = si.koma_table(rec + helper)
        self.assertEqual(table, {520: {'chr_b': 23, 'panel': 4}})


class Stage16Tests(unittest.TestCase):
    def test_native_stage_16_uses_its_verified_bg_cu_identity(self):
        r = battle(stage=16)
        identity = si.read_identity(r.peek, KOMA)
        self.assertEqual(identity['layout'], 'dark-tournament')
        self.assertEqual((identity['stage_byte'], identity['stage']), (16, 'bg-cu'))
        self.assertEqual(si.read_identity(battle(stage=17).peek, KOMA)['stage'], 'unknown-17')

    @unittest.skipUnless((Path(__file__).resolve().parents[3]/'kit/cases-v1.schema.json').exists(),
                         'needs a case schema that is not part of this repository')
    def test_all_case_stage_enums_accept_the_verified_bg_cu_fixture(self):
        import json
        schema = json.loads((Path(__file__).resolve().parents[3]/'kit/cases-v1.schema.json').read_text())
        enums = [value['properties']['stage']['enum'] for value in schema['$defs'].values()
                 if isinstance(value, dict) and 'stage' in value.get('properties', {})]
        self.assertEqual(len(enums), 3)
        for enum in enums:
            self.assertIn('bg-cu', enum)
            self.assertEqual(set(enum), {*si.STAGES.values(), 'test-play'})


if __name__ == '__main__':
    unittest.main()
