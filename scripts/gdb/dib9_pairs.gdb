# Pair-level pass probe for jus-dib9.
#
# Question: for every collision pair the per-frame pass (0x0207FBD0) and its
# bucket-1/4/8 helper (0x020809C8) process in frames 1-3, which two
# participants are involved, which bucket (tail-append site) the pair is
# routed to, and does the mark store (object +0x18 bit 0x2) fire for either
# side. Builds on the register roles already established live in
# docs/research/feel-captures/projectile-conflict-2026-09-11/
# pc-naruto-fy-npc-yusuke-fy/{zoi_fd98_regs.md,zoi_obj18_writer.md} and the
# bucket table in docs/research/findings/contact-queue-insert-writer-found.md.
#
# Register roles, verified against disassembly for THIS probe
# (scripts/analysis/query.py disasm), not assumed:
#
# - Loop header 0x0207FC10-0x0207FC1C (`query.py disasm 0x0207FC00 40`):
#     0x0207FC10  ldr r0, [r4, #0xc]   ; r0 = pair+0xC = objB
#     0x0207FC14  ldr r1, [r4, #8]     ; r1 = pair+0x8 = objA
#     0x0207FC18  ldr r7, [r0, #0x1c]  ; r7 = *(objB+0x1c) = nodeB
#     0x0207FC1C  ldr r6, [r1, #0x1c]  ; r6 = *(objA+0x1c) = nodeA
#   A breakpoint AT 0x0207FC1C stops BEFORE that instruction executes, so r6
#   (nodeA) is not yet loaded there -- only r7 (nodeB, loaded by the PRECEDING
#   instruction at 0x0207FC18) is valid at that pc. This probe therefore
#   breaks one instruction later, at 0x0207FC20, where both r6 and r7 hold
#   their final values for this iteration (DEVIATION from the literal brief
#   text "break *0x0207FC1C", reported as such). r4 = pair entry throughout
#   (unchanged by this instruction pair); objA=*(r4+8), objB=*(r4+0xC).
#
# - Bucket append sites, re-derived from a full disassembly of both routines
#   (`query.py disasm 0x0207FBD0 400`, `query.py disasm 0x020809C8 160`),
#   not assumed from the doc's examples. Each breakpoint address below IS
#   the `bl 0x02037b98` instruction; the `add` that computes the bucket
#   head lives one instruction (4-8 bytes) EARLIER at the address noted --
#   an earlier version of this comment wrongly showed the `add` mnemonic
#   at the breakpoint address itself:
#     0x0207FBD0 (per-frame pass) inline sites, all `bl 0x02037b98`:
#       0x0207FD94  bl 0x2037b98 -> bucket 7  ; add r0,r8,#0x60 @0x0207FD8C; payload reg r4 (str r4,[r7,#8] @0x0207FD90)
#       0x0207FF98  bl 0x2037b98 -> bucket 5  ; add r0,r8,#0x50 @0x0207FF94; payload reg r7 (str r7,[sb,#8] @0x0207FF8C)
#       0x02080008  bl 0x2037b98 -> bucket 16 ; add r0,r8,#0xa8 @0x02080004; payload reg r7 (str r7,[r5,#8] @0x0207FFFC)
#       0x02080118  bl 0x2037b98 -> bucket 15 ; add r0,r8,#0xa0 @0x02080114; payload reg r7 (str r7,[r5,#8] @0x0208010C)
#     0x020809C8 (bucket-1/4/8 helper) sites, all `bl 0x02037b98`:
#       0x02080AF8  bl 0x2037b98 -> bucket 1  ; add r0,r7,#0x30 @0x02080AF4; payload reg r6 (str r6,[r8,#8] @0x02080AF0)
#       0x02080AAC  bl 0x2037b98 -> bucket 4  ; add r0,r7,#0x48 @0x02080AA4; payload reg r6 (str r6,[r4,#8] @0x02080AA8)
#       0x02080BDC  bl 0x2037b98 -> bucket 8  ; add r0,r7,#0x68 @0x02080BD8; payload reg r6 (str r6,[r8,#8] @0x02080BD4)
#   Bucket head offset -> index: (offset-0x28)/8, matching
#   contact-queue-insert-writer-found.md's table exactly for 1/4/5/7/8;
#   buckets 15 and 16 are additional inline sites this probe adds (not in
#   that doc's table, which only enumerated 1-8). No other
#   `bl 0x02037b98` site exists inside either routine's bounds (function
#   sizes 1572 and 604 bytes per `query.py func`).
#
# - 0x020809C8 entry: r7 is caller-live at this exact pc, NOT the manager --
#   `mov r7,r0` (the instruction that actually loads the manager into r7)
#   is at 0x020809E8, ten instructions after entry, so a breakpoint AT
#   0x020809C8 reads r7 before that assignment happens. (The
#   contact-queue-insert-writer-found.md "add r0, r7, #0x48" reference is to
#   r7's value at the LATER bucket-append sites inside this routine, after
#   the mov, not at entry -- do not conflate the two.) r2 = pair entry per
#   HANDOFF.md "Important limits" ("r1/r4 at 0x020809C8 entry are
#   caller-live, not arguments" -- r2 is used instead, matching this
#   probe's r2-based objA/objB read via +8/+0xC, the same struct shape as
#   r4 in the 0x0207FBD0 loop header). This probe logs r7 at entry as
#   `r7_callerlive`, not `r7_manager`.
#
# - 0x02080C18 (strb r0,[r1,#0x18], jus-8zoi's known mark writer): disasm
#   (`query.py disasm 0x02080BE0 20`) shows this strb has NO condition code
#   -- gating is done by `beq`/`bne` branches before it, not by predication.
#   The store always executes once this breakpoint is hit. r1 = objA (loaded
#   at 0x02080C0C from r6's node), r4 = nodeA (tested at 0x02080BE0-BE8).
#
# - 0x0207FDAC (strbne r0,[r1,#0x18], jus-8zoi's second mark writer, inline
#   in 0x0207FBD0's bucket-7 path): predicated. r6 = nodeA (the gate),
#   r4 = pair entry, r1 = *(r4+8) = objA (loaded conditionally). Per
#   HANDOFF.md, `strbne` breakpoints stop BEFORE the predicated store
#   executes; this probe logs the Z flag and a derived store_exec instead of
#   trusting r0/r1 as "the stored value".
#
# No gameplay naming of node +0x18 bit 0, entry +0x08 bit 5, record+0x38,
# object +0x18 bit 0x2, 0x209, or the slot field anywhere in this probe's
# output strings.

