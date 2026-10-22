#include "soh/Enhancements/randomizer/location_access.h"
#include "soh/Enhancements/randomizer/entrance.h"

using namespace Rando;

// The SFM entry Wolfos is a progression lock, not merely an enemy check.
// Generic CanKillEnemy(RE_WOLFOS) includes Bombchus, but Bombchu-only does not
// reliably clear this specific lock-in encounter in-game.  Keep the physical
// gate stricter while still respecting the selected Enemy Soul mode.
static bool CanClearSfmEntryWolfos() {
    const int enemySoulMode = ctx->GetOption(RSK_SHUFFLE_ENEMY_SOUL).Get();
    if (enemySoulMode == 1 && !logic->HasItem(RG_ENEMY_SOUL)) {
        return false;
    }
    if (enemySoulMode == 2 && !logic->HasItem(RG_ENEMY_SOUL_WOLFOS)) {
        return false;
    }

    return logic->CanJumpslash() || logic->CanUse(RG_FAIRY_BOW) || logic->CanUse(RG_FAIRY_SLINGSHOT) ||
           logic->CanUse(RG_DINS_FIRE) ||
           (logic->CanUse(RG_BOMB_BAG) &&
            (logic->CanUse(RG_NUTS) || logic->CanUse(RG_HOOKSHOT) || logic->CanUse(RG_BOOMERANG)));
}

static bool CanReceiveSariaSong() {
    if (!logic->IsChild || !logic->Get(LOGIC_MET_ZELDA)) {
        return false;
    }
    if (ctx->GetOption(RSK_SHUFFLE_NPC_SOUL) && !logic->HasItem(RG_NPC_SOUL)) {
        return false;
    }

    const int speakMode = ctx->GetOption(RSK_SHUFFLE_SPEAK).Get();
    if (speakMode == 1 && !logic->HasItem(RG_SPEAK_HYLIAN)) {
        return false;
    }
    if (speakMode == 2 && !logic->HasItem(RG_SPEAK_KOKIRI)) {
        return false;
    }
    return true;
}

