# ROM AI access paths

These are bounded static findings from the original game's ov11 code. They do
not establish the values seen during play or explain the owner's AI behavior
complaints. The investigation and withdrawn interpretations are in
[CPU AI levels](../research/side-quests/cpu-ai-levels.md).

## Probability gate field

The main gate at `0x02179130` reads the AI state word at `+0x38`, masks it to
the low byte, and compares it with a word threshold from `0x0218190C`. Three
other gate routines also read `+0x38`. The code establishes a shared storage
field, but does not show that separate calls observe the same unchanged value.
Two PRNG-fed word stores and two caller-fed byte stores are identified; other
candidate writes still need attribution. One previously counted site,
`0x021765A4`, stores a pointer into another object. See tracker item `jus-tx3b` and
the [writer correction](../research/side-quests/cpu-ai-levels.md#310-the-rolls-distribution-is-unknown-so-every-percentage-above-is-provisional).

Per-call writer, value, and correlation measurements remain open in
`jus-ai-roll-writer-trace-xgig`. An independent-draw patch option is tracked in
`jus-ai-independent-gate-draws-o1fr`.

## Opponent-state accessor

The accessor at `0x02174F4C` returns a byte from `[[fighter]+4]+8`. Observed
uses compare values 1 and 2 and use values at or above 3 to select different
table indices. Other AI paths read a flags word at entity `+0x68` and position
values at `+0xB0/+0xB4`. This byte is therefore one input, rather than the
AI's entire opponent model. See tracker item `jus-phqu` and the
[accessor trace](../research/side-quests/cpu-ai-levels.md#39-one-opponent-state-accessor-returns-a-byte).

The meanings of the byte values, selected rows, and effects on behavior remain
open in `jus-ai-opponent-state-map-mbq6`.
