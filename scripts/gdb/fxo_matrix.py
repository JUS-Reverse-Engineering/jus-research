#!/usr/bin/env python3
"""Train presentation matrix (j6mat): one compact receipt per recorded run, repeat agreement, ticket coverage and claim resolution.

A run is one 512-frame native capture of a j6fix fixture cell (docs/research/feel-captures/2026-10-25-j6fix-fixtures/recipes.json)
with the native call hooks and the lifecycle FXO probe (fxo_tracker.generate(..., lifecycle=True)). receipt() reduces its bounded
probe window and native calls to the facts the j6-j9 ticket asks for, each read from a recorded row:

  presentations  every tracked effect: id, object, allocation generation, birth tick and phase, rendered ticks and per-draw
                 cell/flip/scale/priority, and three separate ends: the dump-observed (`sampled`) end, the instruction-time
                 `native` end (a pool/heap free with its caller, or the next successful initialization of the object), and the
                 successor initialization that reuses a freed block before the same dump (`native.successor`). An instruction
                 time (`instruction_tick`, `init_instruction_tick`: the tick of the recorded LMF/LMG/LAE row) and the dump tick
                 that first shows it (`dump_tick`) are separate fields; v2 split them (v1 exported the dump tick as `tick`).
  joins          the shot-art initializer context (LSE at 0x02023894 with lr 0x0216C6D4) and the render-object link store (LSL):
                 projectile element, spawn info, render object, output slot, animation, and the track it presents.
  sound          NoteTrack owner rows (LNT) with the owner's +0xA4/+0xA6, animation and frame, and the play/result rows (LSP/LSH).
  requests       every sound play request (LSP) with its result (LSH): archive, index, success, the ARM9 player object and the
                 ARM7 player id it carries (byte +0x3C of the player object, word 15 of the LSH dump), and the NoteTrack row that
                 dispatched it, if one did.
  voices         the ARM7 hardware voices (snd_arm7.voices) of each request's player id, allocated from the request tick until the
                 next request of that player id: channel, track, start registers and the separately kept ends.
  body           the fighter body animation initializations: Train-bank initializations that start no tracked presentation.

Ticks are reported as capture ticks (gfc - first_gfc of the native capture), so repeats compare directly. A receipt is never built
from a reduction that refuses: refusals are carried verbatim and `ok` is False.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SCHEMA = "train-matrix-receipt/v2"
SHOT_CALL_LR = 0x0216C6D4
TRAIN_BANK = 0x742
SHARED_BANKS = list(range(0x2100, 0x2500))
# the tracked banks of the matrix probe (fxo_tracker.generate filter: Train, the shared range and the common banks the round-2 up+X
# capture dispatched); a reduction must declare exactly the probe's banks
MATRIX_BANKS = [TRAIN_BANK] + SHARED_BANKS + [0x5000, 0x5010, 0x5F00]


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _runs(seq):
    """Run-length list [[value, count], ...] of a sequence."""
    out = []
    for v in seq:
        if out and out[-1][0] == v:
            out[-1][1] += 1
        else:
            out.append([v, 1])
    return out


def _rel(g, t0):
    return None if g is None else g - t0


def presentation(t, t0):
    """One reduced track as capture-tick facts. The three ends stay separate: `sampled` is what the dump observed (a death or a
    reinit of the pointer), `native` is the instruction-time free or replacing initialization, and `successor` is the recorded
    initialization that reused a freed block before the same dump. Each end carries the tick of its recorded instruction row
    (`instruction_tick`: the LMF pool-free entry, the LMG heap free or the replacing initializer's return; `init_instruction_tick`:
    the successor's LAE initializer entry) apart from the dump tick that first shows it (`dump_tick`)."""
    drawn = [s["drawn"] for s in t["samples"] if s.get("drawn")]
    ne = t.get("end_native")
    native = None
    if ne is not None:
        su = ne.get("successor")
        native = {"kind": ne["kind"], "instruction_tick": _rel(ne["gfc"], t0), "dump_tick": _rel(ne["tick"], t0),
                  "free_kind": ne.get("free_kind"), "caller": ne.get("caller"), "by_anim": ne.get("by_anim"),
                  "successor": None if su is None else {"anim": su["anim"], "init_instruction_tick": _rel(su["gfc"], t0),
                                                        "dump_tick": _rel(su["tick"], t0)}}
    end = t.get("end")
    alloc = t.get("alloc")
    return {"n": t["n"], "id": t["id"], "obj": t["obj"], "gen": t.get("gen"), "alloc_gen": None if alloc is None else alloc["gen"],
            "alloc_block": None if alloc is None else alloc["block"], "birth": _rel(t["birth_gfc"], t0),
            "init_tick": _rel((t.get("init") or {}).get("gfc"), t0),
            "birth_phase": (t.get("birth") or {}).get("phase"), "init_ret_pc": (t.get("init") or {}).get("ret_pc"),
            "drawn": [_rel((t.get("rendered") or {}).get("first_gfc"), t0), _rel((t.get("rendered") or {}).get("last_gfc"), t0)],
            "draws": len(drawn), "cells": _runs([d["cell"] for d in drawn]), "flips": sorted({d["flip"] for d in drawn}),
            "attrs": sorted({d["attr"] for d in drawn if d.get("attr") is not None}),
            "priority": sorted({json.dumps(d.get("priority"), sort_keys=True) for d in drawn if d.get("priority") is not None}),
            "scales": _runs([tuple(d["scale_q12"]) for d in drawn if d.get("scale_q12")]),
            "spaces": dict(Counter(d["space"] for d in drawn)),
            "path": [[s["gfc"] - t0] + list(s["drawn"]["screen_q12"]) for s in t["samples"]
                     if s.get("drawn") and s["drawn"].get("screen_q12")],
            "sampled": None if end is None else {"kind": end["kind"], "dump_tick": _rel(end["gfc"], t0), "age": end.get("age")},
            "native": native}


def mirror(tracks):
    """The x-mirror byte node+0x48 (LDX `hflip`) of every presentation's drawn samples: {"<id>#<n>": sorted values}. It lives outside
    `facts` so a run recorded with it compares by digest with matrix runs recorded before it; it is None when no draw of the run
    carries the byte. A presentation with some draws missing it lists None among its values."""
    out = {"%s#%d" % (t["id_hex"], t["n"]): sorted({s["drawn"].get("hflip") for s in t["samples"] if s.get("drawn")},
                                                   key=lambda v: -1 if v is None else v) for t in tracks}
    return out if any(v != [None] and v for v in out.values()) else None


def joins(rows, tracks, t0):
    """Shot-art joins: each LSE (initializer entry from the shot-art builder) with the LSL link store before it and the track that
    presents its object and animation."""
    out = []
    for r in rows:
        if r.tag != "LSE":
            continue
        link = [x for x in rows if x.tag == "LSL" and x.line < r.line]
        link = link[-1] if link else None
        tr = [t["n"] for t in tracks if t["obj"] == r.kv.get("obj") and t["id"] == r.kv.get("anim") and t["birth_gfc"] >= r.gfc]
        out.append({"tick": r.gfc - t0, "anim": r.kv.get("anim"), "el": r.kv.get("el"), "info": r.kv.get("info"),
                    "ro": r.kv.get("ro"), "slot": r.kv.get("slot"), "obj": r.kv.get("obj"),
                    "link_ok": link is not None and (link.kv.get("ro"), link.kv.get("slot")) == (r.kv.get("ro"), r.kv.get("slot")),
                    "track": tr[0] if tr else None})
    return out


def sound(rows, t0):
    """NoteTrack sound rows with the play request and its result that follow each."""
    out = []
    for i, r in enumerate(rows):
        if r.tag != "LNT":
            continue
        nxt = [x for x in rows[i + 1:i + 8] if x.tag in ("LSP", "LSH")]
        sp = next((x for x in nxt if x.tag == "LSP"), None)
        sh = next((x for x in nxt if x.tag == "LSH"), None)
        out.append({"tick": r.gfc - t0, "pc": r.kv.get("pc"), "owner": r.kv.get("owner"), "fighter": r.kv.get("fighter"),
                    "a4": r.kv.get("a4"), "a6": r.kv.get("a6"), "anim": r.kv.get("anim"), "frame": r.kv.get("frame"),
                    "archive": None if sp is None else sp.kv.get("archive"), "index": None if sp is None else sp.kv.get("index"),
                    "ok": None if sh is None else sh.kv.get("ok"), "player": None if sh is None else sh.kv.get("player")})
    return out


import re as _re

_TAG = _re.compile(r'^(?:L[A-Z]{1,4}|FXT|FXO|FXPOS|PH\w*) gfc=(\d+)|"gfc":(\d+)')


def _tag(line):
    m = _TAG.search(line)
    return None if m is None else int(m[1] or m[2])


def cut(lines, first, last):
    """The bounded probe window of a native capture whose first and last frame rows read game frame counters `first` and `last`.
    It starts at the last `FXT gfc=<first>` heartbeat (the one after the capture's state reload), extended back over that tick's
    frame-anchor JSON block and the lifecycle rows tagged with the same tick, and ends before the first row tagged past `last`
    that follows `FXT gfc=<last>`. Raises ValueError when either heartbeat is absent: a window is never guessed."""
    fxt = [i for i, ln in enumerate(lines) if ln.startswith("FXT gfc=%d " % first)]
    if not fxt:
        raise ValueError("no FXT heartbeat at the first frame %d" % first)
    start = fxt[-1]
    s, seen_frame = start, False
    while s > 0:
        ln = lines[s - 1]
        v = _tag(ln)
        if (v is not None and v != first) or (seen_frame and v is None):
            break
        if ln.startswith('{"type":"frame"'):
            seen_frame = True
        s -= 1
    ends = [i for i, ln in enumerate(lines) if ln.startswith("FXT gfc=%d " % last) and i > start]
    if not ends:
        raise ValueError("no FXT heartbeat at the last frame %d" % last)
    e = ends[0]
    while e < len(lines) and not ((_tag(lines[e]) or 0) > last):
        e += 1
    return lines[s:e]


PLAYER_OBJ_BASE, PLAYER_OBJ_SIZE, PLAYER_ID_WORD = 0x020AD648, 0x44, 15
MOVE_ANIM = {("596", "X"): 0x074229, ("597", "X"): 0x07422B, ("596", "UP_X"): 0x07422A, ("597", "UP_X"): 0x07422C,
             ("596", "UA"): 0x074218, ("597", "UA"): 0x074218}
# the ticket's sound-zero key per X cell: (anim, frame, tier archive at controller +0xA6)
SOUND_KEY = {"596": (0x074229, 55, 0x19D), "597": (0x07422B, 53, 0x19E)}
# the ticket's four retirement occurrences: panel -> (effect id, archive birth frame) (j6-j9 ticket, "Capture the four unobserved
# retirements"). Each named occurrence's initializer runs on tick move + f + 1, where move is the tick the body animation was
# initialized (recorded: 52/78/79 in k596 X, 50 in k597 X, move 26). The NoteTrack row's own frame field reads 55/53 on tick
# move + 55/53, so the ticket's archive frame numbering and the recorded frame field differ by one tick at effect events.
RETIREMENTS = {"596": ((0x074261, 25), (0x074266, 51), (0x074265, 52)), "597": ((0x074285, 23),)}
# shot-art segment count per panel's X (ticket: 14 k4 and 18 k5 shot elements)
SEGMENTS = {"596": 14, "597": 18}
PANELS, MOVES, FACINGS, REPEATS = ("596", "597"), ("X", "UP_X", "UA"), ("R", "L"), (1, 2, 3)


def run_id(panel, move, facing, rep):
    """The ticket's run name for one matrix run."""
    return "J6-TRX-k%s-%s-%s-whiff-repeat%d" % (panel, move, facing, rep)


def requests(rows, t0):
    """Every sound play request: the LSP row, the first LSH after it (its result) and the NoteTrack (LNT) row of the same tick that
    precedes it with no other request between, if any. The ARM7 player id is read from the dump, never computed from the object
    address."""
    out = []
    for i, r in enumerate(rows):
        if r.tag != "LSP":
            continue
        sh = next((x for x in rows[i + 1:] if x.tag in ("LSH", "LSP")), None)
        sh = sh if sh is not None and sh.tag == "LSH" else None
        nt = next((x for x in reversed(rows[:i]) if x.tag in ("LNT", "LSP") or x.gfc != r.gfc), None)
        nt = nt if nt is not None and nt.tag == "LNT" and nt.gfc == r.gfc else None
        pw = sh.kv.get("pw") if sh is not None else None
        words = [int(v, 16) for v in pw.strip(",").split(",")] if isinstance(pw, str) and pw.strip(",") else []
        out.append({"tick": r.gfc - t0, "archive": r.kv.get("archive"), "index": r.kv.get("index"),
                    "ok": None if sh is None else sh.kv.get("ok"), "player_obj": None if sh is None else sh.kv.get("player"),
                    "player_id": words[PLAYER_ID_WORD] & 0xFF if len(words) > PLAYER_ID_WORD else None,
                    "notetrack": None if nt is None else {"pc": nt.kv.get("pc"), "owner": nt.kv.get("owner"), "a6": nt.kv.get("a6"),
                                                           "anim": nt.kv.get("anim"), "frame": nt.kv.get("frame")}})
    return out


def _voice(v, t0):
    st = v["start"]
    return {"ch": v["ch"], "gen": v["gen"], "track": v["alloc"]["track"] if v["alloc"] else None,
            "prio": v["alloc"]["prio"] if v["alloc"] else None, "alloc": _rel(v["alloc"]["gfc"], t0) if v["alloc"] else None,
            "start": st["gfc"] - t0, "fields": st["fields"], "mix": st["mix"], "sad": (v["setup"] or {}).get("sad"),
            "updates": len(v["updates"]), "ends": [[e["kind"], e["gfc"] - t0] for e in v["ends"]]}


def attribute(reqs, voices, t0):
    """Join each successful request to the ARM7 voices its player id allocated from the request tick until that player id's next
    request. A voice is attributed to at most one request; unattributed voices stay counted by player."""
    out, used = [], set()
    ok = [q for q in reqs if q["ok"] and q["player_id"] is not None]
    for q in reqs:
        if q not in ok:
            out.append(dict(q, voices=[]))
            continue
        i = ok.index(q)
        nxt = next((x["tick"] for x in ok[i + 1:] if x["player_id"] == q["player_id"]), None)
        vs = []
        for k, v in enumerate(voices):
            a = v["alloc"]
            if k in used or a is None or a["player"] != q["player_id"]:
                continue
            tick = a["gfc"] - t0
            if tick >= q["tick"] and (nxt is None or tick < nxt):
                used.add(k)
                vs.append(_voice(v, t0))
        out.append(dict(q, voices=vs))
    rest = Counter(v["alloc"]["player"] if v["alloc"] else None for k, v in enumerate(voices) if k not in used)
    return out, {str(k): n for k, n in sorted(rest.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))}


