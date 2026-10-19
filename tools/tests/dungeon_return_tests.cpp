// Real entrance runtime, native entrance/game-over/savewarp functions and menu
// helpers. Engine file/room IO is isolated; this is not a ROM collision test.
#include "captured_return_engine.inc"
#include <type_traits>

using SettingsMap = std::unordered_map<std::string, int>;
namespace ER = SohExtreme::EntranceRuntime;
namespace SohExtreme {
struct SaveConnectionIdentity {
    std::string seed;
    int team = 0, slot = 1;
    bool Valid() const { return !seed.empty() && slot > 0; }
};
}
std::string saveServer = "server", saveSlot = "player", cachedSlotSettingsJson = "settings";
SohExtreme::SaveConnectionIdentity saveConnectionIdentity{"seed", 0, 1};
SettingsMap settingsForReload;
bool metadataForReloadIsAP = true;
SohExtreme::SaveConnectionIdentity identityForReload = saveConnectionIdentity;
std::string serverForReload = saveServer, slotForReload = saveSlot, settingsJsonForReload = cachedSlotSettingsJson;
bool restoreMapDuringLoad = true;
SohExtreme::CrossingJournal gCrossingJournal;

void ReloadMetadata(bool isArchipelagoSave, const std::string& server, const std::string& slot,
                    const std::string& cachedSettingsJson, const SohExtreme::SaveConnectionIdentity& identity) {
    const bool currentSaveIsArchipelago = currentSaveIsAP;
#include "captured_metadata_identity.inc"
#include "captured_metadata_reset.inc"
    currentSaveIsAP = isArchipelagoSave;
    saveConnectionIdentity = identity;
    saveServer = server;
    saveSlot = slot;
    cachedSlotSettingsJson = cachedSettingsJson;
}

using RespawnData = std::remove_reference_t<decltype(gSaveContext.respawn[0])>;
constexpr int ITEM_SWORD_MASTER = 1;
int itemGrants = 0;
void Item_Give(PlayState*, int) { ++itemGrants; }
#include "captured_native_respawn.inc"
#include "captured_native_savewarp.inc"
#include "captured_native_gameover.inc"
#include "captured_grotto_force_return.inc"

constexpr int TEXTBOX_TYPE_BLUE = 0, TEXT_CONTINUE_DUNGEON_MSG = 1, TEXT_CONTINUE_OVERWORLD_MSG = 2;
constexpr int NA_SE_SY_PIECE_OF_HEART = 1;
int gSfxDefaultPos = 0, gSfxDefaultFreqAndVolScale = 0, gSfxDefaultReverb = 0;
template <typename... T> void Audio_PlaySfxGeneral(T...) {}
struct CustomMessage {
    std::string text;
    CustomMessage(const std::string& value, int) : text(value) {}
    static std::string THREE_WAY_CHOICE() { return "<three>"; }
    static std::string TWO_WAY_CHOICE() { return "<two>"; }
};
#include "captured_menu_messages.inc"
static int8_t pendingSpawnAge = -1;
int openedTextId = -1;
void Message_StartTextbox(PlayState*, int text, void*) { openedTextId = text; }
void Play_SaveSceneFlags(PlayState*) {}
#define YEARS_CHILD LINK_AGE_CHILD
#define LINK_AGE_IN_YEARS (child ? LINK_AGE_CHILD : LINK_AGE_ADULT)
#include "captured_sram_dungeon_entries.inc"
void Sram_OpenSave() {
    ReloadMetadata(metadataForReloadIsAP, serverForReload, slotForReload, settingsJsonForReload, identityForReload);
    if (restoreMapDuringLoad && currentSaveIsAP) assert(ER::Apply(settingsForReload));
#include "captured_sram_entrance_selection.inc"
}
#include "captured_menu_spawn.inc"
#include "captured_menu_is_dungeon.inc"
#include "captured_menu_prompt.inc"
#include "captured_menu_begin_reload.inc"
void RunLoadHook() {
    if (!IS_RANDO) return;
    Archipelago_CancelPendingEntranceSpawn();
    Entrance_Init();
#include "captured_load_spawn_gate.inc"
}
void RandomizerResetNoSwimRecovery() {}
#include "captured_native_exit.inc"

