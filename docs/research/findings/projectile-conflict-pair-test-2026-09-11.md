# Projectile-conflict pair test favours the dies-on-contact reading

Tracker items: `jus-pebk`, `jus-hitbox-priority-clash-1evz`.

## Question

`jus-pebk` set up an owner-designed pair test to separate two readings of
node `+0x18` bit 0 (traced to entry `+0x08` bit 5 in
`docs/research/findings/node-0x18-is-seeded-from-the-collision-entry-property-word.md`):

- **H1** (self property): bit 0 set means this record is torn down via the
  `0x209` path when it touches another attack; bit 0 clear means attack
  contact is ignored.
- **H2** (pair rule): bit 0 set marks a class that *loses* to bit-clear
  records specifically -- a comparison between the two sides, not a
  property of either side alone.

The census that motivated this test
(`docs/research/feel-captures/projectile-census-2026-09-10/SUMMARY.md`)
could not separate the two: every bit-set "loser" it found was also a
projectile that dies on hitting a body, so H1 and H2 both predict its fate.

## Conditions

- Emulator: `fork_commit c26edf0e0d75364823856c9272a103fe39e03999`, built
  `2026-09-01T19:26:00Z`, JIT off.
- Tool: `scripts/emu/projectile_replay.py` (tracker item `jus-2s9k`), run once per
  state with the tool's default plan (`START` frames 0-2, no input to
  frame ~149, `START` frames 150-152), 170 observed frames per run.
- Full per-state data, watch specs, and per-frame timelines:
  `docs/research/feel-captures/projectile-conflict-2026-09-11/SUMMARY.md`
  and its per-slot `RESULTS.md`/census files.
- Owner-chosen pairs and testimony:
  `docs/research/moveset-notes/OWNER-NOTES.md`, "Owner projectile-conflict
  states for jus-pebk (2026-09-11)".
- Positive control (`pc-momotaro-npc-yusuke-projectiles-about-to-collide`):
  reproduced -- Yusuke's fwd-Y record 70 (`+0x34=0x1002`, `+0x3C=0x63C822`,
  node `+0x18` bit 0 set) went `0x8 -> 0x209 -> 0x200` on contact.

## Evidence

1. **Bit-clear vs bit-clear** (`pc-yugi-fb-npc-momotaro-fy`: Yugi dice
   record 45, entries 273+258, vs Momotaro fwd-Y record 50, entry 262 --
   both bit 0 clear): neither record ever showed the `0x209` transient.
   Both toggled `0x8<->0x9` for a while and then went straight to `0x200`,
   45 frames apart (+70 and +25 frames from unpause). Owner testimony: the
   two projectiles pass through each other, no collision effect, no
   damage. H2 predicts one side should win; there is no winner here to
   pick.