def start(window, t0):
    """The fighters as the first dump of the window (tick 0) reports them: object, state, flags word +0x78 and raw physics
    position, read from the probe's `fighter` rows, never from the state recipe."""
    out, gfc = {}, None
    for ln in window:
        if ln.startswith('{"type":"frame"'):
            gfc = json.loads(ln)["gfc"]
        elif ln.startswith('{"type":"fighter"') and gfc == t0:
            f = json.loads(ln)
            out["p%d" % (f["slot"] + 1)] = {"obj": int(f["obj"], 16), "state": f["state"], "flags78": int(f["flags78"], 16),
                                           "phys": [f["physx"], f["physy"]]}
        elif gfc is not None and gfc > t0:
            break
    return out


def body(life, tracks, t0):
    """The fighter body animation initializations: successful Train-bank initializer calls that start no tracked presentation (the
    effect ids share the body's id range, e.g. the UA components 0x074238/0x074239/0x07423F)."""
    started = {(t["obj"], (t.get("init") or {}).get("gfc")) for t in tracks}
    return [{"tick": c["ret_gfc"] - t0, "obj": c["obj"], "anim": c["anim"]} for c in life["calls"]
            if c["ok"] and c["anim"] >> 8 == TRAIN_BANK and (c["obj"], c["ret_gfc"]) not in started]


