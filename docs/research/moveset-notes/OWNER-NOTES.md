# Owner moveset notes (load before driving any character)

Owner testimony about how moves actually behave in play: mash extensions,
holds, cancels, direction rules. The GameFAQs extracts
(`docs/research/gamefaqs-movesets/`) are the move checklist; this file is the
part the guides miss. **Every moveset-mapping worker reads the character's
extract and this file before its first input** (standing program;
`jus-kakashi-moveset-map-33lu`, `jus-roster-moveset-campaign-69it`). Owner
testimony outranks a measurement that contradicts it (hard rule).

Add a section per character as the owner tells us more. Keep the owner's
wording; add the date.

## General (2026-09-03)

- **Character switch** is L/R only when the L/R hotkey stickers are assigned
  to battle koma in the deck builder (deck-editor.md covers the stickers).
  Otherwise it is a tap on the koma panels, which our touch injection has
  never managed (`jus-3aw`). Only the Taikoubou deck has the hotkeys
  set (`jus-e2w4`): L = Yusuke, R = Momotaro there. Measured: 1-frame press,
  new fighter live in 3 frames, queued if pressed during an attack; the hotkey
  goes to a fixed panel, so it cannot bring the leader back.
- **Down+Y shatters guard instantly** for every character: guard pops at once
  and the move's own knockback applies (Kakashi's is a pop). Shatter moves
  without pop/launch knockback (Sasuke's down Y, a charge and sword swing) are
  believed not to inflict the very long hitstun of a real gauge-full break
  (`jus-xcz0`). "Unblockable" is the wrong word for this; the guard is broken, not
  bypassed. Measured: confirmed on Kakashi and Sasuke; the shatter hit is
  identical to an unguarded hit, and the long stagger is gauge-full only.
- **Landing lag:** the owner noticed substantially longer landing lag
  sometimes. Measured (`jus-4nta`, three characters): each air attack in a hop
  adds 12 frames and a double jump adds 9 to a 10-frame base, plus whatever
  the current attack still owes if you land mid-swing. Plain 13, double jump
  22, one air attack 25, two 37, double jump + attack 34, worst 64. The long
  case is two air attacks, or landing during the swing. You can still attack
  from inside the window; only movement is locked.
- **Falldown:** after enough damage in one combo the victim is forced into a
  knockdown with i-frames; owner recalls a flat ~150 threshold (`jus-p6jm`).
- **Kit types:** Taikoubou, Yugi and Muhyo are summoners; their kit works
  through a summoned creature. Mashirito creates items: his Ultimate Action
  leaves items on the field, Y makes chests that look like item chests and
  explode on contact, forward Y sends a walking object that explodes at the
  end of its path.

## Kakashi `23` (2026-09-03)

- Forward Y (shuriken line): **mash Y after the input to throw more
  shuriken.** The guide's "up to 6" is the mashed count.
- Up Y **only hits an enemy who is above him in the air.** The sequence that
  connects is **side B (pops the victim up) → up Y.**

## Muhyo `59` (2026-09-03)

- Forward Y: **hold the input to make it travel farther before it comes out
  of the ground.** The victim is popped in a direction that depends on
  whether it emerges to their left, right or centre.
  Measured 2026-09-03: about 64 px ahead, only the knockback sign flips.
- Up Y is a **bird-like summon that arcs upward; it only hits someone
  directly in front of Muhyo, or slightly in front and above.** Run 7 whiffed
  it from standing range and after pops; it needs the victim at point-blank
  or just above and ahead.

## Sasuke `21` (2026-09-03)

- 8-koma X vs 7-koma X: functionally about the same launcher; the 8-koma
  does more damage and has a slightly different windup. The 7-koma
  measurement (run 7) stands in for both.
- Up B: a **two-hit rising kick. The second hit can be cancelled** into a
  different move by inputting another action before the second kick fires
  (up B into X, up B into Y).

## Taikoubou `68` (2026-09-03)

- Summoner: a different named ally per input; measured, none persists past
  its own move (`jus-4ocm`).
- The **neutral Y summon has a proper hitbox/body**, like another battle
  character or a support: abilities and attacks that stop on a character stop
  on that summon. The owner thinks no other summon behaves like that
  (`jus-kq7n`). Known cases: **Kakashi 4-koma X beam stops on it**;
  **Kinnikuman's grappling specials grab it** and play the whole throw
  animation holding nothing.
  Only an **enemy's** attack stops on it; an ally's passes through, so the
  test needs Taikoubou on the CPU side and Kakashi 4 (or Kinnikuman) as P1.

## Kinnikuman `65` (2026-09-03)

- Wrestler; his specials are grappling grabs. They connect with anything
  that counts as a body, including Taikoubou's Y summon (`jus-kq7n`).
- Air Y **can hit twice**, as the guide says, but only if the victim is
  against a wall or gets knocked back into the projectiles' return path. The
  projectiles carry their own knockback, so the second hit is rare; one hit
  from open ground is the normal case (the 2026-09-03 measurement).

## Yoh (White Swan) `26` (2026-09-03)

- Regular Yoh `25` with a different sprite and slightly different hitboxes;
  the real difference is the X specials. The 6-koma X inflicts launcher state
  plus blind.

## Goku (2026-09-02)

- Up+X (4-koma): Goku leans back, yells and sends out a speech bubble; the
  bubble freezes the victim and applies some knockback on hit (`jus-law`).

## Luffy `12` / Franky `17` (2026-09-03)

- Luffy up+Y keeps hitting while Y is mashed. Franky's Y moves are powered up
  in two steps by his Ultimate Action (cola). Likely homes for the
  unreferenced hitbox records (`jus-hitbox-record-selection-u3ig`).

## Projectile interaction / move priority (2026-09-09)

- Owner recalls moves that **feel high-priority**: they "eat" other projectiles
  more often than not when the two meet. Not attributable to a specific
  character yet — asked for a concrete repro pair (attacker move + opponent
  projectile) to use as the runtime test case.
- Beam-type projectiles are a confounding variable the owner flags explicitly:
  they may behave differently from ordinary projectiles in exchanges.
- Recorded against `jus-hitbox-priority-clash-1evz`: the 2026-09-09 static
  pass found no strength-comparison layer in the damage path, so the "eating"
  must emerge from projectile HP + bucket routing + entity lifetime (despawn),
  the per-field min/max picks, or buckets 5/15/16/21 — all still to be
  reconciled with this testimony before GAP 1 closes.

## Owner answers on projectile interaction (2026-09-09, same session)

- **Repro pair for "eating":** Yusuke **6-koma X** is high-priority and "eats a
  lot of things." No dedicated save state yet; owner offered to list projectile
  characters for opponents.
- **Beam vs beam:** usually they **cancel each other out** (both disappear).
- **Beam vs projectile:** **usually the projectile wins.**
- Note the apparent tension to resolve in runtime data: if Yusuke 6 X is itself
  beam-class, it is an exception to "projectile usually wins" — or it wins on
  attrition (damage/HP), which is what the static model predicts. Capture will
  disambiguate.

## Momotaro vs Yusuke projectile conflict (2026-09-10)

- Owner built the deterministic state
  `pc-momotaro-npc-yusuke-projectiles-about-to-collide` (pause-menu save,
  paused right before the projectiles meet): Momotaro forward+Y projectile vs
  Yusuke forward+Y projectile.
- **Momotaro's projectile wins every time.**

## Owner projectile-interaction save states (2026-09-10)

Owner supplied 11 pause-menu save states in
`<STATES>/projectile-states/`, each paused with a
projectile launched or about to launch, for tracker item `jus-2s9k`. Owner's
description of each, verbatim in substance:

- `pc-hitsugaya-airy-npc-ichigo-fy`: Hitsugaya's air Y creates a big chunk of
  ice in the air. Ichigo's uncharged forward Y is about to make contact
  with it.
- `pc-ichigo-fy-vegeta` and `pc-ichigo-charged-fy-vegeta`: no projectiles
  colliding. Ichigo's uncharged forward Y in one, his charged forward Y in
  the other. Charging forward Y increases its damage, speed, size, and
  knockback (owner).
- `pc-vegeta-x-ichigo-x`: owner (Vegeta, right side) fires the X beam
  special; Ichigo fires his X projectile from the left. The projectile
  passes through the beam but does no damage or knockback to Vegeta when it
  reaches him (owner).
- `pc-yugi-fb-npc-vegeta-fy`: Yugi throws dice down-right. Dice are
  notoriously "high priority" and eat a lot of stuff; they seem to persist
  for as long as their animation runs, no matter what, right through beams
  (owner).
- `pc-yugi-fb-npc-vegeta-x`: dice summoned on the left; Vegeta X beam comes
  from the right aiming left. The beam hits the dice but they keep moving;
  the beam hits Yugi, but the dice keep making "contact" with the beam for
  their duration (owner).
- `pc-eve-x-npc-vegeta-x`: Eve summons feather projectiles and shoots them
  left; Vegeta fires his X beam right, eating her projectiles and then
  hitting her (owner).
- `pc-taikoubou-upx-npc-kakashi-x`: Taikoubou (right) summons a tornado;
  Kakashi (left) fires a beam; the beam stops on the tornado and keeps
  stopping wherever the tornado is as it travels left (owner).
- `pc-mashirito-y-npx-yusuke-fy` (sic, "npx" in filename): Mashirito's Y
  creates a chest that explodes on contact. The chest and the explosion seem
  to have different classifications from a player's perspective (owner).
- `pc-mashirito-fy-momotaro-x`: Mashirito's forward Y sends out a walking
  poop (traveling left in the save). Like Yugi's forward B it persists and
  is never canceled; it travels its distance then explodes. In the save,
  Momotaro's X hits it.
- `pc-mashirito-fy-npc-momotaro-b`: a melee attack (Momotaro B) hitting the
  walking poop. Melee attacks also seem to have some level of priority:
  sometimes one character's attack is overridden and they take damage
  ("losing" the interaction), sometimes the hitboxes collide and cancel each
  other out so no one takes damage (owner).

Owner earlier (2026-09-09) stated beam vs beam usually cancel both and beam
vs projectile usually the projectile wins; the Vegeta X and Kakashi X states
above are beam cases to test that.

## Charge / empowerment (2026-09-11)

Owner vocabulary: a **charge** is the action that sets an **empowered** state on
the character's own moves. Charge is **not** always the Ultimate Action.

**Per-character charge inputs (owner, corrected 2026-09-11):**

- **Ichigo**, base 4/5/6-koma form: charge either with the Ultimate Action
  (select) **or** by using his neutral Y and tapping so it plays its full
  animation to completion. Ichigo's 7/8-koma is a **different form** (charge
  input not stated for it).
