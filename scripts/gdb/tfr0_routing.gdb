# tfr0_routing.gdb -- jus-tfr0 (LIVE half). Instruments every per-bucket
# append site named in docs/research/findings/collision-bucket-routing-static.md:
# helper buckets 1/4/8 (0x020809C8's tail-appends at 0x02080AF8/0x02080AAC/
# 0x02080BDC), inline bucket 7 (0x0207FD94, inside the per-frame pass
# 0x0207FBD0), buckets 2/3 (0x020808C0's tail-appends at 0x020809B8/
# 0x02080934), the clash list (0x02080660's append at 0x0208087C, into
# record+0x10), and bucket 10 (no static producer found anywhere in arm9 --
# this probe write-watches manager+0x78/+0x7C directly instead of a call
# site, per the static finding's own live-test spec).
#
# Register roles are taken verbatim from the two already-live-verified
# probes this one extends (scripts/gdb/dib9_pairs.gdb, scripts/gdb/
# f58_routes.gdb), not re-derived:
#   - 0x0207FC20 (LOOP_HDR): r4=pair entry, r6=nodeA=*(objA+0x1c),
#     r7=nodeB=*(objB+0x1c), objA=*(r4+8), objB=*(r4+0xc). r6/r7 keep these
#     roles through the WHOLE function body to 0x0207FE3C (f58 comment,
#     confirmed by reading every intervening block), so the bucket-7
#     append at 0x0207FD94 can read nodeA/nodeB straight from r6/r7.
#     REFUTED for r7 on the naruto run (jus-tfr0, 2026-09-12): the
#     BUCKET n=7 line logged nodeB14=0x0 via $r7 at this exact site,
#     contradicting the same pair's LOOP_HDR line three breakpoints
#     earlier (nodeB14=0x10001001) -- r7 does NOT reliably still hold
#     nodeB by the time execution reaches 0x0207FD94 on every path.
#     RESULTS.md's routing table uses the LOOP_HDR reading instead of the
#     BUCKET line's own (wrong) one for this pair. Not re-verified by
#     disassembly; flagged here as a probe defect for any follow-up
#     (fix: re-derive nodeB via *(objB+0x1c) at the bucket-7 site itself,
#     same fix already applied below at the bucket-1/4/8/2/3 sites).
#     Comment-only annotation; behaviour unchanged.
#   - 0x020809C8 (bucket 1/4/8 helper): its OWN r6 (not the outer loop's)
#     holds the pair entry at each append site (dib9_pairs.gdb "BUCKET n=1"
#     etc. read objA=*(r6+8), objB=*(r6+0xc) at 0x02080AF8/AAC/BDC) --
#     the caller's r6/r7 (nodeA/nodeB) are NOT live here; node fields are
#     re-derived below via *(obj+0x1c) instead of trusted from a register.
#   - 0x020808C0 (bucket 2/3 helper): entry r0=manager, r1=record, r2=pair
#     entry; internally r4 = the pair entry (mov r4,r2 at 0x020808C4, per
#     f58 comment), still r4 at both append sites 0x020809B8/0x02080934.
#   - 0x02080660 (clash-list helper): entry r0=manager, r1=record (moved to
#     r7 at 0x0208066C), r2=pair entry, r3=objB=*(r2+0xc), r6=nodeB=
#     *(objB+0x1c) loaded at 0x02080670 and still r6 at the append site
#     0x0208087C (f58 comment). This is a single-node (nodeB-only) append;
#     no A-side node is established by any prior doc for this site, so A
#     fields are logged as NA here rather than guessed.
#
# New for this probe (jus-tfr0): every append-site command block also
# derives node+0x14 (class bits) and node+0x18 bit 0 for whichever
# node(s) are available at that site, plus the pair's slot field
# (record+0x34, per colprm-record-0x34-0x3c-low-bits-agree-with-player-slot.md)
# when the record pointer is in-range -- none of this was logged at the
# per-bucket lines in the prior two probes (only at LOOP_HDR, one join step
# away). LOOP_HDR itself gains nodeA14/nodeB14 for the same reason.
#
# Bucket 10 (`manager+0x78`/`+0x7c`, no static producer found by the
# complete 100-site arm9 census in collision-bucket-routing-static.md):
# rather than a call-site breakpoint (none exists), this probe sets a
# hardware watchpoint on both list-head words the first time PASS_ENTRY
# resolves the manager pointer. Any write at all refutes "no producer";
# silence across every frame of every state corroborates it (a direct
# pointer-store producer bypassing 0x02037b98 would still show up here).
#
# No gameplay naming of node +0x14/+0x18, entry +0x08 bit 5, record+0x34,
# object +0x18 bit 0x2, 0x209, or the slot field anywhere in this probe's
# output strings -- raw values only.

