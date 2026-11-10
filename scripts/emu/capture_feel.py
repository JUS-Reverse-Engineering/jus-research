#!/usr/bin/env python3
"""Feel-vector capture for owner-played matches (tracker item jus-golden-damage-vectors-mj25).

Passively logs, every frame while a human plays:
  - the world-position array for both fighters (found by signature, see below)
  - both fighters' character records (HP, abilities, chr_b index)
via the bridge's tail mode, to docs/research/feel-captures/<match>.jsonl.gz.
Never injects input; the owner plays normally.

WHY signature scans instead of fixed addresses: both the character array and
the position array live in per-battle heap. A 0x20 shift between battles is on
record for the char array (find_battle_structs.py docstring), and stale copies
of both structures score well enough to fool a naive scan. Every `start`
re-locates both live and refuses to arm unless the identity checks pass.

Position-array signature (validated 2026-08-26, MOMO no-heal battle):
  two coordinate pairs of s32 8.8-fixed pixels, 0x40 apart (P1 then opponent),
  equal Y at match start (both grounded), and each pair duplicated at +8 —
  P1 X tracked walking (416.0 -> 503.6 px) and reversed on LEFT; idle held.

Character-record signature: HP u16 at +0x00 (multiple of 64), chr_b index
u8 < 74 at +0x29, four slots 0x50 apart. Identity-checked against --expect
when given (use the deck's runtime roster from its owner-context finding).

Usage (emulator already running via launch_emu.sh, battle on screen):
  python3 scripts/emu/capture_feel.py start --match m01 [--expect 67,68,32]
  ... owner plays ...
  python3 scripts/emu/capture_feel.py stop --match m01

`stop` gzips the log and writes a .meta.json sidecar with the resolved bases
(the conditions block for every row in the log).
"""
import argparse
import gzip
import json
import os
import struct
import subprocess
import sys
import tempfile
import time

EMU_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(EMU_DIR))
OUT_DIR = os.path.join(REPO, "docs", "research", "feel-captures")
MAIN_RAM = (0x02000000, 0x02400000)
CHR_B_COUNT = 74
POS_STRIDE = 0x40
CHAR_STRIDE = 0x50
ENTITY_DUMP_LEN = 0x100


