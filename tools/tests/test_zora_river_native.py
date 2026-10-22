"""Compile the native HF/Zora's River routing and crossing-credit implementation.

Uses complete production Entrance_Init and lookup bodies, the actual AP
Record/Complete methods, and the source catalog/policy/crossing headers.
Game state, discovery persistence, and non-native grotto IO are isolated.
No scene geometry, game rendering, or Windows game executable is emulated.
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
import zipfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def between(text, start, end):
    first = text.index(start)
    return text[first:text.index(end, first)]


def enum_containing(text, marker):
    middle = text.index(marker)
    first = text.rindex("typedef enum {", 0, middle)
    return text[first:text.index(";", middle) + 1]


def struct_named(text, name):
    last = text.index("} " + name + ";") + len("} " + name + ";")
    first = text.rindex("typedef struct {", 0, last)
    return text[first:last]


def function(text, signature):
    """Extract an unmodified function, respecting C/C++ strings and comments."""
    first = text.index(signature)
    opening = text.index("{", first)
    cursor, depth, state = opening, 0, "code"
    while cursor < len(text):
        char = text[cursor]
        pair = text[cursor:cursor + 2]
        if state == "line":
            if char == "\n":
                state = "code"
        elif state == "comment":
            if pair == "*/":
                state = "code"
                cursor += 1
        elif state in ("'", '"'):
            if char == "\\":
                cursor += 1
            elif char == state:
                state = "code"
        elif pair in ("//", "/*"):
            state = "line" if pair == "//" else "comment"
            cursor += 1
        elif char in ("'", '"'):
            state = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[first:cursor + 1]
        cursor += 1
    raise ValueError("Unclosed function: " + signature)


def archive_read(archive, relative):
    matches = [name for name in archive.namelist()
               if name == relative or name.endswith("/" + relative)]
    if len(matches) != 1:
        raise ValueError(f"Expected one baseline member for {relative}: {matches}")
    return archive.read(matches[0])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    compiler = shutil.which("g++") or shutil.which("c++")
    if not compiler:
        raise SystemExit("A C++20 compiler is required.")
    dependencies = ("entrance_table.h", "scene_table.h", "z64.h", "z64scene.h")
    for name in dependencies:
        if not (args.dependencies / name).is_file():
            raise SystemExit(f"Missing retained native dependency: {name}")
    source_names = (
        "soh/Network/Archipelago/EntranceRuntime.inc",
        "soh/Network/Archipelago/EntranceRouting.h",
        "soh/Network/Archipelago/EntranceRandomizerData.inc",
        "soh/Network/Archipelago/EntranceDestinationPolicy.h",
        "soh/Network/Archipelago/EntranceDestinationData.inc",
        "soh/Network/Archipelago/SceneTransitionChecks.h",
        "soh/Network/Archipelago/SceneTransitionData.inc",
        "soh/Enhancements/randomizer/randomizer_entrance.c",
        "soh/Enhancements/randomizer/randomizer_entrance.h",
        "soh/Enhancements/randomizer/randomizer_entrance_tracker.cpp",
        "soh/Enhancements/randomizer/randomizerTypes.h",
        "soh/Enhancements/randomizer/randomizer_grotto.c",
        "soh/Enhancements/randomizer/randomizerEnums/RandomizerSettingKey.h",
        "soh/Enhancements/randomizer/randomizerEnums/RandomizerOptions.h",
        "archipelago/soh_extreme/EntranceCatalog.json",
        "archipelago/soh_extreme/EntranceDestinationPolicy.json",
    )
    test_names = ("tools/tests/test_zora_river_native.py",
                  "tools/tests/zora_river_native_tests.cpp.in")
    before = {name: digest(root / name) for name in source_names}
    tests_before = {name: digest(root / name) for name in test_names}
    dependency_before = {name: digest(args.dependencies / name) for name in dependencies}
    read = lambda name: (root / name).read_text(encoding="utf-8-sig")
    runtime = read(source_names[0])
    native = read("soh/Enhancements/randomizer/randomizer_entrance.c")
    header = read("soh/Enhancements/randomizer/randomizer_entrance.h")
    tracker = read("soh/Enhancements/randomizer/randomizer_entrance_tracker.cpp")
    types = read("soh/Enhancements/randomizer/randomizerTypes.h")
    grotto = read("soh/Enhancements/randomizer/randomizer_grotto.c")
    engine = (args.dependencies / "z64.h").read_text()
    native_scene = (args.dependencies / "z64scene.h").read_text()
    catalog = json.loads(read("archipelago/soh_extreme/EntranceCatalog.json"))
    river_ids = (234, 385, 473, 785)
    river_rows = [row for row in catalog if row["id"] in river_ids]
    if len(river_rows) != 4 or {row["id"] for row in river_rows} != set(river_ids):
        raise SystemExit("The production catalog must contain all four river endpoints.")

    constants = "\n".join(re.findall(
        r"^#define (?:ENTRANCE_TABLE_SIZE|ENTRANCE_OVERRIDES_MAX_COUNT|SHUFFLEABLE_BOSS_COUNT)\s+[^\r\n]+",
        header, re.M))
    constants += "\n" + between(header, "#define ENTRANCE_INFO_FIELD", "typedef struct")
    constants += "\n" + "\n".join(re.findall(
        r"^#define ENTRANCE_GROTTO_(?:LOAD|EXIT)_START\s+\S+", types, re.M))
    constants += "\n#define NUM_GROTTOS " + str(
        between(grotto, "static const GrottoLoadInfo", "static const GrottoReturnInfo")
        .count(".entranceIndex ="))
    engine_constants = "\n".join(enum_containing(engine, marker) for marker in
                                  ("TRANS_TYPE_WIPE,", "TCA_NORMAL,", "TCC_BLACK,", "TCS_FAST"))
    engine_constants += "\n" + re.search(r"^#define TRANS_TYPE_CIRCLE[^\r\n]+", engine, re.M).group(0)
    engine_constants += "\n" + "\n".join(re.findall(
        r"^#define ENTRANCE_INFO_(?:CONTINUE_BGM_FLAG|DISPLAY_TITLE_CARD_FLAG|END_TRANS_TYPE_(?:MASK|SHIFT)|START_TRANS_TYPE_(?:MASK|SHIFT))[^\r\n]+",
        engine, re.M))

    captures = {
        "captured_native_constants.h": constants,
        "captured_engine_constants.h": engine_constants,
        "captured_scene_aliases.h": re.search(r"^#define SCENE_UNUSED_6E[^\r\n]+", native_scene, re.M).group(0),
        "captured_native_structs.h": "\n".join((struct_named(engine, "ActorEntry"),
                                                   struct_named(engine, "EntranceInfo"),
                                                   struct_named(header, "EntranceOverride"))),
        "captured_native_init.inc": between(native, "// Overwrite the dynamic exit", "s16 Entrance_PeekNextIndexOverride("),
        "captured_native_override.inc": function(native, "s16 Entrance_OverrideNextIndex("),
        "captured_discovery.inc": function(tracker, "bool IsEntranceDiscovered("),
        "captured_runtime_state.inc": between(runtime, "EntranceRouting routing;", "// Runtime checkpoints") + "\n" +
            between(runtime, "struct PendingArrival {", "void CancelTransition("),
        "captured_runtime_methods.inc": "\n".join(function(runtime, signature) for signature in
            ("uint8_t CurrentArrivalAge()", "void ArmArrival(", "int ResolvedArrival(",
             "bool ArrivalTableMatches(", "void Record(", "int64_t Complete(")),
        "captured_runtime_exports.inc": "\n".join(function(runtime, signature) for signature in
            ('extern "C" bool Archipelago_EntranceShuffleActive(',
             'extern "C" void Archipelago_RecordEntrance(',
             'extern "C" int Archipelago_ResolvedEntranceArrival(')),
        "captured_catalog.inc": "\n".join(
            "{" + ",".join(str(row[key]) for key in
                           ("id", "reverse", "scene", "source_scene", "check_id")) + "},"
            for row in river_rows),
    }
    # An actual installation must finish all direct writes before legacy alias
    # fallback. The complete initializer is also executed for every permutation.
    native_init = function(native, "void Entrance_Init(")
    direct_write = native_init.index("entranceOverrideTable[originalIndex] = overrideIndex;")
    legacy_call = native_init.index("Entrance_ApplyLegacyRiverOverrides(entranceOverrides);")
    if legacy_call < direct_write:
        raise SystemExit("Legacy river aliases must follow direct table installation.")
    if "Entrance_ApplyLegacyRiverOverrides" not in captures["captured_native_init.inc"]:
        raise SystemExit("The full native initializer capture omitted its legacy alias helper.")

    baseline = None
    if args.baseline:
        with zipfile.ZipFile(args.baseline) as archive:
            raw_native = archive_read(archive, "soh/Enhancements/randomizer/randomizer_entrance.c")
            raw_tracker = archive_read(archive, "soh/Enhancements/randomizer/randomizer_entrance_tracker.cpp")
        old_native = raw_native.decode("utf-8-sig")
        old_tracker = raw_tracker.decode("utf-8-sig")
        captures["captured_baseline_init.inc"] = between(old_native, "// Overwrite the dynamic exit", "s16 Entrance_PeekNextIndexOverride(")
        captures["captured_baseline_override.inc"] = function(old_native, "s16 Entrance_OverrideNextIndex(")
        captures["captured_baseline_discovery.inc"] = function(old_tracker, "bool IsEntranceDiscovered(")
        baseline = {"archive": args.baseline.name, "sha256": digest(args.baseline),
                    "source_sha256": {
                        "soh/Enhancements/randomizer/randomizer_entrance.c": hashlib.sha256(raw_native).hexdigest(),
                        "soh/Enhancements/randomizer/randomizer_entrance_tracker.cpp": hashlib.sha256(raw_tracker).hexdigest()},
                    "note": "Previous shipped native bodies execute against the current catalog to isolate native aliasing regressions."}

    with tempfile.TemporaryDirectory(prefix="soh-zora-river-") as directory:
        work = Path(directory)
        for name, value in captures.items():
            (work / name).write_text(value + "\n")
        harness = work / "zora_river.cpp"
        harness.write_text(read(test_names[1]))
        executable = work / "zora_river"
        command = [compiler, "-std=c++20", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                   "-Wno-unused-variable", "-Wno-missing-field-initializers", "-Wno-unused-parameter",
                   "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-I", str(work),
                   "-I", str(args.dependencies.resolve()), "-I", str(root)]
        if baseline:
            command.append("-DTEST_BASELINE=1")
        subprocess.run(command + [str(harness), "-o", str(executable)], check=True)
        env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0", UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
        result = subprocess.run([str(executable)], capture_output=True, text=True, env=env)
        if result.returncode:
            print(result.stdout)
            print(result.stderr)
            raise SystemExit(result.returncode)
        results = json.loads(result.stdout)

    after = {name: digest(root / name) for name in source_names}
    if before != after or tests_before != {name: digest(root / name) for name in test_names}:
        raise SystemExit("Production or fixture sources changed during validation; rerun after edits settle.")
    if dependency_before != {name: digest(args.dependencies / name) for name in dependencies}:
        raise SystemExit("Retained native dependencies changed during validation.")
    if baseline:
        baseline["reproductions"] = results["baseline_reproductions"]
    report = {
        "status": "passed", **results, "source_sha256": after, "test_sha256": tests_before,
        "dependency_sha256": dependency_before,
        "captured_sha256": {name: hashlib.sha256(value.encode()).hexdigest() for name, value in captures.items()},
        "baseline": baseline, "source_unchanged_during_tests": True,
        "sanitizers": ["address", "undefined"], "leak_scanner": False,
        "native_windows_build": False, "in_game_playthrough": False,
        "coverage": [
            "Complete production Entrance_Init, table reset and native lookup bodies",
            "Actual AP EntranceRouting and endpoint/policy/crossing headers",
            "Actual AP Record, Complete, ArmArrival and ResolvedArrival functions",
            "Four distinct physical river endpoints, all four native age/time layers",
            "Distinct mapped destinations and coupled returns with source-only check credit",
            "All 24 orderings of four river override rows",
            "Explicit identity water paths preserve their native water spawn",
            "Legacy land-only maps retain their original route entries and effective native destinations",
            "Partial and absent legacy aliases, native-only aliases and exact AP discovery",
            "Independent river-path wire revision validation rejects incomplete or incompatible maps atomically",
            "Canceled, suppressed, dead, wrong-scene and repeated arrival credit guards",
        ],
        "limitations": [
            "Game-state reads, discovery persistence and departure-position capture are explicit IO shims.",
            "All exercised destinations are native entrance indices; grotto resolution is an identity IO shim that invokes the real AP resolution callback.",
            "Scene allocation, collision geometry, player swimming, actor updates, rendering and network transmission are not exercised.",
            "Baseline replay isolates previous native bodies against current endpoint metadata; it is not a previous executable or full game replay.",
        ],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "passed", "report": str(args.report),
                      "case_count": report["case_count"], "assertion_count": report["assertion_count"],
                      "baseline_reproductions": report["baseline_reproductions"]}, indent=2))


if __name__ == "__main__":
    main()
