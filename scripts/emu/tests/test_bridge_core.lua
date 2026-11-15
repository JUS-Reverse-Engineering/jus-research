-- scripts/emu/tests/test_bridge_core.lua
-- Run: lua scripts/emu/tests/test_bridge_core.lua  (from repo root; mise provides Lua 5.4 as `lua`)
package.path = "scripts/emu/?.lua;" .. package.path
local core = require("bridge_core")
local passed, failed = 0, 0
local function eq(a, b, msg)
    if a == b then passed = passed + 1
    else failed = failed + 1; print("FAIL: " .. msg ..
         " expected=" .. tostring(b) .. " got=" .. tostring(a)) end
end

-- jenc: canonical (sorted keys), NULL sentinel, empty-object support
eq(core.jenc({b = 1, a = 2}), '{"a":2,"b":1}', "sorted keys")
eq(core.jenc({1, 2, 3}), "[1,2,3]", "array")
eq(core.jenc(core.NULL), "null", "null sentinel")
eq(core.jenc(core.obj({})), "{}", "empty object not array")
eq(core.jenc({x = core.NULL}), '{"x":null}', "null value kept")
eq(core.jenc('a"\n'), '"a\\"\\n"', "string escaping")
eq(core.jenc("\1"), '"\\u0001"', "control char escaping")
eq(core.jenc(3), "3", "integer stays integral")

-- segment lookup: gaps are force-neutral, not release
local plan = { segments = {
    { ["from"] = 0, ["to"] = 2, buttons = {"Right"} },
    { ["from"] = 5, ["to"] = 6, buttons = {"B"}, touch = nil },
  }, total_frames = 10 }
local m = core.mask_for_frame(plan, 1)
eq(m.buttons.Right, true, "in-segment button")
m = core.mask_for_frame(plan, 3)
eq(next(m.buttons), nil, "gap = empty pressed set")
eq(m.neutral_override, true, "gap keeps override active")
m = core.mask_for_frame(plan, 9)
eq(m.neutral_override, true, "tail keeps override active")

-- pressed list in fixed canonical order
local pl = core.pressed_list({ B = true, A = true, Right = true })
eq(table.concat(pl, ","), "A,B,Right", "canonical button order")

-- plan machine: init -> running -> done, with per-frame records
local pm = core.new_plan_machine(plan, { }, 0)
local rec
for i = 1, 10 do rec = pm:step(function() return {} end) end
eq(pm.state, "done", "plan machine completes")
eq(rec.f, 9, "last frame index")

-- watch values land in the record, nil becomes the NULL sentinel
local pm2 = core.new_plan_machine(plan, { { name = "hp", len = 1 },
                                          { name = "bad", len = 1 } }, 0)
local rec2 = pm2:step(function(spec)
    if spec.name == "hp" then return 40 end
    return nil
end)
eq(rec2.w.hp, 40, "watch value recorded")
eq(rec2.w.bad, core.NULL, "failed watch read becomes NULL")
eq(core.jenc(rec2.w), '{"bad":null,"hp":40}', "watch table encodes canonically")

-- settle machine: settles when framecount hits the sidecar target
local sm = core.new_settle_machine(1000, 60)   -- target fc, max wait
eq(sm:step(1500), "waiting", "not settled at other fc")
eq(sm:step(1000), "settled", "settled at target fc")
local sm2 = core.new_settle_machine(1000, 2)
sm2:step(1500)
eq(sm2:step(1501), "timeout", "settle timeout")

