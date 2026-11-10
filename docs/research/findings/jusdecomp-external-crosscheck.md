# External cross-check — JUSDecomp overlay map vs ours

Tracker item: `jus-jusdecomp-crosscheck-x1cf`

Recorded 2026-08-26. Source: [piuzera/JUSDecomp](https://github.com/piuzera/JUSDecomp)
(MIT license) — an independent static-recompilation project that runs JUS (AJUJ)
natively on Windows via ndsrecomp, v0.2.1 playable. It had no contact with our
record, which makes its agreements meaningful corroboration and its
disagreements worth resolving. Their RE effort covers decks, saves, and modding;
their own TODO.md (2026-08-20/21 scope changes) demotes battle-mechanics
*understanding* because the recomp runs the original code untouched — so they
publish no combat arithmetic.

## 1. Overlay table — independent agreement, no numbering conflict

Their [overlays doc](https://github.com/piuzera/JUSDecomp/blob/main/decomp/docs/OVERLAYS.md)
(from their dsd 0.12.0 extraction metadata) matches our overlay model exactly:

- 14 ARM9 overlays, ids 0–13; ov6 base `0x0214CD20` (region A, 0x25C40 code),
  ov11 base `0x02172A60` (region B, 0xF000 code + 0x2A760 BSS).
- Region model: one region-A overlay + one of ov10/ov11 in region B + ov12
  near-resident. Region B swaps ov10 (comm) → ov11 on battle entry.

This independently agrees with [Overlay-Map.md](../Overlay-Map.md) and our
runtime residency measurements
([Overlay-Residency-By-Mode.md](../Overlay-Residency-By-Mode.md): ov06 and ov11
100% resident in battle). All our published ov6 addresses (e.g. `0x02157114`,
`0x021710A8`) fall inside their ov006 range — both projects number from the
ROM overlay table, so "their ov006" = "our ov6".

## 2. Their battle labels — conflict, resolved in our favor

Their overlays doc labels **ov006 "Battle UI layer"** (evidence: 33 `battle/*`
NitroFS path strings) and **ov011 "Battle core engine"** (their own grade:
*strongly inferred*, by elimination — no path strings, called only by ov006,
compact 875-function graph). Both labels are superseded by our finer-grained
evidence:

- **ov11 is battle AI**, not the battle core: it is the sole referencer of
  `chr/ai/ai_param.bin` ([Overlay-Map.md](../Overlay-Map.md)). Note this is
  their own method (path-string attribution) applied at file rather than
  directory grain.
- **The combat core lives in arm9 main**: damage formula `0x020823E4` called
  from the collision pipeline at `0x02081280`
  ([damage spec](../../confirmed-facts/damage.md),
  [p208](p208-damage-formula-0x020823E4.md)); collision managers and MoveMan
  are main-RAM constructions ([collision spec](../../confirmed-facts/collision.md)).
- **ov6 carries battle logic, not just UI**: the load-time gate-word +
  packed-nature assembly at `0x02157114`
  ([p220](p220-one-routine-assembles-both-derived-values.md)) and all 8 callers
  of the HP-delta apply entry `0x020783CC`
  ([HP-Struct-From-Disassembly.md](../HP-Struct-From-Disassembly.md)).

No changes to our specs result from this cross-check; our claims stand and
gain an independent corroborator for the overlay/residency model.

## 3. Reusable assets in their repo (runtime-agnostic; verify before promoting)

These are leads, not confirmed facts — their docs contain self-retractions, so
anything below must pass our own verification before entering
`docs/confirmed-facts/`.

- **Deck record format** ([their DECK_FORMAT doc](https://github.com/piuzera/JUSDecomp/blob/main/decomp/docs/DECK_FORMAT.md),
  runtime-confirmed by them via live injection): 92-byte records, 16 slots of
  `{u16 koma_id, u16 flags}` (`0xFFFF` empty), Shift-JIS full-width name at
  `+0x40`; slot link flags decoded.
- **Deck-system RAM addresses** ([their FUNCTIONS doc](https://github.com/piuzera/JUSDecomp/blob/main/decomp/docs/FUNCTIONS.md)): deck table
  `0x020B0DBC + idx*0x5C`, counts `0x020B0D6C`/`0x020B0D6D`, aux table
  `0x020B1FB4 + idx*0x4C`, table2 `0x020B2E8C + idx*0x5C`, save dirty-range
  tracker `0x020B02AC` (marker fn `0x02073114`). Useful for scripted battle
  setup: poke a deck record instead of menuing.
- **`JUSDecomp/data/koma_db.csv`** — 890 komas with shape grids, nature, tiles, type;
  plus `kizuna.json` (205/206 battle komas mapped).
- **Compiler pinning**: original binary matches `mwccarm 2.0/*`/`dsi/*`
  builds (their byte-exact match of `func_ov000_0214de00`). Reference tool if
  we ever need to settle a truncation-vs-rounding question by recompilation.
- **Overlay→screen map for non-battle overlays** (ov000 title/menu, ov005 deck
  builder, ov007 download-play lobby, ov008 WFC, ov012 shared UI/DB library —
  their path-string evidence is strong for these).

## 4. What not to take

- Their ov006/ov011 battle labels (§2).
- Their ov006 `symbols.txt` — 1047 of ~1290 symbols are auto-generated
  `func_`/`data_` names; no semantic naming to import.
- Any combat behavior claims — they have none.
