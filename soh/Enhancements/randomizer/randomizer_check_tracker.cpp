#include <array>
#include <cstdio>
#include <map>
#include <string>
#include <sstream>
#include <vector>
#include <set>

#include <spdlog/common.h>
#include <libultraship/controller/controldeck/ControlDeck.h>

#include "randomizer_check_tracker.h"
#include "CheckFinderState.h"
#include "soh/Network/Archipelago/ArchipelagoClient.h"
#include "soh/Network/Archipelago/TrackerRegions.h"

extern "C" bool Archipelago_ShouldHandleCheck(int32_t randomizerCheck);
extern "C" bool Archipelago_IsCheckMappedActive(int32_t randomizerCheck);
extern "C" bool Archipelago_IsCurrentSaveActive(void);
extern "C" bool Archipelago_PrepareCheckFinderMappings(void);
extern "C" bool Archipelago_IsLocationActive(int64_t locationId);
extern "C" bool Archipelago_IsLocationReported(int64_t locationId);
extern "C" bool MegaSoul_HasEnemyDefeatSoul(int16_t actorId);

#include "randomizer_entrance_tracker.h"
#include "randomizer_item_tracker.h"
#include "randomizer_tracker_windows.h"
#include "randomizerTypes.h"
#include "soh/Enhancements/randomizer/randomizerEnums.h"
#include "soh/Enhancements/randomizer/static_data.h"
#include "soh/OTRGlobals.h"
#include "soh/SaveManager.h"
#include "soh/SohGui/UIWidgets.hpp"
#include "soh/SohGui/SohGui.hpp"
#include "dungeon.h"
#include "entrance.h"
#include "fishsanity.h"
#include "location_access.h"
#include "3drando/fill.hpp"
#include "soh/Enhancements/debugger/performanceTimer.h"
#include "soh/Enhancements/randomizer/randomizer.h"
#include "soh/ObjectExtension/ObjectExtension.h"
#include "location.h"
#include "item_location.h"
#include "randomizer_check_objects.h"
#include "soh/Enhancements/game-interactor/GameInteractor.h"

extern "C" {
#include "overlays/actors/ovl_En_GirlA/z_en_girla.h"
#include "z64item.h"
#include "variables.h"
#include "macros.h"
extern PlayState* gPlayState;
}

extern "C" GetItemEntry ItemTable_RetrieveEntry(s16 modIndex, s16 getItemID);

extern std::vector<ItemTrackerItem> dungeonRewardStones;
extern std::vector<ItemTrackerItem> dungeonRewardMedallions;
extern std::vector<ItemTrackerItem> songItems;
extern std::vector<ItemTrackerItem> equipmentItems;

using json = nlohmann::json;
using namespace UIWidgets;

namespace CheckTracker {

struct NpcSpeechFinderEntry {
    int32_t rc;
    int64_t locationId;
    RandomizerGet languageItem;
};

static const NpcSpeechFinderEntry kNpcSpeechFinderEntries[] = {
#include "soh/Network/Archipelago/ArchipelagoSpeechFinderMap.inc"
};

enum EnemyFinderCombat : uint8_t {
    EFC_MELEE,
    EFC_RANGED,
    EFC_REFLECT_NUTS,
    EFC_RANGED_OR_MELEE,
    EFC_EXPLOSIVE,
    EFC_EXPLOSIVE_OR_MELEE,
    EFC_HOOKSHOT_AND_MELEE,
    EFC_HOOKSHOT_OR_MELEE,
    EFC_BOOMERANG,
    EFC_FIRE_OR_MELEE,
    EFC_CONTACT, EFC_FIRE, EFC_BOW, EFC_BOOMERANG_AND_MELEE,
};

enum EnemyFinderGate : uint8_t { EFG_NONE, EFG_AMY, EFG_ANUBIS, EFG_COFFIN, EFG_COMPOSER, EFG_FOREST_BLOCK_TOP, EFG_GRAVE, EFG_MEG, EFG_NIGHT, EFG_PEAHAT_LARVA, EFG_SFM_MOBLIN, EFG_SWIM };

struct EnemyDefeatFinderEntry {
    int64_t locationId;
    RandomizerCheckArea area;
    RandomizerRegion region;
    int16_t scene;
    int8_t room;
    int8_t grottoId;
    int16_t actorId;
    EnemyFinderCombat combat;
    const char* name;
    uint8_t spawnMask;
    EnemyFinderGate gate;
    bool exactRegion;
};

// Generated from the finite per-placement AP enemy catalog. Infer the count so
// adding a catalogue entry cannot leave a stale hand-maintained bound.
static const EnemyDefeatFinderEntry kEnemyDefeatFinderEntries[] = {
#include "soh/Network/Archipelago/ArchipelagoEnemyFinderMap.inc"
};
static constexpr size_t kEnemyDefeatFinderEntryCount = sizeof(kEnemyDefeatFinderEntries) / sizeof(kEnemyDefeatFinderEntries[0]);

// NPC Speech checks are separate AP locations.  Never overload the native
// RandomizerCheck row: the native reward check and its first-talk check can both
// be active in the same AP slot.
static std::set<int64_t> availableNpcSpeechLocations;
static std::set<int64_t> availableEnemyDefeatLocations;

static RandomizerCheckArea GetNpcSpeechArea(const NpcSpeechFinderEntry& entry) {
    auto* location = Rando::StaticData::GetLocation(static_cast<RandomizerCheck>(entry.rc));
    return location != nullptr ? location->GetArea() : RCAREA_INVALID;
}

static bool IsNpcSpeechVisible(const NpcSpeechFinderEntry& entry) {
    if (!Archipelago_IsCurrentSaveActive() || !Archipelago_IsLocationActive(entry.locationId)) {
        return false;
    }
    const auto area = GetNpcSpeechArea(entry);
    return area >= RCAREA_KOKIRI_FOREST && area < RCAREA_INVALID;
}

static bool IsEnemyDefeatVisible(const EnemyDefeatFinderEntry& entry) {
    return Archipelago_IsCurrentSaveActive() && Archipelago_IsLocationActive(entry.locationId) &&
           entry.area >= RCAREA_KOKIRI_FOREST && entry.area < RCAREA_INVALID;
}

static bool EnemyFinderMelee(Rando::Logic* enemyLogic) {
    return enemyLogic->CanUse(RG_KOKIRI_SWORD) || enemyLogic->CanUse(RG_MASTER_SWORD) ||
           enemyLogic->CanUse(RG_BIGGORON_SWORD) || enemyLogic->CanUse(RG_GIANTS_KNIFE) ||
           enemyLogic->CanUse(RG_STICKS) || enemyLogic->CanUse(RG_MEGATON_HAMMER);
}

static bool EnemyFinderRanged(Rando::Logic* enemyLogic) {
    return enemyLogic->CanUse(RG_FAIRY_SLINGSHOT) || enemyLogic->CanUse(RG_FAIRY_BOW) ||
           enemyLogic->CanUse(RG_HOOKSHOT) || enemyLogic->CanUse(RG_LONGSHOT) ||
           enemyLogic->CanUse(RG_BOOMERANG);
}

static bool EnemyFinderCombatReachable(Rando::Logic* enemyLogic, EnemyFinderCombat combat) {
    const bool melee = EnemyFinderMelee(enemyLogic);
    const bool ranged = EnemyFinderRanged(enemyLogic);
    const bool explosives = enemyLogic->HasExplosives();
    switch (combat) {
        case EFC_CONTACT: return true; // A flying pot can be baited into the floor.
        case EFC_FIRE: return enemyLogic->CanUse(RG_DINS_FIRE) || enemyLogic->CanUse(RG_FIRE_ARROWS);
        case EFC_BOW: return enemyLogic->CanUse(RG_FAIRY_BOW);
        case EFC_BOOMERANG_AND_MELEE: return enemyLogic->CanUse(RG_BOOMERANG) && melee;
        case EFC_MELEE: return melee;
        case EFC_RANGED: return ranged;
        case EFC_REFLECT_NUTS: return enemyLogic->CanReflectNuts();
        case EFC_RANGED_OR_MELEE: return ranged || melee;
        case EFC_EXPLOSIVE: return explosives;
        case EFC_EXPLOSIVE_OR_MELEE: return explosives || melee;
        case EFC_HOOKSHOT_AND_MELEE:
            return (enemyLogic->CanUse(RG_HOOKSHOT) || enemyLogic->CanUse(RG_LONGSHOT)) && melee;
        case EFC_HOOKSHOT_OR_MELEE:
            return enemyLogic->CanUse(RG_HOOKSHOT) || enemyLogic->CanUse(RG_LONGSHOT) || melee;
        case EFC_BOOMERANG: return enemyLogic->CanUse(RG_BOOMERANG);
        case EFC_FIRE_OR_MELEE:
            return enemyLogic->CanUse(RG_DINS_FIRE) || enemyLogic->CanUse(RG_FIRE_ARROWS) || melee;
        default: return false;
    }
}

static bool EnemyFinderRoomCondition(Rando::Logic* logic, const EnemyDefeatFinderEntry& entry) {
    auto ctx = Rando::Context::GetInstance();
    switch (entry.locationId) {
#include "soh/Network/Archipelago/ArchipelagoEnemyRoomConditions.inc"
        default: return true; // No additional local obstacle beyond the mapped parent.
    }
}

static bool EnemyFinderEncounterGate(Rando::Logic* enemyLogic, const EnemyDefeatFinderEntry& entry) {
    switch (entry.gate) {
        case EFG_MEG: return enemyLogic->Get(LOGIC_FOREST_JOELLE) &&
            enemyLogic->Get(LOGIC_FOREST_BETH) && enemyLogic->Get(LOGIC_FOREST_AMY);
        case EFG_AMY: return enemyLogic->HasItem(RG_POWER_BRACELET);
        case EFG_FOREST_BLOCK_TOP: return enemyLogic->IsAdult && enemyLogic->HasItem(RG_CLIMB) &&
            enemyLogic->HasItem(RG_GORONS_BRACELET);
        case EFG_COFFIN: return enemyLogic->HasFireSourceWithTorch() || enemyLogic->CanUse(RG_FAIRY_BOW);
        case EFG_COMPOSER: return enemyLogic->HasItem(RG_SPEAK_HYLIAN);
        case EFG_GRAVE: return enemyLogic->HasItem(RG_POWER_BRACELET);
        case EFG_PEAHAT_LARVA: return EnemyFinderMelee(enemyLogic);
        case EFG_SWIM: return enemyLogic->HasItem(RG_BRONZE_SCALE);
        case EFG_NIGHT: return enemyLogic->AtNight;
        default: return true; // Other gates inherit their precise parent region/combat rule.
    }
}

static bool IsEnemyDefeatReachable(const EnemyDefeatFinderEntry& entry) {
    auto* region = RegionTable(entry.region);
    auto enemyLogic = Rando::Context::GetInstance()->GetLogic();
    if (region == nullptr || enemyLogic == nullptr || !region->HasAccess()) return false;
    if (!MegaSoul_HasEnemyDefeatSoul(entry.actorId)) return false;
    if (entry.actorId == ACTOR_EN_TUBO_TRAP && !enemyLogic->HasItem(RG_POT_SOUL)) return false;
    if (entry.grottoId >= 0 && Rando::Context::GetInstance()->GetOption(RSK_SHUFFLE_SHOVEL) &&
        !enemyLogic->HasItem(RG_SHOVEL)) return false;
    SohExtreme::ScopedCheckFinderLogic<Rando::Logic, SaveContext> liveEnemyLogic(*enemyLogic, gSaveContext);
    enemyLogic->CurrentRegionKey = entry.region;
    enemyLogic->CurrentCheckKey = RC_UNKNOWN_CHECK;
    const bool access[] = {region->childDay, region->childNight, region->adultDay, region->adultNight};
    bool reachable = false;
    for (uint8_t i = 0; i < 4 && !reachable; ++i) {
        if (!(entry.spawnMask & (1u << i)) || !access[i]) continue;
        enemyLogic->IsAdult = i >= 2;
        enemyLogic->IsChild = i < 2;
        enemyLogic->AtDay = (i & 1) == 0;
        enemyLogic->AtNight = !enemyLogic->AtDay;
        if (!EnemyFinderRoomCondition(enemyLogic.get(), entry)) continue;
        if (entry.scene == 0x0C && !enemyLogic->HasItem(RG_GERUDO_MEMBERSHIP_CARD)) continue;
        reachable = EnemyFinderEncounterGate(enemyLogic.get(), entry) &&
            EnemyFinderCombatReachable(enemyLogic.get(), entry.combat);
    }
    return reachable;
}

static int64_t GetPendingNpcSpeechLocation(RandomizerCheck rc) {
    if (!Archipelago_IsCurrentSaveActive()) {
        return -1;
    }
    for (const auto& entry : kNpcSpeechFinderEntries) {
        if (entry.rc == static_cast<int32_t>(rc) && Archipelago_IsLocationActive(entry.locationId) &&
            !Archipelago_IsLocationReported(entry.locationId)) {
            return entry.locationId;
        }
    }
    return -1;
}

static bool HasNpcSpeechInteractionItems(const NpcSpeechFinderEntry& entry) {
    auto ctx = Rando::Context::GetInstance();
    auto speechLogic = ctx->GetLogic();
    if (ctx->GetOption(RSK_SHUFFLE_NPC_SOUL) && !speechLogic->HasItem(RG_NPC_SOUL)) {
        return false;
    }
    if (ctx->GetOption(RSK_SHUFFLE_SPEAK)) {
        if (entry.languageItem != RG_NONE) {
            if (!speechLogic->HasItem(entry.languageItem)) {
                return false;
            }
        } else if (!(speechLogic->HasItem(RG_SPEAK_DEKU) || speechLogic->HasItem(RG_SPEAK_GERUDO) ||
                     speechLogic->HasItem(RG_SPEAK_GORON) || speechLogic->HasItem(RG_SPEAK_HYLIAN) ||
                     speechLogic->HasItem(RG_SPEAK_KOKIRI) || speechLogic->HasItem(RG_SPEAK_ZORA))) {
            return false;
        }
    }
    return true;
}

static WidgetInfo backgroundColorWidget;
static WidgetInfo windowTypeWidget;
static WidgetInfo dungeonSpoilerWidget;
static WidgetInfo hideUnshuffledShopWidget;
static WidgetInfo showGSWidget;
static WidgetInfo showLogicWidget;
static WidgetInfo checkAvailabilityWidget;

// settings
bool showShops;
bool showOverworldTokens;
bool showDungeonTokens;
bool showBeans;
bool showScrubs;
bool showMajorScrubs;
bool showMerchants;
bool showSongs;
bool showBeehives;
bool showCows;
bool showOverworldFreestanding;
bool showDungeonFreestanding;
bool showSilver;
bool showAdultTrade;
bool showKokiriSword;
bool showMasterSword;
bool showHyruleLoach;
bool showWeirdEgg;
bool showZeldasLetter;
bool showGerudoCard;
bool showOverworldPots;
bool showDungeonPots;
bool showOverworldGrass;
bool showDungeonGrass;
bool showOverworldCrates;
bool showDungeonCrates;
bool showRocks;
bool showOverworldBoulders;
bool showDungeonBoulders;
bool showTrees;
bool showBushes;
bool showOverworldSigns;
bool showDungeonSigns;
bool showOverworldWonderItems;
bool showDungeonWonderItems;
bool showBeggar;
bool showIcicles;
bool showRedIce;
bool showFrogSongRupees;
bool showFountainFairies;
bool showStoneFairies;
bool showBeanFairies;
bool showSongFairies;
bool showButterflyFairies;
bool showStartingMapsCompasses;
bool showKeysanity;
bool showGerudoFortressKeys;
bool showBossKeysanity;
bool showGanonBossKey;
bool showOcarinas;
bool show100SkullReward;
bool showLinksPocket;
bool showChestMinigame;
bool fortressFast;
bool fortressNormal;

u8 fishsanityMode;
u8 fishsanityPondCount;
bool fishsanityAgeSplit;

// persistent during gameplay
bool initialized;
bool doAreaScroll;
bool previousShowHidden = false;
bool hideShopUnshuffledChecks = false;
bool alwaysShowGS = false;

static bool presetLoaded = false;
static ImVec2 presetPos;
static ImVec2 presetSize;

std::map<uint32_t, RandomizerCheck> startingShopItem = {
    { SCENE_KOKIRI_SHOP, RC_KF_SHOP_ITEM_1 },
    { SCENE_BAZAAR, RC_MARKET_BAZAAR_ITEM_1 },
    { SCENE_POTION_SHOP_MARKET, RC_MARKET_POTION_SHOP_ITEM_1 },
    { SCENE_BOMBCHU_SHOP, RC_MARKET_BOMBCHU_SHOP_ITEM_1 },
    { SCENE_POTION_SHOP_KAKARIKO, RC_KAK_POTION_SHOP_ITEM_1 },
    { SCENE_ZORA_SHOP, RC_ZD_SHOP_ITEM_1 },
    { SCENE_GORON_SHOP, RC_GC_SHOP_ITEM_1 },
};

std::map<SceneID, RandomizerCheckArea> DungeonRCAreasBySceneID = {
    { SCENE_DEKU_TREE, RCAREA_DEKU_TREE },
    { SCENE_DODONGOS_CAVERN, RCAREA_DODONGOS_CAVERN },
    { SCENE_JABU_JABU, RCAREA_JABU_JABUS_BELLY },
    { SCENE_FOREST_TEMPLE, RCAREA_FOREST_TEMPLE },
    { SCENE_FIRE_TEMPLE, RCAREA_FIRE_TEMPLE },
    { SCENE_WATER_TEMPLE, RCAREA_WATER_TEMPLE },
    { SCENE_SHADOW_TEMPLE, RCAREA_SHADOW_TEMPLE },
    { SCENE_SPIRIT_TEMPLE, RCAREA_SPIRIT_TEMPLE },
    { SCENE_BOTTOM_OF_THE_WELL, RCAREA_BOTTOM_OF_THE_WELL },
    { SCENE_ICE_CAVERN, RCAREA_ICE_CAVERN },
    { SCENE_GERUDO_TRAINING_GROUND, RCAREA_GERUDO_TRAINING_GROUND },
    { SCENE_INSIDE_GANONS_CASTLE, RCAREA_GANONS_CASTLE },
};

// Dungeon entrances with obvious visual differences between MQ and vanilla qualifying as spoiling on sight
std::vector<uint32_t> spoilingEntrances = {
    ENTR_DEKU_TREE_ENTRANCE,
    ENTR_DODONGOS_CAVERN_BOSS_DOOR,
    ENTR_JABU_JABU_ENTRANCE,
    ENTR_JABU_JABU_BOSS_DOOR,
    ENTR_FOREST_TEMPLE_ENTRANCE,
    ENTR_FIRE_TEMPLE_ENTRANCE,
    ENTR_FIRE_TEMPLE_BOSS_DOOR,
    ENTR_WATER_TEMPLE_BOSS_DOOR,
    ENTR_SPIRIT_TEMPLE_ENTRANCE,
    ENTR_SHADOW_TEMPLE_BOSS_DOOR,
    ENTR_ICE_CAVERN_ENTRANCE,
    ENTR_GERUDO_TRAINING_GROUND_ENTRANCE,
    ENTR_INSIDE_GANONS_CASTLE_ENTRANCE,
};

std::map<RandomizerCheckArea, std::vector<RandomizerCheck>> checksByArea;
bool areasFullyChecked[RCAREA_INVALID];
u32 areasSpoiled = 0;
bool showVOrMQ;
s16 areaChecksGotten[RCAREA_INVALID]; //|     "Kokiri Forest (4/9)"
s16 areaChecksAvailable[RCAREA_INVALID];
s16 areaCheckTotals[RCAREA_INVALID];
uint16_t totalChecks = 0;
uint16_t totalChecksAvailable = 0;
uint16_t totalChecksGotten = 0;
bool optCollapseAll; // A bool that will collapse all checks once
bool optExpandAll;   // A bool that will expand all checks once
RandomizerCheck lastLocationChecked = RC_UNKNOWN_CHECK;
RandomizerCheckArea previousArea = RCAREA_INVALID;
RandomizerCheckArea currentArea = RCAREA_INVALID;
OSContPad* trackerButtonsPressed;
std::unordered_map<RandomizerCheck, std::string> checkNameOverrides;

bool ShouldShowCheck(RandomizerCheck rc);
bool UpdateFilters();
bool CompareChecks(RandomizerCheck, RandomizerCheck);
bool CheckByArea(RandomizerCheckArea);
void DrawLocation(RandomizerCheck);
void DrawNpcSpeechLocation(const NpcSpeechFinderEntry& entry);
void DrawEnemyDefeatLocation(const EnemyDefeatFinderEntry& entry);
void LoadSettings();
void RainbowTick();
void UpdateAreas(RandomizerCheckArea area);
void UpdateInventoryChecks();
void UpdateOrdering(RandomizerCheckArea);
int sectionId;

bool hideUnchecked = false;
bool hideScummed = false;
bool hideSeen = false;
bool hideSkipped = false;
bool hideSaved = false;
bool hideCollected = false;
bool showHidden = true;
bool mystery = false;
bool showLogicTooltip = false;
bool enableAvailableChecks = false;
bool onlyShowAvailable = false;

SceneID DungeonSceneLookupByArea(RandomizerCheckArea area) {
    switch (area) {
        case RCAREA_DEKU_TREE:
            return SCENE_DEKU_TREE;
        case RCAREA_DODONGOS_CAVERN:
            return SCENE_DODONGOS_CAVERN;
        case RCAREA_JABU_JABUS_BELLY:
            return SCENE_JABU_JABU;
        case RCAREA_FOREST_TEMPLE:
            return SCENE_FOREST_TEMPLE;
        case RCAREA_FIRE_TEMPLE:
            return SCENE_FIRE_TEMPLE;
        case RCAREA_WATER_TEMPLE:
            return SCENE_WATER_TEMPLE;
        case RCAREA_SPIRIT_TEMPLE:
            return SCENE_SPIRIT_TEMPLE;
        case RCAREA_SHADOW_TEMPLE:
            return SCENE_SHADOW_TEMPLE;
        case RCAREA_BOTTOM_OF_THE_WELL:
            return SCENE_BOTTOM_OF_THE_WELL;
        case RCAREA_ICE_CAVERN:
            return SCENE_ICE_CAVERN;
        case RCAREA_GERUDO_TRAINING_GROUND:
            return SCENE_GERUDO_TRAINING_GROUND;
        case RCAREA_GANONS_CASTLE:
            return SCENE_INSIDE_GANONS_CASTLE;
        default:
            return SCENE_ID_MAX;
    }
}

const Color_RGBA8 Color_Main_Default = { 255, 255, 255, 255 };                  // White
const Color_RGBA8 Color_Area_Incomplete_Extra_Default = { 255, 255, 255, 255 }; // White
const Color_RGBA8 Color_Area_Complete_Extra_Default = { 255, 255, 255, 255 };   // White
const Color_RGBA8 Color_Unchecked_Extra_Default = { 255, 255, 255, 255 };       // White
const Color_RGBA8 Color_Skipped_Main_Default = { 160, 160, 160, 255 };          // Grey
const Color_RGBA8 Color_Skipped_Extra_Default = { 160, 160, 160, 255 };         // Grey
const Color_RGBA8 Color_Seen_Extra_Default = { 255, 255, 255, 255 };            // TODO
const Color_RGBA8 Color_Hinted_Extra_Default = { 255, 255, 255, 255 };          // TODO
const Color_RGBA8 Color_Collected_Extra_Default = { 242, 101, 34, 255 };        // Orange
const Color_RGBA8 Color_Scummed_Extra_Default = { 0, 174, 239, 255 };           // Blue
const Color_RGBA8 Color_Saved_Extra_Default = { 0, 185, 0, 255 };               // Green

Color_RGBA8 Color_Background = { 0, 0, 0, 255 };

Color_RGBA8 Color_Area_Incomplete_Main = { 255, 255, 255, 255 };  // White
Color_RGBA8 Color_Area_Incomplete_Extra = { 255, 255, 255, 255 }; // White
Color_RGBA8 Color_Area_Complete_Main = { 255, 255, 255, 255 };    // White
Color_RGBA8 Color_Area_Complete_Extra = { 255, 255, 255, 255 };   // White
Color_RGBA8 Color_Unchecked_Main = { 255, 255, 255, 255 };        // White
Color_RGBA8 Color_Unchecked_Extra = { 255, 255, 255, 255 };       // Useless
Color_RGBA8 Color_Skipped_Main = { 160, 160, 160, 255 };          // Grey
Color_RGBA8 Color_Skipped_Extra = { 160, 160, 160, 255 };         // Grey
Color_RGBA8 Color_Seen_Main = { 255, 255, 255, 255 };             // TODO
Color_RGBA8 Color_Seen_Extra = { 160, 160, 160, 255 };            // TODO
Color_RGBA8 Color_Hinted_Main = { 255, 255, 255, 255 };           // TODO
Color_RGBA8 Color_Hinted_Extra = { 255, 255, 255, 255 };          // TODO
Color_RGBA8 Color_Collected_Main = { 255, 255, 255, 255 };        // White
Color_RGBA8 Color_Collected_Extra = { 242, 101, 34, 255 };        // Orange
Color_RGBA8 Color_Scummed_Main = { 255, 255, 255, 255 };          // White
Color_RGBA8 Color_Scummed_Extra = { 0, 174, 239, 255 };           // Blue
Color_RGBA8 Color_Saved_Main = { 255, 255, 255, 255 };            // White
Color_RGBA8 Color_Saved_Extra = { 0, 185, 0, 255 };               // Green

static ImGuiTextFilter checkSearch;
static bool recalculateAvailable = false;
// True only while CheckTrackerLoadGame() is rebuilding derived UI state.
// During this phase SetAreaSpoiled() must not queue save jobs or refresh UI;
// doing that on every area was an AP Start-time save storm.
static bool trackerLoadInProgress = false;
static RandomizerRegion availableChecksStartingRegion = RR_ROOT;
static RandoAgeTime availableChecksStartingAgeTime = RAT_NONE;
static int16_t previousEntrance = 0;

// Abilities, souls, keys, and scene puzzle flags can change without OnItemReceive
// (AP application, save restoration, consumption, or the save editor). Observe
// their actual values instead of watching only Bombchu/bean ammo and age/time.
static SohExtreme::CheckFinderStateSnapshot lastFinderState;

static void ResetLiveFinderStateSnapshot() {
    lastFinderState.Reset();
}

std::array<bool, RCAREA_INVALID> filterAreasHidden = { 0 };
std::array<bool, RC_MAX> filterChecksHidden = { 0 };

void TrySetAreas() {
    if (checksByArea.empty()) {
        for (int i = RCAREA_KOKIRI_FOREST; i < RCAREA_INVALID; i++) {
            checksByArea.emplace(static_cast<RandomizerCheckArea>(i), std::vector<RandomizerCheck>());
        }
    }
}

void CalculateTotals() {
    totalChecks = 0;
    totalChecksAvailable = 0;
    totalChecksGotten = 0;

    for (uint8_t i = 0; i < RCAREA_INVALID; i++) {
        totalChecks += areaCheckTotals[i];
        totalChecksAvailable += areaChecksAvailable[i];
        totalChecksGotten += areaChecksGotten[i];
    }
}

uint16_t GetTotalChecks() {
    return totalChecks;
}

uint16_t GetTotalChecksGotten() {
    return totalChecksGotten;
}

bool IsCheckHidden(RandomizerCheck rc) {
    Rando::ItemLocation* itemLocation = OTRGlobals::Instance->gRandoContext->GetItemLocation(rc);
    RandomizerCheckStatus status = itemLocation->GetCheckStatus();
    bool available = itemLocation->IsAvailable();
    bool skipped = itemLocation->GetIsSkipped();
    bool obtained = itemLocation->HasObtained();
    bool seen = status == RCSHOW_SEEN_OR_HINTED || status == RCSHOW_IDENTIFIED;
    bool scummed = status == RCSHOW_SCUMMED;
    bool unchecked = status == RCSHOW_UNCHECKED;

    return !showHidden &&
           ((skipped && hideSkipped) || (seen && hideSeen) || (scummed && hideScummed) || (unchecked && hideUnchecked));
}

void RecalculateAreaTotals(RandomizerCheckArea rcArea) {
    areaChecksGotten[rcArea] = 0;
    areaChecksAvailable[rcArea] = 0;
    areaCheckTotals[rcArea] = 0;
    for (auto rc : checksByArea.at(rcArea)) {
        if (!IsVisibleInCheckTracker(rc)) {
            continue;
        }
        areaCheckTotals[rcArea]++;

        Rando::ItemLocation* itemLoc = OTRGlobals::Instance->gRandoContext->GetItemLocation(rc);

        if (itemLoc->GetIsSkipped() || itemLoc->HasObtained()) {
            areaChecksGotten[rcArea]++;
        }

        if (itemLoc->IsAvailable() && !IsCheckHidden(rc)) {
            areaChecksAvailable[rcArea]++;
        }
    }

    if (Archipelago_IsCurrentSaveActive()) {
        for (const auto& entry : kNpcSpeechFinderEntries) {
            if (!IsNpcSpeechVisible(entry) || GetNpcSpeechArea(entry) != rcArea) {
                continue;
            }
            areaCheckTotals[rcArea]++;
            if (Archipelago_IsLocationReported(entry.locationId)) {
                areaChecksGotten[rcArea]++;
            } else if (availableNpcSpeechLocations.contains(entry.locationId)) {
                areaChecksAvailable[rcArea]++;
            }
        }
        for (size_t enemyIndex = 0; enemyIndex < kEnemyDefeatFinderEntryCount; ++enemyIndex) {
            const auto& entry = kEnemyDefeatFinderEntries[enemyIndex];
            if (!IsEnemyDefeatVisible(entry) || entry.area != rcArea) continue;
            areaCheckTotals[rcArea]++;
            if (Archipelago_IsLocationReported(entry.locationId)) {
                areaChecksGotten[rcArea]++;
            } else if (availableEnemyDefeatLocations.contains(entry.locationId)) {
                areaChecksAvailable[rcArea]++;
            }
        }
    }

    CalculateTotals();
}

std::map<RandomizerGet, RandomizerCheckArea> MapRGtoRandomizerCheckArea = {
    { RG_DEKU_TREE_MAP, RCAREA_DEKU_TREE },
    { RG_DODONGOS_CAVERN_MAP, RCAREA_DODONGOS_CAVERN },
    { RG_JABU_JABUS_BELLY_MAP, RCAREA_JABU_JABUS_BELLY },
    { RG_FOREST_TEMPLE_MAP, RCAREA_FOREST_TEMPLE },
    { RG_FIRE_TEMPLE_MAP, RCAREA_FIRE_TEMPLE },
    { RG_WATER_TEMPLE_MAP, RCAREA_WATER_TEMPLE },
    { RG_SPIRIT_TEMPLE_MAP, RCAREA_SPIRIT_TEMPLE },
    { RG_SHADOW_TEMPLE_MAP, RCAREA_SHADOW_TEMPLE },
    { RG_BOTTOM_OF_THE_WELL_MAP, RCAREA_BOTTOM_OF_THE_WELL },
    { RG_ICE_CAVERN_MAP, RCAREA_ICE_CAVERN }
};

// In the case that we get an excess key or silver rupee, it spoils the MQ status
// because it is not turned into a blue rupee as excess.
// For keyrings, we can count the keys on the viewmodel
void SpoilAreaFromCheck(RandomizerCheck rc) {
    Rando::Location* loc = Rando::StaticData::GetLocation(rc);
    Rando::ItemLocation* itemLoc = Rando::Context::GetInstance()->GetItemLocation(rc);
    if (itemLoc->GetPlacedItem().GetItemType() == ItemType::ITEMTYPE_MAP) {
        RandomizerCheckArea area = MapRGtoRandomizerCheckArea[itemLoc->GetPlacedRandomizerGet()];
        if (!IsAreaSpoiled(area)) {
            SetAreaSpoiled(area);
        }
    }
    if (itemLoc->GetPlacedItem().GetItemType() == ItemType::ITEMTYPE_SILVER) {
        if (!Rando::StaticData::constantSilvers.contains(itemLoc->GetPlacedRandomizerGet()) &&
            !IsAreaSpoiled(Rando::StaticData::silverToArea[itemLoc->GetPlacedRandomizerGet()])) {
            SetAreaSpoiled(Rando::StaticData::silverToArea[itemLoc->GetPlacedRandomizerGet()]);
        } else if (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_SILVER) ==
                   RO_SHUFFLE_SILVER_ON) {
            switch (itemLoc->GetPlacedRandomizerGet()) {
                case RG_SHADOW_SILVER_SPIKES:
                    if (*Randomizer::SilverFieldFromSaveContext(&gSaveContext, itemLoc->GetPlacedRandomizerGet()) >=
                        6) {
                        SetAreaSpoiled(RCAREA_SHADOW_TEMPLE);
                    }
                    break;
                case RG_GTG_SILVER_LAVA:
                    if (*Randomizer::SilverFieldFromSaveContext(&gSaveContext, itemLoc->GetPlacedRandomizerGet()) >=
                        6) {
                        SetAreaSpoiled(RCAREA_GERUDO_TRAINING_GROUND);
                    }
                    break;
                case RG_GTG_SILVER_WATER:
                    if (*Randomizer::SilverFieldFromSaveContext(&gSaveContext, itemLoc->GetPlacedRandomizerGet()) >=
                        4) {
                        SetAreaSpoiled(RCAREA_GERUDO_TRAINING_GROUND);
                    }
                    break;
                default:
                    break;
            }
        }
    } else if (itemLoc->GetPlacedItem().GetItemType() == ItemType::ITEMTYPE_SMALLKEY) {
        switch (itemLoc->GetPlacedRandomizerGet()) {
            case RG_FOREST_TEMPLE_SMALL_KEY:
                if (OTRGlobals::Instance->gRandoContext->GetDungeon(Rando::FOREST_TEMPLE)
                        ->GetTotalSmallKeys(&gSaveContext) >= 6) {
                    SetAreaSpoiled(RCAREA_FOREST_TEMPLE);
                }
                break;
            case RG_FIRE_TEMPLE_SMALL_KEY:
                if (OTRGlobals::Instance->gRandoContext->GetDungeon(Rando::FIRE_TEMPLE)
                        ->GetTotalSmallKeys(&gSaveContext) >= 6) {
                    SetAreaSpoiled(RCAREA_FIRE_TEMPLE);
                }
                break;
            case RG_WATER_TEMPLE_SMALL_KEY:
                if (OTRGlobals::Instance->gRandoContext->GetDungeon(Rando::WATER_TEMPLE)
                        ->GetTotalSmallKeys(&gSaveContext) >= 3) {
                    SetAreaSpoiled(RCAREA_WATER_TEMPLE);
                }
                break;
            case RG_SPIRIT_TEMPLE_SMALL_KEY:
                if (OTRGlobals::Instance->gRandoContext->GetDungeon(Rando::SPIRIT_TEMPLE)
                        ->GetTotalSmallKeys(&gSaveContext) >= 6) {
                    SetAreaSpoiled(RCAREA_SPIRIT_TEMPLE);
                }
                break;
            case RG_SHADOW_TEMPLE_SMALL_KEY:
                if (OTRGlobals::Instance->gRandoContext->GetDungeon(Rando::SHADOW_TEMPLE)
                        ->GetTotalSmallKeys(&gSaveContext) >= 6) {
                    SetAreaSpoiled(RCAREA_SHADOW_TEMPLE);
                }
                break;
            case RG_BOTTOM_OF_THE_WELL_SMALL_KEY:
                if (OTRGlobals::Instance->gRandoContext->GetDungeon(Rando::BOTTOM_OF_THE_WELL)
                        ->GetTotalSmallKeys(&gSaveContext) >= 3) {
                    SetAreaSpoiled(RCAREA_BOTTOM_OF_THE_WELL);
                }
                break;
            case RG_GERUDO_TRAINING_GROUND_SMALL_KEY:
                if (OTRGlobals::Instance->gRandoContext->GetDungeon(Rando::GERUDO_TRAINING_GROUND)
                        ->GetTotalSmallKeys(&gSaveContext) >= 4) {
                    SetAreaSpoiled(RCAREA_GERUDO_TRAINING_GROUND);
                }
                break;
            case RG_FOREST_TEMPLE_KEY_RING:
                SetAreaSpoiled(RCAREA_FOREST_TEMPLE);
                break;
            case RG_FIRE_TEMPLE_KEY_RING:
                SetAreaSpoiled(RCAREA_FIRE_TEMPLE);
                break;
            case RG_WATER_TEMPLE_KEY_RING:
                SetAreaSpoiled(RCAREA_WATER_TEMPLE);
                break;
            case RG_SPIRIT_TEMPLE_KEY_RING:
                SetAreaSpoiled(RCAREA_SPIRIT_TEMPLE);
                break;
            case RG_SHADOW_TEMPLE_KEY_RING:
                SetAreaSpoiled(RCAREA_SHADOW_TEMPLE);
                break;
            case RG_BOTTOM_OF_THE_WELL_KEY_RING:
                SetAreaSpoiled(RCAREA_BOTTOM_OF_THE_WELL);
                break;
            case RG_GERUDO_TRAINING_GROUND_KEY_RING:
                SetAreaSpoiled(RCAREA_GERUDO_TRAINING_GROUND);
                break;
            default:
                break;
        }
    }
    if (!IsAreaSpoiled(loc->GetArea())) {
        SetAreaSpoiled(loc->GetArea());
    }
}

