# jh7d_dream_attack.gdb -- tracker item jus-jh7d (dream attack + chain).
#
#   FRAME       0x0207F480  collision driver entry (frame marker, same as
#                           lxyt_kbrecord.gdb/idiy_kbstage.gdb/etc.) --
#                           $jh7d_frame free-runs from GDB attach and is
#                           NOT aligned to the Lua bridge's plan-relative
#                           frame numbers (RESULTS.md §6).
#
# Reuses the moveData-pointer breakpoint from scripts/gdb/lxyt_kbrecord.gdb
# (0x020817EC, r3 = moveData ptr already loaded, per that file's comment on
# GDB stopping BEFORE the addressed instruction) and adds the arm9 hit-event
# processor entry (0x02080F14, called from 0x02080C28 per guard-sp.md §0.5)
# to see whether a hitbox/hit ever reaches P2 during the R,R(dream),L(dream),
# R(special) chain. One attach, unbounded (runs until the plan ends and the
# harness kills the process), ends in `continue`.

set pagination off
set confirm off
set logging file jh7d_dream_attack.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $jh7d_frame = 0

break *0x0207F480
commands
  silent
  set $jh7d_frame = $jh7d_frame + 1
  continue
end

break *0x020817EC
commands
  silent
  printf "HITPTR frame=%d ptr=0x%x b04=%d b07=%d b0c=%d b0d=%d b0e=%d hitboxctx=0x%x atkctx=0x%x\n", \
    $jh7d_frame, $r3, \
    *(unsigned char*)($r3+0x04), *(unsigned char*)($r3+0x07), \
    *(signed char*)($r3+0x0c), *(signed char*)($r3+0x0d), \
    *(unsigned char*)($r3+0x0e), $r6, $r5
  continue
end

break *0x02080F14
commands
  silent
  printf "HITPROC frame=%d r0=0x%x r1=0x%x r2=0x%x r3=0x%x lr=0x%x\n", \
    $jh7d_frame, $r0, $r1, $r2, $r3, $lr
  continue
end

continue
