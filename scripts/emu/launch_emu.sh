#!/usr/bin/env bash
# scripts/emu/launch_emu.sh
# Start melonDS with the JUS ROM and the agent bridge already running, then
# wait until the bridge publishes its first heartbeat. No clicking required
# (needs the --lua-script patch from scripts/emu/patches/joypad-set.patch).
#
# Usage: bash scripts/emu/launch_emu.sh [--keep-ipc]
#   --keep-ipc   don't wipe /tmp/jus_emu first (keeps savestates and runs)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ "$(uname -s)" = Darwin ]; then
  MELONDS="${MELONDS:-$HOME/src/melonDS-lua/build/melonDS.app/Contents/MacOS/melonDS}"
else
  MELONDS="${MELONDS:-$HOME/src/melonDS-lua/build/melonDS}"
fi
ROM="${ROM:-$HOME/roms/jus.nds}"
IPC_DIR="${JUS_EMU_DIR:-/tmp/jus_emu}"
KEEP_IPC=0
for a in "$@"; do
  case "$a" in
    --keep-ipc) KEEP_IPC=1 ;;
  esac
done

# ---- lease check (P1.8a) -----------------------------------------------------
# Launch needs either the runner lease token (JUS_EMU_LEASE_TOKEN, must match the
# current lease) or an explicit legacy label (JUS_EMU_HOLDER), and the legacy path
# is refused while a runner holds a live lease (the lease itself is checked below, under
# the lock). Token AND JUS_EMU_LEASE_EPOCH are required. See README "Emulator lease".
# shellcheck source=stop_emu_lib.sh
. "$SCRIPT_DIR/stop_emu_lib.sh"
if [ -z "${JUS_EMU_LEASE_TOKEN:-}" ] && [ -z "${JUS_EMU_HOLDER:-}" ]; then
  echo "REFUSING TO LAUNCH: set JUS_EMU_LEASE_TOKEN (runner lease) or JUS_EMU_HOLDER=<label> (legacy)." >&2
  exit 6
fi

[ -x "$MELONDS" ] || { echo "no melonDS binary at $MELONDS (run build_melonds_lua.sh)"; exit 1; }
[ -f "$ROM" ] || { echo "no ROM at $ROM"; exit 1; }

# ---- exclusive-access check -------------------------------------------------
# This script wipes the shared IPC dir (and stops only the melonDS pid recorded
# by a dead holder, never "every melonDS"), so launching while another session is driving the emulator silently destroys its
# run. That happened: three wakes of runtime measurements were confounded by it
# (tracker item jus-emulator-access-not-exclusive-tum) and the symptoms all looked like
# game behaviour or bad experiment design -- attacks that never landed, a core
# frozen mid-run, a stale pending.json, and damage-formula stops that appeared
# to fire with no input.
#
# Refuse whenever a HOLDER record names a live emulator. A repeated label is
# not proof that the caller owns the existing process. Stop it explicitly
# before relaunching.
HOLDER_FILE="$IPC_DIR/HOLDER"
# Serialize check-and-publish with stop_emu.sh / other launches (released once
# HOLDER is written). The dead-holder stop below runs the stop logic from
# stop_emu_lib.sh under this same lock instead of re-entering stop_emu.sh.
mkdir -p "$IPC_DIR"
if command -v flock >/dev/null 2>&1; then
  exec 9>"$IPC_DIR/.lock"
  flock 9
else
  echo "note: flock not installed; launch/stop are not serialized" >&2
fi
# Authority is checked only now that we hold the lock lease.py shares: takeover cannot
# run until HOLDER is published, and a takeover that happened while we waited refuses us.
IPC_DIR="$IPC_DIR" emu_lease_guard || exit 6
ME="${JUS_EMU_HOLDER:-lease-${JUS_EMU_LEASE_TOKEN:-unlabelled-$PPID}}"
if [ -f "$HOLDER_FILE" ]; then
  OTHER="$(sed -n '1p' "$HOLDER_FILE" 2>/dev/null || true)"
  OTHER_PID="$(sed -n '2p' "$HOLDER_FILE" 2>/dev/null || true)"
  if [ -n "$OTHER_PID" ] && kill -0 "$OTHER_PID" 2>/dev/null; then
    echo "REFUSING TO LAUNCH: '$OTHER' holds the emulator (melonDS pid $OTHER_PID, still alive)." >&2
    echo "  since $(sed -n '3p' "$HOLDER_FILE" 2>/dev/null)" >&2
    echo "Launching would kill their emulator and wipe the shared IPC dir." >&2
    echo "Stop that holder explicitly before launching another emulator." >&2
    exit 3
  fi
fi

