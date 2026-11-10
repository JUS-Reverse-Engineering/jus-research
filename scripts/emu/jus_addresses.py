"""Known JUS memory addresses and pointer chains.

Ported from scripts/gdb/README.md (the GDB watcher is the historical
source; this file is the go-forward single source of truth).

HP ADDRESSING WARNING (2026-08-23): current HP is a 16-bit little-endian
value in 1/64 units (displayed = raw/64), stored at the even address below
what older docs called the "1/4 scale" byte (160 displayed = 40 stored
was reading only the HIGH byte of the u16). current and MAX HP read
IDENTICALLY at full health, so a static peek cannot tell them apart; any
future correction needs a window where the value is known to be moving
(regen, a poked byte, a landed hit) to confirm which address it actually
has. Verified live: docs/research/HP-And-Damage-Runtime-Findings.md,
tracker item jus-hp-address-current-vs-max, harness handoff 2026-08-19.
"""

ADDRESSES = {
    # Battle state
    "battle_timer": 0x021DEA71,
    "special_meter_1": 0x021DF731,
    # HP, your side (active + deck slots, 0x50 apart).
    # Current HP is a u16 in 1/64 units at these bases (displayed = raw/64).
    # The old +1 values (0x021DF1D5 etc.) were the HIGH byte of MAX HP and
    # silently read max instead of current (fixed 2026-08-23, harness handoff).
    "hp_player_active": 0x021DF1D4,
    "hp_player_deck1": 0x021DF224,
    "hp_player_deck2": 0x021DF274,
    "hp_player_deck3": 0x021DF2C4,
    # HP, opponent side (+0x61C from yours)
    "hp_opp_active": 0x021DF7F0,
    "hp_opp_deck1": 0x021DF840,
    "hp_opp_deck2": 0x021DF890,
    "hp_opp_deck3": 0x021DF8E0,
    # Deck builder
    "deck_state_flag": 0x020A0C98,
    "deck_leader_bool": 0x020A2289,
    "deck_active_slot": 0x020AFEB4,
    # Code
    "fn_health_calc": 0x020784FC,
}

# Pointer chains: [base, off1, off2...] means read u32 at base, add off1,
# read u32, add off2... final value is the struct base address.
# Verified for offline/training mode (scripts/gdb/README.md, 2026-02-03).
CHAINS = {
    "player": [0x023D2A74, 0x10],
    "opponent": [0x023D2A74, 0x00, 0x10],
}

# Character-struct offsets worth watching (scripts/gdb/README.md).
_STRUCT_OFFSETS = {
    "0x78": (0x78, 1),   # ground/air state (0x22 ground, 0xC0 hitstun)
    "0x88": (0x88, 1),   # positive status id
    "0xA0": (0xA0, 2),   # negative status flags / timer pair 2
    "0x98": (0x98, 2),   # timer pair 1
    "0xD9": (0xD9, 1),   # jump counter
    "0x102": (0x102, 2), # defense timer
}

WATCH_PRESETS = {
    "hp_all": [
        {"name": "hp_all.p1", "addr": ADDRESSES["hp_player_active"], "len": 2},
        {"name": "hp_all.o1", "addr": ADDRESSES["hp_opp_active"], "len": 2},
    ],
    "player_struct": [
        {"name": "player_struct.%s" % k, "chain": CHAINS["player"],
         "offset": off, "len": ln}
        for k, (off, ln) in _STRUCT_OFFSETS.items()
    ],
    "opponent_struct": [
        {"name": "opponent_struct.%s" % k, "chain": CHAINS["opponent"],
         "offset": off, "len": ln}
        for k, (off, ln) in _STRUCT_OFFSETS.items()
    ],
    "battle": [
        {"name": "battle.timer", "addr": ADDRESSES["battle_timer"], "len": 1},
        {"name": "battle.special1", "addr": ADDRESSES["special_meter_1"], "len": 1},
    ],
}


def resolve_watch(name):
    """Expand a preset name into a list of concrete watch specs.

    Raises KeyError for unknown names.
    """
    return [dict(s) for s in WATCH_PRESETS[name]]
