"""Render native body cells with their original coordinates and full palettes."""
from __future__ import annotations

import hashlib
import re
import struct
from pathlib import Path

from PIL import Image

import aar_inventory
import anim_timing
import effect_render
import move_records


def _member(archive, name):
    entries = aar_inventory.parse_alar_v2(archive)['entries']
    hits = [entry for entry in entries if entry['name'] == name]
    if len(hits) != 1:
        raise ValueError(f'expected exactly one archive member {name}, got {len(hits)}')
    entry = hits[0]
    return move_records.maybe_dscp(archive[entry['offset']:entry['offset'] + entry['size']])


def _texture_keys(kind, raw):
    if kind == 'const':
        return [[0, struct.unpack_from('<I', raw)[0]]]
    if kind != 'key':
        raise ValueError(f'unsupported TextureID track kind {kind}')
    keys, offset = [], 0
    while offset + 2 <= len(raw):
        tick = struct.unpack_from('<H', raw, offset)[0]
        if tick == 0xFFFF:
            return keys
        if offset + 6 > len(raw):
            raise ValueError('truncated keyed TextureID')
        keys.append([tick, struct.unpack_from('<I', raw, offset + 2)[0]])
        offset += 6
    raise ValueError('keyed TextureID missing terminator')


def _cell_keys(bounds, textures, lookup):
    keys = []
    for tick in sorted({time for time, _ in bounds + textures}):
        held_bounds = [value for time, value in bounds if time <= tick]
        held_textures = [value for time, value in textures if time <= tick]
        if not held_bounds or not held_textures:
            raise ValueError(f'no initialized BoundsIndex/TextureID at frame {tick}')
        cell, texture = held_bounds[-1], held_textures[-1] & 0xFFFFFF
        if (texture, cell) not in lookup:
            raise ValueError(f'texture {texture:#x} missing native cell {cell} at frame {tick}')
        keys.append([tick, lookup[(texture, cell)]])
    return keys


def _node_blocks(table, start, end):
    """ALMT v2 nodes share one header; nonzero node deltas accumulate.

    Track offsets are relative to each count block, bounded by the next
    populated block. Raw properties remain available without interpreting
    their runtime behavior.
    """
    raw = table.buf
    ident, frames = struct.unpack_from('<IH', raw, start)
    base = start + table.hdr_end
    bases = [base]
    for index in range(1, len(table.nodes)):
        delta = struct.unpack_from('<H', raw, start + 8 + 2 * index)[0]
        if delta:
            base += delta
        bases.append(base if delta else None)
    populated = [offset for offset in bases if offset is not None]
    nodes = []
    for name, offset in zip(table.nodes, bases):
        node = {'name': name, 'status': 'absent', 'reason': None,
                'tracks': {}, 'raw_tracks': [], 'id': None, 'frames': None,
                'start': offset, 'end': None}
        nodes.append(node)
        if offset is None:
            continue
        stop = next((value for value in populated if value > offset), end)
        node.update(id=ident & 255, frames=frames, end=stop, status='decoded')
        try:
            if not start + table.hdr_end <= offset < stop <= end:
                raise ValueError('node block outside animation')
            nc, nk = raw[offset:offset + 2]
            count = nc + nk
            indexes = raw[offset + 2:offset + 2 + count]
            tp = offset + 2 + count
            tp += tp & 1
            if tp + count * 2 > stop or any(i >= len(table.props) for i in indexes):
                raise ValueError('invalid node property table')
            offsets = [offset + struct.unpack_from('<H', raw, tp + 2 * i)[0]
                       for i in range(count)]
            if offsets != sorted(offsets) or any(o < tp + count * 2 or o >= stop
                                                 for o in offsets):
                raise ValueError('invalid node track offsets')
            for index, (prop_index, track_start) in enumerate(zip(indexes, offsets)):
                prop = table.props[prop_index]
                track_end = offsets[index + 1] if index + 1 < count else stop
                data = raw[track_start:track_end]
                kind = 'const' if index < nc else 'key'
                node['raw_tracks'].append({'prop': prop, 'kind': kind,
                                           'raw_hex': data.hex()})
            for track in node['raw_tracks']:
                prop, kind = track['prop'], track['kind']
                data = bytes.fromhex(track['raw_hex'])
                if prop == 'TextureID':
                    node['tracks'][prop] = _texture_keys(kind, data)
                elif prop == 'BoundsIndex':
                    keys = [list(key) for key in anim_timing.decode_track(prop, kind, data)]
                    if kind == 'key':
                        terminator = len(keys) * 4
                        if data[terminator:terminator + 2] != b'\xff\xff':
                            raise ValueError('BoundsIndex missing terminator')
                    node['tracks'][prop] = keys
        except (ValueError, struct.error) as exc:
            node.update(status='unsupported', reason=str(exc))
    return nodes


