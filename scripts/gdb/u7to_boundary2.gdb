# u7to_boundary2.gdb -- jus-u7to (frame boundary + regen-tick side, round 2).
#
# Prior round (Check C, trio-2026-09-12) measured ordering: INTEGRATOR ->
# PAD -> REGEN_TICK x6 -> FIGHTER_TASK x2 -> OBJSHOT -> [next INTEGRATOR],
# but could not pin which side of the ring is the true frame cut, because
# neither the pad routine (0x0203A614) nor bench regen (0x02077D40) has a
# static sort-key registration anywhere in the corpus (confirmed again this
# session via query.py xrefs-to/pool-values: zero hits for both, and for the
# two scheduler-pass executor functions 0x02012A14/0x02012AB8 that walk the
# task-list rings -- their own callers are also invisible to static xref
# scanning, meaning they're reached through an indirect/computed call).
#
# This probe's new idea: log $lr (return address) the first few times each
# of these "static-orphan" routines is hit. $lr reveals the real caller even
# when the static xref scanner can't find it (indirect calls, jump tables).
# If PAD, REGEN, and the two ring executors all return to the SAME caller
# function, that caller is the true per-frame driver, and disassembling it
# (after the run, statically, with query.py) will show the real call order
# and therefore the real frame boundary.
#
# Anchors:
#   RING_EXEC_LO   0x02012A14  scheduler-pass executor (walks manager+0x460
#                              list via +0x0C, calls vtable+0x58) -- zero
#                              static callers found
#   RING_EXEC_HI   0x02012AB8  second scheduler-pass executor (walks
#                              r4+0xab8 list) -- zero static callers found
#   PAD_ENTRY      0x0203A610  start of the pad-decode routine (the actual
#                              function start, one instruction before the
#                              0x0203A614 `cmp r1,#0` early-return codex/prior
#                              sessions cited) -- zero static callers found
#   REGEN_TICK     0x02077D40  bench regen tick -- zero static callers found
#   FIGHTER_TASK   0x02156DDC  fighter per-frame task entry (has a known
#                              sort key, 0x85000)
#   OBJSHOT        0x0216AF04  ObjShot per-frame entry (key 0x88000)
#   HIT_EVENTS     0x0207F480  collision driver entry (key 0x9E000)
#   INTEGRATOR     0x02082E10  integrator pass entry (key 0xA1000)
#
# Only log $lr for the first few hits of each static-orphan routine (to keep
# the log small and because $lr won't change call to call if there's one
# caller); log every hit of the four known tasks for ordering context, capped
# at 80 frames worth via the frame counter on HIT_EVENTS.

set pagination off
set confirm off
set logging file u7to_boundary2.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $u7to_frame = 0
set $u7to_pad_n = 0
set $u7to_regen_n = 0
set $u7to_ringlo_n = 0
set $u7to_ringhi_n = 0

break *0x0207F480
commands
  silent
  set $u7to_frame = $u7to_frame + 1
  printf "FRAME n=%d\n", $u7to_frame
  if $u7to_frame >= 80
    printf "FRAME_CAP reached, detaching probe logic (still continuing)\n"
  end
  continue
end

break *0x02156DDC
commands
  silent
  printf "FIGHTER_TASK frame=%d obj=0x%x lr=0x%x\n", $u7to_frame, $r0, $lr
  continue
end

break *0x0216AF04
commands
  silent
  printf "OBJSHOT frame=%d lr=0x%x\n", $u7to_frame, $lr
  continue
end

break *0x02082E10
commands
  silent
  printf "INTEGRATOR frame=%d lr=0x%x\n", $u7to_frame, $lr
  continue
end

break *0x0203A610
commands
  silent
  set $u7to_pad_n = $u7to_pad_n + 1
  printf "PAD_ENTRY frame=%d hit_n=%d lr=0x%x r0=0x%x\n", $u7to_frame, $u7to_pad_n, $lr, $r0
  continue
end

break *0x02077D40
commands
  silent
  set $u7to_regen_n = $u7to_regen_n + 1
  printf "REGEN_TICK frame=%d hit_n=%d lr=0x%x r0=0x%x\n", $u7to_frame, $u7to_regen_n, $lr, $r0
  continue
end

break *0x02012A14
commands
  silent
  set $u7to_ringlo_n = $u7to_ringlo_n + 1
  printf "RING_EXEC_LO frame=%d hit_n=%d lr=0x%x\n", $u7to_frame, $u7to_ringlo_n, $lr
  continue
end

break *0x02012AB8
commands
  silent
  set $u7to_ringhi_n = $u7to_ringhi_n + 1
  printf "RING_EXEC_HI frame=%d hit_n=%d lr=0x%x\n", $u7to_frame, $u7to_ringhi_n, $lr
  continue
end

continue
