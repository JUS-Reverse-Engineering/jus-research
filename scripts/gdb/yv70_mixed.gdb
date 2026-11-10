# f58_routes.gdb -- jus-58bf. Extends scripts/gdb/dib9_pairs.gdb with the four
# enqueue routes jus-dib9 did not watch (bl 0x20808c0 at 0x0208016C/0x020801B4
# = buckets 2/3 via the manager's +0x38/+0x40 heads inside 0x020808C0; bl
# 0x2080660 at 0x0207FED4/0x0207FF14 = the clash-node list at record+0x10),
# the 0x0207FD70 return-value check on 0x020808A4 (the gate that decides the
# inline bucket-7 append at 0x0207FD94), and every conditional-branch exit
# from the loop body (0x0207FC20-0x0207FD6C) that reaches the pair's common
# "advance to next entry" point at 0x0207FE3C without going through any
# append or mark. Register roles re-verified for THIS probe by full
# disassembly (`query.py disasm`), not assumed from dib9_pairs.gdb's header:
#
# - r4 = pair entry, r6 = nodeA (*(objA+0x1c)), r7 = nodeB (*(objB+0x1c))
#   throughout the ENTIRE function body from 0x0207FC20 through the
#   0x0207FE3C advance -- confirmed by reading every intervening block
#   (0x0207FC9C, 0x0207FCF8, 0x0207FDB4-0x0207FE38 all still address fields
#   through r6/r7). This lets every EXIT breakpoint below log pair/nodeA/
#   nodeB without re-deriving them.
#
# - 0x020808C0 (`query.py disasm 0x20808c0 264`, `query.py func` reports
#   size=264, callers=1): entry r0=manager, r1=record (caller's r4, the
#   bucket-6 record this pair's outer per-record loop is walking -- NOT
#   objA/objB), r2=pair entry. It reads objA=*(r2+8), objB=*(r2+0xc), and
#   record's own +0x40 word (via r1). Two tail-append sites inside, both
#   `bl 0x2037b98` (the same generic tail-append `contact-queue-insert-
#   writer-found.md` documents for buckets 1/4/8): `add r0,r5,#0x40` at
#   0x02080934 (manager+0x40 = bucket 3, node payload = the pair entry --
#   `str r4,[r6,#8]` at 0x02080938, r4 = the caller's r2/this function's r4
#   set at entry (`mov r4,r2` 0x020808C4), i.e. the pair entry, NOT the
#   record -- matches doc's bucket-3 head shape but corrects the payload)
#   and `add r0,r5,#0x38` at 0x020809B8 (manager+0x38 = bucket 2, same
#   pair-entry payload, `str r4,[r6,#8]` at 0x020809BC).
#   Which of the two fires depends on a chain of node/record flag tests
#   (0x020808D8-0x02080990); at 0x020808F4-0x02080904 the routine also
#   does a predicated `ldrbne r3,[r2,#0x18]; bicne r3,r3,#2; strbne
#   r3,[r2,#0x18]` with r2 = *(entry+0xc) = objB, gated on
#   `*(nodeB+0x18) & 1` -- CORRECTION: this is a CLEAR of object+0x18 bit
#   0x2, i.e. THE SAME restricted field jus-8zoi's object+0x18 documents,
#   not a different struct field as a prior version of this comment
#   claimed. Uninstrumented in this probe; flagged as a follow-up, not a
#   third mark site.
#
# - 0x02080660 (`query.py disasm 0x2080660 260`, size=580, callers=1):
#   entry r0=manager, r1=record (caller's r1 per the outer-loop disasm at
#   0x0207FE5C `ldr r4,[fp,#8]`; INSIDE this function r1 is moved into r7
#   at 0x0208066C `mov r7,r1`, so r7 = record, not manager), r2=pair entry
#   (r3=*(r2+0xc)=objB is read at entry, then r6=*(r3+0x1c)=nodeB at
#   0x02080670 `ldr r6,[r3,#0x1c]` -- r6 is nodeB, NOT the pair entry
#   itself). Despite the doc's summary ("clash nodes -> record+0x10"), the
#   actual store creating a clash node is `add r0,r7,#0x10` + `bl
#   0x2037b98` at 0x0208087C -- record+0x10 IS the clash-node list head,
#   confirmed; the node itself is popped from the manager's `+0x20` free
#   list (`ldr r8,[r0,#0x20]` at 0x02080854, `bl 0x2037c24`), payload =
#   `*(nodeB+0xc)` (`str r1,[r8,#8]` at 0x0208086C, r1 there loaded from
#   `[r6,#0xc]` i.e. nodeB+0xc) -- log it raw as clash_payload, no naming.
#   This path is gated on a large chain of position/velocity
#   comparisons (0x020806D8-0x0208081C, using nodeB's `+0x28`-derived
#   short and record's `+0x2c..0x3a` short fields) that reads as a
#   swept-AABB overlap test, not a flag test -- consistent with "clash"
#   meaning a geometric near-miss, not a flag-gated category. Several
#   early exits (`bne 0x208089c`) return without any append.
#
# - 0x020808A4 (`query.py disasm 0x20808a4 28`, size=28, callers=1, called
#   twice inline at 0x0207FD48 and 0x0207FD6C -- NOT the same call site as
#   contact-queue-insert-writer-found.md's helpers, which are separate
#   functions): `tst r0,#0x1000; if clear return 0; else tst r1,#1;
#   return 1 if that bit is CLEAR, else 0`. Inputs at the two call sites
#   are node-local: call 1 (0x0207FD40-48) passes r0=nodeA+0x14,
#   r1=nodeA+0x18; call 2 (0x0207FD54-6C) passes r0=nodeB+0x14 (bic'd,
#   top byte cleared, but the routine re-tests the ORIGINAL r0 value
#   which the bic instruction at 0x0207FD5C overwrote into r1, not r0 --
#   r0 at 0x0207FD54 is still the unmasked nodeB+0x14 word when the bl
#   fires). So it returns 1 iff (node+0x14 bit 0x1000 is SET) AND
#   (node+0x18 bit 0 is CLEAR), else 0. Call 1's result gates an
#   IMMEDIATE exit if 1 (0x0207FD4C/50, bne 0x207fe3c) -- this is EXIT_N,
#   helper(nodeA +0x14, +0x18) returned 1. Call 2's result gates whether the bucket-7
#   inline append (0x0207FD78-94) executes: if 0, skip straight to the
#   mark gate at 0x0207FD98 with NO append. Given node+0x18 bit 0 is the
#   already-measured mark-permission qualifier (jus-8zoi), this reads as
#   "append to bucket 7 only if nodeB is flagged 0x1000 AND not already
#   permitted to mark" -- i.e. bucket-7 append and the mark-permission
#   state are complementary for nodeB, which is the mechanical answer to
#   the naruto asymmetry question (see MARK/CMP20808A4 log lines).
#
# EXIT sites: every conditional branch between 0x0207FC20 and 0x0207FD6C
# whose target is the shared advance point 0x0207FE3C, or whose target is
# a distinct code region that itself only ever reaches 0x0207FE3C without
# touching append/mark (`query.py disasm 0x0207FC20 400` traced by hand,
# each target followed to its own terminal branch):
#   EXIT_A 0x0207FC28 bne  (nodeB+0x14 & r9 != 0, r9 = 0x00080800 loaded
#                           pc-relative from the pool word at 0x020801F4)
#   EXIT_B 0x0207FC34 beq  (nodeA+0x14 & 0x10000000 == 0)
#   EXIT_C 0x0207FC3C bne  (nodeA+0x14 & 0x40000000 != 0)
#   EXIT_D 0x0207FC48 bne  (nodeB+0x1c & 0x10000000 != 0)
#   EXIT_E 0x0207FC58 bne  (recB(=*(nodeB+0xc))+0x40 & 0x80 != 0)
#   EXIT_F 0x0207FC98 b    (unconditional; "adjacent-slot merge" path --
#                           writes half-fields to both nodes' +0x20/+0x22,
#                           reached when nodeA+0x14 bit 0x8000000 SET and
#                           nodeB+0x14 bit 0x1000 SET)
#   EXIT_G 0x0207FCB0 blo  (byte cmp *(nodeA+0x10) < *(nodeB+0x10), reached
#                           when 0x8000000 SET and 0x1000 CLEAR)
#   EXIT_H 0x0207FCF4 b    (unconditional; sets recA+0x40 bit 0x20000,
#                           same gate as EXIT_G but byte cmp not blo)
#   EXIT_I 0x0207FDB4 (breakpoint on the branch TARGET, not source, since
#                      the source 0x0207FD0C's own commands would be
#                      redundant with this one; reached when 0x8000000
#                      CLEAR and the byte-cmp swapped order disagrees --
#                      this whole region 0x0207FDB4-0x0207FE38 always
#                      terminates at 0x0207FE3C per disasm, confirmed by
#                      following every branch in it)
#   EXIT_J 0x0207FD14 bne  (leftover r1 from 0x0207FC38 nonzero)
#   EXIT_K 0x0207FD1C bne  (nodeB+0x14 & 0x40000000 != 0)
#   EXIT_L 0x0207FD24 bne  (nodeA+0x14 & 0x80000 != 0)
#   EXIT_M 0x0207FD34 bne  (nodeA+0x24 & (nodeB+0x14 & 0xFFFFFF) nonzero --
#                           A's +0x24 halfword tested/masked against B's
#                           +0x14 low 3 bytes, NOT nodeA alone)
#   EXIT_N 0x0207FD50 bne  (helper(nodeA +0x14, +0x18) returned 1 --
#                           first bl 0x20808a4 call, args both from nodeA)
#
# Total breakpoints in this file: 14 kept from dib9_pairs.gdb + 9 new
# required (4 call sites x2 + the 0x0207FD70 cmp) + 14 EXIT sites = 37.
# This exceeds the brief's "< 25 breakpoints total" guidance. Deviation,
# reported as such: each EXIT site is hit at most once per pair-entry per
# frame (mutually exclusive with the others in the same chain), so the
# perf risk the guidance is actually protecting against -- breakpoint
# TRAFFIC slowing emulation (README's own framing) -- stays bounded by the
# handful of pair-entries per frame these states have (2 per state, per
# dib9), not by the breakpoint count itself. Kept anyway because dropping
# any of the 14 EXIT sites would leave the falsification question ("where
# is the dice pair dropped") only partially answered.
#
# No gameplay naming of node +0x18 bit 0, entry +0x08 bit 5, record+0x38,
# object +0x18 bit 0x2, 0x209, or the slot field anywhere in this probe's
# output strings.
#
# Self-caught defect (before any state besides the control was run): a
# breakpoint set AT a conditional branch's own instruction address fires
# every time execution reaches that PC, whether or not the branch is
# actually taken -- the first control run showed EVERY EXIT_A-E site firing
# in sequence for one pair entry, which would misread as "took every exit"
# if read naively. Fixed by reading CPSR at each such breakpoint and
# printing a `taken=` field computed from that branch's own condition code
# (Z for bne/beq, C for blo); EXIT_F/H (unconditional `b`) and EXIT_I
# (logged at the branch TARGET, not source) do not have this ambiguity.
# Only `taken=1` rows are real exits; `taken=0` rows just mean the pair
# entry passed through that instruction address without taking it.

