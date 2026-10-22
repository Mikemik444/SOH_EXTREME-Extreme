/*
 * Much of the code here was borrowed from https://github.com/gamestabled/OoT3D_Randomizer/blob/main/code/src/grotto.c
 * It's been adapted for SoH to use our gPlayState vs their gGlobalContext and slightly different named properties.
 */

#include "randomizer_grotto.h"
#include "soh/Network/Archipelago/ArchipelagoC.h"
#include "soh/OTRGlobals.h"

#include "variables.h"
#include "functions.h"
#include "SoulActorAccess.h"
#include "overlays/actors/ovl_En_Ishi/z_en_ishi.h"
#include "overlays/actors/ovl_Obj_Bombiwa/z_obj_bombiwa.h"
#include <math.h>

extern PlayState* gPlayState;

// Information necessary for entering each grotto
static const GrottoLoadInfo grottoLoadTable[NUM_GROTTOS] = {
    // clang-format off
    {.entranceIndex = ENTR_GROTTOS_10,        .content = 0xFD, .scene = SCENE_DESERT_COLOSSUS},       // Desert Colossus -> Colossus Grotto
    {.entranceIndex = ENTR_GROTTOS_4,         .content = 0xEF, .scene = SCENE_LAKE_HYLIA},            // Lake Hylia -> LH Grotto
    {.entranceIndex = ENTR_GROTTOS_10,        .content = 0xEB, .scene = SCENE_ZORAS_RIVER},           // Zora River -> ZR Storms Grotto
    {.entranceIndex = ENTR_FAIRYS_FOUNTAIN_0, .content = 0xE6, .scene = SCENE_ZORAS_RIVER},           // Zora River -> ZR Fairy Grotto
    {.entranceIndex = ENTR_GROTTOS_0,         .content = 0x29, .scene = SCENE_ZORAS_RIVER},           // Zora River -> ZR Open Grotto
    {.entranceIndex = ENTR_GROTTOS_4,         .content = 0xF9, .scene = SCENE_DEATH_MOUNTAIN_CRATER}, // DMC Lower Nearby -> DMC Hammer Grotto
    {.entranceIndex = ENTR_GROTTOS_0,         .content = 0x7A, .scene = SCENE_DEATH_MOUNTAIN_CRATER}, // DMC Upper Nearby -> DMC Upper Grotto
    {.entranceIndex = ENTR_GROTTOS_4,         .content = 0xFB, .scene = SCENE_GORON_CITY},            // GC Grotto Platform -> GC Grotto
    {.entranceIndex = ENTR_GROTTOS_0,         .content = 0x57, .scene = SCENE_DEATH_MOUNTAIN_TRAIL},  // Death Mountain -> DMT Storms Grotto
    {.entranceIndex = ENTR_GROTTOS_13,        .content = 0xF8, .scene = SCENE_DEATH_MOUNTAIN_TRAIL},  // Death Mountain Summit -> DMT Cow Grotto
    {.entranceIndex = ENTR_GROTTOS_0,         .content = 0x28, .scene = SCENE_KAKARIKO_VILLAGE},      // Kak Backyard -> Kak Open Grotto
    {.entranceIndex = ENTR_GROTTOS_3,         .content = 0xE7, .scene = SCENE_KAKARIKO_VILLAGE},      // Kakariko Village -> Kak Redead Grotto
    {.entranceIndex = ENTR_GROTTOS_9,         .content = 0xF6, .scene = SCENE_HYRULE_CASTLE},         // Hyrule Castle Grounds -> HC Storms Grotto
    {.entranceIndex = ENTR_GROTTOS_11,        .content = 0xE1, .scene = SCENE_HYRULE_FIELD},          // Hyrule Field -> HF Tektite Grotto
    {.entranceIndex = ENTR_GROTTOS_1,         .content = 0xE5, .scene = SCENE_HYRULE_FIELD},          // Hyrule Field -> HF Near Kak Grotto
    {.entranceIndex = ENTR_FAIRYS_FOUNTAIN_0, .content = 0xFF, .scene = SCENE_HYRULE_FIELD},          // Hyrule Field -> HF Fairy Grotto
    {.entranceIndex = ENTR_GROTTOS_0,         .content = 0x00, .scene = SCENE_HYRULE_FIELD},          // Hyrule Field -> HF Near Market Grotto
    {.entranceIndex = ENTR_GROTTOS_5,         .content = 0xE4, .scene = SCENE_HYRULE_FIELD},          // Hyrule Field -> HF Cow Grotto
    {.entranceIndex = ENTR_GROTTOS_2,         .content = 0xE6, .scene = SCENE_HYRULE_FIELD},          // Hyrule Field -> HF Inside Fence Grotto
    {.entranceIndex = ENTR_GROTTOS_0,         .content = 0x03, .scene = SCENE_HYRULE_FIELD},          // Hyrule Field -> HF Open Grotto
    {.entranceIndex = ENTR_GROTTOS_0,         .content = 0x22, .scene = SCENE_HYRULE_FIELD},          // Hyrule Field -> HF Southeast Grotto
    {.entranceIndex = ENTR_GROTTOS_4,         .content = 0xFC, .scene = SCENE_LON_LON_RANCH},         // Lon Lon Ranch -> LLR Grotto
    {.entranceIndex = ENTR_GROTTOS_8,         .content = 0xED, .scene = SCENE_SACRED_FOREST_MEADOW},  // SFM Entryway -> SFM Wolfos Grotto
    {.entranceIndex = ENTR_GROTTOS_10,        .content = 0xEE, .scene = SCENE_SACRED_FOREST_MEADOW},  // Sacred Forest Meadow -> SFM Storms Grotto
    {.entranceIndex = ENTR_FAIRYS_FOUNTAIN_0, .content = 0xFF, .scene = SCENE_SACRED_FOREST_MEADOW},  // Sacred Forest Meadow -> SFM Fairy Grotto
    {.entranceIndex = ENTR_GROTTOS_7,         .content = 0xF5, .scene = SCENE_LOST_WOODS},            // LW Beyond Mido -> LW Scrubs Grotto
    {.entranceIndex = ENTR_GROTTOS_0,         .content = 0x14, .scene = SCENE_LOST_WOODS},            // Lost Woods -> LW Near Shortcuts Grotto
    {.entranceIndex = ENTR_GROTTOS_0,         .content = 0x2C, .scene = SCENE_KOKIRI_FOREST},         // Kokiri Forest -> KF Storms Grotto
    {.entranceIndex = ENTR_FAIRYS_FOUNTAIN_0, .content = 0xFF, .scene = SCENE_ZORAS_DOMAIN},          // Zoras Domain -> ZD Storms Grotto
    {.entranceIndex = ENTR_FAIRYS_FOUNTAIN_0, .content = 0xFF, .scene = SCENE_GERUDOS_FORTRESS},      // Gerudo Fortress -> GF Storms Grotto
    {.entranceIndex = ENTR_GROTTOS_10,        .content = 0xF0, .scene = SCENE_GERUDO_VALLEY},         // GV Fortress Side -> GV Storms Grotto
    {.entranceIndex = ENTR_GROTTOS_6,         .content = 0xF2, .scene = SCENE_GERUDO_VALLEY},         // GV Grotto Ledge -> GV Octorok Grotto
    {.entranceIndex = ENTR_GROTTOS_12,        .content = 0xF3, .scene = SCENE_LOST_WOODS},            // LW Beyond Mido -> Deku Theater

    // clang-format on
};

