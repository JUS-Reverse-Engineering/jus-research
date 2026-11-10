"""oam_read: OAM entry decoder, affine groups, live capture plumbing, and --from-dump round trip.

All synthetic 1 KiB buffers. Nothing here touches the emulator or /tmp/jus_emu.
"""
import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import oam_read as oam  # noqa: E402


def blank():
    return bytearray(1024)


def put(buf, i, attr0=0, attr1=0, attr2=0, filler=0):
    struct.pack_into('<HHHH', buf, 8 * i, attr0, attr1, attr2, filler)


def attr0(y=0, rs=0, b9=0, mode=0, mosaic=0, c256=0, shape=0):
    return (y & 0xFF) | (rs << 8) | (b9 << 9) | (mode << 10) | (mosaic << 12) | (c256 << 13) | (shape << 14)


class TestDecodeBasics(unittest.TestCase):
    def test_blank_buffer_gives_128_default_entries(self):
        out = oam.decode_oam(bytes(blank()), 'main')
        self.assertEqual(len(out), 128)
        self.assertEqual([e['index'] for e in out], list(range(128)))
        e = out[0]
        self.assertEqual((e['width'], e['height']), (8, 8))
        self.assertFalse(e['hidden'])
        self.assertEqual(e['x'], 0)
        self.assertEqual(e['y'], 0)

    def test_wrong_length_rejected(self):
        with self.assertRaises(ValueError):
            oam.decode_oam(bytes(1023), 'main')
        with self.assertRaises(ValueError):
            oam.decode_affine(bytes(1025))

    def test_bad_engine_rejected(self):
        with self.assertRaises(ValueError):
            oam.decode_oam(bytes(blank()), 'bogus')

    def test_field_positions(self):
        buf = blank()
        # y=0x42, rs=0, b9=0, mode=2, mosaic=1, c256=1, shape=1
        # x=0x0AB, hflip=1, vflip=0, size=2
        # tile=0x123, priority=3, palette=0xA
        put(buf, 5, attr0(y=0x42, mode=2, mosaic=1, c256=1, shape=1),
            attr1=0xAB | (1 << 12) | (2 << 14), attr2=0x123 | (3 << 10) | (0xA << 12))
        e = oam.decode_oam(bytes(buf), 'main')[5]
        self.assertEqual(e['y'], 0x42)
        self.assertEqual(e['obj_mode'], 2)
        self.assertEqual(e['mosaic'], 1)
        self.assertEqual(e['color_256'], 1)
        self.assertEqual(e['shape'], 1)
        self.assertEqual(e['x'], 0xAB)
        self.assertEqual(e['hflip'], 1)
        self.assertEqual(e['vflip'], 0)
        self.assertEqual(e['size'], 2)
        self.assertEqual(e['tile'], 0x123)
        self.assertEqual(e['priority'], 3)
        self.assertEqual(e['palette'], 0xA)


class TestNegativeX(unittest.TestCase):
    def test_x_0x1f0_is_minus_16(self):
        buf = blank()
        put(buf, 0, attr1=0x1F0)
        self.assertEqual(oam.decode_oam(bytes(buf), 'main')[0]['x'], -16)

    def test_x_0x100_is_minus_256(self):
        buf = blank()
        put(buf, 0, attr1=0x100)
        self.assertEqual(oam.decode_oam(bytes(buf), 'main')[0]['x'], -256)

    def test_x_0x0ff_is_positive_255(self):
        buf = blank()
        put(buf, 0, attr1=0x0FF)
        self.assertEqual(oam.decode_oam(bytes(buf), 'main')[0]['x'], 255)

    def test_x_0x1ff_is_minus_1(self):
        buf = blank()
        put(buf, 0, attr1=0x1FF)
        self.assertEqual(oam.decode_oam(bytes(buf), 'main')[0]['x'], -1)


class TestYWrap(unittest.TestCase):
    def test_raw_y_kept_in_range(self):
        buf = blank()
        put(buf, 0, attr0=attr0(y=0xF0))
        self.assertEqual(oam.decode_oam(bytes(buf), 'main')[0]['y'], 0xF0)

    def test_y_240_wraps_to_minus_16(self):
        buf = blank()
        put(buf, 0, attr0=attr0(y=0xF0))
        self.assertEqual(oam.decode_oam(bytes(buf), 'main')[0]['y_signed'], -16)

    def test_y_191_stays_positive_and_192_wraps(self):
        buf = blank()
        put(buf, 0, attr0=attr0(y=160))
        put(buf, 1, attr0=attr0(y=191))
        put(buf, 2, attr0=attr0(y=192))
        out = oam.decode_oam(bytes(buf), 'main')
        self.assertEqual(out[0]['y_signed'], 160)
        self.assertEqual(out[1]['y_signed'], 191)
        self.assertEqual(out[2]['y_signed'], -64)


