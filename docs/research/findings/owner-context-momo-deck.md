# Owner context: MOMO deck

Tracker item: `jus-ds8t`  
Date: 2026-08-26

The owner kept the EDA deck unchanged and created a new deck named `MOMO` in
visible deck-list position 6. The refreshed battle savestate is
`ds8t_momo_battle_noheal`.

## Runtime identity

The refresh run found the player roster in order `[67,68,32]`:

| runtime index | character | panel/context |
|---:|---|---|
| 67 | Momotaro | 6-koma ALT; Power normal nature; attacks deal Knowledge damage, specials deal Power damage |
| 68 | Taikoubou | summoner character |
| 32 | Yusuke | 6-koma |

These runtime IDs come from the battle `+0x29`/`+0x41` fields and are the
authoritative ordering for experiments. The deck-refresh manifest records this
order in `scripts/emu/savestate_refresh.json`.

## Owner attack observations

- Momotaro's X special is a persistent energy beam while he is firing it.
- Yusuke's X special fires a large, high-priority projectile that consumes many
  other projectiles on contact.
- Most Taikoubou Y moves summon another character sprite that behaves like a
  projectile.
- Taikoubou's neutral Y summons a downward slash with a battle/support-like
  hitbox: attacks that stop on those characters stop on it, and fighters
  walking through it are slowed in the same way.

The nature split, persistence, projectile priority, and summoned hitbox are
owner observations. They are useful probes for later projectile classification,
but are not yet static engine conclusions.
