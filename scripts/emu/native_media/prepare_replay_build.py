"""Recreate the native replay extension over the pinned v1 instrument."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--repository', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
repo = Path(__file__).resolve().parents[3]
evidence = repo / 'docs/research/feel-captures/16g-native-replay-2026-10-05'
manifest = json.loads((evidence / 'build-manifest.json').read_text())
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
v1 = repo / 'docs/research/feel-captures/16g-native-media-2026-10-05/build-manifest.json'
if sha(v1) != manifest['v1_build_manifest_sha256']:
    raise SystemExit('v1 manifest changed')
patch = evidence / 'native-replay.patch'
if sha(patch) != manifest['replay_patch_sha256']:
    raise SystemExit('replay patch changed')
subprocess.run([sys.executable, str(Path(__file__).with_name('prepare_build.py')),
                '--repository', str(a.repository), '--out', str(a.out)], check=True)
for item in manifest['changed_files']:
    path = a.out / item['path']
    before = sha(path) if path.exists() else None
    if before != item['before_sha256']:
        raise SystemExit('replay baseline changed: ' + item['path'])
subprocess.run(['git', 'apply', str(patch)], cwd=a.out, check=True)
for item in manifest['changed_files']:
    if sha(a.out / item['path']) != item['sha256']:
        raise SystemExit('replay source mismatch: ' + item['path'])
print('Recreated', len(manifest['changed_files']), 'replay source files exactly')