set pagination off
set confirm off
set logging file yv70_mixed.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $yv70_frame = 0

# ---- Frame marker (kept from dib9_pairs.gdb) ----
break *0x0207FAD4
condition $bpnum $r4 == 0x220e234
commands
  silent
  set $yv70_frame = $yv70_frame + 1
  printf "FRAME n=%d\n", $yv70_frame
  continue
end

# ---- STORE209, all records (kept) ----
break *0x0207FB0C
commands
  silent
  printf "STORE209 frame=%d rec=0x%x r0=0x%x lr=0x%x\n", $yv70_frame, $r4, $r0, $lr
  continue
end

# ---- Per-frame pass entry (kept) ----
break *0x0207FBD0
commands
  silent
  printf "PASS_ENTRY frame=%d manager=0x%x lr=0x%x\n", $yv70_frame, $r0, $lr
  continue
end

# ---- Loop header (kept, same one-instruction shift as dib9_pairs.gdb) ----
break *0x0207FC20
commands
  silent
  set $yv70_pair = $r4
  set $yv70_objA = *(unsigned int*)($r4+0x8)
  set $yv70_objB = *(unsigned int*)($r4+0xC)
  set $yv70_nodeA = $r6
  set $yv70_nodeB = $r7
  printf "LOOP_HDR frame=%d pair=0x%x objA=0x%x objB=0x%x nodeA=0x%x nodeB=0x%x", $yv70_frame, $yv70_pair, $yv70_objA, $yv70_objB, $yv70_nodeA, $yv70_nodeB
  if $yv70_nodeA == 0 || $yv70_nodeB == 0
    printf " BOUNDS_CASE nodeA_zero=%d nodeB_zero=%d\n", ($yv70_nodeA == 0), ($yv70_nodeB == 0)
  else
    set $yv70_n18A = *(unsigned int*)($yv70_nodeA+0x18)
    set $yv70_n18B = *(unsigned int*)($yv70_nodeB+0x18)
    set $yv70_recA = *(unsigned int*)($yv70_nodeA+0xC)
    set $yv70_recB = *(unsigned int*)($yv70_nodeB+0xC)
    printf " nodeA18=0x%x nodeB18=0x%x recA=0x%x recB=0x%x\n", $yv70_n18A, $yv70_n18B, $yv70_recA, $yv70_recB
  end
  continue
