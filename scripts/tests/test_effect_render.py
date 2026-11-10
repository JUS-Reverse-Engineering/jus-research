import importlib.util
import os
import struct
import sys
import unittest
import _deps

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analysis", "effect_render.py")
SPEC = importlib.util.spec_from_file_location("effect_render", SCRIPT)
R = importlib.util.module_from_spec(SPEC)
sys.modules["effect_render"] = R
SPEC.loader.exec_module(R)

HAVE_ROM = R.mr.CHRARC.exists() and R.EFC.exists()
# jus_files b756b40 moved the sheets into per-character folders. The tests
# skip only without jus_files, so a stale path fails instead of skipping
SHEET_DIR = os.path.join(R.REPO, "jus_files", "sprites", "characters")
SHEET = os.path.join(SHEET_DIR, "Naruto", "kakashi", "Kakashi.png")


def dsig(height, pixels, pal=(0x01A0, 0x001F, 0x03E0, 0x7C00), flags=0x20, extra=()):
    pals = [list(p) + [0] * (16 - len(p)) for p in (pal, *extra)]
    return (b"DSIG" + bytes([1, flags]) + struct.pack("<HHH", len(pals), 0x40, height)
            + b"".join(struct.pack("<16H", *p) for p in pals) + pixels)


def dstx(version, sprites, trailer=(0, 0, 0, 0)):
    body, offs = b"", []
    head = 0xA + 2 * len(sprites)
    for segs in sprites:
        offs.append(head + len(body) - 0xA)
        body += struct.pack("<H", len(segs)) + b"".join(struct.pack("<Hbbbb", *s) for s in segs)
        if version == 2:
            body += struct.pack("<4h", *trailer)
    tex_at = head + len(body)
    return (b"DSTX" + bytes([version, 3]) + struct.pack("<HH", len(sprites), tex_at)
            + b"".join(struct.pack("<H", o) for o in offs) + body + struct.pack("<I", 0x210000))


class TexelTest(unittest.TestCase):
    def test_2bpp_is_128_wide_low_bits_first(self):
        px = bytearray(32 * 8)
        px[0] = 0b11100100          # x0..3 = 0, 1, 2, 3
        px[31] = 0b10 << 6          # x127 = 2
        px[32] = 0b01               # row 1, x0 = 1
        t = R.parse_dsig(dsig(8, bytes(px)))
        self.assertEqual([R.texel(t, x, 0) for x in range(4)], [0, 1, 2, 3])
        self.assertEqual(R.texel(t, 127, 0), 2)
        self.assertEqual(R.texel(t, 0, 1), 1)
        self.assertEqual(R.texel(t, 128, 0), 0)

    def test_4bpp_view_is_64_wide_low_nibble_first(self):
        px = bytearray(32 * 8)
        px[0] = 0xA5                # x0 = 5, x1 = 10
        px[31] = 0xF0               # x63 = 15
        t = R.parse_dsig(dsig(8, bytes(px)))
        self.assertEqual((R.texel(t, 0, 0, 4), R.texel(t, 1, 0, 4)), (5, 10))
        self.assertEqual(R.texel(t, 63, 0, 4), 15)
        self.assertEqual(R.texel(t, 64, 0, 4), 0)

    def test_shape_bit_6_picks_2bpp(self):
        self.assertEqual(R.bpp_of(0x41), 2)
        self.assertEqual(R.bpp_of(0x01), 4)

    def test_flag_0x10_means_lz77_pixels(self):
        row = bytes(range(32))
        lz = struct.pack("<I", 0x10 | (32 << 8)) + b"".join(b"\0" + row[i:i + 8] for i in range(0, 32, 8))
        self.assertEqual(R.parse_dsig(dsig(1, lz, flags=0x50))["pixels"], row)
        self.assertEqual(R.parse_dsig(dsig(1, row, flags=0x20))["pixels"], row)
        with self.assertRaises(ValueError):
            R.parse_dsig(dsig(2, row, flags=0x20))   # too few raw bytes for 2 rows


