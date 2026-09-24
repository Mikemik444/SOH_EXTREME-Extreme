#ifndef SOH_EXTREME_FISHING_SOUL_ACCESS_H
#define SOH_EXTREME_FISHING_SOUL_ACCESS_H

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

// Fishing uses one actor ID for the owner, catchable fish and aquarium fish.
// Presence and permission to speak are intentionally separate from rod access.
bool MegaSoul_IsFishingOwnerPresent(void);
bool MegaSoul_ArePondFishPresent(void);
bool MegaSoul_CanTalkToFishingOwner(void);

#ifdef __cplusplus
}
#endif

#endif
