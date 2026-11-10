#!/usr/bin/env python3
"""hitbox_strip.py -- render a per-frame PNG strip and a first/last-active
table from a scripts/gdb/atns41_hitbox_dump.gdb JSONL capture.

Why this exists
----------------
`jus-atns.4.1` asks for bounding-rect drawings around hitboxes, the way other
fighting-game docs draw them, in place of kakashi.md's contact-time-only
measurements. The GDB probe (`scripts/gdb/atns41_hitbox_dump.gdb`) logs per
frame: a `frame` line (frame number), 0-2 `fighter` lines (obj/state/M/
flags78), and 0-N `elem` lines -- one per geometry element walked off a live
ColPrm record's wrapper (`record+0x60`), per
`docs/research/findings/hitbox-node-geometry-static.md` §0: each element
carries an id, a live sub-element count (`cnt`, the active gate), a
back-pointer to its wrapper (`e20`), its own centre-offset/half-extent
rectangle, and up to `cnt` sub-element rectangles.

This module also reads the *old* wrapper-based format (`type: "node"`,
predating the geometry-object fix) so already-committed legacy captures still
parse without crashing -- cheap to keep since the two shapes are structurally
similar (a whole-object rect plus a sub list). Old-format lines carry no
`id`/`e20`, so `hitbox_check.py`'s element-identity checks skip them.

This script does not interpret hit/hurt semantics (no gameplay naming, per the
ticket brief): elements are colored only by structural identity (id 0, the
body element, vs any other id), not gameplay meaning.

Coordinate handling
--------------------
Per `jus-atns.4.1` step 2, and the Refuter's correction (2026-09-12 19:10,
"Rect grows from a point is wrong"): the element's own aggregate rect
(`+0x2c/+0x2e`/`+0x30/+0x32`) is zero on the spawn frame while the SUB-rect
(`+0x3c + j*8`) already carries the full box on the spawn frame (its offset/half-extent can still
change within the window) -- the sub-rect is the hitbox. So `centre = (pos/4096 + offset)`,
`half-extent` in px is computed from the **first sub-rect** when one exists;
the aggregate rect is used only as a fallback when an element has no subs
(`cnt == 0` or an empty `sub` list) -- never to describe "growth" from a
degenerate point. `pos` is the raw 32-bit world position this probe reads
off the element's own owner chain (`*(*(elem+8)+4)+0x50`, x/y/z at
+0xc/+0x10/+0x14) and `offset`/`half-extent` are already integer px, per the
finding. Only elements with `cnt > 0` (the active gate) are drawn or listed
in the active-frame table -- inactive elements go stale (per the finding's
own note) and are not meaningful geometry. The active-frame table and CSV
group by **(record, id)**, not record alone (the Refuter's note: grouping
by record alone hides distinct elements sharing a record, e.g. a body
element and a move-specific element coexisting on the same record).

Usage
-----
    python3 hitbox_strip.py CAPTURE.jsonl --out-dir OUT/ [--attack NAME]

Writes OUT/strip.png (one row of small per-frame panels), OUT/frames.csv
(one row per active element per frame), and OUT/active_frames.md (first/last
active frame per record).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from dataclasses import dataclass, field

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - exercised only when PIL is missing
    Image = ImageDraw = ImageFont = None


BODY_ELEM_COLOR = (220, 90, 90)    # id == 0 (body element)
OTHER_ELEM_COLOR = (70, 130, 200)  # any other id (or old-format/unknown id)
FIGHTER_LABEL_COLOR = (90, 90, 90)  # fighter state-code caption, not a rect
BG_COLOR = (255, 255, 255)
PANEL_PAD = 8
PANEL_SIZE = 96
POS_SCALE = 4096.0  # pos/4096 + offset == centre, in px (jus-atns.4.1 step 2)


@dataclass
class Rect:
    """An axis-aligned rectangle: centre = pos/4096 (x, y only) + off;
    extents are half-extents (cx, cy). Both off and half are already in
    px per the finding this probe is built from."""

    off_x: float
    off_y: float
    half_x: float
    half_y: float
    kind: str  # "elem" (the element's own rect) or "sub"

    def bounds(self, pos_x: float, pos_y: float):
        """Live captures can carry negative half-extents in stale/garbage
        slots; min()/max() here keep every rect axis-ordered for PIL
        without dropping or reinterpreting the raw sign -- write_csv()
        still logs the untouched off/half values."""
        cx = pos_x / POS_SCALE + self.off_x
        cy = pos_y / POS_SCALE + self.off_y
        x0, x1 = cx - self.half_x, cx + self.half_x
        y0, y1 = cy - self.half_y, cy + self.half_y
        return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


@dataclass
class FrameData:
    frame: int
    fighters: list = field(default_factory=list)  # each: dict(slot, obj, state, M, flags78)
    nodes: list = field(default_factory=list)      # each: dict(record, elem, id, cnt, e20, pos, rects=[Rect,...])


def _to_int(v) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        return int(v, 16) if v.lower().startswith("0x") else int(v)
    return 0


def load_jsonl(path: str) -> list[FrameData]:
    """Parse the GDB probe's JSONL into one FrameData per `frame` line, in
    the order frames appeared. Lines with an unrecognized `type` are
    ignored (forward-compatible with a probe that logs more line types).
    Understands both the current per-element format (`type: "elem"`) and
    the legacy per-wrapper format (`type: "node"`, pre-jus-atns.4.1 fix)."""
    frames: dict[int, FrameData] = {}
    order: list[int] = []

    def get_frame(n: int) -> FrameData:
        if n not in frames:
            frames[n] = FrameData(frame=n)
            order.append(n)
        return frames[n]

    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = obj.get("type")
            if t == "frame":
                get_frame(obj["frame"])
            elif t == "fighter":
                fd = get_frame(obj["frame"])
                fd.fighters.append(obj)
            elif t == "elem":
                fd = get_frame(obj["frame"])
                fd.nodes.append(_parse_elem(obj))
            elif t == "node":
                fd = get_frame(obj["frame"])
                fd.nodes.append(_parse_legacy_node(obj))

    return [frames[n] for n in order]


def _parse_elem(obj: dict) -> dict:
    cnt = obj.get("cnt", 0)
    rects = [
        Rect(
            off_x=obj["extent_off"][0],
            off_y=obj["extent_off"][1],
            half_x=obj["half_extent"][0],
            half_y=obj["half_extent"][1],
            kind="elem",
        )
    ]
    for sub in obj.get("sub", []):
        if len(sub) != 4:
            continue
        soff_x, soff_y, shx, shy = sub
        rects.append(Rect(off_x=soff_x, off_y=soff_y, half_x=shx, half_y=shy, kind="sub"))
    return {
        "record": obj["record"],
        "elem": obj.get("elem"),
        "id": obj.get("id"),
        "cnt": cnt,
        "e20": obj.get("e20"),
        "pos": obj.get("pos", [0, 0, 0]),
        "rects": rects,
    }


def _parse_legacy_node(obj: dict) -> dict:
    """Old wrapper-based format (`record+0x60` read directly, before the
    jus-atns.4.1 element-layout fix). No `id`/`e20` -- callers that need
    element identity (hitbox_check.py) must treat these as unsupported."""
    cnt = obj.get("subcount", 0)
    rects = [
        Rect(
            off_x=obj["extent_off"][0],
            off_y=obj["extent_off"][1],
            half_x=obj["half_extent"][0],
            half_y=obj["half_extent"][1],
            kind="elem",
        )
    ]
    for sub in obj.get("sub", []):
        if len(sub) != 4:
            continue
        soff_x, soff_y, shx, shy = sub
        rects.append(Rect(off_x=soff_x, off_y=soff_y, half_x=shx, half_y=shy, kind="sub"))
    return {
        "record": obj["record"],
        "elem": obj.get("colobj"),
        "id": None,
        "cnt": cnt,
        "e20": None,
        "pos": obj.get("pos", [0, 0, 0]),
        "rects": rects,
    }


def _display_rects(node: dict) -> list:
    """The rect(s) that represent this element's actual hitbox: every
    sub-rect (`kind == "sub"`) when at least one exists, falling back to
    the element's own aggregate rect (`kind == "elem"`) only when there is
    no sub -- per the Refuter's correction (2026-09-12 19:10): the
    aggregate is zero on the spawn frame while the sub already carries the
    full, constant box, so "the sub-rect is the hitbox," never the
    aggregate."""
    subs = [r for r in node["rects"] if r.kind == "sub"]
    if subs:
        return subs
    return [r for r in node["rects"] if r.kind == "elem"]


def active_records(frames: list[FrameData]):
    """Per (record, id), the first and last frame it appeared with an
    active element (`cnt > 0`) -- deliverable 3's "first/last active
    hitbox frame" table. Keyed by (record, id) rather than record alone
    (Refuter, 2026-09-12 19:10): grouping by record alone hides distinct
    elements that coexist on the same record (e.g. a body element and a
    move-specific element)."""
    first: dict[tuple, int] = {}
    last: dict[tuple, int] = {}
    for fd in frames:
        for node in fd.nodes:
            if node["cnt"] <= 0:
                continue
            key = (node["record"], node["id"])
            first.setdefault(key, fd.frame)
            last[key] = fd.frame
    return first, last


def write_csv(frames: list[FrameData], out_path: str) -> None:
    """One row per active *sub* (or display rect) per active element per
    frame (`cnt > 0` only), with the element's own position and each rect
    from `_display_rects` (the sub-rects, or the aggregate when there is
    no sub). jus-atns.4.2: the previous version emitted only
    `_display_rects(node)[0]`, silently dropping every sub past the
    first on any element with more than one live sub-rect. `rect_index`
    is the 0-based position of that row's rect within
    `_display_rects(node)` for that element/frame, so multiple rows for
    the same (frame, record, id) can be told apart and re-grouped."""
    with open(out_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "frame",
                "record",
                "id",
                "cnt",
                "e20",
                "pos_x",
                "pos_y",
                "pos_z",
                "rect_index",
                "rect_kind",
                "off_x",
                "off_y",
                "half_x",
                "half_y",
            ]
        )
        for fd in frames:
            for node in fd.nodes:
                if node["cnt"] <= 0:
                    continue
                pos = node.get("pos", [0, 0, 0])
                rects = _display_rects(node)
                rows = rects if rects else [None]
                for idx, r in enumerate(rows):
                    writer.writerow(
                        [
                            fd.frame,
                            node["record"],
                            node["id"],
                            node["cnt"],
                            node.get("e20"),
                            pos[0],
                            pos[1],
                            pos[2] if len(pos) > 2 else 0,
                            idx,
                            r.kind if r else "",
                            r.off_x if r else "",
                            r.off_y if r else "",
                            r.half_x if r else "",
                            r.half_y if r else "",
                        ]
                    )


def write_markdown_table(frames: list[FrameData], out_path: str, attack: str) -> None:
    first, last = active_records(frames)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("# %s -- first/last active hitbox frame\n\n" % attack)
        fh.write("| record | id | first active frame | last active frame |\n")
        fh.write("|---|---|---|---|\n")
        for key in sorted(first):
            rec, elem_id = key
            fh.write("| %d | %s | %d | %d |\n" % (rec, elem_id, first[key], last[key]))
        if not first:
            fh.write("| (none) | -- | -- | -- |\n")


def _active_nodes(fd: FrameData):
    return [n for n in fd.nodes if n["cnt"] > 0]


def _panel_bounds(frames: list[FrameData]):
    """Bounding box (in px, pos/4096 + offset already folded in) over
    every active-element's display rect in every frame, so one fixed
    pixel scale covers the whole strip."""
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    any_rect = False
    for fd in frames:
        for node in _active_nodes(fd):
            px, py = node["pos"][0], node["pos"][1]
            for r in _display_rects(node):
                x0, y0, x1, y1 = r.bounds(px, py)
                min_x, min_y = min(min_x, x0), min(min_y, y0)
                max_x, max_y = max(max_x, x1), max(max_y, y1)
                any_rect = True
    if not any_rect:
        return (-1.0, -1.0, 1.0, 1.0)
    pad_x = max((max_x - min_x) * 0.1, 1.0)
    pad_y = max((max_y - min_y) * 0.1, 1.0)
    return (min_x - pad_x, min_y - pad_y, max_x + pad_x, max_y + pad_y)


def render_strip(frames: list[FrameData], out_path: str, attack: str) -> None:
    if Image is None:
        raise RuntimeError("Pillow is required to render PNGs (pip install pillow)")

    bounds = _panel_bounds(frames)
    bmin_x, bmin_y, bmax_x, bmax_y = bounds
    span_x = max(bmax_x - bmin_x, 1e-6)
    span_y = max(bmax_y - bmin_y, 1e-6)
    scale = (PANEL_SIZE - 2 * PANEL_PAD) / max(span_x, span_y)

    def to_px(x: float, y: float):
        px = PANEL_PAD + (x - bmin_x) * scale
        py = PANEL_PAD + (y - bmin_y) * scale
        return px, py

    n = max(len(frames), 1)
    strip = Image.new("RGB", (PANEL_SIZE * n, PANEL_SIZE + 20), BG_COLOR)
    draw = ImageDraw.Draw(strip)
    font = ImageFont.load_default()

    for i, fd in enumerate(frames):
        panel_x0 = i * PANEL_SIZE
        draw.rectangle(
            [panel_x0, 0, panel_x0 + PANEL_SIZE - 1, PANEL_SIZE - 1],
            outline=(200, 200, 200),
        )
        for node in _active_nodes(fd):
            px, py = node["pos"][0], node["pos"][1]
            color = BODY_ELEM_COLOR if node.get("id") == 0 else OTHER_ELEM_COLOR
            for r in _display_rects(node):
                x0, y0, x1, y1 = r.bounds(px, py)
                px0, py0 = to_px(x0, y0)
                px1, py1 = to_px(x1, y1)
                draw.rectangle(
                    [panel_x0 + px0, py0, panel_x0 + px1, py1], outline=color
                )
        for fighter in fd.fighters:
            state = fighter.get("state", -1)
            label = "s%d" % state if fighter.get("slot") == 0 else "S%d" % state
            draw.text((panel_x0 + 2, PANEL_SIZE + 2), label, fill=FIGHTER_LABEL_COLOR, font=font)
        draw.text((panel_x0 + 2, PANEL_SIZE - 12), str(fd.frame), fill=(0, 0, 0), font=font)

    strip.save(out_path)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("jsonl", help="capture file from atns41_hitbox_dump.gdb")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--attack", default=None, help="label for the markdown table")
    args = ap.parse_args(argv)

    os.makedirs(args.out_dir, exist_ok=True)
    frames = load_jsonl(args.jsonl)
    if not frames:
        print(
            "%s: no frame records in the capture. Most likely the battle was "
            "paused (a stray START opened the pause menu, so the per-frame "
            "anchor never fired) or the probe never attached; see "
            "scripts/gdb/atns41_hitbox_dump.gdb header." % args.jsonl,
            file=sys.stderr,
        )
        return 2
    attack = args.attack or os.path.basename(os.path.dirname(os.path.abspath(args.jsonl)))

    write_csv(frames, os.path.join(args.out_dir, "frames.csv"))
    write_markdown_table(frames, os.path.join(args.out_dir, "active_frames.md"), attack)
    render_strip(frames, os.path.join(args.out_dir, "strip.png"), attack)

    first, last = active_records(frames)
    print(
        "%s: %d frames, %d records with an active element"
        % (attack, len(frames), len(first))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
