#!/usr/bin/env python3
"""Extract the koma (character) list from the Genroh GameFAQs guide for
Jump Ultimate Stars into structured JSON.

Gem/evolution costs are deliberately dropped: only in-battle mechanics are kept.
"""

import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "raw", "45856-genroh-guide.txt")
OUT = os.path.abspath(
    os.path.join(
        HERE, "..", "..", "docs", "research", "guides", "systems", "koma-list.json"
    )
)

SERIES_TITLE = re.compile(r"^<{3,}(.+?)>{3,}\s*$")
STARS = re.compile(r"^\*{10,}\s*$")
CHAR_SEP = re.compile(r"^={10,}\s*$")
BLOCK_SEP = re.compile(r"^-{10,}\s*$")
SECTION = re.compile(r"^-([A-Z][A-Z ]*[A-Z])-\s*$")
KOMA_HEADER = re.compile(r"^(\d+) ?Koma: ?(.*)$")
JSOUL = re.compile(r"^J-Soul: ?(\d*)\s*$")
SPECIAL = re.compile(r"^Special ([AB]): ?(.*)$")
ATK_NATURE = re.compile(r"^Attack Nature: ?(.*)$")
NOTE = re.compile(r"^(?:NOTE|Note|TIP):\s*(.*)$")
BOOST = re.compile(r"^(?:Boost|BOOST): ?(.*)$")
PASSIVE = re.compile(r"^Passive Effects?: ?(.*)$")
ULTIMATE = re.compile(r"^Ultimate Actions?: ?(.*)$")
COST = re.compile(r"^Cost: ")
# All-caps line with no lowercase words other than the "aka" connector.
NAME_LINE = re.compile(r'^[A-Z0-9][A-Z0-9 .,!?&\'"()/:*+#-]*$')

# Section header -> (role, kind). "unlock" rows are evolution-chart purchases
# (music, demos, stages, quiz sets, evolution paths) with no battle stats.
SECTION_ROLES = {
    "HELP KOMA": ("help", None),
    "SUPPORT KOMA": ("support", None),
    "BATTLE KOMA": ("battle", None),
    "BATLE KOMA": ("battle", None),  # typo in the guide (Hiei)
    "DATA": ("unlock", "data"),
    "STAGE": ("unlock", "stage"),
    "QUIZ": ("unlock", "quiz"),
    "INFO CHARACTER": ("unlock", "info_character"),
    "GALAXY": ("unlock", "galaxy"),
    "EVOLUTION PATH": ("unlock", "evolution_path"),
}


def is_name_line(line, min_caps=2):
    s = line.strip()
    if not s or "[" in s or "=" in s:
        return False
    if s.startswith(("-", "*", "(", "|")):
        return False
    s = s.replace(" aka ", " ")
    if not NAME_LINE.match(s):
        return False
    return bool(re.search(r"[A-Z]{%d}" % min_caps, s)) or (
        min_caps == 1 and bool(re.search(r"[A-Z]", s))
    )


def split_boosts(text):
    """'Usopp, Shanks, Cobra(Cobra)' -> [{name, series}]"""
    out = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(.*?)\(([^)]*)\)\s*$", part)
        if m:
            out.append({"name": m.group(1).strip(), "series": m.group(2).strip()})
        else:
            out.append({"name": part, "series": None})
    return out


def load_section(lines):
    """Return the slice of the guide holding the real koma list.

    Skips the '--How to Read--' template (its series banner literally says
    'series title') and stops at the next top-level guide section.
    """
    start = None
    for i, line in enumerate(lines):
        m = SERIES_TITLE.match(line)
        if m and m.group(1).strip().lower() != "series title":
            # rewind to the '*****' banner above it
            j = i
            while j > 0 and not STARS.match(lines[j - 1]):
                j -= 1
            start = j - 1
            break
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].startswith("C6:") or lines[i].startswith("C6."):
            end = i
            while end > start and not CHAR_SEP.match(lines[end - 1]):
                end -= 1
            break
    return start, end, lines[start:end]


def parse_roster(header, rows):
    """The roster is three fixed-width columns keyed off the header line."""
    cols = [(m.start(), m.group(1)) for m in re.finditer(r"-(\w+) Characters-", header)]
    bounds = [c[0] for c in cols] + [10**6]
    roster = {c[1].lower(): [] for c in cols}
    for row in rows:
        for idx, (_, label) in enumerate(cols):
            cell = row[bounds[idx] : bounds[idx + 1]].strip()
            if cell and cell != "n/a":
                roster[label.lower()].append(cell)
    return roster


