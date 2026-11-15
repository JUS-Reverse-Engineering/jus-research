"""File-based IPC with agent_bridge.lua running inside melonDS.

Layout under the IPC dir (default /tmp/jus_emu):
  heartbeat.json      bridge-owned; {session, framecount, wallclock, state}
  cmd/inbox.lua       client-owned; one pending command as a Lua literal
  cmd/pending.json    client-owned; {id, epoch} survives inbox consumption
  cmd/next_id         client-owned; persistent id counter
  ack/<id>.json       bridge-owned; {id, epoch, ok, result|error}
  stop.flag           client-owned sentinel; bridge aborts active plan
  runs/, states/      run artifacts and savestates

Commands are Lua literals (bridge needs no JSON parser); acks and
heartbeats are JSON from the bridge's canonical encoder. Delivery is
at-most-once: on timeout a command's fate is unknown; check status
before reissuing (spec §3). Single client per IPC dir by design.

Ownership: every mutation the client makes (directory setup and
stale-epoch cleanup in __init__, next_id, publish_command, ack consumption
in wait_ack, request_stop) runs inside `with self.guard():`. A leased runner
passes `guard=Owned(lease).section` (owned.py: the lease lock plus
assert_current), so a fenced runner raises instead of writing. wait_ack
polls read-only and removes only its own ack and a pending.json whose id
is its own; a foreign ack is left alone.

Resident client: `resident()` returns one long-lived IpcClient per IPC dir, and `batch()` / `state_load()` /
`call()` are the library entry points (the pattern l77m_fast.py started). A long-lived client re-reads the heartbeat
session before each call, so a bridge restart does not leave it sending a stale epoch. `batch` is ONE command, one id,
one ack: the bridge runs the steps in one callback and the ack's result is {results, completed, failed_index}. It is
not frame-atomic (the Lua callback runs on the GUI thread while the core free-runs); it saves the per-verb poll wait.
`state_load` failures carry an `inspection` + `hint` (inspect_state_load); bridge timing and the settle rule are unchanged.
"""
import contextlib, enum, gzip, hashlib, json, os, re, struct, time, zlib
from pathlib import Path

from jus_plan import lua_literal

HEARTBEAT_STALE_S = 5.0
DEFAULT_DIR = os.environ.get("JUS_EMU_DIR", "/tmp/jus_emu")
# Keep these two in step with bridge_core.lua (M.BATCH_MAX / M.BATCH_REFUSED); test_jus_batch checks they agree.
BATCH_MAX = 64
BATCH_REFUSED = ("batch", "run_plan", "state_load", "state_save")


class BridgeState(enum.Enum):
    IDLE = "idle"
    PLAN_RUNNING = "plan_running"
    LOADING_STATE = "loading_state"
    SAVING_STATE = "saving_state"
    FLUSHING = "flushing"
    PAUSED = "paused"   # heartbeat stale, emulator process alive (GDB stop?)
    DEAD = "dead"


_LIVE = {s.value: s for s in (BridgeState.IDLE, BridgeState.PLAN_RUNNING,
                              BridgeState.LOADING_STATE,
                              BridgeState.SAVING_STATE, BridgeState.FLUSHING)}


def emulator_process_alive(ipc_dir=None):
    """Check process names and optional launch PID records, never command arguments.

    An unavailable /proc or an unreadable/malformed PID record means alive.
    A reused PID also keeps the check closed, even for an unrelated process.
    """
    try:
        processes = os.listdir('/proc')
    except OSError:
        return True
    for pid in processes:
        if not pid.isdigit():
            continue
        proc = Path('/proc') / pid
        try:
            comm = (proc / 'comm').read_text().strip().lower()
        except OSError:
            comm = ''
        try:
            exe = os.path.basename(os.readlink(proc / 'exe')).lower()
        except OSError:
            exe = ''
        if 'melonds' in comm or 'melonds' in exe:
            return True
    if ipc_dir is not None:
        for filename, line in (('emu.pid', 0), ('HOLDER', 1)):
            try:
                record = (Path(ipc_dir) / filename).read_text().splitlines()
            except FileNotFoundError:
                continue
            except (OSError, UnicodeError):
                return True
            try:
                pid = int(record[line].strip())
            except (IndexError, ValueError):
                return True
            if pid <= 0 or os.path.exists(f'/proc/{pid}'):
                return True
    return False


