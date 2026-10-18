#pragma once
#include <cstdint>
#include <map>
#include <string>
#include <unordered_map>
#include "EntranceDestinationPolicy.h"

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

// Carried Ruto survives native room loads, but not a full scene reload. These
// six Jabu door pairs keep the native carry route used by progression logic.
// Their explicit identity mappings still award ordinary door-crossing checks.
// Keep this contract aligned with EntranceRandomizer.LOCAL_CARRIER_DOORS.
inline bool IsLocalCarrierDoor(int id) {
    const auto* row = EntranceEndpointById(id);
    if (!row || row->sourceScene != 2) return false;
    switch (row->door) {
        case 2: case 4: case 11: case 12: case 14: case 21: return true;
        default: return false;
    }
}

// Slot data is authoritative. Neither a local menu nor a reconnect rerolls it.
// Validation is atomic: malformed maps never leave a half-applied route table.
class EntranceRouting {
  public:
    bool Configure(const std::unordered_map<std::string, int>& settings, std::string& error) {
        std::map<int, int> next;
        const auto version = settings.find("EntranceRandomizerRevision");
        if (version == settings.end() || version->second == 0) {
            // A genuinely disabled/legacy seed may omit the map. A seed that
            // requests shuffled entrances must never quietly become vanilla.
            bool requested = false;
            for (const char* key : {"ShuffleInteriorsEntrances", "ShuffleThievesHideoutEntrances",
                    "ShuffleDungeonsEntrances", "ShuffleGanonTowerEntrance", "ShuffleBossEntrances",
                    "ShuffleGrottosEntrances", "ShuffleOverworldEntrances", "ShuffleOwlDrops",
                    "ShuffleWarpSongs", "ShuffleOverworldSpawns", "ShuffleDungeonDoors"}) {
                const auto flag = settings.find(key);
                requested |= flag != settings.end() && flag->second != 0;
            }
            for (const auto& [key, value] : settings) {
                if (key.starts_with("EntranceMap.")) requested = true;
            }
            if (requested) {
                error = "This seed requests shuffled entrances but has no versioned entrance map. "
                        "Regenerate it with the matching SOH-EXTREME APWorld.";
                return false;
            }
            routes.clear();
            return true;
        }
        if (version->second != 1) { error = "Unsupported entrance mapping revision"; return false; }
        const auto policyVersion = settings.find("EntranceDestinationPolicyRevision");
        if (policyVersion != settings.end() && policyVersion->second != kEntranceDestinationPolicyRevision) {
            error = "Unsupported entrance destination policy revision";
            return false;
        }
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
            const auto* sourcePolicy = EntranceDestinationById(id);
            const auto* targetPolicy = EntranceDestinationById(value);
            if (!sourcePolicy || !targetPolicy) {
                error = "Entrance endpoint has no verified playable destination";
                return false;
            }
            if ((sourcePolicy->sourceAgeMask & targetPolicy->arrivalAgeMask) == 0) {
                error = "Entrance destination cannot be used at the source's required age";
                return false;
            }
            if (IsLocalCarrierDoor(id) && value != id) {
                error = "This seed shuffles a Jabu-Jabu door needed to carry Ruto. "
                        "Generate a new seed with the matching SOH-EXTREME APWorld.";
                return false;
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
