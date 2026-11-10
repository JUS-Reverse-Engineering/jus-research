"""Decode intrinsic abilities from a chr_b record and the ability.bin catalogue.

arm9 0x02077768 reads five sparse slots at record +0x03. The bound is
cmp sb,#5 at 0x02077818; AddAbility at 0x02077A74 ignores zero. Catalogue
kinds 0/1 append; kind 2 invokes a stat handler instead. The later +0x558
node walk can append deck-granted abilities, which this static reader omits.
Byte +0x02 is not a slot count. P178's variable-count interpretation is
superseded by the instruction trace in P223/P224.
"""
from __future__ import annotations


PROOF_GRADE = "STATIC"
LOADER_ADDRESSES = (0x02077768, 0x02077818, 0x02077A74)
PROOF_CITES = (
    "docs/research/findings/p223-ondisk-ability-list-found.md:5",
    "docs/research/findings/p224-two-ability-sources-and-eight-non-abilities.md:29",
)


def decode_record(record: bytes, catalogue: bytes) -> list[int]:
    """Return ordered, nonzero kind-0/1 ids from the five intrinsic slots.

    `record` is one complete 60-byte chr_b record, including a preserved
    chr-natures.json `raw` value decoded with bytes.fromhex. `catalogue` is
    ability.bin, whose four-byte entries store their kind in byte zero.
    """
    if len(record) != 60:
        raise ValueError(f"chr_b record must be 60 bytes, got {len(record)}")
    if not catalogue or len(catalogue) % 4:
        raise ValueError("ability catalogue must contain complete four-byte entries")
    result = []
    for ability_id in record[3:8]:
        if ability_id == 0:
            continue
        offset = ability_id * 4
        if offset >= len(catalogue):
            raise ValueError(f"ability id {ability_id} is outside the catalogue")
        kind = catalogue[offset]
        if kind not in (0, 1, 2):
            raise ValueError(f"ability id {ability_id} has unknown kind {kind}")
        if kind != 2:
            result.append(ability_id)
    return result