def interpret_heartbeat(hb, emulator_alive):
    if time.time() - hb["wallclock"] > HEARTBEAT_STALE_S:
        return BridgeState.PAUSED if emulator_alive else BridgeState.DEAD
    return _LIVE.get(hb["state"], BridgeState.DEAD)


def read_heartbeat(ipc_dir):
    """The bridge heartbeat as a dict, or None. Read-only: no directories made, nothing cleaned."""
    try:
        with open(os.path.join(ipc_dir, "heartbeat.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def validate_batch_steps(steps):
    """Normalise `[{op, args?}, ...]` for the bridge's batch op, refusing what the bridge would. Raises ValueError."""
    if not isinstance(steps, list):
        raise ValueError("batch steps must be a list of {op, args} objects")
    if len(steps) > BATCH_MAX:
        raise ValueError("batch has %d steps; the limit is %d" % (len(steps), BATCH_MAX))
    out = []
    for i, st in enumerate(steps):
        if not isinstance(st, dict) or not isinstance(st.get("op"), str) or not st["op"]:
            raise ValueError("step %d: needs a string \"op\"" % i)
        if st["op"] in BATCH_REFUSED:
            raise ValueError("step %d (%s): not allowed in a batch (multi-callback state machine or nested batch; "
                             "run it as its own command)" % (i, st["op"]))
        args = st.get("args", {})
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise ValueError("step %d (%s): args must be an object" % (i, st["op"]))
        out.append({"op": st["op"], "args": args})
    return out


def _write_atomic(path, content):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(content)
    os.replace(tmp, path)


AUTO = object()   # "resolve it yourself" (None means "skip it")


class IpcClient:
    def __init__(self, ipc_dir=DEFAULT_DIR, guard=None):
        self.dir = ipc_dir
        self.guard = guard or contextlib.nullcontext
        self.epoch = None
        with self.guard():
            for sub in ("cmd", "ack", "runs", "states"):
                os.makedirs(os.path.join(self.dir, sub), exist_ok=True)
            hb = self._read_heartbeat()
            if hb is not None:
                self.epoch = hb["session"]
                self._clean_stale_epoch_files()

    # -- heartbeat / status --------------------------------------------
    def _read_heartbeat(self):
        try:
            with open(os.path.join(self.dir, "heartbeat.json")) as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def state(self):
        hb = self._read_heartbeat()
        if hb is None:
            return BridgeState.DEAD, None
        return interpret_heartbeat(hb, emulator_process_alive(self.dir)), hb

    # -- epoch hygiene --------------------------------------------------
    def _clean_stale_epoch_files(self):
        pend = os.path.join(self.dir, "cmd", "pending.json")
        try:
            with open(pend) as f:
                if json.load(f).get("epoch") != self.epoch:
                    os.remove(pend)
                    inbox = os.path.join(self.dir, "cmd", "inbox.lua")
                    if os.path.exists(inbox):
                        os.remove(inbox)
        except (OSError, ValueError):
            pass
        ackdir = os.path.join(self.dir, "ack")
        for name in os.listdir(ackdir):
            path = os.path.join(ackdir, name)
            try:
                with open(path) as f:
                    if json.load(f).get("epoch") != self.epoch:
                        os.remove(path)
            except (OSError, ValueError):
                try:
                    os.remove(path)
                except OSError:
                    pass

    # -- command ids ------------------------------------------------------
    def next_id(self):
        with self.guard():
            return self._next_id()

    def _next_id(self):
        path = os.path.join(self.dir, "cmd", "next_id")
        try:
            with open(path) as f:
                n = int(f.read().strip())
        except (OSError, ValueError):
            n = 0
        n += 1
        _write_atomic(path, str(n))
        return n

    # -- publish / wait ---------------------------------------------------
    def publish_command(self, op, args, cmd_id=None):
        if self.epoch is None:
            raise RuntimeError("no bridge heartbeat — is agent_bridge.lua "
                               "loaded? (`jusemu status` for details)")
        pend = os.path.join(self.dir, "cmd", "pending.json")
        with self.guard():
            if os.path.exists(pend):
                raise RuntimeError(
                    "a command is pending (unacked); check `jusemu status`, "
                    "then remove %s if it is stale" % pend)
            cid = cmd_id if cmd_id is not None else self._next_id()
            body = "return " + lua_literal(
                {"epoch": self.epoch, "id": cid, "op": op, "args": args})
            _write_atomic(pend, json.dumps({"id": cid, "epoch": self.epoch}))
            _write_atomic(os.path.join(self.dir, "cmd", "inbox.lua"), body)
        return cid

    def wait_ack(self, cid, timeout=10.0):
        ack_path = os.path.join(self.dir, "ack", "%d.json" % cid)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if os.path.exists(ack_path):
                with open(ack_path) as f:
                    ack = json.load(f)
                if ack.get("epoch") == self.epoch and ack.get("id") == cid:
                    with self.guard():
                        os.remove(ack_path)
                        self._clear_pending(cid)
                    return ack
                # stale/foreign ack: not ours to delete (a new client's
                # __init__ cleans foreign epochs); keep waiting
            time.sleep(0.05)
        raise TimeoutError(
            "no ack for command %d after %.1fs — INDETERMINATE: the bridge "
            "may or may not have executed it. Check `jusemu status`." %
            (cid, timeout))

    def _clear_pending(self, cid):
        """Remove cmd/pending.json only if it marks command `cid` of this
        epoch. Caller holds the guard."""
        pend = os.path.join(self.dir, "cmd", "pending.json")
        try:
            with open(pend) as f:
                mark = json.load(f)
        except (OSError, ValueError):
            return False
        if mark.get("id") != cid or mark.get("epoch") != self.epoch:
            return False
        os.remove(pend)
        return True

    def abandon(self, cid):
        """Give up on unacked command `cid`: remove its pending.json and,
        with it, inbox.lua (both only if the marker is still cid's). The
        bridge may be consuming it right now: at-most-once, fate unknown."""
        with self.guard():
            if self._clear_pending(cid):
                inbox = os.path.join(self.dir, "cmd", "inbox.lua")
                if os.path.exists(inbox):
                    os.remove(inbox)
                return True
        return False

    # -- resident-client entry points ------------------------------------
    def sync_epoch(self):
        """Adopt the bridge's current session if it changed since this client was built (bridge restart), cleaning the
        old epoch's leftovers exactly as __init__ does. A no-op while the session is unchanged."""
        hb = self._read_heartbeat()
        if hb is None or hb.get("session") == self.epoch:
            return self.epoch
        with self.guard():
            self.epoch = hb["session"]
            self._clean_stale_epoch_files()
        return self.epoch

    def call(self, op, args=None, timeout=15.0):
        """Publish one command and wait for its ack. At-most-once: no retry; on TimeoutError the fate is unknown and
        the pending marker stays (a second call raises until `abandon`)."""
        self.sync_epoch()
        cid = self.publish_command(op, args or {})
        return self.wait_ack(cid, timeout=timeout)

    def batch(self, steps, timeout=15.0):
        """Run `[{op, args}, ...]` as ONE bridge command. Returns the ack: ok with result.results on success; on a step
        failure ok is False, `error` names the step, and result.results/completed/failed_index keep what ran."""
        return self.call("batch", {"steps": validate_batch_steps(steps)}, timeout)

    def state_load(self, slot, timeout=30.0, keep_neutral=False, archive_dir=AUTO, hashes=None):
        """`state_load`, with an `inspection` and `hint` attached to a failed ack (a settle timeout acks ok=False) and to a
        TimeoutError (`.inspection`, `.hint`). A successful ack is returned untouched."""
        args = {"slot": slot}
        if keep_neutral:
            args["keep_neutral"] = True
        try:
            ack = self.call("state_load", args, timeout)
        except TimeoutError as e:
            e.inspection = _safe_inspect(self.dir, slot, archive_dir, hashes, True)
            e.hint = e.inspection.get("hint")
            raise
        if not ack.get("ok"):
            ack["inspection"] = _safe_inspect(self.dir, slot, archive_dir, hashes, "settle" in str(ack.get("error", "")))
            ack["hint"] = ack["inspection"].get("hint")
        return ack

    def request_stop(self):
        with self.guard():
            _write_atomic(os.path.join(self.dir, "stop.flag"), "stop")


# -- resident client ----------------------------------------------------------
_RESIDENT = {}


def resident(ipc_dir=None, guard=None):
    """The one long-lived IpcClient for `ipc_dir` (default JUS_EMU_DIR), made on first use. `guard` applies only when the
    client is created. Reuse it across calls instead of spawning a `jusemu.py` process per verb."""
    key = os.path.abspath(ipc_dir or DEFAULT_DIR)
    if key not in _RESIDENT:
        _RESIDENT[key] = IpcClient(key, guard=guard)
    return _RESIDENT[key]


def batch(steps, ipc_dir=None, timeout=15.0):
    return resident(ipc_dir).batch(steps, timeout)


def state_load(slot, ipc_dir=None, timeout=30.0, **kw):
    return resident(ipc_dir).state_load(slot, timeout, **kw)


# -- inspected load errors ------------------------------------------------------
HERE = Path(__file__).resolve().parent
SETTLE_PROBE = "0x02181B28"   # README: confirm a load with the framecount and [0x02181B28], never with the ack alone


def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def default_hashes():
    try:
        with open(HERE / "hashes.json") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def rom_info(hashes=None):
    """The ROM the build records (hashes.json) against the file on disk. `actual_sha256` is None when the file is absent."""
    hashes = default_hashes() if hashes is None else hashes
    path = hashes.get("rom_path")
    info = {"path": path, "recorded_sha256": hashes.get("rom_sha256"), "actual_sha256": None, "match": None}
    if path and os.path.isfile(os.path.expanduser(path)):
        info["actual_sha256"] = _sha256_file(os.path.expanduser(path))
        info["match"] = info["actual_sha256"] == info["recorded_sha256"]
    return info


def default_archive_dir():
    """The savestate archive (jus_files/save_states), or None when it cannot be resolved (submodule absent, no repo)."""
    try:
        import build_state   # lazy: only a failed load needs the archive
        d = build_state.store_dir()
        return d if Path(d).is_dir() else None
    except Exception:
        return None


def _mln_info(path):
    """Header facts for a .mln savestate: present, size, gzip, and the version at header offset 4.
    The header layout was checked against a synthetic file only."""
    info = {"path": str(path), "present": path.is_file()}
    if not info["present"]:
        return info, None
    blob = path.read_bytes()
    info["bytes"] = len(blob)
    info["gzipped"] = blob[:2] == b"\x1f\x8b"
    raw = blob
    if info["gzipped"]:
        try:
            raw = gzip.decompress(blob)
        except (OSError, EOFError, zlib.error) as e:
            info.update(header_ok=False, error="gzip stream unreadable: %s" % e)
            return info, None
    info["raw_bytes"] = len(raw)
    info["raw_sha256"] = hashlib.sha256(raw).hexdigest()
    info["magic"] = raw[:4].decode("ascii", "replace")
    if raw[:4] != b"MELN":
        info["header_ok"] = False
        return info, raw
    info["header_ok"] = True
    major, minor = struct.unpack_from("<HH", raw, 4)
    info["version"] = "%d.%d" % (major, minor)
    sections, off = [], 0x10
    while off + 16 <= len(raw) and len(sections) < 64:
        length = struct.unpack_from("<I", raw, off + 4)[0]
        sections.append(raw[off:off + 4].decode("ascii", "replace"))
        if length < 16:
            break
        off += length
    info["sections"] = sections
    return info, raw


def _sidecar_info(path):
    info = {"path": str(path), "present": path.is_file()}
    if not info["present"]:
        return info
    text = path.read_text(errors="replace")
    info["json_ok"] = True
    fc = None
    try:
        fc = json.loads(text).get("framecount_at_save")
    except (ValueError, AttributeError):
        info["json_ok"] = False
    m = re.search(r'"framecount_at_save":(\d+)', text)   # the bridge's own reader (agent_bridge.lua read_sidecar)
    info["bridge_regex_ok"] = m is not None
    info["framecount_at_save"] = int(m.group(1)) if m else fc
    return info


def inspect_state_load(ipc_dir, slot, *, archive_dir=AUTO, hashes=None, last_framecount=None, settle_timeout=False):
    """Read-only facts about a `state_load` that failed or did not settle, plus a `hint`. Never raises on bad files.

    Keys: slot, mln{present, header_ok, magic, version, gzipped, sections, raw_sha256}, sidecar{present, json_ok,
    bridge_regex_ok, framecount_at_save}, archive{listed, expected, actual, match}, rom{recorded_sha256,
    actual_sha256, match}, last_framecount (from the heartbeat unless given), hint.
    """
    out = {"slot": slot}
    if not slot or os.path.basename(slot) != slot or slot in (".", ".."):
        out.update(error="slot is not a plain name", hint="slot %r is not a plain state name" % slot)
        return out
    states = Path(ipc_dir) / "states"
    out["mln"], raw = _mln_info(states / (slot + ".mln"))
    out["sidecar"] = _sidecar_info(states / (slot + ".meta.json"))
    if archive_dir is AUTO:
        archive_dir = default_archive_dir()
    out["archive"] = {"dir": str(archive_dir) if archive_dir else None, "listed": False}
    if archive_dir and raw is not None:
        try:
            meta = json.loads((Path(archive_dir) / (slot + ".meta.json")).read_text())
        except (OSError, ValueError):
            meta = {}
        if meta.get("sha256"):
            out["archive"].update(listed=True, expected=meta["sha256"], actual=out["mln"]["raw_sha256"],
                                  match=meta["sha256"] == out["mln"]["raw_sha256"])
    out["rom"] = rom_info(hashes)
    if last_framecount is None:
        hb = read_heartbeat(ipc_dir)
        last_framecount = hb.get("framecount") if hb else None
    out["last_framecount"] = last_framecount
    out["hint"] = _load_hint(out, settle_timeout)
    return out


def _load_hint(i, settle_timeout):
    mln, side, arch, rom = i["mln"], i["sidecar"], i["archive"], i["rom"]
    if not mln["present"]:
        return "no .mln for this slot in the IPC states/ dir: copy it there (state load reads <ipc>/states/<slot>.mln)"
    if not mln.get("header_ok"):
        return "the .mln is not a melonDS savestate (%s): truncated copy or the wrong file" % (
            mln.get("error") or "magic %r, expected 'MELN'" % mln.get("magic"))
    notes = []
    if arch.get("listed") and arch["match"] is False:
        notes.append("the .mln differs from the archive's recorded sha256: a modified or different copy")
    if rom["match"] is False:
        notes.append("the ROM on disk differs from hashes.json's rom_sha256: states are tied to the ROM that made them")
    if not side["present"]:
        notes.append("no sidecar (<slot>.meta.json): the bridge refuses a state with none (pre-protocol savestate)")
    elif not side["bridge_regex_ok"]:
        notes.append("the sidecar has no framecount_at_save the bridge can read: it must be compact JSON, "
                     "'\"framecount_at_save\":N' with no space after the colon (json.dump defaults break it)")
    elif side["framecount_at_save"] == 0:
        notes.append("the sidecar's framecount_at_save is 0, a dummy: such a load always acks 'did not settle' even when "
                     "it worked. Read framecount and [%s] to tell" % SETTLE_PROBE)
    elif settle_timeout:
        notes.append("the framecount never reached framecount_at_save=%s: either the load really failed or the sidecar "
                     "is wrong. Read framecount and [%s] to tell" % (side["framecount_at_save"], SETTLE_PROBE))
    if not notes:
        notes.append("the files look consistent; if the ack said it did not settle, read framecount and [%s] "
                     "before treating the load as failed" % SETTLE_PROBE)
    return "; ".join(notes)


def _safe_inspect(ipc_dir, slot, archive_dir, hashes, settle_timeout):
    try:
        return inspect_state_load(ipc_dir, slot, archive_dir=archive_dir, hashes=hashes, settle_timeout=settle_timeout)
    except Exception as e:   # diagnostics must never mask the load result
        return {"slot": slot, "error": "inspection failed: %s: %s" % (type(e).__name__, e),
                "hint": "inspection failed; read framecount and [%s]" % SETTLE_PROBE}
