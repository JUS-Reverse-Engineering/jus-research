#!/usr/bin/env python3
"""Native lifecycle recorder layered on the FXO probe (j6rec): initializer commit/return, allocation generations, shot-art context,
NoteTrack sound ownership and birth-time transforms, all read by GDB at the instruction that decides them.

The layer is opt-in: fxo_tracker.generate(..., lifecycle=True) splices it into the ordinary FXO probe. The default probe text and its
pinned hash are unchanged. Every row starts `TAG gfc=<frame counter read at that instruction>`.

ARM9 facts the rows rest on (arm9.bin at 0x02000000, ov06.bin at 0x0214CD20; opcodes are checked by the native call hooks):

  0x02023894  animation initializer: push {r3,r4,r5,lr}; r5 = object. 0x020238B0 calls the resource lookup, 0x020238B4 `movs r1,r0`,
              0x020238BC `popeq` returns zero when the lookup failed. Otherwise 0x020238D0 binds and 0x020238D4 `mov r0,#1` returns
              success. Every call reaches 0x020238BC; the CPSR Z flag there decides the return. Return rows carry sp, so an entry at
              sp S pairs with returns at S-16.
  0x02023924  shared-effect initializer: tail-jumps to 0x0201C660(r0 = [obj+0x68], r1 = obj, r2 = anim), which pushes eight
              registers. 0x0201C6FC returns 1 (bound), 0x0201C710 returns 0. Entry sp S pairs with returns at S-32.
  0x0201A228  allocator: push {r3,lr}; returns at 0x0201A260 (pool path) and 0x0201A26C (heap path), r0 = block. Entry S, returns S-8.
  0x0201A9EC  pool free: returns 1 at 0x0201AA74 when the block belonged to a pool; returns 0 at 0x0201AA40 or 0x0201AA90 otherwise.
              0x0201AA40 is a block inside an arena but below its pool area. The delete wrappers 0x0204100C/0x02041130 call
              it and, on zero, the heap free 0x0201A958(block, 1). 0x02040FE4 shares their +0x140 count decrement and call to
              0x02021F3C but frees nothing. Entry S, returns S-24.
  0x0201AFA8  pool page carve: 0x0201AFD8 takes 0x800 bytes from the arena (0x0201A5A4) with no null test, builds the page's free
              list and returns the page at 0x0201B070 (r0 = page, r5 = pool). The pool free releases an emptied page through the
              heap free at 0x0201B1DC (lr 0x0201B1E0), so a page is a block whose allocation is this return, not 0x0201A228.
  0x0216C6D0  `bl 0x02023894` inside the shot-art builder 0x0216C5F0: r8 = projectile element (life +0x18, kind +0x1A, effect +0x1C,
              flags +0x26, owner ColPrm +0x28, entity +0x2C), r9 = spawn info, r10 = the builder's output, [r10] = render object,
              r0 = [[[r10]+0xC]+4] the animated object, r1 = animation. 0x0216C64C `str r0,[r10]` links the render object.
  0x021569FC  NoteTrack op 4 sub 2: r0 = owner, r1 = event (u8 sub, u8 op, s16 arg); plays ([owner+0xA6], arg) through 0x0207342C.
              Sub 1 (0x021569E0) plays [owner+0xA4]; sub 0 (0x021569CC) plays category 0x7A.
  0x020734A8  `bl 0x0205DAAC(handle 0x0214BCBC, archive, index)`; 0x020734B0 sees its result in r0 and the handle's player word.

parse(lines) -> ordered rows; inits(rows) -> paired initializer calls; allocations(rows) -> block generations with free calls;
lifecycle(rows) -> per successful initialization, its allocation generation and its end (replacement or free) at instruction time.
Every pairing failure is a named refusal, never a guess.
"""
import re
from collections import namedtuple

GFC = 0x020A0F10
ANIM_ENTRY, SHARED_ENTRY, SHARED_IMPL = 0x02023894, 0x02023924, 0x0201C660
ANIM_FAIL_POP, ANIM_OK = 0x020238BC, 0x020238D4
SHARED_OK, SHARED_FAIL = 0x0201C6FC, 0x0201C710
ALLOC, ALLOC_RET = 0x0201A228, (0x0201A260, 0x0201A26C)
POOL_FREE, POOL_FREE_RET = 0x0201A9EC, {0x0201AA40: 0, 0x0201AA74: 1, 0x0201AA90: 0}
HEAP_FREE = 0x0201A958
PAGE_RET, PAGE_SIZE = 0x0201B070, 0x800
DELETE_WRAPPERS = (0x0204100C, 0x02041130)   # 0x02040FE4 only drops the +0x140 count: it frees nothing
SP_DROP = {ANIM_ENTRY: 16, SHARED_IMPL: 32, ALLOC: 8, POOL_FREE: 24}
Z_FLAG = 1 << 30

