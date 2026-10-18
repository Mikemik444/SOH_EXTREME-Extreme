"""Compile the actual AP runtime and reporting methods with isolated engine IO."""
from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile


def main():
    root = Path(__file__).resolve().parents[2]
    compiler = shutil.which("g++") or shutil.which("c++")
    if not compiler:
        raise SystemExit("A C++20 compiler (g++ or c++) is required for this regression test.")
    client = (root / "soh/Network/Archipelago/ArchipelagoClient.cpp").read_text(encoding="utf-8-sig")
    start = client.index("void ArchipelagoClient::CaptureSceneTransition()")
    end = client.index("void ArchipelagoClient::BeginDoorTransition(", start)
    native = (root / "soh/Enhancements/randomizer/randomizer_entrance.c").read_text(encoding="utf-8-sig")
    override_start = native.index("s16 Entrance_OverrideNextIndex(")
    override_end = native.index("s16 Entrance_OverrideDynamicExit(", override_start)
    alias_start = native.index("        // Override both land and water entrances")
    alias_end = native.index("\n    }\n\n    // Stop playing background music", alias_start)
    entrance_header = (root / "soh/Enhancements/randomizer/randomizer_entrance.h").read_text(encoding="utf-8-sig")
    capacity = re.search(r"^#define ENTRANCE_OVERRIDES_MAX_COUNT\s+\d+[^\r\n]*", entrance_header, re.MULTILINE)
    if capacity is None:
        raise SystemExit("The production entrance capacity definition was not found.")
    catalog = json.loads((root / "archipelago/soh_extreme/EntranceCatalog.json").read_text())
    overworld = [row for row in catalog if row["category"] == "overworld"]
    with tempfile.TemporaryDirectory(prefix="soh-entrance-test-") as directory:
        work = Path(directory)
        for name in ("entrance.h", "randomizer_entrance.h", "randomizer_grotto.h"):
            stub = work / "soh/Enhancements/randomizer" / name
            stub.parent.mkdir(parents=True, exist_ok=True)
            stub.write_text("// Engine types are supplied by the isolated test.\n")
        (work / "captured_scene_methods.inc").write_text(client[start:end])
        (work / "captured_native_scene_override.inc").write_text(native[override_start:override_end])
        (work / "captured_native_water_aliases.inc").write_text(native[alias_start:alias_end])
        (work / "captured_entrance_capacity.h").write_text(capacity.group(0) + "\n")
        (work / "captured_overworld_endpoints.h").write_text(
            "constexpr int kOverworldEndpointIds[] = {" + ",".join(str(row["id"]) for row in overworld) + "};\n"
            "constexpr int kOverworldPrimaryEndpointIds[] = {" +
            ",".join(str(row["id"]) for row in overworld if row["primary"]) + "};\n"
        )
        executable = work / "entrance_runtime_tests"
        subprocess.run([
            compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(work),
            str(Path(__file__).with_name("entrance_runtime_tests.cpp")), "-o", str(executable),
        ], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    main()
