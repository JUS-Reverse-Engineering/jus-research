# lxyt_kbrecord_dump2.gdb -- jus-lxyt second pass: B, down B, Y, down Y.
set pagination off
set confirm off
set logging file lxyt_kbrecord_dump2.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $lxyt_hits = 0

break *0x020817EC
commands
  silent
  set $lxyt_hits = $lxyt_hits + 1
  printf "HIT n=%d ptr=0x%x\n", $lxyt_hits, $r3
  x/20xb $r3
  if $lxyt_hits >= 6
    printf "DONE, detaching\n"
    detach
    quit
  end
  continue
end

continue