def out_of_scope(tracks, rows, t0, press):
    """Tracks the input cannot have caused, {name: {birth, reason}}:
      born_before_input  born before the first press tick;
      persistent_object  outside the Train bank, its object drawn on every tick from the window's first through the birth and its
                         block not allocated in the window before it: a re-initialization of a presentation that predates the input
                         (the screen-space HUD objects of banks 0x5000 / 0x5F00 are re-initialized by the HUD at times that depend
                         only on the elapsed frames: 0x500009 on tick 101 of the k597 X facing-L window, absent from facing R).
    Train bank tracks are in scope whatever their object's history."""
    drawn, allocs = {}, {}
    for r in rows:
        if r.tag == "LDX":
            drawn.setdefault(r.kv.get("owner"), set()).add(r.gfc)
        elif r.tag == "LMR":
            allocs.setdefault(r.kv.get("ptr"), []).append(r.gfc)
    out = {}
    for t in tracks:
        name, b = "%s#%d" % (t["id_hex"], t["n"]), t["birth_gfc"]
        if b - t0 < press:
            out[name] = {"birth": b - t0, "reason": "born_before_input"}
        elif t["id"] >> 8 != TRAIN_BANK and set(range(t0, b + 1)) <= drawn.get(t["obj"], set()) and \
                not any(g <= b for g in allocs.get(t["obj"], [])):
            out[name] = {"birth": b - t0, "reason": "persistent_object"}
    return out


