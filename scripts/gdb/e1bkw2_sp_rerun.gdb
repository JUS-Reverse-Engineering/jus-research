# scripts/gdb/e1bkw2_sp_rerun.gdb (jus-1bkw, Part B rerun)
#
# Builds on scripts/gdb/e1bkw_sp_remainder.gdb (kept as-is; this is a
# new file, not an edit, so the first session's probe stays
# reproducible byte-for-byte). Adds, per the Refuter's Part B
# requirements:
#
# - Positive-control breakpoints at the two already-confirmed writers
#   0x0215FCB8 (+0x66/+0x68 copy) and 0x0215FCCC (+0x6A copy), logging
#   the value about to be written (read at entry, before the `strh`,
#   from the SAME halfword the `strh` re-stores -- so no ordering
#   race) and the char/state_block/lr, so every fixture's log carries
#   its own 3840/2560 proof the deposit path is live before any
#   negative result in this same log is trusted.
# - A per-anchor-tick heartbeat: once ANY breakpoint below has seen an
#   SP pool slot address (Q4's or Q5's `r0`), the anchor tick
#   ($e1bkw_frame, same PC 0x02082E10 as the first probe) also logs
#   that slot's pool word (`u32[slot+0x5C8]`) and bar count
#   (`s8[slot+0x5CD]`) every single frame from then on -- so a
#   negative (e.g. Q4 staying zero) has a continuous, per-frame trail
#   proving inputs were registering the whole time, not just a
#   silent gap. Before the first sighting, the heartbeat line is
#   simply not printed (no slot known yet); this is intentional, not
#   a bug -- do not read "heartbeat starts at frame N" as "SP existed
#   only from frame N".
# - A per-anchor-tick guard-flag heartbeat: reads `M+0x40` bit
#   `0x1000` for BOTH fighter-table slots (P1 `0x021DEB3C`, P2
#   `0x021DEB40`) every tick, via the same `M = [[char+0x1a8]+0x10]`
#   chain Q3 already uses -- so guarded/unguarded state around each
#   press in `pc-kenshin-luffy-guard` is read directly every frame,
#   not only at the moment the writer itself fires (which, per the
#   first session's own correction, may not fire on a guarded press
#   at all, giving no reading there otherwise).
#
# - An INPUT_HEARTBEAT every anchor tick: P1's raw input word
#   (`char+0x6c`, same field atns5_guard.gdb reads) so a plan-relative
#   press ("the second B press") can be converted to an absolute
#   `$e1bkw_frame` after the fact by finding that button's bit's
#   rising edge in the log and subtracting 2 (per the ticket brief:
#   "plan press = word edge -2"), instead of trusting an unrecorded
#   offset the way the first Part A session did.
#
# Q1-Q6 breakpoints below are IDENTICAL to e1bkw_sp_remainder.gdb --
# copied, not `source`d, so this file is self-contained and its own
# raw log is directly comparable line-for-line with the first
# session's log format for the same event types.

set pagination off
set confirm off
handle SIGILL stop nopass noprint
target remote localhost:3333

set $e1bkw_frame = 0
set $e1bkw_slot = 0

break *0x02082E10
commands
  silent
  set $e1bkw_frame = $e1bkw_frame + 1
  set $e1bkw_p1in = *(unsigned int*)0x021DEB3C
  if $e1bkw_p1in != 0
    printf "INPUT_HEARTBEAT frame=%d char=%#x input6c=%#x\n", \
      $e1bkw_frame, $e1bkw_p1in, *(unsigned int*)($e1bkw_p1in+0x6c)
  end
  if $e1bkw_slot != 0
    printf "SP_HEARTBEAT frame=%d slot=%#x pool=%u bars=%d\n", \
      $e1bkw_frame, $e1bkw_slot, *(unsigned int*)($e1bkw_slot+0x5c8), \
      *(signed char*)($e1bkw_slot+0x5cd)
  end
  set $e1bkw_p1c = *(unsigned int*)0x021DEB3C
  set $e1bkw_p2c = *(unsigned int*)0x021DEB40
  if $e1bkw_p1c != 0
    set $e1bkw_p1m0 = *(unsigned int*)($e1bkw_p1c+0x1a8)
    if $e1bkw_p1m0 != 0
      set $e1bkw_p1rec = *(unsigned int*)($e1bkw_p1m0+0x10)
      if $e1bkw_p1rec != 0
        printf "GUARD_HEARTBEAT frame=%d who=P1 char=%#x record=%#x bit_1000=%d gauge=%d\n", \
          $e1bkw_frame, $e1bkw_p1c, $e1bkw_p1rec, \
          (*(unsigned int*)($e1bkw_p1rec+0x40) >> 12) & 1, \
          *(unsigned short*)($e1bkw_p1c+0x102)
      end
    end
  end
  if $e1bkw_p2c != 0
    set $e1bkw_p2m0 = *(unsigned int*)($e1bkw_p2c+0x1a8)
    if $e1bkw_p2m0 != 0
      set $e1bkw_p2rec = *(unsigned int*)($e1bkw_p2m0+0x10)
      if $e1bkw_p2rec != 0
        printf "GUARD_HEARTBEAT frame=%d who=P2 char=%#x record=%#x bit_1000=%d gauge=%d\n", \
          $e1bkw_frame, $e1bkw_p2c, $e1bkw_p2rec, \
          (*(unsigned int*)($e1bkw_p2rec+0x40) >> 12) & 1, \
          *(unsigned short*)($e1bkw_p2c+0x102)
      end
    end
  end
  continue
end

# --- Bar-spend fallback: every SP-apply call, by lr -----------------
# 0x020781E4(slot, amount) is the SP-apply routine itself (arm9, per
# the finding doc's title claim). Breaking here directly, and logging
# `lr`, catches every caller including whichever one debits a special's
# bar cost, in case 0x0215AC64 (Q4, the previously-suspected debit
# site) keeps reading amount=0 through the X special.
break *0x020781E4
commands
  silent
  if $e1bkw_slot == 0
    set $e1bkw_slot = $r0
  end
  printf "SPAPPLY frame=%d slot=%#x amount=%d lr=%#x\n", \
    $e1bkw_frame, $r0, (int)$r1, $lr
  continue
end

# --- Positive control: the two confirmed deposit writers ---------------
break *0x0215FCB8
commands
  silent
  printf "WRITER_FCB8 frame=%d state_block=%#x char=%#x val_66=%d val_68=%d lr=%#x\n", \
    $e1bkw_frame, $r0, $r0-0x130, \
    *(unsigned short*)($r0+0x5a), *(unsigned short*)($r0+0x5c), $lr
  continue
end

break *0x0215FCCC
commands
  silent
  printf "WRITER_FCCC frame=%d state_block=%#x char=%#x val_6a=%d lr=%#x\n", \
    $e1bkw_frame, $r0, $r0-0x130, *(unsigned short*)($r0+0x5e), $lr
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
  if $e1bkw_slot == 0
    set $e1bkw_slot = $r0
  end
  printf "Q4_NEGDEBIT frame=%d slot=%#x amount=%d lr=%#x\n", \
    $e1bkw_frame, $r0, (int)$r1, $lr
  continue
end

# --- Q5: ability 55/56 tick cadence --------------------------------------
break *0x02077E3C
commands
  silent
  if $e1bkw_slot == 0
    set $e1bkw_slot = $r0
  end
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

# No top-level `continue` here -- the driver owns `set logging
# redirect/enabled` and issues the first `continue` itself, matching
# e1bkw_sp_remainder.gdb's own contract.
