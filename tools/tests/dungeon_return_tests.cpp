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
// Ammo observations are an independent per-save service. The ammo fixtures
// execute that store; the return fixture supplies only its reset boundary.
int ammoSourceFile = 0;
void ResetAmmoSources() { ammoSourceFile = gSaveContext.fileNum; }

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

constexpr int ITEM_SWORD_MASTER = 1;
int itemGrants = 0;
void Item_Give(PlayState*, int) { ++itemGrants; }
#include "captured_native_respawn.inc"
#include "captured_native_savewarp.inc"
#include "captured_native_gameover.inc"
#include "captured_grotto_force_special.inc"
#include "captured_grotto_force_return.inc"
#include "captured_grotto_force_void.inc"
#include "captured_grotto_identity.inc"
#include "captured_grotto_ownership.inc"

// Only the collision query results are supplied by this integration fixture.
// Actual geometry is separately compiled by test_grotto_landing_native.py.
bool landingGeometryClear = true, landingValidationClear = true;
bool resolveLandingOnArrival = true;
CollisionPoly fixtureFloor;
static bool Grotto_FindReturnLanding(Player*, Vec3f* point, CollisionPoly** poly) {
    if (!landingGeometryClear) return false;
    *point = grottoLanding.origin;
    point->x += Math_SinS(grottoLanding.yaw) * 64.0f;
    point->z += Math_CosS(grottoLanding.yaw) * 64.0f;
    *poly = &fixtureFloor;
    return true;
}
static bool Grotto_ValidateLanding(Player*, Vec3f* point, CollisionPoly** poly) {
    *poly = &fixtureFloor;
    return landingValidationClear && Grotto_PointClearOfHoles(point, 20.0f);
}
#include "captured_grotto_landing_state.inc"

int nativeEmergences = 0, nativeIdleStarts = 0;
constexpr int Player_Action_8084F9A0 = 0;
void Player_SetupAction(PlayState*, Player*, int, int) {}
void Player_StartGrottoEmergence(PlayState*, Player* link) {
    ++nativeEmergences;
    link->actor.velocity.y = 12.0f;
    link->actor.bgCheckFlags &= ~BGCHECKFLAG_GROUND;
}
void Player_StartMode_Idle(PlayState*, Player*) { ++nativeIdleStarts; }
#include "captured_player_grotto_start.inc"
void DispatchFirstGrottoUpdate(PlayState* play, Player* link) {
#include "captured_player_grotto_dispatch.inc"
}

constexpr int VB_INFLICT_VOID_DAMAGE = 0;
template <typename... Args> bool GameInteractor_Should(int, bool vanilla, Args...) { return vanilla; }
void Math_Vec3f_Copy(Vec3f* destination, const Vec3f* source) { *destination = *source; }
int func_80845C68(PlayState*, int) { return 0; }
void ApplyNativePlayerRespawn(PlayState* play, Player* link) {
    Actor* thisx = &link->actor;
    int respawnFlag, respawnMode;
#include "captured_player_respawn_override.inc"
#include "captured_player_down_checkpoint.inc"
}

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
        {"EntranceRiverPathsRevision",1},
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
    gSaveContext.linkAge = child ? LINK_AGE_CHILD : LINK_AGE_ADULT;
    landingGeometryClear = landingValidationClear = resolveLandingOnArrival = true;
    nativeEmergences = nativeIdleStarts = 0;
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
    const bool explicitReturn = ER::dungeonReturnArrival;
    assert(Archipelago_EntranceBeforeSceneInit());
    if (explicitReturn) assert(gSaveContext.respawnFlag == 0);
    assert(Archipelago_EntranceAfterSceneConditions());
    play.sceneNum = scene;
    play.roomCtx.curRoom.num = gSaveContext.respawnFlag > 0 ?
        gSaveContext.respawn[gSaveContext.respawnFlag - 1].roomIndex :
        Archipelago_EntranceSpawnRoom(scene,nativeRoom);
    static ActorEntry nativeEntry;
    nativeEntry = {}; nativeEntry.pos = nativePosition;
    play.linkActorEntry = &nativeEntry;
    Archipelago_EntranceSpawnPosition(scene);
    client.CompleteSceneTransition(scene);
    player = {}; // The scene creates a fresh player before Player_Init.
    player.actor.world.pos = {float(play.linkActorEntry->pos.x), float(play.linkActorEntry->pos.y), float(play.linkActorEntry->pos.z)};
    player.actor.shape.rot.y = play.linkActorEntry->rot.y;
    player.actor.params = play.linkActorEntry->params;
    ApplyNativePlayerRespawn(&play, &player);
    if (((player.actor.params >> 8) & 0xF) == 4) Player_StartMode_Grotto(&play, &player);
    play.transitionTrigger = TRANS_TRIGGER_OFF;
    gSaveContext.respawnFlag = 0;
    gSaveContext.health = 48;
    gSaveContext.savedSceneNum = scene;
