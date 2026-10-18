
#include <cstdint>
#include <iostream>
#include <map>
#include <vector>
enum { SCENE_KOKIRI_FOREST, SCENE_MIDOS_HOUSE, SCENE_LOST_WOODS,
       SCENE_HYRULE_CASTLE, SCENE_LON_LON_BUILDINGS, SCENE_KAKARIKO_CENTER_GUEST_HOUSE };
enum { EVENTCHKINF_SPOKE_TO_MIDO_AFTER_DEKU_TREES_DEATH, EVENTCHKINF_OBTAINED_ZELDAS_LETTER,
       EVENTCHKINF_TALON_RETURNED_FROM_CASTLE, EVENTCHKINF_TALON_RETURNED_FROM_KAKARIKO,
       EVENTCHKINF_TALON_WOKEN_IN_CASTLE };
static int testAge = 0, testFlags = 0;
static bool Flags_GetEventChkInf(int flag) { return (testFlags & (1 << flag)) != 0; }
#define LINK_IS_ADULT (testAge == 1)
using u8 = unsigned char;
struct Actor { bool killed = false; };
struct EnMd {};
struct EnTa { Actor actor; };
struct PlayState { int sceneNum; };
static void Actor_Kill(Actor* actor) { actor->killed = true; }
namespace SohExtreme {
struct TrackerScene { int scene = -1; bool Matches(const TrackerScene& other) const {
    return scene >= 0 && scene == other.scene;
}};
inline int TrackerSceneRoutePriority(const TrackerScene& route, const TrackerScene& current,
                                     int routeAge, int routeTime, int age, int time) {
    return ((routeAge < 0 || routeAge == age) ? 4 : 0) +
           ((routeTime < 0 || routeTime == time) ? 2 : 0) + (route.Matches(current) ? 1 : 0);
}
}
static bool FinderNpcSpeechScenePresent(int64_t id, int scene, int age) {
    if (id == 10000094) { // EnMd_ShouldSpawn
        const bool atHome = Flags_GetEventChkInf(EVENTCHKINF_SPOKE_TO_MIDO_AFTER_DEKU_TREES_DEATH) ||
                            Flags_GetEventChkInf(EVENTCHKINF_OBTAINED_ZELDAS_LETTER);
        if (scene == SCENE_KOKIRI_FOREST) return !atHome;
        if (scene == SCENE_MIDOS_HOUSE) return age == 0 && atHome;
    } else if (id == 10000118) { // EnTa_Init: castle, child ranch, adult Kakariko roles
        const bool leftCastle = Flags_GetEventChkInf(EVENTCHKINF_TALON_RETURNED_FROM_CASTLE);
        if (scene == SCENE_HYRULE_CASTLE) return !leftCastle;
        if (scene == SCENE_LON_LON_BUILDINGS) return age == 0 && leftCastle;
        if (scene == SCENE_KAKARIKO_CENTER_GUEST_HOUSE) {
            return age == 1 && !Flags_GetEventChkInf(EVENTCHKINF_TALON_RETURNED_FROM_KAKARIKO);
        }
    }
    return true;
}
u8 EnMd_ShouldSpawn(EnMd* thisActor, PlayState* play) {
    if (play->sceneNum == SCENE_KOKIRI_FOREST) {
        if (!Flags_GetEventChkInf(EVENTCHKINF_SPOKE_TO_MIDO_AFTER_DEKU_TREES_DEATH) &&
            !Flags_GetEventChkInf(EVENTCHKINF_OBTAINED_ZELDAS_LETTER)) {
            return 1;
        }
    }

    if (play->sceneNum == SCENE_MIDOS_HOUSE) {
        if (Flags_GetEventChkInf(EVENTCHKINF_SPOKE_TO_MIDO_AFTER_DEKU_TREES_DEATH) ||
            Flags_GetEventChkInf(EVENTCHKINF_OBTAINED_ZELDAS_LETTER)) {
            if (!LINK_IS_ADULT) {
                return 1;
            }
        }
    }

    if (play->sceneNum == SCENE_LOST_WOODS) {
        return 1;
    }

    return 0;
}
static bool NativeTalonScenePresent(int scene) { EnTa actor; EnTa* thisActor = &actor;
if (scene == SCENE_KAKARIKO_CENTER_GUEST_HOUSE) {
if (Flags_GetEventChkInf(EVENTCHKINF_TALON_RETURNED_FROM_KAKARIKO)) {
                Actor_Kill(&thisActor->actor);
            } else if (!LINK_IS_ADULT) {
                Actor_Kill(&thisActor->actor);
            }
}
if (scene == SCENE_HYRULE_CASTLE) {
if (Flags_GetEventChkInf(EVENTCHKINF_TALON_RETURNED_FROM_CASTLE)) {
                    Actor_Kill(&thisActor->actor);
                }
}
if (scene == SCENE_LON_LON_BUILDINGS) {
if (!Flags_GetEventChkInf(EVENTCHKINF_TALON_RETURNED_FROM_CASTLE)) {
                    Actor_Kill(&thisActor->actor);
                } else if (LINK_IS_ADULT) {
                    Actor_Kill(&thisActor->actor);
                }
}
return !actor.actor.killed; }

