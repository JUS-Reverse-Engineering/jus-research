# atns1_dream.gdb -- jus-atns.1 (dream attack hit-landing rerun, follow-up
# to closed jus-jh7d). Fixture: pc-taikoubou-npc-jotaro-dark-tournament.
#
# Per-frame anchor, same breakpoint atns45_select.gdb and atns41 use
# (arm9 0x02082E10, once-per-frame integrator pass entry, physics.md §7):
#   FRAME  frame, p1 committed/pending state (obj+0x18/+0x19), p2 state
#          (obj+0x18 of the fighter resolved from the table each frame --
#          P1 may be Taikoubou/Momotaro/Yusuke across a switch, so this is
#          NOT hardcoded to one koma's object), p1/p2 hp, p1/p2 physx/physy
#          (element+0xC/+0x10, opponent elem = own elem+0x40, per jh7d/
#          atns45 addressing), p1 active-slot index (obj+0x1CC), player
#          deck slots 0/1/2 action byte (+0x24) and active bit (+0x25 & 1,
#          deck-editor.md "Test +0x25 & 1, not the +0x24 word"), opponent
#          slot 0 action byte/active bit (sanity -- confirms P2 never
#          switches under us), and the L-offset sweep (Facts item 2): raw
#          u16 words at P1-obj +0x04/+0x06/+0x08 and +0x20/+0x22/+0x24/
#          +0x26, logged every frame so a post-hoc diff around the press
#          can find whether a switch/dream request is stored immediately
#          (queue) or decided fresh inside a window (no stored value until
#          commit).
#
# Event line STATE11_ENTER: fired the frame P1's obj+0x18 (committed state)
# transitions INTO 11 (0x0b) from something else -- the dream-attack state
# code (jh7d finding, the combat notes §12).
#
# Damage capture: break at arm9 0x02082588, one instruction past the
# kind-byte load (0x02082584 `ldrb r4,[r3]`) in the damage formula
# (0x020823E4, called from 0x02081280 inside 0x02080F14, per damage.md §4).
# At this breakpoint (GDB stops BEFORE the addressed instruction executes,
# per every prior probe's convention):
#   r3   moveData pointer ([sl+0x10], loaded at 0x02082570)
#   r4   kind byte (moveData[+0]), just loaded at 0x02082584
#   r5   the scaled base term (damage.md §4 step 2, "r5 = base<<8 * f1/256
#        * f2/256")
#   r0   the running nature-adjusted accumulator (damage.md §4 step 3;
#        gate terms at 0x020825A8+ haven't landed yet at this breakpoint)
#   r1   ldrsb [r3+0xe] (class byte, damage.md §4 step 4's class index)
#   r8   defender-side context pointer ([call-site r0]+0xc, damage.md §4
#        step 1's "r8 = [r0, #0xc]" -- gate word/nature-row source; the
#        nearest thing to a "victim id" available at this program point,
#        since the routine never carries the raw fighter-object pointer
#        this far into its own scratch chain)
#   sl   "the hit element" (call-site r1, damage.md §4 step 1's `mov sl,
#        r1`) -- the nearest available "attacker id" for the same reason.
# These are logged as raw pointers/bytes, not resolved further -- fighter-
# object identity for this hit is NOT reconstructed here (open item, see
# RESULTS.md).

set pagination off
set confirm off
set logging overwrite off
# Deliberately does NOT set `logging file` / `logging enabled on` here --
# atns43_cancel.gdb's own header explains why: the runner (dream_run.py,
# via cancel_run.attach_commands()) owns those, sending `logging redirect
# on` BEFORE `logging enabled on`. Pre-enabling logging here without
# redirect, as an earlier draft of this script did, tees every per-frame
# printf to stdout as well; live batch 1 wedged the emulator paused at a
# suspiciously round, byte-count-sized frame (180 lines, ~360 bytes each
# -- right at a 64KB pipe buffer) on its first three attempts, matching
# cancel_run.py's documented wedge exactly ("an unread stdout pipe fills
# ... GDB blocks in write(), halting the ARM9").
# NOT "stop" -- README.md's "Combined Lua+GDB workflow" section documents
# that a stray SIGILL on this stub, handled as "stop", leaves GDB halted
# forever with nothing to auto-continue it (a known cause of a false
# "0 hits" result that looks identical to a healthy run). "pass" is also
# rejected outright by this gdbstub ("Can't send signals to this remote
# system"). ce7u_shatter*.gdb's "nostop" is the working precedent: SIGILL
# never halts GDB's control flow at all, so the one outstanding `continue`
# just keeps running through it.
handle SIGILL nostop noprint nopass
target remote localhost:3333

set $a1_frame = 0
set $a1_p1_state_prev = -1

