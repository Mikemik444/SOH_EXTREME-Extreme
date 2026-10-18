"""Assemble the final 1.8.4 source bundle's hash-bound validation record.

Run after final AP source freeze, both official full fills, APWorld rebuild and
ZIP-loader validation, and prepare_source_delivery.py --prepare. This script
does not generate seeds or change production source.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import prepare_source_delivery as delivery

TESTS = ROOT / "tests"
SOURCE = ROOT / "source"
CURRENT_REPORTS = (
    "jabu_184_native_bridge_validation.json",
    "entrance_184_settings_validation.json",
    "jabu_184_carry_validation.json",
    "entrance_184_overworld_validation.json",
    "entrance_184_spawn_placement_validation.json",
    "entrance_184_full_fill_child.json",
    "entrance_184_full_fill_adult.json",
)
FIXTURE_REPORTS = (
    "entrance_184_bridge_child_report.json",
    "entrance_184_bridge_adult_report.json",
)
DIAGNOSTIC_REPORTS = (
    "entrance_184_installer_timestamp_reproduction.json",
    "entrance_184_adult_fill_reproduction.json",
)
EVIDENCE_FILES = (
    "entrance_184_release_evidence.py",
    "entrance_184_reproduce_installer_build.py",
    "entrance_184_installer_build_probe.ps1",
    "entrance_184_export_bridge.py",
    "entrance_184_run_full_fill.py",
    "entrance_184_bridge_child_cvars.json",
    "entrance_184_bridge_adult_cvars.json",
    "entrance_184_bridge_child_slot_data.json",
    "entrance_184_bridge_adult_slot_data.json",
    "entrance_184_bridge_child.log",
    "entrance_184_bridge_adult.log",
    "entrance_184_settings_validation.log",
    "jabu_184_carry_validation.log",
    "entrance_184_overworld_regressions.log",
    "entrance_184_spawn_placement_regression.py",
    "entrance_184_spawn_placement_regressions.log",
    "entrance_184_full_fill_child.log",
    "entrance_184_full_fill_adult.log",
    "entrance_184_adult_fill_reproduction.log",
    "entrance_184_native_dependencies_provenance.json",
)


def read(name: str):
    assert Path(name).name == name, name
    return json.loads((TESTS / name).read_text(encoding="utf-8-sig"))


def file_hash(path: Path):
    assert path.is_file(), path
    return delivery.base.sha256(path.read_bytes())


def resolve_source(relative: str):
    candidate = SOURCE / relative
    return candidate if candidate.is_file() else SOURCE / "archipelago/soh_extreme" / relative


def verify_native_inputs(report: dict, name: str):
    delivery.verify_source_hashes(report, name)
    for relative, expected in report.get("test_sha256", {}).items():
        assert file_hash(resolve_source(relative)) == expected, {"report": name, "stale_test": relative}
    for relative, expected in report.get("fixture_sha256", {}).items():
        assert file_hash(ROOT / relative) == expected, {"report": name, "stale_fixture": relative}
    for relative, expected in report.get("dependency_sha256", {}).items():
        assert file_hash(TESTS / "entrance_184_native_dependencies" / relative) == expected, {
            "report": name, "stale_dependency": relative,
        }


def main():
    manifest = json.loads(delivery.MANIFEST.read_bytes())
    assert manifest["version"] == "1.8.4" and manifest["layout"] == "complete_source_files"
    assert manifest == delivery.source_manifest()
    source_hashes = {entry["path"]: entry["sha256"] for entry in manifest["files"]}
    source_completeness = delivery.source_completeness(manifest)
    assert source_completeness["source_sha256"] == source_hashes
    current = {name: read(name) for name in CURRENT_REPORTS}
    packaging = {name: read(name) for name in delivery.PACKAGING_REPORTS}
    assert all(report["status"] == "passed" for report in (*current.values(), *packaging.values()))
    for name, report in current.items():
        verify_native_inputs(report, name)
    for name, report in packaging.items():
        delivery.verify_source_hashes(report, name)

    yaml_hash = file_hash(delivery.USER_YAML)
    expected_precollected = current["jabu_184_carry_validation.json"]["precollected"]
    assert sorted(expected_precollected) == ["Weird Egg", "Zelda's Letter"]
    full_fills = {}
    for age in ("child", "adult"):
        name = f"entrance_184_full_fill_{age}.json"
        report = current[name]
        assert report["age"] == age and report["world_version"] == "1.8.4"
        assert report["archipelago_version"] == "0.6.7"
        assert report["yaml_sha256"] == yaml_hash and report["source_unchanged_during_run"]
        assert report["validation"]["passed"]
        players = report["validation"]["players"]
        assert set(players) == {"1"}
        player = players["1"]
        assert player["goal_met"] and player["full_accessibility"]
        assert player["checked"] == player["network_checks"] and player["checked"] > 0
        assert report["initial_network_checks"] > 0 and report["initial_progression_checks"]
        assert report["initial_physical_checks"] > 0 and report["initial_hyrule_field_reachable"] is True
        assert sorted(report["precollected_items"]) == sorted(expected_precollected)
        assert report["saved_mixed_entrance_pools"] == ["all"]
        assert report["enabled_entrance_categories"] == report["expanded_mixed_categories"]
        assert report["native_overworld_flag"] == 1
        assert report["overworld_endpoints"] == 52
        assert 0 < report["changed_overworld_endpoints"] <= report["overworld_endpoints"]
        full_fills[age] = {
            "seed": report["seed"], "goal_met": True, "full_accessibility": True,
            "network_checks": player["network_checks"], "checked": player["checked"],
            "initial_network_checks": report["initial_network_checks"],
            "initial_physical_checks": report["initial_physical_checks"],
            "initial_hyrule_field_reachable": True,
            "precollected_items": report["precollected_items"],
            "initial_progression_checks": report["initial_progression_checks"],
            "child_spawn": report["child_spawn"], "adult_spawn": report["adult_spawn"],
            "changed_overworld_endpoints": report["changed_overworld_endpoints"],
            "source_unchanged_during_run": True,
        }

    bridge = current["jabu_184_native_bridge_validation.json"]
    settings = current["entrance_184_settings_validation.json"]
    spawn_guard = current["entrance_184_spawn_placement_validation.json"]
    assert spawn_guard["tests_run"] >= 58
    assert spawn_guard["failures"] == spawn_guard["errors"] == spawn_guard["skipped"] == 0
    assert spawn_guard["source_unchanged_during_run"] is True
    assert spawn_guard["runner_sha256"] == file_hash(TESTS / "entrance_184_spawn_placement_regression.py")
    assert spawn_guard["log_sha256"] == file_hash(TESTS / "entrance_184_spawn_placement_regressions.log")
    for report in (bridge, settings):
        assert len(report["cases"]) == 2
        assert report["native_windows_build"] is False and report["in_game_playthrough"] is False
        assert report["engine_io_isolated"] is True
        assert set(report["sanitizers"]) == {"address", "undefined"}
    for case in bridge["cases"]:
        assert case["routes"] == 719 and case["settings"] == 1028
        assert 0 < case["changed_overworld_routes"] <= 52
        assert case["native_scene_lookups"] == 232 and case["native_dynamic_lookups"] == 14
        assert case["door_cases"]["ordinary_openings"] == 421
        assert case["door_cases"]["local_carrier_directions"] == 12
        assert {spawn["age"] for spawn in case["spawn_cases"]} == {"child", "adult"}
    for case in settings["cases"]:
        assert case["routes"] == 719 and case["native_cvars"] == 1028
        assert len(case["rejected_inputs"]) == 28
        for flag in ("corrected_snapshot_recovery", "good_cache_preserved", "legacy_all_off_accepted",
                     "status_uses_installed_routes", "valid_snapshot_readiness"):
            assert case[flag], flag

    # These authentic maps were exported before the item-fill stage. Any
    # intentional provenance exception must be explicitly reviewed here; all
    # current full-fill reports above always require every AP source hash.
    fixture_provenance = []
    for name in FIXTURE_REPORTS:
        report = read(name)
        assert report["status"] == "passed" and report["world_version"] == "1.8.4"
        assert report["yaml_sha256"] == yaml_hash and report["source_unchanged_during_run"]
        delivery.verify_source_hashes(report, name)
        assert report["exported_mapping_endpoints"] == 719 and report["exported_cvars"] == 1028
        assert 0 < report["changed_overworld_endpoints"] <= 52
        assert report["mixed_pools"] == ["all"] and len(report["local_carrier_identity_routes"]) == 12
        assert report["initial_selected_age_hyrule_field_reachable"] is True
        assert report["precollected_unchanged_by_entrance_shuffle"] is True
        assert report["initial_precollected_item_counts"] == {"Weird Egg": 1, "Zelda's Letter": 1}
        assert len(report["initial_reachable_physical_checks"]) == full_fills[report["age"]]["initial_physical_checks"]
        assert report["initial_swim_missing"] is True
        assert report["both_mapped_spawns_outside_water_temple"] is True
        for artifact in report["artifacts"].values():
            path = Path(artifact["path"])
            assert path.parent == TESTS
            assert file_hash(path) == artifact["sha256"]
    diagnostics = {name: read(name) for name in DIAGNOSTIC_REPORTS}
    assert all(report["status"] == "reproduced" for report in diagnostics.values())
    assert diagnostics["entrance_184_adult_fill_reproduction.json"]["yaml_sha256"] == yaml_hash
    assert file_hash(TESTS / "entrance_184_adult_fill_reproduction.log") == diagnostics[
        "entrance_184_adult_fill_reproduction.json"]["log_sha256"]
    assert len(diagnostics["entrance_184_installer_timestamp_reproduction.json"]["cases"]) == 4

    dependency_provenance = TESTS / "entrance_184_native_dependencies/provenance.json"
    shutil.copyfile(dependency_provenance, TESTS / "entrance_184_native_dependencies_provenance.json")
    evidence_files = sorted({*CURRENT_REPORTS, *FIXTURE_REPORTS, *DIAGNOSTIC_REPORTS, *EVIDENCE_FILES})
    evidence_hashes = {name: file_hash(TESTS / name) for name in evidence_files}
    result = {
        "status": "passed", "world_version": "1.8.4", "layout": "complete_source_files",
        "source_sha256": source_hashes,
        "native_windows_build_or_gameplay_run": False,
        "evidence_files": evidence_files,
        "evidence_sha256": evidence_hashes,
        "packaging_evidence_sha256": {name: file_hash(TESTS / name) for name in delivery.PACKAGING_REPORTS},
        "fixture_provenance_files": fixture_provenance,
        "changed_generator_files": packaging["entrance_184_generator_scope.json"]["changed_logic_or_resource_files"],
        "full_fills": full_fills,
        "yaml_sha256": yaml_hash,
        "source_completeness": {
            "manifest_covers_every_modified_or_added_source_file": True,
            "current_files_compared": source_completeness["current_files_compared"],
            "complete_changed_source_files": source_completeness["complete_changed_source_files"],
            "missing_original_files": [],
        },
        "native_scope": "Compiled production parser/readiness/status, complete entrance initializer and lookup, cached/late/save-menu spawn, and native door/check dispatch; engine I/O is isolated, with address/undefined sanitizers.",
        "diagnostic_scope": "The earlier timestamp-skipped native builds and the adult item-fill failure are reproduced pre-fix failures, not successful generation or Windows gameplay evidence.",
        "limits": [
            "No complete Windows game build, MSBuild run, or in-game playthrough was performed here.",
            "The source-only clean build helper was exercised in minimal real CMake/GCC fixtures using PowerShell Core on Unix.",
            "The user's exact earlier seed map, received-item snapshot, and launched executable were not available for inspection.",
            "Native map validation does not enforce that every enabled category is present in an otherwise valid partially supplied revision-1 map.",
        ],
    }
    (TESTS / delivery.RELEASE_REPORT).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "source_files": len(source_hashes),
                      "evidence_files": len(evidence_files), "full_fills": full_fills}, indent=2))


if __name__ == "__main__":
    main()
