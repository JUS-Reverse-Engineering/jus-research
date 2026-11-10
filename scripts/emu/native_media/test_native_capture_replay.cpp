#include "NativeCapture.h"
#include "NativeReplay.h"
#include <cassert>
#include <fstream>
#include <iterator>
#include <iostream>

int main(int argc, char** argv)
{
    assert(argc == 2);
    std::filesystem::path root = argv[1];
    std::filesystem::create_directory(root);
    std::vector<uint32_t> image(256 * 192, 0);
    NativeCapture c;
    assert(c.start(root / "metadata", 1, 2));
    assert(c.sequence() == 0);
    NativeWatchValue present;
    present.address = 0x02001000; present.bytes = {7};
    present.readAddresses = {0x02000000}; present.pointers = {0x02001000};
    NativeWatchValue absent;
    absent.present = false; absent.bytes = {0};
    absent.readAddresses = {0x02000004}; absent.pointers = {0};
    c.beginFrame(100); c.audio(112, 12, 1, 2);
    assert(c.frame(1, 120, 4095, image.data(), image.data(), {7, 0}, {present, absent}));
    assert(c.sequence() == 1 && !c.active());
    std::ifstream f(root / "metadata" / "frames.tsv");
    std::string raw{std::istreambuf_iterator<char>(f), {}};
    assert(raw.find("watch_present\twatch_addresses\twatch_paths\n") != std::string::npos);
    assert(raw.find("\t10\t33558528,0\t33554432:33558528;33554436:0\n") != std::string::npos);
    NativeCapture bad;
    assert(bad.start(root / "bad", 1, 2)); bad.beginFrame(100); bad.audio(112, 12, 1, 2);
    assert(!bad.frame(1, 120, 4095, image.data(), image.data(), {8, 0}, {present, absent}));
    NativeCapture bounded;
    assert(bounded.start(root / "bounded", 1, 2)); bounded.beginFrame(100); bounded.audio(112, 12, 1, 2);
    std::vector<NativeWatchValue> tooMany(65);
    tooMany[0].bytes = {7, 0};
    assert(!bounded.frame(1, 120, 4095, image.data(), image.data(), {7, 0}, tooMany));
    std::cout << "Native frame pointer provenance and payload controls passed\n";
}
