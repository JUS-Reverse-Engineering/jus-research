#!/usr/bin/env python3
"""Byte-diff the Ichigo Y-variant captures against each other.

Reads the `*.capture.json` files written by `ichigo_y_capture.py` and writes
a `DIFF.md` that answers one question: do the Y variants use the same backing
bytes? For each structure (ObjShot element, the position element at
`[record+0x5C]`, the entity's first 0x100 bytes, the ColPrm record, the
record's first node, the resolved collision entry) it lists every byte offset
whose value differs across the captures that spawned, with the value per
state.

Two categories are pulled out of the raw byte diff instead of being reported
as byte differences:

- **Pointer words.** Any 4-byte aligned word that holds a value in
  `0x02000000..0x023FFFFF` in *any* capture is a pointer word. Its four
  bytes are listed once, as a pointer, marked same-target or
  different-target -- a different allocation address is not a difference in
  content.
- **Explicitly excluded offsets.** The ObjShot element's `+0x18` word and
  the position element's `+0x0C`/`+0x10` x/y, which change every frame by
  construction. Every excluded offset is listed in DIFF.md with its reason.
  Nothing else is masked.

DIFF.md also reports, per structure, how many bytes survived that masking and
how many of those are nonzero in any capture, so "byte-identical" can be read
with its comparison surface attached -- most of the entity and record is zero.

Two derived relations are checked against the data rather than asserted:
the first node's `+0x26` byte against `id - 0x100`, and the position
element's s16 pair at `+0x24`/`+0x26` against the measured one-frame dx/dy.

Field-offsets-only output, same rule as `projectile_census.py`: no gameplay
names for any bit, only offsets.
"""
import argparse
import json
import os
import struct
import sys

RAM_LOW = 0x02000000
RAM_HIGH = 0x02400000

WORD_SIZE = 4

# Structures diffed, in report order.
STRUCTURES = ["element", "position_element", "entity", "record",
              "node0", "entry"]

STRUCTURE_TITLES = {
    "element": "ObjShot element (0x6C bytes)",
    "position_element": "Position element (`[record+0x5C]`, 0x40 bytes)",
    "entity": "Entity first 0x100 bytes (`element+0x2C`)",
    "record": "ColPrm record (0x188 bytes)",
    "node0": "First node on the record's `+0x08` list (0x2C bytes)",
    "entry": "Resolved collision entry (0x14 bytes)",
}

# Offsets excluded from a byte diff, with the reason recorded in DIFF.md.
# Nothing else is masked: `+0x0C`/`+0x10` on the ObjShot element are RAM
# pointers and so fall under the pointer rule, and every other offset is
# diffed and listed.
ELEMENT_EXCLUDED = {
    0x18: "low half of the u16 word `projectile_census.py` reads as the "
          "lifetime; it counts down once per frame and the captures were "
          "frozen at different points in the shot's life",
    0x19: "high half of the same u16 word",
}

POSITION_ELEMENT_EXCLUDED = {}
for _off in range(0x0C, 0x14):
    POSITION_ELEMENT_EXCLUDED[_off] = (
        "`+0x0C`/`+0x10` current x/y; the six saves have Ichigo standing in "
        "different places, so these differ for reasons that have nothing to "
        "do with which of the six saves it is")

EXCLUDED = {"element": ELEMENT_EXCLUDED,
            "position_element": POSITION_ELEMENT_EXCLUDED}


def is_ram_ptr(v):
    return RAM_LOW <= v < RAM_HIGH


def hexw(v):
    return "0x%08X" % (v & 0xFFFFFFFF) if v is not None else None


def pointer_word_offsets(blobs):
    """Aligned word offsets holding a RAM pointer in at least one blob."""
    if not blobs:
        return []
    length = min(len(b) for b in blobs.values())
    out = []
    for off in range(0, length - (length % WORD_SIZE), WORD_SIZE):
        for b in blobs.values():
            if is_ram_ptr(struct.unpack_from("<I", b, off)[0]):
                out.append(off)
                break
    return out