void SpoilAreaFromCantObtain(RandomizerGet rg) {
    // only spoil if it wouldn't transform anyway, in case someone manages to glitch this value
    switch (rg) {
        case RG_FOREST_TEMPLE_SMALL_KEY:
            if (OTRGlobals::Instance->gRandoContext->GetDungeon(Rando::FOREST_TEMPLE)
                    ->GetTotalSmallKeys(&gSaveContext) < 6) {
                SetAreaSpoiled(RCAREA_FOREST_TEMPLE);
            }
            break;
        case RG_FIRE_TEMPLE_SMALL_KEY:
            if (OTRGlobals::Instance->gRandoContext->GetDungeon(Rando::FIRE_TEMPLE)->GetTotalSmallKeys(&gSaveContext) <
                8) {
                SetAreaSpoiled(RCAREA_FIRE_TEMPLE);
            }
            break;
        case RG_WATER_TEMPLE_SMALL_KEY:
            if (OTRGlobals::Instance->gRandoContext->GetDungeon(Rando::WATER_TEMPLE)->GetTotalSmallKeys(&gSaveContext) <
                6) {
                SetAreaSpoiled(RCAREA_WATER_TEMPLE);
            }
            break;
        case RG_SPIRIT_TEMPLE_SMALL_KEY:
            if (OTRGlobals::Instance->gRandoContext->GetDungeon(Rando::SPIRIT_TEMPLE)
                    ->GetTotalSmallKeys(&gSaveContext) < 7) {
                SetAreaSpoiled(RCAREA_SPIRIT_TEMPLE);
            }
            break;
        case RG_SHADOW_TEMPLE_SMALL_KEY:
            if (OTRGlobals::Instance->gRandoContext->GetDungeon(Rando::SHADOW_TEMPLE)
                    ->GetTotalSmallKeys(&gSaveContext) < 6) {
                SetAreaSpoiled(RCAREA_SHADOW_TEMPLE);
            }
            break;
        case RG_BOTTOM_OF_THE_WELL_SMALL_KEY:
            if (OTRGlobals::Instance->gRandoContext->GetDungeon(Rando::BOTTOM_OF_THE_WELL)
                    ->GetTotalSmallKeys(&gSaveContext) < 3) {
                SetAreaSpoiled(RCAREA_BOTTOM_OF_THE_WELL);
            }
            break;
        case RG_GERUDO_TRAINING_GROUND_SMALL_KEY:
            if (OTRGlobals::Instance->gRandoContext->GetDungeon(Rando::GERUDO_TRAINING_GROUND)
                    ->GetTotalSmallKeys(&gSaveContext) < 9) {
                SetAreaSpoiled(RCAREA_GERUDO_TRAINING_GROUND);
            }
            break;
        case RG_SHADOW_SILVER_SPIKES:
            if (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_SILVER) == RO_SHUFFLE_SILVER_ON &&
                *Randomizer::SilverFieldFromSaveContext(&gSaveContext, rg) < 10) {
                SetAreaSpoiled(RCAREA_SHADOW_TEMPLE);
            }
            break;
        case RG_GTG_SILVER_LAVA:
            if (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_SILVER) == RO_SHUFFLE_SILVER_ON &&
                *Randomizer::SilverFieldFromSaveContext(&gSaveContext, rg) < 6) {
                SetAreaSpoiled(RCAREA_GERUDO_TRAINING_GROUND);
            }
            break;
        case RG_GTG_SILVER_WATER:
            if (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_SILVER) == RO_SHUFFLE_SILVER_ON &&
                *Randomizer::SilverFieldFromSaveContext(&gSaveContext, rg) < 5) {
                SetAreaSpoiled(RCAREA_GERUDO_TRAINING_GROUND);
            }
            break;
        default:
            return;
    }
}

void RecalculateAllAreaTotals() {
    for (auto& [rcArea, checks] : checksByArea) {
        if (rcArea == RCAREA_INVALID) {
            return;
        }
        RecalculateAreaTotals(rcArea);
    }
}

void SetCheckCollected(RandomizerCheck rc) {
    Rando::ItemLocation* itemLoc = OTRGlobals::Instance->gRandoContext->GetItemLocation(rc);
    Rando::Location* loc = Rando::StaticData::GetLocation(rc);
    if (itemLoc == nullptr || loc == nullptr) {
        return;
    }

    const bool wasObtained = itemLoc->HasObtained();
    itemLoc->SetCheckStatus(RCSHOW_COLLECTED);

    // Archipelago check collection must stay cheap. The old path called
    // UpdateOrdering(), which calls RecalculateAllAreaTotals(). In AP mode,
    // IsVisibleInCheckTracker() consults the AP location map, so that full recount
    // can become hundreds of thousands of name comparisons on a single pickup.
    //
    // Update only this check/area here. Full tracker rebuilds still happen at the
    // normal load/settings boundaries, not on the gameplay collection frame.
    if (Archipelago_IsCurrentSaveActive()) {
        const RandomizerCheckArea area = loc->GetArea();

        if (!wasObtained && IsVisibleInCheckTracker(rc)) {
            if (!itemLoc->GetIsSkipped()) {
                areaChecksGotten[area]++;
                if (areaChecksAvailable[area] > 0) {
                    areaChecksAvailable[area]--;
                }
            } else {
                itemLoc->SetIsSkipped(false);
            }
        }

        SaveManager::Instance->SaveSection(gSaveContext.fileNum, sectionId, true);

        if (!IsAreaSpoiled(area)) {
            SetAreaSpoiled(area);
        }

        doAreaScroll = true;
        if (checksByArea.contains(area)) {
            std::sort(checksByArea.find(area)->second.begin(), checksByArea.find(area)->second.end(), CompareChecks);
        }
        CalculateTotals();
        UpdateInventoryChecks();
        return;
    }

    if (IsVisibleInCheckTracker(rc)) {
        if (!itemLoc->GetIsSkipped()) {
            areaChecksGotten[loc->GetArea()]++;
            areaChecksAvailable[loc->GetArea()]--;
        } else {
            itemLoc->SetIsSkipped(false);
        }
    }
    SaveManager::Instance->SaveSection(gSaveContext.fileNum, sectionId, true);

    if (!IsAreaSpoiled(loc->GetArea())) {
        SetAreaSpoiled(loc->GetArea());
    }

    doAreaScroll = true;
    UpdateOrdering(loc->GetArea());
    UpdateInventoryChecks();
}

bool IsAreaScene(SceneID sceneNum) {
    switch (sceneNum) {
        case SCENE_HYRULE_FIELD:
        case SCENE_KAKARIKO_VILLAGE:
        case SCENE_GRAVEYARD:
        case SCENE_ZORAS_RIVER:
        case SCENE_KOKIRI_FOREST:
        case SCENE_SACRED_FOREST_MEADOW:
        case SCENE_LAKE_HYLIA:
        case SCENE_ZORAS_DOMAIN:
        case SCENE_ZORAS_FOUNTAIN:
        case SCENE_GERUDO_VALLEY:
        case SCENE_LOST_WOODS:
        case SCENE_DESERT_COLOSSUS:
        case SCENE_GERUDOS_FORTRESS:
        case SCENE_HAUNTED_WASTELAND:
        case SCENE_HYRULE_CASTLE:
        case SCENE_DEATH_MOUNTAIN_TRAIL:
        case SCENE_DEATH_MOUNTAIN_CRATER:
        case SCENE_GORON_CITY:
        case SCENE_LON_LON_RANCH:
        case SCENE_DEKU_TREE:
        case SCENE_DODONGOS_CAVERN:
        case SCENE_JABU_JABU:
        case SCENE_FOREST_TEMPLE:
        case SCENE_FIRE_TEMPLE:
        case SCENE_WATER_TEMPLE:
        case SCENE_SPIRIT_TEMPLE:
        case SCENE_SHADOW_TEMPLE:
        case SCENE_BOTTOM_OF_THE_WELL:
        case SCENE_ICE_CAVERN:
        case SCENE_GERUDO_TRAINING_GROUND:
        case SCENE_GANONS_TOWER:
        case SCENE_INSIDE_GANONS_CASTLE:
        case SCENE_BACK_ALLEY_DAY:
        case SCENE_BACK_ALLEY_NIGHT:
        case SCENE_MARKET_DAY:
        case SCENE_MARKET_NIGHT:
        case SCENE_MARKET_RUINS:
            return true;
        default:
            return false;
    }
}

RandomizerCheckArea AreaFromEntranceGroup[] = {
    RCAREA_INVALID,          RCAREA_KOKIRI_FOREST, RCAREA_LOST_WOODS,           RCAREA_SACRED_FOREST_MEADOW,
    RCAREA_KAKARIKO_VILLAGE, RCAREA_GRAVEYARD,     RCAREA_DEATH_MOUNTAIN_TRAIL, RCAREA_DEATH_MOUNTAIN_CRATER,
    RCAREA_GORON_CITY,       RCAREA_ZORAS_RIVER,   RCAREA_ZORAS_DOMAIN,         RCAREA_ZORAS_FOUNTAIN,
    RCAREA_HYRULE_FIELD,     RCAREA_LON_LON_RANCH, RCAREA_LAKE_HYLIA,           RCAREA_GERUDO_VALLEY,
    RCAREA_GERUDO_FORTRESS,  RCAREA_WASTELAND,     RCAREA_DESERT_COLOSSUS,      RCAREA_MARKET,
    RCAREA_HYRULE_CASTLE,
};

