# Minimal frame-marker probe for jus-8zoi ("who else sets object+0x18
# bit 2 for rec49/rec50's objects").
#
# The bit-0x2 writer already confirmed for the momotaro/yusuke control
# (docs/research/feel-captures/projectile-conflict-2026-09-10/b18-writer/RESULTS.md)
# is strb r0,[r1,#0x18] at 0x02080C18. A prior GDB census on the
# pc-naruto-fy-npc-yusuke-fy state (zoi_contact_naruto.log, breakpoint at
# that same address) recorded zero PAIR_STORE hits across the run window --
# that writer never executed here. This script does not re-probe
# 0x02080C18; it only supplies frame alignment for a companion JUS_WATCH
# session (scripts/emu/README.md patch 5) armed on the participant-object
# +0x18 bytes themselves, so whichever *other* instruction touches those
# bytes is caught by the watch hook (reports pc = store instruction + 8)
# and this log's frame markers say which frame each watch hit landed in.
#
# Two breakpoints, per the task brief:
# - 0x0207FAD4 (the "0x8 -> 0x9" flag store), conditioned to the fixed
#   per-frame heartbeat record used elsewhere in this campaign
#   (rec=0x0220E234, see scripts/gdb/zoi_contact_probe.gdb's comment: "the
#   control's baseline record hits this breakpoint once per frame") --
#   fires once per frame regardless of state, so it doubles as a frame
#   counter/marker with no per-record decoding.
# - 0x0207FB0C (the "0x9 -> 0x209" flag store) for rec49 (0x02212D3C) and
#   rec50 (0x02212EC4) specifically, so the log shows which frame each
#   record's flag word actually flipped to 0x209 -- the frame the object
#   bit must already be set by, whatever wrote it.
#
# No object/node dumping here (kept deliberately minimal per the brief);
# the object-level detail comes from the JUS_WATCH log's own pc/val fields
# and the post-hoc disassembly, not from this GDB session.

set pagination off
set confirm off
set logging file zoi_obj18_writer.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $zoi_frame = 0

break *0x0207FAD4
condition $bpnum $r4 == 0x220e234
commands
  silent
  set $zoi_frame = $zoi_frame + 1
  printf "FRAME_MARKER n=%d\n", $zoi_frame
  continue
end

break *0x0207FB0C
condition $bpnum $r4 == 0x2212d3c || $r4 == 0x2212ec4
# jus-8zoi note: hardcoded to rec49/rec50. To reuse this script on the
# momotaro/yusuke control (rec70 = 0x02214d64) and get FLAG_0x209 frame
# alignment in that run's own log, extend the condition, e.g.:
#   condition $bpnum $r4 == 0x2212d3c || $r4 == 0x2212ec4 || $r4 == 0x2214d64
commands
  silent
  printf "FLAG_0x209 rec=0x%x r0=0x%x lr=0x%x frame_marker=%d\n", $r4, $r0, $lr, $zoi_frame
  continue
end

printf "PROBE_ARMED\n"
continue
