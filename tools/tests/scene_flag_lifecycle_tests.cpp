// Captured native flag lifecycle and gate code; engine IO is isolated below.
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <iterator>
#include <set>

using u8 = uint8_t;
using s8 = int8_t;
using s16 = int16_t;
using u16 = uint16_t;
using s32 = int32_t;
using u32 = uint32_t;
struct Vec3f { float x, y, z; };
struct Vec3s { s16 x, y, z; };
struct Actor {
    s16 params;
    int room, id;
    bool isDrawn, killed, destroyed;
    int cleanupSwitch;
    Actor* next;
    struct { Vec3f pos; Vec3s rot; } world, home;
    Vec3f prevPos;
    struct { Vec3s rot; } shape;
    s16 yawTowardsPlayer;
};
struct SceneFlags { u32 chest, swch, clear, collect, tempSwch, tempClear, tempCollect; };
struct ActorContext {
    SceneFlags flags;
    struct { Actor* head; } actorLists[3];
    void* absoluteSpace;
};
struct SavedSceneFlags { u32 chest, swch, clear, collect; };
struct RespawnData {
    s16 entranceIndex;
    s32 roomIndex, playerParams;
    Vec3f pos;
    s16 yaw;
    u32 tempSwchFlags, tempCollectFlags;
};
struct TransitionActorEntry { struct { int room; } sides[2]; };
struct PlayState {
    int sceneNum, nextEntranceIndex;
    ActorContext actorCtx;
    struct { struct { int num; } curRoom, prevRoom; } roomCtx;
    struct { int unk_E3F4; } msgCtx;
    int colChkCtx, billboardMtxF, viewProjectionMtxF;
    struct { TransitionActorEntry* list; } transiActorCtx;
};
struct SaveContext {
    SavedSceneFlags sceneFlags[128];
    RespawnData respawn[3];
    int respawnFlag, entranceIndex;
} gSaveContext;
struct Player { Actor actor; int naviTextId, unk_A86; float fallStartHeight; s16 yaw; } player;
PlayState* gPlayState = nullptr;
int gMtxFClear, flagSetHooks, flagUnsetHooks, collisionClears, finalCleanupCalls;
bool timerMayTick = true, recordSwitchEvents = false;
enum { FLAG_SCENE_SWITCH, FLAG_SCENE_CLEAR, RESPAWN_MODE_DOWN, RESPAWN_MODE_RETURN = 1,
       VB_INFLICT_VOID_DAMAGE, VB_PLAY_ONEPOINT_ACTOR_CS, VB_SWITCH_TIMER_TICK,
       SCENE_JABU_JABU = 2, NA_SE_EV_METALDOOR_CLOSE };
enum { SCENE_DEKU_TREE = 0, SCENE_DODONGOS_CAVERN = 1, SCENE_FOREST_TEMPLE = 3,
       SCENE_FIRE_TEMPLE = 4, SCENE_SPIRIT_TEMPLE = 6, SCENE_GERUDOS_FORTRESS = 93,
       ACTOR_PLAYER = 100, RSK_SHUFFLE_DUNGEON_ENTRANCES, RO_DUNGEON_ENTRANCE_SHUFFLE_OFF };
