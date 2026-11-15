#!/usr/bin/env python3
"""Runner-owned emulator lease with heartbeat and fenced takeover.

Standalone (stdlib only) so launch_emu.sh / stop_emu.sh can run it directly:
  python3 lease.py status
  python3 lease.py release --token T
  python3 lease.py guard [--token T --epoch E] [--locked]
                                          # exit 0 ok, 6 refused (used by the shell scripts)

State lives in the IPC dir ($JUS_EMU_DIR, default /tmp/jus_emu):
  LEASE.json   the current lease, replaced only by atomic rename
  LEASE.epoch  highest epoch ever issued (epochs never go backwards, even after release)
  .lock        THE operation lock (flock). One lock, so there is no lock order to get wrong:
               lease transitions (acquire/takeover/release/heartbeat/legacy recovery) and the
               shell emulator effects (launch_emu.sh, stop_emu.sh, HOLDER publication) all
               serialise on it. Shell callers take it, then re-validate their authority
               (guard --locked, which must not lock again) and keep it through the effect, so
               a takeover waits for an in-progress effect and an effect that waited sees the
               post-takeover lease and is refused.

A lease records: token, epoch, pid, start (the /proc start token, field 22, the same
identity HOLDER line 4 uses), campaign, trial_index, heartbeat_ts, acquired_ts,
heartbeat_mono, boot_id, stale_after, took_over.

Takeover (acquire over an existing lease) is allowed only when the holder is provably
dead (different boot, pid gone, zombie, or start token mismatch = pid reuse) or its
same-boot monotonic heartbeat age exceeds stale_after with nonnegative wall age.
It always bumps the epoch. The old holder is fenced:
assert_current(), heartbeat() and release() raise LeaseFenced once its token/epoch is no
longer the file's. Call assert_current() before every emulator-touching operation.
Shell authority is the pair (JUS_EMU_LEASE_TOKEN, JUS_EMU_LEASE_EPOCH) as issued by
acquire (Lease.env()); both must equal the current lease, so reusing a token across epochs
does not revive an old shell environment.
Remaining gap: a Python holder that checks assert_current() and then acts is not covered by
the lock. The stale threshold does NOT bound that window (a suspended process may resume at
any time); only the shell effects are serialised with takeover. Legacy (tokenless) recovery
of a stale or dead lease is itself a fenced transition (epoch bump, lease retired).
"""

import argparse
import fcntl
import json
import math
import os
from pathlib import Path
import sys
import time
import uuid

DEFAULT_STALE_AFTER = 120.0
EXIT_REFUSED = 6


class LeaseError(Exception):
    pass


class LeaseHeld(LeaseError):
    """Another live holder with a fresh heartbeat owns the lease."""


class LeaseFenced(LeaseError):
    """This holder's token/epoch is no longer the current lease."""


def ipc_root(ipc_dir=None):
    return Path(ipc_dir or os.environ.get('JUS_EMU_DIR') or '/tmp/jus_emu')


def proc_start(pid):
    """Process start identity (/proc stat field 22), None if the pid is gone or a zombie."""
    try:
        rest = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    except (OSError, IndexError):
        return None
    if rest[0] == 'Z':
        return None
    return rest[19]


def _lease_path(root):
    return root / 'LEASE.json'


def _atomic_write(path, text):
    tmp = path.with_name(f'{path.name}.tmp.{os.getpid()}')
    with open(tmp, 'w') as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    dfd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)


def _boot_id():
    try:
        return Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    except OSError as e:
        raise LeaseError(f'cannot read boot id from /proc ({e}); refusing to lease without it') from e


def _valid(d):
    if not isinstance(d, dict) or d.keys() != {
            'token', 'epoch', 'pid', 'start', 'campaign', 'trial_index',
            'heartbeat_ts', 'acquired_ts', 'stale_after', 'took_over',
            'heartbeat_mono', 'boot_id'}:
        return False
    if any(type(d[k]) is not str or not d[k] for k in ('token', 'start', 'campaign', 'boot_id')):
        return False
    try:
        uuid.UUID(d['boot_id'])
    except ValueError:
        return False
    if not d['start'].isascii() or not d['start'].isdigit():
        return False
    if any(type(d[k]) is not int or d[k] < 1 for k in ('epoch', 'pid')):
        return False
    if d['trial_index'] is not None and (type(d['trial_index']) is not int or d['trial_index'] < 0):
        return False
    for k in ('heartbeat_ts', 'acquired_ts', 'stale_after', 'heartbeat_mono'):
        if type(d[k]) not in (int, float):
            return False
        try:
            if not math.isfinite(d[k]):
                return False
        except OverflowError:
            return False
    return (d['stale_after'] > 0 and d['heartbeat_mono'] >= 0
            and (d['took_over'] is None or
                 type(d['took_over']) is str and d['took_over'] in ('stale', 'dead')))