RandomizerCheckArea GetCheckArea() {
    auto scene = static_cast<SceneID>(gPlayState->sceneNum);
    bool grottoScene = (scene == SCENE_GROTTOS || scene == SCENE_FAIRYS_FOUNTAIN);
    const EntranceData* ent = EntranceTracker::GetEntranceData(
        grottoScene ? ENTRANCE_GROTTO_EXIT_START + EntranceTracker::GetCurrentGrottoId() : gSaveContext.entranceIndex);
    RandomizerCheckArea area = RCAREA_INVALID;
    if (ent != nullptr && !IsAreaScene(scene) && ent->type != ENTRANCE_TYPE_DUNGEON) {
        if (ent->source == "Desert Colossus" || ent->destination == "Desert Colossus") {
            area = RCAREA_DESERT_COLOSSUS;
        } else {
            area = AreaFromEntranceGroup[ent->dstGroup];
        }
    }
    if (area == RCAREA_INVALID) {
        if (grottoScene && (EntranceTracker::GetCurrentGrottoId() == -1) &&
            (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_GROTTO_ENTRANCES) == RO_GENERIC_OFF)) {
            area = previousArea;
        } else {
            area = RandomizerCheckObjects::GetRCAreaBySceneID(scene);
        }
    }
    return area;
}

std::array<SceneID, 4> skipScenes = {
    SCENE_GANON_BOSS,
    SCENE_GANONS_TOWER_COLLAPSE_EXTERIOR,
    SCENE_INSIDE_GANONS_CASTLE_COLLAPSE,
    SCENE_GANONS_TOWER_COLLAPSE_INTERIOR,
};

void ClearAreaChecksAndTotals() {
    availableNpcSpeechLocations.clear();
    availableEnemyDefeatLocations.clear();
    for (auto& [rcArea, vec] : checksByArea) {
        vec.clear();
        areaChecksGotten[rcArea] = 0;
        areaChecksAvailable[rcArea] = 0;
        areaCheckTotals[rcArea] = 0;
    }
    totalChecks = 0;
    totalChecksGotten = 0;
    totalChecksAvailable = 0;
}

void SetShopSeen(uint32_t sceneNum, bool prices) {
    RandomizerCheck start = startingShopItem.find(sceneNum)->second;
    if (sceneNum == SCENE_POTION_SHOP_KAKARIKO && !LINK_IS_ADULT) {
        return;
    }
    if (GetCheckArea() == RCAREA_KAKARIKO_VILLAGE && sceneNum == SCENE_BAZAAR) {
        start = RC_KAK_BAZAAR_ITEM_1;
    }
    bool statusChanged = false;
    for (int i = start; i < start + 8; i++) {
        if (OTRGlobals::Instance->gRandoContext->GetItemLocation(i)->GetCheckStatus() == RCSHOW_UNCHECKED) {
            OTRGlobals::Instance->gRandoContext->GetItemLocation(i)->SetCheckStatus(RCSHOW_SEEN_OR_HINTED);
            statusChanged = true;
        }
    }
    if (statusChanged) {
        SaveManager::Instance->SaveSection(gSaveContext.fileNum, sectionId, true);
    }
}

// Items share hint text keys: all six jabber nuts are "the ability to speak".
// Counted once on first use.
static bool HintNamesItemUniquely(RandomizerGet rg) {
    static const auto keyUses = [] {
        std::array<uint16_t, RHT_MAX> uses{};
        for (const auto& item : Rando::StaticData::GetItemTable()) {
            uses[item.GetHintKey()]++;
        }
        return uses;
    }();
    return keyUses[Rando::StaticData::RetrieveItem(rg).GetHintKey()] == 1;
}

// Only HINT_TYPE_ITEM hints name a check's item outright; other types stay
// ambiguous. Marks Seen, not Identified, since hints never state a price.
static bool ApplyItemHintToChecks(RandomizerHint hintKey) {
    // Ambiguous/obscure hints reuse the same phrase across items (all four swords are
    // just "a sword"), so only clear hints are safe to mark - skip anything else
    if (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_HINT_CLARITY) != RO_HINT_CLARITY_CLEAR) {
        return false;
    }

    if (hintKey == RH_NONE) {
        return false;
    }

    // The hint-revealed hook can fire for hints the seed has disabled.
    auto hint = OTRGlobals::Instance->gRandoContext->GetHint(hintKey);
    if (!hint->IsEnabled() || hint->GetHintType() != HINT_TYPE_ITEM) {
        return false;
    }

    // Loop over hinted locations, apply the ones which are unambiguous
    bool changed = false;
    for (RandomizerCheck rc : hint->GetHintedLocations()) {
        if (rc == RC_UNKNOWN_CHECK) {
            continue;
        }
        auto loc = OTRGlobals::Instance->gRandoContext->GetItemLocation(rc);
        // Ice traps hint, and display, as their disguise.
        RandomizerGet named = loc->GetPlacedRandomizerGet();
        auto& overrides = OTRGlobals::Instance->gRandoContext->overrides;
        if (named == RG_ICE_TRAP && overrides.contains(rc)) {
            named = overrides[rc].LooksLike();
        }
        if (!HintNamesItemUniquely(named)) {
            // The hint could mean several items, no spoilers!
            continue;
        }
        if (loc->GetCheckStatus() == RCSHOW_UNCHECKED) {
            loc->SetCheckStatus(RCSHOW_SEEN_OR_HINTED);
            changed = true;
        }
    }
    return changed;
}

void CheckTrackerHintRevealed(RandomizerHint hintKey) {
    if (!GameInteractor::IsSaveLoaded() || !IS_RANDO) {
        return;
    }
    if (ApplyItemHintToChecks(hintKey)) {
        SaveManager::Instance->SaveSection(gSaveContext.fileNum, sectionId, true);
    }
}

void CheckTrackerLoadGame(int32_t fileNum) {
    if (IS_BOSS_RUSH) {
        return;
    }

    trackerLoadInProgress = true;
    ResetLiveFinderStateSnapshot();
    LoadSettings();

    // AP slot data is authoritative, but many sanity location families are registered
    // by separate Ship init hooks.  A tracker rebuild can run before one of those hooks
    // after Start/Reset, leaving a perfectly valid AP location absent from StaticData
    // and therefore invisible to Check Finder.  Every registration function below is
    // idempotent, so make the location table complete before rebuilding checksByArea.
    if (Archipelago_IsCurrentSaveActive()) {
        Rando::StaticData::RegisterSongLocations();
        Rando::StaticData::RegisterBeehiveLocations();
        Rando::StaticData::RegisterCowLocations();
        Rando::StaticData::RegisterFishLocations();
        Rando::StaticData::RegisterFairyLocations();
        Rando::StaticData::RegisterPotLocations();
        Rando::StaticData::RegisterFreestandingLocations();
        Rando::StaticData::RegisterSilverLocations();
        Rando::StaticData::RegisterGrassLocations();
        Rando::StaticData::RegisterCrateLocations();
        Rando::StaticData::RegisterRockLocations();
        Rando::StaticData::RegisterTreeLocations();
        Rando::StaticData::RegisterSignLocations();
        Rando::StaticData::RegisterWonderItemLocations();
        Rando::StaticData::RegisterBeggarLocations();
        Rando::StaticData::RegisterIcicleLocations();
        Rando::StaticData::RegisterRedIceLocations();
    }

    TrySetAreas();

    // On an in-process AP reload (new file -> Start, or Reset -> Start), the
    // tracker containers can still contain derived data from the previous phase.
    // Rebuild them exactly once instead of appending/sorting duplicate entries.
    ClearAreaChecksAndTotals();
    checkNameOverrides.clear();

    for (auto& entry : Rando::StaticData::GetLocationTable()) {
        RandomizerCheck rc = entry.GetRandomizerCheck();
        if (rc == RC_UNKNOWN_CHECK || rc == RC_MAX || rc == RC_LINKS_POCKET) {
            continue;
        }

        Rando::Location* entry2 = Rando::StaticData::GetLocation(rc);
        if (entry2 == nullptr || entry2->GetArea() == RCAREA_INVALID) {
            continue;
        }
        Rando::ItemLocation* loc = OTRGlobals::Instance->gRandoContext->GetItemLocation(rc);

        checksByArea.find(entry2->GetArea())->second.push_back(entry2->GetRandomizerCheck());
        if (IsVisibleInCheckTracker(entry2->GetRandomizerCheck())) {
            areaCheckTotals[entry2->GetArea()]++;
            if (loc->GetCheckStatus() == RCSHOW_SAVED || loc->GetIsSkipped()) {
                areaChecksGotten[entry2->GetArea()]++;
            }
            if (loc->IsAvailable()) {
                areaChecksAvailable[entry2->GetArea()]++;
            }
        }

        if (areaChecksGotten[entry2->GetArea()] != 0 || RandomizerCheckObjects::AreaIsOverworld(entry2->GetArea()) ||
            loc->GetCheckStatus() == RCSHOW_SCUMMED) {
            areasSpoiled |= (1 << entry2->GetArea());
        }

        // Create check name overrides for child pond fish if age split is disabled
        if (fishsanityMode != RO_FISHSANITY_OFF && fishsanityMode != RO_FISHSANITY_OVERWORLD &&
            entry.GetRCType() == RCTYPE_FISH && entry.GetScene() == SCENE_FISHING_POND &&
            entry.GetActorParams() != 116 && !fishsanityAgeSplit) {
            if (entry.GetShortName().starts_with("Child")) {
                checkNameOverrides[rc] = entry.GetShortName().substr(6);
            }
        }
    }

    if (Archipelago_IsCurrentSaveActive()) {
        for (const auto& entry : kNpcSpeechFinderEntries) {
            if (!IsNpcSpeechVisible(entry)) {
                continue;
            }
            const auto area = GetNpcSpeechArea(entry);
            areaCheckTotals[area]++;
            if (Archipelago_IsLocationReported(entry.locationId)) {
                areaChecksGotten[area]++;
            }
        }
        for (size_t enemyIndex = 0; enemyIndex < kEnemyDefeatFinderEntryCount; ++enemyIndex) {
            const auto& entry = kEnemyDefeatFinderEntries[enemyIndex];
            if (!IsEnemyDefeatVisible(entry)) continue;
            areaCheckTotals[entry.area]++;
            if (Archipelago_IsLocationReported(entry.locationId)) {
                areaChecksGotten[entry.area]++;
            }
        }
    }

    for (int i = RCAREA_KOKIRI_FOREST; i < RCAREA_INVALID; i++) {
        if (!IsAreaSpoiled(static_cast<RandomizerCheckArea>(i)) &&

            (RandomizerCheckObjects::AreaIsOverworld(static_cast<RandomizerCheckArea>(i)) || !IS_RANDO ||
             OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_MQ_DUNGEON_RANDOM) == RO_MQ_DUNGEONS_NONE ||
             (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_MQ_DUNGEON_RANDOM) ==
                  RO_MQ_DUNGEONS_SELECTION &&
              OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(
                  static_cast<RandomizerSettingKey>(RSK_MQ_DEKU_TREE + (i - RCAREA_DEKU_TREE))) != RO_MQ_SET_RANDOM) ||
             (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_MQ_DUNGEON_SET) == RO_GENERIC_ON &&
              OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(
                  static_cast<RandomizerSettingKey>(RSK_MQ_DEKU_TREE + (i - RCAREA_DEKU_TREE))) != RO_MQ_SET_RANDOM) ||
             (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_MQ_DUNGEON_RANDOM) ==
                  RO_MQ_DUNGEONS_SET_NUMBER &&
              (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_MQ_DUNGEON_COUNT) == MAX_MQ_DUNGEON_COUNT ||
               OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_MQ_DUNGEON_COUNT) == 0)))) {
            SetAreaSpoiled(static_cast<RandomizerCheckArea>(i));
        }
    }
    if (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_LINKS_POCKET) != RO_LINKS_POCKET_NOTHING &&
        IS_RANDO) {
        uint8_t startingAge = OTRGlobals::Instance->gRandoContext->GetOption(RSK_SELECTED_STARTING_AGE).Get();
        RandomizerCheckArea startingArea;
        switch (startingAge) {
            case RO_AGE_CHILD:
                startingArea = RCAREA_KOKIRI_FOREST;
                break;
            case RO_AGE_ADULT:
                startingArea = RCAREA_MARKET;
                break;
            default:
                startingArea = RCAREA_KOKIRI_FOREST;
                break;
        }

        checksByArea.find(startingArea)->second.push_back(RC_LINKS_POCKET);
        areaChecksGotten[startingArea]++;
        areaCheckTotals[startingArea]++;
    }

    showVOrMQ =
        (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_MQ_DUNGEON_RANDOM) ==
             RO_MQ_DUNGEONS_RANDOM_NUMBER ||
         (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_MQ_DUNGEON_RANDOM) == RO_MQ_DUNGEONS_SET_NUMBER &&
          OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_MQ_DUNGEON_COUNT) < MAX_MQ_DUNGEON_COUNT));
    initialized = true;
    UpdateAllOrdering();
    UpdateInventoryChecks();
    UpdateFilters();

    RegionTable_Init();

    Rando::Context::GetInstance()->GetEntranceShuffler()->ApplyEntranceOverrides();

    recalculateAvailable = CVarGetInteger(CVAR_TRACKER_CHECK("EnableAvailableChecks"), 0) != 0;
    trackerLoadInProgress = false;

    if (Archipelago_IsCurrentSaveActive()) {
        SPDLOG_INFO("[Archipelago] Check Tracker load completed; Available Checks scheduled={}",
                    recalculateAvailable);
    }
}

void CheckTrackerShopSlotChange(uint8_t cursorSlot, int16_t basePrice) {
    if (gPlayState->sceneNum == SCENE_HAPPY_MASK_SHOP) { // Happy Mask Shop is not used in rando, so is not tracked
        return;
    }

    auto slot = startingShopItem.find(gPlayState->sceneNum)->second + cursorSlot;
    if (GetCheckArea() == RCAREA_KAKARIKO_VILLAGE && gPlayState->sceneNum == SCENE_BAZAAR) {
        slot = RC_KAK_BAZAAR_ITEM_1 + cursorSlot;
    }
    auto status = OTRGlobals::Instance->gRandoContext->GetItemLocation(slot)->GetCheckStatus();
    if (status == RCSHOW_SEEN_OR_HINTED) {
        OTRGlobals::Instance->gRandoContext->GetItemLocation(slot)->SetCheckStatus(RCSHOW_IDENTIFIED);
        SaveManager::Instance->SaveSection(gSaveContext.fileNum, sectionId, true);
        RecalculateAvailableChecks();
    }
}

void CheckTrackerTransition(uint32_t sceneNum) {
    if (!GameInteractor::IsSaveLoaded()) {
        return;
    }
    doAreaScroll = true;
    previousArea = currentArea;
    currentArea = GetCheckArea();

    // AP placement/mapping is scene-local. OnSceneInit has just warmed this scene,
    // so refresh only the tracker area we actually entered instead of rebuilding
    // every area/check in the world.
    if (Archipelago_IsCurrentSaveActive() && currentArea != RCAREA_INVALID) {
        RecalculateAreaTotals(currentArea);
        UpdateAreas(currentArea);
        if (CVarGetInteger(CVAR_TRACKER_CHECK("EnableAvailableChecks"), 0)) {
            RecalculateAvailableChecks();
        }
    }

    switch (sceneNum) {
        case SCENE_KOKIRI_SHOP:
        case SCENE_BAZAAR:
        case SCENE_POTION_SHOP_MARKET:
        case SCENE_BOMBCHU_SHOP:
        case SCENE_POTION_SHOP_KAKARIKO:
        case SCENE_GORON_SHOP:
        case SCENE_ZORA_SHOP:
            SetShopSeen(sceneNum, false);
            break;
    }
    if (!IsAreaSpoiled(currentArea) && (RandomizerCheckObjects::AreaIsOverworld(currentArea) ||
                                        std::find(spoilingEntrances.begin(), spoilingEntrances.end(),
                                                  gPlayState->nextEntranceIndex) != spoilingEntrances.end())) {
        SetAreaSpoiled(currentArea);
    }
}

void CheckTrackerItemReceive(GetItemEntry giEntry) {
    if (!GameInteractor::IsSaveLoaded() || std::find(std::begin(skipScenes), std::end(skipScenes),
                                                     (SceneID)gPlayState->sceneNum) != std::end(skipScenes)) {
        return;
    }

    // In randomizer/AP, even a non-major receive can change live reachability.
    // Bombchu 5/10/20 refills are the concrete case: the live logic deliberately
    // checks CURRENT Bombchu ammo, but these refills are not necessarily classified
    // as advancement.  RecalculateAvailableChecks() only schedules/debounces the
    // expensive graph pass, so it is safe to request it for every received item.
    if (IS_RANDO) {
        if (CVarGetInteger(CVAR_TRACKER_CHECK("EnableAvailableChecks"), 0)) {
            RecalculateAvailableChecks();
        }
        return;
    }

    auto scene = static_cast<SceneID>(gPlayState->sceneNum);
    // Vanilla special item checks
    if (!IS_RANDO) {
        if (giEntry.itemId == ITEM_SHIELD_DEKU) {
            SetCheckCollected(RC_KF_SHOP_ITEM_1);
            return;
        } else if (giEntry.itemId == ITEM_KOKIRI_EMERALD) {
            SetCheckCollected(RC_QUEEN_GOHMA);
            return;
        } else if (giEntry.itemId == ITEM_GORON_RUBY) {
            SetCheckCollected(RC_KING_DODONGO);
            return;
        } else if (giEntry.itemId == ITEM_ZORA_SAPPHIRE) {
            SetCheckCollected(RC_BARINADE);
            return;
        } else if (giEntry.itemId == ITEM_MEDALLION_FOREST) {
            SetCheckCollected(RC_PHANTOM_GANON);
            return;
        } else if (giEntry.itemId == ITEM_MEDALLION_FIRE) {
            SetCheckCollected(RC_VOLVAGIA);
            return;
        } else if (giEntry.itemId == ITEM_MEDALLION_WATER) {
            SetCheckCollected(RC_MORPHA);
            return;
        } else if (giEntry.itemId == ITEM_MEDALLION_SHADOW) {
            SetCheckCollected(RC_BONGO_BONGO);
            return;
        } else if (giEntry.itemId == ITEM_MEDALLION_SPIRIT) {
            SetCheckCollected(RC_TWINROVA);
            return;
        } else if (giEntry.itemId == ITEM_MEDALLION_LIGHT) {
            SetCheckCollected(RC_GIFT_FROM_RAURU);
            return;
        } else if (giEntry.itemId == ITEM_SONG_EPONA) {
            SetCheckCollected(RC_SONG_FROM_MALON);
            return;
        } else if (giEntry.itemId == ITEM_SONG_SARIA) {
            SetCheckCollected(RC_SONG_FROM_SARIA);
            return;
        } else if (giEntry.itemId == ITEM_BEAN) {
            SetCheckCollected(RC_ZR_MAGIC_BEAN_SALESMAN);
            return;
        } else if (giEntry.itemId == ITEM_BRACELET) {
            SetCheckCollected(RC_GC_DARUNIAS_JOY);
            return;
        } /* else if (giEntry.itemId == ITEM_SONG_SUN) {
             SetCheckCollected(RC_SONG_FROM_ROYAL_FAMILYS_TOMB);
             return;
         } else if (giEntry.itemId == ITEM_SONG_TIME) {
             SetCheckCollected(RC_SONG_FROM_OCARINA_OF_TIME);
             return;
         } else if (giEntry.itemId == ITEM_SONG_STORMS) {
             SetCheckCollected(RC_SONG_FROM_WINDMILL);
             return;
         } else if (giEntry.itemId == ITEM_SONG_MINUET) {
             SetCheckCollected(RC_SHEIK_IN_FOREST);
             return;
         } else if (giEntry.itemId == ITEM_SONG_BOLERO) {
             SetCheckCollected(RC_SHEIK_IN_CRATER);
             return;
         } else if (giEntry.itemId == ITEM_SONG_SERENADE) {
             SetCheckCollected(RC_SHEIK_IN_ICE_CAVERN);
             return;
         } else if (giEntry.itemId == ITEM_SONG_NOCTURNE) {
             SetCheckCollected(RC_SHEIK_IN_KAKARIKO);
             return;
         } else if (giEntry.itemId == ITEM_SONG_REQUIEM) {
             SetCheckCollected(RC_SHEIK_AT_COLOSSUS);
             return;
         } else if (giEntry.itemId == ITEM_SONG_PRELUDE) {
             SetCheckCollected(RC_SHEIK_AT_TEMPLE);
             return;
         }*/
    }
}

void CheckTrackerSceneFlagSet(int16_t sceneNum, int16_t flagType, int32_t flag) {
    if (IS_RANDO) {
        return;
    }

    if (flagType != FLAG_SCENE_TREASURE && flagType != FLAG_SCENE_COLLECTIBLE) {
        return;
    }
    if (sceneNum == SCENE_GRAVEYARD && flag == 0x19 &&
        flagType == FLAG_SCENE_COLLECTIBLE) { // Gravedigging tour special case
        SetCheckCollected(RC_GRAVEYARD_DAMPE_GRAVEDIGGING_TOUR);
        return;
    }
    for (auto& loc : Rando::StaticData::GetLocationTable()) {
        if (!IsVisibleInCheckTracker(loc.GetRandomizerCheck())) {
            continue;
        }
        SpoilerCollectionCheckType checkMatchType = flagType == FLAG_SCENE_TREASURE
                                                        ? SpoilerCollectionCheckType::SPOILER_CHK_CHEST
                                                        : SpoilerCollectionCheckType::SPOILER_CHK_COLLECTABLE;
        Rando::SpoilerCollectionCheck scCheck = loc.GetCollectionCheck();
        if (scCheck.scene == sceneNum && scCheck.flag == flag && scCheck.type == checkMatchType) {
            SetCheckCollected(loc.GetRandomizerCheck());
            return;
        }
    }
}

