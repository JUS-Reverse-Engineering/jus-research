"""Exercise the real launcher without a ROM, GUI, or shared emulator lease."""

import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import unittest


LAUNCHER = Path(__file__).resolve().parents[1] / 'launch_emu.sh'


class LaunchLifetimeTest(unittest.TestCase):
    def test_emulator_survives_launch_runner_process_group_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy2(LAUNCHER, root / 'launch_emu.sh')
            # Isolate the launcher from real melonDS processes and shared IPC.
            (root / 'stop_emu_lib.sh').write_text(
                'emu_stop_parse() { :; }\nemu_stop_run() { exit 0; }\nemu_lease_guard() { return 0; }\n')
            (root / 'jus.nds').touch()
            binary = root / 'fake-emulator'
            binary.write_text(
                '#!/usr/bin/env python3\n'
                'import json, os, time\n'
                'from pathlib import Path\n'
                'root = Path(os.environ["JUS_EMU_DIR"])\n'
                'n = 0\n'
                'while True:\n'
                '    n += 1\n'
                '    tmp = root / "heartbeat.tmp"\n'
                '    tmp.write_text(json.dumps({"framecount": n}))\n'
                '    tmp.replace(root / "heartbeat.json")\n'
                '    time.sleep(0.05)\n'
            )
            binary.chmod(0o755)
            env = dict(os.environ, MELONDS=str(binary), ROM=str(root / 'jus.nds'),
                       JUS_EMU_DIR=str(root), JUS_EMU_HOLDER='lifetime-test')
            runner = subprocess.Popen(
                ['bash', str(root / 'launch_emu.sh'), '--keep-ipc'],
                env=env, start_new_session=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
            )
            pid = None
            try:
                stdout, stderr = runner.communicate(timeout=10)
                self.assertEqual(runner.returncode, 0, stdout + stderr)
                pid = int((root / 'emu.pid').read_text())
                before = json.loads((root / 'heartbeat.json').read_text())['framecount']
                # Command runners reclaim the launch command's process group.
                try:
                    os.killpg(runner.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                time.sleep(0.3)
                after = json.loads((root / 'heartbeat.json').read_text())['framecount']
                self.assertGreater(after, before,
                                   'emulator heartbeat stopped when launch runner was cleaned up')
                self.assertEqual(os.getpgid(pid), pid)
            finally:
                if runner.poll() is None:
                    os.killpg(runner.pid, signal.SIGKILL)
                    runner.communicate()
                if pid is None and (root / 'emu.pid').exists():
                    pid = int((root / 'emu.pid').read_text())
                if pid is not None:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass


if __name__ == '__main__':
    unittest.main()
