"""Exercise real exported slot JSON through the native entrance implementation.

Usage: python test_entrance_slot_bridge.py --dependencies PATH --report PATH
       child_cvars.json adult_cvars.json

The dependency directory contains nlohmann/json.hpp and public Shipwright enum
headers. No network access or native game build is performed by this runner.
The C++ fixture isolates engine IO, but compiles the complete production native
Entrance_Init, lookup, grotto resolution, savewarp, JSON parser and AP runtime,
along with the player door dispatch and native shutter side/distance checks.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile


def between(text, start, end):
    begin = text.index(start)
    return text[begin:text.index(end, begin)]


def enum_containing(text, marker):
    middle = text.index(marker)
    start = text.rindex("typedef enum {", 0, middle)
    end = text.index(";", middle) + 1
    return text[start:end]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("fixtures", type=Path, nargs="+")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    compiler = shutil.which("g++") or shutil.which("c++")
    if not compiler:
        raise SystemExit("A C++20 compiler is required.")
    required = ("json.hpp", "entrance_table.h", "scene_table.h", "z64.h", "z64save.h")
    for name in required:
        if not (args.dependencies / name).is_file():
            raise SystemExit(f"Missing public test dependency: {args.dependencies / name}")
    source_names = (
        "soh/Network/Archipelago/ArchipelagoClient.cpp",
        "soh/Network/Archipelago/EntranceRouting.h",
        "soh/Network/Archipelago/EntranceRuntime.inc",
        "soh/Network/Archipelago/EntranceRandomizerData.inc",
        "soh/Enhancements/randomizer/randomizer_entrance.c",
        "soh/Enhancements/randomizer/randomizer_entrance.h",
        "soh/Enhancements/randomizer/randomizer_grotto.c",
        "soh/Enhancements/randomizer/randomizer_grotto.h",
        "soh/Enhancements/randomizer/randomizerTypes.h",
        "soh/Enhancements/randomizer/settings.cpp",
        "soh/Enhancements/randomizer/hook_handlers.cpp",
        "soh/Enhancements/QoL/BetterSaveMenu.cpp",
        "archipelago/soh_extreme/EntranceCatalog.json",
        "src/overlays/actors/ovl_player_actor/z_player.c",
        "src/overlays/actors/ovl_Door_Shutter/z_door_shutter.c",
        "soh/Network/Archipelago/SceneTransitionChecks.h",
        "soh/Network/Archipelago/SceneTransitionData.inc",
        "src/code/z_actor.c",
        "soh/Network/Archipelago/EntranceDestinationPolicy.h",
        "soh/Network/Archipelago/EntranceDestinationData.inc",
        "soh/Network/Archipelago/ArchipelagoC.h",
        "archipelago/soh_extreme/EntranceDestinationPolicy.json",
    )
    before = {name: digest(root / name) for name in source_names}
    test_names = ("tools/tests/test_entrance_slot_bridge.py", "tools/tests/entrance_slot_bridge_tests.cpp")
    test_before = {name: digest(root / name) for name in test_names}
    read = lambda name: (root / name).read_text(encoding="utf-8-sig")
    client, native, header, grotto, grotto_header, types, settings, hooks, menu = (
        read(name) for name in (
            source_names[0], source_names[4], source_names[5], source_names[6],
            source_names[7], source_names[8], source_names[9], source_names[10], source_names[11]
        )
    )
    engine = (args.dependencies / "z64.h").read_text()
    save = (args.dependencies / "z64save.h").read_text()
    catalog = json.loads(read("archipelago/soh_extreme/EntranceCatalog.json"))
    player_source = read(source_names[13])
    shutter_source = read(source_names[14])
    actor_source = read(source_names[17])
    native_cvars = re.findall(
        r'^\s*OPT_(?:BOOL|U8)\((RSK_\w+),[^\n]*?CVAR_RANDOMIZER_SETTING\("([^"]+)"\)',
        settings, re.MULTILINE,
    )
    assert native_cvars and len(native_cvars) == len({key for key, _ in native_cvars})
    with tempfile.TemporaryDirectory(prefix="soh-slot-bridge-") as directory:
        work = Path(directory)
        for name in ("entrance.h", "randomizer_entrance.h", "randomizer_grotto.h"):
            stub = work / "soh/Enhancements/randomizer" / name
            stub.parent.mkdir(parents=True, exist_ok=True)
            stub.write_text("// Engine declarations are isolated by the regression fixture.\n")
        native_constants = "\n".join(re.findall(
            r'^#define (?:ENTRANCE_TABLE_SIZE|ENTRANCE_OVERRIDES_MAX_COUNT|SHUFFLEABLE_BOSS_COUNT)\s+[^\r\n]+',
            header, re.MULTILINE,
        ))
        native_constants += "\n" + between(header, "#define ENTRANCE_INFO_FIELD", "typedef struct")
        native_constants += "\n" + "\n".join(re.findall(
            r'^#define ENTRANCE_GROTTO_(?:LOAD|EXIT)_START\s+\S+', types, re.MULTILINE,
        ))
        native_constants += "\n" + "\n".join(re.findall(
            r'^#define (?:NOT_GROTTO|GROTTO_LOAD|GROTTO_RETURN)\s+\S+', grotto_header, re.MULTILINE,
        ))
        native_constants += "\n#define NUM_GROTTOS " + str(
            between(grotto, "static const GrottoLoadInfo", "static const GrottoReturnInfo").count(".entranceIndex =")
        ) + "\n"
        engine_constants = "\n".join(enum_containing(engine, marker) for marker in (
            "TRANS_TYPE_WIPE,", "TCA_NORMAL,", "TCC_BLACK,", "TCS_FAST",
        ))
        engine_constants += "\n" + re.search(r'^#define TRANS_TYPE_CIRCLE[^\r\n]+', engine, re.MULTILINE).group(0)
        engine_constants += "\n" + "\n".join(re.findall(
            r'^#define ENTRANCE_INFO_(?:CONTINUE_BGM_FLAG|DISPLAY_TITLE_CARD_FLAG|END_TRANS_TYPE_(?:MASK|SHIFT)|START_TRANS_TYPE_(?:MASK|SHIFT))[^\r\n]+',
            engine, re.MULTILINE,
        ))
        engine_constants += "\n" + enum_containing(save, "RESPAWN_MODE_DOWN,")
        engine_constants += "\n" + enum_containing(save, "LINK_AGE_ADULT,")
        native_struct = between(header, "typedef struct {", "#ifdef __cplusplus")
        grotto_structs = between(grotto_header, "typedef struct {", "#ifdef __cplusplus")
        captures = {
            "captured_engine_constants.h": engine_constants,
            "captured_native_constants.h": native_constants,
            "captured_native_structs.h": native_struct + "\n" + grotto_structs,
            "captured_native_init.inc": between(native, "// Overwrite the dynamic exit", "s16 Entrance_PeekNextIndexOverride("),
            "captured_grotto_data.inc": between(grotto, "// Information necessary for entering each grotto", "// SOH-EXTREME Shovel semantics."),
            "captured_grotto_functions.inc": between(grotto, "void Grotto_InitExitAndLoadLists(void)", "// Override the entrance index when entering into a grotto actor"),
            "captured_native_lookup.inc": between(native, "s16 Entrance_PeekNextIndexOverride(", "u32 Entrance_SceneAndSpawnAre("),
            "captured_native_savewarp.inc": between(native, "void Entrance_SetSavewarpEntrance(void)", "void Entrance_SetWarpSongEntrance(void)"),
            "captured_load_spawn_gate.inc": between(hooks, "        // Handle randomized spawn positions after the save context", "        onFlagSetHook ="),
            "captured_save_menu_spawn.inc": between(menu, "static int16_t GetAgeSpawnEntrance(", "bool IsSceneDungeon("),
            "captured_slot_parser.inc": between(client, "static bool ParseFlatStringIntObject(const std::string& raw, std::unordered_map<std::string, int64_t>& out) {", "static void RefreshArchipelagoRandomizerHooks()"),
            "captured_client_crossings.inc": between(client, "void ArchipelagoClient::ReportTransition(", "void ArchipelagoClient::SendLocation("),
            # The C player implementation names its Player* 'this'. Rename only
            # that identifier when compiling the unchanged dispatch block as C++.
            "captured_player_door_dispatch.inc": re.sub(r'\bthis\b', 'playerActor', between(
                player_source,
                "            if ((this->doorType != PLAYER_DOORTYPE_FAKE) && (doorActor->category == ACTORCAT_DOOR)) {",
                "            doorActor->room = play->roomCtx.curRoom.num;")),
            "captured_shutter_side.inc": re.sub(r'\bthis\b', 'shutterActor', between(
                shutter_source, "f32 DoorShutter_GetPlayerDistance(", "void DoorShutter_WaitClear(")),
            "captured_actor_coordinates.inc": between(actor_source, "void Actor_WorldToActorCoords(", "f32 Actor_HeightDiff("),
            "captured_native_cvars.inc": "\n".join(f'{{{key}, "{cvar}"}},' for key, cvar in native_cvars),
            "captured_overworld_ids.inc": ",".join(str(row["id"]) for row in catalog if row["category"] == "overworld"),
            "captured_door_actors.inc": "\n".join(
                f'{{{row["id"]}, {row["actor"]}, {row["params"]}}},'
                for row in sorted((row for row in catalog if row["door"] >= 0),
                                  key=lambda row: (row["id"] != 8456, row["id"]))),
        }
        for name, value in captures.items():
            (work / name).write_text(value + "\n")
        executable = work / "entrance_slot_bridge"
        command = [compiler, "-std=c++20", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                   "-Wno-missing-field-initializers", "-Wno-unused-variable", "-Wno-narrowing",
                   "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-I", str(work),
                   "-I", str(args.dependencies.resolve()), "-I", str(root),
                   str(Path(__file__).with_name("entrance_slot_bridge_tests.cpp")), "-o", str(executable)]
        subprocess.run(command, check=True)
        test_env = dict(os.environ)
        # This managed environment cannot enumerate /proc/<pid>/task for LSan.
        # Address/undefined checks stay enabled; leak scanning is outside scope.
        test_env["ASAN_OPTIONS"] = "detect_leaks=0"
        test_env["UBSAN_OPTIONS"] = "halt_on_error=1:print_stacktrace=1"
        result = subprocess.run([str(executable), *(str(path.resolve()) for path in args.fixtures)],
                                text=True, capture_output=True, env=test_env)
        if result.returncode:
            print(result.stdout)
            print(result.stderr)
            raise SystemExit(result.returncode)
        cases = json.loads(result.stdout)
    after = {name: digest(root / name) for name in source_names}
    if before != after or test_before != {name: digest(root / name) for name in test_names}:
        raise SystemExit("Source changed during bridge verification; rerun after the edit is complete.")
    report = {
        "status": "passed", "cases": cases,
        "coverage": ["production JSON parser", "719-route exported maps", "complete native Entrance_Init",
                     "native scene and dynamic-exit lookup", "native grotto load/return resolution",
                     "cached and late child/adult spawn", "save-menu age spawn", "paired return endpoints",
                     "native player door dispatch", "all 421 catalog door directions",
                     "native-accepted near-plane shutter openings", "local carrier-door checks",
                     "death/cancel/open-only/partial-crossing rejection", "wrong-arrival rejection",
                     "inconsistent-map rejection", "legacy all-off preservation"],
        "engine_io_isolated": True, "native_windows_build": False, "in_game_playthrough": False,
        "sanitizers": ["address", "undefined"], "leak_scanner": False, "source_sha256": before,
        "test_sha256": test_before,
        "fixture_sha256": {str(path): digest(path) for path in args.fixtures},
        "dependency_sha256": {name: digest(args.dependencies / name) for name in required},
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "passed", "report": str(args.report), "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
