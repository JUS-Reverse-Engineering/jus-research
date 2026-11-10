"""Private frontend config and process-owned listening socket witnesses."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from owned import Owned

try:
    import startup_identity as I
except ImportError:
    I = None


class StartupIdentity(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(I, 'private endpoint startup verification missing')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.config = self.root / 'config/melonDS/melonDS.toml'
        self.config.parent.mkdir(parents=True)

    def config_for(self, ports, enabled=True):
        self.config.write_text(f'[Instance0.Gdb]\nEnabled = {str(enabled).lower()}\n'
            f'[Instance0.Gdb.ARM9]\nPort = {ports[0]}\n[Instance0.Gdb.ARM7]\nPort = {ports[1]}\n')

    def test_config_ports_and_owned_listener_receipt(self):
        sockets = [socket.socket() for _ in range(2)]
        for s in sockets:
            self.addCleanup(s.close)
            s.bind(('127.0.0.1', 0))
            s.listen()
        ports = [s.getsockname()[1] for s in sockets]
        self.config_for(ports)
        self.assertEqual(I.config_ports(self.config), ports)
        receipt = I.receipt(self.config, os.getpid(), self.root)
        self.assertEqual(receipt['ports'], ports)
        self.assertEqual(receipt['pid'], os.getpid())
        sockets[1].close()
        with self.assertRaisesRegex(ValueError, 'listening'):
            I.receipt(self.config, os.getpid(), self.root)

    def test_disabled_duplicate_and_unowned_endpoints_refused(self):
        self.config_for([15335, 15336], enabled=False)
        with self.assertRaises(ValueError):
            I.config_ports(self.config)
        self.config_for([15335, 15335])
        with self.assertRaises(ValueError):
            I.config_ports(self.config)
        self.config_for([15335, 15336])
        with self.assertRaisesRegex(ValueError, 'listening'):
            I.receipt(self.config, os.getpid(), self.root)

    def test_invalid_endpoint_values(self):
        for value in ('true', '3333.0', '"3333"', '1023', '65536'):
            self.config_for([15335, 15336])
            self.config.write_text(self.config.read_text().replace('Port = 15335', 'Port = ' + value))
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'private debugger'):
                I.config_ports(self.config)

    def test_port_collision_and_wrong_config_location_refused_before_launch(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.config_for([sock.getsockname()[1], 15336])
            with self.assertRaises(OSError):
                I.preflight(self.config, self.config.parent.parent, '/usr/bin/python3')
        self.config_for([15335, 15336])
        with self.assertRaises(ValueError):
            I.preflight(self.config, self.root / 'elsewhere', '/usr/bin/python3')
        (self.root / 'bin/portable').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'portable'):
            I.preflight(self.config, self.config.parent.parent, self.root / 'bin/melonDS')

    def test_listeners_must_belong_to_exact_pid_and_holder_start(self):
        child = subprocess.Popen([sys.executable, '-B', '-c',
            'import socket, json, sys; s=[socket.socket(),socket.socket()]; '
            '[x.bind(("127.0.0.1",0)) for x in s]; [x.listen() for x in s]; '
            'print(json.dumps([x.getsockname()[1] for x in s]),flush=True); sys.stdin.read()'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        try:
            ports = json.loads(child.stdout.readline())
            self.config_for(ports)
            with self.assertRaisesRegex(ValueError, 'listening'):
                I.receipt(self.config, os.getpid(), self.root)
            actual = I.receipt(self.config, child.pid, self.root)
            self.assertEqual(actual['pid'], child.pid)
            (self.root / 'HOLDER').write_text(f'owned\n{child.pid}\nnow\nwrong-start\n')
            with patch.dict(os.environ, JUS_EMU_DIR=str(self.root)), \
                 patch.object(I.Owned, 'from_env', return_value=Owned()), \
                 patch.object(sys, 'argv', ['startup_identity', 'receipt', str(self.config), '--pid', str(child.pid)]):
                with self.assertRaisesRegex(ValueError, 'identity changed'):
                    I.main()
        finally:
            child.stdin.close()
            child.wait(timeout=5)
            child.stdout.close()


if __name__ == '__main__':
    unittest.main()
