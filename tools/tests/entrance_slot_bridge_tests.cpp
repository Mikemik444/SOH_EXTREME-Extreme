// Real exported slot JSON -> production parser -> AP runtime -> native tables.
// Engine allocation, actor collision and CVar IO are isolated. Routing code is
// extracted unchanged from production by test_entrance_slot_bridge.py.
#include <algorithm>
#include <array>
#include <cassert>
#include <cmath>
#include <cfloat>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <iterator>
#include <limits>
#include <map>
#include <set>
#include <string>
#include <string.h>
#include <unordered_map>
#include <vector>
#include "soh/Network/Archipelago/ArchipelagoC.h"
#include "json.hpp"

using u8 = uint8_t;
using s8 = int8_t;
using s16 = int16_t;
using u16 = uint16_t;
using s32 = int32_t;
using u32 = uint32_t;
using f32 = float;
enum SceneID {
#define DEFINE_SCENE(segment, title, id, ...) id,
#include "scene_table.h"
#undef DEFINE_SCENE
    SCENE_MAX,
    SCENE_UNUSED_6E = SCENE_MAX // z64scene.h aliases the unused final scene ID.
};
enum EntranceIndex {
#define DEFINE_ENTRANCE(id, ...) id,
#include "entrance_table.h"
#undef DEFINE_ENTRANCE
    ENTR_MAX
};
#define RANDO_ENUM_BEGIN(name) enum name {
#define RANDO_ENUM_ITEM(name) name,
#define RANDO_ENUM_END(name) };
#include "soh/Enhancements/randomizer/randomizerEnums/RandomizerSettingKey.h"
#include "soh/Enhancements/randomizer/randomizerEnums/RandomizerOptions.h"
#undef RANDO_ENUM_BEGIN
#undef RANDO_ENUM_ITEM
#undef RANDO_ENUM_END
#include "captured_engine_constants.h"
#include "captured_native_constants.h"

