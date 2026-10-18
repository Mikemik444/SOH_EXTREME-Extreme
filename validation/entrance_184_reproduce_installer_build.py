"""Reproduce archive timestamp stale builds using actual installer functions.

Uses the real old/delivered native version header in a minimal C++ executable,
the shipped installer PowerShell functions, and a real configured CMake build.
All working files are confined to a new temporary fixture directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def unpack_preserving_times(archive: Path, destination: Path, *, root_prefix: str = "") -> None:
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            if info.is_dir() or not info.filename.startswith(root_prefix):
                continue
            relative = info.filename[len(root_prefix):]
            if not relative:
                continue
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zf.read(info))
            timestamp = time.mktime((*info.date_time, 0, 0, -1))
            os.utime(target, (timestamp, timestamp))


def run(command: list[str], *, log: Path) -> str:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log.write_text(result.stdout, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}); see {log}: {result.stdout[-1200:]}")
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=ROOT / "delivery/SOH-EXTREME-1.8.3-spawn-placement.zip")
    parser.add_argument("--cmake", type=Path, default=Path("/tmp/soh-entrance-build-cmake/cmake/data/bin/cmake"))
    parser.add_argument("--powershell", type=Path, default=ROOT / "runtime/powershell-7.6.7/bin/pwsh")
    parser.add_argument("--report", type=Path, default=ROOT / "tests/entrance_184_installer_timestamp_reproduction.json")
    parser.add_argument("--expect", choices=("stale", "fresh"), default="stale")
    args = parser.parse_args()
    fixture = Path(tempfile.mkdtemp(prefix="soh-installer-build-"))
    # PowerShell's standard XDG runtime directories must stay inside this
    # disposable fixture when the container user profile is read-only.
    os.environ["XDG_CACHE_HOME"] = str(fixture / "powershell-cache")
    os.environ["XDG_CONFIG_HOME"] = str(fixture / "powershell-config")
    os.environ["XDG_DATA_HOME"] = str(fixture / "powershell-data")
    unpack_preserving_times(args.package, fixture / "unpacked")
    package = next(path.parent for path in (fixture / "unpacked").rglob("manifest.json"))
    manifest = json.loads((package / "manifest.json").read_bytes())
    cases = []
    previous = {
        "original": None,
        "prior_1_8_1": ROOT / "delivery/SOH-EXTREME-1.8.1-coupled-entrances.zip",
        "prior_1_8_2": ROOT / "delivery/SOH-EXTREME-1.8.2-overworld-entrances.zip",
        "already_matching_sources_with_old_executable": None,
    }
    if manifest["version"] != "1.8.3":
        previous["prior_1_8_3"] = ROOT / "delivery/SOH-EXTREME-1.8.3-spawn-placement.zip"
    with zipfile.ZipFile(ROOT / "upload/haha.zip") as original:
        for name, prior in previous.items():
            case_root = fixture / name
            repository = case_root / "repository"
            repository.mkdir(parents=True)
            for entry in manifest["files"]:
                if entry["original_sha256"] is None:
                    continue
                target = repository / entry["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(original.read(entry["path"]))
            if prior is not None:
                with zipfile.ZipFile(prior) as archive:
                    for info in archive.infolist():
                        if info.is_dir() or "/payload/" not in info.filename:
                            continue
                        target = repository / info.filename.split("/payload/", 1)[1]
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(archive.read(info))
            (repository / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.15)\nproject(InstallerFixture LANGUAGES CXX)\n"
                "add_executable(soh version.cpp)\nset_target_properties(soh PROPERTIES SUFFIX \".exe\")\n",
                encoding="utf-8",
            )
            (repository / "version.cpp").write_text(
                '#include <iostream>\n#include "soh/SohExtremeVersion.h"\n'
                'int main() { std::cout << SOH_EXTREME_VERSION << "\\n"; }\n',
                encoding="utf-8",
            )
            build = repository / "build-vs"
            run([str(args.cmake), "-S", str(repository), "-B", str(build), "-G", "Unix Makefiles",
                 "-DCMAKE_BUILD_TYPE=Release"], log=case_root / "configure.log")
            run([str(args.cmake), "--build", str(build), "--config", "Release", "--parallel", "8"],
                log=case_root / "initial_build.log")
            exe = build / "soh.exe"
            before = {"version": subprocess.check_output([str(exe)], text=True).strip(),
                      "sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
                      "mtime_ns": exe.stat().st_mtime_ns}
            if name == "already_matching_sources_with_old_executable":
                for entry in manifest["files"]:
                    target = repository / entry["path"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(package / "payload" / entry["path"], target)
            result_path = case_root / "installer_result.json"
            run([str(args.powershell), "-NoLogo", "-NoProfile", "-File",
                 str(ROOT / "tests/entrance_184_installer_build_probe.ps1"),
                 "-PackageDirectory", str(package), "-RepositoryPath", str(repository),
                 "-BuildDirectory", str(build), "-ResultPath", str(result_path)],
                log=case_root / "installer.log")
            result = json.loads(result_path.read_bytes())
            result.update({"name": name, "before": before,
                           "native_header_sha256_verified": hashlib.sha256(
                               (repository / "soh/SohExtremeVersion.h").read_bytes()).hexdigest() == next(
                                   entry["sha256"] for entry in manifest["files"]
                                   if entry["path"] == "soh/SohExtremeVersion.h"),
                           "same_executable_bytes": before["sha256"] == result["executable_sha256"],
                           "build_log": str(case_root / "installer.log")})
            if args.expect == "stale":
                assert result["executable_version_output"] == before["version"] != manifest["version"], result
                assert result["same_executable_bytes"], result
            else:
                assert result["executable_version_output"] == manifest["version"] != before["version"], result
                assert not result["same_executable_bytes"], result
                receipt = result["build_receipt"]
                assert receipt and receipt["clean_first"] and receipt["all_native_sources_match_payload"], result
                assert "--clean-first" in receipt["cmake_arguments"], receipt
                assert receipt["game_executable"]["path"] == str(exe), receipt
                assert receipt["game_executable"]["sha256"] == result["executable_sha256"], receipt
                assert receipt["game_executable"]["modified_during_build"], receipt
            cases.append(result)
    report = {"status": "reproduced" if args.expect == "stale" else "passed",
              "package": str(args.package), "package_sha256": hashlib.sha256(args.package.read_bytes()).hexdigest(),
              "target_version": manifest["version"], "expected": args.expect,
              "cmake_version": subprocess.check_output([str(args.cmake), "--version"], text=True).splitlines()[0],
              "fixture_root": str(fixture), "cases": cases}
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(args.report), "cases": [
        {"name": result["name"], "build_exit": result["installer_build_exit_code"],
         "compiled_before": result["before"]["version"], "compiled_after": result["executable_version_output"],
         "source_modified": result["source_last_write_utc"], "exe_modified": result["executable_last_write_utc"],
         "source_hash_matches_package": result["native_header_sha256_verified"]} for result in cases]}, indent=2))


if __name__ == "__main__":
    main()
