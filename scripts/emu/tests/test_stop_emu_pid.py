"""PID-scoped emulator stop, with fake melonDS processes only.

Set EMU_SCRIPTS_DIR to run against another copy of the scripts/emu stop and launch files.
Never touches /tmp/jus_emu or any process this test did not start.
"""

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

SCRIPTS = Path(os.environ.get('EMU_SCRIPTS_DIR') or Path(__file__).resolve().parents[1])


def start_time(pid):
    stat = Path(f'/proc/{pid}/stat').read_text()
    return stat.rsplit(')', 1)[1].split()[19]


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:
        return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0] != 'Z'
    except OSError:
        return False


class StopEmuPidTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.ipc = self.root / 'ipc'
        self.ipc.mkdir()
        bindir = self.root / 'bin'
        bindir.mkdir()
        # argv[0] must end in /melonDS to look like the real emulator.
        self.fake = bindir / 'melonDS'
        shutil.copy2(shutil.which('sleep'), self.fake)
        self.procs = []
        self.env = dict(os.environ, JUS_EMU_DIR=str(self.ipc), JUS_EMU_HOLDER='tester')
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            p.wait()
        self._tmp.cleanup()

    def spawn(self, argv0=None, ignore_term=False):
        # SIGTERM set to ignored survives exec, so TERM cannot kill the fake.
        pre = (lambda: signal.signal(signal.SIGTERM, signal.SIG_IGN)) if ignore_term else None
        p = subprocess.Popen([argv0 or str(self.fake), '300'], executable=str(self.fake),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True, preexec_fn=pre)
        self.procs.append(p)
        return p

    def holder(self, pid, start, label='owner'):
        lines = [label, str(pid), 'now'] + ([str(start)] if start is not None else [])
        (self.ipc / 'HOLDER').write_text('\n'.join(lines) + '\n')

    def stop(self, *args):
        return subprocess.run(['bash', str(SCRIPTS / 'stop_emu.sh'), *args], env=self.env,
                              capture_output=True, text=True, timeout=60)

    def test_pid_stop_kills_only_that_pid(self):
        a, b = self.spawn(), self.spawn()
        self.holder(a.pid, start_time(a.pid))
        r = self.stop('--pid', str(a.pid))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIsNotNone(a.wait(timeout=5))
        self.assertIsNone(b.poll(), 'second melonDS must survive')
        self.assertFalse((self.ipc / 'HOLDER').exists())

    def test_explicit_start_time_without_holder_file(self):
        a, b = self.spawn(), self.spawn()
        r = self.stop('--pid', str(a.pid), '--start-time', start_time(a.pid))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        a.wait(timeout=5)
        self.assertIsNone(b.poll())

    def test_start_time_mismatch_refuses(self):
        a = self.spawn()
        self.holder(a.pid, int(start_time(a.pid)) + 1)
        r = self.stop('--pid', str(a.pid))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('REFUSING', r.stderr)
        self.assertIsNone(a.poll(), 'reused-pid victim must survive')

    def test_unrecorded_start_time_refuses(self):
        a = self.spawn()
        r = self.stop('--pid', str(a.pid))
        self.assertNotEqual(r.returncode, 0)
        self.assertIsNone(a.poll())

    def test_non_melonds_argv0_refuses(self):
        other = self.root / 'bin' / 'notemu'
        shutil.copy2(shutil.which('sleep'), other)
        p = subprocess.Popen([str(other), '300'])
        self.procs.append(p)
        r = self.stop('--pid', str(p.pid), '--start-time', start_time(p.pid))
        self.assertNotEqual(r.returncode, 0)
        self.assertIsNone(p.poll())

    def test_plain_force_does_not_kill_other_melonds(self):
        a, b = self.spawn(), self.spawn()
        self.holder(a.pid, start_time(a.pid))
        r = self.stop('--force')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        a.wait(timeout=5)
        self.assertIsNone(b.poll(), '--force must not mean kill every melonDS')

    def test_plain_force_without_record_kills_nothing(self):
        b = self.spawn()
        r = self.stop('--force')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIsNone(b.poll())

    def test_broad_flag_kills_matching_fakes_only(self):
        a, b = self.spawn(), self.spawn()
        pattern = '^' + str(self.fake) + '( |$)'
        r = self.stop('--all-melonds-i-am-sure', pattern)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        a.wait(timeout=5)
        b.wait(timeout=5)

    def run_launch(self):
        """Run a scratch copy of launch_emu.sh with a dead HOLDER and a fake emulator."""
        dead = subprocess.Popen(['true'])
        dead.wait()
        self.holder(dead.pid, 12345)
        scripts = self.root / 'scripts'
        scripts.mkdir()
        for name in ('launch_emu.sh', 'stop_emu.sh', 'stop_emu_lib.sh', 'pidfd_signal.py'):
            if (SCRIPTS / name).exists():
                shutil.copy2(SCRIPTS / name, scripts / name)
        emu = self.root / 'fake-emulator'
        emu.write_text(
            '#!/usr/bin/env python3\n'
            'import json, os, time\nfrom pathlib import Path\n'
            'root = Path(os.environ["JUS_EMU_DIR"])\n'
            'while True:\n'
            '    (root / "heartbeat.tmp").write_text(json.dumps({"framecount": 1}))\n'
            '    (root / "heartbeat.tmp").replace(root / "heartbeat.json")\n'
            '    time.sleep(0.05)\n')
        emu.chmod(0o755)
        (self.root / 'jus.nds').touch()
        env = dict(self.env, MELONDS=str(emu), ROM=str(self.root / 'jus.nds'))
        r = subprocess.run(['bash', str(scripts / 'launch_emu.sh'), '--keep-ipc'], env=env,
                           capture_output=True, text=True, timeout=60)
        try:
            new_pid = int((self.ipc / 'emu.pid').read_text())
        except (OSError, ValueError):
            new_pid = None
        if new_pid:
            self.addCleanup(lambda: alive(new_pid) and os.kill(new_pid, 9))
        return r, new_pid

    def test_launch_with_dead_holder_stops_only_recorded_pid(self):
        b = self.spawn()
        r, new_pid = self.run_launch()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIsNone(b.poll(), 'launch must not kill an unrelated melonDS')
        lines = (self.ipc / 'HOLDER').read_text().splitlines()
        self.assertEqual(lines[1], str(new_pid))
        self.assertEqual(lines[3], start_time(new_pid))

    # ---- fix round: review findings P1, P2a, P2b, P2c ----

    def hook(self, text):
        path = self.root / 'hook.sh'
        path.write_text(text)
        self.env['BASH_ENV'] = str(path)

    def darwin(self):
        (self.root / 'bin' / 'uname').write_text('#!/bin/sh\necho Darwin\n')
        (self.root / 'bin' / 'uname').chmod(0o755)
        self.env['PATH'] = str(self.root / 'bin') + ':' + os.environ['PATH']

    def test_p1_start_token_change_between_term_and_kill_refuses(self):
        a = self.spawn(ignore_term=True)
        self.holder(a.pid, start_time(a.pid))
        # First wait-loop sleep happens after TERM; change the identity reader there.
        self.hook('sleep() { proc_start() { echo reused-start; }; command sleep "$@"; }\n')
        r = self.stop('--force')
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIsNone(a.poll(), 'KILL must not be sent after identity changed')
        self.assertTrue((self.ipc / 'HOLDER').exists())

    def test_p1_argv0_change_between_term_and_kill_refuses(self):
        a = self.spawn(ignore_term=True)
        self.holder(a.pid, start_time(a.pid))
        self.hook('sleep() { proc_argv0() { echo /usr/bin/vim; }; command sleep "$@"; }\n')
        r = self.stop('--force')
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIsNone(a.poll())

    def test_p1_pidfd_helper_refuses_wrong_token_and_signals_right_one(self):
        a = self.spawn()
        helper = SCRIPTS / 'pidfd_signal.py'
        bad = subprocess.run(['python3', str(helper), str(a.pid), '1', 'KILL', '/melonDS'])
        self.assertEqual(bad.returncode, 4)
        self.assertIsNone(a.poll())
        ok = subprocess.run(['python3', str(helper), str(a.pid), start_time(a.pid), 'KILL',
                             '/melonDS'])
        self.assertEqual(ok.returncode, 0)
        a.wait(timeout=5)

    def test_p2a_darwin_rejects_lookalike_executables(self):
        self.darwin()
        for argv0 in ('/x/melonDS.app/Contents/MacOS/melonDS-not-an-emulator',
                      '/x/melonDSxapp/Contents/MacOS/melonDS',
                      '/usr/bin/melonDS'):
            with self.subTest(argv0=argv0):
                a = self.spawn(argv0=argv0)
                self.holder(a.pid, start_time(a.pid))
                r = self.stop('--force')
                self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
                self.assertIsNone(a.poll())

    def test_p2a_darwin_accepts_the_exact_bundle_executable(self):
        self.darwin()
        a = self.spawn(argv0='/Apps/melonDS.app/Contents/MacOS/melonDS')
        self.holder(a.pid, start_time(a.pid))
        r = self.stop('--force')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        a.wait(timeout=5)

    def test_p2b_holder_replaced_mid_stop_survives(self):
        a, b = self.spawn(ignore_term=True), self.spawn()
        self.holder(a.pid, start_time(a.pid))
        repl = self.root / 'repl'
        repl.write_text(f'new-owner\n{b.pid}\nnow\n{start_time(b.pid)}\n')
        self.env.update(OWNED_PID=str(a.pid), REPLACEMENT=str(repl))
        # Model a new launch publishing while A dies: KILL A, then swap HOLDER.
        self.hook('sleep() { builtin kill -9 "$OWNED_PID"; command sleep 0.2;'
                  ' command cp "$REPLACEMENT" "$JUS_EMU_DIR/HOLDER"; }\n')
        r = self.stop('--force')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        a.wait(timeout=5)
        self.assertIsNone(b.poll())
        self.assertIn(str(b.pid), (self.ipc / 'HOLDER').read_text())

    def test_p2b_broad_zero_matches_keeps_live_holder(self):
        a = self.spawn()
        self.holder(a.pid, start_time(a.pid))
        r = self.stop('--all-melonds-i-am-sure', '^' + str(self.root) + '/nonexistent( |$)')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIsNone(a.poll())
        self.assertTrue((self.ipc / 'HOLDER').exists())

    def test_p2b_broad_zero_matches_clears_dead_holder(self):
        dead = subprocess.Popen(['true'])
        dead.wait()
        self.holder(dead.pid, 1)
        r = self.stop('--all-melonds-i-am-sure', '^' + str(self.root) + '/nonexistent( |$)')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((self.ipc / 'HOLDER').exists())

    @unittest.skipUnless(shutil.which('flock'), 'flock not installed')
    def test_p2b_stop_waits_for_the_ipc_lock(self):
        import fcntl
        a = self.spawn()
        self.holder(a.pid, start_time(a.pid))
        with open(self.ipc / '.lock', 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            p = subprocess.Popen(['bash', str(SCRIPTS / 'stop_emu.sh'), '--force'],
                                 env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.procs.append(p)
            time.sleep(1.0)
            self.assertIsNone(p.poll(), 'stop must wait for the lock')
            self.assertIsNone(a.poll())
        p.wait(timeout=10)
        a.wait(timeout=5)

    def test_p2c_missing_or_option_like_values_are_usage_errors(self):
        for args in (['--pid'], ['--pid', '--force'], ['--pid', ''], ['--pid', 'abc'],
                     ['--start-time'], ['--start-time', '--force'], ['--force', '--start-time', '']):
            with self.subTest(args=args):
                a = self.spawn()
                self.holder(a.pid, start_time(a.pid))
                r = self.stop(*args)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIsNone(a.poll(), 'recorded fake must survive a usage error')
                self.assertTrue((self.ipc / 'HOLDER').exists())


    # ---- round 3: fail closed on Linux, non-empty identity, no env lock bypass ----

    def sitecustomize(self, body):
        site = self.root / 'site'
        site.mkdir(exist_ok=True)
        (site / 'sitecustomize.py').write_text(body)
        self.env['PYTHONPATH'] = str(site)

    def assert_refused(self, r, p, rc=None):
        out = r.stdout + r.stderr
        if rc is None:
            self.assertNotEqual(r.returncode, 0, out)
        else:
            self.assertEqual(r.returncode, rc, out)
        self.assertIsNone(p.poll(), 'nothing may be signalled')
        self.assertTrue((self.ipc / 'HOLDER').exists(), 'HOLDER must be kept')

    def signals_sent(self):
        path = self.ipc / 'signals'
        lines = path.read_text().splitlines() if path.exists() else []
        return [ln for ln in lines if ln.startswith(('-TERM', '-KILL'))]

    def test_r3_p1_pidfd_open_permission_error_fails_closed(self):
        a = self.spawn()
        self.holder(a.pid, start_time(a.pid))
        self.sitecustomize(
            'import os\nfrom pathlib import Path\n'
            'def denied(pid):\n'
            '    Path(os.environ["JUS_EMU_DIR"], "pidfd-denied").touch()\n'
            '    raise PermissionError("injected pidfd_open denial")\n'
            'os.pidfd_open = denied\n')
        r = self.stop('--force')
        self.assertTrue((self.ipc / 'pidfd-denied').exists(), 'injection must reach the helper')
        self.assert_refused(r, a, rc=5)
        self.assertIn('pidfd', r.stderr)

    def test_r3_p1_pidfd_send_signal_oserror_fails_closed(self):
        a = self.spawn()
        self.holder(a.pid, start_time(a.pid))
        self.sitecustomize(
            'import signal\n'
            'def denied(fd, sig, *a):\n'
            '    raise PermissionError("injected pidfd_send_signal denial")\n'
            'signal.pidfd_send_signal = denied\n')
        self.assert_refused(self.stop('--force'), a, rc=5)

    def test_r3_p1_helper_rc5_with_identity_change_signals_nothing(self):
        a = self.spawn()
        self.holder(a.pid, start_time(a.pid))
        self.hook('python3() { proc_start() { echo replaced-start; }; return 5; }\n'
                  'kill() { echo "$@" >> "$JUS_EMU_DIR/signals"; builtin kill "$@"; }\n')
        self.assert_refused(self.stop('--force'), a, rc=5)
        self.assertEqual(self.signals_sent(), [])

    def test_r3_p1_missing_helper_fails_closed(self):
        scripts = self.root / 'nohelper'
        scripts.mkdir()
        for name in ('stop_emu.sh', 'stop_emu_lib.sh'):
            if (SCRIPTS / name).exists():
                shutil.copy2(SCRIPTS / name, scripts / name)
        a = self.spawn()
        self.holder(a.pid, start_time(a.pid))
        r = subprocess.run(['bash', str(scripts / 'stop_emu.sh'), '--force'], env=self.env,
                           capture_output=True, text=True, timeout=60)
        self.assert_refused(r, a, rc=5)

    def test_r3_p1_darwin_plain_kill_is_announced_and_revalidated(self):
        self.darwin()
        a = self.spawn(argv0='/Apps/melonDS.app/Contents/MacOS/melonDS', ignore_term=True)
        self.holder(a.pid, start_time(a.pid))
        self.hook('sleep() { proc_start() { echo reused-start; }; command sleep "$@"; }\n')
        r = self.stop('--force')
        self.assert_refused(r, a, rc=4)
        self.assertIn('plain kill', r.stderr)

    def test_r3_p2a_empty_argv0_refused_on_plain_kill_path(self):
        self.darwin()
        a = subprocess.Popen(['', '300'], executable=str(self.fake), start_new_session=True)
        self.procs.append(a)
        self.holder(a.pid, start_time(a.pid))
        self.hook('python3() { return 5; }\n')
        r = self.stop('--force')
        self.assert_refused(r, a, rc=4)
        self.assertIn('executable', r.stderr)

    def test_r3_p2a_empty_argv0_refused_by_shell_on_linux(self):
        a = subprocess.Popen(['', '300'], executable=str(self.fake), start_new_session=True)
        self.procs.append(a)
        self.holder(a.pid, start_time(a.pid))
        r = self.stop('--force')
        self.assert_refused(r, a, rc=4)
        self.assertIn('executable is not melonDS', r.stderr)

    def test_r3_p2a_failing_executable_reader_refused_on_plain_kill_path(self):
        self.darwin()
        a = self.spawn(argv0='/Apps/melonDS.app/Contents/MacOS/melonDS')
        self.holder(a.pid, start_time(a.pid))
        # The reader prints a valid-looking identity but fails: its status must count.
        self.hook('python3() { return 5; }\n'
                  'tr() { echo /Apps/melonDS.app/Contents/MacOS/melonDS; return 1; }\n')
        r = self.stop('--force')
        self.assert_refused(r, a, rc=4)

    @unittest.skipUnless(shutil.which('flock'), 'flock not installed')
    def test_r3_p2b_env_flag_cannot_bypass_a_held_lock(self):
        import fcntl
        for flag in ('1', '0', 'yes'):
            with self.subTest(flag=flag):
                a = self.spawn()
                self.holder(a.pid, start_time(a.pid))
                env = dict(self.env, JUS_EMU_LOCK_HELD=flag)
                with open(self.ipc / '.lock', 'w') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    p = subprocess.Popen(['bash', str(SCRIPTS / 'stop_emu.sh'), '--force'],
                                         env=env, stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
                    self.procs.append(p)
                    time.sleep(1.0)
                    self.assertIsNone(p.poll(), 'stop must wait for the lock')
                    self.assertIsNone(a.poll())
                    self.assertTrue((self.ipc / 'HOLDER').exists())
                self.assertEqual(p.wait(timeout=10), 0)
                a.wait(timeout=5)

    def test_r3_launch_without_flock_prints_note(self):
        self.hook('command() { if [ "$1" = -v ] && [ "$2" = flock ]; then return 1; fi;'
                  ' builtin command "$@"; }\n')
        r, _ = self.run_launch()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('flock not installed', r.stderr)

    @unittest.skipUnless(shutil.which('flock'), 'flock not installed')
    def test_r4_absent_ipc_dir_stop_cannot_act_inside_a_launch(self):
        """Absent IPC dir: a launch that starts while stop runs must not lose its process."""
        def wait_for(path, seconds):
            end = time.monotonic() + seconds
            while time.monotonic() < end and not path.exists():
                time.sleep(0.01)
            return path.exists()
        a = self.spawn()
        token = start_time(a.pid)
        self.ipc.rmdir()
        ready, go = self.root / 'stop-ready', self.root / 'stop-go'
        published, finish = self.root / 'published', self.root / 'finish'
        # Pause stop just before it resolves its target (after any lock decision).
        self.hook('trap \'if [[ "$BASH_COMMAND" = emu_stop_run ]]; then touch "$PAUSE_READY";'
                  ' while [ ! -f "$PAUSE_GO" ]; do command sleep .01; done; fi\' DEBUG\n')
        self.env.update(PAUSE_READY=str(ready), PAUSE_GO=str(go))
        stop = subprocess.Popen(['bash', str(SCRIPTS / 'stop_emu.sh'), '--force'], env=self.env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.procs.append(stop)
        self.assertTrue(wait_for(ready, 10), 'stop never reached its pause point')
        # A launcher does what launch_emu.sh does: mkdir, lock, publish HOLDER, hold the lock.
        launcher_env = {k: v for k, v in self.env.items() if k != 'BASH_ENV'}
        launcher_env.update(PID=str(a.pid), TOKEN=token, PUBLISHED=str(published),
                            FINISH=str(finish))
        launcher = subprocess.Popen(
            ['bash', '-c', 'mkdir -p "$JUS_EMU_DIR"; exec 9>"$JUS_EMU_DIR/.lock"; flock 9;'
             ' printf "launcher\\n%s\\nnow\\n%s\\n" "$PID" "$TOKEN" > "$JUS_EMU_DIR/HOLDER";'
             ' touch "$PUBLISHED"; while [ ! -f "$FINISH" ]; do sleep .01; done'],
            env=launcher_env)
        self.procs.append(launcher)
        try:
            wait_for(published, 2)    # unlocked stop: publishes now; locked stop: blocks
            go.touch()
            out, err = stop.communicate(timeout=20)
            self.assertTrue(wait_for(published, 10), 'launcher never got the lock')
            self.assertIsNone(a.poll(), 'stop killed the process a concurrent launch published:\n'
                              + out + err)
            self.assertEqual(stop.returncode, 0, out + err)
            self.assertTrue((self.ipc / 'HOLDER').exists())
        finally:
            finish.touch()
            launcher.wait(timeout=10)

if __name__ == '__main__':
    unittest.main()
