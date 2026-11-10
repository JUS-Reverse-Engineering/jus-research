#!/usr/bin/env python3
"""effect_render.py -- draw JUS effect sprites (DSTX + DSIG v1) to PNG.

Why (jus-wmqi.6.7): the hit sparks, smoke puffs and move effects live in
their own art bundles, not in the fighter's main sheet. Matching JUS's effects
needs seeing them. This tool decodes the bundles and
draws each effect animation as a strip of cells, one per BoundsIndex key.

Where the bundles live (ALAR v2, parsed by aar_inventory):
  chr/<prefix>.aar (inside ChrArc.aar)  <prefix>_eNN[_].dtx, <prefix>_e00.dig,
                                        <prefix>_e0.amt  (character effects)
  efc/comm_a.aar ... comm_c.aar         jyocyu_efe_[abc].{dtx,dig,amt}
  efc/comm_g.aar                        jyochu_gion.{dtx,dig,amt}

Formats, read from the bytes (little-endian):

  DSIG v1 (effect art; the fighter's main sheet is DSIG v2, see anim_timing):
    +4 u8 version (1), +5 u8 flags, +6 u16 palette count, +8 u16 (0x40 in
    every file seen), +0xA u16 height in pixels, then the palettes at +0xC
    (16 BGR555 colours each, colour 0 = transparent), then the pixels.
    Flag 0x10: the pixels are one LZ77 (type 0x10) block. Without it they are
    raw. The pixel buffer is height rows of 32 bytes, top to bottom. One
    buffer holds two kinds of art, picked per segment (shape bit 6, below):
      2 bpp: 128 px per row, four pixels per byte, low bits first; only
             colours 0-3 of the palette are reachable.
      4 bpp:  64 px per row, two pixels per byte, low nibble first.
    Evidence: every file's pixel byte count is exactly height * 32; every
    2 bpp segment fits inside 128 px and every 4 bpp segment inside 64 px
    (test_every_segment_fits_the_texture); and the renders match the
    fighter sheet (vfx-sfx.md).
  DSTX (sprite list): +4 u8 version, +5 u8 flags, +6 u16 sprite count,
    +8 u16 offset of the texture: an embedded DSIG there, or else a u32 id
    whose low 24 bits match the id of a .dig in the same bundle. Then u16
    sprite offsets at 0xA + 2i (relative to 0xA). A sprite is a u16 segment
    count, then 6-byte segments: u16 source, s8 x, s8 y, u8 shape, u8
    palette. Version 2 adds an 8-byte trailer after the segments: s16 x0,
    y0, x1, y1 bounds. Version 1 has no trailer.
  Segment: source = (row << 5) | column, in 8-pixel units (bit 4 is never
    set). Low 4 bits of shape pick the size (anim_timing.SIZES, the DS OBJ
    shape/size table), bit 4 flips x, bit 5 flips y (the four-way mirrored
    hit sparks confirm both), bit 6 (0x40) set = 2 bpp art, clear = 4 bpp
    art. Every segment with bit 6 clear uses a palette with more than four
    colours. x, y place the segment's top-left corner relative to the
    effect's origin.
  Effect animation (ALMT <bundle>.amt): BoundsIndex keys pick the sprite,
    TextureID (a u32 id, low 24 bits) picks which .dtx member.

NOT FOR RELEASE: the PNGs this writes are ripped JUS art. They go under
jus_files/extracted/vfx-sfx/render/ (untracked) and are never committed.

Usage:
    python3 scripts/analysis/effect_render.py na_b_04 --anim 0x42 0x43
    python3 scripts/analysis/effect_render.py comm_a --all
    python3 scripts/analysis/effect_render.py yh_b_01 --all --sheets
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))

import aar_inventory as ai  # noqa: E402
import anim_timing as at  # noqa: E402
import anim_events as ae  # noqa: E402
import move_records as mr  # noqa: E402

EFC = REPO / "jus_files" / "ripped_jus_files" / "efc"
OUT = REPO / "jus_files" / "extracted" / "vfx-sfx" / "render"
ROW_BYTES = 32
SIZES = at.SIZES
COMM = ("comm_a", "comm_b", "comm_c", "comm_g")


def _u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


# ------------------------------------------------------------------ bundles

def _alar(blob: bytes) -> dict[str, tuple[int, bytes]]:
    inv = ai.parse_alar_v2(blob)
    return {e["name"]: (e["file_id"], mr.maybe_dscp(blob[e["offset"]:e["offset"] + e["size"]]))
            for e in inv["entries"]}


def members(source: str) -> dict[str, tuple[int, bytes]]:
    """name -> (file id, bytes) for a chr prefix (na_b_04), a special-move
    archive (na_b_04_4) or an efc bank (comm_a).

    A special-move archive's effects also draw from the base archive's
    textures (0x6046d in na_b_04_4 names texture 0x060440, na_b_04_e00), so
    the base archive's .dtx/.dig members are merged in (inferred: the ids
    only resolve that way)."""
    if source in COMM:
        return _alar((EFC / f"{source}.aar").read_bytes())
    out = _alar(mr.maybe_dscp(mr.alar_v3_member(mr.CHRARC, f"chr/{source}.aar")))
    base, _, n = source.rpartition("_")
    if n in ("4", "5", "6"):
        for name, v in members(base).items():
            if name.endswith((".dtx", ".dig")):
                out.setdefault(name, v)
    return out


# ------------------------------------------------------------------ DSIG v1

def parse_dsig(b: bytes) -> dict:
    if b[:4] != b"DSIG" or b[4] != 1:
        raise ValueError(f"not a DSIG v1 block: {b[:6]!r}")
    flags, npal, height = b[5], _u16(b, 6), _u16(b, 0xA)
    pals = [[_u16(b, 0xC + p * 32 + 2 * i) for i in range(16)] for p in range(npal)]
    o = 0xC + npal * 32
    pix = mr.lz77(b, o) if flags & 0x10 else b[o:o + height * ROW_BYTES]
    if len(pix) != height * ROW_BYTES:
        raise ValueError(f"DSIG pixels: {len(pix)} bytes, want {height * ROW_BYTES}")
    return {"flags": flags, "palettes": pals, "height": height, "pixels": pix}


def texel(dsig: dict, x: int, y: int, bpp: int = 2) -> int:
    """Colour index at (x, y) in the 2 bpp (128 px) or 4 bpp (64 px) view; 0 outside."""
    per = 8 // bpp
    if not (0 <= x < ROW_BYTES * per and 0 <= y < dsig["height"]):
        return 0
    b = dsig["pixels"][y * ROW_BYTES + x // per]
    return (b >> (bpp * (x % per))) & ((1 << bpp) - 1)


def bpp_of(shape: int) -> int:
    return 2 if shape & 0x40 else 4


# ------------------------------------------------------------------ DSTX

def parse_dstx(b: bytes) -> dict:
    if b[:4] != b"DSTX":
        raise ValueError(f"not a DSTX block: {b[:4]!r}")
    ver, n, ref = b[4], _u16(b, 6), _u16(b, 8)
    sprites, bounds = [], []
    for i in range(n):
        so = 0xA + _u16(b, 0xA + 2 * i)
        cnt = _u16(b, so)
        sprites.append([struct.unpack_from("<Hbbbb", b, so + 2 + 6 * k) for k in range(cnt)])
        bounds.append(struct.unpack_from("<4h", b, so + 2 + 6 * cnt) if ver == 2 else None)
    tex = {"embedded": ref} if b[ref:ref + 4] == b"DSIG" else {"id": struct.unpack_from("<I", b, ref)[0]}
    return {"version": ver, "flags": b[5], "sprites": sprites, "bounds": bounds, "texture": tex}


def source_xy(src: int) -> tuple[int, int]:
    return (src & 0x1F) * 8, (src >> 5) * 8


def texture_of(bundle: dict, dstx_name: str) -> dict:
    raw = bundle[dstx_name][1]
    d = parse_dstx(raw)
    if "embedded" in d["texture"]:
        return parse_dsig(raw[d["texture"]["embedded"]:])
    want = d["texture"]["id"] & 0xFFFFFF
    hits = [b for n, (fid, b) in bundle.items() if n.endswith(".dig") and fid & 0xFFFFFF == want]
    if len(hits) != 1:
        raise ValueError(f"{dstx_name}: texture id 0x{want:06x} matches {len(hits)} .dig members")
    return parse_dsig(hits[0])


def seg_box(seg) -> tuple[int, int, int, int]:
    _, x, y, shape, _ = seg
    w, h = SIZES[shape & 15]
    return x, y, x + 8 * w, y + 8 * h


def draw(dsig: dict, segs: list, box: tuple[int, int, int, int]):
    """RGBA image of one sprite; `box` = (x0, y0, x1, y1) in effect space."""
    from PIL import Image
    x0, y0, x1, y1 = box
    img = Image.new("RGBA", (max(1, x1 - x0), max(1, y1 - y0)), (0, 0, 0, 0))
    px = img.load()
    for seg in segs:  # later segments draw over earlier ones (matches the sheet, cells 49/50)
        src, x, y, shape, pal = seg
        w, h = SIZES[shape & 15]
        sx, sy = source_xy(src)
        bpp = bpp_of(shape)
        pals = dsig["palettes"]
        colours = pals[pal] if pal < len(pals) else None
        for yy in range(8 * h):
            for xx in range(8 * w):
                v = texel(dsig, sx + xx, sy + yy, bpp)
                if not v:
                    continue
                X = 8 * w - 1 - xx if shape & 0x10 else xx
                Y = 8 * h - 1 - yy if shape & 0x20 else yy
                gx, gy = x + X - x0, y + Y - y0
                if 0 <= gx < img.width and 0 <= gy < img.height:
                    px[gx, gy] = (at._rgb(colours[v]) if colours else (255, 0, 255)) + (255,)
    return img


# ------------------------------------------------------------------ animations

def effect_anims(bundle: dict, source: str) -> dict[int, dict]:
    """full effect id -> {member, anim, frames, cells [(frame, cell)], texture}.

    Skips `<source>.amt`, the fighter's body motions: they draw from the main
    DSIG v2 sheet in chr/<prefix>c.aar (anim_timing), not from this bundle."""
    out = {}
    for name, (fid, raw) in bundle.items():
        if not name.endswith(".amt") or name == f"{source}.amt":
            continue
        almt = mr.Almt(raw, 0)
        for idx, full in almt.full_animations():
            e = full["nodes"][0]["entry"]
            if e is None:
                continue
            tr = {}
            for t in e["tracks"]:
                data = t["raw"]
                if t["prop"] == "TextureID" and t["kind"] == "key":
                    # full_entry's legacy boundary can clip this last track.
                    end = max(n["end"] for n in full["nodes"] if n["end"] is not None)
                    nodes = ae.cumulative_node_tracks(almt, e["start"], end)
                    tracks, stop = nodes[almt.nodes[0]]
                    off = tracks["TextureID"][1]
                    stop = min([o for _, o in tracks.values() if o > off] + [stop])
                    data = raw[off:stop]
                tr[t["prop"]] = at.decode_track(t["prop"], t["kind"], data)
            if "BoundsIndex" not in tr or "TextureID" not in tr:
                continue
            texids = {v for _, v in tr["TextureID"]}
            row = {"member": name, "anim": e["id"], "frames": e["frames"],
                   "cells": tr["BoundsIndex"], "texture": None, "skip": None}
            if len(texids) != 1:
                row["texture_keys"] = [(f, v & 0xFFFFFF) for f, v in tr["TextureID"]]
            else:
                row["texture"] = texids.pop() & 0xFFFFFF
            out[(fid & 0xFFFF00) | e["id"]] = row
    return out


def dstx_member(bundle: dict, texture: int) -> str:
    hits = [n for n, (fid, _) in bundle.items() if n.endswith(".dtx") and fid & 0xFFFFFF == texture]
    if len(hits) != 1:
        raise ValueError(f"texture 0x{texture:06x} matches {hits}")
    return hits[0]


def render_anim(bundle: dict, info: dict, scale: int = 3):
    """Strip of the anim's cells in key order, all on one shared box, labelled."""
    from PIL import Image, ImageDraw
    textures = info.get("texture_keys", [(0, info["texture"])])
    sheets = {}
    for _, texture in textures:
        name = dstx_member(bundle, texture)
        sheets[texture] = (parse_dstx(bundle[name][1]), texture_of(bundle, name))
    keys = []
    for f in sorted({f for f, _ in info["cells"]} | {f for f, _ in textures}):
        cells = [c for t, c in info["cells"] if t <= f]
        ids = [v for t, v in textures if t <= f]
        if f >= info["frames"] or not cells or not ids:
            continue
        d, tex = sheets[ids[-1]]
        c = cells[-1]
        if c < len(d["sprites"]):
            keys.append((f, c, d["sprites"][c], tex))
    boxes = [seg_box(s) for _, _, segs, _ in keys for s in segs] or [(0, 0, 8, 8)]
    box = (min(b[0] for b in boxes) - 2, min(b[1] for b in boxes) - 2,
           max(b[2] for b in boxes) + 2, max(b[3] for b in boxes) + 2)
    cw, ch = (box[2] - box[0]) * scale, (box[3] - box[1]) * scale
    strip = Image.new("RGBA", (max(1, cw * len(keys)), ch + 14), (48, 48, 64, 255))
    pen = ImageDraw.Draw(strip)
    for i, (f, c, segs, tex) in enumerate(keys):
        im = draw(tex, segs, box).resize((cw, ch), Image.NEAREST)
        strip.alpha_composite(im, (i * cw, 14))
        ox, oy = (-box[0]) * scale + i * cw, (-box[1]) * scale + 14
        pen.line([(ox - 3, oy), (ox + 3, oy)], fill=(255, 64, 64, 255))
        pen.line([(ox, oy - 3), (ox, oy + 3)], fill=(255, 64, 64, 255))
        pen.text((i * cw + 2, 1), f"f{f} c{c}", fill=(255, 255, 255, 255))
    return strip, name, [(f, c) for f, c, _, _ in keys]