- **Franky, Fuusuke, Yusuke, and Gear 2 Luffy** (Luffy's 7/8-koma form): charge
  with the Ultimate Action.
- **Fuusuke, Ichigo, G2 Luffy**: their Ultimate Action is "press the button and
  you get empowered after the animation finishes".
- **Franky**: his Ultimate Action drinks one of **3 random bottle colours**.
  One colour empowers; the other two do not. Drinking the empower colour a
  second time empowers him **further, maxing at two**.
- **Yusuke**: his Ultimate Action charges as you hold it — he starts with one
  animation and, as you hold, the sprite changes to a **second** animation.
  Yusuke himself is empowered only once he reaches that second animation.
  Holding just long enough for the first animation to start, then switching to
  Ichigo, leaves **Ichigo fully empowered**.
- **Raoh**: empowered by his **Y attack**. His Ultimate Action only regains SP
  and does **not** give the empowered state.

**Empowerment transfer matrix (owner, 2026-09-11):**

- Ichigo's projectiles are empowered after: his own charge; Yusuke taps charge.
- Yusuke's projectiles are empowered after: his own full charge; Franky charge
  lvl 1.
- Franky's Y attacks have two levels of empowerment. Only level 1 has been
  reached by transferring charge through a character switch; that happens after
  Yusuke fully charges, or his own charge used once.
- Fuusuke's Y attacks are empowered after: his own charge; G2 Luffy's charge;
  Raoh's charge. They are **augmented strangely** by Yusuke tapping charge and
  by Ichigo's charge — not empowered: forward Y is invisible, up Y acts
  empowered (a third hit) but always goes straight up where it is normally
  aimable, down Y and air Y act completely normal.
- Raoh's attacks are empowered after: G2 Luffy's charge; Fuusuke's charge.
- "I tried most other combinations and they lead to no change in empowerment.
  Cannot recall other characters that 'empower' themselves like this." (owner)

## Ichigo Y projectile variants (2026-09-11)

Owner testimony (verbatim, 2026-09-11): "I'd like to look into what kinds of
differences there are between Ichigo's Y projectiles. AirY and upY both fire
the same projectile as fwd Y, at different angles. Do they use the same
pointers / bytes / whatever in the backend too?"

Four owner pause-menu saves were ingested for this question, for `jus-puc7`:

- `pc-ichigo-airy-charged` — Ichigo air Y, charged.
- `pc-ichigo-airy-uncharged` — Ichigo air Y, uncharged.
- `pc-ichigo-upy-charged` — Ichigo up Y, charged.
- `pc-ichigo-upy-uncharged` — Ichigo up Y, uncharged.

Follow-up testimony, same day, on the four states:

> I tried to make sure I paused at the very beginning of the animation for each of those saves. the projectile is not spawned yet on any of them

## Owner projectile-conflict states for jus-pebk (2026-09-11)

Eight owner pause-menu saves, each paused right before two projectiles meet,
imported to `jus_files/save_states/` for `jus-pebk`:

- `pc-yugi-fb-npc-momotaro-fy`: Yugi dice vs Momotaro fwd Y. They pass through
  each other. Both projectiles still exist, no collision effect in the UI, and
  fwd Y passed right through Yugi without damaging.
- `pc-yugi-fb-npc-yusuke-x`: Yusuke X passes through Yugi dice and the
  collision effect IS shown; then Yugi (owner) takes damage when Yusuke X
  hits.
- `pc-naruto-fy-npc-yusuke-x`: Yusuke X eats all 3 of Naruto's fwd Y shuriken;
  they vanish with the collision effect and Naruto takes damage.
- `pc-yugi-y-npc-yusuke-x`: Yugi Y summons a swordsman who swings downward and
  sends a wave projectile. Owner is not sure whether Yusuke X passed through
  it or they cancelled out — either way, X then hit Yugi.
- `pc-taikoubou-upx-npc-yusuke-x`: Yusuke X hits Taikoubou's tornado and
  vanishes. Owner thinks the tornado acts the same way a beam does but is not
  sure.
- `pc-kurama-x-npc-yusuke-x`: Kurama's X has super high priority and eats
  Yusuke X. Owner is not sure Kurama X is technically a projectile. This state
  also has Taikoubou's tornado out, but Yusuke X hits Kurama X first since it
  is wider.
- `pc-sasuke-x-npc-yusuke-x`: Sasuke X is not a projectile — Sasuke moves fast
  with a ball of lightning in hand, and it has high priority. Collision effect
  shown, Yusuke X vanishes, Sasuke (owner) takes no damage.
- `pc-naruto-fy-npc-yusuke-fy`: Naruto fwd Y throws three shuriken, flying left
  in this save. They contact Yusuke's fwd Y projectile; it vanishes with the
  collision effect along with ONE of the shuriken; the other two shuriken
  persist.

General (owner, 2026-09-11): Yusuke 6-koma X eats a lot; the pairs above are
the owner's chosen repro set.

- Owner (2026-09-11): Yusuke 6-koma X is a projectile. A same-day model
  inference that it is not a ColPrm/ObjShot record was retracted; the
  capture tool could not see records spawned after unpause.

- Owner (2026-09-11, follow-up on the two non-projectile-side states):
  - Sasuke X: sends Sasuke flying forward; he hits whoever he touches. The
    sasuke state may genuinely hold only ONE projectile record (Yusuke X).
    Owner added it because Yusuke X vanishes when Sasuke reaches it while
    Sasuke takes no damage: the projectile is cancelled out by a melee move.
  - Kurama X: a very fast whip flurry, known for very high priority. Incoming
    attacks either get eaten and vanish, or get neutralized and pass through
    Kurama doing no damage. The kurama state has at least two projectiles
    (Yusuke X plus Taikoubou's upX tornado, left on the field before a
    character switch to Kurama), but Kurama X itself may not be one.

- Owner (2026-09-12), answers to OWNER-QUESTIONS:
  - `pc-yusuke-fy-preroll`: Yusuke as the player (P1), paused right before
    his fwd Y goes out. Made for the slot-field check (`jus-qqiy` gap).
  - `pc-yugi-fb-npc-yusuke-x`: Yusuke had started the X but not fired it at
    the pause; it comes out about 2-3 s (roughly 120-180 frames) after
    unpausing. So the earlier 600-frame no-input runs did include the X
    firing; the slot-2 records created mid-run are the candidates.

- Owner (2026-09-12):
  - The 0.75x special damage on Jotaro is probably a passive that reduces
    incoming special damage (victim-side ability), not a move property.
  - **Dream attacks.** In a deck where hotkeys are assigned to deck members:
    switch to a member with the hotkey, then press that same hotkey again and
    it triggers a "dream attack". Then press the other hotkey: you switch to
    that other character and they fire their dream attack. Press the first
    hotkey again: you switch back to the first character and fire a special.
    This chains multi-character combos across the whole deck.
  - Confirmed (owner checked the deck, 2026-09-12): Jotaro carries the
    "reduced damage from specials" passive. The 0.75x on specials measured
    against Jotaro is that passive, not a move property.

## 2026-09-12 — time-out / sudden death (owner)

"Sudden death rules are different depending on mode. I also don't care about
pinning that down in the backend, that's easy enough to rebuild from behavior."

Ruling: the time-out / sudden-death / tiebreak rule is out of scope for the RE
effort. The combat notes §11 record the one observed session (point mode: expiry
starts another timed round; a second expiry ends in a draw with both sides at
placement 1, 0 points) as an example, marks the rule mode-dependent per owner,
and stops there (`jus-l77m`).

## 2026-09-13 — Kakashi cancel routes (owner)

"I think Y cancels into side Y and up Y, actually. up Y cancels into air B or
air Y." Context: the jus-atns.4.3 grid tested only neutral B and neutral Y as
follow-ups and found the Y-family cancelling into nothing through +40; that
result is limited to those two follow-ups. Owner testimony outranks it. To
measure: Y → side Y, Y → up Y, up Y → air B, up Y → air Y (jus-atns.4.3).
Follow-up, same day: "I might be misremembering on the Y cancel but I could've
sworn neutral Y has some ending lag that you can cancel into one of those two."
Grade: owner recollection, uncertain. Consistent with the capture: neutral Y's
boxes end at +20 (+34 foot box) and idle-return is +43, leaving 9–23 frames
of ending lag that grid 1 never probed with a directional input.

## 2026-09-13 — jump and guard uniform, dash per character (owner)

"I believe jump is uniform across characters, as is guard. Dash is not
though." Standing rule: owner testimony outranks measurement. Note the
tension with physics.md §6.4's three jump tiers (−1816/−1752/−1689 raw, apex
79/75/71 px; Sasuke tier 1 and Raoh tier 3 arcs measured bit-identical to
poked arcs, `jus-wthh`). Possible readings: the owner means jump rules (count,
hold behaviour, no per-character animation timing) rather than a ~8 px apex
spread; or the tiers are deck/koma-derived rather than character-derived.
Flagged for the owner; unresolved.



