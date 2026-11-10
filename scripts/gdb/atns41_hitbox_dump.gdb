# atns41_hitbox_dump.gdb -- jus-atns.4.1. Per-frame hitbox/hurtbox geometry dump
# for the offline PNG frame strips (scripts/analysis/hitbox_strip.py).
#
# Frame anchor: the integrator pass entry, arm9 0x02082E10. physics.md §7
# ("Per-frame task order") places it as the LAST scheduler task in the
# per-frame rotation (key 0xA1000, after the collision driver's 0x9E000),
# and documents it as "a pass, not a per-element entry: its own entry fires
# once per frame." The ticket brief explicitly rules out the collision
# driver 0x0207F480 itself as a frame anchor (2-16 fires/frame); this is the
# once-per-frame point physics.md §7 names instead, and it runs strictly
# after this frame's collision resolution, so the geometry read here
# reflects the frame that was just resolved.
# Exception: physx/physy are read before this frame's motion, so they equal
# the Lua watch position of the previous frame (E3 "The one-frame offset").
#
# ColPrm manager: resolving it at the constructor Battle_ColPrmManCreate
# (arm9 0x0207C4C0) does NOT work for this tracker item's workflow -- every capture
# here starts from a mid-battle savestate load, and the constructor only
# runs once at battle creation, before any savestate was taken, so a
# breakpoint there never fires when resuming from a save. Instead this
# script derives the manager address from its own self-pointer at the
# first frame the anchor breakpoint fires: `manager+0x00` holds a pointer
# equal to `manager+0x454` (the base of the 128 inline ColPrm records,
# collision.md §2) -- confirmed this session by peeking `0x0220DDE0` (the
# address collision.md's p204 finding names for a prior session) via
# `jusemu.py peek`: it read `0x220e234`, exactly `0x0220DDE0+0x454`. Rather
# than hardcode that address (deterministic across boots of the same save
# family, but still session-local per collision.md's own caution), the
# script instead sweeps a small fixed window of candidate manager
# addresses seeded from 0x0220DDE0 and accepts the one whose self-pointer
# closes the `+0x454` loop -- self-verifying every run, no hardcoded
# address to go stale.
#
# Geometry layout (element, not wrapper), per
# docs/research/findings/hitbox-node-geometry-static.md §0 (the live
# correction this tracker item's own debugger pass wrote after the orchestrator
# found the previous version of this probe read the wrong object):
#
# `record+0x60` is a 0x40-byte ColObj WRAPPER, not the rectangle holder:
#   - wrapper+0x08 / +0x0C  head / tail of a linked list of geometry
#                           ELEMENTS (the actual rectangle holders)
#   - wrapper+0x10          pair list
#   - wrapper+0x18          owner
#
# Each geometry ELEMENT is 0x64 bytes, linked at its own +0x00, up to 4
# walked per wrapper (no capture has shown more than 2):
#   - elem+0x00           next-element pointer (the link this probe walks)
#   - elem+0x08           owner (= wrapper+0x18)
#   - elem+0x0C  u16      live sub-element count -- the active gate (0 or 1
#                         seen)
#   - elem+0x0E  u16      id
#   - elem+0x18  u8       flags (bit 0x80 tested by the overlap test)
#   - elem+0x20           back-pointer to the wrapper (== record+0x60);
#                         logged as `e20` for the regression check in
#                         scripts/analysis/hitbox_check.py
#   - elem+0x2C/+0x2E  s16  per-axis centre offset (extent_off)
#   - elem+0x30/+0x32  s16  per-axis half-extent   (half_extent)
#   - elem+0x3C + j*8     sub-element j: +0/+2 s16 centre-offset (x,y),
#                         +4/+6 s16 half-extent (x,y) -- iterated exactly
#                         `cnt` times (capped at 8; no capture this tracker item
#                         has seen more than a handful of sub-elements)
#   - the world position feeding the element's AABB centre:
#                         *(*(elem+8)+4)+0x50, then +0xc/+0x10/+0x14 =
#                         x/y/z (full 32-bit each, raw physics units x16)
#
# Also logged, raw, no gameplay naming (per the ticket brief's explicit
# rule for the slot field, extended here to every bit-level field this
# probe was not asked to interpret): record+0x34, record+0x38, record+0x40.
#
# Fighter fields, per the ticket brief and physics.md/kakashi.md's
# Conditions blocks: fighter table arm9 0x021DEB3C (fixed address, not
# session-local -- kakashi.md Hazards: "Resolve slot 1 ... for every new
# state", always relative to this same table address), M = [[obj+0x1a8]+0x10]
# (kakashi.md Conditions), obj+0x18 state code (physics.md §4.5),
# M+0x78 flags word ("rebuilt per frame" per the ticket brief).
#
# Output: one JSON object per line (JSONL), six `type`s: "frame" (one per
# anchor hit), "fighter" (0-2 per frame), "record" (one per live record,
# i.e. `rec+0x60 != 0`, logging that wrapper pointer independently of the
# `elem` walk below), "elem" (0-N per frame, one per geometry element
# walked off a live wrapper's +0x08 list, up to 8 per wrapper -- raised
# from 4 by jus-atns.4.2 after the Refuter's PASS notes found a 5th
# simultaneous element on Kakashi's own body wrapper (record 11) during
# neutral_y/dash_y that the old 4-element cap silently truncated), "manager"
# (once, when the manager address is resolved), and "overflow" (emitted
# whenever the element walk hits its 8-element cap while more elements
# remain linked, or a sub-element walk hits its 8-sub cap while `cnt`
# claims more -- see the Refuter's note, 2026-09-12 19:10, that the caps
# can silently truncate real data). jus-atns.4.2 also moved the sub-overflow
# marker: it used to print mid-way through the still-open `elem` JSON line
# (corrupting it), so it is now buffered in a flag and emitted as its own
# line only after the `elem` line's closing `]}\n` -- see the sub-walk
# below. A Python postprocessor (scripts/analysis/hitbox_strip.py)
# groups by frame number. This script does not open the output file itself
# -- `set logging file` is set by the run harness per attack capture (see
# the capture folder's own README/RESULTS.md) so one script serves every
# attack without editing.
#
# Fighter physics x/y (Refuter, 2026-09-12 19:10, check B): added to each
# "fighter" line as `physx`/`physy`, read directly from the fixed-address
# fighter *physics element* (not the `obj` from the fighter table above),
# per the ticket brief and physics.md §5 (P1 x at 0x0220C074 = element+0x0C) and §6: P1's physics element is
# `0x0220C068`; the opponent's is `+0x40` (`0x0220C0A8`) on this state
# (`pc-kakashi-npc-jotaro-dark-tournament`, fixed fighter slots 0/1, not the
# J-Arena relocated-array case physics.md warns about). Position is the
# integrator's own pair at element+0x0C (x) / +0x10 (y), s32, 8.8 fixed
# point px (physics.md §6.1 step 5, §6 "Units"). This is the same physics
# x the ColPrm element's own position chain resolves to divided by 16
# (`hitbox-node-geometry-static.md` §0; Refuter's own verification: record
# 11 body x 2585760 -> 2431200 raw = 631.29 -> 593.55 px, `pos//16`
# reproduces this to the unit) -- logging it independently here (fixed
# element address, not the ColPrm chain) is what makes
# `hitbox_check.py`'s check B a real cross-check rather than comparing a
# value against itself.
#
# No stepi (unreliable per scripts/gdb/README.md); no watchpoints (silently
# unsupported by the melonDS stub). Ends with a top-level `continue` after
# the last breakpoint is armed, per the README's "silently freezes" note --
# without it the target stays halted at attach and no frame ever advances.
#
# The pc-*-dark-tournament states load UNPAUSED (verified 2026-09-12,
# jus-atns.4.1 debugger). Do NOT press START before attaching: a lone START
# opens the pause menu, which halts the battle tasks, so the anchor at
# 0x02082E10 never fires while the emulator still renders at 60 fps and the
# CPU idles at 0x02055680. Screenshot after `state load`; press START only if
# the pause-menu panel is visible. If START was pressed by mistake, a second
# START through a plan while GDB stays attached resumes the battle.

