"""The `batch` op (client side), the resident client, inspected state-load errors and `jusemu info`.

Everything runs against fake IPC dirs under tempfile.mkdtemp(); no emulator, no bridge. FakeBridge plays the
bridge's half of the file protocol (consume cmd/inbox.lua, write ack/<id>.json); the real agent_bridge.lua wiring is
covered by test_agent_bridge_wiring.lua (stub emulator globals), which TestBridgeWiring runs when `lua` is on PATH.
"""
import contextlib, gzip, hashlib, io, json, os, re, shutil, struct, subprocess, tempfile, threading, time, unittest
from pathlib import Path
from unittest import mock

import jus_ipc
import jusemu
from jus_ipc import IpcClient

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def write_hb(d, epoch="e1", state="idle", fc=100):
    tmp = os.path.join(d, "hb.tmp")
    with open(tmp, "w") as f:
        json.dump({"session": epoch, "framecount": fc, "wallclock": time.time(), "state": state}, f)
    os.replace(tmp, os.path.join(d, "heartbeat.json"))


class FakeBridge(threading.Thread):
    """Consumes cmd/inbox.lua like the bridge (read, delete) and acks. `respond(cmd)` -> (ok, result_or_error)."""

    def __init__(self, ipc_dir, respond=None, epoch="e1"):
        super().__init__(daemon=True)
        self.dir, self.epoch, self.respond = ipc_dir, epoch, respond or self.default
        self.seen = []                      # (id, op, raw inbox text), one per consumed command
        self._halt = threading.Event()
        self.mute = False                   # consume the inbox but never ack (an indeterminate command)

    @staticmethod
    def default(cmd):
        ops = re.findall(r'\["op"\] = "(\w+)"', cmd["raw"])
        ops = [o for o in ops if o != "batch"]
        return True, {"completed": len(ops), "failed_index": None,
                      "results": [{"op": o, "ok": True, "result": {}} for o in ops]}

    def run(self):
        inbox = os.path.join(self.dir, "cmd", "inbox.lua")
        while not self._halt.is_set():
            if os.path.exists(inbox):
                with open(inbox) as f:
                    raw = f.read()
                os.remove(inbox)
                cid = int(re.search(r'\["id"\] = (\d+)', raw).group(1))
                cmd = {"id": cid, "raw": raw}
                self.seen.append((cid, cmd, raw))
                if self.mute:
                    continue
                ok, payload = self.respond(cmd)
                body = {"id": cid, "epoch": self.epoch, "ok": ok}
                body["result" if ok or isinstance(payload, dict) else "error"] = payload
                if not ok and isinstance(payload, dict):
                    body["error"] = payload.get("error", "failed")
                tmp = os.path.join(self.dir, "ack", "t.tmp")
                with open(tmp, "w") as f:
                    json.dump(body, f)
                os.replace(tmp, os.path.join(self.dir, "ack", "%d.json" % cid))
            time.sleep(0.01)

    def stop(self):
        self._halt.set()
        self.join(timeout=2)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        write_hb(self.dir)
        self.client = IpcClient(self.dir)

    def bridge(self, respond=None):
        b = FakeBridge(self.dir, respond)
        b.start()
        self.addCleanup(b.stop)
        return b


