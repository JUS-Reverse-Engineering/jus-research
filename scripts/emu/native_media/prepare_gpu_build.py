"""Recreate the native GPU-media source (consumed OAM/VRAM/palette stream) over the pinned hooks instrument.

Runs prepare_hooks_build.py, then applies native-gpu.patch after checking it against the sha256 pinned in
build_info.linux.json (`gpu_layer`). The patched NativeGpuMedia.h must equal the repo copy that
test_native_capture.cpp exercises.
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
layer = json.loads((HERE / 'build_info.linux.json').read_text())['gpu_layer']
patch = HERE / 'native-gpu.patch'
if sha(patch) != layer['patch_sha256']:
    raise SystemExit('native-gpu.patch changed since build_info.linux.json')
subprocess.run([sys.executable, str(HERE / 'prepare_hooks_build.py'),
                '--repository', str(a.repository), '--out', str(a.out)], check=True)
subprocess.run(['git', 'apply', str(patch)], cwd=a.out, check=True)
header = a.out / 'src/frontend/qt_sdl/NativeGpuMedia.h'
if sha(header) != sha(HERE / 'NativeGpuMedia.h'):
    raise SystemExit('patched NativeGpuMedia.h differs from scripts/emu/native_media/NativeGpuMedia.h')
for path, digest in layer['changed_files'].items():
    if sha(a.out / path) != digest:
        raise SystemExit('gpu source mismatch: ' + path)
print('Applied native-gpu.patch;', len(layer['changed_files']), 'files match the build record')
