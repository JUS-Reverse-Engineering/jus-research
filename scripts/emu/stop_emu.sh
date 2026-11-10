#!/usr/bin/env bash
# scripts/emu/stop_emu.sh
# Stop the melonDS this session launched -- and only that one.
#
# Usage:
#   stop_emu.sh [--force]                    stop the melonDS recorded in $IPC_DIR/HOLDER
#   stop_emu.sh --pid N [--start-time T]     stop exactly pid N
#   stop_emu.sh --all-melonds-i-am-sure [PATTERN]
#                                            kill EVERY matching melonDS (no script uses this)
#
# Guarantees:
#  * Identity = argv[0] (the executable, matched literally on a path boundary,
#    never its arguments) AND the process start token recorded at launch
#    (HOLDER line 4). It is re-checked before EVERY signal, TERM and KILL alike;
#    a mismatch, an empty executable, or a reader that fails refuses with
#    exit 4 and signals nothing.
#  * Linux: every signal goes through a pidfd (pidfd_signal.py): the check and
#    the signal are bound to one process instance, so a reused PID cannot be
#    hit. If the helper cannot do that (no python3, no pidfd support, any pidfd
#    error) stop refuses with exit 5 and signals nothing; it never falls back.
#  * macOS (no pidfd): plain kill, announced on stderr, with identity re-checked
#    immediately before each kill. A PID reused inside that gap could be hit.
#  * An emu.pid-only record has no start token: a live pid is refused unless you
#    pass --start-time.
#  * This entry point always takes flock on $IPC_DIR/.lock (when flock is
#    installed), creating $IPC_DIR first if absent; nothing skips it.
#    launch_emu.sh, which holds the lock already, sources stop_emu_lib.sh
#    instead of running this script.
#    HOLDER is removed only if it still names the exact instance this run read.
#  * Runner-owned lease (lease.py): after taking .lock (the lease's own lock too), refuses
#    with exit 6 while a live lease is held unless JUS_EMU_LEASE_TOKEN and
#    JUS_EMU_LEASE_EPOCH both match it. A stale/dead lease is retired first (fenced).
#    No lease and no token: unchanged.
#  * --force only skips the "someone else holds this" warning.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=stop_emu_lib.sh
. "$HERE/stop_emu_lib.sh"
emu_stop_parse "$@"

# Serialize with launch_emu.sh and other stops, before any record is read.
# Always: nothing inherited can skip this, and an absent IPC dir is created
# (as launch_emu.sh does) so a launch that starts meanwhile cannot slip in.
if command -v flock >/dev/null 2>&1; then
  mkdir -p "$IPC_DIR" || { echo "cannot create $IPC_DIR; not stopping" >&2; exit 1; }
  exec 9>"$IPC_DIR/.lock" || { echo "cannot open $IPC_DIR/.lock; not stopping" >&2; exit 1; }
  flock 9 || { echo "cannot lock $IPC_DIR/.lock; not stopping" >&2; exit 1; }
else
  echo "note: flock not installed; launch/stop are not serialized" >&2
fi
# Authority is checked only once we hold the lock (lease.py shares it), so a takeover
# that happened while we waited is seen and an in-progress effect blocks takeover.
emu_lease_guard || exit 6

emu_stop_run
