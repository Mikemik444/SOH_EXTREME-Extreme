"""Validate observed refill metadata against native pot/crate drop functions.

Native drop parameter decoding, large-crate initialization, collectible flags,
and age conversion execute as C11. Exact check identification and observation
callbacks execute as C++20. Hook dispatch and drop allocation are explicit IO
boundaries. Actual bounded source retention and JSON serialization execute;
AP refill proof/transport is tested separately.
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

from test_zora_river_native import function


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dependencies", type=Path, default=Path("tests/ammo_sources_1812_native_dependencies"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sources = (
        "soh/Network/Archipelago/AmmoPolicy.h",
        "soh/Network/Archipelago/AmmoSourcePolicy.h",
        "soh/Network/Archipelago/ArchipelagoC.h",
        "soh/Enhancements/randomizer/ShufflePots.cpp",
        "soh/Enhancements/randomizer/ShuffleCrates.cpp",
        "soh/Enhancements/randomizer/RCToRandInf.cpp",
        "soh/Enhancements/randomizer/randomizerTypes.h",
        "src/overlays/actors/ovl_Obj_Tsubo/z_obj_tsubo.c",
        "src/overlays/actors/ovl_Obj_Kibako/z_obj_kibako.c",
        "src/overlays/actors/ovl_Obj_Kibako2/z_obj_kibako2.c",
        "src/code/z_actor.c",
        "src/code/z_en_item00.c",
        "soh/Network/Archipelago/ArchipelagoClient.cpp",
        "soh/Network/Archipelago/ArchipelagoClient.h",
    )
    test_names = (
        "tools/tests/test_ammo_sources_native.py",
        "tools/tests/ammo_sources_native_io.h",
        "tools/tests/ammo_sources_native_tests.cpp.in",
        "tools/tests/ammo_sources_legacy_functions.inc",
        "tools/tests/test_zora_river_native.py",
    )
    before = {name: digest(root / name) for name in sources}
    tests_before = {name: digest(root / name) for name in test_names}
    dependency_names = ("z64actor.h", "z64actor.h.provenance.json")
    dependencies_before = {name: digest(args.dependencies / name) for name in dependency_names}
    provenance = json.loads((args.dependencies / "z64actor.h.provenance.json").read_text())
    if provenance["sha256"] != dependencies_before["z64actor.h"]:
        raise SystemExit("Retained official native header differs from its recorded download hash")
    actor_header = (args.dependencies / "z64actor.h").read_text()
    enum_match = re.search(r"typedef enum \{\s*/\* 0x00 \*/ ITEM00_RUPEE_GREEN,.*?\} [A-Za-z0-9_]+;",
                           actor_header, re.S)
    if enum_match is None:
        raise SystemExit("Cannot extract the actual native Item00 drop enum")
    item_enum = enum_match[0]
    text = {name: (root / name).read_text(encoding="utf-8-sig") for name in sources}
    pots, crates = text[sources[3]], text[sources[4]]
    bridge = text[sources[2]]
    if not re.search(r"void Archipelago_ObserveAmmoSource\(int32_t randomizerCheck, int32_t actorId,\s*"
                     r"int32_t sourceDropParams,\s*int32_t collectibleInput\);", bridge):
        raise SystemExit("The real observation C bridge declaration is missing or changed")
    native = {}
    for path, signatures in (
        (sources[7], ("void ObjTsubo_SpawnCollectible(ObjTsubo* this, PlayState* play) {",)),
        (sources[8], ("void ObjKibako_SpawnCollectible(ObjKibako* this, PlayState* play) {",)),
        (sources[9], ("void ObjKibako2_SpawnCollectible(ObjKibako2* this, PlayState* play) {",
                      "void ObjKibako2_Init(Actor* thisx, PlayState* play) {")),
        (sources[10], ("s32 Flags_GetCollectible(", "void Flags_SetCollectible(")),
        (sources[11], ("s16 func_8001F404(",)),
    ):
        for signature in signatures:
            native[signature] = function(text[path], signature)
    identities = {signature: function(body, signature) for body, signatures in (
        (text[sources[5]], ("bool IdentifyCheck(",)),
        (pots, ("static CheckIdentity IdentifyPot(",)),
        (crates, ("static CheckIdentity IdentifyCrate(", "static CheckIdentity IdentifySmallCrate(")),
    ) for signature in signatures}
    callbacks = {signature: function(body, signature) for body, signatures in (
        (pots, ("void RegisterShufflePots(",)),
        (crates, ("void ObjKibako2_RandomizerInit(", "void ObjKibako_RandomizerInit(", "void RegisterShuffleCrates(")),
    ) for signature in signatures}
    source_functions = {signature: function(text[sources[12]], signature) for signature in (
        "void ArchipelagoClient::ResetAmmoSources(",
        "void ArchipelagoClient::ObserveAmmoSource(",
        "std::string ArchipelagoClient::AmmoSourcesJson(",
        'extern "C" void Archipelago_ObserveAmmoSource(',
    )}
    types = text[sources[6]]
    check_identity = re.search(r"typedef struct CheckIdentity \{.*?\} CheckIdentity;", types, re.S)[0]
    params_macro = re.search(r"^#define TWO_ACTOR_PARAMS[^\n]+", types, re.M)[0]
    c_code = '#include "ammo_sources_native_io.h"\nstatic int sInitChain[1];\n' + "\n\n".join(native.values())
    c_code += "\nuint32_t SourceTest_AmmoSourceMaskC(int32_t kind, int32_t params, int32_t flag) {\n"
    c_code += "    return SohExtreme_AmmoSourceMask(kind, params, flag);\n}\n"
    test_root = root / "tools/tests"
    legacy = (test_root / "ammo_sources_legacy_functions.inc").read_text()
    cpp_code = (test_root / "ammo_sources_native_tests.cpp.in").read_text()
    replacements = {
        "IDENTITY_TYPE": check_identity + "\n" + params_macro,
        "IDENTITIES": "\n\n".join(identities.values()),
        "CALLBACKS": "\n\n".join(callbacks.values()),
        "SOURCE_FUNCTIONS": "\n\n".join(source_functions.values()),
        "LEGACY": legacy,
    }
    for name, body in replacements.items():
        cpp_code = cpp_code.replace("@" + name + "@", body)
    if re.search(r"@[A-Z_]+@", cpp_code):
        raise SystemExit("Unexpanded observed-source fixture")
    with tempfile.TemporaryDirectory(prefix="soh-ammo-sources-") as directory:
        directory = Path(directory)
        (directory / "native.c").write_text(c_code)
        (directory / "fixture.cpp").write_text(cpp_code)
        (directory / "captured_item00_enum.h").write_text("#pragma once\n" + item_enum + "\n")
        common = ["-O1", "-g", "-fno-omit-frame-pointer", "-fsanitize=address,undefined", "-fno-pie",
                  "-I" + str(root), "-I" + str(test_root), "-I" + str(directory)]
        commands = [
            [shutil.which("gcc") or "cc", "-std=c11", "-Werror=implicit-function-declaration", *common,
             "-c", str(directory / "native.c"), "-o", str(directory / "native.o")],
            [shutil.which("g++") or "c++", "-std=c++20", *common, "-no-pie",
             str(directory / "fixture.cpp"), str(directory / "native.o"), "-o", str(directory / "sources")],
        ]
        for command in commands:
            result = subprocess.run(command, text=True, capture_output=True)
            if result.returncode:
                raise SystemExit(result.stdout + result.stderr)
        result = subprocess.run([str(directory / "sources")], text=True, capture_output=True,
            env=dict(os.environ, ASAN_OPTIONS="detect_leaks=0:halt_on_error=1",
                     UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1"))
        if result.returncode:
            raise SystemExit(result.stdout + result.stderr)
    counts = json.loads(result.stdout)
    after = {name: digest(root / name) for name in sources}
    tests_after = {name: digest(root / name) for name in test_names}
    dependencies_after = {name: digest(args.dependencies / name) for name in dependency_names}
    if before != after or tests_before != tests_after or dependencies_before != dependencies_after:
        raise SystemExit("Source changed during observed-source validation; rerun after edits settle")
    # Observation must not widen randomized rendering, item replacement or doors.
    behavior_hashes = {}
    for body, label, names in ((pots, "pots", ("uint8_t ObjTsubo_RandomizerHoldsItem(",
                                               "void ObjTsubo_RandomizerSpawnCollectible(")),
                               (crates, "crates", ("uint8_t ObjKibako2_RandomizerHoldsItem(",
                                                    "uint8_t ObjKibako_RandomizerHoldsItem(",
                                                    "void ObjKibako2_RandomizerSpawnCollectible(",
                                                    "void ObjKibako_RandomizerSpawnCollectible("))):
        behavior_hashes[label] = {name: hashlib.sha256(function(body, name).encode()).hexdigest() for name in names}
    expected_behavior = dict(re.findall(r"Unchanged (\S+) SHA256: ([0-9a-f]{64})", legacy))
    for group in behavior_hashes.values():
        for signature, checksum in group.items():
            name = signature.rsplit(" ", 1)[-1].rstrip("(")
            if expected_behavior.get(name) != checksum:
                raise SystemExit("Pre-observation randomized container behavior changed: " + name)
    report = {
        "status": "passed", **counts,
        "sanitizers": ["AddressSanitizer", "UndefinedBehaviorSanitizer"],
        "leak_detection": "Disabled because executor /proc/task access is unavailable",
        "languages": ["C11 native drop/init/flag/age functions", "C++20 identity, registration, retention and C bridge"],
        "source_unchanged_during_tests": True,
        "scope": "Actual native pot/small-crate/large-crate drop functions, large-crate Init, collectible flag Get/Set, age conversion, exact IdentifyCheck and source-specific identity normalization, source observation init callbacks, actual client ObserveAmmoSource/ResetAmmoSources/AmmoSourcesJson methods and exported C bridge. All 64 collectible flags and 32 raw drop values are exercised for each actor class. Bounds, deduplication, conflicting/tombstoned variants, observed age, physical-file change and reset execute through real client methods. Native allocation, inventory, check database IO and hook dispatch are controlled. Full save/settings lifecycle call sites are source-bound but not compiled in this fixture. No scene geometry, AP reachability proof, complete Windows game build or controller playthrough is claimed.",
        "raw_mask_bits": {"stick": 1, "nut": 2, "bomb": 4, "arrows": 16, "seeds_for_age_conversion": 32},
        "accepted_raw_drop_ids": {"bombs_a": 4, "arrows_small": 8, "arrows_medium": 9, "arrows_large": 10,
                                  "bombs_b": 11, "nuts": 12, "stick": 13, "seeds": 16},
        "large_crate_contract": "sourceDropParams=actor.home.rot.x; collectibleInput=crateActor.collectibleFlag saved before native Init clears home.rot.z",
        "sources": after, "tests": tests_after, "dependencies": dependencies_after,
        "native_drop_enum_provenance": provenance,
        "native_drop_enum_sha256": hashlib.sha256(item_enum.encode()).hexdigest(),
        "randomized_container_behavior_unchanged": True,
        "tested_function_sha256": {name: hashlib.sha256(body.encode()).hexdigest()
                                   for name, body in {**native, **identities, **callbacks, **source_functions}.items()},
        "randomized_behavior_function_sha256": behavior_hashes,
        "retained_baseline_source_sha256": dict(re.findall(r"Original (\S+) SHA256: ([0-9a-f]{64})", legacy)),
        "replay_command": "python3 source/tools/tests/test_ammo_sources_native.py --dependencies tests/ammo_sources_1812_native_dependencies --report tests/ammo_sources_1812_native.json",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "passed", **counts, "report": str(args.report)}))


if __name__ == "__main__":
    main()
