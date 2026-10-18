// Executes the production AP router and transition-reporting methods with
// isolated engine IO. This does not simulate game collision or a playthrough.
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <map>
#include <string>
#include <unordered_map>
#include <vector>
#include "captured_entrance_capacity.h"
#include "captured_overworld_endpoints.h"
#include "../../soh/Network/Archipelago/SceneTransitionChecks.h"

using s16 = int16_t;
struct Vec3s { s16 x = 0, y = 0, z = 0; };
struct Vec3f { float x = 0, y = 0, z = 0; };
struct Actor {
    struct { Vec3f pos; } world;
    struct { Vec3s rot; } shape;
};
struct ActorEntry { Vec3s pos, rot; s16 params = 0; };
struct Player { Actor actor; } player;
struct PlayState {
    struct { bool running = true; } state;
    int sceneNum = 52;
    struct { int state = 0; } gameOverCtx;
    struct { struct { int num = 0; } curRoom; } roomCtx;
    ActorEntry* linkActorEntry = nullptr;
    int nextEntranceIndex = 0, transitionTrigger = 0, transitionType = 0;
} play, *gPlayState = &play;
struct SaveContext {
    int health = 48, gameMode = 0, respawnFlag = 0, cutsceneIndex = 0, nextCutsceneIndex = 0, entranceIndex = 187;
    int cutsceneTrigger = 0;
    struct { int tempSwchFlags = 0, tempCollectFlags = 0, entranceIndex = 0, data = 0; } respawn[4];
} gSaveContext;
enum {
    GAMEMODE_NORMAL = 0, GAMEOVER_INACTIVE = 0, TRANS_TRIGGER_OFF = 0, TRANS_TRIGGER_START = 1,
    TRANS_TYPE_FADE_BLACK_FAST = 1, RESPAWN_MODE_RETURN = 2,
    ENTR_LINKS_HOUSE_CHILD_SPAWN = 187, ENTR_HYRULE_FIELD_10 = 642,
    LINK_AGE_ADULT = 0, LINK_AGE_CHILD = 1,
    ENTR_MAX = 0x614, ENTRANCE_TABLE_SIZE = ENTR_MAX, ENTR_LINKS_HOUSE_1 = 626,
    ENTR_ZORAS_RIVER_WEST_EXIT = 234, ENTR_HYRULE_FIELD_RIVER_EXIT = 385,
    ENTR_CASTLE_GROUNDS_RAINBOW_BRIDGE_EXIT = 573,
    // The uploaded checkout omits these engine table headers. Values verified in:
    // https://github.com/HarbourMasters/Shipwright/blob/develop/soh/include/tables/entrance_table.h
    // https://github.com/HarbourMasters/Shipwright/blob/develop/soh/include/tables/scene_table.h
    ENTR_ZORAS_RIVER_3 = 0x1D9, ENTR_HYRULE_FIELD_14 = 0x311,
    SCENE_CASTLE_COURTYARD_GUARDS_DAY = 0x45, SCENE_CASTLE_COURTYARD_GUARDS_NIGHT = 0x46,
    RSK_SHUFFLE_ENTRANCES = 0, RSK_DECOUPLED_ENTRANCES = 1,
    RO_GENERIC_OFF = 0, RO_GENERIC_ON = 1
};
struct EntranceInfo { int scene = 0, spawn = 0; } gEntranceTable[ENTR_MAX];
bool currentSaveIsAP = true;
bool child = true;
namespace Rando {
struct TestOption {
    int value = 0;
    void Set(int next) { value = next; }
};
struct Context {
    TestOption options[2];
    TestOption& GetOption(int index) { return options[index]; }
    static Context* GetInstance() { static Context instance; return &instance; }
};
}
#define LINK_IS_CHILD child
#define GET_PLAYER(play) (&::player)
template <typename... Args> void TestLog(Args&&...) {}
#define SPDLOG_ERROR(...) TestLog(__VA_ARGS__)
struct EntranceOverride { uint16_t type; int16_t index, destination, override, overrideDestination; };
EntranceOverride overrides[ENTRANCE_OVERRIDES_MAX_COUNT]{};
EntranceOverride* Randomizer_GetEntranceOverrides() { return overrides; }
int entranceInitializations = 0;
std::map<s16, s16> entranceOverrideTable;
void Entrance_Init() {
    ++entranceInitializations;
    entranceOverrideTable.clear();
    for (s16 i = 0; i < ENTR_MAX; ++i) entranceOverrideTable[i] = i;
    for (const auto& row : overrides) {
        if (row.index == 0 && row.destination == 0 && row.override == 0 && row.overrideDestination == 0) continue;
        if (row.index >= ENTR_MAX) continue; // Grotto state is isolated engine IO.
        s16 originalIndex = row.index, overrideIndex = row.override;
        entranceOverrideTable[originalIndex] = overrideIndex;
        // This alias initialization block is extracted from production Entrance_Init.
#include "captured_native_water_aliases.inc"
    }
}
int lastNativeLookup = -1, lastDiscovered = -1, lastTracked = -1;
s16 Entrance_GetOverride(s16 index) {
    lastNativeLookup = index;
    const auto found = entranceOverrideTable.find(index);
    return found == entranceOverrideTable.end() ? index : found->second;
}
void Entrance_SetEntranceDiscovered(uint16_t index, uint8_t) { lastDiscovered = index; }
void EntranceTracker_SetLastEntranceOverride(s16 index) { lastTracked = index; }
bool Archipelago_IsCurrentSaveFile() { return currentSaveIsAP; }
float Math_SinS(s16 yaw) { return std::sin(yaw * 3.14159265358979323846f / 32768.0f); }
float Math_CosS(s16 yaw) { return std::cos(yaw * 3.14159265358979323846f / 32768.0f); }
extern "C" int Archipelago_ResolveDoorArrival(int, bool);
extern "C" int Archipelago_ResolvedEntranceArrival(int, int);
s16 Grotto_OverrideSpecialEntrance(s16 target) {
    const int resolved = Archipelago_ResolveDoorArrival(target, false);
    return static_cast<s16>(Archipelago_ResolvedEntranceArrival(target, resolved));
}
#include "../../soh/Network/Archipelago/EntranceRuntime.inc"
// Execute the real native scene override, including its courtyard exception.
#include "captured_native_scene_override.inc"

