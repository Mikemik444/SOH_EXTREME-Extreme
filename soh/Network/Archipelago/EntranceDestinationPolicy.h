#pragma once

#include <cstdint>

namespace SohExtreme {
// These bits describe ages, not the engine's inverse LINK_AGE_* ordinals.
inline constexpr uint8_t kEntranceChildAge = 1;
inline constexpr uint8_t kEntranceAdultAge = 2;
inline constexpr int kEntranceDestinationPolicyRevision = 1;

enum EntranceDestinationKind {
    kEntranceNative = 0,
    kEntranceGrottoLoad = 1,
    kEntranceGrottoReturn = 2,
    kEntranceRoomDoor = 3,
};

struct EntranceNormalLayer {
    int scene, spawn;
};

struct EntranceDestinationPolicy {
    int id, nativeIndex, kind;
    uint8_t sourceAgeMask, arrivalAgeMask;
    EntranceNormalLayer normalLayers[4]; // child day/night, adult day/night
};

inline constexpr EntranceDestinationPolicy kEntranceDestinationPolicies[] = {
#include "EntranceDestinationData.inc"
};

inline const EntranceDestinationPolicy* EntranceDestinationById(int id) {
    for (const auto& row : kEntranceDestinationPolicies) if (row.id == id) return &row;
    return nullptr;
}

inline bool EntranceDestinationAllowsAge(const EntranceDestinationPolicy* destination, uint8_t age) {
    return destination && (age == kEntranceChildAge || age == kEntranceAdultAge) &&
           (destination->arrivalAgeMask & age) != 0;
}
} // namespace SohExtreme
