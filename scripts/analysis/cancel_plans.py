#!/usr/bin/env python3
"""cancel_plans.py -- jus-atns.4.3. Kakashi cancel/follow-up plan generator.

Builds jusemu.py plan.json dicts that walk LEFT for 26 frames (the recipe's
default approach: Kakashi faces LEFT toward Jotaro at load, 26 LEFT frames
close to contact range -- docs/research/feel-captures/kakashi-kit-2026-09-12/
plan.json templates), press an attack `A`, then press a follow-up `F` some
`k` frames after `A`'s own input frame.

Attack input templates are lifted directly from the existing, already-
verified plan.json files in kakashi-kit-2026-09-12/ (forward_b, up_b,
down_b, neutral_y, forward_y, down_y, air_b, air_y) so the walk-in/attack
timing this tracker item measures cancels against is the same timing the base-kit
capture already used.

Follow-up element ids (kakashi.md §2, RESULTS.md neutral_b /
neutral_y frame logs): B's own hitbox element is id 256; Y's are
12/257/258/259 (12 recorded in neutral_y/dash_y captures, 259 only under
the raised 8-element cap on Y/dash_y -- jus-atns.4.2).

Coarse grid (frames after the first attack's own input frame): 4, 8, 12,
16, 20, 24, 28, 32, 40. cancel_run.py refines by bisection between the
last rejected and first accepted k once the coarse pass brackets them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

WALK_FRAMES = 26  # frames 0..25 LEFT, matches kakashi-kit-2026-09-12 templates
PRESS_LEN = 3      # attack/follow presses are held for 3 frames in those templates
AIR_JUMP_TO_ATTACK_DELAY = 15  # air_b/air_y templates: jump at 26, attack press at 41

# Grounded attacks: press these buttons starting at frame WALK_FRAMES.
# `up_Y` (UP+Y held 3 frames) is both a first move (grid 2: it cancels into
# air B/air Y while airborne) and, via the same idle-plan machinery, its
# own follow-up idle baseline; `side_Y` (LEFT+Y held 3 frames) is only ever
# used here as a follow-up, but gets a standalone idle baseline the same
# way -- both match kakashi-kit-2026-09-12/{up_y,side_y}/plan.json.
GROUNDED_ATTACKS = {
    "B": ["B"],
    "side_B": ["LEFT", "B"],
    "up_B": ["UP", "B"],
    "down_B": ["DOWN", "B"],
    "Y": ["Y"],
    "side_Y": ["LEFT", "Y"],
    "down_Y": ["DOWN", "Y"],
    "up_Y": ["UP", "Y"],
}

# Air attacks: single-frame jump (A) at WALK_FRAMES, then the attack press
# AIR_JUMP_TO_ATTACK_DELAY frames later, exactly as air_b/air_y's plan.json.
AIR_ATTACKS = {
    "air_B": ["B"],
    "air_Y": ["Y"],
}

ATTACKS = list(GROUNDED_ATTACKS) + list(AIR_ATTACKS)

# Directional cancel follow-ups (jus-atns.4.3 grid 2, owner routes):
# side_Y/up_Y hold their direction + Y for 3 frames, same as their standalone
# GROUNDED_ATTACKS shape above. air_B/air_Y as FOLLOW-UPS press only the
# button (no jump/"A") -- up_Y already leaves Kakashi airborne, so a follow-
# up air B/air Y needs no jump input, unlike air_B/air_Y as a first move
# (AIR_ATTACKS, which do need the "A" jump since Kakashi starts grounded).
FOLLOWUP_BUTTONS = {
    "B": ["B"],
    "Y": ["Y"],
    "side_Y": ["LEFT", "Y"],
    "up_Y": ["UP", "Y"],
    "air_B": ["B"],
    "air_Y": ["Y"],
}
FOLLOWUP_IDS = {
    "B": {256},
    "Y": {12, 257, 258, 259},
    "side_Y": {262},
    "up_Y": {264, 265, 266},
    "air_B": {267},
    "air_Y": {268},
}
FOLLOWUPS = list(FOLLOWUP_BUTTONS)

# Movement follow-ups (jus-atns.4.7 grid 3): JUMP/DASH/GUARD, unlike every
# FOLLOWUP_BUTTONS entry above, are not a single button set held for
# PRESS_LEN frames -- each is its own short sequence of (duration, buttons)
# segments relative to the follow-up's own frame 0. `()` means a released
# frame (no buttons).
#   JUMP: "A" jump, a 2-frame press (matches kakashi.md's jump recipe).
#   DASH: physics.md §6.3's confirmed double-tap window (taps of 3-8
#     frames, release gap of 3-10 frames both dash) -- LEFT for 5, release
#     for 5, LEFT for 5, all comfortably inside that window.
#   GUARD: DOWN held 10 frames -- guides/systems/battle-system.md's
#     "Down = Guard" (NOT a shoulder button).
MOVEMENT_FOLLOWUPS = {
    "JUMP": [(2, ("A",))],
    "DASH": [(5, ("LEFT",)), (5, ()), (5, ("LEFT",))],
    "GUARD": [(10, ("DOWN",))],
}

# The state code each movement follow-up is expected to produce
# (physics.md §4.5: 0 idle, 1 walk, 2 dash, 3 guard, 4 jump start,
# 5 double-jump start, 6 airborne, 9 attack, 13 landing).
MOVEMENT_SIGNATURE_STATES = {
    "JUMP": {4, 5, 6},
    "DASH": {2},
    "GUARD": {3},
}

COARSE_GRID = [4, 8, 12, 16, 20, 24, 28, 32, 40]

DEFAULT_TAIL_FRAMES = 160

# Refuter (RESULTS.md 2026-09-13 09:55): "build_plan unions buttons on
# overlapping frames" -- a k<4 follow-up press started before the first
# move's own PRESS_LEN=3 held frames released, so the plan held BOTH
# button sets on the shared frames instead of pressing the follow-up as
# its own, separate input edge (side_B_up_Y_k2 merged to B+LEFT+UP+Y and
# produced a side Y, not an up Y). The smallest k that leaves at least
# one released frame between the first move's own last held frame
# (attack_frame + PRESS_LEN - 1) and the follow-up's first pressed frame
# (attack_frame + k) is PRESS_LEN + 1.
MIN_FOLLOWUP_K = PRESS_LEN + 1


def attack_input_frame(attack: str) -> int:
    """The frame the attack's OWN input starts (kakashi.md's "input" frame)."""
    if attack in GROUNDED_ATTACKS:
        return WALK_FRAMES
    if attack in AIR_ATTACKS:
        return WALK_FRAMES + AIR_JUMP_TO_ATTACK_DELAY
    raise ValueError(f"unknown attack {attack!r}")


def _coalesce(frame_buttons: dict[int, tuple[str, ...]]) -> list[dict]:
    """Turn a frame->buttons map into minimal contiguous segments."""
    if not frame_buttons:
        return []
    frames = sorted(frame_buttons)
    segments = []
    start = frames[0]
    prev = frames[0]
    cur = frame_buttons[frames[0]]
    for f in frames[1:]:
        buttons = frame_buttons[f]
        if f == prev + 1 and buttons == cur:
            prev = f
            continue
        segments.append({"from": start, "to": prev, "buttons": list(cur)})
        start = f
        prev = f
        cur = buttons
    segments.append({"from": start, "to": prev, "buttons": list(cur)})
    return segments


def _base_frames(attack: str) -> dict[int, tuple[str, ...]]:
    frame_buttons: dict[int, tuple[str, ...]] = {}
    for f in range(0, WALK_FRAMES):
        frame_buttons[f] = ("LEFT",)
    if attack in GROUNDED_ATTACKS:
        press = tuple(GROUNDED_ATTACKS[attack])
        start = WALK_FRAMES
        for f in range(start, start + PRESS_LEN):
            frame_buttons[f] = press
    else:
        frame_buttons[WALK_FRAMES] = ("A",)
        press = tuple(AIR_ATTACKS[attack])
        start = attack_input_frame(attack)
        for f in range(start, start + PRESS_LEN):
            frame_buttons[f] = press
    return frame_buttons


def _followup_segments(follow: str) -> list[tuple[int, tuple[str, ...]]]:
    """The (duration, buttons) segments a follow-up's own press is built
    from, relative to its own frame 0. Every FOLLOWUP_BUTTONS entry is a
    single button set held PRESS_LEN frames; MOVEMENT_FOLLOWUPS entries
    (jus-atns.4.7 grid 3) are their own explicit multi-segment shape."""
    if follow in MOVEMENT_FOLLOWUPS:
        return MOVEMENT_FOLLOWUPS[follow]
    return [(PRESS_LEN, tuple(FOLLOWUP_BUTTONS[follow]))]


def _followup_duration(follow: str) -> int:
    return sum(duration for duration, _buttons in _followup_segments(follow))


def _write_followup_segments(frame_buttons: dict[int, tuple[str, ...]],
                              follow: str, follow_frame: int) -> None:
    """Write `follow`'s own segments into `frame_buttons` starting at
    `follow_frame`. Never unions onto an already-assigned frame -- raises
    instead (RESULTS.md "Refuter" 09:55: build_plan must not union a
    follow-up's d-pad with the first move's)."""
    f = follow_frame
    for duration, buttons in _followup_segments(follow):
        for offset in range(duration):
            frame = f + offset
            if buttons:
                if frame in frame_buttons:
                    raise ValueError(
                        f"follow-up press at frame {frame} overlaps the "
                        f"first move's own held frames; unreachable once "
                        f"k >= {MIN_FOLLOWUP_K} is enforced -- never union "
                        f"a follow-up's d-pad with the first move's")
                frame_buttons[frame] = tuple(buttons)
        f += duration


def build_plan(attack: str, follow: str | None, k: int | None,
                tail_frames: int = DEFAULT_TAIL_FRAMES) -> dict:
    """Build a plan dict: walk LEFT, press `attack`, then (if `follow` is
    given) press `follow` `k` frames after `attack`'s own input frame."""
    frame_buttons = _base_frames(attack)
    attack_frame = attack_input_frame(attack)
    follow_frame = None
    if follow is not None:
        if k is None:
            raise ValueError("k is required when follow is given")
        if k < MIN_FOLLOWUP_K:
            raise ValueError(
                f"k={k} is too small: the first move's own press holds "
                f"through frame {attack_frame + PRESS_LEN - 1}, so a "
                f"follow-up press at frame {attack_frame + k} would start "
                f"before that release and get unioned onto the same held "
                f"frames instead of pressed as its own input edge "
                f"(RESULTS.md 'Refuter' 09:55); minimum k is "
                f"{MIN_FOLLOWUP_K}")
        follow_frame = attack_frame + k
        _write_followup_segments(frame_buttons, follow, follow_frame)
        name = f"{attack}_{follow}_k{k}"
    else:
        name = f"{attack}_idle"
    segments = _coalesce(frame_buttons)
    return {
        "name": name,
        "segments": segments,
        "tail_frames": tail_frames,
        "_meta": {
            "attack": attack,
            "follow": follow,
            "k": k,
            "attack_frame": attack_frame,
            "follow_frame": follow_frame,
        },
    }