// Information necessary for setting up returning from a grotto
static const GrottoReturnInfo grottoReturnTable[NUM_GROTTOS] = {
    // clang-format off
    {.entranceIndex = ENTR_DESERT_COLOSSUS_EAST_EXIT,       .room = 0x00, .angle = 0xA71C, .pos = {.x =    62.5078f, .y =   -32.0f, .z = -1296.2f}},   // Colossus Grotto -> Desert Colossus
    {.entranceIndex = ENTR_LAKE_HYLIA_NORTH_EXIT,            .room = 0x00, .angle = 0x0000, .pos = {.x = -3039.34f,   .y = -1033.0f, .z =  6080.74f}},  // LH Grotto -> Lake Hylia
    {.entranceIndex = ENTR_ZORAS_RIVER_WEST_EXIT,           .room = 0x00, .angle = 0x0000, .pos = {.x = -1630.05f,   .y =   100.0f, .z =  -132.104f}}, // ZR Storms Grotto -> Zora River
    {.entranceIndex = ENTR_ZORAS_RIVER_WEST_EXIT,           .room = 0x00, .angle = 0xE000, .pos = {.x =   649.507f,  .y =   570.0f, .z =  -346.853f}}, // ZR Fairy Grotto -> Zora River
    {.entranceIndex = ENTR_ZORAS_RIVER_WEST_EXIT,           .room = 0x00, .angle = 0x8000, .pos = {.x =   362.29f,   .y =   570.0f, .z =   111.48f}},  // ZR Open Grotto -> Zora River
    {.entranceIndex = ENTR_DEATH_MOUNTAIN_CRATER_GC_EXIT, .room = 0x01, .angle = 0x31C7, .pos = {.x = -1666.73f,   .y =   721.0f, .z =  -459.21f}},  // DMC Hammer Grotto -> DMC Lower Local
    {.entranceIndex = ENTR_DEATH_MOUNTAIN_CRATER_UPPER_EXIT, .room = 0x01, .angle = 0x238E, .pos = {.x =    63.723f,  .y =  1265.0f, .z =  1791.39f}},  // DMC Upper Grotto -> DMC Upper Local
    {.entranceIndex = ENTR_GORON_CITY_UPPER_EXIT,            .room = 0x03, .angle = 0x0000, .pos = {.x =  1104.73f,   .y =   580.0f, .z = -1159.95f}},  // GC Grotto -> GC Grotto Platform
    {.entranceIndex = ENTR_DEATH_MOUNTAIN_TRAIL_GC_EXIT,  .room = 0x00, .angle = 0x8000, .pos = {.x =  -387.584f,  .y =  1386.0f, .z = -1213.05f}},  // DMT Storms Grotto -> Death Mountain
    {.entranceIndex = ENTR_DEATH_MOUNTAIN_TRAIL_GC_EXIT,  .room = 0x00, .angle = 0x8000, .pos = {.x =  -691.022f,  .y =  1946.0f, .z =  -312.969f}}, // DMT Cow Grotto -> Death Mountain Summit
    {.entranceIndex = ENTR_KAKARIKO_VILLAGE_FRONT_GATE,      .room = 0x00, .angle = 0x0000, .pos = {.x =   855.238f,  .y =    80.0f, .z =  -234.095f}}, // Kak Open Grotto -> Kak Backyard
    {.entranceIndex = ENTR_KAKARIKO_VILLAGE_FRONT_GATE,      .room = 0x00, .angle = 0x0000, .pos = {.x =  -401.873f,  .y =     0.0f, .z =   402.792f}}, // Kak Redead Grotto -> Kakariko Village
    {.entranceIndex = ENTR_CASTLE_GROUNDS_SOUTH_EXIT,         .room = 0x00, .angle = 0x9555, .pos = {.x =  1009.02f,   .y =  1571.0f, .z =   855.532f}}, // HC Storms Grotto -> Castle Grounds
    {.entranceIndex = ENTR_HYRULE_FIELD_CENTER_EXIT,          .room = 0x00, .angle = 0x1555, .pos = {.x = -4949.58f,   .y =  -300.0f, .z =  2837.59f}},  // HF Tektite Grotto -> Hyrule Field
    {.entranceIndex = ENTR_HYRULE_FIELD_CENTER_EXIT,          .room = 0x00, .angle = 0xC000, .pos = {.x =  2050.6f,    .y =    20.0f, .z =  -160.397f}}, // HF Near Kak Grotto -> Hyrule Field
    {.entranceIndex = ENTR_HYRULE_FIELD_CENTER_EXIT,          .room = 0x00, .angle = 0x0000, .pos = {.x = -4447.66f,   .y =  -300.0f, .z =  -393.191f}}, // HF Fairy Grotto -> Hyrule Field
    {.entranceIndex = ENTR_HYRULE_FIELD_CENTER_EXIT,          .room = 0x00, .angle = 0xE000, .pos = {.x = -1446.56f,   .y =     0.0f, .z =   830.775f}}, // HF Near Market Grotto -> Hyrule Field
    {.entranceIndex = ENTR_HYRULE_FIELD_CENTER_EXIT,          .room = 0x00, .angle = 0x0000, .pos = {.x = -7874.07f,   .y =  -300.0f, .z =  6921.31f}},  // HF Cow Grotto -> Hyrule Field
    {.entranceIndex = ENTR_HYRULE_FIELD_CENTER_EXIT,          .room = 0x00, .angle = 0xEAAB, .pos = {.x = -4989.13f,   .y =  -700.0f, .z = 13821.1f}},   // HF Inside Fence Grotto -> Hyrule Field
    {.entranceIndex = ENTR_HYRULE_FIELD_CENTER_EXIT,          .room = 0x00, .angle = 0x8000, .pos = {.x = -4032.61f,   .y =  -700.0f, .z = 13831.5f}},   // HF Open Grotto -> Hyrule Field
    {.entranceIndex = ENTR_HYRULE_FIELD_CENTER_EXIT,          .room = 0x00, .angle = 0x9555, .pos = {.x =  -288.313f,  .y =  -500.0f, .z = 12320.2f}},   // HF Southeast Grotto -> Hyrule Field
    {.entranceIndex = ENTR_LON_LON_RANCH_ENTRANCE,         .room = 0x00, .angle = 0xAAAB, .pos = {.x =  1775.92f,   .y =     0.0f, .z =  1486.82f}},  // LLR Grotto -> Lon Lon Ranch
    {.entranceIndex = ENTR_SACRED_FOREST_MEADOW_SOUTH_EXIT,  .room = 0x00, .angle = 0x8000, .pos = {.x =  -189.861f,  .y =     0.0f, .z =  1898.09f}},  // SFM Wolfos Grotto -> SFM Entryway
    {.entranceIndex = ENTR_SACRED_FOREST_MEADOW_SOUTH_EXIT,  .room = 0x00, .angle = 0xAAAB, .pos = {.x =   314.853f,  .y =   480.0f, .z = -2300.39f}},  // SFM Storms Grotto -> Sacred Forest Meadow
    {.entranceIndex = ENTR_SACRED_FOREST_MEADOW_SOUTH_EXIT,  .room = 0x00, .angle = 0x0000, .pos = {.x =    55.034f,  .y =     0.0f, .z =   250.595f}}, // SFM Fairy Grotto -> Sacred Forest Meadow
    {.entranceIndex = ENTR_LOST_WOODS_NORTH_EXIT,            .room = 0x08, .angle = 0x2000, .pos = {.x =   691.994f,  .y =     0.0f, .z = -2502.2f}},   // LW Scrubs Grotto -> LW Beyond Mido
    {.entranceIndex = ENTR_LOST_WOODS_SOUTH_EXIT,            .room = 0x02, .angle = 0xE000, .pos = {.x =   905.755f,  .y =     0.0f, .z =  -901.43f}},  // LW Near Shortcuts Grotto -> Lost Woods
    {.entranceIndex = ENTR_KOKIRI_FOREST_UPPER_EXIT,         .room = 0x00, .angle = 0x4000, .pos = {.x =  -507.065f,  .y =   380.0f, .z = -1220.43f}},  // KF Storms Grotto -> Kokiri Forest
    {.entranceIndex = ENTR_ZORAS_DOMAIN_ENTRANCE,          .room = 0x01, .angle = 0xD555, .pos = {.x =  -855.68f,   .y =    14.0f, .z =  -474.422f}}, // ZD Storms Grotto -> Zoras Domain
    {.entranceIndex = ENTR_GERUDOS_FORTRESS_EAST_EXIT,      .room = 0x00, .angle = 0x4000, .pos = {.x =   380.521f,  .y =   333.0f, .z = -1560.74f}},  // GF Storms Grotto -> Gerudo Fortress
    {.entranceIndex = ENTR_GERUDO_VALLEY_WEST_EXIT,         .room = 0x00, .angle = 0x9555, .pos = {.x = -1326.34f,   .y =    15.0f, .z =  -983.994f}}, // GV Storms Grotto -> GV Fortress Side
    {.entranceIndex = ENTR_GERUDO_VALLEY_EAST_EXIT,         .room = 0x00, .angle = 0x8000, .pos = {.x =   291.513f,  .y =  -555.0f, .z =  1478.39f}},  // GV Octorok Grotto -> GV Grotto Ledge
    {.entranceIndex = ENTR_LOST_WOODS_NORTH_EXIT,            .room = 0x06, .angle = 0x4000, .pos = {.x =   109.281f,  .y =   -20.0f, .z = -1601.42f}},  // Deku Theater -> LW Beyond Mido

    // clang-format on
};

