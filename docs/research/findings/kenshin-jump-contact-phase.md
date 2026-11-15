# Kenshin jump contact phase and landing clamp

828 retained Kenshin rows and a fresh-capture
preregistration support this: The atns41 integrator-entry position is the previous step's
position, while Native contact bit0x02 reflects the current collision pass.
Surface membership therefore agrees with the previous row's contact bit. The
ROM clip proves ORR#2 at0x0207ECB4 and the store to M+0x78 at0x0207ECB8; full
caller phase is supported by the probe comment and827 Native phase pairs, not
proved solely by that clip.

Predict the landing surface from the independent test-play table and contact-row
height. The landing row is contact+1, exactly on that surface. Its downward step
equals surface minus contact-row height and must be positive and no larger than
the contact row's step. All later steps are zero. Exact-row arrival is
EXACT_ROW_UNRULED, an unknown surface is SURFACE_UNTABLED, and an oversized step
is CLAMP_EXCEEDS_STEP. These are refusals, never tolerance cases.

The retained trajectory has launch25, contact63 at163799 with step408, and
landing64 at163839 with step40. State13 lasts65..74. The separate preregistration
rejects a one-row-shifted trajectory even when the general clamp rule passes.

Eighteen independent Train sources establish floor180223/platform163839 and the
clamp shape:12 steps78 after475 and6 steps187 after955, followed by stillness.
Their row numbers46/94/143 are relative to anchor256, absolute302/350/399.
Those samplers are one frame ahead of the contact probe. They do not establish the
launch/contact predicates; all18 fail the general checker as expected.
The stage-collision table and platform horizontal extent remain undecoded.

The pinned physics.md was left unchanged. Qualification, sources and exact
predictions are in jump-ground-v2-refute-qualification.json,
test-play-surfaces.json and jump-ground-v2-preregistration.json. The historical
c31 capture remains diagnostic, with no retroactive admission.