def receipt(window, arm7, clock, cell, banks):
    """One run's receipt (train-matrix-receipt/v2) from its bounded probe window, the ARM7 window, the capture clock and the cell
    {panel, move, facing, rep, state, raw_sha256, presses}. `facts` holds everything repeats must agree on; `digest` is its sha256.

    Certification scope is what the input can have caused (out_of_scope): a refused track outside it is listed in `pre_input` with
    its reason and the kinds of its refusals, never certified and never silently dropped. Every other refusal, including the ones of
    no track, is fatal."""
    import fxo_lifecycle as lc
    import fxo_tracker as ft
    import snd_arm7 as sa
    t0 = clock["first_gfc"]
    red = ft.reduce(window, banks=banks, lifecycle=True)
    rows = lc.parse(window)
    life = lc.lifecycle(rows)
    a7 = sa.voices(sa.parse(arm7))
    scope = out_of_scope(red["tracks"], rows, t0, min(p[0] for p in cell["presses"]))
    pre = sorted(n for n in scope if any(m.get("track") == n for m in red["missing"]))
    refusals = [m for m in red["missing"] if m.get("track") not in pre] + [dict(m, layer="arm7") for m in a7["missing"]]
    base = {"schema": SCHEMA, "cell": cell, "clock": {"first_gfc": t0, "last_gfc": clock["last_gfc"]}, "banks": banks}
    if refusals:
        return dict(base, ok=False, refusals=refusals)
    tracks = [t for t in red["tracks"] if "%s#%d" % (t["id_hex"], t["n"]) not in pre]
    pre_input = [dict(scope[name], track=name, refusals=sorted({m["kind"] for m in red["missing"] if m.get("track") == name}))
                 for name in pre]
    att, other = attribute(requests(rows, t0), a7["voices"], t0)
    facts = {"presentations": [presentation(t, t0) for t in tracks], "joins": joins(rows, tracks, t0), "sound": sound(rows, t0),
             "requests": att, "other_voices": other, "body": body(life, red["tracks"], t0), "start": start(window, t0),
             "pre_input": pre_input,
             "inits": {"calls": len(life["calls"]), "failed": [{"tick": c["gfc"] - t0, "obj": c["obj"], "anim": c["anim"],
                                                                "ret_pc": c["ret_pc"]} for c in life["failed"]]}}
    return dict(base, ok=True, refusals=[], facts=facts, digest=digest(facts), mirror=mirror(tracks))


def _mirror_free(facts):
    """The facts with every facing-dependent field dropped (screen position, flip, cells, scale), so the R and L runs of a cell compare
    on lifecycle, joins and sound alone."""
    keep = ("id", "alloc_gen", "birth", "birth_phase", "drawn", "draws", "sampled", "native")
    return {"presentations": [{k: p[k] for k in keep} for p in facts["presentations"]],
            "joins": [{k: j[k] for k in ("tick", "anim", "link_ok")} for j in facts["joins"]],
            "requests": [{k: q[k] for k in ("tick", "archive", "index", "ok", "player_id")} for q in facts["requests"]],
            "body": [{k: b[k] for k in ("tick", "anim")} for b in facts["body"]]}


