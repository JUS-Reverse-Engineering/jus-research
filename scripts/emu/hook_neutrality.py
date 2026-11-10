#!/usr/bin/env python3
"""Hook neutrality of native captures: does recording with the call hooks change what the emulator produced?

A capture bundle is a run directory with request.json (tag, cell, mode, recipe, masks, watches) and native/ holding frames.tsv, the
512 rendered frames (frames-ppm.tar.gz, members %06d.ppm), audio.bin (16-byte packets; frame i owns packets
[audio_offset, audio_offset + audio_count)) and watches.tsv (the RAM watch definitions). compare() reads two bundles and tests real
byte equality of every emulated output: each PPM, the whole audio stream, every frames.tsv column (the emulated clock
start_tick/end_tick that bounds each frame's audio samples, the RAM snapshot ram_hex and the watch columns included) and the watch
definitions. No column is left out, and a header other than COLUMNS is refused.

manifest() is the per-frame digest table of one bundle (sha256 of each PPM, audio slice, ram_hex and the watch columns, with the
small columns verbatim), so a bundle too large to commit is represented by bytes that change when any compared byte does.
provenance() names the source files of a bundle by sha256 and size. `record ROOT OUT` compares every unhooked bundle u-<cell> under
ROOT with each hooked repeat m-<cell>-r<n> and writes OUT/manifests/<tag>.json.gz, OUT/provenance/<tag>.json and OUT/neutrality.json.
"""
import csv
import gzip
import hashlib
import json
import sys
import tarfile
from pathlib import Path

SCHEMA = "hook-neutrality/v1"
# frames.tsv as native_media/validate_capture.py reads it: start_tick/end_tick are the emulated clock (frame i starts where frame
# i-1 ended and its audio samples are stamped inside it), not host time
COLUMNS = ("sequence", "nds_frame", "start_tick", "end_tick", "key_mask", "audio_offset", "audio_count", "ram_hex", "held_left",
           "held_right", "watch_present", "watch_addresses", "watch_paths")
SMALL_COLUMNS = ("sequence", "nds_frame", "start_tick", "end_tick", "key_mask", "audio_offset", "audio_count", "held_left",
                 "held_right")
WATCH_COLUMNS = ("watch_present", "watch_addresses", "watch_paths")
AUDIO_PACKET = 16
SOURCES = ("request.json", "native/frames.tsv", "native/frames-ppm.tar.gz", "native/audio.bin", "native/watches.tsv")
# hook outputs, present only in a hooked capture
HOOK_SOURCES = ("native/hooks.json", "native/calls.tsv")


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def load(native):
    """The emulated outputs of one native/ directory: {rows, ppm: [bytes per frame], audio, watches}. Refuses (ValueError) a
    frames.tsv header other than COLUMNS, PPM members that are not exactly %06d.ppm for every row, and an audio
    stream whose length or frame slices do not tile it in AUDIO_PACKET packets."""
    native = Path(native)
    lines = (native / "frames.tsv").read_text().splitlines()
    rows = list(csv.DictReader(lines, delimiter="\t"))
    header = lines[0].split("\t")
    if header != list(COLUMNS):
        raise ValueError("%s: frames.tsv columns %s, expected %s" % (native, header, list(COLUMNS)))
    with tarfile.open(native / "frames-ppm.tar.gz", "r:gz") as tf:
        members = {Path(m.name).name: tf.extractfile(m).read() for m in tf if m.isfile()}
    names = ["%06d.ppm" % i for i in range(len(rows))]
    if sorted(members) != names:
        raise ValueError("%s: %d PPM members for %d frames" % (native, len(members), len(rows)))
    audio = (native / "audio.bin").read_bytes()
    pos = 0
    for r in rows:
        if int(r["audio_offset"]) != pos:
            raise ValueError("%s: frame %s audio_offset %s, expected %d" % (native, r["sequence"], r["audio_offset"], pos))
        pos += int(r["audio_count"])
    if len(audio) != pos * AUDIO_PACKET:
        raise ValueError("%s: audio.bin %d bytes for %d packets of %d" % (native, len(audio), pos, AUDIO_PACKET))
    return {"rows": rows, "ppm": [members[n] for n in names], "audio": audio, "watches": (native / "watches.tsv").read_bytes()}


def compare(a, b):
    """Byte differences between the emulated outputs of two native/ directories: [[field, sequence or None], ...], empty when every
    compared byte is equal."""
    x, y = load(a), load(b)
    out = []
    if len(x["rows"]) != len(y["rows"]):
        out.append(["frames", None])
    for rx, ry, px, py in zip(x["rows"], y["rows"], x["ppm"], y["ppm"]):
        out += [[c, rx["sequence"]] for c in COLUMNS if rx[c] != ry[c]]
        if px != py:
            out.append(["ppm", rx["sequence"]])
    if x["audio"] != y["audio"]:
        out.append(["audio", None])
    if x["watches"] != y["watches"]:
        out.append(["watches.tsv", None])
    return out


