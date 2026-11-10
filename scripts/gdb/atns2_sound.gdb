# atns2_sound.gdb -- jus-atns.2 live half (generic VFX/SFX trigger census).
#
# Frame anchor (physics.md's once-per-frame integrator entry, same anchor
# atns41_hitbox_dump.gdb/atns45_select.gdb use): arm9 0x02082E10. Per frame
# this logs P1/P2 state code (obj+0x18) and HP so sound events can be lined
# up against state transitions (hit-received, KO, dream-attack install).
#
# Fixed addresses (characters/kakashi.md Conditions block, same fixture
# pair atns45_select.gdb used -- Kakashi P1 vs Jotaro P2, both slot 0 of
# their own decks):
#   Kakashi (P1) obj   0x02228E80
#   Jotaro (P2) obj     read each frame from the fighter table 0x021DEB3C
#                        slot 1 (per-state per kakashi.md Hazards -- Jotaro's
#                        obj can move between save/launches, P1's does not)
#   Kakashi HP (u16)    0x021DF1D4 (deck HP record 0, player)
#   Jotaro HP (u16)     0x021DF7F0 (deck HP record 0, opponent)
#
# The sound wrapper, arm9 0x0207342C(category=r0, id=r1) (TRIGGERS.md
# section 0): a dedup-gated request queue. Two breakpoints bracket it:
#
#   0x0207342C (entry): every call attempt, category/id straight from
#     r0/r1, plus the caller's return address (lr) stashed in a global so
#     the accept breakpoint below can still report it even though the
#     free-list branch (taken whenever the dedup node-link path runs)
#     clobbers lr with its own two `bl` targets before falling through.
#     This function does not call back into itself, so the stash is safe
#     across the single, non-reentrant span between the two breakpoints.
#
#   0x02073498 (post-dedup convergence): only the accept path reaches this
#     breakpoint -- the "dropped" `popeq` at 0x02073458 is itself a return
#     from the function, not a fall-through to here (TRIGGERS.md section 0
#     corrected, jus-atns.2 Refuter, live-2026-09-14 pass 2). Both of the
#     *accept* branches converge here instead: the free-list-null skip and
#     the taken free-list node-link path. Category is still r6, id is
#     still r5 (the entry's r0/r1, moved into callee-saved registers at
#     0x02073430/0x02073434 and never touched by the free-list helpers
#     0x2037f58/0x2037f14 in between) -- reaching here means this call got
#     PAST the dedup check and will actually reach the three unresolved
#     play helpers. A logged "sound_entry" with no matching "sound" at the
#     same frame is a dedup-dropped request (it returned via the popeq
#     instead of reaching this breakpoint).
#
# Kept as small as possible per frame (atns43_cancel.gdb's finding: heavy
# per-frame printing across many plan executions under one attach risks
# wedging the bridge) -- no ColPrm/manager walk, no stepi, no watchpoints.
#
# Unlike atns45_select.gdb (a standalone one-shot session), this script
# does NOT set its own `logging file`/`logging enabled` and does NOT end
# with a top-level `continue` -- atns2_sound_run.py drives multiple plans
# from one attach (same recipe cancel_run.py/atns43_cancel.gdb use: "one
# launch, one attach ... per plan: state load then run") and owns `set
# logging file` / `set logging redirect on` / `set logging enabled on`
# (redirect BEFORE enabled, else GDB tees every printf to stdout too and
# an unread pipe wedges the bridge once it fills -- atns43_cancel.gdb's
# finding) plus the initial `continue` itself, issued only after logging
# is fully wired up.

set pagination off
set confirm off
handle SIGILL stop nopass noprint
target remote localhost:3333

set $a2_frame = 0
set $a2_sound_lr = 0
set $a2_kstate_prev = -1