struct Vec3s { s16 x = 0, y = 0, z = 0; };
struct Vec3f { float x = 0, y = 0, z = 0; };
struct Actor {
    struct { Vec3f pos; } world;
    struct { Vec3s rot; } shape;
    int id = 0, category = 0, params = 0;
};
struct ActorEntry { Vec3s pos, rot; s16 params = 0; };
struct Player { Actor actor; int doorType = 0; } player;
struct TransitionActorEntry {
    struct { int room = -1; } sides[2];
    int id = 0, params = 0;
    Vec3s pos;
    s16 rotY = 0;
};
struct PlayState {
    struct { bool running = true; } state;
    int sceneNum = SCENE_TEMPLE_OF_TIME;
    int numRooms = 64;
    struct { int state = 0; } gameOverCtx;
    struct { struct { int num = 0; } curRoom; } roomCtx;
    struct { TransitionActorEntry* list = nullptr; int numActors = 0; } transiActorCtx;
    ActorEntry* linkActorEntry = nullptr;
    int nextEntranceIndex = 0, transitionTrigger = 0, transitionType = 0;
} play, *gPlayState = &play;
struct SaveContext {
    int health = 48, gameMode = 0, respawnFlag = 0, cutsceneIndex = 0, nextCutsceneIndex = 0;
    int cutsceneTrigger = 0;
    int entranceIndex = ENTR_LINKS_HOUSE_CHILD_SPAWN, nextTransitionType = 0;
    int savedSceneNum = SCENE_TEMPLE_OF_TIME;
    int fileNum = 0;
    struct {
        int tempSwchFlags = 0, tempCollectFlags = 0, entranceIndex = 0, data = 0;
        int roomIndex = 0, playerParams = 0, yaw = 0;
        Vec3f pos;
    } respawn[RESPAWN_MODE_MAX];
} gSaveContext;
enum {
    GAMEMODE_NORMAL = 0, GAMEOVER_INACTIVE = 0,
    TRANS_TRIGGER_OFF = 0, TRANS_TRIGGER_START = 1,
    ENTR_LOAD_OPENING = -1, ENTR_RETURN_GROTTO = 0x7FFF,
};
struct EntranceInfo { u8 scene; u8 spawn; u16 field; };
EntranceInfo gEntranceTable[ENTR_MAX] = {
#define DEFINE_ENTRANCE(id, scene, spawn, continueBgm, titleCard, startType, endType) \
    {scene, spawn, ENTRANCE_INFO_FIELD(continueBgm, titleCard, endType, startType)},
#include "entrance_table.h"
#undef DEFINE_ENTRANCE
};
#include "captured_native_structs.h"
bool currentSaveIsAP = true, child = true, isRandomizer = true;
namespace Rando {
struct TestOption {
    int value = 0;
    void Set(int next) { value = next; }
};
struct Context {
    TestOption options[RSK_MAX];
    TestOption& GetOption(RandomizerSettingKey key) { return options[key]; }
    static Context* GetInstance() { static Context instance; return &instance; }
};
}
#define LINK_IS_CHILD child
#define LINK_IS_ADULT (!child)
#define IS_RANDO isRandomizer
#define RAND_GET_OPTION(key) (Rando::Context::GetInstance()->GetOption(key).value)
#define GET_PLAYER(play) (static_cast<void>(play), &::player)
template <typename... Args> void TestLog(Args&&...) {}
#define SPDLOG_ERROR(...) TestLog(__VA_ARGS__)
#define SPDLOG_INFO(...) TestLog(__VA_ARGS__)
#define SPDLOG_WARN(...) TestLog(__VA_ARGS__)
#define CVAR_ENHANCEMENT(name) name
int CVarGetInteger(const char*, int fallback) { return fallback; }
uint8_t Randomizer_GetSettingValue(RandomizerSettingKey key) { return RAND_GET_OPTION(key); }
EntranceOverride overrides[ENTRANCE_OVERRIDES_MAX_COUNT]{};
EntranceOverride* Randomizer_GetEntranceOverrides() { return overrides; }
void Grotto_InitExitAndLoadLists(void);
void Grotto_SetExitOverride(s16 originalIndex, s16 overrideIndex);
void Grotto_SetLoadOverride(s16 originalIndex, s16 overrideIndex);
s16 Grotto_GetEntranceValueHandlingGrottoRando(s16 nextEntranceIndex);
s16 Grotto_OverrideSpecialEntrance(s16 nextEntranceIndex);
void Entrance_SetEntranceDiscovered(u16, u8) {}
void EntranceTracker_SetLastEntranceOverride(s16) {}
void EntranceTracker_SetCurrentGrottoID(s8) {}
bool Archipelago_IsCurrentSaveFile() { return currentSaveIsAP; }
extern "C" bool Archipelago_EntranceShuffleActive(void);
float Math_SinS(s16 yaw) { return std::sin(yaw * 3.14159265358979323846f / 32768.0f); }
float Math_CosS(s16 yaw) { return std::cos(yaw * 3.14159265358979323846f / 32768.0f); }

// Includes the complete native Entrance_Init and all of its local helpers.
#include "captured_native_init.inc"
#include "soh/Network/Archipelago/SceneTransitionChecks.h"
#include "soh/Network/Archipelago/EntranceRuntime.inc"
#include "captured_grotto_data.inc"
#include "captured_grotto_functions.inc"
#include "captured_native_lookup.inc"
#include "captured_native_savewarp.inc"
#include "captured_save_menu_spawn.inc"
#include "captured_slot_parser.inc"

