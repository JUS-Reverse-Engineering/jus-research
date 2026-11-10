#!/usr/bin/env python3
"""move_records.py -- map a character's animations to the authored 20-byte
collision records they make live, and print those records' fields.

Why this exists
---------------
`docs/confirmed-facts/collision.md` GAPS G1 ("the runtime hitbox parser") asked
which of the 2837 authored 20-byte records in `chr/col/<file>.bin` become live
hit elements on a given move's animation frame.  The selector is now known
(tracker item `jus-hitbox-record-selection-u3ig`; see
`docs/research/feel-captures/register-2026-09-03/static-hitbox-record-selection.md`):

  animation property `CollisionTypeN` (N = 0..6, a per-node channel)
     -> descriptor+0x0C   (arm9 setter 0x0207A2F4, CollisionType vtable 0x0209F96C)
     -> Battle_ColObjAddColWork(colobj, id)   (arm9 0x0207B11C, ColWork+0x0E = id)
     -> arm9 0x0207D440:
            id >= 0x100 : element+0x10 = [[record+0x6C]+0x0C] + (id - 0x100) * 20
                          i.e. the CHARACTER's own chr/col file, record (id-0x100)
            id <  0x100 : element+0x10 = 0x0209FC2C + id * 20
                          i.e. a built-in arm9 table (ids 0..13 are the sized ones)
     -> the hit processor arm9 0x02080F14 reads that pointer as `[r6+0x10]`
        (moveData[+1] type, [+7] hitstun add, [+0xC]/[+0xD] knockback X/Y).

`CollisionEnableN` is only the on/off toggle for the same channel N; it is NOT
the record index (0/1 in the data).  This script reads the animation side out
of the character's ALMT motion file and joins it to the on-disk col records.

Data sources (read-only)
------------------------
  records   jus_files/chrbin/chr/col/<file>.bin      (flat, 20-byte stride, no header)
  animation jus_files/ripped_jus_files/chr/ChrArc.aar
              -> chr/<file>.aar   (DSCP = 4-byte magic + Nintendo LZ77 type 0x10)
              -> inner ALAR v2 -> <file>.amt (DSCP) -> ALMT motion
  names     docs/research/chr_b-Complete-Mapping.md  (chr_b index <-> file <-> name)

CAVEAT on field names: the exported `*_collision.json` column names
(`width`/`height`/`knockback`/`projectileId`) were never verified against a
consumer and several are wrong.  This script prints BOTH the byte offset and
the name the arm9 consumer justifies.  See
`docs/research/feel-captures/guardbreak-2026-09-02/static-knockback-fields.md`.

CAVEAT on the File column: `chr_b-Complete-Mapping.md`'s File column is known
wrong or unverified on 25 rows (2026-10-13) across 7 prefixes; the E0 pin (2026-10-18) measured 23, so len(SUSPECT_CHRB) is now 2 (71, 72)
(`jus-chrb-colfile-mapping-audit-x7i2`,
opened by `jus-lxyt`'s live pointer trace on Kakashi -- see
`docs/research/findings/knockback-record-pointer-per-hit.md`). This script
self-checks the file it picks against a small known-good dict (`KNOWN_REC0`)
for the characters that have been live-verified and refuses (nonzero exit)
on a mismatch; it warns on stderr, but does not refuse, when the resolved
row is one of the unverified suspect rows (`SUSPECT_CHRB`). Pass
`--live-record <hex bytes>` to check an ad-hoc rec-0 capture (e.g. a fresh
GDB dump) against whatever file this run picked, independent of the dict.
"""
from __future__ import annotations

import argparse
import io
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COL_DIRS = [
    ROOT / "jus_files" / "chrbin" / "chr" / "col",
    ROOT / "jus_files" / "extracted_chrbin" / "ChrBin.aar" / "chr" / "col",
]
CHRARC = ROOT / "jus_files" / "ripped_jus_files" / "chr" / "ChrArc.aar"
CHRB_MAP = ROOT / "docs" / "research" / "chr_b-Complete-Mapping.md"
RECORD_SIZE = 20
CHAR_ID_BASE = 0x100          # arm9 0x0207D4AC / 0x0207D4B8
BUILTIN_TABLE = 0x0209FC2C    # arm9 0x0207D570 literal

# --------------------------------------------------------------------------- #
# self-validation: chr_b-Complete-Mapping.md's File column is known wrong on
# 25 rows across 7 prefixes (2026-10-13; 23 measured by E0 2026-10-18) (jus-chrb-colfile-mapping-audit-x7i2, opened by
# jus-lxyt's live pointer trace -- see
# docs/research/findings/knockback-record-pointer-per-hit.md). Rather than
# silently resolve one of those rows to a file that may not hold this
# character's records, this script refuses on a known mismatch and warns on
# an unverified suspect row. Extend KNOWN_REC0 as more characters get a live
# trace or a byte-for-byte file search.
# --------------------------------------------------------------------------- #
# E0 roster pin (2026-10-18, docs/research/feel-captures/2026-10-18-e0-roster/roster_reconciled.json)
# measured 23 of the 25 suspect rows by full-file byte equality against the live col base. Only the
# never-active komamen Green (71) and Yellow (72) are still unobserved (dt_b_01..03 are identical, so
# even a measured base would be ambiguous). Ambiguous rows 12/20/70 were never in this set.
SUSPECT_CHRB = {71, 72}

