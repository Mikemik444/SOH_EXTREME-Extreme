#pragma once
#include <cstdint>
#include <map>
#include <string>
#include <unordered_map>

namespace SohExtreme {
struct EntranceEndpoint {
    int id, reverse, scene, sourceScene;
    int64_t check;
    int door, side, fromRoom, room, anchor, x, y, z, yaw;
    const char* name;
};
inline constexpr EntranceEndpoint kEntranceEndpoints[] = {
#include "EntranceRandomizerData.inc"
};
inline const EntranceEndpoint* EntranceEndpointById(int id) {
    for (const auto& row : kEntranceEndpoints) if (row.id == id) return &row;
    return nullptr;
}

// Slot data is authoritative. Neither a local menu nor a reconnect rerolls it.
// Validation is atomic: malformed maps never leave a half-applied route table.
class EntranceRouting {
  public:
    bool Configure(const std::unordered_map<std::string, int>& settings, std::string& error) {
        std::map<int, int> next;
        const auto version = settings.find("EntranceRandomizerRevision");
        if (version == settings.end() || version->second == 0) { routes.clear(); return true; }
        if (version->second != 1) { error = "Unsupported entrance mapping revision"; return false; }
        for (const auto& [key, value] : settings) {
            if (!key.starts_with("EntranceMap.")) continue;
            const auto idText = key.substr(12);
            size_t used = 0; int id;
            try { id = std::stoi(idText, &used); }
            catch (...) { error = "Malformed entrance source"; return false; }
            const auto* source = EntranceEndpointById(id);
            if (used != idText.size() || !source || !EntranceEndpointById(value) || !next.emplace(id, value).second) {
                error = "Unknown or duplicate entrance endpoint"; return false;
            }
        }
        if (next.empty()) { error = "Enabled entrance randomizer has no mapping"; return false; }
        for (const auto& [id, target] : next) {
            const auto* a = EntranceEndpointById(id);
            const auto* b = EntranceEndpointById(target);
            if (a->reverse < 0) continue; // One-way routes cannot invent a return.
            const auto reverse = next.find(b->reverse);
            if (b->reverse < 0 || reverse == next.end() || reverse->second != a->reverse) {
                error = "Entrance pairs are decoupled"; return false;
            }
        }
        routes = std::move(next);
        return true;
    }
    void Reset() { routes.clear(); }
    int Destination(int source) const {
        const auto it = routes.find(source);
        return it == routes.end() ? source : it->second;
    }
    bool Contains(int source) const { return routes.contains(source); }
    bool Active() const { return !routes.empty(); }
    const std::map<int, int>& Routes() const { return routes; }
  private:
    std::map<int, int> routes;
};
} // namespace SohExtreme