class TestBatchClient(Base):
    STEPS = [{"op": "poke", "args": {"addr": 0x02000010, "bytes": [1, 2]}}, {"op": "peek", "args": {"addr": 0x02000010, "len": 2}}]

    def test_round_trip_one_id_one_ack(self):
        b = self.bridge()
        before = self.client._next_id()
        ack = self.client.batch(self.STEPS, timeout=5)
        self.assertTrue(ack["ok"])
        self.assertEqual(ack["result"]["completed"], 2)
        self.assertEqual([r["op"] for r in ack["result"]["results"]], ["poke", "peek"])
        self.assertEqual(len(b.seen), 1, "the whole batch is one published command")
        self.assertEqual(b.seen[0][0], before + 1, "the whole batch consumed exactly one id")
        self.assertIn('["op"] = "batch"', b.seen[0][2])
        self.assertIn('["steps"]', b.seen[0][2])
        self.assertEqual(os.listdir(os.path.join(self.dir, "ack")), [], "ack consumed")
        self.assertFalse(os.path.exists(os.path.join(self.dir, "cmd", "pending.json")))

    def test_failure_ack_keeps_partial_results(self):
        self.bridge(lambda cmd: (False, {"error": "step 1 (tail_stop): no tail running", "completed": 1, "failed_index": 1,
                                         "results": [{"op": "peek", "ok": True, "result": {}},
                                                     {"op": "tail_stop", "ok": False, "error": "no tail running"}]}))
        ack = self.client.batch([{"op": "peek", "args": {"addr": 0x02000000, "len": 1}}, {"op": "tail_stop"}], timeout=5)
        self.assertFalse(ack["ok"])
        self.assertEqual(ack["result"]["failed_index"], 1)
        self.assertEqual(len(ack["result"]["results"]), 2)

    def test_refused_ops_never_published(self):
        b = self.bridge()
        for op in ("run_plan", "state_load", "state_save", "batch"):
            with self.subTest(op=op):
                with self.assertRaisesRegex(ValueError, "not allowed in a batch"):
                    self.client.batch([{"op": "peek", "args": {}}, {"op": op, "args": {}}], timeout=1)
        self.assertEqual(b.seen, [])
        self.assertFalse(os.path.exists(os.path.join(self.dir, "cmd", "pending.json")))

    def test_bad_step_shapes_rejected(self):
        for steps in ("x", [1], [{"args": {}}], [{"op": 3}], [{"op": "peek", "args": 5}],
                      [{"op": "peek"}] * (jus_ipc.BATCH_MAX + 1)):
            with self.subTest(steps=steps):
                with self.assertRaises(ValueError):
                    self.client.batch(steps, timeout=1)

    def test_empty_batch_is_legal(self):
        self.bridge()
        ack = self.client.batch([], timeout=5)
        self.assertTrue(ack["ok"])

    def test_resend_after_timeout_is_refused_not_duplicated(self):
        """At-most-once: an unacked batch has an unknown fate, so a second batch must not be published on top of it."""
        b = self.bridge()
        b.mute = True
        with self.assertRaises(TimeoutError):
            self.client.batch(self.STEPS, timeout=0.3)
        with self.assertRaisesRegex(RuntimeError, "pending"):
            self.client.batch(self.STEPS, timeout=0.3)
        time.sleep(0.1)
        self.assertEqual(len(b.seen), 1, "the bridge saw the batch once")
        # only an explicit abandon (fate unknown, caller's call) frees the slot
        self.assertTrue(self.client.abandon(b.seen[0][0]))
        b.mute = False
        self.assertTrue(self.client.batch(self.STEPS, timeout=5)["ok"])
        self.assertEqual(len(b.seen), 2)

    def test_epoch_change_is_picked_up_before_publishing(self):
        """A resident client outlives bridge restarts: batch re-reads the heartbeat session instead of sending a stale epoch."""
        write_hb(self.dir, epoch="e2")
        b = FakeBridge(self.dir, epoch="e2")
        b.start()
        self.addCleanup(b.stop)
        self.assertEqual(self.client.epoch, "e1")
        ack = self.client.batch(self.STEPS, timeout=5)
        self.assertTrue(ack["ok"])
        self.assertEqual(self.client.epoch, "e2")
        self.assertIn('"e2"', b.seen[0][2])


class TestResident(Base):
    def setUp(self):
        super().setUp()
        jus_ipc._RESIDENT.clear()
        self.addCleanup(jus_ipc._RESIDENT.clear)

    def test_one_client_per_dir(self):
        a = jus_ipc.resident(self.dir)
        self.assertIs(a, jus_ipc.resident(self.dir))
        other = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, other, True)
        self.assertIsNot(a, jus_ipc.resident(other))

    def test_module_level_batch_uses_the_resident_client(self):
        self.bridge()
        ack = jus_ipc.batch([{"op": "status", "args": {}}], ipc_dir=self.dir, timeout=5)
        self.assertTrue(ack["ok"])
        self.assertEqual(jus_ipc.resident(self.dir).dir, os.path.abspath(self.dir))

    def test_l77m_fast_keeps_its_surface(self):
        src = (HERE.parent / "l77m_fast.py").read_text()
        for name in ("def peek", "def poke", "def poke_u16", "def poke_u32", "def state_load", "def run_plan", "def batch"):
            self.assertIn(name, src)


