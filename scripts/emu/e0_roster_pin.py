"""E0 roster pin: for every owner character-mapping state, read each side's roster (chr_b, HP, nature byte) and
the active fighter's authored collision-record base with the bytes at it.

    e0_roster_pin.py --mode offline --out DIR   read the states' saved RAM; no emulator
    e0_roster_pin.py --mode live    --out DIR   launch the emulator under JUS_EMU_HOLDER, load each state through the
                                                bridge, dump main RAM, read the same fields, stop the emulator

Both modes run the same extractor (`extract(ram)`) on a 4 MB main-RAM image, so a live row and an offline row of the
same state must be identical in every field the load does not move (validity.json compares them).

What a row holds (docs/research/knockback-record-pointer-per-hit.md:22-32,48-53; HP-And-Damage-Runtime-Findings.md):
  roster[side][slot]  rec = HP halfword (P1REC/P2REC + 0x50*slot); hp = u16[rec], hp_max = u16[rec-2],
                      koma = u16[rec-0x0C], active = u8[rec+0x25]&1, chr_b = u8[rec+0x29] (hp_addr+0x29),
                      nature_raw = u8[rec-5] (the battle struct's +0x13; struct base = rec-0x18, because chr_b is
                      char+0x41 = rec+0x29), tier_raw = u8[rec-7] (char+0x11)
  active[side]        obj = [FIGHTERS+4*side], M = [[obj+0x1A8]+0x10] (the ColPrm record),
                      base = [[M+0x6C]+0x0C]: the character's chr/col file as loaded in RAM (hit_records.py header);
                      base_hex = the first COL_DUMP bytes there (the longest col file is 1200 bytes)
"""
import argparse
import datetime
import gzip
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import fighter_layout as fl  # noqa: E402
import state_identity as si  # noqa: E402

MAIN_RAM = si.MAIN_RAM
RAM_SIZE = si.MAIN_RAM_SIZE
COL_DUMP = 0x500
SLOTS = 4
STATES_DIR = ROOT / 'jus_files' / 'save_states' / 'character-mappings'
IPC = Path(os.environ.get('JUS_EMU_DIR', '/tmp/jus_emu'))
LIVE_SLOT = 'e0pin-cur'
# The bridge's ack for a dummy-sidecar load (agent_bridge.lua abort_plan). Matched exactly, never by substring.
LOAD_NOT_SETTLED = 'state load did not settle (framecount never hit target)'


def in_ram(addr, n=1):
    return MAIN_RAM <= addr and addr + n <= MAIN_RAM + RAM_SIZE


class Ram:
    def __init__(self, ram):
        assert len(ram) == RAM_SIZE
        self.ram = ram

    def u(self, addr, n):
        if not in_ram(addr, n):
            raise ValueError(f'{addr:#x} outside main RAM')
        i = addr - MAIN_RAM
        return int.from_bytes(self.ram[i:i + n], 'little')

    def bytes(self, addr, n):
        if not in_ram(addr, 1):
            raise ValueError(f'{addr:#x} outside main RAM')
        i = addr - MAIN_RAM
        return self.ram[i:i + n]