class Character:
    def __init__(self, name, series):
        self.d = {
            "name": name,
            "series": series,
            "boosts": [],
            "passive_effects": [],
            "ultimate_action": None,
            "evolution_chart": [],
            "notes": [],
            "koma": [],
            "unparsed": [],
        }


def parse_header_lines(char, lines):
    """Character preamble: Boost / Passive / Ultimate Action / Evolution Chart."""
    d = char.d
    cont = None  # where a wrapped continuation line should be appended
    for raw in lines:
        line = raw.rstrip()
        s = line.strip()
        if not s:
            cont = None
            continue
        m = BOOST.match(s)
        if m:
            d["boosts"].extend(split_boosts(m.group(1)))
            cont = None
            continue
        if PASSIVE.match(s):
            cont = "passive"
            continue
        m = ULTIMATE.match(s)
        if m:
            d["ultimate_action"] = m.group(1).strip() or None
            cont = "ultimate"
            continue
        if s.startswith("Evolution Chart:"):
            cont = "evo"
            continue
        # chart rows can be separated from their label by a blank line
        if "[" in s or s.startswith("|"):
            d["evolution_chart"].append(line)
            continue
        m = NOTE.match(s)
        if m:
            d["notes"].append(m.group(1).strip())
            cont = "note"
            continue
        if cont == "passive":
            if s.startswith("-"):
                d["passive_effects"].append(s.lstrip("- ").strip())
            elif d["passive_effects"]:
                d["passive_effects"][-1] += " " + s
            else:
                d["passive_effects"].append(s)
        elif cont == "ultimate":
            d["ultimate_action"] = ((d["ultimate_action"] or "") + " " + s).strip()
        elif cont == "evo":
            d["evolution_chart"].append(line)
        elif cont == "note" and d["notes"]:
            d["notes"][-1] += " " + s
        else:
            d["unparsed"].append(line)


def parse_help(lines):
    effect, unlock, extra, form = [], None, [], None
    for raw in lines:
        s = raw.strip()
        if not s or COST.match(s):
            continue
        if is_name_line(s):
            form = s  # team/alternate name printed above the koma sections
        elif s.startswith("("):
            if unlock is None:
                unlock = s
            else:
                extra.append(s)
        elif unlock is None:
            effect.append(s)
        else:
            extra.append(s)
    entry = {
        "role": "help",
        "size": 1,
        "effect": " ".join(effect) or None,
        "unlock": unlock,
    }
    if form:
        entry["form_name"] = form
    if extra:
        entry["unparsed"] = extra
    return [entry]


def parse_unlock(kind, lines):
    text = [s.strip() for s in lines if s.strip() and not COST.match(s.strip())]
    return [{"role": "unlock", "kind": kind, "text": text}]


PRELUDE = (BOOST, PASSIVE, ULTIMATE)


def _is_prelude(para):
    """A koma's alternate-form banner: an all-caps name plus Boost/Passive lines."""
    for raw in para:
        s = raw.strip()
        if is_name_line(s) or any(p.match(s) for p in PRELUDE):
            return True
        return False
    return False


def split_blocks(lines):
    """One koma record per 'N Koma:' header.

    Records are separated by blank lines or '-----' rules, but a record's
    shape/cost/note lines sit in their own paragraph, and an alternate-form
    banner can sit in the paragraph before the header.
    """
    paras, cur = [], []
    for raw in lines:
        if BLOCK_SEP.match(raw) or not raw.strip():
            if cur:
                paras.append(cur)
            cur = []
            continue
        cur.append(raw)
    if cur:
        paras.append(cur)

    def has_header(para):
        return any(KOMA_HEADER.match(x.strip()) for x in para)

    records, pending, leading = [], [], []
    for idx, para in enumerate(paras):
        if has_header(para):
            records.append(pending + para)
            pending = []
        elif (
            _is_prelude(para)
            and idx + 1 < len(paras)
            and has_header(paras[idx + 1])
        ):
            pending.extend(para)
        elif records:
            records[-1].extend(para)
        else:
            leading.extend(para)
    if pending:
        if records:
            records[-1].extend(pending)
        else:
            leading.extend(pending)
    return leading, records


