# The reaction pointer table holds start handlers

Tracker item: `jus-reaction-table-start-handlers-8l0w`. Static read of the ROM, with one savestate
corroboration, 2026-11-13 intake. Cross-check source: Keshire's Ghidra export
([keshire.md](../external/keshire.md)), which lists the same distinct values.

The reaction pointer table at 0x021721A0 holds start handlers. The addresses seen latched at
runtime are their continuations.

## Table

16 entries, indexed by reaction:

| Reaction index | Start handler |
|---|---|
| 0, 1, 2, 7 | 0x0215B6A0 |
| 3 | 0x0215B72C |
| 4 | 0x0215B7CC |
| 5 | 0x0215B870 |
| 6 | 0x0215BA40 |
| 8 | 0x0215B68C |
| 9 to 15 | 0x0215B568 |

## Continuations

Each start handler stores its continuation into obj+0xFC and returns, so the slot is
replaced on the next tick.

- Reaction 3 installs 0x0215B784 (store at 0x0215B778).
- Reaction 8 and reactions 9 to 15 install 0x0215B648 (stores at 0x0215B690 and 0x0215B61C).
- The four addresses earlier docs cited are 0x0215B720, 0x0215B818 (reaction 4), 0x0215B910
  (reaction 5) and 0x0215BAB8 (reaction 6). They were read from obj+0xFC after the hit frame.

A training-mode savestate holds obj+0xFC = 0x0215B910.

Both readings are right about different things: the table holds the start handlers, and
obj+0xFC after the hit holds the continuation. The earlier statement in the physics
reference that the static addresses are not the table's pointer values was wrong.

## Get-up chains

- Falldown (reaction 4): B7CC, B818, B84C, BC44, BC8C.
- Clean pop (reaction 5): B870, B910, BB34, BB78, BC44, BC8C.
- Launcher (reaction 6): BA40, BAB8, BB34, and onward.

(Addresses are 0x0215xxxx with the prefix omitted.) The continuations were traced during the
intake.
