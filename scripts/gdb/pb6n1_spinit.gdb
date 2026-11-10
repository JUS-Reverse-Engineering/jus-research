# scripts/gdb/pb6n1_spinit.gdb (jus-pb6n.1)
#
# Catch the SP max-bar (`m`, slot+0x5CC) / current-bar (`c`, slot+0x5CD)
# initialiser live and dump the `+0x558` node-list walk it does to compute
# `m`. Static basis (no live confirmation until this probe runs):
# docs/research/findings/sp-initial-state-and-bonus-table-static.md §2/§3,
# disasm re-checked this session via
# `scripts/analysis/query.py disasm 0x02077610 200`.
#
# Function 0x02077610 (arm9), entry r0 = slot pointer (== [char+0x1B4],
# guard-sp.md §1.4). r0 is never reassigned in this function -- every
# breakpoint below can read the slot fields straight off r0 without
# tracking a separate register.
#
#   0x02077610  entry: zero +0x5CC/+0x5DD/+0x5DE/+0x5DF/+0x5E0..+0x5E2
#   0x02077640  ldr r8,[r0,#0x558]     -- head of the node list
#   0x02077644  cmp r8,#0; popeq        -- empty list -> m stays 0, return
#   0x02077690  LOOP TOP: r8 = the node this iteration
#                 classification = *(u8*)(*(u32*)(r8+0x34)+0xb) & 0xf
#                 weight-determinant = *(u8*)(r8+0x40)
#                 qualifies iff classification != 3 AND weight != 2
#                 +0x5CC gets +1 always when qualifying, +1 again
#                 (i.e. net +2) when weight == 0, clamped to 0x10 each time
#   0x02077758  ldr r8,[r8]             -- advance to next node (node+0x00)
#   0x02077764  pop {...,pc}            -- loop exit / function return;
#                 r0 (slot, unchanged) +0x5CC/+0x5CD hold the final m/c-input
#
# `node+0x41` is read as an id byte on a DIFFERENT loop over this SAME list
# later in this same function (0x020777AC, second walk, unrelated to m/c) --
# not proven to identify a node's koma/character on THIS loop. Logged here
# only as a labelled candidate per the ticket's ask ("whatever identifies
# the node's koma/character"), not as a confirmed id field.
#
# One GDB attach per emulator launch (scripts/gdb/README.md). Every command
# list ends in `continue` so the Lua bridge keeps driving frames.
#
# Logging setup (file/redirect/enabled) is the RUNNER's job, not this
# script's (scripts/analysis/cancel_run.py's `attach_commands()` pattern,
# reused by scripts/analysis/pb6n1_spinit_run.py) -- `set logging redirect
# on` must precede `set logging enabled on` or an unread stdout pipe wedges
# GDB in write() once probe traffic is high (cancel_run.py module
# docstring). This file only declares the breakpoints.

set pagination off
set confirm off
set logging overwrite off
handle SIGILL stop nopass noprint
target remote localhost:3333

set $pb6n1_call = 0
set $pb6n1_node = 0
set $pb6n1_framectr = 0

# --- entry: log which call this is, the slot pointer, and the caller ------
break *0x02077610
commands
  silent
  set $pb6n1_call = $pb6n1_call + 1
  set $pb6n1_node = 0
  printf "SPINIT call=%d entry slot=%#x lr=%#x m_before=%d c_before=%d\n", \
    $pb6n1_call, $r0, $lr, \
    *(signed char*)($r0+0x5cc), *(signed char*)($r0+0x5cd)
  continue
end

# --- empty-list early return (m stays 0) -----------------------------------
# NOTE: 0x02077648 is the `popeq {...,pc}` itself (0x02077644 is the
# preceding `cmp r8,#0`) -- PC reaches this address on EVERY call regardless
# of whether the list is empty (the `eq` condition only gates whether the
# pop actually executes; the instruction fetch/breakpoint hit happens
# either way). Guard on r8 (the list head, still valid here) so this only
# fires on a genuinely empty list, not on every call (jus-pb6n.1 Refuter
# fix: without this guard EMPTY-LIST fired 96/96 on non-empty lists too).
break *0x02077648
commands
  silent
  if $r8 == 0
    printf "SPINIT call=%d EMPTY-LIST slot=%#x\n", $pb6n1_call, $r0
  end
  continue
end

# --- per-node: loop top, r8 = this iteration's node ------------------------
break *0x02077690
commands
  silent
  set $pb6n1_node = $pb6n1_node + 1
  printf "SPINIT call=%d node#%d ptr=%#x class_raw=%#x class_nibble=%d weight40=%d id41_candidate=%d\n", \
    $pb6n1_call, $pb6n1_node, $r8, \
    *(unsigned char*)(*(unsigned int*)($r8+0x34)+0xb), \
    (*(unsigned char*)(*(unsigned int*)($r8+0x34)+0xb)) & 0xf, \
    *(unsigned char*)($r8+0x40), \
    *(unsigned char*)($r8+0x41)
  continue
end

# --- function exit: resulting m/c after the whole walk ---------------------
break *0x02077764
commands
  silent
  printf "SPINIT call=%d RESULT slot=%#x nodes_seen=%d m=%d c=%d\n", \
    $pb6n1_call, $r0, $pb6n1_node, \
    *(signed char*)($r0+0x5cc), *(signed char*)($r0+0x5cd)
  continue
end

# --- frame marker: collision-driver entry, fires ~once per emulated frame --
# (per scripts/gdb/e2h3_sp_b.gdb precedent; the 0x0207FAD4 convention from
# other campaigns is control-record-specific and does not apply here).
break *0x0207F480
commands
  silent
  set $pb6n1_framectr = $pb6n1_framectr + 1
  printf "FRAME #%d\n", $pb6n1_framectr
  continue
end