set pagination off
set confirm off
set logging overwrite off
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $atns41_frame = 0
set $atns41_manager = 0
set $atns41_manager_resolved = 0

# Layout parameters (E3). A driver sets them with -ex before -x; unset, they keep the Dark Tournament
# values this script always used. Deck-maker test-play states keep the fighter table, the element array and the
# ColPrm manager 0x20 lower (scripts/emu/fighter_layout.py LAYOUTS), and the fighters' physics elements there are
# not at the array's first two slots: a driver reads them live as [M+0x5C] and passes both.
#   $atns41_ft_addr    fighter table (DT 0x021DEB3C, test play 0x021DEB1C)
#   $atns41_physel0/1  P1 / P2 physics element (DT 0x0220C068 / 0x0220C0A8)
#   $atns41_mgr_seed   centre of the self-verifying manager sweep (DT 0x0220DDE0, test play 0x0220DDC0)
if $_isvoid($atns41_ft_addr)
  set $atns41_ft_addr = 0x021DEB3C
end
if $_isvoid($atns41_physel0)
  set $atns41_physel0 = 0x0220C068
end
if $_isvoid($atns41_physel1)
  set $atns41_physel1 = 0x0220C0A8
end
if $_isvoid($atns41_mgr_seed)
  set $atns41_mgr_seed = 0x0220DDE0