def _read(root):
    """Return the lease dict, None if absent, or the string 'corrupt'."""
    try:
        text = _lease_path(root).read_text()
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError):
        return 'corrupt'
    try:
        d = json.loads(text)
        if not _valid(d):
            return 'corrupt'
        return d
    except ValueError:
        return 'corrupt'


def _last_epoch(root, d):
    n = d['epoch'] if isinstance(d, dict) else 0
    try:
        n = max(n, int((root / 'LEASE.epoch').read_text().strip()))
    except (OSError, ValueError):
        pass
    return n


class _Lock:
    def __init__(self, root):
        root.mkdir(parents=True, exist_ok=True)
        self.f = open(root / '.lock', 'a')

    def __enter__(self):
        fcntl.flock(self.f, fcntl.LOCK_EX)
        return self

    def __exit__(self, *exc):
        self.f.close()


def _classify(d, now=None):
    """free | held | stale | dead | corrupt for a lease dict read from disk."""
    if d is None:
        return 'free'
    if d == 'corrupt':
        return 'corrupt'
    if d['boot_id'] != _boot_id() or proc_start(d['pid']) != d['start']:
        return 'dead'
    age = (time.time() if now is None else now) - d['heartbeat_ts']
    elapsed = time.monotonic() - d['heartbeat_mono']
    if age >= 0 and elapsed > d['stale_after']:
        return 'stale'
    return 'held'


class Lease:
    def __init__(self, root, token, epoch):
        self.root = Path(root)
        self.token = token
        self.epoch = epoch

    def _current(self):
        d = _read(self.root)
        if not isinstance(d, dict) or d['token'] != self.token or d['epoch'] != self.epoch:
            raise LeaseFenced(f'lease token={self.token} epoch={self.epoch} is no longer current')
        return d

    def assert_current(self):
        """Raise LeaseFenced unless this holder still owns the lease. Call before each emulator op."""
        self._current()

    def heartbeat(self, trial_index=None):
        with _Lock(self.root):
            d = self._current()
            d['heartbeat_ts'] = time.time()
            d['heartbeat_mono'] = time.monotonic()
            if trial_index is not None:
                d['trial_index'] = trial_index
            if not _valid(d):
                raise LeaseError('invalid heartbeat fields')
            _atomic_write(_lease_path(self.root), json.dumps(d, sort_keys=True))

    def release(self):
        release(self.token, ipc_dir=self.root, epoch=self.epoch)

    def bridge_stale(self, max_age):
        return bridge_stale(max_age, ipc_dir=self.root)

    def env(self):
        """Environment that authorises launch_emu.sh / stop_emu.sh as this exact acquisition."""
        return {'JUS_EMU_LEASE_TOKEN': self.token, 'JUS_EMU_LEASE_EPOCH': str(self.epoch)}


def acquire(campaign, token, ipc_dir=None, pid=None, stale_after=None):
    """Take the lease for `token` (the calling runner process by default).

    Raises LeaseHeld if a live, fresh holder owns it; unreadable leases fail closed.
    Over a dead/stale lease it takes over with epoch+1, fencing the previous holder.
    """
    root = ipc_root(ipc_dir)
    pid = pid or os.getpid()
    start = proc_start(pid)
    if start is None:
        raise LeaseError(f'pid {pid} is not a live process')
    if stale_after is None:
        stale_after = float(os.environ.get('JUS_EMU_LEASE_STALE', DEFAULT_STALE_AFTER))
    with _Lock(root):
        d = _read(root)
        state = _classify(d)
        if state == 'corrupt':
            raise LeaseError('refusing to acquire: unreadable lease')
        if state in ('held',):
            raise LeaseHeld(f"lease held by token={d['token']} epoch={d['epoch']} pid={d['pid']} "
                            f"campaign={d.get('campaign')}")
        epoch = _last_epoch(root, d) + 1
        now = time.time()
        new = {'token': token, 'epoch': epoch, 'pid': pid, 'start': start,
               'campaign': campaign, 'trial_index': None, 'heartbeat_ts': now,
               'acquired_ts': now, 'stale_after': stale_after,
               'heartbeat_mono': time.monotonic(), 'boot_id': _boot_id(),
               'took_over': state if state != 'free' else None}
        if not _valid(new):
            raise LeaseError('invalid acquisition fields')
        _atomic_write(root / 'LEASE.epoch', str(epoch))
        _atomic_write(_lease_path(root), json.dumps(new, sort_keys=True))
    return Lease(root, token, epoch)


