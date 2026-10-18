#!/usr/bin/env python3
"""Compile/run the real no-Swim recovery helpers against isolated engine state.

No game assets or engine headers are included in the uploaded patch tree. This
harness compiles the production helper bodies, supplying only the external
engine services/state. It checks routing and respawn state, not in-game collision
geometry or a full native client build. Requires a C++20 compiler.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class NoSwimRecoveryTests(unittest.TestCase):
    def test_native_recovery_state(self):
        compiler = shutil.which("c++") or shutil.which("g++") or shutil.which("clang++")
        if compiler is None:
            self.skipTest("A C++20 compiler is required")
        hooks = (ROOT / "soh/Enhancements/randomizer/hook_handlers.cpp").read_text()
        helper = hooks[hooks.index("// from z_player.c\n"):hooks.index("\nf32 triforcePieceScale;")]
        policy = (ROOT / "soh/Enhancements/GameplayDeliverySafety.h").read_text()
        policy = policy[policy.index("inline bool CanReceiveGameplayReward"):policy.index("inline bool CanTriggerGameplayTrap")]
        flags = sorted(set(re.findall(r"\b(?:PLAYER_STATE[123]_|BGCHECKFLAG_)[A-Z0-9_]+", helper + policy)))
        constants = sorted(set(re.findall(r"\b(?:ENTR_|SCENE_)[A-Z0-9_]+", helper)) | {"SCENE_WATER_TEMPLE", "SCENE_LINKS_HOUSE"})
        definitions = "\n".join(f"constexpr unsigned long long {name} = 1ULL << {i};" for i, name in enumerate(flags))
        definitions += "\n" + "\n".join(f"constexpr int {name} = {i+100};" for i, name in enumerate(constants))
        source = r"""
