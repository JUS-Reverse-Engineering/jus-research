"""Battle RAM layouts, layout detection, and native watches that reach the fighters through the fighter table.

Two layouts exist. Dark Tournament training states use the addresses the repo docs give. Deck-maker
test-play states (every owner character-mapping state) keep the same structures 0x20 lower: the fighter
table, both HP record arrays, the element array and the ColPrm manager all move by -0x20
(docs/research/feel-captures/import-character-mapping-2026-09-24, "The test-play layout"; moved here from
that capture's plans/a0.py).

Fighter objects are never literals here. Every per-object watch is a pointer chain that starts at the
layout's fighter table, slot 0 for p1 and slot 1 for p2, so a heap that moves between states is followed.

Guard-contact recorder (jus-o0nw): per fighter, `colprm` = M itself ([obj+0x1A8]+0x10, 4 bytes; the guard_block hook logs r1 = the
defender's M) and `flags` = the word at M+0x78, whose bit 26 (byte 3, 0x04) is the is-guarding flag (guard-sp.md section 0.5).

Body art per fighter, where render = [[[[obj+0x1A8]+8]+4]+0x64] (the sprite node):
  cell    s16 [render+0x4A]       BoundsIndex; written by strh at 0x02032E38 (JUS_WATCH reports pc+8 = 0x02032E40)
  texture u32 [[render+0x20]+8]   TextureID; the descriptor getter 0x02025068 reads [[[node+0x64]+0x20]+8]
  facing  u8  [render+0x48]       horizontal flip (setter 0x02032F28 strb r6,[r0,#0x48])
"""

P1_PTR = 0x02181B28  # the local P1 fighter object pointer; equals fighter table slot 0 in every battle

LAYOUTS = {
    'dark-tournament': {'FIGHTERS': 0x021DEB3C, 'P1REC': 0x021DF1D4, 'P2REC': 0x021DF7F0,
                        'ELARR': 0x0220C068, 'MGR': 0x0220DDE0},
    'test-play': {'FIGHTERS': 0x021DEB1C, 'P1REC': 0x021DF1B4, 'P2REC': 0x021DF7D0,
                  'ELARR': 0x0220C048, 'MGR': 0x0220DDC0},
}

GFC = 0x020A0F10      # global frame counter word
SPRITE = [0x1A8, 8, 4, 0x64]   # obj -> wrapper -> entity -> node -> sprite (render) pointer
COLPRM = [0x1A8, 0x10]         # obj -> wrapper -> ColPrm record M


class LayoutError(RuntimeError):
    pass


def detect_layout(peek):
    """Match the local fighter and an aligned live-list head in the manager's inline pool.

    manager+0 is the active-list head, not a self-pointer. Removing crates can
    retire record zero and advance it. peek returns an unsigned little-endian int.
    Refuse zero or multiple matching layouts.
    """
    p1 = peek(P1_PTR, 4)
    hits = []
    for name, L in LAYOUTS.items():
        if peek(L['FIGHTERS'], 4) != p1:
            continue
        offset = peek(L['MGR'], 4) - L['MGR'] - 0x454
        if 0 <= offset < 128 * 0x188 and offset % 0x188 == 0:
            hits.append(name)
    if len(hits) != 1:
        raise LayoutError(f'no single RAM layout matches (p1 {p1:#x}, matches {hits})')
    return hits[0]


def probe_watches():
    """Direct watches holding every word detect_layout reads, for a short native probe capture."""
    ws = [{'name': 'p1ptr', 'addr': P1_PTR, 'len': 4}]
    for n, L in LAYOUTS.items():
        ws += [{'name': f'{n}:fighters', 'addr': L['FIGHTERS'], 'len': 4},
               {'name': f'{n}:mgr', 'addr': L['MGR'], 'len': 4}]
    return ws


def peek_from_probe(values):
    """A peek over one probe row's watch values; any address the probe did not read raises KeyError."""
    by_addr = {(w['addr'], w['len']): values[w['name']] for w in probe_watches() if w['name'] in values}

    def peek(addr, n):
        return by_addr[(addr, n)]
    return peek


