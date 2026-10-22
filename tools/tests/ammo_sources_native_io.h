#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "soh/Network/Archipelago/ArchipelagoC.h"
#include "soh/Network/Archipelago/AmmoSourcePolicy.h"
#include "captured_item00_enum.h"

#ifdef __cplusplus
extern "C" {
#endif

// Narrow native IO shapes. These do not claim binary compatibility with the
// full engine's Actor, collider, scene context, or object allocation.
typedef int8_t s8;
typedef int16_t s16;
typedef int32_t s32;
typedef uint8_t u8;
typedef uint32_t u32;
typedef float f32;
enum {
    VB_POT_DROP_ITEM = 1, VB_SMALL_CRATE_DROP_ITEM = 2, VB_CRATE_DROP_ITEM = 3,
    VB_PREVENT_ADULT_STICK = 4,
    ACTOR_OBJ_TSUBO = 1, ACTOR_OBJ_KIBAKO = 2, ACTOR_OBJ_KIBAKO2 = 3,
    ITEM_STICK = 0, ITEM_BOW = 3, ITEM_SLINGSHOT = 6, ITEM_NONE = 255,
    UPG_BOMB_BAG = 1,
    FLAG_SCENE_COLLECTIBLE = 1,
    LINK_AGE_ADULT = 0, LINK_AGE_CHILD = 1, QUEST_RANDOMIZER = 1,
};
typedef struct Vec3f { f32 x, y, z; } Vec3f;
typedef struct Vec3s { s16 x, y, z; } Vec3s;
typedef struct Actor {
    s16 id, params;
    struct { Vec3f pos; Vec3s rot; } home, world;
    struct { Vec3s rot; } shape;
} Actor;
typedef struct DynaPolyActor { Actor actor; u32 bgId; } DynaPolyActor;
typedef struct PlayState {
    int sceneNum, linkAgeOnLoad;
    struct { struct { u32 collect, tempCollect; } flags; } actorCtx;
    struct { int dyna; } colCtx;
} PlayState;
typedef struct ObjTsubo { Actor actor; } ObjTsubo;
typedef struct ObjKibako { Actor actor; } ObjKibako;
typedef struct ObjKibako2 {
    DynaPolyActor dyna;
    int collider;
    void (*actionFunc)(struct ObjKibako2*, PlayState*);
    s16 collectibleFlag;
} ObjKibako2;
typedef struct CollisionHeader { int unused; } CollisionHeader;
typedef struct EnItem00 { int unused; } EnItem00;
extern PlayState* gPlayState;
extern int gSourceDropCalls, gSourceDropParams, gSourceFlagEvents;
extern int gSourceAdult, gSourceInventory[256], gSourceCapacities[16];
extern struct SourceTestSave {
    int magicLevel, healthCapacity, health, fileNum, linkAge;
    struct { struct { int id; } quest; } ship;
} gSaveContext;
extern CollisionHeader gLargeCrateCol;

#define osSyncPrintf(...) ((void)0)
#define LUSLOG_INFO(...) ((void)0)
#define LINK_IS_ADULT (gSourceAdult != 0)
#define CUR_CAPACITY(upg) (gSourceCapacities[(upg)])
#define INV_CONTENT(item) (gSourceInventory[(item)])

int GameInteractor_Should(int, int, ...);
EnItem00* Item_DropCollectible(PlayState*, Vec3f*, s16);
void DynaPolyActor_Init(DynaPolyActor*, int);
void Actor_ProcessInitChain(Actor*, const int*);
void ObjKibako2_InitCollider(Actor*, PlayState*);
void CollisionHeader_GetVirtual(CollisionHeader*, CollisionHeader**);
u32 DynaPoly_SetBgActor(PlayState*, int*, Actor*, CollisionHeader*);
void ObjKibako2_Idle(ObjKibako2*, PlayState*);
void GameInteractor_ExecuteOnSceneFlagSet(int, int, int);
s16 EnItem00_ConvertOrdinaryBombDrop(s16);

void ObjTsubo_SpawnCollectible(ObjTsubo*, PlayState*);
void ObjKibako_SpawnCollectible(ObjKibako*, PlayState*);
void ObjKibako2_SpawnCollectible(ObjKibako2*, PlayState*);
void ObjKibako2_Init(Actor*, PlayState*);
s32 Flags_GetCollectible(PlayState*, s32);
void Flags_SetCollectible(PlayState*, s32);
s16 func_8001F404(s16);
uint32_t SourceTest_AmmoSourceMaskC(int32_t, int32_t, int32_t);

#ifdef __cplusplus
}
#endif
