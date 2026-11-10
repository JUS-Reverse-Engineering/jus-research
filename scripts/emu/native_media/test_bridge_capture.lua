package.path = 'scripts/emu/?.lua;' .. package.path
local native = require('native_capture')
local calls = {}
local api = {
    start = function(path, watches, frames, state)
        assert(path == '/tmp/new-native-session')
        assert(watches[1].address == 0x02100000 and watches[1].length == 2)
        assert(frames == 8)
        assert(state == "/tmp/jus_emu/states/prepared.mln")
        calls[#calls+1] = 'start'
        return true, 150
    end,
    stop = function() calls[#calls+1] = 'stop'; return true, 158 end,
}
local pad = {}
local h = native.new(api, function(v) return v end, function(v) pad[#pad+1] = v or "released" end)
assert(h.allow('poke'))
local result = h.start({path='/tmp/new-native-session',watches={{address=0x02100000,length=2}},frames=8,buttons={Down=true},state="/tmp/jus_emu/states/prepared.mln"})
assert(result.boundary_frame == 150)
assert(pad[1] and pad[1].Down == true)
assert(not h.allow('poke') and not h.allow('state_load') and not h.allow('run_plan'))
assert(h.allow('status') and h.allow('native_capture_stop'))
local stopped = h.stop({})
assert(stopped.boundary_frame == 158 and h.allow('poke'))
assert(table.concat(calls,',') == 'start,stop')
assert(pad[2] == 'released')
local failed = native.new({start=function() return false, 'renderer' end},function(v) return v end,function() end)
local ok, why = pcall(failed.start,{path='x',watches={},frames=1})
assert(not ok and tostring(why):find('renderer') and failed.allow('poke'))
local missing = native.new(nil,function(v) return v end)
assert(not pcall(missing.start,{path='x',watches={},frames=1}))
local cleanup = {}
local throwing = native.new({start=function() error('invalid watches') end},function(v) return v end,
    function(v) cleanup[#cleanup+1] = v or 'released' end)
assert(not pcall(throwing.start,{path='x',watches={},frames=1,buttons={Down=true}}))
assert(cleanup[2] == 'released' and throwing.allow('poke'))
local timeline = {4095,3967,4095}
local scheduled = native.new({start=function(path,watches,frames,state,masks)
    assert(frames == 3 and masks == timeline)
    return true, 77
end},function(v) return v end,function() end)
assert(scheduled.start({path='timeline',watches={},frames=3,masks=timeline}).boundary_frame == 77)
local hooked, starts = {}, 0
local hooking = native.new({start=function(path,watches,frames,state,masks,hooks)
    starts = starts + 1; hooked[starts] = hooks
    return true, 5
end},function(v) return v end,function() end)
assert(hooking.start({path='plain',watches={},frames=1}).boundary_frame == 5)
assert(hooked[1] == nil)
local lists = {{address=0x021729EC,offsets={0},next=0,limit=16,fields={{path={0x18},length=2}}}}
local hooking2 = native.new({start=function(path,watches,frames,state,masks,hooks)
    starts = starts + 1; hooked[starts] = hooks
    return true, 6
end},function(v) return v end,function() end)
assert(hooking2.start({path='hooked',watches={},frames=1,calls={0x0206C7FC},lists=lists}).boundary_frame == 6)
assert(hooked[2].calls[1] == 0x0206C7FC and hooked[2].lists == lists)
local hooking3 = native.new({start=function(path,watches,frames,state,masks,hooks)
    starts = starts + 1; hooked[starts] = hooks
    return true, 7
end},function(v) return v end,function() end)
assert(hooking3.start({path='gpu',watches={},frames=1,gpu=1}).boundary_frame == 7)
assert(hooked[3].gpu == 1 and hooked[3].calls == nil and hooked[3].lists == nil)
print('Native bridge command checks passed')
