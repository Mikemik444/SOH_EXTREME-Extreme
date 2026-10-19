// Included once by ArchipelagoClient.cpp, on the gameplay thread.
#include "EntranceRouting.h"
#include <array>
#include <cmath>
#include "soh/Enhancements/randomizer/entrance.h"
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
const EntranceEndpoint* lastArrivalSource = nullptr;
const EntranceEndpoint* lastArrivalTarget = nullptr;
bool suppressTransitionChecks = false;
// An actual load/save-to-spawn request may precede this save's slot map.
// Applying settings or reconnecting never creates a new request.
int pendingSpawnAge = -1;
bool slotMapLoaded = false;

// Runtime checkpoints contain position only. Scene switches, timed puzzles,
// clear flags, carried actors and inventory still follow normal scene reloads.
struct SceneReturnPoint {
    bool valid = false;
    int scene = -1, room = -1, age = -1, file = -1, target = -1;
    Vec3f position{};
    s16 yaw = 0;
    int dungeonEntrance = -1;
};
SceneReturnPoint roomEntry;
SceneReturnPoint previousScene;
SceneReturnPoint departingScene;
SceneReturnPoint restartArrival;
bool dungeonReturnArrival = false;
int returnedDungeonOwner = -1;
struct PendingDungeonReturn {
    bool valid = false, previous = false;
    int entrance = -1, age = -1, file = -1;
    SceneReturnPoint point, origin;
    std::map<int, int> routes;
};
PendingDungeonReturn pendingDungeonReturn;
const EntranceDestinationPolicy* sceneArrivalPolicy = nullptr;

// A real resolved AP transition owns one arrival. Peeks and Finder labels never
// arm this marker, and a changed map/save or canceled transition discards it.
struct PendingArrival {
    const EntranceEndpoint* source = nullptr;
    const EntranceDestinationPolicy* target = nullptr;
    int resolvedIndex = -1;
    bool prepared = false;
    bool resolutionMismatch = false;
};
PendingArrival pendingArrival;

void CancelTransition() {
    pendingArrival = {};
    restartArrival = {};
    dungeonReturnArrival = false;
    returnedDungeonOwner = -1;
    suppressTransitionChecks = false;
    arrival = crossingSource = crossingTarget = openedDoor = nullptr;
    lastArrivalSource = lastArrivalTarget = nullptr;
    doorJournal.Reset();
}

void Reset(bool preserveRequestedDungeonReturn = false) {
    routing.Reset();
    slotMapLoaded = false;
    pendingSpawnAge = -1;
    roomEntry = previousScene = departingScene = {};
    sceneArrivalPolicy = nullptr;
    // Only LoadSaveMetadata may preserve an explicitly requested same-save,
    // same-seed, same-settings reload. Ordinary file loads always clear it.
    if (!preserveRequestedDungeonReturn) pendingDungeonReturn = {};
    CancelTransition();
}

uint8_t CurrentArrivalAge() {
    return LINK_IS_CHILD ? kEntranceChildAge : kEntranceAdultAge;
}

void ArmArrival(int source, int target) {
    if (!routing.Active() || !Archipelago_IsCurrentSaveFile()) return;
    const auto* policy = EntranceDestinationById(target);
    if (!policy) return; // Configure rejects any unreviewed endpoint.
    pendingArrival = { EntranceEndpointById(source), policy, -1, false };
}

// Called only by the real native resolver, after grotto/room side effects.
// Coupled grotto returns can reuse a saved entrance from elsewhere in the same
// scene. Keep their saved room/position, but use the reviewed scene-load base.
int ResolvedArrival(int target, int resolved) {
    if (!routing.Active() || !Archipelago_IsCurrentSaveFile() || !pendingArrival.target ||
        pendingArrival.target->id != target) return resolved;
    if (pendingArrival.target->kind == kEntranceGrottoReturn) {
        resolved = pendingArrival.target->nativeIndex;
        gSaveContext.respawnFlag = 2;
    }
    pendingArrival.resolutionMismatch = resolved != pendingArrival.target->nativeIndex;
    // The transition's fade reads this index before scene initialization. Keep
    // even a rejected resolution on its reviewed group until recovery runs.
    if (pendingArrival.resolutionMismatch) resolved = pendingArrival.target->nativeIndex;
    pendingArrival.resolvedIndex = resolved;
    return resolved;
}

bool ArrivalTableMatches(const EntranceDestinationPolicy* policy) {
    if (!policy || policy->nativeIndex < 0 || policy->nativeIndex + 3 >= ENTRANCE_TABLE_SIZE) return false;
    for (int layer = 0; layer < 4; ++layer) {
        const auto& expected = policy->normalLayers[layer];
        const auto& actual = gEntranceTable[policy->nativeIndex + layer];
        if (actual.scene != expected.scene || actual.spawn != expected.spawn) return false;
    }
    return true;
}