break *0x02082E10
commands
  silent
  set $a2_frame = $a2_frame + 1

  set $a2_kobj = 0x02228E80
  set $a2_jft = *(unsigned int*)(0x021DEB3C + 1*4)

  set $a2_kstate = *(unsigned char*)($a2_kobj + 0x18)
  set $a2_jstate = -1
  if $a2_jft != 0
    set $a2_jstate = *(unsigned char*)($a2_jft + 0x18)
  end

  set $a2_khp = *(unsigned short*)0x021DF1D4
  set $a2_jhp = *(unsigned short*)0x021DF7F0

  # jus-atns.2 P3 tail additions (2026-09-14b, Q2/Q4): $a2_kobj is P1's
  # object slot (same fixed address atns1_dream.gdb uses across fixtures --
  # NOT specific to Kakashi despite the "k" name; it is whichever koma is
  # active in P1's slot). p1_pending (obj+0x19) / p1_1cc (obj+0x1cc, active
  # slot index) are needed for Q2's state-11 entry detection and Q2's
  # "verify slot 2 active" check; the player-deck array base 0x021DF1D4,
  # stride 0x50, +0x25 bit0 gives per-slot active-bit per deck-editor.md.
  set $a2_pending = *(unsigned char*)($a2_kobj + 0x19)
  set $a2_1cc = *(unsigned int*)($a2_kobj + 0x1cc)
  set $a2_s0bit = *(unsigned char*)(0x021DF1D4 + 0x50*0 + 0x25) & 1
  set $a2_s1bit = *(unsigned char*)(0x021DF1D4 + 0x50*1 + 0x25) & 1
  set $a2_s2bit = *(unsigned char*)(0x021DF1D4 + 0x50*2 + 0x25) & 1

  # jus-atns.2 P3 tail fix pass (2026-09-14, Part B, Q3): per-frame P1 SP
  # pool word + bars, so a switch's carry delta is visible even if the
  # carry_id7/carry_id9_pos/carry_id9_neg sites never fire.
  # guard-sp.md §1.4: pool 0x021DF72C, max/cur bars 0x021DF730/0x021DF731.
  set $a2_sp_pool = *(unsigned int*)0x021DF72C
  set $a2_sp_bars = *(unsigned short*)0x021DF730

  printf "{\"type\":\"frame\",\"frame\":%d,\"kstate\":%d,\"jstate\":%d,\"khp\":%d,\"jhp\":%d,\"pending\":%d,\"slot1cc\":%d,\"s0bit\":%d,\"s1bit\":%d,\"s2bit\":%d,\"sp_pool\":%d,\"sp_bars_max_cur\":\"0x%x\"}\n", \
    $a2_frame, $a2_kstate, $a2_jstate, $a2_khp, $a2_jhp, $a2_pending, $a2_1cc, $a2_s0bit, $a2_s1bit, $a2_s2bit, $a2_sp_pool, $a2_sp_bars

  if $a2_kstate == 11 && $a2_kstate_prev != 11
    printf "{\"type\":\"state11_enter\",\"frame\":%d,\"slot1cc\":%d}\n", $a2_frame, $a2_1cc
  end
  set $a2_kstate_prev = $a2_kstate

  continue
end

break *0x0207342C
commands
  silent
  set $a2_sound_lr = $lr
  printf "{\"type\":\"sound_entry\",\"frame\":%d,\"category\":\"0x%x\",\"id\":\"0x%x\",\"lr\":\"0x%x\"}\n", $a2_frame, $r0, $r1, $a2_sound_lr
  continue
end

break *0x02073498
commands
  silent
  printf "{\"type\":\"sound\",\"frame\":%d,\"category\":\"0x%x\",\"id\":\"0x%x\",\"caller\":\"0x%x\"}\n", $a2_frame, $r6, $r5, $a2_sound_lr
  continue
end

# --- jus-atns.2 P3 tail (2026-09-14b) additions below -----------------
#
# Q1: hit-resolution gate. TRIGGERS.md/the combat notes §14 site 0x02082478
# (mov r0,#0x7a; mov r1,#0x28; bl 0x207342c) is reached only if BOTH:
#   0x0208242C  tst r0,#0x2000000 ; beq 0x208247c   (r0 = attacker flag
#               word, loaded at 0x02082424 from [r4+0x40]; branches AROUND
#               the call when bit 25 is CLEAR)
#   0x02082458  tst r1,r0 lsr #3 ; bne 0x208247c    (r1 = status-table
#               byte; branches around the call when the AND is nonzero)
# Logging both test operands at both sites tells us, on any hit where
# 0x28 does NOT fire, which of the two closed it.
#
# Correction (2026-09-14, fix pass, Refuter FAIL on the first tail run):
# at 0x02082458, r0 is NOT the same attacker flag word reloaded/reused --
# 0x02082438-0x02082444 loads [[lit]]+4 and calls `bl 0x2031070` just
# before this breakpoint, so r0 here is that call's RETURN VALUE, a
# distinct value from gate1's flag word. Field renamed below to avoid
# implying it is the same operand.
break *0x0208242C
commands
  silent
  printf "{\"type\":\"gate1\",\"frame\":%d,\"r0_flagword\":\"0x%x\",\"bit25_set\":%d}\n", \
    $a2_frame, $r0, (($r0 & 0x2000000) != 0)
  continue
end

break *0x02082458
commands
  silent
  printf "{\"type\":\"gate2\",\"frame\":%d,\"r0_call_result\":\"0x%x\",\"r1_statusbyte\":\"0x%x\",\"and_nonzero\":%d}\n", \
    $a2_frame, $r0, $r1, (($r1 & ($r0 >> 3)) != 0)
  continue
end

# Q4: KO-adjacent state install handlers (the combat notes §14 "Open" paragraph).
# r0 at entry to both is the fighter object pointer (mov r4,r0 / mov
# r5,r0 immediately after each prologue); lr is the caller so a KO-window
# hit tells us which caller reached these without a separate trace.
break *0x0215C488
commands
  silent
  printf "{\"type\":\"state24_install\",\"frame\":%d,\"obj\":\"0x%x\",\"lr\":\"0x%x\"}\n", $a2_frame, $r0, $lr
  continue
end