void CheckTrackerFlagSet(int16_t flagType, int32_t flag) {
    if (IS_RANDO) {
        return;
    }

    SpoilerCollectionCheckType checkMatchType = SpoilerCollectionCheckType::SPOILER_CHK_NONE;
    switch (flagType) {
        case FLAG_GS_TOKEN:
            checkMatchType = SpoilerCollectionCheckType::SPOILER_CHK_GOLD_SKULLTULA;
            break;
        case FLAG_EVENT_CHECK_INF:
            if ((flag == EVENTCHKINF_CARPENTERS_FREE(0) || flag == EVENTCHKINF_CARPENTERS_FREE(1) ||
                 flag == EVENTCHKINF_CARPENTERS_FREE(2) || flag == EVENTCHKINF_CARPENTERS_FREE(3)) &&
                GET_EVENTCHKINF_CARPENTERS_FREE_ALL()) {
                SetCheckCollected(RC_TH_FREED_CARPENTERS);
                return;
            }
            checkMatchType = SpoilerCollectionCheckType::SPOILER_CHK_EVENT_CHK_INF;
            break;
        case FLAG_INF_TABLE:
            if (flag == INFTABLE_190) {
                SetCheckCollected(RC_GF_HBA_1000_POINTS);
                return;
            } else if (flag == INFTABLE_11E) {
                SetCheckCollected(RC_GC_ROLLING_GORON_AS_CHILD);
                return;
            } else if (flag == INFTABLE_GORON_CITY_DOORS_UNLOCKED) {
                SetCheckCollected(RC_GC_ROLLING_GORON_AS_ADULT);
                return;
            } else if (flag == INFTABLE_139) {
                SetCheckCollected(RC_ZD_KING_ZORA_THAWED);
                return;
            } else if (flag == INFTABLE_191) {
                SetCheckCollected(RC_MARKET_LOST_DOG);
                return;
            }
            if (!IS_RANDO) {
                if (flag == INFTABLE_BOUGHT_STICK_UPGRADE) {
                    SetCheckCollected(RC_LW_DEKU_SCRUB_NEAR_BRIDGE);
                    return;
                } else if (flag == INFTABLE_BOUGHT_NUT_UPGRADE) {
                    SetCheckCollected(RC_LW_DEKU_SCRUB_GROTTO_FRONT);
                    return;
                }
            }
            break;
        case FLAG_ITEM_GET_INF:
            if (!IS_RANDO) {
                if (flag == ITEMGETINF_OBTAINED_STICK_UPGRADE_FROM_STAGE) {
                    SetCheckCollected(RC_DEKU_THEATER_SKULL_MASK);
                    return;
                } else if (flag == ITEMGETINF_OBTAINED_NUT_UPGRADE_FROM_STAGE) {
                    SetCheckCollected(RC_DEKU_THEATER_MASK_OF_TRUTH);
                    return;
                } else if (flag == ITEMGETINF_DEKU_SCRUB_HEART_PIECE) {
                    SetCheckCollected(RC_HF_DEKU_SCRUB_GROTTO);
                    return;
                }
            }
            checkMatchType = SpoilerCollectionCheckType::SPOILER_CHK_ITEM_GET_INF;
            break;
        case FLAG_RANDOMIZER_INF:
            checkMatchType = SpoilerCollectionCheckType::SPOILER_CHK_RANDOMIZER_INF;
            break;
    }
    if (checkMatchType == SpoilerCollectionCheckType::SPOILER_CHK_NONE) {
        return;
    }
    for (auto& loc : Rando::StaticData::GetLocationTable()) {
        if ((!IS_RANDO && ((loc.GetQuest() == RCQUEST_MQ && !IS_MASTER_QUEST) ||
                           (loc.GetQuest() == RCQUEST_VANILLA && IS_MASTER_QUEST))) ||
            (IS_RANDO && !(OTRGlobals::Instance->gRandoContext->GetDungeonFromScene(loc.GetScene()) == nullptr) &&
             ((OTRGlobals::Instance->gRandoContext->GetDungeonFromScene(loc.GetScene())->IsMQ() &&
               loc.GetQuest() == RCQUEST_VANILLA) ||
              OTRGlobals::Instance->gRandoContext->GetDungeonFromScene(loc.GetScene())->IsVanilla() &&
                  loc.GetQuest() == RCQUEST_MQ))) {
            continue;
        }
        Rando::SpoilerCollectionCheck scCheck = loc.GetCollectionCheck();
        SpoilerCollectionCheckType scCheckType = scCheck.type;
        if (checkMatchType == SpoilerCollectionCheckType::SPOILER_CHK_RANDOMIZER_INF &&
            scCheckType == SpoilerCollectionCheckType::SPOILER_CHK_RANDOMIZER_INF) {
            if (flag == OTRGlobals::Instance->gRandomizer->GetRandomizerInfFromCheck(loc.GetRandomizerCheck())) {
                SetCheckCollected(loc.GetRandomizerCheck());
                return;
            }
            continue;
        }
        int16_t checkFlag = scCheck.flag;
        if (checkMatchType == SpoilerCollectionCheckType::SPOILER_CHK_GOLD_SKULLTULA) {
            checkFlag = loc.GetActorParams();
        }
        if (checkFlag == flag && scCheck.type == checkMatchType) {
            SetCheckCollected(loc.GetRandomizerCheck());
            return;
        }
    }
}

void CheckTrackerDialogMessage() {
    // These dialogues state the price, so a Seen check upgrades to Identified.
    auto identifyCheck = [](RandomizerCheck rc) {
        auto loc = OTRGlobals::Instance->gRandoContext->GetItemLocation(rc);
        RandomizerCheckStatus status = loc->GetCheckStatus();
        if (status == RCSHOW_UNCHECKED || status == RCSHOW_SEEN_OR_HINTED) {
            loc->SetCheckStatus(RCSHOW_IDENTIFIED);
            RecalculateAvailableChecks();
        }
    };

    if (gPlayState->msgCtx.textId == TEXT_BEAN_SALESMAN_BUY_FOR_10) {
        identifyCheck(RC_ZR_MAGIC_BEAN_SALESMAN);
    } else if (gPlayState->msgCtx.textId == TEXT_MEDIGORON) {
        identifyCheck(RC_GC_MEDIGORON);
    } else if (gPlayState->msgCtx.textId == TEXT_GRANNYS_SHOP) {
        identifyCheck(RC_KAK_GRANNYS_SHOP);
    } else if (gPlayState->msgCtx.textId == TEXT_CARPET_SALESMAN_1) {
        identifyCheck(RC_WASTELAND_BOMBCHU_SALESMAN);
    } else if (gPlayState->msgCtx.textId == TEXT_SCRUB_RANDOM) {
        if (auto* actor = gPlayState->msgCtx.talkActor) {
            if (auto* checkIdentity = ObjectExtension::GetInstance().Get<ScrubIdentity>(actor)) {
                identifyCheck(checkIdentity->identity.randomizerCheck);
            }
        }
    }
}

void InitTrackerData(bool isDebug) {
    TrySetAreas();
    areasSpoiled = 0;
}

void SaveTrackerData(SaveContext* saveContext, int sectionID, bool fullSave) {
    bool updateOrdering = false;
    std::vector<RandomizerCheck> checkCount;
    for (int i = RC_UNKNOWN_CHECK; i < RC_MAX; i++) {
        if (OTRGlobals::Instance->gRandoContext->GetItemLocation(i)->GetCheckStatus() != RCSHOW_UNCHECKED ||
            OTRGlobals::Instance->gRandoContext->GetItemLocation(i)->GetIsSkipped())
            checkCount.push_back(static_cast<RandomizerCheck>(i));
    }
    SaveManager::Instance->SaveArray("checkStatus", checkCount.size(), [&](size_t i) {
        RandomizerCheck check = checkCount.at(i);
        RandomizerCheckStatus savedStatus =
            OTRGlobals::Instance->gRandoContext->GetItemLocation(check)->GetCheckStatus();
        bool isSkipped = OTRGlobals::Instance->gRandoContext->GetItemLocation(check)->GetIsSkipped();
        if (savedStatus == RCSHOW_COLLECTED) {
            if (fullSave) {
                OTRGlobals::Instance->gRandoContext->GetItemLocation(check)->SetCheckStatus(RCSHOW_SAVED);
                savedStatus = RCSHOW_SAVED;
                updateOrdering = true;
            } else {
                savedStatus = RCSHOW_SCUMMED;
            }
        }
        if (savedStatus != RCSHOW_UNCHECKED || isSkipped) {
            SaveManager::Instance->SaveStruct("", [&]() {
                SaveManager::Instance->SaveData("randomizerCheck", check);
                SaveManager::Instance->SaveData("status", savedStatus);
                SaveManager::Instance->SaveData("skipped", isSkipped);
            });
        }
    });
    SaveManager::Instance->SaveData("areasSpoiled", areasSpoiled);
    if (updateOrdering && !Archipelago_IsCurrentSaveActive()) {
        // Native tracker ordering/area recount is expensive on the expanded AP
        // location set and runs inside the save worker. Reset/exit then waits for
        // that worker, making a normal Save -> Reset look frozen. AP check status
        // is still serialized above; only the derived UI recount is skipped.
        UpdateAllOrdering();
        UpdateAllAreas();
    }
}

void SaveFile(SaveContext* saveContext, int sectionID, bool fullSave) {
    SaveTrackerData(saveContext, sectionID, fullSave);
    if (fullSave && !Archipelago_IsCurrentSaveActive()) {
        recalculateAvailable = true;
    }
    // AP saves can be written immediately after an item/check callback.  Do not
    // clear a finder rebuild that was just scheduled by that callback: doing so
    // made live Shovel/Soul/Open-Chest changes appear only after reloading.
}

void LoadFile() {
    SaveManager::Instance->LoadArray("checkStatus", RC_MAX, [](size_t i) {
        SaveManager::Instance->LoadStruct("", [&]() {
            RandomizerCheckStatus status;
            bool skipped;
            RandomizerCheck rc;
            SaveManager::Instance->LoadData("randomizerCheck", rc, RC_UNKNOWN_CHECK);
            SaveManager::Instance->LoadData("status", status, RCSHOW_UNCHECKED);
            SaveManager::Instance->LoadData("skipped", skipped, false);
            OTRGlobals::Instance->gRandoContext->GetItemLocation(rc)->SetCheckStatus(status);
            OTRGlobals::Instance->gRandoContext->GetItemLocation(rc)->SetIsSkipped(skipped);
        });
    });
    SaveManager::Instance->LoadData("areasSpoiled", areasSpoiled, (uint32_t)0);

    // SaveManager is still inside the save-file load here.  When AP is already
    // active in this process (new AP file -> Start, or Reset -> Start), running
    // UpdateAllOrdering() here makes IsVisibleInCheckTracker() take the AP lookup
    // path for the entire world before OnLoadGame.  A clean process did not hit
    // that stale-active path, which is why restarting the EXE made the same save
    // open successfully.  The normal CheckTrackerLoadGame() hook rebuilds all
    // derived ordering/totals once the save has fully loaded.
    if (Archipelago_IsCurrentSaveActive()) {
        recalculateAvailable = false;
        SPDLOG_INFO("[Archipelago] Restored tracker statuses; deferred derived tracker rebuild until OnLoadGame");
        return;
    }

    UpdateAllOrdering();
    UpdateAllAreas();
}

void Teardown() {
    initialized = false;
    trackerLoadInProgress = false;
    recalculateAvailable = false;
    ClearAreaChecksAndTotals();
    checksByArea.clear();
    areasSpoiled = 0;
    filterAreasHidden = { 0 };
    filterChecksHidden = { 0 };

    lastLocationChecked = RC_UNKNOWN_CHECK;
    ResetLiveFinderStateSnapshot();
}

bool IsAreaSpoiled(RandomizerCheckArea rcArea) {
    return areasSpoiled & (1 << rcArea);
}

// we don't care how many silvers for this check, only that all possible silver items are known
bool AreAllSilversSpoiled() {
    return IsAreaSpoiled(RCAREA_DODONGOS_CAVERN) && IsAreaSpoiled(RCAREA_BOTTOM_OF_THE_WELL) &&
           IsAreaSpoiled(RCAREA_GANONS_CASTLE) && IsAreaSpoiled(RCAREA_SHADOW_TEMPLE) &&
           IsAreaSpoiled(RCAREA_SPIRIT_TEMPLE) && IsAreaSpoiled(RCAREA_ICE_CAVERN);
}

void SetAreaSpoiled(RandomizerCheckArea rcArea) {
    const uint32_t mask = (1u << rcArea);
    if ((areasSpoiled & mask) != 0) {
        return;
    }

    areasSpoiled |= mask;

    // CheckTrackerLoadGame() derives/spoils many areas while a save is opening.
    // Saving after every derived bit queues a burst of SaveSection jobs on Start,
    // and Reset/exit later waits for that backlog.  The derived mask is written by
    // the next normal save; no disk/UI work belongs in the load rebuild itself.
    if (trackerLoadInProgress) {
        return;
    }

    SaveManager::Instance->SaveSection(gSaveContext.fileNum, sectionId, true);
    RefreshItemTrackerMainWindow();
}

void InternalRecalculateAvailableChecks(RandomizerRegion startingRegion, RandoAgeTime startingAgeTime);

static RandomizerCheckArea FinderRowArea(int64_t id, const ArchipelagoClient& client) {
    const auto rc = client.GetFinderNativeCheck(id);
    if (rc > static_cast<int32_t>(RC_UNKNOWN_CHECK)) {
        const auto* location = Rando::StaticData::GetLocation(static_cast<RandomizerCheck>(rc));
        if (location != nullptr) return location->GetArea();
    }
    for (const auto& entry : kNpcSpeechFinderEntries) {
        if (entry.locationId == id) return GetNpcSpeechArea(entry);
    }
    for (const auto& entry : kEnemyDefeatFinderEntries) {
        if (entry.locationId == id) return entry.area;
    }
    return RCAREA_INVALID;
}

static void DrawUniversalFinderMirror() {
    auto& client = ArchipelagoClient::GetInstance();
    std::string status;
    const auto* snapshot = client.GetFinderSnapshot(status);
    ImGui::TextWrapped("%s", status.c_str());
    if (ImGui::Button("Refresh AP checks")) client.RefreshFinderMirror();
    ImGui::SameLine();
    if (ImGui::Button("Restart AP tracker")) {
        client.RestartFinderWorker();
        return; // restarting invalidates the snapshot pointer
    }
    if (snapshot == nullptr) {
        ImGui::Separator();
        ImGui::TextWrapped("The game starts Universal Tracker's evaluator automatically. "
            "No tracker window or special launcher is required. Keep tracker.apworld and "
            "the matching soh_extreme.apworld in your Archipelago installation.");
        if (ImGui::CollapsingHeader("Archipelago runtime location")) {
            static char path[2048] = {};
            static bool initialized = false;
            if (!initialized) {
                const char* configured = CVarGetString(CVAR_REMOTE_ARCHIPELAGO("TrackerRuntimePath"), "");
                std::snprintf(path, sizeof(path), "%s", configured ? configured : "");
                initialized = true;
            }
            ImGui::TextWrapped("Normally detected automatically. For a portable/custom installation, "
                "enter its full folder or ArchipelagoLauncherDebug.exe path. Leave blank for automatic detection.");
            ImGui::InputText("Runtime path", path, sizeof(path));
            if (ImGui::Button("Use path and retry")) {
                CVarSetString(CVAR_REMOTE_ARCHIPELAGO("TrackerRuntimePath"), path);
                Ship::Context::GetRawInstance()->GetWindow()->GetGui()->SaveConsoleVariablesNextFrame();
                client.RestartFinderWorker();
            }
            if (!client.GetFinderRuntimePath().empty())
                ImGui::TextWrapped("Detected: %s", client.GetFinderRuntimePath().c_str());
        }
        return;
    }
    size_t normal = 0, glitched = 0;
    for (const auto& row : snapshot->rows) { if (row.state == 1) ++normal; else ++glitched; }
    ImGui::Text("In logic: %u   Glitched: %u   Checked: %u / %u",
        static_cast<unsigned>(normal), static_cast<unsigned>(glitched),
        static_cast<unsigned>(snapshot->checked.size()), static_cast<unsigned>(snapshot->active.size()));
    if (snapshot->received > client.GetAppliedItemCount()) {
        ImGui::TextWrapped("AP has delivered %llu items; %llu are applied to this save. "
            "This list uses the AP received inventory, as Universal Tracker does.",
            static_cast<unsigned long long>(snapshot->received),
            static_cast<unsigned long long>(client.GetAppliedItemCount()));
    }
    // ID-to-area mapping is used ONLY to sort/highlight the player's scene area.
    // Missing mapping does not hide a check or change its logical availability.
    const bool areaMappingsReady = client.PrepareCheckFinderMappings();
    const auto here = GetCheckArea();
    const int current = here >= RCAREA_KOKIRI_FOREST && here < RCAREA_INVALID ? static_cast<int>(here) : -1;
    if (current >= 0)
        ImGui::Text("Current area: %s", RandomizerCheckObjects::GetRCAreaName(here).c_str());
    static bool currentFirst = true;
    static bool onlyCurrent = false;
    static ImGuiTextFilter filter;
    ImGui::Checkbox("Current area first", &currentFirst);
    ImGui::SameLine();
    ImGui::Checkbox("Only current area", &onlyCurrent);
    filter.Draw("Search region/check");
    if (onlyCurrent && !areaMappingsReady)
        ImGui::TextWrapped("Area labels are synchronizing; showing all regions until the mapping is ready.");
    const auto groups = SohExtreme::GroupTrackerRows(*snapshot, current, currentFirst, onlyCurrent && areaMappingsReady,
        [&](int64_t id) {
            const auto area = FinderRowArea(id, client);
            return area == RCAREA_INVALID ? -1 : static_cast<int>(area);
        }, [&](const SohExtreme::TrackerRow& row) {
            const std::string text = row.region + " | " + row.name;
            return filter.PassFilter(text.c_str());
        });
    ImGui::Separator();
    if (ImGui::BeginChild("SOHExtremeUTRegions", ImVec2(0, 0), false)) {
        if (groups.empty()) ImGui::TextUnformatted("No remaining in-logic checks match this view.");
        for (const auto& group : groups) {
            // Stable region identity preserves expand/collapse state as item
            // counts change or the current-area groups move to the top.
            ImGui::PushID(group.region.c_str());
            const std::string label = (group.currentArea ? "[Current area] " : "") + group.region +
                " (" + std::to_string(group.normal) + " in logic, " + std::to_string(group.glitched) + " glitched)###APRegion";
            if (ImGui::CollapsingHeader(label.c_str(), ImGuiTreeNodeFlags_DefaultOpen)) {
                ImGui::Indent();
                for (const auto* row : group.rows) {
                    const std::string line = (row->state == 2 ? "[Glitched] " : "") + row->name;
                    ImGui::TextUnformatted(line.c_str());
                    if (ImGui::IsItemHovered()) {
                        ImGui::BeginTooltip();
                        ImGui::Text("AP location ID: %lld", static_cast<long long>(row->id));
                        ImGui::TextUnformatted(row->region.c_str());
                        ImGui::EndTooltip();
                    }
                }
                ImGui::Unindent();
            }
            ImGui::PopID();
        }
    }
    ImGui::EndChild();
}