set pagination off
set confirm off
set logging file tfr0_routing.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $tfr0_frame = 0
set $tfr0_manager = 0
set $tfr0_watch_armed = 0

# ---- Frame marker ----
break *0x0207FAD4
condition $bpnum $r4 == 0x220e234
commands
  silent
  set $tfr0_frame = $tfr0_frame + 1
  printf "FRAME n=%d\n", $tfr0_frame
  continue
end

# ---- Per-frame pass entry; also arms the bucket-10 watchpoints once ----
break *0x0207FBD0
commands
  silent
  printf "PASS_ENTRY frame=%d manager=0x%x lr=0x%x\n", $tfr0_frame, $r0, $lr
  if $tfr0_watch_armed == 0
    set $tfr0_manager = $r0
    set $tfr0_watch_armed = 1
    printf "ARMING_BUCKET10_WATCH manager=0x%x head=0x%x tail=0x%x\n", $tfr0_manager, $tfr0_manager+0x78, $tfr0_manager+0x7c
    watch *(unsigned int*)($tfr0_manager+0x78)
    commands
      silent
      printf "BUCKET10_HEAD_WRITE frame=%d old=0x%x new=0x%x pc=0x%x\n", $tfr0_frame, $__old, $__new, $pc
      continue
    end
    watch *(unsigned int*)($tfr0_manager+0x7c)
    commands
      silent
      printf "BUCKET10_TAIL_WRITE frame=%d old=0x%x new=0x%x pc=0x%x\n", $tfr0_frame, $__old, $__new, $pc
      continue
    end
  end
  continue
end

# ---- Loop header: pair, both objects, both nodes, +0x14/+0x18, slot field ----
break *0x0207FC20
commands
  silent
  set $tfr0_pair = $r4
  set $tfr0_objA = *(unsigned int*)($r4+0x8)
  set $tfr0_objB = *(unsigned int*)($r4+0xC)
  set $tfr0_nodeA = $r6
  set $tfr0_nodeB = $r7
  printf "LOOP_HDR frame=%d pair=0x%x objA=0x%x objB=0x%x nodeA=0x%x nodeB=0x%x", $tfr0_frame, $tfr0_pair, $tfr0_objA, $tfr0_objB, $tfr0_nodeA, $tfr0_nodeB
  if $tfr0_nodeA == 0 || $tfr0_nodeB == 0
    printf " BOUNDS_CASE nodeA_zero=%d nodeB_zero=%d\n", ($tfr0_nodeA == 0), ($tfr0_nodeB == 0)
  else
    set $tfr0_n14A = *(unsigned int*)($tfr0_nodeA+0x14)
    set $tfr0_n14B = *(unsigned int*)($tfr0_nodeB+0x14)
    set $tfr0_n18A = *(unsigned int*)($tfr0_nodeA+0x18)
    set $tfr0_n18B = *(unsigned int*)($tfr0_nodeB+0x18)
    set $tfr0_recA = *(unsigned int*)($tfr0_nodeA+0xC)
    set $tfr0_recB = *(unsigned int*)($tfr0_nodeB+0xC)
    printf " nodeA14=0x%x nodeB14=0x%x nodeA18bit0=%d nodeB18bit0=%d", $tfr0_n14A, $tfr0_n14B, ($tfr0_n18A & 1), ($tfr0_n18B & 1)
    if $tfr0_recA != 0 && $tfr0_recA >= 0x02000000 && $tfr0_recA < 0x02400000
      printf " recA34=0x%x", *(unsigned int*)($tfr0_recA+0x34)
    else
      printf " recA34=NA"
    end
    if $tfr0_recB != 0 && $tfr0_recB >= 0x02000000 && $tfr0_recB < 0x02400000
      printf " recB34=0x%x", *(unsigned int*)($tfr0_recB+0x34)
    else
      printf " recB34=NA"
    end
    printf "\n"
  end
  continue
