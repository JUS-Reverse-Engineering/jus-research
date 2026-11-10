# GameFAQs moveset extracts: schema

One JSON file per guide, named `<character-slug>--<gamefaqs-id>.json` (two
guides for one character = two files). Extraction tracker item: `jus-6ckd`. Source
files live in `sources/gamefaqs/raw/` (gitignored; see
`docs/research/sources/gamefaqs.md`).

These are **player-written numbers**, community testimony. They are a
checklist of what moves exist and roughly what they do, not measurements.
Never cite one as a confirmed value.

```json
{
  "character": "Kakashi",
  "series": "Naruto",
  "chr_b": 23,
  "chr_b_note": "from docs/research/chr_b-Complete-Mapping.md; null if the character is not in the table",
  "source": {"file": "46618-kakashi.txt", "gamefaqs_id": 46618, "author": "MasterTurtle", "version": "2.0"},
  "kit_type": "standard | summoner | item-creator | other (owner's word; see README)",
  "natures_available": ["knowledge", "laughter"],
  "koma": [
    {
      "size": 4,
      "role": "battle | support | help",
      "nature": "knowledge",
      "hp": null,
      "passives": ["text as written"],
      "specials": [ { "input": "X", "name": "...", "description": "...", "damage": "as written", "hits": null, "properties": ["projectile"], "quote": "short guide quote" } ],
      "support_effect": "for support/help koma only",
      "help_effect": "for help koma only"
    }
  ],
  "moves": [
    {
      "input": "B | side B | up B | down B | air B | Y | side Y | up Y | down Y | air Y | select | B string | other",
      "name": "guide's name or null",
      "description": "one or two plain sentences",
      "damage": "as written, e.g. '2 + 6' or '24 close, less far'",
      "hits": 2,
      "properties": ["launcher", "pop", "guard break", "projectile", "forced switch", "knockdown", "status:<name>", "mash-extend", "multi-hit", "counter", "charge"],
      "quote": "the sentence(s) this came from, trimmed"
    }
  ],
  "combos": ["as written, optional"],
  "unresolved": ["anything the guide says that did not fit the schema, or contradictions between sections"]
}
```

Rules: keep the guide's own words in `quote`; do not invent damage numbers;
use `null` for anything the guide does not say; `properties` only when the
guide states the effect. Inputs use the guide's directions (side/up/down),
not our button codes. The down+B "forced switch" attack and the SELECT
Ultimate Action are moves, not specials.