void CheckTrackerWindow::DrawElement() {
    Color_Background = CVarGetColor(CVAR_TRACKER_CHECK("BgColor.Value"), Color_Bg_Default);
    Color_Area_Incomplete_Main = CVarGetColor(CVAR_TRACKER_CHECK("AreaIncomplete.MainColor.Value"), Color_Main_Default);
    Color_Area_Incomplete_Extra =
        CVarGetColor(CVAR_TRACKER_CHECK("AreaIncomplete.ExtraColor.Value"), Color_Area_Incomplete_Extra_Default);
    Color_Area_Complete_Main = CVarGetColor(CVAR_TRACKER_CHECK("AreaComplete.MainColor.Value"), Color_Main_Default);
    Color_Area_Complete_Extra =
        CVarGetColor(CVAR_TRACKER_CHECK("AreaComplete.ExtraColor.Value"), Color_Area_Complete_Extra_Default);
    Color_Unchecked_Main = CVarGetColor(CVAR_TRACKER_CHECK("Unchecked.MainColor.Value"), Color_Main_Default);
    Color_Unchecked_Extra =
        CVarGetColor(CVAR_TRACKER_CHECK("Unchecked.ExtraColor.Value"), Color_Unchecked_Extra_Default);
    Color_Skipped_Main = CVarGetColor(CVAR_TRACKER_CHECK("Skipped.MainColor.Value"), Color_Main_Default);
    Color_Skipped_Extra = CVarGetColor(CVAR_TRACKER_CHECK("Skipped.ExtraColor.Value"), Color_Skipped_Extra_Default);
    Color_Seen_Main = CVarGetColor(CVAR_TRACKER_CHECK("Seen.MainColor.Value"), Color_Main_Default);
    Color_Seen_Extra = CVarGetColor(CVAR_TRACKER_CHECK("Seen.ExtraColor.Value"), Color_Seen_Extra_Default);
    Color_Hinted_Main = CVarGetColor(CVAR_TRACKER_CHECK("Hinted.MainColor.Value"), Color_Main_Default);
    Color_Hinted_Extra = CVarGetColor(CVAR_TRACKER_CHECK("Hinted.ExtraColor.Value"), Color_Hinted_Extra_Default);
    Color_Collected_Main = CVarGetColor(CVAR_TRACKER_CHECK("Collected.MainColor.Value"), Color_Main_Default);
    Color_Collected_Extra =
        CVarGetColor(CVAR_TRACKER_CHECK("Collected.ExtraColor.Value"), Color_Collected_Extra_Default);
    Color_Scummed_Main = CVarGetColor(CVAR_TRACKER_CHECK("Scummed.MainColor.Value"), Color_Main_Default);
    Color_Scummed_Extra = CVarGetColor(CVAR_TRACKER_CHECK("Scummed.ExtraColor.Value"), Color_Scummed_Extra_Default);
    Color_Saved_Main = CVarGetColor(CVAR_TRACKER_CHECK("Saved.MainColor.Value"), Color_Main_Default);
    Color_Saved_Extra = CVarGetColor(CVAR_TRACKER_CHECK("Saved.ExtraColor.Value"), Color_Saved_Extra_Default);
    hideUnchecked = CVarGetInteger(CVAR_TRACKER_CHECK("Unchecked.Hide"), 0);
    hideScummed = CVarGetInteger(CVAR_TRACKER_CHECK("Scummed.Hide"), 0);
    hideSeen = CVarGetInteger(CVAR_TRACKER_CHECK("Seen.Hide"), 0);
    hideSkipped = CVarGetInteger(CVAR_TRACKER_CHECK("Skipped.Hide"), 0);
    hideSaved = CVarGetInteger(CVAR_TRACKER_CHECK("Saved.Hide"), 0);
    hideCollected = CVarGetInteger(CVAR_TRACKER_CHECK("Collected.Hide"), 0);
    showHidden = CVarGetInteger(CVAR_TRACKER_CHECK("ShowHidden"), 0);
    mystery = CVarGetInteger(CVAR_RANDOMIZER_ENHANCEMENT("MysteriousShuffle"), 0);
    showLogicTooltip = CVarGetInteger(CVAR_TRACKER_CHECK("ShowLogic"), 0);
    enableAvailableChecks = CVarGetInteger(CVAR_TRACKER_CHECK("EnableAvailableChecks"), 0);
    onlyShowAvailable = CVarGetInteger(CVAR_TRACKER_CHECK("OnlyShowAvailable"), 0);

    hideShopUnshuffledChecks = CVarGetInteger(CVAR_TRACKER_CHECK("HideUnshuffledShopChecks"), 0);
    alwaysShowGS = CVarGetInteger(CVAR_TRACKER_CHECK("AlwaysShowGSLocs"), 0);
    if (CVarGetInteger(CVAR_TRACKER_CHECK("WindowType"), TRACKER_WINDOW_WINDOW) == TRACKER_WINDOW_FLOATING) {
        if (CVarGetInteger(CVAR_TRACKER_CHECK("ShowOnlyPaused"), 0) &&
            (gPlayState == nullptr || gPlayState->pauseCtx.state == 0)) {
            return;
        }

        if (CVarGetInteger(CVAR_TRACKER_CHECK("DisplayType"), TRACKER_DISPLAY_ALWAYS) == TRACKER_DISPLAY_COMBO_BUTTON) {
            int comboButton1Mask = buttons[CVarGetInteger(CVAR_TRACKER_CHECK("ComboButton1"), TRACKER_COMBO_BUTTON_L)];
            int comboButton2Mask = buttons[CVarGetInteger(CVAR_TRACKER_CHECK("ComboButton2"), TRACKER_COMBO_BUTTON_R)];
            OSContPad* trackerButtonsPressed =
                std::dynamic_pointer_cast<LUS::ControlDeck>(Ship::Context::GetRawInstance()->GetControlDeck())
                    ->GetPads();
            bool comboButtonsHeld = trackerButtonsPressed != nullptr &&
                                    trackerButtonsPressed[0].button & comboButton1Mask &&
                                    trackerButtonsPressed[0].button & comboButton2Mask;
            if (!comboButtonsHeld) {
                return;
            }
        }
    }

    if (presetLoaded) {
        ImGui::SetNextWindowSize(presetSize);
        ImGui::SetNextWindowPos(presetPos);
        presetLoaded = false;
    } else {
        ImGui::SetNextWindowSize(ImVec2(400, 540), ImGuiCond_FirstUseEver);
    }
    if (Trackers::BeginFloatWindows(
            "Check Tracker", &mIsVisible, Color_Background,
            static_cast<TrackerWindowType>(CVarGetInteger(CVAR_TRACKER_CHECK("WindowType"), TRACKER_WINDOW_WINDOW)),
            CVarGetInteger(CVAR_TRACKER_CHECK("Draggable"), 1), ImGuiWindowFlags_NoScrollbar)) {
        if (!GameInteractor::IsSaveLoaded() || !initialized) {
            ImGui::Text("Waiting for file load..."); // TODO Language
            Trackers::EndFloatWindows();
            return;
        }

        if (Archipelago_IsCurrentSaveActive() && (enableAvailableChecks || onlyShowAvailable)) {
            // AP mode displays UT's actual evaluated IDs, not a second solver.
            // Normal standalone-randomizer tracking is unchanged.
            recalculateAvailable = false;
            DrawUniversalFinderMirror();
            Trackers::EndFloatWindows();
            return;
        }

        if (recalculateAvailable) {
            recalculateAvailable = false;
            InternalRecalculateAvailableChecks(availableChecksStartingRegion, availableChecksStartingAgeTime);
            availableChecksStartingRegion = RR_ROOT;
            availableChecksStartingAgeTime = RAT_NONE;
        }

        // Quick Options
#ifdef __WIIU__
        float headerHeight = 40.0f;
#else
        float headerHeight = 20.0f;
#endif
        if (!ImGui::BeginTable("Check Tracker", 1, 0)) {
            Trackers::EndFloatWindows();
            return;
        }

        ImGui::SetWindowFontScale(CVarGetFloat(CVAR_TRACKER_CHECK("FontSize"), 1.0f));

        ImGui::TableNextRow(0, 0);
        ImGui::TableNextColumn();
        if (CVarGetInteger(CVAR_TRACKER_CHECK("HiddenItemsToggleVisible"), 1) &&
            UIWidgets::CVarCheckbox(
                "Show Hidden Items", CVAR_TRACKER_CHECK("ShowHidden"),
                UIWidgets::CheckboxOptions(
                    { { .tooltip =
                            "When active, items will show hidden checks by default when updated to this state." } })
                    .Color(THEME_COLOR))) {
            doAreaScroll = true;
            showHidden = CVarGetInteger(CVAR_TRACKER_CHECK("ShowHidden"), 0);
            RecalculateAllAreaTotals();
        }
        if (CVarGetInteger(CVAR_TRACKER_CHECK("AvailableChecksToggleVisible"), 1)) {
            if (UIWidgets::CVarCheckbox(
                    "Only Show Available Checks", CVAR_TRACKER_CHECK("OnlyShowAvailable"),
                    UIWidgets::CheckboxOptions(
                        { { .tooltip =
                                "When active, unavailable checks are hidden. Turning this on also enables "
                                "SOH-EXTREME logic-based Available Checks." } })
                        .Color(THEME_COLOR))) {
                doAreaScroll = true;
                onlyShowAvailable = CVarGetInteger(CVAR_TRACKER_CHECK("OnlyShowAvailable"), 0);

                if (onlyShowAvailable && !CVarGetInteger(CVAR_TRACKER_CHECK("EnableAvailableChecks"), 0)) {
                    CVarSetInteger(CVAR_TRACKER_CHECK("EnableAvailableChecks"), 1);
                    enableAvailableChecks = true;
                }

                if (enableAvailableChecks) {
                    RecalculateAvailableChecks();
                } else {
                    RecalculateAllAreaTotals();
                }
            }
        }
        if (Archipelago_IsCurrentSaveActive()) {
            if (UIWidgets::Button("Reload Checks", UIWidgets::ButtonOptions().Color(THEME_COLOR))) {
                Archipelago_PrepareCheckFinderMappings();
                recalculateAvailable = true;
                availableChecksStartingRegion = RR_ROOT;
                availableChecksStartingAgeTime = RAT_NONE;
                doAreaScroll = true;
                SPDLOG_INFO("[Archipelago] Check Finder manual reload requested");
            }
            ImGui::SameLine();
            UIWidgets::Tooltip("Re-read AP mappings and recalculate reachable checks, including NPC Speech checks.");
        }
        if (CVarGetInteger(CVAR_TRACKER_CHECK("ExpandCollapseButtonsVisible"), 0)) {
            if (UIWidgets::Button("Expand All", UIWidgets::ButtonOptions()
                                                    .Color(THEME_COLOR)
                                                    .Size({ ImGui::GetContentRegionAvail().x / 2 - 6, 0 }))) {
                optCollapseAll = false;
                optExpandAll = true;
                doAreaScroll = true;
            }
            ImGui::SameLine();
            if (UIWidgets::Button(
                    "Collapse All",
                    UIWidgets::ButtonOptions().Color(THEME_COLOR).Size({ ImGui::GetContentRegionAvail().x - 6, 0 }))) {
                optExpandAll = false;
                optCollapseAll = true;
            }
        }
        UIWidgets::PushStyleCombobox(THEME_COLOR);
        if (CVarGetInteger(CVAR_TRACKER_CHECK("SearchInputVisible"), 1)) {
            if (checkSearch.Draw("", ImGui::GetContentRegionAvail().x - 42)) {
                UpdateFilters();
            }
            std::string checkSearchText = checkSearch.InputBuf;
            checkSearchText.erase(std::remove(checkSearchText.begin(), checkSearchText.end(), ' '),
                                  checkSearchText.end());
            ImGui::SameLine();
            if (UIWidgets::Button(ICON_FA_ERASER, UIWidgets::ButtonOptions()
                                                      .Size(UIWidgets::Sizes::Inline)
                                                      .Color(THEME_COLOR)
                                                      .Padding(ImVec2(10.f, 6.f)))) {
                checkSearch.Clear();
                UpdateFilters();
                doAreaScroll = true;
            }
            if (checkSearchText.length() < 1) {
                ImGui::SameLine(20.0f);
                ImGui::TextColored(ImVec4(1.0f, 1.0f, 1.0f, 0.4f), "Search...");
            }
        }
        UIWidgets::PopStyleCombobox();

        if (CVarGetInteger(CVAR_TRACKER_CHECK("CheckTotalsVisible"), 1)) {
            std::ostringstream totalChecksSS;
            totalChecksSS << "";
            if (enableAvailableChecks) {
                totalChecksSS << totalChecksAvailable << " Available / ";
            }
            totalChecksSS << totalChecksGotten << " Checked / " << totalChecks << " Total";
            ImGui::Text("%s", totalChecksSS.str().c_str());
        }

        bool headerPresent =
            CVarGetInteger(CVAR_TRACKER_CHECK("HiddenItemsToggleVisible"), 1) ||
            (enableAvailableChecks && CVarGetInteger(CVAR_TRACKER_CHECK("AvailableChecksToggleVisible"), 1)) ||
            CVarGetInteger(CVAR_TRACKER_CHECK("ExpandCollapseButtonsVisible"), 0) ||
            CVarGetInteger(CVAR_TRACKER_CHECK("SearchInputVisible"), 1) ||
            CVarGetInteger(CVAR_TRACKER_CHECK("CheckTotalsVisible"), 1);
        if (headerPresent) {
            ImGui::Separator();
        }

        // Checks Section Lead-in
        ImGui::TableNextRow();
        ImGui::TableNextColumn();
        if (!ImGui::BeginTable("CheckTracker##Checks", 1, ImGuiTableFlags_ScrollY)) {
            ImGui::EndTable();
            Trackers::EndFloatWindows();
            return;
        }
        ImGui::TableNextRow();
        ImGui::TableNextColumn();

        // Prep for loop
        RainbowTick();
        bool doDraw = false;
        bool thisAreaFullyChecked = false;
        bool mqSpoilers = CVarGetInteger(CVAR_TRACKER_CHECK("MQSpoilers"), 0);
        bool hideIncomplete = CVarGetInteger(CVAR_TRACKER_CHECK("AreaIncomplete.Hide"), 0);
        bool hideComplete = CVarGetInteger(CVAR_TRACKER_CHECK("AreaComplete.Hide"), 0);
        bool collapseLogic;
        bool doingCollapseOrExpand = optExpandAll || optCollapseAll;
        bool isThisAreaSpoiled;
        RandomizerCheckArea lastArea = RCAREA_INVALID;
        Color_RGBA8 mainColor;
        Color_RGBA8 extraColor;
        std::string stemp;

        bool shouldHideFilteredAreas = CVarGetInteger(CVAR_TRACKER_CHECK("HideFilteredAreas"), 1);

        ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, ImVec2(4.0f, 3.0f));
        for (auto& [rcArea, checks] : checksByArea) {
            RandomizerCheckArea thisArea = currentArea;

            thisAreaFullyChecked = (areaChecksGotten[rcArea] == areaCheckTotals[rcArea]);
            // Last Area needs to be cleaned up
            if (lastArea != RCAREA_INVALID && doDraw) {
                UIWidgets::PaddedSeparator();
            }
            lastArea = rcArea;
            if (previousShowHidden != showHidden) {
                previousShowHidden = showHidden;
                doAreaScroll = true;
            }
            if ((shouldHideFilteredAreas && filterAreasHidden[rcArea]) ||
                (!showHidden &&
                 ((hideComplete && thisAreaFullyChecked) || (hideIncomplete && !thisAreaFullyChecked))) ||
                (enableAvailableChecks && onlyShowAvailable && areaChecksAvailable[rcArea] == 0)) {
                doDraw = false;
            } else {
                // Get the colour for the area
                if (thisAreaFullyChecked) {
                    mainColor = Color_Area_Complete_Main;
                    extraColor = Color_Area_Complete_Extra;
                } else {
                    mainColor = Color_Area_Incomplete_Main;
                    extraColor = Color_Area_Incomplete_Extra;
                }

                // Draw the area
                collapseLogic = !thisAreaFullyChecked;
                if (doingCollapseOrExpand) {
                    if (optExpandAll) {
                        collapseLogic = true;
                    } else if (optCollapseAll) {
                        collapseLogic = false;
                    }
                }
                stemp = RandomizerCheckObjects::GetRCAreaName(rcArea) + "##TreeNode";
                ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(mainColor.r / 255.0f, mainColor.g / 255.0f,
                                                            mainColor.b / 255.0f, mainColor.a / 255.0f));
                if (doingCollapseOrExpand) {
                    ImGui::SetNextItemOpen(collapseLogic, ImGuiCond_Always);
                } else {
                    ImGui::SetNextItemOpen(!thisAreaFullyChecked, ImGuiCond_Once);
                }
                doDraw = ImGui::TreeNodeEx(stemp.c_str(), ImGuiTreeNodeFlags_NoTreePushOnOpen);
                ImGui::PopStyleColor();
                ImGui::SameLine();
                ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(extraColor.r / 255.0f, extraColor.g / 255.0f,
                                                            extraColor.b / 255.0f, extraColor.a / 255.0f));

                isThisAreaSpoiled = IsAreaSpoiled(rcArea) || mqSpoilers;

                if (isThisAreaSpoiled) {
                    std::ostringstream areaTotalsSS;
                    std::ostringstream areaTotalsTooltipSS;

                    areaTotalsSS << "(";
                    if (enableAvailableChecks) {
                        areaTotalsSS << static_cast<uint16_t>(areaChecksAvailable[rcArea]) << " / ";
                        areaTotalsTooltipSS << "Available / ";
                    }
                    areaTotalsSS << static_cast<uint16_t>(areaChecksGotten[rcArea]) << " / "
                                 << static_cast<uint16_t>(areaCheckTotals[rcArea]) << ")";
                    areaTotalsTooltipSS << "Checked / Total";

                    if (showVOrMQ && RandomizerCheckObjects::AreaIsDungeon(rcArea)) {
                        if (OTRGlobals::Instance->gRandoContext->GetDungeonFromScene(DungeonSceneLookupByArea(rcArea))
                                ->IsMQ()) {
                            areaTotalsSS << " - MQ";
                        } else {
                            areaTotalsSS << " - Vanilla";
                        }
                    }

                    ImGui::Text("%s", areaTotalsSS.str().c_str());
                    UIWidgets::Tooltip(areaTotalsTooltipSS.str().c_str());
                } else {
                    ImGui::Text("???");
                }

                ImGui::PopStyleColor();

                // Keep areas loaded between transitions
                if (thisArea == rcArea && doAreaScroll) {
                    ImGui::SetScrollHereY(0.0f);
                    doAreaScroll = false;
                }
                for (auto rc : checks) {
                    if (doDraw && isThisAreaSpoiled && !filterChecksHidden[rc]) {
                        DrawLocation(rc);
                    }
                }
                if (doDraw && isThisAreaSpoiled && Archipelago_IsCurrentSaveActive()) {
                    for (const auto& entry : kNpcSpeechFinderEntries) {
                        if (IsNpcSpeechVisible(entry) && GetNpcSpeechArea(entry) == rcArea) {
                            DrawNpcSpeechLocation(entry);
                        }
                    }
                    for (size_t enemyIndex = 0; enemyIndex < kEnemyDefeatFinderEntryCount; ++enemyIndex) {
                        const auto& entry = kEnemyDefeatFinderEntries[enemyIndex];
                        if (IsEnemyDefeatVisible(entry) && entry.area == rcArea) {
                            DrawEnemyDefeatLocation(entry);
                        }
                    }
                }
            }
        }
        ImGui::PopStyleVar();

        ImGui::EndTable(); // Checks Lead-out
        ImGui::EndTable(); // Quick Options Lead-out
        if (doingCollapseOrExpand) {
            optCollapseAll = false;
            optExpandAll = false;
        }
    }
    Trackers::EndFloatWindows();
}

bool UpdateFilters() {
    for (auto& [rcArea, checks] : checksByArea) {
        filterAreasHidden[rcArea] = !checkSearch.PassFilter(RandomizerCheckObjects::GetRCAreaName(rcArea).c_str());
        for (auto check : checks) {
            if (ShouldShowCheck(check)) {
                filterAreasHidden[rcArea] = false;
                filterChecksHidden[check] = false;
            } else {
                filterChecksHidden[check] = true;
            }
        }
        if (Archipelago_IsCurrentSaveActive()) {
            for (const auto& entry : kNpcSpeechFinderEntries) {
                if (!IsNpcSpeechVisible(entry) || GetNpcSpeechArea(entry) != rcArea) {
                    continue;
                }
                auto* loc = Rando::StaticData::GetLocation(static_cast<RandomizerCheck>(entry.rc));
                if (loc != nullptr) {
                    const std::string speechName = "NPC Speech: " + loc->GetShortName();
                    if (checkSearch.PassFilter(speechName.c_str())) {
                        filterAreasHidden[rcArea] = false;
                    }
                }
            }
            for (size_t enemyIndex = 0; enemyIndex < kEnemyDefeatFinderEntryCount; ++enemyIndex) {
                const auto& entry = kEnemyDefeatFinderEntries[enemyIndex];
                if (IsEnemyDefeatVisible(entry) && entry.area == rcArea && checkSearch.PassFilter(entry.name)) {
                    filterAreasHidden[rcArea] = false;
                }
            }
        }
    }

    return true;
}

bool ShouldShowCheck(RandomizerCheck check) {
    auto itemLoc = Rando::Context::GetInstance()->GetItemLocation(check);
    std::string search = (Rando::StaticData::GetLocation(check)->GetShortName() + " " +
                          Rando::StaticData::GetLocation(check)->GetName() + " " +
                          RandomizerCheckObjects::GetRCAreaName(Rando::StaticData::GetLocation(check)->GetArea()));
    if (itemLoc->HasObtained() || itemLoc->GetCheckStatus() == RCSHOW_SCUMMED ||
        (!mystery &&
         (itemLoc->GetCheckStatus() == RCSHOW_IDENTIFIED || itemLoc->GetCheckStatus() == RCSHOW_SEEN_OR_HINTED) &&
         itemLoc->GetPlacedRandomizerGet() != RG_ICE_TRAP)) {
        search += " " + itemLoc->GetPlacedItemName().GetForLanguage(gSaveContext.language);
    } else if (itemLoc->GetCheckStatus() == RCSHOW_IDENTIFIED && !mystery) {
        search +=
            OTRGlobals::Instance->gRandoContext->overrides[check].GetTrickName().GetForLanguage(gSaveContext.language);
    } else if (itemLoc->GetCheckStatus() == RCSHOW_SEEN_OR_HINTED && !mystery) {
        search += Rando::StaticData::RetrieveItem(OTRGlobals::Instance->gRandoContext->overrides[check].LooksLike())
                      .GetName()
                      .GetForLanguage(gSaveContext.language);
    }
    return (IsVisibleInCheckTracker(check) &&
            (checkSearch.Filters.Size == 0 || checkSearch.PassFilter(search.c_str())));
}

void LoadSettings() {
    // If in randomzer, then get the setting and check if in general we should be showing the settings
    // If in vanilla, _try_ to show items that at least are needed for 100%

    showShops =
        IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHOPSANITY) != RO_SHOPSANITY_OFF;
    showBeans =
        !IS_RANDO ||
        OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_MERCHANTS) ==
            RO_SHUFFLE_MERCHANTS_BEANS_ONLY ||
        OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_MERCHANTS) == RO_SHUFFLE_MERCHANTS_ALL;
    showScrubs =
        IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_SCRUBS) == RO_SCRUBS_ALL;
    showMajorScrubs =
        IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_SCRUBS) != RO_SCRUBS_OFF;
    showMerchants =
        !IS_RANDO ||
        OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_MERCHANTS) ==
            RO_SHUFFLE_MERCHANTS_ALL_BUT_BEANS ||
        OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_MERCHANTS) == RO_SHUFFLE_MERCHANTS_ALL;
    showSongs =
        IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_SONGS) != RO_SONG_SHUFFLE_OFF;
    showBeehives =
        IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_BEEHIVES) == RO_GENERIC_YES;
    showCows = IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_COWS) == RO_GENERIC_YES;
    showAdultTrade =
        !IS_RANDO || OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_ADULT_TRADE) == RO_GENERIC_YES;
    showKokiriSword = !IS_RANDO || OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_KOKIRI_SWORD) ==
                                       RO_GENERIC_YES;
    showMasterSword = !IS_RANDO || OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_MASTER_SWORD) ==
                                       RO_GENERIC_YES;
    showHyruleLoach = IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_FISHSANITY) ==
                                      RO_FISHSANITY_HYRULE_LOACH;
    showWeirdEgg = !IS_RANDO || OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_WEIRD_EGG) ==
                                    RO_WEIRD_EGG_SHUFFLED;
    showZeldasLetter = !IS_RANDO || OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(
                                        RSK_SHUFFLE_ZELDAS_LETTER) == RO_GENERIC_YES;
    showGerudoCard = !IS_RANDO || OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(
                                      RSK_SHUFFLE_GERUDO_MEMBERSHIP_CARD) == RO_GENERIC_YES;
    showFrogSongRupees = IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(
                                         RSK_SHUFFLE_FROG_SONG_RUPEES) == RO_GENERIC_YES;
    showFountainFairies = IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(
                                          RSK_SHUFFLE_FOUNTAIN_FAIRIES) == RO_GENERIC_YES;
    showStoneFairies = IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_STONE_FAIRIES) ==
                                       RO_GENERIC_YES;
    showBeanFairies =
        IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_BEAN_FAIRIES) == RO_GENERIC_YES;
    showSongFairies =
        IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_SONG_FAIRIES) == RO_GENERIC_YES;
    showButterflyFairies = IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(
                                           RSK_SHUFFLE_BUTTERFLY_FAIRIES) == RO_GENERIC_YES;
    showStartingMapsCompasses = IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(
                                                RSK_SHUFFLE_MAPANDCOMPASS) != RO_DUNGEON_ITEM_LOC_VANILLA;
    showKeysanity = IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_KEYSANITY) !=
                                    RO_DUNGEON_ITEM_LOC_VANILLA;
    showBossKeysanity = IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_BOSS_KEYSANITY) !=
                                        RO_DUNGEON_ITEM_LOC_VANILLA;
    showGerudoFortressKeys =
        IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_GERUDO_KEYS) != RO_GERUDO_KEYS_VANILLA;
    showGanonBossKey = IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_GANONS_BOSS_KEY) !=
                                       RO_GANON_BOSS_KEY_VANILLA;
    showOcarinas =
        IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_OCARINA) == RO_GENERIC_YES;
    show100SkullReward = IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(
                                         RSK_SHUFFLE_100_GS_REWARD) == RO_GENERIC_YES;
    // don't show Link's Pocket if not randomizer, or if rando and pocket is disabled
    showLinksPocket = IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_LINKS_POCKET) !=
                                      RO_LINKS_POCKET_NOTHING;
    showChestMinigame = IS_RANDO && OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(
                                        RSK_SHUFFLE_CHEST_MINIGAME) != RO_GENERIC_OFF;

    if (IS_RANDO) {
        switch (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_TOKENS)) {
            case RO_TOKENSANITY_ALL:
                showOverworldTokens = true;
                showDungeonTokens = true;
                break;
            case RO_TOKENSANITY_OVERWORLD:
                showOverworldTokens = true;
                showDungeonTokens = false;
                break;
            case RO_TOKENSANITY_DUNGEONS:
                showOverworldTokens = false;
                showDungeonTokens = true;
                break;
            default:
                showOverworldTokens = false;
                showDungeonTokens = false;
                break;
        }

        switch (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_POTS)) {
            case RO_SHUFFLE_POTS_ALL:
                showOverworldPots = true;
                showDungeonPots = true;
                break;
            case RO_SHUFFLE_POTS_OVERWORLD:
                showOverworldPots = true;
                showDungeonPots = false;
                break;
            case RO_SHUFFLE_POTS_DUNGEONS:
                showOverworldPots = false;
                showDungeonPots = true;
                break;
            default:
                showOverworldPots = false;
                showDungeonPots = false;
                break;
        }

        switch (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_GRASS)) {
            case RO_SHUFFLE_GRASS_ALL:
                showOverworldGrass = true;
                showDungeonGrass = true;
                break;
            case RO_SHUFFLE_GRASS_OVERWORLD:
                showOverworldGrass = true;
                showDungeonGrass = false;
                break;
            case RO_SHUFFLE_GRASS_DUNGEONS:
                showOverworldGrass = false;
                showDungeonGrass = true;
                break;
            default:
                showOverworldGrass = false;
                showDungeonGrass = false;
                break;
        }

        switch (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_CRATES)) {
            case RO_SHUFFLE_CRATES_ALL:
                showOverworldCrates = true;
                showDungeonCrates = true;
                break;
            case RO_SHUFFLE_CRATES_OVERWORLD:
                showOverworldCrates = true;
                showDungeonCrates = false;
                break;
            case RO_SHUFFLE_CRATES_DUNGEONS:
                showOverworldCrates = false;
                showDungeonCrates = true;
                break;
            default:
                showOverworldCrates = false;
                showDungeonCrates = false;
                break;
        }

        showRocks = OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_ROCKS);
        switch (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_BOULDERS)) {
            case RO_SHUFFLE_BOULDERS_ALL:
                showOverworldBoulders = true;
                showDungeonBoulders = true;
                break;
            case RO_SHUFFLE_BOULDERS_OVERWORLD:
                showOverworldBoulders = true;
                showDungeonBoulders = false;
                break;
            case RO_SHUFFLE_BOULDERS_DUNGEONS:
                showOverworldBoulders = false;
                showDungeonBoulders = true;
                break;
            default:
                showOverworldBoulders = false;
                showDungeonBoulders = false;
                break;
        }

        switch (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_SIGNS)) {
            case RO_SHUFFLE_SIGNS_ALL:
                showOverworldSigns = true;
                showDungeonSigns = true;
                break;
            case RO_SHUFFLE_SIGNS_OVERWORLD:
                showOverworldSigns = true;
                showDungeonSigns = false;
                break;
            case RO_SHUFFLE_SIGNS_DUNGEONS:
                showOverworldSigns = false;
                showDungeonSigns = true;
                break;
            default:
                showOverworldSigns = false;
                showDungeonSigns = false;
                break;
        }

        showTrees = OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_TREES);
        showBushes = OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_BUSHES) ||
                     showOverworldGrass;

        switch (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_WONDER_ITEMS)) {
            case RO_SHUFFLE_WONDER_ITEMS_ALL:
                showOverworldWonderItems = true;
                showDungeonWonderItems = true;
                break;
            case RO_SHUFFLE_WONDER_ITEMS_OVERWORLD:
                showOverworldWonderItems = true;
                showDungeonWonderItems = false;
                break;
            case RO_SHUFFLE_WONDER_ITEMS_DUNGEONS:
                showOverworldWonderItems = false;
                showDungeonWonderItems = true;
                break;
            default:
                showOverworldWonderItems = false;
                showDungeonWonderItems = false;
                break;
        }
        showBeggar = OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_BEGGAR);
        showIcicles = OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_ICICLES);
        showRedIce = OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_RED_ICE);
    } else { // Vanilla
        showOverworldTokens = true;
        showDungeonTokens = true;
        showOverworldPots = false;
        showDungeonPots = false;
        showOverworldGrass = false;
        showDungeonGrass = false;
        showOverworldCrates = false;
        showDungeonCrates = false;
        showRocks = false;
        showOverworldBoulders = false;
        showDungeonBoulders = false;
        showTrees = false;
        showBushes = false;
        showOverworldWonderItems = false;
        showDungeonWonderItems = false;
        showOverworldSigns = false;
        showDungeonSigns = false;
        showBeggar = false;
        showIcicles = false;
        showRedIce = false;
    }

    fortressFast = false;
    fortressNormal = false;
    switch (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_GERUDO_FORTRESS)) {
        case RO_GF_CARPENTERS_FREE:
            showGerudoFortressKeys = false;
            showGerudoCard = false;
            break;
        case RO_GF_CARPENTERS_FAST:
            fortressFast = true;
            break;
        case RO_GF_CARPENTERS_NORMAL:
            fortressNormal = true;
            break;
    }

    fishsanityMode = OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_FISHSANITY);
    fishsanityPondCount = OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_FISHSANITY_POND_COUNT);
    fishsanityAgeSplit = OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_FISHSANITY_AGE_SPLIT);

    if (IS_RANDO) {
        switch (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_FREESTANDING)) {
            case RO_SHUFFLE_FREESTANDING_ALL:
                showOverworldFreestanding = true;
                showDungeonFreestanding = true;
                break;
            case RO_SHUFFLE_FREESTANDING_OVERWORLD:
                showOverworldFreestanding = true;
                showDungeonFreestanding = false;
                break;
            case RO_SHUFFLE_FREESTANDING_DUNGEONS:
                showOverworldFreestanding = false;
                showDungeonFreestanding = true;
                break;
            default:
                showOverworldFreestanding = false;
                showDungeonFreestanding = false;
                break;
        }

        showSilver = OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SHUFFLE_SILVER);
    } else { // Vanilla
        showOverworldFreestanding = false;
        showDungeonFreestanding = true;
    }

    switch (OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_GANONS_BOSS_KEY)) {
        case RO_GANON_BOSS_KEY_STONES:
            Rando::Context::GetInstance()->GBKCondition(RO_CHECK_TRIGGER_STONES);
            break;
        case RO_GANON_BOSS_KEY_MEDALLIONS:
            Rando::Context::GetInstance()->GBKCondition(RO_CHECK_TRIGGER_MEDALLIONS);
            break;
        case RO_GANON_BOSS_KEY_REWARDS:
            Rando::Context::GetInstance()->GBKCondition(RO_CHECK_TRIGGER_REWARDS);
            break;
        case RO_GANON_BOSS_KEY_DUNGEONS:
            Rando::Context::GetInstance()->GBKCondition(RO_CHECK_TRIGGER_DUNGEONS);
            break;
        case RO_GANON_BOSS_KEY_TOKENS:
            Rando::Context::GetInstance()->GBKCondition(RO_CHECK_TRIGGER_TOKENS);
            break;
        default:
            Rando::Context::GetInstance()->GBKCondition(RO_CHECK_TRIGGER_NONE);
            break;
    }
}

