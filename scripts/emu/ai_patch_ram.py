#!/usr/bin/env python3
"""Patch the running AI in RAM so the change is visible immediately.

ov11 is loaded from ROM to RAM at 0x02172A60, so every code edit is a poke at the
virtual address itself -- no ROM rebuild, no file, nothing to clean up. The AI
profile is likewise already copied into RAM at [AI+0x2C] by the time a battle is
running, so the data edits poke that live copy rather than ai_param.bin.

REVERT BY RELOADING THE SAVESTATE. The tool refuses to write a patched ROM; the
on-disk ROM is never touched.

    # show what would change, change nothing
    python3 scripts/emu/ai_patch_ram.py --set pivot --show

    # apply and leave the emulator running so it can be watched
    python3 scripts/emu/ai_patch_ram.py --set pivot
    python3 scripts/emu/ai_patch_ram.py --set active
    python3 scripts/emu/ai_patch_ram.py --set react
    python3 scripts/emu/ai_patch_ram.py --set all

    # go back to stock
    python3 scripts/emu/ai_patch_ram.py --reload

Tiers
  pivot   ov11 0x0217ACE0  sub r0,r0,#5 -> #1
          The pivot computes max(0, difficulty-5) and is the ONLY gate that arms
          the 0x0C behaviour mode (0x0217AD30 is the only site in ov11 storing
          0x0C to AI+0x3A). At the observed difficulty 5 this moves the
          threshold index 0 -> 4, i.e. 25% -> 65%: a predicted 2.6x in arm
          events. Byte 0xE2400005 -> 0xE2400001.
  active  AI profile gate bytes -> table index 3 (50%)
          The probability gate at ov11 0x02179130 indexes a table at 0x0218190C
          = [64,76,102,128,166,179,217,243]; a profile byte >= 8 is
          unconditional. 91 of 160 live cells in the shipped archetypes are the
          lowest row, which is the mechanical reason the CPU looks passive. This
          raises them to index 3 and deliberately does NOT go to >= 8, because
          the gate arms its 30-tick cooldown only on failure, so "unconditional"
          also disarms the throttle.

          CAVEAT: the percentages above are thresholds/256, NOT measured
          probabilities. The roll field is written by only two sites in ov11 and
          the per-frame callback never refreshes it, so its distribution is
          unestablished. Reason about the threshold index, not the percentage.
          See cpu-ai-levels.md sections 3.2 and 3.10.
  react   ov11 0x0217FDB0  moveq r0,#0x5A -> #0x14   (90 -> 20 frames)
          ov11 0x0217E3E4  moveq r0,#0x1E -> #0x14   (30 -> 20 frames)
          These are failure-only lockouts: a single failed roll silences the
          reactive branch for 90 frames (~1.5 s). Shortening them cannot make the
          CPU choose a different branch, only reconsider sooner, so it cannot by
          itself cause careless attacks or self-KOs.
  idle_in_action_set
          ov11 0x021813D1  0xFF -> 0x00  and  0x021813D2  0x00 -> 0xFF
          The state guard at 0x0217BFE0 scans the byte table at 0x021813CC =
          {9,10,11,12,26,-1} and returns 1 only when a fighter's own state code
          is in it. 9/10 are attacks, 11 a dream attack, 12 a SELECT ultimate,
          and 26 is unanchored. So this is an ATTACK-FAMILY state test, not a
          general "can act" test. The patch adds "idle" (0) to the accepted set
          and moves the terminator one byte along, so an idle fighter now reads
          as if it were in that family.

          BLUNT, and the only lever the A/B found that works. It has 17 callers
          and they use the two results with BOTH polarities -- step 4 and step 5
          leave the phase alone on 1 and reset it on 0, while step 11 goes to
          phase 4 on 1 and leaves on 0. So this is not "idle now escapes"; it is
          a redistribution of which branch every gate takes. Measured on the
          freeze fixture: the fight diverges from stock at fc 32760, 749 frames
          before the freeze point, and the freeze never occurs -- 834 attack
          frames where stock has none, and the opponent is launched into states
          8/23/24/25. The surgical alternative (NOP-ing the finalizer's early
          return at 0x0217A974) is inert. See cpu-ai-levels.md 3.25 and 3.26.

          The ROM equivalent is the two bytes at 0x001E6771 and 0x001E6772.
  all     pivot + react. Deliberately does NOT include idle_in_action_set: it is
          a different concern and mixes badly with the aggression tiers.

Addresses are derived at runtime, never hardcoded for the profile.
"""
from __future__ import annotations

import argparse
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EMU = REPO / 'scripts' / 'emu'
sys.path.insert(0, str(EMU))

