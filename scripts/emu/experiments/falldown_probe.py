"""Falldown / forced-knockdown probe (tracker item jus-p6jm).

Drives a repeated-attack loop on an idle victim and logs the WHOLE victim
fighter object (0x00..0x180) every frame, plus the victim's ColPrm scratch
tail (M+0x140..0x180) and the opponent deck HP slot. The per-frame diff of
the object is how we hunt a combo-damage accumulator.

Watch budget (validator cap 512 bytes/frame):
    v_obj  0x000..0x180  384
    v_M    0x140..0x180   64
    v_slot 0x00..0x08      8
    a_obj  0x18..0x20      8   (attacker state, to time the loop)
                          ---
                          464

CLI
---
    python3 falldown_probe.py run --label b20 --attack B --hits 20 \
        --period 36 --hp 500 --outdir <dir>
    python3 falldown_probe.py diff --outdir <dir> --label b20
    python3 falldown_probe.py hits --outdir <dir> --label b20

`run` needs the emulator up (scripts/emu/launch_emu.sh) and the state
pc-kakashi-npc-jotaro-dark-tournament present. `diff`/`hits` are offline.
"""
import argparse
import gzip
import json
import os
import struct
import subprocess
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
JUSEMU = os.path.join(REPO, "scripts", "emu", "jusemu.py")

# pc-kakashi-npc-jotaro-dark-tournament (moveset_map.py ADDRESSES["pc"])
ADDR = {
    "a_obj": 0x02228E80,
    "v_obj": 0x0224EF00,
    "v_M": 0x0220F494,
    "v_hp": 0x021DF7F0,
    "a_elem": 0x0220C068,
    "v_elem": 0x0220C0A8,
    # damage.md 4: the deck record's `+0x16` max HP / `+0x18` current HP pair,
    # i.e. two bytes below the current-HP address. Max HP is CLAMPED to
    # 0x4000 = 256.0 by the engine. M+0x178/0x17c mirror the pair and are
    # rebuilt every frame, so a poke there does not stick (run 3 attempt).
    "v_maxhp": 0x021DF7EE,
    "v_curhp": 0x021DF7F0,
}
# other victim states, for the max-HP scaling test
STATES = {
    "pc-kakashi-npc-jotaro-dark-tournament": dict(ADDR),
    "pc-eve-npc-jotaro-dark-tournament": dict(ADDR, v_obj=0x0222CFE0),
    "pc-kenshin-npc-nami-dark-tournament": dict(ADDR, v_obj=0x02230D60),
    "pc-kenshin-npc-franky-dark-tournament": dict(ADDR, v_obj=0x02230D60),
    "pc-kenshin-npc-luffy-dark-tournament": dict(ADDR, v_obj=0x02230D60),
}

ATTACKS = {           # name -> (buttons, period hint)
    "X": (["X"], 90),
    "upX": (["UP", "X"], 90),
    "B": (["B"], 36),
    "Y": (["Y"], 47),
    "sideB": (["LEFT", "B"], 40),
    "downY": (["DOWN", "Y"], 53),
}


def emu(*a, timeout=400):
    r = subprocess.run(["python3", JUSEMU, *a], capture_output=True,
                       text=True, timeout=timeout)
    if r.returncode:
        raise SystemExit("jusemu %s failed:\n%s\n%s"
                         % (a, r.stdout[-800:], r.stderr[-800:]))
    return r.stdout


def peek(addr, n):
    v = json.loads(emu("peek", hex(addr), str(n)))["result"]["value"]
    if isinstance(v, list):
        return bytes(v)
    return struct.pack("<I", v & 0xFFFFFFFF)[:n]


def watches(A, layout="obj"):
    """Two layouts, because 0x180 of the object plus 0x180 of M is over the
    512-byte/frame validator cap. `obj` diffs the fighter object, `M` diffs
    the whole ColPrm scratch block. Both keep HP, the state code and x."""
    common = [
        {"name": "vslot", "addr": A["v_hp"] - 4, "len": 0x30},
        {"name": "vx", "addr": A["v_elem"] + 0xC, "len": 4},
        {"name": "ax", "addr": A["a_elem"] + 0xC, "len": 4},
        {"name": "aobj", "addr": A["a_obj"] + 0x18, "len": 8},
    ]
    if layout == "M":
        return common + [
            {"name": "vM", "addr": A["v_M"], "len": 0x180},
            {"name": "vst", "addr": A["v_obj"] + 0x100, "len": 0x20},
            {"name": "v18", "addr": A["v_obj"] + 0x18, "len": 8},
        ]
    return common + [
        {"name": "vobj", "addr": A["v_obj"], "len": 0x180},
        {"name": "vM", "addr": A["v_M"] + 0x140, "len": 0x40},
    ]