#include <cassert>
#include <cstdint>
#include <iostream>
#include <unordered_map>
using s16 = int16_t; using s32 = int32_t; using f32 = float;
struct Vec3f { float x = 0, y = 0, z = 0; };
struct Rotation { s16 x = 0, y = 0, z = 0; };
struct RespawnData {
    Vec3f pos; s16 yaw = 0; s16 playerParams = 0; s16 entranceIndex = 0;
    int roomIndex = 0; int data = 0; unsigned tempSwchFlags = 0, tempCollectFlags = 0;
};
struct Actor {
    struct { Vec3f pos; } world;
    struct { Rotation rot; } shape;
    unsigned long long bgCheckFlags = 0; float yDistToWater = 0; int floorBgId = 0;
};
struct Player {
    Actor actor; unsigned long long stateFlags1 = 0, stateFlags2 = 0, stateFlags3 = 0;
};
struct PlayState {
    int sceneNum = 0, transitionTrigger = 0, transitionMode = 0, transitionType = 0;
    s16 nextEntranceIndex = -1;
    struct { int state = 0; } gameOverCtx, csCtx;
    struct { int status = 0; struct { int num = 0; } curRoom; } roomCtx;
    struct { struct { unsigned tempSwch = 0, tempCollect = 0; } flags; } actorCtx;
    struct { int room = 0; } setupEntranceList[16];
};
struct SaveContext {
    int health = 48, gameMode = 0, linkAge = 0, respawnFlag = 0;
    int nextTransitionType = 0, nextCutsceneIndex = 0, cutsceneTrigger = 0;
    float entranceSpeed = 0; s16 entranceIndex = 0; RespawnData respawn[3];
};
struct Entrance { int scene = 0, spawn = 0; };
constexpr int ENTRANCE_TABLE_SIZE = 4096, BGCHECK_SCENE = 50;
constexpr int RESPAWN_MODE_DOWN = 0, RESPAWN_MODE_RETURN = 1;
constexpr int TRANS_TRIGGER_OFF = 0, TRANS_TRIGGER_START = 1, TRANS_MODE_OFF = 0;
constexpr int TRANS_TYPE_FADE_BLACK = 7, GAMEMODE_NORMAL = 0, GAMEOVER_INACTIVE = 0, CS_STATE_IDLE = 0;
constexpr int RAND_INF_CAN_SWIM = 1;
SaveContext gSaveContext; PlayState play; PlayState* gPlayState = &play; Player player;
Entrance gEntranceTable[ENTRANCE_TABLE_SIZE];
#define GET_PLAYER(p) (&::player)
#define LINK_IS_CHILD (gSaveContext.linkAge == 0)
int cancelCalls = 0, overrideCalls = 0, grottoCalls = 0, sourceReturns = 0, ageSpawns = 0;
int nativeVoids = 0, forcedGrottos = 0, warnings = 0, notices = 0;
s16 lastGrotto = -1, configuredSpawn = 250, returnedSource = 251;
bool hasSwim = false, paused = false, blockingCs = false, active = true, canReturn = false;
bool Flags_GetRandomizerInf(int) { return hasSwim; }
bool Player_InBlockingCsMode(PlayState*, Player*) { return blockingCs; }
struct GameInteractor { static bool IsGameplayPaused() { return paused; } };
void Archipelago_CancelEntranceTransition() { ++cancelCalls; }
bool Archipelago_EntranceShuffleActive() { return active; }
bool Archipelago_EntranceReturnFromUnsafeArrival() {
    ++sourceReturns;
    if (!canReturn) return false;
    canReturn = false; play.nextEntranceIndex = returnedSource;
    play.transitionTrigger = TRANS_TRIGGER_START; gSaveContext.respawnFlag = 0; return true;
}
bool Archipelago_EntranceSavewarp() {
    if (!active) return false;
    ++ageSpawns; gSaveContext.entranceIndex = configuredSpawn;
    gSaveContext.respawnFlag = 0; return true;
}
s16 Grotto_OverrideSpecialEntrance(s16 entrance) { ++grottoCalls; lastGrotto = entrance; return entrance; }
s16 Entrance_GetOverride(s16 entrance) { ++overrideCalls; return configuredSpawn; }
void Play_SetupRespawnPoint(PlayState* p, int mode, int params) {
    auto& point = gSaveContext.respawn[mode]; point.entranceIndex = gSaveContext.entranceIndex;
    point.roomIndex = p->roomCtx.curRoom.num; point.playerParams = params; point.pos = player.actor.world.pos;
    point.yaw = player.actor.shape.rot.y; point.tempSwchFlags = p->actorCtx.flags.tempSwch;
    point.tempCollectFlags = p->actorCtx.flags.tempCollect;
}
void Play_TriggerVoidOut(PlayState* p) {
    ++nativeVoids; p->nextEntranceIndex = gSaveContext.respawn[RESPAWN_MODE_DOWN].entranceIndex;
    p->transitionTrigger = TRANS_TRIGGER_START; gSaveContext.respawnFlag = 1;
}
void Grotto_ForceGrottoReturnOnSpecialEntrance() { ++forcedGrottos; }
#define SPDLOG_WARN(...) (++warnings)
namespace Notification { struct Message { const char* message; }; void Emit(Message) { ++notices; } }
""" + definitions + "\nnamespace SohExtreme {\n" + policy + "\n}\n" + helper + r"""
void Reset() {
    RandomizerResetNoSwimRecovery(); gSaveContext = {}; play = {}; player = {}; gPlayState = &play;
    for (auto& row : gEntranceTable) row = {};
    cancelCalls = overrideCalls = grottoCalls = sourceReturns = ageSpawns = 0;
    nativeVoids = forcedGrottos = warnings = notices = 0;
    hasSwim = paused = blockingCs = canReturn = false; active = true; lastGrotto = -1;
    configuredSpawn = 250; returnedSource = 251;
    player.actor.floorBgId = BGCHECK_SCENE;
    player.actor.bgCheckFlags = BGCHECKFLAG_GROUND;
    gSaveContext.entranceIndex = 80; play.sceneNum = 6; play.roomCtx.curRoom.num = 7;
    player.actor.world.pos = {11.0f, 120.0f, 35.0f}; player.actor.shape.rot.y = 1234;
    play.actorCtx.flags.tempSwch = 0xA; play.actorCtx.flags.tempCollect = 0xB;
    RandomizerBeginNoSwimScene();
}
void Wet() {
    player.stateFlags1 = PLAYER_STATE1_IN_WATER;
    player.actor.yDistToWater = 100.0f; player.actor.bgCheckFlags = 0;
    play.transitionTrigger = TRANS_TRIGGER_OFF; play.transitionMode = TRANS_MODE_OFF;
}
void Arrive(int scene, s16 entrance, int room) {
    play.sceneNum = scene; gSaveContext.entranceIndex = entrance; play.roomCtx.curRoom.num = room;
    play.transitionTrigger = TRANS_TRIGGER_OFF; play.transitionMode = TRANS_MODE_OFF;
    RandomizerBeginNoSwimScene();
}
int main() {
    // Voluntary water entry restores this actual room and keeps current flags.
    Reset(); RandomizerUpdateNoSwimRecovery(); assert(noSwimRecovery.hasDryPoint);
    play.actorCtx.flags.tempSwch = 0xCC; Wet(); RandomizerUpdateNoSwimRecovery();
    assert(play.nextEntranceIndex == 80 && gSaveContext.respawnFlag == 1);
    const auto& down = gSaveContext.respawn[RESPAWN_MODE_DOWN];
    assert(down.roomIndex == 7 && down.pos.x == 11.0f && down.yaw == 1234);
    assert(down.tempSwchFlags == 0xCC && !noSwimRecovery.hasDryPoint);
    assert(overrideCalls == 0 && sourceReturns == 0 && cancelCalls == 1);

    // An immediately submerged arrival returns to the real preceding dry room,
    // preserving that room's flags and avoiding automatic repeated damage.
    Reset(); RandomizerUpdateNoSwimRecovery(); Arrive(SCENE_WATER_TEMPLE, ENTR_WATER_TEMPLE_ENTRANCE, 12);
    play.actorCtx.flags.tempSwch = 0xEE; Wet(); RandomizerUpdateNoSwimRecovery();
    assert(play.nextEntranceIndex == 80 && gSaveContext.entranceIndex == ENTR_WATER_TEMPLE_ENTRANCE);
    assert(gSaveContext.respawnFlag == 2 && gSaveContext.respawn[RESPAWN_MODE_RETURN].roomIndex == 7);
    assert(gSaveContext.respawn[RESPAWN_MODE_RETURN].tempSwchFlags == 0xA);
    assert(overrideCalls == 0 && sourceReturns == 0 && lastGrotto == 80);

    // A room warp can reload the same scene; visit identity still distinguishes
    // forced entry from a voluntary step into water.
    Reset(); RandomizerUpdateNoSwimRecovery(); Arrive(6, 80, 22); Wet(); RandomizerUpdateNoSwimRecovery();
    assert(gSaveContext.respawnFlag == 2 && gSaveContext.respawn[RESPAWN_MODE_RETURN].roomIndex == 7);

    // Movable floors, water contact, cutscenes and loading rooms are not safe.
    Reset(); player.actor.floorBgId = 0; RandomizerUpdateNoSwimRecovery(); assert(!noSwimRecovery.hasDryPoint);
    Reset(); player.actor.yDistToWater = 1; RandomizerUpdateNoSwimRecovery(); assert(!noSwimRecovery.hasDryPoint);
    Reset(); blockingCs = true; RandomizerUpdateNoSwimRecovery(); assert(!noSwimRecovery.hasDryPoint);
    Reset(); play.roomCtx.status = 1; RandomizerUpdateNoSwimRecovery(); assert(!noSwimRecovery.hasDryPoint);

    // Owning Swim leaves water gameplay unchanged; incomplete fades/death/pause
    // cannot start overlapping recovery transitions.
    Reset(); Wet(); hasSwim = true; RandomizerUpdateNoSwimRecovery(); assert(cancelCalls == 0 && sourceReturns == 0);
    Reset(); Wet(); play.transitionMode = 1; RandomizerUpdateNoSwimRecovery(); assert(sourceReturns == 0);
    Reset(); Wet(); play.transitionTrigger = 1; RandomizerUpdateNoSwimRecovery(); assert(sourceReturns == 0);
    Reset(); Wet(); gSaveContext.health = 0; RandomizerUpdateNoSwimRecovery(); assert(sourceReturns == 0);
    Reset(); Wet(); paused = true; RandomizerUpdateNoSwimRecovery(); assert(sourceReturns == 0);

    // Missing history first consumes the real source return, once.
    Reset(); canReturn = true; Wet(); RandomizerUpdateNoSwimRecovery();
    assert(play.nextEntranceIndex == returnedSource && sourceReturns == 1 && ageSpawns == 0);
    Arrive(SCENE_WATER_TEMPLE, returnedSource, 2); Wet(); RandomizerUpdateNoSwimRecovery();
    assert(sourceReturns == 1 && ageSpawns == 1 && play.nextEntranceIndex == configuredSpawn);

    // A legacy wet start is tried once; another immediate wet arrival has a
    // finite dry escape, without another shuffle, traversal report, or item.
    Reset(); Wet(); RandomizerUpdateNoSwimRecovery();
    assert(ageSpawns == 1 && play.nextEntranceIndex == configuredSpawn && gSaveContext.entranceIndex == 80);
    Arrive(SCENE_WATER_TEMPLE, configuredSpawn, 0); Wet(); RandomizerUpdateNoSwimRecovery();
    assert(ageSpawns == 1 && sourceReturns == 1 && play.nextEntranceIndex == ENTR_LINKS_HOUSE_1);
    assert(overrideCalls == 0 && warnings == 1 && notices == 1);

    // Fresh normal dry gameplay rearms recovery. A save/age change cannot use
    // a stale dry snapshot from another character state.
    Arrive(SCENE_LINKS_HOUSE, ENTR_LINKS_HOUSE_1, 0); player.stateFlags1 = 0;
    player.actor.bgCheckFlags = BGCHECKFLAG_GROUND; player.actor.yDistToWater = 0;
    RandomizerUpdateNoSwimRecovery(); assert(noSwimRecovery.hasDryPoint && !noSwimRecovery.triedAgeSpawn);
    RandomizerResetNoSwimRecovery(); assert(!noSwimRecovery.hasDryPoint);
    Reset(); RandomizerUpdateNoSwimRecovery(); gSaveContext.linkAge = 1; Wet(); RandomizerUpdateNoSwimRecovery();
    assert(ageSpawns == 1 && play.nextEntranceIndex == configuredSpawn);

    // Native vanilla-spawn rescue coordinates are allowed only in their actual
    // room. An AP room anchor must never teleport to the dungeon entry room.
    Reset(); active = false; gSaveContext.entranceIndex = ENTR_WATER_TEMPLE_ENTRANCE;
    play.sceneNum = SCENE_WATER_TEMPLE; play.roomCtx.curRoom.num = 2;
    gEntranceTable[ENTR_WATER_TEMPLE_ENTRANCE] = {SCENE_WATER_TEMPLE, 0}; play.setupEntranceList[0].room = 2;
    Wet(); RandomizerUpdateNoSwimRecovery();
    assert(gSaveContext.respawn[RESPAWN_MODE_DOWN].pos.y == 780.0f && nativeVoids == 0);
    Reset(); gSaveContext.entranceIndex = ENTR_WATER_TEMPLE_ENTRANCE;
    play.sceneNum = SCENE_WATER_TEMPLE; play.roomCtx.curRoom.num = 2;
    gEntranceTable[ENTR_WATER_TEMPLE_ENTRANCE] = {SCENE_WATER_TEMPLE, 0}; play.setupEntranceList[0].room = 2;
    Wet(); RandomizerUpdateNoSwimRecovery(); assert(ageSpawns == 1 && !noSwimRecovery.triedKnownRespawn);

    // Grotto reloads keep their own RETURN content. Repeated wet grotto entry
    // falls back to a real earlier dry point instead of reloading forever.
    Reset(); RandomizerUpdateNoSwimRecovery(); Arrive(SCENE_GROTTOS, 220, 0);
    gSaveContext.respawn[RESPAWN_MODE_RETURN].data = 0x7A; Wet(); RandomizerUpdateNoSwimRecovery();
    assert(play.nextEntranceIndex == 220 && gSaveContext.respawn[RESPAWN_MODE_RETURN].data == 0x7A);
    Arrive(SCENE_GROTTOS, 220, 0); Wet(); RandomizerUpdateNoSwimRecovery();
    assert(play.nextEntranceIndex == 80 && gSaveContext.respawn[RESPAWN_MODE_RETURN].roomIndex == 7);
    std::cout << "No-Swim recovery: all 12 regression groups passed\n";
}
"""
        with tempfile.TemporaryDirectory(prefix="soh-no-swim-test-") as directory:
            source_path = Path(directory) / "recovery.cpp"
            executable = Path(directory) / "recovery"
            source_path.write_text(source)
            compiled = subprocess.run([compiler, "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
                                       str(source_path), "-o", str(executable)], text=True, capture_output=True)
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            result = subprocess.run([str(executable)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
