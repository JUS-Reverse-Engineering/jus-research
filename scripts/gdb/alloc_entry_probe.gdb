# Collision-node allocator probe (tracker item jus-b9sb)
#
# Watches the allocator at 0x0207D440: the hitbox id read, the entry-pointer
# store on both id paths, and node +0x18 at the function's return.
#
# Addresses verified against jus_files/arm9/arm9.bin (capstone, base 0x02000000):
#   0x0207D4A8  ldrh r3, [r6, #0xe]      id read           (r4=record, r5=node, r6=ColWork)
#   0x0207D4D4  str  r0, [r5, #0x10]     id >= 0x100 store; 0x0207D4D8 is the next insn
#   0x0207D57C  str  r0, [r5, #0x10]     id <  0x100 store; 0x0207D580 is the next insn
#   0x0207D834  pop  {r3,r4,r5,r6,r7,pc} the only non-early return; r0 = r5 = node here
#
# Log lands in the *current directory* as alloc_probe.log, so run with -cd:
#   arm-none-eabi-gdb -batch -cd <outdir> -x scripts/gdb/alloc_entry_probe.gdb
# One attach per emulator launch; load the savestate before attaching.

set pagination off
set confirm off
set logging file alloc_probe.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint

target remote localhost:3333

# id read, before the branch on 0x100
break *0x0207D4A8
commands
  silent
  printf "ALLOC_ID id=0x%x record=0x%x node=0x%x colwork=0x%x\n", *(unsigned short*)($r6+0xe), $r4, $r5, $r6
  continue
end

# authored path (id >= 0x100): entry pointer already stored at node +0x10
break *0x0207D4D8
commands
  silent
  printf "ALLOC_ENTRY_AUTHORED node=0x%x entry=0x%x entry08=0x%x\n", $r5, *(unsigned int*)($r5+0x10), *(unsigned int*)(*(unsigned int*)($r5+0x10)+8)
  continue
end

# builtin path (id < 0x100): entry pointer already stored at node +0x10
break *0x0207D580
commands
  silent
  printf "ALLOC_ENTRY_BUILTIN node=0x%x entry=0x%x\n", $r5, *(unsigned int*)($r5+0x10)
  continue
end

# return: node +0x18 in its final allocation-time value
break *0x0207D834
commands
  silent
  printf "ALLOC_DONE node=0x%x node18=0x%x\n", $r5, *(unsigned int*)($r5+0x18)
  continue
end

printf "PROBE_ARMED\n"
continue