void ClearIncomingCutscene() {
    gSaveContext.cutsceneIndex = 0;
    gSaveContext.nextCutsceneIndex = 0xFFEF;
    gSaveContext.cutsceneTrigger = 0;
}

bool RecoverRejectedArrival(const char* reason) {
    const int rejected = pendingArrival.target ? pendingArrival.target->id : -1;
    const int reverse = pendingArrival.source ? pendingArrival.source->reverse : -1;
    const uint8_t age = CurrentArrivalAge();
    const int spawn = age == kEntranceChildAge ? ENTR_LINKS_HOUSE_CHILD_SPAWN : ENTR_HYRULE_FIELD_10;
    // A reverse is already resolved. Never send it through the shuffle again.
    const int candidates[] = { reverse, routing.Destination(spawn), ENTR_LINKS_HOUSE_1 };
    for (int target : candidates) {
        const auto* policy = EntranceDestinationById(target);
        if (!EntranceDestinationAllowsAge(policy, age) || !ArrivalTableMatches(policy)) continue;
        SPDLOG_ERROR("[Archipelago] Rejected entrance {} ({}, age {}); recovering to verified entrance {}",
                     rejected, reason, age, target);
        CancelTransition();
        suppressTransitionChecks = true;
        ArmArrival(-1, target);
        gSaveContext.respawnFlag = 0;
        ClearIncomingCutscene();
        gSaveContext.entranceIndex = Grotto_OverrideSpecialEntrance(static_cast<int16_t>(target));
        if (pendingArrival.resolvedIndex == policy->nativeIndex &&
            gSaveContext.entranceIndex == policy->nativeIndex) return true;
    }
    SPDLOG_ERROR("[Archipelago] No verified entrance recovery is available; refusing the scene load");
    CancelTransition();
    return false;
}

// The fade reads the table before Play_Init. Do not let inherited cutscene
// layers index beyond the verified group while this exact AP arrival is queued.
int TransitionLayer(int nextEntrance, int layer) {
    if (routing.Active() && Archipelago_IsCurrentSaveFile() && pendingArrival.target &&
        pendingArrival.resolvedIndex == nextEntrance && gSaveContext.gameMode == GAMEMODE_NORMAL) return 0;
    return layer;
}

bool BeforeSceneInit() {
    const int linkAge = LINK_IS_CHILD ? LINK_AGE_CHILD : LINK_AGE_ADULT;
    if ((roomEntry.scene >= 0 && (roomEntry.age != linkAge || roomEntry.file != gSaveContext.fileNum)) ||
        (previousScene.valid && (previousScene.age != linkAge || previousScene.file != gSaveContext.fileNum))) {
        roomEntry = previousScene = {};
    }
    if (roomEntry.scene >= 0) departingScene = roomEntry;
    else if (departingScene.age != linkAge || departingScene.file != gSaveContext.fileNum) departingScene = {};
    returnedDungeonOwner = restartArrival.valid ? restartArrival.dungeonEntrance : -1;
    roomEntry = {};
    sceneArrivalPolicy = nullptr;
    // Game over assigns a respawn flag after resolving this explicit return.
    // It must not restore the departed scene's temporary flags, including on
    // AP saves with entrance shuffle disabled and no shuffled arrival marker.
    if (dungeonReturnArrival && Archipelago_IsCurrentSaveFile()) gSaveContext.respawnFlag = 0;
    if (!pendingArrival.target) return true;
    if (!routing.Active() || !Archipelago_IsCurrentSaveFile() || gSaveContext.gameMode != GAMEMODE_NORMAL ||
        pendingArrival.resolvedIndex < 0 || gSaveContext.entranceIndex != pendingArrival.resolvedIndex) {
        CancelTransition();
        return true; // An unrandomized story transition superseded the request.
    }
    const uint8_t age = CurrentArrivalAge();
    const auto* source = pendingArrival.source ? EntranceDestinationById(pendingArrival.source->id) : nullptr;
    if (!EntranceDestinationAllowsAge(pendingArrival.target, age) ||
        (source && (source->sourceAgeMask & age) == 0)) {
        if (!RecoverRejectedArrival("destination is unavailable at the current age")) return false;
    } else if (pendingArrival.resolutionMismatch ||
               pendingArrival.resolvedIndex != pendingArrival.target->nativeIndex ||
               !ArrivalTableMatches(pendingArrival.target)) {
        if (!RecoverRejectedArrival("native scene/spawn does not match the verified destination")) return false;
    }
    ClearIncomingCutscene();
    sceneArrivalPolicy = pendingArrival.target;
    pendingArrival.prepared = true;
    return true;
}