end
printf "{\"type\":\"params\",\"ft\":\"0x%x\",\"physel0\":\"0x%x\",\"physel1\":\"0x%x\",\"mgr_seed\":\"0x%x\"}\n", $atns41_ft_addr, $atns41_physel0, $atns41_physel1, $atns41_mgr_seed

# ---- Frame anchor: once per frame, after this frame's collision pass ----
break *0x02082E10
commands
  silent
  set $atns41_frame = $atns41_frame + 1

  # Resolve the manager once: sweep candidate addresses seeded from the
  # address collision.md's p204 finding names (0x0220DDE0), self-verifying
  # via the +0x454 self-pointer described above. Re-run every state load
  # (cheap; only really does work the first time per launch).
  if $atns41_manager_resolved == 0
    # the seed itself first, then the +-0x1000 sweep
    if *(unsigned int*)$atns41_mgr_seed == $atns41_mgr_seed + 0x454
      set $atns41_manager = $atns41_mgr_seed
      set $atns41_manager_resolved = 1
      printf "{\"type\":\"manager\",\"addr\":\"0x%x\"}\n", $atns41_manager
    end
    set $atns41_seed = $atns41_mgr_seed - 0x1000
    set $atns41_k = 0
    while $atns41_k < 0x2000 && $atns41_manager_resolved == 0
      set $atns41_cand = $atns41_seed + $atns41_k
      set $atns41_self = *(unsigned int*)$atns41_cand
      if $atns41_self == $atns41_cand + 0x454
        set $atns41_manager = $atns41_cand
        set $atns41_manager_resolved = 1
        printf "{\"type\":\"manager\",\"addr\":\"0x%x\"}\n", $atns41_manager
      end
      set $atns41_k = $atns41_k + 4
    end
  end

  # gfc: the battle frame counter word (0x020A0F10, the Lua `gfc` watch and kit_hit_probe's stamp), so this
  # basis and the Lua rows join on one clock
  printf "{\"type\":\"frame\",\"frame\":%d,\"gfc\":%d}\n", $atns41_frame, *(unsigned int*)0x020A0F10

  # -- fighters, via the fixed-address fighter table --
  set $atns41_ft = $atns41_ft_addr
  set $atns41_i = 0
  while $atns41_i < 2
    set $atns41_obj = *(unsigned int*)($atns41_ft + $atns41_i*4)
    if $atns41_obj != 0
      set $atns41_state = *(unsigned char*)($atns41_obj + 0x18)
      set $atns41_m_outer = *(unsigned int*)($atns41_obj + 0x1a8)
      set $atns41_m = 0
      if $atns41_m_outer != 0
        set $atns41_m = *(unsigned int*)($atns41_m_outer + 0x10)
      end
      set $atns41_flags78 = 0
      if $atns41_m != 0
        set $atns41_flags78 = *(unsigned int*)($atns41_m + 0x78)
      end
      # Physics x/y: the physics-element addresses the driver passed ($atns41_physel0/1; the DT defaults are
      # P1 0x0220C068, opponent +0x40) -- NOT derived from $atns41_obj/the fighter table.
      set $atns41_physel = $atns41_physel0
      if $atns41_i == 1
        set $atns41_physel = $atns41_physel1
      end
      set $atns41_physx = *(int*)($atns41_physel + 0xc)
      set $atns41_physy = *(int*)($atns41_physel + 0x10)
      printf "{\"type\":\"fighter\",\"frame\":%d,\"slot\":%d,\"obj\":\"0x%x\",\"state\":%d,\"M\":\"0x%x\",\"flags78\":\"0x%x\",\"physx\":%d,\"physy\":%d}\n", $atns41_frame, $atns41_i, $atns41_obj, $atns41_state, $atns41_m, $atns41_flags78, $atns41_physx, $atns41_physy
    end
    set $atns41_i = $atns41_i + 1
  end

  # -- live ColPrm records: walk each wrapper's geometry-element list --
  if $atns41_manager != 0
    set $atns41_base = $atns41_manager + 0x454
    set $atns41_r = 0
    while $atns41_r < 128
      set $atns41_rec = $atns41_base + $atns41_r*0x188
      set $atns41_wrap = *(unsigned int*)($atns41_rec + 0x60)
      if $atns41_wrap != 0
        printf "{\"type\":\"record\",\"frame\":%d,\"record\":%d,\"wrap\":\"0x%x\"}\n", $atns41_frame, $atns41_r, $atns41_wrap
        set $atns41_r34 = *(unsigned int*)($atns41_rec + 0x34)
        set $atns41_r38 = *(unsigned int*)($atns41_rec + 0x38)
        set $atns41_r40 = *(unsigned int*)($atns41_rec + 0x40)

        set $atns41_e = *(unsigned int*)($atns41_wrap + 0x08)
        set $atns41_ecount = 0
        while $atns41_e != 0 && $atns41_ecount < 8
          set $atns41_id = *(unsigned short*)($atns41_e + 0xe)
          set $atns41_cnt = *(unsigned short*)($atns41_e + 0xc)
          set $atns41_flags = *(unsigned char*)($atns41_e + 0x18)
          set $atns41_e20 = *(unsigned int*)($atns41_e + 0x20)
          set $atns41_extx = *(short*)($atns41_e + 0x2c)
          set $atns41_exty = *(short*)($atns41_e + 0x2e)
          set $atns41_hextx = *(short*)($atns41_e + 0x30)
          set $atns41_hexty = *(short*)($atns41_e + 0x32)

          set $atns41_posx = 0
          set $atns41_posy = 0
          set $atns41_posz = 0
          set $atns41_posblk1 = *(unsigned int*)($atns41_e + 8)
          if $atns41_posblk1 != 0
            set $atns41_posblk2 = *(unsigned int*)($atns41_posblk1 + 4)
            if $atns41_posblk2 != 0
              set $atns41_posblk3 = *(unsigned int*)($atns41_posblk2 + 0x50)
              if $atns41_posblk3 != 0
                set $atns41_posx = *(int*)($atns41_posblk3 + 0xc)
                set $atns41_posy = *(int*)($atns41_posblk3 + 0x10)
                set $atns41_posz = *(int*)($atns41_posblk3 + 0x14)
              end
            end
          end

          printf "{\"type\":\"elem\",\"frame\":%d,\"record\":%d,\"elem\":\"0x%x\",\"id\":%d,\"cnt\":%d,\"flags\":\"0x%x\",\"e20\":\"0x%x\",\"pos\":[%d,%d,%d],\"extent_off\":[%d,%d],\"half_extent\":[%d,%d],\"rec34\":\"0x%x\",\"rec38\":\"0x%x\",\"rec40\":\"0x%x\",\"sub\":[", $atns41_frame, $atns41_r, $atns41_e, $atns41_id, $atns41_cnt, $atns41_flags, $atns41_e20, $atns41_posx, $atns41_posy, $atns41_posz, $atns41_extx, $atns41_exty, $atns41_hextx, $atns41_hexty, $atns41_r34, $atns41_r38, $atns41_r40

          set $atns41_j = 0
          set $atns41_jmax = $atns41_cnt
          set $atns41_sub_overflowed = 0
          if $atns41_jmax > 8
            set $atns41_jmax = 8
            set $atns41_sub_overflowed = 1
          end
          while $atns41_j < $atns41_jmax
            set $atns41_sub = $atns41_e + 0x3c + $atns41_j*8
            set $atns41_soffx = *(short*)($atns41_sub + 0)
            set $atns41_soffy = *(short*)($atns41_sub + 2)
            set $atns41_shx = *(short*)($atns41_sub + 4)
            set $atns41_shy = *(short*)($atns41_sub + 6)
            if $atns41_j > 0
              printf ","
            end
            printf "[%d,%d,%d,%d]", $atns41_soffx, $atns41_soffy, $atns41_shx, $atns41_shy
            set $atns41_j = $atns41_j + 1
          end
          printf "]}\n"

          # Sub-overflow marker: emitted here, as its own line, only after
          # the elem line above has already closed with "]}\n" -- jus-atns.4.2
          # fix. Emitting it mid-line (the old behaviour) interleaved this
          # printf's text into the still-open elem JSON line and corrupted it.
          if $atns41_sub_overflowed == 1
            printf "{\"type\":\"overflow\",\"frame\":%d,\"record\":%d,\"elem\":\"0x%x\",\"kind\":\"sub\",\"cnt\":%d,\"cap\":8}\n", $atns41_frame, $atns41_r, $atns41_e, $atns41_cnt
          end

          set $atns41_e = *(unsigned int*)($atns41_e + 0x00)
          set $atns41_ecount = $atns41_ecount + 1
        end
        if $atns41_e != 0 && $atns41_ecount >= 8
          printf "{\"type\":\"overflow\",\"frame\":%d,\"record\":%d,\"wrap\":\"0x%x\",\"kind\":\"elem\",\"cap\":8}\n", $atns41_frame, $atns41_r, $atns41_wrap
        end
      end
      set $atns41_r = $atns41_r + 1
    end
  end
  continue
end

continue