from jus_ipc import DEFAULT_DIR, BridgeState, IpcClient  # noqa: E402

ANCHOR = 0x02172960
AI_MGR_OFF = 0x128
SLOT0_OFF = 0xA8
STRIDE = 0x10C
MAIN_RAM = (0x02000000, 0x02400000)

# ov11 load base; its virtual address IS the RAM address once resident.
OV11_BASE = 0x02172A60
OV11_FILE = REPO / 'jus_files' / 'arm9' / 'overlays' / 'arm9_ov11.bin'

# name -> (ov11 virtual address, expected original word, patched word, human note)
CODE_EDITS = {
    'pivot': (0x0217ACE0, 0xE2400005, 0xE2400001,
              'sub r0,r0,#5 -> #1   (arming roll 25% -> 65% at difficulty 5)'),
    'gate':  (0x02179130, 0xE351001B, 0xE3510019,
              'cmp r1,#0x1B -> #0x19  (revives the dead 0x1A call site)'),
    'react90': (0x0217FDB0, 0x03A0005A, 0x03A00014,
                'moveq r0,#90 -> #20  (failed-roll lockout, frames)'),
    'react30': (0x0217E3E4, 0x03A0001E, 0x03A00014,
                'moveq r0,#30 -> #20  (failed-roll lockout, frames)'),
    # A four-byte window so the pre-image check covers the whole table tail, not
    # just the byte being changed. Only the middle two bytes move:
    #   1A FF 00 00  ->  1A 00 FF 00
    'idle_in_action_set': (0x021813D0, 0x0000FF1A, 0x00FF001A,
                           'guard table 0x021813CC: terminator -> accepted state 0, '
                           'old successor byte -> new terminator'),
}

# Profile bytes the probability gate is asked about, from the direct
# 'bl 0x02179130' call sites. 0x1A is dead in the stock ROM because the gate
# early-outs for any index <= 0x1B.
LIVE_PARAMS = [0x1C, 0x1D, 0x1F, 0x21, 0x22, 0x23, 0x24, 0x25]
TABLE_INDEX = 3          # 128/256 = 50%

TIERS = {
    'pivot':  ['pivot'],
    'gate':   ['gate'],
    'react':  ['react90', 'react30'],
    'active': [],          # data-only, no code edits
    'idle_in_action_set': ['idle_in_action_set'],
    'all':    ['pivot', 'react90', 'react30'],
}


def say(*a):
    print(*a, flush=True)