namespace CheckTracker { void RecalculateAvailableChecks() {} }
SohExtreme::CrossingJournal gCrossingJournal;
class ArchipelagoClient {
  public:
    bool checksEnabled = true, sessionActive = true;
    int64_t inactiveLocation = 0;
    std::vector<int64_t> reports;
    bool HasSceneTransitionChecks() const { return checksEnabled; }
    bool IsGameplaySessionActive() const { return sessionActive; }
    bool IsLocationActive(int64_t location) const { return location != inactiveLocation; }
    bool IsLocationSubmitted(int64_t location) const {
        return std::find(reports.begin(), reports.end(), location) != reports.end();
    }
    void SendLocation(int64_t location, bool) { reports.push_back(location); }
    void ReportTransition(int64_t);
    void CaptureSceneTransition();
    void CompleteSceneTransition(int16_t);
    void BeginDoorTransition(int, int, int, const Actor*, int);
    void AdvanceDoorTransition();
} doorClient;
#include "captured_client_crossings.inc"
enum { ACTORCAT_DOOR = 1, ACTORCAT_BG = 2, PLAYER_DOORTYPE_SLIDING = 1,
       PLAYER_DOORTYPE_HANDLE = 2, PLAYER_DOORTYPE_FAKE = 3 };
#define GET_TRANSITION_ACTOR_INDEX(actor) ((static_cast<uint16_t>((actor)->params)) >> 10)
int roomRequests = 0;
template <typename RoomContext> void Room_RequestNewRoom(PlayState*, RoomContext* room, int target) {
    ++roomRequests;
    room->curRoom.num = target;
}
void Archipelago_BeginDoorTransition(int door, int from, int to, const Actor* actor, int side) {
    doorClient.BeginDoorTransition(door, from, to, actor, side);
}
void DispatchPlayerDoor(Player* playerActor, PlayState* play, Actor* doorActor, int doorDirection) {
    int frontRoom;
#include "captured_player_door_dispatch.inc"
}
struct DoorShutter { struct { Actor actor; } dyna; int gfxType = 3; };
struct ShutterInfo { int e = 50, f = 15; } sShutterInfo[4];
bool Player_InCsMode(PlayState*) { return false; }
enum { VB_BE_NEAR_DOOR_SHUTTER = 1 };
template <typename... Args> bool GameInteractor_Should(int, bool vanilla, Args...) { return vanilla; }
#include "captured_actor_coordinates.inc"
#define ABS(value) std::abs(value)
#include "captured_shutter_side.inc"

void RunLoadSpawnHook() {
    Archipelago_CancelPendingEntranceSpawn();
    Entrance_Init();
#include "captured_load_spawn_gate.inc"
}

using SettingsMap = std::unordered_map<std::string, int>;
SettingsMap ParseSettings(const std::string& raw) {
    std::unordered_map<std::string, int64_t> parsed;
    assert(ParseFlatStringIntObject(raw, parsed));
    SettingsMap settings;
    for (const auto& [key, value] : parsed) {
        assert(value >= std::numeric_limits<int>::min() && value <= std::numeric_limits<int>::max());
        settings.emplace(key, static_cast<int>(value));
    }
    return settings;
}

void ApplyNativeOptionInputs(const SettingsMap& settings) {
    // CVar IO is isolated, using suffixes captured from the actual native option
    // declarations; the non-CVar derived entrance flag must be restored by Apply.
    static const std::pair<RandomizerSettingKey, const char*> nativeKeys[] = {
#include "captured_native_cvars.inc"
    };
    auto* context = Rando::Context::GetInstance();
    for (auto& option : context->options) option.Set(0);
    for (const auto& [key, suffix] : nativeKeys) {
        const auto found = settings.find(suffix);
        if (found != settings.end()) context->GetOption(key).Set(found->second);
    }
}

void ResetSave() {
    SohExtreme::EntranceRuntime::Reset();
    gPlayState = &play;
    play = {};
    gSaveContext = {};
    currentSaveIsAP = true;
    isRandomizer = true;
    for (auto& value : overrides) value = {};
    Entrance_ResetEntranceTable();
    Entrance_Init();
}

int NativeDestination(int source) {
    if (source >= ENTRANCE_GROTTO_EXIT_START && source < ENTRANCE_GROTTO_EXIT_START + NUM_GROTTOS)
        return grottoExitList[source - ENTRANCE_GROTTO_EXIT_START];
    if (source >= ENTRANCE_GROTTO_LOAD_START && source < ENTRANCE_GROTTO_LOAD_START + NUM_GROTTOS)
        return grottoLoadList[source - ENTRANCE_GROTTO_LOAD_START];
    if (source >= 0 && source < ENTR_MAX) return entranceOverrideTable[source];
    return Archipelago_EntranceDestination(source); // Room doors use the AP crossing dispatcher.
}

