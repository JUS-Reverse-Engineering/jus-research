set pagination off
set confirm off
set logging file /tmp/jus_emu/e2h3_gdb.log
set logging enabled on
target remote localhost:3333

# SP-apply entry: r0=slot, r1=amount
break *0x020781E4
commands
  silent
  printf "APPLY entry slot=%#x amount=%d lr=%#x  x=%#x m=%d c=%d flag=%d\n", $r0, (int)$r1, $lr, *(unsigned int*)0x21df730, *(signed char*)0x21df734, *(signed char*)0x21df735, *(signed char*)0x21df737
  continue
end

# affordability check entry: r0=slot, r1=amount
break *0x020782AC
commands
  silent
  printf "CHECK entry slot=%#x amount=%d lr=%#x  x=%#x m=%d c=%d flag=%d\n", $r0, (int)$r1, $lr, *(unsigned int*)0x21df730, *(signed char*)0x21df734, *(signed char*)0x21df735, *(signed char*)0x21df737
  continue
end

# tail c>=m check
break *0x02078290
commands
  silent
  printf "TAIL entry r0=%#x r1=%#x lr=%#x  x=%#x m=%d c=%d\n", $r0, $r1, $lr, *(unsigned int*)0x21df730, *(signed char*)0x21df734, *(signed char*)0x21df735
  continue
end

# bar-step H1 (borrow, negative path)
break *0x0207830C
commands
  silent
  printf "H1(borrow) entry r0=%#x r1=%#x lr=%#x  x=%#x m=%d c=%d\n", $r0, $r1, $lr, *(unsigned int*)0x21df730, *(signed char*)0x21df734, *(signed char*)0x21df735
  continue
end

# bar-step H2 (carry, positive path)
break *0x02078328
commands
  silent
  printf "H2(carry) entry r0=%#x r1=%#x lr=%#x  x=%#x m=%d c=%d\n", $r0, $r1, $lr, *(unsigned int*)0x21df730, *(signed char*)0x21df734, *(signed char*)0x21df735
  continue
end

echo BREAKPOINTS-ARMED\n
continue
