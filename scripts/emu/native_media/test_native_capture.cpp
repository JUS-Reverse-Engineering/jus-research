#include "NativeCapture.h"
#include "NativeGpuMedia.h"
#include <algorithm>
#include <functional>
#include <set>
#include <sstream>
#include <cassert>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <iostream>
#include <vector>
using namespace std;
namespace fs = std::filesystem;
string read(const fs::path& p) { ifstream f(p,ios::binary); return {istreambuf_iterator<char>(f),{}}; }

// Synthetic 2D renderer state for the GPU-media stream. runFrame() calls the
// observer in melonDS order: for VCount 0..191 compose(line) then (below 191)
// sprites(line+1); at VCount 262 sprites(0) for the next frame.
struct FakeGpu
{
    vector<uint8_t> oam[2], vram[2], pal[2], ext[2], sregs[2], cregs[2], postOam, postPal, postRegs;
    FakeGpu()
    {
        for (int e = 0; e < 2; ++e)
        {
            oam[e].assign(1024, 0); vram[e].assign(NativeGpuMedia::VramBytes[e], 0);
            pal[e].assign(512, 0); ext[e].assign(8192, 0); sregs[e].assign(12, 0); cregs[e].assign(36, 0);
            for (int i = 0; i < 1024; ++i) oam[e][i] = uint8_t(i * 7 + e);
            for (size_t i = 0; i < vram[e].size(); ++i) vram[e][i] = uint8_t(i / 1024 + e);
            for (int i = 0; i < 512; ++i) pal[e][i] = uint8_t(i + 3 * e);
        }
        postOam.assign(2048, 0); postPal.assign(2048, 0); postRegs.assign(18, 0);
    }
};
using LineHook = function<void(FakeGpu&, int vcount)>;
void runFrame(NativeGpuMedia& g, FakeGpu& f, LineHook hook = {})
{
    for (int v = 0; v < 192; ++v)
    {
        if (hook) hook(f, v);
        for (unsigned e = 0; e < 2; ++e) g.compose(e, v, f.pal[e].data(), f.ext[e].data(), f.cregs[e].data());
        if (v < 191)
            for (unsigned e = 0; e < 2; ++e)
                g.sprites(e, v + 1, f.oam[e].data(), f.vram[e].data(), uint32_t(f.vram[e].size()), f.sregs[e].data());
    }
    if (hook) hook(f, 262);
    for (unsigned e = 0; e < 2; ++e)
        g.sprites(e, 0, f.oam[e].data(), f.vram[e].data(), uint32_t(f.vram[e].size()), f.sregs[e].data());
}
vector<vector<string>> table(const fs::path& p)
{
    vector<vector<string>> rows; istringstream in(read(p)); string line;
    getline(in, line);
    while (getline(in, line)) { vector<string> row; string cell; istringstream cells(line); while (getline(cells, cell, '\t')) row.push_back(cell); rows.push_back(row); }
    return rows;
}
// gpu-spans.tsv rows for (sequence, engine, stream).
vector<vector<string>> spansOf(const fs::path& dir, int seq, int engine, const string& stream)
{
    vector<vector<string>> out;
    for (auto& r : table(dir / "gpu-spans.tsv"))
        if (r[0] == to_string(seq) && r[2] == to_string(engine) && r[3] == stream) out.push_back(r);
    return out;
}
string blobBytes(const fs::path& dir, const string& id)
{
    for (auto& r : table(dir / "gpu-blobs.tsv"))
        if (r[0] == id) return read(dir / "gpu-blobs.bin").substr(stoul(r[2]), stoul(r[3]));
    return "";
}
string str(const vector<uint8_t>& v) { return string(v.begin(), v.end()); }
// Bitwise CRC-32 (IEEE, reflected), independent of the writer's table version.
uint32_t crcBits(const string& b)
{
    uint32_t c = 0xFFFFFFFFu;
    for (unsigned char x : b) { c ^= x; for (int k = 0; k < 8; ++k) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1))); }
    return ~c;
}
// Blob index: every CRC matches its bytes, offsets are contiguous, no kind+bytes pair is stored twice; post CRCs match.
void blobIndexOk(const fs::path& dir)
{
    string bin = read(dir / "gpu-blobs.bin"); size_t at = 0; std::set<string> seen;
    for (auto& r : table(dir / "gpu-blobs.tsv"))
    {
        assert(stoul(r[2]) == at);
        string b = bin.substr(at, stoul(r[3])); at += b.size();
        assert(crcBits(b) == stoul(r[4]));
        assert(seen.insert(r[1] + '|' + b).second);
    }
    assert(at == bin.size());
    string post = read(dir / "gpu-post.bin"); size_t k = 0;
    for (auto& r : table(dir / "gpu-frames.tsv")) { assert(crcBits(post.substr(4096 * k++, 4096)) == stoul(r[2])); }
}
bool frameOk(NativeGpuMedia& g, FakeGpu& f, uint32_t seq, string* why = nullptr)
{
    string e; bool ok = g.frame(seq, 500 + seq, f.postOam.data(), f.postPal.data(), f.postRegs.data(), e);
    if (why) *why = e;
    return ok;
}