def diff_structure(blobs, excluded=None):
    """Diff a {state: bytes} mapping. Pure; no I/O.

    Returns a dict with `length`, `length_note`, `pointer_words`,
    `differing_offsets`, `excluded`, `identical_after_masking`.
    """
    excluded = dict(excluded or {})
    result = {
        "states": sorted(blobs),
        "length": 0,
        "length_note": {k: len(v) for k, v in sorted(blobs.items())},
        "pointer_words": [],
        "differing_offsets": [],
        "compared_bytes": 0,
        "nonzero_compared_bytes": 0,
        "excluded": [{"offset": o, "reason": excluded[o]}
                     for o in sorted(excluded)],
        "identical_after_masking": True,
    }
    if not blobs:
        return result
    length = min(len(b) for b in blobs.values())
    result["length"] = length

    ptr_offsets = pointer_word_offsets(blobs)
    ptr_bytes = set()
    for off in ptr_offsets:
        values = {s: struct.unpack_from("<I", b, off)[0]
                  for s, b in sorted(blobs.items())}
        same = len(set(values.values())) == 1
        result["pointer_words"].append({
            "offset": off,
            "values": values,
            "values_hex": {s: hexw(v) for s, v in values.items()},
            "same_target": same,
        })
        ptr_bytes.update(range(off, off + WORD_SIZE))

    compared = 0
    nonzero = 0
    for off in range(length):
        if off in ptr_bytes or off in excluded:
            continue
        compared += 1
        values = {s: b[off] for s, b in sorted(blobs.items())}
        if any(values.values()):
            nonzero += 1
        if len(set(values.values())) > 1:
            result["differing_offsets"].append({"offset": off,
                                                "values": values})
    result["compared_bytes"] = compared
    result["nonzero_compared_bytes"] = nonzero
    result["identical_after_masking"] = not result["differing_offsets"]
    return result


def collect_blobs(captures, structure):
    """{state: bytes} for one structure, over the captures that spawned."""
    out = {}
    for slot, cap in sorted(captures.items()):
        if not cap.get("spawned"):
            continue
        if structure == "node0":
            nodes = cap.get("nodes") or []
            if not nodes or not nodes[0].get("bytes"):
                continue
            out[slot] = bytes.fromhex(nodes[0]["bytes"])
        elif structure == "entry":
            for n in cap.get("nodes") or []:
                if n.get("entry_bytes"):
                    out[slot] = bytes.fromhex(n["entry_bytes"])
                    break
        else:
            blob = (cap.get(structure) or {}).get("bytes")
            if blob:
                out[slot] = bytes.fromhex(blob)
    return out


def check_node_0x26_vs_id(captures):
    """Does the first node's `+0x26` byte equal `id - 0x100` everywhere?"""
    rows, exceptions = [], []
    for slot, cap in sorted(captures.items()):
        nodes = cap.get("nodes") or []
        if not cap.get("spawned") or not nodes:
            continue
        n = nodes[0]
        if not n.get("bytes") or n.get("id") is None:
            continue
        byte26 = bytes.fromhex(n["bytes"])[0x26]
        expected = n["id"] - 0x100
        row = {"slot": slot, "id": n["id"], "node_0x26": byte26,
               "expected": expected, "match": byte26 == expected}
        rows.append(row)
        if not row["match"]:
            exceptions.append(row)
    return {"rows": rows, "exceptions": exceptions,
            "holds": bool(rows) and not exceptions}


def check_pos_velocity_words(captures):
    """Do the position element's s16 pair at `+0x24`/`+0x26` equal the
    measured one-frame dx/dy?"""
    rows, exceptions = [], []
    for slot, cap in sorted(captures.items()):
        pos = (cap.get("position_element") or {}).get("bytes")
        samples = (cap.get("velocity") or {}).get("samples") or []
        if not cap.get("spawned") or not pos or not samples:
            continue
        b = bytes.fromhex(pos)
        w24 = struct.unpack_from("<h", b, 0x24)[0]
        w26 = struct.unpack_from("<h", b, 0x26)[0]
        row = {"slot": slot, "word_0x24": w24, "word_0x26": w26,
               "dx": samples[0]["dx"], "dy": samples[0]["dy"]}
        row["match"] = (w24 == row["dx"] and w26 == row["dy"])
        rows.append(row)
        if not row["match"]:
            exceptions.append(row)
    return {"rows": rows, "exceptions": exceptions,
            "holds": bool(rows) and not exceptions}