def agree(receipts):
    """Repeat agreement of one cell: every receipt ok and the same digest. Returns {ok, digest, runs, differ}, `differ` naming the
    fact keys whose content differs from the first receipt's."""
    bad = [r["cell"]["rep"] for r in receipts if not r["ok"]]
    digs = sorted({r["digest"] for r in receipts if r["ok"]})
    differ = []
    if len(digs) > 1:
        f0 = next(r for r in receipts if r["ok"])["facts"]
        differ = sorted({k for r in receipts if r["ok"] for k in f0 if digest(r["facts"][k]) != digest(f0[k])})
    return {"ok": not bad and len(digs) == 1 and len(receipts) == len(REPEATS), "digest": digs[0] if len(digs) == 1 else None,
            "runs": len(receipts), "refused": bad, "differ": differ}


def retirement(p, t0):
    """A presentation's end as instruction times and dump observations, never conflated. `native` is the instruction-time end (a
    direct free with its caller, or a replacing initialization) closing allocation generation `alloc_gen`; `reinit` is the successor
    initialization that reused the block before the same dump. Both carry the capture tick and the game frame counter (t0 + tick) of
    their recorded instruction row. `dump_observed` holds what the per-tick dump showed: the dump tick of the native end, of the
    successor, and the sampled end."""
    n = p["native"]
    su = None if n is None else n["successor"]
    return {"id": p["id"], "obj": p["obj"], "birth": p["birth"], "alloc_gen": p["alloc_gen"],
            "native": None if n is None else {"kind": n["kind"], "instruction_tick": n["instruction_tick"],
                                              "instruction_gfc": t0 + n["instruction_tick"], "free_kind": n["free_kind"],
                                              "caller": n["caller"], "by_anim": n["by_anim"]},
            "reinit": None if su is None else {"anim": su["anim"], "init_instruction_tick": su["init_instruction_tick"],
                                               "init_instruction_gfc": t0 + su["init_instruction_tick"]},
            "dump_observed": {"native_end_tick": None if n is None else n["dump_tick"], "reinit_tick": None if su is None else su["dump_tick"],
                              "sampled": p["sampled"]}}


def ticket_retirements(facts, panel, t0, move="X"):
    """The ticket's named occurrences in one receipt (first capture gfc t0): per (id, frame), the presentations of that id whose
    initializer ran on the move tick + frame + 1 (see RETIREMENTS), each with its retirement(). `found` is False when none or more
    than one matches."""
    move_ticks = [b["tick"] for b in facts["body"] if b["anim"] == MOVE_ANIM[(panel, move)]]
    out = []
    for eid, frame in RETIREMENTS[panel]:
        hit = [p for p in facts["presentations"] if move_ticks and p["id"] == eid and p["init_tick"] == move_ticks[0] + frame + 1]
        out.append({"id": eid, "frame": frame, "found": len(hit) == 1, "matches": len(hit),
                    "retirement": retirement(hit[0], t0) if len(hit) == 1 else None})
    return out


def coverage(receipts):
    """One row per ticket run (36): present, ok, the expected body animation observed, and the per-cell checks the ticket names
    (sound-zero key, joins, retirements) where they apply."""
    by = {(r["cell"]["panel"], r["cell"]["move"], r["cell"]["facing"], r["cell"]["rep"]): r for r in receipts}
    out = []
    for panel in PANELS:
        for move in MOVES:
            for facing in FACINGS:
                for rep in REPEATS:
                    r = by.get((panel, move, facing, rep))
                    row = {"run": run_id(panel, move, facing, rep), "present": r is not None, "ok": bool(r and r["ok"])}
                    if r and r["ok"]:
                        f = r["facts"]
                        row["move_anim"] = any(b["anim"] == MOVE_ANIM[(panel, move)] for b in f["body"])
                        if move == "X":
                            anim, frame, arch = SOUND_KEY[panel]
                            key = [q for q in f["requests"] if q["notetrack"] and q["notetrack"]["anim"] == anim
                                   and q["notetrack"]["frame"] == frame and q["notetrack"]["a6"] == arch and q["archive"] == arch]
                            row["sound_key"] = bool(key) and all(q["ok"] for q in key)
                            row["sound_voices"] = sum(len(q["voices"]) for q in key)
                            js = f["joins"]
                            row["joins"] = len(js)
                            row["joins_ok"] = len(js) == SEGMENTS[panel] and all(j["link_ok"] and j["track"] is not None for j in js)
                            rs = ticket_retirements(f, panel, r["clock"]["first_gfc"])
                            row["retirements"] = sum(x["found"] for x in rs)
                            row["retirements_native"] = all(x["found"] and x["retirement"]["native"] is not None for x in rs)
                        row["failed_inits"] = len(f["inits"]["failed"])
                    out.append(row)
    return out


