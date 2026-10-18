"""Compile actual AP spawn/runtime, save-menu helper and grotto reset code.

Engine IO is isolated. This verifies cached/late map lifecycles and fixed age
destinations, not game collision, a Windows build or an in-game playthrough.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


CASES = r'''
bool isRandomizer = true;
#define IS_RANDO isRandomizer
#define RAND_GET_OPTION(key) (Rando::Context::GetInstance()->GetOption(key).value)
constexpr int ENTR_TEMPLE_OF_TIME_WARP_PAD = 1524;

// Isolated native fallback for this spawn-only test. The AP resolver and load
// gate below are the actual production code, including a missing-map request.
void Entrance_SetSavewarpEntrance() {
    if (Archipelago_EntranceSavewarp()) return;
    gSaveContext.entranceIndex = child ? ENTR_LINKS_HOUSE_CHILD_SPAWN : ENTR_TEMPLE_OF_TIME_WARP_PAD;
}
#include "captured_save_menu_spawn.inc"
void RunLoadSpawnHook() {
    Archipelago_CancelPendingEntranceSpawn();
#include "captured_load_spawn_gate.inc"
}

int main() {
    using namespace SohExtreme;
    using namespace SohExtreme::EntranceRuntime;
    const std::unordered_map<std::string,int> settings{
        {"EntranceRandomizerRevision",1}, {"EntranceMap.187",8961}, {"EntranceMap.642",130}
    };
    auto resetFile = [&]() {
        Reset();
        gSaveContext = {};
        gPlayState = &play;
        play = {};
        currentSaveIsAP = true;
        child = true;
        isRandomizer = true;
        std::fill_n(overrides, ENTRANCE_OVERRIDES_MAX_COUNT, EntranceOverride{});
        Entrance_Init();
        Rando::Context::GetInstance()->GetOption(RSK_SHUFFLE_ENTRANCES).Set(0);
    };
    const auto* childTarget = EntranceEndpointById(8961);
    assert(childTarget && childTarget->room != 0 && childTarget->scene == 6);

    resetFile();
    assert(Apply(settings));
    for (int reload = 0; reload < 3; ++reload) {
        gSaveContext.cutsceneIndex = 0xFFF1;
        RunLoadSpawnHook();
        assert(gSaveContext.entranceIndex == childTarget->anchor);
        assert(arrival == childTarget && pendingSpawnAge == -1);
        assert(gSaveContext.cutsceneIndex == 0 && suppressTransitionChecks);
        SceneInit(childTarget->scene);
        assert(gPlayState->roomCtx.curRoom.num == childTarget->room);
        assert(Complete(childTarget->scene) == 0);
    }
    std::cout << "PASS: cached child loads reuse the chosen exact room and clear the opening cutscene.\n";

    // Same-scene age change: a child room-door and adult lobby must not share
    // the child's custom arrival. Exercise the actual BetterSaveMenu helper.
    assert(Archipelago_EntranceSavewarp());
    assert(arrival == childTarget);
    const int adultEntrance = GetAgeSpawnEntrance(LINK_AGE_ADULT);
    assert(adultEntrance == 130 && arrival == nullptr && pendingSpawnAge == -1);
    child = false;
    SceneInit(6);
    assert(gPlayState->roomCtx.curRoom.num == 0 && Complete(6) == 0);
    assert(GetAgeSpawnEntrance(LINK_AGE_CHILD) == childTarget->anchor);
    assert(arrival == childTarget);
    std::cout << "PASS: save-to-spawn resolves the explicitly selected age without stale room state.\n";

    resetFile();
    RunLoadSpawnHook();
    assert(!slotMapLoaded && pendingSpawnAge == LINK_AGE_CHILD);
    assert(gSaveContext.entranceIndex == 187 && !suppressTransitionChecks);
    assert(!ServicePendingSpawn(true));
    assert(Apply(settings));
    assert(gSaveContext.entranceIndex == 187 && pendingSpawnAge == LINK_AGE_CHILD);
    assert(!ServicePendingSpawn(false)); // fade/dialog/cutscene safety boundary
    play.state.running = false;
    assert(!ServicePendingSpawn(true));
    play.state.running = true;
    play.transitionTrigger = TRANS_TRIGGER_START;
    assert(!ServicePendingSpawn(true));
    play.transitionTrigger = TRANS_TRIGGER_OFF;
    gSaveContext.health = 0;
    assert(!ServicePendingSpawn(true));
    gSaveContext.health = 48;
    assert(ServicePendingSpawn(true));
    assert(play.nextEntranceIndex == childTarget->anchor && gSaveContext.entranceIndex == 187);
    assert(pendingSpawnAge == -1 && arrival == childTarget && suppressTransitionChecks);
    SceneInit(6);
    ArchipelagoClient client;
    client.CaptureSceneTransition();
    client.CompleteSceneTransition(6);
    assert(client.reports.empty());
    for (int reconnect = 0; reconnect < 3; ++reconnect) {
        assert(Apply(settings));
        assert(!ServicePendingSpawn(true) && play.transitionTrigger == TRANS_TRIGGER_OFF);
    }
    std::cout << "PASS: late verified map completes one safe load warp, reports no traversal, and never rewarps on reconnect.\n";

    resetFile();
    RunLoadSpawnHook();
    assert(GetAgeSpawnEntrance(LINK_AGE_ADULT) == 642);
    assert(pendingSpawnAge == LINK_AGE_ADULT);
    assert(Apply(settings));
    play.state.running = false;
    assert(!ServicePendingSpawn(true) && pendingSpawnAge == LINK_AGE_ADULT);
    child = false; // Player_Destroy commits the requested age before new Play_Init.
    play.state.running = true;
    assert(ServicePendingSpawn(true) && play.nextEntranceIndex == 130 && !arrival);
    std::cout << "PASS: deferred explicit-age request survives the old scene's teardown.\n";

    resetFile();
    assert(Apply({{"EntranceRandomizerRevision",0}}));
    assert(slotMapLoaded && !routing.Active());
    RunLoadSpawnHook();
    assert(pendingSpawnAge == -1 && !suppressTransitionChecks);
    assert(gSaveContext.entranceIndex == 187 && !ServicePendingSpawn(true));
    // An unresolved load that receives a verified disabled map is consumed too.
    resetFile(); RunLoadSpawnHook();
    assert(Apply({{"EntranceRandomizerRevision",0}}));
    assert(!ServicePendingSpawn(true) && pendingSpawnAge == -1 && !suppressTransitionChecks);
    assert(Apply(settings) && !ServicePendingSpawn(true));
    std::cout << "PASS: known disabled maps preserve native behavior and cannot arm later relocation.\n";

    resetFile(); RunLoadSpawnHook();
    Archipelago_CancelPendingEntranceSpawn(); // OnExitGame / new OnLoadGame
    assert(Apply(settings) && !ServicePendingSpawn(true));
    resetFile(); RunLoadSpawnHook();
    Reset(); // LoadSaveMetadata resets map ownership when the selected save changes.
    assert(Apply(settings) && !ServicePendingSpawn(true));
    resetFile(); RunLoadSpawnHook();
    auto invalid = settings; invalid["EntranceRandomizerRevision"] = 99;
    assert(!Apply(invalid) && !slotMapLoaded && pendingSpawnAge == LINK_AGE_CHILD);
    assert(Apply(settings) && ServicePendingSpawn(true));
    std::cout << "PASS: exit/save switch clear requests; rejected slot maps cannot consume or replace them.\n";

    resetFile();
    assert(Apply(settings));
    const auto routesBefore = routing.Routes();
    const int initBefore = entranceInitializations;
    grottoId = 5; lastEntranceType = GROTTO_LOAD;
    overridingNextEntrance = true; grottoEnteredViaDoorAna = true;
    grottoExitList[5] = 130;
    Archipelago_ResolveDoorArrival(8961, false);
    const auto* customArrivalBefore = arrival;
    Rando::Context::GetInstance()->GetOption(RSK_SHUFFLE_ENTRANCES).Set(0);
    assert(Apply(settings));
    assert(entranceInitializations == initBefore && routing.Routes() == routesBefore);
    assert(Rando::Context::GetInstance()->GetOption(RSK_SHUFFLE_ENTRANCES).value == 1);
    assert(grottoId == 5 && lastEntranceType == GROTTO_LOAD && overridingNextEntrance && grottoEnteredViaDoorAna);
    assert(grottoExitList[5] == 130 && arrival == customArrivalBefore);
    // A separate context reset must still restore the native arrays.
    overrides[0] = {};
    assert(Apply(settings) && entranceInitializations == initBefore + 1);
    assert(entranceOverrideTable[187] == 8961 && arrival == customArrivalBefore);
    const int rebuilt = entranceInitializations;
    gPlayState = nullptr;
    assert(Apply(settings) && entranceInitializations == rebuilt + 1);
    gPlayState = &play;
    std::cout << "PASS: duplicate live maps preserve real grotto state and custom arrival; reset/non-gameplay tables rebuild.\n";

    resetFile(); currentSaveIsAP = false;
    gSaveContext.cutsceneIndex = 0xFFF1;
    assert(!Archipelago_EntranceSavewarp() && !Archipelago_EntranceSavewarpForAge(LINK_AGE_ADULT));
    assert(pendingSpawnAge == -1 && !suppressTransitionChecks && gSaveContext.cutsceneIndex == 0xFFF1);
    isRandomizer = false;
    assert(GetAgeSpawnEntrance(LINK_AGE_CHILD) == 187);
    assert(GetAgeSpawnEntrance(LINK_AGE_ADULT) == 1524);
    isRandomizer = true;
    entranceOverrideTable[187] = 1119;
    assert(GetAgeSpawnEntrance(LINK_AGE_CHILD) == 1119);
    assert(pendingSpawnAge == -1 && !ServicePendingSpawn(true));
    std::cout << "PASS: ordinary native randomizer and non-randomizer saves keep their existing spawn paths.\n";
}
'''


def between(text, start, end):
    begin = text.index(start)
    return text[begin:text.index(end, begin)]


def main():
    root = Path(__file__).resolve().parents[2]
    compiler = shutil.which("g++") or shutil.which("c++")
    if not compiler:
        raise SystemExit("A C++20 compiler is required.")
    read = lambda name: (root / name).read_text(encoding="utf-8-sig")
    client = read("soh/Network/Archipelago/ArchipelagoClient.cpp")
    native = read("soh/Enhancements/randomizer/randomizer_entrance.c")
    grotto = read("soh/Enhancements/randomizer/randomizer_grotto.c")
    menu = read("soh/Enhancements/QoL/BetterSaveMenu.cpp")
    hooks = read("soh/Enhancements/randomizer/hook_handlers.cpp")
    header = read("soh/Enhancements/randomizer/randomizer_entrance.h")
    types = read("soh/Enhancements/randomizer/randomizerTypes.h")
    grotto_header = read("soh/Enhancements/randomizer/randomizer_grotto.h")
    fixture = read("tools/tests/entrance_runtime_tests.cpp").split("void TestFullCatalog()", 1)[0]
    fixture = fixture.replace('#include "../../soh/', '#include "' + str(root / "soh") + '/')
    grotto_count = between(grotto, "static const GrottoLoadInfo", "static const GrottoReturnInfo").count(".entranceIndex =")
    grotto_state = between(grotto, "static s16 grottoExitList", "// SOH-EXTREME Shovel")
    grotto_constants = "\n".join(re.findall(r"^#define (?:ENTRANCE_GROTTO_(?:LOAD|EXIT)_START)\s+\S+", types, re.M))
    grotto_constants += "\n" + "\n".join(re.findall(r"^#define (?:NOT_GROTTO|GROTTO_LOAD|GROTTO_RETURN)\s+\S+", grotto_header, re.M))
    preinit = (f"using u8 = uint8_t; using s8 = int8_t;\n#define NUM_GROTTOS {grotto_count}\n" +
               grotto_constants + "\n" + grotto_state + '\n#include "captured_grotto_init.inc"\n')
    fixture = fixture.replace("int entranceInitializations = 0;", preinit + "\nint entranceInitializations = 0;")
    fixture = fixture.replace("void Entrance_Init() {\n", "void Entrance_Init() {\n    Grotto_InitExitAndLoadLists();\n", 1)
    gate = between(hooks, "        // Handle randomized spawn positions after the save context", "        onFlagSetHook =")
    # This ordering is the save/seed ownership boundary for late live data.
    update = between(client, "void ArchipelagoClient::Update()", "    if (activeLocationsPendingRefresh.exchange(false))")
    assert update.index("if (!currentSaveIsArchipelago || saveIdentityMismatch)") < update.index("ServicePendingSpawn(")
    assert "ServicePendingSpawn(SohExtreme::CanReceiveGameplayReward(gPlayState))" in update
    assert "Archipelago_CancelPendingEntranceSpawn();" in between(
        hooks, "void RandomizerOnExitGameHandler(", "void RandomizerOnKaleidoscopeUpdateHandler(")
    assert "SohExtreme::EntranceRuntime::Reset();" in between(
        client, "void ArchipelagoClient::LoadSaveMetadata(", "void ArchipelagoClient::BeginItemReplay(")
    with tempfile.TemporaryDirectory(prefix="soh-spawn-lifecycle-") as directory:
        work = Path(directory)
        for name in ("entrance.h", "randomizer_entrance.h", "randomizer_grotto.h"):
            stub = work / "soh/Enhancements/randomizer" / name
            stub.parent.mkdir(parents=True, exist_ok=True)
            stub.write_text("// Engine IO is supplied by the fixture.\n")
        captured = {
            "captured_entrance_capacity.h": re.search(r"^#define ENTRANCE_OVERRIDES_MAX_COUNT\s+\d+[^\r\n]*", header, re.M).group(0),
            "captured_overworld_endpoints.h": "// This focused fixture does not need the full-catalog test arrays.\n",
            "captured_scene_methods.inc": between(client, "void ArchipelagoClient::CaptureSceneTransition()", "void ArchipelagoClient::BeginDoorTransition("),
            "captured_native_scene_override.inc": between(native, "s16 Entrance_OverrideNextIndex(", "s16 Entrance_OverrideDynamicExit("),
            "captured_native_water_aliases.inc": between(native, "        // Override both land and water entrances", "\n    }\n\n    // Stop playing background music"),
            "captured_grotto_init.inc": between(grotto, "void Grotto_InitExitAndLoadLists(void)", "static bool Grotto_ShouldSetLastEntrance"),
            "captured_save_menu_spawn.inc": between(menu, "static int16_t GetAgeSpawnEntrance(", "bool IsSceneDungeon("),
            "captured_load_spawn_gate.inc": gate,
        }
        for name, contents in captured.items():
            (work / name).write_text(contents + "\n")
        cpp = work / "spawn_lifecycle.cpp"
        cpp.write_text(fixture + CASES)
        executable = work / "spawn_lifecycle"
        subprocess.run([compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(work),
                        str(cpp), "-o", str(executable)], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    main()
