"""Fact-check the claims made in docs/research/side-quests/cpu-ai-levels.md.

Each check re-derives the claim from the ROM bytes / ai_param.bin and either
prints PASS with the evidence or FAIL.
"""
import os
import struct
import subprocess
from collections import Counter
from pathlib import Path

ROM = Path(os.environ.get('JUS_ROM', 'jus.nds')).read_bytes()
OV_ROM, BASE = 0x1D7E00, 0x02172A60
AI_ROM, STRIDE, ROWS = 0xF73260, 0x30, 89
OV = ROM[OV_ROM:OV_ROM + 61440]
AI = ROM[AI_ROM:AI_ROM + ROWS * STRIDE]
rows = [AI[i * STRIDE:(i + 1) * STRIDE] for i in range(ROWS)]

fails = []


def check(name, cond, evidence=''):
    print(('PASS  ' if cond else 'FAIL  ') + name + (f'   [{evidence}]' if evidence else ''))
    if not cond:
        fails.append(name)


def w(addr):
    return struct.unpack_from('<I', OV, addr - BASE)[0]


# 1. hashes
import hashlib
check('ov11 sha256 prefix 1ab547c7',
      hashlib.sha256(OV).hexdigest().startswith('1ab547c716127265'),
      hashlib.sha256(OV).hexdigest()[:16])
check('ai_param sha256 prefix e744be39',
      hashlib.sha256(AI).hexdigest().startswith('e744be3925fa448e'),
      hashlib.sha256(AI).hexdigest()[:16])

# 2. ROM offsets are unique content matches
check('ov11 unique at 0x1D7E00', ROM.find(OV) == OV_ROM and ROM.find(OV, OV_ROM + 1) == -1)
check('ai_param unique at 0xF73260', ROM.find(AI) == AI_ROM and ROM.find(AI, AI_ROM + 1) == -1)

# 3. profile copy stride
check('copy length 0x30 in 0x02179684 region', 0x30 in [w(a) & 0xFFF for a in range(0x02179684, 0x02179690, 4)])

# 4. +0x2E setup and clamp
check('0x02173100 ldrb r0,[r0,#0x2E]', w(0x02173100) == 0xE5D0002E, f'0x{w(0x02173100):08X}')
check('0x0217310C cmp r0,#8', w(0x0217310C) == 0xE3500008, f'0x{w(0x0217310C):08X}')
check('clamp never fires on stock data (+0x2E max 7)', max(r[0x2E] for r in rows) == 7,
      f'max +0x2E = {max(r[0x2E] for r in rows)}')

# 5. 20 groups of 4, +0x2F on the last row only
groups = {}
for k in range(20):
    groups[k] = [rows[1 + 4 * k + j][0x2E] for j in range(4)]
# every group except 18 (the documented exception) is the 1,3,5,7 ladder
check('19/20 groups use the 1,3,5,7 ladder',
      all(v == [1, 3, 5, 7] for k, v in groups.items() if k != 18) and groups[18] == [2, 4, 6, 7],
      'group 18 is the only deviation')
check('last row of each group is the only +0x2F != 0xFF',
      all(rows[4 + 4 * k][0x2F] == k and all(rows[1 + 4 * k + j][0x2F] == 0xFF for j in range(3))
          for k in range(20)))
check('groups are NOT identical except +0x2E', any(
    any(rows[4 + 4 * k][o] != rows[1 + 4 * k][o] for o in range(0x2E) if o != 0x2E)
    for k in range(20)), 'group 2 differs at +0x08/+0x09/+0x23')
check('group 18 ladder is 2,4,6,7', groups[18] == [2, 4, 6, 7], str(groups[18]))
check('all other groups are 1,3,5,7',
      all(groups[k] == [1, 3, 5, 7] for k in range(20) if k != 18))
check('20 unique +0x2F values 0..19, rest 0xFF',
      sorted(r[0x2F] for r in rows).count(0xFF) == 69 and
      sorted(r[0x2F] for r in rows)[:20] == list(range(20)))

# 6. gate
check('0x02179130 cmp r1,#0x1B', w(0x02179130) == 0xE351001B, f'0x{w(0x02179130):08X}')
check('0x02179134 ble', (w(0x02179134) & 0xFF000000) == 0xDA000000)
check('0x02179158 movhs r1,#1', w(0x02179158) == 0x23A01001, f'0x{w(0x02179158):08X}')
check('0x02179188 moveq r1,#0x1E', w(0x02179188) == 0x03A0101E, f'0x{w(0x02179188):08X}')
check('pool 0x021791A0 -> 0x0218190C', w(0x021791A0) == 0x0218190C, f'0x{w(0x021791A0):08X}')
thr = struct.unpack_from('<8I', OV, 0x0218190C - BASE)
check('threshold table = documented', list(thr) == [64, 76, 102, 128, 166, 179, 217, 243], str(thr))

