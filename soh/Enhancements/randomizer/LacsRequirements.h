#pragma once

#include <cstdint>
#include "randomizerEnums.h"

namespace SohExtreme {

// Shared by the actual save's LACS trigger and native reachability logic.
// Counts are supplied by each caller's own inventory; no global tracker state
// is read by the runtime trigger.
struct LacsRequirements {
    bool archipelago = false;
    bool triforceHunt = false;
    bool shadowMedallion = false;
    bool spiritMedallion = false;
    uint32_t bossKeyMode = RO_GANON_BOSS_KEY_VANILLA;
    uint32_t stones = 0;
    uint32_t medallions = 0;
    uint32_t dungeons = 0;
    uint32_t tokens = 0;
    uint32_t requiredStones = 0;
    uint32_t requiredMedallions = 0;
    uint32_t requiredRewards = 0;
    uint32_t requiredDungeons = 0;
    uint32_t requiredTokens = 0;
    uint32_t bonusReward = 0;
};

inline bool MeetsLacsRequirements(const LacsRequirements& state) {
    // Native standalone seeds use the original cutscene condition. AP Triforce
    // Hunt likewise explicitly keeps vanilla LACS, independent of the inactive
    // boss-key location selector preserved in YAML/slot data.
    if (!state.archipelago || state.triforceHunt) {
        return state.shadowMedallion && state.spiritMedallion;
    }
    switch (state.bossKeyMode) {
        case RO_GANON_BOSS_KEY_STONES:
            return state.stones + state.bonusReward >= state.requiredStones;
        case RO_GANON_BOSS_KEY_MEDALLIONS:
            return state.medallions + state.bonusReward >= state.requiredMedallions;
        case RO_GANON_BOSS_KEY_REWARDS:
            return state.stones + state.medallions + state.bonusReward >= state.requiredRewards;
        case RO_GANON_BOSS_KEY_DUNGEONS:
            return state.dungeons + state.bonusReward >= state.requiredDungeons;
        case RO_GANON_BOSS_KEY_TOKENS:
            return state.tokens >= state.requiredTokens;
        default:
            return state.shadowMedallion && state.spiritMedallion;
    }
}

} // namespace SohExtreme
