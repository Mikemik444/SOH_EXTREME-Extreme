// Production native table, resolver and AP runtime. See the Python runner for
// the exact extracted blocks and the isolated engine-IO declarations.
#include "captured_bridge_engine.inc"

using namespace SohExtreme;
using namespace SohExtreme::EntranceRuntime;
using SettingsMap = std::unordered_map<std::string, int>;

// Hook, inventory and allocation IO are isolated; conditional-trigger control
// flow and its exact event flag identifiers come from the production source.
enum {
    VB_PLAY_TRANSITION_CS, VB_BE_ELIGIBLE_FOR_NOCTURNE_OF_SHADOW,
    VB_GIVE_ITEM_FAIRY_OCARINA, VB_BE_ELIGIBLE_FOR_LIGHT_ARROWS,
    QUEST_MEDALLION_SPIRIT, QUEST_MEDALLION_SHADOW,
    QUEST_KOKIRI_EMERALD, QUEST_GORON_RUBY, QUEST_ZORA_SAPPHIRE,
    ITEM_OCARINA_FAIRY,
    OCARINA_SONG_MINUET, OCARINA_SONG_BOLERO, OCARINA_SONG_SERENADE,
    OCARINA_SONG_REQUIEM, OCARINA_SONG_NOCTURNE, OCARINA_SONG_PRELUDE,
};
bool storyEnabled = false;
std::set<int> eventFlags, questItems;
std::vector<int> receivedItems;
int spawnedScene = -1, spawnedPoint = -1, exitRequests = 0;
bool GameInteractor_Should(int hook, bool vanilla) {
    return hook == VB_PLAY_TRANSITION_CS ? storyEnabled : vanilla;
}
bool Flags_GetEventChkInf(int flag) { return eventFlags.contains(flag); }
void Flags_SetEventChkInf(int flag) { eventFlags.insert(flag); }
void Item_Give(PlayState*, int item) { receivedItems.push_back(item); }
#define CHECK_QUEST_ITEM(item) questItems.contains(item)
#define IS_DAY (gSaveContext.nightFlag == 0)
#define IS_CUTSCENE_LAYER (gSaveContext.sceneLayer >= SCENE_LAYER_CUTSCENE_FIRST)
#define osSyncPrintf(...) ((void)0)
#define LUSLOG_INFO(...) ((void)0)
#define SET_NEXT_GAMESTATE(...) ((void)0)
void GameInteractor_ExecuteOnExitGame(int) { ++exitRequests; }
void Magic_Reset(PlayState*) {}
void Interface_ChangeHudVisibilityMode(int) {}
void Play_SpawnScene(PlayState* state, int scene, int spawn) {
    spawnedScene = scene;
    spawnedPoint = spawn;
    state->sceneNum = scene;
}
#include "captured_conditions.inc"
#include "captured_grotto_actor.inc"
#include "captured_warp_songs.inc"

void RunSceneBoundary() {
    int baseSceneLayer = -1;
    PlayState* play = gPlayState;
#include "captured_play_boundary.inc"
    assert(baseSceneLayer >= 0 && baseSceneLayer < 20);
}
int FadeTableIndex() {
    PlayState* play = gPlayState;
#include "captured_fade_layer.inc"
    return play->nextEntranceIndex + sceneLayer;
}

