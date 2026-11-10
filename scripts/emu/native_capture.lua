local M = {}
function M.new(api, obj, pad)
    local locked = false
    return {
        allow = function(op)
            return not locked or op == 'status' or op == 'native_capture_stop'
        end,
        start = function(args)
            if not api or not api.start then error('native capture unavailable in this build') end
            pad(args.buttons or {})
            local hooks = nil
            if args.calls or args.lists or args.gpu then hooks = {calls=args.calls, lists=args.lists, gpu=args.gpu} end
            local called, ok, boundary = pcall(api.start, args.path, args.watches, args.frames, args.state, args.masks, hooks)
            if not called or not ok then
                pad(nil)
                error('native capture failed: ' .. tostring(called and boundary or ok))
            end
            locked = true
            return obj({path=args.path, boundary_frame=boundary})
        end,
        stop = function()
            if not api or not api.stop then error('native capture unavailable in this build') end
            local ok, boundary = api.stop()
            if not ok then error('native stop failed: ' .. tostring(boundary)) end
            locked = false
            pad(nil)
            return obj({boundary_frame=boundary})
        end,
    }
end
return M
