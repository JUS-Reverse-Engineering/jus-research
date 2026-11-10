"""Recreate the isolated native-media source without modifying the owner checkout."""
import argparse
import hashlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--repository', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[3]
evidence = repo / 'docs/research/feel-captures/16g-native-media-2026-10-05'
baseline = json.loads((evidence / 'baseline.json').read_text())
build = json.loads((evidence / 'build-manifest.json').read_text())
if a.out.exists():
    raise SystemExit('Refusing reused output directory')
a.out.mkdir(parents=True)
archive = subprocess.check_output(['git', '-C', str(a.repository), 'archive', baseline['base_revision']])
with tarfile.open(fileobj=io.BytesIO(archive)) as t:
    t.extractall(a.out, filter='data')
subprocess.run(['git', 'apply', str(evidence / 'owner-baseline.patch')], cwd=a.out, check=True)
(a.out / 'src/frontend/qt_sdl/lua/libs/LuaScreendump.cpp').write_bytes((evidence / 'owner-LuaScreendump.cpp').read_bytes())
for name, sha in baseline['files'].items():
    if hashlib.sha256((a.out / name).read_bytes()).hexdigest() != sha:
        raise SystemExit('Baseline mismatch: ' + name)
patch = evidence / 'native-media.patch'
if hashlib.sha256(patch.read_bytes()).hexdigest() != build['native_patch_sha256']:
    raise SystemExit('Native patch mismatch')
subprocess.run(['git', 'apply', str(patch)], cwd=a.out, check=True)
for item in build['changed_files']:
    if hashlib.sha256((a.out / item['path']).read_bytes()).hexdigest() != item['sha256']:
        raise SystemExit('Patched source mismatch: ' + item['path'])
print('Recreated', len(baseline['files']), 'baseline files and', len(build['changed_files']), 'patched files')
