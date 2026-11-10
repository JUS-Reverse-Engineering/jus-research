import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from run_experiments import classify_probe, has_prompt_since, main, parse_captures, run_batch


def probe(probe_id="p1", minimum=1):
    return {
        "id": probe_id,
        "savestate": "fight_base",
        "lua_plan": "plan.json",
        "expected_hit": {"min": minimum},
        "positive_control": {"kind": "memory_change", "address": "0x021df7f0", "length": 2},
    }


class FakeRuntime:
    def __init__(self, *, fail_on=None):
        self.events = []
        self.fail_on = fail_on
        self.reads = iter([100, 90, 90, 80])

    def _event(self, name, *args):
        self.events.append((name,) + args)
        if self.fail_on == name:
            raise RuntimeError("boom")

    def launch(self): self._event("launch")
    def state_load(self, slot): self._event("state_load", slot)
    def health(self): self._event("health"); return {"state": "alive"}
    def read_control(self, control):
        if control["kind"] == "plan_watch_change":
            raise AssertionError("plan watches are read from the completed plan log")
        self._event("read_control"); return next(self.reads)
    def read_plan_control(self, control, plan_result):
        self._event("read_plan_control", control["watch"])
        return 100, 90
    def attach(self, script): self._event("attach", script)
    def arm(self, probe_id): self._event("arm", probe_id)
    def resume(self): self._event("resume")
    def run_plan(self, plan, timeout=None): self._event("run_plan", plan, timeout); return {"ok": True}
    def interrupt(self): self._event("interrupt")
    def disarm(self, probe_id): self._event("disarm", probe_id)
    def hit_count(self, probe_id): self._event("hit_count", probe_id); return 1
    def captures(self, probe_id): self._event("captures", probe_id); return [{"r1": "0xfffffe80", "lr": "0x0215ac74"}]
    def close(self): self._event("close")


class SupervisorTests(unittest.TestCase):
    def test_cli_requires_explicit_holder(self):
        argv = [
            "missing-spec.json",
            "--compiled", "compiled.gdb",
            "--results", "results.json",
            "--log", "session.log",
        ]
        try:
            main(argv)
        except SystemExit as exc:
            self.assertEqual(exc.code, 2)
        except FileNotFoundError:
            self.fail("CLI used a shared default holder and tried to read the spec")

    def test_prompt_detection_ignores_old_prompt(self):
        old = b"(gdb) old prompt\n"
        transcript = old + b"JUS_PROBE_HIT p1\n"
        self.assertFalse(has_prompt_since(transcript, len(old)))
        self.assertTrue(has_prompt_since(transcript + b"(gdb) ", len(old)))

    def test_capture_parser_keeps_register_values_by_probe(self):
        log = "JUS_PROBE_HIT p1 r1=0xfffffe80 lr=0x215ac74\nJUS_PROBE_HIT p2 r1=0x1 lr=0x2\n"
        self.assertEqual(parse_captures(log, "p1"), [{"r1": "0xfffffe80", "lr": "0x215ac74"}])

    def test_one_attach_and_standalone_load_before_each_probe(self):
        runtime = FakeRuntime()
        first = probe()
        first["timeout_seconds"] = 180
        spec = {"session_id": "s", "probes": [first, probe("p2")]}

        result = run_batch(spec, runtime, "compiled.gdb")

        names = [event[0] for event in runtime.events]
        self.assertEqual(names.count("launch"), 1)
        self.assertEqual(names.count("attach"), 1)
        self.assertEqual(names.count("state_load"), 2)
        self.assertLess(names.index("state_load"), names.index("attach"))
        second_load = names.index("state_load", names.index("state_load") + 1)
        self.assertLess(names.index("resume", names.index("disarm") + 1), second_load)
        self.assertEqual([row["status"] for row in result["probes"]], ["valid", "valid"])
        self.assertTrue(result["passed"])
        self.assertIn(("run_plan", "plan.json", 180), runtime.events)
        self.assertEqual(result["probes"][0]["captures"][0]["r1"], "0xfffffe80")

    def test_control_is_required_for_zero_hit_or_positive_hit(self):
        healthy = {"state": "alive"}
        self.assertEqual(classify_probe(probe(minimum=0), 0, {"ok": True}, 100, 90, healthy)["status"], "valid")
        self.assertEqual(classify_probe(probe(minimum=1), 1, {"ok": True}, 100, 90, {"state": "idle"})["status"], "valid")
        self.assertEqual(classify_probe(probe(minimum=0), 0, {"ok": True}, 100, 100, healthy)["status"], "inconclusive")
        failed = classify_probe(probe(minimum=1), 0, {"ok": True}, 100, 90, healthy)
        self.assertEqual((failed["status"], failed["outcome"]), ("valid", "failed_expected_hit"))

    def test_failure_preserves_completed_probe_and_invalidates_rest(self):
        runtime = FakeRuntime(fail_on="run_plan")
        spec = {"session_id": "s", "probes": [probe(), probe("p2")]}
        result = run_batch(spec, runtime, "compiled.gdb")
        self.assertEqual([row["status"] for row in result["probes"]], ["invalid", "invalid"])
        self.assertEqual(result["resume_from"], "p1")

    def test_inconclusive_probe_makes_batch_fail(self):
        runtime = FakeRuntime()
        runtime.reads = iter([100, 100])
        result = run_batch({"session_id": "s", "probes": [probe()]}, runtime, "compiled.gdb")
        self.assertFalse(result["passed"])
        self.assertEqual(result["resume_from"], "p1")

    def test_plan_watch_control_accepts_a_transient_change(self):
        runtime = FakeRuntime()
        row = probe()
        row["positive_control"] = {"kind": "plan_watch_change", "watch": "hp_all.o1"}
        result = run_batch({"session_id": "s", "probes": [row]}, runtime, "compiled.gdb")
        self.assertTrue(result["passed"])
        self.assertIn(("read_plan_control", "hp_all.o1"), runtime.events)


if __name__ == "__main__":
    unittest.main()