## 2026-09-13 — Kakashi SELECT is a substitution status (owner)

"The SELECT dodge might be tough to capture. Kakashi gets a status on him
that lasts some number of seconds. If he's hit while he has that status, a
log appears in his position and he can reappear somewhere (slight teleport in
any direction based on dpad input). He takes no damage." So the 60-frame
state 12 is the activation animation; the protection is a timed status that
outlives it, consumed by the first hit: no damage, a log entity at his
position, and a d-pad-directed displacement. Measure: the status field/timer
written at activation (diff Kakashi's object before/after SELECT), its
duration (hits at increasing offsets until one lands), and the teleport
displacement per d-pad direction.

## 2026-09-13 — Generated tables replace hand-written rows (owner)

Owner: "I want the hand-written rows retired once the live path is proven."

Applies to Kakashi's character page, §2. The framework's generated
regions (`<!-- kit:begin … -->`) currently sit beside the hand-written
attack/cancel/idle-return tables on purpose. Once the live acquire path
(`jus-roster-moveset-campaign-69it.1.4` live smoke) validates a real capture
end to end, the hand-written rows that the generated tables cover are
retired; hand-written prose (conditions summary, feel notes, open register,
maintainer rulings) stays. Any hand-written number the generated tables do not
yet carry moves to the open register rather than being kept as a parallel
table.

## 2026-09-13 — Run the remaining steps back to back (owner)

Owner: "instead of ticking every hour, do all ticks in sequence til done with
all 15." The 2-hour cron job is deleted. Step shape is unchanged (one
Builder, one Refuter, one fix round, checkpoint, commit, push, emulator
clear); steps start immediately after the previous commit. Estimated queue:
framework live smoke, retire hand-written rows, framework doc; jus-atns.4.9,
4.8, Portable re-review; jus-l77m, jus-tfr0, jus-atns.2, jus-atns.1, jus-pb6n
tail, collision.md §7 review.

