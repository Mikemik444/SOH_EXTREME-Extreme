"""Verify clean rebuilding after copying complete source files with old timestamps."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str], log: Path) -> str:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log.write_text(result.stdout, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}); see {log}: {result.stdout[-1400:]}")
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--helper", type=Path, default=ROOT / "delivery/SOH-EXTREME-1.8.4-source-files/BUILD_RELEASE.ps1")
    parser.add_argument("--cmake", type=Path, default=Path("/tmp/soh-entrance-build-cmake/cmake/data/bin/cmake"))
    parser.add_argument("--powershell", type=Path, default=ROOT / "runtime/powershell-7.6.7/bin/pwsh")
    parser.add_argument("--report", type=Path, default=ROOT / "tests/entrance_184_source_build_validation.json")
    args = parser.parse_args()
    fixture = Path(tempfile.mkdtemp(prefix="soh-source-build-"))
    os.environ.update({"XDG_CACHE_HOME": str(fixture / "powershell-cache"),
                       "XDG_CONFIG_HOME": str(fixture / "powershell-config"),
                       "XDG_DATA_HOME": str(fixture / "powershell-data")})
    package = fixture / "source-files"
    package.mkdir()
    shutil.copyfile(args.helper, package / "BUILD_RELEASE.ps1")
    header_relative = "soh/SohExtremeVersion.h"
    header_bytes = (ROOT / "source" / header_relative).read_bytes()
    assert b'"1.8.4"' in header_bytes
    manifest = {"version": "1.8.4", "build_helper_revision": 4, "files": [
        {"path": header_relative, "sha256": hashlib.sha256(header_bytes).hexdigest()}]}
    (package / "SOURCE_FILES.json").write_text(json.dumps(manifest), encoding="utf-8")
    originals = {}
    with zipfile.ZipFile(ROOT / "upload/haha.zip") as archive:
        originals["original_1_8_0"] = archive.read(header_relative)
    for version, archive_name in (("1_8_1", "SOH-EXTREME-1.8.1-coupled-entrances.zip"),
                                  ("1_8_2", "SOH-EXTREME-1.8.2-overworld-entrances.zip"),
                                  ("1_8_3", "SOH-EXTREME-1.8.3-spawn-placement.zip")):
        with zipfile.ZipFile(ROOT / "delivery" / archive_name) as archive:
            name = next(name for name in archive.namelist() if name.endswith("/payload/" + header_relative))
            originals["prior_" + version] = archive.read(name)
    originals["already_copied_current_sources_over_old_executable"] = originals["original_1_8_0"]
    cases = []
    for name, original_header in originals.items():
        case_root = fixture / name
        repository = case_root / "repository"
        header = repository / header_relative
        header.parent.mkdir(parents=True)
        header.write_bytes(original_header)
        marker = repository / "soh/Network/Archipelago/EntranceRuntime.inc"
        marker.parent.mkdir(parents=True)
        marker.write_text("// Fixture repository marker, not compiled.\n", encoding="utf-8")
        (repository / "CMakeLists.txt").write_text(
            "cmake_minimum_required(VERSION 3.15)\nproject(SourceBuildFixture LANGUAGES CXX)\n"
            "add_executable(soh version.cpp)\nset_target_properties(soh PROPERTIES SUFFIX \".exe\")\n", encoding="utf-8")
        (repository / "version.cpp").write_text(
            '#include <iostream>\n#include "soh/SohExtremeVersion.h"\n'
            'int main() { std::cout << SOH_EXTREME_VERSION << "\\n"; }\n', encoding="utf-8")
        build = repository / "build-vs"
        run([str(args.cmake), "-S", str(repository), "-B", str(build), "-G", "Unix Makefiles",
             "-DCMAKE_BUILD_TYPE=Release"], case_root / "configure.log")
        run([str(args.cmake), "--build", str(build), "--config", "Release", "--parallel", "8"], case_root / "initial-build.log")
        exe = build / "soh.exe"
        before = {"version": subprocess.check_output([str(exe)], text=True).strip(), "sha256": digest(exe)}
        header.write_bytes(header_bytes)
        # Recreate the extracted archive's preserved old source time. No
        # source timestamp manipulation is performed by the build helper.
        os.utime(header, (1_000_000_000, 1_000_000_000))
        before_source_time = header.stat().st_mtime_ns
        if name == "already_copied_current_sources_over_old_executable":
            run([str(args.cmake), "--build", str(build), "--config", "Release", "--parallel", "8"], case_root / "stale-incremental-build.log")
            assert digest(exe) == before["sha256"]
            assert subprocess.check_output([str(exe)], text=True).strip() == before["version"]
        result_path = case_root / "result.json"
        run([str(args.powershell), "-NoLogo", "-NoProfile", "-File",
             str(ROOT / "tests/entrance_184_source_build_probe.ps1"),
             "-PackageDirectory", str(package), "-RepositoryPath", str(repository),
             "-BuildDirectory", str(build), "-ResultPath", str(result_path)], case_root / "helper.log")
        result = json.loads(result_path.read_bytes())
        receipt = result["build_receipt"]
        assert result["build_exit_code"] == 0
        assert result["executable_version_output"] == "1.8.4" != before["version"]
        assert result["executable_sha256"] != before["sha256"]
        assert result["build_helper_sha256"] == digest(args.helper)
        assert result["source_copy_move_replace_calls"] == 0
        assert receipt["clean_first"] and receipt["all_native_sources_match_manifest"]
        assert receipt["game_executable"]["path"] == str(exe)
        assert receipt["game_executable"]["sha256"] == result["executable_sha256"]
        assert "--clean-first" in receipt["cmake_arguments"]
        assert header.stat().st_mtime_ns == before_source_time
        result.update({"name": name, "before": before,
                       "source_header_sha256": digest(header), "source_timestamp_unchanged": True,
                       "compiled_executable_changed": True, "build_log": str(case_root / "helper.log")})
        cases.append(result)
    # Exercise the newly introduced pre-build source checks against an actual
    # current APWorld, including the repository's legitimate ZIP repack case.
    preflight = []
    world_relative = "archipelago/soh_extreme.apworld"
    world = repository / world_relative
    world.parent.mkdir(parents=True, exist_ok=True)
    archive_bytes = (ROOT / "source" / world_relative).read_bytes()
    world.write_bytes(archive_bytes)
    with zipfile.ZipFile(world) as archive:
        contents = [{"path": entry.filename, "size_bytes": entry.file_size,
                     "sha256": hashlib.sha256(archive.read(entry)).hexdigest()}
                    for entry in archive.infolist() if not entry.is_dir()]
        stored = {entry.filename: archive.read(entry) for entry in archive.infolist() if not entry.is_dir()}
    manifest["files"].append({"path": world_relative, "sha256": hashlib.sha256(archive_bytes).hexdigest(),
                              "zip_contents": {"entries": contents}})
    (package / "SOURCE_FILES.json").write_text(json.dumps(manifest), encoding="utf-8")
    command = [str(args.powershell), "-NoLogo", "-NoProfile", "-File",
               str(ROOT / "tests/entrance_184_source_build_probe.ps1"), "-PackageDirectory", str(package),
               "-RepositoryPath", str(repository), "-BuildDirectory", str(build),
               "-ResultPath", str(fixture / "preflight-result.json"), "-VerifyOnly"]
    for name in ("exact_source_files", "same_apworld_contents_with_changed_zip_metadata", "changed_apworld_contents_rejected"):
        if name != "exact_source_files":
            with zipfile.ZipFile(world, "w", compression=zipfile.ZIP_STORED) as archive:
                for entry_name, data in reversed(list(stored.items())):
                    if name == "changed_apworld_contents_rejected" and entry_name == "archipelago.json":
                        data += b"\n "
                    info = zipfile.ZipInfo(entry_name, (2001, 2, 3, 4, 5, 6))
                    archive.writestr(info, data)
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (fixture / (name + ".log")).write_text(result.stdout, encoding="utf-8")
        if name == "changed_apworld_contents_rejected":
            assert result.returncode != 0 and "does not match version 1.8.4" in result.stdout, result.stdout
        else:
            assert result.returncode == 0, result.stdout
        preflight.append({"name": name, "status": "passed", "exit_code": result.returncode})
    report = {"status": "passed", "target_version": "1.8.4", "build_helper_revision": 4,
              "build_helper_sha256": digest(args.helper), "fixture_manifest_sha256": digest(package / "SOURCE_FILES.json"),
              "source_header_sha256": hashlib.sha256(header_bytes).hexdigest(),
              "cmake_version": subprocess.check_output([str(args.cmake), "--version"], text=True).splitlines()[0],
              "fixture_root": str(fixture), "cases": cases, "source_verification_cases": preflight,
              "full_game_built": False, "windows_execution": False,
              "scope": "Actual delivered helper functions with one real native version header in a minimal compiled CMake target."}
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(args.report), "cases": [
        {"name": case["name"], "before": case["before"]["version"], "after": case["executable_version_output"],
         "clean_first": case["build_receipt"]["clean_first"], "exe_discovery": case["build_receipt"]["game_executable"]["discovery"]}
        for case in cases]}, indent=2))


if __name__ == "__main__":
    main()
