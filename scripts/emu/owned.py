"""Owned sections: the one way a leased runner mutates shared state (P1.8b).

Rule: every mutation of a shared namespace (the IPC root, the attempt's checkpoints, batch.json, kept files and raw
folders) by a leased runner happens inside `Owned.section()`. A section takes `$IPC_DIR/.lock` (lease._Lock, the same
flock as acquire/heartbeat/release and the shell launch/stop effects) and calls `Lease.assert_current()` while holding
it. A takeover therefore lands either before the section (the check raises LeaseFenced and nothing is written) or after
the section's write is complete; there is no check-to-write window.

A section holds the lock for milliseconds: file writes, renames, mkdir, small gzip. Never wait inside one (ack polling,
status.json polling, subprocess completion), and never call `Lease.heartbeat()` inside one: it takes the lock itself
and _Lock opens a fresh descriptor each time, so nesting deadlocks. Sections are not reentrant; entering one inside
another raises RuntimeError.

`Owned(None)` is a no-op (unleased runs behave as before). `Owned.from_env(ipc_dir)` builds the owner from
JUS_EMU_LEASE_TOKEN / JUS_EMU_LEASE_EPOCH (Lease.env()), which is how the warm-up child inherits its parent's lease.

Stdlib only, next to lease.py, which stays unchanged.
"""
from contextlib import contextmanager
import os
import threading

import lease as _lease

_held = threading.local()


class Owned:
    def __init__(self, lease=None):
        self.lease = lease

    @contextmanager
    def section(self):
        if getattr(_held, 'active', False):
            raise RuntimeError('owned sections are not reentrant (nesting the lease lock deadlocks)')
        _held.active = True
        try:
            if self.lease is None:
                yield
            else:
                with _lease._Lock(self.lease.root):
                    self.lease.assert_current()
                    yield
        finally:
            _held.active = False

    def run(self, fn, *args, **kwargs):
        with self.section():
            return fn(*args, **kwargs)

    @staticmethod
    def from_env(ipc_dir):
        token = os.environ.get('JUS_EMU_LEASE_TOKEN', '')
        if not token:
            return Owned(None)
        try:
            epoch = int(os.environ.get('JUS_EMU_LEASE_EPOCH', ''))
        except ValueError:
            raise _lease.LeaseError('JUS_EMU_LEASE_TOKEN needs JUS_EMU_LEASE_EPOCH (use Lease.env())')
        return Owned(_lease.Lease(_lease.ipc_root(ipc_dir), token, epoch))