bool AfterSceneConditions() {
    if (!pendingArrival.prepared || !pendingArrival.target) return true;
    // ConditionalTriggers may deliberately schedule a legitimate story scene,
    // including its reward/quest flags. Preserve that newly scheduled behavior.
    // Boss intros run later, after scene spawn, and are not suppressed here.
    if (gSaveContext.gameMode != GAMEMODE_NORMAL || gSaveContext.cutsceneIndex != 0 ||
        gSaveContext.nextCutsceneIndex != 0xFFEF ||
        gSaveContext.entranceIndex != pendingArrival.resolvedIndex) {
        pendingArrival = {};
        arrival = nullptr;
        restartArrival = {};
        dungeonReturnArrival = false;
        returnedDungeonOwner = -1;
        sceneArrivalPolicy = nullptr;
        return true;
    }
    // Normal engine setup selects only one of these four verified layers,
    // including Hyrule Field/Kokiri Forest's ordinary story-based variants.
    if (!EntranceDestinationAllowsAge(pendingArrival.target, CurrentArrivalAge()) ||
        !ArrivalTableMatches(pendingArrival.target)) {
        if (!RecoverRejectedArrival("arrival changed before normal scene selection")) return false;
    }
    pendingArrival = {};
    return true;
}

// File-select and cached/live settings use the same validation as installation.
// No Context, CVar or engine table is changed by this preflight.
bool Validate(const std::unordered_map<std::string, int>& settings, EntranceRouting& next, std::string& error) {
    if (!next.Configure(settings, error)) return false;
    for (const auto& [source, target] : next.Routes()) {
        for (int id : { source, target }) {
            const auto* policy = EntranceDestinationById(id);
            const auto* endpoint = EntranceEndpointById(id);
            if (!policy || !endpoint || policy->nativeIndex < 0 ||
                policy->nativeIndex + 3 >= ENTRANCE_TABLE_SIZE ||
                (endpoint->door >= 0) != (policy->kind == kEntranceRoomDoor) ||
                (endpoint->door >= 0 && endpoint->anchor != policy->nativeIndex)) {
                error = "Entrance destination has no valid reviewed native scene-load base";
                return false;
            }
        }
    }
    const auto sceneCount = std::count_if(next.Routes().begin(), next.Routes().end(), [](const auto& pair) {
        return EntranceEndpointById(pair.first)->door < 0;
    });
    if (sceneCount > ENTRANCE_OVERRIDES_MAX_COUNT) {
        error = "The seed's entrance map exceeds this client's capacity. Update the SOH-EXTREME client.";
        return false;
    }
    return true;
}

bool Apply(const std::unordered_map<std::string, int>& settings) {
    std::string error;
    EntranceRouting next;
    if (!Validate(settings, next, error)) {
        SPDLOG_ERROR("[Archipelago] Entrance mapping rejected: {}", error);
        return false;
    }
    const auto context = Rando::Context::GetInstance();
    if (!context) {
        SPDLOG_ERROR("[Archipelago] Randomizer context unavailable for entrance routing");
        return false;
    }
    const bool sameRoutes = routing.Routes() == next.Routes() &&
                            routing.UsesPreviousSceneReturn() == next.UsesPreviousSceneReturn();
    if (!sameRoutes) {
        CancelTransition();
        roomEntry = previousScene = departingScene = {};
        sceneArrivalPolicy = nullptr;
        // A menu request survives only its own table reinstall and semantics.
        if (pendingDungeonReturn.routes != next.Routes() ||
            pendingDungeonReturn.previous != next.UsesPreviousSceneReturn())
            pendingDungeonReturn = {};
    }
    routing = std::move(next);
    slotMapLoaded = true;
    // This derived option has NO CVar. SetAllToContext therefore resets it to
    // false, and AP never calls the native seed generator's FinalizeSettings.
    // Without restoring it here, scene -> room-door routes load the dungeon's
    // anchor lobby instead of the paired room, and shuffled starting spawns
    // are ignored. The validated slot map owns this flag, including on reload.
    context->GetOption(RSK_SHUFFLE_ENTRANCES).Set(routing.Active() ? RO_GENERIC_ON : RO_GENERIC_OFF);
    context->GetOption(RSK_DECOUPLED_ENTRANCES).Set(RO_GENERIC_OFF);
    auto* overrides = Randomizer_GetEntranceOverrides();
    std::array<EntranceOverride, ENTRANCE_OVERRIDES_MAX_COUNT> nextOverrides{};
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
        nextOverrides[n++] = { 0, static_cast<int16_t>(source), static_cast<int16_t>(a->reverse),
                               static_cast<int16_t>(target), static_cast<int16_t>(b->reverse) };
    }
    const bool sameOverrides = std::equal(nextOverrides.begin(), nextOverrides.end(), overrides,
        [](const EntranceOverride& a, const EntranceOverride& b) {
            return a.type == b.type && a.index == b.index && a.destination == b.destination &&
                   a.override == b.override && a.overrideDestination == b.overrideDestination;
        });
    std::copy(nextOverrides.begin(), nextOverrides.end(), overrides);
    // SetAllToContext resets options, not the installed native entrance table.
    // Reinitializing an unchanged live map also resets grottoId/return state.
    // New loads call Reset first; changed or externally reset arrays still need
    // installation, and non-gameplay initialization must rebuild the table.
    if (!sameRoutes || !sameOverrides || !Archipelago_IsCurrentSaveFile() ||
        !gPlayState || !gPlayState->state.running) {
        Entrance_Init();
    }
    return true;
}