Row = namedtuple("Row", "line tag gfc kv")
ROW = re.compile(r"(L[A-Z]{1,4}) gfc=(\d+)(.*)")
KV = re.compile(r"(\w+)=(\S*)")


def _num(v):
    return int(v, 16) if re.fullmatch(r"0x[0-9a-fA-F]+", v) else int(v) if re.fullmatch(r"-?\d+", v) else v


def parse(lines):
    """The lifecycle rows of a probe log, in log order. Other rows (the ordinary FXO stream) are left to fxo_tracker."""
    out = []
    for i, ln in enumerate(lines):
        m = ROW.match(ln)
        if m:
            kv = {k: _num(v) for k, v in KV.findall(m[3])}
            out.append(Row(i, m[1], int(m[2]), kv))
    return out


def _refuse(missing, kind, line, detail):
    missing.append({"kind": kind, "line": None if line is None else line + 1, "detail": detail})


def inits(rows, missing):
    """Pair every initializer entry with its return by the stack pointer. Returns one dict per call, in entry order:
    {pc, obj, anim, gfc, line, lr, ok, ret_gfc, ret_line, ret_pc}. A failed call has ok False and ret_pc 0x020238BC (or 0x0201C710).
    Refusals: init_unpaired (no matching return, or a return with no open call at its sp), init_flag_mismatch (the Z flag at
    0x020238BC contradicts r1), init_object_mismatch (the return's r5 is not the entry's object)."""
    calls, stack = [], []
    for r in rows:
        kv = r.kv
        if r.tag == "LAE" and kv.get("pc") == ANIM_ENTRY:
            c = {"pc": ANIM_ENTRY, "obj": kv["obj"], "anim": kv["anim"], "gfc": r.gfc, "line": r.line, "lr": kv["lr"], "sp": kv["sp"],
                 "ok": None, "ret_gfc": None, "ret_line": None, "ret_pc": None}
            calls.append(c)
            stack.append(c)
        elif r.tag == "LAE" and kv.get("pc") == SHARED_ENTRY:
            c = {"pc": SHARED_ENTRY, "obj": kv["obj"], "anim": kv["anim"], "gfc": r.gfc, "line": r.line, "lr": kv["lr"], "sp": kv["sp"],
                 "ok": None, "ret_gfc": None, "ret_line": None, "ret_pc": None, "impl": False}
            calls.append(c)
            stack.append(c)
        elif r.tag == "LSI":
            top = stack[-1] if stack else None
            if top is not None and top["pc"] == SHARED_ENTRY and top["sp"] == kv["sp"] and not top["impl"] and top["obj"] == kv["obj"]:
                top["impl"] = True
            else:   # another caller of 0x0201C660: an initialization outside the effect entry, paired the same way
                c = {"pc": SHARED_IMPL, "obj": kv["obj"], "anim": kv["anim"], "gfc": r.gfc, "line": r.line, "lr": kv["lr"], "sp": kv["sp"],
                     "ok": None, "ret_gfc": None, "ret_line": None, "ret_pc": None}
                calls.append(c)
                stack.append(c)
        elif r.tag == "LAR":
            pc = kv["pc"]
            drop = 16 if pc in (ANIM_FAIL_POP, ANIM_OK) else 32
            want = (ANIM_ENTRY,) if drop == 16 else (SHARED_ENTRY, SHARED_IMPL)
            top = stack[-1] if stack else None
            if top is None or top["pc"] not in want or top["sp"] - drop != kv["sp"]:
                _refuse(missing, "init_unpaired", r.line, "return at 0x%08x sp 0x%x has no open call" % (pc, kv["sp"]))
                continue
            if drop == 16 and kv.get("obj") != top["obj"]:
                _refuse(missing, "init_object_mismatch", r.line, "r5 0x%x at 0x%08x is not the entry object 0x%x" % (kv.get("obj", -1), pc, top["obj"]))
            if top["pc"] == SHARED_ENTRY and not top["impl"]:
                _refuse(missing, "init_unpaired", r.line, "shared entry at line %d never reached 0x0201C660" % (top["line"] + 1))
            if pc == ANIM_FAIL_POP:
                z = bool(kv["cpsr"] & Z_FLAG)
                if z != (kv["r1"] == 0):
                    _refuse(missing, "init_flag_mismatch", r.line, "Z=%d but r1=0x%x at 0x020238BC" % (z, kv["r1"]))
                if not z:
                    top["bc_line"] = r.line   # the conditional pop does not execute: the call continues to 0x020238D4
                    continue
                ok = False
            elif pc == ANIM_OK:
                if "bc_line" not in top:
                    _refuse(missing, "init_unpaired", r.line, "success at 0x020238D4 without the 0x020238BC test")
                ok = True
            else:
                ok = pc == SHARED_OK
            top.update(ok=ok, ret_gfc=r.gfc, ret_line=r.line, ret_pc=pc)
            stack.pop()
    for c in stack:
        _refuse(missing, "init_unpaired", c["line"], "call at 0x%08x on 0x%x never returned in the log" % (c["pc"], c["obj"]))
    for c in calls:
        c.pop("bc_line", None)
    return calls


