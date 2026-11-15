import json, os, shutil, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from unittest import mock
from jus_ipc import IpcClient, BridgeState, emulator_process_alive, interpret_heartbeat


def write_hb(d, epoch="epoch1", state="idle", age=0.0):
    tmp = os.path.join(d, "hb.tmp")
    with open(tmp, "w") as f:
        json.dump({"session": epoch, "framecount": 100,
                   "wallclock": time.time() - age, "state": state}, f)
    os.replace(tmp, os.path.join(d, "heartbeat.json"))


@unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux /proc")
class TestEmulatorProcessAlive(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def spawn(self, argv):
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def stop():
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=5)
        self.addCleanup(stop)
        return process

    def pid_record(self, filename, pid):
        body = f"{pid}\n" if filename == "emu.pid" else f"test-holder\n{pid}\n2026-10-22\n0\n"
        (self.root / filename).write_text(body)

    def test_emulator_name_only_in_argv_is_not_alive(self):
        self.spawn([sys.executable, "-c", "import time; time.sleep(60)", "--note=melonDS"])
        self.assertFalse(emulator_process_alive())

    def test_comm_name_is_alive(self):
        binary = self.root / "melonDS"
        binary.symlink_to(shutil.which("sleep"))
        process = self.spawn([str(binary), "60"])
        self.assertEqual(Path(f"/proc/{process.pid}/comm").read_text().strip(), "melonDS")
        self.assertNotIn("melonds", os.readlink(f"/proc/{process.pid}/exe").lower())
        self.assertTrue(emulator_process_alive())

    def test_exe_basename_is_alive_when_comm_is_truncated(self):
        binary = self.root / "long-worker-prefix-MeLoNdS"
        shutil.copyfile(shutil.which("sleep"), binary)
        binary.chmod(0o700)
        process = self.spawn([str(binary), "60"])
        self.assertNotIn("melonds", Path(f"/proc/{process.pid}/comm").read_text().lower())
        self.assertTrue(emulator_process_alive())

    def test_live_emu_pid_covers_renamed_binary(self):
        process = self.spawn([shutil.which("sleep"), "60"])
        self.pid_record("emu.pid", process.pid)
        self.assertTrue(emulator_process_alive(self.root))

    def test_live_holder_pid_covers_renamed_binary(self):
        process = self.spawn([shutil.which("sleep"), "60"])
        self.pid_record("HOLDER", process.pid)
        self.assertTrue(emulator_process_alive(self.root))

    def test_dead_pid_records_are_not_alive(self):
        process = self.spawn([shutil.which("sleep"), "60"])
        process.terminate()
        process.wait(timeout=5)
        self.assertFalse(Path(f"/proc/{process.pid}").exists())
        for filename in ("emu.pid", "HOLDER"):
            self.pid_record(filename, process.pid)
        self.assertFalse(emulator_process_alive(self.root))

    def test_missing_pid_records_are_not_alive(self):
        self.assertFalse(emulator_process_alive(self.root))

    def test_unparseable_pid_records_fail_closed(self):
        for filename, bodies in (("emu.pid", ("", "oops\n", "0\n", "-1\n")),
                                 ("HOLDER", ("", "test-holder\n", "test-holder\n\n", "test-holder\noops\n"))):
            for body in bodies:
                with self.subTest(filename=filename, body=body):
                    path = self.root / filename
                    path.write_text(body)
                    try:
                        self.assertTrue(emulator_process_alive(self.root))
                    finally:
                        path.unlink()

    def test_unlistable_proc_fails_closed(self):
        with mock.patch("jus_ipc.os.listdir", side_effect=PermissionError("/proc denied")):
            self.assertTrue(emulator_process_alive())

    def test_unreadable_pid_records_fail_closed(self):
        for filename in ("emu.pid", "HOLDER"):
            with self.subTest(filename=filename):
                path = self.root / filename
                path.mkdir()
                try:
                    self.assertTrue(emulator_process_alive(self.root))
                finally:
                    path.rmdir()

    def test_invalid_pid_record_encoding_fails_closed(self):
        for filename in ("emu.pid", "HOLDER"):
            with self.subTest(filename=filename):
                path = self.root / filename
                path.write_bytes(b'\xff')
                try:
                    self.assertTrue(emulator_process_alive(self.root))
                finally:
                    path.unlink()

    def test_client_state_uses_its_ipc_pid_records(self):
        process = self.spawn([shutil.which("sleep"), "60"])
        self.pid_record("emu.pid", process.pid)
        write_hb(self.root, age=60)
        state, _ = IpcClient(str(self.root)).state()
        self.assertEqual(state, BridgeState.PAUSED)

    def test_jusemu_status_ignores_argv_and_reads_holder_pid(self):
        decoy = self.spawn([sys.executable, "-c", "import time; time.sleep(60)", "--note=melonDS"])
        write_hb(self.root, age=60)
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / "jusemu.py"),
                   "--ipc-dir", str(self.root), "status"]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["state"], "dead")
        self.pid_record("HOLDER", decoy.pid)
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["state"], "paused")


