#!/usr/bin/env bash
# scripts/emu/restore_states.sh
# Unpack the committed bridge savestates (jus_files/save_states/<slot>.mln.gz
# + <slot>.meta.json) into the IPC states dir, where `jusemu.py state load
# <slot>` finds them. /tmp is tmpfs on Linux, so run this after every reboot.
#
# Usage: bash scripts/emu/restore_states.sh [--force]
#   --force   overwrite slots that already exist (default: keep them, since a
#             local slot may be a newer re-save of the same name)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="$SCRIPT_DIR/../../jus_files/save_states"
DEST="${JUS_EMU_DIR:-/tmp/jus_emu}/states"
FORCE=0
[ "${1:-}" = --force ] && FORCE=1

[ -d "$SRC" ] || { echo "no $SRC (git submodule update --init jus_files)" >&2; exit 1; }
mkdir -p "$DEST"

restored=0; kept=0
for gz in "$SRC"/*.mln.gz; do
  slot="$(basename "$gz" .mln.gz)"
  meta="$SRC/$slot.meta.json"
  [ -f "$meta" ] || { echo "skip $slot: no meta.json sidecar" >&2; continue; }
  if [ "$FORCE" = 0 ] && [ -f "$DEST/$slot.mln" ]; then kept=$((kept+1)); continue; fi
  gzip -dc "$gz" > "$DEST/$slot.mln.tmp" && mv "$DEST/$slot.mln.tmp" "$DEST/$slot.mln"
  cp "$meta" "$DEST/$slot.meta.json"
  restored=$((restored+1))
done
echo "restored $restored slot(s), kept $kept existing, into $DEST"
