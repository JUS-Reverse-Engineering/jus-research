#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

touch "$TMP_DIR/jus.nds"
printf 'same-session\n%s\nnow\n' "$$" > "$TMP_DIR/HOLDER"

set +e
OUTPUT="$(
  JUS_EMU_DIR="$TMP_DIR" \
  JUS_EMU_HOLDER="same-session" \
  MELONDS=/usr/bin/true \
  ROM="$TMP_DIR/jus.nds" \
  bash "$ROOT/scripts/emu/launch_emu.sh" --force 2>&1
)"
STATUS=$?
set -e

if [[ "$STATUS" -ne 3 ]]; then
  echo "launch must refuse every live HOLDER, including the same label and --force; got $STATUS" >&2
  echo "$OUTPUT" >&2
  exit 1
fi
if [[ "$OUTPUT" != *"REFUSING TO LAUNCH"* ]]; then
  echo "launch refusal must identify the live HOLDER conflict" >&2
  exit 1
fi

echo "live HOLDER cannot be bypassed"