void Record(int source) {
    if (!routing.Active() || !Archipelago_IsCurrentSaveFile()) return;
    const auto* a = EntranceEndpointById(source);
    if (!a) return;
    const int target = routing.Destination(source);
    const auto* destination = EntranceDestinationById(target);
    // Safety is independent of check credit. Also guard an unshuffled special
    // exit when mixed entrances made its shared interior reachable at either age.
    if (gSaveContext.gameMode == GAMEMODE_NORMAL &&
        (routing.Contains(source) || !EntranceDestinationAllowsAge(destination, CurrentArrivalAge())))
        ArmArrival(source, target);
    if (suppressTransitionChecks || !routing.Contains(source)) return;
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
            // The validated map keeps Ruto's essential doors at identity.
            // Use the ordinary room/check path so the held actor survives.
            if (IsLocalCarrierDoor(row.id) && routing.Destination(row.id) == row.id) return;
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
    if (!routing.Active() || !Archipelago_IsCurrentSaveFile()) return target;
    const auto* row = EntranceEndpointById(target);
    if (!row || row->door < 0) return target;
    if (!peek) {
        if (!pendingArrival.target || pendingArrival.target->id != target) ArmArrival(-1, target);
        arrival = row;
        gSaveContext.respawnFlag = 0;
        gSaveContext.nextCutsceneIndex = 0xFFEF;
        // No temporary room flags from the source scene survive the warp.
        gSaveContext.respawn[RESPAWN_MODE_RETURN].tempSwchFlags = 0;
        gSaveContext.respawn[RESPAWN_MODE_RETURN].tempCollectFlags = 0;
    }
    return peek ? row->anchor : ResolvedArrival(target, row->anchor);
}

int SpawnRoom(int scene, int room) {
    if (Archipelago_IsCurrentSaveFile() && restartArrival.valid && CrossingScene(restartArrival.scene) == CrossingScene(scene))
        return restartArrival.room;
    return Archipelago_IsCurrentSaveFile() && arrival && arrival->scene == scene ? arrival->room : room;
}

bool SpawnPosition(int scene) {
    if (!Archipelago_IsCurrentSaveFile() || !gPlayState || !gPlayState->linkActorEntry) return false;
    if (restartArrival.valid && CrossingScene(restartArrival.scene) == CrossingScene(scene)) {
        spawnEntry = *gPlayState->linkActorEntry;
        spawnEntry.pos.x = static_cast<s16>(restartArrival.position.x);
        spawnEntry.pos.y = static_cast<s16>(restartArrival.position.y);
        spawnEntry.pos.z = static_cast<s16>(restartArrival.position.z);
        spawnEntry.rot.y = restartArrival.yaw;
        spawnEntry.params = 0x0DFF;
        gPlayState->linkActorEntry = &spawnEntry;
        restartArrival = {};
        arrival = nullptr;
        return true;
    }
    if (!arrival || arrival->scene != scene) return false;
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
    dungeonReturnArrival = false;
    const bool arrived = !suppressTransitionChecks && source && target &&
                         CrossingScene(target->scene) == CrossingScene(scene);
    suppressTransitionChecks = false;
    lastArrivalSource = arrived ? source : nullptr;
    lastArrivalTarget = arrived ? target : nullptr;
    return arrived ? source->check : 0;
}

