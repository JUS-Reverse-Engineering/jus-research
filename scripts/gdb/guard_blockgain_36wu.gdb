# scripts/gdb/guard_blockgain_36wu.gdb (jus-36wu)
# Guard block-gain leg: does the SP deposit-writer/apply path change under
# the guard flag (M+0x78 bit 26, M=0x0220F494 fixed for this exact state
# per docs/confirmed-facts/guard-sp.md's own precedent measurement)?
set pagination off
set confirm off
set logging file /tmp/jus_emu/guard_blockgain_36wu_gdb.log
set logging enabled on
target remote localhost:3333

break *0x0215FCCC
commands
  silent
  printf "WRITE_6A state_block=%#x char=%#x src_5E=%#x guard_word=%#x guard_bit26=%d lr=%#x\n", \
    $r0, $r0-0x130, *(unsigned short*)($r0+0x5e), \
    *(unsigned int*)0x220f50c, (*(unsigned int*)0x220f50c >> 26) & 1, $lr
  continue
end

break *0x0215FCD8
commands
  silent
  printf "WRITE_6C state_block=%#x char=%#x src_60=%#x guard_word=%#x guard_bit26=%d lr=%#x\n", \
    $r0, $r0-0x130, *(unsigned short*)($r0+0x60), \
    *(unsigned int*)0x220f50c, (*(unsigned int*)0x220f50c >> 26) & 1, $lr
  continue
end

break *0x0215FCE4
commands
  silent
  printf "WRITE_64_CHECK state_block=%#x char=%#x idx=%d bit_set=%d guard_bit26=%d lr=%#x\n", \
    $r0, $r0-0x130, $r1, (*(unsigned int*)($r0+0xc) >> $r1) & 1, \
    (*(unsigned int*)0x220f50c >> 26) & 1, $lr
  continue
end

break *0x0215AC64
commands
  silent
  printf "NEG_DEBIT slot=%#x amount=%d guard_bit26=%d lr=%#x\n", \
    $r0, (int)$r1, (*(unsigned int*)0x220f50c >> 26) & 1, $lr
  continue
end

continue