SettingsMap Identity() {
    SettingsMap result{{"EntranceRandomizerRevision", 1}, {"EntranceDestinationPolicyRevision", 1}};
    for (const auto& row : kEntranceEndpoints) result["EntranceMap." + std::to_string(row.id)] = row.id;
    return result;
}
SettingsMap OneWay(int source, int target) {
    return {{"EntranceRandomizerRevision", 1}, {"EntranceDestinationPolicyRevision", 1},
            {"EntranceMap." + std::to_string(source), target}};
}
SettingsMap SwapPairs(int a, int b) {
    const int ar = EntranceEndpointById(a)->reverse, br = EntranceEndpointById(b)->reverse;
    assert(ar >= 0 && br >= 0);
    return {{"EntranceRandomizerRevision", 1}, {"EntranceDestinationPolicyRevision", 1},
            {"EntranceMap." + std::to_string(a), b}, {"EntranceMap." + std::to_string(br), ar},
            {"EntranceMap." + std::to_string(b), a}, {"EntranceMap." + std::to_string(ar), br}};
}
void Fresh(const SettingsMap& settings, bool asChild = true) {
    Reset();
    play = {};
    gPlayState = &play;
    gSaveContext = {};
    currentSaveIsAP = isRandomizer = true;
    child = asChild;
    for (auto& option : Rando::Context::GetInstance()->options) option.value = 0;
    eventFlags.clear(); questItems.clear(); receivedItems.clear();
    storyEnabled = false;
    spawnedScene = spawnedPoint = -1;
    exitRequests = 0;
    assert(Apply(settings));
}
void QueueTarget(int target) {
    CancelTransition();
    ArmArrival(-1, target);
    play.nextEntranceIndex = 0;
    gSaveContext.respawnFlag = 0;
    play.nextEntranceIndex = Grotto_OverrideSpecialEntrance(static_cast<s16>(target));
    assert(pendingArrival.target && pendingArrival.target->id == target);
    assert(pendingArrival.resolvedIndex == play.nextEntranceIndex);
    gSaveContext.entranceIndex = play.nextEntranceIndex;
}

nlohmann::json ValidateCatalog() {
    Fresh(Identity());
    assert(std::size(kEntranceDestinationPolicies) == 719);
    // AP map alone must install the five child-safe bluewarp spawn repairs.
    assert(!RAND_GET_OPTION(RSK_SHUFFLE_DUNGEON_ENTRANCES));
    assert(!RAND_GET_OPTION(RSK_SHUFFLE_BOSS_ENTRANCES));
    assert(!RAND_GET_OPTION(RSK_SHUFFLE_GROTTO_ENTRANCES));
    assert(!RAND_GET_OPTION(RSK_SHUFFLE_OVERWORLD_SPAWNS));
    assert(!RAND_GET_OPTION(RSK_SHUFFLE_WARP_SONGS));
    size_t tableFacts = 0, allowedArrivals = 0, roomArrivals = 0, ageVariants = 0;
    for (const auto& policy : kEntranceDestinationPolicies) {
        const auto* endpoint = EntranceEndpointById(policy.id);
        assert(endpoint && ArrivalTableMatches(&policy));
        for (int layer = 0; layer < 4; ++layer) {
            const auto& expected = policy.normalLayers[layer];
            const auto& actual = gEntranceTable[policy.nativeIndex + layer];
            assert(actual.scene == expected.scene && actual.spawn == expected.spawn);
            // Routing checks and emergency returns must recognize every real
            // age/time scene variant, not merely the catalog's first scene.
            assert(CrossingScene(endpoint->scene) == CrossingScene(actual.scene));
            ++tableFacts;
            if (actual.scene != endpoint->scene) ++ageVariants;
            child = layer < 2;
            if (!EntranceDestinationAllowsAge(&policy, CurrentArrivalAge())) continue;
            QueueTarget(policy.id);
            gSaveContext.dayTime = layer % 2 ? 0 : 0x8000;
            gSaveContext.nextDayTime = 0xFFFF;
            gSaveContext.cutsceneIndex = 0xFFF4;
            gSaveContext.nextCutsceneIndex = 0xFFF8;
            gSaveContext.cutsceneTrigger = 1;
            assert(FadeTableIndex() == policy.nativeIndex);
            // Reading the exact pre-scene fade entry is sanitizer checked too.
            assert(gEntranceTable[FadeTableIndex()].scene == policy.normalLayers[0].scene);
            RunSceneBoundary();
            assert(play.state.running && !exitRequests && child == (layer < 2));
            assert(gSaveContext.sceneLayer >= 0 && gSaveContext.sceneLayer < 4);
            const auto& selected = policy.normalLayers[gSaveContext.sceneLayer];
            assert(spawnedScene == selected.scene && spawnedPoint == selected.spawn);
            assert(gSaveContext.cutsceneIndex == 0 && gSaveContext.nextCutsceneIndex == 0xFFEF);
            assert(gSaveContext.cutsceneTrigger == 0 && !pendingArrival.target);
            if (endpoint->door >= 0) {
                ActorEntry initial;
                play.linkActorEntry = &initial;
                assert(SpawnRoom(spawnedScene, 99) == endpoint->room);
                assert(SpawnPosition(spawnedScene));
                ++roomArrivals;
            }
            crossingSource = endpoint;
            crossingTarget = endpoint;
            assert(Complete(spawnedScene) == endpoint->check);
            assert(lastArrivalSource == endpoint && lastArrivalTarget == endpoint);
            ++allowedArrivals;
        }
    }
    assert(tableFacts == 2876 && allowedArrivals == 2870 && roomArrivals == 1684 && ageVariants > 0);
    return {{"reviewed_endpoints", 719}, {"verified_normal_table_entries", tableFacts},
            {"age_allowed_native_arrivals", allowedArrivals}, {"door_room_arrivals", roomArrivals},
            {"scene_variant_check_identities", ageVariants}};
}

