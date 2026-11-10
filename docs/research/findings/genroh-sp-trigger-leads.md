# Genroh guide leads for SP gain triggers

Recorded under `jus-1bkw` during consolidation `jus-atns.3`, 2026-09-12.
Source: Genroh, GameFAQs FAQ 45856, local
`sources/gamefaqs/raw/45856-genroh-guide.txt`, help-ability list at lines 1291–1441.
The raw corpus is gitignored. The checked-in
guide archive contains the same ability
categories; source inventory identifies the guide.

Evidence grade: fan-guide testimony. This supplies candidate gameplay triggers,
not runtime-confirmed mappings to ability IDs, deposit cells, or payout rates.

| Candidate trigger | Raw-guide lines | Missing for implementation |
|---|---|---|
| Battle or support attack/block events | 1291–1314 | Meaning of attack/block and per-contact versus per-action firing |
| Multiple hits | 1316–1330 | Hit threshold, window, reset condition, amount |
| Remaining on the same fighter without support calls | 1332–1342 | Tick interval, reset behavior, amount |
| Repeated specials within a short interval | 1344–1356 | Required count, interval, reset condition, amount |
| Standing still without attacking | 1358–1369 | Entry delay, tick interval, amount |
| Opposing nature or low health | 1371–1394 | Nature/HP predicate and amount |
| Inflicting or receiving a KO | 1396–1411 | Trigger implementation; receiving-KO entry claims one bar, unverified |
| Presence on the field | 1413–1419 | Tick interval and amount |
| Last-moment block | 1421–1431 | Timing window and amount |
| Chain attacks | 1433–1441 | Chain definition, reset condition, amount |

The guide gives no numeric cadence, multi-hit threshold, or repeated-special
window in these entries. Its receiving-KO one-bar claim is an exception to the
otherwise unspecified amounts and still needs verification. Anna and Don Patch
provide named carrier leads for multi-hit and repeated-special effects.

The measured base mechanism remains the
[SP deposit-and-payout model](../../confirmed-facts/guard-sp.md). Owner testimony
also confirms gains from hitting and being hit, with passive extensions
([scope record](owner-feel-scope-2026-09-12.md)). Test the guide predicates against
the measured deposit cells and ability table before assigning rates or IDs.
