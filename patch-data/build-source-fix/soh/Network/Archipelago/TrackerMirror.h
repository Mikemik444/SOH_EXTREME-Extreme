#pragma once
// Read-only Universal Tracker snapshots. No game types, items, or receipt writes.
// Bounds and session checks apply before a snapshot can replace displayed data.
#include <algorithm>
#include <cstdint>
#include <cstddef>
#include <iterator>
#include <limits>
#include <set>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace SohExtreme {
constexpr size_t kTrackerMaxEntries = 20000;
constexpr size_t kTrackerMaxBytes = 750000;
constexpr const char* kTrackerProtocol = "SOHExtremeFinder1";
constexpr const char* kTrackerVersion = "0.11.22";
struct TrackerRow {
    int64_t id = 0;
    uint8_t state = 0; // 1 normal; 2 UT's separate glitched state
    std::string name;
    std::string region;
};
struct TrackerSnapshot {
    std::string nonce, producer, version;
    uint32_t slot = 0, manualCount = 0, ignoredCount = 0;
    uint64_t request = 0, revision = 0, received = 0;
    std::set<int64_t> active, checked;
    std::vector<TrackerRow> rows;
};
inline std::vector<uint8_t> DecodeTrackerBase64(const std::string& encoded) {
    if (encoded.empty() || encoded.size() % 4 || encoded.size() > ((kTrackerMaxBytes + 2) / 3) * 4)
        throw std::invalid_argument("Invalid tracker payload size");
    auto digit = [](char c) -> int {
        if (c >= 'A' && c <= 'Z') return c - 'A';
        if (c >= 'a' && c <= 'z') return c - 'a' + 26;
        if (c >= '0' && c <= '9') return c - '0' + 52;
        if (c == '+') return 62;
        if (c == '/') return 63;
        return -1;
    };
    std::vector<uint8_t> out;
    out.reserve((encoded.size() / 4) * 3);
    for (size_t i = 0; i < encoded.size(); i += 4) {
        const int a = digit(encoded[i]), b = digit(encoded[i + 1]);
        const int c = encoded[i + 2] == '=' ? 0 : digit(encoded[i + 2]);
        const int d = encoded[i + 3] == '=' ? 0 : digit(encoded[i + 3]);
        const bool pad2 = encoded[i + 2] == '=', pad1 = encoded[i + 3] == '=';
        if (a < 0 || b < 0 || c < 0 || d < 0 || (pad2 && !pad1) ||
            ((pad1 || pad2) && i + 4 != encoded.size()) || (pad2 && (b & 15)) || (pad1 && !pad2 && (c & 3)))
            throw std::invalid_argument("Invalid tracker base64");
        const uint32_t bits = static_cast<uint32_t>((a << 18) | (b << 12) | (c << 6) | d);
        out.push_back(static_cast<uint8_t>(bits >> 16));
        if (!pad2) out.push_back(static_cast<uint8_t>(bits >> 8));
        if (!pad1) out.push_back(static_cast<uint8_t>(bits));
    }
    if (out.size() > kTrackerMaxBytes) throw std::invalid_argument("Tracker payload too large");
    return out;
}
inline TrackerSnapshot DecodeTrackerSnapshot(const std::string& encoded) {
    const auto data = DecodeTrackerBase64(encoded);
    size_t pos = 0;
    auto integer = [&](size_t bytes) -> uint64_t {
        if (bytes > data.size() - pos) throw std::invalid_argument("Truncated tracker payload");
        uint64_t result = 0;
        for (size_t i = 0; i < bytes; ++i) result |= uint64_t(data[pos++]) << (8 * i);
        return result;
    };
    auto text = [&]() -> std::string {
        const size_t len = static_cast<size_t>(integer(2));
        if (len > 2048 || len > data.size() - pos) throw std::invalid_argument("Invalid tracker text size");
        std::string result(data.begin() + pos, data.begin() + pos + len);
        pos += len;
        // UTF-8 can remain UTF-8 for ImGui; C control characters and NUL cannot
        // become labels or format strings (rendering always uses TextUnformatted).
        for (unsigned char c : result) if (c < 32 || c == 127) throw std::invalid_argument("Invalid tracker label");
        return result;
    };
    const uint8_t magic[] = {'S','E','F','T','1',0};
    if (data.size() < sizeof(magic) || !std::equal(std::begin(magic), std::end(magic), data.begin()))
        throw std::invalid_argument("Unknown tracker protocol");
    pos = sizeof(magic);
    TrackerSnapshot result;
    result.nonce = text(); result.producer = text(); result.version = text();
    if (result.nonce.size() != 32 || result.producer.empty() || result.producer.size() > 64)
        throw std::invalid_argument("Invalid tracker session");
    result.slot = static_cast<uint32_t>(integer(4));
    result.request = integer(8); result.revision = integer(8); result.received = integer(8);
    result.manualCount = static_cast<uint32_t>(integer(4)); result.ignoredCount = static_cast<uint32_t>(integer(4));
    auto locations = [&](std::set<int64_t>& out) {
        const auto count = integer(4);
        if (count > kTrackerMaxEntries) throw std::invalid_argument("Too many tracker locations");
        for (uint64_t i = 0; i < count; ++i) {
            const uint64_t id = integer(8);
            if (!id || id > uint64_t(std::numeric_limits<int64_t>::max()) || !out.insert(static_cast<int64_t>(id)).second)
                throw std::invalid_argument("Invalid or duplicate tracker location");
        }
    };
    locations(result.active); locations(result.checked);
    if (!std::includes(result.active.begin(), result.active.end(), result.checked.begin(), result.checked.end()))
        throw std::invalid_argument("Checked location outside active set");
    const auto count = integer(4);
    if (count > kTrackerMaxEntries) throw std::invalid_argument("Too many tracker rows");
    std::set<int64_t> seen;
    for (uint64_t i = 0; i < count; ++i) {
        TrackerRow row;
        const uint64_t id = integer(8);
        if (!id || id > uint64_t(std::numeric_limits<int64_t>::max())) throw std::invalid_argument("Invalid row ID");
        row.id = static_cast<int64_t>(id); row.state = static_cast<uint8_t>(integer(1));
        row.name = text(); row.region = text();
        if ((row.state != 1 && row.state != 2) || !result.active.count(row.id) || result.checked.count(row.id) ||
            !seen.insert(row.id).second || row.name.empty()) throw std::invalid_argument("Invalid tracker row");
        result.rows.push_back(std::move(row));
    }
    if (pos != data.size()) throw std::invalid_argument("Trailing tracker data");
    return result;
}