SohExtreme::CrossingJournal gCrossingJournal;
class ArchipelagoClient {
public:
    std::vector<int64_t> reports;
    bool HasSceneTransitionChecks() const { return true; }
    bool IsGameplaySessionActive() const { return true; }
    bool IsLocationActive(int64_t) const { return true; }
    void AdvanceDoorTransition() {}
    void ReportTransition(int64_t location) { if (location) reports.push_back(location); }
    void CaptureSceneTransition();
    void CompleteSceneTransition(int16_t);
};
// The runner extracts these two complete methods from ArchipelagoClient.cpp.
#include "captured_scene_methods.inc"

void SceneInit(int scene) {
    gPlayState->sceneNum = scene;
    gPlayState->roomCtx.curRoom.num = 0;
    gPlayState->transitionTrigger = TRANS_TRIGGER_OFF;
    static ActorEntry vanillaEntry;
    vanillaEntry = {};
    gPlayState->linkActorEntry = &vanillaEntry;
    if (Rando::Context::GetInstance()->GetOption(RSK_SHUFFLE_ENTRANCES).value ||
        Archipelago_EntranceShuffleActive()) {
        gPlayState->roomCtx.curRoom.num = Archipelago_EntranceSpawnRoom(scene, 0);
        Archipelago_EntranceSpawnPosition(scene);
    }
}

