# Live kind-byte + despawn-site probe for jus-68cu.
#
# Follows up docs/research/findings/entity-kind-table-static.md and
# docs/research/feel-captures/entity-kinds-2026-09-12/RESULTS.md, which read
# all 27 ObjShot kind handlers statically but found no call-graph edge from
# any handler to any of the three despawn candidates
# (0x0216C958/0x0216E1C0/0x0216F398, docs/confirmed-facts/entities.md §7).
# This probe closes that gap live: it breaks at ObjShot element creation and
# at the entry of all three despawn candidates, logging the kind byte
# (elem+0x1A) and lifetime half (elem+0x18) at each hit, plus the shared
# destructor 0x02083648 (arm9) as a best-effort teardown-confirmation signal.
#
# Register conventions (confirmed by disassembly this session, not assumed):
#   - Creation dispatch call site 0x0216ADD8 (inside the ObjShot initializer
#     0x0216ACC8, entities.md §5.2): at this PC (break-before semantics --
#     the instruction at the breakpoint address has NOT executed yet), r0 =
#     element (already loaded by the preceding `mov r0,r8` at 0x0216ADD4),
#     r2 = kind byte (already loaded by `ldrb r2,[r8,#0x1a]` at 0x0216ADD0),
#     r7 = owner (set by the caller before this function ran; the `mov
#     r1,r7` that would overwrite r1 with it has not executed yet, so r1 at
#     this exact PC is the dispatch table base, NOT the owner -- use r7).
#     Lifetime is already stored at elem+0x18 by this point -- the store is
#     `strh r0,[r8,#0x18]` at 0x0216ADA8 (kind byte is stored two
#     instructions earlier, `strb r1,[r8,#0x1a]` at 0x0216AD88; 0x0216ADCC is
#     a *different* store, `str r0,[r8,#0x1c]`, the conditional payload
#     field, not the lifetime).
#   - All three despawn candidates take the element pointer in r0 AT ENTRY
#     (confirmed by reading each prologue: 0x0216C958 does `mov r8,r0`,
#     0x0216E1C0 does `mov r5,r0`, 0x0216F398 does `mov r7,r0` -- all copy
#     the r0 argument, so breaking at the function's first instruction and
#     reading r0 directly gives the element pointer in every case, before
#     any of those movs execute).
#   - 0x02083648 (arm9) is the shared pooled-entity destructor cited in
#     momotaro-yusuke-projectile-conflict.md ("the wrapper called the common
#     destructor 0x02083648") and is also called directly from inside
#     0x0216C958's own body (confirmed via `query.py callees 0x0216C958`).
#     Its r0 argument is NOT guaranteed to equal the ObjShot element in
#     every caller (0x0216C958 passes `*(r7)` where r7 is its own second
#     argument, not the element) -- this probe logs it as a raw heuristic
#     signal (site-agnostic "a teardown happened here, with this lr/r0"),
#     not as a confirmed per-kind despawn attribution. Cross-reference by
#     log line order against the despawn-candidate hits, same method
#     momotaro-yusuke-projectile-conflict.md used (three-way census +
#     separate teardown trace), not a claim that r0 here is the element.
#
# Frame counter: no live RAM frame counter is confirmed anywhere in this
# repo (same limitation flp3_creation_probe.gdb documents at length --
# projectile_census.py/projectile_replay.py's emu.framecount() is a Lua
# bridge call GDB cannot read) and this log carries no framecount marker of
# any kind. This probe prints a monotonic per-breakpoint sequence number
# ($e68cu_seq) and relies on GDB log line order for ordering only.
# "Frames alive"/"checks" in any writeup built from this log is a COUNT OF
# DESPAWN-CHECK HITS at the site that tore the element down (the CREATE
# line itself is excluded from that count), which is a frame count only to
# the extent the checked updater (0x0216F398/0x0216E1C0/0x0216C958) runs
# exactly once per rendered frame -- that per-frame-once assumption is not
# independently confirmed here and must be stated as an assumption, not a
# fact, in any writeup. There is no "+1 destroy frame" to add on top of the
# check count -- the destructor fires on its own log line (DESTRUCT_FIRE),
# not as an extra despawn-check hit, so it is not part of this count.
#
# One probe script, reused across every state -- no per-state edits needed.

set pagination off
set confirm off
set logging file e68cu_kind_despawn.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $e68cu_seq = 0

break *0x0216ADD8
commands
  silent
  set $e68cu_seq = $e68cu_seq + 1
  set $elem = $r0
  set $kind = $r2 & 0xff
  set $owner = $r7
  set $lifetime = *(short*)($elem+0x18)
  printf "CREATE seq=%d elem=0x%x kind=0x%02x lifetime=%d owner=0x%x\n", $e68cu_seq, $elem, $kind, $lifetime, $owner
  continue
end

break *0x0216C958
commands
  silent
  set $e68cu_seq = $e68cu_seq + 1
  set $elem = $r0
  set $kind = *(unsigned char*)($elem+0x1a)
  set $lifetime = *(short*)($elem+0x18)
  printf "DESPAWN_CHECK seq=%d site=0x0216C958 elem=0x%x kind=0x%02x lifetime=%d\n", $e68cu_seq, $elem, $kind, $lifetime
  continue
end

break *0x0216E1C0
commands
  silent
  set $e68cu_seq = $e68cu_seq + 1
  set $elem = $r0
  set $kind = *(unsigned char*)($elem+0x1a)
  set $lifetime = *(short*)($elem+0x18)
  printf "DESPAWN_CHECK seq=%d site=0x0216E1C0 elem=0x%x kind=0x%02x lifetime=%d\n", $e68cu_seq, $elem, $kind, $lifetime
  continue
end

break *0x0216F398
commands
  silent
  set $e68cu_seq = $e68cu_seq + 1
  set $elem = $r0
  set $kind = *(unsigned char*)($elem+0x1a)
  set $lifetime = *(short*)($elem+0x18)
  printf "DESPAWN_CHECK seq=%d site=0x0216F398 elem=0x%x kind=0x%02x lifetime=%d\n", $e68cu_seq, $elem, $kind, $lifetime
  continue
end

break *0x02083648
commands
  silent
  set $e68cu_seq = $e68cu_seq + 1
  printf "DESTRUCT_FIRE seq=%d arg0=0x%x lr=0x%x\n", $e68cu_seq, $r0, $lr
  continue
end

printf "PROBE_ARMED\n"
continue