bool ReturnFromUnsafeArrival() {
    if (!routing.Active() || !Archipelago_IsCurrentSaveFile() || !gPlayState ||
        gPlayState->transitionTrigger != TRANS_TRIGGER_OFF) return false;
    const auto* source = lastArrivalSource;
    const auto* target = lastArrivalTarget;
    // Consume this history before loading: a second wet arrival cannot bounce
    // back through this recovery again. A one-way arrival has no reverse.
    lastArrivalSource = lastArrivalTarget = nullptr;
    if (!source || !target || source->reverse < 0 ||
        CrossingScene(target->scene) != CrossingScene(gPlayState->sceneNum)) return false;
    const int destination = source->reverse;
    CancelTransition();
    suppressTransitionChecks = true;
    ArmArrival(-1, destination);
    gSaveContext.respawnFlag = 0;
    gSaveContext.nextCutsceneIndex = 0xFFEF;
    // source->reverse is already the resolved return endpoint. Looking it up
    // in the shuffle map again would send Link through an unrelated entrance.
    gPlayState->nextEntranceIndex = Grotto_OverrideSpecialEntrance(static_cast<int16_t>(destination));
    gPlayState->transitionTrigger = TRANS_TRIGGER_START;
    gPlayState->transitionType = TRANS_TYPE_FADE_BLACK_FAST;
    return true;
}
bool ReturnPolicyMatches(const EntranceDestinationPolicy* policy, int scene, int nativeIndex) {
    if (!EntranceDestinationAllowsAge(policy, CurrentArrivalAge()) ||
        !ArrivalTableMatches(policy) || policy->nativeIndex != nativeIndex) return false;
    const int firstLayer = LINK_IS_CHILD ? 0 : 2;
    return CrossingScene(policy->normalLayers[firstLayer].scene) == CrossingScene(scene) ||
           CrossingScene(policy->normalLayers[firstLayer + 1].scene) == CrossingScene(scene);
}

bool ReturnPointIsCurrent(const SceneReturnPoint& point) {
    return Archipelago_IsCurrentSaveFile() && point.valid && point.file == gSaveContext.fileNum &&
           point.age == (LINK_IS_CHILD ? LINK_AGE_CHILD : LINK_AGE_ADULT);
}

// Called after Link/room initialization and after a native room change commits.
// Play_SetupRespawnPoint can instead run at a death position, so it is not used
// as evidence that Link successfully entered a room.
void RecordRoomEntry() {
    if (!routing.Active() || !Archipelago_IsCurrentSaveFile() || !gPlayState ||
        gSaveContext.gameMode != GAMEMODE_NORMAL || gSaveContext.cutsceneIndex >= 0xFFF0 ||
        gSaveContext.health <= 0 || gPlayState->roomCtx.curRoom.num < 0 ||
        gPlayState->roomCtx.curRoom.num >= gPlayState->numRooms) return;
    const auto* player = GET_PLAYER(gPlayState);
    if (!player) return;
    const auto& pos = player->actor.world.pos;
    for (float axis : {pos.x, pos.y, pos.z}) {
        if (!std::isfinite(axis) || axis < -32768.0f || axis > 32767.0f) return;
    }
    const auto matches = [&](const EntranceDestinationPolicy* policy) {
        return ReturnPolicyMatches(policy, gPlayState->sceneNum, gSaveContext.entranceIndex);
    };
    const auto* policy = sceneArrivalPolicy;
    if (!matches(policy)) {
        policy = EntranceDestinationById(gSaveContext.entranceIndex);
        if (!matches(policy)) {
            policy = nullptr;
            for (const auto& row : kEntranceEndpoints) {
                const auto* candidate = EntranceDestinationById(row.id);
                // Shared grotto bases do not identify their contents/return.
                // Only an actual resolved grotto arrival may select those.
                if (candidate && candidate->kind != kEntranceGrottoLoad &&
                    candidate->kind != kEntranceGrottoReturn && matches(candidate)) {
                    policy = candidate;
                    break;
                }
            }
        }
    }
    int dungeonEntrance = Entrance_GetDungeonSpawn(gPlayState->sceneNum);
    if (policy && Entrance_IsBossScene(gPlayState->sceneNum)) {
        if (returnedDungeonOwner >= 0) {
            dungeonEntrance = returnedDungeonOwner;
        } else if (ReturnPointIsCurrent(roomEntry) && roomEntry.scene == gPlayState->sceneNum) {
            dungeonEntrance = roomEntry.dungeonEntrance;
        } else if (ReturnPointIsCurrent(departingScene) && departingScene.dungeonEntrance >= 0) {
            // A shuffled boss belongs to the dungeon Link actually came from.
            dungeonEntrance = departingScene.dungeonEntrance;
        } else {
            const auto* boss = EntranceEndpointById(policy->id);
            const auto* back = boss && boss->reverse >= 0 ?
                EntranceEndpointById(routing.Destination(boss->reverse)) : nullptr;
            if (back && !Entrance_IsBossScene(back->scene)) {
                const int sourceDungeon = Entrance_GetDungeonSpawn(back->scene);
                if (sourceDungeon >= 0) dungeonEntrance = sourceDungeon;
            }
        }
    }
    returnedDungeonOwner = -1;
    if (departingScene.scene >= 0 && departingScene.file == gSaveContext.fileNum &&
        departingScene.age == (LINK_IS_CHILD ? LINK_AGE_CHILD : LINK_AGE_ADULT) &&
        CrossingScene(departingScene.scene) != CrossingScene(gPlayState->sceneNum)) {
        previousScene = ReturnPointIsCurrent(departingScene) ? departingScene : SceneReturnPoint{};
    }
    departingScene = {};
    sceneArrivalPolicy = policy;
    // Remember that a distinct normal scene was entered even if its scripted
    // entry is not a reviewed return destination (for example Ganondorf).
    // Entering it may return to the prior Tower, but leaving it must not keep
    // an older scene mislabeled as the immediate previous scene.
    roomEntry = {policy != nullptr, gPlayState->sceneNum, gPlayState->roomCtx.curRoom.num,
                 LINK_IS_CHILD ? LINK_AGE_CHILD : LINK_AGE_ADULT, gSaveContext.fileNum,
                 policy ? policy->id : -1, pos, player->actor.shape.rot.y, dungeonEntrance};
}