void TestFullCatalog() {
    using namespace SohExtreme;
    using namespace SohExtreme::EntranceRuntime;
    std::unordered_map<std::string, int> settings{{"EntranceRandomizerRevision", 1}};
    size_t sceneSources = 0;
    for (const auto& row : kEntranceEndpoints) {
        settings["EntranceMap." + std::to_string(row.id)] = row.id;
        if (row.door < 0) ++sceneSources;
    }
    assert(std::size(kEntranceEndpoints) == 719 && sceneSources == 298);
    assert(sceneSources < ENTRANCE_OVERRIDES_MAX_COUNT);
    assert(Apply(settings));
    assert(routing.Routes().size() == std::size(kEntranceEndpoints));
    auto verifyNativeRows = [&]() {
        size_t count = 0;
        for (const auto& [source, target] : routing.Routes()) {
            const auto* a = EntranceEndpointById(source);
            const auto* b = EntranceEndpointById(target);
            if (a->door >= 0) continue;
            const auto& row = overrides[count++];
            assert(row.index == source && row.destination == a->reverse);
            assert(row.override == target && row.overrideDestination == b->reverse);
        }
        assert(count == sceneSources);
        for (; count < ENTRANCE_OVERRIDES_MAX_COUNT; ++count) {
            const auto& row = overrides[count];
            assert(row.index == 0 && row.destination == 0 && row.override == 0 && row.overrideDestination == 0);
        }
    };
    verifyNativeRows();
    for (const auto& row : kEntranceEndpoints) assert(routing.Destination(row.id) == row.id);

    // Every overworld pair changes, including the three reported mountain exits.
    auto swapPairs = [&](int a, int b) {
        const int ra = EntranceEndpointById(a)->reverse, rb = EntranceEndpointById(b)->reverse;
        settings["EntranceMap." + std::to_string(a)] = b;
        settings["EntranceMap." + std::to_string(rb)] = ra;
        settings["EntranceMap." + std::to_string(b)] = a;
        settings["EntranceMap." + std::to_string(ra)] = rb;
    };
    swapPairs(333, 582); // DMT -> Goron City, Darunia -> lower Crater
    swapPairs(327, 317); // summit -> upper Crater, Kakariko -> DMT
    std::vector<int> remaining;
    for (int id : kOverworldPrimaryEndpointIds) {
        if (id != 333 && id != 582 && id != 327 && id != 317) remaining.push_back(id);
    }
    assert(remaining.size() % 2 == 0 && std::size(kOverworldEndpointIds) == 52);
    for (size_t i = 0; i < remaining.size(); i += 2) swapPairs(remaining[i], remaining[i + 1]);
    assert(Apply(settings));
    verifyNativeRows();
    assert(routing.Destination(333) == 582 && routing.Destination(449) == 441);
    assert(routing.Destination(582) == 333 && routing.Destination(441) == 449);
    assert(routing.Destination(327) == 317 && routing.Destination(401) == 445);
    for (int id : kOverworldEndpointIds) {
        const auto* source = EntranceEndpointById(id);
        const auto* target = EntranceEndpointById(routing.Destination(id));
        assert(source && target && source->door < 0 && target->door < 0 && target->id != id);
        assert(Archipelago_EntranceDestination(target->reverse) == source->reverse);
        gPlayState->sceneNum = source->sourceScene;
        Record(id);
        SceneInit(target->scene);
        assert(Complete(target->scene) == source->check);
        const auto* returning = EntranceEndpointById(routing.Destination(target->reverse));
        Record(target->reverse);
        SceneInit(returning->scene);
        assert(returning->id == source->reverse);
        assert(Complete(returning->scene) == EntranceEndpointById(target->reverse)->check);
    }
    Reset();
    std::cout << "PASS: all 719 routes accepted, 298 indexed rows retained, and 52 overworld routes return as coupled pairs.\n";
}