int ResolvedEntrance(int target) {
    const auto* row = SohExtreme::EntranceEndpointById(target);
    assert(row);
    if (row->door >= 0) return row->anchor;
    if (target >= ENTRANCE_GROTTO_LOAD_START && target < ENTRANCE_GROTTO_LOAD_START + NUM_GROTTOS)
        return grottoLoadTable[target - ENTRANCE_GROTTO_LOAD_START].entranceIndex;
    if (target >= ENTRANCE_GROTTO_EXIT_START && target < ENTRANCE_GROTTO_EXIT_START + NUM_GROTTOS)
        return grottoReturnTable[target - ENTRANCE_GROTTO_EXIT_START].entranceIndex;
    return target;
}

void FinishSceneAt(const SohExtreme::EntranceEndpoint* target) {
    using namespace SohExtreme::EntranceRuntime;
    play.sceneNum = target->scene;
    play.transitionTrigger = TRANS_TRIGGER_OFF;
    play.nextEntranceIndex = 0;
    play.roomCtx.curRoom.num = Archipelago_EntranceSpawnRoom(target->scene, 0);
    static ActorEntry vanillaEntry;
    vanillaEntry = {};
    play.linkActorEntry = &vanillaEntry;
    const bool moved = Archipelago_EntranceSpawnPosition(target->scene);
    assert(moved == (target->door >= 0));
    if (target->door >= 0) assert(play.roomCtx.curRoom.num == target->room);
    assert(Complete(target->scene) == 0); // Spawn is not a physical traversal check.
}

