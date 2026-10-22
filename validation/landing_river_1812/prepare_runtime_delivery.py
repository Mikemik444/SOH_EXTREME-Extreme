"""Build the cumulative 1.8.4 runtime-entrance and installer-rebuild package.

Historical deliveries are immutable input fixtures. Run --build-apworld,
validate the actual APWorld, then --prepare. --finalize requires the selected
release evidence, completed documentation, and all artifact hashes to agree.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import zipfile


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
VERSION = "1.8.4"
INSTALLER_REVISION = 4
PACKAGE = ROOT / "delivery/SOH-EXTREME-1.8.4-runtime-entrances"
PAYLOAD = PACKAGE / "payload"
PREVIOUS_PACKAGE = ROOT / "delivery/SOH-EXTREME-1.8.3-spawn-placement"
PREVIOUS_PACKAGES = (
    ROOT / "tests/installer_revision_1_reference.zip",
    ROOT / "delivery/SOH-EXTREME-1.8.1-coupled-entrances.zip",
    ROOT / "delivery/SOH-EXTREME-1.8.2-overworld-entrances.zip",
    ROOT / "delivery/SOH-EXTREME-1.8.3-spawn-placement.zip",
)
USER_YAML = ROOT / "upload/SOH-EXTREME(20261017-230302).yaml"
ADDITIONAL_PAYLOAD_PATHS = {
    "soh/Network/Archipelago/EntranceRouting.h",
    "soh/Network/Archipelago/ArchipelagoClient.h",
    "soh/SohGui/SohMenuNetwork.cpp",
    "tools/tests/test_entrance_settings.py",
    "tools/tests/test_entrance_slot_bridge.py",
    "tools/tests/entrance_slot_bridge_tests.cpp",
}
RELEASE_REPORT = "entrance_184_release_validation.json"
PACKAGING_REPORTS = (
    "entrance_184_apworld_validation.json",
    "entrance_184_tracker_version_validation.json",
    "entrance_184_installer_validation.json",
    "entrance_184_installer_build_validation.json",
    "entrance_184_yaml_validation.json",
    "entrance_184_generator_preservation.json",
)
VALIDATION_SCRIPTS = (
    "validate_apworld_archive.py",
    "entrance_184_validate_installer.ps1",
    "entrance_184_run_installer_validation.ps1",
    "entrance_184_reproduce_installer_build.py",
    "entrance_184_installer_build_probe.ps1",
)
HISTORICAL_REPORTS = (
    "spawn_183_full_fill_child.json",
    "spawn_183_full_fill_adult.json",
    "spawn_183_full_fill_child.log",
    "spawn_183_full_fill_adult.log",
    "spawn_183_generator_validation.json",
    "spawn_183_generator_regressions.log",
    "spawn_183_frontier_physical_guard_regression_child.json",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_files():
    return [path for path in sorted(SOURCE.rglob("*"))
            if path.is_file() and not any(part in {".git", "__pycache__"} for part in path.parts)
            and path.suffix != ".pyc"]


def version_values():
    root_manifest = json.loads((SOURCE / "archipelago/archipelago.json").read_bytes())
    world_manifest = json.loads((SOURCE / "archipelago/soh_extreme/archipelago.json").read_bytes())
    assert root_manifest == world_manifest
    assert root_manifest["world_version"] == VERSION
    assert root_manifest["version"] == root_manifest["compatible_version"] == 7
    tracker = (SOURCE / "archipelago/soh_extreme/TrackerMirror.py").read_text(encoding="utf-8")
    native = (SOURCE / "soh/SohExtremeVersion.h").read_text(encoding="utf-8")
    entrance = (SOURCE / "archipelago/soh_extreme/EntranceRandomizer.py").read_text(encoding="utf-8")
    assert re.search(r'^VERSION = "' + re.escape(VERSION) + r'"$', tracker, re.MULTILINE)
    assert re.search(r'^#define SOH_EXTREME_VERSION "' + re.escape(VERSION) + r'"$', native, re.MULTILINE)
    assert re.search(r'^REVISION = 1$', entrance, re.MULTILINE)


def deterministic_zip(archive: Path, files: dict[str, bytes]):
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for relative, data in sorted(files.items()):
            assert "\\" not in relative and not PurePosixPath(relative).is_absolute()
            assert ".." not in PurePosixPath(relative).parts
            info = zipfile.ZipInfo(relative, date_time=(2026, 10, 17, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            output.writestr(info, data, compresslevel=9)
    with zipfile.ZipFile(archive) as check:
        assert check.testzip() is None
        assert set(check.namelist()) == set(files)
        assert len(check.namelist()) == len(files)
        for name, data in files.items():
            assert check.read(name) == data


def build_apworld():
    version_values()
    world_root = SOURCE / "archipelago/soh_extreme"
    files = {path.relative_to(SOURCE / "archipelago").as_posix(): path.read_bytes()
             for path in source_files() if path.is_relative_to(world_root)}
    files["archipelago.json"] = (SOURCE / "archipelago/archipelago.json").read_bytes()
    archive = SOURCE / "archipelago/soh_extreme.apworld"
    deterministic_zip(archive, files)
    print(json.dumps({"stage": "apworld_built", "version": VERSION, "archive": str(archive),
                      "entries": len(files), "sha256": sha256(archive.read_bytes()),
                      "bytes": archive.stat().st_size}, indent=2))


def previous_payload_hashes():
    hashes: dict[str, set[str]] = {}
    for path in PREVIOUS_PACKAGES:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir() or "/payload/" not in info.filename:
                    continue
                relative = info.filename.split("/payload/", 1)[1]
                hashes.setdefault(relative, set()).add(sha256(archive.read(info)))
    return hashes


def accepted_apworld_contents():
    with zipfile.ZipFile(ROOT / "upload/haha.zip") as original:
        archives = [original.read("archipelago/soh_extreme.apworld")]
    for path in PREVIOUS_PACKAGES:
        with zipfile.ZipFile(path) as package:
            matches = [name for name in package.namelist()
                       if name.endswith("/payload/archipelago/soh_extreme.apworld")]
            assert len(matches) == 1
            archives.append(package.read(matches[0]))
    archives.append((SOURCE / "archipelago/soh_extreme.apworld").read_bytes())
    result = []
    seen = set()
    for data in archives:
        with zipfile.ZipFile(io.BytesIO(data)) as world:
            assert world.testzip() is None
            entries = [{"path": info.filename, "size_bytes": info.file_size,
                        "sha256": sha256(world.read(info))}
                       for info in sorted(world.infolist(), key=lambda info: info.filename)
                       if not info.is_dir()]
            assert len(entries) == len({entry["path"] for entry in entries})
        identity = tuple((entry["path"], entry["size_bytes"], entry["sha256"]) for entry in entries)
        if identity not in seen:
            seen.add(identity)
            result.append({"entries": entries})
    return result


def expected_payload_paths():
    previous = json.loads((PREVIOUS_PACKAGE / "manifest.json").read_bytes())
    assert previous["version"] == "1.8.3" and len(previous["files"]) == 27
    return {entry["path"] for entry in previous["files"]} | ADDITIONAL_PAYLOAD_PATHS


def build_manifest():
    previous = previous_payload_hashes()
    manifest = {"version": VERSION, "installer_revision": INSTALLER_REVISION, "files": []}
    with zipfile.ZipFile(ROOT / "upload/haha.zip") as original:
        names = set(original.namelist())
        for path in source_files():
            relative = path.relative_to(SOURCE).as_posix()
            after = path.read_bytes()
            before = original.read(relative) if relative in names else None
            if before == after:
                continue
            original_hash = sha256(before) if before is not None else None
            target_hash = sha256(after)
            entry = {"path": relative, "original_sha256": original_hash, "sha256": target_hash}
            earlier = sorted(previous.get(relative, set()) - {original_hash, target_hash})
            if earlier:
                entry["previous_sha256"] = earlier
            if relative == "archipelago/soh_extreme.apworld":
                entry["accepted_zip_contents"] = accepted_apworld_contents()
            manifest["files"].append(entry)
    actual = {entry["path"] for entry in manifest["files"]}
    expected = expected_payload_paths()
    assert actual == expected, {"unexpected": sorted(actual - expected), "missing": sorted(expected - actual)}
    return manifest


def verify_apworld(*, include_staged: bool):
    version_values()
    archive = SOURCE / "archipelago/soh_extreme.apworld"
    if include_staged:
        assert (PACKAGE / "soh_extreme.apworld").read_bytes() == archive.read_bytes()
    with zipfile.ZipFile(archive) as world:
        assert world.testzip() is None
        expected = {path.relative_to(SOURCE / "archipelago").as_posix(): path.read_bytes()
                    for path in source_files() if path.is_relative_to(SOURCE / "archipelago/soh_extreme")}
        expected["archipelago.json"] = (SOURCE / "archipelago/archipelago.json").read_bytes()
        assert set(world.namelist()) == set(expected)
        assert len(world.namelist()) == len(expected)
        for name, data in expected.items():
            assert world.read(name) == data, name


def verify_yaml():
    data = USER_YAML.read_bytes()
    output = PACKAGE / "SOH-EXTREME.yaml"
    if output.exists():
        assert output.read_bytes() == data
    else:
        output.write_bytes(data)
    report = {"status": "passed", "target_version": VERSION, "method": "byte_for_byte_equality",
              "sha256": sha256(data), "source": USER_YAML.name,
              "settings_changed": False, "source_bytes": len(data)}
    (ROOT / "tests/entrance_184_yaml_validation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def verify_generator_preservation():
    checked = {}
    version_changes = {}
    with zipfile.ZipFile(PREVIOUS_PACKAGE / "soh_extreme.apworld") as previous:
        with zipfile.ZipFile(SOURCE / "archipelago/soh_extreme.apworld") as current:
            assert set(previous.namelist()) == set(current.namelist())
            for name in current.namelist():
                old = previous.read(name)
                new = current.read(name)
                if old == new:
                    checked[name] = sha256(new)
                else:
                    assert name in {"archipelago.json", "soh_extreme/archipelago.json", "soh_extreme/TrackerMirror.py"}, name
                    assert old.replace(b'1.8.3', b'1.8.4') == new, name
                    version_changes[name] = {"before_sha256": sha256(old), "after_sha256": sha256(new)}
    historical = {name: sha256((PREVIOUS_PACKAGE / "validation" / name).read_bytes())
                  for name in HISTORICAL_REPORTS}
    report = {"status": "passed", "target_version": VERSION, "reference_version": "1.8.3",
              "method": "exact_package_contents_comparison_except_three_release_labels",
              "unchanged_package_files": checked, "release_label_changes": version_changes,
              "historical_report_sha256": historical, "new_full_fills_run": False,
              "conclusion": "Generator logic and resources are identical to the previously fully filled 1.8.3 release."}
    (ROOT / "tests/entrance_184_generator_preservation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def prepare():
    PACKAGE.mkdir(parents=True, exist_ok=True)
    verify_apworld(include_staged=False)
    verify_yaml()
    verify_generator_preservation()
    manifest = build_manifest()
    expected = {entry["path"] for entry in manifest["files"]}
    if PAYLOAD.exists():
        actual = {p.relative_to(PAYLOAD).as_posix() for p in PAYLOAD.rglob("*") if p.is_file()}
        assert actual <= expected, {"stale_payload_files": sorted(actual - expected)}
    for entry in manifest["files"]:
        target = PAYLOAD / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / entry["path"], target)
    (PACKAGE / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(SOURCE / "archipelago/soh_extreme.apworld", PACKAGE / "soh_extreme.apworld")
    print(json.dumps({"stage": "prepared", "version": VERSION, "payload_file_count": len(expected),
                      "supported_previous_packages": [path.name for path in PREVIOUS_PACKAGES],
                      "paths": sorted(expected)}, indent=2))


def read_report(name: str):
    assert Path(name).name == name
    return json.loads((ROOT / "tests" / name).read_text(encoding="utf-8-sig"))


def finalize():
    verify_apworld(include_staged=True)
    verify_yaml()
    verify_generator_preservation()
    manifest = build_manifest()
    assert manifest == json.loads((PACKAGE / "manifest.json").read_bytes())
    for entry in manifest["files"]:
        assert sha256((PAYLOAD / entry["path"]).read_bytes()) == entry["sha256"], entry["path"]
    release = read_report(RELEASE_REPORT)
    assert release["status"] == "passed" and release["world_version"] == VERSION
    expected_hashes = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
    assert release["source_sha256"] == expected_hashes
    assert release["native_windows_build_or_gameplay_run"] is False
    evidence_names = release["evidence_files"]
    assert evidence_names and len(evidence_names) == len(set(evidence_names))
    reports = {name: read_report(name) for name in PACKAGING_REPORTS}
    assert all(report["status"] == "passed" for report in reports.values())
    installer = reports["entrance_184_installer_validation.json"]
    assert installer["target_version"] == VERSION and installer["payload_file_count"] == len(manifest["files"])
    assert installer["installer_sha256"] == sha256((PACKAGE / "APPLY_AND_BUILD.ps1").read_bytes())
    assert installer["manifest_sha256"] == sha256((PACKAGE / "manifest.json").read_bytes())
    build = reports["entrance_184_installer_build_validation.json"]
    assert build["target_version"] == VERSION and len(build["cases"]) >= 5
    for case in build["cases"]:
        assert case["installer_build_exit_code"] == 0
        assert case["executable_version_output"] == VERSION
        assert case["installer_sha256"] == installer["installer_sha256"]
        assert case["manifest_sha256"] == installer["manifest_sha256"]
        assert case["native_header_sha256_verified"] and not case["same_executable_bytes"]
        receipt = case["build_receipt"]
        assert receipt["clean_first"] and receipt["all_native_sources_match_payload"]
        assert receipt["game_executable"]["sha256"] == case["executable_sha256"]
    archive_hash = sha256((SOURCE / "archipelago/soh_extreme.apworld").read_bytes())
    for name in ("entrance_184_apworld_validation.json", "entrance_184_tracker_version_validation.json"):
        assert reports[name]["archive_sha256"] == archive_hash
    assert set(reports["entrance_184_tracker_version_validation.json"]["versions"].values()) == {VERSION}
    assert reports["entrance_184_yaml_validation.json"]["sha256"] == sha256(USER_YAML.read_bytes())
    for name in ("README.txt", "VALIDATION.txt"):
        prose = (PACKAGE / name).read_text(encoding="utf-8")
        assert len(prose) > 1000 and "DRAFT_" not in prose
    selected = {RELEASE_REPORT, *PACKAGING_REPORTS, *VALIDATION_SCRIPTS, *evidence_names}
    for name in selected:
        assert Path(name).name == name
        assert (ROOT / "tests" / name).is_file(), name
    report_dir = PACKAGE / "validation"
    expected_validation_paths = selected | {"previous_1_8_3/" + name for name in HISTORICAL_REPORTS}
    existing = {path.relative_to(report_dir).as_posix() for path in report_dir.rglob("*") if path.is_file()}
    assert existing <= expected_validation_paths, {"unselected_validation_files": sorted(existing - expected_validation_paths)}
    report_dir.mkdir(exist_ok=True)
    for name in sorted(selected):
        shutil.copyfile(ROOT / "tests" / name, report_dir / name)
    historical = report_dir / "previous_1_8_3"
    historical.mkdir(exist_ok=True)
    for name in HISTORICAL_REPORTS:
        shutil.copyfile(PREVIOUS_PACKAGE / "validation" / name, historical / name)
    files = {path.relative_to(PACKAGE.parent).as_posix(): path.read_bytes()
             for path in sorted(PACKAGE.rglob("*")) if path.is_file()}
    assert all("__pycache__" not in name and not name.endswith(".pyc") for name in files)
    archive = PACKAGE.parent / (PACKAGE.name + ".zip")
    deterministic_zip(archive, files)
    print(json.dumps({"stage": "verified", "archive": str(archive), "bytes": archive.stat().st_size,
                      "sha256": sha256(archive.read_bytes()), "replacement_files": len(manifest["files"]),
                      "package_files": len(files)}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    stage = parser.add_mutually_exclusive_group(required=True)
    stage.add_argument("--build-apworld", action="store_true")
    stage.add_argument("--prepare", action="store_true")
    stage.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    if args.build_apworld:
        build_apworld()
    elif args.prepare:
        prepare()
    else:
        finalize()