int DungeonReturnMode() {
    if (!Archipelago_IsCurrentSaveFile() || !routing.UsesPreviousSceneReturn())
        return AP_DUNGEON_RETURN_SPAWN;
    if (gPlayState && ReturnPointIsCurrent(previousScene) &&
        CrossingScene(previousScene.scene) != CrossingScene(gPlayState->sceneNum))
        return AP_DUNGEON_RETURN_PREVIOUS_SCENE;
    return AP_DUNGEON_RETURN_NO_PREVIOUS_SCENE;
}

PendingDungeonReturn BuildDungeonReturn() {
    PendingDungeonReturn request;
    if (!Archipelago_IsCurrentSaveFile() || !gPlayState) return request;
    const int mode = DungeonReturnMode();
    if (mode == AP_DUNGEON_RETURN_NO_PREVIOUS_SCENE) return request;
    request.previous = mode == AP_DUNGEON_RETURN_PREVIOUS_SCENE;
    if (request.previous) {
        request.point = previousScene;
    } else {
        request.entrance = ReturnPointIsCurrent(roomEntry) && roomEntry.scene == gPlayState->sceneNum ?
            roomEntry.dungeonEntrance : Entrance_GetDungeonSpawn(gPlayState->sceneNum);
        if (request.entrance < 0) return {};
    }
    request.valid = true;
    request.origin = roomEntry;
    request.age = LINK_IS_CHILD ? LINK_AGE_CHILD : LINK_AGE_ADULT;
    request.file = gSaveContext.fileNum;
    request.routes = routing.Routes();
    return request;
}

bool ApplyDungeonReturn(const PendingDungeonReturn& request) {
    if (!request.valid || !Archipelago_IsCurrentSaveFile() || request.file != gSaveContext.fileNum ||
        request.age != (LINK_IS_CHILD ? LINK_AGE_CHILD : LINK_AGE_ADULT) ||
        request.routes != routing.Routes()) return false;
    const EntranceDestinationPolicy* policy = nullptr;
    if (request.previous) {
        if (!routing.UsesPreviousSceneReturn() || !ReturnPointIsCurrent(request.point)) return false;
        policy = EntranceDestinationById(request.point.target);
        if (!EntranceDestinationAllowsAge(policy, CurrentArrivalAge()) || !ArrivalTableMatches(policy)) return false;
    } else if (routing.Active()) {
        // Use the native dungeon entryway, already resolved. Adult arrivals in
        // child dungeons can share a reviewed room-door anchor; the policy is
        // checked without applying that door's custom room/position.
        for (const auto& candidate : kEntranceDestinationPolicies) {
            if (candidate.nativeIndex == request.entrance &&
                EntranceDestinationAllowsAge(&candidate, CurrentArrivalAge()) && ArrivalTableMatches(&candidate)) {
                policy = &candidate;
                break;
            }
        }
        if (!policy) return false;
    }
    CancelTransition();
    pendingSpawnAge = -1;
    suppressTransitionChecks = true;
    dungeonReturnArrival = true;
    gSaveContext.respawnFlag = 0;
    ClearIncomingCutscene();
    if (request.previous) {
        ArmArrival(-1, request.point.target);
        // A saved physical endpoint is already resolved. Do not shuffle it
        // again. The native resolver restores the correct shared-grotto ID.
        gSaveContext.entranceIndex = Grotto_OverrideSpecialEntrance(static_cast<s16>(request.point.target));
        restartArrival = request.point;
        arrival = nullptr;
    } else {
        gSaveContext.entranceIndex = request.entrance;
        if (policy) {
            ArmArrival(-1, policy->id);
            ResolvedArrival(policy->id, request.entrance);
        }
    }
    gSaveContext.respawnFlag = 0;
    roomEntry = request.origin;
    return true;
}

