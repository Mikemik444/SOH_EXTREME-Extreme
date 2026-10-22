"""Compile the production ammo ownership helper with its real setting declaration.

The negative case includes the real C++ OTRGlobals header, whose C-only API block
does not declare Randomizer_GetSettingValue. The fixed case additionally uses the
exact C-linkage declaration now present in ArchipelagoClient.cpp. Engine storage
and inventory macros are the existing explicit ammo fixture boundary; the setting
function is neither mocked nor defined in either compile-only translation unit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from test_zora_river_native import function


SOURCE = Path(__file__).resolve().parents[2]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    client_path = "soh/Network/Archipelago/ArchipelagoClient.cpp"
    source_names = (client_path, "soh/OTRGlobals.h", "soh/OTRGlobals.cpp",
                    "soh/Enhancements/randomizer/randomizerEnums.h",
                    "soh/Enhancements/randomizer/randomizerEnums/RandomizerSettingKey.h",
                    "soh/Network/Archipelago/ArchipelagoC.h",
                    "soh/Network/Archipelago/AmmoPolicy.h")
    test_names = ("tools/tests/test_setting_bridge_declaration.py",
                  "tools/tests/test_zora_river_native.py", "tools/tests/ammo_native_io.h")
    before = {name: sha((SOURCE / name).read_bytes()) for name in source_names}
    test_before = {name: sha((SOURCE / name).read_bytes()) for name in test_names}
    client_bytes = (SOURCE / client_path).read_bytes()
    client = client_bytes.decode().replace("\r\n", "\n")
    bridge = (SOURCE / "soh/OTRGlobals.cpp").read_text()
    definition = function(bridge, 'extern "C" u8 Randomizer_GetSettingValue(')
    declaration = definition.split("{", 1)[0].rstrip() + ";"
    assert client.count(declaration) == 1
    with zipfile.ZipFile(args.baseline) as baseline:
        old_bytes = baseline.read(client_path)
    assert client_bytes.replace((declaration + "\r\n").encode(), b"", 1) == old_bytes
    helper = function(client, "uint32_t CaptureApAmmoOwnedMask(")
    assert helper == function(old_bytes.decode().replace("\r\n", "\n"),
                              "uint32_t CaptureApAmmoOwnedMask(")

    # Remove the old test-only declaration and numeric key placeholder. The real
    # production enum supplies the parameter type and RSK_BOMBCHU_BAG value.
    io = (SOURCE / "tools/tests/ammo_native_io.h").read_text()
    assert io.count("int Randomizer_GetSettingValue(int setting);\n") == 1
    assert io.count("RSK_BOMBCHU_BAG = 0, ") == 1
    io = io.replace("int Randomizer_GetSettingValue(int setting);\n", "")
    io = io.replace("RSK_BOMBCHU_BAG = 0, ", "")
    # These action enums are only consumed by the full player/ammo fixture.
    io = io.replace('#include "captured_arrow_types.h"\n', "")
    io = io.replace('#include "captured_player_actions.h"\n', "")
    enums = (SOURCE / "soh/Enhancements/randomizer/randomizerEnums.h").read_text()
    expansion = "\n".join(re.findall(r"^#define RANDO_ENUM_(?:BEGIN|ITEM|END)\(.*$", enums, re.M))
    assert len(expansion.splitlines()) == 3
    prefix = '\n'.join((
        '#include "ammo_declaration_io.h"',
        '#include "soh/OTRGlobals.h"',
        expansion,
        '#include "soh/Enhancements/randomizer/randomizerEnums/RandomizerSettingKey.h"',
        '#undef RANDO_ENUM_BEGIN', '#undef RANDO_ENUM_ITEM', '#undef RANDO_ENUM_END',
    )) + '\n'
    variants = {
        "baseline_missing_cpp_declaration": prefix + helper,
        "production_cpp_declaration": prefix + declaration + "\n" + helper,
    }
    results = {}
    with tempfile.TemporaryDirectory(prefix="soh-setting-declaration-") as temp:
        work = Path(temp)
        (work / "ammo_declaration_io.h").write_text(io)
        for name, content in variants.items():
            unit = work / (name + ".cpp")
            unit.write_text(content)
            command = ["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-fsyntax-only",
                       "-I", str(SOURCE), "-I", str(work), str(unit)]
            result = subprocess.run(command, text=True, capture_output=True, timeout=30)
            results[name] = {"returncode": result.returncode,
                             "stderr": result.stderr.replace(temp, "$PROBE"),
                             "translation_unit_sha256": sha(content.encode())}
    negative = results["baseline_missing_cpp_declaration"]
    positive = results["production_cpp_declaration"]
    assert negative["returncode"] != 0 and "Randomizer_GetSettingValue" in negative["stderr"], negative
    assert "not declared" in negative["stderr"], negative
    assert positive["returncode"] == 0, positive
    assert before == {name: sha((SOURCE / name).read_bytes()) for name in source_names}
    assert test_before == {name: sha((SOURCE / name).read_bytes()) for name in test_names}
    report = {
        "status": "passed", "cases": results,
        "scope": "Compile-only check of the complete production ammo ownership helper and its C-linkage setting declaration.",
        "exact_change": "One C-linkage declaration added; every other ArchipelagoClient.cpp byte matches 1.8.13.",
        "baseline": {"archive": args.baseline.name, "archive_sha256": sha(args.baseline.read_bytes()),
                     "source_sha256": {client_path: sha(old_bytes)}},
        "source_sha256": before, "test_sha256": test_before,
        "helper_sha256": sha(helper.encode()), "declaration": declaration,
        "matches_actual_bridge_definition_signature": True,
        "source_unchanged_during_tests": True,
        "compiler": subprocess.check_output(["g++", "--version"], text=True).splitlines()[0],
        "native_windows_build": False,
        "limitations": ["Engine inventory storage and macros are explicit test IO boundaries.",
                        "No function implementation is supplied or linked by this declaration probe.",
                        "This is a focused C++20 compile check, not the full Windows/MSVC build."],
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "passed", "negative_reproduced": True,
                      "fixed_helper_compiles": True, "helper_unchanged": True}))


if __name__ == "__main__":
    main()
