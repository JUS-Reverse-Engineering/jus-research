# lxyt_kbrecord.gdb -- jus-lxyt (knockback record identification).
#
# jus-idiy's HITPROC probe (scripts/gdb/idiy_kbstage.gdb) broke at
# 0x020817E8, the `ldr r3,[r6,#0x10]` moveData-load instruction itself, so
# every logged moveData pointer read 0x0 (the load hadn't executed yet).
# GDB breakpoints stop BEFORE the addressed instruction. This probe breaks
# one instruction later, at 0x020817EC (`ldrb r0,[r3,#1]`, the type-byte
# read; r3 untouched), where r3 already holds the just-loaded moveData
# pointer -- and dumps the pointer plus the record bytes physics.md/
# move_records.py care about (+0x04 base/frameStart-ish, +0x07 hitstunAdd,
# +0x0C kbX, +0x0D kbY, +0x0E class). The actual sequence from the load:
#   0x020817E8  ldr   r3,[r6,#0x10]   moveData load (the earlier, broken probe)
#   0x020817EC  ldrb  r0,[r3,#1]      type byte -> r0 (this probe's breakpoint)
#   0x020817F0  ldrsb r4,[r3,#0xC]    kbX -> r4 (r3 still untouched)
#   0x020817F4  ldrsb r3,[r3,#0xD]    kbY -> r3 (THIS is the clobber, two
#                                      instructions after the breakpoint, not
#                                      the very next one)
#
# Also carries jus-idiy's MSTAGE/KBX_STORE/KBY_STORE breakpoints so a single
# run ties: record pointer+bytes -> multiplier M -> staged M+0x148/M+0x14A
# write, per hit, per frame.
#
# Anchors (same addresses as horizontal-knockback-per-character-inputs-static.md
# "Stage 1" and idiy_kbstage.gdb; re-confirmed this session):
#   FRAME       0x0207F480  collision driver entry (frame marker)
#   HITPTR      0x020817EC  moveData ptr valid in r3 (fixed break point)
#   MSTAGE      0x0208182C  r1=M (multiplier), r3=raw x-product before >>8
#   KBX_STORE1..4  0x020818C8/0x020818E0/0x02081914/0x0208192C  M+0x148 stores
#   KBY_STORE   0x02081978  M+0x14A store (unconditional)
#
# GDB breakpoints stop BEFORE the addressed instruction executes.

set pagination off
set confirm off
set logging file lxyt_kbrecord.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $lxyt_frame = 0

break *0x0207F480
commands
  silent
  set $lxyt_frame = $lxyt_frame + 1
  printf "FRAME n=%d\n", $lxyt_frame
  continue
end

break *0x020817EC
commands
  silent
  printf "HITPTR frame=%d ptr=0x%x b04=%d b07=%d b0c=%d b0d=%d b0e=%d hitboxctx=0x%x atkctx=0x%x\n", \
    $lxyt_frame, $r3, \
    *(unsigned char*)($r3+0x04), *(unsigned char*)($r3+0x07), \
    *(signed char*)($r3+0x0c), *(signed char*)($r3+0x0d), \
    *(unsigned char*)($r3+0x0e), $r6, $r5
  continue
end

break *0x0208182C
commands
  silent
  printf "MSTAGE frame=%d M=%d xproduct=%d\n", $lxyt_frame, $r1, $r3
  continue
end

break *0x020818C8
commands
  silent
  printf "KBX_STORE frame=%d site=1(ground+) M_base=0x%x new_val=%d\n", $lxyt_frame, $r8-0xa4, $r0
  continue
end

break *0x020818E0
commands
  silent
  printf "KBX_STORE frame=%d site=2(ground-) M_base=0x%x new_val=%d\n", $lxyt_frame, $r8-0xa4, $r0
  continue
end

break *0x02081914
commands
  silent
  printf "KBX_STORE frame=%d site=3(facing-) M_base=0x%x new_val=%d\n", $lxyt_frame, $r8-0xa4, $r0
  continue
end

break *0x0208192C
commands
  silent
  printf "KBX_STORE frame=%d site=4(facing+) M_base=0x%x new_val=%d\n", $lxyt_frame, $r8-0xa4, $r0
  continue
end

break *0x02081978
commands
  silent
  printf "KBY_STORE frame=%d M_base=0x%x new_val=%d\n", $lxyt_frame, $r8-0xa4, $r0
  continue
end

continue
