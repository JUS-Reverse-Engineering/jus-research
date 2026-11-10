# Extended creation probe for jus-flp3.
#
# Extends scripts/gdb/xyqc_preroll_probe.gdb (jus-xyqc, commits 90ef1a2,
# 6f35632) with the fields jus-flp3 asks for: creator resolution, x at
# creation vs at the 0x209 store, and a bounded node-list walk logging node
# +0x18 bit 0 and entry +0x08 bit 5 per node. See
# the session handoff, "Next move" 1 (tracker item jus-flp3).
#
# Frame counter: NO RAM address for a game-visible frame counter is
# confirmed anywhere in this repo (checked scripts/emu/jus_addresses.py,
# scripts/emu/README.md, docs/confirmed-facts/INVENTORY.md, and
# docs/research/feel-captures/projectile-conflict-2026-09-10/nodes/RESULTS.md,
# which states this explicitly). projectile_census.py/projectile_replay.py
# use emu.framecount(), a Lua-side bridge call GDB cannot read. This probe
# therefore prints a monotonic software sequence number ($flp3_seq,
# incremented once per CREATE_REC hit) instead of a frame count, and keeps
# relying on GDB log line order for ordering across breakpoints, same as
# the jus-xyqc batch. This is a known limitation, not a new finding -- do
# not read $flp3_seq as a frame number.
#
# The node walk also fires at the two flag-store breakpoints
# (0x0207FAD4/0x0207FB0C), not just at CREATE_REC: a first run showed
# record+0x08 is always 0 (no nodes) at the CREATE_REC breakpoint for every
# created record across all seven states (0 NODE lines in 7/7 logs), so
# node +0x18/entry +0x08 cannot be read at creation time -- nodes are
# attached to the record later. NODE_AT_0x9/NODE_AT_0x209 are the only
# points in this probe where a created record's node state is observed.
#
# Node walk fields mirror scripts/emu/projectile_census.py exactly
# (RECORD_NODE_HEAD_OFFSET=0x08, NODE_STRIDE=0x2C, NODE_NEXT_OFFSET=0x00,
# NODE_ENTRY_OFFSET=0x10, NODE_18_OFFSET=0x18, ENTRY_0x08_OFFSET=0x08).
# It is a singly linked list (node+0x00 = next), not a count+array, so the
# walk below is a bounded `while` loop capped at 16 nodes (matching
# projectile_census.py's NODE_MAX_WALK) with a self-loop guard (stops if
# next == current or next == the walk's own head, rather than looping
# forever on a corrupt or cyclic list). The logs committed with this batch
# (flp3_creation_600.log.gz, all seven states) were captured with the cap
# at 8 and no self-loop guard. Among the 26 created records this batch
# tracks, the deepest walk observed was 4 nodes (taikoubou-upx's
# 0x2213B04), so raising the cap does not change any created-record
# result in the committed logs. One pre-existing, non-created record
# (0x220F494, in pc-sasuke-x-npc-yusuke-x's log) hit the old 8-node cap
# exactly (i=0..7) at every NODE_AT_0x9/NODE_AT_0x209 read for that
# record -- its true node-list length in that run is unknown and was
# truncated, not measured as exactly 8; this is exactly the case the
# raised cap and self-loop guard are for.
#
# Creator resolution: r1 at 0x0207C988/0x0207CA70 is already documented as
# "owner" in xyqc_preroll_probe.gdb's CREATE printf. The two in-battle
# fighter-object pointers are confirmed at the fighter table 0x021DEB3C
# (slot 0 = P1, word at 0x021DEB3C) and slot 1 (word at 0x021DEB40) --
# docs/research/Character-State-Struct.md:35, docs/confirmed-facts/physics.md:698-736,
# scripts/emu/README.md "the victim/opponent fighter object address is
# per-deck". Each fighter object's chr_b index is at +0x41
# (scripts/emu/README.md "Nearby fields on the same struct"). If r1 matches
# neither pointer, log r1 plus *(r1) and *(r1+4) and mark resolution
# unverified per jus-flp3 step 1(b) -- do not infer a character from shape.
#
# Record x: s32 at [[record+0x5C]+0xC] (raw units, /256 = pixels), the same
# field projectile_census.py reads (ELEMENT_X_OFFSET=0xC via record+0x5C).
#
# Rules: do not name node +0x18 bit 0, entry +0x08 bit 5, or record+0x38
# as priority/cancel/hit or any gameplay meaning -- this script logs
# observables only.

