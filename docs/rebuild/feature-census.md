# Feature census

`feature-census.json` lists every JUS kit feature the committed decoders see across the 74 battle
prefixes, both as the original aggregate and as a per-prefix cast census. It exists so the kit exporter cannot drop a feature silently: `scripts/kit/feature_status.py`
classifies each key in `FEATURE_STATUS`, and `scripts/tests/test_export_coverage.py` fails on a key
that table lacks.

Build and check:

```
python3 scripts/analysis/feature_census.py build   # write feature-census.json
python3 scripts/analysis/feature_census.py check   # exit 0 iff the committed file is fresh
python3 scripts/analysis/feature_census.py keys    # every key with its event and prefix counts
```

`export-kit` runs `check` as a precondition. The scanner reads the same decoders as the other
tables (`ua_table.anim_scan`, `anim_events`, `mash_table.decode_event`, `move_records`,
`knockback_table.record_uses`) and the shot rows of `chr/shot/<prefix>.bin`. It needs `jus_files`.

## Keys

| Prefix | Source | Example |
|---|---|---|
| `op0.subN[.variant]` | NoteTrack op 0 wait/branch events; variants split decoded forms | `op0.sub5.arm`, `op0.sub1.hold_release_disarm` |
| `op1.subN`, `op2.subN`, `op4.subN` | NoteTrack ops 1, 2, 4 | `op1.sub3` |
| `op3.argN`, `op3.subN` | op 3 sub 0 by arg; other op 3 subs | `op3.arg2`, `op3.sub2` |
| `gn.GNxx`, `node.undecoded.GNxx` | effect nodes decoded (spawns) or left raw | `node.undecoded.GN02` |
| `rec.mask.bitN`, `rec.type.N`, `rec.kind.N`, `rec.<field>.nonzero` | 20-byte KB records | `rec.mask.bit9`, `rec.statusRaw.nonzero` |
| `shot.kind.0xNN`, `shot.flag.0xN`, `shot.bN.nonzero`, `shot.bytes16_27.nonzero` | shot rows | `shot.kind.0x0d`, `shot.flag.0x40` |
| `error.*` | a loader failed; the test refuses these | |

## Shape

Per character: `anims` keyed `<member>#0x<anim>` (member is the `chr/<member>.aar` stem: the base
prefix or `<prefix>_<koma>`) with `frames`, `keys` (`{key: [frames]}`; `-1` marks an undecoded
node), `spawns` (`[frame, shot row]` of each op 3 arg 2) and `recs` (collision ids from 0x100 the
anim's boxes name); `records` (`{rec: [keys]}`) and `shots` (`{row: {kind, art, flags, b28, b29,
keys}}`). The top-level `keys` gives each key's event count and prefix count.

`records_by_prefix` has one row per archive prefix. Each row contains `prefix`, `roster`, `features`
(feature-key occurrence counts), `m0_keys`, `m0_no_census_signal`, `mechanism_demand` and `cost`.
Roster identity separates `candidates` (every `chr_b` and name whose reconciled candidates include
the archive prefix) and `doc_prefix` (all rows documented with that prefix; this can be more than
one identity in the reconciliation). `chr_b` and `name` are populated only for a pinned archive
join; an ambiguous row never chooses one candidate.

`mechanism_demand` contains counts for both `unsupported` and `partial` feature keys in
`feature_status.FEATURE_STATUS`. Cost sums occurrence counts for `unsupported` keys only; partial
keys are retained in demand but contribute zero to cost. Repeated frames/rows add proportionally.
This is a simple demand proxy, not an estimate of implementation hours. `cross_cast.records_per_mechanism`
counts prefixes with each mechanism key. `cross_cast.m0_keys_by_demand` ranks M0 buckets by prefixes
with a direct signal. These explicit key sets are grounded in the importer deferral definitions at
`import_kit.py:143-154`, the hold-tier decoder at `mash_table.py:89`, body flag at
`feature_status.py`'s `op3.sub2` entry, no-damage record kind at `scripts/kit/feature_status.py:453`, held-summon
shot kind at the `shot.kind.0x0d` status entry, and ability effects at `op3.arg7/23/32`. Element
hurtbox geometry, support assists, form-change state, cancel-carry metadata, and legacy mash fields
have no direct signal in this census and are reported in `m0_no_census_signal` rather than assigned
a broad proxy.

The existing aggregate `version`, `keys`, and `characters` fields retain their original values and
serialization. The new sections are additive.

K7-a classifies shot features per occurrence. Only a decoded join on root
animation, authored frame, row and occurrence can retire a native shot key.
An undecoded flag stays unsupported even when another occurrence of its kind
is decoded. Counter and forced-switch mask readings use the ROM table in
[collision-node-flags.json](collision-node-flags.json), produced by
collision_node_flags.py.
`REC_MASK_NODE_WORD_READER_CLOSURE_OPEN` and
`ANIM_OP1_FLAG_READER_CLOSURE_OPEN` remain explicit debts. See the
native-readings reference.
