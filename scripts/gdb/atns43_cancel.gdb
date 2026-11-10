# atns43_cancel.gdb -- jus-atns.4.3. Per-frame cancel-window probe.
#
# Small, fast sibling of atns41_hitbox_dump.gdb: no rectangles, no
# per-element geometry, just what cancel_run.py's acceptance detector
# needs every frame at the anchor 0x02082E10 (physics.md §7 -- fires once
# per frame, strictly after this frame's collision resolution):
#   - P1's obj+0x18 state code (physics.md §4.5: 0 idle, 1 walk, 2 dash,
#     4/5 jump start, 6 airborne, 9 attack, 12 SELECT, 13 landing)
#   - P2's obj+0x18 state code (jus-roster-moveset-campaign-69it.1.4 live-
#     bridge audit -- the fighter table at 0x021DEB3C holds exactly two
#     live pointers, P1's then P2's, at +0 and +4, physics.md §5. -1 while
#     the P2 pointer has not yet resolved to a nonzero value)
#   - P1's physics x/y (fixed element 0x0220C068, same address atns41 uses,
#     physics.md §6)
#   - the ids of any live (cnt>0) geometry elements on collision records
#     11, 13, 14 -- Kakashi's own body/attack record and the two spawned
#     records his moves use (kakashi.md §2: down B, up B,
#     side Y spawn travelling records; capped at 8 ids total across the
#     three records, matching the brief)
#   - each roster slot's own active-koma flag, bit 0 of
#     0x021DF7F0 + 0x50*i + 0x25 for slot i (docs/confirmed-facts/
#     characters/kakashi.md's "0x021DF7F0+0x50i+0x25 bit 0" note, §"victim"
#     row and its "+0x25 active .../+0x29 chr_b ... relative to
#     0x021DF7F0" clarification -- jus-atns.4.9, Portability blocker 6:
#     down B's forced-switch claim needs a second, independent read of
#     which koma is active, not just P2's own state code) -- slot 0 is the
#     first roster entry, slot 1 the second; `active0`/`active1` are each
#     0 or 1, never the state code
#
# One JSON line per frame, type "frame" (probe version v4 -- "f6"/"b11b"/
# "hp1"/"hp2" added this ticket, jus-atns.4.8, for the Kakashi SELECT
# residual measurement: the same four cheap reads
# scripts/gdb/atns45_select.gdb's first launch used (Kakashi obj+0xF6 --
# the "used SELECT at least once" latch byte; obj+0x11B -- the one-shot
# sentinel candidate; and both fighters' u16 HP words), added to THIS probe
# instead of loading atns45_select.gdb live so the framework's live path
# stays on one probe (design note in the moveset-mapping-framework doc
# §3.4: "the live path loads only atns43_cancel.gdb"). All four reads are
# fixed-offset/fixed-address, no extra manager walk, keeping the per-frame
# cost the same as v3 plus four scalar reads:
#   f6   -- P1 (Kakashi) obj+0xF6, byte (kakashi-select-2026-09-13/
#           RESULTS.md "1. The status write": 0x00->0x01 at SELECT
#           activation, latched)
#   b11b -- P1 obj+0x11B, byte (same doc: 0x00->0xFF candidate expiry
#           sentinel, single flip, unconfirmed as the live decrementing
#           timer itself)
#   hp1  -- P1's own HP, u16 at the fixed deck-record-0 address
#           0x021DF1D4 (docs/confirmed-facts kakashi.md Conditions block)
#   hp2  -- P2's HP, u16 at the fixed deck-record-0 address 0x021DF7F0
# (v3 added "active0"/"active1", jus-atns.4.9; v2 added "state2"; v1 frame
# lines had none of the above):
#   {"type":"frame","frame":N,"state":S,"state2":S2,"physx":X,"physy":Y,"active0":A0,"active1":A1,"f6":F6,"b11b":B11B,"hp1":H1,"hp2":H2,"ids":[...]}
# plus one "manager" line the first time the ColPrm manager resolves.
#
# f6/b11b/hp1/hp2 are read off P1's own object unconditionally (Kakashi is
# always P1 in every fixture this probe is used against, per every
# kit/kakashi.toml [[fixture.attacker]] block) -- they are NOT gated on
# which character is loaded, same convention as the P1 state/physx/physy
# reads above. A non-Kakashi P1 would simply read whatever bytes live at
# those offsets on its own object; nothing here validates the character.
#
# Manager resolution is the same self-verifying sweep atns41 uses (seeded
# from 0x0220DDE0, accepted when candidate+0 == candidate+0x454) -- a
# one-shot breakpoint on the constructor does not work from a mid-battle
# savestate load (atns41's own header explains why).
#
# Unlike atns41, this script does NOT end with a top-level `continue` and
# does NOT set its own logging file. cancel_run.py drives multiple plans
# from one attach (recipe: "one launch, one attach ... per plan: state
# load then run"), so it owns `set logging file` / `set logging enabled
# on` and issues the first `continue` itself, mirroring
# scripts/gdb/run_experiments.py's GdbSession.attach()/resume() split
# (attach loads the script and returns a prompt; resume sends `continue`
# separately). Loading this script therefore leaves GDB at an ordinary
# prompt with the breakpoint armed but not yet running.