bool RequestDungeonReturn() {
    pendingDungeonReturn = BuildDungeonReturn();
    pendingSpawnAge = -1;
    return pendingDungeonReturn.valid;
}

bool RestoreDungeonReturn() {
    if (!pendingDungeonReturn.valid) return false;
    if (!slotMapLoaded) return true; // Complete the request when its own map arrives.
    const auto request = std::move(pendingDungeonReturn);
    pendingDungeonReturn = {};
    return ApplyDungeonReturn(request);
}

bool GameOverDungeonReturn() {
    pendingDungeonReturn = {};
    return ApplyDungeonReturn(BuildDungeonReturn());
}

void CancelDungeonReturn() {
    pendingDungeonReturn = {};
    restartArrival = {};
    dungeonReturnArrival = false;
    returnedDungeonOwner = -1;
    roomEntry = previousScene = departingScene = {};
    sceneArrivalPolicy = nullptr;
}

// Resolves an actual spawn request, not a UI preview. Both load and the save
// menu use this path so an age change cannot retain the previous age's room.
bool SavewarpForAge(int age) {
    if (!Archipelago_IsCurrentSaveFile() || (age != LINK_AGE_CHILD && age != LINK_AGE_ADULT)) return false;
    pendingSpawnAge = -1;
    CancelDungeonReturn();
    // A verified legacy/disabled map is different from slot data not loaded yet.
    // It must retain ordinary native savewarp behavior without a future request.
    if (slotMapLoaded && !routing.Active()) return false;
    CancelTransition();
    if (!slotMapLoaded) {
        pendingSpawnAge = age;
        return false;
    }
    suppressTransitionChecks = true;
    const int source = age == LINK_AGE_CHILD ? ENTR_LINKS_HOUSE_CHILD_SPAWN : ENTR_HYRULE_FIELD_10;
    ArmArrival(source, routing.Destination(source));
    gSaveContext.respawnFlag = 0;
    // New child saves retain the opening cutscene until SkipIntro runs. An AP
    // spawn is already resolved; it must not depend on a second native peek.
    gSaveContext.cutsceneIndex = 0;
    gSaveContext.nextCutsceneIndex = 0xFFEF;
    gSaveContext.entranceIndex = Grotto_OverrideSpecialEntrance(routing.Destination(source));
    return true;
}

bool ServicePendingSpawn(bool safeToTransition) {
    if (pendingDungeonReturn.valid) {
        if (!Archipelago_IsCurrentSaveFile() || pendingDungeonReturn.file != gSaveContext.fileNum ||
            pendingDungeonReturn.age != (LINK_IS_CHILD ? LINK_AGE_CHILD : LINK_AGE_ADULT)) {
            pendingDungeonReturn = {};
            return false;
        }
        if (!safeToTransition || !slotMapLoaded || !gPlayState || !gPlayState->state.running ||
            gSaveContext.gameMode != GAMEMODE_NORMAL || gSaveContext.health <= 0 ||
            gPlayState->gameOverCtx.state != GAMEOVER_INACTIVE ||
            gPlayState->transitionTrigger != TRANS_TRIGGER_OFF) return false;
        const int currentEntrance = gSaveContext.entranceIndex;
        if (!RestoreDungeonReturn()) return false;
        const int destination = gSaveContext.entranceIndex;
        gSaveContext.entranceIndex = currentEntrance;
        gPlayState->nextEntranceIndex = destination;
        gPlayState->transitionTrigger = TRANS_TRIGGER_START;
        gPlayState->transitionType = TRANS_TYPE_FADE_BLACK_FAST;
        return true;
    }
    if (pendingSpawnAge < 0) return false;
    if (!Archipelago_IsCurrentSaveFile()) {
        pendingSpawnAge = -1;
        return false;
    }
    if (slotMapLoaded && !routing.Active()) {
        pendingSpawnAge = -1;
        return false;
    }
    if (!safeToTransition || !slotMapLoaded || !routing.Active() || !gPlayState ||
        !gPlayState->state.running || gSaveContext.gameMode != GAMEMODE_NORMAL || gSaveContext.health <= 0 ||
        gPlayState->gameOverCtx.state != GAMEOVER_INACTIVE ||
        gPlayState->transitionTrigger != TRANS_TRIGGER_OFF) return false;
    const int age = pendingSpawnAge;
    if (age != (LINK_IS_CHILD ? LINK_AGE_CHILD : LINK_AGE_ADULT)) {
        // A later intentional age change supersedes a still-unresolved load.
        pendingSpawnAge = -1;
        return false;
    }
    const int currentEntrance = gSaveContext.entranceIndex;
    // Consume the request before starting the transition. The already-running
    // scene keeps its entrance index until the engine commits the next scene.
    if (!SavewarpForAge(age)) return false;
    const int destination = gSaveContext.entranceIndex;
    gSaveContext.entranceIndex = currentEntrance;
    gPlayState->nextEntranceIndex = destination;
    gPlayState->transitionTrigger = TRANS_TRIGGER_START;
    gPlayState->transitionType = TRANS_TYPE_FADE_BLACK_FAST;
    return true;
}
} // namespace SohExtreme::EntranceRuntime

