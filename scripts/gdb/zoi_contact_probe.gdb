# Contact-pair proof probe for jus-8zoi.
#
# Corrected target per jus-8zoi correction comment (2026-09-12): the
# contact-pair site is the bucket filler 0x020809C8, NOT 0x020823E4 (that
# address is the damage formula, see docs/confirmed-facts about damage.md).
# 0x020809C8 is called only from 0x0207FBD0
# (0x02080188/0x020801D0) -- see
# docs/research/findings/contact-queue-insert-writer-found.md section 2 and
# docs/research/findings/momotaro-yusuke-projectile-conflict.md "Nested bit
# traced". This probe measures which two records are paired at that site,
# every call, and correlates that with the existing 0x0207FAD4/0x0207FB0C
# flag-store breaks reused verbatim (field logic, not just addresses) from
# scripts/gdb/flp3_creation_probe.gdb (jus-flp3).
#
# Node layout offsets are the ones already confirmed in
# scripts/emu/projectile_census.py: NODE_NEXT_OFFSET=0x00,
# NODE_OBJ_OFFSET=0x08, NODE_REC_OFFSET=0x0C, NODE_ENTRY_OFFSET=0x10,
# NODE_18_OFFSET=0x18. record+0x5C -> position element, element+0xC = x
# (ELEMENT_X_OFFSET), same as flp3/qqiy.
#
# Bit-0x2 store site: docs/research/feel-captures/projectile-conflict-2026-09-10/b18-writer/RESULTS.md
# "GDB capture at the bit-0x2 write" found, at the strb *0x02080C18*, r1 =
# participant A's object (*(nodeA+0x08)), not a pair struct, r4 = node A,
# r5 = node B. This probe reuses that exact
# breakpoint and register assignment; it additionally resolves each node's
# owning record via NODE_REC_OFFSET (0x0C) and a self-check that the
# record's own node-list (record+0x08) actually contains that node
# address, walking with the same capped/self-loop-guarded loop
# scripts/emu/projectile_census.py and flp3_creation_probe.gdb use
# (NODE_MAX_WALK=16).
#
# Rules carried over: no gameplay naming of node +0x18 bit 0, entry +0x08
# bit 5, record+0x38, or the +0x34/+0x3C slot field -- offsets and raw
# values only ("agrees with player slot", never "owner"/"team").

set pagination off
set confirm off
set logging file zoi_contact.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $zoi_seq = 0

# Entry to the bucket filler. Per contact-queue-insert-writer-found.md
# section 3 ("filled pre-pipeline") and jus-8zoi measurement, this is a
# per-pair helper for buckets 1/4/8, not called exactly once per frame --
# the yugi-momotaro run saw four calls in the same frame (frame 62). r1/r4
# at this address are caller-live registers, not this routine's arguments;
# the pair identity is carried in r2, logged here only as a raw pointer.
break *0x020809C8
commands
  silent
  set $zoi_seq = $zoi_seq + 1
  printf "FILLER_ENTRY seq=%d r0=0x%x r1=0x%x r2=0x%x r3=0x%x r4=0x%x r5=0x%x lr=0x%x\n", $zoi_seq, $r0, $r1, $r2, $r3, $r4, $r5, $lr
  continue
end

