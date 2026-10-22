#pragma once

#include <stdint.h>
#include "AmmoPolicy.h"

enum SohExtremeAmmoSourceKind {
    SOH_EXTREME_AMMO_SOURCE_POT = 1,
    SOH_EXTREME_AMMO_SOURCE_SMALL_CRATE = 2,
    SOH_EXTREME_AMMO_SOURCE_LARGE_CRATE = 3,
};

// Seeds are retained as raw source metadata because adult collectible
// conversion changes them into arrows. They are not a protected ammo type.
enum { SOH_EXTREME_AMMO_SOURCE_SEEDS = 1u << 5 };

// Ordinary En_Item00 drop IDs. The client verifies these against the engine's
// symbolic constants before using this engine-independent classifier.
enum SohExtremeAmmoSourceDrop {
    SOH_EXTREME_AMMO_DROP_BOMBS_A = 0x04,
    SOH_EXTREME_AMMO_DROP_ARROWS_SMALL = 0x08,
    SOH_EXTREME_AMMO_DROP_ARROWS_MEDIUM = 0x09,
    SOH_EXTREME_AMMO_DROP_ARROWS_LARGE = 0x0A,
    SOH_EXTREME_AMMO_DROP_BOMBS_B = 0x0B,
    SOH_EXTREME_AMMO_DROP_NUTS = 0x0C,
    SOH_EXTREME_AMMO_DROP_STICK = 0x0D,
    SOH_EXTREME_AMMO_DROP_SEEDS = 0x10,
};

// Source parameters are observed from the real actor, never inferred from a
// location's vanilla reward. Large crates use home.rot.x for the drop and the
// collectibleFlag saved by native Init; home.rot.z has already been cleared.
// The caller retains the exact check identity, actor kind and observed age.
static inline uint32_t SohExtreme_AmmoSourceMask(int32_t sourceKind, int32_t sourceDropParams,
                                                int32_t collectibleInput) {
    if (sourceDropParams < INT16_MIN || sourceDropParams > UINT16_MAX) {
        return 0;
    }

    const uint32_t params = (uint32_t)sourceDropParams;
    int32_t drop;
    uint32_t flag;
    switch (sourceKind) {
        case SOH_EXTREME_AMMO_SOURCE_POT:
            drop = params & 0x1Fu;
            flag = (params >> 9) & 0x3Fu;
            break;
        case SOH_EXTREME_AMMO_SOURCE_SMALL_CRATE:
            drop = params & 0x1Fu;
            flag = (params >> 8) & 0x3Fu;
            break;
        case SOH_EXTREME_AMMO_SOURCE_LARGE_CRATE:
            drop = sourceDropParams;
            flag = (uint32_t)collectibleInput & 0x3Fu;
            break;
        default:
            return 0;
    }
    if (flag != 0) {
        return 0;
    }

    switch (drop) {
        case SOH_EXTREME_AMMO_DROP_BOMBS_A:
        case SOH_EXTREME_AMMO_DROP_BOMBS_B:
            return SOH_EXTREME_AMMO_REFILL_BOMB;
        case SOH_EXTREME_AMMO_DROP_NUTS:
            return SOH_EXTREME_AMMO_REFILL_NUT;
        case SOH_EXTREME_AMMO_DROP_STICK:
            return SOH_EXTREME_AMMO_REFILL_STICK;
        case SOH_EXTREME_AMMO_DROP_ARROWS_SMALL:
        case SOH_EXTREME_AMMO_DROP_ARROWS_MEDIUM:
        case SOH_EXTREME_AMMO_DROP_ARROWS_LARGE:
            return SOH_EXTREME_AMMO_REFILL_ARROWS;
        case SOH_EXTREME_AMMO_DROP_SEEDS:
            return SOH_EXTREME_AMMO_SOURCE_SEEDS;
        default:
            // Includes flexible/random drops, health, rupees, keys, equipment,
            // the ITEM_BOW-granting single arrow, special bombs, and AP dummies.
            return 0;
    }
}
