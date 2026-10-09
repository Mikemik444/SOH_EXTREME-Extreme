#pragma once

#include <string>

namespace SohExtreme {
// Network addresses locate a room; they do not identify its generated game.
struct SaveConnectionIdentity {
    std::string seed;
    int team = -1;
    int slot = -1;
    bool Valid() const { return !seed.empty() && team >= 0 && slot > 0; }
};

enum class SaveConnectionDecision { Waiting, Ready, WrongSlot, WrongSeed, ConfirmLegacy };

inline SaveConnectionDecision CompareSaveConnection(
    const SaveConnectionIdentity& saved, const std::string& savedSlot, const std::string& savedServer,
    const SaveConnectionIdentity& live, const std::string& liveSlot, const std::string& liveServer,
    bool authenticated, bool confirmLegacy = false) {
    if (!authenticated || !live.Valid()) return SaveConnectionDecision::Waiting;
    if (!savedSlot.empty() && savedSlot != liveSlot) return SaveConnectionDecision::WrongSlot;
    if (!saved.seed.empty()) {
        if (saved.seed != live.seed) return SaveConnectionDecision::WrongSeed;
        if (saved.team != live.team || saved.slot != live.slot) return SaveConnectionDecision::WrongSlot;
        return SaveConnectionDecision::Ready;
    }
    // Pre-0.11.61 saves have no seed identity. Retain their existing same-address
    // compatibility, but never silently guess a new room from its player name.
    if (!confirmLegacy && !savedServer.empty() && savedServer != liveServer)
        return SaveConnectionDecision::ConfirmLegacy;
    return SaveConnectionDecision::Ready;
}
} // namespace SohExtreme
