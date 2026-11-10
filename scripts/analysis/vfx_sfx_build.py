#!/usr/bin/env python3
"""Build docs/rebuild/vfx-sfx.json: hit sparks, effect spawns and sounds, from the bytes.

Why (jus-wmqi.6.12): one machine-readable table of which
effect and which sound each hit, guard, clash and move plays. Every value
here is read from the ROM, the ripped archives or the SDAT on each build;
nothing is typed in by hand except the addresses to read. vfx-sfx.md says
what each part means and how sure we are.

Sources (all under jus_files/, untracked):
  ov6 / arm9           rom_loader.load_memory_map()  (dispatcher tables, spawn sites)
  chrbin/chr/effect/   per-character hit-effect tables (8-byte records)
  chrbin/chr/col/      collision records (+0x0E hit effect, +0x0F onomatopoeia)
  ChrArc.aar, efc/     effect bundles (effect_render.effect_anims)
  JS2_sound.sdat       sequence names and one-shot render stats (sfx_render)

Usage:
    python3 scripts/analysis/vfx_sfx_build.py            # write the JSON
    python3 scripts/analysis/vfx_sfx_build.py --check    # exit 1 if it is stale
    python3 scripts/analysis/vfx_sfx_build.py --tables   # print the vfx-sfx.md tables
    python3 scripts/analysis/vfx_sfx_build.py --check --char NAME [--chr-b N] [--prefix P]
        check one character: a roster one against the committed JSON, any other
        (e.g. --char eve --chr-b 37) only has to decode. Writing a --char needs --out.

The roster is decoder_roster.json; other characters come from char_args.py.
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(HERE))

import anim_events as ae  # noqa: E402
import anim_timing as at  # noqa: E402
import char_args  # noqa: E402
import effect_render as er  # noqa: E402
import move_records as mr  # noqa: E402
import rom_loader  # noqa: E402
import sfx_render as sf  # noqa: E402

OUT_JSON = REPO / "docs" / "rebuild" / "vfx-sfx.json"
EFFECT_DIR = REPO / "jus_files" / "chrbin" / "chr" / "effect"

SPAWN = 0x0206C7FC           # effect spawn: r0 id, r1 x, r2 y, r3 flag
PLAY = 0x0207342C            # sound wrapper: r0 seqarc, r1 sequence
DISPATCH = 0x02153CE8        # ov6 hit-effect dispatcher
SOUND_TABLE = 0x02171E2C     # ov6: 16 x u32 sequence in SEQ_BATTLE
PAIR_TABLE = 0x02171E6C      # ov6: 16 x 2 x u32 spark ids
ARG7_TABLE = 0x02171E1C      # ov6: 4 x u32 (indexed by record +0x10)
ARG8_TABLE = 0x02171E0C      # ov6: 8 x u16 (indexed by record +0x11)
ONOMATOPOEIA_BASE = 0x240000
SEQ_BATTLE = 0x7A
CHARS = tuple(char_args.roster())
KOMA_SETS = (4, 5, 6)         # <prefix>_<n>.aar, a special-move archive, when the character has one
COMM_SOURCES = ("comm_a", "comm_b", "comm_c", "comm_g")
# SE_FLOORDWN (SEQ_BATTLE 0x29): the touchdown effect plays it. The generic pop and
# launcher reaction handlers (ov6 0x0215B910 / 0x0215BAB8) play it; INFERRED which of them a
# fighter's floor landing reaches.
# SE_HVYSWDFURI (0x19) and SE_TUKI (0x1a): Eve's Y and anim 0x28 play the first, her up B the second.
WAV_TARGETS = ("SE_HIT", "SE_HVYHIT", "SE_SLASH", "SE_HVYSLASH", "SE_KABOOM", "SE_GUARD",
               "SE_SOUSAI", "SE_DASH", "SE_DRON", "SE_FURI", "SE_HVYFURI", "SE_KO", "SE_CHRCHNG",
               "SE_FLOORDWN", "SE_HVYSWDFURI", "SE_TUKI")

# (label, ldr of the effect id, bl, overlay, [mov r?,#seqarc], [mov r?,#seq]).
# The id is the ldr's literal-pool word; the call target is decoded from the bl.
SITES = [
    ("guard spark", 0x02081D30, 0x02081D40, None, 0x02081D44, 0x02081D48),
    ("clash spark (0x02080E5C)", 0x02080E7C, 0x02080EEC, None, 0x02080E84, 0x02080E88),
    ("clash spark (0x02080C70)", 0x02080C90, 0x02080D00, None, 0x02080C98, 0x02080C9C),
    ("grab text (block at 0x020826E8)", 0x02082714, 0x0208272C, None, None, None),
    ("0x210012 (arm9)", 0x0207E7A8, 0x0207E7B0, None, None, None),
    ("0x210012 (ov6)", 0x02167178, 0x02167188, 6, None, None),
    ("KO-state load (ov6 0x0215C7C8)", 0x0215C7C8, 0x0215C7D0, 6, None, None),
    ("KO-state load (ov6 0x0215C4F8)", 0x0215C4F8, 0x0215C504, 6, None, None),
]
DISPATCH_CALLERS = (0x02081A24, 0x02082134)

# One more hop for sites whose bl is a helper, not the spawn call:
# site bl -> (the helper's bl that the id reaches, overlay, words that must
# hold for the id to get there). The build refuses to run if a word differs.
HOPS = {
    # 0x0215F6E4(obj, id, r2): r2 == 0 takes 0x0215F718, which spawns the id
    # at [[[[obj+0x1A8]+0x10]+0x5C]+0xC / +0x10] >> 8 with flag 0.
    0x0215C504: (0x0215F73C, 6, [
        (0x0215C500, 0xE3A02000, "mov r2, #0 (the caller)"),
        (0x0215F6EC, 0xE3520000, "cmp r2, #0"),
        (0x0215F6F0, 0x0A000008, "beq 0x0215F718"),
        (0x0215F71C, 0xE1A00001, "mov r0, r1 (the id)"),
        (0x0215F724, 0xE3A03000, "mov r3, #0 (flag)"),
    ]),
    # 0x02159B8C(obj, id): passes the id on in r1 to
    # 0x02023894([[obj+0xAC]+4], id, 0), a lookup through 0x0201C170.
    0x0215C7D0: (0x02159BA0, 6, [
        (0x02159B90, 0xE1A04000, "mov r4, r0"),
        (0x02159B94, 0xE59400AC, "ldr r0, [r4, #0xac]"),
        (0x02159B98, 0xE3A02000, "mov r2, #0"),
        (0x02159B9C, 0xE5900004, "ldr r0, [r0, #4]"),
    ]),
}


def _hex(v: int, w: int = 6) -> str:
    return f"0x{v:0{w}x}"


class Rom:
    def __init__(self):
        self.mm = rom_loader.load_memory_map()

    def word(self, addr: int, overlay=None) -> int:
        return struct.unpack("<I", self.mm.read(addr, 4, overlay=overlay))[0]

    def half(self, addr: int, overlay=None) -> int:
        return struct.unpack("<H", self.mm.read(addr, 2, overlay=overlay))[0]

    def bl_target(self, addr: int, overlay=None) -> int:
        w = self.word(addr, overlay)
        if (w >> 24) & 0xF != 0xB:
            raise ValueError(f"{addr:#x}: {w:#010x} is not a bl")
        off = w & 0xFFFFFF
        off -= (1 << 24) if off & 0x800000 else 0
        return addr + 8 + 4 * off

    def ldr_literal(self, addr: int, overlay=None) -> int:
        w = self.word(addr, overlay)
        if w & 0x0F7F0000 != 0x051F0000:
            raise ValueError(f"{addr:#x}: {w:#010x} is not ldr rX, [pc, #imm]")
        imm = w & 0xFFF
        return self.word(addr + 8 + (imm if w & 0x00800000 else -imm), overlay)

    def mov_imm(self, addr: int, overlay=None) -> int:
        w = self.word(addr, overlay)
        if w & 0x0FEF0F00 != 0x03A00000:
            raise ValueError(f"{addr:#x}: {w:#010x} is not mov rX, #imm8")
        return w & 0xFF


def seq_names(sdat: sf.Sdat, seqarc: int = SEQ_BATTLE) -> list:
    return sdat.d["symb"]["seqarc_seqs"][seqarc]


def dispatch(rom: Rom, names: list) -> dict:
    sounds = [rom.word(SOUND_TABLE + 4 * i, 6) for i in range(16)]
    pairs = [[rom.word(PAIR_TABLE + 8 * i + 4 * k, 6) for k in (0, 1)] for i in range(16)]
    rows = [{"index": i, "sound": s, "sound_name": names[s], "pair": [_hex(p) for p in pairs[i]]}
            for i, s in enumerate(sounds)]
    return {
        "address": _hex(DISPATCH, 8),
        "callers": {_hex(c, 8): _hex(rom.bl_target(c), 8) for c in DISPATCH_CALLERS},
        "sound_table": _hex(SOUND_TABLE, 8),
        "pair_table": _hex(PAIR_TABLE, 8),
        "rows": rows,
        "arg7_table": [rom.word(ARG7_TABLE + 4 * i, 6) for i in range(4)],
        "arg8_table": [rom.half(ARG8_TABLE + 2 * i, 6) for i in range(8)],
    }


def expect_words(rom: Rom, words: list, overlay) -> None:
    for addr, want, what in words:
        got = rom.word(addr, overlay)
        if got != want:
            raise ValueError(f"{addr:#x}: {got:#010x}, want {want:#010x} ({what})")


def sites(rom: Rom, names: list) -> list:
    out = []
    for label, ldr, bl, ov, m0, m1 in SITES:
        tgt = rom.bl_target(bl, ov)
        via, last = [], tgt
        if bl in HOPS:
            hop, hov, words = HOPS[bl]
            expect_words(rom, words, hov)
            last = rom.bl_target(hop, hov)
            via.append({"call": _hex(hop, 8), "call_target": _hex(last, 8)})
        row = {"what": label, "effect": _hex(rom.ldr_literal(ldr, ov)), "id_load": _hex(ldr, 8),
               "call": _hex(bl, 8), "call_target": _hex(tgt, 8), "via": via,
               "is_spawn_call": last == SPAWN, "sound": None}
        if m0 is not None:
            sa, sq = rom.mov_imm(m0, ov), rom.mov_imm(m1, ov)
            row["sound"] = {"seqarc": _hex(sa, 2), "seq": _hex(sq, 2),
                            "name": names[sq] if sa == SEQ_BATTLE else None}
        out.append(row)
    return out


def effect_tables() -> dict:
    """chr/effect/<prefix>.bin: (u32 effect, u16 slot, u16 sound) records."""
    out = {}
    for p in sorted(EFFECT_DIR.glob("*.bin")):
        b = p.read_bytes()
        if len(b) % 8:
            raise ValueError(f"{p.name}: {len(b)} bytes, not a multiple of 8")
        out[p.stem] = [{"index": _hex(0x40 + i, 2), "effect": _hex(e), "slot": s, "sound": _hex(snd, 2)}
                       for i, (e, s, snd) in enumerate(struct.iter_unpack("<IHH", b))]
    return out


def resolve_hit(idx: int, disp: dict, table: list | None) -> dict:
    """What the dispatcher does with one selector byte (r1 side)."""
    if idx == -1:
        return {"kind": "none"}
    if idx >= 0x40:
        rec = table[idx - 0x40] if table and idx - 0x40 < len(table) else None
        return {"kind": "per-character", "record": rec}
    if idx < 16:
        r = disp["rows"][idx]
        return {"kind": "shared", "sound_name": r["sound_name"], "pair": r["pair"]}
    return {"kind": "out of table"}


def resolve_text(ono: int, disp: dict, table: list | None):
    """What the dispatcher does with the onomatopoeia byte (r2 side)."""
    if 0 <= ono < 0x40:
        return _hex(ONOMATOPOEIA_BASE | ono)
    return resolve_hit(ono, disp, table) if ono >= 0x40 else None


def hit_records(prefix: str, disp: dict, tables: dict) -> list:
    table = tables.get(prefix)
    out = []
    for i, raw in enumerate(mr.read_records(prefix)):
        d = mr.decode_record(raw)
        if d["hitEffect"] == -1 and d["onomatopoeia"] == -1:
            continue
        ono = d["onomatopoeia"]
        out.append({"record": i, "kind": d["kind"], "hit_effect": d["hitEffect"],
                    "onomatopoeia": ono,
                    "effect": resolve_hit(d["hitEffect"], disp, table),
                    "text": resolve_text(ono, disp, table)})
    return out


def kit_nobox_slots(kit: dict | None) -> dict:
    """{anim id: slot} for each kit move that names its animation (jus_anim) and has no hit boxes."""
    out = {}
    for m in (kit or {}).get("moves", []):
        if m.get("jus_anim") is not None and not m.get("boxes"):
            out[int(m["jus_anim"], 16)] = m["slot"]
    return out


def load_kit(char: str) -> dict | None:
    path = REPO / "docs" / "rebuild" / "characters" / f"{char}.kit.json"
    return json.loads(path.read_text()) if path.exists() else None


def nobox_label(char: str, aid: int, kit: dict | None) -> tuple[str, str] | None:
    """(move, source) for an anim no box capture names: a box-less kit move of a KIT_LABELS fighter takes its
    slot name, and a shared state anim (the dash) takes its name unless this character has its own
    STATE_CHECKS row for it."""
    slot = kit_nobox_slots(kit).get(aid) if char in at.KIT_LABELS else None
    if slot is not None:
        return slot, (f"kit jus_anim: {char}.kit.json moves[{slot}] (no hit boxes, so no box capture; "
                      "not measured on the animation)")
    state = at.SHARED_STATES.get(aid)
    if state is None or any(a == aid for a, *_ in at.STATE_CHECKS.get(char, [])):
        return None
    seen = [c.capitalize() for c, rows in at.STATE_CHECKS.items() if any(a == aid for a, *_ in rows)]
    return state, (f"INFERRED: state anim id 0x{aid:02x}, captured on {' and '.join(seen)}; "
                   f"not captured for {char.capitalize()}")


def move_label(char: str, aid: int, kit: dict | None = None) -> tuple[str | None, int | None, str | None]:
    """(move, koma, label_src) for an anim: koma is the special's set, None for the base kit. label_src is
    None for a label a capture gave, and names the source for one it did not (nobox_label)."""
    for sp in at.SPECIALS.get(char, []):
        if sp["anim"] == aid:
            return sp["move"], sp["koma"], None
    for name, a, _cap, _rule, opts in at.MOVES.get(char, []):
        if a == aid:
            return name, opts.get("koma"), None
    for name, a, koma in at.STATIC_MOVES.get(char, []):
        if a == aid:
            return name, koma, "STATIC: kit/komamen.toml jus_anim; event-level, not captured SFX"
    names = [n for a, n, *_ in at.STATE_CHECKS.get(char, []) if a == aid]
    if names:
        return names[0], None, None
    got = nobox_label(char, aid, kit)
    return (got[0], None, got[1]) if got else (None, None, None)


def special_hits(prefix: str, spec: dict) -> list:
    """The col records a special's hits use, with each record's kind byte (+0x00)."""
    recs = mr.read_records(prefix)
    return [{"record": h[0], "kind": mr.decode_record(recs[h[0]])["kind"], "what": h[1], "source": h[2],
             "grade": h[3] if len(h) > 3 else "measured"} for h in spec["hits"]]


def moves(char: str, prefix: str, names: list) -> list:
    ev = ae.anim_events(ae.load_almt(prefix))
    specials = {sp["anim"]: sp for sp in at.SPECIALS.get(char, [])}
    kit = load_kit(char)
    out = []
    for aid, row in sorted(ev.items()):
        if not (row["spawns"] or row["sounds"]):
            continue
        move, koma, src = move_label(char, aid, kit)
        rec = {"anim": _hex(aid, 2), "move": move}
        if move is not None:
            rec["koma"] = koma
            if src is not None:
                rec["label_src"] = src
        else:
            rec["why_no_move"] = "no capture ties this animation to a move"
        rec["archive"] = f"chr/{prefix}.aar"
        if koma is not None:
            rec["koma_archive"] = f"chr/{prefix}_{koma}.aar"
        rec.update({
            "frames": row["frames"],
            "spawns": [{"frame": s["frame"], "effect": _hex(s["effect"]), "x": s["x"], "y": s["y"],
                        "node": s["node"],
                        **{k: s[k] for k in ("parent_link", "effect_flags", "draw_prio") if k in s}}
                       for s in row["spawns"]],
            "sounds": [{"frame": s["frame"], "sub": s["sub"], "category": s["category"],
                        "id": _hex(s["id"], 2),
                        "name": names[s["id"]] if s["sub"] == 0 and s["id"] < len(names) else None}
                       for s in row["sounds"]],
            "undecoded_nodes": row["undecoded_nodes"],
        })
        if aid in specials:
            rec["hits"] = special_hits(prefix, specials[aid])
        out.append(rec)
    return out


def _has_archive(source: str) -> bool:
    try:
        mr.alar_v3_member(mr.CHRARC, f"chr/{source}.aar")
    except KeyError:
        return False
    return True


def effect_sources(chars: dict, exists=_has_archive) -> list:
    """Each character's base archive and its koma archives that exist, then the shared banks."""
    out = []
    for c in chars.values():
        p = c["prefix"]
        if not exists(p):
            raise SystemExit(f"chr/{p}.aar is not in ChrArc")
        out += [p] + [f"{p}_{n}" for n in KOMA_SETS if exists(f"{p}_{n}")]
    return out + list(COMM_SOURCES)


