#pragma once
// Per-capture execution hooks for the native recorder.
//  - Call log: a list of ARM9 instruction addresses. Each time the interpreter is
//    about to execute one, the core reports (pc, opcode, r0-r15); the hit is held
//    until the frame row is written and then appended to calls.tsv with that row's
//    sequence and nds_frame.
//  - List walks: bounded linked-list reads taken once per completed frame, after the
//    watches, into list-frames.tsv and list-nodes.tsv.
// Both only read emulator state. Formats are documented in scripts/emu/README.md.
#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

struct NativeListField
{
    std::vector<int32_t> path;   // node+path[0], then each later entry: pointer hop, add
    uint32_t length = 0;
    bool optional = false;       // a null hop marks the field absent instead of failing
};

struct NativeList
{
    uint32_t address = 0;        // head chain: address, then pointer hop + offset per entry;
    std::vector<int32_t> offsets; // the word at the final address is the first node
    int32_t next = 0;            // node offset of the next-node pointer
    uint32_t limit = 0;          // nodes walked per frame
    std::vector<NativeListField> fields;
};

struct NativeCallHit { uint32_t pc, insn, r[8], lr; };

class NativeHooks
{
    std::vector<NativeCallHit> pending;
    std::ofstream calls, frames, nodes;
    bool overflow = false;

    static bool ram(int64_t address, uint32_t length, bool aligned = false)
    {
        return address >= 0x02000000 && address + length <= 0x02400000 && (!aligned || address % 4 == 0);
    }
    static bool code(uint32_t pc)
    {
        return pc % 2 == 0 && ((pc >= 0x01FF8000 && pc < 0x02000000) || (pc >= 0x02000000 && pc < 0x02400000));
    }
    static std::string join(const std::vector<int32_t>& values)
    {
        std::ostringstream out;
        for (size_t i = 0; i < values.size(); ++i) { if (i) out << ','; out << values[i]; }
        return out.str();
    }

public:
    static constexpr size_t MaxPCs = 64, MaxLists = 4, MaxLimit = 32, MaxFields = 16, MaxNodeBytes = 128;
    static constexpr size_t MaxHitsPerFrame = 4096;
    std::vector<uint32_t> pcs;   // sorted by validate()
    std::vector<NativeList> lists;

    bool enabled() const { return !pcs.empty() || !lists.empty(); }
    bool watching(uint32_t pc) const { return std::binary_search(pcs.begin(), pcs.end(), pc); }

    void validate()
    {
        std::sort(pcs.begin(), pcs.end());
        if (pcs.size() > MaxPCs || std::adjacent_find(pcs.begin(), pcs.end()) != pcs.end()
            || !std::all_of(pcs.begin(), pcs.end(), code))
            throw std::invalid_argument("invalid_call_pcs");
        if (lists.size() > MaxLists) throw std::invalid_argument("list_budget");
        for (const auto& list : lists)
        {
            uint32_t bytes = 0;
            if (!list.limit || list.limit > MaxLimit || list.fields.empty() || list.fields.size() > MaxFields
                || list.offsets.size() > 8 || !ram(list.address, 4, true))
                throw std::invalid_argument("invalid_list_recipe");
            for (const auto& field : list.fields)
            {
                bytes += field.length;
                if (!field.length || field.path.empty() || field.path.size() > 9
                    || (field.optional && field.path.size() < 2))
                    throw std::invalid_argument("invalid_list_recipe");
            }
            if (bytes > MaxNodeBytes) throw std::invalid_argument("invalid_list_recipe");
        }
    }

    // The capture directory already exists; writes the registration files and opens the logs.
    bool start(const std::filesystem::path& directory)
    {
        if (!std::filesystem::is_directory(directory)) return false;
        pending.clear(); overflow = false;
        std::ofstream spec(directory / "hooks.json");
        spec << "{\"version\":1,\"call_pcs\":" << pcs.size() << ",\"lists\":" << lists.size() << "}\n";
        bool ok = bool(spec);
        if (!pcs.empty())
        {
            std::ofstream list(directory / "call-pcs.tsv");
            list << "pc\n";
            for (auto pc : pcs) list << pc << '\n';
            calls.open(directory / "calls.tsv");
            calls << "sequence\tnds_frame\tpc\tinsn\tr0\tr1\tr2\tr3\tr4\tr5\tr6\tr7\tlr\n";
            ok = ok && list && calls;
        }
        if (!lists.empty())
        {
            std::ofstream list(directory / "lists.tsv");
            list << "list\taddress\toffsets\tnext\tlimit\tfields\n";
            for (size_t i = 0; i < lists.size(); ++i)
            {
                const auto& l = lists[i];
                list << i << '\t' << l.address << '\t' << join(l.offsets) << '\t' << l.next << '\t' << l.limit << '\t';
                for (size_t j = 0; j < l.fields.size(); ++j)
                    list << (j ? ";" : "") << join(l.fields[j].path) << ':' << l.fields[j].length << ':' << l.fields[j].optional;
                list << '\n';
            }
            frames.open(directory / "list-frames.tsv");
            frames << "sequence\tnds_frame\tlist\tpresent\tcount\ttruncated\thead_path\n";
            nodes.open(directory / "list-nodes.tsv");
            nodes << "sequence\tnds_frame\tlist\tnode\taddress\tnext\tfield_present\tfield_addresses\tdata_hex\n";
            ok = ok && list && frames && nodes;
        }
        return ok;
    }

