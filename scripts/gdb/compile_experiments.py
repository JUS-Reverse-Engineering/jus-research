#!/usr/bin/env python3
"""Validate a batch-experiment spec and compile its persistent GDB session."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

EMU_DIR = Path(__file__).resolve().parents[1] / "emu"
sys.path.insert(0, str(EMU_DIR))
from jus_plan import validate_plan


class SpecError(ValueError):
    pass


def _hex(value, label):
    if not isinstance(value, str) or not value.lower().startswith("0x"):
        raise SpecError(f"{label} must be a hexadecimal string")
    try:
        return int(value, 0)
    except ValueError as exc:
        raise SpecError(f"{label} must be a hexadecimal string") from exc


def _symbol(probe_id):
    return re.sub(r"[^A-Za-z0-9_]", "_", probe_id)


def validate_spec(spec):
    if spec.get("schema_version") != 1:
        raise SpecError("schema_version must be 1")
    if not spec.get("session_id"):
        raise SpecError("session_id is required")
    gdb = spec.get("gdb", {})
    if not gdb.get("host") or not isinstance(gdb.get("port"), int):
        raise SpecError("gdb host and port are required")
    probes = spec.get("probes")
    if not isinstance(probes, list) or not probes:
        raise SpecError("at least one probe is required")
    seen = set()
    for probe in probes:
        probe_id = probe.get("id")
        if not probe_id:
            raise SpecError("every probe needs an id")
        if probe_id in seen:
            raise SpecError(f"duplicate probe id: {probe_id}")
        seen.add(probe_id)
        bp = probe.get("breakpoint", {})
        if not bp.get("overlay"):
            raise SpecError(f"{probe_id}: breakpoint overlay is required")
        _hex(bp.get("address"), f"{probe_id}: breakpoint address")
        if "condition" in bp and (not isinstance(bp["condition"], str) or not bp["condition"].strip()):
            raise SpecError(f"{probe_id}: breakpoint condition must be a non-empty string")
        timeout = probe.get("timeout_seconds")
        if timeout is not None and (not isinstance(timeout, (int, float)) or timeout <= 0):
            raise SpecError(f"{probe_id}: timeout_seconds must be positive")
        captures = probe.get("captures", {})
        registers = captures.get("registers")
        if not isinstance(registers, list) or not registers:
            raise SpecError(f"{probe_id}: captures.registers is required")
        if any(not isinstance(reg, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", reg) for reg in registers):
            raise SpecError(f"{probe_id}: invalid register capture")
        if not probe.get("savestate"):
            raise SpecError(f"{probe_id}: savestate is required")
        plan_path = Path(probe.get("lua_plan", ""))
        if not plan_path.is_file():
            raise SpecError(f"{probe_id}: lua_plan does not exist: {plan_path}")
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SpecError(f"{probe_id}: invalid lua_plan: {exc}") from exc
        if "load_state" in plan:
            raise SpecError(f"{probe_id}: lua_plan must not contain load_state")
        try:
            validate_plan(plan)
        except Exception as exc:
            raise SpecError(f"{probe_id}: invalid lua_plan: {exc}") from exc
        expected = probe.get("expected_hit", {})
        if not isinstance(expected.get("min"), int) or expected["min"] < 0:
            raise SpecError(f"{probe_id}: expected_hit.min must be non-negative")
        control = probe.get("positive_control")
        if not isinstance(control, dict):
            raise SpecError(f"{probe_id}: positive_control is required")
        if control.get("kind") == "memory_change":
            _hex(control.get("address"), f"{probe_id}: positive_control address")
            if not isinstance(control.get("length"), int) or control["length"] <= 0:
                raise SpecError(f"{probe_id}: positive_control length must be positive")
        elif control.get("kind") == "plan_watch_change":
            if not control.get("watch"):
                raise SpecError(f"{probe_id}: positive_control watch is required")
        else:
            raise SpecError(f"{probe_id}: unsupported positive_control kind")
    return spec


def compile_gdb(spec, log_path):
    validate_spec(spec)
    session_id = spec["session_id"]
    gdb = spec["gdb"]
    lines = [
        "set pagination off",
        "set confirm off",
        f"set logging file {log_path}",
        "set logging overwrite on",
        "set logging enabled on",
        "handle SIGILL stop nopass noprint",
        f'printf "JUS_SESSION_BEGIN {session_id}\\n"',
        f"target remote {gdb['host']}:{gdb['port']}",
    ]
    for probe in spec["probes"]:
        probe_id = probe["id"]
        symbol = _symbol(probe_id)
        registers = probe["captures"]["registers"]
        fmt = " ".join(f"{reg}=0x%x" for reg in registers)
        args = ", ".join(f"${reg}" for reg in registers)
        lines.extend([
            f"break *{probe['breakpoint']['address']}",
            f"set $jus_bp_{symbol} = $bpnum",
        ])
        if probe["breakpoint"].get("condition"):
            lines.append(f"condition $bpnum {probe['breakpoint']['condition']}")
        lines.extend([
            "commands $bpnum",
            "  silent",
            f'  printf "JUS_PROBE_HIT {probe_id} {fmt}\\n", {args}',
        ])
        for memory in probe["captures"].get("memory", []):
            address = _hex(memory["address"], f"{probe_id}: memory address")
            length = memory.get("length", 1)
            lines.append(f"  x/{length}bx 0x{address:08x}")
        lines.extend(["  continue", "end", "disable $bpnum"])
    for probe in spec["probes"]:
        probe_id = probe["id"]
        symbol = _symbol(probe_id)
        lines.extend([
            f"define jus-arm-{probe_id}",
            "  disable breakpoints",
            f"  enable $jus_bp_{symbol}",
            f'  printf "JUS_PROBE_BEGIN {probe_id}\\n"',
            "end",
            f"define jus-disarm-{probe_id}",
            f"  disable $jus_bp_{symbol}",
            f'  printf "JUS_PROBE_END {probe_id}\\n"',
            "end",
        ])
    lines.append(f'printf "JUS_SESSION_READY {session_id}\\n"')
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--log", default="gdb-experiments.log")
    args = parser.parse_args(argv)
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    args.output.write_text(compile_gdb(spec, args.log), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "probes": len(spec["probes"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