def sound_archives(chars: dict) -> list:
    """SDAT sequence archives to render in full: those a character names (sound_seqarc)."""
    return [c["sound_seqarc"] for c in chars.values() if c.get("sound_seqarc")]


def effects(source: str) -> dict:
    bundle = er.members(source)
    out = {}
    for eid, a in sorted(er.effect_anims(bundle, source).items()):
        row = {"member": a["member"], "frames": a["frames"],
               "cells": [[f, c] for f, c in a["cells"]],
               "texture": _hex(a["texture"]) if a["texture"] is not None else None,
               "skip": a["skip"]}
        if a["texture"] is not None:
            try:
                row["dtx"] = er.dstx_member(bundle, a["texture"])
            except ValueError:
                row["skip"] = f"texture {_hex(a['texture'])} is in another archive"
        if "texture_keys" in a:
            row["texture_keys"] = [[f, _hex(v)] for f, v in a["texture_keys"]]
            row["dtx_keys"] = [[f, er.dstx_member(bundle, v)] for f, v in a["texture_keys"]]
        out[_hex(eid)] = row
    return out


def wav_rows(sdat: sf.Sdat, move_rows: dict, chars: dict) -> list:
    names = seq_names(sdat)
    want = list(WAV_TARGETS)
    for rows in move_rows.values():
        for m in rows:
            for s in m["sounds"]:
                if s["name"] and s["name"] not in want:
                    want.append(s["name"])
    jobs = [(SEQ_BATTLE, names.index(n)) for n in want]
    for arc in sound_archives(chars):
        sa = sdat.seqarc_index(arc)
        jobs += [(sa, i) for i in range(len(seq_names(sdat, sa)))]
    out = []
    for sa, i in jobs:
        r = sf.render_one(sdat, sa, i, None)
        out.append({k: r[k] for k in ("seqarc_name", "index", "name", "bank_name", "seconds",
                                      "audible_seconds", "peak_dbfs", "rms_dbfs", "silent",
                                      "hit_cap", "problems")}
                   | {"notes": len(r["notes"]),
                      "wav": f"{r['seqarc_name']}_{i:02x}_{r['name']}.wav"})
    return out


