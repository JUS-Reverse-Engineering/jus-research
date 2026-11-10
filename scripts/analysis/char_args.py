#!/usr/bin/env python3
"""char_args.py -- which character the analysis decoders run on.

anim_timing.py and vfx_sfx_build.py write one committed JSON for a roster of
characters. The roster is decoder_roster.json (name, chr_b, prefix, in output
order). A character that is not in it comes from the command line:

    --char eve --chr-b 37            prefix from the chr_b mapping doc (bc_b_01)
    --char eve --chr-b 37 --prefix bc_b_01
    --char eve                       chr_b from kit/eve.toml [fixture.attacker]

Every resolved pair is checked against docs/research/chr_b-Complete-Mapping.md
(the archive that chr_b names) and, when kit/<name>.toml exists, against its
chr_b, so a wrong index fails here and not as a plausible-looking table.
"""
from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
ROSTER = HERE / "decoder_roster.json"
MAPPING = REPO / "docs" / "research" / "chr_b-Complete-Mapping.md"
KIT = REPO / "kit"

_MAP_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*([a-z]{2}_b_\d+)")


def roster() -> dict[str, dict]:
    """name -> {chr_b, prefix[, sound_seqarc]} for the committed JSON, in output order.

    Each entry is checked like a command-line one, so a wrong index in
    decoder_roster.json fails every decoder run."""
    chars = json.loads(ROSTER.read_text())["characters"]
    for name, c in chars.items():
        _validate(name, c["chr_b"], c["prefix"])
    return chars


def ident(c: dict) -> dict:
    """The two fields anim-timing.json carries per character."""
    return {"chr_b": c["chr_b"], "prefix": c["prefix"]}


def mapping_prefix(chr_b: int) -> str | None:
    """The chr/<prefix> archive the mapping doc gives a chr_b (its File column)."""
    for line in MAPPING.read_text(encoding="utf-8").splitlines():
        m = _MAP_ROW.match(line)
        if m and int(m.group(1)) == chr_b:
            return m.group(2)
    return None


def kit_chr_b(name: str) -> int | None:
    """chr_b from kit/<name>.toml [fixture.attacker], or None without such a file."""
    path = KIT / f"{name}.toml"
    if not path.exists():
        return None
    with path.open("rb") as f:
        return tomllib.load(f).get("fixture", {}).get("attacker", {}).get("chr_b")


def add_arguments(ap) -> None:
    ap.add_argument("--char", action="append", metavar="NAME",
                    help="character to run on (repeatable); default: the whole roster")
    ap.add_argument("--chr-b", type=int, dest="chr_b",
                    help="chr_b of a character that is not in the roster")
    ap.add_argument("--prefix", help="chr/<prefix>.aar of that character (default: the mapping doc's)")
    ap.add_argument("--seqarc", help="SDAT sequence archive to render that character's sounds from")


def _validate(name: str, chr_b: int, prefix: str | None) -> str | None:
    """Refuse a chr_b that the kit file or the mapping doc contradicts; return the doc's prefix."""
    kit = kit_chr_b(name)
    if kit is not None and kit != chr_b:
        raise SystemExit(f"{name}: chr_b {chr_b} but kit/{name}.toml says {kit}")
    doc = mapping_prefix(chr_b)
    if prefix is not None and doc is not None and doc != prefix:
        raise SystemExit(f"{name}: chr_b {chr_b} is {doc} in {MAPPING.name}, not {prefix}")
    return doc


def resolve(name: str, chr_b: int | None = None, prefix: str | None = None,
            seqarc: str | None = None) -> dict:
    name = name.lower()
    known = roster().get(name, {})
    chr_b = chr_b if chr_b is not None else known.get("chr_b", kit_chr_b(name))
    if chr_b is None:
        raise SystemExit(f"{name}: not in decoder_roster.json and no kit/{name}.toml; pass --chr-b")
    prefix = prefix or known.get("prefix") or _validate(name, chr_b, None)
    if prefix is None:
        raise SystemExit(f"{name}: chr_b {chr_b} is not in {MAPPING.name}; pass --prefix")
    _validate(name, chr_b, prefix)
    out = {"chr_b": chr_b, "prefix": prefix}
    seqarc = seqarc or known.get("sound_seqarc")
    if seqarc:
        out["sound_seqarc"] = seqarc
    return out


def select(args) -> dict[str, dict] | None:
    """The characters the command line names, resolved; None when it names none."""
    chars = args.char or []
    extra = (args.chr_b, args.prefix, args.seqarc)
    if not chars:
        if any(x is not None for x in extra):
            raise SystemExit("--chr-b, --prefix and --seqarc need --char NAME")
        return None
    if len(chars) > 1 and any(x is not None for x in extra):
        raise SystemExit("--chr-b, --prefix and --seqarc go with one --char")
    return {c.lower(): resolve(c, *extra) if len(chars) == 1 else resolve(c) for c in chars}
