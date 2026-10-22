"""Exercise actual entrance-label registration, component ownership and lifecycle.

Engine drawing, collision geometry and destination wording use explicit I/O
shims. The optional immutable 1.8.11 ZIP supplies the old production updater
bodies for an executable duplicate-label reproduction. No game build or ROM
playthrough is claimed.
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


def fragments(ui: str, world: str, floor: str, legacy: bool) -> tuple[dict[str, str], dict[str, str]]:
    functions = {
        "YELLOW_FUNCTION": function(ui, "UpdateRoomDebugLabels"),
        "RESET_FUNCTION": function(world, "ResetRoomDebugWorldLabels"),
        "CACHE_FUNCTION": function(world, "CacheRoomDebugExitAnchors"),
        "CYAN_FUNCTION": function(world, "UpdateRoomDebugWorldLabels"),
        "FLOOR_WRAPPER": function(floor, "BgCheck_EntityRaycastFloor3"),
    }
    extra = {
        "VISIBLE_FUNCTION": (ui, "RoomDebugActorLabelVisible"),
        "COLLECTOR_FUNCTION": (ui, "CollectRoomDebugDoorActors"),
        "OWNERSHIP_FUNCTION": (world, "RoomDebugDoorExitPolygons"),
    }
    for token, (source, name) in extra.items():
        functions[token] = "" if legacy else function(source, name)
    hooks = ui[ui.index("void CheckTrackerWindow::InitElement()") :]
    parts = {
        **functions,
        "DOOR_TYPE": re.search(r"struct RoomDebugDoor \{.*?\n\};", ui, re.S)[0],
        "SCENE_TYPE": re.search(r"struct RoomDebugSceneTransition \{.*?\n\};", ui, re.S)[0],
        "WORLD_GLOBALS": world.split("static void ResetRoomDebugWorldLabels()", 1)[0],
        "COLLECTOR_ALIAS": "" if legacy else re.search(r"using RoomDebugDoorActors = [^\n]+;", ui)[0],
        "OWNERSHIP_ALIAS": "" if legacy else re.search(r"using RoomDebugExitPolygons = [^\n]+;", world)[0],
        "SCENE_HOOK": re.search(r"OnSceneInit>\(\[\]\(int16_t\) (\{.*?\n    \})\);", hooks, re.S)[1],
        "ACTOR_HOOK": re.search(r"OnActorDestroy>\(\[\]\(void\* actor\) (\{.*?\n    \})\);", hooks, re.S)[1],
    }
    forbidden = ("Archipelago_EntranceObserve", "Archipelago_EntranceSelect", "Archipelago_ResolveDoor",
                 "Archipelago_EntranceRecord", "Archipelago_Report", "Flags_Set", "Room_RequestNewRoom")
    for name, value in functions.items():
        assert not any(token in value for token in forbidden), name
    return parts, functions


def run_fixture(build: Path, name: str, fixture: str, parts: dict[str, str], legacy: bool) -> dict:
    for token, value in parts.items():
        fixture = fixture.replace("@" + token + "@", value)
    assert not re.search(r"@[A-Z_]+@", fixture)
    source = build / (name + ".cpp")
    source.write_text(fixture)
    binary = build / name
    command = ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(build), "-I", str(SOURCE),
               "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-g", "-O1"]
    if legacy:
        command.append("-DLEGACY_REPLAY")
    compiled = subprocess.run(command + [str(source), "-o", str(binary)], text=True, capture_output=True)
    if compiled.returncode:
        raise RuntimeError(compiled.stdout + compiled.stderr)
    environment = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:halt_on_error=1",
                       UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
    executed = subprocess.run([str(binary)], text=True, capture_output=True, env=environment)
    print(executed.stdout, end="")
    if executed.returncode:
        raise RuntimeError(executed.stderr or f"{name} failed: {executed.returncode}")
    match = re.search(r"RESULT cases=(\d+) assertions=(\d+)", executed.stdout)
    assert match
    return {"status": "passed", "cases": int(match[1]), "assertions": int(match[2]),
            "output": executed.stdout.splitlines()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, help="Immutable delivered 1.8.11 source ZIP")
    args = parser.parse_args()
    rando = SOURCE / "soh/Enhancements/randomizer"
    paths = {
        "ui": rando / "randomizer_check_tracker.cpp",
        "world": rando / "RoomDebugWorldLabels.inc",
        "geometry": rando / "SceneExitLabels.h",
        "doors": rando / "RoomDebugDoorData.inc",
        "scene_data": rando / "RoomDebugSceneData.inc",
        "tags": SOURCE / "soh/Enhancements/nametag.cpp",
        "tag_api": SOURCE / "soh/Enhancements/nametag.h",
        "player": SOURCE / "src/overlays/actors/ovl_player_actor/z_player.c",
        "door_actor": SOURCE / "src/overlays/actors/ovl_En_Door/z_en_door.c",
        "collision": SOURCE / "src/code/z_bgcheck.c",
        "runner": Path(__file__),
        "extractor": Path(__file__).with_name("test_soul_object_blockers.py"),
        "fixture": Path(__file__).with_name("entrance_label_overlays_native_tests.cpp.in"),
    }
    before = {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}
    ui, world, floor = (paths[name].read_text() for name in ("ui", "world", "collision"))
    parts, functions = fragments(ui, world, floor, legacy=False)

    # Ground the overlay ownership probes and visibility policy in native source.
    player = function(paths["player"].read_text(), "Player_ActionHandler_1")
    assert "sp6C = (doorDirection * 22.0f)" in player
    assert "checkPos.y = doorActor->world.pos.y + 10.0f" in player
    assert "BgCheck_EntityRaycastFloor1(&play->colCtx, &groundPoly, &checkPos)" in player
    idle = function(paths["door_actor"].read_text(), "EnDoor_Idle")
    assert "fabsf(playerPosRelToDoor.y) < 20.0f" in idle
    first = function(floor, "BgCheck_EntityRaycastFloor1")
    third = functions["FLOOR_WRAPPER"]
    assert "COLPOLY_IGNORE_ENTITY, outPoly, &bgId, pos, NULL, 0x1C, 1.0f" in first
    assert "COLPOLY_IGNORE_ENTITY, outPoly, bgId, pos, NULL, 0x1C, 1.0f" in third
    renderer = function(paths["tags"].read_text(), "DrawNameTag")
    assert "nameTag->actor->draw == nullptr || !nameTag->actor->isDrawn" in renderer
    assert "const float fadeEnd = nameTag->actor ? 440000.0f : 2250000.0f" in renderer
    assert 'CVAR_TRACKER_CHECK("RoomDebugDestinationLabels"), 0' in functions["YELLOW_FUNCTION"]
    assert '#include "functions.h"' in ui.split('extern "C" {', 1)[1].split("}", 1)[0]

    baseline_info = None
    baseline_parts = None
    if args.baseline:
        with ZipFile(args.baseline) as archive:
            old_ui = archive.read("soh/Enhancements/randomizer/randomizer_check_tracker.cpp").decode().replace("\r\n", "\n")
            old_world = archive.read("soh/Enhancements/randomizer/RoomDebugWorldLabels.inc").decode().replace("\r\n", "\n")
        baseline_parts, baseline_functions = fragments(old_ui, old_world, floor, legacy=True)
        baseline_info = {
            "archive": args.baseline.name, "sha256": digest(args.baseline),
            "tested_function_sha256": {name: hashlib.sha256(value.encode()).hexdigest()
                                       for name, value in baseline_functions.items() if value},
            "scope": "Old production updater/cache/reset bodies taken directly from the supplied ZIP; explicit engine I/O shims and the current backward-compatible SceneExitLabels.h. The header's added polygon metadata is unused by the old bodies.",
        }
        # Destination wording/policy remain outside the overlay edit. The separately
        # validated Finder auto-expansion update may change its view/controller.
        for name, current, previous in (
            ("RoomDebugDestination", ui, old_ui),
            ("RoomDebugSceneExitText", world, old_world),
            ("RoomDebugPassageText", world, old_world),
            ("FinderCheckArrival", ui, old_ui),
        ):
            assert function(current, name) == function(previous, name), name + " unexpectedly changed"

    with tempfile.TemporaryDirectory(prefix="soh-entrance-overlays-") as temporary:
        build = Path(temporary)
        color = build / "ship/utils/color.h"
        color.parent.mkdir(parents=True)
        color.write_text("#pragma once\n#include <cstdint>\nstruct Color_RGBA8 { uint8_t r, g, b, a; };\n")
        header_source = build / "header.cpp"
        header_source.write_text('#include "soh/Enhancements/randomizer/SceneExitLabels.h"\nint main() {}\n')
        result = subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-I", str(SOURCE),
                                 "-fsyntax-only", str(header_source)], text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        template = paths["fixture"].read_text()
        if baseline_parts:
            baseline_info["reproduction"] = run_fixture(build, "before", template, baseline_parts, legacy=True)
        current = run_fixture(build, "after", template, parts, legacy=False)
    after = {str(path.relative_to(SOURCE)): digest(path) for path in paths.values()}
    if before != after:
        raise RuntimeError("Source changed during validation; rerun after edits settle.")
    report = {
        **current,
        "sanitizers": ["AddressSanitizer", "UndefinedBehaviorSanitizer"],
        "standalone_header_compile": "passed",
        "source_unchanged_during_tests": True,
        "destination_wording_unchanged_from_baseline": bool(args.baseline),
        "scope": "Actual production collector, renderer-eligibility helper, yellow/cyan updaters, exit ownership, cache/reset bodies, scene/actor hook bodies and Floor3 wrapper; full SceneExitLabels.h and physical catalogues. Engine actors, synthetic triangle floor queries, NameTag registration and destination wording use explicit I/O shims. No full native game build, ROM geometry, rendered UI/controller playthrough, or new seed validation.",
        "sources": after,
        "tested_function_sha256": {name: hashlib.sha256(value.encode()).hexdigest() for name, value in functions.items()},
        "baseline": baseline_info,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
