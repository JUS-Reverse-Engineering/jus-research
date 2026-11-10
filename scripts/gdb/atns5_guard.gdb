# atns5_guard.gdb -- jus-atns.5. Per-frame guard-release / attack-acceptance
# probe. Derived from scripts/gdb/atns43_cancel.gdb (same frame anchor
# 0x02082E10, same JSON-line convention, same "no top-level continue, no
# own `set logging file`" contract -- the driver (atns5_guard_run.py)
# attaches after a state load, owns `set logging redirect on`/`enabled on`,
# and issues the first `continue` itself, per atns43's own header and the
# moveset-mapping-framework.md §5 preflight table).
#
# Unlike atns43, every fighter-relative read here is off the fighter table
# (arm9 0x021DEB3C, +0 = P1, +4 = P2, physics.md §5) rather than a
# hardcoded Kakashi object address, so the same probe works for Yusuke
# (reached in the taikoubou fixture by an L-button roster switch) without
# editing.
#
# Fields (guard-sp.md §0.5/§0.7/§0.8; physics.md §5):
#   - P1 obj+0x18 state code ("state")
#   - P2 obj+0x18 state code ("state2")
#   - P1 obj+0x11A guard-entry lock, byte, arms to 6 on manual guard entry,
#     drains 1/frame ("lock")
#   - P1's M = [[obj+0x1a8]+0x10] (guard-sp.md §0.5's ColPrm scratch block,
#     resolved dynamically every frame off P1's own object -- NOT a
#     hardcoded fixed address, so this generalizes across fixtures/
#     characters unlike the Kenshin-session addresses guard-sp.md §0.8
#     quotes for that state only):
#       - M+0x78 bit 26 (0x04000000) -- the live "is guarding" flag
#         ("guard_bit")
#       - M+0x40 bit 0x1000 -- the blocked-hit marker, set every frame a
#         block landed on this fighter ("blocked_latch")
#   - hp1/hp2: both fighters' HP, u16 at the fixed deck-record-0 addresses
#     0x021DF1D4 (slot 0) / 0x021DF7F0 (slot 1) -- same addressing atns43
#     already uses; these are deck-record addresses (indexed by roster
#     slot), not object-relative, so they track whichever fighter is
#     currently active in that slot (including after an L/R switch)
#   - P1 obj+0x6c input word, bit 0x02 (Down, confirmed unambiguous --
#     guard-sp.md §0.7) as "in_down", and bits 0x80/0x100 (B and Y, "in
#     unresolved order" per that same section) as "in_x80"/"in_x100" --
#     logged raw so the driver can determine empirically, per fixture,
#     which one tracks the B press (e.g. by correlating with the plan's
#     own B-press segment in a B_standalone run) rather than assuming.
#     These give an OBSERVED, per-frame button-edge signal independent of
#     the plan's own nominal frame numbers, which drift by a warm-up
#     offset between `state load` and `run` (same phenomenon cancel_run.py
#     documents for its own captures) -- the driver's detector anchors on
#     these observed edges, not on the plan's nominal button_up/press
#     frame. **`in_down` is a held LEVEL** (reads 1 for the whole DOWN
#     hold, 0->1 at press, 1->0 at release -- confirmed live over a
#     30-frame hold). **`in_x80`/`in_x100` are one-frame press EDGES, not
#     levels** (a B held for the plan's own 3-frame press length still
#     reads `in_x80`==1 on only ONE of those frames, confirmed live --
#     jus-atns.5 RESULTS.md's basis note) -- do not read either as "the
#     button is currently held".
#   - ids: ALL live (cnt>0) geometry element ids across the full 128-
#     record ColPrm sweep (atns41_hitbox_dump.gdb's manager-sweep
#     pattern), capped at 8 ids/frame before jus-wmqi.2 (now 64, and
#     logged as "recs" -- see below). NOT filtered to "P1's own"
#     records: a live check found record 11's wrapper `+0x18` ("owner")
#     reads an address that is NOT the fighter-table P1 object pointer
#     (0x02024F4C vs Kakashi's own 0x02228E80 on
#     pc-kakashi-npc-jotaro-dark-tournament) -- whatever `+0x18` is, it
#     is not usable as an owner filter the way this probe first assumed
#     (jus-atns.5 RESULTS.md, "the owner-filter dead end"). The ticket
#     brief's own fallback for Yusuke ("sweep the ColPrm manager for all
#     records with cnt>0") is used for BOTH characters instead: the id
#     list here can include hurtboxes/hitboxes from either fighter, and
#     the driver cross-checks first-hitbox timing against P1's own
#     acceptance frame and P2's hp to judge plausibility rather than
#     trusting ownership.
#
# One JSON line per frame, type "frame":
#   {"type":"frame","frame":N,"state":S,"state2":S2,"lock":L,
#    "guard_bit":G,"blocked_latch":B,"in_down":D,"in_x80":X80,
#    "in_x100":X100,"hp1":H1,"hp2":H2,"poked":P, <wmqi.2 fields>,
#    "recs":[[record,id],...]}
#
# wmqi.2 fields (jus-wmqi.2, 2026-09-22):
#   - w64/w68/w6c/w70: raw P1 obj words at +0x64..+0x70, hex. +0x6c is
#     the input word: 0x80 B pressed this frame, 0x400 B held, 0x100 Y
#     pressed, 0x800 Y held, 0x2 DOWN held, 0x4 LEFT held, 0x4000 L
#     pressed, 0x8000 R pressed (read live, docs/research/feel-captures/
#     wmqi2-guard-2026-09-22/RESULTS.md). Touch input does not appear here.
#   - act1/act2: bitmask of active deck slots, bit i = record i's +0x25
#     bit 0, P1 records at 0x021DF1D4 + 0x50*i, P2 at 0x021DF7F0 + 0x50*i.
#   - chr1/chr2: chr_b (+0x29) of slots 0..3 on each side.
#   - hp1s/hp2s: current HP (u16, 1/64) of slots 0..3 on each side. hp1 and
#     hp2 are slot 0 only, which is the deck leader, not the active fighter.
#   - x1/x2: physics x of P1 and the opponent (0x0220C068 / 0x0220C0A8
#     element +0xC; fixed addresses valid on the pc-kakashi-* states).
#   - recs replaces the old "ids" list: live elements as [record index,
#     element id], capped at 64 per frame and 8 per record.
#     atns5_guard_run.normalize_row rebuilds "ids" from it for the
#     detectors.
# plus one "manager" line the first time the ColPrm manager resolves.
#
# Manager resolution: same self-verifying sweep atns41/atns43 use (seeded
# from 0x0220DDE0, accepted when candidate+0 == candidate+0x454) -- a
# one-shot breakpoint on the constructor does not work from a mid-battle
# savestate load.

