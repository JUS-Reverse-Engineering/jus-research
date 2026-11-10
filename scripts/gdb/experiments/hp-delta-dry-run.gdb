set pagination off
set confirm off
set logging file /tmp/jus-g3-hp-delta.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
printf "JUS_SESSION_BEGIN g3-hp-delta-dry-run\n"
target remote localhost:3333
break *0x02078488
set $jus_bp_hp_delta_apply = $bpnum
condition $bpnum ($r1 & 0x80000000) != 0
commands $bpnum
  silent
  printf "JUS_PROBE_HIT hp-delta-apply r1=0x%x lr=0x%x\n", $r1, $lr
  continue
end
disable $bpnum
define jus-arm-hp-delta-apply
  disable breakpoints
  enable $jus_bp_hp_delta_apply
  printf "JUS_PROBE_BEGIN hp-delta-apply\n"
end
define jus-disarm-hp-delta-apply
  disable $jus_bp_hp_delta_apply
  printf "JUS_PROBE_END hp-delta-apply\n"
end
printf "JUS_SESSION_READY g3-hp-delta-dry-run\n"
