"""Recreate the native-hooks source (call log + list walks) over the pinned replay instrument.

Runs prepare_replay_build.py, then applies native-hooks.patch after checking it
against the sha256 pinned in build_info.linux.json (`hooks_layer`). The patched
NativeHooks.h must equal the repo copy that test_native_hooks.cpp exercises.
Then applies the separately pinned GDB EOF fix over its recorded input hash.
The reconnect layer resets per-connection protocol state over that verified source.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--repository', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
layer = json.loads((HERE / 'build_info.linux.json').read_text())['hooks_layer']
patch = HERE / 'native-hooks.patch'
if sha(patch) != layer['patch_sha256']:
    raise SystemExit('native-hooks.patch changed since build_info.linux.json')
subprocess.run([sys.executable, str(HERE / 'prepare_replay_build.py'),
                '--repository', str(a.repository), '--out', str(a.out)], check=True)
subprocess.run(['git', 'apply', str(patch)], cwd=a.out, check=True)
header = a.out / 'src/frontend/qt_sdl/NativeHooks.h'
if sha(header) != sha(HERE / 'NativeHooks.h'):
    raise SystemExit('patched NativeHooks.h differs from scripts/emu/native_media/NativeHooks.h')
for path, digest in layer['changed_files'].items():
    if sha(a.out / path) != digest:
        raise SystemExit('hooks source mismatch: ' + path)
print('Applied native-hooks.patch;', len(layer['changed_files']), 'files match the build record')
fix = layer['gdb_eof_fix']
eof_patch = HERE / Path(fix['patch']).name
if sha(eof_patch) != fix['patch_sha256']:
    raise SystemExit('gdb-eof.patch changed since build_info.linux.json')
if sha(a.out / 'src/debug/GdbProto.cpp') != fix['before_sha256']:
    raise SystemExit('GDB EOF baseline changed')
for path, digest in fix['before_files'].items():
    if sha(a.out / path) != digest:
        raise SystemExit('GDB disconnect baseline changed: ' + path)
subprocess.run(['git', 'apply', '--unidiff-zero', str(eof_patch)], cwd=a.out, check=True)
for path, digest in fix['changed_files'].items():
    if sha(a.out / path) != digest:
        raise SystemExit('GDB EOF source mismatch: ' + path)
print('Applied gdb-eof.patch;', len(fix['changed_files']), 'files match the build record')
reconnect = layer['gdb_reconnect_fix']
reconnect_patch = HERE / Path(reconnect['patch']).name
stub = a.out / 'src/debug/GdbStub.cpp'
if sha(reconnect_patch) != reconnect['patch_sha256']:
    raise SystemExit('gdb-reconnect.patch changed since build_info.linux.json')
if sha(stub) != reconnect['before_sha256']:
    raise SystemExit('GDB reconnect baseline changed')
subprocess.run(['git', 'apply', str(reconnect_patch)], cwd=a.out, check=True)
if sha(stub) != reconnect['changed_sha256']:
    raise SystemExit('GDB reconnect source mismatch')
print('Applied gdb-reconnect.patch; stub matches the build record')
