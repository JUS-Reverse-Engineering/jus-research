set confirm off
set pagination off
set height 0
set width 0
handle SIGILL nostop noprint nopass
target remote localhost:3333

# Test 1 (down Y, Kakashi): the attacker hit element found by the locate
# pass at 0221A8F4 (this launch, ce7u-kakashi-guard state, downY plan).
# Clear bit 26 (0x04000000) of its +0x14 word BEFORE the collision driver
# runs the frame that connects the hit. Guard the write on the known
# unpatched signature (0x14001001) so an unrelated frame/slot reuse is
# never touched.
set $ce7u_hits480 = 0
break *0x0207F480
commands
silent
set $ce7u_hits480 = $ce7u_hits480 + 1
set $ce7u_v = *(unsigned int*)0x0221A908
if $ce7u_v == 0x14001001
  set *(unsigned int*)0x0221A908 = 0x10001001
  printf "DRIVER480 hit=%d elem14 BEFORE=%08x AFTER=%08x PATCHED\n", $ce7u_hits480, $ce7u_v, *(unsigned int*)0x0221A908
end
continue
end

break *0x02081D90
commands
silent
printf "PAIR ip=%08x r3=%08x defv14=%08x r2mask=%02x atk20=%04x atk24=%04x defrec=%08x atkrec=%08x atk14=%08x\n", $ip, $r3, *(unsigned int*)($ip+0x14), $r2, $r1, *(unsigned short*)($r3+0x24), *(unsigned int*)($ip+0x10), *(unsigned int*)($r3+0x10), *(unsigned int*)($r3+0x14)
continue
end

break *0x02081CC8
commands
silent
printf "BLOCKSTORE hit\n"
continue
end

break *0x0215EC64
commands
silent
printf "GAUGEADD ov6 hit\n"
continue
end

break *0x02081DC8
commands
silent
printf "SHATTERSTORE hit\n"
continue
end

continue
