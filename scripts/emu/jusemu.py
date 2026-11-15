"""Claude-facing CLI for driving melonDS via agent_bridge.lua.

Usage examples:
  python3 jusemu.py status
  python3 jusemu.py selftest
  python3 jusemu.py peek 0x021DF1D4 2   # current HP, u16, displayed = raw/64
  python3 jusemu.py peek 0x78 2 --chain player
  python3 jusemu.py peek 0x021DEB3C 4 --state path/to/luffy_training.mln.gz   # offline: a savestate file, no emulator
  python3 jusemu.py state save training
  python3 jusemu.py run plans/example_walk_and_b.json
  python3 jusemu.py screenshot /tmp/shot.png
  python3 jusemu.py batch steps.json    # [{"op": "poke", "args": {...}}, {"op": "peek", ...}] (or - for stdin): one command
  python3 jusemu.py info                # bridge ops this build supports, build record, ROM hash; works with no bridge up
"""
import argparse, hashlib, json, os, re, subprocess, sys, time

from jus_addresses import CHAINS
import jus_ipc
from jus_ipc import IpcClient, BridgeState, DEFAULT_DIR
from jus_plan import PlanError, validate_plan, validate_watches, plan_to_lua
from owned import Owned
import state_identity as si

MAX_DUMP_BYTES = 0x400000  # 4 MB (all of main RAM)

SMOKE_ARGS = {  # minimal valid argv per subcommand, used by tests
    "run": ["p.json"], "peek": ["0x02000000", "1"],
    "poke": ["0x02000000", "ff"], "state": ["save", "s"],
    "dump": ["0x02000000", "0x02000010", "out.bin"],
    "watch": ["set", "w.json"], "screenshot": ["out.png"],
    "status": [], "stop": [], "selftest": [],
    "batch": ["steps.json"], "info": [],
}


def build_parser():
    p = argparse.ArgumentParser(prog="jusemu")
    p.add_argument("--ipc-dir", default=DEFAULT_DIR)
    sub = p.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run"); r.add_argument("plan")
    r.add_argument("--timeout", type=float,
                   help="override the plan timeout in seconds (GDB can slow emulation)")
    pk = sub.add_parser("peek")
    pk.add_argument("addr"); pk.add_argument("length", type=int)
    pk.add_argument("--chain", choices=sorted(CHAINS))
    pk.add_argument("--state", metavar="NAME",
                    help="read offline from a melonDS savestate (NAME in the save_states store, or a path) "
                         "instead of the live emulator")
    po = sub.add_parser("poke")
    po.add_argument("addr"); po.add_argument("hexbytes")
    _st_help = "save or load a savestate slot; a failed load also reports inspection and hint"
    st = sub.add_parser("state", help=_st_help, description=_st_help)
    st.add_argument("action", choices=["save", "load"])
    st.add_argument("slot")
    d = sub.add_parser("dump")
    d.add_argument("start"); d.add_argument("end"); d.add_argument("outfile")
    w = sub.add_parser("watch")
    w.add_argument("action", choices=["set"]); w.add_argument("spec", help="path to a watch spec JSON file")
    tl = sub.add_parser("tail")
    tl.add_argument("action", choices=["start", "stop"])
    tl.add_argument("spec", nargs="?",
                    help="path to a watch spec JSON file; omit to reuse `watch set`")
    tl.add_argument("--out", help="log path (default IPC runs/tail.jsonl)")
    tl.add_argument("--every", type=int, default=1,
                    help="sample every Nth frame (default 1 = every frame)")
    sd = sub.add_parser("screendump")
    sd.add_argument("outfile")
    sc = sub.add_parser("screenshot")
    sc.add_argument("outfile")
    sc.add_argument("--interactive", action="store_true",
                    help="fall back to manual window selection")
    bt = sub.add_parser("batch", help="run a JSON list of {op, args} steps as ONE bridge command")
    bt.add_argument("steps", help="JSON file: a list of steps, or {\"steps\": [...]}; - reads stdin")
    bt.add_argument("--timeout", type=float, default=15.0, help="seconds to wait for the single ack (default 15)")
    sub.add_parser("info", help="bridge ops, build record and ROM hash; offline-safe, read-only")
    for name in ("status", "stop", "selftest"):
        sub.add_parser(name)
    return p


