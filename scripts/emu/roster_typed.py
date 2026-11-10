"""A23 typed support proof beside the unchanged stock roster guard.

This establishes identity only. Cell admission and hit attribution are separate.
Support id_byte is never interpreted as a battle chr_b.
"""
import hashlib
from pathlib import Path

import fighter_layout as fl
import state_identity as si

STOCK_SHA256 = '1e84546b27910e2333e0d15e3678a7b58993de9a079c9cb9559fc12d213229b9'


class TypedRosterError(si.IdentityError):
    def __init__(self, clause, message, stock_refusal=None):
        self.clause = clause
        self.stock_refusal = stock_refusal
        super().__init__(f'{clause}: {message}')


def require(condition, clause, message, stock_refusal=None):
    if not condition:
        raise TypedRosterError(clause, message, stock_refusal)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def slot_table(peek, layout, side, count):
    base = fl.LAYOUTS[layout]['P1REC' if side == 0 else 'P2REC']
    return [dict(slot=i, active=bool(peek(base + 0x50 * i + 0x25, 1) & 1),
                 type=peek(base + 0x50 * i + 0x28, 1),
                 id_byte=peek(base + 0x50 * i + 0x29, 1)) for i in range(count)]


class Reader:
    def __init__(self, layout, load_peek, expected_active_slots, slot_counts=(4, 4)):
        require(sha(si.__file__) == STOCK_SHA256, 'RT-1', 'stock state_identity.py SHA changed')
        require(slot_counts in [(4, 4), (5, 4)], 'RT-3', 'unsupported roster watch schema')
        require(set(expected_active_slots) == {'p1', 'p2'}, 'RT-4', 'fixture battle slots missing')
        self.layout, self.slot_counts = layout, slot_counts
        self.tables, self.battles = {}, {}
        for side in (0, 1):
            name = f'p{side + 1}'
            # The load row must pass stock; no typed fallback is allowed here.
            battle = si.read_roster(load_peek, layout, side)
            table = slot_table(load_peek, layout, side, slot_counts[side])
            slot = battle['active_slot']
            require(slot == expected_active_slots[name] and table[slot]['type'] == 0,
                    'RT-4', 'load battle differs from fixture expectation')
            self.tables[name], self.battles[name] = table, slot

    def read(self, peek, side):
        name = f'p{side + 1}'
        refusal = None
        try:
            identity = si.read_roster(peek, self.layout, side)
        except si.IdentityError as error:
            if str(error) != f'{name}: 2 active roster slots':
                raise
            identity, refusal = None, str(error)
        table = slot_table(peek, self.layout, side, self.slot_counts[side])
        original = self.tables[name]
        require([s['type'] for s in table] == [s['type'] for s in original],
                'RT-3', f'{name} record type changed', refusal)
        require([s['id_byte'] for s in table] == [s['id_byte'] for s in original],
                'RT-5', f'{name} record id byte changed', refusal)
        active = [s for s in table if s['active']]
        battle = [s['slot'] for s in active if s['type'] == 0]
        require(battle == [self.battles[name]], 'RT-4', f'{name} battle slot changed', refusal)
        support = [s['slot'] for s in active if s['type'] == 1]
        if refusal is None:
            require(len(active) == 1, 'RT-4', 'active record outside stock watch span')
            # Preserve the stock return object and fields verbatim.
            return dict(identity=identity, roster_path='stock', stock_refusal=None, support=None)
        require(len(active) == 2 and len(support) == 1 and all(s['type'] in (0, 1) for s in active),
                'RT-4', 'two-active refusal is not one battle plus one support', refusal)
        # Direct battle-record arithmetic, exactly as in stock read_roster.
        base = fl.LAYOUTS[self.layout]['P1REC' if side == 0 else 'P2REC']
        rec = base + 0x50 * self.battles[name]
        identity = dict(active_slot=self.battles[name], chr_b=peek(rec + 0x29, 1),
                        hp=peek(rec, 2), hp_max=peek(rec - 2, 2))
        return dict(identity=identity, roster_path='typed_support_v1',
                    stock_refusal=refusal, support=support[0])


