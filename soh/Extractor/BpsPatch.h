#pragma once

#include <array>
#include <cstdint>
#include <cstring>
#include <limits>
#include <span>
#include <string>
#include <vector>
#include <utility>

namespace SohRom {
// BPS specification by byuu (public domain):
// https://github.com/Alcaro/Flips/blob/master/bps_spec.md
inline uint32_t Crc32(std::span<const uint8_t> data) {
    static constexpr auto table = [] {
        std::array<uint32_t, 256> values{};
        for (uint32_t i = 0; i < values.size(); ++i) {
            uint32_t crc = i;
            for (int j = 0; j < 8; ++j) crc = (crc >> 1) ^ ((crc & 1) ? 0xedb88320u : 0);
            values[i] = crc;
        }
        return values;
    }();
    uint32_t crc = 0xffffffffu;
    for (auto byte : data) crc = table[(crc ^ byte) & 255] ^ (crc >> 8);
    return crc ^ 0xffffffffu;
}

inline uint32_t ReadLe32(std::span<const uint8_t> data, size_t pos) {
    return uint32_t(data[pos]) | (uint32_t(data[pos+1]) << 8) |
           (uint32_t(data[pos+2]) << 16) | (uint32_t(data[pos+3]) << 24);
}

// Bounds apply before allocation/copy. A failure leaves the caller's output intact.
inline bool ApplyBps(std::span<const uint8_t> source, std::span<const uint8_t> patch,
                     std::vector<uint8_t>& output, std::string& error, size_t maxOutput = 64 * 1024 * 1024) {
    auto fail = [&](const char* message) { error = message; return false; };
    error.clear();
    if (patch.size() < 19 || std::memcmp(patch.data(), "BPS1", 4) != 0)
        return fail("Invalid normal-layout conversion patch header.");
    const size_t end = patch.size() - 12;
    if (Crc32(patch.first(patch.size()-4)) != ReadLe32(patch, patch.size()-4))
        return fail("Normal-layout conversion patch checksum failed.");
    if (Crc32(source) != ReadLe32(patch, end))
        return fail("This ROM does not match the normal-layout conversion patch.");
    size_t cursor = 4;
    auto number = [&](uint64_t& value) {
        value = 0;
        uint64_t shift = 1;
        constexpr auto max = std::numeric_limits<uint64_t>::max();
        while (cursor < end) {
            uint8_t byte = patch[cursor++];
            if ((byte & 127) > (max-value)/shift) return false;
            value += (byte & 127)*shift;
            if (byte & 128) return true;
            if (shift > (max >> 7)) return false;
            shift <<= 7;
            if (value > max-shift) return false;
            value += shift;
        }
        return false;
    };
    uint64_t sourceSize, targetSize, metadataSize;
    if (!number(sourceSize) || !number(targetSize) || !number(metadataSize) ||
        sourceSize != source.size() || targetSize > maxOutput || metadataSize > end-cursor)
        return fail("Invalid normal-layout conversion patch sizes.");
    cursor += static_cast<size_t>(metadataSize);
    std::vector<uint8_t> result(static_cast<size_t>(targetSize));
    size_t written = 0, sourceRelative = 0, targetRelative = 0;
    while (cursor < end) {
        uint64_t action;
        if (!number(action)) return fail("Invalid conversion command.");
        const uint64_t length64 = (action >> 2) + 1;
        if (length64 > result.size()-written) return fail("Conversion exceeds output size.");
        const size_t length = static_cast<size_t>(length64);
        switch (action & 3) {
            case 0:
                if (written > source.size() || length > source.size()-written)
                    return fail("Conversion reads beyond the source ROM.");
                std::memcpy(result.data()+written, source.data()+written, length);
                break;
            case 1:
                if (length > end-cursor) return fail("Truncated conversion data.");
                std::memcpy(result.data()+written, patch.data()+cursor, length);
                cursor += length;
                break;
            case 2:
            case 3: {
                uint64_t delta;
                if (!number(delta)) return fail("Invalid conversion offset.");
                size_t& relative = (action & 3) == 2 ? sourceRelative : targetRelative;
                const uint64_t distance = delta >> 1;
                if (delta & 1) {
                    if (distance > relative) return fail("Conversion reads before the input.");
                    relative -= static_cast<size_t>(distance);
                } else {
                    if (distance > std::numeric_limits<size_t>::max()-relative)
                        return fail("Conversion offset overflow.");
                    relative += static_cast<size_t>(distance);
                }
                if ((action & 3) == 2) {
                    if (relative > source.size() || length > source.size()-relative)
                        return fail("Conversion reads beyond the source ROM.");
                    std::memcpy(result.data()+written, source.data()+relative, length);
                } else {
                    if (relative >= written) return fail("Conversion refers to unwritten output.");
                    // BPS TargetCopy intentionally allows overlapping copies (RLE).
                    for (size_t i = 0; i < length; ++i) result[written+i] = result[relative+i];
                }
                relative += length;
                break;
            }
        }
        written += length;
    }
    if (written != result.size() || Crc32(result) != ReadLe32(patch, end+4))
        return fail("Normal-layout conversion output verification failed.");
    output = std::move(result);
    return true;
}
} // namespace SohRom