end

# ---- Bucket 7 append (inline, 0x0207FBD0). r6/r7 still nodeA/nodeB here. ----
break *0x0207FD94
commands
  silent
  set $tfr0_pair = $r4
  set $tfr0_objA = *(unsigned int*)($r4+0x8)
  set $tfr0_objB = *(unsigned int*)($r4+0xC)
  printf "BUCKET n=7 frame=%d pair=0x%x objA=0x%x objB=0x%x nodeA14=0x%x nodeB14=0x%x nodeA18bit0=%d nodeB18bit0=%d\n", $tfr0_frame, $tfr0_pair, $tfr0_objA, $tfr0_objB, *(unsigned int*)($r6+0x14), *(unsigned int*)($r7+0x14), (*(unsigned int*)($r6+0x18) & 1), (*(unsigned int*)($r7+0x18) & 1)
  continue
end

# ---- 0x020809C8 entry (bucket 1/4/8 helper); r2 = pair entry (caller-live
# roles per dib9_pairs.gdb header; r7 is NOT yet the manager here). ----
break *0x020809C8
commands
  silent
  printf "FILLER_ENTRY frame=%d pair=0x%x\n", $tfr0_frame, $r2
  continue
end

# ---- Bucket 1/4/8 appends. This routine's OWN r6 = pair entry at each site. ----
break *0x02080AF8
commands
  silent
  set $tfr0_objA = *(unsigned int*)($r6+0x8)
  set $tfr0_objB = *(unsigned int*)($r6+0xC)
  set $tfr0_nodeA = *(unsigned int*)($tfr0_objA+0x1C)
  set $tfr0_nodeB = *(unsigned int*)($tfr0_objB+0x1C)
  printf "BUCKET n=1 frame=%d pair=0x%x objA=0x%x objB=0x%x nodeA14=0x%x nodeB14=0x%x nodeA18bit0=%d nodeB18bit0=%d\n", $tfr0_frame, $r6, $tfr0_objA, $tfr0_objB, *(unsigned int*)($tfr0_nodeA+0x14), *(unsigned int*)($tfr0_nodeB+0x14), (*(unsigned int*)($tfr0_nodeA+0x18) & 1), (*(unsigned int*)($tfr0_nodeB+0x18) & 1)
  continue
end

break *0x02080AAC
commands
  silent
  set $tfr0_objA = *(unsigned int*)($r6+0x8)
  set $tfr0_objB = *(unsigned int*)($r6+0xC)
  set $tfr0_nodeA = *(unsigned int*)($tfr0_objA+0x1C)
  set $tfr0_nodeB = *(unsigned int*)($tfr0_objB+0x1C)
  printf "BUCKET n=4 frame=%d pair=0x%x objA=0x%x objB=0x%x nodeA14=0x%x nodeB14=0x%x nodeA18bit0=%d nodeB18bit0=%d\n", $tfr0_frame, $r6, $tfr0_objA, $tfr0_objB, *(unsigned int*)($tfr0_nodeA+0x14), *(unsigned int*)($tfr0_nodeB+0x14), (*(unsigned int*)($tfr0_nodeA+0x18) & 1), (*(unsigned int*)($tfr0_nodeB+0x18) & 1)
  continue
