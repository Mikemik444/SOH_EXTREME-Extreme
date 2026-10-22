#pragma once

/* SOH-EXTREME: ordinary loot and assigned ammo use the same bag prerequisite.
 * Parameters are integers so this header can be included from C actor files.
 * The bag item itself is granted by Context::HandleGetBombchuBag, NOT here.
 */
static inline int SohExtreme_HasBombchuContainer(int progressiveBag, int hasBombchuSlot,
                                                unsigned int upgradeLevel) {
    return hasBombchuSlot && (!progressiveBag || upgradeLevel > 0);
}

static inline int SohExtreme_CanReceiveBombchuRefill(int bagRequired, int progressiveBag,
                                                     int hasBombchuSlot, unsigned int upgradeLevel) {
    return !bagRequired || SohExtreme_HasBombchuContainer(progressiveBag, hasBombchuSlot, upgradeLevel);
}

static inline int SohExtreme_BombchuCapacity(int progressiveBag, unsigned int upgradeLevel) {
    if (!progressiveBag) return 50;
    if (upgradeLevel == 0) return 0;
    if (upgradeLevel == 1) return 20;
    if (upgradeLevel == 2) return 30;
    return 50;
}

static inline int SohExtreme_AddBombchuRefill(int currentAmmo, int refill, int capacity) {
    if (capacity <= 0) return 0;
    if (currentAmmo < 0) currentAmmo = 0;
    if (currentAmmo > capacity) currentAmmo = capacity;
    if (refill <= 0) return currentAmmo;
    return refill >= capacity - currentAmmo ? capacity : currentAmmo + refill;
}

static inline int SohExtreme_UseBombchuOnlyRefill(int hasBombBag, int progressiveBag,
                                                int hasBombchuSlot, unsigned int upgradeLevel) {
    return !hasBombBag && SohExtreme_HasBombchuContainer(progressiveBag, hasBombchuSlot, upgradeLevel);
}
