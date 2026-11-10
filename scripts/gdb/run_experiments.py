#!/usr/bin/env python3
"""Run a compiled experiment batch with one emulator launch and one GDB attach."""

from __future__ import annotations

import argparse
import json
import os
import re
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

from compile_experiments import validate_spec


ROOT = Path(__file__).resolve().parents[2]
JUSEMU = ROOT / "scripts" / "emu" / "jusemu.py"
LAUNCH = ROOT / "scripts" / "emu" / "launch_emu.sh"


def classify_probe(probe, hits, plan_result, before, after, health):
    if health.get("state") not in {"alive", "idle", "paused"}:
        return {"status": "invalid", "outcome": "unhealthy_session"}
    if not plan_result.get("ok"):
        return {"status": "invalid", "outcome": "plan_failed"}
    if before is None or after is None or before == after:
        return {"status": "inconclusive", "outcome": "positive_control_missing"}
    minimum = probe["expected_hit"]["min"]
    if hits < minimum:
        return {"status": "valid", "outcome": "failed_expected_hit"}
    return {"status": "valid", "outcome": "passed" if hits else "admissible_zero_hit"}


def run_batch(spec, runtime, compiled_script):
    results = {"session_id": spec["session_id"], "probes": [], "resume_from": None}
    runtime.launch()
    attached = False
    try:
        for index, probe in enumerate(spec["probes"]):
            if index:
                runtime.resume()
            runtime.state_load(probe["savestate"])
            pre_health = runtime.health()
            control = probe["positive_control"]
            before = None if control["kind"] == "plan_watch_change" else runtime.read_control(control)
            if not attached:
                runtime.attach(compiled_script)
                attached = True
            else:
                runtime.interrupt()
            runtime.arm(probe["id"])
            runtime.resume()
            plan_result = runtime.run_plan(probe["lua_plan"], timeout=probe.get("timeout_seconds"))
            if control["kind"] == "plan_watch_change":
                before, after = runtime.read_plan_control(control, plan_result)
            else:
                after = runtime.read_control(control)
            post_health = runtime.health()
            runtime.interrupt()
            runtime.disarm(probe["id"])
            hits = runtime.hit_count(probe["id"])
            captures = runtime.captures(probe["id"])
            verdict = classify_probe(probe, hits, plan_result, before, after, post_health)
            results["probes"].append({
                "id": probe["id"],
                "hits": hits,
                "captures": captures,
                "control": {"before": before, "after": after},
                "health": {"before": pre_health, "after": post_health},
                "plan": plan_result,
                **verdict,
            })
    except Exception as exc:
        completed = {row["id"] for row in results["probes"]}
        for probe in spec["probes"]:
            if probe["id"] not in completed:
                results["probes"].append({"id": probe["id"], "status": "invalid", "outcome": f"aborted: {type(exc).__name__}: {exc}"})
        results["resume_from"] = next(row["id"] for row in results["probes"] if row["status"] == "invalid")
    finally:
        runtime.close()
    successful_outcomes = {"passed", "admissible_zero_hit"}
    results["passed"] = (
        len(results["probes"]) == len(spec["probes"])
        and all(row.get("status") == "valid" and row.get("outcome") in successful_outcomes for row in results["probes"])
    )
    if not results["passed"] and results["resume_from"] is None:
        results["resume_from"] = next(
            row["id"] for row in results["probes"]
            if row.get("status") != "valid" or row.get("outcome") not in successful_outcomes
        )
    return results


class GdbSession:
    def __init__(self, binary, script, timeout=20):
        self.process = subprocess.Popen(
            [binary, "-q", "-x", str(script)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )
        self.transcript = bytearray()
        self._wait_prompt(timeout)

    def _wait_prompt(self, timeout=20):
        start = len(self.transcript)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.process.stdout], [], [], min(0.25, deadline - time.monotonic()))
            if not ready:
                if self.process.poll() is not None:
                    raise RuntimeError(f"GDB exited early: {self.transcript.decode(errors='replace')}")
                continue
            chunk = os.read(self.process.stdout.fileno(), 4096)
            if not chunk:
                break
            self.transcript.extend(chunk)
            if has_prompt_since(self.transcript, start):
                return
        raise TimeoutError(f"GDB prompt timeout: {self.transcript[-4096:].decode(errors='replace')}")

    def command(self, command, wait=True):
        self.process.stdin.write((command + "\n").encode())
        self.process.stdin.flush()
        if wait:
            self._wait_prompt()

    def interrupt(self):
        self.process.send_signal(signal.SIGINT)
        self._wait_prompt()

    def close(self):
        if self.process.poll() is None:
            try:
                self.command("quit", wait=False)
                self.process.wait(timeout=5)
            except Exception:
                self.process.terminate()