set pagination off
set confirm off
set logging file flp3_creation.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $flp3_seq = 0
set $flp3_p1 = 0x021DEB3C
set $flp3_p2 = 0x021DEB40

break *0x0207C988
commands
  silent
  printf "CREATE mgr=0x%x owner=0x%x arg34=0x%x arg38=0x%x arg3c=0x%x lr=0x%x\n", $r0, $r1, $r2, $r3, *(unsigned int*)($sp), $lr
  continue
end

break *0x0207CA70
commands
  silent
  set $flp3_seq = $flp3_seq + 1
  set $rec = $r4
  set $creator = $r1
  set $p1ptr = *(unsigned int*)($flp3_p1)
  set $p2ptr = *(unsigned int*)($flp3_p2)
  set $elem = *(unsigned int*)($rec+0x5C)

  printf "CREATE_REC seq=%d record=0x%x f34=0x%x f38=0x%x f3c=0x%x creator=0x%x p1=0x%x p2=0x%x", $flp3_seq, $rec, *(unsigned int*)($rec+0x34), *(unsigned int*)($rec+0x38), *(unsigned int*)($rec+0x3c), $creator, $p1ptr, $p2ptr

  if $creator == $p1ptr
    printf " creator_resolved=P1 creator_chr_b=%d", *(unsigned char*)($creator+0x41)
  else
    if $creator == $p2ptr
      printf " creator_resolved=P2 creator_chr_b=%d", *(unsigned char*)($creator+0x41)
    else
      if $creator >= 0x02000000 && $creator < 0x02400000
        printf " creator_resolved=UNVERIFIED creator_deref0=0x%x creator_deref4=0x%x", *(unsigned int*)($creator), *(unsigned int*)($creator+4)
      else
        printf " creator_resolved=UNVERIFIED creator_raw=0x%x (outside RAM)", $creator
      end
    end
  end

  if $elem != 0 && $elem >= 0x02000000 && $elem < 0x02400000
    printf " x_create=%d\n", *(int*)($elem+0xC)
  else
    printf " x_create=NULL elem=0x%x\n", $elem
  end

  set $flp3_head = *(unsigned int*)($rec+0x08)
  set $flp3_node = $flp3_head
  set $flp3_i = 0
  while $flp3_node != 0 && $flp3_i < 16
    set $flp3_n18 = *(unsigned int*)($flp3_node+0x18)
    set $flp3_entry = *(unsigned int*)($flp3_node+0x10)
    if $flp3_entry != 0 && $flp3_entry >= 0x02000000 && $flp3_entry < 0x02400000
      set $flp3_e08 = *(unsigned int*)($flp3_entry+0x08)
      printf "  NODE seq=%d i=%d addr=0x%x n18=0x%x n18_bit0=%d entry=0x%x e08=0x%x e08_bit5=%d\n", $flp3_seq, $flp3_i, $flp3_node, $flp3_n18, $flp3_n18 & 1, $flp3_entry, $flp3_e08, ($flp3_e08 >> 5) & 1
    else
      printf "  NODE seq=%d i=%d addr=0x%x n18=0x%x n18_bit0=%d entry=0x%x e08=NULL\n", $flp3_seq, $flp3_i, $flp3_node, $flp3_n18, $flp3_n18 & 1, $flp3_entry
    end
    set $flp3_next = *(unsigned int*)($flp3_node+0x00)
    if $flp3_next == $flp3_node || $flp3_next == $flp3_head
      set $flp3_node = 0
    else
      set $flp3_node = $flp3_next
    end
    set $flp3_i = $flp3_i + 1
  end

  continue
end

