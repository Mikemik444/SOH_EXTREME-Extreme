"""Run native scene/room flag-lifecycle fragments and inventory temporary shutters.

The engine IO around the captured code is isolated. This proves flag storage,
cleanup ordering, respawn masks and native gate decisions; it is not a game
build, collision playthrough or a proof of each switch's physical approach.
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


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def between(text, first, after):
    start = text.index(first)
    return text[start:text.index(after, start)]


def function(text, name):
    match = re.search(r"^(?:void|s32|int) " + re.escape(name) + r"\([^;]+?\) \{", text, re.M)
    assert match, name
    opening = text.index("{", match.start())
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[match.start():end]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    source_names = (
        "src/code/z_actor.c", "src/code/z_play.c",
        "src/overlays/actors/ovl_player_actor/z_player.c",
        "src/overlays/actors/ovl_Door_Shutter/z_door_shutter.c",
        "src/overlays/actors/ovl_Door_Shutter/z_door_shutter.h",
        "src/overlays/actors/ovl_Bg_Mizu_Shutter/z_bg_mizu_shutter.c",
        "soh/Network/Archipelago/EntranceRuntime.inc",
        "archipelago/soh_extreme/EntranceCatalog.json",
        "soh/Enhancements/randomizer/hook_handlers.cpp",
    )
    test_names = ("tools/tests/test_scene_flag_lifecycle.py", "tools/tests/scene_flag_lifecycle_tests.cpp")
    source_before = {name: digest(root / name) for name in source_names}
    tests_before = {name: digest(root / name) for name in test_names}
    actor, play, player, door, door_header, mizu, runtime, catalog_text, hooks = (
        (root / name).read_text(encoding="utf-8-sig") for name in source_names)
    catalog = json.loads(catalog_text)
    shutters = [row for row in catalog if row.get("actor") == 46
                and ((row["params"] >> 6) & 15) in (2, 7) and row["params"] & 63 >= 32]
    assert len(shutters) == 48
    assert len({(row["scene"], row["door"]) for row in shutters}) == 24
    # Bind the actual AP call path without treating the complete game loop as
    # executed by this fixture. Save is keyed by play->sceneNum, independently
    # of the next entrance selected by the AP door route.
    destroy = function(play, "Play_Destroy")
    assert "func_80031C3C(&play->actorCtx, play);" in destroy
    resolve = function(runtime, "ResolveDoor")
    assert "gSaveContext.respawnFlag = 0;" in resolve
    assert "gSaveContext.respawn[RESPAWN_MODE_RETURN].tempSwchFlags = 0;" in resolve
    assert "gSaveContext.respawn[RESPAWN_MODE_RETURN].tempCollectFlags = 0;" in resolve
    restored = between(function(actor, "Actor_InitContext"),
                       "    savedSceneFlags = &gSaveContext.sceneFlags[play->sceneNum];", "    TitleCard_Init(")
    respawn = between(player, "    respawnFlag = gSaveContext.respawnFlag;",
                      "    if ((respawnFlag == 0) || (respawnFlag < -1)) {")
    reset_start = mizu.index("        if (this->timerMax != 0x3F * 20) {")
    reset_end = mizu.index("\n    }\n}", reset_start)
    mizu_reset = mizu[reset_start:reset_end]
    record = between(function(hooks, "RandomizerOnSceneFlagSetHandler"),
                     "    if (flagType == FLAG_SCENE_SWITCH) {", "\n\n    RandomizerCheck rc =")
    replay = between(function(hooks, "RandomizerOnActorInitHandler"),
                     "    if (actor->id == ACTOR_PLAYER) {", "\n\n    if (actor->id == ACTOR_EN_SI)")
    captures = {
        "scene_flag_types.inc": between(door_header, "typedef enum {", "struct DoorShutter;"),
        "scene_flag_access.inc": "\n\n".join(function(actor, name) for name in (
            "Flags_GetSwitch", "Flags_SetSwitch", "Flags_UnsetSwitch", "Flags_GetClear",
            "Flags_SetClear", "Flags_UnsetClear", "Flags_GetTempClear", "Flags_SetTempClear")),
        "scene_flag_save.inc": function(play, "Play_SaveSceneFlags") + "\n\n" + function(play, "Play_SetRespawnData"),
        "scene_flag_restore.inc": "void RestoreSceneFlags(PlayState* play, ActorContext* actorCtx) {\n"
                                  "    SavedSceneFlags* savedSceneFlags;\n" + restored + "}\n",
        "scene_flag_cleanup.inc": function(actor, "func_80031B14") + "\n\n" + function(actor, "func_80031C3C"),
        "scene_flag_respawn.inc": "void RestorePlayerRespawn(Player* this, PlayState* play) {\n"
                                  "    Actor* thisx = &this->actor;\n    s32 respawnFlag, respawnMode;\n" + respawn + "}\n",
        "scene_flag_shutter.inc": "\n\n".join(function(door, name) for name in (
            "DoorShutter_SetupAction", "DoorShutter_SetupDoor", "DoorShutter_WaitClear",
            "DoorShutter_BarAndWaitSwitchFlag", "DoorShutter_UnbarredCheckSwitchFlag")),
        "scene_flag_timer.inc": "void RestoreMizuShutterState(BgMizuShutter* this, PlayState* play) {\n"
                                + mizu_reset + "\n}\n\n" + function(mizu, "BgMizuShutter_WaitForTimer"),
        "scene_flag_recorded.inc": "void RecordSceneSwitch(int16_t sceneNum, int16_t flagType, int16_t flag) {\n"
                                   + record + "\n}\n\nvoid RestoreRecordedSwitches(Actor* actor) {\n" + replay + "\n}\n",
        "scene_flag_placements.inc": "\n".join(
            f'{{{row["id"]}, {row["scene"]}, {row["door"]}, {row["side"]}, {row["from_room"]}, '
            f'{row["room"]}, {row["params"]}}},' for row in shutters),
    }
    # The C actor identifier is a C++ keyword. Rename only that identifier;
    # the captured expressions, branch order and assignments remain intact.
    captures = {name: re.sub(r"\bthis\b", "self", value) for name, value in captures.items()}
    compiler = shutil.which("g++") or shutil.which("c++")
    if not compiler:
        raise SystemExit("A C++20 compiler is required.")
    with tempfile.TemporaryDirectory(prefix="soh-scene-flags-") as directory:
        work = Path(directory)
        for name, value in captures.items():
            (work / name).write_text(value + "\n")
        executable = work / "scene_flag_lifecycle"
        subprocess.run([compiler, "-std=c++20", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                        "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-I", str(work),
                        str(root / test_names[1]), "-o", str(executable)], check=True)
        environment = dict(os.environ, ASAN_OPTIONS="detect_leaks=0",
                           UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
        result = subprocess.run([str(executable)], capture_output=True, text=True, env=environment)
        if result.returncode:
            print(result.stdout)
            print(result.stderr)
            raise SystemExit(result.returncode)
        cases = json.loads(result.stdout)
    assert source_before == {name: digest(root / name) for name in source_names}, "Production changed during validation"
    assert tests_before == {name: digest(root / name) for name in test_names}, "Test changed during validation"
    inventory = [{key: row[key] for key in (
                    "id", "source", "target", "scene", "door", "side", "from_room", "room", "params")}
                 | {"switch_flag": row["params"] & 63,
                    "native_side": "switch" if row["side"] else "unbarred",
                    "same_room_yaw_discriminator": row["from_room"] == row["room"],
                    "catalog_source_condition": row.get("condition")}
                 for row in shutters]
    report = {
        "status": "passed", "cases": cases,
        "source_sha256": source_before, "test_sha256": tests_before,
        "captured_fragment_sha256": {name: hashlib.sha256(value.encode()).hexdigest() for name, value in captures.items()},
        "sanitizers": ["address", "undefined"], "leak_scanner": False,
        "engine_io_isolated": True, "native_game_build": False, "in_game_playthrough": False,
        "scope": "Native scene flag save/restore, actor cleanup ordering, normal room cleanup, respawn masks, all catalog temporary-switch shutter directions, resettable water-shutter timer decisions, and existing non-MQ randomizer recorded-switch replay. Physical switch approach and collision assets are not executed.",
        "source_path_assertions": ["Play_Destroy invokes source actor cleanup", "AP ResolveDoor selects respawnFlag 0 and clears return temporary flags"],
        "temporary_switch_shutter_inventory": inventory,
        "conclusion": "Permanent scene flags stay scoped to the source and destination scene. Ordinary room cleanup retains switches 32..55; actor-context initialization clears all temporary switches, and room cleanup clears 56..63. Existing player-init hooks then replay only explicitly recorded scene switches (among these shutters: Jabu59, Forest37, Spirit35). Timer handlers can also unset saved-range switch IDs. No blanket flag copying or switch grants are justified by this fixture.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "passed", "report": str(args.report), "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