nlohmann::json ValidateStaleSetups() {
    Fresh(Identity());
    // These are actual pre-fix failure indices, asserted without reading OOB.
    assert(gEntranceTable[0x00C + 8].scene == SCENE_UNUSED_6E);
    assert(gEntranceTable[0x00C + 12].scene == SCENE_SASATEST);
    assert(0x610 + 4 == ENTRANCE_TABLE_SIZE);
    size_t cases = 0;
    for (int destination : {0x00C, 0x610}) {
        for (bool asChild : {true, false}) {
            child = asChild;
            for (int cutscene = 0xFFF0; cutscene <= 0xFFFF; ++cutscene) {
                if (cutscene == 0xFFFD) continue; // Native Play_Init already normalizes this value.
                QueueTarget(destination);
                gSaveContext.cutsceneIndex = cutscene;
                gSaveContext.nextCutsceneIndex = cutscene;
                assert(FadeTableIndex() == destination);
                RunSceneBoundary();
                assert(gSaveContext.sceneLayer < 4 && spawnedScene == EntranceEndpointById(destination)->scene);
                assert(gSaveContext.cutsceneIndex == 0 && child == asChild && !pendingArrival.target);
                ++cases;
            }
        }
    }
    return {{"stale_cutscene_arrivals", cases}, {"native_unused_scene_fixture", "0x00C + layer 8"},
            {"native_debug_scene_fixture", "0x00C + layer 12"},
            {"native_oob_fixture", "0x610 + layer 4 == table size"}};
}

nlohmann::json ValidateMapPreflight() {
    Fresh(OneWay(187, 343));
    const auto accepted = routing.Routes();
    std::vector<SettingsMap> invalid = {
        OneWay(187, 0x2EA), OneWay(187, 0x614), OneWay(187, -1),
        OneWay(187, 1000), OneWay(642, 832), OneWay(638, 1000), OneWay(1364, 1000),
    };
    auto unknownPolicy = OneWay(187, 343);
    unknownPolicy["EntranceDestinationPolicyRevision"] = 2;
    invalid.push_back(unknownPolicy);
    for (const auto& settings : invalid) {
        assert(!Apply(settings));
        assert(routing.Routes() == accepted && entranceOverrideTable[187] == 343);
    }
    auto legacy = OneWay(187, 343);
    legacy.erase("EntranceDestinationPolicyRevision");
    assert(Apply(legacy));
    assert(Apply(SwapPairs(333, 1000))); // Both-age physical source needs a runtime age check.
    return {{"atomic_rejections", invalid.size()}, {"valid_missing_policy_revision", true},
            {"both_age_source_accepted_for_runtime_age_check", true}};
}