def read_holder() -> str | None:
    """Name of whoever holds the emulator, or None when unheld."""
    try:
        first = Path(DEFAULT_DIR, 'HOLDER').read_text().splitlines()[:1]
    except OSError:
        return None
    return first[0].strip() if first and first[0].strip() else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--state', default='pc-kakashi-npc-jotaro-fightcpu')
    ap.add_argument('--set', choices=sorted(TIERS), help='apply this tier in RAM')
    ap.add_argument('--reload', action='store_true', help='revert to stock by reloading')
    ap.add_argument('--show', action='store_true', help='report diffs, change nothing')
    ap.add_argument('--keep-running', action='store_true', default=True,
                    help='leave the emulator up (default)')
    ap.add_argument('--stop', action='store_true', help='shut the emulator down after')
    ap.add_argument('--holder', default=None)
    args = ap.parse_args()

    if not (args.set or args.reload or args.show):
        ap.error('one of --set / --reload / --show is required')

    holder = args.holder or f'ai-patch-{os.getpid()}'
    os.environ['JUS_EMU_HOLDER'] = holder
    # --show reports on a battle that is ALREADY resident, so it must not
    # launch: launch_emu.sh kills every melonDS and wipes the IPC dir, and a
    # fresh boot has no battle, so there would be nothing left to report on.
    want_emulator = bool(args.set or args.reload) and not args.show

    c = IpcClient(DEFAULT_DIR)
    if want_emulator:
        bstate, _hb = c.state()
        if bstate in (BridgeState.IDLE, BridgeState.PLAN_RUNNING):
            holder = read_holder() or holder
            say(f'== attaching to the live emulator (holder "{holder}") ==')
            say('   it is already up, so nothing was launched or killed.')
        else:
            say(f'== launching emulator (holder {holder}) ==')
            r = subprocess.run(['bash', str(EMU / 'launch_emu.sh')],
                               env=dict(os.environ, JUS_EMU_HOLDER=holder),
                               capture_output=True, text=True)
            if r.returncode != 0:
                say('LAUNCH FAILED rc=%d' % r.returncode)
                say(r.stderr.strip()[-1500:])
                return 2
            say('   up.')
            # A relaunch starts a fresh bridge with a new session id, so the
            # client must be rebuilt or every command is rejected as stale.
            c = IpcClient(DEFAULT_DIR)

    def poke(addr, data: bytes):
        a = c.wait_ack(c.publish_command('poke', {'addr': addr, 'bytes': list(data)}), 10.0)
        if not a.get('ok'):
            raise SystemExit('poke 0x%08X failed: %s' % (addr, a.get('error')))

    def peek(addr, ln=4):
        a = c.wait_ack(c.publish_command('peek', {'addr': addr, 'len': ln}), 10.0)
        if not a.get('ok'):
            raise SystemExit('peek 0x%08X failed: %s' % (addr, a.get('error')))
        v = a['result']['value']
        return v if isinstance(v, int) else int.from_bytes(bytes(v), 'little')

    if args.reload:
        say(f'== reloading {args.state} (this discards any RAM patch) ==')
        c.wait_ack(c.publish_command('state_load', {'slot': args.state}), 60.0)
        time.sleep(0.5)
        say('   back to stock.')
        return 0

    # ---- resolve the live AI slots -------------------------------------
    say('== resolving AI slots ==')
    root = peek(ANCHOR)
    if not (MAIN_RAM[0] <= root < MAIN_RAM[1]):
        say('   battle root 0x%08X is not a main-RAM pointer; is a battle loaded?' % root)
        return 3
    mgr = peek(root + AI_MGR_OFF)
    say(f'   root 0x{root:08X}  mgr 0x{mgr:08X}')

    slots = []
    for i in range(4):
        base = mgr + SLOT0_OFF + i * STRIDE
        d4 = peek(base + 0xD4)
        if (d4 >> 28) & 0xF == i:
            slots.append((i, base))
            say(f'   slot {i}: 0x{base:08X}  identity OK (0xD4=0x{d4:08X})')
    if not slots:
        say('   no live AI slots')
        return 3

    # ---- what would change --------------------------------------------
    edits: list[tuple[str, int, bytes, bytes]] = []
    if args.set:
        for key in TIERS[args.set]:
            addr, exp, new, note = CODE_EDITS[key]
            edits.append((note, addr, struct.pack('<I', exp), struct.pack('<I', new)))

    if args.set in ('active', 'all'):
        for i, base in slots:
            prof = peek(base + 0x2C)
            for off in LIVE_PARAMS:
                cur = peek(prof + off, 1)
                if cur < 8 and cur != TABLE_INDEX:
                    edits.append((f'profile 0x{prof:08X} slot {i} +0x{off:02X} '
                                  f'{cur} -> {TABLE_INDEX}',
                                  prof + off, bytes([cur]), bytes([TABLE_INDEX])))

    say(f'\n== {len(edits)} byte edit(s) ==')
    for note, addr, before, after in edits:
        say(f'   0x{addr:08X}  {before.hex(" ")} -> {after.hex(" ")}   {note}')

    if not edits:
        say('   nothing to do (already at target, or tier has no edits)')
        if args.stop:
            subprocess.run(['bash', str(EMU / 'stop_emu.sh')], env=dict(os.environ),
                           capture_output=True)
        return 0

    if args.show:
        say('\n   --show: nothing was written.')
        return 0

    # ---- apply ---------------------------------------------------------
    for note, addr, before, after in edits:
        cur = peek(addr, len(before))
        want = int.from_bytes(before, 'little')
        if cur != want:
            say(f'   REFUSING 0x{addr:08X}: live value 0x{cur:X} != expected 0x{want:X}'
                ' (already patched? or wrong build?)')
            return 4
    for _note, addr, _b, after in edits:
        poke(addr, after)
    say(f'\n   wrote {len(edits)} edit(s) to live RAM.')

    say('\n== verifying ==')
    for note, addr, before, after in edits:
        now = peek(addr, len(after))
        ok = now == int.from_bytes(after, 'little')
        say(f'   0x{addr:08X} now 0x{now:X} {"ok" if ok else "MISMATCH"}   {note}')

    say(f'\nThe emulator is still running under holder "{holder}".')
    say('Play and watch. To go back to stock:')
    say(f'   JUS_EMU_HOLDER={holder} python3 scripts/emu/ai_patch_ram.py --reload')
    say('To shut it down:')
    say(f'   JUS_EMU_HOLDER={holder} bash scripts/emu/stop_emu.sh')

    if args.stop:
        subprocess.run(['bash', str(EMU / 'stop_emu.sh')], env=dict(os.environ),
                       capture_output=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