class DstxTest(unittest.TestCase):
    def test_v2_has_bounds_trailer_v1_does_not(self):
        segs = [[(0x21, -8, -8, 0x41, 0)], [(0x02, 0, 0, 0x40, 0)]]
        v2 = R.parse_dstx(dstx(2, segs, (-8, -8, 8, 8)))
        self.assertEqual(v2["sprites"], segs)
        self.assertEqual(v2["bounds"][0], (-8, -8, 8, 8))
        v1 = R.parse_dstx(dstx(1, segs))
        self.assertEqual(v1["sprites"], segs)
        self.assertEqual(v1["bounds"], [None, None])
        self.assertEqual(v1["texture"], {"id": 0x210000})

    def test_source_is_row_times_32_plus_column(self):
        self.assertEqual(R.source_xy(0x582), (16, 352))   # comm_a hit spark cell 1
        self.assertEqual(R.source_xy(0x0E), (112, 0))

    @_deps.needs("PIL")
    def test_later_segment_draws_on_top(self):
        # Two 8x8 segments on the same spot, colour 1 of palette 0 then of
        # palette 1. The later one must win (the sheet says so: cells 49/50).
        px = bytearray(32 * 8)
        px[0] = 0b01
        t = R.parse_dsig(dsig(8, bytes(px), extra=[(0, 0x7C00)]))
        im = R.draw(t, [(0, 0, 0, 0x40, 0), (0, 0, 0, 0x40, 1)], (0, 0, 8, 8))
        self.assertEqual(im.getpixel((0, 0)), R.at._rgb(0x7C00) + (255,))
        im = R.draw(t, [(0, 0, 0, 0x40, 1), (0, 0, 0, 0x40, 0)], (0, 0, 8, 8))
        self.assertEqual(im.getpixel((0, 0)), R.at._rgb(0x001F) + (255,))

    @_deps.needs("PIL")
    def test_flip_bits(self):
        px = bytearray(32 * 8)
        px[0] = 0b01                # only texel (0, 0) set
        t = R.parse_dsig(dsig(8, bytes(px)))
        box = (0, 0, 8, 8)
        for shape, want in ((0x40, (0, 0)), (0x50, (7, 0)), (0x60, (0, 7)), (0x70, (7, 7))):
            im = R.draw(t, [(0, 0, 0, shape, 0)], box)
            got = [(x, y) for y in range(8) for x in range(8) if im.getpixel((x, y))[3]]
            self.assertEqual(got, [want], hex(shape))