break *0x02082E10
commands
  silent
  set $a1_frame = $a1_frame + 1

  set $a1_p1obj = 0x02228E80
  set $a1_p2ft = *(unsigned int*)(0x021DEB3C + 1*4)

  set $a1_p1state = *(unsigned char*)($a1_p1obj + 0x18)
  set $a1_p1pending = *(unsigned char*)($a1_p1obj + 0x19)
  set $a1_p1_1cc = *(unsigned int*)($a1_p1obj + 0x1cc)

  set $a1_p2state = -1
  if $a1_p2ft != 0
    set $a1_p2state = *(unsigned char*)($a1_p2ft + 0x18)
  end

  set $a1_p1physx = *(int*)(0x0220C068 + 0xc)
  set $a1_p1physy = *(int*)(0x0220C068 + 0x10)
  set $a1_p2physx = *(int*)(0x0220C0A8 + 0xc)
  set $a1_p2physy = *(int*)(0x0220C0A8 + 0x10)

  set $a1_p1hp = *(unsigned short*)0x021DF1D4
  set $a1_p2hp = *(unsigned short*)0x021DF7F0

  # player deck records: base 0x021DF1D4, 0x50 apart (slots 0/1/2)
  set $a1_s0act24 = *(unsigned short*)(0x021DF1D4 + 0x50*0 + 0x24)
  set $a1_s0bit = *(unsigned char*)(0x021DF1D4 + 0x50*0 + 0x25) & 1
  set $a1_s1act24 = *(unsigned short*)(0x021DF1D4 + 0x50*1 + 0x24)
  set $a1_s1bit = *(unsigned char*)(0x021DF1D4 + 0x50*1 + 0x25) & 1
  set $a1_s2act24 = *(unsigned short*)(0x021DF1D4 + 0x50*2 + 0x24)
  set $a1_s2bit = *(unsigned char*)(0x021DF1D4 + 0x50*2 + 0x25) & 1

  # opponent slot 0 sanity (does P2 ever "switch" under us -- it shouldn't)
  set $a1_o0act24 = *(unsigned short*)(0x021DF7F0 + 0x24)
  set $a1_o0bit = *(unsigned char*)(0x021DF7F0 + 0x25) & 1

  # L-offset sweep off the P1 object (Facts item 2: +4/+6/+8, +20..+26)
  set $a1_l04 = *(unsigned short*)($a1_p1obj + 0x04)
  set $a1_l06 = *(unsigned short*)($a1_p1obj + 0x06)
  set $a1_l08 = *(unsigned short*)($a1_p1obj + 0x08)
  set $a1_l20 = *(unsigned short*)($a1_p1obj + 0x20)
  set $a1_l22 = *(unsigned short*)($a1_p1obj + 0x22)
  set $a1_l24 = *(unsigned short*)($a1_p1obj + 0x24)
  set $a1_l26 = *(unsigned short*)($a1_p1obj + 0x26)

  printf "{\"type\":\"frame\",\"frame\":%d,\"p1_state\":%d,\"p1_pending\":%d,\"p1_1cc\":%d,\"p2_state\":%d,\"p1hp\":%d,\"p2hp\":%d,\"p1x\":%d,\"p1y\":%d,\"p2x\":%d,\"p2y\":%d,\"s0_a24\":%d,\"s0_bit\":%d,\"s1_a24\":%d,\"s1_bit\":%d,\"s2_a24\":%d,\"s2_bit\":%d,\"o0_a24\":%d,\"o0_bit\":%d,\"l04\":%d,\"l06\":%d,\"l08\":%d,\"l20\":%d,\"l22\":%d,\"l24\":%d,\"l26\":%d,\"p1obj\":\"0x%x\",\"p2obj\":\"0x%x\"}\n", \
    $a1_frame, $a1_p1state, $a1_p1pending, $a1_p1_1cc, $a1_p2state, $a1_p1hp, $a1_p2hp, $a1_p1physx, $a1_p1physy, $a1_p2physx, $a1_p2physy, \
    $a1_s0act24, $a1_s0bit, $a1_s1act24, $a1_s1bit, $a1_s2act24, $a1_s2bit, $a1_o0act24, $a1_o0bit, \
    $a1_l04, $a1_l06, $a1_l08, $a1_l20, $a1_l22, $a1_l24, $a1_l26, $a1_p1obj, $a1_p2ft

  if $a1_p1state == 11 && $a1_p1_state_prev != 11
    printf "{\"type\":\"state11_enter\",\"frame\":%d,\"p1_pending\":%d,\"p1x\":%d,\"p2x\":%d,\"gap\":%d}\n", \
      $a1_frame, $a1_p1pending, $a1_p1physx, $a1_p2physx, ($a1_p2physx - $a1_p1physx)
  end
  set $a1_p1_state_prev = $a1_p1state

  continue
end

break *0x02082588
commands
  silent
  # Guard: this breakpoint sits inside the shared damage-formula routine
  # (0x020823E4), called from the per-frame hit-processing chain
  # (0x02080F14, confirmed by jh7d_dream_attack.gdb to fire every frame
  # independent of any real hit). r3 (the moveData pointer) is only
  # guaranteed valid on a frame where a hit actually connects -- on any
  # other frame reaching this instruction, r3 can be 0 or garbage, and
  # dereferencing it aborts GDB's whole commands list mid-way (the
  # trailing `continue` never runs), wedging the emulator paused forever.
  # Bounds-check against main RAM (jus_plan.py's own MAIN_RAM range)
  # before reading anything through r3.
  if $r3 >= 0x02000000 && $r3 < 0x02400000
    set $a1_kind = *(unsigned char*)$r3
    set $a1_class = *(signed char*)($r3 + 0xe)
    printf "{\"type\":\"hit\",\"frame\":%d,\"movedata\":\"0x%x\",\"kind\":%d,\"class\":%d,\"r5\":%d,\"r0\":%d,\"sl\":\"0x%x\",\"r8\":\"0x%x\",\"p1hp\":%d,\"p2hp\":%d}\n", \
      $a1_frame, $r3, $a1_kind, $a1_class, $r5, $r0, $sl, $r8, \
      *(unsigned short*)0x021DF1D4, *(unsigned short*)0x021DF7F0
  else
    printf "{\"type\":\"hit_skipped_bad_ptr\",\"frame\":%d,\"r3\":\"0x%x\"}\n", $a1_frame, $r3
  end
  continue
end
