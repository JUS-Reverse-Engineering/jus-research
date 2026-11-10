# atns45_select.gdb -- jus-atns.4.5 (Kakashi SELECT substitution status) and
# the live half of jus-atns.4.6 (tier / dash / passive bits / sound calls).
#
# Reuses atns41_hitbox_dump.gdb's conventions: frame anchor at the
# once-per-frame integrator pass entry arm9 0x02082E10 (physics.md §7), no
# stepi, no watchpoints (unsupported by the melonDS stub), ends with a
# top-level `continue`. This session does NOT walk ColPrm geometry -- it is
# not needed for the status-byte/timer question -- so there is no manager
# resolution here, keeping the per-frame cost low (atns43_cancel.gdb's
# 2026-09-13 finding: a probe that prints heavily on every frame across many
# plan executions under one attach risks wedging the bridge; this probe
# stays as small as possible per frame for that reason).
#
# Fixed addresses, all from characters/kakashi.md's Conditions block and
# HP-And-Damage-Runtime-Findings.md's address table (this state, record 0
# = deck leader, both fighters slot 0 of their own decks):
#   Kakashi (P1) obj      0x02228E80
#   Kakashi M              [[obj+0x1a8]+0x10] (resolved live, not hardcoded)
#   Kakashi physics elem   0x0220C068
#   Jotaro (CPU) obj       0x0224EF00 (read from fighter table 0x021DEB3C slot 1
#                          each frame -- per-state per kakashi.md Hazards)
#   Jotaro physics elem    0x0220C0A8 (P1 elem + 0x40)
#   Kakashi HP (u16)       0x021DF1D4 (deck HP record 0, player)
#   Jotaro HP (u16)        0x021DF7F0 (deck HP record 0, opponent)
#
# Status candidate region logged every frame (adjust after the diff, per the
# ticket brief, if the real write lands elsewhere):
#   Kakashi obj+0xF0 .. +0x100  (17 words)
#   Kakashi M+0x160 .. +0x180   (9 words)
#
# One-shot reads at the first frame the anchor fires (jus-atns.4.6 live half,
# items 1-2 of "For the live half" in kakashi-tier-dash-passives-static.md):
#   obj+0xBA (expect -1752, tier 2 jump impulse)
#   obj+0x128 (expect bit 0x04 set -- Wall Jump; 0x02/0x08 clear)
#
# Breakpoints for jus-atns.4.6 live half items 3-4:
#   0x02156710 (dash setup): log r1 and the 16 bytes at r1
#   0x0207342C (sound wrapper): log (category=r0, id=r1) and the local
#     frame counter
#
# Second launch (2026-09-13, jus-atns.4.5 item 5, log entity): extended with
# atns41_hitbox_dump.gdb's ColPrm record/element walk, but NOT run every
# frame -- atns43_cancel.gdb's finding above (heavy per-frame printing across
# many plan executions risks wedging the bridge) is still binding, so the
# walk is gated to a short capture window: it only fires for the 8 frames
# starting the frame Kakashi's `obj+0x18` transitions INTO 8 (the nullified-
# hit reaction code found in the first launch), which is exactly the window
# the ticket's item 5 needs (find a record/id appearing at Kakashi's
# pre-hit position on the nullified frame). Manager resolution copied
# verbatim from atns41_hitbox_dump.gdb (self-verifying sweep from the
# collision.md p204 seed, +0x454 self-pointer check) so this script has no
# hardcoded manager address to go stale.

set pagination off
set confirm off
set logging overwrite off
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $a45_frame = 0
set $a45_oneshot_done = 0
set $a45_manager = 0
set $a45_manager_resolved = 0
set $a45_kstate_prev = -1
set $a45_capture_countdown = 0

