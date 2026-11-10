set pagination off
set confirm off
set logging file /tmp/projectile-conflict-b18-writer.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

# 0x02080C18: strb r0, [r1, #0x18] -- executes right after "orr r0, r0, #2"
# at 0x02080C14, inside function 0x020809C8. r1 comes from [r6+8] (a
# list-node-like structure), matching the object at 0x023a5bf8 whose
# +0x18 byte gains bit 0x2 here.
break *0x02080C18
commands
  silent
  printf "B18_BIT2_WRITE r0=0x%x r1=0x%x r2=0x%x r3=0x%x r4=0x%x r5=0x%x r6=0x%x r7=0x%x lr=0x%x sp=0x%x\n", $r0, $r1, $r2, $r3, $r4, $r5, $r6, $r7, $lr, $sp
  x/8wx $r1
  continue
end

printf "B18_WRITER_READY\n"
continue