# chr_b index -> how the File column was measured when no rec 0 bytes exist
# (so it cannot live in KNOWN_REC0). The join is the stored value (ctrl+0xA3)
# the character's own UA/consumer table produces, matched to the one file whose
# ua-table stores it. Consumer: chrb_names_for (cancel, knockback, mash and ua tables all use it).
MEASURED_CHRB_FILE = {
    3: "Vegeta (SSJ) = db_b_04, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    4: "Gohan (SSJ) = db_b_05, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    5: "Gohan (SSJ2) = db_b_06, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    6: "Gotenks = db_b_07, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    7: "Gotenks (SSJ) = db_b_08, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    8: "Piccolo = db_b_09, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    9: "Frieza = db_b_10, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    10: "Majin Buu = db_b_11, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    11: "Vegetto = db_b_12, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    13: "Zoro = op_b_02, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    14: "Sanji = op_b_03, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    16: "Robin = op_b_05, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    17: "Franky stores 3/6, side Y f10->f52/f103, air Y f11->f89/f158 = op_b_06 "
        "(feel-captures/2026-10-13-yusuke-ua S0; confirmed by E0 roster pin, roster_reconciled.json)",
    18: "G2 Luffy stores 9 = op_b_07, the only op_b_* store of 9; value only "
        "(feel-captures/2026-10-13-yusuke-ua S0; confirmed by E0 roster pin, roster_reconciled.json)",
    19: "PCT Nami = op_b_08, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    22: "Sakura = na_b_03, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    24: "Kyuubi Naruto = na_b_05, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    38: "Train = bc_b_02, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    48: "Don Patch = bb_b_02, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    49: "Shinsetsu = bb_b_03, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
    66: "Edajima = oj_b_01, full-file byte equality with the live col base (E0 roster pin, roster_reconciled.json, MEASURED)",
}

# chr_b index -> rec 0's 20 bytes, hex, for the *correct* file (not the
# mapping table's File column). Kakashi/Sasuke: live GDB pointer trace
# (jus-lxyt). Vegeta/Eve: byte-for-byte file search off census ENTRIES.md
# arithmetic, not yet pointer-traced -- weaker evidence, same conclusion.
# Momotaro (2026-09-12): live bridge read of rec11's authored_base (P1,
# active) ([[record+0x6C]+0x0C], no hit/GDB needed -- projectile_census.py
# already resolves this per in-use record) in
# pc-momotaro-npc-nami-dark-tournament, chr_b index confirmed via the
# player-slot byte +0x29 = 67; positive controls (Vegeta, Kakashi as P2)
# reproduced db_b_03/na_b_04 first. See
# docs/research/feel-captures/colfile-audit-2026-09-12/RESULTS.md.
KNOWN_REC0 = {
    23: "0301000008000000000000000500000c01010000",  # Kakashi  -> na_b_04
    21: "0301000007000000000000000600000c01010000",  # Sasuke   -> na_b_02
    2:  "030100000a000000000000000400000c01010000",   # Vegeta   -> db_b_03
    37: "0300000007000000000000000500000c01010000",  # Eve      -> bc_b_01
    67: "030000000a000000000000000700051501000000",  # Momotaro -> oj_b_02
}


# --------------------------------------------------------------------------- #
# Nintendo LZ77 (type 0x10), as used behind the 4-byte "DSCP" magic
# --------------------------------------------------------------------------- #
def lz77(data: bytes, off: int = 0) -> bytes:
    hdr = struct.unpack_from("<I", data, off)[0]
    kind, size = hdr & 0xFF, hdr >> 8
    if kind != 0x10:
        raise ValueError(f"unsupported compression type 0x{kind:02x} at 0x{off:x}")
    out = bytearray()
    p = off + 4
    while len(out) < size:
        flags = data[p]
        p += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                x, y = data[p], data[p + 1]
                p += 2
                n = (x >> 4) + 3
                disp = (((x & 0xF) << 8) | y) + 1
                for _ in range(n):
                    out.append(out[len(out) - disp])
            else:
                out.append(data[p])
                p += 1
    return bytes(out)


def dscp(data: bytes, off: int = 0) -> bytes:
    if data[off:off + 4] != b"DSCP":
        raise ValueError("not a DSCP container")
    return lz77(data, off + 4)


def maybe_dscp(data: bytes) -> bytes:
    return dscp(data) if data[:4] == b"DSCP" else data


# --------------------------------------------------------------------------- #
# ALAR v3 (ChrArc.aar) member lookup
# --------------------------------------------------------------------------- #
def alar_v3_member(path: Path, want: str) -> bytes:
    d = path.read_bytes()
    if d[:4] != b"ALAR" or d[4] != 3:
        raise ValueError(f"{path} is not ALAR v3")
    nfiles = struct.unpack_from("<H", d, 6)[0]
    infos = [struct.unpack_from("<H", d, 0x12 + 2 * i)[0] for i in range(nfiles)]
    for io_ in infos:
        off, size = struct.unpack_from("<II", d, io_ + 4)
        name_end = d.index(b"\0", io_ + 0x12)
        name = d[io_ + 0x12:name_end].decode("ascii", "replace")
        if name == want:
            return d[off:off + size]
    raise KeyError(want)


