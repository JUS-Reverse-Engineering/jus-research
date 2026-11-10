# DREAM cancel window: C4 inheritance

PF-31o. Static ov6 disassembly, checked against existing J6FIX raw frames. No
emulator run. Code: `cancel_table.dream_entry_facts`, `unnested_offers` and
`dream_offers` (`scripts/analysis/cancel_table.py`), tested in
`scripts/tests/test_cancel_table.py` (DreamEntryFactsTest, DreamOffersTest). Oracle:
`scripts/tests/test_dream_c4_oracle.py`.

## The question

Move id 12 (the dream attack, anim 0x28, ov6 row 0x02171348: mask 0xFFFFFFFF,
misc 0x140B0B) has a ground cancel window. The decoder in `cancel_table.py`
projects row 12's mask onto the ground reader and gets no follow-ups and no
X / up X. That projection is right only if C4 (fighter+0xC4, the chain mask) is
row 12's word when the window opens. pf31i left the three Komamen `followups`
rows open because the id-12 path that skips C4 had no proof and no kit
representation.

## C4 writers

An ARM immediate-store scan of all of ov6 (`c4_stores`) finds exactly five
stores that reach fighter+0xC4..+0xC7:

| PC | Context | Effect |
|---|---|---|
| 0x02159DB8 | neutral start 0x02159D7C | C4 = 0 |
| 0x02159DF4 | neutral start, ids 13/14 | C4 \|= ~0 |
| 0x02159E20 | neutral start | C4 \|= mask[id] (0x02159E10-1C) |
| 0x02159E84 | neutral start, id 12 only (cmp 0x02159E68) | C4 \|= ~0 |
| 0x0215A578 | state-9 fire 0x0215A550, ids 1-10, 13, 14 | C4 \|= mask[id], C9++ |

In arm9, the strh at 0x020816C8 / 0x02081FF0 writes the hit-element object,
whose +0xC8 is a halfword latch. The +0xC0 word stores at 0x020797CC,
0x02089408 and 0x0203C924 write a team pointer array and globals. None of them
writes the fighter.

## The two ways DREAM starts

**Neutral start.** The ground reader 0x0215A720 returns 12 first whenever the
one-tick request +0xD1 is set (fighter message handler 0x021574CC case 4, at
0x021575DC, sets it and writes the koma slot; 0x02156EC8 clears it every
frame). The neutral start then clears C4 and ORs in mask[12] and then ~0, so
C4 is all ones. It copies the active koma +0x1CC to the snapshot +0x1D0
(0x02159E88-90) and sets +0xD2 = 1, +0xD3 = 0. The window offers nothing:
`dream_offers(None) == ([], False)`.

**Cancel entry (id 12 fired from a window).** State 9's per-frame reader
(handler 0x02159EF8, body from 0x0215A148) runs for every move id. Its only
id-dependent load is +0xCB at 0x0215A390, a counter index whose branches rejoin
at 0x0215A3B8. While +0xF3 is set (ground) the latch takes id 12 testing C0
only (0x0215A4B4-BC). The fire case is system_jump[1], 0x0215A590 to
0x0215A618:

- it requires the fighter to be grounded;
- it compares +0x1CC with +0x1D0;
  - if they differ, it starts DREAM (12);
  - if they are equal, it starts X (13) or up X (14, +0x6C bit 0) for one SP bar;
- it sets +0xD2 = 1 and +0xD3 += 1;
- it has no load or store of +0xC4..+0xC7 (`fire_path_c4_access == []`).

The tail stores the id to +0xCA and clears +0x14, so the same handler
re-initialises the new move on the next tick. The neutral start's C4 writes do
not run on that tick. C4 is therefore exactly what the cancelled move's chain
left.

## Offers after a cancel entry

DREAM's window opens at its key (Train 30, others per `cancel-table.json`) with
the ground reader. It offers the ground projection of the inherited C4. For a
chain entered through the readers, C4 is the last move's own mask:
`unnested_offers() == []` shows that every target t of a window of m has
mask[t] ⊇ mask[m]. So a DREAM entered by cancelling move m offers m's own ground
`into` and, if m's window has one, its special. A DREAM cancelled from a DREAM
window passes the same C4 on. A neutral DREAM offers nothing.

## X / up X entered through the id-12 branch

The id-12 fire chooses its move by comparing the snapshot. When +0x1CC equals
+0x1D0, 0x0215A590 starts X (13), or up X (14) when +0x6C bit 0 is set. It does
this under the same grounded and 1-SP-bar gates, and it does not touch C4.
That X / up X keeps the inherited C4, so it is **not** proved terminal.

The "cancelled X is terminal" law (`special_cancel.terminal`) is sound only
when scoped to a normal's `special_cancel`. That X / up X is reader id 13 / 14,
fired through 0x0215A550. It ORs the all-ones mask[13 | 14] into C4, and the
only exception is a DREAM requested out of it, whose latch skips C4. The
existing D3 `special_cancel.terminal` rows describe that ordinary edge only.
An engine must not make "terminal" an unconditional property of X.

## Independent oracle: J6FIX raw frames

`docs/research/feel-captures/2026-10-25-j6fix-dream-exit` was captured to
explain Train's DREAM exit, not this law. Its 25 runs record P1 fighter
+0xC0..+0xF7 and +0x1CC..+0x1E7 every frame. Decoded straight from the raw
frame rows:

- 21 neutral starts (+0xD2 rises with +0xD3 = 0): C4 = 0xFFFFFFFF, C9 = 0,
  CA = 12, D0 = CC in every one.
- 22 fire entries (+0xD3 increments): C4, C9 and D0 are unchanged across the
  entry tick. CA = 12 exactly when CC ≠ D0, otherwise 13 / 14.
- C4 never changes while the state stays 11, and C0 is 0 in every frame.
- +0xF3 rises exactly at the decoded DREAM key after both kinds of entry:
  Train (bc_b_02) 30, neutral and fire; Kakashi (na_b_04) 16, neutral and fire;
  Eve (bc_b_01) 16, fire.

Every captured fire entry came from a DREAM window, so the inherited C4 the
oracle sees is all ones. It confirms that the fire path does not write C4. It
does not exercise a normal → DREAM cancel.

## Reachability limit and capture cells

The law above covers any C4 the fire path inherits. Whether a normal attack's
window can latch id 12 depends on +0xD1 being set during that window. The
sender of fighter message 4 is arm9 deck code, which was not traced. So the
law is complete, but which source moves reach it is not proved. The cells that
would settle it:

- **Fixture:** the hotkey fixture `dc1b-yusuke4-kakashi4-npc-jotaro-idle`.
- **Cell 1:** a ground normal with a ground window (Yusuke B). Re-press the
  active koma's hotkey inside its window, before any neutral DREAM. Repeat
  after one neutral DREAM, so that D0 = CC.
- **Cell 2:** the same press, then a follow-up normal (Y) and X inside DREAM's
  window.
- **Watch:** C0, C4, C8, C9, CA, CB, D1, D2, D3, F3, F4, +0x1CC, +0x1D0, the
  state byte, input edges, and the animation id and frame, every tick.

## Kit representation

The kit DREAM `cancel` is `{frame, into: [], kind: "ground", inherit: true}`. `frame` is CT's start, and `into: []`
plus no special is the neutral case. `field_closure` closes row 12's
`followups` only as a view of the whole decoded window, the native all-ones
row-12 mask, and that exact `cancel`. It proves the entry-state
transformation, not an input edge.
