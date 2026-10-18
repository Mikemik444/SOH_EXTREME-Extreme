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
    int sceneNum = 52;
    struct { int state = 0; } gameOverCtx;
    struct { struct { int num = 0; } curRoom; } roomCtx;
    ActorEntry* linkActorEntry = nullptr;
    int nextEntranceIndex = 0, transitionTrigger = 0, transitionType = 0;
} play, *gPlayState = &play;
struct SaveContext {
    int health = 48, gameMode = 0, respawnFlag = 0, nextCutsceneIndex = 0, entranceIndex = 187;
    struct { int tempSwchFlags = 0, tempCollectFlags = 0, entranceIndex = 0, data = 0; } respawn[4];
} gSaveContext;
enum {
    GAMEMODE_NORMAL = 0, GAMEOVER_INACTIVE = 0, TRANS_TRIGGER_OFF = 0, TRANS_TRIGGER_START = 1,
    TRANS_TYPE_FADE_BLACK_FAST = 1, RESPAWN_MODE_RETURN = 2,
    ENTR_LINKS_HOUSE_CHILD_SPAWN = 187, ENTR_HYRULE_FIELD_10 = 642,
    ENTRANCE_OVERRIDES_MAX_COUNT = 296, ENTR_MAX = 0x614,
    RSK_SHUFFLE_ENTRANCES = 0, RSK_DECOUPLED_ENTRANCES = 1,
    RO_GENERIC_OFF = 0, RO_GENERIC_ON = 1
};
struct EntranceInfo { int scene = 0; } gEntranceTable[ENTR_MAX];
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
#define SPDLOG_ERROR(...) ((void)0)
struct EntranceOverride { uint16_t type; int16_t index, destination, override, overrideDestination; };
EntranceOverride overrides[ENTRANCE_OVERRIDES_MAX_COUNT]{};
EntranceOverride* Randomizer_GetEntranceOverrides() { return overrides; }
int entranceInitializations = 0;
void Entrance_Init() { ++entranceInitializations; }
bool Archipelago_IsCurrentSaveFile() { return currentSaveIsAP; }
float Math_SinS(s16 yaw) { return std::sin(yaw * 3.14159265358979323846f / 32768.0f); }
float Math_CosS(s16 yaw) { return std::cos(yaw * 3.14159265358979323846f / 32768.0f); }
extern "C" int Archipelago_ResolveDoorArrival(int, bool);
s16 Grotto_OverrideSpecialEntrance(s16 target) {
    return static_cast<s16>(Archipelago_ResolveDoorArrival(target, false));
}
#include "../../soh/Network/Archipelago/EntranceRuntime.inc"

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
}
