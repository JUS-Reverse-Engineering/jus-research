# Findings: no strength-comparison layer in the damage path — the hit-resolution order

2026-09-09. Static. Tracker item `jus-hitbox-priority-clash-1evz` (moves GAPS 1, **static
part** — see the owner-testimony caveat at the end).
Worker: deepseek-v4-flash (general-purpose). Second opinion: `codex exec -m
gpt-5.6-sol`, neutrally framed (Q1–Q6), in full agreement on every load-bearing
point. Orchestrator spot-checks matched.

**Headline (scoped):** there is **no hit-tier / hit-properties / strength comparison
anywhere in the collision→damage path.** The runtime walker is located (the bucket-1
pair body `0x02080F14` + siblings). Resolution order is **bucket order, then
pair-list insertion order**; multi-pair damage is **additive** into the victim's
class-indexed arrays, plus independent per-field min/max "winning hit" picks. The one
pairwise authored-field comparison (CollisionEntry byte `+0x00`, "kind") is **pair
orientation** (which member is the plain box), not strength.

**Scope caveat (owner testimony, 2026-09-09, outranks this finding):** the owner
recalls moves that reliably **"eat" other projectiles**, and flags beam-type
projectiles as a confounding variable. That behavior is NOT explained by this pass
and does not contradict it: this census covered the damage path only. The eating
must emerge from the entity layer — projectile HP + bucket-1 routing + despawn
(`jus-964r`, `jus-n53r`), the per-field min/max picks below, buckets 5/15/16/21
(spot-checked only), or beam entities' multi-record structure. GAP 1 stays open
until reconciled; OWNER-NOTES.md 2026-09-09 carries the testimony.

## 1. The walker (GAP 1's "runtime collision walker reading the 20-byte records")

`0x02080F14` (bucket 1, the damage path), `0x02081B20` (bucket 2, knockback),
`0x02081D68` (bucket 3), `0x02081DDC` (bucket 4, bit-11 path), `0x020826A0`/
`0x02082780`/`0x02082984` (buckets 15/18/19), fold `0x020821C4`. Pairs are
per-record, walked from `[[record+0x60]+0x10]` by the pre-pipeline filler
`0x0207FBD0`; pair node `+8` = A (victim) participant, `+0xC` = B (attacker).

## 2. One-sided record reads — a tier test is structurally impossible

In `0x02080F14` there are **11 loads of `[r6,#0x10]` (attacker CollisionEntry) and
zero of `[r5,#0x10]` (victim)** (codex census). The damage formula `0x020823E4`
likewise loads its CollisionEntry only from arg1 (attacker); the victim is reached
only via its record (`[r0+0xC]`) for `+0x40`/`+0x175`. All ten register-vs-register
`cmp`s in the pair body are accounted for: same-attacker identity dedup
(`0x02081188`, gated by attacker `elem+0x14 & 0x3000000`, consulting the per-victim
landed list `record+0x28`), HP-gain cap arithmetic (`0x02081480`), SP-drain
arithmetic (`0x020814D0`), the four per-field min/max picks (§4), and a transform-X
comparison for knockback direction (`0x020818A8`, `[record+0x5C]+0xC` of both
sides — position, not authored strength).

## 3. The kind comparison is orientation

`0x02080128-0x02080134` (and the `0x02080174/0x020801BC` arms): loads byte `+0x00`
of **both** CollisionEntries, `A == B` → no helper at all; `A >= B` → skip;
`A < B` → `0x020809C8`. Element construction makes `elem+0x14` bit 28 set / bit 29
clear when `kind != 0`, bit 29 set / bit 28+12 clear when `kind == 0`
(`0x0207D4D8-0x0207D518`, mask `0xEFFFEFFF`) — so bucket 1 (damage) is entered only
with the **plain box (kind 0) in the A/victim slot and the attack (kind > 0) in the
B/attacker slot**. It is a role test; there is no "highest kind wins" and no use of
kind magnitude beyond zero/nonzero.

## 4. Multi-pair resolution: additive + per-field min/max

Every pair that reaches the bucket-1 body accumulates (`record+0xA4/+0xEC` class
slots, `0x020812C8-0x020812F4`; the `0x37F0` gate only skips the contact-array
route). No "pick one pair" step exists. The per-victim "winning hit" fields are
independent per-field picks against the victim's stored value — never a
second attacker:

