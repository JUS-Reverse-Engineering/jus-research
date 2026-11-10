# e4tok_order.gdb -- jus-entity-frame-placement-4tok.
#
# Measures the per-frame call ORDER of seven documented per-frame routines by
# breaking on each routine's ENTRY and printing a tag + a monotonically
# increasing global hit counter. A second, per-frame-local counter resets at
# the frame marker so repeated hits within one frame (once per element, once
# per record, etc.) are visible without re-deriving order from the global
# counter alone.
#
# Frame marker: entry to the collision driver 0x0207F480 (arm9, size=1736,
# callers=0 in functions.json -- reached only through the generic per-frame
# task list registered via 0x02028384, same mechanism confirmed for the
# fighter per-frame task 0x02156DDC). collision.md §5 places this driver in
# phase 2 ("Hit events") and states it runs once per frame. No VBlank/main-
# loop frame-advance routine is documented anywhere in confirmed-facts or
# other docs (checked physics.md, collision.md, the engine notes, the combat notes) --
# this driver entry is used INSTEAD, per the brief's "better: main loop's
# frame-advance routine if documented; state which you used" fallback
# clause. This makes phase-2 tag HIT_EVENTS double as the frame boundary:
# HIT_EVENTS's own hit count IS the frame number.
#
# Anchors used (static basis, all from docs read this session):
#   HIT_EVENTS   0x0207F480  collision driver entry, collision.md §5,
#                            registered on manager +0xE0; literal_load at
#                            0x0207C5E8 feeds a branch to 0x02028384 at
#                            0x0207C5F0 (task-list registration).
#   FIGHTER_UPD  0x0215A978  ov6 per-frame fighter update, physics.md §4.5
#                            ("per-frame fighter update ... called from ov6
#                            0x02156EB0" and guard-sp.md §0.5 stage 3).
#                            Confirmed live in this session: it is called
#                            from inside the fighter per-frame task
#                            0x02156DDC at 0x02156EB0 (r1=0) and again at
#                            0x02156F64 (r1=1, a different sub-path of the
#                            same task).
#   STATE_COMMIT 0x02159CC4  ov6 generic state-machine commit (obj+0x18 <-
#                            obj+0x19), physics.md §4.5. Confirmed live:
#                            called from 0x02156DDC at 0x02156EC0, AFTER
#                            both FIGHTER_UPD (0x02156EB0) and GUARD_DRAIN
#                            (0x02156EB8) in that same task's instruction
#                            order.
#   GUARD_DRAIN  0x0215EF24  ov6 guard-gauge drain (`if (g>0) g--`),
#                            guard-sp.md §0.5 rule 5, "called every frame
#                            from 0x02156EB8". Confirmed live: called from
#                            0x02156DDC at 0x02156EB8, between FIGHTER_UPD
#                            and STATE_COMMIT.
#   INTEGRATOR   0x02082E10  arm9 per-element integrator, physics.md §6.1.
#   OBJSHOT      0x0216AF04  ObjShot per-frame entry, entities.md §5.1,
#                            registered via 0x02028384 (same task-list
#                            mechanism as HIT_EVENTS and the fighter task).
#   REGEN_TICK   0x02077D40  bench regen tick, damage.md §8.
#
# Static expectation from the fighter task's own instruction order (this
# session's disasm of 0x02156DDC, one fighter's per-frame slice):
#   FIGHTER_UPD -> GUARD_DRAIN -> STATE_COMMIT
# i.e. the state commit that publishes obj+0x18 happens AFTER the guard
# drain within the SAME fighter-task call, contradicting the engine notes' current
# row-3 prose order ("state commit" listed as part of "fighter update"
# without an explicit guard-drain interleave). This probe measures where
# HIT_EVENTS, INTEGRATOR, OBJSHOT and REGEN_TICK fall relative to that
# 3-step sequence and to each other, across frames.
#
# Not anchored (no static address found in confirmed-facts docs
# after checking physics.md, guard-sp.md, entities.md, collision.md,
# damage.md, the combat notes, the engine notes): input sample, status-node countdown.
# Not probed here; reported as TBD in the finding.

set pagination off
set confirm off
set logging file e4tok_order.log
set logging overwrite on
set logging enabled on
handle SIGILL stop nopass noprint
target remote localhost:3333

set $e4tok_hits = 0
set $e4tok_frame = 0
set $e4tok_local = 0

break *0x0207F480
commands
  silent
  set $e4tok_hits = $e4tok_hits + 1
  set $e4tok_frame = $e4tok_frame + 1
  set $e4tok_local = 0
  printf "FRAME n=%d\n", $e4tok_frame
  set $e4tok_local = $e4tok_local + 1
  printf "HIT tag=HIT_EVENTS global=%d frame=%d local=%d pc=0x0207F480\n", $e4tok_hits, $e4tok_frame, $e4tok_local
  continue
end

break *0x0215A978
commands
  silent
  set $e4tok_hits = $e4tok_hits + 1
  set $e4tok_local = $e4tok_local + 1
  printf "HIT tag=FIGHTER_UPD global=%d frame=%d local=%d pc=0x0215A978 obj=0x%x r1=0x%x\n", $e4tok_hits, $e4tok_frame, $e4tok_local, $r0, $r1
  continue
end

break *0x02159CC4
commands
  silent
  set $e4tok_hits = $e4tok_hits + 1
  set $e4tok_local = $e4tok_local + 1
  printf "HIT tag=STATE_COMMIT global=%d frame=%d local=%d pc=0x02159CC4 obj=0x%x\n", $e4tok_hits, $e4tok_frame, $e4tok_local, $r0
  continue
end

break *0x0215EF24
commands
  silent
  set $e4tok_hits = $e4tok_hits + 1
  set $e4tok_local = $e4tok_local + 1
  printf "HIT tag=GUARD_DRAIN global=%d frame=%d local=%d pc=0x0215EF24 obj=0x%x\n", $e4tok_hits, $e4tok_frame, $e4tok_local, $r0
  continue
end

break *0x02082E10
commands
  silent
  set $e4tok_hits = $e4tok_hits + 1
  set $e4tok_local = $e4tok_local + 1
  printf "HIT tag=INTEGRATOR global=%d frame=%d local=%d pc=0x02082E10 elem=0x%x\n", $e4tok_hits, $e4tok_frame, $e4tok_local, $r0
  continue
end

break *0x0216AF04
commands
  silent
  set $e4tok_hits = $e4tok_hits + 1
  set $e4tok_local = $e4tok_local + 1
  printf "HIT tag=OBJSHOT global=%d frame=%d local=%d pc=0x0216AF04\n", $e4tok_hits, $e4tok_frame, $e4tok_local
  continue
end

break *0x02077D40
commands
  silent
  set $e4tok_hits = $e4tok_hits + 1
  set $e4tok_local = $e4tok_local + 1
  printf "HIT tag=REGEN_TICK global=%d frame=%d local=%d pc=0x02077D40\n", $e4tok_hits, $e4tok_frame, $e4tok_local
  continue
end

printf "PROBE_ARMED\n"
continue
