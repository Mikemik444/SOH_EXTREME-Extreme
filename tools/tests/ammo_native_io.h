#pragma once

// Explicit engine IO boundary for extracted native functions. These are narrow
// test shapes, not binary-compatible game structures or engine replacements.
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include "soh/Network/Archipelago/ArchipelagoC.h"
#include "soh/Network/Archipelago/AmmoPolicy.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef int8_t s8;
typedef uint8_t u8;
typedef int16_t s16;
typedef uint16_t u16;
typedef int32_t s32;
typedef uint32_t u32;
typedef float f32;
enum {
    ITEM_STICK = 0, ITEM_NUT = 1, ITEM_BOMB = 2, ITEM_BOW = 3,
    ITEM_ARROW_FIRE = 4, ITEM_SLINGSHOT = 6, ITEM_BOMBCHU = 9,
    ITEM_ARROW_ICE = 12, ITEM_BEAN = 16, ITEM_ARROW_LIGHT = 18,
    ITEM_SEEDS = 88, ITEM_NONE = 255,
    UPG_QUIVER = 0, UPG_BOMB_BAG = 1, UPG_BULLET_BAG = 2,
    UPG_STICKS = 6, UPG_NUTS = 7, UPG_BOMBCHU = 8,
    QUEST_RANDOMIZER = 1, GAMEMODE_NORMAL = 0,
    RSK_BOMBCHU_BAG = 0, RO_BOMBCHU_BAG_NONE = 0,
    RO_BOMBCHU_BAG_SINGLE = 1, RO_BOMBCHU_BAG_PROGRESSIVE = 2,
    SLOT_STICK = ITEM_STICK, SLOT_NUT = ITEM_NUT, SLOT_BOMB = ITEM_BOMB,
    SLOT_BOW = ITEM_BOW, SLOT_BOMBCHU = ITEM_BOMBCHU,
    MAGIC_STATE_IDLE = 0, MAGIC_CONSUME_NOW = 0,
    ACTOR_EN_BOM = 1, ACTOR_EN_BOM_CHU = 2, ACTOR_EN_ARROW = 3,
    GI_NONE = 0, PLAYER_BODYPART_R_HAND = 0,
    VB_CHECK_BOMBCHU_CAPACITY = 1, VB_DEKU_STICK_BREAK = 2,
    VB_DEKU_STICK_BURN_OUT = 3, VB_DEKU_STICK_BURN_DOWN = 4,
    VB_PLAYER_ARROW_MAGIC_CONSUMPTION = 5,
    NA_SE_SY_ERROR = 1, NA_SE_IT_WOODSTICK_BROKEN = 2,
    NA_SE_VO_LI_SWORD_N = 3, NA_SE_VO_FR_SMILE_0 = 4,
    NA_SE_IT_BOW_DRAW = 5, NA_SE_IT_SLING_DRAW = 6, NA_SE_IT_HOOKSHOT_READY = 7,
    PLAYER_STATE1_CARRYING_ACTOR = 1u << 0,
    PLAYER_STATE1_ON_HORSE = 1u << 1,
    PLAYER_STATE1_READY_TO_FIRE = 1u << 2,
};
#include "captured_arrow_types.h"
#include "captured_player_actions.h"

typedef struct Vec3f { f32 x, y, z; } Vec3f;
typedef struct Vec3s { s16 x, y, z; } Vec3s;
typedef struct Color_RGBA8 { u8 r, g, b, a; } Color_RGBA8;
typedef struct Actor {
    struct { Vec3f pos; } world;
    struct { Vec3s rot; } shape;
    struct Actor *parent, *child;
} Actor;
typedef struct GetItemEntry { int item; } GetItemEntry;
typedef struct Player {
    Actor actor;
    u32 stateFlags1;
    int heldItemAction, unk_860, unk_834, unk_A73, getItemId;
    float unk_85C;
    Actor *heldActor, *interactRangeActor;
    GetItemEntry getItemEntry;
    Vec3s unk_3BC;
    Vec3f bodyPartsPos[1];
    struct { Vec3f tip; } meleeWeaponInfo[1];
    int skelAnime;
} Player;
typedef struct PlayState {
    int actorCtx;
    s8 bombchuBowlingStatus;
    s16 shootingGalleryStatus;
    struct { s16 hbaAmmo; } interfaceCtx;
} PlayState;
typedef struct AmmoTestSave {
    struct { s8 ammo[256]; u8 items[256]; u32 upgrades, questItems; } inventory;
    struct {
        struct {
            int id;
            struct { struct { u8 bombchuUpgradeLevel; } randomizer; } data;
        } quest;
        u8 randomizerInf[32];
    } ship;
    u16 minigameState;
    int magicState, gameMode, linkAge;
    s16 rupees;
    u16 dayTime, nightFlag;
} AmmoTestSave;
extern AmmoTestSave gSaveContext;
extern PlayState* gPlayState;
extern int gAmmoCapacities[16], gAmmoUpgrades[16];
extern int gIsAdult, gHookshot, gExplosiveType, gSpawnSucceeds;
extern int gAnimationFinished, gThrowFrame, gMagicSucceeds, gCapacityHook;
extern int gBowSlingshotFix, gInfiniteAmmo;
extern int gNoRandomDrops, gTreesDropSticks, gDampeAllNight, gBombchuBagMode;
extern int gUnequipped, gPutAway, gSpawned, gLastActorId, gLastActorParams;
extern int gMagicRequests, gMagicCost, gBreakEffects, gFlameEffects, gRumbles;
extern int gVoices, gSounds, gStatsCalls, gStatsUsed[256];
extern int gPlayerAnim_link_normal_light_bom_end;
extern Vec3f gSfxDefaultPos;
extern float gSfxDefaultFreqAndVolScale;
extern s8 gSfxDefaultReverb;