# --------------------------------------------------------------------------- #
# ALMT motion parsing
# --------------------------------------------------------------------------- #
# Bytes per key of a keyed track, by property name: u16 frame + the value. STATIC (PF-31m).
# The ALMT loader gives a keyed track its property's own key reader ([prop+4], vtable+0x78)
# or the generic reader 0x0201E1E4 (arm9 0x0201F598..0x0201F5E4). The generic reader steps
# 2 * ((size + 1) // 2 + 1) bytes per key (0x0201E1FC..0x0201E220), size = the property's
# vtable+0x68 callback:
#   2: CollisionType0-6 (vtable 0x0209F96C) and CollisionEnable0-6 (0x0209FA18), both
#      registered from the name table 0x0209F868 (0x0207A2A8, 0x0207A3CC); BoundsIndex
#      (0x02099AF4); EffectFlags (0x02099640); Marker (0x0209A508); callback 0x0204AAE8 -> 4
#   1: ParentLink (0x02099DA4, callback 0x0204AAD8) -> 4
#   4: 2DPos (0x02098C48), TextureID (0x0209A660), Alpha (0x02098900), DrawPrio (0x020989A8),
#      registered at 0x020215EC..0x02021668 (callbacks 0x0204B2EC, 0x0204A788, 0x0204B188) -> 6
# Own readers: GenerateID 0x02016220 (descriptor 0x02099E50) steps size 4 -> 6
# (0x02016248..0x02016254); CollisionRect0-6 0x0207A658 (vtable 0x0209F8C4, size 8,
# installed at 0x0207A57C) steps 0xA (0x0207A694, 0x0207A6B4). The loader counts Marker keys
# at 4 bytes (0x0201F620..0x0201F63C) and hands NoteTrack (name match 0x0201EDE4, loader+0x6C)
# to 0x0201E468, which reads (u16 frame, s16 rel) keys. A keyed property not listed has no
# known stride; a node holding one is reported, never parsed with a guessed stride.
KEY_STRIDE = {"BoundsIndex": 4, "EffectFlags": 4, "ParentLink": 4, "Marker": 4, "NoteTrack": 4,
              "2DPos": 6, "TextureID": 6, "Alpha": 6, "DrawPrio": 6, "GenerateID": 6,
              **{f"CollisionType{n}": 4 for n in range(7)},
              **{f"CollisionEnable{n}": 4 for n in range(7)},
              **{f"CollisionRect{n}": 10 for n in range(7)}}


def keyed_track(buf: bytes, s: int, e: int, stride: int) -> tuple[list, bool]:
    """(keys, terminated) of a keyed track in buf[s:e]. A key's value is its stride - 2 bytes
    read as one little-endian unsigned int, so a 4-byte key's value is the u16 it always was."""
    keys, q = [], s
    while q + 2 <= e:
        f = struct.unpack_from("<H", buf, q)[0]
        if f == 0xFFFF:
            return keys, True
        if q + stride > e:
            break
        keys.append((f, int.from_bytes(buf[q + 2:q + stride], "little")))
        q += stride
    return keys, False


def native_node_blocks(almt: "Almt", start: int) -> list[tuple[str, int]]:
    """[(node name, count-block offset)] of the animation entry at `start`, in node order.

    The ALMT loader frames nodes from the entry header (arm9 0x0201F1B8..0x0201F208): node i's
    u16 at entry+8+2i is added to entry-0x20, as a running sum for version >= 2 and on its own
    for version 1; a zero word omits the node. The offset is the node's u8 constant count,
    u8 keyed count block, whose track offsets (0x0201F6BC..0x0201F728) are relative to it."""
    buf, version, run, out = almt.buf, almt.buf[almt.base + 4], 0, []
    for i, name in enumerate(almt.nodes):
        word = struct.unpack_from("<H", buf, start + 8 + 2 * i)[0]
        run = word if version <= 1 else run + word
        if word:
            out.append((name, start - 0x20 + run))
    return out


