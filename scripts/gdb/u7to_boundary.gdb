# u7to_boundary.gdb -- jus-u7to (frame boundary + regen-tick side + pad
# sampler verification).
#
# State: pc-momotaro-npc-yusuke-projectiles-about-to-collide, 60 frames,
# no input.
#
# Anchors (re-confirmed this session via `query.py disasm`):
#   PAD_CANDIDATE  0x0203A640  the `ldrh r2,[ip]` codex flagged as the
#                              pad-sampling read; ip is the source register.
#                              is ip == 0x04000130 (REG_KEYINPUT)?
#   FIGHTER_TASK   0x02156DDC  fighter per-frame task entry
#   OBJSHOT        0x0216AF04  ObjShot per-frame entry
#   HIT_EVENTS     0x0207F480  collision driver entry (also used as the
#                              frame marker, consistent with the other two
#                              checks in this campaign)
#   INTEGRATOR     0x02082E10  integrator pass entry (fires once/frame)
#   INTEG_ELEMENT  0x02082E44  right after `ldr lr,[ip,#8]` inside the
#                              integrator's per-element loop body
#                              (0x02082E40) -- lr=element ptr, ip=list node
#   REGEN_TICK     0x02077D40  bench regen tick

set pagination off
set confirm off
set logging file u7to_boundary.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $u7to_frame = 0
set $u7to_local = 0
set $u7to_elem_n = 0

break *0x0207F480
commands
  silent
  set $u7to_frame = $u7to_frame + 1
  set $u7to_local = 0
  set $u7to_elem_n = 0
  printf "FRAME n=%d\n", $u7to_frame
  continue
end

break *0x0203A640
commands
  silent
  set $u7to_local = $u7to_local + 1
  printf "PAD frame=%d local=%d ip=0x%x is_keyinput=%d val=0x%x\n", \
    $u7to_frame, $u7to_local, $ip, ($ip == 0x04000130), *(unsigned short*)$ip
  continue
end

break *0x02156DDC
commands
  silent
  set $u7to_local = $u7to_local + 1
  printf "FIGHTER_TASK frame=%d local=%d obj=0x%x\n", $u7to_frame, $u7to_local, $r0
  continue
end

break *0x0216AF04
commands
  silent
  set $u7to_local = $u7to_local + 1
  printf "OBJSHOT frame=%d local=%d\n", $u7to_frame, $u7to_local
  continue
end

break *0x02077D40
commands
  silent
  set $u7to_local = $u7to_local + 1
  printf "REGEN_TICK frame=%d local=%d\n", $u7to_frame, $u7to_local
  continue
end

break *0x02082E10
commands
  silent
  set $u7to_local = $u7to_local + 1
  set $u7to_elem_n = 0
  printf "INTEGRATOR frame=%d local=%d owner_r0=0x%x\n", $u7to_frame, $u7to_local, $r0
  continue
end

break *0x02082E44
commands
  silent
  set $u7to_elem_n = $u7to_elem_n + 1
  printf "INTEG_ELEMENT frame=%d elem_n=%d node=0x%x element=0x%x\n", \
    $u7to_frame, $u7to_elem_n, $ip, $lr
  continue
end

continue