# The bit-0x2 store itself: nodeA=r4, nodeB=r5, r1=participant A's object
# (*(nodeA+0x08)), exactly as captured in b18-writer/RESULTS.md. r0 here
# is the value about to be stored (breakpoint fires before the strb
# executes). The PAIROBJ_WORD dump below is a participant-A-object dump,
# not a dump of a separate pair struct.
break *0x02080C18
commands
  silent
  printf "PAIR_STORE seq=%d r0_val=0x%x pairobj=0x%x nodeA=0x%x nodeB=0x%x lr=0x%x\n", $zoi_seq, $r0, $r1, $r4, $r5, $lr

  # ---- Node A ----
  set $zoi_recA = *(unsigned int*)($r4+0x0C)
  set $zoi_entryA = *(unsigned int*)($r4+0x10)
  set $zoi_n18A = *(unsigned int*)($r4+0x18)
  printf "  NODE_A addr=0x%x rec=0x%x n18=0x%x n18_bit0=%d entry=0x%x", $r4, $zoi_recA, $zoi_n18A, $zoi_n18A & 1, $zoi_entryA
  if $zoi_entryA != 0 && $zoi_entryA >= 0x02000000 && $zoi_entryA < 0x02400000
    printf " e08=0x%x", *(unsigned int*)($zoi_entryA+0x08)
  else
    printf " e08=NULL"
  end
  if $zoi_recA != 0 && $zoi_recA >= 0x02000000 && $zoi_recA < 0x02400000
    printf " rec34=0x%x rec3c=0x%x rec40=0x%x", *(unsigned int*)($zoi_recA+0x34), *(unsigned int*)($zoi_recA+0x3c), *(unsigned int*)($zoi_recA+0x40)
    set $zoi_elemA = *(unsigned int*)($zoi_recA+0x5C)
    if $zoi_elemA != 0 && $zoi_elemA >= 0x02000000 && $zoi_elemA < 0x02400000
      printf " x=%d", *(int*)($zoi_elemA+0xC)
    else
      printf " x=NULL elem=0x%x", $zoi_elemA
    end
    set $zoi_walk = *(unsigned int*)($zoi_recA+0x08)
    set $zoi_found = 0
    set $zoi_i = 0
    while $zoi_walk != 0 && $zoi_i < 16
      if $zoi_walk == $r4
        set $zoi_found = 1
      end
      set $zoi_next = *(unsigned int*)($zoi_walk+0x00)
      if $zoi_next == $zoi_walk
        set $zoi_walk = 0
      else
        set $zoi_walk = $zoi_next
      end
      set $zoi_i = $zoi_i + 1
    end
    printf " rec_owns_node=%d", $zoi_found
  else
    printf " rec_owns_node=NA"
  end
  printf "\n"

  # ---- Node B ----
  set $zoi_recB = *(unsigned int*)($r5+0x0C)
  set $zoi_entryB = *(unsigned int*)($r5+0x10)
  set $zoi_n18B = *(unsigned int*)($r5+0x18)
  printf "  NODE_B addr=0x%x rec=0x%x n18=0x%x n18_bit0=%d entry=0x%x", $r5, $zoi_recB, $zoi_n18B, $zoi_n18B & 1, $zoi_entryB
  if $zoi_entryB != 0 && $zoi_entryB >= 0x02000000 && $zoi_entryB < 0x02400000
    printf " e08=0x%x", *(unsigned int*)($zoi_entryB+0x08)
  else
    printf " e08=NULL"
  end
  if $zoi_recB != 0 && $zoi_recB >= 0x02000000 && $zoi_recB < 0x02400000
    printf " rec34=0x%x rec3c=0x%x rec40=0x%x", *(unsigned int*)($zoi_recB+0x34), *(unsigned int*)($zoi_recB+0x3c), *(unsigned int*)($zoi_recB+0x40)
    set $zoi_elemB = *(unsigned int*)($zoi_recB+0x5C)
    if $zoi_elemB != 0 && $zoi_elemB >= 0x02000000 && $zoi_elemB < 0x02400000
      printf " x=%d", *(int*)($zoi_elemB+0xC)
    else
      printf " x=NULL elem=0x%x", $zoi_elemB
    end
    set $zoi_walk = *(unsigned int*)($zoi_recB+0x08)
    set $zoi_found = 0
    set $zoi_i = 0
    while $zoi_walk != 0 && $zoi_i < 16
      if $zoi_walk == $r5
        set $zoi_found = 1
      end
      set $zoi_next = *(unsigned int*)($zoi_walk+0x00)
      if $zoi_next == $zoi_walk
        set $zoi_walk = 0
      else
        set $zoi_walk = $zoi_next
      end
      set $zoi_i = $zoi_i + 1
    end
    printf " rec_owns_node=%d", $zoi_found
  else
    printf " rec_owns_node=NA"
  end
  printf "\n"

  # ---- Pair object dump, r1[0x00..0x20], 9 words ----
  set $zoi_i = 0
  while $zoi_i < 9
    set $zoi_off = $zoi_i * 4
    printf "  PAIROBJ_WORD off=0x%02x val=0x%x\n", $zoi_off, *(unsigned int*)($r1 + $zoi_off)
    set $zoi_i = $zoi_i + 1
  end

  continue
