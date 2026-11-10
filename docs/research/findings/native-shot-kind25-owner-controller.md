# Native shot kind 25 is an owner controller

This is offline ROM and retained-capture evidence.

## ROM rule and namespaces

The shot-file layout is 32 bytes per row. Byte 0 is shot class and word +12 is
art, decoded by `scripts/analysis/ua_table.py:270-279`. ObjShot elements are 0x6C
bytes. The initializer copies that class to element +0x1A; ov6 0x0216ADD0..ADE4
indexes the 27-word dispatch table at 0x02172864. These are classes 0..26,
not the collision record's `kind` byte, which retains its clash-tier meaning.

The dispatch table's other classes and handler addresses are recorded in
[objshot-manager-and-the-27-kind-dispatch-table.md](objshot-manager-and-the-27-kind-dispatch-table.md),
under "The kind dispatch table". The 108 raw table bytes were re-read for this
change, SHA256 `172cc36a58bf555c338853b78cc431ac01670d47a732f4d7b3361fb194271ee1`;
all 27 handler addresses agree with that table. Their gameplay names are not established.
Kind 13 additionally carries an active NoteTrack.

Kind 25 dispatches to 0x0216B9D8. It calls 0x0216B514, which stores the owner
argument directly into shot+0x2C at 0x0216B530. It allocates a controller slot
and calls 0x0216C5F0 to create children. Thus the existing recorder's
`[shot+0x2C]+0x10` is the owner's ColPrm and its geometry head aliases the main
fighter chain. It is not a kind-0 spawned-body chain.

Kinds 1, 2, 3, 4 and 23 belong to the same owner-alias controller family.
Kind 2 dispatches directly to 0x0216B514. Kinds 1, 3 and 4 reach it through
0x0216B4F4, whose call is at 0x0216B4FC; kind 23 reaches it through
0x0216B9B0, whose call is at 0x0216B9B8. These classes still refuse body
decoding because their capture evidence has not yet been established.

Kind 25 sets shot+0x26 bit 1 and loops through 32 controller entries, setting
bit 2 where bit 0 is present, at 0x0216B9E4..BA14. Its callback registration is
in the shared initializer at 0x0216B670..B674, targeting 0x0216CE6C. That callback
moves eligible children by the owner's position delta and skips entries with
bit 2 at 0x0216CEB4..CEB8. These children have their own ColPrm and global geometry.
The body decoder does not turn them into fighter-body attacks by following the
owner alias. Their collision-phase samples remain in `native_bodies.carriers`.
The kind-25 children are real damaging attacks: the retained global elements
have native id 273, attack-category bit 28 and damage-eligible flag bit 7,
with their own ColPrm. They exist only in the carrier stream for this decoding.
An empty P1 `body.hitboxes` list for Train k5 X therefore does not mean "no attack".

## Geometry and retained bytes

ARM9 0x02079E64..E7C forms the signed x center from rectangle edges and the
facing multiplier, 1 minus twice the mirror flag. The analogous y stores end
at 0x02079EA0. Half extents are edge differences halved at 0x02079EA4..ED8.
The setters receive four signed halfwords at 0x02079EFC. They are already
transformed. Applying facing a second time is incorrect. This rule is supported
by the ROM reading and a synthetic signed-center test only. P1 has
`p1facing = 0` throughout the retained capture, so there is no real mirrored
sample. A mirrored capture is still required before treating the cell as covered.

At collision entry, 0x0207B47C..494 converts the Q12 position to an integer
origin with signed wrapping. Each active geometry element contributes its
signed center and half extents. Inclusive Q8 bounds are 256 times
`[origin_x+cx-hx, origin_y+cy-hy, origin_x+cx+hx, origin_y+cy+hy]`.
Replay stores before each element visit; animation can rewrite boxes later.

The committed `scripts/emu/native_media/plans/fixtures/train-kind25-w4.json.gz`
is a lossless gzip of the operator's `w4/body-input.json`, SHA256
`3e2dbbf8205d4f6de9866a9be877887e655658a83f3625d7987b772924491e88`.
It retains all 172 ticks. Kind 25 occurs exactly at ticks 62..82. Each aliases
P1 ColPrm 0x0220FA94 and head 0x023BF988. The sole main-chain element has native
id 0, one hurt rectangle and no damage-eligible main attack in that interval.
The decoder emits one P1 hurtbox and an observed empty P1 hitbox list per tick.

`kind25_oracle.py` imports no decoder functions. It independently unpacks signed
halfwords, replays the transform hooks and samples pre-visit rectangles, then
computes the integer origin with arithmetic wrapping and constructs the bounds.
`test_native_kind25.py` compares each of the 21 ticks and tests every other
nonzero byte class plus out-of-range and non-integer classes. Owner, ColPrm and
head mutations must refuse before allowing the alias.

Disassembly excerpts are in `docs/research/feel-captures/2026-11-01-nb-kind25/`.
Reproduce through `scripts/analysis/disasm_range.py` with the ranges above;
kind/controller functions require `--overlay 6`.

## Next prerequisite blocker

The operator stopped after the original body refusal. The retained prerequisite
contains W3 bookkeeping and W4 body bytes, but no FXO pass or collision-record
log. Running `native_carriers.read` with those rows, W4 hooks and no collision
records reports `collision record stream absent`, with zero agreeing or
disagreeing samples. It cannot reproduce record-16/gfc-356 disagreement. A new
acquisition must collect the FXO pass before that claim can be evaluated.
The earlier Train Y@k4 record-16 disagreement from an earlier capture is a
separate retained run and remains open. No emulator ran for this note.