class ArchipelagoClient {
public:
    std::vector<int64_t> reports;
    bool HasSceneTransitionChecks() const { return true; }
    bool IsGameplaySessionActive() const { return true; }
    bool IsLocationActive(int64_t) const { return true; }
    void AdvanceDoorTransition() {}
    void ReportTransition(int64_t id) { if (id) reports.push_back(id); }
    void CaptureSceneTransition();
    void CompleteSceneTransition(int16_t);
} client;
#include "captured_client_scene.inc"

std::map<std::string, int> cases;
void Count(const char* name) { ++cases[name]; }
SettingsMap Settings(int mask = 0) {
    SettingsMap result{{"EntranceRandomizerRevision",1}, {"EntrancePoolPolicyRevision",1},
        {"EntranceMixedPoolMask",mask}, {"DungeonDoorMixedOutside",int((mask & 1024) && (mask & ~(4 | 16 | 1024)))},
        {"ShuffleDungeonDoors",(mask & 1024) ? 1 : 0}};
    for (const auto& row : SohExtreme::kEntranceEndpoints) result["EntranceMap." + std::to_string(row.id)] = row.id;
    return result;
}
void SwapPairs(SettingsMap& settings, int first, int second) {
    const int a = SohExtreme::EntranceEndpointById(first)->reverse;
    const int b = SohExtreme::EntranceEndpointById(second)->reverse;
    assert(a >= 0 && b >= 0);
    settings["EntranceMap." + std::to_string(first)] = second;
    settings["EntranceMap." + std::to_string(b)] = a;
    settings["EntranceMap." + std::to_string(second)] = first;
    settings["EntranceMap." + std::to_string(a)] = b;
}
void ResetFixture(const SettingsMap& settings, bool asChild = false) {
    ER::Reset();
    play = {}; gPlayState = &play; gSaveContext = {}; player = {};
    gSaveContext.nextCutsceneIndex = 0xFFEF;
    child = asChild; currentSaveIsAP = true; isRandomizer = true;
    for (auto& option : Rando::Context::GetInstance()->options) option.Set(0);
    for (auto& row : overrides) row = {};
    Entrance_ResetEntranceTable();
    assert(ER::Apply(settings));
    settingsForReload = settings;
    saveServer = serverForReload = "server";
    saveSlot = slotForReload = "player";
    cachedSlotSettingsJson = settingsJsonForReload = "settings";
    saveConnectionIdentity = identityForReload = {"seed", 0, 1};
    metadataForReloadIsAP = restoreMapDuringLoad = true;
    client.reports.clear();
    itemGrants = 0;
}
void FinishArrival(int scene, int nativeRoom = 0, Vec3s nativePosition = {101,202,303}) {
    assert(Archipelago_EntranceBeforeSceneInit());
    assert(Archipelago_EntranceAfterSceneConditions());
    play.sceneNum = scene;
    play.roomCtx.curRoom.num = Archipelago_EntranceSpawnRoom(scene,nativeRoom);
    static ActorEntry nativeEntry;
    nativeEntry = {}; nativeEntry.pos = nativePosition;
    play.linkActorEntry = &nativeEntry;
    Archipelago_EntranceSpawnPosition(scene);
    client.CompleteSceneTransition(scene);
    player.actor.world.pos = {float(play.linkActorEntry->pos.x), float(play.linkActorEntry->pos.y), float(play.linkActorEntry->pos.z)};
    player.actor.shape.rot.y = play.linkActorEntry->rot.y;
    play.transitionTrigger = TRANS_TRIGGER_OFF;
    gSaveContext.respawnFlag = 0;
    gSaveContext.health = 48;
    gSaveContext.savedSceneNum = scene;
#include "captured_room_entry_call.inc"
}
void ArriveResolved(int target, int room = 0, Vec3s position = {101,202,303}) {
    const auto* policy = SohExtreme::EntranceDestinationById(target);
    assert(policy);
    ER::ArmArrival(-1,target);
    gSaveContext.entranceIndex = Grotto_OverrideSpecialEntrance(target);
    const int layer = child ? 0 : 2;
    FinishArrival(policy->normalLayers[layer].scene,room,position);
}
void FinishMenuReload() {
    RandomizerOnExitGameHandler(gSaveContext.fileNum);
    play.state.running = false;
    RunLoadHook();
    play.state.running = true;
}
void BeginDungeonReturn() {
    BeginSaveMenuReload(&play,false);
    FinishMenuReload();
}
void PopulatePreviousScene(const SettingsMap& settings) {
    ResetFixture(settings);
    ArriveResolved(896,0,{123,234,345}); // Zora Shop, a distinct outside-pool scene.
    assert(!ER::previousScene.valid);
    ArriveResolved(8459); // Jabu NW corridor room, reached through a room endpoint.
    assert(ER::previousScene.valid && ER::previousScene.scene == SCENE_ZORA_SHOP);
}