def build_segments(attack, hits, period, approach, facing, hold=3, first=0,
                   chase=False):
    """approach frames of `facing`, then `hits` presses `period` apart.

    With `chase`, every frame between two attack presses holds `facing`, so
    the attacker walks back into range after each knockback. Without it the
    loop breaks after two hits (run 1) because B's own pushback outranges B.
    """
    segs = []
    f = 0
    if approach > 0:
        segs.append({"from": 0, "to": approach - 1, "buttons": [facing]})
        f = approach
    f += first
    attack_frames = []
    for i in range(hits):
        s = f + i * period
        attack_frames.append(s)
        if chase and i > 0:
            gap_from = attack_frames[i - 1] + hold
            gap_to = s - 1 if chase < 0 else min(s - 1, gap_from + chase - 1)
            if gap_from <= gap_to:
                segs.append({"from": gap_from, "to": gap_to,
                             "buttons": [facing]})
        segs.append({"from": s, "to": s + hold - 1,
                     "buttons": list(ATTACKS[attack][0])})
    return segs, attack_frames


def run(args):
    A = STATES[args.state]
    facing = args.facing.upper()
    segs, attack_frames = build_segments(
        args.attack, args.hits, args.period, args.approach, facing,
        hold=args.hold, first=args.first, chase=args.chase)
    plan = {"name": args.label, "segments": segs,
            "tail_frames": args.tail, "watches": watches(A, args.layout)}
    os.makedirs(args.outdir, exist_ok=True)
    ppath = os.path.join(args.outdir, args.label + ".plan.json")
    with open(ppath, "w") as f:
        json.dump(plan, f, indent=1)

    emu("state", "load", args.state)
    time.sleep(2.5)
    pokes = []
    if args.hp:
        # HP is a SIGNED 16-bit raw/64 (run 2: 0xE100 read back as -128.0 and
        # killed the victim on the spot), so the ceiling is 511.98.
        raw = int(round(args.hp * 64))
        if not (0 < raw <= 0x4000):
            raise SystemExit("hp %.2f above the engine's 0x4000 max-HP cap"
                             % args.hp)
        blob = struct.pack("<h", raw)
        # M+0x178 max first: the hit routine CLAMPS current HP to max (run 1).
        for addr in (A["v_maxhp"], A["v_curhp"]):
            emu("poke", hex(addr), blob.hex())
            time.sleep(0.15)
            got = peek(addr, 2)
            if got != blob:
                raise SystemExit("HP poke did not stick at %s: %s"
                                 % (hex(addr), got.hex()))
            pokes.append([hex(addr), blob.hex()])
    if args.vx is not None:
        blob = struct.pack("<i", int(round(args.vx * 256)))
        emu("poke", hex(A["v_elem"] + 0xC), blob.hex())
        pokes.append([hex(A["v_elem"] + 0xC), blob.hex()])
        time.sleep(0.15)
    if args.ax is not None:
        blob = struct.pack("<i", int(round(args.ax * 256)))
        emu("poke", hex(A["a_elem"] + 0xC), blob.hex())
        pokes.append([hex(A["a_elem"] + 0xC), blob.hex()])
        time.sleep(0.15)
    for spec in args.poke or []:
        addr, hexb = spec.split(":")
        emu("poke", addr, hexb)
        time.sleep(0.2)
        pokes.append([addr, hexb])

    out = emu("run", ppath, "--timeout", str(args.timeout))
    logline = [l for l in out.splitlines() if l.startswith("log:")]
    if not logline:
        raise SystemExit("plan produced no log:\n" + out[-800:])
    rows = [json.loads(l) for l in open(logline[0].split()[1])]
    gz = os.path.join(args.outdir, args.label + ".jsonl.gz")
    with gzip.open(gz, "wt") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    meta = {"label": args.label, "state": args.state, "attack": args.attack,
            "hits": args.hits, "period": args.period, "hold": args.hold,
            "approach": args.approach, "facing": facing, "first": args.first,
            "chase": args.chase, "layout": args.layout,
            "attack_frames": attack_frames, "pokes": pokes,
            "addresses": {k: hex(v) for k, v in A.items()},
            "frames": len(rows), "plan": ppath}
    with open(os.path.join(args.outdir, args.label + ".meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(json.dumps({k: meta[k] for k in
                      ("label", "state", "attack", "hits", "period",
                       "frames", "pokes")}))


