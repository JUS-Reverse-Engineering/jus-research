#!/usr/bin/env python3
"""Reference model of JUS's tap-extended ("mash") moves: a deterministic playhead
simulator.

Rules and basis: docs/rebuild/mash-table.md ("Press counting", "Reference model").
Event data: docs/rebuild/mash-table.json (scripts/analysis/mash_table.py). The core is
pure (events, anim frame count and an input word per tick in; a PathResult out); only
the loaders at the bottom and the CLI touch files.

The model, all from the ov6 disassembly unless marked TUNING:

  Playhead. One anim frame per elapsed tick (tick 0 = the anchor = press + 3). On a tick
      the playhead is at frame `fr`; events keyed at `fr` run; then `fr += 1`, or
      `fr = target` if one queued a jump (it lands on the next tick). A loop adds
      (check - marker + 1) ticks.
  Sub 0 count loop (0x02155A04). Returns if [obj+0x78] is 0. Calls the counter
      (0x021561A8) with limit ev[3]; blocked ones do nothing. Else counts presses of
      button ev[4] over window ev[5]; at ev[6] presses queues a jump to marker ev[2].
  Counter (0x021561A8). One byte at obj+0xA2 for the whole anim (reset at 0x021555D4),
      so every limited event shares it. `c = byte; byte = c + 1; if c >= limit:
      byte = 0, blocked`. It bumps on every evaluation, pressed or not. Limit -1 is
      unlimited and does not bump.
  Sub 18 two-way (0x02155A84). No counter. Fewer than ev[6] presses -> marker ev[2],
      else marker ev[3]; a jump is queued either way.
  Press count (0x021613C4) over the ring updater (0x02161148), a literal port of
      Ring below: 16 segments of an unchanged input word, each stored duration being
      length - 1, plus the current word and its duration. An edge (the button's edge mask,
      table 0x02171098) counts if its age <= window, the age being raw ticks minus the
      number of word changes since the edge. The history runs across moves. The updater
      runs before the check in the same tick. Facing is not a bit of the word: when the fighter
      faces left the updater swaps the LEFT and RIGHT bits (4 and 8), so a turn is a word change
      only while a horizontal is held. Directions are held-only bits; the shoulder bits (0x4000,
      0x8000) are edge-only. A run's duration rolls over at 600 (the model rolls at 600 too;
      no mash window reaches it).
  Idle. idle_tick = M_IDLE + (elapsed - playhead), with M_IDLE = frames + 3 for a
      grounded move (anim-timing.md). The sign matters: a loop pushes idle later.
  Contact (TUNING, 5 of 5 cases). A box key entered on tick t touches on t + 1, except
      when t is a jump landing whose target is not check + 1 and the key is at the
      target frame: delay 0. Eve k4's 24 and 37, k5's 276 at +0.
  Loop (sub 2, 0x021559C0). Counter-limited like sub 0 but with no press test: it always
      queues a jump to its marker unless blocked. Limit -1 is unlimited.
  Ground wait (sub 3, 0x02155CAC; slot 0, grounded test 0x021562E8). Arms a marker (-1
      disarms). Every callback polls slot 0 before the queued jump (slot 6): once grounded
      the playhead goes to the armed frame, slot 0 empties and the queued jump is dropped.
      The landing tick is an input: simulate(grounded_from=L + 1) for a capture landing
      label L (Eve k5: 8 of 8 measured idles). None leaves the wait unmodeled.
  Sub 20 stored jump (0x021560F8). Reads the team store (`simulate(stored=...)`, None = empty):
      an empty store does nothing; otherwise it empties the store (the first evaluation consumes it,
      a later pass of the same frame finds it empty) and, if the value is one of the event's
      `targets` (value, frame) pairs, queues a jump to that frame. An unlisted value jumps nowhere.
      Sub 19 (store) is not modeled: `stored` is the register's value when the anim starts.
  End keys (op 3 sub 1, 0x0215693C). A move ends 2 ticks after the playhead reaches its
      first end key, else at frames + 3: end_idle() (Train 51 / 45 / 60).
  Not modeled: air wait (sub 4), the physics behind the landing tick, history scope (per
      fighter vs per team, TUNING), saturation of the stored durations.

Usage:
    python3 scripts/analysis/mash_path.py bc_b_01 0x29 --edges 16,20
    python3 scripts/analysis/mash_path.py bc_b_01 0x29 --mash       # X on 1, off 1
    python3 scripts/analysis/mash_path.py bc_b_02 0x21 --mash --max-ticks 300
    python3 scripts/analysis/mash_path.py bc_b_01 0x2c --mash --landing 64   # idle 86
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional, Sequence, Union

# table 0x02171098 (edge masks) and the matching held masks, button index -> mask
EDGE_MASKS = (0x80, 0x100, 0x40, 0x1000)
HELD_MASKS = (0x400, 0x800, 0x200, 0x2000)
RING_SEGMENTS = 16
GROUNDED_IDLE_EXTRA = 3          # idle = frames + 3 (anim-timing.md)
CONTACT_DELAY = 1                # TUNING: a box that appears on tick t touches on t + 1
LANDING_CONTACT_DELAY = 0        # TUNING: ... unless it is the key a non-adjacent jump landed on
DEFAULT_HISTORY = 20             # input ticks fed before tick 0
DEFAULT_MAX_TICKS = 600

WordSource = Union[Callable[[int], int], Mapping[int, int], Sequence[int]]


# ---------------------------------------------------------------------------- ring


class Ring:
    """Literal port of the ov6 input history: updater 0x02161148, counter 0x021613C4."""

    def __init__(self) -> None:
        self.ring = [(0, 0)] * RING_SEGMENTS
        # Native init 0x021610D4 uses idx 16, cur 0. This normalized empty history
        # starts at 0; the wrap-quirk position depends on history and is unobservable
        # in committed cases.
        self.idx = 0
        self.cur = 0
        self.dur = 0

    def update(self, word: int) -> None:
        if word == self.cur:
            self.dur += 1
            if self.dur < 600:
                return
        self.idx = (self.idx + 1) % RING_SEGMENTS
        self.ring[self.idx] = (self.cur, self.dur)
        self.cur, self.dur = word, 0

    def held(self, mask: int) -> tuple[bool, int]:
        """0x02161440, including the entry-14 pointer reload on index underflow."""
        released = not bool(self.cur & mask)
        total = 0 if released else self.dur
        index = pointer = self.idx
        for _ in range(RING_SEGMENTS):
            word, duration = self.ring[pointer]
            if not word & mask:
                break
            total += duration
            index -= 1
            if index < 0:
                pointer = index = 15
            pointer -= 1
        return released, total

    def count(self, edge_mask: int, window: int) -> int:
        if self.dur > window:
            return 0
        age = self.dur
        n = 1 if self.cur & edge_mask else 0
        j = self.idx
        for _ in range(RING_SEGMENTS):
            age += self.ring[j][1]
            if age > window:
                break
            if self.ring[j][0] & edge_mask:
                n += 1
            j = (j - 1) % RING_SEGMENTS
        return n


# ---------------------------------------------------------------------------- data


@dataclass(frozen=True)
class MashEvent:
    """One playhead event, frames already resolved: sub 0 count_loop, sub 18 two_way, sub 2 loop
    (limit -1 = unlimited, target_true = its frame), sub 3 land_arm (target_true = the armed
    frame, None = disarm), sub 20 stored_jump (`targets` = ((value, frame), ...))."""
    frame: int
    kind: str                    # "count_loop" | "two_way" | "loop" (sub 2) | "land_arm" (sub 3) | "stored_jump" (sub 20)
    button_idx: int
    window: int
    threshold: int
    limit: Optional[int]         # count_loop / loop only; -1 = unlimited
    target_true: Optional[int]   # count_loop / loop: its marker frame; land_arm: None = disarm
    target_false: Optional[int]  # two_way only
    targets: Optional[tuple] = None   # stored_jump or hold ladder: ((duration, frame), ...)
    auto_release: bool = False


@dataclass(frozen=True)
class Eval:
    tick: int
    frame: int
    event: int                   # index into the events list
    outcome: str                 # "blocked" | "jump" | "fall" (counted, too few presses)
    presses: int


@dataclass(frozen=True)
class Jump:
    tick: int                    # the tick the event ran on
    check_frame: int
    target_frame: int
    event: int
    branch: str                  # "true" | "false" | "land" (a sub 3 arm fired, event -1)

    @property
    def landing_tick(self) -> int:
        return self.tick + 1


@dataclass(frozen=True)
class BoxEntry:
    tick: int                    # elapsed tick the key frame is the playhead
    frame: int
    label: object
    landing: bool                # entered by a jump to a non-adjacent frame
    contact_delay: int
    contact_tick: int


@dataclass(frozen=True)
class PathResult:
    frames: int
    trace: tuple[int, ...]       # playhead frame on each elapsed tick
    evals: tuple[Eval, ...]
    jumps: tuple[Jump, ...]
    entries: tuple[BoxEntry, ...]
    end_tick: Optional[int]      # first tick with the playhead past the last frame
    idle_tick: Optional[int]
    truncated: bool              # stopped by max_ticks (the loop never left)


def events_from_row(row: Mapping, *, waits: bool = False, holds: bool = False) -> list[MashEvent]:
    """Mash events of one anim row of docs/rebuild/mash-table.json: sub 0 (count_loop) and
    sub 18 (two_way). With waits=True also sub 2 (loop) and sub 3 (land_arm), on a row that has
    a sub 0 or 18 event. The default keeps the list the kit exporter indexes by event (it knows
    only the two press kinds); a row with only loop / wait / store events gives [] either way.
    A loop whose
    marker is absent from the anim has no frame and is left out; so is an arm whose marker is
    absent (a disarm, marker -1, is kept with target None)."""
    out = []
    mash = any(e.get("sub") in ((0, 1, 18) if holds else (0, 18)) for e in row["events"])
    for e in row["events"]:
        if holds and e.get("sub") == 1:
            tiers = tuple((e[f"hold_{i}"], e[f"marker_{i}_frame"])
                          for i in (1, 2, 3) if e[f"hold_{i}"])
            out.append(MashEvent(e["frame"], "hold", e["button_idx"], 0, 0, None,
                                 e["marker_default_frame"], None, tiers, bool(e["hold_flag"])))
        elif e.get("sub") == 0:
            lim = -1 if e.get("limit_unbounded") else e["limit"]
            out.append(MashEvent(e["frame"], "count_loop", e["button_idx"], e["window"],
                                 e["threshold"], lim, e["marker_frame"], None))
        elif e.get("sub") == 18:
            out.append(MashEvent(e["frame"], "two_way", e["button_idx"], e["window"],
                                 e["threshold"], None, e["marker_true_frame"],
                                 e["marker_false_frame"]))
        elif waits and mash and e.get("sub") == 2 and e["marker_frame"] is not None:
            # unconditional counter-limited jump (0x021559C0); limit -1 = unlimited
            out.append(MashEvent(e["frame"], "loop", 0, 0, 0, e["limit"], e["marker_frame"], None))
        elif waits and mash and e.get("sub") == 3 and (e["disarm"] or e["marker_frame"] is not None):
            # arm / disarm the ground-wait slot (0x02155CAC)
            out.append(MashEvent(e["frame"], "land_arm", 0, 0, 0, None, e["marker_frame"], None))
    return out


# ---------------------------------------------------------------------------- input


def tap_words(button_idx: int, edge_ticks: Iterable[int], length: int = 3) -> Callable[[int], int]:
    """Input word per tick for taps whose word edge lands on `edge_ticks` (elapsed ticks,
    may be negative). A tap holds the button for `length` ticks. Only the button's bits are
    set; direction bits never change in the trials, so they would not change the count."""
    down: set[int] = set()
    for e in edge_ticks:
        down.update(range(e, e + length))
    edge, held = EDGE_MASKS[button_idx], HELD_MASKS[button_idx]

    def word(t: int) -> int:
        if t not in down:
            return 0
        return held | (edge if (t - 1) not in down else 0)

    return word


def _word_fn(words: WordSource) -> Callable[[int], int]:
    if callable(words):
        return words
    if isinstance(words, Mapping):
        return lambda t: words.get(t, 0)
    return lambda t: words[t] if 0 <= t < len(words) else 0


# ---------------------------------------------------------------------------- core


def simulate(frames: int, events: Sequence[MashEvent], words: WordSource, *,
             box_keys: Optional[Mapping[int, object]] = None,
             max_ticks: int = DEFAULT_MAX_TICKS, history: int = DEFAULT_HISTORY,
             idle_frame: Optional[int] = None, obj78: bool = True,
             grounded_from: Optional[int] = None, stored: Optional[int] = None,
             grounded_at: Optional[Callable[[int], bool]] = None, held: Optional[int] = None) -> PathResult:
    """Run an anim's mash events for up to `max_ticks` elapsed ticks.

    held: game-axis hold H, press at -1; overrides words using the poll button.
    words: input word per elapsed tick (callable, dict or list; ticks before 0 are fed
    for `history` ticks so earlier presses count). box_keys: anim frame -> label of every
    box key (enable 0 -> 1); each time the playhead reaches one it is reported.
    idle_frame: M_IDLE on the frame axis (default frames + 3). obj78: [obj+0x78] != 0.
    grounded_from: first elapsed tick on which the fighter reads as grounded (capture landing
    tick + 1); a sub 3 arm then jumps to its marker. None = the landing is not modeled: arms
    never fire and a loop (sub 2) runs only while no arm is pending, i.e. the wait is skipped.
    grounded_at: per-tick ground predicate for runs with several landings and takeoffs.
    Overrides grounded_from when supplied; the caller supplies the slot-poll sampling phase.
    stored: the team store's value when the anim starts (None = empty); a stored_jump (sub 20)
    consumes it, see the module doc.
    """
    if held is not None:
        button = next((e.button_idx for e in events if e.kind == "hold"), 2)
        words = tap_words(button, [-1], length=held)
    word = _word_fn(words)
    ground = grounded_at
    if ground is None and grounded_from is not None:
        ground = lambda t: t >= grounded_from
    ring = Ring()
    for t in range(-history, 0):
        ring.update(word(t))
    by_frame: dict[int, list[int]] = {}
    for i, ev in enumerate(events):
        by_frame.setdefault(ev.frame, []).append(i)
    keys = dict(box_keys or {})
    counter = 0
    fr = 0
    landing: Optional[tuple[int, int]] = None      # (target frame, check frame) of this tick's jump
    pending: Optional[tuple[int, int, str, int]] = None   # slot 6: (target, event, branch, check tick)
    land_slot: Optional[int] = None                # slot 0: marker frame armed by sub 3 (None = empty)
    hold_slot = None
    store = stored                                 # the team register (None = empty)
    prev_fr = 0                                    # frame of the previous tick (before its advance)
    trace: list[int] = []
    evals: list[Eval] = []
    jumps: list[Jump] = []
    entries: list[BoxEntry] = []
    end_tick: Optional[int] = None
    t = 0
    while t < max_ticks:
        # Capture-supported sampler order: update the ring before polling slots.
        ring.update(word(t))
        # Native 0x02155700: slots 0 (ground), 5 (hold), 6 (queued jump), first firing
        # wins. Slot 6 is cleared every callback (0x02155748).
        landing = None
        slot_fired = False
        if land_slot is not None and ground is not None and ground(t):
            jumps.append(Jump(t - 1, prev_fr, land_slot, -1, "land"))
            landing = (land_slot, prev_fr)
            fr, land_slot, pending = land_slot, None, None
            slot_fired = True
        if not slot_fired and hold_slot is not None:
            i, armed_tick = hold_slot
            if not obj78:
                hold_slot = None
            elif t > armed_tick:
                ev = events[i]
                released, duration = ring.held(HELD_MASKS[ev.button_idx])
                tiers = ev.targets or ()
                if released or (ev.auto_release and duration > max((h for h, _ in tiers), default=0)):
                    target = ev.target_true
                    for threshold, marker in reversed(tiers):
                        if duration > threshold:
                            target = marker
                            break
                    jumps.append(Jump(t - 1, ev.frame, target, i, "hold"))
                    landing = (target, ev.frame)
                    fr, pending, hold_slot = target, None, None
                    slot_fired = True
        if not slot_fired and pending is not None:
            target, i, branch, ctick = pending
            jumps.append(Jump(ctick, prev_fr, target, i, branch))
            landing = (target, prev_fr)
            fr, pending = target, None
        if fr >= frames:
            end_tick = t
            break
        trace.append(fr)
        if fr in keys:
            lands = landing is not None and landing[0] == fr and landing[0] != landing[1] + 1
            delay = LANDING_CONTACT_DELAY if lands else CONTACT_DELAY
            entries.append(BoxEntry(t, fr, keys[fr], lands, delay, t + delay))
        queued: Optional[tuple[int, int, str]] = None
        if obj78:
            for i in by_frame.get(fr, ()):
                ev = events[i]
                if ev.kind == "hold":
                    hold_slot = (i, t)
                    continue
                if ev.kind == "land_arm":
                    land_slot = ev.target_true         # None (marker 255) empties the slot
                    continue
                if ev.kind == "stored_jump":
                    if store is None:
                        continue                   # an empty store does nothing
                    value, store = store, None     # the read empties it, hit or miss
                    target = dict(ev.targets or ()).get(value)
                    evals.append(Eval(t, fr, i, "jump" if target is not None else "fall", 0))
                    if target is not None and queued is None:
                        queued = (target, i, "true")
                    continue
                if ev.kind == "loop":
                    if land_slot is not None and ground is None:
                        continue                   # the wait loop of an unmodeled landing
                    if ev.limit != -1:
                        c = counter
                        counter = c + 1
                        if c >= ev.limit:
                            counter = 0
                            evals.append(Eval(t, fr, i, "blocked", 0))
                            continue
                    evals.append(Eval(t, fr, i, "jump", 0))
                    if queued is None:
                        queued = (ev.target_true, i, "true")
                    continue
                if ev.kind == "count_loop" and ev.limit != -1:
                    c = counter
                    counter = c + 1
                    if c >= ev.limit:
                        counter = 0
                        evals.append(Eval(t, fr, i, "blocked", 0))
                        continue
                presses = ring.count(EDGE_MASKS[ev.button_idx], ev.window)
                ok = presses >= ev.threshold
                if ev.kind == "count_loop":
                    target, branch = (ev.target_true, "true") if ok else (None, "false")
                else:
                    target, branch = ((ev.target_true, "true") if ok
                                      else (ev.target_false, "false"))
                evals.append(Eval(t, fr, i, "jump" if target is not None else "fall", presses))
                # First wins: a second jump queued on the same tick does not replace the
                # first. No source for this rule: the mash table has 0 same-frame event
                # pairs, so it never applies to the committed data.
                if target is not None and queued is None:
                    queued = (target, i, branch)
        prev_fr = fr
        fr += 1                                     # normal advance, always (0xA0000 Tick)
        if queued is not None:
            pending = (queued[0], queued[1], queued[2], t)
        t += 1
    truncated = end_tick is None
    idle = None
    if not truncated:
        m_idle = idle_frame if idle_frame is not None else frames + GROUNDED_IDLE_EXTRA
        idle = m_idle + (end_tick - fr)            # elapsed - playhead; fr == frames + overshoot
    return PathResult(frames, tuple(trace), tuple(evals), tuple(jumps), tuple(entries),
                      end_tick, idle, truncated)


END_KEY_DELAY = 2                # the move ends 2 ticks after the playhead reaches an end key


def end_idle(res: PathResult, ends: Iterable[int]) -> Optional[int]:
    """Idle tick of a run under the end-key rule: 2 ticks after the first tick whose playhead
    is an end key (op 3 sub 1 frame, `ends` of the mash-table row), else the model's own
    frames + 3 idle. A key at `frames` is reached when the run ends with the playhead on it.
    None if the run was truncated."""
    keys = set(ends)
    for t, f in enumerate(res.trace):
        if f in keys:
            return t + END_KEY_DELAY
    if res.truncated:
        return None
    if res.frames in keys and res.idle_tick == res.end_tick + GROUNDED_IDLE_EXTRA:   # playhead == frames
        return res.end_tick + END_KEY_DELAY
    return res.idle_tick


# ---------------------------------------------------------------------------- loaders

REPO = Path(__file__).resolve().parent.parent.parent
TABLE_PATH = REPO / "docs" / "rebuild" / "mash-table.json"
BOXES_PATH = REPO / "docs" / "rebuild" / "collision-boxes.json"


def load_table(path: Path = TABLE_PATH) -> dict:
    with open(path) as fh:
        return json.load(fh)


def find_anim(table: Mapping, prefix: str, anim_id: int) -> dict:
    for char in table["characters"]:
        if char["prefix"] == prefix:
            for row in char["anims"]:
                if int(row["anim"], 16) == anim_id:
                    return row
    raise KeyError(f"{prefix} anim 0x{anim_id:02x} is not in the mash table")


def load_box_keys(prefix: str, anim_id: int, path: Path = BOXES_PATH) -> dict[int, object]:
    """Frames where a box channel turns on (enable 0 -> 1), as frame -> box type id,
    from docs/rebuild/collision-boxes.json. Channel 0 (the body) is skipped."""
    with open(path) as fh:
        chars = json.load(fh)["characters"]
    char = next(c for c in chars.values() if c["prefix"] == prefix)
    anim = char["animations"][f"{anim_id:02x}"]
    out: dict[int, object] = {}
    for ch in anim["channels"]:
        if ch["channel"] == 0:
            continue
        types = dict(map(tuple, ch["type"]))
        on = False
        for f, enable in ch["enable"]:
            if enable and not on:
                out[f] = types.get(f)
            on = bool(enable)
    return out


# ---------------------------------------------------------------------------- CLI


def format_result(res: PathResult) -> str:
    lines = [f"frames {res.frames}, ticks run {len(res.trace)}, end tick {res.end_tick}, "
             f"idle tick {res.idle_tick}" + (", TRUNCATED (loop never left)" if res.truncated else "")]
    for v in res.evals:
        lines.append(f"  eval  t{v.tick:<4} f{v.frame:<3} ev{v.event} {v.outcome:<7} presses {v.presses}")
    for j in res.jumps:
        lines.append(f"  jump  t{j.tick:<4} f{j.check_frame} -> f{j.target_frame} ({j.branch}), "
                     f"playhead f{j.target_frame} on t{j.landing_tick}")
    for e in res.entries:
        lines.append(f"  box   t{e.tick:<4} f{e.frame:<3} {e.label} contact t{e.contact_tick} "
                     f"(+{e.contact_delay}{', landing' if e.landing else ''})")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prefix")
    ap.add_argument("anim", help="anim id, e.g. 0x29")
    ap.add_argument("--edges", default="", help="comma list of word-edge ticks (elapsed)")
    ap.add_argument("--length", type=int, default=None,
                    help="ticks each tap is held (default 3; 1 when --landing is given: a 3-tick hold "
                         "gives 54 on the k5/T/up_X_s11_g8 trial, measured 53, edge 11, landing 31)")
    ap.add_argument("--mash", action="store_true", help="edge every 2 ticks, held 1")
    ap.add_argument("--button", type=int, help="button index (default: the first event's)")
    ap.add_argument("--max-ticks", type=int, default=DEFAULT_MAX_TICKS)
    ap.add_argument("--landing", type=int,
                    help="capture landing label L: the fighter reads as grounded from tick L + 1. "
                         "Also sets the default --length to 1 (see --length)")
    args = ap.parse_args(argv)
    aid = int(args.anim, 0)
    row = find_anim(load_table(), args.prefix, aid)
    events = events_from_row(row, waits=True)
    if not events:
        ap.error("no mash events in that anim")
    button = events[0].button_idx if args.button is None else args.button
    if args.mash:
        words = tap_words(button, range(1, args.max_ticks, 2), length=1)
    else:
        edges = [int(x) for x in args.edges.split(",") if x]
        length = args.length if args.length is not None else (1 if args.landing is not None else 3)
        words = tap_words(button, edges, length=length)
    try:
        keys = load_box_keys(args.prefix, aid)
    except (KeyError, StopIteration, FileNotFoundError):
        keys = {}
    print(format_result(simulate(row["frames"], events, words, box_keys=keys,
                                 max_ticks=args.max_ticks,
                                 grounded_from=None if args.landing is None else args.landing + 1)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