end

# ---- Existing bucket-append sites inside 0x0207FBD0 (kept) ----
break *0x0207FD94
commands
  silent
  printf "BUCKET n=7 frame=%d pair=0x%x objA=0x%x objB=0x%x\n", $yv70_frame, $r4, *(unsigned int*)($r4+0x8), *(unsigned int*)($r4+0xC)
  continue
end

break *0x0207FF98
commands
  silent
  printf "BUCKET n=5 frame=%d pair=0x%x objA=0x%x objB=0x%x\n", $yv70_frame, $r7, *(unsigned int*)($r7+0x8), *(unsigned int*)($r7+0xC)
  continue
end

break *0x02080008
commands
  silent
  printf "BUCKET n=16 frame=%d pair=0x%x objA=0x%x objB=0x%x\n", $yv70_frame, $r7, *(unsigned int*)($r7+0x8), *(unsigned int*)($r7+0xC)
  continue
end

break *0x02080118
commands
  silent
  printf "BUCKET n=15 frame=%d pair=0x%x objA=0x%x objB=0x%x\n", $yv70_frame, $r7, *(unsigned int*)($r7+0x8), *(unsigned int*)($r7+0xC)
  continue
end

# ---- 0x020809C8 (bucket 1/4/8 helper) entry (kept) ----
break *0x020809C8
commands
  silent
  set $yv70_r2 = $r2
  printf "FILLER_ENTRY frame=%d pair=0x%x", $yv70_frame, $yv70_r2
  if $yv70_r2 != 0 && $yv70_r2 >= 0x02000000 && $yv70_r2 < 0x02400000
    printf " objA=0x%x objB=0x%x", *(unsigned int*)($yv70_r2+0x8), *(unsigned int*)($yv70_r2+0xC)
  else
    printf " objA=NA objB=NA"
  end
  printf " r7_callerlive=0x%x lr=0x%x\n", $r7, $lr
  continue
