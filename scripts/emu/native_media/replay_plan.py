"""Compile existing bridge input segments and watches for native capture."""
BITS = dict(zip(('A', 'B', 'SELECT', 'START', 'RIGHT', 'LEFT', 'UP', 'DOWN', 'R', 'L', 'X', 'Y'), range(12)))


def compile_masks(segments, tail):
    if type(tail) is not int or tail < 0:
        raise ValueError('invalid tail')
    previous = -1
    for segment in segments:
        start, end, buttons = segment['from'], segment['to'], segment['buttons']
        if type(start) is not int or type(end) is not int or start <= previous or end < start:
            raise ValueError('segments must be ordered and disjoint')
        if not isinstance(buttons, list) or any(not isinstance(b, str) or b.upper() not in BITS for b in buttons):
            raise ValueError('unknown DS button')
        previous = end
    frames = previous + 1 + tail
    if not 1 <= frames <= 4096:
        raise ValueError('native frame budget')
    masks = [4095] * frames
    for segment in segments:
        pressed = 0
        for button in segment['buttons']:
            pressed |= 1 << BITS[button.upper()]
        masks[segment['from']:segment['to'] + 1] = [4095 & ~pressed] * (segment['to'] - segment['from'] + 1)
    return masks


def watch_arguments(watches):
    if len(watches) > 64 or sum(w['len'] for w in watches) > 512:
        raise ValueError('native watch budget')
    if len({w['name'] for w in watches}) != len(watches):
        raise ValueError('duplicate watch names')
    result = []
    for watch in watches:
        chain = watch.get('chain')
        address, offsets = (chain[0], chain[1:]) if chain else (watch['addr'], [])
        optional = watch.get('optional', False)
        if type(optional) is not bool:
            raise ValueError('optional must be boolean')
        result.append({'address': address, 'length': watch['len'], 'offsets': offsets,
                       'offset': watch.get('offset', 0), 'optional': optional})
    return result