def parse_koma_block(lines, role):
    entry = {"role": role, "size": None, "nature": None, "shape": [], "specials": []}
    unparsed, notes = [], []
    cur_special = None
    cont = None
    for raw in lines:
        line = raw.rstrip()
        s = line.strip()
        if not s:
            cont = None
            continue
        if COST.match(s):
            cont = None
            continue
        m = KOMA_HEADER.match(s)
        if m:
            entry["size"] = int(m.group(1))
            entry["nature"] = m.group(2).strip() or None
            cont = None
            continue
        m = JSOUL.match(s)
        if m:
            entry["j_soul"] = int(m.group(1)) if m.group(1) else None
            cont = None
            continue
        m = SPECIAL.match(s)
        if m:
            cur_special = {
                "slot": m.group(1),
                "name": m.group(2).strip(),
                "effects": [],
                "attack_nature": None,
            }
            entry["specials"].append(cur_special)
            cont = "special"
            continue
        m = ATK_NATURE.match(s)
        if m:
            if cur_special:
                cur_special["attack_nature"] = m.group(1).strip() or None
            else:
                unparsed.append(line)
            cont = None
            continue
        m = BOOST.match(s)
        if m:
            entry.setdefault("boosts", []).extend(split_boosts(m.group(1)))
            cont = None
            continue
        if PASSIVE.match(s):
            entry.setdefault("passive_effects", [])
            cont = "passive"
            continue
        m = ULTIMATE.match(s)
        if m:
            entry["ultimate_action"] = m.group(1).strip() or None
            cont = "ultimate"
            continue
        m = NOTE.match(s)
        if m:
            notes.append(m.group(1).strip())
            cont = "note"
            continue
        if "[" in s:
            entry["shape"].append(line)
            cont = None
            continue
        if cont == "passive":
            if s.startswith("-"):
                entry["passive_effects"].append(s.lstrip("- ").strip())
            elif entry["passive_effects"]:
                entry["passive_effects"][-1] += " " + s
            continue
        if cont == "ultimate":
            entry["ultimate_action"] = (
                (entry["ultimate_action"] or "") + " " + s
            ).strip()
            continue
        if cont == "note":
            notes[-1] += " " + s
            continue
        # An all-caps line names an alternate form of the character (Super
        # Saiyjin Goku, Soge-King) that this koma turns them into.
        if is_name_line(s) and not entry["specials"] and entry["size"] is None:
            entry["form_name"] = s
            continue
        if s.startswith("("):
            # trailing parenthetical: unlock hint, or an effect on the last move
            if entry["shape"]:
                entry.setdefault("unlock_note", []).append(s)
            elif cur_special:
                cur_special["effects"].append(s)
            elif role == "support" and entry["specials"]:
                entry["specials"][-1]["effects"].append(s)
            else:
                unparsed.append(line)
            continue
        if role == "support" and not entry["specials"]:
            # support koma list the move name as a bare line after the header
            name, effects = s, []
            m = re.match(r"^(.*?)\s*(\(.*)$", s)
            if m:
                name, effects = m.group(1).strip(), [m.group(2).strip()]
            entry["specials"].append(
                {
                    "slot": None,
                    "name": name,
                    "effects": effects,
                    "attack_nature": entry["nature"],
                }
            )
            cur_special = entry["specials"][-1]
            cont = "special"
            continue
        if cont == "special" and cur_special:
            cur_special["name"] = (cur_special["name"] + " " + s).strip()
            continue
        if entry.get("unlock_note"):
            entry["unlock_note"][-1] += " " + s  # wrapped '(Buy the path...)' note
            continue
        if role == "support" and entry["specials"]:
            # a second bare line is an alias for the same move
            entry["specials"][-1].setdefault("alt_names", []).append(s)
            continue
        unparsed.append(line)
    # split trailing parentheticals out of special names
    for sp in entry["specials"]:
        m = re.match(r"^(.*?)\s*(\(.*\))$", sp["name"])
        if m:
            sp["name"] = m.group(1).strip()
            sp["effects"].insert(0, m.group(2))
    if notes:
        entry["notes"] = notes
    if unparsed:
        entry["unparsed"] = unparsed
    return [entry]


def parse_character(name, series, lines):
    char = Character(name, series)
    # split into the header preamble plus '-SECTION-' chunks
    chunks, header, cur = [], [], None
    for raw in lines:
        m = SECTION.match(raw.strip())
        if m:
            if cur:
                chunks.append(cur)
            key = m.group(1)
            if key not in SECTION_ROLES:
                char.d["unparsed"].append(raw.rstrip())
                cur = None
                continue
            cur = (key, [])
            continue
        if cur:
            cur[1].append(raw)
        else:
            header.append(raw)
    if cur:
        chunks.append(cur)

    parse_header_lines(char, header)
    for key, body in chunks:
        role, kind = SECTION_ROLES[key]
        # Battle koma sometimes follow a -DATA-/-HELP KOMA- section with no
        # '-BATTLE KOMA-' header of their own, so every section is scanned for
        # 'N Koma:' records and the section's own text is whatever precedes them.
        leading, blocks = split_blocks(body)
        entries = []
        if any(x.strip() for x in leading):
            if role == "help":
                entries.extend(parse_help(leading))
            elif role == "unlock":
                entries.extend(parse_unlock(kind, leading))
            else:
                char.d["unparsed"].extend(x.rstrip() for x in leading if x.strip())
        for block in blocks:
            # Some characters omit the '-BATTLE KOMA-' header, so trust the
            # koma count over the section header: 1 help, 2-3 support, 4+ battle.
            size = next(
                (
                    int(m.group(1))
                    for m in (KOMA_HEADER.match(x.strip()) for x in block)
                    if m
                ),
                None,
            )
            block_role = role
            if size is not None:
                block_role = "battle" if size >= 4 else "support"
            entries.extend(parse_koma_block(block, block_role))
        char.d["koma"].extend(entries)
    return char.d