nlohmann::json VerifyDoors(bool shuffled) {
    using namespace SohExtreme;
    using namespace SohExtreme::EntranceRuntime;
    struct DoorActorFixture { int id, actor, params; };
    constexpr DoorActorFixture actors[] = {
#include "captured_door_actors.inc"
    };
    assert(std::size(actors) == 421);
    size_t ordinaryCases = 0, nearPlaneCases = 0, exactPlaneCases = 0, jabuCases = 0;
    size_t abortedCases = 0, failedArrivalCases = 0;
    size_t localCarrierDirections = 0, localCarrierCases = 0;
    std::map<int, size_t> actorFamilies;
    for (const auto& fixture : actors) {
        const auto* row = EntranceEndpointById(fixture.id);
        const auto* target = EntranceEndpointById(shuffled ? routing.Destination(row->id) : row->id);
        assert(row && row->door >= 0 && target);
        ++actorFamilies[fixture.actor];
        if (IsLocalCarrierDoor(row->id)) ++localCarrierDirections;
        const bool shouldWarp = shuffled && !IsLocalCarrierDoor(row->id);
        if (shuffled && IsLocalCarrierDoor(row->id)) assert(target->id == row->id);
        // At exactly zero, native facing uses the unflipped orientation while
        // the returned side uses positive Z (its comparisons are >0 and >=0).
        const int boundaries = fixture.actor == 46 ? (row->side == 1 ? 3 : 2) : 1;
        for (int boundary = 0; boundary < boundaries; ++boundary) {
            std::array<TransitionActorEntry, 64> transitions{};
            assert(row->door < static_cast<int>(transitions.size()));
            auto& portal = transitions[row->door];
            portal.sides[row->side].room = row->fromRoom;
            portal.sides[1 - row->side].room = row->room;
            portal.id = fixture.actor;
            DoorShutter shutter;
            shutter.gfxType = row->scene == SCENE_JABU_JABU ? 3 : 0;
            auto& actor = shutter.dyna.actor;
            actor.id = fixture.actor;
            actor.category = ACTORCAT_DOOR;
            actor.params = fixture.params | (row->door << 10);
            actor.world.pos = {static_cast<float>(row->x), static_cast<float>(row->y), static_cast<float>(row->z)};
            actor.shape.rot.y = static_cast<s16>(row->yaw);
            const int direction = row->side == 1 ? 1 : -1;
            const float start = direction * (boundary == 0 ? 22.0f : boundary == 1 ? 0.5f : 0.0f);
            const float nx = Math_SinS(actor.shape.rot.y), nz = Math_CosS(actor.shape.rot.y);
            player.actor.shape.rot.y = static_cast<s16>(row->yaw + (direction > 0 && boundary != 2 ? 0x8000 : 0));
            player.doorType = fixture.actor == 46 ? PLAYER_DOORTYPE_SLIDING : PLAYER_DOORTYPE_HANDLE;
            const auto position = [&](float distance) {
                player.actor.world.pos = {row->x + nx * distance,
                                          static_cast<float>(row->y - (shutter.gfxType == 3 ? 80 : 0)),
                                          row->z + nz * distance};
            };
            const auto expectIdle = [&] {
                assert(doorClient.reports.empty() && play.transitionTrigger == TRANS_TRIGGER_OFF);
            };
            const auto openDoor = [&] {
                CancelTransition();
                gCrossingJournal.Reset();
                play = {};
                gPlayState = &play;
                gSaveContext = {};
                doorClient.reports.clear();
                doorClient.checksEnabled = doorClient.sessionActive = true;
                doorClient.inactiveLocation = 0;
                play.transiActorCtx.list = transitions.data();
                play.transiActorCtx.numActors = static_cast<int>(transitions.size());
                play.sceneNum = row->sourceScene;
                play.roomCtx.curRoom.num = row->fromRoom;
                position(start);
                if (fixture.actor == 46) {
                    // The actual native side selector accepts these near-plane
                    // openings. Locks have already authorized this action.
                    const int nativeSide = DoorShutter_GetPlayerSide(&shutter, &play);
                    if (nativeSide != direction) {
                        std::cerr << "Fixture opening was not accepted: id=" << row->id << " start=" << start
                                  << " expected_side=" << direction << " native_side=" << nativeSide << "\n";
                    }
                    assert(nativeSide == direction);
                }
                roomRequests = 0;
                DispatchPlayerDoor(&player, &play, &actor, direction);
                if (shuffled && IsLocalCarrierDoor(row->id)) assert(!openedDoor);
                assert(play.roomCtx.curRoom.num == row->room);
                assert(roomRequests == (row->fromRoom != row->room));
                expectIdle(); // An accepted open action alone never awards.
                doorClient.AdvanceDoorTransition();
                expectIdle(); // The new room may load before Link crosses.
                position(direction * 30.0f);
                doorClient.AdvanceDoorTransition();
                expectIdle(); // Further movement on the starting side.
                position(-direction * 2.0f);
                doorClient.AdvanceDoorTransition();
                expectIdle(); // Crossing the plane alone is insufficient.
            };
            openDoor();
            position(-direction * 22.0f);
            doorClient.AdvanceDoorTransition();
            if (shouldWarp) {
                if (play.transitionTrigger != TRANS_TRIGGER_START) {
                    std::cerr << "Missing accepted door traversal: id=" << row->id << " scene=" << row->scene
                              << " door=" << row->door << " start=" << start << "\n";
                }
                assert(play.transitionTrigger == TRANS_TRIGGER_START);
                assert(play.nextEntranceIndex == ResolvedEntrance(target->id));
                assert(doorClient.reports.empty()); // Award only after arrival.
                doorClient.CaptureSceneTransition();
                doorClient.CompleteSceneTransition(target->scene);
            } else {
                assert(play.transitionTrigger == TRANS_TRIGGER_OFF);
            }
            assert(doorClient.reports == std::vector<int64_t>{row->check});
            doorClient.AdvanceDoorTransition();
            doorClient.CompleteSceneTransition(target->scene);
            assert(doorClient.reports.size() == 1);

            // Each cancellation invalidates the accepted open. Restoring the
            // old scene/room or reviving Link cannot revive a stale crossing.
            for (int cancel = 0; cancel < 4; ++cancel) {
                openDoor();
                if (cancel == 0) gSaveContext.health = 0;
                if (cancel == 1) { CancelTransition(); gCrossingJournal.Reset(); }
                if (cancel == 2) play.sceneNum = row->sourceScene + 1;
                if (cancel == 3) play.roomCtx.curRoom.num = 100;
                position(-direction * 22.0f);
                doorClient.AdvanceDoorTransition();
                expectIdle();
                gSaveContext.health = 48;
                play.sceneNum = row->sourceScene;
                play.roomCtx.curRoom.num = row->room;
                doorClient.AdvanceDoorTransition();
                expectIdle();
                doorClient.CompleteSceneTransition(target->scene);
                expectIdle();
                ++abortedCases;
            }
            if (shouldWarp) {
                openDoor();
                position(-direction * 22.0f);
                doorClient.AdvanceDoorTransition();
                assert(play.transitionTrigger == TRANS_TRIGGER_START);
                doorClient.CaptureSceneTransition();
                doorClient.CompleteSceneTransition(target->scene == 0 ? 1 : 0);
                assert(doorClient.reports.empty());
                doorClient.CompleteSceneTransition(target->scene);
                assert(doorClient.reports.empty());
                ++failedArrivalCases;
            }
            if (boundary == 0) ++ordinaryCases;
            if (boundary == 1) ++nearPlaneCases;
            if (boundary == 2) ++exactPlaneCases;
            if (row->scene == SCENE_JABU_JABU) ++jabuCases;
            if (IsLocalCarrierDoor(row->id)) ++localCarrierCases;
        }
    }
    assert(actorFamilies[46] == 307 && actorFamilies[9] == 114);
    assert(ordinaryCases == 421 && nearPlaneCases == 307 && exactPlaneCases > 100 && jabuCases >= 60);
    assert(abortedCases == (ordinaryCases + nearPlaneCases + exactPlaneCases) * 4);
    assert(localCarrierDirections == 12 && localCarrierCases == 30);
    play.transiActorCtx = {};
    return {{"shuffled", shuffled}, {"ordinary_openings", ordinaryCases},
            {"accepted_near_plane_openings", nearPlaneCases}, {"accepted_exact_plane_openings", exactPlaneCases},
            {"jabu_cases", jabuCases}, {"canceled_or_dead_crossings_rejected", abortedCases},
            {"local_carrier_directions", localCarrierDirections}, {"local_carrier_check_cases", localCarrierCases},
            {"wrong_arrivals_rejected", failedArrivalCases},
            {"shutter_directions", actorFamilies[46]}, {"handle_directions", actorFamilies[9]}};
}

