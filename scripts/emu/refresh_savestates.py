#!/usr/bin/env python3
"""Rebuild verified no-heal battle savestates for a batch of deck slots.

Each manifest entry is cold-booted independently. The selected deck is checked
on the screen-driven route, its runtime chr_b roster is compared with the
manifest, auto-heal is disabled and behaviourally verified, then the final
state is saved under the requested name.

Usage:
    python3 refresh_savestates.py scripts/emu/savestate_refresh.json
    python3 refresh_savestates.py manifest.json --keep-open
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import boot_verified as BV  # noqa: E402
import find_battle_structs as F  # noqa: E402
import match_run as M  # noqa: E402
import nav  # noqa: E402
from jus_ipc import DEFAULT_DIR  # noqa: E402  live emulator IPC root

STATE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
DEFAULT_HOLDER = "codex-refresh-savestates-%d" % os.getpid()


def load_manifest(path):
    """Load and validate a manifest, returning its ordered state entries."""
    with open(path, encoding="utf-8") as stream:
        document = json.load(stream)
    entries = document.get("states") if isinstance(document, dict) else document
    if not isinstance(entries, list) or not entries:
        raise ValueError("manifest must contain a non-empty 'states' list")

    seen = set()
    checked = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("each manifest state must be an object")
        name = entry.get("state")
        deck = entry.get("deck")
        roster = entry.get("roster")
        if not isinstance(name, str) or not STATE_NAME.fullmatch(name):
            raise ValueError("state names must match %s" % STATE_NAME.pattern)
        if name in seen:
            raise ValueError("duplicate state name: %s" % name)
        if not isinstance(deck, int) or isinstance(deck, bool) or deck < 1:
            raise ValueError("deck must be a positive integer for %s" % name)
        if not isinstance(roster, list) or not roster:
            raise ValueError("roster must be a non-empty list for %s" % name)
        if any(not isinstance(index, int) or isinstance(index, bool)
               or not 0 <= index <= 73 for index in roster):
            raise ValueError("roster indices must be integers in 0..73 for %s" % name)
        if len(set(roster)) != len(roster):
            raise ValueError("roster contains duplicate indices for %s" % name)
        seen.add(name)
        checked.append({"state": name, "deck": deck, "roster": roster,
                        "label": entry.get("label", name)})
    return checked


def deck_selection_steps(deck):
    """Return button names needed to move from deck 1 to ``deck``."""
    if not isinstance(deck, int) or isinstance(deck, bool) or deck < 1:
        raise ValueError("deck must be a positive integer")
    return [("DOWN",)] * (deck - 1) + [("A",)]


def roster_matches(observed, expected):
    """Require the ordered live roster to equal the manifest roster."""
    return list(observed) == list(expected)


def build_steps(deck):
    """Build the verified boot route with an explicit deck selection."""
    select = [("btn", [button]) for (button,) in deck_selection_steps(deck)]
    return [
        ("top_menu", [("tap",) + BV.TAP_ARENA, ("btn", ["A"])], "arena_menu"),
        ("arena_menu", [("tap",) + BV.TAP_TRAINING, ("btn", ["A"])],
         "deck_select"),
        ("deck_select", select, "stage_select"),
        ("stage_select", [("btn", ["A"])], "rule_select"),
        ("rule_select", [("btn", ["START"])], "battle"),
    ]


def boot_to_deck(deck):
    """Cold-boot route to a verified battle without saving a state."""
    presses, distance = BV.reach_top_menu()
    print("  top_menu after %d START presses (distance %.2f)" %
          (presses, distance))
    for source, actions, destination in build_steps(deck):
        source_distance = BV.SL.wait_for(source)
        nav.advance(BV.PRE_PRESS_SETTLE)
        if source == "rule_select":
            taps, flags = BV.rules_off()
            print("  items+gimmicks OFF after %d taps (flags %s)" % (taps, flags))
        for action in actions:
            BV.act(action)
        if destination == "battle":
            # Custom deck battles use a different HUD fingerprint from the
            # stock training battle. The verified rule-screen transition plus
            # the battle root/side invariant is the convergent oracle here.
            root = M.resolve_addresses()
            destination_distance = 0.0
            print("  battle root 0x%08X resolved (custom HUD accepted)" % root)
        else:
            destination_distance = BV.SL.wait_for(destination, max_frames=1500)
        print("  %-14s -> %-14s verified (src %.2f, dst %.2f)" %
              (source, destination, source_distance, destination_distance))

    # Do not call B.in_battle() here. Its signature scan can select a stale
    # four-slot copy left in RAM after an earlier battle. resolve_addresses()
    # already proved the live player side, so its derived HP_PLAYER is the
    # authoritative start of the current player character array.
    return M.HP_PLAYER


def runtime_roster(base, path="/tmp/jus_refresh_roster.bin"):
    """Read the live non-empty player slots at a discovered array base."""
    F.dump_ram(path)
    with open(path, "rb") as stream:
        ram = stream.read()
    offset = base - F.BASE
    slots = [F.read_slot(ram, offset + i * F.SLOT_STRIDE) for i in range(4)]
    # The engine reserves four slots even for a three-character deck. An
    # unused slot can retain a nonzero garbage index (EDA currently exposes
    # 117 there), so validity is part of the roster oracle.
    return [slot["index"] for slot in slots
            if slot["hp"] and slot["index"] <= 73]


def cli(*args):
    result = subprocess.run([sys.executable, os.path.join(HERE, "jusemu.py")] +
                            list(args), capture_output=True, text=True, cwd=HERE)
    if result.returncode:
        raise RuntimeError("jusemu %s failed:\n%s%s" %
                           (args, result.stdout, result.stderr))
    return result.stdout


def stop_emulator(environment):
    holder_path = os.path.join(environment.get("JUS_EMU_DIR", DEFAULT_DIR),
                               "HOLDER")
    if os.path.exists(holder_path):
        with open(holder_path, encoding="utf-8") as stream:
            holder = stream.readline().strip()
            pid_text = stream.readline().strip()
        if (holder and holder != environment["JUS_EMU_HOLDER"] and
                pid_text.isdigit() and
                subprocess.run(["kill", "-0", pid_text],
                               stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL).returncode == 0):
            raise RuntimeError("refusing to stop emulator held by %r" % holder)
    subprocess.run(["bash", os.path.join(HERE, "stop_emu.sh")],
                   env=environment, check=True)


def launch_emulator(environment):
    subprocess.run(["bash", os.path.join(HERE, "launch_emu.sh"), "--keep-ipc"],
                   env=environment, check=True)


def refresh_entry(entry):
    print("\nrefreshing %s: deck %d (%s)" %
          (entry["state"], entry["deck"], entry["label"]))
    base = boot_to_deck(entry["deck"])
    observed = runtime_roster(base)
    print("  runtime roster: %s" % observed)
    if not roster_matches(observed, entry["roster"]):
        raise RuntimeError("roster mismatch for %s: expected %s, got %s" %
                           (entry["state"], entry["roster"], observed))
    M.autoheal_off()
    print("  auto-heal OFF verified")
    print(cli("state", "save", entry["state"]).strip())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("--keep-open", action="store_true",
                        help="leave the final verified battle running")
    args = parser.parse_args(argv)
    entries = load_manifest(args.manifest)
    environment = os.environ.copy()
    environment["JUS_EMU_HOLDER"] = environment.get("JUS_EMU_HOLDER", DEFAULT_HOLDER)

    try:
        for entry in entries:
            # Every entry starts from title so the deck cursor has a known origin.
            stop_emulator(environment)
            launch_emulator(environment)
            refresh_entry(entry)
    finally:
        if not args.keep_open:
            stop_emulator(environment)
    print("\nrefreshed %d savestate(s)" % len(entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
