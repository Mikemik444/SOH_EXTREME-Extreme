// Actual native medallion hook and shutter decisions; only engine IO is isolated.
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <set>

using s8 = int8_t;
using s16 = int16_t;
using u16 = uint16_t;
using s32 = int32_t;
#include "medallion_gate_types.inc"
struct Actor {
    s16 params = 0;
    int room = 0;
    struct { struct { s16 y = 0; } rot; } shape;
    s16 yawTowardsPlayer = 0;
};
struct TransitionActorEntry { struct { int room = 0; } sides[2]; };
struct PlayState {
    int sceneNum = 13;
    struct { TransitionActorEntry* list = nullptr; } transiActorCtx;
} play, *gPlayState = &play;
struct Player { Actor actor; int naviTextId = 0; } player;
struct DoorShutter;
using DoorShutterActionFunc = void (*)(DoorShutter*, PlayState*);
struct DoorShutter {
    struct { Actor actor; } dyna;
    int doorType = SHUTTER, styleType = 0, gfxType = 0, actionTimer = 0;
    float barsClosedAmount = 0;
    DoorShutterActionFunc actionFunc = nullptr;
};
struct ShutterObjectInfo { int index1, index2; } sObjectInfo[] = {{1, 2}};
enum {
    SCENE_INSIDE_GANONS_CASTLE = 13, SCENE_JABU_JABU = 2,
    QUEST_MEDALLION_FOREST, QUEST_MEDALLION_FIRE, QUEST_MEDALLION_WATER,
    QUEST_MEDALLION_SPIRIT, QUEST_MEDALLION_SHADOW, QUEST_MEDALLION_LIGHT,
    ACTOR_DOOR_SHUTTER, RSK_MEDALLION_LOCKED_TRIALS, VB_PLAY_ONEPOINT_ACTOR_CS,
};
bool randomizer = true, medallionOption = true, registered = false, childAge = true;
std::set<int> medals, clearFlags, tempClearFlags, switches;
#define IS_RANDO randomizer
#define RAND_GET_OPTION(key) ((void)(key), medallionOption)
#define COND_ID_HOOK(event, actor, condition, handler) ((void)(actor), registered = (condition))
#define CHECK_QUEST_ITEM(item) medals.contains(item)
#define GET_PLAYER(state) ((void)(state), &::player)
#define ABS(value) std::abs(value)
bool Flags_GetClear(PlayState*, int room) { return clearFlags.contains(room); }
bool Flags_GetTempClear(PlayState*, int room) { return tempClearFlags.contains(room); }
bool Flags_GetSwitch(PlayState*, int flag) { return switches.contains(flag); }
void Flags_SetClear(PlayState*, int room) { clearFlags.insert(room); }
bool GameInteractor_Should(int, bool, DoorShutter*) { return false; }
void OnePointCutscene_Attention(PlayState*, Actor*) {}
int DoorShutter_GetPlayerSide(DoorShutter*, PlayState*) { return 0; }
bool DoorShutter_UpdateBarsClosed(DoorShutter*, PlayState*, float) { return true; }
void DoorShutter_SetupType(DoorShutter*, PlayState*) {}
void DoorShutter_Unbar(DoorShutter*, PlayState*) {}
void DoorShutter_Idle(DoorShutter*, PlayState*) {}
void DoorShutter_Unopenable(DoorShutter*, PlayState*) {}
void DoorShutter_UnbarredCheckSwitchFlag(DoorShutter*, PlayState*) {}
void DoorShutter_WaitClear(DoorShutter*, PlayState*);
void DoorShutter_BarAndWaitSwitchFlag(DoorShutter*, PlayState*);
#include "medallion_gate_setup.inc"
#include "medallion_gate_clear.inc"
#include "medallion_gate_switch.inc"
#include "medallion_gate_hook.inc"

struct Placement { int endpoint, scene, params, door, fromRoom; std::array<int, 2> rooms; };
constexpr Placement placements[] = {
#include "medallion_gate_placements.inc"
};
const Placement& PlacementById(int id) {
    for (const auto& row : placements) if (row.endpoint == id) return row;
    std::abort();
}
// Expected medallion and directions are independent of the hook extraction;
// changing the hook's quest test or actor params causes these cases to fail.
struct Gate { const char* trial; int medal, params, mainEndpoint, reverseEndpoint; bool reverseUsesClear; };
constexpr Gate gates[] = {
    {"Forest", QUEST_MEDALLION_FOREST, 8255, 9872, 9873, false},
    {"Water", QUEST_MEDALLION_WATER, 9279, 9875, 9874, true},
    {"Light", QUEST_MEDALLION_LIGHT, 10303, 9876, 9877, false},
    {"Fire", QUEST_MEDALLION_FIRE, 11327, 9878, 9879, false},
    {"Shadow", QUEST_MEDALLION_SHADOW, 12351, 9881, 9880, true},
    {"Spirit", QUEST_MEDALLION_SPIRIT, 16447, 9888, 9889, false},
};

