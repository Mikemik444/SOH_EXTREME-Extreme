#pragma once

#include <cstdint>
#include <map>
#include <string>
#include <utility>

namespace SohExtreme {

// Generated from the same stable-ID descriptions used by the APWorld. Display
// names never replace the numeric identities used for checks or reachability.
struct CheckDescription {
    int64_t location;
    const char* name;
    const char* legacyName;
    int sourceScene, door, fromRoom, toRoom, side;
};

inline constexpr CheckDescription kCheckDescriptions[] = {
#include "CheckDescriptions.inc"
};

inline const CheckDescription* FindCheckDescription(int64_t location) {
    static const std::map<int64_t, const CheckDescription*> descriptions = [] {
        std::map<int64_t, const CheckDescription*> result;
        for (const auto& description : kCheckDescriptions) result.emplace(description.location, &description);
        return result;
    }();
    const auto found = descriptions.find(location);
    return found != descriptions.end() ? found->second : nullptr;
}

inline std::string DescriptiveCheckName(const std::string& inputName) {
    static const std::map<std::string, const CheckDescription*> descriptions = [] {
        std::map<std::string, const CheckDescription*> result;
        for (const auto& description : kCheckDescriptions) {
            result.emplace(description.name, &description);
            result.emplace(description.legacyName, &description);
        }
        return result;
    }();
    const auto found = descriptions.find(inputName);
    // Cross-game hint rows do not include a game or location ID. Only exact
    // names registered by this world may be replaced; all others stay intact.
    return found != descriptions.end() ? found->second->name : inputName;
}

inline std::string CleanTrackerLabel(std::string label, bool hideTransitionNumbers = true) {
    // These are display-only implementation prefixes. Keep the meaningful
    // location, item ordinal, age annotation and custom alias text intact.
    for (;;) {
        bool removed = false;
        for (const char* prefix : { "EXTREME ", "Extreme ", "Enemy Route: ",
                                    "Entrance Collection: ", "Silver Access: " }) {
            const std::string text(prefix);
            if (label.compare(0, text.size(), text) == 0) {
                label.erase(0, text.size());
                removed = true;
                break;
            }
        }
        if (!removed) break;
    }

    if (!hideTransitionNumbers) return label;

    // Only remove the catalog's exact parenthesized numeric door suffix. A
    // check such as "Room of Three Stalfos" or "Chest 2" is not an engine ID.
    size_t search = 0;
    while ((search = label.find(" (door ", search)) != std::string::npos) {
        size_t cursor = search + 7;
        const auto take = [&](const char* text) {
            const std::string token(text);
            if (label.compare(cursor, token.size(), token) != 0) return false;
            cursor += token.size();
            return true;
        };
        const auto number = [&]() {
            const size_t start = cursor;
            while (cursor < label.size() && label[cursor] >= '0' && label[cursor] <= '9') ++cursor;
            return cursor != start;
        };
        bool valid = number() && take(", room ") && number();
        if (valid && take(" side ")) {
            valid = number() && take(" to side ") && number();
        } else if (valid) {
            valid = take(" to ") && number();
        }
        if (valid && take(")")) label.erase(search, cursor - search);
        else search += 7;
    }
    return label;
}

inline std::string TrackerCheckNumbers(const CheckDescription& description) {
    if (description.door >= 0) {
        // The existing catalog and Room debug show doors one-based. Native
        // room numbers stay zero-based so the optional details agree with both.
        std::string result = " (door " + std::to_string(description.door + 1) +
            ", room " + std::to_string(description.fromRoom);
        if (description.fromRoom == description.toRoom && description.side >= 0) {
            result += " side " + std::to_string(description.side + 1) +
                " to side " + std::to_string(2 - description.side);
        } else {
            result += " to " + std::to_string(description.toRoom);
        }
        return result + ")";
    }
    return description.fromRoom >= 0 ? " (room " + std::to_string(description.fromRoom) + ")" : "";
}

inline std::string TrackerCheckLabel(int64_t location, std::string inputName, bool showNumbers = false) {
    const auto* description = FindCheckDescription(location);
    if (description == nullptr) return CleanTrackerLabel(std::move(inputName), !showNumbers);

    // Keep UT's terminal age annotation in its original position. Custom
    // aliases occur before it and are preserved below, including parentheses.
    std::string age;
    for (const char* suffix : { " [Child]", " [Adult]", " [Any age]", " [Child only]",
                                " [Adult only]", " [Child / Adult]" }) {
        const std::string text(suffix);
        if (inputName.size() >= text.size() &&
            inputName.compare(inputName.size() - text.size(), text.size(), text) == 0) {
            age = text;
            inputName.erase(inputName.size() - text.size());
            break;
        }
    }

    std::string suffix;
    const std::string canonical(description->name);
    const std::string legacy(description->legacyName);
    if (inputName.compare(0, canonical.size(), canonical) == 0) {
        suffix = inputName.substr(canonical.size());
    } else if (inputName.compare(0, legacy.size(), legacy) == 0) {
        suffix = inputName.substr(legacy.size());
    } else if (inputName.compare(0, 10, "Shuffled: ") == 0) {
        // Older APWorld snapshots only named the source region and shuffled
        // destination. Retain that arrival while restoring the physical door
        // landmark from its immutable check ID.
        const auto separator = inputName.find(" -> ");
        if (separator != std::string::npos) suffix = " | Shuffled to: " + inputName.substr(separator + 4);
        else return CleanTrackerLabel(std::move(inputName), !showNumbers) + age;
    } else {
        // Future/custom producers may supply their own meaningful names.
        // Preserve those instead of silently replacing unrecognized text.
        return CleanTrackerLabel(std::move(inputName)) +
            (showNumbers ? TrackerCheckNumbers(*description) : "") + age;
    }
    return CleanTrackerLabel(canonical) + (showNumbers ? TrackerCheckNumbers(*description) : "") +
        CleanTrackerLabel(std::move(suffix)) + age;
}

} // namespace SohExtreme
