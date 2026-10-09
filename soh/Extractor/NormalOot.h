#pragma once

#include "BpsPatch.h"
#include <algorithm>
#include <filesystem>
#include <fstream>

namespace SohRom {
inline bool NormalizeRom(std::vector<uint8_t>& data, std::string& error) {
    if (data.size() < 4 || data.size() > 64 * 1024 * 1024 || data.size() % 4 != 0) {
        error = "Invalid ROM size.";
        return false;
    }
    const auto magic = ReadLe32(data, 0);
    if (magic == 0x12408037) {
        for (size_t i = 0; i < data.size(); i += 2) std::swap(data[i], data[i+1]);
    } else if (magic == 0x80371240) {
        for (size_t i = 0; i < data.size(); i += 4) std::reverse(data.begin()+i, data.begin()+i+4);
    } else if (magic != 0x40123780) {
        error = "Unrecognized N64 ROM byte order.";
        return false;
    }
    return true;
}

inline bool ReadFile(const std::filesystem::path& path, std::vector<uint8_t>& data, size_t limit,
                     std::string& error) {
    std::ifstream stream(path, std::ios::binary | std::ios::ate);
    const auto size = stream ? stream.tellg() : std::streampos(-1);
    if (size < 0 || static_cast<uint64_t>(size) > limit) {
        error = "Cannot read " + path.filename().string() + ". Check the assets folder.";
        return false;
    }
    data.resize(static_cast<size_t>(size));
    stream.seekg(0);
    if (!data.empty() && !stream.read(reinterpret_cast<char*>(data.data()), data.size())) {
        error = "Incomplete read of " + path.filename().string();
        return false;
    }
    return true;
}

// The reference pair is verified by build_normal_oot_patch.py and by extraction
// parity tests. Do not guess a patch for another regional/debug MQ revision.
inline bool ConvertMasterQuest(std::span<const uint8_t> source, const std::filesystem::path& assets,
                               std::vector<uint8_t>& output, std::string& error) {
    if (source.size() < 20 || source[16] != 0x1d || source[17] != 0x41 ||
        source[18] != 0x36 || source[19] != 0xf3) {
        error = "Normal-layout conversion currently supports PAL GameCube Master Quest. "
                "This MQ revision needs its own verified conversion data.";
        return false;
    }
    std::vector<uint8_t> patch;
    if (!ReadFile(assets / "normal-oot/pal-mq-to-ntsc10.bps", patch, 64 * 1024 * 1024, error)) return false;
    std::vector<uint8_t> converted;
    if (!ApplyBps(source, patch, converted, error, 32 * 1024 * 1024)) return false;
    if (converted.size() != 32 * 1024 * 1024 || converted[16] != 0xec || converted[17] != 0x70 ||
        converted[18] != 0x11 || converted[19] != 0xb7) {
        error = "Conversion did not produce the expected normal OoT revision.";
        return false;
    }
    output = std::move(converted);
    return true;
}
} // namespace SohRom