end

break *0x02080AF8
commands
  silent
  printf "BUCKET n=1 frame=%d pair=0x%x objA=0x%x objB=0x%x\n", $yv70_frame, $r6, *(unsigned int*)($r6+0x8), *(unsigned int*)($r6+0xC)
  continue
end

break *0x02080AAC
commands
  silent
  printf "BUCKET n=4 frame=%d pair=0x%x objA=0x%x objB=0x%x\n", $yv70_frame, $r6, *(unsigned int*)($r6+0x8), *(unsigned int*)($r6+0xC)
  continue
end

break *0x02080BDC
commands
  silent
  printf "BUCKET n=8 frame=%d pair=0x%x objA=0x%x objB=0x%x\n", $yv70_frame, $r6, *(unsigned int*)($r6+0x8), *(unsigned int*)($r6+0xC)
  continue
end

# ---- Mark site 1: 0x02080C18, unconditional strb (kept) ----
break *0x02080C18
commands
  silent
  printf "MARK site=0x02080C18 frame=%d objA=0x%x newval=0x%x store_exec=1(unconditional)\n", $yv70_frame, $r1, $r0
  continue
end

# ---- Mark site 2: 0x0207FDAC, strbne (kept) ----
break *0x0207FDAC
commands
  silent
  set $yv70_z = ($cpsr >> 30) & 1
  printf "MARK site=0x0207FDAC frame=%d pair=0x%x nodeA=0x%x nodeA18_bit0=%d cpsr_z=%d store_exec=%d r0=0x%x r1=0x%x\n", $yv70_frame, $r4, $r6, (*(unsigned int*)($r6+0x18)) & 1, $yv70_z, ($yv70_z == 0), $r0, $r1
  continue