def allocations(rows, missing):
    """Allocator calls and frees -> {block: [generation...]}. A generation is {gen, block, size, alloc_gfc, alloc_line, alloc_lr,
    free}; free is None while the block lives, else {gfc, line, kind ('pool' | 'heap'), caller (the delete wrapper's lr when one
    entered first)}. A pool page carve (LMP) starts a generation of size 0x800 marked page=True. gen 0 is a block live before the
    log (no allocator return observed): its size and allocation are unmeasured.
    Refusals: alloc_unpaired, free_unpaired, double_free (a free of a block whose generation already ended), heap_free_after_pool
    (a heap free of a block the pool path already freed)."""
    blocks, open_alloc, open_free, wrappers = {}, [], [], {}   # wrappers: block -> its open delete wrapper's (lr, line); deletes nest
    def live(block):
        """The block's latest generation; a block never seen before is a pre-window generation 0. A freed latest generation is
        returned as is (the caller refuses the second free): only an allocator return starts a new generation."""
        gens = blocks.setdefault(block, [])
        if not gens:
            gens.append({"gen": len(gens) if gens else 0, "block": block, "size": None, "alloc_gfc": None, "alloc_line": None,
                         "alloc_lr": None, "free": None, "pre_window": True})
        return gens[-1]
    for r in rows:
        kv = r.kv
        if r.tag == "LMA":
            open_alloc.append((kv["sp"], kv["size"], kv["lr"], r))
        elif r.tag == "LMR":
            if not open_alloc or open_alloc[-1][0] - SP_DROP[ALLOC] != kv["sp"]:
                _refuse(missing, "alloc_unpaired", r.line, "allocator return sp 0x%x has no open call" % kv["sp"])
                continue
            _sp, size, lr, entry = open_alloc.pop()
            if kv["ptr"] == 0:
                continue
            gens = blocks.setdefault(kv["ptr"], [])
            if gens and gens[-1]["free"] is None:
                _refuse(missing, "double_alloc", r.line, "block 0x%x returned again while generation %d lives" % (kv["ptr"], gens[-1]["gen"]))
            gens.append({"gen": (gens[-1]["gen"] + 1) if gens else 1, "block": kv["ptr"], "size": size, "alloc_gfc": r.gfc,
                         "alloc_line": r.line, "alloc_lr": lr, "free": None, "pre_window": False})
        elif r.tag == "LMP":
            gens = blocks.setdefault(kv["ptr"], [])
            if gens and gens[-1]["free"] is None:
                _refuse(missing, "double_alloc", r.line, "page 0x%x carved again while generation %d lives" % (kv["ptr"], gens[-1]["gen"]))
            gens.append({"gen": (gens[-1]["gen"] + 1) if gens else 1, "block": kv["ptr"], "size": PAGE_SIZE, "alloc_gfc": r.gfc,
                         "alloc_line": r.line, "alloc_lr": PAGE_RET, "free": None, "pre_window": False, "page": True})
        elif r.tag == "LMW" and kv.get("pc") in DELETE_WRAPPERS:
            wrappers[kv["ptr"]] = (kv["lr"], r.line)
        elif r.tag == "LMF":
            open_free.append((kv["sp"], kv["ptr"], r, wrappers.get(kv["ptr"])))
        elif r.tag == "LMFR":
            if not open_free or open_free[-1][0] - SP_DROP[POOL_FREE] != kv["sp"]:
                _refuse(missing, "free_unpaired", r.line, "pool free return sp 0x%x has no open call" % kv["sp"])
                continue
            _sp, ptr, entry, wr = open_free.pop()
            if POOL_FREE_RET.get(kv["pc"]) != (1 if kv["ret"] else 0):
                _refuse(missing, "free_unpaired", r.line, "return 0x%x at 0x%08x contradicts its path" % (kv["ret"], kv["pc"]))
            if kv["ret"]:
                wrappers.pop(ptr, None)
                g = live(ptr)
                if g["free"] is not None:
                    _refuse(missing, "double_free", r.line, "block 0x%x freed twice" % ptr)
                g["free"] = {"gfc": entry.gfc, "line": entry.line, "ret_line": r.line, "kind": "pool", "caller": wr[0] if wr else None}
        elif r.tag == "LMG":
            ptr = kv["ptr"]
            g = live(ptr)
            if g["free"] is not None:
                _refuse(missing, "heap_free_after_pool" if g["free"]["kind"] == "pool" else "double_free", r.line,
                        "heap free of block 0x%x already freed at line %d" % (ptr, g["free"]["line"] + 1))
                continue
            wr = wrappers.pop(ptr, None)
            g["free"] = {"gfc": r.gfc, "line": r.line, "ret_line": None, "kind": "heap", "caller": wr[0] if wr else None}
    for _sp, size, lr, entry in open_alloc:
        _refuse(missing, "alloc_unpaired", entry.line, "allocator call never returned in the log")
    for _sp, ptr, entry, _wr in open_free:
        _refuse(missing, "free_unpaired", entry.line, "pool free of 0x%x never returned in the log" % ptr)
    return blocks


