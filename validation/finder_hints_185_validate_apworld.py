"""Load the release APWorld through the official loader without a loose world.

This is an isolated import/resource smoke test; it does not generate or fill.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile


def probe(args):
    import ModuleUpdate
    ModuleUpdate.update_ran = True
    import settings
    settings.no_gui = True
    settings.skip_autosave = True

    import importlib
    from importlib.resources import files
    import pkgutil
    import zipimport
    import Utils
    import worlds
    from worlds.AutoWorld import AutoWorldRegister

    package = importlib.import_module("worlds.soh_extreme")
    module_names = (
        "EntranceRandomizer", "EntranceOptions", "NpcSpeech", "SceneTransitions",
        "EnemyRoomLogic", "SilverRoomLogic", "FrontierFill", "TrackerMirror", "CheckDescriptions", "_vendor_oot_soh",
    )
    modules = {name: importlib.import_module(f"worlds.soh_extreme.{name}")
               for name in module_names}
    modules["__init__"] = package
    for name, module in modules.items():
        assert isinstance(module.__loader__, zipimport.zipimporter), (name, module.__loader__)
        assert ".apworld/soh_extreme/" in module.__file__, (name, module.__file__)
    assert not worlds.failed_world_loads, worlds.failed_world_loads
    assert AutoWorldRegister.world_types["SOH-EXTREME"] is package.SohExtremeWorld
    assert tuple(package.SohExtremeWorld.world_version) == tuple(int(part) for part in args.expected_version.split('.'))
    sources = [source for source in worlds.world_sources
               if Path(source.path).name == "soh_extreme.apworld"]
    assert len(sources) == 1 and sources[0].is_zip and sources[0].time_taken >= 0, sources
    assert not (args.runtime / "worlds" / "soh_extreme").exists()

    resource_root = files(package)
    resources = []
    json_resources = {}
    with zipfile.ZipFile(args.archive) as archive:
        assert archive.testzip() is None
        names = [entry.filename for entry in archive.infolist() if not entry.is_dir()]
        assert len(names) == len(set(names)), "Duplicate archive entries"
        manifest = json.loads(archive.read("archipelago.json"))
        assert manifest == json.loads(archive.read("soh_extreme/archipelago.json"))
        assert manifest["world_version"] == args.expected_version
        assert manifest["minimum_ap_version"] == "0.6.7"
        assert manifest["game"] == "SOH-EXTREME"
        package_names = {name.removeprefix("soh_extreme/") for name in names
                         if name.startswith("soh_extreme/")}
        expected_names = {path.relative_to(args.source).as_posix()
                          for path in args.source.rglob("*")
                          if path.is_file() and "__pycache__" not in path.parts
                          and path.suffix != ".pyc"}
        assert package_names == expected_names, {
            "missing": sorted(expected_names - package_names),
            "extra": sorted(package_names - expected_names),
        }
        for relative in sorted(package_names):
            resource = resource_root.joinpath(*relative.split("/"))
            expected = archive.read("soh_extreme/" + relative)
            assert resource.is_file(), relative
            assert resource.read_bytes() == expected, relative
            assert (args.source / relative).read_bytes() == expected, relative
            resources.append(relative)
            if relative.endswith(".json"):
                json_resources[relative] = json.loads(resource.read_text(encoding="utf-8"))
        assert json.loads(pkgutil.get_data(package.__name__, "archipelago.json")) == manifest

    er = modules["EntranceRandomizer"]
    assert er.CATALOG == tuple(json_resources["EntranceCatalog.json"])
    assert er.DUNGEON_ROUTES == json_resources["DungeonLocationRoutes.json"]
    assert er.REVISION == 1
    assert callable(er._starting_state_is_viable)
    assert modules["EnemyRoomLogic"].GRAPH == json_resources["EnemyRoomGraph.json"]
    assert modules["EnemyRoomLogic"].ENEMY_ROOM_MAP == json_resources["EnemyRoomMap.json"]
    assert modules["SilverRoomLogic"].ROUTES == json_resources["SilverRoomRoutes.json"]
    assert modules["NpcSpeech"].CATALOG == tuple(json_resources["NpcSpeechCatalog.json"])
    raw_catalog = tuple(json_resources["SceneTransitionCatalog.json"] + json_resources["DungeonDoorCatalog.json"])
    descriptions = json_resources["CheckDescriptions.json"]
    named_catalog = modules["SceneTransitions"].CATALOG
    assert len(named_catalog) == len(raw_catalog)
    for raw, named in zip(raw_catalog, named_catalog):
        assert {key: value for key, value in raw.items() if key != "name"} == {
            key: value for key, value in named.items() if key != "name"}
        assert named["name"] == descriptions.get(str(raw["id"]), {}).get("name", raw["name"])
        assert package.SohExtremeWorld.location_name_to_id[named["name"]] == raw["id"]
    published = package.SohExtremeWorld.location_name_to_id
    assert len(published) == len(set(published.values())), "Datapackage contains duplicate location IDs"
    for tutorial in package.SohExtremeWorld.web.tutorials:
        assert resource_root.joinpath("docs", tutorial.file_name).is_file(), tutorial.file_name

    # The standalone build compares these release labels. Import both copies
    # of TrackerMirror so a stale literal cannot pass just because the world
    # manifest and the generator import correctly.
    tracker_path = args.source / "TrackerMirror.py"
    tracker_bytes = tracker_path.read_bytes()
    tracker_spec = importlib.util.spec_from_file_location(
        "worlds.soh_extreme._loose_tracker_version_validation", tracker_path)
    loose_tracker = importlib.util.module_from_spec(tracker_spec)
    tracker_spec.loader.exec_module(loose_tracker)
    literal_match = re.search(r'^VERSION = "([^"]+)"\r?$',
                              tracker_bytes.decode("utf-8"), re.MULTILINE)
    assert literal_match, "Keep the literal VERSION field compatible with the PowerShell build"
    native_match = re.search(r'^#define SOH_EXTREME_VERSION "([^"]+)"\r?$',
                             args.native_header.read_text(encoding="utf-8"), re.MULTILINE)
    assert native_match, "Missing native release version"
    versions = {
        "archive_manifest": manifest["world_version"],
        "loose_manifest": json.loads((args.source / "archipelago.json").read_bytes())["world_version"],
        "loose_tracker_version": loose_tracker.VERSION,
        "loose_tracker_literal": literal_match.group(1),
        "packaged_tracker_version": modules["TrackerMirror"].VERSION,
        "native_header_version": native_match.group(1),
    }
    assert set(versions.values()) == {args.expected_version}, versions
    assert tracker_bytes.count(b"\r\n") == tracker_bytes.count(b"\n"), "TrackerMirror CRLF changed"
    archive_sha256 = hashlib.sha256(args.archive.read_bytes()).hexdigest()
    version_report = {
        "status": "passed",
        "test": "standalone_build_release_version_parity",
        "versions": versions,
        "archive_sha256": archive_sha256,
        "loose_tracker_path": str(tracker_path),
        "packaged_tracker_origin": modules["TrackerMirror"].__file__,
        "packaged_tracker_loader": type(modules["TrackerMirror"].__loader__).__name__,
        "native_header_path": str(args.native_header),
        "literal_version_field_preserved": True,
        "tracker_crlf_lines": tracker_bytes.count(b"\r\n"),
        "tracker_bare_lf_lines": 0,
        "tracker_sha256": hashlib.sha256(tracker_bytes).hexdigest(),
        "generation_run": False,
    }
    args.version_report.write_text(json.dumps(version_report, indent=2) + "\n", encoding="utf-8")

    report = {
        "status": "passed",
        "test": "official_apworld_zip_import_and_all_package_resources",
        "archipelago_version": Utils.__version__,
        "world_version": manifest["world_version"],
        "minimum_ap_version": manifest["minimum_ap_version"],
        "archive": str(args.archive),
        "archive_size_bytes": args.archive.stat().st_size,
        "archive_sha256": archive_sha256,
        "archive_entries": len(names),
        "package_files_verified": len(resources),
        "source_files_missing": [],
        "json_resources_loaded": sorted(json_resources),
        "entrance_catalog_entries": len(er.CATALOG),
        "entrance_mapping_revision": er.REVISION,
        "starting_state_guard_present": True,
        "official_loader_source": sources[0].resolved_path,
        "world_loader": type(package.__loader__).__name__,
        "module_origins": {name: module.__file__ for name, module in modules.items()},
        "resources_root": str(resource_root),
        "no_loose_world_during_import": True,
        "failed_world_loads": worlds.failed_world_loads,
        "generation_run": False,
        "release_versions": versions,
        "tracker_version_report": str(args.version_report),
    }
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "status", "archipelago_version", "world_version", "archive_entries",
        "package_files_verified", "entrance_catalog_entries", "world_loader")}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--native-header", type=Path)
    parser.add_argument("--version-report", type=Path)
    parser.add_argument("--expected-version", default="1.8.2")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    if args.native_header is None:
        args.native_header = args.source.parents[1] / "soh" / "SohExtremeVersion.h"
    if args.version_report is None:
        args.version_report = args.report.parent / "tracker_version_validation.json"
    if args.probe:
        probe(args)
        return

    world_link = args.runtime / "worlds" / "soh_extreme"
    assert world_link.is_symlink(), "Expected the isolated test runtime's source symlink"
    link_target = os.readlink(world_link)
    staged_archive = args.runtime / "custom_worlds" / "soh_extreme.apworld"
    assert not staged_archive.exists(), "Refusing to replace an existing test archive"
    staged_archive.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.version_report.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copyfile(args.archive, staged_archive)
        world_link.unlink()
        command = [sys.executable, str(Path(__file__).resolve()), "--probe",
                   "--runtime", str(args.runtime), "--archive", str(args.archive),
                   "--source", str(args.source), "--report", str(args.report),
                   "--native-header", str(args.native_header),
                   "--version-report", str(args.version_report),
                   "--expected-version", args.expected_version]
        subprocess.run(command, cwd=args.runtime, env=os.environ.copy(), check=True, timeout=60)
    finally:
        if not world_link.exists() and not world_link.is_symlink():
            world_link.symlink_to(link_target, target_is_directory=True)
        staged_archive.unlink(missing_ok=True)
    assert world_link.is_symlink() and os.readlink(world_link) == link_target
    report = json.loads(args.report.read_text(encoding="utf-8"))
    report["source_symlink_restored"] = True
    report["staged_archive_removed"] = not staged_archive.exists()
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