end

break *0x02080BDC
commands
  silent
  set $tfr0_objA = *(unsigned int*)($r6+0x8)
  set $tfr0_objB = *(unsigned int*)($r6+0xC)
  set $tfr0_nodeA = *(unsigned int*)($tfr0_objA+0x1C)
  set $tfr0_nodeB = *(unsigned int*)($tfr0_objB+0x1C)
  printf "BUCKET n=8 frame=%d pair=0x%x objA=0x%x objB=0x%x nodeA14=0x%x nodeB14=0x%x nodeA18bit0=%d nodeB18bit0=%d\n", $tfr0_frame, $r6, $tfr0_objA, $tfr0_objB, *(unsigned int*)($tfr0_nodeA+0x14), *(unsigned int*)($tfr0_nodeB+0x14), (*(unsigned int*)($tfr0_nodeA+0x18) & 1), (*(unsigned int*)($tfr0_nodeB+0x18) & 1)
  continue
end

# ---- Bucket 2/3 appends (0x020808C0). r4 = pair entry inside this routine
# (f58 comment: mov r4,r2 at entry). ----
break *0x020809B8
commands
  silent
  set $tfr0_objA = *(unsigned int*)($r4+0x8)
  set $tfr0_objB = *(unsigned int*)($r4+0xC)
  set $tfr0_nodeA = *(unsigned int*)($tfr0_objA+0x1C)
  set $tfr0_nodeB = *(unsigned int*)($tfr0_objB+0x1C)
  printf "BUCKET n=2 frame=%d pair=0x%x objA=0x%x objB=0x%x nodeA14=0x%x nodeB14=0x%x nodeA18bit0=%d nodeB18bit0=%d\n", $tfr0_frame, $r4, $tfr0_objA, $tfr0_objB, *(unsigned int*)($tfr0_nodeA+0x14), *(unsigned int*)($tfr0_nodeB+0x14), (*(unsigned int*)($tfr0_nodeA+0x18) & 1), (*(unsigned int*)($tfr0_nodeB+0x18) & 1)
  continue
end

break *0x02080934
commands
  silent
  set $tfr0_objA = *(unsigned int*)($r4+0x8)
  set $tfr0_objB = *(unsigned int*)($r4+0xC)
  set $tfr0_nodeA = *(unsigned int*)($tfr0_objA+0x1C)
  set $tfr0_nodeB = *(unsigned int*)($tfr0_objB+0x1C)
  printf "BUCKET n=3 frame=%d pair=0x%x objA=0x%x objB=0x%x nodeA14=0x%x nodeB14=0x%x nodeA18bit0=%d nodeB18bit0=%d\n", $tfr0_frame, $r4, $tfr0_objA, $tfr0_objB, *(unsigned int*)($tfr0_nodeA+0x14), *(unsigned int*)($tfr0_nodeB+0x14), (*(unsigned int*)($tfr0_nodeA+0x18) & 1), (*(unsigned int*)($tfr0_nodeB+0x18) & 1)
  continue
end

# ---- Clash-list append (0x02080660 -> 0x0208087C). r7=record, r6=nodeB,
# per f58 comment; single-node append, A-side unresolved (logged NA). ----
break *0x0208087C
commands
  silent
  printf "BUCKET n=clash frame=%d record=0x%x nodeA=NA nodeB=0x%x nodeA14=NA nodeB14=0x%x nodeA18bit0=NA nodeB18bit0=%d clash_payload=0x%x\n", $tfr0_frame, $r7, $r6, *(unsigned int*)($r6+0x14), (*(unsigned int*)($r6+0x18) & 1), *(unsigned int*)($r6+0xC)
  continue
end

printf "PROBE_ARMED\n"
continue
