"""Validate live Finder scene identity and automatic/manual section expansion.

Compiles actual production resolver/dropdown bodies and the unmodified drawing
loop, plus the full scene-grouping header. Game state, location-table reads and
ImGui are explicit I/O shims. Retained native tables ground scene IDs and shared
spawn meanings. This is not a native game build or a rendered UI playthrough.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from zipfile import ZipFile

from test_soul_object_blockers import SOURCE, function


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_dependencies(argument: Path | None) -> Path:
    candidates = [argument] if argument else [
        SOURCE.parent / "tests/entrance_184_native_dependencies",
        SOURCE / "validation/native_dependencies",
        SOURCE.parent / "validation/native_dependencies",
    ]
    for candidate in candidates:
        if candidate and (candidate / "scene_table.h").is_file() and (candidate / "entrance_table.h").is_file():
            return candidate
    raise RuntimeError("Pass --native-deps with the retained native scene_table.h and entrance_table.h.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--native-deps", type=Path)
    args = parser.parse_args()
    deps = native_dependencies(args.native_deps)
    rando = SOURCE / "soh/Enhancements/randomizer"
    ap = SOURCE / "soh/Network/Archipelago"
    paths = {
        "ui": rando / "randomizer_check_tracker.cpp",
        "groups": ap / "TrackerScenes.h",
        "snapshots": ap / "TrackerMirror.h",
        "version": SOURCE / "soh/SohExtremeVersion.h",
        "crossings": ap / "SceneTransitionChecks.h",
        "crossing_data": ap / "SceneTransitionData.inc",
        "overrides": ap / "FinderSceneOverrides.inc",
        "area_lookup": rando / "location.cpp",
        "locations": rando / "location_list.cpp",
        "names": SOURCE / "soh/util.cpp",
        "areas": rando / "randomizer_check_objects.cpp",
        "entrances": rando / "randomizer_entrance_tracker.cpp",
        "enums": rando / "randomizerEnums.h",
        "enum_list": rando / "randomizerEnumList.h",
        "scene_init": SOURCE / "src/code/z_scene.c",
        "room_init": SOURCE / "src/code/z_room.c",
        "fixture": Path(__file__).with_name("finder_autoexpand_native_tests.cpp.in"),
        "runner": Path(__file__),
        "extractor": Path(__file__).with_name("test_soul_object_blockers.py"),
    }
    paths.update({"enum_" + path.stem: path for path in (rando / "randomizerEnums").glob("*.h")})
    before = {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}
    dep_hashes = {name: digest(deps / name) for name in ("scene_table.h", "entrance_table.h")}
    ui = paths["ui"].read_text()
    draw = function(ui, "DrawUniversalFinderMirror")
    current = function(ui, "FinderCurrentScene")
    functions = {name: function(ui, name) for name in
                 ("FinderScene", "FinderCurrentScene", "FinderNativeScene", "DrawFinderDropdown")}
    functions["DrawFinderDropdown"] = "template <typename Key>\n" + functions["DrawFinderDropdown"]
    loop = draw[draw.index('    ImGui::Separator();\n    if (ImGui::BeginChild("SOHExtremeUTRegions"'):]
    assert loop.endswith("\n}")
    loop = loop[:-2]  # omit only the outer function's closing brace
    functions["DrawUniversalFinderMirror_presentation_loop"] = loop
    functions["Rando::TryGetAreaFromScene"] = function(paths["area_lookup"].read_text(), "Rando::TryGetAreaFromScene")
    assert "const auto current = FinderCurrentScene();" in draw
    assert "static std::map<std::pair<int, int>, bool> sceneDropdownChoices;" in draw
    assert "group->scene.Key()" in loop and 'ImGui::PushID("APScenes")' in loop
    assert "onlyCurrent && sceneMappingsReady" in draw
    assert 'TrackerDestinationLabel(row->id, row->name, arrival)' in loop
    assert 'ImGui::TextDisabled("%s", details.c_str())' in loop
    assert "GetCheckArea(" not in current and "gSaveContext" not in current and "snapshot" not in current
    assert "setupEntranceList[play->curSpawn].spawn" in paths["scene_init"].read_text()
    assert "setupEntranceList[play->curSpawn].room" in paths["room_init"].read_text()
    native_entrances = (deps / "entrance_table.h").read_text()
    assert re.search(r"DEFINE_ENTRANCE\(ENTR_WINDMILL_AND_DAMPES_GRAVE_GRAVE,\s*SCENE_WINDMILL_AND_DAMPES_GRAVE,\s*0,", native_entrances)
    assert re.search(r"DEFINE_ENTRANCE\(ENTR_WINDMILL_AND_DAMPES_GRAVE_WINDMILL,\s*SCENE_WINDMILL_AND_DAMPES_GRAVE,\s*1,", native_entrances)

    # The checked-in location table supplies the selected native lookup inputs;
    # FinderNativeScene itself consumes the real full override table at runtime.
    selected = ("RC_TOT_LEFTMOST_GOSSIP_STONE", "RC_TOT_LEFT_CENTER_GOSSIP_STONE",
                "RC_TOT_RIGHTMOST_GOSSIP_STONE", "RC_TOT_RIGHT_CENTER_GOSSIP_STONE",
                "RC_KAK_BAZAAR_ITEM_1", "RC_MARKET_BAZAAR_ITEM_1", "RC_KAK_WINDMILL_FREESTANDING_POH")
    locations = paths["locations"].read_text()
    metadata = []
    for name in selected:
        line = next(line for line in locations.splitlines() if f"locationTable[{name}] =" in line)
        scene = re.search(r"\bSCENE_[A-Z0-9_]+\b", line)[0]
        area = re.search(r"\bRCAREA_[A-Z0-9_]+\b", line)
        metadata.append(f"{{ {name}, {{ {scene}, {area[0] if area else 'Rando::TryGetAreaFromScene(' + scene + ')'} }} }},")
    entrance_text = paths["entrances"].read_text()
    shared_inputs = []
    # The production tracker rows explicitly identify all ten shared spawn pairs.
    for scene in ("SCENE_BAZAAR", "SCENE_SHOOTING_GALLERY", "SCENE_GREAT_FAIRYS_FOUNTAIN_MAGIC", "SCENE_GREAT_FAIRYS_FOUNTAIN_SPELLS"):
        rows = [line for line in entrance_text.splitlines() if re.search(r"\{\{\s*" + scene + r",\s*0x", line)]
        for line in rows:
            spawn = int(re.search(scene + r",\s*(0x[0-9A-Fa-f]+)", line)[1], 16)
            groups = re.findall(r"\bENTRANCE_GROUP_[A-Z0-9_]+\b", line)
            group_to_area = {"KAKARIKO": "KAKARIKO_VILLAGE", "MARKET": "MARKET", "DEATH_MOUNTAIN_TRAIL": "DEATH_MOUNTAIN_TRAIL",
                             "DEATH_MOUNTAIN_CRATER": "DEATH_MOUNTAIN_CRATER", "HYRULE_CASTLE": "HYRULE_CASTLE",
                             "ZORAS_FOUNTAIN": "ZORAS_FOUNTAIN", "DESERT_COLOSSUS": "DESERT_COLOSSUS"}
            area = "RCAREA_" + group_to_area[groups[0].removeprefix("ENTRANCE_GROUP_")]
            shared_inputs.append(f"{{ {scene}, {spawn}, {area} }},")
    assert len(shared_inputs) == 10
    with ZipFile(args.baseline) as archive:
        old_ui = archive.read("soh/Enhancements/randomizer/randomizer_check_tracker.cpp").decode().replace("\r\n", "\n")
    old_draw = function(old_ui, "DrawUniversalFinderMirror")
    old_current = old_draw[old_draw.index("    const int scene = gPlayState"):old_draw.index("    if (current.scene >= 0)")]
    baseline_functions = {name: function(old_ui, name) for name in ("FinderScene", "FinderNativeScene")}
    baseline_functions["current_binding"] = old_current
    baseline_code = "namespace Legacy {\n" + "\n".join(baseline_functions[name] for name in ("FinderScene", "FinderNativeScene"))
    baseline_code += "\nstatic SohExtreme::TrackerScene Current() {\n" + old_current + "    return current;\n}\n}\n"
    parts = {
        **functions,
        "SCENE_NAMES": re.search(r"std::vector<std::string> sceneNames = \{.*?\n\};", paths["names"].read_text(), re.S)[0],
        "AREA_NAMES": re.search(r"std::map<RandomizerCheckArea, std::string> rcAreaNames = \{.*?\n\};", paths["areas"].read_text(), re.S)[0],
        "AREA_GROUPS": re.search(r"RandomizerCheckArea AreaFromEntranceGroup\[\] = \{.*?\n\};", ui, re.S)[0],
        "LOCATION_INPUTS": "\n".join(metadata),
        "SHARED_INPUTS": "\n".join(shared_inputs),
        "LEGACY": baseline_code,
    }
    fixture = paths["fixture"].read_text()
    for token, value in parts.items():
        fixture = fixture.replace("@" + token + "@", value)
    assert not re.search(r"@[A-Za-z_:]+@", fixture)
    with tempfile.TemporaryDirectory(prefix="soh-finder-autoexpand-") as temporary:
        build = Path(temporary)
        cpp = build / "finder.cpp"
        cpp.write_text(fixture)
        command = ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(SOURCE), "-I", str(deps),
                   "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g", "-O1", str(cpp), "-o", str(build / "finder")]
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        environment = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:halt_on_error=1", UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
        result = subprocess.run([str(build / "finder")], text=True, capture_output=True, env=environment)
        print(result.stdout, end="")
        if result.returncode:
            raise RuntimeError(result.stderr or f"Finder tests failed: {result.returncode}")
        match = re.search(r"RESULT cases=(\d+) assertions=(\d+) baseline_reproductions=(\d+)", result.stdout)
        assert match
    after = {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}
    assert after == before, "Source changed during validation; rerun after edits settle."
    assert dep_hashes == {name: digest(deps / name) for name in dep_hashes}
    report = {
        "status": "passed", "cases": int(match[1]), "assertions": int(match[2]),
        "sanitizers": ["AddressSanitizer", "UndefinedBehaviorSanitizer"],
        "source_unchanged_during_tests": True,
        "scope": "Actual FinderScene/FinderCurrentScene/FinderNativeScene/DrawFinderDropdown function bodies and the unmodified final presentation loop of DrawUniversalFinderMirror; full production TrackerScenes/SceneTransitionChecks headers and Finder override table. Actual native area lookup and authored scene/region names are compiled. Engine PlayState, selected location-table reads, native grotto identity/entrance metadata and ImGui drawing/input use explicit I/O shims. The ten shared-spawn inputs come from the native entrance tracker. Not a full native game build, core ImGui integration test, rendered UI, ROM geometry or controller playthrough. Finder reachability, AP item rules, IDs and the wire format are unchanged.",
        "output": result.stdout.splitlines(), "sources": after, "native_dependencies": dep_hashes,
        "tested_function_sha256": {name: hashlib.sha256(value.encode()).hexdigest() for name, value in functions.items()},
        "baseline": {"archive": args.baseline.name, "sha256": digest(args.baseline), "reproductions": int(match[3]),
                     "tested_function_sha256": {name: hashlib.sha256(value.encode()).hexdigest() for name, value in baseline_functions.items()},
                     "scope": "Untouched 1.8.11 FinderScene/FinderNativeScene and exact live current binding reproduce missed night/ruins ToT groups and the stale saved-area Dampe-to-Windmill mismatch."},
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
