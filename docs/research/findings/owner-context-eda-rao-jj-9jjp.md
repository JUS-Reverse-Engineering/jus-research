# Owner testimony — EDA, RAO, and JJ decks

Tracker item: `jus-9jjp`

Runtime reconciliation is tracked separately in `jus-qz7z`.

Recorded 2026-08-26 from the owner's description of the three newly prepared
deck slots. This entry preserves player knowledge as test context; it does not
promote the observations below to measured game facts.

## Decks

| save-deck position | name | battle characters | other context |
|---:|---|---|---|
| 3 | EDA | Edajima, Don Patch, Luffy | Edajima is the intended gate-bit 4+5 target; Don Patch and Luffy provide useful follow-up targets. |
| 4 | RAO | Raoh, Franky, Nami | Franky and Nami are owner-selected heavy/light movement contrasts. |
| 5 | JJ | Jotaro, Sanji, Lenalee, Kenshin | Kenshin uses the 5-koma panel; intended special-gate and movement follow-up deck. |

## Reported gameplay observations

- Edajima feels super-heavy: slow movement and low knockback. The owner
  attributes this to a unique passive and distinguishes it from being
  intrinsically heavy like Franky.
- Don Patch is reported to be inherently weak to special attacks. His short
  height can make some attacks, including Sanji neutral Y, miss while he is
  standing still.
- Luffy resists blunt attacks (punches and kicks) and is weak to sharp attacks
  (blades).
- Sanji neutral Y does not hit a stationary Don Patch.
- Kenshin's 5-koma X special deals damage and knockback. The launch distance
  and height are reported to vary with opponent weight and remaining health;
  whether the health term is percentage-of-max or an absolute value is
  unknown.

## Open interpretation

The owner recalls earlier work suggesting that weight may not be stored as an
independent variable, and may overlap with walking speed and possibly dash
length. That relationship remains unconfirmed. These observations should be
used to choose stimuli and controls, not cited as a settled field map.

## Savestate capture

The editor state containing the saved decks is
`ds8t_decks_eda_rao_jj_editor`. Battle-entry states with auto-heal behaviorally
verified off are `ds8t_deck3_battle_noheal`, `ds8t_rao_battle_noheal`, and
`ds8t_jj_battle_noheal`.

The raw player-slot `+0x29` bytes observed in those battle states were EDA
`[66, 48, 12]`, RAO `[62, 15, 17]`, and JJ `[28, 14, 36, 46]`. They do not
match the owner-visible character names when interpreted through the current
`chr_b` table. The owner confirmed the MelonDS deck displays were correct, so
this is an unresolved deck-selection or runtime-index mapping problem, not a
correction to the deck list above.