## 2026-09-13 — Codex second opinions (owner)

Owner: add codex (model `gpt-5.6-sol`) as a second reviewer on two judgment
steps: the framework doc (`jus-roster-moveset-campaign-69it.1` child e) and
the Kakashi kit Portable re-review (`jus-atns.4`). Invocation rule stands:
`timeout 300 codex exec -m gpt-5.6-sol` with the prompt as a file argument
and `< /dev/null`, never stdin. Test-rerun Refuter work stays Claude.

## 2026-09-14 — dream-attack chain ordering depends on the first hit's hitstun type (owner)

Watching the fight-CPU fixture (`pc-kakashi-npc-jotaro-fightcpu`; the CPU's deck
is Jotaro / Sanji / Kenshin / Lenalee) chain dream attacks: Jotaro → Sanji whiffs
on Sanji. Jotaro's tap attack (dream attack) inflicts the **pop** hitstun type,
which knocks the opponent into the air and too far for Sanji's follow-up to
connect. Sanji first, then Jotaro, connects both tap attacks. Whether
Sanji → Jotaro → Sanji lands Sanji's special is not recalled. Standing rule:
owner testimony outranks measurement.



Unmeasured: the per-character dream-attack hit type table and the follow-up reach that makes Sanji-first work.

## 2026-09-14 — Yusuke is the second framework character (owner)

