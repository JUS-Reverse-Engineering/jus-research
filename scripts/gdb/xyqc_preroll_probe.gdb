# Batch pre-roll probe for jus-xyqc.
#
# Combines the jus-8bjc record-creation probe (entry of the ColPrm
# record-create routine 0x0207C988, and the post-+0x38-store point
# 0x0207CA70) with breakpoints at the two record+0x40 flag stores
# identified in docs/research/findings/momotaro-yusuke-projectile-conflict.md
# ("Flag writer"): 0x0207FAD4 (0x8 -> 0x9 OR) and 0x0207FB0C (0x9 -> 0x209
# OR, conditional strne). Record pointer is $r4 at both flag-store sites per
# docs/research/feel-captures/projectile-conflict-2026-09-10/nodes/RESULTS.md
# ("Breakpoint condition (both breakpoints): $r4 == ...").
#
# Purpose: catch every record the game installs during a 600-frame no-input
# run, regardless of ColPrm slot or timing, so a projectile that spawns and
# is torn down between two census points is not invisible. Run with -cd so
# the log lands in the state's own output directory.
set pagination off
set confirm off
set logging file xyqc_preroll.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

break *0x0207C988
commands
  silent
  printf "CREATE mgr=0x%x owner=0x%x arg34=0x%x arg38=0x%x arg3c=0x%x lr=0x%x\n", $r0, $r1, $r2, $r3, *(unsigned int*)($sp), $lr
  continue
end

break *0x0207CA70
commands
  silent
  printf "CREATE_REC record=0x%x f34=0x%x f38=0x%x\n", $r4, *(unsigned int*)($r4+0x34), *(unsigned int*)($r4+0x38)
  continue
end

break *0x0207FAD4
commands
  silent
  printf "FLAG_0x9 rec=0x%x f34=0x%x f3c=0x%x r0=0x%x lr=0x%x\n", $r4, *(unsigned int*)($r4+0x34), *(unsigned int*)($r4+0x3c), $r0, $lr
  continue
end

break *0x0207FB0C
commands
  silent
  printf "FLAG_0x209 rec=0x%x f34=0x%x f3c=0x%x r0=0x%x lr=0x%x\n", $r4, *(unsigned int*)($r4+0x34), *(unsigned int*)($r4+0x3c), $r0, $lr
  continue
end

printf "PROBE_ARMED\n"
continue