def containing(blocks, obj, line):
    """The allocation generation live at log line `line` whose block contains `obj` ([block, block+size)); the object's own block
    when it was allocated before the log (size unmeasured: only the exact pointer matches). None when no generation contains it."""
    best = None
    for block, gens in blocks.items():
        for g in gens:
            if g.get("page"):
                continue   # a pool page holds object blocks; it is never an object's own allocation
            born = g["alloc_line"] if g["alloc_line"] is not None else -1
            died = g["free"]["line"] if g["free"] is not None else float("inf")
            if not born < line < died:
                continue
            inside = obj == block if g["size"] is None else block <= obj < block + g["size"]
            if inside and (best is None or block > best["block"]):
                best = g
    return best


def lifecycle(rows):
    """Per successful initialization: {obj, anim, pc, gfc, line, alloc: {block, gen} | None, end: {kind, gfc, line} | None}.
    The end of a presentation is the first later SUCCESSFUL initialization of the same object while its allocation generation lives
    (`replaced`), or the free of that generation (`freed`), whichever comes first in call order. Failed initializations end nothing.
    Returns {calls, failed, presentations, blocks, missing}."""
    missing = []
    calls = inits(rows, missing)
    blocks = allocations(rows, missing)
    good = [c for c in calls if c["ok"]]
    pres = []
    for i, c in enumerate(good):
        g = containing(blocks, c["obj"], c["ret_line"])
        nxt = next((d for d in good[i + 1:] if d["obj"] == c["obj"]), None)
        end = None
        if g is not None and g["free"] is not None and (nxt is None or g["free"]["line"] < nxt["ret_line"]):
            end = {"kind": "freed", "gfc": g["free"]["gfc"], "line": g["free"]["line"], "free_kind": g["free"]["kind"], "caller": g["free"]["caller"]}
        elif nxt is not None:
            end = {"kind": "replaced", "gfc": nxt["ret_gfc"], "line": nxt["ret_line"], "by_anim": nxt["anim"]}
        pres.append({"obj": c["obj"], "anim": c["anim"], "pc": c["pc"], "lr": c["lr"], "gfc": c["ret_gfc"], "line": c["ret_line"],
                     "alloc": None if g is None else {"block": g["block"], "gen": g["gen"], "pre_window": g["pre_window"]}, "end": end})
    failed = [c for c in calls if c["ok"] is False]
    return {"calls": calls, "failed": failed, "presentations": pres, "blocks": blocks, "missing": missing}