# ------------------------------------------------------------------ offline
def _buf(w, name):
    v = w.get(name)
    if v is None:
        return b""
    if isinstance(v, int):
        return struct.pack("<I", v & 0xFFFFFFFF)
    return bytes(v)


def frames(outdir, label):
    gz = os.path.join(outdir, label + ".jsonl.gz")
    out = []
    for line in gzip.open(gz, "rt"):
        r = json.loads(line)
        w = r.get("watches") or r.get("w") or {}
        out.append({"f": r.get("frame", r.get("framecount")),
                    "vobj": _buf(w, "vobj"), "vM": _buf(w, "vM"),
                    "vslot": _buf(w, "vslot"), "aobj": _buf(w, "aobj"),
                    "vst": _buf(w, "vst"), "v18": _buf(w, "v18"),
                    "vx": _buf(w, "vx"), "ax": _buf(w, "ax")})
    return out


def hp_of(fr):
    """Victim live HP. The deck slot record at 0x021DF7F0 is a MIRROR that a
    poke does not stick in (run 1: poked 500 -> read back 160 on the first
    hit), so the live value is M+0x17c."""
    if len(fr["vM"]) >= 0x180:
        return struct.unpack_from("<h", fr["vM"], 0x17C)[0] / 64.0
    if len(fr["vM"]) >= 0x40:
        return struct.unpack_from("<h", fr["vM"], 0x17C - 0x140)[0] / 64.0
    return hp_rec(fr)


def x_of(fr, key="vx"):
    if len(fr.get(key) or b"") < 4:
        return float("nan")
    return struct.unpack_from("<i", fr[key], 0)[0] / 256.0


def hp_rec(fr):
    """Deck-record current HP; the vslot watch starts 4 bytes low."""
    return struct.unpack_from("<h", fr["vslot"], 4)[0] / 64.0


def vfield(fr, off):
    """A victim-object byte, from whichever layout the capture used."""
    o = fr.get("vobj") or b""
    if len(o) > off:
        return o[off]
    if 0x100 <= off < 0x120 and len(fr.get("vst") or b"") == 0x20:
        return fr["vst"][off - 0x100]
    if 0x18 <= off < 0x20 and len(fr.get("v18") or b"") == 8:
        return fr["v18"][off - 0x18]
    return -1


def cmd_hits(args):
    fr = frames(args.outdir, args.label)
    meta = json.load(open(os.path.join(args.outdir,
                                       args.label + ".meta.json")))
    print("rel  hp      state hitstun +0x110 +0x112 react  M16C   vx      ax")
    prev_hp = None
    n = 0
    total = 0.0
    for i, f in enumerate(fr):
        hp = hp_of(f)
        mbase = 0 if len(f["vM"]) > 0x100 else 0x140
        m16c = struct.unpack_from("<H", f["vM"], 0x16C - mbase)[0]
        st = vfield(f, 0x18)
        hs = vfield(f, 0x115)
        interesting = (prev_hp is not None and hp != prev_hp) or m16c
        if interesting:
            if prev_hp is not None and hp < prev_hp:
                n += 1
                total += prev_hp - hp
            print("%4d %7.2f %5d %7d %6d %6d %5d %5d %7.2f %7.2f" %
                  (i, hp, st, hs, vfield(f, 0x110), vfield(f, 0x112),
                   vfield(f, 0x100), m16c,
                   x_of(f, "vx"), x_of(f, "ax")))
        prev_hp = hp
    print("hits(hp-drops)=%d total_damage=%.2f  attack_frames=%s"
          % (n, total, meta["attack_frames"][:40]))


def cmd_states(args):
    fr = frames(args.outdir, args.label)
    last = None
    for i, f in enumerate(fr):
        st = vfield(f, 0x18)
        if st != last:
            print("rel %4d  state %3d  hp %7.2f  hitstun %3d"
                  % (i, st, hp_of(f), vfield(f, 0x115)))
            last = st


IGNORE = set()          # filled by --ignore