def mln(version=(1, 3), ram=b"\0" * 64, gz=False):
    """A synthetic melonDS savestate: MELN header + one NDSG section (the real RAM layout is not needed here)."""
    sect = b"NDSG" + struct.pack("<I", 16 + len(ram)) + b"\0" * 8 + ram
    blob = b"MELN" + struct.pack("<HHI", version[0], version[1], 16 + len(sect)) + b"\0" * 4 + sect
    return gzip.compress(blob, mtime=0) if gz else blob


class TestInspection(Base):
    def put_state(self, slot="s1", blob=None, sidecar='{"framecount_at_save":1234,"saved_at":1,"session":"x","slot":"s1"}'):
        states = os.path.join(self.dir, "states")
        if blob is not None:
            Path(states, slot + ".mln").write_bytes(blob)
        if sidecar is not None:
            Path(states, slot + ".meta.json").write_text(sidecar)

    def inspect(self, slot="s1", **kw):
        kw.setdefault("archive_dir", None)
        kw.setdefault("hashes", {"rom_sha256": "ab" * 32, "rom_path": os.path.join(self.dir, "no-rom.nds")})
        return jus_ipc.inspect_state_load(self.dir, slot, **kw)

    def test_header_and_sidecar_fields(self):
        self.put_state(blob=mln())
        i = self.inspect(last_framecount=777)
        self.assertEqual(i["slot"], "s1")
        self.assertTrue(i["mln"]["present"])
        self.assertEqual(i["mln"]["magic"], "MELN")
        self.assertEqual(i["mln"]["version"], "1.3")
        self.assertIn("NDSG", i["mln"]["sections"])
        self.assertFalse(i["mln"]["gzipped"])
        self.assertTrue(i["sidecar"]["present"])
        self.assertTrue(i["sidecar"]["json_ok"])
        self.assertTrue(i["sidecar"]["bridge_regex_ok"])
        self.assertEqual(i["sidecar"]["framecount_at_save"], 1234)
        self.assertEqual(i["last_framecount"], 777)
        self.assertEqual(i["rom"]["recorded_sha256"], "ab" * 32)
        self.assertIsNone(i["rom"]["actual_sha256"], "ROM file absent: reported, not invented")
        self.assertIn("hint", i)

    def test_missing_state_file(self):
        self.put_state(blob=None)
        i = self.inspect()
        self.assertFalse(i["mln"]["present"])
        self.assertIn("no .mln", i["hint"])

    def test_corrupt_header(self):
        self.put_state(blob=b"JUNKJUNKJUNKJUNKJUNK")
        i = self.inspect()
        self.assertTrue(i["mln"]["present"])
        self.assertFalse(i["mln"]["header_ok"])
        self.assertIn("not a melonDS savestate", i["hint"])

    def test_gzipped_state_is_read_through(self):
        self.put_state(blob=mln(gz=True))
        i = self.inspect()
        self.assertTrue(i["mln"]["gzipped"])
        self.assertTrue(i["mln"]["header_ok"])

    def test_no_sidecar_is_the_bridge_refusal(self):
        self.put_state(blob=mln(), sidecar=None)
        i = self.inspect()
        self.assertFalse(i["sidecar"]["present"])
        self.assertIn("no sidecar", i["hint"])

    def test_spaced_json_sidecar_is_parseable_but_not_for_the_bridge(self):
        self.put_state(blob=mln(), sidecar=json.dumps({"slot": "s1", "framecount_at_save": 5}))
        i = self.inspect()
        self.assertTrue(i["sidecar"]["json_ok"])
        self.assertFalse(i["sidecar"]["bridge_regex_ok"])
        self.assertIn("compact", i["hint"])

    def test_unparseable_sidecar(self):
        self.put_state(blob=mln(), sidecar="{not json")
        i = self.inspect()
        self.assertFalse(i["sidecar"]["json_ok"])

    def test_dummy_sidecar_hint_says_the_load_may_have_worked(self):
        self.put_state(blob=mln(), sidecar='{"framecount_at_save":0,"slot":"s1"}')
        i = self.inspect(settle_timeout=True)
        self.assertIn("0x02181B28", i["hint"])
        self.assertIn("dummy", i["hint"])

    def test_sha_against_archive_manifest(self):
        blob = mln()
        self.put_state(blob=blob)
        arch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, arch, True)
        Path(arch, "s1.meta.json").write_text(json.dumps({"slot": "s1", "sha256": hashlib.sha256(blob).hexdigest()}))
        i = self.inspect(archive_dir=arch)
        self.assertTrue(i["archive"]["listed"])
        self.assertTrue(i["archive"]["match"])
        Path(arch, "s1.meta.json").write_text(json.dumps({"slot": "s1", "sha256": "0" * 64}))
        i = self.inspect(archive_dir=arch)
        self.assertFalse(i["archive"]["match"])
        self.assertIn("differs from the archive", i["hint"])

    def test_gzipped_state_hashes_the_raw_bytes_like_the_archive(self):
        raw = mln()
        self.put_state(blob=gzip.compress(raw, mtime=0))
        arch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, arch, True)
        Path(arch, "s1.meta.json").write_text(json.dumps({"sha256": hashlib.sha256(raw).hexdigest()}))
        self.assertTrue(self.inspect(archive_dir=arch)["archive"]["match"])

    def test_archive_without_the_slot_is_reported_unlisted(self):
        self.put_state(blob=mln())
        arch = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, arch, True)
        i = self.inspect(archive_dir=arch)
        self.assertFalse(i["archive"]["listed"])

    def test_rom_hash_actual_vs_recorded(self):
        self.put_state(blob=mln())
        rom = os.path.join(self.dir, "rom.nds")
        Path(rom).write_bytes(b"rom-bytes")
        good = hashlib.sha256(b"rom-bytes").hexdigest()
        i = self.inspect(hashes={"rom_sha256": good, "rom_path": rom})
        self.assertTrue(i["rom"]["match"])
        i = self.inspect(hashes={"rom_sha256": "00" * 32, "rom_path": rom})
        self.assertFalse(i["rom"]["match"])
        self.assertIn("ROM", i["hint"])

    def test_forced_load_failure_attaches_inspection_to_the_ack(self):
        """The client path end to end: a fake bridge refuses the load; the returned ack carries inspection + hint."""
        self.put_state(blob=mln(), sidecar='{"framecount_at_save":0,"slot":"s1"}')
        self.bridge(lambda cmd: (False, "state load did not settle (framecount never hit target)"))
        ack = self.client.state_load("s1", timeout=5, archive_dir=None,
                                     hashes={"rom_sha256": "ab" * 32, "rom_path": "/nonexistent.nds"})
        self.assertFalse(ack["ok"])
        self.assertIn("did not settle", ack["error"])
        self.assertEqual(ack["inspection"]["mln"]["version"], "1.3")
        self.assertEqual(ack["inspection"]["last_framecount"], 100, "from the heartbeat")
        self.assertIn("hint", ack)
        self.assertEqual(ack["hint"], ack["inspection"]["hint"])

    def test_successful_load_is_left_alone(self):
        self.put_state(blob=mln())
        self.bridge(lambda cmd: (True, {"loaded": True, "framecount": 1234}))
        ack = self.client.state_load("s1", timeout=5)
        self.assertTrue(ack["ok"])
        self.assertNotIn("inspection", ack)
        self.assertNotIn("hint", ack)

    def test_ack_timeout_carries_the_inspection(self):
        self.put_state(blob=mln())
        b = self.bridge()
        b.mute = True
        with self.assertRaises(TimeoutError) as cm:
            self.client.state_load("s1", timeout=0.3, archive_dir=None, hashes={})
        self.assertIn("mln", cm.exception.inspection)

    def test_cli_state_load_failure_prints_inspection(self):
        self.put_state(blob=mln())
        self.bridge(lambda cmd: (False, "no sidecar for state 's1'"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch("jus_ipc.default_archive_dir", return_value=None):
            jusemu.main(["--ipc-dir", self.dir, "state", "load", "s1"])
        body = json.loads(out.getvalue())
        self.assertFalse(body["ok"])
        self.assertIn("inspection", body)

    def test_cli_state_load_success_output_unchanged(self):
        self.put_state(blob=mln())
        self.bridge(lambda cmd: (True, {"loaded": True}))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            jusemu.main(["--ipc-dir", self.dir, "state", "load", "s1"])
        self.assertEqual(sorted(json.loads(out.getvalue())), ["epoch", "id", "ok", "result"])


class TestBatchVerb(Base):
    def run_cli(self, *argv, stdin=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            if stdin is not None:
                with mock.patch("sys.stdin", io.StringIO(stdin)):
                    rc = None
                    try:
                        jusemu.main(["--ipc-dir", self.dir, *argv])
                    except SystemExit as e:
                        rc = e.code
            else:
                rc = None
                try:
                    jusemu.main(["--ipc-dir", self.dir, *argv])
                except SystemExit as e:
                    rc = e.code
        return rc, out.getvalue()

    def test_parser_knows_the_new_verbs(self):
        p = jusemu.build_parser()
        for cmd in ("batch", "info"):
            self.assertEqual(p.parse_args([cmd] + jusemu.SMOKE_ARGS[cmd]).command, cmd)

    def test_batch_from_file(self):
        self.bridge()
        f = os.path.join(self.dir, "steps.json")
        Path(f).write_text(json.dumps([{"op": "peek", "args": {"addr": 0x02000000, "len": 4}}, {"op": "status"}]))
        rc, out = self.run_cli("batch", f)
        self.assertIsNone(rc)
        self.assertTrue(json.loads(out)["ok"])

    def test_batch_from_stdin_accepts_a_steps_object(self):
        self.bridge()
        rc, out = self.run_cli("batch", "-", stdin=json.dumps({"steps": [{"op": "status"}]}))
        self.assertTrue(json.loads(out)["ok"])

    def test_failed_batch_exits_nonzero_and_prints_partials(self):
        self.bridge(lambda cmd: (False, {"error": "step 0 (tail_stop): no tail running", "completed": 0, "failed_index": 0,
                                         "results": [{"op": "tail_stop", "ok": False, "error": "no tail running"}]}))
        rc, out = self.run_cli("batch", "-", stdin=json.dumps([{"op": "tail_stop"}]))
        self.assertEqual(rc, 1)
        self.assertEqual(json.loads(out)["result"]["failed_index"], 0)

    def test_refused_op_is_a_cli_error(self):
        rc, out = self.run_cli("batch", "-", stdin=json.dumps([{"op": "state_load", "args": {"slot": "x"}}]))
        self.assertEqual(rc, 2)
        self.assertEqual(out, "")
        self.assertFalse(os.path.exists(os.path.join(self.dir, "cmd", "pending.json")))

    def test_batch_timeout_must_be_positive_and_publishes_nothing(self):
        f = os.path.join(self.dir, "steps.json")
        Path(f).write_text(json.dumps([{"op": "status"}]))
        cmd_dir = os.path.join(self.dir, "cmd")
        before = sorted(os.listdir(cmd_dir))
        for bad in ("0", "-1"):
            rc, out = self.run_cli("batch", "--timeout", bad, f)
            self.assertEqual(rc, 2, bad)
            self.assertEqual(out, "")
            self.assertEqual(sorted(os.listdir(cmd_dir)), before, bad)
            self.assertFalse(os.path.exists(os.path.join(cmd_dir, "pending.json")))

    def test_run_timeout_must_be_positive_and_publishes_nothing(self):
        f = os.path.join(self.dir, "plan.json")
        Path(f).write_text(json.dumps({"name": "t", "segments": [{"from": 0, "to": 10, "buttons": ["A"]}]}))
        before = sorted(os.listdir(self.dir))
        cmd_before = sorted(os.listdir(os.path.join(self.dir, "cmd")))
        for bad in ("0", "-1"):
            rc, out = self.run_cli("run", "--timeout", bad, f)
            self.assertEqual(rc, 2, bad)
            self.assertEqual(out, "")
            self.assertEqual(sorted(os.listdir(self.dir)), before, bad)   # no run dir
            self.assertEqual(sorted(os.listdir(os.path.join(self.dir, "cmd"))), cmd_before, bad)


class TestInfo(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def info(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            jusemu.main(["--ipc-dir", self.dir, "info"])
        return json.loads(out.getvalue())

    def test_offline_reports_bridge_down_and_derives_ops_from_the_file(self):
        body = self.info()
        self.assertFalse(body["bridge"]["up"])
        self.assertEqual(body["bridge"]["state"], "dead")
        self.assertEqual(body["ops"]["source"], "bridge-file")
        ops = set(body["ops"]["list"])
        for op in ("peek", "poke", "status", "batch", "run_plan", "state_load", "state_save", "native_capture_start", "tail_start"):
            self.assertIn(op, ops)
        self.assertEqual(body["ops"]["batch_refused"], ["batch", "run_plan", "state_load", "state_save"])
        self.assertIn("agent_bridge.lua", body["ops"]["bridge_file"])
        self.assertEqual(len(body["ops"]["bridge_file_sha256"]), 64)
        self.assertIn("note", body["ops"])
        self.assertIn("rom", body)
        self.assertIn("build", body)

    def test_offline_info_writes_nothing_to_the_ipc_dir(self):
        self.info()
        self.assertEqual(os.listdir(self.dir), [])

    @unittest.skipUnless((HERE.parent / "build_info.json").exists(), "build_info.json is not in this repository")
    def test_build_section_reads_build_info(self):
        build = self.info()["build"]
        with open(HERE.parent / "build_info.json") as f:
            self.assertEqual(build["fork_commit"], json.load(f)["fork_commit"])

    def test_live_heartbeat_is_reported_without_touching_state(self):
        write_hb(self.dir, epoch="e9", state="idle", fc=4321)
        before = sorted(os.listdir(self.dir))
        with mock.patch("jus_ipc.emulator_process_alive", return_value=True):
            body = self.info()
        self.assertTrue(body["bridge"]["up"])
        self.assertEqual(body["bridge"]["session"], "e9")
        self.assertEqual(body["bridge"]["framecount"], 4321)
        self.assertEqual(sorted(os.listdir(self.dir)), before)

    def test_ops_match_the_real_bridge_op_table(self):
        """Guards the offline derivation against drift: every handlers.* name and special op in agent_bridge.lua is listed."""
        lua = (HERE.parent / "agent_bridge.lua").read_text()
        names = set(re.findall(r"^(?:function )?handlers[.](\w+)\s*(?:=|\()", lua, re.M))
        names |= set(re.findall(r'cmd\.op == "(\w+)"', lua))
        self.assertEqual(set(self.info()["ops"]["list"]), names)


class TestConstantsAgree(unittest.TestCase):
    def test_python_batch_constants_match_bridge_core(self):
        lua = (HERE.parent / "bridge_core.lua").read_text()
        self.assertEqual(int(re.search(r"M\.BATCH_MAX = (\d+)", lua).group(1)), jus_ipc.BATCH_MAX)
        refused = re.search(r"M\.BATCH_REFUSED = \{([^}]*)\}", lua).group(1)
        self.assertEqual(sorted(re.findall(r"(\w+) = true", refused)), sorted(jus_ipc.BATCH_REFUSED))


@unittest.skipUnless(shutil.which("lua"), "needs the lua 5.4 CLI")
class TestBridgeWiring(unittest.TestCase):
    def test_agent_bridge_batch_wiring(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        env = dict(os.environ, JUS_EMU_DIR=d, JUS_EMU_SRC=str(HERE.parent))
        r = subprocess.run(["lua", str(HERE / "test_agent_bridge_wiring.lua")], env=env, cwd=REPO,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("failed=0", r.stdout)


@unittest.skipUnless(shutil.which("lua"), "needs the lua 5.4 CLI")
class TestBridgeCore(unittest.TestCase):
    def test_bridge_core_lua_checks(self):
        # bridge_core.lua sets package.path relative to the repo root, so run from there.
        r = subprocess.run(["lua", str(HERE / "test_bridge_core.lua")], cwd=REPO,
                           capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("failed=0", r.stdout)


if __name__ == "__main__":
    unittest.main()