# ---------------------------------------------------------------------------------------------------------------------------------------
# the GDB layer (spliced into the FXO probe by fxo_tracker.generate(..., lifecycle=True))

G = "*(unsigned int*)0x020A0F10"
DRAW_GATE = 0x01FF80FC   # ITCM draw of class-B drawables: past the cell != -1, resource and frame-data gates; r0 = the element's transform
SHOT_CALL_LR = 0x0216C6D4

HELPERS = r'''
define lcw
  # $arg0 = address, $arg1 = word count: inline comma words, guarded to main RAM and DTCM
  if ($arg0 >= 0x02000000 && $arg0 < 0x023FFF00) || ($arg0 >= 0x027C0000 && $arg0 < 0x027C3F00)
    set $lcw_i = 0
    while $lcw_i < $arg1
      printf "%x,", *(unsigned int*)($arg0 + 4 * $lcw_i)
      set $lcw_i = $lcw_i + 1
    end
  else
    printf "unreachable"
  end
end

define lchain
  # parent chain from node $arg0: node:x:y:z:flags:s12..s48 (words +0x30..+0x48, the node's scale/rotation block) per node
  set $lc_p = $arg0
  set $lc_k = 0
  while $lc_k < 6 && $lc_p >= 0x02000000 && $lc_p < 0x023FFF00
    printf "0x%x:%d:%d:%d:%x:%x.%x.%x.%x.%x.%x.%x;", $lc_p, *(int*)($lc_p+0xc), *(int*)($lc_p+0x10), *(int*)($lc_p+0x14), *(unsigned int*)($lc_p+4), *(unsigned int*)($lc_p+0x30), *(unsigned int*)($lc_p+0x34), *(unsigned int*)($lc_p+0x38), *(unsigned int*)($lc_p+0x3c), *(unsigned int*)($lc_p+0x40), *(unsigned int*)($lc_p+0x44), *(unsigned int*)($lc_p+0x48)
    set $lc_p = *(unsigned int*)($lc_p + 0x18)
    set $lc_k = $lc_k + 1
  end
  printf "end=0x%x", $lc_p
end

define lff
  # $arg0 = slot, $arg1 = the fighter's collision element: owner [el+8], transform node [[owner+4]+0x50] and its parent chain
  set $lf_o = 0
  set $lf_h = 0
  set $lf_n = 0
  if $arg1 >= 0x02000000 && $arg1 < 0x023FFF00
    set $lf_o = *(unsigned int*)($arg1 + 8)
  end
  if $lf_o >= 0x02000000 && $lf_o < 0x023FFF00
    set $lf_h = *(unsigned int*)($lf_o + 4)
  end
  if $lf_h >= 0x02000000 && $lf_h < 0x023FFF00
    set $lf_n = *(unsigned int*)($lf_h + 0x50)
  end
  printf "LFF gfc=%d slot=%d el=0x%x owner=0x%x holder=0x%x node=0x%x chain=", *(unsigned int*)0x020A0F10, $arg0, $arg1, $lf_o, $lf_h, $lf_n
  lchain $lf_n
  printf "\n"
end

define lbirth
  # $arg0 = object at a successful initializer return: its element (+0x50) position and parent chain at that instruction
  if $arg0 >= 0x02000000 && $arg0 < 0x023FFF00
    set $lb_el = *(unsigned int*)($arg0 + 0x50)
    printf "LBR gfc=%d obj=0x%x el=0x%x elvt=0x%x chain=", *(unsigned int*)0x020A0F10, $arg0, $lb_el, ($lb_el >= 0x02000000 && $lb_el < 0x023FFF00) ? *(unsigned int*)$lb_el : 0
    lchain $lb_el
    printf "\n"
  end
end
'''

ENTRY_ROW = ('  printf "LAE gfc=%%d pc=0x%08x obj=0x%%x anim=0x%%x arg=0x%%x sp=0x%%x lr=0x%%x\\n", %s, $r0, $r1, $r2, $sp, $lr\n')
SHOT_ROW = r'''  if $lr == 0x0216C6D4
    printf "LSE gfc=%d obj=0x%x anim=0x%x el=0x%x info=0x%x slot=0x%x ro=0x%x ew=", *(unsigned int*)0x020A0F10, $r0, $r1, $r8, $r9, $r10, ($r10 >= 0x02000000 && $r10 < 0x023FFF00) ? *(unsigned int*)$r10 : 0
    lcw $r8 24
    printf " iw="
    lcw $r9 24
    printf "\n"
  end
'''