class Almt:
    """One ALMT motion table.

    Layout (derived 2026-09-03, this tracker item):
      +0x00 'ALMT'  +0x04 u8 version(2)  +0x06 u8 nodeCount  +0x08 u32 propCount
      +0x0C  nodeCount * 4 ASCII node names
      then   u32 animation-entry offsets (ascending, until 0 / out of range)
      then   propCount * u16 offsets to NUL-terminated property-name strings

    Animation entry:
      +0x00 u32 animation id (low byte is the id the engine uses)
      +0x04 u16 frame count
      +0x10 u8  constant-track count  nc
      +0x11 u8  keyframed-track count nk
      +0x12 (nc+nk) u8 property indexes, 2-byte aligned, then
            (nc+nk) u16 data offsets, each relative to entry+0x10
      constant track: one packed value
      keyframed track: (u16 frame, value) keys, KEY_STRIDE[prop] bytes each, terminated
            by frame 0xFFFF
    `full_entry` keeps the legacy node starts that anim_events and the support paths
    key on; `native_nodes` frames every node the loader's way and is what the record
    census (`anim_record_uses`, `node_problems`) reads.
    """

    def __init__(self, buf: bytes, base: int = 0):
        if buf[base:base + 4] != b"ALMT":
            raise ValueError("not ALMT")
        self.buf = buf
        self.base = base
        self.node_count = buf[base + 6]
        self.prop_count = struct.unpack_from("<I", buf, base + 8)[0]
        p = base + 0xC
        self.nodes = [buf[p + 4 * i:p + 4 * i + 4].decode("ascii", "replace")
                      for i in range(self.node_count)]
        p += 4 * self.node_count
        self.anim_offsets = []
        while True:
            v = struct.unpack_from("<I", buf, p)[0]
            if v == 0 or base + v > len(buf) or (self.anim_offsets and v < self.anim_offsets[-1]):
                break
            self.anim_offsets.append(v)
            p += 4
        name_off = [struct.unpack_from("<H", buf, p + 2 * i)[0] for i in range(self.prop_count)]
        self.props = []
        for o in name_off:
            o += base
            self.props.append(buf[o:buf.index(b"\0", o)].decode("ascii", "replace"))
        # entry end = next entry start, or the property-name string table
        self.limit = base + min(name_off) if name_off else len(buf)
        # Entries in a multi-node ALMT carry one extra u16 "which byte offset
        # does node N's own sub-entry start at" field per *additional* node,
        # right after frames (+0x0A, +0x0C, ... one per node beyond node 0),
        # pushing nc/nk (and the base that per-track offsets are relative to)
        # out by 2 bytes per extra node. So hdr_end = 0x0A + 2*(node_count-1):
        # node_count 1 -> 0x0A, 3 (Luffy) -> 0x0E, 4 (Kenshin) -> 0x10.
        # Verified against rk_b_01_5/_6.aar (node_count 1, hdr_end 0x0A),
        # op_b_01.aar/Luffy (node_count 3, hdr_end 0x0E) and rk_b_01.aar's
        # node 0 (node_count 4, hdr_end 0x10) -- the wrong hdr_end reliably
        # produces implausible nc/nk (huge track counts) or an offset table
        # that runs off the end of the block; the right one decodes clean.
        self.hdr_end = 0x0A + 2 * max(self.node_count - 1, 0)
        self.extra_node_slots = max(self.node_count - 1, 0)

    def animations(self):
        starts = [self.base + o for o in self.anim_offsets]
        ends = starts[1:] + [len(self.buf)]
        for idx, (a, b) in enumerate(zip(starts, ends)):
            yield idx, self._entry(a, b)

    def _entry(self, a: int, b: int) -> dict:
        buf = self.buf
        he = self.hdr_end
        anim_id = struct.unpack_from("<I", buf, a)[0] & 0xFF
        frames = struct.unpack_from("<H", buf, a + 4)[0]
        nc, nk = buf[a + he], buf[a + he + 1]
        if a + he + 2 + nc + nk > b:
            raise ValueError(f"entry header overruns block (nc={nc} nk={nk} a=0x{a:x} b=0x{b:x})")
        props = list(buf[a + he + 2:a + he + 2 + nc + nk])
        tp = a + he + 2 + nc + nk
        if tp & 1:
            tp += 1
        if tp + 2 * (nc + nk) > b:
            raise ValueError(f"offset table overruns block (a=0x{a:x} b=0x{b:x})")
        tbl = [struct.unpack_from("<H", buf, tp + 2 * j)[0] for j in range(nc + nk)]
        bounds = [a + he + t for t in tbl] + [b]
        if any(x < a or x > b for x in bounds) or bounds != sorted(bounds):
            raise ValueError(f"track offset table not monotonic/in-range (a=0x{a:x} b=0x{b:x})")
        tracks = []
        for j, pr in enumerate(props):
            s, e = bounds[j], min(bounds[j + 1], b)
            name = self.props[pr] if pr < len(self.props) else f"prop{pr}"
            if j < nc:
                val = struct.unpack_from("<H", buf, s)[0] if e - s >= 2 else None
                keys = [(0, val)] if val is not None else []
                tracks.append({"prop": name, "kind": "const", "keys": keys,
                               "raw": buf[s:e], "terminated": True})
            else:
                stride = KEY_STRIDE.get(name)
                keys, terminated = keyed_track(buf, s, e, stride) if stride else ([], False)
                tracks.append({"prop": name, "kind": "key", "keys": keys, "stride": stride,
                               "raw": buf[s:e], "terminated": terminated})
        return {"index": idx_placeholder(), "id": anim_id, "frames": frames,
                "tracks": tracks, "prop_indexes": props, "start": a, "end": b}

    @staticmethod
    def _entry_is_clean(entry: dict) -> str | None:
        """None if `entry` looks like a genuine decode; else a one-line reason it doesn't.

        Only the *last* track's end is ambiguous (it is clamped to the block
        end, not to a following track's start from the offset table), so only
        the last track is required to hit an explicit 0xFFFF terminator.
        Interior tracks are bounded exactly by the next track's known start
        and are not expected to carry a terminator of their own.
        """
        for t in entry["tracks"]:
            if t["prop"].startswith("prop"):
                return f"unknown property index in {t['prop']!r}"
            if t["kind"] == "key" and t["stride"] is None:
                return f"keyed {t['prop']} has no known key stride (KEY_STRIDE)"
        tracks = entry["tracks"]
        if tracks and tracks[-1]["kind"] == "key" and not tracks[-1]["terminated"]:
            return f"{tracks[-1]['prop']} (last track) never hit the 0xFFFF terminator"
        return None

    def full_entry(self, top_a: int, top_b: int) -> dict:
        """Decode every node of one top-level animation entry.

        Node 0 (`self.nodes[0]`, always `SP01`) is described directly at
        `top_a`. If `self.node_count > 1`, `self.extra_node_slots` (=
        `node_count - 1`) little-endian u16 fields starting at `top_a+0x0A`
        are *candidate* byte offsets (from `top_a`) to additional per-node
        sub-entries -- each is a full copy of the same entry format
        (id/frames/nc/nk/props/tracks), laid out somewhere in `[top_a, top_b)`
        (not necessarily in node order, not necessarily in the order the
        header slots list them: see static-hitbox-record-selection.md's
        "ALMT full-node decode" note).

        A candidate offset is only trusted as a node-block boundary if it is
        >= the byte position where node 0's own track-offset table says node
        0's data ends -- otherwise it demonstrably collides with node 0's own
        authored tracks and is reported, not guessed at, as `unexplained`.
        Every accepted boundary is then decoded with the same `_entry()`
        parser and independently validated (`_entry_is_clean`); a boundary
        that decodes to unknown property indexes or an unterminated keyframe
        track is reported as `undecoded`, never guessed at.
        """
        buf = self.buf
        he = self.hdr_end
        node0_min_end = top_a + he  # lower bound if there happen to be zero tracks, or on error
        try:
            nc0, nk0 = buf[top_a + he], buf[top_a + he + 1]
            if nc0 + nk0:
                tp = top_a + he + 2 + nc0 + nk0
                if tp & 1:
                    tp += 1
                last_off = struct.unpack_from("<H", buf, tp + 2 * (nc0 + nk0 - 1))[0]
                node0_min_end = top_a + he + last_off
        except (IndexError, struct.error):
            pass  # node0 itself will fail _entry() below and get reported there

        result = {"nodes": []}
        if self.node_count <= 1:
            try:
                entry0 = self._entry(top_a, top_b)
                reason0 = self._entry_is_clean(entry0)
            except (ValueError, struct.error) as ex:
                entry0, reason0 = None, str(ex)
            result["nodes"].append({"name": self.nodes[0] if self.nodes else "node0",
                                     "ok": reason0 is None, "reason": reason0,
                                     "entry": entry0, "start": top_a, "end": top_b})
            return result

        raw_offs = [struct.unpack_from("<H", buf, top_a + 0xA + 2 * i)[0]
                    for i in range(self.extra_node_slots)]
        slot_names = [self.nodes[i] if i < len(self.nodes) else f"node{i}"
                      for i in range(1, 1 + self.extra_node_slots)]
        accepted, unexplained = [], []
        for off, label in zip(raw_offs, slot_names):
            if off == 0:
                continue
            abs_off = top_a + off
            if abs_off < node0_min_end or abs_off >= top_b:
                unexplained.append((label, off))
            else:
                accepted.append((abs_off, label))
        accepted.sort()

        # Node 0's data runs to the next node's count block in the loader's own framing
        # (native_node_blocks). A legacy slot start sits hdr_end bytes earlier, which cut
        # node 0's last track short (PF-31m). The node's "end" stays the legacy boundary:
        # the max node end is the animation end anim_events and effect_render walk to.
        end0 = accepted[0][0] if accepted else top_b
        try:
            data0 = min([b for _, b in native_node_blocks(self, top_a) if b > top_a + he] + [top_b])
        except (IndexError, struct.error):
            data0 = end0
        try:
            entry0 = self._entry(top_a, min(data0, top_b))
            reason0 = self._entry_is_clean(entry0)
        except (ValueError, struct.error) as ex:
            entry0, reason0 = None, str(ex)
        result["nodes"].append({"name": self.nodes[0] if self.nodes else "node0",
                                 "ok": reason0 is None, "reason": reason0,
                                 "entry": entry0, "start": top_a, "end": end0})

        bounds = [p for p, _ in accepted] + [top_b]
        for i, (start, label) in enumerate(accepted):
            end = bounds[i + 1]
            try:
                e = self._entry(start, end)
                reason = self._entry_is_clean(e)
            except (ValueError, struct.error) as ex:
                e, reason = None, str(ex)
            result["nodes"].append({"name": label, "ok": reason is None, "reason": reason,
                                     "entry": e, "start": start, "end": end})
        for label, off in unexplained:
            result["nodes"].append({"name": label, "ok": False,
                                     "reason": f"header offset 0x{off:x} is before node0's own "
                                                "last track or out of range -- not a node "
                                                "boundary, meaning unknown",
                                     "entry": None, "start": None, "end": None})
        return result

    def full_animations(self):
        """Yield (idx, full_entry_dict) for every top-level animation, all nodes decoded."""
        starts = [self.base + o for o in self.anim_offsets]
        ends = starts[1:] + [len(self.buf)]
        for idx, (a, b) in enumerate(zip(starts, ends)):
            yield idx, self.full_entry(a, b)

    def native_nodes(self, top_a: int, top_b: int) -> list[dict]:
        """Every node of one animation entry in the loader's own framing (PF-31m).

        Nodes sit at native_node_blocks; a node's data runs to the next count block in
        address order, the last to `top_b`. Track offsets must lie past the node's offset
        table, ascend and stay inside the node; every keyed track is parsed at its property's
        KEY_STRIDE and must hit its 0xFFFF terminator inside its own bounds. A node failing
        any check is ok: False with a reason. id and frames are the animation's own (top_a).
        Node dicts match full_entry's, but start/end are the count block and its stop."""
        buf = self.buf
        anim_id = struct.unpack_from("<I", buf, top_a)[0] & 0xFF
        frames = struct.unpack_from("<H", buf, top_a + 4)[0]
        blocks = sorted(native_node_blocks(self, top_a), key=lambda nb: nb[1])
        out = []
        for i, (name, cb) in enumerate(blocks):
            stop = blocks[i + 1][1] if i + 1 < len(blocks) else top_b
            try:
                entry = {"id": anim_id, "frames": frames, "start": cb, "end": stop,
                         **self._node_block(cb, stop, top_a)}
                reason = None
            except (ValueError, IndexError, struct.error) as ex:
                entry, reason = None, str(ex)
            out.append({"name": name, "ok": reason is None, "reason": reason,
                        "entry": entry, "start": cb, "end": stop})
        return out

    def _node_block(self, cb: int, stop: int, top_a: int) -> dict:
        buf = self.buf
        if not top_a <= cb < stop <= len(buf):
            raise ValueError(f"node block 0x{cb:x}..0x{stop:x} outside its animation")
        nc, nk = buf[cb], buf[cb + 1]
        props = list(buf[cb + 2:cb + 2 + nc + nk])
        tp = cb + 2 + nc + nk
        tp += tp & 1
        if tp + 2 * (nc + nk) > stop:
            raise ValueError(f"offset table overruns node (cb=0x{cb:x} stop=0x{stop:x})")
        bounds = [cb + struct.unpack_from("<H", buf, tp + 2 * j)[0] for j in range(nc + nk)]
        bounds.append(stop)
        if any(x < tp + 2 * (nc + nk) for x in bounds) or bounds != sorted(bounds):
            raise ValueError(f"track offsets leave the node or descend (cb=0x{cb:x})")
        tracks = []
        for j, pr in enumerate(props):
            if pr >= len(self.props):
                raise ValueError(f"unknown property index {pr} (cb=0x{cb:x})")
            name, s, e = self.props[pr], bounds[j], bounds[j + 1]
            if j < nc:
                if e - s < 2:
                    raise ValueError(f"constant {name} is shorter than a u16 (cb=0x{cb:x})")
                tracks.append({"prop": name, "kind": "const",
                               "keys": [(0, struct.unpack_from("<H", buf, s)[0])],
                               "raw": buf[s:e], "terminated": True})
                continue
            stride = KEY_STRIDE.get(name)
            if stride is None:
                raise ValueError(f"keyed {name} has no known key stride (KEY_STRIDE)")
            keys, terminated = keyed_track(buf, s, e, stride)
            if not terminated:
                raise ValueError(f"keyed {name} never hit the 0xFFFF terminator in its node "
                                 f"(cb=0x{cb:x})")
            tracks.append({"prop": name, "kind": "key", "keys": keys, "stride": stride,
                           "raw": buf[s:e], "terminated": True})
        return {"tracks": tracks, "prop_indexes": props}

    def native_animations(self):
        """Yield (idx, [native node dict]) for every top-level animation."""
        starts = [self.base + o for o in self.anim_offsets]
        ends = starts[1:] + [len(self.buf)]
        for idx, (a, b) in enumerate(zip(starts, ends)):
            yield idx, self.native_nodes(a, b)


