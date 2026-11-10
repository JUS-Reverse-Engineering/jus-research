"""Validate one raw native recorder bundle without inferring gameplay parity."""
import csv
import hashlib
import json
import struct
import zlib
from pathlib import Path


def _reachable(address, length, aligned=False):
    return 0x02000000 <= address and address + length <= 0x02400000 and (not aligned or address % 4 == 0)


def validate_hooks(folder, nds_frames, calls, lists, read_csv, require):
    """Check the NativeHooks.h files against the requested recipe; return decoded calls and list walks.

    calls: ARM9 instruction addresses. lists: [{'name', 'address', 'offsets', 'next', 'limit',
    'fields': [{'name', 'path', 'length', 'optional'?}]}]. nds_frames[i] is frames.tsv row i's nds_frame.
    """
    calls, lists = sorted(set(calls or [])), list(lists or [])
    present = (folder / 'hooks.json').exists()
    require(present == bool(calls or lists), 'hook files and hook expectation disagree')
    if not present:
        return {}
    require(json.loads((folder / 'hooks.json').read_text()) == {'version': 1, 'call_pcs': len(calls), 'lists': len(lists)},
            'hooks.json mismatch')
    out = {}
    if calls:
        require([int(r['pc']) for r in read_csv('call-pcs.tsv', ['pc'])] == calls, 'call pc registration mismatch')
        columns = ['sequence', 'nds_frame', 'pc', 'insn'] + [f'r{i}' for i in range(8)] + ['lr']
        decoded, last = [], 0
        for row in read_csv('calls.tsv', columns):
            row = {k: int(v) for k, v in row.items()}
            seq = row['sequence']
            require(last <= seq < len(nds_frames) and row['nds_frame'] == nds_frames[seq], 'call row frame mismatch')
            require(row['pc'] in calls and all(0 <= row[k] <= 0xFFFFFFFF for k in columns[2:]), 'call row value mismatch')
            decoded.append(row)
            last = seq
        out['calls'] = decoded
    else:
        require(not (folder / 'calls.tsv').exists(), 'unexpected calls.tsv')
    if lists:
        registered = read_csv('lists.tsv', ['list', 'address', 'offsets', 'next', 'limit', 'fields'])
        expect = [{'list': str(i), 'address': str(l['address']), 'offsets': ','.join(map(str, l['offsets'])),
                   'next': str(l['next']), 'limit': str(l['limit']),
                   'fields': ';'.join(f"{','.join(map(str, f['path']))}:{f['length']}:{int(f.get('optional', False))}"
                                      for f in l['fields'])} for i, l in enumerate(lists)]
        require(registered == expect, 'list recipe registration mismatch')
        heads = read_csv('list-frames.tsv', ['sequence', 'nds_frame', 'list', 'present', 'count', 'truncated', 'head_path'])
        nodes = read_csv('list-nodes.tsv', ['sequence', 'nds_frame', 'list', 'node', 'address', 'next',
                                            'field_present', 'field_addresses', 'data_hex'])
        require(len(heads) == len(nds_frames) * len(lists), 'missing list frame rows')
        walks = {l['name']: [] for l in lists}
        cursor = 0
        for h_index, head in enumerate(heads):
            seq, index = divmod(h_index, len(lists))
            recipe = lists[index]
            require([int(head['sequence']), int(head['nds_frame']), int(head['list'])] == [seq, nds_frames[seq], index],
                    'list frame row order mismatch')
            here, count, truncated = head['present'], int(head['count']), head['truncated']
            require(here in ('0', '1') and truncated in ('0', '1') and 0 <= count <= recipe['limit'], 'invalid list frame row')
            path = [[int(x) for x in pair.split(':')] for pair in head['head_path'].split(',')]
            address, first = recipe['address'], None
            for hop, (location, value) in enumerate(path):
                require(location == address and _reachable(location, 4, True), 'list head path mismatch')
                if hop < len(recipe['offsets']):
                    if value == 0:
                        require(here == '0' and hop == len(path) - 1, 'list head null mismatch')
                        break
                    require(_reachable(value, 4, True), 'list head pointer unreachable')
                    address = value + recipe['offsets'][hop]
                else:
                    require(hop == len(path) - 1, 'list head path too long')
                    first = value
            require((here == '1') == (first is not None), 'list presence mismatch')
            require(count == 0 or first, 'empty head with nodes')
            walk = {'present': here == '1', 'count': count, 'truncated': truncated == '1', 'nodes': []}
            expected = first or 0
            for n in range(count):
                require(cursor < len(nodes), 'missing list node rows')
                node = nodes[cursor]
                cursor += 1
                require([int(node[k]) for k in ('sequence', 'nds_frame', 'list', 'node')] == [seq, nds_frames[seq], index, n],
                        'list node row order mismatch')
                node_address, link = int(node['address']), int(node['next'])
                require(node_address == expected and _reachable(node_address, 4, True), 'list node link mismatch')
                flags, addresses = node['field_present'], [int(x) for x in node['field_addresses'].split(',')]
                data = bytes.fromhex(node['data_hex'])
                fields = recipe['fields']
                require(len(flags) == len(fields) == len(addresses) and set(flags) <= {'0', '1'}
                        and len(data) == sum(f['length'] for f in fields), 'list node shape mismatch')
                decoded, at = {'address': node_address, 'next': link}, 0
                for f, flag, field_address in zip(fields, flags, addresses):
                    chunk = data[at:at + f['length']]
                    at += f['length']
                    if flag == '1':
                        require(_reachable(field_address, f['length'])
                                and (len(f['path']) > 1 or field_address == node_address + f['path'][0]), 'list field address mismatch')
                        decoded[f['name']] = int.from_bytes(chunk, 'little') if f['length'] <= 4 else list(chunk)
                    else:
                        require(f.get('optional', False) and field_address == 0 and chunk == bytes(len(chunk)),
                                'absent list field mismatch')
                        decoded[f['name']] = None
                walk['nodes'].append(decoded)
                expected = link
            require(expected == 0 if truncated == '0' else (count == recipe['limit'] and expected != 0),
                    'list termination mismatch')
            walks[recipe['name']].append(walk)
        require(cursor == len(nodes), 'extra list node rows')
        out['lists'] = walks
    else:
        require(not (folder / 'lists.tsv').exists(), 'unexpected lists.tsv')
    return out


