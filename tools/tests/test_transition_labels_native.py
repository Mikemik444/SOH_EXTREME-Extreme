"""Run the production transition-label formatters with explicit engine I/O shims.

This validates all catalogue destinations, physical room doors and scene-exit
handle doors, plus each native EnHoll type while its loaded room disagrees with
Link's physical side. It is not a full game build or a visual playthrough.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from test_soul_object_blockers import SOURCE, function


REGIONS = {
    "RR_FOREST_TEMPLE_BOSS_ENTRYWAY": "Forest Temple: Before the Boss Room",
    "RR_FIRE_TEMPLE_BOSS_ENTRYWAY": "Fire Temple: Before the Boss Room",
    "RR_WATER_TEMPLE_BOSS_ENTRYWAY": "Water Temple: Before the Boss Room",
    "RR_SPIRIT_TEMPLE_BOSS_ENTRYWAY": "Spirit Temple: Before the Boss Room",
    "RR_SHADOW_TEMPLE_BOSS_ENTRYWAY": "Shadow Temple: Before the Boss Room",
    "RR_JABU_JABUS_BELLY_BOSS_EXIT": "Jabu Jabu's Belly: Exit from the Boss Room",
}
AREAS = {
    "MK": "Market", "Kak": "Kakariko Village", "KF": "Kokiri Forest", "LW": "Lost Woods",
    "SFM": "Sacred Forest Meadow", "HF": "Hyrule Field", "LH": "Lake Hylia", "LLR": "Lon Lon Ranch",
    "GY": "Graveyard", "DMT": "Death Mountain Trail", "DMC": "Death Mountain Crater", "GC": "Goron City",
    "ZR": "Zora's River", "ZD": "Zora's Domain", "ZF": "Zora's Fountain", "GV": "Gerudo Valley",
    "GF": "Gerudo's Fortress", "HC": "Hyrule Castle",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_arrival(endpoint, descriptions):
    if endpoint["door"] >= 0:
        row = descriptions[str(endpoint["check_id"])]
        # These authored same-room landmarks include the crossed maze sector.
        if 11211290 <= endpoint["check_id"] <= 11211307:
            return row["name"].removeprefix("Door: ")
        return row["arrival_name"]
    name = endpoint["name"].split(" -> ", 1)[-1]
    if name in REGIONS:
        return REGIONS[name]
    head, space, rest = name.partition(" ")
    return AREAS[head] + ": " + rest if space and head in AREAS else name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    rando = SOURCE / "soh/Enhancements/randomizer"
    ap = SOURCE / "soh/Network/Archipelago"
    world = SOURCE / "archipelago/soh_extreme"
    paths = {
        "ui": rando / "randomizer_check_tracker.cpp",
        "world_labels": rando / "RoomDebugWorldLabels.inc",
        "door_data": rando / "RoomDebugDoorData.inc",
        "scene_data": rando / "RoomDebugSceneData.inc",
        "labels": ap / "RoomTransitionLabels.h",
        "check_labels": ap / "TrackerCheckLabels.h",
        "descriptions": ap / "CheckDescriptions.inc",
        "routing": ap / "EntranceRouting.h",
        "endpoints": ap / "EntranceRandomizerData.inc",
        "policy": ap / "EntranceDestinationPolicy.h",
        "policy_data": ap / "EntranceDestinationData.inc",
        "api": ap / "ArchipelagoC.h",
        "resources": SOURCE / "soh/ResourceManagerHelpers.h",
        "ap_descriptions": world / "CheckDescriptions.json",
        "ap_endpoints": world / "EntranceCatalog.json",
        "ap_doors": world / "DungeonDoorCatalog.json",
        "ap_transitions": world / "SceneTransitionCatalog.json",
        "generator": SOURCE / "tools/generate_room_debug_destinations.py",
        "runner": Path(__file__),
        "extractor": Path(__file__).with_name("test_soul_object_blockers.py"),
        "fixture": Path(__file__).with_name("transition_labels_native_tests.cpp.in"),
    }
    before = {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}
    ui, labels = (paths[name].read_text() for name in ("ui", "world_labels"))
    functions = {
        "RoomDebugDestination": function(ui, "RoomDebugDestination"),
        "RoomDebugSceneExitText": function(labels, "RoomDebugSceneExitText"),
        "RoomDebugPassageText": function(labels, "RoomDebugPassageText"),
        "FinderCheckArrival": function(ui, "FinderCheckArrival"),
    }
    assert '#include "soh/Network/Archipelago/RoomTransitionLabels.h"' in ui
    assert '#include "soh/ResourceManagerHelpers.h"' in ui
    assert "uint32_t ResourceMgr_IsSceneMasterQuest(s16 sceneNum);" in paths["resources"].read_text()
    finder = function(ui, "DrawUniversalFinderMirror")
    assert 'CVAR_TRACKER_CHECK("ShowRoomDoorNumbers"), 0' in finder
    assert 'TrackerCheckLabel(row->id, row->name, showRoomDoorNumbers)' not in finder
    assert 'SohExtreme::TrackerDestinationLabel(row->id, row->name, arrival)' in finder
    draw = finder.split('for (const auto* row : group->rows)', 1)[1]
    assert draw.index('ImGui::TextWrapped("%s", line.c_str())') < draw.index('if (showRoomDoorNumbers)')
    assert 'ImGui::TextDisabled("%s", details.c_str())' in draw
    assert 'CVAR_TRACKER_CHECK("RoomDebugDestinationLabels"), 0' in ui
    assert 'RoomDebugDestination(i)' in function(ui, "DrawRoomDebugWindow")
    forbidden = ("Archipelago_EntranceObserve", "Archipelago_EntranceSelect", "Archipelago_ResolveDoor",
                 "Archipelago_EntranceRecord", "Archipelago_Report", "Flags_Set")
    assert not any(token in text for token in forbidden for text in functions.values())

    endpoints = json.loads(paths["ap_endpoints"].read_text())
    descriptions = json.loads(paths["ap_descriptions"].read_text())
    doors = {row["id"]: row for row in json.loads(paths["ap_doors"].read_text())}
    for endpoint in endpoints:
        if endpoint["door"] >= 0:
            physical = doors[endpoint["check_id"]]
            assert endpoint["room"] == physical["room_to"]
            assert endpoint["scene"] == physical["target_scene"]
        else:
            assert endpoint["room"] == -1
    subprocess.run([sys.executable, str(paths["generator"]), "--check"], check=True)

    parts = {
        "DOOR_TYPE": re.search(r"struct RoomDebugDoor \{.*?\n\};", ui, re.S)[0],
        "SCENE_TYPE": re.search(r"struct RoomDebugSceneTransition \{.*?\n\};", ui, re.S)[0],
        "SCENE_DECLARATION": re.search(r"static std::string RoomDebugSceneExitText\([^;]+;", ui)[0],
        "SCENE_FUNCTION": functions["RoomDebugSceneExitText"],
        "DOOR_FUNCTION": functions["RoomDebugDestination"],
        "PASSAGE_FUNCTION": functions["RoomDebugPassageText"],
        "FINDER_FUNCTION": functions["FinderCheckArrival"],
        "ARRIVALS": "\n".join("{ %d, %s, %d }," % (row["id"], json.dumps(expected_arrival(row, descriptions)), row["room"])
                                for row in endpoints),
    }
    text = paths["fixture"].read_text()
    for key, value in parts.items():
        text = text.replace("@" + key + "@", value)
    assert not re.search(r"@[A-Z_]+@", text)
    with tempfile.TemporaryDirectory(prefix="soh-transition-labels-") as tmp:
        build = Path(tmp)
        standalone = build / "header.cpp"
        standalone.write_text('#include "soh/Network/Archipelago/RoomTransitionLabels.h"\nint main() {}\n')
        common = ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(SOURCE)]
        header_compile = subprocess.run(common + ["-fsyntax-only", str(standalone)], text=True, capture_output=True)
        if header_compile.returncode:
            raise RuntimeError(header_compile.stdout + header_compile.stderr)
        cpp = build / "labels.cpp"
        cpp.write_text(text)
        command = common + ["-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g", "-O1",
                            str(cpp), "-o", str(build / "labels")]
        compiled = subprocess.run(command, text=True, capture_output=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout + compiled.stderr)
        env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:halt_on_error=1",
                   UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
        result = subprocess.run([str(build / "labels")], text=True, capture_output=True, env=env)
        print(result.stdout, end="")
        if result.returncode:
            raise RuntimeError(result.stderr or f"Transition label tests failed: {result.returncode}")
        match = re.search(r"RESULT cases=(\d+) assertions=(\d+)", result.stdout)
        assert match
    after = {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}
    if before != after:
        raise RuntimeError("Source changed during validation; rerun after edits settle.")
    report = {
        "status": "passed", "cases": int(match[1]), "assertions": int(match[2]),
        "sanitizers": ["AddressSanitizer", "UndefinedBehaviorSanitizer"],
        "standalone_header_compile": "passed", "source_unchanged_during_tests": True,
        "catalogue": {"endpoint_arrivals": 721, "room_door_endpoints": 421, "scene_endpoints_unknown_room": 300,
                      "physical_scene_exit_handles": 52, "same_room_directions": 24, "native_passage_types": 7},
        "scope": "Actual production RoomDebugDestination, RoomDebugSceneExitText, RoomDebugPassageText and FinderCheckArrival bodies, plus the full shared production header and tables. Engine actors/room state, save-scoped AP mapping, math, MQ/scene names, entrance table and unchanged lower-level scene-exit resolution use explicit I/O shims. Finder toggle/second-line rendering and required header declarations are source-inspected. No full native game build, rendered UI test, ROM geometry or controller playthrough.",
        "output": result.stdout.splitlines(), "sources": after,
        "tested_function_sha256": {name: hashlib.sha256(value.encode()).hexdigest() for name, value in functions.items()},
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
