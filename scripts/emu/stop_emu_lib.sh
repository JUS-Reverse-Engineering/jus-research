# scripts/emu/stop_emu_lib.sh -- sourced, never run. The stop logic shared by
# stop_emu.sh (which always takes $IPC_DIR/.lock first) and launch_emu.sh
# (which already holds that lock and calls this in a subshell). Nothing here
# takes the lock, and nothing in the environment can make stop_emu.sh skip it.
#
#   emu_stop_parse "$@"   parse stop_emu.sh options (exit 2 on a usage error)
#   emu_stop_run          stop the target; the caller must hold the lock
#
# Exit codes: 0 stopped or nothing to stop, 1 still alive after KILL,
# 2 usage error, 4 identity check refused, 5 cannot signal safely here
# (Linux only: the pidfd helper failed, so nothing was signalled).
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  echo "stop_emu_lib.sh is sourced by stop_emu.sh/launch_emu.sh; run stop_emu.sh" >&2
  exit 2
fi
EMU_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

emu_stop_parse() {
  FORCE=0
  ALL=0
  TARGET_PID=""
  TARGET_START=""
  CUSTOM_PATTERN=""
  PLATFORM="$(uname -s)"
  if [ "$PLATFORM" = Darwin ]; then
    PATTERN="melonDS\\.app/Contents/MacOS/melonDS( |$)"     # broad mode only
    EXE_SUFFIX="/melonDS.app/Contents/MacOS/melonDS"
  else
    PATTERN="^[^ ]*/melonDS( |$)"                            # broad mode only
    EXE_SUFFIX="/melonDS"
  fi
  local opt
  while [ $# -gt 0 ]; do
    case "$1" in
      --force) FORCE=1 ;;
      --all-melonds-i-am-sure) ALL=1 ;;
      --pid|--start-time)
        opt="$1"
        [ $# -ge 2 ] || emu_stop_usage "$opt needs a value"
        case "$2" in ""|-*) emu_stop_usage "$opt needs a value, got '$2'" ;; esac
        if [ "$opt" = --pid ]; then
          case "$2" in *[!0-9]*) emu_stop_usage "--pid needs a number, got '$2'" ;; esac
          TARGET_PID="$2"
        else
          TARGET_START="$2"
        fi
        shift ;;
      --*) emu_stop_usage "unknown option: $1" ;;
      *) [ -n "$1" ] && CUSTOM_PATTERN="$1" ;;
    esac
    shift
  done
  [ -n "$CUSTOM_PATTERN" ] && PATTERN="$CUSTOM_PATTERN"
  IPC_DIR="${JUS_EMU_DIR:-/tmp/jus_emu}"
  HOLDER_FILE="$IPC_DIR/HOLDER"
  ME="${JUS_EMU_HOLDER:-unlabelled-$PPID}"
  return 0
}
# emu_lease_guard -> 6 (refused) unless this caller may touch the emulator under the
# runner-owned lease (lease.py). MUST be called AFTER taking $IPC_DIR/.lock and the lock must
# stay held through the effect: lease.py uses the same lock, so a takeover waits for us and
# we re-validate after any wait. JUS_EMU_LEASE_TOKEN and JUS_EMU_LEASE_EPOCH must both match
# the current lease; with no token, a held (live, fresh) or unreadable lease refuses and a
# stale/dead one is retired (epoch bump) so its old holder is fenced. No lease file and no
# token skips python entirely, so legacy operators are unchanged. Fails closed on error.
emu_lease_guard() {
  local ipc="${IPC_DIR:-${JUS_EMU_DIR:-/tmp/jus_emu}}"
  [ -n "${JUS_EMU_LEASE_TOKEN:-}" ] || [ -e "$ipc/LEASE.json" ] || return 0
  command -v python3 >/dev/null 2>&1 || { echo "REFUSING: lease present but python3 missing" >&2; return 6; }
  JUS_EMU_DIR="$ipc" python3 "$EMU_LIB_DIR/lease.py" guard --locked --token "${JUS_EMU_LEASE_TOKEN:-}" --epoch "${JUS_EMU_LEASE_EPOCH:-}" || return 6
}
emu_stop_usage() { echo "usage error: $1" >&2; exit 2; }

