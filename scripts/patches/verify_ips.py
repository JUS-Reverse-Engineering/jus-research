"""Independent IPS applier, used to verify the generated patches round-trip."""
import os
import struct
import sys
from pathlib import Path


def apply_ips(rom: bytes, ips: bytes) -> bytes:
    if ips[:5] != b'PATCH':
        raise SystemExit('bad IPS magic')
    out = bytearray(rom)
    i = 5
    while ips[i:i + 3] != b'EOF':
        if ips[i:i + 1] != b'@':
            raise SystemExit(f'expected @ at {i}, got {ips[i:i+1]!r}')
        i += 1
        off = struct.unpack_from('>I', ips, i)[0]
        i += 4
        size = ips[i]
        i += 1
        if size == 0:
            rle_len = struct.unpack_from('>H', ips, i)[0]
            i += 2
            b = ips[i]
            i += 1
            assert rle_len == 0, 'RLE-to-EOF not supported here'
            continue
        i += 2  # skip compare length
        out[off:off + size] = ips[i + size:i + 2 * size]  # skip 'before', take 'after'
        i += 2 * size
    if ips[i:i + 3] != b'EOF':
        raise SystemExit('missing EOF')
    return bytes(out)


if __name__ == '__main__':
    rom = Path(os.environ.get('JUS_ROM', 'jus.nds')).read_bytes()
    ips_path = Path(sys.argv[1])
    patched = apply_ips(rom, ips_path.read_bytes())

    stock_ov = Path(__file__).resolve().parents[2].joinpath('jus_files/arm9/overlays/arm9_ov11.bin').read_bytes()
    stock_ai = Path(__file__).resolve().parents[2].joinpath('jus_files/chrbin/chr/ai/ai_param.bin').read_bytes()
    OV, AI = 0x1D7E00, 0xF73260
    BASE = 0x02172A60

    new_ov = patched[OV:OV + len(stock_ov)]
    new_ai = patched[AI:AI + len(stock_ai)]

    # 1. size preserved
    assert len(patched) == len(rom), 'ROM size changed'
    # 2. diff confined to expected regions
    diffs = [i for i in range(len(rom)) if rom[i] != patched[i]]
    assert all(OV <= d < OV + len(stock_ov) or AI <= d < AI + len(stock_ai) for d in diffs), \
        'patch wrote outside ov11/ai_param.bin'
    print(f'{ips_path.name}: {len(diffs)} bytes differ, all inside ov11 or ai_param.bin')
    print(f'  ov11 changed bytes: {sum(1 for d in diffs if OV <= d < OV + len(stock_ov))}')
    print(f'  ai_param changed bytes: {sum(1 for d in diffs if AI <= d < AI + len(stock_ai))}')

    # 3. gate instruction is still valid ARM
    cmp_w = struct.unpack_from('<I', new_ov, 0x02179130 - BASE)[0]
    print(f'  gate cmp @0x02179130 = 0x{cmp_w:08X} (imm={cmp_w & 0xFF}, cond={(cmp_w >> 28) & 0xF})')
    assert (cmp_w & 0x0FF00000) == 0x03500000, 'cmp no longer encodes cmp r1,#imm'
    assert ((cmp_w >> 28) & 0xF) == 0xE, 'cmp lost its AL condition'

    # 4. threshold table decodes to sane u32s
    th = struct.unpack_from('<8I', new_ov, 0x0218190C - BASE)
    print(f'  threshold table = {th}')
    assert all(v <= 255 for v in th), 'threshold out of range'

    # 5. report the per-row gate params after patching
    rows = [new_ai[i * 0x30:(i + 1) * 0x30] for i in range(89)]
    live = [0x1C, 0x1D, 0x1F, 0x21, 0x22, 0x23, 0x24, 0x25]
    for label, r in (('stock row 1 ', stock_ai[0x30:0x60]), ('patched row 1', rows[1]),
                     ('stock row 13', stock_ai[13 * 0x30:14 * 0x30]), ('patched row 13', rows[13])):
        print(f'  {label}: ' + ' '.join(f'{r[o]:3d}' for o in live))
    print('OK')
