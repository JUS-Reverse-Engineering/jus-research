# Register probe at the 0x0207FD98 gate (jus-8zoi).
#
# Question: at 0x0207FD98-0x0207FDAC inside routine 0x0207FBD0 --
#   ldr r0,[r6,#0x18]; tst r0,#1
#   ldrne r1,[r4,#8]; ldrbne r0,[r1,#0x18]; orrne r0,r0,#2; strbne r0,[r1,#0x18]
# -- the gate reads node r6's +0x18 bit 0, and the store marks node r4's
# object (r1 = *(r4+8)). Are r6 and r4 the same node when this fires? If
# not, which node's bit gates which node's object?
#
# This does not re-derive the writer -- that's already established in
# zoi_obj18_writer.md (the store at 0x0207FDAC, +8 = 0x0207FDB4/0207FDAC+4
# reported pc). This probe captures r4, r6, both nodes' +0x18 flag words,
# both nodes' object pointers (+0x08), both nodes' owning-record pointers
# (+0x0C, per the node layout in zoi_baseline_bit.gdb's header comment),
# and object A's (r4's object) +0x18 byte immediately before the store, so
# a same-node/different-node determination and codex's falsifier
# (r6 != r4, r6 bit0 set, r4 bit0 clear, store executes) can be checked
# directly against captured registers rather than inferred.
#
# Second breakpoint at 0x0207FDAC (the strbne itself) captures r0/r1 and
# the cpsr Z flag so it's explicit whether the predicated store actually
# executed for that hit (condition NE requires Z clear). GDB stops on this
# address regardless of whether the predicate would skip the instruction's
# effect -- per the task brief, ARM predication does not suppress the
# breakpoint fetch/decode trap.
#
# Frame alignment reuses the same two markers as zoi_obj18_writer.gdb:
# - 0x0207FAD4 conditioned on the fixed per-frame heartbeat record
#   (r4 == 0x220e234) as a plain frame counter.
# - 0x0207FB0C ("flags -> 0x209" store) conditioned on rec49 (0x2212D3C)
#   and rec50 (0x2212EC4) so the frame each record's own flag word flips
#   to 0x209 is visible in the same log.
#
# Every commands block ends with continue; a top-level continue follows
# the last breakpoint (required -- see scripts/gdb/README.md "Emulator
# silently freezes").

set pagination off
set confirm off
set logging file zoi_fd98_regs.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $zoi_frame = 0

break *0x0207FAD4
condition $bpnum $r4 == 0x220e234
commands
  silent
  set $zoi_frame = $zoi_frame + 1
  printf "FRAME_MARKER n=%d\n", $zoi_frame
  continue
end

break *0x0207FB0C
condition $bpnum $r4 == 0x2212d3c || $r4 == 0x2212ec4
commands
  silent
  printf "FLAG_0x209 rec=0x%x r0=0x%x lr=0x%x frame_marker=%d\n", $r4, $r0, $lr, $zoi_frame
  continue
end

break *0x0207FD98
commands
  silent
  printf "GATE frame=%d r4=0x%x r6=0x%x same_node=%d n4_18=0x%x n6_18=0x%x objA=0x%x objB=0x%x recA=0x%x recB=0x%x objA18_pre=0x%x\n", $zoi_frame, $r4, $r6, ($r4 == $r6), *(unsigned int*)($r4+0x18), *(unsigned int*)($r6+0x18), *(unsigned int*)($r4+0x08), *(unsigned int*)($r6+0x08), *(unsigned int*)($r4+0x0c), *(unsigned int*)($r6+0x0c), *(unsigned char*)(*(unsigned int*)($r4+0x08)+0x18)
  continue
end

break *0x0207FDAC
commands
  silent
  printf "STORE frame=%d r0=0x%x r1=0x%x cpsr_z=%d store_exec=%d\n", $zoi_frame, $r0, $r1, (($cpsr >> 30) & 1), ((($cpsr >> 30) & 1) == 0)
  continue
end

printf "PROBE_ARMED\n"
continue