class TrackerMirrorState {
  public:
    void Reset(const std::string& nonce) {
        nonce_ = nonce; snapshot_ = {}; producer_.clear(); hasSnapshot_ = false;
        request_ = 0; lastReceive_ = 0;
    }
    uint64_t NextRequest() { return ++request_; }
    const std::string& Nonce() const { return nonce_; }
    bool Accept(TrackerSnapshot candidate, uint32_t slot, double now, std::string& error) {
        if (candidate.version != kTrackerVersion) { error = "Tracker version mismatch; use 0.11.22 on both sides."; return false; }
        if (nonce_.empty() || candidate.nonce != nonce_ || candidate.slot != slot ||
            candidate.request == 0 || candidate.request > request_) { error = "Wrong tracker session."; return false; }
        if (!producer_.empty() && producer_ != candidate.producer && now - lastReceive_ <= 10.0) {
            error = "AP tracker session changed; restarting synchronization."; return false;
        }
        if (producer_ == candidate.producer && hasSnapshot_ &&
            (candidate.request < snapshot_.request || candidate.revision <= snapshot_.revision)) {
            error = "Out-of-order tracker snapshot."; return false;
        }
        producer_ = candidate.producer; snapshot_ = std::move(candidate);
        hasSnapshot_ = true; lastReceive_ = now; error.clear(); return true;
    }
    const TrackerSnapshot* Current(uint32_t slot, uint64_t received, const std::set<int64_t>& active,
                                   const std::set<int64_t>& checked, double now, std::string& status) const {
        if (!hasSnapshot_) { status = "Starting the automatic AP tracker..."; return nullptr; }
        if (now - lastReceive_ > 10.0) { status = "Tracker snapshot expired; waiting for a live update."; return nullptr; }
        if (snapshot_.slot != slot || snapshot_.active != active) { status = "Tracker location manifest differs from this slot."; return nullptr; }
        if (snapshot_.received != received || snapshot_.checked != checked) {
            status = "Synchronizing AP items and checked locations with Universal Tracker..."; return nullptr;
        }
        status = "Automatic AP tracker - Universal Tracker rules.";
        return &snapshot_;
    }
  private:
    std::string nonce_, producer_;
    uint64_t request_ = 0;
    double lastReceive_ = 0;
    bool hasSnapshot_ = false;
    TrackerSnapshot snapshot_;
};
} // namespace SohExtreme
