"""Package the cumulative 1.8.11 entrance-label and native grotto correction.

The APWorld, AP rules, item placements, options and release markers are unchanged.
Every prior replacement file and historical validation report is retained.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import shutil
import zipfile

from prepare_seed_safety_1810_delivery import inventory
from prepare_source_delivery import write_source_archive

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source"
BASE = ROOT / "delivery/SOH-EXTREME-1.8.11-source-files.zip"
BASE_SHA = "5dbd457545a053e1175e4d921afd8168272e75d9de386ea373013b85693094e0"
VERSION = "1.8.11"
PACKAGE = ROOT / "delivery/SOH-EXTREME-1.8.11-entrance-fixes-source-files"
ARCHIVE = PACKAGE.parent / (PACKAGE.name + ".zip")
VALIDATION = PACKAGE / "validation/entrance_fixes_1811"
PRODUCTION_CHANGES = {
    "soh/Enhancements/randomizer/randomizer_check_tracker.cpp",
    "soh/Enhancements/randomizer/RoomDebugWorldLabels.inc",
    "soh/Enhancements/randomizer/SceneExitLabels.h",
    "soh/Enhancements/randomizer/logic.cpp",
}
REQUIRED_REPORTS = {
    "entrance_label_overlays_1811_native.json",
    "transition_labels_1811_overlay_regression.json",
    "grotto_access_1811_native.json",
    "bomb_grotto_1811_ap.json",
    "grotto_1811_uploaded_seed_reproduction.json",
    "finder_autoexpand_1811_native.json",
}
PRESERVE_TOP = {"README.txt", "VALIDATION.txt", "SOURCE_FILES.json"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(path: Path):
    return json.loads(path.read_bytes())


def ap_contents() -> dict[str, bytes]:
    folder = SOURCE / "archipelago/soh_extreme"
    entries = {"archipelago.json": (SOURCE / "archipelago/archipelago.json").read_bytes()}
    entries.update({"soh_extreme/" + p.relative_to(folder).as_posix(): p.read_bytes()
                    for p in folder.rglob("*") if p.is_file()
                    and "__pycache__" not in p.parts and p.suffix != ".pyc"})
    return entries


def assert_ap_unchanged(base: zipfile.ZipFile) -> None:
    current = (SOURCE / "archipelago/soh_extreme.apworld").read_bytes()
    assert current == base.read("archipelago/soh_extreme.apworld") == base.read("soh_extreme.apworld")
    with zipfile.ZipFile(io.BytesIO(current)) as ap:
        assert {n: ap.read(n) for n in ap.namelist()} == ap_contents()
    assert (SOURCE / "soh/SohExtremeVersion.h").read_bytes() == base.read("soh/SohExtremeVersion.h")


def prepare() -> None:
    assert sha(BASE.read_bytes()) == BASE_SHA
    current, _, original_count, current_count = inventory()
    with zipfile.ZipFile(BASE) as base, zipfile.ZipFile(ROOT / "upload/haha.zip") as original:
        assert_ap_unchanged(base)
        old_manifest = json.loads(base.read("SOURCE_FILES.json"))
        previous = {r["path"]: r for r in old_manifest["files"]}
        assert len(previous) == 190 and set(previous) <= set(current)
        contents = {
            ("validation/base_1.8.11/" + n if n in PRESERVE_TOP else n): base.read(n)
            for n in base.namelist()
        }
        rows, delta = [], {}
        for name, metadata in sorted(current.items()):
            data = (SOURCE / name).read_bytes()
            before = base.read(name) if name in previous else (
                original.read(name) if name in original.namelist() else None)
            row = dict(previous.get(name, {}))
            row.update(metadata)
            rows.append(row)
            contents[name] = data
            if data != before:
                assert name in PRODUCTION_CHANGES or name.startswith("tools/tests/"), name
                delta[name] = {"change": "modified" if before is not None else "added",
                               "previous_sha256": sha(before) if before is not None else None,
                               "sha256": sha(data), "size_bytes": len(data)}
        assert PRODUCTION_CHANGES <= set(delta), sorted(PRODUCTION_CHANGES - set(delta))
        assert (SOURCE / "soh/Enhancements/randomizer/logic.cpp").read_bytes().startswith(
            b"#include <libultraship/bridge/consolevariablebridge.h>\r\n")
        manifest = {"version": VERSION, "layout": "complete_source_files", "build_helper_revision": 4,
                    "release": "Entrance labels, Finder automatic expansion and native bomb-grotto tool correction.",
                    "files": rows}
        contents["SOURCE_FILES.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
        # This directory contains only reproducible build-staging outputs.
        # Start a complete snapshot so a previous preparation cannot leak files.
        if PACKAGE.exists():
            shutil.rmtree(PACKAGE)
        for name, data in contents.items():
            path = PACKAGE / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        report = {
            "status": "passed", "version": VERSION, "base_archive_sha256": BASE_SHA,
            "original_source_files": original_count, "current_source_files": current_count,
            "complete_source_files": len(rows), "changes_since_1.8.11": delta,
            "all_190_previous_replacement_files_retained": True,
            "unmanifested_source_changes": [], "all_ap_sources_unchanged": True,
            "apworld_byte_identical_to_1.8.11": True, "apworld_matches_current_source": True,
            "build_helpers_yaml_and_release_markers_unchanged": True,
            "cvar_declaration_fix_retained": True,
            "source_sha256": {r["path"]: r["sha256"] for r in rows},
            "manifest_sha256": sha(contents["SOURCE_FILES.json"]),
            "apworld_sha256": sha(contents["soh_extreme.apworld"]),
            "prepared_archive_paths": sorted(contents),
        }
        (ROOT / "tests/entrance_fixes_1811_source_completeness.json").write_text(
            json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": "prepared", "complete_source_files": len(rows),
                      "changes": list(delta), "package": str(PACKAGE)}))


def validate_report(name: str, report: dict) -> None:
    assert report.get("status") in {"passed", "exactly_reproduced"}, (name, report.get("status"))
    binding_keys = ("sources", "source_sha256", "test_sha256", "stable_source_sha256", "version_source_sha256")
    assert any(report.get(key) for key in binding_keys), (name, "No source-bound validation evidence")
    for key in binding_keys:
        for relative, expected in report.get(key, {}).items():
            assert isinstance(expected, str), (name, key, relative)
            assert sha((SOURCE / relative).read_bytes()) == expected, (name, key, relative)


def finalize(report_paths: list[Path]) -> None:
    assert report_paths, "Fresh source-bound verification reports are required."
    assert REQUIRED_REPORTS <= {p.name for p in report_paths}, sorted(
        REQUIRED_REPORTS - {p.name for p in report_paths})
    assert sha(BASE.read_bytes()) == BASE_SHA
    manifest = read(PACKAGE / "SOURCE_FILES.json")
    completeness = read(ROOT / "tests/entrance_fixes_1811_source_completeness.json")
    preflight = read(ROOT / "tests/entrance_fixes_1811_source_build_validation.json")
    assert completeness["status"] == preflight["status"] == "passed"
    assert completeness["manifest_sha256"] == preflight["manifest_sha256"]
    assert preflight["manifest_sha256"] == sha((PACKAGE / "SOURCE_FILES.json").read_bytes())
    current, _, _, _ = inventory()
    assert set(current) == {r["path"] for r in manifest["files"]}
    for row in manifest["files"]:
        assert row["sha256"] == sha((SOURCE / row["path"]).read_bytes()) == sha((PACKAGE / row["path"]).read_bytes())
    reports = {}
    VALIDATION.mkdir(parents=True, exist_ok=True)
    added_paths = set()
    for path in report_paths:
        report = read(path)
        validate_report(path.name, report)
        assert path.name not in reports
        reports[path.name] = report
        shutil.copyfile(path, VALIDATION / path.name)
        added_paths.add((VALIDATION / path.name).relative_to(PACKAGE).as_posix())
    # Replacement files are intentionally cumulative changes, not an entire
    # checkout. Preserve unchanged native fixture inputs separately; all AP
    # inputs are already present in the byte-identical complete APWorld.
    replay_inputs = {}
    binding_keys = ("sources", "source_sha256", "test_sha256", "stable_source_sha256", "version_source_sha256")
    with zipfile.ZipFile(PACKAGE / "soh_extreme.apworld") as ap:
        for report in reports.values():
            for key in binding_keys:
                for relative, expected in report.get(key, {}).items():
                    target = PACKAGE / relative
                    if target.is_file():
                        assert sha(target.read_bytes()) == expected, relative
                        location = relative
                    elif relative.startswith("archipelago/soh_extreme/"):
                        member = relative.removeprefix("archipelago/")
                        assert sha(ap.read(member)) == expected, relative
                        location = "soh_extreme.apworld!" + member
                    else:
                        target = PACKAGE / "validation/native_source" / relative
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(SOURCE / relative, target)
                        assert sha(target.read_bytes()) == expected, relative
                        location = target.relative_to(PACKAGE).as_posix()
                        added_paths.add(location)
                    entry = {"sha256": expected, "location": location}
                    assert relative not in replay_inputs or replay_inputs[relative] == entry
                    replay_inputs[relative] = entry
            for name, expected in report.get("native_dependencies", {}).items():
                assert Path(name).name == name, name
                source = ROOT / "tests/entrance_184_native_dependencies" / name
                assert sha(source.read_bytes()) == expected, name
                target = PACKAGE / "validation/native_dependencies" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                assert sha(target.read_bytes()) == expected, name
                location = target.relative_to(PACKAGE).as_posix()
                added_paths.add(location)
                replay_inputs["native_dependencies/" + name] = {"sha256": expected, "location": location}
    replay_index = VALIDATION / "REPLAY_INPUTS.json"
    replay_index.write_text(json.dumps(replay_inputs, indent=2) + "\n")
    added_paths.add(replay_index.relative_to(PACKAGE).as_posix())
    for name in ("entrance_fixes_1811_source_completeness.json",
                 "entrance_fixes_1811_source_build_validation.json",
                 "entrance_fixes_1811_source_build_check.py", "entrance_184_source_build_probe.ps1"):
        shutil.copyfile(ROOT / "tests" / name, VALIDATION / name)
        added_paths.add((VALIDATION / name).relative_to(PACKAGE).as_posix())
    shutil.copyfile(Path(__file__), VALIDATION / Path(__file__).name)
    added_paths.add((VALIDATION / Path(__file__).name).relative_to(PACKAGE).as_posix())
    exact_name = "grotto_1811_uploaded_seed_reproduction.json"
    ap_test_name = "bomb_grotto_1811_ap.json"
    assert exact_name in reports and ap_test_name in reports
    exact, ap_test = reports[exact_name], reports[ap_test_name]
    settings_input = ROOT / "tests/grotto_1811_uploaded_seed_reproduction.options.json"
    spoiler_input = ROOT / "upload/AP_66154502437901277321_Spoiler.txt"
    audit_runner = ROOT / "tests/audit_uploaded_seed_189.py"
    assert sha(settings_input.read_bytes()) == ap_test["settings_report_sha256"]
    assert sha(spoiler_input.read_bytes()) == exact["spoiler_sha256"]
    assert exact["matching_placements"] == exact["network_checks"] == 4036
    assert exact["mismatched_placements"] == 0 and exact["child_spawn"]["id"] == 1806
    assert exact["mapping"]["187"] == exact["mapping"]["1806"] == 1806
    assert len(exact["mapping"]) == 719
    assert {s for s, target in exact["mapping"].items() if target == 1806} == {"187", "1806"}
    assert exact["source_unchanged_during_run"] and exact["all_placements_match_uploaded_spoiler"]
    player = exact["original_ap_validation"]["players"]["1"]
    assert exact["original_ap_validation"]["passed"] and player["goal_met"]
    assert player["checked"] == player["network_checks"] == 4036
    assert sha(audit_runner.read_bytes()) == "fc76a385c39575ebe0375d922e17a4c3851340532263411df72918a08ec36ec5"
    inputs = VALIDATION / "inputs"
    inputs.mkdir(exist_ok=True)
    for source, target in ((settings_input, inputs / settings_input.name),
                           (spoiler_input, inputs / spoiler_input.name),
                           (audit_runner, VALIDATION / audit_runner.name)):
        shutil.copyfile(source, target)
        assert source.read_bytes() == target.read_bytes()
        added_paths.add(target.relative_to(PACKAGE).as_posix())
    replay = r'''Replay notes for the fresh entrance/Finder/grotto evidence
====================================================
Run from a complete checkout after merging the replacement source files. Use
Python with Archipelago 0.6.8 and its dependencies, importing this unchanged
SOH-EXTREME 1.8.11 world from the checkout. Supply your actual runtime paths.
Also copy the validation folder into the checkout root to use these commands.
Unchanged native source inputs are retained under validation/native_source
with their checkout-relative paths; they are references, not extra changes.
REPLAY_INPUTS.json identifies every bound source input, including AP source
members already contained in the root soh_extreme.apworld. The native scene
and entrance tables are retained under validation/native_dependencies.

AP source-versus-spawn regression:
python tools/tests/test_bomb_grotto_logic.py --settings-report validation/entrance_fixes_1811/inputs/grotto_1811_uploaded_seed_reproduction.options.json --report bomb_grotto_replay.json

Exact uploaded-seed reconstruction:
python validation/entrance_fixes_1811/audit_uploaded_seed_189.py --source-root . --spoiler validation/entrance_fixes_1811/inputs/AP_66154502437901277321_Spoiler.txt --report seed_reproduction.json --initial-time-random

The filename number differs from the generator seed in the spoiler header.
Exact attribution requires all 4,036 generated placements to match. The original
Random starting-time setting is restored before world RNG resolution. This
audit generates no game output files and changes no user save or installed world.

Native grotto fixture (C++ compiler with AddressSanitizer and UBSan):
python tools/tests/test_grotto_access_native.py --report grotto_native_replay.json

Native destination formatter regression:
python tools/tests/test_transition_labels_native.py --report labels_replay.json

Native Finder automatic expansion and old-behavior reproductions:
python tools/tests/test_finder_autoexpand_native.py --baseline ../SOH-EXTREME-1.8.11-source-files.zip --native-deps validation/native_dependencies --report finder_replay.json

Native overlapping entrance labels and old-behavior reproductions:
python tools/tests/test_entrance_label_overlays_native.py --baseline ../SOH-EXTREME-1.8.11-source-files.zip --report overlay_replay.json

Adjust the --baseline path to your immutable original 1.8.11 source archive.
The Finder runner requires it; the overlay runner can omit that argument when
not replaying the former duplicate producers. The required original archive has
SHA256 5dbd457545a053e1175e4d921afd8168272e75d9de386ea373013b85693094e0.
Production-function native fixtures isolate engine I/O; they are not a native
game build or controller playthrough. See each report for actual source hashes.
'''
    (VALIDATION / "REPLAY.txt").write_text(replay)
    added_paths.add((VALIDATION / "REPLAY.txt").relative_to(PACKAGE).as_posix())
    with zipfile.ZipFile(BASE) as base:
        assert_ap_unchanged(base)
        for name in ("BUILD_RELEASE.cmd", "BUILD_RELEASE.ps1", "SOH-EXTREME.yaml", "soh_extreme.apworld"):
            assert (PACKAGE / name).read_bytes() == base.read(name), name
        for name in base.namelist():
            if name.startswith("validation/"):
                assert (PACKAGE / name).read_bytes() == base.read(name), name
    readme = r'''SOH-EXTREME 1.8.11 - Complete source files, entrance fixes
=========================================================

YELLOW AND CYAN ENTRANCE LABELS
------------------------------
A physical doorway now gets one yellow label, including double doors. If that
doorway also owns a scene-exit trigger, its overlapping cyan label is suppressed
while the yellow label is visible. Independent exits keep their cyan labels,
including separate exits that share a destination. Invisible or distant door
actors leave the scene-exit fallback available. Existing descriptive names and
destination room numbers are retained.

CHECK FINDER AUTOMATIC EXPANSION
-------------------------------
The current physical scene opens automatically until you explicitly choose its
dropdown state. Untouched sections collapse again when you leave. A deliberate
open or close remains your choice. The current area is determined from the live
scene identity, independent of the tracker worker's inventory-refresh timing.
Day/night/adult variants of the same area match the same Finder section. Shared
interiors use their physical spawn identity, and the Dampe's Grave-to-Windmill
passage follows Link's current room instead of the original entrance. Manual
scene choices remain stable when the region grouping or visible check counts change.

BOMBABLE GROTTOS AND RANDOMIZED SPAWN
-----------------------------------
The hidden hole's native opening rule now requires usable explosives or Hammer,
matching the existing Archipelago rule. Grab / Power Bracelet alone cannot open
it. Existing Shovel, Rock / Boulder Soul and Stone of Agony logic policy and
separate source-specific blockers are retained; this is not a change to which
physical obstacles are governed by Souls.

Opening the hole from outside and arriving inside are separate routes. A grotto
used as the randomized spawn can have reachable checks without explosives.
Returning to that spawn restores access to its inside. The checks still apply
their own applicable item, Soul and combat requirements. No explosives condition
has been added to every check in a grotto merely because its outside hole is shut.

UPLOADED SEED CHECK
-------------------
AP_66154502437901277321 was reconstructed from generator seed
28991991854046421672. All 4,036 placements match the uploaded spoiler exactly.
Its child spawn targets HF Stone Bridge Tree Grotto, and that grotto's physical
field entrance retains its vanilla destination. AP validation reaches all 4,036
checks and the goal across 44 validation spheres. The exact reconstruction and
source-versus-spawn regression are included in this update's validation folder.
This is verification of the AP model, not a full in-game route/collision proof.

COMPATIBILITY
-------------
The APWorld and every AP source file are byte-identical to the delivered 1.8.11.
No entrance map, item placement, location ID, option or release marker changed.
An existing 1.8.11 seed/save does not need regeneration for this source update.
The previously diagnosed Armos-room seed AP_98530958489753355589 remains blocked;
these label/grotto changes do not repair that older seed's fixed placements.

INSTALL AND BUILD
-----------------
1. Merge soh, src, archipelago and tools into your complete checkout, replacing
   the corresponding files. Copy SOURCE_FILES.json, BUILD_RELEASE.cmd and
   BUILD_RELEASE.ps1 into the checkout root as well.
2. For E:\test\bb, run:

   cd /d E:\test\bb
   BUILD_RELEASE.cmd -RepositoryPath "E:\test\bb" -BuildDirectory "build-vs"

   The helper verifies the complete replacement sources and performs a clean
   Release build. Use the executable path printed by that successful build.
3. The root soh_extreme.apworld is the same 1.8.11 file previously supplied.
   If you still need to update an older APWorld, install it at:
   C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
   Keep your current 1.8.11 seed/save for this update.

All earlier complete replacement sources are included, including the Dodongo
wall/switch fixes and logic.cpp's direct declaration include for CVarGetInteger.
There is no payload folder and no patch application step.

VALIDATION
----------
Fresh evidence and reproducible source tests are under
validation/entrance_fixes_1811/ and tools/tests/. Source hashes bind each current
report to its actual inputs. The shipped build helper's source preflight checks
every replacement file in a disposable fixture. Historical reports retain their
original bytes and dates; they are not presented as fresh runs of changed source.
To replay the tests, also copy validation into the checkout and follow REPLAY.txt.
Native fixtures execute production code with explicit engine I/O shims. This
partial-source environment does not perform a full Windows game build or an
in-game controller playthrough. Source-graph seed validation is not a guarantee
that every modeled physical route has been tested in the game.

The old APWorld under validation/dodongo_1811/inputs is audit-only. Use the
current APWorld in the ZIP root if installation is needed.
'''
    (PACKAGE / "README.txt").write_text(readme, encoding="utf-8")
    validation_text = (
        "SOH-EXTREME 1.8.11 entrance-fix validation\n\n"
        "Fresh reports:\n" + "".join("- " + n + "\n" for n in reports) +
        "- entrance_fixes_1811_source_completeness.json\n"
        "- entrance_fixes_1811_source_build_validation.json\n\n"
        "All 190 previous replacement files retained. APWorld and all AP sources unchanged.\n"
        "Current reports bind exact source bytes; prior reports remain historical.\n"
        "No complete native Windows build or in-game playthrough was performed.\n")
    (PACKAGE / "VALIDATION.txt").write_text(validation_text)
    (VALIDATION / "SCOPE.txt").write_text(validation_text)
    added_paths.update({"README.txt", "VALIDATION.txt",
                        (VALIDATION / "SCOPE.txt").relative_to(PACKAGE).as_posix()})
    summary = {"status": "passed", "version": VERSION,
               "complete_source_files": len(manifest["files"]),
               "base_archive_sha256": BASE_SHA,
               "all_previous_replacement_files_retained": True,
               "apworld_unchanged": True, "native_source_only_behavior_change": True,
               "requires_new_seed_for_this_update": False,
               "fresh_report_sha256": {p.name: sha(p.read_bytes()) for p in report_paths},
               "source_sha256": completeness["source_sha256"],
               "manifest_sha256": completeness["manifest_sha256"],
               "apworld_sha256": completeness["apworld_sha256"]}
    (VALIDATION / "entrance_fixes_1811_release_validation.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    added_paths.add((VALIDATION / "entrance_fixes_1811_release_validation.json").relative_to(PACKAGE).as_posix())
    contents = {p.relative_to(PACKAGE).as_posix(): p.read_bytes()
                for p in PACKAGE.rglob("*") if p.is_file()}
    assert set(contents) == set(completeness["prepared_archive_paths"]) | added_paths, {
        "unexpected_stage_paths": sorted(set(contents) - set(completeness["prepared_archive_paths"]) - added_paths),
        "missing_stage_paths": sorted((set(completeness["prepared_archive_paths"]) | added_paths) - set(contents)),
    }
    assert not any(n.startswith("payload/") or n.endswith((".patch", ".diff")) for n in contents)
    write_source_archive(ARCHIVE, contents, datetime.now(timezone.utc))
    with zipfile.ZipFile(ARCHIVE) as result:
        assert result.testzip() is None
        assert {n: result.read(n) for n in result.namelist()} == contents
    output = {"status": "passed", "archive": str(ARCHIVE), "size_bytes": ARCHIVE.stat().st_size,
              "sha256": sha(ARCHIVE.read_bytes()), "complete_source_files": len(manifest["files"]),
              "archive_entries": len(contents), "every_member_byte_verified": True}
    (ROOT / "tests/entrance_fixes_1811_archive_validation.json").write_text(
        json.dumps(output, indent=2) + "\n")
    print(json.dumps(output))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "finalize"))
    parser.add_argument("--report", type=Path, action="append", default=[])
    arguments = parser.parse_args()
    if arguments.action == "prepare":
        prepare()
    else:
        finalize(arguments.report)
