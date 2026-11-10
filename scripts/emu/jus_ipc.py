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

Ownership (P1.8b): every mutation the client makes (directory setup and
stale-epoch cleanup in __init__, next_id, publish_command, ack consumption
in wait_ack, request_stop) runs inside `with self.guard():`. A leased runner
passes `guard=Owned(lease).section` (owned.py: the lease lock plus
assert_current), so a fenced runner raises instead of writing. wait_ack
polls read-only and removes only its own ack and a pending.json whose id
is its own; a foreign ack is left alone.
"""
import contextlib, enum, json, os, time
from pathlib import Path

from jus_plan import lua_literal

HEARTBEAT_STALE_S = 5.0
DEFAULT_DIR = os.environ.get("JUS_EMU_DIR", "/tmp/jus_emu")


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


def _write_atomic(path, content):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(content)
    os.replace(tmp, path)


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

    def request_stop(self):
        with self.guard():
            _write_atomic(os.path.join(self.dir, "stop.flag"), "stop")