def main():
    with open(SRC, encoding="utf-8", errors="replace") as fh:
        lines = fh.read().split("\n")
    start, end, sec = load_section(lines)

    series_list = []
    cur_series = None
    i = 0
    n = len(sec)
    pending_name = None
    char_lines = []

    def flush_char():
        nonlocal pending_name, char_lines
        if pending_name and cur_series is not None:
            cur_series["characters"].append(
                parse_character(pending_name, cur_series["series"], char_lines)
            )
        pending_name, char_lines = None, []

    while i < n:
        line = sec[i]
        m = SERIES_TITLE.match(line)
        if m:
            flush_char()
            cur_series = {
                "series": m.group(1).strip(),
                "mangaka": None,
                "series_symbol": None,
                "roster": {},
                "characters": [],
                "unparsed": [],
            }
            series_list.append(cur_series)
            i += 1
            roster_header, roster_rows = None, []
            while i < n and not STARS.match(sec[i]):
                s = sec[i].rstrip()
                if s.startswith("Mangaka:"):
                    cur_series["mangaka"] = s.split(":", 1)[1].strip()
                elif s.startswith("Series Symbol:"):
                    cur_series["series_symbol"] = s.split(":", 1)[1].strip()
                elif "Characters-" in s:
                    roster_header = s
                elif s.strip():
                    roster_rows.append(s)
                i += 1
            if roster_header:
                cur_series["roster"] = parse_roster(roster_header, roster_rows)
            elif roster_rows:
                cur_series["unparsed"].extend(roster_rows)
            i += 1  # skip closing '****'
            continue
        if CHAR_SEP.match(line) or STARS.match(line):
            # a couple of separators are stray (Zoro): only end the character if
            # a new name follows, otherwise keep reading the same one
            nxt = next((x.strip() for x in sec[i + 1 : i + 6] if x.strip()), "")
            if not nxt or is_name_line(nxt, min_caps=1) or SERIES_TITLE.match(nxt):
                flush_char()
            i += 1
            continue
        if pending_name is None:
            # single-letter names exist (Death Note's "L", Neuro's "X")
            if line.strip() and is_name_line(line, min_caps=1):
                pending_name = line.strip()
            elif line.strip() and cur_series is not None:
                cur_series["unparsed"].append(line.rstrip())
            i += 1
            continue
        char_lines.append(line)
        i += 1
    flush_char()

    data = {
        "metadata": {
            "title": "Jump Ultimate Stars koma (character) list",
            "source": "gf-45856",
            "source_title": "Jump Ultimate Stars FAQ/Walkthrough",
            "source_author": "Genroh",
            "source_version": "v2.5",
            "source_url": "https://gamefaqs.gamespot.com/ds/932999-jump-ultimate-stars/faqs/45856",
            "source_lines": [start + 1, end],
            "guide_section": "C5. Koma (Character) List",
            "note": "Unverified community source. Values transcribed from a "
            "fan-written guide; not confirmed against the game.",
            "scope_note": "Gem/evolution costs are intentionally excluded; only "
            "in-battle mechanics are captured.",
        },
        "series": series_list,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    chars = sum(len(s["characters"]) for s in series_list)
    koma = [k for s in series_list for c in s["characters"] for k in c["koma"]]
    jsoul = [k for k in koma if k.get("j_soul") is not None]
    unparsed = sum(
        len(c["unparsed"]) for s in series_list for c in s["characters"]
    ) + sum(len(k.get("unparsed", [])) for k in koma) + sum(
        len(s["unparsed"]) for s in series_list
    )
    print(f"series={len(series_list)} characters={chars} koma={len(koma)}")
    for role in ("help", "support", "battle", "unlock"):
        print(f"  {role}: {sum(1 for k in koma if k['role'] == role)}")
    print(f"j_soul values={len(jsoul)}")
    print(f"specials={sum(len(k.get('specials', [])) for k in koma)}")
    print(f"unparsed lines={unparsed}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
