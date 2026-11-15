-- scripts/emu/tests/test_agent_bridge_wiring.lua
-- Drives the real agent_bridge.lua against stub emulator globals (no melonDS): checks that `batch` is wired
-- through the one epoch guard and the one ack. Run from the repo root with JUS_EMU_DIR pointing at an empty
-- temp dir: JUS_EMU_DIR=$(mktemp -d) JUS_EMU_SRC=scripts/emu lua scripts/emu/tests/test_agent_bridge_wiring.lua
local dir = assert(os.getenv("JUS_EMU_DIR"), "set JUS_EMU_DIR to a temp dir")
assert(dir ~= "/tmp/jus_emu", "refusing the live IPC dir")
local passed, failed = 0, 0
local function check(cond, msg)
    if cond then passed = passed + 1 else failed = failed + 1; print("FAIL: " .. msg) end
end

local fc = 1000
local writes, loads = {}, 0
emu = { framecount = function() return fc end }
joypad = { set = function() end }
input = { NDSTapUp = function() end, NDSTapDown = function() end }
savestate = { load = function() loads = loads + 1 end, save = function() end }
screen = { dump = function() return true end }
memory = {
    read_u8 = function() return 0 end, read_u16_le = function() return 0 end,
    read_u32_le = function(a) return a end,
    read_bytes_as_array = function(_, n) local t = {} for i = 1, n do t[i] = 0 end return t end,
    write_bytes_as_array = function(a, b) writes[#writes + 1] = { a, #b } end,
}

capture = { start = function() return true, 5 end, stop = function() return true, 6 end }
dofile((os.getenv("JUS_EMU_SRC") or "scripts/emu") .. "/agent_bridge.lua")

local function slurp(path)
    local f = io.open(path, "r"); if not f then return nil end
    local s = f:read("a"); f:close(); return s
end
local session = slurp(dir .. "/heartbeat.json"):match('"session":"([^"]+)"')
check(session ~= nil, "bridge wrote a heartbeat with a session")

local next_id = 100
local function send(op, args_lua, epoch)
    next_id = next_id + 1
    local f = assert(io.open(dir .. "/cmd/inbox.lua", "w"))
    f:write(string.format('return {epoch=%q, id=%d, op=%q, args=%s}', epoch or session, next_id, op, args_lua))
    f:close()
    for _ = 1, 10 do _Update() end            -- POLL_INTERVAL ticks: one poll
    return next_id, slurp(dir .. "/ack/" .. next_id .. ".json")
end
local function ack_count()
    local n = 0
    for _ in io.popen('ls "' .. dir .. '/ack"'):lines() do n = n + 1 end
    return n
end

-- ok batch: one id, one ack, per-step results
local id, ack = send("batch", '{steps={{op="poke",args={addr=0x02000010,bytes={1,2,3}}},{op="status",args={}}}}')
check(ack and ack:find('"ok":true', 1, true), "batch ok ack: " .. tostring(ack))
check(ack and ack:find('"completed":2', 1, true), "both steps completed")
check(ack and ack:find('"written":3', 1, true), "poke result inside the batch ack")
check(ack and ack:find('"op":"status"', 1, true), "status step result present")
check(#writes == 1, "poke ran once")
check(ack_count() == 1, "exactly one ack for the whole batch")

-- mid-batch failure: results so far plus the failing index; later steps never run
writes = {}
id, ack = send("batch", '{steps={{op="poke",args={addr=0x02000010,bytes={9}}},{op="tail_stop",args={}},{op="poke",args={addr=0x02000020,bytes={9}}}}}')
check(ack and ack:find('"ok":false', 1, true), "failing batch acks ok=false")
check(ack and ack:find('"failed_index":1', 1, true), "failed index reported")
check(ack and ack:find('"completed":1', 1, true), "one step completed before the failure")
check(ack and ack:find("no tail running", 1, true), "error names the failing step's cause")
check(#writes == 1, "step after the failure did not run")

-- refused ops: nothing runs, state_load never reaches savestate.load
writes = {}
id, ack = send("batch", '{steps={{op="poke",args={addr=0x02000010,bytes={9}}},{op="state_load",args={slot="x"}}}}')
check(ack and ack:find('"ok":false', 1, true), "batch with state_load refused")
check(ack and ack:find("not allowed in a batch", 1, true), "refusal text")
check(#writes == 0 and loads == 0, "refused batch ran nothing")
id, ack = send("batch", '{steps={{op="run_plan",args={}}}}')
check(ack and ack:find("not allowed in a batch", 1, true), "run_plan refused in a batch")

-- epoch guard: a stale epoch is rejected once for the whole batch
writes = {}
id, ack = send("batch", '{steps={{op="poke",args={addr=0x02000010,bytes={9}}}}}', "old-epoch")
check(ack and ack:find("stale epoch", 1, true), "stale epoch refuses the batch")
check(#writes == 0, "stale batch ran nothing")

-- empty batch
id, ack = send("batch", '{steps={}}')
check(ack and ack:find('"ok":true', 1, true) and ack:find('"results":[]', 1, true), "empty batch ok: " .. tostring(ack))

-- an existing op is untouched
id, ack = send("status", '{}')
check(ack and ack:find('"ok":true', 1, true) and ack:find('"state":"idle"', 1, true), "plain status still works")

-- native capture lock: a locked bridge refuses batches (even status-only) and a start step locks the steps after it
local id2, a2
writes = {}
id2, a2 = send("native_capture_start", '{path="/tmp/x"}')
check(a2 and a2:find('"ok":true',1,true), "nc start ok: "..tostring(a2))
id2, a2 = send("batch", '{steps={{op="poke",args={addr=0x02000010,bytes={9}}}}}')
check(a2 and a2:find("native capture locks", 1, true), "batch refused while locked: "..tostring(a2))
check(#writes == 0, "locked batch ran nothing")
id2, a2 = send("batch", '{steps={{op="status",args={}}}}')
check(a2 and a2:find('"ok":false',1,true), "batch (even status-only) refused while locked")
id2, a2 = send("native_capture_stop", '{}')
check(a2 and a2:find('"ok":true',1,true), "nc stop ok: "..tostring(a2))
writes = {}
id2, a2 = send("batch", '{steps={{op="native_capture_start",args={path="/tmp/y"}},{op="poke",args={addr=0x02000010,bytes={9}}}}}')
check(a2 and a2:find('"failed_index":1',1,true), "start step locks later step: "..tostring(a2))
check(#writes == 0, "poke after lock did not run")
send("native_capture_stop", '{}')

print(string.format("passed=%d failed=%d", passed, failed))
os.exit(failed == 0 and 0 or 1)
