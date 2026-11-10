# kit_hit_probe.gdb -- the contact probe for kit hit trials (J2'a).
#
# Records, for every contact of a hit trial, what the per-contact claim
# `<move>_hit_record_<j>` (scripts/kit/hit_records.py) needs:
#   - the moveData (record) pointer, and the authored base it is relative to,
#     so a reader can compute  rec = (pointer - base) / 20  with no static
#     lookup: base = [[ColPrm record + 0x6C] + 0x0C], the ColPrm record is
#     [node + 0x0C] and the node is r6 (arm9 0x0207D440; move_records.py
#     header; projectile_census.read_authored_base reads the same chain);
#   - the 20 record bytes and the node's 11 words (its id word is a second
#     read of rec + 0x100);
#   - the contact count per frame: `n` is the 1-based order of this contact
#     within one global frame counter value, so two contacts on one frame
#     print n=1 and n=2;
#   - the victim's staged pair, M+0x148 / M+0x14A, after this contact;
#   - the M+0x16C latch (arm9 0x020815F8 max-latches moveData[+1] into it,
#     before this break, and 0x02051864 clears it every frame; this is the
#     value the reaction handler keys on, not a frame count).
#
# It is a drop-in for plans/c4_contacts.gdb in a driver's `arm-none-eabi-gdb
# -q -nx -ex "set logging file LOG" -ex "set logging redirect on" -x ...`
# launch: same GDB-stub attach, same HIT/MD/EL/MSTAGE line shapes (the c1/c4
# logs under docs/research/feel-captures/ parse unchanged), plus the fields
# above. The block path is left out: no kit trial blocks.
#
# Registers (arm9 0x020817E8..0x02081978, the hit processor):
#   r3  moveData pointer, just loaded at 0x020817E8 (valid at the 0x020817EC
#       break; clobbered by 0x020817F4)
#   r6  the hit node (node+0x0C ColPrm record, node+0x10 moveData)
#   r8  the victim's M + 0xA4  (the staged stores are strh [r8,#0xa4] and
#       [r8,#0xa6]; the latch is ldrh [r8,#0xc8])
# GDB breakpoints stop BEFORE the addressed instruction executes. At 0x02081978
# (strh r0,[r8,#0xa6]) the X half of the staged pair is already stored and r0
# holds the Y half about to be stored, so the line reads x from memory and y
# from r0. Each frame stamp is the battle frame counter 0x020A0F10, the word
# the Lua `gfc` watch reads, so these lines join Lua rows by gfc.

set pagination off
set confirm off
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $kit_prev_gfc = -1
set $kit_n = 0

break *0x020817EC
commands
  silent
  set $kit_gfc = *(unsigned int*)0x020A0F10
  if $kit_gfc == $kit_prev_gfc
    set $kit_n = $kit_n + 1
  else
    set $kit_n = 1
    set $kit_prev_gfc = $kit_gfc
  end
  set $kit_base = 0
  set $kit_colprm = *(unsigned int*)($r6+0x0c)
  if $kit_colprm != 0
    set $kit_table = *(unsigned int*)($kit_colprm+0x6c)
    if $kit_table != 0
      set $kit_base = *(unsigned int*)($kit_table+0x0c)
    end
  end
  printf "HIT gfc=%d n=%d md=0x%08x base=0x%08x h16c=%d r5=0x%08x r6=0x%08x r7=0x%08x r8=0x%08x r9=0x%08x r10=0x%08x lr=0x%08x\n", $kit_gfc, $kit_n, $r3, $kit_base, *(unsigned short*)($r8+0xc8), $r5, $r6, $r7, $r8, $r9, $r10, $lr
  printf "MD "
  x/20xb $r3
  printf "EL "
  x/11xw $r6
  continue
end

break *0x0208182C
commands
  silent
  printf "MSTAGE gfc=%d M=%d xproduct=%d\n", *(unsigned int*)0x020A0F10, $r1, $r3
  continue
end

break *0x02081978
commands
  silent
  printf "STAGE gfc=%d M=0x%08x x=%d y=%d\n", *(unsigned int*)0x020A0F10, $r8-0xa4, *(short*)($r8+0xa4), (short)$r0
  continue
end

printf "PROBE_ARMED\n"
continue
