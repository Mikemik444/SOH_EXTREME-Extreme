"""Compile real AP hint loading/rendering and native description methods.

Usage: python test_archipelago_hints.py --dependencies PATH [--report PATH]

PATH must contain nlohmann's single-header json.hpp. Game/session IO is isolated;
the production header and client hint methods compile without alteration.
Textbox pagination and native message-buffer streaming have separate tests.
"""

from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dependencies", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--reveal", action="store_true", help="Compile actual reveal/snapshot/journal client methods")
    mode.add_argument("--save-metadata", action="store_true", help="Compile actual same-save tracker preservation")
    parser.add_argument("--bridge-fixture", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    compiler = shutil.which("g++") or shutil.which("c++")
    if compiler is None:
        raise SystemExit("A C++20 compiler (g++ or c++) is required.")
    dependency = args.dependencies / "json.hpp"
    if not dependency.is_file():
        raise SystemExit(f"Missing nlohmann single-header dependency: {dependency}")

    header = root / "soh/Network/Archipelago/ArchipelagoHintData.h"
    client = root / "soh/Network/Archipelago/ArchipelagoClient.cpp"
    harness = Path(__file__).with_name("archipelago_save_metadata_tests.cpp" if args.save_metadata else
                                    "archipelago_hint_reveal_tests.cpp" if args.reveal else "archipelago_hint_data_tests.cpp")
    paths = [header, client, harness, Path(__file__).resolve(),
             root / "soh/Network/Archipelago/ArchipelagoHintTarget.h",
             root / "soh/Network/Archipelago/ArchipelagoHintClient.inc",
             root / "soh/Network/Archipelago/ArchipelagoClient.h",
             root / "soh/Network/Archipelago/SaveConnectionIdentity.h"]
    before = {str(path.relative_to(root)): digest(path) for path in paths}
    client_text = client.read_text(encoding="utf-8-sig")
    begin = client_text.index("std::string ArchipelagoClient::GetHintItemDescription(")
    end = client_text.index("void ArchipelagoClient::EnsureLocationScouts(", begin)
    literal_begin = client_text.index("static std::string ApMessageName(")
    literal_end = client_text.index("void ArchipelagoClient::DrainMessages(", literal_begin)
    methods = client_text[literal_begin:literal_end] + client_text[begin:end]
    save_begin = client_text.index("void ArchipelagoClient::LoadSaveMetadata(")
    save_end = client_text.index("void ArchipelagoClient::BeginItemReplay(", save_begin)
    prime_begin = client_text.index("void ArchipelagoClient::PrimeNewSaveMetadata(")
    prime_end = client_text.index("void ArchipelagoClient::PrepareNewSaveItemReplay(", prime_begin)

    with tempfile.TemporaryDirectory(prefix="soh-ap-hint-test-") as directory:
        work = Path(directory)
        (work / "nlohmann").mkdir()
        shutil.copyfile(dependency, work / "nlohmann/json.hpp")
        (work / "captured_hint_methods.inc").write_text(methods, encoding="utf-8")
        (work / "captured_save_metadata.inc").write_text(client_text[save_begin:save_end], encoding="utf-8")
        (work / "captured_prime_metadata.inc").write_text(client_text[prime_begin:prime_end], encoding="utf-8")
        executable = work / "archipelago_hint_data_tests"
        subprocess.run([
            compiler, "-std=c++20", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
            "-I", str(work), "-I", str(root), str(harness), "-o", str(executable),
        ], check=True)
        environment = os.environ.copy()
        # LeakSanitizer cannot enumerate processes in the isolated test runtime.
        environment["ASAN_OPTIONS"] = environment.get("ASAN_OPTIONS", "") + ":detect_leaks=0"
        environment["UBSAN_OPTIONS"] = environment.get("UBSAN_OPTIONS", "") + ":halt_on_error=1"
        command = [str(executable)]
        if args.reveal and args.bridge_fixture:
            command.append(str(args.bridge_fixture))
        result = subprocess.run(command, capture_output=True, text=True, env=environment)
        if result.returncode:
            raise SystemExit(result.stdout + result.stderr)
        report = json.loads(result.stdout)

    after = {str(path.relative_to(root)): digest(path) for path in paths}
    if before != after:
        raise SystemExit("Production or regression source changed while the test was running.")
    report.update({
        "scope": ("Complete production LoadSaveMetadata method; worker/engine IO isolated."
                  if args.save_metadata else
                  "Production target/header, reveal/snapshot/journal, and PrimeNewSaveMetadata methods; game/session IO isolated."
                  if args.reveal else
                  "Production AP hint-data header and native hint-description methods; game/session IO isolated."),
        "source_sha256": before,
        "source_unchanged_during_test": True,
        "json_header_sha256": digest(dependency),
        "sanitizers": ["address", "undefined"],
        "leak_sanitizer_enabled": False,
        "native_textbox_pagination_tested_here": False,
        "reveal_snapshot_journal_methods": args.reveal,
        "actual_prime_new_save_metadata": args.reveal,
        "save_metadata_worker_preservation": args.save_metadata,
    })
    rendered = json.dumps(report, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
