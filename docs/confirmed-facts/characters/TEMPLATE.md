# {{CHARACTER_NAME}} (`chr_b` {{CHR_B_INDEX}}, `{{FILE_PREFIX}}`)

Use this template for a current character reference. Cite
[character-index.json](character-index.json) for generated identity fields. Support every
other claim with a tracker item. Put raw logs and investigation notes under `docs/research/` and
link them from the source section.

Primary map tracker item: `{{MAP_ITEM_ID}}`.

## Identity

| Field | Value | Source |
|---|---|---|
| Character | {{CHARACTER_NAME}} | [character index](character-index.json) |
| Series | {{SERIES}} | [character index](character-index.json) |
| `chr_b` index | {{CHR_B_INDEX}} | [character index](character-index.json) |
| File prefix | `{{FILE_PREFIX}}` | [character index](character-index.json) |
| Form or panel variant | {{FORM_OR_PANEL}} | {{IDENTITY_SOURCE}} |

## Measurement conditions

Record enough information to reproduce the observations. Use one row for each capture
set when conditions differ.

| Item | Value | Tracker item |
|---|---|---|
| Capture or state | {{CAPTURE_OR_STATE}} | {{CONDITIONS_ITEM_ID}} |
| Emulator build | {{EMULATOR_BUILD}} | {{CONDITIONS_ITEM_ID}} |
| ROM hash record | {{ROM_HASH_SOURCE}} | {{CONDITIONS_ITEM_ID}} |
| Attacker | {{ATTACKER}} | {{CONDITIONS_ITEM_ID}} |
| Victim | {{VICTIM}} | {{CONDITIONS_ITEM_ID}} |
| Geometry | {{GEOMETRY}} | {{CONDITIONS_ITEM_ID}} |
| CPU and rules | {{CPU_AND_RULES}} | {{CONDITIONS_ITEM_ID}} |
| Measurement method | {{MEASUREMENT_METHOD}} | {{CONDITIONS_ITEM_ID}} |

## Column definitions

Define every measured column before the move tables. State the sampling point, units,
and any instrumentation delay.

| Column | Definition | Tracker item |
|---|---|---|
| {{COLUMN_NAME}} | {{DEFINITION_AND_UNITS}} | {{COLUMN_ITEM_ID}} |

## Normal moves

Add one row for each tested input and condition. Use `not measured` when the campaign did
not test a value. Do not infer a value from animation, guide text, or another character.

| Input | Condition | Startup | Active | Recovery | Hits | Damage | Hit type | Hitstun | Knockback | Effects | Tracker item |
|---|---|---:|---:|---:|---:|---:|---|---:|---|---|---|
| {{INPUT}} | {{CONDITION}} | {{STARTUP}} | {{ACTIVE}} | {{RECOVERY}} | {{HITS}} | {{DAMAGE}} | {{HIT_TYPE}} | {{HITSTUN}} | {{KNOCKBACK}} | {{EFFECTS}} | {{MOVE_ITEM_ID}} |

Describe only behavior needed to interpret the table, such as multi-hit timing, forced
switches, movement during the attack, or a measurement hazard. Cite each paragraph.

## Special moves

Identify the panel or form that provides each special. Separate inputs that dispatch the
same move only when the supporting tracker item establishes that equivalence.

| Panel or form | Input | Move | Startup | Active | Recovery | Hits | Damage | Hit type | Hitstun | Knockback | Cost | Effects | Tracker item |
|---|---|---|---:|---:|---:|---:|---:|---|---:|---|---:|---|---|
| {{PANEL_OR_FORM}} | {{INPUT}} | {{MOVE}} | {{STARTUP}} | {{ACTIVE}} | {{RECOVERY}} | {{HITS}} | {{DAMAGE}} | {{HIT_TYPE}} | {{HITSTUN}} | {{KNOCKBACK}} | {{COST}} | {{EFFECTS}} | {{SPECIAL_ITEM_ID}} |

## Resources and passive effects

| Resource or effect | Observed behavior | Address or field | Conditions | Tracker item |
|---|---|---|---|---|
| {{RESOURCE_OR_EFFECT}} | {{OBSERVED_BEHAVIOR}} | {{ADDRESS_OR_FIELD}} | {{CONDITIONS}} | {{RESOURCE_ITEM_ID}} |

## Character-specific mechanics

| Mechanic | Trigger | Observed result | Limits | Tracker item |
|---|---|---|---|---|
| {{MECHANIC}} | {{TRIGGER}} | {{OBSERVED_RESULT}} | {{LIMITS}} | {{MECHANIC_ITEM_ID}} |

## Not yet measured

List only open questions that belong to this character. Create or cite a tracker item for each
question. Do not use this section as a general testing queue.

| Question | Why it matters | Tracker item |
|---|---|---|
| {{QUESTION}} | {{IMPACT}} | {{OPEN_ITEM_ID}} |

## Sources

| Source | Purpose | Tracker item |
|---|---|---|
| {{RAW_CAPTURE_OR_FINDING_LINK}} | {{WHAT_IT_SUPPORTS}} | {{SOURCE_ITEM_ID}} |

Link shared mechanics to the relevant current references instead of copying them here:

- [Physics](../physics.md)
- [Damage](../damage.md)
- [Moves](../moves.md)
- [Guard and SP](../guard-sp.md)
- [Helpers and passives](../helpers.md)
