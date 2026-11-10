#!/usr/bin/env python3
"""collision_boxes.py -- every animation's collision channels, per character.

A character's ALMT motion table (`chr/<prefix>.aar` -> `<prefix>.amt`) keys
up to seven collision channels per animation: `CollisionType{n}`,
`CollisionEnable{n}` and `CollisionRect{n}` (anim-timing.md §6). anim_timing.py
decodes them to check timing; this tool writes them out whole, so a consumer
that needs a box (for example the guard box, anim 0x03 type 2) reads a committed
file and not the ROM.

    python3 scripts/analysis/collision_boxes.py build          # the whole set
    python3 scripts/analysis/collision_boxes.py build --char eve --chr-b 37 --out FILE
    python3 scripts/analysis/collision_boxes.py --check        # exit 1 when stale

Output: docs/rebuild/collision-boxes.json,
`characters.<name>.animations.<id hex, no prefix>` = `{frames, channels}`;
each channel is `{channel, type, enable, rect}`, each a list of `[frame, value]`
keys as stored (a const track is one key at frame 0), rects `[x0, y0, x1, y1]`
in px relative to the fighter's feet, x positive the way it faces. Only
animations with at least one rect channel are listed. A channel whose
Type/Enable track is absent has an empty list (Enable absent means on).

Characters: decoder_roster.json plus EXTRA (extra victim characters). Any other character is passed with --char/--chr-b (char_args.py)
and is not written to the committed file; add it to EXTRA to commit it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))

import anim_timing as at  # noqa: E402
import char_args  # noqa: E402

OUT_JSON = REPO / "docs" / "rebuild" / "collision-boxes.json"
# Not in decoder_roster.json (that file also drives anim-timing.json and
# vfx-sfx.json): extra victim characters.
EXTRA = {"jotaro": {"chr_b": 28, "prefix": "jj_b_01"}}
CHANNELS = 7


def default_chars() -> dict[str, dict]:
    chars = {n: char_args.ident(c) for n, c in char_args.roster().items()}
    for name, c in EXTRA.items():
        chars[name] = char_args.resolve(name, c["chr_b"], c["prefix"])
        chars[name] = char_args.ident(chars[name])
    return chars


def _keys(an, prop: str, rect: bool = False) -> list:
    return [[f, list(v) if rect else v] for f, v in an.keys(prop)]


def animation(an) -> dict | None:
    chans = []
    for n in range(CHANNELS):
        if not an.keys(f"CollisionRect{n}"):
            continue
        chans.append({"channel": n, "type": _keys(an, f"CollisionType{n}"),
                      "enable": _keys(an, f"CollisionEnable{n}"),
                      "rect": _keys(an, f"CollisionRect{n}", rect=True)})
    return {"frames": an.frames, "channels": chans} if chans else None


def build(chars: dict | None = None) -> dict:
    doc = {"_schema": "scripts/analysis/collision_boxes.py docstring",
           "_generated_by": "python3 scripts/analysis/collision_boxes.py build",
           "characters": {}}
    for name, c in (default_chars() if chars is None else chars).items():
        anims = {}
        for aid, an in sorted(at.load_anims(c["prefix"]).items()):
            rec = animation(an)
            if rec is not None:
                anims[f"{aid:02x}"] = rec
        doc["characters"][name] = {"chr_b": c["chr_b"], "prefix": c["prefix"], "animations": anims}
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 when the committed JSON is stale")
    ap.add_argument("--out", type=Path, default=OUT_JSON)
    char_args.add_arguments(ap)
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("build", help="write docs/rebuild/collision-boxes.json (or --out, for --char)")
    b.add_argument("--out", type=Path, default=OUT_JSON)
    char_args.add_arguments(b)
    a = ap.parse_args(argv)
    sel = char_args.select(a)
    if sel is not None:
        sel = {n: char_args.ident(c) for n, c in sel.items()}
    if a.check:
        text = json.dumps(build(sel), indent=None, separators=(",", ":")) + "\n"
        ok = a.out.exists() and (a.out.read_text() == text if sel is None else True)
        print("fresh" if ok else "stale: rerun python3 scripts/analysis/collision_boxes.py build")
        return 0 if ok else 1
    if a.cmd != "build":
        ap.error("a command or --check is required")
    if sel is not None and a.out == OUT_JSON:
        raise SystemExit("--char writes only that character: pass --out FILE, "
                         "or build the whole set without --char")
    a.out.write_text(json.dumps(build(sel), indent=None, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