def qualify(rows, *, layout, load_peek, expected_active_slots, cell,
            slot_counts=(4, 4), peek_for_row=None):
    require(bool(rows), 'RT-7', 'empty capture')
    reader = Reader(layout, load_peek, expected_active_slots, slot_counts)
    if peek_for_row is None:
        peek_for_row = lambda row: fl.roster_peek(layout, row['w'])
    output, refusals = [], []
    intervals = {'p1': [], 'p2': []}
    opened = {'p1': None, 'p2': None}
    counts = {'stock': 0, 'typed_support_v1': 0}
    side_counts = {name: dict(counts) for name in intervals}
    for tick, row in enumerate(rows):
        sides, paths = {}, {}
        peek = peek_for_row(row)
        for side in (0, 1):
            name = f'p{side + 1}'
            result = reader.read(peek, side)
            sides[name], paths[name] = result['identity'], result['roster_path']
            side_counts[name][result['roster_path']] += 1
            if result['stock_refusal'] is not None:
                refusals.append(dict(tick=tick, side=name, message=result['stock_refusal']))
            current = result['support']
            if opened[name] is not None and opened[name]['slot'] != current:
                opened[name]['off'] = tick
                opened[name] = None
            if current is not None and opened[name] is None:
                opened[name] = dict(slot=current, on=tick, off=None)
                intervals[name].append(opened[name])
        path = 'typed_support_v1' if 'typed_support_v1' in paths.values() else 'stock'
        require(cell != 'W7-DREAM-R' or path == 'stock', 'RT-9', 'DREAM took support path')
        counts[path] += 1
        output.append(dict(tick=tick, roster_path=path, roster_paths=paths, sides=sides))
    checks = []
    for side in (0, 1):
        name = f'p{side + 1}'
        for interval in intervals[name]:
            first = interval['on'] - 1
            last = interval['off'] if interval['off'] is not None else len(rows) - 1
            def body(tick):
                try:
                    if tick == -1:
                        fighter = load_peek(fl.LAYOUTS[layout]['FIGHTERS'] + 4 * side, 4)
                        wrapper = load_peek(fighter + 0x1A8, 4)
                        return fighter.to_bytes(4, 'little'), load_peek(wrapper + 0x10, 4)
                    w = rows[tick]['w']
                    entry = bytes(w['fighters'][4 * side:4 * side + 4])
                    require(len(entry) == 4, 'RT-8', 'fighters entry truncated')
                    return entry, w[name + 'colprm']
                except (KeyError, si.IdentityError) as error:
                    raise TypedRosterError('RT-8', f'missing body corroboration {error}') from error
            baseline = body(first)
            for tick in range(first, last + 1):
                require(body(tick) == baseline, 'RT-8', f'{name} body changed at {tick}')
            checks.append(dict(side=name, on=interval['on'], off=interval['off'],
                               checked=[first, last], rows=last - first + 1,
                               fighter=int.from_bytes(baseline[0], 'little'), colprm=baseline[1]))
    proof = dict(schema='roster_support_proof_v1', reader_sha256=sha(__file__),
                 state_identity_sha256=sha(si.__file__), state_identity_unchanged=True,
                 cell=cell, load_slot_tables=reader.tables, battle_slots=reader.battles,
                 support_intervals=intervals, body_corroboration=checks,
                 rows_by_path=counts, side_rows_by_path=side_counts,
                 stock_calls=2 * len(rows), load_stock_calls=2,
                 stock_refusals=refusals, stock_refusal_count=len(refusals),
                 first_stock_refusal_tick=refusals[0]['tick'] if refusals else None,
                 RT_result='PASS_IDENTITY_ONLY', cell_admitted=False,
                 support_character_identity='UNMEASURED; id_byte is not battle chr_b')
    return dict(rows=output, roster_support_proof_v1=proof)
