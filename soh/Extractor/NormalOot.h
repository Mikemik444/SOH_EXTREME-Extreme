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
    // Match Extractor::ValidateAndFixRom: some MQ debug dumps carry a patched
    // US region byte. Only repair the private working copy, never the input file.
    if (data.size() >= 64 && data[16] == 0x91 && data[17] == 0x7d &&
        data[18] == 0x18 && data[19] == 0xf6) data[0x3e] = 'P';
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

// Each reference pair is verified by byte-for-byte native conversion tests.
// The BPS source checksum distinguishes dumps sharing the same header CRC.
inline bool ConvertMasterQuest(std::span<const uint8_t> source, const std::filesystem::path& assets,
                               std::vector<uint8_t>& output, std::string& error) {
    const char* patchName = nullptr;
    if (source.size() >= 20) {
        const auto header = ReadLe32(source, 16);
        if (header == 0xf336411d) patchName = "normal-oot/pal-mq-to-ntsc10.bps";
        if (header == 0xf6187d91) patchName = "normal-oot/mq-debug-to-ntsc10.bps";
    }
    if (patchName == nullptr) {
        error = "Normal-layout conversion supports PAL GameCube Master Quest and the verified 64 MB MQ Debug dump. "
                "This MQ revision needs its own verified conversion data.";
        return false;
    }
    std::vector<uint8_t> patch;
    if (!ReadFile(assets / patchName, patch, 64 * 1024 * 1024, error)) return false;
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