def build(chars: dict | None = None) -> dict:
    """The vfx-sfx document for `chars` (default: the committed roster)."""
    chars = char_args.roster() if chars is None else chars
    rom, sdat = Rom(), sf.Sdat()
    names = seq_names(sdat)
    disp = dispatch(rom, names)
    tables = effect_tables()
    move_rows = {c: moves(c, v["prefix"], names) for c, v in chars.items()}
    return {
        "_schema": "docs/rebuild/vfx-sfx.md",
        "_generated_by": "python3 scripts/analysis/vfx_sfx_build.py",
        "_not_for_release": "ids, frames and stats only; the PNG/WAV renders stay in "
                            "jus_files/extracted/vfx-sfx/render/ (untracked)",
        "hit_dispatch": disp,
        "spawn_sites": sites(rom, names),
        "seq_battle": [{"id": _hex(i, 2), "name": n} for i, n in enumerate(names)],
        "character_effect_tables": tables,
        "hit_records": {c: hit_records(v["prefix"], disp, tables) for c, v in chars.items()},
        "moves": move_rows,
        "effects": {s: effects(s) for s in effect_sources(chars)},
        "sounds": wav_rows(sdat, move_rows, chars),
    }


# ------------------------------------------------------------------ doc tables

def _cell(v) -> str:
    return "—" if v is None or v == "" else str(v)


