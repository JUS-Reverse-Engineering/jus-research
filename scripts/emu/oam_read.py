"""OAM (sprite attribute memory) entry reader for the JUS melonDS bridge.

READER STEP, pixel step for vis-v2. The decoder and the pixel
renderer (obj_tile_offset, obj_pixels, obj_layer) are checked against synthetic
buffers (tests/test_oam_read.py). On live GPU-media captures (consumed OAM, OBJ
VRAM and palette per frame) obj_layer reproduces 99.52-99.96 % of the 2D-visible
OBJ pixels by exact RGB; the rest of its predictions are covered by the 3D layer
(docs/research/feel-captures/2026-10-19-vis-v2-oam-clocks/README.md).

Layout (Nintendo DS, GBATEK): each engine has 1 KiB of OAM, 128 entries of 8
bytes. Each entry is attr0, attr1, attr2 and a filler halfword. The filler
halfwords of entries 4n..4n+3 hold the affine group n: PA, PB, PC, PD.

    main engine OAM  0x07000000
    sub  engine OAM  0x07000400

Reading live: `jusemu.py peek` refuses addresses outside main RAM
(jus_plan.validate_watches), so OAM cannot go through peek. This reader uses
`jusemu.py dump` on the same IPC bridge, as projectile_census.Ram does for RAM.

Usage:
    python3 oam_read.py --engine main --json OUT.json        # live bridge
    python3 oam_read.py --engine sub --from-dump raw.bin --json OUT.json
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
JUSEMU = os.path.join(HERE, "jusemu.py")

OAM_BYTES = 1024
ENTRIES = 128
AFFINE_GROUPS = 32
ENGINE_BASE = {"main": 0x07000000, "sub": 0x07000400}

# (shape, size) -> (width, height). Shape 3 is prohibited and has no size.
SIZE_TABLE = {
    (0, 0): (8, 8), (0, 1): (16, 16), (0, 2): (32, 32), (0, 3): (64, 64),
    (1, 0): (16, 8), (1, 1): (32, 8), (1, 2): (32, 16), (1, 3): (64, 32),
    (2, 0): (8, 16), (2, 1): (8, 32), (2, 2): (16, 32), (2, 3): (32, 64),
}


def _check_buf(buf, n=OAM_BYTES):
    if len(buf) != n:
        raise ValueError("expected %d bytes, got %d" % (n, len(buf)))


def _check_engine(engine):
    if engine not in ENGINE_BASE:
        raise ValueError("engine must be 'main' or 'sub', got %r" % (engine,))


def _u16(buf, off):
    return buf[off] | (buf[off + 1] << 8)


def decode_oam(buf, engine):
    """Decode 128 OAM entries from a 1 KiB buffer. Returns a list of dicts."""
    _check_engine(engine)
    buf = bytes(buf)
    _check_buf(buf)
    out = []
    for i in range(ENTRIES):
        a0 = _u16(buf, 8 * i)
        a1 = _u16(buf, 8 * i + 2)
        a2 = _u16(buf, 8 * i + 4)
        y = a0 & 0xFF
        rot_scale = (a0 >> 8) & 1
        b9 = (a0 >> 9) & 1
        shape = (a0 >> 14) & 3
        size = (a1 >> 14) & 3
        x = a1 & 0x1FF
        if x >= 256:          # 9-bit two's complement
            x -= 512
        if rot_scale:
            rotscale_param = (a1 >> 9) & 0x1F
            hflip = vflip = None
        else:
            rotscale_param = None
            hflip = (a1 >> 12) & 1
            vflip = (a1 >> 13) & 1
        wh = SIZE_TABLE.get((shape, size))
        out.append({
            "index": i,
            "engine": engine,
            "y": y,
            # Y values 192..255 are the wrapped negative positions (-64..-1); the
            # DS screen is 192 lines tall, so 160..191 are on-screen.
            "y_signed": y - 256 if y >= 192 else y,
            "rot_scale": bool(rot_scale),
            # bit 9 = double-size when rot_scale, disable when not.
            "double_size_or_disable": bool(b9),
            # Hidden: not rot/scale and disable bit set.
            "hidden": bool(not rot_scale and b9),
            "obj_mode": (a0 >> 10) & 3,
            "mosaic": (a0 >> 12) & 1,
            "color_256": (a0 >> 13) & 1,
            "shape": shape,
            "x": x,
            "rotscale_param": rotscale_param,
            "hflip": hflip,
            "vflip": vflip,
            "size": size,
            "width": wh[0] if wh else None,
            "height": wh[1] if wh else None,
            "tile": a2 & 0x3FF,
            "priority": (a2 >> 10) & 3,
            "palette": (a2 >> 12) & 0xF,
            "affine_group": i // 4,
        })
    return out


def _s16(v):
    return v - 0x10000 if v & 0x8000 else v


def decode_affine(buf):
    """32 affine groups. PA/PB/PC/PD come from filler halfwords of entries 4n..4n+3.

    Values are signed 8.8 fixed point: PA is the raw signed int, PA is the float.
    """
    buf = bytes(buf)
    _check_buf(buf)
    out = []
    for g in range(AFFINE_GROUPS):
        rec = {"group": g}
        for k, name in enumerate(("PA", "PB", "PC", "PD")):
            raw = _s16(_u16(buf, 8 * (4 * g + k) + 6))
            rec[name + "_raw"] = raw
            rec[name] = raw / 256.0
        out.append(rec)
    return out


def buffer_from_peek(buf):
    """Normalise a peek result (bytes, bytearray or jusemu's JSON list) to bytes."""
    return bytes(buf)


def read_oam_buffer(peek, engine):
    """Fetch the raw 1 KiB OAM buffer for an engine through peek(addr, n)."""
    _check_engine(engine)
    buf = buffer_from_peek(peek(ENGINE_BASE[engine], OAM_BYTES))
    _check_buf(buf)
    return buf


def read_oam(peek, engine):
    """Read and decode the 128 entries of one engine through peek(addr, n)."""
    return decode_oam(read_oam_buffer(peek, engine), engine)


def make_live_peek(tmp_dir, ipc_dir=None):
    """peek(addr, n) backed by `jusemu.py dump` over the existing IPC bridge."""
    def peek(addr, n):
        outfile = os.path.join(tmp_dir, "oam_%08x_%x.bin" % (addr, n))
        cmd = [sys.executable, JUSEMU]
        if ipc_dir:
            cmd += ["--ipc-dir", ipc_dir]
        cmd += ["dump", hex(addr), hex(addr + n), outfile]
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=HERE)
        if r.returncode != 0:
            raise RuntimeError("jusemu dump failed: %s%s" % (r.stdout, r.stderr))
        with open(outfile, "rb") as f:
            data = f.read()
        if len(data) != n:
            raise RuntimeError("short dump at 0x%08X: got %d, wanted %d"
                               % (addr, len(data), n))
        return data
    return peek