def summary_row(slot, cap):
    """One per-state summary row's fields."""
    if not cap.get("spawned"):
        return {"slot": slot, "spawned": False}
    el = cap.get("element", {})
    rec = cap.get("record", {})
    nodes = cap.get("nodes") or []
    entry_node = next((n for n in nodes if n.get("entry_bytes")), None)
    vel = (cap.get("velocity") or {}).get("samples") or []
    return {
        "slot": slot,
        "spawned": True,
        "run_kind": cap["meta"].get("run_kind"),
        "frames_stepped": cap["meta"].get("frames_stepped_since_unpause"),
        "kind": el.get("kind"),
        "record_idx": rec.get("idx"),
        "id": entry_node.get("id") if entry_node else None,
        "id_kind": entry_node.get("id_kind") if entry_node else None,
        "entry_0x08": hexw(entry_node["entry_0x08"])
        if entry_node and entry_node.get("entry_0x08") is not None else None,
        "entry_bytes": entry_node.get("entry_bytes") if entry_node else None,
        "node_count": len(nodes),
        "node_0x18": [hexw(n.get("field_0x18")) for n in nodes],
        "samples": vel,
        "u16_0x18": el.get("u16_0x18"),
        "s32_0x18": el.get("s32_0x18"),
        "pos_x": (cap.get("position_element") or {}).get("x_0x0C"),
        "pos_y": (cap.get("position_element") or {}).get("y_0x10"),
    }