def die(msg):
    print("error: %s" % msg, file=sys.stderr)
    raise SystemExit(2)


def parse_hexbytes(s):
    if len(s) == 0 or len(s) % 2 != 0 or not all(
            c in "0123456789abcdefABCDEF" for c in s):
        die("hexbytes must be even-length hex, got %r" % s)
    return [int(s[i:i+2], 16) for i in range(0, len(s), 2)]


def validate_dump_range(start, end):
    if end <= start:
        die("dump end must be > start")
    if end - start > MAX_DUMP_BYTES:
        die("dump larger than %d bytes" % MAX_DUMP_BYTES)
    return start, end


def build_peek(addr, length, chain):
    a = int(addr, 0)
    target = ({"chain": CHAINS[chain], "offset": a} if chain
              else {"addr": a})
    validate_watches([{"name": "peek", "len": length} | target])
    return "peek", dict(target, len=length)


def resolve_state_path(name):
    """A savestate path: NAME as an existing file, else store/NAME.mln.gz, else store/NAME.mln."""
    if os.path.isfile(os.path.expanduser(name)):
        return os.path.expanduser(name)
    import build_state  # lazy: only the offline path needs the savestate store
    store = build_state.store_dir()
    for ext in (".mln.gz", ".mln"):
        cand = store / (name + ext)
        if cand.is_file():
            return str(cand)
    die("no savestate %r: neither %s nor %s in %s" % (name, name + ".mln.gz", name + ".mln", store))


def load_state_ram(path):
    """RamImage over a savestate's main RAM (raw or gzipped .mln)."""
    try:
        with open(path, "rb") as f:
            blob = f.read()
        return si.RamImage(si.mln_ram(blob))
    except (OSError, EOFError, si.IdentityError) as e:
        die("cannot read savestate %s: %s" % (path, e))


def resolve_chain_offline(ram, chain):
    """The struct base a named chain reaches in a savestate's RAM: the same walk as agent_bridge.lua resolve_chain,
    read u32 and add the next offset, one hop per element after the first."""
    p = chain[0]
    for off in chain[1:]:
        try:
            p = ram.peek(p, 4)
        except si.IdentityError as e:
            die("chain %s: %s" % (chain, e))
        if not (si.MAIN_RAM <= p < si.MAIN_RAM + si.MAIN_RAM_SIZE) or p % 4:
            die("chain %s: bad pointer %#x" % (chain, p))
        p += off
    return p


def offline_read(ram, target, length):
    """What the live peek returns for `target` (build_peek's addr or chain+offset form), read from a savestate."""
    if "chain" in target:
        addr = resolve_chain_offline(ram, target["chain"]) + target.get("offset", 0)
    else:
        addr = target["addr"]
    try:
        value = ram.peek(addr, length)
    except si.IdentityError as e:
        die(str(e))
    if length in (1, 2, 4):
        return value
    return list(value.to_bytes(length, "little"))  # the live bridge returns a byte array for other lengths


def peek_offline(state, addr, length, chain=None):
    """The live peek's ack shape (without the bridge's id and epoch), read from a savestate."""
    try:
        _, target = build_peek(addr, length, chain)
    except (PlanError, ValueError) as e:
        die(str(e))
    ram = load_state_ram(resolve_state_path(state))
    return {"ok": True, "result": {"value": offline_read(ram, target, target["len"])}}


def run_timeout(total_frames):
    return total_frames / 30.0 + 15.0  # emulated speed >=30fps + slack


def resolve_run_timeout(total_frames, override=None):
    if override is not None:
        if override <= 0:
            die("--timeout must be positive")
        return override
    return run_timeout(total_frames)


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json(path):
    with open(path) as f:
        return json.load(f)