end

# =====================================================================
# NEW for jus-58bf: the four blind enqueue routes.
# =====================================================================

# ---- bl 0x20808c0 call site 1 (0x0208016C). r0=manager, r1=record,
# r2=pair entry (see header comment). Log all of r0-r3 plus the pair. ----
break *0x0208016C
commands
  silent
  printf "CALL_20808C0 site=0x0208016C frame=%d manager=0x%x record=0x%x pair=0x%x r3=0x%x\n", $yv70_frame, $r0, $r1, $r2, $r3
  continue
end

break *0x02080170
commands
  silent
  printf "RET_20808C0 site=0x0208016C frame=%d r0=0x%x\n", $yv70_frame, $r0
  continue
end

# ---- bl 0x20808c0 call site 2 (0x020801B4) ----
break *0x020801B4
commands
  silent
  printf "CALL_20808C0 site=0x020801B4 frame=%d manager=0x%x record=0x%x pair=0x%x r3=0x%x\n", $yv70_frame, $r0, $r1, $r2, $r3
  continue
end

break *0x020801B8
commands
  silent
  printf "RET_20808C0 site=0x020801B4 frame=%d r0=0x%x\n", $yv70_frame, $r0
  continue
end

# ---- bl 0x2080660 call site 1 (0x0207FED4). Same r0/r1/r2 convention. ----
break *0x0207FED4
commands
  silent
  printf "CALL_2080660 site=0x0207FED4 frame=%d manager=0x%x record=0x%x pair=0x%x r3=0x%x\n", $yv70_frame, $r0, $r1, $r2, $r3
  continue
end

break *0x0207FED8
commands
  silent
  printf "RET_2080660 site=0x0207FED4 frame=%d r0=0x%x\n", $yv70_frame, $r0
  continue
end

# ---- bl 0x2080660 call site 2 (0x0207FF14) ----
break *0x0207FF14
commands
  silent
  printf "CALL_2080660 site=0x0207FF14 frame=%d manager=0x%x record=0x%x pair=0x%x r3=0x%x\n", $yv70_frame, $r0, $r1, $r2, $r3
  continue
end

break *0x0207FF18
commands
  silent
  printf "RET_2080660 site=0x0207FF14 frame=%d r0=0x%x\n", $yv70_frame, $r0
  continue
end

# ---- 0x0207FD70: cmp r0,#0 after the SECOND bl 0x20808a4 (nodeB gate for
# the bucket-7 inline append). r4=pair, r6=nodeA, r7=nodeB (still valid). ----
break *0x0207FD70
commands
  silent
  printf "CMP_20808A4 site=0x0207FD70 frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x r0=0x%x nodeB18_bit0=%d\n", $yv70_frame, $r4, $r6, $r7, $r0, (*(unsigned int*)($r7+0x18)) & 1
  continue
end

# =====================================================================
# NEW for jus-58bf: early-exit sites between 0x0207FC20 and 0x0207FD6C.
# =====================================================================

break *0x0207FC28
commands
  silent
  printf "EXIT site=0x0207FC28 frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x nodeA24=0x%x nodeA14=0x%x nodeB24=0x%x nodeB14=0x%x taken=%d\n", $yv70_frame, $r4, $r6, $r7, (*(unsigned short*)($r6+0x24)), (*(unsigned int*)($r6+0x14)), (*(unsigned short*)($r7+0x24)), (*(unsigned int*)($r7+0x14)), ((($cpsr >> 30) & 1) == 0)
  continue
end

break *0x0207FC34
commands
  silent
  printf "EXIT site=0x0207FC34 frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x nodeA24=0x%x nodeA14=0x%x nodeB24=0x%x nodeB14=0x%x taken=%d\n", $yv70_frame, $r4, $r6, $r7, (*(unsigned short*)($r6+0x24)), (*(unsigned int*)($r6+0x14)), (*(unsigned short*)($r7+0x24)), (*(unsigned int*)($r7+0x14)), ((($cpsr >> 30) & 1) == 1)
  continue