def idx_placeholder():
    return None


def find_almts(blob: bytes):
    """Yield Almt objects for every motion table in a decompressed member."""
    out = []
    for m in re.finditer(rb"DSCP", blob):
        try:
            sub = dscp(blob, m.start())
        except Exception:
            continue
        if sub[:4] == b"ALMT":
            try:
                out.append(Almt(sub, 0))
            except Exception:
                pass
    for m in re.finditer(rb"ALMT", blob):
        try:
            out.append(Almt(blob, m.start()))
        except Exception:
            pass
    return out


# --------------------------------------------------------------------------- #
# records
# --------------------------------------------------------------------------- #
FIELDS = [
    (0x00, 1, "u", "kind",       "0=plain box (no damage), 3/4/5 seen on attacks"),
    (0x01, 1, "u", "type",       "arm9 0x020817EC: ==6 gates HP-band + weight scaling"),
    (0x02, 1, "u", "byte2",      "unattributed"),
    (0x03, 1, "s", "statusRaw",  "arm9 0x02081698 ldrsb: staged status id. Negative: -raw to channel 1 (X+0x173); positive: raw to channel 0 (X+0x172); flushed at ov6 0x02158B34"),
    (0x04, 1, "u", "frameStart", "authored frame; != in-game startup (-3..+5)"),
    (0x05, 1, "s", "shakeScale", "arm9 0x020812A0: SP drain per contact, 1/100 bar (<< 8 into the struck owner's cell sums; ov6 0x0215AC5C applies -sum to the team pool); misnamed, not a shake"),
    (0x06, 1, "u", "byte6",      "unattributed"),
    (0x07, 1, "s", "hitstunAdd", "arm9 0x02081300: M+0x171 += this"),
    (0x08, 4, "w", "propMask",   "arm9 0x0207D688: 32-bit bitmask -> 3 flag tables at 0x0209FD44"),
    (0x0C, 1, "s", "kbX",        "arm9 0x020817F0: horizontal knockback"),
    (0x0D, 1, "s", "kbY",        "arm9 0x020817F4: vertical knockback"),
    # 0x0E/0x0F were once labelled shakeRowB/shakeRowA. The loads at those
    # addresses feed ov6 0x02153CE8's r1/r2 (vfx-sfx.md §2), not a shake table.
    (0x0E, 1, "s", "hitEffect",  "arm9 0x0208125C -> r1 of ov6 0x02153CE8: hit spark + sound index (class index)"),
    (0x0F, 1, "s", "onomatopoeia", "arm9 0x02081238 -> r2 of ov6 0x02153CE8: comm_g text 0x240000|idx"),
    (0x10, 1, "u", "byte16",     "args 7 of ov6 0x02153CE8 (0x020819FC); indexes word table 0x02171E1C"),
    (0x11, 1, "u", "byte17",     "args 8 of ov6 0x02153CE8 (0x02081A08); indexes halfword table 0x02171E0C -> vtable+0x104 call"),
    (0x12, 1, "u", "byte18",     "unattributed"),
    (0x13, 1, "u", "byte19",     "unattributed"),
]


