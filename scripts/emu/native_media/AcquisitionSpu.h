#pragma once
#include <array>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <stdexcept>

struct AcquisitionSpuState {
    std::ofstream samples,regs;
    uint32_t sequence=0,gfc=0;
    bool active=false;
};
inline AcquisitionSpuState acquisitionSpuState;
inline void acquisitionLe(std::ostream& out,uint64_t value,unsigned n) {
    for(unsigned i=0;i<n;i++) out.put(char(value>>(8*i)));
}
inline void acquisitionSpuBegin(uint32_t sequence,uint32_t gfc) {
    auto& s=acquisitionSpuState;
    const char* path=std::getenv("J6ACQ_SPU");
    if(!path) return;
    if(!s.samples.is_open()) {
        std::filesystem::create_directories(path);
        s.samples.open(std::filesystem::path(path)/"samples.bin",std::ios::binary);
        s.regs.open(std::filesystem::path(path)/"regs.jsonl");
    }
    s.sequence=sequence;s.gfc=gfc;s.active=true;
    if(!s.samples || !s.regs) throw std::runtime_error("SPU tap IO failure");
}
inline void acquisitionSpuEnd() {
    acquisitionSpuState.active=false;
    acquisitionSpuState.samples.flush();
    acquisitionSpuState.regs.flush();
}
inline void acquisitionSpuSample(uint64_t clock,uint32_t period,int32_t left,int32_t right,
    uint32_t cnt10,uint32_t cnt11,const std::array<int32_t,32>& channels,uint32_t gfc=UINT32_MAX) {
    auto& s=acquisitionSpuState;
    if(!s.active) return;
    acquisitionLe(s.samples,clock,8);
    for(uint32_t v:{s.sequence,gfc==UINT32_MAX?s.gfc:gfc,period,uint32_t(left),uint32_t(right),cnt10,cnt11})
        acquisitionLe(s.samples,v,4);
    for(int32_t v:channels) acquisitionLe(s.samples,uint32_t(v),4);
    if(!s.samples) throw std::runtime_error("SPU tap sample IO failure");
}
template<class ReadGfc>
inline void acquisitionSpuSampleAll(uint64_t clock,uint32_t period,int32_t left,int32_t right,
    const std::array<uint32_t,16>& cnt,const std::array<int32_t,32>& channels,ReadGfc readGfc) {
    auto& s=acquisitionSpuState;
    if(!s.active) return;
    acquisitionLe(s.samples,clock,8);
    for(uint32_t v:{s.sequence,uint32_t(readGfc()),period,uint32_t(left),uint32_t(right)}) acquisitionLe(s.samples,v,4);
    for(uint32_t v:cnt) acquisitionLe(s.samples,v,4);
    for(int32_t v:channels) acquisitionLe(s.samples,uint32_t(v),4);
    if(!s.samples) throw std::runtime_error("SPU all-channel tap IO failure");
}
template<class Channel>
struct AcquisitionRegisterGuard {
    uint64_t clock;uint32_t addr,value,width;Channel* channels;
    AcquisitionRegisterGuard(uint64_t t,uint32_t a,uint32_t v,uint32_t w,Channel* c):
        clock(t),addr(a),value(v),width(w),channels(c) {}
    ~AcquisitionRegisterGuard() {
        auto& s=acquisitionSpuState;
        unsigned n=(addr>>4)&15;
        if(!s.active || addr<0x04000400 || addr>=0x04000500 || (n<10 || n>15)) return;
        const auto& c=channels[n];
        s.regs << "{\"clock\":" << clock << ",\"sequence\":" << s.sequence
            << ",\"gfc\":" << s.gfc << ",\"channel\":" << n << ",\"address\":" << addr
            << ",\"value\":" << value << ",\"width\":" << width
            << ",\"registers\":{\"CNT\":" << c.Cnt << ",\"SAD\":" << c.SrcAddr
            << ",\"TMR\":" << c.TimerReload << ",\"PNT\":" << (c.LoopPos>>2)
            << ",\"LEN\":" << (c.Length>>2) << "}}\n";
    }
};