def _animations(prefix, raw):
    table = move_records.Almt(raw)
    animations = []
    starts = [table.base + offset for offset in table.anim_offsets]
    for index, (start, end) in enumerate(zip(starts, starts[1:] + [len(raw)])):
        animation = {'stable_id': f'{prefix}:anim:{index:04x}', 'index': index,
                     'id': struct.unpack_from('<I', raw, start)[0] & 255,
                     'frames': struct.unpack_from('<H', raw, start + 4)[0],
                     'rate': raw[start + 6], 'loop': raw[start + 7],
                     'nodes': _node_blocks(table, start, end)}
        animations.append(animation)
    return animations


def _body_geometry(prefix, repo_root=None):
    """Load body tiles/cells and all animation nodes without changing module globals.

    Raw tracks retain properties this renderer does not interpret. Node status
    describes ALMT structural decoding, not runtime playback verification.
    """
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    folder = root / 'jus_files' / 'ripped_jus_files' / 'chr'
    body_archive = move_records.maybe_dscp(move_records.alar_v3_member(
        folder / 'ChrArc.aar', f'chr/{prefix}.aar'))
    graphics_archive = (folder / f'{prefix}c.aar').read_bytes()
    entries = aar_inventory.parse_alar_v2(graphics_archive)['entries']
    if len(entries) != 1:
        raise ValueError(f'{prefix}: expected one DSIG graphics member')
    entry = entries[0]
    graphics = graphics_archive[entry['offset']:entry['offset'] + entry['size']]
    if graphics[:4] != b'DSIG' or graphics[4] != 2:
        raise ValueError(f'{prefix}: unsupported body DSIG format')
    palette_count = graphics[6]
    palettes = [list(struct.unpack_from('<16H', graphics, 12 + index * 32))
                for index in range(palette_count)]
    frame_table = 12 + palette_count * 32 + 4
    frame_count = struct.unpack_from('<I', graphics, frame_table)[0]
    frames = [move_records.lz77(graphics, frame_table + struct.unpack_from(
        '<H', graphics, frame_table + 4 + 4 * index)[0] * 4)
        for index in range(frame_count)]
    texture = _member(body_archive, f'{prefix}_.dtx')
    if texture[:4] != b'DSTX' or texture[4] != 1:
        raise ValueError(f'{prefix}: unsupported body DSTX format')
    cell_count = struct.unpack_from('<H', texture, 6)[0]
    cells = []
    for index in range(cell_count):
        offset = 10 + struct.unpack_from('<H', texture, 10 + 2 * index)[0]
        segments = struct.unpack_from('<H', texture, offset)[0]
        cells.append([struct.unpack_from('<HbbBB', texture, offset + 2 + 6 * seg)
                      for seg in range(segments)])
    return {'prefix': prefix, 'palettes': palettes, 'frames': frames, 'cells': cells,
            'tile_alignments': [2] * len(cells),
            'source_hashes': {'body_archive': hashlib.sha256(body_archive).hexdigest(),
                              'graphics_archive': hashlib.sha256(graphics_archive).hexdigest()}}


def load_body(prefix, repo_root=None):
    """Load one body atlas and its local animation inventory."""
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    bundle = _body_geometry(prefix, root)
    members = _archive_members(prefix, root)
    bundle['anims'] = _animations(prefix, members[f'{prefix}.amt'][1])
    return bundle


