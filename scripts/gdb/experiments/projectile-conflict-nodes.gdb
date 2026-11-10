set pagination off
set confirm off
set logging file /tmp/projectile-conflict-nodes.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

break *0x0207FB00
condition $bpnum $r4 == 0x02214D64 || $r4 == 0x02214EEC
commands
  silent
  printf "JUS_NODE rec=0x%x node=0x%x obj=0x%x b18=0x%x h0c=0x%x n2a=0x%x flags=0x%x\n", $r4, $r1, *(unsigned int*)($r1+8), $r0, *(unsigned short*)(*(unsigned int*)($r1+8)+0xc), *(unsigned char*)($r1+0x2a), *(unsigned int*)($r4+0x40)
  x/11wx $r1
  x/8wx *(unsigned int*)($r1+8)
  continue
end

break *0x0207FB0C
condition $bpnum $r4 == 0x02214D64 || $r4 == 0x02214EEC
commands
  silent
  printf "JUS_OR200 rec=0x%x node=0x%x obj=0x%x\n", $r4, $r1, *(unsigned int*)($r1+8)
  continue
end

printf "JUS_NODES_READY\n"
continue
