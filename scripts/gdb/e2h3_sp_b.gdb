# scripts/gdb/e2h3_sp_b.gdb (jus-e2h3, corrected field map)
#
# Re-run of the SP measurement with the CORRECTED field map. The prior probe
# scripts/gdb/e2h3_sp.gdb (a different, still-open builder's file — do not
# edit it) hardcoded slot+0x5C8..+0x5CF around a single literal address and
# mislabeled the packed m|c word as "x" (see
# docs/research/findings/sp-apply-0x020781E4-is-a-mixed-radix-pool-with-bar-count.md
# "Live confirmation" section). This file avoids that bug by deriving every
# field address from the *live register* holding the slot pointer at each
# breakpoint, confirmed from static disasm this session
# (scripts/analysis/query.py disasm 0x020781E4 90 / 0x0207834C 30):
#
#   0x020781E4 entry:            r0 = slot, r1 = amount; then r4 = slot for
#                                 the rest of the routine (mov r4,r0 @1E8).
#   0x0207830C / 0x02078328:     r0 = slot at entry (unmodified until the
#                                 strb at the end of each).
#   0x0207834C:                  r0 = slot at entry (mov r4,r0 @0354).
#   0x020782AC:                  r0 = slot, r1 = amount at entry.
#
# Field offsets from the corrected map (jus-e2h3 assignment):
#   x  (u32, fractional pool)  slot+0x5C8
#   m  (s8,  max bars)         slot+0x5CC
#   c  (s8,  bars)             slot+0x5CD
#   free-pass  (s8)            slot+0x5CE
#   refuse-loss (s8)           slot+0x5CF
#
# One GDB attach per emulator launch (scripts/gdb/README.md). Every command
# list ends in `continue` so the Lua bridge keeps driving frames.

set pagination off
set confirm off
set logging file /tmp/jus_emu/e2h3_sp_b_gdb.log
set logging enabled on
target remote localhost:3333

set $framectr = 0

# --- APPLY entry: r0=slot, r1=amount ---------------------------------------
break *0x020781E4
commands
  silent
  printf "APPLY entry slot=%#x amount=%d lr=%#x x=%#x m=%d c=%d\n", \
    $r0, (int)$r1, $lr, *(unsigned int*)($r0+0x5c8), \
    *(signed char*)($r0+0x5cc), *(signed char*)($r0+0x5cd)
  continue
end

# --- APPLY internal stores (r4 = slot throughout this routine) -------------
break *0x02078210
commands
  silent
  printf "APPLY store(neg-add) slot=%#x new_x=%#x m=%d c=%d\n", \
    $r4, $r0, *(signed char*)($r4+0x5cc), *(signed char*)($r4+0x5cd)
  continue
end

break *0x02078258
commands
  silent
  printf "APPLY store(pos-add) slot=%#x new_x=%#x m=%d c=%d\n", \
    $r4, $r0, *(signed char*)($r4+0x5cc), *(signed char*)($r4+0x5cd)
  continue
end

break *0x02078234
commands
  silent
  printf "APPLY store(neg-borrow-ok) slot=%#x new_x=%#x c=%d\n", \
    $r4, $r0, *(signed char*)($r4+0x5cd)
  continue
end

break *0x0207827C
commands
  silent
  printf "APPLY store(pos-carry-ok) slot=%#x new_x=%#x c=%d\n", \
    $r4, $r0, *(signed char*)($r4+0x5cd)
  continue
end

break *0x02078238
commands
  silent
  printf "APPLY store(neg-borrow-fail-clamp0) slot=%#x c=%d\n", \
    $r4, *(signed char*)($r4+0x5cd)
  continue
end

break *0x02078280
commands
  silent
  printf "APPLY store(pos-carry-fail-clamp0) slot=%#x c=%d\n", \
    $r4, *(signed char*)($r4+0x5cd)
  continue
end

break *0x020782A4
commands
  silent
  printf "APPLY tail-clamp(c>=m) slot=%#x x_before=%#x storing=%#x m=%d c=%d\n", \
    $r4, *(unsigned int*)($r4+0x5c8), $r0, \
    *(signed char*)($r4+0x5cc), *(signed char*)($r4+0x5cd)
  continue
end

# --- H1 (bar borrow, c -= 1) and H2 (bar carry, c += 1 bounded by m) -------
break *0x0207830C
commands
  silent
  printf "H1(borrow) entry slot=%#x c_before=%d lr=%#x\n", \
    $r0, *(signed char*)($r0+0x5cd), $lr
  continue
end

# strbpl r1,[r0,#0x5cd] -- the actual c-decrement store inside H1
break *0x0207831C
commands
  silent
  printf "H1(borrow) strb slot=%#x c_new=%d\n", $r0, (int)(signed char)$r1
  continue
end

break *0x02078328
commands
  silent
  printf "H2(carry) entry slot=%#x c_before=%d lr=%#x\n", \
    $r0, *(signed char*)($r0+0x5cd), $lr
  continue
end

# strble r1,[r0,#0x5cd] -- the actual c-increment store inside H2
break *0x02078340
commands
  silent
  printf "H2(carry) strb slot=%#x c_new=%d\n", $r0, (int)(signed char)$r1
  continue
end

# --- spend-bars wrapper entry -----------------------------------------------
break *0x0207834C
commands
  silent
  printf "WRAPPER(0207834C) entry slot=%#x lr=%#x free_pass=%d refuse_loss=%d\n", \
    $r0, $lr, *(signed char*)($r0+0x5ce), *(signed char*)($r0+0x5cf)
  continue
end

# --- affordability check entry + return value ------------------------------
break *0x020782AC
commands
  silent
  printf "CHECK entry slot=%#x amount=%d lr=%#x x=%#x m=%d c=%d\n", \
    $r0, (int)$r1, $lr, *(unsigned int*)($r0+0x5c8), \
    *(signed char*)($r0+0x5cc), *(signed char*)($r0+0x5cd)
  continue
end

# bx lr at the end of 0x020782AC -- r0 is the return value (1=affordable, 0=not)
break *0x02078308
commands
  silent
  printf "CHECK return r0=%d\n", $r0
  continue
end

# --- frame marker: collision-driver entry, fires ~once per emulated frame --
# (0x0207FAD4's $r4==0x220e234 convention is specific to a different,
# projectile-conflict control record from another campaign and will not
# match in these SP states, so this probe uses the driver entry instead,
# per the assignment's "OR" clause.)
break *0x0207F480
commands
  silent
  set $framectr = $framectr + 1
  printf "FRAME #%d\n", $framectr
  continue
end

echo BREAKPOINTS-ARMED\n
continue