# proc_start PID -> a token that is stable for the life of the process.
proc_start() {
  if [ -r "/proc/$1/stat" ]; then
    # field 22 (starttime); comm may contain spaces, so cut after the last ')'.
    sed 's/^.*) //' "/proc/$1/stat" 2>/dev/null | awk '{print $20}'
  else
    ps -o lstart= -p "$1" 2>/dev/null | sed 's/^ *//; s/ *$//'
  fi
}
# proc_argv0 PID -> the executable alone (argv[0] on Linux, ps comm on macOS).
proc_argv0() {
  if [ -r "/proc/$1/cmdline" ]; then
    tr '\0' '\n' < "/proc/$1/cmdline" 2>/dev/null | head -n 1
  else
    ps -o comm= -p "$1" 2>/dev/null
  fi
}
# Only a non-empty executable ending in the melonDS path matches.
is_melonds_argv0() {
  case "$1" in
    "") return 1 ;;
    *"$EXE_SUFFIX") return 0 ;;
  esac
  return 1
}
is_alive() {
  kill -0 "$1" 2>/dev/null || return 1
  local st
  st="$(sed 's/^.*) //' "/proc/$1/stat" 2>/dev/null | awk '{print $1}')"
  [ "$st" != Z ]
}
# revalidate PID START: 0 if PID is still the same melonDS instance, else 4.
# A reader that fails or prints nothing refuses; it never counts as a match.
revalidate() {
  local a now
  if ! a="$(proc_argv0 "$1")"; then
    echo "REFUSING TO STOP pid $1: could not read its executable." >&2
    return 4
  fi
  if ! is_melonds_argv0 "$a"; then
    echo "REFUSING TO STOP pid $1: executable is not melonDS ('$a')." >&2
    return 4
  fi
  if ! now="$(proc_start "$1")" || [ -z "$now" ]; then
    echo "REFUSING TO STOP pid $1: could not read its start token." >&2
    return 4
  fi
  if [ "$now" != "$2" ]; then
    echo "REFUSING TO STOP pid $1: start token '$now' != recorded '$2' (pid reused?)." >&2
    return 4
  fi
  return 0
}
# send_sig SIG PID START -> 0 sent (or target gone), 4 identity refused,
# 5 cannot signal safely.
#  Linux: pidfd_signal.py opens a pidfd, re-checks identity, and signals
#    through it. Any helper failure (no python3, no helper, no pidfd support,
#    pidfd_open/pidfd_send_signal errors) refuses; there is no plain-kill fallback.
#  Elsewhere (macOS): plain kill, announced, with identity re-checked
#    immediately before the kill. A PID reused between that check and the kill
#    could still be hit.
send_sig() {
  if [ "$PLATFORM" = Linux ]; then
    revalidate "$2" "$3" || return 4
    local rc=0
    if [ ! -f "$EMU_LIB_DIR/pidfd_signal.py" ]; then
      rc=127
    else
      python3 "$EMU_LIB_DIR/pidfd_signal.py" "$2" "$3" "$1" "$EXE_SUFFIX" || rc=$?
    fi
    case $rc in
      0|3) return 0 ;;
      4) echo "REFUSING TO STOP pid $2: identity changed before signal." >&2; return 4 ;;
    esac
    echo "REFUSING TO STOP pid $2: pidfd signalling failed (rc $rc); on Linux there is" >&2
    echo "  no plain-kill fallback. Nothing was signalled with $1." >&2
    return 5
  fi
  echo "note: $PLATFORM has no pidfd; using plain kill after a fresh identity check" >&2
  revalidate "$2" "$3" || return 4
  kill "-$1" "$2" 2>/dev/null || true
  return 0
}

