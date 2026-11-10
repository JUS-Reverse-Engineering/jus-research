"""Extra boundary observations for the six pinned legacy shot recorder families.

Addresses are test-play only. ARM9 02032f30 writes render+48; ov6 021573b4/bc
loads fighter+1a8 -> wrapper+18 and 02156100 reads signed controller+a3.
SP: ARM9 02078204..a4, docs/confirmed-facts/guard-sp.md:880-916 and
feel-captures/sp-live-2026-09-12b/pc-naruto-fy-npc-yusuke-fy/gdb_run2.log.gz:4333-4337.
No emulator operations occur here. Render pointers must be resolved during prep.
"""
import copy

from fighter_layout import LAYOUTS, SPRITE
from jus_plan import validate_watches

SP_BAR = 0x6400
BUDGETS = {'train_base': (17, 324), 'train_specials': (18, 325),
           'train_height': (27, 443), 'tka': (17, 480),
           'tkb': (27, 236), 'fx': (19, 483)}


def _layout(name):
    if name != 'test-play':
        raise ValueError(f'unsupported legacy layout: {name!r}')
    return LAYOUTS[name]


def _ram(addr, length=4):
    if type(addr) is not int or addr % 4 or not 0x02000000 <= addr <= 0x02400000 - length:
        raise ValueError(f'unknown or unaligned RAM pointer: {addr!r}')
    return addr


def resolve_render(layout, side, peek):
    L = _layout(layout)
    if side not in (1, 2):
        raise ValueError('side must be 1 or 2')
    obj = _ram(peek(L['FIGHTERS'] + 4 * (side - 1), 4))
    for offset in SPRITE:
        obj = _ram(peek(obj + offset, 4), 0x49)
    return obj


def signed_store(value):
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError('stored watch must be one unsigned byte')
    return value - 256 if value >= 128 else value


def decode_sp(data):
    """Expose pool bytes as unsigned, and max/current bytes as signed.

    ARM9 0x02078240 compares the pool with signed bge/blt. The unsigned pool
    here preserves the raw watch word, not the CPU comparison semantics.
    """
    if not isinstance(data, (list, bytes)) or len(data) not in (6, 8):
        raise ValueError('SP needs the six-byte block or legacy eight-byte block')
    if any(type(x) is not int or not 0 <= x <= 255 for x in data):
        raise ValueError('SP contains a non-byte')
    return {'pool': int.from_bytes(bytes(data[:4]), 'little'),
            'max': signed_store(data[4]), 'current': signed_store(data[5])}


def check_active(watches, *, expected_slot, chr_b):
    active = []
    for slot in range(4):
        data = watches.get(f'p1id{slot}')
        if data is None or len(data) != 5:
            raise ValueError('all four P1 identity watches are required')
        if data[0] & 1:
            active.append((slot, data[4]))
    if active != [(expected_slot, chr_b)]:
        raise ValueError(f'P1 slot/identity changed: {active!r}')
    return expected_slot


def augment(family, watches, *, layout, active_slot, renders):
    L = _layout(layout)
    if family not in BUDGETS:
        raise ValueError(f'unknown source family: {family!r}')
    if type(active_slot) is not int or not 0 <= active_slot < 4:
        raise ValueError('unknown active P1 slot')
    if (len(watches), sum(w['len'] for w in watches)) != BUDGETS[family]:
        raise ValueError('source watch profile does not match the pinned family')
    validate_watches(watches)
    pool = next((w for w in watches if w['name'] == 'p1sp'), None)
    if pool != {'name': 'p1sp', 'addr': L['P1REC'] + 0x558, 'len': 8}:
        raise ValueError('unknown SP pointer/layout')
    out = copy.deepcopy(watches)
    names = {w['name'] for w in out}
    for side in (1, 2):
        if side not in renders:
            raise ValueError('missing resolved render pointer')
        render = _ram(renders[side], 0x49)
        if not {f'p{side}face', f'p{side}facing'} & names:
            out.append({'name': f'p{side}facing', 'addr': render + 0x48, 'len': 1})
        out.append({'name': f'p{side}stored',
                    'chain': [L['FIGHTERS'] + 4 * (side - 1), 0x1A8, 0x18, 0xA3], 'len': 1})
    out.append({'name': 'p2sp', 'addr': L['P2REC'] + 0x558, 'len': 6})
    if family.startswith('train_'):
        expected = {f'p1id{i}' for i in range(4)}
        if not expected <= names:
            raise ValueError('four P1 identity watches must be retained')
        out.append({'name': 'p1hp_current', 'addr': L['P1REC'] + active_slot * 0x50, 'len': 2})
    return validate_watches(out)
