"""Verify a private melonDS config and both process-owned GDB listeners."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import tomllib

import lease
from owned import Owned


def config_ports(config):
    gdb = tomllib.loads(Path(config).read_text())['Instance0']['Gdb']
    ports = [gdb[cpu]['Port'] for cpu in ('ARM9', 'ARM7')]
    if (gdb['Enabled'] is not True or any(type(p) is not int or not 1024 <= p <= 65535 for p in ports)
            or len(set(ports)) != 2):
        raise ValueError('private debugger must enable two distinct nonprivileged ports')
    return ports


def preflight(config, xdg, binary):
    config = Path(config).resolve()
    if config != Path(xdg).resolve() / 'melonDS/melonDS.toml':
        raise ValueError('private config differs from XDG_CONFIG_HOME')
    if (Path(binary).resolve().parent / 'portable').exists():
        raise ValueError('portable config would override XDG_CONFIG_HOME')
    for port in config_ports(config):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', port))


def listening_ports(pid):
    sockets = set()
    for fd in Path(f'/proc/{pid}/fd').iterdir():
        try:
            target = fd.readlink().as_posix()
            if target.startswith('socket:['):
                sockets.add(target[8:-1])
        except FileNotFoundError:
            continue
    ports = set()
    for protocol in ('tcp', 'tcp6'):
        for line in Path(f'/proc/{pid}/net/{protocol}').read_text().splitlines()[1:]:
            row = line.split()
            if row[3] == '0A' and row[9] in sockets:
                ports.add(int(row[1].rsplit(':', 1)[1], 16))
    return ports


def receipt(config, pid, ipc):
    ports = config_ports(config)
    if not set(ports) <= listening_ports(pid):
        raise ValueError('pinned emulator does not own both listening debugger endpoints')
    return dict(pid=pid, start=lease.proc_start(pid), binary=os.path.realpath(f'/proc/{pid}/exe'),
                config=str(Path(config).resolve()), xdg_config_home=os.environ.get('XDG_CONFIG_HOME'),
                config_sha256=hashlib.sha256(Path(config).read_bytes()).hexdigest(), ports=ports,
                ipc=str(Path(ipc).resolve()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'receipt'))
    parser.add_argument('config')
    parser.add_argument('--pid', type=int)
    args = parser.parse_args()
    if args.action == 'preflight':
        preflight(args.config, os.environ['XDG_CONFIG_HOME'], os.environ['MELONDS'])
    else:
        ipc = Path(os.environ['JUS_EMU_DIR'])
        with Owned.from_env(ipc).section():
            data = receipt(args.config, args.pid, ipc)
            holder = (ipc / 'HOLDER').read_text().splitlines()
            if int(holder[1]) != data['pid'] or holder[3] != data['start']:
                raise ValueError('emulator identity changed during startup')
            lease._atomic_write(ipc / 'runtime.json', json.dumps(data, sort_keys=True))


if __name__ == '__main__':
    main()
