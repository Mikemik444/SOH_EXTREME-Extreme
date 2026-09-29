#pragma once

#include <cstdint>
#include <string>
#include <vector>

// Copied with SaveContext on the game thread, then owned by one save job.
// A writer must never pair old inventory with a newer live AP receipt cursor.
struct ArchipelagoSaveSnapshot {
    bool active = false;
    uint64_t receivedItemCount = 0;
    std::string server;
    std::string slot;
    std::string settingsJson;
    std::vector<uint64_t> fallbackNpcSpeechHashes;
    std::vector<int64_t> pendingLocations;
};