def manifest(native):
    """The per-frame digest table of one native/ directory. Each frame row: the SMALL_COLUMNS verbatim, then the sha256 of ram_hex,
    of the WATCH_COLUMNS joined by tabs, of the PPM bytes and of the frame's audio slice."""
    d = load(native)
    frames = []
    for r, ppm in zip(d["rows"], d["ppm"]):
        o, n = int(r["audio_offset"]) * AUDIO_PACKET, int(r["audio_count"]) * AUDIO_PACKET
        frames.append([r[c] for c in SMALL_COLUMNS] + [_sha(r["ram_hex"].encode()), _sha("\t".join(r[c] for c in WATCH_COLUMNS).encode()),
                                                      _sha(ppm), _sha(d["audio"][o:o + n])])
    return {"schema": SCHEMA, "columns": list(SMALL_COLUMNS) + ["ram_hex_sha256", "watch_sha256", "ppm_sha256", "audio_sha256"],
            "audio_packet_bytes": AUDIO_PACKET, "audio_bytes": len(d["audio"]), "audio_sha256": _sha(d["audio"]),
            "watches_tsv_sha256": _sha(d["watches"]), "frames": frames}


def provenance(run):
    """Where a bundle's bytes came from: its tag, cell and capture mode (request.json), the hook table when hooked
    (native/hooks.json), and the sha256 and size of each source file read and of each hook output present (HOOK_SOURCES)."""
    run = Path(run)
    req = json.loads((run / "request.json").read_text())
    hooks = run / "native" / "hooks.json"
    return {"schema": SCHEMA, "tag": req["tag"], "cell": req["cell"], "mode": req["mode"],
            "hooks": json.loads(hooks.read_text()) if hooks.is_file() else None,
            "files": {p: {"sha256": _sha((run / p).read_bytes()), "bytes": (run / p).stat().st_size}
                      for p in SOURCES + HOOK_SOURCES if p in SOURCES or (run / p).is_file()}}


def record(root, out):
    """Compare each unhooked bundle u-<cell> under `root` with its hooked repeats m-<cell>-r<n> and write the committed record to
    `out`. Returns the neutrality table {cell: {unhooked, hooked: {tag: differences}}}."""
    root, out = Path(root), Path(out)
    (out / "manifests").mkdir(parents=True, exist_ok=True)
    (out / "provenance").mkdir(exist_ok=True)
    table = {}
    for u in sorted(root.glob("u-*")):
        cell = u.name[2:]
        hooked = sorted(root.glob("m-%s-r*" % cell))
        if not hooked:
            raise ValueError("%s: no hooked repeat" % u.name)
        for run in [u] + hooked:
            p = provenance(run)
            if p["mode"] != ("unhooked" if run is u else "hooked") or p["cell"] != cell:
                raise ValueError("%s: request says %s %s" % (run.name, p["mode"], p["cell"]))
            (out / "provenance" / (run.name + ".json")).write_text(json.dumps(p, indent=1, sort_keys=True) + "\n")
            (out / "manifests" / (run.name + ".json.gz")).write_bytes(
                gzip.compress((json.dumps(manifest(run / "native"), separators=(",", ":")) + "\n").encode(), compresslevel=9, mtime=0))
        table[cell] = {"unhooked": u.name, "hooked": {h.name: compare(u / "native", h / "native") for h in hooked}}
    (out / "neutrality.json").write_text(json.dumps({"schema": SCHEMA, "columns": list(COLUMNS), "cells": table},
                                                    indent=1, sort_keys=True) + "\n")
    return table


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    c = sub.add_parser("compare", help="byte differences of two native/ directories")
    c.add_argument("a")
    c.add_argument("b")
    r = sub.add_parser("record", help="compare u-<cell> with m-<cell>-r<n> under ROOT and write the record to OUT")
    r.add_argument("root")
    r.add_argument("out")
    a = ap.parse_args()
    if a.command == "compare":
        diff = compare(a.a, a.b)
        print(json.dumps(diff))
        sys.exit(1 if diff else 0)
    t = record(a.root, a.out)
    bad = {k: {h: d for h, d in v["hooked"].items() if d} for k, v in t.items()}
    bad = {k: v for k, v in bad.items() if v}
    print(json.dumps(bad) if bad else "all hooked repeats byte-equal to their unhooked capture")
    sys.exit(1 if bad else 0)
