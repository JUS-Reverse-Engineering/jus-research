"""Fast, low-latency helper for jus-l77m timeout runs: one process, no
per-call subprocess spawn (each jusemu.py invocation costs real wall-clock
time, which the emulator free-runs through -- see scripts/emu/README.md
"Frame counting"). Import and reuse the client instead. The client is
jus_ipc.resident(), the one long-lived IpcClient per IPC dir that any script
can share; `batch` runs several ops as one command (one id, one ack).
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jus_ipc
from jus_plan import validate_plan, plan_to_lua

client = jus_ipc.resident()


def peek(addr, length):
    cid = client.next_id()
    client.publish_command("peek", {"addr": addr, "len": length}, cmd_id=cid)
    ack = client.wait_ack(cid, timeout=10.0)
    return ack["result"]["value"]


def poke(addr, byte_list):
    cid = client.next_id()
    client.publish_command("poke", {"addr": addr, "bytes": byte_list}, cmd_id=cid)
    return client.wait_ack(cid, timeout=10.0)


def poke_u16(addr, value):
    return poke(addr, [value & 0xFF, (value >> 8) & 0xFF])


def poke_u32(addr, value):
    return poke(addr, [value & 0xFF, (value >> 8) & 0xFF,
                        (value >> 16) & 0xFF, (value >> 24) & 0xFF])


def state_load(slot):
    return client.state_load(slot, timeout=30.0)   # a failed ack carries `inspection` and `hint`


def batch(steps, timeout=15.0):
    """steps = [{"op": "poke", "args": {...}}, ...]; see jus_ipc.IpcClient.batch."""
    return client.batch(steps, timeout=timeout)


def run_plan(plan_dict, timeout=30.0):
    plan = validate_plan(plan_dict)
    cid = client.next_id()
    rd = os.path.join(client.dir, "runs", "%s-%d-%s" % (plan["name"], cid, client.epoch))
    os.makedirs(rd, exist_ok=True)
    lua_path = os.path.join(rd, "plan.lua")
    with open(lua_path, "w") as f:
        f.write(plan_to_lua(plan))
    client.publish_command("run_plan", {"plan_path": lua_path, "run_dir": rd}, cmd_id=cid)
    return client.wait_ack(cid, timeout=timeout)


if __name__ == "__main__":
    print(json.dumps({"framecount": "n/a - use peek/poke/run_plan"}))