# --- OBJ pixel decoding from consumed bytes (vispilot-d1 V2) -------------------
# Inputs are the bytes the native GPU-media stream records: one engine's OAM bank,
# its OBJ VRAM flat copy (256 KiB main, 128 KiB sub), the 512-byte OBJ palette and
# the 8 KiB OBJ extended palette. Addressing follows GBATEK (DISPCNT bit 4 = 1D,
# bits 20-21 = 1D boundary, bit 31 = OBJ extended palettes). Affine, bitmap and
# mosaic entries are reported unsupported instead of approximated.


def obj_tile_offset(entry, dispcnt, tile_x, tile_y):
    """Byte offset into OBJ VRAM of tile (tile_x, tile_y) of a non-bitmap entry."""
    tile_bytes = 64 if entry["color_256"] else 32
    if dispcnt & 0x10:
        base = (entry["tile"] << ((dispcnt >> 20) & 3)) * 32
        return base + (tile_y * (entry["width"] // 8) + tile_x) * tile_bytes
    return entry["tile"] * 32 + tile_y * 1024 + tile_x * tile_bytes


def obj_pixels(entry, dispcnt, vram, pal, extpal=None):
    """Opaque on-screen pixels of one entry as {(x, y): rgb555}, or None if unsupported."""
    if entry["hidden"]:
        return {}
    if entry["rot_scale"] or entry["obj_mode"] == 3 or entry["mosaic"] or entry["width"] is None:
        return None
    mask = len(vram) - 1
    out = {}
    w, h = entry["width"], entry["height"]
    for row in range(h):
        y = (entry["y"] + row) & 0xFF
        if y >= 192:
            continue
        src_y = h - 1 - row if entry["vflip"] else row
        for col in range(w):
            x = entry["x"] + col
            if not 0 <= x < 256:
                continue
            src_x = w - 1 - col if entry["hflip"] else col
            at = obj_tile_offset(entry, dispcnt, src_x // 8, src_y // 8)
            if entry["color_256"]:
                value = vram[(at + (src_y % 8) * 8 + src_x % 8) & mask]
                if not value:
                    continue
                if dispcnt & (1 << 31):
                    index = entry["palette"] * 256 + value
                    color = _u16(extpal, 2 * index)
                else:
                    color = _u16(pal, 2 * value)
            else:
                byte = vram[(at + (src_y % 8) * 4 + (src_x % 8) // 2) & mask]
                value = (byte >> 4) if src_x & 1 else (byte & 0xF)
                if not value:
                    continue
                color = _u16(pal, 2 * (entry["palette"] * 16 + value))
            out[(x, y)] = color
    return out


def obj_layer(oam_bytes, dispcnt, vram, pal, extpal=None, engine="main"):
    """Front OBJ pixel per screen position: lower priority value wins, then lower index.

    OBJ-window entries (mode 2) are skipped. Returns {'pixels': {(x, y): {color, index,
    priority, mode}}, 'unsupported': [indices]}. BG layers, blending and brightness are
    not modelled; callers compare only where those cannot apply.
    """
    pixels, unsupported = {}, []
    for entry in decode_oam(oam_bytes, engine):
        if entry["obj_mode"] == 2 and not entry["hidden"]:
            continue
        drawn = obj_pixels(entry, dispcnt, vram, pal, extpal)
        if drawn is None:
            unsupported.append(entry["index"])
            continue
        for xy, color in drawn.items():
            old = pixels.get(xy)
            if old is None or entry["priority"] < old["priority"]:
                pixels[xy] = {"color": color, "index": entry["index"],
                              "priority": entry["priority"], "mode": entry["obj_mode"]}
    return {"pixels": pixels, "unsupported": unsupported}


def rgb555_to_rgb888(color):
    """melonDS software output for a 15-bit colour: 6-bit channels (bit 15 is green's
    low bit), then each channel c6 -> (c6 << 2) | (c6 >> 4)."""
    r6 = (color & 0x1F) << 1
    g6 = ((color >> 4) & 0x3E) | (color >> 15 & 1)
    b6 = (color >> 9) & 0x3E
    return tuple((c << 2) | (c >> 4) for c in (r6, g6, b6))


def build_doc(buf, engine, source):
    return {
        "engine": engine,
        "base": "0x%08X" % ENGINE_BASE[engine],
        "source": source,
        "entries": decode_oam(buf, engine),
        "affine": decode_affine(buf),
    }


def build_parser():
    p = argparse.ArgumentParser(prog="oam_read",
                                description="Read and decode OAM entries (reader step).")
    p.add_argument("--engine", choices=sorted(ENGINE_BASE), default="main")
    p.add_argument("--from-dump", metavar="FILE",
                   help="decode a raw 1 KiB OAM dump instead of reading the live bridge")
    p.add_argument("--json", metavar="OUT", help="write JSON here (default: stdout)")
    p.add_argument("--ipc-dir", default=None, help="jusemu IPC dir (default: jusemu's)")
    p.add_argument("--tmp-dir", default=None,
                   help="scratch dir for live dumps (default: a fresh dir under TMPDIR)")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.from_dump:
        with open(args.from_dump, "rb") as f:
            buf = f.read()
        if len(buf) != OAM_BYTES:
            raise SystemExit("error: --from-dump needs %d bytes, got %d"
                             % (OAM_BYTES, len(buf)))
        doc = build_doc(buf, args.engine, "dump")
    else:
        tmp = args.tmp_dir or tempfile.mkdtemp(prefix="oam_read_")
        peek = make_live_peek(tmp, args.ipc_dir)
        buf = read_oam_buffer(peek, args.engine)
        doc = build_doc(buf, args.engine, "live")
    text = json.dumps(doc, indent=1)
    if args.json:
        with open(args.json, "w") as f:
            f.write(text + "\n")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