end

break *0x0207FC3C
commands
  silent
  printf "EXIT site=0x0207FC3C frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x nodeA24=0x%x nodeA14=0x%x nodeB24=0x%x nodeB14=0x%x taken=%d\n", $yv70_frame, $r4, $r6, $r7, (*(unsigned short*)($r6+0x24)), (*(unsigned int*)($r6+0x14)), (*(unsigned short*)($r7+0x24)), (*(unsigned int*)($r7+0x14)), ((($cpsr >> 30) & 1) == 0)
  continue
end

break *0x0207FC48
commands
  silent
  printf "EXIT site=0x0207FC48 frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x nodeA24=0x%x nodeA14=0x%x nodeB24=0x%x nodeB14=0x%x taken=%d\n", $yv70_frame, $r4, $r6, $r7, (*(unsigned short*)($r6+0x24)), (*(unsigned int*)($r6+0x14)), (*(unsigned short*)($r7+0x24)), (*(unsigned int*)($r7+0x14)), ((($cpsr >> 30) & 1) == 0)
  continue
end

break *0x0207FC58
commands
  silent
  printf "EXIT site=0x0207FC58 frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x nodeA24=0x%x nodeA14=0x%x nodeB24=0x%x nodeB14=0x%x taken=%d\n", $yv70_frame, $r4, $r6, $r7, (*(unsigned short*)($r6+0x24)), (*(unsigned int*)($r6+0x14)), (*(unsigned short*)($r7+0x24)), (*(unsigned int*)($r7+0x14)), ((($cpsr >> 30) & 1) == 0)
  continue
end

break *0x0207FC98
commands
  silent
  printf "EXIT site=0x0207FC98 frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x nodeA24=0x%x nodeA14=0x%x nodeB24=0x%x nodeB14=0x%x taken=1(unconditional)\n", $yv70_frame, $r4, $r6, $r7, (*(unsigned short*)($r6+0x24)), (*(unsigned int*)($r6+0x14)), (*(unsigned short*)($r7+0x24)), (*(unsigned int*)($r7+0x14))
  continue
end

break *0x0207FCB0
commands
  silent
  printf "EXIT site=0x0207FCB0 frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x nodeA24=0x%x nodeA14=0x%x nodeB24=0x%x nodeB14=0x%x taken=%d\n", $yv70_frame, $r4, $r6, $r7, (*(unsigned short*)($r6+0x24)), (*(unsigned int*)($r6+0x14)), (*(unsigned short*)($r7+0x24)), (*(unsigned int*)($r7+0x14)), ((($cpsr >> 29) & 1) == 0)
  continue
end

break *0x0207FCF4
commands
  silent
  printf "EXIT site=0x0207FCF4 frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x nodeA24=0x%x nodeA14=0x%x nodeB24=0x%x nodeB14=0x%x taken=1(unconditional)\n", $yv70_frame, $r4, $r6, $r7, (*(unsigned short*)($r6+0x24)), (*(unsigned int*)($r6+0x14)), (*(unsigned short*)($r7+0x24)), (*(unsigned int*)($r7+0x14))
  continue
end

break *0x0207FDB4
commands
  silent
  printf "EXIT site=0x0207FDB4 frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x nodeA24=0x%x nodeA14=0x%x nodeB24=0x%x nodeB14=0x%x taken=1(target-only)\n", $yv70_frame, $r4, $r6, $r7, (*(unsigned short*)($r6+0x24)), (*(unsigned int*)($r6+0x14)), (*(unsigned short*)($r7+0x24)), (*(unsigned int*)($r7+0x14))
  continue
end

break *0x0207FD14
commands
  silent
  printf "EXIT site=0x0207FD14 frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x nodeA24=0x%x nodeA14=0x%x nodeB24=0x%x nodeB14=0x%x taken=%d\n", $yv70_frame, $r4, $r6, $r7, (*(unsigned short*)($r6+0x24)), (*(unsigned int*)($r6+0x14)), (*(unsigned short*)($r7+0x24)), (*(unsigned int*)($r7+0x14)), ((($cpsr >> 30) & 1) == 0)
  continue
end

