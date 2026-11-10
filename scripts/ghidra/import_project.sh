#!/usr/bin/env bash
# scripts/ghidra/import_project.sh
#
# Reproducible builder for the JUS Ghidra project (Phase G0 of
# docs/design/archive/Ghidra-And-Batch-GDB-Plan.md).
#
# Exit criterion: this script reproducibly builds a Ghidra project containing
# arm9 + all non-stub overlays (same-address overlays included), Thumb-seeded,
# analyzed, and passing all scripted smoke tests.
#
# =============================================================================
# TOPOLOGY DECISION (Step 2): ONE GHIDRA PROGRAM PER BINARY
# =============================================================================
# JUS overlays share RAM addresses: ov00-ov09 all load at 0x0214CD20,
# ov10/ov11 at 0x02172A60, ov12/ov13 at 0x021AC1C0; they are mutually exclusive
# at runtime (the y9 overlay table slots one of them in). We import each binary
# as its OWN Ghidra Program at its RAM base. Addresses never collide because
# each Program lives in its own address space.
#
# (overlay/address) -> program mapping:
#   arm9.bin        @ 0x02000000  -> program "arm9"
#   ov00..ov08.bin  @ 0x0214CD20  -> programs "ov00".."ov08"  (skip ov09, stub)
#   ov10/ov11.bin   @ 0x02172A60  -> programs "ov10","ov11"
#   ov12.bin        @ 0x021AC1C0  -> program "ov12"          (skip ov13, stub)
# Stub overlays (ov09, ov13: 32 bytes, placeholder) are skipped.
#
# NTRGhidra decision: NOT used. NTRGhidra loads the whole ROM with overlays at
# their real addresses, which recreates the SAME-ADDRESS collision (all of
# ov00-ov08 would map onto one address range in one Program). It also has no
# release pinned to Ghidra 12.1.3. The one-Program-per-binary BinaryLoader
# topology sidesteps both. Cross-binary xrefs (e.g. ov6 Thumb blx -> arm9
# 0x020783CC) are resolved in G1's query layer by mapping (overlay,address) to
# the owning program; within G0 we only need each call to decode correctly,
# which the smoke tests verify.
#
# =============================================================================
# VERSION PINNING (Step 1)
# =============================================================================
# This script was written and tested against the pinned trio below. An unpinned
# trio can be mutually incompatible (Ghidra <-> JDK <-> analysis behavior).
#   Ghidra:    12.1.3  (Homebrew formula: Cellar/ghidra/12.1.3/libexec)
#   JDK:       temurin-21.0.12 (mise, pinned in mise.toml: java = "temurin-21")
#   NTRGhidra: NOT INSTALLED / NOT USED (see topology decision)
# The script verifies at run time: analyzeHeadless exists, java reports 21.
# If the machine's Ghidra differs, edit GHIDRA_VERSION and the locate paths below
# together -- do not silently run against an untested combination.
# =============================================================================
#
# Usage:  bash scripts/ghidra/import_project.sh
#
#   Environment overrides:
#     GHIDRA_INSTALL_DIR         Optional. Explicit Ghidra install root. When set,
#                                the script uses <dir>/libexec/support/analyzeHeadless
#                                (Homebrew formula layout) or <dir>/support/analyzeHeadless
#                                (release-zip layout), and fails loudly if neither is
#                                executable instead of silently falling back to
#                                auto-detect. Nothing else is probed when set.
#     GHIDRA_ANALYSIS_TIMEOUT    Analysis timeout per file (default 1800s).
#
# The script is re-runnable (idempotent): each run builds into a fresh temp
# dir, validates, then atomically swaps into scripts/ghidra/project/.
# The project dir is gitignored; the script is the reproducible artifact.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
GHIDRA_DIR="$SCRIPT_DIR"
PROJECT_DIR="$GHIDRA_DIR/project"
SCRIPTS_DIR="$GHIDRA_DIR/scripts"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
FUNCS_JSON="$REPO_ROOT/jus_files/analysis/functions.json"
OVERLAYS_JSON="$REPO_ROOT/jus_files/overlays/overlays.json"
ARM9_MANIFEST="$REPO_ROOT/jus_files/arm9/binaries.json"

# ----------------------------------------------------------------------------
# Version pins + runtime verification (Step 1)
# ----------------------------------------------------------------------------
GHIDRA_VERSION="12.1.3"
JDK_PIN="temurin-21"
ANALYSIS_TIMEOUT_SEC="${GHIDRA_ANALYSIS_TIMEOUT:-1800}"
BUILD_LOG="$GHIDRA_DIR/build.log"