def has_prompt_since(transcript, start):
    return b"(gdb)" in transcript[start:]


def parse_captures(log, probe_id):
    prefix = f"JUS_PROBE_HIT {probe_id} "
    captures = []
    for line in log.splitlines():
        if not line.startswith(prefix):
            continue
        captures.append(dict(re.findall(r"([A-Za-z][A-Za-z0-9_]*)=(0x[0-9A-Fa-f]+)", line[len(prefix):])))
    return captures


def _json_prefix(output):
    return json.JSONDecoder().raw_decode(output.lstrip())[0]


class ShellRuntime:
    def __init__(self, spec, gdb_binary, log_path, holder, *, launch=True):
        self.spec = spec
        self.gdb_binary = gdb_binary
        self.log_path = Path(log_path)
        self.holder = holder
        self.should_launch = launch
        self.gdb = None

    def _jusemu(self, *args):
        proc = subprocess.run([sys.executable, str(JUSEMU), *args], cwd=ROOT, text=True, capture_output=True, check=True)
        return _json_prefix(proc.stdout)

    def launch(self):
        if not self.should_launch:
            return
        env = os.environ.copy()
        env["JUS_EMU_HOLDER"] = self.holder
        subprocess.run(["bash", str(LAUNCH), "--keep-ipc"], cwd=ROOT, env=env, check=True)

    def state_load(self, slot):
        ack = self._jusemu("state", "load", slot)
        if not ack.get("ok"):
            raise RuntimeError(f"savestate load failed: {ack}")

    def health(self):
        return self._jusemu("status")

    def read_control(self, control):
        ack = self._jusemu("peek", control["address"], str(control["length"]))
        if not ack.get("ok"):
            raise RuntimeError(f"positive-control read failed: {ack}")
        return ack["result"]["value"]

    def read_plan_control(self, control, plan_result):
        log_path = Path(plan_result["result"]["log"])
        values = []
        for line in log_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            value = row.get("w", {}).get(control["watch"])
            if value is not None:
                values.append(value)
        if not values:
            return None, None
        first = values[0]
        changed = min(values)
        if changed == first:
            changed = max(values)
        return first, changed

    def attach(self, script):
        self.gdb = GdbSession(self.gdb_binary, script)

    def arm(self, probe_id):
        self.gdb.command(f"jus-arm-{probe_id}")

    def resume(self):
        self.gdb.command("continue", wait=False)

    def run_plan(self, plan, timeout=None):
        args = ["run", plan]
        if timeout is not None:
            args.extend(["--timeout", str(timeout)])
        return self._jusemu(*args)

    def interrupt(self):
        self.gdb.interrupt()

    def disarm(self, probe_id):
        self.gdb.command(f"jus-disarm-{probe_id}")

    def hit_count(self, probe_id):
        if not self.log_path.exists():
            return 0
        return self.log_path.read_text(errors="replace").count(f"JUS_PROBE_HIT {probe_id} ")

    def captures(self, probe_id):
        if not self.log_path.exists():
            return []
        return parse_captures(self.log_path.read_text(errors="replace"), probe_id)

    def close(self):
        if self.gdb is not None:
            self.gdb.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--compiled", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--gdb", default="arm-none-eabi-gdb")
    parser.add_argument("--holder", required=True)
    parser.add_argument("--no-launch", action="store_true")
    args = parser.parse_args(argv)
    spec = validate_spec(json.loads(args.spec.read_text(encoding="utf-8")))
    runtime = ShellRuntime(spec, args.gdb, args.log, args.holder, launch=not args.no_launch)
    result = run_batch(spec, runtime, args.compiled)
    args.results.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"results": str(args.results), "resume_from": result["resume_from"]}, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
