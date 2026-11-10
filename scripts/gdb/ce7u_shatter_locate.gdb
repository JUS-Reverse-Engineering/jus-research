set confirm off
set pagination off
set height 0
set width 0
handle SIGILL nostop noprint nopass
target remote localhost:3333
break *0x02081D90
commands
silent
printf "PAIR ip=%08x r3=%08x defv14=%08x r2mask=%02x atk20=%04x atk24=%04x defrec=%08x atkrec=%08x atk14=%08x\n", $ip, $r3, *(unsigned int*)($ip+0x14), $r2, $r1, *(unsigned short*)($r3+0x24), *(unsigned int*)($ip+0x10), *(unsigned int*)($r3+0x10), *(unsigned int*)($r3+0x14)
continue
end
continue
