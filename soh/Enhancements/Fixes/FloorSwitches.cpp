#include "soh/Enhancements/game-interactor/GameInteractor.h"
#include "soh/ShipInit.hpp"

extern "C" {
#include "src/overlays/actors/ovl_Obj_Switch/z_obj_switch.h"

// z_bgcheck.c exports this, but the public headers used by this enhancement do
// not expose the declaration.  We use it only to immediately resync DynaPoly
// after the vanilla floor-switch position correction.
void DynaPoly_UpdateBgActorTransforms(PlayState* play, DynaCollisionContext* dyna);
}

extern PlayState* gPlayState;

static constexpr int32_t CVAR_FLOOR_SWITCHES_DEFAULT = 0;
#define CVAR_FLOOR_SWITCHES_NAME CVAR_ENHANCEMENT("FixFloorSwitches")
#define CVAR_FLOOR_SWITCHES_VALUE CVarGetInteger(CVAR_FLOOR_SWITCHES_NAME, CVAR_FLOOR_SWITCHES_DEFAULT)

static void OnInitFloorSwitches(void* refActor) {
    // The two affected floor-switch placements are corrected directly in
    // ObjSwitch_Init *before* DynaPoly registration.  Do not move the actor from
    // this post-init hook: doing so recreates the model/collision desync that
    // caused the switch to work from one room entrance but not the other.
    (void)refActor;
}

static void RegisterFloorSwitchesFix() {
    // Keep the hook registered for compatibility with the enhancement CVar, but
    // the actual transform correction now happens atomically in ObjSwitch_Init.
    // This hook intentionally performs no post-registration movement.
    COND_ID_HOOK(OnActorInit, ACTOR_OBJ_SWITCH, CVAR_FLOOR_SWITCHES_VALUE, OnInitFloorSwitches);
}

static RegisterShipInitFunc initFunc(RegisterFloorSwitchesFix, { CVAR_FLOOR_SWITCHES_NAME, "IS_RANDO" });