def fighter_watches(layout):
    """The P0 body profile: per slot object, physics, HP and body art watches, plus the table self-check pair."""
    if layout not in LAYOUTS:
        raise LayoutError(f'unknown layout {layout!r}')
    L = LAYOUTS[layout]
    ws = [{'name': 'gfc', 'addr': GFC, 'len': 4},
          {'name': 'p1ptr', 'addr': P1_PTR, 'len': 4},
          {'name': 'fighters', 'addr': L['FIGHTERS'], 'len': 8}]
    for k, slot in enumerate(('p1', 'p2')):
        obj = L['FIGHTERS'] + 4 * k
        rec = L['P1REC'] if k == 0 else L['P2REC']
        ws += [
            {'name': f'{slot}st', 'chain': [obj, 0x18], 'len': 1},
            {'name': f'{slot}input', 'chain': [obj, 0x6C], 'len': 4},
            {'name': f'{slot}move', 'chain': [obj, 0xC0], 'len': 56},
            {'name': f'{slot}abilities', 'chain': [obj, 0x128], 'len': 8},
            {'name': f'{slot}hp', 'addr': rec - 2, 'len': 4},
            {'name': f'{slot}identity', 'addr': rec + 0x25, 'len': 5},
            {'name': f'{slot}sp', 'addr': rec + 0x558, 'len': 6},
            {'name': f'{slot}el', 'chain': [obj, *COLPRM, 0x5C, 0x0C], 'len': 28},
            {'name': f'{slot}ground', 'chain': [obj, *COLPRM, 0x78], 'len': 1},
            {'name': f'{slot}flags', 'chain': [obj, *COLPRM, 0x78], 'len': 4},     # bit 26 (byte 3, 0x04): is guarding
            {'name': f'{slot}colprm', 'chain': [obj, *COLPRM], 'len': 4},          # M itself: arm9 0x02081CC8 logs r1 = M
            {'name': f'{slot}gate', 'chain': [obj, *COLPRM, 0x44], 'len': 4},
            {'name': f'{slot}cell', 'chain': [obj, *SPRITE, 0x4A], 'len': 2},
            {'name': f'{slot}tex', 'chain': [obj, *SPRITE, 0x20, 8], 'len': 4},
            {'name': f'{slot}facing', 'chain': [obj, *SPRITE, 0x48], 'len': 1},
            {'name': f'{slot}art', 'chain': [obj, 0x1A8, 8, 4, 0x68, 0x54, 0x28], 'len': 24},
        ]
    return ws


REACTION_OFFSET = 0xFC   # victim object: reaction handler pointer (+0xFC), type (+0x100), combo accumulator (+0x10E),
REACTION_LEN = 0x28      # landing timer (+0x110), damage (+0x112), hitstun (+0x114, whole frames at +0x115), alternate selector (+0x11E)


def reaction_watches(layout):
    """The reaction recorder: the victim (p2) object's reaction block, obj+0xFC .. obj+0x123, in one chain watch."""
    if layout not in LAYOUTS:
        raise LayoutError(f'unknown layout {layout!r}')
    return [{'name': 'p2rx', 'chain': [LAYOUTS[layout]['FIGHTERS'] + 4, REACTION_OFFSET], 'len': REACTION_LEN}]


ROSTER_SLOTS = 4
ROSTER_STEP = 0x50   # one roster record per slot, as state_identity reads them


def roster_watches(layout):
    """The identity guard: both sides' four roster records, direct statics (no pointer chain).

    Per side k (1 or 2) and slot i: g{k}s{i}hp = u16 max, u16 current at rec-2 (the active slot's HP) and
    g{k}s{i}id = the five bytes rec+0x25..0x29 (active flag at +0x25, chr_b at +0x29).
    """
    if layout not in LAYOUTS:
        raise LayoutError(f'unknown layout {layout!r}')
    L = LAYOUTS[layout]
    ws = []
    for k, rec in ((1, L['P1REC']), (2, L['P2REC'])):
        for i in range(ROSTER_SLOTS):
            base = rec + ROSTER_STEP * i
            ws += [{'name': f'g{k}s{i}hp', 'addr': base - 2, 'len': 4},
                   {'name': f'g{k}s{i}id', 'addr': base + 0x25, 'len': 5}]
    return ws


def roster_peek(layout, values):
    """A peek(addr, n) over one frame row's roster watch values; an address no roster watch covers raises KeyError."""
    mem = {}
    for w in roster_watches(layout):
        v = values.get(w['name'])
        if v is None:
            raise KeyError(w['name'])
        data = v.to_bytes(w['len'], 'little') if isinstance(v, int) else bytes(v)
        mem.update({w['addr'] + j: b for j, b in enumerate(data)})

    def peek(addr, n):
        return int.from_bytes(bytes(mem[addr + j] for j in range(n)), 'little')
    return peek


def check_table(values):
    """Refuse a frame whose fighter table slot 0 is not the live P1 pointer: the chains would follow a stale table."""
    slot0 = int.from_bytes(bytes(values['fighters'][:4]), 'little')
    if slot0 != values['p1ptr']:
        raise LayoutError(f'fighter table slot 0 {slot0:#x} != [P1_PTR] {values["p1ptr"]:#x}')


def s16(v):
    return v - 0x10000 if v >= 0x8000 else v
