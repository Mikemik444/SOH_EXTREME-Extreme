#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace SohExtreme {
// Immutable provenance for the exact item text placed in a native message.
// Merely constructing or copying this value never reveals a server hint.
struct HintTarget {
    int64_t locationId = -1;
    int64_t itemId = -1;
    int finderId = 0;
    int recipientId = 0;
    int flags = -1; // Unknown is not progression. AP advancement is bit 0.
    bool starting = false;
    std::string item, location, finder, recipient, game, entrance;
    // Session in which this text was constructed; a new save/room cannot
    // accidentally publish the unfinished textbox from the previous one.
    std::string seed;
    int team = -1;
    int slot = 0;

    bool IsProgression() const { return flags >= 0 && (flags & 1) != 0 && (flags & 4) == 0; }
    bool HasLocation() const { return !starting && locationId >= 0 && finderId > 0; }
};

// Called only after the native message's final page has actually been drawn.
// The client revalidates progression and session identity before publishing.
void RecordRevealedHintTargets(const std::vector<HintTarget>& targets);
} // namespace SohExtreme