def decode_record(raw: bytes) -> dict:
    out = {}
    for off, size, sign, name, _ in FIELDS:
        if size == 4:
            out[name] = struct.unpack_from("<I", raw, off)[0]
        elif sign == "s":
            out[name] = struct.unpack_from("<b", raw, off)[0]
        else:
            out[name] = raw[off]
    return out


def fmt_record(idx: int, raw: bytes, prefix: str = "") -> str:
    r = decode_record(raw)
    return (f"{prefix}rec {idx:3d} (id 0x{idx + CHAR_ID_BASE:03x})  "
            f"kind {r['kind']} type {r['type']:2d}  kbX {r['kbX']:4d} kbY {r['kbY']:4d}  "
            f"hitstunAdd {r['hitstunAdd']:3d}  frameStart {r['frameStart']:3d}  "
            f"statusRaw {r['statusRaw']:4d}  propMask 0x{r['propMask']:08x}  "
            f"| {' '.join(f'{b:02x}' for b in raw)}")


# --------------------------------------------------------------------------- #
# character resolution
# --------------------------------------------------------------------------- #
def load_chrb_rows() -> dict[int, tuple[str, str, str]]:
    """Every chr_b row of chr_b-Complete-Mapping.md -> (file_prefix, file_cell, name).
    file_cell is the whole File cell; it differs from file_prefix only when the cell
    carries an annotation (E0 leaves 12/20/70 ambiguous and 71/72/73 unobserved), and
    for those rows file_prefix is the doc's label, not a measured pin."""
    rows = {}
    if not CHRB_MAP.exists():
        return rows
    for line in CHRB_MAP.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|\s*(([a-z]{2}_[a-z]_\d+)\b[^|]*?)\s*\|\s*([^|]+?)\s*\|", line)
        if m:
            rows[int(m.group(1))] = (m.group(3), m.group(2), m.group(4))
    return rows


def load_chrb_map():
    """chr_b index -> (file_prefix, name) for the rows with a clean File cell only;
    annotated (ambiguous/unobserved) rows are left out so resolve() never treats
    them as a pin. Use load_chrb_rows() to see every row."""
    return {i: (f, n) for i, (f, cell, n) in load_chrb_rows().items() if cell == f}


