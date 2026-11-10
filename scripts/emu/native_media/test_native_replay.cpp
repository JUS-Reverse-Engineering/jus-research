#include "NativeReplay.h"
#include <cassert>
#include <functional>
#include <iostream>

int main()
{
    auto rejects = [](const std::function<void()>& fn) {
        bool failed = false;
        try { fn(); } catch (const std::exception&) { failed = true; }
        assert(failed);
    };
    NativeReplayPlan plan;
    plan.frames = 6;
    plan.masks = {4095, 3967, 3967, 4095, 4093, 4095};
    plan.validate();
    for (uint32_t i = 0; i < plan.frames; ++i) assert(plan.mask(i, 123) == plan.masks[i]);
    rejects([&] { plan.mask(6, 123); });
    auto bad = plan; bad.masks.pop_back(); rejects([&] { bad.validate(); });
    bad = plan; bad.masks[0] = 4096; rejects([&] { bad.validate(); });
    bad = plan; bad.frames = 0; rejects([&] { bad.validate(); });
    bad = plan; bad.frames = 4097; rejects([&] { bad.validate(); });
    plan.masks.clear(); assert(plan.mask(2, 3967) == 3967);

    std::vector<uint8_t> ram(0x400000);
    auto write32 = [&](uint32_t addr, uint32_t value) {
        for (unsigned i = 0; i < 4; ++i) ram.at(addr - 0x02000000 + i) = uint8_t(value >> (8 * i));
    };
    auto read8 = [&](uint32_t addr) { return ram.at(addr - 0x02000000); };
    auto read32 = [&](uint32_t addr) {
        uint32_t value = 0;
        for (unsigned i = 0; i < 4; ++i) value |= uint32_t(read8(addr + i)) << (8 * i);
        return value;
    };
    NativeWatch watch{0x02000020, 2, {4, 8}, 2, true};
    plan.watches = {watch}; plan.validate();
    write32(0x02000020, 0x02000100); write32(0x02000104, 0x02001000);
    ram.at(0x100A) = 0xAB; ram.at(0x100B) = 0xCD;
    auto values = plan.read(read32, read8);
    assert(values[0].present && values[0].address == 0x0200100A);
    assert((values[0].pointers == std::vector<uint32_t>{0x02000100, 0x02001000}));
    assert((values[0].bytes == std::vector<uint8_t>{0xAB, 0xCD}));
    write32(0x02000104, 0x02002000); ram.at(0x200A) = 7;
    assert(plan.read(read32, read8)[0].bytes[0] == 7);
    write32(0x02000104, 0);
    values = plan.read(read32, read8);
    assert(!values[0].present && values[0].address == 0);
    assert((values[0].bytes == std::vector<uint8_t>{0, 0}));
    assert(values[0].pointers.back() == 0);
    plan.watches[0].optional = false; rejects([&] { plan.read(read32, read8); });
    plan.watches[0].optional = true;
    for (uint32_t ptr : {0x01000000u, 0x02400000u, 0x02001001u, 0xFFFFFFFCu}) {
        write32(0x02000104, ptr); rejects([&] { plan.read(read32, read8); });
    }
    write32(0x02000104, 0x023FFFFC); rejects([&] { plan.read(read32, read8); });
    bad = plan; bad.watches[0].offsets.assign(9, 0); rejects([&] { bad.validate(); });
    bad = plan; bad.watches[0].address = 0x02000021; rejects([&] { bad.validate(); });
    bad = plan; bad.watches[0].length = 513; rejects([&] { bad.validate(); });
    bad = plan; bad.watches.assign(65, NativeWatch{0x02000000, 1, {}, 0, false});
    rejects([&] { bad.validate(); });
    bad = plan; bad.watches = {NativeWatch{0x023FFFFF, 2, {}, 0, false}};
    rejects([&] { bad.validate(); });
    bad = plan; bad.watches = {NativeWatch{0x02000000, 1, {}, -1, false}};
    rejects([&] { bad.validate(); });
    plan.watches = {NativeWatch{0x0200100A, 2, {}, 0, false}};
    plan.validate(); values = plan.read(read32, read8);
    assert(values[0].present && values[0].pointers.empty() && values[0].bytes[1] == 0xCD);
    std::cout << "Native replay schedule and reachable component controls passed\n";
}