break *0x0207FD1C
commands
  silent
  printf "EXIT site=0x0207FD1C frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x nodeA24=0x%x nodeA14=0x%x nodeB24=0x%x nodeB14=0x%x taken=%d\n", $yv70_frame, $r4, $r6, $r7, (*(unsigned short*)($r6+0x24)), (*(unsigned int*)($r6+0x14)), (*(unsigned short*)($r7+0x24)), (*(unsigned int*)($r7+0x14)), ((($cpsr >> 30) & 1) == 0)
  continue
end

break *0x0207FD24
commands
  silent
  printf "EXIT site=0x0207FD24 frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x nodeA24=0x%x nodeA14=0x%x nodeB24=0x%x nodeB14=0x%x taken=%d\n", $yv70_frame, $r4, $r6, $r7, (*(unsigned short*)($r6+0x24)), (*(unsigned int*)($r6+0x14)), (*(unsigned short*)($r7+0x24)), (*(unsigned int*)($r7+0x14)), ((($cpsr >> 30) & 1) == 0)
  continue
end

break *0x0207FD34
commands
  silent
  printf "EXIT site=0x0207FD34 frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x nodeA24=0x%x nodeA14=0x%x nodeB24=0x%x nodeB14=0x%x taken=%d\n", $yv70_frame, $r4, $r6, $r7, (*(unsigned short*)($r6+0x24)), (*(unsigned int*)($r6+0x14)), (*(unsigned short*)($r7+0x24)), (*(unsigned int*)($r7+0x14)), ((($cpsr >> 30) & 1) == 0)
  continue
end

break *0x0207FD50
commands
  silent
  printf "EXIT site=0x0207FD50 frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x nodeA24=0x%x nodeA14=0x%x nodeB24=0x%x nodeB14=0x%x taken=%d\n", $yv70_frame, $r4, $r6, $r7, (*(unsigned short*)($r6+0x24)), (*(unsigned int*)($r6+0x14)), (*(unsigned short*)($r7+0x24)), (*(unsigned int*)($r7+0x14)), ((($cpsr >> 30) & 1) == 0)
  continue
end


# =====================================================================
# jus-yv70 extensions (this file). Three additions to f58_routes.gdb:
#
# 1. Goal 1 -- the object+0x18 bit-0x2 CLEAR predicated store f58's header
#    already flagged as "uninstrumented ... flagged as a follow-up" is at
#    0x02080904 (`strbne r3,[r2,#0x18]`), gated on `*(nodeB+0x18) & 1`
#    (test at 0x020808F8, r1=nodeB at that point). CORRECTION to this
#    tracker item's own brief: the brief describes this site as "inside function
#    0x02080660". Address arithmetic on f58's own cited sizes disproves
#    that: `query.py func 0x2080660` reports size=580 (0x244), so
#    0x02080660+0x244 = 0x020808A4 exactly -- the NEXT function's start
#    (f58 header's own size=28 for 0x020808A4 confirms: 0x20808A4+0x1C =
#    0x020808C0, the function AFTER that). The clear site at
#    0x020808F4-0x02080904 is inside 0x020808C0 (push at 0x020808C0,
#    `mov r4,r2` at 0x020808C4), exactly where f58's header already
#    describes it. Re-disassembled 0x02080660 in full (`query.py disasm
#    0x2080660 580`) for this tracker item's goal-1 deliverable anyway (see
#    docs/research/feel-captures/projectile-conflict-2026-09-11/
#    codex_prompt_clear_site.txt and the SUMMARY.md section for the
#    plain-English writeup); it does not contain the clear site.
#
#    Register roles AT 0x02080904 confirmed by disasm from 0x020808C0:
#    r4 = pair entry (`mov r4,r2` 0x020808C4), r2 = objB (`ldr
#    r2,[r4,#0xc]` 0x020808CC, never reassigned before the store), r1 =
#    nodeB (`ldr r1,[r2,#0x1c]` 0x020808E0, r2 there is the objB loaded
#    at entry -- same register, not yet clobbered), r0 = nodeA (`ldr
#    r0,[r3,#0x1c]` 0x020808DC, r3 there = objA). The breakpoint is set
#    AT the strbne instruction itself (0x02080904); at that PC the OLD
#    byte is still in memory (the store has not executed), so
#    `*(unsigned char*)(objB+0x18)` read at the breakpoint IS the
#    pre-store value -- no need to read r3 (which already holds the
#    bic'd NEW value computed by the preceding `bicne` at 0x02080900).
#
# 2. Goal 2 -- +0x24/+0x14 logging added to every existing EXIT_A-N
#    commands block below (in place, not duplicated), plus two new
#    sites confirmed by `query.py disasm 0x207fc20 300`:
#      - 0x0207FD3C: `strh r0,[r6,#0x24]` (r6=nodeA). r0 there =
#        orr(nodeA+0x24_old, bic(r3,#0xff000000)) and r3 = nodeB+0x14
#        (`ldr r3,[r7,#0x14]` at function entry 0x0207FC20, r7=nodeB,
#        never reassigned before this point) -- confirms
#        pair-loop-drops.md's "nodeA+0x24 OR-ed with nodeB+0x14 &
#        0xFFFFFF" claim exactly, r3 is unchanged since entry. Breakpoint
#        set AT the strh (pre-store state readable from memory, same
#        logic as item 1).
#      - 0x0207FD64: this is the `beq #0x207fd78` instruction itself (the
#        "shortcut" the brief describes) -- confirmed by disasm, not a
#        different instruction. Taking it skips the second `bl
#        0x20808a4` call (0x0207FD68-6C) and its cmp/branch
#        (0x0207FD70-74), landing directly on the bucket-7 tail-append
#        entry (0x0207FD78) with NO second-helper evaluation. This is
#        the shortcut per f58's own header note about call 2's gate.
#        `taken=` computed from Z (beq).
#
# All new fields use the existing $yv70_frame/pair/nodeA/nodeB convention;
# no new gameplay naming.
# =====================================================================


