set pagination off
set confirm off
set logging file /tmp/projectile-conflict-despawn.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

break *0x0216c958
commands
  silent
  printf "JUS_DESPAWN_HIT c958 r0=0x%x r1=0x%x r4=0x%x lr=0x%x\n", $r0, $r1, $r4, $lr
  x/10wx 0x0220cf28
  x/3wx 0x02214da0
  continue
end

break *0x0216e1c0
commands
  silent
  printf "JUS_DESPAWN_HIT e1c0 r0=0x%x r1=0x%x r4=0x%x lr=0x%x\n", $r0, $r1, $r4, $lr
  x/10wx 0x0220cf28
  x/3wx 0x02214da0
  continue
end

break *0x0216f398
commands
  silent
  printf "JUS_DESPAWN_HIT f398 r0=0x%x r1=0x%x r4=0x%x lr=0x%x\n", $r0, $r1, $r4, $lr
  x/10wx 0x0220cf28
  x/3wx 0x02214da0
  continue
end

break *0x02083648
commands
  silent
  printf "JUS_DESTRUCTOR_HIT r0=0x%x r1=0x%x r4=0x%x lr=0x%x\n", $r0, $r1, $r4, $lr
  x/10wx 0x0220cf28
  x/3wx 0x02214da0
  continue
end

break *0x0216f99c
commands
  silent
  printf "JUS_WRAPPER_HIT r0=0x%x r4=0x%x lr=0x%x\n", $r0, $r4, $lr
  x/3wx 0x02214da0
  continue
end

printf "JUS_DESPAWN_READY\n"