#include "captured_room_entry_call.inc"
    if (resolveLandingOnArrival) DispatchFirstGrottoUpdate(&play, &player);
}
void ArriveResolved(int target, int room = 0, Vec3s position = {101,202,303}) {
    const auto* policy = SohExtreme::EntranceDestinationById(target);
    assert(policy);
    if (ER::roomEntry.scene >= 0) {
        ER::RememberPlayerPosition();
        ER::CaptureSceneDeparture(true);
    }
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
bool SamePoint(const ER::SceneReturnPoint& a, const ER::SceneReturnPoint& b) {
    return a.valid == b.valid && a.scene == b.scene && a.room == b.room && a.age == b.age &&
           a.file == b.file && a.target == b.target && a.position.x == b.position.x &&
           a.position.y == b.position.y && a.position.z == b.position.z && a.yaw == b.yaw &&
           a.dungeonEntrance == b.dungeonEntrance && a.grottoEmergence == b.grottoEmergence;
}
void AssertPlayerAt(const ER::SceneReturnPoint& point) {
    assert(play.sceneNum == point.scene && play.roomCtx.curRoom.num == point.room);
    assert(player.actor.world.pos.x == static_cast<s16>(point.position.x) &&
           player.actor.world.pos.y == static_cast<s16>(point.position.y) &&
           player.actor.world.pos.z == static_cast<s16>(point.position.z) && player.actor.shape.rot.y == point.yaw);
}
void MovePlayer(Vec3f position, s16 yaw = 0) {
    player.actor.world.pos = position;
    player.actor.shape.rot.y = yaw;
    ER::RememberPlayerPosition();
}
bool RequestNativeRoom(int roomNum) {
    auto* roomCtx = &play.roomCtx;
#include "captured_room_request_hook.inc"
    // Resource/room allocation is the isolated IO boundary. The production
    // pre-request hook above must run before the engine replaces curRoom.
    if (roomCtx->status != 0) return false;
    roomCtx->curRoom.num = roomNum;
    roomCtx->status = 1;
    return true;
}
void FinishNativeRoom(int selectedRoom) {
    play.roomCtx.curRoom.num = selectedRoom;
    play.roomCtx.status = 0;
#include "captured_room_entry_call.inc"
}
void FinishQueuedArrival(int target) {
    const auto* policy = SohExtreme::EntranceDestinationById(target);
    assert(policy);
    client.CaptureSceneTransition();
    gSaveContext.entranceIndex = play.nextEntranceIndex;
    FinishArrival(policy->normalLayers[child ? 0 : 2].scene);
}
ER::SceneReturnPoint CrossMappedDoor(int source, bool finish = true) {
    const auto* door = SohExtreme::EntranceEndpointById(source);
    assert(door && door->door >= 0 && play.sceneNum == door->sourceScene &&
           play.roomCtx.curRoom.num == door->fromRoom);
    const auto entry = ER::roomEntry, history = ER::previousScene;
    Actor actor;
    actor.world.pos = {float(door->x), float(door->y), float(door->z)};
    actor.shape.rot.y = door->yaw;
    const float nx = Math_SinS(door->yaw), nz = Math_CosS(door->yaw);
    const float side = door->side == 1 ? 1.0f : -1.0f;
    MovePlayer({door->x + nx * side * 22.0f, float(door->y), door->z + nz * side * 22.0f},
               static_cast<s16>(door->yaw + (side > 0 ? 0x8000 : 0)));
    const auto departure = ER::CaptureReturnPoint();
    ER::BeginDoor(door->door, door->fromRoom, door->room, &actor, door->side);
    assert(ER::openedDoor && SamePoint(ER::doorDeparture.point, departure));
    if (door->fromRoom != door->room) assert(RequestNativeRoom(door->room));
    assert(SamePoint(ER::roomEntry, entry) && SamePoint(ER::previousScene, history));
    player.actor.world.pos = {door->x - nx * side * 60.0f, float(door->y), door->z - nz * side * 60.0f};
    ER::AdvanceDoor();
    assert(play.transitionTrigger == TRANS_TRIGGER_START && ER::pendingDepartureRecorded);
    FinishNativeRoom(door->room); // Native doorway completion must not record the intermediate room.
    assert(SamePoint(ER::roomEntry, entry) && SamePoint(ER::previousScene, history));
    if (finish) FinishQueuedArrival(ER::routing.Destination(source));
    return departure;
}
void DieAndReturnToCurrentRoom() {
    const auto checkpoint = ER::roomEntry, history = ER::previousScene;
    const auto reportCount = client.reports.size();
    player.actor.world.pos = {-444,-555,-666};
    gSaveContext.health = 0;
    play.actorCtx.flags.tempSwch = 0x12345678;
    play.actorCtx.flags.tempCollect = 0x11223344;
    Entrance_SetGameOverEntrance();
    assert(ER::restartArrival.valid && ER::preserveHistoryForArrival);
    assert(ER::restartArrival.target == checkpoint.target);
    Play_TriggerRespawn(&play);
    gSaveContext.respawnFlag = -2; // Actual kaleidoscope continuation assignment.
    Grotto_ForceGrottoReturn();
    FinishQueuedArrival(checkpoint.target);
    AssertPlayerAt(checkpoint);
    assert(SamePoint(ER::previousScene, history) && !ER::preserveHistoryForArrival);
    assert(client.reports.size() == reportCount && itemGrants == 0);
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
    DieAndReturnToCurrentRoom();
    assert(play.sceneNum == SCENE_FIRE_TEMPLE_BOSS && ER::roomEntry.dungeonEntrance == ENTR_FOREST_TEMPLE_ENTRANCE);
    BeginDungeonReturn();
    assert(gSaveContext.entranceIndex == ENTR_FOREST_TEMPLE_ENTRANCE);
    Count("boss_death_same_room_and_menu_source_dungeon");
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

    ResetFixture(settings);
    ArriveResolved(896,0,{123,234,345});
    const auto initialShopEntry = ER::roomEntry;
    MovePlayer({432,234,654},1234);
    const auto shopDoorway = ER::CaptureReturnPoint();
    ArriveResolved(8459);
    assert(!SamePoint(initialShopEntry, ER::previousScene));
    assert(SamePoint(shopDoorway, ER::previousScene));
    DieAndReturnToCurrentRoom();
    DieAndReturnToCurrentRoom();
    assert(SamePoint(shopDoorway, ER::previousScene));
    Count("repeated_death_keeps_departure_history");

    const auto jabuCheckpoint = ER::roomEntry;
    StartContinuePrompt(&play);
    assert(openedTextId == TEXT_CONTINUE_DUNGEON_MSG);
    BeginDungeonReturn();
    assert(gSaveContext.entranceIndex == 896 && ER::restartArrival.valid);
    FinishArrival(SCENE_ZORA_SHOP);
    AssertPlayerAt(shopDoorway);
    assert(SamePoint(ER::previousScene, jabuCheckpoint));
    assert(client.reports.empty());
    StartContinuePrompt(&play);
    assert(openedTextId == TEXT_CONTINUE_DUNGEON_MSG);
    BeginDungeonReturn();
    FinishArrival(SCENE_JABU_JABU);
    AssertPlayerAt(jabuCheckpoint);
    assert(client.reports.empty());
    Count("return_restores_departure_position_and_yaw");

    const auto history = ER::previousScene;
    assert(ER::Apply(settings));
    assert(SamePoint(ER::previousScene, history));
    assert(!ER::ServicePendingSpawn(true));
    Count("same_map_reconnect_keeps_history");
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
    ER::CaptureSceneDeparture(true);
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
void TestImmediateMappedRoomHistory() {
    for (bool sameRoom : {false,true}) {
        auto settings = Settings(2047);
        if (sameRoom) SwapPairs(settings,8460,8463); // Corridor -> another door in that same room.
        PopulatePreviousScene(settings); // Current Jabu room 7, older history Zora Shop.
        const auto oldEntry = ER::roomEntry;
        const auto departure = CrossMappedDoor(8460);
        const auto current = ER::roomEntry;
        assert(play.sceneNum == SCENE_JABU_JABU);
        assert(play.roomCtx.curRoom.num == (sameRoom ? 7 : 8));
        assert(!SamePoint(oldEntry, current));
        assert(SamePoint(ER::previousScene, departure));
        assert(Archipelago_EntranceDungeonReturnMode() == AP_DUNGEON_RETURN_PREVIOUS_SCENE);
        assert(client.reports.size() == 1 && client.reports.front() == SohExtreme::EntranceEndpointById(8460)->check);
        DieAndReturnToCurrentRoom();
        DieAndReturnToCurrentRoom();
        assert(SamePoint(ER::previousScene, departure));
        BeginDungeonReturn();
        FinishArrival(SCENE_JABU_JABU);
        AssertPlayerAt(departure);
        assert(client.reports.size() == 1);
        const auto returnToB = ER::previousScene;
        BeginDungeonReturn();
        FinishArrival(SCENE_JABU_JABU);
        AssertPlayerAt(returnToB);
        assert(client.reports.size() == 1);
        Count(sameRoom ? "same_room_different_door_return_and_death" : "same_scene_next_room_return_and_death");
    }
    for (int mask : {0,1024,4,16,4|16|1024}) {
        ResetFixture(Settings(mask));
        ArriveResolved(8459);
        CrossMappedDoor(8460);
        DieAndReturnToCurrentRoom();
        assert(play.roomCtx.curRoom.num == 8);
        assert(Archipelago_EntranceDungeonReturnMode() == AP_DUNGEON_RETURN_SPAWN);
        BeginDungeonReturn();
        assert(gSaveContext.entranceIndex == ENTR_JABU_JABU_ENTRANCE);
        FinishArrival(SCENE_JABU_JABU);
        assert(play.roomCtx.curRoom.num == 0);
        Count("death_checkpoint_independent_of_dungeon_menu_policy");
    }
}
void TestNativeRoomCompletion() {
    PopulatePreviousScene(Settings(2047));
    const auto entry = ER::roomEntry, history = ER::previousScene;
    play.transiActorCtx.numActors = 2;
    MovePlayer({30,-260,-60},1234);
    Archipelago_EntranceObserveRoomBoundary(0,7,8,false);
    const auto boundary = ER::CaptureReturnPoint();
    // Actual end-of-Player_Update precedes the invisible hallway actor. The
    // request occurs 50..100 units on the far side while curRoom is still 7.
    MovePlayer({30,-260,60},1234);
    Archipelago_EntranceObserveRoomBoundary(0,8,7,false);
    Archipelago_EntranceSelectRoomBoundary(0,8);
    assert(RequestNativeRoom(8));
    assert(SamePoint(ER::nativeRoomDeparture, boundary));
    assert(SamePoint(ER::roomEntry, entry) && SamePoint(ER::previousScene, history));
    // Return without finishing the far room. Both checkpoints remain unchanged.
    MovePlayer({30,-260,-180},2345);
    FinishNativeRoom(7);
    assert(SamePoint(ER::roomEntry, entry) && SamePoint(ER::previousScene, history));
    assert(!ER::nativeRoomDeparture.valid);
    Count("abandoned_hallway_preload_keeps_checkpoint_and_history");

    MovePlayer({40,-260,-80},3456);
    Archipelago_EntranceObserveRoomBoundary(0,7,8,false);
    Archipelago_EntranceSelectRoomBoundary(0,8);
    assert(RequestNativeRoom(8));
    // A visible narrow hallway can preload at 150 units; keep refining its
    // source-side point while Link approaches, even though curRoom was swapped.
    player.actor.world.pos = {40,-260,-20};
    Archipelago_EntranceObserveRoomBoundary(0,7,8,false);
    const auto beforePlane = ER::nativeRoomDeparture;
    player.actor.world.pos = {40,-260,80};
    Archipelago_EntranceObserveRoomBoundary(0,8,7,false);
    FinishNativeRoom(8);
    assert(SamePoint(ER::previousScene, beforePlane));
    assert(ER::previousScene.room == 7 && ER::previousScene.position.z == -20);
    assert(ER::roomEntry.room == 8 && ER::roomEntry.position.z == 80);
    DieAndReturnToCurrentRoom();
    BeginDungeonReturn();
    FinishArrival(SCENE_JABU_JABU);
    AssertPlayerAt(beforePlane);
    assert(client.reports.empty());
    Count("completed_native_hallway_source_side_return_and_death");

    const auto current = ER::roomEntry;
    player.actor.bgCheckFlags = BGCHECKFLAG_GROUND;
    MovePlayer({10,200,-10},4567);
    const auto grounded = ER::CaptureReturnPoint();
    player.actor.bgCheckFlags = 0;
    MovePlayer({10,40,-10},4567);
    play.transiActorCtx.numActors = 2;
    Archipelago_EntranceObserveRoomBoundary(1,current.room,9,true);
    Archipelago_EntranceSelectRoomBoundary(1,9);
    assert(SamePoint(ER::nativeRoomDeparture, grounded));
    assert(RequestNativeRoom(9));
    player.actor.world.pos.y = -60;
    FinishNativeRoom(9);
    assert(SamePoint(ER::previousScene, grounded));
    Count("vertical_boundary_uses_grounded_source_position");

    PopulatePreviousScene(Settings(2047));
    const auto checkpoint = ER::roomEntry;
    const auto prior = ER::previousScene;
    const auto* door = SohExtreme::EntranceEndpointById(8460);
    Actor actor; actor.world.pos = {float(door->x),float(door->y),float(door->z)}; actor.shape.rot.y=door->yaw;
    MovePlayer({float(door->x),float(door->y),float(door->z + 22)},0);
    ER::BeginDoor(door->door,door->fromRoom,door->room,&actor,door->side);
    assert(RequestNativeRoom(8));
    FinishNativeRoom(7);
    assert(SamePoint(ER::roomEntry,checkpoint) && SamePoint(ER::previousScene,prior));
    assert(!ER::openedDoor && !ER::pendingDepartureRecorded);
    Count("abandoned_mapped_shutter_keeps_checkpoint_and_history");
}
void TestReloadAndRecoveryHistory() {
    PopulatePreviousScene(Settings(2047));
    const auto history = ER::previousScene;
    const int target = ER::roomEntry.target;
    const int scene = play.sceneNum;
    MovePlayer({777,888,999},7890);
    auto* play = gPlayState;
#include "captured_suns_song_reload.inc"
    client.CaptureSceneTransition();
    assert(!ER::pendingDepartureRecorded);
    gSaveContext.entranceIndex = play->nextEntranceIndex;
    FinishArrival(scene);
    assert(SamePoint(ER::previousScene,history));
    assert(client.reports.empty());
    (void)target;
    Count("suns_song_reload_preserves_previous_doorway");

    auto settings = Settings(2047);
    SwapPairs(settings,8460,8861);
    PopulatePreviousScene(settings);
    const auto safeHistory = ER::previousScene;
    CrossMappedDoor(8460);
    assert(gPlayState->sceneNum == SCENE_WATER_TEMPLE);
    assert(client.reports.size() == 1);
    assert(Archipelago_EntranceReturnFromUnsafeArrival());
    FinishQueuedArrival(8461); // Already resolved source-side endpoint; never shuffle again.
    assert(gPlayState->sceneNum == SCENE_JABU_JABU && gPlayState->roomCtx.curRoom.num == 7);
    assert(SamePoint(ER::previousScene,safeHistory));
    assert(client.reports.size() == 1 && !Archipelago_EntranceReturnFromUnsafeArrival());
    DieAndReturnToCurrentRoom();
    assert(SamePoint(ER::previousScene,safeHistory));
    Count("wet_arrival_recovery_restores_history_without_extra_credit");
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
            AssertPlayerAt(original);
            assert(ER::roomEntry.target == policy.id && client.reports.empty());
            assert(grottoId == (policy.id & 0xFF));
            if (policy.kind == SohExtreme::kEntranceGrottoLoad)
                assert(gSaveContext.respawn[RESPAWN_MODE_RETURN].data == grottoLoadTable[grottoId].content);
            Count(asChild ? "child_shared_grotto_previous_scene" : "adult_shared_grotto_previous_scene");
        }
    }
}
void TestGrottoLandingAndNativeOverrides() {
    for (bool asChild : {false,true}) {
        ResetFixture(Settings(1024 | 8),asChild);
        ArriveResolved(896,0,{123,234,345});
        ArriveResolved(2062); // HF stone-bridge/tree grotto exterior return.
        assert(ER::roomEntry.valid && ER::roomEntry.target == 2062);
        assert(grottoLanding.landed && !Grotto_HasPendingReturnLanding());
        assert(!ER::roomEntry.grottoEmergence && nativeIdleStarts == 1 && nativeEmergences == 0);
        const auto landed = ER::roomEntry, history = ER::previousScene;
        assert(history.target == 896);
        assert(std::hypot(landed.position.x - grottoReturnTable[14].pos.x,
                          landed.position.z - grottoReturnTable[14].pos.z) > 50.0f);
        for (const int mode : {RESPAWN_MODE_DOWN, RESPAWN_MODE_RETURN}) {
            const auto& data = gSaveContext.respawn[mode];
            assert(data.playerParams == 0x0DFF && data.pos.x == landed.position.x &&
                   data.pos.z == landed.position.z && data.yaw == landed.yaw);
        }
        Count("exterior_player_override_then_landed_checkpoint");

        // Both native helpers must reuse the proven point, including the later
        // positive-respawnFlag override inside the real Player_Init block.
        for (bool special : {false,true}) {
            if (special) Grotto_ForceGrottoReturnOnSpecialEntrance();
            else Grotto_ForceRegularVoidOut();
            player.actor.world.pos = {1,2,3};
            ApplyNativePlayerRespawn(&play, &player);
            assert(player.actor.world.pos.x == landed.position.x &&
                   player.actor.world.pos.z == landed.position.z && player.actor.params == 0x0DFF);
            assert(SamePoint(ER::previousScene, history));
            Count("native_force_helper_reuses_landed_point");
        }
        gSaveContext.respawnFlag = 0;
        DieAndReturnToCurrentRoom();
        assert(!ER::roomEntry.grottoEmergence);
        Count("death_after_grotto_landing_keeps_previous_scene");

        // Reject a falling/on-hole departure point even if the doorway actor
        // continues to update before the transition starts.
        MovePlayer({landed.position.x + 80.0f, landed.position.y, landed.position.z},0x1234);
        const auto departure = ER::lastGroundPosition;
        Actor hole;
        hole.id = ACTOR_DOOR_ANA; hole.update = +[]{};
        hole.world.pos = grottoReturnTable[14].pos;
        play.actorCtx.actorLists[0].head = &hole;
        player.actor.world.pos = hole.world.pos;
        player.stateFlags1 |= PLAYER_STATE1_FLOOR_DISABLED;
        player.actor.bgCheckFlags &= ~BGCHECKFLAG_GROUND;
        ER::RememberPlayerPosition();
        assert(SamePoint(ER::lastGroundPosition, departure));
        ArriveResolved(1806,0,{456,567,678});
        assert(ER::roomEntry.target == 1806 && play.sceneNum == SCENE_GROTTOS);
        assert(!Grotto_HasPendingReturnLanding());
        assert(SamePoint(ER::previousScene, departure));
        play.actorCtx.actorLists[0].head = nullptr;
        BeginDungeonReturn();
        FinishArrival(departure.scene);
        AssertPlayerAt(departure);
        assert(player.actor.params == 0x0DFF && !ER::roomEntry.grottoEmergence);
        Count("grotto_previous_scene_uses_last_clear_departure");

        // The exit origin has not become a stationary checkpoint if death
        // interrupts the queued start before the first collision-ready update.
        ResetFixture(Settings(1024 | 8),asChild);
        ArriveResolved(896);
        resolveLandingOnArrival = false;
        ArriveResolved(2062);
        assert(ER::roomEntry.grottoEmergence && Grotto_HasPendingReturnLanding());
        DieAndReturnToCurrentRoom();
        assert(player.actor.params == 0x04FF && ER::roomEntry.grottoEmergence);
        assert(Grotto_HasPendingReturnLanding() && nativeIdleStarts == 0);
        const auto pendingHistory = ER::previousScene;
        landingGeometryClear = false;
        DispatchFirstGrottoUpdate(&play,&player);
        assert(nativeEmergences == 1 && grottoLanding.observing && !grottoLanding.landed);
        Grotto_UpdateReturnLanding(&player.actor);
        assert(ER::roomEntry.grottoEmergence); // Airborne is not a landing.
        Count("death_before_grotto_landing_replays_emergence");

        hole.world.pos = grottoLanding.origin;
        play.actorCtx.actorLists[0].head = &hole;
        player.actor.bgCheckFlags |= BGCHECKFLAG_GROUND;
        Grotto_UpdateReturnLanding(&player.actor);
        assert(ER::roomEntry.grottoEmergence); // Ground under the hole is insufficient.
        player.actor.world.pos.x += 80.0f;
        Grotto_UpdateReturnLanding(&player.actor);
        assert(grottoLanding.landed && !ER::roomEntry.grottoEmergence);
        assert(SamePoint(ER::previousScene,pendingHistory));
        assert(gSaveContext.respawn[RESPAWN_MODE_RETURN].playerParams == 0x0DFF);
        play.actorCtx.actorLists[0].head = nullptr;
        DieAndReturnToCurrentRoom();
        Count("native_emergence_landing_updates_only_current_checkpoint");
    }
    auto settings = Settings(2047);
    settings["EntranceMap.187"] = 1806;
    ResetFixture(settings,true);
    assert(ER::routing.Destination(187) == 1806);
    assert(GetAgeSpawnEntrance(LINK_AGE_CHILD) == grottoLoadTable[14].entranceIndex);
    FinishArrival(SCENE_GROTTOS,0,{111,222,333});
    assert(ER::roomEntry.target == 1806 && !Grotto_HasPendingReturnLanding());
    assert(play.sceneNum == SCENE_GROTTOS && nativeIdleStarts == 0 && nativeEmergences == 0);
    Count("existing_seed_interior_spawn_1806_is_not_converted_to_exterior");
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
    TestImmediateMappedRoomHistory(); TestNativeRoomCompletion(); TestReloadAndRecoveryHistory();
    TestSharedGrottoHistory(); TestGrottoLandingAndNativeOverrides(); TestLifecycleAndSpawn();
    assert(itemGrants == 0);
    nlohmann::json report = cases;
    std::cout << report.dump(2) << '\n';
}
