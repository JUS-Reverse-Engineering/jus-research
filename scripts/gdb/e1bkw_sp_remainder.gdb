# scripts/gdb/e1bkw_sp_remainder.gdb (jus-1bkw)
#
# Remainder-of-jus-36wu probe: one script, all six open SP-deposit
# questions, reused across all three fixtures (addresses are fixed;
# only which events actually fire differs per fixture). Follows the
# atns5_guard_run.py idiom (scripts/analysis/atns5_guard_run.py):
# - no `set logging file`/`enabled on` here -- the driver
#   (scripts/analysis/e1bkw_sp_run.py) owns that AFTER attaching, via
#   `set logging redirect on` then `enabled on`, per attach_commands().
# - a per-frame anchor breakpoint (0x02082E10, same frame-tick PC
#   atns43_cancel.gdb/atns5_guard.gdb use) maintains a running frame
#   counter ($e1bkw_frame) that every OTHER breakpoint's printf also
#   emits, so events from different breakpoints can be correlated on
#   one shared, monotonic frame axis without cross-contaminating each
#   other's own per-type row numbering (never renumber `frame` over
#   mixed rows -- a standing discipline note).
#
# Q1: snapshot trigger, 0x0215FB88. Logs lr, r0 (state block; char =
#   r0-0x130), frame, and a 3-deep backtrace (bt) to distinguish
#   match-start / per-hit / per-koma-switch / per-frame cadence and
#   name the caller.
# Q2: index space. 0x0215FD00 (r1=idx accumulator-add site), Fragment B
#   0x0215FC20 (r1=idx, bit-already-set test), 0x0215FCE4 (r1=idx,
#   +0x64 gate bit test). Also logs +0xC bitmask before the Fragment B
#   test (Fragment B itself reads/sets it) and at the +0x64 gate.
# Q3: guard flag at the hit writer, 0x0215EB3C. Per the ov6 disasm read
#   this session (0x0215EAEC prologue: push {r3,r4,r5,lr}; mov r4,r0 --
#   r4 holds the victim char pointer for the whole handler, unclobbered
#   up to and including this call site's own `add r0,r4,#0x130`), so at
#   this breakpoint r4 == victim char. The ticket brief's "record" is
#   the SAME `M` atns5_guard.gdb already documents and uses successfully
#   (guard-sp.md §0.5): `M = [[char+0x1a8]+0x10]` -- NOT `[char+0x1a8]`
#   directly (an earlier version of this probe read only the single
#   indirection and got a pointer-shaped, non-bitmask value out of
#   `record+0x40`; caught live on `pc-kenshin-luffy-guard`'s first
#   session and corrected before any conclusion was drawn from it --
#   see RESULTS.md's Q3 section). Logs `M+0x40` bit `0x1000`, victim
#   char, and which fighter-table slot (P1/P2, via arm9 0x021DEB3C) the
#   victim char matches.
# Q4: negative debit, 0x0215AC64. Logs amount (r1) and lr across all
#   fixtures.
# Q5: ability 55/56 tick cadence, 0x02077E3C. Logs frame, the SP pool
#   ADDRESS (`slot`, r0 -- NOT the pool word's value; nothing here
#   dereferences it) and the applied delta (`amount`, r1), plus koma
#   (r4) and its `+0x4b`/`+0x4c` signed bytes -- NOT hardcoded to one
#   fixture's slot address; the driver reads slot addresses itself.
#   Cadence is computed from the shared frame counter in
#   post-processing, not from this breakpoint's own fields.
# Q6: the 5120/+0x62 candidate, 0x0215FD68. Logs lr and +0x5A before/after
#   the add (this is the `ldrh +0x5a; ldrh +0x62; add; strh +0x5a`
#   accumulator-add site per the finding doc's Fragment A section).
#
# One GDB attach per emulator launch (scripts/gdb/README.md convention).

set pagination off
set confirm off
handle SIGILL stop nopass noprint
target remote localhost:3333

set $e1bkw_frame = 0

break *0x02082E10
commands
  silent
  set $e1bkw_frame = $e1bkw_frame + 1
  continue
end

