"""Runner-owned emulator lease. Fakes only: scratch IPC dir, fake melonDS = copy of sleep.

Never touches /tmp/jus_emu or any process this test did not start.
"""

import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

EMU = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('emu_lease', EMU / 'lease.py')
lease = importlib.util.module_from_spec(_spec)
sys.modules['emu_lease'] = lease
_spec.loader.exec_module(lease)


def start_time(pid):
    return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[19]


class LeaseBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.ipc = self.root / 'ipc'
        self.ipc.mkdir()
        (self.root / 'bin').mkdir()
        self.fake = self.root / 'bin' / 'melonDS'
        shutil.copy2(shutil.which('sleep'), self.fake)
        self.procs = []
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.wait()
        self._tmp.cleanup()

    def spawn(self):
        p = subprocess.Popen([str(self.fake), '300'], stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        self.procs.append(p)
        return p

    def acquire(self, token, pid=None, stale_after=60.0, campaign='camp'):
        return lease.acquire(campaign, token, ipc_dir=self.ipc, pid=pid or os.getpid(),
                             stale_after=stale_after)

    def raw(self):
        return json.loads((self.ipc / 'LEASE.json').read_text())


class AcquireTest(LeaseBase):
    def test_records_identity(self):
        p = self.spawn()
        l = self.acquire('tok1', pid=p.pid)
        d = self.raw()
        self.assertEqual((d['token'], d['epoch'], d['pid'], d['campaign']), ('tok1', 1, p.pid, 'camp'))
        self.assertEqual(d['start'], start_time(p.pid))
        self.assertIsNone(d['trial_index'])
        self.assertIn('heartbeat_ts', d)
        l.assert_current()

    def test_concurrent_acquire_exactly_one_wins(self):
        code = (
            "import sys, importlib.util, time, os\n"
            "spec = importlib.util.spec_from_file_location('l', sys.argv[1]);"
            "m = importlib.util.module_from_spec(spec); sys.modules['l']=m; spec.loader.exec_module(m)\n"
            "while not os.path.exists(sys.argv[3]): time.sleep(0.001)\n"
            "try:\n"
            "    m.acquire('c', sys.argv[4], ipc_dir=sys.argv[2], pid=int(sys.argv[5]), stale_after=60)\n"
            "    print('WIN')\n"
            "except m.LeaseHeld:\n"
            "    print('LOSE')\n")
        live = self.spawn()
        go = self.root / 'go'
        ps = [subprocess.Popen([sys.executable, '-c', code, str(EMU / 'lease.py'), str(self.ipc),
                                str(go), f'tok{i}', str(live.pid)],
                               stdout=subprocess.PIPE, text=True) for i in range(2)]
        self.procs.extend(ps)
        go.write_text('x')
        outs = sorted(p.communicate(timeout=30)[0].strip() for p in ps)
        self.assertEqual(outs, ['LOSE', 'WIN'])
        self.assertEqual(self.raw()['epoch'], 1)

    def test_live_holder_fresh_heartbeat_cannot_be_taken_over(self):
        a = self.spawn()
        self.acquire('A', pid=a.pid)
        with self.assertRaises(lease.LeaseHeld):
            self.acquire('B', pid=os.getpid())
        self.assertEqual(self.raw()['token'], 'A')

    def test_same_token_reacquire_is_refused_while_live(self):
        a = self.spawn()
        self.acquire('A', pid=a.pid)
        with self.assertRaises(lease.LeaseHeld):
            self.acquire('A', pid=a.pid)


class TakeoverTest(LeaseBase):
    def test_stale_heartbeat_takeover_bumps_epoch_and_fences_old(self):
        a = self.spawn()
        old = self.acquire('A', pid=a.pid, stale_after=0.2)
        time.sleep(0.4)
        new = self.acquire('B', pid=os.getpid())
        self.assertEqual(new.epoch, old.epoch + 1)
        self.assertEqual(self.raw()['token'], 'B')
        with self.assertRaises(lease.LeaseFenced):
            old.assert_current()
        with self.assertRaises(lease.LeaseFenced):
            old.heartbeat(3)
        with self.assertRaises(lease.LeaseFenced):
            old.release()
        self.assertEqual(self.raw()['token'], 'B')
        new.assert_current()

    def test_heartbeat_keeps_lease_fresh(self):
        a = self.spawn()
        l = self.acquire('A', pid=a.pid, stale_after=0.5)
        for i in range(4):
            time.sleep(0.2)
            l.heartbeat(i)
        self.assertEqual(self.raw()['trial_index'], 3)
        with self.assertRaises(lease.LeaseHeld):
            self.acquire('B')

    def test_dead_pid_takeover_allowed(self):
        a = self.spawn()
        old = self.acquire('A', pid=a.pid)
        a.kill()
        a.wait()
        new = self.acquire('B')
        self.assertEqual(new.epoch, old.epoch + 1)
        with self.assertRaises(lease.LeaseFenced):
            old.assert_current()

    def test_pid_reuse_start_mismatch_is_dead(self):
        a = self.spawn()
        self.acquire('A', pid=a.pid)
        d = self.raw()
        d['start'] = str(int(d['start']) + 1)  # same live pid, different process instance
        (self.ipc / 'LEASE.json').write_text(json.dumps(d))
        new = self.acquire('B')
        self.assertEqual(new.epoch, 2)

    def test_epoch_monotonic_across_release(self):
        a = self.spawn()
        l1 = self.acquire('A', pid=a.pid)
        l1.release()
        self.assertFalse((self.ipc / 'LEASE.json').exists())
        l2 = self.acquire('B', pid=a.pid)
        self.assertEqual(l2.epoch, 2)
        with self.assertRaises(lease.LeaseFenced):
            l1.assert_current()

    def test_assert_current_when_lease_gone_is_fenced(self):
        a = self.spawn()
        l = self.acquire('A', pid=a.pid)
        (self.ipc / 'LEASE.json').unlink()
        with self.assertRaises(lease.LeaseFenced):
            l.assert_current()


class ReleaseAndStatusTest(LeaseBase):
    def test_release_wrong_token_refused(self):
        a = self.spawn()
        self.acquire('A', pid=a.pid)
        with self.assertRaises(lease.LeaseError):
            lease.release('WRONG', ipc_dir=self.ipc)
        self.assertEqual(self.raw()['token'], 'A')
        lease.release('A', ipc_dir=self.ipc)
        self.assertFalse((self.ipc / 'LEASE.json').exists())

    def test_status_states(self):
        self.assertEqual(lease.status(ipc_dir=self.ipc)['state'], 'free')
        a = self.spawn()
        self.acquire('A', pid=a.pid, stale_after=0.2)
        self.assertEqual(lease.status(ipc_dir=self.ipc)['state'], 'held')
        time.sleep(0.4)
        self.assertEqual(lease.status(ipc_dir=self.ipc)['state'], 'stale')
        a.kill()
        a.wait()
        self.assertEqual(lease.status(ipc_dir=self.ipc)['state'], 'dead')

    def test_cli_status_and_release(self):
        a = self.spawn()
        self.acquire('A', pid=a.pid)
        env = dict(os.environ, JUS_EMU_DIR=str(self.ipc))
        r = subprocess.run([sys.executable, str(EMU / 'lease.py'), 'status'], env=env,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['state'], 'held')
        bad = subprocess.run([sys.executable, str(EMU / 'lease.py'), 'release', '--token', 'X'],
                             env=env, capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)
        ok = subprocess.run([sys.executable, str(EMU / 'lease.py'), 'release', '--token', 'A'],
                            env=env, capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)

    def test_bridge_heartbeat_age(self):
        self.assertIsNone(lease.bridge_heartbeat_age(ipc_dir=self.ipc))
        hb = self.ipc / 'heartbeat.json'
        hb.write_text('{}')
        os.utime(hb, (time.time() - 50, time.time() - 50))
        self.assertGreater(lease.bridge_heartbeat_age(ipc_dir=self.ipc), 49)
        self.assertTrue(lease.bridge_stale(10, ipc_dir=self.ipc))
        self.assertFalse(lease.bridge_stale(100, ipc_dir=self.ipc))


class AtomicityTest(LeaseBase):
    def test_partial_tmp_file_leaves_old_lease(self):
        a = self.spawn()
        self.acquire('A', pid=a.pid, stale_after=0.1)
        # a writer crashed after creating a truncated temp file, before the rename
        (self.ipc / 'LEASE.json.tmp.99999').write_text('{"token": "B", "epo')
        self.assertEqual(self.raw()['token'], 'A')
        self.assertEqual(lease.status(ipc_dir=self.ipc)['token'], 'A')
        time.sleep(0.3)
        new = self.acquire('C')  # leftovers do not wedge the next acquire
        self.assertEqual(self.raw()['token'], 'C')
        self.assertEqual(new.epoch, 2)

    def test_crash_between_write_and_rename_keeps_old(self):
        a = self.spawn()
        self.acquire('A', pid=a.pid, stale_after=0.1)
        time.sleep(0.3)
        orig = os.replace
        def boom(*args, **kw):
            raise KeyboardInterrupt('crash before rename')
        lease.os.replace = boom
        try:
            with self.assertRaises(KeyboardInterrupt):
                lease.acquire('x', 'B', ipc_dir=self.ipc, pid=os.getpid(), stale_after=60)
        finally:
            lease.os.replace = orig
        self.assertEqual(self.raw()['token'], 'A')

    def test_corrupt_file_refuses_acquisition(self):
        (self.ipc / 'LEASE.json').write_text('{"token": "B", "epo')
        self.assertEqual(lease.status(ipc_dir=self.ipc)['state'], 'corrupt')
        with self.assertRaises(lease.LeaseError):
            self.acquire('C')
        self.assertEqual(lease.status(ipc_dir=self.ipc)['state'], 'corrupt')


class ShellGuardTest(LeaseBase):
    """launch_emu.sh / stop_emu.sh integration, with a fake melonDS (MELONDS) only."""

    def run_sh(self, script, env_extra, *args):
        env = dict(os.environ, JUS_EMU_DIR=str(self.ipc), MELONDS=str(self.fake),
                   ROM=str(self.root / 'rom.nds'))
        env.pop('JUS_EMU_HOLDER', None)
        env.pop('JUS_EMU_LEASE_TOKEN', None)
        env.pop('JUS_EMU_LEASE_EPOCH', None)
        env.update(env_extra)
        (self.root / 'rom.nds').write_text('x')
        return subprocess.run(['bash', str(EMU / script), *args], env=env, capture_output=True,
                              text=True, timeout=90)

    def test_launch_refuses_without_token_or_holder(self):
        r = self.run_sh('launch_emu.sh', {})
        self.assertEqual(r.returncode, 6, r.stdout + r.stderr)
        self.assertFalse((self.ipc / 'emu.pid').exists())

    def test_launch_refuses_wrong_token(self):
        a = self.spawn()
        self.acquire('A', pid=a.pid)
        r = self.run_sh('launch_emu.sh', {'JUS_EMU_LEASE_TOKEN': 'B'})
        self.assertEqual(r.returncode, 6, r.stdout + r.stderr)

    def test_legacy_holder_refused_while_lease_live(self):
        a = self.spawn()
        self.acquire('A', pid=a.pid)
        r = self.run_sh('launch_emu.sh', {'JUS_EMU_HOLDER': 'legacy'})
        self.assertEqual(r.returncode, 6, r.stdout + r.stderr)
        self.assertFalse((self.ipc / 'emu.pid').exists())

    def test_stop_refused_while_foreign_lease_live(self):
        a = self.spawn()
        self.acquire('A', pid=a.pid)
        r = self.run_sh('stop_emu.sh', {'JUS_EMU_HOLDER': 'legacy'})
        self.assertEqual(r.returncode, 6, r.stdout + r.stderr)

    def test_launch_with_token_proceeds_and_stop_with_token(self):
        a = self.spawn()
        self.acquire('A', pid=a.pid)
        r = self.run_sh('launch_emu.sh', {'JUS_EMU_LEASE_TOKEN': 'A', 'JUS_EMU_LEASE_EPOCH': '1'})
        # fake melonDS never writes a heartbeat; getting past the guard is what matters
        self.assertTrue((self.ipc / 'emu.pid').exists(), r.stdout + r.stderr)
        emu = int((self.ipc / 'emu.pid').read_text())
        self.addCleanup(lambda: os.kill(emu, 9) if Path(f'/proc/{emu}').exists() else None)
        s = self.run_sh('stop_emu.sh', {'JUS_EMU_LEASE_TOKEN': 'A', 'JUS_EMU_LEASE_EPOCH': '1'})
        self.assertEqual(s.returncode, 0, s.stdout + s.stderr)

    def test_legacy_holder_without_lease_unchanged(self):
        s = self.run_sh('stop_emu.sh', {'JUS_EMU_HOLDER': 'legacy'})
        self.assertEqual(s.returncode, 0, s.stdout + s.stderr)

    def test_dead_lease_does_not_block_legacy(self):
        a = self.spawn()
        self.acquire('A', pid=a.pid)
        a.kill()
        a.wait()
        s = self.run_sh('stop_emu.sh', {'JUS_EMU_HOLDER': 'legacy'})
        self.assertEqual(s.returncode, 0, s.stdout + s.stderr)


class LockProtocolTest(LeaseBase):
    """One lock order: .lock serialises lease transitions and shell effects."""

    run_sh = ShellGuardTest.run_sh

    def popen_sh(self, script, env_extra):
        env = dict(os.environ, JUS_EMU_DIR=str(self.ipc), MELONDS=str(self.fake),
                   ROM=str(self.root / 'rom.nds'))
        env.pop('JUS_EMU_HOLDER', None)
        env.pop('JUS_EMU_LEASE_TOKEN', None)
        env.pop('JUS_EMU_LEASE_EPOCH', None)
        env.update(env_extra)
        (self.root / 'rom.nds').write_text('x')
        p = subprocess.Popen(['bash', str(EMU / script)], env=env, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True)
        self.procs.append(p)
        return p

    def hold_op_lock(self):
        f = open(self.ipc / '.lock', 'a')
        fcntl.flock(f, fcntl.LOCK_EX)
        self.addCleanup(f.close)
        return f

    def backdate(self, age=3600):
        d = self.raw()
        d['heartbeat_ts'] -= age
        d['heartbeat_mono'] -= age
        (self.ipc / 'LEASE.json').write_text(json.dumps(d))

    def publish_holder(self, emu):
        (self.ipc / 'HOLDER').write_text(
            f'h\n{emu.pid}\n2026-10-18 00:00:00\n{start_time(emu.pid)}\n')

    def swap_lease_to_b(self, runner_b):
        d = self.raw()
        d.update(token='B', epoch=d['epoch'] + 1, pid=runner_b.pid, start=start_time(runner_b.pid))
        (self.ipc / 'LEASE.epoch').write_text(str(d['epoch']))
        (self.ipc / 'LEASE.json').write_text(json.dumps(d))

    def test_blocked_stop_is_refused_after_takeover(self):
        ra, rb, emu = self.spawn(), self.spawn(), self.spawn()
        la = self.acquire('A', pid=ra.pid)
        self.publish_holder(emu)
        lock = self.hold_op_lock()
        p = self.popen_sh('stop_emu.sh', {'JUS_EMU_LEASE_TOKEN': 'A',
                                          'JUS_EMU_LEASE_EPOCH': str(la.epoch)})
        time.sleep(1.5)
        self.assertIsNone(p.poll())
        self.swap_lease_to_b(rb)
        lock.close()
        out = p.communicate(timeout=60)[0]
        self.assertEqual(p.returncode, 6, out)
        self.assertIsNone(emu.poll(), 'new holder emulator must survive the fenced stop')
        self.assertTrue((self.ipc / 'HOLDER').exists())

    def test_blocked_launch_is_refused_after_takeover(self):
        ra, rb = self.spawn(), self.spawn()
        la = self.acquire('A', pid=ra.pid)
        lock = self.hold_op_lock()
        p = self.popen_sh('launch_emu.sh', {'JUS_EMU_LEASE_TOKEN': 'A',
                                            'JUS_EMU_LEASE_EPOCH': str(la.epoch)})
        time.sleep(1.5)
        self.assertIsNone(p.poll())
        self.swap_lease_to_b(rb)
        lock.close()
        out = p.communicate(timeout=60)[0]
        self.assertEqual(p.returncode, 6, out)
        self.assertFalse((self.ipc / 'emu.pid').exists())
        self.assertFalse((self.ipc / 'HOLDER').exists())

    def test_takeover_waits_for_held_operation_lock(self):
        ra = self.spawn()
        self.acquire('A', pid=ra.pid)
        self.backdate()
        lock = self.hold_op_lock()
        code = ("import sys, importlib.util\n"
                "spec = importlib.util.spec_from_file_location('l', sys.argv[1]);"
                "m = importlib.util.module_from_spec(spec); sys.modules['l'] = m; spec.loader.exec_module(m)\n"
                "m.acquire('c', 'B', ipc_dir=sys.argv[2], pid=int(sys.argv[3]), stale_after=60)\n")
        rb = self.spawn()
        p = subprocess.Popen([sys.executable, '-B', '-c', code, str(EMU / 'lease.py'), str(self.ipc), str(rb.pid)])
        self.procs.append(p)
        time.sleep(1.5)
        self.assertIsNone(p.poll(), 'takeover must wait for the operation lock, not fail open')
        self.assertEqual(self.raw()['token'], 'A')
        lock.close()
        self.assertEqual(p.wait(timeout=30), 0)
        self.assertEqual((self.raw()['token'], self.raw()['epoch']), ('B', 2))

    def test_legacy_recovery_of_stale_lease_fences_old_holder(self):
        ra, emu = self.spawn(), self.spawn()
        la = self.acquire('A', pid=ra.pid)
        self.backdate()
        self.publish_holder(emu)
        s = self.run_sh('stop_emu.sh', {'JUS_EMU_HOLDER': 'legacy'})
        self.assertEqual(s.returncode, 0, s.stdout + s.stderr)
        with self.assertRaises(lease.LeaseFenced):
            la.heartbeat()
        with self.assertRaises(lease.LeaseFenced):
            la.assert_current()
        self.assertGreater(int((self.ipc / 'LEASE.epoch').read_text()), la.epoch)
        self.assertGreater(self.acquire('C', pid=ra.pid).epoch, la.epoch)

    def test_legacy_recovery_of_dead_lease_fences_old_holder(self):
        ra = self.spawn()
        la = self.acquire('A', pid=ra.pid)
        ra.kill()
        ra.wait()
        s = self.run_sh('stop_emu.sh', {'JUS_EMU_HOLDER': 'legacy'})
        self.assertEqual(s.returncode, 0, s.stdout + s.stderr)
        with self.assertRaises(lease.LeaseFenced):
            la.assert_current()

    def test_same_token_new_epoch_refuses_old_shell_env(self):
        ra, emu = self.spawn(), self.spawn()
        old = self.acquire('SAME', pid=ra.pid)
        self.backdate()
        new = self.acquire('SAME', pid=ra.pid)
        self.assertEqual((old.epoch, new.epoch), (1, 2))
        self.publish_holder(emu)
        s = self.run_sh('stop_emu.sh', {'JUS_EMU_LEASE_TOKEN': 'SAME', 'JUS_EMU_LEASE_EPOCH': '1'})
        self.assertEqual(s.returncode, 6, s.stdout + s.stderr)
        self.assertIsNone(emu.poll())
        s = self.run_sh('stop_emu.sh', {'JUS_EMU_LEASE_TOKEN': 'SAME', 'JUS_EMU_LEASE_EPOCH': '2'})
        self.assertEqual(s.returncode, 0, s.stdout + s.stderr)

    def test_wrong_token_right_epoch_is_refused(self):
        ra = self.spawn()
        la = self.acquire('A', pid=ra.pid)
        s = self.run_sh('stop_emu.sh', {'JUS_EMU_LEASE_TOKEN': 'B', 'JUS_EMU_LEASE_EPOCH': str(la.epoch)})
        self.assertEqual(s.returncode, 6, s.stdout + s.stderr)

    def test_token_without_epoch_is_refused(self):
        ra = self.spawn()
        self.acquire('A', pid=ra.pid)
        s = self.run_sh('stop_emu.sh', {'JUS_EMU_LEASE_TOKEN': 'A'})
        self.assertEqual(s.returncode, 6, s.stdout + s.stderr)

    def test_lease_env_helper(self):
        l = self.acquire('A')
        self.assertEqual(l.env(), {'JUS_EMU_LEASE_TOKEN': 'A', 'JUS_EMU_LEASE_EPOCH': '1'})


if __name__ == '__main__':
    unittest.main()
