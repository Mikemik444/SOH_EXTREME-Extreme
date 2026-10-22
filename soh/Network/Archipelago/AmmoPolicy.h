#pragma once

#include <stdint.h>

// Shared with the authoritative AP refill snapshot. Each ammo type becomes
// consumable independently when its own repeatable refill is reachable.
enum SohExtremeAmmoRefillMask {
    SOH_EXTREME_AMMO_REFILL_STICK = 1u << 0,
    SOH_EXTREME_AMMO_REFILL_NUT = 1u << 1,
    SOH_EXTREME_AMMO_REFILL_BOMB = 1u << 2,
    SOH_EXTREME_AMMO_REFILL_BOMBCHU = 1u << 3,
    SOH_EXTREME_AMMO_REFILL_ARROWS = 1u << 4,
};

// The caller owns save identity, item/container ownership, and refill freshness.
// This only preserves ammo already present; zero ammo and pickups are unchanged.
static inline int32_t SohExtreme_AdjustAmmoChange(int32_t currentAmmo, int32_t change,
                                                 int eligible, int hasRepeatableRefill) {
    if (!eligible || hasRepeatableRefill || currentAmmo <= 0 || change >= 0) {
        return change;
    }

    // Comparing deltas avoids overflowing currentAmmo + change, including an
    // INT32_MIN request. Positive currentAmmo makes 1 - currentAmmo safe.
    const int32_t minimumChange = 1 - currentAmmo;
    return change < minimumChange ? minimumChange : change;
}
