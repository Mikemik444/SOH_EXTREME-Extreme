#pragma once
// Engine I/O only. Production actor structs, Init/selection/door bodies,
// animation tables, native scene IDs and destination policy are captured intact.
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include "soh/Network/Archipelago/ArchipelagoC.h"

typedef int16_t s16;
typedef int32_t s32;
typedef int8_t s8;
typedef uint8_t u8;
typedef float f32;
typedef struct { f32 x, y, z; } Vec3f;
typedef struct { s16 x, y, z; } Vec3s;
typedef struct { int unused; } SkelAnime;
typedef int RandomizerInf;
typedef struct PlayState PlayState;
typedef struct Actor Actor;
struct Actor {
    s16 params, objBankIndex, textId;
    uint32_t flags;
    struct { Vec3f pos; Vec3s rot; } world;
    void (*draw)(Actor*, PlayState*);
    bool killed;
};
struct PlayState { s16 sceneNum; int objectCtx, actorCtx; };
typedef struct { Actor actor; } Player;
static Player gPlayer;
static struct { uint16_t dayTime; bool nightFlag; } gSaveContext;
static bool gAdult, gRando = true, gCurrentSave = true, gKnown = true;
static bool gObjectLoaded = true, gSwitch, gLegacyWindowOverride;
static unsigned gActive = 15, gSubmitted, gChecks, gSpawns;
static bool gEventFlags[0x100];
static f32 gDistance;
static int gEnHeishiSkel, gEnHeishiIdleAnim;
#define ARRAY_COUNT(a) (sizeof(a) / sizeof((a)[0]))
#define IS_DAY (!gSaveContext.nightFlag)
#define IS_RANDO gRando
#define LINK_IS_ADULT gAdult
#define GET_PLAYER(play) (&gPlayer)
#define VT_FGCOL(color) ""
#define VT_RST ""
#define ACTOR_FLAG_UPDATE_CULLING_DISABLED 1
#define ACTOR_FLAG_ATTENTION_ENABLED 2
#define ACTOR_FLAG_FRIENDLY 4
#define ACTOR_FLAG_LOCK_ON_DISABLED 8
#define ACTOR_EN_EX_RUPPY 0
#define VB_WONDER_HEISHI_PATROLLING 1
#define VB_DOOR_BE_LOCKED 2
#include "captured_native_constants.h"
#include "captured_actor_structs.h"

static void Check(bool condition, const char* expression, int line) {
    ++gChecks;
    if (!condition) { fprintf(stderr, "line %d: %s\n", line, expression); exit(1); }
}
#define CHECK(expression) Check((expression), #expression, __LINE__)
static int LocationBit(int64_t id) {
    const int64_t locations[] = { 11000122LL, 11000662LL, 11001024LL, 11683197LL };
    for (unsigned i = 0; i < ARRAY_COUNT(locations); ++i) if (locations[i] == id) return 1u << i;
    return 0;
}
bool Archipelago_IsCurrentSaveFile(void) { return gCurrentSave; }
bool Archipelago_IsLocationActive(int64_t id) { return gKnown && (gActive & LocationBit(id)) != 0; }
bool Archipelago_IsLocationSubmitted(int64_t id) { return (gSubmitted & LocationBit(id)) != 0; }
static bool Flags_GetEventChkInf(int id) { return gEventFlags[id]; }
static bool Flags_GetSwitch(PlayState* play, int flag) { (void)play; (void)flag; return gSwitch; }
static bool Object_IsLoaded(int* context, int index) { (void)context; (void)index; return gObjectLoaded; }
static f32 Actor_WorldDistXZToActor(Actor* first, Actor* second) { (void)first; (void)second; return gDistance; }
static void Actor_Kill(Actor* actor) { actor->killed = true; actor->draw = NULL; }
static void Actor_SetScale(Actor* actor, f32 scale) { (void)actor; (void)scale; }
static void SkelAnime_Init(PlayState* play, SkelAnime* animation, int* skeleton, int* clip,
                           Vec3s* joints, Vec3s* morphs, int count) {
    (void)play; (void)animation; (void)skeleton; (void)clip; (void)joints; (void)morphs; (void)count;
}
static void Actor_SpawnAsChild(int* context, Actor* parent, PlayState* play, int actor,
                               f32 x, f32 y, f32 z, int rx, int ry, int rz, int params) {
    (void)context; (void)parent; (void)play; (void)actor; (void)x; (void)y; (void)z;
    (void)rx; (void)ry; (void)rz; (void)params; ++gSpawns;
}
static void osSyncPrintf(const char* format, ...) { (void)format; }
// The ordinary hook's bool is unmodified. The preexisting wonder-item hook is
// represented by its exact selection result (type != 5) when registered/pending.
static bool GameInteractor_Should(int hook, bool ordinary, ...) {
    va_list args;
    va_start(args, ordinary);
    if (hook == VB_WONDER_HEISHI_PATROLLING && gLegacyWindowOverride) {
        EnHeishi1* guard = va_arg(args, EnHeishi1*);
        ordinary = guard->type != 5;
    }
    va_end(args);
    return ordinary;
}
void EnHeishi1_Draw(Actor* actor, PlayState* play) { (void)actor; (void)play; }
void EnHeishi1_SetupWalk(EnHeishi1* guard, PlayState* play) { (void)guard; (void)play; }
void EnHeishi1_SetupWaitNight(EnHeishi1* guard, PlayState* play) { (void)guard; (void)play; }
void EnHeishi1_WaitNight(EnHeishi1* guard, PlayState* play) { (void)guard; (void)play; }
void EnHeishi1_SetupKick(EnHeishi1* guard, PlayState* play) { (void)guard; (void)play; }
void EnHeishi1_Walk(EnHeishi1* guard, PlayState* play) { (void)guard; (void)play; }
void EnDoor_Idle(EnDoor* door, PlayState* play) { (void)door; (void)play; }
void EnDoor_AjarWait(EnDoor* door, PlayState* play) { (void)door; (void)play; }
void EnDoor_WaitForCheck(EnDoor* door, PlayState* play) { (void)door; (void)play; }