# Locate analyzeHeadless. Check order (first hit wins):
#   0. $GHIDRA_INSTALL_DIR override -- explicit, trumps every auto-detect below.
#      Probes the Homebrew-formula layout then the release-zip layout, and dies
#      with an actionable message if neither is executable (no silent fallback).
#   1. Homebrew Cellar formula (this machine): Cellar/ghidra/<ver>/libexec/support/analyzeHeadless
#   2. Homebrew Caskroom cask:                 Caskroom/ghidra/*/ghidra_*/support/analyzeHeadless
#   3. On PATH (e.g. Linux unzipped release:   ghidra_*/support/analyzeHeadless)
find_analyzeHeadless() {
  # 0. Explicit override.
  if [ -n "${GHIDRA_INSTALL_DIR:-}" ]; then
    for cand in \
      "$GHIDRA_INSTALL_DIR/libexec/support/analyzeHeadless" \
      "$GHIDRA_INSTALL_DIR/support/analyzeHeadless"; do
      [ -x "$cand" ] && { printf '%s\n' "$cand"; return 0; }
    done
    die "GHIDRA_INSTALL_DIR=$GHIDRA_INSTALL_DIR is set but neither '$GHIDRA_INSTALL_DIR/libexec/support/analyzeHeadless' (Homebrew layout) nor '$GHIDRA_INSTALL_DIR/support/analyzeHeadless' (release layout) is executable -- fix GHIDRA_INSTALL_DIR or unset it to allow auto-detect"
  fi
  if [ -x "$HOME/.local/opt/ghidra/libexec/support/analyzeHeadless" ]; then
    printf '%s\n' "$HOME/.local/opt/ghidra/libexec/support/analyzeHeadless"; return 0
  fi
  local cell="$(ls -d /opt/homebrew/Cellar/ghidra/*/libexec/support/analyzeHeadless 2>/dev/null | head -1)"
  [ -n "$cell" ] && [ -x "$cell" ] && { printf '%s\n' "$cell"; return 0; }
  local cask="$(ls /opt/homebrew/Caskroom/ghidra/*/ghidra_*/support/analyzeHeadless 2>/dev/null | head -1)"
  [ -n "$cask" ] && [ -x "$cask" ] && { printf '%s\n' "$cask"; return 0; }
  command -v analyzeHeadless 2>/dev/null && return 0
  return 1
}

die() { echo "ERROR: $*" >&2; exit 1; }

