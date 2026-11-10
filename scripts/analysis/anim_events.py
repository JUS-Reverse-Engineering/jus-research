#!/usr/bin/env python3
"""Effect spawns (GN nodes) and NoteTrack events per animation, from the ALMT bytes.

Why (jus-wmqi.6.12): to know which effect each move spawns, on
which animation frame and where, and which sound it plays. Both live in the
character's `<prefix>.amt` (ChrArc.aar -> chr/<prefix>.aar), not in code.

Track layouts decoded here (all little-endian). The ALMT entry/node framing is
move_records.Almt's; this tool only reads the per-track bytes from their true
start, because Almt clips a node's last track at the next node's start.

  GenerateID (GN nodes), keyed: (u16 frame, u32 effect id) * n, then u16 0xFFFF.
      STATIC: native reader arm9 0x02016220 computes stride 6 from the
      descriptor's size4 callback 0x0204A788 and dispatches a nonzero id
      only at its key frame (0x020162C4..0x02016308). Effect GN's method is
      0x0206CA8C, which loads the effect at 0x0206CB88. Zero does nothing.
      GN02 uses the same tracks; its count block is located by cumulative
      ALMT v2 deltas, not an independent animation header (see recovery).
  2DPos, keyed: (u16 frame, s16 x, s16 y) * n, 0xFFFF. Const: (s16 x, s16 y).
  NoteTrack (SP01), keyed: (u16 frame, u16 rel) * n, 0xFFFF. Key k's record
      starts `rel` u16 words after key k's own frame field (word 2k). A record
      is u16 count, then count u16 offsets (words, from the record start), each
      to one event. An event starts with u8 sub, u8 op, s16 arg; some ops carry
      more words after that. `raw` holds the whole event: up to the next
      event, or for a record's last event up to the next record's start (16 bytes when
      none follows), so the op3 arg 2 shot row (ev[4]) is not clipped to the 4-byte head.
  Event dispatch (ov6): the per-frame loop at 0x021557C0 calls table
      0x0217200C[op](obj, event). op 4 is sound: 0x02156A18 calls table
      0x02171FF4[sub] from 0x02156A2C. sub 0 -> 0x021569CC plays
      (0x7A = SEQ_BATTLE, arg); sub 1 -> 0x021569E0 plays ([obj+0xA4], arg);
      sub 2 -> 0x021569FC plays ([obj+0xA6], arg). Other ops are listed raw.
  Branch events (op 0, sub table 0x02172084; docs/research/2026-10-15-taikoubou-6kx-branches.md):
      sub 5 (0x02155D3C) contact_wait: queue kind 6 (slot 2, table 0x021710A8)
          with Marker s8 ev[2]; -1 disarms. Kind 6's poll (0x021563B4) is true
          iff [[ctrl+0x7C]+0x10]+0x158 & 0xF, a per-frame contact word.
      sub 9 (0x02155DB8) counter_wait: queue kind 9, slot 2, signed Marker ev[2].
          Poll 0x021564E8 tests ColPrm+0x40 & 0x20000; -1 disarms. STATIC: p230
          (docs/research/findings/p230-kenshin-status-counter-sound.md).
          Decode contract (counter_waits(), pinned by test_anim_events.CounterWaitContractTest):
          one dict per occurrence, in track order,
              {kind: "counter_wait", frame, marker, marker_frame, disarm}
          frame = the NoteTrack key frame; marker = signed byte ev[2] (0xFF reads -1, never
          255); disarm = marker == -1; marker_frame = first frame of that Marker in the
          anim's Marker track, None for a disarm or an absent Marker (a native no-op:
          lookup 0x0201F93C returns 0 at 0x0201F9AC). Absent is not an error.
      sub 14 (0x02155E90) deck_count_branch: query 0x42 (fighter callback
          0x02157A44, case at 0x02157E68) is true iff the player slot's count
          s8 [[fighter+0x1B4]+0x5DF] >= threshold. Tested first with s8 ev[4]
          (true: kind-0 jump to Marker u8 ev[5]), then with s8 ev[2] (true:
          Marker u8 ev[3]); neither: no jump. `branches` on each row lists
          them with marker frames from the anim's Marker track.

Usage:
    python3 scripts/analysis/anim_events.py kakashi [--json] [--anim 0x1f]
    python3 scripts/analysis/anim_events.py na_b_04 --member na_b_04_e0.amt
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import anim_timing as at  # noqa: E402
import move_records as mr  # noqa: E402

SOUND_OP = 4
BRANCH_OP = 0
BRANCH_KINDS = {5: "contact_wait", 9: "counter_wait", 14: "deck_count_branch"}
LAST_EVENT_BYTES = 16  # last event of the final record has no next record to bound it
# bytes an op-0 event reads from its start, by sub (the raw column keeps exactly these); shared
# with mash_table.RAW_LEN. Subs not listed fall back to 4 bytes. Subs 11, 21 and 29 read 6: a
# marker, an alternate marker or counter, and a u16/second threshold (STATIC, ov6 handlers
# 0x02155DE0, 0x02155E08 and 0x02155F40; m14j3 report section 2 and the decoder defect note).
SUB_EVENT_LEN = {0: 8, 1: 18, 2: 4, 3: 4, 4: 4, 5: 4, 9: 4, 11: 6, 14: 6,
                 18: 8, 19: 4, 20: 4, 21: 6, 23: 12, 29: 6}
SOUND_SUBS = {0: "0x7A", 1: "obj+0xA4", 2: "obj+0xA6"}
ALIASES = {k: v["prefix"] for k, v in at.CHARS.items()}


def _u16(b, o):
    return struct.unpack_from("<H", b, o)[0]


def _s16(b, o):
    return struct.unpack_from("<h", b, o)[0]


# ------------------------------------------------------------------ tracks

def node_tracks(buf: bytes, a: int, hdr_end: int, props: list[str]) -> dict:
    """prop -> (kind, absolute start) for the entry/node that starts at `a`."""
    nc, nk = buf[a + hdr_end], buf[a + hdr_end + 1]
    idx = list(buf[a + hdr_end + 2:a + hdr_end + 2 + nc + nk])
    tp = a + hdr_end + 2 + nc + nk
    tp += tp & 1
    out = {}
    for j, pr in enumerate(idx):
        name = props[pr] if pr < len(props) else f"prop{pr}"
        out[name] = ("const" if j < nc else "key", a + hdr_end + _u16(buf, tp + 2 * j))
    return out


def cumulative_node_tracks(almt: mr.Almt, start: int, end: int) -> dict:
    """ALMT v2 count blocks, arm9 0x0201F1B8..208 and 0x0201F6BC..728.

    Used to recover nodes the legacy full_entry parser cannot locate. A node
    has no private animation header. Its nonzero delta advances a running
    base initialized to entry-0x20; zero omits a node without resetting it.
    """
    if almt.buf[almt.base + 4] != 2:
        raise ValueError("cumulative nodes require ALMT v2")
    base, blocks = start - 0x20, []
    for i, name in enumerate(almt.nodes):
        delta = _u16(almt.buf, start + 8 + 2 * i)
        base += delta
        if delta:
            blocks.append((name, base))
    out = {}
    for i, (name, base) in enumerate(blocks):
        stop = blocks[i + 1][1] if i + 1 < len(blocks) else end
        if not start <= base < stop <= end:
            raise ValueError("node boundary outside animation")
        tracks = node_tracks(almt.buf, base, 0, almt.props)
        if any(not base <= off < stop for _, off in tracks.values()):
            raise ValueError("track outside node")
        out[name] = (tracks, stop)
    return out


def decode_generate(buf: bytes, off: int, kind: str = "key") -> list[tuple[int, int]]:
    """GenerateID keys: [(frame, effect id)]."""
    if kind == "const":
        return [(0, struct.unpack_from("<I", buf, off)[0])]
    out = []
    while off + 2 <= len(buf):
        f = _u16(buf, off)
        if f == 0xFFFF:
            break
        out.append((f, struct.unpack_from("<I", buf, off + 2)[0]))
        off += 6
    return out


def decode_pos(buf: bytes, off: int, kind: str = "key") -> list[tuple[int, int, int]]:
    """2DPos keys: [(frame, x, y)]."""
    if kind == "const":
        return [(0, _s16(buf, off), _s16(buf, off + 2))]
    out = []
    while off + 2 <= len(buf):
        f = _u16(buf, off)
        if f == 0xFFFF:
            break
        out.append((f, _s16(buf, off + 2), _s16(buf, off + 4)))
        off += 6
    return out


def pos_at(keys, frame):
    cur = (0, 0)
    for f, x, y in keys:
        if f <= frame:
            cur = (x, y)
    return cur


def walk_notetrack(buf: bytes, off: int) -> list[dict]:
    """Container structure of one keyed NoteTrack, with every event's absolute offset.

    [{key, frame, record, count, events: [{index, offset, container_end, sub, op, arg}]}].
    `container_end` bounds the event by the next event (or, for the record's last event, the
    next record or LAST_EVENT_BYTES); it is NOT the native read span, which is per handler
    (`op0_read_len`, and scripts/kit/support_vm.py for the other ops). Bytes past the native
    read span, up to container_end, are record metadata and must never be executed.
    """
    keys = []
    k = 0
    while off + 4 * k + 2 <= len(buf):
        f = _u16(buf, off + 4 * k)
        if f == 0xFFFF:
            break
        keys.append((k, f, _u16(buf, off + 4 * k + 2)))
        k += 1
    rec_starts = sorted({off + 2 * (2 * k + rel) for k, _f, rel in keys})
    out = []
    for k, f, rel in keys:
        rec = off + 2 * (2 * k + rel)
        n = _u16(buf, rec)
        starts = [rec + 2 * _u16(buf, rec + 2 + 2 * i) for i in range(n)]
        evs = []
        for i, s in enumerate(starts):
            need = op0_read_len(buf[s]) if buf[s + 1] == BRANCH_OP else 4
            if i + 1 < n:
                end = starts[i + 1]
            elif buf[s + 1] == BRANCH_OP:
                end = s + need
            else:
                # last event: runs to the next record's start (events carry more words after
                # the 4-byte head, e.g. op3 arg2 ev[4] = shot row); else LAST_EVENT_BYTES
                nxt = [r for r in rec_starts if r > s]
                end = nxt[0] if nxt else min(s + LAST_EVENT_BYTES, len(buf))
            evs.append({"index": i, "offset": s, "container_end": end, "need": need,
                        "sub": buf[s], "op": buf[s + 1], "arg": _s16(buf, s + 2)})
        out.append({"key": k, "frame": f, "record": rec, "count": n, "events": evs})
    return out


def op0_read_len(sub: int) -> int:
    """Native read span of an op-0 event, in bytes (SUB_EVENT_LEN; unlisted subs read 4)."""
    return SUB_EVENT_LEN.get(sub, 4)


def decode_notetrack(buf: bytes, off: int) -> list[dict]:
    """[{frame, events: [{sub, op, arg, raw}]}] for one keyed NoteTrack."""
    out = []
    for key in walk_notetrack(buf, off):
        evs = []
        for e in key["events"]:
            s = e["offset"]
            ev = {"sub": e["sub"], "op": e["op"], "arg": e["arg"],
                  "raw": buf[s:max(e["container_end"], s + e["need"])].hex(" ")}
            br = decode_branch(e["sub"], buf, s) if e["op"] == BRANCH_OP else None
            if br is not None:
                ev["branch"] = br
            evs.append(ev)
        out.append({"frame": key["frame"], "events": evs})
    return out


def decode_markers(buf: bytes, off: int) -> dict[int, int]:
    """Keyed Marker track (u16 frame, u16 marker) * n, 0xFFFF: {marker: first frame}."""
    out, k = {}, 0
    while off + 4 * k + 4 <= len(buf):
        f = _u16(buf, off + 4 * k)
        if f == 0xFFFF:
            break
        out.setdefault(_u16(buf, off + 4 * k + 2), f)
        k += 1
    return out


def decode_branch(sub: int, buf: bytes, s: int) -> dict | None:
    """Fields of an op-0 sub 5 / 9 / 14 event at `s` (None for other subs)."""
    if sub in (5, 9):
        m = struct.unpack_from("<b", buf, s + 2)[0]
        row = {"kind": BRANCH_KINDS[sub], "marker": m, "disarm": m == -1}
        if sub == 9:
            row.update(queue_kind=9, poll="0x021564E8")
        return row
    if sub == 14:
        hi, lo = struct.unpack_from("<b", buf, s + 4)[0], struct.unpack_from("<b", buf, s + 2)[0]
        return {"kind": BRANCH_KINDS[14], "query": 0x42,
                "tiers": [{"min_count": hi, "marker": buf[s + 5]},
                          {"min_count": lo, "marker": buf[s + 3]}]}
    return None


def resolve_branch(branch: dict, markers: dict[int, int]) -> dict:
    """Copy of `branch` with the frame of each marker it names (None when absent)."""
    out = dict(branch)
    if "tiers" in out:
        out["tiers"] = [dict(t, frame=markers.get(t["marker"])) for t in out["tiers"]]
    else:
        out["frame"] = None if out["disarm"] else markers.get(out["marker"])
    return out


# ------------------------------------------------------------------ per character

def counter_waits(row: dict) -> list[dict]:
    """counter_wait contract rows for one anim_events() row (see the module docstring).

    `row["branches"]` is the resolved per-anim branch list; only counter_wait entries
    are kept, reshaped to {kind, frame, marker, marker_frame, disarm}.
    """
    return [{"kind": "counter_wait", "frame": b["frame_at"], "marker": b["marker"],
             "marker_frame": b["frame"], "disarm": b["disarm"]}
            for b in row["branches"] if b["kind"] == "counter_wait"]


def load_almt(prefix: str, member: str | None = None) -> mr.Almt:
    return mr.Almt(mr.maybe_dscp(at._member(prefix, member or f"{prefix}.amt")), 0)


def anim_events(almt: mr.Almt) -> dict[int, dict]:
    """anim id -> {frames, spawns, notes, sounds, undecoded_nodes}."""
    res = {}
    for idx, full in almt.full_animations():
        top = full["nodes"][0]
        if top["entry"] is None:
            continue
        aid, frames = top["entry"]["id"], top["entry"]["frames"]
        row = {"anim": aid, "frames": frames, "spawns": [], "notes": [], "sounds": [],
               "branches": [], "undecoded_nodes": []}
        markers = {}
        recovered = None
        recovery_failed = False
        for node in full["nodes"]:
            # Node framing rule (AEFIX, same rule as the support path): the
            # legacy full_entry start is kept only while its tracks validate,
            # meaning they equal the block the native cumulative walk gives that
            # label. A missing start, a start whose tracks differ (wrong
            # start) and swapped labels are all recovered with the walk. When
            # the walk itself is unavailable (v1 ALMT, boundary check fails)
            # the legacy node is kept only if full_entry marked it ok. A node
            # neither path can frame is listed in undecoded_nodes.
            if node is top:
                use_walk = False
            else:
                if recovered is None and not recovery_failed:
                    try:
                        end = max(n["end"] for n in full["nodes"] if n["end"] is not None)
                        recovered = cumulative_node_tracks(almt, top["start"], end)
                    except (ValueError, KeyError, IndexError, struct.error):
                        recovery_failed = True
                walked = (recovered or {}).get(node["name"])
                if recovered is None:
                    use_walk = False
                    if node["start"] is None or not node["ok"]:
                        row["undecoded_nodes"].append(node["name"])
                        continue
                elif walked is None:
                    use_walk = False
                    if node["start"] is None or not node["ok"]:
                        row["undecoded_nodes"].append(node["name"])
                        continue
                else:
                    try:
                        legacy = (node_tracks(almt.buf, node["start"], almt.hdr_end, almt.props)
                                  if node["start"] is not None else None)
                    except (IndexError, struct.error):
                        legacy = None
                    use_walk = legacy != walked[0]
            if use_walk:
                tr, stop = recovered[node["name"]]
            else:
                tr, stop = None, len(almt.buf)
            # A node whose tracks run past the buffer fails alone (full_entry
            # already marks such a node ok: False). The file's other nodes and
            # animations still decode; the failure is listed in node_errors.
            try:
                is_recovered = tr is not None
                tr = tr if is_recovered else node_tracks(
                    almt.buf, node["start"], almt.hdr_end, almt.props)
                buf = almt.buf[:stop]
                spawns, notes = [], None
                if "GenerateID" in tr:
                    gk, go = tr["GenerateID"]
                    pos = decode_pos(buf, tr["2DPos"][1], tr["2DPos"][0]) if "2DPos" in tr else []
                    for f, eid in decode_generate(buf, go, gk):
                        if eid:
                            x, y = pos_at(pos, f)
                            spawns.append({"node": node["name"], "frame": f,
                                           "effect": eid, "x": x, "y": y})
                            if is_recovered:
                                for prop, field in (("ParentLink", "parent_link"),
                                                    ("EffectFlags", "effect_flags"),
                                                    ("DrawPrio", "draw_prio")):
                                    if prop in tr:
                                        kind, off = tr[prop]
                                        keys = (decode_generate(buf, off, kind) if prop == "DrawPrio"
                                                else at.decode_track(prop, kind, buf[off:]))
                                        held = [v for t, v in keys if t <= f]
                                        if held:
                                            spawns[-1][field] = (int(bool(held[-1] & 0xFF))
                                                                if prop == "ParentLink" else held[-1])
                if node["name"] == "SP01" and "NoteTrack" in tr and tr["NoteTrack"][0] == "key":
                    notes = decode_notetrack(almt.buf, tr["NoteTrack"][1])
                    if "Marker" in tr and tr["Marker"][0] == "key":
                        markers = decode_markers(almt.buf, tr["Marker"][1])
            except (struct.error, IndexError) as ex:
                kind = "struct.error" if isinstance(ex, struct.error) else type(ex).__name__
                row["undecoded_nodes"].append(node["name"])
                row.setdefault("node_errors", []).append({"node": node["name"], "error": f"{kind}: {ex}"})
                continue
            row["spawns"].extend(spawns)
            if notes is not None:
                row["notes"] = notes
        row["markers"] = markers
        for key in row["notes"]:
            for ev in key["events"]:
                if "branch" in ev:
                    row["branches"].append(dict(resolve_branch(ev["branch"], markers), frame_at=key["frame"]))
                if ev["op"] == SOUND_OP:
                    row["sounds"].append({"frame": key["frame"], "sub": ev["sub"],
                                          "category": SOUND_SUBS.get(ev["sub"], f"sub{ev['sub']}"),
                                          "id": ev["arg"]})
        if aid in res:
            raise SystemExit(f"animation id 0x{aid:02x} appears twice")
        res[aid] = row
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("who", help="kakashi, yusuke, or a chr prefix such as na_b_04")
    ap.add_argument("--member", help="ALMT member name (default <prefix>.amt)")
    ap.add_argument("--anim", help="only this animation id")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    prefix = ALIASES.get(a.who, a.who)
    ev = anim_events(load_almt(prefix, a.member))
    if a.anim:
        ev = {k: v for k, v in ev.items() if k == int(a.anim, 0)}
    if a.json:
        print(json.dumps({f"0x{k:02x}": v for k, v in ev.items()}, indent=1))
        return 0
    for aid, row in ev.items():
        if not (row["spawns"] or row["notes"]):
            continue
        print(f"anim 0x{aid:02x} frames {row['frames']}")
        for marker, frame in sorted(row["markers"].items()):
            print(f"  marker {marker}: f{frame}")
        for s in row["spawns"]:
            print(f"  spawn {s['node']} f{s['frame']:<3d} 0x{s['effect']:06x} at ({s['x']},{s['y']})")
        for k in row["notes"]:
            evs = " | ".join(f"op{e['op']} sub{e['sub']} arg {e['arg']:#x}" for e in k["events"])
            print(f"  note  f{k['frame']:<3d} {evs}")
        for b in row["branches"]:
            if "tiers" in b:
                tiers = ", ".join(f"count >= {t['min_count']} -> marker {t['marker']} (f{t['frame']})"
                                  for t in b["tiers"])
                print(f"  branch f{b['frame_at']:<3d} {b['kind']}: {tiers}, else no jump")
            else:
                trigger = "counter latch" if b["kind"] == "counter_wait" else "contact"
                what = ("disarm" if b["disarm"] else
                        f"on {trigger} -> marker {b['marker']} (f{b['frame']})")
                print(f"  branch f{b['frame_at']:<3d} {b['kind']}: {what}")
        if row["undecoded_nodes"]:
            print(f"  undecoded nodes: {row['undecoded_nodes']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
