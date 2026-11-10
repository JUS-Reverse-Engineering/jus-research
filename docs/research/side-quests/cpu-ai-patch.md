# Combat CPU patch: first-pass investigation notes

**Historical record. Superseded for structure, the decision gate, and patching by
[cpu-ai-levels.md](cpu-ai-levels.md), which is the current document for this
question. Read that one first.**

This document preserves the first investigation pass outside the main
combat-engine reverse-engineering work. It is kept for provenance: its claims
stand as they were written on 2026-09-14, including the ones a later
second-opinion review corrected. Where this file and `cpu-ai-levels.md` differ,
the newer document is right. The specific corrections are listed in its
sections 2.2, 2.4, 2.5, 3.1 and 3.4.

First investigation: 2026-09-14. No ROM patch or live difficulty comparison was
produced at that time. The findings below come from static inspection of local
binaries. Player observations and proposed changes are identified separately.

## Goal and player observations

The user wants to understand the game's three combat CPU difficulty settings and discuss a patch that makes the CPU play better. All three settings are easy for a player with some game knowledge to beat.

The user reports these weaknesses:

| Weakness | Observed behavior |
|---|---|
| Careless attacks | The CPU commits to attacks without sufficient judgment. |
| Accidental self-KOs | The CPU sometimes walks or jumps off a ledge and dies. |
| Poor punishment | The CPU does not punish openings well. |
| Excessive defense | Against Yugi 4's X beam, the CPU guards even inside the dead zone close to Yugi, where the user says it can attack him safely while the beam remains active. |

These are user-reported observations, not measurements reproduced during this investigation. The Yugi example is the strongest initial test because it supplies a specific move and a spatial boundary between safety and danger.

The initial suggestion from a peer was to compare identical situations across difficulty settings and look for reaction delays, attack delays, movement randomness, and weighted choices. Static inspection supports the presence of probability gates and cooldowns. It does not yet connect those mechanisms to these reported weaknesses.

## Static findings

All overlay addresses in this section refer to **overlay 11**, loaded at `0x02172A60`. Other overlays share this address range. An address without its overlay identity is insufficient evidence.

### Profile selection

| Evidence | Interpretation and limit |
|---|---|
| `BattleAI_Create`, `0x02172A60`, accesses the resource descriptor at `0x021816C0`. Its string pointer is `0x021817AC`, naming `chr/ai/ai_param.bin`. Instructions `0x02172AF4` through `0x02172B34` retain the loaded pointer at AI manager `+0x24`. | Connects the global profile file to AI initialization. |
| ARM9 getter `0x02070CDC` returns `0x020B0004 + player_index * 0x4C`. AI setup reads byte `+0x34` at ov11 `0x021730DC`. | The profile selector read by this path is at `0x020B0038 + player_index * 0x4C`. Its relationship to the three menu settings is unresolved. |
| Call site `0x021730F8` passes that byte as `r2` to `BattleAIState_Create`, `0x02178FF8`. | Setup substitutes zero when battle root `+0x154` equals 5. This investigation did not establish the meaning of mode 5. |
| The constructor calls `0x02179648`. Instructions `0x02179684` through `0x0217968C` calculate `resource_data + selector * 0x30` and copy `0x30` bytes into the new state. | The selector indexes a profile copied during construction. Editing the configuration after loading a saved battle may leave the active profile unchanged. ARM9 copy routine `0x02051890` takes source `r0`, destination `r1`, and length `r2`. |
| `jus_files/chrbin/chr/ai/ai_param.bin` contains 4272 bytes. | At the proven 48-byte stride, it contains 89 profiles. Do not label rows 0, 1, and 2 as the three difficulty settings without evidence. |
| Instructions `0x02173100` through `0x02173114` copy state byte `+0x2E` to per-player AI `+0x104`, capped at 7. Routine `0x021793A8` scans the first 81 profiles and filters using `+0x2E`, `+0x2F`, bitfields, and parameter comparisons. | Profile selection has more structure than a single difficulty scalar. The gameplay meaning of these fields remains unresolved. |

### Probability and cooldowns

The gate at `0x02179130` reads a parameter byte after checking an associated cooldown. For parameter values below 8, it indexes the word table at `0x0218190C`:

```text
64, 76, 102, 128, 166, 179, 217, 243
```

The gate accepts when the low byte of state `+0x38` is less than or equal to the selected threshold. Values of 8 or greater bypass that random comparison after the cooldown check passes. A failed comparison writes 30 to the associated cooldown. These statements concern the gate's eligible-index path; its callers and parameter indices need tracing before any modification.

Callback `0x02179694` decrements cooldowns and refreshes the cached random word through ARM9 `0x02031070`. The delay is **30 callback updates**, not a measured 30 game frames. The behavior controlled by this gate is not yet identified.

Other gates use different parameter offsets and random bit slices. For example, `0x0217920C` returns whether `(cached_random & 63) < state_byte_at_0x11`. The gate at `0x02179278` compares in the other direction. Increasing every parameter would not consistently increase acceptance or improve play.

Several gates use the same cached random word. Treating their outcomes as independent random trials would be an unsupported assumption.

### Existing move-data evidence