# ----------------------------------------------------------------------------
# Step 0: Preflight
# ----------------------------------------------------------------------------
preflight() {
  echo "[preflight] start"

  # submodule initialized
  if [ ! -f "$REPO_ROOT/jus_files/analysis/functions.json" ]; then
    die "jus_files submodule not initialized (missing analysis/functions.json). Run:  git submodule update --init"
  fi

  # arm9 binary + manifest
  [ -f "$ARM9_MANIFEST" ] || die "missing $ARM9_MANIFEST"
  ARM9_SIZE="$(python3 -c "import json;print(json.load(open('$ARM9_MANIFEST'))['binaries']['arm9']['size'])")"
  ARM9_RAM="$(python3 -c "import json;print(hex(json.load(open('$ARM9_MANIFEST'))['binaries']['arm9']['ram_address']))")"
  [ -f "$REPO_ROOT/jus_files/arm9/arm9.bin" ] || die "missing jus_files/arm9/arm9.bin"
  ACTUAL="$(wc -c < "$REPO_ROOT/jus_files/arm9/arm9.bin" | tr -d '[:space:]')"
  [ "$ACTUAL" = "$ARM9_SIZE" ] || die "arm9.bin size mismatch: expected $ARM9_SIZE got $ACTUAL"

  # overlay manifest
  [ -f "$OVERLAYS_JSON" ] || die "missing $OVERLAYS_JSON"
  python3 -c "import json; d=json.load(open('$OVERLAYS_JSON')); assert len(d)>=14, 'y9 table short'" \
    || die "y9 overlay table unreadable"

  # every overlay binary present with expected size
  python3 - "$REPO_ROOT/jus_files/overlays" "$OVERLAYS_JSON" <<'PY' || die "overlay preflight failed"
import json, os, sys
d = json.load(open(sys.argv[2]))
for o in d:
    p = os.path.join(sys.argv[1], o['file'])
    if not os.path.isfile(p):
        print(f"missing {o['file']}"); sys.exit(1)
    if os.path.getsize(p) != o['file_bytes']:
        print(f"{o['file']} size mismatch: expected {o['file_bytes']} got {os.path.getsize(p)}"); sys.exit(1)
PY

  # output dir writable
  mkdir -p "$PROJECT_DIR"
  [ -w "$PROJECT_DIR" ] || die "project dir not writable: $PROJECT_DIR"

  # functions.json readable + sane shape
  python3 -c "import json;d=json.load(open('$FUNCS_JSON'));assert 'functions' in d and len(d['functions'])>1000" \
    || die "functions.json unreadable or wrong shape"

  # runtime version verification (Step 1)
  AH="$(find_analyzeHeadless)" || die "analyzeHeadless not found (is Ghidra installed?)"
  echo "[preflight] analyzeHeadless: $AH"
  case "$AH" in
    *"$GHIDRA_VERSION"*) echo "[preflight] Ghidra version OK (pin $GHIDRA_VERSION)" ;;
    *)
      # report the actual version from application.properties if we can
      local props="${AH%/support/analyzeHeadless}/Ghidra/application.properties"
      local ver="?"
      [ -f "$props" ] && ver="$(sed -n 's/^application.version=//p' "$props" | head -1)"
      die "Ghidra version mismatch: found '$ver' at $AH, expected '$GHIDRA_VERSION' (edit GHIDRA_VERSION + locate paths together)"
      ;;
  esac

  if ! command -v java >/dev/null 2>&1 && [ -z "${JAVA_HOME:-}" ]; then
    die "no java on PATH and JAVA_HOME unset. Run:  mise install  (mise.toml pins $JDK_PIN)"
  fi
  local jver="$(java -version 2>&1 | head -1)"
  echo "[preflight] java: $jver (pin $JDK_PIN)"
  case "$jver" in
    *'"21.'*) echo "[preflight] JDK 21 OK" ;;
    *) die "JDK is not 21 (got: $jver). Run:  mise install" ;;
  esac

  echo "$AH" > "$GHIDRA_DIR/.analyzeHeadless.path"
  echo "[preflight] done"
}

