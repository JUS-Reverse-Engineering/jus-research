# scripts/gdb/deposit_writer_36wu.gdb (jus-36wu)
#
# Live confirmation of the SP deposit writers found static this session
# (0x0215FCCC/0x0215FCD8/0x0215FCE4, ov6), the ability 55/56 consumer
# (arm9 0x02077E3C inside 0x02077D40), and the negative-debit path
# (0x0215AC64). Reuses the field map and style of scripts/gdb/e2h3_sp_b.gdb
# (jus-e2h3) without editing that file.
#
# Register roles confirmed by static disasm this session:
#   0x0215FCCC (ov6): r0 = state block (char+0x130); writes r0+0x6A from r0+0x5E.
#   0x0215FCD8 (ov6): r0 = state block; writes r0+0x6C from r0+0x60.
#   0x0215FCE4 (ov6): r0 = state block, r1 = ability index; conditional on
#                      bit r1 of [r0+0xC]; writes r0+0x64 from r0+0x16+2*r1.
#   0x02077E3C (arm9): r0 = slot (arg1 of 0x02077D40), r1 = amount
#                      (s8[koma+0x4B] + s8[koma+0x4C]), r4 = koma pointer.
#   0x0215AC64 (ov6):  bl site inside the per-object tick function; r0 = slot
#                      ([r5+0x1B4]), r1 = amount (negative pending debit).
#
# One GDB attach per emulator launch (scripts/gdb/README.md).

set pagination off
set confirm off
set logging file /tmp/jus_emu/deposit_writer_36wu_gdb.log
set logging enabled on
target remote localhost:3333

# --- Deposit writer: +0x6A = copy of +0x5E ---------------------------------
break *0x0215FCCC
commands
  silent
  printf "WRITE_6A state_block=%#x char=%#x src_5E=%#x lr=%#x\n", \
    $r0, $r0-0x130, *(unsigned short*)($r0+0x5e), $lr
  continue
end

# --- Deposit writer: +0x6C = copy of +0x60 ---------------------------------
break *0x0215FCD8
commands
  silent
  printf "WRITE_6C state_block=%#x char=%#x src_60=%#x lr=%#x\n", \
    $r0, $r0-0x130, *(unsigned short*)($r0+0x60), $lr
  continue
end

# --- Deposit writer: +0x64 = table[idx] if bit idx of +0xC set -------------
break *0x0215FCE4
commands
  silent
  printf "WRITE_64_CHECK state_block=%#x char=%#x idx=%d mask=%#x bit_set=%d table_val=%#x lr=%#x\n", \
    $r0, $r0-0x130, $r1, *(unsigned int*)($r0+0xc), \
    (*(unsigned int*)($r0+0xc) >> $r1) & 1, \
    *(unsigned short*)($r0+0x16+2*$r1), $lr
  continue
end

# --- Ability 55/56 consumer: arm9 0x02077E3C, r0=slot r1=amount r4=koma ----
break *0x02077E3C
commands
  silent
  printf "ABILITY_5556_TICK slot=%#x amount=%d koma=%#x koma_4b=%d koma_4c=%d lr=%#x\n", \
    $r0, (int)$r1, $r4, *(signed char*)($r4+0x4b), *(signed char*)($r4+0x4c), $lr
  continue
end

# --- Negative-debit path: 0x0215AC64, r0=slot r1=amount --------------------
break *0x0215AC64
commands
  silent
  printf "NEG_DEBIT slot=%#x amount=%d lr=%#x\n", $r0, (int)$r1, $lr
  continue
end

continue