static s16 grottoExitList[NUM_GROTTOS] = { 0 };
static s16 grottoLoadList[NUM_GROTTOS] = { 0 };
static s8 grottoId = 0xFF;
static s8 lastEntranceType = NOT_GROTTO;
static bool overridingNextEntrance = false;
static bool grottoEnteredViaDoorAna = false;

// A hole coordinate is an emergence origin, never an idle/death checkpoint.
// Ownership is exact and lasts only for this exterior visit and save/age.
typedef struct {
    bool queued;
    bool observing;
    bool landed;
    s16 grotto;
    s16 scene;
    s16 room;
    s16 entrance;
    s16 file;
    s16 age;
    s16 yaw;
    Vec3f origin;
    Vec3f position;
} GrottoLandingState;
static GrottoLandingState grottoLanding = { 0 };

static bool Grotto_LandingMatchesCurrent(void);
static void Grotto_SetRespawnLanding(RespawnMode mode);

// SOH-EXTREME Shovel semantics. This list mirrors the native randomizer
// regions that begin hidden by a bomb/song trigger, rock/boulder, or hammer
// obstacle. Permanently-open holes (HF/Kak/ZR open grottos, etc.) are omitted.
s32 Grotto_ActorRequiresShovel(Actor* thisx) {
    if (thisx == NULL || gPlayState == NULL) {
        return false;
    }

    // SOH-EXTREME semantics: Shovel owns EVERY physical grotto entrance,
    // including holes that are normally open.  Match the Door_Ana actor to
    // the native grotto load table so unrelated actors can never be gated.
    const s8 content = thisx->params & 0x00FF;
    const s8 scene = gPlayState->sceneNum;

    for (s16 index = 0; index < NUM_GROTTOS; index++) {
        if (content == grottoLoadTable[index].content && scene == grottoLoadTable[index].scene) {
            return true;
        }
    }

    return false;
}

// Initialize both lists so that each index refers to itself. An index referring
// to itself means that the entrance is not shuffled. Indices will be overwritten
// later in Entrance_Init() in entrance.c if entrance shuffle is enabled.
// For the grotto load list, the entrance index is 0x0700 + the grotto id
// For the grotto exit list, the entrance index is 0x0800 + the grotto id
void Grotto_InitExitAndLoadLists(void) {
    for (u8 i = 0; i < NUM_GROTTOS; i++) {
        grottoLoadList[i] = ENTRANCE_GROTTO_LOAD_START + i;
        grottoExitList[i] = ENTRANCE_GROTTO_EXIT_START + i;
    }

    grottoId = 0xFF;
    lastEntranceType = NOT_GROTTO;
    overridingNextEntrance = false;
    grottoEnteredViaDoorAna = false;
    grottoLanding = (GrottoLandingState){ 0 };
}

static bool Grotto_ShouldSetLastEntrance(void) {
    return Randomizer_GetSettingValue(RSK_SHUFFLE_GROTTO_ENTRANCES) &&
           (Randomizer_GetSettingValue(RSK_MIX_GROTTO_ENTRANCES) ||
            Randomizer_GetSettingValue(RSK_DECOUPLED_ENTRANCES));
}

void Grotto_SetExitOverride(s16 originalIndex, s16 overrideIndex) {
    s16 id = originalIndex & 0x00FF;
    grottoExitList[id] = overrideIndex;
}

void Grotto_SetLoadOverride(s16 originalIndex, s16 overrideIndex) {
    s16 id = originalIndex & 0x00FF;
    grottoLoadList[id] = overrideIndex;
}