class TestHeartbeat(unittest.TestCase):
    def hb(self, age_s, state="idle", alive=True):
        return interpret_heartbeat(
            {"session": "abc", "framecount": 100,
             "wallclock": time.time() - age_s, "state": state},
            emulator_alive=alive)

    def test_fresh_states(self):
        self.assertEqual(self.hb(0.5), BridgeState.IDLE)
        self.assertEqual(self.hb(0.5, "plan_running"), BridgeState.PLAN_RUNNING)
        self.assertEqual(self.hb(0.5, "loading_state"), BridgeState.LOADING_STATE)
        self.assertEqual(self.hb(0.5, "saving_state"), BridgeState.SAVING_STATE)

    def test_stale_alive_is_paused(self):
        self.assertEqual(self.hb(30, alive=True), BridgeState.PAUSED)

    def test_stale_dead_is_dead(self):
        self.assertEqual(self.hb(30, alive=False), BridgeState.DEAD)

    def test_unknown_state_is_dead(self):
        self.assertEqual(self.hb(0.5, "wat"), BridgeState.DEAD)


class TestClientNoBridge(unittest.TestCase):
    def test_status_without_heartbeat_is_dead(self):
        c = IpcClient(tempfile.mkdtemp())
        state, hb = c.state()
        self.assertEqual(state, BridgeState.DEAD)
        self.assertIsNone(hb)

    def test_publish_without_heartbeat_raises(self):
        c = IpcClient(tempfile.mkdtemp())
        with self.assertRaises(RuntimeError):
            c.publish_command("status", {})


