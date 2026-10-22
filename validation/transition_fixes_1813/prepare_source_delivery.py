"""Prepare complete edited source files directly in their original folder paths.

The final ZIP has top-level soh/, archipelago/, and tools/ directories. It has
no payload tree, source-copy installer, or patch-application step. BUILD_RELEASE
only verifies the copied source files and clean-rebuilds an existing CMake
configuration. Earlier deliveries remain immutable reference artifacts.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import zipfile

import prepare_runtime_delivery as base


ROOT = base.ROOT
SOURCE = base.SOURCE
VERSION = base.VERSION
PACKAGE = ROOT / "delivery/SOH-EXTREME-1.8.4-source-files"
MANIFEST = PACKAGE / "SOURCE_FILES.json"
PREVIOUS_PACKAGE = base.PREVIOUS_PACKAGE
USER_YAML = base.USER_YAML
RELEASE_REPORT = "entrance_184_release_validation.json"
PACKAGING_REPORTS = (
    "entrance_184_apworld_validation.json",
    "entrance_184_tracker_version_validation.json",
    "entrance_184_source_build_validation.json",
    "entrance_184_yaml_validation.json",
    "entrance_184_generator_scope.json",
    "entrance_184_source_completeness.json",
    "entrance_184_source_zip_validation.json",
)
PACKAGE_CREATION_REPORT = "entrance_184_package_creation.json"
PACKAGE_VERIFICATION_REPORT = "entrance_184_package_validation.json"
VALIDATION_SCRIPTS = (
    "validate_apworld_archive.py",
    "entrance_184_validate_source_build.py",
    "entrance_184_source_build_probe.ps1",
    "entrance_184_validate_source_zip.py",
)
HISTORICAL_REPORTS = base.HISTORICAL_REPORTS

# Extend this set only with actual reviewed source changes for this release.
ADDITIONAL_SOURCE_PATHS: set[str] = {
    "archipelago/soh_extreme/DungeonLocationRoutes.json",
    "archipelago/soh_extreme/EnemyRoomGraph.json",
    "soh/Enhancements/randomizer/location_access/dungeons/jabujabus_belly.cpp",
    "soh/Network/Archipelago/SceneTransitionChecks.h",
    "tools/tests/test_jabu_carry.py",
}


def configure_base():
    base.PACKAGE = PACKAGE
    base.PAYLOAD = PACKAGE
    base.ADDITIONAL_PAYLOAD_PATHS.update(ADDITIONAL_SOURCE_PATHS)


def source_manifest():
    configure_base()
    complete = base.build_manifest()
    result = {"version": VERSION, "layout": "complete_source_files",
              "build_helper_revision": 4, "files": []}
    for entry in complete["files"]:
        source = SOURCE / entry["path"]
        row = {"path": entry["path"], "size_bytes": source.stat().st_size, "sha256": entry["sha256"]}
        if entry["path"] == "archipelago/soh_extreme.apworld":
            # This current content snapshot alone permits metadata-only ZIP
            # repacking by the repository's normal CMake packaging target.
            row["zip_contents"] = entry["accepted_zip_contents"][-1]
        result["files"].append(row)
    return result


def source_completeness(manifest: dict):
    """Independently compare the complete source tree with the original ZIP.

    This includes unchanged production files in the comparison without adding
    them to the replacement-files deliverable. Missing original source files
    and any unmanifested modification fail the audit.
    """
    original_path = ROOT / "upload/haha.zip"
    current_paths = {path.relative_to(SOURCE).as_posix(): path
                     for path in base.source_files()}

    def ignored(relative: str):
        path = PurePosixPath(relative)
        return any(part in {".git", "__pycache__"} for part in path.parts) or path.suffix == ".pyc"

    changed = {}
    unchanged_count = 0
    with zipfile.ZipFile(original_path) as original:
        original_files = [info.filename for info in original.infolist()
                          if not info.is_dir() and not ignored(info.filename)]
        assert len(original_files) == len(set(original_files)), "Duplicate original source paths"
        original_names = set(original_files)
        missing_original = original_names - set(current_paths)
        assert not missing_original, {"removed_original_source_files": sorted(missing_original)}
        for relative, path in current_paths.items():
            before = original.read(relative) if relative in original_names else None
            after = path.read_bytes()
            if before == after:
                unchanged_count += 1
                continue
            changed[relative] = {
                "change": "modified" if before is not None else "added",
                "original_sha256": base.sha256(before) if before is not None else None,
                "sha256": base.sha256(after),
                "size_bytes": len(after),
            }
    expected = {entry["path"]: entry for entry in manifest["files"]}
    assert set(changed) == set(expected), {
        "unmanifested_source_changes": sorted(set(changed) - set(expected)),
        "manifested_files_without_a_source_change": sorted(set(expected) - set(changed)),
    }
    for relative, change in changed.items():
        assert change["sha256"] == expected[relative]["sha256"], {"manifest_source_hash_mismatch": relative}
        assert change["size_bytes"] == expected[relative]["size_bytes"], {"manifest_source_size_mismatch": relative}
    production = {name: row for name, row in changed.items() if not name.startswith("tools/tests/")}
    regression_tests = {name: row for name, row in changed.items() if name.startswith("tools/tests/")}
    report = {
        "status": "passed",
        "world_version": VERSION,
        "method": "byte_for_byte_comparison_of_every_original_and_current_source_file",
        "original_archive": original_path.name,
        "original_archive_sha256": base.sha256(original_path.read_bytes()),
        "original_files_compared": len(original_names),
        "current_files_compared": len(current_paths),
        "unchanged_files": unchanged_count,
        "complete_changed_source_files": len(changed),
        "changed_production_files": production,
        "changed_regression_test_files": regression_tests,
        "source_sha256": {name: row["sha256"] for name, row in changed.items()},
        "missing_original_files": [],
        "unmanifested_source_changes": [],
        "manifest_covers_every_modified_or_added_source_file": True,
        "exclusions": {
            "path_components": [".git", "__pycache__"],
            "suffixes": [".pyc"],
            "scope": "Only source-tree version-control and Python cache intermediates are excluded. Native harness dependencies and report intermediates are outside the source tree.",
        },
    }
    (ROOT / "tests/entrance_184_source_completeness.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def write_source_archive(archive: Path, files: dict[str, bytes], created: datetime):
    """Write fresh source timestamps; clean-first remains the rebuild guarantee."""
    assert created.tzinfo is not None and created.utcoffset().total_seconds() == 0
    stamp = (created.year, created.month, created.day, created.hour, created.minute, created.second // 2 * 2)
    unix_seconds = int(created.timestamp())
    filetime = (unix_seconds + 11_644_473_600) * 10_000_000
    # Standard UTC and NTFS metadata avoids relying on a DOS timestamp's
    # timezone interpretation when the extractor supports these extra fields.
    timestamp_extra = struct.pack("<HHBI", 0x5455, 5, 1, unix_seconds)
    timestamp_extra += struct.pack("<HHIHHQQQ", 0x000A, 32, 0, 1, 24, filetime, filetime, filetime)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for relative, data in sorted(files.items()):
            path = PurePosixPath(relative)
            assert "\\" not in relative and not path.is_absolute() and ".." not in path.parts
            info = zipfile.ZipInfo(relative, date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.extra = timestamp_extra
            output.writestr(info, data, compresslevel=9)
    with zipfile.ZipFile(archive) as check:
        assert check.testzip() is None
        assert set(check.namelist()) == set(files) and len(check.namelist()) == len(files)
        assert all(info.date_time == stamp for info in check.infolist())
        assert all(info.extra == timestamp_extra for info in check.infolist())
        for relative, data in files.items():
            assert check.read(relative) == data, relative
    return stamp


def generator_scope():
    unchanged = {}
    labels = {}
    changed = {}
    with zipfile.ZipFile(PREVIOUS_PACKAGE / "soh_extreme.apworld") as previous:
        with zipfile.ZipFile(SOURCE / "archipelago/soh_extreme.apworld") as current:
            old_names = set(previous.namelist())
            new_names = set(current.namelist())
            for name in sorted(old_names | new_names):
                old = previous.read(name) if name in old_names else None
                new = current.read(name) if name in new_names else None
                if old == new:
                    unchanged[name] = base.sha256(new)
                elif name in {"archipelago.json", "soh_extreme/archipelago.json", "soh_extreme/TrackerMirror.py"}:
                    assert old is not None and new is not None and old.replace(b"1.8.3", b"1.8.4") == new, name
                    labels[name] = {"before_sha256": base.sha256(old), "after_sha256": base.sha256(new)}
                else:
                    changed[name] = {"before_sha256": base.sha256(old) if old is not None else None,
                                     "after_sha256": base.sha256(new) if new is not None else None}
    historical = {name: base.sha256((PREVIOUS_PACKAGE / "validation" / name).read_bytes())
                  for name in HISTORICAL_REPORTS}
    report = {"status": "passed", "target_version": VERSION, "reference_version": "1.8.3",
              "method": "exact_archive_content_comparison_with_every_logic_change_identified",
              "unchanged_package_files": unchanged, "release_label_changes": labels,
              "changed_logic_or_resource_files": changed, "historical_report_sha256": historical,
              "historical_full_fill_scope": "The included 1.8.3 full fills remain historical evidence for that exact release; current changes require current test evidence."}
    (ROOT / "tests/entrance_184_generator_scope.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def prepare():
    configure_base()
    PACKAGE.mkdir(parents=True, exist_ok=True)
    base.verify_apworld(include_staged=False)
    base.verify_yaml()
    generator_scope()
    manifest = source_manifest()
    source_completeness(manifest)
    expected_sources = {entry["path"] for entry in manifest["files"]}
    for directory in ("soh", "archipelago", "tools"):
        actual = {path.relative_to(PACKAGE).as_posix() for path in (PACKAGE / directory).rglob("*") if path.is_file()}
        assert actual <= expected_sources, {"unexpected_source_files": sorted(actual - expected_sources)}
    for entry in manifest["files"]:
        target = PACKAGE / entry["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SOURCE / entry["path"], target)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(SOURCE / "archipelago/soh_extreme.apworld", PACKAGE / "soh_extreme.apworld")
    assert not (PACKAGE / "payload").exists()
    assert not (PACKAGE / "APPLY_AND_BUILD.ps1").exists()
    print(json.dumps({"stage": "prepared", "version": VERSION, "layout": manifest["layout"],
                      "complete_source_files": len(manifest["files"]), "paths": sorted(expected_sources)}, indent=2))


def verify_source_hashes(report: dict, report_name: str):
    for relative, expected in report.get("source_sha256", {}).items():
        path = SOURCE / relative
        if not path.is_file():
            path = SOURCE / "archipelago/soh_extreme" / relative
        assert path.is_file(), {"report": report_name, "missing_source": relative}
        assert base.sha256(path.read_bytes()) == expected, {"report": report_name, "stale_source": relative}


def finalize():
    configure_base()
    base.verify_apworld(include_staged=True)
    base.verify_yaml()
    scope = generator_scope()
    manifest = source_manifest()
    completeness = source_completeness(manifest)
    assert manifest == json.loads(MANIFEST.read_bytes())
    expected_hashes = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
    for relative, expected in expected_hashes.items():
        assert base.sha256((PACKAGE / relative).read_bytes()) == expected, relative
    release = base.read_report(RELEASE_REPORT)
    assert release["status"] == "passed" and release["world_version"] == VERSION
    assert release["source_sha256"] == expected_hashes
    assert release["layout"] == "complete_source_files"
    assert release["native_windows_build_or_gameplay_run"] is False
    evidence_names = release["evidence_files"]
    assert evidence_names and len(evidence_names) == len(set(evidence_names))
    assert set(release["evidence_sha256"]) == set(evidence_names)
    fixture_provenance = set(release.get("fixture_provenance_files", []))
    assert fixture_provenance <= {"entrance_184_bridge_child_report.json", "entrance_184_bridge_adult_report.json"}
    assert fixture_provenance <= set(evidence_names)
    for name in evidence_names:
        assert Path(name).name == name
        assert base.sha256((ROOT / "tests" / name).read_bytes()) == release["evidence_sha256"][name], {
            "changed_release_evidence": name,
        }
        if name.endswith(".json"):
            evidence = base.read_report(name)
            if isinstance(evidence, dict) and name not in fixture_provenance:
                verify_source_hashes(evidence, name)
    reports = {name: base.read_report(name) for name in PACKAGING_REPORTS}
    assert set(release["packaging_evidence_sha256"]) == set(PACKAGING_REPORTS)
    for name in PACKAGING_REPORTS:
        assert base.sha256((ROOT / "tests" / name).read_bytes()) == release["packaging_evidence_sha256"][name], {
            "changed_packaging_evidence": name,
        }
    assert all(report["status"] == "passed" for report in reports.values())
    source_zip = reports["entrance_184_source_zip_validation.json"]
    assert source_zip["source_zip_writer_sha256"] == base.sha256(inspect.getsource(write_source_archive).encode())
    assert len(source_zip["cases"]) == 3 and source_zip["central_utc_and_ntfs_fields_verified"]
    assert all(case["matches_package_creation_time"] and case["content_preserved"]
               and case["exit_code"] == 0 for case in source_zip["cases"])
    build = reports["entrance_184_source_build_validation.json"]
    assert build["target_version"] == VERSION and len(build["cases"]) >= 5
    assert build["build_helper_sha256"] == base.sha256((PACKAGE / "BUILD_RELEASE.ps1").read_bytes())
    assert build["source_header_sha256"] == base.sha256((SOURCE / "soh/SohExtremeVersion.h").read_bytes())
    for case in build["cases"]:
        assert case["build_exit_code"] == 0 and case["executable_version_output"] == VERSION
        assert case["compiled_executable_changed"] and case["source_timestamp_unchanged"]
        assert case["source_copy_move_replace_calls"] == 0
        receipt = case["build_receipt"]
        assert receipt["clean_first"] and receipt["all_native_sources_match_manifest"]
        assert receipt["game_executable"]["sha256"] == case["executable_sha256"]
    archive_hash = base.sha256((SOURCE / "archipelago/soh_extreme.apworld").read_bytes())
    for name in ("entrance_184_apworld_validation.json", "entrance_184_tracker_version_validation.json"):
        assert reports[name]["archive_sha256"] == archive_hash
    assert set(reports["entrance_184_tracker_version_validation.json"]["versions"].values()) == {VERSION}
    assert reports["entrance_184_yaml_validation.json"]["sha256"] == base.sha256(USER_YAML.read_bytes())
    assert release["changed_generator_files"] == scope["changed_logic_or_resource_files"]
    for name in ("README.txt", "VALIDATION.txt"):
        prose = (PACKAGE / name).read_text(encoding="utf-8")
        assert len(prose) > 1000 and "DRAFT_" not in prose
    created = datetime.now(timezone.utc).replace(microsecond=0)
    created_text = created.isoformat().replace("+00:00", "Z")
    stamp = (created.year, created.month, created.day, created.hour, created.minute, created.second // 2 * 2)
    creation_report = {
        "world_version": VERSION,
        "package_created_utc": created_text,
        "zip_entry_datetime_utc_components": list(stamp),
        "zip_timestamp_resolution_seconds": 2,
        "utc_modification_timestamp": int(created.timestamp()),
        "extra_timestamp_fields": ["0x5455 UTC modification time", "0x000A NTFS modification/access/creation times"],
        "timestamp_policy": "Every outer source-bundle entry uses this package creation time; the APWorld's internal deterministic metadata is unchanged.",
        "build_requirement": "cmake --build build-vs --config Release --parallel 8 --clean-first",
    }
    (ROOT / "tests" / PACKAGE_CREATION_REPORT).write_text(json.dumps(creation_report, indent=2) + "\n", encoding="utf-8")
    selected = {RELEASE_REPORT, PACKAGE_CREATION_REPORT, *PACKAGING_REPORTS, *VALIDATION_SCRIPTS, *evidence_names}
    for name in selected:
        assert Path(name).name == name and (ROOT / "tests" / name).is_file(), name
    report_dir = PACKAGE / "validation"
    expected_validation_paths = selected | {"previous_1_8_3/" + name for name in HISTORICAL_REPORTS}
    existing = {path.relative_to(report_dir).as_posix() for path in report_dir.rglob("*") if path.is_file()}
    assert existing <= expected_validation_paths, {"unselected_evidence": sorted(existing - expected_validation_paths)}
    report_dir.mkdir(exist_ok=True)
    for name in sorted(selected):
        shutil.copyfile(ROOT / "tests" / name, report_dir / name)
    historical = report_dir / "previous_1_8_3"
    historical.mkdir(exist_ok=True)
    for name in HISTORICAL_REPORTS:
        shutil.copyfile(PREVIOUS_PACKAGE / "validation" / name, historical / name)
    expected_files = set(expected_hashes) | {
        "BUILD_RELEASE.cmd", "BUILD_RELEASE.ps1", "SOURCE_FILES.json", "README.txt", "VALIDATION.txt",
        "SOH-EXTREME.yaml", "soh_extreme.apworld",
    } | {"validation/" + name for name in expected_validation_paths}
    files = {path.relative_to(PACKAGE).as_posix(): path.read_bytes()
             for path in sorted(PACKAGE.rglob("*")) if path.is_file()}
    assert set(files) == expected_files, {"unexpected": sorted(set(files) - expected_files), "missing": sorted(expected_files - set(files))}
    assert all("__pycache__" not in name and not name.endswith(".pyc") for name in files)
    assert all(not name.startswith("payload/") and "APPLY_AND_BUILD" not in name for name in files)
    archive = PACKAGE.parent / (PACKAGE.name + ".zip")
    assert write_source_archive(archive, files, created) == stamp
    final_report = {
        "status": "passed", "stage": "verified", "world_version": VERSION,
        "archive": str(archive), "bytes": archive.stat().st_size,
        "sha256": base.sha256(archive.read_bytes()), "complete_source_files": len(expected_hashes),
        "package_files": len(files), "layout": "direct_original_source_folders",
        "package_created_utc": created_text,
        "zip_entry_datetime_utc_components": list(stamp),
        "all_outer_zip_timestamps_use_package_creation_time": True,
        "utc_and_ntfs_timestamp_metadata_verified": True,
        "all_zip_entries_and_crcs_verified": True,
        "source_completeness_report_sha256": base.sha256((ROOT / "tests/entrance_184_source_completeness.json").read_bytes()),
        "manifest_covers_every_modified_or_added_source_file": completeness["manifest_covers_every_modified_or_added_source_file"],
        "source_sha256": expected_hashes,
        "package_file_sha256": {name: base.sha256(data) for name, data in files.items()},
        "native_windows_build_or_gameplay_run": False,
    }
    (ROOT / "tests" / PACKAGE_VERIFICATION_REPORT).write_text(json.dumps(final_report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in final_report.items()
                      if key not in {"source_sha256", "package_file_sha256"}}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    stage = parser.add_mutually_exclusive_group(required=True)
    stage.add_argument("--build-apworld", action="store_true")
    stage.add_argument("--prepare", action="store_true")
    stage.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    if args.build_apworld:
        base.build_apworld()
    elif args.prepare:
        prepare()
    else:
        finalize()