void gpuMediaChecks(const fs::path& root)
{
    // Both OAM banks, including affine filler words, round-trip post-frame and consumed.
    {
        NativeGpuMedia g; FakeGpu f; fs::path d = root / "gpu-roundtrip"; fs::create_directory(d);
        assert(g.start(d, 2));
        for (int i = 0; i < 2048; ++i) f.postOam[i] = uint8_t(255 - i % 251);
        for (int i = 0; i < 2048; ++i) f.postPal[i] = uint8_t(i % 13);
        f.oam[0][6] = 0x34; f.oam[0][7] = 0x12;  // PA of affine group 0 (filler halfword of entry 0)
        f.oam[1][8 * 127 + 6] = 0xFE;            // PD of affine group 31 on the sub engine
        runFrame(g, f); assert(frameOk(g, f, 0));
        runFrame(g, f); assert(frameOk(g, f, 1));
        assert(!g.active());
        string post = read(d / "gpu-post.bin");
        assert(post.size() == 2 * 4096);
        assert(post.substr(0, 2048) == str(f.postOam) && post.substr(2048, 2048) == str(f.postPal));
        auto first = spansOf(d, 0, 0, "obj");
        assert(first.size() == 2 && first[0][4] == "0" && first[0][5] == "0" && first[0][6] == "0" && first[0][7] == "-");
        assert(first[1][4] == "1" && first[1][5] == "191" && first[1][6] == "1");
        assert(blobBytes(d, first[1][7]) == str(f.oam[0]));
        auto second = spansOf(d, 1, 1, "obj");
        assert(second.size() == 1 && second[0][4] == "0" && second[0][5] == "191");
        assert(blobBytes(d, second[0][7]) == str(f.oam[1]));
        assert(table(d / "gpu-frames.tsv").size() == 2 && table(d / "gpu-frames.tsv")[1][1] == "501");
        auto sets = table(d / "gpu-vram-sets.tsv");
        assert(sets.size() == 2 && sets[0][1] == "0" && sets[1][1] == "1");
        assert(count(sets[0][2].begin(), sets[0][2].end(), ',') == 255 && count(sets[1][2].begin(), sets[1][2].end(), ',') == 127);
        { vector<string> p; string c; istringstream in(sets[0][2]); while (getline(in, c, ',')) p.push_back(c);
          assert(blobBytes(d, p[7]) == string(f.vram[0].begin() + 7 * 1024, f.vram[0].begin() + 8 * 1024)); }
        assert(read(d / "gpu-media.json").find("\"vram_pages\":[256,128]") != string::npos);
        assert(crcBits("123456789") == 0xCBF43926u);
        blobIndexOk(d);
    }
    // Palette changes with the same OAM (same tile id): new pal blob, OAM blob reused.
    {
        NativeGpuMedia g; FakeGpu f; fs::path d = root / "gpu-palette"; fs::create_directory(d);
        assert(g.start(d, 3));
        runFrame(g, f); assert(frameOk(g, f, 0));
        runFrame(g, f); assert(frameOk(g, f, 1));
        f.pal[0][2] ^= 0x1F;
        runFrame(g, f); assert(frameOk(g, f, 2));
        auto o1 = spansOf(d, 1, 0, "obj"), o2 = spansOf(d, 2, 0, "obj");
        auto c1 = spansOf(d, 1, 0, "compose"), c2 = spansOf(d, 2, 0, "compose");
        assert(o1.size() == 1 && o2.size() == 1 && o1[0][7] == o2[0][7] && o1[0][8] == o2[0][8]);
        assert(c1.size() == 1 && c2.size() == 1 && c1[0][9] != c2[0][9] && c1[0][10] == c2[0][10]);
        assert(blobBytes(d, c2[0][9]) == str(f.pal[0]));
    }
    // OBJ mapping change (DISPCNT bit 4: 2D -> 1D) is a separate obj span by registers alone.
    {
        NativeGpuMedia g; FakeGpu f; fs::path d = root / "gpu-mapping"; fs::create_directory(d);
        assert(g.start(d, 2));
        runFrame(g, f); assert(frameOk(g, f, 0));
        runFrame(g, f, [](FakeGpu& x, int v) { if (v == 40) x.sregs[0][0] |= 0x10; });
        assert(frameOk(g, f, 1));
        auto o = spansOf(d, 1, 0, "obj");
        assert(o.size() == 2 && o[0][5] == "40" && o[1][4] == "41" && o[0][7] == o[1][7] && o[0][11] != o[1][11]);
        assert(o[1][11].substr(0, 2) == "10");
    }
    // Consumed OAM differs from the post-frame snapshot: both kept, neither overwritten.
    {
        NativeGpuMedia g; FakeGpu f; fs::path d = root / "gpu-postmismatch"; fs::create_directory(d);
        assert(g.start(d, 2));
        runFrame(g, f); assert(frameOk(g, f, 0));
        runFrame(g, f, [](FakeGpu& x, int v) { if (v == 262) x.oam[0][0] = 0xAA; });  // write after line 0 drew
        f.postOam.assign(f.oam[0].begin(), f.oam[0].end()); f.postOam.resize(2048, 0); f.postOam[0] = 0x55;
        assert(frameOk(g, f, 1));
        auto o = spansOf(d, 1, 0, "obj");
        assert(o.size() == 1 && blobBytes(d, o[0][7])[0] != char(0x55) && blobBytes(d, o[0][7])[0] != char(0xAA));
        assert(read(d / "gpu-post.bin").substr(4096, 1) == string(1, char(0x55)));
    }
    // Mid-frame scanline versions: OAM write at VCount 99 (affects output line 100),
    // one VRAM page write at VCount 150 (line 151); the frame keeps three spans.
    {
        NativeGpuMedia g; FakeGpu f; fs::path d = root / "gpu-scanline"; fs::create_directory(d);
        assert(g.start(d, 2));
        runFrame(g, f); assert(frameOk(g, f, 0));
        runFrame(g, f, [](FakeGpu& x, int v) {
            if (v == 99) x.oam[0][16] ^= 1;
            if (v == 150) x.vram[0][5 * 1024 + 3] ^= 0xFF;
        });
        assert(frameOk(g, f, 1));
        auto o = spansOf(d, 1, 0, "obj");
        assert(o.size() == 3);
        assert(o[0][4] == "0" && o[0][5] == "99" && o[1][4] == "100" && o[1][5] == "150" && o[2][4] == "151" && o[2][5] == "191");
        assert(o[0][7] != o[1][7] && o[1][7] == o[2][7] && o[0][8] == o[1][8] && o[1][8] != o[2][8]);
        auto sets = table(d / "gpu-vram-sets.tsv");
        auto pages = [&](const string& id) { for (auto& r : sets) if (r[0] == id) { vector<string> p; string c; istringstream s(r[2]); while (getline(s, c, ',')) p.push_back(c); return p; } return vector<string>{}; };
        auto before = pages(o[1][8]), after = pages(o[2][8]);
        int diff = 0; for (size_t i = 0; i < before.size(); ++i) diff += before[i] != after[i];
        assert(before.size() == 256 && diff == 1 && before[5] != after[5]);
        assert(blobBytes(d, after[5])[3] == char(f.vram[0][5 * 1024 + 3]));
        assert(spansOf(d, 1, 1, "obj").size() == 1);  // the sub engine is untouched
    }
    // Missing compose lines, out-of-order lines, overflowed budgets: the stream fails closed.
    {
        NativeGpuMedia g; FakeGpu f; fs::path d = root / "gpu-missing"; fs::create_directory(d);
        assert(g.start(d, 2));
        for (int v = 1; v < 192; ++v)
            for (unsigned e = 0; e < 2; ++e) g.sprites(e, v, f.oam[e].data(), f.vram[e].data(), uint32_t(f.vram[e].size()), f.sregs[e].data());
        string why; assert(!frameOk(g, f, 0, &why) && why == "gpu_scanline_coverage" && !g.active());
    }
    {
        NativeGpuMedia g; FakeGpu f; fs::path d = root / "gpu-order"; fs::create_directory(d);
        assert(g.start(d, 2));
        g.compose(0, 0, f.pal[0].data(), f.ext[0].data(), f.cregs[0].data());
        g.compose(0, 2, f.pal[0].data(), f.ext[0].data(), f.cregs[0].data());
        string why; assert(!frameOk(g, f, 0, &why) && why == "gpu_scanline_order");
    }
    {
        NativeGpuMedia g; FakeGpu f; fs::path d = root / "gpu-skipline0"; fs::create_directory(d);
        assert(g.start(d, 3));
        runFrame(g, f); assert(frameOk(g, f, 0));
        for (int v = 0; v < 192; ++v)  // a frame whose next-frame line 0 never ran
        {
            for (unsigned e = 0; e < 2; ++e) g.compose(e, v, f.pal[e].data(), f.ext[e].data(), f.cregs[e].data());
            if (v < 191) for (unsigned e = 0; e < 2; ++e) g.sprites(e, v + 1, f.oam[e].data(), f.vram[e].data(), uint32_t(f.vram[e].size()), f.sregs[e].data());
        }
        assert(frameOk(g, f, 1));
        runFrame(g, f);
        string why; assert(!frameOk(g, f, 2, &why) && why == "gpu_scanline_order");
    }
    {
        NativeGpuMedia g; FakeGpu f; fs::path d = root / "gpu-blob-overflow"; fs::create_directory(d);
        g.blobBudget = 200 * 1024;  // less than the 256 unique VRAM pages
        assert(g.start(d, 1));
        runFrame(g, f);
        string why; assert(!frameOk(g, f, 0, &why) && why == "gpu_blob_overflow");
        assert(table(d / "gpu-frames.tsv").empty());
    }
    {
        NativeGpuMedia g; FakeGpu f; fs::path d = root / "gpu-span-overflow"; fs::create_directory(d);
        g.spanBudget = 2;
        assert(g.start(d, 1));
        runFrame(g, f, [](FakeGpu& x, int v) { if (v == 10 || v == 20) x.pal[1][0] ^= 1; });
        string why; assert(!frameOk(g, f, 0, &why) && why == "gpu_span_overflow");
    }
    {
        NativeGpuMedia g; FakeGpu f; fs::path d = root / "gpu-bad";
        assert(!g.start(d, 1));  // directory must already exist
        fs::create_directory(d); assert(g.start(d, 1)); assert(!g.start(d, 1));
        g.sprites(1, 5, f.oam[1].data(), f.vram[1].data(), 256 * 1024, f.sregs[1].data());  // wrong VRAM size for sub
        string why; assert(!frameOk(g, f, 0, &why) && why == "gpu_bad_observation");
    }
}
int main(int argc,char**argv) {
    assert(argc==2);
    fs::path root=argv[1]; fs::create_directory(root);
    vector<uint32_t> top(256*192,0x00112233), bottom(256*192,0x00445566);
    NativeCapture c;
    assert(!c.start(root/"bad",0,2));
    assert(c.start(root/"ok",2,2));
    c.beginFrame(100);
    c.audio(112,12,-32768,32767);
    assert(c.frame(77,120,4095,top.data(),bottom.data(),{1,2}));
    auto ppm=read(root/"ok"/"000000.ppm");
    string h="P6\n256 384\n255\n";
    assert(ppm.size()==h.size()+256*384*3);
    assert(ppm.substr(0,h.size())==h);
    assert(ppm.substr(h.size(),3)==string("\x11\x22\x33",3));
    assert(ppm.substr(h.size()+256*192*3,3)==string("\x44\x55\x66",3));
    auto audio=read(root/"ok"/"audio.bin");
    assert(audio==string("\x70\0\0\0\0\0\0\0\x0c\0\0\0\0\x80\xff\x7f",16));
    c.beginFrame(120);
    c.audio(124,12,1,-1);
    assert(c.frame(78,140,4093,top.data(),bottom.data(),{3,4}));
    assert(!c.active());
    assert(read(root/"ok"/"frames.tsv").find("0\t77\t100\t120\t4095\t0\t1\t0102\t0\t0\t")!=string::npos);
    assert(read(root/"ok"/"frames.tsv").find("1\t78\t120\t140\t4093\t1\t1\t0304\t0\t0\t")!=string::npos);
    assert(read(root/"ok"/"status.json").find("\"state\":\"complete\"")!=string::npos);
    NativeCapture reused;
    assert(!reused.start(root/"ok",2,2));
    assert(read(root/"ok"/"audio.bin").size()==32);
    NativeCapture rewind;
    assert(rewind.start(root/"rewind",3,2));
    rewind.beginFrame(100); rewind.audio(112,12,1,2); assert(rewind.frame(10,120,4095,top.data(),bottom.data(),{0,1}));
    rewind.beginFrame(120); assert(!rewind.frame(10,140,4095,top.data(),bottom.data(),{0,1}));
    assert(read(root/"rewind"/"status.json").find("frame_discontinuity")!=string::npos);
    assert(!fs::exists(root/"rewind"/"000001.ppm"));
    NativeCapture stale;
    assert(stale.start(root/"stale",1,1)); stale.beginFrame(100); stale.audio(99,12,0,0);
    assert(!stale.frame(1,120,0,top.data(),bottom.data(),{0}));
    assert(read(root/"stale"/"status.json").find("audio_outside_frame")!=string::npos);
    NativeCapture wrong;
    assert(wrong.start(root/"wrong",1,2));wrong.beginFrame(1);
    assert(!wrong.frame(1,2,0,top.data(),bottom.data(),{0}));
    assert(read(root/"wrong"/"status.json").find("watch_length")!=string::npos);
    NativeCapture empty;
    assert(empty.start(root/"empty",1,1));empty.beginFrame(100);
    assert(!empty.frame(1,120,0,top.data(),bottom.data(),{0}));
    assert(read(root/"empty"/"status.json").find("audio_missing")!=string::npos);
    NativeCapture io;
    assert(io.start(root/"io",1,1));io.beginFrame(100);io.audio(112,12,1,2);
    fs::create_directory(root/"io"/"000000.ppm");
    assert(!io.frame(1,120,0,top.data(),bottom.data(),{0}));
    assert(read(root/"io"/"status.json").find("io_error")!=string::npos);
    assert(!io.active());
    gpuMediaChecks(root);
    cout<<"Native capture writer and GPU-media behavior checks passed\n";
}
