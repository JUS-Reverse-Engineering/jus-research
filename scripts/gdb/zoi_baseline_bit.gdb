# Static-memory baseline probe for jus-8zoi.
#
# Question: at the paused baseline frame (before any unpause), is
# participant-object +0x18 bit 2 already set for the nodes' objects tied to
# a state's in-use records? This is NOT a breakpoint trace -- target remote
# halts the CPU on attach, and that halted moment IS the measurement. No
# breakpoints are set here.
#
# Record/node/object layout per
# docs/research/feel-captures/projectile-conflict-2026-09-10/nodes/RESULTS.md:
# node struct 0x2C bytes, node+0x00 = next pointer, node+0x08 = object
# pointer, node+0x0C = owning record pointer, node+0x10 = entry pointer,
# node+0x18 = flags word. record+0x08 = head of the node list (walk
# node+0x00 for next, cap 16 iterations, self-loop guarded). Object fields
# read here: +0x18 (byte, bit 2 is the question) and the raw words
# +0x00..+0x20 (9 words, stride 4) for context.
#
# Label note (jus-8zoi, 2026-09-11): the bit of interest is value 0x2
# (bit index 1, ($zoi_o18 >> 1) & 1), not bit index 2 (value 0x4). Earlier
# committed logs from this script were taken with the wrong shift
# (($zoi_o18 >> 2) & 1) under the label `obj18_bit2` -- those logs are
# unaffected in substance because `zoi_baseline_bit.md` restates the
# results by value (`0x2`) computed from the logged `obj18=` byte, not by
# trusting the old bit-index label. This script now prints the correct
# shift under the label `obj18_bit0x2`.
#
# zoi_dump_record <record_addr> <record_idx> prints record+0x34/+0x38/+0x3C/
# +0x40, then every node in that record's node list with node+0x18, the
# node's object pointer, and (when the object pointer looks like a main-RAM
# address) object+0x18 plus the 9 raw words. Offsets and raw hex/decimal
# values only, no gameplay naming, matching the cited RESULTS.md style.
#
# Usage: this file is the initial -x script for one GDB attach. It defines
# zoi_dump_record, connects, dumps the baseline for whatever records the
# caller lists below, then issues a top-level `continue` (required -- a
# script that ends on a halted CPU freezes the emulator, see
# scripts/gdb/README.md's "Emulator silently freezes" hazard). Naruto-session
# follow-up dumps (+1 frame, +2 frames) are driven by injecting further
# `zoi_dump_record ...` calls (the definition persists for the GDB session)
# through a kept-open stdin fifo after a SIGINT-interrupt of `continue`,
# exactly as described in docs/research/feel-captures/projectile-conflict-2026-09-11/
# pc-naruto-fy-npc-yusuke-fy/zoi_baseline_bit.md's conditions block.

set pagination off
set confirm off
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint

define zoi_dump_record
  set $zoi_addr = $arg0
  set $zoi_idx  = $arg1
  printf "RECORD idx=%d addr=0x%x f34=0x%x f38=0x%x f3c=0x%x f40=0x%x\n", $zoi_idx, $zoi_addr, *(unsigned int*)($zoi_addr+0x34), *(unsigned int*)($zoi_addr+0x38), *(unsigned int*)($zoi_addr+0x3c), *(unsigned int*)($zoi_addr+0x40)
  set $zoi_node = *(unsigned int*)($zoi_addr+0x08)
  set $zoi_head = $zoi_node
  set $zoi_i = 0
  while $zoi_node != 0 && $zoi_i < 16
    set $zoi_obj = *(unsigned int*)($zoi_node+0x08)
    set $zoi_n18 = *(unsigned int*)($zoi_node+0x18)
    printf "  NODE idx=%d i=%d addr=0x%x n18=0x%x obj=0x%x", $zoi_idx, $zoi_i, $zoi_node, $zoi_n18, $zoi_obj
    if $zoi_obj != 0 && $zoi_obj >= 0x02000000 && $zoi_obj < 0x02400000
      set $zoi_o18 = *(unsigned char*)($zoi_obj+0x18)
      printf " obj18=0x%x obj18_bit0x2=%d\n", $zoi_o18, ($zoi_o18 >> 1) & 1
      set $zoi_w = 0
      while $zoi_w <= 0x20
        printf "    OBJWORD idx=%d node_i=%d off=0x%02x val=0x%x\n", $zoi_idx, $zoi_i, $zoi_w, *(unsigned int*)($zoi_obj+$zoi_w)
        set $zoi_w = $zoi_w + 4
      end
    else
      printf " obj18=NA\n"
    end
    set $zoi_next = *(unsigned int*)($zoi_node+0x00)
    if $zoi_next == $zoi_node || $zoi_next == $zoi_head
      set $zoi_node = 0
    else
      set $zoi_node = $zoi_next
    end
    set $zoi_i = $zoi_i + 1
  end
end

target remote localhost:3333

# Union of every record index either capture in
# docs/research/feel-captures/projectile-conflict-2026-09-11/ needs: 11/12
# (shared reference, both states), 49/50/51/52 (pc-naruto-fy-npc-yusuke-fy),
# 70 (pc-momotaro-npc-yusuke-projectiles-about-to-collide control). Dumping
# the full union in every session is harmless -- these are static manager-
# array slots that exist regardless of which savestate is loaded -- and lets
# one script serve both sessions without a templating step.
printf "=== STAGE=baseline ===\n"
zoi_dump_record 0x0220F30C 11
zoi_dump_record 0x0220F494 12
zoi_dump_record 0x02212D3C 49
zoi_dump_record 0x02212EC4 50
zoi_dump_record 0x0221304C 51
zoi_dump_record 0x022131D4 52
zoi_dump_record 0x02214D64 70
printf "=== STAGE_DONE=baseline ===\n"

continue