def cell_of(meta):
    """The receipt cell of a run from its request metadata {tag, cell: k<panel>-<move>-<facing>, state, raw_sha256, presses}. A matrix
    tag `m-<cell>-r<rep>` gives its repeat; any other run (diagnostic, mirror) is repeat 0."""
    panel, move, facing = meta["cell"][1:].split("-")
    rep = int(meta["tag"].rsplit("-r", 1)[1]) if meta["tag"].startswith("m-") else 0
    return {"panel": panel, "move": move, "facing": facing, "rep": rep, "tag": meta["tag"],
            "state": meta["state"], "raw_sha256": meta["raw_sha256"], "presses": meta["presses"]}


def write_excerpt(run, dest):
    """Write the committed excerpt of one packed run directory `run` (C-gdb/window.log.gz: the cut() window; A7-gdb/gdb-*.log.gz with
    offsets.json [a, b]: the ARM7 gdb log and the byte offset b of the capture end; C-gdb/capture-clock.json; request.json) to `dest`:
    fxo-window.log.gz (the window, recompressed), arm7-log.gz (every A7 row of the ARM7 log before b), capture-clock.json, cell.json
    and source.json (the sha256 of each raw input read, so the excerpt names the bundle it came from). Gzip mtime is 0, so the same
    run writes the same bytes."""
    import gzip
    run, dest = Path(run), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    a7 = sorted((run / "A7-gdb").glob("gdb-*.log.gz"))
    if len(a7) != 1:
        raise ValueError("%s: expected one ARM7 gdb log, found %d" % (run, len(a7)))
    _a, b = json.loads((run / "A7-gdb" / "offsets.json").read_text())
    rows = [ln for ln in gzip.decompress(a7[0].read_bytes())[:b].decode(errors="replace").split("\n") if ln.startswith("A7")]
    with gzip.GzipFile(dest / "arm7-log.gz", "wb", mtime=0, compresslevel=9) as f:
        f.write(("\n".join(rows) + "\n").encode())
    window = gzip.decompress((run / "C-gdb" / "window.log.gz").read_bytes())
    with gzip.GzipFile(dest / "fxo-window.log.gz", "wb", mtime=0, compresslevel=9) as f:
        f.write(window)
    c = json.loads((run / "C-gdb" / "capture-clock.json").read_text())
    (dest / "capture-clock.json").write_text(json.dumps({"first_gfc": c["first_gfc"], "last_gfc": c["last_gfc"]}, indent=1))
    req = json.loads((run / "request.json").read_text())
    (dest / "cell.json").write_text(json.dumps({"tag": req["tag"], "cell": req["cell"], "state": req["recipe"]["state"],
                                                "raw_sha256": req["recipe"]["raw_sha256"], "presses": req["recipe"]["presses"]},
                                               indent=1) + "\n")
    src = {"tag": req["tag"], "arm7_end_offset": b, "arm7_rows": len(rows), "window_lines": window.count(b"\n"),
           "sha256": {p: hashlib.sha256((run / p).read_bytes()).hexdigest()
                      for p in ("C-gdb/window.log.gz", "C-gdb/capture-clock.json", "A7-gdb/offsets.json", "request.json",
                                str(a7[0].relative_to(run)))}}
    (dest / "source.json").write_text(json.dumps(src, indent=1, sort_keys=True) + "\n")
    return dest


def excerpt_receipt(path, banks=None):
    """The receipt of a committed run excerpt: fxo-window.log.gz (the bounded probe window, cut()), arm7-log.gz (the ARM7 client rows
    up to the capture end, windowed by snd_arm7.window), capture-clock.json and cell.json."""
    import gzip
    import snd_arm7 as sa
    path = Path(path)
    clock = json.loads((path / "capture-clock.json").read_text())
    with gzip.open(path / "fxo-window.log.gz", "rt") as fh:
        window = fh.read().split("\n")
    with gzip.open(path / "arm7-log.gz", "rt") as fh:
        arm7 = sa.window(fh.read().split("\n"), clock["first_gfc"], clock["last_gfc"])
    return receipt(window, arm7, clock, cell_of(json.loads((path / "cell.json").read_text())), MATRIX_BANKS if banks is None else banks)


# Named visual identities (Train T5 component numbers): id -> name
NAMED = {0x074241: "gun (65)", 0x074280: "girl (128)", 0x07426E: "gold lines (110)", 0x07426F: "swirl (111)", 0x07428E: "swirl (142)"}
REGISTER = "open: the register stays open until a downstream implementation and its checks exist"


def _cellname(c):
    return "k%s-%s-%s" % (c["panel"], c["move"], c["facing"])


def _drawn_facts(p):
    return {"drawn": p["drawn"], "draws": p["draws"], "cells": p["cells"], "flips": p["flips"], "scales": p["scales"],
            "spaces": p["spaces"], "priority": p["priority"], "native": p["native"] and p["native"]["kind"]}


