#pragma once

#include "z64math.h"
#include "z64actor.h"

#define NUM_GROTTOS GROTTO_OFFSET_MAX
#define NOT_GROTTO 0
#define GROTTO_LOAD 1
#define GROTTO_RETURN 2

typedef struct {
    s16 entranceIndex;
    s8 content;
    s8 scene;
} GrottoLoadInfo;

typedef struct {
    s16 entranceIndex;
    s8 room;
    s16 angle;
    Vec3f pos;
} GrottoReturnInfo;

#ifdef __cplusplus
extern "C" {
#endif
void Grotto_InitExitAndLoadLists(void);
void Grotto_SetExitOverride(s16 originalIndex, s16 overrideIndex);
void Grotto_SetLoadOverride(s16 originalIndex, s16 overrideIndex);
s16 Grotto_GetEntranceValueHandlingGrottoRando(s16 nextEntranceIndex);
s16 Grotto_OverrideSpecialEntrance(s16 nextEntranceIndex);
void Grotto_OverrideActorEntrance(Actor* thisx);
s32 Grotto_ActorRequiresShovel(Actor* thisx);
// Exterior grotto returns resolve a safe stationary landing on the first
// player update, after room actors and dynamic background lookup initialize.
// Resolve returns 0 for no request, 1 for a placed landing, 2 for native emergence.
s32 Grotto_QueueReturnLanding(Actor* actor);
s32 Grotto_HasPendingReturnLanding(void);
s32 Grotto_ResolveReturnLanding(Actor* actor);
void Grotto_UpdateReturnLanding(Actor* actor);
s32 Grotto_CanCaptureReturnPoint(Actor* actor);
void Grotto_ForceGrottoReturnOnSpecialEntrance(void);
void Grotto_ForceGrottoReturn(void);
void Grotto_ForceRegularVoidOut(void);
void Grotto_SanitizeEntranceType(void);
s16 Grotto_GetRenamedGrottoIndexFromOriginal(s8 content, s8 scene);
s8 Grotto_CurrentGrotto();
#ifdef __cplusplus
};
#endif
