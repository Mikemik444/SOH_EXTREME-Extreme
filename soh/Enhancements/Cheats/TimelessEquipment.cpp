#include "soh/Enhancements/game-interactor/GameInteractor.h"
#include "soh/ShipInit.hpp"
#include "soh/cvar_prefixes.h"

extern "C" {
#include "z64save.h"
#include "variables.h"
#include "macros.h"
extern SaveContext gSaveContext;
extern s32 Flags_GetRandomizerInf(RandomizerInf flag);
}

#define CVAR_TIMELESS_EQUIPMENT_NAME CVAR_CHEAT("TimelessEquipment")

static bool CrossAgeEquipmentEnabledForCurrentAge() {
    // Do not grant cross-age permissions on the title screen, on another
    // game mode or on a file that has not received the AP progression item.
    if (!GameInteractor::IsSaveLoaded(true) || !IS_RANDO) return false;
    return LINK_IS_ADULT
        ? Flags_GetRandomizerInf(RAND_INF_ADULT_CAN_USE_CHILD_ITEMS) != 0
        : Flags_GetRandomizerInf(RAND_INF_CHILD_CAN_USE_ADULT_ITEMS) != 0;
}

static void RegisterTimelessEquipment() {
    // Register once regardless of AP inventory. The flags may change at any
    // frame after a received item; registration-time snapshots go stale.
    COND_VB_SHOULD(VB_PLAYER_MEETS_AGE_REQ, true, {
        if (CVarGetInteger(CVAR_TIMELESS_EQUIPMENT_NAME, 0) || CrossAgeEquipmentEnabledForCurrentAge())
            *should = true;
    });
    COND_VB_SHOULD(VB_ITEM_MEETS_AGE_REQ, true, {
        if (CVarGetInteger(CVAR_TIMELESS_EQUIPMENT_NAME, 0) || CrossAgeEquipmentEnabledForCurrentAge())
            *should = true;
    });
    COND_VB_SHOULD(VB_SLOT_MEETS_AGE_REQ, true, {
        if (CVarGetInteger(CVAR_TIMELESS_EQUIPMENT_NAME, 0) || CrossAgeEquipmentEnabledForCurrentAge())
            *should = true;
    });
}

static RegisterShipInitFunc initFunc(RegisterTimelessEquipment, { CVAR_TIMELESS_EQUIPMENT_NAME });