def table_dispatch(d: dict) -> str:
    lines = ["| index | sound (SEQ_BATTLE) | spark pair [0] / [1] |", "|---|---|---|"]
    for r in d["hit_dispatch"]["rows"]:
        lines.append(f"| {r['index']} | `0x{r['sound']:02x}` {r['sound_name']} | "
                     f"`{r['pair'][0]}` / `{r['pair'][1]}` |")
    return "\n".join(lines)


def table_sites(d: dict) -> str:
    lines = ["| site | effect | id load | call → target | sound |", "|---|---|---|---|---|"]
    for r in d["spawn_sites"]:
        snd = (f"({r['sound']['seqarc']}, {r['sound']['seq']}) {r['sound']['name']}"
               if r["sound"] else "—")
        call = f"`{r['call']}` → `{r['call_target']}`"
        for h in r["via"]:
            call += f"; its `{h['call']}` → `{h['call_target']}`"
        call += "" if r["is_spawn_call"] else " (not the spawn call)"
        lines.append(f"| {r['what']} | `{r['effect']}` | `{r['id_load']}` | {call} | {snd} |")
    return "\n".join(lines)


def table_seq_battle(d: dict) -> str:
    rows = d["seq_battle"]
    per = 4
    lines = ["| " + " | ".join(["id", "name"] * per) + " |", "|" + "---|" * (2 * per)]
    for k in range(0, len(rows), per):
        cells = []
        for r in rows[k:k + per]:
            cells += [f"`{r['id']}`", _cell(r["name"])]
        cells += [""] * (2 * per - len(cells))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def table_moves(d: dict, char: str) -> str:
    lines = ["| anim | move | koma | spawns: frame → effect (x, y) | sounds: frame → id name | "
             "hits: record (kind) |", "|---|---|---|---|---|---|"]
    for m in d["moves"][char]:
        sp = "; ".join(f"{s['frame']} → `{s['effect']}` ({s['x']}, {s['y']})" for s in m["spawns"])
        so = "; ".join(f"{s['frame']} → `{s['id']}` {s['name']}" if s["sub"] == 0 else
                       f"{s['frame']} → {s['category']} `{s['id']}`" for s in m["sounds"])
        hits = ", ".join(f"{h['record']} ({h['kind']})" for h in m.get("hits", []))
        koma = m.get("koma")
        lines.append(f"| `{m['anim']}` | {_cell(m['move'])} | {_cell(koma)} | {_cell(sp)} | {_cell(so)} | "
                     f"{_cell(hits)} |")
    return "\n".join(lines)