    // Called from the ARM9 interpreter, before the instruction at pc executes.
    void hit(uint32_t pc, uint32_t insn, const uint32_t* r)
    {
        if (pending.size() >= MaxHitsPerFrame) { overflow = true; return; }
        NativeCallHit h{pc, insn, {}, r[14]};
        std::copy(r, r + 8, h.r);
        pending.push_back(h);
    }

    // After the frame row is written: flush this frame's hits and walk the lists.
    template <typename Read32, typename Read8>
    bool frame(uint32_t sequence, uint32_t ndsFrame, Read32 read32, Read8 read8, std::string& error)
    {
        if (overflow) { error = "call_log_overflow"; pending.clear(); return false; }
        for (const auto& h : pending)
        {
            calls << sequence << '\t' << ndsFrame << '\t' << h.pc << '\t' << h.insn;
            for (auto value : h.r) calls << '\t' << value;
            calls << '\t' << h.lr << '\n';
        }
        pending.clear();
        for (size_t index = 0; index < lists.size(); ++index)
        {
            const auto& list = lists[index];
            std::ostringstream path;
            int64_t address = list.address;
            bool present = true;
            auto hop = [&](int64_t location) -> uint32_t {
                if (!ram(location, 4, true)) throw std::invalid_argument("list_pointer_unreachable");
                uint32_t value = read32(uint32_t(location));
                path << (path.tellp() > 0 ? "," : "") << location << ':' << value;
                return value;
            };
            std::vector<std::string> rows;
            uint32_t count = 0, node = 0;
            try
            {
                for (auto offset : list.offsets)
                {
                    uint32_t pointer = hop(address);
                    if (!pointer) { present = false; break; }
                    address = int64_t(pointer) + offset;
                }
                if (present) node = hop(address);
                while (present && node && count < list.limit)
                {
                    if (!ram(node, 4, true)) throw std::invalid_argument("list_pointer_unreachable");
                    std::string flags, addresses, data;
                    for (const auto& field : list.fields)
                    {
                        int64_t at = int64_t(node) + field.path[0];
                        bool here = true;
                        for (size_t k = 1; k < field.path.size(); ++k)
                        {
                            if (!ram(at, 4, true)) throw std::invalid_argument("list_pointer_unreachable");
                            uint32_t pointer = read32(uint32_t(at));
                            if (!pointer)
                            {
                                if (!field.optional) throw std::invalid_argument("required_list_field_absent");
                                here = false; break;
                            }
                            at = int64_t(pointer) + field.path[k];
                        }
                        if (here && !ram(at, field.length)) throw std::invalid_argument("list_pointer_unreachable");
                        std::ostringstream hex;
                        for (uint32_t b = 0; b < field.length; ++b)
                            hex << std::hex << std::setw(2) << std::setfill('0') << unsigned(here ? read8(uint32_t(at + b)) : 0);
                        flags += here ? '1' : '0';
                        addresses += (flags.size() > 1 ? "," : "") + std::to_string(here ? at : 0);
                        data += hex.str();
                    }
                    int64_t link = int64_t(node) + list.next;
                    if (!ram(link, 4, true)) throw std::invalid_argument("list_pointer_unreachable");
                    uint32_t next = read32(uint32_t(link));
                    std::ostringstream row;
                    row << sequence << '\t' << ndsFrame << '\t' << index << '\t' << count << '\t' << node << '\t'
                        << next << '\t' << flags << '\t' << addresses << '\t' << data << '\n';
                    rows.push_back(row.str());
                    node = next; ++count;
                }
            }
            catch (const std::invalid_argument& e) { error = e.what(); return false; }
            frames << sequence << '\t' << ndsFrame << '\t' << index << '\t' << present << '\t' << count << '\t'
                   << (present && node ? 1 : 0) << '\t' << path.str() << '\n';
            for (const auto& row : rows) nodes << row;
        }
        calls.flush(); frames.flush(); nodes.flush();
        if ((calls.is_open() && !calls) || (frames.is_open() && !frames) || (nodes.is_open() && !nodes))
        { error = "io_error"; return false; }
        return true;
    }

    void close() { pending.clear(); calls.close(); frames.close(); nodes.close(); }
};