break *0x0215CA44
commands
  silent
  printf "{\"type\":\"state25_install\",\"frame\":%d,\"obj\":\"0x%x\",\"lr\":\"0x%x\"}\n", $a2_frame, $r0, $lr
  continue
end

# Q3: SP/HP carry payout. the combat notes §14 site 0x02158BEC (id 7, r4 = fill
# delta, positive-only per the ble at 0x2158bd4) and 0x02158C0C /
# 0x02158C2C (id 9 both sites, r5 = SP delta -- C0C is the r5>0 branch,
# C2C is the r5<0 branch, per the bge/ble pair at 0x2158bf4/0x2158c14).
#
# Correction (2026-09-14, fix pass, Refuter FAIL on the first tail run):
# the original printfs here logged $r0 as "pool_word", but each of these
# three sites sits right after `mov r0,#0x7a` (the sound wrapper's
# category argument, staged immediately before the `bl 0x207342c` these
# breakpoints precede) -- r0 is always 0x7a at these addresses, never the
# pool word. Replaced with the real P1 SP pool word (0x021DF72C,
# guard-sp.md §1.4) and the max/current bar pair right after it
# (0x021DF730/0x021DF731).
break *0x02158BEC
commands
  silent
  set $a2_sp_pool = *(unsigned int*)0x021DF72C
  set $a2_sp_bars = *(unsigned short*)0x021DF730
  printf "{\"type\":\"carry_id7\",\"frame\":%d,\"sp_pool\":%d,\"sp_bars_max_cur\":\"0x%x\",\"r4_delta\":%d,\"r5\":%d}\n", \
    $a2_frame, $a2_sp_pool, $a2_sp_bars, $r4, $r5
  continue
end

break *0x02158C0C
commands
  silent
  set $a2_sp_pool = *(unsigned int*)0x021DF72C
  set $a2_sp_bars = *(unsigned short*)0x021DF730
  printf "{\"type\":\"carry_id9_pos\",\"frame\":%d,\"sp_pool\":%d,\"sp_bars_max_cur\":\"0x%x\",\"r4\":%d,\"r5_delta\":%d}\n", \
    $a2_frame, $a2_sp_pool, $a2_sp_bars, $r4, $r5
  continue
end

break *0x02158C2C
commands
  silent
  set $a2_sp_pool = *(unsigned int*)0x021DF72C
  set $a2_sp_bars = *(unsigned short*)0x021DF730
  printf "{\"type\":\"carry_id9_neg\",\"frame\":%d,\"sp_pool\":%d,\"sp_bars_max_cur\":\"0x%x\",\"r4\":%d,\"r5_delta\":%d}\n", \
    $a2_frame, $a2_sp_pool, $a2_sp_bars, $r4, $r5
  continue
end


# --- jus-atns.2 P3 tail fix pass (2026-09-14, Part B) additions below ---
#
# Q3: the SP-apply calls just above the payout sites (brief's ask) --
# 0x02158BC0 and 0x02158BCC -- log r4/r5 and lr so we can see whether this
# routine is even entered on an ordinary switch, and with what delta,
# independent of whether the id7/id9 payout sites downstream ever fire.
break *0x02158BC0
commands
  silent
  printf "{\"type\":\"sp_apply_bc0\",\"frame\":%d,\"r4\":%d,\"r5\":%d,\"lr\":\"0x%x\"}\n", $a2_frame, $r4, $r5, $lr
  continue
end

break *0x02158BCC
commands
  silent
  printf "{\"type\":\"sp_apply_bcc\",\"frame\":%d,\"r4\":%d,\"r5\":%d,\"lr\":\"0x%x\"}\n", $a2_frame, $r4, $r5, $lr
  continue
end

# Q2: dispatcher 0x021574CC itself -- log r2 (the dispatch code argument)
# and [r4+0x1ac] (the null-checked pointer the 0xB site's body branches
# on) to separate the two candidate causes for the 0xB site's silence:
# "never invoked with r2=11" vs "invoked with r2=11 but [r4+0x1ac] is
# null".
break *0x021574CC
commands
  silent
  set $a2_r4_1ac = *(unsigned int*)($r4 + 0x1ac)
  printf "{\"type\":\"dispatch_02157\",\"frame\":%d,\"r2_code\":%d,\"r4_1ac\":\"0x%x\"}\n", \
    $a2_frame, $r2, $a2_r4_1ac
  continue
end

# Q4: the two alternate state-24 install sites (state-code-handler-table-
# static.md ~165-167) the first tail pass never instrumented.
break *0x0215C690
commands
  silent
  printf "{\"type\":\"state24_install_alt1\",\"frame\":%d,\"obj\":\"0x%x\",\"lr\":\"0x%x\"}\n", $a2_frame, $r0, $lr
  continue
end

break *0x0215C704
commands
  silent
  printf "{\"type\":\"state24_install_alt2\",\"frame\":%d,\"obj\":\"0x%x\",\"lr\":\"0x%x\"}\n", $a2_frame, $r0, $lr
  continue
end
