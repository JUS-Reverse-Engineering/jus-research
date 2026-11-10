#!/usr/bin/env python3
"""ROM census of the effect-animation initializer paths the FXO registration predicate covers (fxo_initializers/v1).

The FXO probe (fxo_tracker.generate) registers an effect object when its animation is initialized by id. This module derives, from
the ARM9 binary and the battle-resident overlays (jus_files/arm9: arm9.bin at 0x02000000, ov06 battle, ov11 battle AI, ov12 UI
library), every way the ROM binds an animation to an object and which call sites can pass a shared-effect id
(0x210000 <= id < 0x250000). The committed fxo_initializers.json is its output; the reducer reads that file, never the ROM.

ARM9 facts, each checked by opcode below (a mismatch raises, so a different ROM never yields a census):

  0x020239B0  bind(object, resource, frame): stores the resource at [object+0x68]. Its direct callers are exactly four:
              0x020238D0  inside 0x02023894, the ordinary initializer: lookup 0x0201C170(object, [object+0x68], id, arg) by id.
              0x02023914  inside 0x020238DC: lookup 0x0201C4CC on a resource-stream object (r2 is an object with a vtable; its +0x2C
                          and +0x28 methods are called at 0x0201C4F8 and 0x0201C50C). No animation id. Its only caller, 0x0201140C,
                          is inside 0x02010D18, a vtable method (word at 0x0209423C).
              0x0201E8E4, 0x0201ED54  inside 0x0201E744 (called from 0x0204B070) and 0x0201EB60 (vtable word 0x0209CC10): rebind a
                          child node to a freshly allocated 0x58-byte resource wrapper (constructor 0x0201E71C). No animation id.
  0x02023924  the shared-effect initializer: tail-jumps through the literal at 0x0202393C to 0x0201C660([object+0x68], object, id),
              which selects the animation whose id matches inside the object's bound resource. 0x0201C660 has no other reference.
  0x0206C7FC  fx_spawn: 0x0206C814..0x0206C820 send ids in [0x210000, 0x250000) to `bl 0x02023924` at 0x0206C884; every other id
              branches to 0x0206C8DC and reaches `bl 0x02023894` at 0x0206C974 with r1 = r8 (callee-saved since 0x0206C804). So
              the return address 0x0206C978 never carries a shared id.
  0x0206CA8C  the GN01 handler: creates the object by id (0x02010ADC, 0x02011B38) and calls 0x02023894 at 0x0206CB88 with no
              range test, so shared ids reach the ordinary initializer here (the Train Y 0x230000 birth, lr 0x0206CB8C).

So the two hooked entries are the only animation-id initializers. A shared id may arrive at either. A site is admissible for a
shared-id registration unless the ROM excludes it: the fx_spawn guard above, or an id argument that is a constant outside the
shared range on a straight run with no incoming direct branch. Anything else (another entry, an lr that is no direct call site
of its entry, an excluded site) is a named reducer refusal (fxo_tracker: unknown_initializer, unproven_initializer_path).

    fxo_initializers.py --write   regenerate fxo_initializers.json from jus_files
    fxo_initializers.py --check   exit 1 when the committed file differs from the ROM census
"""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
OUT = HERE.with_name("fxo_initializers.json")
SCHEMA = "fxo-initializers/v1"

ANIM_ENTRY, SHARED_ENTRY, SHARED_IMPL, BIND = 0x02023894, 0x02023924, 0x0201C660, 0x020239B0
STREAM_ENTRY = 0x020238DC
SHARED_IDS = (0x210000, 0x250000)
BATTLE_OVERLAYS = (6, 11, 12)
BIND_CALLERS = {0x020238D0: "0x02023894 ordinary initializer (lookup 0x0201C170 by id)",
                0x02023914: "0x020238DC resource-stream initializer (lookup 0x0201C4CC; no id)",
                0x0201E8E4: "child-node rebind in 0x0201E744 (no id)",
                0x0201ED54: "child-node rebind in 0x0201EB60 (no id)"}
