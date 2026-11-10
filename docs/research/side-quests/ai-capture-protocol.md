# The AI capture protocol: one run, many questions

**Status:** proposed, and already demonstrated once. Written 2026-09-27 in response to the
question "why so many emulator jobs — can't we dump things from one run for many rounds of
agents?" The answer is yes, mostly, and the demonstration is `cpu-ai-levels.md` §3.22.

## 1. What the plan's "jobs" actually are, and which of them are real

In `cpu-ai-judgement-plan.md` a **job is one controlled replay** — one scenario — not one
emulator launch. The plan's 15–20 jobs decompose into two very different kinds:

| kind | why it exists | collapsible? |
|---|---|---|
| **Discovery** — "what does this field do, which branch runs, what is the id" | a *new question* appears after the last answer | **Yes, largely.** These are observational and share a fixture. |
| **Validation** — stock vs patched, then on a second character and a second geometry | a claim is only credible if it transfers | **No.** Two ROMs need two runs; a different character needs a third. |

The discovery tail is where the plan is wasteful, and it is wasteful because it assumes each
question needs its own run. It does not.

## 2. The demonstration: Astra's step 2 answered with zero emulator jobs

Step 2 asked what phase 1 waits for after movement expires, and named a specific mechanism
(the `0x02177BA4` expiry never reaching the replan path) plus its own falsifier ("the disarm
is normal, and the CPU is waiting on a separate valid constraint").

That was answered **entirely from dumps already on disk**, by joining two of them on
framecount:

- `jus_files/captures/ai_actions/tail.jsonl` — tracked in the `jus_files` submodule as of
  2026-09-28 (the whole `captures/` corpus, 806 files, 66 MB, commit `3becc4e`).
  fc 32755–33964, carries `AI+0x39/+0x3A/+0x105` and both fighters' state codes;
- `<TMP>/crew-zmdb-freezehold/hold1.jsonl` — fc 32565–35994, carries both
  `BattleAIMove` objects at `+0xC0..+0x18F`.

Result: the disarm fires normally (20 times; `+0x105 = 1` at fc 33415–33416, exactly when
`+0x180` drops to 0), both movement objects are inert from fc 33416, and the freeze is a
**phase-1 park** (`+0x39 = 1` held 456 frames) rather than a movement timeout. The plan's
falsifier fired and its target (phase 1, handler `0x0217B0F0`) was confirmed. Zero launches,
zero watches, no risk to the fixture.

**This is the protocol's whole argument.** Two captures taken for unrelated reasons, each
carrying a different half of the answer, were enough. Neither was taken with this question in
mind.

## 3. The binding constraint is ours, not the emulator's

`scripts/emu/agent_bridge.lua` refuses a watch spec over **512 bytes** or **32 watches**
(lines 346/359). Those are our own guards in our own script, and the tail is written to disk
**by Lua** (`io.open(path,"w")` + a buffered flush), not streamed over the host round-trip.
So neither number is a hardware or protocol limit:

- the byte budget can be raised in `agent_bridge.lua`;
- the real costs are emulator speed and disk;
- `dump` remains available for large regions at a single moment.

The practical consequence: a "standing capture" can carry the **union** of the fields several
future questions will need, and every later analysis reads the file.

## 4. The protocol

1. **One standing capture per (ROM, fixture).** Wide watch set, every frame, no thinning,
   no patching during the run. A capture is a measurement; a patch is a separate A/B.
2. **Choose the watch set as a superset, not for one question.** For the freeze fixture the
   union already fits the existing 512-byte budget:

   | block | bytes |
   |---|---:|
   | `AI+0x38..0x3B`, `+0x3E`, `+0x40`, `+0x48`, `+0x4C`, `+0x105`, `+0x10A`, `+0x1C`, `+0x24`, `+0xD4` | 29 |
   | both `BattleAIMove` objects, `+0xC0..+0x18F` | 416 |
   | both fighters: state codes, x, y, vx, vy, HP | 30 |
   | both engine wall words | 8 |
   | **total** | **483 / 512** |

   That single run would cover the freeze phase machine (§3.22), the movement objects, the
   bounds fields, and the fighter-side denominators the objective proxies need. Adding the
   reaction table's inputs — `[AI+0x2C]+0x38` and the 13 weights at `[AI+0x2C]+0x17..+0x23`
   — costs 13 more and still fits at 496, which would also close
   `jus-ai-reaction-band-fwik`.

   §3.23's discriminating test adds four more: `+0x3E` (1 byte), `[[AI+0x20]+0x18]` (1), and
   the movement accessor's inputs `[AI+0x24]` and `[[AI+0x24]+8]` (4 each). **The last three
   are pointer-valued**, so resolve them once at capture start and watch the resolved
   addresses — or watch the pointers and re-resolve offline. `+0x3E` alone decides whether the
   freeze holds at the knockdown-state exit or the missing-object exit, and it is a single
   byte.
3. **Version the watch set, and re-capture only when it changes** — not once per question.
   When a new field is needed, extend the set and take one new run; every question already
   answered stays answered from the old file.
   **First one taken 2026-09-28:** `docs/research/side-quests/ai-phase-capture-2026-09-28/` —
   3420 rows, 0 gaps, 23 watches / 510 bytes, latch fc 33509 confirmed. It carries the phase
   machine (`+0x39`, `+0x3E`, `+0x40`, `+0x105`), both movement objects, the resolved accessor
   object `[[AI+0x24]+8]`, the state the finalizer's guard reads, and the reaction band. Read
   it before commissioning anything for the freeze.
4. **Record the schema next to the dump** (field → address → object → unit), so a later agent
   can read it without re-deriving the addresses. `watches.json` is the existing precedent.
5. **Store it where the next session finds it**, and treat it as a corpus, not a scratch file.
   The `<TMP>/crew-*/` dumps are one `rm -rf` from gone. **`jus_files/captures/` is the
   durable home, and it is tracked as of 2026-09-28** — before that the whole directory was
   untracked, so the corpus *looked* committed and was not. A finding also gets a parent-owned
   extract beside the docs, holding the *decisive columns* rather than the full watch set, so it
   survives a submodule that stops being cloned. The first is
   `docs/research/side-quests/ai-phase-capture-2026-09-28/` (3420 rows, 16 columns, 255 KB,
   enough to re-check every claim in §3.24 offline).
6. **Never re-run to reproduce a known latch.** §3.22 shows the latch and the pre-latch
   silence are already in hand.

## 5. Revised budget

| milestone | Astra's estimate | revised | why |
|---|---:|---:|---|
| Freeze: step 2 static | 0 jobs | **0** | done, from disk |
| Freeze: step 3 J1 stock control | 1 | **0–1** | covered by the standing capture if taken |
| Freeze: step 3 J2 instrumented | 1 | **1** | GDB; needs a bridge-only control beside it |
| Freeze: step 3 J3 intervention | 1 | **1** | a diagnostic probe |
| Freeze: step 5 J4/J5 A/B | 2 | **2** | two ROMs — irreducible |
| Freeze: step 5 transfer | 4 | **2–4** | a second character and a second geometry — irreducible |
| Step 6 careless attacks (discovery) | 2–4 | **0–1** | fields already in the standing set |
| Step 7 punishment (discovery) | 2–4 | **1** | `jus-ai-reaction-band-fwik` |
| Step 8 self-KO (discovery) | 3–5 | **1–2** | needs an edge scenario, not new fields |
| **total** | **15–20** | **8–13** | |

The floor is set by validation, not discovery: **2 runs per (ROM × fixture)**, plus one GDB
run and one intervention. Everything else is a file read.

## 6. What this does not fix

- **A different character or geometry cannot be inferred from the freeze fixture.** Transfer
  evidence needs its own runs.
- **A patched ROM needs its own run**, and a savestate may restore stock overlay bytes over a
  patched session — the plan's ROM-loading gate stands.
- **A wide watch set is not free**: more per-frame work slows the emulator, so a 3400-frame
  standing capture may take longer in wall-clock than a narrow one. It is still one run.
- **This does not make discovery unnecessary** — it makes each discovery answer reusable.

## 6. Correction (2026-09-28): a capture is not an atomic snapshot

The premise this protocol rests on — "deterministic to the frame when unperturbed" — is true of
the *game* and false of the *capture*. Measured, and explained against the melonDS source in
`cpu-ai-levels.md` §3.29:

- `EmuThread.cpp:451` emits `signalLuaUpdate` after `RunFrame()`; the Lua slot runs on the Qt GUI
  thread while emulation continues on its own thread.
- `agent_bridge.lua` reads `emu.framecount()` **first** and the watches **after**, and
  `NDS::NumFrames` increments near the **end** of `RunFrame` (`NDS.cpp:1067`).
- So the emulation thread can start the next frame's RAM writes between the counter read and the
  watch reads. Two callbacks can log the same `fc` with different RAM phases, and the 23 watches
  are read **sequentially**, so a row is not atomic even in principle.

Measured rate: 5 torn rows in 12008 (~0.04%), each an isolated one-row blip that re-converges and
whose values equal the *next* row's.

**Consequences for anyone reading a capture:**

1. **Do not use bit-identity as the determinism test.** Use *no divergence that persists beyond
   one row*. A one-row blip that re-converges is a torn read; a divergence that continues is real.
2. **Re-read §3.25 accordingly.** "Bit-identical on 23 fields across 3400 frames" means "no
   sustained divergence" — at ~0.04%, 3400 rows has an expected ~1.4 torn rows, so an exact match
   was partly luck.
3. **The flag is in `agent_bridge.lua` (2026-09-28) but is not sufficient.** `plan_step` and
   `tail_step` bracket the watch batch with two `emu.framecount()` reads and write `"torn":true`
   when they differ; `tail_stop` reports a `torn` count. It catches only the case where a whole
   frame completed during the read. `NDS::NumFrames` increments at the *end* of `RunFrame`, so a
   read that straddles a **mid-frame** boundary has an unchanged counter and is not flagged — and
   that is the case that actually occurs. The only sound fix is a C++ one: snapshot the watched
   bytes on the emulation thread after `RunFrame()`.
4. **So use the signature instead.** A torn read shows the *next* frame's values: the divergent
   row equals the base's next frame in every differing field, and the series re-converges.
   `determinism_run.py`'s `looks_torn` classifies it and `diff_span` counts differing frames.
   `BLIPS ONLY` (1–3 frames) is an artifact; `NONDETERMINISTIC` (hundreds) is real.
5. **Compare on `fc`, never on row index.** Cleaning drops rows, and a dropped row shifts every
   later index and manufactures a divergence. Drop `torn` and `d > 1` rows, then walk the fc
   intersection. A row with `d > 1` is a duplicate: `plan_step` emitted several records for one
   callback and read the same memory for each.
