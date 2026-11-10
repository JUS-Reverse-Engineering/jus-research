#!/usr/bin/env python3
"""Roster feature census: every NoteTrack, effect-node, KB-record and shot-row feature the
committed decoders see, as a table the kit exporter and its coverage test read.
No emulator. Output: docs/rebuild/feature-census.json.

Why: `scripts/kit/export_kit.py` is claim-driven and never walked the static anim closure of a
move, so features it does not model were dropped without a trace. This census names every feature key present anywhere in
the roster. `feature_status.FEATURE_STATUS` (scripts/kit/) must classify each key, and
`scripts/tests/test_export_coverage.py` fails on a key it does not know.

Feature keys (one string per feature):
  op0.subN[.variant]            NoteTrack op 0 (branch/wait) subs; variants split the decoded forms
  op1.subN, op2.subN, op4.subN  NoteTrack ops 1, 2, 4
  op3.argN, op3.subN            op 3 sub 0 by arg; other op 3 subs
  gn.GNxx / node.undecoded.GNxx effect nodes decoded (spawns) / left raw
  rec.mask.bitN, rec.type.N, rec.kind.N, rec.<field>.nonzero     20-byte KB record fields
  shot.kind.0xNN, shot.flag.0xN, shot.b1/b28/b29/b30/b31.nonzero, shot.bytes16_27.nonzero
                                chr/shot/<prefix>.bin 32-byte rows
  error.*                       a loader failed (the test refuses these)

Table shape (per character): `anims` keyed "<member>#0x<anim>" (member = the chr/<member>.aar
file stem: the base prefix or `<prefix>_<koma>`) with `keys` {key: [frames]}, `spawns`
[[frame, shot row]] (op 3 arg 2) and `recs` (collision ids >= 0x100 that anim's boxes name);
`records` {rec: [keys]}; `shots` {row: {kind, art, flags, b28, b29, keys}}.

Usage:
    python3 scripts/analysis/feature_census.py build   # write the .json
    python3 scripts/analysis/feature_census.py check   # exit 0 = the committed file is fresh
    python3 scripts/analysis/feature_census.py keys    # print every key with its counts
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "kit"))

import anim_events as E  # noqa: E402
import cancel_table as C  # noqa: E402
import knockback_table as K  # noqa: E402
import mash_table as M  # noqa: E402
import move_records as mr  # noqa: E402
import ua_table as U  # noqa: E402

REPO = M.REPO
OUT = REPO / "docs" / "rebuild" / "feature-census.json"
VERSION = 1
ROSTER = REPO / "docs/research/feel-captures/2026-10-18-e0-roster/roster_reconciled.json"
SHOT_ROW_BYTES = 32
RECORD_FIELDS = ("byte2", "statusRaw", "shakeScale", "byte6", "hitEffect", "onomatopoeia",
                 "byte16", "byte17", "byte18", "byte19")

_FACTS = None


def _facts():
    global _FACTS
    if _FACTS is None:
        _FACTS = M.code_facts()
    return _FACTS


def event_keys(ev: dict, markers: dict) -> list:
    """Feature keys of one NoteTrack event (op/sub, op 3 arg, op 0 field split)."""
    op, sub, raw = ev["op"], ev["sub"], ev["raw"]
    if op == 3 and sub == 0:
        return [f"op3.arg{raw[2]}"]
    if op == 0:
        keys = [f"op0.sub{sub}"]
        if sub in M.KINDS:
            d = M.decode_event(sub, raw[:M.RAW_LEN[sub]], _facts(), markers)
            if sub == 1:
                if d.get("kind") == "hold_release":
                    keys.append("op0.sub1.hold_release_disarm" if d.get("marker_default") == 0xFFFF
                                else "op0.sub1.hold_release" + ("" if d.get("marker_default_frame") is not None
                                                                 else ".null_marker"))
                else:
                    keys.append("op0.sub1.hold_tiers")
            if sub in (3, 4, 5):
                keys.append(f"op0.sub{sub}." + ("disarm" if d.get("disarm") else "arm"))
            if sub in (2, 0) and d.get("marker_frame") is None:
                keys.append(f"op0.sub{sub}.null_marker")
        return keys
    return [f"op{op}.sub{sub}"]


def shot_rows(prefix: str, *, native: bool = False) -> list:
    """chr/shot/<prefix>.bin as dicts: kind, flags, art, the successor bytes and the rest."""
    path = mr.ROOT / U.SHOT_DIR / f"{prefix}.bin"
    if not path.exists():
        return []
    raw = path.read_bytes()
    out = []
    for i in range(len(raw) // SHOT_ROW_BYTES):
        r = raw[i * SHOT_ROW_BYTES:(i + 1) * SHOT_ROW_BYTES]
        out.append({"row": i, "kind": r[0], "b1": r[1], "flags": struct.unpack_from("<I", r, 8)[0],
                    "art": struct.unpack_from("<I", r, 12)[0], "mid": r[16:28].hex(),
                    "b28": r[28], "b29": r[29], "b30": r[30], "b31": r[31]})
        if native:
            out[-1].update(speed=struct.unpack_from("<H", r, 4)[0],
                           lifetime=struct.unpack_from("<H", r, 6)[0] or 30,
                           end_effect=struct.unpack_from("<I", r, 20)[0])
    return out


def shot_keys(r: dict) -> list:
    keys = [f"shot.kind.0x{r['kind']:02x}"]
    if r["b1"]:
        keys.append("shot.b1.nonzero")
    keys += [f"shot.flag.0x{1 << b:x}" for b in range(32) if r["flags"] >> b & 1]
    keys += [f"shot.{f}.nonzero" for f in ("b28", "b29", "b30", "b31") if r[f]]
    if r["mid"] != "00" * 12:
        keys.append("shot.bytes16_27.nonzero")
    return keys


def record_keys(d: dict) -> list:
    keys = [f"rec.type.{d['type']}", f"rec.kind.{d['kind']}"]
    keys += [f"rec.mask.bit{b}" for b in range(32) if d["propMask"] >> b & 1]
    keys += [f"rec.{f}.nonzero" for f in RECORD_FIELDS if d[f]]
    return keys


def _member_name(member: str) -> str:
    return Path(member).name[:-4]


def prefix_census(prefix: str) -> dict:
    """The compact census of one prefix. Loader failures are listed under `errors`."""
    out = {"prefix": prefix, "anims": {}, "records": {}, "shots": {}, "errors": []}
    shots = shot_rows(prefix)
    for r in shots:
        out["shots"][str(r["row"])] = {"kind": r["kind"], "art": f"0x{r['art']:08x}", "flags": r["flags"],
                                       "b28": r["b28"], "b29": r["b29"], "keys": shot_keys(r)}
    try:
        scans = U.anim_scan(prefix)
    except BaseException as ex:      # the loaders raise SystemExit
        out["errors"].append(f"anim_scan: {ex}")
        scans = []
    gn = {}
    try:
        for member, almt in mr.motions(prefix):
            for aid, row in E.anim_events(almt).items():
                gn[(member, aid)] = row
    except BaseException as ex:
        out["errors"].append(f"anim_events: {ex}")
    uses = {}
    try:
        _f, refs = K.record_uses(prefix)
        for rec, places in refs.items():
            for place in places:      # "member 0xanim" or "member 0xanim NODE"
                uses.setdefault(" ".join(place.split()[:2]), []).append(rec)
    except BaseException as ex:
        out["errors"].append(f"record_uses: {ex}")
    for sc in scans:
        name = _member_name(sc["member"])
        loc = f"{name}#0x{sc['anim']:02x}"
        keys = defaultdict(list)
        spawns = []
        for ev in sc["events"]:
            for k in event_keys(ev, sc["markers"]):
                keys[k].append(ev["frame"])
            if ev["op"] == 3 and ev["sub"] == 0 and ev["raw"][2] == 2:
                spawns.append([ev["frame"], ev["raw"][4]])
        g = gn.get((sc["member"], sc["anim"]), {})
        for s in g.get("spawns", []):
            keys[f"gn.{s['node'][:4]}"].append(s["frame"])
        for n in g.get("undecoded_nodes", []):
            keys[f"node.undecoded.{n[:4]}"].append(-1)
        recs = sorted(set(uses.get(f"{name} 0x{sc['anim']:02x}", [])))
        out["anims"][loc] = {"frames": sc["frames"], "keys": {k: sorted(v) for k, v in sorted(keys.items())},
                             "spawns": sorted(spawns), "recs": recs}
    try:
        recs = mr.read_records(prefix)
    except BaseException as ex:
        recs = []
        out["errors"].append(f"records: {ex}")
    for i, raw in enumerate(recs):
        out["records"][str(i)] = record_keys(mr.decode_record(raw))
    return out


@contextlib.contextmanager
def _motions_parsed_once():
    """anim_scan, anim_events and record_uses each walk `move_records.motions(prefix)`; parse a prefix's
    members once (one-prefix cache, restored on exit). The decoders only read the parsed members."""
    original = mr.motions
    cached = functools.lru_cache(maxsize=1)(lambda prefix: list(original(prefix)))
    mr.motions = cached
    try:
        yield
    finally:
        mr.motions = original


def build() -> dict:
    with _motions_parsed_once():
        chars = [prefix_census(p) for p in C.battle_prefixes()]
    counts = defaultdict(lambda: [0, set()])
    for c in chars:
        for anim in c["anims"].values():
            for k, frames in anim["keys"].items():
                counts[k][0] += len(frames)
                counts[k][1].add(c["prefix"])
        for keys in c["records"].values():
            for k in keys:
                counts[k][0] += 1
                counts[k][1].add(c["prefix"])
        for row in c["shots"].values():
            for k in row["keys"]:
                counts[k][0] += 1
                counts[k][1].add(c["prefix"])
        for e in c["errors"]:
            k = "error." + e.split(":")[0]
            counts[k][0] += 1
            counts[k][1].add(c["prefix"])
    records_by_prefix = []
    roster_rows = json.loads(ROSTER.read_text(encoding="utf-8"))["rows"]
    from feature_status import FEATURE_STATUS
    # M0 importer deferrals are semantic buckets over the census vocabulary.
    # M0 deferrals in import_kit.py:143-154 name kit fields, not decoder families.
    # These exact keys are evidence only: hold tiers (mash_table.py:89), body flag
    # (feature_status.py op3.sub2 entry), no-damage record kind (move_records.py:585),
    # held summon shot (feature_status.py shot.kind.0x0d entry), and ability effects
    # (feature_status.py op3.arg7/23/32 entries). No other buckets have evidence in
    # this census: their inputs are outside its decoders or the similarly named keys
    # already map to implemented kit fields (import_kit.py:1194-1201, 1498-1502).
    m0_feature_keys = {
        "charge": {"op0.sub1.hold_tiers"},
        "body": {"op3.sub2"},
        "element": set(),
        "summon": {"shot.kind.0x0d"},
        "support": set(),
        "push": {"rec.kind.0"},
        "forms": set(),
        "abilities": {"op3.arg7", "op3.arg23", "op3.arg32"},
        "cancel_carry": set(),
        "mash": set(),
    }
    # Mechanism ids are stable feature-status demands: each unsupported/partial key
    # is one independently exercised M-key until a concrete mechanism owns it.
    def feature_map(c):
        out = defaultdict(int)
        for anim in c["anims"].values():
            for key, frames in anim["keys"].items(): out[key] += len(frames)
        for keys in c["records"].values():
            for key in keys: out[key] += 1
        for shot in c["shots"].values():
            for key in shot["keys"]: out[key] += 1
        for error in c["errors"]: out["error." + error.split(":")[0]] += 1
        return dict(sorted(out.items()))
    for c in chars:
        features = feature_map(c)
        candidates = sorted(({"chr_b": item["chr_b"], "name": item["name"]}
                            for item in roster_rows if c["prefix"] in item.get("candidates", [])),
                           key=lambda item: (item["chr_b"], item["name"]))
        doc_items = sorted((item for item in roster_rows if item.get("doc_prefix") == c["prefix"]),
                           key=lambda item: item["chr_b"])
        pinned = next((item for item in roster_rows
                       if item.get("join_status") == "pinned"
                       and c["prefix"] in (item.get("prefix"), item.get("measured_prefix"))), None)
        identity = pinned or (doc_items[0] if doc_items else {})
        status = identity.get("join_status", "unobserved")
        # Preserve a single identity only for a pinned join. Ambiguous candidate
        # memberships and document identity are reported independently, never guessed.
        roster_identity = {"chr_b": identity.get("chr_b") if pinned else None,
                           "name": identity.get("name") if pinned else None,
                           "pin_status": status,
                           "candidates": candidates,
                           "doc_prefix": [{"chr_b": item["chr_b"], "name": item["name"]}
                                          for item in doc_items]}
        m0 = sorted(name for name, keys in m0_feature_keys.items()
                    if any(key in features for key in keys))
        no_census_signal = sorted(name for name, keys in m0_feature_keys.items() if not keys)
        mechanisms = {key: count for key, count in features.items()
                      if key in FEATURE_STATUS and FEATURE_STATUS[key].status in ("unsupported", "partial")}
        cost = sum(count for key, count in mechanisms.items()
                   if FEATURE_STATUS[key].status == "unsupported")
        records_by_prefix.append({"prefix": c["prefix"], "roster": roster_identity, "features": features,
                                  "m0_keys": m0, "m0_no_census_signal": no_census_signal,
                                  "mechanism_demand": mechanisms, "cost": cost})
    mechanism_records = defaultdict(set)
    m0_records = defaultdict(set)
    for row in records_by_prefix:
        for key, count in row["mechanism_demand"].items():
            if count: mechanism_records[key].add(row["prefix"])
        for key in row["m0_keys"]: m0_records[key].add(row["prefix"])
    return {"version": VERSION,
            "keys": {k: {"count": v[0], "prefixes": len(v[1])} for k, v in sorted(counts.items())},
            "characters": chars,
            "records_by_prefix": records_by_prefix,
            "cross_cast": {"records_per_mechanism": {k: len(v) for k, v in sorted(mechanism_records.items())},
                           "m0_keys_by_demand": [{"key": k, "records": len(v)} for k, v in
                                                  sorted(m0_records.items(), key=lambda kv: (-len(kv[1]), kv[0]))]}}


def dump(table: dict) -> str:
    """One line per anim/record/shot row so a diff stays readable."""
    lines = ['{"version": %d,' % table["version"],
             '"keys": ' + json.dumps(table["keys"], sort_keys=True, separators=(",", ":")) + ',',
             '"characters": [']
    for n, c in enumerate(table["characters"]):
        lines.append('{"prefix": %s,' % json.dumps(c["prefix"]))
        lines.append('"errors": %s,' % json.dumps(c["errors"]))
        for part in ("anims", "records", "shots"):
            lines.append('"%s": {' % part)
            items = list(c[part].items())
            for j, (k, v) in enumerate(items):
                lines.append("%s: %s%s" % (json.dumps(k), json.dumps(v, sort_keys=True, separators=(",", ":")),
                                           "," if j + 1 < len(items) else ""))
            lines.append("}%s" % ("," if part != "shots" else ""))
        lines.append("}%s" % ("," if n + 1 < len(table["characters"]) else ""))
    lines.append("]}")
    # Preserve the established aggregate/character serialization byte-for-byte and
    # append the additive sections after the characters array.
    body = "\n".join(lines)
    body = body[:-1] + ",\n" + json.dumps({"records_by_prefix": table["records_by_prefix"],
                                                "cross_cast": table["cross_cast"]},
                                               sort_keys=True, separators=(",", ":"))[1:-1] + "}\n"
    return body


def load(path: Path = OUT) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=("build", "check", "keys"))
    a = ap.parse_args(argv)
    if a.cmd == "check" and not ROSTER.exists():
        print("check skipped: needs inputs that are not part of this repository (" + str(ROSTER.relative_to(REPO)) + ")")
        return 0
    table = build()
    if a.cmd == "build":
        OUT.write_text(dump(table), encoding="utf-8")
        print(f"wrote {OUT.relative_to(REPO)}")
        return 0
    if a.cmd == "keys":
        for k, v in table["keys"].items():
            print(f"{k:40s} {v['count']:6d}  prefixes {v['prefixes']:3d}")
        return 0
    fresh = OUT.exists() and OUT.read_text(encoding="utf-8") == dump(table)
    print("fresh" if fresh else "STALE: run build")
    return 0 if fresh else 1


if __name__ == "__main__":
    raise SystemExit(main())
