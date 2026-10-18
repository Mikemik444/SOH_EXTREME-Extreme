"""Verify native Ganon trial medallion gates with their authored door directions.

Runs extracted production OnDoorInit, registration, SetupDoor, WaitClear and
BarAndWaitSwitchFlag code. Inventory, scene flags and animation IO are isolated;
no game build or collision playthrough is claimed.
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


def fragment(text, first, after):
    start = text.index(first)
    return text[start:text.index(after, start)]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    source_names = (
        "soh/Enhancements/randomizer/MedallionLockedTrials.cpp",
        "src/overlays/actors/ovl_Door_Shutter/z_door_shutter.c",
        "src/overlays/actors/ovl_Door_Shutter/z_door_shutter.h",
        "src/code/z_actor.c",
        "archipelago/soh_extreme/EntranceCatalog.json",
    )
    test_names = ("tools/tests/test_medallion_trial_native.py", "tools/tests/medallion_trial_native_tests.cpp")
    sources_before = {name: digest(root / name) for name in source_names}
    tests_before = {name: digest(root / name) for name in test_names}
    read = lambda name: (root / name).read_text(encoding="utf-8-sig")
    hook, door, header, actor, catalog_text = (read(name) for name in source_names)
    catalog = json.loads(catalog_text)
    expected_ids = {9872, 9873, 9874, 9875, 9876, 9877, 9878, 9879, 9880, 9881, 9888, 9889}
    placements = [row for row in catalog if row["id"] in expected_ids]
    assert len(placements) == 12
    assert 'actor->room = play->roomCtx.curRoom.num;' in actor
    assert '(i << 0xA) + transitionActor->params' in actor
    definitions = []
    for row in placements:
        sides = (row["from_room"], row["room"]) if row["side"] == 0 else (row["room"], row["from_room"])
        definitions.append(
            f'{{{row["id"]}, {row["scene"]}, {row["params"] | (row["door"] << 10)}, '
            f'{row["door"]}, {row["from_room"]}, {{{sides[0]}, {sides[1]}}}}},')
    captures = {
        "medallion_gate_types.inc": fragment(header, "typedef enum {", "struct DoorShutter;"),
        "medallion_gate_hook.inc": fragment(hook, "static void OnDoorInit(", "static RegisterShipInitFunc"),
        "medallion_gate_setup.inc": fragment(door, "void DoorShutter_SetupAction(DoorShutter* this, DoorShutterActionFunc actionFunc) {", "void DoorShutter_Init("),
        "medallion_gate_clear.inc": fragment(door, "void DoorShutter_WaitClear(DoorShutter* this, PlayState* play) {", "void DoorShutter_Unopenable("),
        "medallion_gate_switch.inc": fragment(door, "void DoorShutter_BarAndWaitSwitchFlag(DoorShutter* this, PlayState* play) {", "void DoorShutter_UnbarredCheckSwitchFlag("),
        "medallion_gate_placements.inc": "\n".join(definitions),
    }
    # The native C actor uses 'this' as a local identifier; only rename that
    # identifier to compile the same bodies together with the C++ hook.
    captures = {name: re.sub(r'\bthis\b', 'doorActor', text) for name, text in captures.items()}
    compiler = shutil.which("g++") or shutil.which("c++")
    if not compiler:
        raise SystemExit("A C++20 compiler is required.")
    with tempfile.TemporaryDirectory(prefix="soh-medallion-native-") as directory:
        work = Path(directory)
        for name, text in captures.items():
            (work / name).write_text(text + "\n")
        executable = work / "medallion_trial_native"
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
    assert sources_before == {name: digest(root / name) for name in source_names}, "Production changed during validation"
    assert tests_before == {name: digest(root / name) for name in test_names}, "Test changed during validation"
    report = {
        "status": "passed", "cases": cases,
        "source_sha256": sources_before, "test_sha256": tests_before,
        "captured_fragment_sha256": {name: hashlib.sha256(value.encode()).hexdigest()
                                     for name, value in captures.items()},
        "sanitizers": ["address", "undefined"], "leak_scanner": False,
        "engine_io_isolated": True, "native_game_build": False, "in_game_playthrough": False,
        "scope": "Actual native medallion hook and directional shutter decisions, with clear/tempclear/switch and inventory IO isolated; authored non-MQ door placements.",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "passed", "report": str(args.report), "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
