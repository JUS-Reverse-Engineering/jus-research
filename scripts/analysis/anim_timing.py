#!/usr/bin/env python3
"""anim_timing.py -- which art cell JUS shows on which frame of a move.

Why this exists
---------------
Each fighter is drawn from a strip of art frames. Showing the right
frame on the right tick needs JUS's own timing. JUS keeps that timing in
the character's ALMT motion table (`chr/<prefix>.aar` -> `<prefix>.amt`).
Each animation has a `BoundsIndex` track: (frame, cell) keys, where `cell`
is a sprite index in the character's `<prefix>_.dtx` sprite list. The same
animation also carries the collision tracks (`CollisionType/Enable/Rect`),
and art and boxes run off one clock.

So this tool does two things:

1. `decode`: read an animation's cell keys and header (static).
2. `check`: replay an animation's collision keys against a live capture
   (`frames.jsonl` from the kit probes) and count the frames that agree.
   Collision boxes are on the same clock as the art, so a full match on the
   anchor basis measures the art clock too. The cell ids themselves stay
   static unless a MOVES row cites a capture that read the live cell
   (`cells_measured`, checked by `cells_grade`).
`build` runs 1 and 2 for every move in MOVES and STATE_CHECKS and writes
docs/rebuild/anim-timing.json. It refuses to write when a capture's best
animation is not the one MOVES names, so a wrong id cannot slip in.

Formats (static: see docs/rebuild/anim-timing.md §6):

- ALMT entry: +0 u32 id (low byte), +4 u16 frames, +6 u8 rate (60 on every
  Kakashi/Yusuke entry), +7 u8 loop flag. Keyed tracks are (u16 frame,
  value) pairs ended by 0xFFFF; a CollisionRect key is 10 bytes (frame plus
  s16 x0, y0, x1, y1) and a const rect is 8 bytes.
- DSIG (`chr/<prefix>c.aar`, ALAR v2, one member): +6 u8 palette count,
  palettes at +0x0C (16 BGR555 each), then u32, then u32 frame count, then
  (u16 off, u16 size) per frame; frame data is LZ77 at nfp + off*4, raw 4bpp
  tiles.
- DSTX type 0x83 (`<prefix>_.dtx`): +6 u16 sprite count, u16 offsets at
  0x0A + 2i (relative to 0x0A); a sprite is u16 segment count, then 6-byte
  segments (u16 DSIG frame, s8 x, s8 y, u8 shape, u8 palette). Low 4 bits of
  shape pick the size, bits 4-5 flip. Tiles are used one after another
  across segments.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))

import char_args  # noqa: E402
import move_records as mr  # noqa: E402
from anim_rows import C1, C2, C3, C4, KIT_LABELS, MOVES, NO_SIDE_X, SHARED_STATES, SPECIALS, STATE_CHECKS, STATIC_MOVES  # noqa: E402,F401

CHR = REPO / "jus_files" / "ripped_jus_files" / "chr"
CAPS = REPO / "docs" / "research" / "feel-captures"
OUT_JSON = REPO / "docs" / "rebuild" / "anim-timing.json"
STRIP_MAP = CAPS / "anim-timing-2026-09-23" / "strip-cell-map.json"

# The committed roster (decoder_roster.json); any other character is built from
# --char/--chr-b/--prefix (char_args.py). MOVES, STATE_CHECKS and SPECIALS
# (anim_rows.py) are keyed by name and hold rows only for characters with captures.
CHARS = char_args.roster()

# ---------------------------------------------------------------- ALMT


@dataclass
class Anim:
    id: int
    frames: int
    rate: int
    loop: int
    tracks: dict = field(default_factory=dict)

    def keys(self, prop):
        return self.tracks.get(prop, [])


def _u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def _s16(b, o):
    return struct.unpack_from("<h", b, o)[0]


def decode_track(prop: str, kind: str, raw: bytes) -> list:
    """(frame, value) keys of one track. Rects are 4-tuples of s16."""
    if prop == "TextureID" and kind == "key":
        out, q = [], 0
        while q + 2 <= len(raw):
            f = _u16(raw, q)
            if f == 0xFFFF:
                return out
            if q + 6 > len(raw):
                raise ValueError("truncated keyed TextureID")
            out.append((f, struct.unpack_from("<I", raw, q + 2)[0]))
            q += 6
        raise ValueError("keyed TextureID missing terminator")
    rect = prop.startswith("CollisionRect")
    signed = prop.startswith("CollisionType")
    if kind == "const":
        if rect:
            return [(0, tuple(_s16(raw, 2 * i) for i in range(4)))]
        if prop == "TextureID":
            return [(0, struct.unpack_from("<I", raw, 0)[0])]
        return [(0, _s16(raw, 0) if signed else _u16(raw, 0))]
    stride = 10 if rect else 4
    out, q = [], 0
    while q + 2 <= len(raw):
        f = _u16(raw, q)
        if f == 0xFFFF or q + stride > len(raw):
            break
        if rect:
            out.append((f, tuple(_s16(raw, q + 2 + 2 * i) for i in range(4))))
        else:
            out.append((f, _s16(raw, q + 2) if signed else _u16(raw, q + 2)))
        q += stride
    return out


def _inner(prefix: str) -> tuple[bytes, dict]:
    import aar_inventory as ai
    blob = mr.maybe_dscp(mr.alar_v3_member(mr.CHRARC, f"chr/{prefix}.aar"))
    return blob, ai.parse_alar_v2(blob)


def _member(prefix: str, name: str) -> bytes:
    blob, inv = _inner(prefix)
    hits = [e for e in inv["entries"] if e["name"] == name]
    if len(hits) != 1:
        raise SystemExit(f"{prefix}: expected one {name}, found {len(hits)}")
    e = hits[0]
    return blob[e["offset"]:e["offset"] + e["size"]]


def load_anims(prefix: str, member: str | None = None) -> dict[int, Anim]:
    """Node-0 entry of every animation in `<prefix>.amt` (or `member` of
    chr/<prefix>.aar, e.g. a koma archive's effect table), keyed by id."""
    almt = mr.Almt(mr.maybe_dscp(_member(prefix, member or f"{prefix}.amt")), 0)
    res = {}
    for idx, full in almt.full_animations():
        e = full["nodes"][0]["entry"]
        if e is None:
            continue
        a = almt.base + almt.anim_offsets[idx]
        an = Anim(e["id"], e["frames"], almt.buf[a + 6], almt.buf[a + 7])
        for t in e["tracks"]:
            an.tracks[t["prop"]] = decode_track(t["prop"], t["kind"], t["raw"])
        if an.id in res:
            raise SystemExit(f"{prefix}: animation id 0x{an.id:02x} appears twice")
        res[an.id] = an
    return res


def segments(keys: list, frames: int) -> tuple[list, int | None]:
    """Collapse (frame, cell) keys into shown spans.

    Returns ([{cell, start, len}], end_cell). A key at frame == `frames` is
    the end marker: it is returned as end_cell, not as a span. Runs of the
    same cell merge. The last span runs to `frames`.
    """
    body = sorted((f, c) for f, c in keys if f < frames)
    end = [c for f, c in keys if f == frames]
    spans = []
    for i, (f, c) in enumerate(body):
        nxt = body[i + 1][0] if i + 1 < len(body) else frames
        if spans and spans[-1]["cell"] == c:
            spans[-1]["len"] += nxt - f
        else:
            spans.append({"cell": c, "start": f, "len": nxt - f})
    return spans, (end[0] if end else None)


def val_at(keys, t):
    v = None
    for f, x in keys:
        if f <= t:
            v = x
    return v


def predict(an: Anim, t: int, facing: int) -> set:
    """Collision elements the ALMT puts out at anim frame t.

    One (type, cx, cy, hx, hy) per enabled channel that has a rect track
    (a typed channel with no rect puts out no element: Eve's side Y channel 2
    is never captured). facing -1 mirrors x.
    """
    out = set()
    for ch in range(7):
        tk = an.keys(f"CollisionType{ch}")
        # The no-rect skip is evidenced only by Eve side Y (0x21) channel 2,
        # type 0 with no enable and no rect. Kakashi 0x18 channel 1 (type 271)
        # is an unchecked counter-case: it is not verified against this rule.
        if not tk or not an.keys(f"CollisionRect{ch}"):
            continue
        if not val_at(an.keys(f"CollisionEnable{ch}") or [(0, 1)], t):
            continue
        x0, y0, x1, y1 = val_at(an.keys(f"CollisionRect{ch}"), t)
        cx = (x0 + x1) / 2 * (1 if facing > 0 else -1)
        out.add((val_at(tk, t), cx, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2))
    return out


def box_types(an: Anim) -> set:
    return {v for p, ks in an.tracks.items() if p.startswith("CollisionType") for _, v in ks}


# ---------------------------------------------------------------- captures

PROBE_CAP = 4  # the kit probe logs at most 4 elements per record (hitbox_strip)


@dataclass
class Capture:
    path: Path
    state: dict
    physx: dict
    elems: dict

    @property
    def frames(self):
        return sorted(self.state)


def load_capture(path: Path) -> Capture:
    st, px, el = {}, {}, {}
    with open(path) as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("type") == "fighter" and r.get("slot") == 0:
                st[r["frame"]] = r["state"]
                px[r["frame"]] = r["physx"]
            elif r.get("type") == "elem" and r.get("cnt", 0) > 0 and r.get("sub"):
                el.setdefault(r["frame"], []).append(r)
    return Capture(Path(path), st, px, el)


def p1_elems(cap: Capture, f: int) -> set:
    """P1's live sub-rects at frame f: elements whose position is P1's (x16)."""
    out = set()
    for r in cap.elems.get(f, []):
        if f in cap.physx and r["pos"][0] == cap.physx[f] * 16:
            for s in r["sub"]:
                out.add((r["id"],) + tuple(s))
    return out


def agrees(pred: set, seen: set, types: set) -> bool:
    """True when the capture shows exactly the predicted boxes (±1 px).

    Only captured ids that the animation can put out are compared (spawned
    shots carry their own ids). When the capture holds PROBE_CAP or more
    boxes, a predicted box may be missing: the probe cut it off.
    """
    capped = len(seen) >= PROBE_CAP
    left = [c for c in seen if c[0] in types]
    for p in pred:
        hit = [c for c in left if c[0] == p[0] and all(abs(c[i] - p[i]) <= 1 for i in range(1, 5))]
        if not hit:
            if capped:
                continue
            return False
        left.remove(hit[0])
    return not left


def anchor_of(cap: Capture, rule: str) -> int:
    """Frame 0 of an animation in a capture.

    'leave_idle': first frame the state is not 0/1 (grounded normals,
    kakashi.md §0). 'state9': first frame in state 9 (air moves). Otherwise
    a chain like '4', '13-1' or '13>0-1': find the first frame in the first
    state, then the first later frame in the next state, and so on; then add
    the trailing +k or -k.
    """
    frames = cap.frames
    if rule in ("leave_idle", "state9"):
        for f in frames:
            s = cap.state[f]
            if (rule == "state9" and s == 9) or (rule == "leave_idle" and s not in (0, 1)):
                return f
        raise SystemExit(f"{cap.path}: no anchor for rule {rule}")
    body, k = rule, 0
    for sign in "+-":
        if sign in body:
            body, off = body.split(sign)
            k = int(off) * (1 if sign == "+" else -1)
    f0 = frames[0] - 1
    for want in (int(x) for x in body.split(">")):
        hit = next((f for f in frames if f > f0 and cap.state[f] == want), None)
        if hit is None:
            raise SystemExit(f"{cap.path}: no anchor for rule {rule}")
        f0 = hit
    return f0 + k


def score(an: Anim, cap: Capture, anchor: int, facing: int, upto: int | None = None) -> list:
    """Anim frames t in [0, upto) where the capture disagrees."""
    n = an.frames if upto is None else upto
    types = box_types(an)
    return [t for t in range(n)
            if not agrees(predict(an, t, facing), p1_elems(cap, anchor + t), types)]


def rank(anims: dict, cap: Capture, anchor: int, facing: int) -> list:
    """[(fraction, anim id)] best first, each anim scored over its own length."""
    res = []
    for aid, an in anims.items():
        if an.frames == 0 or not box_types(an):
            continue
        bad = score(an, cap, anchor, facing)
        res.append(((an.frames - len(bad)) / an.frames, aid))
    return sorted(res, key=lambda x: (-x[0], x[1]))


def state_return(cap: Capture, anchor: int) -> int | None:
    """Frames from anchor to the first frame back in state 0/1."""
    for f in cap.frames:
        if f > anchor and cap.state[f] in (0, 1):
            return f - anchor
    return None


def first_leave(cap: Capture, anchor: int, state: int) -> int | None:
    for f in cap.frames:
        if f > anchor and cap.state[f] != state:
            return f - anchor
    return None


# ---------------------------------------------------------------- art

SIZES = {0: (1, 1), 1: (2, 2), 2: (4, 4), 3: (8, 8), 4: (2, 1), 5: (4, 1),
         6: (4, 2), 7: (8, 4), 8: (1, 2), 9: (1, 4), 10: (2, 4), 11: (4, 8)}


def load_art(prefix: str):
    import aar_inventory as ai
    c = (CHR / f"{prefix}c.aar").read_bytes()
    e = ai.parse_alar_v2(c)["entries"][0]
    d = c[e["offset"]:e["offset"] + e["size"]]
    if d[:4] != b"DSIG":
        raise SystemExit(f"{prefix}c.aar: not DSIG")
    npal = d[6]
    pals = [[_u16(d, 0xC + p * 32 + 2 * i) for i in range(16)] for p in range(npal)]
    nfp = 0xC + npal * 32 + 4
    nf = struct.unpack_from("<I", d, nfp)[0]
    frames = [mr.lz77(d, nfp + _u16(d, nfp + 4 + 4 * i) * 4) for i in range(nf)]
    t = _member(prefix, f"{prefix}_.dtx")
    n = _u16(t, 6)
    sprites = []
    for i in range(n):
        so = 0xA + _u16(t, 0xA + 2 * i)
        cnt = _u16(t, so)
        sprites.append([struct.unpack_from("<Hbbbb", t, so + 2 + 6 * k) for k in range(cnt)])
    return pals, frames, sprites


def _rgb(c):
    return ((c & 31) * 255 // 31, ((c >> 5) & 31) * 255 // 31, ((c >> 10) & 31) * 255 // 31)


def render_cell(art, i: int, canvas: int = 192):
    from PIL import Image
    pals, frames, sprites = art
    img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    px_ = img.load()
    base = 0
    for fi, x, y, shape, pal in sprites[i]:
        tiles = frames[fi]
        w, h = SIZES[shape & 15]
        fl = (shape >> 4) & 3
        ti, base = base, base + w * h
        colours = pals[pal & 3] if (pal & 3) < len(pals) else None
        for ty in range(h):
            for tx in range(w):
                tn = ti + ty * w + tx
                tb = tiles[tn * 32:tn * 32 + 32]
                if len(tb) < 32:
                    continue
                for py in range(8):
                    for px in range(8):
                        b = tb[py * 4 + px // 2]
                        v = (b >> 4) if px & 1 else (b & 15)
                        if v == 0:
                            continue
                        X, Y = tx * 8 + px, ty * 8 + py
                        if fl & 1:
                            X = w * 8 - 1 - X
                        if fl & 2:
                            Y = h * 8 - 1 - Y
                        gx, gy = canvas // 2 + x + X, canvas // 2 + y + Y
                        if 0 <= gx < canvas and 0 <= gy < canvas:
                            px_[gx, gy] = (_rgb(colours[v]) if colours else (255, 0, 255)) + (255,)
    return img


def _crop(im):
    bb = im.getchannel("A").getbbox()
    return im.crop(bb) if bb else None


def overlap(strip_ref, cell, tol: int = 24):
    """Best alignment of `cell` inside `strip_ref` (both RGBA crops).

    Returns (cell_cover, strip_cover): the share of the cell's pixels and of
    the strip frame's pixels that land on a same-colour pixel (each channel
    within `tol`). A clean match has both near 1. A strip frame that also
    holds a detached effect has cell_cover near 1 and strip_cover below it.
    """
    from PIL import Image, ImageChops
    pad = 3
    W = max(strip_ref.width, cell.width) + 2 * pad
    H = max(strip_ref.height, cell.height) + 2 * pad
    A = Image.new("RGBA", (W, H))
    A.paste(strip_ref, (pad, pad))
    a_mask = A.getchannel("A").point(lambda v: 255 if v else 0)
    a_rgb = A.convert("RGB")
    n_poc = a_mask.histogram()[255]
    n_cell = cell.getchannel("A").point(lambda v: 255 if v else 0).histogram()[255]
    best = (0.0, 0.0)
    for dx in range(0, W - cell.width + 1):
        for dy in range(0, H - cell.height + 1):
            B = Image.new("RGBA", (W, H))
            B.paste(cell, (dx, dy))
            b_mask = B.getchannel("A").point(lambda v: 255 if v else 0)
            both = ImageChops.multiply(a_mask, b_mask)
            if both.histogram()[255] < best[0] * n_cell:
                continue
            diff = ImageChops.difference(a_rgb, B.convert("RGB"))
            bad = None
            for ch in diff.split():
                m = ch.point(lambda v: 255 if v > tol else 0)
                bad = m if bad is None else ImageChops.lighter(bad, m)
            good = ImageChops.multiply(both, ImageChops.invert(bad))
            n = good.histogram()[255]
            cand = (n / max(n_cell, 1), n / max(n_poc, 1))
            if cand[0] + cand[1] > best[0] + best[1]:
                best = cand
    return best


def main_texture(anims: dict) -> int:
    """TextureID of the stand animation: the character's main art sheet."""
    return anims[0].keys("TextureID")[0][1]


def main_cells(anims: dict) -> list[int]:
    tex = main_texture(anims)
    return sorted({c for an in anims.values() if an.keys("TextureID")[:1] == [(0, tex)]
                   for _, c in an.keys("BoundsIndex")})


TIE = 0.04  # candidates within this much of the best (cell_cover + strip_cover)


def grade_frame(row: list) -> dict:
    """Turn one strip frame's ranked candidates into {cells, grade, ...}.

    cells: every candidate tied with the best (look-alike cells, e.g. a pose
    two moves share). grade: 'clean' when both covers are 0.9 or more;
    'extra' when the cell is all there but the strip frame holds more art
    (a detached effect); 'weak' when the best cell covers 0.6 or more;
    else 'none' (no main-sheet cell is in this frame). A blank frame
    (no pixels) is 'blank'.
    """
    if row is None:
        return {"cells": [], "grade": "blank"}
    if not row:  # every main-sheet cell is too big to fit in this frame
        return {"cells": [], "grade": "none"}
    b = row[0]
    cc, pc = b["cell_cover"], b["strip_cover"]
    if min(cc, pc) >= 0.9:
        g = "clean"
    elif cc >= 0.85:
        g = "extra"
    elif cc >= 0.6:
        g = "weak"
    else:
        return {"cells": [], "grade": "none", "cell_cover": cc, "strip_cover": pc}
    best = cc + pc
    cells = [r["cell"] for r in row if r["cell_cover"] + r["strip_cover"] >= best - TIE]
    return {"cells": cells, "grade": g, "cell_cover": cc, "strip_cover": pc}


def match_strips(prefix: str, strip_dir: Path, cells: list[int] | None = None) -> dict:
    """For each strip frame in `strip_dir`/sprites.json: its best cells.

    A cell only competes when it is no more than 4 px larger than the strip
    frame on either axis (it has to fit inside). By default only cells some
    main-sheet animation shows compete (Kakashi's cells 167-333 are an
    unused second colour set). The output keeps the best five
    (cell, cell_cover, strip_cover) per frame.
    """
    from PIL import Image
    art = load_art(prefix)
    ids = cells if cells is not None else main_cells(load_anims(prefix))
    crops = {}
    for i in ids:
        c = _crop(render_cell(art, i))
        if c is not None:
            crops[i] = c
    meta = json.loads((strip_dir / "sprites.json").read_text())
    out = {}
    for group in ("anims", "projectiles"):
        for name, m in meta.get(group, {}).items():
            strip = Image.open(strip_dir / group / f"{name}.png").convert("RGBA")
            cw, ch = m["cell"]
            rows = []
            for k in range(m["frames"]):
                f = _crop(strip.crop((k * cw, 0, (k + 1) * cw, ch)))
                if f is None:
                    rows.append(None)  # a blank frame
                    continue
                sc = []
                for i, c in crops.items():
                    if c.width > f.width + 4 or c.height > f.height + 4:
                        continue
                    if c.width * c.height * 4 < f.width * f.height and group == "anims":
                        continue  # a tiny piece cannot be a whole fighter frame
                    cc, pc = overlap(f, c)
                    sc.append((round(cc, 3), round(pc, 3), i))
                sc.sort(key=lambda x: -(x[0] + x[1]))
                rows.append([{"cell": i, "cell_cover": cc, "strip_cover": pc} for cc, pc, i in sc[:5]])
            out[f"{group}/{name}"] = rows
    return out


# ---------------------------------------------------------------- tables


def box_changes(an: Anim, n: int, facing: int = -1) -> int:
    """How many times the animation's boxes change inside its first n frames."""
    return sum(predict(an, t, facing) != predict(an, t - 1, facing) for t in range(1, n))


def end_evidence(anims, an: Anim, cap: Capture, g_end: int, facing: int) -> dict:
    """What the capture shows after the last anim frame.

    end_hold: how many game frames from anim frame `frames` on still show
    the end key's boxes. stand_at: frames after `frames` until the stand
    animation's boxes show. Each is None when the end key's boxes equal
    stand's, because then the capture cannot tell them apart.
    """
    end = predict(an, an.frames, facing)
    stand = predict(anims[0], 0, facing)
    types = box_types(an) | box_types(anims[0])
    if agrees(end, stand, types):  # within the ±1 px tolerance: no signal
        return {"end_hold": None, "stand_at": None}
    hold = 0
    while hold < 8 and agrees(end, p1_elems(cap, g_end + hold), types):
        hold += 1
    stand_at = next((k for k in range(12) if agrees(stand, p1_elems(cap, g_end + k), types)), None)
    return {"end_hold": hold, "stand_at": stand_at}


def check(anims, cap_dir: str, want: int, rule: str, opts: dict, facing: int = -1) -> dict:
    """check_capture on a committed kit capture (`cap_dir` under feel-captures)."""
    cap = load_capture(CAPS / cap_dir / "frames.jsonl")
    return check_capture(anims, cap, f"docs/research/feel-captures/{cap_dir}/frames.jsonl",
                         want, rule, opts, facing)


def check_capture(anims, cap: Capture, label: str, want: int, rule: str, opts: dict,
                  facing: int = -1) -> dict:
    """Replay anim `want` against a capture from `rule`'s anchor.

    Returns the agreement, the frames that disagree, the other animations
    that fit the same frames equally well (only ones at least as long as
    the checked span), when the attack state ends and to what, and when
    the state returns to idle. A pause (at, n) shifts anim frames >= at by
    n game frames; the n paused frames must show frame at-1's boxes.
    opts["then"] = [anim ids]: after the checked span, while the state is 6
    (fall), each frame but the last must show one of these animations'
    frame-0 boxes; the last is checked for the landing animation 0x07.
    """
    anchor = anchor_of(cap, rule)
    an = anims[want]
    n = opts.get("upto", an.frames)
    at, gap = opts.get("pause", (an.frames, 0))

    def game(t):
        return anchor + t + (gap if t >= at else 0)

    def fits(a, frames):
        types = box_types(a)
        return [t for t in frames if not agrees(predict(a, t, facing), p1_elems(cap, game(t)), types)]

    bad = fits(an, range(n))
    types = box_types(an)
    pause_bad = [i for i in range(gap)
                 if not agrees(predict(an, at - 1, facing), p1_elems(cap, anchor + at + i), types)]
    also = sorted(f"0x{aid:02x}" for aid, a in anims.items()
                  if aid != want and a.frames >= n and box_types(a) and not fits(a, range(n)))
    leave = first_leave(cap, anchor, cap.state.get(anchor))
    out = {"capture": label,
           "anchor_rule": rule, "anchor_frame": anchor, "checked_frames": n,
           "agree": n - len(bad), "disagree_at": bad, "box_changes": box_changes(an, n),
           "also_fits": also, "state_return": state_return(cap, anchor),
           "state_end": None if leave is None else {"at": leave, "to": cap.state[anchor + leave]}}
    if n == an.frames:
        out.update(end_evidence(anims, an, cap, game(an.frames), facing))
    if gap:
        out["pause"] = {"before_anim_frame": at, "game_frames": gap,
                        "paused_frames_agree": gap - len(pause_bad)}
    if "then" in opts:
        g = game(n)
        span = [f for f in range(g, g + 400) if cap.state.get(f) == 6]
        span = [f for k, f in enumerate(span) if f == g + k]  # the unbroken run from g
        def shows(a, f):
            return agrees(predict(anims[a], 0, facing), p1_elems(cap, f), box_types(anims[a]))
        # the last fall frame already shows the landing (0x07 starts one frame before state 13)
        fall, last = span[:-1], span[-1:]
        ok = [f for f in fall if any(shows(a, f) for a in opts["then"])]
        out["then"] = {"anims": [f"0x{a:02x}" for a in opts["then"]], "from_anim_frame": n,
                       "fall_frames": len(fall), "agree": len(ok),
                       "last_fall_frame_shows_landing": bool(last) and shows(0x07, last[0])}
    return out


def cells_grade(label: str, cells: list, frames: int, cm: dict, caps: Path = CAPS) -> str:
    """The cells half of a move's grade, "cells measured[ to anim frame N]".

    `cm` = {capture, key, upto?} names a capture dir holding checks.json whose
    `anim[key]` read the live cell per frame (a RAM field). It is only trusted
    when that file says the cells match the static table and its per-cell
    starts equal the decoded `cells` for every start before `upto`.
    """
    upto = cm.get("upto", frames)
    entry = json.loads((caps / cm["capture"] / "checks.json").read_text())["anim"][cm["key"]]
    want = [(c["start"], c["cell"]) for c in cells if c["start"] < upto]
    got = [(f, c) for f, c in entry["state9_cells"] if f < upto]
    if not entry["matches_anim_timing_static"] or got != want:
        raise SystemExit(f"{label}: {cm['capture']} does not measure these cells: "
                         f"capture {got}, decoded {want}")
    return "cells measured" + ("" if upto == frames else f" to anim frame {upto - 1}")


def refusal(chk: dict) -> str | None:
    """Why a move check cannot pin its animation, or None when it can."""
    if chk["disagree_at"]:
        return f"disagrees at anim frames {chk['disagree_at'][:10]}"
    if chk["also_fits"]:
        return f"other animations fit the same frames: {chk['also_fits']}"
    p = chk.get("pause")
    if p and p["paused_frames_agree"] != p["game_frames"]:
        return f"paused frames agree {p['paused_frames_agree']}/{p['game_frames']}"
    t = chk.get("then")
    if t and (t["fall_frames"] == 0 or t["agree"] != t["fall_frames"]
              or not t["last_fall_frame_shows_landing"]):
        return f"fall after the cut agrees {t['agree']}/{t['fall_frames']}"
    return None


def move_gates(label: str, an, chk: dict, opts: dict) -> dict:
    """Build's per-move gates. Returns the extra record fields; raises SystemExit
    when an idle return off `frames + 3` has no `why`, or a `cut` does not sit
    where the attack state ends."""
    extra = {}
    if chk["state_return"] != an.frames + 3:
        if "why" not in opts:
            raise SystemExit(f"{label}: idle return +{chk['state_return']} is not "
                             f"frames + 3 = {an.frames + 3}; MOVES needs a 'why'")
        extra["idle_return_why"] = opts["why"]
    if "cut" in opts:
        cut = opts["cut"]
        if chk["state_end"]["at"] != cut["state_at"] or chk["checked_frames"] != cut["at"]:
            raise SystemExit(f"{label}: the attack state ends at "
                             f"{chk['state_end']}, MOVES says the cut is at {cut['at']}")
        extra["draw"] = {"anim_frames": cut["at"], "then": cut["then"], "cause": cut["cause"]}
    return extra


# ---------------------------------------------------------------- specials 

# The special captures (C1: Kakashi 4, C2: Yusuke 6, C3: Kakashi 5 and 6,
# C4: Yusuke 4 and 5) log one row per battle frame, keyed by s = frame -
# (the special's press + 3), with P1's state and, in some watch sets, P1's
# body element: `ke1` (C1 K, C4 K), `p1e1` (C2 G2), `p1body` (C4 Q) or the
# raw element bytes `raw.h2` (C2 H/H2/H3: +0x0C count, +0x0E id, +0x3C
# sub-rect). Only the body box (element id 0) is compared: those watch sets
# don't read the hit elements. C3 logs no P1 body box at all, nor does C4's
# 4-koma X, so those rows check the state only.


@dataclass
class SpecialCapture:
    label: str
    rows: dict   # s -> {"state": int, "body": (cx, cy, hx, hy) or None}
    plan: dict   # s -> plan frame


def special_body(r: dict):
    """P1's body sub-rect (cx, cy, hx, hy) from one C1/C2 row, or None."""
    for k in ("ke1", "p1e1", "p1body"):
        if k in r:
            e = r[k]
            return tuple(e["sub0"]) if e and e.get("id") == 0 and e.get("cnt") == 1 else None
    b = (r.get("raw") or {}).get("h2")
    if b and _u16(bytes(b), 0x0E) == 0 and _u16(bytes(b), 0x0C) == 1:
        return tuple(_s16(bytes(b), 0x3C + 2 * k) for k in range(4))
    return None


def load_special_capture(rel: str) -> SpecialCapture:
    import gzip
    path = CAPS / f"{rel}.frames.jsonl.gz"
    rows, plan = {}, {}
    with gzip.open(path, "rt") as fh:
        for line in fh:
            if line.strip():
                r = json.loads(line)
                rows[r["s"]] = {"state": r["p1st"], "body": special_body(r)}
                plan[r["s"]] = r["plan"]
    return SpecialCapture(f"docs/research/feel-captures/{rel}.frames.jsonl.gz", rows, plan)


def box_matches(pred: tuple, seen: tuple) -> bool:
    """The capture's whole-pixel box against a predicted one: equal where the
    prediction is whole, within half a pixel where it is a half."""
    return all((abs(p - q) <= 0.5) if p != int(p) else p == q for p, q in zip(pred, seen))


def _body_pred(an: Anim, t: int, facing: int):
    return [p[1:] for p in predict(an, t, facing) if p[0] == 0]


def check_plays(an: Anim, cap: SpecialCapture, rule: str, segments: list, facing: int = -1) -> dict:
    """Replay anim `an` along `segments` against a special capture.

    A segment is ("play", s0, t0, n): s0 .. s0+n-1 show anim frames t0 ..
    t0+n-1; or ("hold", s0, s1, lo, hi): s0 .. s1-1 each show some frame in
    lo..hi (the clock is frozen or loops there; the boxes can't say which).
    The rule's anchor must be s 0: the first non-idle state ('leave_idle')
    or the first state 9 ('state9') at or after s -5. A capture with no body
    box gets no segments: only its anchor and idle return are checked.
    """
    first = next(s for s in sorted(cap.rows) if s >= -5 and (
        cap.rows[s]["state"] == 9 if rule == "state9" else cap.rows[s]["state"] not in (0, 1)))
    if first != 0:
        raise SystemExit(f"{cap.label}: {rule} anchor is s {first}, not s 0")
    want = []
    for seg in segments:
        if seg[0] == "play":
            _, s0, t0, n = seg
            want += [(s0 + i, [t0 + i]) for i in range(n)]
        else:
            _, s0, s1, lo, hi = seg
            want += [(s, list(range(lo, hi + 1))) for s in range(s0, s1)]
    bad, prev, changes = [], None, 0
    for s, ts in want:
        seen = cap.rows.get(s, {}).get("body")
        ok = seen is not None and any(
            len(pb) == 1 and box_matches(pb[0], seen)
            for pb in (_body_pred(an, t, facing) for t in ts))
        if not ok:
            bad.append(s)
        box = _body_pred(an, ts[0], facing)
        changes += prev is not None and box != prev
        prev = box
    back = next((s for s in sorted(cap.rows) if s > 0 and cap.rows[s]["state"] in (0, 1)), None)
    if not any(r["body"] for r in cap.rows.values()):
        if segments:
            raise SystemExit(f"{cap.label}: no body box, so no segments can be checked")
        compared = "P1 state only (this capture logs no P1 body box), s = press + 3"
    else:
        compared = "P1 body box (element id 0), s = press + 3"
    return {"capture": cap.label, "anchor_rule": rule, "anchor_frame": cap.plan[0],
            "compared": compared, "checked_frames": len(want),
            "agree": len(want) - len(bad), "disagree_at": bad, "box_changes": changes,
            "state_return": back}


SPECIAL_STRIPS = REPO / "docs" / "rebuild" / "special-strips.json"


def special_row(char: str, spec: dict, anims: dict, strips: dict) -> dict:
    """One special animation's anim-timing row ."""
    prefix = CHARS[char]["prefix"]
    an = anims[spec["anim"]]
    rec = {"move": spec["move"], "koma": spec["koma"], "archive": f"chr/{prefix}.aar",
           "koma_archive": f"chr/{prefix}_{spec['koma']}.aar", **anim_record(an)}
    strip = strips[char]["strips"][spec["strip"]]
    last = 0
    for c in rec["cells"]:
        c["strip_frames"] = fr = [k for k, cell in enumerate(strip["cells"]) if cell == c["cell"]]
        c["pick"] = next((k for k in fr if k >= last), fr[0]) if fr else None
        last = c["pick"] if c["pick"] is not None else last
        if c["pick"] is None:
            if c["cell"] not in spec.get("missing", {}):
                raise SystemExit(f"{char} {spec['move']}: cell {c['cell']} has no strip frame and no why")
            c["why"] = spec["missing"][c["cell"]]
    used = {k for c in rec["cells"] for k in c["strip_frames"]}
    rec.update({"strip": spec["strip"], "strip_also": [],
                "strip_frames_not_in_anim": [k for k in range(len(strip["cells"])) if k not in used]})
    plays = []
    for path, rel, segs in spec["plays"]:
        chk = check_plays(an, load_special_capture(rel), spec["rule"], segs, spec.get("facing", -1))
        if chk["disagree_at"]:
            raise SystemExit(f"{char} {spec['move']} ({path}): 0x{an.id:02x} disagrees at s {chk['disagree_at'][:10]}")
        plays.append({"path": path, "segments": [list(x) for x in segs], **chk})
    off = [p["state_return"] for p in plays if p["state_return"] != an.frames + 3]
    if off and "idle_return_why" not in spec:
        raise SystemExit(f"{char} {spec['move']} (koma {spec['koma']}): idle at {off}, not frames + 3 = "
                         f"{an.frames + 3}; SPECIALS needs an 'idle_return_why'")
    rec["check"] = {k: v for k, v in plays[0].items() if k not in ("path", "segments")}
    rec["plays"] = plays
    held = any(x[0] == "hold" for _, _, segs in spec["plays"] for x in segs)
    n = f"{len(plays)} path{'s' if len(plays) > 1 else ''}"
    if all(p["checked_frames"] == 0 for p in plays):
        clock = f"start and idle return measured on {n} (no body box read, so no frame is checked)"
    else:
        clock = f"box clock measured on {n}" + (" (held spans: which frame shows is not measured)" if held else "")
    rec["grade"] = clock + ", cells static, strip frames matched on the sheet (special-strips.json)"
    rec["hits"] = [{"record": h[0], "what": h[1], "source": h[2],
                    "grade": h[3] if len(h) > 3 else "measured"} for h in spec["hits"]]
    for k in ("levels", "aliases", "idle_return_why"):
        if k in spec:
            rec[k] = spec[k]
    return rec


def load_strip_map() -> dict:
    return json.loads(STRIP_MAP.read_text()) if STRIP_MAP.exists() else {}


STATE_STRIPS = {"stand", "walk", "dash", "jump", "block", "hit", "down"}


def strip_for(spans: list, strips: dict, prefer: set = frozenset()) -> dict:
    """Pick the fighter strip that holds the most of these cells.

    Ranked by (distinct cells found, strip frames found, name in `prefer`);
    a strip must hold at least half the animation's distinct cells, so one
    look-alike pose does not claim a strip. A tie is reported in
    `strip_also`. Each span gains `strip_frames` (the strip's frames whose
    tied cells include the span's cell; empty when the strip lacks it) and
    `pick` (the first of those frames at or after the previous span's pick,
    so a strip that runs in order maps in order).
    """
    cells = {s["cell"] for s in spans}
    score = {}
    for name, rows in strips.items():
        if name.startswith("projectiles/"):
            continue
        found = {c for c in cells if any(c in r["cells"] for r in rows)}
        nfr = sum(any(c in r["cells"] for c in cells) for r in rows)
        if found and 2 * len(found) >= len(cells):
            score[name] = (len(found), nfr, name in prefer)
    for s in spans:
        s["strip_frames"], s["pick"] = [], None
    if not score:
        return {"strip": None, "strip_also": []}
    top = max(score.values())
    names = sorted(n for n, v in score.items() if v == top)
    rows = strips[names[0]]
    last = 0
    for s in spans:
        s["strip_frames"] = fr = [k for k, r in enumerate(rows) if s["cell"] in r["cells"]]
        if fr:
            s["pick"] = next((k for k in fr if k >= last), fr[0])
            last = s["pick"]
    used = {k for s in spans for k in s["strip_frames"]}
    return {"strip": names[0], "strip_also": names[1:],
            "strip_frames_not_in_anim": [k for k in range(len(rows)) if k not in used]}


def anim_record(an: Anim) -> dict:
    spans, end = segments(an.keys("BoundsIndex"), an.frames)
    tex = an.keys("TextureID")
    return {"anim": f"0x{an.id:02x}", "frames": an.frames, "rate": an.rate,
            "loop": bool(an.loop), "cells": spans, "end_cell": end,
            "texture": tex[0][1] if tex else None}


def _placed(an: Anim, strips: dict, main_tex: int) -> dict:
    rec = anim_record(an)
    if rec["texture"] == main_tex:
        rec.update(strip_for(rec["cells"], strips, STATE_STRIPS if an.id < 0x1E else set()))
    else:
        for s in rec["cells"]:
            s["strip_frames"], s["pick"] = [], None
        rec.update({"strip": None, "strip_also": [], "note": "cells index another art sheet (TextureID)"})
    return rec


def _identity_cells(row, animation, library, sequence):
    from native_texture_identity import frames
    for cell in row["cells"]:
        texture = val_at(animation.keys("TextureID"), cell["start"])
        ids = frames(library, sequence, texture, cell["cell"])
        ordinals = sorted({int(fid[1:]) - 1 for fid in ids})
        cell.update(texture_id=texture, strip_frames=ordinals, pick=ordinals[0],
                    normalized_frame_ids=ids, pick_source="texture_cell_identity")
    row["strip"] = sequence
    row["strip_also"] = []


def _native_body_identity(char, anims, rows):
    if char != "kenshin":
        return
    from native_texture_identity import frames
    import effect_render
    import feature_census
    library = json.loads((REPO / "jus_files/sprites/normalized/kenshin_himura/animations.json").read_text())
    sequences = {0x2A: "k4_up_x_body", 0x2C: "k5_up_x_body", 0x2E: "k6_up_x_body",
                 0x2B: "k5_x_body", 0x27: "air_y_body", 0x23: "up_y_body"}
    for row in rows:
        aid = int(row["anim"], 16)
        if aid in sequences:
            _identity_cells(row, anims[aid], library, sequences[aid])
    shot = feature_census.shot_rows("rk_b_01", native=True)[0]
    if not shot["flags"] & 1 or shot["flags"] & 0x20 or not shot["end_effect"]:
        raise ValueError("reviewed Kenshin terminal effect is missing")
    resource_id = shot["end_effect"]
    effect = effect_render.effect_anims(effect_render.members("rk_b_01_5"), "rk_b_01_5")[resource_id]
    found = []
    for member, almt in mr.motions("rk_b_01"):
        for idx, nodes in almt.native_animations():
            header = almt.base + almt.anim_offsets[idx]
            if struct.unpack_from("<I", almt.buf, header)[0] != resource_id:
                continue
            tracks = {t["prop"]:decode_track(t["prop"], t["kind"], t["raw"])
                      for node in nodes for t in node["entry"]["tracks"]}
            if any(name.startswith("Collision") for name in tracks):
                raise ValueError("terminal effect unexpectedly has collision")
            duration = struct.unpack_from("<H", almt.buf, header+4)[0]
            animation = Anim(effect["anim"], duration, almt.buf[header+6], almt.buf[header+7], tracks)
            sequence = f"k5_x_move_component_rk_b_01_e5_amt_id_{effect['anim']}_node_0"
            row = {**anim_record(animation), "archive":member, "amt":effect["member"], "grade":"static"}
            _identity_cells(row, animation, library, sequence)
            row["playback"] = dict(sequence=sequence,
                age_frames=[frames(library, sequence, val_at(animation.keys("TextureID"), age),
                                   val_at(animation.keys("BoundsIndex"), age))[0] for age in range(duration+1)],
                end="remove")
            found.append(row)
    if len(found) != 1:
        raise ValueError("terminal effect full resource id is not unique")
    rows.extend(found)


def build(chars: dict | None = None) -> dict:
    """The anim-timing document for `chars` (default: the committed roster)."""
    strip_ref = load_strip_map()
    specials = json.loads(SPECIAL_STRIPS.read_text())["characters"]
    doc = {"_schema": "docs/rebuild/anim-timing.md §5",
           "_generated_by": "python3 scripts/analysis/anim_timing.py build",
           "_strip_map": str(STRIP_MAP.relative_to(REPO)),
           "_special_strips": str(SPECIAL_STRIPS.relative_to(REPO)),
           "characters": {}}
    for char, c in (CHARS if chars is None else chars).items():
        meta = char_args.ident(c)
        anims = load_anims(meta["prefix"])
        tex = main_texture(anims)
        strips = strip_ref.get(char, {}).get("strips", {})
        moves, seen = [], set()
        for name, aid, cap_dir, rule, opts in MOVES.get(char, []):
            koma = opts.get("koma")
            rec = {"move": name, "koma": koma, **(
                {"archive": f"chr/{CHARS[char]['prefix']}.aar",
                 "koma_archive": f"chr/{CHARS[char]['prefix']}_{koma}.aar"} if koma is not None else {}),
                **_placed(anims[aid], strips, tex)}
            rec["check"] = chk = check(anims, cap_dir, aid, rule, opts)
            why = refusal(chk)
            if why:
                raise SystemExit(f"{char} {name}: capture does not pin 0x{aid:02x}: {why}")
            for extra in opts.get("also", []):
                more = check(anims, extra, aid, rule, opts)
                why = refusal(more)
                if why:
                    raise SystemExit(f"{char} {name}: {extra} does not pin 0x{aid:02x}: {why}")
                rec.setdefault("check_also", []).append(more)
            rec.update(move_gates(f"{char} {name}", anims[aid], chk, opts))
            full = chk["checked_frames"] == anims[aid].frames
            rec["grade"] = ("box clock measured" if chk["box_changes"] else "start measured") + \
                ("" if full else f" to anim frame {chk['checked_frames'] - 1}") + ", " + \
                (cells_grade(f"{char} {name}", rec["cells"], anims[aid].frames, opts["cells_measured"])
                 if "cells_measured" in opts else "cells static")
            moves.append(rec)
            seen.add(aid)
        for name, aid, koma in STATIC_MOVES.get(char, []):
            moves.append({"move": name, "koma": koma, **_placed(anims[aid], strips, tex),
                          "grade": "static", "label_src": "kit/komamen.toml jus_anim; art clock unmeasured"})
            seen.add(aid)
        for spec in SPECIALS.get(char, []):
            moves.append(special_row(char, spec, anims, specials))
            seen.add(spec["anim"])
        checks = {}
        for aid, what, cap_dir, rule, opts in STATE_CHECKS.get(char, []):
            c = check(anims, cap_dir, aid, rule, opts)
            if c["disagree_at"]:
                raise SystemExit(f"{char} {what}: 0x{aid:02x} disagrees: {c}")
            checks.setdefault(aid, []).append({"what": what, **c})
        states, other = [], []
        for aid in sorted(anims):
            if aid in seen:
                continue
            rec = _placed(anims[aid], strips, tex)
            if aid in checks:
                rec["checks"] = checks[aid]
                rec["grade"] = "start measured, cells static"
            else:
                rec["grade"] = "static"
            (states if aid < 0x1E else other).append(rec)
        _native_body_identity(char, anims, other)
        proj = {n: rows for n, rows in strips.items() if n.startswith("projectiles/")}
        doc["characters"][char] = {**meta, "main_texture": tex, "moves": moves,
                                   "states": states, "other": other,
                                   "projectile_strips": {n: [r["grade"] for r in rows] for n, rows in proj.items()}}
    return doc


def grade_strips(raw: dict) -> dict:
    """Raw `match_strips` rows -> the committed map: strip -> graded frames."""
    return {name.split("/", 1)[1] if name.startswith("anims/") else name:
            [{**grade_frame(row), "ranked": row} for row in rows]
            for name, rows in raw.items()}


TABLE_START = "<!-- generated:anim-timing {char} -->"
TABLE_END = "<!-- /generated:anim-timing {char} -->"


def _cells_md(cells: list) -> str:
    out = []
    for c in cells:
        fr = "/".join(map(str, c["strip_frames"])) if c["strip_frames"] else "none"
        out.append(f"{c['cell']}@{c['start']}+{c['len']}→{fr}")
    return ", ".join(out)


def render_tables(doc: dict, char: str) -> str:
    """The markdown tables anim-timing.md shows for one character."""
    c = doc["characters"][char]
    lines = [TABLE_START.format(char=char), "",
             "| move | anim | frames | cells: cell@start+len→strip frame | end cell | strip | check (capture: agree/checked, idle return) | grade |",
             "|---|---|---|---|---|---|---|---|"]
    for m in c["moves"]:
        if "plays" in m:
            continue
        if m.get("grade") == "static":
            koma = f" (koma {m['koma']})" if m["koma"] is not None else ""
            lines.append(f"| `{m['move']}`{koma} | {m['anim']} | {m['frames']} | {_cells_md(m['cells'])} | "
                         f"{m['end_cell']} | {m['strip'] or 'none'} | art clock unmeasured | static |")
            continue
        k = m["check"]
        cap = k["capture"].split("feel-captures/")[1].rsplit("/frames.jsonl")[0]
        extra = ""
        if "pause" in k:
            extra = f"; pause {k['pause']['game_frames']}f before anim frame {k['pause']['before_anim_frame']}"
        if "draw" in m:
            extra += f"; **draw anim frames 0–{m['draw']['anim_frames'] - 1} only, then {m['draw']['then']}**"
        koma = f" (koma {m['koma']})" if m["koma"] is not None else ""
        lines.append(f"| `{m['move']}`{koma} | {m['anim']} | {m['frames']} | {_cells_md(m['cells'])} | "
                     f"{m['end_cell']} | {m['strip'] or 'none'} | `{cap}`: {k['agree']}/{k['checked_frames']}, "
                     f"+{k['state_return']}{extra} | {m['grade']} |")
    specials = [m for m in c["moves"] if "plays" in m]
    if specials:
        lines += ["", "Specials (koma set, anim in the base amt, art in the koma archive):", "",
                  "| move | koma | anim | frames | cells: cell@start+len→strip frame | strip | "
                  "plays (capture: agree/checked, idle return) | hits (col record: what) | grade |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for m in specials:
            plays = "; ".join(
                f"{p['path']} `{p['capture'].split('feel-captures/')[1].rsplit('.frames.jsonl')[0]}`: "
                f"{p['agree']}/{p['checked_frames']}, +{p['state_return']}" for p in m["plays"])
            hits = ", ".join(f"{h['record']}: {h['what']}" for h in m["hits"])
            lines.append(f"| `{m['move']}` | {m['koma']} | {m['anim']} | {m['frames']} | {_cells_md(m['cells'])} | "
                         f"{m['strip']} | {plays} | {hits} | {m['grade']} |")
    lines += ["", "Moves whose idle return is not `frames + 3` (each needs an override):", "",
              "| move | anim | frames | frames + 3 | idle return | why |", "|---|---|---|---|---|---|"]
    for m in c["moves"]:
        if "idle_return_why" in m:
            back = f"+{m['check']['state_return']}"
            if len(m.get("plays", [])) > 1:
                back = "; ".join(f"{p['path']}: +{p['state_return']}" for p in m["plays"])
            koma = f" {m['koma']}" if m["koma"] is not None else ""
            lines.append(f"| `{m['move']}`{koma} | {m['anim']} | {m['frames']} | {m['frames'] + 3} | "
                         f"{back} | {m['idle_return_why']} |")
    lines += ["", "| anim | frames | loop | cells: cell@start+len→strip frame | strip | evidence | grade |",
              "|---|---|---|---|---|---|---|"]
    for r in c["states"] + c["other"]:
        if r.get("note"):
            continue
        ev = "; ".join(f"{x['what']}: {x['agree']}/{x['checked_frames']}"
                       + (f", also fits {'/'.join(x['also_fits'])}" if x["also_fits"] else "")
                       for x in r.get("checks", [])) or "none"
        lines.append(f"| {r['anim']} | {r['frames']} | {'loop' if r['loop'] else 'hold'} | {_cells_md(r['cells'])} | "
                     f"{r['strip'] or 'none'} | {ev} | {r['grade']} |")
    other = [r["anim"] for r in c["other"] if r.get("note")]
    if other:
        lines += ["", f"On another art file (TextureID is not the main sheet's, so the hand-cut strips "
                  f"cannot show them): {', '.join(other)}."]
    lines += ["", TABLE_END.format(char=char)]
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI


def check_committed(sel: dict | None, out: Path) -> int:
    """--check: 1 if `out` is stale for the characters built, else 0.

    No selection: the roster's whole document must equal the committed bytes.
    A selection: each character's entry must equal its committed entry; one
    the file does not hold only has to decode (its moves list is rows-free).
    """
    doc = build(sel)
    if sel is None:
        text = json.dumps(doc, indent=1) + "\n"
        ok = out.exists() and out.read_text() == text
        print("fresh" if ok else f"stale: rerun {doc['_generated_by']}")
        return 0 if ok else 1
    old = json.loads(out.read_text()).get("characters", {}) if out.exists() else {}
    rc = 0
    for name, new in json.loads(json.dumps(doc))["characters"].items():
        if name not in old:
            print(f"{name}: not in {out.name}; decodes clean ({len(new['states']) + len(new['other'])} "
                  f"state/other animations, {len(new['moves'])} move rows)")
        elif old[name] == new:
            print(f"{name}: fresh")
        else:
            print(f"{name}: stale: rerun {doc['_generated_by']}")
            rc = 1
    return rc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the committed JSON is stale for the roster, or for --char")
    ap.add_argument("--out", type=Path, default=OUT_JSON, help="with --check: the JSON to compare")
    char_args.add_arguments(ap)
    sub = ap.add_subparsers(dest="cmd")
    d = sub.add_parser("decode", help="print an animation's cells and boxes")
    d.add_argument("prefix")
    d.add_argument("anim", nargs="?", type=lambda s: int(s, 0))
    c = sub.add_parser("check", help="rank animations against a capture")
    c.add_argument("prefix")
    c.add_argument("capture", type=Path)
    c.add_argument("--rule", choices=["leave_idle", "state9"], default="leave_idle")
    c.add_argument("--facing", type=int, default=-1)
    tb = sub.add_parser("tables", help="print the markdown tables for anim-timing.md")
    tb.add_argument("char")
    b = sub.add_parser("build", help="write docs/rebuild/anim-timing.json (or --out, for --char)")
    b.add_argument("--out", type=Path, default=OUT_JSON)
    char_args.add_arguments(b)
    a = ap.parse_args(argv)
    if a.check:
        gaps = [str(p.relative_to(REPO)) for p in (SPECIAL_STRIPS, CAPS) if not p.exists()]
        if gaps:
            print("check skipped: needs inputs that are not part of this repository (" + ", ".join(gaps) + ")")
            return 0
        return check_committed(char_args.select(a), a.out)
    if a.cmd is None:
        ap.error("a command or --check is required")
    if a.cmd == "decode":
        anims = load_anims(a.prefix)
        for aid in ([a.anim] if a.anim is not None else sorted(anims)):
            print(json.dumps(anim_record(anims[aid])))
    elif a.cmd == "check":
        anims = load_anims(a.prefix)
        cap = load_capture(a.capture)
        anchor = anchor_of(cap, a.rule)
        print("anchor", anchor, "state_return", state_return(cap, anchor))
        for fr, aid in rank(anims, cap, anchor, a.facing)[:5]:
            bad = score(anims[aid], cap, anchor, a.facing)
            print(f"  0x{aid:02x} frames {anims[aid].frames:3d} agree {fr:.3f} disagree_at {bad[:20]}")
    elif a.cmd == "tables":
        print(render_tables(json.loads(OUT_JSON.read_text()), a.char))
    elif a.cmd == "build":
        sel = char_args.select(a)
        if sel is not None and a.out == OUT_JSON:
            raise SystemExit("--char writes only that character: pass --out FILE, "
                             "or build the whole roster without --char")
        a.out.write_text(json.dumps(build(sel), indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