LAYER = r'''
set $lse_n = 0

break *0x020238BC
commands
  silent
  printf "LAR gfc=%d pc=0x020238bc obj=0x%x r1=0x%x sp=0x%x cpsr=0x%x\n", *(unsigned int*)0x020A0F10, $r5, $r1, $sp, $cpsr
  continue
end

break *0x020238D4
commands
  silent
  printf "LAR gfc=%d pc=0x020238d4 obj=0x%x r1=0x%x sp=0x%x cpsr=0x%x\n", *(unsigned int*)0x020A0F10, $r5, $r1, $sp, $cpsr
  lbirth $r5
  continue
end

break *0x0201C660
commands
  silent
  printf "LSI gfc=%d ctl=0x%x obj=0x%x anim=0x%x sp=0x%x lr=0x%x\n", *(unsigned int*)0x020A0F10, $r0, $r1, $r2, $sp, $lr
  if $lse_n < 32
    eval "set $lse_o_%d = $r1", $lse_n
    set $lse_n = $lse_n + 1
  end
  continue
end

break *0x0201C6FC
commands
  silent
  printf "LAR gfc=%d pc=0x0201c6fc ok=1 sp=0x%x\n", *(unsigned int*)0x020A0F10, $sp
  if $lse_n > 0
    set $lse_n = $lse_n - 1
    eval "set $lse_co = $lse_o_%d", $lse_n
    lbirth $lse_co
  end
  continue
end

break *0x0201C710
commands
  silent
  printf "LAR gfc=%d pc=0x0201c710 ok=0 sp=0x%x\n", *(unsigned int*)0x020A0F10, $sp
  if $lse_n > 0
    set $lse_n = $lse_n - 1
  end
  continue
end

break *0x0201A228
commands
  silent
  printf "LMA gfc=%d size=0x%x lr=0x%x sp=0x%x\n", *(unsigned int*)0x020A0F10, $r0, $lr, $sp
  continue
end

break *0x0201A260
commands
  silent
  printf "LMR gfc=%d pc=0x0201a260 ptr=0x%x sp=0x%x\n", *(unsigned int*)0x020A0F10, $r0, $sp
  continue
end

break *0x0201A26C
commands
  silent
  printf "LMR gfc=%d pc=0x0201a26c ptr=0x%x sp=0x%x\n", *(unsigned int*)0x020A0F10, $r0, $sp
  continue
end

break *0x0201B070
commands
  silent
  printf "LMP gfc=%d ptr=0x%x pool=0x%x sp=0x%x\n", *(unsigned int*)0x020A0F10, $r0, $r5, $sp
  continue
end

break *0x0201A9EC
commands
  silent
  printf "LMF gfc=%d ptr=0x%x lr=0x%x sp=0x%x\n", *(unsigned int*)0x020A0F10, $r0, $lr, $sp
  continue
end

break *0x0201AA40
commands
  silent
  printf "LMFR gfc=%d pc=0x0201aa40 ret=0x%x sp=0x%x\n", *(unsigned int*)0x020A0F10, $r0, $sp
  continue
end

break *0x0201AA74
commands
  silent
  printf "LMFR gfc=%d pc=0x0201aa74 ret=0x%x sp=0x%x\n", *(unsigned int*)0x020A0F10, $r0, $sp
  continue
end

break *0x0201AA90
commands
  silent
  printf "LMFR gfc=%d pc=0x0201aa90 ret=0x%x sp=0x%x\n", *(unsigned int*)0x020A0F10, $r0, $sp
  continue
end

break *0x0201A958
commands
  silent
  printf "LMG gfc=%d ptr=0x%x r1=0x%x lr=0x%x sp=0x%x\n", *(unsigned int*)0x020A0F10, $r0, $r1, $lr, $sp
  continue
end

break *0x0204100C
commands
  silent
  printf "LMW gfc=%d pc=0x0204100c ptr=0x%x lr=0x%x sp=0x%x\n", *(unsigned int*)0x020A0F10, $r0, $lr, $sp
  continue
end

break *0x02041130
commands
  silent
  printf "LMW gfc=%d pc=0x02041130 ptr=0x%x lr=0x%x sp=0x%x\n", *(unsigned int*)0x020A0F10, $r0, $lr, $sp
  continue
end

break *0x0216EB8C
commands
  silent
  set $lsa_obj = 0
  set $lsa_node = 0
  if $r0 >= 0x02000000 && $r0 < 0x023FFF00
    set $lsa_animholder = *(unsigned int*)($r0+0xc)
    set $lsa_posholder = *(unsigned int*)($r0+8)
    if $lsa_animholder >= 0x02000000 && $lsa_animholder < 0x023FFF00
      set $lsa_obj = *(unsigned int*)($lsa_animholder+4)
    end
    if $lsa_posholder >= 0x02000000 && $lsa_posholder < 0x023FFF00
      set $lsa_posbase = *(unsigned int*)($lsa_posholder+4)
      if $lsa_posbase >= 0x02000000 && $lsa_posbase < 0x023FFF00
        set $lsa_node = *(unsigned int*)($lsa_posbase+0x50)
      end
    end
  end
  printf "LSA gfc=%d holder=0x%x anim=0x%x lr=0x%x obj=0x%x node=0x%x\n", *(unsigned int*)0x020A0F10, $r0, $r1, $lr, $lsa_obj, $lsa_node
  continue
end

break *0x0216C64C
commands
  silent
  printf "LSL gfc=%d ro=0x%x el=0x%x info=0x%x slot=0x%x\n", *(unsigned int*)0x020A0F10, $r0, $r8, $r9, $r10
  continue
end

break *0x021569CC
commands
  silent
  printf "LNT gfc=%d pc=0x021569cc owner=0x%x ev=0x%x evw=0x%x lr=0x%x\n", *(unsigned int*)0x020A0F10, $r0, $r1, *(unsigned int*)$r1, $lr
  continue
end

break *0x021569E0
commands
  silent
  printf "LNT gfc=%d pc=0x021569e0 owner=0x%x ev=0x%x evw=0x%x lr=0x%x fighter=0x%x a4=0x%x a6=0x%x anim=0x%x frame=%d\n", *(unsigned int*)0x020A0F10, $r0, $r1, *(unsigned int*)$r1, $lr, *(unsigned int*)($r0+0x74), *(unsigned short*)($r0+0xa4), *(unsigned short*)($r0+0xa6), *(unsigned int*)($r0+0x94), *(unsigned int*)($r0+0x98)
  continue
end

break *0x021569FC
commands
  silent
  printf "LNT gfc=%d pc=0x021569fc owner=0x%x ev=0x%x evw=0x%x lr=0x%x fighter=0x%x a4=0x%x a6=0x%x anim=0x%x frame=%d\n", *(unsigned int*)0x020A0F10, $r0, $r1, *(unsigned int*)$r1, $lr, *(unsigned int*)($r0+0x74), *(unsigned short*)($r0+0xa4), *(unsigned short*)($r0+0xa6), *(unsigned int*)($r0+0x94), *(unsigned int*)($r0+0x98)
  continue
end

break *0x020734A8
commands
  silent
  printf "LSP gfc=%d handle=0x%x archive=0x%x index=0x%x prev=0x%x\n", *(unsigned int*)0x020A0F10, $r0, $r1, $r2, *(unsigned int*)0x0214BCBC
  continue
end

break *0x01FF80FC
commands
  silent
  set $ld_o = *(unsigned int*)($r10 + 0x38)
  set $ld_e = 0
  if $ld_o >= 0x02000000 && $ld_o < 0x023FFF00
    set $ld_e = *(unsigned int*)($ld_o + 0x50)
  end
  set $ld_m = *(unsigned int*)($r10 + 0x34)
  set $ld_z = -1
  if $ld_m >= 0x02000000 && $ld_m < 0x023FFF00
    set $ld_z = *(unsigned int*)($ld_m + 0x4bc)
  end
  printf "LDX gfc=%d node=0x%x owner=0x%x el=0x%x cell=%d flip=%d hflip=%d attr=0x%x res=0x%x key=%u mgr=0x%x zslot=%d alpha=%u mtx=0x%x mw=", *(unsigned int*)0x020A0F10, $r10, $ld_o, $ld_e, *(short*)($r10 + 0x4a), *(unsigned char*)($r10 + 0x49), *(unsigned char*)($r10 + 0x48), *(unsigned short*)($r10 + 0x24), $r4, *(unsigned short*)($r10 + 6), $ld_m, $ld_z, $r5, $r0
  lcw $r0 16
  printf " chain="
  lchain $ld_e
  printf "\n"
  continue
end
'''

