# lxyt_kbrecord_dump.gdb -- jus-lxyt verification pass.
# Dumps the full 20 bytes at the moveData pointer (r3 at 0x020817EC) for the
# first two HITPROC calls, then detaches (not kill -9) so the emulator keeps
# running and a later `jusemu.py peek` can independently re-read the same
# address through the Lua bridge -- a cross-instrument check on the GDB
# printf byte reads from lxyt_kbrecord.gdb's first pass.

set pagination off
set confirm off
set logging file lxyt_kbrecord_dump.log
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
  if $lxyt_hits >= 4
    printf "DONE, detaching\n"
    detach
    quit
  end
  continue
end

continue