def claims(receipts, mirrors=()):
    """Per-claim native evidence for the four claims (shot sound, named visuals, x-mirror, retirements) from the matrix receipts (one representative repeat per cell, the
    facts of the other repeats being equal when agreement holds). Each claim: {evidence, gaps, native_evidence: complete|incomplete,
    register}. `gaps` names every ticket requirement a run did not meet; complete means no gap.

    `mirrors` are receipts of runs recorded with the x-mirror byte (`mirror`, node+0x48). The x-mirror claim's framebuffer-transform evidence
    takes one per cell, accepted only when its digest equals the cell's agreed matrix digest (same facts, so the same presentation
    numbering); a cell without one is a named gap."""
    by = {}
    for r in receipts:
        by.setdefault(_cellname(r["cell"]), []).append(r)
    agr = {k: agree(v) for k, v in by.items()}
    rep = {k: next((r for r in sorted(v, key=lambda r: r["cell"]["rep"]) if r["ok"]), None) for k, v in by.items()}
    cov = coverage(receipts)
    out = {}

    def why(k):
        a = agr.get(k)
        if a is None or rep.get(k) is None:
            return "%s: no certified run" % k
        if a["runs"] != len(REPEATS) or a["refused"]:
            return "%s: %d of %d repeats certified" % (k, a["runs"] - len(a["refused"]), len(REPEATS))
        return "%s: repeats disagree on %s" % (k, a["differ"])

    every = ["k%s-%s-%s" % (p, m, f) for p in PANELS for m in MOVES for f in FACINGS]

    gaps, ev = [], {}
    for panel in PANELS:
        for facing in FACINGS:
            k = "k%s-X-%s" % (panel, facing)
            r = rep.get(k)
            if r is None or not agr[k]["ok"]:
                gaps.append(why(k))
                if r is None:
                    continue
            f = r["facts"]
            pres = {p["n"]: p for p in f["presentations"]}
            js = [dict(j, presentation={"id": pres[j["track"]]["id"], "alloc_gen": pres[j["track"]]["alloc_gen"],
                                        "cells": pres[j["track"]]["cells"], "flips": pres[j["track"]]["flips"],
                                        "anchor": pres[j["track"]]["path"][:1], "spaces": pres[j["track"]]["spaces"]}
                       if j["track"] in pres else None) for j in f["joins"]]
            anim, frame, arch = SOUND_KEY[panel]
            key = [q for q in f["requests"] if q["notetrack"] and (q["notetrack"]["anim"], q["notetrack"]["frame"]) == (anim, frame)]
            ev[k] = {"joins": js, "sound_key": key}
            if len(js) != SEGMENTS[panel] or not all(j["link_ok"] and j["presentation"] for j in js):
                gaps.append("%s: %d of %d shot elements joined" % (k, sum(1 for j in js if j["link_ok"] and j["presentation"]), SEGMENTS[panel]))
            if len(key) != 1 or key[0]["archive"] != arch or key[0]["notetrack"]["a6"] != arch or not key[0]["ok"] or not key[0]["voices"]:
                gaps.append("%s: sound-zero key not dispatched from +0xA6 archive 0x%x with voices" % (k, arch))
    out["SG-0304.8"] = {"evidence": ev, "gaps": gaps}

    gaps, ev = [], {}
    for eid, name in NAMED.items():
        seen = {k: [_drawn_facts(p) for p in r["facts"]["presentations"] if p["id"] == eid] for k, r in sorted(rep.items()) if r}
        ev["0x%06x %s" % (eid, name)] = {k: v for k, v in seen.items() if v} or "measured absence in %d cells" % len(seen)
    out["SG-0453.1"] = {"evidence": ev, "gaps": [why(k) for k in every if not agr.get(k, {}).get("ok")]}

    gaps, ev = [], {}
    for k in sorted(rep):
        r = rep[k]
        if r is None or r["cell"]["move"] != "UA":
            continue
        ps = r["facts"]["presentations"]
        ev[k] = {"body": r["facts"]["body"], "components": [dict(_drawn_facts(p), id=p["id"], birth=p["birth"], path=p["path"]) for p in ps],
                 "unterminated": [p["n"] for p in ps if p["native"] is None]}
        if ev[k]["unterminated"]:
            gaps.append("%s: components without a native end %s" % (k, ev[k]["unterminated"]))
    for panel in PANELS:
        for facing in FACINGS:
            k = "k%s-UA-%s" % (panel, facing)
            if rep.get(k) is None or not agr.get(k, {}).get("ok"):
                gaps.append(why(k))
    sw = {k: [p["birth"] for p in r["facts"]["presentations"] if p["id"] == 0x07426F] for k, r in sorted(rep.items())
          if r and r["cell"]["panel"] == "596" and r["cell"]["move"] == "X"}
    ev["k4 X swirl 0x07426f"] = sw
    mir = {}
    for m in mirrors:
        k = _cellname(m["cell"])
        if m["ok"] and m.get("mirror") and agr.get(k, {}).get("ok") and m["digest"] == agr[k]["digest"]:
            mir.setdefault(k, m["mirror"])
    ev["x mirror node+0x48"] = mir
    gaps += ["%s: no x-mirror run with the cell's digest" % k for k in every if k not in mir]
    out["SG-0453.2"] = {"evidence": ev, "gaps": gaps}

    gaps, ev = [], {}
    for r in sorted(receipts, key=lambda r: (r["cell"]["panel"], r["cell"]["facing"], r["cell"]["rep"])):
        c = r["cell"]
        if c["move"] != "X":
            continue
        k = run_id(c["panel"], "X", c["facing"], c["rep"])
        if not r["ok"]:
            gaps.append("%s: refused" % k)
            continue
        ev[k] = ticket_retirements(r["facts"], c["panel"], r["clock"]["first_gfc"])
        gaps += ["%s: 0x%06x frame %d not observed once (%d matches)" % (k, x["id"], x["frame"], x["matches"]) for x in ev[k] if not x["found"]]
        gaps += ["%s: 0x%06x has no native end" % (k, x["id"]) for x in ev[k] if x["found"] and x["retirement"]["native"] is None]
    for row in cov:
        if "-X-" in row["run"] and not row["present"]:
            gaps.append("%s: not recorded" % row["run"])
    out["SG-0453.4"] = {"evidence": ev, "gaps": gaps}
    for v in out.values():
        v["native_evidence"] = "incomplete" if v["gaps"] else "complete"
        v["register"] = REGISTER
    return out


