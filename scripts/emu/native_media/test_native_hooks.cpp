#include "NativeHooks.h"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <iterator>
#include <map>
using namespace std;
namespace fs = std::filesystem;
string read(const fs::path& p) { ifstream f(p, ios::binary); return {istreambuf_iterator<char>(f), {}}; }

int main(int argc, char** argv)
{
    assert(argc == 2);
    fs::path root = argv[1]; fs::create_directory(root);
    auto rejects = [](const function<void()>& fn) {
        bool failed = false;
        try { fn(); } catch (const invalid_argument&) { failed = true; }
        assert(failed);
    };

    // Fake ARM9 RAM: manager pointer at 0x02100000 -> manager 0x02200000 whose head
    // points to node A (0x02200100) -> node B (0x02200200) -> null. Node A has a
    // position chain [[A+0x2C]+0x10] -> 0x02300000, x/y at +0xC. Node B's chain is null.
    map<uint32_t, uint8_t> ram;
    auto put32 = [&](uint32_t a, uint32_t v) { for (int i = 0; i < 4; ++i) ram[a + i] = uint8_t(v >> (8 * i)); };
    auto put16 = [&](uint32_t a, uint16_t v) { ram[a] = uint8_t(v); ram[a + 1] = uint8_t(v >> 8); };
    put32(0x02100000, 0x02200000);
    put32(0x02200000, 0x02200100);
    put32(0x02200100, 0x02200200); put16(0x02200118, 23); ram[0x0220011A] = 7; put32(0x0220012C, 0x02280000);
    put32(0x02280010, 0x02300000); put32(0x0230000C, 0x1234); put32(0x02300010, 0xFFFFFF00);
    put32(0x02200200, 0); put16(0x02200218, 0xFFFF); ram[0x0220021A] = 5; put32(0x0220022C, 0);
    auto r32 = [&](uint32_t a) { uint32_t v = 0; for (int i = 0; i < 4; ++i) v |= uint32_t(ram[a + i]) << (8 * i); return v; };
    auto r8 = [&](uint32_t a) { return ram[a]; };

    NativeList shots;
    shots.address = 0x02100000; shots.offsets = {0}; shots.next = 0; shots.limit = 16;
    shots.fields = {{{0x18}, 2, false}, {{0x1A}, 1, false}, {{0x2C, 0x10, 0xC}, 8, true}};

    // Validation bounds.
    NativeHooks ok; ok.pcs = {0x0206C7FC, 0x020734AC}; ok.lists = {shots}; ok.validate();
    rejects([&] { NativeHooks h; h.pcs = {0x0206C7FD}; h.validate(); });          // misaligned
    rejects([&] { NativeHooks h; h.pcs = {0x03000000}; h.validate(); });          // outside ARM9 code RAM
    rejects([&] { NativeHooks h; h.pcs.assign(65, 0x02000000); h.validate(); });  // budget
    rejects([&] { NativeHooks h; h.pcs = {0x02000000, 0x02000000}; h.validate(); }); // duplicate
    rejects([&] { NativeHooks h; auto l = shots; l.limit = 0; h.lists = {l}; h.validate(); });
    rejects([&] { NativeHooks h; auto l = shots; l.limit = 33; h.lists = {l}; h.validate(); });
    rejects([&] { NativeHooks h; auto l = shots; l.fields.assign(17, {{0}, 1, false}); h.lists = {l}; h.validate(); });
    rejects([&] { NativeHooks h; auto l = shots; l.fields = {{{0}, 129, false}}; h.lists = {l}; h.validate(); });
    rejects([&] { NativeHooks h; auto l = shots; l.fields = {{{}, 1, false}}; h.lists = {l}; h.validate(); });
    rejects([&] { NativeHooks h; auto l = shots; l.fields = {{{0}, 1, true}}; h.lists = {l}; h.validate(); }); // optional direct
    rejects([&] { NativeHooks h; h.lists.assign(5, shots); h.validate(); });
    assert(!NativeHooks().enabled() && ok.enabled());
    assert(ok.watching(0x020734AC) && !ok.watching(0x020734B0));

    // Writer: spec files, call rows, list rows.
    assert(ok.start(root / "bundle-missing") == false);   // directory must exist (capture made it)
    fs::create_directory(root / "b");
    assert(ok.start(root / "b"));
    assert(read(root / "b" / "hooks.json") == "{\"version\":1,\"call_pcs\":2,\"lists\":1}\n");
    assert(read(root / "b" / "call-pcs.tsv") == "pc\n33998844\n34026668\n");
    assert(read(root / "b" / "lists.tsv") ==
           "list\taddress\toffsets\tnext\tlimit\tfields\n0\t34603008\t0\t0\t16\t24:2:0;26:1:0;44,16,12:8:1\n");
    uint32_t regs[16] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16};
    ok.hit(0x020734AC, 0xE3500001, regs);
    regs[0] = 0; ok.hit(0x020734AC, 0xE3500001, regs);
    string error;
    assert(ok.frame(0, 501, r32, r8, error) && error.empty());
    // Second frame: no calls; node A retired (head now B only).
    put32(0x02200000, 0x02200200);
    assert(ok.frame(1, 502, r32, r8, error));
    // Third frame: list head null -> present, empty. Then the manager pointer null -> absent.
    put32(0x02200000, 0);
    assert(ok.frame(2, 503, r32, r8, error));
    put32(0x02100000, 0);
    assert(ok.frame(3, 504, r32, r8, error));
    ok.close();
    assert(read(root / "b" / "calls.tsv") ==
           "sequence\tnds_frame\tpc\tinsn\tr0\tr1\tr2\tr3\tr4\tr5\tr6\tr7\tlr\n"
           "0\t501\t34026668\t3813670913\t1\t2\t3\t4\t5\t6\t7\t8\t15\n"
           "0\t501\t34026668\t3813670913\t0\t2\t3\t4\t5\t6\t7\t8\t15\n");
    fs::create_directory(root / "thumb");
    NativeHooks thumb;
    thumb.pcs = {0x0214DBD6, 0x0214DF74};
    thumb.validate();
    assert(thumb.start(root / "thumb"));
    regs[0] = 0x020A0F10;
    regs[1] = 78991;
    auto captureThumb = [&](uint32_t r15, uint32_t nextInstr) {
        uint32_t pc = r15 - 2;
        if (thumb.watching(pc)) thumb.hit(pc, nextInstr & 0xFFFF, regs);
    };
    captureThumb(0x0214DBD8, 0x6001ABCD >> 16);
    captureThumb(0x0214DF76, 0xABCD6001);
    assert(thumb.frame(78, 253437, r32, r8, error));
    thumb.close();
    assert(read(root / "thumb" / "calls.tsv") ==
           "sequence\tnds_frame\tpc\tinsn\tr0\tr1\tr2\tr3\tr4\tr5\tr6\tr7\tlr\n"
           "78\t253437\t34921430\t24577\t34213648\t78991\t3\t4\t5\t6\t7\t8\t15\n"
           "78\t253437\t34922356\t24577\t34213648\t78991\t3\t4\t5\t6\t7\t8\t15\n");
    assert(read(root / "b" / "list-frames.tsv") ==
           "sequence\tnds_frame\tlist\tpresent\tcount\ttruncated\thead_path\n"
           "0\t501\t0\t1\t2\t0\t34603008:35651584,35651584:35651840\n"
           "1\t502\t0\t1\t1\t0\t34603008:35651584,35651584:35652096\n"
           "2\t503\t0\t1\t0\t0\t34603008:35651584,35651584:0\n"
           "3\t504\t0\t0\t0\t0\t34603008:0\n");
    // Node A: life 23 (1700), kind 7, position present at 0x0230000C (36700172).
    // Node B: life -1, kind 5, position chain null at its first hop -> absent, zero padded.
    assert(read(root / "b" / "list-nodes.tsv") ==
           "sequence\tnds_frame\tlist\tnode\taddress\tnext\tfield_present\tfield_addresses\tdata_hex\n"
           "0\t501\t0\t0\t35651840\t35652096\t111\t35651864,35651866,36700172\t17000734120000" "00ffffff\n"
           "0\t501\t0\t1\t35652096\t0\t110\t35652120,35652122,0\tffff050000000000000000\n"
           "1\t502\t0\t0\t35652096\t0\t110\t35652120,35652122,0\tffff050000000000000000\n");

    // Truncation: a self-loop stops at the limit and is flagged.
    fs::create_directory(root / "loop");
    NativeHooks loop; auto l = shots; l.limit = 2; l.fields = {{{0x1A}, 1, false}}; loop.lists = {l};
    put32(0x02100000, 0x02200000); put32(0x02200000, 0x02200100); put32(0x02200100, 0x02200100);
    assert(loop.start(root / "loop") && loop.frame(0, 9, r32, r8, error)); loop.close();
    assert(read(root / "loop" / "list-frames.tsv").find("0\t9\t0\t1\t2\t1\t") != string::npos);
    assert(!fs::exists(root / "loop" / "calls.tsv"));

    // Unreachable node pointer fails the frame with a named error.
    fs::create_directory(root / "bad");
    NativeHooks bad; bad.lists = {shots};
    put32(0x02200100, 0x04000000);
    assert(bad.start(root / "bad") && !bad.frame(0, 9, r32, r8, error) && error == "list_pointer_unreachable");
    bad.close();

    // A required field chain that hits null fails; per-frame hit budget overflows.
    fs::create_directory(root / "req");
    NativeHooks req; auto rl = shots; rl.fields = {{{0x2C, 0x10, 0xC}, 8, false}}; req.lists = {rl};
    put32(0x02200100, 0); put32(0x0220012C, 0);
    assert(req.start(root / "req") && !req.frame(0, 9, r32, r8, error) && error == "required_list_field_absent");
    req.close();
    fs::create_directory(root / "flood");
    NativeHooks flood; flood.pcs = {0x02000000};
    assert(flood.start(root / "flood"));
    for (size_t i = 0; i <= NativeHooks::MaxHitsPerFrame; ++i) flood.hit(0x02000000, 0, regs);
    assert(!flood.frame(0, 9, r32, r8, error) && error == "call_log_overflow");
    flood.close();
    cout << "Native call-log and list-walk checks passed\n";
}