class TestClient(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        write_hb(self.dir)
        self.c = IpcClient(self.dir)

    def ack(self, cid, epoch="epoch1", ok=True):
        tmp = os.path.join(self.dir, "ack", "t")
        with open(tmp, "w") as f:
            json.dump({"id": cid, "epoch": epoch, "ok": ok,
                       "result": {"state": "idle"}}, f)
        os.replace(tmp, os.path.join(self.dir, "ack", "%d.json" % cid))

    def test_ids_monotonic_across_instances(self):
        a = self.c.publish_command("status", {})
        self.ack(a)
        self.c.wait_ack(a, timeout=1)
        c2 = IpcClient(self.dir)
        b = c2.publish_command("status", {})
        self.assertGreater(b, a)

    def test_publish_writes_inbox_and_pending(self):
        cid = self.c.publish_command("status", {})
        self.assertTrue(os.path.exists(
            os.path.join(self.dir, "cmd", "inbox.lua")))
        self.assertTrue(os.path.exists(
            os.path.join(self.dir, "cmd", "pending.json")))
        with open(os.path.join(self.dir, "cmd", "inbox.lua")) as f:
            content = f.read()
        self.assertIn('"status"', content)
        self.assertIn("epoch1", content)
        self.assertIn(str(cid), content)

    def test_pending_blocks_even_after_inbox_consumed(self):
        self.c.publish_command("status", {})
        os.remove(os.path.join(self.dir, "cmd", "inbox.lua"))  # bridge ate it
        with self.assertRaises(RuntimeError):
            self.c.publish_command("status", {})

    def test_wait_ack_clears_pending(self):
        cid = self.c.publish_command("status", {})
        self.ack(cid)
        ack = self.c.wait_ack(cid, timeout=1)
        self.assertTrue(ack["ok"])
        self.assertFalse(os.path.exists(
            os.path.join(self.dir, "cmd", "pending.json")))

    def test_ack_with_wrong_epoch_rejected(self):
        cid = self.c.publish_command("status", {})
        self.ack(cid, epoch="old-epoch")
        with self.assertRaises(TimeoutError):
            self.c.wait_ack(cid, timeout=0.3)

    def test_stale_epoch_files_cleaned_on_new_epoch(self):
        cid = self.c.publish_command("status", {})
        # bridge restarts with a new session:
        write_hb(self.dir, epoch="epoch2")
        c2 = IpcClient(self.dir)
        c2.publish_command("status", {})  # must not raise: stale cleaned
        self.assertEqual(c2.epoch, "epoch2")

    def test_wait_ack_timeout_is_indeterminate(self):
        cid = self.c.publish_command("status", {})
        with self.assertRaises(TimeoutError):
            self.c.wait_ack(cid, timeout=0.2)


class Refused(Exception):
    pass


class TestOwnership(unittest.TestCase):
    """Ack cleanup is ID-specific, and every mutation runs inside the client's guard."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        write_hb(self.dir)
        self.guarded = []

    def ack(self, cid, epoch="epoch1"):
        with open(os.path.join(self.dir, "ack", "%d.json" % cid), "w") as f:
            json.dump({"id": cid, "epoch": epoch, "ok": True}, f)

    def path(self, *p):
        return os.path.join(self.dir, *p)

    def snapshot(self):
        out = {}
        for d, _, files in os.walk(self.dir):
            for n in files:
                with open(os.path.join(d, n), "rb") as f:
                    out[os.path.relpath(os.path.join(d, n), self.dir)] = f.read()
        return out

    def test_a_pending_marker_of_another_command_survives_the_ack(self):
        a = IpcClient(self.dir)
        cid = a.publish_command("status", {})
        os.remove(self.path("cmd", "inbox.lua"))           # bridge consumed A's command and acked it
        self.ack(cid)
        os.remove(self.path("cmd", "pending.json"))        # B reconciled A's marker
        b = IpcClient(self.dir)
        bid = b.publish_command("native_capture_start", {"owner": "B"})
        a.wait_ack(cid, timeout=1)
        with open(self.path("cmd", "pending.json")) as f:
            self.assertEqual(json.load(f)["id"], bid)
        self.assertTrue(os.path.exists(self.path("cmd", "inbox.lua")))
        self.assertFalse(os.path.exists(self.path("ack", "%d.json" % cid)))
        with self.assertRaises(RuntimeError):
            a.publish_command("status", {})               # B's command is still pending

    def test_a_foreign_ack_is_not_deleted(self):
        c = IpcClient(self.dir)
        cid = c.publish_command("status", {})
        self.ack(cid, epoch="other-epoch")
        with self.assertRaises(TimeoutError):
            c.wait_ack(cid, timeout=0.2)
        self.assertTrue(os.path.exists(self.path("ack", "%d.json" % cid)))
        self.assertTrue(os.path.exists(self.path("cmd", "pending.json")))

    def guard_that(self, refuse):
        test = self

        class Guard:
            def __enter__(self):
                test.guarded.append("enter")
                if refuse[0]:
                    raise Refused

            def __exit__(self, *exc):
                test.guarded.append("exit")
        return lambda: Guard()

    def test_a_refusing_guard_leaves_every_file_intact(self):
        refuse = [False]
        c = IpcClient(self.dir, guard=self.guard_that(refuse))
        cid = c.publish_command("status", {})
        self.ack(cid)
        with open(self.path("cmd", "pending.json"), "w") as f:
            json.dump({"id": cid, "epoch": "stale"}, f)   # would be cleaned by a new client
        before = self.snapshot()
        refuse[0] = True
        for op in (lambda: c.wait_ack(cid, timeout=1), c.next_id,
                   lambda: c.publish_command("status", {}), c.request_stop,
                   lambda: IpcClient(self.dir, guard=self.guard_that(refuse))):
            with self.assertRaises(Refused):
                op()
            self.assertEqual(self.snapshot(), before)

    def test_mutations_happen_inside_the_guard(self):
        import jus_ipc
        inside = [False]
        test = self

        class Guard:
            def __enter__(self):
                inside[0] = True

            def __exit__(self, *exc):
                inside[0] = False
        real_write, real_remove = jus_ipc._write_atomic, os.remove

        def write(path, content):
            test.assertTrue(inside[0], path)
            real_write(path, content)

        def remove(path):
            test.assertTrue(inside[0], path)
            real_remove(path)
        with mock.patch.object(jus_ipc, "_write_atomic", write), mock.patch.object(jus_ipc.os, "remove", remove):
            c = IpcClient(self.dir, guard=Guard)
            cid = c.publish_command("status", {})
            self.ack(cid)
            c.wait_ack(cid, timeout=1)
            c.request_stop()
        self.assertFalse(os.path.exists(self.path("cmd", "pending.json")))


if __name__ == "__main__":
    unittest.main()