2. **Bit-set vs bit-set** (`pc-naruto-fy-npc-yusuke-fy`: rec49, the Yusuke
   fwd-Y candidate by shape-match to the control's record 70, vs rec50, one
   of Naruto's three shuriken -- both bit 0 set): both went `0x8 -> 0x209 ->
   0x200` on the *same* frame pair (112982/112983), one frame after
   unpause. Owner testimony: Yusuke's fwd Y and one shuriken vanish
   together with the collision effect. H2 predicts one side should win;
   both went down together instead.

3. **Control** (bit-set Yusuke fwd-Y vs bit-clear Momotaro fwd-Y): the
   bit-set side is torn down via `0x209`, the bit-clear side survives. This
   result fits both H1 and H2 -- it is not discriminating by itself, which
   is why the census needed the two pairs above.

4. **`pc-naruto-fy-npc-yusuke-x`**: all three of Naruto's bit-set shuriken
   (rec53/54/55) went straight `0x8 -> 0x200` at the same frame (+15 from
   unpause, no `0x209` transient). Owner testimony: Yusuke 6-koma X IS a
   projectile; no Yusuke X record was present at the paused baseline frame
   or at the post-run census (see Retraction, below), so this run cannot
   place it in the record layer either way. This is a different teardown
   path from the other three pairs and is **not** confirmed attack-vs-attack
   contact as this instrument measures it, so it does not bear on H1 vs H2
   either way.

## Verdict

Two pairs discriminate between H1 and H2, and both fall H1's way: neither a
bit-clear-vs-bit-clear pair nor a bit-set-vs-bit-set pair produced a winner.
H2 is disfavoured. "Torn down via the `0x209` path when it touches another
attack" (bit 0 set) vs "attack contact ignored" (bit 0 clear) is the
observable that survives; this document does not name bit 0 as priority,
cancel, hit, or any other gameplay term, because contact itself was not
directly measured (see below).

## What this cannot show

- Contact was not independently confirmed -- there was no pair-test
  breakpoint on an actual collision check. The teardown timing (same frame
  for both records in each discriminating pair) is the evidence, not a
  measured touch.
- Record ownership ("this record is Yusuke's fwd Y", "this one is Naruto's
  shuriken") is inferred from shape (field values, node sets, and the match
  to the positive control's record 70), not read from any owner field --
  the census schema has none.
- Each pair is one encounter. Nothing here rules out a rarer third factor
  that happens to correlate with bit 0 in these four captures.
- `pc-naruto-fy-npc-yusuke-fy` also left a free-slot record active for part
  of the run (slot 52, frames 112981-113006) that the watch spec never
  attributed to an owner; the owner's third shuriken is otherwise
  unaccounted for.

## Second opinion

An independent GPT-5-class model (`codex`) reviewed the naruto-fy-yusuke-fy
capture and the control
(`docs/research/feel-captures/projectile-conflict-2026-09-11/codex_prompt_rec49.txt`,
`codex_second_opinion_rec49.md`,
`codex_prompt_rec49_followup.txt`,
`codex_second_opinion_rec49_followup.md`). It agreed that rec49 differs from
rec50/rec51 and is the best Yusuke fwd-Y candidate, and that the timeline
fits the owner's account. It also cautioned, independent
of the correction below, that the data show correlation in one encounter,
not a proven bit-controlled rule: contact itself is not established for
record 51 (bit 0 set, no `0x209`, no evidence it touched anything), and the
bit-clear pair does not confirm an attack-on-attack event either.

Its one objection rested on a wrong control value in the first prompt (node
`+0x18=0x220`, bit 0 clear) -- a transcription error, not the real value
(node `+0x18=0x00000001`, entry `+0x08=0x20`, bit 0 **set**). With the wrong
value, codex flagged a genuine contradiction of H1. The followup prompt
supplied the correction and asked it to redo that answer: codex confirmed
the corrected control removes the contradiction, and that the bit-0 reading
"survives as a correlation consistent with all supplied captures, not yet a
demonstrated rule" -- matching the verdict above.

## Retraction (2026-09-11, owner testimony)

Owner testimony: Yusuke 6-koma X IS a projectile. This retracts the
Evidence (4) and Open wording above that called it "not a ColPrm/ObjShot
record." The correct statement: in the four X states captured here
(`pc-yugi-fb-npc-yusuke-x`, `pc-yugi-y-npc-yusuke-x`,
`pc-taikoubou-upx-npc-yusuke-x`, `pc-kurama-x-npc-yusuke-x`), no Yusuke X
record was present at the paused baseline frame or at the post-run census.
`projectile_replay.py`'s tail only watches baseline records plus a few free
slots, so a record that spawned after unpause and was torn down before the
post census is invisible to this run -- that is a tool blind spot, not
evidence about the game's record layer. The owner notes these states may be
paused before the projectiles spawn.

In `pc-naruto-fy-npc-yusuke-x`, the three shuriken went straight
`0x8 -> 0x200` at +15, consistent with an unwatched X record arriving and
being torn down within the same window: free-slot watch `free56_0x40` went
`0x200 -> 0x8` at frame 113398, `0x8 -> 0x209` at 113404, `0x209 -> 0x200`
at 113405 -- the same contact-teardown signature seen elsewhere in this
capture set. This is the only trace available from this run; it is
consistent with, but does not prove, an unwatched X record's lifecycle.

Plan: a pre-roll rerun (unpause each X state, re-pause once both
projectiles exist per census, save a derived `<slot>-preroll` state, rerun
`projectile_replay.py`) is needed to put Yusuke X's own record inside the
watch set. Tracked as `jus-xyqc`.

## Open

- Whether Yusuke's 6-koma X, Kurama's X, and Sasuke's X are ColPrm/ObjShot
  records is unresolved: the four X-side states captured here had no
  Yusuke X record at baseline or post census, but `projectile_replay.py`
  cannot see records spawned and torn down between those two points (see
  Retraction, above). A pre-roll rerun is needed before drawing a
  conclusion either way. See the follow-up tracker item below.
- `pc-sasuke-x-npc-yusuke-x` produced an invalid run (all 170 tail frames
  identical -- it never unpaused); no conclusion either way, rerun needed.
- The owner's third shuriken in `pc-naruto-fy-npc-yusuke-fy` is
  unaccounted for beyond the unattributed free-slot-52 activity above.