int main() {
    size_t cases = 0, clearAlternatives = 0, switchRejectedDespiteClear = 0;
    for (const auto& gate : gates) {
        for (bool reverse : {false, true}) {
            const auto& placement = PlacementById(reverse ? gate.reverseEndpoint : gate.mainEndpoint);
            assert(placement.params == gate.params && placement.scene == SCENE_INSIDE_GANONS_CASTLE);
            assert(placement.fromRoom == (reverse ? (placement.rooms[0] == 1 ? placement.rooms[1] : placement.rooms[0]) : 1));
            for (bool asChild : {true, false}) {
                childAge = asChild;
                for (bool enabled : {false, true}) {
                    for (int ownership : {0, 1, 2}) { // none, correct, wrong medallion
                        for (int clear : {0, 1, 2, 3}) { // neither, permanent, temporary, both
                            for (bool switch63 : {false, true}) {
                                std::array<TransitionActorEntry, 64> transitions{};
                                for (size_t i = 0; i < 2; ++i)
                                    transitions[placement.door].sides[i].room = placement.rooms[i];
                                play.sceneNum = placement.scene;
                                play.transiActorCtx.list = transitions.data();
                                DoorShutter door;
                                door.dyna.actor.params = static_cast<s16>(placement.params);
                                // Actor_Spawn assigns the current room; this is
                                // a direct room arrival, not a prior entry route.
                                door.dyna.actor.room = placement.fromRoom;
                                medals.clear(); clearFlags.clear(); tempClearFlags.clear(); switches.clear();
                                if (ownership == 1) medals.insert(gate.medal);
                                if (ownership == 2) medals.insert(gates[(&gate - gates + 1) % std::size(gates)].medal);
                                if (clear & 1) clearFlags.insert(placement.fromRoom);
                                if (clear & 2) tempClearFlags.insert(placement.fromRoom);
                                if (switch63) switches.insert(63);
                                randomizer = true; medallionOption = enabled;
                                RegisterMedallionLockedTrials();
                                assert(registered == enabled);
                                if (registered) OnDoorInit(&door);
                                const bool locked = enabled && ownership != 1;
                                assert(door.doorType == (locked ? SHUTTER_FRONT_SWITCH_BACK_CLEAR : SHUTTER));
                                DoorShutter_SetupDoor(&door, &play);
                                const bool clearSide = reverse ? gate.reverseUsesClear : !gate.reverseUsesClear;
                                if (!locked) {
                                    assert(door.actionFunc == DoorShutter_Idle);
                                } else if (clearSide) {
                                    if (clear & 1) {
                                        assert(door.actionFunc == DoorShutter_Idle);
                                    } else {
                                        assert(door.actionFunc == DoorShutter_WaitClear);
                                        door.actionFunc(&door, &play);
                                        assert(door.actionFunc == ((clear & 2) ? DoorShutter_Unbar : DoorShutter_WaitClear));
                                        assert(Flags_GetClear(&play, placement.fromRoom) == static_cast<bool>(clear & 2));
                                    }
                                    if (reverse && clear) ++clearAlternatives;
                                } else if (switch63) {
                                    assert(door.actionFunc == DoorShutter_UnbarredCheckSwitchFlag);
                                } else {
                                    assert(door.actionFunc == DoorShutter_BarAndWaitSwitchFlag);
                                    door.actionFunc(&door, &play);
                                    assert(door.actionFunc == DoorShutter_BarAndWaitSwitchFlag);
                                    if (clear) ++switchRejectedDespiteClear;
                                }
                                assert(childAge == asChild); // Gate has no age mutation or age exemption.
                                ++cases;
                            }
                        }
                    }
                }
            }
        }
    }
    // Registration and actor identity isolate the feature from other gameplay.
    randomizer = false; medallionOption = true; RegisterMedallionLockedTrials(); assert(!registered);
    randomizer = true; medallionOption = false; RegisterMedallionLockedTrials(); assert(!registered);
    medals.clear();
    DoorShutter unrelated;
    unrelated.dyna.actor.params = 16447;
    play.sceneNum = SCENE_JABU_JABU;
    OnDoorInit(&unrelated); assert(unrelated.doorType == SHUTTER);
    unrelated.dyna.actor.params = 0;
    play.sceneNum = SCENE_INSIDE_GANONS_CASTLE;
    OnDoorInit(&unrelated); assert(unrelated.doorType == SHUTTER);
    assert(cases == 1152 && clearAlternatives == 48 && switchRejectedDespiteClear == 72);
    std::cout << "{\"direction_inventory_flag_cases\":" << cases
              << ",\"reverse_clear_alternative_cases\":" << clearAlternatives
              << ",\"switch_side_rejections_despite_clear\":" << switchRejectedDespiteClear
              << ",\"registration_and_unrelated_actor_cases\":4,"
                 "\"switch_barred_reverse_trials\":[\"Forest\",\"Light\",\"Fire\",\"Spirit\"],"
                 "\"room_clear_reverse_trials\":[\"Water\",\"Shadow\"],"
                 "\"correct_medallion_removes_added_gate\":true,"
                 "\"wrong_medallion_does_not_unlock\":true,"
                 "\"both_age_profiles_checked\":true}\n";
}