-- batch: pure logic. One call runs every step; failure stops it and keeps the partial results.
local function mk_handlers(log)
    return {
        peek = function(a) log[#log+1] = "peek"; return core.obj({ value = a.addr }) end,
        poke = function(a) log[#log+1] = "poke"; return core.obj({ written = #a.bytes }) end,
        boom = function(a) log[#log+1] = "boom"; error("kaboom") end,
    }
end
local log = {}
local ok, err, det = core.run_batch({ { op = "poke", args = { bytes = {1, 2} } },
                                      { op = "peek", args = { addr = 7 } } },
                                    mk_handlers(log), function() return true end)
eq(ok, true, "batch ok")
eq(err, nil, "batch ok has no error")
eq(table.concat(log, ","), "poke,peek", "steps run in order")
eq(det.completed, 2, "batch completed count")
eq(det.failed_index, core.NULL, "no failed index on success")
eq(det.results[1].ok, true, "step 0 ok")
eq(det.results[2].result.value, 7, "step 1 result carried")
eq(core.jenc(det.results[1]), '{"ok":true,"op":"poke","result":{"written":2}}', "step encodes canonically")

log = {}
ok, err, det = core.run_batch({ { op = "peek", args = { addr = 1 } }, { op = "boom" },
                                { op = "peek", args = { addr = 2 } } },
                              mk_handlers(log), function() return true end)
eq(ok, false, "mid-batch failure fails the batch")
eq(table.concat(log, ","), "peek,boom", "steps after the failure never run")
eq(det.failed_index, 1, "failed index is 0-based")
eq(det.completed, 1, "completed counts only the steps before the failure")
eq(#det.results, 2, "results so far include the failing step")
eq(det.results[2].ok, false, "failing step marked failed")
eq(err:find("kaboom", 1, true) ~= nil, true, "error names the cause")
eq(err:find("step 1", 1, true) ~= nil, true, "error names the step index")

for _, bad in ipairs({ "run_plan", "state_load", "state_save", "batch" }) do
    log = {}
    ok, err, det = core.run_batch({ { op = "peek", args = { addr = 1 } }, { op = bad, args = {} } },
                                  mk_handlers(log), function() return true end)
    eq(ok, false, "refused op " .. bad)
    eq(#log, 0, "refused batch runs nothing (" .. bad .. ")")
    eq(det.failed_index, 1, "refused index (" .. bad .. ")")
    eq(det.completed, 0, "refused completed (" .. bad .. ")")
    eq(err:find("not allowed in a batch", 1, true) ~= nil, true, "clear refusal (" .. bad .. ")")
end

log = {}
ok, err, det = core.run_batch({ { op = "nope" } }, mk_handlers(log), function() return true end)
eq(ok, false, "unknown op refused up front")
eq(err:find("unknown op", 1, true) ~= nil, true, "unknown op named")

ok, err, det = core.run_batch({}, mk_handlers({}), function() return true end)
eq(ok, true, "empty batch is ok")
eq(det.completed, 0, "empty batch completed 0")
eq(core.jenc(det.results), "[]", "empty batch results encode as []")

ok, err = core.run_batch("x", mk_handlers({}), function() return true end)
eq(ok, false, "non-list steps rejected")
ok, err = core.run_batch({ { args = {} } }, mk_handlers({}), function() return true end)
eq(ok, false, "step without op rejected")

-- up-front refusals: nothing runs, so completed is 0; failed_index is 0-based
log = {}
ok, err, det = core.run_batch({ { args = {} } }, mk_handlers(log), function() return true end)
eq(det.failed_index, 0, "missing op: failed index (0-based)")
eq(det.completed, 0, "missing op: completed 0")
eq(#log, 0, "missing op: nothing ran")

log = {}
ok, err, det = core.run_batch({ { op = "peek", args = { addr = 1 } }, { op = "nope" } },
                              mk_handlers(log), function() return true end)
eq(ok, false, "unknown op after a valid step refused")
eq(det.failed_index, 1, "unknown op: failed index (0-based)")
eq(det.completed, 0, "unknown op: refused up front, completed 0")
eq(#log, 0, "unknown op: the valid step before it did not run")
eq(err:find("step 1 (nope): unknown op", 1, true) ~= nil, true, "unknown op named at its index")

log = {}
ok, err, det = core.run_batch({ { op = "peek", args = "not a table" } }, mk_handlers(log), function() return true end)
eq(ok, false, "non-table args refused")
eq(det.failed_index, 0, "non-table args: failed index (0-based)")
eq(det.completed, 0, "non-table args: completed 0")
eq(#log, 0, "non-table args: nothing ran")
local many = {}
for i = 1, core.BATCH_MAX + 1 do many[i] = { op = "peek", args = { addr = i } } end
ok, err = core.run_batch(many, mk_handlers({}), function() return true end)
eq(ok, false, "oversized batch rejected")

-- the per-step guard: a step that locks the bridge stops the steps after it
local locked = false
local h = mk_handlers({})
h.lock = function() locked = true; return core.obj({}) end
ok, err, det = core.run_batch({ { op = "lock" }, { op = "poke", args = { bytes = {1} } } }, h,
                              function(op) return not locked or op == "status" end)
eq(ok, false, "guard re-checked per step")
eq(det.failed_index, 1, "guard failure index")

print(string.format("passed=%d failed=%d", passed, failed))
os.exit(failed == 0 and 0 or 1)