break *0x02082E10
commands
  silent
  set $a45_frame = $a45_frame + 1

  set $a45_kobj = 0x02228E80
  set $a45_jft = *(unsigned int*)(0x021DEB3C + 1*4)

  if $a45_oneshot_done == 0
    set $a45_oneshot_done = 1
    set $a45_ba = *(short*)($a45_kobj + 0xba)
    set $a45_p128 = *(unsigned int*)($a45_kobj + 0x128)
    printf "{\"type\":\"oneshot\",\"frame\":%d,\"obj_ba\":%d,\"obj_128\":\"0x%x\"}\n", $a45_frame, $a45_ba, $a45_p128
  end

  set $a45_kstate = *(unsigned char*)($a45_kobj + 0x18)
  set $a45_kmouter = *(unsigned int*)($a45_kobj + 0x1a8)
  set $a45_km = 0
  if $a45_kmouter != 0
    set $a45_km = *(unsigned int*)($a45_kmouter + 0x10)
  end

  set $a45_jstate = -1
  if $a45_jft != 0
    set $a45_jstate = *(unsigned char*)($a45_jft + 0x18)
  end

  set $a45_kphysx = *(int*)(0x0220C068 + 0xc)
  set $a45_kphysy = *(int*)(0x0220C068 + 0x10)
  set $a45_jphysx = *(int*)(0x0220C0A8 + 0xc)
  set $a45_jphysy = *(int*)(0x0220C0A8 + 0x10)

  set $a45_khp = *(unsigned short*)0x021DF1D4
  set $a45_jhp = *(unsigned short*)0x021DF7F0

  printf "{\"type\":\"frame\",\"frame\":%d,\"kstate\":%d,\"jstate\":%d,\"kphysx\":%d,\"kphysy\":%d,\"jphysx\":%d,\"jphysy\":%d,\"khp\":%d,\"jhp\":%d,\"kobj\":\"0x%x\",\"jobj\":\"0x%x\",\"km\":\"0x%x\"", $a45_frame, $a45_kstate, $a45_jstate, $a45_kphysx, $a45_kphysy, $a45_jphysx, $a45_jphysy, $a45_khp, $a45_jhp, $a45_kobj, $a45_jft, $a45_km

  printf ",\"status_obj\":["
  set $a45_i = 0
  while $a45_i < 17
    set $a45_w = *(unsigned int*)($a45_kobj + 0xf0 + $a45_i*4)
    if $a45_i > 0
      printf ","
    end
    printf "\"0x%x\"", $a45_w
    set $a45_i = $a45_i + 1
  end
  printf "]"

  printf ",\"status_m\":["
  set $a45_i = 0
  if $a45_km != 0
    while $a45_i < 9
      set $a45_w = *(unsigned int*)($a45_km + 0x160 + $a45_i*4)
      if $a45_i > 0
        printf ","
      end
      printf "\"0x%x\"", $a45_w
      set $a45_i = $a45_i + 1
    end
  end
  printf "]}\n"

  # -- resolve the ColPrm manager once (atns41's self-verifying sweep) --
  if $a45_manager_resolved == 0
    set $a45_seed = 0x0220DDE0 - 0x1000
    set $a45_k = 0
    while $a45_k < 0x2000 && $a45_manager_resolved == 0
      set $a45_cand = $a45_seed + $a45_k
      set $a45_self = *(unsigned int*)$a45_cand
      if $a45_self == $a45_cand + 0x454
        set $a45_manager = $a45_cand
        set $a45_manager_resolved = 1
        printf "{\"type\":\"manager\",\"addr\":\"0x%x\"}\n", $a45_manager
      end
      set $a45_k = $a45_k + 4
    end
  end

  # -- log-entity capture window: arm on the frame kstate transitions to 8
  # (the nullified-hit reaction code, first-launch finding) --
  if $a45_kstate == 8 && $a45_kstate_prev != 8
    set $a45_capture_countdown = 8
    printf "{\"type\":\"capture_armed\",\"frame\":%d,\"kphysx\":%d,\"kphysy\":%d}\n", $a45_frame, $a45_kphysx, $a45_kphysy
  end

  if $a45_capture_countdown > 0 && $a45_manager != 0
    set $a45_base = $a45_manager + 0x454
    set $a45_r = 0
    while $a45_r < 128
      set $a45_rec = $a45_base + $a45_r*0x188
      set $a45_wrap = *(unsigned int*)($a45_rec + 0x60)
      if $a45_wrap != 0
        set $a45_r34 = *(unsigned int*)($a45_rec + 0x34)
        set $a45_r38 = *(unsigned int*)($a45_rec + 0x38)
        set $a45_r40 = *(unsigned int*)($a45_rec + 0x40)
        printf "{\"type\":\"record\",\"frame\":%d,\"record\":%d,\"wrap\":\"0x%x\",\"rec34\":\"0x%x\",\"rec38\":\"0x%x\",\"rec40\":\"0x%x\"}\n", $a45_frame, $a45_r, $a45_wrap, $a45_r34, $a45_r38, $a45_r40

        set $a45_e = *(unsigned int*)($a45_wrap + 0x08)
        set $a45_ecount = 0
        while $a45_e != 0 && $a45_ecount < 8
          set $a45_id = *(unsigned short*)($a45_e + 0xe)
          set $a45_cnt = *(unsigned short*)($a45_e + 0xc)
          set $a45_flags = *(unsigned char*)($a45_e + 0x18)
          set $a45_extx = *(short*)($a45_e + 0x2c)
          set $a45_exty = *(short*)($a45_e + 0x2e)
          set $a45_hextx = *(short*)($a45_e + 0x30)
          set $a45_hexty = *(short*)($a45_e + 0x32)
          set $a45_posx = 0
          set $a45_posy = 0
          set $a45_posblk1 = *(unsigned int*)($a45_e + 8)
          if $a45_posblk1 != 0
            set $a45_posblk2 = *(unsigned int*)($a45_posblk1 + 4)
            if $a45_posblk2 != 0
              set $a45_posblk3 = *(unsigned int*)($a45_posblk2 + 0x50)
              if $a45_posblk3 != 0
                set $a45_posx = *(int*)($a45_posblk3 + 0xc)
                set $a45_posy = *(int*)($a45_posblk3 + 0x10)
              end
            end
          end
          printf "{\"type\":\"elem\",\"frame\":%d,\"record\":%d,\"elem\":\"0x%x\",\"id\":%d,\"cnt\":%d,\"flags\":\"0x%x\",\"pos\":[%d,%d],\"extent_off\":[%d,%d],\"half_extent\":[%d,%d]}\n", $a45_frame, $a45_r, $a45_e, $a45_id, $a45_cnt, $a45_flags, $a45_posx, $a45_posy, $a45_extx, $a45_exty, $a45_hextx, $a45_hexty
          set $a45_e = *(unsigned int*)($a45_e + 0x00)
          set $a45_ecount = $a45_ecount + 1
        end
      end
      set $a45_r = $a45_r + 1
    end
    set $a45_capture_countdown = $a45_capture_countdown - 1
  end

  set $a45_kstate_prev = $a45_kstate

  continue
end

break *0x02156710
commands
  silent
  set $a45_r1 = $r1
  printf "{\"type\":\"dashsetup\",\"frame\":%d,\"r1\":\"0x%x\",\"bytes\":[", $a45_frame, $a45_r1
  set $a45_i = 0
  while $a45_i < 16
    set $a45_b = *(unsigned char*)($a45_r1 + $a45_i)
    if $a45_i > 0
      printf ","
    end
    printf "%d", $a45_b
    set $a45_i = $a45_i + 1
  end
  printf "]}\n"
  continue
end

break *0x0207342C
commands
  silent
  printf "{\"type\":\"sound\",\"frame\":%d,\"category\":\"0x%x\",\"id\":\"0x%x\"}\n", $a45_frame, $r0, $r1
  continue
end

continue
