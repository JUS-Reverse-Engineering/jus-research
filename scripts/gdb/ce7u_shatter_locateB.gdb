set confirm off
set pagination off
set height 0
set width 0
handle SIGILL nostop noprint nopass
target remote localhost:3333
break *0x02081CC4
commands
silent
printf "BLKPAIR r4=%08x r5=%08x r4_14=%08x r4_20=%04x r4_24=%04x r4rec=%08x r5_14=%08x r5_20=%04x r5_24=%04x r5rec=%08x\n", $r4, $r5, *(unsigned int*)($r4+0x14), *(unsigned short*)($r4+0x20), *(unsigned short*)($r4+0x24), *(unsigned int*)($r4+0x10), *(unsigned int*)($r5+0x14), *(unsigned short*)($r5+0x20), *(unsigned short*)($r5+0x24), *(unsigned int*)($r5+0x10)
continue
end
continue