# ----------------------------------------------------------------------------
# Per-binary import: seed (noanalysis) then analyze.  Appends into $PROJ/$PROJNAME.
# ----------------------------------------------------------------------------
import_one() {
  local name="$1" bin="$2" base="$3" prov="$4"
  # Provenance key (4th arg) is the functions.json `provenance` field (e.g. "ov6",
  # "arm9" -- no ".bin" extension), distinct by design from the stored program
  # basename that -process matches (e.g. "ov06.bin"). SeedThumb filters functions.json
  # by this provenance; -process selects the program by its import basename.
  # Ghidra stores each program under the basename of the imported file
  # (e.g. "arm9.bin", "ov06.bin"). -process matches that stored name.
  local prog="$(basename "$bin")"
  echo "[import] $name ($prog) @ $base (provenance $prov)"

  # Each analyzeHeadless invocation writes to its OWN temp log, which we then
  # append to the shared $BUILD_LOG. Greps (seed assertion, timeout markers) are
  # scoped to the invocation's tmp log, so a marker can never be mis-attributed
  # to another binary. Mind set -euo pipefail: grep/exit-1-on-no-match must be
  # guarded (the assertion's python exits non-zero via `|| seed_rc=$?`).

  # Pass 1: import with NO analysis, then seed functions+TMode as postScript.
  # Seeding must happen before any disassembly or the TMode set conflicts with
  # instructions Ghidra already made ARM.
  local seed_args=("$prov" "$FUNCS_JSON")
  [ -n "$ENTRY" ] && seed_args+=("$ENTRY")
  local tmp_log="$(mktemp)"
  "$AH" "$PROJ" "$PROJNAME" \
    -import "$bin" \
    -processor ARM:LE:32:v5t \
    -loader BinaryLoader \
    -loader-baseAddr "$base" \
    -noanalysis \
    -scriptPath "$SCRIPTS_DIR" \
    -postScript SeedThumb.java "${seed_args[@]}" \
    >> "$tmp_log" 2>&1 || {
      cat "$tmp_log" >> "$BUILD_LOG"; rm -f "$tmp_log"
      die "import+seed failed for $name (see $BUILD_LOG)"
    }
  # Seed assertion for THIS invocation: no SEED_FAIL, and a SEED_DONE line whose
  # prov= matches this binary's provenance with created>=1. A functions.json that
  # is present-but-wrong-shaped (or a partial seeding regression) ships today
  # because the script returns normally in both cases -- structurally assert it.
  if grep -q "SEED_FAIL" "$tmp_log"; then
    cat "$tmp_log" >> "$BUILD_LOG"; rm -f "$tmp_log"
    die "seeding degraded for $name: SEED_FAIL in seed output (see $BUILD_LOG)"
  fi
  seed_rc=0
  python3 - "$tmp_log" "$prov" <<'PY' || seed_rc=$?
import re, sys
log = open(sys.argv[1]).read()
prov = sys.argv[2]
for line in log.splitlines():
    m = re.search(r'SEED_DONE created=(\d+)', line)
    if m and ('prov=' + prov) in line:
        sys.exit(0 if int(m.group(1)) >= 1 else 2)
sys.exit(3)
PY
  if [ "$seed_rc" -ne 0 ]; then
    cat "$tmp_log" >> "$BUILD_LOG"; rm -f "$tmp_log"
    die "seeding degraded for $name: no SEED_DONE created>=1 prov=$prov (rc=$seed_rc, see $BUILD_LOG)"
  fi
  cat "$tmp_log" >> "$BUILD_LOG"
  rm -f "$tmp_log"

  # Pass 2: full analysis with a per-file timeout. analyzeHeadless exits 0 even
  # on analysis timeout, so we grep the log for the timeout marker AND the
  # postScript's own completion marker.
  local tmp_log="$(mktemp)"
  "$AH" "$PROJ" "$PROJNAME" \
    -process "$prog" \
    -analysisTimeoutPerFile "$ANALYSIS_TIMEOUT_SEC" \
    -scriptPath "$SCRIPTS_DIR" \
    -postScript SmokeTest.java timeout \
    >> "$tmp_log" 2>&1 || {
      cat "$tmp_log" >> "$BUILD_LOG"; rm -f "$tmp_log"
      die "analysis failed for $name (see $BUILD_LOG)"
    }

  # Fail the build on analyzer timeout -- never ship a half-analyzed project.
  if grep -q "SMOKE_TIMEOUT_FAIL" "$tmp_log"; then
    cat "$tmp_log" >> "$BUILD_LOG"; rm -f "$tmp_log"
    die "analysis of $name timed out (timeout $ANALYSIS_TIMEOUT_SEC) -- not shipping a half-analyzed project"
  fi
  if grep -q "Analysis timed out at" "$tmp_log"; then
    cat "$tmp_log" >> "$BUILD_LOG"; rm -f "$tmp_log"
    die "analyzeHeadless reported analysis timeout for $name (see $BUILD_LOG)"
  fi
  cat "$tmp_log" >> "$BUILD_LOG"
  rm -f "$tmp_log"
}

# ----------------------------------------------------------------------------
# Smoke tests (Step 4) -- scripted, grep-checked, fail the build on any FAIL.
# ----------------------------------------------------------------------------
smoke_one() {
  local prog="$1"; shift
  # $@ = remaining args for SmokeTest.java
  echo "[smoke] $prog $*"
  # Per-invocation tmp log (same pattern as import_one) so the FAIL/timeout
  # greps in smoke_all are scoped to this call, not the whole build.log.
  local tmp_log="$(mktemp)"
  "$AH" "$PROJ" "$PROJNAME" \
    -process "$prog" \
    -noanalysis \
    -scriptPath "$SCRIPTS_DIR" \
    -postScript SmokeTest.java "$@" \
    >> "$tmp_log" 2>&1 || {
      cat "$tmp_log" >> "$BUILD_LOG"; rm -f "$tmp_log"
      die "smoke test invocation failed for $prog (see $BUILD_LOG)"
    }
  cat "$tmp_log" >> "$BUILD_LOG"
  rm -f "$tmp_log"
}