class TestShapeSize(unittest.TestCase):
    TABLE = {
        (0, 0): (8, 8), (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
        (1, 0): (16, 8), (1, 1): (32, 8), (1, 2): (32, 16), (1, 3): (64, 32),
        (2, 0): (8, 16), (2, 1): (8, 32), (2, 2): (16, 32), (2, 3): (32, 64),
    }

    def test_all_twelve_combos(self):
        self.assertEqual(len(self.TABLE), 12)
        for (shape, size), wh in self.TABLE.items():
            with self.subTest(shape=shape, size=size):
                buf = blank()
                put(buf, 7, attr0=attr0(shape=shape), attr1=size << 14)
                e = oam.decode_oam(bytes(buf), 'main')[7]
                self.assertEqual((e['width'], e['height']), wh)
                self.assertEqual(e['shape'], shape)
                self.assertEqual(e['size'], size)

    def test_prohibited_shape_3_has_no_size(self):
        buf = blank()
        for size in range(4):
            put(buf, 0, attr0=attr0(shape=3), attr1=size << 14)
            e = oam.decode_oam(bytes(buf), 'main')[0]
            self.assertIsNone(e['width'])
            self.assertIsNone(e['height'])


class TestHidden(unittest.TestCase):
    def test_plain_entry_with_bit9_is_hidden(self):
        buf = blank()
        put(buf, 3, attr0=attr0(rs=0, b9=1))
        self.assertTrue(oam.decode_oam(bytes(buf), 'main')[3]['hidden'])

    def test_rotscale_entry_with_bit9_is_double_size_not_hidden(self):
        buf = blank()
        put(buf, 3, attr0=attr0(rs=1, b9=1))
        e = oam.decode_oam(bytes(buf), 'main')[3]
        self.assertFalse(e['hidden'])
        self.assertTrue(e['double_size_or_disable'])

    def test_rotscale_clear_bit9_not_hidden(self):
        buf = blank()
        put(buf, 3, attr0=attr0(rs=1, b9=0))
        self.assertFalse(oam.decode_oam(bytes(buf), 'main')[3]['hidden'])


class TestFlipVsRotscale(unittest.TestCase):
    def test_plain_entry_reads_hflip_vflip(self):
        buf = blank()
        put(buf, 2, attr1=(1 << 12) | (1 << 13))
        e = oam.decode_oam(bytes(buf), 'main')[2]
        self.assertEqual((e['hflip'], e['vflip']), (1, 1))
        self.assertIsNone(e['rotscale_param'])

    def test_rotscale_entry_reads_param_not_flips(self):
        buf = blank()
        # rotscale param = bits 9-13; set to 0x1F (31) and bits 12/13 are part of it
        put(buf, 2, attr0=attr0(rs=1), attr1=0x1F << 9)
        e = oam.decode_oam(bytes(buf), 'main')[2]
        self.assertEqual(e['rotscale_param'], 31)
        self.assertIsNone(e['hflip'])
        self.assertIsNone(e['vflip'])

    def test_rotscale_param_middle_value(self):
        buf = blank()
        put(buf, 2, attr0=attr0(rs=1), attr1=0x05 << 9)
        self.assertEqual(oam.decode_oam(bytes(buf), 'main')[2]['rotscale_param'], 5)


class TestAffine(unittest.TestCase):
    def test_group_slots_come_from_entries_4n_to_4n_plus_3(self):
        buf = blank()
        # group 1 = entries 4..7; PA=entry4 filler, PB=entry5, PC=entry6, PD=entry7
        put(buf, 4, filler=0x0100)   # PA = 1.0
        put(buf, 5, filler=0x0080)   # PB = 0.5
        put(buf, 6, filler=0x0000)   # PC = 0.0
        put(buf, 7, filler=0x0200)   # PD = 2.0
        g = oam.decode_affine(bytes(buf))
        self.assertEqual(len(g), 32)
        self.assertEqual(g[1]['group'], 1)
        self.assertEqual((g[1]['PA'], g[1]['PB'], g[1]['PC'], g[1]['PD']), (1.0, 0.5, 0.0, 2.0))

    def test_affine_param_sign(self):
        buf = blank()
        put(buf, 0, filler=0xFF00)  # signed -256 -> -1.0
        put(buf, 1, filler=0x8000)  # -32768 -> -128.0
        put(buf, 2, filler=0x7FFF)  # max positive
        put(buf, 3, filler=0x0001)  # 1/256
        g = oam.decode_affine(bytes(buf))[0]
        self.assertEqual(g['PA_raw'], -256)
        self.assertEqual(g['PA'], -1.0)
        self.assertEqual(g['PB'], -128.0)
        self.assertEqual(g['PC'], 0x7FFF / 256)
        self.assertAlmostEqual(g['PD'], 1 / 256)

    def test_filler_halfword_not_read_as_affine_in_plain_entry_decode(self):
        # The filler bytes are the affine params regardless of rot_scale; decode_oam
        # does not interpret them, decode_affine does.
        buf = blank()
        put(buf, 0, attr0=attr0(rs=1), filler=0xFF00)
        e = oam.decode_oam(bytes(buf), 'main')[0]
        self.assertNotIn('PA', e)


class TestEngineBase(unittest.TestCase):
    def test_base_addresses(self):
        self.assertEqual(oam.ENGINE_BASE['main'], 0x07000000)
        self.assertEqual(oam.ENGINE_BASE['sub'], 0x07000400)
        self.assertEqual(oam.OAM_BYTES, 1024)

    def test_read_oam_uses_main_base(self):
        seen = []

        def peek(addr, n):
            seen.append((addr, n))
            return bytes(blank())
        oam.read_oam(peek, 'main')
        self.assertEqual(seen, [(0x07000000, 1024)])

    def test_read_oam_uses_sub_base(self):
        seen = []

        def peek(addr, n):
            seen.append((addr, n))
            return bytes(blank())
        oam.read_oam(peek, 'sub')
        self.assertEqual(seen, [(0x07000400, 1024)])

    def test_read_oam_accepts_list_return(self):
        # jusemu peek returns a JSON list for multi-byte reads; read_oam must accept it.
        buf = blank()
        put(buf, 0, attr1=0x1F0)
        out = oam.read_oam(lambda a, n: list(buf), 'main')
        self.assertEqual(out[0]['x'], -16)

    def test_read_oam_rejects_short_read(self):
        with self.assertRaises(ValueError):
            oam.read_oam(lambda a, n: bytes(10), 'main')


class TestLivePlumbing(unittest.TestCase):
    def test_live_peek_calls_jusemu_dump_with_engine_range(self):
        def fake_run(cmd, **kw):
            outfile = cmd[-1]
            with open(outfile, 'wb') as f:
                f.write(bytes(range(256)) * 4)
            return mock.Mock(returncode=0, stdout='{}', stderr='')

        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(oam.subprocess, 'run', side_effect=fake_run) as run:
            peek = oam.make_live_peek(d, ipc_dir='/nonexistent-ipc-dir')
            buf = peek(0x07000400, 1024)
            cmd = run.call_args[0][0]
            self.assertIn('dump', cmd)
            self.assertIn('0x7000400', cmd)
            self.assertIn('0x7000800', cmd)
            self.assertTrue(cmd[1].endswith('jusemu.py'))
            self.assertEqual(len(buf), 1024)
            self.assertEqual(buf[:4], bytes([0, 1, 2, 3]))

    def test_live_peek_short_dump_raises(self):
        def fake_run(cmd, **kw):
            with open(cmd[-1], 'wb') as f:
                f.write(bytes(10))
            return mock.Mock(returncode=0, stdout='', stderr='')

        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(oam.subprocess, 'run', side_effect=fake_run):
            peek = oam.make_live_peek(d, ipc_dir='/nonexistent-ipc-dir')
            with self.assertRaises(RuntimeError):
                peek(0x07000000, 1024)

    def test_live_peek_bridge_failure_raises(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(
                oam.subprocess, 'run',
                return_value=mock.Mock(returncode=1, stdout='', stderr='timeout')):
            peek = oam.make_live_peek(d, ipc_dir='/nonexistent-ipc-dir')
            with self.assertRaises(RuntimeError):
                peek(0x07000000, 1024)


class TestFromDumpRoundTrip(unittest.TestCase):
    def test_from_dump_round_trips_to_json(self):
        buf = blank()
        put(buf, 0, attr0=attr0(y=0xF0, shape=2), attr1=0x1F0 | (2 << 14), attr2=0x0AB)
        put(buf, 9, attr0=attr0(rs=1, b9=1), attr1=0x1F << 9, filler=0xFF00)
        put(buf, 127, attr0=attr0(rs=0, b9=1), attr1=0x0FF, attr2=(3 << 12) | 5)
        with tempfile.TemporaryDirectory() as d:
            dump = os.path.join(d, 'oam_sub.bin')
            out = os.path.join(d, 'oam_sub.json')
            with open(dump, 'wb') as f:
                f.write(bytes(buf))
            rc = oam.main(['--engine', 'sub', '--from-dump', dump, '--json', out])
            self.assertEqual(rc, 0)
            with open(out) as f:
                doc = json.load(f)
        self.assertEqual(doc['engine'], 'sub')
        self.assertEqual(doc['base'], '0x07000400')
        self.assertEqual(doc['entries'], json.loads(json.dumps(oam.decode_oam(bytes(buf), 'sub'))))
        self.assertEqual(doc['affine'], json.loads(json.dumps(oam.decode_affine(bytes(buf)))))
        self.assertEqual(doc['entries'][0]['x'], -16)
        self.assertEqual(doc['entries'][0]['y_signed'], -16)
        self.assertTrue(doc['entries'][127]['hidden'])
        self.assertEqual(doc['entries'][9]['rotscale_param'], 31)
        self.assertEqual(doc['affine'][2]['PB'], -1.0)

    def test_from_dump_rejects_wrong_size(self):
        with tempfile.TemporaryDirectory() as d:
            dump = os.path.join(d, 'short.bin')
            with open(dump, 'wb') as f:
                f.write(bytes(512))
            with self.assertRaises(SystemExit):
                oam.main(['--from-dump', dump, '--json', os.path.join(d, 'o.json')])


def attr1(x=0, hflip=0, vflip=0, size=0):
    return (x & 0x1FF) | (hflip << 12) | (vflip << 13) | (size << 14)


def attr2(tile=0, prio=0, pal=0):
    return tile | (prio << 10) | (pal << 12)


def pal_with(entries):
    pal = bytearray(512)
    for index, color in entries.items():
        struct.pack_into('<H', pal, 2 * index, color)
    return bytes(pal)


def vram_4bpp_tile(vram, byte_base, colors):
    """colors: 8x8 nibbles row-major written at byte_base (4bpp, 32 bytes)."""
    for row in range(8):
        for col in range(0, 8, 2):
            vram[byte_base + row * 4 + col // 2] = colors[row][col] | (colors[row][col + 1] << 4)


class TestTileAddressing(unittest.TestCase):
    """Byte offsets of OBJ tiles: 1D boundaries, 2D 32-tile rows, 4bpp/8bpp (GBATEK DISPCNT bits 4, 20-21)."""

    def entry(self, c256=0, shape=0, size=1, tile=3):
        b = blank()
        put(b, 0, attr0(c256=c256, shape=shape), attr1(size=size), attr2(tile=tile))
        return oam.decode_oam(b, 'main')[0]

    def test_1d_32_byte_boundary_4bpp(self):
        e = self.entry()  # 16x16, tile 3
        self.assertEqual(oam.obj_tile_offset(e, 0x10, 0, 0), 3 * 32)
        self.assertEqual(oam.obj_tile_offset(e, 0x10, 1, 0), 3 * 32 + 32)
        self.assertEqual(oam.obj_tile_offset(e, 0x10, 0, 1), 3 * 32 + 2 * 32)

    def test_1d_128_byte_boundary_8bpp(self):
        e = self.entry(c256=1)
        dispcnt = 0x10 | (2 << 20)
        self.assertEqual(oam.obj_tile_offset(e, dispcnt, 0, 0), 3 * 128)
        self.assertEqual(oam.obj_tile_offset(e, dispcnt, 1, 1), 3 * 128 + (1 * 2 + 1) * 64)

    def test_2d_rows_are_32_tiles(self):
        e = self.entry()
        self.assertEqual(oam.obj_tile_offset(e, 0, 1, 1), 3 * 32 + 1024 + 32)
        e8 = self.entry(c256=1)
        self.assertEqual(oam.obj_tile_offset(e8, 0, 1, 1), 3 * 32 + 1024 + 64)

    def test_same_tile_id_different_mapping_reads_different_bytes(self):
        e = self.entry()
        self.assertNotEqual(oam.obj_tile_offset(e, 0, 0, 1), oam.obj_tile_offset(e, 0x10, 0, 1))


class TestObjPixels(unittest.TestCase):
    def setUp(self):
        self.vram = bytearray(256 * 1024)
        self.tile = [[(r + c) % 16 for c in range(8)] for r in range(8)]  # colour 0 on the anti-diagonal start
        vram_4bpp_tile(self.vram, 5 * 32, self.tile)
        self.pal = pal_with({16 * 2 + i: i for i in range(16)})

    def one(self, a0, a1, a2, dispcnt=0x10, pal=None, extpal=None):
        b = blank()
        put(b, 0, a0, a1, a2)
        return oam.obj_pixels(oam.decode_oam(b, 'main')[0], dispcnt, bytes(self.vram), pal or self.pal, extpal)

    def test_4bpp_palette_bank_and_transparency(self):
        px = self.one(attr0(y=10), attr1(x=20), attr2(tile=5, pal=2))
        self.assertNotIn((20, 10), px)                      # nibble 0 is transparent
        self.assertEqual(px[(21, 10)], 1)                    # bank 2 entry 1 holds colour 1
        self.assertEqual(px[(27, 17)], 14)
        self.assertEqual(len(px), 63)                        # (r+c)%16 == 0 only at r=c=0

    def test_changed_palette_same_tile_id(self):
        a = self.one(attr0(y=10), attr1(x=20), attr2(tile=5, pal=2))
        b = self.one(attr0(y=10), attr1(x=20), attr2(tile=5, pal=2), pal=pal_with({16 * 2 + i: 0x7C00 | i for i in range(16)}))
        self.assertEqual(a.keys(), b.keys())
        self.assertTrue(all(b[k] == (a[k] | 0x7C00) for k in a))

    def test_hflip_vflip(self):
        plain = self.one(attr0(y=0), attr1(x=0), attr2(tile=5, pal=2))
        flipped = self.one(attr0(y=0), attr1(x=0, hflip=1, vflip=1), attr2(tile=5, pal=2))
        self.assertEqual(flipped, {(7 - x, 7 - y): c for (x, y), c in plain.items()})

    def test_negative_x_and_y_wrap(self):
        px = self.one(attr0(y=252), attr1(x=0x1FC), attr2(tile=5, pal=2))
        self.assertEqual(min(x for x, _ in px), 0)
        self.assertEqual(max(x for x, _ in px), 3)
        self.assertEqual(sorted({y for _, y in px}), [0, 1, 2, 3])
        self.assertEqual(px[(0, 0)], self.tile[4][4])

    def test_8bpp_standard_and_extended_palette(self):
        for i in range(64):
            self.vram[0x2000 + i] = 3
        std = self.one(attr0(c256=1), attr1(), attr2(tile=0x100, pal=1), dispcnt=0, pal=pal_with({3: 0x1234}))
        self.assertEqual(set(std.values()), {0x1234})
        ext = bytearray(8192); struct.pack_into('<H', ext, 2 * (256 + 3), 0x0ABC)
        extd = self.one(attr0(c256=1), attr1(), attr2(tile=0x100, pal=1), dispcnt=1 << 31, pal=pal_with({3: 0x1234}), extpal=bytes(ext))
        self.assertEqual(set(extd.values()), {0x0ABC})

    def test_unsupported_entries_return_none(self):
        self.assertIsNone(self.one(attr0(rs=1), attr1(), attr2(tile=5)))        # affine
        self.assertIsNone(self.one(attr0(mode=3), attr1(), attr2(tile=5)))      # bitmap
        self.assertEqual(self.one(attr0(b9=1), attr1(), attr2(tile=5)), {})     # hidden

    def test_layer_priority_then_lower_index(self):
        b = blank()
        put(b, 0, attr0(y=0), attr1(x=0), attr2(tile=5, pal=2, prio=2))
        put(b, 1, attr0(y=0), attr1(x=0), attr2(tile=5, pal=3, prio=1))   # higher priority wins
        put(b, 2, attr0(y=0), attr1(x=0), attr2(tile=5, pal=4, prio=1))   # same priority, later index loses
        pal = pal_with({**{32 + i: i for i in range(16)}, **{48 + i: 0x100 + i for i in range(16)}, **{64 + i: 0x200 + i for i in range(16)}})
        layer = oam.obj_layer(bytes(b), 0x10, bytes(self.vram), pal)
        self.assertEqual(layer['pixels'][(1, 0)], {'color': 0x101, 'index': 1, 'priority': 1, 'mode': 0})
        self.assertEqual(layer['unsupported'], [])

    def test_rgb_expansion_matches_melonds(self):
        self.assertEqual(oam.rgb555_to_rgb888(0x7FFF), (251, 251, 251))
        self.assertEqual(oam.rgb555_to_rgb888(0xFFFF), (251, 255, 251))  # bit 15 is green's low bit
        self.assertEqual(oam.rgb555_to_rgb888(0x001F), (251, 0, 0))
        self.assertEqual(oam.rgb555_to_rgb888(0x0001), (8, 0, 0))


if __name__ == '__main__':
    unittest.main()