static void Grotto_SetupReturnInfo(GrottoReturnInfo grotto, RespawnMode respawnMode) {
    // Set necessary grotto return data to the Entrance Point, so that voiding out and setting FW work correctly
    gSaveContext.respawn[respawnMode].entranceIndex = grotto.entranceIndex;
    gSaveContext.respawn[respawnMode].roomIndex = grotto.room;
    gSaveContext.respawn[respawnMode].playerParams = 0x04FF; // exiting grotto with no initial camera focus
    gSaveContext.respawn[respawnMode].yaw = grotto.angle;
    gSaveContext.respawn[respawnMode].pos = grotto.pos;
    // If Mixed Entrance Pools or decoupled entrances are active, set these flags to 0 instead of restoring them
    if (Randomizer_GetSettingValue(RSK_MIX_GROTTO_ENTRANCES) || Randomizer_GetSettingValue(RSK_DECOUPLED_ENTRANCES)) {
        gSaveContext.respawn[respawnMode].tempSwchFlags = 0;
        gSaveContext.respawn[respawnMode].tempCollectFlags = 0;
    } else {
        gSaveContext.respawn[respawnMode].tempSwchFlags = gSaveContext.respawn[RESPAWN_MODE_RETURN].tempSwchFlags;
        gSaveContext.respawn[respawnMode].tempCollectFlags = gSaveContext.respawn[RESPAWN_MODE_RETURN].tempCollectFlags;
    }
}

// Get the next entrance value while handling conversion of grotto rando IDs to real entrance values.
// This method doesn't change player respawn data, so only use this if you are querying an entrance index.
s16 Grotto_GetEntranceValueHandlingGrottoRando(s16 nextEntranceIndex) {
    const s16 apDoor = Archipelago_ResolveDoorArrival(nextEntranceIndex, true);
    if (apDoor != nextEntranceIndex) return apDoor;
    // Don't change anything unless grotto shuffle has been enabled
    if (!Archipelago_EntranceShuffleActive() &&
        !Randomizer_GetSettingValue(RSK_SHUFFLE_GROTTO_ENTRANCES) &&
        !Randomizer_GetSettingValue(RSK_SHUFFLE_OVERWORLD_SPAWNS) &&
        !Randomizer_GetSettingValue(RSK_SHUFFLE_WARP_SONGS)) {
        return nextEntranceIndex;
    }

    // If Link hits a grotto exit, load the entrance index from the grotto exit list
    // based on the current grotto ID
    if (nextEntranceIndex == ENTR_RETURN_GROTTO) {
        nextEntranceIndex = grottoExitList[grottoId];
        const s16 apExit = Archipelago_ResolveDoorArrival(nextEntranceIndex, true);
        if (apExit != nextEntranceIndex) return apExit;
    }

    // Get the new grotto id from the next entrance, temp value to override modifying the static one
    s8 tempGrottoId = nextEntranceIndex & 0x00FF;

    // Grotto Returns
    if (nextEntranceIndex >= ENTRANCE_GROTTO_EXIT_START &&
        nextEntranceIndex < ENTRANCE_GROTTO_EXIT_START + NUM_GROTTOS) {
        GrottoReturnInfo grotto = grottoReturnTable[tempGrottoId];

        // When the nextEntranceIndex is determined by a dynamic exit,
        // or set by Entrance_OverrideBlueWarp to mark a blue warp entrance,
        // we have to set the respawn information and nextEntranceIndex manually
        if (gPlayState != NULL && gPlayState->nextEntranceIndex != ENTR_LOAD_OPENING) {
            nextEntranceIndex = grotto.entranceIndex;
        } else if (gPlayState == NULL) { // Handle spawn position when loading from a save file
            nextEntranceIndex = grotto.entranceIndex;
            // Otherwise return 0x7FFF (ENTR_RETURN_GROTTO) and let the game handle it
        } else {
            nextEntranceIndex = ENTR_RETURN_GROTTO;
        }
        // Grotto Loads
    } else if (nextEntranceIndex >= ENTRANCE_GROTTO_LOAD_START && nextEntranceIndex < ENTRANCE_GROTTO_EXIT_START) {
        GrottoLoadInfo grotto = grottoLoadTable[tempGrottoId];
        nextEntranceIndex = grotto.entranceIndex;
    }

    return nextEntranceIndex;
}

// Translates and overrides the passed in entrance index if it corresponds to a
// special grotto entrance (grotto load or return point) and updates player respawn data correctly.
s16 Grotto_OverrideSpecialEntrance(s16 nextEntranceIndex) {
    const s16 apDoor = Archipelago_ResolveDoorArrival(nextEntranceIndex, false);
    if (apDoor != nextEntranceIndex) return apDoor;
    // Don't change anything unless grotto shuffle has been enabled
    if (!Archipelago_EntranceShuffleActive() &&
        !Randomizer_GetSettingValue(RSK_SHUFFLE_GROTTO_ENTRANCES) &&
        !Randomizer_GetSettingValue(RSK_SHUFFLE_OVERWORLD_SPAWNS) &&
        !Randomizer_GetSettingValue(RSK_SHUFFLE_WARP_SONGS)) {
        return Archipelago_ResolvedEntranceArrival(nextEntranceIndex, nextEntranceIndex);
    }

    // ENTR_RETURN_GROTTO means Link physically left a grotto. Any other way (warp song / owl / spawn)
    // arrives as a concrete grotto-exit index.
    bool grottoExit = nextEntranceIndex == ENTR_RETURN_GROTTO;

    // If Link hits a grotto exit, load the entrance index from the grotto exit list
    // based on the current grotto ID
    if (grottoExit) {
        Archipelago_RecordEntrance(ENTRANCE_GROTTO_EXIT_START + grottoId);
        Entrance_SetEntranceDiscovered(ENTRANCE_GROTTO_EXIT_START + grottoId, false);
        EntranceTracker_SetLastEntranceOverride(ENTRANCE_GROTTO_EXIT_START + grottoId);
        nextEntranceIndex = grottoExitList[grottoId];
        const s16 apExit = Archipelago_ResolveDoorArrival(nextEntranceIndex, false);
        if (apExit != nextEntranceIndex) return apExit;
    }

    const s16 apTarget = nextEntranceIndex;
    grottoLanding = (GrottoLandingState){ 0 };
    // Get the new grotto id from the next entrance
    grottoId = nextEntranceIndex & 0x00FF;

    // Grotto Returns
    if (nextEntranceIndex >= ENTRANCE_GROTTO_EXIT_START &&
        nextEntranceIndex < ENTRANCE_GROTTO_EXIT_START + NUM_GROTTOS) {
        GrottoReturnInfo grotto = grottoReturnTable[grottoId];

        // Normally grotto exit leaves pre-grotto respawn data that Door_Ana set on entry alone,
        // so void-out returns to other last entrance. This is only when leaving grotto entered through
        // Door_Ana (grottoExit && grottoEnteredViaDoorAna): only then does RESPAWN_MODE_RETURN hold
        // valid pre-grotto data. A warp song or spawn shuffled onto a grotto load point enters without
        // Door_Ana (so RETURN is stale), those must set up the grotto's own return data to position Link.
        bool normalGrottoExit = !Grotto_ShouldSetLastEntrance() && grottoExit && grottoEnteredViaDoorAna;

        if (!normalGrottoExit) {
            Grotto_SetupReturnInfo(grotto, RESPAWN_MODE_RETURN);
            Grotto_SetupReturnInfo(grotto, RESPAWN_MODE_DOWN);
        }

        // When the nextEntranceIndex is determined by a dynamic exit,
        // or set by Entrance_OverrideBlueWarp to mark a blue warp entrance,
        // we have to set the respawn information and nextEntranceIndex manually
        if (gPlayState != NULL && gPlayState->nextEntranceIndex != ENTR_LOAD_OPENING) {
            gSaveContext.respawnFlag = 2;
            nextEntranceIndex =
                normalGrottoExit ? gSaveContext.respawn[RESPAWN_MODE_RETURN].entranceIndex : grotto.entranceIndex;
            gPlayState->transitionType = TRANS_TYPE_FADE_WHITE;
            gSaveContext.nextTransitionType = TRANS_TYPE_FADE_WHITE;
        } else if (gPlayState == NULL) { // Handle spawn position when loading from a save file
            gSaveContext.respawnFlag = 2;
            nextEntranceIndex = grotto.entranceIndex;
            gSaveContext.nextTransitionType = TRANS_TYPE_FADE_WHITE;
            // Otherwise return 0x7FFF (ENTR_RETURN_GROTTO) and let the game handle it
        } else {
            nextEntranceIndex = ENTR_RETURN_GROTTO;
        }

        lastEntranceType = normalGrottoExit ? NOT_GROTTO : GROTTO_RETURN;
        // Grotto Loads
    } else if (nextEntranceIndex >= ENTRANCE_GROTTO_LOAD_START && nextEntranceIndex < ENTRANCE_GROTTO_EXIT_START) {
        // Set the respawn data to load the correct grotto
        GrottoLoadInfo grotto = grottoLoadTable[grottoId];
        gSaveContext.respawn[RESPAWN_MODE_RETURN].data = grotto.content;
        nextEntranceIndex = grotto.entranceIndex;

        EntranceTracker_SetCurrentGrottoID(grottoId);

        lastEntranceType = NOT_GROTTO;
        grottoEnteredViaDoorAna = false;
        // Otherwise just unset the current grotto ID
    } else {
        grottoId = 0xFF;
        lastEntranceType = NOT_GROTTO;
    }

    overridingNextEntrance = true;
    return Archipelago_ResolvedEntranceArrival(apTarget, nextEntranceIndex);
}