def _excerpt_job(path):
    return Path(path).name, excerpt_receipt(path)


def _gz_json(obj):
    import gzip
    return gzip.compress((json.dumps(obj, sort_keys=True) + "\n").encode(), compresslevel=9, mtime=0)


def rebuild(matrix_dir, workers=4):
    """Every derived file of a matrix directory, rebuilt from its committed excerpts (fixture/<tag>, write_excerpt) alone:
    {relative path: bytes} for receipts/<tag>.json.gz (the 36 matrix runs, tag m-*), mirror/<tag>.json.gz (the x-mirror runs, tags
    d-* and h-*), agreement.json, coverage.json and claims.json. Other excerpts (the d2 diagnostic) feed no file. Refuses unless
    there are 36 matrix and 12 mirror excerpts."""
    from concurrent.futures import ProcessPoolExecutor
    fx = Path(matrix_dir) / "fixture"
    paths = sorted(str(p) for p in fx.iterdir() if p.name.startswith(("m-", "d-", "h-")))
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            got = dict(ex.map(_excerpt_job, paths))
    else:
        got = dict(map(_excerpt_job, paths))
    rcs = [got[t] for t in sorted(got) if t.startswith("m-")]
    mirrors = [got[t] for t in sorted(got) if not t.startswith("m-")]
    if len(rcs) != len(PANELS) * len(MOVES) * len(FACINGS) * len(REPEATS) or len(mirrors) != len(PANELS) * len(MOVES) * len(FACINGS):
        raise ValueError("%d matrix and %d mirror excerpts, expected 36 and 12" % (len(rcs), len(mirrors)))
    out = {}
    for t, r in got.items():
        out["%s/%s.json.gz" % ("receipts" if t.startswith("m-") else "mirror", t)] = _gz_json(r)
    cells = {}
    for r in rcs:
        cells.setdefault(_cellname(r["cell"]), []).append(r)
    out["agreement.json"] = (json.dumps({k: agree(v) for k, v in sorted(cells.items())}, indent=1, sort_keys=True) + "\n").encode()
    out["coverage.json"] = (json.dumps(coverage(rcs), indent=1) + "\n").encode()
    out["claims.json"] = (json.dumps(claims(rcs, mirrors), indent=1, sort_keys=True) + "\n").encode()
    return out


def sha256sums(matrix_dir):
    """SHA256SUMS of a matrix directory: every file but SHA256SUMS and README.md, sorted by relative path."""
    d = Path(matrix_dir)
    files = sorted(p for p in d.rglob("*") if p.is_file() and p.name not in ("SHA256SUMS", "README.md"))
    return "".join("%s  %s\n" % (hashlib.sha256(p.read_bytes()).hexdigest(), p.relative_to(d)) for p in files)


def check(matrix_dir, workers=4, want=None):
    """The relative paths whose committed bytes differ from rebuild() (missing files count), plus SHA256SUMS when it is stale and any
    receipts/ or mirror/ file rebuild() does not produce. Empty when the directory is exactly what its excerpts give. `want` is a
    rebuild() result to check against instead of rebuilding."""
    d = Path(matrix_dir)
    want = rebuild(d, workers) if want is None else want
    bad = [k for k, v in sorted(want.items()) if not (d / k).is_file() or (d / k).read_bytes() != v]
    bad += sorted(str(p.relative_to(d)) for sub in ("receipts", "mirror") for p in (d / sub).iterdir()
                  if str(p.relative_to(d)) not in want)
    if not (d / "SHA256SUMS").is_file() or (d / "SHA256SUMS").read_text() != sha256sums(d):
        bad.append("SHA256SUMS")
    return bad


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="rebuild or check a Train matrix directory from its committed excerpts")
    ap.add_argument("command", choices=("rebuild", "check"))
    ap.add_argument("matrix_dir")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if a.command == "rebuild":
        d = Path(a.matrix_dir)
        for sub in ("receipts", "mirror"):
            (d / sub).mkdir(exist_ok=True)
        for k, v in rebuild(d, a.workers).items():
            (d / k).write_bytes(v)
        (d / "SHA256SUMS").write_text(sha256sums(d))
        print("rebuilt", d)
    else:
        bad = check(a.matrix_dir, a.workers)
        print("\n".join(bad) if bad else "ok")
        sys.exit(1 if bad else 0)