def make_run_dir(ipc_dir, plan, cmd_id, epoch):
    rd = os.path.join(ipc_dir, "runs", "%s-%d" % (plan["name"], cmd_id))
    os.makedirs(rd, exist_ok=True)
    with open(os.path.join(rd, "plan.json"), "w") as f:
        json.dump(plan, f, indent=1)
    meta = {"epoch": epoch, "cmd_id": cmd_id, "created": time.time(),
            "plan_sha256": hashlib.sha256(
                json.dumps(plan, sort_keys=True).encode()).hexdigest(),
            "reproducible": False}
    here = os.path.dirname(os.path.abspath(__file__))
    build_info = os.path.join(here, "build_info.json")
    hashes = os.path.join(here, "hashes.json")  # rom/bios/fw/save/config
    if os.path.exists(build_info) and os.path.exists(hashes):
        meta["build"] = _read_json(build_info)
        meta["hashes"] = _read_json(hashes)
        cfg = meta["hashes"].get("melonds_config_path")
        if cfg and os.path.exists(os.path.expanduser(cfg)):
            meta["config_sha256"] = _sha(os.path.expanduser(cfg))
        meta["reproducible"] = True
    if plan.get("load_state"):
        sidecar = os.path.join(ipc_dir, "states",
                               plan["load_state"] + ".meta.json")
        if os.path.exists(sidecar):
            meta["state"] = _read_json(sidecar)
    with open(os.path.join(rd, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    return rd


WINID_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "winid.c")
WINID_BIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "winid")


