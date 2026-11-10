#!/usr/bin/env python3
"""Disassemble an address range of arm9 or an overlay with capstone.

  python3 scripts/analysis/disasm_range.py 0x02082EC0 0x02083120 [--overlay 6] [--thumb]
"""
import argparse, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import rom_loader, capstone
ap=argparse.ArgumentParser(); ap.add_argument("start"); ap.add_argument("end"); ap.add_argument("--overlay",default=None); ap.add_argument("--thumb",action="store_true")
a=ap.parse_args(); s=int(a.start,16); e=int(a.end,16)
mm=rom_loader.load_memory_map()
data=mm.read(s,e-s,overlay=int(a.overlay) if a.overlay is not None else None)
md=capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB if a.thumb else capstone.CS_MODE_ARM); md.detail=False
for i in md.disasm(data,s):
    print(f"{i.address:08X}  {i.bytes.hex():<8}  {i.mnemonic:<7} {i.op_str}")