def render_diff_md(captures, diffs, rows):
    L = ["# Ichigo Y variants: backend byte diff", "",
         "Generated by `scripts/emu/ichigo_y_diff.py` from the "
         "`*.capture.json` files in this directory. Offsets only; no "
         "gameplay names.", ""]

    spawned = [r["slot"] for r in rows if r["spawned"]]
    missing = [r["slot"] for r in rows if not r["spawned"]]
    L.append("Captures diffed (spawned): %s"
             % (", ".join("`%s`" % s for s in spawned) or "none"))
    if missing:
        L.append("")
        L.append("Captures excluded (nothing spawned): %s"
                 % ", ".join("`%s`" % s for s in missing))
    L.append("")

    L.append("## (b) Per-state summary")
    L.append("")
    L.append("| state | run | frames stepped | `+0x1A` kind | record idx | "
             "id | entry `+0x08` | entry bytes | nodes | node `+0x18` | "
             "sample 0 dx,dy | sample 1 dx,dy | `+0x18` u16 | `+0x18` s32 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if not r["spawned"]:
            L.append("| `%s` | - | - | - | - | - | - | - | - | - | - | - | - "
                     "| - |" % r["slot"])
            continue
        s = r["samples"]

        def samp(i):
            return ("%d,%d" % (s[i]["dx"], s[i]["dy"])) if len(s) > i else "-"

        L.append("| `%s` | %s | %s | %s | %s | %s (%s) | %s | `%s` | %d | %s "
                 "| %s | %s | %s | %s |" % (
                     r["slot"], r["run_kind"], r["frames_stepped"], r["kind"],
                     r["record_idx"], r["id"], r["id_kind"], r["entry_0x08"],
                     r["entry_bytes"], r["node_count"],
                     ", ".join(x for x in r["node_0x18"] if x) or "-",
                     samp(0), samp(1), r["u16_0x18"], r["s32_0x18"]))
    L.append("")

    L.append("## (a) Per-structure byte diff")
    L.append("")
    for name in STRUCTURES:
        dd = diffs[name]
        L.append("### %s" % STRUCTURE_TITLES[name])
        L.append("")
        if not dd["states"]:
            L.append("No capture supplied this structure.")
            L.append("")
            continue
        L.append("States: %s. Common length compared: 0x%X bytes (per-state "
                 "lengths %s)." % (", ".join("`%s`" % s for s in dd["states"]),
                                   dd["length"],
                                   ", ".join("`%s` 0x%X" % (k, v) for k, v
                                             in dd["length_note"].items())))
        L.append("")
        L.append("After removing pointer words and excluded offsets, %d "
                 "bytes are actually compared, and %d of those are nonzero "
                 "in at least one capture. The rest are zero in every "
                 "capture, so they carry no information either way."
                 % (dd["compared_bytes"], dd["nonzero_compared_bytes"]))
        L.append("")

        if dd["excluded"]:
            L.append("Excluded offsets (not diffed, listed with reason):")
            L.append("")
            L.append("| offset | reason |")
            L.append("|---|---|")
            for e in dd["excluded"]:
                L.append("| `+0x%02X` | %s |" % (e["offset"], e["reason"]))
            L.append("")

        L.append("Pointer words (value in `0x02000000..0x023FFFFF` in at "
                 "least one capture):")
        L.append("")
        if dd["pointer_words"]:
            L.append("| offset | same target? | " +
                     " | ".join("`%s`" % s for s in dd["states"]) + " |")
            L.append("|---|---|" + "---|" * len(dd["states"]))
            for p in dd["pointer_words"]:
                L.append("| `+0x%02X` | %s | %s |" % (
                    p["offset"], "same" if p["same_target"] else "different",
                    " | ".join(p["values_hex"][s] for s in dd["states"])))
        else:
            L.append("None.")
        L.append("")

        L.append("Differing byte offsets (pointer words and excluded offsets "
                 "removed):")
        L.append("")
        if dd["differing_offsets"]:
            L.append("| offset | " +
                     " | ".join("`%s`" % s for s in dd["states"]) + " |")
            L.append("|---|" + "---|" * len(dd["states"]))
            for o in dd["differing_offsets"]:
                L.append("| `+0x%02X` | %s |" % (
                    o["offset"],
                    " | ".join("0x%02X" % o["values"][s]
                               for s in dd["states"])))
        else:
            L.append("None.")
        L.append("")

    L.append("## (d) Two derived relations, checked against the captures")
    L.append("")
    n26 = check_node_0x26_vs_id(captures)
    L.append("The first node's `+0x26` byte against `id - 0x100`: **%s** "
             "across %d captures." % ("holds" if n26["holds"] else
                                      "does NOT hold", len(n26["rows"])))
    L.append("")
    L.append("| state | id | node `+0x26` | expected | match |")
    L.append("|---|---|---|---|---|")
    for r in n26["rows"]:
        L.append("| `%s` | %s | 0x%02X | 0x%02X | %s |"
                 % (r["slot"], r["id"], r["node_0x26"], r["expected"],
                    r["match"]))
    L.append("")
    pv = check_pos_velocity_words(captures)
    L.append("The position element's s16 pair at `+0x24`/`+0x26` against the "
             "measured one-frame dx/dy: **%s** across %d captures."
             % ("holds" if pv["holds"] else "does NOT hold", len(pv["rows"])))
    L.append("")
    L.append("| state | `+0x24` | `+0x26` | measured dx | measured dy | "
             "match |")
    L.append("|---|---|---|---|---|---|")
    for r in pv["rows"]:
        L.append("| `%s` | %d | %d | %d | %d | %s |"
                 % (r["slot"], r["word_0x24"], r["word_0x26"], r["dx"],
                    r["dy"], r["match"]))
    L.append("")

    L.append("## (c) Verdict")
    L.append("")
    for name in STRUCTURES:
        dd = diffs[name]
        if not dd["states"]:
            L.append("- **%s**: not captured." % name)
            continue
        ptr_diff = [p["offset"] for p in dd["pointer_words"]
                    if not p["same_target"]]
        ptr_same = [p["offset"] for p in dd["pointer_words"]
                    if p["same_target"]]
        if dd["identical_after_masking"]:
            L.append("- **%s**: byte-identical across the spawned captures "
                     "after masking pointer words and the excluded offsets "
                     "(%d bytes compared, %d of them nonzero somewhere). "
                     "Pointer words pointing at the same target: %s. "
                     "Pointer words with different targets: %s."
                     % (name, dd["compared_bytes"],
                        dd["nonzero_compared_bytes"],
                        ", ".join("`+0x%02X`" % o for o in ptr_same) or "none",
                        ", ".join("`+0x%02X`" % o for o in ptr_diff) or "none"))
        else:
            L.append("- **%s**: NOT byte-identical (%d bytes compared, %d of "
                     "them nonzero somewhere). Differing offsets: %s. "
                     "Pointer words with different targets: %s."
                     % (name, dd["compared_bytes"],
                        dd["nonzero_compared_bytes"],
                        ", ".join("`+0x%02X`" % o["offset"]
                                  for o in dd["differing_offsets"]),
                        ", ".join("`+0x%02X`" % o for o in ptr_diff) or "none"))
    L.append("")
    return "\n".join(L)


def load_captures(paths):
    caps = {}
    for p in paths:
        with open(p) as f:
            cap = json.load(f)
        caps[cap["meta"]["slot"]] = cap
    return caps


def build_parser():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dir", required=True,
                   help="directory holding the *.capture.json files; DIFF.md "
                        "is written here")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    paths = sorted(os.path.join(args.dir, f) for f in os.listdir(args.dir)
                   if f.endswith(".capture.json"))
    if not paths:
        raise SystemExit("no *.capture.json files in %s" % args.dir)
    caps = load_captures(paths)
    diffs = {name: diff_structure(collect_blobs(caps, name),
                                  excluded=EXCLUDED.get(name))
             for name in STRUCTURES}
    rows = [summary_row(slot, cap) for slot, cap in sorted(caps.items())]
    out = os.path.join(args.dir, "DIFF.md")
    with open(out, "w") as f:
        f.write(render_diff_md(caps, diffs, rows))
    print(json.dumps({"captures": len(caps),
                      "spawned": sum(1 for r in rows if r["spawned"]),
                      "diff": out}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
