# Record-create probe (tracker item jus-8bjc)
#
# Breaks at the entry of the ColPrm record-create routine 0x0207C988 and logs
# its arguments. Verified against jus_files/arm9/arm9.bin (capstone, base
# 0x02000000): the prologue copies r1->r8, r2->r7, r3->r6, [sp+0x30]->r5, and
# later stores r7 to record+0x34 (0x0207CA64), r6 to record+0x38 (0x0207CA6C),
# r5-derived word to record+0x3C (0x0207CA7C). So r2 = +0x34 seed, r3 = +0x38 seed.
# Also logs the record pointer at the +0x38 store so rows can be joined to the
# census record index ((rec - 0x0220E234) / 0x188).
#
# Log lands in the current directory as record_create.log; run with -cd.
set pagination off
set confirm off
set logging file record_create.log
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
printf "PROBE_ARMED\n"
continue