void TestWaterAliases() {
    using namespace SohExtreme;
    using namespace SohExtreme::EntranceRuntime;
    std::unordered_map<std::string, int> settings{
        {"EntranceRandomizerRevision", 1}, {"EntranceMap.234", 333},
        {"EntranceMap.441", 385}, {"EntranceMap.333", 234}, {"EntranceMap.385", 441}
    };
    assert(Apply(settings));
    const std::pair<int, int> aliases[] = {
        {ENTR_ZORAS_RIVER_3, ENTR_ZORAS_RIVER_WEST_EXIT},
        {ENTR_HYRULE_FIELD_14, ENTR_HYRULE_FIELD_RIVER_EXIT}
    };
    for (const auto& [raw, canonical] : aliases) {
        CancelTransition();
        const auto* source = EntranceEndpointById(canonical);
        const auto* target = EntranceEndpointById(routing.Destination(canonical));
        gPlayState->sceneNum = source->sourceScene;
        const int destination = Entrance_OverrideNextIndex(raw);
        assert(destination == target->id && lastNativeLookup == raw);
        assert(lastDiscovered == canonical && lastTracked == canonical);
        assert(crossingSource == source && crossingTarget == target);
        SceneInit(target->scene);
        assert(Complete(target->scene) == source->check && lastArrivalSource == source);
        assert(routing.Destination(target->reverse) == source->reverse);
        assert(Archipelago_EntranceReturnFromUnsafeArrival());
        assert(gPlayState->nextEntranceIndex == source->reverse);
        SceneInit(source->sourceScene);
        assert(Complete(source->sourceScene) == 0);
    }
    // Non-AP saves retain the raw identities and the existing native destination.
    currentSaveIsAP = false;
    for (const auto& [raw, canonical] : aliases) {
        CancelTransition();
        gPlayState->sceneNum = EntranceEndpointById(canonical)->sourceScene;
        assert(Entrance_OverrideNextIndex(raw) == entranceOverrideTable[raw]);
        assert(lastNativeLookup == raw && lastDiscovered == raw && lastTracked == raw);
        assert(!crossingSource && !lastArrivalSource);
    }
    currentSaveIsAP = true;
    // Neither courtyard crawlspace exit is routed, discovered, or reported.
    for (int scene : {SCENE_CASTLE_COURTYARD_GUARDS_DAY, SCENE_CASTLE_COURTYARD_GUARDS_NIGHT}) {
        CancelTransition();
        gPlayState->sceneNum = scene;
        lastNativeLookup = lastDiscovered = lastTracked = -1;
        assert(Entrance_OverrideNextIndex(ENTR_CASTLE_GROUNDS_RAINBOW_BRIDGE_EXIT) ==
               ENTR_CASTLE_GROUNDS_RAINBOW_BRIDGE_EXIT);
        assert(lastNativeLookup == -1 && lastDiscovered == -1 && lastTracked == -1 && !crossingSource);
    }
    // Disabling AP routes also preserves the original water arrival variants.
    assert(Apply({{"EntranceRandomizerRevision", 0}}));
    gPlayState->sceneNum = 81;
    for (const auto& [raw, canonical] : aliases) {
        (void)canonical;
        assert(Entrance_OverrideNextIndex(raw) == raw);
        assert(lastDiscovered == raw && lastTracked == raw);
    }
    Reset();
    std::cout << "PASS: water aliases retain native destinations, canonical AP checks and paired recovery; non-AP and courtyard behavior preserved.\n";
}