Use Yusuke to prove that the moveset framework maps a second character with a
new manifest under `kit/`. The archived
`pc-taikoubou-npc-jotaro-dark-tournament` state can reach Yusuke with an L tap;
his identity is verified by `jus-atns.5`. Existing fast-B and guard-release
measurements make him the cheapest second case.

## 2026-09-14 — turn off training auto-heal for the Kakashi SELECT rerun (owner)

The owner pointed out that the in-battle pause menu can turn off auto-heal.
Use that training setting before looking for a different fixture. Verify it by
poking the dynamically resolved P1 HP address down and confirming that it does
not rise, then run a no-SELECT damaging-hit control in the same batch as the
SELECT trials. The earlier captures used the fixed `hp1` address
`0x021DF1D4`, which never moved in about 7,500 logged frames, so they do not
establish whether auto-heal hid the damage or the address was stale.

## 2026-09-14 — projectile contact rule: melee caveat (owner)






The owner called out `pc-sasuke-x-npc-yusuke-x`: Sasuke X is a forward-moving
melee attack, Yusuke X vanishes on contact, and Sasuke takes no damage. The
generic rule can explain this because it applies to attack hitboxes, not only
projectile entities: an ordinary bit-clear attack hitbox can contact a bit-set
projectile and mark only the projectile. The rerun found no Sasuke-shaped
projectile record. The exact Sasuke/Yusuke pair was not logged, so that
application remains inferred.





















