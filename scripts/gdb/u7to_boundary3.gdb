# u7to_boundary3.gdb -- jus-u7to (frame boundary + regen-tick side, round 3).
#
# Round 2 (u7to_boundary2.gdb) found: FIGHTER_TASK/OBJSHOT/INTEGRATOR all
# return to the SAME lr (0x02028628, inside the generic node-invoke thunk
# 0x02028608), confirming they're one sorted scheduler list, walked by
# RING_EXEC_LO (0x02012A14, itself called via a vtable-dispatch wrapper at
# 0x02027978, returning to 0x020279cc). REGEN_TICK (0x02077D40) and PAD_ENTRY
# (0x0203A610) each return to their OWN distinct, non-generic caller
# (0x020768d8 inside function 0x02076510; 0x02028f94 inside function
# 0x02028f68, itself called by 0x02028EE0, the array-walk half of a pair
# with 0x02028F24 -- 0x02028930 is a SEPARATE straight-line
# single-object helper, not an array walker; it also calls 0x02028f68
# but its call site is menu-only) -- neither is part of the sorted list.
# This round's goal: find what calls 0x02027978 (RING_EXEC_LO's immediate
# caller), 0x02028EE0 (PAD's grandparent caller in battle), and 0x02076510
# (REGEN's owner function) -- if all three trace to one shared driver
# function, disassembling that driver statically pins the real order and
# lets us look for a VBlank-wait primitive in it.

set pagination off
set confirm off
set logging file u7to_boundary3.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $u7to_frame = 0
set $u7to_n1 = 0
set $u7to_n2 = 0
set $u7to_n3 = 0

break *0x0207F480
commands
  silent
  set $u7to_frame = $u7to_frame + 1
  printf "FRAME n=%d\n", $u7to_frame
  continue
end

break *0x02027978
commands
  silent
  set $u7to_n1 = $u7to_n1 + 1
  printf "CALLER_OF_RING frame=%d hit_n=%d lr=0x%x r0=0x%x\n", $u7to_frame, $u7to_n1, $lr, $r0
  continue
end

break *0x02028930
commands
  silent
  set $u7to_n2 = $u7to_n2 + 1
  printf "CALLER_OF_PAD frame=%d hit_n=%d lr=0x%x r0=0x%x\n", $u7to_frame, $u7to_n2, $lr, $r0
  continue
end

break *0x02076510
commands
  silent
  set $u7to_n3 = $u7to_n3 + 1
  printf "CALLER_OF_REGEN frame=%d hit_n=%d lr=0x%x r0=0x%x\n", $u7to_frame, $u7to_n3, $lr, $r0
  continue
end

break *0x02156DDC
commands
  silent
  printf "FIGHTER_TASK frame=%d obj=0x%x\n", $u7to_frame, $r0
  continue
end

break *0x0216AF04
commands
  silent
  printf "OBJSHOT frame=%d\n", $u7to_frame
  continue
end

break *0x02082E10
commands
  silent
  printf "INTEGRATOR frame=%d\n", $u7to_frame
  continue
end

continue
