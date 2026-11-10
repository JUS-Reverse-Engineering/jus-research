# Kakashi SELECT live steering baseline

Date: 2026-09-16

This file freezes the action and rationale approved before the
TypeSafe request. Later reviews may change the action, but they do not change
this baseline.

## Working hypothesis

Owner testimony describes Kakashi SELECT as a timed substitution status. The
exact protection duration and whether a protected hit consumes the status stay
open until a valid damage comparison resolves them.

## Known facts and provenance

- SELECT enters state 12 at input plus 3 and plays a 60-frame activation. The
  activation has no measured hitbox or SP cost. Source:
  earlier Kakashi capture notes.
- SELECT is not accepted while Kakashi is airborne or mid-attack. Reuse was
  accepted from idle at plus 200 and ignored during a hit reaction at plus 60.
  Source: earlier Kakashi capture notes.
- The prior fight-CPU batch recorded hit reactions but no HP decrease through
  about 7,500 frames. It used a fixed HP address without a P1 damage control.
  Source: `docs/research/feel-captures/kakashi-4.10-2026-09-14/RESULTS.md`.
- `obj+0xF6` and `obj+0x11B` are not SELECT-specific status or expiry fields.
  Source: earlier Kakashi capture notes.
- The owner directed this rerun to disable auto-heal, derive HP from the live
  battle root, validate P1 and Kakashi identity, and require a damaging
  no-SELECT control. Source: `jus-n4io`.

## Alternatives

- A1: SELECT protects only the first qualifying incoming hit and the hit
  consumes the protection.
- A2: SELECT protects qualifying incoming hits for a duration, so more than one
  hit can be protected before expiry.
- A3: The prior contrast was caused by a stale HP address, auto-heal, attack
  selection, or another uncontrolled fixture difference. SELECT protection is
  not reproduced.
- A4: The fixture cannot produce matched damaging hits. The question remains
  unknown.
- A5: Owner testimony conflicts with the measurement. Preserve the conflict and
  return to the owner instead of overriding the testimony.

## Baseline action

Use `pc-kakashi-npc-jotaro-fightcpu`. Resolve the battle root and P1 HP at
runtime. Verify the active sides and Kakashi identity. Lower P1 HP, require an
immediate read-back, disable auto-heal, and prove that the lowered value does
not regenerate.

Run a no-SELECT control and require a CPU hit that lowers the same P1 HP field.
If that control passes, reload the fixture and run SELECT. Prove that state 12
was entered, then compare the first hit, later hits, and increasing delays.
Keep the existing hit-reaction and teleport fields in every capture.

The approved baseline did not require a matched no-SELECT run at every tested
delay. That omission remains visible so the trial can measure whether review
changes the instrumentation plan.

## Outcome mapping

- A real no-SELECT hit lowers HP and the matched first hit after SELECT does
  not: support first-hit protection behavior.
- The first real hit does not lower HP and a second real hit does: support
  one-hit consumption.
- Multiple real hits do not lower HP before a later damaging hit: support a
  time-bounded behavior and bracket its duration.
- SELECT and no-SELECT both lower HP: do not reproduce protection. Hold the
  open details and investigate the fixture or testimony
  conflict.
- Any failed root, identity, HP, auto-heal, SELECT activation, or damaging-hit
  control: stop without interpreting the run.
- A late trial without an actual qualifying hit: unknown, not expiry evidence.

## Frozen action policy

- Failed deterministic controls block interpretation.
- An experiment that cannot distinguish A1 from A2 returns for one redesign.
- Sufficient behavior evidence with no open mechanism gap
  proposes stopping.
- A useful distinguishing experiment proceeds only within the approved
  `jus-n4io` scope.
- An owner conflict, an omitted alternative that changes the claim,
  or an unresolved reviewer judgment returns to the owner.
- TypeSafe probabilities do not become game facts or permission to run.

The trial permits two capture batches and one redesign after an uninformative
result. Report before expanding those limits.
