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

// The catalog's dungeon/boss pools include both halves of a paired entrance.
// In particular a dungeon's outside exit is still a dungeon-pool endpoint.
// Scene 12 is Thieves' Hideout (interior pool), not a dungeon pool member.
inline bool IsDungeonPoolEndpoint(int id) {
    const auto* row = EntranceEndpointById(id);
    if (!row) return false;
    if (row->door >= 0) return true;
    const auto dungeonScene = [](int scene) {
        return (scene >= 0 && scene <= 11) || scene == 13 || (scene >= 17 && scene <= 24);
    };
    const auto* back = EntranceEndpointById(row->reverse);
    return dungeonScene(row->scene) || (back && dungeonScene(back->scene));
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
            previousSceneReturn = false;
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
        const auto riverRevision = settings.find("EntranceRiverPathsRevision");
        if (riverRevision != settings.end()) {
            if (riverRevision->second < 0 || riverRevision->second > 1) {
                error = "Unsupported Zora's River entrance policy";
                return false;
            }
            if (riverRevision->second == 1 && (next.contains(234) || next.contains(385)) &&
                (!next.contains(473) || !next.contains(785))) {
                error = "The entrance map is missing a Zora's River water path";
                return false;
            }
            if (riverRevision->second == 0) {
                for (const auto& [source, target] : next) {
                    if (source == 473 || source == 785 || target == 473 || target == 785) {
                        error = "Water-path endpoints require the independent Zora's River entrance policy";
                        return false;
                    }
                }
            }
        }
        for (const auto& [id, target] : next) {
            const auto* a = EntranceEndpointById(id);
            const auto* b = EntranceEndpointById(target);
            if (a->reverse < 0) continue; // One-way routes cannot invent a return.
            const auto reverse = next.find(b->reverse);
            if (b->reverse < 0 || reverse == next.end() || reverse->second != a->reverse) {
                error = "Entrance pairs are decoupled"; return false;
            }
        }
        const auto value = [&](const char* key) {
            const auto it = settings.find(key);
            return it == settings.end() ? 0 : it->second;
        };
        const int poolRevision = value("EntrancePoolPolicyRevision");
        const int mixedMask = value("EntranceMixedPoolMask");
        const int mixedOutside = value("DungeonDoorMixedOutside");
        constexpr int dungeonMask = (1 << 2) | (1 << 4) | (1 << 10);
        constexpr int doorMask = 1 << 10;
        constexpr int allMask = (1 << 11) - 1;
        const bool selectedOutside = (mixedMask & doorMask) != 0 &&
                                     (mixedMask & (allMask ^ dungeonMask)) != 0;
        if (poolRevision < 0 || poolRevision > 1 || mixedMask < 0 || (mixedMask & ~allMask) != 0 ||
            (mixedOutside != 0 && mixedOutside != 1) ||
            ((poolRevision != 0 || mixedMask != 0 || mixedOutside != 0) &&
             (mixedOutside != static_cast<int>(selectedOutside) ||
              ((mixedMask & doorMask) != 0 && value("ShuffleDungeonDoors") == 0)))) {
            error = "Invalid dungeon entrance mixed-pool policy";
            return false;
        }
        previousSceneReturn = selectedOutside;
        // Cached older seeds omit the effective pool mask. Their actual paired
        // routes identify cross-category door mixing without interpreting the
        // old broad MixedEntrances flag as dungeon-door participation.
        if (poolRevision == 0 && mixedMask == 0 && mixedOutside == 0) {
            for (const auto& [source, target] : next) {
                const auto* endpoint = EntranceEndpointById(source);
                if (endpoint->door >= 0 && !IsDungeonPoolEndpoint(target)) {
                    previousSceneReturn = true;
                    break;
                }
            }
        }
        routes = std::move(next);
        return true;
    }
    void Reset() { routes.clear(); previousSceneReturn = false; }
    int Destination(int source) const {
        const auto it = FindSource(source);
        return it == routes.end() ? source : it->second;
    }
    bool Contains(int source) const { return FindSource(source) != routes.end(); }
    bool Active() const { return !routes.empty(); }
    bool UsesPreviousSceneReturn() const { return Active() && previousSceneReturn; }
    const std::map<int, int>& Routes() const { return routes; }
  private:
    std::map<int, int>::const_iterator FindSource(int source) const {
        const auto exact = routes.find(source);
        if (exact != routes.end()) return exact;
        // Keep older saved maps byte-for-byte while honoring their former
        // water-to-land destination aliases. Check/recovery callers still use
        // the raw physical source. Explicit water mappings always take priority.
        if (source == 473) return routes.find(234); // Hyrule Field -> river water path
        if (source == 785) return routes.find(385); // River -> Hyrule Field water path
        return routes.end();
    }
    std::map<int, int> routes;
    bool previousSceneReturn = false;
};
} // namespace SohExtreme
