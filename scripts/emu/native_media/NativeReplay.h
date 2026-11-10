#pragma once
#include <cstdint>
#include <stdexcept>
#include <utility>
#include <vector>

struct NativeWatch
{
    uint32_t address, length;
    std::vector<int32_t> offsets;
    int32_t offset = 0;
    bool optional = false;
};

struct NativeWatchValue
{
    bool present = true;
    uint32_t address = 0;
    std::vector<uint32_t> pointers, readAddresses;
    std::vector<uint8_t> bytes;
};

struct NativeReplayPlan
{
    uint32_t frames = 0;
    std::vector<uint32_t> masks;
    std::vector<NativeWatch> watches;

    static uint32_t reachable(int64_t address, uint32_t length, bool aligned = false)
    {
        if (address < 0x02000000 || address + length > 0x02400000
            || !length || (aligned && address % 4))
            throw std::invalid_argument("unreachable_watch");
        return uint32_t(address);
    }
    void validate() const
    {
        if (!frames || frames > 4096 || (!masks.empty() && masks.size() != frames))
            throw std::invalid_argument("invalid_schedule_length");
        for (auto mask : masks)
            if (mask > 4095) throw std::invalid_argument("invalid_key_mask");
        if (watches.size() > 64) throw std::invalid_argument("watch_budget");
        uint32_t bytes = 0;
        for (const auto& watch : watches)
        {
            if (!watch.length || watch.length > 512 || bytes + watch.length > 512
                || watch.offsets.size() > 8 || (watch.optional && watch.offsets.empty()))
                throw std::invalid_argument("invalid_watch_recipe");
            bytes += watch.length;
            reachable(watch.address, watch.offsets.empty() ? watch.length : 4, !watch.offsets.empty());
            if (watch.offsets.empty()) reachable(int64_t(watch.address) + watch.offset, watch.length);
        }
    }
    uint32_t mask(uint32_t sequence, uint32_t fallback) const
    {
        if (sequence >= frames) throw std::out_of_range("schedule_exhausted");
        return masks.empty() ? fallback : masks.at(sequence);
    }
    template <typename Read32, typename Read8>
    std::vector<NativeWatchValue> read(Read32 read32, Read8 read8) const
    {
        std::vector<NativeWatchValue> values;
        for (const auto& watch : watches)
        {
            NativeWatchValue value;
            int64_t address = watch.address;
            for (auto offset : watch.offsets)
            {
                auto location = reachable(address, 4, true);
                auto pointer = read32(location);
                value.readAddresses.push_back(location); value.pointers.push_back(pointer);
                if (!pointer)
                {
                    if (!watch.optional) throw std::invalid_argument("required_watch_absent");
                    value.present = false; break;
                }
                reachable(pointer, 1, true);
                address = int64_t(pointer) + offset;
            }
            value.bytes.resize(watch.length, 0);
            if (value.present)
            {
                value.address = reachable(address + watch.offset, watch.length);
                for (uint32_t i = 0; i < watch.length; ++i) value.bytes[i] = read8(value.address + i);
            }
            values.push_back(std::move(value));
        }
        return values;
    }
};
