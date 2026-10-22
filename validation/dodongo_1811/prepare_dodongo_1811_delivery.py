"""Package cumulative complete source files for the 1.8.11 Dodongo/transition fixes.

The corrected APWorld and cumulative sources share version 1.8.11.
Historical reports keep their original bytes and source-hash bindings.
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
BASE = ROOT / "delivery/SOH-EXTREME-1.8.10-buildfix-source-files.zip"
BASE_SHA = "09fd56ce1da976b16d4d2d38b904c51478313996755054a0ea6157dee57e6d02"
PACKAGE = ROOT / "delivery/SOH-EXTREME-1.8.11-source-files"
ARCHIVE = PACKAGE.parent / (PACKAGE.name + ".zip")
VALIDATION = PACKAGE / "validation/dodongo_1811"
VERSION = "1.8.11"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(path: Path):
    return json.loads(path.read_bytes())


def apworld_contents():
    world = SOURCE / "archipelago/soh_extreme"
    contents = {"archipelago.json": (SOURCE / "archipelago/archipelago.json").read_bytes()}
    contents.update({"soh_extreme/" + path.relative_to(world).as_posix(): path.read_bytes()
                     for path in world.rglob("*") if path.is_file() and
                     "__pycache__" not in path.parts and path.suffix != ".pyc"})
    assert contents["archipelago.json"] == contents["soh_extreme/archipelago.json"]
    assert json.loads(contents["archipelago.json"])["world_version"] == VERSION
    return contents


def build_apworld():
    contents = apworld_contents()
    target = SOURCE / "archipelago/soh_extreme.apworld"
    write_source_archive(target, contents, datetime.now(timezone.utc))
    print(json.dumps({"status": "built", "version": VERSION, "apworld_entries": len(contents),
                      "apworld_sha256": sha(target.read_bytes())}))


def prepare():
    assert sha(BASE.read_bytes()) == BASE_SHA
    with zipfile.ZipFile(SOURCE / "archipelago/soh_extreme.apworld") as world:
        assert {name: world.read(name) for name in world.namelist()} == apworld_contents()
    changed, _, original_count, current_count = inventory()
    with zipfile.ZipFile(BASE) as base, zipfile.ZipFile(ROOT / "upload/haha.zip") as original:
        old_manifest = json.loads(base.read("SOURCE_FILES.json"))
        previous = {row["path"]: row for row in old_manifest["files"]}
        assert set(previous) <= set(changed), sorted(set(previous) - set(changed))
        contents = {}
        for name in base.namelist():
            assert not name.endswith("/")
            target = "validation/base_1.8.10_buildfix/" + name if name in (
                "README.txt", "VALIDATION.txt", "SOURCE_FILES.json") else name
            contents[target] = base.read(name)
        rows, delta = [], {}
        for name, metadata in sorted(changed.items()):
            current = (SOURCE / name).read_bytes()
            before = base.read(name) if name in previous else (
                original.read(name) if name in original.namelist() else None)
            row = dict(previous.get(name, {}))
            row.update(metadata)
            if name == "archipelago/soh_extreme.apworld":
                with zipfile.ZipFile(SOURCE / name) as world:
                    row["zip_contents"] = {"entries": [
                        {"path": member, "size_bytes": len(world.read(member)),
                         "sha256": sha(world.read(member))} for member in sorted(world.namelist())]}
            rows.append(row)
            contents[name] = current
            if current != before:
                delta[name] = {"change": "modified" if before is not None else "added",
                               "previous_sha256": sha(before) if before is not None else None,
                               "sha256": sha(current), "size_bytes": len(current)}
        assert delta, "No source changes to deliver"
        contents["soh_extreme.apworld"] = (SOURCE / "archipelago/soh_extreme.apworld").read_bytes()
        assert contents["soh_extreme.apworld"] == contents["archipelago/soh_extreme.apworld"]
        assert contents["soh/Enhancements/randomizer/logic.cpp"] == base.read("soh/Enhancements/randomizer/logic.cpp")
        assert contents["soh/Enhancements/randomizer/logic.cpp"].startswith(
            b"#include <libultraship/bridge/consolevariablebridge.h>\r\n")
        manifest = {"version": VERSION, "layout": "complete_source_files", "build_helper_revision": 4,
                    "release": "Dodongo switch logic, bombable walls and descriptive room destinations.",
                    "files": rows}
        contents["SOURCE_FILES.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
        for name in ("BUILD_RELEASE.cmd", "BUILD_RELEASE.ps1"):
            contents[name] = base.read(name).replace(b"1.8.10", b"1.8.11")
        assert contents["SOH-EXTREME.yaml"] == base.read("SOH-EXTREME.yaml")
    for name, data in contents.items():
        path = PACKAGE / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    VALIDATION.mkdir(parents=True, exist_ok=True)
    report = {
        "status": "passed", "version": VERSION, "release": "dodongo-switch-wall-labels",
        "base_archive_sha256": BASE_SHA, "original_source_files": original_count,
        "current_source_files": current_count, "complete_source_files": len(rows),
        "changes_since_buildfix": delta, "all_previous_source_files_retained": True,
        "unmanifested_source_changes": [], "apworld_matches_current_source": True, "yaml_unchanged": True,
        "cvar_declaration_fix_retained": True, "build_helpers_unchanged_except_version": True,
        "source_sha256": {row["path"]: row["sha256"] for row in rows},
        "manifest_sha256": sha(contents["SOURCE_FILES.json"]),
        "apworld_sha256": sha(contents["soh_extreme.apworld"]),
    }
    (ROOT / "tests/dodongo_1811_source_completeness.json").write_text(json.dumps(report, indent=2) + "\n")
    with zipfile.ZipFile(BASE) as base, zipfile.ZipFile(io.BytesIO(base.read("soh_extreme.apworld"))) as old_world:
        stable = ("archipelago/soh_extreme/EntranceCatalog.json",
                  "archipelago/soh_extreme/DungeonDoorCatalog.json",
                  "archipelago/soh_extreme/EntranceDestinationPolicy.json",
                  "archipelago/soh_extreme/CheckDescriptions.json",
                  "archipelago/soh_extreme/__init__.py")
        for name in stable:
            assert (SOURCE / name).read_bytes() == old_world.read(name.removeprefix("archipelago/")), name
    world_contents = apworld_contents()
    version_files = ("archipelago/archipelago.json", "archipelago/soh_extreme/archipelago.json",
                     "archipelago/soh_extreme/TrackerMirror.py", "soh/SohExtremeVersion.h")
    assert all(b"1.8.11" in (SOURCE / name).read_bytes() for name in version_files)
    ap_report = {"status": "passed", "version": VERSION, "entries": len(world_contents),
                 "apworld_sha256": report["apworld_sha256"],
                 "every_archive_entry_matches_current_source": True,
                 "all_four_version_markers_match": True,
                 "unchanged_entrance_catalogs_destination_policy_and_check_names": True,
                 "unchanged_world_item_and_location_registry": True,
                 "stable_source_sha256": {name: sha((SOURCE / name).read_bytes()) for name in stable},
                 "version_source_sha256": {name: sha((SOURCE / name).read_bytes()) for name in version_files},
                 "archive_entry_sha256": {name: sha(data) for name, data in sorted(world_contents.items())}}
    (ROOT / "tests/dodongo_1811_apworld_validation.json").write_text(json.dumps(ap_report, indent=2) + "\n")
    print(json.dumps({"status": "prepared", "package": str(PACKAGE), "source_files": len(rows),
                      "source_changes": list(delta), "apworld_matches_current_source": True}))


def finalize():
    manifest = read(PACKAGE / "SOURCE_FILES.json")
    completeness = read(ROOT / "tests/dodongo_1811_source_completeness.json")
    reports = {
        name: read(ROOT / "tests" / name) for name in (
            "dodongo_1811_source_build_validation.json", "dodongo_1811_apworld_validation.json",
            "wall_collision_1811_native.json", "entrance_hallway_boundary_1811_native.json",
            "dodongo_armos_1811_ap_logic.json", "dodongo_armos_1811_native_logic.json",
            "transition_labels_1810_native.json", "dodongo_1811_full_fill_child.json",
            "dodongo_1811_full_fill_adult.json")}
    assert completeness["status"] == "passed"
    assert all(report["status"] == "passed" for report in reports.values())
    for row in manifest["files"]:
        name = row["path"]
        assert row["sha256"] == sha((SOURCE / name).read_bytes()) == sha((PACKAGE / name).read_bytes()), name
    current, _, _, _ = inventory()
    assert set(current) == {row["path"] for row in manifest["files"]}
    assert completeness["manifest_sha256"] == reports["dodongo_1811_source_build_validation.json"]["manifest_sha256"]
    assert completeness["apworld_sha256"] == reports["dodongo_1811_apworld_validation.json"]["apworld_sha256"]
    assert completeness["apworld_sha256"] == sha((PACKAGE / "soh_extreme.apworld").read_bytes())
    for name, report in reports.items():
        for key in ("sources", "source_sha256", "test_sha256", "stable_source_sha256", "version_source_sha256"):
            for relative, expected in report.get(key, {}).items():
                assert sha((SOURCE / relative).read_bytes()) == expected, (name, key, relative)
    exact_name = "uploaded_seed_1810_dc_exact_metadata.json"
    replay_name = "uploaded_seed_1811_dc_corrected_replay.json"
    exact, replay = read(ROOT / "tests" / exact_name), read(ROOT / "tests" / replay_name)
    assert exact["status"] == "exactly_reproduced" and exact["matching_placements"] == 4036
    assert exact["mismatched_placements"] == 0 and len(exact["mapping"]) == 719
    assert exact["child_spawn"]["id"] == 8354 and exact["child_spawn"]["room"] == 5
    assert replay["status"] == "audit_completed" and replay["world_version"] == VERSION
    assert replay["checked_network_locations"] == 2 and replay["blocked_network_locations"] == 4034
    assert replay["goal_met"] is False and replay["all_network_placements_restored_exactly"]
    assert replay["all_network_item_classifications_restored_exactly"] and replay["all_shop_prices_restored_exactly"]
    assert replay["exact_reproduction_sha256"] == sha((ROOT / "tests" / exact_name).read_bytes())
    assert sha((ROOT / "upload/AP_98530958489753355589_Spoiler.txt").read_bytes()) == exact["spoiler_sha256"] == replay["spoiler_sha256"]
    for relative, expected in replay["source_sha256"].items():
        assert sha((SOURCE / relative).read_bytes()) == expected, relative
    baseline_source = ROOT / "tests/uploaded_seed_1810_dc_baseline/source"
    for relative, expected in exact["source_sha256"].items():
        assert sha((baseline_source / relative).read_bytes()) == expected, relative
    assert reports["dodongo_armos_1811_ap_logic.json"]["input_evidence_sha256"] == sha((ROOT / "tests" / exact_name).read_bytes())
    for age in ("child", "adult"):
        report = reports[f"dodongo_1811_full_fill_{age}.json"]
        player = report["validation"]["players"]["1"]
        assert report["version"] == VERSION and report["age"] == age
        assert report["requested_age"] == age and report["resolved_age_matches_requested"]
        assert report["resolved_options"]["starting_age"].casefold() == age
        if age == "adult":
            assert report["resolved_options"]["closed_forest"] == "Off"
            assert set(report["option_overrides"]) == {"closed_forest"}
        else:
            assert report["option_overrides"] == {}
            assert report["resolved_options"]["closed_forest"] == "On"
        assert report["initial_hyrule_field_reachable"] and report["initial_progression"]
        assert player["goal_met"] and player["checked"] == player["network_checks"] == 4036
        assert report["original_exact_reproduction_sha256"] == sha((ROOT / "tests" / exact_name).read_bytes())
        for relative, expected in report["fixture_sha256"].items():
            assert sha((ROOT / "tests" / relative).read_bytes()) == expected, relative

    evidence = list(reports) + ["dodongo_1811_source_completeness.json", exact_name, replay_name]
    for name in evidence:
        shutil.copyfile(ROOT / "tests" / name, VALIDATION / name)
    scripts = ("dodongo_1811_source_build_check.py", "entrance_184_source_build_probe.ps1",
               "dodongo_1811_full_fill.py", "audit_uploaded_seed_189.py", "replay_uploaded_seed_1810.py")
    for name in scripts:
        shutil.copyfile(ROOT / "tests" / name, VALIDATION / name)
    shutil.copyfile(Path(__file__), VALIDATION / Path(__file__).name)
    inputs = VALIDATION / "inputs"
    inputs.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "upload/AP_98530958489753355589_Spoiler.txt", inputs / "AP_98530958489753355589_Spoiler.txt")
    with zipfile.ZipFile(BASE) as base:
        (inputs / "original_world_1.8.10.apworld").write_bytes(base.read("soh_extreme.apworld"))
    (VALIDATION / "SCOPE.txt").write_text(
        "These are current 1.8.11 source, rule, display and seed validation results.\n"
        "The transition-label report keeps its original 1810 filename but binds the final delivered source.\n"
        "The old uploaded seed was exactly reproduced with its original 1.8.10 APWorld, then replayed\n"
        "without changing any mapping, network item/classification or shop price under corrected 1.8.11 rules.\n"
        "The original_world_1.8.10.apworld under inputs is audit-only: install the current root APWorld.\n"
        "The fresh child full fill uses the reported options and new rule model.\n"
        "The adult variant explicitly sets Closed Forest Off because On forces Child; both assert the actual age.\n"
        "Full-fill validation creates no game output files.\n"
        "Production-function fixtures isolate engine I/O; they are not a full native build or in-game playthrough.\n"
        "Older reports elsewhere in validation keep their original bytes and historical source hashes.\n")
    summary = {
        "status": "passed", "version": VERSION, "utc": datetime.now(timezone.utc).isoformat(),
        "complete_source_files": len(manifest["files"]),
        "source_sha256": completeness["source_sha256"], "manifest_sha256": completeness["manifest_sha256"],
        "apworld_sha256": completeness["apworld_sha256"], "base_archive_sha256": BASE_SHA,
        "reports_sha256": {name: sha((ROOT / "tests" / name).read_bytes()) for name in evidence},
        "uploaded_seed_exact_placements": 4036, "uploaded_seed_corrected_reachable": 2,
        "uploaded_seed_goal_reachable": False, "fresh_child_full_fill_passed": True,
        "fresh_adult_full_fill_passed": True, "native_game_build": False,
        "scope": "Cumulative source manifest, actual shipped build-helper preflight, APWorld/source identity, native fixtures and official AP generation/replay. No complete Windows build, ROM-geometry measurement or controller playthrough.",
    }
    (VALIDATION / "dodongo_1811_release_validation.json").write_text(json.dumps(summary, indent=2) + "\n")
    count = len(manifest["files"])
    (PACKAGE / "README.txt").write_text(r'''SOH-EXTREME 1.8.11 - Complete source files
==========================================

DODONGO'S CAVERN STARTING SOFTLOCK
--------------------------------
Both exits from Armos Room, room 5, are barred by temporary switch 0x22 on the
central pillar. The stairs-side exit was incorrectly considered free by the
native/AP rules. Both exits now require the current age's switch-access action.
The normal child route needs Grab / Power Bracelet and Climb. The structural
statue has no Armos Soul or Rock / Boulder Soul requirement. The adult ledge
route and genuinely usable alternate actions retain their authored behavior.

The switch is temporary scene state, so an earlier adult visit cannot permanently
unlock it for an unequipped child. The Armos Room -> Bomb Room shortcut now passes
through the physical Entrance Side Bridge doorway and cannot bypass its mapping.

Your AP_98530958489753355589 seed was exactly reproduced: all 4,036 items and 719
entrance connections match. Its child spawn enters Armos Room 5. With the corrected
rules, the unchanged seed reaches only Link's Pocket and Song from Impa: 2 of 4,036,
then stops. It requires regeneration with the included 1.8.11 APWorld and a new save.
Updating the native executable cannot move that seed's fixed items or entrance map.

BOMBABLE WALLS
--------------
The small mud walls now register their receiving collider during the actor update
instead of Draw. Their solid barrier can receive explosive and ordinary Hammer
hits when the model is not drawn. The attack mask, normal switch, break effects,
King Dodongo floor and lava-cover behavior are retained. No new Soul is required.

ROOM DESTINATION LABELS
----------------------
The opt-in world destination labels put a descriptive arrival first, for example:

  Door to Deku Tree: Basement Torch Room
  Room 6

The number is the actual destination room for a mapped room door. Raw native
boss-return names such as RR_FOREST_TEMPLE_BOSS_ENTRYWAY are now readable names.
Real scene-exit handle identities distinguish front/back exits sharing a scene.
Preloading a room does not reverse a label while Link remains on the source side.
Native passages show their physical destinations, including vertical/drop types.
Unknown destination-room numbers are left unspecified; spawn indices are not rooms.

In Check Finder, Show room and door numbers remains optional and off by default.
When enabled, the destination room and source door details are below the descriptive
check name. Existing age suffixes and player aliases are preserved. AP check names,
location IDs, entrance catalogs and destination policy are unchanged.

INSTALL AND BUILD
-----------------
1. Merge soh, src, archipelago and tools into your complete checkout, replacing
   the corresponding files. Replace SOURCE_FILES.json in the checkout root too,
   and copy BUILD_RELEASE.cmd and BUILD_RELEASE.ps1 there.
2. For your E:\test\bb checkout, run:

   cd /d E:\test\bb
   BUILD_RELEASE.cmd -RepositoryPath "E:\test\bb" -BuildDirectory "build-vs"

   The helper verifies the complete sources, performs a clean Release build and
   prints the executable path. Use your actual paths if different.
3. Install the ROOT soh_extreme.apworld from this ZIP to:
   C:\ProgramData\Archipelago\custom_worlds\soh_extreme.apworld
4. Generate a new seed with 1.8.11 and start its new save. Your reported Armos-room
   seed is blocked; do not resume that save expecting the placement to change.

All prior source fixes are included, including logic.cpp's direct console-variable
declaration-header include for the C3861 error. A local EnHoll pointer/fixture
signature now matches the native coordinate API; its routing behavior is unchanged.

VALIDATION
----------
Fresh evidence is under validation/dodongo_1811/. It includes the exact original
seed reproduction and corrected replay, focused native/AP regressions, separate
child/adult full fills, current APWorld/source verification and the actual build
helper's source preflight. The child test uses your reported settings. The adult
test explicitly changes Closed Forest to Off because On forces Child, and both
tests assert the age actually generated. Native fixtures execute production functions with
explicit engine I/O shims. No full Windows game build or controller playthrough
was performed in this partial-source environment.

Historical reports elsewhere in validation retain their original source hashes.
The old APWorld under validation/dodongo_1811/inputs is ONLY for reproducing the
failed original seed; install the 1.8.11 APWorld in this ZIP's root.
''' +
        f"\nCONTENTS: {count} complete replacement source files, matching APWorld, YAML and build helpers.\n")
    (PACKAGE / "VALIDATION.txt").write_text(
        f"SOH-EXTREME 1.8.11 validation: PASSED\n{count} complete replacement source files.\n"
        "Current evidence: validation/dodongo_1811/\n"
        "Walls: 52 cases / 347 assertions. Hallway signature: 65 cases / 144 assertions.\n"
        "Armos native switch logic: 83 cases / 926 assertions. AP: 8 methods / 230 decisions.\n"
        "Destination labels: 1,278 cases / 6,910 assertions; standalone header compilation passed.\n"
        "Native fixtures passed AddressSanitizer and UndefinedBehaviorSanitizer.\n"
        "Original seed: 4,036 exact placements and 719 mappings; corrected unchanged replay 2/4,036, goal false.\n"
        "Fresh child and adult full fills: 4,036/4,036 and goal reachable in each.\n"
        "Actual generated ages asserted; adult variant explicitly uses Closed Forest Off.\n"
        "APWorld bytes and complete source manifest verified by the shipped helper.\n"
        "No full Windows native build or gameplay test performed.\n")
    contents = {p.relative_to(PACKAGE).as_posix(): p.read_bytes() for p in PACKAGE.rglob("*") if p.is_file()}
    assert not any(name.startswith("payload/") or name.endswith((".patch", ".diff")) for name in contents)
    write_source_archive(ARCHIVE, contents, datetime.now(timezone.utc))
    result = {"status": "passed", "version": VERSION, "archive": str(ARCHIVE),
              "sha256": sha(ARCHIVE.read_bytes()), "size_bytes": ARCHIVE.stat().st_size,
              "complete_source_files": count, "archive_files": len(contents),
              "zip_crc_and_inventory_verified": True, "patch_files": 0}
    (ROOT / "tests/dodongo_1811_source_zip_validation.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build-apworld", "prepare", "finalize"))
    args = parser.parse_args()
    {"build-apworld": build_apworld, "prepare": prepare, "finalize": finalize}[args.action]()