def melonds_window_id():
    """CoreGraphics window id for the emulator, or None.

    Not System Events. Asking it for melonDS's window id returns error -1728 --
    the Qt window is not exposed through the accessibility API, so no permission
    grant fixes it. Nor a full-display capture: melonDS normally sits behind the
    terminal, and a display capture only sees what is on top. `screencapture -l`
    can grab an occluded window, and CoreGraphics gives up the id with no extra
    permission and no Python dependency.
    """
    if not os.path.exists(WINID_BIN) or (
            os.path.exists(WINID_SRC)
            and os.path.getmtime(WINID_SRC) > os.path.getmtime(WINID_BIN)):
        b = subprocess.run(["cc", "-O2", "-framework", "CoreGraphics",
                            "-framework", "CoreFoundation",
                            "-o", WINID_BIN, WINID_SRC],
                           capture_output=True, text=True)
        if b.returncode != 0:
            print("could not build winid: %s" % b.stderr.strip(), file=sys.stderr)
            return None
    r = subprocess.run([WINID_BIN, "melonDS"], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    # melonDS owns several windows: the main one, a "Lua Script" console, Qt menu
    # bar strips (3440x24) and sometimes an untitled 500x500 helper. Picking the
    # first big one grabbed the untitled helper and captured a blank white image,
    # which then read as "the screen never changed". So key on the real title --
    # the main window is titled like "[60/60] melonDS 1.1".
    best = None
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        wid, dims, owner, title = parts[0], parts[1], parts[2], parts[3]
        # Match on the OWNING PROCESS, never the title. Matching titles captured
        # the terminal window, because it was titled "Hand off melonDS runtime
        # harness for JUS" -- it contained "melonDS", and being larger it won.
        # Fingerprints of the terminal then looked plausibly stable and produced
        # a completely fictitious "the screen never changed".
        if owner.strip() != "melonDS":
            continue
        if "Lua Script" in title:
            continue
        try:
            w, h = (int(x) for x in dims.split("x"))
        except ValueError:
            continue
        if w < 200 or h < 200:
            continue
        if best is None or w * h > best[1]:
            best = (wid, w * h)
    return best[0] if best else None


def do_screenshot(outfile, interactive):
    if sys.platform != "darwin":
        print("error: screenshot is macOS-only (CoreGraphics window capture). "
              "Use `jusemu.py screendump OUT.ppm`, which reads the core's "
              "framebuffer and works on every OS.", file=sys.stderr)
        return 2
    wid = melonds_window_id()
    if wid is None:
        if interactive:
            return subprocess.run(["screencapture", "-w", outfile]).returncode
        print("error: no melonDS window found via CoreGraphics (running?); "
              "use --interactive to pick a window manually", file=sys.stderr)
        return 1
    # -x no sound, -o no window shadow (keeps the image the exact window size).
    rc = subprocess.run(["screencapture", "-x", "-o", "-l", wid,
                         outfile]).returncode
    if rc == 0 and os.path.getsize(outfile) < 2000:
        print("warning: %s is suspiciously small -- the capture may be blank"
              % outfile, file=sys.stderr)
    return rc


BRIDGE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_bridge.lua")
CORE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bridge_core.lua")


def bridge_ops_from_file(path=BRIDGE_FILE):
    """Ops the bridge file dispatches: `handlers.X` entries plus the ops poll_commands tests by name. Read from the
    file, not from the running emulator (the bridge has no op that lists its own ops)."""
    with open(path) as f:
        lua = f.read()
    ops = set(re.findall(r"^(?:function )?handlers[.](\w+)\s*(?:=|\()", lua, re.M))
    ops |= set(re.findall(r'cmd\.op == "(\w+)"', lua))
    return sorted(ops)


def _build_record():
    here = os.path.dirname(os.path.abspath(__file__))
    out = {}
    for key, name in (("", "build_info.json"), ("native_linux", os.path.join("native_media", "build_info.linux.json"))):
        try:
            rec = _read_json(os.path.join(here, name))
        except (OSError, ValueError):
            continue
        keep = {k: rec[k] for k in ("fork_commit", "patches", "built_at", "app_path", "purpose") if k in rec}
        if key:
            out[key] = keep
        else:
            out.update(keep)
    out["note"] = "recorded in the repo's build_info; not read from the running binary"
    return out


def info_report(ipc_dir):
    """Everything `info` prints. Read-only: it never builds a client, so it makes no directories and cleans nothing."""
    hb = jus_ipc.read_heartbeat(ipc_dir)
    if hb is None:
        bridge = {"up": False, "state": BridgeState.DEAD.value,
                  "reason": "no heartbeat.json in %s: agent_bridge.lua is not loaded (or the IPC dir differs)" % ipc_dir}
    else:
        state = jus_ipc.interpret_heartbeat(hb, jus_ipc.emulator_process_alive(ipc_dir))
        bridge = {"up": state not in (BridgeState.DEAD, BridgeState.PAUSED), "state": state.value,
                  "session": hb.get("session"), "framecount": hb.get("framecount")}
        if state == BridgeState.PAUSED:
            bridge["reason"] = "heartbeat stale but the emulator process is alive (GDB stop?)"
    with open(BRIDGE_FILE, "rb") as f:
        file_sha = hashlib.sha256(f.read()).hexdigest()
    ops = {"source": "bridge-file", "list": bridge_ops_from_file(), "batch_max": jus_ipc.BATCH_MAX,
           "batch_refused": sorted(jus_ipc.BATCH_REFUSED),
           "bridge_file": os.path.relpath(BRIDGE_FILE, os.path.dirname(os.path.dirname(os.path.dirname(BRIDGE_FILE)))),
           "bridge_file_sha256": file_sha,
           "note": "derived offline from agent_bridge.lua in this checkout; the bridge has no op that lists its own ops, so "
                   "this is what the file dispatches, not proof the running emulator loaded this version. "
                   "native_capture_* answer 'unavailable in this build' on a build without the native recorder."}
    return {"bridge": bridge, "ops": ops, "build": _build_record(), "rom": jus_ipc.rom_info()}


def load_batch_steps(spec):
    """Steps from a JSON file path or `-` (stdin): a list, or an object with a "steps" list."""
    try:
        body = json.load(sys.stdin) if spec == "-" else _read_json(spec)
    except (OSError, ValueError) as e:
        die("cannot read batch steps from %s: %s" % ("stdin" if spec == "-" else spec, e))
    if isinstance(body, dict) and "steps" in body:
        body = body["steps"]
    try:
        return jus_ipc.validate_batch_steps(body)
    except ValueError as e:
        die(str(e))


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.command == "screenshot":
        raise SystemExit(do_screenshot(args.outfile, args.interactive))
    if args.command == "peek" and args.state is not None:
        # Offline: no IPC client, no lease, no bridge. The live path below is untouched.
        print(json.dumps(peek_offline(args.state, args.addr, args.length, args.chain), indent=1))
        return

    if args.command == "info":
        print(json.dumps(info_report(args.ipc_dir), indent=1))
        return
    if args.command == "run" and args.timeout is not None and args.timeout <= 0:
        die("--timeout must be positive")   # before the run dir or the command is written
    if args.command == "batch":
        if args.timeout <= 0:   # checked before anything is sent, as for `run`
            die("--timeout must be positive")
        steps = load_batch_steps(args.steps)   # refused before any client or file exists

    # Under a runner's lease (JUS_EMU_LEASE_TOKEN/EPOCH, e.g. case_batch's warm-up child) every IPC write is an
    # owned section (owned.py), so a fenced child writes nothing; without the env Owned(None) is a no-op.
    owned = Owned.from_env(args.ipc_dir)
    client = IpcClient(args.ipc_dir, guard=owned.section)

    if args.command == "status":
        state, hb = client.state()
        print(json.dumps({"state": state.value, "heartbeat": hb}, indent=1))
        return
    if args.command == "stop":
        client.request_stop()
        print("stop requested")
        return

    if args.command == "run":
        plan = validate_plan(_read_json(args.plan))
        cid = client.next_id()

        def write_run_dir():
            rd = make_run_dir(args.ipc_dir, plan, cid, client.epoch)
            with open(os.path.join(rd, "plan.lua"), "w") as f:
                f.write(plan_to_lua(plan))
            return rd
        rd = owned.run(write_run_dir)
        lua_path = os.path.join(rd, "plan.lua")
        client.publish_command(
            "run_plan", {"plan_path": lua_path, "run_dir": rd}, cmd_id=cid)
        try:
            ack = client.wait_ack(cid, timeout=resolve_run_timeout(plan["total_frames"], args.timeout))
        except TimeoutError:
            state, _ = client.state()
            if state == BridgeState.PAUSED:
                print("emulator paused (GDB?) — plan frozen, not failed. "
                      "Resume the emulator, then `jusemu status`.")
                return
            raise
        print(json.dumps(ack, indent=1))
        print("log: %s" % os.path.join(rd, "log.jsonl"))
        return

    if args.command == "batch":
        ack = client.batch(steps, timeout=args.timeout)
        print(json.dumps(ack, indent=1))
        if not ack.get("ok"):
            raise SystemExit(1)
        return

    if args.command == "state" and args.action == "load":
        # Same command as before; a failed ack (and a timeout) now also carries `inspection` and `hint`.
        try:
            ack = client.state_load(args.slot, timeout=30.0)
        except TimeoutError as e:
            print(json.dumps({"inspection": getattr(e, "inspection", None), "hint": getattr(e, "hint", None)},
                             indent=1), file=sys.stderr)
            raise
        print(json.dumps(ack, indent=1))
        return

    if args.command == "peek":
        op, a = build_peek(args.addr, args.length, args.chain)
        timeout = 10.0
    elif args.command == "poke":
        op, a = "poke", {"addr": int(args.addr, 0),
                         "bytes": parse_hexbytes(args.hexbytes)}
        timeout = 10.0
    elif args.command == "state":
        op, a = "state_" + args.action, {"slot": args.slot}
        timeout = 30.0  # save/load are multi-frame state machines
    elif args.command == "dump":
        s, e = validate_dump_range(int(args.start, 0), int(args.end, 0))
        op, a = "dump", {"start": s, "end": e,
                         "outfile": os.path.abspath(args.outfile)}
        timeout = 60.0
    elif args.command == "watch":
        specs = validate_watches(_read_json(args.spec))
        op, a = "set_watches", {"specs": specs}
        timeout = 10.0
    elif args.command == "tail":
        if args.action == "stop":
            op, a = "tail_stop", {}
        else:
            if args.every < 1:
                die("--every must be >= 1")
            a = {"every": args.every}
            if args.spec:
                a["specs"] = validate_watches(_read_json(args.spec))
            if args.out:
                a["out"] = os.path.abspath(args.out)
            op = "tail_start"
        timeout = 10.0
    elif args.command == "screendump":
        op, a = "screendump", {"path": os.path.abspath(args.outfile)}
        timeout = 15.0
    elif args.command == "selftest":
        op, a = "selftest", {}
        timeout = 30.0
    else:
        die("unhandled command %r" % args.command)
    cid = client.publish_command(op, a)
    print(json.dumps(client.wait_ack(cid, timeout=timeout), indent=1))


if __name__ == "__main__":
    main()