def jusemu(*args, timeout=90):
    r = subprocess.run([sys.executable, os.path.join(EMU_DIR, "jusemu.py")] + list(args),
                       capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError("jusemu %s failed:\n%s%s" % (args[0], r.stdout, r.stderr))
    return r.stdout


def dump_ram(path):
    jusemu("dump", hex(MAIN_RAM[0]), hex(MAIN_RAM[1]), path, timeout=120)
    if os.path.getsize(path) != MAIN_RAM[1] - MAIN_RAM[0]:
        raise RuntimeError("short RAM dump")
    return open(path, "rb").read()


def s32(buf, off):
    return struct.unpack_from("<i", buf, off)[0]


def find_pos_array(ram):
    """Both fighters' (X, Y) pairs, 0x40 apart, equal Y, each duplicated at +8."""
    hits = []
    for off in range(0, len(ram) - POS_STRIDE - 16, 4):
        x1, y1 = s32(ram, off), s32(ram, off + 4)
        if not (5000 <= x1 <= 500000 and 5000 <= y1 <= 500000):
            continue
        if (x1, y1) != (s32(ram, off + 8), s32(ram, off + 12)):
            continue
        x2, y2 = s32(ram, off + POS_STRIDE), s32(ram, off + POS_STRIDE + 4)
        if y2 != y1 or x2 == x1:
            continue
        if (x2, y2) != (s32(ram, off + POS_STRIDE + 8), s32(ram, off + POS_STRIDE + 12)):
            continue
        hits.append(MAIN_RAM[0] + off)
    # The pair array has a history ring of stale copies at 0x80 stride below
    # the live one. The live block is preceded at -4 by a main-RAM pointer;
    # ring slots are not.
    #
    # This used to collapse a surviving tie by taking the highest address, on
    # the theory that the live block sits above its ring. THAT IS WRONG and it
    # cost real data: m01 lost 6.5 minutes of movement entirely, and one arm
    # each in m03 and m06 was dead, because the live block was simply absent
    # from the candidate list (it transiently fails the duplicated-at-+8 test
    # while the fighters move) and "highest" then returned a corpse. Failures
    # cluster in long sessions where the ring has grown; a fresh relaunch
    # usually happens to put the live block on top, which is why the bug looked
    # intermittent.
    #
    # So: never guess. Return every survivor and let the caller disambiguate by
    # observing which one actually moves (see cmd_probe_pos).
    live = [h for h in hits
            if MAIN_RAM[0] <= s32(ram, h - MAIN_RAM[0] - 4) < MAIN_RAM[1]]
    return sorted(live) or sorted(hits)


def find_char_array(ram, expect):
    """Four HP slots 0x50 apart, HP%64==0, chr_b idx <74; two such groups
    (player then opponent). Returns (player_base, opp_base)."""
    groups = []
    for off in range(0, len(ram) - 4 * CHAR_STRIDE, 4):
        idxs = []
        # Decks hold 1-4 battle chars. Unused slots are LOADED, not empty:
        # a placeholder record with HP=512 raw (8.0 — below any real chr_b
        # base HP, per codex 2026-08-26) and chr_b index byte 118 (>= 74).
        # The idx < CHR_B_COUNT check is what rejects them.
        for slot in range(4):
            b = off + slot * CHAR_STRIDE
            hp = struct.unpack_from("<H", ram, b)[0]
            idx = ram[b + 0x29]
            if hp == 0 or hp % 64 or hp > 0x4000 or idx >= CHR_B_COUNT:
                break
            idxs.append(idx)
        if idxs:
            groups.append((MAIN_RAM[0] + off, idxs))
    if expect:
        groups = [g for g in groups
                  if len(g[1]) >= len(expect) and g[1][:len(expect)] == expect]
    return groups


def positive_controls(ram, pos_base, char_base, expect):
    hp = struct.unpack_from("<H", ram, char_base - MAIN_RAM[0])[0]
    idx = ram[char_base - MAIN_RAM[0] + 0x29]
    assert hp % 64 == 0 and hp > 0, "player HP failed sanity (%d)" % hp
    assert idx < CHR_B_COUNT, "player chr_b index insane (%d)" % idx
    if expect:
        assert idx == expect[0], "active chr_b %d != expected %d" % (idx, expect[0])
    y1 = s32(ram, pos_base - MAIN_RAM[0] + 4)
    y2 = s32(ram, pos_base - MAIN_RAM[0] + POS_STRIDE + 4)
    assert y1 == y2, "fighters not sharing ground Y — wrong array?"
    return {"player_hp_raw": hp, "player_chrb": idx, "ground_y_8p8": y1}


def cmd_start(args):
    expect = [int(x) for x in args.expect.split(",")] if args.expect else None
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tf:
        ram = dump_ram(tf.name)
    os.unlink(tf.name)

    pos_hits = find_pos_array(ram)
    if getattr(args, "pos_base", None):
        pos_base = int(args.pos_base, 16)
        if pos_base not in pos_hits:
            print("warn: --pos-base %s is not in the current candidate list %s; "
                  "using it anyway because you asked, but re-probe if the watch "
                  "turns out dead"
                  % (hex(pos_base), [hex(h) for h in pos_hits]), file=sys.stderr)
    elif len(pos_hits) == 1:
        pos_base = pos_hits[0]
    else:
        raise SystemExit(
            "position-array signature hit %d times: %s\n"
            "Refusing to guess — picking the wrong one silently records a frozen\n"
            "position for the whole match (see find_pos_array). Identify the live\n"
            "block first:\n"
            "  1. tell the owner to walk back and forth continuously\n"
            "  2. python3 scripts/emu/capture_feel.py probe-pos --seconds 6\n"
            "  3. re-run start with --pos-base <the address it reports>"
            % (len(pos_hits), [hex(h) for h in pos_hits]))

    char_groups = find_char_array(ram, expect)
    if not char_groups:
        raise SystemExit("no character array matched — is a battle on screen?")
    player_base = char_groups[0][0]
    opp_base = player_base + 0x61C  # historical player->opponent offset; verified below
    ohp = struct.unpack_from("<H", ram, opp_base - MAIN_RAM[0])[0]
    if ohp == 0 or ohp % 64:
        raise SystemExit("opponent HP at player+0x61C failed sanity (%d)" % ohp)

    controls = positive_controls(ram, pos_base, player_base, expect)

    # Watch budget is 512 bytes/frame. All four deck slots per side are
    # watched (0x2C covers HP +0x00 .. chr_b idx +0x29) because switches are
    # routine: down+B force-switches the victim on hit, and KOs rotate the
    # CPU deck (owner context, tracker item jus-golden-damage-vectors-mj25).
    # Timer/SP are named absolute addresses expressed relative to the found
    # char base, assuming they drift together (same region, same allocation
    # era) — the meta sidecar records the assumption.
    watches = [
        {"name": "pos", "addr": pos_base, "len": 0x80},
        {"name": "timer", "addr": player_base - 0x763, "len": 1},
        {"name": "sp1", "addr": player_base + 0x55D, "len": 1},
    ]
    for i in range(4):
        watches.append({"name": "p1s%d" % i,
                        "addr": player_base + i * CHAR_STRIDE, "len": 0x2C})
        watches.append({"name": "ops%d" % i,
                        "addr": opp_base + i * CHAR_STRIDE, "len": 0x2C})
    os.makedirs(OUT_DIR, exist_ok=True)
    spec_path = os.path.join(OUT_DIR, args.match + ".watches.json")
    log_path = os.path.join(OUT_DIR, args.match + ".jsonl")
    json.dump(watches, open(spec_path, "w"), indent=1)

    # Per-frame watches only cover 0x2C of each 0x50 slot record, and the
    # 512 byte/frame budget has no room to widen them (8 slots x 0x50 = 640).
    # Per-character stats do not need per-frame sampling though: they are
    # constant for the whole match. So snapshot every slot's FULL 0x50 record
    # once, here, from the RAM dump we already hold. Costs nothing at runtime
    # and covers the 0x24 bytes/slot the stream misses. Confirmed necessary by
    # m03, where the two candidate weight fields both sat inside 0x2C but the
    # real field could as easily have been in the unwatched tail.
    slot_records = {}
    for side, base in (("p1", player_base), ("op", opp_base)):
        for i in range(4):
            addr = base + i * CHAR_STRIDE
            rec = ram[addr - MAIN_RAM[0]:addr - MAIN_RAM[0] + CHAR_STRIDE]
            slot_records["%ss%d" % (side, i)] = {
                "addr": hex(addr), "hex": rec.hex(),
                "hp_raw": struct.unpack_from("<H", rec, 0)[0],
                "chr_b": rec[0x29],
            }

    # Weight is not in the 0x50 slot record, in chr_b.bin, or in the pos
    # window (m03 + m03-analysis-fable.md ruled all three out). The remaining
    # candidates are the deeper per-entity structures pointed to at slot+0x1C
    # and slot+0x20 -- the same shape as the documented Luffy ability bitset,
    # which lives in a deeper entity rather than the slot. Snapshot them here
    # for the same reason as the slot records: per-character stats are
    # constant, so once at arm time costs nothing and needs no watch budget.
    entity_dumps = {}
    for name, rec_info in slot_records.items():
        rec = bytes.fromhex(rec_info["hex"])
        for off in (0x1C, 0x20):
            ptr = struct.unpack_from("<I", rec, off)[0]
            key = "%s+0x%02X" % (name, off)
            if not (MAIN_RAM[0] <= ptr < MAIN_RAM[1] - ENTITY_DUMP_LEN):
                entity_dumps[key] = {"ptr": hex(ptr), "hex": None,
                                     "skipped": "outside main RAM"}
                continue
            start = ptr - MAIN_RAM[0]
            entity_dumps[key] = {
                "ptr": hex(ptr),
                "hex": ram[start:start + ENTITY_DUMP_LEN].hex(),
            }

    jusemu("tail", "start", spec_path, "--out", log_path)
    meta = {
        "match": args.match, "started_unix": int(time.time()),
        "pos_base": hex(pos_base), "player_char_base": hex(player_base),
        "opp_char_base": hex(opp_base), "watches": watches,
        "slot_records_at_arm": slot_records,
        "entity_dumps_at_arm": entity_dumps,
        "positive_controls": controls, "expect_roster": expect,
        "units": {"position": "s32 8.8 fixed px at pos+0x00/+0x04 (P1), +0x40/+0x44 (opp)",
                  "hp": "u16 1/64 displayed at slot+0x00; chr_b idx u8 at +0x29",
                  "timer_sp": "1 byte each; addresses derived from char base "
                              "(-0x763 / +0x55D), drift-together assumption",
                  "slot_records_at_arm": "full 0x50 record per slot, hex, "
                                         "sampled once at arm time; the "
                                         "per-frame stream only carries 0x2C",
                  "entity_dumps_at_arm": "0x%X bytes at the pointers held in "
                                         "slot+0x1C and slot+0x20, per slot, "
                                         "sampled once at arm time; leading "
                                         "candidate location for weight"
                                         % ENTITY_DUMP_LEN},
    }
    json.dump(meta, open(os.path.join(OUT_DIR, args.match + ".meta.json"), "w"), indent=1)
    print("armed: %s" % log_path)
    print("controls: %s" % controls)
    print("PLAY NOW — then: capture_feel.py stop --match %s" % args.match)


def cmd_probe_pos(args):
    """Identify the live position block by watching every candidate move.

    Each candidate costs only 8 bytes of the 512 byte/frame watch budget (one
    X/Y pair), so all of them can be observed at once. The owner walks; exactly
    one candidate's X should change. Stale ring copies are frozen by
    definition, which is precisely what makes them indistinguishable from a
    live-but-idle block — so the owner MUST be moving while this runs.
    """
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tf:
        ram = dump_ram(tf.name)
    os.unlink(tf.name)
    cands = find_pos_array(ram)
    if not cands:
        raise SystemExit("no position-array candidates at all — is a battle on screen?")
    print("probing %d candidate(s): %s" % (len(cands), [hex(c) for c in cands]))
    watches = [{"name": "c%d" % i, "addr": c, "len": 8}
               for i, c in enumerate(cands)]
    spec = os.path.join(tempfile.gettempdir(), "jus_probe_pos.watches.json")
    log = os.path.join(tempfile.gettempdir(), "jus_probe_pos.jsonl")
    json.dump(watches, open(spec, "w"), indent=1)
    if os.path.exists(log):
        os.unlink(log)
    jusemu("tail", "start", spec, "--out", log)
    print("sampling %d s — THE OWNER MUST BE WALKING RIGHT NOW" % args.seconds)
    time.sleep(args.seconds)
    jusemu("tail", "stop")

    seen = [set() for _ in cands]
    rows = 0
    for line in open(log):
        try:
            v = json.loads(line)["v"]
        except ValueError:
            continue
        rows += 1
        for i in range(len(cands)):
            seen[i].add(struct.unpack_from("<i", bytes(v[i]), 0)[0])
    print("%d frames sampled\n" % rows)
    movers = []
    for i, c in enumerate(cands):
        n = len(seen[i])
        if n > 1:
            movers.append(c)
        xs = sorted(seen[i])
        print("  %-12s X distinct %4d  %s%s"
              % (hex(c), n,
                 "%.2f..%.2f" % (xs[0] / 256, xs[-1] / 256) if xs else "-",
                 "   <== MOVED" if n > 1 else ""))
    print()
    if len(movers) == 1:
        print("LIVE: %s" % hex(movers[0]))
        print("arm with: capture_feel.py start --match <m> --expect <r> "
              "--pos-base %s" % hex(movers[0]))
        return
    if not movers:
        raise SystemExit(
            "nothing moved. Either the owner was not walking, or the live block "
            "is absent from the candidate list (it can transiently fail the "
            "duplicated-at-+8 test). Reload the savestate and probe again.")
    raise SystemExit(
        "%d candidates moved: %s. Unexpected — do not guess between them; "
        "reload the savestate and probe again."
        % (len(movers), [hex(m) for m in movers]))


def cmd_stop(args):
    jusemu("tail", "stop")
    log_path = os.path.join(OUT_DIR, args.match + ".jsonl")
    if not os.path.exists(log_path) or os.path.getsize(log_path) == 0:
        raise SystemExit("no rows captured at %s" % log_path)
    n = sum(1 for _ in open(log_path))
    with open(log_path, "rb") as f, gzip.open(log_path + ".gz", "wb") as g:
        g.write(f.read())
    os.unlink(log_path)
    meta_path = os.path.join(OUT_DIR, args.match + ".meta.json")
    meta = json.load(open(meta_path))
    meta["stopped_unix"] = int(time.time())
    meta["rows"] = n
    json.dump(meta, open(meta_path, "w"), indent=1)
    print("captured %d frames -> %s.gz" % (n, log_path))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    st = sub.add_parser("start")
    st.add_argument("--match", required=True)
    st.add_argument("--expect", help="expected runtime chr_b roster, e.g. 67,68,32")
    st.add_argument("--pos-base", help="hex address of the live position block, "
                                      "as reported by probe-pos; skips the "
                                      "ambiguity refusal")
    pp = sub.add_parser("probe-pos", help="find the live position block by "
                                          "watching all candidates while the "
                                          "owner walks")
    pp.add_argument("--seconds", type=float, default=6.0)
    sp = sub.add_parser("stop")
    sp.add_argument("--match", required=True)
    args = ap.parse_args()
    if args.cmd == "start":
        cmd_start(args)
    elif args.cmd == "probe-pos":
        cmd_probe_pos(args)
    else:
        cmd_stop(args)


if __name__ == "__main__":
    main()