end

# Flag-store breaks, carried over verbatim from flp3_creation_probe.gdb
# (jus-flp3): record in r4, stored value in r0, node +0x18 bit0, entry
# +0x08 bit5, x via record+0x5C->elem+0xC. Doubles as the frame-marker
# convention: the control's baseline record (rec=0x220e234) hits this
# breakpoint once per frame.
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
  set $zoi_head = *(unsigned int*)($r4+0x08)
  set $zoi_node = $zoi_head
  set $zoi_i = 0
  while $zoi_node != 0 && $zoi_i < 16
    set $zoi_n18 = *(unsigned int*)($zoi_node+0x18)
    set $zoi_entry = *(unsigned int*)($zoi_node+0x10)
    if $zoi_entry != 0 && $zoi_entry >= 0x02000000 && $zoi_entry < 0x02400000
      set $zoi_e08 = *(unsigned int*)($zoi_entry+0x08)
      printf "  NODE_AT_0x9 rec=0x%x i=%d addr=0x%x n18=0x%x n18_bit0=%d entry=0x%x e08=0x%x e08_bit5=%d\n", $r4, $zoi_i, $zoi_node, $zoi_n18, $zoi_n18 & 1, $zoi_entry, $zoi_e08, ($zoi_e08 >> 5) & 1
    else
      printf "  NODE_AT_0x9 rec=0x%x i=%d addr=0x%x n18=0x%x n18_bit0=%d entry=0x%x e08=NULL\n", $r4, $zoi_i, $zoi_node, $zoi_n18, $zoi_n18 & 1, $zoi_entry
    end
    set $zoi_next = *(unsigned int*)($zoi_node+0x00)
    if $zoi_next == $zoi_node || $zoi_next == $zoi_head
      set $zoi_node = 0
    else
      set $zoi_node = $zoi_next
    end
    set $zoi_i = $zoi_i + 1
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
  set $zoi_head = *(unsigned int*)($r4+0x08)
  set $zoi_node = $zoi_head
  set $zoi_i = 0
  while $zoi_node != 0 && $zoi_i < 16
    set $zoi_n18 = *(unsigned int*)($zoi_node+0x18)
    set $zoi_entry = *(unsigned int*)($zoi_node+0x10)
    if $zoi_entry != 0 && $zoi_entry >= 0x02000000 && $zoi_entry < 0x02400000
      set $zoi_e08 = *(unsigned int*)($zoi_entry+0x08)
      printf "  NODE_AT_0x209 rec=0x%x i=%d addr=0x%x n18=0x%x n18_bit0=%d entry=0x%x e08=0x%x e08_bit5=%d\n", $r4, $zoi_i, $zoi_node, $zoi_n18, $zoi_n18 & 1, $zoi_entry, $zoi_e08, ($zoi_e08 >> 5) & 1
    else
      printf "  NODE_AT_0x209 rec=0x%x i=%d addr=0x%x n18=0x%x n18_bit0=%d entry=0x%x e08=NULL\n", $r4, $zoi_i, $zoi_node, $zoi_n18, $zoi_n18 & 1, $zoi_entry
    end
    set $zoi_next = *(unsigned int*)($zoi_node+0x00)
    if $zoi_next == $zoi_node || $zoi_next == $zoi_head
      set $zoi_node = 0
    else
      set $zoi_node = $zoi_next
    end
    set $zoi_i = $zoi_i + 1
  end
  continue
end

printf "PROBE_ARMED\n"
continue