# address -> instruction word, every fact the census rests on
OPCODES = {
    0x02023894: 0xE92D4038, 0x020238B0: 0xEBFFE22E, 0x020238D0: 0xEB000036,               # push; bl 0x0201C170; bl 0x020239B0
    0x020238DC: 0xE92D4018, 0x020238FC: 0xEBFFE2F2, 0x02023914: 0xEB000025,               # push; bl 0x0201C4CC; bl 0x020239B0
    0x02023924: 0xE59FC010, 0x02023938: 0xE12FFF1C, 0x0202393C: SHARED_IMPL,              # ldr ip,=0x0201C660; bx ip; literal
    0x020239B0: 0xE92D4038, 0x020239D4: 0xE5854068,                                       # bind: push; str r4,[r5,#0x68]
    0x0201C4F8: 0xE592202C, 0x0201C50C: 0xE5911028,                                       # stream lookup: vtable +0x2C, +0x28
    0x0201140C: 0xEB004932, 0x0201E8E4: 0xEB001431, 0x0201ED54: 0xEB001315,
    0x0206C804: 0xE1A08000,                                                               # fx_spawn: mov r8, r0 (the id)
    0x0206C814: 0xE3580821, 0x0206C818: 0x3A00002F,                                       # cmp r8,#0x210000; blo 0x0206C8DC
    0x0206C81C: 0xE3580825, 0x0206C820: 0x2A00002D,                                       # cmp r8,#0x250000; bhs 0x0206C8DC
    0x0206C87C: 0xE1A01008, 0x0206C884: 0xEBFEDC26,                                       # mov r1,r8; bl 0x02023924
    0x0206C8D8: 0xEA000041,                                                               # b 0x0206C9E4 (shared path never falls through)
    0x0206C96C: 0xE1A01008, 0x0206C974: 0xEBFEDBC6,                                       # mov r1,r8; bl 0x02023894
    0x0206CB70: 0xE1A0100B, 0x0206CB88: 0xEBFEDB41,                                       # GN01: mov r1,fp; bl 0x02023894
}
GUARDED = {0x0206C978: "fx_spawn 0x0206C7FC: ids in [0x210000, 0x250000) branch to 0x02023924 at 0x0206C884 (guards 0x0206C814..0x0206C820)"}


def _sx(v, bits):
    return v - (1 << bits) if v & (1 << (bits - 1)) else v


def images(root=ROOT):
    """[(name, base, bytes)] for arm9 and the battle-resident overlays, with each file's sha256."""
    arm9 = Path(root) / "jus_files/arm9"
    meta = json.loads((arm9 / "binaries.json").read_text())
    out = [("arm9", 0x02000000, (arm9 / "arm9.bin").read_bytes())]
    for e in meta["overlays_arm9"]:
        if e["id"] in BATTLE_OVERLAYS:
            out.append(("ov%02d" % e["id"], e["ram_address"], (arm9 / "overlays" / e["file"]).read_bytes()))
    return out


def _word(imgs, addr):
    base, data = imgs[0][1], imgs[0][2]
    return struct.unpack_from("<I", data, addr - base)[0]


def _branches(name, base, data):
    """Every direct ARM B/BL/BLX(imm) and Thumb BL/BLX pair: (site, target, kind)."""
    for off in range(0, len(data) - 3, 4):
        w = struct.unpack_from("<I", data, off)[0]
        if (w >> 25) & 7 == 5:
            pc = base + off
            target = pc + 8 + _sx(w & 0xFFFFFF, 24) * 4
            if w >> 28 == 0xF:
                yield pc, target + ((w >> 24) & 1) * 2, "arm-blx"
            else:
                yield pc, target, ("arm-bl" if (w >> 24) & 1 else "arm-b") + ("" if w >> 28 == 0xE else "-cond")
    for off in range(0, len(data) - 3, 2):
        h1, h2 = struct.unpack_from("<HH", data, off)
        if h1 >> 11 == 0x1E and h2 >> 11 in (0x1F, 0x1D):
            pc = base + off
            target = pc + 4 + _sx(((h1 & 0x7FF) << 12) | ((h2 & 0x7FF) << 1), 23)
            yield pc, (target & ~3) if h2 >> 11 == 0x1D else target, "thumb-blx" if h2 >> 11 == 0x1D else "thumb-bl"


def _literal_refs(base, data, target):
    return [base + off for off in range(0, len(data) - 3, 4) if struct.unpack_from("<I", data, off)[0] in (target, target | 1)]


def _id_argument(name, base, data, call, thumb, targets):
    """The r1 definition reaching a call on its straight run: ('const', value) only for a mov-immediate or pc-relative literal with
    no direct branch landing after it up to the call; otherwise ('dynamic', instruction or reason)."""
    import capstone
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB if thumb else capstone.CS_MODE_ARM)
    md.detail = True
    step = 2 if thumb else 4
    ins = None
    for back in range(64 * step, 0, -step):
        start = call - back
        if start < base:
            continue
        got = list(md.disasm(data[start - base:call - base + 4], start))
        if got and got[-1].address == call:
            ins = got[:-1]
            break
    if ins is None:
        return "dynamic", "undecodable"
    for i in reversed(ins):
        if any(t in targets for t in range(i.address + step, call + 1, step)):
            return "dynamic", "branch target between 0x%08X and the call" % i.address
        if i.group(capstone.CS_GRP_JUMP) or i.group(capstone.CS_GRP_CALL) or i.mnemonic.startswith(("pop", "bx", "blx", "ldm")):
            return "dynamic", "block start at 0x%08X" % i.address
        if capstone.arm.ARM_REG_R1 in i.regs_access()[1]:
            text = "%s %s" % (i.mnemonic, i.op_str)
            if i.cc not in (capstone.arm.ARM_CC_AL, capstone.arm.ARM_CC_INVALID):
                return "dynamic", "conditional " + text
            if i.mnemonic in ("mov", "movs", "mvn", "mvns") and len(i.operands) == 2 and i.operands[1].type == capstone.arm.ARM_OP_IMM:
                v = i.operands[1].imm & 0xFFFFFFFF
                return "const", (~v & 0xFFFFFFFF) if i.mnemonic.startswith("mvn") else v
            if i.mnemonic == "ldr" and i.operands[1].type == capstone.arm.ARM_OP_MEM and i.operands[1].mem.base == capstone.arm.ARM_REG_PC \
                    and i.operands[1].mem.index == 0:
                lit = ((i.address + (4 if thumb else 8)) & ~3) + i.operands[1].mem.disp
                return "const", struct.unpack_from("<I", data, lit - base)[0]
            return "dynamic", text
    return "dynamic", "no definition in the decoded window"


