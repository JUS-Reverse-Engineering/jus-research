# idiy_kbstage.gdb -- jus-idiy (per-character horizontal knockback factor).
#
# Question: physics.md §4.6 says the horizontal shortcut raw_x/128==record+0xC
# holds exactly for some characters but not Kakashi. The static finding
# (horizontal-knockback-per-character-inputs-static.md) found no per-character
# multiplier anywhere on the kbX path and instead flags M+0x148 accumulation
# (the store is `+=`/`-=`, and Kakashi's multi-hit moves might fire the hit
# processor more than once on the same input frame) as the leading hypothesis.
# This probe counts hit-processor invocations and M+0x148/M+0x14A stores per
# frame, so a multi-write frame on Kakashi vs a single-write frame on the
# Kenshin controls settles it directly.
#
# Anchors, all re-confirmed by `query.py disasm 0x020817E8 130` this session
# (same addresses as horizontal-knockback-per-character-inputs-static.md §
# "Stage 1"):
#   FRAME       0x0207F480  collision driver entry (frame marker, same as
#                           other checks in this campaign)
#   HITPROC     0x020817E8  hit-event processor entry; r3=[r6,#0x10]=moveData
#                           ptr at this point (before it's overwritten)
#   KBRAW       0x020817F8  right after the two ldrsb: r4=kbX (raw s8), r3=kbY
#                           (raw s8), both un-shifted/un-scaled
#   MSTAGE      0x0208182C  right after `mul r3,r1,r4` (x=M*(kbX<<7)): r1=M
#                           (the HP-band/weight-derived multiplier, 0x100 on
#                           non-launcher hits), r3=the raw product before >>8
#   KBX_STORE1  0x020818C8  strh [r8,#0xa4] (M+0x148), the "grounded, sign +"
#                           branch: r8=M+0xA4 (so M_base=r8-0xA4), r0=new value
#   KBX_STORE2  0x020818E0  strh [r8,#0xa4], the "grounded, sign -" branch
#   KBX_STORE3  0x02081914  strh [r8,#0xa4], one of the facing-helper branches
#   KBX_STORE4  0x0208192C  strh [r8,#0xa4], the other facing-helper branch
#                           (exactly one of KBX_STORE1..4 fires per HITPROC
#                           call -- they are mutually exclusive branches of
#                           the same `if`)
#   KBY_STORE   0x02081978  strh [r8,#0xa6] (M+0x14A), the y-scale store;
#                           unconditional (always executes once per HITPROC
#                           call, unlike the x side's four-way branch)
#
# GDB breakpoints stop BEFORE the addressed instruction executes.

set pagination off
set confirm off
set logging file idiy_kbstage.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $idiy_frame = 0
set $idiy_hitproc_this_frame = 0
set $idiy_kbx_this_frame = 0
set $idiy_kby_this_frame = 0

break *0x0207F480
commands
  silent
  set $idiy_frame = $idiy_frame + 1
  printf "FRAME n=%d hitproc_prev=%d kbx_stores_prev=%d kby_stores_prev=%d\n", \
    $idiy_frame, $idiy_hitproc_this_frame, $idiy_kbx_this_frame, $idiy_kby_this_frame
  set $idiy_hitproc_this_frame = 0
  set $idiy_kbx_this_frame = 0
  set $idiy_kby_this_frame = 0
  continue
end

break *0x020817E8
commands
  silent
  set $idiy_hitproc_this_frame = $idiy_hitproc_this_frame + 1
  printf "HITPROC frame=%d call_n=%d moveData=0x%x hitboxctx=0x%x atkctx=0x%x\n", \
    $idiy_frame, $idiy_hitproc_this_frame, $r3, $r6, $r5
  continue
end

break *0x020817F8
commands
  silent
  printf "KBRAW frame=%d kbX=%d kbY=%d\n", $idiy_frame, $r4, $r3
  continue
end

break *0x0208182C
commands
  silent
  printf "MSTAGE frame=%d M=%d xproduct=%d\n", $idiy_frame, $r1, $r3
  continue
end

break *0x020818C8
commands
  silent
  set $idiy_kbx_this_frame = $idiy_kbx_this_frame + 1
  printf "KBX_STORE frame=%d site=1(ground+) call_n=%d M_base=0x%x new_val=%d\n", \
    $idiy_frame, $idiy_kbx_this_frame, $r8-0xa4, $r0
  continue
end

break *0x020818E0
commands
  silent
  set $idiy_kbx_this_frame = $idiy_kbx_this_frame + 1
  printf "KBX_STORE frame=%d site=2(ground-) call_n=%d M_base=0x%x new_val=%d\n", \
    $idiy_frame, $idiy_kbx_this_frame, $r8-0xa4, $r0
  continue
end

break *0x02081914
commands
  silent
  set $idiy_kbx_this_frame = $idiy_kbx_this_frame + 1
  printf "KBX_STORE frame=%d site=3(facing-) call_n=%d M_base=0x%x new_val=%d\n", \
    $idiy_frame, $idiy_kbx_this_frame, $r8-0xa4, $r0
  continue
end

break *0x0208192C
commands
  silent
  set $idiy_kbx_this_frame = $idiy_kbx_this_frame + 1
  printf "KBX_STORE frame=%d site=4(facing+) call_n=%d M_base=0x%x new_val=%d\n", \
    $idiy_frame, $idiy_kbx_this_frame, $r8-0xa4, $r0
  continue
end

break *0x02081978
commands
  silent
  set $idiy_kby_this_frame = $idiy_kby_this_frame + 1
  printf "KBY_STORE frame=%d call_n=%d M_base=0x%x new_val=%d\n", \
    $idiy_frame, $idiy_kby_this_frame, $r8-0xa4, $r0
  continue
end

continue