def extract(ram_bytes):
    """One state's row from its main-RAM image. Never raises on a bad pointer: it records the failure."""
    m = Ram(ram_bytes)
    row = {'layout': None, 'sides': {}}
    try:
        row['layout'] = fl.detect_layout(lambda a, n: m.u(a, n))
    except Exception as e:  # noqa: BLE001 - recorded, not hidden
        row['layout_error'] = str(e)
        return row
    L = fl.LAYOUTS[row['layout']]
    for k, tag in ((0, 'p1'), (1, 'p2')):
        base_rec = L['P1REC'] if k == 0 else L['P2REC']
        slots = []
        for i in range(SLOTS):
            r = base_rec + 0x50 * i
            slots.append({'slot': i, 'rec': r, 'hp': m.u(r, 2), 'hp_max': m.u(r - 2, 2), 'koma': m.u(r - 0x0C, 2),
                          'flag24': m.u(r + 0x24, 1), 'flag25': m.u(r + 0x25, 1), 'active': m.u(r + 0x25, 1) & 1,
                          'chr_b': m.u(r + 0x29, 1), 'nature_raw': m.u(r - 5, 1), 'tier_raw': m.u(r - 7, 1)})
        side = {'roster': slots, 'active_slots': [s['slot'] for s in slots if s['active']]}
        act = {}
        try:
            obj = m.u(L['FIGHTERS'] + 4 * k, 4)
            act['obj'] = obj
            wrapper = m.u(obj + 0x1A8, 4)
            act['wrapper'] = wrapper
            M = m.u(wrapper + 0x10, 4)
            act['M'] = M
            x = m.u(M + 0x6C, 4)
            act['M_6c'] = x
            base = m.u(x + 0x0C, 4)
            act['base'] = base
            n = min(COL_DUMP, MAIN_RAM + RAM_SIZE - base) if in_ram(base) else 0
            act['base_hex'] = m.bytes(base, n).hex() if n > 0 else ''
            act['state'] = m.u(obj + 0x18, 1)
        except Exception as e:  # noqa: BLE001
            act['error'] = str(e)
        side['active'] = act
        row['sides'][tag] = side
    return row


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def manifest_states():
    man = json.loads((STATES_DIR / 'manifest.json').read_text())
    return [f for f in man['files'] if f['archive_path'].endswith('.mln.gz')]


def offline_ram(path):
    return si.mln_ram(Path(path).read_bytes())


def fc_of(client):
    hb = client._read_heartbeat() or {}
    return hb.get('framecount')


