# Guide-Sourced Data (GameFAQs)

Data distilled from fan-made GameFAQs guides for Jump Ultimate Stars. Raw guide
text lives in `sources/gamefaqs/raw/` (untracked — the guides are copyrighted
by their authors; re-fetch with `sources/gamefaqs/fetch.sh`, which pulls from
the Wayback Machine because GameFAQs blocks direct scraping).

## Scope

Only **in-battle mechanics** are in scope. Gem/evolution costs and
other economy data (J-Gem earn rates, unlock prices) are out of scope — ignore
them where they appear in older extractions and don't extract them going
forward. (Exception: unlock data that reveals battle mechanics is fine.)

## Reliability

These are hand-written community guides, not extracted game data. Treat every
number as a **claim to verify**, not a confirmed fact. They're useful as:

- a hypothesis source (e.g. "nature triangle gives 1.5x damage" → verify in ov06)
- a cross-check against runtime findings and `docs/confirmed-facts/`
- a base layer of movesets and koma stats to fill gaps we haven't reached yet

When a guide claim is confirmed against the ROM or runtime traces, promote it
to `docs/confirmed-facts/` and cite both sources. When a guide claim is
refuted, note it here so it doesn't get re-imported.

Every extracted fact carries its source guide id (the GameFAQs FAQ id, e.g.
`gf-45856`). URL pattern:
`https://gamefaqs.gamespot.com/ds/933199-jump-ultimate-stars/faqs/<id>`

## Layout

- `systems/` — mechanics distilled from system FAQs (battle rules, gauges,
  status effects, deckbuilding, support/help koma, healing, statistics).
  See `systems/README.md` for the per-file index.
- `characters/` — per-character moveset and koma data, one file per source
  guide (52 files covering all 52 character guides; note two Muhyo and two
  Lenalee guides by different authors). Most contain per-move damage numbers,
  J-Soul (HP) values per koma size, hit counts, and SP costs. Sparse ones
  (mostly strategy, few numbers): hiei, killua, arale, tsuna.

## Deliberately not extracted (out of scope)

- `46489` Manga Moments FAQ (collectibles) and the two general walkthroughs —
  no battle mechanics.
- Economy/menu docs that were extracted early were moved to
  `JUSToolkit/docs/articles/game-reference/` (j-gem, wireless-mode).
