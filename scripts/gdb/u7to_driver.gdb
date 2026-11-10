# u7to_driver.gdb -- jus-u7to (pad-walk driver pick, falsification run).
#
# Open question from RESULTS.md (u7to-boundary-2026-09-12): the pad walk
# 0x02028EE0 is called from two static candidates, both with zero static
# callers found and neither caught live yet:
#   DRIVER_A  0x02034738  inside the accumulator loop 0x02034690
#             (accumulator word 0x020A0DC0, 20.12 fixed-point; r4 = acc>>12
#             is the loop's step count -- read at this same breakpoint)
#   DRIVER_B  0x020422BC  inside 0x02041F9C, after
#             `blx [[r0,#0x1c8]+0x14]`
# Falsification test (as specified by the brief): exactly one of these two
# should fire per battle frame. Whichever does is the real driver.
#
# Also logs, for context and per-frame-boundary bookkeeping:
#   PAD       0x0203A63C  the REG_KEYINPUT read itself (confirmed in
#             trio-2026-09-12/C to be the actual hardware register load,
#             not the 0x0203A640 OR operand)
#   REGEN     0x02076510  bench regen's real scheduler task entry
#             (sort key 0x81000, per RESULTS.md finding 1)
#   FIGHTER   0x02156DDC  fighter per-frame task entry (sort key 0x85000)
#   INTEG     0x02082E10  integrator pass entry (sort key 0xA1000); used
#             here as the once-per-frame counter tick, per prior sessions'
#             confirmation that this entry fires exactly once per frame
#
# Every commands block ends with `continue`; the script ends with a
# trailing top-level `continue` (melonDS's stub halts the CPU on attach --
# see scripts/gdb/README.md, "Emulator silently freezes...").

set pagination off
set confirm off
set logging file u7to_driver.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $u7to_frame = 0
set $u7to_a_n = 0
set $u7to_b_n = 0
set $u7to_pad_n = 0
set $u7to_regen_n = 0
set $u7to_fighter_n = 0

break *0x02082E10
commands
  silent
  set $u7to_frame = $u7to_frame + 1
  printf "FRAME n=%d\n", $u7to_frame
  printf "INTEG frame=%d lr=0x%x\n", $u7to_frame, $lr
  continue
end

break *0x02034738
commands
  silent
  set $u7to_a_n = $u7to_a_n + 1
  printf "DRIVER_A frame=%d hit_n=%d r4=0x%x acc=0x%x lr=0x%x\n", $u7to_frame, $u7to_a_n, $r4, *(unsigned int *)0x020A0DC0, $lr
  continue
end

break *0x020422BC
commands
  silent
  set $u7to_b_n = $u7to_b_n + 1
  printf "DRIVER_B frame=%d hit_n=%d lr=0x%x\n", $u7to_frame, $u7to_b_n, $lr
  continue
end

break *0x0203A63C
commands
  silent
  set $u7to_pad_n = $u7to_pad_n + 1
  printf "PAD frame=%d hit_n=%d lr=0x%x\n", $u7to_frame, $u7to_pad_n, $lr
  continue
end

break *0x02076510
commands
  silent
  set $u7to_regen_n = $u7to_regen_n + 1
  printf "REGEN frame=%d hit_n=%d lr=0x%x\n", $u7to_frame, $u7to_regen_n, $lr
  continue
end

break *0x02156DDC
commands
  silent
  set $u7to_fighter_n = $u7to_fighter_n + 1
  printf "FIGHTER frame=%d hit_n=%d r0=0x%x lr=0x%x\n", $u7to_frame, $u7to_fighter_n, $r0, $lr
  continue
end

continue
