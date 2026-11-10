"""Static class-B depth setup, derived from guarded ARM9 instructions.

The orthographic builder at 0x020666F0 writes mode 0 and MTX_LOAD_4x4.
Its reciprocal is Q32, with a Q12 numerator and a rounded Q32 product.
No result of this module is a framebuffer measurement.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys


def _trunc(n, d):
    return (abs(n) // abs(d)) * (-1 if (n < 0) != (d < 0) else 1)


def ortho_words(top, bottom, left, right, near, far, scale):
    if top == bottom or left == right or near == far:
        raise ValueError('zero projection span')
    # 0x02050864/8DC supply (4096 << 32) / span. The W variant
    # scales that reciprocal by scale/4096 before 0x02050D80 rounds.
    def inv(span):
        return _trunc(_trunc(4096 << 32, span) * scale, 4096)
    def mul(a, b):
        return (a * b + (1 << 31)) >> 32
    x, y, z = inv(right-left), inv(top-bottom), inv(far-near)
    return [mul(8192,x),0,0,0, 0,mul(8192,y),0,0,
            0,0,mul(-8192,z),0, mul(-(right+left),x),
            mul(-(top+bottom),y),mul(-(far+near),z),scale]


def class_b_attr(alpha):
    return 0x1f0000c0 | (alpha << 16)


def attr_fields(word):
    return dict(polygon_id=(word >> 24) & 63, alpha=(word >> 16) & 31,
                translucent_depth_write=bool(word & (1 << 11)),
                equal_depth=bool(word & (1 << 14)),
                keep_back=bool(word & (1 << 6)), keep_front=bool(word & (1 << 7)))


def depth(matrix, slot):
    z = ((slot << 8) * matrix[10] >> 12) + matrix[14]
    w = ((slot << 8) * matrix[11] >> 12) + matrix[15]
    if w <= 0:
        raise ValueError('nonpositive clip w')
    return (z + w) / (2 * w)


def rule(matrix, attr):
    fields = attr_fields(attr)
    if fields['equal_depth'] or fields['alpha'] != 31:
        raise ValueError('unproved depth mode')
    a, b = depth(matrix,1),depth(matrix,12)
    if a == b:
        raise ValueError('equal slot depths')
    return 'higher_slot_in_front' if b < a else 'lower_slot_in_front'


# Selected instructions establish the call arguments, ports, register bits,
# class-B caller, and reciprocal arithmetic. A different image is refused.
GUARDS = {
    0x02042cac:0xe59f2054, 0x02042cb0:0xe59f1054,
    0x02042cb4:0xe1a00302, 0x02042cb8:0xe5812000,
    0x02042cbc:0xe58d0000, 0x02042cc0:0xe3a01501,
    0x02042cc4:0xe58d1004, 0x02042cc8:0xe3a00000,
    0x02042ccc:0xe58d1008, 0x02042cd0:0xe3a01001,
    0x02042cd4:0xe58d100c, 0x02042cd8:0xe1a02000,
    0x02042cdc:0xe3a01703, 0x02042ce0:0xe3a03601,
    0x02042ce4:0xe58d0010, 0x02042ce8:0xfa008e80,
    0x02042d08:0xbfff0000, 0x02042d0c:0x04000580,
    0x02042fe0:0xe59f1094, 0x02042fe8:0xe3c00a03,
    0x02042fec:0xe3800008, 0x02042ff0:0xe1c100b0,
    0x02042ff4:0xebffff2a, 0x02043004:0xe59f2074,
    0x02043008:0xe3a0303f, 0x0204300c:0xfa008d0b,
    0x02043078:0xffffcffd, 0x02043080:0x00007fff,
    0x02066460:0x04000350, 0x02066464:0x04000354,
    0x02066880:0x04000440, 0x02066894:0x04000458,
    0x0203ae20:0xe1800302, 0x0203ae2c:0xe1801c03,
    0x0203ae34:0xe1811802, 0x0203ae40:0x040004a4,
    0x01ff80ac:0xe3a00000, 0x01ff80b8:0xe3a02003,
    0x01ff80bc:0xe3a0301f, 0x01ff80c4:0xeb010b53,
    0x01ff82c4:0xe1a01408, 0x01ff82c8:0xe5801030,
}


def decode(arm9):
    for addr, want in GUARDS.items():
        offset = addr - 0x02000000 if addr >= 0x02000000 else 0xa05c0 + addr - 0x01ff8000
        got = struct.unpack_from('<I',arm9,offset)[0]
        if got != want:
            raise ValueError('opcode at 0x%08x: 0x%08x != 0x%08x' % (addr,got,want))
    matrix=ortho_words(0,192<<12,0,256<<12,-1024<<12,1024<<12,1024<<12)
    attr=class_b_attr(31)
    return dict(schema='train-static-depth/v1',grade='DERIVED',
                arm9_sha256=hashlib.sha256(arm9).hexdigest(),
                guards={hex(a):hex(v) for a,v in GUARDS.items()},
                projection=dict(caller='0x02042ca4',builder='0x020666f0',
                                mode=0,load_port='0x04000458',words=matrix),
                polygon_attr=attr,fields=attr_fields(attr),
                dispcnt_update=dict(clear_mask=0x3000,set_mask=8),clear_depth=32767,
                rule=rule(matrix,attr),
                slot_depths={str(s):depth(matrix,s) for s in (1,12)},
                limit='Static derivation. Live setup confirmation is in polygon-receipt.json; framebuffer winning-node attribution remains separate.')


if __name__ == '__main__':
    print(json.dumps(decode(Path(sys.argv[1]).read_bytes()),indent=2,sort_keys=True))