@unittest.skipUnless(HAVE_ROM, "needs jus_files ChrArc.aar and efc/")
class RealBundleTest(unittest.TestCase):
    SOURCES = ("na_b_04", "yh_b_01", "comm_a", "comm_b", "comm_c", "comm_g")

    def test_every_segment_fits_the_texture(self):
        for src in self.SOURCES:
            b = R.members(src)
            for name in sorted(n for n in b if n.endswith(".dtx")):
                try:
                    tex = R.texture_of(b, name)
                except ValueError:
                    continue   # the fighter's main sheet (DSIG v2 in <prefix>c.aar)
                for i, segs in enumerate(R.parse_dstx(b[name][1])["sprites"]):
                    for s in segs:
                        w, h = R.SIZES[s[3] & 15]
                        x, y = R.source_xy(s[0])
                        width = R.ROW_BYTES * 8 // R.bpp_of(s[3])
                        self.assertLessEqual(x + 8 * w, width, f"{src} {name} sprite {i} {s}")
                        self.assertLessEqual(y + 8 * h, tex["height"], f"{src} {name} sprite {i} {s}")

    def test_kakashi_textures(self):
        b = R.members("na_b_04")
        e00 = R.texture_of(b, "na_b_04_e00.dtx")
        self.assertEqual((e00["height"], len(e00["palettes"]), e00["flags"]), (384, 17, 0x20))
        e04 = R.texture_of(b, "na_b_04_e04_.dtx")      # embedded, LZ77
        self.assertEqual((e04["height"], len(e04["pixels"]), e04["flags"]), (32, 1024, 0x50))

    def test_effect_anims(self):
        k = R.effect_anims(R.members("na_b_04"), "na_b_04")
        self.assertEqual(sorted(k)[0], 0x060438)
        self.assertEqual(sorted(k)[-1], 0x06044E)
        a = k[0x060442]
        self.assertEqual((a["frames"], a["texture"]), (18, 0x060440))
        self.assertEqual([c for f, c in a["cells"] if f < a["frames"]], [24, 25, 26, 27, 28, 29, 30])
        g = R.effect_anims(R.members("comm_a"), "comm_a")
        self.assertEqual([c for f, c in g[0x21000C]["cells"]][:5], [162, 163, 164, 165, 166])

    @_deps.needs("PIL")
    def test_smoke_cells_match_the_sheet_row(self):
        # Opaque pixel count of each 0x42 cell; the first three and the last
        # equal the Kakashi.png smoke row (y 1430-1525) exactly (vfx-sfx.md).
        b = R.members("na_b_04")
        d = R.parse_dstx(b["na_b_04_e00.dtx"][1])
        tex = R.texture_of(b, "na_b_04_e00.dtx")
        counts = []
        for c in range(24, 31):
            segs = d["sprites"][c]
            boxes = [R.seg_box(s) for s in segs]
            box = (min(x[0] for x in boxes), min(x[1] for x in boxes),
                   max(x[2] for x in boxes), max(x[3] for x in boxes))
            im = R.draw(tex, segs, box)
            hist = im.getchannel("A").histogram()
            counts.append(sum(hist) - hist[0])
        self.assertEqual(counts, [148, 656, 1410, 1936, 1405, 622, 245])

    @unittest.skipUnless(os.path.isdir(SHEET_DIR), "needs jus_files/sprites")
    @_deps.needs("PIL")
    def test_smoke_cell_25_is_pixel_exact_on_the_sheet(self):
        from PIL import Image
        b = R.members("na_b_04")
        d = R.parse_dstx(b["na_b_04_e00.dtx"][1])
        tex = R.texture_of(b, "na_b_04_e00.dtx")
        segs = d["sprites"][25]
        boxes = [R.seg_box(s) for s in segs]
        im = R.draw(tex, segs, (min(x[0] for x in boxes), min(x[1] for x in boxes),
                                max(x[2] for x in boxes), max(x[3] for x in boxes)))
        im = im.crop(im.getchannel("A").getbbox())
        row = Image.open(SHEET).convert("RGB").crop((83, 1430, 125, 1525))
        bg = row.getpixel((0, 0))
        ys = [y for y in range(row.height) if any(row.getpixel((x, y)) != bg for x in range(row.width))]
        blob = row.crop((0, ys[0], row.width, ys[-1] + 1))
        self.assertEqual(blob.size, im.size)
        a = {(x, y) for y in range(im.height) for x in range(im.width) if im.getpixel((x, y))[3]}
        s = {(x, y) for y in range(blob.height) for x in range(blob.width) if blob.getpixel((x, y)) != bg}
        self.assertEqual(a, s)

    @unittest.skipUnless(os.path.isdir(SHEET_DIR), "needs jus_files/sprites")
    @_deps.needs("PIL")
    def test_smoke_cell_25_colours_match_the_sheet(self):
        # Compare 5-bit colours: the sheet widens with v << 3, the renderer
        # with v * 255 // 31. 651 of 656 pixels match. The other 5 each sit
        # under one segment only, and 3 of them hold a grey (5-bit 29) that
        # palette 2 does not have, so the sheet differs there.
        from PIL import Image
        im = crop_cell(*kakashi_e00(), 25)
        row = Image.open(SHEET).convert("RGB").crop((83, 1430, 125, 1525))
        bg = row.getpixel((0, 0))
        ys = [y for y in range(row.height) if any(row.getpixel((x, y)) != bg for x in range(row.width))]
        blob = row.crop((0, ys[0], row.width, ys[-1] + 1))
        self.assertEqual(blob.size, im.size)
        bad = {(x, y) for y in range(im.height) for x in range(im.width)
               if im.getpixel((x, y))[3] and to5(im.getpixel((x, y))) != sheet5(blob.getpixel((x, y)))}
        self.assertEqual(bad, {(16, 1), (25, 1), (13, 21), (20, 21), (28, 21)})

    @unittest.skipUnless(os.path.isdir(SHEET_DIR), "needs jus_files/sprites")
    @_deps.needs("PIL")
    def test_overlap_order_matches_the_sheet(self):
        # Cells 49 and 50 (effects 0x060446 / 0x060447) have many pixels
        # where two segments overlap with different colours. With the later
        # segment on top every pixel matches the sheet; with the first on top
        # only 808 of 1004 and 1348 of 1628 do.
        from PIL import Image
        sheet = Image.open(SHEET).convert("RGB")
        d, tex = kakashi_e00()
        for cell, (x0, y0) in ((49, (78, 8641)), (50, (208, 8657))):
            im = crop_cell(d, tex, cell)
            patch = sheet.crop((x0, y0, x0 + im.width, y0 + im.height))
            bg = sheet.getpixel((0, 0))
            for y in range(im.height):
                for x in range(im.width):
                    a, s = im.getpixel((x, y)), patch.getpixel((x, y))
                    self.assertEqual(bool(a[3]), s != bg, (cell, x, y))
                    if a[3]:
                        self.assertEqual(to5(a), sheet5(s), (cell, x, y))

    @_deps.needs("PIL")
    def test_spark_pair_is_orange_then_blue(self):
        # pair[0] 0x210000 draws warm (red > blue), pair[1] 0x210013 cool.
        b = R.members("comm_a")
        anims = R.effect_anims(b, "comm_a")
        name = R.dstx_member(b, anims[0x210000]["texture"])
        d, tex = R.parse_dstx(b[name][1]), R.texture_of(b, name)
        tally = {}
        for eid in (0x210000, 0x210013):
            warm = cool = 0
            for f, c in anims[eid]["cells"]:
                if f >= anims[eid]["frames"] or not d["sprites"][c]:
                    continue
                im = crop_cell(d, tex, c)
                for p in (im.getpixel((x, y)) for y in range(im.height) for x in range(im.width)):
                    if p[3]:
                        warm += p[0] > p[2]
                        cool += p[2] > p[0]
            tally[eid] = (warm, cool)
        w, c = tally[0x210000]
        self.assertGreater(w, 3 * c, tally)
        w, c = tally[0x210013]
        self.assertGreater(c, 3 * w, tally)


def to5(rgba):
    """Renderer colour (v * 255 // 31 per channel) back to 5-bit."""
    return tuple((v * 31 + 127) // 255 for v in rgba[:3])


def sheet5(rgb):
    """Sheet colour (v << 3 per channel) back to 5-bit."""
    return tuple(v >> 3 for v in rgb[:3])


def kakashi_e00():
    b = R.members("na_b_04")
    return R.parse_dstx(b["na_b_04_e00.dtx"][1]), R.texture_of(b, "na_b_04_e00.dtx")


def crop_cell(d, tex, cell):
    """One sprite drawn on its segments' box, cropped to its opaque pixels."""
    segs = d["sprites"][cell]
    boxes = [R.seg_box(s) for s in segs]
    im = R.draw(tex, segs, (min(x[0] for x in boxes), min(x[1] for x in boxes),
                            max(x[2] for x in boxes), max(x[3] for x in boxes)))
    return im.crop(im.getchannel("A").getbbox())


if __name__ == "__main__":
    unittest.main()