def build_idle_plan(attack: str, tail_frames: int = DEFAULT_TAIL_FRAMES) -> dict:
    """Baseline plan: just the attack, no follow-up, for the idle-return
    frame measurement."""
    return build_plan(attack, None, None, tail_frames=tail_frames)


def build_followup_idle_plan(follow: str, idle_wait: int = 10,
                              tail_frames: int = DEFAULT_TAIL_FRAMES) -> dict:
    """Standalone signature baseline for a follow-up (jus-atns.4.7 grid 3):
    `idle_wait` frames of no input (nothing held from any prior move, so
    the follow-up's own press is unambiguous -- important for DASH, whose
    double-tap window would otherwise chain off a preceding LEFT hold),
    then the follow-up's own press. Used to capture each movement follow-
    up's own state-code/physics signature in isolation, not chained after
    any attack."""
    frame_buttons: dict[int, tuple[str, ...]] = {}
    _write_followup_segments(frame_buttons, follow, idle_wait)
    segments = _coalesce(frame_buttons)
    return {
        "name": f"{follow}_idle_standalone",
        "segments": segments,
        "tail_frames": tail_frames,
        "_meta": {
            "attack": None,
            "follow": follow,
            "k": None,
            "attack_frame": None,
            "follow_frame": idle_wait,
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_plan = sub.add_parser("plan", help="build one attack+follow-up plan")
    p_plan.add_argument("attack", choices=ATTACKS)
    p_plan.add_argument("follow", choices=FOLLOWUPS + list(MOVEMENT_FOLLOWUPS))
    p_plan.add_argument("k", type=int)
    p_plan.add_argument("--tail-frames", type=int, default=DEFAULT_TAIL_FRAMES)
    p_plan.add_argument("--out", type=Path)

    p_idle = sub.add_parser("idle", help="build the no-follow-up baseline plan")
    p_idle.add_argument("attack", choices=ATTACKS)
    p_idle.add_argument("--tail-frames", type=int, default=DEFAULT_TAIL_FRAMES)
    p_idle.add_argument("--out", type=Path)

    p_followup_idle = sub.add_parser(
        "followup-idle",
        help="build a movement follow-up's standalone signature baseline (grid 3)")
    p_followup_idle.add_argument("follow", choices=list(MOVEMENT_FOLLOWUPS))
    p_followup_idle.add_argument("--idle-wait", type=int, default=10)
    p_followup_idle.add_argument("--tail-frames", type=int, default=DEFAULT_TAIL_FRAMES)
    p_followup_idle.add_argument("--out", type=Path)

    args = parser.parse_args(argv)

    if args.cmd == "plan":
        plan = build_plan(args.attack, args.follow, args.k, tail_frames=args.tail_frames)
    elif args.cmd == "followup-idle":
        plan = build_followup_idle_plan(args.follow, idle_wait=args.idle_wait,
                                         tail_frames=args.tail_frames)
    else:
        plan = build_idle_plan(args.attack, tail_frames=args.tail_frames)

    text = json.dumps(plan, indent=1)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