set pagination off
set confirm off
set logging file dib9_pairs.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $dib9_frame = 0

# ---- Frame marker ----
break *0x0207FAD4
condition $bpnum $r4 == 0x220e234
commands
  silent
  set $dib9_frame = $dib9_frame + 1
  printf "FRAME n=%d\n", $dib9_frame
  continue
end

# ---- Existing 0x0207FB0C store breakpoint, ALL records (not conditioned) ----
break *0x0207FB0C
commands
  silent
  printf "STORE209 frame=%d rec=0x%x r0=0x%x lr=0x%x\n", $dib9_frame, $r4, $r0, $lr
  continue
end

# ---- Per-frame pass entry ----
break *0x0207FBD0
commands
  silent
  printf "PASS_ENTRY frame=%d manager=0x%x lr=0x%x\n", $dib9_frame, $r0, $lr
  continue
end

# ---- Loop header, one instruction after 0x0207FC1C so r6 (nodeA) is valid.
# See header comment: r4=pair, r6=nodeA=*(objA+0x1c), r7=nodeB=*(objB+0x1c). ----
break *0x0207FC20
commands
  silent
  set $dib9_pair = $r4
  set $dib9_objA = *(unsigned int*)($r4+0x8)
  set $dib9_objB = *(unsigned int*)($r4+0xC)
  set $dib9_nodeA = $r6
  set $dib9_nodeB = $r7
  printf "LOOP_HDR frame=%d pair=0x%x objA=0x%x objB=0x%x nodeA=0x%x nodeB=0x%x", $dib9_frame, $dib9_pair, $dib9_objA, $dib9_objB, $dib9_nodeA, $dib9_nodeB
  if $dib9_nodeA == 0 || $dib9_nodeB == 0
    printf " BOUNDS_CASE nodeA_zero=%d nodeB_zero=%d\n", ($dib9_nodeA == 0), ($dib9_nodeB == 0)
  else
    set $dib9_n18A = *(unsigned int*)($dib9_nodeA+0x18)
    set $dib9_n18B = *(unsigned int*)($dib9_nodeB+0x18)
    set $dib9_recA = *(unsigned int*)($dib9_nodeA+0xC)
    set $dib9_recB = *(unsigned int*)($dib9_nodeB+0xC)
    set $dib9_objA18 = *(unsigned char*)($dib9_objA+0x18)
    set $dib9_objB18 = *(unsigned char*)($dib9_objB+0x18)
    printf " nodeA18=0x%x nodeB18=0x%x recA=0x%x recB=0x%x", $dib9_n18A, $dib9_n18B, $dib9_recA, $dib9_recB
    if $dib9_recA != 0 && $dib9_recA >= 0x02000000 && $dib9_recA < 0x02400000
      printf " recA34=0x%x", *(unsigned int*)($dib9_recA+0x34)
    else
      printf " recA34=NA"
    end
    if $dib9_recB != 0 && $dib9_recB >= 0x02000000 && $dib9_recB < 0x02400000
      printf " recB34=0x%x", *(unsigned int*)($dib9_recB+0x34)
    else
      printf " recB34=NA"
    end
    printf " objA18b=0x%x objB18b=0x%x\n", $dib9_objA18, $dib9_objB18
  end
  continue