SNDOK_OLD = '  printf "SNDOK gfc=%d ok=%d cat=0x%x id=0x%x\\n", *(unsigned int*)0x020A0F10, $r0, $r6, $r5\n'
SNDOK_NEW = SNDOK_OLD + ('  set $lsh_p = *(unsigned int*)0x0214BCBC\n'
                         '  printf "LSH gfc=%d ok=%d player=0x%x pw=", *(unsigned int*)0x020A0F10, $r0, $lsh_p\n'
                         '  lcw $lsh_p 24\n  printf "\\n"\n')
ANIM_ROWS = {ANIM_ENTRY: '  printf "ANIM gfc=%d r0=0x%08x r1=0x%08x lr=0x%08x\\n", *(unsigned int*)0x020A0F10, $r0, $r1, $lr\n',
             SHARED_ENTRY: '  printf "ANIM gfc=%d r0=0x%08x r1=0x%08x lr=0x%08x pc=0x02023924\\n", *(unsigned int*)0x020A0F10, $r0, $r1, $lr\n'}
FXT_OLD = '  printf "FXT gfc=%%d n=%%d life=%d cap=%d\\n", $fxo_gf, $fxo_n\n'
FXT_NEW = ('  printf "FXT gfc=%%d n=%%d life=%d cap=%d cam=%%d\\n", $fxo_gf, $fxo_n, *(int*)0x020A5C68\n'
           '  lff 0 $atns41_physel0\n  lff 1 $atns41_physel1\n')
