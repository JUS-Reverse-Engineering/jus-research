"""Who and where a battle savestate is, read from its RAM: layout, stage, both fighters' chr_b and panel, rules.

The read works on two sources with one peek(addr, n) interface:
  - a .mln file, offline: melonDS keeps main RAM at the start of the NDSG section, after a u32 console
    type (melonDS NDS::DoSavestate); RamImage(mln_ram(bytes)).peek;
  - the live emulator, through the bridge.

Fields (the battle character record `rec` is the CURRENT HP halfword, char+0x18; slots step by 0x50):
  koma id   u16 [rec-0x0C]  (char+0x0C, the deck node's koma id); koma.bin gives its chr_b and size
  active    u8  [rec+0x25] bit 0
  chr_b     u8  [rec+0x29]  (char+0x41)
  HP        u16 [rec-2] max, [rec] current, 1/64 units
  position  s32 [[[[obj+0x1A8]+0x10]+0x5C]+0x0C] x, +0x10 y; ground u8 [[[obj+0x1A8]+0x10]+0x78]
  stage     u8  0x020AFE9C, the J Arena stage-list index; 32 is Dark Tournament (暗黒武術会会場, visible list
            position 33). Measured 2026-10-09 by correlation over the savestate store: every Dark Tournament
            training state reads 32, both J Arena stadium states read 0 (docs/research/feel-captures/
            2026-10-09-a3-dt-states/RESULTS.md). Deck-maker test play keeps the last J Arena choice here, so the
            byte names a stage only in the dark-tournament layout; elsewhere stage is None.
            Stage 16 is bg-cu: j6fix native map coordinates/types and grid match stage/bg_cu.bin; see
            docs/research/feel-captures/2026-10-25-j6fix-fixtures/README.md.
  rules     u8  0x020AFEBB items, 0x020AFEBC gimmick, 0x020AFEBD team (boot_verified.py RULE_FLAGS)
  cpu       u8  0x02181D1C, the pause menu's COM設定: 0 なにもしない (idle), 1 戦う (fight), 2 ガード (guard),
            3 ジャンプ (jump). Found 2026-10-09 by cycling the row and diffing main RAM (plans/find_menu_bytes.py,
            the only byte reading 0,1,2,3,0 outside UI scratch), then checked on the store: the three
            pc-kenshin-*-guard states read 2, both fightcpu states and e1-cpu read 1, the idle fixtures read 0.
            Measured in the dark-tournament layout only; elsewhere cpu is None.
"""
import gzip
import struct

import fighter_layout as fl

MAIN_RAM = 0x02000000
MAIN_RAM_SIZE = 0x400000
STAGE_SELECT = 0x020AFE9C
STAGES = {32: 'dark-tournament', 0: 'j-arena-stadium', 16: 'bg-cu'}
RULE_ITEMS, RULE_GIMMICK, RULE_TEAM = 0x020AFEBB, 0x020AFEBC, 0x020AFEBD
COM_SETTING = 0x02181D1C
CPU = {0: 'idle', 1: 'fight', 2: 'guard', 3: 'jump'}
SLOTS = 4
EXPECT_KEYS = {'layout', 'stage', 'cpu', 'items', 'gimmick', 'team', 'p1', 'p2', 'hp_full', 'floor_y_raw',
               'at_rest'}
SIDE_KEYS = {'chr_b', 'koma', 'panel', 'active_slot', 'state'}


class IdentityError(RuntimeError):
    pass


def mln_ram(blob):
    """Main RAM (4 MB) from a melonDS savestate, raw or gzipped."""
    if blob[:2] == b'\x1f\x8b':
        blob = gzip.decompress(blob)
    if blob[:4] != b'MELN':
        raise IdentityError('not a melonDS savestate')
    off = 0x10
    while off + 16 <= len(blob):
        magic, length = blob[off:off + 4], struct.unpack_from('<I', blob, off + 4)[0]
        if magic == b'NDSG':
            ram = blob[off + 20:off + 20 + MAIN_RAM_SIZE]
            if len(ram) != MAIN_RAM_SIZE:
                raise IdentityError('NDSG section shorter than main RAM')
            return ram
        if length < 16:
            break
        off += length
    raise IdentityError('no NDSG section')


class RamImage:
    def __init__(self, ram):
        self.ram = ram

    def peek(self, addr, n):
        i = addr - MAIN_RAM
        if i < 0 or i + n > len(self.ram):
            raise IdentityError(f'{addr:#x} outside main RAM')
        return int.from_bytes(self.ram[i:i + n], 'little')