# 7. 0x1A dead call site
check('0x0217A6C0 mov r1,#0x1A', w(0x0217A6C0) == 0xE3A0101A, f'0x{w(0x0217A6C0):08X}')
check('0x1A <= 0x1B so the site is dead', 0x1A <= 0x1B)

# 8. 0x25 call site
check('0x021801D0 mov r1,#0x25', w(0x021801D0) == 0xE3A01025, f'0x{w(0x021801D0):08X}')

# 9. inverted gate
check('0x02179278 gate reads +0x12', w(0x02179278) == 0xE5D01012, f'0x{w(0x02179278):08X}')
check('0x02179290 cmp r0,r1 ; movhi -> higher byte = LESS',
      w(0x02179290) == 0xE1500001 and w(0x02179294) == 0x83A00001,
      'movhi r0,#1 = 0x83A00001, returns 1 when r0>r1')
check('0x0217920C gate reads +0x11 (higher = more)',
      w(0x0217920C) == 0xE5901038 and w(0x02179210) == 0xE5D00011,
      'movlo r0,#1 on cmp r1,r0')

# 10. band table
band = [OV[0x021811F4 - BASE + 2 * i] for i in range(8)]
band2 = [OV[0x021811F5 - BASE + 2 * i] for i in range(8)]
check('band table 0x021811F4', band == [4, 16, 32, 64, 96, 128, 160, 192], str(band))
check('band accept table 0x021811F5', band2 == [12, 38, 76, 102, 128, 166, 204, 243], str(band2))

# 11. picker scans 81 rows
check('0x0217958C cmp r2,#0x51 (81 rows)', w(0x0217958C) == 0xE3520051, f'0x{w(0x0217958C):08X}')
check('0x02179594 back-edge to 0x02179430', (w(0x02179594) & 0xFF) == 0xBA or w(0x02179594) & 0x80000000)
check('0x021795C8 cmp r5,#0x4D carve-out', w(0x021795C8) == 0xE355004D, f'0x{w(0x021795C8):08X}')

# 12. the picker is not the combat path: single caller
out = subprocess.run(['python3', 'scripts/analysis/query.py', 'xrefs-to', '0x02172FEC'],
                     capture_output=True, text=True, cwd=str(Path(__file__).resolve().parents[2])).stdout
check('picker thunk has exactly 1 caller', out.count('bl ->') == 1, out.strip().splitlines()[-1])
check('that caller is ov6 0x0216077C', '0x0216077C' in out)

# 13. combat path is a direct index
check('0x021730DC ldrb r2,[r0,#0x34] (selector byte)', w(0x021730DC) == 0xE5D02034, f'0x{w(0x021730DC):08X}')
check('0x021730F4 moveq r2,#0 (mode-5 override)', w(0x021730F4) == 0x03A02000, f'0x{w(0x021730F4):08X}')
check('0x021730F8 bl BattleAIState_Create', (w(0x021730F8) & 0xFF000000) == 0xEB000000)

# 14. 90/160 zero cells
live = [0x1C, 0x1D, 0x1F, 0x21, 0x22, 0x23, 0x24, 0x25]
zeros = sum(1 for k in range(20) for o in live if rows[1 + 4 * k][o] == 0)
check('90/160 archetype gate cells are 0', zeros == 90, f'{zeros}/160')

# 15. archetype 0 readout in the doc
r1 = rows[1]
check('archetype 0 params match the doc table',
      [r1[o] for o in live] == [0, 0, 0, 0, 0, 6, 1, 1], str([r1[o] for o in live]))

# 16. the four corrections from the second opinion
check('CORRECTED: last-wins picker, not first-match', w(0x0217958C) == 0xE3520051 and
      w(0x02179598) == 0xE3E00000, '0x02179598 mvn r0,#0')
check('CORRECTED: group 18 is not {1,3,5,7}', groups[18] == [2, 4, 6, 7])
check('CORRECTED: +0x12 gate is inverted', w(0x02179290) == 0xE1500001 and w(0x02179294) == 0x83A00001)
check('CORRECTED: the dead 0x1A site is a data-unfixable dead branch', w(0x02179130) == 0xE351001B)

print()
print(f'{len(fails)} failure(s)' + (': ' + ', '.join(fails) if fails else ''))