class Live:
    """The bridge session. Launch and stop go through launch_emu.sh and plain stop_emu.sh under our own holder."""

    def __init__(self, holder, scratch):
        self.holder = holder
        self.scratch = Path(scratch)
        self.env = dict(os.environ, JUS_EMU_HOLDER=holder)
        self.client = None
        self.info = {}

    def launch(self):
        hf = IPC / 'HOLDER'
        if hf.exists():
            raise SystemExit(f'HOLDER file exists: {hf.read_text()!r}; not launching')
        pg = subprocess.run(['pgrep', '-af', '^[^ ]*/melonDS( |$)'], capture_output=True, text=True)
        if pg.stdout.strip():
            raise SystemExit(f'a melonDS is running: {pg.stdout.strip()}; not launching')
        self.info['start'] = datetime.datetime.now().isoformat(timespec='seconds')
        p = subprocess.run(['bash', str(HERE / 'launch_emu.sh'), '--keep-ipc'], cwd=ROOT, env=self.env,
                           capture_output=True, text=True)
        self.info['launch_rc'] = p.returncode
        self.info['launch_out'] = (p.stdout + p.stderr)[-600:]
        if p.returncode != 0:
            raise SystemExit(f'launch_emu.sh exit {p.returncode}: {p.stdout}{p.stderr}')
        self.info['holder_file'] = (IPC / 'HOLDER').read_text().strip().splitlines()
        self.info['emu_pid'] = (IPC / 'emu.pid').read_text().strip()
        from jus_ipc import IpcClient
        self.client = IpcClient(str(IPC))

    def stop(self):
        p = subprocess.run(['bash', str(HERE / 'stop_emu.sh')], cwd=ROOT, env=self.env, capture_output=True, text=True)
        self.info['stop'] = datetime.datetime.now().isoformat(timespec='seconds')
        self.info['stop_out'] = (p.stdout + p.stderr).strip()[-300:]

    def cmd(self, op, args, timeout=30.0, allow=None):
        cid = self.client.publish_command(op, args)
        ack = self.client.wait_ack(cid, timeout=timeout)
        if not ack.get('ok', True) and not (allow is not None and ack.get('error') == allow):
            raise RuntimeError(f'{op}: {ack}')
        return ack

    def load_and_dump(self, mln_gz):
        """Stage the raw state under LIVE_SLOT (dummy sidecar, the a0.py import pattern), load it, dump main RAM."""
        states = IPC / 'states'
        raw = gzip.decompress(Path(mln_gz).read_bytes())
        tmp = states / f'{LIVE_SLOT}.mln.tmp'
        tmp.write_bytes(raw)
        os.replace(tmp, states / f'{LIVE_SLOT}.mln')
        (states / f'{LIVE_SLOT}.meta.json').write_text('{"framecount_at_save":0,"slot":"%s"}' % LIVE_SLOT)
        fc0 = fc_of(self.client)
        # The dummy sidecar names framecount 0, which a loaded state never reaches, so the bridge reports
        # LOAD_NOT_SETTLED after it has loaded the state (the a0.py import pattern, RESULTS.md "dummy load"). Accept
        # exactly that error string. This does not prove the requested state loaded: the layout read passes for any
        # valid battle layout. The proof is validity()'s live_rows_equal_offline_rows, checked by the bundle.
        ack = self.cmd('state_load', {'slot': LIVE_SLOT}, 120.0, allow=LOAD_NOT_SETTLED)
        time.sleep(0.4)
        out = self.scratch / 'ram.bin'
        self.cmd('dump', {'start': MAIN_RAM, 'end': MAIN_RAM + RAM_SIZE, 'outfile': str(out)}, 90.0)
        data = out.read_bytes()
        return data, {'load_ack_ok': ack.get('ok'), 'load_ack_error': ack.get('error'), 'fc_before_load': fc0, 'fc_after_dump': fc_of(self.client),
                      'raw_sha256': hashlib.sha256(raw).hexdigest()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--mode', choices=('offline', 'live'), required=True)
    ap.add_argument('--out', required=True, help='bundle directory (rows.<mode>.jsonl is written here)')
    ap.add_argument('--limit', type=int, default=0, help='only the first N states (smoke test)')
    ap.add_argument('--only', help='substring of the archive path')
    ap.add_argument('--holder', default=f'e0pin-{os.getpid()}')
    ap.add_argument('--scratch', default=os.path.join(tempfile.gettempdir(), 'e0pin-scratch'))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    scratch = Path(a.scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    states = manifest_states()
    if a.only:
        states = [s for s in states if a.only in s['archive_path']]
    if a.limit:
        states = states[:a.limit]
    live = None
    meta = {'mode': a.mode, 'states': len(states), 'holder': a.holder,
            'started': datetime.datetime.now().isoformat(timespec='seconds')}
    if a.mode == 'live':
        live = Live(a.holder, scratch)
        live.launch()
    rows_path = out / f'rows.{a.mode}.jsonl'
    try:
        with open(rows_path, 'w') as fo:
            for n, s in enumerate(states):
                gz = STATES_DIR / s['archive_path']
                rec = {'state': s['archive_path'], 'source_sha256': s['source_sha256'],
                       'archive_sha256': s['archive_sha256']}
                try:
                    if live:
                        ram, extra = live.load_and_dump(gz)
                        rec['live'] = extra
                    else:
                        ram = offline_ram(gz)
                    rec.update(extract(ram))
                except Exception as e:  # noqa: BLE001
                    rec['error'] = f'{type(e).__name__}: {e}'
                fo.write(json.dumps(rec) + '\n')
                fo.flush()
                print(n + 1, len(states), s['archive_path'], rec.get('layout'), rec.get('error', ''), flush=True)
    finally:
        if live:
            live.stop()
            meta.update(live.info)
    meta['finished'] = datetime.datetime.now().isoformat(timespec='seconds')
    (out / f'run.{a.mode}.json').write_text(json.dumps(meta, indent=1) + '\n')


if __name__ == '__main__':
    main()