def chrb_names_for(prefix: str) -> list[dict]:
    """The one names-for-prefix join shared by the cancel, knockback, mash and ua
    tables: every chr_b row whose File cell starts with this prefix, with the
    basis for the join. Annotated rows stay in, with the annotation in the basis."""
    out = []
    for idx, (f, cell, name) in sorted(load_chrb_rows().items()):
        if f != prefix:
            continue
        if cell != f:
            basis = ("File column annotated in chr_b-Complete-Mapping.md, not a clean "
                     "measured pin: " + cell)
        elif idx in KNOWN_REC0:
            basis = "File column live-verified (move_records.KNOWN_REC0)"
        elif idx in MEASURED_CHRB_FILE:
            basis = "File column measured: " + MEASURED_CHRB_FILE[idx]
        elif idx in SUSPECT_CHRB:
            basis = "File column suspect, unverified (move_records.SUSPECT_CHRB)"
        else:
            basis = "File column not flagged"
        out.append({"chr_b": idx, "name": name, "basis": basis})
    return out


def resolve(who: str):
    """-> (file_prefix, display_name).  Accepts a chr_b index, a file prefix or a name."""
    idx, prefix, name = resolve_with_index(who)
    return prefix, name


def resolve_with_index(who: str):
    """-> (chr_b_index_or_None, file_prefix, display_name).  Accepts a chr_b
    index, a file prefix or a name. The index is None only when `who` was
    itself a bare file prefix that isn't in the map at all -- in every other
    case the index is the row this resolution actually came from, which
    matters when two rows share a File-column value (the Sakura/Kakashi
    na_b_04 ambiguity chr_b-Complete-Mapping.md now flags) and a naive
    file->index reverse lookup would pick the wrong one."""
    rows = load_chrb_map()
    if re.fullmatch(r"\d+", who):
        i = int(who)
        if i not in rows:
            raise SystemExit(f"chr_b index {i} not in {CHRB_MAP.name}")
        f, n = rows[i]
        return i, f, n
    if re.fullmatch(r"[a-z]{2}_[a-z]_\d+", who):
        for i, (f, n) in rows.items():
            if f == who:
                return i, f, n
        return None, who, "(not in chr_b map)"
    hits = [(i, f, n) for i, (f, n) in rows.items() if who.lower() in n.lower()]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise SystemExit(f"no character matches {who!r}")
    raise SystemExit("ambiguous: " + ", ".join(f"{n} ({f})" for _i, f, n in hits))


def validate_file_choice(idx: int | None, prefix: str, recs: list[bytes],
                          live_record: str | None) -> None:
    """Self-validation per jus-chrb-colfile-mapping-audit-x7i2: refuse outright
    on a known mismatch against KNOWN_REC0; warn on an unverified suspect row;
    also check an explicit --live-record capture against whatever record it
    claims to be rec 0 of this resolved file."""
    if idx is not None and idx in KNOWN_REC0:
        want = bytes.fromhex(KNOWN_REC0[idx])
        got = recs[0] if recs else b""
        if got != want:
            raise SystemExit(
                f"REFUSING: chr_b {idx} resolved to {prefix}.bin, but its rec 0 "
                f"({got.hex()}) does not match the known-good rec 0 for this "
                f"character ({want.hex()}). chr_b-Complete-Mapping.md's File "
                f"column is wrong for this row (jus-chrb-colfile-mapping-audit-x7i2); "
                f"do not trust this file for chr_b {idx} until the mapping is fixed.")
        print(f"# self-check: chr_b {idx} rec 0 matches the known-good bytes for "
              f"{prefix}.bin -- OK", file=sys.stderr)
    elif idx is not None and idx in SUSPECT_CHRB:
        print(f"# WARNING: chr_b {idx} -> {prefix}.bin is one of the {len(SUSPECT_CHRB)} rows "
              f"chr_b-Complete-Mapping.md's File column is flagged suspect on "
              f"(jus-chrb-colfile-mapping-audit-x7i2); this file has NOT been "
              f"live-verified for this character. Treat this lookup as unverified.",
              file=sys.stderr)
    elif idx is not None and idx in MEASURED_CHRB_FILE:
        print(f"# measured: chr_b {idx} -> {prefix}.bin, basis: "
              f"{MEASURED_CHRB_FILE[idx]}", file=sys.stderr)
    if idx is not None:
        print(f"# resolved chr_b {idx} -> {prefix}.bin", file=sys.stderr)
    if live_record:
        live = bytes.fromhex(live_record.replace(" ", ""))
        if not recs or recs[0] != live:
            raise SystemExit(
                f"REFUSING: --live-record {live.hex()} does not match {prefix}.bin's "
                f"rec 0 ({recs[0].hex() if recs else '(empty file)'}). This file is "
                f"not the one the live game reads for this character.")
        print(f"# --live-record confirmed against {prefix}.bin rec 0", file=sys.stderr)


def col_path(prefix: str) -> Path:
    for d in COL_DIRS:
        p = d / f"{prefix}.bin"
        if p.exists():
            return p
    raise SystemExit(f"no collision file for {prefix} under {COL_DIRS[0]}")