break *0x0207FAD4
commands
  silent
  set $elem = *(unsigned int*)($r4+0x5C)
  printf "FLAG_0x9 rec=0x%x f34=0x%x f3c=0x%x r0=0x%x lr=0x%x", $r4, *(unsigned int*)($r4+0x34), *(unsigned int*)($r4+0x3c), $r0, $lr
  if $elem != 0 && $elem >= 0x02000000 && $elem < 0x02400000
    printf " x=%d\n", *(int*)($elem+0xC)
  else
    printf " x=NULL elem=0x%x\n", $elem
  end
  set $flp3_head = *(unsigned int*)($r4+0x08)
  set $flp3_node = $flp3_head
  set $flp3_i = 0
  while $flp3_node != 0 && $flp3_i < 16
    set $flp3_n18 = *(unsigned int*)($flp3_node+0x18)
    set $flp3_entry = *(unsigned int*)($flp3_node+0x10)
    if $flp3_entry != 0 && $flp3_entry >= 0x02000000 && $flp3_entry < 0x02400000
      set $flp3_e08 = *(unsigned int*)($flp3_entry+0x08)
      printf "  NODE_AT_0x9 rec=0x%x i=%d addr=0x%x n18=0x%x n18_bit0=%d entry=0x%x e08=0x%x e08_bit5=%d\n", $r4, $flp3_i, $flp3_node, $flp3_n18, $flp3_n18 & 1, $flp3_entry, $flp3_e08, ($flp3_e08 >> 5) & 1
    else
      printf "  NODE_AT_0x9 rec=0x%x i=%d addr=0x%x n18=0x%x n18_bit0=%d entry=0x%x e08=NULL\n", $r4, $flp3_i, $flp3_node, $flp3_n18, $flp3_n18 & 1, $flp3_entry
    end
    set $flp3_next = *(unsigned int*)($flp3_node+0x00)
    if $flp3_next == $flp3_node || $flp3_next == $flp3_head
      set $flp3_node = 0
    else
      set $flp3_node = $flp3_next
    end
    set $flp3_i = $flp3_i + 1
  end
  continue
end

break *0x0207FB0C
commands
  silent
  set $elem = *(unsigned int*)($r4+0x5C)
  printf "FLAG_0x209 rec=0x%x f34=0x%x f3c=0x%x r0=0x%x lr=0x%x", $r4, *(unsigned int*)($r4+0x34), *(unsigned int*)($r4+0x3c), $r0, $lr
  if $elem != 0 && $elem >= 0x02000000 && $elem < 0x02400000
    printf " x=%d\n", *(int*)($elem+0xC)
  else
    printf " x=NULL elem=0x%x\n", $elem
  end
  set $flp3_head = *(unsigned int*)($r4+0x08)
  set $flp3_node = $flp3_head
  set $flp3_i = 0
  while $flp3_node != 0 && $flp3_i < 16
    set $flp3_n18 = *(unsigned int*)($flp3_node+0x18)
    set $flp3_entry = *(unsigned int*)($flp3_node+0x10)
    if $flp3_entry != 0 && $flp3_entry >= 0x02000000 && $flp3_entry < 0x02400000
      set $flp3_e08 = *(unsigned int*)($flp3_entry+0x08)
      printf "  NODE_AT_0x209 rec=0x%x i=%d addr=0x%x n18=0x%x n18_bit0=%d entry=0x%x e08=0x%x e08_bit5=%d\n", $r4, $flp3_i, $flp3_node, $flp3_n18, $flp3_n18 & 1, $flp3_entry, $flp3_e08, ($flp3_e08 >> 5) & 1
    else
      printf "  NODE_AT_0x209 rec=0x%x i=%d addr=0x%x n18=0x%x n18_bit0=%d entry=0x%x e08=NULL\n", $r4, $flp3_i, $flp3_node, $flp3_n18, $flp3_n18 & 1, $flp3_entry
    end
    set $flp3_next = *(unsigned int*)($flp3_node+0x00)
    if $flp3_next == $flp3_node || $flp3_next == $flp3_head
      set $flp3_node = 0
    else
      set $flp3_node = $flp3_next
    end
    set $flp3_i = $flp3_i + 1
  end
  continue
end

printf "PROBE_ARMED\n"
continue