enum RandomizerInf {
    RAND_INF_GF_GTG_GATE_PERMANENTLY_OPEN, RAND_INF_DEKU_TREE_MQ_TORCH_SWITCH,
    RAND_INF_DODONGOS_CAVERN_MQ_SILVER_RUPEES, RAND_INF_JABU_JABUS_BELLY_FIRST_SWITCH,
    RAND_INF_FOREST_DRAINED_WELL, RAND_INF_FOREST_LOBBY_EYES, RAND_INF_FOREST_MQ_COURTYARD_WEB_BURNT,
    RAND_INF_FIRE_MQ_LOBBY_TORCHES, RAND_INF_SPIRIT_SUN_ON_FLOOR_ON, RAND_INF_SPIRIT_MQ_LOBBY_SILVER_RUPEES,
};
std::set<RandomizerInf> recordedSwitches;
void RecordSceneSwitch(int16_t, int16_t, int16_t);
void Flags_SetRandomizerInf(RandomizerInf value) { recordedSwitches.insert(value); }
bool Flags_GetRandomizerInf(RandomizerInf value) { return recordedSwitches.contains(value); }
using SceneID = int;
struct DungeonInfo { bool IsVanilla() const { return true; } } dungeonInfo;
namespace Rando {
struct Context {
    static Context* GetInstance() { static Context instance; return &instance; }
    DungeonInfo* GetDungeonFromScene(SceneID) { return &dungeonInfo; }
};
}
struct FixtureOption { bool IsNot(int) const { return false; } } fixtureOption;
#define RAND_GET_OPTION(key) ((void)(key), fixtureOption)
#define ARRAY_COUNT(value) static_cast<s32>(std::size(value))
#define LUSLOG_INFO(...) ((void)0)
#define HREG(index) ((void)(index), 0)
#define osSyncPrintf(...) ((void)0)
#define ZELDA_ARENA_FREE_DEBUG(value) std::free(value)
#define ABS(value) std::abs(value)
#define GET_PLAYER(state) ((void)(state), &::player)
void GameInteractor_ExecuteOnSceneFlagSet(int scene, int type, int flag) {
    ++flagSetHooks;
    if (recordSwitchEvents) RecordSceneSwitch(scene, type, flag);
}
void GameInteractor_ExecuteOnSceneFlagUnset(int, int, int) { ++flagUnsetHooks; }
template <typename... Args> bool GameInteractor_Should(int kind, bool fallback, Args...) {
    return kind == VB_SWITCH_TIMER_TICK ? timerMayTick : fallback;
}
void Matrix_MtxFCopy(int* target, const int* source) { *target = *source; }
void Math_Vec3f_Copy(Vec3f* target, const Vec3f* source) { *target = *source; }
#include "scene_flag_access.inc"
#include "scene_flag_save.inc"
#include "scene_flag_restore.inc"
#include "scene_flag_recorded.inc"

Actor* Actor_Delete(ActorContext* context, Actor* actor, PlayState* play) {
    Actor* next = actor->next;
    if (actor->cleanupSwitch >= 0) Flags_SetSwitch(play, actor->cleanupSwitch);
    for (auto& list : context->actorLists) {
        Actor** node = &list.head;
        while (*node && *node != actor) node = &(*node)->next;
        if (*node) *node = next;
    }
    actor->destroyed = true;
    return next;
}
void Actor_Kill(Actor* actor) { actor->killed = true; }
void Actor_Destroy(Actor* actor, PlayState*) { actor->destroyed = true; }
void CollisionCheck_ClearContext(PlayState*, int*) { ++collisionClears; }
void func_80030488(PlayState*) { ++finalCleanupCalls; }
#include "scene_flag_cleanup.inc"
#include "scene_flag_respawn.inc"

#include "scene_flag_types.inc"
struct DoorShutter;
using DoorShutterActionFunc = void (*)(DoorShutter*, PlayState*);
struct DoorShutter {
    struct { Actor actor; } dyna{};
    int doorType = SHUTTER, styleType = 0, gfxType = 0, actionTimer = 0, unk_164 = 0;
    float barsClosedAmount = 0;
    DoorShutterActionFunc actionFunc = nullptr;
};
struct ShutterObjectInfo { int index1, index2; } sObjectInfo[] = {{1, 2}};
void OnePointCutscene_Attention(PlayState*, Actor*) {}
int DoorShutter_GetPlayerSide(DoorShutter*, PlayState*) { return 0; }
bool DoorShutter_UpdateBarsClosed(DoorShutter*, PlayState*, float) { return true; }
void DoorShutter_SetupType(DoorShutter*, PlayState*) {}
void DoorShutter_Unbar(DoorShutter*, PlayState*) {}
void DoorShutter_Idle(DoorShutter*, PlayState*) {}
void DoorShutter_Unopenable(DoorShutter*, PlayState*) {}
void DoorShutter_WaitClear(DoorShutter*, PlayState*);
void DoorShutter_BarAndWaitSwitchFlag(DoorShutter*, PlayState*);
void DoorShutter_UnbarredCheckSwitchFlag(DoorShutter*, PlayState*);
#include "scene_flag_shutter.inc"