The earlier [battle engine map](../Battle-Engine-Map.md) calls `0x02174330` a decision function. Its entry allocates objects and registers a callback at `0x021743B0` through `0x021743B4`. It is setup code; those instructions do not establish a per-frame decision loop.

The routine reads move data through ARM9 getters `0x02078514` and `0x0207853C`, at call sites `0x021746E0` and `0x02174724`. Earlier static findings associate this data with availability and range checks. Exact semantics and refresh frequency remain unresolved.

The [battle root object map](../findings/battle-add-root-object-map.md) places the AI manager at battle root `+0x128`, with the root pointer at `0x02172960`. The [overlay map](../Overlay-Map.md) records ov11's residency and resource references.

## Proposed patch direction

These are design proposals, not implemented changes or established diagnoses. Better situational judgment is the priority. Faster reactions could otherwise increase careless attacks and accidental deaths.

| Target | Proposed behavior | Evaluation scenario |
|---|---|---|
| Ledge safety | Reject movement that leads offstage unless a deliberate aerial action has a viable recovery route. Preserve legitimate edge attacks and pursuit. | Place the CPU near an edge with its opponent across a gap, behind it, and above it. Measure accidental deaths and successful recovery. |
| Threat recognition | Check whether an attack can reach the CPU's body during the response window before selecting or maintaining defense. | Use Yugi 4's X with the CPU inside the dead zone, at its boundary, and inside the beam. Include movement across that boundary. |
| Attack selection | Consider range, facing, commitment, and likely retaliation before attacking. | Bait attacks just outside their useful range and compare decisions. |
| Punishment | Recognize recovery windows and choose a move that reaches before the opponent can recover. | Whiff the same punishable move at several distances and measure response timing and successful punishes. |

The Yugi case can distinguish at least four hypotheses:

- Threat detection uses a broad distance check or an opponent-attacking flag.
- Threat detection represents the beam but ignores its dead zone.
- The CPU begins guarding appropriately and then fails to reconsider.
- The CPU recognizes safety but an attack-selection gate suppresses the punish.

Changing a guard delay would address only some of these possibilities. No current evidence selects one explanation.

The proposed difficulty design keeps basic movement safety consistent across settings, then varies reaction delay, punish reliability, and tactical choices. An easier CPU can miss opportunities without routinely falling off the stage. This is a proposal for discussion, not an approved patch specification.

## Investigation sequence after explicit user invocation

1. Compare all three actual combat difficulty settings with the same CPU slot, character, deck, stage, and match rules. Record the selector at `0x021730DC` and the resulting 48-byte state during construction. Training idle, guard, and fight controls are separate from match difficulty.
2. Determine whether the menu changes the selector, other fields, or both. Preserve a capture of each menu setting and its initialized profile before naming any row.
3. Trace consumers of differing profile fields. Reproduce the Yugi beam case and log the guard decision, threat geometry, and attack-selection outcome. Compare the dead zone with a positive control inside the beam.
4. Evaluate a causal change by restoring the same full state, including RNG, and changing one field in the active copied profile. Repeat across several starting RNG states. Later random sequences can diverge once behavior changes.
5. Reproduce the ledge, careless-attack, and punishment cases. Measure outcomes as well as timing. Improved aggression alone is not evidence of better decisions.
6. Choose data edits, AI script changes, or code changes from those results. A shared probability-gate edit could affect multiple behaviors and modes. Confirm the affected paths before selecting a patch location.

## Evidence reproduction

These commands run from the repository root and inspect local artifacts. They do not require the temporary files from the original session.

```sh
python3 scripts/analysis/disasm_range.py 0x02070CDC 0x02070CF0
python3 scripts/analysis/disasm_range.py 0x021730D0 0x02173118 --overlay 11
python3 scripts/analysis/disasm_range.py 0x02179648 0x02179694 --overlay 11
python3 scripts/analysis/disasm_range.py 0x02179130 0x021791A4 --overlay 11
python3 scripts/analysis/disasm_range.py 0x02179694 0x021796E0 --overlay 11
python3 scripts/analysis/disasm_range.py 0x02174330 0x021743D8 --overlay 11
python3 - <<'PY'
from pathlib import Path
import hashlib
import struct

overlay = Path('jus_files/arm9/overlays/arm9_ov11.bin')
profiles = Path('jus_files/chrbin/chr/ai/ai_param.bin')
for path in (overlay, profiles):
    data = path.read_bytes()
    print(path, len(data), hashlib.sha256(data).hexdigest())
print('profile count, remainder:', divmod(profiles.stat().st_size, 0x30))
print('gate thresholds:', struct.unpack_from('<8I', overlay.read_bytes(),
                                            0x0218190C - 0x02172A60))
PY
```

SHA-256 hashes of the inspected artifacts:

| Artifact | SHA-256 |
|---|---|
| `jus_files/arm9/overlays/arm9_ov11.bin` | `1ab547c71612726599ef063d0f5909dff41c03661d97567cca873f8ef2e80db9` |
| `jus_files/chrbin/chr/ai/ai_param.bin` | `e744be3925fa448e2a7b9a0016065ca74855b54e8dc52929cfac3d0ca99ad319` |

The original inspection also used a linear ARM disassembly of ov11. Such output includes data pools decoded as instructions. Only validated code spans support the claims here. Menu mapping, behavioral attribution, and patch effectiveness remain unverified.