void RegionTable_Init_SacredForestMeadow() {
    // clang-format off
    areaTable[RR_SFM_ENTRYWAY] = Region("SFM Entryway", SCENE_SACRED_FOREST_MEADOW, {
        //Events
        EVENT_ACCESS(LOGIC_OPEN_SFM_GATE, logic->IsChild && CanClearSfmEntryWolfos()),
    }, {
        //Locations
        LOCATION(RC_SFM_WONDER_ENTRANCE,    true),
    }, {
        //Exits
        ENTRANCE(RR_LW_BEYOND_MIDO,       true),
        ENTRANCE(RR_SACRED_FOREST_MEADOW, logic->IsAdult || logic->Get(LOGIC_OPEN_SFM_GATE)),
        ENTRANCE(RR_SFM_WOLFOS_GROTTO,    logic->CanOpenBombGrotto()),
    });

    areaTable[RR_SFM_ABOVE_MAZE] = Region("SFM Above Maze", SCENE_SACRED_FOREST_MEADOW, {
        //Events
        EVENT_ACCESS(LOGIC_FAIRY_ACCESS, logic->CallGossipFairyExceptSuns()),
    }, {
        //Locations
        LOCATION(RC_SFM_GS,                                logic->IsAdult && logic->HookshotOrBoomerang() && logic->CanGetNightTimeGS()),
        LOCATION(RC_SFM_MAZE_LOWER_GOSSIP_STONE_FAIRY,     logic->CallGossipFairyExceptSuns()),
        LOCATION(RC_SFM_MAZE_LOWER_GOSSIP_STONE_FAIRY_BIG, logic->CanUse(RG_SONG_OF_STORMS)),
        LOCATION(RC_SFM_MAZE_UPPER_GOSSIP_STONE_FAIRY,     logic->CallGossipFairyExceptSuns()),
        LOCATION(RC_SFM_MAZE_UPPER_GOSSIP_STONE_FAIRY_BIG, logic->CanUse(RG_SONG_OF_STORMS)),
        LOCATION(RC_SFM_MAZE_LOWER_GOSSIP_STONE,           true),
        LOCATION(RC_SFM_MAZE_UPPER_GOSSIP_STONE,           true),
    }, {
        //Exits
        ENTRANCE(RR_SFM_ENTRYWAY,             true),
        ENTRANCE(RR_SFM_OUTSIDE_FAIRY_GROTTO, true),
        ENTRANCE(RR_SACRED_FOREST_MEADOW,     true),
    });

    areaTable[RR_SACRED_FOREST_MEADOW] = Region("Sacred Forest Meadow", SCENE_SACRED_FOREST_MEADOW, {
        //Events
        EVENT_ACCESS(LOGIC_FAIRY_ACCESS, logic->CallGossipFairyExceptSuns()),
    }, {
        //Locations
        LOCATION(RC_SONG_FROM_SARIA,                  CanReceiveSariaSong()),
        LOCATION(RC_SHEIK_IN_FOREST,                  (logic->IsAdult) && (!ctx->GetOption(RSK_SHUFFLE_NPC_SOUL) || logic->HasItem(RG_NPC_SOUL)) && (!ctx->GetOption(RSK_SHUFFLE_SPEAK) || logic->HasItem(RG_SPEAK_HYLIAN))),
        LOCATION(RC_SFM_SARIA_GOSSIP_STONE_FAIRY,     logic->CallGossipFairyExceptSuns()),
        LOCATION(RC_SFM_SARIA_GOSSIP_STONE_FAIRY_BIG, logic->CanUse(RG_SONG_OF_STORMS)),
        LOCATION(RC_SFM_SARIA_GOSSIP_STONE,           true),
        LOCATION(RC_SFM_WONDER_MAZE_1,                true),
        LOCATION(RC_SFM_WONDER_MAZE_2,                true),
        LOCATION(RC_SFM_WONDER_MAZE_3,                true),
        LOCATION(RC_SFM_WONDER_MAZE_4,                true),
        LOCATION(RC_SFM_WONDER_MAZE_5,                true),
    }, {
        //Exits
        ENTRANCE(RR_FOREST_TEMPLE_ENTRYWAY, logic->CanUse(RG_HOOKSHOT)),
        ENTRANCE(RR_SFM_ENTRYWAY,           logic->IsAdult || logic->Get(LOGIC_OPEN_SFM_GATE)),
        // adult can jump up, but it's a trick. being hit directly by club moblin while wearing hover boots also works, but relies on coming from LW
        ENTRANCE(RR_SFM_ABOVE_MAZE,         logic->CanClimbLadder() || (logic->IsAdult && (logic->CanGroundJump() || (ctx->GetTrickOption(RT_UNINTUITIVE_JUMPS) && logic->BunnyHood())))),
        ENTRANCE(RR_SFM_STORMS_GROTTO,      logic->CanOpenStormsGrotto()),
    });

    areaTable[RR_SFM_OUTSIDE_FAIRY_GROTTO] = Region("SFM Outside Fairy Grotto", SCENE_SACRED_FOREST_MEADOW, {}, {}, {
        //Exits
        ENTRANCE(RR_SFM_FAIRY_GROTTO, true),
        ENTRANCE(RR_SFM_ABOVE_MAZE,   logic->CanClimbLadder()),
    });

    areaTable[RR_SFM_FAIRY_GROTTO] = Region("SFM Fairy Grotto", SCENE_GROTTOS, {
        //Events
        EVENT_ACCESS(LOGIC_FAIRY_ACCESS, true),
    }, {
        //Locations
        LOCATION(RC_SFM_FAIRY_GROTTO_FAIRY_1, true),
        LOCATION(RC_SFM_FAIRY_GROTTO_FAIRY_2, true),
        LOCATION(RC_SFM_FAIRY_GROTTO_FAIRY_3, true),
        LOCATION(RC_SFM_FAIRY_GROTTO_FAIRY_4, true),
        LOCATION(RC_SFM_FAIRY_GROTTO_FAIRY_5, true),
        LOCATION(RC_SFM_FAIRY_GROTTO_FAIRY_6, true),
        LOCATION(RC_SFM_FAIRY_GROTTO_FAIRY_7, true),
        LOCATION(RC_SFM_FAIRY_GROTTO_FAIRY_8, true),
    }, {
        //Exits
        ENTRANCE(RR_SFM_OUTSIDE_FAIRY_GROTTO, true),
    });

    areaTable[RR_SFM_WOLFOS_GROTTO] = Region("SFM Wolfos Grotto", SCENE_GROTTOS, {}, {
        //Locations
        LOCATION(RC_SFM_WOLFOS_GROTTO_CHEST, logic->CanKillEnemy(RE_WOLFOS, ED_CLOSE, true, 2) && logic->HasItem(RG_OPEN_CHEST)),
    }, {
        //Exits
        ENTRANCE(RR_SFM_ENTRYWAY, true),
    });

    areaTable[RR_SFM_STORMS_GROTTO] = Region("SFM Storms Grotto", SCENE_GROTTOS, {}, {
        //Locations
        LOCATION(RC_SFM_DEKU_SCRUB_GROTTO_REAR,    logic->CanStunDeku() && logic->HasItem(RG_SPEAK_DEKU) && GetCheckPrice() <= GetWalletCapacity()),
        LOCATION(RC_SFM_DEKU_SCRUB_GROTTO_FRONT,   logic->CanStunDeku() && logic->HasItem(RG_SPEAK_DEKU) && GetCheckPrice() <= GetWalletCapacity()),
        LOCATION(RC_SFM_DEKU_SCRUB_GROTTO_BEEHIVE, logic->CanBreakUpperBeehives()),
    }, {
        //Exits
        ENTRANCE(RR_SACRED_FOREST_MEADOW, true),
    });

    // clang-format on
}