def cmd_diff(args):
    """Per-frame diff of one watched buffer; per-offset change counts."""
    fr = frames(args.outdir, args.label)
    key = args.buf
    lo, hi = args.lo, args.hi
    changes = {}
    trace = {}
    for i in range(1, len(fr)):
        a, b = fr[i - 1][key], fr[i][key]
        if not a or not b:
            continue
        for o in range(lo, min(hi, len(a), len(b))):
            if a[o] != b[o]:
                changes[o] = changes.get(o, 0) + 1
                trace.setdefault(o, []).append((i, a[o], b[o]))
    print("offset  n_changes  first->last  monotone_up  distinct_values")
    for o in sorted(changes):
        t = trace[o]
        vals = [t[0][1]] + [x[2] for x in t]
        up = all(vals[k + 1] >= vals[k] for k in range(len(vals) - 1))
        if args.max_changes and changes[o] > args.max_changes:
            continue
        print("0x%03X  %8d  %3d->%-3d  %-11s %d"
              % (o, changes[o], vals[0], vals[-1], up, len(set(vals))))
    if args.show:
        for o in [int(x, 16) for x in args.show]:
            print("\n0x%03X trace:" % o)
            print("  " + ", ".join("%d:%d->%d" % t for t in trace.get(o, [])))


def cmd_field(args):
    """Print one field per frame alongside HP, for the frames it changes."""
    fr = frames(args.outdir, args.label)
    off = int(args.offset, 16)
    ln = args.len
    prev = None
    for i, f in enumerate(fr):
        src = f["vM"] if args.m else f["vobj"]
        base = 0x140 if args.m else 0
        if off - base + ln > len(src):
            continue
        v = int.from_bytes(src[off - base:off - base + ln], "little")
        if v != prev:
            print("rel %4d  hp %7.2f  val %d (0x%X)" % (i, hp_of(f), v, v))
            prev = v


def main():
    p = argparse.ArgumentParser(prog="falldown_probe")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run")
    r.add_argument("--label", required=True)
    r.add_argument("--outdir", required=True)
    r.add_argument("--state", default="pc-kakashi-npc-jotaro-dark-tournament")
    r.add_argument("--attack", default="B", choices=sorted(ATTACKS))
    r.add_argument("--hits", type=int, default=20)
    r.add_argument("--period", type=int, default=36)
    r.add_argument("--hold", type=int, default=3)
    r.add_argument("--approach", type=int, default=26)
    r.add_argument("--facing", default="LEFT")
    r.add_argument("--first", type=int, default=0)
    r.add_argument("--chase", type=int, default=0,
                   help="frames of --facing after each press (walk back into "
                        "range); -1 = the whole gap")
    r.add_argument("--tail", type=int, default=180)
    r.add_argument("--hp", type=float, default=0.0,
                   help="poke the victim's current-HP record to this value")
    r.add_argument("--vx", type=float, help="poke victim element x (px)")
    r.add_argument("--ax", type=float, help="poke attacker element x (px)")
    r.add_argument("--poke", action="append",
                   help="extra poke as 0xADDR:hexbytes")
    r.add_argument("--layout", default="obj", choices=("obj", "M"))
    r.add_argument("--timeout", type=int, default=600)
    r.set_defaults(fn=run)

    for name, fn in (("hits", cmd_hits), ("states", cmd_states)):
        s = sub.add_parser(name)
        s.add_argument("--outdir", required=True)
        s.add_argument("--label", required=True)
        s.set_defaults(fn=fn)

    d = sub.add_parser("diff")
    d.add_argument("--outdir", required=True)
    d.add_argument("--label", required=True)
    d.add_argument("--lo", type=lambda x: int(x, 16), default=0)
    d.add_argument("--hi", type=lambda x: int(x, 16), default=0x180)
    d.add_argument("--max-changes", type=int, default=0)
    d.add_argument("--buf", default="vobj",
                   choices=("vobj", "vM", "vslot", "vst", "v18"))
    d.add_argument("--show", nargs="*", default=[])
    d.set_defaults(fn=cmd_diff)

    fl = sub.add_parser("field")
    fl.add_argument("--outdir", required=True)
    fl.add_argument("--label", required=True)
    fl.add_argument("--offset", required=True)
    fl.add_argument("--len", type=int, default=1)
    fl.add_argument("--m", action="store_true", help="offset is in M, not obj")
    fl.set_defaults(fn=cmd_field)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
