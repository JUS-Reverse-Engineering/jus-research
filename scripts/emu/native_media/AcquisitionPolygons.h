#pragma once
#include <array>
#include <cstdint>
#include <ostream>
#include <vector>

struct AcquisitionVertex {
    std::array<int32_t,4> position{};
    std::array<int32_t,2> screen{}, texture{};
    std::array<int32_t,3> color{};
    int32_t z=0,w=0;
};
struct AcquisitionPolygon {
    uint32_t index=0,attr=0,tex=0,palette=0;
    bool wbuffer=false,facing=false;
    std::vector<AcquisitionVertex> vertices;
};
template<size_t N>
inline void acquisitionArray(std::ostream& out,const std::array<int32_t,N>& a) {
    out << '[';
    for(size_t i=0;i<N;i++) { if(i) out << ','; out << a[i]; }
    out << ']';
}
inline void acquisitionPolygons(std::ostream& out,uint32_t sequence,uint32_t gfc,
    uint32_t dispcnt,uint32_t clear,const std::array<int32_t,16>& projection,
    const std::vector<AcquisitionPolygon>& polygons) {
    out << "{\"schema\":\"acquisition-polygons/v1\",\"sequence\":" << sequence
        << ",\"gfc\":" << gfc << ",\"dispcnt\":" << dispcnt
        << ",\"clear_attr2\":" << clear << ",\"projection\":";
    acquisitionArray(out,projection);
    out << ",\"polygons\":[";
    bool first=true;
    for(const auto& p:polygons) {
        if(!first) out << ','; first=false;
        out << "{\"index\":" << p.index << ",\"attr\":" << p.attr
            << ",\"tex\":" << p.tex << ",\"palette\":" << p.palette
            << ",\"wbuffer\":" << (p.wbuffer ? "true":"false")
            << ",\"facing\":" << (p.facing ? "true":"false") << ",\"vertices\":[";
        bool fv=true;
        for(const auto& v:p.vertices) {
            if(!fv) out << ','; fv=false;
            out << "{\"position\":"; acquisitionArray(out,v.position);
            out << ",\"screen\":"; acquisitionArray(out,v.screen);
            out << ",\"texture\":"; acquisitionArray(out,v.texture);
            out << ",\"color\":"; acquisitionArray(out,v.color);
            out << ",\"z\":" << v.z << ",\"w\":" << v.w << '}';
        }
        out << "]}";
    }
    out << "]}\n";
}
