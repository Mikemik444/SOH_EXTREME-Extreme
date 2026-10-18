"""Compile the actual AP runtime and reporting methods with isolated engine IO."""
from pathlib import Path
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
    with tempfile.TemporaryDirectory(prefix="soh-entrance-test-") as directory:
        work = Path(directory)
        for name in ("entrance.h", "randomizer_entrance.h", "randomizer_grotto.h"):
            stub = work / "soh/Enhancements/randomizer" / name
            stub.parent.mkdir(parents=True, exist_ok=True)
            stub.write_text("// Engine types are supplied by the isolated test.\n")
        (work / "captured_scene_methods.inc").write_text(client[start:end])
        executable = work / "entrance_runtime_tests"
        subprocess.run([
            compiler, "-std=c++20", "-O2", "-Wall", "-Wextra", "-Werror", "-I", str(work),
            str(Path(__file__).with_name("entrance_runtime_tests.cpp")), "-o", str(executable),
        ], check=True)
        subprocess.run([str(executable)], check=True)


if __name__ == "__main__":
    main()