nlohmann::json ValidateRecovery() {
    // A reverse endpoint is resolved directly. Its own shuffled mapping points
    // somewhere else and must not be followed during recovery.
    Fresh(SwapPairs(333, 1000));
    const int reverse = EntranceEndpointById(333)->reverse;
    assert(routing.Destination(reverse) != reverse);
    play.nextEntranceIndex = Entrance_OverrideNextIndex(333);
    gSaveContext.entranceIndex = play.nextEntranceIndex;
    assert(pendingArrival.target->id == 1000);
    RunSceneBoundary();
    assert(child && gSaveContext.entranceIndex == EntranceDestinationById(reverse)->nativeIndex);
    assert(suppressTransitionChecks && Complete(spawnedScene) == 0 && !lastArrivalSource);

    auto settings = OneWay(1536, 1000);
    settings["EntranceMap.187"] = 343;
    Fresh(settings);
    play.nextEntranceIndex = Entrance_OverrideNextIndex(1536);
    gSaveContext.entranceIndex = play.nextEntranceIndex;
    RunSceneBoundary();
    assert(child && gSaveContext.entranceIndex == 343); // one-way has no reverse

    settings = OneWay(1536, 832);
    settings["EntranceMap.642"] = 343;
    Fresh(settings, false);
    play.nextEntranceIndex = Entrance_OverrideNextIndex(1536);
    gSaveContext.entranceIndex = play.nextEntranceIndex;
    RunSceneBoundary();
    assert(!child && gSaveContext.entranceIndex == 343); // actual adult spawn, never age-forced

    settings = OneWay(1536, 1000);
    settings["EntranceMap.187"] = 343;
    Fresh(settings);
    const auto originalRanch = gEntranceTable[343];
    gEntranceTable[343].scene = SCENE_UNUSED_6E;
    play.nextEntranceIndex = Entrance_OverrideNextIndex(1536);
    gSaveContext.entranceIndex = play.nextEntranceIndex;
    RunSceneBoundary();
    assert(child && gSaveContext.entranceIndex == ENTR_LINKS_HOUSE_1 && spawnedScene == SCENE_LINKS_HOUSE);
    gEntranceTable[343] = originalRanch;

    Fresh(settings);
    const auto originalHouse = gEntranceTable[ENTR_LINKS_HOUSE_1];
    gEntranceTable[343].scene = SCENE_UNUSED_6E;
    gEntranceTable[ENTR_LINKS_HOUSE_1].scene = SCENE_UNUSED_6E;
    play.nextEntranceIndex = Entrance_OverrideNextIndex(1536);
    gSaveContext.entranceIndex = play.nextEntranceIndex;
    RunSceneBoundary();
    assert(!play.state.running && exitRequests == 1 && spawnedScene == -1 && !pendingArrival.target);
    gEntranceTable[343] = originalRanch;
    gEntranceTable[ENTR_LINKS_HOUSE_1] = originalHouse;

    // A physically reachable special exit is guarded even if not in the map.
    Fresh(OneWay(187, 343), false);
    assert(!routing.Contains(832));
    play.nextEntranceIndex = Entrance_OverrideNextIndex(832);
    gSaveContext.entranceIndex = play.nextEntranceIndex;
    assert(pendingArrival.target && pendingArrival.target->id == 832);
    RunSceneBoundary();
    assert(!child && gSaveContext.entranceIndex == EntranceDestinationById(1400)->nativeIndex);

    // A resolver inconsistency cannot feed a raw/out-of-table fade index.
    Fresh(OneWay(187, 343));
    Record(187);
    play.nextEntranceIndex = ResolvedArrival(343, 0x7FFF);
    assert(play.nextEntranceIndex == 343 && pendingArrival.resolutionMismatch);
    gSaveContext.entranceIndex = play.nextEntranceIndex;
    RunSceneBoundary();
    assert(spawnedScene == SCENE_LON_LON_RANCH && suppressTransitionChecks && !pendingArrival.target);
    return {{"recovery_cases", 7}, {"order", {"source reverse without reshuffle", "actual-age slot spawn", "verified dry house"}},
            {"no_valid_table_refuses_scene_load", true}, {"actual_age_preserved", true}};
}