def read_records(prefix: str) -> list[bytes]:
    d = col_path(prefix).read_bytes()
    if len(d) % RECORD_SIZE:
        print(f"warning: {prefix}.bin is {len(d)} bytes, not a multiple of {RECORD_SIZE}",
              file=sys.stderr)
    return [d[i * RECORD_SIZE:(i + 1) * RECORD_SIZE] for i in range(len(d) // RECORD_SIZE)]


def motions(prefix: str):
    """Every (member-name, Almt) pair for a character, base koma size first."""
    if not CHRARC.exists():
        return []
    out = []
    for member in [f"chr/{prefix}.aar"] + [f"chr/{prefix}_{k}.aar" for k in (4, 5, 6, 7, 8)]:
        try:
            raw = alar_v3_member(CHRARC, member)
        except KeyError:
            continue
        blob = maybe_dscp(raw)
        for a in find_almts(blob):
            if any(p.startswith("CollisionType") for p in a.props):
                out.append((member, a))
    return out


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #
def anim_record_uses(almt: Almt):
    """-> list of (anim_index, node_name, anim_id, frames, channel, [(frame, id)]).

    Walks every node of every top-level entry in the loader's framing (see
    `Almt.native_nodes`), not just node 0. A node that failed self-checks is
    skipped and its problem surfaces separately via `node_problems()`.
    """
    res = []
    for idx, nodes in almt.native_animations():
        for node in nodes:
            if not node["ok"] or node["entry"] is None:
                continue
            e = node["entry"]
            for t in e["tracks"]:
                if not t["prop"].startswith("CollisionType"):
                    continue
                res.append((idx, node["name"], e["id"], e["frames"], t["prop"], t["keys"]))
    return res


def node_problems(almt: Almt):
    """-> list of (anim_index, node_name, reason) for every node that did not decode cleanly."""
    out = []
    for idx, nodes in almt.native_animations():
        for node in nodes:
            if not node["ok"]:
                out.append((idx, node["name"], node.get("reason") or "unknown"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("who", help="chr_b index, file prefix (rk_b_01) or character name")
    ap.add_argument("--list", action="store_true",
                    help="dump every authored record of this character")
    ap.add_argument("--anim", help="animation id (hex ok: 0x2e) or 'all'")
    ap.add_argument("--record", type=int, help="show one record and who references it")
    ap.add_argument("--nodes", action="store_true",
                    help="also list, per motion member, which non-node0 ALMT nodes "
                         "decoded cleanly vs. couldn't be resolved statically")
    ap.add_argument("--live-record", metavar="HEX",
                    help="20 bytes (hex, spaces ok) of a record captured live at "
                         "runtime (e.g. a GDB rec-0 dump); refuse (nonzero exit) if "
                         "the resolved file's rec 0 doesn't contain it")
    args = ap.parse_args()

    idx, prefix, name = resolve_with_index(args.who)
    recs = read_records(prefix)
    validate_file_choice(idx, prefix, recs, args.live_record)
    print(f"# {name}  file {prefix}  records {len(recs)}  "
          f"ids 0x{CHAR_ID_BASE:03x}..0x{CHAR_ID_BASE + len(recs) - 1:03x}")
    print(f"# built-in ids 0..13 come from arm9 0x{BUILTIN_TABLE:08x} instead "
          f"(0 = plain box, no damage)")

    if args.list:
        for i, raw in enumerate(recs):
            print(fmt_record(i, raw))

    mots = motions(prefix)
    if not mots:
        print("# no ALMT motion found (need jus_files/ripped_jus_files/chr/ChrArc.aar)")
        return 0

    used = {}
    for member, almt in mots:
        for idx, node, aid, frames, chan, keys in anim_record_uses(almt):
            for f, v in keys:
                if v >= CHAR_ID_BASE:
                    used.setdefault(v - CHAR_ID_BASE, []).append((member, node, aid, chan, f))

    if args.nodes:
        print("\n# per-node decode status (node0 = SP01, always decoded by the base parser)")
        for member, almt in mots:
            probs = node_problems(almt)
            if not probs:
                print(f"  {Path(member).name}: all nodes ({', '.join(almt.nodes)}) decoded clean"
                      if almt.node_count > 1 else f"  {Path(member).name}: single node ({almt.nodes[0] if almt.nodes else '?'})")
                continue
            for idx, node, reason in probs:
                print(f"  {Path(member).name} anim[{idx}] {node}: UNDECODED -- {reason}")

    if args.anim is not None:
        want = None if args.anim == "all" else int(args.anim, 0)
        for member, almt in mots:
            for idx, node, aid, frames, chan, keys in anim_record_uses(almt):
                if want is not None and aid != want:
                    continue
                live = [(f, v) for f, v in keys]
                print(f"\n{member} anim[{idx}] id 0x{aid:02x} frames {frames} {node} {chan}:")
                for f, v in live:
                    if v >= CHAR_ID_BASE:
                        i = v - CHAR_ID_BASE
                        if i < len(recs):
                            print(fmt_record(i, recs[i], prefix=f"  f{f:<3d} -> "))
                        else:
                            print(f"  f{f:<3d} -> id 0x{v:03x} = rec {i} OUT OF RANGE")
                    else:
                        print(f"  f{f:<3d} -> built-in id {v}"
                              + ("  (plain box, no damage)" if v == 0 else ""))

    if args.record is not None:
        i = args.record
        if not 0 <= i < len(recs):
            raise SystemExit(f"record {i} out of range (0..{len(recs)-1})")
        print()
        print(fmt_record(i, recs[i]))
        for off, size, sign, fname, note in FIELDS:
            r = decode_record(recs[i])
            print(f"    +0x{off:02x} {fname:12s} = {r[fname]:>10}   {note}")
        refs = used.get(i, [])
        print(f"    referenced by: {refs if refs else 'NOTHING in the parsed motions'}")

    if not args.list and args.anim is None and args.record is None:
        # default: coverage summary, the useful one-screen answer
        print("\n# record -> (motion member, node, animation id, channel, frame)")
        for i in range(len(recs)):
            refs = used.get(i)
            if refs:
                pretty = ", ".join(f"{Path(m).name} {n} anim 0x{a:02x} {c} f{f}"
                                   for m, n, a, c, f in refs)
            else:
                pretty = "-- unreferenced in parsed motions --"
            print(f"  rec {i:3d} (id 0x{i + CHAR_ID_BASE:03x}): {pretty}")
        undecoded_total = sum(len(node_problems(almt)) for _, almt in mots)
        if undecoded_total:
            print(f"\n# {undecoded_total} node(s) across all motion members could not be "
                  f"decoded (self-checks failed); rerun with --nodes for details. Any record "
                  f"shown unreferenced above may live on one of those.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