# --- Q1: snapshot trigger ---------------------------------------------
break *0x0215FB88
commands
  silent
  printf "Q1_SNAPSHOT frame=%d state_block=%#x char=%#x lr=%#x\n", \
    $e1bkw_frame, $r0, $r0-0x130, $lr
  printf "Q1_BACKTRACE frame=%d\n", $e1bkw_frame
  bt 3
  continue
end

# --- Q2: index space ----------------------------------------------------
break *0x0215FD00
commands
  silent
  printf "Q2_ACCUM_ADD frame=%d state_block=%#x char=%#x idx=%d lr=%#x\n", \
    $e1bkw_frame, $r0, $r0-0x130, $r1, $lr
  continue
end

break *0x0215FC20
commands
  silent
  printf "Q2_FRAGB_ENTRY frame=%d state_block=%#x char=%#x idx=%d bit_already_set=%d mask_before=%#x lr=%#x\n", \
    $e1bkw_frame, $r0, $r0-0x130, $r1, (*(unsigned int*)($r0+0xc) >> $r1) & 1, \
    *(unsigned int*)($r0+0xc), $lr
  continue
end

break *0x0215FCE4
commands
  silent
  printf "Q2_GATE64 frame=%d state_block=%#x char=%#x idx=%d mask_before=%#x bit_set=%d table_val=%#x lr=%#x\n", \
    $e1bkw_frame, $r0, $r0-0x130, $r1, *(unsigned int*)($r0+0xc), \
    (*(unsigned int*)($r0+0xc) >> $r1) & 1, *(unsigned short*)($r0+0x16+2*$r1), $lr
  continue
end

# --- Q3: guard flag at the hit writer (0x0215EB3C, victim char = r4) ----
break *0x0215EB3C
commands
  silent
  set $e1bkw_p1 = *(unsigned int*)0x021DEB3C
  set $e1bkw_p2 = *(unsigned int*)0x021DEB40
  set $e1bkw_m0 = *(unsigned int*)($r4+0x1a8)
  set $e1bkw_record = *(unsigned int*)($e1bkw_m0+0x10)
  printf "Q3_HITWRITER frame=%d victim_char=%#x is_p1=%d is_p2=%d m0=%#x record=%#x record_40=%#x guard_bit_1000=%d lr=%#x\n", \
    $e1bkw_frame, $r4, ($r4 == $e1bkw_p1), ($r4 == $e1bkw_p2), $e1bkw_m0, $e1bkw_record, \
    *(unsigned int*)($e1bkw_record+0x40), (*(unsigned int*)($e1bkw_record+0x40) >> 12) & 1, $lr
  continue
end

# --- Q4: negative debit --------------------------------------------------
break *0x0215AC64
commands
  silent
  printf "Q4_NEGDEBIT frame=%d slot=%#x amount=%d lr=%#x\n", \
    $e1bkw_frame, $r0, (int)$r1, $lr
  continue
end

# --- Q5: ability 55/56 tick cadence --------------------------------------
break *0x02077E3C
commands
  silent
  printf "Q5_ABILITY5556 frame=%d slot=%#x amount=%d koma=%#x koma_4b=%d koma_4c=%d lr=%#x\n", \
    $e1bkw_frame, $r0, (int)$r1, $r4, *(signed char*)($r4+0x4b), *(signed char*)($r4+0x4c), $lr
  continue
end

# --- Q6: the 5120/+0x62 candidate ---------------------------------------
break *0x0215FD68
commands
  silent
  printf "Q6_CANDIDATE_BEFORE frame=%d state_block=%#x char=%#x pre_5a=%#x val_62=%#x lr=%#x\n", \
    $e1bkw_frame, $r0, $r0-0x130, *(unsigned short*)($r0+0x5a), *(unsigned short*)($r0+0x62), $lr
  continue
end

break *0x0215FD78
commands
  silent
  printf "Q6_CANDIDATE_AFTER frame=%d state_block=%#x char=%#x post_5a=%#x\n", \
    $e1bkw_frame, $r0, $r0-0x130, *(unsigned short*)($r0+0x5a)
  continue
end

# No top-level `continue` here: the driver (scripts/analysis/e1bkw_sp_run.py)
# sets logging redirect/enabled AFTER this script loads and only then
# issues its own first `continue` -- matching atns5_guard.gdb's contract
# exactly (a top-level continue here would start streaming breakpoint
# output to the raw gdb-process stdout, not the log file, before logging
# is turned on).
