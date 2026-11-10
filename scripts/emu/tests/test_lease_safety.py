"""Lease safety with fake clocks and process identities; no subprocesses or emulator."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import lease


class LeaseSafety(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.wall = self.enterContext(patch.object(lease.time, 'time', return_value=1000.0))
        self.mono = self.enterContext(patch.object(lease.time, 'monotonic', return_value=100.0))
        self.proc = self.enterContext(patch.object(lease, 'proc_start', return_value='123'))
        self.old = self.acquire('old')
        self.path = self.root / 'LEASE.json'

    def acquire(self, token):
        return lease.acquire('campaign', token, ipc_dir=self.root, stale_after=10)

    def assert_held(self):
        self.assertEqual(lease.status(self.root)['state'], 'held')
        with self.assertRaises(lease.LeaseHeld):
            self.acquire('new')
        self.assertFalse(lease.guard(ipc_dir=self.root)[0])
        self.old.assert_current()

    def test_backward_step_never_stale(self):
        self.wall.return_value = 900.0
        self.mono.return_value = 120.0
        self.assert_held()

    def test_forward_step_live_runner(self):
        self.wall.return_value = 100000.0
        self.mono.return_value = 101.0
        self.assert_held()
        self.old.heartbeat(2)
        self.wall.return_value += 11
        self.mono.return_value = 102.0
        self.assert_held()

    def test_dead_runner_after_backward_step(self):
        self.wall.return_value = 900.0
        self.proc.side_effect = lambda pid: '123' if pid == 999 else None
        new = lease.acquire('c', 'new', ipc_dir=self.root, pid=999)
        self.assertEqual(new.epoch, 2)
        self.assertEqual(lease.status(self.root)['took_over'], 'dead')

    def test_elapsed_monotonic_timeout(self):
        self.wall.return_value = 1011.0
        self.mono.return_value = 111.0
        self.assertEqual(self.acquire('new').epoch, 2)
        with self.assertRaises(lease.LeaseFenced):
            self.old.heartbeat()

    def test_different_boot_is_dead(self):
        d = json.loads(self.path.read_text())
        d['boot_id'] = '00000000-0000-0000-0000-000000000000'
        self.path.write_text(json.dumps(d))
        self.assertEqual(self.acquire('new').epoch, 2)

    def assert_corrupt(self, d):
        self.path.write_text(json.dumps(d))
        before = self.path.read_bytes()
        self.assertEqual(lease._read(self.root), 'corrupt')
        self.assertEqual(lease.status(self.root)['state'], 'corrupt')
        self.assertFalse(lease.guard(ipc_dir=self.root)[0])
        self.assertFalse(lease.guard('old', 1, ipc_dir=self.root)[0])
        with self.assertRaises(lease.LeaseError):
            self.acquire('new')
        with self.assertRaises(lease.LeaseError):
            self.old.release()
        with self.assertRaises(lease.LeaseFenced):
            self.old.heartbeat()
        self.assertEqual(self.path.read_bytes(), before)

    def test_missing_every_key(self):
        good = json.loads(self.path.read_text())
        for key in good:
            with self.subTest(key=key):
                self.assert_corrupt({k: v for k, v in good.items() if k != key})

    def test_wrong_types_every_key(self):
        good = json.loads(self.path.read_text())
        for key in good:
            with self.subTest(key=key):
                self.assert_corrupt({**good, key: []})
        for key in ('epoch', 'pid', 'heartbeat_ts', 'acquired_ts', 'stale_after', 'heartbeat_mono', 'trial_index'):
            with self.subTest(key=key, value=True):
                self.assert_corrupt({**good, key: True})
        for key in ('heartbeat_ts', 'acquired_ts', 'stale_after', 'heartbeat_mono'):
            for value in (float('nan'), float('inf'), -float('inf')):
                with self.subTest(key=key, value=value):
                    self.assert_corrupt({**good, key: value})

    def test_extra_keys_rejected(self):
        self.assert_corrupt({**json.loads(self.path.read_text()), 'state': 'free'})

    def test_non_object_rejected(self):
        for d in ([], None, 'lease', 1):
            with self.subTest(d=d):
                self.assert_corrupt(d)

    def test_invalid_values(self):
        good = json.loads(self.path.read_text())
        for key, value in (('token', ''), ('campaign', ''), ('start', 'bad'),
                           ('boot_id', 'bad'), ('pid', 0), ('epoch', -1),
                           ('trial_index', -1), ('stale_after', 0),
                           ('heartbeat_mono', -1), ('took_over', 'free')):
            with self.subTest(key=key, value=value):
                self.assert_corrupt({**good, key: value})

    def test_unreadable_encoding_and_json(self):
        for raw in (b'\xff', b'{broken'):
            self.path.write_bytes(raw)
            self.assertEqual(lease._read(self.root), 'corrupt')
            with self.assertRaises(lease.LeaseError):
                self.acquire('new')
            self.assertEqual(self.path.read_bytes(), raw)

    def test_heartbeat_refreshes_monotonic_stamp(self):
        self.mono.return_value = 150.0
        self.wall.return_value = 1005.0
        self.old.heartbeat(3)
        d = json.loads(self.path.read_text())
        self.assertEqual(d['heartbeat_mono'], 150.0)
        self.assertEqual(d['heartbeat_ts'], 1005.0)
        self.assertEqual(d['trial_index'], 3)

    def test_boot_id_read_failure_is_lease_error(self):
        with patch.object(lease.Path, 'read_text', side_effect=OSError('no proc')):
            with self.assertRaises(lease.LeaseError) as cm:
                lease._boot_id()
            self.assertNotIsInstance(cm.exception, OSError)
            self.assertIn('boot', str(cm.exception))
            with self.assertRaises(lease.LeaseError):
                self.acquire('new')