end

# ---- Bucket append sites inside 0x0207FBD0 ----
break *0x0207FD94
commands
  silent
  printf "BUCKET n=7 frame=%d pair=0x%x objA=0x%x objB=0x%x\n", $dib9_frame, $r4, *(unsigned int*)($r4+0x8), *(unsigned int*)($r4+0xC)
  continue
end

break *0x0207FF98
commands
  silent
  printf "BUCKET n=5 frame=%d pair=0x%x objA=0x%x objB=0x%x\n", $dib9_frame, $r7, *(unsigned int*)($r7+0x8), *(unsigned int*)($r7+0xC)
  continue
end

break *0x02080008
commands
  silent
  printf "BUCKET n=16 frame=%d pair=0x%x objA=0x%x objB=0x%x\n", $dib9_frame, $r7, *(unsigned int*)($r7+0x8), *(unsigned int*)($r7+0xC)
  continue
end

break *0x02080118
commands
  silent
  printf "BUCKET n=15 frame=%d pair=0x%x objA=0x%x objB=0x%x\n", $dib9_frame, $r7, *(unsigned int*)($r7+0x8), *(unsigned int*)($r7+0xC)
  continue
end

# ---- 0x020809C8 (bucket 1/4/8 helper) entry ----
break *0x020809C8
commands
  silent
  set $dib9_r2 = $r2
  printf "FILLER_ENTRY frame=%d pair=0x%x", $dib9_frame, $dib9_r2
  if $dib9_r2 != 0 && $dib9_r2 >= 0x02000000 && $dib9_r2 < 0x02400000
    printf " objA=0x%x objB=0x%x", *(unsigned int*)($dib9_r2+0x8), *(unsigned int*)($dib9_r2+0xC)
  else
    printf " objA=NA objB=NA"
  end
  printf " r7_callerlive=0x%x lr=0x%x\n", $r7, $lr
  continue
end

# ---- Bucket append sites inside 0x020809C8 ----
break *0x02080AF8
commands
  silent
  printf "BUCKET n=1 frame=%d pair=0x%x objA=0x%x objB=0x%x\n", $dib9_frame, $r6, *(unsigned int*)($r6+0x8), *(unsigned int*)($r6+0xC)
  continue
end

break *0x02080AAC
commands
  silent
  printf "BUCKET n=4 frame=%d pair=0x%x objA=0x%x objB=0x%x\n", $dib9_frame, $r6, *(unsigned int*)($r6+0x8), *(unsigned int*)($r6+0xC)
  continue
end

break *0x02080BDC
commands
  silent
  printf "BUCKET n=8 frame=%d pair=0x%x objA=0x%x objB=0x%x\n", $dib9_frame, $r6, *(unsigned int*)($r6+0x8), *(unsigned int*)($r6+0xC)
  continue
end

# ---- Mark store site 1: 0x02080C18, unconditional strb (no predicate --
# gating is done by branches before it; the store always executes once this
# breakpoint fires). r1 = objA, r0 = value about to be stored (bit 0x2 ORed
# in at 0x02080C14, before this breakpoint's pc). ----
break *0x02080C18
commands
  silent
  printf "MARK site=0x02080C18 frame=%d objA=0x%x newval=0x%x store_exec=1(unconditional)\n", $dib9_frame, $r1, $r0
  continue
end

# ---- Mark store site 2: 0x0207FDAC, strbne (predicated on the gate at
# 0x0207FD98: (*(r6+0x18) & 1) != 0). The breakpoint stops BEFORE the
# predicated store executes; log the Z flag instead of trusting r0/r1 as a
# fired store per HANDOFF.md "Important limits". NE requires Z clear, so
# store_exec = (Z==0). r6=nodeA (the gate register), r4=pair entry. ----
break *0x0207FDAC
commands
  silent
  set $dib9_z = ($cpsr >> 30) & 1
  printf "MARK site=0x0207FDAC frame=%d pair=0x%x nodeA=0x%x nodeA18_bit0=%d cpsr_z=%d store_exec=%d r0=0x%x r1=0x%x\n", $dib9_frame, $r4, $r6, (*(unsigned int*)($r6+0x18)) & 1, $dib9_z, ($dib9_z == 0), $r0, $r1
  continue
end

printf "PROBE_ARMED\n"
continue