def koma_table(blob):
    """Battle panels of koma.bin: koma id -> {chr_b, panel size} (docs/confirmed-facts/koma.md section 1)."""
    out = {}
    for i in range(len(blob) // 12):
        img, _, _, _, ptype, ability, group = struct.unpack_from('<HHBBBBB', blob, i * 12)
        if ptype == 0:
            out[img] = {'chr_b': ability, 'panel': group + 1}
    return out


def s32(v):
    return v - (1 << 32) if v >= 1 << 31 else v


def read_roster(peek, layout, k):
    """Side k's active roster slot, its chr_b and HP. peek only needs the roster records, so a frame row's
    roster watches (fighter_layout.roster_peek) are enough."""
    L = fl.LAYOUTS[layout]
    rec = L['P1REC'] if k == 0 else L['P2REC']
    active = [i for i in range(SLOTS) if peek(rec + 0x50 * i + 0x25, 1) & 1]
    if len(active) != 1:
        raise IdentityError(f'p{k + 1}: {len(active)} active roster slots')
    r = rec + 0x50 * active[0]
    return {'active_slot': active[0], 'chr_b': peek(r + 0x29, 1), 'hp': peek(r, 2), 'hp_max': peek(r - 2, 2)}


def read_side(peek, layout, k, koma):
    L = fl.LAYOUTS[layout]
    side = read_roster(peek, layout, k)
    r = (L['P1REC'] if k == 0 else L['P2REC']) + 0x50 * side['active_slot']
    side['koma'] = peek(r - 0x0C, 2)
    side['hp_full'] = side['hp'] == side['hp_max']
    panel = koma.get(side['koma'])
    if panel is None or panel['chr_b'] != side['chr_b']:
        raise IdentityError(f'p{k + 1}: koma {side["koma"]} is not a battle panel of chr_b {side["chr_b"]}')
    side['panel'] = panel['panel']
    obj = peek(L['FIGHTERS'] + 4 * k, 4)
    colprm = peek(peek(obj + 0x1A8, 4) + 0x10, 4)
    el = peek(colprm + 0x5C, 4)
    side.update(state=peek(obj + 0x18, 1), ground=peek(colprm + 0x78, 1),
                x_raw=s32(peek(el + 0x0C, 4)), y_raw=s32(peek(el + 0x10, 4)))
    return side


def read_identity(peek, koma):
    layout = fl.detect_layout(peek)
    stage_byte, com = peek(STAGE_SELECT, 1), peek(COM_SETTING, 1)
    dt = layout == 'dark-tournament'
    ident = {'layout': layout, 'stage_byte': stage_byte,
             'stage': STAGES.get(stage_byte, f'unknown-{stage_byte}') if dt else None,
             'com_byte': com, 'cpu': CPU.get(com, f'unknown-{com}') if dt else None,
             'items': peek(RULE_ITEMS, 1), 'gimmick': peek(RULE_GIMMICK, 1), 'team': peek(RULE_TEAM, 1)}
    for k in (0, 1):
        ident[f'p{k + 1}'] = read_side(peek, layout, k, koma)
    ident['hp_full'] = ident['p1']['hp_full'] and ident['p2']['hp_full']
    ident['at_rest'] = ident['p1']['state'] == 0 and ident['p2']['state'] == 0
    return ident


def check_expect(ident, expect):
    """Every mismatch between an identity and a recipe's [expect] table, as 'key: got X, want Y' strings."""
    unknown = set(expect) - EXPECT_KEYS
    if unknown:
        raise IdentityError(f'unknown expect keys {sorted(unknown)}')
    fails = []
    for key, want in sorted(expect.items()):
        if key in ('p1', 'p2'):
            if set(want) - SIDE_KEYS:
                raise IdentityError(f'unknown {key} keys {sorted(set(want) - SIDE_KEYS)}')
            fails += [f'{key}.{f}: got {ident[key][f]}, want {w}' for f, w in sorted(want.items())
                      if ident[key][f] != w]
        elif key == 'floor_y_raw':
            fails += [f'floor_y_raw: {s} y {ident[s]["y_raw"]} grounded={ident[s]["ground"]}, want {want}'
                      for s in ('p1', 'p2') if ident[s]['y_raw'] != want]
        elif ident[key] != want:
            fails.append(f'{key}: got {ident[key]}, want {want}')
    return fails