def render_body_cell(bundle, index):
    """Return RGBA and exclusive native bounds; native zero is (-minx, -miny).

    Segments consume one tile cursor per cell. DSIG v2 allocates each segment
    in two-tile units; the DSIG v1 adapter emits contiguous one-tile units.
    """
    if not 0 <= index < len(bundle['cells']):
        raise ValueError(f'body cell index out of range: {index}')
    segments = bundle['cells'][index]
    if not segments:
        return Image.new('RGBA', (1, 1)), (0, 0, 1, 1)
    bounds = []
    for frame, x, y, shape, palette in segments:
        if shape & 0xC0 or (shape & 15) not in anim_timing.SIZES:
            raise ValueError(f'unsupported body segment shape {shape:#x}')
        if not 0 <= palette < len(bundle['palettes']):
            raise ValueError(f'body palette index out of range: {palette}')
        if not 0 <= frame < len(bundle['frames']):
            raise ValueError(f'body frame index out of range: {frame}')
        width, height = anim_timing.SIZES[shape & 15]
        bounds.append((x, y, x + width * 8, y + height * 8))
    x0 = min(b[0] for b in bounds)
    y0 = min(b[1] for b in bounds)
    x1 = max(b[2] for b in bounds)
    y1 = max(b[3] for b in bounds)
    image = Image.new('RGBA', (x1 - x0, y1 - y0))
    pixels = image.load()
    cursor = 0
    alignment = bundle.get('tile_alignments', [1] * len(bundle['cells']))[index]
    for frame, x, y, shape, palette in segments:
        width, height = anim_timing.SIZES[shape & 15]
        tiles = bundle['frames'][frame]
        end = cursor + width * height
        if len(tiles) < end * 32:
            raise ValueError(f'truncated body tile data: cell {index}, frame {frame}')
        colours = bundle['palettes'][palette]
        for ty in range(height):
            for tx in range(width):
                tile_offset = (cursor + ty * width + tx) * 32
                for py in range(8):
                    for px in range(8):
                        byte = tiles[tile_offset + py * 4 + px // 2]
                        colour_index = (byte >> 4) if px & 1 else (byte & 15)
                        if colour_index == 0:
                            continue
                        if colour_index >= len(colours):
                            raise ValueError(f'palette colour index out of range: {colour_index}')
                        colour = colours[colour_index]
                        local_x, local_y = tx * 8 + px, ty * 8 + py
                        if shape & 0x10:
                            local_x = width * 8 - 1 - local_x
                        if shape & 0x20:
                            local_y = height * 8 - 1 - local_y
                        pixels[x + local_x - x0, y + local_y - y0] = (
                            (colour & 31) * 255 // 31, ((colour >> 5) & 31) * 255 // 31,
                            ((colour >> 10) & 31) * 255 // 31, 255)
        cursor = ((end + alignment - 1) // alignment) * alignment
    return image, (x0, y0, x1, y1)


def _archive_members(prefix, root):
    folder = root / 'jus_files' / 'ripped_jus_files'
    if prefix in effect_render.COMM:
        raw = (folder / 'efc' / f'{prefix}.aar').read_bytes()
    else:
        raw = move_records.maybe_dscp(move_records.alar_v3_member(
            folder / 'chr' / 'ChrArc.aar', f'chr/{prefix}.aar'))
    members = {}
    for entry in aar_inventory.parse_alar_v2(raw)['entries']:
        data = move_records.maybe_dscp(raw[entry['offset']:entry['offset'] + entry['size']])
        members[entry['name']] = (entry['file_id'], data)
    return members


def _texture_tiles(raw, sprites):
    """Adapt DSIG v1 tiled support or linear effect pixels to body tile bytes."""
    if raw[:5] != b'DSIG\x01':
        raise ValueError('unsupported archive DSIG format')
    mode = raw[7]
    if mode == 4:
        count = raw[6]
        palettes = [list(struct.unpack_from('<16H', raw, 12 + i * 32)) for i in range(count)]
        data = raw[12 + count * 32:]
        if len(data) % 32:
            raise ValueError('support tile bytes are not aligned to 32-byte tiles')
        texture = None
    elif mode == 0:
        texture = effect_render.parse_dsig(raw)
        palettes = texture['palettes']
        data = None
    else:
        raise ValueError(f'unsupported DSIG v1 storage mode {mode}')
    frames, cells = [], []
    for sprite in sprites:
        tiles = bytearray()
        segments = []
        for src, x, y, shape, palette in sprite:
            shape, palette = shape & 255, palette & 255
            if shape & 0x80 or (shape & 15) not in anim_timing.SIZES:
                raise ValueError(f'unsupported archive segment shape {shape:#x}')
            width, height = anim_timing.SIZES[shape & 15]
            if not 0 <= palette < len(palettes):
                raise ValueError(f'archive palette index out of range: {palette}')
            if mode == 4:
                if shape & 0x40:
                    raise ValueError('2bpp tiled support storage is not decoded')
                end = (src + width * height) * 32
                if end > len(data):
                    raise ValueError('support tile source exceeds texture')
                tiles.extend(data[src * 32:end])
            else:
                sx, sy = effect_render.source_xy(src)
                bpp = effect_render.bpp_of(shape)
                if sx + width * 8 > 32 * (8 // bpp) or sy + height * 8 > texture['height']:
                    raise ValueError('effect segment exceeds texture bounds')
                for ty in range(height):
                    for tx in range(width):
                        for py in range(8):
                            for px in range(0, 8, 2):
                                a = effect_render.texel(texture, sx + tx * 8 + px, sy + ty * 8 + py, bpp)
                                b = effect_render.texel(texture, sx + tx * 8 + px + 1, sy + ty * 8 + py, bpp)
                                tiles.append(a | b << 4)
            segments.append((len(frames), x, y, shape & 0x3F, palette))
        frames.append(bytes(tiles))
        cells.append(segments)
    return {'palettes': palettes, 'frames': frames, 'cells': cells}


def load_archive(prefix, repo_root=None):
    """Load support/body/effect cells into the same renderable tile representation.

    Cell indices in node ``cell_keys`` address the flattened bundle. Original
    BoundsIndex keys remain untouched. Unsupported textures or unresolved node
    texture selection are reported explicitly and never produce guessed cells.
    """
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[2]
    own = _archive_members(prefix, root)
    members = dict(own)
    base, _, panel_text = prefix.rpartition('_')
    panel = int(panel_text) if panel_text in ('1', '2', '3', '4', '5', '6', '7', '8') else None
    family = re.fullmatch(r'([a-z]+_[bs]_\d+)(?:_[1-8])?', prefix)
    if family:
        stem = family[1]
        for candidate in [stem] + [f'{stem}_{number}' for number in range(1, 9)]:
            if candidate == prefix:
                continue
            try:
                dependencies = _archive_members(candidate, root)
            except (KeyError, FileNotFoundError):
                continue
            members.update({name: value for name, value in dependencies.items()
                            if name.endswith(('.dtx', '.dig')) and name not in members})
    role = 'support' if re.fullmatch(r'[a-z]+_s_\d+(?:_\d+)?', prefix) else (
        'battle' if re.fullmatch(r'[a-z]+_b_\d+(?:_\d+)?', prefix) else 'effect')
    bundle = {'prefix': prefix, 'role': role, 'panel': panel, 'palettes': [], 'frames': [],
              'cells': [], 'cell_metadata': [], 'anims': [], 'unsupported_textures': [],
              'source_hashes': {name: hashlib.sha256(raw).hexdigest() for name, (_, raw) in members.items()}}
    cell_lookup = {}
    for name, (fid, raw) in sorted(members.items()):
        if not name.endswith('.dtx'):
            continue
        texture_id = fid & 0xFFFFFF
        try:
            parsed = effect_render.parse_dstx(raw)
            reference = parsed['texture']
            body_prefix = name.removesuffix('_.dtx')
            if name.endswith('_.dtx') and (root / 'jus_files' / 'ripped_jus_files' / 'chr' / f'{body_prefix}c.aar').exists():
                art = _body_geometry(body_prefix, root)
            else:
                if 'embedded' in reference:
                    graphics = raw[reference['embedded']:]
                else:
                    wanted = reference['id'] & 0xFFFFFF
                    hits = [value for member, (mid, value) in members.items()
                            if member.endswith('.dig') and mid & 0xFFFFFF == wanted]
                    if len(hits) != 1:
                        raise ValueError(f'texture {wanted:#x} resolves to {len(hits)} graphics members')
                    graphics = hits[0]
                art = _texture_tiles(graphics, parsed['sprites'])
            palette_base, frame_base = len(bundle['palettes']), len(bundle['frames'])
            bundle['palettes'].extend(art['palettes'])
            bundle['frames'].extend(art['frames'])
            for local, segments in enumerate(art['cells']):
                cell_lookup[(texture_id, local)] = len(bundle['cells'])
                bundle['cell_metadata'].append({'member': name, 'texture_id': texture_id, 'local_cell': local})
                bundle.setdefault('tile_alignments', []).append(
                    art.get('tile_alignments', [1] * len(art['cells']))[local])
                bundle['cells'].append([(frame + frame_base, x, y, shape, palette + palette_base)
                                        for frame, x, y, shape, palette in segments])
        except (ValueError, KeyError, IndexError, struct.error) as error:
            bundle['unsupported_textures'].append({'member': name, 'texture_id': texture_id, 'reason': str(error)})
    for name, (_, raw) in sorted(own.items()):
        if not name.endswith('.amt'):
            continue
        for animation in _animations(prefix, raw):
            animation['member'] = name
            animation['stable_id'] = f"{prefix}:{name}:anim:{animation['index']:04x}"
            for node in animation['nodes']:
                node['cell_keys'] = []
                bounds = node['tracks'].get('BoundsIndex', [])
                texture = node['tracks'].get('TextureID', [])
                node['resolution_status'] = 'no_cells' if not bounds else 'unresolved'
                node['resolution_reason'] = None
                if bounds:
                    try:
                        node['cell_keys'] = _cell_keys(bounds, texture, cell_lookup)
                    except ValueError as error:
                        node['resolution_reason'] = str(error)
                    else:
                        node['resolution_status'] = 'resolved'
            bundle['anims'].append(animation)
    return bundle