nlohmann::json ValidateStoryBehavior() {
    Fresh(OneWay(187, ENTR_DESERT_COLOSSUS_OUTSIDE_TEMPLE));
    storyEnabled = true;
    QueueTarget(ENTR_DESERT_COLOSSUS_OUTSIDE_TEMPLE);
    gSaveContext.cutsceneIndex = gSaveContext.nextCutsceneIndex = 0xFFF4;
    RunSceneBoundary();
    assert(eventFlags.contains(EVENTCHKINF_LEARNED_REQUIEM_OF_SPIRIT));
    assert(gSaveContext.entranceIndex == ENTR_DESERT_COLOSSUS_EAST_EXIT && gSaveContext.cutsceneIndex == 0xFFF0);
    assert(gSaveContext.sceneLayer == 4 && !pendingArrival.target);

    Fresh(OneWay(187, ENTR_LOST_WOODS_BRIDGE_EAST_EXIT));
    storyEnabled = true;
    QueueTarget(ENTR_LOST_WOODS_BRIDGE_EAST_EXIT);
    gSaveContext.cutsceneIndex = 0xFFF8;
    RunSceneBoundary();
    assert(eventFlags.contains(EVENTCHKINF_SPOKE_TO_SARIA_ON_BRIDGE));
    assert(receivedItems == std::vector<int>{ITEM_OCARINA_FAIRY});
    assert(gSaveContext.entranceIndex == ENTR_LOST_WOODS_SOUTH_EXIT && gSaveContext.cutsceneIndex == 0xFFF0);

    Fresh(OneWay(642, ENTR_TEMPLE_OF_TIME_WARP_PAD), false);
    storyEnabled = true;
    questItems = {QUEST_MEDALLION_SPIRIT, QUEST_MEDALLION_SHADOW};
    QueueTarget(ENTR_TEMPLE_OF_TIME_WARP_PAD);
    gSaveContext.cutsceneIndex = 0xFFF4;
    RunSceneBoundary();
    assert(eventFlags.contains(EVENTCHKINF_RETURNED_TO_TEMPLE_OF_TIME_WITH_ALL_MEDALLIONS));
    assert(gSaveContext.entranceIndex == ENTR_TEMPLE_OF_TIME_ENTRANCE && gSaveContext.cutsceneIndex == 0xFFF8);
    assert(gSaveContext.sceneLayer == 12 && !child);

    Fresh(OneWay(642, ENTR_KAKARIKO_VILLAGE_FRONT_GATE), false);
    storyEnabled = true;
    eventFlags = {EVENTCHKINF_USED_FOREST_TEMPLE_BLUE_WARP, EVENTCHKINF_USED_FIRE_TEMPLE_BLUE_WARP,
                  EVENTCHKINF_USED_WATER_TEMPLE_BLUE_WARP};
    QueueTarget(ENTR_KAKARIKO_VILLAGE_FRONT_GATE);
    RunSceneBoundary();
    assert(eventFlags.contains(EVENTCHKINF_BONGO_BONGO_ESCAPED_FROM_WELL));
    assert(gSaveContext.cutsceneIndex == 0xFFF0 && !child);

    // An ordinary unarmed native story load is untouched even while AP ER is
    // active. The cutscene layer and the same table scene selection survive.
    Fresh(OneWay(187, 343));
    gSaveContext.entranceIndex = ENTR_TEMPLE_OF_TIME_ENTRANCE;
    gSaveContext.cutsceneIndex = 0xFFF8;
    gSaveContext.nextCutsceneIndex = 0xFFEF;
    RunSceneBoundary();
    assert(gSaveContext.cutsceneIndex == 0xFFF8 && gSaveContext.sceneLayer == 12);
    assert(!pendingArrival.target);
    return {{"production_conditional_triggers", {"Requiem", "Saria ocarina and flag", "Light Arrow cutscene", "Nocturne"}},
            {"ordinary_unarmed_story_unchanged", true}};
}

