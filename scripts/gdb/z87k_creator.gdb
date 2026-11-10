# z87k_creator.gdb -- jus-z87k (pair-entry creation site, live check).
#
# State: pc-taikoubou-upx-npc-yusuke-x, 80 frames, no input. Per yv70 the
# mixed tornado/created pair forms at ~frame 62.
#
# Anchors (all addresses from docs/research/findings/pair-entry-creation-
# site-static.md, this session's static pass, disasm re-confirmed via
# `query.py disasm 0x0207B860 260` before writing this probe):
#   FRAME marker : 0x0207F480  collision driver entry (brief's frame marker)
#   CREATE       : 0x0207ACB8  pair-entry creator/allocator (r1=A, r2=B geo
#                              records, both 0x64-byte records per codex's
#                              correction to the static finding)
#   FINE_TAG     : 0x0207B9E8  first instr after node+0x08/0x0C/0x10/0x11/0x12
#                              are written for a TYPE-2 (fine sub-element
#                              match) creation, inside 0x0207B7F0
#   BROAD_TAG    : 0x0207BA6C  same, for a TYPE-6 (broad-only) creation
#   FINE_AX0     : 0x0207B968  fine-phase axis-0 cmp (r2=|delta|, r0=extent
#                              sum after `add r0,r1,r0`); bgt at 0x0207B96C
#                              skips the pair if this fails
#   FINE_AX1     : 0x0207B9B4  fine-phase axis-1 cmp, same shape
#   BROAD_AX0    : 0x0207B8A8  broad-phase axis-0 cmp, same shape
#   BROAD_AX1    : 0x0207B8F4  broad-phase axis-1 cmp, same shape
#   UNLINK       : 0x0207AD04  unlinker entry (r0=node, r1=manager/free-list
#                              owner, r2=ColObj/wrapper) -- confirms per-
#                              frame stale/duplicate free and, by node addr
#                              recurring across frames, list persistence
#
# GDB breakpoints stop BEFORE the instruction at the breakpoint address
# executes, so registers read at a `cmp` address are exactly the operands
# that `cmp` is about to compare (already loaded by prior instructions in
# the same straight-line block).

set pagination off
set confirm off
set logging file z87k_creator.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $z87k_frame = 0
set $z87k_hits = 0

break *0x0207F480
commands
  silent
  set $z87k_frame = $z87k_frame + 1
  printf "FRAME n=%d\n", $z87k_frame
  continue
end

break *0x0207ACB8
commands
  silent
  set $z87k_hits = $z87k_hits + 1
  printf "CREATE_ENTRY n=%d frame=%d A=0x%x B=0x%x A_wrapper=0x%x B_wrapper=0x%x\n", \
    $z87k_hits, $z87k_frame, $r1, $r2, *(int*)($r1+0x20), *(int*)($r2+0x20)
  continue
end

break *0x0207B9E8
commands
  silent
  printf "FINE_TAG frame=%d node=0x%x node08=0x%x node0c=0x%x node10=0x%x node11=0x%x node12=0x%x\n", \
    $z87k_frame, $r0, *(int*)($r0+0x08), *(int*)($r0+0x0c), \
    *(char*)($r0+0x10) & 0xff, *(char*)($r0+0x11) & 0xff, *(char*)($r0+0x12) & 0xff
  continue
end

break *0x0207BA6C
commands
  silent
  printf "BROAD_TAG frame=%d node=0x%x node08=0x%x node0c=0x%x node10=0x%x node11=0x%x node12=0x%x\n", \
    $z87k_frame, $r0, *(int*)($r0+0x08), *(int*)($r0+0x0c), \
    *(char*)($r0+0x10) & 0xff, *(char*)($r0+0x11) & 0xff, *(char*)($r0+0x12) & 0xff
  continue
end

break *0x0207B968
commands
  silent
  printf "FINE_AX0 frame=%d absdelta=%d extentsum=%d pass=%d\n", $z87k_frame, $r2, $r0, ($r2 <= $r0)
  continue
end

break *0x0207B9B4
commands
  silent
  printf "FINE_AX1 frame=%d absdelta=%d extentsum=%d pass=%d\n", $z87k_frame, $r2, $r0, ($r2 <= $r0)
  continue
end

break *0x0207B8A8
commands
  silent
  printf "BROAD_AX0 frame=%d absdelta=%d extentsum=%d pass=%d\n", $z87k_frame, $r2, $r0, ($r2 <= $r0)
  continue
end

break *0x0207B8F4
commands
  silent
  printf "BROAD_AX1 frame=%d absdelta=%d extentsum=%d pass=%d\n", $z87k_frame, $r2, $r0, ($r2 <= $r0)
  continue
end

break *0x0207AD04
commands
  silent
  printf "UNLINK frame=%d node=0x%x owner=0x%x colobj=0x%x\n", $z87k_frame, $r0, $r1, $r2
  continue
end

continue