nlohmann::json VerifyFixture(const char* path) {
    using namespace SohExtreme;
    using namespace SohExtreme::EntranceRuntime;
    std::ifstream input(path);
    assert(input);
    const std::string raw((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
    const auto settings = ParseSettings(raw);
    assert(settings.at("EntranceRandomizerRevision") == 1);
    assert(settings.at("ShuffleOverworldEntrances") == 1);
    assert(settings.at("ShuffleOverworldSpawns") == 1);
    assert(settings.at("SceneTransitionChecks") == 1);
    ResetSave();
    ApplyNativeOptionInputs(settings);
    assert(!RAND_GET_OPTION(RSK_SHUFFLE_ENTRANCES));
    assert(Apply(settings));
    assert(RAND_GET_OPTION(RSK_SHUFFLE_ENTRANCES) && Archipelago_EntranceShuffleActive());
    assert(routing.Routes().size() == 719);
    size_t sceneRows = 0, changedRows = 0, sceneLookups = 0, coupledRows = 0;
    for (const auto& [source, targetId] : routing.Routes()) {
        const auto* sourceRow = EntranceEndpointById(source);
        const auto* target = EntranceEndpointById(targetId);
        assert(sourceRow && target);
        assert(NativeDestination(source) == targetId);
        if (source != targetId) ++changedRows;
        if (sourceRow->door < 0) ++sceneRows;
        if (sourceRow->reverse >= 0) {
            assert(NativeDestination(target->reverse) == sourceRow->reverse);
            ++coupledRows;
        }
        if (source >= 0 && source < ENTR_MAX) {
            CancelTransition();
            play.sceneNum = sourceRow->sourceScene;
            play.nextEntranceIndex = 0;
            gSaveContext.respawnFlag = 0;
            const int resolved = Entrance_OverrideNextIndex(source);
            assert(resolved == ResolvedEntrance(targetId));
            ++sceneLookups;
        }
    }
    assert(sceneRows == 298 && sceneRows < ENTRANCE_OVERRIDES_MAX_COUNT && changedRows > 500);
    assert(sceneLookups > 200 && coupledRows > 650);
    size_t dynamicLookups = 0;
    for (size_t i = 0; i < std::size(dynamicExitList); ++i) {
        const int source = dynamicExitList[i];
        assert(routing.Contains(source));
        CancelTransition();
        play.nextEntranceIndex = 0;
        const int target = routing.Destination(source);
        assert(Entrance_OverrideDynamicExit(static_cast<s16>(i)) == ResolvedEntrance(target));
        ++dynamicLookups;
    }
    constexpr int overworldIds[] = {
#include "captured_overworld_ids.inc"
    };
    assert(std::size(overworldIds) == 52);
    for (int source : overworldIds) assert(NativeDestination(source) != source);
    // The Temple of Time exterior, mountain summit -> crater, and city entry
    // all execute through the same complete native table used above.
    const int templeExit = ENTR_TEMPLE_OF_TIME_EXTERIOR_DAY_OUTSIDE_TEMPLE;
    assert(NativeDestination(templeExit) != templeExit);
    assert(NativeDestination(ENTR_DEATH_MOUNTAIN_CRATER_UPPER_EXIT) != ENTR_DEATH_MOUNTAIN_CRATER_UPPER_EXIT);
    assert(NativeDestination(ENTR_GORON_CITY_UPPER_EXIT) != ENTR_GORON_CITY_UPPER_EXIT);
    const auto doorCases = VerifyDoors(true);

    nlohmann::json ages = nlohmann::json::array();
    for (int age : {LINK_AGE_CHILD, LINK_AGE_ADULT}) {
        child = age == LINK_AGE_CHILD;
        const int source = child ? ENTR_LINKS_HOUSE_CHILD_SPAWN : ENTR_HYRULE_FIELD_10;
        const auto* target = EntranceEndpointById(settings.at("EntranceMap." + std::to_string(source)));
        assert(target && target->scene != (child ? SCENE_LINKS_HOUSE : SCENE_TEMPLE_OF_TIME));
        const int resolved = ResolvedEntrance(target->id);
        for (int reload = 0; reload < 3; ++reload) {
            // Save metadata resets per-save state before applying the cached JSON.
            ResetSave();
            ApplyNativeOptionInputs(settings);
            assert(Apply(ParseSettings(raw)));
            gPlayState = nullptr;
            gSaveContext.cutsceneIndex = 0xFFF1;
            RunLoadSpawnHook();
            assert(gSaveContext.entranceIndex == resolved);
            assert(pendingSpawnAge == -1 && suppressTransitionChecks && gSaveContext.cutsceneIndex == 0);
            gPlayState = &play;
            FinishSceneAt(target);
            assert(GetAgeSpawnEntrance(age) == resolved);
            FinishSceneAt(target);
        }
        // Native load hook occurs before uncached slot data arrives.
        ResetSave();
        gPlayState = nullptr;
        RunLoadSpawnHook();
        assert(pendingSpawnAge == age && !slotMapLoaded);
        gPlayState = &play;
        ApplyNativeOptionInputs(settings);
        assert(Apply(ParseSettings(raw)));
        assert(!ServicePendingSpawn(false));
        assert(ServicePendingSpawn(true) && play.nextEntranceIndex == resolved);
        assert(pendingSpawnAge == -1);
        FinishSceneAt(target);
        for (int reconnect = 0; reconnect < 3; ++reconnect) {
            ApplyNativeOptionInputs(settings);
            assert(Apply(ParseSettings(raw)));
            assert(!ServicePendingSpawn(true));
        }
        ages.push_back({{"age", child ? "child" : "adult"}, {"target", target->id},
                        {"scene", target->scene}, {"room", target->room},
                        {"native_entrance", resolved}, {"cached_loads", 3},
                        {"save_menu_returns", 3}, {"late_load_transitions", 1}});
    }
    return {{"fixture", path}, {"settings", settings.size()}, {"routes", routing.Routes().size()},
            {"scene_rows", sceneRows}, {"native_scene_lookups", sceneLookups},
            {"native_dynamic_lookups", dynamicLookups},
            {"changed_routes", changedRows}, {"coupled_returns", coupledRows},
            {"changed_overworld_routes", std::size(overworldIds)}, {"spawn_cases", ages},
            {"door_cases", doorCases}};
}

void VerifyInvalidMaps() {
    using namespace SohExtreme;
    using namespace SohExtreme::EntranceRuntime;
    ResetSave();
    assert(Apply({{"EntranceRandomizerRevision", 1}, {"EntranceMap.187", 343}}));
    const auto accepted = routing.Routes();
    for (const SettingsMap& invalid : {
        SettingsMap{{"ShuffleOverworldEntrances", 1}},
        SettingsMap{{"EntranceRandomizerRevision", 0}, {"ShuffleOverworldSpawns", 1}},
        SettingsMap{{"EntranceMap.187", 343}},
        SettingsMap{{"EntranceRandomizerRevision", 1}},
        SettingsMap{{"EntranceRandomizerRevision", 99}, {"EntranceMap.187", 343}},
    }) {
        assert(!Apply(invalid));
        assert(routing.Routes() == accepted && NativeDestination(187) == 343);
    }
    size_t protectedRejections = 0;
    for (const auto& row : kEntranceEndpoints) {
        if (!IsLocalCarrierDoor(row.id)) continue;
        // Even a legacy seed's otherwise paired map must not reload a room
        // on a carrier-critical door and delete its held Ruto actor.
        const SettingsMap invalid{{"EntranceRandomizerRevision", 1},
                                  {"EntranceMap." + std::to_string(row.id), row.reverse}};
        std::string error;
        EntranceRouting validation;
        assert(!validation.Configure(invalid, error));
        assert(error.find("carry Ruto") != std::string::npos);
        assert(!Apply(invalid));
        assert(routing.Routes() == accepted && NativeDestination(187) == 343);
        ++protectedRejections;
    }
    assert(protectedRejections == 12);
    assert(Apply({{"EntranceRandomizerRevision", 0}, {"ShuffleOverworldEntrances", 0},
                  {"ShuffleOverworldSpawns", 0}}));
    assert(!routing.Active() && !RAND_GET_OPTION(RSK_SHUFFLE_ENTRANCES));
    assert(NativeDestination(187) == 187 && NativeDestination(642) == 642);
    assert(Apply({})); // A true old all-off slot remains valid.
    assert(!routing.Active());
    VerifyDoors(false);

    std::unordered_map<std::string, int64_t> parsed{{"keep", 1}};
    const auto original = parsed;
    for (const std::string raw : {"[]", "{\"EntranceRandomizerRevision\":true}",
                                  "{\"EntranceMap.187\":3.5}", "{\"x\":9223372036854775808}"}) {
        assert(!ParseFlatStringIntObject(raw, parsed));
        assert(parsed == original);
    }
}

int main(int argc, char** argv) {
    assert(argc >= 2);
    nlohmann::json cases = nlohmann::json::array();
    for (int i = 1; i < argc; ++i) cases.push_back(VerifyFixture(argv[i]));
    VerifyInvalidMaps();
    std::cout << cases.dump(2) << '\n';
}