#define TEST_AMMO_SLOT(item) ((item) == ITEM_SEEDS ? ITEM_SLINGSHOT : (item))
#define AMMO(item) (gSaveContext.inventory.ammo[TEST_AMMO_SLOT(item)])
#define INV_CONTENT(item) (gSaveContext.inventory.items[TEST_AMMO_SLOT(item)])
#define CUR_CAPACITY(upg) (gAmmoCapacities[(upg)])
#define CUR_UPG_VALUE(upg) (gAmmoUpgrades[(upg)])
#define LINK_IS_ADULT (gIsAdult != 0)
#define CVAR_CHEAT(name) name
#define CVAR_ENHANCEMENT(name) name
#define GET_ITEM_NONE {0}
#define ABS(value) ((value) < 0 ? -(value) : (value))
#define DECR(value) ((value) != 0 ? --(value) : 0)
#define osSyncPrintf(...) ((void)0)

void Inventory_ChangeAmmo(s16 item, s16 ammoChange);
void Legacy_Inventory_ChangeAmmo(s16 item, s16 ammoChange);
void GameplayStats_UpdateAmmoUsed(s16 item, s16 ammoUsed);
int GameInteractor_Should(int behavior, int condition, ...);
int CVarGetInteger(const char* name, int fallback);
int Randomizer_GetSettingValue(int setting);
int Player_GetExplosiveHeld(Player* player);
void Player_PutAwayHeldItem(PlayState* play, Player* player);
Actor* Actor_SpawnAsChild(int*, Actor*, PlayState*, int, float, float, float, int, int, int, int);
Actor* Actor_Spawn(int*, PlayState*, int, float, float, float, int, int, int, int);
int Player_HoldsHookshot(Player* player);
void Player_RequestRumble(Player*, int, int, int, int);
void Player_UseItem(PlayState*, Player*, int);
void Player_PlaySfx(Player*, int);
void Player_PlayVoiceSfx(Player*, int);
void EffectSsStick_Spawn(PlayState*, Vec3f*, int);
void func_8002836C(PlayState*, Vec3f*, Vec3f*, Vec3f*, Color_RGBA8*, Color_RGBA8*, float, int, int);
int LinkAnimation_Update(PlayState*, int*);
int LinkAnimation_OnFrame(int*, float);
void func_8083A098(Player*, int*, PlayState*);
void Player_DecelerateToZero(Player*);
void Sfx_PlaySfxCentered(int);
void Player_SetUpperActionFunc(Player*, s32 (*)(Player*, PlayState*));
int Magic_RequestChange(PlayState*, s16, s16);
s32 func_808351D4(Player*, PlayState*);
void Audio_PlaySfxGeneral(int, Vec3f*, int, float*, float*, s8*);
void Play_TriggerRespawn(PlayState*);

void Player_InitExplosiveIA(PlayState*, Player*);
s32 func_80834380(PlayState*, Player*, s32*, s32*);
s32 func_8083442C(Player*, PlayState*);
s32 func_808350A4(PlayState*, Player*);
void func_80842A88(PlayState*, Player*);
s32 func_80842AC4(PlayState*, Player*);
void Player_UpdateBurningDekuStick(PlayState*, Player*);
void Player_Action_8084E604(Player*, PlayState*);

int TestAmmoPureC(void);

#ifdef __cplusplus
}
#endif
