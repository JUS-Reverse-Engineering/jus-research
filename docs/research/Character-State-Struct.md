# In-battle character state struct

> Historical February 2026 map: see the [archived struct map](archive/Character-State-Struct-2026-02.md). It is superseded; this page's current reference is the character-init copy table.

## Fields established from the character-init copy (2026-08-14, Loop-Atlas K3)

The init function `0x02077C0C` copies `chr_b.bin` data into this struct. That fills part of the
`0x0000 - 0x003F` region this document lists as "Unknown", plus two fields in the `0x0040 - 0x0069`
gap. Source: `findings/k3-chr_b-to-battle-copy.md`.

| offset | source | contents | evidence |
|---|---|---|---|
| `+0x10` | `chr_b[0x02]` signed | 5 values `2..6`. **REFUTED as `tier`** (that's `+0x11`). **Walk-speed class** (2026-09-02): ov6 `0x02158A10` reads it as the index into the s16 table at `0x02171108` (107/96/85/74/62 raw/frame for 2..6) and stores the result in the fighter object `+0xB8`; verified on four bodies (physics.md §6.2, `jus-movement-speed-runtime-0luv`) | init copy (K3 finding, §source above) |
| `+0x11` | `chr_b[0x01]` signed | **the damage-formula `tier`**; also indexes the **jump-impulse table** `0x02171118` (−1816/−1752/−1689 for tier 1/2/3 → fighter object `+0xBA`, physics.md §6.4). Values `{1:11, 2:56, 3:7}`, and `chr_b-Complete-Mapping.md` independently documents tier `1`→−1, `2`→+0, `3`→+1. Goku and both damage targets read `2`, giving `tier-2 = 0` and `damage = damage1/5` exactly — matching B = 8.000 with `damage1 = 40` | init copy (K3 finding, §source above) |
| `+0x13` | `chr_b[0x00]` | **base nature** (`0`=力, `1`=知, `2`=笑) | init copy (K3 finding, §source above) |
| `+0x14` | per-size record `+0x2` | 3 values `{0,1,2}` over owned sizes | unknown |
| `+0x15` | per-size record `+0x3` | 3 values `{0,1,2}` over owned sizes | unknown |
| `+0x16` | per-size record `+0x0`, `<<6` | **max HP** | init copy (K3 finding, §source above) |
| `+0x18` | copied from `+0x16` | **current HP** (starts at max) | init copy (K3 finding, §source above) |
| `+0x2E` | `chr_b[0x30]` halfword | 56 distinct, `0..570` — looks like an ID | unknown |
| `+0x30` | per-size halfword at `chr_b[0x32]`, stride 2 | 133 distinct, `0..572` — per-size ID | unknown |
| `+0x34` | — | **pointer to the panel's `koma.bin` record**; its `+0x8` (size−1) drives all per-size indexing | init copy (K3 finding, §source above) |
| `+0x41` | — | **`chr_b` index** | init copy (K3 finding, §source above) |
| `+0x49` | per-size record `+0x1` | **regen rate**. Uniformly **1** across all 174 owned-size records; the init's "default to 4 if zero" branch never fires for a real panel | init copy (K3 finding, §source above) |

> **Correction to the HP citation below.** This document cites `0x021DF1D5` as "Player 1 HP". Two
> problems, both since established: HP is a **u16** and that address is only its **high byte** (the
> 1/4-scale reading) of **deck HP record** 0 (the 0x50-byte per-deck-character record, `rec+0x00` HP,
> `rec+0x03` charId, `rec+0x24` active flag; `HP-And-Damage-Runtime-Findings.md` §1,
> `jus-slot-name-collision-agh5`), and absolute battle addresses are **session-local** — the same struct was seen at
> `0x021DF19C` and `0x021DF1B4` in different sessions. Use the struct offset `+0x18`, and locate the
> struct with `scripts/emu/find_battle_structs.py`.

> **AR base identity (2026-09-02, `jus-fighter-object-identity-c56i`).** In local-mode battle states `0x021E2A7C..0x88` hold code bytes;
> the 4-slot table of ov6 fighter objects is at `0x021DEB3C` (`0x02228E80` P1, `0x02230D60` P2). The AR
> offsets `+0x88`, `+0xA0`, `+0xD9..DB`, `+0x102` line up with that object's status id, status word, air
> state and guard gauge, so the AR "character struct" is most likely the fighter object, not `char+0x56C`.
> Only `+0x78` (0x22 on ground) does not match it.
>
> **Resolved 2026-09-02 (`jus-fighter-object-ar-plus-0x78-p7um`).** The raw code text
> ([AR-Codes-Raw.md](AR-Codes-Raw.md)) shows two different bases: the status / jump / defense codes deref
> `[0x02181B28]` once, and that word reads `0x02228E80` = the P1 fighter object live (`feel-captures/guardbreak-2026-09-02/runtime-report.md` §7).
> The Ground/Air code derefs `[[0x023D2A74]+0x10]` and writes its `+0x78`; in local mode `0x023D2A74`
> holds garbage, but the byte that is `0x22` grounded / `0x00` airborne is the ColPrm scratch block's
> `H+0x78` (P1 `0x0220F384`; `0x20` on the launch frame, `0x02` on the landing frame). `H` is reached
> from the fighter object as `[[obj+0x1a8]+0x10]`, so the AR chain is the same shape with a different
> root. The `+0x78` row in the archived map belongs to `H`, not to the fighter object.

> **Struct identity caveat.** The table above came from static analysis of the init function. The
> archived map came from GDB on base pointers `0x021E2A7C`+ (wifi mode). They are **plausibly** the same
> struct type, but that identity is not proven. `Battle-Engine-Map.md`'s open question **B10** is the
> same question.