// Override the entrance index when entering into a grotto actor
// thisx - pointer to the grotto actor
void Grotto_OverrideActorEntrance(Actor* thisx) {
    // Vanilla Behavior if there's no possibility of ending up in a grotto randomly
    if (!Archipelago_EntranceShuffleActive() &&
        !Randomizer_GetSettingValue(RSK_SHUFFLE_GROTTO_ENTRANCES) &&
        !Randomizer_GetSettingValue(RSK_SHUFFLE_OVERWORLD_SPAWNS) &&
        !Randomizer_GetSettingValue(RSK_SHUFFLE_WARP_SONGS)) {
        return;
    }

    s8 grottoContent = thisx->params & 0x00FF;

    // Loop through the grotto load table until we find the matching index based
    // on content and scene
    for (s16 index = 0; index < NUM_GROTTOS; index++) {

        if (grottoContent == grottoLoadTable[index].content && gPlayState->sceneNum == grottoLoadTable[index].scene) {
            // Find the override for the matching index from the grotto Load List
            Entrance_SetEntranceDiscovered(ENTRANCE_GROTTO_LOAD_START + index, false);
            EntranceTracker_SetLastEntranceOverride(ENTRANCE_GROTTO_LOAD_START + index);
            Archipelago_RecordEntrance(ENTRANCE_GROTTO_LOAD_START + index);
            index = grottoLoadList[index];

            // Run the index through the special entrances override check
            lastEntranceType = GROTTO_LOAD;
            gPlayState->nextEntranceIndex = Grotto_OverrideSpecialEntrance(index);
            grottoEnteredViaDoorAna = true;
            return;
        }
    }
}

// Set necessary flags for when warp songs/overworld spawns are shuffled to grotto return points
void Grotto_ForceGrottoReturnOnSpecialEntrance(void) {
    if (lastEntranceType == GROTTO_RETURN && (Archipelago_EntranceShuffleActive() ||
                                              Randomizer_GetSettingValue(RSK_SHUFFLE_GROTTO_ENTRANCES) ||
                                              Randomizer_GetSettingValue(RSK_SHUFFLE_OVERWORLD_SPAWNS) ||
                                              Randomizer_GetSettingValue(RSK_SHUFFLE_WARP_SONGS))) {
        gSaveContext.respawnFlag = 2;
        Grotto_SetRespawnLanding(RESPAWN_MODE_RETURN);
        if (!Archipelago_EntranceShuffleActive())
            gSaveContext.respawn[RESPAWN_MODE_RETURN].playerParams = 0x04FF;
        // Clear current temp flags
        gSaveContext.respawn[RESPAWN_MODE_RETURN].tempSwchFlags = 0;
        gSaveContext.respawn[RESPAWN_MODE_RETURN].tempCollectFlags = 0;
    }
}

// Set the respawn flag for when we want to return from a grotto entrance
// Used for Sun's Song and Game Over, which usually don't restore saved position data
void Grotto_ForceGrottoReturn(void) {
    if (lastEntranceType == GROTTO_RETURN && (Archipelago_EntranceShuffleActive() ||
                                              Randomizer_GetSettingValue(RSK_SHUFFLE_GROTTO_ENTRANCES) ||
                                              Randomizer_GetSettingValue(RSK_SHUFFLE_OVERWORLD_SPAWNS) ||
                                              Randomizer_GetSettingValue(RSK_SHUFFLE_WARP_SONGS))) {
        gSaveContext.respawnFlag = 2;
        Grotto_SetRespawnLanding(RESPAWN_MODE_RETURN);
        // Save the current temp flags in the grotto return point, so they'll properly keep their values.
        gSaveContext.respawn[RESPAWN_MODE_RETURN].tempSwchFlags = gPlayState->actorCtx.flags.tempSwch;
        gSaveContext.respawn[RESPAWN_MODE_RETURN].tempCollectFlags = gPlayState->actorCtx.flags.tempCollect;
    }
}

// Used for the DMT special voids, which usually don't restore saved position data
void Grotto_ForceRegularVoidOut(void) {
    if (lastEntranceType == GROTTO_RETURN && (Archipelago_EntranceShuffleActive() ||
                                              Randomizer_GetSettingValue(RSK_SHUFFLE_GROTTO_ENTRANCES) ||
                                              Randomizer_GetSettingValue(RSK_SHUFFLE_OVERWORLD_SPAWNS) ||
                                              Randomizer_GetSettingValue(RSK_SHUFFLE_WARP_SONGS))) {
        gSaveContext.respawn[RESPAWN_MODE_DOWN] = gSaveContext.respawn[RESPAWN_MODE_RETURN];
        Grotto_SetRespawnLanding(RESPAWN_MODE_DOWN);
        gSaveContext.respawnFlag = 1;
    }
}