bool IsCheckShuffled(RandomizerCheck rc) {
    Rando::Location* loc = Rando::StaticData::GetLocation(rc);
    if (IS_RANDO) {
        return (loc->GetArea() != RCAREA_INVALID) &&        // don't show Invalid locations
               (loc->GetRCType() != RCTYPE_GOSSIP_STONE) && // TODO: Don't show hints until tracker supports them
               (loc->GetRCType() != RCTYPE_STATIC_HINT) &&  // TODO: Don't show hints until tracker supports them
               (loc->GetRCType() != RCTYPE_CHEST_GAME || showChestMinigame) &&
               (rc != RC_HC_ZELDAS_LETTER || showZeldasLetter) && (rc != RC_LINKS_POCKET || showLinksPocket) &&
               OTRGlobals::Instance->gRandoContext->IsQuestOfLocationActive(rc) &&
               (loc->GetRCType() != RCTYPE_SHOP ||
                (showShops &&
                 OTRGlobals::Instance->gRandomizer->IdentifyShopItem(loc->GetScene(), loc->GetActorParams() + 1)
                         .enGirlAShopItem == 50)) &&
               (rc != RC_WINCON) && (rc != RC_GANON) &&
               (loc->GetRCType() != RCTYPE_SCRUB || showScrubs ||
                (showMajorScrubs && (rc == RC_LW_DEKU_SCRUB_NEAR_BRIDGE || // The 3 scrubs that are always randomized
                                     rc == RC_HF_DEKU_SCRUB_GROTTO || rc == RC_LW_DEKU_SCRUB_GROTTO_FRONT))) &&
               ((loc->GetRCType() != RCTYPE_MERCHANT || (showMerchants && rc != RC_ZR_MAGIC_BEAN_SALESMAN)) ||
                (rc == RC_ZR_MAGIC_BEAN_SALESMAN && showBeans)) &&
               (loc->GetRCType() != RCTYPE_BEGGAR || showBeggar) &&
               (loc->GetRCType() != RCTYPE_SONG_LOCATION || showSongs) &&
               (loc->GetRCType() != RCTYPE_BEEHIVE || showBeehives) &&
               (loc->GetRCType() != RCTYPE_OCARINA || showOcarinas) &&
               (loc->GetRCType() != RCTYPE_SKULL_TOKEN || alwaysShowGS ||
                (showOverworldTokens && RandomizerCheckObjects::AreaIsOverworld(loc->GetArea())) ||
                (showDungeonTokens && RandomizerCheckObjects::AreaIsDungeon(loc->GetArea()))) &&
               (loc->GetRCType() != RCTYPE_POT ||
                (showOverworldPots && RandomizerCheckObjects::AreaIsOverworld(loc->GetArea())) ||
                (showDungeonPots && RandomizerCheckObjects::AreaIsDungeon(loc->GetArea()))) &&
               (loc->GetRCType() != RCTYPE_GRASS ||
                (showOverworldGrass && RandomizerCheckObjects::AreaIsOverworld(loc->GetArea())) ||
                (showDungeonGrass && RandomizerCheckObjects::AreaIsDungeon(loc->GetArea()))) &&
               (loc->GetRCType() != RCTYPE_CRATE ||
                (showOverworldCrates && RandomizerCheckObjects::AreaIsOverworld(loc->GetArea())) ||
                (showDungeonCrates && RandomizerCheckObjects::AreaIsDungeon(loc->GetArea()))) &&
               (loc->GetRCType() != RCTYPE_NLCRATE ||
                (showOverworldCrates && RandomizerCheckObjects::AreaIsOverworld(loc->GetArea()) &&
                 OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_LOGIC_RULES) == RO_LOGIC_NO_LOGIC) ||
                (showDungeonCrates && RandomizerCheckObjects::AreaIsDungeon(loc->GetArea()))) &&
               (loc->GetRCType() != RCTYPE_SMALL_CRATE ||
                (showOverworldCrates && RandomizerCheckObjects::AreaIsOverworld(loc->GetArea())) ||
                (showDungeonCrates && RandomizerCheckObjects::AreaIsDungeon(loc->GetArea()))) &&
               (loc->GetRCType() != RCTYPE_ROCK || showRocks) &&
               (loc->GetRCType() != RCTYPE_BOULDER ||
                (showOverworldBoulders && RandomizerCheckObjects::AreaIsOverworld(loc->GetArea())) ||
                (showDungeonBoulders && RandomizerCheckObjects::AreaIsDungeon(loc->GetArea()))) &&
               (loc->GetRCType() != RCTYPE_TREE || showTrees) &&
               (loc->GetRCType() != RCTYPE_NLTREE ||
                (showTrees &&
                 OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_LOGIC_RULES) == RO_LOGIC_NO_LOGIC)) &&
               (loc->GetRCType() != RCTYPE_BUSH || showBushes) && (loc->GetRCType() != RCTYPE_COW || showCows) &&
               (loc->GetRCType() != RCTYPE_SIGN ||
                (showOverworldSigns && RandomizerCheckObjects::AreaIsOverworld(loc->GetArea())) ||
                (showDungeonSigns && RandomizerCheckObjects::AreaIsDungeon(loc->GetArea()))) &&
               (loc->GetRCType() != RCTYPE_WONDER_ITEM ||
                (showOverworldWonderItems && RandomizerCheckObjects::AreaIsOverworld(loc->GetArea())) ||
                (showDungeonWonderItems && RandomizerCheckObjects::AreaIsDungeon(loc->GetArea()))) &&
               (loc->GetRCType() != RCTYPE_ICICLE || showIcicles) &&
               (loc->GetRCType() != RCTYPE_RED_ICE || showRedIce) &&
               (loc->GetRCType() != RCTYPE_FISH || Rando::Fishsanity::GetFishLocationIncluded(loc)) &&
               (loc->GetRCType() != RCTYPE_FREESTANDING ||
                (showOverworldFreestanding && RandomizerCheckObjects::AreaIsOverworld(loc->GetArea())) ||
                (showDungeonFreestanding && RandomizerCheckObjects::AreaIsDungeon(loc->GetArea()))) &&
               (loc->GetRCType() != RCTYPE_SILVER || showSilver) &&
               (loc->GetRCType() != RCTYPE_ADULT_TRADE || showAdultTrade ||
                rc == RC_KAK_ANJU_AS_ADULT ||  // adult trade checks that are always shuffled
                rc == RC_DMT_TRADE_CLAIM_CHECK // even when shuffle adult trade is off
                ) &&
               (rc != RC_KF_KOKIRI_SWORD_CHEST || showKokiriSword) && (rc != RC_TOT_MASTER_SWORD || showMasterSword) &&
               (rc != RC_LH_HYRULE_LOACH || showHyruleLoach) && (rc != RC_HC_MALON_EGG || showWeirdEgg) &&
               (loc->GetRCType() != RCTYPE_FROG_SONG || showFrogSongRupees) &&
               ((loc->GetRCType() != RCTYPE_MAP && loc->GetRCType() != RCTYPE_COMPASS) || showStartingMapsCompasses) &&
               (loc->GetRCType() != RCTYPE_FOUNTAIN_FAIRY || showFountainFairies) &&
               (loc->GetRCType() != RCTYPE_STONE_FAIRY || showStoneFairies) &&
               (loc->GetRCType() != RCTYPE_BEAN_FAIRY || showBeanFairies) &&
               (loc->GetRCType() != RCTYPE_SONG_FAIRY || showSongFairies) &&
               (loc->GetRCType() != RCTYPE_BUTTERFLY_FAIRY || showButterflyFairies) &&
               (loc->GetRCType() != RCTYPE_SMALL_KEY || showKeysanity) &&
               (loc->GetRCType() != RCTYPE_BOSS_KEY || showBossKeysanity) &&
               (loc->GetRCType() != RCTYPE_GANON_BOSS_KEY || showGanonBossKey) &&
               (rc != RC_KAK_100_GOLD_SKULLTULA_REWARD || show100SkullReward) &&
               (loc->GetRCType() != RCTYPE_GF_KEY && rc != RC_TH_FREED_CARPENTERS ||
                (showGerudoCard && rc == RC_TH_FREED_CARPENTERS) ||
                (fortressNormal && showGerudoFortressKeys && loc->GetRCType() == RCTYPE_GF_KEY) ||
                (fortressFast && showGerudoFortressKeys && rc == RC_TH_1_TORCH_CARPENTER));
    } else if (loc->IsVanillaCompletion()) {
        return (OTRGlobals::Instance->gRandoContext->IsQuestOfLocationActive(rc) || rc == RC_GIFT_FROM_RAURU) &&
               rc != RC_LINKS_POCKET;
    }
    return false;
}

bool IsVisibleInCheckTracker(RandomizerCheck rc) {
    auto loc = Rando::StaticData::GetLocation(rc);
    if (IS_RANDO) {
        // For an Archipelago save, the generated slot's active-location list is
        // authoritative. Native tracker category toggles were built around a
        // locally generated SoH seed and can hide checks that AP actually enabled
        // (freestanding rupees and Wonder Items are common examples).
        //
        // Keep only real native location records, but otherwise show exactly the
        // RandomizerChecks owned by this AP slot.
        if (Archipelago_IsCurrentSaveActive()) {
            return loc != nullptr &&
                   loc->GetArea() != RCAREA_INVALID &&
                   loc->GetRCType() != RCTYPE_GOSSIP_STONE &&
                   loc->GetRCType() != RCTYPE_STATIC_HINT &&
                   Archipelago_IsCheckMappedActive(static_cast<int32_t>(rc));
        }

        return !Rando::Context::GetInstance()->GetItemLocation(rc)->IsExcluded() &&
               (IsCheckShuffled(rc) ||
                (alwaysShowGS && loc->GetRCType() == RCTYPE_SKULL_TOKEN &&
                 OTRGlobals::Instance->gRandoContext->IsQuestOfLocationActive(rc)) ||
                (loc->GetRCType() == RCTYPE_SHOP && showShops && !hideShopUnshuffledChecks));
    } else {
        return loc->IsVanillaCompletion() &&
               (!loc->IsDungeon() || (loc->IsDungeon() && loc->GetQuest() == gSaveContext.ship.quest.id));
    }
}

void UpdateInventoryChecks() {
    // For all the areas with maps, if you have one, spoil the area
    for (auto [scene, area] : DungeonRCAreasBySceneID) {
        if (CHECK_DUNGEON_ITEM(DUNGEON_MAP, scene)) {
            SetAreaSpoiled(area);
        }
    }
}

void UpdateAreaFullyChecked(RandomizerCheckArea area) {
}

void UpdateAllAreas() {
    // Sort the entire thing
    for (int i = 0; i < RCAREA_INVALID; i++) {
        UpdateAreas(static_cast<RandomizerCheckArea>(i));
    }
}

void UpdateAreas(RandomizerCheckArea area) {
    if (checksByArea.contains(area)) {
        areasFullyChecked[area] = static_cast<size_t>(areaChecksGotten[area]) == checksByArea.find(area)->second.size();
    }
}

void UpdateAllOrdering() {
    // Sort every area, then recalculate totals ONCE.
    //
    // The old implementation called UpdateOrdering() for every area, and each
    // UpdateOrdering() called RecalculateAllAreaTotals().  That turned a global
    // tracker rebuild into roughly O(area_count * all_checks).  With SOH-EXTREME
    // sanity/AP locations this can look like a permanent hang on Start.
    for (int i = 0; i < RCAREA_INVALID; i++) {
        const auto area = static_cast<RandomizerCheckArea>(i);
        if (checksByArea.contains(area)) {
            auto& checks = checksByArea.find(area)->second;
            std::sort(checks.begin(), checks.end(), CompareChecks);
        }
    }

    RecalculateAllAreaTotals();
    CalculateTotals();
}

void UpdateOrdering(RandomizerCheckArea rcArea) {
    // Sort a single area
    if (checksByArea.contains(rcArea)) {
        std::sort(checksByArea.find(rcArea)->second.begin(), checksByArea.find(rcArea)->second.end(), CompareChecks);
    }
    RecalculateAllAreaTotals();
    CalculateTotals();
}

bool IsEoDCheck(RandomizerCheckType type) {
    return type == RCTYPE_BOSS_HEART_OR_OTHER_REWARD || type == RCTYPE_DUNGEON_REWARD;
}

bool CompareChecks(RandomizerCheck i, RandomizerCheck j) {
    Rando::Location* x = Rando::StaticData::GetLocation(i);
    Rando::Location* y = Rando::StaticData::GetLocation(j);
    auto itemI = OTRGlobals::Instance->gRandoContext->GetItemLocation(i);
    auto itemJ = OTRGlobals::Instance->gRandoContext->GetItemLocation(j);
    bool iCollected = itemI->HasObtained();
    bool iSaved = itemI->GetCheckStatus() == RCSHOW_SAVED;
    bool jCollected = itemJ->HasObtained();
    bool jSaved = itemJ->GetCheckStatus() == RCSHOW_SAVED;

    if (!iCollected && jCollected) {
        return true;
    } else if (iCollected && !jCollected) {
        return false;
    }

    if (!iSaved && jSaved) {
        return true;
    } else if (iSaved && !jSaved) {
        return false;
    }

    if (!itemI->GetIsSkipped() && itemJ->GetIsSkipped()) {
        return true;
    } else if (itemI->GetIsSkipped() && !itemJ->GetIsSkipped()) {
        return false;
    }

    if (!IsEoDCheck(x->GetRCType()) && IsEoDCheck(y->GetRCType())) {
        return true;
    } else if (IsEoDCheck(x->GetRCType()) && !IsEoDCheck(y->GetRCType())) {
        return false;
    }

    if (i < j) {
        return true;
    } else if (i > j) {
        return false;
    }

    return false;
}

bool IsHeartPiece(GetItemID giid) {
    return giid == GI_HEART_PIECE || giid == GI_HEART_PIECE_WIN;
}

bool IsMysteryShopItem(RandomizerCheck rc) {
    s32 sceneNum = 0;
    u8 slotIndex = 0;

    if (rc >= RC_KF_SHOP_ITEM_1 && rc <= RC_KF_SHOP_ITEM_8) {
        sceneNum = SCENE_KOKIRI_SHOP;
        slotIndex = rc - RC_KF_SHOP_ITEM_1;
    } else if (rc >= RC_MARKET_BAZAAR_ITEM_1 && rc <= RC_MARKET_BAZAAR_ITEM_8) {
        sceneNum = SCENE_BAZAAR;
        slotIndex = rc - RC_MARKET_BAZAAR_ITEM_1;
    } else if (rc >= RC_MARKET_POTION_SHOP_ITEM_1 && rc <= RC_MARKET_POTION_SHOP_ITEM_8) {
        sceneNum = SCENE_POTION_SHOP_MARKET;
        slotIndex = rc - RC_MARKET_POTION_SHOP_ITEM_1;
    } else if (rc >= RC_MARKET_BOMBCHU_SHOP_ITEM_1 && rc <= RC_MARKET_BOMBCHU_SHOP_ITEM_8) {
        sceneNum = SCENE_BOMBCHU_SHOP;
        slotIndex = rc - RC_MARKET_BOMBCHU_SHOP_ITEM_1;
    } else if (rc >= RC_KAK_BAZAAR_ITEM_1 && rc <= RC_KAK_BAZAAR_ITEM_8) {
        sceneNum = SCENE_TEST01;
        slotIndex = rc - RC_KAK_BAZAAR_ITEM_1;
    } else if (rc >= RC_KAK_POTION_SHOP_ITEM_1 && rc <= RC_KAK_POTION_SHOP_ITEM_8) {
        sceneNum = SCENE_POTION_SHOP_KAKARIKO;
        slotIndex = rc - RC_KAK_POTION_SHOP_ITEM_1;
    } else if (rc >= RC_GC_SHOP_ITEM_1 && rc <= RC_GC_SHOP_ITEM_8) {
        sceneNum = SCENE_GORON_SHOP;
        slotIndex = rc - RC_GC_SHOP_ITEM_1;
    } else if (rc >= RC_ZD_SHOP_ITEM_1 && rc <= RC_ZD_SHOP_ITEM_8) {
        sceneNum = SCENE_ZORA_SHOP;
        slotIndex = rc - RC_ZD_SHOP_ITEM_1;
    } else {
        return false;
    }

    ShopItemIdentity shopItemIdentity = OTRGlobals::Instance->gRandomizer->IdentifyShopItem(sceneNum, slotIndex + 1);
    return shopItemIdentity.enGirlAShopItem == SI_RANDOMIZED_ITEM;
}

void DrawNpcSpeechLocation(const NpcSpeechFinderEntry& entry) {
    if (!IsNpcSpeechVisible(entry)) {
        return;
    }

    auto* loc = Rando::StaticData::GetLocation(static_cast<RandomizerCheck>(entry.rc));
    if (loc == nullptr) {
        return;
    }

    const bool reported = Archipelago_IsLocationReported(entry.locationId);
    const bool available = !reported && availableNpcSpeechLocations.contains(entry.locationId);
    std::string txt = "NPC Speech: " + loc->GetShortName();

    if (!checkSearch.PassFilter(txt.c_str())) {
        return;
    }
    if (enableAvailableChecks && onlyShowAvailable && !available) {
        return;
    }
    if (reported && !showHidden && hideCollected) {
        return;
    }
    if (!reported && !showHidden && hideUnchecked) {
        return;
    }

    const Color_RGBA8 mainColor = reported ? Color_Collected_Main : Color_Unchecked_Main;

    ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, { 4.0f, 3.0f });
    const float sz = ImGui::GetFrameHeight();
    ImGui::Dummy(ImVec2(sz, sz));
    ImGui::PopStyleVar();
    ImGui::SameLine();

    ImVec4 styleColor(mainColor.r / 255.0f, mainColor.g / 255.0f, mainColor.b / 255.0f, mainColor.a / 255.0f);
    if (enableAvailableChecks) {
        if (reported) {
            ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0, 0, 0, 0));
        } else {
            ImGui::PushStyleColor(ImGuiCol_Text, styleColor);
        }
        ImGui::Text("%s", available ? ICON_FA_UNLOCK : ICON_FA_LOCK);
        ImGui::PopStyleColor();
        ImGui::SameLine();
    }

    ImGui::PushStyleColor(ImGuiCol_Text, styleColor);
    ImGui::Text("%s", txt.c_str());
    ImGui::PopStyleColor();
}

