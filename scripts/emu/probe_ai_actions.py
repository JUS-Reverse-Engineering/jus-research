#!/usr/bin/env python3
"""Per-frame battle-AI probe: is AI action 8 ever reached?

Answers the question filed as tracker item jus-9na3. That tracker item reasoned that the
behaviour selector AI+0x3A == 0xC routes to action 8, but that no store of 8 to
AI+0xA0 exists in ov11, so the pivot patch in
docs/research/side-quests/cpu-ai-levels.md may be a no-op.

THAT REASONING IS BUILT ON A WRONG OFFSET, and this probe shows it. The action-id
field is AI+0x39, not AI+0xA0. In ov11 the 0x3A==0xC route stores 8 to +0x39
(0x0217BAD0/0x0217BAD4), and the default arm stores 4 to +0x39
(0x0217BADC/0x0217BAE0). A live capture saw +0x39 == 8, always with +0x3A ==
0x0C, while +0xA0 never left 0. See the FIELDS comment below for the
disassembly and the runtime counts.

READ-ONLY. It never pokes RAM and never presses a button during the capture, so
the CPU acts exactly as it would in an offline match.

Address derivation (runtime, chain-based -- do NOT hardcode; see the
battle-root-moves-with-rule-mode gotcha):

    root      = [0x02172960]                  ov6 BSS pointer, 0 outside a battle
    mgr       = [root + 0x128]                the AI manager
    AI[i]     = [mgr + 0xA8 + i*0x10C]        four inline 0x10C slots
    node      = [AI[i] + 0x20]                current action node
    state     = [node + 0x18]                 the byte action 8 polls against 0x0C

Slot identity is self-checking: 0x02172D9C stamps the slot index into the top
nibble of AI+0xD4, so u32(AI[i]+0xD4) >> 28 must equal i.

Usage:
    python3 probe_ai_actions.py --state pc-kakashi-npc-jotaro-fightcpu --seconds 20
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EMU = REPO / 'scripts' / 'emu'
sys.path.insert(0, str(EMU))

from jus_ipc import DEFAULT_DIR, IpcClient  # noqa: E402
from jus_plan import plan_to_lua, validate_plan  # noqa: E402

ANCHOR = 0x02172960
AI_MGR_OFF = 0x128
SLOT0_OFF = 0xA8
STRIDE = 0x10C
N_SLOTS = 4

# Per-slot byte fields we log every frame.
#
# CORRECTION (2026-09-26, from a live capture + disassembly of ov11):
# +0xA0 is NOT the action-id field. The action id lives at +0x39. Proof from
# ov11, the 0x3A==0xC route itself:
#     0217BA88  ldrb r0, [r5, #0x3a]
#     0217BA8C  cmp  r0, #0xc
#     0217BA90  bne  #0x217badc
#     ...
#     0217BAD0  mov  r0, #8
#     0217BAD4  strb r0, [r5, #0x39]     <-- the store of 8, to +0x39
# and the default arm two instructions later:
#     0217BADC  mov  r0, #4
#     0217BAE0  strb r0, [r5, #0x39]
# A live 20s capture saw +0x39 == 8 for 4 frames, all with +0x3A == 0x0C, and
# +0x39 == 8 never occurred with any other +0x3A value. Meanwhile +0xA0 stayed
# 0 for all 1208 frames. So conclusions drawn from +0xA0 (tracker item jus-9na3) watched
# the wrong field. +0xA0 is a different, state-gated field: its 6 ov11 stores
# write 0/1/2/3 and are guarded on the character's [node+0x18] == 0x10.
FIELDS = [
    ('act', 0x39, 1),   # ACTION ID -- the question: does 8 ever appear?
    ('b3a', 0x3A, 1),   # behaviour selector (+0x3A == 0x0C routes action 8)
    ('b3b', 0x3B, 1),   # one-step lookahead id
    ('xA0', 0xA0, 1),   # NOT the action id; state-gated, stores 0/1/2/3
    ('a1', 0xA1, 1),    # phase
    ('a2', 0xA2, 1),    # lockout countdown
    ('ac', 0xAC, 1),    # sub-action selector
    ('ad', 0xAD, 1),    # step counter
    ('f104', 0x104, 1),  # difficulty
    ('f105', 0x105, 1),  # behaviour selector (does 9 ever appear?)
    ('st18', None, 1),  # [node+0x18], the byte action 8 polls vs 0x0C
]

MAIN_RAM = (0x02000000, 0x02400000)


def sane(p, what):
    if not (MAIN_RAM[0] <= p < MAIN_RAM[1]) or p % 4:
        raise SystemExit(f'{what} = 0x{p:08X} is not a main-RAM pointer')
    return p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--state', default='pc-kakashi-npc-jotaro-fightcpu')
    ap.add_argument('--seconds', type=float, default=20.0)
    ap.add_argument('--holder', default=None, help='JUS_EMU_HOLDER; default unique')
    ap.add_argument('--out', type=Path, default=REPO / 'jus_files' / 'captures' / 'ai_actions')
    ap.add_argument('--skip-launch', action='store_true',
                    help='an emulator is already up and this holder owns it')
    args = ap.parse_args()

    holder = args.holder or f'ai-probe-{os.getpid()}'
    os.environ['JUS_EMU_HOLDER'] = holder
    args.out.mkdir(parents=True, exist_ok=True)

    def say(*a):
        print(*a, flush=True)

    if not args.skip_launch:
        say(f'== launching emulator (holder {holder}) ==')
        r = subprocess.run(['bash', str(EMU / 'launch_emu.sh')],
                           env=dict(os.environ, JUS_EMU_HOLDER=holder),
                           capture_output=True, text=True)
        say(r.stdout.strip()[-2000:])
        if r.returncode != 0:
            say('LAUNCH FAILED rc=%d' % r.returncode)
            say(r.stderr.strip()[-2000:])
            return 2

    c = IpcClient(DEFAULT_DIR)

    say(f'== loading savestate {args.state} ==')
    # The bridge reads cmd.args.slot (agent_bridge.lua:426), NOT 'state'.
    # Sending 'state' leaves slot nil, and the bridge's own no-sidecar error
    # path does `slot ..` -- which raises on nil, so the bridge throws before
    # acking and the client times out instead of getting a clean error.
    ack = c.wait_ack(c.publish_command('state_load', {'slot': args.state}), 60.0)
    say('   ack ok=%s %s' % (ack.get('ok'), str(ack.get('error'))[:200]))
    if not ack.get('ok'):
        say('STATE LOAD FAILED -- aborting rather than probing a stale ROM state')
        return 7

    # Gotcha: never treat a single post-load read as data. Advance >=10 frames.
    time.sleep(0.5)

    # ov11 hosts every AI address used below. This MUST be measured AFTER the
    # state load: sampled before it, it describes the boot screen instead, which
    # once made this probe record "ov11 1.8% -- not resident" for a capture in
    # which the AI demonstrably ran. Measured at the loaded state it is 100%.
    try:
        res = subprocess.run([sys.executable, str(EMU / 'overlay_residency.py'),
                              '--label', 'battle'], capture_output=True, text=True)
        say('== overlay residency (at the loaded state) ==')
        say(res.stdout.strip()[-1500:])
        ov11 = res.stdout
        if 'ov11' not in res.stdout:
            say('   could not read an ov11 line; treating residency as UNKNOWN')
        elif '%' not in res.stdout.split('ov11')[1][:12]:
            say('   could not parse an ov11 percentage')
        else:
            pct = float(res.stdout.split('ov11')[1].split('%')[0])
            if pct < 99.0:
                say(f'   ABORT: ov11 only {pct}% resident -- these addresses are meaningless')
                return 7
    except Exception as e:  # noqa: BLE001
        ov11 = f'(residency check failed: {e})'
        say('   residency UNKNOWN -- continuing, but treat addresses as unproven')

    def peek(addr, ln=4):
        a = c.wait_ack(c.publish_command('peek', {'addr': addr, 'len': ln}), 10.0)
        if not a.get('ok'):
            raise SystemExit('peek 0x%08X failed: %s' % (addr, a.get('error')))
        return a['result']['value']

    say('== deriving AI slots ==')
    root = sane(peek(ANCHOR), 'battle root')
    mgr = sane(peek(root + AI_MGR_OFF), 'AI manager')
    say(f'   root     = 0x{root:08X}')
    say(f'   mgr      = 0x{mgr:08X}')

    slots = []
    for i in range(N_SLOTS):
        base = mgr + SLOT0_OFF + i * STRIDE
        try:
            d4 = peek(base + 0xD4)
        except SystemExit:
            say(f'   slot {i}: unreadable, skipped')
            continue
        stamped = (d4 >> 28) & 0xF
        if stamped != i:
            say(f'   slot {i}: not constructed (0xD4=0x{d4:08X}, stamped {stamped}) -- skipped')
            continue
        slots.append((i, base, d4))
        say(f'   slot {i}: base 0x{base:08X}  0xD4=0x{d4:08X}  identity OK')

    if not slots:
        say('NO LIVE AI SLOTS -- the battle has no AI manager. Aborting.')
        return 3

    # Name the CPU: [AI+0x20]+0x1A8 vs root+0x0DC (player) / +0x0E0 (opponent).
    p1_obj = peek(root + 0x0DC)
    p2_obj = peek(root + 0x0E0)
    say(f'   player battleObj  = 0x{p1_obj:08X}')
    say(f'   opponent battleObj= 0x{p2_obj:08X}')
    for i, base, _d4 in slots:
        node = sane(peek(base + 0x20), f'slot {i} node')
        say(f'   slot {i} node=0x{node:08X}')

    # Build an ABSOLUTE watch spec: chain depth is capped at 3, and the
    # node->+0x18 hop needs a 4th, so resolve node pointers once and watch
    # them directly for the per-frame phase.
    specs = []
    for i, base, _d4 in slots:
        node = peek(base + 0x20)
        for name, off, ln in FIELDS:
            addr = (node + 0x18) if off is None else (base + off)
            specs.append({'name': f'ai{i}.{name}', 'addr': addr, 'len': ln})
    total = sum(s['len'] for s in specs)
    say(f'== {len(specs)} watches, {total} bytes/frame (budget 512) ==')
    if len(specs) > 32 or total > 512:
        say('WATCH BUDGET EXCEEDED -- aborting rather than logging garbage')
        return 4

    spec_path = args.out / 'watches.json'
    log_path = args.out / 'tail.jsonl'
    meta_path = args.out / 'meta.json'
    spec_path.write_text(json.dumps(specs, indent=1))

    say('== one warm-up plan (bridge-skip mitigation, per standing rules) ==')
    warm = {'name': 'ai-probe-warmup',
            'segments': [{'from': 0, 'to': 30, 'buttons': []}],
            'tail_frames': 30}
    # run_plan takes a plan FILE PATH + run_dir, not an inline table
    # (agent_bridge.lua:415). Passing an inline dict leaves plan_path nil and
    # load_plan_file(nil) raises inside an un-pcall'd call, so the bridge never
    # acks and we hang for the full timeout. Same failure shape as state_load.
    run_dir = Path(c.dir) / 'runs' / f'ai-probe-warmup-{c.next_id()}'
    run_dir.mkdir(parents=True, exist_ok=True)
    plan_path = run_dir / 'plan.lua'
    plan_path.write_text(plan_to_lua(validate_plan(warm)))
    ack = c.wait_ack(c.publish_command(
        'run_plan', {'plan_path': str(plan_path), 'run_dir': str(run_dir)}), 60.0)
    say('   warm-up ack ok=%s %s' % (ack.get('ok'), str(ack.get('error'))[:200]))
    if not ack.get('ok'):
        say('WARM-UP PLAN FAILED -- aborting')
        return 8

    say(f'== tail capture for {args.seconds:.0f}s ==')
    ack = c.wait_ack(c.publish_command(
        'tail_start', {'specs': specs, 'out': str(log_path), 'every': 1}), 15.0)
    say('   tail_start ok=%s %s' % (ack.get('ok'), str(ack.get('error'))[:200]))
    if not ack.get('ok'):
        return 5

    time.sleep(args.seconds)

    ack = c.wait_ack(c.publish_command('tail_stop', {}), 20.0)
    say('   tail_stop ok=%s dropped=%s' % (ack.get('ok'), ack.get('result', {}).get('dropped')))

    rows = [json.loads(x) for x in log_path.read_text().splitlines() if x.strip()]
    if not rows:
        say('NO ROWS CAPTURED')
        return 6

    # The bridge reports the LATE row of each dropped span. The frames that were
    # never read are the ones in between, so report both.
    late_gap_rows = [r['fc'] for r in rows if r.get('elapsed', 1) != 1]
    skipped: list[int] = []
    for r in rows:
        n = r.get('elapsed', 1)
        if n > 1:
            skipped.extend(range(r['fc'] - (n - 1), r['fc']))
    say(f'== {len(rows)} rows, {len(late_gap_rows)} with elapsed != 1, '
        f'{len(skipped)} frames never read: {skipped} ==')

    # Map spec order back to values.
    names = [s['name'] for s in specs]
    cols = {n: [] for n in names}
    for r in rows:
        for n, v in zip(names, r['v']):
            cols[n].append(v)

    def hist(name):
        c_ = Counter(cols[name])
        return ', '.join(f'{k}:{v}' for k, v in sorted(c_.items(), key=lambda kv: -kv[1])[:12])

    say('\n===== per-field value histograms =====')
    for n in names:
        say(f'  {n:12s} {hist(n)}')

    def ever(name, val):
        return sum(1 for v in cols[name] if v == val)

    say('\n===== THE QUESTIONS =====')
    a8 = sum(ever(f'ai{i}.act', 8) for i, _b, _d in slots)
    say(f'  frames with action id 8 (+0x39)     : {a8}')
    say(f'  distinct action ids seen (+0x39)   : '
        f'{sorted(set(v for i, _b, _d in slots for v in cols[f"ai{i}.act"]))}')
    say(f'  frames with +0xA0 != 0            : '
        f'{sum(1 for i, _b, _d in slots for v in cols[f"ai{i}.xA0"] if v != 0)}')
    say(f'  frames with +0x105 == 9            : {sum(ever(f"ai{i}.f105", 9) for i, _b, _d in slots)}')
    say(f'  frames with +0x3A == 0x0C          : {sum(ever(f"ai{i}.b3a", 0x0C) for i, _b, _d in slots)}')
    say(f'  frames with node+0x18 == 0x0C      : {sum(ever(f"ai{i}.st18", 0x0C) for i, _b, _d in slots)}')
    say(f'  distinct +0x3A values             : '
        f'{sorted(set(v for i, _b, _d in slots for v in cols[f"ai{i}.b3a"]))}')
    say(f'  distinct node+0x18 values          : '
        f'{sorted(set(v for i, _b, _d in slots for v in cols[f"ai{i}.st18"]))}')
    say(f'  distinct +0x105 values             : '
        f'{sorted(set(v for i, _b, _d in slots for v in cols[f"ai{i}.f105"]))}')
    say(f'  difficulty values                  : '
        f'{sorted(set(v for i, _b, _d in slots for v in cols[f"ai{i}.f104"]))}')

    # The money question: when the pivot's behaviour fires, what action results?
    say('\n===== pivot correlation: rows where +0x3A == 0x0C =====')
    for i, _b, _d in slots:
        pairs = Counter()
        n = 0
        for k in range(len(rows)):
            if cols[f'ai{i}.b3a'][k] == 0x0C:
                n += 1
                pairs[cols[f'ai{i}.act'][k]] += 1
        if n:
            say(f'  slot {i}: {n} rows, resulting action ids: {dict(sorted(pairs.items()))}')
        else:
            say(f'  slot {i}: +0x3A never reached 0x0C in this capture')
        # The converse: is action 8 ever seen with a +0x3A that is NOT 0x0C?
        elsewhere = sum(1 for k in range(len(rows))
                        if cols[f'ai{i}.act'][k] == 8 and cols[f'ai{i}.b3a'][k] != 0x0C)
        say(f'  slot {i}: action 8 with +0x3A != 0x0C: {elsewhere} rows')

    meta = {
        'state': args.state,
        'holder': holder,
        'rows': len(rows),
        'gap_rows': len(late_gap_rows),
        'late_gap_rows': late_gap_rows[:50],
        'skipped_frames': skipped,
        'seconds': args.seconds,
        'root': hex(root),
        'ai_manager': hex(mgr),
        'slots': [{'index': i, 'base': hex(b), 'd4': hex(d)} for i, b, d in slots],
        'player_battle_obj': hex(p1_obj),
        'opponent_battle_obj': hex(p2_obj),
        'ov11_residency': ov11,
        'watches': specs,
        'histograms': {n: dict(Counter(cols[n])) for n in names},
        'answers': {
            'action8_frames': a8,
            'action_ids_seen': sorted(set(v for i, _b, _d in slots for v in cols[f'ai{i}.act'])),
            'action8_with_other_b3a': sum(
                1 for i, _b, _d in slots for k in range(len(rows))
                if cols[f'ai{i}.act'][k] == 8 and cols[f'ai{i}.b3a'][k] != 0x0C),
            'a0_nonzero_frames': sum(1 for i, _b, _d in slots
                                     for v in cols[f'ai{i}.xA0'] if v != 0),
            'f105_nine_frames': sum(ever(f'ai{i}.f105', 9) for i, _b, _d in slots),
            'b3a_0x0c_frames': sum(ever(f'ai{i}.b3a', 0x0C) for i, _b, _d in slots),
            'st18_0x0c_frames': sum(ever(f'ai{i}.st18', 0x0C) for i, _b, _d in slots),
            'difficulty_seen': sorted(set(v for i, _b, _d in slots for v in cols[f'ai{i}.f104'])),
        },
    }
    meta_path.write_text(json.dumps(meta, indent=1, default=str))
    say(f'\nmeta -> {meta_path}')
    say(f'raw  -> {log_path}  (not committed, per precedent)')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    finally:
        if os.environ.get('JUS_EMU_HOLDER'):
            subprocess.run(['bash', str(EMU / 'stop_emu.sh')],
                           env=dict(os.environ), capture_output=True, text=True)
