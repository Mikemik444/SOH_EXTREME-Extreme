"""Run the real AP arrival guards, native resolvers and scene-condition boundary.

Usage: python test_entrance_destination_native_safety.py --dependencies PATH --report PATH

The dependencies are the same verified public enum/table headers used by
test_entrance_slot_bridge.py. Engine allocation, inventory/flag IO and scene
allocation are isolated; production routing, native table construction, grotto
resolution, ConditionalTriggers, fade layer selection, and the Play_Init
scene-selection block are extracted verbatim. This is not a game playthrough.
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

from test_entrance_slot_bridge import between, digest, enum_containing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
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
        "soh/Network/Archipelago/EntranceDestinationPolicy.h",
        "soh/Network/Archipelago/EntranceDestinationData.inc",
        "soh/Network/Archipelago/EntranceRouting.h",
        "soh/Network/Archipelago/EntranceRuntime.inc",
        "soh/Network/Archipelago/ArchipelagoC.h",
        "soh/Network/Archipelago/EntranceRandomizerData.inc",
        "soh/Network/Archipelago/SceneTransitionChecks.h",
        "soh/Network/Archipelago/SceneTransitionData.inc",
        "soh/Enhancements/randomizer/randomizer_entrance.c",
        "soh/Enhancements/randomizer/randomizer_entrance.h",
        "soh/Enhancements/randomizer/randomizer_grotto.c",
        "soh/Enhancements/randomizer/randomizer_grotto.h",
        "soh/Enhancements/randomizer/randomizerTypes.h",
        "src/code/z_play.c", "src/code/z_demo.c",
        "archipelago/soh_extreme/EntranceDestinationPolicy.json",
    )
    test_names = (
        "tools/tests/test_entrance_destination_native_safety.py",
        "tools/tests/entrance_destination_safety_tests.cpp",
        "tools/tests/test_entrance_slot_bridge.py",
        "tools/tests/entrance_slot_bridge_tests.cpp",
    )
    before = {name: digest(root / name) for name in source_names}
    test_before = {name: digest(root / name) for name in test_names}
    read = lambda name: (root / name).read_text(encoding="utf-8-sig")
    native = read("soh/Enhancements/randomizer/randomizer_entrance.c")
    header = read("soh/Enhancements/randomizer/randomizer_entrance.h")
    grotto = read("soh/Enhancements/randomizer/randomizer_grotto.c")
    grotto_header = read("soh/Enhancements/randomizer/randomizer_grotto.h")
    types = read("soh/Enhancements/randomizer/randomizerTypes.h")
    play_source = read("src/code/z_play.c")
    conditions = between(read("src/code/z_demo.c"), "void Cutscene_HandleConditionalTriggers(",
                         "void Cutscene_SetSegment(")
    engine = (args.dependencies / "z64.h").read_text()
    save = (args.dependencies / "z64save.h").read_text()
    native_constants = "\n".join(re.findall(
        r'^#define (?:ENTRANCE_TABLE_SIZE|ENTRANCE_OVERRIDES_MAX_COUNT|SHUFFLEABLE_BOSS_COUNT)\s+[^\r\n]+',
        header, re.MULTILINE))
    native_constants += "\n" + between(header, "#define ENTRANCE_INFO_FIELD", "typedef struct")
    native_constants += "\n" + "\n".join(re.findall(
        r'^#define ENTRANCE_GROTTO_(?:LOAD|EXIT)_START\s+\S+', types, re.MULTILINE))
    native_constants += "\n" + "\n".join(re.findall(
        r'^#define (?:NOT_GROTTO|GROTTO_LOAD|GROTTO_RETURN)\s+\S+', grotto_header, re.MULTILINE))
    native_constants += "\n#define NUM_GROTTOS " + str(between(
        grotto, "static const GrottoLoadInfo", "static const GrottoReturnInfo").count(".entranceIndex ="))
    engine_constants = "\n".join(enum_containing(engine, marker) for marker in (
        "TRANS_TYPE_WIPE,", "TCA_NORMAL,", "TCC_BLACK,", "TCS_FAST"))
    engine_constants += "\n" + re.search(r'^#define TRANS_TYPE_CIRCLE[^\r\n]+', engine, re.MULTILINE).group(0)
    engine_constants += "\n" + "\n".join(re.findall(
        r'^#define ENTRANCE_INFO_(?:CONTINUE_BGM_FLAG|DISPLAY_TITLE_CARD_FLAG|END_TRANS_TYPE_(?:MASK|SHIFT)|START_TRANS_TYPE_(?:MASK|SHIFT))[^\r\n]+',
        engine, re.MULTILINE))
    engine_constants += "\n" + enum_containing(save, "RESPAWN_MODE_DOWN,")
    engine_constants += "\n" + enum_containing(save, "LINK_AGE_ADULT,")
    engine_constants += "\n" + enum_containing(save, "SCENE_LAYER_CHILD_DAY,")
    event_flags = sorted(set(re.findall(r'\bEVENTCHKINF_\w+', conditions + play_source)))
    event_definitions = []
    for flag in event_flags:
        match = re.search(r'^#define ' + flag + r'\s+[^\r\n]+', save, re.MULTILINE)
        if match:
            event_definitions.append(match.group(0))
    engine_constants += "\n" + "\n".join(event_definitions)
    # Reuse the existing full-table bridge's engine IO declarations. Only add
    # SaveContext/PlayState fields used by the newly captured native boundaries.
    harness = read("tools/tests/entrance_slot_bridge_tests.cpp").split(
        '#include "captured_native_savewarp.inc"', 1)[0]
    harness = harness.replace("    int savedSceneNum = SCENE_TEMPLE_OF_TIME;",
        "    int savedSceneNum = SCENE_TEMPLE_OF_TIME;\n"
        "    int nextDayTime = 0xFFFF, dayTime = 0x8000, skyboxTime = 0, nightFlag = 0;\n"
        "    int nayrusLoveTimer = 0, sceneLayer = 0;")
    harness = harness.replace("    int sceneNum = SCENE_TEMPLE_OF_TIME;",
        "    int sceneNum = SCENE_TEMPLE_OF_TIME;\n"
        "    struct { int lastPlayedSong = 0; } msgCtx;")
    captures = {
        "captured_engine_constants.h": engine_constants,
        "captured_native_constants.h": native_constants,
        "captured_native_structs.h": between(header, "typedef struct {", "#ifdef __cplusplus") +
            "\n" + between(grotto_header, "typedef struct {", "#ifdef __cplusplus"),
        "captured_native_init.inc": between(native, "// Overwrite the dynamic exit", "s16 Entrance_PeekNextIndexOverride("),
        "captured_grotto_data.inc": between(grotto, "// Information necessary for entering each grotto", "// SOH-EXTREME Shovel semantics."),
        "captured_grotto_functions.inc": between(grotto, "void Grotto_InitExitAndLoadLists(void)", "// Override the entrance index when entering into a grotto actor"),
        "captured_grotto_actor.inc": between(grotto, "void Grotto_OverrideActorEntrance(", "// Set the respawn flag for when we want to return from a grotto entrance"),
        "captured_native_lookup.inc": between(native, "s16 Entrance_PeekNextIndexOverride(", "u32 Entrance_SceneAndSpawnAre("),
        "captured_warp_songs.inc": between(native, "void Entrance_SetWarpSongEntrance(", "// Check if Link should still be riding epona"),
        "captured_conditions.inc": conditions,
        "captured_play_boundary.inc": between(play_source, "    if (gSaveContext.nextCutsceneIndex != 0xFFEF)",
                                               '    osSyncPrintf("\\nSCENE_NO='),
        "captured_fade_layer.inc": between(play_source, "                        s16 sceneLayer = 0;",
                                            '                        // fade out bgm'),
        "captured_bridge_engine.inc": harness,
    }
    with tempfile.TemporaryDirectory(prefix="soh-destination-safety-") as directory:
        work = Path(directory)
        for name in ("entrance.h", "randomizer_entrance.h", "randomizer_grotto.h"):
            stub = work / "soh/Enhancements/randomizer" / name
            stub.parent.mkdir(parents=True, exist_ok=True)
            stub.write_text("// Engine declarations are isolated by the regression fixture.\n")
        for name, value in captures.items():
            (work / name).write_text(value + "\n")
        executable = work / "entrance_destination_safety"
        command = [compiler, "-std=c++20", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                   "-Wno-missing-field-initializers", "-Wno-unused-variable", "-Wno-narrowing",
                   "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-I", str(work),
                   "-I", str(args.dependencies.resolve()), "-I", str(root),
                   str(Path(__file__).with_name("entrance_destination_safety_tests.cpp")), "-o", str(executable)]
        subprocess.run(command, check=True)
        environment = dict(os.environ, ASAN_OPTIONS="detect_leaks=0",
                           UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
        result = subprocess.run([str(executable)], text=True, capture_output=True, env=environment)
        if result.returncode:
            print(result.stdout)
            print(result.stderr)
            raise SystemExit(result.returncode)
        cases = json.loads(result.stdout)
    if before != {name: digest(root / name) for name in source_names} or test_before != {
            name: digest(root / name) for name in test_names}:
        raise SystemExit("Source or fixture changed during validation; rerun after production freeze.")
    report = {
        "status": "passed", "cases": cases, "source_sha256": before, "test_sha256": test_before,
        "dependency_sha256": {name: digest(args.dependencies / name) for name in required},
        "captured_fragment_sha256": {name: hashlib.sha256(value.encode()).hexdigest()
                                     for name, value in captures.items()},
        "sanitizers": ["address", "undefined"], "leak_scanner": False,
        "engine_io_isolated": True, "native_windows_build": False, "in_game_playthrough": False,
        "limitations": "Verifies native table/resolver/scene-selection code and engine-I/O shims, not scene assets, actor collision, or a full game build.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "passed", "report": str(args.report), "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