extern "C" bool Archipelago_EntranceShuffleActive(void) {
    return Archipelago_IsCurrentSaveFile() && SohExtreme::EntranceRuntime::routing.Active();
}
extern "C" void Archipelago_CancelEntranceTransition(void) {
    SohExtreme::EntranceRuntime::CancelTransition();
    SohExtreme::EntranceRuntime::suppressTransitionChecks = true;
}
extern "C" bool Archipelago_EntranceReturnFromUnsafeArrival(void) {
    return SohExtreme::EntranceRuntime::ReturnFromUnsafeArrival();
}
extern "C" void Archipelago_RecordEntrance(int source) { SohExtreme::EntranceRuntime::Record(source); }
extern "C" int Archipelago_ResolvedEntranceArrival(int target, int resolved) {
    return SohExtreme::EntranceRuntime::ResolvedArrival(target, resolved);
}
extern "C" int Archipelago_EntranceTransitionLayer(int nextEntrance, int layer) {
    return SohExtreme::EntranceRuntime::TransitionLayer(nextEntrance, layer);
}
extern "C" bool Archipelago_EntranceBeforeSceneInit(void) {
    return SohExtreme::EntranceRuntime::BeforeSceneInit();
}
extern "C" bool Archipelago_EntranceAfterSceneConditions(void) {
    return SohExtreme::EntranceRuntime::AfterSceneConditions();
}
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

extern "C" void Archipelago_EntranceRecordRoomEntry(void) {
    SohExtreme::EntranceRuntime::RecordRoomEntry();
}
extern "C" int Archipelago_EntranceDungeonReturnMode(void) {
    return SohExtreme::EntranceRuntime::DungeonReturnMode();
}
extern "C" bool Archipelago_EntranceRequestDungeonReturn(void) {
    return SohExtreme::EntranceRuntime::RequestDungeonReturn();
}
extern "C" bool Archipelago_EntranceRestoreDungeonReturn(void) {
    return SohExtreme::EntranceRuntime::RestoreDungeonReturn();
}
extern "C" bool Archipelago_EntranceGameOverDungeonReturn(void) {
    return SohExtreme::EntranceRuntime::GameOverDungeonReturn();
}
extern "C" bool Archipelago_EntranceDungeonReturnInProgress(void) {
    return Archipelago_IsCurrentSaveFile() && SohExtreme::EntranceRuntime::dungeonReturnArrival;
}
extern "C" void Archipelago_EntranceCancelDungeonReturn(void) {
    SohExtreme::EntranceRuntime::CancelDungeonReturn();
}

extern "C" bool Archipelago_EntranceSavewarpForAge(int age) {
    return SohExtreme::EntranceRuntime::SavewarpForAge(age);
}
extern "C" bool Archipelago_EntranceSavewarp(void) {
    // The AP root graph guarantees the current age's saved slot destination.
    return Archipelago_EntranceSavewarpForAge(LINK_IS_CHILD ? LINK_AGE_CHILD : LINK_AGE_ADULT);
}
extern "C" void Archipelago_CancelPendingEntranceSpawn(void) {
    SohExtreme::EntranceRuntime::pendingSpawnAge = -1;
    SohExtreme::EntranceRuntime::CancelTransition();
}
