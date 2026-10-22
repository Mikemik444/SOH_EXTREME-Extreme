"""Compile actual native ammo consumers and the AP last-unit guard.

The native C bodies are compiled as C11, the AP wrapper and trap bodies as
C++20, both with AddressSanitizer and UndefinedBehaviorSanitizer. Engine IO,
the clock, and authentication are explicit test boundaries. The actual AP
ownership/state-token/expiry decisions are compiled without replacements.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from test_zora_river_native import between, function


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def declaration(text, start):
    first = text.index(start)
    return text[first:text.index(";", first) + 1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    cc = shutil.which("gcc") or shutil.which("cc")
    cxx = shutil.which("g++") or shutil.which("c++")
    if not cc or not cxx:
        raise SystemExit("C11 and C++20 compilers are required")
    sources = (
        "src/code/z_parameter.c",
        "src/overlays/actors/ovl_player_actor/z_player.c",
        "src/overlays/actors/ovl_En_Arrow/z_en_arrow.h",
        "soh/Enhancements/ExtraTraps.cpp",
        "soh/Network/Archipelago/AmmoPolicy.h",
        "soh/Network/Archipelago/ArchipelagoC.h",
        "soh/Network/Archipelago/ArchipelagoClient.cpp",
        "soh/Network/Archipelago/ArchipelagoClient.h",
        "soh/Network/Archipelago/TrackerMirror.h",
        "soh/SohExtremeVersion.h",
    )
    test_names = (
        "tools/tests/test_ammo_native.py",
        "tools/tests/ammo_native_io.h",
        "tools/tests/ammo_native_tests.cpp.in",
        "tools/tests/ammo_native_legacy_functions.inc",
        "tools/tests/test_zora_river_native.py",
    )
    before = {name: digest(root / name) for name in sources}
    test_before = {name: digest(root / name) for name in test_names}
    read = lambda path: (root / path).read_text(encoding="utf-8-sig")
    parameter, player, arrow, traps = (read(name) for name in sources[:4])
    client = read("soh/Network/Archipelago/ArchipelagoClient.cpp")
    public = read("soh/Network/Archipelago/ArchipelagoC.h")
    legacy = read("tools/tests/ammo_native_legacy_functions.inc")
    signatures = (
        "void Player_InitExplosiveIA(PlayState* play, Player* this) {",
        "s32 func_80834380(PlayState* play, Player* this, s32* itemPtr, s32* typePtr) {",
        "s32 func_8083442C(Player* this, PlayState* play) {",
        "s32 func_808350A4(PlayState* play, Player* this) {",
        "void func_80842A88(PlayState* play, Player* this) {",
        "s32 func_80842AC4(PlayState* play, Player* this) {",
        "void Player_UpdateBurningDekuStick(PlayState* play, Player* this) {",
        "void Player_Action_8084E604(Player* this, PlayState* play) {",
    )
    native = {signature: function(player, signature) for signature in signatures}
    native["void Inventory_ChangeAmmo("] = function(parameter, "void Inventory_ChangeAmmo(")
    helpers = {signature: function(client, signature) for signature in (
        "static uint64_t HashApReceiptBytes(",
        "template <typename T>\nstatic uint64_t HashApReceiptValue(",
        "uint32_t ApAmmoMaskForItem(", "uint32_t CaptureApAmmoOwnedMask(",
        "uint32_t CaptureApAmmoAvailableMask(", "uint32_t CaptureApAmmoRulesFlags(",
        "uint64_t CaptureApAmmoStateToken(",
        "int32_t ArchipelagoClient::AdjustAmmoChange(",
        'extern "C" int32_t Archipelago_AdjustAmmoChange(',
    )}
    trap_functions = {signature: function(traps, signature) for signature in (
        "static void ApplyAmmoTrapReduction(", "static void ResetExtraTrapEffects(",
        "static void UpdateExtraTrapEffects(",
    )}
    if native["void Inventory_ChangeAmmo("].count("Archipelago_AdjustAmmoChange(") != 1:
        raise SystemExit("Inventory_ChangeAmmo must apply exactly one AP adjustment")
    if "int32_t Archipelago_AdjustAmmoChange(int32_t item, int32_t currentAmmo, int32_t change);" not in public:
        raise SystemExit("The real C bridge declaration is missing or has changed")
    if '#include "soh/Network/Archipelago/ArchipelagoC.h"' not in parameter:
        raise SystemExit("Native Inventory_ChangeAmmo must include its real C bridge header")

    action_table = between(player, "static s32 (*sItemActionUpdateFuncs[])", "static void")
    action_names = re.findall(r"//\s*(PLAYER_IA_\w+)", action_table.split("};", 1)[0])
    if len(action_names) != len(set(action_names)) or "PLAYER_IA_BOW" not in action_names:
        raise SystemExit("Unable to capture native player action indices")
    captures = {
        "captured_arrow_types.h": between(arrow, "typedef enum {", "#endif"),
        "captured_player_actions.h": "enum {\n" + "\n".join(
            f"    {name} = {index}," for index, name in enumerate(action_names)) + "\n};\n",
    }
    constants = "\n".join(declaration(player, start) for start in (
        "typedef struct ExplosiveInfo {", "static ExplosiveInfo sExplosiveInfos[]",
        "static u16 D_80854398[]", "static u8 sMagicArrowCosts[]",
        "static Vec3f D_808547A4", "static Vec3f D_808547B0",
        "static Color_RGBA8 D_808547BC", "static Color_RGBA8 D_808547C0",
    ))
    # The struct contains member semicolons, unlike its following data arrays.
    constants = constants.replace(declaration(player, "typedef struct ExplosiveInfo {"),
        between(player, "typedef struct ExplosiveInfo {", "typedef struct BottleDropInfo {").strip())
    c_code = '#include "ammo_native_io.h"\n#include <limits.h>\n' + constants + "\n"
    c_code += "\n\n".join(native.values())
    c_code += "\n#define Inventory_ChangeAmmo Legacy_Inventory_ChangeAmmo\n"
    c_code += function(legacy, "void Inventory_ChangeAmmo(")
    c_code += "\n#undef Inventory_ChangeAmmo\n"
    c_code += r'''
int TestAmmoPureC(void) {
    const int32_t currents[] = { INT32_MIN, -128, -1, 0, 1, 2, 99, 127, INT32_MAX };
    const int32_t changes[] = { INT32_MIN, -32768, -129, -99, -2, -1, 0, 1, 32767, INT32_MAX };
    int checks = 0;
    for (unsigned c = 0; c < sizeof(currents) / sizeof(currents[0]); ++c)
        for (unsigned d = 0; d < sizeof(changes) / sizeof(changes[0]); ++d)
            for (int eligible = 0; eligible != 2; ++eligible)
                for (int refill = 0; refill != 2; ++refill) {
                    const int32_t current = currents[c], change = changes[d];
                    int64_t expected = change;
                    if (eligible && !refill && current > 0 && change < 0) {
                        int64_t result = (int64_t)current + change;
                        expected = (result < 1 ? 1 : result) - current;
                    }
                    ++checks;
                    if (SohExtreme_AdjustAmmoChange(current, change, eligible, refill) != expected)
                        return -checks;
                }
    return checks;
}
'''
    cpp_code = read("tools/tests/ammo_native_tests.cpp.in")
    cpp_code = cpp_code.replace("@CLIENT_FUNCTIONS@", "\n\n".join(helpers.values()))
    cpp_code = cpp_code.replace("@TRAP_ENUM@", between(traps, "typedef enum {", "static AltTrapType roll"))
    cpp_code = cpp_code.replace("@TRAP_FUNCTIONS@", "\n\n".join(trap_functions.values()))
    cpp_code = cpp_code.replace("@LEGACY_TRAP@", between(legacy, "case ADD_AMMO_TRAP:", "// END LEGACY TRAP"))
    if re.search(r"@[A-Z_]+@", cpp_code):
        raise SystemExit("Unexpanded native test template")
    with tempfile.TemporaryDirectory(prefix="soh-ammo-native-") as work:
        work = Path(work)
        for name, code in captures.items():
            (work / name).write_text(code)
        (work / "native.c").write_text(c_code)
        (work / "fixture.cpp").write_text(cpp_code)
        options = ["-O1", "-g", "-fno-omit-frame-pointer", "-fsanitize=address,undefined",
                   "-fno-pie", "-I" + str(root), "-I" + str(root / "tools/tests"), "-I" + str(work)]
        commands = [
            [cc, "-std=c11", "-Werror=implicit-function-declaration", *options,
             "-c", str(work / "native.c"), "-o", str(work / "native.o")],
            [cxx, "-std=c++20", *options, "-no-pie", str(work / "fixture.cpp"),
             str(work / "native.o"), "-o", str(work / "ammo_native")],
        ]
        for command in commands:
            result = subprocess.run(command, text=True, capture_output=True)
            if result.returncode:
                raise SystemExit(result.stdout + result.stderr)
        # LeakSanitizer cannot inspect /proc/task in the managed executor.
        # Address/undefined-behavior instrumentation remains enabled.
        environment = dict(os.environ, ASAN_OPTIONS="detect_leaks=0:halt_on_error=1",
                           UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
        result = subprocess.run([str(work / "ammo_native")], text=True, capture_output=True, env=environment)
        if result.returncode:
            raise SystemExit(result.stdout + result.stderr)
    match = re.search(r"cases=(\d+) assertions=(\d+) baseline_cases=(\d+)", result.stdout)
    if not match:
        raise SystemExit("Native test output did not report completed cases")
    after = {name: digest(root / name) for name in sources}
    test_after = {name: digest(root / name) for name in test_names}
    if before != after or test_before != test_after:
        raise SystemExit("Source files changed during native validation; rerun after the edit finishes")
    tested = dict(native, **helpers, **trap_functions)
    report = {
        "status": "passed", "cases": int(match[1]), "assertions": int(match[2]),
        "baseline_cases": int(match[3]),
        "sanitizers": ["AddressSanitizer", "UndefinedBehaviorSanitizer"],
        "leak_detection": "Disabled: LeakSanitizer cannot inspect /proc/task in the managed executor",
        "languages": ["C11 (actual native ammo/player functions)", "C++20 (actual AP/trap functions)"],
        "source_unchanged_during_tests": True,
        "scope": "Actual Inventory_ChangeAmmo, stick break/burn, bow aiming/firing and native minigame counters, explosive spawning and Bowling counters, nut throw, ExtraTraps ammo-event update, AP ownership/availability/state-token/expiry guard, and exported C wrapper. The pure policy is also compiled and tested as C11 at integer boundaries. Authentication, time, engine storage shapes, bag capacities and unrelated actor/audio/animation/magic IO are isolated. Tracker refill proofs and real scene collision/rendering are outside this native fixture; no complete Windows game build or controller playthrough is claimed.",
        "baseline": {
            "provenance": "Unmodified function/case bodies retained from the user-provided upload/haha.zip",
            "source_hashes": dict(re.findall(r"Original (\S+) SHA256: ([0-9a-f]{64})", legacy)),
            "reproductions": ["last native ammo unit disappears for each of five ammo items",
                               "native ammo trap removes all five final units",
                               "empty Bombchu decrement can leave signed ammo at -1",
                               "signed-byte underflow before native capacity clamp can create arrows from zero"],
        },
        "replay_command": "python3 source/tools/tests/test_ammo_native.py --report tests/ammo_1812_native.json",
        "external_dependencies": ["Python 3", "gcc with C11", "g++ with C++20", "ASan and UBSan"],
        "sources": after, "tests": test_after,
        "tested_function_sha256": {signature: hashlib.sha256(body.encode()).hexdigest()
                                   for signature, body in tested.items()},
        "captured_native_metadata_sha256": {name: hashlib.sha256(body.encode()).hexdigest()
                                           for name, body in captures.items()},
        "output": result.stdout.splitlines(),
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(result.stdout, end="")
    print(f"Report: {args.report}")


if __name__ == "__main__":
    main()