// If returning to a FW point saved at a grotto exit, copy the FW data to the Grotto Return Point
// so that Sun's Song and Game Over will behave correctly
void Grotto_SetupReturnInfoOnFWReturn(void) {
    if ((Archipelago_EntranceShuffleActive() && gSaveContext.fw.playerParams == 0x04FF) ||
        Randomizer_GetSettingValue(RSK_SHUFFLE_GROTTO_ENTRANCES) ||
        Randomizer_GetSettingValue(RSK_SHUFFLE_OVERWORLD_SPAWNS) ||
        Randomizer_GetSettingValue(RSK_SHUFFLE_WARP_SONGS) && gSaveContext.fw.playerParams == 0x04FF) {
        gSaveContext.respawn[RESPAWN_MODE_RETURN] = gSaveContext.respawn[RESPAWN_MODE_TOP];
        // An old FW point with emergence parameters can still be at the hole.
        // Keep its native emergence until the destination can prove a landing.
        gSaveContext.respawn[RESPAWN_MODE_RETURN].playerParams =
            Archipelago_EntranceShuffleActive() ? 0x04FF : 0x0DFF;
        lastEntranceType = GROTTO_RETURN;
    } else {
        lastEntranceType = NOT_GROTTO;
    }
}

// If a scene transition is not overridden at all (i.e. guards throwing Link out / quitting game)
// the lastEntranceType must be cleared to avoid messing up savewarps and deathwarps.
// This does not apply to void out and other respawns, which should keep the lastEntranceType.
void Grotto_SanitizeEntranceType(void) {
    if (!overridingNextEntrance && gSaveContext.respawnFlag == 0) {
        lastEntranceType = NOT_GROTTO;
        grottoLanding = (GrottoLandingState){ 0 };
    }
    overridingNextEntrance = false;
}

// Get the renamed entrance index based on the grotto contents and exit scene number
s16 Grotto_GetRenamedGrottoIndexFromOriginal(s8 content, s8 scene) {
    for (s16 index = 0; index < NUM_GROTTOS; index++) {
        if (content == grottoLoadTable[index].content && scene == grottoLoadTable[index].scene) {
            return ENTRANCE_GROTTO_LOAD_START | index;
        }
    }

    return ENTRANCE_GROTTO_LOAD_START;
}

s8 Grotto_CurrentGrotto() {
    if (Archipelago_EntranceShuffleActive() || Randomizer_GetSettingValue(RSK_SHUFFLE_GROTTO_ENTRANCES) ||
        Randomizer_GetSettingValue(RSK_SHUFFLE_OVERWORLD_SPAWNS) ||
        Randomizer_GetSettingValue(RSK_SHUFFLE_WARP_SONGS)) {
        return grottoId;
    } else {
        s16 entrance = gSaveContext.respawn[RESPAWN_MODE_RETURN].entranceIndex;
        s8 scene = gEntranceTable[entrance].scene;
        s8 data = gSaveContext.respawn[RESPAWN_MODE_RETURN].data;
        return Grotto_GetRenamedGrottoIndexFromOriginal(data, scene) & 0xFF;
    }
}

// SOH-EXTREME exterior grotto landing ownership and geometry.
static bool Grotto_LandingMatchesCurrent(void) {
    return gPlayState != NULL && Archipelago_EntranceShuffleActive() &&
           grottoLanding.grotto >= 0 && grottoLanding.grotto < NUM_GROTTOS &&
           grottoId == grottoLanding.grotto && grottoLanding.scene == gPlayState->sceneNum &&
           grottoLanding.room == gPlayState->roomCtx.curRoom.num &&
           grottoLanding.entrance == gSaveContext.entranceIndex &&
           grottoLanding.file == gSaveContext.fileNum && grottoLanding.age == gSaveContext.linkAge;
}

static bool Grotto_FinitePosition(const Vec3f* point) {
    return isfinite(point->x) && isfinite(point->y) && isfinite(point->z) &&
           fabsf(point->x) <= 32766.0f && fabsf(point->y) <= 32766.0f && fabsf(point->z) <= 32766.0f;
}

static bool Grotto_PointClearOfHoles(const Vec3f* point, f32 margin) {
    for (s32 category = 0; category < ACTORCAT_MAX; ++category) {
        for (Actor* actor = gPlayState->actorCtx.actorLists[category].head; actor != NULL; actor = actor->next) {
            if (actor->id != ACTOR_DOOR_ANA || actor->update == NULL) continue;
            // Include dormant, Shovel-hidden and still-covered Door_Ana actors.
            // Their static scene floor alone cannot reveal the trigger.
            const f32 dx = point->x - actor->world.pos.x;
            const f32 dz = point->z - actor->world.pos.z;
            if (fabsf(point->y - actor->world.pos.y) <= 60.0f &&
                dx * dx + dz * dz <= (15.0f + margin) * (15.0f + margin)) return false;
        }
    }
    return true;
}

s32 Grotto_CanCaptureReturnPoint(Actor* actor) {
    if (gPlayState == NULL || actor == NULL) return false;
    const Player* player = GET_PLAYER(gPlayState);
    if (player == NULL || actor != &player->actor ||
        (player->stateFlags1 & PLAYER_STATE1_FLOOR_DISABLED)) return false;
    return Grotto_FinitePosition(&actor->world.pos) && Grotto_PointClearOfHoles(&actor->world.pos, 4.0f);
}

static bool Grotto_StaticGround(const Vec3f* point, f32 probeY, f32* floor, CollisionPoly** poly) {
    s32 bgId = BGCHECK_SCENE;
    Vec3f probe = *point;
    probe.y = probeY;
    *poly = NULL;
    *floor = BgCheck_EntityRaycastFloor3(&gPlayState->colCtx, poly, &bgId, &probe);
    if (*poly == NULL || bgId != BGCHECK_SCENE || !isfinite(*floor) || *floor <= BGCHECK_Y_MIN ||
        COLPOLY_GET_NORMAL((*poly)->normal.y) < 0.8f ||
        SurfaceType_GetSceneExitIndex(&gPlayState->colCtx, *poly, bgId) != 0 ||
        SurfaceType_GetFloorEffect(&gPlayState->colCtx, *poly, bgId) == 2 ||
        SurfaceType_IsWallDamage(&gPlayState->colCtx, *poly, bgId) ||
        SurfaceType_GetConveyorSpeed(&gPlayState->colCtx, *poly, bgId) != 0) return false;
    const u32 floorType = SurfaceType_GetFloorType(&gPlayState->colCtx, *poly, bgId);
    const u32 floorProperty = func_80041EA4(&gPlayState->colCtx, *poly, bgId);
    if (floorType == 2 || floorType == 3 || floorType == 4 || floorType == 7 || floorType == 12 ||
        floorProperty == 5 || floorProperty == 12) return false;
    f32 surface = *floor;
    WaterBox* water = NULL;
    if (WaterBox_GetSurface1(gPlayState, &gPlayState->colCtx, point->x, point->z, &surface, &water) &&
        (!isfinite(surface) || surface > *floor)) return false;
    return true;
}