ARMED = 'printf "PROBE_ARMED\\n"\ncontinue\n'


def _once(text, old, new, what):
    if text.count(old) != 1:
        raise RuntimeError("fxo_lifecycle: %s: expected exactly one %r in the FXO probe, found %d" % (what, old, text.count(old)))
    return text.replace(old, new)


def splice(text, life, capacity):
    """The FXO probe text (fxo_tracker.generate) with the lifecycle layer added. Existing rows keep their exact format; the FXT
    heartbeat gains ` cam=` and every FXPOS row gains ` chain=` (the element's parent chain), both trailing key=value fields the
    reducer's row patterns already admit. No breakpoint is placed on an instruction whose single step lands on another breakpoint:
    a breakpoint on the `bl 0x02023894` at 0x0216C6D0 made the stub report the initializer entry twice in the j6rec exploration,
    so the shot-art context (r8 element, r9 spawn info, r10 output slot: callee-saved, unchanged by that call) is read at the
    initializer entry when lr is 0x0216C6D4, and the sound player is read at the existing SNDOK stop rather than one instruction later."""
    for pc, row in ANIM_ROWS.items():
        extra = ENTRY_ROW % (pc, G) + (SHOT_ROW if pc == ANIM_ENTRY else "")
        text = _once(text, row, row + extra, "initializer entry 0x%08x" % pc)
    text = _once(text, FXT_OLD % (life, capacity), FXT_NEW % (life, capacity), "heartbeat")
    text = _once(text, SNDOK_OLD, SNDOK_NEW, "sound start")
    out = []
    for ln in text.split("\n"):
        s = ln.lstrip()
        if s.startswith('printf "FXPOS '):
            ind = ln[:len(ln) - len(s)]
            out += [ind + s.replace('\\n"', '"', 1), ind + 'printf " chain="', ind + 'set $lc_start = 0',
                    ind + 'if $fxo_el >= 0x02000000 && $fxo_el < 0x023FFF00',
                    ind + '  set $lc_start = *(unsigned int*)($fxo_el + 0x18)', ind + 'end', ind + 'lchain $lc_start',
                    ind + 'printf "\\n"']
        else:
            out.append(ln)
    text = "\n".join(out)
    if not text.endswith(ARMED):
        raise RuntimeError("fxo_lifecycle: the FXO probe no longer ends with its arm marker")
    head, body = text.split("\n", 1)
    head = head.replace("; do not edit.", "; + lifecycle layer scripts/gdb/fxo_lifecycle.py; do not edit.")
    return head + "\n" + HELPERS + body[:-len(ARMED)] + LAYER + ARMED
