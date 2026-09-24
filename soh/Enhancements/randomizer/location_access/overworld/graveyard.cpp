#include "soh/Enhancements/randomizer/location_access.h"
#include "soh/Enhancements/randomizer/entrance.h"

using namespace Rando;

// LOCATION / EVENT_ACCESS / ENTRANCE wrap their access expressions in
// captureless lambdas. These helpers therefore MUST have static storage
// duration; function-local lambda variables cannot be referenced from those
// generated [] lambdas and cause MSVC C3493/C2326.
static bool CanTalkToDampe() {
    const bool npcExists =
        !ctx->GetOption(RSK_SHUFFLE_NPC_SOUL) || logic->HasItem(RG_NPC_SOUL);
    const bool canSpeak =
        !ctx->GetOption(RSK_SHUFFLE_SPEAK) || logic->HasItem(RG_SPEAK_HYLIAN);
    return npcExists && canSpeak;
}

static bool CanUseShovel() {
    return !ctx->GetOption(RSK_SHUFFLE_SHOVEL) || logic->HasItem(RG_SHOVEL);
}

void RegionTable_Init_Graveyard() {
    // clang-format off
    areaTable[RR_THE_GRAVEYARD] = Region("The Graveyard", SCENE_GRAVEYARD, {
        //Events
        EVENT_ACCESS(LOGIC_PLANT_GRAVEYARD_BEAN, CanPlantBean(RG_GRAVEYARD_BEAN_SOUL)),
        EVENT_ACCESS(LOGIC_FAIRY_ACCESS,         (logic->AtDay && logic->CanUse(RG_STICKS)) || (logic->IsChild && logic->BeanPlanted(LOGIC_PLANT_GRAVEYARD_BEAN) && logic->CanUse(RG_SONG_OF_STORMS))),
        EVENT_ACCESS(LOGIC_BUG_ACCESS,           logic->HasItem(RG_POWER_BRACELET)),
        EVENT_ACCESS(LOGIC_SOLD_SPOOKY_MASK,     logic->IsChild && logic->AtDay && logic->HasItem(RG_SPOOKY_MASK) && logic->HasItem(RG_CHILD_WALLET) && logic->HasItem(RG_SPEAK_HYLIAN)),
    }, {
        //Locations
        LOCATION(RC_GRAVEYARD_FREESTANDING_POH,        (((logic->IsAdult && logic->BeanPlanted(LOGIC_PLANT_GRAVEYARD_BEAN)) || logic->CanUse(RG_LONGSHOT)) && logic->CanBreakCrates()) || (ctx->GetTrickOption(RT_GY_POH) && logic->CanUse(RG_BOOMERANG))),
        LOCATION(RC_GRAVEYARD_DAMPE_GRAVEDIGGING_TOUR, logic->HasItem(RG_CHILD_WALLET) && logic->IsChild && logic->AtNight && CanTalkToDampe() && CanUseShovel()), //TODO: This needs to change
        LOCATION(RC_GRAVEYARD_GS_WALL,                 logic->IsChild && logic->HookshotOrBoomerang() && logic->AtNight && logic->CanGetNightTimeGS()),
        LOCATION(RC_GRAVEYARD_GS_BEAN_PATCH,           logic->CanSpawnSoilSkull(RG_GRAVEYARD_BEAN_SOUL) && logic->CanAttack()),
        LOCATION(RC_GRAVEYARD_BEAN_SPROUT_FAIRY_1,     logic->IsChild && logic->BeanPlanted(LOGIC_PLANT_GRAVEYARD_BEAN) && logic->CanUse(RG_SONG_OF_STORMS)),
        LOCATION(RC_GRAVEYARD_BEAN_SPROUT_FAIRY_2,     logic->IsChild && logic->BeanPlanted(LOGIC_PLANT_GRAVEYARD_BEAN) && logic->CanUse(RG_SONG_OF_STORMS)),
        LOCATION(RC_GRAVEYARD_BEAN_SPROUT_FAIRY_3,     logic->IsChild && logic->BeanPlanted(LOGIC_PLANT_GRAVEYARD_BEAN) && logic->CanUse(RG_SONG_OF_STORMS)),
        LOCATION(RC_GY_GRASS_1,                        logic->CanCollectGrass()),
        LOCATION(RC_GY_GRASS_2,                        logic->CanCollectGrass()),
        LOCATION(RC_GY_GRASS_3,                        logic->CanCollectGrass()),
        LOCATION(RC_GY_GRASS_4,                        logic->CanCollectGrass()),
        LOCATION(RC_GY_GRASS_5,                        logic->CanCollectGrass()),
        LOCATION(RC_GY_GRASS_6,                        logic->CanCollectGrass()),
        LOCATION(RC_GY_GRASS_7,                        logic->CanCollectGrass()),
        LOCATION(RC_GY_GRASS_8,                        logic->CanCollectGrass()),
        LOCATION(RC_GY_GRASS_9,                        logic->CanCollectGrass()),
        LOCATION(RC_GY_GRASS_10,                       logic->CanCollectGrass()),
        LOCATION(RC_GY_GRASS_11,                       logic->CanCollectGrass()),
        LOCATION(RC_GY_GRASS_12,                       logic->CanCollectGrass()),
        LOCATION(RC_GRAVEYARD_CRATE,                   ((logic->IsAdult && logic->BeanPlanted(LOGIC_PLANT_GRAVEYARD_BEAN)) || logic->CanUse(RG_LONGSHOT)) && logic->CanBreakCrates()),
        LOCATION(RC_GY_ROCK,                           logic->CanBreakRocks()),
        LOCATION(RC_GY_NEAR_HUT_GRAVE_BUTTERFLY_FAIRY, logic->IsChild && logic->AtDay && logic->CanUse(RG_STICKS)),
        LOCATION(RC_GY_ENTRANCE_RECTANGLE_SIGN,        logic->CanRead()),
        LOCATION(RC_GY_ENTRANCE_PLINTH,                logic->CanRead()),
        LOCATION(RC_GY_RIGHT_OF_ROYAL_TOMB_GRAVE,      logic->CanRead()),
        LOCATION(RC_GY_LEFT_OF_ROYAL_TOMB_GRAVE,       logic->CanRead()),
        LOCATION(RC_GY_ROYAL_TOMB_GRAVE,               logic->CanRead() || logic->CanUse(RG_ZELDAS_LULLABY)),
    }, {
        //Exits
        ENTRANCE(RR_GRAVEYARD_SHIELD_GRAVE,       (logic->IsAdult || logic->AtNight) && logic->HasItem(RG_POWER_BRACELET)),
        ENTRANCE(RR_GRAVEYARD_COMPOSERS_GRAVE,    logic->CanUse(RG_ZELDAS_LULLABY)),
        ENTRANCE(RR_GRAVEYARD_HEART_PIECE_GRAVE,  (logic->IsAdult || logic->AtNight) && logic->HasItem(RG_POWER_BRACELET)),
        ENTRANCE(RR_GRAVEYARD_DAMPES_GRAVE,       logic->IsAdult && logic->HasItem(RG_POWER_BRACELET)),
        ENTRANCE(RR_GRAVEYARD_DAMPES_HOUSE,       logic->IsAdult && logic->HasItem(RG_DAMPES_HUT_KEY) /*|| logic->AtDampeTime*/), //TODO: This needs to be handled in ToD rework
        ENTRANCE(RR_KAKARIKO_VILLAGE,             true),
        ENTRANCE(RR_GRAVEYARD_WARP_PAD_REGION,    false),
    });

    areaTable[RR_GRAVEYARD_SHIELD_GRAVE] = Region("Graveyard Shield Grave", SCENE_GRAVE_WITH_FAIRYS_FOUNTAIN, {}, {
        //Locations
        LOCATION(RC_GRAVEYARD_SHIELD_GRAVE_CHEST, logic->HasItem(RG_OPEN_CHEST)),
    }, {
        //Exits
        ENTRANCE(RR_THE_GRAVEYARD,               true),
        ENTRANCE(RR_GRAVEYARD_SHIELD_GRAVE_BACK, AnyAgeTime([]{return logic->CanBreakMudWalls();})),
    });

    areaTable[RR_GRAVEYARD_SHIELD_GRAVE_BACK] = Region("Graveyard Shield Grave Back", SCENE_GRAVE_WITH_FAIRYS_FOUNTAIN, {}, {
        //Locations
        LOCATION(RC_GRAVEYARD_SHIELD_GRAVE_FAIRY_1, true),
        LOCATION(RC_GRAVEYARD_SHIELD_GRAVE_FAIRY_2, true),
        LOCATION(RC_GRAVEYARD_SHIELD_GRAVE_FAIRY_3, true),
        LOCATION(RC_GRAVEYARD_SHIELD_GRAVE_FAIRY_4, true),
        LOCATION(RC_GRAVEYARD_SHIELD_GRAVE_FAIRY_5, true),
        LOCATION(RC_GRAVEYARD_SHIELD_GRAVE_FAIRY_6, true),
        LOCATION(RC_GRAVEYARD_SHIELD_GRAVE_FAIRY_7, true),
        LOCATION(RC_GRAVEYARD_SHIELD_GRAVE_FAIRY_8, true),
    }, {
        //Exits
        ENTRANCE(RR_GRAVEYARD_SHIELD_GRAVE, true),
    });

    areaTable[RR_GRAVEYARD_HEART_PIECE_GRAVE] = Region("Graveyard Heart Piece Grave", SCENE_REDEAD_GRAVE, {}, {
        //Locations
        LOCATION(RC_GRAVEYARD_HEART_PIECE_GRAVE_CHEST, logic->CanUse(RG_SUNS_SONG) && logic->CanOpenLargeChest()),
    }, {
        //Exits
        ENTRANCE(RR_THE_GRAVEYARD, true),
    });

    areaTable[RR_GRAVEYARD_COMPOSERS_GRAVE] = Region("Graveyard Composers Grave", SCENE_ROYAL_FAMILYS_TOMB, {}, {
        //Locations
        LOCATION(RC_GRAVEYARD_ROYAL_FAMILYS_TOMB_CHEST,     logic->HasFireSource() && logic->HasItem(RG_OPEN_CHEST)),
        LOCATION(RC_SONG_FROM_ROYAL_FAMILYS_TOMB,           logic->CanUseProjectile() || logic->CanJumpslash()),
        LOCATION(RC_GRAVEYARD_ROYAL_FAMILYS_TOMB_SUN_FAIRY, logic->CanUse(RG_SUNS_SONG)),
    }, {
        //Exits
        ENTRANCE(RR_THE_GRAVEYARD, true),
    });

    areaTable[RR_GRAVEYARD_DAMPES_GRAVE] = Region("Graveyard Dampes Grave", SCENE_WINDMILL_AND_DAMPES_GRAVE, {
        //Events
        EVENT_ACCESS(LOGIC_NUT_ACCESS, CanTalkToDampe() && logic->CanBreakPots()),
    }, {
        //Locations
        LOCATION(RC_GRAVEYARD_HOOKSHOT_CHEST,              CanTalkToDampe() && logic->CanOpenLargeChest()),
        LOCATION(RC_GRAVEYARD_DAMPE_RACE_FREESTANDING_POH, (logic->IsAdult || ctx->GetTrickOption(RT_GY_CHILD_DAMPE_RACE_POH) || logic->BunnyHood()) && CanTalkToDampe()),
        LOCATION(RC_GY_DAMPES_GRAVE_POT_1,                 CanTalkToDampe() && logic->CanBreakPots()),
        LOCATION(RC_GY_DAMPES_GRAVE_POT_2,                 CanTalkToDampe() && logic->CanBreakPots()),
        LOCATION(RC_GY_DAMPES_GRAVE_POT_3,                 CanTalkToDampe() && logic->CanBreakPots()),
        LOCATION(RC_GY_DAMPES_GRAVE_POT_4,                 CanTalkToDampe() && logic->CanBreakPots()),
        LOCATION(RC_GY_DAMPES_GRAVE_POT_5,                 CanTalkToDampe() && logic->CanBreakPots()),
        LOCATION(RC_GY_DAMPES_GRAVE_POT_6,                 CanTalkToDampe() && logic->CanBreakPots()),
        LOCATION(RC_GRAVEYARD_DAMPE_RACE_RUPEE_1,          CanTalkToDampe()),
        LOCATION(RC_GRAVEYARD_DAMPE_RACE_RUPEE_2,          CanTalkToDampe()),
        LOCATION(RC_GRAVEYARD_DAMPE_RACE_RUPEE_3,          CanTalkToDampe()),
        LOCATION(RC_GRAVEYARD_DAMPE_RACE_RUPEE_4,          CanTalkToDampe()),
        LOCATION(RC_GRAVEYARD_DAMPE_RACE_RUPEE_5,          CanTalkToDampe()),
        LOCATION(RC_GRAVEYARD_DAMPE_RACE_RUPEE_6,          CanTalkToDampe()),
        LOCATION(RC_GRAVEYARD_DAMPE_RACE_RUPEE_7,          CanTalkToDampe()),
        LOCATION(RC_GRAVEYARD_DAMPE_RACE_RUPEE_8,          CanTalkToDampe()),
        LOCATION(RC_GY_WONDER_DAMPE_RACE_1,                CanTalkToDampe()),
        LOCATION(RC_GY_WONDER_DAMPE_RACE_2,                CanTalkToDampe()),
        LOCATION(RC_GY_WONDER_DAMPE_RACE_3,                CanTalkToDampe()),
        LOCATION(RC_GY_WONDER_DAMPE_RACE_4,                CanTalkToDampe()),
        LOCATION(RC_GY_WONDER_DAMPE_RACE_5,                CanTalkToDampe()),
        LOCATION(RC_GY_WONDER_DAMPE_RACE_6,                CanTalkToDampe()),
        LOCATION(RC_GY_WONDER_DAMPE_RACE_7,                CanTalkToDampe()),
        LOCATION(RC_GY_WONDER_DAMPE_RACE_8,                CanTalkToDampe()),
        LOCATION(RC_GY_WONDER_DAMPE_RACE_9,                CanTalkToDampe()),
        LOCATION(RC_GY_WONDER_DAMPE_RACE_10,                CanTalkToDampe()),
        LOCATION(RC_GY_WONDER_DAMPE_RACE_11,                CanTalkToDampe()),
        LOCATION(RC_GY_WONDER_DAMPE_RACE_12,                CanTalkToDampe()),
        LOCATION(RC_GY_WONDER_DAMPE_RACE_13,                CanTalkToDampe()),
        LOCATION(RC_GY_WONDER_DAMPE_RACE_14,                CanTalkToDampe()),
        LOCATION(RC_GY_WONDER_DAMPE_RACE_15,                CanTalkToDampe()),
    }, {
        //Exits
        ENTRANCE(RR_THE_GRAVEYARD,      true),
        ENTRANCE(RR_KAK_WINDMILL_UPPER, CanTalkToDampe() && ((logic->IsAdult && logic->CanUse(RG_SONG_OF_TIME)) || (logic->IsChild && logic->CanGroundJump())), false),
    });

    areaTable[RR_GRAVEYARD_DAMPES_HOUSE] = Region("Graveyard Dampes House", SCENE_GRAVEKEEPERS_HUT, {}, {
        //Locations
        LOCATION(RC_DAMPE_HINT, logic->IsAdult),
    }, {
        //Exits
        ENTRANCE(RR_THE_GRAVEYARD, true),
    });

    areaTable[RR_GRAVEYARD_WARP_PAD_REGION] = Region("Graveyard Warp Pad Region", SCENE_GRAVEYARD, {
        //Events
        EVENT_ACCESS(LOGIC_FAIRY_ACCESS, logic->CallGossipFairyExceptSuns()),
    }, {
        //Locations
        LOCATION(RC_GRAVEYARD_GOSSIP_STONE_FAIRY,     logic->CallGossipFairyExceptSuns()),
        LOCATION(RC_GRAVEYARD_GOSSIP_STONE_FAIRY_BIG, logic->CanUse(RG_SONG_OF_STORMS)),
        LOCATION(RC_GRAVEYARD_GOSSIP_STONE,           true),
    }, {
        //Exits
        ENTRANCE(RR_THE_GRAVEYARD,          true),
        ENTRANCE(RR_SHADOW_TEMPLE_ENTRYWAY, logic->CanUse(RG_DINS_FIRE) || (ctx->GetTrickOption(RT_GY_SHADOW_FIRE_ARROWS) && logic->IsAdult && logic->CanUse(RG_FIRE_ARROWS))),
    });

    // clang-format on
}