## 2026-09-22 — JUS has no dash attacks (owner)

Owner, in the session lead's session: "there are no dash attacks in the game"
(`jus-roster-moveset-campaign-69it.8`). So a B or Y pressed out of a dash is
the plain B or Y. No GameFAQs extract has a dash input either (moves named
"Dash ...", like Gon's side B "Dash Kick", sit on a normal direction input).
No kit manifest lists `dash_B`/`dash_Y` any more: they were retired from
`kit/kakashi.toml` and `kit/yusuke.toml`, with their claims and doc rows.
The dash captures stay on disk as plain B/Y out of a dash (Kakashi
`kakashi-kit-2026-09-12/dash_b`, `dash_y`; Yusuke
`yusuke-kit2-2026-09-22/geometry1/dash_B_idle`, `dash_Y_idle`). Yusuke's
matched plain B/Y exactly (same ids, windows and timing), which agrees with
the ruling. The dash itself is still a per-character movement fact (the
2026-09-13 note above).

## 2026-09-25 — Kakashi B → up B → Y and air B → air Y (owner)

Relayed by the session lead in the brief that approved the static cancel
extractor (`jus-cancel-table-extractor-9qry`); the "…" is the session lead's
cut, not ours:

"kakashi's b should cancel into his upB … B upB Y is a valid combo in JUS"

"his air B cancels into his air Y as well"

Grade: owner testimony. B → up B → Y and air B → air Y have no live
measurement; air B → air Y is live check (c) in `jus-cancel-live-checks-u9qr`.
The static gate (`scripts/analysis/cancel_table.py check`) cites these lines.

## 2026-09-25 — Specials are neutral X and up X only; air turning (owner)

Said to the session lead on 2026-09-25:

"side X and down X are not a thing. only neutral and up"

"In JUS, you can change direction in the air at any time"

"Turning does NOT work during air attacks, those fire in whatever direction
you were already facing"

Grade: owner testimony. So each panel has exactly two specials, X and up X. Pressing
X with side or down is just X; C1 §14 saw the same latches and damage for
side X and down X as for X. No kit or capture needs side X or down X rows.
Facing in the air: free to change outside air attacks, locked for the whole air attack.

## 2026-09-30 — Special input inventory and push guard (owner)

The owner reaffirmed: the attack specials are **X** and **up+X**. There is no separate side-X or air-X attack. Horizontal direction with X selects neutral X. Reserved engine slot names and historical capture labels do not create additional moves.

**Down+X is push guard:** press X while holding guard. If an opponent's melee attack hits that guard, the attacker is pushed back. The X press alone does not shove the opponent or start another attack special. This clarifies the guard context omitted from the 2026-09-25 shorthand that side/down chords are just X.

Grade: owner testimony, 2026-09-30. Outside guard the down chord can resolve to neutral X. Raw C1/C2/R1 labels are historical input spellings.

## 2026-09-27 — the 5- and 6-koma specials' mechanics (owner)

Relayed to the session lead on 2026-09-27. Kept in the owner's wording.

Also from this session, on the saves themselves: **most character-special
save states are recorded in deck-builder training mode, not regular training
mode**, and that changes the RAM snapshots (where things live). This is A0's
"test-play" layout (0x20 lower); capture probes must pick the layout per load.

Kakashi:

- **5-koma X (Raikiri):** hold to charge it up **so it travels farther**. The
  owner does not believe it changes damage amounts. It **always fires in the
  direction Kakashi was facing when he started charging**.
- **6-koma X (Chidori):** hold to charge so it travels farther, same rule on
  damage. **This one can change direction both before and mid-flight:** press
  back right before letting go and he'll go backwards; he can change direction
  instantly while he's travelling (**side to side only, no up and down**).
- **6-koma up X (Mangekyou):** he spawns a projectile that moves slowly in
  front of him, and **it can be moved around while it is active**.

Owner confirmed against C3 (2026-09-27, same session):
- **The X dash passes straight through a guarding dummy** — no hit, no guard —
  on both the 5- and 6-koma panels. Correct, not a bug.
- **Level 3 fires by itself at press + 95 frames.** The charge changes distance
  and level, not damage: 36 on 5-koma, 44 on 6-koma at every level.
- **The eye's steering rule:** it eases toward the held heading, ignores
  straight back and straight ahead, and keeps its heading when released.



Yusuke:

- **5-koma X (Spirit Gun):** hold to charge it up and do more damage. It was
  said to **auto-fire after a certain amount of time** — **retracted by the
  owner the same day (2026-09-27): a misremembering.**
- **6-koma X (Super Spirit Gun):** hold to charge it up and do more damage.
  **It can be held indefinitely** (no auto-fire).
- **6-koma up X (Demon combo / Awakening):** **changes his form for its
  duration.** He lunges forward and punches. **If he misses, he changes back
  to his normal form and the special is over.** If he hits, he does a
  multi-hit combo, kicks the opponent up into the air, and shoots them with
  an energy blast; then he changes back to normal.

Measured against this (C4, 2026-09-27; 33 trials on `cm-yusuke-5`, every load
checked against A0's row — `docs/research/feel-captures/yusuke-4-5koma-specials-2026-09-27/RESULTS.md`,
`docs/rebuild/characters/yusuke.md` §6b/§6c): the **5-koma X does not
auto-fire** (the shot appears at release+11 at every hold from 3 to **3600**
frames; two levels, threshold **66** frames: L1 32 damage, L2 44). The
**5-koma up X does not charge** either — holds 3-1500 all give the tap's 4 hits
at the same latches (the guide calls it chargeable), and its hit count varies
with the gap (4 / 7 / 8), logged unknown. The **4-koma X and up X do not
charge**.

Grade: owner testimony. Cross-check against the guide: KMK 5 X "the damage is
always 36; how long you charge just changes the distance"; KMK 6 X "Chidori …
44 total"; KMK 6 up X "Mangekyou … you can control the path of the eye and it
goes through walls"; KMY 5 X and 6 X both "hold X to charge".















































## 2026-10-12 (owner, in chat)

- (a) Eve 4-koma X can be tapped to extend it for more hits and damage.
- (b) Train's forward (side) Y and air Y can both be extended by tapping.
- (c) Eve's forward (side) Y is a grab: her hair goes forward, catches the opponent, and throws them behind her.

## Ultimate Actions (owner, 2026-10-12)

- (a) "Train's ultimate action (select btn) allows him to fire twice as many bullets during his airY or forward Y attacks. It's an important part of his kit."

- (c) "Oh, the charged state transferring between characters was something I looked into in a different round of research. Some characters' charges transfer and some dont. E.g. Yusuke taps the charge but doesnt go to full, then switches to Ichigo, and Ichigo behaves as if fully charged. I had various save states for characters who charge trying to show examples of who can transfer a charge and who cant"
- (d) "Franky - drinks a random drink. 1 of 3 possible ones. If it's cola, his next heavy attack is charged up. If he has cola a second time, it'll be charged even more"
- (e) "G2 Luffy - charges up at least his forward Y, I believe possibly also allowing it to guard break?"
- (f) "Buu - dunno what it actually does. He just beats his chest like a gorilla. It might give some SP?"
- (g) "Sanji - does a little spin and presents a random dish of food. Heals deckmates varying amounts based on the dish."
- (h) "Yugi - swaps himself out with another character in your deck. They become your current active fighter instead. Works even if the opponent has inflicted the "deck seal" status which otherwise prevents switching or summoning supports"


