#!/usr/bin/env python3
"""Build a CPU-AI patch for the JUS (AJUJ) .nds ROM.

Emits an IPS patch (and optionally a patched .nds) from the findings in
docs/research/side-quests/cpu-ai-levels.md.

Patch levers, in increasing order of intrusiveness:

  L1  data/ai_param.bin  -- raise the per-profile decision-probability bytes
                            that the probability gate at ov11 0x02179130 reads.
                            Granular: per archetype, per character, per byte.
  L2  data/ai_param.bin  -- also revive the dead call site at 0x0217A6C4 by
                            lowering the gate's early-out threshold.
  L3  code/ov11          -- raise the shared threshold table at 0x0218190C.

ROM offsets were located by content search and are verified at build time.

Usage:
  python3 make_cpu_ai_patch.py --tier 1 --out cpu-ai-t1.ips
  python3 make_cpu_ai_patch.py --tier 1 --out patched.nds --whole-rom
  python3 make_cpu_ai_patch.py --tier 3 --out cpu-ai-t3.ips
"""
from __future__ import annotations

import os
import argparse
import hashlib
import struct
import sys
from pathlib import Path

# --- ROM geometry (verified by content search + round-trip) ---------------
OV11_ROM = 0x1D7E00          # arm9_ov11.bin inside the ROM
OV11_BASE = 0x02172A60       # ov11 load address
AI_ROM = 0x00F73260          # chr/ai/ai_param.bin inside the ROM
AI_ROWS = 89
AI_STRIDE = 0x30
OV11_LEN = 61440
AI_LEN = AI_ROWS * AI_STRIDE  # 4272

REPO = Path(__file__).resolve().parents[2]

THRESH_TABLE = 0x0218190C    # 8 x u32, ov11
GATE_CMP = 0x02179130        # 'cmp r1,#0x1b' -- the early-out threshold
GATE_EARLYOUT = 0x02179134   # 'ble #0x2179198' -- the branch that uses it

# Profile byte offsets the probability gate is asked about, from the 11
# direct 'bl 0x02179130' call sites. 0x1A is dead in the stock ROM because
# the gate early-outs for any index <= 0x1B.
GATE_PARAMS = [0x1A, 0x1C, 0x1D, 0x1F, 0x21, 0x22, 0x23, 0x24, 0x25]
LIVE_PARAMS = [p for p in GATE_PARAMS if p > 0x1B]

# Acceptance rates of table entries 0..7, as a fraction of 256.
THRESH = [64, 76, 102, 128, 166, 179, 217, 243]
# Table index to raise every live param to. Index 7 = 243/256 = 95%.
# Index 3 = 128/256 = 50% is the conservative pick; see the doc for why we
# deliberately stop short of "always" (>= 8).
TIER_TARGETS = {1: 3, 2: 7, 3: 7}


def ov_off(addr: int) -> int:
    """ov11 virtual address -> ROM offset."""
    return OV11_ROM + (addr - OV11_BASE)