GPU_LINES = 192
GPU_KINDS = {'oam': 1024, 'pal': 512, 'extpal': 8192, 'page': 1024}
GPU_SPEC = {'version': 1, 'page_bytes': 1024, 'vram_pages': [256, 128],
            'sprite_reg_bytes': 12, 'compose_reg_bytes': 36, 'post_reg_bytes': 18}
GPU_STREAMS = ((0, 'obj'), (0, 'compose'), (1, 'obj'), (1, 'compose'))


def validate_gpu(folder, nds_frames, read_csv, require):
    """Check the NativeGpuMedia.h files; return blobs, VRAM sets and per-frame consumed spans.

    Every blob is re-read and its CRC-32 checked. Every frame must carry, per engine,
    obj and compose spans covering output lines 0..191 exactly once. The one allowed
    hole is obj line 0 of sequence 0, consumed before the capture began (observed=0).
    """
    frames = len(nds_frames)
    spec = json.loads((folder / 'gpu-media.json').read_text())
    require(spec == {**GPU_SPEC, 'frames': frames}, 'gpu-media.json mismatch')
    raw = (folder / 'gpu-blobs.bin').read_bytes()
    blobs, kinds, seen, offset = {}, {}, set(), 0
    for i, row in enumerate(read_csv('gpu-blobs.tsv', ['blob', 'kind', 'offset', 'length', 'crc32'])):
        kind, at, length = row['kind'], int(row['offset']), int(row['length'])
        require(int(row['blob']) == i and kind in GPU_KINDS and length == GPU_KINDS[kind] and at == offset,
                'gpu blob index mismatch')
        data = raw[at:at + length]
        require(len(data) == length and zlib.crc32(data) == int(row['crc32']), 'gpu blob checksum mismatch')
        require((kind, data) not in seen, 'duplicate gpu blob')
        seen.add((kind, data))
        blobs[i], kinds[i] = data, kind
        offset += length
    require(offset == len(raw), 'unindexed gpu blob bytes')
    def ref(value, kind):
        require(value.isdigit() and kinds.get(int(value)) == kind, 'gpu span reference mismatch')
        return int(value)
    sets, set_keys = {}, set()
    for i, row in enumerate(read_csv('gpu-vram-sets.tsv', ['set', 'engine', 'pages'])):
        engine = int(row['engine'])
        pages = [ref(p, 'page') for p in row['pages'].split(',')]
        require(int(row['set']) == i and engine in (0, 1) and len(pages) == GPU_SPEC['vram_pages'][engine],
                'gpu vram set mismatch')
        require((engine, tuple(pages)) not in set_keys, 'duplicate gpu vram set')
        set_keys.add((engine, tuple(pages)))
        sets[i] = {'engine': engine, 'pages': pages}
    post = (folder / 'gpu-post.bin').read_bytes()
    require(len(post) == frames * 4096, 'gpu post-frame record count mismatch')
    rows = read_csv('gpu-frames.tsv', ['sequence', 'nds_frame', 'post_crc32', 'post_regs_hex'])
    require(len(rows) == frames, 'missing gpu frame rows')
    out = []
    for i, row in enumerate(rows):
        record = post[i * 4096:(i + 1) * 4096]
        require(int(row['sequence']) == i and int(row['nds_frame']) == nds_frames[i], 'gpu frame row mismatch')
        require(zlib.crc32(record) == int(row['post_crc32']), 'gpu post-frame checksum mismatch')
        require(len(row['post_regs_hex']) == 2 * GPU_SPEC['post_reg_bytes'], 'gpu post register length mismatch')
        out.append({'sequence': i, 'nds_frame': nds_frames[i], 'post_oam': (record[:1024], record[1024:2048]),
                    'post_pal': record[2048:], 'post_regs': bytes.fromhex(row['post_regs_hex']),
                    'spans': {key: [] for key in GPU_STREAMS}})
    spans = read_csv('gpu-spans.tsv', ['sequence', 'nds_frame', 'engine', 'stream', 'first_line', 'last_line',
                                       'observed', 'oam', 'vram_set', 'pal', 'extpal', 'regs_hex'])
    order = []
    for row in spans:
        seq, engine, stream = int(row['sequence']), int(row['engine']), row['stream']
        require(0 <= seq < frames and int(row['nds_frame']) == nds_frames[seq] and (engine, stream) in GPU_STREAMS,
                'gpu span row mismatch')
        group = (seq, GPU_STREAMS.index((engine, stream)))
        require(not order or order[-1] <= group, 'gpu span rows out of order')
        order.append(group)
        first, last = int(row['first_line']), int(row['last_line'])
        require(0 <= first <= last < GPU_LINES and row['observed'] in ('0', '1'), 'gpu span lines invalid')
        if row['observed'] == '0':
            require(seq == 0 and stream == 'obj' and first == last == 0
                    and all(row[k] == '-' for k in ('oam', 'vram_set', 'pal', 'extpal', 'regs_hex')),
                    'unobserved gpu span outside the capture start')
            span = {'first': 0, 'last': 0, 'observed': False}
        elif stream == 'obj':
            require(row['pal'] == row['extpal'] == '-' and row['vram_set'].isdigit()
                    and sets.get(int(row['vram_set']), {}).get('engine') == engine
                    and len(row['regs_hex']) == 2 * GPU_SPEC['sprite_reg_bytes'], 'gpu obj span mismatch')
            span = {'first': first, 'last': last, 'observed': True, 'oam': ref(row['oam'], 'oam'),
                    'vram_set': int(row['vram_set']), 'regs': bytes.fromhex(row['regs_hex'])}
        else:
            require(row['oam'] == row['vram_set'] == '-' and len(row['regs_hex']) == 2 * GPU_SPEC['compose_reg_bytes'],
                    'gpu compose span mismatch')
            span = {'first': first, 'last': last, 'observed': True, 'pal': ref(row['pal'], 'pal'),
                    'extpal': ref(row['extpal'], 'extpal'), 'regs': bytes.fromhex(row['regs_hex'])}
        out[seq]['spans'][(engine, stream)].append(span)
    content = lambda s: {k: v for k, v in s.items() if k not in ('first', 'last')}
    for frame in out:
        for key, group in frame['spans'].items():
            expect = 0
            for a, b in zip(group, group[1:]):
                require(content(a) != content(b), 'gpu spans not merged')
            for span in group:
                require(span['first'] == expect, 'gpu scanline coverage mismatch')
                expect = span['last'] + 1
            require(expect == GPU_LINES, 'gpu scanline coverage mismatch')
    return {'blobs': blobs, 'sets': sets, 'frames': out}