set pagination off
set confirm off
set logging overwrite off
handle SIGILL stop nopass noprint
target remote localhost:3333

set $atns5_frame = 0
set $atns5_manager = 0
set $atns5_manager_resolved = 0

# -- jus-atns.5 round 2, job B: lock-vs-minimum-duration poke discriminator.
# $atns5_poke_mode is set from the command line (-ex "set $atns5_poke_mode =
# N") before this script loads; 0 = off (every other job/trial), 1 = write
# 12 into P1 obj+0x11A on the SAME frame the lock is observed armed to 6
# (lock model predicts clear 6 frames later than the unpoked tap; ~7-frame
# minimum-duration model predicts no change), 2 = write 0 into obj+0x11A one
# frame after that arm frame (i.e. press+4, since arm is press+3 -- lock
# model predicts the flag can clear as early as this poke; minimum-duration
# model predicts it still holds ~7 frames). Both are reactive (triggered off
# the OBSERVED lock==6 edge, not a precomputed absolute frame number) so
# they need no knowledge of this session's cumulative frame counter.
set $atns5_poke_done = 0
set $atns5_poke_armed = 0
set $atns5_poke_since = 0

break *0x02082E10
commands
  silent
  set $atns5_frame = $atns5_frame + 1

  if $atns5_manager_resolved == 0
    set $atns5_seed = 0x0220DDE0 - 0x1000
    set $atns5_k = 0
    while $atns5_k < 0x2000 && $atns5_manager_resolved == 0
      set $atns5_cand = $atns5_seed + $atns5_k
      set $atns5_self = *(unsigned int*)$atns5_cand
      if $atns5_self == $atns5_cand + 0x454
        set $atns5_manager = $atns5_cand
        set $atns5_manager_resolved = 1
        printf "{\"type\":\"manager\",\"addr\":\"0x%x\"}\n", $atns5_manager
      end
      set $atns5_k = $atns5_k + 4
    end
  end

  # -- P1/P2 objects off the fighter table --
  set $atns5_ft = 0x021DEB3C
  set $atns5_p1obj = *(unsigned int*)$atns5_ft
  set $atns5_p2obj = *(unsigned int*)($atns5_ft + 4)

  set $atns5_state = -1
  set $atns5_lock = -1
  set $atns5_guard_bit = -1
  set $atns5_blocked_latch = -1
  set $atns5_in_down = -1
  set $atns5_in_x80 = -1
  set $atns5_in_x100 = -1
  if $atns5_p1obj != 0
    set $atns5_state = *(unsigned char*)($atns5_p1obj + 0x18)
    set $atns5_lock = *(unsigned char*)($atns5_p1obj + 0x11a)

    # A `state load` between trials resets the emulated memory but NOT
    # this script's own GDB convenience variables -- found live (jus-atns.5
    # round 2): without this reset, $atns5_poke_done stays 1 from the
    # FIRST trial in an attach and every later trial in the same attach
    # silently skips its own poke, looking identical to an unpoked
    # control. Reset the latch whenever P1 is back at idle (state 0),
    # which every trial's own leading frames pass through before its own
    # guard press.
    if $atns5_state == 0
      set $atns5_poke_done = 0
      set $atns5_poke_armed = 0
      set $atns5_poke_since = 0
    end

    # -- job B poke (see the header note above $atns5_poke_mode) --
    if $atns5_poke_mode == 1
      if $atns5_poke_done == 0 && $atns5_lock == 6
        set *(unsigned char*)($atns5_p1obj + 0x11a) = 12
        set $atns5_lock = 12
        set $atns5_poke_done = 1
      end
    end
    if $atns5_poke_mode == 2
      if $atns5_poke_armed == 0 && $atns5_lock == 6
        set $atns5_poke_armed = 1
        set $atns5_poke_since = 0
      else
        if $atns5_poke_armed == 1 && $atns5_poke_done == 0
          set $atns5_poke_since = $atns5_poke_since + 1
          if $atns5_poke_since == 1
            set *(unsigned char*)($atns5_p1obj + 0x11a) = 0
            set $atns5_lock = 0
            set $atns5_poke_done = 1
          end
        end
      end
    end

    set $atns5_input6c = *(unsigned int*)($atns5_p1obj + 0x6c)
    set $atns5_in_down = 0
    if ($atns5_input6c & 0x02) != 0
      set $atns5_in_down = 1
    end
    set $atns5_in_x80 = 0
    if ($atns5_input6c & 0x80) != 0
      set $atns5_in_x80 = 1
    end
    set $atns5_in_x100 = 0
    if ($atns5_input6c & 0x100) != 0
      set $atns5_in_x100 = 1
    end
    set $atns5_m_outer = *(unsigned int*)($atns5_p1obj + 0x1a8)
    set $atns5_m = 0
    if $atns5_m_outer != 0
      set $atns5_m = *(unsigned int*)($atns5_m_outer + 0x10)
    end
    if $atns5_m != 0
      set $atns5_flags78 = *(unsigned int*)($atns5_m + 0x78)
      set $atns5_flags40 = *(unsigned int*)($atns5_m + 0x40)
      set $atns5_guard_bit = ($atns5_flags78 >> 26) & 1
      set $atns5_blocked_latch = 0
      if ($atns5_flags40 & 0x1000) != 0
        set $atns5_blocked_latch = 1
      end
    end
  end

  set $atns5_state2 = -1
  if $atns5_p2obj != 0
    set $atns5_state2 = *(unsigned char*)($atns5_p2obj + 0x18)
  end

  set $atns5_hp1 = *(unsigned short*)0x021DF1D4
  set $atns5_hp2 = *(unsigned short*)0x021DF7F0

  # -- jus-wmqi.2 additions (see header "wmqi.2 fields") --
  set $atns5_w64 = -1
  set $atns5_w68 = -1
  set $atns5_w6c = -1
  set $atns5_w70 = -1
  if $atns5_p1obj != 0
    set $atns5_w64 = *(unsigned int*)($atns5_p1obj + 0x64)
    set $atns5_w68 = *(unsigned int*)($atns5_p1obj + 0x68)
    set $atns5_w6c = *(unsigned int*)($atns5_p1obj + 0x6c)
    set $atns5_w70 = *(unsigned int*)($atns5_p1obj + 0x70)
  end
  set $atns5_act1 = 0
  set $atns5_act2 = 0
  set $atns5_ri = 0
  while $atns5_ri < 4
    if (*(unsigned char*)(0x021DF1D4 + $atns5_ri*0x50 + 0x25) & 1) != 0
      set $atns5_act1 = $atns5_act1 | (1 << $atns5_ri)
    end
    if (*(unsigned char*)(0x021DF7F0 + $atns5_ri*0x50 + 0x25) & 1) != 0
      set $atns5_act2 = $atns5_act2 | (1 << $atns5_ri)
    end
    set $atns5_ri = $atns5_ri + 1
  end
  set $atns5_c10 = *(unsigned char*)(0x021DF1D4 + 0x29)
  set $atns5_c11 = *(unsigned char*)(0x021DF1D4 + 0x50 + 0x29)
  set $atns5_c12 = *(unsigned char*)(0x021DF1D4 + 0xa0 + 0x29)
  set $atns5_c13 = *(unsigned char*)(0x021DF1D4 + 0xf0 + 0x29)
  set $atns5_c20 = *(unsigned char*)(0x021DF7F0 + 0x29)
  set $atns5_c21 = *(unsigned char*)(0x021DF7F0 + 0x50 + 0x29)
  set $atns5_c22 = *(unsigned char*)(0x021DF7F0 + 0xa0 + 0x29)
  set $atns5_c23 = *(unsigned char*)(0x021DF7F0 + 0xf0 + 0x29)
  set $atns5_h21 = *(unsigned short*)(0x021DF7F0 + 0x50)
  set $atns5_h22 = *(unsigned short*)(0x021DF7F0 + 0xa0)
  set $atns5_h23 = *(unsigned short*)(0x021DF7F0 + 0xf0)
  set $atns5_h11 = *(unsigned short*)(0x021DF1D4 + 0x50)
  set $atns5_h12 = *(unsigned short*)(0x021DF1D4 + 0xa0)
  set $atns5_h13 = *(unsigned short*)(0x021DF1D4 + 0xf0)
  set $atns5_x1 = *(int*)(0x0220C068 + 0xc)
  set $atns5_x2 = *(int*)(0x0220C0A8 + 0xc)

  printf "{\"type\":\"frame\",\"frame\":%d,\"state\":%d,\"state2\":%d,\"lock\":%d,\"guard_bit\":%d,\"blocked_latch\":%d,\"in_down\":%d,\"in_x80\":%d,\"in_x100\":%d,\"hp1\":%d,\"hp2\":%d,\"poked\":%d,\"w64\":\"0x%x\",\"w68\":\"0x%x\",\"w6c\":\"0x%x\",\"w70\":\"0x%x\",\"act1\":%d,\"act2\":%d,\"chr1\":[%d,%d,%d,%d],\"chr2\":[%d,%d,%d,%d],\"hp1s\":[%d,%d,%d,%d],\"hp2s\":[%d,%d,%d,%d],\"x1\":%d,\"x2\":%d,\"recs\":[", $atns5_frame, $atns5_state, $atns5_state2, $atns5_lock, $atns5_guard_bit, $atns5_blocked_latch, $atns5_in_down, $atns5_in_x80, $atns5_in_x100, $atns5_hp1, $atns5_hp2, $atns5_poke_done, $atns5_w64, $atns5_w68, $atns5_w6c, $atns5_w70, $atns5_act1, $atns5_act2, $atns5_c10, $atns5_c11, $atns5_c12, $atns5_c13, $atns5_c20, $atns5_c21, $atns5_c22, $atns5_c23, $atns5_hp1, $atns5_h11, $atns5_h12, $atns5_h13, $atns5_hp2, $atns5_h21, $atns5_h22, $atns5_h23, $atns5_x1, $atns5_x2

  set $atns5_first = 1
  set $atns5_idcount = 0
  if $atns5_manager != 0 && $atns5_p1obj != 0
    set $atns5_base = $atns5_manager + 0x454
    set $atns5_r = 0
    while $atns5_r < 128 && $atns5_idcount < 64
      set $atns5_rec = $atns5_base + $atns5_r*0x188
      set $atns5_wrap = *(unsigned int*)($atns5_rec + 0x60)
      if $atns5_wrap != 0
        set $atns5_e = *(unsigned int*)($atns5_wrap + 0x08)
        set $atns5_ewalk = 0
        while $atns5_e != 0 && $atns5_ewalk < 8 && $atns5_idcount < 64
          set $atns5_cnt = *(unsigned short*)($atns5_e + 0xc)
          if $atns5_cnt > 0
            set $atns5_id = *(unsigned short*)($atns5_e + 0xe)
            if $atns5_first == 0
              printf ","
            end
            printf "[%d,%d]", $atns5_r, $atns5_id
            set $atns5_first = 0
            set $atns5_idcount = $atns5_idcount + 1
          end
          set $atns5_e = *(unsigned int*)($atns5_e + 0x00)
          set $atns5_ewalk = $atns5_ewalk + 1
        end
      end
      set $atns5_r = $atns5_r + 1
    end
  end
  printf "]}\n"
  continue
end
