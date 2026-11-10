# scripts/gdb/ability5556_36wu.gdb (jus-36wu)
# Ability 55/56 tick live check on pc-momotaro-npc-nami-dark-tournament
# (chr_b 67 Momotaro, ability-56 carrier, confirmed active P1 per
# docs/research/feel-captures/sp-live-2026-09-12/pc-momotaro-npc-nami-dark-tournament/RESULTS.md).
set pagination off
set confirm off
set logging file /tmp/jus_emu/deposit_writer_36wu_momo_gdb.log
set logging enabled on
target remote localhost:3333

break *0x02077D40 if (*(signed char*)($r1+0x4b) != 0) || (*(signed char*)($r1+0x4c) != 0)
commands
  silent
  printf "TICK_ENTRY_NONZERO_ABILITY slot=%#x koma=%#x koma_3c=%#x koma_4b=%d koma_4c=%d lr=%#x\n", \
    $r0, $r1, *(unsigned int*)($r1+0x3c), *(signed char*)($r1+0x4b), *(signed char*)($r1+0x4c), $lr
  continue
end

break *0x02077E3C
commands
  silent
  printf "ABILITY_5556_TICK_FIRED slot=%#x amount=%d koma=%#x koma_4b=%d koma_4c=%d lr=%#x\n", \
    $r0, (int)$r1, $r4, *(signed char*)($r4+0x4b), *(signed char*)($r4+0x4c), $lr
  continue
end

break *0x0215AC64
commands
  silent
  printf "NEG_DEBIT slot=%#x amount=%d lr=%#x\n", $r0, (int)$r1, $lr
  continue
end

continue
