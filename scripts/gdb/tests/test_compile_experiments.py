import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from compile_experiments import SpecError, compile_gdb, validate_spec


def specimen(plan):
    return {
        "schema_version": 1,
        "session_id": "hp-delta-dry-run",
        "gdb": {"host": "localhost", "port": 3333},
        "probes": [{
            "id": "hp-delta-apply",
            "name": "HP delta apply known-positive",
            "breakpoint": {"overlay": "arm9", "address": "0x02078488"},
            "captures": {"registers": ["r1", "lr"], "memory": []},
            "savestate": "fight_base",
            "lua_plan": str(plan),
            "expected_hit": {"min": 1},
            "positive_control": {
                "kind": "memory_change",
                "address": "0x021df7f0",
                "length": 2,
            },
        }],
    }


class CompileExperimentTests(unittest.TestCase):
    def test_validation_requires_overlay_address_control_and_unique_id(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / "plan.json"
            plan.write_text('{"name":"p","segments":[{"from":0,"to":0,"buttons":[]}],"tail_frames":1}', encoding="utf-8")
            spec = specimen(plan)
            del spec["probes"][0]["breakpoint"]["overlay"]
            with self.assertRaisesRegex(SpecError, "overlay"):
                validate_spec(spec)

            spec = specimen(plan)
            spec["probes"].append(dict(spec["probes"][0]))
            with self.assertRaisesRegex(SpecError, "duplicate"):
                validate_spec(spec)

            spec = specimen(plan)
            del spec["probes"][0]["positive_control"]
            with self.assertRaisesRegex(SpecError, "positive_control"):
                validate_spec(spec)

    def test_validation_rejects_plan_embedded_state_load(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / "plan.json"
            plan.write_text(json.dumps({"name": "p", "segments": [{"from": 0, "to": 0, "buttons": []}], "load_state": "fight_base"}), encoding="utf-8")
            with self.assertRaisesRegex(SpecError, "load_state"):
                validate_spec(specimen(plan))

    def test_validation_uses_the_lua_plan_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / "plan.json"
            plan.write_text(json.dumps({
                "name": "p",
                "segments": [
                    {"from": 0, "to": 10, "buttons": ["B"]},
                    {"from": 5, "to": 12, "buttons": ["B"]},
                ],
                "tail_frames": 1,
            }), encoding="utf-8")
            with self.assertRaisesRegex(SpecError, "lua_plan"):
                validate_spec(specimen(plan))

    def test_validation_accepts_plan_watch_positive_control(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / "plan.json"
            plan.write_text('{"name":"p","segments":[{"from":0,"to":0,"buttons":[]}],"tail_frames":1}', encoding="utf-8")
            spec = specimen(plan)
            spec["probes"][0]["positive_control"] = {"kind": "plan_watch_change", "watch": "hp_all.o1"}
            self.assertIs(validate_spec(spec), spec)

    def test_compiler_emits_one_attach_isolated_breakpoints_and_continue(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / "plan.json"
            plan.write_text('{"name":"p","segments":[{"from":0,"to":0,"buttons":[]}],"tail_frames":1}', encoding="utf-8")
            spec = specimen(plan)
            second = dict(spec["probes"][0])
            second.update({"id": "second", "name": "second", "breakpoint": {"overlay": "ov6", "address": "0x02150000"}})
            spec["probes"].append(second)

            script = compile_gdb(spec, log_path="session.log")

            self.assertEqual(script.count("target remote localhost:3333"), 1)
            self.assertIn("handle SIGILL stop nopass noprint", script)
            self.assertIn("JUS_SESSION_BEGIN hp-delta-dry-run", script)
            self.assertIn("JUS_PROBE_HIT hp-delta-apply", script)
            self.assertIn("r1=0x%x lr=0x%x", script)
            self.assertEqual(script.count("disable $bpnum"), 2)
            command_blocks = script.split("commands $bpnum")[1:]
            self.assertTrue(all("\n  continue\nend" in block for block in command_blocks))
            self.assertIn("define jus-arm-hp-delta-apply", script)
            self.assertIn("disable breakpoints\n  enable $jus_bp_hp_delta_apply", script)

    def test_compiler_emits_optional_breakpoint_condition(self):
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / "plan.json"
            plan.write_text('{"name":"p","segments":[{"from":0,"to":0,"buttons":[]}],"tail_frames":1}', encoding="utf-8")
            spec = specimen(plan)
            spec["probes"][0]["breakpoint"]["condition"] = "$r1 < 0"
            spec["probes"][0]["timeout_seconds"] = 180
            script = compile_gdb(spec, log_path="session.log")
            self.assertIn("condition $bpnum $r1 < 0", script)


if __name__ == "__main__":
    unittest.main()