set pagination off
set confirm off
set logging overwrite off
handle SIGILL stop nopass noprint
target remote localhost:3333

set $atns43_frame = 0
set $atns43_manager = 0
set $atns43_manager_resolved = 0

break *0x02082E10
commands
  silent
  set $atns43_frame = $atns43_frame + 1

  if $atns43_manager_resolved == 0
    set $atns43_seed = 0x0220DDE0 - 0x1000
    set $atns43_k = 0
    while $atns43_k < 0x2000 && $atns43_manager_resolved == 0
      set $atns43_cand = $atns43_seed + $atns43_k
      set $atns43_self = *(unsigned int*)$atns43_cand
      if $atns43_self == $atns43_cand + 0x454
        set $atns43_manager = $atns43_cand
        set $atns43_manager_resolved = 1
        printf "{\"type\":\"manager\",\"addr\":\"0x%x\"}\n", $atns43_manager
      end
      set $atns43_k = $atns43_k + 4
    end
  end

  # -- P1/P2 state + physics x/y (fixed addresses, per atns41/physics.md) --
  set $atns43_ft = 0x021DEB3C
  set $atns43_p1obj = *(unsigned int*)$atns43_ft
  set $atns43_p2obj = *(unsigned int*)($atns43_ft + 4)
  set $atns43_state = -1
  if $atns43_p1obj != 0
    set $atns43_state = *(unsigned char*)($atns43_p1obj + 0x18)
  end
  set $atns43_state2 = -1
  if $atns43_p2obj != 0
    set $atns43_state2 = *(unsigned char*)($atns43_p2obj + 0x18)
  end
  set $atns43_physx = *(int*)(0x0220C068 + 0xc)
  set $atns43_physy = *(int*)(0x0220C068 + 0x10)

  # -- v4 (jus-atns.4.8): SELECT status candidates + both fighters' HP --
  set $atns43_f6 = -1
  set $atns43_b11b = -1
  if $atns43_p1obj != 0
    set $atns43_f6 = *(unsigned char*)($atns43_p1obj + 0xf6)
    set $atns43_b11b = *(unsigned char*)($atns43_p1obj + 0x11b)
  end
  set $atns43_hp1 = *(unsigned short*)0x021DF1D4
  set $atns43_hp2 = *(unsigned short*)0x021DF7F0

  # -- each roster slot's own active-koma flag (confirmed-facts kakashi.md
  #    "0x021DF7F0+0x50i+0x25 bit 0"; jus-atns.4.9 blocker 6) --
  set $atns43_active_byte0 = *(unsigned char*)(0x021DF7F0 + 0x50*0 + 0x25)
  set $atns43_active0 = $atns43_active_byte0 & 1
  set $atns43_active_byte1 = *(unsigned char*)(0x021DF7F0 + 0x50*1 + 0x25)
  set $atns43_active1 = $atns43_active_byte1 & 1

  # -- live element ids (cnt>0) on records 11, 13, 14, cap 8 total --
  printf "{\"type\":\"frame\",\"frame\":%d,\"state\":%d,\"state2\":%d,\"physx\":%d,\"physy\":%d,\"active0\":%d,\"active1\":%d,\"f6\":%d,\"b11b\":%d,\"hp1\":%d,\"hp2\":%d,\"ids\":[", $atns43_frame, $atns43_state, $atns43_state2, $atns43_physx, $atns43_physy, $atns43_active0, $atns43_active1, $atns43_f6, $atns43_b11b, $atns43_hp1, $atns43_hp2
  set $atns43_idcount = 0
  set $atns43_first = 1
  if $atns43_manager != 0
    set $atns43_base = $atns43_manager + 0x454
    set $atns43_recidx = 0
    while $atns43_recidx < 3
      if $atns43_recidx == 0
        set $atns43_r = 11
      end
      if $atns43_recidx == 1
        set $atns43_r = 13
      end
      if $atns43_recidx == 2
        set $atns43_r = 14
      end
      set $atns43_rec = $atns43_base + $atns43_r*0x188
      set $atns43_wrap = *(unsigned int*)($atns43_rec + 0x60)
      if $atns43_wrap != 0
        set $atns43_e = *(unsigned int*)($atns43_wrap + 0x08)
        set $atns43_ewalk = 0
        while $atns43_e != 0 && $atns43_ewalk < 8 && $atns43_idcount < 8
          set $atns43_cnt = *(unsigned short*)($atns43_e + 0xc)
          if $atns43_cnt > 0
            set $atns43_id = *(unsigned short*)($atns43_e + 0xe)
            if $atns43_first == 0
              printf ","
            end
            printf "%d", $atns43_id
            set $atns43_first = 0
            set $atns43_idcount = $atns43_idcount + 1
          end
          set $atns43_e = *(unsigned int*)($atns43_e + 0x00)
          set $atns43_ewalk = $atns43_ewalk + 1
        end
      end
      set $atns43_recidx = $atns43_recidx + 1
    end
  end
  printf "]}\n"
  continue
end
