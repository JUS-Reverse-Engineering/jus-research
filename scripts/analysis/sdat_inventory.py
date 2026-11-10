#!/usr/bin/env python3
"""Inventory and extract a Nitro SDAT (Nintendo DS sound archive) file.

Why (jus-atns.2): `jus_files/ripped_jus_files/sound/JS2_sound.sdat` has never
been parsed in this repo. This is a standard Nitro SDAT container (SYMB/INFO/
FAT/FILE blocks) as documented publicly for the DS sound driver (see e.g.
loveemu's sdat notes, feos's "SDAT File Specifications", and vgmtrans's
source) -- every field below was re-verified against the actual bytes of
this specific file (see docs/research/feel-captures/vfx-sfx-2026-09-12/
ASSETS.md "conditions" section), not trusted blindly from a web description.

Container layout (all little-endian):
    Header (0x40 bytes): "SDAT", BOM 0xFFFE, version u16, file size u32,
    header size u16 (=0x40), num blocks u16 (=4), then 4x (offset u32,
    size u32) pairs for SYMB, INFO, FAT, FILE.

    SYMB block: "SYMB", block size u32, then 8x u32 offsets (relative to the
    SYMB block start) to 8 "records": SEQ, SEQARC, BANK, WAVEARC, PLAYER,
    GROUP, PLAYER2, STRM. Each record is `count:u32` followed by `count`
    u32 offsets (again relative to the SYMB block start); each offset points
    to a NUL-terminated ASCII name, or is 0 if that slot is unnamed.
    SEQARC is the exception: its entries are 8 bytes, (name offset u32,
    sub-record offset u32), and the sub-record is a normal count-prefixed
    name list, one name per sequence inside that archive. (Before
    2026-09-23 this tool read SEQARC at a 4-byte stride, so index 2*i
    showed entry i's name beside entry 2*i's fileId: the old "SEQ_BATTLE =
    fileId 159" in ASSETS.md came from that. SEQ_BATTLE is entry 122,
    fileId 61; see scripts/tests/test_sdat_inventory.py.)

    INFO block: "INFO", block size u32, then 8x u32 offsets to the same 8
    record kinds, count-prefixed the same way, except each INFO record's
    per-item offset points to a small binary struct (not a string). This
    tool decodes the first u16 of that struct as `fileId` for the SEQ,
    SEQARC, BANK, and WAVEARC records (verified against the FAT for all
    four in this file -- see ASSETS.md); PLAYER/GROUP/PLAYER2/STRM structs
    are NOT decoded (this game's PLAYER records don't carry a plain
    fileId, and GROUP is a variable-length nested structure; both are
    reported by count only).

    FAT block: "FAT ", record count u32, then that many 16-byte entries:
    (fileOffset u32, fileSize u32, reserved u32 x2), each fileOffset/size
    being an *absolute* offset into the whole .sdat file (not relative to
    the FILE block).

    FILE block: "FILE", block size u32, then raw sub-file bytes at the
    offsets given by FAT (each individually a self-contained SSEQ, SSAR,
    SBNK, SWAR, or STRM chunk with its own magic/header).

Usage:
    python3 scripts/analysis/sdat_inventory.py <sdat> [--detail TYPE]
        [--extract OUTDIR] [--selftest]

    TYPE is one of: seq, seqarc, bank, wavarc, player, group, player2, strm

Examples:
    python3 scripts/analysis/sdat_inventory.py jus_files/ripped_jus_files/sound/JS2_sound.sdat
    python3 scripts/analysis/sdat_inventory.py JS2_sound.sdat --detail seqarc
    python3 scripts/analysis/sdat_inventory.py JS2_sound.sdat --extract out/ --fat-id 650
    python3 scripts/analysis/sdat_inventory.py --selftest

Read-only on the input file; only writes under --extract's output directory.
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

RECORD_NAMES = ["seq", "seqarc", "bank", "wavarc", "player", "group",
                 "player2", "strm"]


def cstr(b: bytes, off: int) -> str:
    end = b.find(b"\0", off)
    if end == -1:
        end = len(b)
    return b[off:end].decode("ascii", "replace")


def _name_list(b: bytes, symb_off: int, base: int) -> list[str | None]:
    cnt = struct.unpack_from("<I", b, base)[0]
    offs = struct.unpack_from(f"<{cnt}I", b, base + 4) if cnt else ()
    return [cstr(b, symb_off + o) if o else None for o in offs]


def parse_symb(b: bytes, symb_off: int) -> dict[str, list]:
    """Names per record kind. Extra key `seqarc_seqs`: for SEQARC entry i,
    the list of sequence names inside that archive (index = sound id)."""
    assert b[symb_off:symb_off + 4] == b"SYMB", "bad SYMB magic"
    recoffs = struct.unpack_from("<8I", b, symb_off + 8)
    out: dict[str, list] = {"seqarc_seqs": []}
    for rname, ro in zip(RECORD_NAMES, recoffs):
        if ro == 0:
            out[rname] = []
            continue
        base = symb_off + ro
        if rname != "seqarc":
            out[rname] = _name_list(b, symb_off, base)
            continue
        cnt = struct.unpack_from("<I", b, base)[0]
        names, seqs = [], []
        for i in range(cnt):
            no, so = struct.unpack_from("<II", b, base + 4 + 8 * i)
            names.append(cstr(b, symb_off + no) if no else None)
            seqs.append(_name_list(b, symb_off, symb_off + so) if so else [])
        out["seqarc"] = names
        out["seqarc_seqs"] = seqs
    return out


def parse_info(b: bytes, info_off: int) -> dict[str, list[int]]:
    """Returns, per record kind, an offset (relative to INFO block start)
    for every item -- callers that know the per-kind struct layout decode
    further; this function only resolves the item-offset table."""
    assert b[info_off:info_off + 4] == b"INFO", "bad INFO magic"
    recoffs = struct.unpack_from("<8I", b, info_off + 8)
    out: dict[str, list[int]] = {}
    for rname, ro in zip(RECORD_NAMES, recoffs):
        if ro == 0:
            out[rname] = []
            continue
        base = info_off + ro
        cnt = struct.unpack_from("<I", b, base)[0]
        offs = struct.unpack_from(f"<{cnt}I", b, base + 4) if cnt else ()
        out[rname] = list(offs)
    return out


def info_file_id(b: bytes, info_off: int, item_off: int) -> int | None:
    """First u16 of an INFO item struct -- verified as `fileId` for SEQ,
    SEQARC, BANK, WAVARC record kinds in this .sdat (cross-checked against
    FAT magic bytes: SSEQ/SSAR/SBNK/SWAR all resolved correctly)."""
    if item_off == 0:
        return None
    return struct.unpack_from("<H", b, info_off + item_off)[0]


def seqarc_file_id(b: bytes, d: dict, idx: int) -> int | None:
    return info_file_id(b, d["blocks"][1][0], d["info"]["seqarc"][idx])


def bank_info(b: bytes, d: dict, idx: int) -> dict:
    """INFO bank struct: fileId u16, reserved u16, 4x wave-archive id u16
    (0xFFFF = unused)."""
    o = d["blocks"][1][0] + d["info"]["bank"][idx]
    fid, _r, *wa = struct.unpack_from("<6H", b, o)
    return {"file_id": fid, "wavarcs": wa}


def parse_ssar(blob: bytes) -> dict:
    """SSAR: 0x10 header, DATA block at 0x10: magic, size, dataOffset u32
    (sequence bytecode base, from the SSAR start), count u32, then count
    12-byte records (seq offset u32 from dataOffset or 0xFFFFFFFF, bank u16,
    volume u8, channel prio u8, player prio u8, player u8, 2 pad)."""
    if blob[:4] != b"SSAR" or blob[0x10:0x14] != b"DATA":
        raise ValueError("not an SSAR")
    data_off, cnt = struct.unpack_from("<II", blob, 0x18)
    recs = []
    for i in range(cnt):
        so, bank, vol, cpr, ppr, ply = struct.unpack_from("<IHBBBB", blob, 0x20 + 12 * i)
        recs.append({"offset": None if so == 0xFFFFFFFF else so, "bank": bank, "volume": vol,
                     "channel_prio": cpr, "player_prio": ppr, "player": ply})
    return {"data_offset": data_off, "records": recs}


def parse_fat(b: bytes, fat_off: int) -> list[tuple[int, int]]:
    assert b[fat_off:fat_off + 4] == b"FAT ", "bad FAT magic"
    cnt = struct.unpack_from("<I", b, fat_off + 8)[0]
    base = fat_off + 0x0C
    out = []
    for i in range(cnt):
        foff, fsize, _r1, _r2 = struct.unpack_from("<IIII", b, base + i * 16)
        out.append((foff, fsize))
    return out


def parse_sdat(b: bytes) -> dict:
    if b[:4] != b"SDAT":
        raise ValueError(f"not an SDAT file: magic={b[:4]!r}")
    version = struct.unpack_from("<H", b, 6)[0]
    filesize = struct.unpack_from("<I", b, 8)[0]
    header_size, num_blocks = struct.unpack_from("<HH", b, 0x0C)
    blocks = []
    for i in range(num_blocks):
        off, size = struct.unpack_from("<II", b, 0x10 + i * 8)
        blocks.append((off, size))
    symb_off, symb_size = blocks[0]
    info_off, info_size = blocks[1]
    fat_off, fat_size = blocks[2] if len(blocks) > 2 else (None, None)
    symb = parse_symb(b, symb_off)
    info = parse_info(b, info_off)
    fat = parse_fat(b, fat_off) if fat_off else []
    return dict(version=version, filesize=filesize, header_size=header_size,
                num_blocks=num_blocks, blocks=blocks, symb=symb, info=info,
                fat=fat)


def magic_at(b: bytes, off: int) -> bytes:
    return b[off:off + 4]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sdat", type=Path, nargs="?")
    ap.add_argument("--detail", choices=RECORD_NAMES,
                     help="list every named/unnamed entry of one record kind")
    ap.add_argument("--extract", type=Path,
                     help="dump every FAT entry's raw bytes into this dir")
    ap.add_argument("--fat-id", type=int,
                     help="with --extract, dump only this one FAT id")
    ap.add_argument("--seqarc", metavar="NAME_OR_INDEX",
                     help="list the sequences inside one SEQARC (index = sound id)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if not args.sdat:
        ap.error("sdat file required unless --selftest")

    b = args.sdat.read_bytes()
    d = parse_sdat(b)
    print(f"{args.sdat.name}: SDAT v{d['version']:#06x}, {d['filesize']} bytes, "
          f"{d['num_blocks']} blocks, FAT entries={len(d['fat'])}")
    for rname in RECORD_NAMES:
        names = d["symb"].get(rname, [])
        named = sum(1 for n in names if n)
        print(f"  {rname:8s} SYMB count={len(names):<5d} named={named}")

    if args.detail:
        rname = args.detail
        names = d["symb"].get(rname, [])
        item_offs = d["info"].get(rname, [])
        info_off = d["blocks"][1][0]
        print(f"\n{rname} entries ({len(names)}):")
        for i, nm in enumerate(names):
            fid = info_file_id(b, info_off, item_offs[i]) if i < len(item_offs) else None
            if fid is not None and fid < len(d["fat"]):
                foff, fsize = d["fat"][fid]
                mg = magic_at(b, foff)
                print(f"  [{i:4d}] {nm or '(unnamed)':30s} fileId={fid:<5d} "
                      f"fat_off={foff:#x} size={fsize:<8d} magic={mg!r}")
            else:
                print(f"  [{i:4d}] {nm or '(unnamed)':30s} fileId={fid}")

    if args.seqarc is not None:
        names = d["symb"]["seqarc"]
        key = args.seqarc
        idx = int(key, 0) if key[:1].isdigit() else names.index(key)
        fid = seqarc_file_id(b, d, idx)
        foff, fsize = d["fat"][fid]
        ssar = parse_ssar(b[foff:foff + fsize])
        seqs = d["symb"]["seqarc_seqs"][idx]
        print(f"\nseqarc [{idx}] {idx:#x} {names[idx]} fileId={fid} size={fsize} "
              f"sequences={len(ssar['records'])}")
        for j, r in enumerate(ssar["records"]):
            nm = seqs[j] if j < len(seqs) else None
            bank = d["symb"]["bank"][r["bank"]] if r["bank"] < len(d["symb"]["bank"]) else None
            print(f"  {j:3d} {j:#04x} {nm or '(unnamed)':24s} bank={r['bank']} ({bank}) "
                  f"vol={r['volume']} offset={r['offset']}")

    if args.extract:
        outdir = args.extract
        outdir.mkdir(parents=True, exist_ok=True)
        ids = [args.fat_id] if args.fat_id is not None else range(len(d["fat"]))
        count = 0
        for fid in ids:
            foff, fsize = d["fat"][fid]
            blob = b[foff:foff + fsize]
            mg = magic_at(b, foff).decode("ascii", "replace").strip()
            ext = {"SSEQ": "sseq", "SSAR": "ssar", "SBNK": "sbnk",
                   "SWAR": "swar", "STRM": "strm"}.get(mg, "bin")
            dest = outdir / f"fat_{fid:04d}_{mg or 'RAW'}.{ext}"
            dest.write_bytes(blob)
            count += 1
        print(f"\nextracted {count} FAT entries to {outdir}")

    return 0


def selftest() -> int:
    """Build a minimal synthetic SDAT in memory and check the parser
    recovers it exactly (no ROM file required)."""
    def pad(s: bytes, n: int) -> bytes:
        return s + b"\0" * (n - len(s))

    # Build SYMB: 1 named SEQ entry "SEQ_TEST", other 7 records empty.
    symb_header_size = 8 + 8 * 4  # magic+size + 8 record offsets
    seq_record_off = symb_header_size
    seq_name_off = seq_record_off + 4 + 4  # count(1) + 1 offset
    seq_name = b"SEQ_TEST\0"
    symb_body = struct.pack("<I", 1) + struct.pack("<I", seq_name_off) + seq_name
    symb_recoffs = [seq_record_off] + [0] * 7
    symb = b"SYMB" + struct.pack("<I", 0) + struct.pack("<8I", *symb_recoffs) + symb_body
    symb = symb[:4] + struct.pack("<I", len(symb)) + symb[8:]

    info_header_size = 8 + 8 * 4
    seq_info_record_off = info_header_size
    seq_item_off = seq_info_record_off + 4 + 4
    info_body = struct.pack("<I", 1) + struct.pack("<I", seq_item_off) + struct.pack("<H", 0)
    info_recoffs = [seq_info_record_off] + [0] * 7
    info = b"INFO" + struct.pack("<I", 0) + struct.pack("<8I", *info_recoffs) + info_body
    info = info[:4] + struct.pack("<I", len(info)) + info[8:]

    fat = b"FAT " + struct.pack("<I", 0) + struct.pack("<I", 1) + struct.pack("<IIII", 0x40, 4, 0, 0)
    fat = fat[:4] + struct.pack("<I", len(fat)) + fat[8:]

    file_blk = b"FILE" + struct.pack("<I", 0) + b"SEQ\0"
    file_blk = file_blk[:4] + struct.pack("<I", len(file_blk)) + file_blk[8:]

    blocks = [symb, info, fat, file_blk]
    header_size = 0x10 + 4 * 8
    offset = header_size
    block_table = b""
    body = b""
    for blk in blocks:
        block_table += struct.pack("<II", offset, len(blk))
        body += blk
        offset += len(blk)
    total = header_size + len(body)
    header = (b"SDAT" + struct.pack("<H", 0xFEFF) + struct.pack("<H", 0x0100)
              + struct.pack("<I", total) + struct.pack("<HH", header_size, 4)
              + block_table)
    sdat_bytes = header + body

    d = parse_sdat(sdat_bytes)
    ok = (d["symb"]["seq"] == ["SEQ_TEST"] and len(d["fat"]) == 1
          and d["fat"][0] == (0x40, 4))
    print("selftest:", "PASS" if ok else "FAIL", d["symb"]["seq"], d["fat"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