# Clear a dead holder's record. This stops only the melonDS pid recorded in
# HOLDER (identity-checked by start time); other melonDS processes may belong
# to another session and are left alone.
# Runs in a subshell (the stop logic exits) while this shell holds the lock.
(
  set +e
  # shellcheck source=stop_emu_lib.sh
  . "$SCRIPT_DIR/stop_emu_lib.sh"
  emu_stop_parse --force
  emu_stop_run
) || exit 1

# Clear transient IPC state, but NEVER states/ -- savestates are expensive to
# recreate (a full scripted boot-to-battle) and are the whole point of being
# able to resume an experiment. `--keep-ipc` additionally preserves runs/.
if [ "$KEEP_IPC" = 0 ]; then
  rm -rf "$IPC_DIR/cmd" "$IPC_DIR/ack" "$IPC_DIR/runs"
fi
mkdir -p "$IPC_DIR"/{cmd,ack,runs,states}
rm -f "$IPC_DIR"/heartbeat.json "$IPC_DIR"/cmd/inbox.lua \
      "$IPC_DIR"/cmd/pending.json "$IPC_DIR"/stop.flag
rm -f "$IPC_DIR"/ack/*.json 2>/dev/null || true

export JUS_EMU_SRC="$SCRIPT_DIR"
export JUS_EMU_DIR="$IPC_DIR"
export MELONDS

if [ -n "${JUS_EMU_WORKER_CONFIG:-}" ]; then
  python3 "$SCRIPT_DIR/startup_identity.py" preflight "$JUS_EMU_WORKER_CONFIG"
fi

echo "launching: $MELONDS $ROM --lua-script $SCRIPT_DIR/agent_bridge.lua"
EMU_ID="$(python3 - "$MELONDS" "$ROM" "$SCRIPT_DIR/agent_bridge.lua" "$IPC_DIR" <<'PY'
import pathlib
import subprocess
import sys

binary, rom, bridge, ipc_dir = sys.argv[1:]
ipc = pathlib.Path(ipc_dir)
with (ipc / 'emu.stdout').open('wb') as stdout, (ipc / 'emu.stderr').open('wb') as stderr:
    process = subprocess.Popen(
        [binary, rom, '--lua-script', bridge], stdin=subprocess.DEVNULL,
        stdout=stdout, stderr=stderr, start_new_session=True,
    )
# Identity token (same as stop_emu.sh proc_start): lets a later stop prove the
# pid is still this process and not a reused one.
try:
    stat = pathlib.Path(f'/proc/{process.pid}/stat').read_text()
    start = stat.rsplit(')', 1)[1].split()[19]
except OSError:
    out = subprocess.run(['ps', '-o', 'lstart=', '-p', str(process.pid)],
                         capture_output=True, text=True).stdout
    start = out.strip()
print(process.pid)
print(start)
PY
)"
EMU_PID="$(printf '%s\n' "$EMU_ID" | sed -n '1p')"
EMU_START="$(printf '%s\n' "$EMU_ID" | sed -n '2p')"
echo "$EMU_PID" > "$IPC_DIR/emu.pid"
# Claim it, so another session's launch refuses instead of killing this one.
# Line 4 is the melonDS start time; readers of lines 1-3 are unaffected.
printf '%s\n%s\n%s\n%s\n' "$ME" "$EMU_PID" "$(date '+%Y-%m-%d %H:%M:%S')" "$EMU_START" > "$HOLDER_FILE"
exec 9>&-    # release the launch/stop lock; melonDS never inherited it
echo "emulator claimed by '$ME' (pid $EMU_PID)"

# Wait for the bridge to come up. The ROM boot itself takes a few seconds.
for i in $(seq 1 60); do
  if [ -f "$IPC_DIR/heartbeat.json" ]; then
    if [ -n "${JUS_EMU_WORKER_CONFIG:-}" ]; then
      python3 "$SCRIPT_DIR/startup_identity.py" receipt "$JUS_EMU_WORKER_CONFIG" --pid "$EMU_PID"
    fi
    echo "bridge up after ${i}s:"
    cat "$IPC_DIR/heartbeat.json"; echo
    exit 0
  fi
  if ! kill -0 "$EMU_PID" 2>/dev/null; then
    echo "melonDS exited early. stderr:"; cat "$IPC_DIR/emu.stderr"; exit 1
  fi
  sleep 1
done

echo "no heartbeat after 60s. emulator still running (pid $EMU_PID)."
echo "--- stdout ---"; tail -20 "$IPC_DIR/emu.stdout" || true
echo "--- stderr ---"; tail -20 "$IPC_DIR/emu.stderr" || true
exit 1