static bool Grotto_ClearBodyPath(Player* player, const Vec3f* from, const Vec3f* to) {
    Vec3f previous = *from, next = *to, adjusted;
    CollisionPoly* poly = NULL;
    s32 bgId = BGCHECK_SCENE;
    f32 ceilingY;
    if (BgCheck_EntitySphVsWall3(&gPlayState->colCtx, &adjusted, &next, &previous,
                               player->ageProperties->wallCheckRadius, &poly, &bgId, &player->actor, 26.0f))
        return false;
    if (BgCheck_EntityCheckCeiling(&gPlayState->colCtx, &ceilingY, &next,
                                 player->ageProperties->ceilingCheckHeight, &poly, &bgId, &player->actor))
        return false;
    return true;
}

static bool Grotto_CylinderOverlapsPlayer(const ColliderCylinder* cylinder, const Vec3f* feet,
                                         f32 radius, f32 height) {
    if (!(cylinder->base.ocFlags1 & OC1_ON) || !(cylinder->info.ocElemFlags & OCELEM_ON)) return false;
    const f32 bottom = cylinder->dim.pos.y + cylinder->dim.yShift;
    if (feet->y + height <= bottom || feet->y >= bottom + cylinder->dim.height) return false;
    const f32 dx = feet->x - cylinder->dim.pos.x;
    const f32 dz = feet->z - cylinder->dim.pos.z;
    const f32 separation = radius + cylinder->dim.radius;
    return dx * dx + dz * dz <= separation * separation;
}

static bool Grotto_ClearActorCollisions(Player* player, const Vec3f* point) {
    const f32 radius = player->ageProperties->wallCheckRadius;
    const f32 height = player->ageProperties->ceilingCheckHeight;
    Actor* exclusions[] = { &player->actor };
    // Use native OC checks for registered cylinders/joint spheres. Sample the
    // center and player perimeter; the important rock actors are also checked
    // below because their PROP updates register OC after this player update.
    for (s32 i = 0; i < 9; ++i) {
        Vec3f bottom = *point;
        if (i != 0) {
            const s16 angle = (s16)((i - 1) * 0x2000);
            bottom.x += Math_SinS(angle) * radius;
            bottom.z += Math_CosS(angle) * radius;
        }
        bottom.y += 1.0f;
        Vec3f top = bottom;
        top.y = point->y + height;
        if (CollisionCheck_LineOCCheck(gPlayState, &gPlayState->colChkCtx, &bottom, &top, exclusions, 1)) return false;
    }
    for (s32 category = 0; category < ACTORCAT_MAX; ++category) {
        for (Actor* actor = gPlayState->actorCtx.actorLists[category].head; actor != NULL; actor = actor->next) {
            if (actor == &player->actor || actor->id == ACTOR_DOOR_ANA || actor->update == NULL) continue;
            const f32 dx = point->x - actor->world.pos.x;
            const f32 dz = point->z - actor->world.pos.z;
            if (fabsf(point->y - actor->world.pos.y) > 200.0f || dx * dx + dz * dz > 160.0f * 160.0f) continue;
            // Uninitialized nearby actors cannot prove a clear arrival yet.
            if (actor->init != NULL) return false;
            if (MegaSoul_ShouldDisableActorCollision(actor)) continue;
            if (actor->id == ACTOR_OBJ_BOMBIWA) {
                if (Grotto_CylinderOverlapsPlayer(&((ObjBombiwa*)actor)->collider, point, radius, height)) return false;
            } else if (actor->id == ACTOR_EN_ISHI) {
                if (Grotto_CylinderOverlapsPlayer(&((EnIshi*)actor)->collider, point, radius, height)) return false;
            } else if (actor->colChkInfo.mass == MASS_IMMOVABLE &&
                       (actor->colChkInfo.cylRadius <= 0 || actor->colChkInfo.cylHeight <= 0)) {
                // Mido and other NPCs can have real OC cylinders but zero
                // generic body dimensions. Before their first OC registration
                // there is no proven clearance, so keep native emergence.
                return false;
            } else if (actor->colChkInfo.cylRadius > 0 && actor->colChkInfo.cylHeight > 0) {
                // Scene actors that have not registered their first OC keep a
                // conservative body exclusion. No actor is moved or disabled.
                f32 actorRadius = actor->colChkInfo.cylRadius;
                if (actor->colChkInfo.mass == MASS_IMMOVABLE && actorRadius < 64.0f) actorRadius = 64.0f;
                if (point->y < actor->world.pos.y + actor->colChkInfo.cylHeight &&
                    point->y + height > actor->world.pos.y &&
                    dx * dx + dz * dz <= (radius + actorRadius) * (radius + actorRadius)) return false;
            }
        }
    }
    return true;
}

static bool Grotto_ValidateLanding(Player* player, Vec3f* point, CollisionPoly** resultPoly) {
    if (!Grotto_FinitePosition(point) || !Grotto_PointClearOfHoles(point, player->ageProperties->wallCheckRadius + 1.0f))
        return false;
    f32 floor;
    if (!Grotto_StaticGround(point, point->y + 8.0f, &floor, resultPoly) || fabsf(floor - point->y) > 8.0f)
        return false;
    point->y = floor;
    // The whole standing footprint needs support; do not place Link on the
    // very edge of a ledge or on a thin point between disconnected platforms.
    for (s32 i = 0; i < 8; ++i) {
        Vec3f edge = *point;
        const s16 angle = (s16)(i * 0x2000);
        edge.x += Math_SinS(angle) * (player->ageProperties->wallCheckRadius + 1.0f);
        edge.z += Math_CosS(angle) * (player->ageProperties->wallCheckRadius + 1.0f);
        CollisionPoly* edgePoly;
        f32 edgeFloor;
        if (!Grotto_StaticGround(&edge, point->y + 8.0f, &edgeFloor, &edgePoly) ||
            fabsf(edgeFloor - point->y) > 8.0f) return false;
    }
    return Grotto_ClearBodyPath(player, point, point) && Grotto_ClearActorCollisions(player, point);
}