def table_sounds(d: dict) -> str:
    lines = ["| archive | id | name | notes | audible s | peak dBFS | file |", "|---|---|---|---|---|---|---|"]
    for r in d["sounds"]:
        aud = "silent" if r["silent"] else r["audible_seconds"]
        lines.append(f"| {r['seqarc_name']} | `0x{r['index']:02x}` | {r['name']} | {r['notes']} | "
                     f"{aud} | {r['peak_dbfs']} | `{r['wav']}` |")
    return "\n".join(lines)


def render_tables(d: dict) -> list[str]:
    return [table_dispatch(d), table_sites(d), table_seq_battle(d),
            *[table_moves(d, c) for c in d["moves"]], table_sounds(d)]


def check_committed(data: dict, sel: dict | None, out: Path) -> int:
    """--check: 1 if `out` is stale for the characters built, else 0.

    No selection: the whole document must equal the committed one. A
    selection: each character's `moves` and `hit_records` must equal its
    committed entries; one the file does not hold only has to decode.
    """
    old = json.loads(out.read_text()) if out.exists() else None
    if sel is None:
        ok = old == data
        print("fresh" if ok else f"stale: rerun {data['_generated_by']}")
        return 0 if ok else 1
    rc = 0
    for name in sel:
        if old is None or name not in old["moves"]:
            print(f"{name}: not in {out.name}; decodes clean "
                  f"({len(data['moves'][name])} animations with events, "
                  f"{len(data['hit_records'][name])} hit records)")
        elif all(old[k][name] == data[k][name] for k in ("moves", "hit_records")):
            print(f"{name}: fresh")
        else:
            print(f"{name}: stale: rerun {data['_generated_by']}")
            rc = 1
    return rc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the committed JSON is stale")
    ap.add_argument("--tables", action="store_true", help="print the generated vfx-sfx.md tables")
    ap.add_argument("--out", type=Path, default=OUT_JSON)
    char_args.add_arguments(ap)
    a = ap.parse_args(argv)
    sel = char_args.select(a)
    if a.check and sel is None and a.out == OUT_JSON:
        gaps = [f"docs/rebuild/characters/{c}.kit.json" for c in at.KIT_LABELS
                if not (REPO / "docs" / "rebuild" / "characters" / f"{c}.kit.json").exists()]
        if gaps:
            print("check skipped: needs inputs that are not part of this repository (" + ", ".join(gaps) + ")")
            return 0
    if sel is not None and not a.check and not a.tables and a.out == OUT_JSON:
        raise SystemExit("--char writes only that character: pass --out FILE, "
                         "or build the whole roster without --char")
    data = json.loads(json.dumps(build(sel)))
    if a.tables:
        print("\n\n".join(render_tables(data)))
        return 0
    text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    if a.check:
        return check_committed(data, sel, a.out)
    a.out.write_text(text)
    print(f"wrote {a.out.relative_to(REPO) if a.out.is_relative_to(REPO) else a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