def release(token, ipc_dir=None, epoch=None):
    root = ipc_root(ipc_dir)
    with _Lock(root):
        d = _read(root)
        if not isinstance(d, dict) or d['token'] != token or (epoch is not None and d['epoch'] != epoch):
            if epoch is not None:
                raise LeaseFenced(f'lease token={token} epoch={epoch} is no longer current')
            raise LeaseError(f'refusing to release: token does not match the current lease')
        _lease_path(root).unlink()


def status(ipc_dir=None):
    root = ipc_root(ipc_dir)
    d = _read(root)
    st = _classify(d)
    out = {'state': st, 'ipc_dir': str(root)}
    if isinstance(d, dict):
        out.update(d)
        out['heartbeat_age'] = round(time.time() - d.get('heartbeat_ts', 0), 3)
        out['holder_alive'] = proc_start(d['pid']) == d['start']
    return out


def bridge_heartbeat_age(ipc_dir=None):
    """Seconds since the bridge last wrote $IPC_DIR/heartbeat.json, None if it never has."""
    try:
        return time.time() - (ipc_root(ipc_dir) / 'heartbeat.json').stat().st_mtime
    except FileNotFoundError:
        return None


def bridge_stale(max_age, ipc_dir=None):
    """True if the bridge heartbeat is missing or older than max_age seconds (runner must stop dispatch)."""
    age = bridge_heartbeat_age(ipc_dir)
    return age is None or age > max_age


def _retire(root, d):
    """Fenced legacy recovery of a stale/dead lease. Caller holds the operation lock."""
    epoch = _last_epoch(root, d) + 1
    _atomic_write(root / 'LEASE.epoch', str(epoch))
    _lease_path(root).unlink()


def guard(token=None, epoch=None, ipc_dir=None, locked=False):
    """Shell-side check. Returns (ok, message).

    With a token: token AND epoch must equal the current lease. Without: refuse while a
    lease is held (live holder, fresh heartbeat) or unreadable; over a stale/dead lease the
    legacy caller first retires it (epoch bump under the lock) so the old holder is fenced.
    `locked=True` means the caller already holds the operation lock (the shell scripts do);
    otherwise it is taken here.
    """
    root = ipc_root(ipc_dir)
    if locked:
        return _guard(root, token, epoch)
    with _Lock(root):
        return _guard(root, token, epoch)


def _guard(root, token, epoch):
    d = _read(root)
    if token:
        try:
            epoch = int(epoch)
        except (TypeError, ValueError):
            return False, 'JUS_EMU_LEASE_TOKEN needs JUS_EMU_LEASE_EPOCH (use Lease.env())'
        if not isinstance(d, dict) or d['token'] != token or d['epoch'] != epoch:
            return False, 'JUS_EMU_LEASE_TOKEN/EPOCH does not match the current lease (fenced or never acquired)'
        return True, ''
    st = _classify(d)
    if st in ('held', 'corrupt'):
        who = f" token={d['token']} campaign={d.get('campaign')} pid={d['pid']}" if isinstance(d, dict) else ''
        return False, f'emulator lease is {st}{who}; only its runner may launch/stop (set JUS_EMU_LEASE_TOKEN and JUS_EMU_LEASE_EPOCH)'
    if st in ('stale', 'dead'):
        _retire(root, d)
    return True, ''


def main(argv=None):
    ap = argparse.ArgumentParser(prog='lease')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status')
    r = sub.add_parser('release')
    r.add_argument('--token', required=True)
    g = sub.add_parser('guard')
    g.add_argument('--token', default='')
    g.add_argument('--epoch', default='')
    g.add_argument('--locked', action='store_true')
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'status':
            print(json.dumps(status(), indent=2, sort_keys=True))
        elif a.cmd == 'release':
            release(a.token)
        else:
            ok, msg = guard(a.token, a.epoch, locked=a.locked)
            if not ok:
                print('REFUSING: ' + msg, file=sys.stderr)
                return EXIT_REFUSED
    except LeaseError as e:
        print(f'lease: {e}', file=sys.stderr)
        return EXIT_REFUSED
    return 0


if __name__ == '__main__':
    sys.exit(main())