int main() {
    using namespace SohExtreme;
    using namespace SohExtreme::EntranceRuntime;
    std::unordered_map<std::string, int> settings{{"EntranceRandomizerRevision", 1}};
    auto pair = [&](int a, int b) {
        const int ra = EntranceEndpointById(a)->reverse, rb = EntranceEndpointById(b)->reverse;
        settings["EntranceMap." + std::to_string(a)] = b;
        settings["EntranceMap." + std::to_string(rb)] = ra;
        settings["EntranceMap." + std::to_string(b)] = a;
        settings["EntranceMap." + std::to_string(ra)] = rb;
    };
    pair(626, 8960); // Link's House <-> Spirit room door
    pair(130, 9094); // Spirit entrance <-> Shadow room door
    pair(55, 8848);  // Shadow entrance <-> Water room door
    pair(0, 0);     // Ordinary Deku entrance, for recovery reporting
    settings["EntranceMap.187"] = 8961;
    auto* context = Rando::Context::GetInstance();
    context->GetOption(RSK_SHUFFLE_ENTRANCES).Set(0);
    context->GetOption(RSK_DECOUPLED_ENTRANCES).Set(1);
    assert(Apply(settings));
    assert(entranceInitializations == 1);
    assert(context->GetOption(RSK_SHUFFLE_ENTRANCES).value == 1);
    assert(context->GetOption(RSK_DECOUPLED_ENTRANCES).value == 0);
    assert(Archipelago_EntranceShuffleActive());

    for (const auto& [src, dst] : routing.Routes()) {
        const auto* a = EntranceEndpointById(src);
        const auto* b = EntranceEndpointById(dst);
        if (a->reverse >= 0) assert(routing.Destination(b->reverse) == a->reverse);
    }
    for (int source : {529, 481, 517}) {
        const auto* target = EntranceEndpointById(routing.Destination(source));
        assert(target && target->door >= 0 && target->room != 0);
        Record(source);
        assert(Grotto_OverrideSpecialEntrance(target->id) == target->anchor);
        SceneInit(target->scene);
        assert(gPlayState->roomCtx.curRoom.num == target->room);
        assert(arrival == nullptr);
        assert(Complete(target->scene) == EntranceEndpointById(source)->check);
        assert(routing.Destination(target->reverse) == EntranceEndpointById(source)->reverse);
    }
    std::cout << "PASS: Spirit, Shadow and Water use their mapped rooms with paired returns.\n";

    // Exercise both sides of every cataloged room door, including room zero.
    unsigned doorSides = 0;
    for (const auto& row : kEntranceEndpoints) {
        if (row.door < 0) continue;
        Archipelago_ResolveDoorArrival(row.id, false);
        SceneInit(row.scene);
        assert(gPlayState->roomCtx.curRoom.num == row.room);
        const s16 yaw = static_cast<s16>(row.yaw + (row.side ? 0x8000 : 0));
        const auto* entry = gPlayState->linkActorEntry;
        assert(entry->pos.x == static_cast<s16>(row.x + Math_SinS(yaw) * 60.0f));
        assert(entry->pos.y == static_cast<s16>(row.y));
        assert(entry->pos.z == static_cast<s16>(row.z + Math_CosS(yaw) * 60.0f));
        assert(entry->rot.y == yaw && entry->params == 0x0DFF && !arrival);
        ++doorSides;
    }
    std::cout << "PASS: exact room and position delivery for " << doorSides << " catalog door sides.\n";

    // A duplicate slot refresh cannot erase an in-flight custom arrival.
    Archipelago_ResolveDoorArrival(8961, false);
    const auto* pending = arrival;
    context->GetOption(RSK_SHUFFLE_ENTRANCES).Set(0);
    assert(Apply(settings) && arrival == pending);
    assert(context->GetOption(RSK_SHUFFLE_ENTRANCES).value == 1);
    auto broken = settings;
    broken["EntranceMap.529"] = 16;
    const auto previousRoutes = routing.Routes();
    assert(!Apply(broken) && routing.Routes() == previousRoutes && arrival == pending);

    // Returning from a wet room goes directly to the source's reverse once.
    CancelTransition();
    gPlayState->sceneNum = 52;
    Record(529);
    const auto* wet = EntranceEndpointById(routing.Destination(529));
    SceneInit(wet->scene);
    Complete(wet->scene);
    assert(Archipelago_EntranceReturnFromUnsafeArrival());
    assert(gPlayState->nextEntranceIndex == 626);
    assert(suppressTransitionChecks);
    SceneInit(52);
    assert(Complete(52) == 0);
    assert(!Archipelago_EntranceReturnFromUnsafeArrival());

    // Even a rescue identical to a vanilla scene exit must report no check.
    ArchipelagoClient client;
    CancelTransition();
    gPlayState->sceneNum = 85;
    Record(0);
    SceneInit(0);
    Complete(0);
    assert(Archipelago_EntranceReturnFromUnsafeArrival());
    assert(gPlayState->nextEntranceIndex == 521);
    client.CaptureSceneTransition();
    client.CompleteSceneTransition(85);
    assert(client.reports.empty() && !suppressTransitionChecks);
    // Show the ordinary journal would recognize this physical exit otherwise.
    gPlayState->sceneNum = 0;
    gSaveContext.respawnFlag = 0;
    gPlayState->nextEntranceIndex = 521;
    client.CaptureSceneTransition();
    client.CompleteSceneTransition(85);
    assert(client.reports.size() == 1 && client.reports[0] == 11000521);

    // Both the savewarp and door arrival use a single destination lookup.
    assert(Archipelago_EntranceSavewarp());
    assert(gSaveContext.entranceIndex == EntranceEndpointById(8961)->anchor);
    assert(arrival == EntranceEndpointById(8961) && suppressTransitionChecks);
    SceneInit(6);
    client.reports.clear();
    client.CompleteSceneTransition(6);
    assert(client.reports.empty());
    Archipelago_CancelEntranceTransition();
    assert(!arrival && !crossingSource && !lastArrivalSource && suppressTransitionChecks);
    Complete(6);

    // A legacy slot cannot inherit a previous map or its derived native flag.
    assert(Apply({{"EntranceRandomizerRevision", 0}}));
    assert(!routing.Active() && !Archipelago_EntranceShuffleActive());
    assert(context->GetOption(RSK_SHUFFLE_ENTRANCES).value == 0);
    assert(Apply(settings));
    currentSaveIsAP = false;
    assert(!Archipelago_EntranceShuffleActive());
    assert(Archipelago_EntranceDestination(529) == 529);
    currentSaveIsAP = true;
    Reset();
    assert(!arrival && !routing.Active() && !suppressTransitionChecks);
    std::cout << "PASS: reload, validation, savewarp, one-use recovery and crossing reports.\n";
    TestFullCatalog();
    TestWaterAliases();
}