def census(root=ROOT):
    imgs = images(root)
    for addr, word in OPCODES.items():
        if _word(imgs, addr) != word:
            raise ValueError("fxo_initializers: 0x%08X holds 0x%08X, not 0x%08X: another ROM" % (addr, _word(imgs, addr), word))
    branches = {name: list(_branches(name, base, data)) for name, base, data in imgs}
    targets = {name: {t for _, t, _ in b} for name, b in branches.items()}

    def callers(target):
        return [(name, pc, kind) for name, b in branches.items() for pc, t, kind in b if t == target]

    bind = {pc for _, pc, _ in callers(BIND)}
    if bind != set(BIND_CALLERS):
        raise ValueError("fxo_initializers: bind 0x020239B0 callers changed: %s" % sorted("0x%08X" % a for a in bind))
    refs = {e: [(n, pc) for n, base, data in imgs for pc in _literal_refs(base, data, e)] + [(n, pc) for n, pc, _ in callers(e)]
            for e in (SHARED_IMPL, STREAM_ENTRY)}
    if refs[SHARED_IMPL] != [("arm9", 0x0202393C)]:
        raise ValueError("fxo_initializers: 0x0201C660 is referenced outside 0x02023924: %s" % refs[SHARED_IMPL])
    if refs[STREAM_ENTRY] != [("arm9", 0x0201140C)]:
        raise ValueError("fxo_initializers: 0x020238DC has another caller: %s" % refs[STREAM_ENTRY])
    sha = {name: hashlib.sha256(data).hexdigest() for name, _, data in imgs}
    entries = {}
    for entry, role in ((ANIM_ENTRY, "ordinary initializer: lookup by id, then bind"),
                        (SHARED_ENTRY, "shared-effect initializer: select the id inside the bound resource")):
        sites = []
        for name, pc, kind in sorted(callers(entry), key=lambda c: (c[0], c[1])):
            if kind not in ("arm-bl", "thumb-blx"):
                raise ValueError("fxo_initializers: %s call 0x%08X to 0x%08X is a %s" % (name, pc, entry, kind))
            thumb = kind.startswith("thumb")
            base, data = next((b, d) for n, b, d in imgs if n == name)
            how, value = _id_argument(name, base, data, pc, thumb, targets[name])
            lr = pc + 4 + (1 if thumb else 0)
            if lr in GUARDED:
                shared, why = False, GUARDED[lr]
            elif how == "const":
                shared = SHARED_IDS[0] <= value < SHARED_IDS[1]
                why = "constant id 0x%x" % value
            else:
                shared, why = True, "id argument not constant (%s)" % value
            sites.append({"image": name, "call": "0x%08X" % pc, "lr": "0x%08X" % lr, "mode": "thumb" if thumb else "arm",
                          "shared_id_possible": shared, "why": why})
        entries["0x%08X" % entry] = {"role": role, "sites": sites}
    return {"schema": SCHEMA, "generator": "scripts/gdb/fxo_initializers.py", "images": sha,
            "shared_ids": ["0x%X" % SHARED_IDS[0], "0x%X" % SHARED_IDS[1]],
            "bind": {"address": "0x%08X" % BIND, "callers": {"0x%08X" % a: r for a, r in sorted(BIND_CALLERS.items())}},
            "entries": entries}


def dumps(data):
    return json.dumps(data, indent=1, sort_keys=True) + "\n"


def load(path=OUT):
    """{entry pc: frozenset of lr values admissible for a shared-id registration} from the committed census."""
    data = json.loads(Path(path).read_text())
    if data.get("schema") != SCHEMA:
        raise ValueError("fxo_initializers: %s is not %s" % (path, SCHEMA))
    return {int(e, 16): frozenset(int(s["lr"], 16) for s in v["sites"] if s["shared_id_possible"]) for e, v in data["entries"].items()}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    a = p.parse_args(argv)
    text = dumps(census())
    if a.write:
        OUT.write_text(text)
        print("wrote", OUT)
        return 0
    if OUT.read_text() != text:
        print("fxo_initializers.json differs from the ROM census; run --write", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