void DrawEnemyDefeatLocation(const EnemyDefeatFinderEntry& entry) {
    if (!IsEnemyDefeatVisible(entry)) return;
    const bool reported = Archipelago_IsLocationReported(entry.locationId);
    const bool available = !reported && availableEnemyDefeatLocations.contains(entry.locationId);
    if (!checkSearch.PassFilter(entry.name)) return;
    if (enableAvailableChecks && onlyShowAvailable && !available) return;
    if (reported && !showHidden && hideCollected) return;
    if (!reported && !showHidden && hideUnchecked) return;

    const Color_RGBA8 mainColor = reported ? Color_Collected_Main : Color_Unchecked_Main;
    ImVec4 styleColor(mainColor.r / 255.0f, mainColor.g / 255.0f, mainColor.b / 255.0f, mainColor.a / 255.0f);

    ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, { 4.0f, 3.0f });
    const float sz = ImGui::GetFrameHeight();
    ImGui::Dummy(ImVec2(sz, sz));
    ImGui::PopStyleVar();
    ImGui::SameLine();
    if (enableAvailableChecks) {
        if (reported) ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0, 0, 0, 0));
        else ImGui::PushStyleColor(ImGuiCol_Text, styleColor);
        ImGui::Text("%s", available ? ICON_FA_UNLOCK : ICON_FA_LOCK);
        ImGui::PopStyleColor();
        ImGui::SameLine();
    }
    ImGui::PushStyleColor(ImGuiCol_Text, styleColor);
    ImGui::Text("%s", entry.name);
    ImGui::PopStyleColor();
}

void DrawLocation(RandomizerCheck rc) {
    Color_RGBA8 mainColor = Color_Unchecked_Main;
    Color_RGBA8 extraColor = Color_Unchecked_Extra;
    std::string txt;
    Rando::Location* loc = Rando::StaticData::GetLocation(rc);
    Rando::ItemLocation* itemLoc = OTRGlobals::Instance->gRandoContext->GetItemLocation(rc);
    RandomizerCheckStatus status = itemLoc->GetCheckStatus();
    bool skipped = itemLoc->GetIsSkipped();
    bool available = itemLoc->IsAvailable();
    if (enableAvailableChecks && onlyShowAvailable && !available) {
        return;
    }

    if (status == RCSHOW_COLLECTED) {
        if (!showHidden && hideCollected) {
            return;
        }
        mainColor =
            !IsHeartPiece((GetItemID)Rando::StaticData::RetrieveItem(loc->GetVanillaItem()).GetItemID()) && !IS_RANDO
                ? Color_Collected_Extra
                : Color_Collected_Main;
        extraColor = Color_Collected_Extra;
    } else if (status == RCSHOW_SAVED) {
        if (!showHidden && hideSaved) {
            return;
        }
        mainColor =
            !IsHeartPiece((GetItemID)Rando::StaticData::RetrieveItem(loc->GetVanillaItem()).GetItemID()) && !IS_RANDO
                ? Color_Saved_Extra
                : Color_Saved_Main;
        extraColor = Color_Saved_Extra;
    } else if (skipped) {
        if (!showHidden && hideSkipped) {
            return;
        }
        mainColor =
            !IsHeartPiece((GetItemID)Rando::StaticData::RetrieveItem(loc->GetVanillaItem()).GetItemID()) && !IS_RANDO
                ? Color_Skipped_Extra
                : Color_Skipped_Main;
        extraColor = Color_Skipped_Extra;
    } else if (status == RCSHOW_SEEN_OR_HINTED || status == RCSHOW_IDENTIFIED) {
        if (!showHidden && hideSeen) {
            return;
        }
        mainColor =
            !IsHeartPiece((GetItemID)Rando::StaticData::RetrieveItem(loc->GetVanillaItem()).GetItemID()) && !IS_RANDO
                ? Color_Seen_Extra
                : Color_Seen_Main;
        extraColor = Color_Seen_Extra;
    } else if (status == RCSHOW_SCUMMED) {
        if (!showHidden && hideScummed) {
            return;
        }
        mainColor =
            !IsHeartPiece((GetItemID)Rando::StaticData::RetrieveItem(loc->GetVanillaItem()).GetItemID()) && !IS_RANDO
                ? Color_Scummed_Extra
                : Color_Scummed_Main;
        extraColor = Color_Scummed_Extra;
    } else if (status == RCSHOW_UNCHECKED) {
        if (!showHidden && hideUnchecked) {
            return;
        }
        mainColor =
            !IsHeartPiece((GetItemID)Rando::StaticData::RetrieveItem(loc->GetVanillaItem()).GetItemID()) && !IS_RANDO
                ? Color_Unchecked_Extra
                : Color_Unchecked_Main;
        extraColor = Color_Unchecked_Extra;
    }

    // Main Text
    if (checkNameOverrides.contains(loc->GetRandomizerCheck())) {
        txt = checkNameOverrides[loc->GetRandomizerCheck()];
    } else {
        txt = loc->GetShortName();
    }
    if (lastLocationChecked == loc->GetRandomizerCheck()) {
        txt = "* " + txt;
    }

    // Draw button - for Skipped/Seen/Scummed/Unchecked only
    ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, { 4.0f, 3.0f });
    float sz = ImGui::GetFrameHeight();
    if (status == RCSHOW_UNCHECKED || status == RCSHOW_SEEN_OR_HINTED ||
        status == RCSHOW_IDENTIFIED || status == RCSHOW_SCUMMED || skipped) {
        if (UIWidgets::StateButton(std::to_string(rc).c_str(), skipped ? ICON_FA_PLUS : ICON_FA_TIMES, ImVec2(sz, sz),
                                   UIWidgets::ButtonOptions().Color(THEME_COLOR))) {
            if (skipped) {
                OTRGlobals::Instance->gRandoContext->GetItemLocation(rc)->SetIsSkipped(false);
                areaChecksGotten[loc->GetArea()]--;
                totalChecksGotten--;
                if (available) {
                    areaChecksAvailable[loc->GetArea()]++;
                    totalChecksAvailable++;
                }
            } else {
                OTRGlobals::Instance->gRandoContext->GetItemLocation(rc)->SetIsSkipped(true);
                areaChecksGotten[loc->GetArea()]++;
                totalChecksGotten++;
                if (available) {
                    areaChecksAvailable[loc->GetArea()]--;
                    totalChecksAvailable--;
                }
            }
            UpdateOrdering(loc->GetArea());
            UpdateInventoryChecks();
            SaveManager::Instance->SaveSection(gSaveContext.fileNum, sectionId, true);
        }
    } else {
        ImGui::Dummy(ImVec2(sz, sz));
    }
    ImGui::PopStyleVar();

    ImGui::SameLine();

    // Draw
    ImVec4 styleColor(mainColor.r / 255.0f, mainColor.g / 255.0f, mainColor.b / 255.0f, mainColor.a / 255.0f);
    if (enableAvailableChecks) {
        if (itemLoc->HasObtained()) {
            ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0, 0, 0, 0));
        } else {
            ImGui::PushStyleColor(ImGuiCol_Text, styleColor);
        }
        ImGui::Text("%s", available ? ICON_FA_UNLOCK : ICON_FA_LOCK);
        ImGui::PopStyleColor();
        ImGui::SameLine();
    }

    ImGui::PushStyleColor(ImGuiCol_Text, styleColor);
    ImGui::Text("%s", txt.c_str());
    ImGui::PopStyleColor();

    // Draw the extra info
    txt = "";

    if (status != RCSHOW_UNCHECKED) {
        switch (status) {
            case RCSHOW_UNCHECKED:
                break;
            case RCSHOW_SAVED:
            case RCSHOW_COLLECTED:
            case RCSHOW_SCUMMED:
                if (IS_RANDO) {
                    txt = itemLoc->GetPlacedItem().GetName().GetForLanguage(gSaveContext.language);
                } else {
                    if (IsHeartPiece((GetItemID)Rando::StaticData::RetrieveItem(loc->GetVanillaItem()).GetItemID())) {
                        if (gSaveContext.language == LANGUAGE_ENG || gSaveContext.language == LANGUAGE_GER ||
                            gSaveContext.language == LANGUAGE_JPN) {
                            txt = Rando::StaticData::RetrieveItem(loc->GetVanillaItem()).GetName().english;
                        } else if (gSaveContext.language == LANGUAGE_FRA) {
                            txt = Rando::StaticData::RetrieveItem(loc->GetVanillaItem()).GetName().french;
                        }
                    }
                }
                break;
            case RCSHOW_IDENTIFIED:
            case RCSHOW_SEEN_OR_HINTED:
                if (IS_RANDO) {
                    const auto checkType = loc->GetRCType();
                    const bool hideMerchantName =
                        checkType == RCTYPE_MERCHANT &&
                        (!OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_MERCHANT_TEXT_HINT) || mystery);
                    const bool hideScrubName =
                        checkType == RCTYPE_SCRUB &&
                        (!OTRGlobals::Instance->gRandomizer->GetRandoSettingValue(RSK_SCRUB_TEXT_HINT) || mystery);
                    const bool hideShopName = checkType == RCTYPE_SHOP && mystery && IsMysteryShopItem(rc);
                    const bool revealItemName = !(hideMerchantName || hideScrubName || hideShopName);

                    if (itemLoc->GetPlacedRandomizerGet() == RG_ICE_TRAP && revealItemName) {
                        if (status == RCSHOW_IDENTIFIED) {
                            txt = OTRGlobals::Instance->gRandoContext->overrides[rc].GetTrickName().GetForLanguage(
                                gSaveContext.language);
                        } else {
                            txt = Rando::StaticData::RetrieveItem(
                                      OTRGlobals::Instance->gRandoContext->overrides[rc].LooksLike())
                                      .GetName()
                                      .GetForLanguage(gSaveContext.language);
                        }
                    } else if (revealItemName) {
                        txt = itemLoc->GetPlacedItem().GetName().GetForLanguage(gSaveContext.language);
                    }
                    if (itemLoc->CanBePurchased() && IsVisibleInCheckTracker(rc) && status == RCSHOW_IDENTIFIED) {
                        auto price = OTRGlobals::Instance->gRandoContext->GetItemLocation(rc)->GetPrice();
                        txt = !txt.empty() ? spdlog::fmt_lib::format("{} - {}", txt, price)
                                           : spdlog::fmt_lib::format("{}", price);
                    }
                } else {
                    if (IsHeartPiece((GetItemID)Rando::StaticData::RetrieveItem(loc->GetVanillaItem()).GetItemID())) {
                        if (gSaveContext.language == LANGUAGE_ENG || gSaveContext.language == LANGUAGE_GER ||
                            gSaveContext.language == LANGUAGE_JPN) {
                            txt = Rando::StaticData::RetrieveItem(loc->GetVanillaItem()).GetName().english;
                        } else if (gSaveContext.language == LANGUAGE_FRA) {
                            txt = Rando::StaticData::RetrieveItem(loc->GetVanillaItem()).GetName().french;
                        }
                    }
                }
                break;
        }
    }
    if (txt == "" && skipped) {
        txt = "Skipped"; // TODO language
    }

    if (txt != "") {
        ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(extraColor.r / 255.0f, extraColor.g / 255.0f, extraColor.b / 255.0f,
                                                    extraColor.a / 255.0f));
        ImGui::SameLine();
        ImGui::Text(" (%s)", txt.c_str());
        ImGui::PopStyleColor();
    }

    if (showLogicTooltip) {
        for (auto& locationInRegion : areaTable[itemLoc->GetParentRegionKey()].locations) {
            if (locationInRegion.GetLocation() == rc) {
                std::string conditionStr = locationInRegion.GetConditionStr();
                if (conditionStr != "true") {
                    UIWidgets::Tooltip(conditionStr.c_str());
                }
                break;
            }
        }
    }
}

static std::set<std::string> rainbowCVars = {
    CVAR_TRACKER_CHECK("AreaIncomplete.MainColor"), CVAR_TRACKER_CHECK("AreaIncomplete.ExtraColor"),
    CVAR_TRACKER_CHECK("AreaComplete.MainColor"),   CVAR_TRACKER_CHECK("AreaComplete.ExtraColor"),
    CVAR_TRACKER_CHECK("Unchecked.MainColor"),      CVAR_TRACKER_CHECK("Unchecked.ExtraColor"),
    CVAR_TRACKER_CHECK("Skipped.MainColor"),        CVAR_TRACKER_CHECK("Skipped.ExtraColor"),
    CVAR_TRACKER_CHECK("Seen.MainColor"),           CVAR_TRACKER_CHECK("Seen.ExtraColor"),
    CVAR_TRACKER_CHECK("Hinted.MainColor"),         CVAR_TRACKER_CHECK("Hinted.ExtraColor"),
    CVAR_TRACKER_CHECK("Collected.MainColor"),      CVAR_TRACKER_CHECK("Collected.ExtraColor"),
    CVAR_TRACKER_CHECK("Scummed.MainColor"),        CVAR_TRACKER_CHECK("Scummed.ExtraColor"),
    CVAR_TRACKER_CHECK("Saved.MainColor"),          CVAR_TRACKER_CHECK("Saved.ExtraColor"),
};

int hue = 0;
void RainbowTick() {
    float freqHue = hue * 2 * M_PIf / (360 * CVarGetFloat(CVAR_COSMETIC("RainbowSpeed"), 0.6f));
    for (auto& cvar : rainbowCVars) {
        if (CVarGetInteger((cvar + ".Rainbow").c_str(), 0) == 0) {
            continue;
        }

        Color_RGBA8 newColor;
        newColor.r = static_cast<uint8_t>(sin(freqHue + 0) * 127) + 128;
        newColor.g = static_cast<uint8_t>(sin(freqHue + (2 * M_PI / 3)) * 127) + 128;
        newColor.b = static_cast<uint8_t>(sin(freqHue + (4 * M_PI / 3)) * 127) + 128;
        newColor.a = 255;

        CVarSetColor((cvar + ".Value").c_str(), newColor);
    }

    hue++;
    hue %= 360;
}

void ImGuiDrawTwoColorPickerSection(const char* text, const char* cvarMainName, const char* cvarExtraName,
                                    Color_RGBA8& main_color, Color_RGBA8& extra_color,
                                    const Color_RGBA8& main_default_color, const Color_RGBA8& extra_default_color,
                                    const char* cvarHideName, const char* tooltip, UIWidgets::Colors theme) {
    Color_RGBA8 cvarMainColor = CVarGetColor(cvarMainName, main_default_color);
    Color_RGBA8 cvarExtraColor = CVarGetColor(cvarExtraName, extra_default_color);
    main_color = cvarMainColor;
    extra_color = cvarExtraColor;

    UIWidgets::PushStyleCombobox(theme);
    if (ImGui::CollapsingHeader(text)) {
        if (*cvarHideName != '\0') {
            std::string label = cvarHideName;
            label += "##Hidden";
            ImGui::PushID(label.c_str());
            UIWidgets::CVarCheckbox(
                "Hidden", cvarHideName,
                UIWidgets::CheckboxOptions(
                    { { .tooltip = "When active, checks will hide by default when updated to this state. Can "
                                   "be overridden with the \"Show Hidden Items\" option." } })
                    .Color(theme));
            ImGui::PopID();
        }
        std::string mainLabel = "Name##" + std::string(cvarMainName);
        if (UIWidgets::CVarColorPicker(mainLabel.c_str(), cvarMainName, main_default_color, false,
                                       UIWidgets::ColorPickerRandomButton | UIWidgets::ColorPickerResetButton |
                                           UIWidgets::ColorPickerRainbowCheck,
                                       theme)) {
            main_color = CVarGetColor(cvarMainName, main_default_color);
        }

        std::string extraLabel = "Details##" + std::string(cvarExtraName);
        if (UIWidgets::CVarColorPicker(extraLabel.c_str(), cvarExtraName, extra_default_color, false,
                                       UIWidgets::ColorPickerRandomButton | UIWidgets::ColorPickerResetButton |
                                           UIWidgets::ColorPickerRainbowCheck,
                                       theme)) {
            extra_color = CVarGetColor(cvarExtraName, extra_default_color);
        }
    }
    if (tooltip != NULL && strlen(tooltip) != 0) {
        ImGui::SameLine();
        ImGui::Text(" ?");
        UIWidgets::Tooltip(tooltip);
    }
    UIWidgets::PopStyleCombobox();
}

void InternalRecalculateAvailableChecks(RandomizerRegion startingRegion, RandoAgeTime startingAgeTime) {
    if (!enableAvailableChecks || !GameInteractor::IsSaveLoaded() || gPlayState == nullptr) {
        return;
    }

    const bool apSave = Archipelago_IsCurrentSaveActive();
    if (apSave) {
        // The AP Check Finder renders the live UT snapshot; do not compute a
        // conflicting local result on item/scene callbacks or manual reload.
        ArchipelagoClient::GetInstance().RefreshFinderMirror();
        return;
    }
    if (apSave && !Archipelago_PrepareCheckFinderMappings()) {
        // Scouts are still arriving. ArchipelagoClient schedules a fresh pass as
        // soon as the complete active set is present, so do not spin every frame.
        SPDLOG_DEBUG("[Archipelago] Available Checks deferred until active scouts are complete");
        return;
    }

    ResetPerformanceTimer(PT_RECALCULATE_AVAILABLE_CHECKS);
    StartPerformanceTimer(PT_RECALCULATE_AVAILABLE_CHECKS);

    const auto& ctx = Rando::Context::GetInstance();
    logic = ctx->GetLogic();
    if (logic == nullptr) {
        StopPerformanceTimer(PT_RECALCULATE_AVAILABLE_CHECKS);
        return;
    }
    SohExtreme::ScopedCheckFinderLogic<Rando::Logic, SaveContext> liveLogic(*logic, gSaveContext);


    // SOH-EXTREME/AP: never seed availability from the room we happen to be in.
    // Every location must prove a complete path from RR_ROOT through every parent
    // region/entrance requirement first.  Seeding from nextEntranceIndex allowed
    // checks in otherwise unreachable zones (Lake Hylia, GC maze, grottos, etc.)
    // to leak into the Available list.
    // SOH-EXTREME 0.8.09: Check Finder is a logic tool, not a "what can I
    // reach from the room I happen to be standing in" tool. Always certify a
    // complete Root -> ... -> location path for both native randomizer saves
    // and Archipelago saves. This keeps Check Finder identical to generation.
    startingRegion = RR_ROOT;

    if (startingAgeTime == RAT_NONE) {
        if (LINK_IS_CHILD && IS_DAY) {
            startingAgeTime = RAT_CHILD_DAY;
        } else if (LINK_IS_CHILD && IS_NIGHT) {
            startingAgeTime = RAT_CHILD_NIGHT;
        } else if (LINK_IS_ADULT && IS_DAY) {
            startingAgeTime = RAT_ADULT_DAY;
        } else if (LINK_IS_ADULT && IS_NIGHT) {
            startingAgeTime = RAT_ADULT_NIGHT;
        }
    }

    std::vector<RandomizerCheck> targetLocations;
    targetLocations.reserve(RC_MAX);
    for (auto& location : Rando::StaticData::GetLocationTable()) {
        RandomizerCheck rc = location.GetRandomizerCheck();
        Rando::ItemLocation* itemLocation = ctx->GetItemLocation(rc);
        itemLocation->SetAvailable(false);

        // AP's active-location set is authoritative. NPC Speech locations are
        // synthetic AP-only checks keyed to a stable native RC, so keep their
        // anchor RC in the reachability pass even when the underlying native
        // reward check is not active or was already collected.
        const bool pendingNpcSpeech = GetPendingNpcSpeechLocation(rc) >= 0;
        if (apSave && !Archipelago_IsCheckMappedActive(static_cast<int32_t>(rc)) && !pendingNpcSpeech) {
            continue;
        }

        if (!itemLocation->HasObtained() || pendingNpcSpeech) {
            targetLocations.emplace_back(rc);
        }
    }

    std::vector<RandomizerCheck> availableChecks =
        ReachabilitySearch(targetLocations, RG_NONE, true, startingRegion, startingAgeTime);
    std::set<RandomizerCheck> nativeAvailable(availableChecks.begin(), availableChecks.end());

    // A speech-only anchor must never make the underlying native AP location look
    // available after that native check was already obtained.  Keep the two AP
    // locations' availability states independent.
    for (auto& rc : availableChecks) {
        auto* itemLocation = ctx->GetItemLocation(rc);
        if (itemLocation != nullptr &&
            (!apSave || Archipelago_IsCheckMappedActive(static_cast<int32_t>(rc))) &&
            !itemLocation->HasObtained()) {
            itemLocation->SetAvailable(true);
        }
    }

    // NPC Speech Sanity uses a native RC as its physical interaction anchor.
    // The speech check must satisfy the FULL native anchor rule (zone access, age,
    // Open Chest where the interaction is tied to a chest, Dampe/race rules, shop
    // access, etc.) in addition to NPC Soul + the correct Speak language.  Merely
    // reaching the parent region is not sufficient.
    availableNpcSpeechLocations.clear();
    availableEnemyDefeatLocations.clear();
    if (apSave) {
        for (const auto& entry : kNpcSpeechFinderEntries) {
            RandomizerCheck rc = static_cast<RandomizerCheck>(entry.rc);
            if (Archipelago_IsLocationActive(entry.locationId) &&
                !Archipelago_IsLocationReported(entry.locationId) &&
                HasNpcSpeechInteractionItems(entry) &&
                nativeAvailable.contains(rc)) {
                availableNpcSpeechLocations.insert(entry.locationId);
            }
        }
        for (size_t enemyIndex = 0; enemyIndex < kEnemyDefeatFinderEntryCount; ++enemyIndex) {
            const auto& entry = kEnemyDefeatFinderEntries[enemyIndex];
            if (IsEnemyDefeatVisible(entry) && !Archipelago_IsLocationReported(entry.locationId) &&
                IsEnemyDefeatReachable(entry)) {
                availableEnemyDefeatLocations.insert(entry.locationId);
            }
        }
    }

    // Mapping/scout completion can make native rows visible after the previous
    // filter pass.  Refresh the row filters before recounting so an area header
    // can never say e.g. "2 available" while only one available row is drawn.
    UpdateFilters();

    // Recompute checked/available/total counts from one source of truth. This
    // includes native rows plus synthetic NPC Speech and per-placement Enemy
    // Defeat rows, so the counters cannot lag behind the row state.
    RecalculateAllAreaTotals();

    StopPerformanceTimer(PT_RECALCULATE_AVAILABLE_CHECKS);
    SPDLOG_INFO("{} Available Checks: {} reachable active checks in {}ms",
                apSave ? "[Archipelago]" : "[Randomizer]",
                totalChecksAvailable,
                GetPerformanceTimer(PT_RECALCULATE_AVAILABLE_CHECKS).count());
}

void NotifyArchipelagoLocationReported(int64_t locationId) {
    if (!Archipelago_IsCurrentSaveActive()) return;

    for (const auto& entry : kNpcSpeechFinderEntries) {
        if (entry.locationId == locationId && IsNpcSpeechVisible(entry)) {
            RecalculateAreaTotals(GetNpcSpeechArea(entry));
            RecalculateAvailableChecks();
            return;
        }
    }
    for (size_t enemyIndex = 0; enemyIndex < kEnemyDefeatFinderEntryCount; ++enemyIndex) {
        const auto& entry = kEnemyDefeatFinderEntries[enemyIndex];
        if (entry.locationId == locationId && IsEnemyDefeatVisible(entry)) {
            RecalculateAreaTotals(entry.area);
            RecalculateAvailableChecks();
            return;
        }
    }
}

void RecalculateAvailableChecks(RandomizerRegion startingRegion /* = RR_ROOT */,
                                RandoAgeTime startingAgeTime /* = RAT_NONE */) {
    // Available Checks is an explicit tracker feature, not mandatory gameplay
    // work. Keep it completely dormant unless enabled; when enabled, merely
    // schedule one deferred pass so repeated item/check callbacks coalesce.
    if (!CVarGetInteger(CVAR_TRACKER_CHECK("EnableAvailableChecks"), 0)) {
        recalculateAvailable = false;
        return;
    }

    recalculateAvailable = true;
    availableChecksStartingRegion = startingRegion;
    availableChecksStartingAgeTime = startingAgeTime;
}

