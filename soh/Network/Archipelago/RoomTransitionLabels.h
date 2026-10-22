#pragma once

#include <algorithm>
#include <cstdint>
#include <map>
#include <string>
#include <utility>

#include "EntranceRouting.h"
#include "TrackerCheckLabels.h"

namespace SohExtreme {

inline std::string ReadableEntranceDestination(std::string name) {
    // Older native scene names append a spawn ordinal, for example "Market
    // Back Alley (4)". It is not the engine room displayed on the next line.
    const auto ordinal = name.rfind(" (");
    if (ordinal != std::string::npos && name.back() == ')' && ordinal + 3 < name.size() &&
        std::all_of(name.begin() + ordinal + 2, name.end() - 1, [](char value) {
            return value >= '0' && value <= '9';
        })) {
        name.erase(ordinal);
    }
    // These boss return endpoints intentionally have no AP check. Their
    // immutable runtime names still contain native region identifiers.
    const std::pair<const char*, const char*> nativeRegions[] = {
        { "RR_FOREST_TEMPLE_BOSS_ENTRYWAY", "Forest Temple: Before the Boss Room" },
        { "RR_FIRE_TEMPLE_BOSS_ENTRYWAY", "Fire Temple: Before the Boss Room" },
        { "RR_WATER_TEMPLE_BOSS_ENTRYWAY", "Water Temple: Before the Boss Room" },
        { "RR_SPIRIT_TEMPLE_BOSS_ENTRYWAY", "Spirit Temple: Before the Boss Room" },
        { "RR_SHADOW_TEMPLE_BOSS_ENTRYWAY", "Shadow Temple: Before the Boss Room" },
        { "RR_JABU_JABUS_BELLY_BOSS_EXIT", "Jabu Jabu's Belly: Exit from the Boss Room" },
    };
    for (const auto& [token, description] : nativeRegions) {
        if (name == token) return description;
    }
    const std::pair<const char*, const char*> areas[] = {
        { "MK ", "Market: " }, { "Kak ", "Kakariko Village: " },
        { "KF ", "Kokiri Forest: " }, { "LW ", "Lost Woods: " },
        { "SFM ", "Sacred Forest Meadow: " }, { "HF ", "Hyrule Field: " },
        { "LH ", "Lake Hylia: " }, { "LLR ", "Lon Lon Ranch: " },
        { "GY ", "Graveyard: " }, { "DMT ", "Death Mountain Trail: " },
        { "DMC ", "Death Mountain Crater: " }, { "GC ", "Goron City: " },
        { "ZR ", "Zora's River: " }, { "ZD ", "Zora's Domain: " },
        { "ZF ", "Zora's Fountain: " }, { "GV ", "Gerudo Valley: " },
        { "GF ", "Gerudo's Fortress: " }, { "HC ", "Hyrule Castle: " },
    };
    for (const auto& [prefix, area] : areas) {
        const std::string shortName(prefix);
        if (name.compare(0, shortName.size(), shortName) == 0) {
            name.replace(0, shortName.size(), area);
            break;
        }
    }
    return name;
}

// Display-only helpers. The destination endpoint is the arriving half of the
// installed mapping: its room is the room entered, not its fromRoom or reverse.
inline std::string EntranceArrivalDescription(const EntranceEndpoint& endpoint) {
    const auto* description = FindCheckDescription(endpoint.check);
    if (endpoint.door >= 0 && description != nullptr) {
        std::string label = CleanTrackerLabel(description->name);
        if (label.compare(0, 6, "Door: ") == 0) label.erase(0, 6);
        const auto separator = label.find(" -> ");
        if (separator == std::string::npos) {
            // Same-room maze passages have individually authored landmarks
            // and crossing directions. Do not collapse them to "Central Maze".
            return label;
        }
        std::string arrival = label.substr(separator + 4);
        const auto sceneEnd = label.find(": ");
        if (endpoint.sourceScene == endpoint.scene && sceneEnd < separator) {
            arrival.insert(0, label.substr(0, sceneEnd + 2));
        }
        return arrival;
    }
    std::string arrival(endpoint.name);
    const auto separator = arrival.find(" -> ");
    if (separator != std::string::npos) arrival.erase(0, separator + 4);
    return ReadableEntranceDestination(CleanTrackerLabel(std::move(arrival)));
}

inline const EntranceEndpoint* EntranceEndpointByCheck(int64_t check) {
    if (check <= 0) return nullptr; // Spawn and song-only endpoints have no check.
    static const std::map<int64_t, const EntranceEndpoint*> checks = [] {
        std::map<int64_t, const EntranceEndpoint*> result;
        for (const auto& endpoint : kEntranceEndpoints) {
            if (endpoint.check > 0) result.emplace(endpoint.check, &endpoint);
        }
        return result;
    }();
    const auto found = checks.find(check);
    return found != checks.end() ? found->second : nullptr;
}

inline std::string RoomDestinationLabel(const std::string& kind, const std::string& description, int room) {
    std::string text = kind + " to " + description;
    if (room >= 0) text += "\nRoom " + std::to_string(room);
    return text;
}

// A native hallway can enter a room containing several logical sectors. Use
// only their common room-level landmark; selecting one sector would imply an
// exact arrival that is not present in the authored physical door catalogue.
inline std::string NativeRoomDescription(int scene, int room) {
    static const std::map<std::pair<int, int>, std::string> names = [] {
        std::map<std::pair<int, int>, std::string> result;
        for (const auto& endpoint : kEntranceEndpoints) {
            if (endpoint.door < 0 || endpoint.room < 0) continue;
            std::string name = EntranceArrivalDescription(endpoint);
            const auto maze = name.find("Central Maze - ");
            if (maze != std::string::npos) name.erase(maze + 12);
            const auto key = std::make_pair(endpoint.scene, endpoint.room);
            const auto [it, inserted] = result.emplace(key, name);
            if (!inserted) {
                size_t common = 0;
                while (common < it->second.size() && common < name.size() &&
                       it->second[common] == name[common]) ++common;
                // Keep complete words when the common prefix ends mid-word.
                if (common < it->second.size() && common < name.size() && common > 0 &&
                    it->second[common] != ' ' && name[common] != ' ') {
                    const auto space = it->second.rfind(' ', common - 1);
                    common = space == std::string::npos ? 0 : space;
                }
                it->second.resize(common);
                while (!it->second.empty() && (it->second.back() == ' ' || it->second.back() == ':'))
                    it->second.pop_back();
            }
        }
        return result;
    }();
    const auto found = names.find({ scene, room });
    return found != names.end() ? found->second : "";
}

// EnHoll types 0/3/4/6 use the signed horizontal plane; types 2/5 use height.
// Room loading can run ahead of Link or lag behind him, so the engine's current
// room is not a reliable side indicator for these native passages.
inline int PassageSourceSide(int type, float localZ, float height) {
    if (type == 1) return height > 0.0f ? 0 : -1; // Downward-only drop.
    if (type == 2 || type == 5) return height > 0.0f ? 0 : 1;
    if (type == 0 || type == 3 || type == 4 || type == 6) return localZ < 0.0f ? 0 : 1;
    return -1;
}

inline std::string TrackerCheckDetailLine(int64_t location, const EntranceEndpoint* arrival = nullptr) {
    const auto* description = FindCheckDescription(location);
    if (description == nullptr) return "";
    if (description->door < 0) {
        if (arrival != nullptr && arrival->room >= 0) {
            return "Destination room " + std::to_string(arrival->room);
        }
        return description->fromRoom >= 0 ? "Room " + std::to_string(description->fromRoom) : "";
    }
    const int room = arrival != nullptr ? arrival->room : description->toRoom;
    std::string result = room >= 0 ? "Destination room " + std::to_string(room) : "Destination: scene entrance";
    result += " | From room " + std::to_string(description->fromRoom) +
              " | Door " + std::to_string(description->door + 1);
    if (description->fromRoom == description->toRoom && description->side >= 0) {
        result += " | Source side " + std::to_string(description->side + 1);
    }
    return result;
}

inline std::string TrackerDestinationLabel(int64_t location, std::string inputName,
                                           const EntranceEndpoint* arrival = nullptr) {
    std::string label = TrackerCheckLabel(location, inputName, false);
    if (arrival == nullptr) return label;
    const auto* physical = FindCheckDescription(location);
    if (physical == nullptr) return label;
    const std::string canonical = CleanTrackerLabel(physical->name);
    if (label.compare(0, canonical.size(), canonical) != 0) return label;
    const auto shuffled = label.find(" | Shuffled to: ");
    if (shuffled == std::string::npos) return label;

    // Replace only the known producer's mapped destination. Age suffixes and
    // player aliases remain in place; an unknown custom label stays intact.
    const std::string replacement = EntranceArrivalDescription(*arrival);
    size_t end = label.size();
    const auto annotation = label.find(" [", shuffled + 16);
    if (annotation != std::string::npos) end = annotation;
    const auto alias = label.find(" (", shuffled + 16);
    if (alias != std::string::npos && alias < end) end = alias;
    label.replace(shuffled + 16, end - shuffled - 16, replacement);
    return label;
}

} // namespace SohExtreme
