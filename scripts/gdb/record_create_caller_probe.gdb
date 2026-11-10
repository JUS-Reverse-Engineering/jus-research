# Record-create caller probe (tracker item jus-8bjc)
#
# Every record creation in the first probe came through the wrapper at
# 0x020834D4 (its `bl 0x0207C988` is at 0x02083560). The wrapper passes its own
# r2/r3 through unchanged (mov r7,r2 / mov r6,r3 in the prologue; mov r2,r7 /
# mov r3,r6 before the call). This probe logs the wrapper's arguments and its
# return address so the +0x38 seed can be traced one level further up.
# Log lands in the current directory as record_create_caller.log; run with -cd.
set pagination off
set confirm off
set logging file record_create_caller.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333
break *0x020834D4
commands
  silent
  printf "WRAP ctor=0x%x r1=0x%x arg34=0x%x arg38=0x%x sp20=0x%x sp24=0x%x lr=0x%x\n", $r0, $r1, $r2, $r3, *(unsigned int*)($sp), *(unsigned int*)($sp+4), $lr
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