def gpu_vram(gpu, set_id):
    """The OBJ VRAM bytes of one consumed VRAM set (256 KiB main, 128 KiB sub)."""
    return b''.join(gpu['blobs'][p] for p in gpu['sets'][set_id]['pages'])


def gpu_phase(gpu):
    """Per frame and engine: consumed span counts and how consumed OAM relates to post-frame OAM.

    `line0_eq_prev_post` compares OAM consumed for output line 0 with the post-frame OAM
    recorded after the previous RunFrame; `eq_post` with the post-frame OAM of the same frame.
    None means not measurable (first frame, or line 0 unobserved).
    """
    rows = []
    for i, frame in enumerate(gpu['frames']):
        for engine in (0, 1):
            obj = frame['spans'][(engine, 'obj')]
            line0 = obj[0]
            consumed = gpu['blobs'][line0['oam']] if line0['observed'] else None
            prev = gpu['frames'][i - 1]['post_oam'][engine] if i else None
            rows.append({'sequence': i, 'engine': engine, 'obj_spans': len(obj),
                         'oam_versions': len({s['oam'] for s in obj if s['observed']}),
                         'compose_spans': len(frame['spans'][(engine, 'compose')]),
                         'line0_eq_prev_post': None if consumed is None or prev is None else consumed == prev,
                         'eq_post': None if consumed is None else consumed == frame['post_oam'][engine]})
    return rows