def find_blob(rom: bytes, blob: bytes, name: str) -> int:
    hits, start = [], 0
    while True:
        i = rom.find(blob, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1
    if len(hits) != 1:
        raise SystemExit(f'{name}: expected exactly 1 match in ROM, got {len(hits)}')
    return hits[0]


def locate(rom: bytes, ov_src: Path, ai_src: Path) -> None:
    """Re-derive both ROM offsets from content, and assert the known offsets."""
    got_ov = find_blob(rom, ov_src.read_bytes(), 'arm9_ov11.bin')
    got_ai = find_blob(rom, ai_src.read_bytes(), 'ai_param.bin')
    if got_ov != OV11_ROM:
        raise SystemExit(f'ov11 moved: expected 0x{OV11_ROM:X}, found 0x{got_ov:X}')
    if got_ai != AI_ROM:
        raise SystemExit(f'ai_param.bin moved: expected 0x{AI_ROM:X}, found 0x{got_ai:X}')


def build_edits(rom: bytes, ov_src: Path, ai_src: Path, tier: int) -> list[tuple[int, bytes, bytes]]:
    """Return (rom_offset, before, after) triples."""
    edits: list[tuple[int, bytes, bytes]] = []
    ai = bytearray(ai_src.read_bytes())

    if tier in (1, 2, 3):
        target = TIER_TARGETS[tier]
        # Rows 1..80 are the 20 archetype groups x 4 difficulty steps.
        # Rows 0 and 81..88 are a default template and a trailing blob that
        # the profile picker never scans, so we leave them alone.
        for row in range(1, 81):
            for off in LIVE_PARAMS:
                cur = ai[row * AI_STRIDE + off]
                if cur >= 8 or cur == target:
                    continue  # already unconditional, or already at target
                before = bytes([cur])
                after = bytes([target])
                edits.append((AI_ROM + row * AI_STRIDE + off, before, after))
                ai[row * AI_STRIDE + off] = target

    if tier in (2, 3):
        # Revive the dead 0x1A call site. Stock: cmp r1,#0x1b ; ble <ret0>.
        # The conditional is 'ble' (0xDA) on the halfword after cmp.
        # Lowering 0x1B -> 0x19 makes index 0x1A reach the threshold compare.
        # Encoding: cmp r1,#imm is 0xE3510<imm> for imm<256, little-endian.
        addr = GATE_CMP
        cur = rom[ov_off(addr):ov_off(addr) + 4]
        exp = struct.pack('<I', 0xE351001B)
        if cur != exp:
            raise SystemExit(f'gate early-out not as expected at 0x{addr:08X}: {cur.hex()}')
        new = struct.pack('<I', 0xE3510019)
        edits.append((ov_off(addr), cur, new))

    if tier == 3:
        # Raise the shared threshold table so even the 0x1A/0x1C/... params
        # and the five band gates that reuse this table fire more often.
        before = rom[ov_off(THRESH_TABLE):ov_off(THRESH_TABLE) + 32]
        after = struct.pack('<8I', 255, 255, 255, 255, 255, 255, 255, 255)
        edits.append((ov_off(THRESH_TABLE), before, after))

    # All edits must actually change the ROM as described.
    for off, before, after in edits:
        if rom[off:off + len(before)] != before:
            raise SystemExit(f'pre-image mismatch at ROM 0x{off:X}: '
                             f'rom={rom[off:off+len(before)].hex()} want={before.hex()}')
    edits.sort(key=lambda e: e[0])
    for i in range(1, len(edits)):
        if edits[i][0] < edits[i - 1][0] + len(edits[i - 1][1]):
            raise SystemExit(f'overlapping edits at 0x{edits[i-1][0]:X}/0x{edits[i][0]:X}')
    return edits


def write_ips(edits, path: Path) -> None:
    """Minimal IPS writer: records -> EOF."""
    out = bytearray(b'PATCH')
    for off, before, after in edits:
        assert len(before) == len(after), 'IPS records keep length constant'
        out += b'@' + struct.pack('>I', off)
        out += bytes((len(after),))     # replacement length (1 byte)
        out += b'\x00\x00'              # compare length (2 bytes, big-endian)
        out += before + after
    out += b'EOF'
    path.write_bytes(bytes(out))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--rom', type=Path, default=Path(os.environ.get('JUS_ROM', 'jus.nds')))
    ap.add_argument('--ov11', type=Path,
                    default=REPO / 'jus_files/arm9/overlays/arm9_ov11.bin')
    ap.add_argument('--ai-param', type=Path,
                    default=REPO / 'jus_files/chrbin/chr/ai/ai_param.bin')
    ap.add_argument('--tier', type=int, choices=[1, 2, 3], required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--whole-rom', action='store_true',
                    help='write a patched .nds instead of an .ips')
    args = ap.parse_args()

    rom = args.rom.read_bytes()
    locate(rom, args.ov11, args.ai_param)
    edits = build_edits(rom, args.ov11, args.ai_param, args.tier)

    n_ai = sum(1 for e in edits if AI_ROM <= e[0] < AI_ROM + AI_LEN)
    n_ov = len(edits) - n_ai

    if args.whole_rom:
        out = bytearray(rom)
        for off, _before, after in edits:
            out[off:off + len(after)] = after
        args.out.write_bytes(bytes(out))
        kind = 'patched ROM'
    else:
        write_ips(edits, args.out)
        kind = 'IPS'

    print(f'tier {args.tier}: {len(edits)} byte edits '
          f'({n_ai} in ai_param.bin, {n_ov} in ov11) -> {kind} {args.out}')
    print(f'  ai_param.bin @ ROM 0x{AI_ROM:X}, ov11 @ ROM 0x{OV11_ROM:X} (base 0x{OV11_BASE:08X})')
    if tier_targets := TIER_TARGETS[args.tier]:
        print(f'  live gate params {["0x%02X" % p for p in LIVE_PARAMS]} '
              f'raised to table index {tier_targets} = {THRESH[tier_targets]}/256 = '
              f'{THRESH[tier_targets] / 256:.0%} acceptance')
    if args.tier >= 3:
        print('  shared threshold table 0x0218190C -> all 255 (unconditional)')
    if args.tier >= 2:
        print('  gate early-out 0x1B -> 0x19, reviving the dead 0x1A call site')
    print(f'  sha256 {hashlib.sha256(args.out.read_bytes()).hexdigest()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