// Follow the native neutral-input emergence: physics precedes the action,
// vy=12, emergence gravity=-1, ramp horizontal speed by .5 to 3 below vy=6,
// then ordinary neutral fall decelerates .1. Every descending candidate is
// constrained by the destination's real collision; no constant XY offset is
// assumed to be a safe landing. Unusual geometry keeps native emergence.
static bool Grotto_FindReturnLanding(Player* player, Vec3f* result, CollisionPoly** resultPoly) {
    const f32 rate = R_UPDATE_RATE * 0.5f;
    if (rate <= 0.0f || rate > 1.5f || gPlayState->colCtx.colHeader == NULL ||
        gPlayState->roomCtx.status != 0) return false;
    Vec3f point = grottoLanding.origin;
    f32 velocityY = 12.0f, gravity = 0.0f, speed = 0.0f;
    bool falling = false;
    for (s32 step = 0; step < 64; ++step) {
        Vec3f next = point;
        velocityY += gravity;
        if (velocityY < -20.0f) velocityY = -20.0f;
        next.x += Math_SinS(grottoLanding.yaw) * speed * rate;
        next.y += velocityY * rate;
        next.z += Math_CosS(grottoLanding.yaw) * speed * rate;
        if (!Grotto_FinitePosition(&next) || !Grotto_ClearBodyPath(player, &point, &next)) return false;
        if (velocityY < 0.0f) {
            CollisionPoly* poly;
            f32 floor;
            if (!Grotto_StaticGround(&next, point.y + 1.0f, &floor, &poly)) return false;
            if (next.y <= floor && point.y >= floor) {
                if (fabsf(floor - grottoLanding.origin.y) > 20.0f) return false;
                next.y = floor;
                if (!Grotto_ValidateLanding(player, &next, resultPoly)) return false;
                *result = next;
                return true;
            }
        }
        point = next;
        if (!falling) {
            gravity = -1.0f;
            if (velocityY < 0.0f) falling = true;
            else if (velocityY < 6.0f) speed = fminf(speed + 0.5f, 3.0f);
        } else {
            gravity = REG(68) / 100.0f;
            speed = fmaxf(speed - 0.1f, 0.0f);
        }
    }
    return false;
}

static void Grotto_SaveLandedPoint(Player* player) {
    grottoLanding.position = player->actor.world.pos;
    grottoLanding.yaw = player->actor.shape.rot.y;
    grottoLanding.landed = true;
    grottoLanding.queued = false;
    grottoLanding.observing = false;
    for (s32 mode = RESPAWN_MODE_DOWN; mode <= RESPAWN_MODE_RETURN; ++mode) {
        RespawnData* respawn = &gSaveContext.respawn[mode];
        respawn->entranceIndex = gSaveContext.entranceIndex;
        respawn->roomIndex = gPlayState->roomCtx.curRoom.num;
        respawn->pos = grottoLanding.position;
        respawn->yaw = grottoLanding.yaw;
        respawn->playerParams = 0x0DFF;
        respawn->tempSwchFlags = gPlayState->actorCtx.flags.tempSwch;
        respawn->tempCollectFlags = gPlayState->actorCtx.flags.tempCollect;
    }
    Archipelago_EntranceRememberGrottoLanding();
}

s32 Grotto_QueueReturnLanding(Actor* actor) {
    if (gPlayState == NULL || actor == NULL || !Archipelago_EntranceShuffleActive() ||
        grottoId < 0 || grottoId >= NUM_GROTTOS ||
        gPlayState->sceneNum != grottoLoadTable[grottoId].scene ||
        gPlayState->roomCtx.curRoom.num < 0 || gPlayState->roomCtx.curRoom.num >= gPlayState->numRooms ||
        !Grotto_FinitePosition(&actor->world.pos)) return false;
    grottoLanding = (GrottoLandingState){ 0 };
    grottoLanding.queued = true;
    grottoLanding.grotto = grottoId;
    grottoLanding.scene = gPlayState->sceneNum;
    grottoLanding.room = gPlayState->roomCtx.curRoom.num;
    grottoLanding.entrance = gSaveContext.entranceIndex;
    grottoLanding.file = gSaveContext.fileNum;
    grottoLanding.age = gSaveContext.linkAge;
    grottoLanding.yaw = actor->shape.rot.y;
    grottoLanding.origin = actor->world.pos;
    return true;
}

s32 Grotto_HasPendingReturnLanding(void) {
    return (grottoLanding.queued || grottoLanding.observing) && Grotto_LandingMatchesCurrent();
}

s32 Grotto_ResolveReturnLanding(Actor* actor) {
    if (!grottoLanding.queued) return 0;
    if (!Grotto_LandingMatchesCurrent() || actor == NULL || GET_PLAYER(gPlayState) == NULL ||
        actor != &GET_PLAYER(gPlayState)->actor) {
        grottoLanding = (GrottoLandingState){ 0 };
        return 0;
    }
    Player* player = (Player*)actor;
    Vec3f position;
    CollisionPoly* floorPoly;
    grottoLanding.queued = false;
    if (!Grotto_FindReturnLanding(player, &position, &floorPoly)) {
        grottoLanding.observing = true;
        return 2;
    }
    const Vec3f delta = { position.x - actor->world.pos.x, position.y - actor->world.pos.y,
                         position.z - actor->world.pos.z };
    actor->world.pos = actor->home.pos = actor->prevPos = position;
    actor->focus.pos.x += delta.x;
    actor->focus.pos.y += delta.y;
    actor->focus.pos.z += delta.z;
    actor->floorHeight = player->fallStartHeight = position.y;
    actor->floorPoly = floorPoly;
    actor->floorBgId = BGCHECK_SCENE;
    actor->bgCheckFlags |= BGCHECKFLAG_GROUND;
    actor->velocity = (Vec3f){ 0 };
    actor->colChkInfo.displacement = (Vec3f){ 0 };
    actor->speedXZ = player->linearVelocity = 0.0f;
    actor->params = 0x0DFF;
    gSaveContext.entranceSpeed = 0.0f;
    Grotto_SaveLandedPoint(player);
    return 1;
}

void Grotto_UpdateReturnLanding(Actor* actor) {
    if (!grottoLanding.observing) return;
    if (!Grotto_LandingMatchesCurrent() || actor == NULL || GET_PLAYER(gPlayState) == NULL ||
        actor != &GET_PLAYER(gPlayState)->actor) {
        grottoLanding = (GrottoLandingState){ 0 };
        return;
    }
    Player* player = (Player*)actor;
    if (!(actor->bgCheckFlags & BGCHECKFLAG_GROUND) || actor->floorBgId != BGCHECK_SCENE ||
        (player->stateFlags1 & (PLAYER_STATE1_FLOOR_DISABLED | PLAYER_STATE1_IN_WATER))) return;
    Vec3f point = actor->world.pos;
    CollisionPoly* poly;
    if (Grotto_ValidateLanding(player, &point, &poly) && fabsf(point.y - actor->world.pos.y) <= 1.0f)
        Grotto_SaveLandedPoint(player);
}

static void Grotto_SetRespawnLanding(RespawnMode mode) {
    RespawnData* respawn = &gSaveContext.respawn[mode];
    if (grottoLanding.landed && Grotto_LandingMatchesCurrent()) {
        respawn->pos = grottoLanding.position;
        respawn->yaw = grottoLanding.yaw;
        respawn->playerParams = 0x0DFF;
    } else {
        respawn->pos = grottoReturnTable[grottoId].pos;
        respawn->yaw = grottoReturnTable[grottoId].angle;
        // Without a proven landing an AP return must keep emergence, not idle
        // on the trigger. Native non-AP save/void behavior remains unchanged.
        respawn->playerParams = Archipelago_EntranceShuffleActive() ? 0x04FF : 0x0DFF;
    }
}