struct BgMizuShutter;
using BgMizuShutterActionFunc = void (*)(BgMizuShutter*, PlayState*);
struct BgMizuShutter {
    struct { Actor actor; } dyna{};
    int timer = 0, timerMax = 0;
    Vec3f closedPos{}, openPos{};
    BgMizuShutterActionFunc actionFunc = nullptr;
};
void BgMizuShutter_WaitForTimer(BgMizuShutter*, PlayState*);
void BgMizuShutter_WaitForSwitch(BgMizuShutter*, PlayState*) {}
void BgMizuShutter_Move(BgMizuShutter*, PlayState*) {}
void Audio_PlayActorSound2(Actor*, int) {}
void Actor_PlaySfx_FlaggedTimer(Actor*, int) {}
#include "scene_flag_timer.inc"

struct Placement { int id, scene, door, side, fromRoom, toRoom, params; };
constexpr Placement placements[] = {
#include "scene_flag_placements.inc"
};
static_assert(std::size(placements) == 48);

int main() {
    size_t switchCases = 0, sceneRoundTrips = 0, roomMaskCases = 0;
    size_t shutterCases = 0, timerCases = 0, respawnCases = 0, unsetObserverMisses = 0;
    size_t replayCases = 0, unrecordedGateCases = 0;
    // Test every bit, including both storage boundaries and the highest bit.
    for (int flag = 0; flag < 64; ++flag) {
        PlayState play{};
        play.sceneNum = 4;
        flagSetHooks = flagUnsetHooks = 0;
        Flags_SetSwitch(&play, flag);
        assert(Flags_GetSwitch(&play, flag));
        const u32 mask = u32{1} << (flag % 32);
        assert(play.actorCtx.flags.swch == (flag < 32 ? mask : 0));
        assert(play.actorCtx.flags.tempSwch == (flag >= 32 ? mask : 0));
        Flags_SetSwitch(&play, flag);
        assert(flagSetHooks == 1);
        Flags_UnsetSwitch(&play, flag);
        Flags_UnsetSwitch(&play, flag);
        assert(!Flags_GetSwitch(&play, flag));
        if (flagUnsetHooks != 1) ++unsetObserverMisses;
        ++switchCases;

        gSaveContext = {};
        const u32 destinationBit = u32{1} << ((flag + 1) % 32);
        gSaveContext.sceneFlags[5] = {2, destinationBit, u32{1} << 12, 8};
        Flags_SetSwitch(&play, flag);
        Flags_SetClear(&play, 9);
        Flags_SetTempClear(&play, 11);
        play.actorCtx.flags.chest = 1;
        play.actorCtx.flags.collect = 4;
        play.actorCtx.flags.tempCollect = 16;
        // Next entrance metadata already points elsewhere, as during an AP
        // transition; saving must still select the source play->sceneNum.
        gSaveContext.entranceIndex = 0x10;
        play.nextEntranceIndex = 0x10;
        func_80031C3C(&play.actorCtx, &play);
        assert(gSaveContext.sceneFlags[4].swch == (flag < 32 ? mask : 0));
        assert(gSaveContext.sceneFlags[4].clear == (u32{1} << 9));
        assert(gSaveContext.sceneFlags[5].swch == destinationBit);
        PlayState destination{};
        destination.sceneNum = 5;
        RestoreSceneFlags(&destination, &destination.actorCtx);
        assert(destination.actorCtx.flags.swch == destinationBit);
        assert(destination.actorCtx.flags.clear == (u32{1} << 12));
        assert(destination.actorCtx.flags.chest == 2 && destination.actorCtx.flags.collect == 8);
        assert(destination.actorCtx.flags.tempSwch == 0 && destination.actorCtx.flags.tempClear == 0);
        assert(destination.actorCtx.flags.tempCollect == 0);
        PlayState returned{};
        returned.sceneNum = 4;
        RestoreSceneFlags(&returned, &returned.actorCtx);
        assert(static_cast<bool>(Flags_GetSwitch(&returned, flag)) == (flag < 32));
        assert(returned.actorCtx.flags.clear == (u32{1} << 9));
        assert(returned.actorCtx.flags.chest == 1 && returned.actorCtx.flags.collect == 4);
        assert(returned.actorCtx.flags.tempClear == 0 && returned.actorCtx.flags.tempCollect == 0);
        ++sceneRoundTrips;

        PlayState rooms{};
        rooms.sceneNum = 4;
        Flags_SetSwitch(&rooms, flag);
        Flags_SetTempClear(&rooms, 6);
        Flags_SetClear(&rooms, 7);
        func_80031B14(&rooms, &rooms.actorCtx);
        assert(static_cast<bool>(Flags_GetSwitch(&rooms, flag)) == (flag < 56));
        assert(rooms.actorCtx.flags.tempClear == 0 && Flags_GetClear(&rooms, 7));
        ++roomMaskCases;
    }

    // Actual full cleanup saves changes made by actor destruction, and only
    // after every actor has been removed from its source scene.
    gSaveContext = {};
    PlayState cleanup{};
    cleanup.sceneNum = 2;
    Actor dying{};
    dying.cleanupSwitch = 10;
    cleanup.actorCtx.actorLists[0].head = &dying;
    func_80031C3C(&cleanup.actorCtx, &cleanup);
    assert(dying.destroyed && !cleanup.actorCtx.actorLists[0].head);
    assert(gSaveContext.sceneFlags[2].swch == (u32{1} << 10));
    assert(gSaveContext.sceneFlags[5].swch == 0);

    // Normal room cleanup preserves current/previous/global actors and removes
    // unrelated actors before resetting room-local flags.
    PlayState rooms{};
    rooms.roomCtx.curRoom.num = 4;
    rooms.roomCtx.prevRoom.num = 3;
    std::array<Actor, 5> actors{};
    const int actorRooms[] = {4, 3, -1, 2, 8};
    for (size_t i = 0; i < actors.size(); ++i) {
        actors[i].room = actorRooms[i];
        actors[i].cleanupSwitch = -1;
        actors[i].next = i + 1 < actors.size() ? &actors[i + 1] : nullptr;
    }
    actors[4].isDrawn = true;
    rooms.actorCtx.actorLists[0].head = &actors[0];
    func_80031B14(&rooms, &rooms.actorCtx);
    assert(!actors[0].destroyed && !actors[1].destroyed && !actors[2].destroyed);
    assert(actors[3].destroyed && actors[4].destroyed && actors[4].killed);

    // Respawn data is a separate, explicit path. It restores only the lower
    // 24 temporary switch bits; ordinary AP door loads use respawnFlag zero.
    for (int mode : {0, 1, 2, -1, -3}) {
        gSaveContext = {};
        PlayState play{};
        play.sceneNum = 6;
        play.actorCtx.flags.tempSwch = 0xFFFFFFFF;
        play.actorCtx.flags.tempCollect = 0x13579;
        Vec3f position{1, 2, 3};
        Play_SetRespawnData(&play, 0, 130, 8, 3, &position, 123);
        Play_SetRespawnData(&play, 1, 130, 9, 4, &position, 456);
        assert(gSaveContext.respawn[0].tempSwchFlags == 0xFFFFFFFF);
        RestoreSceneFlags(&play, &play.actorCtx);
        gSaveContext.respawnFlag = mode;
        player = {};
        RestorePlayerRespawn(&player, &play);
        const bool restores = mode != 0 && mode != -3;
        assert(play.actorCtx.flags.tempSwch == (restores ? 0xFFFFFFu : 0u));
        assert(play.actorCtx.flags.tempCollect == (restores ? 0x13579u : 0u));
        if (mode == -3) assert(player.actor.params == 4);
        ++respawnCases;
    }

    // Check both actual authored sides of all 24 temporary-switch shutters.
    // Same-room DC door19 is selected by yaw, matching SetupDoor's native
    // special case rather than inferring side from the room number alone.
    for (const auto& placement : placements) {
        for (bool set : {false, true}) {
            PlayState play{};
            play.sceneNum = placement.scene;
            std::array<TransitionActorEntry, 64> transitions{};
            transitions[placement.door].sides[placement.side].room = placement.fromRoom;
            transitions[placement.door].sides[1 - placement.side].room = placement.toRoom;
            play.transiActorCtx.list = transitions.data();
            DoorShutter door;
            door.dyna.actor.params = static_cast<s16>(placement.params | (placement.door << 10));
            door.dyna.actor.room = placement.fromRoom;
            door.dyna.actor.yawTowardsPlayer = placement.side ? 0 : static_cast<s16>(0x8000);
            door.doorType = (placement.params >> 6) & 15;
            const int flag = placement.params & 63;
            if (set) Flags_SetSwitch(&play, flag);
            DoorShutter_SetupDoor(&door, &play);
            if (!placement.side) {
                assert(door.actionFunc == DoorShutter_Idle);
            } else if (set) {
                assert(door.actionFunc == DoorShutter_UnbarredCheckSwitchFlag);
                Flags_UnsetSwitch(&play, flag);
                DoorShutter_UnbarredCheckSwitchFlag(&door, &play);
                assert(door.actionFunc == DoorShutter_BarAndWaitSwitchFlag);
                Flags_SetSwitch(&play, flag);
                DoorShutter_BarAndWaitSwitchFlag(&door, &play);
                assert(door.actionFunc == DoorShutter_Unbar);
            } else {
                assert(door.actionFunc == DoorShutter_BarAndWaitSwitchFlag);
                Flags_SetClear(&play, placement.fromRoom);
                Flags_SetTempClear(&play, placement.fromRoom);
                DoorShutter_BarAndWaitSwitchFlag(&door, &play);
                assert(door.actionFunc == DoorShutter_BarAndWaitSwitchFlag);
            }
            ++shutterCases;
        }
    }

    // A room-clear shutter promotes a completed fight to the saved clear bit.
    // Temporary clear by itself is intentionally never copied to another scene.
    gSaveContext = {};
    PlayState cleared{};
    cleared.sceneNum = 2;
    DoorShutter clearDoor;
    clearDoor.dyna.actor.room = 8;
    DoorShutter_SetupAction(&clearDoor, DoorShutter_WaitClear);
    Flags_SetTempClear(&cleared, 8);
    DoorShutter_WaitClear(&clearDoor, &cleared);
    assert(Flags_GetClear(&cleared, 8));
    assert(clearDoor.actionFunc == DoorShutter_Unbar);
    func_80031C3C(&cleared.actorCtx, &cleared);
    RestoreSceneFlags(&cleared, &cleared.actorCtx);
    assert(Flags_GetClear(&cleared, 8) && !Flags_GetTempClear(&cleared, 8));

    // The native randomizer has a small, explicit replay layer after context
    // restoration. Only a previously observed switch action in the matching
    // scene may produce these persistent RandoInf records.
    constexpr std::array<std::array<int, 2>, 4> recordedPairs = {{{2, 59}, {3, 37}, {3, 38}, {6, 35}}};
    recordSwitchEvents = true;
    for (const auto& [scene, flag] : recordedPairs) {
        for (bool actionPerformed : {false, true}) {
            for (int destinationScene = 0; destinationScene <= 6; ++destinationScene) {
                gSaveContext = {};
                recordedSwitches.clear();
                PlayState source{};
                source.sceneNum = scene;
                gPlayState = &source;
                if (actionPerformed) Flags_SetSwitch(&source, flag);
                func_80031C3C(&source.actorCtx, &source);
                PlayState destination{};
                destination.sceneNum = destinationScene;
                gPlayState = &destination;
                RestoreSceneFlags(&destination, &destination.actorCtx);
                assert(!Flags_GetSwitch(&destination, flag));
                player = {};
                player.actor.id = ACTOR_PLAYER;
                RestoreRecordedSwitches(&player.actor);
                assert(static_cast<bool>(Flags_GetSwitch(&destination, flag)) ==
                       (actionPerformed && scene == destinationScene));
                ++replayCases;
            }
        }
    }
    std::set<std::pair<int, int>> unrecordedPairs;
    for (const auto& placement : placements) {
        bool recorded = false;
        for (const auto& pair : recordedPairs)
            recorded |= pair[0] == placement.scene && pair[1] == (placement.params & 63);
        if (!recorded) unrecordedPairs.emplace(placement.scene, placement.params & 63);
    }
    for (const auto& [scene, flag] : unrecordedPairs) {
        gSaveContext = {};
        recordedSwitches.clear();
        PlayState source{};
        source.sceneNum = scene;
        gPlayState = &source;
        Flags_SetSwitch(&source, flag);
        func_80031C3C(&source.actorCtx, &source);
        RestoreSceneFlags(&source, &source.actorCtx);
        player = {};
        player.actor.id = ACTOR_PLAYER;
        RestoreRecordedSwitches(&player.actor);
        assert(!Flags_GetSwitch(&source, flag));
        ++unrecordedGateCases;
    }
    recordSwitchEvents = false;
    gPlayState = nullptr;

    // A timed shutter owns a timer as well as a flag. Its actual init state
    // resets the flag even when its index is in the scene-saved 0..31 range.
    for (int flag : {7, 34, 62}) {
        for (bool timed : {false, true}) {
            for (bool initiallySet : {false, true}) {
                PlayState play{};
                BgMizuShutter shutter;
                shutter.dyna.actor.params = static_cast<s16>(flag);
                shutter.closedPos = {0, 10, 0};
                shutter.openPos = {0, 20, 0};
                shutter.timerMax = timed ? 20 : 0x3F * 20;
                if (initiallySet) Flags_SetSwitch(&play, flag);
                RestoreMizuShutterState(&shutter, &play);
                const bool remainsOpen = !timed && initiallySet;
                assert(static_cast<bool>(Flags_GetSwitch(&play, flag)) == remainsOpen);
                assert(shutter.actionFunc == (remainsOpen ? BgMizuShutter_WaitForTimer : BgMizuShutter_WaitForSwitch));
                if (timed) assert(shutter.dyna.actor.world.pos.y == 10);
                if (remainsOpen) assert(shutter.dyna.actor.world.pos.y == 20);
                Flags_SetSwitch(&play, flag);
                shutter.timer = 1;
                timerMayTick = false;
                BgMizuShutter_WaitForTimer(&shutter, &play);
                assert(shutter.timer == 1 && Flags_GetSwitch(&play, flag));
                timerMayTick = true;
                BgMizuShutter_WaitForTimer(&shutter, &play);
                assert(static_cast<bool>(Flags_GetSwitch(&play, flag)) == !timed);
                assert(shutter.timer == (timed ? 0 : 1));
                if (timed) assert(shutter.actionFunc == BgMizuShutter_Move);
                ++timerCases;
            }
        }
    }
    assert(switchCases == 64 && sceneRoundTrips == 64 && roomMaskCases == 64);
    assert(shutterCases == 96 && respawnCases == 5 && timerCases == 12);
    assert(replayCases == 56 && unrecordedGateCases == 18);
    std::cout << "{\"switch_storage_and_hook_cases\":" << switchCases
              << ",\"cross_scene_and_same_scene_return_cases\":" << sceneRoundTrips
              << ",\"ordinary_room_flag_mask_cases\":" << roomMaskCases
              << ",\"authored_temporary_shutter_direction_cases\":" << shutterCases
              << ",\"explicit_respawn_cases\":" << respawnCases
              << ",\"resettable_timer_cases\":" << timerCases
              << ",\"observed_missing_unset_notifications\":" << unsetObserverMisses
              << ",\"recorded_switch_scene_scoping_cases\":" << replayCases
              << ",\"unrecorded_shutter_flags_stay_reset_cases\":" << unrecordedGateCases
              << ",\"cleanup_order_and_clear_promotion_cases\":3,"
                 "\"permanent_source_flags_survive_return\":true,"
                 "\"destination_flags_are_not_inherited_from_source\":true,"
                 "\"room_cleanup_keeps_switches_32_through_55\":true,"
                 "\"actor_context_initialization_resets_all_temporary_switches\":true,"
                 "\"player_init_replays_only_recorded_scene_switches\":true,"
                 "\"timers_can_unset_saved_range_switches\":true}\n";
}