def validate(folder, frames, watches, key_mask, calls=None, lists=None, gpu=False):
    folder = Path(folder)
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    def read_csv(name, columns):
        with (folder / name).open() as f:
            reader = csv.DictReader(f, delimiter='\t')
            rows = list(reader)
            require(reader.fieldnames == columns, name + ': schema mismatch')
        require(all(None not in row and all(value is not None for value in row.values()) for row in rows), name + ': malformed row')
        return rows
    require(type(frames) is int and 1 <= frames <= 4096, 'invalid expected frame count')
    masks = [key_mask] * frames if type(key_mask) is int else list(key_mask)
    require(len(masks) == frames and all(type(m) is int and 0 <= m <= 4095 for m in masks), 'invalid expected input schedule')
    require(len(watches) <= 64 and all(type(w['len']) is int and 1 <= w['len'] <= 512 for w in watches)
            and sum(w['len'] for w in watches) <= 512, 'watch budget')
    require(len({w['name'] for w in watches}) == len(watches), 'duplicate watch name')
    extended = (folder / 'schema.json').exists()
    require(extended or (type(key_mask) is int and not any('chain' in w for w in watches)), 'extended schema missing')
    recipes = []
    for w in watches:
        chain = w.get('chain')
        require(chain is None or 2 <= len(chain) <= 9, 'invalid chain depth')
        address, offsets = (chain[0], chain[1:]) if chain else (w['addr'], [])
        offset, optional = w.get('offset', 0), w.get('optional', False)
        require(type(optional) is bool and type(address) is int and 0x02000000 <= address < 0x02400000, 'invalid watch recipe')
        require(all(type(o) is int and -(1 << 31) <= o < (1 << 31) for o in [*offsets, offset]), 'invalid watch offset')
        require(not offsets or address % 4 == 0 and address + 4 <= 0x02400000, 'invalid pointer root')
        require(not optional or offsets, 'optional direct watch')
        if not offsets:
            require(address + w['len'] <= 0x02400000 and 0x02000000 <= address + offset
                    and address + offset + w['len'] <= 0x02400000, 'unreachable direct watch')
            require(extended or offset == 0, 'unsupported legacy watch offset')
        recipes.append((address, w['len'], offsets, offset, optional))
    expected = [(r[0], r[1]) for r in recipes]
    registered = read_csv('watches.tsv', ['address', 'length', 'offsets', 'offset', 'optional'] if extended else ['address', 'length'])
    require(extended or not (folder / 'input-schedule.tsv').exists(), 'v2 schedule requires schema')
    require([(int(w['address']), int(w['length'])) for w in registered] == expected, 'watch registration mismatch')
    if extended:
        schema = json.loads((folder / 'schema.json').read_text())
        require(schema == {'version': 2, 'frames': frames, 'watch_count': len(watches)} and all(type(x) is int for x in schema.values()), 'extended schema mismatch')
        require(all(w['optional'] in ('0', '1') for w in registered), 'invalid optional registration')
        registered_recipes = [(int(w['address']), int(w['length']),
            [int(o) for o in w['offsets'].split(',')] if w['offsets'] else [], int(w['offset']), bool(int(w['optional']))) for w in registered]
        require(registered_recipes == recipes, 'watch recipe registration mismatch')
        schedule = read_csv('input-schedule.tsv', ['sequence', 'key_mask'])
        require([(int(r['sequence']), int(r['key_mask'])) for r in schedule] == list(enumerate(masks)), 'input schedule registration mismatch')
    options = read_csv('audio-options.tsv', ['period', 'interpolation', 'degrade_10bit', 'apply_bias'])
    require(len(options) == 1, 'audio options missing')
    options = {k: int(v) for k, v in options[0].items()}
    period = options['period']
    require(period in (704, 1024) and options['interpolation'] in range(5)
            and options['degrade_10bit'] in (0, 1) and options['apply_bias'] in (0, 1), 'invalid audio options')
    status = json.loads((folder / 'status.json').read_text())
    require(status['state'] == 'complete' and status['error'] == '' and status['frames'] == frames, 'recording incomplete')
    raw = (folder / 'audio.bin').read_bytes()
    require(len(raw) % 16 == 0, 'trailing audio bytes')
    samples = list(struct.iter_unpack('<QIhh', raw))
    require(len(samples) == status['audio_packets'] and samples, 'missing audio packets')
    require(all(b[0] > a[0] and b[0] - a[0] == b[1] for a, b in zip(samples, samples[1:])), 'audio clock discontinuity')
    require(all(s[1] == period for s in samples), 'zero audio interval')
    original_headers = ['sequence', 'nds_frame', 'start_tick', 'end_tick', 'key_mask', 'audio_offset', 'audio_count', 'ram_hex', 'held_left', 'held_right']
    records = read_csv('frames.tsv', original_headers + (['watch_present', 'watch_addresses', 'watch_paths'] if extended else []))
    require(len(records) == frames, 'missing frame rows')
    require({p.name for p in folder.glob('*.ppm')} == {f'{i:06d}.ppm' for i in range(frames)}, 'native image count mismatch')
    decoded = []
    offset = 0
    previous_end = None
    previous_frame = None
    last_held = None
    for i, row in enumerate(records):
        seq, frame, start, end, mask, begin, count = [int(row[k]) for k in ('sequence', 'nds_frame', 'start_tick', 'end_tick', 'key_mask', 'audio_offset', 'audio_count')]
        held = (int(row['held_left']), int(row['held_right']))
        require(seq == i and end > start and mask == masks[i], 'frame/input mismatch')
        if i:
            require(start == previous_end and frame == previous_frame + 1, 'frame clock discontinuity')
            require(held == last_held, 'held audio state discontinuity')
        require(begin == offset and 0 < count <= 2048 and offset + count <= len(samples), 'audio range mismatch')
        chunk = samples[offset:offset + count]
        require(all(start < s[0] <= end for s in chunk), 'audio outside frame boundary')
        require(chunk[0][0] - start <= period and end - chunk[-1][0] < period, 'audio boundary coverage gap')
        ram = bytes.fromhex(row['ram_hex'])
        require(len(ram) == sum(w['len'] for w in watches), 'watch length mismatch')
        values = {}
        resolutions = {}
        pos = 0
        if extended:
            flags = row.get('watch_present', '')
            addresses = [int(x) for x in row.get('watch_addresses', '').split(',')] if watches else []
            paths = row.get('watch_paths', '').split(';') if watches else []
            require(len(flags) == len(watches) and set(flags) <= {'0', '1'} and len(addresses) == len(watches) and len(paths) == len(watches), 'missing watch provenance')
        for index, w in enumerate(watches):
            data = ram[pos:pos + w['len']]
            present = True
            if extended:
                address, length, offsets, final_offset, optional = recipes[index]
                path = [] if paths[index] == '-' else [[int(x) for x in pair.split(':')] for pair in paths[index].split(',')]
                require(len(path) <= len(offsets) and all(len(pair) == 2 for pair in path), 'invalid pointer path')
                for hop, step in enumerate(offsets):
                    require(hop < len(path) and 0x02000000 <= address and address + 4 <= 0x02400000 and address % 4 == 0, 'unreachable pointer read')
                    location, pointer = path[hop]
                    require(location == address and 0 <= pointer <= 0xFFFFFFFF, 'pointer read proof mismatch')
                    if pointer == 0:
                        require(optional and hop == len(path) - 1, 'invalid null termination')
                        present = False
                        break
                    require(0x02000000 <= pointer < 0x02400000 and pointer % 4 == 0, 'unreachable nonzero pointer')
                    address = pointer + step
                if present:
                    address += final_offset
                    require(len(path) == len(offsets) and 0x02000000 <= address and address + length <= 0x02400000, 'unreachable resolved watch')
                else:
                    address = 0
                    require(data == bytes(length), 'nonzero absent watch padding')
                require((flags[index] == '1') == present and addresses[index] == address, 'watch presence/address mismatch')
                resolutions[w['name']] = {'present': present, 'address': address, 'path': path}
            values[w['name']] = (int.from_bytes(data, 'little') if w['len'] <= 4 else list(data)) if present else None
            pos += w['len']
        image = folder / f'{i:06d}.ppm'
        ppm = image.read_bytes()
        header = b'P6\n256 384\n255\n'
        require(ppm.startswith(header) and len(ppm) == len(header) + 256 * 384 * 3, 'invalid native image')
        decoded.append({'sequence': seq, 'nds_frame': frame, 'start_tick': start, 'end_tick': end,
                        'key_mask': mask, 'audio_offset': offset, 'audio_count': count, 'w': values,
                        'image_sha256': hashlib.sha256(ppm).hexdigest(), 'watch_resolutions': resolutions})
        offset += count
        previous_end, previous_frame, last_held = end, frame, chunk[-1][2:4]
    require(offset == len(samples), 'unindexed audio')
    hooks = validate_hooks(folder, [r['nds_frame'] for r in decoded], calls, lists, read_csv, require)
    require((folder / 'gpu-media.json').exists() == bool(gpu), 'gpu files and gpu expectation disagree')
    if gpu:
        hooks['gpu'] = validate_gpu(folder, [r['nds_frame'] for r in decoded], read_csv, require)
    return {**hooks, 'audio_options': options, 'frames': frames, 'audio_packets': len(samples), 'nonzero_audio': any(s[2] or s[3] for s in samples),
            'rows': decoded, 'audio_sha256': hashlib.sha256(raw).hexdigest()}