void LoadFromPreset(const nlohmann::json& info) {
    presetLoaded = true;
    presetPos = { info.at("pos").at("x"), info.at("pos").at("y") };
    presetSize = { info.at("size").at("width"), info.at("size").at("height") };
}

void CheckTrackerWindow::Draw() {
    if (!IsVisible()) {
        return;
    }
    DrawElement();
    // Sync up the IsVisible flag if it was changed by ImGui
    SyncVisibilityConsoleVariable();
}

void CheckTrackerSettingsWindow::DrawElement() {
    ImGui::PushStyleVar(ImGuiStyleVar_CellPadding, { 8.0f, 8.0f });
    if (ImGui::BeginTable("CheckTrackerSettingsTable", 2, ImGuiTableFlags_BordersH | ImGuiTableFlags_BordersV)) {
        ImGui::TableSetupColumn("General settings", ImGuiTableColumnFlags_WidthStretch, 200.0f);
        ImGui::TableSetupColumn("Section settings", ImGuiTableColumnFlags_WidthStretch, 200.0f);
        ImGui::TableHeadersRow();
        ImGui::TableNextRow();
        ImGui::TableNextColumn();
        SohGui::GetSohMenu()->MenuDrawItem(backgroundColorWidget,
                                           static_cast<uint32_t>(ImGui::GetContentRegionAvail().x), THEME_COLOR);

        SohGui::GetSohMenu()->MenuDrawItem(windowTypeWidget, static_cast<uint32_t>(ImGui::GetContentRegionAvail().x),
                                           THEME_COLOR);

        UIWidgets::CVarSliderFloat("Font Size", CVAR_TRACKER_CHECK("FontSize"),
                                   UIWidgets::FloatSliderOptions()
                                       .Tooltip("Sets the font size used in the check tracker.")
                                       .Format("%.1f")
                                       .Step(0.1f)
                                       .Min(0.3f)
                                       .Max(2.0f)
                                       .Color(THEME_COLOR)
                                       .DefaultValue(1.0f));

        if (CVarGetInteger(CVAR_TRACKER_CHECK("WindowType"), TRACKER_WINDOW_WINDOW) == TRACKER_WINDOW_FLOATING) {
            UIWidgets::CVarCheckbox("Enable Dragging", CVAR_TRACKER_CHECK("Draggable"),
                                    UIWidgets::CheckboxOptions().Color(THEME_COLOR));
            UIWidgets::CVarCheckbox("Only Enable While Paused", CVAR_TRACKER_CHECK("ShowOnlyPaused"),
                                    UIWidgets::CheckboxOptions().Color(THEME_COLOR));
            UIWidgets::CVarCombobox("Display Mode", CVAR_TRACKER_CHECK("DisplayType"), showMode,
                                    UIWidgets::ComboboxOptions()
                                        .LabelPosition(UIWidgets::LabelPositions::Far)
                                        .ComponentAlignment(UIWidgets::ComponentAlignments::Right)
                                        .Color(THEME_COLOR)
                                        .DefaultIndex(0));
            if (CVarGetInteger(CVAR_TRACKER_CHECK("DisplayType"), TRACKER_DISPLAY_ALWAYS) ==
                TRACKER_DISPLAY_COMBO_BUTTON) {
                UIWidgets::CVarCombobox("Combo Button 1", CVAR_TRACKER_CHECK("ComboButton1"), buttonStrings,
                                        UIWidgets::ComboboxOptions()
                                            .LabelPosition(UIWidgets::LabelPositions::Far)
                                            .ComponentAlignment(UIWidgets::ComponentAlignments::Right)
                                            .Color(THEME_COLOR)
                                            .DefaultIndex(TRACKER_COMBO_BUTTON_L));
                UIWidgets::CVarCombobox("Combo Button 2", CVAR_TRACKER_CHECK("ComboButton2"), buttonStrings,
                                        UIWidgets::ComboboxOptions()
                                            .LabelPosition(UIWidgets::LabelPositions::Far)
                                            .ComponentAlignment(UIWidgets::ComponentAlignments::Right)
                                            .Color(THEME_COLOR)
                                            .DefaultIndex(TRACKER_COMBO_BUTTON_L));
            }
        }
        ImGui::BeginDisabled(CVarGetInteger(CVAR_SETTING("DisableChanges"), 0));
        SohGui::GetSohMenu()->MenuDrawItem(dungeonSpoilerWidget,
                                           static_cast<uint32_t>(ImGui::GetContentRegionAvail().x), THEME_COLOR);
        ImGui::EndDisabled();

        SohGui::GetSohMenu()->MenuDrawItem(hideUnshuffledShopWidget,
                                           static_cast<uint32_t>(ImGui::GetContentRegionAvail().x), THEME_COLOR);

        SohGui::GetSohMenu()->MenuDrawItem(showGSWidget, static_cast<uint32_t>(ImGui::GetContentRegionAvail().x),
                                           THEME_COLOR);

        SohGui::GetSohMenu()->MenuDrawItem(showLogicWidget, static_cast<uint32_t>(ImGui::GetContentRegionAvail().x),
                                           THEME_COLOR);

        // Tracker availability is a live UI preference, not a seed setting.
        // It must remain toggleable while an AP/randomizer save is loaded.
        SohGui::GetSohMenu()->MenuDrawItem(checkAvailabilityWidget,
                                           static_cast<uint32_t>(ImGui::GetContentRegionAvail().x), THEME_COLOR);

        // Filtering settings
        UIWidgets::CVarCheckbox(
            "Filter Empty Areas", CVAR_TRACKER_CHECK("HideFilteredAreas"),
            UIWidgets::CheckboxOptions()
                .Tooltip("If enabled, will hide area headers that have no locations matching filter")
                .Color(THEME_COLOR)
                .DefaultValue(true));

        ImGui::SeparatorText("Tracker Header Visibility");
        UIWidgets::CVarCheckbox("Hidden Items Toggle", CVAR_TRACKER_CHECK("HiddenItemsToggleVisible"),
                                UIWidgets::CheckboxOptions().Color(THEME_COLOR).DefaultValue(true));
        UIWidgets::CVarCheckbox("Available Checks Toggle", CVAR_TRACKER_CHECK("AvailableChecksToggleVisible"),
                                UIWidgets::CheckboxOptions().Color(THEME_COLOR).DefaultValue(true));
        UIWidgets::CVarCheckbox("Expand/Collapse Buttons", CVAR_TRACKER_CHECK("ExpandCollapseButtonsVisible"),
                                UIWidgets::CheckboxOptions().Color(THEME_COLOR).DefaultValue(false));
        UIWidgets::CVarCheckbox("Search Input", CVAR_TRACKER_CHECK("SearchInputVisible"),
                                UIWidgets::CheckboxOptions().Color(THEME_COLOR).DefaultValue(true));
        UIWidgets::CVarCheckbox("Check Totals", CVAR_TRACKER_CHECK("CheckTotalsVisible"),
                                UIWidgets::CheckboxOptions().Color(THEME_COLOR).DefaultValue(true));

        ImGui::TableNextColumn();

        CheckTracker::ImGuiDrawTwoColorPickerSection("Area Incomplete", CVAR_TRACKER_CHECK("AreaIncomplete.MainColor"),
                                                     CVAR_TRACKER_CHECK("AreaIncomplete.ExtraColor"),
                                                     Color_Area_Incomplete_Main, Color_Area_Incomplete_Extra,
                                                     Color_Main_Default, Color_Area_Incomplete_Extra_Default,
                                                     CVAR_TRACKER_CHECK("AreaIncomplete.Hide"), "", THEME_COLOR);
        CheckTracker::ImGuiDrawTwoColorPickerSection("Area Complete", CVAR_TRACKER_CHECK("AreaComplete.MainColor"),
                                                     CVAR_TRACKER_CHECK("AreaComplete.ExtraColor"),
                                                     Color_Area_Complete_Main, Color_Area_Complete_Extra,
                                                     Color_Main_Default, Color_Area_Complete_Extra_Default,
                                                     CVAR_TRACKER_CHECK("AreaComplete.Hide"), "", THEME_COLOR);
        CheckTracker::ImGuiDrawTwoColorPickerSection(
            "Unchecked", CVAR_TRACKER_CHECK("Unchecked.MainColor"), CVAR_TRACKER_CHECK("Unchecked.ExtraColor"),
            Color_Unchecked_Main, Color_Unchecked_Extra, Color_Main_Default, Color_Unchecked_Extra_Default,
            CVAR_TRACKER_CHECK("Unchecked.Hide"), "Checks you have not interacted with at all.", THEME_COLOR);
        CheckTracker::ImGuiDrawTwoColorPickerSection(
            "Skipped", CVAR_TRACKER_CHECK("Skipped.MainColor"), CVAR_TRACKER_CHECK("Skipped.ExtraColor"),
            Color_Skipped_Main, Color_Skipped_Extra, Color_Main_Default, Color_Skipped_Extra_Default,
            CVAR_TRACKER_CHECK("Skipped.Hide"), "", THEME_COLOR);
        CheckTracker::ImGuiDrawTwoColorPickerSection(
            "Seen", CVAR_TRACKER_CHECK("Seen.MainColor"), CVAR_TRACKER_CHECK("Seen.ExtraColor"), Color_Seen_Main,
            Color_Seen_Extra, Color_Main_Default, Color_Seen_Extra_Default, CVAR_TRACKER_CHECK("Seen.Hide"),
            "Used for shops. Shows item names for shop slots when walking in, and prices when highlighting them in buy "
            "mode.",
            THEME_COLOR);
        CheckTracker::ImGuiDrawTwoColorPickerSection(
            "Scummed", CVAR_TRACKER_CHECK("Scummed.MainColor"), CVAR_TRACKER_CHECK("Scummed.ExtraColor"),
            Color_Scummed_Main, Color_Scummed_Extra, Color_Main_Default, Color_Scummed_Extra_Default,
            CVAR_TRACKER_CHECK("Scummed.Hide"),
            "Checks you collect, but then reload before saving so you no longer have them.", THEME_COLOR);
        // CheckTracker::ImGuiDrawTwoColorPickerSection("Hinted (WIP)",     CVAR_TRACKER_CHECK("Hinted.MainColor"),
        // CVAR_TRACKER_CHECK("Hinted.ExtraColor"),          Color_Hinted_Main,            Color_Hinted_Extra,
        // Color_Main_Default, Color_Hinted_Extra_Default,          CVAR_TRACKER_CHECK("Hinted.Hide"),         "",
        // THEME_COLOR);
        CheckTracker::ImGuiDrawTwoColorPickerSection(
            "Collected", CVAR_TRACKER_CHECK("Collected.MainColor"), CVAR_TRACKER_CHECK("Collected.ExtraColor"),
            Color_Collected_Main, Color_Collected_Extra, Color_Main_Default, Color_Collected_Extra_Default,
            CVAR_TRACKER_CHECK("Collected.Hide"), "Checks you have collected without saving or reloading yet.",
            THEME_COLOR);
        CheckTracker::ImGuiDrawTwoColorPickerSection(
            "Saved", CVAR_TRACKER_CHECK("Saved.MainColor"), CVAR_TRACKER_CHECK("Saved.ExtraColor"), Color_Saved_Main,
            Color_Saved_Extra, Color_Main_Default, Color_Saved_Extra_Default, CVAR_TRACKER_CHECK("Saved.Hide"),
            "Checks that you saved the game while having collected.", THEME_COLOR);

        ImGui::PopStyleVar(1);
        ImGui::EndTable();
    }
}

void CheckTrackerLiveLogicStateUpdate() {
    if (!GameInteractor::IsSaveLoaded() || gPlayState == nullptr || !IS_RANDO ||
        !CVarGetInteger(CVAR_TRACKER_CHECK("EnableAvailableChecks"), 0)) {
        ResetLiveFinderStateSnapshot();
        return;
    }

    auto& state = lastFinderState;
    state.BeginSample();
    state.Observe(gSaveContext.fileNum);
    state.Observe(gSaveContext.ship.quest.id);
    state.Observe(gSaveContext.linkAge);
    state.Observe(IS_DAY != 0);
    state.Observe(gSaveContext.nightFlag);
    state.Observe(gPlayState->sceneNum);
    state.Observe(gPlayState->roomCtx.curRoom.num);

    const auto& inventory = gSaveContext.inventory;
    state.ObserveArray(inventory.items);
    state.ObserveArray(inventory.ammo);
    state.Observe(inventory.equipment);
    state.Observe(inventory.upgrades);
    state.Observe(inventory.questItems);
    state.ObserveArray(inventory.dungeonItems);
    state.ObserveArray(inventory.dungeonKeys);
    state.Observe(inventory.gsTokens);
    state.ObserveArray(gSaveContext.ship.stats.dungeonKeys);
    state.ObserveArray(gSaveContext.ship.randomizerInf);
    state.Observe(gSaveContext.healthCapacity);
    state.Observe(gSaveContext.magicLevel);
    state.Observe(gSaveContext.isMagicAcquired);
    state.Observe(gSaveContext.isDoubleMagicAcquired);
    state.Observe(gSaveContext.isDoubleDefenseAcquired);
    state.Observe(gSaveContext.bgsFlag);
    state.Observe(gSaveContext.scarecrowLongSongSet);
    state.Observe(gSaveContext.scarecrowSpawnSongSet);
    state.ObserveArray(gSaveContext.eventChkInf);
    state.ObserveArray(gSaveContext.itemGetInf);
    state.ObserveArray(gSaveContext.infTable);
    state.ObserveArray(gSaveContext.gsFlags);
    state.ObserveArray(gSaveContext.highScores);

    // Room counters and bean/puzzle switches are not inventory items. Observe
    // both saved scenes and the live scene; neither guarantees an item callback.
    for (const auto& flags : gSaveContext.sceneFlags) {
        state.Observe(flags.chest);
        state.Observe(flags.swch);
        state.Observe(flags.clear);
        state.Observe(flags.collect);
    }
    state.Observe(gPlayState->actorCtx.flags.swch);
    state.Observe(gPlayState->actorCtx.flags.tempSwch);
    state.Observe(gPlayState->actorCtx.flags.clear);
    state.Observe(gPlayState->actorCtx.flags.tempClear);
    state.Observe(gPlayState->actorCtx.flags.collect);
    state.Observe(gPlayState->actorCtx.flags.tempCollect);

    const auto& rando = gSaveContext.ship.quest.data.randomizer;
    state.Observe(rando.triforcePiecesCollected);
    state.Observe(rando.bombchuUpgradeLevel);
    state.Observe(rando.silverShadowBlades);
    state.Observe(rando.silverShadowPit);
    state.Observe(rando.silverShadowSpikes);
    state.Observe(rando.silverSpiritChild);
    state.Observe(rando.silverSpiritSun);
    state.Observe(rando.silverSpiritBoulders);
    state.Observe(rando.silverBotw);
    state.Observe(rando.silverIceCavernBlades);
    state.Observe(rando.silverIceCavernBlock);
    state.Observe(rando.silverGtgSlope);
    state.Observe(rando.silverGtgLava);
    state.Observe(rando.silverGtgWater);
    state.Observe(rando.silverGanonLight);
    state.Observe(rando.silverGanonForest);
    state.Observe(rando.silverGanonFire);
    state.Observe(rando.silverGanonSpirit);
    state.Observe(rando.silverMqDodongosCavern);
    state.Observe(rando.silverMqShadowInvisibleBlades);
    state.Observe(rando.silverMqSpiritLobby);
    state.Observe(rando.silverMqSpiritBigWall);
    state.Observe(rando.silverMqGanonWater);
    state.Observe(rando.silverMqGanonShadow);

    // Read the active seed Context, not randomizer-menu CVars. AP slot data
    // remains authoritative. OptionValue intentionally needs an explicit .Get().
    const auto& ctx = Rando::Context::GetInstance();
    for (int key = RSK_NONE + 1; key < RSK_MAX; ++key) {
        state.Observe(ctx->GetOption(static_cast<RandomizerSettingKey>(key)).Get());
    }

    for (int trick = 0; trick < RT_MAX; ++trick) {
        state.Observe(ctx->GetTrickOption(static_cast<RandomizerTrick>(trick)).Get());
    }

    if (state.EndSample()) {
        // This only queues one deferred pass. Multiple changes in a frame do
        // not run multiple searches, save files, or perform AP/network work.
        RecalculateAvailableChecks();
    }
}

void CheckTrackerWindow::InitElement() {
    SaveManager::Instance->AddInitFunction(InitTrackerData);
    sectionId = SaveManager::Instance->AddSaveFunction("trackerData", 1, SaveFile, true, SECTION_PARENT_NONE);
    SaveManager::Instance->AddLoadFunction("trackerData", 1, LoadFile);
    GameInteractor::Instance->RegisterGameHook<GameInteractor::OnLoadGame>(CheckTrackerLoadGame);
    GameInteractor::Instance->RegisterGameHook<GameInteractor::OnExitGame>([](uint32_t fileNum) { Teardown(); });
    GameInteractor::Instance->RegisterGameHook<GameInteractor::OnItemReceive>(CheckTrackerItemReceive);
    GameInteractor::Instance->RegisterGameHook<GameInteractor::OnPlayerUpdate>(CheckTrackerLiveLogicStateUpdate);
    GameInteractor::Instance->RegisterGameHook<GameInteractor::OnTransitionEnd>(CheckTrackerTransition);
    GameInteractor::Instance->RegisterGameHook<GameInteractor::OnShopSlotChange>(CheckTrackerShopSlotChange);
    GameInteractor::Instance->RegisterGameHook<GameInteractor::OnSceneFlagSet>(CheckTrackerSceneFlagSet);
    GameInteractor::Instance->RegisterGameHook<GameInteractor::OnFlagSet>(CheckTrackerFlagSet);
    GameInteractor::Instance->RegisterGameHook<GameInteractor::OnDialogMessage>(CheckTrackerDialogMessage);
    GameInteractor::Instance->RegisterGameHook<GameInteractor::OnRandoHintRevealed>(CheckTrackerHintRevealed);
}

void CheckTrackerWindow::UpdateElement() {
}

void RegisterCheckTrackerWidgets() {
    backgroundColorWidget = { .name = "Background Color##CheckTracker", .type = WidgetType::WIDGET_CVAR_COLOR_PICKER };
    backgroundColorWidget.CVar(CVAR_TRACKER_CHECK("BgColor"))
        .Options(
            ColorPickerOptions().Color(THEME_COLOR).DefaultValue(Color_Bg_Default).UseAlpha().ShowReset().ShowRandom());
    SohGui::GetSohMenu()->AddSearchWidget({ backgroundColorWidget, "Randomizer", "Check Tracker", "General Settings" });

    windowTypeWidget = { .name = "Window Type##CheckTracker", .type = WidgetType::WIDGET_CVAR_COMBOBOX };
    windowTypeWidget.CVar(CVAR_TRACKER_CHECK("WindowType"))
        .Options(ComboboxOptions()
                     .DefaultIndex(TRACKER_WINDOW_WINDOW)
                     .ComponentAlignment(ComponentAlignments::Right)
                     .LabelPosition(LabelPositions::Far)
                     .Color(THEME_COLOR)
                     .ComboMap(windowType));
    SohGui::GetSohMenu()->AddSearchWidget({ windowTypeWidget, "Randomizer", "Check Tracker", "General Settings" });

    dungeonSpoilerWidget = { .name = "Vanilla/MQ Dungeon Spoilers", .type = WidgetType::WIDGET_CVAR_CHECKBOX };
    dungeonSpoilerWidget.CVar(CVAR_TRACKER_CHECK("MQSpoilers"))
        .Options(CheckboxOptions()
                     .Color(THEME_COLOR)
                     .Tooltip("If enabled, Vanilla/MQ dungeons will show on the tracker immediately. "
                              "Otherwise, Vanilla/MQ dungeon locations must be unlocked."));
    SohGui::GetSohMenu()->AddSearchWidget({ dungeonSpoilerWidget, "Randomizer", "Check Tracker", "General Settings" });

    hideUnshuffledShopWidget = { .name = "Hide Unshuffled Shop Item Checks", .type = WidgetType::WIDGET_CVAR_CHECKBOX };
    hideUnshuffledShopWidget.CVar(CVAR_TRACKER_CHECK("HideUnshuffledShopChecks"))
        .Options(
            CheckboxOptions()
                .Color(THEME_COLOR)
                .Tooltip("If enabled, will prevent the tracker from displaying slots with non-shop-item shuffles."))
        .Callback([&](WidgetInfo& info) {
            hideShopUnshuffledChecks = CVarGetInteger(CVAR_TRACKER_CHECK("HideUnshuffledShopChecks"), 0);
            UpdateFilters();
        });
    SohGui::GetSohMenu()->AddSearchWidget(
        { hideUnshuffledShopWidget, "Randomizer", "Check Tracker", "General Settings" });

    showGSWidget = { .name = "Always Show Gold Skulltulas", .type = WidgetType::WIDGET_CVAR_CHECKBOX };
    showGSWidget.CVar(CVAR_TRACKER_CHECK("AlwaysShowGSLocs"))
        .Options(CheckboxOptions()
                     .Color(THEME_COLOR)
                     .Tooltip("If enabled, will show GS locations in the tracker regardless of tokensanity settings."))
        .Callback([&](WidgetInfo& info) {
            alwaysShowGS = !alwaysShowGS;
            UpdateFilters();
        });
    SohGui::GetSohMenu()->AddSearchWidget({ showGSWidget, "Randomizer", "Check Tracker", "General Settings" });

    showLogicWidget = { .name = "Show Logic", .type = WidgetType::WIDGET_CVAR_CHECKBOX };
    showLogicWidget.CVar(CVAR_TRACKER_CHECK("ShowLogic"))
        .Options(CheckboxOptions()
                     .Color(THEME_COLOR)
                     .Tooltip("If enabled, will show a check's logic when hovering over it."));
    SohGui::GetSohMenu()->AddSearchWidget({ showLogicWidget, "Randomizer", "Check Tracker", "General Settings" });

    checkAvailabilityWidget = { .name = "Enable Available Checks", .type = WidgetType::WIDGET_CVAR_CHECKBOX };
    checkAvailabilityWidget.CVar(CVAR_TRACKER_CHECK("EnableAvailableChecks"))
        .Options(CheckboxOptions()
                     .Color(THEME_COLOR)
                     .Tooltip("If enabled, will show the checks that are available to be collected "
                              "with your current progress."))
        .Callback([&](WidgetInfo& info) {
            enableAvailableChecks = CVarGetInteger(CVAR_TRACKER_CHECK("EnableAvailableChecks"), 0);
            if (!enableAvailableChecks) {
                CVarSetInteger(CVAR_TRACKER_CHECK("OnlyShowAvailable"), 0);
                onlyShowAvailable = false;
                recalculateAvailable = false;

                // Clear stale availability flags/counts when disabling the feature.
                const auto& ctx = Rando::Context::GetInstance();
                for (auto& location : Rando::StaticData::GetLocationTable()) {
                    ctx->GetItemLocation(location.GetRandomizerCheck())->SetAvailable(false);
                }
                RecalculateAllAreaTotals();
            } else {
                RecalculateAvailableChecks();
            }
        });
    SohGui::GetSohMenu()->AddSearchWidget(
        { checkAvailabilityWidget, "Randomizer", "Check Tracker", "General Settings" });
}

static RegisterMenuInitFunc menuInitFunc(RegisterCheckTrackerWidgets);
} // namespace CheckTracker