nlohmann::json ValidatePathsAndMarkers() {
    Fresh(Identity());
    // Peeks do not create or replace a pending actual transition.
    assert(!pendingArrival.target);
    Entrance_PeekNextIndexOverride(343);
    Grotto_GetEntranceValueHandlingGrottoRando(1792);
    ResolveDoor(8456, true);
    assert(!pendingArrival.target);
    QueueTarget(12);
    const auto before = pendingArrival;
    Entrance_PeekNextIndexOverride(343);
    ResolveDoor(8456, true);
    assert(pendingArrival.target == before.target && pendingArrival.resolvedIndex == before.resolvedIndex);
    assert(Apply(Identity()));
    assert(pendingArrival.target == before.target); // unchanged reconnect does not discard actual request
    CancelTransition();
    assert(!pendingArrival.target);
    QueueTarget(12);
    gSaveContext.entranceIndex = 343; // an unrelated native transition superseded this one
    gSaveContext.cutsceneIndex = 0xFFF4;
    assert(BeforeSceneInit() && !pendingArrival.target && gSaveContext.cutsceneIndex == 0xFFF4);
    QueueTarget(12);
    currentSaveIsAP = false;
    assert(TransitionLayer(12, 8) == 8 && BeforeSceneInit() && !pendingArrival.target);
    currentSaveIsAP = true;

    // Physical grotto entry and a coupled return work with only AP's map set.
    Fresh(Identity());
    Actor grotto;
    grotto.params = static_cast<u8>(grottoLoadTable[0].content);
    play.sceneNum = grottoLoadTable[0].scene;
    Grotto_OverrideActorEntrance(&grotto);
    assert(pendingArrival.target && pendingArrival.target->id == 1792);
    assert(play.nextEntranceIndex == EntranceDestinationById(1792)->nativeIndex);
    gSaveContext.entranceIndex = play.nextEntranceIndex;
    RunSceneBoundary();
    auto& back = gSaveContext.respawn[RESPAWN_MODE_RETURN];
    back.entranceIndex = ENTR_DESERT_COLOSSUS_WARP_PAD;
    back.roomIndex = 7; back.playerParams = 0x04FF; back.pos = {11, 22, 33};
    const auto savedReturn = back;
    play.nextEntranceIndex = ENTR_LOAD_OPENING;
    const int returnIndex = Grotto_OverrideSpecialEntrance(ENTR_RETURN_GROTTO);
    assert(returnIndex == EntranceDestinationById(2048)->nativeIndex);
    assert(gSaveContext.respawnFlag == 2 && back.roomIndex == savedReturn.roomIndex);
    assert(back.pos.x == 11 && back.pos.y == 22 && back.pos.z == 33 && back.playerParams == 0x04FF);
    assert(pendingArrival.target && pendingArrival.target->id == 2048);

    // The actual warp-song and bluewarp implementations both finalize markers.
    Fresh(Identity());
    for (int song : {OCARINA_SONG_MINUET, OCARINA_SONG_BOLERO, OCARINA_SONG_SERENADE,
                     OCARINA_SONG_REQUIEM, OCARINA_SONG_NOCTURNE, OCARINA_SONG_PRELUDE}) {
        CancelTransition();
        play.msgCtx.lastPlayedSong = song;
        Entrance_SetWarpSongEntrance();
        assert(pendingArrival.target && pendingArrival.resolvedIndex == play.nextEntranceIndex);
    }
    for (int entrance : {ENTR_SACRED_FOREST_MEADOW_WARP_PAD, ENTR_DEATH_MOUNTAIN_CRATER_WARP_PAD,
                         ENTR_LAKE_HYLIA_WARP_PAD, ENTR_DESERT_COLOSSUS_WARP_PAD, ENTR_GRAVEYARD_WARP_PAD}) {
        CancelTransition();
        gSaveContext.entranceIndex = entrance;
        Entrance_OverrideBlueWarp();
        assert(pendingArrival.target && pendingArrival.resolvedIndex == gSaveContext.entranceIndex);
        assert(ArrivalTableMatches(pendingArrival.target));
    }
    Reset();
    assert(!pendingArrival.target);
    return {{"peek_and_reset_guards", true}, {"same_map_reconnect_preserves_request", true},
            {"ap_only_physical_grotto_entry", true}, {"coupled_grotto_return_position_preserved", true},
            {"actual_warp_song_paths", 6}, {"actual_child_bluewarp_paths", 5}};
}

int main() {
    nlohmann::json report;
    report["catalog"] = ValidateCatalog();
    report["stale_setups"] = ValidateStaleSetups();
    report["map_preflight"] = ValidateMapPreflight();
    report["recovery"] = ValidateRecovery();
    report["story"] = ValidateStoryBehavior();
    report["paths_and_markers"] = ValidatePathsAndMarkers();
    std::cout << report.dump(2) << '\n';
}