| field | CollisionEntry byte | rule |
|---|---|---|
| `record+0x16C` | `+1` (u8) | keep **max** (`strhlt`, `0x020815F4`) |
| `record+0x174` (+pos `+0x14C/+0x14E`) | `+2` (u8) | keep **min nonzero** (0 = empty, `0x02081624`) |
| `record+0x172` (+class `+0x168`) | `+3` (s8, ≥0 arm) | keep **min** (`0x020816B8`) |
| `record+0x173` (+class `+0x16A`) | `+3` (s8, <0 arm) | keep **min signed** (`0x020816F0`) |
| `record+0x182` | `|+3| == 0x17` | OR in attacker `elem+0x14` low byte (`0x02081720`) |

This is the closest thing to "strongest wins" in the code, and it is per-field, not
per-pair: `+0x16C` can come from attacker X while `+0x172` comes from attacker Y.

## 5. Trades and clashes

- **Same-frame trade (both attacks connect):** two victim-side pairs, each routed to
  bucket 1, each resolved independently — both victims accumulate. No cross-pair
  guard exists.
- **Attack-box vs attack-box overlap (the literal clash):** equal kinds → bucket 7;
  unequal kinds with non-plain A → bucket 8. Their consumers `0x02080C70`/`0x02080E5C`
  are VFX-only: geometry via `0x02080D28`, effect spawn `0x0206C7FC` (constants
  `0x0021000E`/`0x0021000D`), sound `0x0207342C` (r0=0x7A, r1=0x2A). **No
  CollisionEntry is read, no record field written, no damage, no cancel.**

## 6. CollisionEntry byte census at runtime (hit-test path)

Bucket 1 (`0x02080F14`): `+0x01` (max pick; `cmp #6` selects KB/HP-band table),
`+0x02` (min pick, position, effect spawn), `+0x03` (signed min picks, class bytes,
0x17 special), `+0x05` (SP damage), `+0x07` (hitstun add → `record+0x171`), `+0x08..0x0B`
(propMask: `0x8000` HP-gain transfer, `0x10000` SP drain; construction-time T14/T18/T1C),
`+0x0C`/`+0x0D` (kbX/kbY), `+0x0E`/`+0x0F` (shake rows → `0x02153CE8` args),
`+0x10`/`+0x11` (see §7). Formula (`0x020823E4`): `+0x00` (kind 4/5 body/band
bonus), `+0x04` (base damage), `+0x0E` (multiplier-table element index, clamp 0..15).
Bucket 2 (`0x02081B20`): `+0x06`, kbX, formula bytes. Bucket 4 (`0x02081DDC`):
`+0x04`/`+0x05` (HP/SP deltas), `+0x03`/`+0x01` (same picks), shake/effect bytes.
Routing prefilters read both sides' `+0x00` only.

## 7. Correction: `+0x10`/`+0x11` ARE consumed

`move_records.py` marks `+0x10` "hitTier — no consumer located" and `+0x11`
"hitProperties — no consumer located". Both are consumed: `0x020819FC`/`0x02081A08`
(bucket 1) and `0x02082110`/`0x02082118` (bucket 4) pass them as args 7/8 to ov6
`0x02153CE8`, which uses `+0x11` to index a halfword table at `0x02171E0C (→
vtable+0x104 indirect call)` and `+0x10` to index a word table at `0x02171E1C
(→ cmp #0x1000, bl 0x20235dc)`. Both tables read zero in the static image (writers
exist at ov6 `0x0217170C` etc., ov5 `0x0216B3CC`; not decoded) — whether they
encode an ordered "tier" is open, but the consumers are live. **This is the one
remaining place a priority-like semantic could hide in this path.**

## 8. Falsification tests

1. Bucket-1 orientation: break at `0x02081280`; predicted `[[r5+0x10]]==0` (plain)
   and `[[r6+0x10]]>0`.
2. Equal-kind clash is VFX-only: two overlapping attack boxes → break at
   `0x02080D00`/`0x02080D0C` fires, no `record+0xA4` slot or `+0x134` write.
3. Multi-pair additive: two attackers, one victim, one frame → both class slots
   nonzero, `+0x134` = sum.
4. Per-field independence: two hits with swapped `(+1,+3)` magnitudes → `+0x16C`
   and `+0x172` from different pairs.
5. `+0x10/+0x11` live: poke `+0x10` → changed `0x02153CE8` dispatch.

Unresolved: pair-node generation (who allocates into `[record+0x60]+0x10`);
`0x02171E0C`/`0x02171E1C` table writers and semantics; buckets 5/15/16/21 (push-apart/
position, spot-checked, no CollisionEntry pair comparison); the owner's
projectile-eating behavior (entity layer).