emu_stop_run() {
  local found sig remaining p left hp rc
  if [ "$ALL" = 1 ]; then
    pids() { pgrep -f "$PATTERN" 2>/dev/null || true; }
    found="$(pids)"
    if [ -n "$found" ]; then
      echo "killing EVERY match of '$PATTERN': $(echo "$found" | tr '\n' ' ')" >&2
      for sig in TERM KILL; do
        remaining="$(pids)"; [ -z "$remaining" ] && break
        for p in $remaining; do kill "-$sig" "$p" 2>/dev/null || true; done
        for _ in 1 2 3 4 5 6; do [ -z "$(pids)" ] && break; sleep 0.5; done
      done
      left="$(pids)"
      if [ -n "$left" ]; then echo "FAILED to kill: $(echo "$left" | tr '\n' ' ')" >&2; exit 1; fi
    else
      echo "no melonDS running"
    fi
    # Keep a HOLDER whose process the pattern excluded and which is still alive.
    hp="$(sed -n '2p' "$HOLDER_FILE" 2>/dev/null || true)"
    if [ -n "$hp" ] && is_alive "$hp"; then
      echo "kept HOLDER: pid $hp is alive and was not matched by the pattern" >&2
    else
      rm -f "$HOLDER_FILE"
    fi
    exit 0
  fi

  # Resolve the single target from the HOLDER record unless --pid names one.
  REC_LABEL=""; REC_PID=""; REC_START=""
  if [ -f "$HOLDER_FILE" ]; then
    REC_LABEL="$(sed -n '1p' "$HOLDER_FILE" 2>/dev/null || true)"
    REC_PID="$(sed -n '2p' "$HOLDER_FILE" 2>/dev/null || true)"
    REC_START="$(sed -n '4p' "$HOLDER_FILE" 2>/dev/null || true)"
  fi
  if [ -z "$TARGET_PID" ]; then
    TARGET_PID="$REC_PID"
    [ -z "$TARGET_PID" ] && [ -f "$IPC_DIR/emu.pid" ] && TARGET_PID="$(sed -n '1p' "$IPC_DIR/emu.pid")"
  fi
  if [ -z "$TARGET_PID" ]; then
    echo "no recorded melonDS to stop (no HOLDER/emu.pid); not touching any process"
    exit 0
  fi
  case "$TARGET_PID" in *[!0-9]*) emu_stop_usage "bad pid in record: $TARGET_PID" ;; esac
  if [ -z "$TARGET_START" ] && [ "$TARGET_PID" = "$REC_PID" ]; then TARGET_START="$REC_START"; fi

  if ! is_alive "$TARGET_PID"; then
    echo "pid $TARGET_PID is not running"
    emu_remove_record
    exit 0
  fi

  if [ -z "$TARGET_START" ]; then
    echo "REFUSING TO STOP pid $TARGET_PID: no recorded start time to prove it is our melonDS." >&2
    echo "  Pass --start-time T (from /proc/$TARGET_PID/stat field 22) if you are sure." >&2
    exit 4
  fi
  revalidate "$TARGET_PID" "$TARGET_START" || exit 4

  if [ "$FORCE" = 0 ] && [ "$TARGET_PID" = "$REC_PID" ] && [ -n "$REC_LABEL" ] && [ "$REC_LABEL" != "$ME" ]; then
    echo "WARNING: '$REC_LABEL' holds this emulator (pid $TARGET_PID). Stopping it anyway." >&2
    echo "  If that was not intended, they will see a dead bridge with no explanation." >&2
  fi

  echo "killing: $TARGET_PID"
  for sig in TERM KILL; do
    is_alive "$TARGET_PID" || break
    rc=0
    send_sig "$sig" "$TARGET_PID" "$TARGET_START" || rc=$?
    [ "$rc" = 0 ] || exit "$rc"
    for _ in 1 2 3 4 5 6; do is_alive "$TARGET_PID" || break; sleep 0.5; done
  done
  if is_alive "$TARGET_PID"; then
    echo "FAILED to kill: $TARGET_PID" >&2
    echo "(a sandboxed shell may not be allowed to signal it)" >&2
    exit 1
  fi
  emu_remove_record
  echo "melonDS pid $TARGET_PID stopped"
  exit 0
}

# Drop HOLDER only if it still names the exact record this run read.
emu_remove_record() {
  [ "$TARGET_PID" = "$REC_PID" ] || return 0
  [ -f "$HOLDER_FILE" ] || return 0
  if [ "$(sed -n '2p' "$HOLDER_FILE" 2>/dev/null)" = "$REC_PID" ] &&
     [ "$(sed -n '4p' "$HOLDER_FILE" 2>/dev/null)" = "$REC_START" ]; then
    rm -f "$HOLDER_FILE"
  else
    echo "kept HOLDER: it was replaced while stopping pid $TARGET_PID" >&2
  fi
}