smoke_all() {
  echo "[smoke] decompile arm9.bin 0x02078488 (ApplyDeltaToCurrent clamped add)"
  smoke_one arm9.bin decompile 0x02078488
  echo "[smoke] ov06.bin Thumb blx 0x02150DD8 -> 0x020783CC"
  smoke_one ov06.bin thumb 0x02150DD8 0x020783CC
  echo "[smoke] ov05.bin ARM bl 0x02156C70 -> 0x02078CB8"
  smoke_one ov05.bin armbl 0x02156C70 0x02078CB8

  # Same-address distinct-bytes test: ov5 and ov6 both base 0x0214CD20. Each
  # must hold its OWN bytes. Check the first 32 bytes (differ between the two)
  # and a deeper region (0x021700E0): ov5 holds ASCII there, ov6 holds code.
  # Also the byte just past ov5's end (0x02172280) exists in ov6 (0x49) and
  # would be OOB in ov5 -- proves per-program independence of the shared range.
  echo "[smoke] ov05.bin vs ov06.bin same-address distinct bytes"
  smoke_one ov05.bin range 0x0214CD20 0x0214CD40 78402de904d04de20150a0e10060a0e188109fe588209fe56000a0e31e30a0e3
  smoke_one ov06.bin range 0x0214CD20 0x0214CD40 f8b5aab0041c0020059009900490c248407a002802d0099826f7a0ec26f72eed
  smoke_one ov05.bin range 0x021700E0 0x02170100 6465636b6d616b652f6465636b6d616b652e6161720000006465636b6d616b65
  smoke_one ov06.bin range 0x021700E0 0x02170100 0030a0e3340086e5080094e50610a0e1380086e5080096e50120a0e3fe01d0e1
  smoke_one ov06.bin range 0x02172280 0x02172290 496e666f506f70756c61725365740000

  # Any SMOKE_*_FAIL marker (excluding the informational *_FAIL_CASCADE lines that
  # only annotate an already-reported timeout) fails the build.
  if grep -qE "SMOKE_[A-Z_]+_FAIL( |$)" "$BUILD_LOG"; then
    grep -E "SMOKE_[A-Z_]+_FAIL" "$BUILD_LOG" | tail -20
    die "smoke tests FAILED (see $BUILD_LOG)"
  fi
  echo "[smoke] all smoke tests passed"
}

# ----------------------------------------------------------------------------
# Atomic swap into project/ (never mutate last known-good in place)
# ----------------------------------------------------------------------------
swap_in() {
  local new="$1" stamp="$(date +%Y%m%d%H%M%S)"
  echo "[swap] installing $new -> $PROJECT_DIR"
  if [ -d "$PROJECT_DIR" ]; then
    local old="$GHIDRA_DIR/project.old.$stamp"
    mv "$PROJECT_DIR" "$old"
    echo "[swap] previous project preserved at $old (delete manually once satisfied)"
  fi
  mv "$new" "$PROJECT_DIR"
  echo "[swap] done"
}

# ----------------------------------------------------------------------------
main() {
  preflight
  AH="$(cat "$GHIDRA_DIR/.analyzeHeadless.path")"

  PROJ="$(mktemp -d "${TMPDIR:-/tmp}/ghidra-jus.XXXXXX")"
  PROJNAME="JUS"
  echo "[build] fresh project dir: $PROJ (name $PROJNAME)"
  : > "$BUILD_LOG"

  # import arm9 (explicit ARM entry 0x02005080 = 0x02000000 + 20480)
  ENTRY="0x02005080"
  import_one arm9 "$REPO_ROOT/jus_files/arm9/arm9.bin" "$ARM9_RAM" arm9
  ENTRY=""

  # import overlays: all non-stub (skip ov09, ov13 which are 32-byte stubs)
  python3 - "$OVERLAYS_JSON" "$REPO_ROOT/jus_files/overlays" <<'PY' > "$GHIDRA_DIR/.overlay_imports"
import json, sys
d = json.load(open(sys.argv[1]))
out = []
for o in d:
    if o['ram_size'] <= 32:      # stub overlay (ov09, ov13)
        continue
    out.append((o['file'].replace('.bin',''), o['file'], hex(o['ram_address']),
                'ov' + str(o['id'])))
for row in sorted(out, key=lambda r: r[0]):
    print('\t'.join(row))
PY
  while IFS=$'\t' read -r name bin base prov; do
    import_one "$name" "$REPO_ROOT/jus_files/overlays/$bin" "$base" "$prov"
  done < "$GHIDRA_DIR/.overlay_imports"

  # smoke tests
  smoke_all

  # validate then swap
  echo "[build] all imports + seeds + analysis + smoke tests passed"
  swap_in "$PROJ"
  rm -f "$GHIDRA_DIR/.overlay_imports" "$GHIDRA_DIR/.analyzeHeadless.path"
  echo "[build] OK -- project at $PROJECT_DIR (contains: arm9 + ov00..ov08, ov10, ov11, ov12)"
}

main "$@"