def render_sheet(tex: dict, pal: int = 0, bpp: int = 2, scale: int = 2):
    """The whole buffer in one view (2 bpp: 128 px wide, 4 bpp: 64 px wide)."""
    from PIL import Image
    w = ROW_BYTES * 8 // bpp
    img = Image.new("RGBA", (w, tex["height"]), (48, 48, 64, 255))
    px = img.load()
    colours = tex["palettes"][pal]
    for y in range(tex["height"]):
        for x in range(w):
            v = texel(tex, x, y, bpp)
            if v:
                px[x, y] = at._rgb(colours[v]) + (255,)
    return img.resize((w * scale, tex["height"] * scale), Image.NEAREST)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("source", help="chr prefix (na_b_04, yh_b_01) or comm_a/b/c/g")
    ap.add_argument("--anim", nargs="*", default=[], help="anim ids (low byte or full id)")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--sheets", action="store_true", help="also write each texture sheet")
    ap.add_argument("--scale", type=int, default=3)
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    bundle = members(a.source)
    anims = effect_anims(bundle, a.source)
    want = [int(x, 0) for x in a.anim]
    picks = sorted(anims) if a.all else [k for k in sorted(anims) if k in want or k & 0xFF in want]
    out = a.out / a.source
    out.mkdir(parents=True, exist_ok=True)
    for k in picks:
        if anims[k]["texture"] is not None and not [
                n for n, (fid, _) in bundle.items()
                if n.endswith(".dtx") and fid & 0xFFFFFF == anims[k]["texture"]]:
            anims[k]["skip"] = f"texture 0x{anims[k]['texture']:06x} is in another archive"
        if anims[k]["skip"]:
            print(f"skip {k:06x}: {anims[k]['skip']}")
            continue
        strip, name, keys = render_anim(bundle, anims[k], a.scale)
        p = out / f"{k:06x}.png"
        strip.save(p)
        print(f"{p}  {name}  frames {anims[k]['frames']}  cells {[c for _, c in keys]}")
    if a.sheets:
        for name in sorted(n for n in bundle if n.endswith(".dtx")):
            try:
                tex = texture_of(bundle, name)
            except ValueError as e:
                print(f"skip {name}: {e}")
                continue
            for bpp in (2, 4):
                p = out / f"sheet_{name}_{bpp}bpp.png"
                render_sheet(tex, bpp=bpp).save(p)
                print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
