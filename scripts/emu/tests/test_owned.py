"""owned.Owned: the lease lock plus assert_current around every shared write. Scratch IPC roots and
forked python children only; no emulator, no /tmp/jus_emu."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import lease
from owned import Owned


def stale_takeover(ipc, token='b'):
    with mock.patch.object(lease.time, 'time', return_value=time.time() + lease.DEFAULT_STALE_AFTER + 1), \
            mock.patch.object(lease.time, 'monotonic', return_value=time.monotonic() + lease.DEFAULT_STALE_AFTER + 1):
        return lease.acquire(token, token, ipc_dir=ipc)


class TestOwned(unittest.TestCase):
    def setUp(self):
        self.ipc = Path(tempfile.mkdtemp())

    def test_no_lease_is_a_no_op(self):
        o = Owned(None)
        with o.section():
            (self.ipc / 'x').write_text('1')
        self.assertEqual(o.run(lambda a, b=0: a + b, 1, b=2), 3)
        self.assertFalse((self.ipc / '.lock').exists())     # no lock file, nothing else touched

    def test_current_holder_writes(self):
        a = lease.acquire('a', 'a', ipc_dir=self.ipc)
        Owned(a).run((self.ipc / 'x').write_text, 'ok')
        self.assertEqual((self.ipc / 'x').read_text(), 'ok')

    def test_a_fenced_holder_raises_before_writing(self):
        a = lease.acquire('a', 'a', ipc_dir=self.ipc)
        stale_takeover(self.ipc)
        body = mock.Mock()
        with self.assertRaises(lease.LeaseFenced):
            with Owned(a).section():
                body()
        body.assert_not_called()

    def test_re_entry_raises(self):
        for o in (Owned(None), Owned(lease.acquire('a', 'a', ipc_dir=self.ipc))):
            with self.subTest(lease=o.lease is not None):
                with o.section():
                    with self.assertRaises(RuntimeError):
                        with o.section():
                            pass
                with o.section():                           # the flag is cleared again on exit
                    pass

    def test_a_section_blocks_the_lock_in_another_process(self):
        a = lease.acquire('a', 'a', ipc_dir=self.ipc)
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            try:
                os.close(r)
                with lease._Lock(self.ipc):
                    os.write(w, b'x')
                    time.sleep(0.5)
            finally:
                os._exit(0)
        os.close(w)
        os.read(r, 1)
        t0 = time.monotonic()
        with Owned(a).section():
            waited = time.monotonic() - t0
        os.waitpid(pid, 0)
        self.assertGreater(waited, 0.3)

    def test_from_env(self):
        self.assertIsNone(Owned.from_env(self.ipc).lease)
        a = lease.acquire('a', 'a', ipc_dir=self.ipc)
        with mock.patch.dict(os.environ, a.env()):
            o = Owned.from_env(str(self.ipc))
        self.assertEqual((o.lease.token, o.lease.epoch, o.lease.root), ('a', a.epoch, self.ipc))
        with mock.patch.dict(os.environ, {'JUS_EMU_LEASE_TOKEN': 'a', 'JUS_EMU_LEASE_EPOCH': ''}):
            with self.assertRaises(lease.LeaseError):
                Owned.from_env(self.ipc)


if __name__ == '__main__':
    unittest.main()