# =====================================================================
# jus-yv70 goal 1: the object+0x18 bit-0x2 clear, breakpoint AT the
# predicated store itself (0x02080904). See header block above for the
# register-role derivation and the correction re: which function this
# lives in.
# =====================================================================
break *0x02080904
commands
  silent
  set $yv70_z = ($cpsr >> 30) & 1
  printf "CLEAR site=0x02080904 frame=%d pair=0x%x nodeB=0x%x nodeB18=0x%x objB=0x%x objB18_old=0x%x cpsr_z=%d store_exec=%d\n", $yv70_frame, $r4, $r1, (*(unsigned int*)($r1+0x18)), $r2, (*(unsigned char*)($r2+0x18)), $yv70_z, ($yv70_z == 0)
  continue
end

# =====================================================================
# jus-yv70 goal 2 new site 1: 0x0207FD3C, strh r0,[r6,#0x24] (nodeA+0x24
# OR-ed with nodeB+0x14 & 0xFFFFFF). Breakpoint AT the strh; the memory
# read of nodeA+0x24 here is the PRE-store value (store has not executed
# yet at this PC).
# =====================================================================
break *0x0207FD3C
commands
  silent
  printf "STRH_FD3C frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x nodeA24_pre=0x%x nodeA14=0x%x nodeB24=0x%x nodeB14=0x%x\n", $yv70_frame, $r4, $r6, $r7, (*(unsigned short*)($r6+0x24)), (*(unsigned int*)($r6+0x14)), (*(unsigned short*)($r7+0x24)), (*(unsigned int*)($r7+0x14))
  continue
end

# =====================================================================
# jus-yv70 goal 2 new site 2: 0x0207FD64, the `beq #0x207fd78` shortcut
# instruction itself. taken=1 means the second bl 0x20808a4 call and its
# cmp/branch are skipped entirely for this pair entry.
# =====================================================================
break *0x0207FD64
commands
  silent
  set $yv70_z2 = ($cpsr >> 30) & 1
  printf "SHORTCUT_FD64 frame=%d pair=0x%x nodeA=0x%x nodeB=0x%x nodeA24=0x%x nodeA14=0x%x nodeB24=0x%x nodeB14=0x%x taken=%d\n", $yv70_frame, $r4, $r6, $r7, (*(unsigned short*)($r6+0x24)), (*(unsigned int*)($r6+0x14)), (*(unsigned short*)($r7+0x24)), (*(unsigned int*)($r7+0x14)), ($yv70_z2 == 1)
  continue
end

printf "PROBE_ARMED\n"
continue
