"""Decoder-free five-transition oracle over committed lossless call and FXO rows."""
import gzip
import json
from pathlib import Path
import struct
import sys

FIXTURES = Path(__file__).resolve().parents[3] / 'scripts/emu/native_media/plans/fixtures'
FXO = [FIXTURES / 'train-fxo1-all.jsonl.gz', FIXTURES / 'train-fxo2-all.jsonl.gz']
TICKS = (13, 78, 82, 98, 102)
EL = 0x023BF988
BEGIN, VISIT, TARGET = 0x0207B414, 0x0207B4C4, 0x02079EFC
STORES = (0x02079E7C, 0x02079EA0, 0x02079EC0, 0x02079ED8)


def signed(value):
    return struct.unpack('<h', (value & 65535).to_bytes(2, 'little'))[0]


def calls():
    with gzip.open(FIXTURES / 'train-kind25-w4.json.gz', 'rt') as f:
        return json.load(f)['calls']


def clocks():
    with gzip.open(FIXTURES / 'train-kind25-w4.json.gz', 'rt') as f:
        return [row['w']['gfc'] for row in json.load(f)['rows']]


def fxo(path, wanted):
    frame, found = {}, {}
    for line in gzip.open(path, 'rt'):
        if not line.startswith('{'):
            continue
        row = json.loads(line)
        if row.get('type') == 'frame':
            frame[row['frame']] = row['gfc']
        elif row.get('type') == 'elem' and row.get('record') == 16 and row.get('elem') == '0x23bf988':
            gfc = frame.get(row['frame'])
            if gfc in wanted:
                found[gfc] = row['sub'][0]
    return found


def run():
    stream, gfc = calls(), clocks()
    starts = [i for i, c in enumerate(stream) if c['pc'] == BEGIN]
    assert len(starts) == len(gfc) == 172
    assert all(b - a == 1 for a, b in zip(gfc, gfc[1:]))
    results = {}
    for t in TICKS:
        lo, hi = starts[t], starts[t + 1]
        visit = next(i for i in range(lo, hi) if stream[i]['pc'] == VISIT and stream[i]['r5'] == EL)
        writes = []
        for i in range(lo + 4, hi):
            c = stream[i]
            if c['pc'] == TARGET and c['r0'] == EL and c['r2'] == 0:
                preceding = stream[i - 4:i]
                assert [x['pc'] for x in preceding] == list(STORES)
                rect = [signed(x['r1'] if j == 1 else x['r3']) for j, x in enumerate(preceding)]
                writes.append((i, rect, c['sequence']))
        if '--mutate-emulator' in sys.argv:
            writes = [w for w in writes if w[2] == t]
        assert len(writes) == 1, (t, writes)
        i, rect, seq = writes[0]
        assert i > visit
        results[t] = dict(gfc=gfc[t], writer_index=i, writer_sequence=seq, post_write=rect)
    for run, path in enumerate(FXO, 1):
        values = fxo(path, {x['gfc'] for x in results.values()})
        assert len(values) == 5
        for t, result in results.items():
            assert values[result['gfc']] == result['post_write'], (run, t, result, values[result['gfc']])
    assert results[78]['writer_sequence'] == 79
    print(json.dumps(results, sort_keys=True))


if __name__ == '__main__':
    run()