constexpr int RC_UNKNOWN_CHECK = 0, RCAREA_INVALID = -1;
struct ConversationScene { int64_t location; int check, scene, area, grotto, age, time; };
static SohExtreme::TrackerScene FinderNativeScene(int) { return {}; }
static SohExtreme::TrackerScene FinderScene(int scene, int, int) { return {scene}; }
static SohExtreme::TrackerScene Select(int64_t id, int currentScene) {
    static const ConversationScene rows[] = {
{ 10000094LL, RC_UNKNOWN_CHECK, SCENE_KOKIRI_FOREST, RCAREA_INVALID, -1, 0, -1 },
{ 10000094LL, RC_UNKNOWN_CHECK, SCENE_MIDOS_HOUSE, RCAREA_INVALID, -1, 0, -1 },
{ 10000094LL, RC_UNKNOWN_CHECK, SCENE_LOST_WOODS, RCAREA_INVALID, -1, 1, -1 },
{ 10000118LL, RC_UNKNOWN_CHECK, SCENE_HYRULE_CASTLE, RCAREA_INVALID, -1, 0, -1 },
{ 10000118LL, RC_UNKNOWN_CHECK, SCENE_LON_LON_BUILDINGS, RCAREA_INVALID, -1, 0, -1 },
{ 10000118LL, RC_UNKNOWN_CHECK, SCENE_KAKARIKO_CENTER_GUEST_HOUSE, RCAREA_INVALID, -1, 1, -1 },
};

    std::map<int64_t, std::vector<ConversationScene>> conversations;
    for (const auto& row : rows) conversations[row.location].push_back(row);
    const auto conversation = conversations.find(id);
    const SohExtreme::TrackerScene current {currentScene};
    const int age = testAge, time = 0;
        SohExtreme::TrackerScene best;
        int bestPriority = -1;
        for (const auto& route : conversation->second) {
            if (!FinderNpcSpeechScenePresent(id, route.scene, age)) continue;
            const auto scene = route.check != RC_UNKNOWN_CHECK ? FinderNativeScene(route.check)
                : FinderScene(route.scene, route.area, route.grotto);
            const int priority = SohExtreme::TrackerSceneRoutePriority(scene, current, route.age, route.time, age, time);
            if (priority > bestPriority) {
                best = scene;
                bestPriority = priority;
            }
        }
        return best;
}

int main() {
    int comparisons = 0;
    for (testAge = 0; testAge < 2; ++testAge) {
        for (testFlags = 0; testFlags < 4; ++testFlags) {
            for (int scene : {SCENE_KOKIRI_FOREST, SCENE_MIDOS_HOUSE, SCENE_LOST_WOODS}) {
                PlayState play {scene};
                if (FinderNpcSpeechScenePresent(10000094, scene, testAge) != bool(EnMd_ShouldSpawn(nullptr, &play))) return 1;
                ++comparisons;
            }
        }
        for (int flags = 0; flags < 8; ++flags) {
            testFlags = flags << 2;
            for (int scene : {SCENE_HYRULE_CASTLE, SCENE_LON_LON_BUILDINGS, SCENE_KAKARIKO_CENTER_GUEST_HOUSE}) {
                if (FinderNpcSpeechScenePresent(10000118, scene, testAge) != NativeTalonScenePresent(scene)) return 2;
                ++comparisons;
            }
        }
    }
    struct Case { const char* name; int64_t id; int age, flags, current, expected; };
    const Case cases[] = {
        {"Mido before story flags in forest",10000094,0,0,SCENE_KOKIRI_FOREST,SCENE_KOKIRI_FOREST},
        {"Mido before story flags in empty house",10000094,0,0,SCENE_MIDOS_HOUSE,SCENE_KOKIRI_FOREST},
        {"Mido after Deku conversation in forest",10000094,0,1,SCENE_KOKIRI_FOREST,SCENE_MIDOS_HOUSE},
        {"Mido after letter in forest",10000094,0,2,SCENE_KOKIRI_FOREST,SCENE_MIDOS_HOUSE},
        {"Mido Skip Child Zelda in forest",10000094,0,22,SCENE_KOKIRI_FOREST,SCENE_MIDOS_HOUSE},
        {"Mido adult before flags",10000094,1,0,SCENE_KOKIRI_FOREST,SCENE_LOST_WOODS},
        {"Mido adult after flags",10000094,1,3,SCENE_MIDOS_HOUSE,SCENE_LOST_WOODS},
        {"Talon sleeping in castle",10000118,0,0,SCENE_HYRULE_CASTLE,SCENE_HYRULE_CASTLE},
        {"Talon sleeping in empty ranch",10000118,0,0,SCENE_LON_LON_BUILDINGS,SCENE_HYRULE_CASTLE},
        {"Talon awake but not departed",10000118,0,16,SCENE_HYRULE_CASTLE,SCENE_HYRULE_CASTLE},
        {"Talon departed while player visits castle",10000118,0,4,SCENE_HYRULE_CASTLE,SCENE_LON_LON_BUILDINGS},
        {"Talon departed while player visits ranch",10000118,0,4,SCENE_LON_LON_BUILDINGS,SCENE_LON_LON_BUILDINGS},
        {"Talon Skip Child Zelda in castle",10000118,0,22,SCENE_HYRULE_CASTLE,SCENE_LON_LON_BUILDINGS},
        {"Talon adult before Kakariko departure",10000118,1,4,SCENE_HYRULE_CASTLE,SCENE_KAKARIKO_CENTER_GUEST_HOUSE},
        {"Talon adult departed Kakariko",10000118,1,12,SCENE_KAKARIKO_CENTER_GUEST_HOUSE,-1},
    };
    for (const auto& row : cases) {
        testAge = row.age; testFlags = row.flags;
        const int actual = Select(row.id, row.current).scene;
        std::cout << row.name << '\t' << row.expected << '\t' << actual << '\n';
        if (actual != row.expected) return 3;
    }
    std::cout << "native_predicate_comparisons\t" << comparisons << '\n';
}
