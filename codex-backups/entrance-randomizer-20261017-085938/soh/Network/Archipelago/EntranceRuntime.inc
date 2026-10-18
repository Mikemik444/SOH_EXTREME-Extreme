// Included once by ArchipelagoClient.cpp, on the gameplay thread.
#include "EntranceRouting.h"
#include "soh/Enhancements/randomizer/randomizer_entrance.h"
#include "soh/Enhancements/randomizer/randomizer_grotto.h"

namespace SohExtreme::EntranceRuntime {
EntranceRouting routing;
const EntranceEndpoint* arrival = nullptr;
const EntranceEndpoint* crossingSource = nullptr;
const EntranceEndpoint* crossingTarget = nullptr;
ActorEntry spawnEntry;
CrossingJournal doorJournal;
const EntranceEndpoint* openedDoor = nullptr;

void Reset() {
    routing.Reset(); arrival = crossingSource = crossingTarget = openedDoor = nullptr;
    doorJournal.Reset();
}

bool Apply(const std::unordered_map<std::string, int>& settings) {
    std::string error;
    if (!routing.Configure(settings, error)) {
        SPDLOG_ERROR("[Archipelago] Entrance mapping rejected: {}", error);
        return false;
    }
    auto* overrides = Randomizer_GetEntranceOverrides();
    std::fill_n(overrides, ENTRANCE_OVERRIDES_MAX_COUNT, EntranceOverride{});
    size_t n = 0;
    for (const auto& [source, target] : routing.Routes()) {
        const auto* a = EntranceEndpointById(source);
        const auto* b = EntranceEndpointById(target);
        // Door sources are dispatched by physical door crossing, not indexed
        // through the game's scene entrance table. Scene -> door is supported.
        if (a->door >= 0) continue;
        if (n >= ENTRANCE_OVERRIDES_MAX_COUNT) {
            SPDLOG_ERROR("[Archipelago] Entrance mapping exceeds native capacity");
            return false;
        }
        overrides[n++] = { 0, static_cast<int16_t>(source), static_cast<int16_t>(a->reverse),
                           static_cast<int16_t>(target), static_cast<int16_t>(b->reverse) };
    }
    Entrance_Init();
    return true;
}

void Record(int source) {
    if (!routing.Active() || !Archipelago_IsCurrentSaveFile()) return;
    const auto* a = EntranceEndpointById(source);
    if (!a || !routing.Contains(source)) return;
    // Save/death warp paths can use the same entrance indices. They are never
    // traversal checks, even though their destination still follows the map.
    if (!gPlayState || gSaveContext.health <= 0 || gSaveContext.gameMode != GAMEMODE_NORMAL ||
        gPlayState->gameOverCtx.state != GAMEOVER_INACTIVE) return;
    crossingSource = a;
    crossingTarget = EntranceEndpointById(routing.Destination(source));
}

void BeginDoor(int door, int from, int to, const Actor* actor, int side) {
    openedDoor = nullptr; doorJournal.Reset();
    if (!routing.Active() || !Archipelago_IsCurrentSaveFile() || !gPlayState || !actor) return;
    const auto* crossing = FindDoorCrossing(gPlayState->sceneNum, door, from, to,
                                           actor->world.pos.x, actor->world.pos.z, side);
    if (!crossing) return;
    for (const auto& row : kEntranceEndpoints) {
        if (row.check == crossing->location && routing.Contains(row.id)) {
            openedDoor = &row; break;
        }
    }
    if (!openedDoor) return;
    const auto* player = GET_PLAYER(gPlayState);
    if (!player) { openedDoor = nullptr; return; }
    doorJournal.BeginDoor(crossing, player->actor.world.pos.x, player->actor.world.pos.z,
                          Math_SinS(actor->shape.rot.y), Math_CosS(actor->shape.rot.y));
}

void AdvanceDoor() {
    if (!openedDoor || !gPlayState) return;
    const auto* player = GET_PLAYER(gPlayState);
    if (!player) return;
    const auto check = doorJournal.AdvanceDoor(gPlayState->sceneNum, gPlayState->roomCtx.curRoom.num,
        player->actor.world.pos.x, player->actor.world.pos.z, gSaveContext.health > 0);
    if (!check) return;
    const int source = openedDoor->id;
    openedDoor = nullptr;
    Record(source);
    const int target = routing.Destination(source);
    // Only crossing a physically opened door gets here. Its lock, combat clear
    // flag, source soul and abilities have already been enforced by the actor.
    gSaveContext.respawnFlag = 0;
    gSaveContext.nextCutsceneIndex = 0xFFEF;
    gPlayState->nextEntranceIndex = Grotto_OverrideSpecialEntrance(static_cast<int16_t>(target));
    gPlayState->transitionTrigger = TRANS_TRIGGER_START;
    gPlayState->transitionType = TRANS_TYPE_FADE_BLACK_FAST;
}

int ResolveDoor(int target, bool peek) {
    if (!routing.Active()) return target;
    const auto* row = EntranceEndpointById(target);
    if (!row || row->door < 0) return target;
    if (!peek) {
        arrival = row;
        gSaveContext.respawnFlag = 0;
        gSaveContext.nextCutsceneIndex = 0xFFEF;
        // No temporary room flags from the source scene survive the warp.
        gSaveContext.respawn[RESPAWN_MODE_RETURN].tempSwchFlags = 0;
        gSaveContext.respawn[RESPAWN_MODE_RETURN].tempCollectFlags = 0;
    }
    return row->anchor;
}

int SpawnRoom(int scene, int room) {
    return arrival && arrival->scene == scene ? arrival->room : room;
}

bool SpawnPosition(int scene) {
    if (!arrival || arrival->scene != scene || !gPlayState || !gPlayState->linkActorEntry) return false;
    spawnEntry = *gPlayState->linkActorEntry;
    const s16 yaw = static_cast<s16>(arrival->yaw + (arrival->side ? 0x8000 : 0));
    spawnEntry.pos.x = static_cast<s16>(arrival->x + Math_SinS(yaw) * 60.0f);
    spawnEntry.pos.y = static_cast<s16>(arrival->y);
    spawnEntry.pos.z = static_cast<s16>(arrival->z + Math_CosS(yaw) * 60.0f);
    spawnEntry.rot.y = yaw;
    spawnEntry.params = 0x0DFF;
    gPlayState->linkActorEntry = &spawnEntry;
    arrival = nullptr;
    return true;
}

int64_t Complete(int scene) {
    const auto* source = crossingSource;
    const auto* target = crossingTarget;
    crossingSource = crossingTarget = nullptr;
    openedDoor = nullptr; doorJournal.Reset();
    return source && target && CrossingScene(target->scene) == CrossingScene(scene) ? source->check : 0;
}
} // namespace SohExtreme::EntranceRuntime

extern "C" void Archipelago_RecordEntrance(int source) { SohExtreme::EntranceRuntime::Record(source); }
extern "C" int Archipelago_ResolveDoorArrival(int target, bool peek) {
    return SohExtreme::EntranceRuntime::ResolveDoor(target, peek);
}
extern "C" int Archipelago_EntranceSpawnRoom(int scene, int room) {
    return SohExtreme::EntranceRuntime::SpawnRoom(scene, room);
}
extern "C" bool Archipelago_EntranceSpawnPosition(int scene) {
    return SohExtreme::EntranceRuntime::SpawnPosition(scene);
}
extern "C" const char* Archipelago_EntranceDestinationName(int source) {
    const auto& routing = SohExtreme::EntranceRuntime::routing;
    if (!routing.Contains(source) || !Archipelago_IsCurrentSaveFile()) return nullptr;
    const auto* target = SohExtreme::EntranceEndpointById(routing.Destination(source));
    return target ? target->name : nullptr;
}

extern "C" int Archipelago_EntranceDestination(int source) {
    return Archipelago_IsCurrentSaveFile() ? SohExtreme::EntranceRuntime::routing.Destination(source) : source;
}
