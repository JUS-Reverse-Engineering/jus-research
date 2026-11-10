# Owner clarification of combat feel

Source: owner conversation on 2026-09-12, recorded in `jus-atns.3`.
These are owner gameplay testimony, not new runtime measurements.

## Projectile persistence

Projectiles survive switching characters once the animation that spawned them has
ended. Fire-then-switch is constrained by the fighter's animation timing. Switching
does not itself remove the projectile. This is owner testimony about observed behavior;
it does not identify a teardown callback or measure the earliest legal switch frame.

## Attack and guard timing

Startup varies by attack. The owner identifies Yusuke's neutral B as exceptionally
fast, including when used immediately after releasing guard. The owner describes
guard-release delay as short and consistent across characters. Neither statement
supplies an exact frame count.

Open questions: attack startup and guard-release timing. Measure input
acceptance, first active hitbox, first contact, and guard-flag clear separately.
Existing input-to-contact tables can include projectile travel or spacing effects.
Do not infer a universal startup delay or equate guard-flag clearing with the earliest
accepted attack input. Follow-up: `jus-atns.5`.

## SP gain

The owner states that hitting and being hit increase SP, with passives adding gain
methods such as multi-hit attacks and repeated specials. The Genroh guide is a lead
for those triggers, not a supplied cadence measurement. Preserve the measured
deposit-and-payout arithmetic while resolving amounts, conditions, and tick timing
under `jus-1bkw`.
