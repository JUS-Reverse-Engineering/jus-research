#pragma once
#include "NativeReplay.h"
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <vector>

class NativeCapture
{
    struct Sample { uint64_t tick; uint32_t period; int16_t left, right; };
    std::filesystem::path directory;
    std::ofstream rows, sound;
    std::vector<Sample> samples;
    uint32_t limit = 0, count = 0, bytes = 0, lastFrame = 0;
    uint64_t startTick = 0, lastEnd = 0, lastSample = 0, audioCount = 0;
    bool recording = false, begun = false;
    int16_t heldLeft = 0, heldRight = 0;

    static void le(std::ostream& out, uint64_t value, unsigned length)
    {
        for (unsigned i = 0; i < length; ++i) out.put(char(value >> (8 * i)));
    }
    void finish(const char* state, const char* error)
    {
        recording = false;
        rows.flush(); sound.flush();
        if (!rows || !sound) { state = "failed"; error = "io_error"; }
        rows.close(); sound.close();
        if (rows.fail() || sound.fail()) { state = "failed"; error = "io_error"; }
        std::ofstream status(directory / "status.json");
        status << "{\"state\":\"" << state << "\",\"error\":\"" << error
               << "\",\"frames\":" << count << ",\"audio_packets\":" << audioCount << "}\n";
        status.close();
    }
public:
    ~NativeCapture() { if (recording) finish("stopped", "incomplete"); }
    bool active() const { return recording; }
    uint32_t sequence() const { return count; }
    void fail(const char* error) { if (recording) finish("failed", error); }
    void stop() { if (recording) finish("stopped", "incomplete"); }
    bool start(const std::filesystem::path& path, uint32_t frames, uint32_t watchBytes)
    {
        if (recording || !frames || frames > 4096 || watchBytes > 512) return false;
        std::error_code ec;
        if (!std::filesystem::create_directory(path, ec)) return false;
        directory = path; limit = frames; bytes = watchBytes;
        count = 0; audioCount = 0; lastSample = 0; begun = false;
        rows.clear(); sound.clear();
        rows.open(directory / "frames.tsv");
        sound.open(directory / "audio.bin", std::ios::binary);
        recording = true;
        rows << "sequence\tnds_frame\tstart_tick\tend_tick\tkey_mask\taudio_offset\taudio_count\tram_hex\theld_left\theld_right\twatch_present\twatch_addresses\twatch_paths\n";
        if (!rows || !sound) { fail("io_error"); return false; }
        return true;
    }
    void beginFrame(uint64_t tick, int16_t left = 0, int16_t right = 0)
    {
        if (!recording) return;
        if (begun || (count && tick != lastEnd)) { fail("clock_discontinuity"); return; }
        begun = true; startTick = tick; heldLeft = left; heldRight = right; samples.clear();
    }
    void audio(uint64_t tick, uint32_t period, int16_t left, int16_t right)
    {
        if (!recording) return;
        if (!begun || tick <= startTick) { fail("audio_outside_frame"); return; }
        if (!period || (audioCount + samples.size() && tick - lastSample != period))
        { fail("audio_discontinuity"); return; }
        if (samples.size() >= 2048) { fail("audio_overflow"); return; }
        samples.push_back({tick, period, left, right}); lastSample = tick;
    }
    bool frame(uint32_t frame, uint64_t end, uint32_t mask,
               const uint32_t* top, const uint32_t* bottom, const std::vector<uint8_t>& ram,
               const std::vector<NativeWatchValue>& values = {})
    {
        if (!recording) return false;
        if (!begun || end <= startTick) { fail("clock_discontinuity"); return false; }
        if (count && frame != lastFrame + 1) { fail("frame_discontinuity"); return false; }
        if (ram.size() != bytes) { fail("watch_length"); return false; }
        if (!values.empty())
        {
            if (values.size() > 64) { fail("watch_metadata_budget"); return false; }
            std::vector<uint8_t> proof;
            for (const auto& value : values)
            {
                if (value.pointers.size() > 8 || value.pointers.size() != value.readAddresses.size()) { fail("watch_path_length"); return false; }
                proof.insert(proof.end(), value.bytes.begin(), value.bytes.end());
            }
            if (proof != ram) { fail("watch_payload_mismatch"); return false; }
        }
        if (samples.empty()) { fail("audio_missing"); return false; }
        if (!top || !bottom) { fail("native_planes_missing"); return false; }
        if (!samples.empty() && samples.back().tick > end) { fail("audio_outside_frame"); return false; }
        std::ostringstream name; name << std::setw(6) << std::setfill('0') << count << ".ppm";
        std::ofstream image(directory / name.str(), std::ios::binary);
        image << "P6\n256 384\n255\n";
        for (const auto plane : {top, bottom})
            for (unsigned i = 0; i < 256 * 192; ++i)
            { image.put(char(plane[i] >> 16)); image.put(char(plane[i] >> 8)); image.put(char(plane[i])); }
        image.close();
        for (const auto& s : samples)
        { le(sound,s.tick,8); le(sound,s.period,4); le(sound,uint16_t(s.left),2); le(sound,uint16_t(s.right),2); }
        rows << count << '\t' << frame << '\t' << startTick << '\t' << end << '\t' << mask
             << '\t' << audioCount << '\t' << samples.size() << '\t';
        for (auto byte : ram) rows << std::hex << std::setw(2) << std::setfill('0') << unsigned(byte);
        rows << std::dec << '\t' << heldLeft << '\t' << heldRight << '\t';
        for (const auto& value : values) rows << (value.present ? '1' : '0');
        rows << '\t';
        for (size_t i = 0; i < values.size(); ++i) { if (i) rows << ','; rows << values[i].address; }
        rows << '\t';
        for (size_t i = 0; i < values.size(); ++i)
        {
            if (i) rows << ';';
            if (values[i].pointers.empty()) rows << '-';
            for (size_t j = 0; j < values[i].pointers.size(); ++j)
            { if (j) rows << ','; rows << values[i].readAddresses[j] << ':' << values[i].pointers[j]; }
        }
        rows << '\n';
        rows.flush(); sound.flush();
        if (!image || !rows || !sound) { fail("io_error"); return false; }
        ++count; audioCount += samples.size(); lastFrame = frame; lastEnd = end; begun = false;
        if (count == limit) finish("complete", "");
        return true;
    }
};