void TestPolicy() {
    constexpr struct { int id; bool dungeon; } categoryTruth[] = {
#include "captured_category_truth.inc"
    };
    for (const auto& row : categoryTruth) {
        assert(SohExtreme::IsDungeonPoolEndpoint(row.id) == row.dungeon);
        Count("catalog_category_classification");
    }
    for (int mask : {0,1024,4,16,4|16|1024,1|2,1024|1,1024|8,2047}) {
        const auto settings = Settings(mask);
        ResetFixture(settings);
        const bool expected = (mask & 1024) && (mask & ~(4|16|1024));
        assert(ER::routing.UsesPreviousSceneReturn() == expected);
        Count("effective_pool_modes");
    }
    auto settings = Settings(2047);
    ResetFixture(settings);
    for (const auto& [key,value] : std::vector<std::pair<std::string,int>>{
            {"EntrancePoolPolicyRevision",2},{"EntranceMixedPoolMask",4096},
            {"DungeonDoorMixedOutside",0},{"ShuffleDungeonDoors",0}}) {
        auto invalid = settings; invalid[key] = value;
        const auto old = ER::routing.Routes();
        assert(!ER::Apply(invalid));
        assert(ER::routing.Routes() == old && ER::routing.UsesPreviousSceneReturn());
        Count("invalid_policy_atomic_rejection");
    }
    settings = Settings();
    settings.erase("EntrancePoolPolicyRevision"); settings.erase("EntranceMixedPoolMask"); settings.erase("DungeonDoorMixedOutside");
    settings["MixedEntrances"] = 1;
    ResetFixture(settings);
    assert(!ER::routing.UsesPreviousSceneReturn());
    Count("legacy_unrelated_mixed_flag");
    SwapPairs(settings,896,8961); // Shop and Spirit door.
    ResetFixture(settings);
    assert(ER::routing.UsesPreviousSceneReturn());
    Count("legacy_actual_door_outside_route");
    settings = Settings();
    settings.erase("EntrancePoolPolicyRevision"); settings.erase("EntranceMixedPoolMask"); settings.erase("DungeonDoorMixedOutside");
    SwapPairs(settings,ENTR_FIRE_TEMPLE_ENTRANCE,8961);
    ResetFixture(settings);
    assert(!ER::routing.UsesPreviousSceneReturn()); // Dungeon entry/exit pair is still dungeon category.
    Count("legacy_dungeon_pair_category");
}
void TestDungeonSpawns() {
    for (const char* flag : {"ShuffleDungeonDoors","ShuffleDungeonsEntrances","ShuffleBossEntrances","ShuffleGanonTowerEntrance"}) {
        auto settings = Settings(); settings[flag] = 1;
        SwapPairs(settings,ENTR_FIRE_TEMPLE_ENTRANCE,ENTR_WATER_TEMPLE_ENTRANCE);
        ResetFixture(settings);
        ArriveResolved(ENTR_FIRE_TEMPLE_ENTRANCE,7);
        player.actor.world.pos = {177,288,399};
        play.roomCtx.curRoom.num = 8;
        Archipelago_EntranceRecordRoomEntry();
        assert(Archipelago_EntranceDungeonReturnMode() == AP_DUNGEON_RETURN_SPAWN);
        StartContinuePrompt(&play);
        assert(openedTextId == TEXT_CONTINUE_DUNGEON_MSG);
        assert(continueDungeonMsg.text.find("Go to Dungeon Spawn") != std::string::npos);
        BeginDungeonReturn();
        assert(gSaveContext.entranceIndex == ENTR_FIRE_TEMPLE_ENTRANCE);
        assert(!ER::arrival && !ER::restartArrival.valid);
        FinishArrival(SCENE_FIRE_TEMPLE);
        assert(play.roomCtx.curRoom.num == 0 && player.actor.world.pos.x == 101);
        assert(client.reports.empty() && !ER::pendingDungeonReturn.valid);
        assert(!Archipelago_EntranceRestoreDungeonReturn());
        Count("separate_dungeon_settings_entryway");
    }
    ResetFixture({{"EntranceRandomizerRevision",0}});
    play.sceneNum = gSaveContext.savedSceneNum = SCENE_SPIRIT_TEMPLE;
    BeginDungeonReturn();
    assert(gSaveContext.entranceIndex == ENTR_SPIRIT_TEMPLE_ENTRANCE);
    assert(Archipelago_EntranceDungeonReturnMode() == AP_DUNGEON_RETURN_SPAWN);
    Count("ap_all_off_dungeon_entryway");
    ResetFixture({{"EntranceRandomizerRevision",0}});
    currentSaveIsAP = metadataForReloadIsAP = false; isRandomizer = false;
    play.sceneNum = gSaveContext.savedSceneNum = SCENE_SHADOW_TEMPLE;
    StartContinuePrompt(&play);
    assert(openedTextId == TEXT_CONTINUE_DUNGEON_MSG);
    BeginDungeonReturn();
    assert(gSaveContext.entranceIndex == ENTR_SHADOW_TEMPLE_ENTRANCE);
    assert(!ER::pendingDungeonReturn.valid);
    Count("vanilla_dungeon_entryway");
    ResetFixture(Settings(4|16|1024));
    ArriveResolved(8459);
    BeginDungeonReturn();
    assert(gSaveContext.entranceIndex == ENTR_JABU_JABU_ENTRANCE && !ER::arrival && !ER::restartArrival.valid);
    Count("dungeon_only_mixed_entryway");
}
void TestBossOwnership() {
    auto settings = Settings(); settings["ShuffleBossEntrances"] = 2;
    SwapPairs(settings,12,773); // Forest boss door -> Volvagia.
    for (bool directSpawn : {false,true}) {
        ResetFixture(settings);
        if (!directSpawn) ArriveResolved(ENTR_FOREST_TEMPLE_ENTRANCE,7);
        ArriveResolved(773);
        assert(ER::roomEntry.dungeonEntrance == ENTR_FOREST_TEMPLE_ENTRANCE);
        BeginDungeonReturn();
        assert(gSaveContext.entranceIndex == ENTR_FOREST_TEMPLE_ENTRANCE);
        FinishArrival(SCENE_FOREST_TEMPLE);
        assert(client.reports.empty());
        Count("shuffled_boss_source_dungeon");
    }
    ResetFixture(settings);
    ArriveResolved(ENTR_FOREST_TEMPLE_ENTRANCE,7);
    ArriveResolved(773);
    gSaveContext.health = 0;
    player.actor.world.pos = {-444,-555,-666};
    play.actorCtx.flags.tempSwch = 0x12345678;
    play.actorCtx.flags.tempCollect = 0x11223344;
    Entrance_SetGameOverEntrance();
    assert(gSaveContext.entranceIndex == ENTR_FOREST_TEMPLE_ENTRANCE);
    Play_TriggerRespawn(&play);
    gSaveContext.respawnFlag = -2; // Actual kaleidoscope continuation assignment.
    assert(play.nextEntranceIndex == ENTR_FOREST_TEMPLE_ENTRANCE);
    assert(Archipelago_EntranceBeforeSceneInit());
    assert(gSaveContext.respawnFlag == 0); // Native Player_Init cannot restore boss flags in the dungeon.
    assert(!ER::restartArrival.valid && itemGrants == 0);
    Count("game_over_dungeon_and_flag_isolation");
}
void TestPreviousScene() {
    const auto settings = Settings(2047);
    ResetFixture(settings);
    ArriveResolved(8459);
    StartContinuePrompt(&play);
    assert(openedTextId == TEXT_CONTINUE_OVERWORLD_MSG);
    assert(Archipelago_EntranceDungeonReturnMode() == AP_DUNGEON_RETURN_NO_PREVIOUS_SCENE);
    assert(!Archipelago_EntranceRequestDungeonReturn());
    assert(continuePreviousSceneMsg.text.find("Return to Previous Scene") != std::string::npos);
    Count("no_history_omits_middle_action");
    PopulatePreviousScene(settings);
    const auto previous = ER::previousScene;
    ArriveResolved(8460); // Full same-scene room reload must not replace the prior Zora Shop scene.
    play.roomCtx.curRoom.num = 7;
    player.actor.world.pos = {411,522,633};
    player.actor.shape.rot.y = 1234;
#include "captured_room_entry_call.inc"
    assert(ER::previousScene.scene == previous.scene && ER::previousScene.position.x == previous.position.x);
    assert(ER::roomEntry.room == 7 && ER::roomEntry.position.x == 411);
    StartContinuePrompt(&play);
    assert(openedTextId == TEXT_CONTINUE_DUNGEON_MSG);
    const auto source = ER::roomEntry;
    BeginDungeonReturn();
    assert(gSaveContext.entranceIndex == 896 && ER::restartArrival.valid);
    FinishArrival(SCENE_ZORA_SHOP);
    assert(play.roomCtx.curRoom.num == previous.room && player.actor.world.pos.x == previous.position.x);
    assert(ER::previousScene.scene == SCENE_JABU_JABU && ER::previousScene.room == 7);
    assert(ER::previousScene.position.x == source.position.x);
    assert(client.reports.empty());
    StartContinuePrompt(&play);
    assert(openedTextId == TEXT_CONTINUE_DUNGEON_MSG); // Also works outside the dungeon after mixed travel.
    BeginDungeonReturn();
    FinishArrival(SCENE_JABU_JABU);
    assert(play.roomCtx.curRoom.num == source.room && player.actor.world.pos.x == source.position.x);
    assert(player.actor.shape.rot.y == source.yaw && client.reports.empty());
    Count("distinct_scene_and_native_room_history");
    const auto sameScene = ER::previousScene;
    assert(ER::Apply(settings));
    assert(ER::previousScene.scene == sameScene.scene && ER::previousScene.position.x == sameScene.position.x);
    assert(!ER::ServicePendingSpawn(true));
    Count("same_map_reconnect_keeps_history");
    PopulatePreviousScene(settings);
    player.actor.world.pos = {-900,-1000,-1100}; gSaveContext.health = 0;
    Entrance_SetGameOverEntrance();
    Play_TriggerRespawn(&play); gSaveContext.respawnFlag = -2;
    assert(play.nextEntranceIndex == 896);
    assert(Archipelago_EntranceBeforeSceneInit() && gSaveContext.respawnFlag == 0);
    assert(ER::restartArrival.position.x == 123);
    Count("game_over_previous_scene");
}
void TestFinalBattleReturns() {
    for (bool active : {false,true}) {
        for (int scene : {SCENE_GANONS_TOWER, SCENE_GANONDORF_BOSS, SCENE_GANON_BOSS,
                          SCENE_GANONS_TOWER_COLLAPSE_INTERIOR, SCENE_GANONS_TOWER_COLLAPSE_EXTERIOR,
                          SCENE_INSIDE_GANONS_CASTLE_COLLAPSE}) {
            ResetFixture(active ? Settings() : SettingsMap{{"EntranceRandomizerRevision",0}});
            play.sceneNum = gSaveContext.savedSceneNum = scene;
            gSaveContext.entranceIndex = ENTR_GANONDORF_BOSS_0;
            gSaveContext.health = 0;
            play.actorCtx.flags.tempSwch = 0x12345678;
            Entrance_SetGameOverEntrance();
            assert(gSaveContext.entranceIndex == ENTR_GANONS_TOWER_0);
            assert(Archipelago_EntranceDungeonReturnInProgress());
            Play_TriggerRespawn(&play);
            gSaveContext.respawnFlag = -2;
            assert(play.nextEntranceIndex == ENTR_GANONS_TOWER_0 && itemGrants == 0);
            assert(Archipelago_EntranceBeforeSceneInit() && gSaveContext.respawnFlag == 0);
            Count(active ? "final_battle_resolved_dungeon_return" : "disabled_map_dungeon_return_flag_isolation");
        }
    }
    ResetFixture(Settings(2047));
    ArriveResolved(896,0,{123,234,345});
    ArriveResolved(ENTR_GANONS_TOWER_0,7,{456,567,678});
    gSaveContext.entranceIndex = ENTR_GANONDORF_BOSS_0;
    FinishArrival(SCENE_GANONDORF_BOSS);
    assert(!ER::roomEntry.valid && ER::roomEntry.scene == SCENE_GANONDORF_BOSS);
    assert(ER::previousScene.scene == SCENE_GANONS_TOWER && ER::previousScene.room == 7);
    gSaveContext.health = 0;
    Entrance_SetGameOverEntrance();
    Play_TriggerRespawn(&play);
    gSaveContext.respawnFlag = -2;
    assert(play.nextEntranceIndex == ENTR_GANONS_TOWER_0);
    FinishArrival(SCENE_GANONS_TOWER);
    assert(play.roomCtx.curRoom.num == 7 && player.actor.world.pos.x == 456);
    assert(!ER::previousScene.valid && itemGrants == 0);
    assert(Archipelago_EntranceDungeonReturnMode() == AP_DUNGEON_RETURN_NO_PREVIOUS_SCENE);
    Count("scripted_scene_keeps_immediate_safe_history");
    PopulatePreviousScene(Settings(2047));
    play.sceneNum = gSaveContext.savedSceneNum = SCENE_GANON_BOSS;
    gSaveContext.health = 0;
    Entrance_SetGameOverEntrance();
    Play_TriggerRespawn(&play);
    assert(play.nextEntranceIndex == 896 && itemGrants == 0);
    Count("final_battle_resolved_previous_scene_return");
    ResetFixture({{"EntranceRandomizerRevision",0}});
    currentSaveIsAP = false;
    play.sceneNum = SCENE_GANON_BOSS;
    Play_TriggerRespawn(&play);
    assert(play.nextEntranceIndex == ENTR_GANONS_TOWER_COLLAPSE_EXTERIOR_0 && itemGrants == 1);
    Count("ordinary_native_final_battle_respawn_preserved");
}
void TestSharedGrottoHistory() {
    for (bool asChild : {false,true}) {
        for (const auto& policy : SohExtreme::kEntranceDestinationPolicies) {
            if ((policy.kind != SohExtreme::kEntranceGrottoLoad &&
                 policy.kind != SohExtreme::kEntranceGrottoReturn) ||
                !SohExtreme::EntranceDestinationAllowsAge(&policy,
                    asChild ? SohExtreme::kEntranceChildAge : SohExtreme::kEntranceAdultAge)) continue;
            ResetFixture(Settings(1024 | 8),asChild);
            ArriveResolved(policy.id,1,{456,567,678});
            const auto original = ER::roomEntry;
            assert(original.valid && original.target == policy.id);
            ArriveResolved(8459);
            assert(ER::previousScene.target == policy.id);
            BeginDungeonReturn();
            assert(ER::restartArrival.target == policy.id);
            FinishArrival(original.scene);
            assert(play.roomCtx.curRoom.num == original.room);
            assert(player.actor.world.pos.x == original.position.x);
            assert(ER::roomEntry.target == policy.id && client.reports.empty());
            assert(grottoId == (policy.id & 0xFF));
            if (policy.kind == SohExtreme::kEntranceGrottoLoad)
                assert(gSaveContext.respawn[RESPAWN_MODE_RETURN].data == grottoLoadTable[grottoId].content);
            Count(asChild ? "child_shared_grotto_previous_scene" : "adult_shared_grotto_previous_scene");
        }
    }
}
void TestLifecycleAndSpawn() {
    auto settings = Settings(2047);
    settings["EntranceMap.187"] = 8961;
    settings["EntranceMap.642"] = 130;
    for (int invalidator = 0; invalidator < 7; ++invalidator) {
        PopulatePreviousScene(settings);
        assert(Archipelago_EntranceRequestDungeonReturn());
        switch (invalidator) {
            case 0: identityForReload.seed = "other-seed"; break;
            case 1: identityForReload.team = 1; break;
            case 2: identityForReload.slot = 2; break;
            case 3: serverForReload = "other-server"; break;
            case 4: slotForReload = "other-player"; break;
            case 5: settingsJsonForReload = "other-settings"; break;
            case 6: metadataForReloadIsAP = false; break;
        }
        Sram_OpenSave();
        assert(!ER::pendingDungeonReturn.valid && !ER::previousScene.valid && !ER::roomEntry.valid);
        Count("different_metadata_discards_history_request");
    }
    for (int invalidator = 0; invalidator < 3; ++invalidator) {
        PopulatePreviousScene(settings);
        assert(Archipelago_EntranceRequestDungeonReturn());
        if (invalidator == 0) gSaveContext.fileNum = 1;
        if (invalidator == 1) child = true;
        if (invalidator == 2) {
            auto changed = settings; SwapPairs(changed,896,1119);
            assert(ER::Apply(changed));
        }
        assert(!Archipelago_EntranceRestoreDungeonReturn());
        assert(!ER::pendingDungeonReturn.valid);
        Count("file_age_map_request_invalidation");
    }
    PopulatePreviousScene(settings);
    child = true;
    assert(Archipelago_EntranceDungeonReturnMode() == AP_DUNGEON_RETURN_NO_PREVIOUS_SCENE);
    ER::BeforeSceneInit();
    assert(!ER::previousScene.valid);
    Count("age_change_invalidates_live_history");
    PopulatePreviousScene(settings);
    assert(Archipelago_EntranceRequestDungeonReturn());
    BeginSaveMenuReload(&play,true);
    assert(!ER::pendingDungeonReturn.valid && !ER::previousScene.valid);
    FinishMenuReload();
    gSaveContext.entranceIndex = GetAgeSpawnEntrance(LINK_AGE_CHILD);
    child = true;
    FinishArrival(SCENE_SPIRIT_TEMPLE);
    assert(play.roomCtx.curRoom.num == SohExtreme::EntranceEndpointById(8961)->room);
    assert(!ER::previousScene.valid && client.reports.empty());
    Count("explicit_age_spawn_overrides_return_and_history");
    PopulatePreviousScene(settings);
    restoreMapDuringLoad = false;
    BeginSaveMenuReload(&play,false);
    assert(ER::pendingDungeonReturn.valid && !ER::slotMapLoaded);
    FinishMenuReload();
    assert(ER::pendingDungeonReturn.valid && ER::pendingSpawnAge == -1);
    assert(ER::Apply(settings));
    assert(!ER::ServicePendingSpawn(false));
    play.transitionTrigger = TRANS_TRIGGER_OFF;
    assert(ER::ServicePendingSpawn(true) && play.nextEntranceIndex == 896);
    assert(!ER::pendingDungeonReturn.valid);
    Count("late_map_completes_one_explicit_return");
}
int main() {
    TestPolicy(); TestDungeonSpawns(); TestBossOwnership(); TestPreviousScene(); TestFinalBattleReturns();
    TestSharedGrottoHistory(); TestLifecycleAndSpawn();
    assert(itemGrants == 0);
    nlohmann::json report = cases;
    std::cout << report.dump(2) << '\n';
}
